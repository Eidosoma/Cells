"""Independent zero-state calcium-sensitive K in three ordinary tissue layers.

The literal legacy numeric-mM opening is not relabelled as a physiological fit.
No production imports, new gate clock, calcium consumption or ATP demand.
"""

import json
import os
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from validation.channels import calcium_activated_potassium_reference as sensor
from validation.tissue import surface_calcium_energy_reference as energy
from validation.tissue import surface_calcium_reference as calcium
from validation.tissue import surface_kinetic_reference as ionic
from validation.tissue.test_calcium_catalog_v2_reference import (
    evidence,
    frozen_module,
    ion_model,
    physical_balance,
)

MODELS = {
    "tissue": (ionic, "resolved_tissue@10", 19),
    "calcium": (calcium, "resolved_calcium@9", 34),
    "energy": (energy, "resolved_calcium_energy@3", 38),
}
LAW = "betse_cagpotassium_numeric_mM_scale@1"
pytestmark = pytest.mark.skipif(
    "CELLS_CALCIUM_ACTIVATED_INPUTS" not in os.environ,
    reason="Require isolated serialized fixture inputs",
)


def inputs():
    directory = os.environ.get("CELLS_CALCIUM_ACTIVATED_INPUTS")
    if not directory:
        return {}
    root = Path(directory)
    answer = {}
    for path in sorted(root.rglob("*.json")):
        raw = json.loads(path.read_text())
        if isinstance(raw, dict) and raw.get("model", {}).get("id") in {
            v[1] for v in MODELS.values()
        }:
            answer[str(path.relative_to(root).with_suffix(""))] = raw
    return answer


def case(family, arm="open"):
    return deepcopy(
        next(
            raw
            for name, raw in inputs().items()
            if raw["model"]["id"] == MODELS[family][1] and name.endswith(arm)
        )
    )


def indices(raw):
    return [j for j, v in enumerate(ion_model(raw)["channels"]) if v["kinetic_law"] == LAW]


def owner_routes(raw):
    m = ion_model(raw)
    patches = {v["id"]: v for v in m["membranes"]}
    cells = [v["id"] for v in m["cells"]]
    outside = [v["id"] for v in m["extracellular"]]
    return [
        (
            cells.index(patches[ch["membrane_id"]]["inside"]),
            outside.index(patches[ch["membrane_id"]]["outside"]),
        )
        for ch in m["channels"]
    ]


def state(family, c, raw, changed):
    module = MODELS[family][0]
    d = module.unpack(c, module.initial(c))
    if changed:
        d["channel_gate"][:] = np.array([[0.31], [0.63]])
        d["channel_gate"][:, indices(raw)] = 0
        if family == "tissue":
            ids = [v["id"] for v in ion_model(raw)["species"]]
            for name, amount in (("Ca", 1e-4), ("Cl", 2e-4)):
                d["amount_increment"][ids.index(name), 0] += amount
                d["extracellular_amount_increment"][ids.index(name), 0] -= amount
        else:
            for i, store in enumerate(c["stores"]):
                d["chemical_amount_increment"][
                    i, [store.ids.index(v) for v in ("Ca", "B", "CaB")], store.cy
                ] += 1e-4 * np.array([-1, -1, 1])
        if family == "energy":
            for i in range(len(c["vi"])):
                d["energy_amount_increment_fmol"][:, i] += (
                    0.1 * c["energy_initial"][:, i].min() * np.array([-1, 1, 1])
                )
    return module.flatten(c, d)


def sensor_routes(family, c, raw, y, slope, phi, time):
    d, rate = ionic.unpack(c, y), ionic.unpack(c, slope)
    m = ion_model(raw)
    ids = [v["id"] for v in m["species"]]
    ca, potassium = ids.index("Ca"), ids.index("K")
    patches = {v["id"]: j for j, v in enumerate(m["membranes"])}
    mapped = owner_routes(raw)
    checks = []
    for j in indices(raw):
        ch, (i, o) = m["channels"][j], mapped[j]
        patch = m["membranes"][patches[ch["membrane_id"]]]
        vm = phi[i] - phi[len(c["vi"]) + o]
        if family == "tissue":
            free = (c["ai"] + d["amount_increment"])[:, i] / c["vi"][i]
        else:
            store = c["stores"][i]
            free = (store.n0 + d["chemical_amount_increment"][i])[
                [store.ids.index(v) for v in ids], store.cy
            ] / store.volume[store.cy]
        outside = (c["ao"] + d["extracellular_amount_increment"])[:, o] / c["vo"][o]
        scalar = sensor.evaluate(float(vm), float(free[ca]), 298.15)
        context = c["calcium"] if family == "energy" else c
        level = ionic.availability(context, "channel", ch["id"], time)
        expected = ionic.transport.decimal_flux(
            free[potassium],
            outside[potassium],
            vm,
            1,
            298.15,
            patch["area_m2"],
            ch["max_permeability_m_per_s"] * ch["abundance"],
            1.0,
            level * scalar["opening"],
            {"F": ionic.F, "R": ionic.R},
        )
        np.testing.assert_array_equal(d["channel_gate"][:, j], 0)
        np.testing.assert_array_equal(rate["channel_gate"][:, j], 0)
        np.testing.assert_array_equal(np.delete(rate["channel_transferred"][:, j], potassium), 0)
        np.testing.assert_allclose(
            rate["channel_transferred"][potassium, j], expected, rtol=3e-15, atol=3e-18
        )
        assert rate["channel_dissipated_energy_pJ"][potassium, j] >= 0
        checks.append(
            dict(
                channel_id=ch["id"],
                cell_owner=i,
                free_calcium_mM=float(free[ca]),
                voltage_V=float(vm),
                opening=scalar["opening"],
                potassium_outward_fmol_s=float(expected),
                gate_slots=[0.0, 0.0],
                gate_derivatives=[0.0, 0.0],
            )
        )
    return checks


@pytest.mark.parametrize("name", tuple(inputs()) or (None,))
@pytest.mark.parametrize("changed", [False, True])
def test_complete_zero_state_catalog_stages(name, changed):
    raw = inputs()[name]
    family = next(k for k, v in MODELS.items() if raw["model"]["id"] == v[1])
    module, _, count = MODELS[family]
    c = module.bind(raw)
    assert len(c["shapes"]) == count
    y = state(family, c, raw, changed)
    slope, phi, proof = module.evaluate(c, y, 0)
    saved = dict(
        inputs=raw,
        state=y.tolist(),
        derivative=slope.tolist(),
        potential_V=phi.tolist(),
        proof=proof,
    )
    evidence(f"stage-{name}-{changed}", saved)
    assert np.isfinite(slope).all()
    saved["accounting"] = physical_balance(family, c, y, slope, phi, proof)
    saved["sensors"] = sensor_routes(family, c, raw, y, slope, phi, 0)
    if name.endswith("open"):
        assert {v["kinetic_law"] for v in ion_model(raw)["channels"]} == set(
            ionic.CATALOG_V3_PERMEABILITIES
        )
    evidence(f"stage-{name}-{changed}", saved)


def test_versioned_catalog_maps_do_not_mutate():
    assert [
        len(v)
        for v in (
            ionic.CATALOG_PERMEABILITIES,
            ionic.CATALOG_V2_PERMEABILITIES,
            ionic.CATALOG_V3_PERMEABILITIES,
        )
    ] == [35, 39, 40]
    assert LAW not in ionic.CATALOG_V2_PERMEABILITIES
    assert ionic.CATALOG_V3_PERMEABILITIES[LAW] == (("K", 1.0),)


@pytest.mark.parametrize("family", MODELS)
def test_sensing_adds_only_potassium_transfer_without_calcium_or_fuel_demand(family):
    raw, module = case(family), MODELS[family][0]
    selected = {ion_model(raw)["channels"][j]["id"] for j in indices(raw)}
    for group in raw["experiment"]["channel_controls"]:
        group["schedule"] = [dict(time=0.0, availability=float(group["channel_id"] in selected))]
    c = module.bind(raw)
    y = state(family, c, raw, True)
    a, phi0, proof = module.evaluate(c, y, 0)
    blocked = deepcopy(raw)
    for group in blocked["experiment"]["channel_controls"]:
        group["schedule"][0]["availability"] = 0.0
    b, phi1, _ = module.evaluate(module.bind(blocked), y, 0)
    np.testing.assert_array_equal(phi0, phi1)
    delta = module.unpack(c, a - b)
    expected_i, expected_o = np.zeros_like(c["ai"]), np.zeros_like(c["ao"])
    ids = [v["id"] for v in ion_model(raw)["species"]]
    k, ca = ids.index("K"), ids.index("Ca")
    for j, (i, o) in enumerate(owner_routes(raw)):
        expected_i[k, i] -= delta["channel_transferred"][k, j]
        expected_o[k, o] += delta["channel_transferred"][k, j]
    np.testing.assert_allclose(delta["amount_increment"], expected_i, rtol=3e-13, atol=3e-15)
    np.testing.assert_allclose(
        delta["extracellular_amount_increment"], expected_o, rtol=3e-13, atol=3e-15
    )
    np.testing.assert_array_equal(delta["amount_increment"][ca], 0)
    np.testing.assert_array_equal(delta["channel_gate"], 0)
    for field in ("pump_cycles", "metabolic_work_pJ"):
        np.testing.assert_array_equal(delta[field], 0)
    if family != "tissue":
        for i, store in enumerate(c["stores"]):
            expected = np.zeros_like(store.n0)
            expected[store.ids.index("K"), store.cy] = expected_i[k, i]
            np.testing.assert_allclose(
                delta["chemical_amount_increment"][i], expected, rtol=3e-13, atol=3e-15
            )
        for field in (
            "plasma_pump_cycles",
            "er_pump_transferred",
            "plasma_metabolic_work_pJ",
            "er_metabolic_work_pJ",
        ):
            np.testing.assert_array_equal(delta[field], 0)
    if family == "energy":
        for field in energy.ENERGY_FIELDS:
            np.testing.assert_array_equal(delta[field], 0)
    physical_balance(family, c, y, a, phi0, proof)
    evidence(
        f"potassium-only-{family}",
        dict(
            inputs=raw,
            state=y.tolist(),
            open_derivative=a.tolist(),
            blocked_derivative=b.tolist(),
            potential_V=phi0.tolist(),
            sensing_consumes_calcium=False,
            sensing_consumes_ATP=False,
        ),
    )


@pytest.mark.parametrize("family", ["calcium", "energy"])
@pytest.mark.parametrize("owner", [0, 1])
def test_only_current_owner_free_calcium_controls_the_sensor(family, owner):
    raw, module = case(family), MODELS[family][0]
    c = module.bind(raw)
    y = module.initial(c)
    before, phi0, _ = module.evaluate(c, y, 0)
    original = module.unpack(c, before)
    mapped = owner_routes(raw)
    affected = []
    for kind in ("bind_cytosol", "er_to_bound"):
        d = module.unpack(c, y.copy())
        store = c["stores"][owner]
        amount = 1e-4
        d["chemical_amount_increment"][owner, store.ids.index("B"), store.cy] -= amount
        d["chemical_amount_increment"][owner, store.ids.index("CaB"), store.cy] += amount
        d["chemical_amount_increment"][
            owner, store.ca, store.cy if kind == "bind_cytosol" else store.er
        ] -= amount
        changed = module.flatten(c, d)
        derivative, phi1, proof = module.evaluate(c, changed, 0)
        after = module.unpack(c, derivative)
        i = np.asarray(c["layout"]["membrane_cell"])
        o = len(c["vi"]) + np.asarray(c["layout"]["membrane_outside"])
        np.testing.assert_allclose(phi0[i] - phi0[o], phi1[i] - phi1[o], rtol=0, atol=3e-14)
        for j in indices(raw):
            if mapped[j][0] == owner and kind == "bind_cytosol":
                assert np.any(
                    after["channel_transferred"][:, j] != original["channel_transferred"][:, j]
                )
                affected.append(ion_model(raw)["channels"][j]["id"])
            else:
                np.testing.assert_allclose(
                    after["channel_transferred"][:, j],
                    original["channel_transferred"][:, j],
                    rtol=3e-13,
                    atol=3e-16,
                )
        physical_balance(family, c, changed, derivative, phi1, proof)
        sensor_routes(family, c, raw, changed, derivative, phi1, 0)
    assert affected


@pytest.mark.parametrize("family", MODELS)
def test_outside_calcium_is_not_the_sensing_input(family):
    raw, module = case(family), MODELS[family][0]
    c = module.bind(raw)
    assert len(c["vo"]) >= 2
    y = module.initial(c)
    a, phi0, _ = module.evaluate(c, y, 0)
    d = module.unpack(c, y.copy())
    ids = [v["id"] for v in ion_model(raw)["species"]]
    for species, amount in (("Ca", 1e-4), ("Cl", 2e-4)):
        d["extracellular_amount_increment"][ids.index(species), [0, 1]] += np.array(
            [-amount, amount]
        )
    changed = module.flatten(c, d)
    b, phi1, proof = module.evaluate(c, changed, 0)
    ra, rb = module.unpack(c, a), module.unpack(c, b)
    np.testing.assert_allclose(
        ra["channel_transferred"][:, indices(raw)],
        rb["channel_transferred"][:, indices(raw)],
        rtol=3e-13,
        atol=3e-16,
    )
    physical_balance(family, c, changed, b, phi1, proof)
    sensor_routes(family, c, raw, changed, b, phi1, 0)


@pytest.mark.parametrize("family", MODELS)
@pytest.mark.parametrize("blocked", [False, True])
def test_nonzero_packed_slots_reject_even_when_blocked(family, blocked):
    raw, module = case(family), MODELS[family][0]
    if blocked:
        for group in raw["experiment"]["channel_controls"]:
            group["schedule"] = [dict(time=0.0, availability=0.0)]
    c = module.bind(raw)
    d = module.unpack(c, module.initial(c))
    j = indices(raw)[0]
    d["channel_gate"][0, j] = 1e-20
    with pytest.raises(ValueError, match="slots must stay zero"):
        module.evaluate(c, module.flatten(c, d), 0)


@pytest.mark.parametrize(
    "fault", ["invented_gates", "missing_ca", "wrong_ca_valence", "wrong_k_weight"]
)
def test_stateless_sensor_declaration_is_explicit(fault):
    raw = case("tissue")
    m = raw["model"]
    ch = deepcopy(m["channels"][indices(raw)[0]])
    m["channels"] = [ch]
    raw["experiment"]["channel_controls"] = [
        v for v in raw["experiment"]["channel_controls"] if v["channel_id"] == ch["id"]
    ]
    if fault == "invented_gates":
        ch["initial_gate"] = [0.0, 0.0]
    elif fault == "missing_ca":
        m["species"] = [v for v in m["species"] if v["id"] != "Ca"]
    elif fault == "wrong_ca_valence":
        next(v for v in m["species"] if v["id"] == "Ca")["valence"] = 1
    else:
        ch["permeant_ions"][0]["relative_permeability"] = 0.5
    with pytest.raises(ValueError, match="initial_gate|exact ordered"):
        ionic.bind(raw)


@pytest.mark.parametrize("family", MODELS)
def test_old_39_law_identity_rejects_new_sensor(family):
    raw = case(family)
    ion_model(raw)["id"] = "resolved_tissue@9"
    if family != "tissue":
        raw["model"]["id"] = (
            "resolved_calcium@8" if family == "calcium" else "resolved_calcium_energy@2"
        )
    with pytest.raises(ValueError, match="known channel law"):
        MODELS[family][0].bind(raw)


@pytest.mark.parametrize("family", ["calcium", "energy"])
def test_new_owned_identity_requires_tissue10(family):
    raw = case(family)
    ion_model(raw)["id"] = "resolved_tissue@9"
    with pytest.raises(ValueError, match="versioned"):
        MODELS[family][0].bind(raw)


@pytest.mark.parametrize("family", MODELS)
def test_control_boundary_is_algebraic_and_preserves_zero_slots(family):
    raw, module = case(family), MODELS[family][0]
    event = raw["experiment"]["end_time"] / 3
    selected = {ion_model(raw)["channels"][j]["id"] for j in indices(raw)}
    for group in raw["experiment"]["channel_controls"]:
        if group["channel_id"] in selected:
            group["schedule"] = [
                dict(time=0.0, availability=1.0),
                dict(time=event, availability=0.0),
            ]
    c = module.bind(raw)
    y = module.initial(c)
    a, phi0, _ = module.evaluate(c, y, np.nextafter(event, 0))
    b, phi1, proof = module.evaluate(c, y, event)
    ra, rb = module.unpack(c, a), module.unpack(c, b)
    np.testing.assert_array_equal(phi0, phi1)
    assert np.any(ra["channel_transferred"][:, indices(raw)] != 0)
    np.testing.assert_array_equal(rb["channel_transferred"][:, indices(raw)], 0)
    np.testing.assert_array_equal(ra["channel_gate"][:, indices(raw)], 0)
    np.testing.assert_array_equal(rb["channel_gate"][:, indices(raw)], 0)
    physical_balance(family, c, y, b, phi1, proof)


@pytest.mark.parametrize("family", MODELS)
@pytest.mark.parametrize("old_law_count", [35, 39])
@pytest.mark.parametrize("changed", [False, True])
def test_previous_law_behavior_is_bitwise_unchanged(family, old_law_count, changed):
    root = Path(os.environ["CELLS_CALCIUM_ACTIVATED_BASELINE"])
    old_i = frozen_module("prior_kinetic", root / "validation/tissue/surface_kinetic_reference.py")
    old_c = frozen_module("prior_calcium", root / "validation/tissue/surface_calcium_reference.py")
    old_c.kinetic = old_i
    old_e = frozen_module(
        "prior_energy", root / "validation/tissue/surface_calcium_energy_reference.py"
    )
    old_e.calcium = old_c
    previous = {"tissue": old_i, "calcium": old_c, "energy": old_e}[family]
    raw = case(family)
    m = ion_model(raw)
    allowed = (
        ionic.CATALOG_PERMEABILITIES if old_law_count == 35 else ionic.CATALOG_V2_PERMEABILITIES
    )
    m["channels"] = [v for v in m["channels"] if v["kinetic_law"] in allowed]
    names = {v["id"] for v in m["channels"]}
    raw["experiment"]["channel_controls"] = [
        v for v in raw["experiment"]["channel_controls"] if v["channel_id"] in names
    ]
    old_raw = deepcopy(raw)
    ion_model(old_raw)["id"] = "resolved_tissue@8" if old_law_count == 35 else "resolved_tissue@9"
    if family != "tissue":
        old_raw["model"]["id"] = (
            ("resolved_calcium@7" if old_law_count == 35 else "resolved_calcium@8")
            if family == "calcium"
            else (
                "resolved_calcium_energy@1" if old_law_count == 35 else "resolved_calcium_energy@2"
            )
        )
    module = MODELS[family][0]
    c, old = module.bind(raw), previous.bind(old_raw)
    np.testing.assert_array_equal(module.initial(c), previous.initial(old))
    y = state(family, c, raw, changed)
    actual, expected = module.evaluate(c, y, 0), previous.evaluate(old, y, 0)
    np.testing.assert_array_equal(actual[0], expected[0])
    np.testing.assert_array_equal(actual[1], expected[1])
    evidence(
        f"old{old_law_count}-exact-{family}-{changed}",
        dict(
            state=y.tolist(),
            derivative=actual[0].tolist(),
            potential_V=actual[1].tolist(),
            exact_derivative=True,
            exact_potential=True,
        ),
    )


def test_short_energy_trajectory_has_exact_zero_sensor_slots_and_refines():
    raw = case("energy")
    e = raw["experiment"]
    e.update(end_time=2.5e-6, observation_times=[0.0, 1.1e-6, 1.7e-6, 2.5e-6])
    for name, groups in e.items():
        if name.endswith("_controls"):
            for group in groups:
                key = "schedule" if "schedule" in group else "controls"
                group[key] = [v for v in group[key] if v["time"] == 0]
    ch = ion_model(raw)["channels"][indices(raw)[0]]["id"]
    next(g for g in e["channel_controls"] if g["channel_id"] == ch)["schedule"].append(
        dict(time=1.1e-6, availability=0.0)
    )
    e["regeneration_controls"][0]["schedule"].append(dict(time=1.7e-6, availability=0.0))
    c = energy.bind(raw)
    ordinary, refined = (energy.integrate(raw, refinement=r) for r in (1, 2))
    evidence(
        "short-adaptive",
        dict(
            inputs=raw,
            times=ordinary["times"],
            state=ordinary["state"].tolist(),
            refined_state=refined["state"].tolist(),
            evaluations=[ordinary["evaluations"], refined["evaluations"]],
            scope="2.5-us full coupled wiring; instantaneous sensor has no gate clock",
        ),
    )
    for name in c["shapes"]:
        a, b = (energy.unpack(c, result["state"])[name] for result in (ordinary, refined))
        np.testing.assert_allclose(
            a, b, rtol=3e-9, atol=3e-28 if name.endswith("_C") else 3e-13, err_msg=name
        )
    for result in (ordinary, refined):
        np.testing.assert_array_equal(
            energy.unpack(c, result["state"])["channel_gate"][:, :, indices(raw)], 0
        )
    assert ordinary["event_times"] == [0.0, 1.1e-6, 1.7e-6, 2.5e-6]
    for time, y in zip(ordinary["times"], ordinary["state"], strict=True):
        slope, phi, proof = energy.evaluate(c, y, time)
        physical_balance("energy", c, y, slope, phi, proof)
        sensor_routes("energy", c, raw, y, slope, phi, time)


def test_no_production_imports():
    assert not any(name == "cells" or name.startswith(("cells.", "jax")) for name in sys.modules)
