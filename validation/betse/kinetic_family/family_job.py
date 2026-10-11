"""Freeze one development-family test/trajectory and regression attempt, detached.

This uses preserved evidence identities, never the old current-tree guard on a
deliberately new source context. No polling, automatic retries or follow-up jobs.
"""

import argparse
import hashlib
import json
import os
import resource
import signal
import subprocess
import sys
import time
import traceback
import zipfile
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
PYTHON = ROOT / ".venv/bin/python"
PRESERVATION = ROOT / "runs/spec-010-family-2026-09-16/pre-integration-01"
PRESERVATION_SHA = "d9ba2cea129119b8caa96d0cf2d1e45e12811ffd368a1183a26f8011759132a9"
NEW_TESTS = tuple(
    f"tests/unit/test_kinetic_finite_{n}.py" for n in ("schema", "dynamics", "legacy", "runner")
)
OLD_TESTS = tuple(
    f"tests/unit/test_{n}.py"
    for n in (
        "bioelectric_cell",
        "multispecies_membrane",
        "finite_extracellular_production",
        "finite_extracellular_ownership",
        "kinetic_pump",
    )
)
SOFTWARE = (
    "reports/spec-010-family-schema-01.xml",
    "reports/spec-010-family-dynamics-02.xml",
    "reports/spec-010-family-legacy-01.xml",
    "reports/spec-010-family-smoke-01.xml",
    "reports/spec-010-family-composition-01.xml",
    "reports/spec-010-family-controller-02.xml",
)


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def prior():
    require(
        sha(PRESERVATION / "completion.json") == PRESERVATION_SHA, "Preservation receipt changed"
    )
    r = read(PRESERVATION / "completion.json")
    require(r["status"] == "process_qualification_reviewed_pass", "Process gate not reviewed")
    require(
        sha(PRESERVATION / "worktree.zip") == r["worktree_zip_sha256"],
        "Pre-edit source archive changed",
    )
    original = ROOT / r["qualification"]
    require(
        all(sha(original / n) == h for n, h in r["qualification_files_sha256"].items()),
        "Process qualification payload changed",
    )
    process_name = "src/cells/processes/kinetic_pump.py"
    require(
        sha(ROOT / process_name)
        == read(original / "registration.json")["sources_sha256"][process_name],
        "Qualified process itself changed",
    )
    audit = ROOT / "runs/num-011-coupled-audit-2026-09-16/audit-01"
    require(
        sha(audit / "completion.json")
        == "9a8500c86464bd487754cc8d4a56c2c30b94f85451b217960aeff7cff7be5fb1",
        "Coupled independent closeout changed",
    )
    require(
        all(
            sha(audit / n) == h for n, h in read(audit / "completion.json")["files_sha256"].items()
        ),
        "Coupled audit payload changed",
    )
    registration = read(audit / "registration.json")
    capture = ROOT / registration["capture"]
    require(
        all(sha(capture / n) == h for n, h in registration["capture_sha256"].items()),
        "Saved coupled reference/candidate changed",
    )
    candidate_sources = read(capture / "registration.json")["sources_sha256"]
    for name in (
        "validation/betse/pump_coupled/coupled_reference.py",
        "validation/betse/pump_coupled/coupled_plan.py",
    ):
        require(sha(ROOT / name) == candidate_sources[name], "Independent equation source changed")
    return {
        "preservation_sha256": PRESERVATION_SHA,
        "coupled_capture_sha256": registration["capture_sha256"],
    }


def sources():
    names = {
        str(p.relative_to(ROOT))
        for directory in ("src/cells", "tests", "scripts", "validation/betse")
        for p in (ROOT / directory).rglob("*.py")
    }
    names |= {str(p.relative_to(ROOT)) for p in (ROOT / "configs").rglob("*.json")}
    # Capture new bytes of all known accepted implementation inputs, including
    # lock files and non-Python fixtures. This is a new source context, not a
    # requirement that intentionally edited core files still equal the old hash.
    names |= set(read(ROOT / "reports/ref-003a-preservation.json")["implementation_files_sha256"])
    names |= {
        "pyproject.toml",
        "docs/KINETIC_FINITE_BATH_MODEL.md",
        "reports/SPEC010_FAMILY_HANDOFF.md",
    }
    return {n: sha(ROOT / n) for n in sorted(names)}


def protocol():
    return {
        "cpu_affinity": [0, 1, 2, 3],
        "new_tests": list(NEW_TESTS),
        "new_test_count": 74,
        "regression": list(OLD_TESTS),
        "regression_count": 348,
        "family_timeout_seconds": 1200,
        "regression_timeout_seconds": 600,
        "total_timeout_seconds": 1860,
        "per_file_bytes": 64 * 1024**2,
        "artifact_bytes": 256 * 1024**2,
        "trajectory_cases": 6,
        "trajectory_runs": 12,
        "restart_suffixes": 12,
        "reference_methods": ["DOP853", "Radau"],
    }


def runtime():
    return {
        "python": sys.version,
        "packages": {
            n: metadata.version(n)
            for n in ("jax", "jaxlib", "numpy", "scipy", "ml_dtypes", "opt_einsum", "pytest")
        },
    }


def test_count(path):
    suites = ET.parse(path).getroot().findall("testsuite")
    require(
        bool(suites)
        and all(int(s.get(k, "0")) == 0 for s in suites for k in ("failures", "errors", "skipped")),
        "Nonpassing test receipt",
    )
    return sum(int(s.attrib["tests"]) for s in suites)


def environment():
    env = os.environ.copy()
    for name in ("PYTHONPATH", "PYTEST_ADDOPTS", "PYTEST_PLUGINS"):
        env.pop(name, None)
    env.update(
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONNOUSERSITE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        JAX_PLATFORMS="cpu",
        JAX_ENABLE_X64="true",
        JAX_DISABLE_JIT="false",
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
    )
    return env


def authenticate(output):
    r = read(output / "registration.json")
    require(r["schema"] == "cells.kinetic_finite_family_attempt@1", "Registration schema")
    require(r["protocol"] == protocol() and r["prior"] == prior(), "Protocol/prior changed")
    require(r["sources_sha256"] == sources(), "Frozen family source changed")
    require(r["runtime"] == runtime(), "Runtime changed")
    for name, value in r["software"].items():
        require(
            sha(ROOT / name) == value["sha256"] and test_count(ROOT / name) == value["tests"],
            "Prelaunch check changed",
        )
    with zipfile.ZipFile(output / "sources.zip") as archive:
        require(
            set(archive.namelist()) == r["sources_sha256"].keys()
            and len(archive.namelist()) == len(r["sources_sha256"]),
            "Source membership",
        )
        require(
            all(
                hashlib.sha256(archive.read(n)).hexdigest() == h
                for n, h in r["sources_sha256"].items()
            ),
            "Source bytes",
        )
    return r


def register(output):
    require(
        output.is_relative_to(ROOT / "runs") and output != ROOT / "runs" and not output.exists(),
        "Use a fresh run directory",
    )
    r = {
        "schema": "cells.kinetic_finite_family_attempt@1",
        "registered_utc": datetime.now(UTC).isoformat(),
        "protocol": protocol(),
        "prior": prior(),
        "sources_sha256": sources(),
        "runtime": runtime(),
        "software": {n: {"sha256": sha(ROOT / n), "tests": test_count(ROOT / n)} for n in SOFTWARE},
        "automatic_polling": False,
        "automatic_retry": False,
        "automatic_followup": False,
        "stable_release_promoted": False,
        "biology_validated": False,
        "gpu_tested": False,
    }
    output.mkdir(parents=True)
    try:
        write(output / "registration.json", r)
        with zipfile.ZipFile(
            output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for n in r["sources_sha256"]:
                archive.write(ROOT / n, arcname=n)
        authenticate(output)
    except BaseException:
        write(
            output / "registration-failure.json",
            {
                "status": "not_launched",
                "traceback": traceback.format_exc(),
                "automatic_retry": False,
            },
        )
        raise
    return r


def deadline(_signal, _frame):
    raise TimeoutError("Kinetic family controller deadline")


def execute(output):
    require(not (output / "started.json").exists(), "Execution already attempted")
    started = time.monotonic()
    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, protocol()["total_timeout_seconds"])
    try:
        write(
            output / "started.json",
            {"pid": os.getpid(), "started_utc": datetime.now(UTC).isoformat()},
        )
        r = authenticate(output)
        p = r["protocol"]
        require(sorted(os.sched_getaffinity(0)) == p["cpu_affinity"], "CPU affinity")
        resource.setrlimit(resource.RLIMIT_FSIZE, (p["per_file_bytes"],) * 2)
        for name, files, count, timeout in (
            ("family", NEW_TESTS, p["new_test_count"], p["family_timeout_seconds"]),
            ("regression", OLD_TESTS, p["regression_count"], p["regression_timeout_seconds"]),
        ):
            with (
                (output / f"{name}.stdout.log").open("x") as out,
                (output / f"{name}.stderr.log").open("x") as err,
            ):
                subprocess.run(
                    [
                        str(PYTHON),
                        "-B",
                        "-m",
                        "pytest",
                        "-q",
                        "-W",
                        "error",
                        *files,
                        "--junitxml=" + str(output / f"{name}.xml"),
                        "--basetemp=" + str(output / f"{name}-artifacts"),
                    ],
                    cwd=ROOT,
                    env=environment(),
                    stdin=subprocess.DEVNULL,
                    stdout=out,
                    stderr=err,
                    check=True,
                    timeout=timeout,
                )
            require(test_count(output / f"{name}.xml") == count, "Test coverage differs")
        # No new reference solver is launched. Compare the ordinary runner to
        # both frozen independent integrators; retain all complete trajectories.
        comparisons = sorted((output / "family-artifacts").glob("*/comparison.json"))
        comparisons = [p for p in comparisons if not p.parent.is_symlink()]
        require(len(comparisons) == p["trajectory_runs"], "Trajectory artifact coverage")
        records = [read(path) for path in comparisons]
        require(len({(v["case"], v["dt_s"]) for v in records}) == 12, "Duplicate trajectory")
        require(
            all(
                v["restart_bitwise_equal"] and set(v["methods"]) == {"DOP853", "Radau"}
                for v in records
            ),
            "Missing reference/restart comparison",
        )
        write(output / "trajectory-comparisons.json", records)
        authenticate(output)
        used = sum(
            path.stat().st_size
            for path in output.rglob("*")
            if path.is_file() and not path.is_symlink()
        )
        require(used < p["artifact_bytes"] - 1024**2, "Artifact budget")
        files = {
            str(path.relative_to(output)): sha(path)
            for path in output.rglob("*")
            if path.is_file()
            and not path.is_symlink()
            and path.name not in ("runner.stdout.log", "runner.stderr.log", "launch.json")
        }
        write(
            output / "completion.json",
            {
                "status": "family_checks_pass_pending_review",
                "finished_utc": datetime.now(UTC).isoformat(),
                "elapsed_seconds": time.monotonic() - started,
                "files_sha256": files,
                "new_tests": p["new_test_count"],
                "regression_tests": p["regression_count"],
                "trajectory_runs": len(records),
                "restart_suffixes": 12,
                "artifact_bytes_before_receipt": used,
                "native_betse_trajectory": False,
                "biology_validated": False,
                "gpu_tested": False,
                "stable_release_promoted": False,
                "automatic_followup": False,
            },
        )
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        write(
            output / "failure.json",
            {
                "status": "failed_not_accepted",
                "elapsed_seconds": time.monotonic() - started,
                "traceback": traceback.format_exc(),
                "automatic_retry": False,
            },
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def launch(output):
    register(output)
    try:
        with (
            (output / "runner.stdout.log").open("x") as out,
            (output / "runner.stderr.log").open("x") as err,
        ):
            child = subprocess.Popen(
                [
                    "taskset",
                    "-c",
                    "0-3",
                    str(PYTHON),
                    "-B",
                    str(Path(__file__).resolve()),
                    "execute",
                    str(output),
                ],
                cwd=ROOT,
                env=environment(),
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                start_new_session=True,
            )
        receipt = {
            "status": "launched_detached",
            "pid": child.pid,
            "launched_utc": datetime.now(UTC).isoformat(),
            "registration_sha256": sha(output / "registration.json"),
            "automatic_polling": False,
        }
        write(output / "launch.json", receipt)
        return receipt
    except BaseException:
        write(
            output / "launch-failure.json",
            {"status": "launch_failed", "traceback": traceback.format_exc()},
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("launch", "execute"))
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.action == "launch":
        print(json.dumps(launch(args.output.resolve()), sort_keys=True))
    else:
        execute(args.output.resolve())
