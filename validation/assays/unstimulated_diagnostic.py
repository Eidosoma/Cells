"""Post-hoc signal histories and fixed-reader geometry outside source cells.

Only authenticated saved trajectories are read. Known input labels and strengths
are diagnostic probes; no physics, reader selection or new validation is run.
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
from cells.numerics import betse_spatial as passive
from cells.processes.electrochemistry import F
from validation.assays import template_diagnostic as geometry
from validation.assays import template_readout as reader
from validation.assays import unstimulated_readout as assay
from validation.assays.two_task_diagnostic import REPLAY_ATOL, REPLAY_RTOL, compare_replay
from validation.betse.spatial_active.refinement import completed_prior, digest

ROOT = Path(__file__).resolve().parents[2]
BINDING = dict(
    root="/mnt/workspaces/Cells/two-task-unstimulated-20261012-01",
    registration_sha256="7db8efc66e6f56d4d0b8beb8026e26fe0cc64e2b990a30ebabea76d493783d0a",
    completion_sha256="29f0b9ae8fb6ade45f4907a614d03d62fccc4a817575c440ef072377b35b3e61",
    require_completed_cpu_and_gpu=True,
)
MODES = ("voltage", "final_voltage", "all_cell_voltage", "input_at_readout", "input_history")
TASKS = ("location", "timing")


def extent(values):
    values = [v for v in values if v is not None]
    return [min(values), max(values)] if values else None


def voltage_history(concentrations, tissue):
    """The existing field law's voltage terms, without transport integration.

    Return patch voltage and area-weighted voltage for every physical cell slot.
    Do not use observed__vm_ave, whose legacy arithmetic patch mean differs from
    the qualified reader's area-weighted mean on unequal membrane areas.
    """
    p = passive.Layout(*(np.asarray(tissue[k]) for k in passive.Layout._fields))
    cells, _ = passive.ownership(p, xp=np)
    values = np.asarray(concentrations, dtype=float)
    if (
        values.ndim != 3
        or not len(values)
        or values.shape[1:] != (p.valence.size, p.cell_volume.size)
        or not np.isfinite(values).all()
        or np.any(values <= 0)
    ):
        raise ValueError("Expected positive finite time/species/cell concentrations")
    # Preserve the scalar observation's charge accumulation order per sample.
    rho = np.stack([(p.valence * F) @ sample for sample in values])
    rho += p.extra_cell_charge_density
    inside = rho * (p.cell_volume / (cells @ p.membrane_area)) / p.capacitance_density
    boundary = passive.boundary_field(p.boundary_values, xp=np)
    patch = inside[:, p.cell_owner] - boundary.ravel()[p.outside_owner]
    weighted = np.stack(
        [
            patch[:, p.cell_owner == i]
            @ (p.membrane_area[p.cell_owner == i] / p.membrane_area[p.cell_owner == i].sum())
            for i in range(p.cell_volume.size)
        ],
        axis=1,
    )
    if not np.isfinite(patch).all() or not np.isfinite(weighted).all():
        raise ValueError("Nonfinite reconstructed voltage")
    return patch, weighted


def pair_summary(times, delta, readout_indices, *, margin):
    """Timewise norms and a necessary pair-separation condition, not a decoder.

    For the existing fixed-curve score (1-Lipschitz), both opposite-label cases
    can exceed margin m only if their feature distance exceeds 2m. Satisfying
    that condition alone never establishes successful or robust reading.
    """
    times, delta, indices = map(np.asarray, (times, delta, readout_indices))
    if (
        times.ndim != 1
        or delta.ndim != 2
        or not delta.shape[1]
        or len(times) != len(delta)
        or not np.isfinite(times).all()
        or not np.isfinite(delta).all()
        or np.any(np.diff(times) <= 0)
        or indices.ndim != 1
        or len(indices) != 3
        or indices.dtype.kind not in "iu"
        or np.any(np.diff(indices) <= 0)
        or np.any((indices < 0) | (indices >= len(times)))
        or indices[-1] != len(times) - 1
        or not np.isfinite(margin)
        or margin <= 0
    ):
        raise ValueError("Invalid paired history or sampling")
    norm = np.linalg.norm(delta, axis=1)
    sampled = delta[indices]
    distance = float(np.linalg.norm(sampled))
    later = norm[indices[1] :]
    return dict(
        sampled_contrast_l2_V=distance,
        sampled_half_separation_V=distance / 2,
        necessary_separation_for_both_margin_decisions=bool(distance > 2 * margin),
        separation_condition_is_not_sufficient=True,
        per_readout_l2_V=norm[indices].tolist(),
        end_l2_V=float(norm[-1]),
        maximum_l2_V=float(norm.max()),
        first_maximum_time_s=float(times[int(np.argmax(norm))]),
        final_interval_norm_change_V=float(norm[-1] - norm[indices[1]]),
        final_interval_min_l2_V=float(later.min()),
        final_interval_max_l2_V=float(later.max()),
        final_interval_non_decreasing=bool(np.all(np.diff(later) >= 0)),
        end_to_middle_ratio=float(norm[-1] / norm[indices[1]]) if norm[indices[1]] else None,
        exactly_zero=bool(not np.any(delta)),
        final_cell_contrast_V=delta[-1].tolist(),
    )


def task_geometry(rows, features, arm, task, saved_arm, *, margin):
    """Probe one task using the saved fit and known matching counterparts."""
    tasks, training, testing = reader.split(rows, arm)
    if task not in tasks:
        return dict(task=task, unused_task=True)
    index = tasks.index(task)
    fitted = reader.TemplateReader(**saved_arm["calibration"]["template_reader"])
    levels = np.unique([r["amplitude"] for r in training])
    decoded = fitted.read(np.stack([features[r["world_id"]] for r in testing]))
    saved = saved_arm["tasks"][task]["predictions"]
    details = []
    for position, (row, old) in enumerate(zip(testing, saved, strict=True)):
        assert row["world_id"] == old["world_id"] and row[task] == old["target"]
        label = np.array([row[t] for t in tasks])
        opposite = label.copy()
        opposite[index] = 1 - opposite[index]
        own = int(np.flatnonzero(np.all(fitted.labels == label, axis=1))[0])
        other = int(np.flatnonzero(np.all(fitted.labels == opposite, axis=1))[0])
        paired = next(
            r
            for r in testing
            if r["preparation"] == row["preparation"]
            and all(r[t] == opposite[i] for i, t in enumerate(tasks))
        )
        segment, coordinate = geometry.interval(levels, row["amplitude"])
        begin, end = fitted.vertices[own, segment : segment + 2]
        own_model = begin + coordinate * (end - begin)
        other_begin, other_end = fitted.vertices[other, segment : segment + 2]
        tangent = (other_end - other_begin) / (levels[segment + 1] - levels[segment])
        point = np.asarray(features[row["world_id"]])
        residual = float(np.linalg.norm(point - own_model))
        contrast = np.asarray(features[paired["world_id"]]) - point
        shape = geometry.decompose(contrast, tangent)
        score = float(decoded["score"][position, index])
        np.testing.assert_allclose(score, old["score"], atol=REPLAY_ATOL, rtol=REPLAY_RTOL)
        modeled = float(fitted.read([own_model])["score"][0, index])
        roundoff = 64 * np.finfo(float).eps * max(float(np.linalg.norm(point)), 1e-30)
        if abs(score - modeled) > residual + roundoff:
            raise ValueError("Fixed-reader perturbation bound failed")
        details.append(
            dict(
                world_id=row["world_id"],
                paired_world_id=paired["world_id"],
                target=row[task],
                strength=row["amplitude"],
                original_score_V=score,
                original_resolved=bool(decoded["resolved"][position, index]),
                geometry=shape,
                same_strength_calibration_residual_l2_V=residual,
                on_true_curve_score_V=modeled,
                on_true_curve_correct_and_resolved=bool((2 * row[task] - 1) * modeled > margin),
                score_change_when_moved_to_true_curve_V=modeled - score,
                opposite_curve=geometry.curve_projection(
                    decoded, levels, position, other, row["amplitude"]
                ),
                diagnosis_uses_known_labels_and_strength=True,
            )
        )
    return dict(
        task=task,
        unused_task=False,
        cases=len(details),
        original_correct_and_resolved=sum(
            (2 * r["target"] - 1) * r["original_score_V"] > margin for r in details
        ),
        on_true_curve_correct_and_resolved=sum(
            r["on_true_curve_correct_and_resolved"] for r in details
        ),
        original_absolute_score_range_V=extent(abs(r["original_score_V"]) for r in details),
        paired_contrast_l2_range_V=extent(r["geometry"]["contrast_l2"] for r in details),
        perpendicular_contrast_l2_range_V=extent(
            r["geometry"]["perpendicular_l2"] for r in details
        ),
        strength_parallel_squared_fraction_range=extent(
            r["geometry"]["parallel_squared_norm_fraction"] for r in details
        ),
        calibration_residual_l2_range_V=extent(
            r["same_strength_calibration_residual_l2_V"] for r in details
        ),
        max_score_change_to_true_curve_V=max(
            abs(r["score_change_when_moved_to_true_curve_V"]) for r in details
        ),
        details=details,
    )


def paired_histories(rows, histories, times, indices, rule):
    regions = dict(source=rule["cue"]["source_cell_ids"], unstimulated=rule["readout"]["cell_ids"])
    pairs = []
    for task in TASKS:
        other = next(t for t in TASKS if t != task)
        for low in rows:
            if low[task] or (low["arm"] == task + "_only" and low[other]):
                continue
            high = next(
                r
                for r in rows
                if r[task] == 1 and all(r[k] == low[k] for k in ("arm", "preparation", other))
            )
            delta = histories[high["world_id"]] - histories[low["world_id"]]
            pairs.append(
                dict(
                    task=task,
                    arm=low["arm"],
                    split=low["split"],
                    strength=low["amplitude"],
                    other_task_value=low[other],
                    world_ids=[low["world_id"], high["world_id"]],
                    regions={
                        name: pair_summary(
                            times,
                            delta[:, np.array(ids) - 1],
                            indices,
                            margin=rule["reader"]["voltage_margin_V"],
                        )
                        for name, ids in regions.items()
                    },
                )
            )
    return pairs


def analyze(root, output):
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
    assert rule == assay.protocol()
    rows = assay.cases(rule)
    backends, arrays = {}, {}
    for backend in ("cpu", "gpu"):
        directory = root / "evidence" / backend
        assert json.loads((directory / "unstimulated-design.json").read_text())["cases"] == rows
        expected = json.loads((directory / "unstimulated-readouts.json").read_text())
        with np.load(directory / "unstimulated-readouts.npz", allow_pickle=False) as data:
            modes = {
                name: {r["world_id"]: data[f"{name}__{r['world_id']}"] for r in rows}
                for name in MODES
            }
        reproduced, shuffles = assay.reader_reports(rows, modes, rule)
        replay_error = max(
            compare_replay(reproduced, expected["outcomes"]),
            compare_replay(shuffles, expected["shuffles"]),
        )
        histories, reconstruction = {}, []
        for row in rows:
            identity = row["world_id"]
            name = f"unstimulated-world-{identity}"
            raw = json.loads((directory / (name + ".json")).read_text())
            assert raw["case"] == row
            with np.load(directory / (name + ".npz"), allow_pickle=False) as saved:
                steps = saved["state__step_count"]
                np.testing.assert_array_equal(steps, np.arange(1025))
                times = steps * rule["dt_s"]
                np.testing.assert_allclose(times, saved["state__elapsed_s"], atol=6e-17, rtol=0)
                indices = np.rint(
                    np.asarray(raw["input"]["experiment"]["observation_times"]) / rule["dt_s"]
                ).astype(int)
                patch, cell = voltage_history(
                    saved["state__cell_concentration"], raw["input"]["model"]["tissue"]
                )
                sampled = cell[indices].reshape(-1)
                np.testing.assert_allclose(
                    patch[indices], saved["observed__vm"], atol=REPLAY_ATOL, rtol=REPLAY_RTOL
                )
                np.testing.assert_allclose(
                    sampled, modes["all_cell_voltage"][identity], atol=REPLAY_ATOL, rtol=REPLAY_RTOL
                )
                reconstruction.append(
                    dict(
                        world_id=identity,
                        maximum_saved_patch_voltage_difference_V=float(
                            np.max(abs(patch[indices] - saved["observed__vm"]))
                        ),
                        maximum_saved_reader_difference_V=float(
                            np.max(abs(sampled - modes["all_cell_voltage"][identity]))
                        ),
                        saved_features_bitwise=bool(
                            np.array_equal(sampled, modes["all_cell_voltage"][identity])
                        ),
                    )
                )
            histories[identity] = cell
            arrays[f"voltage__{backend}__{identity}"] = cell
        arrays["times_s"] = times
        probes = {
            mode: {
                arm: {
                    task: task_geometry(
                        rows,
                        modes[mode],
                        arm,
                        task,
                        detail,
                        margin=rule["reader"]["voltage_margin_V"],
                    )
                    for task in TASKS
                }
                for arm, detail in expected["outcomes"][mode]["arms"].items()
            }
            for mode in ("voltage", "final_voltage", "all_cell_voltage")
        }
        pairs = paired_histories(rows, histories, times, indices, rule)
        backends[backend] = dict(
            original_replay=dict(
                status="passed",
                reader_modes=7,
                shuffle_reports=32,
                max_absolute_numeric_difference=replay_error,
                exact_decisions_and_metrics=True,
            ),
            reconstruction=reconstruction,
            pairs=pairs,
            geometry=probes,
        )
    differences = [
        float(
            np.max(
                abs(
                    arrays[f"voltage__cpu__{r['world_id']}"]
                    - arrays[f"voltage__gpu__{r['world_id']}"]
                )
            )
        )
        for r in rows
    ]
    np.savez_compressed(output / "voltage-histories.npz", **arrays)
    return dict(
        status="completed",
        kind="unstimulated_saved_trajectory_diagnosis@1",
        authentication=authentication,
        cases=rows,
        backends=backends,
        maximum_reconstructed_cpu_gpu_voltage_difference_V=max(differences),
        readout_times_s=rule["readout"]["times_s"],
        primary_margin_V=rule["reader"]["voltage_margin_V"],
        source_cell_ids=rule["cue"]["source_cell_ids"],
        unstimulated_cell_ids=rule["readout"]["cell_ids"],
        limitations=[
            "Post-hoc inspection of all saved cases; not fresh validation, "
            "a new decoder or a noise model.",
            "Known labels, paired counterparts and true strengths enter geometry probes only. "
            "Original readout failures remain unchanged.",
            "Voltage is reconstructed with the unchanged model's observation law; "
            "no transport integration or field-law change.",
            "History norms at one timestep are diagnostics, not temporal convergence "
            "or numerical-error bounds.",
            "Pair separation above twice the margin is necessary for both correct resolved "
            "fixed-reader decisions, never sufficient.",
            "End-of-run trends describe the saved interval only. They cannot be extrapolated "
            "beyond 64 us, the ordinary runtime's current bound.",
        ],
        replay_tolerances=dict(atol=REPLAY_ATOL, rtol=REPLAY_RTOL),
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
    try:
        sources = {}
        for name in (
            "validation/assays/unstimulated_diagnostic.py",
            "tests/unit/test_unstimulated_diagnostic.py",
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
                scope="Post-hoc saved-data analysis; no new simulation or registration",
            ),
        )
        result = analyze(args.source.resolve(), output)
        write_json(output / "result.json", result | dict(finished_utc=utc()))
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
    print(json.dumps(dict(status="completed", output=str(output))))


if __name__ == "__main__":
    main()
