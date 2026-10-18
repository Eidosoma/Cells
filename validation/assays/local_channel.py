"""Calibrate paired flank-channel interventions with the qualified CPU/L4 runner."""

import copy
import json
from pathlib import Path

import numpy as np

from cells.core.batch import BatchSpec, WorldSpec
from cells.core.specs import parse_spec
from validation.assays import channel_compensation as previous
from validation.assays import local_channel_design as design
from validation.assays import two_task
from validation.assays.channel_compensation import PANELS as PANELS
from validation.assays.channel_compensation import archived_segment as archived_segment
from validation.assays.channel_compensation import calibration_geometry as calibration_geometry
from validation.assays.channel_compensation import calibration_views as calibration_views
from validation.assays.channel_compensation import (
    compare_reader_predictions as compare_reader_predictions,
)
from validation.assays.channel_compensation import features as features
from validation.assays.channel_compensation import geometry as geometry
from validation.assays.channel_compensation import nulls_unresolved as nulls_unresolved
from validation.assays.channel_compensation import ordered as ordered
from validation.assays.channel_compensation import paired_contrasts as paired_contrasts
from validation.assays.channel_compensation import times as times
from validation.assays.channel_compensation import world_name as world_name
from validation.betse.spatial_active.refinement import digest

PROTOCOL_PATH = Path(__file__).with_name("source_order_long") / "local_channel_protocol.json"
PLAN = design.plan()
PRIOR = previous.protocol()
SOURCE = previous.condition_rule(PRIOR, "sham")
SOURCE_ROWS = previous.cases(SOURCE)
ORIGINAL_BINDING = previous.SOURCE_ROOT["prior_binding"]
ORIGINAL_ROWS = [r for r in previous.coupling.SOURCE_ROWS if r["split"] == "calibration"]
CONDITIONS = design.CONDITIONS


def protocol():
    return json.loads(PROTOCOL_PATH.read_text())


def condition_rule(rule, name):
    if rule["conditions"] != CONDITIONS:
        raise ValueError("Unregistered local-channel conditions")
    matches = [c for c in CONDITIONS if c["id"] == name]
    if len(matches) != 1:
        raise ValueError("Unregistered local-channel condition")
    condition = copy.deepcopy(matches[0])
    return copy.deepcopy(rule) | dict(
        condition=condition,
        world_id_offset=condition["world_id_offset"],
        work=rule["work_per_condition"].copy(),
    )


def cases(rule):
    return previous.cases(rule)


def source_row(row, source_rows=SOURCE_ROWS):
    return previous.source_row(row, source_rows)


def historical_source(row):
    return source_row(row), SOURCE["duration_s"]


def definition(base, row, level, backend, rule):
    if rule["condition"] not in CONDITIONS:
        raise ValueError("Unregistered local-channel condition")
    return design.definition(base, row, level, backend, PLAN, rule["condition"]["id"])


def batch(base, rows, level, backend, rule):
    return BatchSpec(
        tuple(
            WorldSpec(r["world_id"], parse_spec(definition(base, r, level, backend, rule)))
            for r in rows
        ),
        rule["batch_worlds"],
        rule["batch_worlds"] * (round(rule["duration_s"] / rule["dt_s"][level]) + 7),
        rule["resources"]["max_batch_working_bytes"],
    )


def validate_plan(rule):
    assert digest(two_task.ROOT / rule["design_plan"]) == rule["design_plan_sha256"]
    assert json.loads((two_task.ROOT / rule["design_plan"]).read_text()) == PLAN
    design.validate_plan(PLAN)
    assert rule["conditions"] == CONDITIONS
    assert rule["calibration_only"] is True and rule["automatic_followup"] is False
    assert rule["diagnostic_binding"] == PLAN["diagnostic_binding"]
    assert rule["source_protocol"] == PLAN["source_protocol"]
    assert rule["source_protocol_sha256"] == PLAN["source_protocol_sha256"]
    assert digest(two_task.ROOT / rule["source_protocol"]) == rule["source_protocol_sha256"]
    for key in (
        "template",
        "template_sha256",
        "dt_s",
        "duration_s",
        "max_steps",
        "preparations",
        "readout",
        "reader",
        "source_cell_ids",
        "task_meanings",
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
        assert rule[key] == PRIOR[key], key
    descriptions = {"selection", "comparison_panels"}
    assert {k: v for k, v in rule["cue_timing"].items() if k not in descriptions} == {
        k: v for k, v in PRIOR["cue_timing"].items() if k not in descriptions
    }
    assert rule["work_per_condition"] == PRIOR["work_per_condition"]
    assert rule["work"] == {k: 5 * v for k, v in rule["work_per_condition"].items()}
    assert rule["prior_binding"] == {
        k: PLAN["source_binding"][k] for k in ("root", "registration_sha256", "completion_sha256")
    } | dict(require_completed_cpu_and_gpu=True)
    assert rule["frozen_reader_source"] == previous.SOURCE_ROOT["frozen_reader_source"]
    assert rule["original_reader_binding"] == ORIGINAL_BINDING
    assert rule["resources"]["max_wall_seconds"] == PLAN["execution"]["proposed_max_wall_seconds"]
    assert (
        rule["resources"]["artifact_and_cache_bytes"]
        == PLAN["execution"]["proposed_artifact_and_cache_budget_bytes"]
    )
    for name in (
        "free_disk_reserve_bytes",
        "max_worker_rss_bytes",
        "gpu_memory_fraction",
        "max_batch_working_bytes",
        "max_retained_array_estimate_bytes",
    ):
        assert rule["resources"][name] == PRIOR["resources"][name]
    return dict(
        status="passed",
        design_plan_sha256=rule["design_plan_sha256"],
        calibration_only=True,
        source_completion_bound=True,
        original_unperturbed_cpu_reader_bound=True,
    )


def baseline(rule):
    if rule["prior_binding"]["completion_sha256"] is None:
        raise ValueError("Source completion must be bound before simulation")
    planned = validate_plan(rule)
    accepted = two_task.baseline(rule)
    records = design.authenticate_bindings(PLAN)
    diagnostic = PLAN["diagnostic_binding"]
    root = Path(diagnostic["root"])
    inputs = json.loads((root / "inputs.json").read_text())
    assert inputs["completion_sha256"] == PLAN["source_binding"]["completion_sha256"]
    for name, expected in inputs["files_sha256"].items():
        assert digest(root / "inputs" / name) == expected, name
    for name, expected in inputs["diagnostic_sources_sha256"].items():
        assert digest(root / "source" / name) == expected == digest(two_task.ROOT / name), name
    original = Path(ORIGINAL_BINDING["root"])
    assert digest(original / "completion.json") == ORIGINAL_BINDING["completion_sha256"]
    manifest = json.loads((original / "completion.json").read_text())
    for name, expected in rule["frozen_reader_source"]["files_sha256"].items():
        assert digest(original / name) == expected == manifest["evidence_sha256"][name]
    return dict(
        status="passed",
        plan=planned,
        accepted=accepted,
        records=records,
        diagnostic_inputs_and_sources_bound=True,
        original_reader_manifest_bound=True,
    )


def load_reference(saved, rows, reference_rows=SOURCE_ROWS):
    return previous.load_reference(saved, rows, reference_rows)


def paired_geometry(target, reference):
    """Report each condition's reoptimized fitted-curve gap against archived sham."""
    result = {}
    for panel in PANELS:
        before, after = reference["panels"][panel], target["panels"][panel]
        rows = []
        for original, candidate in zip(before["task_groups"], after["task_groups"], strict=True):
            assert all(original[k] == candidate[k] for k in ("arm", "task", "level", "dt_s"))
            rows.append(
                dict(
                    arm=candidate["arm"],
                    task=candidate["task"],
                    level=candidate["level"],
                    dt_s=candidate["dt_s"],
                    original=original,
                    candidate=candidate,
                    half_distance_change_V=candidate["half_distance_V"]
                    - original["half_distance_V"],
                )
            )
        result[panel] = dict(
            score_change_V=after["score_V"] - before["score_V"],
            task_groups=rows,
            minimizers_reoptimized=True,
        )
    return result


def combined_selection(reports):
    """Retain the uniform pilot's rule, applied to the five registered conditions."""
    names = [c["id"] for c in CONDITIONS]
    if set(reports) != {"cpu", "gpu"} or any(set(r) != set(names) for r in reports.values()):
        raise ValueError("Complete CPU/L4 condition reports required")
    scores, votes, eligible = {}, {}, {}
    for backend, groups in reports.items():
        scores[backend] = {n: groups[n]["panels"]["selected320"]["score_V"] for n in names}
        if any(not np.isfinite(v) or v < 0 for v in scores[backend].values()):
            raise ValueError("Finite nonnegative geometry scores required")
        eligible[backend] = {n: nulls_unresolved(groups[n]) for n in names}
        maximum = max(scores[backend].values())
        winners = [n for n, v in scores[backend].items() if maximum - v <= geometry.TIE_ATOL_V]
        winner = winners[0] if len(winners) == 1 else "sham"
        if (
            not eligible[backend][winner]
            or not eligible[backend]["sham"]
            or scores[backend][winner] <= 2e-9
            or scores[backend][winner] - scores[backend]["sham"] <= geometry.TIE_ATOL_V
        ):
            winner = "sham"
        votes[backend] = winner
    maximum_error = max(abs(scores["cpu"][n] - scores["gpu"][n]) for n in names)
    selected = (
        votes["cpu"]
        if votes["cpu"] == votes["gpu"] and maximum_error <= geometry.TIE_ATOL_V
        else "sham"
    )
    return dict(
        status="frozen_before_any_fresh_confirmation",
        selected_condition=selected,
        scores_V=scores,
        backend_votes=votes,
        calibration_nulls_unresolved=eligible,
        maximum_score_difference_V=maximum_error,
        tie_atol_V=geometry.TIE_ATOL_V,
        reproducible_improvement=selected != "sham",
        heldout_cases_evaluated=0,
        geometric_selection_is_not_a_recovery_result=True,
        requires_completed_qualification=True,
        automatic_followup=False,
    )
