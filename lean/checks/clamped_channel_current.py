"""Compare @3 instantaneous clamp currents with a 70-digit GHK reference."""

import argparse
import json
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions import pump_composite_spec
from cells.definitions.specs import parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.models import surface_pump_v3 as host
from cells.registry.models import get_model
from ion_channels import REFERENCES
from tests.unit.test_chloride_leak_law import chloride_world
from validation.betse.junction_transport.check import decimal_flux
from validation.tissue import regulated_availability_fixtures as gates
from validation.tissue.surface_pump_v3_fixtures import channel
from validation.tissue.surface_reference import F, R


POWERS = {law: (ion, powers) for law, (_, _, ion, powers) in REFERENCES.items()}
POWERS["cells.channel.clleak_always_open@1"] = ("Cl", (0, 0))
VOLTAGES = np.array([
    [-0.120, 0.060], [-0.075, 0.018], [0.0, 0.0],
    [4e-7, -5e-7], [0.040, -0.100], [0.060, -0.120],
])


def specimen(abundance):
    raw = chloride_world(patch=0.0, swap=0.5)
    model, exp = raw["model"], raw["experiment"]
    cell, bath, patch = (model[key][0] for key in ("cells", "extracellular", "membranes"))
    model["cells"].append(dict(cell, id="cell_1"))
    model["extracellular"].append(dict(bath, id="bath_1"))
    patch["pump"] = None
    exp["pump_controls"] = []
    model["membranes"].append(dict(patch, id="membrane_1", inside="cell_1", outside="bath_1"))
    exp["membrane_controls"].append(dict(exp["membrane_controls"][0], membrane_id="membrane_1"))
    model["channels"] = []
    exp["channel_controls"] = []
    for i, (law, (ion, powers)) in enumerate(POWERS.items()):
        name = f"ch_{i:02d}"
        gate = [0.25 + 0.02 * i, 0.80 - 0.03 * i] if any(powers) else []
        model["channels"].append(channel(name, i % 2, law, ion, 4e-9, abundance, gate))
        exp["channel_controls"].append(dict(channel_id=name, schedule=[dict(time=0.0, availability=1.0)]))
    raw["execution"].update(capacity=2, extracellular_capacity=2, membrane_capacity=2,
                            channel_capacity=len(POWERS) + 1)
    return raw


def reference(raw):
    model = raw["model"]
    species = [s["id"] for s in model["species"]]
    charge = {s["id"]: s["valence"] for s in model["species"]}
    cells = {c["id"]: c for c in model["cells"]}
    baths = {b["id"]: b for b in model["extracellular"]}
    patches = {p["id"]: (i, p) for i, p in enumerate(model["membranes"])}
    flux = np.zeros((len(VOLTAGES), len(species), raw["execution"]["channel_capacity"]))
    current = np.zeros((len(VOLTAGES), flux.shape[-1]))
    for j, ch in enumerate(model["channels"]):
        ion, (mp, hp) = POWERS[ch["kinetic_law"]]
        m, h = ch["initial_gate"] or (1.0, 1.0)
        owner, patch = patches[ch["membrane_id"]]
        cell, bath = cells[patch["inside"]], baths[patch["outside"]]
        ci = cell["initial_amount_fmol"][ion] / cell["volume_pL"]
        co = bath["initial_amount_fmol"][ion] / bath["volume_pL"]
        for k, voltage in enumerate(VOLTAGES[:, owner]):
            j_out = decimal_flux(ci, co, voltage, charge[ion], model["temperature_K"],
                                 patch["area_m2"], ch["max_permeability_m_per_s"], 1,
                                 ch["abundance"] * m**mp * h**hp, {"F": F, "R": R})
            flux[k, species.index(ion), j] = j_out
            current[k, j] = charge[ion] * 1e-15 * F * j_out
    return flux, current


def run():
    if jax.default_backend() != "cpu" or not jax.config.x64_enabled:
        raise RuntimeError("Use the CPU backend with JAX_ENABLE_X64=1")
    raw = specimen(0.5)
    expected_flux, expected_current = reference(raw)
    spec = parse_spec(raw)
    impl = get_model(spec.model)
    state, layout = impl.initial_values(spec)
    control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
    lower_count = parse_spec(specimen(0.25))
    low_state, low_layout = get_model(lower_count.model).initial_values(lower_count)
    half = control._replace(channel=control.channel * 0.5)
    blocked = control._replace(channel=control.channel * 0.0)
    compiled = jax.jit(jax.vmap(
        lambda v, s, c, p: impl.clamped_channel_flux(s, c, p, v, xp=jnp),
        in_axes=(0, None, None, None),
    ))

    def numpy_rows(s, c, p):
        rows = [impl.clamped_channel_flux(s, c, p, v, xp=np) for v in VOLTAGES]
        return tuple(np.stack(values) for values in zip(*rows, strict=True))

    errors = {}
    for backend, evaluate in (("numpy", numpy_rows),
                              ("jax_cpu", lambda s, c, p: compiled(VOLTAGES, s, c, p))):
        flux, current = map(np.asarray, evaluate(state, control, layout))
        np.testing.assert_allclose(flux, expected_flux, rtol=2e-13, atol=0)
        np.testing.assert_allclose(current, expected_current, rtol=2e-13, atol=0)
        for actual, full in zip(evaluate(state, half, layout), (flux, current), strict=True):
            np.testing.assert_array_equal(actual, 0.5 * full)
        for actual, full in zip(evaluate(low_state, control, low_layout), (flux, current), strict=True):
            np.testing.assert_array_equal(actual, 0.5 * full)
        for value in evaluate(state, blocked, layout):
            np.testing.assert_array_equal(value, np.zeros_like(value))
        # Re-evaluate the stacked recorded flux with the same backend's species fold.
        xp = np if backend == "numpy" else jnp
        np.testing.assert_allclose(host.channel_current_A(xp.asarray(flux), layout, xp=xp),
                                   current, rtol=2e-15, atol=0)
        errors[backend] = {
            "max_abs_current_error_A": float(np.max(abs(current - expected_current))),
            "max_abs_flux_error_fmol_s": float(np.max(abs(flux - expected_flux))),
        }
    cl = list(POWERS).index("cells.channel.clleak_always_open@1")
    measurement = json.loads((Path(__file__).parent / "data/maverick2022_kv_density.json").read_text())
    low, high = measurement["maverick2022_kv_density"]["kv15_density_series"]
    return {
        "model": raw["model"]["id"],
        "laws": list(POWERS),
        "voltages_V": VOLTAGES.tolist(),
        "active_populations": len(POWERS),
        "padded_populations": 1,
        "comparisons": errors,
        "chloride_reference_current_pA": (1e12 * expected_current[:, cl]).tolist(),
        "kv15_density_comparison": {
            "gating_channels_per_um2": [low["gating_channels_per_um2"], high["gating_channels_per_um2"]],
            "observed_conducting_fractions": [low["conducting_fraction"], high["conducting_fraction"]],
            "observed_high_over_low": high["conducting_fraction"] / low["conducting_fraction"],
            "high_fraction_if_held_at_low_density_value": low["conducting_fraction"],
        },
    }


def composite_clamp():
    """Compare the public composite entry point with the controls used for its recorded flux."""
    target = gates.SHARED_CHANNEL
    raw = gates.with_coupling(
        gates.scheduled(channel=1.0), species=[gates.REGULATOR],
        states=[gates.frozen("gate", ["cell_3"], 0.5)],
        couplings=[gates.fraction("half_open", "channel", [target], "gate")],
    )
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, layout = model.initial_values(spec)
    times = np.array([0.0])
    control = model.CONTROL_TYPE(*(v[0] for v in pump_composite_spec.control_values(spec, times)))
    slot = next(i for i, ch in enumerate(raw["model"]["channels"]) if ch["id"] == target)
    history = type(state)(*(np.asarray(v)[None] for v in state))
    observed = model.observe_history(times, history, layout, times, spec)
    inner = model.inner
    s = model.inner_state(state)
    p = model.view(layout, state, xp=np)
    held = inner.inner_control(control)
    effective = model.control_view(control, state, layout, xp=np)
    assert effective.channel[slot] == observed.channel_availability[0, slot] == 0.5 * held.channel[slot]
    volt = np.asarray(observed.membrane_voltage_V)[0]
    recorded = host.channel_current_A(np.asarray(observed.channel_flux_fmol_s)[0], p)[slot]
    at_own = inner.clamped_channel_flux(s, effective, p, volt, xp=np)[1][slot]
    held_at_own = inner.clamped_channel_flux(s, held, p, volt, xp=np)[1][slot]
    at_clamp = inner.clamped_channel_flux(s, effective, p, -0.050, xp=np)[1][slot]
    at_held = inner.clamped_channel_flux(s, held, p, -0.050, xp=np)[1][slot]
    np.testing.assert_allclose(at_own, recorded, rtol=2e-14, atol=0)
    assert at_clamp != 0 and recorded != 0
    np.testing.assert_allclose(at_held, 2 * at_clamp, rtol=2e-14, atol=0)
    np.testing.assert_allclose(held_at_own, 2 * recorded, rtol=2e-14, atol=0)
    public = getattr(model, "clamped_channel_flux", None)
    agrees = False
    if public is not None:
        values = [float(public(state, control, layout, v, xp=np)[1][slot]) for v in (volt, -0.05)]
        agrees = bool(np.allclose(values, [recorded, at_clamp], rtol=2e-14, atol=0))
    else:
        values = None
    return dict(model=raw["model"]["id"], channel=target, held=float(held.channel[slot]),
                observed_availability=float(observed.channel_availability[0, slot]),
                held_at_minus50_pA=float(1e12 * at_held), effective_at_minus50_pA=float(1e12 * at_clamp),
                held_at_own_voltage_pA=float(1e12 * held_at_own),
                recorded_at_own_voltage_pA=float(1e12 * recorded), public_currents_A=values,
                public_clamp_matches_both=agrees)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--composite", action="store_true", help="check the operator-controlled composite clamp")
    args = parser.parse_args()
    report = composite_clamp() if args.composite else run()
    print(json.dumps(report, indent=2, allow_nan=False))
    raise SystemExit(int(args.composite and not report["public_clamp_matches_both"]))
