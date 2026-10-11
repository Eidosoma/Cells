"""Versioned orchestration inputs; the first trajectory and all physics stay frozen."""

import xml.etree.ElementTree as ET
from datetime import UTC, datetime

import contact as c
import trajectory_context as original
import trajectory_failure as prior

PROTOCOL = c.HERE / "trajectory_refinement_protocol.json"
PRESERVATION = prior.PRESERVATION
SCOPE = (
    "REF-003d v2: refine the failed native step ladder; unchanged 1 ms seven-cell "
    "passive/blocked model, Cells runs and numerical criteria"
)
AMENDMENT = {
    "revision": 2,
    "scope": SCOPE,
    "native_steps_s": [0.000025, 0.0000125, 0.00000625],
    "max_artifact_bytes": 128 * 1024 * 1024,
}


def validate_protocol(protocol):
    c.require(
        protocol == c.read(original.PROTOCOL) | AMENDMENT,
        "Undeclared refinement amendment: retain physics, cases, Cells runs and tolerances",
    )


def authenticate():
    parent = prior.retained()
    accepted = original.authenticate()
    saved = c.read(PRESERVATION)
    c.require(
        saved["accepted_sources"] == accepted["implementation_files_sha256"]
        and saved["runtime"] == accepted["runtime"],
        "Accepted context changed",
    )
    audit = c.read(prior.AUDIT)
    c.require(
        audit["status"] == "rejection_confirmed"
        and audit["qualified"] is False
        and audit["anchors"] == prior.ANCHORS
        and audit["preservation_sha256"] == c.sha(PRESERVATION),
        "Failed-panel audit differs",
    )
    return parent


def validate_registration(registered):
    parent = authenticate()
    validate_protocol(registered["protocol"])
    c.require(
        registered["schema"] == "cells.betse_trajectory_refinement_registration@1",
        "Refinement registration schema differs",
    )
    c.require(registered["amendment"] == AMENDMENT, "Amendment record differs")
    c.require(
        registered["parent_registration_sha256"] == prior.ANCHORS["registration.json"]
        and registered["failure_audit_sha256"] == c.sha(prior.AUDIT)
        and registered["preservation_sha256"] == c.sha(PRESERVATION),
        "Refinement provenance differs",
    )
    for name in (
        "base_protocol",
        "geometry",
        "settings",
        "cells_runtime",
        "cells_definitions",
        "upstream",
    ):
        c.require(
            registered[name] == parent[name],
            "Unchanged preparation/runtime/Cells definitions differ",
        )
    c.require(prior.NEW_FILES <= set(registered["sources"]), "Incomplete refinement capsule")
    c.require(
        all(c.sha(c.HERE / name) == digest for name, digest in registered["sources"].items()),
        "Refinement source changed",
    )


def preservation_check():
    authenticate()
    baseline = c.read(PRESERVATION)["baseline_sha256"]
    changed = {
        name: {"before": digest, "after": c.sha(c.ROOT / name)}
        for name, digest in baseline.items()
        if c.sha(c.ROOT / name) != digest
    }
    c.require(set(changed) <= prior.ALLOWED_DOCUMENT_EDITS, "Unexpected pre-existing edit")
    return {
        "baseline_files": len(baseline),
        "unchanged_baseline_files": len(baseline) - len(changed),
        "changed_documents": changed,
        "accepted_implementation_files_unchanged": 352,
        "production_modules_unchanged": 51,
    }


def prelaunch(test_receipt, expected_tests, receipt):
    validate_protocol(c.read(PROTOCOL))
    result = preservation_check()
    suites = list(ET.parse(test_receipt).getroot().iter("testsuite"))
    counts = {
        name: sum(int(s.get(name, 0)) for s in suites)
        for name in ("tests", "failures", "errors", "skipped")
    }
    c.require(
        counts == {"tests": expected_tests, "failures": 0, "errors": 0, "skipped": 0},
        "Incomplete adapter preflight",
    )
    c.write(
        receipt,
        result
        | {
            "schema": "cells.betse_trajectory_refinement_prelaunch@1",
            "status": "pass",
            "checked_utc": datetime.now(UTC).isoformat(),
            "test_counts": counts,
            "test_receipt_sha256": c.sha(test_receipt),
            "protocol_sha256": c.sha(PROTOCOL),
            "preservation_sha256": c.sha(PRESERVATION),
            "sources": original.sources(),
        },
    )
    return result | {"tests": counts}
