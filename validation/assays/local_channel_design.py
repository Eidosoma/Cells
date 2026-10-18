"""Prepare paired flank-channel inputs from the completed uniform-channel sham.

This module prepares inputs only. Local causal effects have not been measured;
the execution harness must qualify them before any candidate can be selected.
"""

import copy
import json
from pathlib import Path

import numpy as np

from validation.assays import channel_compensation as source
from validation.betse.spatial_active.refinement import digest

PLAN = Path(__file__).with_name("source_order_long") / "local_channel_plan.json"
CONDITIONS = [
    dict(id="sham", cell_ids=[], channel_scale=1.0, world_id_offset=600000),
    dict(id="source1_flank_lower", cell_ids=[2, 6], channel_scale=0.9, world_id_offset=620000),
    dict(id="source1_flank_higher", cell_ids=[2, 6], channel_scale=1.1, world_id_offset=640000),
    dict(id="source4_flank_lower", cell_ids=[3, 5], channel_scale=0.9, world_id_offset=660000),
    dict(id="source4_flank_higher", cell_ids=[3, 5], channel_scale=1.1, world_id_offset=680000),
]
SOURCE = source.protocol()
SHAM = source.condition_rule(SOURCE, "sham")
SOURCE_ROWS = source.cases(SHAM)


def plan():
    return json.loads(PLAN.read_text())


def validate_plan(design):
    if (
        design["kind"] != "source_order_local_channel_design@1"
        or design["conditions"] != CONDITIONS
        or design["automatic_followup"] is not False
        or design["source_protocol"] != str(source.PROTOCOL_PATH.relative_to(source.two_task.ROOT))
        or design["source_protocol_sha256"] != digest(source.PROTOCOL_PATH)
        or json.loads(source.PROTOCOL_PATH.read_text()) != SOURCE
    ):
        raise ValueError("Unregistered local-channel design or source")
    frozen = design["fixed_assay"]
    if (
        frozen["junction_permeability_scale"] != 0.9
        or frozen["source_cell_ids"] != SOURCE["source_cell_ids"]
        or frozen["central_cell_id"] != 7
        or frozen["calibration_strengths"] != [0.4, 0.6, 0.8]
        or frozen["dt_s"] != SOURCE["dt_s"]
        or frozen["duration_s"] != SOURCE["duration_s"]
        or frozen["primary_panel"] != SOURCE["primary_panel"]
        or frozen["primary_times_us"] != SOURCE["observation_times_us"]["selected320"]
        or frozen["readout_cell_ids"] != SOURCE["readout"]["cell_ids"]
        or frozen["reader_margin_V"] != SOURCE["reader"]["voltage_margin_V"]
        or frozen["arms"] != list(source.geometry.ARMS)
        or design["source_binding"]["root"]
        != "/mnt/workspaces/Cells/two-task-channel-compensation-20261017-01"
    ):
        raise ValueError("Local-channel design changes the frozen assay")
    per_condition = SOURCE["work_per_condition"]
    if design["work"] != dict(
        conditions=5,
        worlds_per_condition_per_backend=per_condition["worlds_per_backend"],
        worlds_per_backend=5 * per_condition["worlds_per_backend"],
        world_steps_per_backend=5 * per_condition["world_steps_per_backend"],
        world_steps_per_arm_per_backend=5 * per_condition["world_steps_per_arm_per_backend"],
        new_heldout_worlds=0,
    ):
        raise ValueError("Local-channel work budget differs")
    return SOURCE


def authenticate_bindings(design):
    validate_plan(design)
    for key in ("source_binding", "diagnostic_binding"):
        binding = design[key]
        root = Path(binding["root"])
        assert not (root / "failure.json").exists()
        for name in ("completion", "result"):
            assert digest(root / (name + ".json")) == binding[name + "_sha256"]
        completion = json.loads((root / "completion.json").read_text())
        assert completion["status"] == binding["status"]
        assert completion["result_sha256"] == binding["result_sha256"]
        if key == "source_binding":
            assert digest(root / "registration.json") == binding["registration_sha256"]
            assert digest(root / "component-protocol.json") == binding["component_protocol_sha256"]
            assert json.loads((root / "component-protocol.json").read_text()) == SOURCE
        else:
            assert digest(root / "inputs.json") == completion["inputs_sha256"]
    return dict(status="passed", completed_records_bound=True, full_archive_audit=False)


def condition_rule(design, name):
    validate_plan(design)
    matches = [c for c in CONDITIONS if c["id"] == name]
    if len(matches) != 1:
        raise ValueError("Unregistered local-channel condition")
    condition = copy.deepcopy(matches[0])
    return copy.deepcopy(SHAM) | dict(
        local_channel=condition, world_id_offset=condition["world_id_offset"]
    )


def cases(design, name):
    return source.cases(condition_rule(design, name))


def predecessor(row):
    identity = {key: value for key, value in row.items() if key != "world_id"}
    matches = [
        r
        for r in SOURCE_ROWS
        if {key: value for key, value in r.items() if key != "world_id"} == identity
    ]
    if len(matches) != 1:
        raise ValueError("No unique calibration predecessor")
    return matches[0]


def definition(base, row, level, backend, design, name):
    configured = condition_rule(design, name)
    if row not in source.cases(configured):
        raise ValueError("Only registered calibration cases are allowed")
    condition = configured["local_channel"]
    raw = source.definition(base, predecessor(row), level, backend, SHAM)
    owner = np.asarray(raw["model"]["tissue"]["cell_owner"]) + 1
    permeability = np.asarray(raw["model"]["channel_permeability"]).copy()
    permeability[np.isin(owner, condition["cell_ids"])] *= condition["channel_scale"]
    raw["model"]["channel_permeability"] = permeability.tolist()
    return raw
