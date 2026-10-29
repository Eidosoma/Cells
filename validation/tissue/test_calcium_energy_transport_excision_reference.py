"""Independent 42-field configured-transport cutting and transient continuation."""

import json
import os
import sys
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from validation.tissue import calcium_energy_transport_excision_fixtures as fixtures
from validation.tissue import calcium_energy_transport_excision_reference as ref


def evidence(name, value, arrays=None):
    if folder := os.environ.get("CELLS_REFERENCE_EVIDENCE"):
        root = Path(folder)
        root.mkdir(parents=True, exist_ok=True)
        if arrays is not None:
            np.savez_compressed(root / (name + ".npz"), **arrays)
        (root / (name + ".json")).write_text(
            json.dumps(value, indent=2, allow_nan=False, default=lambda v: v.tolist()) + "\n"
        )


def integrate(raw, **kwargs):
    try:
        return ref.integrate(raw, **kwargs)
    except ref.ReferenceIntegrationError as error:
        evidence(
            "failed-integration",
            dict(
                definition=raw,
                arguments=kwargs,
                exception=str(error),
                failed_trial=error.diagnostics,
            ),
        )
        raise


@lru_cache(maxsize=None)
def prefix(arm="open", refinement=1):
    return integrate(fixtures.definition(arm), end_time=fixtures.CUT_TIME, refinement=refinement)


def serialized(cut):
    raw = deepcopy(cut["raw"])
    raw["model"] = dict(
        id=ref.MODEL_ID,
        tissue=raw["model"],
        excision=dict(
            law="conservative_tissue_removal_remap@1",
            state_policy="rebase_chemical_fuel_transport_owners_preserve_gates_archive_complete_source@1",
            reference_policy="free_cytosol_anchor_with_conserved_whole_cell_charge@1",
            clock_policy="absolute_time_original_nominal_grid@1",
            energy_policy="record_jump_without_cut_work_law@1",
            ordering="right_continuous_controls_then_removal@1",
            removed_cell_ids=cut["audit"]["removed_cell_ids"],
            source=deepcopy(cut["archive"]),
        ),
    )
    return raw


def compare(c, a, b):
    for name, value in ref.unpack(c, a).items():
        np.testing.assert_allclose(
            value,
            ref.unpack(c, b)[name],
            rtol=2e-8,
            atol=3e-25 if name.endswith("_C") else 3e-11,
            err_msg=name,
        )


def fuel_ledger_residual(c, state):
    d = ref.unpack(c, state)
    demand = d["er_pump_transferred"][:, 0].copy()
    for field, owners in (
        ("pump_cycles", c["patch_owners"]),
        ("plasma_pump_cycles", c["plasma_owners"]),
    ):
        for j, owner in enumerate(owners):
            demand[owner] += d[field][j]
    for j, port in enumerate(c["raw"]["model"]["regeneration_ports"]):
        owner = c["cell_ids"].index(c["pools"][port["pool_id"]]["cell_id"])
        demand[owner] -= d["regeneration_cycles_fmol"][j]
    expected = np.array([-1, 1, 1])[:, None] * demand
    return float(np.max(abs(d["energy_amount_increment_fmol"] - expected), initial=0))


def chemical_ledger_residual(c, state):
    d, prior = ref.unpack(c, state), c["calcium"]
    residual = 0.0
    for i, store in enumerate(prior["stores"]):
        expected = np.zeros_like(store.n0)
        for j, reaction in enumerate(store.reactions):
            owner = store.owners.index(reaction["compartment"])
            for name in store.ids:
                nu = reaction["products"].get(name, 0) - reaction["reactants"].get(name, 0)
                expected[store.ids.index(name), owner] += nu * d["reaction_extent"][i, j]
        moved = d["er_passive_transferred"][i].copy()
        moved[store.ca] += d["er_pump_transferred"][i, 0] + d["er_release_transferred"][i, 0]
        expected[:, store.cy] -= moved
        expected[:, store.er] += moved
        for j, species in enumerate(prior["raw"]["model"]["species"]):
            expected[store.ids.index(species["id"]), store.cy] += d["amount_increment"][j, i]
        residual = max(residual, np.max(abs(d["chemical_amount_increment"][i] - expected)))
    return float(residual)


def total_moieties(snapshot):
    total = snapshot["chemical_moiety_fmol"].sum(axis=(0, 2))
    for j, species in enumerate(snapshot["species_ids"]):
        total[snapshot["moiety_ids"].index(species)] += snapshot["outside_amount_fmol"][j].sum()
    return total


def valences(c):
    return np.array([v["valence"] for v in c["raw"]["model"]["ionic"]["species"]])


def energy_balances(c, first, last, start, end):
    a, b = ref.unpack(c, first), ref.unpack(c, last)
    change = {k: b[k] - a[k] for k in c["shapes"]}
    before, after = ref.snapshot(c, first, start), ref.snapshot(c, last, end)
    heat = sum(np.sum(v) for k, v in change.items() if k.endswith("dissipated_energy_pJ"))
    supplied = np.sum(change["regeneration_supplied_work_pJ"])
    network_work = np.sum(change["network_supplied_work_pJ"])
    internal_work = sum(
        np.sum(change[k])
        for k in ("metabolic_work_pJ", "plasma_metabolic_work_pJ", "er_metabolic_work_pJ")
    )
    total = after["stored_energy_pJ"] - before["stored_energy_pJ"] + heat - supplied - network_work
    internal = (
        after["fuel_free_energy_pJ"].sum()
        - before["fuel_free_energy_pJ"].sum()
        + internal_work
        + np.sum(change["regeneration_dissipated_energy_pJ"])
        - supplied
    )
    return dict(
        total_energy_residual_pJ=float(total),
        pool_internal_transfer_residual_pJ=float(internal),
        pump_internal_transfer_pJ=float(internal_work),
        regeneration_supply_pJ=float(supplied),
        network_external_work_pJ=float(network_work),
    )


@pytest.mark.parametrize("catalog", ["compact", "full"])
@pytest.mark.parametrize(
    "arm",
    [
        "open",
        "blocked",
        "reordered",
        "zero_routes",
        "network_blocked",
        "zero_drive",
        "removed_neutral_history",
    ],
)
def test_full_stage_material_charge_fuel_and_energy(catalog, arm):
    raw = fixtures.definition(arm, catalog=catalog, padded=True)
    c = ref.bind(raw)
    y = ref.initial(c)
    slope, phi, proof = ref.evaluate(c, y, 0.0)
    d = ref.unpack(c, slope)
    assert len(d) == 42 and np.isfinite(slope).all()
    assert abs(proof["physical_energy_balance_pJ_s"]) < 5e-8
    assert np.max(abs(np.asarray(proof["pool_internal_transfer_balance_pJ_s"]))) < 3e-12
    assert fuel_ledger_residual(c, slope) < 3e-15
    assert chemical_ledger_residual(c, slope) < 3e-13
    np.testing.assert_allclose(proof["adenylate_rate_fmol_s"], 0, atol=3e-15)
    np.testing.assert_allclose(proof["phosphorus_rate_fmol_s"], 0, atol=3e-15)
    i = c["cell_ids"].index("cell_1")
    if arm != "removed_neutral_history":
        np.testing.assert_array_equal(d["amount_increment"][:, i], 0.0)
    else:
        np.testing.assert_allclose(
            np.dot(valences(c), d["amount_increment"][:, i]), 0.0, atol=1e-15
        )
    assert d["er_pump_transferred"][i, 0] > 0
    assert proof["signed_pump_demand_fmol_s"][i] > 0
    m = raw["model"]["ionic"]
    if catalog == "full" and arm != "empty":
        assert len({row["kinetic_law"] for row in m["channels"]}) == 56
    snapshot = ref.snapshot(c, y, 0.0)
    np.testing.assert_array_equal(snapshot["fuel_charge_C"], 0.0)
    np.testing.assert_array_equal(snapshot["inside_charge_C"][i], 0.0)
    evidence(
        f"stage-{catalog}-{arm}",
        dict(proof=proof, snapshot=snapshot),
        dict(state=y, derivative=slope, potential_V=phi),
    )


def test_live_pool_changes_drive_without_direct_charge_or_calcium_material():
    c = ref.bind(fixtures.definition())
    y = ref.initial(c)
    d = ref.unpack(c, y)
    changed = deepcopy(d)
    i = c["cell_ids"].index("cell_1")
    changed["energy_amount_increment_fmol"][:, i] = np.array([-1, 1, 1]) * 0.1
    z = ref.flatten(c, changed)
    ra, pa, ga = ref.evaluate(c, y, 0.0)
    rb, pb, gb = ref.evaluate(c, z, 0.0)
    np.testing.assert_array_equal(pa, pb)
    assert ga["pool_hydrolysis_free_energy_J_mol"][i] != gb["pool_hydrolysis_free_energy_J_mol"][i]
    assert (
        ref.unpack(c, ra)["er_pump_transferred"][i, 0]
        != ref.unpack(c, rb)["er_pump_transferred"][i, 0]
    )
    sa, sb = ref.snapshot(c, y, 0.0), ref.snapshot(c, z, 0.0)
    for name in (
        "inside_charge_C",
        "chemical_amount_fmol",
        "er_voltage_V",
        "chemical_fixed_charge_C",
    ):
        np.testing.assert_array_equal(sa[name], sb[name])
    np.testing.assert_allclose(
        sa["fuel_moiety_fmol"], sb["fuel_moiety_fmol"], rtol=2e-15, atol=3e-15
    )


def test_endpoint_energy_counts_finite_pool_once_and_pump_work_is_internal():
    c = ref.bind(fixtures.definition())
    y = ref.initial(c)
    slope = ref.evaluate(c, y, 0.0)[0]
    h = 1e-9
    # This is a directional derivative of physical stores, not a backwards
    # evolved history with negative accumulated dissipation.
    derivative = ref.network.stored_energy_change(c, y + h * slope, reference_state=y - h * slope)[
        "total_pJ"
    ] / (2 * h)
    d = ref.unpack(c, slope)
    heat = sum(np.sum(v) for k, v in d.items() if k.endswith("dissipated_energy_pJ"))
    supply = np.sum(d["regeneration_supplied_work_pJ"]) + np.sum(d["network_supplied_work_pJ"])
    internal = sum(
        np.sum(d[k])
        for k in ("metabolic_work_pJ", "plasma_metabolic_work_pJ", "er_metabolic_work_pJ")
    )
    assert abs(derivative + heat - supply) < 0.02
    assert abs(internal) > 0.1
    assert abs(derivative + heat - supply - internal) > 0.1
    evidence(
        "endpoint-energy",
        dict(
            derivative_pJ_s=derivative,
            heat_pJ_s=float(heat),
            total_external_supply_pJ_s=float(supply),
            internal_pump_work_pJ_s=float(internal),
            residual_pJ_s=float(derivative + heat - supply),
            finite_difference_seconds=h,
        ),
    )


@pytest.mark.parametrize("catalog", ["compact", "full"])
def test_initial_cut_keeps_route_pool_parameters_all_gates_and_nine_clocks(catalog):
    raw = fixtures.definition(catalog=catalog, padded=True)
    c = ref.bind(raw)
    y = ref.initial(c)
    cut = ref.excise(raw, y, ["cell_1"], 0.0)
    after = cut["raw"]["model"]
    assert len(cut["archive"]["checkpoint"]["state"]) == 42
    assert set(ref.event_times(raw)) <= set(ref.event_times(cut["raw"]))
    assert cut["audit"]["removed_pool_ids"] == ["fuel_cell_1"]
    assert cut["audit"]["removed_regeneration_ids"] == ["supply_cell_1"]
    assert cut["audit"]["pump_metabolic_work_internal"]
    assert cut["audit"]["maintained_atp_work_internal"]
    assert cut["audit"]["network_work_external"]
    assert not cut["audit"]["network_routes_store_material"]
    source_routes = {p["id"]: p for p in raw["model"]["network_transport"]["routes"]}
    for route in after["network_transport"]["routes"]:
        assert route == source_routes[route["id"]]
        assert "cell_1" not in route["id"]
    assert len(cut["audit"]["removed_network_route_ids"]) == 4
    assert len(cut["audit"]["retained_network_route_ids"]) == 8
    for group in ("energy_pools", "regeneration_ports"):
        old = {p["id"]: p for p in raw["model"][group]}
        for p in after[group]:
            assert p == old[p["id"]]
    a, b = ref.unpack(c, y), ref.unpack(cut["context"], cut["state"])
    for k, v in b.items():
        if k not in ref.GATES:
            np.testing.assert_array_equal(v, 0.0)
    for field, group in (
        ("channel_gate", "channels"),
        ("junction_gate", "junctions"),
        ("calcium_gate", "membranes"),
    ):
        old = {p["id"]: j for j, p in enumerate(raw["model"]["ionic"][group])}
        keep = [old[p["id"]] for p in after["ionic"][group]]
        np.testing.assert_array_equal(b[field], a[field][..., keep])


def test_reordered_compartment_roles_and_zero_padding_are_archived_without_material():
    raw = fixtures.definition("reordered", padded=True)
    for row in raw["model"]["stores"]:
        model = row["model"]
        names = {model["membrane"]["cytosol"]: "z_cytosol", model["membrane"]["er"]: "a_er"}
        for p in model["compartments"]:
            p["id"] = names[p["id"]]
        for r in model["reactions"]:
            r["compartment"] = names[r["compartment"]]
        for role in ("cytosol", "er"):
            model["membrane"][role] = names[model["membrane"][role]]
        model["compartments"].reverse()
        model["species"].reverse()
    c = ref.bind(raw)
    fields = ref.unpack(c, ref.initial(c))
    for name in (
        "energy_amount_increment_fmol",
        "chemical_amount_increment",
        "channel_gate",
        "calcium_gate",
        "regeneration_cycles_fmol",
        "regeneration_dissipated_energy_pJ",
        "regeneration_supplied_work_pJ",
        *ref.network.EXTRA_FIELDS,
    ):
        widths = [(0, 0)] * fields[name].ndim
        widths[-1] = (0, 1)
        fields[name] = np.pad(fields[name], widths)
    layout = dict(independent_field_shapes={k: list(v.shape) for k, v in fields.items()})
    cut = ref.excise(raw, fields, ["cell_1"], 0.0, source_layout=layout)
    assert cut["archive"]["checkpoint"]["layout"] == layout
    for name, values in fields.items():
        np.testing.assert_array_equal(cut["archive"]["checkpoint"]["state"][name], values)
    assert cut["audit"]["after"]["chemical_compartment_ids"] == ["a_er", "z_cytosol"]
    assert cut["context"]["calcium"]["stores"][0].cy == 1


@pytest.mark.parametrize("arm", ["no-op", "terminal", "single-survivor", "sequential"])
def test_noop_terminal_and_sequential_fuel_ownership(arm):
    raw = fixtures.definition(arm)
    c = ref.bind(raw)
    y = ref.initial(c)
    cut = ref.excise(raw, y, fixtures.cut_plan(arm)[0]["removed_cell_ids"], 0.0)
    if arm == "no-op":
        assert cut["raw"] == raw
        np.testing.assert_array_equal(cut["state"], y)
    elif arm == "terminal":
        assert cut["raw"] is cut["state"] is cut["context"] is None
        assert cut["audit"]["after"] is None
        np.testing.assert_allclose(
            cut["audit"]["removed_fuel_amount_fmol"], c["energy_initial"].sum(axis=1)
        )
    elif arm == "single-survivor":
        assert [p["cell_id"] for p in cut["raw"]["model"]["energy_pools"]] == ["cell_2"]
    else:
        second = ref.excise(serialized(cut), cut["state"], ["cell_0"], 0.0)
        assert [p["cell_id"] for p in second["raw"]["model"]["energy_pools"]] == ["cell_2"]
        assert second["archive"]["definition"]["model"]["excision"]["source"] == cut["archive"]


def test_neutral_fuel_cannot_repair_a_charged_cut():
    raw = fixtures.definition("charged")
    c = ref.bind(raw)
    with pytest.raises(ref.ExcisionError) as caught:
        ref.excise(raw, ref.initial(c), ["cell_0"], 0.0)
    error = caught.value
    assert len(error.archive["checkpoint"]["state"]) == 42
    assert error.audit["rejected"] and abs(error.audit["removed_charge_C"]) > 1e-14
    evidence(
        "expected-charged-refusal",
        dict(exception=str(error), archive=error.archive, audit=error.audit),
    )


@pytest.mark.parametrize(
    "failure",
    [
        "missing_fuel_history",
        "nan",
        "empty_atp",
        "negative_adp",
        "wrong_owner",
        "duplicate_pool",
        "off_grid",
        "past_epoch",
    ],
)
def test_strict_fuel_archive_owner_and_clock_guards(failure):
    raw = fixtures.definition()
    c = ref.bind(raw)
    d = ref.unpack(c, ref.initial(c))
    time = 0.0
    if failure == "missing_fuel_history":
        d.pop("regeneration_supplied_work_pJ")
    elif failure == "nan":
        d["regeneration_cycles_fmol"][0] = np.nan
    elif failure == "empty_atp":
        d["energy_amount_increment_fmol"][0, 0] = -c["energy_initial"][0, 0]
    elif failure == "negative_adp":
        d["energy_amount_increment_fmol"][1, 0] = -2 * c["energy_initial"][1, 0]
    elif failure == "wrong_owner":
        raw["model"]["stores"][0]["model"]["membrane"]["pump"]["metabolism"]["pool_id"] = (
            "fuel_cell_1"
        )
    elif failure == "duplicate_pool":
        raw["model"]["energy_pools"].append(deepcopy(raw["model"]["energy_pools"][0]))
    elif failure == "off_grid":
        time = 0.1 * fixtures.DT
    elif failure == "past_epoch":
        cut = ref.excise(raw, ref.initial(c), ["cell_1"], fixtures.CUT_TIME)
        raw, d = serialized(cut), ref.unpack(cut["context"], cut["state"])
    with pytest.raises(ValueError):
        ref.excise(raw, d, ["cell_1" if failure != "past_epoch" else "cell_0"], time)


@pytest.mark.parametrize("arm", ["open", "removed_neutral_history"])
def test_full_42_prefix_cut_suffix_refinement_and_energy_material_closure(arm):
    raw = fixtures.definition(arm)
    c = ref.bind(raw)
    paths, cuts, suffixes = [], [], []
    for refinement in (1, 2):
        paths.append(prefix(arm, refinement))
        cuts.append(ref.excise(raw, paths[-1]["state"][-1], ["cell_1"], fixtures.CUT_TIME))
        suffixes.append(integrate(serialized(cuts[-1]), refinement=refinement))
    compare(c, paths[0]["state"], paths[1]["state"])
    compare(cuts[0]["context"], suffixes[0]["state"], suffixes[1]["state"])
    before = ref.snapshot(c, ref.initial(c), 0.0)
    pre, post = cuts[0]["audit"]["before"], cuts[0]["audit"]["after"]
    d = ref.unpack(c, paths[0]["state"][-1])
    assert np.max(abs(d["energy_amount_increment_fmol"][:, 1])) > 1e-8
    assert d["er_pump_transferred"][1, 0] > 1e-9
    assert d["er_metabolic_work_pJ"][1] > 1e-8
    assert np.max(abs(d["chemical_amount_increment"][1])) > 1e-8
    if arm == "open":
        np.testing.assert_array_equal(d["amount_increment"][:, 1], 0.0)
    else:
        assert np.max(abs(d["amount_increment"][:, 1])) > 1e-8
        assert abs(np.dot(valences(c), d["amount_increment"][:, 1])) < 1e-15
        for key in ref.network.EXTRA_FIELDS:
            assert np.max(abs(cuts[0]["audit"]["archived_removed_network_state"][key])) > 1e-8
    for name in ("chemical_amount_fmol", "chemical_moiety_fmol", "er_voltage_V", "inside_charge_C"):
        np.testing.assert_array_equal(post[name], pre[name][[0, 2]])
    np.testing.assert_allclose(
        post["chemical_fixed_charge_C"],
        pre["chemical_fixed_charge_C"][[0, 2]],
        rtol=4e-15,
        atol=5e-23,
    )
    np.testing.assert_array_equal(post["fuel_amount_fmol"], pre["fuel_amount_fmol"][:, [0, 2]])
    np.testing.assert_array_equal(post["fuel_free_energy_pJ"], pre["fuel_free_energy_pJ"][[0, 2]])
    for field, group in (
        ("channel_gate", "channels"),
        ("junction_gate", "junctions"),
        ("calcium_gate", "membranes"),
    ):
        old = {p["id"]: j for j, p in enumerate(raw["model"]["ionic"][group])}
        keep = [old[p["id"]] for p in cuts[0]["raw"]["model"]["ionic"][group]]
        np.testing.assert_array_equal(
            ref.unpack(cuts[0]["context"], cuts[0]["state"])[field], d[field][..., keep]
        )
        assert np.max(abs(d[field] - ref.unpack(c, ref.initial(c))[field])) > 1e-8
    for name, values in d.items():
        np.testing.assert_array_equal(cuts[0]["archive"]["checkpoint"]["state"][name], values)
    assert set(ref.event_times(raw)) <= set(ref.event_times(serialized(cuts[0])))
    assert suffixes[0]["times"][0] == fixtures.CUT_TIME == min(suffixes[0]["event_times"])
    final = ref.snapshot(cuts[0]["context"], suffixes[0]["state"][-1], fixtures.END_TIME)
    np.testing.assert_allclose(
        total_moieties(before),
        total_moieties(final) + cuts[0]["audit"]["removed_moiety_fmol"],
        rtol=2e-14,
        atol=3e-11,
    )
    np.testing.assert_allclose(
        before["fuel_moiety_fmol"].sum(axis=1),
        final["fuel_moiety_fmol"].sum(axis=1) + cuts[0]["audit"]["removed_fuel_moiety_fmol"],
        rtol=2e-14,
        atol=3e-11,
    )
    fuel_residuals = [
        fuel_ledger_residual(c, paths[0]["state"][-1]),
        fuel_ledger_residual(cuts[0]["context"], suffixes[0]["state"][-1]),
    ]
    chemical_residuals = [
        chemical_ledger_residual(c, paths[0]["state"][-1]),
        chemical_ledger_residual(cuts[0]["context"], suffixes[0]["state"][-1]),
    ]
    assert max(fuel_residuals + chemical_residuals) < 3e-11
    energies = [
        energy_balances(c, paths[0]["state"][0], paths[0]["state"][-1], 0.0, fixtures.CUT_TIME),
        energy_balances(
            cuts[0]["context"],
            suffixes[0]["state"][0],
            suffixes[0]["state"][-1],
            fixtures.CUT_TIME,
            fixtures.END_TIME,
        ),
    ]
    assert (
        max(
            abs(v[k])
            for v in energies
            for k in ("total_energy_residual_pJ", "pool_internal_transfer_residual_pJ")
        )
        < 3e-9
    )
    assert any(abs(v["pump_internal_transfer_pJ"]) > 1e-8 for v in energies)
    assert all(abs(v["network_external_work_pJ"]) > 1e-8 for v in energies)
    for name, values in ref.unpack(cuts[0]["context"], cuts[0]["state"]).items():
        if name not in ref.GATES:
            np.testing.assert_array_equal(values, 0.0)
    for context, history in (
        (c, d),
        (cuts[0]["context"], ref.unpack(cuts[0]["context"], suffixes[0]["state"][-1])),
    ):
        np.testing.assert_allclose(
            history["network_transferred_fmol"],
            context["network_nu"] * history["network_cycles_fmol"],
            rtol=3e-13,
            atol=3e-11,
        )
    for j in range(2):
        for kind, trace in (("prefix", paths[j]), ("suffix", suffixes[j])):
            evidence(
                f"{arm}-{kind}-refinement-{j + 1}",
                {k: v for k, v in trace.items() if k not in ("state", "potential_V")},
                dict(state=trace["state"], potential_V=trace["potential_V"]),
            )
    evidence(
        f"{arm}-complete-transport-cut-continuation",
        dict(
            audit=cuts[0]["audit"],
            archive=cuts[0]["archive"],
            after_definition=serialized(cuts[0]),
            source_state_fields=42,
            local_zero_fields=39,
            physical_duration_s=fixtures.END_TIME,
            cut_time_s=fixtures.CUT_TIME,
            equilibrium_claim=False,
            native_cut_claim=False,
            maximum_prefix_difference=float(np.max(abs(paths[0]["state"] - paths[1]["state"]))),
            maximum_suffix_difference=float(
                np.max(abs(suffixes[0]["state"] - suffixes[1]["state"]))
            ),
            fuel_ledger_residuals_fmol=fuel_residuals,
            chemical_ledger_residuals_fmol=chemical_residuals,
            energy_checks=energies,
        ),
    )


@pytest.mark.parametrize("arm", ["open", "removed_neutral_history", "zero_routes"])
def test_network_routes_add_owned_ions_external_work_and_no_direct_atp_cost(arm):
    c = ref.bind(fixtures.definition(arm))
    y = ref.initial(c)
    full, phi, proof = ref.evaluate(c, y, 0.0)
    _, prior, physical = ref._energy_view(c, y)
    old, old_phi, old_proof = ref.energy_cut.evaluate(prior, physical, 0.0)
    np.testing.assert_array_equal(phi, old_phi)
    d, base = ref.unpack(c, full), ref.energy_cut.unpack(prior, old)
    for field in (
        "energy_amount_increment_fmol",
        "pump_cycles",
        "plasma_pump_cycles",
        "er_pump_transferred",
        "regeneration_cycles_fmol",
        *ref.GATES,
    ):
        np.testing.assert_array_equal(d[field], base[field])
    np.testing.assert_array_equal(proof["network_direct_atp_demand_fmol_s"], 0.0)
    np.testing.assert_array_equal(
        proof["signed_pump_demand_fmol_s"], old_proof["signed_pump_demand_fmol_s"]
    )
    cell, outside = (
        np.zeros_like(d["amount_increment"]),
        np.zeros_like(d["extracellular_amount_increment"]),
    )
    for j, (i, o) in enumerate(c["network_owners"]):
        moved = d["network_transferred_fmol"][:, j]
        cell[:, i] -= moved
        outside[:, o] += moved
    np.testing.assert_allclose(d["amount_increment"] - base["amount_increment"], cell, atol=3e-13)
    np.testing.assert_allclose(
        d["extracellular_amount_increment"] - base["extracellular_amount_increment"],
        outside,
        atol=3e-13,
    )
    np.testing.assert_allclose(cell.sum(axis=1) + outside.sum(axis=1), 0.0, atol=3e-13)
    for i, store in enumerate(c["stores"]):
        expected = np.zeros_like(store.n0)
        expected[[store.ids.index(s) for s in c["network_species"]], store.cy] = cell[:, i]
        np.testing.assert_allclose(
            d["chemical_amount_increment"][i] - base["chemical_amount_increment"][i],
            expected,
            atol=3e-13,
        )
    np.testing.assert_allclose(
        d["network_transferred_fmol"],
        c["network_nu"] * d["network_cycles_fmol"],
        rtol=3e-14,
        atol=3e-13,
    )
    if arm == "zero_routes":
        for key, value in base.items():
            np.testing.assert_array_equal(d[key], value)
        for key in ref.network.EXTRA_FIELDS:
            assert d[key].size == 0


def test_free_cytosol_changes_transport_and_ca_pump_without_charge_or_total_ca_change():
    c = ref.bind(fixtures.definition())
    y = ref.initial(c)
    fields = deepcopy(ref.unpack(c, y))
    store = c["stores"][0]
    # Rebind 0.0001 fmol cytosolic Ca+B -> CaB: the route senses actual free
    # calcium while the plasma charge and total calcium moiety are fixed.
    fields["chemical_amount_increment"][
        0, [store.ids.index(v) for v in ("Ca", "B", "CaB")], store.cy
    ] += np.array([-1, -1, 1]) * 1e-4
    changed = ref.flatten(c, fields)
    ra, pa, _ = ref.evaluate(c, y, 0.0)
    rb, pb, _ = ref.evaluate(c, changed, 0.0)
    np.testing.assert_array_equal(pa, pb)
    a, b = ref.unpack(c, ra), ref.unpack(c, rb)
    j = c["network_ids"].index("na_ca_cell_0")
    assert a["network_cycles_fmol"][j] != b["network_cycles_fmol"][j]
    assert a["er_pump_transferred"][0, 0] != b["er_pump_transferred"][0, 0]
    sa, sb = ref.snapshot(c, y, 0.0), ref.snapshot(c, changed, 0.0)
    np.testing.assert_allclose(sa["chemical_moiety_fmol"], sb["chemical_moiety_fmol"], atol=3e-15)
    np.testing.assert_array_equal(sa["inside_charge_C"], sb["inside_charge_C"])


def test_reordered_route_species_and_cell_ids_preserve_physical_stage():
    contexts = [ref.bind(fixtures.definition(v)) for v in ("open", "reordered")]
    states = [ref.initial(c) for c in contexts]
    stages = [
        ref.unpack(c, ref.evaluate(c, y, 0.0)[0]) for c, y in zip(contexts, states, strict=True)
    ]
    a, b = contexts
    ri = [b["network_ids"].index(v) for v in a["network_ids"]]
    si = [b["network_species"].index(v) for v in a["network_species"]]
    ci = [b["cell_ids"].index(v) for v in a["cell_ids"]]
    for key in ref.network.EXTRA_FIELDS:
        right = stages[1][key][..., ri]
        if key == "network_transferred_fmol":
            right = right[si]
        np.testing.assert_allclose(stages[0][key], right, rtol=3e-13, atol=3e-13)
    np.testing.assert_allclose(
        stages[0]["amount_increment"],
        stages[1]["amount_increment"][np.ix_(si, ci)],
        rtol=3e-13,
        atol=3e-13,
    )
    for c, y in zip(contexts, states, strict=True):
        cut = ref.excise(c["definition"], y, ["cell_1"], 0.0)
        assert set(cut["audit"]["removed_network_route_ids"]) == {
            "kcl_cell_1",
            "na_ca_cell_1",
            "na_drive_cell_1",
            "ca_out_cell_1",
        }


def test_route_only_and_removed_only_boundaries_survive_with_right_continuity():
    raw = fixtures.definition()
    c = ref.bind(raw)
    y = ref.initial(c)
    route = c["network_ids"].index("na_drive_cell_0")
    boundary = 13.3e-6
    left = ref.unpack(c, ref.evaluate(c, y, np.nextafter(boundary, 0.0))[0])
    right = ref.unpack(c, ref.evaluate(c, y, boundary)[0])
    assert left["network_cycles_fmol"][route] != 0
    assert right["network_cycles_fmol"][route] == 0
    cut = ref.excise(raw, y, ["cell_1"], fixtures.CUT_TIME)
    assert 97.3e-6 in ref.event_times(cut["raw"])
    assert all(
        p["transporter_id"] != "na_drive_cell_1"
        for p in cut["raw"]["experiment"]["network_transport_controls"]
    )
    post, state = cut["context"], cut["state"]
    before = ref.evaluate(post, state, np.nextafter(97.3e-6, 0.0))[0]
    after = ref.evaluate(post, state, 97.3e-6)[0]
    np.testing.assert_array_equal(before, after)


@pytest.mark.parametrize(
    "failure", ["missing_history", "negative_heat", "wrong_owner", "work_sign", "conversion"]
)
def test_transport_archive_route_and_work_guards(failure):
    raw = fixtures.definition("network_blocked")
    c = ref.bind(raw)
    fields = ref.unpack(c, ref.initial(c))
    route = raw["model"]["network_transport"]["routes"][0]
    if failure == "missing_history":
        fields.pop("network_supplied_work_pJ")
    elif failure == "negative_heat":
        fields["network_dissipated_energy_pJ"][0] = -1e-6
    elif failure == "wrong_owner":
        route["membrane_id"] = "missing_membrane"
    elif failure == "work_sign":
        route["drive"]["supplied_energy_J_per_mol"] = 10.0
    elif failure == "conversion":
        route["configuration"]["product multipliers"][0] = 2
    with pytest.raises(ValueError):
        ref.excise(raw, fields, ["cell_1"], 0.0)


def test_no_production_or_accelerator_imports():
    assert not any(k == "cells" or k.startswith(("cells.", "jax", "jaxlib")) for k in sys.modules)
