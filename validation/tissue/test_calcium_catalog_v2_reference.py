"""Independent 39-law wiring and owned calcium/fuel coupling, not settling.

Only serialized fixture inputs enter this worker. The unchanged scalar calcium
extras supply the new gates; component clock qualification is separate.
"""

import importlib.util
import json
import os
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from validation.channels import calcium_catalog_extra_reference as extra
from validation.tissue import surface_calcium_energy_reference as energy
from validation.tissue import surface_calcium_reference as calcium
from validation.tissue import surface_kinetic_reference as ionic
from validation.tissue.test_calcium_energy_reference import accounting, ownership_checks

MODELS = {
    "tissue": (ionic, "resolved_tissue@9", 19),
    "calcium": (calcium, "resolved_calcium@8", 34),
    "energy": (energy, "resolved_calcium_energy@2", 38),
}
EXTRAS = tuple(ionic.ADDED_CALCIUM_LAWS)
pytestmark = pytest.mark.skipif(
    "CELLS_CALCIUM_CATALOG_V2_INPUTS" not in os.environ,
    reason="Require frozen serialized inputs, never production fixture imports",
)


def inputs():
    directory = os.environ.get("CELLS_CALCIUM_CATALOG_V2_INPUTS")
    if not directory:
        return {}
    root = Path(directory)
    values = {}
    for path in sorted(root.rglob("*.json")):
        value = json.loads(path.read_text())
        if isinstance(value, dict) and value.get("model", {}).get("id") in {
            row[1] for row in MODELS.values()
        }:
            values[str(path.relative_to(root).with_suffix(""))] = value
    return values


def case(family, arm="open"):
    candidates = {
        name: raw for name, raw in inputs().items() if raw["model"]["id"] == MODELS[family][1]
    }
    return deepcopy(next(raw for name, raw in candidates.items() if name.endswith(arm)))


def family_of(raw):
    return next(
        name for name, (_, identifier, _) in MODELS.items() if raw["model"]["id"] == identifier
    )


def ion_model(raw):
    return (
        raw["model"] if raw["model"]["id"].startswith("resolved_tissue") else raw["model"]["ionic"]
    )


def evidence(name, value):
    if directory := os.environ.get("CELLS_REFERENCE_EVIDENCE"):
        path = Path(directory) / (name.replace("/", "-") + ".json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def state(family, c, changed):
    module = MODELS[family][0]
    d = module.unpack(c, module.initial(c))
    if changed:
        d["channel_gate"][:] = np.array([[0.31], [0.63]])
        if family == "tissue":
            for s, row in enumerate(c["raw"]["model"]["species"]):
                if row["id"] in ("K", "Cl"):
                    d["amount_increment"][s, 0] += 0.01
                    d["extracellular_amount_increment"][s, 0] -= 0.01
        else:
            for i, store in enumerate(c["stores"]):
                d["chemical_amount_increment"][
                    i, [store.ids.index(v) for v in ("Ca", "B", "CaB")], store.cy
                ] += 1e-4 * np.array([-1, -1, 1])
        if family == "energy":
            for i in range(len(c["vi"])):
                extent = 0.1 * c["energy_initial"][:, i].min()
                d["energy_amount_increment_fmol"][:, i] += extent * np.array([-1, 1, 1])
    return module.flatten(c, d)


def physical_balance(family, c, y, slope, phi, proof):
    if family == "energy":
        return accounting(c, y, slope, proof)
    if family == "calcium":
        assert abs(proof["physical_energy_balance_pJ_s"]) < 3e-10
        return ownership_checks(c, slope)
    d, rate = ionic.unpack(c, y), ionic.unpack(c, slope)
    ci = (c["ai"] + d["amount_increment"]) / c["vi"]
    co = (c["ao"] + d["extracellular_amount_increment"]) / c["vo"]
    n, z = len(c["vi"]), np.asarray(c["layout"]["valence"])
    mu_i = ionic.R * 298.15 * np.log(ci) + ionic.F * z * phi[:n]
    mu_o = ionic.R * 298.15 * np.log(co) + ionic.F * z * phi[n:]
    chemical_capacitor = 1e-3 * (
        np.sum(mu_i * rate["amount_increment"])
        + np.sum(mu_o * rate["extracellular_amount_increment"])
    )
    heat = sum(v.sum() for k, v in rate.items() if k.endswith("dissipated_energy_pJ"))
    work = sum(
        rate[k].sum() for k in ("metabolic_work_pJ", "reservoir_work_pJ", "electrode_work_pJ")
    )
    material = (
        rate["amount_increment"].sum(axis=1)
        + rate["extracellular_amount_increment"].sum(axis=1)
        - rate["reservoir_supplied"].sum(axis=1)
    )
    np.testing.assert_allclose(material, 0, rtol=0, atol=3e-13)
    assert abs(chemical_capacitor + heat - work) < 3e-10
    return dict(
        material_residual_fmol_s=material.tolist(),
        energy_residual_pJ_s=float(chemical_capacitor + heat - work),
    )


def check_new_routes(family, c, y, slope, phi, time):
    d, rate = ionic.unpack(c, y), ionic.unpack(c, slope)
    m = c["calcium"]["raw"]["model"] if family == "energy" else c["raw"]["model"]
    n, ca = len(c["vi"]), [s["id"] for s in m["species"]].index("Ca")
    patches = {p["id"]: j for j, p in enumerate(m["membranes"])}
    observations = []
    for k, channel in enumerate(m["channels"]):
        if channel["kinetic_law"] not in EXTRAS:
            continue
        j = patches[channel["membrane_id"]]
        i, o = c["layout"]["membrane_cell"][j], c["layout"]["membrane_outside"][j]
        voltage = phi[i] - phi[n + o]
        family_name = ionic.ADDED_CALCIUM_LAWS[channel["kinetic_law"]]
        expected_gate = extra.rhs(d["channel_gate"][:, k], float(voltage), family_name)
        np.testing.assert_allclose(
            rate["channel_gate"][:, k], expected_gate, rtol=4e-15, atol=2e-12
        )
        if family == "tissue":
            ci = (c["ai"] + d["amount_increment"])[ca, i] / c["vi"][i]
        else:
            store = c["stores"][i]
            ci = (store.n0 + d["chemical_amount_increment"][i])[store.ca, store.cy] / store.volume[
                store.cy
            ]
        co = (c["ao"] + d["extracellular_amount_increment"])[ca, o] / c["vo"][o]
        opening = extra.opening(d["channel_gate"][:, k], family_name)
        base_context = c["calcium"] if family == "energy" else c
        level = ionic.availability(base_context, "channel", channel["id"], time)
        flux = ionic.transport.decimal_flux(
            ci,
            co,
            voltage,
            2,
            298.15,
            m["membranes"][j]["area_m2"],
            channel["max_permeability_m_per_s"] * channel["abundance"],
            1.0,
            opening * level,
            {"F": ionic.F, "R": ionic.R},
        )
        np.testing.assert_array_equal(np.delete(rate["channel_transferred"][:, k], ca), 0)
        np.testing.assert_allclose(rate["channel_transferred"][ca, k], flux, rtol=3e-15, atol=3e-18)
        assert rate["channel_dissipated_energy_pJ"][ca, k] >= 0
        observations.append(
            dict(
                channel_id=channel["id"],
                owner=i,
                law=channel["kinetic_law"],
                voltage_V=float(voltage),
                free_calcium_mM=float(ci),
                flux_fmol_s=float(flux),
                gate_rate_per_s=rate["channel_gate"][:, k].tolist(),
            )
        )
    return observations


def test_old_registry_stays_35_and_new_registry_is_39():
    assert len(ionic.CATALOG_PERMEABILITIES) == 35
    assert len(ionic.CATALOG_V2_PERMEABILITIES) == 39
    assert set(ionic.CATALOG_V2_PERMEABILITIES) - set(ionic.CATALOG_PERMEABILITIES) == set(EXTRAS)
    assert all(ionic.CATALOG_V2_PERMEABILITIES[law] == (("Ca", 1.0),) for law in EXTRAS)


@pytest.mark.parametrize("name", tuple(inputs()) or (None,))
@pytest.mark.parametrize("changed", [False, True])
def test_complete_derivatives_and_owned_routes(name, changed):
    raw = inputs()[name]
    family = family_of(raw)
    module, _, count = MODELS[family]
    c = module.bind(raw)
    assert len(c["shapes"]) == count
    y = state(family, c, changed)
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
    saved["new_routes"] = check_new_routes(family, c, y, slope, phi, 0)
    if name.endswith("open"):
        assert {ch["kinetic_law"] for ch in ion_model(raw)["channels"]} == set(
            ionic.CATALOG_V2_PERMEABILITIES
        )
    evidence(f"stage-{name}-{changed}", saved)


@pytest.mark.parametrize("family", MODELS)
def test_new_laws_are_rejected_by_old_model_identity(family):
    raw = case(family)
    if family == "tissue":
        raw["model"]["id"] = "resolved_tissue@8"
    else:
        raw["model"]["id"] = (
            "resolved_calcium@7" if family == "calcium" else "resolved_calcium_energy@1"
        )
        raw["model"]["ionic"]["id"] = "resolved_tissue@8"
    with pytest.raises(ValueError, match="known channel law"):
        MODELS[family][0].bind(raw)


@pytest.mark.parametrize("family", ["calcium", "energy"])
def test_new_outer_identity_requires_new_ionic_identity(family):
    raw = case(family)
    raw["model"]["ionic"]["id"] = "resolved_tissue@8"
    with pytest.raises(ValueError, match="39-law|versioned"):
        MODELS[family][0].bind(raw)


@pytest.mark.parametrize("law", EXTRAS)
def test_extra_ion_routes_are_exact(law):
    raw = case("tissue")
    ch = next(v for v in raw["model"]["channels"] if v["kinetic_law"] == law)
    ch["permeant_ions"][0]["relative_permeability"] = 0.5
    with pytest.raises(ValueError, match="exact ordered"):
        ionic.bind(raw)


@pytest.mark.parametrize("family", MODELS)
def test_blocked_caleak_keeps_one_second_clock_and_strict_gate(family):
    raw = case(family)
    for group in raw["experiment"]["channel_controls"]:
        group["schedule"] = [dict(time=0.0, availability=0.0)]
    module = MODELS[family][0]
    c = module.bind(raw)
    d = module.unpack(c, module.initial(c))
    d["channel_gate"][:] = np.array([[0.21], [0.67]])
    y = module.flatten(c, d)
    slope, phi, proof = module.evaluate(c, y, 0)
    rates = module.unpack(c, slope)
    leak = next(
        j
        for j, ch in enumerate(ion_model(raw)["channels"])
        if ch["kinetic_law"] == "betse_caleak_always_open@1"
    )
    np.testing.assert_array_equal(rates["channel_transferred"], 0)
    np.testing.assert_array_equal(rates["channel_gate"][:, leak], 1 - d["channel_gate"][:, leak])
    physical_balance(family, c, y, slope, phi, proof)
    d["channel_gate"][0, leak] = -1e-6
    with pytest.raises(ValueError, match="strict gates"):
        module.evaluate(c, module.flatten(c, d), 0)


@pytest.mark.parametrize("family", ["calcium", "energy"])
@pytest.mark.parametrize("owner", [0, 1])
def test_new_routes_read_owned_free_calcium_not_whole_cell_total(family, owner):
    raw, module = case(family), MODELS[family][0]
    c = module.bind(raw)
    y = module.initial(c)
    a, phi0, _ = module.evaluate(c, y, 0)
    d = module.unpack(c, y.copy())
    store = c["stores"][owner]
    d["chemical_amount_increment"][
        owner, [store.ids.index(v) for v in ("Ca", "B", "CaB")], store.cy
    ] += 1e-4 * np.array([-1, -1, 1])
    changed = module.flatten(c, d)
    b, phi1, proof = module.evaluate(c, changed, 0)
    before, after = module.unpack(c, a), module.unpack(c, b)
    i = np.asarray(c["layout"]["membrane_cell"])
    o = len(c["vi"]) + np.asarray(c["layout"]["membrane_outside"])
    np.testing.assert_allclose(phi0[i] - phi0[o], phi1[i] - phi1[o], rtol=0, atol=3e-14)
    np.testing.assert_array_equal(d["amount_increment"], 0)
    channels, patches = (
        ion_model(raw)["channels"],
        {p["id"]: j for j, p in enumerate(ion_model(raw)["membranes"])},
    )
    affected = []
    for k, ch in enumerate(channels):
        if ch["kinetic_law"] not in EXTRAS:
            continue
        current_owner = i[patches[ch["membrane_id"]]]
        if current_owner == owner:
            assert np.any(before["channel_transferred"][:, k] != after["channel_transferred"][:, k])
            affected.append(ch["id"])
        else:
            np.testing.assert_allclose(
                before["channel_transferred"][:, k],
                after["channel_transferred"][:, k],
                rtol=3e-13,
                atol=3e-16,
            )
    assert affected
    physical_balance(family, c, changed, b, phi1, proof)
    check_new_routes(family, c, changed, b, phi1, 0)


def test_current_pool_changes_all_pumps_but_not_instantaneous_channel_gates():
    c = energy.bind(case("energy"))
    y = energy.initial(c)
    a, phi0, _ = energy.evaluate(c, y, 0)
    d = energy.unpack(c, y.copy())
    d["energy_amount_increment_fmol"][:, 0] = (
        0.2 * c["energy_initial"][:, 0].min() * np.array([-1, 1, 1])
    )
    changed = energy.flatten(c, d)
    b, phi1, proof = energy.evaluate(c, changed, 0)
    before, after = energy.unpack(c, a), energy.unpack(c, b)
    np.testing.assert_array_equal(phi0, phi1)
    for field in (
        "channel_gate",
        "channel_transferred",
        "calcium_channel_transferred",
        "plasma_exchange_cycles",
    ):
        np.testing.assert_array_equal(before[field], after[field])
    for field, owners in (
        ("pump_cycles", c["patch_owners"]),
        ("plasma_pump_cycles", c["plasma_owners"]),
        ("er_pump_transferred", list(range(len(c["vi"])))),
    ):
        mask = np.asarray(owners) == 0
        assert np.any(before[field][mask] != after[field][mask])
        np.testing.assert_array_equal(before[field][~mask], after[field][~mask])
    accounting(c, changed, b, proof)


def test_cav_g_regularized_limit_in_complete_physical_stage():
    raw = case("tissue")
    c = ionic.bind(raw)
    y = ionic.initial(c)
    _, phi, _ = ionic.evaluate(c, y, 0)
    m, p = raw["model"], c["layout"]
    ch = next(v for v in m["channels"] if v["kinetic_law"] == "betse_cav_g_m2h_regularized@1")
    j = [v["id"] for v in m["membranes"]].index(ch["membrane_id"])
    n = len(c["vi"])
    i, o = p["membrane_cell"][j], n + p["membrane_outside"][j]
    phi[i] = phi[o] - 0.027
    capacitance = ionic.electrical.topology(ionic.base.stage(c, y, 0))[0]
    charges = capacitance @ phi
    for row, charge in zip(m["cells"] + m["extracellular"], charges, strict=True):
        row["initial_charge_C"] = float(charge)
    c = ionic.bind(raw)
    y = state("tissue", c, True)
    slope, phi, proof = ionic.evaluate(c, y, 0)
    np.testing.assert_allclose(phi[i] - phi[o], -0.027, rtol=0, atol=3e-14)
    observed = check_new_routes("tissue", c, y, slope, phi, 0)
    physical_balance("tissue", c, y, slope, phi, proof)
    evidence(
        "cav-g-regularized-stage",
        dict(
            inputs=raw,
            state=y.tolist(),
            derivative=slope.tolist(),
            potential_V=phi.tolist(),
            routes=observed,
            scope=(
                "Complete field/gate stage near the exact -27-mV removable singularity; "
                "component clock checks are separate"
            ),
        ),
    )


def frozen_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("family", MODELS)
@pytest.mark.parametrize("changed", [False, True])
def test_old_35_law_behavior_is_bitwise_unchanged_against_frozen_reference(family, changed):
    root = Path(os.environ["CELLS_CALCIUM_CATALOG_V2_BASELINE"])
    old_i = frozen_module("old_kinetic", root / "validation/tissue/surface_kinetic_reference.py")
    old_c = frozen_module("old_calcium", root / "validation/tissue/surface_calcium_reference.py")
    old_c.kinetic = old_i
    old_e = frozen_module(
        "old_energy", root / "validation/tissue/surface_calcium_energy_reference.py"
    )
    old_e.calcium = old_c
    old = {"tissue": old_i, "calcium": old_c, "energy": old_e}[family]
    module = MODELS[family][0]
    raw = case(family)
    m = ion_model(raw)
    m["channels"] = [v for v in m["channels"] if v["kinetic_law"] not in EXTRAS]
    names = {v["id"] for v in m["channels"]}
    raw["experiment"]["channel_controls"] = [
        v for v in raw["experiment"]["channel_controls"] if v["channel_id"] in names
    ]
    previous = deepcopy(raw)
    ion_model(previous)["id"] = "resolved_tissue@8"
    if family != "tissue":
        previous["model"]["id"] = (
            "resolved_calcium@7" if family == "calcium" else "resolved_calcium_energy@1"
        )
    c, baseline = module.bind(raw), old.bind(previous)
    np.testing.assert_array_equal(module.initial(c), old.initial(baseline))
    y = state(family, c, changed)
    actual = module.evaluate(c, y, 0)
    expected = old.evaluate(baseline, y, 0)
    np.testing.assert_array_equal(actual[0], expected[0])
    np.testing.assert_array_equal(actual[1], expected[1])
    evidence(
        f"old35-exact-{family}-{changed}",
        dict(
            state=y.tolist(),
            derivative=actual[0].tolist(),
            potential_V=actual[1].tolist(),
            exact_derivative=True,
            exact_potential=True,
        ),
    )


def test_short_energy_trajectory_refines_with_independent_channel_and_supply_events():
    raw = case("energy")
    e = raw["experiment"]
    e.update(end_time=2.5e-6, observation_times=[0.0, 1.1e-6, 1.7e-6, 2.5e-6])
    for name, groups in e.items():
        if name.endswith("_controls"):
            for group in groups:
                key = "schedule" if "schedule" in group else "controls"
                group[key] = [v for v in group[key] if v["time"] == 0]
    leak = next(
        v["id"]
        for v in ion_model(raw)["channels"]
        if v["kinetic_law"] == "betse_caleak_always_open@1"
    )
    next(g for g in e["channel_controls"] if g["channel_id"] == leak)["schedule"].append(
        dict(time=1.1e-6, availability=0.0)
    )
    e["regeneration_controls"][0]["schedule"].append(dict(time=1.7e-6, availability=0.0))
    c = energy.bind(raw)
    ordinary, tighter = (energy.integrate(raw, refinement=r) for r in (1, 2))
    assert ordinary["event_times"] == [0.0, 1.1e-6, 1.7e-6, 2.5e-6]
    evidence(
        "short-adaptive",
        dict(
            inputs=raw,
            times=ordinary["times"],
            state=ordinary["state"].tolist(),
            refined_state=tighter["state"].tolist(),
            evaluations=[ordinary["evaluations"], tighter["evaluations"]],
            scope="2.5-us coupling and event wiring; no native-clock or settling claim",
        ),
    )
    for name in c["shapes"]:
        a, b = (energy.unpack(c, result["state"])[name] for result in (ordinary, tighter))
        np.testing.assert_allclose(
            a, b, rtol=3e-9, atol=3e-28 if name.endswith("_C") else 3e-13, err_msg=name
        )
    for time, y in zip(ordinary["times"], ordinary["state"], strict=True):
        slope, phi, proof = energy.evaluate(c, y, time)
        accounting(c, y, slope, proof)
        check_new_routes("energy", c, y, slope, phi, time)


def test_no_production_imports():
    assert not any(name == "cells" or name.startswith(("cells.", "jax")) for name in sys.modules)
