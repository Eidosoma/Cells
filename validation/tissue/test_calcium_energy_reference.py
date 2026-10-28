"""Independent finite ATP/calcium coupling, signs and internal energy transfers."""

import json
import math
import os
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from validation.chemistry import finite_energy_reference as chemistry
from validation.tissue import surface_calcium_energy_reference as ref

pytestmark = pytest.mark.skipif(
    "CELLS_CALCIUM_ENERGY_INPUTS" not in os.environ,
    reason="Independent checks require frozen raw finite-energy calcium JSON inputs",
)


def inputs():
    root = Path(os.environ["CELLS_CALCIUM_ENERGY_INPUTS"])
    return {
        p.stem: json.loads(p.read_text())
        for p in sorted(root.glob("*.json"))
        if p.name != "manifest.json"
    }


def case():
    values = inputs()
    return deepcopy(values.get("coupled", values.get("open", next(iter(values.values())))))


def evidence(name, value):
    if directory := os.environ.get("CELLS_REFERENCE_EVIDENCE"):
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        (root / (name + ".json")).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def changed_state(c):
    d = ref.unpack(c, ref.initial(c))
    for i, store in enumerate(c["calcium"]["stores"]):
        extent = 0.1 * float(c["energy_initial"][:, i].min())
        d["energy_amount_increment_fmol"][:, i] = extent * np.array([-1, 1, 1])
        d["chemical_amount_increment"][
            i, [store.ids.index(k) for k in ("Ca", "B", "CaB")], store.cy
        ] += 1e-4 * np.array([-1, -1, 1])
    d["channel_gate"][:] = np.array([[0.31], [0.63]])
    return ref.flatten(c, d)


def ownership_checks(c, derivative):
    """Independent route/reaction accounting with explicit cancellation budgets.

    Unlike the slower maintained-fuel fixture, the reverse finite-pool probe
    has salt rates of order 1e4 fmol/s. Retain its raw residuals and component
    scales instead of treating an absolute tolerance below one ulp as physical.
    """
    d = ref.unpack(c, derivative)
    ions = [s["id"] for s in c["raw"]["model"]["species"]]
    terms = {
        name: []
        for store in c["stores"]
        for species in store.species
        for name in species["moieties"]
    }
    max_ledger = 0.0
    for i, store in enumerate(c["stores"]):
        expected = np.zeros_like(store.n0)
        for j, reaction in enumerate(store.reactions):
            owner = store.owners.index(reaction["compartment"])
            for s, name in enumerate(store.ids):
                nu = reaction["products"].get(name, 0) - reaction["reactants"].get(name, 0)
                expected[s, owner] += nu * d["reaction_extent"][i, j]
        exchange = d["er_passive_transferred"][i].copy()
        exchange[store.ca] += d["er_pump_transferred"][i, 0] + d["er_release_transferred"][i, 0]
        expected[:, store.cy] -= exchange
        expected[:, store.er] += exchange
        for s, name in enumerate(ions):
            expected[store.ids.index(name), store.cy] += d["amount_increment"][s, i]
        np.testing.assert_allclose(
            expected, d["chemical_amount_increment"][i], rtol=3e-14, atol=3e-13
        )
        max_ledger = max(
            max_ledger, float(np.max(np.abs(expected - d["chemical_amount_increment"][i])))
        )
        chemical_charge = math.fsum((store.z[:, None] * d["chemical_amount_increment"][i]).ravel())
        ionic_charge = math.fsum(
            np.asarray(c["layout"]["valence"])[:, 0] * d["amount_increment"][:, i]
        )
        np.testing.assert_allclose(chemical_charge, ionic_charge, rtol=3e-13, atol=3e-13)
        for s, species in enumerate(store.species):
            for name, coefficient in species["moieties"].items():
                terms[name].extend(coefficient * d["chemical_amount_increment"][i, s])
    for s, name in enumerate(ions):
        terms[name].extend(d["extracellular_amount_increment"][s])
    residual = {name: math.fsum(values) for name, values in terms.items()}
    scale = {name: math.fsum(map(abs, values)) for name, values in terms.items()}
    budget = {name: 3e-13 + 8 * np.finfo(float).eps * value for name, value in scale.items()}
    assert all(abs(residual[name]) <= budget[name] for name in terms)
    assert (
        min(float(v.min(initial=0)) for k, v in d.items() if k.endswith("_dissipated_energy_pJ"))
        >= -3e-14
    )
    return dict(
        max_chemical_ledger_residual_fmol_s=max_ledger,
        global_moiety_rate_residual_fmol_s=residual,
        global_moiety_component_scale_fmol_s=scale,
        global_moiety_tolerance_fmol_s=budget,
    )


def accounting(c, y, slope, proof):
    d, rate = ref.unpack(c, y), ref.unpack(c, slope)
    demand, work, supply = (np.zeros(len(c["cell_ids"])) for _ in range(3))
    for j, i in enumerate(c["patch_owners"]):
        demand[i] += rate["pump_cycles"][j]
        work[i] += rate["metabolic_work_pJ"][j]
    for j, i in enumerate(c["plasma_owners"]):
        demand[i] += rate["plasma_pump_cycles"][j]
        work[i] += rate["plasma_metabolic_work_pJ"][j]
    for i in range(len(demand)):
        demand[i] += rate["er_pump_transferred"][i, 0]
        work[i] += rate["er_metabolic_work_pJ"][i]
    for j, port in enumerate(c["raw"]["model"]["regeneration_ports"]):
        i = c["cell_ids"].index(c["pools"][port["pool_id"]]["cell_id"])
        supply[i] += rate["regeneration_cycles_fmol"][j]
    expected = np.array([-1, 1, 1])[:, None] * (demand - supply)
    np.testing.assert_allclose(
        rate["energy_amount_increment_fmol"], expected, rtol=3e-14, atol=3e-15
    )
    pool = c["energy_initial"] + d["energy_amount_increment_fmol"]
    energy_scale = np.abs(work)
    for i in range(len(demand)):
        values = chemistry.thermodynamics(
            pool[:, i], c["energy_volumes"][i], 298.15, c["energy_delta_g0"][i]
        )
        g = values["hydrolysis_free_energy_J_mol"]
        energy_scale[i] += np.abs(
            1e-3
            * np.asarray(values["chemical_potential_J_mol"])
            * rate["energy_amount_increment_fmol"][:, i]
        ).sum()
        np.testing.assert_allclose(work[i], -1e-3 * g * demand[i], rtol=3e-14, atol=3e-14)
    for j, port in enumerate(c["raw"]["model"]["regeneration_ports"]):
        i = c["cell_ids"].index(c["pools"][port["pool_id"]]["cell_id"])
        energy_scale[i] += abs(rate["regeneration_dissipated_energy_pJ"][j]) + abs(
            rate["regeneration_supplied_work_pJ"][j]
        )
    np.testing.assert_allclose(proof["adenylate_rate_fmol_s"], 0, rtol=0, atol=3e-15)
    np.testing.assert_allclose(proof["phosphorus_rate_fmol_s"], 0, rtol=0, atol=3e-15)
    # Strong reversed pumps cancel powers of order 1e5 pJ/s. Preserve the raw
    # residual and the ordinary absolute budget; account separately for binary64
    # roundoff in these few products and sums, using actual component magnitudes.
    energy_budget = 3e-12 + 8 * np.finfo(float).eps * energy_scale
    assert np.all(np.abs(proof["pool_internal_transfer_balance_pJ_s"]) <= energy_budget)
    assert abs(proof["physical_energy_balance_pJ_s"]) < 3e-10
    assert rate["regeneration_dissipated_energy_pJ"].min(initial=0) >= 0
    physical = ownership_checks(c["calcium"], ref.flatten(c["calcium"], rate))
    return dict(
        pump_demand_fmol_s=demand.tolist(),
        regeneration_fmol_s=supply.tolist(),
        internal_work_pJ_s=work.tolist(),
        pool_energy_component_scale_pJ_s=energy_scale.tolist(),
        pool_energy_tolerance_pJ_s=energy_budget.tolist(),
        physical_ownership=physical,
    )


@pytest.mark.parametrize("changed", [False, True])
def test_all_frozen_cases_retain_full_chemical_and_pool_accounting(changed):
    for name, raw in inputs().items():
        c = ref.bind(raw)
        assert len(c["shapes"]) == 38 and len(c["calcium"]["shapes"]) == 34
        assert tuple(c["shapes"])[-4:] == ref.ENERGY_FIELDS
        y = changed_state(c) if changed else ref.initial(c)
        slope, phi, proof = ref.evaluate(c, y, 0)
        evidence(
            f"stage-{name}-{changed}",
            dict(
                status="captured",
                inputs=raw,
                state=y.tolist(),
                slope=slope.tolist(),
                potential_V=phi.tolist(),
                proof=proof,
            ),
        )
        checks = accounting(c, y, slope, proof)
        evidence(
            f"stage-{name}-{changed}",
            dict(
                inputs=raw,
                state=y.tolist(),
                slope=slope.tolist(),
                potential_V=phi.tolist(),
                proof=proof,
                checks=checks,
            ),
        )


def test_live_owner_pool_changes_all_three_pump_families_without_charging_membranes():
    c = ref.bind(case())
    y = ref.initial(c)
    baseline, phi0, _ = ref.evaluate(c, y, 0)
    d = ref.unpack(c, y.copy())
    extent = 0.2 * float(c["energy_initial"][:, 0].min())
    d["energy_amount_increment_fmol"][:, 0] = extent * np.array([-1, 1, 1])
    after, phi1, proof = ref.evaluate(c, ref.flatten(c, d), 0)
    a, b = ref.unpack(c, baseline), ref.unpack(c, after)
    np.testing.assert_array_equal(phi0, phi1)
    for name, owners in (
        ("pump_cycles", c["patch_owners"]),
        ("plasma_pump_cycles", c["plasma_owners"]),
        ("er_pump_transferred", list(range(len(c["cell_ids"])))),
    ):
        owners = np.asarray(owners)
        assert np.any(a[name][owners == 0] != b[name][owners == 0])
        np.testing.assert_array_equal(a[name][owners != 0], b[name][owners != 0])
    for name in (
        "plasma_exchange_cycles",
        "channel_transferred",
        "channel_gate",
        "calcium_channel_transferred",
    ):
        np.testing.assert_array_equal(a[name], b[name])
    accounting(c, ref.flatten(c, d), after, proof)
    np.testing.assert_array_equal(
        c["calcium"]["full"]["model"]["stores"][0]["model"]["membrane"]["pump"]["atp_mM"],
        c["energy_initial"][0, 0] / c["energy_volumes"][0],
    )


def test_incorrect_millimolar_standard_state_is_visible_in_energy_balance(monkeypatch):
    original = ref._legacy_calcium_pump

    def unconverted(pump, concentration, delta, temperature, er):
        result = original(pump, concentration, delta, temperature, er)
        result["delta_g0_J_per_mol"] = float(delta)
        return result

    monkeypatch.setattr(ref, "_legacy_calcium_pump", unconverted)
    c = ref.bind(case())
    _, _, proof = ref.evaluate(c, ref.initial(c), 0)
    assert abs(proof["physical_energy_balance_pJ_s"]) > 1e-5
    assert max(map(abs, proof["pool_internal_transfer_balance_pJ_s"])) > 1e-5
    evidence("negative-control-standard-state", dict(expected_nonzero=True, proof=proof))


def isolated_pump(family):
    raw = case()
    m = raw["model"]
    for patch in m["ionic"]["membranes"]:
        if patch["pump"] is not None:
            patch["pump"]["capacity_fmol_per_s"] = 0.0
    for route in m["plasma_transport"]["membranes"]:
        if route["pump"] is not None:
            route["pump"]["capacity_fmol_per_s"] = 0.0
    for store in m["stores"]:
        if store["model"]["membrane"]["pump"] is not None:
            store["model"]["membrane"]["pump"]["capacity_fmol_per_s"] = 0.0
    for group in raw["experiment"]["regeneration_controls"]:
        group["schedule"] = [dict(time=0.0, availability=0.0)]
    if family == "nak":
        m["ionic"]["membranes"][0]["pump"]["capacity_fmol_per_s"] = 0.02
    elif family == "pmca":
        m["plasma_transport"]["membranes"][0]["pump"]["capacity_fmol_per_s"] = 0.02
    elif family == "er":
        m["stores"][0]["model"]["membrane"]["pump"]["capacity_fmol_per_s"] = 0.02
    return raw


@pytest.mark.parametrize("family", ["nak", "pmca", "er"])
@pytest.mark.parametrize("direction", [-1, 0, 1])
def test_forward_stall_and_reverse_use_signed_one_atp_cycles(family, direction):
    raw = isolated_pump(family)
    c = ref.bind(raw)
    _, phi, _ = ref.evaluate(c, ref.initial(c), 0)
    store = c["calcium"]["stores"][0]
    rt = ref.R * 298.15
    ion = raw["model"]["ionic"]
    ions = [v["id"] for v in ion["species"]]
    patch = ion["membranes"][0]
    outside = [v["id"] for v in ion["extracellular"]].index(patch["outside"])
    co = c["ao"][:, outside] / c["vo"][outside]
    ci = store.n0[:, store.cy] / store.volume[store.cy]
    vm = phi[0] - phi[len(c["vi"]) + outside]
    if family == "nak":
        mu_na = rt * np.log(ci[store.ids.index("Na")] / co[ions.index("Na")]) + ref.F * vm
        mu_k = rt * np.log(ci[store.ids.index("K")] / co[ions.index("K")]) + ref.F * vm
        transport = -3 * mu_na + 2 * mu_k
    elif family == "pmca":
        transport = rt * np.log(co[ions.index("Ca")] / ci[store.ca]) - 2 * ref.F * vm
    else:
        transport = (
            rt * np.log((store.n0[store.ca, store.er] / store.volume[store.er]) / ci[store.ca])
            + 2 * ref.F * store.membrane["initial_voltage_V"]
        )
    concentration = c["energy_initial"][:, 0] / c["energy_volumes"][0]
    quotient = concentration[1] * concentration[2] / (1000 * concentration[0])
    pool = next(p for p in raw["model"]["energy_pools"] if p["cell_id"] == c["cell_ids"][0])
    # Positive direction denotes hydrolysis/forward transport: negative affinity.
    pool["delta_g0_J_per_mol"] = float(
        -transport - rt * np.log(quotient) - direction * rt * np.log(2)
    )
    tuned = ref.bind(raw)
    y = ref.initial(tuned)
    slope, _, proof = ref.evaluate(tuned, y, 0)
    d = ref.unpack(tuned, slope)
    cycles = d[
        {"nak": "pump_cycles", "pmca": "plasma_pump_cycles", "er": "er_pump_transferred"}[family]
    ].flat[0]
    if direction == 0:
        assert abs(cycles) < 1e-15
    else:
        assert direction * cycles > 0
        assert direction * d["energy_amount_increment_fmol"][0, 0] < 0
    np.testing.assert_allclose(
        d["energy_amount_increment_fmol"][:, 0],
        np.array([-1, 1, 1]) * cycles,
        rtol=3e-14,
        atol=3e-16,
    )
    accounting(tuned, y, slope, proof)
    evidence(
        f"pump-{family}-{direction}",
        dict(
            inputs=raw,
            cycle_fmol_s=float(cycles),
            pool_rate_fmol_s=d["energy_amount_increment_fmol"].tolist(),
            proof=proof,
        ),
    )


def test_ncx_does_not_consume_the_finite_atp_pool():
    c = ref.bind(isolated_pump(None))
    y = ref.initial(c)
    slope, _, proof = ref.evaluate(c, y, 0)
    d = ref.unpack(c, slope)
    assert np.any(d["plasma_exchange_cycles"] != 0)
    np.testing.assert_array_equal(d["energy_amount_increment_fmol"], 0)
    accounting(c, y, slope, proof)


def test_regeneration_control_is_independent_and_right_continuous():
    raw = case()
    event = raw["experiment"]["end_time"] / 3
    for group in raw["experiment"]["regeneration_controls"]:
        group["schedule"] = [dict(time=0.0, availability=0.7), dict(time=event, availability=0.0)]
    c = ref.bind(raw)
    y = ref.initial(c)
    before, _, _ = ref.evaluate(c, y, np.nextafter(event, 0))
    after, _, proof = ref.evaluate(c, y, event)
    a, b = ref.unpack(c, before), ref.unpack(c, after)
    np.testing.assert_array_equal(ref.flatten(c["calcium"], a), ref.flatten(c["calcium"], b))
    assert np.any(a["regeneration_cycles_fmol"] != 0)
    for name in ref.ENERGY_FIELDS[1:]:
        np.testing.assert_array_equal(b[name], 0)
    accounting(c, y, after, proof)


@pytest.mark.parametrize("family", ["nak", "pmca", "er"])
def test_cross_owner_fuel_references_are_rejected(family):
    raw = case()
    if family == "nak":
        meta = raw["model"]["ionic"]["membranes"][0]["pump"]["metabolism"]
    elif family == "pmca":
        meta = raw["model"]["plasma_transport"]["membranes"][0]["pump"]["metabolism"]
    else:
        meta = raw["model"]["stores"][0]["model"]["membrane"]["pump"]["metabolism"]
    original = meta["pool_id"]
    meta["pool_id"] = next(p["id"] for p in raw["model"]["energy_pools"] if p["id"] != original)
    with pytest.raises(ValueError, match="own cell"):
        ref.bind(raw)


@pytest.mark.parametrize("species", [0, 1, 2])
def test_exhausted_pool_rejects_with_pumps_and_regeneration_blocked(species):
    c = ref.bind(isolated_pump(None))
    d = ref.unpack(c, ref.initial(c))
    d["energy_amount_increment_fmol"][species, 0] = -c["energy_initial"][species, 0]
    with pytest.raises(ValueError, match="positive pools"):
        ref.evaluate(c, ref.flatten(c, d), 0)


@pytest.mark.parametrize(
    "fault",
    [
        "duplicate_pool",
        "old_er_law",
        "maintained_fields",
        "negative_capacity",
        "missing_control",
        "negative_regeneration",
    ],
)
def test_finite_pool_declaration_guards(fault):
    raw = case()
    if fault == "duplicate_pool":
        raw["model"]["energy_pools"].append(deepcopy(raw["model"]["energy_pools"][0]))
    elif fault == "old_er_law":
        raw["model"]["stores"][0]["model"]["membrane"]["pump"]["law"] = (
            "betse_1_5_er_calcium_pump_positive@1"
        )
    elif fault == "maintained_fields":
        raw["model"]["plasma_transport"]["membranes"][0]["pump"]["atp_mM"] = 1.5
    elif fault == "negative_capacity":
        raw["model"]["plasma_transport"]["membranes"][0]["pump"]["capacity_fmol_per_s"] = -1
    elif fault == "missing_control":
        raw["experiment"]["regeneration_controls"].pop()
    elif fault == "negative_regeneration":
        raw["model"]["regeneration_ports"][0]["capacity_fmol_per_s"] = -1
    with pytest.raises(ValueError):
        ref.bind(raw)


def test_short_adaptive_history_retains_signed_internal_work_and_pool_invariants():
    raw = case()
    e = raw["experiment"]
    e.update(end_time=2.5e-6, observation_times=[0.0, 1.25e-6, 2.5e-6])
    for name, groups in e.items():
        if name.endswith("_controls"):
            for group in groups:
                key = "schedule" if "schedule" in group else "controls"
                group[key] = [row for row in group[key] if row["time"] <= e["end_time"]]
    c = ref.bind(raw)
    ordinary, tighter = (ref.integrate(raw, refinement=r) for r in (1, 2))
    for name in c["shapes"]:
        a, b = (ref.unpack(c, result["state"])[name] for result in (ordinary, tighter))
        np.testing.assert_allclose(
            a, b, rtol=3e-9, atol=3e-28 if name.endswith("_C") else 3e-13, err_msg=name
        )
    d = ref.unpack(c, ordinary["state"][-1])
    for i in range(len(c["cell_ids"])):
        final = c["energy_initial"][:, i] + d["energy_amount_increment_fmol"][:, i]
        change = chemistry.free_energy_change(
            c["energy_initial"][:, i],
            final,
            c["energy_volumes"][i],
            c["energy_volumes"][i],
            298.15,
            c["energy_delta_g0"][i],
        )
        work = (
            sum(
                d["metabolic_work_pJ"][j] for j, owner in enumerate(c["patch_owners"]) if owner == i
            )
            + sum(
                d["plasma_metabolic_work_pJ"][j]
                for j, owner in enumerate(c["plasma_owners"])
                if owner == i
            )
            + d["er_metabolic_work_pJ"][i]
        )
        for j, port in enumerate(raw["model"]["regeneration_ports"]):
            if c["pools"][port["pool_id"]]["cell_id"] == c["cell_ids"][i]:
                work += (
                    d["regeneration_dissipated_energy_pJ"][j]
                    - d["regeneration_supplied_work_pJ"][j]
                )
        assert abs(change + work) < 3e-12
    evidence(
        "short-adaptive-history",
        dict(
            inputs=raw,
            times=ordinary["times"],
            state=ordinary["state"].tolist(),
            refined_state=tighter["state"].tolist(),
            evaluations=[ordinary["evaluations"], tighter["evaluations"]],
            scope="2.5-us coupling/wiring check; no settling or native-clock claim",
        ),
    )


def test_failed_adaptive_stage_retains_full_state(monkeypatch):
    def failed(*args, **kwargs):
        raise ValueError("Deliberate independent failure-state probe")

    monkeypatch.setattr(ref, "evaluate", failed)
    with pytest.raises(ref.ReferenceIntegrationError) as caught:
        ref.integrate(case())
    details = caught.value.diagnostics
    assert details["evaluations"] == 1 and details["automatic_retry"] is False
    assert len(details["state"]) == ref.initial(ref.bind(case())).size
    json.dumps(details, allow_nan=False)
    evidence("deliberately-failed-stage", details)


def test_reference_worker_has_no_cells_or_jax_imports():
    assert not any(name == "cells" or name.startswith("cells.") for name in sys.modules)
    assert not any(name == "jax" or name.startswith("jax.") for name in sys.modules)
