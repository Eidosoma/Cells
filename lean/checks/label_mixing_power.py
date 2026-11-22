"""FR-33 neutral label mixing. Instantaneous face power and accepted-step heat in Cells."""

import json
import math

import jax
import numpy as np

from cells.definitions.specs import parse_spec
from cells.laws.electrochemistry import R
from cells.numerics import surface_transport
from cells.registry.models import get_model
from validation.regions import example, readouts
from validation.tissue import secreted_species_fixtures, surface_fixtures

CASES = {
    "opposing": ((0.9, 0.1), (0.1, 0.9)),
    "same_fractions": ((1.2, 0.6), (0.8, 0.4)),
    "unequal_fractions_and_totals": ((0.9, 0.2), (0.4, 0.6)),
}


def point(compiled, pairs):
    raw = surface_fixtures.definition("equilibrium")
    raw["membrane_open"] = [0.0] * len(raw["membrane_open"])
    raw["junction_open"] = [0.0] * len(raw["junction_open"])
    factor = raw["layout"]["face_factor"][0][0]
    for i, (a, b) in enumerate(pairs):
        raw["layout"]["valence"][i] = [0.0]
        raw["layout"]["face_factor"][i] = [factor, 0.0]
        raw["co"][i] = [a, b, b]
    ci, co, _, voltage, membrane, junction, layout = surface_fixtures.arrays(raw)
    out = compiled(ci, co, np.zeros(ci.shape[1]), voltage, membrane, junction, layout)
    assert bool(out.valid) and out.face_dissipation_pJ_s.dtype == np.float64
    power = float(out.face_dissipation_pJ_s[0])
    scale = (factor / 1e-15) * 1e-3 * R * raw["layout"]["temperature"]
    expected = scale * math.fsum((a - b) * math.log(a / b) for a, b in pairs)
    np.testing.assert_allclose(power, expected, rtol=8e-15, atol=0)
    return power, float(np.asarray(out.face_flux_fmol_s)[:, 0].sum()), scale


def trajectory(pairs, split, dt, steps):
    raw = example.two_node_diffusion(dt=dt, steps=steps)
    a, b = map(sum, zip(*pairs, strict=True))
    profiles = dict(zip(("L", "U"), pairs, strict=True)) if split else {"S": (a, b)}
    # Preserve the same declared shape. Unused tracers are constant at the fixture's trace.
    trace = secreted_species_fixtures.TRACE_mM
    for node in raw["model"]["extracellular"]:
        if node["id"] in ("left", "right"):
            side = ("left", "right").index(node["id"])
            for name in ("S", "L", "U"):
                node["initial_amount_fmol"][name] = profiles.get(name, (trace, trace))[side]
            assert node["volume_pL"] == 1
    spec = parse_spec(raw)
    times, states = readouts.runs(spec)
    np.testing.assert_allclose(times, np.arange(steps + 1) * dt, rtol=0, atol=2e-14)
    _, layout = get_model(spec.model).initial_values(spec)
    rows = [list(spec.model.species_ids).index(s) for s in profiles]
    nodes = [[n.id for n in spec.model.extracellular].index(n) for n in ("left", "right")]
    face = [f.id for f in spec.model.faces].index("face_lr")
    ref = np.asarray(layout.extracellular_amount_reference)
    amount = np.array(
        [(ref + np.asarray(s.extracellular_amount_increment))[np.ix_(rows, nodes)] for s in states]
    )
    transfer = np.array([np.asarray(s.face_transferred)[rows, face] for s in states])
    heat = np.array([float(s.face_dissipated_energy_pJ[face]) for s in states])
    # Each neutral face joins two closed 1 pL nodes. Independently reconstruct the predicted
    # concentrations, the logarithmic mean and the booking using the recorded transfers.
    dtimes = np.diff(times)[:, None]
    k = example.R_DIFFUSION
    theta = float(np.asarray(layout.imex_operator_time).ravel()[0])
    before_l, before_r = amount[:-1, :, 0], amount[:-1, :, 1]
    drift = theta * dtimes * k * (before_l - before_r)
    left, right = before_l - drift, before_r + drift
    assert (left > 0).all() and (right > 0).all()
    log_ratio = np.log1p((left - right) / right)
    weight = k * np.divide(left - right, log_ratio, out=(left + right) / 2, where=left != right)
    applied = np.diff(transfer, axis=0)
    np.testing.assert_allclose(applied, np.diff(amount[:, :, 1], axis=0), rtol=0, atol=6e-15)
    rt = 1e-3 * R * spec.model.temperature_K
    predicted_heat = rt * np.sum(applied**2 / (dtimes * weight), axis=1)
    residual = np.diff(heat) - predicted_heat
    np.testing.assert_allclose(np.diff(heat), predicted_heat, rtol=1e-12, atol=3e-15)
    assert (np.diff(heat) >= 0).all()
    # Continuous ideal two-node diffusion has an analytic endpoint and free-energy loss.
    start_l, start_r = amount[0, :, 0], amount[0, :, 1]
    mean = (start_l + start_r) / 2
    halfdiff = (start_l - start_r) * math.exp(-2 * k * times[-1]) / 2
    end = np.stack((mean + halfdiff, mean - halfdiff), axis=1)
    continuous = float(rt * np.sum(amount[0] * np.log(amount[0]) - end * np.log(end)))
    return (
        {
            "steps": steps,
            "dt_s": dt,
            "final_time_s": times[-1],
            "first_booked_pJ": heat[1],
            "final_booked_pJ": heat[-1],
            "continuous_free_energy_drop_pJ": continuous,
            "max_step_booking_error_pJ": float(np.max(np.abs(residual))),
        },
        heat,
        amount.sum(axis=1),
    )


def compare(name, pairs, compiled):
    parent = tuple(map(sum, zip(*pairs, strict=True)))
    split_power, split_flux, scale = point(compiled, pairs)
    parent_power, parent_flux, _ = point(compiled, [parent])
    np.testing.assert_allclose(split_flux, parent_flux, rtol=5e-15, atol=1e-19)
    a, b = parent
    gap = scale * math.fsum((x - y) * math.log((x / a) / (y / b)) for x, y in pairs)
    np.testing.assert_allclose(split_power - parent_power, gap, rtol=1e-14, atol=2e-18)
    result = {"pairs_mM": pairs, "parent_power_pJ_s": parent_power, "split_power_pJ_s": split_power}
    arms, histories, totals = {}, [], []
    for arm, split in (("parent", False), ("labels", True)):
        arms[arm], heat, total = trajectory(pairs, split, dt=0.01, steps=100)
        histories.append(heat)
        totals.append(total)
    np.testing.assert_allclose(totals[0], totals[1], rtol=0, atol=3e-14)
    if name == "same_fractions":
        np.testing.assert_allclose(histories[0], histories[1], rtol=2e-14, atol=2e-15)
    else:
        assert (histories[1][1:] > histories[0][1:]).all()
    if name == "opposing":
        np.testing.assert_array_equal(histories[0], 0)
        fine, _, _ = trajectory(pairs, True, dt=0.005, steps=200)
        continuum = arms["labels"]["continuous_free_energy_drop_pJ"]
        coarse_error = abs(arms["labels"]["final_booked_pJ"] - continuum)
        assert 0 < abs(fine["final_booked_pJ"] - continuum) < coarse_error
        arms["labels_half_step"] = fine
    return result | {"accepted_steps": arms}


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    face = jax.jit(surface_transport.transport)
    print(json.dumps({n: compare(n, pairs, face) for n, pairs in CASES.items()}, indent=2))
