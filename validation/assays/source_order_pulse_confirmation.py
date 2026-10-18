"""Confirm a calibration-selected pulse protocol on predeclared fresh strengths."""

import json
from pathlib import Path

from validation.assays import source_order_pulse_spacing as spacing
from validation.assays import source_order_selected as selected
from validation.assays import two_task
from validation.assays.source_order_pulse_spacing import archived_segment as archived_segment
from validation.assays.source_order_pulse_spacing import batch as batch
from validation.assays.source_order_pulse_spacing import definition as definition
from validation.assays.source_order_pulse_spacing import features as features
from validation.assays.source_order_pulse_spacing import ordered as ordered
from validation.assays.source_order_pulse_spacing import paired_contrasts as paired_contrasts
from validation.assays.source_order_pulse_spacing import times as times
from validation.assays.source_order_pulse_spacing import world_name as world_name
from validation.assays.source_order_selected import (
    compare_reader_predictions as compare_reader_predictions,
)
from validation.assays.source_order_selected import paired_report as paired_report
from validation.assays.source_order_selected import reader_reports as reader_reports
from validation.assays.source_order_selected import reference_reports as reference_reports
from validation.betse.spatial_active.refinement import digest

PROTOCOL_PATH = Path(__file__).with_name("source_order_long") / "pulse_confirmation_protocol.json"
SOURCE = spacing.protocol()
SOURCE_ROWS = spacing.cases(SOURCE)
STRENGTHS = [0.403125, 0.453125, 0.503125, 0.553125, 0.646875, 0.696875, 0.746875, 0.796875]


def protocol():
    return json.loads(PROTOCOL_PATH.read_text())


def cases(rule=None):
    return selected.cases(protocol() if rule is None else rule)


def historical_source(row):
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
        raise ValueError("No unique authenticated pulse-spacing predecessor case")
    return matches[0], SOURCE["duration_s"] if full else 8e-6


def selected_design(rule):
    """Bind the existing geometric choice without reranking any response."""
    root = Path(rule["prior_binding"]["root"])
    assert not (root / "failure.json").exists()
    assert digest(root / "registration.json") == rule["prior_binding"]["registration_sha256"]
    assert digest(root / "completion.json") == rule["prior_binding"]["completion_sha256"]
    registration = json.loads((root / "registration.json").read_text())
    done = json.loads((root / "completion.json").read_text())
    assert done["status"] == "completed"
    assert digest(root / "result.json") == done["result_sha256"]
    assert digest(root / "component-protocol.json") == registration["component_protocol_sha256"]
    assert json.loads((root / "component-protocol.json").read_text()) == SOURCE
    assert digest(two_task.ROOT / rule["source_protocol"]) == rule["source_protocol_sha256"]
    assert json.loads((two_task.ROOT / rule["source_protocol"]).read_text()) == SOURCE
    binding = rule["selection_binding"]
    relative = binding["relative_path"]
    assert relative == "evidence/gpu/source-order-pulse-spacing-selection.json"
    assert digest(root / relative) == binding["sha256"] == done["evidence_sha256"][relative]
    saved = json.loads((root / relative).read_text())
    assert saved["status"] == "passed"
    choice = saved["selection"]
    assert choice == spacing.combined_selection(
        saved["comparisons"]["cpu"], saved["comparisons"]["gpu"]
    )
    assert choice["status"] == "frozen_before_any_fresh_confirmation"
    assert choice["reproducible_improvement"] and choice["winners_agree"]
    assert choice["selected_onset_separation_us"] == 104
    assert saved["heldout_cases_evaluated"] == choice["heldout_cases_evaluated"] == 0
    assert saved["protocol_sha256"] == rule["source_protocol_sha256"]
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
        "observation_panels",
        "observation_times_us",
        "primary_panel",
        "paired_comparator_panels",
    ):
        assert rule[key] == SOURCE[key], key
    for key in (
        "max_worker_rss_bytes",
        "gpu_memory_fraction",
        "max_batch_working_bytes",
        "max_retained_array_estimate_bytes",
        "free_disk_reserve_bytes",
    ):
        assert rule["resources"][key] == SOURCE["resources"][key], key
    assert rule["preparations"][:3] == SOURCE["preparations"]
    heldout = rule["preparations"][3:]
    assert len(heldout) == 8 and all(r["split"] == "heldout" for r in heldout)
    assert [r["amplitude"] for r in heldout] == rule["evaluation_design"]["strengths"] == STRENGTHS
    assert rule["evaluation_design"]["joint_cases"] == 32
    assert rule["evaluation_design"]["single_task_cases_per_arm"] == 16
    assert rule["world_id_offset"] == 480000
    assert rule["work"] == dict(
        worlds_per_timestep=220,
        worlds_per_backend=660,
        world_steps_per_backend=3153920,
        world_steps_per_arm_per_backend=630784,
    )
    assert rule["automatic_followup"] is False
    return dict(
        status="passed",
        binding=binding,
        selected_onset_separation_us=104,
        selected_times_us=[128, 160, 320],
        fresh_strengths=STRENGTHS,
        frozen_before_new_responses=True,
        heldout_response_reranking=False,
    )


def baseline(rule):
    selection = selected_design(rule)
    accepted = two_task.baseline(rule)
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
        new_strength_responses_not_used_to_select_pulses_or_observations=True,
    )
