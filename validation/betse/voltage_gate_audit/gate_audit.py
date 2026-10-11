"""D088: short, source-bound saved-data closeout, with no model imports or reruns."""

import argparse
import hashlib
import importlib
import importlib.abc
import importlib.metadata
import json
import os
import signal
import sys
import time
import traceback
import zipfile
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import gate_independent as independent

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CAPTURE = ROOT / "runs/ref-004a-kv1p5-2026-09-13/capture-01"
ANCHORS = {
    "completion.json": "6e694ba8d91eec64b7bfde33b1e099047952724c25c90b0f3ba520f1265ca190",
    "registration.json": "562540ff877efab13b909af75fb14b4a5663207b0710d3ce6b5ea73c0cd788d5",
    "comparison.json": "a7fad84c0ccf5b4887d65a2d52e28b31e8b81f1a4d007ffa156139aa9a851e18",
}
FORBIDDEN = ("cells", "betse", "numpy", "jax", "jaxlib", "scipy")
PAYLOADS = {
    "betse.json",
    "betse.log",
    "cells.json",
    "cells.log",
    "comparison.json",
    "registration.json",
    "sources.zip",
    "started.json",
    "matplotlib-cache/fontlist-v3.11.0.json",
}
OPERATIONAL = {"launch.json", "runner.stdout.log", "runner.stderr.log"}
AUDIT_SOURCES = tuple(
    "validation/betse/voltage_gate_audit/" + name
    for name in ("gate_audit.py", "gate_independent.py", "test_gate_audit.py")
) + ("docs/BETSE_VOLTAGE_GATE_CLOSEOUT.md",)
REQUIRE = independent.require
LIMITS = {"total_seconds": 30, "max_artifact_bytes": 16777216, "cpu_affinity": [0, 1, 2, 3]}


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class ModelFence(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in FORBIDDEN:
            raise RuntimeError(f"Model import forbidden by saved-data audit: {fullname}")
        return None


@contextmanager
def model_fence():
    REQUIRE(
        not any(name.split(".")[0] in FORBIDDEN for name in sys.modules), "Model already imported"
    )
    guard = ModelFence()
    sys.meta_path.insert(0, guard)
    try:
        yield
    finally:
        sys.meta_path.remove(guard)


def frozen_helpers():
    sys.path.insert(0, str(HERE.parent / "voltage_gate_contact"))
    return importlib.import_module("gate_job"), importlib.import_module("gate_reference")


def packet_hashes(packet):
    paths = list(packet.rglob("*"))
    REQUIRE(not any(p.is_symlink() for p in paths), "Symlink in saved packet")
    return {str(p.relative_to(packet)): sha(p) for p in paths if p.is_file()}


def manifest(packet, completion):
    hashes = packet_hashes(packet)
    REQUIRE(
        set(hashes) == PAYLOADS | OPERATIONAL | {"completion.json"}, "Saved packet coverage differs"
    )
    REQUIRE(set(completion["files_sha256"]) == PAYLOADS, "Wrong completion payload coverage")
    REQUIRE(
        all(hashes[name] == digest for name, digest in completion["files_sha256"].items()),
        "Saved payload checksum differs",
    )
    REQUIRE(
        all(
            (packet / name).stat().st_size == 0
            for name in ("runner.stdout.log", "runner.stderr.log")
        ),
        "Unexpected controller log",
    )
    return hashes


def runtime_and_receipts(packet, r, completion, native, cells):
    job, _ = frozen_helpers()
    c = job.c
    job.validate_workers(r, native, cells, ANCHORS["registration.json"])
    launch, started = c.read(packet / "launch.json"), c.read(packet / "started.json")
    REQUIRE(
        launch["status"] == "launched_detached" and launch["pid"] == started["pid"] == 2228226,
        "Controller identity differs",
    )
    REQUIRE(
        launch["registration_sha256"]
        == completion["registration_sha256"]
        == ANCHORS["registration.json"],
        "Receipt registration differs",
    )
    REQUIRE(launch["resources"] == r["protocol"]["resources"], "Launched resource policy differs")
    REQUIRE(
        all(
            launch[key] is False
            for key in ("automatic_polling", "automatic_retry", "automatic_followup")
        ),
        "Wrong launch continuation policy",
    )
    REQUIRE(
        completion["schema"] == "cells.betse_kv1p5_contact_capture@1"
        and completion["status"] == "capture_pass_pending_audit",
        "Not the pending capture",
    )
    REQUIRE(
        completion["scope"] == r["protocol"]["scope"]
        and completion["comparison_count"] == 11266
        and completion["failed_comparisons"] == 0
        and completion["isolated_gate_protocols"] == 6
        and completion["trajectories_per_engine"] == 18,
        "Capture numerical scope differs",
    )
    REQUIRE(
        all(
            completion[key] is False
            for key in (
                "automatic_followup",
                "automatic_retry",
                "biology_validated",
                "coupled_cell_qualified",
                "gpu_tested",
                "independent_audit_complete",
                "production_changed",
            )
        ),
        "Capture overclaims scope",
    )
    dates = [
        datetime.fromisoformat(s)
        for s in (
            r["registered_utc"],
            launch["launched_utc"],
            started["started_utc"],
            completion["finished_utc"],
        )
    ]
    REQUIRE(
        all(d.utcoffset() == dates[0].utcoffset() and d.tzinfo is not None for d in dates)
        and dates == sorted(dates),
        "Capture chronology differs",
    )
    elapsed = completion["elapsed_seconds"]
    REQUIRE(
        independent.finite(elapsed)
        and 0 < elapsed <= r["protocol"]["resources"]["total_timeout_seconds"],
        "Capture duration exceeds bound",
    )
    REQUIRE(
        (dates[3] - dates[2]).total_seconds() <= elapsed <= (dates[3] - dates[0]).total_seconds(),
        "Capture clocks disagree",
    )
    REQUIRE(
        sum(row["elapsed_seconds"] for row in (native, cells)) <= elapsed, "Worker times disagree"
    )
    for name, row in (("betse", native), ("cells", cells)):
        REQUIRE(
            independent.finite(row["elapsed_seconds"])
            and 0
            < row["elapsed_seconds"]
            <= r["protocol"]["resources"]["worker_timeout_seconds"][name],
            "Worker over budget",
        )
    used = sum(p.stat().st_size for p in packet.rglob("*") if p.is_file())
    REQUIRE(
        used - (packet / "completion.json").stat().st_size
        == completion["artifact_bytes_before_receipt"]
        and used <= r["protocol"]["resources"]["max_artifact_bytes"],
        "Artifact byte accounting differs",
    )
    REQUIRE(
        all(
            (packet / name).stat().st_size <= r["protocol"]["resources"]["max_worker_file_bytes"]
            for name in ("betse.json", "cells.json", "betse.log", "cells.log")
        ),
        "Worker file over budget",
    )
    site = c.REFERENCE_PYTHON.parent.parent / "lib/python3.13/site-packages"
    installed = {
        "betse/" + str(p.relative_to(site / "betse")): sha(p)
        for p in (site / "betse").rglob("*.py")
    }
    REQUIRE(
        installed == native["installed_python_sha256"] and len(installed) == 332,
        "Current installed native bytes differ",
    )
    packages = {
        d.metadata["Name"]: d.version for d in importlib.metadata.distributions(path=[str(site)])
    }
    REQUIRE(packages == native["environment"]["packages"], "Installed reference lock changed")
    for worker in (native, cells):
        REQUIRE(worker["environment"]["python"] == "3.13.5", "Captured Python version differs")
    REQUIRE(
        all(
            cells["environment"]["packages"].get(k) == v
            for k, v in r["cells_runtime"]["packages"].items()
        ),
        "Captured Cells packages differ",
    )
    REQUIRE(
        native["input_carrier"] == "targets=None; cells=None; SimpleNamespace(dt); no native world"
        and native["state_preparation"]
        == "native equilibrium init recorded; then explicit m/h fixture",
        "Native preparation claim differs",
    )
    REQUIRE(r["protocol"]["fixture_temperature_K"] == 298.15, "Wrong channel engineering regime")
    return {
        "installed_native_python_files": len(installed),
        "capture_artifact_bytes": used,
        "captured_elapsed_seconds": elapsed,
        "initial_open_fraction_is_derived": True,
    }


def load_capture(packet=CAPTURE):
    REQUIRE(
        all(sha(packet / name) == digest for name, digest in ANCHORS.items()),
        "Capture anchor changed",
    )
    job, ref = frozen_helpers()
    c = job.c
    completion = c.read(packet / "completion.json")
    hashes = manifest(packet, completion)
    r = job.authenticate_registration(packet)
    REQUIRE(c.inspect_source() == r["upstream"], "Pinned checkout changed")
    REQUIRE(r["software_preflight"]["tests"] == 63, "Wrong original preflight count")
    native, cells, saved = (
        c.read(packet / name) for name in ("betse.json", "cells.json", "comparison.json")
    )
    provenance = runtime_and_receipts(packet, r, completion, native, cells)
    return {
        "registration": r,
        "completion": completion,
        "native": native,
        "cells": cells,
        "comparison": saved,
        "hashes": hashes,
        "provenance": provenance,
    }


def numerical_audit(data):
    _, ref = frozen_helpers()
    p, native, cells, saved = (
        data["registration"]["protocol"],
        data["native"],
        data["cells"],
        data["comparison"],
    )
    replay = ref.evaluate(p, native, cells)
    REQUIRE(replay == saved, "Frozen comparison does not replay exactly")
    rebuilt = independent.review(p, native, cells, independent.build_reference(p))
    summary = independent.match_saved(rebuilt, saved)
    return summary, rebuilt


def tests_receipt(path, r):
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    REQUIRE(bool(suites), "Missing test suites")
    identities = []
    for suite in suites:
        cases = list(suite.findall("testcase"))
        REQUIRE(
            int(suite.attrib["tests"]) == len(cases)
            and all(int(suite.attrib.get(k, 0)) == 0 for k in ("errors", "failures", "skipped")),
            "Focused regression did not pass",
        )
        for row in cases:
            REQUIRE(
                not any(row.find(k) is not None for k in ("failure", "error", "skipped")),
                "Rejected test case",
            )
            identities.append(row.attrib["classname"] + "::" + row.attrib["name"])
    old = set(r["software_preflight"]["identities"])
    new = set(identities) - old
    REQUIRE(
        len(identities) == len(set(identities)) and len(old) == 63 and old <= set(identities),
        "Original 63 test identities missing or duplicated",
    )
    REQUIRE(
        len(new) >= 20 and all("test_gate_audit::" in name for name in new),
        "Wrong audit-test coverage",
    )
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": sha(path),
        "tests": len(identities),
        "previous_tests": 63,
        "new_tests": len(new),
        "identities": sorted(identities),
        "failures": 0,
        "errors": 0,
        "skipped": 0,
    }


def alarm(_signum, _frame):
    raise TimeoutError("Short saved-data audit exceeded its 30-second budget")


def run(output, tests):
    REQUIRE(
        output.is_relative_to(ROOT / "runs")
        and output != ROOT / "runs"
        and not output.exists()
        and not output.is_relative_to(CAPTURE),
        "Use a fresh audit output directory",
    )
    output.mkdir(parents=True, exist_ok=False)
    began = time.monotonic()
    signal.signal(signal.SIGALRM, alarm)
    signal.setitimer(signal.ITIMER_REAL, LIMITS["total_seconds"])
    try:
        with model_fence():
            job, _ = frozen_helpers()
            c = job.c
            REQUIRE(sorted(os.sched_getaffinity(0)) == LIMITS["cpu_affinity"], "Wrong audit CPUs")
            data = load_capture()
            software = tests_receipt(tests, data["registration"])
            new_sources = {n: sha(ROOT / n) for n in AUDIT_SOURCES}
            registration = {
                "schema": "cells.betse_kv1p5_audit_registration@1",
                "registered_utc": datetime.now(UTC).isoformat(),
                "capture": str(CAPTURE.relative_to(ROOT)),
                "capture_sha256": data["hashes"],
                "sources_sha256": new_sources,
                "limits": LIMITS,
                "tests": software,
                "model_imports_forbidden": list(FORBIDDEN),
            }
            c.write(output / "registration.json", registration)
            with zipfile.ZipFile(
                output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED
            ) as archive:
                for name in new_sources:
                    archive.write(ROOT / name, arcname=name)
            summary, rebuilt = numerical_audit(data)
            c.write(output / "independent-comparisons.json", rebuilt)
            REQUIRE(
                packet_hashes(CAPTURE) == data["hashes"], "Original packet changed during audit"
            )
            job.authenticate_registration(CAPTURE)
            REQUIRE(
                {n: sha(ROOT / n) for n in AUDIT_SOURCES} == new_sources, "Audit source changed"
            )
            REQUIRE(
                tests_receipt(tests, data["registration"]) == software, "Software receipt changed"
            )
            payloads = {
                str(p.relative_to(output)): sha(p) for p in output.rglob("*") if p.is_file()
            }
            REQUIRE(
                sum(p.stat().st_size for p in output.rglob("*") if p.is_file()) + 65536
                <= LIMITS["max_artifact_bytes"],
                "Audit artifact budget exceeded",
            )
            receipt = (
                summary
                | data["provenance"]
                | {
                    "schema": "cells.betse_kv1p5_closeout@1",
                    "status": "isolated_gate_audit_closed",
                    "finished_utc": datetime.now(UTC).isoformat(),
                    "elapsed_seconds": time.monotonic() - began,
                    "capture_completion_sha256": ANCHORS["completion.json"],
                    "files_sha256": payloads,
                    "frozen_comparisons_replayed": 11266,
                    "capture_files_unchanged": len(data["hashes"]),
                    "accepted_implementation_files_unchanged": 352,
                    "production_modules_unchanged": 51,
                    "tests": software,
                    "isolated_gate_qualified": True,
                    "scope": data["registration"]["protocol"]["scope"],
                    "trajectory_backend": "jax_jit",
                    "kinetic_and_one_step_backends": ["numpy", "jax_eager", "jax_jit"],
                    "fixture_temperature_K": 298.15,
                    "biology_validated": False,
                    "gpu_tested": False,
                    "coupled_cell_qualified": False,
                    "model_imports": [],
                    "simulators_rerun": False,
                    "original_evidence_rewritten": False,
                    "automatic_followup": False,
                }
            )
            REQUIRE(
                receipt["elapsed_seconds"] <= LIMITS["total_seconds"], "Audit exceeded wall budget"
            )
            c.write(output / "completion.json", receipt)
            return {
                k: receipt[k]
                for k in (
                    "status",
                    "elapsed_seconds",
                    "independent_comparisons",
                    "failed_comparisons",
                    "native_finest_max_gate_error",
                    "cells_finest_max_gate_error",
                )
            }
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        with (output / "failure.json").open("x") as stream:
            json.dump(
                {
                    "status": "audit_failed_not_qualified",
                    "elapsed_seconds": time.monotonic() - began,
                    "traceback": traceback.format_exc(),
                    "automatic_retry": False,
                },
                stream,
                indent=2,
            )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tests", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output.resolve(), args.tests.resolve()), sort_keys=True))
