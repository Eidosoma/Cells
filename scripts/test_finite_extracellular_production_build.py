"""Current production and four explicitly preserved historical test contexts."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import test_cells_build as previous  # noqa: E402
from scripts.audit_preserved_finite_extracellular_reference import (  # noqa: E402
    ARCHIVE_SHA,
    extract_sources,
)

DRIVER_SHA = "4102a34c4d31e2599ee40b684e31af4f5598a5b6f61b13fc8b39189169d15b99"
V1_PROSPECTIVE = "tests/unit/test_finite_extracellular_artifact_audit.py"
FINITE_HISTORICAL = tuple(
    f"tests/unit/test_{name}.py"
    for name in (
        "finite_extracellular_reference",
        "finite_extracellular_dynamics",
        "finite_extracellular_attempt_audit",
        "finite_extracellular_tangent",
        "finite_extracellular_artifact_audit_v2",
        "finite_extracellular_test_context",
    )
)
THREADS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")


def preserved_workspace(destination):
    """Keep historical nested subprocesses on the already pinned interpreter.

    Only the environment directory is linked. Sources and scientific evidence
    retain the independent copies required by their unchanged no-links guards.
    """
    workspace = previous.reference_workspace(destination, extract=extract_sources)
    (workspace / ".venv").symlink_to(Path(sys.prefix), target_is_directory=True)
    return workspace


def execute_preserved(output):
    output.mkdir()
    report = output / "preserved-finite-reference.xml"
    with tempfile.TemporaryDirectory(prefix="cells-finite-reference-tests-") as temporary:
        workspace = preserved_workspace(Path(temporary) / "Cells")
        command = [
            "taskset",
            "-c",
            "0-3",
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-W",
            "error",
            f"--junitxml={report}",
            *FINITE_HISTORICAL,
        ]
        worker = subprocess.run(
            command,
            cwd=workspace,
            env=os.environ | dict.fromkeys(THREADS, "1") | {"PYTHONPATH": str(workspace / "src")},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    log = output / "preserved-finite-reference.log"
    with log.open("x") as handle:
        handle.write(worker.stdout)
    print(worker.stdout[-2500:], flush=True)
    suites = ET.parse(report).getroot().findall("testsuite")
    record = {
        "exit_code": worker.returncode,
        "junit_sha256": previous.sha(report),
        "log_sha256": previous.sha(log),
        **{
            k: sum(int(s.get(k, 0)) for s in suites)
            for k in ("tests", "failures", "errors", "skipped")
        },
        "seconds": sum(float(s.get("time", 0)) for s in suites),
    }
    result = {
        "status": "pass"
        if all(record[k] == 0 for k in ("exit_code", "failures", "errors", "skipped"))
        else "failed",
        "contexts": {"preserved-finite-reference": record},
        "total_tests": record["tests"],
        "archive_sha256": ARCHIVE_SHA,
        "test_files": list(FINITE_HISTORICAL),
    }
    with (output / "verification.json").open("x") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return result


def run_tests(output):
    if os.environ.get("PYTEST_ADDOPTS") or os.environ.get("PYTEST_PLUGINS"):
        raise ValueError("Require explicit test routing without inherited pytest overrides")
    if previous.sha(ROOT / "scripts/test_cells_build.py") != DRIVER_SHA:
        raise ValueError("Preserved underlying test driver changed")
    failure = ROOT / "runs/num-009-2026-09-10/reference-01/failure.json"
    if previous.sha(failure) != "7dd501991ab3c61144d3f8862f91a8b76c146619e5c554b2b9fd46a5c87f3e67":
        raise ValueError("Historical v1 stopped attempt changed")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    options = " ".join(f"--ignore={name}" for name in (*FINITE_HISTORICAL, V1_PROSPECTIVE))
    prior = os.environ.get("PYTEST_ADDOPTS")
    try:
        os.environ["PYTEST_ADDOPTS"] = options
        current = previous.run_tests(output / "current", only="current")
    finally:
        if prior is None:
            os.environ.pop("PYTEST_ADDOPTS", None)
        else:
            os.environ["PYTEST_ADDOPTS"] = prior
    historical = previous.run_tests(output / "historical", only="reference")
    finite = execute_preserved(output / "finite-reference")
    children = {"current": current, "historical": historical, "finite-reference": finite}
    result = {
        "schema": "cells.finite_extracellular_production_build_matrix@1",
        "status": "pass" if all(r["status"] == "pass" for r in children.values()) else "failed",
        "contexts": current["contexts"] | historical["contexts"] | finite["contexts"],
        "total_tests": sum(r["total_tests"] for r in children.values()),
        "current_pytest_addopts": options,
        "historical_pytest_addopts": None,
        "unexecuted_prospective_suite": {
            "file": V1_PROSPECTIVE,
            "sha256": previous.sha(ROOT / V1_PROSPECTIVE),
            "tests": 13,
            "reason": "V1 stopped without complete evidence; these are not passing coverage.",
            "maintained_replacement": "tests/unit/test_finite_extracellular_artifact_audit_v2.py",
        },
        "preserved_finite_source_sha256": ARCHIVE_SHA,
        "underlying_driver_sha256": DRIVER_SHA,
        "driver_sha256": previous.sha(__file__),
        "child_receipts_sha256": {
            name: previous.sha(output / name / "verification.json") for name in children
        },
    }
    with (output / "verification.json").open("x") as handle:
        json.dump(result, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = run_tests(args.output)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    raise SystemExit(0 if receipt["status"] == "pass" else 1)
