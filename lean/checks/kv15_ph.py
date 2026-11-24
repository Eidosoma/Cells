"""Use Figure 1F activation measurements to predict the distinct Figure 1B step current."""

import json
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
from scipy.optimize import brentq

from cells.definitions.specs import parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.numerics.exponential_gates import advance
from cells.registry import laws
from cells.registry.models import get_model
from tests.unit.test_chloride_leak_law import chloride_world
from validation.tissue.surface_pump_v3_fixtures import channel


def specimen(protocol, *, external_pH=None):
    raw = chloride_world(patch=0.0)
    model = raw["model"]
    for reservoirs, field in (("cells", "inside_K_mM"), ("extracellular", "outside_K_mM")):
        pool = model[reservoirs][0]
        amounts = pool["initial_amount_fmol"]
        potassium = protocol[field] * pool["volume_pL"]
        amounts["Na"] += amounts["K"] - potassium  # Preserve the charge of the fixture.
        amounts["K"] = potassium
    if external_pH is not None:
        # Carry free H as its own positive species. Exchange equal monovalent charge
        # with Na so that changing bath pH preserves each node's declared charge.
        model["species"].append({"id": "H", "valence": 1})
        raw["execution"]["material_balance_atol_fmol"]["H"] = 1e-12
        for group, pH in (("cells", protocol.get("inside_pH", 7.3)),
                          ("extracellular", external_pH)):
            for pool in model[group]:
                amount = pool["volume_pL"] * 10 ** (3 - pH)
                pool["initial_amount_fmol"]["H"] = amount
                pool["initial_amount_fmol"]["Na"] -= amount
        for patch in model["membranes"]:
            patch["permeability_m_per_s"]["H"] = 0.0
    model["membranes"][0]["pump"] = None
    raw["experiment"]["pump_controls"] = []
    model["channels"] = [channel("kv15", 0, "kv1p5_mh@1", "K", 4e-9, 1.0, [0.5, 1.0])]
    raw["experiment"]["channel_controls"] = [
        dict(channel_id="kv15", schedule=[dict(time=0.0, availability=1.0)])
    ]
    raw["execution"]["channel_capacity"] = 1
    spec = parse_spec(raw)
    host = get_model(spec.model)
    state, layout = host.initial_values(spec)
    control = host.Control(*(r[0] for r in control_values(spec, [0.0])))
    return host, state, control, layout


def run():
    if jax.default_backend() != "cpu" or not jax.config.x64_enabled:
        raise RuntimeError("Use the CPU backend with JAX_ENABLE_X64=1")
    data = json.loads((Path(__file__).parent / "data/trapani2003_kv15_ph.json").read_text())
    data = data["trapani2003_kv15_ph"]
    protocol, panel_f = data["protocol"], data["panel_F"]
    law = laws.active().lookup("kv1p5_mh@1")
    host, state, control, layout = specimen(protocol)
    hold, test, tail = [protocol[k] * 1e-3 for k in ("hold_mV", "test_mV", "tail_mV")]
    lower, upper = law.voltage_domain_V
    native_mid = brentq(lambda v: law.kinetics(np.array([v]), xp=np)[0][0, 0] - 0.5, lower, upper)
    mid = panel_f["midpoint_mV"]
    delta = 1e-3 * (mid["acid"] - mid["control"])
    # In the registered law both pH labels select the same voltage-only kinetics.
    offsets = np.array([0.0, 0.0, delta, 1e-3 * mid["control"] - native_mid,
                        1e-3 * mid["acid"] - native_mid])
    for v in (hold, test):
        assert np.all((lower <= v - offsets) & (v - offsets <= upper))
    assert lower <= tail <= upper
    times = np.linspace(0, protocol["step_current_pulse_ms"] * 1e-3, 1501)

    def current(gates, v, maximum, xp):
        saved = state._replace(channel_gate=gates)
        scheduled = control._replace(channel=xp.asarray(control.channel) * maximum)
        return host.clamped_channel_flux(saved, scheduled, layout, v, xp=xp)[1][0]

    def pulse(offset, xp):
        # The comparison moves only the activation target. h and both clocks
        # are evaluated at the actual voltage, as is the ionic driving force.
        def kinetics(v):
            v = xp.asarray([v])
            targets, tau = law.kinetics(v, xp=xp)
            shifted_m = law.kinetics(v - offset, xp=xp)[0][0]
            return xp.stack((shifted_m, targets[1])), tau

        initial = kinetics(hold)[0]
        targets, tau = kinetics(test)
        gates = advance(initial, targets, tau, targets, tau, xp.asarray(times), xp=xp)
        peak = xp.argmax(law.opening(gates, xp=xp))
        peak_gates = gates[:, peak, None]
        return xp.stack((current(peak_gates, test, 1.0, xp),
                         current(gates[:, -1:], test, 1.0, xp), xp.asarray(times)[peak]))

    cpu = np.stack([pulse(offset, np) for offset in offsets])
    compiled = np.asarray(jax.jit(jax.vmap(lambda offset: pulse(offset, jnp)))(offsets))
    np.testing.assert_allclose(compiled, cpu, rtol=2e-12, atol=0)
    assert np.all(cpu[:, :2] > 0)
    np.testing.assert_array_equal(cpu[0], cpu[1])
    f = panel_f["normalized_at_test"]
    prediction = f["acid"] / f["control"]

    def transfer(xp):
        # These synthetic saved gates encode only the measured product m*h.
        normal = xp.asarray([[f["control"]], [1.0]])
        acid = xp.asarray([[f["acid"]], [1.0]])
        step = current(acid, test, 1.0, xp) / current(normal, test, 1.0, xp)
        repol = current(acid, tail, 1.0, xp) / current(normal, tail, 1.0, xp)
        half = current(acid, test, 0.5, xp) / current(normal, test, 1.0, xp)
        return xp.stack((step, repol, half))

    step, tail_ratio, half = transfer(np)
    for values in ((step, tail_ratio, half), jax.jit(lambda: transfer(jnp))()):
        np.testing.assert_allclose(values, [prediction, prediction, 0.5 * prediction], rtol=2e-14)

    # Panel B enters only after predictions from F and from the channel law are complete.
    panel_b = data["panel_B"]
    e = panel_f["reading_precision"]
    return {
        "model": "resolved_pump_tissue@3", "law": law.law_id,
        "panel_F_equal_maximum_prediction": prediction,
        "graph_reading_range": [(f["acid"] - e) / (f["control"] + e),
                                (f["acid"] + e) / (f["control"] - e)],
        "panel_B_observed": panel_b["ratio"], "panel_B_sem": panel_b["sem"],
        "prediction_minus_observed": prediction - panel_b["ratio"],
        "step_ratio_at_test": step, "tail_ratio_at_repolarization": tail_ratio,
        "ratio_with_half_acid_maximum": half,
        "native_activation_midpoint_mV": 1e3 * native_mid,
        "panel_F_midpoint_shift_mV": 1e3 * delta,
        "native_without_pH_input_peak_ratio": cpu[1, 0] / cpu[0, 0],
        "shift_only_native_peak_ratio": cpu[2, 0] / cpu[0, 0],
        "shift_only_native_75ms_ratio": cpu[2, 1] / cpu[0, 1],
        "both_midpoints_from_F_peak_ratio": cpu[4, 0] / cpu[3, 0],
        "both_midpoints_from_F_75ms_ratio": cpu[4, 1] / cpu[3, 1],
        "sampled_peak_time_ms": dict(zip(("native_control", "native_acid", "shift_only_acid",
                                         "panel_F_control", "panel_F_acid"),
                                        (cpu[:, 2] * 1e3).tolist(), strict=True)),
        "numpy_jax_max_current_difference_A": float(np.max(np.abs(cpu[:, :2] - compiled[:, :2]))),
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, allow_nan=False))
