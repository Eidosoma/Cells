"""Temporal checks of the distributed cue and its calibrated voltage reader.

The authenticated 0.25-us panel supplies the coarse observations. Two smaller
steps are simulated on the same inputs. Resolution-matched calibration and a
reader frozen at the coarse step are both reported, without outcome selection.
"""

import json
from pathlib import Path

import numpy as np

from cells.core.batch import BatchSpec, WorldSpec
from cells.core.specs import parse_spec
from validation.assays import distributed_cue, template_readout, two_task
from validation.betse.spatial_active.refinement import digest

PROTOCOL_PATH = Path(__file__).with_name("distributed_timing_protocol.json")


def protocol():
    return json.loads(PROTOCOL_PATH.read_text())


def cases():
    return distributed_cue.cases(distributed_cue.protocol())


def baseline(rule):
    report = two_task.baseline(rule)
    source = two_task.ROOT / rule["source_protocol"]
    assert digest(source) == rule["source_protocol_sha256"]
    prior = json.loads(
        (Path(rule["prior_binding"]["root"]) / "component-protocol.json").read_text()
    )
    assert json.loads(source.read_text()) == prior == distributed_cue.protocol()
    assert rule["dt_s"][0] == prior["dt_s"]
    assert rule["duration_s"] == prior["duration_s"]
    return report | dict(unchanged_cue_and_reader=True, coarse_panel_reused=True)


def definition(base, row, level, backend, rule):
    if type(level) is not int or not 0 <= level < len(rule["dt_s"]):
        raise ValueError("Unregistered refinement level")
    raw = distributed_cue.definition(base, row, backend, distributed_cue.protocol())
    raw["execution"]["dt"] = rule["dt_s"][level]
    return raw


def batch(base, rows, level, backend, rule):
    return BatchSpec(
        tuple(
            WorldSpec(row["world_id"], parse_spec(definition(base, row, level, backend, rule)))
            for row in rows
        ),
        max_worlds=rule["batch_worlds"],
        max_padded_steps=rule["batch_worlds"]
        * (
            round(rule["duration_s"] / rule["dt_s"][level])
            + len(two_task.protocol()["control_steps"])
        ),
        max_working_bytes=rule["resources"]["max_batch_working_bytes"],
    )


def reader_reports(rows, voltages, rule):
    """No retuning: same reader fitted at each step, plus fixed coarse curves.

    Only calibration rows may supply fitted vertices. Evaluation strengths and
    labels are never supplied to TemplateReader.read. The inherited evaluator uses
    held-out labels solely to score predictions.
    """
    if len(voltages) != 3:
        raise ValueError("Three voltage maps required")
    margin = distributed_cue.protocol()["reader"]["voltage_margin_V"]
    reports = {name: {} for name in rule["reader_check"]["calibration_modes"]}
    for mode in rule["reader_check"]["observation_modes"]:
        if mode not in ("voltage", "final_voltage"):
            raise ValueError("Unregistered voltage observation mode")
        features = [
            {key: value if mode == "voltage" else value[-7:] for key, value in level.items()}
            for level in voltages
        ]
        for calibration in reports:
            if calibration not in ("resolution_matched", "frozen_coarse"):
                raise ValueError("Unregistered calibration mode")
            reports[calibration][mode] = []
            for level in range(3):
                selected = {
                    row["world_id"]: features[
                        0
                        if calibration == "frozen_coarse" and row["split"] == "calibration"
                        else level
                    ][row["world_id"]]
                    for row in rows
                }
                reports[calibration][mode].append(
                    template_readout.evaluate(rows, selected, margin=margin)
                )
    return reports


def score_changes(reports, criteria):
    """Per-case signed score drift and decision changes; no success assertion."""
    if len(reports) != 3:
        raise ValueError("Three reader reports required")
    levels = []
    for report in reports:
        entries = {}
        for arm, detail in report["arms"].items():
            for task, values in detail["tasks"].items():
                for prediction in values["predictions"]:
                    key = (arm, task, prediction["world_id"])
                    if key in entries:
                        raise ValueError("Duplicate reader prediction")
                    entries[key] = prediction
        levels.append(entries)
    if not levels[0] or not all(level.keys() == levels[0].keys() for level in levels):
        raise ValueError("Reader case identities changed across resolutions")
    absolute = criteria["absolute_score_change_limit_V"]
    relative = criteria["relative_score_change_limit"]
    if not np.isfinite([absolute, relative]).all() or absolute <= 0 or relative <= 0:
        raise ValueError("Positive finite score-change limits required")
    rows = []
    for (arm, task, identity), coarse in levels[0].items():
        predicted = [level[arm, task, identity] for level in levels]
        if not all(row["target"] == coarse["target"] for row in predicted):
            raise ValueError("Reader targets changed across resolutions")
        scores = np.asarray([row["score"] for row in predicted], dtype=float)
        if not np.isfinite(scores).all():
            raise ValueError("Finite reader scores required")
        changes = np.abs(np.diff(scores))
        limit = min(absolute, relative * abs(scores[2]))
        decisions = [(row["prediction"], row["resolved"]) for row in predicted]
        rows.append(
            dict(
                arm=arm,
                task=task,
                world_id=identity,
                target=coarse["target"],
                scores_V=scores.tolist(),
                predictions=[row["prediction"] for row in predicted],
                resolved=[row["resolved"] for row in predicted],
                successive_score_changes_V=changes.tolist(),
                coarse_to_fine_score_change_V=float(abs(scores[0] - scores[2])),
                stability_limit_V=float(limit),
                finest_steps_within_score_limits=bool(changes[1] <= limit),
                original_dt_within_score_limits=bool(abs(scores[0] - scores[2]) <= limit),
                finest_decisions_agree=decisions[1] == decisions[2],
                original_decision_agrees=decisions[0] == decisions[2],
                all_levels_correct_and_resolved=all(
                    row["resolved"] and row["prediction"] == row["target"] for row in predicted
                ),
            )
        )
    return dict(
        cases=rows,
        criteria=criteria,
        scientific_outcome_is_not_an_acceptance_gate=True,
        continuum_error_bound=False,
    )
