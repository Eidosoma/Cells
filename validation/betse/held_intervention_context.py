"""Authenticate the qualified D078 predecessor and record control-only D079 checks."""

import argparse
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import cluster_closeout as files
import contact as c
import expanded_audit_context as prior
import held_intervention as design
import phase_bridge_context as edits

SESSION = c.ROOT / "runs/ref-003e0-expanded-audit-2026-09-12/audit-01"
PRESERVATION = c.ROOT / "reports/ref-003e1-control-design-preservation.json"
RECEIPT = c.ROOT / "reports/ref-003e1-control-design-review.json"
PREFLIGHT_SHA = "7fbce656b0d5325b5684f1d75898fe2cadfdd64d67f24383527eb21122c22245"
NEW_SOURCES = {
    "held_intervention.py",
    "held_intervention_context.py",
    "held_intervention_plan.json",
    "test_held_intervention.py",
}


def authenticate():
    c.require(c.sha(SESSION / "completion.json") == design.PRIOR_SHA, "D078 closeout changed")
    c.require(c.sha(prior.PRELAUNCH) == PREFLIGHT_SHA, "D078 preflight changed")
    closed = c.read(SESSION / "completion.json")
    c.require(
        closed["status"] == "pass" and closed["expanded_bridge_qualified"] is True,
        "Expanded bridge is not qualified",
    )
    actual = prior.prior.packet_hashes(SESSION)
    c.require(
        all(actual.get(n) == h for n, h in closed["files_sha256"].items())
        and set(actual)
        == set(closed["files_sha256"])
        | {"completion.json", "launch.json", "runner.stdout.log", "runner.stderr.log"},
        "Expanded audit payloads/layout changed",
    )
    for n, h in c.read(SESSION / "registration.json")["sources"].items():
        c.require(c.sha(c.HERE / n) == h, "Captured audit source changed: " + n)
    for n, h in c.read(prior.PRELAUNCH)["new_files_sha256_before_prelaunch"].items():
        c.require(c.sha(c.ROOT / n) == h, "D078 frozen preflight evidence changed: " + n)
    return prior.authenticate()


def preservation_check():
    accepted = authenticate()
    saved = c.read(PRESERVATION)
    c.require(
        saved["accepted_sources"] == accepted["implementation_files_sha256"],
        "Accepted production changed",
    )
    c.require(
        saved["expanded_audit_files_sha256"] == prior.prior.packet_hashes(SESSION)
        and saved["expanded_capture_files_sha256"] == prior.packet_hashes(),
        "Preserved expanded evidence changed",
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
        "expanded_capture_files_unchanged": len(saved["expanded_capture_files_sha256"]),
        "expanded_audit_files_unchanged": len(saved["expanded_audit_files_sha256"]),
        "accepted_implementation_files_unchanged": len(accepted["implementation_files_sha256"]),
        "production_modules_unchanged": sum(
            n.startswith("src/") and n.endswith(".py")
            for n in accepted["implementation_files_sha256"]
        ),
    }


def review(tests, expected):
    c.require(not RECEIPT.exists(), "Control design receipt already exists")
    p = c.read(design.PLAN)
    design.validate_plan(p)
    preserved = preservation_check()
    counts, modules = prior.prior.test_counts(tests)
    c.require(
        counts["tests"] == expected and modules == {"validation.betse.test_held_intervention"},
        "Wrong control-only test coverage",
    )
    native, local = design.run_probe("native"), design.run_probe("cells")
    c.require(
        all(
            row["integration_calls"] == 0 and row["plan_sha256"] == c.sha(design.PLAN)
            for row in (native, local)
        ),
        "Control probe provenance differs",
    )
    quality = {}
    for name, args in (("lint", ["check"]), ("format", ["format", "--check"])):
        quality[name] = subprocess.check_output(
            [str(c.ROOT / ".venv/bin/ruff"), *args, "src", "tests", "scripts", "validation"],
            cwd=c.ROOT,
            text=True,
            timeout=20,
        ).strip()
    native_source = c.SOURCE / "betse/science/tissue/tishandler.py"
    source_contract = design.composition_contract(native_source.read_text())
    baseline = c.read(PRESERVATION)["baseline_sha256"]
    result = {
        "schema": "cells.betse_held_intervention_design_review@1",
        "status": "control_design_checks_pass",
        "finished_utc": datetime.now(UTC).isoformat(),
        "prior_closeout_sha256": design.PRIOR_SHA,
        "prior_design_review_sha256": c.sha(c.ROOT / "reports/ref-003e-design-review.json"),
        "plan_sha256": c.sha(design.PLAN),
        "input_law_sha256": c.sha(design.law.PLAN),
        "criteria_source_sha256": c.sha(c.ROOT / p["criteria_source"]),
        "native_composition_source_sha256": c.sha(native_source),
        "native_composition_contract": source_contract,
        "native_control_probe": native,
        "cells_control_probe": local,
        "tests": counts,
        "test_receipt": str(tests.relative_to(c.ROOT)),
        "test_receipt_sha256": c.sha(tests),
        "preservation_sha256": c.sha(PRESERVATION),
        "sources": {n: c.sha(c.HERE / n) for n in sorted(NEW_SOURCES)},
        "new_files_sha256_before_review": {
            n: h for n, h in files.worktree().items() if n not in baseline
        },
        "quality": quality,
        "proposed_pilot": p["pilot"],
        "capture_registered": False,
        "simulation_launched": False,
        "integration_calls": 0,
        "nonzero_event_dispatch_run": False,
        "trajectory_qualified": False,
        "continuous_waveform_qualified": False,
        "biology_validated": False,
        "gpu_tested": False,
        "production_changed": False,
        "prior_full_suites_rerun": False,
        "stable_promotion": False,
        "next_step": "Bounded actual nonzero SIM preparation/dispatch preflight before capture",
        **preserved,
    }
    c.write(RECEIPT, result)
    print(
        f"{result['status']}: {counts['tests']} tests, "
        f"{len(native['rows'])} native control rows, "
        f"{len(local['rows'])} Cells grids; no integration"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tests", type=Path, required=True)
    parser.add_argument("--expected", type=int, required=True)
    args = parser.parse_args()
    review(args.tests.resolve(), args.expected)
