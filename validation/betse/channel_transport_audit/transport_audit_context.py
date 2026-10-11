"""Read-only source, runtime, partial-record and immutable-capture authentication."""

import importlib
import importlib.abc
import importlib.metadata
import math
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import transport_independent as independent

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "channel_transport_runtime_fix"))
capture_job = importlib.import_module("runtime_job")
c, t = capture_job.c, capture_job.t
ROOT = c.ROOT
CAPTURE = ROOT / "runs/ref-004b-runtime-fix-2026-09-14/capture-01"
PLAN = HERE / "plan.json"
ANCHORS = {
    "completion.json": "e2bbd1e45f0b04845603f29f6fb932f239a22045650128989f2aa93dc0f57f09",
    "registration.json": "90dc854e2a8b32a350127325d8a49a9c8a7159deb9c08e71fdd85c02b285a322",
    "comparison.json": "4d5d491dacca611da7d3d44a89a8de63795046705790c5aaee05b8ab4772918d",
}
FORBIDDEN = ("cells", "betse", "numpy", "jax", "jaxlib", "scipy")
OPERATIONAL = {"launch.json", "runner.stdout.log", "runner.stderr.log"}
NEW_SOURCES = tuple(
    "validation/betse/channel_transport_audit/" + name
    for name in (
        "plan.json",
        "transport_audit_context.py",
        "transport_independent.py",
        "transport_audit_job.py",
        "test_transport_audit.py",
    )
) + ("docs/BETSE_CHANNEL_TRANSPORT_CLOSEOUT.md", "docs/BETSE_CHANNEL_DYNAMIC_PILOT.md")


class ModelFence(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in FORBIDDEN:
            raise RuntimeError(f"Model import forbidden by saved-data audit: {fullname}")
        return None


@contextmanager
def model_fence():
    c.require(
        not any(name.split(".")[0] in FORBIDDEN for name in sys.modules), "Model already imported"
    )
    guard = ModelFence()
    sys.meta_path.insert(0, guard)
    try:
        yield
        c.require(
            not any(name.split(".")[0] in FORBIDDEN for name in sys.modules),
            "Model appeared during audit",
        )
    finally:
        sys.meta_path.remove(guard)


def packet_hashes(packet):
    c.require(packet.is_dir() and not packet.is_symlink(), "Invalid evidence directory")
    return capture_job.setup.packet_hashes(packet)


def sources():
    names = set(capture_job.source_hashes()) | set(NEW_SOURCES)
    return {name: c.sha(ROOT / name) for name in sorted(names)}


def validate_plan(plan):
    c.require(plan == c.read(PLAN), "Audit plan changed")
    c.require(plan["capture"] == str(CAPTURE.relative_to(ROOT)), "Wrong audit target")
    for name, digest in ANCHORS.items():
        c.require(plan[name.removesuffix(".json") + "_sha256"] == digest, "Wrong audit anchor")
    c.require(
        plan["expected_comparisons"] == 37068 and plan["precision_digits"] == 80,
        "Audit numerical scope changed",
    )
    c.require(
        plan["cpu_affinity"] == [0, 1, 2, 3]
        and plan["total_timeout_seconds"] == 120
        and plan["max_artifact_bytes"] == 64 * 1024**2
        and plan["max_file_bytes"] == 32 * 1024**2,
        "Audit resources changed",
    )
    c.require(
        all(
            plan[key] is False
            for key in (
                "simulators_rerun",
                "automatic_polling",
                "automatic_retry",
                "automatic_followup",
            )
        ),
        "Unexpected automatic work",
    )


def manifest(packet, completion, registration):
    payloads = {
        "betse.json",
        "betse.log",
        "cells.json",
        "cells.log",
        "cells_definitions.json",
        "comparison.json",
        "registration.json",
        "sources.zip",
        "started.json",
        "matplotlib-cache/fontlist-v3.11.0.json",
    }
    for variant in registration["protocol"]["variants"]:
        prefix = "native/" + variant["id"] + "/"
        payloads |= {
            prefix + name
            for name in (
                "INITS/world_1.betse.gz",
                "geometry.json",
                "native.yaml",
                "preparation.json",
            )
        }
        payloads |= {
            prefix + state["id"] + "-" + boundary + ".json"
            for state in registration["protocol"]["states"]
            for boundary in ("before", "after")
        }
    hashes = packet_hashes(packet)
    c.require(
        set(hashes) == payloads | OPERATIONAL | {"completion.json"},
        "Capture packet membership changed",
    )
    c.require(set(completion["files_sha256"]) == payloads, "Capture manifest coverage changed")
    c.require(
        all(hashes[name] == digest for name, digest in completion["files_sha256"].items()),
        "Capture payload digest changed",
    )
    for name in ("runner.stdout.log", "runner.stderr.log", "cells.log"):
        c.require((packet / name).stat().st_size == 0, "Unexpected capture log content")
    return hashes


def validate_receipts(packet, registration, completion, native, cells):
    r = registration
    capture_job.validate_workers(r, native, cells, packet)
    launch, started = c.read(packet / "launch.json"), c.read(packet / "started.json")
    c.require(
        launch["status"] == "launched_detached" and launch["pid"] == started["pid"] == 2348520,
        "Capture controller identity changed",
    )
    c.require(
        launch["registration_sha256"] == ANCHORS["registration.json"]
        and launch["resources"] == r["protocol"]["resources"],
        "Capture launch registration/resources changed",
    )
    c.require(
        all(
            launch[key] is False
            for key in ("automatic_polling", "automatic_retry", "automatic_followup")
        ),
        "Capture continuation policy changed",
    )
    c.require(
        completion["schema"] == "cells.betse_channel_transport_preflight_capture@3"
        and completion["status"] == "capture_pass_pending_audit",
        "Capture is not the original pending pass",
    )
    c.require(
        completion["comparison_count"] == 37068
        and completion["failed_comparisons"] == 0
        and completion["native_preparations"] == 4
        and completion["native_single_updates"]
        == completion["cells_matched_transfers_per_backend"]
        == 12,
        "Capture numerical scope changed",
    )
    for key in (
        "configuration_amendment",
        "runtime_amendment",
        "failure_preservation_sha256",
        "runtime_failure_preservation_sha256",
    ):
        c.require(completion[key] == r[key], "Capture correction provenance changed")
    c.require(
        all(
            completion[key] is False
            for key in (
                "independent_audit_complete",
                "coupled_trajectory_qualified",
                "biology_validated",
                "gpu_tested",
                "production_changed",
                "automatic_retry",
                "automatic_followup",
            )
        ),
        "Capture overclaims qualification",
    )
    dates = [
        datetime.fromisoformat(value)
        for value in (
            r["registered_utc"],
            launch["launched_utc"],
            started["started_utc"],
            completion["finished_utc"],
        )
    ]
    c.require(
        all(
            value.tzinfo is not None and value.utcoffset() == dates[0].utcoffset()
            for value in dates
        )
        and dates == sorted(dates),
        "Capture chronology changed",
    )
    elapsed = completion["elapsed_seconds"]
    c.require(
        type(elapsed) in (int, float)
        and math.isfinite(elapsed)
        and 0 < elapsed < r["protocol"]["resources"]["total_timeout_seconds"],
        "Invalid capture duration",
    )
    c.require(
        (dates[-1] - dates[2]).total_seconds() <= elapsed <= (dates[-1] - dates[0]).total_seconds(),
        "Capture clocks disagree",
    )
    c.require(
        sum(row["elapsed_seconds"] for row in (native, cells)) < elapsed,
        "Worker elapsed accounting changed",
    )
    for name, row in (("betse", native), ("cells", cells)):
        value = row["elapsed_seconds"]
        c.require(
            type(value) in (float, int)
            and math.isfinite(value)
            and 0 < value < r["protocol"]["resources"]["worker_timeout_seconds"][name],
            "Worker exceeded registered limit",
        )
    used = sum(path.stat().st_size for path in packet.rglob("*") if path.is_file())
    c.require(
        used - (packet / "completion.json").stat().st_size
        == completion["artifact_bytes_before_receipt"]
        and used < r["protocol"]["resources"]["max_artifact_bytes"],
        "Capture artifact accounting changed",
    )
    c.require(
        all(
            path.stat().st_size <= r["protocol"]["resources"]["max_worker_file_bytes"]
            for path in packet.rglob("*")
            if path.is_file()
        ),
        "Captured file exceeds limit",
    )
    site = c.REFERENCE_PYTHON.parent.parent / "lib/python3.13/site-packages"
    installed = {
        "betse/" + str(path.relative_to(site / "betse")): c.sha(path)
        for path in (site / "betse").rglob("*.py")
    }
    c.require(
        len(installed) == 332 and installed == native["installed_python_sha256"],
        "Installed native source changed",
    )
    packages = {
        dist.metadata["Name"]: dist.version
        for dist in importlib.metadata.distributions(path=[str(site)])
    }
    c.require(packages == native["environment"]["packages"], "Installed native packages changed")
    c.require(
        all(
            importlib.metadata.version(name) == version
            for name, version in r["cells_runtime"]["packages"].items()
        ),
        "Current Cells package versions changed",
    )
    c.require(
        all(
            cells["environment"]["packages"].get(name) == version
            for name, version in r["cells_runtime"]["packages"].items()
        ),
        "Captured Cells package versions changed",
    )
    return {
        "capture_files": len(packet_hashes(packet)),
        "capture_artifact_bytes": used,
        "captured_elapsed_seconds": elapsed,
        "installed_native_python_files": len(installed),
    }


def validate_partials(packet, registration, native, cells):
    c.require(
        c.read(packet / "cells_definitions.json") == cells["definitions"],
        "Cells definition artifact differs",
    )
    before_keys = {
        "before",
        "channel_before",
        "core_initial",
        "dt_s",
        "dtype",
        "id",
        "initialized_channel",
        "metadata",
        "network_inventory",
        "ordinary_diffusivity_m2_per_s",
        "rho_channel",
        "sim_temperature_K",
        "species",
        "valence",
    }
    for variant in registration["protocol"]["variants"]:
        name = variant["id"]
        folder = packet / "native" / name
        prep = native["preparations"][name]
        c.require(
            c.read(folder / "geometry.json") == prep["geometry"]
            and c.read(folder / "preparation.json") == prep,
            "Native preparation artifacts differ",
        )
        for state in registration["protocol"]["states"]:
            row = native["rows"][name + "/" + state["id"]]
            before = c.read(folder / (state["id"] + "-before.json"))
            c.require(
                set(before) == before_keys
                and all(row[key] == value for key, value in before.items()),
                "Native before artifact differs",
            )
            c.require(
                c.read(folder / (state["id"] + "-after.json")) == row,
                "Native after artifact differs",
            )


def load_capture():
    c.require(
        all(c.sha(CAPTURE / name) == digest for name, digest in ANCHORS.items()),
        "Capture anchor changed",
    )
    r = capture_job.authenticate(CAPTURE)
    c.require(c.inspect_source() == r["upstream"], "Pinned native checkout changed")
    completion = c.read(CAPTURE / "completion.json")
    hashes = manifest(CAPTURE, completion, r)
    native, cells, comparison = (
        c.read(CAPTURE / name) for name in ("betse.json", "cells.json", "comparison.json")
    )
    provenance = validate_receipts(CAPTURE, r, completion, native, cells)
    validate_partials(CAPTURE, r, native, cells)
    return {
        "registration": r,
        "completion": completion,
        "native": native,
        "cells": cells,
        "comparison": comparison,
        "hashes": hashes,
        "provenance": provenance,
    }


def numerical_audit(data):
    checker = importlib.import_module("transport_check")
    replay = checker.evaluate(data["registration"], data["native"], data["cells"])
    c.require(replay == data["comparison"], "Frozen comparison does not replay exactly")
    rebuilt = independent.rebuild(data["registration"], data["native"], data["cells"])
    summary = independent.reconcile(
        rebuilt, data["comparison"], data["registration"]["protocol"]["tolerances"]
    )
    return summary, rebuilt


def test_receipt(path):
    from xml.etree import ElementTree as ET

    c.require(path.is_file() and path.is_relative_to(ROOT / "reports"), "Missing audit test XML")
    suites = ET.parse(path).getroot()
    suites = [suites] if suites.tag == "testsuite" else list(suites.findall("testsuite"))
    identities = []
    for suite in suites:
        rows = list(suite.findall("testcase"))
        c.require(
            len(rows) == int(suite.attrib["tests"])
            and all(
                int(suite.attrib.get(key, 0)) == 0 for key in ("failures", "errors", "skipped")
            ),
            "Audit preflight did not pass",
        )
        c.require(
            all(
                not any(row.find(key) is not None for key in ("failure", "error", "skipped"))
                for row in rows
            ),
            "Rejected audit test",
        )
        identities += [row.attrib["classname"] + "::" + row.attrib["name"] for row in rows]
    original = c.read(CAPTURE / "registration.json")["software_preflight"]["identities"]
    new = set(identities) - set(original)
    c.require(
        len(identities) == len(set(identities))
        and len(original) == 152
        and set(original) <= set(identities),
        "Original 152 test identities missing or duplicated",
    )
    c.require(
        len(new) >= 30
        and all("channel_transport_audit.test_transport_audit::" in name for name in new),
        "Wrong audit test coverage",
    )
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": c.sha(path),
        "tests": len(identities),
        "previous_tests": 152,
        "new_tests": len(new),
        "identities": sorted(identities),
    }
