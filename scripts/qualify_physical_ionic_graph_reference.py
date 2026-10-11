"""Execute the frozen, bounded NUM-008 graph reference qualification."""

import argparse
import hashlib
import io
import json
import os
import platform
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic

import numpy as np
import scipy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.qualify_voltage_gated_reference import Artifacts  # noqa: E402
from tests import physical_ionic_graph_numerical_checks as checks  # noqa: E402
from tests import physical_ionic_graph_numerical_data as data  # noqa: E402
from tests import reference_physical_ionic_graph_dynamics as ref  # noqa: E402

SOURCE_FILES = (
    "tests/__init__.py",
    "configs/reference/physical_ionic_graph_v1.json",
    "configs/reference/physical_ionic_graph_trajectories_v1.json",
    "docs/PHYSICAL_IONIC_GRAPH_SPEC.md",
    "docs/PHYSICAL_IONIC_GRAPH_NUMERICS.md",
    "tests/reference_multispecies.py",
    "tests/reference_multispecies_dynamics.py",
    "tests/multispecies_numerical_checks.py",
    "tests/reference_voltage_gated_channel.py",
    "tests/reference_voltage_gated_dynamics.py",
    "tests/voltage_gated_numerical_checks.py",
    "tests/reference_physical_ionic_graph.py",
    "tests/physical_ionic_graph_numerical_data.py",
    "tests/reference_physical_ionic_graph_dynamics.py",
    "tests/physical_ionic_graph_numerical_checks.py",
    "tests/unit/test_physical_ionic_graph_dynamics.py",
    "tests/unit/test_physical_ionic_graph_artifact_audit.py",
    "scripts/qualify_voltage_gated_reference.py",
    "scripts/audit_multispecies_reference.py",
    "scripts/qualify_physical_ionic_graph_reference.py",
    "scripts/audit_physical_ionic_graph_reference.py",
    "reports/spec-007-design-check.json",
    "runs/core-007-2026-09-10/release-audit.json",
    "pyproject.toml",
    "requirements-lock.txt",
    "requirements-reference.txt",
)
THREAD_NAMES = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def capture_sources():
    buffer, hashes = io.BytesIO(), {}
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in SOURCE_FILES:
            payload = (ROOT / name).read_bytes()
            hashes[name] = sha(payload)
            archive.writestr(name, payload)
    return buffer.getvalue(), hashes


def run(output):
    plan, cases = data.load_panel()
    affinity = sorted(os.sched_getaffinity(0))
    checks.require(
        len(affinity) == 1 and all(os.environ.get(k) == "1" for k in THREAD_NAMES),
        "Qualification requires one CPU and one-thread environment",
    )
    checks.require(
        (platform.python_version(), np.__version__, scipy.__version__)
        == ("3.13.5", "2.5.3", "1.18.1"),
        "Unqualified dense-basis runtime",
    )
    archive, hashes = capture_sources()
    artifacts = Artifacts(output, plan["resources"]["artifact_bytes"])
    artifacts.write("sources.zip", archive)
    artifacts.write("protocol.json", data.PANEL.read_bytes())
    artifacts.json("cases.json", [case.definition() for case in cases])
    started, analyses, summaries, reduction_summaries = monotonic(), {}, {}, {}
    deadline = started + plan["resources"]["session_wall_seconds"]
    artifacts.json(
        "session.json",
        {
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "protocol_sha256": data.PANEL_SHA256,
            "source_sha256": hashes,
            "resources": plan["resources"],
            "runtime": {
                "python": platform.python_version(),
                "numpy": np.__version__,
                "scipy": scipy.__version__,
                "cpu_affinity": affinity,
                "thread_environment": {k: os.environ.get(k) for k in THREAD_NAMES},
            },
            "state_layout": (
                "nine SPEC-007 fields in declared order, cell-/edge-major; "
                "canonical amounts are increments"
            ),
            "native_coordinates": {
                "Radau": "increments",
                "BDF": "increments",
                "RK4": "absolute_amounts",
            },
            "dense_basis": "Radau/RK4 normalized-time power; BDF Newton coefficients and factors",
        },
    )
    current_case, current_attempt = None, None
    try:
        for case in cases:
            current_case, records, stats = case.id, {}, {}
            definition = case.definition()
            samples = ref.comparison_grid(case, plan["candidate"])
            attempts = [(s["id"], s) for s in plan["references"]] + [
                (f"rk4_{dt:g}", dt) for dt in plan["candidate"]["steps_s"]
            ]
            for name, setting in attempts:
                current_attempt = name
                print(f"{case.id}: {name}", flush=True)
                budget = ref.Budget(
                    deadline=deadline, max_calls=plan["resources"]["max_rhs_calls_per_attempt"]
                )
                if isinstance(setting, dict):
                    arrays, stats[name] = ref.integrate_reference(case, setting, budget=budget)
                    kind = setting["method"]
                else:
                    arrays, stats[name] = ref.integrate_candidate(case, setting, budget=budget)
                    kind = "RK4"
                budget.check()
                complete = stats[name]["status"] == "complete"
                records[name] = arrays | {
                    "sample_times_s": samples if complete else np.empty(0),
                    "sample_state": ref.sample_record(case, arrays, kind, samples)
                    if complete
                    else np.empty((0, case.size)),
                }
                artifacts.arrays(f"{case.id}/{name}.npz", records[name])
                artifacts.json(f"{case.id}/{name}.json", stats[name])
            analyses[case.id] = checks.analyze_case(definition, records, stats, plan)
            if case.independent_cell_reduction:
                components, reduction_summaries[case.id] = [], {}
                settings = next(s for s in plan["references"] if s["id"] == "refined")
                for i, local in enumerate(ref.local_cases(case)):
                    current_attempt = "reduction_" + case.graph.cells[i].cell_id
                    print(f"{case.id}: {current_attempt}", flush=True)
                    module = ref.channel if i in case.channel_cells else ref.ionic
                    budget = module.Budget(
                        deadline=deadline, max_calls=plan["resources"]["max_rhs_calls_per_attempt"]
                    )
                    arrays, item = module.integrate_reference(local, settings, budget=budget)
                    budget.check()
                    observed = module.sample_record(local, arrays, settings["method"], samples)
                    arrays = arrays | {"sample_times_s": samples, "sample_state": observed}
                    components.append(observed)
                    item = {"definition": local.definition(), "statistics": item}
                    artifacts.arrays(f"{case.id}/{current_attempt}.npz", arrays)
                    artifacts.json(f"{case.id}/{current_attempt}.json", item)
                    reduction_summaries[case.id][current_attempt] = item
                reduction = checks.reduction_comparison(
                    definition,
                    records["refined"]["sample_state"],
                    components,
                    plan["trajectory_limits"],
                )
                analyses[case.id]["independent_cell_reduction"] = reduction
                analyses[case.id]["references_pass"] &= reduction["pass"]
            artifacts.json(f"{case.id}/analysis.json", analyses[case.id])
            summaries[case.id] = checks.final_summary(definition, records["refined"], stats)
            print(f"{case.id}: references_pass={analyses[case.id]['references_pass']}", flush=True)
            checks.require(
                analyses[case.id]["references_pass"],
                "Reference qualification failed; stop without extending the plan",
            )
        checks.require(monotonic() < deadline, "Scientific session wall-time budget exhausted")
        checks.require(
            all(sha((ROOT / name).read_bytes()) == digest for name, digest in hashes.items()),
            "Captured source changed during session",
        )
        data.load_panel()  # Recheck production and inherited dependencies at closeout.
        receipt = {
            **checks.select_candidate(analyses, plan),
            "scope": plan["scope"],
            "seconds": monotonic() - started,
            "completed_cases": list(analyses),
            "cases": summaries,
            "reductions": reduction_summaries,
            "protocol_sha256": data.PANEL_SHA256,
            "source_sha256": hashes,
            "files_sha256": dict(artifacts.hashes),
            "artifact_bytes_before_receipt": artifacts.used,
            "production_change": False,
            "production_version": "0.12.0",
            "rejected_candidates": sum(
                s["status"] == "rejected"
                for item in summaries.values()
                for s in item["attempts"].values()
            ),
            "gpu_qualification": "not_performed",
            "biological_acceptance": "not_assessable",
        }
        artifacts.json("verification.json", receipt, closing=True)
        print(
            json.dumps(
                {
                    "status": receipt["status"],
                    "selected_dt_s": receipt["selected_dt_s"],
                    "cases": len(analyses),
                    "seconds": receipt["seconds"],
                    "artifact_bytes": artifacts.used,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return receipt
    except Exception as error:
        artifacts.json(
            "failure.json",
            {
                "status": "stopped",
                "case": current_case,
                "attempt": current_attempt,
                "error_type": type(error).__name__,
                "reason": str(error),
                "completed_cases": list(analyses),
                "files_sha256": dict(artifacts.hashes),
                "seconds": monotonic() - started,
                "production_change": False,
            },
            closing=True,
        )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="A new session directory")
    args = parser.parse_args()
    return 0 if run(args.output)["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
