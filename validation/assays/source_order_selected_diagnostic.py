"""Explain the selected schedule's unresolved cases and paired trade-offs.

Replay completed CPU/L4 evidence and reuse the existing curve, interpolation
and timestep probes. Keep both registered comparators, every gain/regression,
the 2-nV margin and all original predictions; fit no new reader candidate.
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
from validation.assays import source_order_selected as assay
from validation.assays import source_order_spanning_diagnostic as previous
from validation.assays.source_order_long_diagnostic import panel_diagnosis
from validation.assays.two_task_diagnostic import compare_replay
from validation.assays.unstimulated_diagnostic import MODES
from validation.betse.spatial_active.refinement import completed_prior, digest

ROOT = Path(__file__).resolve().parents[2]
BINDING = dict(
    root="/mnt/workspaces/Cells/two-task-source-order-selected-20261015-01",
    registration_sha256="3dbef1145db62fcc84dc3cfc075170057b7aa9c930c6336d53149c98d78aad37",
    completion_sha256="405e0656c945544f661a2f88beda9971b2f99b4650ef48772318da0abc1e30cf",
    require_completed_cpu_and_gpu=True,
)
PANELS = ("selected320", "spanning512", "long512")
TASKS = ("location", "timing")


def paired_case_summary(rows, levels, *, margin):
    """Join fixed paired reports by identity, preserving both directions.

    Scores are signed toward the known label for explanation only. A positive
    margin deficit means unresolved; no oracle or cross-panel fusion is used.
    """
    testing = [r for r in rows if r["arm"] == "joint" and r["split"] == "heldout"]
    identities = {r["world_id"] for r in testing}
    if len(identities) != len(testing) or len(levels) != 3:
        raise ValueError("Expected unique joint cases and three timestep levels")
    indexed = []
    names = (levels[0]["primary_panel"], levels[0]["comparator_panel"])
    for index, level in enumerate(levels):
        if level["level"] != index or names != (level["primary_panel"], level["comparator_panel"]):
            raise ValueError("Paired panel or timestep identity differs")
        by_id = {case["world_id"]: case for case in level["cases"]}
        if set(by_id) != identities or len(by_id) != len(level["cases"]):
            raise ValueError("Paired case identity is missing or duplicated")
        indexed.append(by_id)
    cases = []
    for row in testing:
        identity, tasks = row["world_id"], {}
        pairs = [index[identity] for index in indexed]
        for task in TASKS:
            scores, resolved = {}, {}
            for side in ("primary", "comparator"):
                predictions = [pair[side][task] for pair in pairs]
                if any((p["world_id"], p["target"]) != (identity, row[task]) for p in predictions):
                    raise ValueError("Paired prediction identity or target differs")
                scores[side] = [(2 * row[task] - 1) * p["score"] for p in predictions]
                resolved[side] = [
                    p["resolved"] and p["prediction"] == p["target"] for p in predictions
                ]
            tasks[task] = dict(
                correct_signed_scores_V=scores,
                correct_and_resolved=resolved,
                margin_deficits_V={side: [margin - s for s in ss] for side, ss in scores.items()},
                primary_minus_comparator_scores_V=[
                    a - b for a, b in zip(scores["primary"], scores["comparator"], strict=True)
                ],
            )
        categories = [pair["category"] for pair in pairs]
        cases.append(
            dict(
                world_id=identity,
                preparation=row["preparation"],
                strength=row["amplitude"],
                location=row["location"],
                timing=row["timing"],
                categories_by_level=categories,
                discordant_at_any_level=any(
                    c in ("primary_only", "comparator_only") for c in categories
                ),
                primary_unresolved_at_any_level=any(
                    not all(task["correct_and_resolved"]["primary"]) for task in tasks.values()
                ),
                tasks=tasks,
            )
        )
    return dict(
        primary_panel=names[0],
        comparator_panel=names[1],
        counts_by_level=[level["counts"] for level in levels],
        cases=cases,
        focus_world_ids=[
            case["world_id"]
            for case in cases
            if case["primary_unresolved_at_any_level"] or case["discordant_at_any_level"]
        ],
        original_results_unchanged=True,
        diagnostic_uses_true_labels=True,
        combines_neither_predictions_nor_scores_across_panels=True,
    )


def analyze(root):
    print(json.dumps(dict(phase="authenticate_completed_evidence", utc=utc())), flush=True)
    binding = BINDING | dict(root=str(root))
    if digest(root / "completion.json") != binding["completion_sha256"]:
        raise ValueError("Completed selected-confirmation binding differs")
    authentication = completed_prior(binding, current_root=ROOT)
    registration = json.loads((root / "registration.json").read_text())
    for name, sha in registration["sources_sha256"].items():
        if digest(ROOT / name) != sha:
            raise ValueError("Frozen source changed: " + name)
    authentication["all_prior_sources_unchanged"] = len(registration["sources_sha256"])
    rule = registration["component_protocol"]
    if (
        rule != assay.protocol()
        or rule["primary_panel"] != PANELS[0]
        or rule["paired_comparator_panels"] != list(PANELS[1:])
    ):
        raise ValueError("Registered confirmation protocol differs")
    rows, backends = assay.cases(rule), {}
    for backend in ("cpu", "gpu"):
        print(json.dumps(dict(phase="replay_and_geometry", backend=backend, utc=utc())), flush=True)
        folder = root / "evidence" / backend
        if json.loads((folder / "source-order-selected-design.json").read_text())["cases"] != rows:
            raise ValueError("Saved case panel differs")
        saved_report = json.loads((folder / "source-order-selected-readouts.json").read_text())
        expected = saved_report["panels"]
        with np.load(folder / "source-order-selected-readouts.npz", allow_pickle=False) as saved:
            maps = {
                (level, panel): {
                    mode: {
                        r["world_id"]: saved[f"{level}__{panel}__{mode}__{r['world_id']}"]
                        for r in rows
                    }
                    for mode in MODES
                }
                for level in range(3)
                for panel in rule["observation_panels"]
            }
        reproduced = assay.reader_reports(rows, maps, rule)
        replay_error = compare_replay(reproduced, expected)
        references = assay.reference_reports(rows, maps, reproduced, rule)
        reference_error = compare_replay(
            references,
            json.loads((folder / "source-order-selected-baseline-transfer.json").read_text()),
        )
        paired = {
            name: [
                assay.paired_report(
                    reproduced[PANELS[0]]["resolution_matched"][level]["outcomes"]["voltage"],
                    reproduced[name]["resolution_matched"][level]["outcomes"]["voltage"],
                    primary_name=PANELS[0],
                    comparator_name=name,
                )
                | dict(level=level)
                for level in range(3)
            ]
            for name in PANELS[1:]
        }
        paired_error = compare_replay(paired, saved_report["paired_comparisons"])
        panels = {}
        for panel in PANELS:
            features = [maps[level, panel]["voltage"] for level in range(3)]
            reports = [r["outcomes"]["voltage"] for r in expected[panel]["resolution_matched"]]
            diagnosis = panel_diagnosis(rows, features, reports, rule)
            panels[panel] = dict(
                observation_times_us=rule["observation_times_us"][panel],
                diagnosis=diagnosis,
                unresolved=previous.unresolved_cases(
                    diagnosis, margin=rule["reader"]["voltage_margin_V"]
                ),
            )
        backends[backend] = dict(
            original_replay=dict(
                status="passed",
                panels=len(rule["observation_panels"]),
                timesteps=3,
                reader_modes=7,
                label_shuffles_per_panel_and_timestep=len(rule["reader"]["shuffle_seeds"]),
                maximum_numeric_difference=replay_error,
                reference_transfer_maximum_numeric_difference=reference_error,
                paired_comparison_maximum_numeric_difference=paired_error,
            ),
            original_paired_comparisons=paired,
            paired_cases={
                name: paired_case_summary(rows, levels, margin=rule["reader"]["voltage_margin_V"])
                for name, levels in paired.items()
            },
            panels=panels,
        )
    agreement = compare_replay(backends["cpu"], backends["gpu"])
    return dict(
        status="completed",
        kind="source_order_selected_saved_feature_diagnosis@1",
        authentication=authentication,
        primary_panel=rule["primary_panel"],
        primary_margin_V=rule["reader"]["voltage_margin_V"],
        cases=rows,
        backends=backends,
        cpu_gpu_diagnostic_maximum_numeric_difference=agreement,
        new_simulations=0,
        new_reader_candidates=0,
        automatic_followup=False,
        limitations=[
            "Post-hoc explanation of known deterministic cases, not a fresh confirmation.",
            "All registered panels, predictions, calibration, margins and failures remain fixed.",
            "True strength, other labels and interpolation enter diagnostic probes only.",
            "Do not fuse readers, rerank times or tune margins on these inspected responses.",
            "Geometry and timestep attribution provide no causal proof or continuum bound.",
            "Both saved backends are analyzed on CPU; no new GPU utilization measurement.",
            "Changed observations, readers or physical encoding need a separate experiment.",
        ],
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
            "validation/assays/source_order_selected_diagnostic.py",
            "tests/unit/test_source_order_selected_diagnostic.py",
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
                panels=list(PANELS),
                new_reader_candidates=0,
                scope="Saved-feature diagnosis and paired gain/regression accounting; "
                "no simulation, time search or replacement endpoint",
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
            dict(status="failed", error=str(exc), traceback=traceback.format_exc(), utc=utc()),
        )
        raise
    print(json.dumps(dict(status="completed", output=str(output))), flush=True)


if __name__ == "__main__":
    main()
