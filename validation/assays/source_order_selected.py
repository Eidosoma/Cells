"""Confirm the calibration-selected observation schedule on fresh strengths."""

import json
from pathlib import Path

import numpy as np

from validation.assays import source_order_spanning as previous
from validation.assays import two_task
from validation.assays.source_order_spanning import archived_segment as archived_segment
from validation.assays.source_order_spanning import batch as batch
from validation.assays.source_order_spanning import (
    compare_reader_predictions as compare_reader_predictions,
)
from validation.assays.source_order_spanning import definition as definition
from validation.assays.source_order_spanning import ordered as ordered
from validation.assays.source_order_spanning import paired_contrasts as paired_contrasts
from validation.assays.source_order_spanning import reader_reports as reader_reports
from validation.assays.source_order_spanning import reference_reports as reference_reports
from validation.assays.source_order_spanning import world_name as world_name
from validation.betse.spatial_active.refinement import digest

PROTOCOL_PATH = Path(__file__).with_name("source_order_long") / "selected_protocol.json"
SOURCE = previous.protocol()
SOURCE_ROWS = previous.cases(SOURCE)
SELECTED = (("middle128", 2), ("long256", 0), ("long512", 0))


def protocol():
    return json.loads(PROTOCOL_PATH.read_text())


def cases(rule=None):
    return previous.cases(protocol() if rule is None else rule)


def times(rule, panel):
    if panel == "selected320":
        if rule["observation_times_us"][panel] != [128, 160, 320]:
            raise ValueError("Frozen selected schedule changed")
        return np.array([previous.times(rule, name)[i] for name, i in SELECTED])
    return previous.times(rule, panel)


def selected_vectors(parts):
    """Take the fixed time slices, preserving feature units and cell order."""
    values = {}
    for mode, width in (("voltage", 5), ("all_cell_voltage", 7), ("input_at_readout", 5)):
        slices = []
        for panel, index in SELECTED:
            value = np.asarray(parts[panel][mode])
            if value.shape != (3 * width,) or not np.isfinite(value).all():
                raise ValueError("Invalid selected feature support")
            slices.append(value.reshape(3, width)[index])
        values[mode] = np.concatenate(slices)
    histories = [np.asarray(parts[p]["input_history"]) for p, _ in SELECTED]
    for value in histories[1:]:
        np.testing.assert_array_equal(value, histories[0])
    return values | dict(final_voltage=values["voltage"][-5:], input_history=histories[0])


def features(result, rule, panel):
    if panel != "selected320":
        return previous.features(result, rule, panel)
    times(rule, panel)
    return selected_vectors({p: previous.features(result, rule, p) for p, _ in SELECTED})


def historical_source(row):
    """Map unchanged calibration/null histories and the common pre-cue prefix."""
    full = row["split"] == "calibration" or row["arm"] == "no_cue"
    matches = [
        old
        for old in SOURCE_ROWS
        if all(old[k] == row[k] for k in ("arm", "location", "timing"))
        and (
            old["amplitude"] == row["amplitude"]
            if row["split"] == "calibration"
            else old["preparation"] == "calibration_low"
        )
    ]
    if len(matches) != 1:
        raise ValueError("No unique authenticated predecessor case")
    return matches[0], SOURCE["duration_s"] if full else 8e-6


def paired_report(primary, comparator, *, primary_name, comparator_name):
    """Reuse the qualified pairing, with explicit names for both comparators."""
    report = previous.paired_report(primary, comparator)
    categories = dict(
        spanning_only="primary_only", late_only="comparator_only", both="both", neither="neither"
    )
    return dict(
        primary_panel=primary_name,
        comparator_panel=comparator_name,
        counts={categories[k]: v for k, v in report["counts"].items()},
        cases=[
            dict(
                world_id=r["world_id"],
                primary=r["spanning"],
                comparator=r["late"],
                category=categories[r["category"]],
            )
            for r in report["cases"]
        ],
        primary_minus_comparator_resolved_cases=report["spanning_minus_late_resolved_cases"],
        paired_same_trajectories=True,
        scientific_outcome_is_not_an_acceptance_gate=True,
    )


def selected_design(rule):
    """Authenticate the frozen selection without reranking or reading new responses."""
    binding = rule["selection_binding"]
    root = Path(binding["root"])
    assert not (root / "failure.json").exists()
    assert digest(root / "completion.json") == binding["completion_sha256"]
    done = json.loads((root / "completion.json").read_text())
    assert done["status"] == "completed"
    for name in ("inputs", "result", "selection"):
        assert digest(root / (name + ".json")) == done[name + "_sha256"]
    assert done["selection_sha256"] == binding["selection_sha256"]
    inputs = json.loads((root / "inputs.json").read_text())
    selection = json.loads((root / "selection.json").read_text())
    assert selection["inputs_sha256"] == done["inputs_sha256"]
    assert selection["result_sha256"] == done["result_sha256"]
    assert selection["source_binding"] == {
        k: v for k, v in rule["prior_binding"].items() if k != "require_completed_cpu_and_gpu"
    }
    assert selection["status"] == "frozen_before_any_evaluation"
    assert selection["heldout_evaluations"] == 0
    assert selection["backend_comparison"]["winners_agree"]
    design = selection["selection_rule"]
    assert design == inputs["plan"]["design"]
    assert design["cell_ids"] == rule["readout"]["cell_ids"]
    assert design["feature_count"] == 15
    assert design["dt_s"] == rule["dt_s"]
    assert design["calibration_strengths"] == [
        r["amplitude"] for r in rule["preparations"] if r["split"] == "calibration"
    ]
    assert rule["primary_panel"] == "selected320"
    assert rule["paired_comparator_panels"] == ["spanning512", "long512"]
    for backend in ("cpu", "gpu"):
        assert selection["selections"][backend]["times_us"] == [128, 160, 320]
        assert (
            selection["selections"][backend]["times_us"]
            == rule["observation_times_us"][rule["primary_panel"]]
        )
    assert rule["reader"] == SOURCE["reader"]
    for name, sha in inputs["design_sources_sha256"].items():
        assert digest(root / "source" / name) == digest(two_task.ROOT / name) == sha
    return dict(
        status="passed",
        binding=binding,
        selected_times_us=[128, 160, 320],
        frozen_before_new_responses=True,
        heldout_response_reranking=False,
    )


def baseline(rule):
    selection = selected_design(rule)
    accepted = two_task.baseline(rule)
    assert digest(two_task.ROOT / rule["source_protocol"]) == rule["source_protocol_sha256"]
    assert json.loads((two_task.ROOT / rule["source_protocol"]).read_text()) == SOURCE
    for key in (
        "template",
        "template_sha256",
        "dt_s",
        "duration_s",
        "max_steps",
        "readout",
        "reader",
        "source_cell_ids",
        "task_meanings",
        "cue_timing",
        "replay",
        "score_stability",
        "contrast",
        "batch_worlds",
        "window_steps",
        "resources",
        "work",
    ):
        assert rule[key] == SOURCE[key], key
    assert rule["preparations"][:3] == SOURCE["preparations"][:3]
    assert rule["observation_panels"] == SOURCE["observation_panels"] | {"selected320": None}
    assert rule["observation_times_us"] == SOURCE["observation_times_us"] | {
        "selected320": [128, 160, 320]
    }
    registration = json.loads(
        (Path(rule["prior_binding"]["root"]) / "registration.json").read_text()
    )
    assert {str(p.relative_to(two_task.ROOT)) for p in (two_task.ROOT / "src").rglob("*.py")} == {
        name for name in registration["sources_sha256"] if name.startswith("src/")
    }
    return dict(
        status="passed",
        accepted=accepted,
        selected_design=selection,
        production_physics_cues_reader_and_tolerances_unchanged=True,
        new_strength_responses_not_used_to_select_observations=True,
    )
