"""Post-hoc diagnosis of saved two-task evidence; never run or refit the physics.

Balanced calibration and input marginalization answer different questions from
the original assay. Their scores are diagnostic, not fresh held-out validation.
"""

import argparse
import json
import shutil
import sys
import traceback
from pathlib import Path

import numpy as np

from cells.assays.readout import CentroidReader, score_predictions
from cells.assembly.cli import output_path, utc
from cells.assembly.io import write_json
from validation.assays import two_task as assay
from validation.betse.spatial_active.refinement import completed_prior, digest

BINDING = dict(
    root="/mnt/workspaces/Cells/two-task-readout-20261012-01",
    registration_sha256="4c48d42ccc8340d7231e8329a3689e3f0ee5dd095699c6d5c549f53f0e004a46",
    completion_sha256="a05e141acdc28e27ffb97be1d8a0f9ad5d80adf874e443dbdbe13917ee656d79",
    require_completed_cpu_and_gpu=True,
)
MODES = ("voltage", "final_voltage", "input_at_readout", "input_history")
ARMS = ("joint", "disconnected", "no_cue")
TASKS = ("location", "timing")
REPLAY_ATOL = 1e-15
REPLAY_RTOL = 1e-12


def score_task(partitions, features, task, margin):
    """Retain every calibration and evaluation ID, score and abstention."""
    predictions, calibration = [], []
    for name, training, testing in partitions:
        reader = CentroidReader.fit(
            np.stack([features[r["world_id"]] for r in training]),
            [r[task] for r in training],
            minimum_margin=margin,
        )
        result = reader.read(np.stack([features[r["world_id"]] for r in testing]))
        calibration.append(
            dict(
                fold=name,
                calibration_world_ids=[r["world_id"] for r in training],
                heldout_world_ids=[r["world_id"] for r in testing],
                reader=reader.to_dict(),
            )
        )
        predictions.extend(
            dict(
                world_id=r["world_id"],
                fold=name,
                target=r[task],
                prediction=int(result["prediction"][i]),
                resolved=bool(result["resolved"][i]),
                score=float(result["score"][i]),
            )
            for i, r in enumerate(testing)
        )
    return dict(
        metrics=score_predictions(
            [r["target"] for r in predictions],
            [r["prediction"] for r in predictions],
            [r["resolved"] for r in predictions],
        ),
        predictions=predictions,
        calibration=calibration,
    )


def balanced(rows, features, margin):
    """Use all four calibration combinations, keeping the strength split only."""
    training = [r for r in rows if r["split"] == "calibration"]
    testing = [r for r in rows if r["split"] == "heldout"]
    return {
        task: score_task([("strength_holdout_only", training, testing)], features, task, margin)
        for task in TASKS
    }


def input_marginals(features, *, times, cells):
    """Sum availability deficits over the other axis; no labels or fitted scale.

    These have different supports (cells or times), not the matched 21-feature
    tissue reader. They diagnose the known input encoding only.
    """
    result = {task: {} for task in TASKS}
    for identity, value in features.items():
        value = np.asarray(value)
        if value.shape != (times * cells,) or not np.isfinite(value).all():
            raise ValueError("Expected finite time-major input features")
        deficit = 1 - value.reshape(times, cells)
        result["location"][identity] = deficit.sum(axis=0)
        result["timing"][identity] = deficit.sum(axis=1)
    return result


def input_geometry(rows, features):
    """Explain omitted-combination decisions by distances, not relabelled outputs."""
    records = []
    for fold, training, testing in assay.folds(rows, "joint"):
        train_x = np.stack([1 - features[r["world_id"]] for r in training])
        for task in TASKS:
            labels = np.asarray([r[task] for r in training])
            centers = np.stack([train_x[labels == label].mean(axis=0) for label in (0, 1)])
            for r in testing:
                value = 1 - features[r["world_id"]]
                distances = ((centers - value) ** 2).sum(axis=1)
                records.append(
                    dict(
                        fold=fold,
                        task=task,
                        world_id=r["world_id"],
                        target=r[task],
                        class_counts=[int(np.sum(labels == label)) for label in (0, 1)],
                        deficit_center_squared_norms=(centers**2).sum(axis=1).tolist(),
                        squared_distances=distances.tolist(),
                        nearest_class=int(np.argmin(distances)),
                        max_abs_training_dot=float(np.max(np.abs(train_x @ value))),
                    )
                )
    return records


def paired_effects(rows, features):
    """Descriptive contrasts of ALL cases; evaluation labels enter this analysis.

    This is not a fitted decoder, a significance test, or a sensor-noise model.
    """
    lookup = {(r["amplitude"], r["location"], r["timing"]): r["world_id"] for r in rows}
    amplitudes = sorted({r["amplitude"] for r in rows})

    def contrast(a, b):
        value = features[lookup[b]] - features[lookup[a]]
        return dict(
            world_ids=[lookup[a], lookup[b]],
            l2_V=float(np.linalg.norm(value)),
            max_abs_V=float(np.max(np.abs(value))),
        )

    timing = [
        dict(amplitude=a, location=location, **contrast((a, location, 0), (a, location, 1)))
        for a in amplitudes
        for location in (0, 1)
    ]
    location = [
        dict(amplitude=a, timing=t, **contrast((a, 0, t), (a, 1, t)))
        for a in amplitudes
        for t in (0, 1)
    ]
    amplitude = [
        dict(
            amplitudes=[amplitudes[0], amplitudes[-1]],
            location=location,
            timing=t,
            **contrast((amplitudes[0], location, t), (amplitudes[-1], location, t)),
        )
        for location in (0, 1)
        for t in (0, 1)
    ]
    directions = []
    for task in TASKS:
        centers = [
            np.mean(
                [
                    features[r["world_id"]]
                    for r in rows
                    if r["split"] == "calibration" and r[task] == label
                ],
                axis=0,
            )
            for label in (0, 1)
        ]
        directions.append(centers[1] - centers[0])
    denominator = float(np.linalg.norm(directions[0]) * np.linalg.norm(directions[1]))
    return dict(
        timing_pairs=timing,
        location_pairs=location,
        amplitude_pairs=amplitude,
        calibration_task_contrast_cosine=(
            float(directions[0] @ directions[1] / denominator) if denominator else None
        ),
        feature_count=len(next(iter(features.values()))),
    )


def compare_replay(actual, expected):
    """Exact decisions/metrics, roundoff-bounded numeric scores and calibration."""
    if isinstance(expected, dict):
        if actual.keys() != expected.keys():
            raise ValueError("Saved readout fields differ")
        for key in ("metrics", "joint"):
            if key in expected and actual[key] != expected[key]:
                raise ValueError("Saved readout metrics differ")
        return max((compare_replay(actual[k], v) for k, v in expected.items()), default=0)
    if isinstance(expected, list):
        if len(actual) != len(expected):
            raise ValueError("Saved readout lengths differ")
        return max((compare_replay(a, b) for a, b in zip(actual, expected, strict=True)), default=0)
    if isinstance(expected, float):
        np.testing.assert_allclose(actual, expected, atol=REPLAY_ATOL, rtol=REPLAY_RTOL)
        return abs(actual - expected)
    if actual != expected:
        raise ValueError("Saved readout decision or metadata differs")
    return 0


def analyze(root):
    binding = BINDING | dict(root=str(root))
    authentication = completed_prior(binding, current_root=assay.ROOT)
    if authentication["completion_sha256"] != binding["completion_sha256"]:
        raise ValueError("Completed assay binding differs")
    registration = json.loads((root / "registration.json").read_text())
    for name, expected in registration["sources_sha256"].items():
        if digest(assay.ROOT / name) != expected:
            raise ValueError("Frozen assay source changed: " + name)
    authentication["all_prior_sources_unchanged"] = len(registration["sources_sha256"])
    rule = registration["component_protocol"]
    backend_reports = {}
    for backend in ("cpu", "gpu"):
        directory = root / "evidence" / backend
        rows = json.loads((directory / "assay-design.json").read_text())["cases"]
        if rows != assay.cases(rule):
            raise ValueError("Saved input panel differs from the registered protocol")
        expected = json.loads((directory / "assay-readouts.json").read_text())
        with np.load(directory / "assay-readouts.npz", allow_pickle=False) as data:
            modes = {
                name: {r["world_id"]: data[f"{name}__{r['world_id']}"] for r in rows}
                for name in MODES
            }
        margins = {
            name: rule["reader"]["input_margin" if name.startswith("input") else "voltage_margin_V"]
            for name in MODES
        }
        reproduced = {
            name: assay.evaluate(rows, features, margin=margins[name])
            for name, features in modes.items()
        }
        reproduced["voltage_1uV_margin"] = assay.evaluate(
            rows, modes["voltage"], margin=rule["reader"]["coarse_voltage_margin_V"]
        )
        replay_error = compare_replay(reproduced, expected["outcomes"])
        probes = {
            name: {
                arm: balanced([r for r in rows if r["arm"] == arm], values, margins[name])
                for arm in ARMS
            }
            for name, values in modes.items()
        }
        marginals = input_marginals(
            modes["input_history"],
            times=len(rule["input_history_steps"]),
            cells=len(rule["readout_cell_ids"]),
        )
        marginal_scores, geometry, effects = {}, {}, {}
        for arm in ARMS:
            selected = [r for r in rows if r["arm"] == arm]
            marginal_scores[arm] = {
                task: score_task(
                    assay.folds(selected, arm),
                    marginals[task],
                    task,
                    rule["reader"]["input_margin"],
                )
                for task in TASKS
            }
            geometry[arm] = input_geometry(selected, modes["input_history"])
            effects[arm] = paired_effects(selected, modes["voltage"])
        backend_reports[backend] = dict(
            original_replay=dict(
                status="passed",
                max_absolute_numeric_difference=replay_error,
                exact_decisions_and_metadata=True,
            ),
            original_metrics={
                mode: {
                    arm: {task: value["metrics"] for task, value in detail["tasks"].items()}
                    for arm, detail in report["arms"].items()
                }
                for mode, report in reproduced.items()
            },
            balanced_strength_holdout=probes,
            input_marginals_original_combination_holdout=marginal_scores,
            input_deficit_geometry=geometry,
            voltage_paired_effects=effects,
        )
    return dict(
        status="completed",
        kind="two_task_saved_evidence_diagnostic@1",
        scope="Post-hoc analysis of existing CPU/L4 evidence; no new simulation or validation.",
        authentication=authentication,
        backends=backend_reports,
        original_cpu_gpu_comparison=json.loads(
            (root / "evidence/gpu/assay-cpu-gpu.json").read_text()
        ),
        limitations=[
            "Original failed two-task outcome remains unchanged.",
            "Balanced calibration tests strengths, not an unseen location/timing combination.",
            "Input marginals use different feature supports and are not tissue readers.",
            "Contrasts include already-inspected held-out data; no fresh validation claim.",
            "Few-nanovolt timing effects need specific refinement and a justified noise budget.",
            "No biological, memory, causal consumer, polycomputing or throughput claim.",
        ],
        replay_tolerances=dict(
            atol=REPLAY_ATOL,
            rtol=REPLAY_RTOL,
            scope="Saved analysis replay only, not physics tolerances",
        ),
        automatic_followup=False,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--source", type=Path, default=Path(BINDING["root"]))
    args = parser.parse_args(argv)
    output = output_path(args.output)
    output.mkdir()
    try:
        sources = {}
        for name in (
            "validation/assays/two_task_diagnostic.py",
            "tests/unit/test_two_task_diagnostic.py",
        ):
            target = output / "source" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(assay.ROOT / name, target)
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
                development_data_already_inspected=True,
                scope="Diagnostic analysis; no prospective registration or new simulation.",
            ),
        )
        result = analyze(args.source.resolve())
        write_json(output / "result.json", result | dict(finished_utc=utc()))
        write_json(
            output / "completion.json",
            dict(
                status="completed",
                kind="two_task_saved_evidence_diagnostic@1",
                inputs_sha256=digest(output / "inputs.json"),
                result_sha256=digest(output / "result.json"),
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
    print(json.dumps(dict(status="completed", output=str(output))))


if __name__ == "__main__":
    main()
