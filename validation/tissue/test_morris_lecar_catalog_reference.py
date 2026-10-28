"""Independent mixed 0/1/2-state ML catalog integration, not native clocks.

Raw fixture JSON and the separately frozen scalar reference are the only
inputs. ML HCN retains its source sign and K/Na routing, without a Ca route.
"""

import json
import os
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from validation.channels import morris_lecar_channels_reference as ml
from validation.tissue import surface_calcium_energy_reference as energy
from validation.tissue import surface_calcium_reference as calcium
from validation.tissue import surface_kinetic_reference as ionic
from validation.tissue.test_calcium_activated_catalog_reference import (
    owner_routes,
    sensor_routes,
)
from validation.tissue.test_calcium_activated_catalog_reference import (
    state as previous_state,
)
from validation.tissue.test_calcium_catalog_v2_reference import (
    evidence,
    frozen_module,
    ion_model,
    physical_balance,
)

MODELS = {
    "tissue": (ionic, "resolved_tissue@11", 19),
    "calcium": (calcium, "resolved_calcium@10", 34),
    "energy": (energy, "resolved_calcium_energy@4", 38),
}
LAWS = tuple(ionic.MORRIS_LECAR_LAWS)
DYNAMIC = ionic.ML_DYNAMIC_LAWS
pytestmark = pytest.mark.skipif(
    "CELLS_MORRIS_LECAR_INPUTS" not in os.environ,
    reason="Require frozen raw fixtures and the stable independent scalar component",
)


def inputs():
    directory = os.environ.get("CELLS_MORRIS_LECAR_INPUTS")
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


def state(family, c, raw, changed):
    d = ionic.unpack(c, previous_state(family, c, raw, changed))
    for j, ch in enumerate(ion_model(raw)["channels"]):
        law = ch["kinetic_law"]
        if law in LAWS:
            d["channel_gate"][1, j] = 0
            if law not in DYNAMIC:
                d["channel_gate"][0, j] = 0
    return ionic.flatten(c, d)


def ml_routes(family, c, raw, y, slope, phi, time):
    d, rate = ionic.unpack(c, y), ionic.unpack(c, slope)
    m = ion_model(raw)
    ids, patches = [v["id"] for v in m["species"]], {v["id"]: v for v in m["membranes"]}
    checks = []
    for j, (ch, (i, o)) in enumerate(zip(m["channels"], owner_routes(raw), strict=True)):
        law = ch["kinetic_law"]
        if law not in LAWS:
            continue
        cls = ionic.MORRIS_LECAR_LAWS[law]
        vm = phi[i] - phi[len(c["vi"]) + o]
        scalar = ml.kinetics(float(vm), cls)
        opened = ml.opening(float(d["channel_gate"][0, j]), float(vm), cls)
        expected_gate = ml.rhs(float(d["channel_gate"][0, j]), float(vm), cls)
        np.testing.assert_allclose(
            rate["channel_gate"][0, j], expected_gate, rtol=3e-15, atol=1e-12
        )
        np.testing.assert_array_equal(d["channel_gate"][1, j], 0)
        np.testing.assert_array_equal(rate["channel_gate"][1, j], 0)
        if law not in DYNAMIC:
            np.testing.assert_array_equal(d["channel_gate"][:, j], 0)
            np.testing.assert_array_equal(rate["channel_gate"][:, j], 0)
            assert opened == scalar["target"]
        else:
            assert opened == d["channel_gate"][0, j]
            np.testing.assert_allclose(
                scalar["tau_s"], scalar["raw_tau"] / (1000 * scalar["phi"]), rtol=3e-15, atol=0
            )
        if family == "tissue":
            ci = (c["ai"] + d["amount_increment"])[:, i] / c["vi"][i]
        else:
            store = c["stores"][i]
            ci = (store.n0 + d["chemical_amount_increment"][i])[
                [store.ids.index(v) for v in ids], store.cy
            ] / store.volume[store.cy]
        co = (c["ao"] + d["extracellular_amount_increment"])[:, o] / c["vo"][o]
        context = c["calcium"] if family == "energy" else c
        level = ionic.availability(context, "channel", ch["id"], time)
        expected = np.zeros(len(ids))
        for species, weight in ml.PERMEABILITIES[cls]:
            s = ids.index(species)
            expected[s] = ionic.transport.decimal_flux(
                ci[s],
                co[s],
                vm,
                m["species"][s]["valence"],
                298.15,
                patches[ch["membrane_id"]]["area_m2"],
                ch["max_permeability_m_per_s"] * ch["abundance"] * weight,
                1.0,
                level * opened,
                {"F": ionic.F, "R": ionic.R},
            )
        np.testing.assert_allclose(
            rate["channel_transferred"][:, j], expected, rtol=3e-15, atol=3e-18
        )
        assert np.all(rate["channel_dissipated_energy_pJ"][:, j] >= 0)
        if cls in ("HCN2_ML", "HCN4_ML"):
            assert tuple(
                (v["species_id"], v["relative_permeability"]) for v in ch["permeant_ions"]
            ) == (("K", 1.0), ("Na", 0.2))
            assert rate["channel_transferred"][ids.index("Ca"), j] == 0
            assert ml.voltage_derivative(float(vm), cls)[0] > 0
        checks.append(
            dict(
                channel_id=ch["id"],
                law=law,
                owner=i,
                voltage_V=float(vm),
                dynamic=law in DYNAMIC,
                opening=float(opened),
                target=scalar["target"],
                tau_s=scalar["tau_s"] if law in DYNAMIC else None,
                gate_derivative_per_s=rate["channel_gate"][:, j].tolist(),
                transferred_fmol_s=expected.tolist(),
            )
        )
    return checks


@pytest.mark.parametrize("name", tuple(inputs()) or (None,))
@pytest.mark.parametrize("changed", [False, True])
def test_complete_mixed_state_catalog(name, changed):
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
    saved["ML_routes"] = ml_routes(family, c, raw, y, slope, phi, 0)
    saved["calcium_sensors"] = sensor_routes(family, c, raw, y, slope, phi, 0)
    if name.endswith("open"):
        assert {v["kinetic_law"] for v in ion_model(raw)["channels"]} == set(
            ionic.CATALOG_V4_PERMEABILITIES
        )
    evidence(f"stage-{name}-{changed}", saved)


def test_versioned_catalog_sizes_and_state_counts():
    assert [
        len(v)
        for v in (
            ionic.CATALOG_PERMEABILITIES,
            ionic.CATALOG_V2_PERMEABILITIES,
            ionic.CATALOG_V3_PERMEABILITIES,
            ionic.CATALOG_V4_PERMEABILITIES,
        )
    ] == [35, 39, 40, 53]
    assert len(LAWS) == 13 and len(DYNAMIC) == 5
    assert set(ionic.CATALOG_V4_PERMEABILITIES) - set(ionic.CATALOG_V3_PERMEABILITIES) == set(LAWS)


@pytest.mark.parametrize("law", LAWS)
def test_initial_gate_cardinality_is_explicit(law):
    raw = case("tissue")
    ch = next(v for v in raw["model"]["channels"] if v["kinetic_law"] == law)
    ch["initial_gate"] = [0.31, 0.0] if law in DYNAMIC else [0.0]
    with pytest.raises(ValueError, match="zero or one"):
        ionic.bind(raw)


@pytest.mark.parametrize("law", LAWS)
@pytest.mark.parametrize("blocked", [False, True])
def test_absent_packed_gate_slots_reject(law, blocked):
    raw = case("tissue")
    if blocked:
        for group in raw["experiment"]["channel_controls"]:
            group["schedule"] = [dict(time=0.0, availability=0.0)]
    c = ionic.bind(raw)
    d = ionic.unpack(c, ionic.initial(c))
    j = next(j for j, ch in enumerate(raw["model"]["channels"]) if ch["kinetic_law"] == law)
    d["channel_gate"][1 if law in DYNAMIC else 0, j] = 1e-20
    with pytest.raises(ValueError, match="Absent Morris–Lecar"):
        ionic.evaluate(c, ionic.flatten(c, d), 0)


@pytest.mark.parametrize("family", MODELS)
def test_blocked_dynamic_gates_evolve_and_instantaneous_laws_have_no_clock(family):
    raw, module = case(family), MODELS[family][0]
    c = module.bind(raw)
    y = state(family, c, raw, True)
    a, phi0, _ = module.evaluate(c, y, 0)
    blocked = deepcopy(raw)
    for group in blocked["experiment"]["channel_controls"]:
        group["schedule"] = [dict(time=0.0, availability=0.0)]
    b, phi1, proof = module.evaluate(module.bind(blocked), y, 0)
    ra, rb = module.unpack(c, a), module.unpack(c, b)
    np.testing.assert_array_equal(phi0, phi1)
    np.testing.assert_array_equal(ra["channel_gate"], rb["channel_gate"])
    np.testing.assert_array_equal(rb["channel_transferred"], 0)
    dynamic = [j for j, ch in enumerate(ion_model(raw)["channels"]) if ch["kinetic_law"] in DYNAMIC]
    assert len(dynamic) >= 5 and np.all(rb["channel_gate"][0, dynamic] != 0)
    physical_balance(family, c, y, b, phi1, proof)


@pytest.mark.parametrize("name", ["HCN2_ML", "HCN4_ML"])
@pytest.mark.parametrize("fault", ["reverse_order", "extra_calcium"])
def test_ml_hcn_ion_contract_is_ordered_k_na_without_calcium(name, fault):
    raw = case("tissue")
    ch = next(
        v for v in raw["model"]["channels"] if ionic.MORRIS_LECAR_LAWS.get(v["kinetic_law"]) == name
    )
    if fault == "reverse_order":
        ch["permeant_ions"].reverse()
    else:
        ch["permeant_ions"].append(dict(species_id="Ca", relative_permeability=0.0))
    with pytest.raises(ValueError, match="exact ordered"):
        ionic.bind(raw)


@pytest.mark.parametrize("family", MODELS)
def test_previous_40_law_identity_rejects_ml(family):
    raw = case(family)
    ion_model(raw)["id"] = "resolved_tissue@10"
    if family != "tissue":
        raw["model"]["id"] = (
            "resolved_calcium@9" if family == "calcium" else "resolved_calcium_energy@3"
        )
    with pytest.raises(ValueError, match="known channel law"):
        MODELS[family][0].bind(raw)


@pytest.mark.parametrize("family", ["calcium", "energy"])
def test_new_owned_identity_requires_ionic11(family):
    raw = case(family)
    ion_model(raw)["id"] = "resolved_tissue@10"
    with pytest.raises(ValueError, match="versioned"):
        MODELS[family][0].bind(raw)


@pytest.mark.parametrize("family", ["calcium", "energy"])
def test_free_calcium_changes_cak_sensing_but_not_ml_gate_opening(family):
    raw, module = case(family), MODELS[family][0]
    c = module.bind(raw)
    y = module.initial(c)
    a, phi0, _ = module.evaluate(c, y, 0)
    d = module.unpack(c, y.copy())
    store = c["stores"][0]
    d["chemical_amount_increment"][
        0, [store.ids.index(v) for v in ("Ca", "B", "CaB")], store.cy
    ] += 1e-4 * np.array([-1, -1, 1])
    changed = module.flatten(c, d)
    b, phi1, proof = module.evaluate(c, changed, 0)
    ra, rb = module.unpack(c, a), module.unpack(c, b)
    changed_sensor = False
    for j, (ch, (owner, _)) in enumerate(
        zip(ion_model(raw)["channels"], owner_routes(raw), strict=True)
    ):
        law = ch["kinetic_law"]
        if law in LAWS:
            np.testing.assert_allclose(
                ra["channel_gate"][:, j], rb["channel_gate"][:, j], rtol=3e-13, atol=1e-12
            )
            if all(
                species != "Ca" for species, _ in ml.PERMEABILITIES[ionic.MORRIS_LECAR_LAWS[law]]
            ):
                np.testing.assert_allclose(
                    ra["channel_transferred"][:, j],
                    rb["channel_transferred"][:, j],
                    rtol=3e-13,
                    atol=3e-16,
                )
        elif law == ionic.CALCIUM_ACTIVATED_LAW and owner == 0:
            assert np.any(ra["channel_transferred"][:, j] != rb["channel_transferred"][:, j])
            changed_sensor = True
    assert changed_sensor
    physical_balance(family, c, changed, b, phi1, proof)
    ml_routes(family, c, raw, changed, b, phi1, 0)
    sensor_routes(family, c, raw, changed, b, phi1, 0)


def test_live_atp_feedback_does_not_become_a_direct_ml_drive():
    raw = case("energy")
    c = energy.bind(raw)
    y = energy.initial(c)
    a, phi0, _ = energy.evaluate(c, y, 0)
    d = energy.unpack(c, y.copy())
    d["energy_amount_increment_fmol"][:, 0] = (
        0.2 * c["energy_initial"][:, 0].min() * np.array([-1, 1, 1])
    )
    changed = energy.flatten(c, d)
    b, phi1, proof = energy.evaluate(c, changed, 0)
    ra, rb = energy.unpack(c, a), energy.unpack(c, b)
    np.testing.assert_array_equal(phi0, phi1)
    np.testing.assert_array_equal(ra["channel_gate"], rb["channel_gate"])
    np.testing.assert_array_equal(ra["channel_transferred"], rb["channel_transferred"])
    assert np.any(ra["pump_cycles"] != rb["pump_cycles"])
    assert np.any(ra["plasma_pump_cycles"] != rb["plasma_pump_cycles"])
    assert np.any(ra["er_pump_transferred"] != rb["er_pump_transferred"])
    physical_balance("energy", c, changed, b, phi1, proof)


@pytest.mark.parametrize("family", MODELS)
@pytest.mark.parametrize("old_count", [35, 39, 40])
@pytest.mark.parametrize("changed", [False, True])
def test_old_catalogs_are_bitwise_unchanged(family, old_count, changed):
    root = Path(os.environ["CELLS_MORRIS_LECAR_BASELINE"])
    old_i = frozen_module("pre_ml_kinetic", root / "validation/tissue/surface_kinetic_reference.py")
    old_c = frozen_module("pre_ml_calcium", root / "validation/tissue/surface_calcium_reference.py")
    old_c.kinetic = old_i
    old_e = frozen_module(
        "pre_ml_energy", root / "validation/tissue/surface_calcium_energy_reference.py"
    )
    old_e.calcium = old_c
    previous = {"tissue": old_i, "calcium": old_c, "energy": old_e}[family]
    raw = case(family)
    allowed = {
        35: ionic.CATALOG_PERMEABILITIES,
        39: ionic.CATALOG_V2_PERMEABILITIES,
        40: ionic.CATALOG_V3_PERMEABILITIES,
    }[old_count]
    m = ion_model(raw)
    m["channels"] = [v for v in m["channels"] if v["kinetic_law"] in allowed]
    names = {v["id"] for v in m["channels"]}
    raw["experiment"]["channel_controls"] = [
        v for v in raw["experiment"]["channel_controls"] if v["channel_id"] in names
    ]
    old_raw = deepcopy(raw)
    ion_model(old_raw)["id"] = {
        35: "resolved_tissue@8",
        39: "resolved_tissue@9",
        40: "resolved_tissue@10",
    }[old_count]
    if family != "tissue":
        old_raw["model"]["id"] = (
            {35: "resolved_calcium@7", 39: "resolved_calcium@8", 40: "resolved_calcium@9"}
            if family == "calcium"
            else {
                35: "resolved_calcium_energy@1",
                39: "resolved_calcium_energy@2",
                40: "resolved_calcium_energy@3",
            }
        )[old_count]
    module = MODELS[family][0]
    c, old = module.bind(raw), previous.bind(old_raw)
    np.testing.assert_array_equal(module.initial(c), previous.initial(old))
    y = state(family, c, raw, changed)
    actual, expected = module.evaluate(c, y, 0), previous.evaluate(old, y, 0)
    np.testing.assert_array_equal(actual[0], expected[0])
    np.testing.assert_array_equal(actual[1], expected[1])
    evidence(
        f"old{old_count}-exact-{family}-{changed}",
        dict(
            state=y.tolist(),
            derivative=actual[0].tolist(),
            potential_V=actual[1].tolist(),
            exact_derivative=True,
            exact_potential=True,
        ),
    )


def test_short_full_energy_refinement_keeps_absent_states_and_event_semantics():
    raw = case("energy")
    e = raw["experiment"]
    e.update(end_time=2.5e-6, observation_times=[0.0, 0.8e-6, 1.4e-6, 1.9e-6, 2.5e-6])
    for name, groups in e.items():
        if name.endswith("_controls"):
            for group in groups:
                key = "schedule" if "schedule" in group else "controls"
                group[key] = [v for v in group[key] if v["time"] == 0]
    for law, event in ((LAWS[0], 0.8e-6), (LAWS[5], 1.4e-6)):
        ch = next(v["id"] for v in ion_model(raw)["channels"] if v["kinetic_law"] == law)
        next(g for g in e["channel_controls"] if g["channel_id"] == ch)["schedule"].append(
            dict(time=event, availability=0.0)
        )
    e["regeneration_controls"][0]["schedule"].append(dict(time=1.9e-6, availability=0.0))
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
            scope="2.5-us complete-state coupling and event wiring; no native BE or settling claim",
        ),
    )
    for name in c["shapes"]:
        a, b = (energy.unpack(c, result["state"])[name] for result in (ordinary, refined))
        np.testing.assert_allclose(
            a, b, rtol=3e-9, atol=3e-28 if name.endswith("_C") else 3e-13, err_msg=name
        )
    for result in (ordinary, refined):
        gates = energy.unpack(c, result["state"])["channel_gate"]
        for j, ch in enumerate(ion_model(raw)["channels"]):
            law = ch["kinetic_law"]
            if law in LAWS:
                np.testing.assert_array_equal(gates[:, 1 if law in DYNAMIC else 0 :, j], 0)
    assert ordinary["event_times"] == [0.0, 0.8e-6, 1.4e-6, 1.9e-6, 2.5e-6]
    for time, y in zip(ordinary["times"], ordinary["state"], strict=True):
        slope, phi, proof = energy.evaluate(c, y, time)
        physical_balance("energy", c, y, slope, phi, proof)
        ml_routes("energy", c, raw, y, slope, phi, time)
        sensor_routes("energy", c, raw, y, slope, phi, time)


def test_no_production_imports():
    assert not any(name == "cells" or name.startswith(("cells.", "jax")) for name in sys.modules)
