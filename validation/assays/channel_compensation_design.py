"""Prepare calibration inputs; no simulation, selection or acceptance is performed.

The source campaign must be completed and bound by a later execution protocol.
This builder keeps channel changes off the cue sources and holds the junction
impairment fixed. It reuses the already qualified physical input definitions.
"""

import copy
import json
from pathlib import Path

import numpy as np

from validation.assays import source_order_coupling_transfer as coupling
from validation.assays import two_task
from validation.betse.spatial_active.refinement import digest

PLAN = Path(__file__).with_name("source_order_long") / "channel_compensation_plan.json"
CONDITIONS = [
    dict(id="sham", channel_scale=1.0, world_id_offset=540000),
    dict(id="channel_lower", channel_scale=0.9, world_id_offset=560000),
    dict(id="channel_higher", channel_scale=1.1, world_id_offset=580000),
]


def plan():
    return json.loads(PLAN.read_text())


def validate_plan(design):
    source = coupling.protocol()
    if (
        design["kind"] != "source_order_channel_compensation_design@1"
        or design["conditions"] != CONDITIONS
        or digest(two_task.ROOT / design["source_protocol"]) != design["source_protocol_sha256"]
        or json.loads((two_task.ROOT / design["source_protocol"]).read_text()) != source
        or design["automatic_followup"] is not False
    ):
        raise ValueError("Unregistered compensation design or source protocol")
    impairment, control, calibration = (
        design["impairment"],
        design["alternative_control"],
        design["calibration"],
    )
    if (
        impairment["parameter"] != "model.tissue.junction_permeability"
        or impairment["scale"] != 0.9
        or control["parameter"] != "model.channel_permeability"
        or control["cell_ids"] != source["readout"]["cell_ids"]
        or control["excluded_source_cell_ids"] != source["source_cell_ids"]
        or control["scales"] != [0.9, 1.0, 1.1]
        or calibration["strengths"] != [0.4, 0.6, 0.8]
        or calibration["dt_s"] != source["dt_s"]
        or calibration["duration_s"] != source["duration_s"]
        or calibration["reader_margin_V"] != source["reader"]["voltage_margin_V"]
        or calibration["primary_panel"] != source["primary_panel"]
        or calibration["primary_times_us"] != source["observation_times_us"]["selected320"]
        or calibration["remote_cell_ids"] != source["readout"]["cell_ids"]
        or calibration["arms"] != two_task.protocol()["arms"]
    ):
        raise ValueError("Compensation changes the frozen impairment, controls or assay")
    return source


def condition_rule(design, name):
    source = validate_plan(design)
    matches = [c for c in CONDITIONS if c["id"] == name]
    if len(matches) != 1:
        raise ValueError("Unregistered compensation condition")
    condition = copy.deepcopy(matches[0])
    rule = coupling.condition_rule(source, "lower")
    rule["preparations"] = [p for p in rule["preparations"] if p["split"] == "calibration"]
    rule["world_id_offset"] = condition["world_id_offset"]
    rule["work"] = dict(
        worlds_per_timestep=60,
        worlds_per_backend=180,
        world_steps_per_backend=860160,
        world_steps_per_arm_per_backend=172032,
    )
    # This is a physical-input recipe only, not a runnable acceptance protocol.
    return rule | dict(channel_compensation=condition)


def cases(design, name):
    return coupling.cases(condition_rule(design, name))


def definition(base, row, level, backend, design, name):
    rule = condition_rule(design, name)
    if row not in coupling.cases(rule):
        raise ValueError("Only registered calibration cases are allowed")
    raw = coupling.definition(base, row, level, backend, rule)
    model = raw["model"]
    owner = np.asarray(model["tissue"]["cell_owner"])
    mask = np.isin(owner + 1, design["alternative_control"]["cell_ids"])
    permeability = np.asarray(model["channel_permeability"]).copy()
    permeability[mask] *= rule["channel_compensation"]["channel_scale"]
    model["channel_permeability"] = permeability.tolist()
    return raw
