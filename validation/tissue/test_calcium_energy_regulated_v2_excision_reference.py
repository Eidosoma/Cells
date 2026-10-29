"""Independent regulated cut ownership, instantaneous fields and continuation."""

import json
import os
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from validation.regulation import integrated_network_regulation_v2_fixtures as regulated_fixture
from validation.tissue import calcium_energy_regulated_v2_excision_fixtures as fixtures
from validation.tissue import calcium_energy_regulated_v2_excision_reference as ref
from validation.tissue.test_calcium_energy_excision_reference import (
    chemical_ledger_residual,
    fuel_ledger_residual,
    total_moieties,
)


def evidence(name, value, arrays=None):
    if folder := os.environ.get("CELLS_REFERENCE_EVIDENCE"):
        root = Path(folder)
        root.mkdir(parents=True, exist_ok=True)
        if arrays is not None:
            np.savez_compressed(root / (name + ".npz"), **arrays)
        (root / (name + ".json")).write_text(
            json.dumps(value, indent=2, allow_nan=False, default=lambda v: v.tolist()) + "\n"
        )


def serialized(cut):
    raw = deepcopy(cut["raw"])
    raw["model"] = dict(
        id=ref.MODEL_ID,
        tissue=raw["model"],
        excision=dict(
            law="conservative_tissue_removal_remap@1",
            state_policy="rebase_chemical_fuel_regulation_owners_preserve_gates_archive_complete_source@1",
            reference_policy="free_cytosol_anchor_with_conserved_whole_cell_charge@1",
            clock_policy="absolute_time_original_nominal_grid@1",
            energy_policy="record_jump_without_cut_work_law@1",
            ordering="right_continuous_controls_then_removal@1",
            removed_cell_ids=cut["audit"]["removed_cell_ids"],
            source=deepcopy(cut["archive"]),
        ),
    )
    return raw


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


def compare(c, a, b):
    for name, value in ref.unpack(c, a).items():
        np.testing.assert_allclose(
            value,
            ref.unpack(c, b)[name],
            rtol=2e-8,
            atol=3e-25 if name.endswith("_C") else 3e-11,
            err_msg=name,
        )


def balances(c, first, last, start, end):
    a, b = ref.unpack(c, first), ref.unpack(c, last)
    delta = {k: b[k] - a[k] for k in c["shapes"]}
    before, after = ref.snapshot(c, first, start), ref.snapshot(c, last, end)
    heat = sum(np.sum(v) for k, v in delta.items() if k.endswith("dissipated_energy_pJ"))
    supply = np.sum(delta["regeneration_supplied_work_pJ"])
    internal = sum(
        np.sum(delta[k])
        for k in ("metabolic_work_pJ", "plasma_metabolic_work_pJ", "er_metabolic_work_pJ")
    )
    return dict(
        total_energy_residual_pJ=float(
            after["stored_energy_pJ"] - before["stored_energy_pJ"] + heat - supply
        ),
        pool_internal_transfer_residual_pJ=float(
            after["fuel_free_energy_pJ"].sum()
            - before["fuel_free_energy_pJ"].sum()
            + internal
            + np.sum(delta["regeneration_dissipated_energy_pJ"])
            - supply
        ),
        pump_internal_transfer_pJ=float(internal),
        regeneration_supply_pJ=float(supply),
    )


def retained_rules(raw, after):
    target = ref._targets(after["model"])
    return [
        r
        for r in raw["model"]["network_regulation"]["rules"]
        if r["target_id"] in target[r["kind"]]
    ]


@pytest.mark.parametrize("catalog", ["compact", "full"])
@pytest.mark.parametrize(
    "arm",
    ["open", "blocked", "reordered", "empty", "no_rules", "shadowed", "identity", "factor_blocked"],
)
def test_complete_stage_owners_material_and_energy(catalog, arm):
    raw = fixtures.definition(arm, catalog=catalog, padded=True)
    c = ref.bind(raw)
    y = ref.initial(c)
    slope, phi, proof = ref.evaluate(c, y, 0.0)
    assert len(c["shapes"]) == 38 and np.isfinite(slope).all()
    assert abs(proof["physical_energy_balance_pJ_s"]) < 5e-8
    assert np.max(abs(np.asarray(proof["pool_internal_transfer_balance_pJ_s"]))) < 3e-12
    assert fuel_ledger_residual(c, slope) < 3e-15
    assert chemical_ledger_residual(c, slope) < 3e-13
    if catalog == "full" and arm != "empty":
        assert len({r["kinetic_law"] for r in raw["model"]["ionic"]["channels"]}) == 56
    snap = ref.snapshot(c, y, 0.0)
    np.testing.assert_array_equal(snap["potential_V"], phi)
    i = c["cell_ids"].index("cell_1")
    np.testing.assert_array_equal(ref.unpack(c, slope)["amount_increment"][:, i], 0.0)
    assert ref.unpack(c, slope)["er_pump_transferred"][i, 0] > 0
    evidence(
        f"stage-{catalog}-{arm}",
        dict(proof=proof, snapshot=snap),
        dict(state=y, derivative=slope, potential_V=phi),
    )


@pytest.mark.parametrize("catalog", ["compact", "full"])
@pytest.mark.parametrize("arm", ["open", "shadowed", "no_rules", "reordered"])
def test_initial_cut_preserves_exact_order_owner_factors_gates_and_clocks(catalog, arm):
    raw = fixtures.definition(arm, catalog=catalog, padded=True)
    c = ref.bind(raw)
    y = ref.initial(c)
    cut = ref.excise(raw, y, ["cell_1"], 0.0)
    assert cut["raw"]["model"]["network_regulation"]["rules"] == retained_rules(raw, cut["raw"])
    assert cut["audit"]["surviving_rule_factors_unchanged"]
    assert len(cut["archive"]["checkpoint"]["state"]) == 38
    assert set(ref.event_times(raw)) <= set(ref.event_times(cut["raw"]))
    a, b = ref.unpack(c, y), ref.unpack(cut["context"], cut["state"])
    for name, values in b.items():
        if name not in ref.GATES:
            np.testing.assert_array_equal(values, 0.0)
    for field, group in (
        ("channel_gate", "channels"),
        ("junction_gate", "junctions"),
        ("calcium_gate", "membranes"),
    ):
        old = {r["id"]: j for j, r in enumerate(raw["model"]["ionic"][group])}
        keep = [old[r["id"]] for r in cut["raw"]["model"]["ionic"][group]]
        np.testing.assert_array_equal(b[field], a[field][..., keep])
    proof = ref.bind(serialized(cut))
    np.testing.assert_array_equal(
        ref.evaluate(proof, ref.initial(proof), 0.0)[0],
        ref.evaluate(cut["context"], cut["state"], 0.0)[0],
    )


def test_live_free_cytosol_and_fuel_samples_and_shadowed_rules():
    raw = fixtures.definition("shadowed")
    c = ref.bind(raw)
    state = ref.initial(c)
    before = ref.regulation.factors(c, state, 0.0)
    d = deepcopy(ref.unpack(c, state))
    # Neutral fuel changes leave instantaneous charge/field unchanged but alter
    # live factors. Free calcium is read from chemical cytosol, not whole-cell Q.
    d["energy_amount_increment_fmol"][:, 0] = [-0.1, 0.1, 0.1]
    store = c["stores"][0]
    # Reverse one binding reaction, preserving chemical moieties and charge.
    reaction = store.reactions[0]
    for name in store.ids:
        nu = reaction["products"].get(name, 0) - reaction["reactants"].get(name, 0)
        d["chemical_amount_increment"][0, store.ids.index(name), store.cy] = -nu * 1e-4
    d["reaction_extent"][0, 0] = -1e-4
    changed = ref.flatten(c, d)
    after = ref.regulation.factors(c, changed, 0.0)
    assert np.max(abs(np.asarray(before["rule_factors"]) - after["rule_factors"])) > 1e-7
    for kind in ("nak", "channel", "junction"):
        last = next(r for r in reversed(c["rules"]) if r["kind"] == kind)
        indices = [
            i
            for i, r in enumerate(c["rules"])
            if r["kind"] == kind and r["target_id"] == last["target_id"]
        ]
        assert len(indices) >= 2
        assert before["rule_factors"][indices[0]] != before["rule_factors"][indices[-1]]
    # A shadowed rule is still validated/evaluated and archived, not discarded.
    cut = ref.excise(raw, changed, ["cell_1"], 0.0)
    assert cut["raw"]["model"]["network_regulation"]["rules"] == retained_rules(raw, cut["raw"])
    assert cut["archive"]["definition"] == raw


def test_actual_regulated_field_in_floating_components_not_unregulated_projection():
    # The frozen @2 parent fixture has floating capacitor components. A no-op
    # cut retains its geometry, so any field difference is caused by factors.
    raw = regulated_fixture.definition("active", compact=True)
    c = ref.bind(raw)
    state = ref.initial(c)
    _, actual, _ = ref.evaluate(c, state, 0.0)
    parent = ref.fuel_cut.bind(c["raw"])
    _, unregulated, _ = ref.fuel_cut.evaluate(parent, state, 0.0)
    difference = float(np.max(abs(actual - unregulated)))
    assert difference > 1e-7
    snap = ref.snapshot(c, state, 0.0)
    np.testing.assert_allclose(snap["potential_V"], actual, rtol=2e-11, atol=3e-12)
    cut = ref.excise(raw, state, [], 0.0)
    np.testing.assert_allclose(
        cut["audit"]["before"]["potential_V"], actual, rtol=2e-11, atol=3e-12
    )
    evidence(
        "floating-regulated-field",
        dict(
            error_if_unregulated_V=difference,
            actual_potential_V=actual,
            unregulated_potential_V=unregulated,
            scope="Manufactured instantaneous floating-field case, not an evolved prefix",
        ),
    )


def test_padded_complete_source_history_is_archived_without_new_owners():
    raw = fixtures.definition("reordered", padded=True)
    c = ref.bind(raw)
    fields = deepcopy(ref.unpack(c, ref.initial(c)))
    for name in (
        "energy_amount_increment_fmol",
        "chemical_amount_increment",
        "channel_gate",
        "calcium_gate",
        "regeneration_cycles_fmol",
        "regeneration_dissipated_energy_pJ",
        "regeneration_supplied_work_pJ",
    ):
        widths = [(0, 0)] * fields[name].ndim
        widths[-1] = (0, 1)
        fields[name] = np.pad(fields[name], widths)
    layout = dict(declared_padding=True, original_layout=c["layout"])
    cut = ref.excise(raw, fields, ["cell_1"], 0.0, source_layout=layout)
    for name, value in fields.items():
        np.testing.assert_array_equal(cut["archive"]["checkpoint"]["state"][name], value)
    assert cut["archive"]["checkpoint"]["layout"]["declared_padding"]
    assert len(cut["archive"]["checkpoint"]["state"]) == 38
    assert cut["raw"]["model"]["network_regulation"]["rules"] == retained_rules(raw, cut["raw"])


def test_bound_and_er_calcium_are_not_regulator_free_cytosol_samples():
    c = ref.bind(fixtures.definition())
    y = ref.initial(c)
    d = deepcopy(ref.unpack(c, y))
    for i, store in enumerate(c["stores"]):
        d["chemical_amount_increment"][i, store.ids.index("CaB"), store.cy] = 1e-4
        d["chemical_amount_increment"][i, store.ca, store.er] = 1e-4
    # These are read-view counterfactuals, not a dynamically admissible cut.
    np.testing.assert_array_equal(
        ref.regulation.samples(c, y), ref.regulation.samples(c, ref.flatten(c, d))
    )


@pytest.mark.parametrize("arm", ["no-op", "terminal", "single-survivor", "sequential"])
def test_noop_terminal_single_and_sequential_epochs(arm):
    raw = fixtures.definition(arm)
    c = ref.bind(raw)
    y = ref.initial(c)
    first = fixtures.cut_plan(arm)[0]
    cut = ref.excise(raw, y, first["removed_cell_ids"], first["time_s"])
    assert cut["archive"]["definition"] == raw
    if arm == "no-op":
        assert cut["raw"] == raw
        np.testing.assert_array_equal(cut["state"], y)
    elif arm == "terminal":
        assert cut["raw"] is None and cut["state"] is None
        assert cut["audit"]["removed_regulator_ids"] == [r["id"] for r in c["rules"]]
    elif arm == "single-survivor":
        assert cut["context"]["cell_ids"] == ["cell_2"]
    else:
        next_plan = fixtures.cut_plan(arm)[1]
        after = serialized(cut)
        second = ref.excise(after, cut["state"], next_plan["removed_cell_ids"], next_plan["time_s"])
        assert second["context"]["cell_ids"] == ["cell_2"]
        assert second["archive"]["definition"]["model"]["excision"]["source"] == cut["archive"]


def test_charged_cut_refused_without_implicit_regulation_or_charge_repair():
    raw = fixtures.definition("charged")
    c = ref.bind(raw)
    with pytest.raises(ref.ExcisionError) as caught:
        ref.excise(raw, ref.initial(c), ["cell_0"], 0.0)
    assert caught.value.archive["definition"] == raw
    assert caught.value.audit["regulated_cut_field"]
    evidence(
        "charged-refusal",
        dict(exception=str(caught.value), audit=caught.value.audit, archive=caught.value.archive),
    )


@pytest.mark.parametrize(
    "failure",
    [
        "target",
        "sample_cell",
        "sample_exterior",
        "fuel_owner",
        "duplicate",
        "shadowed_owner",
        "missing_state",
        "off_grid",
        "altered_survivor",
        "missing_survivor",
    ],
)
def test_complete_rules_owners_history_and_clock_refusals(failure):
    raw = fixtures.definition("shadowed")
    c = ref.bind(raw)
    d = ref.unpack(c, ref.initial(c))
    rules = raw["model"]["network_regulation"]["rules"]
    time = 0.0
    if failure == "target":
        rules[0]["target_id"] = "missing"
    elif failure == "sample_cell":
        rules[0]["sample_cell_id"] = "cell_1"
    elif failure == "sample_exterior":
        rules[0]["sample_exterior_id"] = "missing"
    elif failure == "fuel_owner":
        rules[0]["fuel_pool_id"] = "fuel_cell_1"
    elif failure == "duplicate":
        rules[-1]["id"] = rules[0]["id"]
    elif failure == "shadowed_owner":
        rules[0]["fuel_pool_id"] = "absent"
    elif failure == "missing_state":
        d.pop("regeneration_supplied_work_pJ")
    elif failure == "off_grid":
        time = 0.1 * fixtures.DT
    else:
        cut = ref.excise(raw, d, ["cell_1"], fixtures.CUT_TIME)
        raw, d = serialized(cut), ref.unpack(cut["context"], cut["state"])
        rules = raw["model"]["tissue"]["network_regulation"]["rules"]
        if failure == "altered_survivor":
            rules.reverse()
        else:
            rules.pop(0)
        time = fixtures.CUT_TIME
    with pytest.raises(ValueError):
        ref.excise(raw, d, ["cell_0"], time)


def test_endpoint_energy_no_regulator_store_or_extra_pump_work():
    raw = fixtures.definition()
    c = ref.bind(raw)
    y = ref.initial(c)
    slope = ref.evaluate(c, y, 0.0)[0]
    h = 1e-9
    derivative = (
        ref.snapshot(c, y + h * slope, 0.0)["stored_energy_pJ"]
        - ref.snapshot(c, y - h * slope, 0.0)["stored_energy_pJ"]
    ) / (2 * h)
    d = ref.unpack(c, slope)
    heat = sum(np.sum(v) for k, v in d.items() if k.endswith("dissipated_energy_pJ"))
    supply = np.sum(d["regeneration_supplied_work_pJ"])
    internal = sum(
        np.sum(d[k])
        for k in ("metabolic_work_pJ", "plasma_metabolic_work_pJ", "er_metabolic_work_pJ")
    )
    assert abs(derivative + heat - supply) < 0.02
    assert abs(derivative + heat - supply - internal) > 0.1
    evidence(
        "endpoint-energy",
        dict(
            derivative_pJ_s=derivative,
            heat_pJ_s=float(heat),
            supply_pJ_s=float(supply),
            internal_work_pJ_s=float(internal),
            residual_pJ_s=float(derivative + heat - supply),
        ),
    )


def test_full_38_prefix_cut_suffix_refinement_and_live_regulation():
    raw = fixtures.definition("shadowed")
    c = ref.bind(raw)
    paths, cuts, suffixes = [], [], []
    for refinement in (1, 2):
        paths.append(integrate(raw, end_time=fixtures.CUT_TIME, refinement=refinement))
        cuts.append(ref.excise(raw, paths[-1]["state"][-1], ["cell_1"], fixtures.CUT_TIME))
        suffixes.append(integrate(serialized(cuts[-1]), refinement=refinement))
        for kind, trace in (("prefix", paths[-1]), ("suffix", suffixes[-1])):
            evidence(
                f"{kind}-refinement-{refinement}",
                {k: v for k, v in trace.items() if k not in ("state", "potential_V")},
                dict(state=trace["state"], potential_V=trace["potential_V"]),
            )
    compare(c, paths[0]["state"], paths[1]["state"])
    compare(cuts[0]["context"], suffixes[0]["state"], suffixes[1]["state"])
    before = ref.snapshot(c, ref.initial(c), 0.0)
    pre, post = cuts[0]["audit"]["before"], cuts[0]["audit"]["after"]
    d = ref.unpack(c, paths[0]["state"][-1])
    assert np.max(abs(d["energy_amount_increment_fmol"][:, 1])) > 1e-8
    assert d["er_pump_transferred"][1, 0] > 1e-9
    assert d["er_metabolic_work_pJ"][1] > 1e-8
    np.testing.assert_array_equal(d["amount_increment"][:, 1], 0.0)
    for name, values in d.items():
        np.testing.assert_array_equal(cuts[0]["archive"]["checkpoint"]["state"][name], values)
    for name in ("chemical_amount_fmol", "chemical_moiety_fmol", "er_voltage_V", "inside_charge_C"):
        np.testing.assert_array_equal(post[name], pre[name][[0, 2]])
    np.testing.assert_allclose(
        post["chemical_fixed_charge_C"],
        pre["chemical_fixed_charge_C"][[0, 2]],
        rtol=4e-15,
        atol=5e-23,
    )
    np.testing.assert_array_equal(post["fuel_amount_fmol"], pre["fuel_amount_fmol"][:, [0, 2]])
    assert (
        np.max(
            abs(
                np.asarray(before["network_regulation"]["rule_factors"])
                - pre["network_regulation"]["rule_factors"]
            )
        )
        > 1e-9
    )
    assert cuts[0]["raw"]["model"]["network_regulation"]["rules"] == retained_rules(
        raw, cuts[0]["raw"]
    )
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
    contexts = [c, cuts[0]["context"]]
    endstates = [paths[0]["state"][-1], suffixes[0]["state"][-1]]
    fuel_residual = [fuel_ledger_residual(k, y) for k, y in zip(contexts, endstates, strict=True)]
    chemical_residual = [
        chemical_ledger_residual(k, y) for k, y in zip(contexts, endstates, strict=True)
    ]
    assert max(fuel_residual + chemical_residual) < 3e-11
    energy = [
        balances(c, paths[0]["state"][0], paths[0]["state"][-1], 0.0, fixtures.CUT_TIME),
        balances(
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
            for v in energy
            for k in ("total_energy_residual_pJ", "pool_internal_transfer_residual_pJ")
        )
        < 3e-9
    )
    evidence(
        "complete-regulated-cut-continuation",
        dict(
            audit=cuts[0]["audit"],
            archive=cuts[0]["archive"],
            after_definition=serialized(cuts[0]),
            source_state_fields=38,
            local_zero_fields=35,
            physical_duration_s=fixtures.END_TIME,
            cut_time_s=fixtures.CUT_TIME,
            equilibrium_claim=False,
            native_cut_claim=False,
            maximum_prefix_difference=float(np.max(abs(paths[0]["state"] - paths[1]["state"]))),
            maximum_suffix_difference=float(
                np.max(abs(suffixes[0]["state"] - suffixes[1]["state"]))
            ),
            fuel_ledger_residuals_fmol=fuel_residual,
            chemical_ledger_residuals_fmol=chemical_residual,
            energy_checks=energy,
        ),
    )


def test_no_production_or_accelerator_imports():
    assert not any(k == "cells" or k.startswith(("cells.", "jax", "jaxlib")) for k in sys.modules)
