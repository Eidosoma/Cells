"""Check inner-cycle charge cancellation and an open-circuit passive face as separate components."""

import json
import math
from decimal import Decimal, localcontext
from types import SimpleNamespace

import jax
import jax.numpy as jnp
import numpy as np
from mitochondrial_cycles import seven_cycle_world

from cells.execution.runner import run
from cells.kinds import transporter
from cells.laws.electrochemistry import CHARGE_PER_FMOL, MOL_PER_FMOL, F, R
from cells.numerics import extracellular_field
from tests.unit import test_mito_cycle_laws as fixtures


def inner_cycles():
    raw = seven_cycle_world()
    dt = raw["execution"]["dt"]
    raw["experiment"].update(end_time=2 * dt, observation_times=[0, dt, 2 * dt])
    spec, _, _, layout, _ = fixtures.start(raw)
    lumen = [x.id for x in spec.model.extracellular].index("lumen_0")
    z = np.array(spec.model.valence)
    trajectory = run(spec)
    h = trajectory.history
    rows = []
    for k in range(1, len(trajectory.times)):
        state = type(h)(*(a[k] for a in h))
        books = transporter.ledger_terms(state, layout, xp=np)
        matrix = z * books["cell"][:, 0]
        ims = z * books["outside"][:, lumen]
        net = math.fsum([*matrix, *ims])
        gross = math.fsum([*abs(matrix), *abs(ims)])
        assert abs(net) <= 128 * np.finfo(float).eps * gross and abs(math.fsum(matrix)) > 0
        assert np.count_nonzero(state.cycle_count[0]) == 7
        rows.append(
            dict(matrix_fmol_eq=math.fsum(matrix), ims_fmol_eq=math.fsum(ims), combined_fmol_eq=net)
        )
    assert trajectory.final.step_index == 2 and len(rows) == 2
    return rows


def passive_face():
    # One edge from IMS to a gauged bath, with two mobile monovalent forms of opposite valence.
    # This is the engine's generic face solver. Bound-form closure and the MT-1b host are separate.
    z = np.array([1.0, -1.0])
    layout = SimpleNamespace(
        face_active=np.array([True]),
        senders=np.array([0]),
        receivers=np.array([1]),
        face_factor=np.full((2, 1), 1e-18),
        temperature=310.15,
        valence=z[:, None],
        extracellular_active=np.array([True, True]),
        gauge_mask=np.array([False, True]),
    )
    solve = jax.jit(lambda n: extracellular_field.solve(n, layout, xp=jnp))
    reference = Decimal(1)
    rows = {}
    for name, inside in (("matched", [1, 1]), ("moving_salt", [2, 2]), ("unequal", [3, 2])):
        amounts = np.array([[x, 1] for x in inside], dtype=float)
        solution = solve(amounts)
        v = float(solution.potential_V[0] - solution.potential_V[1])
        flux = np.asarray(solution.flux_fmol_per_s)[:, 0]
        current = math.fsum(z * flux)
        gross = math.fsum(abs(z * flux))
        assert abs(current) <= 128 * np.finfo(float).eps * gross
        logs = [Decimal(x).ln() for x in inside]
        means = [
            (Decimal(x) - reference) / log if log else reference
            for x, log in zip(inside, logs, strict=True)
        ]
        diffusion = means[0] * logs[0] - means[1] * logs[1]
        expected = (
            -Decimal(str(R))
            * Decimal(str(layout.temperature))
            / Decimal(str(F))
            * diffusion
            / sum(means)
        )
        voltage_scale = (
            R
            * layout.temperature
            / F
            * float(sum(abs(m * log) for m, log in zip(means, logs, strict=True)) / sum(means))
        )
        assert abs(v - float(expected)) <= 128 * np.finfo(float).eps * voltage_scale
        # At zero voltage the log mean times the log ratio equals the concentration difference.
        forced = layout.face_factor[0, 0] / MOL_PER_FMOL * (inside[0] - inside[1])
        forced_engine = float(solution.diffusion_current_A[0]) / CHARGE_PER_FMOL
        assert abs(forced - forced_engine) <= 128 * np.finfo(float).eps * max(gross, abs(forced))
        if name == "matched":
            assert v == 0 and gross == 0
        elif name == "moving_salt":
            assert np.all(flux > 0) and forced == 0
        else:
            assert v < 0 and np.all(flux > 0) and abs(forced) > 1e8 * abs(current)
        rows[name] = dict(
            ims_minus_bath_mV=1000 * v,
            net_outward_fmol_eq_s=current,
            gross_fmol_eq_s=gross,
            forced_zero_voltage_fmol_eq_s=forced,
            ims_charge_at_unit_volume_fmol_eq=inside[0] - inside[1],
        )
    assert (
        rows["matched"]["ims_charge_at_unit_volume_fmol_eq"]
        != rows["unequal"]["ims_charge_at_unit_volume_fmol_eq"]
    )
    return rows


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    with localcontext() as ctx:
        ctx.prec = 65
        print(
            json.dumps(
                dict(
                    inner_cycle_steps=inner_cycles(),
                    outer_face=passive_face(),
                    integrated_mt1b="pending",
                ),
                indent=2,
                allow_nan=False,
            )
        )
