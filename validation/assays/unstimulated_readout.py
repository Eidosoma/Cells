"""Fixed observations outside the two directly inhibited source cells.

Physical inputs and the reader algorithm come from the qualified distributed
cue. Calibration and evaluation use one fixed timestep and observation support.
The all-cell comparator is recorded separately and cannot enter the primary fit.
"""

import json
from pathlib import Path

import numpy as np

from cells.assays.readout import VoltageReadout
from validation.assays import distributed_cue, distributed_timing, template_readout, two_task
from validation.assays.distributed_cue import batch as batch
from validation.assays.distributed_cue import cases as cases
from validation.assays.distributed_cue import definition as definition
from validation.betse.spatial_active.refinement import digest

PROTOCOL_PATH = Path(__file__).with_name("unstimulated_readout_protocol.json")


def protocol():
    return json.loads(PROTOCOL_PATH.read_text())


def baseline(rule):
    report = two_task.baseline(rule)
    source = two_task.ROOT / rule["source_protocol"]
    assert digest(source) == rule["source_protocol_sha256"]
    previous = json.loads(
        (Path(rule["prior_binding"]["root"]) / "component-protocol.json").read_text()
    )
    assert previous == json.loads(source.read_text()) == distributed_timing.protocol()
    cue = distributed_cue.protocol()
    assert rule["dt_s"] == previous["dt_s"][rule["historical_reproduction"]["level"]]
    assert rule["duration_s"] == previous["duration_s"]
    assert rule["cue"] == cue["cue"]
    for key in (
        "type",
        "voltage_margin_V",
        "coarse_voltage_margin_V",
        "input_margin",
        "shuffle_seeds",
    ):
        assert rule["reader"][key] == cue["reader"][key]
    return report | dict(calibration_step_pinned=True, cue_and_reader_algorithm_unchanged=True)


def observation_rule(rule, *, all_cells=False):
    """Keep exact accepted physical times from the original fixture clock."""
    return two_task.protocol() | {
        "readout_cell_ids": rule["readout"]["all_cell_ids" if all_cells else "cell_ids"]
    }


def voltage_features(result, rule, *, all_cells=False):
    selected = observation_rule(rule, all_cells=all_cells)
    readout = VoltageReadout(
        tuple(selected["readout_cell_ids"]),
        tuple(step * selected["dt_s"] for step in selected["readout_steps"]),
    )
    layout = result.final.layout
    return readout.observe(
        result.observations.times,
        result.observations.membrane_voltage_V,
        cell_ids=np.asarray(layout.ids),
        cell_owner=np.asarray(layout.tissue_cell_owner),
        membrane_area=np.asarray(layout.tissue_membrane_area),
    )


def features(result, rule):
    selected = observation_rule(rule)
    voltage = voltage_features(result, rule)
    return dict(
        voltage=voltage,
        final_voltage=voltage[-len(selected["readout_cell_ids"]) :],
        all_cell_voltage=voltage_features(result, rule, all_cells=True),
        input_at_readout=two_task.input_features(result.spec, selected["readout_steps"], selected),
        input_history=two_task.input_features(
            result.spec, selected["input_history_steps"], selected
        ),
    )


def reader_reports(rows, modes, rule):
    reports = {
        mode: template_readout.evaluate(
            rows,
            values,
            margin=rule["reader"][
                "input_margin" if mode.startswith("input") else "voltage_margin_V"
            ],
        )
        for mode, values in modes.items()
    }
    voltage = modes["voltage"]
    reports["voltage_1uV_margin"] = template_readout.evaluate(
        rows, voltage, margin=rule["reader"]["coarse_voltage_margin_V"]
    )
    reports["balanced_centroid_voltage"] = template_readout.evaluate(
        rows, voltage, margin=rule["reader"]["voltage_margin_V"], centroid=True
    )
    joint = [row for row in rows if row["arm"] == "joint"]
    shuffles = [
        template_readout.evaluate(
            joint, voltage, margin=rule["reader"]["voltage_margin_V"], shuffle_seed=seed
        )
        for seed in rule["reader"]["shuffle_seeds"]
    ]
    return reports, shuffles
