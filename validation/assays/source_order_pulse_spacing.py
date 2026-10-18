"""Calibration-only test of a dose-preserving, later second source pulse."""

import json
from pathlib import Path

import numpy as np

from cells.core.batch import BatchSpec, WorldSpec
from cells.core.specs import parse_spec
from validation.assays import source_order_observation_design as geometry
from validation.assays import source_order_selected as previous
from validation.assays import two_task
from validation.assays.source_order_selected import archived_segment as archived_segment
from validation.assays.source_order_selected import features as features
from validation.assays.source_order_selected import ordered as ordered
from validation.assays.source_order_selected import paired_contrasts as paired_contrasts
from validation.assays.source_order_selected import times as times
from validation.assays.source_order_selected import world_name as world_name
from validation.assays.template_readout import TemplateReader
from validation.betse.spatial_active.refinement import digest

PROTOCOL_PATH = Path(__file__).with_name("source_order_long") / "pulse_spacing_protocol.json"
SOURCE = previous.protocol()
SOURCE_ROWS = [r for r in previous.cases(SOURCE) if r["split"] == "calibration"]
PANELS = ("selected320", "spanning512", "long512")
STRENGTHS = [0.4, 0.6, 0.8]


def protocol():
    return json.loads(PROTOCOL_PATH.read_text())


def cases(rule=None):
    return previous.cases(protocol() if rule is None else rule)


def validate_plan(rule):
    """Bind the single physical change before reading any new response."""
    path = two_task.ROOT / rule["design_plan"]
    assert digest(path) == rule["design_plan_sha256"]
    plan = json.loads(path.read_text())
    design = plan["design"]
    assert rule["prior_binding"] == plan["source_binding"] | {"require_completed_cpu_and_gpu": True}
    assert rule["diagnostic_binding"] == plan["diagnostic_binding"]
    assert rule["calibration_only"] is True and rule["automatic_followup"] is False
    assert rule["preparations"] == SOURCE["preparations"][:3]
    assert [r["amplitude"] for r in rule["preparations"]] == STRENGTHS
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
        "score_stability",
        "contrast",
        "batch_worlds",
        "window_steps",
        "observation_panels",
        "observation_times_us",
        "primary_panel",
    ):
        assert rule[key] == SOURCE[key], key
    assert rule["readout"]["cell_ids"] == design["cell_ids"]
    assert rule["observation_times_us"][PANELS[0]] == design["primary_times_us"]
    assert [rule["observation_times_us"][p] for p in PANELS[1:]] == design["comparator_times_us"]
    assert rule["reader"]["voltage_margin_V"] == design["reader_margin_V"] == 2e-9
    cue = rule["cue_timing"]
    for key in ("early_pulse_us", "location_only_pulse_us", "pulse_width_us"):
        assert cue[key] == SOURCE["cue_timing"][key] == design[key]
    assert cue["late_pulse_us"] == design["candidate_late_pulse_us"] == [112, 120]
    assert cue["onset_separation_us"] == design["candidate_onset_separation_us"] == 104
    assert rule["replay"]["snapshot_step"] == SOURCE["replay"]["snapshot_step"] == 1663
    assert rule["work"] == dict(
        worlds_per_timestep=design["candidate_worlds_per_timestep"],
        worlds_per_backend=design["candidate_worlds_per_backend"],
        world_steps_per_backend=design["candidate_world_steps_per_backend"],
        world_steps_per_arm_per_backend=design["candidate_world_steps_per_arm_per_backend"],
    )
    geometry.calibration_rows(cases(rule), dict(calibration_strengths=STRENGTHS))
    return plan


def baseline(rule):
    validate_plan(rule)
    accepted = two_task.baseline(rule)
    assert digest(two_task.ROOT / rule["source_protocol"]) == rule["source_protocol_sha256"]
    assert json.loads((two_task.ROOT / rule["source_protocol"]).read_text()) == SOURCE
    binding = rule["diagnostic_binding"]
    folder = Path(binding["root"])
    assert not (folder / "failure.json").exists()
    assert digest(folder / "completion.json") == binding["completion_sha256"]
    done = json.loads((folder / "completion.json").read_text())
    assert done["status"] == "completed"
    assert digest(folder / "result.json") == done["result_sha256"] == binding["result_sha256"]
    assert digest(folder / "inputs.json") == done["inputs_sha256"]
    inputs = json.loads((folder / "inputs.json").read_text())
    assert inputs["source_binding"] == rule["prior_binding"]
    for name, sha in inputs["diagnostic_sources_sha256"].items():
        assert digest(folder / "source" / name) == digest(two_task.ROOT / name) == sha
    registration = json.loads(
        (Path(rule["prior_binding"]["root"]) / "registration.json").read_text()
    )
    assert {str(p.relative_to(two_task.ROOT)) for p in (two_task.ROOT / "src").rglob("*.py")} == {
        name for name in registration["sources_sha256"] if name.startswith("src/")
    }
    return dict(
        status="passed",
        accepted=accepted,
        diagnostic_binding=binding,
        production_physics_reader_and_tolerances_unchanged=True,
        calibration_only=True,
        new_evaluation_responses=0,
    )


def definition(base, row, level, backend, rule):
    """Reuse the qualified event amplitudes, shifting only the late on/off times."""
    if rule["cue_timing"]["early_pulse_us"] != [8, 16] or rule["cue_timing"]["late_pulse_us"] != [
        112,
        120,
    ]:
        raise ValueError("Only the declared 104-us onset separation is supported")
    raw = previous.definition(
        base, row, level, backend, rule | {"cue_timing": SOURCE["cue_timing"]}
    )
    if ordered(row):
        changes = raw["experiment"]["changes"]
        unit = two_task.protocol()["dt_s"]
        assert [c["time"] for c in changes[-2:]] == [104 * unit, 112 * unit]
        for change, time in zip(changes[-2:], (112, 120), strict=True):
            change["time"] = time * unit
    return raw


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


def historical_source(row):
    matches = [
        old
        for old in SOURCE_ROWS
        if all(old[k] == row[k] for k in ("arm", "amplitude", "location", "timing", "split"))
    ]
    if len(matches) != 1:
        raise ValueError("No unique baseline calibration case")
    return matches[0], 104e-6 if ordered(row) else SOURCE["duration_s"]


def load_reference(saved, rows):
    """Read only explicitly named calibration voltages, without archive enumeration."""
    training = geometry.calibration_rows(rows, dict(calibration_strengths=STRENGTHS))
    maps, accessed = {}, []
    for level in range(3):
        for panel in PANELS:
            values = {}
            for row in training:
                before, _ = historical_source(row)
                key = f"{level}__{panel}__voltage__{before['world_id']}"
                value = np.asarray(saved[key], dtype=np.float64)
                if value.shape != (15,) or not np.isfinite(value).all():
                    raise ValueError("Invalid calibration feature: " + key)
                values[row["world_id"]] = value.copy()
                accessed.append(key)
            maps[level, panel] = dict(voltage=values)
    return maps, accessed


def calibration_geometry(rows, maps, rule):
    """Fixed panels and calibration-only opposite-label segment distances."""
    training = geometry.calibration_rows(rows, dict(calibration_strengths=STRENGTHS))
    panels = {}
    for panel in PANELS:
        groups, nulls = [], []
        for level, dt in enumerate(rule["dt_s"]):
            for arm in geometry.ARMS:
                selected = [r for r in training if r["arm"] == arm]
                tasks = list(geometry.TASKS)
                if arm.endswith("_only"):
                    task = arm.removesuffix("_only")
                    ignored = next(t for t in tasks if t != task)
                    selected = [r for r in selected if r[ignored] == 0]
                    tasks = [task]
                values = np.stack([maps[level, panel]["voltage"][r["world_id"]] for r in selected])
                if values.shape != (len(selected), 15) or not np.isfinite(values).all():
                    raise ValueError("Expected fifteen finite calibration voltages")
                fitted = TemplateReader.fit(
                    values,
                    np.array([[r[t] for t in tasks] for r in selected]),
                    [r["amplitude"] for r in selected],
                    minimum_margin=rule["reader"]["voltage_margin_V"],
                )
                if arm in ("no_cue", "disconnected"):
                    decoded = fitted.read(values)
                    nulls.append(
                        dict(
                            arm=arm,
                            level=level,
                            dt_s=dt,
                            tasks={
                                task: dict(
                                    maximum_absolute_score_V=float(
                                        np.abs(decoded["score"][:, i]).max()
                                    ),
                                    resolved_cases=int(decoded["resolved"][:, i].sum()),
                                )
                                for i, task in enumerate(tasks)
                            },
                            included_in_selection_objective=False,
                        )
                    )
                else:
                    for i, task in enumerate(tasks):
                        groups.append(
                            dict(arm=arm, task=task, level=level, dt_s=dt)
                            | geometry.task_separation(fitted, i, STRENGTHS)
                        )
        limiting = min(groups, key=lambda g: g["half_distance_V"])
        panels[panel] = dict(
            times_us=rule["observation_times_us"][panel],
            feature_count=15,
            score_V=limiting["half_distance_V"],
            limiting_group=limiting,
            task_groups=groups,
            calibration_null_controls=nulls,
        )
    return dict(
        panels=panels,
        primary_panel=PANELS[0],
        score_V=panels[PANELS[0]]["score_V"],
        heldout_arrays_loaded=0,
        heldout_cases_evaluated=0,
        calibration_cases=len(training),
    )


def protocol_comparison(baseline, candidate):
    """Primary support alone chooses between pulse protocols, never a comparator panel."""
    scores = [report["panels"][PANELS[0]]["score_V"] for report in (baseline, candidate)]
    if not np.isfinite(scores).all() or min(scores) < 0:
        raise ValueError("Finite nonnegative geometry scores required")
    difference = scores[1] - scores[0]
    selected = 104 if difference > geometry.TIE_ATOL_V else 96
    return dict(
        baseline_onset_separation_us=96,
        candidate_onset_separation_us=104,
        baseline_score_V=scores[0],
        candidate_score_V=scores[1],
        candidate_minus_baseline_V=difference,
        selected_onset_separation_us=selected,
        tie_atol_V=geometry.TIE_ATOL_V,
        candidate_fitted_minimum_above_margin=scores[1] > 2e-9,
        candidate_fitted_minimum_minus_margin_V=scores[1] - 2e-9,
        baseline_preferred_without_improvement=selected == 96,
    )


def combined_selection(cpu, gpu):
    """A disagreement keeps the baseline; no fresh confirmation is launched here."""
    scores = [r[k] for r in (cpu, gpu) for k in ("baseline_score_V", "candidate_score_V")]
    if not np.isfinite(scores).all() or min(scores) < 0:
        raise ValueError("Finite backend comparison scores required")
    choices = [
        104 if r["candidate_score_V"] - r["baseline_score_V"] > geometry.TIE_ATOL_V else 96
        for r in (cpu, gpu)
    ]
    if choices != [r["selected_onset_separation_us"] for r in (cpu, gpu)]:
        raise ValueError("Backend choice differs from its scores")
    error = max(abs(cpu[k] - gpu[k]) for k in ("baseline_score_V", "candidate_score_V"))
    reproducible = choices == [104, 104] and error <= geometry.TIE_ATOL_V
    return dict(
        winners_agree=choices[0] == choices[1],
        maximum_score_difference_V=error,
        reproducible_improvement=reproducible,
        selected_onset_separation_us=104 if reproducible else 96,
        status="frozen_before_any_fresh_confirmation",
        heldout_cases_evaluated=0,
        automatic_followup=False,
        geometric_selection_is_not_a_resolution_result=True,
    )
