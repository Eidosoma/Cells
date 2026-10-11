"""D085 resource-only continuation; original inputs, failure and completed rows stay frozen."""

import argparse
import copy
import importlib
import json
import math
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "response_panel"))
prior = importlib.import_module("refined_response_context")
old_job = importlib.import_module("refined_response_job")
c, audit = prior.c, prior.audit
FAILED = c.ROOT / "runs/ref-003e1-response-refined-2026-09-13/capture-01"
PLAN = HERE / "trace_resume_plan.json"
PRESERVATION = c.ROOT / "reports/ref-003e1-trace-resume-preservation.json"
PRELAUNCH = c.ROOT / "reports/ref-003e1-trace-resume-prelaunch.json"
PROBE = c.ROOT / "reports/ref-003e1-trace-resume-resource-probe.json"
REUSE = c.ROOT / "reports/ref-003e1-trace-resume-reuse-check.json"
NEW_FILES = {
    "trace_resume_plan.json",
    "trace_resume_context.py",
    "trace_resume_probe.py",
    "trace_resume_check.py",
    "trace_resume_job.py",
    "test_trace_resume.py",
}
ANCHORS = {
    "failure.json": "12cddb240fca4a6831bd29663c6ed7ea8b3572fdc159931f6ac84acd912ac65f",
    "cells-failure.json": "81ed94ba37389ba9f68987f181c76552225bb42ee202015062305b5a64bbfc7f",
    "registration.json": "209586bf9f03897d71db4192f1a9fb0883b56c47756949978b6e2fc888de928d",
    "native.json": "df021ee24f82a282aa20389461d6b1d825e4a2039a6e8155a0d451b7d0277e02",
}
EXPECTED = {
    "schema": "cells.betse_trace_resume_plan@1",
    "amendment": "raise_only_eight_640_step_Cells_trace_caps",
    "max_trace_bytes": 67108864,
    "reused_native_runs": 16,
    "reused_cells_runs": 26,
    "new_native_runs": 0,
    "new_cells_runs": 22,
    "new_cells_steps": 8480,
    "new_eager_steps": 4000,
    "new_jit_steps": 4480,
    "stage_timeout_seconds": {"cells": 6600, "comparison": 300},
    "total_timeout_seconds": 7200,
    "max_artifact_bytes": 1073741824,
    "max_worker_file_bytes": 67108864,
    "cpu_affinity": "0-3",
    "automatic_polling": False,
    "automatic_retry": False,
    "automatic_expansion": False,
    "trajectory_qualified": False,
    "native_convergence_qualified": False,
    "forcing_convergence_qualified": False,
    "biology_validated": False,
    "gpu_tested": False,
}


def validate_plan(p):
    c.require(
        json.dumps(p, sort_keys=True, allow_nan=False) == json.dumps(EXPECTED, sort_keys=True),
        "Unregistered trace continuation scope/resources",
    )


def previous():
    return c.read(FAILED / "registration.json")


def changed_ids(r):
    return [
        row["id"]
        for row in r["cells_rows"]
        if row["hold_step_s"] == 0.00000625 and row["subdivision"] == 4
    ]


def definitions(r):
    result = copy.deepcopy(r["cells_definitions"])
    for identifier in changed_ids(r):
        c.require(
            result[identifier]["execution"]["max_trace_bytes"] == 16777216,
            "Unexpected original trace budget",
        )
        result[identifier]["execution"]["max_trace_bytes"] = EXPECTED["max_trace_bytes"]
    return result


def reuse_records(r):
    return {
        row["id"]: {
            "path": "cells/" + row["id"] + "/result.json",
            "sha256": c.sha(FAILED / "cells" / row["id"] / "result.json"),
        }
        for row in r["cells_rows"][:26]
    }


def expected_failed_paths(r):
    paths = {
        "registration.json",
        "sources.zip",
        "started.json",
        "native.json",
        "native.log",
        "cells.log",
        "cells-failure.json",
        "matplotlib-cache/fontlist-v3.11.0.json",
    }
    common = {
        "started.json",
        "core.json",
        "final-state.json",
        "final-metadata.json",
        "result.json",
        "checks.json",
        "native.yaml",
        "INITS/world_1.betse.gz",
        "SIMS/sim_1.betse.gz",
    }
    observed = {"dynamics.json", "loop-entry.json", "loop-metadata.json", "events.json"}
    for row in r["native_rows"]:
        for mode in r["plan"]["native_modes"]:
            paths |= {
                f"native/{prior.prior.key(row)}/{mode}/{n}"
                for n in common | (observed if mode == "observed" else set())
            }
    paths |= {f"cells-started/{k:02d}.json" for k in range(27)}
    paths |= {entry["path"] for entry in reuse_records(r).values()}
    return paths


def authenticate():
    c.require(
        all(c.sha(FAILED / n) == h for n, h in ANCHORS.items()),
        "Original resource-failure anchor changed",
    )
    r, closed = previous(), c.read(FAILED / "failure.json")
    actual, expected = audit.packet_hashes(FAILED), expected_failed_paths(r)
    c.require(
        closed["status"] == "failed_not_qualified"
        and closed["stage"] == "cells"
        and closed["trajectory_qualified"] is False
        and closed["automatic_retry"] is False
        and set(actual) == expected | audit.OPERATIONAL | {"failure.json"}
        and set(closed["files_sha256"]) == expected
        and all(actual[n] == h for n, h in closed["files_sha256"].items()),
        "Original failure payload coverage/hash differs",
    )
    error = c.read(FAILED / "cells-failure.json")
    c.require(
        error["stage"] == "cells"
        and "ConfigError: Estimated trace working storage exceeds max_trace_bytes"
        in error["traceback"]
        and "_trace_budget" in error["traceback"],
        "Original failure cause differs",
    )
    prior.validate_registration(r)
    old_job.capsule(FAILED, r)
    for k, row in enumerate(r["cells_rows"][:27]):
        c.require(
            c.read(FAILED / f"cells-started/{k:02d}.json")["row"] == row,
            "Original started-row sequence differs",
        )
    for row in r["cells_rows"][:26]:
        record = c.read(FAILED / "cells" / row["id"] / "result.json")
        c.require(
            record["id"] == row["id"]
            and record["definition"] == r["cells_definitions"][row["id"]]
            and record["final_step_index"] == prior.count(row["hold_step_s"]) * row["subdivision"],
            "Completed Cells row identity differs",
        )
    nw = c.read(FAILED / "native.json")
    c.require(
        nw["status"] == "capture_controls_pass_pending_comparison"
        and nw["registration_sha256"] == ANCHORS["registration.json"]
        and nw["sources"] == r["sources"]
        and nw["warnings"] == []
        and nw["engine"] == "actual_betse_full_sim_loop"
        and len(nw["results"]) == 16,
        "Retained native worker provenance differs",
    )
    return r


def sources():
    return previous()["sources"] | {
        "response_resume/" + n: c.sha(HERE / n) for n in sorted(NEW_FILES)
    }


def preserve():
    authenticate()
    pre = c.read(prior.PRELAUNCH)
    software_registration = c.read((c.ROOT / pre["test_receipt"]).parent / "registration.json")
    names = (
        set(audit.files.worktree())
        | set(c.read(prior.PRESERVATION)["baseline_sha256"])
        | set(pre["new_files_sha256_before_prelaunch"])
        | set(software_registration["files_sha256"])
        | {str(prior.PRELAUNCH.relative_to(c.ROOT))}
    )
    owned = {str((HERE / n).relative_to(c.ROOT)) for n in NEW_FILES}
    baseline = {n: c.sha(c.ROOT / n) for n in sorted(names - owned)}
    c.write(
        PRESERVATION,
        {
            "schema": "cells.betse_trace_resume_preservation@1",
            "created_utc": datetime.now(UTC).isoformat(),
            "failure_anchors": ANCHORS,
            "baseline_sha256": baseline,
            "failed_files_sha256": audit.packet_hashes(FAILED),
        },
    )
    print(
        json.dumps(
            {
                "status": "preserved",
                "baseline_files": len(baseline),
                "failed_files": len(audit.packet_hashes(FAILED)),
            }
        )
    )


def preservation_check():
    authenticate()
    saved = c.read(PRESERVATION)
    c.require(
        saved["failure_anchors"] == ANCHORS
        and saved["failed_files_sha256"] == audit.packet_hashes(FAILED),
        "Original resource-failed attempt changed",
    )
    changed = {
        n: {"before": h, "after": c.sha(c.ROOT / n)}
        for n, h in saved["baseline_sha256"].items()
        if c.sha(c.ROOT / n) != h
    }
    c.require(set(changed) <= prior.legacy.edits.ALLOWED_EDITS, "Unexpected pre-existing edit")
    return {
        "baseline_files": len(saved["baseline_sha256"]),
        "unchanged_baseline_files": len(saved["baseline_sha256"]) - len(changed),
        "changed_documents": changed,
        "resource_failure_files_unchanged": len(saved["failed_files_sha256"]),
        "production_modules_unchanged": 51,
        "accepted_implementation_files_unchanged": 352,
    }


def inputs():
    validate_plan(c.read(PLAN))
    r = previous()
    keys = (
        "plan",
        "native_rows",
        "cells_rows",
        "common_times_s",
        "cells_export_shapes",
        "criteria",
        "upstream",
        "base_protocol",
        "geometry",
        "settings",
        "cells_runtime",
    )
    return {k: r[k] for k in keys} | {
        "continuation_plan": c.read(PLAN),
        "cells_definitions": definitions(r),
        "new_cells_rows": r["cells_rows"][26:],
        "reused_cells": reuse_records(r),
        "failed_capture_anchors": ANCHORS,
        "reused_native_worker_sha256": ANCHORS["native.json"],
    }


def resources():
    r = previous()
    completed = [
        (row, c.read(FAILED / "cells" / row["id"] / "result.json")) for row in r["cells_rows"][:26]
    ]
    rates = {
        backend: max(
            record["timings"]["total_run_seconds"] / record["final_step_index"]
            for row, record in completed
            if row["backend"] == backend
        )
        for backend in r["plan"]["cells_backends"]
    }
    seconds = math.ceil(1.5 * (4000 * rates["jax_eager"] + 4480 * rates["jax_jit"]) + 120)
    retained_size = old_job.budget.artifact_bytes(FAILED)
    bytes_per_step = max(
        (FAILED / "cells" / row["id"] / "result.json").stat().st_size / record["final_step_index"]
        for row, record in completed
    )
    artifact_estimate = math.ceil(retained_size + 1.5 * 8480 * bytes_per_step + 32 * 1024**2)
    largest_estimate = math.ceil(1.5 * 640 * bytes_per_step)
    c.require(
        seconds < EXPECTED["stage_timeout_seconds"]["cells"]
        and seconds + 300 + 60 < EXPECTED["total_timeout_seconds"]
        and artifact_estimate < EXPECTED["max_artifact_bytes"]
        and largest_estimate < EXPECTED["max_worker_file_bytes"],
        "Continuation CPU/artifact estimate exceeds cap",
    )
    return {
        "basis": (
            "slowest measured D084 per-step eager/JIT cost applied only to "
            "unexecuted rows plus allowances"
        ),
        "slowest_seconds_per_step": rates,
        "estimated_cells_seconds_with_allowances": seconds,
        "comparison_allowance_seconds": 300,
        "retained_artifact_bytes": retained_size,
        "estimated_combined_artifact_bytes_with_allowances": artifact_estimate,
        "estimated_largest_worker_file_bytes_with_allowances": largest_estimate,
        "peak_RAM_measured": False,
        "new_steps_by_backend": {"jax_eager": 4000, "jax_jit": 4480},
    }


def validate_registration(r):
    expected, pre = inputs(), c.read(PRELAUNCH)
    validate_plan(r["continuation_plan"])
    c.require(
        r["schema"] == "cells.betse_trace_resume_registration@1"
        and all(r[k] == v for k, v in expected.items())
        and r["sources"] == pre["sources"] == sources()
        and len(r["sources"]) == 112
        and r["prelaunch_sha256"] == c.sha(PRELAUNCH)
        and r["preservation_sha256"] == pre["preservation_sha256"] == c.sha(PRESERVATION)
        and pre["status"] == "resource_and_reuse_preflight_pass_not_continuation_execution"
        and all(c.sha(c.HERE / n) == h for n, h in r["sources"].items()),
        "Continuation registration/input/source differs",
    )
    for n, h in pre["files_sha256"].items():
        c.require(c.sha(c.ROOT / n) == h, "Frozen continuation prelaunch input changed: " + n)
    preservation_check()


def prelaunch(tests, expected):
    preserved = preservation_check()
    counts, modules = audit.receipts.test_counts(tests)
    c.require(
        counts["tests"] == expected
        and modules == {"validation.betse.response_resume.test_trace_resume"},
        "Wrong continuation preflight tests",
    )
    probe = importlib.import_module("trace_resume_probe")
    check = importlib.import_module("trace_resume_check")
    probe.validate(c.read(PROBE), inputs())
    check.validate_reuse(c.read(REUSE), inputs())
    quality = {}
    for name, args in (("lint", ["check"]), ("format", ["format", "--check"])):
        quality[name] = subprocess.check_output(
            [str(c.ROOT / ".venv/bin/ruff"), *args, "src", "tests", "scripts", "validation"],
            cwd=c.ROOT,
            text=True,
            timeout=20,
        ).strip()
    baseline = c.read(PRESERVATION)["baseline_sha256"]
    frozen = {n: h for n, h in audit.files.worktree().items() if n not in baseline}
    frozen[str(tests.relative_to(c.ROOT))] = c.sha(tests)
    c.write(
        PRELAUNCH,
        {
            "schema": "cells.betse_trace_resume_prelaunch@1",
            "status": "resource_and_reuse_preflight_pass_not_continuation_execution",
            "created_utc": datetime.now(UTC).isoformat(),
            "sources": sources(),
            "tests": counts,
            "quality": quality,
            "resources": resources(),
            "preservation_sha256": c.sha(PRESERVATION),
            "files_sha256": frozen,
            "resource_probe_sha256": c.sha(PROBE),
            "reuse_check_sha256": c.sha(REUSE),
            "trajectory_run": False,
            **preserved,
        },
    )
    print(
        json.dumps(
            {
                "status": "prelaunch_pass",
                "tests": counts,
                "quality": quality,
                "resources": resources(),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preserve", "prelaunch"))
    parser.add_argument("--tests", type=Path)
    parser.add_argument("--expected-tests", type=int)
    args = parser.parse_args()
    if args.action == "preserve":
        preserve()
    else:
        prelaunch(args.tests.resolve(), args.expected_tests)
