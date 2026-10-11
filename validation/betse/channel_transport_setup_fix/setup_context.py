"""A configuration-only amendment over frozen REF-004b sources and failure evidence."""

import hashlib
import importlib
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "channel_transport_preflight"
sys.path.insert(0, str(OLD))
t = importlib.import_module("transport_protocol")
base_job = importlib.import_module("transport_job")
c = t.c
AMENDMENT = HERE / "amendment.json"
FAILED = c.ROOT / "runs/ref-004b-transport-2026-09-14/capture-01"
PRESERVED = c.ROOT / "reports/ref-004b-setup-fix-preservation.json"
FAILURE_SHA = "e0d4a28641be602862abec1667be15743606ed30da4016cb73523302a50f69f1"
REGISTRATION_SHA = "bde5e58153cbe955252bad47b216fad2b6a9cfa449691e3f8f2ac64b3a31dcbc"


def configuration(template, base, protocol, variant, directory):
    """Only this field changes. In particular optional reaction/transport lists stay null."""
    conf = t.configuration(template, base, protocol, variant, directory)
    c.require(conf["general network"]["biomolecules"] is None, "Original configuration changed")
    conf["general network"]["biomolecules"] = []
    return conf


def packet_hashes(directory):
    paths = sorted(directory.rglob("*"))
    c.require(not any(p.is_symlink() for p in paths), "Symlink in evidence packet")
    return {str(p.relative_to(directory)): c.sha(p) for p in paths if p.is_file()}


def validate_amendment(amendment):
    c.require(amendment == c.read(AMENDMENT), "Unregistered setup amendment")
    c.require(
        amendment["configuration_path"] == ["general network", "biomolecules"]
        and amendment["original_value"] is None
        and amendment["corrected_value"] == [],
        "Only null-to-empty-sequence correction is permitted",
    )
    c.require(c.sha(t.PROTOCOL) == amendment["base_protocol_sha256"], "Numerical protocol changed")
    c.require(
        amendment["failure_sha256"] == FAILURE_SHA
        and amendment["original_registration_sha256"] == REGISTRATION_SHA,
        "Wrong failed attempt",
    )


def authenticate_original():
    """Hash/read only: do not rerun an old audit or use its growing-directory guard."""
    c.require(c.sha(FAILED / "failure.json") == FAILURE_SHA, "Original failure changed")
    c.require(
        c.sha(FAILED / "registration.json") == REGISTRATION_SHA, "Original registration changed"
    )
    original = c.read(FAILED / "registration.json")
    c.require(
        original["sources_sha256"] == base_job.source_hashes(), "Frozen implementation changed"
    )
    for name, digest in original["preserved_sources_sha256"].items():
        c.require(c.sha(c.ROOT / name) == digest, f"Earlier source changed: {name}")
    with zipfile.ZipFile(FAILED / "sources.zip") as archive:
        names = archive.namelist()
        c.require(
            len(names) == len(set(names)) and set(names) == set(original["sources_sha256"]),
            "Original source capsule membership changed",
        )
        c.require(
            all(
                hashlib.sha256(archive.read(n)).hexdigest() == digest
                for n, digest in original["sources_sha256"].items()
            ),
            "Original capsule changed",
        )
    c.require(
        base_job.prior_closeout() == original["prior_closeout"], "Isolated prerequisite changed"
    )
    c.require(
        c.authenticate_cells()["runtime"] == original["cells_runtime"], "Accepted runtime changed"
    )
    c.require(c.sha(c.PRESERVATION) == original["preservation_sha256"], "Accepted anchor changed")
    t.validate_protocol(original["protocol"])
    c.require(original["base_protocol"] == c.read(t.a.PROTOCOL), "Base setup changed")
    geometry = c.ROOT / original["protocol"]["geometry_source"]
    c.require(c.sha(geometry) == original["geometry_source_sha256"], "Geometry source changed")
    c.require(
        original["expected_geometry"] == {k: c.read(geometry)[k] for k in t.GEOMETRY_FIELDS},
        "Geometry mapping changed",
    )
    c.require(
        base_job.software_receipt(c.ROOT / original["software_preflight"]["path"])
        == original["software_preflight"],
        "Original software receipt changed",
    )
    c.require(
        c.read(FAILED / "failure.json")["status"] == "failed_not_qualified",
        "Original failure reclassified",
    )
    c.require(
        not any(
            (FAILED / name).exists()
            for name in (
                "completion.json",
                "comparison.json",
                "betse.json",
                "cells.json",
                "cells.log",
            )
        ),
        "Unexpected aggregate results in failed preparation",
    )
    return original


def preserve():
    validate_amendment(c.read(AMENDMENT))
    original = authenticate_original()
    c.require(c.inspect_source() == original["upstream"], "Upstream changed since failure")
    files = packet_hashes(FAILED)
    c.write(
        PRESERVED,
        {
            "schema": "cells.betse_channel_setup_failure_preservation@1",
            "status": "preserved",
            "created_utc": datetime.now(UTC).isoformat(),
            "failure_path": str(FAILED.relative_to(c.ROOT)),
            "failure_sha256": FAILURE_SHA,
            "registration_sha256": REGISTRATION_SHA,
            "files_sha256": files,
            "artifact_bytes": sum((FAILED / n).stat().st_size for n in files),
            "original_sources_sha256": original["sources_sha256"],
            "earlier_sources_sha256": original["preserved_sources_sha256"],
            "historical_reports_sha256": {
                name: c.sha(c.ROOT / name)
                for name in (
                    "reports/REF004B_TRANSPORT_PREFLIGHT_HANDOFF.md",
                    "reports/ref-004b-transport-checks-01.xml",
                    "reports/ref-004b-transport-checks-02.xml",
                    "reports/ref-004b-transport-checks-03.xml",
                )
            },
            "completed_network_off_cases": ["native_initial", "prescribed_mh_a", "prescribed_mh_b"],
            "original_capture_qualified": False,
            "simulators_rerun": False,
        },
    )
    return {"status": "preserved", "failure_files": len(files), "receipt": str(PRESERVED)}


def authenticate_preservation():
    original = authenticate_original()
    saved = c.read(PRESERVED)
    c.require(
        saved["status"] == "preserved" and saved["files_sha256"] == packet_hashes(FAILED),
        "Failed capture bytes or membership changed",
    )
    c.require(
        saved["original_sources_sha256"] == original["sources_sha256"]
        and saved["earlier_sources_sha256"] == original["preserved_sources_sha256"],
        "Preserved source inventories changed",
    )
    for name, digest in saved["historical_reports_sha256"].items():
        c.require(c.sha(c.ROOT / name) == digest, f"Historical report changed: {name}")
    return original
