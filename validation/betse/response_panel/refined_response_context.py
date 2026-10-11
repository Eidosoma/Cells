"""D084: source-bound finer response inputs; old rejection and preflight stay frozen."""

import argparse
import importlib
import json
import math
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "response_refinement"))
prior = importlib.import_module("refined_dispatch_context")
dispatch_job = importlib.import_module("refined_dispatch_job")
c, held, audit = prior.c, prior.held, prior.audit_context
legacy = audit.prior
DISPATCH = c.ROOT / "runs/ref-003e1-refined-dispatch-2026-09-13/preflight-01"
COARSE = audit.SESSION
ANCHORS = {
    "completion.json": "250bbeb7c85f9401a6a36078c87c19e944236dd23d900043613b59c64593ca69",
    "registration.json": "f51386fe793ad06ba76cbaa46d5d3d4fbbb951cedfbe5cd37dcc6d558ccb1f4b",
    "sources.zip": "12790c5d045532fb085d7f2dfa965757fc0f651240b16cac4667dc942de1e888",
    "worker.json": "855f07b345be3e715968ffd5a55e1da9a673e47f1792ac124a7852e091a12936",
}
PLAN = HERE / "refined_response_plan.json"
PRESERVATION = c.ROOT / "reports/ref-003e1-refined-response-preservation.json"
PRELAUNCH = c.ROOT / "reports/ref-003e1-refined-response-prelaunch.json"
NEW_FILES = {
    "refined_response_plan.json",
    "refined_response_context.py",
    "refined_response_native.py",
    "refined_response_cells_check.py",
    "refined_response_check.py",
    "refined_response_job.py",
    "test_refined_response.py",
    "test_refined_response_check.py",
}
EXPECTED = {
    "schema": "cells.betse_refined_response_plan@1",
    "hold_steps_s": [0.0000125, 0.00000625],
    "retained_hold_step_s": 0.000025,
    "conditions": ["baseline", "zero_amplitude", "static_blocked", "suppression_recovery"],
    "constant_profile": "matched_constants",
    "duration_s": 0.001,
    "cells_subdivisions": [1, 2, 4],
    "cells_backends": ["jax_eager", "jax_jit"],
    "native_modes": ["observed", "unobserved"],
    "native_runs": 16,
    "cells_runs": 48,
    "observed_native_steps": 960,
    "cells_steps_total": 13440,
    "criteria_source": "validation/betse/trajectory_refinement_protocol.json",
    "control_atol": 2e-14,
    "terminal_rate_policy": "validate_Cells_last_hold_but_no_invented_native_final_RHS",
    "required_gates": (
        "internal_laws_all_h_fixed_input_solver_all_h_backend_all_h_cross_engine_finest_h"
    ),
    "cross_failure_policy": (
        "retain_all_coarse_and_intermediate_rejections_report_required_gates_separately"
    ),
    "across_hold_policy": (
        "common_41_boundaries_diagnostic_only_native_joint_solver_and_resampling_Cells_input_sensitivity"
    ),
    "stage_timeout_seconds": {"native": 300, "cells": 10800, "comparison": 300},
    "total_timeout_seconds": 11700,
    "max_artifact_bytes": 1073741824,
    "max_worker_file_bytes": 67108864,
    "cpu_affinity": "0-3",
    "automatic_polling": False,
    "automatic_retry": False,
    "automatic_expansion": False,
    "native_convergence_qualified": False,
    "forcing_convergence_qualified": False,
    "trajectory_qualified": False,
    "biology_validated": False,
    "gpu_tested": False,
}


def validate_plan(p):
    c.require(
        json.dumps(p, sort_keys=True, allow_nan=False) == json.dumps(EXPECTED, sort_keys=True),
        "Unregistered finer response scope/resources",
    )


def count(h):
    c.require(type(h) is float and h in (0.000025, 0.0000125, 0.00000625), "Unknown hold")
    return held.law.clock_parameters(c.read(held.law.PLAN), h)[0]


def native_rows(p):
    validate_plan(p)
    return prior.rows(c.read(prior.PLAN))


def identifier(h, condition, backend, factor):
    return f"{h:.8f}/{condition}/{backend}/subdivision-{factor}"


def cells_rows(p):
    validate_plan(p)
    return [
        {
            "hold_step_s": h,
            "condition": condition,
            "backend": backend,
            "subdivision": factor,
            "id": identifier(h, condition, backend, factor),
        }
        for h in p["hold_steps_s"]
        for condition in p["conditions"]
        for backend in p["cells_backends"]
        for factor in p["cells_subdivisions"]
    ]


def definitions(p):
    return {
        r["id"]: held.cells_definition(
            c.read(held.PLAN), r["condition"], r["hold_step_s"], r["subdivision"], r["backend"]
        )
        for r in cells_rows(p)
    }


def common_times(p):
    validate_plan(p)
    return {
        f"{h:.8f}": [k * h for k in range(count(h))] + [p["duration_s"]] for h in p["hold_steps_s"]
    }


def panel_view(r, h):
    """In-memory selection of registered rows, never a replacement registration."""
    c.require(h in r["plan"]["hold_steps_s"], "Unregistered hold selection")
    rows = [row for row in r["cells_rows"] if row["hold_step_s"] == h]
    return r | {
        "plan": r["plan"] | {"hold_step_s": h},
        "native_rows": [row for row in r["native_rows"] if row["dt_s"] == h],
        "cells_rows": rows,
        "cells_definitions": {row["id"]: r["cells_definitions"][row["id"]] for row in rows},
        "common_times_s": r["common_times_s"][f"{h:.8f}"],
    }


def prepared(row):
    return {
        n: c.read(DISPATCH / prior.key(row) / (n + ".json")) for n in ("core", "ready", "metadata")
    }


overlap_path = legacy.overlap_path
export_shapes = legacy.export_shapes


def sources():
    return c.read(DISPATCH / "registration.json")["sources"] | {
        "response_panel/" + n: c.sha(HERE / n) for n in sorted(NEW_FILES)
    }


def authenticate():
    c.require(
        all(c.sha(DISPATCH / n) == h for n, h in ANCHORS.items()), "D083 dispatch anchor changed"
    )
    result = c.read(DISPATCH / "completion.json")
    actual = audit.packet_hashes(DISPATCH)
    c.require(
        result["status"] == "refined_dispatch_checks_pass_not_response_qualification"
        and result["event_dispatch_calls"] == 960
        and result["integration_calls"] == 0
        and result["trajectory_qualified"] is False
        and set(actual) == set(result["files_sha256"]) | audit.OPERATIONAL | {"completion.json"}
        and all(actual[n] == h for n, h in result["files_sha256"].items()),
        "D083 preflight verdict or payload changed",
    )
    registered = c.read(DISPATCH / "registration.json")
    dispatch_job.validate_registration(registered)
    prior.audit_job.capsule(DISPATCH, registered)
    dispatch_job.validate_worker(c.read(DISPATCH / "worker.json"), registered, DISPATCH)
    return prior.preservation_check()


def preserve():
    authenticate()
    pre = c.read(prior.PRELAUNCH)
    names = (
        set(audit.files.worktree())
        | set(c.read(prior.PRESERVATION)["baseline_sha256"])
        | set(pre["new_files_sha256_before_prelaunch"])
        | {str(prior.PRELAUNCH.relative_to(c.ROOT))}
    )
    owned = {str((HERE / n).relative_to(c.ROOT)) for n in NEW_FILES}
    baseline = {n: c.sha(c.ROOT / n) for n in sorted(names - owned)}
    c.write(
        PRESERVATION,
        {
            "schema": "cells.betse_refined_response_preservation@1",
            "created_utc": datetime.now(UTC).isoformat(),
            "dispatch_anchors": ANCHORS,
            "baseline_sha256": baseline,
            "dispatch_files_sha256": audit.packet_hashes(DISPATCH),
            "audit_files_sha256": audit.packet_hashes(prior.AUDIT),
            "capture_files_sha256": audit.packet_hashes(COARSE),
            "external_metadata_change": audit.EXTERNAL_METADATA,
        },
    )
    print(json.dumps({"status": "preserved", "baseline_files": len(baseline)}))


def preservation_check():
    preserved, saved = authenticate(), c.read(PRESERVATION)
    c.require(
        saved["dispatch_anchors"] == ANCHORS
        and saved["dispatch_files_sha256"] == audit.packet_hashes(DISPATCH)
        and saved["audit_files_sha256"] == audit.packet_hashes(prior.AUDIT)
        and saved["capture_files_sha256"] == audit.packet_hashes(COARSE)
        and saved["external_metadata_change"] == audit.EXTERNAL_METADATA,
        "Frozen finer-input or response evidence changed",
    )
    changed = {
        n: {"before": h, "after": c.sha(c.ROOT / n)}
        for n, h in saved["baseline_sha256"].items()
        if c.sha(c.ROOT / n) != h
    }
    c.require(set(changed) <= legacy.edits.ALLOWED_EDITS, "Unexpected pre-existing edit")
    return preserved | {
        "baseline_files": len(saved["baseline_sha256"]),
        "unchanged_baseline_files": len(saved["baseline_sha256"]) - len(changed),
        "changed_documents": changed,
        "refined_dispatch_files_unchanged": len(saved["dispatch_files_sha256"]),
    }


def resources(p):
    validate_plan(p)
    old = c.read(COARSE / "registration.json")
    records = [c.read(COARSE / "cells" / row["id"] / "result.json") for row in old["cells_rows"]]
    per_step = {
        backend: max(
            r["timings"]["total_run_seconds"] / r["final_step_index"]
            for row, r in zip(old["cells_rows"], records, strict=True)
            if row["backend"] == backend
        )
        for backend in p["cells_backends"]
    }
    estimates = {
        "native": math.ceil(1.5 * c.read(COARSE / "native.json")["elapsed_seconds"] * 6 + 60),
        "cells": math.ceil(1.5 * 6720 * sum(per_step.values()) + 120),
        "comparison": math.ceil(2 * c.read(COARSE / "comparison.json")["elapsed_seconds"] * 7 + 30),
    }
    sizes = [f.stat().st_size for f in COARSE.rglob("*") if f.is_file()]
    size, largest = math.ceil(1.5 * sum(sizes) * 6 + 16 * 1024**2), math.ceil(1.5 * max(sizes) * 4)
    c.require(
        all(estimates[k] < p["stage_timeout_seconds"][k] for k in estimates)
        and sum(estimates.values()) + 60 < p["total_timeout_seconds"]
        and size < p["max_artifact_bytes"]
        and largest < p["max_worker_file_bytes"],
        "Prospective response resources exceed cap",
    )
    return {
        "basis": (
            "D081 measured maximum eager/JIT seconds per accepted step and capture sizes; "
            "explicit scaling and allowances"
        ),
        "slowest_seconds_per_step": per_step,
        "accepted_steps_per_backend": 6720,
        "stage_seconds_with_allowances": estimates,
        "estimated_artifact_bytes_with_allowances": size,
        "estimated_largest_worker_file_bytes_with_allowances": largest,
        "peak_RAM_measured": False,
    }


def validate_registration(r):
    validate_plan(r["plan"])
    pre = c.read(PRELAUNCH)
    c.require(
        r["schema"] == "cells.betse_refined_response_registration@1"
        and r["plan"] == pre["plan"] == c.read(PLAN)
        and r["dispatch_anchors"] == ANCHORS
        and r["prelaunch_sha256"] == c.sha(PRELAUNCH)
        and r["preservation_sha256"] == pre["preservation_sha256"] == c.sha(PRESERVATION)
        and pre["status"] == "software_checks_pass_not_response_execution"
        and pre["test_receipt_sha256"] == c.sha(c.ROOT / pre["test_receipt"])
        and r["sources"] == pre["sources"] == sources()
        and len(r["sources"]) == 106
        and all(c.sha(c.HERE / n) == h for n, h in r["sources"].items()),
        "Refined response identity/source/tests changed",
    )
    for n, h in pre["new_files_sha256_before_prelaunch"].items():
        c.require(c.sha(c.ROOT / n) == h, "Frozen refined-response input changed: " + n)
    expected = legacy.evidence.trusted_registration()
    for k in ("base_protocol", "geometry", "settings", "cells_runtime", "upstream"):
        c.require(r[k] == expected[k], "Response physics/runtime differs: " + k)
    c.require(
        r["criteria"] == expected["protocol"] == c.read(c.ROOT / r["plan"]["criteria_source"])
        and r["native_rows"] == native_rows(r["plan"])
        and r["cells_rows"] == cells_rows(r["plan"])
        and r["cells_definitions"] == definitions(r["plan"])
        and r["common_times_s"] == common_times(r["plan"])
        and r["cells_export_shapes"] == export_shapes(),
        "Response tolerances/coverage/inputs differ",
    )
    preservation_check()


def prelaunch(tests, expected):
    preserved = preservation_check()
    plan = c.read(PLAN)
    counts, modules = audit.receipts.test_counts(tests)
    c.require(
        counts["tests"] == expected == 114
        and modules
        == {
            "validation.betse.response_panel.test_refined_response",
            "validation.betse.response_panel.test_refined_response_check",
        },
        "Wrong refined response software coverage",
    )
    software = importlib.import_module("refined_response_job")
    packet = tests.parent
    software.validate_software_registration(c.read(packet / "registration.json"), packet)
    closed = c.read(packet / "completion.json")
    actual = audit.packet_hashes(packet)
    c.require(
        tests.name == "regression.xml"
        and closed["status"] == "software_checks_pass_await_user_review_no_response_launch"
        and closed["tests"] == counts
        and closed["sources"] == sources()
        and closed["test_receipt_sha256"] == c.sha(tests)
        and closed["registration_sha256"] == c.sha(packet / "registration.json")
        and closed["trajectory_run"] is False
        and set(actual) == set(closed["files_sha256"]) | audit.OPERATIONAL | {"completion.json"}
        and all(actual[n] == h for n, h in closed["files_sha256"].items()),
        "Software closeout receipt differs",
    )
    quality = {}
    for name, args in (("lint", ["check"]), ("format", ["format", "--check"])):
        quality[name] = subprocess.check_output(
            [str(c.ROOT / ".venv/bin/ruff"), *args, "src", "tests", "scripts", "validation"],
            cwd=c.ROOT,
            text=True,
            timeout=20,
        ).strip()
    baseline = c.read(PRESERVATION)["baseline_sha256"]
    new = {n: h for n, h in audit.files.worktree().items() if n not in baseline}
    new[str(tests.relative_to(c.ROOT))] = c.sha(tests)
    new |= {str((packet / n).relative_to(c.ROOT)): h for n, h in actual.items()}
    result = {
        "schema": "cells.betse_refined_response_prelaunch@1",
        "status": "software_checks_pass_not_response_execution",
        "created_utc": datetime.now(UTC).isoformat(),
        "plan": plan,
        "sources": sources(),
        "dispatch_anchors": ANCHORS,
        "preservation_sha256": c.sha(PRESERVATION),
        "test_receipt": str(tests.relative_to(c.ROOT)),
        "test_receipt_sha256": c.sha(tests),
        "tests": counts,
        "quality": quality,
        "resources": resources(plan),
        "new_files_sha256_before_prelaunch": new,
        "trajectory_run": False,
        **preserved,
    }
    c.write(PRELAUNCH, result)
    print(json.dumps({k: result[k] for k in ("status", "tests", "quality", "resources")}))


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
