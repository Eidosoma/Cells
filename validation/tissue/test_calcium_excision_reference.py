"""Independent chemical ownership, charge anchors and bounded cut continuation."""

import json
import os
import sys
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from validation.tissue import calcium_excision_fixtures as fixtures
from validation.tissue import calcium_excision_reference as ref


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
def prefix(refinement=1):
    return integrate(fixtures.definition(), end_time=fixtures.CUT_TIME, refinement=refinement)


def serialized(cut):
    raw = deepcopy(cut["raw"])
    raw["model"] = dict(
        id=ref.MODEL_ID,
        tissue=raw["model"],
        excision=dict(
            law="conservative_tissue_removal_remap@1",
            state_policy="rebase_chemical_owners_preserve_gates_archive_complete_source@1",
            reference_policy="free_cytosol_anchor_with_conserved_whole_cell_charge@1",
            clock_policy="absolute_time_original_nominal_grid@1",
            energy_policy="record_jump_without_cut_work_law@1",
            ordering="right_continuous_controls_then_removal@1",
            removed_cell_ids=cut["audit"]["removed_cell_ids"],
            source=deepcopy(cut["archive"]),
        ),
    )
    return raw


def compare(c, a, b, *, rtol=2e-8, atol=3e-11):
    for name, values in ref.unpack(c, a).items():
        np.testing.assert_allclose(
            values,
            ref.unpack(c, b)[name],
            rtol=rtol,
            atol=3e-25 if name.endswith("_C") else atol,
            err_msg=name,
        )


def energy_balance(c, before, after, start, end):
    a, b = ref.unpack(c, before), ref.unpack(c, after)
    heat = sum(np.sum(b[k] - a[k]) for k in c["shapes"] if k.endswith("dissipated_energy_pJ"))
    work = sum(
        np.sum(b[k] - a[k])
        for k in (
            "reservoir_work_pJ",
            "electrode_work_pJ",
            "metabolic_work_pJ",
            "plasma_metabolic_work_pJ",
            "er_metabolic_work_pJ",
        )
    )
    return (
        ref.snapshot(c, after, end)["stored_energy_pJ"]
        - ref.snapshot(c, before, start)["stored_energy_pJ"]
        + heat
        - work
    )


def chemical_ledger_residual(c, state):
    d = ref.unpack(c, state)
    residual = 0.0
    for i, store in enumerate(c["stores"]):
        expected = np.zeros_like(store.n0)
        for j, reaction in enumerate(store.reactions):
            owner = store.owners.index(reaction["compartment"])
            for name in store.ids:
                coefficient = reaction["products"].get(name, 0) - reaction["reactants"].get(name, 0)
                expected[store.ids.index(name), owner] += coefficient * d["reaction_extent"][i, j]
        transported = d["er_passive_transferred"][i].copy()
        transported[store.ca] += d["er_pump_transferred"][i, 0] + d["er_release_transferred"][i, 0]
        expected[:, store.cy] -= transported
        expected[:, store.er] += transported
        for j, species in enumerate(c["raw"]["model"]["species"]):
            expected[store.ids.index(species["id"]), store.cy] += d["amount_increment"][j, i]
        residual = max(residual, np.max(abs(d["chemical_amount_increment"][i] - expected)))
    return float(residual)


def total_moieties(snapshot):
    value = snapshot["chemical_moiety_fmol"].sum(axis=(0, 2))
    for j, species in enumerate(snapshot["species_ids"]):
        value[snapshot["moiety_ids"].index(species)] += snapshot["outside_amount_fmol"][j].sum()
    return value


@pytest.mark.parametrize("catalog", ["compact", "full"])
@pytest.mark.parametrize("arm", ["open", "blocked", "reordered", "empty"])
def test_all_34_stage_fields_and_independent_energy_proof(catalog, arm):
    raw = fixtures.definition(arm, catalog=catalog, padded=True)
    c = ref.bind(raw)
    y = ref.initial(c)
    slope, phi, proof = ref.evaluate(c, y, 0.0)
    d = ref.unpack(c, slope)
    assert len(d) == 34 and np.isfinite(slope).all()
    assert abs(proof["physical_energy_balance_pJ_s"]) < 5e-8
    m = c["raw"]["model"]
    if catalog == "full" and arm != "empty":
        assert len({p["kinetic_law"] for p in m["channels"]}) == 56
    removed = [p["id"] for p in m["cells"]].index("cell_1")
    np.testing.assert_array_equal(d["amount_increment"][:, removed], 0.0)
    assert np.max(abs(d["chemical_amount_increment"][removed])) > 0
    assert np.max(abs(d["reaction_extent"][removed])) > 0
    assert np.max(abs(d["er_passive_transferred"][removed])) > 0
    snap = ref.snapshot(c, y, 0.0)
    np.testing.assert_allclose(snap["inside_charge_C"][removed], 0.0, atol=0)
    np.testing.assert_allclose(snap["potential_V"], phi, atol=3e-12)
    assert all(not v["reservoir"] for v in m["extracellular"])
    evidence(
        f"stage-{catalog}-{arm}", dict(proof=proof, snapshot=snap), dict(state=y, derivative=slope)
    )


def test_energy_directional_derivative_includes_bound_species_and_er_capacitor():
    c = ref.bind(fixtures.definition())
    y = ref.initial(c)
    slope = ref.evaluate(c, y, 0.0)[0]
    epsilon = 1e-9
    estimate = (
        ref.snapshot(c, y + epsilon * slope, 0.0)["stored_energy_pJ"]
        - ref.snapshot(c, y - epsilon * slope, 0.0)["stored_energy_pJ"]
    ) / (2 * epsilon)
    d = ref.unpack(c, slope)
    heat = sum(np.sum(v) for k, v in d.items() if k.endswith("dissipated_energy_pJ"))
    work = sum(
        np.sum(d[k])
        for k in ("metabolic_work_pJ", "plasma_metabolic_work_pJ", "er_metabolic_work_pJ")
    )
    assert abs(estimate + heat - work) < 0.02
    evidence(
        "endpoint-directional-energy",
        dict(
            energy_derivative_pJ_s=estimate,
            heat_pJ_s=heat,
            maintained_work_pJ_s=work,
            residual_pJ_s=estimate + heat - work,
            finite_difference_seconds=epsilon,
        ),
    )


@pytest.mark.parametrize("catalog", ["compact", "full"])
def test_initial_neutral_cut_keeps_all_three_gate_fields_and_exact_store_parameters(catalog):
    raw = fixtures.definition(catalog=catalog, padded=True)
    c = ref.bind(raw)
    y = ref.initial(c)
    cut = ref.excise(raw, y, ["cell_1"], 0.0)
    post = ref.unpack(cut["context"], cut["state"])
    old = ref.unpack(c, y)
    for name, values in post.items():
        if name not in ref.GATES:
            np.testing.assert_array_equal(values, 0.0)
    old_m, new_m = c["raw"]["model"], cut["context"]["raw"]["model"]
    for field, owners in (("channel_gate", "channels"), ("junction_gate", "junctions")):
        indices = {p["id"]: i for i, p in enumerate(old_m[owners])}
        expected = [indices[p["id"]] for p in new_m[owners]]
        np.testing.assert_array_equal(post[field], old[field][..., expected])
    patches = {p["id"]: i for i, p in enumerate(old_m["membranes"])}
    np.testing.assert_array_equal(
        post["calcium_gate"], old["calcium_gate"][:, [patches[p["id"]] for p in new_m["membranes"]]]
    )
    old_stores = {p["cell_id"]: p["model"] for p in raw["model"]["stores"]}
    for row in cut["raw"]["model"]["stores"]:
        assert row["model"] == old_stores[row["cell_id"]]
    assert len(cut["archive"]["checkpoint"]["state"]) == 34
    assert set(ref.event_times(raw)) <= set(ref.event_times(cut["raw"]))


def test_charged_removal_is_refused_with_complete_failed_evidence():
    raw = fixtures.definition("charged")
    c = ref.bind(raw)
    with pytest.raises(ref.ExcisionError) as caught:
        ref.excise(raw, ref.initial(c), ["cell_0"], 0.0)
    error = caught.value
    assert len(error.archive["checkpoint"]["state"]) == 34
    assert error.audit["rejected"]
    assert abs(error.audit["removed_charge_C"]) > 1e-14
    evidence(
        "expected-charged-removal-refusal",
        dict(exception=str(error), archive=error.archive, audit=error.audit),
    )


@pytest.mark.parametrize("arm", ["no-op", "terminal", "single-survivor", "sequential"])
def test_noop_terminal_and_compatible_multiple_removal(arm):
    raw = fixtures.definition(arm)
    c = ref.bind(raw)
    y = ref.initial(c)
    removed = fixtures.cut_plan(arm)[0]["removed_cell_ids"]
    cut = ref.excise(raw, y, removed, 0.0)
    if arm == "no-op":
        assert cut["raw"] == raw
        np.testing.assert_array_equal(cut["state"], y)
    elif arm == "terminal":
        assert cut["raw"] is cut["state"] is cut["context"] is None
        assert cut["audit"]["after"] is None
        np.testing.assert_allclose(
            cut["audit"]["removed_chemical_amount_fmol"],
            cut["audit"]["before"]["chemical_amount_fmol"].sum(axis=0),
        )
    elif arm == "single-survivor":
        assert [v["id"] for v in cut["raw"]["model"]["ionic"]["cells"]] == ["cell_2"]
    else:
        again = ref.excise(serialized(cut), cut["state"], ["cell_0"], 0.0)
        assert [v["id"] for v in again["raw"]["model"]["ionic"]["cells"]] == ["cell_2"]
        assert again["archive"]["definition"]["model"]["excision"]["source"] == cut["archive"]


@pytest.mark.parametrize(
    "failure",
    [
        "partial",
        "nan",
        "negative_chemical",
        "calcium_gate",
        "stateless_gate",
        "duplicate",
        "unknown",
        "off_grid",
        "anchor",
    ],
)
def test_strict_source_and_cut_guards(failure):
    raw = fixtures.definition()
    c = ref.bind(raw)
    fields = ref.unpack(c, ref.initial(c))
    removed, time = ["cell_1"], 0.0
    if failure == "partial":
        fields.pop("er_metabolic_work_pJ")
    elif failure == "nan":
        fields["reaction_extent"][0, 0] = float("nan")
    elif failure == "negative_chemical":
        fields["chemical_amount_increment"][0, 0, 0] = -1000
    elif failure == "calcium_gate":
        fields["calcium_gate"][0, 0] = 1.01
    elif failure == "stateless_gate":
        index = next(
            i for i, row in enumerate(raw["model"]["ionic"]["channels"]) if not row["initial_gate"]
        )
        fields["channel_gate"][0, index] = 0.1
    elif failure == "duplicate":
        removed *= 2
    elif failure == "unknown":
        removed = ["absent"]
    elif failure == "off_grid":
        time = 0.1 * fixtures.DT
    elif failure == "anchor":
        raw["model"]["ionic"]["cells"][0]["initial_amount_fmol"]["Ca"] += 0.001
    with pytest.raises(ValueError):
        ref.excise(raw, fields, removed, time)


def test_full_34_prefix_cut_suffix_refinement_and_physical_owner_conservation():
    raw = fixtures.definition()
    c = ref.bind(raw)
    paths, cuts, suffixes = [], [], []
    for refinement in (1, 2):
        paths.append(prefix(refinement))
        cuts.append(
            ref.excise(
                raw,
                paths[-1]["state"][-1],
                ["cell_1"],
                fixtures.CUT_TIME,
                step_index=40,
                event_index=7,
            )
        )
        suffixes.append(integrate(serialized(cuts[-1]), refinement=refinement))
    compare(c, paths[0]["state"], paths[1]["state"])
    compare(cuts[0]["context"], suffixes[0]["state"], suffixes[1]["state"])
    before = ref.snapshot(c, ref.initial(c), 0.0)
    final_prefix = cuts[0]["audit"]["before"]
    post = cuts[0]["audit"]["after"]
    delta = ref.unpack(c, paths[0]["state"][-1])
    assert np.max(abs(delta["chemical_amount_increment"][1])) > 1e-8
    np.testing.assert_array_equal(delta["amount_increment"][:, 1], 0.0)
    assert np.max(abs(final_prefix["er_voltage_V"])) > 1e-8
    assert np.max(abs(delta["reaction_extent"])) > 1e-8
    assert np.max(abs(delta["er_passive_transferred"])) > 1e-8
    assert abs(final_prefix["inside_charge_C"][1]) == 0
    for snapshot in (final_prefix, post):
        np.testing.assert_allclose(
            snapshot["chemical_fixed_charge_C"],
            snapshot["current_chemical_fixed_charge_C"],
            rtol=4e-15,
            atol=5e-23,
        )
    for name in (
        "chemical_amount_fmol",
        "chemical_moiety_fmol",
        "er_voltage_V",
        "inside_charge_C",
        "chemical_fixed_charge_C",
    ):
        if name == "chemical_fixed_charge_C":
            np.testing.assert_allclose(
                post[name], final_prefix[name][[0, 2]], rtol=4e-15, atol=5e-23
            )
        else:
            np.testing.assert_array_equal(post[name], final_prefix[name][[0, 2]])
    np.testing.assert_array_equal(
        post["free_cytosol_amount_fmol"], final_prefix["free_cytosol_amount_fmol"][:, [0, 2]]
    )
    assert (
        np.max(abs(final_prefix["free_cytosol_amount_fmol"] - c["ai"] - delta["amount_increment"]))
        > 1e-8
    )
    assert set(ref.event_times(raw)) <= set(ref.event_times(serialized(cuts[0])))
    assert suffixes[0]["start_time"] == fixtures.CUT_TIME
    assert suffixes[0]["times"][0] == fixtures.CUT_TIME
    assert min(suffixes[0]["event_times"]) == fixtures.CUT_TIME
    final = ref.snapshot(cuts[0]["context"], suffixes[0]["state"][-1], fixtures.END_TIME)
    np.testing.assert_allclose(
        total_moieties(before),
        total_moieties(final) + cuts[0]["audit"]["removed_moiety_fmol"],
        rtol=2e-14,
        atol=3e-11,
    )
    residuals = [
        chemical_ledger_residual(c, paths[0]["state"][-1]),
        chemical_ledger_residual(cuts[0]["context"], suffixes[0]["state"][-1]),
    ]
    assert max(residuals) < 3e-11
    energies = [
        energy_balance(c, paths[0]["state"][0], paths[0]["state"][-1], 0.0, fixtures.CUT_TIME),
        energy_balance(
            cuts[0]["context"],
            suffixes[0]["state"][0],
            suffixes[0]["state"][-1],
            fixtures.CUT_TIME,
            fixtures.END_TIME,
        ),
    ]
    assert max(abs(v) for v in energies) < 3e-9
    for j in range(2):
        evidence(
            f"prefix-refinement-{j + 1}",
            {k: v for k, v in paths[j].items() if k not in ("state", "potential_V")},
            dict(state=paths[j]["state"], potential_V=paths[j]["potential_V"]),
        )
        evidence(
            f"suffix-refinement-{j + 1}",
            {k: v for k, v in suffixes[j].items() if k not in ("state", "potential_V")},
            dict(state=suffixes[j]["state"], potential_V=suffixes[j]["potential_V"]),
        )
    evidence(
        "complete-cut-continuation",
        dict(
            audit=cuts[0]["audit"],
            archive=cuts[0]["archive"],
            after_definition=serialized(cuts[0]),
            source_state_fields=34,
            local_zero_fields=31,
            physical_duration_s=fixtures.END_TIME,
            cut_time_s=fixtures.CUT_TIME,
            equilibrium_claim=False,
            native_cut_claim=False,
            maximum_prefix_difference=float(np.max(abs(paths[0]["state"] - paths[1]["state"]))),
            maximum_suffix_difference=float(
                np.max(abs(suffixes[0]["state"] - suffixes[1]["state"]))
            ),
            chemical_ledger_residuals_fmol=residuals,
            continuous_energy_residuals_pJ=energies,
        ),
    )


def test_no_production_or_accelerator_imports():
    assert not any(
        name == "cells" or name.startswith(("cells.", "jax", "jaxlib")) for name in sys.modules
    )
