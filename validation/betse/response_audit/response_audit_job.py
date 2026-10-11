"""Detached audit plus transparent legacy-guard/new regression outcomes; never simulate."""

import argparse
import hashlib
import json
import os
import resource
import subprocess
import time
import traceback
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import response_audit as audit
import response_audit_context as ctx

c = ctx.c
LEGACY_GUARD = (
    "validation.betse.test_held_response",
    "test_earlier_evidence_and_engineering_preserved",
)


def validate_registration(r):
    pre = c.read(ctx.PRELAUNCH)
    c.require(
        r["schema"] == "cells.betse_held_response_audit_registration@1"
        and json.dumps(r["plan"], sort_keys=True) == json.dumps(ctx.PLAN, sort_keys=True)
        and r["anchors"] == ctx.ANCHORS
        and r["external_metadata_change"] == ctx.EXTERNAL_METADATA
        and r["prelaunch_sha256"] == c.sha(ctx.PRELAUNCH)
        and r["preservation_sha256"] == c.sha(ctx.PRESERVATION),
        "Audit registration identity/scope differs",
    )
    c.require(
        pre["status"] == "pass"
        and pre["sources"] == ctx.sources()
        and pre["plan"] == ctx.PLAN
        and pre["test_receipt_sha256"] == c.sha(c.ROOT / pre["test_receipt"])
        and r["new_test_count"] == pre["tests"]["tests"],
        "Audit prelaunch/test evidence differs",
    )
    c.require(
        r["sources"] == c.read(ctx.SESSION / "registration.json")["sources"] | ctx.sources()
        and len(r["sources"]) == 92
        and all(c.sha(c.HERE / n) == h for n, h in r["sources"].items()),
        "Audit source coverage differs",
    )
    for n, h in pre["new_files_sha256_before_prelaunch"].items():
        c.require(c.sha(c.ROOT / n) == h, "Frozen audit preflight input changed: " + n)


def capsule(output, registered):
    with zipfile.ZipFile(output / "sources.zip") as archive:
        names = archive.namelist()
        c.require(
            len(names) == len(set(names))
            and set(names) == set(registered["sources"])
            and all(
                hashlib.sha256(archive.read(n)).hexdigest() == registered["sources"][n]
                for n in names
            ),
            "Audit capsule differs",
        )


def legacy_outcome(path, returncode):
    """An unmodified historical preservation guard must fail on the user's edit.

    Record the actual 121-pass / one-failure outcome. Never relabel it a green
    regression, skip its test, patch its assertions or accept additional failures.
    """
    suites = list(ET.parse(path).getroot().iter("testsuite"))
    counts = {
        k: sum(int(s.get(k, 0)) for s in suites) for k in ("tests", "failures", "errors", "skipped")
    }
    cases = [case for suite in suites for case in suite.findall("testcase")]
    original = ET.parse(c.ROOT / "reports/ref-003e1-response-checks-03.xml")
    identities = [(case.get("classname"), case.get("name")) for case in cases]
    expected = {(case.get("classname"), case.get("name")) for case in original.iter("testcase")}
    c.require(
        len(set(identities)) == len(identities) == 122 and set(identities) == expected,
        "Legacy regression test identities differ",
    )
    failures = [case for case in cases if case.find("failure") is not None]
    c.require(
        returncode == 1
        and counts == {"tests": 122, "failures": 1, "errors": 0, "skipped": 0}
        and len(cases) == 122
        and len(failures) == 1,
        "Legacy regression has an unexpected outcome",
    )
    case = failures[0]
    c.require(
        (case.get("classname"), case.get("name")) == LEGACY_GUARD
        and "Unexpected pre-existing edit" in case.find("failure").get("message", ""),
        "Different legacy guard/test failed",
    )
    c.require(
        c.sha(c.ROOT / ctx.EXTERNAL_METADATA["path"]) == ctx.EXTERNAL_METADATA["after_sha256"],
        "Legacy metadata-change explanation differs",
    )
    return {
        "status": "expected_metadata_guard_rejection_not_all_tests_pass",
        "counts": counts,
        "passed": 121,
        "failed_test": {"module": LEGACY_GUARD[0], "name": LEGACY_GUARD[1]},
        "metadata_change": ctx.EXTERNAL_METADATA,
        "assertions_changed": False,
        "tests_skipped": False,
    }


def commands(output):
    python = [str(c.CELLS_PYTHON), "-B"]
    pytest = [*python, "-m", "pytest", "-q", "-W", "error"]
    return [
        ("audit", [*python, str(ctx.HERE / "response_audit.py"), str(output)]),
        (
            "legacy_regression",
            [
                *pytest,
                str(c.HERE / "test_held_response.py"),
                str(c.HERE / "test_held_response_check.py"),
                "--junitxml=" + str(output / "legacy-regression.xml"),
            ],
        ),
        (
            "regression",
            [
                *pytest,
                str(ctx.HERE / "test_saved_response.py"),
                "--junitxml=" + str(output / "regression.xml"),
            ],
        ),
    ]


def payloads(output):
    return {n: h for n, h in ctx.packet_hashes(output).items() if n not in ctx.OPERATIONAL}


def validate_audit(result, output, registered):
    c.require(
        result["schema"] == "cells.betse_held_response_failure_audit@1"
        and result["status"] == "audit_pass_rejection_reproduced_pending_regression"
        and result["scope"] == audit.SCOPE
        and result["anchors"] == ctx.ANCHORS
        and result["driver_sha256"] == registered["sources"]["response_audit/response_audit.py"],
        "Independent audit identity differs",
    )
    c.require(
        result["frozen_comparisons_replayed"] == 345576
        and result["internal_checks"]["comparisons"] == 198264
        and result["internal_checks"]["failed_comparisons"] == 0
        and result["internal_checks"]["first_failures"] == []
        and result["independent_surfaces"]["comparisons"] == 147312
        and result["independent_surfaces"]["failed_comparisons"] == 150,
        "Independent numerical/rejection evidence differs",
    )
    c.require(
        result["model_calls"] == 0
        and result["model_imports"] == []
        and result["native_runs"] == 8
        and result["cells_runs"] == 24
        and result["total_files"] == 150
        and result["payloads"] == 146
        and all(
            result[k] is False
            for k in (
                "response_qualified",
                "native_convergence_qualified",
                "forcing_convergence_qualified",
                "capture_rerun",
                "original_packet_rewritten",
                "biology_validated",
                "gpu_tested",
            )
        ),
        "Audit scope/import boundary differs",
    )
    c.require(
        result["corrected_report_sha256"] == c.sha(output / "corrected-comparison.json")
        and result["failure_ledger_sha256"] == c.sha(output / "failure-ledger.json")
        and len(c.read(output / "failure-ledger.json")["all_failures"]) == 150,
        "Corrected report/full failure ledger differs",
    )


def finish(output, registered, started, stage_seconds):
    validate_registration(registered)
    capsule(output, registered)
    preserved = ctx.preservation_check()
    result = c.read(output / "audit.json")
    validate_audit(result, output, registered)
    legacy = legacy_outcome(output / "legacy-regression.xml", 1)
    c.require(legacy == c.read(output / "legacy-regression.json"), "Legacy guard receipt differs")
    counts, modules = ctx.receipts.test_counts(output / "regression.xml")
    c.require(
        counts["tests"] == registered["new_test_count"]
        and modules == {"validation.betse.response_audit.test_saved_response"},
        "New regression coverage differs",
    )
    size = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
    elapsed = time.monotonic() - started
    c.require(
        size < ctx.PLAN["max_artifact_bytes"] - 65536
        and elapsed < ctx.PLAN["total_timeout_seconds"],
        "Audit total resource cap exceeded",
    )
    c.write(
        output / "completion.json",
        {
            "schema": "cells.betse_held_response_failure_closeout@1",
            "status": "failure_audit_closed_response_rejected",
            "finished_utc": datetime.now(UTC).isoformat(),
            "elapsed_seconds": elapsed,
            "stage_seconds": stage_seconds,
            "registration_sha256": c.sha(output / "registration.json"),
            "files_sha256": payloads(output),
            "artifact_bytes_before_receipt": size,
            "frozen_comparisons_replayed": 345576,
            "independent_surface_comparisons": 147312,
            "failed_physical_comparisons": 150,
            "new_tests": counts,
            "legacy_regression": legacy,
            "response_qualified": False,
            "reporting_fix_separately_recorded": True,
            "capture_rerun": False,
            "original_packet_rewritten": False,
            "automatic_retry": False,
            "automatic_expansion": False,
            "biology_validated": False,
            "gpu_tested": False,
            **preserved,
        },
    )


def execute(output):
    started, stage_seconds, stage = time.monotonic(), {}, "validation"
    try:
        registered = c.read(output / "registration.json")
        validate_registration(registered)
        capsule(output, registered)
        resource.setrlimit(resource.RLIMIT_FSIZE, (ctx.PLAN["max_worker_file_bytes"],) * 2)
        c.write(
            output / "started.json",
            {"pid": os.getpid(), "started_utc": datetime.now(UTC).isoformat()},
        )
        env = os.environ | {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        }
        env.pop("PYTHONPATH", None)
        for stage, command in commands(output):
            remaining = ctx.PLAN["total_timeout_seconds"] - (time.monotonic() - started)
            c.require(remaining > 0, "Audit wall budget exhausted")
            start = time.monotonic()
            with (output / (stage + ".log")).open("x") as log:
                result = subprocess.run(
                    ["taskset", "-c", ctx.PLAN["cpu_affinity"], *command],
                    cwd=c.ROOT,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=min(remaining, ctx.PLAN["stage_timeout_seconds"][stage]),
                    check=False,
                )
            stage_seconds[stage] = time.monotonic() - start
            if stage == "legacy_regression":
                c.write(
                    output / "legacy-regression.json",
                    legacy_outcome(output / "legacy-regression.xml", result.returncode),
                )
            else:
                c.require(result.returncode == 0, "Audit stage failed: " + stage)
            c.require(
                sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
                < ctx.PLAN["max_artifact_bytes"] - 65536,
                "Audit artifact cap exceeded",
            )
            print(
                json.dumps({"completed_stage": stage, "seconds": stage_seconds[stage]}), flush=True
            )
        finish(output, registered, started, stage_seconds)
    except BaseException:
        c.write(
            output / "failure.json",
            {
                "status": "audit_failed_not_closed",
                "stage": stage,
                "elapsed_seconds": time.monotonic() - started,
                "stage_seconds": stage_seconds,
                "traceback": traceback.format_exc(),
                "files_sha256": payloads(output),
                "capture_rerun": False,
                "response_qualified": False,
                "automatic_retry": False,
            },
        )
        raise


def register(output):
    ctx.preservation_check()
    pre = c.read(ctx.PRELAUNCH)
    registered = {
        "schema": "cells.betse_held_response_audit_registration@1",
        "registered_utc": datetime.now(UTC).isoformat(),
        "plan": ctx.PLAN,
        "anchors": ctx.ANCHORS,
        "external_metadata_change": ctx.EXTERNAL_METADATA,
        "prelaunch_sha256": c.sha(ctx.PRELAUNCH),
        "preservation_sha256": c.sha(ctx.PRESERVATION),
        "sources": c.read(ctx.SESSION / "registration.json")["sources"] | ctx.sources(),
        "new_test_count": pre["tests"]["tests"],
    }
    validate_registration(registered)
    c.require(
        output.is_relative_to(c.ROOT / "runs") and output != c.ROOT / "runs",
        "Use a fresh audit run subdirectory",
    )
    output.mkdir(parents=True, exist_ok=False)
    c.write(output / "registration.json", registered)
    with zipfile.ZipFile(output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for n in registered["sources"]:
            archive.write(c.HERE / n, arcname=n)
    capsule(output, registered)
    return registered


def launch(output):
    register(output)
    try:
        with (
            (output / "runner.stdout.log").open("x") as out,
            (output / "runner.stderr.log").open("x") as err,
        ):
            process = subprocess.Popen(
                [
                    "taskset",
                    "-c",
                    ctx.PLAN["cpu_affinity"],
                    str(c.CELLS_PYTHON),
                    "-B",
                    str(Path(__file__).resolve()),
                    "execute",
                    str(output),
                ],
                cwd=c.ROOT,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                start_new_session=True,
            )
    except BaseException:
        c.write(
            output / "failure.json",
            {
                "status": "launch_failed_not_started",
                "traceback": traceback.format_exc(),
                "capture_rerun": False,
            },
        )
        raise
    receipt = {
        "status": "launched_detached",
        "pid": process.pid,
        "launched_utc": datetime.now(UTC).isoformat(),
        "registration_sha256": c.sha(output / "registration.json"),
        "stage_timeout_seconds": ctx.PLAN["stage_timeout_seconds"],
        "total_timeout_seconds": ctx.PLAN["total_timeout_seconds"],
        "automatic_polling": False,
        "capture_rerun": False,
        "automatic_expansion": False,
        "automatic_retry": False,
    }
    c.write(output / "launch.json", receipt)
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("launch", "execute"))
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    (launch if args.command == "launch" else execute)(args.output.resolve())
