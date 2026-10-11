"""D100 immutable paired-capture provenance; authentication is not numerical replay."""

import importlib
import math
import sys
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "channel_history_pilot"))
pilot = importlib.import_module("paired_context")
capture_job = importlib.import_module("paired_job")
prior = importlib.import_module("feedback_audit_context")
c, io, ROOT = pilot.c, pilot.io, pilot.ROOT
CAPTURE = ROOT / "runs/ref-004c-paired-history-2026-09-15/capture-01"
PLAN = HERE / "plan.json"
ANCHORS = {
    "completion.json": "ec63dc8d69a9f4c5b9da93ddf64708e91fc708729eb0f52cb1d8899170bde690",
    "registration.json": "9c539f504312e77e3d695e5a549e0e0d2a34d1801b128c57e23c81f4e128341b",
    "comparison.json": "2cfe3c45128ec5a25a167edb52f3dfb6077383f4747a81b4982f6901a73e5c9f",
    "reference-gate.json": "5f78a8a998911d389a7da13d41d4379eeff460dd6ffbb1b9354a201de98cfd73",
    "history-contrasts.json": "0a58860009314ff7815632adb4a4d613ee1e63b61c6836c18a1bf0a001f3c32e",
}
NEW_SOURCES = tuple(
    "validation/betse/channel_history_audit/" + name
    for name in (
        "plan.json",
        "history_audit_context.py",
        "history_audit_math.py",
        "history_audit_reference.py",
        "history_audit_cells.py",
        "history_audit_replay.py",
        "history_audit_job.py",
        "test_history_audit.py",
    )
) + ("docs/BETSE_CHANNEL_HISTORY_CLOSEOUT.md",)
FORBIDDEN, OPERATIONAL = prior.FORBIDDEN, prior.OPERATIONAL
model_fence, packet_hashes = prior.model_fence, prior.packet_hashes


def sources():
    return pilot.sources() | {name: c.sha(ROOT / name) for name in NEW_SOURCES}


def historical_reports():
    names = [
        "reports/REF004C_HISTORY_PREPARATION_CLOSEOUT.md",
        "reports/REF004C_PAIRED_HISTORY_HANDOFF.md",
        "reports/ref-004c-history-review-checks-01.xml",
        "reports/ref-004c-paired-pilot-checks-01.xml",
        "reports/ref-004c-paired-pilot-checks-02.xml",
        "reports/ref-004c-history-audit-checks-01.xml",
        "reports/ref-004c-history-audit-checks-02.xml",
        "reports/ref-004c-history-audit-checks-03-timeout.json",
        "reports/REF004C_PAIRED_HISTORY_CAPTURE.md",
        "reports/REF004C_PAIRED_HISTORY_AUDIT_HANDOFF.md",
    ]
    return prior.historical_reports() | {name: c.sha(ROOT / name) for name in names}


def validate_plan(plan):
    c.require(plan == c.read(PLAN), "Unregistered paired audit plan")
    expected = {
        "schema": "cells.betse_paired_history_audit_plan@1",
        "decision": "D100",
        "capture": str(CAPTURE.relative_to(ROOT)),
        "completion_sha256": ANCHORS["completion.json"],
        "capture_files": 291,
        "capture_source_inputs": 143,
        "native_identities": 7367280,
        "native_charge_snapshots": 2264,
        "expected_coarse_rejections_by_history": {"a": 14, "b": 7},
        "numeric_checkpoints": 24,
        "checkpoint_arrays": 1296,
        "precision_digits": 80,
        "cpu_affinity": [0, 1, 2, 3],
        "total_timeout_seconds": 900,
        "max_file_bytes": 128 * 1024**2,
        "max_artifact_bytes": 256 * 1024**2,
        "max_decoded_record_bytes": 128 * 1024**2,
    }
    c.require(all(plan[k] == v for k, v in expected.items()), "Paired audit scope differs")
    c.require(
        all(
            plan[k] is False
            for k in (
                "simulators_rerun",
                "reference_integrator_rerun",
                "automatic_polling",
                "automatic_retry",
                "automatic_followup",
            )
        ),
        "Unexpected automatic work",
    )


def payloads(r):
    root = {
        "registration.json",
        "sources.zip",
        "started.json",
        "comparison.json",
        "reference-gate.json",
        "reference-gate-passed.json",
        "history-contrasts.json",
        "matplotlib-cache/fontlist-v3.11.0.json",
    }
    for kind in ("reference", "betse", "cells"):
        root |= {f"{kind}.json", f"{kind}.log", f"{kind}-started.json"}
    for name, view in r["views"].items():
        # Only model payloads from the audited old inventory builder, not its root schema.
        local = {
            n for n in prior.payloads(view) if n.startswith(("cells/", "native/", "reference/"))
        }
        local |= {
            "reference-gate.json.gz",
            "native-accounting.json.gz",
            "cells-accounting.json.gz",
            "trajectory-comparison.json",
            "trajectory-failures.jsonl",
        }
        root |= {name + "/" + n for n in local}
    return root


def provenance(r, done, workers, hashes):
    expected, budget = payloads(r), r["protocol"]["resources"]
    c.require(
        len(expected) == 287 and set(hashes) == expected | OPERATIONAL | {"completion.json"},
        "Paired capture membership differs",
    )
    c.require(
        set(done["files_sha256"]) == expected
        and all(hashes[n] == h for n, h in done["files_sha256"].items()),
        "Paired payload manifest differs",
    )
    launch, started = (c.read(CAPTURE / n) for n in ("launch.json", "started.json"))
    c.require(
        launch["status"] == "launched_detached"
        and launch["pid"] == started["pid"] == 2676647
        and launch["resources"] == budget,
        "Paired launch identity",
    )
    c.require(
        launch["registration_sha256"]
        == done["registration_sha256"]
        == ANCHORS["registration.json"],
        "Paired registration identity",
    )
    comparison = c.read(CAPTURE / "comparison.json")
    c.require(all(done[k] == v for k, v in comparison.items()), "Paired completion differs")
    counts = {
        "native_boundary_comparisons": 7367280,
        "native_direct_charge_snapshots": 2264,
        "coarse_diagnostic_failures": 21,
        "checkpoints": 24,
        "checkpoint_arrays": 1296,
        "observer_pairs": 12,
        "restart_pairs": 4,
        "backend_pairs": 4,
        "native_boundary_failures": 0,
        "cells_accounting_failures": 0,
        "required_trajectory_failures": 0,
        "failed_refinement_groups": 0,
        "history_contrast_failures": 0,
    }
    c.require(
        done["status"] == "paired_capture_pass_pending_audit"
        and all(done[k] == v for k, v in counts.items()),
        "Paired result scope differs",
    )
    c.require(
        done["reference_convergence_checked"] is True
        and all(
            done[k] is False
            for k in (
                "coupled_history_qualified",
                "independent_audit_complete",
                "production_changed",
                "old_evidence_rewritten",
                "biology_validated",
                "gpu_tested",
                "automatic_polling",
                "automatic_retry",
                "automatic_followup",
            )
        ),
        "Paired qualification flags differ",
    )
    c.require(
        launch["reference_gate_before_simulators"] is True
        and all(
            launch[k] is False
            for k in (
                "automatic_polling",
                "automatic_retry",
                "automatic_followup",
            )
        ),
        "Paired automatic work differs",
    )
    stages = {kind: c.read(CAPTURE / f"{kind}-started.json") for kind in workers}
    c.require(
        all(stages[k]["reference_gate_passed"] is (k != "reference") for k in stages),
        "Reference gate bypassed",
    )
    dates = [
        datetime.fromisoformat(v)
        for v in (
            r["registered_utc"],
            launch["launched_utc"],
            started["started_utc"],
            stages["reference"]["started_utc"],
            stages["betse"]["started_utc"],
            stages["cells"]["started_utc"],
            done["finished_utc"],
        )
    ]
    c.require(
        all(t.tzinfo is not None and t.utcoffset().total_seconds() == 0 for t in dates)
        and dates == sorted(dates),
        "Paired stage chronology",
    )
    elapsed = done["elapsed_seconds"]
    c.require(
        math.isfinite(elapsed)
        and sum(w["elapsed_seconds"] for w in workers.values())
        < elapsed
        < budget["total_timeout_seconds"],
        "Paired elapsed budget",
    )
    c.require(
        (dates[-1] - dates[2]).total_seconds() <= elapsed <= (dates[-1] - dates[0]).total_seconds(),
        "Paired wall clock mismatch",
    )
    used = sum((CAPTURE / n).stat().st_size for n in hashes)
    c.require(
        used - (CAPTURE / "completion.json").stat().st_size == done["artifact_bytes_before_receipt"]
        and used < budget["max_artifact_bytes"],
        "Paired artifact accounting",
    )
    c.require(
        all((CAPTURE / n).stat().st_size <= budget["max_file_bytes"] for n in hashes),
        "Paired per-file cap",
    )
    c.require(
        all((CAPTURE / n).stat().st_size == 0 for n in ("runner.stdout.log", "runner.stderr.log")),
        "Unexpected controller output",
    )
    c.require(
        done["tests"] == r["tests"] and done["tests"]["tests"] == 56, "Paired software receipt"
    )
    return {
        "capture_files": len(hashes),
        "capture_source_inputs": len(r["sources_sha256"]),
        "capture_artifact_bytes": used,
        "captured_elapsed_seconds": elapsed,
        "unchanged_implementation_files": 352,
        "unchanged_production_modules": 51,
        "gate_order_evidence": "hash-bound receipts and ordered worker starts, "
        "not an external execution attestation",
    }


def load_capture():
    plan = c.read(PLAN)
    validate_plan(plan)
    c.require(
        all(c.sha(CAPTURE / n) == h for n, h in ANCHORS.items()), "Paired capture anchor changed"
    )
    r = pilot.authenticate(CAPTURE)
    capture_job.require_gate(CAPTURE, r)
    done, hashes = c.read(CAPTURE / "completion.json"), packet_hashes(CAPTURE)
    workers = {
        k: capture_job.validate_worker(r, CAPTURE, k) for k in ("reference", "betse", "cells")
    }
    return {
        "registration": r,
        "completion": done,
        "hashes": hashes,
        "workers": workers,
        "plan": plan,
        "provenance": provenance(r, done, workers, hashes),
    }


def test_receipt(path):
    c.require(path.is_file() and path.is_relative_to(ROOT / "reports"), "Missing paired audit XML")
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    names = []
    for suite in suites:
        rows = list(suite.findall("testcase"))
        c.require(
            len(rows) == int(suite.attrib["tests"])
            and all(int(suite.attrib.get(k, 0)) == 0 for k in ("failures", "errors", "skipped")),
            "Incomplete paired audit tests",
        )
        for row in rows:
            c.require(
                not any(row.find(k) is not None for k in ("failure", "error", "skipped")),
                "Rejected paired audit test",
            )
            names.append(row.attrib["classname"] + "::" + row.attrib["name"])
    c.require(
        len(names) >= 50
        and len(names) == len(set(names))
        and all("channel_history_audit.test_history_audit::" in name for name in names),
        "Audit test coverage",
    )
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": c.sha(path),
        "tests": len(names),
        "identities": sorted(names),
        "original_56_tests_bound_not_rerun": True,
    }
