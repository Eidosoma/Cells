"""D081: source-bound fixed-input response pilot, resources and prelaunch evidence."""

import argparse
import hashlib
import json
import math
import subprocess
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import cluster_closeout as files
import contact as c
import dispatch_preflight as preparation
import dispatch_preflight_context as prior
import held_intervention as held
import phase_bridge_context as edits
import trajectory_context as old
import trajectory_evidence as evidence

PRIOR_SHA = "67c537c0ccb4e716aeefbd69b23b21ed90a3c7c4477796d86c3cdce2c14c7ed5"
PLAN = c.HERE / "held_response_plan.json"
PRESERVATION = c.ROOT / "reports/ref-003e1-response-preservation.json"
PRELAUNCH = c.ROOT / "reports/ref-003e1-response-prelaunch.json"
DISPATCH = c.ROOT / "runs/ref-003e1-dispatch-2026-09-12/preflight-01"
FILES = {
    "held_response_plan.json",
    "held_response_context.py",
    "held_response_native.py",
    "held_response_check.py",
    "held_response_cells_check.py",
    "held_response_job.py",
    "test_held_response.py",
    "test_held_response_check.py",
}


def validate_plan(p):
    expected = {
        "schema": "cells.betse_held_response_plan@1",
        "prior_handoff_sha256": PRIOR_SHA,
        "conditions": list(held.CONDITIONS),
        "constant_profile": "matched_constants",
        "hold_step_s": 0.000025,
        "duration_s": 0.001,
        "cells_subdivisions": [1, 2, 4],
        "cells_backends": ["jax_eager", "jax_jit"],
        "native_modes": ["observed", "unobserved"],
        "native_runs": 8,
        "cells_runs": 24,
        "observed_native_steps": 160,
        "cells_steps_total": 2240,
        "criteria_source": "validation/betse/trajectory_refinement_protocol.json",
        "control_atol": 2e-14,
        "terminal_rate_policy": "validate_Cells_last_hold_but_no_invented_native_final_RHS",
        "cross_failure_policy": (
            "fail_and_retain_unchanged_criteria_including_known_coarse_baseline"
        ),
        "stage_timeout_seconds": {"native": 180, "cells": 2100, "comparison": 180},
        "total_timeout_seconds": 2520,
        "max_artifact_bytes": 536870912,
        "max_worker_file_bytes": 67108864,
        "cpu_affinity": "0-3",
    } | dict.fromkeys(
        (
            "automatic_polling",
            "automatic_retry",
            "automatic_expansion",
            "native_convergence_qualified",
            "forcing_convergence_qualified",
            "trajectory_qualified",
            "biology_validated",
            "gpu_tested",
        ),
        False,
    )
    c.require(
        json.dumps(p, sort_keys=True, allow_nan=False)
        == json.dumps(expected, sort_keys=True, allow_nan=False),
        "Unregistered held-response scope/resources",
    )


def authenticate():
    c.require(c.sha(prior.HANDOFF) == PRIOR_SHA, "D080 handoff changed")
    saved = c.read(prior.HANDOFF)
    c.require(saved["status"] == "nonzero_dispatch_checks_pass", "Actual dispatch did not pass")
    for n, h in saved["new_files_sha256_before_handoff"].items():
        c.require(c.sha(c.ROOT / n) == h, "Frozen D080 evidence changed: " + n)
    c.require(
        preparation.manifest(DISPATCH) == saved["native_attempt_files_sha256"],
        "Native dispatch packet changed",
    )
    registered = c.read(DISPATCH / "registration.json")
    with zipfile.ZipFile(DISPATCH / "sources.zip") as archive:
        c.require(
            len(archive.namelist()) == len(registered["sources"])
            and set(archive.namelist()) == set(registered["sources"]),
            "D080 capsule coverage differs",
        )
        for n, h in registered["sources"].items():
            c.require(
                hashlib.sha256(archive.read(n)).hexdigest() == c.sha(c.HERE / n) == h,
                "D080 capsule/source differs",
            )
    return prior.authenticate()


def native_rows(p):
    validate_plan(p)
    return prior.rows(c.read(prior.PLAN))


def cells_rows(p):
    validate_plan(p)
    return [
        {
            "condition": condition,
            "backend": backend,
            "subdivision": factor,
            "id": f"{condition}/{backend}/subdivision-{factor}",
        }
        for condition in p["conditions"]
        for backend in p["cells_backends"]
        for factor in p["cells_subdivisions"]
    ]


def definitions(p):
    return {
        row["id"]: held.cells_definition(
            c.read(held.PLAN),
            row["condition"],
            p["hold_step_s"],
            row["subdivision"],
            row["backend"],
        )
        for row in cells_rows(p)
    }


def common_times(p):
    validate_plan(p)
    return [i * p["hold_step_s"] for i in range(40)] + [p["duration_s"]]


def prepared(row):
    directory = DISPATCH / row["condition"]
    return {n: c.read(directory / (n + ".json")) for n in ("core", "ready", "metadata")}


def overlap_path(row, mode):
    c.require(row["condition"] != "suppression_recovery", "Pulse has no retained response")
    variant = "zero_amplitude" if row["condition"] == "zero_amplitude" else "default_profile"
    return (
        c.ROOT
        / "runs/ref-003e0-expanded-2026-09-12/capture-01/native"
        / old.key(row["case"]["id"], row["profile"], row["dt_s"])
        / variant
        / mode
        / "result.json"
    )


def export_shapes():
    saved = c.read(evidence.SESSION / "cells/passive/jax_eager/0.00005000/result.json")
    return {
        part: {n: v["shape"][1:] for n, v in saved[part].items()}
        for part in ("history", "observations")
    }


def preservation_check():
    accepted = authenticate()
    saved = c.read(PRESERVATION)
    c.require(
        saved["accepted_sources"] == accepted["implementation_files_sha256"]
        and saved["runtime"] == accepted["runtime"],
        "Accepted Cells source/runtime changed",
    )
    c.require(
        saved["dispatch_files_sha256"] == preparation.manifest(DISPATCH),
        "Dispatch evidence changed",
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
        "dispatch_files_unchanged": len(saved["dispatch_files_sha256"]),
        "accepted_implementation_files_unchanged": len(accepted["implementation_files_sha256"]),
        "production_modules_unchanged": 51,
    }


def resources(p):
    validate_plan(p)
    registered = evidence.trusted_registration()
    records = [
        c.read(evidence.SESSION / "cells" / identifier / "result.json")
        for identifier in registered["cells_definitions"]
    ]
    eager = max(
        r["timings"]["total_run_seconds"] / (r["times"]["shape"][0] - 1)
        for r in records
        if not r["definition"]["execution"]["jit"]
    )
    compiled = max(
        r["timings"]["total_run_seconds"] for r in records if r["definition"]["execution"]["jit"]
    )
    native_seconds = c.read(DISPATCH / "completion.json")["elapsed_seconds"]
    estimates = {
        "native": math.ceil(1.5 * native_seconds * 2 + 60),
        "cells": math.ceil(1.5 * (1120 * eager + 12 * compiled) + 90),
        "comparison": 120,
    }
    state_bytes = max(
        len(json.dumps(prepared(r)["ready"]["state"], indent=2).encode()) for r in native_rows(p)
    )
    largest_native = max(
        overlap_path(r, mode).stat().st_size
        for r in native_rows(p)
        if r["condition"] != "suppression_recovery"
        for mode in p["native_modes"]
    )
    # Full native records plus duplicated event/state exports; Cells allocation
    # scales both history and observation counts, not just the old eight-run total.
    native_bytes = 2 * 8 * largest_native + 2 * 3 * 160 * state_bytes
    cells_bytes = (
        2
        * 24
        * max(
            len(json.dumps(r).encode()) * max(161 / r["times"]["shape"][0], 41 / 11)
            for r in records
        )
    )
    estimate_bytes = math.ceil(native_bytes + cells_bytes + 16 * 1024 * 1024)
    c.require(
        all(estimates[k] < p["stage_timeout_seconds"][k] for k in estimates),
        "Prospective stage time exceeds cap",
    )
    c.require(
        sum(estimates.values()) + 60 < p["total_timeout_seconds"],
        "Prospective total time exceeds cap",
    )
    c.require(estimate_bytes < p["max_artifact_bytes"], "Prospective artifact size exceeds cap")
    return {
        "basis": (
            "D080 native preparation plus slowest retained REF-003d v2 per-step eager "
            "and compiled costs, with explicit allowances"
        ),
        "slowest_eager_seconds_per_step": eager,
        "slowest_compiled_run_seconds": compiled,
        "stage_seconds_with_allowances": estimates,
        "estimated_artifact_bytes_with_allowances": estimate_bytes,
        "peak_RAM_measured": False,
    }


def validate_registration(r):
    validate_plan(r["plan"])
    pre = c.read(PRELAUNCH)
    c.require(
        r["schema"] == "cells.betse_held_response_registration@1"
        and r["prior_handoff_sha256"] == PRIOR_SHA
        and r["prelaunch_sha256"] == c.sha(PRELAUNCH)
        and r["preservation_sha256"] == c.sha(PRESERVATION),
        "Response registration identity differs",
    )
    c.require(
        pre["status"] == "software_checks_pass_not_native_execution"
        and pre["plan_sha256"] == c.sha(PLAN)
        and pre["test_receipt_sha256"] == c.sha(c.ROOT / pre["test_receipt"])
        and r["sources"] == pre["sources"] == old.sources()
        and FILES <= set(r["sources"]),
        "Response inputs/source/tests changed",
    )
    for name, digest in pre["new_files_sha256_before_prelaunch"].items():
        c.require(
            c.sha(c.ROOT / name) == digest, "Frozen response prelaunch input changed: " + name
        )
    accepted = c.authenticate_cells()
    c.require(
        accepted["implementation_files_sha256"] == c.read(PRESERVATION)["accepted_sources"]
        and accepted["runtime"] == r["cells_runtime"],
        "Accepted Cells implementation/runtime differs at execution",
    )
    legacy = evidence.trusted_registration()
    c.require(
        r["native_rows"] == native_rows(r["plan"])
        and r["cells_rows"] == cells_rows(r["plan"])
        and r["cells_definitions"] == definitions(r["plan"])
        and r["common_times_s"] == common_times(r["plan"])
        and r["cells_export_shapes"] == export_shapes(),
        "Response coverage or definitions differ",
    )
    for key in ("base_protocol", "geometry", "settings", "cells_runtime"):
        c.require(r[key] == legacy[key], "Prior physical/runtime inputs differ: " + key)
    c.require(
        r["criteria"] == legacy["protocol"] == c.read(c.ROOT / r["plan"]["criteria_source"])
        and r["upstream"]["files_sha256"] == legacy["upstream"]["files_sha256"],
        "Physical tolerances or source changed",
    )


def prelaunch(tests, expected):
    preserved = preservation_check()
    p = c.read(PLAN)
    counts, modules = prior.prior.prior.prior.test_counts(tests)
    c.require(
        counts["tests"] == expected
        and modules
        == {"validation.betse.test_held_response", "validation.betse.test_held_response_check"},
        "Wrong response preflight tests",
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
            "schema": "cells.betse_held_response_prelaunch@1",
            "status": "software_checks_pass_not_native_execution",
            "created_utc": datetime.now(UTC).isoformat(),
            "plan_sha256": c.sha(PLAN),
            "sources": old.sources(),
            "tests": counts,
            "test_receipt": str(tests.relative_to(c.ROOT)),
            "test_receipt_sha256": c.sha(tests),
            "quality": quality,
            "resources": resources(p),
            "preservation_sha256": c.sha(PRESERVATION),
            "new_files_sha256_before_prelaunch": {
                n: h
                for n, h in files.worktree().items()
                if n not in c.read(PRESERVATION)["baseline_sha256"]
            },
            "trajectory_run": False,
            **preserved,
        },
    )
    print(json.dumps({"status": "software_checks_pass_not_native_execution", "tests": counts}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tests", type=Path)
    parser.add_argument("--expected", type=int, required=True)
    args = parser.parse_args()
    prelaunch(args.tests.resolve(), args.expected)
