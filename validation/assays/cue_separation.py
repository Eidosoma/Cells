"""One predeclared change to late-pulse timing, with dose and readers fixed.

The 140 inspected identities are paired with the completed long-observation
assay. The unchanged runner, physical checks and reader implementations are
reused; this is neither fresh generalization nor a biological noise model.
"""

import json
from pathlib import Path

import numpy as np

from cells.core.batch import BatchSpec, WorldSpec
from cells.core.specs import parse_spec
from validation.assays import long_observation, two_task
from validation.assays.long_observation import archived_segment as archived_segment
from validation.assays.long_observation import cases as cases
from validation.assays.long_observation import (
    compare_reader_predictions as compare_reader_predictions,
)
from validation.assays.long_observation import features as features
from validation.assays.long_observation import paired_contrasts as paired_contrasts
from validation.assays.long_observation import reader_reports as reader_reports
from validation.assays.long_observation import times as times
from validation.assays.long_observation import world_name as world_name
from validation.betse.spatial_active.refinement import digest

PROTOCOL_PATH = Path(__file__).with_name("cue_separation_protocol.json")


def protocol():
    return json.loads(PROTOCOL_PATH.read_text())


def shifted(row):
    return row["arm"] in ("timing_only", "joint", "disconnected") and row["timing"] == 1


def baseline(rule):
    report = two_task.baseline(rule)
    source = two_task.ROOT / rule["source_protocol"]
    assert digest(source) == rule["source_protocol_sha256"]
    old = long_observation.protocol()
    archived = Path(rule["prior_binding"]["root"]) / "component-protocol.json"
    assert old == json.loads(source.read_text()) == json.loads(archived.read_text())
    for key in (
        "template",
        "template_sha256",
        "dt_s",
        "duration_s",
        "observation_panels",
        "observation_times_us",
        "readout",
        "reader",
        "score_stability",
        "contrast",
        "batch_worlds",
        "window_steps",
        "resources",
    ):
        assert rule[key] == old[key], key
    assert sum(shifted(row) for row in cases()) == 42
    return report | dict(
        physical_model_dose_strengths_observations_and_reader_unchanged=True,
        previously_inspected_case_identities=True,
        changed_late_cue_cases=42,
        unchanged_case_inputs=98,
    )


def definition(base, row, level, backend, rule):
    raw = long_observation.definition(base, row, level, backend, rule)
    if not shifted(row):
        return raw
    cue = rule["cue_timing"]
    pulse = cue["late_pulse_us"]
    if pulse != [104, 112] or cue["original_late_pulse_us"] != [24, 32]:
        raise ValueError("Only the registered fixed-dose late-pulse shift is supported")
    changes = raw["experiment"]["changes"]
    active = [c for c in changes if np.any(np.asarray(c["channel"]) != 1)]
    assert len(active) == 1
    event = active[0]
    assert event["time"] == cue["original_late_pulse_us"][0] * two_task.protocol()["dt_s"]
    inhibition = event["channel"]
    baseline_channel = [1.0] * len(inhibition)
    event["channel"] = baseline_channel
    # Retain the old baseline event times; only add the delayed on/off pair.
    changes.extend(
        event | {"time": step * two_task.protocol()["dt_s"], "channel": channel}
        for step, channel in zip(pulse, (inhibition, baseline_channel), strict=True)
    )
    assert all(a["time"] < b["time"] for a, b in zip(changes, changes[1:], strict=False))
    return raw


def batch(base, rows, level, backend, rule):
    return BatchSpec(
        tuple(
            WorldSpec(row["world_id"], parse_spec(definition(base, row, level, backend, rule)))
            for row in rows
        ),
        rule["batch_worlds"],
        rule["batch_worlds"] * (round(rule["duration_s"] / rule["dt_s"][level]) + 7),
        rule["resources"]["max_batch_working_bytes"],
    )
