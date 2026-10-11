"""Immutable pilot/source/runtime authentication; never starts a simulator."""

import importlib
import math
import sys
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "channel_feedback_pilot"))
pilot = importlib.import_module("feedback_context")
capture_job = importlib.import_module("feedback_job")
io = importlib.import_module("feedback_io")
c, ROOT = pilot.c, pilot.ROOT
CAPTURE = ROOT / "runs/ref-004b-feedback-pilot-2026-09-15/capture-01"
PLAN = HERE / "plan.json"
ANCHORS = {
    "completion.json": "28e985c8f1d49d7953b21382ad6a34b6f2989f23c5407a97118902f8391c8ceb",
    "registration.json": "1a479c2589d65a52146c3167f82952a8c83bd4ca359a6e42c931aac6183a065a",
    "capture-comparison.json": "f5fb3f35abf1e7ff9cb2051e3584d3c9261d6d2f415549e75bb7dcd0ecaaeca5",
    "reference-gate.json.gz": "22b40cb33492ea1adea6d0f77712bdaec4b4dab0c34c2e49425a3b88d8c1fefd",
    "trajectory-comparison.json": "94968a184397b647af5a99160478c3ba53136359f171aed621a1395f55e28ffa",  # noqa: E501
}
NEW_SOURCES = tuple(
    "validation/betse/channel_feedback_audit/" + name
    for name in (
        "plan.json",
        "feedback_audit_context.py",
        "feedback_audit_math.py",
        "feedback_audit_native.py",
        "feedback_audit_reference.py",
        "feedback_audit_cells.py",
        "feedback_audit_replay.py",
        "feedback_audit_job.py",
        "test_feedback_audit.py",
    )
) + ("docs/BETSE_CHANNEL_FEEDBACK_CLOSEOUT.md",)
FORBIDDEN, OPERATIONAL = pilot.audit.FORBIDDEN, pilot.audit.OPERATIONAL
model_fence, packet_hashes = pilot.audit.model_fence, pilot.audit.packet_hashes


def sources():
    return {name: c.sha(ROOT / name) for name in sorted(set(pilot.sources()) | set(NEW_SOURCES))}


def historical_reports():
    names = [f"reports/ref-004b-feedback-pilot-checks-{i:02d}.xml" for i in range(1, 6)]
    names += [
        "reports/REF004B_FEEDBACK_PILOT_HANDOFF.md",
        "reports/REF004B_LOOP_AUDIT_HANDOFF.md",
        "reports/REF004B_LOOP_PREPARATION_HANDOFF.md",
        "reports/REF004B_TRANSPORT_AUDIT_HANDOFF.md",
    ]
    return {name: c.sha(ROOT / name) for name in names}


def validate_plan(plan):
    c.require(plan == c.read(PLAN), "Unregistered feedback audit plan")
    c.require(
        plan["schema"] == "cells.betse_channel_feedback_audit_plan@1"
        and plan["decision"] == "D096"
        and plan["capture"] == str(CAPTURE.relative_to(ROOT))
        and plan["completion_sha256"] == ANCHORS["completion.json"],
        "Wrong feedback audit evidence",
    )
    expected = {
        "native_identities": 5181760,
        "native_charge_snapshots": 2264,
        "expected_coarse_rejections": 14,
        "capture_files": 284,
        "capture_source_inputs": 112,
        "precision_digits": 80,
        "total_timeout_seconds": 900,
        "max_file_bytes": 128 * 1024**2,
        "max_artifact_bytes": 256 * 1024**2,
        "max_decoded_record_bytes": 128 * 1024**2,
    }
    c.require(
        all(plan[k] == v for k, v in expected.items()) and plan["cpu_affinity"] == [0, 1, 2, 3],
        "Feedback audit scope/resources changed",
    )
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
    result = set(
        (
            "betse-started.json",
            "betse.json",
            "betse.log",
            "capture-comparison.json",
            "cells-accounting.json.gz",
            "cells-started.json",
            "cells.json",
            "cells.log",
            "native-accounting.json.gz",
            "reference-gate-passed.json",
            "reference-gate.json.gz",
            "reference-started.json",
            "reference.json",
            "reference.log",
            "registration.json",
            "sources.zip",
            "started.json",
            "trajectory-comparison.json",
            "trajectory-failures.jsonl",
            "matplotlib-cache/fontlist-v3.11.0.json",
        )
    )
    for variant in r["protocol"]["variants"]:
        for setting in r["protocol"]["reference"]["solves"]:
            result.add(f"reference/{variant}/{setting['id']}/result.json.gz")
        for step in r["protocol"]["native_steps_s"]:
            for mode in ("observed", "unobserved"):
                directory = f"native/{variant}/dt_{step:.8g}/{mode}/"
                result |= {
                    directory + name
                    for name in (
                        "INITS/world_1.betse.gz",
                        "INITS/init_1.betse.gz",
                        "core.json",
                        "fixture.json",
                        "geometry.json",
                        "native.yaml",
                        "result.json.gz",
                    )
                }
                if mode == "observed":
                    result.add(directory + "loop-entry.json")
    for key in r["cells_definitions"]:
        directory = "cells/" + key + "/"
        result.add(directory + "result.json.gz")
        checkpoints = ["final-checkpoint"]
        if key.endswith(f"/jax_jit/dt_{r['protocol']['restart_step_s']:.8g}"):
            checkpoints += ["midpoint-checkpoint", "resumed-checkpoint"]
            result.add(directory + "resumed.json.gz")
        for checkpoint in checkpoints:
            result |= {
                directory + checkpoint + "/" + name for name in ("manifest.json", "state.npz")
            }
    return result


def provenance(r, done, workers, hashes):
    budget = r["protocol"]["resources"]
    expected = payloads(r)
    c.require(
        len(expected) == 280 and set(hashes) == expected | OPERATIONAL | {"completion.json"},
        "Pilot packet membership differs",
    )
    c.require(
        set(done["files_sha256"]) == expected
        and all(hashes[n] == h for n, h in done["files_sha256"].items()),
        "Pilot artifact manifest differs",
    )
    launch, started = (c.read(CAPTURE / n) for n in ("launch.json", "started.json"))
    c.require(
        launch["status"] == "launched_detached"
        and launch["pid"] == started["pid"] == 2631746
        and launch["resources"] == budget,
        "Pilot launch identity",
    )
    c.require(
        launch["registration_sha256"]
        == done["registration_sha256"]
        == ANCHORS["registration.json"],
        "Pilot registration identity",
    )
    c.require(
        all(
            launch[k] is False
            for k in ("automatic_polling", "automatic_retry", "automatic_followup")
        ),
        "Pilot automatic continuation changed",
    )
    comparison = c.read(CAPTURE / "capture-comparison.json")
    c.require(
        all(done[k] == v for k, v in comparison.items()), "Pilot completion/comparison differs"
    )
    expected_counts = {
        "native_boundary_comparisons": 5181760,
        "native_direct_charge_snapshots": 2264,
        "native_boundary_failures": 0,
        "cells_accounting_failures": 0,
        "required_trajectory_failures": 0,
        "coarse_diagnostic_failures": 14,
        "failed_refinement_groups": 0,
        "reference_solves": 12,
        "native_runs": 24,
        "native_updates": 4480,
        "cells_trajectories": 16,
        "cells_resumed_segments": 4,
        "observer_pairs": 12,
        "restart_pairs": 4,
        "backend_pairs": 4,
    }
    c.require(
        all(done[k] == v for k, v in expected_counts.items())
        and done["status"] == "capture_pass_pending_audit",
        "Pilot numerical scope/receipt differs",
    )
    c.require(
        done["reference_convergence_checked"] is True
        and all(
            done[k] is False
            for k in (
                "production_changed",
                "independent_audit_complete",
                "coupled_trajectory_qualified",
                "biology_validated",
                "gpu_tested",
                "automatic_retry",
                "automatic_followup",
            )
        ),
        "Pilot qualification flags differ",
    )
    gate = c.read(CAPTURE / "reference-gate-passed.json")
    stages = {k: c.read(CAPTURE / f"{k}-started.json") for k in workers}
    c.require(
        gate["gate_sha256"] == ANCHORS["reference-gate.json.gz"]
        and gate["simulators_started"] is False,
        "Reference gate receipt differs",
    )
    c.require(
        stages["reference"]["reference_gate_passed"] is False
        and stages["betse"]["reference_gate_passed"] is True
        and stages["cells"]["reference_gate_passed"] is True,
        "Pilot bypassed reference gate",
    )
    dates = [
        datetime.fromisoformat(v)
        for v in (
            r["registered_utc"],
            launch["launched_utc"],
            started["started_utc"],
            stages["reference"]["started_utc"],
            gate["finished_utc"],
            stages["betse"]["started_utc"],
            stages["cells"]["started_utc"],
            done["finished_utc"],
        )
    ]
    c.require(
        all(t.tzinfo is not None and t.utcoffset().total_seconds() == 0 for t in dates)
        and dates == sorted(dates),
        "Pilot stage chronology",
    )
    elapsed = done["elapsed_seconds"]
    c.require(
        math.isfinite(elapsed)
        and 0 < elapsed < budget["total_timeout_seconds"]
        and sum(w["elapsed_seconds"] for w in workers.values()) < elapsed,
        "Pilot timing/budget",
    )
    c.require(
        (dates[-1] - dates[2]).total_seconds() <= elapsed <= (dates[-1] - dates[0]).total_seconds(),
        "Pilot wall/monotonic clock mismatch",
    )
    used = sum((CAPTURE / name).stat().st_size for name in hashes)
    c.require(
        used - (CAPTURE / "completion.json").stat().st_size == done["artifact_bytes_before_receipt"]
        and used < budget["max_artifact_bytes"],
        "Pilot artifact size accounting",
    )
    c.require(
        all((CAPTURE / name).stat().st_size <= budget["max_file_bytes"] for name in hashes),
        "Pilot per-file budget",
    )
    c.require(
        all((CAPTURE / n).stat().st_size == 0 for n in ("runner.stdout.log", "runner.stderr.log")),
        "Unexpected pilot controller output",
    )
    c.require(
        done["tests"] == r["tests"] and done["tests"]["tests"] == 157,
        "Original software receipt differs",
    )
    return {
        "capture_files": len(hashes),
        "capture_source_inputs": len(r["sources_sha256"]),
        "capture_artifact_bytes": used,
        "captured_elapsed_seconds": elapsed,
        "unchanged_implementation_files": 352,
        "unchanged_production_modules": 51,
    }


def load_capture():
    c.require(all(c.sha(CAPTURE / n) == h for n, h in ANCHORS.items()), "Pilot anchor changed")
    r = capture_job.authenticate(CAPTURE)
    done, hashes = c.read(CAPTURE / "completion.json"), packet_hashes(CAPTURE)
    workers = {
        kind: capture_job.validate_worker(r, CAPTURE, kind)
        for kind in ("reference", "betse", "cells")
    }
    return {
        "registration": r,
        "completion": done,
        "hashes": hashes,
        "workers": workers,
        "provenance": provenance(r, done, workers, hashes),
    }


def native_partials(row, directory):
    for file, field in (
        ("core.json", "core_initial"),
        ("fixture.json", "fixture"),
        ("geometry.json", "geometry"),
    ):
        c.require(c.read(directory / file) == row[field], "Native partial record differs")
    c.require(row["native_pickle"] == "INITS/init_1.betse.gz", "Native restart path differs")
    if row["mode"] == "observed":
        trace = row["trace"]
        entry = trace | {
            "status": "partial_not_qualified",
            "steps": [],
            "pending": None,
            "storage": [],
            "hook_restored": False,
            "calls": trace["calls"] | {"loop_return": 0, "run_return": 0},
        }
        c.require(c.read(directory / "loop-entry.json") == entry, "Native entry trace differs")


def test_receipt(path):
    c.require(
        path.is_file() and path.is_relative_to(ROOT / "reports"), "Missing audit software XML"
    )
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    identities = []
    for suite in suites:
        rows = list(suite.findall("testcase"))
        c.require(
            len(rows) == int(suite.attrib["tests"])
            and all(int(suite.attrib.get(k, 0)) == 0 for k in ("failures", "errors", "skipped")),
            "Incomplete audit software checks",
        )
        for row in rows:
            c.require(
                not any(row.find(k) is not None for k in ("failure", "error", "skipped")),
                "Rejected audit software test",
            )
            identities.append(row.attrib["classname"] + "::" + row.attrib["name"])
    c.require(
        len(identities) >= 40
        and len(identities) == len(set(identities))
        and all("channel_feedback_audit.test_feedback_audit::" in n for n in identities),
        "Audit test identity coverage",
    )
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": c.sha(path),
        "tests": len(identities),
        "identities": sorted(identities),
        "original_157_tests_bound_not_rerun": True,
    }
