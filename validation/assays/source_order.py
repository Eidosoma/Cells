"""Location allocation and source-pulse order at fixed per-source dose.

The inherited reader's wire label ``timing`` denotes source order here, not the
previous common early/late cue. Its meanings are explicit in the new protocol.
"""

import json
from pathlib import Path

import numpy as np

from cells.core.batch import BatchSpec, WorldSpec
from cells.core.specs import parse_spec
from validation.assays import baseline_transfer_diagnostic as reference_reader
from validation.assays import cue_separation as previous
from validation.assays import two_task
from validation.assays import unstimulated_readout as distributed
from validation.assays.long_observation import archived_segment as archived_segment
from validation.assays.long_observation import (
    compare_reader_predictions as compare_reader_predictions,
)
from validation.assays.long_observation import features as features
from validation.assays.long_observation import paired_contrasts as paired_contrasts
from validation.assays.long_observation import reader_reports as reader_reports
from validation.assays.long_observation import times as times
from validation.assays.long_observation import world_name as world_name
from validation.betse.spatial_active.refinement import digest

PROTOCOL_PATH = Path(__file__).with_name("source_order_protocol.json")


def protocol():
    return json.loads(PROTOCOL_PATH.read_text())


def physical_rule(rule):
    return distributed.protocol() | {
        "preparations": rule["preparations"],
        "world_id_offset": rule["world_id_offset"],
    }


def cases(rule=None):
    return distributed.cases(physical_rule(protocol() if rule is None else rule))


def ordered(row):
    return row["arm"] in ("timing_only", "joint", "disconnected")


def historical_unchanged(row):
    return row["arm"] == "no_cue" or (
        row["arm"] == "location_only" and row["split"] == "calibration"
    )


def prior_identity(row, rule):
    return row["world_id"] - rule["world_id_offset"] + distributed.protocol()["world_id_offset"]


def baseline(rule):
    report = two_task.baseline(rule)
    source = two_task.ROOT / rule["source_protocol"]
    assert digest(source) == rule["source_protocol_sha256"]
    old = previous.protocol()
    assert old == json.loads(source.read_text())
    for key in (
        "template",
        "template_sha256",
        "dt_s",
        "duration_s",
        "observation_panels",
        "observation_times_us",
        "readout",
        "score_stability",
        "contrast",
        "batch_worlds",
        "window_steps",
        "resources",
    ):
        assert rule[key] == old[key], key
    for key in (
        "type",
        "voltage_margin_V",
        "coarse_voltage_margin_V",
        "input_margin",
        "modes",
        "primary_mode",
        "shuffle_seeds",
    ):
        assert rule["reader"][key] == old["reader"][key], key
    diagnoses = []
    for binding in rule["diagnostic_bindings"]:
        root = Path(binding["root"])
        assert not (root / "failure.json").exists()
        assert digest(root / "completion.json") == binding["completion_sha256"]
        done = json.loads((root / "completion.json").read_text())
        assert done["status"] == "completed"
        for name, key in (("inputs.json", "inputs_sha256"), ("result.json", "result_sha256")):
            assert digest(root / name) == done[key]
        for name, sha in done.get("evidence_sha256", {}).items():
            assert digest(root / name) == sha
        inputs = json.loads((root / "inputs.json").read_text())
        assert inputs["source_binding"] == rule["prior_binding"]
        for name, sha in inputs["diagnostic_sources_sha256"].items():
            assert digest(root / "source" / name) == digest(two_task.ROOT / name) == sha
        diagnoses.append(
            dict(
                root=str(root),
                status="passed",
                unchanged_sources=len(inputs["diagnostic_sources_sha256"]),
            )
        )
    return report | dict(
        diagnoses=diagnoses,
        physical_model_and_tolerances_unchanged=True,
        task_meanings=rule["task_meanings"],
        new_temporal_task=True,
        evaluation_strengths_fixed_before_responses=True,
    )


def dose_matched_common_pulse(base, row, level, backend, rule):
    """The old simultaneous-source encoding at the new, predeclared strength."""
    if type(level) is not int or not 0 <= level < len(rule["dt_s"]):
        raise ValueError("Unregistered timestep")
    raw = distributed.definition(base, row, backend, physical_rule(rule))
    raw["execution"]["dt"] = rule["dt_s"][level]
    raw["experiment"]["end_time"] = rule["duration_s"]
    raw["experiment"]["observation_times"] = sorted(
        {float(t) for panel in rule["observation_panels"] for t in times(rule, panel)}
    )
    return raw


def definition(base, row, level, backend, rule):
    raw = dose_matched_common_pulse(base, row, level, backend, rule)
    if not ordered(row):
        return raw
    cue = rule["cue_timing"]
    if cue["early_pulse_us"] != [8, 16] or cue["late_pulse_us"] != [104, 112]:
        raise ValueError("Only the registered source-order pulses are supported")
    changes = raw["experiment"]["changes"]
    active = [c for c in changes if np.any(np.asarray(c["channel"]) != 1)]
    assert len(active) == 1
    inhibition = 1 - np.asarray(active[0]["channel"])
    owner = np.asarray(raw["model"]["tissue"]["cell_owner"])
    sources = rule["source_cell_ids"]
    first, second = sources[row["timing"]], sources[1 - row["timing"]]
    scheduled = []
    for step in (0, 8, 16, 24, 32, 104, 112):
        selected = first if 8 <= step < 16 else second if 104 <= step < 112 else None
        channel = np.ones_like(inhibition)
        if selected is not None:
            mask = owner == selected - 1
            channel[mask] -= inhibition[mask]
        scheduled.append(
            changes[0] | dict(time=step * two_task.protocol()["dt_s"], channel=channel.tolist())
        )
    raw["experiment"]["changes"] = scheduled
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


def reference_reports(rows, maps, reports, rule):
    """All source/target transfers with a shared no-cue control, separately from primary."""
    features = [maps[level, "long256"]["voltage"] for level in range(3)]
    references = [reference_reader.no_cue_reference(rows, values) for values in features]
    results, checks = [], []
    margin = rule["reader"]["voltage_margin_V"]
    for source in range(3):
        for target in range(3):
            translated = reference_reader.transfer(
                rows,
                features[source],
                features[target],
                source_reference=references[source][0],
                target_reference=references[target][0],
                margin=margin,
            )
            results.append(dict(source_level=source, target_level=target, outcomes=translated))
            if source == target:
                original = reports["long256"]["resolution_matched"][source]["outcomes"]["voltage"]
                checks.append(
                    reference_reader.translation_check(original, translated) | dict(level=source)
                )
    return dict(
        status="passed",
        task_meanings=rule["task_meanings"],
        references=[details | dict(level=level) for level, (_, details) in enumerate(references)],
        transfers=results,
        matched_translation_checks=checks,
        target_timestep_no_cue_information_supplied=True,
        primary_endpoint_unchanged=True,
        transfer_success_is_not_an_acceptance_gate=True,
    )
