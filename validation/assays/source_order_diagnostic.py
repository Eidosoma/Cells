"""Diagnose joint location/order ambiguity using authenticated saved evidence.

Known labels, strengths and counterparts enter post-hoc probes only. Reuse the
saved readers, voltage law and archive checks; run no integration or new reader.
"""

import argparse
import json
import shutil
import sys
import time
import traceback
from pathlib import Path

import numpy as np

from cells.assembly.cli import output_path, utc
from cells.assembly.io import write_json
from validation.assays import baseline_transfer_diagnostic as background
from validation.assays import cue_separation_diagnostic as saved_history
from validation.assays import source_order as assay
from validation.assays import template_diagnostic as geometry
from validation.assays import template_readout as reader
from validation.assays import unstimulated_diagnostic as history
from validation.assays.two_task_diagnostic import REPLAY_ATOL, REPLAY_RTOL, compare_replay
from validation.betse.spatial_active.refinement import completed_prior, digest

ROOT = Path(__file__).resolve().parents[2]
BINDING = dict(
    root="/mnt/workspaces/Cells/two-task-source-order-20261013-01",
    registration_sha256="759633af71bb9f9d797501f1ae5f44db268a5a2d456709579294ffbb53d688ec",
    completion_sha256="8d1c86534d8177f564cae552935314b439f7669420f0bcef687847a97a9e0211",
    require_completed_cpu_and_gpu=True,
)
TASKS = ("location", "timing")


def competing_curves(rows, features, saved_arm, *, margin):
    """Separate a one-label competitor from a competitor reversing both labels.

    Two oracle probes supply the true other label or the true strength. They
    describe information withheld from the original reader, not new accuracy.
    """
    tasks, training, testing = reader.split(rows, "joint")
    if tasks != saved_arm["calibration"]["task_order"]:
        raise ValueError("Saved calibration task order differs")
    fit = reader.TemplateReader(**saved_arm["calibration"]["template_reader"])
    if fit.minimum_margin != margin:
        raise ValueError("Saved margin differs")
    levels = np.unique([r["amplitude"] for r in training])
    if fit.vertices.shape[1] != len(levels):
        raise ValueError("Saved calibration strength grid differs")
    points = np.stack([features[r["world_id"]] for r in testing])
    decoded = fit.read(points)
    details = []
    for index, row in enumerate(testing):
        labels = np.array([row[t] for t in tasks])
        own = int(np.flatnonzero(np.all(fit.labels == labels, axis=1))[0])
        segment, coordinate = geometry.interval(levels, row["amplitude"])
        fixed_points = fit.vertices[:, segment] + coordinate * (
            fit.vertices[:, segment + 1] - fit.vertices[:, segment]
        )
        fixed_distances = np.linalg.norm(fixed_points - points[index], axis=1)
        distances = decoded["curve_distances"][index]
        for column, task in enumerate(tasks):
            old = saved_arm["tasks"][task]["predictions"][index]
            if (old["world_id"], old["target"]) != (row["world_id"], row[task]):
                raise ValueError("Saved competing-case identity differs")
            score = float(decoded["score"][index, column])
            np.testing.assert_allclose(score, old["score"], atol=REPLAY_ATOL, rtol=REPLAY_RTOL)
            if (
                bool(decoded["resolved"][index, column]),
                int(decoded["prediction"][index, column]),
            ) != (old["resolved"], old["prediction"]):
                raise ValueError("Saved competing-case decision differs")
            correct = np.flatnonzero(fit.labels[:, column] == labels[column])
            wrong = np.flatnonzero(fit.labels[:, column] != labels[column])
            best_correct = int(correct[np.argmin(distances[correct])])
            best_wrong = int(wrong[np.argmin(distances[wrong])])
            single = labels.copy()
            single[column] = 1 - single[column]
            one_flip = int(np.flatnonzero(np.all(fit.labels == single, axis=1))[0])
            other_labels = fit.labels[best_wrong]
            counterpart = next(
                r
                for r in testing
                if r["preparation"] == row["preparation"]
                and all(r[t] == other_labels[i] for i, t in enumerate(tasks))
            )
            closest_segment = int(decoded["closest_segments"][index, best_wrong])
            tangent = (
                fit.vertices[best_wrong, closest_segment + 1]
                - fit.vertices[best_wrong, closest_segment]
            ) / (levels[closest_segment + 1] - levels[closest_segment])
            paired = np.asarray(features[counterpart["world_id"]]) - points[index]
            conditional = float((distances[one_flip] - distances[own]) / 2)
            known_strength = float(
                (fixed_distances[wrong].min() - fixed_distances[correct].min()) / 2
            )
            details.append(
                dict(
                    world_id=row["world_id"],
                    task=task,
                    target=row[task],
                    strength=row["amplitude"],
                    original_correct_signed_score_V=float((2 * row[task] - 1) * score),
                    original_resolved=old["resolved"],
                    own_labels=labels.tolist(),
                    nearest_correct_labels=fit.labels[best_correct].tolist(),
                    nearest_wrong_labels=other_labels.tolist(),
                    nearest_wrong_flips_both=bool(np.all(other_labels != labels)),
                    own_curve=geometry.curve_projection(
                        decoded, levels, index, own, row["amplitude"]
                    ),
                    single_flip_curve=geometry.curve_projection(
                        decoded, levels, index, one_flip, row["amplitude"]
                    ),
                    nearest_wrong_curve=geometry.curve_projection(
                        decoded, levels, index, best_wrong, row["amplitude"]
                    ),
                    same_strength_competing_world_id=counterpart["world_id"],
                    same_strength_competing_geometry=geometry.decompose(paired, tangent),
                    true_other_label_oracle_signed_score_V=conditional,
                    true_other_label_oracle_resolved=conditional > margin,
                    true_strength_oracle_signed_score_V=known_strength,
                    true_strength_oracle_resolved=known_strength > margin,
                    diagnostic_uses_true_labels_strength_and_counterpart=True,
                )
            )
    return dict(
        details=details,
        diagnostic_oracles_are_not_new_readers=True,
        per_task={
            task: dict(
                original_correct_and_resolved=sum(
                    r["original_correct_signed_score_V"] > margin
                    for r in details
                    if r["task"] == task
                ),
                both_label_competitor_cases=sum(
                    r["nearest_wrong_flips_both"] for r in details if r["task"] == task
                ),
                true_other_label_oracle_resolved=sum(
                    r["true_other_label_oracle_resolved"] for r in details if r["task"] == task
                ),
                true_strength_oracle_resolved=sum(
                    r["true_strength_oracle_resolved"] for r in details if r["task"] == task
                ),
            )
            for task in tasks
        },
    )


def joint_geometry(rows, features):
    """Four-corner contrasts at each fixed strength; no calibration or fitting.

    The 01-to-10 contrast equals the mean location contrast minus the mean
    order contrast. This identity does not assume linear tissue physics.
    """
    joint = [r for r in rows if r["arm"] == "joint"]
    results = []
    for preparation in dict.fromkeys(r["preparation"] for r in joint):
        selected = [r for r in joint if r["preparation"] == preparation]
        by_label = {(r["location"], r["timing"]): r for r in selected}
        if len(selected) != 4 or set(by_label) != {(0, 0), (0, 1), (1, 0), (1, 1)}:
            raise ValueError("Each joint strength needs four distinct label combinations")
        if len({(r["amplitude"], r["split"]) for r in selected}) != 1:
            raise ValueError("Joint label combinations must share strength and split")
        x = np.stack(
            [features[by_label[label]["world_id"]] for label in ((0, 0), (0, 1), (1, 0), (1, 1))]
        )
        if x.ndim != 2 or not x.shape[1] or not np.isfinite(x).all():
            raise ValueError("Finite joint feature vectors required")
        interaction = (x[3] - x[2]) - (x[1] - x[0])
        location = (x[2] - x[0]) + interaction / 2
        order = (x[1] - x[0]) + interaction / 2
        crossed, aligned = x[2] - x[1], x[3] - x[0]
        np.testing.assert_allclose(location - order, crossed, atol=REPLAY_ATOL, rtol=REPLAY_RTOL)
        np.testing.assert_allclose(location + order, aligned, atol=REPLAY_ATOL, rtol=REPLAY_RTOL)
        lengths = [float(np.linalg.norm(v)) for v in (location, order)]
        denominator = lengths[0] * lengths[1]
        cosine = float(np.clip(location @ order / denominator, -1, 1)) if denominator else None
        singular = np.linalg.svd(np.stack((location, order), axis=1), compute_uv=False)
        singular = np.pad(singular, (0, 2 - len(singular)))
        results.append(
            dict(
                preparation=preparation,
                split=selected[0]["split"],
                strength=selected[0]["amplitude"],
                world_ids={f"{a}{b}": r["world_id"] for (a, b), r in by_label.items()},
                mean_location_contrast_V=location.tolist(),
                mean_order_contrast_V=order.tolist(),
                mean_location_contrast_l2_V=lengths[0],
                mean_order_contrast_l2_V=lengths[1],
                main_contrast_cosine=cosine,
                interaction_V=interaction.tolist(),
                interaction_l2_V=float(np.linalg.norm(interaction)),
                crossed_label_01_to_10_l2_V=float(np.linalg.norm(crossed)),
                aligned_label_00_to_11_l2_V=float(np.linalg.norm(aligned)),
                singular_values_V=singular.tolist(),
                smaller_to_larger_singular_ratio=float(singular[-1] / singular[0])
                if singular[0]
                else None,
                contrasts_are_descriptive_not_a_causal_interaction_test=True,
            )
        )
    return results


def case_summary(rows, levels, attribution, *, margin):
    cases = []
    for row in rows:
        if row["arm"] != "joint" or row["split"] != "heldout":
            continue
        tasks = {}
        for task in TASKS:
            details = [
                next(
                    r
                    for r in level["details"]
                    if r["world_id"] == row["world_id"] and r["task"] == task
                )
                for level in levels
            ]
            scores = [r["original_correct_signed_score_V"] for r in details]
            changed = next(
                r
                for r in attribution[-1]["details"]
                if r["world_id"] == row["world_id"] and r["task"] == task
            )
            tasks[task] = dict(
                signed_scores_V=scores,
                resolved_by_level=[s > margin for s in scores],
                finest_pair_resolution_changed=changed["resolution_changed"],
                finest_competitors=details[-1],
            )
        cases.append(
            row
            | dict(
                tasks=tasks,
                both_resolved_at_primary=all(t["resolved_by_level"][-1] for t in tasks.values()),
                both_resolved_at_all_steps=all(all(t["resolved_by_level"]) for t in tasks.values()),
            )
        )
    return dict(
        cases=cases,
        unresolved_joint_world_ids=[
            r["world_id"] for r in cases if not r["both_resolved_at_primary"]
        ],
        finest_pair_borderline_world_ids=[
            r["world_id"]
            for r in cases
            if any(t["finest_pair_resolution_changed"] for t in r["tasks"].values())
        ],
        joint_correct_and_resolved_at_all_steps=sum(r["both_resolved_at_all_steps"] for r in cases),
        finite_steps_are_not_a_continuum_bound=True,
    )


def analyze(root, output):
    print(json.dumps(dict(phase="authentication", utc=utc())), flush=True)
    binding = BINDING | dict(root=str(root))
    authentication = completed_prior(binding, current_root=ROOT)
    if authentication["completion_sha256"] != binding["completion_sha256"]:
        raise ValueError("Completed source binding differs")
    registration = json.loads((root / "registration.json").read_text())
    for name, expected in registration["sources_sha256"].items():
        if digest(ROOT / name) != expected:
            raise ValueError("Frozen source changed: " + name)
    authentication["all_prior_sources_unchanged"] = len(registration["sources_sha256"])
    rule = registration["component_protocol"]
    if rule != assay.protocol():
        raise ValueError("Source protocol differs")
    rows, arrays, backends = assay.cases(), {}, {}
    joint = [r for r in rows if r["arm"] == "joint"]
    margin = rule["reader"]["voltage_margin_V"]
    for backend in ("cpu", "gpu"):
        print(json.dumps(dict(backend=backend, phase="reader_replay", utc=utc())), flush=True)
        directory = root / "evidence" / backend
        assert json.loads((directory / "source-order-design.json").read_text())["cases"] == rows
        expected = json.loads((directory / "source-order-readouts.json").read_text())["panels"]
        with np.load(directory / "source-order-readouts.npz", allow_pickle=False) as saved:
            maps = {
                (level, panel): {
                    mode: {
                        r["world_id"]: saved[f"{level}__{panel}__{mode}__{r['world_id']}"]
                        for r in rows
                    }
                    for mode in history.MODES
                }
                for level in range(3)
                for panel in rule["observation_panels"]
            }
        reproduced = assay.reader_reports(rows, maps, rule)
        replay_error = compare_replay(reproduced, expected)
        references = assay.reference_reports(rows, maps, reproduced, rule)
        reference_error = compare_replay(
            references, json.loads((directory / "source-order-baseline-transfer.json").read_text())
        )
        primary = expected["long256"]["resolution_matched"]
        features = [maps[level, "long256"]["voltage"] for level in range(3)]
        probes = [
            dict(
                level=level,
                dt_s=rule["dt_s"][level],
                arms={
                    arm: {
                        task: history.task_geometry(
                            rows, features[level], arm, task, report, margin=margin
                        )
                        for task in reader.split(rows, arm)[0]
                    }
                    for arm, report in primary[level]["outcomes"]["voltage"]["arms"].items()
                },
                competitors=competing_curves(
                    rows,
                    features[level],
                    primary[level]["outcomes"]["voltage"]["arms"]["joint"],
                    margin=margin,
                ),
                joint_geometry=joint_geometry(rows, features[level]),
            )
            for level in range(3)
        ]
        attribution, centered_attribution, drift = [], [], []
        refs = [background.no_cue_reference(rows, f)[0] for f in features]
        centered = [
            {i: f - ref for i, f in values.items()}
            for values, ref in zip(features, refs, strict=True)
        ]
        centered_reports = [
            next(
                r["outcomes"]
                for r in references["transfers"]
                if r["source_level"] == r["target_level"] == level
            )
            for level in range(3)
        ]
        for level in (0, 1):
            metadata = dict(old_level=level, new_level=level + 1)
            attribution.append(
                saved_history.resolution_attribution(
                    rows,
                    features[level],
                    features[level + 1],
                    primary[level]["outcomes"]["voltage"]["arms"]["joint"],
                    primary[level + 1]["outcomes"]["voltage"]["arms"]["joint"],
                    margin=margin,
                )
                | metadata
            )
            centered_attribution.append(
                saved_history.resolution_attribution(
                    rows,
                    centered[level],
                    centered[level + 1],
                    centered_reports[level]["arms"]["joint"],
                    centered_reports[level + 1]["arms"]["joint"],
                    margin=margin,
                )
                | metadata
            )
            drift.append(
                background.drift(
                    rows, features[level], features[level + 1], refs[level], refs[level + 1]
                )
                | metadata
            )
        reconstructions, pairs, diagonals = [], [], []
        for level, dt in enumerate(rule["dt_s"]):
            print(
                json.dumps(dict(backend=backend, level=level, phase="histories", utc=utc())),
                flush=True,
            )
            histories = {}
            for row in joint:
                identity = row["world_id"]
                record = json.loads(
                    (directory / (assay.world_name(level, identity) + ".json")).read_text()
                )
                assert record["case"] == row
                times, cell, checks = saved_history.window_history(directory, record)
                differences = []
                for panel in rule["observation_panels"]:
                    indices = np.rint(assay.times(rule, panel) / dt).astype(int)
                    values = dict(
                        all_cell_voltage=cell[indices].reshape(-1),
                        voltage=cell[indices][:, np.array(rule["readout"]["cell_ids"]) - 1].reshape(
                            -1
                        ),
                    )
                    values["final_voltage"] = values["voltage"][-len(rule["readout"]["cell_ids"]) :]
                    for mode, vector in values.items():
                        old = maps[level, panel][mode][identity]
                        np.testing.assert_allclose(vector, old, atol=REPLAY_ATOL, rtol=REPLAY_RTOL)
                        differences.append(float(np.max(abs(vector - old))))
                reconstructions.append(
                    checks
                    | dict(
                        level=level,
                        world_id=identity,
                        maximum_saved_reader_difference_V=max(differences),
                    )
                )
                histories[identity] = cell
                arrays[f"voltage__{backend}__{level}__{identity}"] = cell
            indices = np.rint(assay.times(rule, "long256") / dt).astype(int)
            pair_rule = rule | dict(cue=dict(source_cell_ids=rule["source_cell_ids"]))
            pairs.extend(
                p | dict(level=level, dt_s=dt)
                for p in history.paired_histories(joint, histories, times, indices, pair_rule)
            )
            for low in joint:
                if low["location"] != 0:
                    continue
                high = next(
                    r
                    for r in joint
                    if r["preparation"] == low["preparation"]
                    and r["location"] == 1
                    and r["timing"] == 1 - low["timing"]
                )
                delta = histories[high["world_id"]] - histories[low["world_id"]]
                diagonals.append(
                    dict(
                        level=level,
                        dt_s=dt,
                        split=low["split"],
                        strength=low["amplitude"],
                        world_ids=[low["world_id"], high["world_id"]],
                        crossed_labels=bool(low["timing"]),
                        regions={
                            name: history.pair_summary(
                                times, delta[:, np.array(ids) - 1], indices, margin=margin
                            )
                            for name, ids in dict(
                                source=rule["source_cell_ids"],
                                unstimulated=rule["readout"]["cell_ids"],
                            ).items()
                        },
                    )
                )
            arrays[f"times_s__{level}"] = times
        backends[backend] = dict(
            original_replay=dict(
                status="passed",
                panels=3,
                timesteps=3,
                reader_modes=7,
                exact_decisions_and_metrics=True,
                max_absolute_numeric_difference=replay_error,
                reference_transfer_max_absolute_numeric_difference=reference_error,
            ),
            geometry=probes,
            raw_resolution_attribution=attribution,
            referenced_resolution_attribution=centered_attribution,
            background_drift=drift,
            reconstruction=reconstructions,
            pairs=pairs,
            diagonal_histories=diagonals,
            primary_cases=case_summary(
                rows, [p["competitors"] for p in probes], attribution, margin=margin
            ),
        )
    differences = [
        dict(
            level=level,
            world_id=r["world_id"],
            maximum_voltage_difference_V=float(
                np.max(
                    abs(
                        arrays[f"voltage__cpu__{level}__{r['world_id']}"]
                        - arrays[f"voltage__gpu__{level}__{r['world_id']}"]
                    )
                )
            ),
        )
        for level in range(3)
        for r in joint
    ]
    np.savez_compressed(output / "voltage-histories.npz", **arrays)
    return dict(
        status="completed",
        kind="source_order_saved_trajectory_diagnosis@1",
        authentication=authentication,
        cases=rows,
        task_meanings=rule["task_meanings"],
        backends=backends,
        cpu_gpu_voltage_differences=differences,
        primary_margin_V=margin,
        primary_readout_times_s=assay.times(rule, "long256").tolist(),
        replay_tolerances=dict(atol=REPLAY_ATOL, rtol=REPLAY_RTOL),
        limitations=[
            "Post-hoc description of inspected deterministic cases; "
            "no new holdout or biological validation.",
            "Original readers, results, failures, thresholds and observation times remain fixed.",
            "True other labels, strengths, calibration interpolation and paired responses "
            "are oracle probes only.",
            "Four-corner contrasts are descriptive identities, "
            "not causal nonlinear-interaction evidence.",
            "Opposite-label pair distance above twice the margin is necessary, "
            "never sufficient for both tasks.",
            "History trends cover 0--256 us only; no time selection or extrapolation.",
            "No-cue references supply target-timestep information; "
            "two-path timestep attribution is not a continuum error bound.",
            "Complete joint histories are reconstructed; control arms use saved readout features.",
            "CPU and GPU saved data are read on CPU; no GPU workload or new simulation.",
        ],
        new_simulations=0,
        automatic_followup=False,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--source", type=Path, default=Path(BINDING["root"]))
    args = parser.parse_args(argv)
    output = output_path(args.output)
    output.mkdir()
    started = time.monotonic()
    try:
        sources = {}
        for name in (
            "validation/assays/source_order_diagnostic.py",
            "tests/unit/test_source_order_diagnostic.py",
        ):
            target = output / "source" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
            sources[name] = digest(target)
        write_json(
            output / "inputs.json",
            dict(
                started_utc=utc(),
                command=sys.argv,
                python=sys.version,
                numpy=np.__version__,
                source_binding=BINDING | dict(root=str(args.source.resolve())),
                diagnostic_sources_sha256=sources,
                scope="Saved-data source-order diagnosis; "
                "no simulation, new decoder or endpoint selection",
            ),
        )
        result = analyze(args.source.resolve(), output)
        write_json(
            output / "result.json",
            result | dict(finished_utc=utc(), elapsed_seconds=time.monotonic() - started),
        )
        write_json(
            output / "completion.json",
            dict(
                status="completed",
                inputs_sha256=digest(output / "inputs.json"),
                result_sha256=digest(output / "result.json"),
                evidence_sha256={"voltage-histories.npz": digest(output / "voltage-histories.npz")},
            ),
        )
    except BaseException as exc:
        write_json(
            output / "failure.json",
            dict(
                status="failed",
                error=str(exc),
                exception=type(exc).__name__,
                traceback=traceback.format_exc(),
                finished_utc=utc(),
            ),
        )
        raise
    print(json.dumps(dict(status="completed", output=str(output))), flush=True)


if __name__ == "__main__":
    main()
