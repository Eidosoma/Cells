"""Production schema/RHS and prescribed one-transfer contact; not an ODE step."""

import sys

import pilot_context as ctx
from pilot_math import Ledger, canonical, native_rates

c = ctx.c


def check_held(row, variant, index, compiled, ledger):
    import jax.numpy as jnp
    import numpy as np

    from cells.core.schedule import PhysicalIonicGraphControl, control_values
    from cells.core.specs import parse_spec
    from cells.models import kinetic_finite_extracellular as model

    raw = row["trace"]["raw_steps"][index]
    case = ctx.case_for(row, variant, physical=raw["before"]["physical"])
    definition = ctx.definition(case, 5e-5)
    spec = parse_spec(definition)
    c.require(spec.to_dict() == definition, "Mapping canonicalization changed inputs")
    state, layout = model.initial_values(spec)
    control = PhysicalIonicGraphControl(*(v[0] for v in control_values(spec, [0.0])))
    native = native_rates(row, variant, raw)
    tol = c.read(ctx.PROTOCOL)["mapping"]
    checks = []
    for backend in ("numpy", "jax_eager", "jax_jit"):
        rate = (
            compiled(state, control, layout, layout.active)
            if backend == "jax_jit"
            else model.rhs(
                state, control, layout, layout.active, xp=np if backend == "numpy" else jnp
            )
        )
        rate_values = {k: np.asarray(v).tolist() for k, v in rate._asdict().items()}
        value = canonical(rate_values)
        ledger.compare("rates_fmol_s", value[:52], native[:52], tol["flux_fmol_s"], tol["relative"])
        ledger.compare(
            "dissipation_pJ_s", value[52:], native[52:], tol["power_pJ_s"], tol["relative"]
        )
        for name in (
            "gate",
            "channel_transferred",
            "junction_gate",
            "junction_transferred",
            "junction_dissipated_energy_pJ",
        ):
            c.require(np.all(np.asarray(getattr(rate, name)) == 0), "Inactive mechanism owns rate")
        c.require(
            np.all(np.asarray(rate.amount_increment)[:, 7:] == 0)
            and np.all(np.asarray(rate.leak_transferred)[:, 7:] == 0)
            and np.all(np.asarray(rate.pump_cycles)[7:] == 0)
            and np.all(np.asarray(rate.extracellular_amount_increment)[:, 1:] == 0),
            "Padding owns rate",
        )
        # This checks the conservative transfer map under a held flux. It is not
        # the RK4 integrator and is not claimed to be a production trajectory.
        prescribed = model.STATE_TYPE(
            *(np.asarray(s) + row["dt_s"] * np.asarray(v) for s, v in zip(state, rate, strict=True))
        )
        after = row["trace"]["steps"][index]["after_voltage"]["physical"]
        inside = (np.asarray(layout.amount_reference) + prescribed.amount_increment) / np.asarray(
            layout.volume
        )
        outside = (
            np.asarray(layout.extracellular_amount_reference)
            + prescribed.extracellular_amount_increment
        ) / np.asarray(layout.extracellular_volume)
        ledger.compare(
            "one_transfer_inside_mM",
            inside[:, :7].tolist(),
            after["inside_mM"][:3],
            tol["concentration_mM"],
            tol["relative"],
        )
        ledger.compare(
            "one_transfer_outside_mM",
            outside[:, 0].tolist(),
            [ctx.uniform(v) for v in after["outside_mM"][:3]],
            tol["concentration_mM"],
            tol["relative"],
        )
        voltage = model.cell_voltage(prescribed.amount_increment, layout, xp=np)
        ledger.compare(
            "one_transfer_voltage_V",
            np.asarray(voltage)[:7].tolist(),
            ctx.owners(after["voltage_V"], row["geometry"]),
            tol["voltage_V"],
            tol["relative"],
        )
        checks.append(dict(backend=backend, rate=value))
    return dict(
        variant=variant["id"],
        native_step=index,
        case=case,
        definition=definition,
        native_rate=native,
        backends=checks,
    )


def worker(r, output):
    import jax

    from cells.models import kinetic_finite_extracellular as model

    c.require(
        jax.default_backend() == "cpu"
        and jax.config.x64_enabled
        and not jax.config.jax_disable_jit,
        "Mapping CPU float64/JIT",
    )
    compiled = jax.jit(model.rhs)
    rows = ctx.native_rows()
    variants = r["native_preparation"]["protocol"]["variants"]
    ledger = Ledger()
    records = []
    for variant in variants:
        for index in range(8):
            records.append(
                check_held(rows[variant["id"] + "/observed"], variant, index, compiled, ledger)
            )
    c.require(
        len(records) == 48 and not any(n == "betse" or n.startswith("betse.") for n in sys.modules),
        "Mapping coverage/isolation",
    )
    return dict(
        status="held_state_mapping_pass",
        held_states=48,
        backend_evaluations=144,
        comparisons=ledger.comparisons,
        maxima=ledger.maxima,
        records=records,
        time_integration_run=False,
        biological_parameters_fitted=False,
    )
