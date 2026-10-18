"""Diagnose the fixed-dose timing result from authenticated saved trajectories.

Reuse the existing voltage law, readers and geometry probes. Original fits are
replayed for verification; no simulation or replacement endpoint is run.
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
from validation.assays import cue_separation as assay
from validation.assays import template_diagnostic as geometry
from validation.assays import template_readout as reader
from validation.assays import unstimulated_diagnostic as history
from validation.assays.two_task_diagnostic import REPLAY_ATOL, REPLAY_RTOL, compare_replay
from validation.betse.spatial_active.refinement import completed_prior, digest

ROOT = Path(__file__).resolve().parents[2]
BINDING = dict(
    root="/mnt/workspaces/Cells/two-task-cue-separation-20261013-01",
    registration_sha256="ed979b4bda793d64d5ff5195a056ed18b0967c68e342d3051359ebbed3f7c4a7",
    completion_sha256="d66bb38b9ed2452aad6b28e290e6839c29fe2c3a5f40f6ca69af4822caade1ae",
    require_completed_cpu_and_gpu=True,
)


def window_history(archive, record):
    """Read only voltage-relevant arrays; verify and count shared endpoints once."""
    if record["status"] != "passed" or not record["windows"]:
        raise ValueError("Incomplete world archive")
    dt = record["input"]["execution"]["dt"]
    stop = round(record["input"]["experiment"]["end_time"] / dt)
    names = ("state__step_count", "state__elapsed_s", "state__cell_concentration")
    pieces, observed, observed_times, previous = {k: [] for k in names}, [], [], None
    for chunk in record["windows"]:
        path = (archive / chunk["file"]).resolve()
        if not path.is_relative_to(archive.resolve()):
            raise ValueError("Unsafe archive window path")
        first, last = chunk["start_step"], chunk["stop_step"]
        expected_start = 0 if previous is None else int(previous["state__step_count"][-1])
        if first != expected_start or last <= first:
            raise ValueError("Noncontiguous archive windows")
        with np.load(path, allow_pickle=False) as saved:
            values = {k: saved[k] for k in names}
            np.testing.assert_array_equal(values["state__step_count"], np.arange(first, last + 1))
            for value in values.values():
                if len(value) != last - first + 1:
                    raise ValueError("Archive state length differs")
            np.testing.assert_allclose(
                values["state__elapsed_s"],
                values["state__step_count"] * dt,
                atol=6e-17,
                rtol=0,
            )
            if previous is not None:
                for name in names:
                    np.testing.assert_array_equal(values[name][0], previous[name][-1])
            for name in names:
                pieces[name].append(values[name][int(previous is not None) :])
            observed.append(saved["observed__vm"])
        previous = values
        observed_times.extend(chunk["observation_times"])
    steps = np.concatenate(pieces["state__step_count"])
    np.testing.assert_array_equal(steps, np.arange(stop + 1))
    np.testing.assert_array_equal(
        observed_times, record["input"]["experiment"]["observation_times"]
    )
    indices = np.rint(np.asarray(observed_times) / dt).astype(int)
    np.testing.assert_allclose(steps[indices] * dt, observed_times, atol=6e-17, rtol=0)
    patch, cell = history.voltage_history(
        np.concatenate(pieces["state__cell_concentration"]), record["input"]["model"]["tissue"]
    )
    saved_patch = np.concatenate(observed)
    np.testing.assert_allclose(patch[indices], saved_patch, atol=REPLAY_ATOL, rtol=REPLAY_RTOL)
    return (
        steps * dt,
        cell,
        dict(
            windows=len(record["windows"]),
            states=len(steps),
            shared_endpoints_verified=True,
            maximum_saved_patch_voltage_difference_V=float(
                np.max(abs(patch[indices] - saved_patch))
            ),
        ),
    )


def resolution_attribution(rows, old_features, new_features, old_arm, new_arm, *, margin):
    """Cross fixed readers and features to expose both orders of score changes.

    This is an algebraic decomposition of the saved timestep difference, not
    an error estimate. The two paths need not assign the same contributions.
    """
    tasks, _, testing = reader.split(rows, "joint")
    fits = [
        reader.TemplateReader(**a["calibration"]["template_reader"]) for a in (old_arm, new_arm)
    ]
    np.testing.assert_array_equal(fits[0].labels, fits[1].labels)
    features = [np.stack([m[r["world_id"]] for r in testing]) for m in (old_features, new_features)]
    decoded = [[fit.read(values) for values in features] for fit in fits]
    details = []
    for index, row in enumerate(testing):
        distance = float(np.linalg.norm(features[1][index] - features[0][index]))
        roundoff = 64 * np.finfo(float).eps * max(float(np.linalg.norm(f[index])) for f in features)
        for column, task in enumerate(tasks):
            cc, cf, fc, ff = [
                float(decoded[a][b]["score"][index, column])
                for a, b in ((0, 0), (0, 1), (1, 0), (1, 1))
            ]
            for arm, score in ((old_arm, cc), (new_arm, ff)):
                saved = arm["tasks"][task]["predictions"][index]
                if (saved["world_id"], saved["target"]) != (row["world_id"], row[task]):
                    raise ValueError("Saved attribution identity differs")
                np.testing.assert_allclose(
                    score, saved["score"], atol=REPLAY_ATOL, rtol=REPLAY_RTOL
                )
            if max(abs(cf - cc), abs(ff - fc)) > distance + roundoff:
                raise ValueError("Fixed-reader perturbation bound failed")
            before, after = abs(cc) > margin, abs(ff) > margin
            details.append(
                dict(
                    world_id=row["world_id"],
                    task=task,
                    strength=row["amplitude"],
                    target=row[task],
                    old_score_V=cc,
                    new_score_V=ff,
                    score_change_V=ff - cc,
                    new_features_old_reader_score_V=cf,
                    old_features_new_reader_score_V=fc,
                    feature_change_with_old_reader_V=cf - cc,
                    reader_change_at_new_features_V=ff - cf,
                    reader_change_at_old_features_V=fc - cc,
                    feature_change_with_new_reader_V=ff - fc,
                    feature_difference_l2_V=distance,
                    old_resolved=before,
                    new_resolved=after,
                    resolution_changed=before != after,
                    prediction_changed=(cc > 0) != (ff > 0),
                    old_signed_distance_above_margin_V=(2 * row[task] - 1) * cc - margin,
                    new_signed_distance_above_margin_V=(2 * row[task] - 1) * ff - margin,
                )
            )
    return dict(details=details, path_dependent_decomposition=True, continuum_error_bound=False)


def case_summary(rows, levels, attribution, *, margin):
    """Retain every primary timing case, including both unresolved and borderline."""
    results = []
    testing = [r for r in rows if r["arm"] == "joint" and r["split"] != "calibration"]
    for row in testing:
        details = [
            next(d for d in level["details"] if d["world_id"] == row["world_id"])
            for level in levels
        ]
        signed = [d["original_correct_signed_margin"] for d in details]
        resolved = [bool(s > margin) for s in signed]
        changed = [
            d
            for d in attribution[-1]["details"]
            if d["world_id"] == row["world_id"] and d["task"] == "timing"
        ][0]
        results.append(
            row
            | dict(
                signed_timing_score_by_level_V=signed,
                correct_and_resolved_by_level=resolved,
                unresolved_at_primary=not resolved[-1],
                finest_pair_resolution_changed=changed["resolution_changed"],
                minimum_tested_signed_margin_V=min(signed) - margin,
                finest_geometry=details[-1],
            )
        )
    return dict(
        cases=results,
        unresolved_world_ids=[r["world_id"] for r in results if r["unresolved_at_primary"]],
        finest_pair_borderline_world_ids=[
            r["world_id"] for r in results if r["finest_pair_resolution_changed"]
        ],
        correct_and_resolved_at_all_three_steps=sum(
            all(r["correct_and_resolved_by_level"]) for r in results
        ),
        tested_steps_are_not_a_continuum_bound=True,
    )


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
    if rule != assay.protocol():
        raise ValueError("Source protocol differs")
    rows, arrays, backends = assay.cases(), {}, {}
    joint = [r for r in rows if r["arm"] == "joint"]
    margin = rule["reader"]["voltage_margin_V"]
    for backend in ("cpu", "gpu"):
        print(json.dumps(dict(backend=backend, phase="reader_replay", utc=utc())), flush=True)
        directory = root / "evidence" / backend
        assert json.loads((directory / "cue-separation-design.json").read_text())["cases"] == rows
        expected = json.loads((directory / "cue-separation-readouts.json").read_text())["panels"]
        with np.load(directory / "cue-separation-readouts.npz", allow_pickle=False) as saved:
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
        primary = expected["long256"]["resolution_matched"]
        probes = [
            dict(
                level=level,
                dt_s=rule["dt_s"][level],
                arms={
                    arm: geometry.diagnose_arm(
                        rows, maps[level, "long256"]["voltage"], arm, report, margin=margin
                    )
                    for arm, report in primary[level]["outcomes"]["voltage"]["arms"].items()
                },
            )
            for level in range(3)
        ]
        attribution = [
            resolution_attribution(
                rows,
                maps[level, "long256"]["voltage"],
                maps[level + 1, "long256"]["voltage"],
                primary[level]["outcomes"]["voltage"]["arms"]["joint"],
                primary[level + 1]["outcomes"]["voltage"]["arms"]["joint"],
                margin=margin,
            )
            | dict(old_level=level, new_level=level + 1)
            for level in (0, 1)
        ]
        reconstructions, pairs = [], []
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
                times, cell, checks = window_history(directory, record)
                differences, bitwise = [], True
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
                        bitwise &= np.array_equal(vector, old)
                reconstructions.append(
                    checks
                    | dict(
                        level=level,
                        world_id=identity,
                        saved_features_bitwise=bool(bitwise),
                        maximum_saved_reader_difference_V=max(differences),
                    )
                )
                histories[identity] = cell
                arrays[f"voltage__{backend}__{level}__{identity}"] = cell
            indices = np.rint(assay.times(rule, "long256") / dt).astype(int)
            pair_rule = rule | dict(
                cue=dict(source_cell_ids=rule["readout"]["excluded_source_cell_ids"])
            )
            pairs.extend(
                p | dict(level=level, dt_s=dt)
                for p in history.paired_histories(joint, histories, times, indices, pair_rule)
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
            ),
            geometry=probes,
            resolution_attribution=attribution,
            reconstruction=reconstructions,
            pairs=pairs,
            primary_timing=case_summary(
                rows, [p["arms"]["joint"] for p in probes], attribution, margin=margin
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
        kind="cue_separation_saved_trajectory_diagnosis@1",
        authentication=authentication,
        cases=rows,
        backends=backends,
        cpu_gpu_voltage_differences=differences,
        primary_margin_V=margin,
        primary_readout_times_s=assay.times(rule, "long256").tolist(),
        source_cell_ids=rule["readout"]["excluded_source_cell_ids"],
        unstimulated_cell_ids=rule["readout"]["cell_ids"],
        replay_tolerances=dict(atol=REPLAY_ATOL, rtol=REPLAY_RTOL),
        limitations=[
            "Post-hoc analysis of inspected synthetic cases; "
            "no new holdout or biological validation.",
            "Original primary results, failures, thresholds and observation times remain fixed.",
            "Known labels, strengths and paired counterparts enter diagnostic probes only.",
            "Geometry uses fixed saved readers; no diagnostic is a replacement decoder.",
            "Pair separation above twice the margin is necessary, "
            "never sufficient for both labels.",
            "History trends describe only 0--256 us and cannot be extrapolated.",
            "Timestep attribution has two path-dependent orders; "
            "neither is a continuum error bound.",
            "Complete joint histories are reconstructed; control arms use saved readout features.",
            "CPU and GPU saved data are read on CPU; this analysis launches no GPU workload.",
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
            "validation/assays/cue_separation_diagnostic.py",
            "tests/unit/test_cue_separation_diagnostic.py",
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
                scope="Saved-data diagnosis; no new simulation, calibration or endpoint selection",
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
