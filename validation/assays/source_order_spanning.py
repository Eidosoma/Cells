"""Confirm fixed early/late observations on fresh source-order strengths."""

import json
from pathlib import Path

import numpy as np

from cells.core.batch import BatchSpec, WorldSpec
from cells.core.specs import parse_spec
from validation.assays import source_order_long as previous
from validation.assays import source_order_precision as precision
from validation.assays import two_task
from validation.assays.source_order_long import archived_segment as archived_segment
from validation.assays.source_order_long import (
    compare_reader_predictions as compare_reader_predictions,
)
from validation.assays.source_order_long import ordered as ordered
from validation.assays.source_order_long import paired_contrasts as paired_contrasts
from validation.assays.source_order_long import reader_reports as reader_reports
from validation.assays.source_order_long import reference_reports as reference_reports
from validation.assays.source_order_long import world_name as world_name
from validation.betse.spatial_active.refinement import digest

PROTOCOL_PATH = Path(__file__).with_name("source_order_long") / "spanning_protocol.json"
SOURCE = precision.protocol()
SOURCE_ROWS = previous.cases(SOURCE)
SPANNING_PANELS = ("middle128", "long256", "long512")


def protocol():
    return json.loads(PROTOCOL_PATH.read_text())


def cases(rule=None):
    return previous.cases(protocol() if rule is None else rule)


def physical_rule(rule):
    # The extra analysis panel uses already-recorded observations. Preserve the
    # preceding 12 observation times and all integration inputs exactly.
    return rule | {
        "observation_panels": SOURCE["observation_panels"],
        "observation_times_us": SOURCE["observation_times_us"],
    }


def times(rule, panel):
    if panel == "spanning512":
        return np.asarray([previous.times(physical_rule(rule), p)[-1] for p in SPANNING_PANELS])
    return previous.times(physical_rule(rule), panel)


def definition(base, row, level, backend, rule):
    return previous.definition(base, row, level, backend, physical_rule(rule))


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


def features(result, rule, panel):
    if panel != "spanning512":
        return previous.features(result, physical_rule(rule), panel)
    parts = [previous.features(result, physical_rule(rule), p) for p in SPANNING_PANELS]
    remote, all_cells = len(rule["readout"]["cell_ids"]), len(rule["readout"]["all_cell_ids"])
    for part in parts[1:]:
        np.testing.assert_array_equal(part["input_history"], parts[0]["input_history"])
    return dict(
        voltage=np.concatenate([p["voltage"][-remote:] for p in parts]),
        final_voltage=parts[-1]["final_voltage"],
        all_cell_voltage=np.concatenate([p["all_cell_voltage"][-all_cells:] for p in parts]),
        input_at_readout=np.concatenate([p["input_at_readout"][-remote:] for p in parts]),
        input_history=parts[0]["input_history"],
    )


def historical_source(row):
    """Full unchanged calibration/null histories; common pre-cue prefix otherwise."""
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


def baseline(rule):
    accepted = two_task.baseline(rule)
    assert json.loads((two_task.ROOT / rule["source_protocol"]).read_text()) == SOURCE
    assert digest(two_task.ROOT / rule["source_protocol"]) == rule["source_protocol_sha256"]
    assert digest(two_task.ROOT / rule["design_plan"]) == rule["design_plan_sha256"]
    plan = json.loads((two_task.ROOT / rule["design_plan"]).read_text())
    assert rule["prior_binding"] == plan["source_binding"] | {"require_completed_cpu_and_gpu": True}
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
    ):
        assert rule[key] == SOURCE[key], key
    assert rule["world_id_offset"] == plan["world_id_offset"]
    assert [r["amplitude"] for r in rule["preparations"] if r["split"] == "heldout"] == plan[
        "evaluation_strengths"
    ]
    assert [r for r in rule["preparations"] if r["split"] == "calibration"] == [
        r for r in SOURCE["preparations"] if r["split"] == "calibration"
    ]
    assert rule["primary_panel"] == "spanning512"
    assert rule["observation_panels"] == SOURCE["observation_panels"] | {"spanning512": None}
    assert rule["observation_times_us"] == SOURCE["observation_times_us"] | {
        "spanning512": plan["reader"]["primary_observation_times_us"]
    }
    assert rule["work"] == {k: plan["execution"][k] for k in rule["work"]}
    binding = rule["diagnostic_binding"]
    folder = Path(binding["root"])
    assert not (folder / "failure.json").exists()
    assert digest(folder / "completion.json") == binding["completion_sha256"]
    done = json.loads((folder / "completion.json").read_text())
    assert done["status"] == "completed"
    for name, key in (("inputs.json", "inputs_sha256"), ("result.json", "result_sha256")):
        assert digest(folder / name) == done[key], name
    inputs = json.loads((folder / "inputs.json").read_text())
    assert inputs["source_binding"] == rule["prior_binding"]
    for name, sha in inputs["diagnostic_sources_sha256"].items():
        assert digest(folder / "source" / name) == digest(two_task.ROOT / name) == sha
    assert {str(p.relative_to(two_task.ROOT)) for p in (two_task.ROOT / "src").rglob("*.py")} == {
        name
        for name in json.loads(
            (Path(rule["prior_binding"]["root"]) / "registration.json").read_text()
        )["sources_sha256"]
        if name.startswith("src/")
    }
    return dict(
        status="passed",
        accepted=accepted,
        diagnostic_completion_sha256=binding["completion_sha256"],
        design_plan_sha256=rule["design_plan_sha256"],
        production_physics_cues_reader_and_tolerances_unchanged=True,
        fresh_strength_responses_before_registration=False,
    )


def paired_report(primary, comparator):
    """Paired joint-case outcomes, retaining improvements and regressions equally."""
    a, b = primary["arms"]["joint"], comparator["arms"]["joint"]
    assert primary["feature_count"] == comparator["feature_count"] == 15
    assert a["calibration"]["world_ids"] == b["calibration"]["world_ids"]
    indices = []
    for arm in (a, b):
        by_task = {
            task: {r["world_id"]: r for r in arm["tasks"][task]["predictions"]}
            for task in ("location", "timing")
        }
        for task in by_task:
            assert len(by_task[task]) == len(arm["tasks"][task]["predictions"])
        assert by_task["location"].keys() == by_task["timing"].keys()
        indices.append(by_task)
    assert indices[0]["location"].keys() == indices[1]["location"].keys()
    counts = dict(spanning_only=0, late_only=0, both=0, neither=0)
    rows = []
    for identity in indices[0]["location"]:
        details = [{task: group[task][identity] for task in group} for group in indices]
        assert all(details[0][t]["target"] == details[1][t]["target"] for t in details[0])
        resolved = [
            all(r["resolved"] and r["prediction"] == r["target"] for r in detail.values())
            for detail in details
        ]
        category = ("neither", "late_only", "spanning_only", "both")[2 * resolved[0] + resolved[1]]
        counts[category] += 1
        rows.append(
            dict(world_id=identity, spanning=details[0], late=details[1], category=category)
        )
    return dict(
        cases=rows,
        counts=counts,
        spanning_minus_late_resolved_cases=counts["spanning_only"] - counts["late_only"],
        paired_same_trajectories=True,
        scientific_outcome_is_not_an_acceptance_gate=True,
    )
