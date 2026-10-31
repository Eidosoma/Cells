"""Deferred native pre-mesh deletion, owner ledger and cut continuation refusal checks."""

import copy
import json
import os
import subprocess
import sys
import traceback
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_native_cut_lifecycle as cut
from validation.topology import betse_native_cut_lifecycle_fixtures as fixtures
from validation.topology import betse_native_cut_lifecycle_records as records


def root(tmp_path):
    return Path(os.environ.get("CELLS_COMPONENT_EVIDENCE", str(tmp_path))) / "native-cut-lifecycle"


def archive(folder, name, value):
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / (name + ".json")).open("x") as stream:
        stream.write(records.snapshot(value) + "\n")


def plain(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {key: plain(v) for key, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    return value


def native(folder, source):
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "inputs.json").write_text(records.snapshot(source) + "\n")
    with (folder / "stdout.log").open("x") as output:
        subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "validation.topology.betse_native_cut_lifecycle_native",
                "--inputs",
                str(folder / "inputs.json"),
                "--output",
                str(folder / "result.json"),
            ],
            check=True,
            timeout=180,
            stdout=output,
            stderr=subprocess.STDOUT,
        )
    result = json.loads((folder / "result.json").read_text())
    assert result["production_imports_denied"] and not result["loaded_production_modules"]
    assert result["complete_native_cut"] is result["physical_mesh_qualified"] is False
    assert result["geometry_calls_executed"] == 0
    return result


def reference(folder, inputs):
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "inputs.json").write_text(json.dumps(inputs, indent=2, allow_nan=False) + "\n")
    with (folder / "stdout.log").open("x") as output:
        subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "validation.topology.betse_native_cut_lifecycle_reference",
                "--inputs",
                str(folder / "inputs.json"),
                "--output",
                str(folder / "result.json"),
            ],
            check=True,
            timeout=180,
            stdout=output,
            stderr=subprocess.STDOUT,
        )
    result = json.loads((folder / "result.json").read_text())
    assert result["production_imports_denied"] and not result["loaded_production_modules"]
    assert result["decimal_precision"] == 80 and result["carried_reference_forms"] == 0
    return result


def begin(inputs):
    topology = cut.ownership.topology_from_dict(inputs["topology"])
    fields = {
        name: cut.ownership.OwnedField(**row) for name, row in inputs["field_declarations"].items()
    }
    return cut.begin("a" * 64, topology, inputs["removed_cell_ids"], fields, **inputs["source"])


def captured_begin(inputs, folder, *, stage):
    """Retain the complete attempted prefix if construction fails unexpectedly."""
    try:
        return begin(inputs)
    except BaseException as error:
        archive(
            folder,
            stage + "-failure",
            dict(
                stage=stage,
                type=type(error).__name__,
                message=str(error),
                traceback=traceback.format_exc(),
                trial=getattr(error, "trial", None),
                trial_available=getattr(error, "trial", None) is not None,
                unexpected_failure=True,
                positive_credit=False,
                automatic_retry=False,
            ),
        )
        raise


def compare_native(trial, captured):
    assert trial.before_json == captured["before_json"]
    assert trial.after_json == captured["after_json"]
    assert trial.source_prefix_completed is captured["source_prefix_completed"]
    if trial.failure_json is None:
        assert captured["failure"] is None
    else:
        actual = json.loads(trial.failure_json)
        assert actual["type"] == captured["failure"]["type"]
        assert actual["message"] == captured["failure"]["message"]
    assert not trial.complete_native_cut


@pytest.mark.parametrize("case", fixtures.CASES)
def test_native_cut_prefix(tmp_path, case):
    inputs = fixtures.fixture(case)
    folder = root(tmp_path) / case
    archive(folder, "inputs-before-constructors", inputs)
    incoming = cut.snapshot(inputs["source"])
    reference_inputs = dict(
        source_graph=incoming,
        topology=inputs["topology"],
        removed_cell_ids=inputs["removed_cell_ids"],
        field_declarations=plain(inputs["field_declarations"]),
    )
    wanted = reference(folder / "independent", reference_inputs)
    # Actual supplied inputs are archived before either implementation/reference.
    epoch = captured_begin(inputs, folder, stage="positive-prefix")
    archive(folder, "actual-prefix-return", epoch)
    captured = native(folder / "native", inputs["source"])
    compare_native(epoch.trial, captured)
    assert cut.snapshot(inputs["source"]) == incoming
    after = records.restore(epoch.trial.after_json)
    np.testing.assert_array_equal(
        after["sim"]["hurt_mask"], wanted["source_hurt_mask_after_delete"]
    )
    plan = epoch.stable_removal.plan
    for domain in cut.ownership.DOMAINS:
        np.testing.assert_array_equal(
            plan.new_to_old[domain], wanted["stable_plan"]["new_to_old"][domain]
        )
        np.testing.assert_array_equal(
            plan.old_to_new[domain], wanted["stable_plan"]["old_to_new"][domain]
        )
    amount_metrics = {}
    for name, row in epoch.stable_removal.fields.items():
        target = wanted["fields"][name]
        for key, value in row._asdict().items():
            if value is None:
                assert target[key] is None
            elif inputs["field_declarations"][name]["kind"] == "state" or key in (
                "retained",
                "removed_values",
            ):
                np.testing.assert_array_equal(value, target[key])
            else:
                budget = 2e-12 + 5e-12 * abs(np.asarray(target[key]))
                metric = float(
                    np.max(abs(np.asarray(value) - np.asarray(target[key])) / budget, initial=0)
                )
                amount_metrics[name + "/" + key] = metric
                assert metric <= 1
    with pytest.raises(cut.CutContinuationRejected) as blocked:
        cut.require_ordinary_continuation(epoch)
    archive(
        folder,
        "continuation-refusal",
        dict(epoch=blocked.value.epoch, capabilities=blocked.value.partial),
    )
    assert blocked.value.partial["physical_mesh_qualified"] is False
    assert blocked.value.partial["ordinary_checkpoint_ready"] is False
    assert epoch.invalidated == cut.REQUIRED_OWNERS
    if case == "no_cells":
        assert not plan.changed and epoch.invalidated
    if case == "global_length_collision":
        assert len(after["sim"]["global_marker"]) == 3
        assert len(inputs["source"]["simulator_fields"]["global_marker"]) == 4
    (folder / "comparison.json").write_text(
        json.dumps(
            dict(
                completed=True,
                exact_native_prefix=True,
                fresh_reference_forms=1,
                carried_reference_forms=0,
                retained_prefix_and_sink_ledgers=True,
                amount_metrics=amount_metrics,
                ordinary_continuation_refused=True,
                source_mesh_calls=0,
                complete_native_cut=False,
                physical_mesh_qualified=False,
                physical_global_conservation_credit=False,
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.mark.parametrize("case", fixtures.RAW_CASES)
def test_native_cut_raw_partial(tmp_path, case):
    inputs = fixtures.fixture(case)
    folder = root(tmp_path) / case
    archive(folder, "raw-inputs", inputs)
    parent = cut.snapshot(inputs["source"])
    trial = cut.capture_prefix(**inputs["source"])
    archive(folder, "raw-complete-available-return", trial)
    captured = native(folder / "native", inputs["source"])
    compare_native(trial, captured)
    assert cut.snapshot(inputs["source"]) == parent
    after = records.restore(trial.after_json)
    assert "available_source_locals" in after
    expected = dict(
        list_last_index="IndexError",
        empty_list_index="TypeError",
        nested_unknown_first="UnboundLocalError",
        scalar_array="TypeError",
        duplicate_list_removal="IndexError",
    )
    if case in expected:
        assert not trial.source_prefix_completed
        assert json.loads(trial.failure_json)["type"] == expected[case]
    else:
        assert trial.source_prefix_completed
        if case == "nested_unknown_late":
            assert len(after["sim"]["cc_mems"][0]) == 3
            np.testing.assert_array_equal(after["sim"]["cc_mems"][0], [0, 2, 3])
        elif case == "species_grid_collision":
            assert after["sim"]["cc_env"].shape == (17,)
        else:
            assert case == "alias_list_mutation"
            assert after["sim"]["alias_first"] == [2]
            assert after["sim"]["alias_second"] == [0, 2, 3]
    if case in ("list_last_index", "duplicate_list_removal"):
        assert after["sim"]["witness_list"] == [0, 1, 2]
    (folder / "raw-retention.json").write_text(
        json.dumps(
            dict(
                positive_credit=False,
                complete_raw_native_and_port_evidence=True,
                source_prefix_completed=trial.source_prefix_completed,
                native_failure_type=None
                if captured["failure"] is None
                else captured["failure"]["type"],
                strict_ordinary_continuation_credit=False,
                complete_native_cut=False,
                physical_mesh_qualified=False,
                geometry_calls=0,
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.mark.parametrize("dependency", fixtures.DEPENDENCIES)
def test_native_cut_capabilities(tmp_path, dependency):
    inputs = fixtures.fixture()
    folder = root(tmp_path) / ("dependency-" + dependency)
    archive(folder, "valid-inputs", inputs)
    epoch = captured_begin(inputs, folder, stage="dependency-baseline")
    archive(folder, "valid-prefix-return", epoch)
    if dependency == "complete_metadata_is_not_checkpoint":
        for owner in cut.REQUIRED_OWNERS:
            chain = json.loads(epoch.rebind_json)
            predecessor = epoch.trial.identity if not chain else chain[-1]["output_identity"]
            epoch = cut.record_rebind(
                epoch,
                owner=owner,
                input_identity=predecessor,
                output_identity="b" * 64,
                artifact_sha256="c" * 64,
                provenance=(
                    "Explicit supplied metadata only; no geometry or checkpoint qualification"
                ),
            )
        assert cut.capabilities(epoch)["missing_owners"] == []
    if dependency in ("missing_geometry", "complete_metadata_is_not_checkpoint"):
        with pytest.raises(cut.CutContinuationRejected) as caught:
            cut.require_ordinary_continuation(epoch)
        error = caught.value
        assert error.partial["ordinary_checkpoint_ready"] is False
    elif dependency in ("changed_trial", "changed_epoch"):
        changed = (
            replace(epoch, identity="0" * 64)
            if dependency == "changed_epoch"
            else replace(epoch, trial=replace(epoch.trial, after_json="{}"))
        )
        archive(folder, "malformed-epoch", changed)
        with pytest.raises(ValueError) as caught:
            cut.capabilities(changed)
        error = caught.value
    elif dependency in ("wrong_rebind_order", "wrong_rebind_parent", "missing_rebind_artifact"):
        with pytest.raises(ValueError) as caught:
            cut.record_rebind(
                epoch,
                owner=cut.REQUIRED_OWNERS[1 if dependency == "wrong_rebind_order" else 0],
                input_identity="d" * 64
                if dependency == "wrong_rebind_parent"
                else epoch.trial.identity,
                output_identity="b" * 64,
                artifact_sha256="" if dependency == "missing_rebind_artifact" else "c" * 64,
                provenance="Supplied malformed prerequisite probe",
            )
        error = caught.value
    else:
        changed = copy.deepcopy(inputs)
        if dependency == "wrong_target_cells":
            changed["source"]["selection"]["cells"] = np.array([0])
        elif dependency == "wrong_target_membranes":
            changed["source"]["selection"]["membranes"] = np.array([0])
        elif dependency == "legacy_ER_requested":
            changed["source"]["parameters"]["Ca_dyn"] = True
        archive(folder, "malformed-inputs", changed)
        if dependency == "malformed_parent_epoch":
            topology = cut.ownership.topology_from_dict(changed["topology"])
            with pytest.raises(ValueError) as caught:
                cut.begin("unowned", topology, changed["removed_cell_ids"], {}, **changed["source"])
        else:
            with pytest.raises(ValueError) as caught:
                begin(changed)
        error = caught.value
    expected_type = (
        "CutContinuationRejected"
        if dependency in ("missing_geometry", "complete_metadata_is_not_checkpoint")
        else ("ValueError")
    )
    expected_message = {
        "missing_geometry": (
            "Cut continuation requires qualified changing geometry and an actual "
            "typed post-cut checkpoint"
        ),
        "complete_metadata_is_not_checkpoint": (
            "Cut continuation requires qualified changing geometry and an actual "
            "typed post-cut checkpoint"
        ),
        "changed_trial": "Changed native prefix evidence",
        "changed_epoch": "Require unchanged complete prefix and separate stable-owner evidence",
        "wrong_rebind_order": (
            "Cut rebind evidence is missing, repeated or outside declared dependency order"
        ),
        "wrong_rebind_parent": (
            "Cut owner evidence must bind its actual predecessor and complete artifact"
        ),
        "missing_rebind_artifact": (
            "Cut owner evidence must bind its actual predecessor and complete artifact"
        ),
        "wrong_target_cells": (
            "Primary prefix picker targets must match explicit stable owner removal"
        ),
        "wrong_target_membranes": (
            "Primary prefix picker targets must match explicit stable owner removal"
        ),
        "malformed_parent_epoch": "Require the actual supplied parent epoch identity",
        "legacy_ER_requested": (
            "This ordinary ECM prefix requires actual is_ecm True/Ca_dyn False owners"
        ),
    }[dependency]
    assert type(error).__name__ == expected_type and str(error) == expected_message
    archive(
        folder,
        "refusal",
        dict(
            type=type(error).__name__, message=str(error), partial=getattr(error, "partial", None)
        ),
    )
    (folder / "dependency.json").write_text(
        json.dumps(
            dict(
                baseline_admitted=True,
                intended_failure_reached=True,
                actual_type=type(error).__name__,
                actual_message=str(error),
                expected_type=expected_type,
                expected_message=expected_message,
                ordinary_checkpoint_ready=False,
                source_failure_credit=False,
            ),
            indent=2,
        )
        + "\n"
    )
