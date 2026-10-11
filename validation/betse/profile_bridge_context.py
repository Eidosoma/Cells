"""REF-003e0 v2: explicit profile prerequisites, preservation and bounded inputs."""

import argparse
import copy
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import UTC, datetime

import cluster_closeout as files
import contact as c
import phase_bridge_context as previous
import trajectory_context as trajectory
import trajectory_evidence as evidence

PRIOR = c.ROOT / "reports/ref-003e0-preflight-handoff.json"
PRIOR_SHA = "31c0e7743b2e237c5a9ec8f683d10bf28c0968833d3dc35be8cd37ce29690b9c"
PLAN = c.HERE / "profile_bridge_plan.json"
PRESERVATION = c.ROOT / "reports/ref-003e0-v2-preservation.json"
FILES = {
    "profile_bridge_context.py",
    "profile_bridge.py",
    "profile_bridge_check.py",
    "profile_bridge_plan.json",
    "test_profile_bridge.py",
}
VARIANTS = {
    "baseline": {"profiles_enabled": False, "event_mode": "disabled"},
    "default_profile": {"profiles_enabled": True, "event_mode": "disabled"},
    "zero_amplitude": {"profiles_enabled": True, "event_mode": "zero_amplitude"},
}


def authenticate():
    c.require(c.sha(PRIOR) == PRIOR_SHA, "D073 handoff changed")
    prior = c.read(PRIOR)
    c.require(
        prior["status"] == "native_preflight_failed_profile_prerequisite", "Wrong predecessor"
    )
    for name, digest in prior["new_files_sha256_before_handoff"].items():
        c.require(c.sha(c.ROOT / name) == digest, "Frozen D073 file changed: " + name)
    packet = c.ROOT / prior["failed_attempt"]
    c.require(
        {str(p.relative_to(packet)): c.sha(p) for p in packet.rglob("*") if p.is_file()}
        == prior["failed_attempt_files_sha256"],
        "Failed preparation packet changed",
    )
    return previous.authenticate()


def preserve():
    accepted = authenticate()
    owned = {"validation/betse/" + name for name in FILES}
    baseline = {name: digest for name, digest in files.worktree().items() if name not in owned}
    c.write(
        PRESERVATION,
        {
            "schema": "cells.betse_profile_bridge_preservation@1",
            "created_utc": datetime.now(UTC).isoformat(),
            "prior_handoff_sha256": PRIOR_SHA,
            "baseline_sha256": baseline,
            "accepted_sources": accepted["implementation_files_sha256"],
        },
    )
    print(json.dumps({"status": "preserved", "baseline_files": len(baseline)}))


def validate_plan(plan):
    c.require(
        plan["schema"] == "cells.betse_profile_bridge_preflight_plan@2"
        and plan["prior_handoff_sha256"] == PRIOR_SHA
        and plan["revision"] == 2,
        "Wrong preparation amendment",
    )
    c.require(
        plan["variants"] == VARIANTS
        and plan["case_ids"] == ["passive", "blocked"]
        and plan["constant_profile"] == "matched_constants"
        and plan["dt_s"] == 0.000025
        and plan["duration_s"] == 0.001
        and plan["dispatch_elapsed_times_s"] == [0.0, 0.0003, 0.0005, 0.0007, 0.001],
        "Preparation coverage/inputs changed",
    )
    c.require(
        plan["worker_timeout_seconds"] == 35
        and plan["max_artifact_bytes"] == 33554432
        and plan["cpu_affinity"] == "0-3"
        and plan["equality"] == "exact_values_shapes_dtypes_bytes"
        and plan["preserve_partial_state"] is True,
        "Preparation resource/evidence contract changed",
    )
    c.require(
        all(
            plan[key] is False
            for key in ("trajectory_run", "trajectory_qualified", "biology_validated", "gpu_tested")
        ),
        "Preparation overclaims trajectory/biology/GPU scope",
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


def mapping(row):
    c.require(row["variant"] in VARIANTS, "Unknown profile bridge variant")
    c.require(row["profile"] in ("source_constants", "matched_constants"), "Unknown constants")
    variant = VARIANTS[row["variant"]]
    protocol, mapped = previous.mapping(row["case"], row["dt_s"], variant["event_mode"])
    for entry in protocol["yaml_overrides"]:
        if entry[0] == ["tissue profile definition", "profiles enabled"]:
            entry[1] = variant["profiles_enabled"]
    previous.require_dispatch_profiles(protocol)
    mapped |= {
        "variant": row["variant"],
        "profiles_enabled": variant["profiles_enabled"],
        "revision": 2,
    }
    return protocol, mapped


def handoff():
    """Bind preparation evidence and focused tests without launching another model."""
    accepted = authenticate()
    preserved = c.read(PRESERVATION)
    changed = {
        name: {"before": digest, "after": c.sha(c.ROOT / name)}
        for name, digest in preserved["baseline_sha256"].items()
        if c.sha(c.ROOT / name) != digest
    }
    c.require(set(changed) <= previous.ALLOWED_EDITS, "Unexpected existing file edit")
    output = c.ROOT / "runs/ref-003e0-v2-2026-09-12/preflight-01"
    terminal = "failure.json" if (output / "failure.json").exists() else "completion.json"
    native = c.read(output / terminal)
    c.require(
        not ((output / "failure.json").exists() and (output / "completion.json").exists()),
        "Ambiguous native terminal status",
    )
    for name, digest in native["files_sha256"].items():
        c.require(c.sha(output / name) == digest, "Native preparation artifact changed")
    c.require(
        {str(p.relative_to(output)) for p in output.rglob("*") if p.is_file()}
        == set(native["files_sha256"]) | {terminal},
        "Preparation file coverage differs",
    )
    c.require(
        c.read(output / "registration.json")["sources"] == trajectory.sources(),
        "Captured/current adapter differs",
    )
    tests = c.ROOT / "reports/ref-003e0-v2-checks-02.xml"
    suites = ET.parse(tests).getroot().findall("testsuite")
    counts = {
        key: sum(int(s.get(key, 0)) for s in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    c.require(
        counts == {"tests": 87, "failures": 0, "errors": 0, "skipped": 0},
        "Incomplete focused tests",
    )
    c.require(
        {case.get("classname") for suite in suites for case in suite.findall("testcase")}
        == {"validation.betse.test_profile_bridge"},
        "Wrong test module",
    )
    quality = {}
    for name, args in (("lint", ["check"]), ("format", ["format", "--check"])):
        quality[name] = subprocess.check_output(
            [str(c.ROOT / ".venv/bin/ruff"), *args, "src", "tests", "scripts", "validation"],
            cwd=c.ROOT,
            text=True,
        ).strip()
    current = files.worktree()
    result = {
        "schema": "cells.betse_profile_bridge_handoff@2",
        "status": native["status"],
        "finished_utc": datetime.now(UTC).isoformat(),
        "prior_handoff_sha256": PRIOR_SHA,
        "preservation_sha256": c.sha(PRESERVATION),
        "native_attempt": str(output.relative_to(c.ROOT)),
        "native_terminal_sha256": c.sha(output / terminal),
        "native_terminal_filename": terminal,
        "native_elapsed_seconds": native["elapsed_seconds"],
        "native_attempt_files_sha256": native["files_sha256"]
        | {terminal: c.sha(output / terminal)},
        "baseline_files": len(preserved["baseline_sha256"]),
        "unchanged_baseline_files": len(preserved["baseline_sha256"]) - len(changed),
        "changed_baseline_files": changed,
        "accepted_implementation_files_unchanged": len(accepted["implementation_files_sha256"]),
        "production_modules_unchanged": sum(
            n.startswith("src/") and n.endswith(".py")
            for n in accepted["implementation_files_sha256"]
        ),
        "new_files_sha256_before_handoff": {
            name: digest
            for name, digest in current.items()
            if name not in preserved["baseline_sha256"]
        },
        "tests": counts | {"junit_sha256": c.sha(tests)},
        "quality": quality,
        "preparations_passed": native.get("preparations", 0)
        if terminal == "completion.json"
        else 0,
        "event_dispatch_calls": native.get("event_dispatch_calls", 0)
        if terminal == "completion.json"
        else None,
        "trajectory_run": False,
        "trajectory_qualified": False,
        "full_loop_observer_runtime_tested": False,
        "biology_validated": False,
        "gpu_tested": False,
        "production_changed": False,
        "prior_adapter_suite_rerun": False,
        "production_matrix_rerun": False,
        "automatic_retry": False,
    }
    c.write(c.ROOT / "reports/ref-003e0-v2-handoff.json", result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "tests": counts,
                "unchanged_baseline_files": result["unchanged_baseline_files"],
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preserve", "handoff"))
    args = parser.parse_args()
    preserve() if args.command == "preserve" else handoff()
