"""Independent checks for finite-pool osmotic and internal-work composition."""

import json
import os
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from validation.chemistry import finite_energy_reference as chemistry
from validation.tissue import surface_energy_reference as energy
from validation.tissue import surface_energy_water_fixtures as fixtures
from validation.tissue import surface_energy_water_reference as ref
from validation.tissue import water_volume_reference as water
from validation.tissue.test_water_kinetic_reference import case as active_water_case


def evidence(name, value):
    if location := os.environ.get("CELLS_REFERENCE_EVIDENCE"):
        path = Path(location)
        path.mkdir(parents=True, exist_ok=True)
        (path / (name + ".json")).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def case(*, multiple=False):
    """Reference-local raw cases; no production fixture or schema projection."""
    raw = active_water_case(multiple=multiple)
    m, e = raw["model"], raw["experiment"]
    m.update(id=ref.MODEL_ID, energy_osmotic_coupling=ref.COUPLING)
    m["energy_pools"] = [
        dict(
            id=f"energy_{i}",
            cell_id=cell["id"],
            law="finite_atp_adp_pi_transformed@1",
            initial_amount_fmol=dict(ATP=3.0, ADP=0.2, Pi=0.2),
            delta_g0_J_per_mol=-37000.0,
        )
        for i, cell in enumerate(m["cells"])
    ]
    m["regeneration_ports"] = [
        dict(
            id=f"regeneration_{i}",
            pool_id=pool["id"],
            law="driven_atp_regeneration_tanh@1",
            capacity_fmol_per_s=0.5,
            supplied_energy_J_per_mol=80000.0,
        )
        for i, pool in enumerate(m["energy_pools"])
    ]
    if multiple:
        # Two pump patches consume cell_0's same pool, alongside cell_1's pool.
        m["membranes"][3]["pump"] = deepcopy(m["membranes"][0]["pump"])
        m["membranes"][3]["pump"]["id"] = "pump_3"
        e["pump_controls"].append(
            dict(pump_id="pump_3", schedule=[dict(time=0.0, availability=0.6)])
        )
    for patch in m["membranes"]:
        if (pump := patch["pump"]) is not None:
            pool = next(v for v in m["energy_pools"] if v["cell_id"] == patch["inside"])
            pump["metabolism"] = dict(kind="finite_energy_pool@1", pool_id=pool["id"])
            pump["capacity_fmol_per_s"] = 20.0
    e["regeneration_controls"] = [
        dict(
            regeneration_id=port["id"],
            schedule=[
                dict(time=0.0, availability=0.5),
                dict(time=19.7e-6, availability=0.0),
                dict(time=43.1e-6, availability=0.8),
            ],
        )
        for port in m["regeneration_ports"]
    ]
    e["observation_times"] = sorted(set(e["observation_times"] + [12.5e-6, 19.7e-6, 43.1e-6]))
    raw["execution"]["regeneration_capacity"] = len(m["regeneration_ports"])
    return raw


def test_current_volumes_reach_nested_ions_pools_pumps_and_supply():
    raw = case()
    c = ref.bind(raw)
    assert [len(v["shapes"]) for v in (c, c["energy"], c["energy"]["ionic"])] == [28, 23, 19]
    d = ref.unpack(c, ref.initial(c))
    d["volume_increment_pL"][:] = 0.1
    d["extracellular_volume_increment_pL"][:] = -0.1
    d["energy_amount_increment_fmol"][:, 0] = [-0.1, 0.1, 0.1]
    slope, phi, proof = ref.evaluate(c, ref.flatten(c, d), 0)
    current = dict(
        c["energy"],
        vi=c["vi"] + 0.1,
        vo=c["vo"] - 0.1,
        energy_volumes=c["vi"] + 0.1,
        ionic=dict(c["energy"]["ionic"], vi=c["vi"] + 0.1, vo=c["vo"] - 0.1),
    )
    expected, expected_phi, _ = energy.evaluate(current, ref.flatten(c["energy"], d), 0)
    actual = ref.unpack(c, slope)
    np.testing.assert_array_equal(ref.flatten(c["energy"], actual), expected)
    np.testing.assert_array_equal(phi, expected_phi)
    for context in (c, c["energy"], c["energy"]["ionic"]):
        np.testing.assert_array_equal(context["vi"], [2.0])
        np.testing.assert_array_equal(context["vo"], [4.0])
    np.testing.assert_array_equal(c["energy"]["energy_volumes"], [2.0])
    old = energy.unpack(
        c["energy"], energy.evaluate(c["energy"], ref.flatten(c["energy"], d), 0)[0]
    )
    for name in (
        "membrane_transferred",
        "channel_transferred",
        "pump_cycles",
        "regeneration_cycles_fmol",
    ):
        assert np.max(np.abs(actual[name] - old[name])) > 1e-8
    assert abs(proof["physical_energy_balance_pJ_s"]) < 2e-10
    assert max(map(abs, proof["pool_internal_transfer_balance_pJ_s"])) < 2e-12
    evidence("current-volume-stage", dict(inputs=raw, proof=proof))


def test_live_pool_osmolytes_change_pressure_without_ionic_charge():
    c = ref.bind(case())
    state = ref.initial(c)
    baseline, phi0, proof0 = ref.evaluate(c, state, 0)
    d = ref.unpack(c, state.copy())
    d["energy_amount_increment_fmol"][:, 0] = [-0.1, 0.1, 0.1]
    changed, phi1, proof1 = ref.evaluate(c, ref.flatten(c, d), 0)
    np.testing.assert_array_equal(phi1, phi0)
    np.testing.assert_allclose(
        np.asarray(proof1["osmotic_pressure_Pa"]) - proof0["osmotic_pressure_Pa"],
        [ref.R * 298.15 * 0.1 / 2, 0],
        rtol=2e-13,
        atol=2e-10,
    )
    a, b = ref.unpack(c, baseline), ref.unpack(c, changed)
    for name in ("membrane_transferred", "channel_transferred", "channel_gate"):
        np.testing.assert_array_equal(a[name], b[name])
    assert b["water_transferred_pL"][0] < a["water_transferred_pL"][0]
    assert np.any(a["pump_cycles"] != b["pump_cycles"])


def test_physical_proof_detects_omitted_pool_pressure(monkeypatch):
    original = water.evaluate

    def missing_pool(case, volume, amount):
        return original(case, volume, amount[:-3])

    monkeypatch.setattr(water, "evaluate", missing_pool)
    c = ref.bind(case())
    _, _, proof = ref.evaluate(c, ref.initial(c), 0)
    assert abs(proof["physical_energy_balance_pJ_s"]) > 0.01
    evidence("omitted-pool-negative-control", dict(expected_nonzero=True, proof=proof))


@pytest.mark.parametrize("kind", ref.CONTROL_KINDS)
def test_six_clocks_are_right_continuous_and_water_has_its_own_work(kind):
    c = ref.bind(case(multiple=kind == "junction"))
    event = c["raw"]["experiment"][kind + "_controls"][0]["schedule"][1]["time"]
    state = ref.initial(c)
    before = ref.unpack(c, ref.evaluate(c, state, np.nextafter(event, 0))[0])
    after = ref.unpack(c, ref.evaluate(c, state, event)[0])
    name = dict(
        membrane="membrane_transferred",
        junction="junction_transferred",
        channel="channel_transferred",
        pump="pump_cycles",
        regeneration="regeneration_cycles_fmol",
        water="water_transferred_pL",
    )[kind]
    assert np.any(before[name]) and np.all(after[name] == 0)
    if kind == "water":
        for name in c["energy"]["shapes"]:
            np.testing.assert_array_equal(before[name], after[name])
        assert np.all(after["pool_volume_work_pJ"] == 0)
    else:
        for name in ref.EXTRA_FIELDS:
            np.testing.assert_array_equal(before[name], after[name])
    if kind == "regeneration":
        for name in c["energy"]["ionic"]["shapes"]:
            np.testing.assert_array_equal(before[name], after[name])


def test_sealed_water_reduces_exactly_to_finite_energy_reference():
    raw = case()
    for row in raw["model"]["water_membranes"]:
        row["hydraulic_permeability_m_per_Pa_s"] = 0
    c = ref.bind(raw)
    slope, phi, _ = ref.evaluate(c, ref.initial(c), 0)
    expected, expected_phi, _ = energy.evaluate(c["energy"], energy.initial(c["energy"]), 0)
    actual = ref.unpack(c, slope)
    np.testing.assert_array_equal(ref.flatten(c["energy"], actual), expected)
    np.testing.assert_array_equal(phi, expected_phi)
    for name in ref.EXTRA_FIELDS:
        assert np.all(actual[name] == 0)


@pytest.mark.parametrize("contraction", [False, True])
def test_pool_volume_work_is_signed_and_counted_once_per_shared_owner(contraction):
    raw = case(multiple=True)
    if contraction:
        for owner in raw["model"]["water_compartments"][:2]:
            owner["pressure_offset_Pa"] = 2e6
    c = ref.bind(raw)
    slope, _, proof = ref.evaluate(c, ref.initial(c), 0)
    d = ref.unpack(c, slope)
    expected = (
        -1e-3
        * ref.R
        * 298.15
        * c["energy_initial"].sum(axis=0)
        / c["vi"]
        * d["volume_increment_pL"]
    )
    np.testing.assert_allclose(d["pool_volume_work_pJ"], expected, rtol=2e-15, atol=1e-13)
    assert (
        np.all(d["pool_volume_work_pJ"] > 0)
        if contraction
        else np.all(d["pool_volume_work_pJ"] < 0)
    )
    demand, supply = np.zeros(2), np.zeros(2)
    for j, patch in enumerate(raw["model"]["membranes"]):
        demand[c["cell_ids"].index(patch["inside"])] += d["pump_cycles"][j]
    for j, port in enumerate(raw["model"]["regeneration_ports"]):
        i = c["cell_ids"].index(c["pools"][port["pool_id"]]["cell_id"])
        supply[i] += d["regeneration_cycles_fmol"][j]
    np.testing.assert_allclose(
        d["energy_amount_increment_fmol"],
        np.array([-demand + supply, demand - supply, demand - supply]),
        rtol=2e-15,
        atol=1e-15,
    )
    assert abs(proof["physical_energy_balance_pJ_s"]) < 2e-8
    assert max(map(abs, proof["pool_internal_transfer_balance_pJ_s"])) < 2e-12
    evidence(f"shared-pools-{contraction}", dict(inputs=raw, proof=proof))


def test_invariant_particle_bound_allows_hydrolysis_increase():
    c = ref.bind(case())
    a = c["energy_initial"][:, 0]
    adenylate, phosphorus = a[0] + a[1], 3 * a[0] + 2 * a[1] + a[2]
    upper = c["pool_maximum_osmolyte_amount_fmol"][0]
    np.testing.assert_allclose(upper, phosphorus - adenylate, rtol=0, atol=2e-15)
    for atp in (0.01, 0.5, 1.0, 2.99):
        final = np.array([atp, adenylate - atp, phosphorus - 2 * adenylate - atp])
        assert np.all(final > 0) and a.sum() < final.sum() < upper


@pytest.mark.parametrize(
    "fault", ["coupling", "temperature", "reservoir", "pool_exhaustion", "volume_bound"]
)
def test_unsupported_scope_and_invalid_trials_are_rejected(fault):
    raw = case()
    if fault == "coupling":
        raw["model"].pop("energy_osmotic_coupling")
    elif fault == "temperature":
        raw["model"]["temperature_K"] = 310
    elif fault == "reservoir":
        raw["model"]["extracellular"][0]["reservoir"] = True
    if fault in ("coupling", "temperature", "reservoir"):
        with pytest.raises(ValueError):
            ref.bind(raw)
        return
    c = ref.bind(raw)
    d = ref.unpack(c, ref.initial(c))
    if fault == "pool_exhaustion":
        d["energy_amount_increment_fmol"][0, 0] = -c["energy_initial"][0, 0]
    else:
        d["volume_increment_pL"][0] = c["minimum_volume_pL"][0] - c["vi"][0]
    with pytest.raises(ValueError):
        ref.evaluate(c, ref.flatten(c, d), 0)


def test_adaptive_history_preserves_material_and_both_energy_identities():
    raw = case()
    c = ref.bind(raw)
    ordinary, tighter = (ref.integrate(raw, refinement=r) for r in (1, 4))
    a, b = (ref.unpack(c, row["state"]) for row in (ordinary, tighter))
    assert tighter["evaluations"] > ordinary["evaluations"]
    for name in a:
        np.testing.assert_allclose(
            a[name], b[name], rtol=3e-9, atol=3e-28 if name.endswith("_C") else 3e-13, err_msg=name
        )
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
    amounts = c["energy_initial"][None] + a["energy_amount_increment_fmol"]
    np.testing.assert_allclose(
        amounts[:, 0] + amounts[:, 1],
        np.broadcast_to((c["energy_initial"][0] + c["energy_initial"][1]), amounts[:, 0].shape),
        rtol=0,
        atol=2e-15,
    )
    np.testing.assert_allclose(
        3 * amounts[:, 0] + 2 * amounts[:, 1] + amounts[:, 2],
        np.broadcast_to(
            (3 * c["energy_initial"][0] + 2 * c["energy_initial"][1] + c["energy_initial"][2]),
            amounts[:, 0].shape,
        ),
        rtol=0,
        atol=4e-15,
    )
    assert np.all(amounts.sum(axis=1) < c["pool_maximum_osmolyte_amount_fmol"])
    start, stop = (ordinary["times"].index(t) for t in (13.3e-6, 39.1e-6))
    for name in ref.EXTRA_FIELDS:
        np.testing.assert_array_equal(a[name][start], a[name][stop])
    assert abs(a["pool_volume_work_pJ"][-1, 0]) > 1e-5
    assert np.max(np.abs(a["energy_amount_increment_fmol"][-1])) > 1e-5
    baseline = water.evaluate(c["water_case"])["free_energy_pJ"]
    vm0 = ordinary["potential_V"][0, 0] - ordinary["potential_V"][0, 1]
    capacitance = raw["model"]["membranes"][0]["capacitance_F"]
    base_capacitor = 0.5e12 * capacitance * vm0**2
    full_energy, pool_changes, stage_errors = [], [], []
    for i, (time, phi) in enumerate(zip(ordinary["times"], ordinary["potential_V"], strict=True)):
        volumes = np.r_[
            c["vi"] + a["volume_increment_pL"][i],
            c["vo"] + a["extracellular_volume_increment_pL"][i],
        ]
        ions = np.c_[
            c["ai"] + a["amount_increment"][i], c["ao"] + a["extracellular_amount_increment"][i]
        ]
        pool_change = chemistry.free_energy_change(
            c["energy_initial"][:, 0],
            amounts[i, :, 0],
            c["vi"][0],
            volumes[0],
            298.15,
            c["energy_delta_g0"][0],
        )
        pool_changes.append(pool_change)
        full_energy.append(
            water.evaluate(c["water_case"], volumes, ions)["free_energy_pJ"]
            - baseline
            + 0.5e12 * capacitance * (phi[0] - phi[1]) ** 2
            - base_capacitor
            + pool_change
        )
        stage_errors.append(
            ref.evaluate(c, ordinary["state"][i], time)[2]["physical_energy_balance_pJ_s"]
        )
    heat = sum(
        value.sum(axis=tuple(range(1, value.ndim)))
        for name, value in a.items()
        if name.endswith("dissipated_energy_pJ")
    )
    full_residual = np.array(full_energy) + heat - a["regeneration_supplied_work_pJ"].sum(axis=-1)
    pool_residual = (
        np.array(pool_changes)
        + a["metabolic_work_pJ"].sum(axis=-1)
        + a["regeneration_dissipated_energy_pJ"].sum(axis=-1)
        - a["regeneration_supplied_work_pJ"].sum(axis=-1)
        - a["pool_volume_work_pJ"].sum(axis=-1)
    )
    np.testing.assert_allclose(full_residual, 0, rtol=0, atol=3e-9)
    np.testing.assert_allclose(pool_residual, 0, rtol=0, atol=3e-12)
    assert max(map(abs, stage_errors)) < 2e-10
    # Endpoint dilution is an energy correction, not the path-dependent work.
    dilution = (
        -1e-3
        * ref.R
        * 298.15
        * amounts[-1, :, 0].sum()
        * np.log1p(a["volume_increment_pL"][-1, 0] / c["vi"][0])
    )
    assert abs(dilution - a["pool_volume_work_pJ"][-1, 0]) > 1e-9
    assert not any(name == "cells" or name.startswith("cells.") for name in sys.modules)
    assert not any(name == "jax" or name.startswith("jax.") for name in sys.modules)
    evidence(
        "adaptive-history",
        dict(
            inputs=raw,
            times=ordinary["times"],
            state=ordinary["state"].tolist(),
            potential_V=ordinary["potential_V"].tolist(),
            refined_state=tighter["state"].tolist(),
            evaluations=[ordinary["evaluations"], tighter["evaluations"]],
            full_energy_residual_pJ=full_residual.tolist(),
            pool_internal_transfer_residual_pJ=pool_residual.tolist(),
            stage_energy_residual_pJ_s=stage_errors,
            endpoint_dilution_pJ=float(dilution),
            production_imports=False,
        ),
    )


@pytest.mark.parametrize("arm", fixtures.ARMS)
def test_coordinator_fixture_stage_contracts(arm):
    raw = fixtures.definition(arm, backend="cpu", padded=False)
    c = ref.bind(raw)
    times = sorted(
        {
            0.0,
            *(
                row["time"]
                for kind in ref.CONTROL_KINDS
                for group in raw["experiment"][kind + "_controls"]
                for row in group["schedule"]
            ),
        }
    )
    proofs = []
    for t in times:
        slope, _, proof = ref.evaluate(c, ref.initial(c), t)
        d = ref.unpack(c, slope)
        assert abs(proof["physical_energy_balance_pJ_s"]) < 2e-10
        assert max(map(abs, proof["pool_internal_transfer_balance_pJ_s"])) < 2e-12
        if arm == "sealed":
            for name in ref.EXTRA_FIELDS:
                assert np.all(d[name] == 0)
        if arm == "reverse":
            assert np.all(d["pump_cycles"] < 0)
        proofs.append(proof)
    evidence(f"fixture-{arm}", dict(inputs=raw, times=times, proofs=proofs))


def test_coordinator_release_fixture_has_complete_finite_energy_water_history():
    raw = fixtures.definition("release", backend="cpu", padded=False)
    c, history = ref.bind(raw), ref.integrate(raw)
    d = ref.unpack(c, history["state"])
    assert history["state"].shape[0] == len(raw["experiment"]["observation_times"])
    assert fixtures.CHECKPOINT_TIME in history["times"]
    assert len(c["shapes"]) == 28
    before, after = (history["times"].index(t) for t in fixtures.WATER_RELEASE_TIMES)
    for name in ref.EXTRA_FIELDS:
        np.testing.assert_array_equal(d[name][before], d[name][after])
    assert np.max(np.abs(d["energy_amount_increment_fmol"][-1])) > 1e-7
    assert np.max(np.abs(d["pool_volume_work_pJ"][-1])) > 1e-8
    evidence(
        "fixture-release-history",
        dict(
            inputs=raw,
            times=history["times"],
            state=history["state"].tolist(),
            potential_V=history["potential_V"].tolist(),
            evaluations=history["evaluations"],
            state_fields=list(c["shapes"]),
            event_times=history["event_times"],
        ),
    )
