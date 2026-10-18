"""Measure timestep drift against a fixed no-cue reference in saved evidence.

Only the original long256 voltage panel is examined. Translation of both the
saved calibration vertices and observations must preserve matched decoding.
Across timesteps, the reference changes but the source response curves stay
fixed. This is a numerical diagnostic, not a new sensing or validation claim.
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
from validation.assays import template_readout as reader
from validation.assays.two_task_diagnostic import REPLAY_ATOL, REPLAY_RTOL, compare_replay
from validation.betse.spatial_active.refinement import completed_prior, digest

ROOT = Path(__file__).resolve().parents[2]
BINDING = dict(
    root="/mnt/workspaces/Cells/two-task-cue-separation-20261013-01",
    registration_sha256="ed979b4bda793d64d5ff5195a056ed18b0967c68e342d3051359ebbed3f7c4a7",
    completion_sha256="d66bb38b9ed2452aad6b28e290e6839c29fe2c3a5f40f6ca69af4822caade1ae",
    require_completed_cpu_and_gpu=True,
)


def no_cue_reference(rows, features):
    """Use one calibration control; verify all duplicate no-cue inputs agree."""
    controls = [r for r in rows if r["arm"] == "no_cue"]
    training = [r for r in controls if r["split"] == "calibration"]
    if not training:
        raise ValueError("A no-cue calibration reference is required")
    selected = min(training, key=lambda r: r["world_id"])
    reference = np.asarray(features[selected["world_id"]], dtype=float)
    if reference.ndim != 1 or not reference.size or not np.isfinite(reference).all():
        raise ValueError("Finite voltage reference required")
    for row in controls:
        np.testing.assert_array_equal(features[row["world_id"]], reference)
    return reference.copy(), dict(
        selected_calibration_world_id=selected["world_id"],
        duplicate_control_world_ids=[r["world_id"] for r in controls],
        all_controls_bitwise_equal=True,
        independent_biological_replicates=0,
        baseline_V=reference.tolist(),
        stimulated_or_evaluation_data_fit_the_baseline=False,
    )


def transfer(rows, source, target, *, source_reference, target_reference, margin):
    """Replay the inherited evaluator using only translated source calibration."""
    features = {
        row["world_id"]: source[row["world_id"]] - source_reference
        if row["split"] == "calibration"
        else target[row["world_id"]] - target_reference
        for row in rows
    }
    return reader.evaluate(rows, features, margin=margin)


def translation_check(original, translated):
    """Keep original distances, margins and any roundoff-level null label flips."""
    if original["arms"].keys() != translated["arms"].keys():
        raise ValueError("Translation changed the case panel")
    max_score, max_distance, differing = 0.0, 0.0, []
    for arm, before in original["arms"].items():
        after = translated["arms"][arm]
        assert before["calibration"]["world_ids"] == after["calibration"]["world_ids"]
        for task, old in before["tasks"].items():
            for a, b in zip(old["predictions"], after["tasks"][task]["predictions"], strict=True):
                if (a["world_id"], a["target"], a["resolved"]) != (
                    b["world_id"],
                    b["target"],
                    b["resolved"],
                ):
                    raise ValueError("Translation changed a resolved decision or case identity")
                np.testing.assert_allclose(
                    a["score"], b["score"], atol=REPLAY_ATOL, rtol=REPLAY_RTOL
                )
                max_score = max(max_score, abs(a["score"] - b["score"]))
                if a["prediction"] != b["prediction"]:
                    limit = REPLAY_ATOL + REPLAY_RTOL * abs(a["score"])
                    if a["resolved"] or max(abs(a["score"]), abs(b["score"])) > limit:
                        raise ValueError("Translation changed a non-null forced decision")
                    differing.append(dict(arm=arm, task=task, before=a, after=b))
        for a, b in zip(before["projections"], after["projections"], strict=True):
            assert a["world_id"] == b["world_id"]
            x, y = np.asarray(a["curve_distances"]), np.asarray(b["curve_distances"])
            np.testing.assert_allclose(x, y, atol=REPLAY_ATOL, rtol=REPLAY_RTOL)
            max_distance = max(max_distance, float(np.max(abs(x - y))))
    return dict(
        status="passed",
        maximum_score_difference_V=max_score,
        maximum_curve_distance_difference_V=max_distance,
        resolved_decisions_preserved=True,
        unresolved_null_prediction_differences=differing,
    )


def drift(rows, old, new, old_reference, new_reference):
    """Measure shared-reference subtraction; this is not a fitted projection."""
    background = new_reference - old_reference
    details = []
    for row in rows:
        identity = row["world_id"]
        raw = new[identity] - old[identity]
        residual = (new[identity] - new_reference) - (old[identity] - old_reference)
        norm, remaining = float(np.linalg.norm(raw)), float(np.linalg.norm(residual))
        details.append(
            row
            | dict(
                raw_drift_l2_V=norm,
                referenced_drift_l2_V=remaining,
                remaining_l2_fraction=remaining / norm if norm else None,
                raw_drift_V=raw.tolist(),
                referenced_drift_V=residual.tolist(),
            )
        )
    return dict(
        background_drift_V=background.tolist(),
        background_drift_l2_V=float(np.linalg.norm(background)),
        cases=details,
        fitted_background_coefficients=0,
    )


def transfer_changes(reference, transferred):
    """Changes from the source-level matched reader, with failure counts visible."""
    comparisons = []
    for arm, report in reference["arms"].items():
        for task, values in report["tasks"].items():
            old = values["predictions"]
            new = transferred["arms"][arm]["tasks"][task]["predictions"]
            assert [(r["world_id"], r["target"]) for r in old] == [
                (r["world_id"], r["target"]) for r in new
            ]
            comparisons.append(
                dict(
                    arm=arm,
                    task=task,
                    cases=len(old),
                    max_score_change_V=max(
                        abs(a["score"] - b["score"]) for a, b in zip(old, new, strict=True)
                    ),
                    prediction_changed_world_ids=[
                        a["world_id"]
                        for a, b in zip(old, new, strict=True)
                        if a["prediction"] != b["prediction"]
                    ],
                    resolution_changed_world_ids=[
                        a["world_id"]
                        for a, b in zip(old, new, strict=True)
                        if a["resolved"] != b["resolved"]
                    ],
                    correct_and_resolved=sum(
                        r["resolved"] and r["prediction"] == r["target"] for r in new
                    ),
                )
            )
    return comparisons


def analyze(root):
    binding = BINDING | dict(root=str(root))
    print(json.dumps(dict(phase="authentication", utc=utc())), flush=True)
    authentication = completed_prior(binding, current_root=ROOT)
    if authentication["completion_sha256"] != binding["completion_sha256"]:
        raise ValueError("Completed source binding differs")
    registration = json.loads((root / "registration.json").read_text())
    for name, expected in registration["sources_sha256"].items():
        if digest(ROOT / name) != expected:
            raise ValueError("Frozen source changed: " + name)
    authentication["all_prior_sources_unchanged"] = len(registration["sources_sha256"])
    rule, rows, backends = registration["component_protocol"], assay.cases(), {}
    assert rule == assay.protocol()
    margin = rule["reader"]["voltage_margin_V"]
    for backend in ("cpu", "gpu"):
        print(json.dumps(dict(phase="baseline_transfer", backend=backend, utc=utc())), flush=True)
        directory = root / "evidence" / backend
        assert json.loads((directory / "cue-separation-design.json").read_text())["cases"] == rows
        saved = json.loads((directory / "cue-separation-readouts.json").read_text())["panels"][
            "long256"
        ]
        with np.load(directory / "cue-separation-readouts.npz", allow_pickle=False) as data:
            features = [
                {r["world_id"]: data[f"{level}__long256__voltage__{r['world_id']}"] for r in rows}
                for level in range(3)
            ]
        references = [no_cue_reference(rows, f) for f in features]
        reports, invariance, replay_error = {}, [], 0.0
        for source in range(3):
            for target in range(3):
                raw = transfer(
                    rows,
                    features[source],
                    features[target],
                    source_reference=0,
                    target_reference=0,
                    margin=margin,
                )
                centered = transfer(
                    rows,
                    features[source],
                    features[target],
                    source_reference=references[source][0],
                    target_reference=references[target][0],
                    margin=margin,
                )
                reports[source, target] = dict(raw=raw, referenced=centered)
                if source == target:
                    replay_error = max(
                        replay_error,
                        compare_replay(
                            raw, saved["resolution_matched"][source]["outcomes"]["voltage"]
                        ),
                    )
                    invariance.append(translation_check(raw, centered) | dict(level=source))
                if source == 0:
                    replay_error = max(
                        replay_error, compare_replay(raw, saved["frozen_coarse"]["voltage"][target])
                    )
        backends[backend] = dict(
            references=[report | dict(level=level) for level, (_, report) in enumerate(references)],
            original_replay=dict(
                status="passed",
                matched_and_frozen_coarse=True,
                max_absolute_numeric_difference=replay_error,
            ),
            translation_invariance=invariance,
            drift=[
                drift(rows, features[a], features[b], references[a][0], references[b][0])
                | dict(source_level=a, target_level=b)
                for a, b in ((0, 1), (1, 2), (0, 2))
            ],
            transfers=[
                dict(
                    source_level=a,
                    target_level=b,
                    **reports[a, b],
                    changes_from_source={
                        mode: transfer_changes(reports[a, a][mode], reports[a, b][mode])
                        for mode in ("raw", "referenced")
                    },
                )
                for a in range(3)
                for b in range(3)
            ],
        )
    return dict(
        status="completed",
        kind="no_cue_baseline_transfer_diagnosis@1",
        authentication=authentication,
        backends=backends,
        dt_s=rule["dt_s"],
        panel="long256",
        mode="voltage",
        feature_count=15,
        primary_margin_V=margin,
        replay_tolerances=dict(atol=REPLAY_ATOL, rtol=REPLAY_RTOL),
        limitations=[
            "Post-hoc numerical diagnosis on inspected synthetic cases, not fresh validation.",
            "One no-cue calibration reference per backend and timestep; no per-case baseline fit.",
            "Translation preserves within-timestep geometry; it cannot resolve strength ambiguity.",
            "A target-timestep control is supplied for transfer: this is reference-assisted, "
            "not transfer without target-domain information.",
            "The source response curves stay fixed apart from their shared coordinate translation.",
            "All nine timestep combinations are reported without selecting a new endpoint.",
            "Residual drift and transferred decisions are outcomes, not acceptance gates.",
            "Three finite timesteps supply no continuum error bound or biological noise model.",
            "Original assay outcomes and thresholds remain unchanged; no new integration.",
        ],
        new_simulations=0,
        gpu_workload_launched=False,
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
            "validation/assays/baseline_transfer_diagnostic.py",
            "tests/unit/test_baseline_transfer_diagnostic.py",
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
                scope="Shared no-cue reference, original primary features, all timestep transfers",
            ),
        )
        result = analyze(args.source.resolve())
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
