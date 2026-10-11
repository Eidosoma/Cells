"""Authenticate D123 and its closed numerical prerequisites without importing it."""

import sys
from pathlib import Path

import wire_decode as wire

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pump_relaxation_plan"))
import check_plan as prior  # noqa: E402

e, ROOT = prior.e, prior.ROOT
CAPTURE = ROOT / "runs/ref-005d-offline-codec-2026-09-17/qualification-01"
REGISTRATION_SHA = "092cd7db7dc3dd9d7d1378607a67ecf16687b249bdded1765eaeceef75529847"
COMPLETION_SHA = "9e5ea291c711deb6edbd6c674c8a7aaff033b932f4c8ef9388db40a4637fe379"
LEGACY = prior.evidence.CAPTURE
e.FORBIDDEN += (
    "record_codec",
    "native_row",
    "qualify",
    "codec_job",
    "native_recording",
    "validation.betse.native_recording",
)


def inventory(directory):
    result = {}
    for path in sorted(directory.rglob("*")):
        wire.need(not path.is_symlink() and (path.is_file() or path.is_dir()), "Unsafe artifact")
        if path.is_file():
            result[str(path.relative_to(directory))] = wire.sha(path)
    return result


def expected_labels():
    return sorted(
        f"{variant}/dt_{step:.8g}/{mode}"
        for variant in (
            "pump_leak",
            "pump_only",
            "leak_only",
            "all_blocked",
            "half_density",
            "closed_boundary",
        )
        for step in (6.25e-6, 3.125e-6, 1.5625e-6)
        for mode in ("observed", "unobserved")
    )


def authenticate():
    wire.need(
        wire.sha(CAPTURE / "registration.json") == REGISTRATION_SHA
        and wire.sha(CAPTURE / "completion.json") == COMPLETION_SHA,
        "Codec evidence identity",
    )
    r, done = (
        wire.read_json(CAPTURE / "registration.json", None),
        wire.read_json(CAPTURE / "completion.json", None),
    )
    wire.need(
        r["schema"] == "cells.native_codec_qualification@1"
        and done["status"] == "offline_codec_exact_pending_independent_review"
        and done["rows"] == 36
        and done["observed_updates"] == 6720
        and done["stream_records"] == 20196,
        "Codec terminal scope",
    )
    for key in (
        "live_observer_qualified",
        "longer_horizon_qualified",
        "native_memory_bounded",
        "production_changed",
        "biology_validated",
        "gpu_tested",
        "automatic_followup",
    ):
        wire.need(done[key] is False, "Expanded codec claim: " + key)
    files = inventory(CAPTURE)
    wire.need(
        len(done["files_sha256"]) == 778
        and set(files)
        == set(done["files_sha256"])
        | {"completion.json", "launch.json", "runner.stdout.log", "runner.stderr.log"},
        "Codec packet membership",
    )
    wire.need(
        all(files[k] == digest for k, digest in done["files_sha256"].items()),
        "Codec payload changed",
    )
    wire.need(
        wire.read_json(CAPTURE / "launch.json")["registration_sha256"] == REGISTRATION_SHA,
        "Codec launch binding",
    )
    wire.need(len(r["sources_sha256"]) == 14, "Codec source coverage")
    prior.evidence.capsule(CAPTURE, r["sources_sha256"])
    wire.need(
        e.software(ROOT / r["software"]["path"], 132) == r["software"]
        and r["software"]["tests"] == 132,
        "Codec software receipt",
    )
    probe = ROOT / r["probe"]["path"]
    wire.need(
        probe.resolve().is_relative_to(ROOT / "runs")
        and wire.sha(probe / "completion.json") == r["probe"]["completion_sha256"]
        and wire.sha(probe / "measurement.json") == r["probe"]["measurement_sha256"],
        "Codec resource probe identity",
    )
    probe_done = wire.read_json(probe / "completion.json", None)
    wire.need(
        probe_done["status"] == "largest_saved_row_exact_resource_probe_only", "Probe incomplete"
    )
    prior.evidence.hashes(probe, probe_done["files_sha256"])
    measurement = wire.read_json(probe / "measurement.json")
    wire.need(
        all(r["sources_sha256"].get(k) == v for k, v in measurement["sources_sha256"].items()),
        "Probe runtime sources differ",
    )

    # Reauthenticate the complete original accepted/rejected chain, not only the
    # source files whose values this particular decoder happens to consume.
    _, modules, _ = prior.authenticate()
    wire.need(
        len(modules) == 55
        and r["capture_completion_sha256"] == prior.evidence.COMPLETION_SHA
        and r["prior_audit_completion_sha256"] == prior.AUDIT_SHA,
        "Numerical prerequisite",
    )
    original_files = wire.read_json(LEGACY / "completion.json", None)["files_sha256"]
    original_rows = wire.read_json(LEGACY / "betse.json", None)["records"]
    wire.need(sorted(r["records"]) == expected_labels() == sorted(original_rows), "Codec matrix")
    for label in expected_labels():
        source = r["records"][label]
        wire.need(source["path"] == original_rows[label], "Legacy row mapping")
        path = prior.evidence.child(LEGACY, source["path"])
        wire.need(
            source["sha256"] == original_files[source["path"]]
            and source["bytes"] == path.stat().st_size,
            "Legacy input identity/extent",
        )
    return r, done, files


def source_manifest():
    paths = [
        *HERE.glob("*.py"),
        HERE / "README.md",
        ROOT / "reports/REF005D_CODEC_AUDIT_HANDOFF.md",
        HERE.parent / "pump_relaxation_plan/check_plan.py",
        HERE.parent / "pump_pilot_audit/audit_evidence.py",
        HERE.parent / "pump_pilot_diagnosis/diagnose.py",
        HERE.parent / "pump_pilot_diagnosis/native_energy.py",
        HERE.parent / "pump_loop_audit/evidence.py",
        HERE.parent / "pump_loop_audit/review.py",
        HERE.parent / "kinetic_family_audit/artifacts.py",
    ]
    return {str(p.relative_to(ROOT)): wire.sha(p) for p in sorted(paths)}
