"""Paired junction-permeability transfer with archived, fixed calibration.

The old strength cohort is reused deliberately. Neither target calibration
responses nor evaluation labels can modify the primary source reader.
"""

import copy
import json
from pathlib import Path

import numpy as np

from cells.core.batch import BatchSpec, WorldSpec
from cells.core.specs import parse_spec
from validation.assays import baseline_transfer_diagnostic as reference
from validation.assays import distributed_timing, template_readout, two_task
from validation.assays import source_order_pulse_confirmation as previous
from validation.assays.source_order_pulse_confirmation import archived_segment as archived_segment
from validation.assays.source_order_pulse_confirmation import (
    compare_reader_predictions as compare_reader_predictions,
)
from validation.assays.source_order_pulse_confirmation import features as features
from validation.assays.source_order_pulse_confirmation import ordered as ordered
from validation.assays.source_order_pulse_confirmation import paired_contrasts as paired_contrasts
from validation.assays.source_order_pulse_confirmation import paired_report as paired_report
from validation.assays.source_order_pulse_confirmation import reader_reports as reader_reports
from validation.assays.source_order_pulse_confirmation import reference_reports as reference_reports
from validation.assays.source_order_pulse_confirmation import times as times
from validation.assays.source_order_pulse_confirmation import world_name as world_name
from validation.betse.spatial_active.refinement import digest

PROTOCOL_PATH = Path(__file__).with_name("source_order_long") / "coupling_transfer_protocol.json"
SOURCE = previous.protocol()
SOURCE_ROWS = previous.cases(SOURCE)
CONDITIONS = [
    dict(id="lower", permeability_scale=0.9, world_id_offset=500000),
    dict(id="higher", permeability_scale=1.1, world_id_offset=520000),
]


def protocol():
    return json.loads(PROTOCOL_PATH.read_text())


def condition_rule(rule, name):
    if rule["coupling_conditions"] != CONDITIONS:
        raise ValueError("Unregistered coupling conditions")
    matches = [c for c in CONDITIONS if c["id"] == name]
    if len(matches) != 1:
        raise ValueError("Unregistered coupling condition")
    condition = matches[0].copy()
    return copy.deepcopy(rule) | dict(
        condition=condition,
        world_id_offset=condition["world_id_offset"],
        work=rule["work_per_condition"].copy(),
    )


def cases(rule):
    return previous.cases(rule)


def source_row(row):
    matches = [
        old
        for old in SOURCE_ROWS
        if {k: v for k, v in old.items() if k != "world_id"}
        == {k: v for k, v in row.items() if k != "world_id"}
    ]
    if len(matches) != 1:
        raise ValueError("No unique paired source case")
    return matches[0]


def definition(base, row, level, backend, rule):
    if rule["condition"] not in CONDITIONS:
        raise ValueError("Unregistered coupling condition")
    raw = previous.definition(base, row, level, backend, rule)
    tissue = raw["model"]["tissue"]
    tissue["junction_permeability"] = (
        np.asarray(tissue["junction_permeability"]) * rule["condition"]["permeability_scale"]
    ).tolist()
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
    # Connected histories may change immediately, even without a cue.
    return source_row(row), SOURCE["duration_s"] if row["arm"] == "disconnected" else 0.0


def validate_design(rule):
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
        "preparations",
    ):
        assert rule[key] == SOURCE[key], key
    assert rule["coupling_conditions"] == CONDITIONS
    assert rule["work_per_condition"] == SOURCE["work"]
    assert rule["work"] == {k: 2 * v for k, v in SOURCE["work"].items()}
    assert rule["automatic_followup"] is False
    assert rule["frozen_reader_source"]["backend"] == "cpu"
    assert rule["frozen_reader_source"]["calibration"] == "archived_source_at_matching_timestep"
    root = Path(rule["prior_binding"]["root"])
    assert not (root / "failure.json").exists()
    for name, key in (
        ("registration.json", "registration_sha256"),
        ("completion.json", "completion_sha256"),
    ):
        assert digest(root / name) == rule["prior_binding"][key]
    done = json.loads((root / "completion.json").read_text())
    assert done["status"] == "completed"
    assert digest(root / "result.json") == done["result_sha256"]
    registration = json.loads((root / "registration.json").read_text())
    assert digest(root / "component-protocol.json") == registration["component_protocol_sha256"]
    assert registration["component_protocol_sha256"] == rule["source_component_protocol_sha256"]
    assert json.loads((root / "component-protocol.json").read_text()) == SOURCE
    assert digest(two_task.ROOT / rule["source_protocol"]) == rule["source_protocol_sha256"]
    for relative, expected in rule["frozen_reader_source"]["files_sha256"].items():
        assert digest(root / relative) == expected == done["evidence_sha256"][relative]
    return dict(
        status="passed",
        source_binding=rule["prior_binding"],
        source_readers_bound_to_completed_manifest=True,
        coupling_conditions=CONDITIONS,
        same_strength_cohort=True,
        fresh_strength_validation=False,
        independent_biological_replicates=0,
    )


def baseline(rule):
    design = validate_design(rule)
    accepted = two_task.baseline(rule)
    return dict(status="passed", design=design, accepted=accepted)


def remap_report(value, identities):
    """Change external case identities only, preserving every reader coefficient."""
    if isinstance(value, list):
        return [remap_report(v, identities) for v in value]
    if isinstance(value, dict):
        return {
            k: identities[v]
            if k == "world_id"
            else [identities[i] for i in v]
            if k == "world_ids"
            else remap_report(v, identities)
            for k, v in value.items()
        }
    return value


def load_source(rule, rows):
    root = Path(rule["prior_binding"]["root"])
    files = rule["frozen_reader_source"]["files_sha256"]
    for relative, expected in files.items():
        assert digest(root / relative) == expected
    directory = root / "evidence" / "cpu"
    saved_reports = json.loads(
        (directory / "source-order-pulse-confirmation-readouts.json").read_text()
    )["panels"]
    identities = {source_row(r)["world_id"]: r["world_id"] for r in rows}
    maps = {}
    with np.load(
        directory / "source-order-pulse-confirmation-readouts.npz", allow_pickle=False
    ) as saved:
        for level in range(3):
            for name in rule["observation_panels"]:
                maps[level, name] = {
                    new: saved[f"{level}__{name}__voltage__{old}"].copy()
                    for old, new in identities.items()
                }
    reports = {
        (level, name): remap_report(
            saved_reports[name]["resolution_matched"][level]["outcomes"]["voltage"], identities
        )
        for level in range(3)
        for name in rule["observation_panels"]
    }
    return maps, reports


def paired_coupling_report(current, original, name):
    report = paired_report(current, original, primary_name=name, comparator_name="source_1.0")
    return report | dict(paired_same_trajectories=False, paired_same_input_cases=True)


def transfer_panel(rows, source, target, rule):
    """Primary uses source calibration only; centering is a labelled diagnostic."""
    margin = rule["reader"]["voltage_margin_V"]
    old = template_readout.evaluate(rows, source, margin=margin)
    raw = reference.transfer(
        rows, source, target, source_reference=0, target_reference=0, margin=margin
    )
    source_reference, source_control = reference.no_cue_reference(rows, source)
    target_reference, target_control = reference.no_cue_reference(rows, target)
    centered = reference.transfer(
        rows,
        source,
        target,
        source_reference=source_reference,
        target_reference=target_reference,
        margin=margin,
    )
    # The primary curves must reproduce the original bitwise, not just agree on labels.
    for arm in old["arms"]:
        assert raw["arms"][arm]["calibration"] == old["arms"][arm]["calibration"]
    return dict(
        source=old,
        raw=raw,
        no_cue_referenced=centered,
        source_control=source_control,
        target_control=target_control,
        raw_vs_source=paired_coupling_report(raw, old, rule["condition"]["id"]),
        referenced_vs_source=paired_coupling_report(centered, old, "reference_assisted"),
        drift=reference.drift(rows, source, target, source_reference, target_reference),
        target_stimulated_calibration_used=False,
        reference_assisted_is_not_unassisted_transfer=True,
    )


def coupling_reports(rows, maps, rule, source):
    old_maps, old_reports = source
    panels = {}
    for name in rule["observation_panels"]:
        levels = []
        for level in range(3):
            report = transfer_panel(rows, old_maps[level, name], maps[level, name]["voltage"], rule)
            assert report["source"] == old_reports[level, name]
            levels.append(report | dict(level=level))
        panels[name] = dict(
            levels=levels,
            score_stability={
                mode: distributed_timing.score_changes(
                    [r[mode] for r in levels], rule["score_stability"]
                )
                for mode in ("raw", "no_cue_referenced")
            },
        )
    primary = panels[rule["primary_panel"]]["levels"][2]["raw"]["arms"]["joint"]["joint"]
    return dict(
        status="passed",
        condition=rule["condition"],
        panels=panels,
        primary=dict(panel=rule["primary_panel"], level=2, mode="raw", joint=primary),
        source_backend="cpu",
        fixed_source_readers=90,
        within_condition_recalibration_is_separate_diagnostic=True,
        same_strength_cohort=True,
        independent_biological_replicates=0,
        scientific_outcomes_are_not_acceptance_gates=True,
    )
