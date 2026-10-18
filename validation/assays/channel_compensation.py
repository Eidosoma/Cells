"""Calibration-only channel compensation at fixed impaired junction coupling."""

import copy
import json
from pathlib import Path

import numpy as np

from cells.assays.readout import score_predictions
from cells.core.batch import BatchSpec, WorldSpec
from cells.core.specs import parse_spec
from validation.assays import baseline_transfer_diagnostic as reference
from validation.assays import channel_compensation_design as design
from validation.assays import source_order_coupling_transfer as coupling
from validation.assays import source_order_observation_design as geometry
from validation.assays import two_task
from validation.assays.source_order_coupling_transfer import archived_segment as archived_segment
from validation.assays.source_order_coupling_transfer import (
    compare_reader_predictions as compare_reader_predictions,
)
from validation.assays.source_order_coupling_transfer import features as features
from validation.assays.source_order_coupling_transfer import ordered as ordered
from validation.assays.source_order_coupling_transfer import paired_contrasts as paired_contrasts
from validation.assays.source_order_coupling_transfer import times as times
from validation.assays.source_order_coupling_transfer import world_name as world_name
from validation.assays.source_order_pulse_spacing import PANELS as PANELS
from validation.assays.source_order_pulse_spacing import (
    calibration_geometry as calibration_geometry,
)
from validation.assays.template_readout import TemplateReader
from validation.betse.spatial_active.refinement import digest

PROTOCOL_PATH = Path(__file__).with_name("source_order_long") / "channel_compensation_protocol.json"
PLAN = design.plan()
SOURCE_ROOT = coupling.protocol()
SOURCE = coupling.condition_rule(SOURCE_ROOT, "lower")
SOURCE_ROWS = [r for r in coupling.cases(SOURCE) if r["split"] == "calibration"]
CONDITIONS = design.CONDITIONS


def protocol():
    return json.loads(PROTOCOL_PATH.read_text())


def condition_rule(rule, name):
    if rule["conditions"] != CONDITIONS:
        raise ValueError("Unregistered channel conditions")
    matches = [c for c in CONDITIONS if c["id"] == name]
    if len(matches) != 1:
        raise ValueError("Unregistered channel condition")
    c = copy.deepcopy(matches[0])
    return copy.deepcopy(rule) | dict(
        condition=c, world_id_offset=c["world_id_offset"], work=rule["work_per_condition"].copy()
    )


def cases(rule):
    return coupling.cases(rule)


def source_row(row, source_rows=SOURCE_ROWS):
    identities = {k: v for k, v in row.items() if k != "world_id"}
    matches = [
        r for r in source_rows if {k: v for k, v in r.items() if k != "world_id"} == identities
    ]
    if len(matches) != 1:
        raise ValueError("No unique calibration predecessor")
    return matches[0]


def historical_source(row):
    # The harness compares full sham histories, but only candidate initial states.
    return source_row(row), SOURCE["duration_s"]


def definition(base, row, level, backend, rule):
    if rule["condition"] not in CONDITIONS:
        raise ValueError("Unregistered channel condition")
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
    assert rule["preparations"] == SOURCE["preparations"][:3]
    assert rule["source_protocol"] == PLAN["source_protocol"]
    assert rule["source_protocol_sha256"] == PLAN["source_protocol_sha256"]
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
    assert rule["work_per_condition"] == design.condition_rule(PLAN, "sham")["work"]
    assert rule["work"] == {k: 3 * v for k, v in rule["work_per_condition"].items()}
    binding = rule["prior_binding"]
    assert binding["root"] == PLAN["source_binding"]["root"]
    assert binding["registration_sha256"] == PLAN["source_binding"]["registration_sha256"]
    assert binding["require_completed_cpu_and_gpu"] is True
    completion = binding["completion_sha256"]
    assert completion is None or (isinstance(completion, str) and len(completion) == 64)
    return dict(
        status="passed",
        design_plan_sha256=rule["design_plan_sha256"],
        calibration_only=True,
        source_completion_bound=completion is not None,
    )


def baseline(rule):
    planned = validate_plan(rule)
    if not planned["source_completion_bound"]:
        raise ValueError("Source completion must be bound before simulation")
    accepted = two_task.baseline(rule)
    root = Path(rule["prior_binding"]["root"])
    assert json.loads((root / "component-protocol.json").read_text()) == SOURCE_ROOT
    assert (
        digest(root / "component-protocol.json")
        == PLAN["source_binding"]["component_protocol_sha256"]
    )
    diagnostic = rule["diagnostic_binding"]
    folder = Path(diagnostic["root"])
    assert digest(folder / "completion.json") == diagnostic["completion_sha256"]
    assert digest(folder / "result.json") == diagnostic["result_sha256"]
    done = json.loads((folder / "completion.json").read_text())
    assert done["status"] == "completed_subset_diagnosis"
    assert done["result_sha256"] == diagnostic["result_sha256"]
    # Reference reader coefficients come from the original completed CPU run.
    original = Path(SOURCE_ROOT["prior_binding"]["root"])
    assert digest(original / "completion.json") == SOURCE_ROOT["prior_binding"]["completion_sha256"]
    manifest = json.loads((original / "completion.json").read_text())
    for name, sha in SOURCE_ROOT["frozen_reader_source"]["files_sha256"].items():
        assert digest(original / name) == sha == manifest["evidence_sha256"][name]
    return dict(
        status="passed", plan=planned, accepted=accepted, original_reader_manifest_bound=True
    )


def load_reference(saved, rows, reference_rows=SOURCE_ROWS):
    training = geometry.calibration_rows(rows, dict(calibration_strengths=[0.4, 0.6, 0.8]))
    maps, loaded = {}, []
    for level in range(3):
        for panel in PANELS:
            values = {}
            for row in training:
                old = source_row(row, reference_rows)
                key = f"{level}__{panel}__voltage__{old['world_id']}"
                value = np.asarray(saved[key], dtype=np.float64)
                if value.shape != (15,) or not np.isfinite(value).all():
                    raise ValueError("Invalid calibration feature: " + key)
                values[row["world_id"]] = value.copy()
                loaded.append(key)
            maps[level, panel] = dict(voltage=values)
    return maps, loaded


def calibration_views(rows, original, target, margin):
    """Read calibration points only; these are not disjoint evaluation outcomes."""
    training = geometry.calibration_rows(rows, dict(calibration_strengths=[0.4, 0.6, 0.8]))
    old_ref, old_control = reference.no_cue_reference(training, original)
    new_ref, new_control = reference.no_cue_reference(training, target)
    reports = {}
    for mode, fit, fit_ref, query_ref in (
        ("raw_frozen_source", original, 0, 0),
        ("reference_assisted", original, old_ref, new_ref),
        ("condition_calibrated", target, 0, 0),
    ):
        arms = {}
        for arm in geometry.ARMS:
            selected = [r for r in training if r["arm"] == arm]
            tasks = list(geometry.TASKS)
            if arm.endswith("_only"):
                task = arm.removesuffix("_only")
                ignored = next(t for t in tasks if t != task)
                selected = [r for r in selected if r[ignored] == 0]
                tasks = [task]
            labels = np.array([[r[t] for t in tasks] for r in selected])
            reader = TemplateReader.fit(
                np.stack([fit[r["world_id"]] - fit_ref for r in selected]),
                labels,
                [r["amplitude"] for r in selected],
                minimum_margin=margin,
            )
            decoded = reader.read(np.stack([target[r["world_id"]] - query_ref for r in selected]))
            task_reports = {}
            for i, task in enumerate(tasks):
                task_reports[task] = dict(
                    predictions=[
                        dict(
                            world_id=r["world_id"],
                            target=r[task],
                            prediction=int(decoded["prediction"][j, i]),
                            resolved=bool(decoded["resolved"][j, i]),
                            score=float(decoded["score"][j, i]),
                        )
                        for j, r in enumerate(selected)
                    ],
                    metrics=score_predictions(
                        labels[:, i], decoded["prediction"][:, i], decoded["resolved"][:, i]
                    ),
                )
            correct = np.all(labels == decoded["prediction"], axis=1)
            resolved = np.all(decoded["resolved"], axis=1)
            arms[arm] = dict(
                tasks=task_reports,
                joint=dict(
                    cases=len(selected), correct_and_resolved=int((correct & resolved).sum())
                ),
                calibration=dict(
                    template_reader=reader.to_dict(), world_ids=[r["world_id"] for r in selected]
                ),
                projections=[
                    dict(
                        world_id=r["world_id"],
                        **{
                            k: decoded[k][j].tolist()
                            for k in ("curve_distances", "closest_segments", "segment_coordinates")
                        },
                    )
                    for j, r in enumerate(selected)
                ],
            )
        reports[mode] = dict(
            arms=arms, feature_count=15, calibration_points_only=True, heldout_cases=0
        )
    return dict(
        views=reports,
        source_control=old_control,
        target_control=new_control,
        drift=reference.drift(training, original, target, old_ref, new_ref),
        heldout_cases=0,
        fitting_points_are_not_confirmation=True,
    )


def nulls_unresolved(report):
    if set(report["panels"]) != set(PANELS):
        raise ValueError("Complete calibration control panels required")
    expected = {(a, level) for a in ("no_cue", "disconnected") for level in range(3)}
    for panel in report["panels"].values():
        controls = panel["calibration_null_controls"]
        if len(controls) != 6 or {(c["arm"], c["level"]) for c in controls} != expected:
            raise ValueError("Complete calibration null controls required")
        for control in controls:
            if set(control["tasks"]) != {"location", "timing"} or any(
                type(t["resolved_cases"]) is not int or not 0 <= t["resolved_cases"] <= 12
                for t in control["tasks"].values()
            ):
                raise ValueError("Invalid calibration null-control counts")
    return all(
        t["resolved_cases"] == 0
        for p in report["panels"].values()
        for n in p["calibration_null_controls"]
        for t in n["tasks"].values()
    )


def combined_selection(reports):
    """Only complete, finite, reproducible geometric improvements can be selected."""
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
