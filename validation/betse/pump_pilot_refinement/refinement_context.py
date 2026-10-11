"""Explicit D119 amendment; preserve the rejected pilot and its numerical contract."""

import copy
import hashlib
import importlib
import math
import shutil
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pump_matched_pilot"))
base = importlib.import_module("pilot_context")
c = base.c
PROTOCOL = HERE / "protocol.json"
PRIOR = c.ROOT / "runs/ref-005c-matched-pump-2026-09-16/pilot-01"
DIAGNOSIS = c.ROOT / "runs/ref-005c-pilot-diagnosis-2026-09-16/review-01"
PRIOR_SHA = "2dc09a3d112b1f0efc3a03d0a43f9cc2a395078553881ba7a7cc33497dff269b"
DIAGNOSIS_SHA = "c6b5f18258d1fa14c2e742fa76b582c0bc7c32ff9e729d96800d8475830a8bb3"


def inventory(directory):
    paths = list(directory.rglob("*"))
    c.require(not any(p.is_symlink() for p in paths), "Symlink in evidence")
    c.require(all(p.is_file() or p.is_dir() for p in paths), "Nonregular evidence")
    return {str(p.relative_to(directory)): c.sha(p) for p in sorted(paths) if p.is_file()}


def prior():
    c.require(
        c.sha(PRIOR / "registration.json") == PRIOR_SHA
        and c.sha(DIAGNOSIS / "completion.json") == DIAGNOSIS_SHA,
        "Prior identities changed",
    )
    done, review = c.read(DIAGNOSIS / "completion.json"), c.read(DIAGNOSIS / "registration.json")
    c.require(
        done["status"] == "failed_pilot_diagnosed_not_qualified"
        and done["failed_comparisons"] == 6,
        "Prior diagnosis scope",
    )
    c.require(
        not (DIAGNOSIS / "failure.json").exists() and not (PRIOR / "completion.json").exists(),
        "Prior disposition changed",
    )
    c.require(
        all(c.sha(DIAGNOSIS / n) == h for n, h in done["files_sha256"].items()),
        "Diagnosis payload changed",
    )
    c.require(inventory(PRIOR) == review["failed_payload_sha256"], "Sealed failed payload changed")
    original = c.read(PRIOR / "registration.json")
    for hashes in (original["sources_sha256"], review["sources_sha256"]):
        c.require(
            all(c.sha(c.ROOT / n) == h for n, h in hashes.items()), "Preserved source changed"
        )
    modules = {n for n in original["sources_sha256"] if n.startswith("src/cells/")}
    c.require(
        len(modules) == 55
        and modules == {str(p.relative_to(c.ROOT)) for p in (c.ROOT / "src/cells").rglob("*.py")},
        "Production inventory changed",
    )
    with zipfile.ZipFile(PRIOR / "sources.zip") as archive:
        c.require(
            len(archive.namelist()) == len(original["sources_sha256"])
            and set(archive.namelist()) == set(original["sources_sha256"]),
            "Prior capsule membership",
        )
        c.require(
            all(
                hashlib.sha256(archive.read(n)).hexdigest() == h
                for n, h in original["sources_sha256"].items()
            ),
            "Prior capsule changed",
        )
    c.require(base.prior() == original["prior"], "Native lifecycle prerequisite changed")
    return dict(
        registration_sha256=PRIOR_SHA,
        diagnosis_completion_sha256=DIAGNOSIS_SHA,
        failed_payload_files=len(review["failed_payload_sha256"]),
    )


def sources():
    names = set(c.read(PRIOR / "registration.json")["sources_sha256"])
    names |= set(c.read(DIAGNOSIS / "registration.json")["sources_sha256"])
    names |= {str(p.relative_to(c.ROOT)) for p in HERE.iterdir() if p.suffix in (".py", ".json")}
    names |= {
        "reports/REF005C_PILOT_FAILURE_DIAGNOSIS.md",
        "docs/BETSE_PUMP_REFINEMENT.md",
        "reports/REF005C_REFINEMENT_HANDOFF.md",
    }
    return {n: c.sha(c.ROOT / n) for n in sorted(names)}


def validate(amendment):
    c.require(amendment == c.read(PROTOCOL), "Unregistered refinement amendment")
    c.require(
        amendment["prior_registration_sha256"] == PRIOR_SHA
        and amendment["diagnosis_completion_sha256"] == DIAGNOSIS_SHA,
        "Amendment prerequisite changed",
    )
    c.require(
        amendment["native_steps_s"] == [6.25e-6, 3.125e-6, 1.5625e-6]
        and amendment["overlap_step_s"] == 6.25e-6,
        "Refinement ladder changed",
    )
    c.require(
        amendment["native_runs"] == 36
        and amendment["observer_pairs"] == 18
        and amendment["exact_overlap_records"] == 12,
        "Native coverage",
    )
    c.require(
        amendment["native_observed_steps"]
        == 6 * sum(round(0.001 / h) for h in amendment["native_steps_s"])
        == 6720,
        "Observed update coverage",
    )
    c.require(
        amendment["new_cells_trajectories"] == amendment["new_reference_solves"] == 0,
        "Unexpected simulator/reference rerun",
    )
    for name in (
        "physical_parameters_changed",
        "energy_definition_changed",
        "scientific_tolerances_changed",
        "production_changed",
        "automatic_polling",
        "automatic_retry",
        "automatic_followup",
    ):
        c.require(amendment[name] is False, "Scientific or automatic scope expanded")
    bounds = amendment["resources"]
    c.require(
        bounds["per_file_bytes"] == 256 * 1024**2 and bounds["artifact_bytes"] == 2 * 1024**3,
        "Recording bounds changed",
    )


def effective_protocol(amendment):
    validate(amendment)
    original = c.read(PRIOR / "registration.json")["protocol"]
    plan = copy.deepcopy(original)
    plan.update(
        schema="cells.betse_refined_pump_pilot@1",
        decision="D119",
        scope=(
            "Refined native 1 ms pump pilot; reuse preserved Cells/reference evidence; "
            "no error mimicry"
        ),
        native_steps_s=amendment["native_steps_s"],
        resources=amendment["resources"],
    )
    protected = set(original) - {"schema", "decision", "scope", "native_steps_s", "resources"}
    c.require(all(plan[k] == original[k] for k in protected), "Numerical/physical contract changed")
    for h in plan["native_steps_s"]:
        c.require(
            all(
                math.isclose(t / h, round(t / h), rel_tol=0, abs_tol=1e-10)
                for t in plan["common_times_s"]
            ),
            "Native grid misses common times",
        )
    return plan


def reuse_manifest():
    files = c.read(DIAGNOSIS / "registration.json")["failed_payload_sha256"]
    selected = {
        n: h
        for n, h in files.items()
        if n in ("mapping.json", "reference.json", "cells.json")
        or n.startswith(("cells/", "reference/"))
    }
    c.require(
        {"mapping.json", "reference.json", "cells.json"} <= selected.keys(), "Missing reuse records"
    )
    return selected


def reuse(output, manifest):
    c.require(manifest == reuse_manifest(), "Reuse selection changed")
    for name, expected in manifest.items():
        source, target = PRIOR / name, output / name
        c.require(c.sha(source) == expected and not target.exists(), "Reuse source/target changed")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        c.require(c.sha(target) == expected, "Reuse copy differs")
    return dict(
        status="saved_evidence_reused",
        files_sha256=manifest,
        cells_trajectories=24,
        reference_solves=18,
        restart_suffixes=6,
        new_solver_runs=0,
    )


def overlap(actual, previous):
    # Canonical JSON retains signed zero; plain float equality would not.
    c.require(base.digest(actual) == base.digest(previous), "Repeated native overlap differs")
    return base.digest(actual)
