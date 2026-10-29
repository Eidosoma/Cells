"""Independent removal, archived history, rebuilt fields and continuation."""

import json
import os
import sys
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from validation.tissue import surface_excision_fixtures as fixtures
from validation.tissue import surface_excision_reference as ref


def evidence(name, report, arrays=None):
    if directory := os.environ.get("CELLS_REFERENCE_EVIDENCE"):
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        if arrays is not None:
            np.savez_compressed(root / (name + ".npz"), **arrays)
        (root / (name + ".json")).write_text(
            json.dumps(report, indent=2, allow_nan=False, default=lambda v: v.tolist()) + "\n"
        )


@lru_cache(maxsize=None)
def source_history(arm="open"):
    raw = fixtures.definition(arm)
    result = ref.integrate(raw, end_time=fixtures.CUT_TIME, max_step_s=1e-4)
    return raw, result


def cut(arm="open"):
    raw, history = source_history(arm)
    plan = fixtures.cut_plan(arm)[0]
    return ref.excise(
        raw,
        history["state"][-1],
        plan["removed_cell_ids"],
        plan["time_s"],
        step_index=101,
        event_index=1,
    )


def serialized(transition):
    raw = deepcopy(transition["raw"])
    raw["model"] = dict(
        id=ref.MODEL_ID,
        tissue=raw["model"],
        excision=dict(source=deepcopy(transition["archive"])),
    )
    return raw


def balance(c, initial_state, state, time, start):
    before = ref.snapshot(c, initial_state, start)
    after = ref.snapshot(c, state, time)
    a, b = ref.unpack(c, initial_state), ref.unpack(c, state)
    heat = sum(
        np.sum(b[k] - a[k])
        for k in (
            "membrane_dissipated_energy_pJ",
            "junction_dissipated_energy_pJ",
            "face_dissipated_energy_pJ",
        )
    )
    work = sum(np.sum(b[k] - a[k]) for k in ("reservoir_work_pJ", "electrode_work_pJ"))
    return after["stored_energy_pJ"] - before["stored_energy_pJ"] + heat - work


@pytest.mark.parametrize("arm", fixtures.ARMS)
def test_three_cell_source_fields_are_valid_before_any_cut(arm):
    raw = fixtures.definition(arm)
    c = ref.bind(raw)
    value = ref.snapshot(c, ref.initial(c), 0)
    assert len(c["shapes"]) == 12
    assert np.isfinite(value["potential_V"]).all()
    assert value["field_proof"]["max_charge_residual_C"] < 3e-25


@pytest.mark.parametrize("arm", ["open", "clamped", "blocked", "single-survivor"])
def test_rebased_survivors_preserve_actual_material_fixed_charge_and_full_source_history(arm):
    raw, history = source_history(arm)
    source_state = history["state"][-1].copy()
    before_raw = deepcopy(raw)
    result = cut(arm)
    audit = result["audit"]
    assert raw == before_raw
    np.testing.assert_array_equal(source_state, history["state"][-1])
    assert result["start_time"] == fixtures.CUT_TIME
    assert result["raw"]["execution"]["dt"] == raw["execution"]["dt"]
    assert result["raw"]["model"]["faces"] == raw["model"]["faces"]
    np.testing.assert_array_equal(result["state"], 0)
    assert set(result["archive"]["checkpoint"]["state"]) == set(ref.bind(raw)["shapes"])
    archived = ref.flatten(ref.bind(raw), result["archive"]["checkpoint"]["state"])
    np.testing.assert_array_equal(archived, source_state)
    assert result["archive"]["checkpoint"]["step_index"] == 101
    assert result["archive"]["checkpoint"]["event_index"] == 1
    for row in result["raw"]["model"]["cells"]:
        old = next(v for v in raw["model"]["cells"] if v["id"] == row["id"])
        assert row["volume_pL"] == old["volume_pL"]
        assert row["fixed_charge_equivalent_fmol"] == old["fixed_charge_equivalent_fmol"]
        i = audit["before"]["cell_ids"].index(row["id"])
        np.testing.assert_array_equal(
            list(row["initial_amount_fmol"].values()), audit["before"]["inside_amount_fmol"][:, i]
        )
        assert row["initial_charge_C"] == audit["before"]["inside_charge_C"][i]
    np.testing.assert_array_equal(
        audit["after"]["outside_amount_fmol"], audit["before"]["outside_amount_fmol"]
    )
    np.testing.assert_allclose(
        audit["after"]["inside_amount_fmol"].sum(axis=1) + audit["removed_amount_fmol"],
        audit["before"]["inside_amount_fmol"].sum(axis=1),
        rtol=0,
        atol=2e-13,
    )
    assert all(
        p["inside"] not in audit["removed_cell_ids"] for p in result["raw"]["model"]["membranes"]
    )
    assert all(
        p["sender"] not in audit["removed_cell_ids"]
        and p["receiver"] not in audit["removed_cell_ids"]
        for p in result["raw"]["model"]["junctions"]
    )
    evidence("transition-" + arm, dict(status="passed", **result))


def test_padded_complete_source_checkpoint_is_archived_without_compacting_history():
    raw, history = source_history()
    c = ref.bind(raw)
    compact = ref.unpack(c, history["state"][-1])
    padded = {name: np.pad(v, [(0, 1)] * v.ndim) for name, v in compact.items()}
    result = ref.excise(raw, padded, ["cell_1"], fixtures.CUT_TIME)
    for name, values in padded.items():
        np.testing.assert_array_equal(result["archive"]["checkpoint"]["state"][name], values)


@pytest.mark.parametrize("arm", ["open", "clamped", "single-survivor"])
def test_cut_energy_and_electrode_jump_are_diagnostics_not_forced_conservation(arm):
    result = cut(arm)
    a = result["audit"]
    jump = a["after"]["electrode_charge_C"] - a["before"]["electrode_charge_C"]
    np.testing.assert_array_equal(a["electrode_charge_impulse_C"], jump)
    np.testing.assert_allclose(jump.sum(), a["removed_charge_C"], rtol=3e-12, atol=3e-25)
    expected = 1e12 * sum(
        row["boundary_potential_V"] * v
        for row, v in zip(result["raw"]["model"]["extracellular"], jump, strict=True)
    )
    assert a["maintained_boundary_work_pJ"] == expected
    residual = (
        a["after"]["stored_energy_pJ"]
        - a["before"]["stored_energy_pJ"]
        + a["removed_chemical_energy_pJ"]
        + a["removed_owned_capacitor_energy_pJ"]
        - expected
    )
    assert a["unresolved_cut_energy_pJ"] == residual
    assert abs(residual) > 1e-8 and a["mechanical_work_model"] is False
    assert a["source_native_tissue_equivalence"] is False


def test_removed_only_absolute_clock_is_retained_without_rate_or_state_jump():
    result = cut()
    raw = result["raw"]
    c = result["context"]
    t = 0.001237
    assert t in ref.event_times(raw)
    assert t in result["audit"]["preserved_noop_clock_times"]
    assert result["start_time"] == fixtures.CUT_TIME
    assert raw["experiment"]["observation_times"][0] == fixtures.CUT_TIME
    before, phi, _ = ref.evaluate(c, result["state"], t - 1e-12)
    after, other, _ = ref.evaluate(c, result["state"], t)
    np.testing.assert_array_equal(before, after)
    np.testing.assert_array_equal(phi, other)


def test_noop_preserves_source_identity_and_all_prior_ledgers():
    raw, history = source_history("no-op")
    result = cut("no-op")
    assert result["raw"] == raw and result["audit"]["no_op"]
    np.testing.assert_array_equal(result["state"], history["state"][-1])
    assert any(np.any(v != 0) for v in ref.unpack(ref.bind(raw), result["state"]).values())
    first = ref.integrate(raw, state=result["state"], start_time=fixtures.CUT_TIME)
    second = ref.integrate(raw)
    np.testing.assert_allclose(first["state"][-1], second["state"][-1], rtol=3e-10, atol=3e-12)


@pytest.mark.parametrize("arm", ["closed", "disconnected"])
def test_incompatible_postcut_field_rejects_and_retains_failure_checkpoint(arm):
    raw = fixtures.definition(arm)
    c = ref.bind(raw)
    state = ref.initial(c)
    removed = fixtures.cut_plan(arm)[0]["removed_cell_ids"]
    before = deepcopy(raw)
    with pytest.raises(ref.ExcisionError) as caught:
        ref.excise(raw, state, removed, 0.0)
    assert raw == before
    np.testing.assert_array_equal(state, 0)
    assert caught.value.audit["rejected"] and caught.value.audit["after"] is None
    assert set(caught.value.archive["checkpoint"]["state"]) == set(c["shapes"])
    evidence(
        "expected-rejected-" + arm,
        dict(status="expected_rejection", archive=caught.value.archive, audit=caught.value.audit),
    )


def test_complete_removal_is_terminal_archive_without_runnable_geometry():
    raw, history = source_history()
    result = ref.excise(
        raw, history["state"][-1], [row["id"] for row in raw["model"]["cells"]], fixtures.CUT_TIME
    )
    assert result["raw"] is result["state"] is result["context"] is None
    assert result["audit"]["terminal"] and result["audit"]["after"] is None
    assert result["audit"]["unresolved_cut_energy_pJ"] is None


@pytest.mark.parametrize(
    "fault", ["unknown", "duplicate", "past", "off-grid", "nonfinite", "incomplete"]
)
def test_invalid_transition_inputs_rejected_without_mutation(fault):
    raw = fixtures.definition()
    c = ref.bind(raw)
    state = ref.initial(c)
    time = fixtures.CUT_TIME
    ids = ["cell_1"]
    if fault == "unknown":
        ids = ["missing"]
    elif fault == "duplicate":
        ids = ["cell_1", "cell_1"]
    elif fault == "past":
        time = -1e-6
    elif fault == "off-grid":
        time = 0.0001237
    elif fault == "nonfinite":
        state[0] = np.nan
    else:
        state = state[:-1]
    with pytest.raises(ValueError):
        ref.excise(raw, state, ids, time)


def test_postcut_complete_trajectory_refinement_material_field_and_energy():
    result = cut()
    raw, c = result["raw"], result["context"]
    runs = [
        ref.integrate(raw, state=result["state"], start_time=result["start_time"], refinement=r)
        for r in (1, 2)
    ]
    residuals = []
    for run in runs:
        assert run["times"][0] == result["start_time"] and 0.001237 in run["event_times"]
        residuals.append([])
        for time, state in zip(run["times"], run["state"], strict=True):
            values = ref.unpack(c, state)
            material = (
                values["amount_increment"].sum(axis=1)
                + values["extracellular_amount_increment"].sum(axis=1)
                - values["reservoir_supplied"].sum(axis=1)
            )
            np.testing.assert_allclose(material, 0, rtol=0, atol=3e-13)
            residuals[-1].append(balance(c, result["state"], state, time, result["start_time"]))
        assert max(map(abs, residuals[-1])) < 3e-9
    np.testing.assert_allclose(runs[0]["state"], runs[1]["state"], rtol=2e-8, atol=3e-11)
    evidence(
        "postcut-refinement",
        dict(
            status="passed",
            absolute_start_s=result["start_time"],
            end_s=raw["experiment"]["end_time"],
            events=runs[0]["event_times"],
            energy_residuals_pJ=residuals,
            evaluations=[v["evaluations"] for v in runs],
            fields=12,
            cut_energy_closure_claim=False,
        ),
        dict(
            times=np.asarray(runs[0]["times"]),
            state=runs[0]["state"],
            refined_state=runs[1]["state"],
        ),
    )


def test_sequential_cuts_keep_distinct_local_ledgers_and_absolute_time():
    first = cut("sequential")
    first_definition = serialized(first)
    second_time = fixtures.cut_plan("sequential")[1]["time_s"]
    evolved = ref.integrate(first_definition, state=first["state"], end_time=second_time)
    second = ref.excise(first_definition, evolved["state"][-1], ["cell_0"], second_time)
    assert [v["id"] for v in second["raw"]["model"]["cells"]] == ["cell_2"]
    np.testing.assert_array_equal(second["state"], 0)
    assert second["archive"]["checkpoint"]["time"] == second_time > first["start_time"]
    assert second["archive"]["definition"]["model"]["excision"]["source"] == first["archive"]
    assert any(np.any(v) for v in second["archive"]["checkpoint"]["state"].values())
    final = ref.integrate(second["raw"], state=second["state"], start_time=second_time)
    assert (
        abs(
            balance(
                second["context"],
                second["state"],
                final["state"][-1],
                final["times"][-1],
                second_time,
            )
        )
        < 3e-9
    )
    evidence(
        "sequential",
        dict(
            status="passed",
            first_archive=first["archive"],
            second_archive=second["archive"],
            first_cut_diagnostic=first["audit"],
            second_cut_diagnostic=second["audit"],
            absolute_final_time_s=final["times"][-1],
        ),
    )


def test_new_serialization_origin_reads_tissue_and_archived_time_without_history_replay():
    transition = cut()
    raw = serialized(transition)
    context = ref.bind(raw)
    assert context["origin_time"] == transition["start_time"]
    np.testing.assert_array_equal(ref.initial(context), 0)
    run = ref.integrate(raw, end_time=transition["start_time"] + 2 * fixtures.DT)
    assert run["times"][0] == transition["start_time"]
    assert not any(name == "cells" or name.startswith(("cells.", "jax")) for name in sys.modules)
