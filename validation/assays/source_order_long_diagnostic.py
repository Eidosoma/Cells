"""Diagnose accepted 512-us source-order responses without new integration.

Replay the frozen readers, distinguish order/strength ambiguity from weak
responses, and examine one explicit early/late observation comparator. All
cases have already been inspected; this is exploration, not a new endpoint.
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
from validation.assays import distributed_timing
from validation.assays import source_order_diagnostic as diagnosis
from validation.assays import source_order_long as assay
from validation.assays import source_order_precision as precision
from validation.assays import template_readout as reader
from validation.assays import unstimulated_diagnostic as geometry
from validation.assays.two_task_diagnostic import compare_replay
from validation.betse.spatial_active.refinement import completed_prior, digest

ROOT = Path(__file__).resolve().parents[2]
BINDING = dict(
    root="/mnt/workspaces/Cells/two-task-source-order-precision-20261014-01",
    registration_sha256="ae01cd63de9ed2a1052adb9bd90fdb25fb6643e017644e069886d7257f1c435b",
    completion_sha256="e6c8c6a7e47071a0f08e4f0fc5d53c54ee518a7ba712e567637fce6b62dc7928",
    require_completed_cpu_and_gpu=True,
)
SPANNING = (("middle128", 128), ("long256", 256), ("long512", 512))


def spanning_features(rows, maps, level, rule):
    """Use five remote voltages at each of 128/256/512 us, with no rescaling.

    This is one mechanism-motivated comparator, fixed before its evaluation.
    It uses no source-cell voltage, true evaluation strength or label.
    """
    if rule["readout"]["cell_ids"] != [2, 3, 5, 6, 7]:
        raise ValueError("Spanning comparator requires the same five remote cells")
    for panel, end_us in SPANNING:
        times = rule["observation_times_us"][panel]
        if len(times) != 3 or times[-1] != end_us:
            raise ValueError("Spanning comparator observation support differs")
    result = {}
    for row in rows:
        identity = row["world_id"]
        selected = []
        for panel, _ in SPANNING:
            values = np.asarray(maps[level, panel]["voltage"][identity], dtype=float)
            if values.shape != (15,) or not np.isfinite(values).all():
                raise ValueError("Expected 15 finite remote-cell voltages")
            selected.append(values[-5:])
        result[identity] = np.concatenate(selected)
    return result


def panel_diagnosis(rows, features, reports, rule):
    """Reuse tested competing-curve, interpolation and timestep probes."""
    margin = rule["reader"]["voltage_margin_V"]
    levels = []
    for level, (values, report) in enumerate(zip(features, reports, strict=True)):
        arm = report["arms"]["joint"]
        levels.append(
            dict(
                level=level,
                dt_s=rule["dt_s"][level],
                competitors=diagnosis.competing_curves(rows, values, arm, margin=margin),
                interpolation={
                    task: geometry.task_geometry(rows, values, "joint", task, arm, margin=margin)
                    for task in diagnosis.TASKS
                },
                joint_geometry=diagnosis.joint_geometry(rows, values),
            )
        )
    attribution = [
        diagnosis.saved_history.resolution_attribution(
            rows,
            features[level],
            features[level + 1],
            reports[level]["arms"]["joint"],
            reports[level + 1]["arms"]["joint"],
            margin=margin,
        )
        | dict(old_level=level, new_level=level + 1)
        for level in (0, 1)
    ]
    return dict(
        levels=levels,
        resolution_attribution=attribution,
        cases=diagnosis.case_summary(
            rows, [level["competitors"] for level in levels], attribution, margin=margin
        ),
    )


def analyze(root):
    print(json.dumps(dict(phase="authenticate_completed_evidence", utc=utc())), flush=True)
    binding = BINDING | dict(root=str(root))
    if digest(root / "completion.json") != binding["completion_sha256"]:
        raise ValueError("Completed precision-repair binding differs")
    authentication = completed_prior(binding, current_root=ROOT)
    registration = json.loads((root / "registration.json").read_text())
    for name, sha in registration["sources_sha256"].items():
        if digest(ROOT / name) != sha:
            raise ValueError("Frozen source changed: " + name)
    authentication["all_prior_sources_unchanged"] = len(registration["sources_sha256"])
    rule = registration["component_protocol"]
    if rule != precision.protocol():
        raise ValueError("Precision-repair protocol differs")
    rows, backends = assay.cases(rule), {}
    for backend in ("cpu", "gpu"):
        print(json.dumps(dict(phase="replay_and_geometry", backend=backend, utc=utc())), flush=True)
        folder = root / "evidence" / backend
        design = json.loads((folder / "source-order-long-design.json").read_text())
        if design["cases"] != rows:
            raise ValueError("Saved case panel differs")
        expected = json.loads((folder / "source-order-long-readouts.json").read_text())["panels"]
        with np.load(folder / "source-order-long-readouts.npz", allow_pickle=False) as saved:
            maps = {
                (level, panel): {
                    mode: {
                        r["world_id"]: saved[f"{level}__{panel}__{mode}__{r['world_id']}"]
                        for r in rows
                    }
                    for mode in geometry.MODES
                }
                for level in range(3)
                for panel in rule["observation_panels"]
            }
        reproduced = assay.reader_reports(rows, maps, rule)
        replay_error = compare_replay(reproduced, expected)
        references = assay.reference_reports(rows, maps, reproduced, rule)
        reference_error = compare_replay(
            references,
            json.loads((folder / "source-order-long-baseline-transfer.json").read_text()),
        )
        panels = {}
        for panel in ("long256", "long512"):
            values = [maps[level, panel]["voltage"] for level in range(3)]
            reports = [r["outcomes"]["voltage"] for r in expected[panel]["resolution_matched"]]
            panels[panel] = panel_diagnosis(rows, values, reports, rule)
        values = [spanning_features(rows, maps, level, rule) for level in range(3)]
        reports = [
            reader.evaluate(rows, f, margin=rule["reader"]["voltage_margin_V"]) for f in values
        ]
        shuffles = [
            [
                reader.evaluate(rows, f, margin=rule["reader"]["voltage_margin_V"], shuffle_seed=s)
                for s in rule["reader"]["shuffle_seeds"]
            ]
            for f in values
        ]
        backends[backend] = dict(
            original_replay=dict(
                status="passed",
                panels=4,
                timesteps=3,
                reader_modes=7,
                exact_decisions_and_metrics=True,
                maximum_numeric_difference=replay_error,
                reference_transfer_maximum_numeric_difference=reference_error,
            ),
            original_panels=panels,
            spanning_comparator=dict(
                observation_times_us=[t for _, t in SPANNING],
                feature_count=15,
                matched_reports=reports,
                shuffles=shuffles,
                score_stability=distributed_timing.score_changes(reports, rule["score_stability"]),
                diagnosis=panel_diagnosis(rows, values, reports, rule),
                exploratory_reuse_of_inspected_cases=True,
                replaces_primary_endpoint=False,
            ),
        )
    agreement = compare_replay(backends["cpu"], backends["gpu"])
    return dict(
        status="completed",
        kind="source_order_long_saved_feature_diagnosis@1",
        authentication=authentication,
        primary_panel="long512",
        primary_margin_V=rule["reader"]["voltage_margin_V"],
        cases=rows,
        backends=backends,
        cpu_gpu_diagnostic_maximum_numeric_difference=agreement,
        new_simulations=0,
        automatic_followup=False,
        limitations=[
            "Known deterministic cases, not a fresh holdout or biological replication.",
            "The original long512 endpoint and all original results stay fixed.",
            "True strength, other labels and calibration interpolation are oracle probes only.",
            "The spanning comparator changes only observation timing; same 15 remote voltages, "
            "unchanged reader and 2-nV margin, no feature rescaling or time search.",
            "A comparator improvement would require a separately registered experiment "
            "with new evaluation strengths before a new generalization claim.",
            "Geometry and timestep attribution describe saved responses, not causal proof "
            "or a continuum bound. No complete-trajectory reconstruction was repeated.",
            "Both archives are analyzed on CPU. There is no GPU job or utilization metric.",
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
            "validation/assays/source_order_long_diagnostic.py",
            "tests/unit/test_source_order_long_diagnostic.py",
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
                spanning_observation_times_us=[t for _, t in SPANNING],
                candidate_count=1,
                scope="Saved-feature diagnosis and one exploratory timing comparator; "
                "no simulation or replacement primary endpoint",
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
