"""D077: frozen inputs/resources for the expanded, still no-op, full-SIM bridge."""

import argparse
import copy
import json
import math
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import cluster_closeout as files
import contact as c
import full_loop_audit_context as previous
import full_loop_bridge_context as pilot
import phase_bridge_context as edits
import profile_bridge_context as profiles
import trajectory_context as trajectory
import trajectory_evidence as evidence

SESSION = c.ROOT / "runs/ref-003e0-loop-audit-2026-09-12/audit-01"
ANCHORS = {
    "completion.json": "3167c314451fb4447d805d587b1bd7433544527c432d23b59c0c1f84113544a3",
    "registration.json": "7ada2470bf06ec90a27b9a1dcc3bf52e6195b2bbd186b39d6f94ea6a85c43561",
    "sources.zip": "3673948df0ce8c915391c6e85b2bcb8bcb51be1ef9e8f0a68847c2bcef5aec76",
    "launch.json": "c09048e849952bf10f83a1042b4eec0328dab326c3f1e52f4cd868ab6fba323d",
}
PRIOR_PRELAUNCH_SHA = "7badffd0704fcceb0fced8f093fd43df4539199a869c19fa5028c77d7df6a535"
PLAN = c.HERE / "expanded_bridge_plan.json"
PRESERVATION = c.ROOT / "reports/ref-003e0-expanded-preservation.json"
PRELAUNCH = c.ROOT / "reports/ref-003e0-expanded-prelaunch.json"
FILES = {
    "expanded_bridge_context.py",
    "expanded_bridge_check.py",
    "expanded_bridge.py",
    "expanded_bridge_plan.json",
    "test_expanded_bridge.py",
}
MODES = pilot.MODES
VARIANTS = copy.deepcopy(profiles.VARIANTS)
EXPECTED_PLAN = {
    "schema": "cells.betse_expanded_bridge_plan@1",
    "pilot_closeout_sha256": ANCHORS["completion.json"],
    "case_ids": ["passive", "blocked"],
    "constant_profiles": ["source_constants", "matched_constants"],
    "dt_s": [0.000025, 0.0000125, 0.00000625],
    "variants": VARIANTS,
    "modes": list(MODES),
    "duration_s": 0.001,
    "native_runs": 72,
    "observed_steps": 3360,
    "enabled_target_dispatches": 1120,
    "observer_pairs": 36,
    "variant_comparisons": 24,
    "pilot_overlap_runs": 12,
    "preparation": "fresh_seed_and_SIM_init_core_then_one_native_run_sim_core",
    "equality": "exact_values_shapes_dtypes_bytes_and_legacy_trace_values",
    "worker_timeout_seconds": 600,
    "total_timeout_seconds": 660,
    "max_artifact_bytes": 2147483648,
    "max_worker_file_bytes": 67108864,
    "cpu_affinity": "0-3",
    "cells_runs": 0,
    "independent_audit": "separate_user_requested_saved_data_step",
    "automatic_retry": False,
    "expanded_bridge_qualified": False,
    "nonzero_intervention": False,
    "biology_validated": False,
    "gpu_tested": False,
}


def authenticate():
    c.require(c.sha(previous.PRELAUNCH) == PRIOR_PRELAUNCH_SHA, "D076 prelaunch changed")
    prelaunch = c.read(previous.PRELAUNCH)
    for name, digest in prelaunch["new_files_sha256_before_prelaunch"].items():
        c.require(c.sha(c.ROOT / name) == digest, "Frozen D076 file changed: " + name)
    for name, digest in ANCHORS.items():
        c.require(c.sha(SESSION / name) == digest, "D076 audit anchor changed")
    completed = c.read(SESSION / "completion.json")
    c.require(
        completed["status"] == "pass"
        and completed["pilot_trajectory_qualified"] is True
        and completed["expanded_bridge_qualified"] is False
        and completed["tests"] == {"tests": 165, "failures": 0, "errors": 0, "skipped": 0},
        "Narrow pilot lacks successful audit/regression closeout",
    )
    for name, digest in completed["files_sha256"].items():
        c.require(c.sha(SESSION / name) == digest, "D076 audit payload changed")
    c.require(
        set(previous.packet_hashes(SESSION))
        == set(completed["files_sha256"])
        | {"completion.json", "launch.json", "runner.stdout.log", "runner.stderr.log"},
        "D076 audit coverage changed",
    )
    for name, digest in c.read(SESSION / "registration.json")["sources"].items():
        c.require(c.sha(c.HERE / name) == digest, "Audited adapter source changed: " + name)
    return previous.authenticate()


def validate_plan(plan):
    c.require(
        json.dumps(plan, sort_keys=True, allow_nan=False)
        == json.dumps(EXPECTED_PLAN, sort_keys=True, allow_nan=False),
        "Unregistered expanded bridge scope/resources",
    )


def rows(plan):
    validate_plan(plan)
    cases = evidence.trusted_registration()["protocol"]["cases"]
    c.require([case["id"] for case in cases] == plan["case_ids"], "Wrong retained cases")
    return [
        {"case": copy.deepcopy(case), "profile": profile, "dt_s": dt, "variant": variant}
        for case in cases
        for profile in plan["constant_profiles"]
        for dt in plan["dt_s"]
        for variant in VARIANTS
    ]


def validate_row(row):
    c.require(row in rows(c.read(PLAN)), "Unregistered expanded row")


def group_key(row):
    return trajectory.key(row["case"]["id"], row["profile"], row["dt_s"])


def pilot_row(row):
    return row | {"profile": "matched_constants", "dt_s": 0.000025}


def pilot_path(row, mode):
    return previous.SESSION / "native" / pilot.key(pilot_row(row)) / mode


def overlap(row):
    return row["profile"] == "matched_constants" and row["dt_s"] == 0.000025


def preserve():
    accepted = authenticate()
    owned = {"validation/betse/" + name for name in FILES}
    baseline = {n: h for n, h in files.worktree().items() if n not in owned}
    c.write(
        PRESERVATION,
        {
            "schema": "cells.betse_expanded_bridge_preservation@1",
            "created_utc": datetime.now(UTC).isoformat(),
            "baseline_sha256": baseline,
            "audit_files_sha256": previous.packet_hashes(SESSION),
            "pilot_files_sha256": previous.packet_hashes(),
            "accepted_sources": accepted["implementation_files_sha256"],
        },
    )
    print(json.dumps({"status": "preserved", "baseline_files": len(baseline)}))


def preservation_check():
    accepted = authenticate()
    saved = c.read(PRESERVATION)
    c.require(saved["accepted_sources"] == accepted["implementation_files_sha256"], "Cells changed")
    c.require(
        saved["audit_files_sha256"] == previous.packet_hashes(SESSION), "Audit packet changed"
    )
    c.require(saved["pilot_files_sha256"] == previous.packet_hashes(), "Pilot packet changed")
    changed = {
        n: {"before": h, "after": c.sha(c.ROOT / n)}
        for n, h in saved["baseline_sha256"].items()
        if c.sha(c.ROOT / n) != h
    }
    c.require(set(changed) <= edits.ALLOWED_EDITS, "Unexpected pre-existing edit")
    return {
        "baseline_files": len(saved["baseline_sha256"]),
        "unchanged_baseline_files": len(saved["baseline_sha256"]) - len(changed),
        "changed_documents": changed,
        "pilot_files_unchanged": len(saved["pilot_files_sha256"]),
        "audit_files_unchanged": len(saved["audit_files_sha256"]),
        "accepted_implementation_files_unchanged": len(accepted["implementation_files_sha256"]),
        "production_modules_unchanged": sum(
            n.startswith("src/") and n.endswith(".py")
            for n in accepted["implementation_files_sha256"]
        ),
    }


def resource_estimate(plan):
    validate_plan(plan)
    estimates = []
    # Scale EVERY pilot row file with the timestep count, even static files.
    # A further factor two covers numeric text length, compression and schema growth.
    for row in rows(plan):
        factor = 2 * round(0.000025 / row["dt_s"])
        for mode in MODES:
            estimates.extend(
                factor * p.stat().st_size for p in pilot_path(row, mode).rglob("*") if p.is_file()
            )
    estimated = sum(estimates) + 16 * 1024 * 1024
    prior = c.read(previous.SESSION / "capture.json")
    linear = prior["elapsed_seconds"] * plan["observed_steps"] / prior["observed_steps"]
    allowed = math.ceil(1.5 * linear)
    free = shutil.disk_usage(c.ROOT).free
    c.require(estimated < plan["max_artifact_bytes"], "Expanded artifact estimate exceeds cap")
    c.require(
        max(estimates) < plan["max_worker_file_bytes"], "Expanded single-file estimate exceeds cap"
    )
    c.require(allowed < plan["worker_timeout_seconds"], "Expanded time estimate exceeds cap")
    c.require(free > 2 * plan["max_artifact_bytes"], "Insufficient free disk headroom")
    return {
        "basis": "actual D075 file sizes and runtime; conservative extrapolation, not a benchmark",
        "estimated_panel_bytes_with_allowances": estimated,
        "estimated_largest_worker_file_bytes": max(estimates),
        "pilot_seconds": prior["elapsed_seconds"],
        "step_scaled_seconds": linear,
        "seconds_with_50_percent_allowance": allowed,
        "free_disk_bytes": free,
        "max_artifact_bytes": plan["max_artifact_bytes"],
        "panel_limit_enforcement": "between rows and at completion; not a hard filesystem quota",
        "worker_file_limit_enforcement": "OS RLIMIT_FSIZE per regular file",
    }


def prelaunch(tests, expected):
    plan = c.read(PLAN)
    for row in rows(plan):
        profiles.mapping(row)
    preserved = preservation_check()
    counts, modules = previous.test_counts(tests)
    c.require(
        counts["tests"] == expected and modules == {"validation.betse.test_expanded_bridge"},
        "Wrong expanded preflight tests",
    )
    quality = {}
    for name, args in (("lint", ["check"]), ("format", ["format", "--check"])):
        quality[name] = subprocess.check_output(
            [str(c.ROOT / ".venv/bin/ruff"), *args, "src", "tests", "scripts", "validation"],
            cwd=c.ROOT,
            text=True,
        ).strip()
    baseline = c.read(PRESERVATION)["baseline_sha256"]
    result = {
        "schema": "cells.betse_expanded_bridge_prelaunch@1",
        "status": "adapter_checks_pass_not_native_execution",
        "checked_utc": datetime.now(UTC).isoformat(),
        "pilot_closeout_sha256": ANCHORS["completion.json"],
        "plan_sha256": c.sha(PLAN),
        "preservation_sha256": c.sha(PRESERVATION),
        "test_receipt": str(tests.relative_to(c.ROOT)),
        "test_receipt_sha256": c.sha(tests),
        "tests": counts,
        "quality": quality,
        "sources": trajectory.sources(),
        "resources": resource_estimate(plan),
        "new_files_sha256_before_prelaunch": {
            n: h for n, h in files.worktree().items() if n not in baseline
        },
        "trajectory_run": False,
        "trajectory_qualified": False,
        **preserved,
    }
    c.write(PRELAUNCH, result)
    print(
        json.dumps({"status": result["status"], "tests": counts, "resources": result["resources"]})
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preserve", "prelaunch"))
    parser.add_argument("--tests", type=Path)
    parser.add_argument("--expected-tests", type=int)
    args = parser.parse_args()
    if args.command == "preserve":
        preserve()
    else:
        prelaunch(args.tests.resolve(), args.expected_tests)
