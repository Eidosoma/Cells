"""Short independent salt/water stages and adaptive histories; no production imports."""

import json
import os
import sys
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from validation.chemistry import finite_energy_reference as chemistry
from validation.tissue import surface_cotransport_water_fixtures as fixtures
from validation.tissue import surface_cotransport_water_reference as ref
from validation.tissue import surface_energy_water_reference as base
from validation.tissue import water_volume_reference as water
from validation.tissue.test_energy_water_reference import case as energy_water_case
from validation.transport import cotransport_reference as transport


def evidence(name, data):
    if location := os.environ.get("CELLS_REFERENCE_EVIDENCE"):
        path = Path(location)
        path.mkdir(parents=True, exist_ok=True)
        (path / (name + ".json")).write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def multi_owner_case():
    raw = energy_water_case(multiple=True)
    m, e = raw["model"], raw["experiment"]
    m["id"] = ref.MODEL_ID
    m["cotransporters"] = [
        dict(id=name, membrane_id=patch, law=law, roles=roles, capacity_fmol_per_s=capacity)
        for name, patch, law, roles, capacity in (
            (
                "kcc_a",
                "membrane_0",
                "kcc_reversible_tanh@1",
                {"potassium": "K", "chloride": "Cl"},
                20.0,
            ),
            (
                "nkcc_b",
                "membrane_2",
                "nkcc_reversible_tanh@1",
                {"sodium": "Na", "potassium": "K", "chloride": "Cl"},
                15.0,
            ),
            (
                "kcc_repeated",
                "membrane_3",
                "kcc_reversible_tanh@1",
                {"potassium": "K", "chloride": "Cl"},
                5.0,
            ),
        )
    ]
    e["cotransport_controls"] = [
        dict(
            cotransport_id=row["id"],
            schedule=[
                dict(time=0.0, availability=0.8),
                dict(time=9.7e-6, availability=0.0),
            ],
        )
        for row in m["cotransporters"]
    ]
    raw["execution"]["cotransport_capacity"] = len(m["cotransporters"])
    return raw


def owner_exchange(c, fields):
    result = np.zeros((len(c["raw"]["model"]["species"]), len(c["vi"]) + len(c["vo"])))
    for j, (i, o) in enumerate(zip(c["cotransport_inside"], c["cotransport_outside"], strict=True)):
        result[:, i] += fields["cotransport_transferred_fmol"][:, j]
        result[:, o] -= fields["cotransport_transferred_fmol"][:, j]
    return result


@pytest.mark.parametrize("arm", fixtures.ARMS)
@pytest.mark.parametrize("changed", [False, True])
def test_all_fixture_stages_have_current_volume_and_complete_owned_ledgers(arm, changed):
    raw = fixtures.definition(arm, backend="cpu", padded=False)
    c = ref.bind(raw)
    assert len(c["shapes"]) == 31 and len(c["water_energy"]["shapes"]) == 28
    assert tuple(c["shapes"])[-3:] == ref.EXTRA_FIELDS
    assert ref.CONTROL_KINDS[-2:] == ("water", "cotransport")
    d = ref.unpack(c, ref.initial(c))
    if changed:
        d["volume_increment_pL"][:] = 0.02
        d["extracellular_volume_increment_pL"][:] = -0.02
        d["energy_amount_increment_fmol"][:, 0] = [-1e-5, 1e-5, 1e-5]
        d["amount_increment"][0, 0], d["extracellular_amount_increment"][0, 0] = -1e-6, 1e-6
    slope, phi, proof = ref.evaluate(c, ref.flatten(c, d), 0)
    prior, expected_phi, previous = base.evaluate(
        c["water_energy"], ref.flatten(c["water_energy"], d), 0
    )
    actual, original = ref.unpack(c, slope), base.unpack(c["water_energy"], prior)
    np.testing.assert_array_equal(phi, expected_phi)
    exchange = owner_exchange(c, actual)
    n = len(c["vi"])
    for name in c["water_energy"]["shapes"]:
        expected = original[name]
        if name == "amount_increment":
            expected = expected + exchange[:, :n]
        elif name == "extracellular_amount_increment":
            expected = expected + exchange[:, n:]
        np.testing.assert_allclose(actual[name], expected, rtol=3e-15, atol=3e-12, err_msg=name)
    np.testing.assert_allclose(exchange.sum(axis=1), 0, rtol=0, atol=3e-12)
    assert np.all(np.asarray(proof["cotransport_route_charge_C_s"]) == 0)
    np.testing.assert_allclose(proof["cotransport_charge_rate_C_s"], 0, rtol=0, atol=2e-20)
    np.testing.assert_allclose(
        actual["cotransport_transferred_fmol"],
        c["cotransport_nu"] * actual["cotransport_cycles_fmol"],
        rtol=2e-15,
        atol=1e-12,
    )
    assert np.min(actual["cotransport_dissipated_energy_pJ"], initial=0) >= 0
    assert abs(proof["physical_energy_balance_pJ_s"]) < 3e-8
    assert (
        abs(proof["cotransport_chemical_power_pJ_s"] + proof["cotransport_dissipation_pJ_s"]) < 3e-8
    )
    np.testing.assert_array_equal(
        proof["pool_volume_power_pJ_s"], previous["pool_volume_power_pJ_s"]
    )
    np.testing.assert_array_equal(proof["osmotic_pressure_Pa"], previous["osmotic_pressure_Pa"])
    if arm in ("sealed", "absent") or (arm == "stall" and not changed):
        for name in ref.EXTRA_FIELDS:
            assert np.all(actual[name] == 0)
    if arm == "sealed_water":
        assert np.all(actual["water_transferred_pL"] == 0)
        assert np.any(actual["cotransport_cycles_fmol"] != 0)
    evidence(
        f"stage-{arm}-{changed}",
        dict(inputs=raw, changed_state=ref.flatten(c, d).tolist(), proof=proof),
    )


def test_current_volume_changes_cotransport_affinity_and_rates():
    c = ref.bind(fixtures.definition("coupled", backend="cpu"))
    d = ref.unpack(c, ref.initial(c))
    original = ref.unpack(c, ref.evaluate(c, ref.flatten(c, d), 0)[0])
    d["volume_increment_pL"][:] = 0.1
    d["extracellular_volume_increment_pL"][:] = -0.1
    slope, _, proof = ref.evaluate(c, ref.flatten(c, d), 0)
    actual = ref.unpack(c, slope)
    ci, co = c["ai"][:, 0] / 2.1, c["ao"][:, 0] / 3.9
    wanted = []
    for j, route in enumerate(c["raw"]["model"]["cotransporters"]):
        ratio = np.prod((co / ci) ** c["cotransport_nu"][:, j])
        level = c["cotransport_controls"][j][0]["availability"]
        wanted.append(route["capacity_fmol_per_s"] * level * (ratio - 1) / (ratio + 1))
    np.testing.assert_allclose(actual["cotransport_cycles_fmol"], wanted, rtol=2e-15, atol=1e-11)
    assert (
        np.min(np.abs(actual["cotransport_cycles_fmol"] - original["cotransport_cycles_fmol"])) > 1
    )
    np.testing.assert_array_equal(c["water_energy"]["vi"], [2.0])
    np.testing.assert_array_equal(c["water_energy"]["vo"], [4.0])
    assert abs(proof["physical_energy_balance_pJ_s"]) < 3e-8


def test_shared_routes_and_multiple_compartments_keep_material_and_energy_local():
    raw = multi_owner_case()
    c = ref.bind(raw)
    slope, phi, proof = ref.evaluate(c, ref.initial(c), 0)
    prior, base_phi, _ = base.evaluate(c["water_energy"], base.initial(c["water_energy"]), 0)
    actual, before = ref.unpack(c, slope), base.unpack(c["water_energy"], prior)
    moved = owner_exchange(c, actual)
    np.testing.assert_allclose(
        np.c_[
            actual["amount_increment"] - before["amount_increment"],
            actual["extracellular_amount_increment"] - before["extracellular_amount_increment"],
        ],
        moved,
        rtol=2e-15,
        atol=2e-15,
    )
    np.testing.assert_array_equal(phi, base_phi)
    for name in base.EXTRA_FIELDS:
        np.testing.assert_array_equal(actual[name], before[name])
    assert abs(proof["physical_energy_balance_pJ_s"]) < 2e-10
    evidence("shared-owners", dict(inputs=raw, proof=proof))


@pytest.mark.parametrize("kind", ref.CONTROL_KINDS)
def test_all_seven_controls_remain_independent_and_right_continuous(kind):
    c = ref.bind(multi_owner_case())
    event = c["raw"]["experiment"][kind + "_controls"][0]["schedule"][1]["time"]
    state = ref.initial(c)
    before = ref.unpack(c, ref.evaluate(c, state, np.nextafter(event, 0))[0])
    after = ref.unpack(c, ref.evaluate(c, state, event)[0])
    if kind == "cotransport":
        assert np.any(before["cotransport_cycles_fmol"])
        assert np.all(after["cotransport_cycles_fmol"] == 0)
        for name in c["water_energy"]["shapes"]:
            if name not in ("amount_increment", "extracellular_amount_increment"):
                np.testing.assert_array_equal(before[name], after[name])
    else:
        for name in ref.EXTRA_FIELDS:
            np.testing.assert_array_equal(before[name], after[name])
    if kind == "water":
        assert np.any(before["water_transferred_pL"])
        assert np.all(after["water_transferred_pL"] == 0)
        assert np.all(after["pool_volume_work_pJ"] == 0)


def test_cotransported_particles_change_next_state_osmotic_pressure_without_charge():
    c = ref.bind(fixtures.definition("coupled", backend="cpu"))
    slope, phi0, before = ref.evaluate(c, ref.initial(c), 0)
    ct = owner_exchange(c, ref.unpack(c, slope))
    d = ref.unpack(c, ref.initial(c))
    # A prescribed neutral displacement tests feedback; this is not an ODE run.
    dt = 1e-6
    d["amount_increment"] += dt * ct[:, :1]
    d["extracellular_amount_increment"] += dt * ct[:, 1:]
    _, phi1, after = ref.evaluate(c, ref.flatten(c, d), 0)
    expected = ref.R * 298.15 * dt * ct.sum(axis=0) / np.r_[c["vi"], c["vo"]]
    np.testing.assert_allclose(
        np.asarray(after["osmotic_pressure_Pa"]) - before["osmotic_pressure_Pa"],
        expected,
        rtol=2e-11,
        atol=3e-10,
    )
    np.testing.assert_allclose(phi1, phi0, rtol=0, atol=2e-12)
    assert np.max(np.abs(expected)) > 1
    np.testing.assert_array_equal(d["energy_amount_increment_fmol"], 0)
    evidence(
        "salt-osmotic-feedback",
        dict(pressure_change_Pa=expected.tolist(), before=before, after=after),
    )


def test_finite_difference_chemical_energy_matches_cotransport_heat():
    c = ref.bind(fixtures.definition("two_patches", backend="cpu"))
    slope, _, proof = ref.evaluate(c, ref.initial(c), 0)
    amount = np.c_[c["ai"], c["ao"]]
    moved = owner_exchange(c, ref.unpack(c, slope))
    h = Decimal("1e-9")
    initial = [[Decimal(str(v)) for v in row] for row in amount]
    plus = [
        [a + h * Decimal(str(d)) for a, d in zip(row, delta, strict=True)]
        for row, delta in zip(initial, moved, strict=True)
    ]
    minus = [
        [a - h * Decimal(str(d)) for a, d in zip(row, delta, strict=True)]
        for row, delta in zip(initial, moved, strict=True)
    ]
    volume = np.r_[c["vi"], c["vo"]].tolist()
    derivative = (
        transport.chemical_free_energy_change(initial, plus, volume, 298.15)
        - transport.chemical_free_energy_change(initial, minus, volume, 298.15)
    ) / (2 * float(h))
    np.testing.assert_allclose(
        derivative, -proof["cotransport_dissipation_pJ_s"], rtol=2e-11, atol=3e-6
    )
    evidence(
        "chemical-energy-gradient",
        dict(derivative_pJ_s=derivative, dissipation_pJ_s=proof["cotransport_dissipation_pJ_s"]),
    )


@pytest.mark.parametrize(
    "fault",
    ["law", "role", "valence", "membrane", "duplicate", "capacity", "control", "control_missing"],
)
def test_invalid_routes_and_controls_are_rejected(fault):
    raw = fixtures.definition("coupled", backend="cpu")
    row = raw["model"]["cotransporters"][0]
    if fault == "law":
        row["law"] = "unknown"
    elif fault == "role":
        row["roles"]["chloride"] = row["roles"]["potassium"]
    elif fault == "valence":
        next(v for v in raw["model"]["species"] if v["id"] == "Cl")["valence"] = -2
    elif fault == "membrane":
        row["membrane_id"] = "missing"
    elif fault == "duplicate":
        raw["model"]["cotransporters"].append(deepcopy(row))
    elif fault == "capacity":
        row["capacity_fmol_per_s"] = -1
    elif fault == "control":
        raw["experiment"]["cotransport_controls"][0]["schedule"][0]["availability"] = 1.1
    else:
        raw["experiment"]["cotransport_controls"].pop()
    with pytest.raises(ValueError):
        ref.bind(raw)


def test_closed_routes_do_not_allow_invalid_volume_or_exhausted_substrates():
    c = ref.bind(fixtures.definition("sealed", backend="cpu"))
    for name, value in (("volume_increment_pL", -1.0), ("amount_increment", -c["ai"][0, 0])):
        d = ref.unpack(c, ref.initial(c))
        d[name].flat[0] = value
        with pytest.raises(ValueError):
            ref.evaluate(c, ref.flatten(c, d), 0)


def test_independent_worker_does_not_import_production_or_jax():
    assert not any(name == "cells" or name.startswith("cells.") for name in sys.modules)
    assert not any(name == "jax" or name.startswith("jax.") for name in sys.modules)


def test_integrator_holds_all_seven_clocks_and_observes_dense_and_event_endpoints(monkeypatch):
    """An analytic prescribed RHS isolates scheduling from all physical rate laws."""
    raw = multi_owner_case()
    e = raw["experiment"]
    e["end_time"] = 1e-4
    fields = (
        "membrane_dissipated_energy_pJ",
        "junction_dissipated_energy_pJ",
        "channel_dissipated_energy_pJ",
        "pump_cycles",
        "regeneration_cycles_fmol",
        "water_transferred_pL",
        "cotransport_cycles_fmol",
    )
    for i, kind in enumerate(ref.CONTROL_KINDS):
        for group in e[kind + "_controls"]:
            group["schedule"] = [
                dict(time=0.0, availability=0.2),
                dict(time=(i + 1) * 1e-5, availability=0.8),
                dict(time=e["end_time"], availability=0.1),
            ]
    events = [0.0, *(i * 1e-5 for i in range(1, 8)), e["end_time"]]
    e["observation_times"] = sorted({*events, 3.5e-6, 25.1e-6, 98.1e-6})
    calls = []

    def prescribed(c, state, time):
        calls.append(time)
        slopes = {name: np.zeros(shape) for name, shape in c["shapes"].items()}
        for kind, field in zip(ref.CONTROL_KINDS, fields, strict=True):
            schedule = c["raw"]["experiment"][kind + "_controls"][0]["schedule"]
            level = next(row["availability"] for row in reversed(schedule) if row["time"] <= time)
            slopes[field].flat[0] = level
        return ref.flatten(c, slopes), np.full(len(c["vi"]) + len(c["vo"]), time), {}

    monkeypatch.setattr(ref, "evaluate", prescribed)
    result = ref.integrate(raw, max_step_s=1e-3)
    c = ref.bind(raw)
    states = ref.unpack(c, result["state"])
    start = ref.unpack(c, ref.initial(c))
    for i, field in enumerate(fields):
        times = np.asarray(result["times"])
        expected = 0.2 * np.minimum(times, events[i + 1]) + 0.8 * np.maximum(
            0, times - events[i + 1]
        )
        np.testing.assert_allclose(
            (states[field] - start[field]).reshape(len(times), -1)[:, 0],
            expected,
            rtol=0,
            atol=2e-18,
        )
    offset = 0
    for segment in result["segments"]:
        assert all(v == segment["left_s"] for v in calls[offset : offset + segment["evaluations"]])
        offset += segment["evaluations"]
    assert calls[offset:] == result["times"]
    np.testing.assert_array_equal(result["potential_V"][:, 0], result["times"])
    np.testing.assert_array_equal(result["final_state"], result["state"][-1])
    assert result["event_times"] == events
    assert result["evaluations"] == offset
    assert len(result["segments"]) == len(events) - 1
    assert result["max_step_s"] == 1e-3
    assert max(s["maximum_accepted_step_s"] for s in result["segments"]) > 1.25e-6
    evidence(
        "analytic-event-semantics",
        dict(events=events, segments=result["segments"], times=result["times"]),
    )


def test_short_channel_free_history_refines_with_material_volume_and_energy_balances():
    raw = fixtures.definition("coupled", backend="cpu")
    raw["model"]["channels"] = []
    raw["experiment"]["channel_controls"] = []
    raw["execution"]["channel_capacity"] = 0
    raw["experiment"].update(end_time=5e-4, observation_times=[0.0, 1.25e-4, 2.5e-4, 5e-4])
    # Keep the published rates and inventories; only the short observation
    # window and explicit integration cap differ from the response panel.
    c = ref.bind(raw)
    ordinary, tighter = (ref.integrate(raw, max_step_s=2.5e-4, refinement=r) for r in (1, 2))
    a, b = (ref.unpack(c, result["state"]) for result in (ordinary, tighter))
    for name in a:
        np.testing.assert_allclose(
            a[name], b[name], rtol=3e-9, atol=3e-28 if name.endswith("_C") else 3e-12, err_msg=name
        )
    for result, divisor in ((ordinary, 1), (tighter, 2)):
        assert result["rtol"] == 2e-11 / divisor
        assert result["amount_volume_energy_atol"] == 2e-14 / divisor
        assert result["electrode_charge_atol_C"] == 1e-29 / divisor
        assert result["max_step_s"] == 2.5e-4 / divisor
        assert np.all(result["evaluation_state_minimum"] <= result["initial_state"])
        assert np.all(result["evaluation_state_maximum"] >= result["initial_state"])
        np.testing.assert_array_equal(result["final_state"], result["state"][-1])
    assert max(s["maximum_accepted_step_s"] for s in ordinary["segments"]) > 1.25e-6
    np.testing.assert_allclose(
        a["amount_increment"].sum(axis=-1) + a["extracellular_amount_increment"].sum(axis=-1),
        0,
        rtol=0,
        atol=3e-14,
    )
    np.testing.assert_allclose(
        a["volume_increment_pL"].sum(axis=-1) + a["extracellular_volume_increment_pL"].sum(axis=-1),
        0,
        rtol=0,
        atol=3e-14,
    )
    np.testing.assert_allclose(
        a["cotransport_transferred_fmol"],
        c["cotransport_nu"] * a["cotransport_cycles_fmol"][:, None, :],
        rtol=3e-15,
        atol=1e-14,
    )
    pool = c["energy_initial"][None] + a["energy_amount_increment_fmol"]
    np.testing.assert_allclose(
        pool[:, 0] + pool[:, 1], c["energy_initial"][:2].sum(), rtol=0, atol=2e-18
    )
    phosphorus = 3 * pool[:, 0] + 2 * pool[:, 1] + pool[:, 2]
    np.testing.assert_allclose(
        phosphorus, (c["energy_initial"] * [[3], [2], [1]]).sum(), rtol=0, atol=4e-18
    )
    assert np.all(pool.sum(axis=1) < c["pool_maximum_osmolyte_amount_fmol"])
    assert abs(a["amount_increment"][-1, 2, 0]) > 1
    assert abs(a["volume_increment_pL"][-1, 0]) > 1e-4
    baseline = water.evaluate(c["water_case"])["free_energy_pJ"]
    capacitance = raw["model"]["membranes"][0]["capacitance_F"]
    phi = ordinary["potential_V"]
    capacitor = 0.5e12 * capacitance * (phi[:, 0] - phi[:, 1]) ** 2
    energies, pool_changes, stage_errors = [], [], []
    for i, time in enumerate(ordinary["times"]):
        volumes = np.r_[
            c["vi"] + a["volume_increment_pL"][i],
            c["vo"] + a["extracellular_volume_increment_pL"][i],
        ]
        amounts = np.c_[
            c["ai"] + a["amount_increment"][i], c["ao"] + a["extracellular_amount_increment"][i]
        ]
        pool_change = chemistry.free_energy_change(
            c["energy_initial"][:, 0],
            pool[i, :, 0],
            c["vi"][0],
            volumes[0],
            298.15,
            c["energy_delta_g0"][0],
        )
        pool_changes.append(pool_change)
        energies.append(
            water.evaluate(c["water_case"], volumes, amounts)["free_energy_pJ"]
            - baseline
            + pool_change
            + capacitor[i]
            - capacitor[0]
        )
        stage_errors.append(
            ref.evaluate(c, ordinary["state"][i], time)[2]["physical_energy_balance_pJ_s"]
        )
    heat = sum(
        value.sum(axis=tuple(range(1, value.ndim)))
        for name, value in a.items()
        if name.endswith("dissipated_energy_pJ")
    )
    full_residual = np.asarray(energies) + heat - a["regeneration_supplied_work_pJ"].sum(axis=-1)
    pool_residual = (
        np.asarray(pool_changes)
        + a["metabolic_work_pJ"].sum(axis=-1)
        + a["regeneration_dissipated_energy_pJ"].sum(axis=-1)
        - a["regeneration_supplied_work_pJ"].sum(axis=-1)
        - a["pool_volume_work_pJ"].sum(axis=-1)
    )
    np.testing.assert_allclose(full_residual, 0, rtol=0, atol=3e-9)
    np.testing.assert_allclose(pool_residual, 0, rtol=0, atol=3e-12)
    assert max(map(abs, stage_errors)) < 3e-8
    evidence(
        "short-adaptive-history",
        dict(
            inputs=raw,
            times=ordinary["times"],
            state=ordinary["state"].tolist(),
            refined_state=tighter["state"].tolist(),
            potential_V=phi.tolist(),
            evaluations=[ordinary["evaluations"], tighter["evaluations"]],
            segments=[ordinary["segments"], tighter["segments"]],
            full_energy_residual_pJ=full_residual.tolist(),
            pool_internal_transfer_residual_pJ=pool_residual.tolist(),
            stage_energy_residual_pJ_s=stage_errors,
            production_imports=False,
        ),
    )


@pytest.mark.parametrize(
    "options",
    [
        {"max_step_s": 0},
        {"max_step_s": float("inf")},
        {"max_step_s": float("nan")},
        {"max_step_s": True},
        {"max_step_s": -1},
        {"max_step_s": 1e-3, "refinement": 0},
        {"max_step_s": 1e-3, "refinement": True},
        {"max_step_s": 1e-3, "method": "Radau"},
    ],
)
def test_integrator_rejects_unsupported_step_tolerances_or_method(options):
    with pytest.raises(ValueError):
        ref.integrate(fixtures.definition("coupled", backend="cpu"), **options)


def test_failed_rhs_keeps_the_attempted_full_state_without_retry(monkeypatch):
    raw = fixtures.definition("coupled", backend="cpu")
    calls = []

    def rejected(c, state, time):
        calls.append((state.copy(), time))
        raise ValueError("deliberate failed-stage evidence probe")

    monkeypatch.setattr(ref, "evaluate", rejected)
    with pytest.raises(ref.ReferenceIntegrationError) as caught:
        ref.integrate(raw, max_step_s=1e-3)
    details = caught.value.diagnostics
    assert len(calls) == 1
    assert details["phase"] == "rhs" and details["automatic_retry"] is False
    assert details["evaluations"] == 1 and details["held_control_time_s"] == 0
    np.testing.assert_array_equal(details["state"], calls[0][0])
    json.dumps(details, allow_nan=False)
    evidence(
        "deliberately-failed-stage", dict(expected_failure=str(caught.value), diagnostics=details)
    )
