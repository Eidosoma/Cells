"""D103 immutable failed-capture provenance; no simulator or numerical imports."""

import ast
import hashlib
import importlib
import json
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "channel_release_preflight"))
previous = importlib.import_module("release_context")
previous_job = importlib.import_module("release_job")
c, io, ROOT = previous.c, previous.io, previous.ROOT
model_fence, packet_hashes = previous.audit.model_fence, previous.audit.packet_hashes
PLAN = HERE / "plan.json"
CAPTURE = ROOT / "runs/ref-004d-release-preflight-2026-09-15/capture-01"
ANCHORS = {
    "registration.json": "5d4f24d7c933ae637957905110ef792684c05d30f31d667da327ebc39a6bd52a",
    "failure.json": "a42ff28ee28780f03aa07e40e5efa9225f9657cc8096708b29d5a3639d52b532",
    "betse.json": "ce3e650ec43e140458c4dae8bc68f5a6b0a47b99382bfb0267c5e514789aa94e",
    "launch.json": "67de69b25120068d354473ada9b1b3420f0f71fb6085bc777bd56fc45684137a",
}
NEW_SOURCES = tuple(
    "validation/betse/channel_release_review/" + name
    for name in (
        "plan.json",
        "review_context.py",
        "review_math.py",
        "review_check.py",
        "review_job.py",
        "test_release_review.py",
        "numpy_source/origin.json",
        "numpy_source/loops_utils.h.src",
        "numpy_source/LICENSE.txt",
    )
) + ("docs/BETSE_CHANNEL_RELEASE_REVIEW.md",)


def validate_plan(plan):
    c.require(
        json.dumps(plan, sort_keys=True, allow_nan=False)
        == json.dumps(c.read(PLAN), sort_keys=True, allow_nan=False),
        "Unregistered saved-input review",
    )
    expected = {
        "schema": "cells.betse_channel_release_review_plan@1",
        "decision": "D103",
        "capture": str(CAPTURE.relative_to(ROOT)),
        "capture_files": 605,
        "capture_source_inputs": 165,
        "fresh_phases": 144,
        "saved_single_updates": 288,
        "input_applications": 288,
        "observer_pairs": 72,
        "zero_flux_mean_rows": 1776,
        "mean_extent": 30,
        "original_failure_preserved": True,
    }
    c.require(all(plan[k] == v for k, v in expected.items()), "Review scope changed")
    for key in (
        "captured_values_changed",
        "physical_tolerances_changed",
        "simulators_rerun",
        "reference_integrator_rerun",
        "production_changed",
        "release_response_qualified",
        "biology_validated",
        "gpu_tested",
        "automatic_polling",
        "automatic_retry",
        "automatic_followup",
    ):
        c.require(plan[key] is False, "Expanded review scope: " + key)


def reduction_sources():
    origin = c.read(HERE / "numpy_source/origin.json")
    c.require(
        c.sha(HERE / "numpy_source/loops_utils.h.src") == origin["source_sha256"]
        and c.sha(HERE / "numpy_source/LICENSE.txt") == origin["license_sha256"],
        "Pinned NumPy source/license changed",
    )
    for name, digest in origin["runtime_files_sha256"].items():
        c.require(c.sha(ROOT / name) == digest, "Pinned reduction runtime changed: " + name)
    version_path = next(n for n in origin["runtime_files_sha256"] if n.endswith("/version.py"))
    assignments = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in ast.parse((ROOT / version_path).read_text()).body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Constant)
    }
    c.require(
        assignments["version"] == origin["installed_version"]
        and assignments["git_revision"] == origin["git_revision"],
        "Installed NumPy revision differs from cited reduction source",
    )
    return origin


def sources():
    return previous.sources() | {name: c.sha(ROOT / name) for name in NEW_SOURCES}


def reports():
    return previous.reports() | {
        name: c.sha(ROOT / name)
        for name in (
            "reports/ref-004d-release-preflight-checks-07.xml",
            "reports/REF004D_RELEASE_PREFLIGHT_FAILURE.md",
            "reports/REF004D_RELEASE_REVIEW_HANDOFF.md",
            "reports/ref-004d-release-review-checks-01.xml",
        )
    }


def capture_membership(native):
    expected = {
        "registration.json",
        "sources.zip",
        "launch.json",
        "started.json",
        "betse-started.json",
        "betse.log",
        "betse.json",
        "failure.json",
        "runner.stdout.log",
        "runner.stderr.log",
        "matplotlib-cache/fontlist-v3.11.0.json",
    }
    for group in native["preparations"]:
        expected |= {
            f"native/{group}/{name}"
            for name in (
                "native.yaml",
                "preparation.json",
                "INITS/world_1.betse.gz",
            )
        }
    for key, modes in native["records"].items():
        for mode in modes:
            expected |= {
                f"native/{key}/{mode}/{name}"
                for name in (
                    "fixture.json",
                    "initial.json.gz",
                    "input-applied.json.gz",
                    "result.json.gz",
                )
            }
    return expected


def load_capture():
    for name, digest in ANCHORS.items():
        c.require(c.sha(CAPTURE / name) == digest, "Failed capture anchor changed: " + name)
    r = previous.authenticate(CAPTURE)
    native = previous_job.validate_worker(r, CAPTURE)
    failure = c.read(CAPTURE / "failure.json")
    c.require(
        failure["status"] == "release_input_preflight_failed_not_qualified"
        and failure["stage"] == "independent_boundary_comparison"
        and "double-transferred channel material" in failure["traceback"],
        "Original capture failure changed",
    )
    c.require(
        len(r["sources_sha256"]) == 165
        and r["tests"]["tests"] == 71
        and native["fresh_phases"] == 144
        and native["single_updates"] == 288
        and native["observer_pairs"] == 72
        and len(native["records"]) == 72,
        "Failed capture is not the completed native panel",
    )
    hashes = packet_hashes(CAPTURE)
    c.require(
        len(hashes) == 605 and set(hashes) == capture_membership(native), "Capture membership"
    )
    origin = reduction_sources()
    c.require(
        native["environment"]["packages"]["numpy"] == origin["installed_version"],
        "Captured NumPy version differs",
    )
    return r, native, hashes


def test_receipt(path):
    c.require(path.is_relative_to(ROOT / "reports") and path.is_file(), "Missing review XML")
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    names = []
    for suite in suites:
        rows = list(suite.findall("testcase"))
        c.require(
            len(rows) == int(suite.attrib["tests"])
            and all(int(suite.attrib.get(k, 0)) == 0 for k in ("failures", "errors", "skipped")),
            "Incomplete or failed saved-review software",
        )
        for row in rows:
            c.require(
                not any(row.find(k) is not None for k in ("failure", "error", "skipped")),
                "Failed review test",
            )
            names.append(row.attrib["classname"] + "::" + row.attrib["name"])
    c.require(
        len(names) >= 40
        and len(set(names)) == len(names)
        and all("channel_release_review.test_release_review::" in n for n in names),
        "Review software coverage differs",
    )
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": c.sha(path),
        "tests": len(names),
        "identities": sorted(names),
    }


def authenticate(output):
    r = c.read(output / "registration.json")
    c.require(r["schema"] == "cells.betse_channel_release_review_registration@1", "Review schema")
    validate_plan(r["plan"])
    c.require(
        r["anchors"] == ANCHORS and r["capture"] == str(CAPTURE.relative_to(ROOT)),
        "Review target changed",
    )
    c.require(r["sources_sha256"] == sources(), "Review sources changed")
    c.require(r["historical_reports_sha256"] == reports(), "Review reports changed")
    c.require(r["capture_sha256"] == packet_hashes(CAPTURE), "Saved capture changed")
    c.require(r["reduction_sources"] == reduction_sources(), "Reduction source contract changed")
    c.require(r["tests"] == test_receipt(ROOT / r["tests"]["path"]), "Review software changed")
    c.require(r["forbidden_imports"] == list(previous.audit.FORBIDDEN), "Model fence changed")
    with zipfile.ZipFile(output / "sources.zip") as archive:
        names = archive.namelist()
        c.require(
            len(names) == len(set(names)) and set(names) == set(r["sources_sha256"]),
            "Review capsule membership",
        )
        c.require(
            all(
                hashlib.sha256(archive.read(n)).hexdigest() == h
                for n, h in r["sources_sha256"].items()
            ),
            "Review capsule bytes",
        )
    return r
