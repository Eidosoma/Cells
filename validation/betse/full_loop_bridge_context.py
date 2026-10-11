"""D075: a prospective, narrow full-SIM-loop pilot after the D074 preparation."""

import argparse
import copy
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import UTC, datetime

import cluster_closeout as files
import contact as c
import phase_bridge_context as phase
import profile_bridge_context as previous
import trajectory_context as trajectory
import trajectory_evidence as evidence

PRIOR = c.ROOT / "reports/ref-003e0-v2-handoff.json"
PRIOR_SHA = "64892978d762ab61f4047b98c5071e4831a295326366c3432f0c9b6839fdbfc5"
PLAN = c.HERE / "full_loop_bridge_plan.json"
PRESERVATION = c.ROOT / "reports/ref-003e0-loop-preservation.json"
PRELAUNCH = c.ROOT / "reports/ref-003e0-loop-prelaunch.json"
FILES = {
    "full_loop_bridge_context.py",
    "full_loop_bridge.py",
    "full_loop_bridge_check.py",
    "full_loop_bridge_plan.json",
    "full_loop_observer.py",
    "test_full_loop_bridge.py",
    "test_full_loop_observer.py",
}
VARIANTS = copy.deepcopy(previous.VARIANTS)
MODES = ("observed", "unobserved")
EXPECTED_PLAN = {
    "schema": "cells.betse_full_loop_bridge_plan@1",
    "prior_handoff_sha256": PRIOR_SHA,
    "scope": "matched-constant 25-us full-loop pilot; not the expanded bridge",
    "case_ids": ["passive", "blocked"],
    "variants": VARIANTS,
    "modes": list(MODES),
    "constant_profile": "matched_constants",
    "dt_s": 0.000025,
    "duration_s": 0.001,
    "native_runs": 12,
    "observed_steps": 240,
    "preparation": "fresh_seed_and_SIM_init_core_then_one_native_run_sim_core",
    "equality": "exact_values_shapes_dtypes_bytes_and_legacy_trace_values",
    "worker_timeout_seconds": 120,
    "total_timeout_seconds": 150,
    "max_artifact_bytes": 268435456,
    "max_worker_file_bytes": 33554432,
    "cpu_affinity": "0-3",
    "partial_evidence": "core_dynamics_loop_entry_then_metadata_and_failure_trace",
    "cells_runs": 0,
    "independent_audit": "separate_user_requested_saved_data_step",
    "automatic_retry": False,
    "expanded_bridge_qualified": False,
    "nonzero_intervention": False,
    "biology_validated": False,
    "gpu_tested": False,
}


def authenticate():
    c.require(c.sha(PRIOR) == PRIOR_SHA, "D074 handoff changed")
    prior = c.read(PRIOR)
    c.require(prior["status"] == "preparation_checks_pass", "D074 preparation did not pass")
    for name, digest in prior["new_files_sha256_before_handoff"].items():
        c.require(c.sha(c.ROOT / name) == digest, "Frozen D074 file changed: " + name)
    packet = c.ROOT / prior["native_attempt"]
    c.require(
        {str(p.relative_to(packet)): c.sha(p) for p in packet.rglob("*") if p.is_file()}
        == prior["native_attempt_files_sha256"],
        "D074 preparation packet changed",
    )
    return previous.authenticate()


def validate_plan(plan):
    c.require(
        json.dumps(plan, sort_keys=True, allow_nan=False)
        == json.dumps(EXPECTED_PLAN, sort_keys=True, allow_nan=False),
        "Unregistered full-loop pilot scope or resource amendment",
    )


def rows(plan):
    validate_plan(plan)
    cases = evidence.trusted_registration()["protocol"]["cases"]
    return [
        {
            "case": copy.deepcopy(case),
            "variant": variant,
            "profile": plan["constant_profile"],
            "dt_s": plan["dt_s"],
        }
        for case in cases
        for variant in VARIANTS
    ]


def key(row):
    return trajectory.key(row["case"]["id"], row["profile"], row["dt_s"]) + "/" + row["variant"]


def retained_path(row, mode="observed"):
    c.require(mode in MODES, "Unknown observation mode")
    return (
        evidence.SESSION
        / "native"
        / trajectory.key(row["case"]["id"], row["profile"], row["dt_s"])
        / mode
        / "result.json"
    )


def preserve():
    accepted = authenticate()
    owned = {"validation/betse/" + name for name in FILES}
    baseline = {name: digest for name, digest in files.worktree().items() if name not in owned}
    c.write(
        PRESERVATION,
        {
            "schema": "cells.betse_full_loop_bridge_preservation@1",
            "created_utc": datetime.now(UTC).isoformat(),
            "prior_handoff_sha256": PRIOR_SHA,
            "baseline_sha256": baseline,
            "accepted_sources": accepted["implementation_files_sha256"],
        },
    )
    print(json.dumps({"status": "preserved", "baseline_files": len(baseline)}))


def preservation_check():
    accepted = authenticate()
    saved = c.read(PRESERVATION)
    c.require(saved["accepted_sources"] == accepted["implementation_files_sha256"], "Cells changed")
    changed = {
        name: {"before": digest, "after": c.sha(c.ROOT / name)}
        for name, digest in saved["baseline_sha256"].items()
        if c.sha(c.ROOT / name) != digest
    }
    c.require(set(changed) <= phase.ALLOWED_EDITS, "Unexpected pre-existing file edit")
    return {
        "baseline_files": len(saved["baseline_sha256"]),
        "unchanged_baseline_files": len(saved["baseline_sha256"]) - len(changed),
        "changed_documents": changed,
        "accepted_implementation_files_unchanged": len(accepted["implementation_files_sha256"]),
        "production_modules_unchanged": sum(
            n.startswith("src/") and n.endswith(".py")
            for n in accepted["implementation_files_sha256"]
        ),
    }


def resource_estimate(plan):
    """Conservative sizing from retained records, not an observed pilot runtime."""
    validate_plan(plan)
    preparation = c.ROOT / c.read(PRIOR)["native_attempt"]
    state_bytes = max(
        len(json.dumps(c.read(p)["state"], indent=2).encode())
        for p in preparation.glob("preparation-*/ready.json")
    )
    native_bytes = max(retained_path(row).stat().st_size for row in rows(plan))
    # Three state copies per dispatch. Factor two allows longer evolved numbers
    # and nesting indentation; 4 MiB/run allows native pickles, metadata and logs.
    estimated = (
        2 * 3 * plan["observed_steps"] * state_bytes
        + plan["native_runs"] * (2 * native_bytes + 4 * 1024 * 1024)
        + 8 * 1024 * 1024
    )
    c.require(estimated < plan["max_artifact_bytes"], "Prospective storage estimate exceeds cap")
    return {
        "largest_prepared_state_json_bytes": state_bytes,
        "largest_retained_observed_record_bytes": native_bytes,
        "estimated_panel_bytes_with_allowances": estimated,
        "max_artifact_bytes": plan["max_artifact_bytes"],
        "basis": "saved inputs plus explicit allowances; not a measured runtime or hard FS quota",
        "prior_six_preparations_seconds": c.read(PRIOR)["native_elapsed_seconds"],
    }


def prelaunch(tests, expected_tests):
    plan = c.read(PLAN)
    validate_plan(plan)
    for row in rows(plan):
        previous.mapping(row)
    preserved = preservation_check()
    suites = list(ET.parse(tests).getroot().iter("testsuite"))
    counts = {
        name: sum(int(s.get(name, 0)) for s in suites)
        for name in ("tests", "failures", "errors", "skipped")
    }
    c.require(
        expected_tests > 0
        and counts == {"tests": expected_tests, "failures": 0, "errors": 0, "skipped": 0},
        "Incomplete focused pilot tests",
    )
    c.require(
        {case.get("classname") for suite in suites for case in suite.findall("testcase")}
        == {"validation.betse.test_full_loop_bridge", "validation.betse.test_full_loop_observer"},
        "Wrong focused test modules",
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
        "schema": "cells.betse_full_loop_bridge_prelaunch@1",
        "status": "adapter_checks_pass_not_native_execution",
        "checked_utc": datetime.now(UTC).isoformat(),
        "prior_handoff_sha256": PRIOR_SHA,
        "preservation_sha256": c.sha(PRESERVATION),
        "plan_sha256": c.sha(PLAN),
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
    parser.add_argument("--tests", type=str)
    parser.add_argument("--expected-tests", type=int)
    args = parser.parse_args()
    if args.command == "preserve":
        preserve()
    else:
        prelaunch((c.ROOT / args.tests).resolve(), args.expected_tests)
