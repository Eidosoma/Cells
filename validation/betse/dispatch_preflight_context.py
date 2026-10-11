"""D080: explicit nonzero preparation inputs, prior evidence and execution boundaries."""

import argparse
import copy
import json
import math
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import cluster_closeout as files
import contact as c
import held_intervention as held
import held_intervention_context as prior
import phase_bridge_context as edits
import trajectory_context as old
import trajectory_evidence as evidence

PRIOR_SHA = "babca8de6553f61bc03abb1ad305eb95d3653cd44233b49759a8067537a984b8"
PLAN = c.HERE / "dispatch_preflight_plan.json"
PRESERVATION = c.ROOT / "reports/ref-003e1-dispatch-preservation.json"
PRELAUNCH = c.ROOT / "reports/ref-003e1-dispatch-prelaunch.json"
HANDOFF = c.ROOT / "reports/ref-003e1-dispatch-handoff.json"
FILES = {
    "dispatch_preflight.py",
    "dispatch_preflight_context.py",
    "dispatch_preflight_check.py",
    "dispatch_preflight_plan.json",
    "test_dispatch_preflight.py",
}


def validate_plan(p):
    expected = {
        "schema": "cells.betse_nonzero_dispatch_plan@1",
        "prior_review_sha256": PRIOR_SHA,
        "conditions": list(held.CONDITIONS),
        "constant_profile": "matched_constants",
        "dt_s": 0.000025,
        "duration_s": 0.001,
        "preparations": 4,
        "dispatches_per_preparation": 40,
        "raw_clock": "native_linspace_0_T_N",
        "terminal_dispatch_elapsed_s": 39 * 0.000025,
        "control_atol": 2e-14,
        "worker_timeout_seconds": 45,
        "total_timeout_seconds": 60,
        "max_artifact_bytes": 67108864,
        "max_worker_file_bytes": 16777216,
        "cpu_affinity": "0-3",
        "persist_each_completed_dispatch": True,
        "integration_calls": 0,
    } | dict.fromkeys(
        (
            "trajectory_run",
            "trajectory_qualified",
            "biology_validated",
            "gpu_tested",
            "automatic_retry",
            "automatic_trajectory_launch",
        ),
        False,
    )
    c.require(
        json.dumps(p, sort_keys=True, allow_nan=False)
        == json.dumps(expected, sort_keys=True, allow_nan=False),
        "Unregistered nonzero dispatch scope or resources",
    )


def authenticate():
    c.require(c.sha(prior.RECEIPT) == PRIOR_SHA, "D079 control review changed")
    reviewed = c.read(prior.RECEIPT)
    c.require(reviewed["status"] == "control_design_checks_pass", "D079 did not pass")
    for n, h in reviewed["new_files_sha256_before_review"].items():
        c.require(c.sha(c.ROOT / n) == h, "Frozen D079 evidence changed: " + n)
    return prior.authenticate()


def rows(plan):
    validate_plan(plan)
    cases = {r["id"]: r for r in evidence.trusted_registration()["protocol"]["cases"]}
    return [
        {
            "condition": condition,
            "case": copy.deepcopy(cases["blocked" if condition == "static_blocked" else "passive"]),
            "profile": plan["constant_profile"],
            "dt_s": plan["dt_s"],
        }
        for condition in plan["conditions"]
    ]


def mapping(row):
    p = c.read(PLAN)
    c.require(row in rows(p), "Unknown dispatch-preflight row")
    law = c.read(held.law.PLAN)
    count, scale, times = held.law.clock_parameters(law, row["dt_s"])
    condition = row["condition"]
    enabled = condition in ("zero_amplitude", "suppression_recovery")
    multiplier = (
        law["candidate_pulse"]["additive_multiplier"]
        if condition == "suppression_recovery"
        else 0.0
    )
    protocol = copy.deepcopy(old.native_protocol(row["case"], row["dt_s"]))
    overrides = {tuple(path): value for path, value in protocol["yaml_overrides"]}
    overrides[("tissue profile definition", "profiles enabled")] = True
    for field, value in (
        ("time step", row["dt_s"]),
        ("sampling rate", row["dt_s"]),
        ("total time", p["duration_s"]),
    ):
        overrides[("sim time settings", field)] = value
    for ion in ("Na", "K", "Cl"):
        for field, value in {
            "event happens": enabled,
            "change start": times[0],
            "change finish": times[1],
            "change rate": times[2],
            "multiplier": multiplier,
            "apply to": ["Base"],
            "modulator function": "None",
        }.items():
            overrides[("change " + ion + " mem", field)] = value
    protocol["yaml_overrides"] = [[list(path), value] for path, value in overrides.items()]
    edits.require_dispatch_profiles(protocol)
    labels = [i * (p["duration_s"] / (count - 1)) for i in range(count - 1)] + [p["duration_s"]]
    return protocol, {
        "condition": condition,
        "phase": "SIM",
        "event_mode": condition if enabled else "disabled",
        "events_enabled": enabled,
        "profiles_enabled": True,
        "preparation": "fresh_seed_SIM_init_core_no_INIT_restart",
        "steps": count,
        "dt_s": row["dt_s"],
        "duration_s": p["duration_s"],
        "raw_clock_scale": scale,
        "mapped_pulse_times_s": times,
        "multiplier": multiplier,
        "raw_labels_s": labels,
        "elapsed_times_s": [i * row["dt_s"] for i in range(count)],
    }


def preservation_check():
    accepted = authenticate()
    saved = c.read(PRESERVATION)
    c.require(saved["accepted_sources"] == accepted["implementation_files_sha256"], "Cells changed")
    c.require(
        saved["expanded_capture_files_sha256"] == prior.prior.packet_hashes()
        and saved["expanded_audit_files_sha256"] == prior.prior.prior.packet_hashes(prior.SESSION),
        "Expanded bridge evidence changed",
    )
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
        "accepted_implementation_files_unchanged": len(accepted["implementation_files_sha256"]),
        "production_modules_unchanged": 51,
        "expanded_capture_files_unchanged": len(saved["expanded_capture_files_sha256"]),
        "expanded_audit_files_unchanged": len(saved["expanded_audit_files_sha256"]),
    }


def resources(plan):
    validate_plan(plan)
    previous = c.ROOT / "runs/ref-003e0-v2-2026-09-12/preflight-01"
    closed = c.read(previous / "completion.json")
    state_bytes = max(
        len(json.dumps(c.read(p)["state"], indent=2).encode())
        for p in previous.glob("preparation-*/ready.json")
    )
    # Two states per dispatch, durable individual files plus aggregate, 2x
    # formatting allowance; eight MiB for preparation/source/metadata/logs.
    estimated_bytes = 2 * 2 * 2 * 160 * state_bytes + 8 * 1024 * 1024
    estimated_seconds = math.ceil(1.5 * closed["elapsed_seconds"] * 4 / 6 + 15)
    c.require(estimated_bytes < plan["max_artifact_bytes"], "Prospective storage exceeds cap")
    c.require(estimated_seconds < plan["worker_timeout_seconds"], "Prospective time exceeds cap")
    return {
        "basis": "D074 measured six preparations plus explicit dispatch/storage allowances",
        "prior_elapsed_seconds": closed["elapsed_seconds"],
        "largest_prepared_state_bytes": state_bytes,
        "estimated_bytes_with_allowances": estimated_bytes,
        "estimated_worker_seconds_with_allowances": estimated_seconds,
        "peak_RAM_measured": False,
    }


def prelaunch(tests, expected):
    preserved = preservation_check()
    plan = c.read(PLAN)
    counts, modules = prior.prior.prior.test_counts(tests)
    c.require(
        counts["tests"] == expected and modules == {"validation.betse.test_dispatch_preflight"},
        "Wrong focused preflight coverage",
    )
    quality = {}
    for name, args in (("lint", ["check"]), ("format", ["format", "--check"])):
        quality[name] = subprocess.check_output(
            [str(c.ROOT / ".venv/bin/ruff"), *args, "src", "tests", "scripts", "validation"],
            cwd=c.ROOT,
            text=True,
            timeout=20,
        ).strip()
    c.write(
        PRELAUNCH,
        {
            "schema": "cells.betse_nonzero_dispatch_prelaunch@1",
            "status": "software_checks_pass_not_native_execution",
            "created_utc": datetime.now(UTC).isoformat(),
            "plan_sha256": c.sha(PLAN),
            "sources": old.sources(),
            "prior_review_sha256": PRIOR_SHA,
            "test_receipt": str(tests.relative_to(c.ROOT)),
            "test_receipt_sha256": c.sha(tests),
            "tests": counts,
            "quality": quality,
            "resources": resources(plan),
            "preservation_sha256": c.sha(PRESERVATION),
            "native_execution": False,
            **preserved,
        },
    )
    print(json.dumps({"status": "software_checks_pass_not_native_execution", "tests": counts}))


def handoff(output):
    import dispatch_preflight as run

    preserved = preservation_check()
    terminal = "failure.json" if (output / "failure.json").exists() else "completion.json"
    c.require(
        not ((output / "failure.json").exists() and (output / "completion.json").exists()),
        "Ambiguous terminal status",
    )
    result = c.read(output / terminal)
    c.require(
        run.manifest(output, exclude={terminal}) == result["files_sha256"],
        "Attempt evidence changed",
    )
    pre = c.read(PRELAUNCH)
    c.require(pre["sources"] == old.sources(), "Preflight sources changed after freeze")
    baseline = c.read(PRESERVATION)["baseline_sha256"]
    c.write(
        HANDOFF,
        {
            "schema": "cells.betse_nonzero_dispatch_handoff@1",
            "status": result["status"],
            "finished_utc": datetime.now(UTC).isoformat(),
            "prior_review_sha256": PRIOR_SHA,
            "prelaunch_sha256": c.sha(PRELAUNCH),
            "native_attempt": str(output.relative_to(c.ROOT)),
            "native_terminal_filename": terminal,
            "native_terminal_sha256": c.sha(output / terminal),
            "native_attempt_files_sha256": run.manifest(output),
            "native_elapsed_seconds": result["elapsed_seconds"],
            "preparations_passed": result.get("preparations", 0),
            "event_dispatch_calls": result.get("event_dispatch_calls", 0),
            "maximum_baseline_scaled_control_error": result.get(
                "maximum_baseline_scaled_control_error"
            ),
            "tests": pre["tests"],
            "quality": pre["quality"],
            "new_files_sha256_before_handoff": {
                n: h for n, h in files.worktree().items() if n not in baseline
            },
            "integration_calls": 0,
            "trajectory_run": False,
            "trajectory_qualified": False,
            "full_loop_noninterference_qualified": False,
            "biology_validated": False,
            "gpu_tested": False,
            "production_changed": False,
            "prior_full_suites_rerun": False,
            "automatic_retry": False,
            "automatic_trajectory_launch": False,
            **preserved,
        },
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "native_elapsed_seconds": result["elapsed_seconds"],
                "tests": pre["tests"],
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prelaunch", "handoff"))
    parser.add_argument("path", type=Path)
    parser.add_argument("--expected", type=int)
    args = parser.parse_args()
    if args.action == "prelaunch":
        prelaunch(args.path.resolve(), args.expected)
    else:
        handoff(args.path.resolve())
