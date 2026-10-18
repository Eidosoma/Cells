"""Explain the completed channel pilot using saved calibration voltages only.

Feature contributions describe where a signal is observed. They do not identify
the effect of changing a particular cell's channels. No new reader, observation
support, simulation, or acceptance threshold is selected here.
"""

import argparse
import json
import shutil
import time
import traceback
from pathlib import Path

import numpy as np

from cells.assembly.cli import output_path, utc
from cells.assembly.io import write_json
from validation.assays import baseline_transfer_diagnostic as background
from validation.assays import channel_compensation as assay
from validation.assays import source_order_observation_design as geometry
from validation.assays.template_readout import TemplateReader
from validation.assays.two_task_diagnostic import compare_replay
from validation.betse.spatial_active.refinement import digest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path("/mnt/workspaces/Cells/two-task-channel-compensation-20261017-01")
COMPLETION_SHA256 = "327837575900507f09ead0d07aa6f6578e1ca90000494264e2f23a16a3687cc3"
STRENGTHS = [0.4, 0.6, 0.8]
CELL_IDS = [2, 3, 5, 6, 7]


def feature(value):
    value = np.asarray(value, dtype=np.float64)
    if value.shape != (15,) or not np.isfinite(value).all():
        raise ValueError("Fifteen finite voltage features required")
    return value


def load_maps(saved, rows):
    training = geometry.calibration_rows(rows, dict(calibration_strengths=STRENGTHS))
    maps, accessed = {}, []
    for level in range(3):
        for panel in assay.PANELS:
            values = {}
            for row in training:
                key = f"{level}__{panel}__voltage__{row['world_id']}"
                values[row["world_id"]] = feature(saved[key]).copy()
                accessed.append(key)
            maps[level, panel] = dict(voltage=values)
    return training, maps, accessed


def distance_parts(delta):
    delta = feature(delta).reshape(3, 5)
    squared = delta * delta
    total = float(squared.sum())
    return dict(
        difference_by_time_cell_V=delta.tolist(),
        distance_V=float(np.sqrt(total)),
        squared_distance_V2=total,
        by_cell_squared_fraction=(squared.sum(axis=0) / total).tolist() if total else None,
        by_time_squared_fraction=(squared.sum(axis=1) / total).tolist() if total else None,
        contribution_is_not_local_channel_sensitivity=True,
    )


def closest_delta(rows, values, group):
    tasks = list(geometry.TASKS)
    selected = [r for r in rows if r["arm"] == group["arm"]]
    if group["arm"].endswith("_only"):
        tasks = [group["arm"].removesuffix("_only")]
        ignored = next(t for t in geometry.TASKS if t != tasks[0])
        selected = [r for r in selected if r[ignored] == 0]
    reader = TemplateReader.fit(
        np.stack([feature(values[r["world_id"]]) for r in selected]),
        np.array([[r[t] for t in tasks] for r in selected]),
        [r["amplitude"] for r in selected],
        minimum_margin=2e-9,
    )
    indices = [reader.labels.tolist().index(label) for label in group["curve_labels"]]
    i, j = group["segments"]
    s, t = group["coordinates"]
    if i not in (0, 1) or j not in (0, 1) or not (0 <= s <= 1 and 0 <= t <= 1):
        raise ValueError("Invalid archived segment coordinates")
    p0, p1 = reader.vertices[indices[0], i : i + 2]
    q0, q1 = reader.vertices[indices[1], j : j + 2]
    # Subtract before interpolation to retain differences of nanovolt signals.
    return (p0 - q0) + s * (p1 - p0) - t * (q1 - q0)


def factorial(values):
    if set(values) != {(0, 0), (0, 1), (1, 0), (1, 1)}:
        raise ValueError("Complete two-by-two label grid required")
    origin = feature(values[0, 0])
    u01, u10, u11 = [feature(values[k]) - origin for k in ((0, 1), (1, 0), (1, 1))]
    location = (u10 + u11 - u01) / 2
    order = (u01 + u11 - u10) / 2
    interaction = u11 - u10 - u01
    denominator = float(np.linalg.norm(location) * np.linalg.norm(order))
    return dict(
        location_effect_V=location.tolist(),
        order_effect_V=order.tolist(),
        interaction_V=interaction.tolist(),
        location_norm_V=float(np.linalg.norm(location)),
        order_norm_V=float(np.linalg.norm(order)),
        interaction_norm_V=float(np.linalg.norm(interaction)),
        effect_cosine=float(location @ order / denominator) if denominator else None,
        opposed_label_pair=distance_parts(u10 - u01),
        aligned_label_pair=distance_parts(u11),
        opposed_pair_identity_error_V=float(np.max(np.abs((location - order) - (u10 - u01)))),
        aligned_pair_identity_error_V=float(np.max(np.abs((location + order) - u11))),
    )


def condition_diagnosis(rows, maps, report, rule):
    replay = assay.calibration_geometry(rows, maps, rule)
    replay_error = compare_replay(replay, report["geometry"])
    panels = {}
    for panel in assay.PANELS:
        archived = report["geometry"]["panels"][panel]
        groups = []
        for group in archived["task_groups"]:
            parts = distance_parts(
                closest_delta(rows, maps[group["level"], panel]["voltage"], group)
            )
            np.testing.assert_allclose(
                parts["distance_V"], group["distance_V"], rtol=1e-12, atol=1e-21
            )
            groups.append(group | dict(feature_contributions=parts))
        joint = []
        for level in range(3):
            values = maps[level, panel]["voltage"]
            for strength in STRENGTHS:
                grid = {
                    (r["location"], r["timing"]): values[r["world_id"]]
                    for r in rows
                    if r["arm"] == "joint" and r["amplitude"] == strength
                }
                joint.append(dict(level=level, strength=strength) | factorial(grid))
        panels[panel] = dict(
            times_us=rule["observation_times_us"][panel],
            cell_ids=CELL_IDS,
            score_V=archived["score_V"],
            task_groups=groups,
            limiting_group=archived["limiting_group"],
            joint_factorial=joint,
            joint_calibration_counts_by_level={
                mode: [
                    entry["views"][mode]["arms"]["joint"]["joint"]
                    for entry in report["reader_views"][panel]
                ]
                for mode in report["reader_views"][panel][0]["views"]
            },
        )
    return dict(maximum_geometry_replay_error=replay_error, panels=panels)


def paired_changes(rows, maps, sham_rows, sham_maps, sham_report):
    def identities(row):
        return row["arm"], row["amplitude"], row["location"], row["timing"]

    original_ids = {identities(r): r["world_id"] for r in sham_rows}
    result = {}
    for panel in assay.PANELS:
        levels = []
        for level in range(3):
            current = maps[level, panel]["voltage"]
            original = {
                r["world_id"]: sham_maps[level, panel]["voltage"][original_ids[identities(r)]]
                for r in rows
            }
            ref, _ = background.no_cue_reference(rows, current)
            old_ref, _ = background.no_cue_reference(rows, original)
            effects = []
            for r in rows:
                identity = r["world_id"]
                change = (current[identity] - ref) - (original[identity] - old_ref)
                effects.append(
                    dict(
                        case=r,
                        cue_relative_change_V=change.tolist(),
                        cue_relative_change_l2_V=float(np.linalg.norm(change)),
                    )
                )
            group = next(
                g
                for g in sham_report["geometry"]["panels"][panel]["task_groups"]
                if g["arm"] == "joint" and g["task"] == "location" and g["level"] == level
            )
            old_delta = closest_delta(rows, original, group)
            new_delta = closest_delta(rows, current, group)
            change = new_delta - old_delta
            linear = 2 * old_delta * change
            quadratic = change * change
            observed = float(new_delta @ new_delta - old_delta @ old_delta)
            reconstructed = float((linear + quadratic).sum())
            np.testing.assert_allclose(reconstructed, observed, rtol=1e-10, atol=1e-30)
            levels.append(
                dict(
                    level=level,
                    no_cue_change=distance_parts(ref - old_ref),
                    calibration_case_effect_changes=effects,
                    same_sham_pair=dict(
                        group=group,
                        sham=distance_parts(old_delta),
                        candidate=distance_parts(new_delta),
                        squared_distance_change_V2=observed,
                        by_cell_signed_squared_distance_change_V2=(linear + quadratic)
                        .reshape(3, 5)
                        .sum(axis=0)
                        .tolist(),
                        by_time_signed_squared_distance_change_V2=(linear + quadratic)
                        .reshape(3, 5)
                        .sum(axis=1)
                        .tolist(),
                        reconstruction_error_V2=abs(reconstructed - observed),
                        coordinates_reoptimized=False,
                        causal_effect_of_each_cell_not_identified=True,
                    ),
                )
            )
        result[panel] = levels
    return result


def capture(output):
    if (
        digest(SOURCE / "completion.json") != COMPLETION_SHA256
        or (SOURCE / "failure.json").exists()
    ):
        raise ValueError("Completed pilot binding differs")
    done = json.loads((SOURCE / "completion.json").read_text())
    result = json.loads((SOURCE / "result.json").read_text())
    registration = json.loads((SOURCE / "registration.json").read_text())
    if done["status"] != "completed" or result["status"] != "completed":
        raise ValueError("Pilot is not completed")
    assert digest(SOURCE / "result.json") == done["result_sha256"]
    assert digest(SOURCE / "registration.json") == result["registration_sha256"]
    assert registration["component_protocol"] == assay.protocol()
    assert digest(SOURCE / "component-protocol.json") == registration["component_protocol_sha256"]
    for name, expected in registration["sources_sha256"].items():
        assert digest(ROOT / name) == expected, name
    names = ["registration.json", "component-protocol.json", "completion.json", "result.json"]
    for backend in ("cpu", "gpu"):
        for condition in assay.CONDITIONS:
            prefix = f"evidence/{backend}/channel-compensation-{condition['id']}"
            names.extend(
                prefix + suffix
                for suffix in ("-design.json", "-calibration.json", "-calibration.npz")
            )
    inputs = {}
    for name in names:
        source, target = SOURCE / name, output / "inputs" / name
        actual = digest(source)
        if name not in ("registration.json", "completion.json", "result.json"):
            assert actual == done["evidence_sha256"][name], name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        assert digest(target) == actual
        inputs[name] = actual
    sources = {}
    for name in (
        "validation/assays/channel_compensation_diagnostic.py",
        "tests/unit/test_channel_compensation_diagnostic.py",
    ):
        target = output / "source" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
        sources[name] = digest(target)
    record = dict(
        utc=utc(),
        source=str(SOURCE),
        completion_sha256=COMPLETION_SHA256,
        files_sha256=inputs,
        diagnostic_sources_sha256=sources,
        unchanged_prior_sources=len(registration["sources_sha256"]),
        scope="Authenticated calibration subset; no full trajectory archive audit.",
        heldout_cases_loaded=0,
        new_simulations=0,
        new_reader_candidates=0,
        gpu_work=False,
        automatic_followup=False,
    )
    write_json(output / "inputs.json", record)
    return registration["component_protocol"]


def analyze(output, rule):
    backends, accessed = {}, {}
    for backend in ("cpu", "gpu"):
        print(
            json.dumps(dict(phase="saved_calibration_analysis", backend=backend, utc=utc())),
            flush=True,
        )
        records, maps, rows, diagnoses = {}, {}, {}, {}
        for c in assay.CONDITIONS:
            name = c["id"]
            prefix = output / "inputs" / "evidence" / backend / f"channel-compensation-{name}"
            records[name] = json.loads(
                prefix.with_name(prefix.name + "-calibration.json").read_text()
            )
            design = json.loads(prefix.with_name(prefix.name + "-design.json").read_text())
            configured = assay.condition_rule(rule, name)
            assert design["cases"] == assay.cases(configured)
            with np.load(
                prefix.with_name(prefix.name + "-calibration.npz"), allow_pickle=False
            ) as saved:
                rows[name], maps[name], keys = load_maps(saved, design["cases"])
            accessed[f"{backend}/{name}"] = keys
            diagnoses[name] = condition_diagnosis(rows[name], maps[name], records[name], configured)
        for name in ("channel_lower", "channel_higher"):
            diagnoses[name]["changes_from_sham"] = paired_changes(
                rows[name], maps[name], rows["sham"], maps["sham"], records["sham"]
            )
        backends[backend] = diagnoses
    difference = compare_replay(backends["cpu"], backends["gpu"])
    return dict(
        status="completed_calibration_diagnosis",
        backends=backends,
        cpu_gpu_maximum_numeric_difference=difference,
        loaded_keys=accessed,
        new_simulations=0,
        heldout_cases_evaluated=0,
        automatic_followup=False,
        limitations=[
            "Exploratory decomposition of known calibration responses, not fresh confirmation.",
            "Joint location/order minima can be the same pair, not independent findings.",
            "Effect cosine and feature contributions are not causal channel derivatives.",
            "Uniform channel perturbations do not identify individual-cell channel sensitivities.",
            "Fitted-curve interior points are interpolations, not simulated new strengths.",
            "No recovery, continuum bound, empirical noise tolerance or new BETSE parity claim.",
            "Host analysis of saved CPU/L4 outputs; no new GPU utilization result.",
        ],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = output_path(args.output.resolve())
    output.mkdir(parents=True)
    began = time.monotonic()
    try:
        rule = capture(output)
        result = analyze(output, rule)
        result["elapsed_seconds"] = time.monotonic() - began
        write_json(output / "result.json", result)
        write_json(
            output / "completion.json",
            dict(
                status=result["status"],
                utc=utc(),
                result_sha256=digest(output / "result.json"),
                inputs_sha256=digest(output / "inputs.json"),
                automatic_followup=False,
            ),
        )
        print(
            json.dumps(dict(status=result["status"], elapsed_seconds=result["elapsed_seconds"])),
            flush=True,
        )
    except BaseException as exc:
        write_json(
            output / "failure.json",
            dict(
                status="failed",
                utc=utc(),
                error=repr(exc),
                traceback=traceback.format_exc(),
                elapsed_seconds=time.monotonic() - began,
            ),
        )
        raise


if __name__ == "__main__":
    main()
