"""Fixed-cue observations through 256 us, with matched timestep checks.

Only horizon, observation times and integration resolution vary. The previous
strength panel is reused deliberately; it is not fresh generalization evidence.
"""

import json
from pathlib import Path

import numpy as np

from cells.assays.readout import VoltageReadout
from cells.core.batch import BatchSpec, WorldSpec
from cells.core.specs import parse_spec
from validation.assays import distributed_timing, template_readout, timing_refinement, two_task
from validation.assays import unstimulated_readout as previous
from validation.betse.spatial_active.refinement import completed_prior, digest

PROTOCOL_PATH = Path(__file__).with_name("long_observation_protocol.json")


def protocol():
    return json.loads(PROTOCOL_PATH.read_text())


def cases():
    return previous.cases(previous.protocol())


def baseline(rule):
    current = two_task.baseline(rule)
    source = two_task.ROOT / rule["source_protocol"]
    assert digest(source) == rule["source_protocol_sha256"]
    old = previous.protocol()
    assert old == json.loads(source.read_text())
    binding = rule["historical_binding"]
    root = Path(binding["root"])
    history = completed_prior(binding, current_root=root / "source")
    assert history["completion_sha256"] == binding["completion_sha256"]
    assert old == json.loads((root / "component-protocol.json").read_text())
    for key in (
        "type",
        "voltage_margin_V",
        "coarse_voltage_margin_V",
        "input_margin",
        "shuffle_seeds",
        "modes",
        "primary_mode",
    ):
        assert rule["reader"][key] == old["reader"][key], key
    assert rule["readout"] == {k: old["readout"][k] for k in rule["readout"]}
    return dict(
        status="passed",
        runtime=current,
        historical_assay=history,
        physical_model_cues_strengths_and_reader_unchanged=True,
        historical_panel_is_not_fresh_holdout=True,
    )


def times(rule, panel):
    if panel not in rule["observation_panels"]:
        raise ValueError("Unregistered observation panel")
    old = two_task.protocol()
    factor = rule["observation_panels"][panel]
    return np.asarray([step * old["dt_s"] * factor for step in old["readout_steps"]])


def definition(base, row, level, backend, rule):
    if type(level) is not int or not 0 <= level < len(rule["dt_s"]):
        raise ValueError("Unregistered timestep")
    raw = previous.definition(base, row, backend, previous.protocol())
    raw["execution"]["dt"] = rule["dt_s"][level]
    raw["experiment"]["end_time"] = rule["duration_s"]
    raw["experiment"]["observation_times"] = sorted(
        {float(t) for panel in rule["observation_panels"] for t in times(rule, panel)}
    )
    return raw


def batch(base, rows, level, backend, rule):
    return BatchSpec(
        tuple(
            WorldSpec(row["world_id"], parse_spec(definition(base, row, level, backend, rule)))
            for row in rows
        ),
        rule["batch_worlds"],
        rule["batch_worlds"]
        * (
            round(rule["duration_s"] / rule["dt_s"][level])
            + len(two_task.protocol()["control_steps"])
        ),
        rule["resources"]["max_batch_working_bytes"],
    )


def features(result, rule, panel):
    layout = result.final.layout

    def voltage(ids):
        return VoltageReadout(tuple(ids), tuple(map(float, times(rule, panel)))).observe(
            result.observations.times,
            result.observations.membrane_voltage_V,
            cell_ids=np.asarray(layout.ids),
            cell_owner=np.asarray(layout.tissue_cell_owner),
            membrane_area=np.asarray(layout.tissue_membrane_area),
        )

    old = two_task.protocol()
    selected = old | {"readout_cell_ids": rule["readout"]["cell_ids"]}
    factor = rule["observation_panels"][panel]
    values = voltage(selected["readout_cell_ids"])
    return dict(
        voltage=values,
        final_voltage=values[-len(selected["readout_cell_ids"]) :],
        all_cell_voltage=voltage(rule["readout"]["all_cell_ids"]),
        input_at_readout=two_task.input_features(
            result.spec, [factor * step for step in old["readout_steps"]], selected
        ),
        input_history=two_task.input_features(result.spec, old["input_history_steps"], selected),
    )


def reader_reports(rows, features_by_panel, rule):
    """Report every preset view; no outcome chooses the reader or primary view."""
    outcomes = {}
    for panel in rule["observation_panels"]:
        levels = [features_by_panel[level, panel] for level in range(3)]
        matched = [previous.reader_reports(rows, modes, rule) for modes in levels]
        frozen, drift = {}, {}
        for mode in ("voltage", "final_voltage", "all_cell_voltage"):
            frozen[mode] = [
                template_readout.evaluate(
                    rows,
                    {
                        row["world_id"]: levels[0 if row["split"] == "calibration" else level][
                            mode
                        ][row["world_id"]]
                        for row in rows
                    },
                    margin=rule["reader"]["voltage_margin_V"],
                )
                for level in range(3)
            ]
            drift[mode] = {
                "resolution_matched": distributed_timing.score_changes(
                    [reports[mode] for reports, _ in matched], rule["score_stability"]
                ),
                "frozen_coarse": distributed_timing.score_changes(
                    frozen[mode], rule["score_stability"]
                ),
            }
        outcomes[panel] = dict(
            resolution_matched=[dict(outcomes=a, shuffles=b) for a, b in matched],
            frozen_coarse=frozen,
            score_stability=drift,
        )
    return outcomes


def paired_contrasts(rows, features_by_panel, rule):
    reports = []
    for panel in rule["observation_panels"]:
        for task in ("location", "timing"):
            other = "timing" if task == "location" else "location"
            for first in rows:
                if first[task] != 0:
                    continue
                second = next(
                    row
                    for row in rows
                    if row[task] == 1
                    and all(row[k] == first[k] for k in ("arm", "preparation", other))
                )
                a, b = first["world_id"], second["world_id"]
                values = timing_refinement.contrast_report(
                    [features_by_panel[level, panel]["voltage"][a] for level in range(3)],
                    [features_by_panel[level, panel]["voltage"][b] for level in range(3)],
                    rule["contrast"],
                )
                values["contrast_V"] = values.pop("timing_contrast_V")
                reports.append(
                    dict(
                        panel=panel,
                        task=task,
                        arm=first["arm"],
                        preparation=first["preparation"],
                        split=first["split"],
                        world_ids=[a, b],
                        independent_biological_replicates=0,
                        **values,
                    )
                )
    return reports


def compare_reader_predictions(actual, expected):
    """Keep decision differences visible even when physical tolerances pass."""
    rows = []
    assert actual.keys() == expected.keys()
    for mode, report in actual.items():
        old = expected[mode]
        assert report["feature_count"] == old["feature_count"]
        for arm, detail in report["arms"].items():
            before = old["arms"][arm]
            assert detail["calibration"]["world_ids"] == before["calibration"]["world_ids"]
            for task, values in detail["tasks"].items():
                pairs = list(
                    zip(values["predictions"], before["tasks"][task]["predictions"], strict=True)
                )
                assert all(
                    (a["world_id"], a["target"]) == (b["world_id"], b["target"]) for a, b in pairs
                )
                rows.append(
                    dict(
                        mode=mode,
                        arm=arm,
                        task=task,
                        max_score_difference=max(abs(a["score"] - b["score"]) for a, b in pairs),
                        differing_decision_world_ids=[
                            a["world_id"]
                            for a, b in pairs
                            if (a["prediction"], a["resolved"]) != (b["prediction"], b["resolved"])
                        ],
                    )
                )
    return rows


def world_name(level, identity):
    return f"long-observation-world-{level}-{identity}"


def archived_segment(archive, level, identity, start, stop, observation_times):
    """Read an arbitrary inclusive state interval from immutable saved windows."""
    record = json.loads((archive / (world_name(level, identity) + ".json")).read_text())
    assert record["status"] == "passed"
    pieces, next_step, found = {}, start, []
    requested = np.asarray(observation_times)
    for chunk in record["windows"]:
        if chunk["stop_step"] < start or chunk["start_step"] > stop:
            continue
        first, last = max(next_step, chunk["start_step"]), min(stop, chunk["stop_step"])
        observed_times = np.asarray(chunk["observation_times"])
        mask = np.isin(observed_times, requested)
        found.extend(observed_times[mask].tolist())
        with np.load(archive / chunk["file"], allow_pickle=False) as saved:
            for name in saved:
                if name.startswith("observed__"):
                    part = saved[name][mask]
                else:
                    part = saved[name][first - chunk["start_step"] : last - chunk["start_step"] + 1]
                pieces.setdefault(name, []).append(part)
        next_step = max(next_step, last + 1)
    assert next_step == stop + 1
    np.testing.assert_array_equal(found, requested)
    return {name: np.concatenate(parts) for name, parts in pieces.items()}
