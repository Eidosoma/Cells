"""One detached process-qualification / existing-model regression attempt. No polling."""

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
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import contact as c  # noqa: E402

AUDIT = c.ROOT / "runs/num-011-coupled-audit-2026-09-16/audit-01"
AUDIT_SHA = "9a8500c86464bd487754cc8d4a56c2c30b94f85451b217960aeff7cff7be5fb1"
EXTRA = (
    "src/cells/processes/kinetic_pump.py",
    "tests/unit/test_kinetic_pump.py",
    "validation/betse/pump_process/process_check.py",
    "validation/betse/pump_process/process_job.py",
    "validation/betse/pump_process/test_process_gate.py",
    "validation/betse/contact.py",
    "docs/KINETIC_PUMP_PROCESS.md",
    "reports/NUM011_COUPLED_CLOSEOUT.md",
    "reports/SPEC010_PROCESS_HANDOFF.md",
)
REGRESSION = (
    "tests/unit/test_bioelectric_cell.py",
    "tests/unit/test_multispecies_membrane.py",
    "tests/unit/test_finite_extracellular_production.py",
    "tests/unit/test_finite_extracellular_ownership.py",
    "tests/unit/test_kinetic_pump.py",
)


def prior():
    c.require(c.sha(AUDIT / "completion.json") == AUDIT_SHA, "Coupled review changed")
    receipt = c.read(AUDIT / "completion.json")
    c.require(
        receipt["status"] == "coupled_candidate_independently_closed", "Coupled gate not closed"
    )
    c.require(
        all(c.sha(AUDIT / n) == h for n, h in receipt["files_sha256"].items()), "Audit payload"
    )
    registered = c.read(AUDIT / "registration.json")
    capture = c.ROOT / registered["capture"]
    c.require(
        all(c.sha(capture / n) == h for n, h in registered["capture_sha256"].items()),
        "Original coupled capture changed",
    )
    contact_audit = c.read(capture / "registration.json")["prior_closeout"]
    directory = c.ROOT / contact_audit["path"]
    c.require(
        c.sha(directory / "completion.json") == contact_audit["completion_sha256"],
        "Source-contact closeout changed",
    )
    c.require(
        all(
            c.sha(directory / n) == h
            for n, h in c.read(directory / "completion.json")["files_sha256"].items()
        ),
        "Source-contact audit payload changed",
    )
    contact_registration = c.read(directory / "registration.json")
    original_contact = c.ROOT / contact_registration["capture"]
    c.require(
        all(
            c.sha(original_contact / n) == h
            for n, h in contact_registration["capture_sha256"].items()
        ),
        "Original source contact changed",
    )
    preserved = c.authenticate_cells()
    c.require(
        preserved["implementation_files_sha256"]
        == registered["accepted_implementation_files_sha256"],
        "Wrong pre-change implementation",
    )
    # A new module changes the whole-package source identity, even though no old
    # equation or checkpoint code changed. Never waive that identity on restore.
    old_sources = registered["accepted_source_hashes"]
    expected = {"src/cells/" + n for n in old_sources} | {EXTRA[0]}
    actual = {str(p.relative_to(c.ROOT)) for p in (c.ROOT / "src/cells").rglob("*.py")}
    c.require(actual == expected, "Unexpected production source inventory")
    return {
        "path": str(AUDIT.relative_to(c.ROOT)),
        "completion_sha256": AUDIT_SHA,
        "old_production_modules": len(old_sources),
        "current_production_modules": len(actual),
    }


def protocol():
    return {
        "cpu_affinity": [0, 1, 2, 3],
        "total_timeout_seconds": 900,
        "contact_timeout_seconds": 60,
        "regression_timeout_seconds": 600,
        "per_file_bytes": 32 * 1024**2,
        "artifact_bytes": 128 * 1024**2,
        "contact_cases": 31,
        "contact_comparisons": 930,
        "regression_tests": 348,
    }


def sources():
    names = set(c.authenticate_cells()["implementation_files_sha256"]) | set(EXTRA)
    return {name: c.sha(c.ROOT / name) for name in sorted(names)}


def tests_receipt(path, minimum):
    path = path.resolve()
    c.require(path.is_relative_to(c.ROOT / "reports"), "Use reports receipt")
    suites = ET.parse(path).getroot().findall("testsuite")
    count = sum(int(s.attrib["tests"]) for s in suites)
    c.require(
        count >= minimum
        and all(
            int(s.attrib.get(k, 0)) == 0 for s in suites for k in ("errors", "failures", "skipped")
        ),
        "Tests failed",
    )
    return {"path": str(path.relative_to(c.ROOT)), "sha256": c.sha(path), "tests": count}


def authenticate(output):
    r = c.read(output / "registration.json")
    c.require(r["schema"] == "cells.kinetic_pump_process_qualification@1", "Wrong registration")
    c.require(all(r[key] == value for key, value in protocol().items()), "Changed protocol")
    c.require(r["sources_sha256"] == sources(), "Registered source changed")
    c.require(r["prior_closeout"] == prior(), "Prior closeout changed")
    c.require(r["packages"] == c.environment()["packages"], "Environment changed")
    c.require(r["regression"] == list(REGRESSION), "Regression scope changed")
    for receipt in r["software"]:
        c.require(tests_receipt(c.ROOT / receipt["path"], 1) == receipt, "Software changed")
    with zipfile.ZipFile(output / "sources.zip") as archive:
        c.require(
            set(archive.namelist()) == set(r["sources_sha256"])
            and len(archive.namelist()) == len(r["sources_sha256"]),
            "Source capsule members",
        )
        c.require(
            all(
                hashlib.sha256(archive.read(n)).hexdigest() == h
                for n, h in r["sources_sha256"].items()
            ),
            "Source capsule bytes",
        )
    return r


def environment():
    env = os.environ.copy()
    for key in ("PYTHONPATH", "PYTEST_ADDOPTS", "PYTEST_PLUGINS"):
        env.pop(key, None)
    env.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "JAX_PLATFORMS": "cpu",
            "JAX_ENABLE_X64": "true",
            "JAX_DISABLE_JIT": "false",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    )
    return env


def register(output, checks, gate_checks):
    c.require(
        output.is_relative_to(c.ROOT / "runs")
        and output != c.ROOT / "runs"
        and not output.exists(),
        "Use fresh qualification output",
    )
    r = {
        "schema": "cells.kinetic_pump_process_qualification@1",
        "sources_sha256": sources(),
        "prior_closeout": prior(),
        "packages": c.environment()["packages"],
        "regression": list(REGRESSION),
        "software": [tests_receipt(checks, 32), tests_receipt(gate_checks, 8)],
        "registered_utc": datetime.now(UTC).isoformat(),
        **protocol(),
        "coupled_production_family_implemented": False,
        "gpu_tested": False,
        "automatic_polling": False,
        "automatic_retry": False,
        "automatic_followup": False,
    }
    output.mkdir(parents=True)
    try:
        c.write(output / "registration.json", r)
        with zipfile.ZipFile(
            output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for name in r["sources_sha256"]:
                archive.write(c.ROOT / name, arcname=name)
        authenticate(output)
    except BaseException:
        c.write(
            output / "registration-failure.json",
            {
                "status": "not_launched",
                "traceback": traceback.format_exc(),
            },
        )
        raise
    return r


def deadline(_signal, _frame):
    raise TimeoutError("Process qualification controller deadline")


def execute(output):
    c.require(not (output / "started.json").exists(), "Execution already attempted")
    started = time.monotonic()
    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, 900)
    try:
        c.write(
            output / "started.json",
            {"started_utc": datetime.now(UTC).isoformat(), "pid": os.getpid()},
        )
        r = authenticate(output)
        c.require(sorted(os.sched_getaffinity(0)) == r["cpu_affinity"], "CPU affinity")
        resource.setrlimit(resource.RLIMIT_FSIZE, (r["per_file_bytes"],) * 2)
        commands = (
            (
                "contact",
                [str(Path(__file__).with_name("process_check.py")), str(output)],
                r["contact_timeout_seconds"],
            ),
            (
                "regression",
                [
                    "-m",
                    "pytest",
                    "-q",
                    "-W",
                    "error",
                    *REGRESSION,
                    "--junitxml=" + str(output / "regression.xml"),
                ],
                r["regression_timeout_seconds"],
            ),
        )
        for name, command, bound in commands:
            with (
                (output / f"{name}.stdout.log").open("x") as out,
                (output / f"{name}.stderr.log").open("x") as err,
            ):
                subprocess.run(
                    [str(c.CELLS_PYTHON), "-B", *command],
                    cwd=c.ROOT,
                    env=environment(),
                    stdin=subprocess.DEVNULL,
                    stdout=out,
                    stderr=err,
                    check=True,
                    timeout=bound,
                )
        contact = c.read(output / "process-contact.json")
        c.require(
            contact["status"] == "pass"
            and contact["comparisons"] == r["contact_comparisons"]
            and not contact["warnings"],
            "Incomplete process contact",
        )
        suites = ET.parse(output / "regression.xml").getroot().findall("testsuite")
        count = sum(int(s.attrib["tests"]) for s in suites)
        c.require(
            count == r["regression_tests"]
            and all(
                int(s.attrib.get(k, 0)) == 0
                for s in suites
                for k in ("errors", "failures", "skipped")
            ),
            "Regression failed",
        )
        authenticate(output)
        used = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
        c.require(used < r["artifact_bytes"] - 1024**2, "Artifact budget")
        c.write(
            output / "completion.json",
            {
                "status": "process_qualification_pass_pending_review",
                "elapsed_seconds": time.monotonic() - started,
                "finished_utc": datetime.now(UTC).isoformat(),
                "contact_comparisons": contact["comparisons"],
                "regression_tests": count,
                "artifact_bytes_before_receipt": used,
                "files_sha256": {
                    n: c.sha(output / n)
                    for n in (
                        "registration.json",
                        "sources.zip",
                        "started.json",
                        "process-contact.json",
                        "regression.xml",
                    )
                },
                "coupled_production_family_implemented": False,
                "biology_validated": False,
                "gpu_tested": False,
                "stable_release_promoted": False,
                "automatic_followup": False,
            },
        )
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        c.write(
            output / "failure.json",
            {
                "status": "failed_not_qualified",
                "elapsed_seconds": time.monotonic() - started,
                "traceback": traceback.format_exc(),
                "automatic_retry": False,
            },
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def launch(output, checks, gate_checks):
    register(output, checks, gate_checks)
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
                    str(c.CELLS_PYTHON),
                    "-B",
                    str(Path(__file__).resolve()),
                    "execute",
                    str(output),
                ],
                cwd=c.ROOT,
                env=environment(),
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                start_new_session=True,
            )
        result = {
            "status": "launched_detached",
            "pid": child.pid,
            "launched_utc": datetime.now(UTC).isoformat(),
            "registration_sha256": c.sha(output / "registration.json"),
            "automatic_polling": False,
        }
        c.write(output / "launch.json", result)
        return result
    except BaseException:
        c.write(
            output / "launch-failure.json",
            {"status": "launch_failed", "traceback": traceback.format_exc()},
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("launch", "execute"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--checks", type=Path)
    parser.add_argument("--gate-checks", type=Path)
    args = parser.parse_args()
    if args.action == "launch":
        c.require(
            args.checks is not None and args.gate_checks is not None, "Need both software receipts"
        )
        print(
            json.dumps(launch(args.output.resolve(), args.checks, args.gate_checks), sort_keys=True)
        )
    else:
        execute(args.output.resolve())
