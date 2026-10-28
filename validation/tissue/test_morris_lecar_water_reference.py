"""Independent 53-law ionic water, live dilution and distinct time scopes.

The oracle represents real owners only. Padding tests compare that active
projection; production padding rejection is checked by the production suite.
The separate water-only equilibrium history is not full tissue settling.
"""

import json
import os
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from validation.channels import calcium_activated_potassium_reference as sensor
from validation.tissue import surface_kinetic_reference as ionic
from validation.tissue import surface_water_kinetic_reference as ref
from validation.tissue import water_volume_reference as water
from validation.tissue.test_calcium_catalog_v2_reference import evidence, frozen_module
from validation.tissue.test_morris_lecar_catalog_reference import ml_routes, sensor_routes

pytestmark = pytest.mark.skipif(
    "CELLS_ML_WATER_INPUTS" not in os.environ,
    reason="Require independently frozen raw water fixture JSONs",
)


def inputs():
    directory = os.environ.get("CELLS_ML_WATER_INPUTS")
    if not directory:
        return {}
    result = {}
    for path in sorted(Path(directory).glob("*.json")):
        raw = json.loads(path.read_text())
        if isinstance(raw, dict) and raw.get("model", {}).get("id") == "resolved_water@3":
            result[path.stem] = raw
    return result


def case(arm="open"):
    return deepcopy(inputs()[arm])


def state(c, changed=False):
    d = ref.unpack(c, ref.initial(c))
    if changed:
        n = len(c["vi"])
        edge = c["water_case"]["edges"][0]
        i, o = edge["sender"], edge["receiver"]
        initial_v = np.r_[c["vi"], c["vo"]]
        amount = min(
            0.05 * min(initial_v[i], initial_v[o]),
            0.25 * (c["maximum_volume_pL"][i] - initial_v[i]),
            0.25 * (initial_v[o] - c["minimum_volume_pL"][o]),
        )
        assert i < n <= o and amount > 0
        d["volume_increment_pL"][i] += amount
        d["extracellular_volume_increment_pL"][o - n] -= amount
        d["water_transferred_pL"][0] = -amount
        for j, ch in enumerate(c["ionic"]["raw"]["model"]["channels"]):
            law = ch["kinetic_law"]
            if law == ionic.CALCIUM_ACTIVATED_LAW or (
                law in ionic.MORRIS_LECAR_LAWS and law not in ionic.ML_DYNAMIC_LAWS
            ):
                d["channel_gate"][:, j] = 0
            elif law in ionic.ML_DYNAMIC_LAWS:
                d["channel_gate"][:, j] = [0.31, 0.0]
            else:
                d["channel_gate"][:, j] = [0.31, 0.63]
        ids = [row["id"] for row in c["raw"]["model"]["species"]]
        for name in ("K", "Cl"):
            s = ids.index(name)
            d["amount_increment"][s, i] += 0.002
            d["extracellular_amount_increment"][s, o - n] -= 0.002
            d["membrane_transferred"][s, 0] = -0.002
    return ref.flatten(c, d)


def stage_values(c, y):
    d = ref.unpack(c, y)
    volume = np.r_[
        c["vi"] + d["volume_increment_pL"], c["vo"] + d["extracellular_volume_increment_pL"]
    ]
    amount = np.c_[c["ai"] + d["amount_increment"], c["ao"] + d["extracellular_amount_increment"]]
    return d, volume, amount


def check_stage(c, y, slope, phi, proof, time=0):
    d, volume, amount = stage_values(c, y)
    r = ref.unpack(c, slope)
    n = len(c["vi"])
    current = dict(c["ionic"], vi=volume[:n], vo=volume[n:])
    expected, wanted_phi, _ = ionic.evaluate(current, ionic.flatten(current, d), time)
    np.testing.assert_array_equal(ref.flatten(c["ionic"], r), expected)
    np.testing.assert_array_equal(phi, wanted_phi)
    edges = [
        dict(
            edge,
            hydraulic_permeability_m_per_Pa_s=edge["hydraulic_permeability_m_per_Pa_s"]
            * next(v["availability"] for v in reversed(schedule) if v["time"] <= time),
        )
        for edge, schedule in zip(c["water_case"]["edges"], c["water_controls"], strict=True)
    ]
    oracle = water.evaluate(dict(c["water_case"], edges=edges), volume, amount)
    np.testing.assert_array_equal(r["water_transferred_pL"], oracle["edge_flow_pL_s"])
    np.testing.assert_array_equal(r["water_dissipated_energy_pJ"], oracle["edge_dissipation_pJ_s"])
    expected_volume = np.zeros(len(volume))
    for j, edge in enumerate(edges):
        expected_volume[edge["sender"]] -= r["water_transferred_pL"][j]
        expected_volume[edge["receiver"]] += r["water_transferred_pL"][j]
    np.testing.assert_allclose(
        np.r_[r["volume_increment_pL"], r["extracellular_volume_increment_pL"]],
        expected_volume,
        rtol=3e-15,
        atol=3e-15,
    )
    np.testing.assert_allclose(
        r["amount_increment"].sum(axis=1) + r["extracellular_amount_increment"].sum(axis=1),
        0,
        rtol=0,
        atol=3e-13,
    )
    np.testing.assert_allclose(expected_volume.sum(), 0, rtol=0, atol=3e-14)
    assert abs(proof["physical_energy_balance_pJ_s"]) < 2e-10
    assert abs(proof["water_energy_balance_pJ_s"]) < 1e-24
    assert all(
        np.min(v, initial=0) >= -3e-14 for k, v in r.items() if k.endswith("dissipated_energy_pJ")
    )
    flat = ionic.flatten(current, d)
    ml = ml_routes("tissue", current, current["raw"], flat, expected, phi, time)
    sensors = sensor_routes("tissue", current, current["raw"], flat, expected, phi, time)
    return dict(
        volume_pL=volume.tolist(),
        water_potential_Pa=oracle["water_potential_Pa"].tolist(),
        water_flow_pL_s=oracle["edge_flow_pL_s"].tolist(),
        ML_routes=ml,
        calcium_sensors=sensors,
    )


@pytest.mark.parametrize("arm", tuple(inputs()) or (None,))
@pytest.mark.parametrize("changed", [False, True])
def test_complete_current_volume_stages(arm, changed):
    raw = inputs()[arm]
    c = ref.bind(raw)
    assert len(c["shapes"]) == 23 and len(c["ionic"]["shapes"]) == 19
    assert c["ionic"]["raw"]["model"]["id"] == "resolved_tissue@11"
    y = state(c, changed)
    if changed and arm == "sealed":
        # This accumulated transfer could not have occurred with Lp fixed at0.
        # Keep it as a rejected counterfactual, not a valid evolved state.
        evidence(
            "sealed-counterfactual",
            dict(
                inputs=raw,
                state=y.tolist(),
                expected_rejection="Nonzero transfer on permanently zero-Lp routes",
            ),
        )
        with pytest.raises(ValueError, match="Permanently sealed"):
            ref.evaluate(c, y, 0)
        return
    slope, phi, proof = ref.evaluate(c, y, 0)
    saved = dict(
        inputs=raw,
        state=y.tolist(),
        derivative=slope.tolist(),
        potential_V=phi.tolist(),
        proof=proof,
    )
    evidence(f"stage-{arm}-{changed}", saved)
    saved["checks"] = check_stage(c, y, slope, phi, proof)
    np.testing.assert_array_equal(c["ionic"]["vi"], c["vi"])
    np.testing.assert_array_equal(c["ionic"]["vo"], c["vo"])
    if arm == "open":
        assert {ch["kinetic_law"] for ch in raw["model"]["channels"]} == set(
            ionic.CATALOG_V4_PERMEABILITIES
        )
    evidence(f"stage-{arm}-{changed}", saved)


def test_cak_senses_live_dilution_and_rejects_stale_volume_explanation():
    raw = case()
    c = ref.bind(raw)
    y = state(c, True)
    slope, phi, proof = ref.evaluate(c, y, 0)
    checks = check_stage(c, y, slope, phi, proof)
    d, volume, amount = stage_values(c, y)
    ids = [v["id"] for v in raw["model"]["species"]]
    ca, k = ids.index("Ca"), ids.index("K")
    owners = [v["id"] for v in raw["model"]["cells"]]
    outside = [v["id"] for v in raw["model"]["extracellular"]]
    patches = {v["id"]: v for v in raw["model"]["membranes"]}
    r, compared = ref.unpack(c, slope), []
    for j, ch in enumerate(raw["model"]["channels"]):
        if ch["kinetic_law"] != ionic.CALCIUM_ACTIVATED_LAW:
            continue
        patch = patches[ch["membrane_id"]]
        i, o = owners.index(patch["inside"]), outside.index(patch["outside"])
        if d["volume_increment_pL"][i] == 0:
            continue
        vi, vo = volume[i], volume[len(owners) + o]
        vm = phi[i] - phi[len(owners) + o]
        live = sensor.evaluate(float(vm), float(amount[ca, i] / vi), 298.15)["opening"]
        stale = sensor.evaluate(float(vm), float(amount[ca, i] / c["vi"][i]), 298.15)["opening"]
        assert live < stale and abs(live - stale) > 1e-13
        level = ionic.availability(c["ionic"], "channel", ch["id"], 0)
        wrong = ionic.transport.decimal_flux(
            amount[k, i] / vi,
            amount[k, len(owners) + o] / vo,
            vm,
            1,
            298.15,
            patch["area_m2"],
            ch["max_permeability_m_per_s"] * ch["abundance"],
            1.0,
            level * stale,
            {"F": ionic.F, "R": ionic.R},
        )
        assert abs(wrong - r["channel_transferred"][k, j]) > 1e-13
        compared.append(
            dict(
                channel=ch["id"],
                live_opening=live,
                stale_opening=stale,
                actual_flux_fmol_s=float(r["channel_transferred"][k, j]),
                stale_flux_fmol_s=float(wrong),
            )
        )
    assert compared
    evidence(
        "live-dilution-negative-control",
        dict(inputs=raw, state=y.tolist(), comparisons=compared, checks=checks),
    )


def test_water_only_transfer_carries_no_solute_and_does_not_make_gate_clocks():
    raw = case()
    for kind in ("membrane", "junction", "channel", "pump"):
        for group in raw["experiment"][kind + "_controls"]:
            group["schedule"] = [dict(time=0.0, availability=0.0)]
    for face in raw["model"]["faces"]:
        face["diffusivity_m2_per_s"] = {key: 0.0 for key in face["diffusivity_m2_per_s"]}
    c = ref.bind(raw)
    y = state(c, True)
    slope, phi, proof = ref.evaluate(c, y, 0)
    r = ref.unpack(c, slope)
    np.testing.assert_array_equal(r["amount_increment"], 0)
    np.testing.assert_array_equal(r["extracellular_amount_increment"], 0)
    assert np.any(r["water_transferred_pL"] != 0)
    assert np.any(r["channel_gate"] != 0)
    check_stage(c, y, slope, phi, proof)


def test_maintained_atp_is_not_an_owned_water_osmolyte():
    raw = case()
    c = ref.bind(raw)
    y = state(c, True)
    a = ref.unpack(c, ref.evaluate(c, y, 0)[0])
    for patch in raw["model"]["membranes"]:
        if patch["pump"] is not None:
            patch["pump"]["metabolism"]["atp_mM"] *= 2
    other = ref.bind(raw)
    b = ref.unpack(other, ref.evaluate(other, y, 0)[0])
    np.testing.assert_array_equal(a["water_transferred_pL"], b["water_transferred_pL"])
    assert np.any(a["pump_cycles"] != b["pump_cycles"])


def test_padding_changes_only_execution_capacity_not_reference_owners():
    raw = case()
    c = ref.bind(raw)
    y = state(c, True)
    a = ref.evaluate(c, y, 0)
    padded = deepcopy(raw)
    for key in (
        "capacity",
        "extracellular_capacity",
        "membrane_capacity",
        "channel_capacity",
        "edge_capacity",
        "face_capacity",
    ):
        padded["execution"][key] += 3
    p = ref.bind(padded)
    b = ref.evaluate(p, y, 0)
    assert p["shapes"] == c["shapes"]
    np.testing.assert_array_equal(a[0], b[0])
    np.testing.assert_array_equal(a[1], b[1])


@pytest.mark.parametrize("field", ["water_transferred_pL", "water_dissipated_energy_pJ"])
def test_permanently_sealed_route_cannot_accumulate_transfer_or_heat(field):
    c = ref.bind(case("sealed"))
    d = ref.unpack(c, ref.initial(c))
    d[field][0] = 1e-20
    with pytest.raises(ValueError, match="Permanently sealed"):
        ref.evaluate(c, ref.flatten(c, d), 0)


@pytest.mark.parametrize("fault", ["lower_volume", "upper_volume", "missing_slot", "finite_fuel"])
def test_domain_failures_are_not_repaired(fault):
    raw = case()
    if fault == "finite_fuel":
        next(p["pump"] for p in raw["model"]["membranes"] if p["pump"] is not None)[
            "metabolism"
        ] = dict(kind="finite_energy_pool@1", pool_id="unsupported")
        with pytest.raises(ValueError, match="maintained"):
            ref.bind(raw)
        return
    c = ref.bind(raw)
    d = ref.unpack(c, ref.initial(c))
    if fault == "lower_volume":
        d["volume_increment_pL"][0] = c["minimum_volume_pL"][0] - c["vi"][0]
    elif fault == "upper_volume":
        d["volume_increment_pL"][0] = c["maximum_volume_pL"][0] - c["vi"][0]
    else:
        j = next(
            j
            for j, ch in enumerate(raw["model"]["channels"])
            if ch["kinetic_law"] == ionic.CALCIUM_ACTIVATED_LAW
        )
        d["channel_gate"][0, j] = 1e-20
    with pytest.raises(ValueError):
        ref.evaluate(c, ref.flatten(c, d), 0)


@pytest.mark.parametrize("changed", [False, True])
@pytest.mark.parametrize("version", ["resolved_water@2", "resolved_water@3"])
def test_original_water2_behavior_is_bitwise_preserved(changed, version):
    root = Path(os.environ["CELLS_ML_WATER_BASELINE"])
    old = frozen_module(
        "old_active_water", root / "validation/tissue/surface_water_kinetic_reference.py"
    )
    old.ionic = frozen_module("old_ionic", root / "validation/tissue/surface_kinetic_reference.py")
    raw = case()
    allowed = (
        set(ionic.CATALOG_PERMEABILITIES)
        - set(ionic.ADDED_SODIUM_LAWS)
        - set(ionic.ADDED_POTASSIUM_LAWS)
        - set(ionic.ADDED_LEAK_LAWS)
    )
    assert len(allowed) == 18
    raw["model"]["channels"] = [v for v in raw["model"]["channels"] if v["kinetic_law"] in allowed]
    names = {v["id"] for v in raw["model"]["channels"]}
    raw["experiment"]["channel_controls"] = [
        v for v in raw["experiment"]["channel_controls"] if v["channel_id"] in names
    ]
    raw["model"]["id"] = version
    previous = deepcopy(raw)
    previous["model"]["id"] = "resolved_water@2"
    c, prior = ref.bind(raw), old.bind(previous)
    np.testing.assert_array_equal(ref.initial(c), old.initial(prior))
    y = state(c, changed)
    actual, wanted = ref.evaluate(c, y, 0), old.evaluate(prior, y, 0)
    np.testing.assert_array_equal(actual[0], wanted[0])
    np.testing.assert_array_equal(actual[1], wanted[1])
    assert actual[2] == wanted[2]
    evidence(
        f"old-water2-exact-{version}-{changed}",
        dict(
            inputs=raw,
            state=y.tolist(),
            derivative=actual[0].tolist(),
            potential_V=actual[1].tolist(),
            proof=actual[2],
        ),
    )


def test_actual_pair_water_only_relaxes_for_twelve_conservative_time_constants():
    c = ref.bind(case())
    source = c["water_case"]
    edge = next(v for v in source["edges"] if v["hydraulic_permeability_m_per_Pa_s"] > 0)
    owners = [edge["sender"], edge["receiver"]]
    pair = {k: source[k] for k in ("temperature_K", "gas_constant_J_per_mol_K")}
    for key in (
        "initial_volume_pL",
        "reference_volume_pL",
        "impermeant_amount_fmol",
        "bulk_modulus_Pa",
        "pressure_offset_Pa",
    ):
        pair[key] = source[key][owners].tolist()
    pair["amount_fmol"] = source["amount_fmol"][:, owners].tolist()
    pair["edges"] = [dict(edge, sender=0, receiver=1)]
    bound = water.bind(pair)
    total = sum(bound["initial_volume_pL"])
    osmoles = bound["amount_fmol"].sum(axis=0) + bound["impermeant_amount_fmol"]
    conductance = 1e15 * edge["area_m2"] * edge["hydraulic_permeability_m_per_Pa_s"]
    # On 0<V_i<Vtotal, the restoring slope exceeds this strictly positive
    # lower bound. The resulting tau is conservative for this nonlinear pair.
    rate_lower_bound = conductance * (
        np.sum(bound["bulk_modulus_Pa"] / bound["reference_volume_pL"])
        + bound["gas_constant_J_per_mol_K"] * bound["temperature_K"] * osmoles.sum() / total**2
    )
    tau_upper_s = 1 / rate_lower_bound
    times = np.linspace(0, 12 * tau_upper_s, 49)
    equilibrium = water.two_compartment_equilibrium(pair)
    a, b = (water.integrate(pair, times, refinement=r) for r in (1, 2))
    initial_error = np.max(np.abs(bound["initial_volume_pL"] - equilibrium))
    assert initial_error > 1e-6
    final_error = np.max(np.abs(a["volume_pL"][-1] - equilibrium))
    assert final_error <= initial_error * np.exp(-12) + 2e-11
    np.testing.assert_allclose(a["volume_pL"], b["volume_pL"], rtol=2e-11, atol=2e-12)
    np.testing.assert_allclose(a["volume_pL"].sum(axis=1), total, rtol=0, atol=3e-13)
    residual = (
        a["free_energy_pJ"] - a["free_energy_pJ"][0] + a["edge_dissipated_energy_pJ"].sum(axis=1)
    )
    np.testing.assert_allclose(residual, 0, rtol=0, atol=3e-8)
    assert np.max(np.diff(a["free_energy_pJ"])) <= 3e-10
    evidence(
        "isolated-water-relaxation",
        dict(
            inputs=pair,
            source_owner_indices=owners,
            conservative_tau_s=float(tau_upper_s),
            horizon_s=float(times[-1]),
            equilibrium_volume_pL=equilibrium.tolist(),
            times_s=times.tolist(),
            volume_pL=a["volume_pL"].tolist(),
            refined_volume_pL=b["volume_pL"].tolist(),
            energy_residual_pJ=residual.tolist(),
            initial_distance_pL=float(initial_error),
            final_distance_pL=float(final_error),
            evaluations=[a["evaluations"], b["evaluations"]],
            scope=(
                "Actual fixture pair, unchanged rates/inventories, fixed solutes; "
                "water-only relaxation, not full tissue settling"
            ),
        ),
    )


def test_short_coupled_history_refines_and_closes_mixing_elastic_and_capacitor_energy():
    raw = case()
    e = raw["experiment"]
    e.update(end_time=2.5e-6, observation_times=[0.0, 0.7e-6, 1.3e-6, 1.9e-6, 2.5e-6])
    for kind in ref.CONTROL_KINDS:
        for group in e[kind + "_controls"]:
            group["schedule"] = [row for row in group["schedule"] if row["time"] == 0]
    e["water_controls"][0]["schedule"].append(dict(time=0.7e-6, availability=0.0))
    e["channel_controls"][-1]["schedule"].append(dict(time=1.3e-6, availability=0.0))
    e["pump_controls"][0]["schedule"].append(dict(time=1.9e-6, availability=0.0))
    c = ref.bind(raw)
    ordinary, refined = (ref.integrate(raw, refinement=r) for r in (1, 2))
    a, b = (ref.unpack(c, v["state"]) for v in (ordinary, refined))
    for name in a:
        np.testing.assert_allclose(
            a[name], b[name], rtol=3e-9, atol=3e-28 if name.endswith("_C") else 3e-13, err_msg=name
        )
    np.testing.assert_allclose(
        a["volume_increment_pL"].sum(axis=-1) + a["extracellular_volume_increment_pL"].sum(axis=-1),
        0,
        rtol=0,
        atol=3e-14,
    )
    full_energy = []
    for time, y, phi in zip(
        ordinary["times"], ordinary["state"], ordinary["potential_V"], strict=True
    ):
        d, volume, amount = stage_values(c, y)
        slope, _, proof = ref.evaluate(c, y, time)
        check_stage(c, y, slope, phi, proof, time)
        stored = water.evaluate(c["water_case"], volume, amount)["free_energy_pJ"]
        for j, patch in enumerate(raw["model"]["membranes"]):
            i, o = (
                c["layout"]["membrane_cell"][j],
                len(c["vi"]) + c["layout"]["membrane_outside"][j],
            )
            stored += 0.5e12 * patch["capacitance_F"] * (phi[i] - phi[o]) ** 2
        full_energy.append(stored)
    dissipated = sum(
        value.sum(axis=tuple(range(1, value.ndim)))
        for name, value in a.items()
        if name.endswith("dissipated_energy_pJ")
    )
    residual = (
        np.asarray(full_energy) - full_energy[0] + dissipated - a["metabolic_work_pJ"].sum(axis=-1)
    )
    np.testing.assert_allclose(residual, 0, rtol=0, atol=3e-9)
    assert ordinary["event_times"] == [0.0, 0.7e-6, 1.3e-6, 1.9e-6, 2.5e-6]
    evidence(
        "short-coupled-history",
        dict(
            inputs=raw,
            times=ordinary["times"],
            state=ordinary["state"].tolist(),
            refined_state=refined["state"].tolist(),
            potential_V=ordinary["potential_V"].tolist(),
            energy_residual_pJ=residual.tolist(),
            evaluations=[ordinary["evaluations"], refined["evaluations"]],
            scope=(
                "2.5-us full23 coupling/event refinement; distinct from isolated water relaxation"
            ),
        ),
    )


def test_no_production_imports():
    assert not any(name == "cells" or name.startswith(("cells.", "jax")) for name in sys.modules)
