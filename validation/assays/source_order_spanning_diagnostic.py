"""Explain unresolved fresh-strength cases using accepted saved features.

The registered spanning/late comparison stays fixed. Reuse the qualified
reader and existing geometry, interpolation and timestep-attribution probes;
do not integrate, select observation times or fit a replacement reader.
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
from validation.assays import source_order_long_diagnostic as previous
from validation.assays import source_order_spanning as assay
from validation.assays.two_task_diagnostic import compare_replay
from validation.betse.spatial_active.refinement import completed_prior, digest

ROOT = Path(__file__).resolve().parents[2]
BINDING = dict(
    root="/mnt/workspaces/Cells/two-task-source-order-spanning-20261014-01",
    registration_sha256="8f433511edd3cc23ffa549af6e1ebaecda4f8fc05bbde8957e4e55e08111a476",
    completion_sha256="de34473c969630b0807f8123d3daea7655a8f29b8e8d8d1fc12e28ca22c544f4",
    require_completed_cpu_and_gpu=True,
)
PANELS = ("spanning512", "long512")


def unresolved_cases(diagnosis, *, margin):
    """Join existing probes by case/task without turning an oracle into a pass."""
    rows = []
    for case in diagnosis["cases"]["cases"]:
        for task, detail in case["tasks"].items():
            if detail["resolved_by_level"][-1]:
                continue
            interpolation = [
                next(
                    row
                    for row in level["interpolation"][task]["details"]
                    if row["world_id"] == case["world_id"]
                )
                for level in diagnosis["levels"]
            ]
            scores = detail["signed_scores_V"]
            assert len(scores) == len(interpolation) == 3
            assert scores[-1] <= margin
            rows.append(
                dict(
                    world_id=case["world_id"],
                    preparation=case["preparation"],
                    strength=case["amplitude"],
                    location=case["location"],
                    timing=case["timing"],
                    task=task,
                    original_correct_signed_scores_V=scores,
                    original_resolved_by_level=detail["resolved_by_level"],
                    finest_margin_shortfall_V=margin - scores[-1],
                    finest_signed_score_change_V=scores[-1] - scores[-2],
                    finest_pair_resolution_changed=detail["finest_pair_resolution_changed"],
                    finest_competitors=detail["finest_competitors"],
                    interpolation_by_level=interpolation,
                    original_case_remains_unresolved=True,
                    oracle_probes_are_not_new_reader_results=True,
                )
            )
    return rows


def analyze(root):
    print(json.dumps(dict(phase="authenticate_completed_evidence", utc=utc())), flush=True)
    binding = BINDING | dict(root=str(root))
    if digest(root / "completion.json") != binding["completion_sha256"]:
        raise ValueError("Completed spanning-confirmation binding differs")
    authentication = completed_prior(binding, current_root=ROOT)
    registration = json.loads((root / "registration.json").read_text())
    for name, sha in registration["sources_sha256"].items():
        if digest(ROOT / name) != sha:
            raise ValueError("Frozen source changed: " + name)
    authentication["all_prior_sources_unchanged"] = len(registration["sources_sha256"])
    rule = registration["component_protocol"]
    if rule != assay.protocol() or rule["primary_panel"] != PANELS[0]:
        raise ValueError("Registered confirmation protocol differs")
    rows, backends = assay.cases(rule), {}
    for backend in ("cpu", "gpu"):
        print(json.dumps(dict(phase="replay_and_geometry", backend=backend, utc=utc())), flush=True)
        folder = root / "evidence" / backend
        if json.loads((folder / "source-order-spanning-design.json").read_text())["cases"] != rows:
            raise ValueError("Saved case panel differs")
        saved_report = json.loads((folder / "source-order-spanning-readouts.json").read_text())
        expected = saved_report["panels"]
        with np.load(folder / "source-order-spanning-readouts.npz", allow_pickle=False) as saved:
            maps = {
                (level, panel): {
                    mode: {
                        r["world_id"]: saved[f"{level}__{panel}__{mode}__{r['world_id']}"]
                        for r in rows
                    }
                    for mode in previous.geometry.MODES
                }
                for level in range(3)
                for panel in rule["observation_panels"]
            }
        reproduced = assay.reader_reports(rows, maps, rule)
        replay_error = compare_replay(reproduced, expected)
        references = assay.reference_reports(rows, maps, reproduced, rule)
        reference_error = compare_replay(
            references,
            json.loads((folder / "source-order-spanning-baseline-transfer.json").read_text()),
        )
        paired = [
            assay.paired_report(
                reproduced[PANELS[0]]["resolution_matched"][level]["outcomes"]["voltage"],
                reproduced[PANELS[1]]["resolution_matched"][level]["outcomes"]["voltage"],
            )
            | dict(level=level)
            for level in range(3)
        ]
        paired_error = compare_replay(paired, saved_report["paired_primary_and_late"])
        panels = {}
        for panel in PANELS:
            features = [maps[level, panel]["voltage"] for level in range(3)]
            reports = [r["outcomes"]["voltage"] for r in expected[panel]["resolution_matched"]]
            diagnosis = previous.panel_diagnosis(rows, features, reports, rule)
            panels[panel] = dict(
                observation_times_us=rule["observation_times_us"][panel],
                diagnosis=diagnosis,
                unresolved=unresolved_cases(diagnosis, margin=rule["reader"]["voltage_margin_V"]),
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
            original_paired_comparison=paired,
            panels=panels,
        )
    agreement = compare_replay(backends["cpu"], backends["gpu"])
    return dict(
        status="completed",
        kind="source_order_spanning_saved_feature_diagnosis@1",
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
            "Post-hoc explanation of known deterministic cases, not another confirmation.",
            "Registered panels, calibration, predictions, margins and unresolved cases stay fixed.",
            "True strength, other labels and interpolation enter diagnostic probes only.",
            "Geometry and timestep attribution provide neither causal proof nor a continuum bound.",
            "Both saved archives are analyzed on CPU; no new GPU workload or utilization metric.",
            "Changed readers, calibration or encoding need a separate declared experiment.",
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
            "validation/assays/source_order_spanning_diagnostic.py",
            "tests/unit/test_source_order_spanning_diagnostic.py",
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
                scope="Saved-feature diagnosis using existing geometry and timestep probes; "
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
