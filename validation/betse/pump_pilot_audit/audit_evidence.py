"""Authenticate the refined pilot without importing its producer or simulators."""

import hashlib
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pump_pilot_diagnosis"))
import diagnose as diagnostic  # noqa: E402

e, arrays = diagnostic.e, diagnostic.a
ROOT = e.ROOT
CAPTURE = ROOT / "runs/ref-005c-refined-pump-2026-09-16/refinement-01"
REGISTRATION_SHA = "1dcfb80dc010bc694bf752caa0b72c0f97699e162f4aa3599bfc5258deec9c07"
COMPLETION_SHA = "45bc4adf9986bf4adc9750af969818b1cf4e0466854e01dbf136e02eb23cba6f"
DIAGNOSIS = ROOT / "runs/ref-005c-pilot-diagnosis-2026-09-16/review-01"
DIAGNOSIS_SHA = "c6b5f18258d1fa14c2e742fa76b582c0bc7c32ff9e729d96800d8475830a8bb3"
LIFECYCLE = ROOT / "runs/ref-005b-pump-loop-audit-2026-09-16/audit-01"
LIFECYCLE_SHA = "ca6e0f6535531ac772ea4d55e81a251d3b25fc8e4cefc2ec7987a6a357b9065e"
e.FORBIDDEN += ("refinement_context", "refinement_check", "refinement_job")


def child(directory, name):
    path = directory / name
    e.require(
        type(name) is str
        and not Path(name).is_absolute()
        and ".." not in Path(name).parts
        and path.resolve().is_relative_to(directory.resolve()),
        "Unsafe evidence path",
    )
    e.require(not path.is_symlink() and path.is_file(), "Missing/linked evidence")
    return path


def hashes(directory, manifest):
    for name, expected in manifest.items():
        e.require(e.sha(child(directory, name)) == expected, "Changed payload: " + name)


def capsule(directory, manifest):
    hashes(ROOT, manifest)
    with zipfile.ZipFile(directory / "sources.zip") as archive:
        e.require(
            len(archive.namelist()) == len(manifest) and set(archive.namelist()) == set(manifest),
            "Source capsule membership",
        )
        e.require(
            all(hashlib.sha256(archive.read(n)).hexdigest() == h for n, h in manifest.items()),
            "Source capsule bytes",
        )


def same_record(left, right, message):
    digest = arrays.digest(left)
    e.require(digest == arrays.digest(right), message)
    return digest


def contract(r, original):
    protected = set(original["protocol"]) - {
        "schema",
        "decision",
        "scope",
        "native_steps_s",
        "resources",
    }
    e.require(set(r["protocol"]) == set(original["protocol"]), "Protocol membership")
    for key in protected:
        same_record(r["protocol"][key], original["protocol"][key], "Scientific contract: " + key)
    for key in (
        "cases",
        "native_geometry",
        "native_initial",
        "native_preparation",
        "cells_reference_runtime",
    ):
        same_record(r[key], original[key], "Preparation changed: " + key)
    a = r["amendment"]
    e.require(
        r["protocol"]["native_steps_s"] == a["native_steps_s"] == [6.25e-6, 3.125e-6, 1.5625e-6],
        "Native ladder",
    )
    e.require(a["overlap_step_s"] == 6.25e-6 and a["exact_overlap_records"] == 12, "Overlap scope")
    e.require(
        a["new_cells_trajectories"] == a["new_reference_solves"] == 0, "Unexpected solver rerun"
    )
    for key in (
        "physical_parameters_changed",
        "energy_definition_changed",
        "scientific_tolerances_changed",
        "production_changed",
    ):
        e.require(a[key] is False, "Expanded amendment: " + key)


def authenticate():
    e.require(
        e.sha(CAPTURE / "registration.json") == REGISTRATION_SHA
        and e.sha(CAPTURE / "completion.json") == COMPLETION_SHA,
        "Refined capture identity",
    )
    r, done = e.read(CAPTURE / "registration.json"), e.read(CAPTURE / "completion.json")
    e.require(
        done["status"] == "refined_pump_pilot_pass_pending_independent_review"
        and done["comparisons"] == 616806
        and done["native_runs"] == 36
        and done["native_observed_steps"] == 6720
        and done["observer_pairs"] == 18
        and done["exact_overlap_records"] == 12,
        "Capture scope",
    )
    for key in (
        "production_changed",
        "scientific_tolerances_changed",
        "biology_validated",
        "gpu_tested",
        "automatic_followup",
    ):
        e.require(done[key] is False, "Unregistered capture claim")
    files = diagnostic.inventory(CAPTURE)
    e.require(
        len(done["files_sha256"]) == 444
        and set(files)
        == set(done["files_sha256"])
        | {"completion.json", "launch.json", "runner.stdout.log", "runner.stderr.log"},
        "Capture membership",
    )
    e.require(
        all(files[n] == h for n, h in done["files_sha256"].items()), "Capture payload changed"
    )
    e.require(len(r["sources_sha256"]) == 641, "Frozen input coverage")
    capsule(CAPTURE, r["sources_sha256"])
    e.require(
        e.software(ROOT / r["software"]["path"], 46) == r["software"], "Capture software receipt"
    )
    original, sources = diagnostic.authenticate()
    contract(r, original)
    e.require(e.sha(DIAGNOSIS / "completion.json") == DIAGNOSIS_SHA, "Diagnosis identity")
    prior = e.read(DIAGNOSIS / "registration.json")
    hashes(DIAGNOSIS, e.read(DIAGNOSIS / "completion.json")["files_sha256"])
    capsule(DIAGNOSIS, prior["sources_sha256"])
    e.require(
        diagnostic.inventory(diagnostic.CAPTURE) == prior["failed_payload_sha256"]
        and len(prior["failed_payload_sha256"]) == 431,
        "Rejected evidence changed",
    )
    reused = {
        n: h
        for n, h in prior["failed_payload_sha256"].items()
        if n in ("mapping.json", "reference.json", "cells.json")
        or n.startswith(("cells/", "reference/"))
    }
    e.require(
        len(reused) == 213
        and r["reuse_files_sha256"] == reused
        and e.read(CAPTURE / "reuse.json")["files_sha256"] == reused,
        "Reuse manifest",
    )
    hashes(CAPTURE, reused)
    e.require(e.sha(LIFECYCLE / "completion.json") == LIFECYCLE_SHA, "Lifecycle review identity")
    hashes(LIFECYCLE, e.read(LIFECYCLE / "completion.json")["files_sha256"])
    e.authenticate()  # Frozen D115 native preparation, source and prerequisite receipts.
    for phase in ("reuse", "betse", "comparison"):
        e.require(
            e.read(CAPTURE / (phase + "-complete.json"))["status"] == "phase_pass",
            "Missing capture phase",
        )
    return r, sources, files


def source_manifest():
    paths = [
        *HERE.glob("*.py"),
        HERE.parent / "pump_pilot_diagnosis/diagnose.py",
        HERE.parent / "pump_pilot_diagnosis/native_energy.py",
        HERE.parent / "pump_loop_audit/evidence.py",
        HERE.parent / "pump_loop_audit/review.py",
        HERE.parent / "kinetic_family_audit/artifacts.py",
        ROOT / "reports/REF005C_AUDIT_HANDOFF.md",
    ]
    return {str(p.relative_to(ROOT)): e.sha(p) for p in sorted(paths)}
