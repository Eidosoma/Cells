"""D106 authentication of the immutable timed capture, not numerical replay."""

import importlib
import math
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "channel_release_pilot"))
pilot = importlib.import_module("timed_context")
capture_job = importlib.import_module("timed_job")
prior = importlib.import_module("history_audit_context")
c, io, ROOT = pilot.c, pilot.io, pilot.ROOT
FORBIDDEN, OPERATIONAL = prior.FORBIDDEN, prior.OPERATIONAL
model_fence, packet_hashes = pilot.model_fence, pilot.packet_hashes
CAPTURE = ROOT / "runs/ref-004d-timed-release-2026-09-16/capture-01"
PLAN = HERE / "plan.json"
ANCHORS = {
    "completion.json": "355a5709eb30460f4734ecb6ea3d9e391d0b7102fdfdb4211d0f411e4083b6a6",
    "registration.json": "a82235aa0940c3c237d947104231ad24dfe0d02d05d55991858ca41690953352",
    "comparison.json": "c7931fdb30cd733df3a4ff96a8642c0687a2def04f438b6b44c686c820a18717",
    "reference-review.json": "07cf26d6edaef597dd20dcdfaa97bcaad3620e35d067da7ee725c1a226852902",
    "reference-review-passed.json": (
        "d86131125c42465139af0927723384b6ac047844067ddfc27cf782c9ffe86c57"
    ),
    "history-contrasts.json": "367b589b28c693a0f4349537f27218381f338ffce74174a0f5d43313b3b6d854",
}
FILES = tuple(
    "validation/betse/channel_release_audit/" + n
    for n in (
        "plan.json",
        "release_audit_context.py",
        "release_audit_math.py",
        "release_audit_native.py",
        "release_audit_cells.py",
        "release_audit_replay.py",
        "release_audit_job.py",
        "test_release_audit.py",
    )
) + ("docs/BETSE_CHANNEL_RELEASE_CLOSEOUT.md",)


def sources():
    return pilot.sources() | {n: c.sha(ROOT / n) for n in FILES}


def historical_reports():
    return pilot.reports() | {
        n: c.sha(ROOT / n)
        for n in (
            "reports/ref-004d-timed-release-checks-09.xml",
            "reports/ref-004d-timed-release-checks-10.xml",
            "reports/REF004D_TIMED_RELEASE_CAPTURE.md",
            "reports/REF004D_RELEASE_AUDIT_HANDOFF.md",
            "reports/ref-004d-release-audit-checks-01.xml",
            "reports/ref-004d-release-audit-checks-02.xml",
            "reports/REF004D_RELEASE_AUDIT_SOFTWARE_TIMEOUT.md",
        )
    }


def validate_plan(plan):
    c.require(plan == c.read(PLAN), "Unregistered timed audit plan")
    c.require(
        plan["decision"] == "D106" and plan["completion_sha256"] == ANCHORS["completion.json"],
        "Timed audit target",
    )
    for name in (
        "simulators_rerun",
        "reference_integrator_rerun",
        "reference_review_rerun",
        "production_changed",
        "biology_validated",
        "gpu_tested",
        "automatic_polling",
        "automatic_retry",
        "automatic_followup",
    ):
        c.require(plan[name] is False, "Expanded audit scope: " + name)


def payloads(r):
    names = {
        "registration.json",
        "sources.zip",
        "started.json",
        "comparison.json",
        "native-accounting.json.gz",
        "history-contrasts.json",
        "reference-review.json",
        "reference-review-passed.json",
        "matplotlib-cache/fontlist-v3.11.0.json",
    }
    for engine in ("betse", "cells"):
        names |= {engine + suffix for suffix in (".json", ".log", "-started.json")}
    for history, view in r["views"].items():
        names |= {
            history + "/" + n
            for n in (
                "cells-accounting.json.gz",
                "cells-sides.json.gz",
                "trajectory-comparison.json",
                "trajectory-failures.jsonl",
            )
        }
        for condition in r["plan"]["conditions"]:
            for step in r["plan"]["native_steps_s"]:
                for mode in ("observed", "unobserved"):
                    folder = history + "/native/" + pilot.key(condition, step) + "/" + mode + "/"
                    leaves = {
                        "native.yaml",
                        "geometry.json",
                        "core.json",
                        "fixture.json",
                        "result.json.gz",
                        "INITS/init_1.betse.gz",
                        "INITS/world_1.betse.gz",
                    }
                    if mode == "observed":
                        leaves.add("loop-entry.json")
                    names |= {folder + n for n in leaves}
        for key, definition in view["cells_definitions"].items():
            folder = history + "/cells/" + key + "/"
            leaves = {
                "result.json.gz",
                "side-probes.json.gz",
                "final-checkpoint/manifest.json",
                "final-checkpoint/state.npz",
            }
            if (
                definition["execution"]["jit"]
                and definition["execution"]["dt"] == view["protocol"]["restart_step_s"]
            ):
                leaves.add("resumed.json.gz")
                leaves |= {
                    checkpoint + "/" + n
                    for checkpoint in ("midpoint-checkpoint", "resumed-checkpoint")
                    for n in ("manifest.json", "state.npz")
                }
            names |= {folder + n for n in leaves}
    return names


def provenance(r, done, workers, hashes):
    expected, budget = payloads(r), r["plan"]["resources"]
    c.require(
        len(expected) == 551 and set(hashes) == expected | OPERATIONAL | {"completion.json"},
        "Timed capture membership",
    )
    c.require(
        set(done["files_sha256"]) == expected
        and all(hashes[n] == h for n, h in done["files_sha256"].items()),
        "Timed capture manifest",
    )
    counts = {
        "native_boundary_comparisons": 14772920,
        "native_boundary_failures": 0,
        "required_comparison_failures": 0,
        "history_contrast_failures": 0,
        "coarse_diagnostic_failures": 49,
        "checkpoints": 48,
        "checkpoint_arrays": 2592,
        "observer_pairs": 24,
        "restart_pairs": 8,
        "backend_pairs": 8,
    }
    c.require(
        done["status"] == "timed_release_capture_pass_pending_audit"
        and all(done[k] == v for k, v in counts.items()),
        "Timed result scope",
    )
    c.require(
        done["reference_review_closed"] is True
        and all(
            done[n] is False
            for n in (
                "independent_capture_audit_complete",
                "release_response_qualified",
                "biology_validated",
                "gpu_tested",
                "production_changed",
                "old_evidence_rewritten",
                "automatic_polling",
                "automatic_retry",
                "automatic_followup",
            )
        ),
        "Timed result flags",
    )
    c.require(
        all(done[k] == v for k, v in c.read(CAPTURE / "comparison.json").items()),
        "Timed completion/result binding",
    )
    launch, started = (c.read(CAPTURE / n) for n in ("launch.json", "started.json"))
    c.require(
        launch["status"] == "launched_detached"
        and launch["pid"] == started["pid"] == 3100871
        and launch["resources"] == budget
        and launch["reference_review_before_simulators"] is True,
        "Timed launch identity",
    )
    c.require(
        launch["registration_sha256"]
        == done["registration_sha256"]
        == ANCHORS["registration.json"],
        "Timed registration binding",
    )
    stages = {k: c.read(CAPTURE / (k + "-started.json")) for k in workers}
    c.require(
        all(row["reference_review_passed"] is True for row in stages.values()),
        "Timed entrance gate bypass",
    )
    dates = [
        datetime.fromisoformat(t)
        for t in (
            r["registered_utc"],
            launch["launched_utc"],
            started["started_utc"],
            stages["betse"]["started_utc"],
            stages["cells"]["started_utc"],
            done["finished_utc"],
        )
    ]
    c.require(
        dates == sorted(dates)
        and all(t.tzinfo is not None and t.utcoffset().total_seconds() == 0 for t in dates),
        "Timed chronology",
    )
    elapsed = done["elapsed_seconds"]
    c.require(
        math.isfinite(elapsed)
        and sum(w["elapsed_seconds"] for w in workers.values())
        < elapsed
        < budget["total_timeout_seconds"]
        and (dates[-1] - dates[2]).total_seconds()
        <= elapsed
        <= (dates[-1] - dates[0]).total_seconds(),
        "Timed wall/monotonic budget",
    )
    used = sum((CAPTURE / n).stat().st_size for n in hashes)
    c.require(
        used - (CAPTURE / "completion.json").stat().st_size == done["artifact_bytes_before_receipt"]
        and used < budget["max_artifact_bytes"]
        and all((CAPTURE / n).stat().st_size <= budget["max_file_bytes"] for n in hashes),
        "Timed artifact budget",
    )
    c.require(
        all((CAPTURE / n).stat().st_size == 0 for n in ("runner.stdout.log", "runner.stderr.log")),
        "Unexpected timed controller output",
    )
    c.require(
        done["tests"] == r["tests"]
        and done["tests"]["tests"] == 121
        and len(r["sources_sha256"]) == 194,
        "Timed source/software scope",
    )
    review = c.read(CAPTURE / "reference-review.json")
    c.require(
        review["independent"] == done["reference_review"]
        and review["model_imports"] == []
        and review["reference_integrator_rerun"] is False,
        "Reference review binding",
    )
    return {
        "capture_files": len(hashes),
        "capture_source_inputs": 194,
        "capture_artifact_bytes": used,
        "captured_elapsed_seconds": elapsed,
        "closed_reference_identities_authenticated_not_replayed": 1485380,
        "gate_order_evidence": (
            "hash-bound receipts and ordered starts, not external execution attestation"
        ),
    }


def load_capture():
    plan = c.read(PLAN)
    validate_plan(plan)
    c.require(
        all(c.sha(CAPTURE / n) == h for n, h in ANCHORS.items()), "Timed capture anchor changed"
    )
    r = pilot.authenticate(CAPTURE)
    capture_job.require_gate(CAPTURE, r)
    done, hashes = c.read(CAPTURE / "completion.json"), packet_hashes(CAPTURE)
    workers = {kind: capture_job.validate_worker(r, CAPTURE, kind) for kind in ("betse", "cells")}
    return {
        "registration": r,
        "completion": done,
        "hashes": hashes,
        "workers": workers,
        "plan": plan,
        "provenance": provenance(r, done, workers, hashes),
    }


def test_receipt(paths):
    receipts = [pilot.xml_receipt(path) for path in paths]
    names = [name for receipt in receipts for name in receipt["identities"]]
    required = {
        "test_capture_authenticates_without_models",
        "test_complete_coarse_native_case_replays_every_column",
        "test_cells_full_state_restart_backend_replay",
        "test_full_side_rhs_frozen_replay",
        "test_all_twelve_contrast_groups_replay",
        "test_dynamic_noop_and_sides_preserve_coarse_misses",
        "test_crosscheck_rejects_corrupted_original_column",
        "test_checkpoint_corruption_rejected",
        "test_controller_success_and_deadline_receipts",
        "test_detached_launch_never_waits_or_polls",
    }
    c.require(
        len(names) >= 60
        and len(names) == len(set(names))
        and all("channel_release_audit.test_release_audit::" in name for name in names)
        and required <= {name.split("::")[-1].split("[")[0] for name in names},
        "Timed audit software coverage",
    )
    return {"receipts": receipts, "tests": len(names), "identities": sorted(names)}
