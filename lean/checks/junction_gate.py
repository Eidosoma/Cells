"""Check voltage-clamped gate kinetics and tracer transfer after a timed junction block."""

import json
import math
from pathlib import Path

import jax
import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.laws.junctions import junction_voltage_relaxation as gate
from validation.betse.junction_gate import reference
from validation.tissue import surface_pump_v3_fixtures as fixture

PROTOCOL = json.loads(Path(reference.__file__).with_name("protocol.json").read_text())
THRESHOLD = PROTOCOL["threshold_voltage_V"]
FLOOR = PROTOCOL["minimum_open_fraction"]
GATE_ATOL = PROTOCOL["tolerances"]["physical_gate_atol"]
INITIAL = 0.9
RELEASE = 1 / 32  # 31.25 ms, exactly on the RK4 grid
VOLTAGES = np.array([-0.080, 0.0, 0.080])
TIMES = np.array([0.0, RELEASE / 2, RELEASE, 1.5 * RELEASE, 2 * RELEASE])
AREA, PERMEABILITY = 1e-10, 1e-6  # m², m/s
TRACER_IN, TRACER_OUT = 3.0, 1.0  # sender and receiver, mM


def clamped():
    voltages = np.sort([*PROTOCOL["voltages_V"], -0.1, 0.1])
    params = gate.Parameters(THRESHOLD, FLOOR)
    rates = jax.jit(gate.kinetics)(voltages, params)
    alpha, beta = reference.rates(voltages, THRESHOLD)
    np.testing.assert_allclose(rates.relaxation_per_s, alpha + beta, rtol=4e-15)
    target = np.asarray(rates.target)
    np.testing.assert_array_equal(target, target[::-1])
    assert np.all(np.diff(target[voltages >= 0]) < 0)
    actual = np.asarray(jax.jit(gate.advance_clamped)(INITIAL, voltages, params, TIMES[:, None]))
    expected = reference.solution(INITIAL, voltages, THRESHOLD, FLOOR, TIMES)
    np.testing.assert_allclose(actual, expected, rtol=0, atol=GATE_ATOL)
    np.testing.assert_array_equal(actual, actual[:, ::-1])
    assert ((FLOOR <= actual) & (actual <= 1)).all()
    d0, d1, d2 = actual[:3] - target
    residual = d0 * d2 - d1**2
    np.testing.assert_allclose(residual, 0, rtol=0, atol=4 * np.finfo(float).eps)
    return dict(
        voltages_V=voltages.tolist(),
        samples=actual.size,
        max_gate_error=float(np.max(abs(actual - expected))),
        max_three_sample_residual=float(np.max(abs(residual))),
        tau_at_minus_100_mV_ms=float(1000 / rates.relaxation_per_s[voltages == -0.1].item()),
        polarity=polarity_comparison(voltages, target),
    )


def polarity_comparison(voltages_V, targets):
    data = json.loads((Path(__file__).with_name("data") / "revilla1999_cx43.json").read_text())
    voltage_mV = data["comparison_abs_voltage_mV"]
    fitted = {}
    for polarity in ("negative", "positive"):
        branch = data[polarity]
        exponent = branch["slope_per_mV"] * (voltage_mV - branch["abs_midpoint_mV"])
        span = branch["maximum"] - branch["minimum"]
        fitted[polarity] = branch["minimum"] + span / (1 + math.exp(exponent))
    negative = targets[voltages_V == -voltage_mV / 1000].item()
    positive = targets[voltages_V == voltage_mV / 1000].item()
    assert negative == positive
    assert fitted["negative"] > fitted["positive"]  # Ordering in the wild-type panel, Fig. 3C.
    return dict(
        abs_voltage_mV=voltage_mV,
        fitted_normalized_conductance=fitted,
        min_max_error_against_fits=(fitted["negative"] - fitted["positive"]) / 2,
        engine_intrinsic_targets=dict(negative=negative, positive=positive),
    )


def definition():
    cells = [(vm, 12.0, 140.0, 12.0) for v in VOLTAGES for vm in (v / 2, -v / 2)]
    raw = fixture.heredity_cells(
        cells, dt=2**-14, end_time=TIMES[-1], observation_times=TIMES, solver="rk4"
    )
    model, experiment, execution = raw["model"], raw["experiment"], raw["execution"]
    model["channels"] = []
    experiment["channel_controls"] = []
    experiment["pump_controls"] = []
    execution["channel_capacity"] = 0
    execution["edge_capacity"] = len(VOLTAGES)
    model["species"].append(dict(id="X", valence=0))
    execution["material_balance_atol_fmol"]["X"] = 1e-10
    for i, cell in enumerate(model["cells"]):
        cell["initial_amount_fmol"]["X"] = (TRACER_IN, TRACER_OUT)[i % 2] * cell["volume_pL"]
    for bath in model["extracellular"]:
        bath["initial_amount_fmol"]["X"] = TRACER_OUT * bath["volume_pL"]
    impermeable = {s["id"]: 0.0 for s in model["species"]}
    for patch in model["membranes"]:
        patch.update(pump=None, permeability_m_per_s=impermeable)
    for i in range(len(VOLTAGES)):
        edge = f"junction_{i}"
        model["junctions"].append(
            dict(
                id=edge,
                sender=f"cell_{2 * i}",
                receiver=f"cell_{2 * i + 1}",
                area_m2=AREA,
                permeability_m_per_s=impermeable | {"X": PERMEABILITY},
                law="cells.route.constant_field@1",
                gate=dict(
                    law=gate.LAW_ID,
                    threshold_voltage_V=THRESHOLD,
                    minimum_open_fraction=FLOOR,
                    initial_gate=INITIAL,
                ),
            )
        )
        experiment["junction_controls"].append(
            dict(
                junction_id=edge,
                schedule=[dict(time=0.0, availability=0.0), dict(time=RELEASE, availability=1.0)],
            )
        )
    return raw


def tissue():
    # X is neutral and is the only mobile substance, so transfer preserves each clamp voltage.
    raw = definition()
    result = run(parse_spec(raw))
    obs = result.observations
    tracer = result.spec.model.species_ids.index("X")
    volume = fixture.HEREDITY_VOLUME_PL
    scale = AREA * PERMEABILITY * 1e15
    np.testing.assert_allclose(
        obs.junction_voltage_V,
        np.broadcast_to(VOLTAGES, obs.junction_voltage_V.shape),
        rtol=0,
        atol=1e-14,
    )
    expected_gate = reference.solution(INITIAL, VOLTAGES, THRESHOLD, FLOOR, TIMES)
    np.testing.assert_allclose(obs.junction_gate, expected_gate, rtol=0, atol=GATE_ATOL)
    alpha, beta = reference.rates(VOLTAGES, THRESHOLD)
    speed = alpha + beta
    target = (alpha + beta * FLOOR) / speed
    # Integrate conductance only during the open interval. The equal-volume
    # concentration difference obeys dΔ/dt = −(2·scale/volume)·g(t)·Δ.
    elapsed = np.maximum(TIMES[:, None] - RELEASE, 0.0)
    at_release = reference.solution(INITIAL, VOLTAGES, THRESHOLD, FLOOR, RELEASE)
    integrated = target * elapsed + (at_release - target) * (-np.expm1(-speed * elapsed)) / speed
    gradient = TRACER_IN - TRACER_OUT
    power = -2 * scale * integrated / volume
    moved = -(volume / 2) * gradient * np.expm1(power)
    flux = scale * expected_gate * gradient * np.exp(power) * (TIMES[:, None] >= RELEASE)
    observed_flux = obs.junction_flux_fmol_s[:, tracer]
    np.testing.assert_array_equal(observed_flux[TIMES < RELEASE], 0)
    np.testing.assert_allclose(observed_flux, flux, rtol=0, atol=3e-12)
    material_atol = raw["execution"]["material_balance_atol_fmol"]["X"]
    for actual in (
        obs.junction_transferred[:, tracer],
        -obs.amount_increment[:, tracer, ::2],
        obs.amount_increment[:, tracer, 1::2],
    ):
        np.testing.assert_allclose(actual, moved, rtol=0, atol=material_atol)
    release_index = list(TIMES).index(RELEASE)
    return dict(
        model=raw["model"]["id"],
        voltages_V=VOLTAGES.tolist(),
        release_s=RELEASE,
        gate_at_release=obs.junction_gate[release_index].tolist(),
        release_flux_fmol_s=observed_flux[release_index].tolist(),
        final_transfer_fmol=obs.junction_transferred[-1, tracer].tolist(),
        max_gate_error=float(np.max(abs(obs.junction_gate - expected_gate))),
        max_transfer_error_fmol=float(np.max(abs(obs.junction_transferred[:, tracer] - moved))),
    )


if __name__ == "__main__":
    print(json.dumps(dict(clamp=clamped(), tissue=tissue()), indent=2, allow_nan=False))
