"""Prospective preparation-only boundary for the separate REF-003e0 adapter."""

import argparse
import copy
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from datetime import UTC, datetime

import cluster_closeout as files
import contact as c
import intervention_design as design
import trajectory_context as trajectory
import trajectory_evidence as evidence

DESIGN_SHA = "17b03572398115bebad98276f1ab159c2e8254f83fa06004d549272225262d94"
PRESERVATION = c.ROOT / "reports/ref-003e0-preflight-preservation.json"
FILES = {
    "phase_bridge_context.py",
    "native_event_observer.py",
    "phase_bridge.py",
    "test_phase_bridge.py",
    "test_native_event_observer.py",
}
ALLOWED_EDITS = {
    "PROGRESS.md",
    "README.md",
    "docs/BETSE_CAPABILITY_ROADMAP.md",
    "docs/BETSE_PASSIVE_TRAJECTORY_PLAN.md",
    "docs/BETSE_REFERENCE_PLAN.md",
    "docs/DECISIONS.md",
    "validation/betse/README.md",
}
EVENT_MODES = ("disabled", "zero_amplitude")


def authenticate():
    c.require(c.sha(design.RECEIPT) == DESIGN_SHA, "D072 design review changed")
    reviewed = c.read(design.RECEIPT)
    c.require(reviewed["status"] == "design_checks_pass", "Design review did not pass")
    for name, digest in reviewed["new_files_sha256_before_review"].items():
        c.require(c.sha(c.ROOT / name) == digest, "Frozen D072 source/evidence changed")
    return design.authenticate()


def preserve():
    accepted = authenticate()
    baseline = {
        n: h
        for n, h in files.worktree().items()
        if n not in {"validation/betse/" + f for f in FILES}
    }
    c.write(
        PRESERVATION,
        {
            "schema": "cells.betse_phase_bridge_preservation@1",
            "created_utc": datetime.now(UTC).isoformat(),
            "design_review_sha256": DESIGN_SHA,
            "baseline_sha256": baseline,
            "accepted_sources": accepted["implementation_files_sha256"],
        },
    )
    print(json.dumps({"status": "preserved", "baseline_files": len(baseline)}))


def mapping(case, dt, event_mode):
    """Keep the accepted preparation; add only SIM clock and declared no-op events."""
    p = c.read(design.PLAN)
    design.validate_plan(p)
    prior = evidence.trusted_registration()
    c.require(case in prior["protocol"]["cases"], "Unknown bridge case")
    c.require(type(dt) is float and dt in p["native_steps_s"], "Unknown bridge timestep")
    c.require(event_mode in EVENT_MODES, "Only no-op bridge events are supported")
    result = copy.deepcopy(trajectory.native_protocol(case, dt))
    count, scale, mapped = design.clock_parameters(p, dt)
    overrides = {tuple(path): value for path, value in result["yaml_overrides"]}
    for field, value in (("time step", dt), ("sampling rate", dt), ("total time", p["duration_s"])):
        overrides[("sim time settings", field)] = value
    # Pinned YAML's default profile; checked again after native loading/resolution.
    tissue_name = "Base"
    for species in ("Na", "K", "Cl"):
        group = "change " + species + " mem"
        fields = {
            "event happens": event_mode == "zero_amplitude",
            "change start": mapped[0],
            "change finish": mapped[1],
            "change rate": mapped[2],
            "multiplier": 0.0,
            "apply to": [tissue_name],
            "modulator function": "None",
        }
        for field, value in fields.items():
            overrides[(group, field)] = value
    result["yaml_overrides"] = [[list(path), value] for path, value in overrides.items()]
    return result, {
        "phase": "SIM",
        "preparation": "fresh_init_core_not_loaded_initialization_pickle",
        "event_mode": event_mode,
        "steps": count,
        "dt_s": dt,
        "duration_s": p["duration_s"],
        "raw_clock_scale": scale,
        "mapped_pulse_times_s": mapped,
        "target_profile": tissue_name,
    }


def preflight_plan():
    """Four fresh preparations, five dispatches each; no integration or capture panel."""
    prior = evidence.trusted_registration()
    return {
        "schema": "cells.betse_phase_bridge_preflight_plan@1",
        "design_review_sha256": DESIGN_SHA,
        "trajectory_run": False,
        "trajectory_qualified": False,
        "rows": [
            {"case": case, "profile": "matched_constants", "dt_s": 0.000025, "event_mode": mode}
            for case in prior["protocol"]["cases"]
            for mode in EVENT_MODES
        ],
        "dispatch_elapsed_times_s": [0.0, 0.0003, 0.0005, 0.0007, 0.001],
        "worker_timeout_seconds": 25,
        "max_artifact_bytes": 16 * 1024 * 1024,
        "cpu_affinity": "0-3",
        "failure_policy": "Retain failure; no automatic retry, trajectory launch or relaxation",
    }


def require_dispatch_profiles(protocol):
    """Post-attempt guard: never silently enable profiles to rescue this candidate."""
    overrides = {tuple(path): value for path, value in protocol["yaml_overrides"]}
    enabled = overrides[("tissue profile definition", "profiles enabled")]
    scheduled = any(
        overrides[("change " + ion + " mem", "event happens")] for ion in ("Na", "K", "Cl")
    )
    c.require(
        not scheduled or enabled is True,
        "Targeted events require tissue profiles; "
        "REF-003e0 needs an explicit versioned profile bridge",
    )


def handoff():
    """Record a failed native preflight plus passing software/negative-evidence tests."""
    accepted = authenticate()
    preserved = c.read(PRESERVATION)
    changes = {
        name: {"before": digest, "after": c.sha(c.ROOT / name)}
        for name, digest in preserved["baseline_sha256"].items()
        if c.sha(c.ROOT / name) != digest
    }
    c.require(set(changes) <= ALLOWED_EDITS, "Unexpected existing source/evidence edit")
    output = c.ROOT / "runs/ref-003e0-2026-09-12/preflight-01"
    c.require(
        c.sha(output / "failure.json")
        == "a59ff3debb871735a8376a0a18805a3aadb0ca2d899518cb6520819261a59c95"
        and c.sha(output / "sources.zip")
        == "a55df2422cddacd02de18eb7af57bb4793e98c42575505f11e9f44eddcae0c24",
        "First native attempt changed",
    )
    registered = c.read(output / "registration.json")
    with zipfile.ZipFile(output / "sources.zip") as archive:
        c.require(
            set(archive.namelist()) == set(registered["sources"]), "Incomplete attempt capsule"
        )
        for name, digest in registered["sources"].items():
            c.require(
                hashlib.sha256(archive.read(name)).hexdigest() == digest, "Attempt capsule changed"
            )
    changed_adapter = {
        name: {"captured": digest, "current": c.sha(c.HERE / name)}
        for name, digest in registered["sources"].items()
        if c.sha(c.HERE / name) != digest
    }
    c.require(
        set(changed_adapter)
        == {"phase_bridge_context.py", "phase_bridge.py", "test_phase_bridge.py"},
        "Unexpected post-attempt source edit",
    )
    tests = c.ROOT / "reports/ref-003e0-preflight-checks-04.xml"
    suites = ET.parse(tests).getroot().findall("testsuite")
    counts = {
        key: sum(int(s.get(key, 0)) for s in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    c.require(
        counts == {"tests": 73, "failures": 0, "errors": 0, "skipped": 0},
        "Incomplete focused tests",
    )
    c.require(
        {case.get("classname") for suite in suites for case in suite.findall("testcase")}
        == {"validation.betse.test_phase_bridge", "validation.betse.test_native_event_observer"},
        "Wrong test modules",
    )
    quality = {}
    for name, args in (("lint", ["check"]), ("format", ["format", "--check"])):
        quality[name] = subprocess.check_output(
            [str(c.ROOT / ".venv/bin/ruff"), *args, "src", "tests", "scripts", "validation"],
            cwd=c.ROOT,
            text=True,
        ).strip()
    current = files.worktree()
    receipt = {
        "schema": "cells.betse_phase_bridge_handoff@1",
        "status": "native_preflight_failed_profile_prerequisite",
        "finished_utc": datetime.now(UTC).isoformat(),
        "design_review_sha256": DESIGN_SHA,
        "preservation_sha256": c.sha(PRESERVATION),
        "failed_attempt": str(output.relative_to(c.ROOT)),
        "failed_attempt_files_sha256": {
            str(p.relative_to(output)): c.sha(p) for p in sorted(output.rglob("*")) if p.is_file()
        },
        "native_elapsed_seconds": c.read(output / "failure.json")["elapsed_seconds"],
        "first_failure": (
            "Adapter metadata assumed dyna.tissue_default existed with profiles disabled"
        ),
        "underlying_prerequisite": (
            "Targeted events require the tissue profiles and target map "
            "omitted by the accepted baseline configuration"
        ),
        "completed_preparation_results": 0,
        "zero_amplitude_runtime_tested": False,
        "full_loop_observer_runtime_tested": False,
        "integration_entry_prohibited": True,
        "native_trajectory_run": False,
        "trajectory_qualified": False,
        "capture_registered": False,
        "preparation_attempt_registered": True,
        "automatic_retry": False,
        "post_attempt_adapter_changes": changed_adapter,
        "baseline_files": len(preserved["baseline_sha256"]),
        "unchanged_baseline_files": len(preserved["baseline_sha256"]) - len(changes),
        "changed_baseline_files": changes,
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
        "prior_adapter_suite_rerun": False,
        "production_matrix_rerun": False,
        "production_changed": False,
        "biology_validated": False,
        "gpu_tested": False,
        "next": (
            "Version the profile bridge; retain profiles-off baseline, compare default-only "
            "profiles-on no-event, then enabled zero-amplitude; "
            "improve partial-state persistence before retry"
        ),
    }
    c.write(c.ROOT / "reports/ref-003e0-preflight-handoff.json", receipt)
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "tests": counts,
                "unchanged_baseline_files": receipt["unchanged_baseline_files"],
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=("preserve", "handoff"), default="preserve")
    args = parser.parse_args()
    preserve() if args.command == "preserve" else handoff()
