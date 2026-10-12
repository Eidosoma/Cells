"""Post-hoc geometry of weak timing margins in authenticated saved evidence.

Known strengths and paired evaluation labels are used only as diagnostic probes.
They do not become reader inputs, calibration samples or new validation scores.
"""

import argparse
import json
import shutil
import sys
import traceback
from pathlib import Path

import numpy as np

from cells.assembly.cli import output_path, utc
from cells.assembly.io import write_json
from validation.assays import template_readout as assay
from validation.assays.two_task_diagnostic import REPLAY_ATOL, REPLAY_RTOL, compare_replay
from validation.betse.spatial_active.refinement import completed_prior, digest

BINDING = dict(
    root="/mnt/workspaces/Cells/two-task-templates-20261012-01",
    registration_sha256="d3f0b70a60334f3748dfcdc2cb61f20576e706137e1ef148446f817706c96836",
    completion_sha256="42d1de03c8f2f648a81e7afb85ad27489bf3ff6669ce9481abc03688f0ce3019",
    require_completed_cpu_and_gpu=True,
)
MODES = ("voltage", "final_voltage", "input_at_readout", "input_history")
ROOT = Path(__file__).resolve().parents[2]


def decompose(delta, tangent):
    """Resolve a finite observed contrast along one fixed calibration tangent."""
    delta, tangent = np.asarray(delta, dtype=float), np.asarray(tangent, dtype=float)
    if (
        delta.ndim != 1
        or not delta.size
        or delta.shape != tangent.shape
        or not np.isfinite(delta).all()
        or not np.isfinite(tangent).all()
    ):
        raise ValueError("Expected two finite vectors with the same support")
    denominator = float(tangent @ tangent)
    coefficient = float(delta @ tangent / denominator) if denominator else 0.0
    parallel = coefficient * tangent
    perpendicular = delta - parallel
    size = float(np.linalg.norm(delta))
    fraction = float(np.linalg.norm(parallel) ** 2 / size**2) if size and denominator else None
    return dict(
        contrast=delta.tolist(),
        calibration_tangent=tangent.tolist(),
        parallel=parallel.tolist(),
        perpendicular=perpendicular.tolist(),
        contrast_l2=float(size),
        parallel_l2=float(np.linalg.norm(parallel)),
        perpendicular_l2=float(np.linalg.norm(perpendicular)),
        parallel_squared_norm_fraction=min(1.0, max(0.0, fraction))
        if fraction is not None
        else None,
        equivalent_strength_change=coefficient,
        tangent_nonzero=bool(denominator),
    )


def interval(levels, strength):
    levels = np.asarray(levels, dtype=float)
    if (
        levels.ndim != 1
        or len(levels) < 2
        or not np.isfinite(levels).all()
        or np.any(np.diff(levels) <= 0)
        or not np.isfinite(strength)
        or not levels[0] <= strength <= levels[-1]
    ):
        raise ValueError("Probe strength must be inside an ordered calibration grid")
    index = int(np.clip(np.searchsorted(levels, strength, side="right") - 1, 0, len(levels) - 2))
    return index, float((strength - levels[index]) / (levels[index + 1] - levels[index]))


def curve_projection(decoded, levels, index, curve, strength):
    selected = int(decoded["closest_segments"][index, curve])
    position = float(decoded["segment_coordinates"][index, curve])
    inferred = float(levels[selected] + position * (levels[selected + 1] - levels[selected]))
    return dict(
        curve_index=curve,
        distance=float(decoded["curve_distances"][index, curve]),
        segment=selected,
        coordinate=position,
        inferred_strength=inferred,
        strength_shift=inferred - strength,
        at_segment_endpoint=position in (0.0, 1.0),
    )


def diagnose_arm(rows, features, arm, saved_arm, *, margin):
    """Geometry only: keep the fitted curves and all original scores frozen."""
    tasks, training, testing = assay.split(rows, arm)
    if "timing" not in tasks:
        return dict(has_timing_task=False, reason="Unused timing label in location-only arm")
    timing_index = tasks.index("timing")
    calibration = saved_arm["calibration"]
    if calibration["task_order"] != tasks:
        raise ValueError("Saved calibration task order differs")
    reader = assay.TemplateReader(**calibration["template_reader"])
    levels = np.unique([r["amplitude"] for r in training])
    if reader.vertices.shape[1] != len(levels):
        raise ValueError("Calibration strength grid differs from curve vertices")
    decoded = reader.read(np.stack([features[r["world_id"]] for r in testing]))
    rows_by_id = {r["world_id"]: r for r in testing}
    saved_scores = {r["world_id"]: r for r in saved_arm["tasks"]["timing"]["predictions"]}
    details = []
    for index, row in enumerate(testing):
        label = np.array([row[t] for t in tasks])
        opposite = label.copy()
        opposite[timing_index] = 1 - opposite[timing_index]
        own = int(np.flatnonzero(np.all(reader.labels == label, axis=1))[0])
        other = int(np.flatnonzero(np.all(reader.labels == opposite, axis=1))[0])
        paired = next(
            r
            for r in testing
            if r["preparation"] == row["preparation"]
            and all(r[t] == opposite[i] for i, t in enumerate(tasks))
        )
        strength = row["amplitude"]
        segment, coordinate = interval(levels, strength)
        step = float(levels[segment + 1] - levels[segment])
        point = np.asarray(features[row["world_id"]])
        own_start, own_end = reader.vertices[own, segment : segment + 2]
        other_start, other_end = reader.vertices[other, segment : segment + 2]
        own_model = own_start + coordinate * (own_end - own_start)
        other_model = other_start + coordinate * (other_end - other_start)
        residual = point - own_model
        residual_l2 = float(np.linalg.norm(residual))
        # The alternative timing curve is the relevant nuisance direction for
        # mistaking one timing for another by adjusting its inferred strength.
        observed_contrast = np.asarray(features[paired["world_id"]]) - point
        geometry = decompose(observed_contrast, (other_end - other_start) / step)
        actual_score = float(decoded["score"][index, timing_index])
        np.testing.assert_allclose(
            actual_score, saved_scores[row["world_id"]]["score"], atol=REPLAY_ATOL, rtol=REPLAY_RTOL
        )
        modeled_score = float(reader.read([own_model])["score"][0, timing_index])
        # Fixed-curve half-gap is 1-Lipschitz. This is an algebra check, not a
        # physical/numerical uncertainty estimate or a new sensing threshold.
        roundoff = 64 * np.finfo(float).eps * max(float(np.linalg.norm(point)), 1e-30)
        if abs(actual_score - modeled_score) > residual_l2 + roundoff:
            raise ValueError("Fixed-curve score violated its perturbation bound")
        all_distances = decoded["curve_distances"][index]
        other_indices = np.flatnonzero(reader.labels[:, timing_index] == opposite[timing_index])
        best_other = int(other_indices[np.argmin(all_distances[other_indices])])

        sign = 2 * row["timing"] - 1
        details.append(
            dict(
                world_id=row["world_id"],
                paired_world_id=paired["world_id"],
                location=row["location"] if "location" in tasks else None,
                timing=row["timing"],
                strength=strength,
                calibration_world_ids=calibration["world_ids"],
                known_strength_segment=segment,
                known_strength_coordinate=coordinate,
                geometry=geometry,
                same_strength_calibration_residual=residual.tolist(),
                same_strength_calibration_residual_l2=residual_l2,
                matched_timing_model_contrast=(other_model - own_model).tolist(),
                matched_timing_model_contrast_l2=float(np.linalg.norm(other_model - own_model)),
                own_curve=curve_projection(decoded, levels, index, own, strength),
                opposite_timing_same_other_labels=curve_projection(
                    decoded, levels, index, other, strength
                ),
                nearest_wrong_timing_curve=curve_projection(
                    decoded, levels, index, best_other, strength
                ),
                nearest_wrong_curve_has_matched_other_labels=best_other == other,
                original_score=actual_score,
                original_correct_signed_margin=sign * actual_score,
                original_resolved=bool(decoded["resolved"][index, timing_index]),
                on_true_calibration_curve_score=modeled_score,
                on_true_curve_correct_signed_margin=sign * modeled_score,
                on_true_curve_correct_and_above_margin=bool(sign * modeled_score > margin),
                score_change_when_moved_to_true_curve=modeled_score - actual_score,
                uses_known_strength_and_true_labels_for_diagnosis_only=True,
            )
        )
    if len(rows_by_id) != len(details):
        raise ValueError("Duplicate diagnostic identities")

    def extent(values):
        values = [v for v in values if v is not None]
        return [min(values), max(values)] if values else None

    return dict(
        has_timing_task=True,
        cases=len(details),
        unique_timing_pairs=len(
            {tuple(sorted((r["world_id"], r["paired_world_id"]))) for r in details}
        ),
        margin=margin,
        original_correct_and_resolved=sum(
            r["original_correct_signed_margin"] > margin for r in details
        ),
        on_true_curve_correct_and_above_margin=sum(
            r["on_true_curve_correct_and_above_margin"] for r in details
        ),
        original_absolute_score_range=extent(abs(r["original_score"]) for r in details),
        on_true_curve_absolute_score_range=extent(
            abs(r["on_true_calibration_curve_score"]) for r in details
        ),
        observed_matched_contrast_l2_range=extent(r["geometry"]["contrast_l2"] for r in details),
        perpendicular_contrast_l2_range=extent(r["geometry"]["perpendicular_l2"] for r in details),
        parallel_squared_norm_fraction_range=extent(
            r["geometry"]["parallel_squared_norm_fraction"] for r in details
        ),
        same_strength_calibration_residual_l2_range=extent(
            r["same_strength_calibration_residual_l2"] for r in details
        ),
        own_curve_distance_range=extent(r["own_curve"]["distance"] for r in details),
        opposite_curve_distance_range=extent(
            r["opposite_timing_same_other_labels"]["distance"] for r in details
        ),
        opposite_curve_absolute_strength_shift_range=extent(
            abs(r["opposite_timing_same_other_labels"]["strength_shift"]) for r in details
        ),
        maximum_absolute_score_change_to_true_curve=max(
            abs(r["score_change_when_moved_to_true_curve"]) for r in details
        ),
        opposite_curve_endpoint_cases=sum(
            r["opposite_timing_same_other_labels"]["at_segment_endpoint"] for r in details
        ),
        nearest_wrong_curve_matches_other_labels=all(
            r["nearest_wrong_curve_has_matched_other_labels"] for r in details
        ),
        details=details,
    )


def replay(rows, modes, expected, rule):
    reproduced = {
        name: assay.evaluate(
            rows,
            values,
            margin=rule["reader"][
                "input_margin" if name.startswith("input") else "voltage_margin_V"
            ],
        )
        for name, values in modes.items()
    }
    reproduced["voltage_1uV_margin"] = assay.evaluate(
        rows, modes["voltage"], margin=rule["reader"]["coarse_voltage_margin_V"]
    )
    reproduced["balanced_centroid_voltage"] = assay.evaluate(
        rows, modes["voltage"], margin=rule["reader"]["voltage_margin_V"], centroid=True
    )
    shuffles = [
        assay.evaluate(
            [r for r in rows if r["arm"] == "joint"],
            modes["voltage"],
            margin=rule["reader"]["voltage_margin_V"],
            shuffle_seed=seed,
        )
        for seed in rule["reader"]["shuffle_seeds"]
    ]
    return dict(
        status="passed",
        outcome_reports=len(reproduced),
        shuffled_reports=len(shuffles),
        max_absolute_numeric_difference=max(
            compare_replay(reproduced, expected["outcomes"]),
            compare_replay(shuffles, expected["shuffles"]),
        ),
        exact_decisions_and_metrics=True,
    )


def analyze(root):
    binding = BINDING | dict(root=str(root))
    authentication = completed_prior(binding, current_root=ROOT)
    if authentication["completion_sha256"] != binding["completion_sha256"]:
        raise ValueError("Completed template assay binding differs")
    registration = json.loads((root / "registration.json").read_text())
    for name, expected in registration["sources_sha256"].items():
        if digest(ROOT / name) != expected:
            raise ValueError("Frozen template source changed: " + name)
    authentication["all_prior_sources_unchanged"] = len(registration["sources_sha256"])
    rule = registration["component_protocol"]
    backends = {}
    for backend in ("cpu", "gpu"):
        directory = root / "evidence" / backend
        rows = json.loads((directory / "templates-design.json").read_text())["cases"]
        if rows != assay.cases(rule):
            raise ValueError("Saved template cases differ from registration")
        expected = json.loads((directory / "templates-readouts.json").read_text())
        with np.load(directory / "templates-readouts.npz", allow_pickle=False) as data:
            modes = {
                name: {r["world_id"]: data[f"{name}__{r['world_id']}"] for r in rows}
                for name in MODES
            }
        replay_report = replay(rows, modes, expected, rule)
        probes = {}
        for name, features in modes.items():
            margin = rule["reader"][
                "input_margin" if name.startswith("input") else "voltage_margin_V"
            ]
            probes[name] = dict(
                feature_units="channel_availability" if name.startswith("input") else "V",
                feature_count=expected["outcomes"][name]["feature_count"],
                arms={
                    arm: diagnose_arm(rows, features, arm, saved_arm, margin=margin)
                    for arm, saved_arm in expected["outcomes"][name]["arms"].items()
                },
            )
        backends[backend] = dict(original_replay=replay_report, diagnostics=probes)
    return dict(
        status="completed",
        kind="two_task_template_geometry_diagnostic@1",
        scope=(
            "Post-hoc geometry of saved observations and frozen calibration; "
            "no simulation or new decoder evaluation."
        ),
        authentication=authentication,
        backends=backends,
        original_cpu_gpu_comparison=json.loads(
            (root / "evidence/gpu/templates-cpu-gpu.json").read_text()
        ),
        limitations=[
            "The original primary joint correct-and-resolved target remains unmet; "
            "its 2-nV margin is unchanged.",
            "Known-strength, known-label and paired-observation probes are diagnostics with "
            "additional information, not valid substitute reader results.",
            "The tangent decomposition describes the sampled feature geometry; "
            "it does not identify a molecular cause or a physical memory carrier.",
            "Moving a point to its true calibrated curve removes that sampled residual only. "
            "It does not prove both physical response curves linear or bound interpolation "
            "error between observed strengths.",
            "Small reported residuals include numerical effects. Algebraic precision is not "
            "biological sensing precision or a new convergence certificate.",
            "No new training, threshold tuning, biological replicates, causal-consumer, "
            "polycomputing or throughput claim.",
        ],
        replay_tolerances=dict(
            atol=REPLAY_ATOL,
            rtol=REPLAY_RTOL,
            scope="Saved analysis replay only; physical tolerances unchanged",
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
            "validation/assays/template_diagnostic.py",
            "tests/unit/test_template_diagnostic.py",
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
                scope=(
                    "Post-hoc analysis of already-inspected evidence; "
                    "no prospective registration or fresh evaluation."
                ),
            ),
        )
        result = analyze(args.source.resolve())
        write_json(output / "result.json", result | dict(finished_utc=utc()))
        write_json(
            output / "completion.json",
            dict(
                status="completed",
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
