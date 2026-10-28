"""Short independent salt/water stages; no production imports or trajectory jobs."""

import json
import os
import sys
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from validation.tissue import surface_cotransport_water_fixtures as fixtures
from validation.tissue import surface_cotransport_water_reference as ref
from validation.tissue import surface_energy_water_reference as base
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
