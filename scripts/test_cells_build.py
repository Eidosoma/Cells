"""Run current Cells tests and source-pinned historical tests in explicit contexts.

Historical NUM-005 unit tests authenticate 0.10.0 and its original packaging.
SPEC-006/NUM-007 similarly authenticate 0.11.0 in a third context.
They are not tests of the current production engine. Give them an isolated
workspace with authenticated old production sources, unchanged reference code
and read-only use of the existing evidence. Never patch a provenance validator.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_preserved_multispecies_reference import (  # noqa: E402
    ARCHIVE_SHA,
    extract_sources,
)
from scripts.audit_preserved_physical_ionic_graph_reference import (  # noqa: E402
    ARCHIVE_SHA as PHYSICAL_GRAPH_ARCHIVE_SHA,
)
from scripts.audit_preserved_physical_ionic_graph_reference import (  # noqa: E402
    extract_sources as extract_physical_graph_sources,
)
from scripts.audit_preserved_voltage_gated_reference import (  # noqa: E402
    ARCHIVE_SHA as CHANNEL_ARCHIVE_SHA,
)
from scripts.audit_preserved_voltage_gated_reference import (  # noqa: E402
    extract_sources as extract_channel_sources,
)

PHYSICAL_GRAPH_HISTORICAL = tuple(
    f"tests/unit/test_{name}.py"
    for name in (
        "physical_ionic_graph_reference",
        "physical_ionic_graph_dynamics",
        "physical_ionic_graph_artifact_audit",
    )
)

CHANNEL_HISTORICAL = tuple(
    f"tests/unit/test_{name}.py"
    for name in (
        "voltage_gated_channel_reference",
        "voltage_gated_dynamics",
        "voltage_gated_artifact_audit",
    )
)

HISTORICAL = tuple(
    f"tests/unit/test_{name}.py"
    for name in (
        "comparison_evidence",
        "graph_candidate",
        "graph_diagnostics",
        "graph_evaluation",
        "graph_evidence",
        "graph_reference_panel",
        "graph_refinement",
        "source_graph_continuation",
        "source_graph_paths",
        "source_preparations",
    )
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reference_workspace(destination, *, extract=extract_sources):
    destination = Path(destination)
    # Copy code so module __file__.resolve() identifies this workspace.
    for name in ("tests", "scripts", "configs", "docs", "data", "reports"):
        shutil.copytree(
            ROOT / name,
            destination / name,
            ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"),
        )
    # Historical path/size guards reject symlinks AND hard links. Use independent
    # files (copy-on-write where supported), preserving both those checks and the
    # real evidence. This is temporary test storage, not a new scientific session.
    required = sum(p.stat().st_size for p in (ROOT / "runs").rglob("*") if p.is_file())
    if shutil.disk_usage(destination).free < required + 256 * 2**20:
        raise ValueError("Insufficient temporary space for the isolated evidence copy")
    subprocess.run(
        ["cp", "-a", "--reflink=auto", str(ROOT / "runs"), str(destination / "runs")], check=True
    )
    extract(destination)
    return destination


def run_tests(output, *, only=None):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    if not {0, 1, 2, 3} <= os.sched_getaffinity(0):
        raise ValueError("The frozen historical test context requires CPUs 0-3")
    environment = os.environ | dict.fromkeys(
        ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"), "1"
    )
    results = {}

    def execute(name, directory, arguments):
        report = output / f"{name}.xml"
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
            *arguments,
        ]
        print(f"Test context: {name}", flush=True)
        worker = subprocess.run(
            command,
            cwd=directory,
            env=environment | {"PYTHONPATH": str(Path(directory) / "src")},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        with (output / f"{name}.log").open("x") as handle:
            handle.write(worker.stdout)
        print(worker.stdout[-2500:], flush=True)
        suites = ET.parse(report).getroot().findall("testsuite")
        results[name] = {
            "exit_code": worker.returncode,
            "junit_sha256": sha(report),
            "log_sha256": sha(output / f"{name}.log"),
            **{
                k: sum(int(s.get(k, 0)) for s in suites)
                for k in ("tests", "failures", "errors", "skipped")
            },
            "seconds": sum(float(s.get("time", 0)) for s in suites),
        }

    if only != "reference":
        execute(
            "current-production",
            ROOT,
            [
                f"--ignore={name}"
                for name in (*HISTORICAL, *CHANNEL_HISTORICAL, *PHYSICAL_GRAPH_HISTORICAL)
            ],
        )
    if only != "current":
        with tempfile.TemporaryDirectory(prefix="cells-historical-tests-") as temporary:
            workspace = reference_workspace(Path(temporary) / "Cells")
            execute("preserved-reference", workspace, list(HISTORICAL))
        with tempfile.TemporaryDirectory(prefix="cells-channel-reference-tests-") as temporary:
            workspace = reference_workspace(
                Path(temporary) / "Cells", extract=extract_channel_sources
            )
            execute("preserved-channel-reference", workspace, list(CHANNEL_HISTORICAL))
        with tempfile.TemporaryDirectory(
            prefix="cells-physical-graph-reference-tests-"
        ) as temporary:
            workspace = reference_workspace(
                Path(temporary) / "Cells", extract=extract_physical_graph_sources
            )
            execute(
                "preserved-physical-graph-reference", workspace, list(PHYSICAL_GRAPH_HISTORICAL)
            )
    passed = all(
        r["exit_code"] == r["failures"] == r["errors"] == r["skipped"] == 0
        for r in results.values()
    )
    receipt = {
        "status": "pass" if passed else "failed",
        "contexts": results,
        "historical_test_files": list(HISTORICAL),
        "channel_historical_test_files": list(CHANNEL_HISTORICAL),
        "physical_graph_historical_test_files": list(PHYSICAL_GRAPH_HISTORICAL),
        "preserved_physical_graph_source_sha256": PHYSICAL_GRAPH_ARCHIVE_SHA,
        "preserved_channel_source_sha256": CHANNEL_ARCHIVE_SHA,
        "preserved_source_sha256": ARCHIVE_SHA,
        "driver_sha256": sha(__file__),
        "cpu_affinity": [0, 1, 2, 3],
        "thread_environment": {
            k: environment[k]
            for k in (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        },
        "total_tests": sum(r["tests"] for r in results.values()),
    }
    with (output / "verification.json").open("x") as handle:
        json.dump(receipt, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--only", choices=("current", "reference"))
    args = parser.parse_args()
    result = run_tests(args.output, only=args.only)
    print(json.dumps(result, indent=2, sort_keys=True))
    sys.exit(0 if result["status"] == "pass" else 1)
