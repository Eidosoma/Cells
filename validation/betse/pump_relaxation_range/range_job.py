"""One prospective pump-only timestep-range test after a sealed arithmetic diagnosis."""

import argparse
import json
import os
import resource
import shutil
import signal
import subprocess
import sys
import time
import traceback
import warnings
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pump_relaxation_diagnosis"))
import diagnose_job as diagnosis  # noqa: E402

prior, c, helpers, write, ROOT = (
    diagnosis.prior,
    diagnosis.c,
    diagnosis.helpers,
    diagnosis.write,
    diagnosis.ROOT,
)
CAPTURE = diagnosis.CAPTURE
DIAG = ROOT / "runs/ref-005e-bath-diagnosis-2026-09-18/diagnosis-01"
DIAG_REG = "63cd0eb7edd207f665dad43aabe4349a4672ad7a3216f321f095cfe16ae102c8"
DIAG_SHA = "9620748cecd851edb8d3b8cbcc45a8eb30aca97031a5200998500182381350ad"
STEPS = [6.25e-6, 3.125e-6, 1.5625e-6]
SCOPE = dict(
    purpose="Test the earlier pump-only range after confirmed bath-averaging roundoff",
    duration_s=0.01,
    rows=[
        dict(id="pump_only", role="pump_only/" + role, dt_s=step, duration_s=0.01, mode=mode)
        for role, step, mode in (
            ("coarse", STEPS[0], "observed"),
            ("medium", STEPS[1], "observed"),
            ("fine_quiet", STEPS[2], "unobserved"),
        )
    ],
    native_step_ranges_s={v: STEPS if v == "pump_only" else prior.STEPS for v in prior.VARIANTS},
    new_native_runs=3,
    new_native_updates=11200,
    reused_native_observed_rows=16,
    new_cells_runs=0,
    reused_cells_trajectories=24,
    reused_restart_suffixes=6,
    new_reference_solves=0,
    reused_reference_solves=18,
    phase_timeout_seconds=dict(native=1200, comparison=600),
    total_timeout_seconds=2100,
    cpu_affinity=[0, 1, 2, 3],
    worker_address_space_bytes=8 * 1024**3,
    per_file_bytes=128 * 1024**2,
    stream_bytes=128 * 1024**2,
    artifact_bytes=256 * 1024**2,
    free_disk_reserve_bytes=1024**3,
    physics_changed=False,
    production_changed=False,
    scientific_tolerances_changed=False,
    original_verdict_changed=False,
    automatic_polling=False,
    automatic_retry=False,
    automatic_followup=False,
)


def sources():
    names = set(diagnosis.sources()) | {str(p.relative_to(ROOT)) for p in HERE.glob("*.py")}
    return {n: c.sha(c.child(ROOT, n)) for n in sorted(names)}


def links():
    return dict(
        diagnosis_directory=str(DIAG.relative_to(ROOT)),
        diagnosis_registration_sha256=DIAG_REG,
        diagnosis_completion_sha256=DIAG_SHA,
        campaign_completion_sha256=diagnosis.DONE_SHA,
        files_sha256={
            str(p.relative_to(ROOT)): c.sha(p)
            for p in (
                DIAG / "diagnosis.json",
                DIAG / "row-2.json",
                CAPTURE / "comparison.json",
                CAPTURE / "cells.json",
                CAPTURE / "native/pump_only/0/comparison.json",
            )
        },
    )


def inputs():
    diagnosis.authenticate(DIAG, DIAG_REG)
    diagnosis.inputs()
    done, _ = c.packet(
        DIAG,
        "completion.json",
        DIAG_SHA,
        extras=("launch.json", "runner.stdout.log", "runner.stderr.log"),
        count=10,
    )
    evidence = c.read(DIAG / "diagnosis.json", None)
    diagnosis.gate(evidence)
    c.need(
        done["status"] == evidence["status"] == "saved_bath_arithmetic_replayed"
        and done["original_convergence_verdict_changed"] is False,
        "Diagnosis disposition",
    )
    c.need(
        all(
            (DIAG / name).read_bytes() == b"" for name in ("runner.stderr.log", "replay.stderr.log")
        ),
        "Diagnosis stderr",
    )
    c.need(
        prior.ctx.inherited()["protocol"]["native_steps_s"] == STEPS,
        "Use the pre-existing qualified 1 ms range, not an outcome-selected scan",
    )
    fine = c.read(CAPTURE / "native/pump_only/0/comparison.json", None)
    c.need(
        fine["dt_s"] == STEPS[-1]
        and fine["within_finest_limits"] is True
        and fine["failed_comparisons"] == 0,
        "Saved finest row",
    )
    return links()


def receipt(path):
    c.need(path.is_relative_to(ROOT / "reports"), "Software receipt location")
    result = c.e.software(path, 12)
    tests = ET.parse(path).getroot().findall("testsuite/testcase")
    required = {
        "test_scope",
        "test_native_dispatch",
        "test_conclusion",
        "test_compare_dispatch",
        "test_binding",
        "test_detached",
        "test_failed_child",
        "test_completion",
    }
    c.need(
        required <= {t.get("name", "").split("[")[0] for t in tests}
        and all("test_range" in t.get("classname", "") for t in tests),
        "Software coverage",
    )
    return result


def check(output, xml):
    helpers.previous.fresh(output)
    c.need(xml.is_relative_to(ROOT / "reports") and not xml.exists(), "Fresh test receipt")
    frozen, start = sources(), time.monotonic()
    output.mkdir(parents=True)
    write(output / "registration.json", dict(sources_sha256=frozen))
    helpers.previous.archive(output, frozen)
    try:
        with (
            (output / "tests.stdout.log").open("x") as out,
            (output / "tests.stderr.log").open("x") as err,
        ):
            helpers.run_child(
                [
                    str(ROOT / ".venv/bin/python"),
                    "-B",
                    "-m",
                    "pytest",
                    "-q",
                    "-W",
                    "error",
                    str(HERE / "test_range.py"),
                    "--junitxml=" + str(xml),
                    "--basetemp=" + str(output / "tests"),
                ],
                out,
                err,
                60,
            )
        tested = receipt(xml)
        c.need(
            frozen == sources() and (output / "tests.stderr.log").read_bytes() == b"",
            "Test context",
        )
        files, aliases = c.inventory(output, pytest_links=True)
        result = dict(
            status="pump_range_software_pass",
            sources_sha256=frozen,
            software=tested,
            files_sha256=files,
            pytest_internal_links=aliases,
            elapsed_seconds=time.monotonic() - start,
        )
        write(output / "completion.json", result)
        return {k: result[k] for k in ("status", "software", "elapsed_seconds")}
    except BaseException:
        write(
            output / "failure.json",
            dict(status="software_failed", traceback=traceback.format_exc()),
        )
        raise


def software(path):
    c.need(path.is_relative_to(ROOT / "runs") and path.name == "completion.json", "Software path")
    done, _ = c.packet(path.parent, path.name, c.sha(path), pytest_links=True)
    c.need(
        done["status"] == "pump_range_software_pass" and done["sources_sha256"] == sources(),
        "Software/source binding",
    )
    c.capsule(path.parent, done["sources_sha256"])
    c.need(receipt(c.child(ROOT, done["software"]["path"])) == done["software"], "Test XML binding")
    return dict(path=str(path.relative_to(ROOT)), sha256=c.sha(path), xml=done["software"])


def budget(output):
    files, _ = c.inventory(output)
    sizes = [(output / name).stat().st_size for name in files]
    c.need(
        all(n <= SCOPE["per_file_bytes"] for n in sizes)
        and sum(sizes) < SCOPE["artifact_bytes"] - 1024**2
        and shutil.disk_usage(output).free >= SCOPE["free_disk_reserve_bytes"],
        "Range disk bounds",
    )


def register(output, proof):
    helpers.previous.fresh(output)
    tested, inherited = software(proof), inputs()
    output.mkdir(parents=True)
    frozen = sources()
    write(
        output / "registration.json",
        dict(
            schema="cells.pump_only_range@1",
            scope=SCOPE,
            input=inherited,
            sources_sha256=frozen,
            software=tested,
            runtime=prior.ctx.runtime(),
            registered_utc=datetime.now(UTC).isoformat(),
        ),
    )
    helpers.previous.archive(output, frozen)
    budget(output)


def authenticate(output, digest, *, native=False):
    c.need(c.sha(output / "registration.json") == digest, "Range registration digest")
    r = c.read(output / "registration.json", None)
    c.need(
        r["schema"] == "cells.pump_only_range@1"
        and r["scope"] == SCOPE
        and r["input"] == links()
        and r["sources_sha256"] == sources()
        and c.sha(DIAG / "completion.json") == DIAG_SHA
        and c.sha(DIAG / "registration.json") == DIAG_REG
        and c.sha(CAPTURE / "completion.json") == diagnosis.DONE_SHA,
        "Range scope/input changed",
    )
    c.capsule(output, r["sources_sha256"])
    c.need(software(c.child(ROOT, r["software"]["path"])) == r["software"], "Software binding")
    if not native:
        c.need(r["runtime"] == prior.ctx.runtime(), "Runtime changed")
    return r


def gate(phase, result):
    if phase == "native":
        c.need(
            result["status"] == "matched_native_captured"
            and result["native_runs"] == 3
            and [
                {k: v[k] for k in ("id", "role", "dt_s", "duration_s", "mode")}
                for v in result["records"]
            ]
            == SCOPE["rows"],
            "Native range coverage",
        )
    else:
        c.need(
            result["status"] == "case_specific_range_completed"
            and result["producer_passed"]
            == (
                result["reused_cells_checks"]["passed"]
                and all(v["passed"] for v in result["cases"].values())
            )
            and {k: v["native_steps_s"] for k, v in result["cases"].items()}
            == SCOPE["native_step_ranges_s"]
            and result["original_common_range_passed"] is False
            and result["original_verdict_changed"] is False
            and result["matched_10ms_qualified"] is False
            and result["independent_review_pending"] is True,
            "Comparison scope/coverage",
        )


def stderr_check(phase, text):
    line = "[range_job.py] Ignoring cutting event, as cut profiles are disabled."
    c.need(text.splitlines() == ([line] * 6 if phase == "native" else []), "Unexpected stderr")


def worker(phase, output, digest):
    r = authenticate(output, digest, native=phase == "native")
    helpers.deadline(SCOPE["phase_timeout_seconds"][phase])
    try:
        resource.setrlimit(resource.RLIMIT_AS, (SCOPE["worker_address_space_bytes"],) * 2)
        resource.setrlimit(resource.RLIMIT_FSIZE, (SCOPE["per_file_bytes"],) * 2)
        c.need(sorted(os.sched_getaffinity(0)) == SCOPE["cpu_affinity"], "CPU affinity")
        warnings.simplefilter("error")
        import range_work

        result = (range_work.capture if phase == "native" else range_work.compare)(
            r, output, write, budget
        )
        gate(phase, result)
        c.need(r["sources_sha256"] == sources(), "Worker source changed")
        result["worker_peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        write(output / (phase + ".json"), result)
        budget(output)
    except BaseException:
        write(
            output / (phase + "-failure.json"),
            dict(status="worker_failed", traceback=traceback.format_exc()),
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def execute(output, digest):
    c.need(not (output / "started.json").exists(), "Range already attempted")
    start = time.monotonic()
    helpers.deadline(SCOPE["total_timeout_seconds"])
    try:
        write(
            output / "started.json",
            dict(pid=os.getpid(), started_utc=datetime.now(UTC).isoformat()),
        )
        r = authenticate(output, digest)
        c.need(inputs() == r["input"], "Input binding")
        elapsed = {}
        for phase, timeout in SCOPE["phase_timeout_seconds"].items():
            began = time.monotonic()
            python = prior.old.old.NATIVE_PYTHON if phase == "native" else ROOT / ".venv/bin/python"
            with (
                (output / (phase + ".stdout.log")).open("x") as out,
                (output / (phase + ".stderr.log")).open("x") as err,
            ):
                helpers.run_child(
                    [
                        str(python),
                        "-B",
                        str(Path(__file__).resolve()),
                        "worker",
                        str(output),
                        "--phase",
                        phase,
                        "--registration-sha",
                        digest,
                    ],
                    out,
                    err,
                    timeout,
                )
            stderr_check(phase, (output / (phase + ".stderr.log")).read_text())
            gate(phase, c.read(output / (phase + ".json"), None))
            budget(output)
            elapsed[phase] = time.monotonic() - began
        authenticate(output, digest)
        c.need(inputs() == r["input"], "Saved input changed during run")
        result = c.read(output / "comparison.json", None)
        files, _ = c.inventory(output)
        files = {
            k: v
            for k, v in files.items()
            if k not in ("launch.json", "runner.stdout.log", "runner.stderr.log")
        }
        write(
            output / "completion.json",
            dict(
                status="case_specific_producer_pass_pending_review"
                if result["producer_passed"]
                else "pump_only_range_miss_not_qualified",
                producer_passed=result["producer_passed"],
                files_sha256=files,
                phase_elapsed_seconds=elapsed,
                elapsed_seconds=time.monotonic() - start,
                finished_utc=datetime.now(UTC).isoformat(),
                native_runs=3,
                cells_runs=0,
                new_reference_solves=0,
                original_common_range_passed=False,
                original_verdict_changed=False,
                matched_10ms_qualified=False,
                independent_review_pending=True,
                automatic_followup=False,
            ),
        )
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        write(
            output / "failure.json",
            dict(
                status="range_failed_not_qualified",
                traceback=traceback.format_exc(),
                elapsed_seconds=time.monotonic() - start,
                automatic_retry=False,
                automatic_followup=False,
            ),
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def launch(output, proof):
    register(output, proof)
    try:
        digest = c.sha(output / "registration.json")
        with (
            (output / "runner.stdout.log").open("x") as out,
            (output / "runner.stderr.log").open("x") as err,
        ):
            child = subprocess.Popen(
                [
                    "taskset",
                    "-c",
                    "0-3",
                    str(ROOT / ".venv/bin/python"),
                    "-B",
                    str(Path(__file__).resolve()),
                    "execute",
                    str(output),
                    "--registration-sha",
                    digest,
                ],
                cwd=ROOT,
                env=helpers.previous.environment(),
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                start_new_session=True,
            )
        result = dict(
            status="launched_detached",
            pid=child.pid,
            registration_sha256=digest,
            launched_utc=datetime.now(UTC).isoformat(),
            automatic_polling=False,
        )
        write(output / "launch.json", result)
        return result
    except BaseException:
        write(
            output / "launch-failure.json",
            dict(status="launch_failed", traceback=traceback.format_exc()),
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "launch", "execute", "worker"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--tests", type=Path)
    parser.add_argument("--software", type=Path)
    parser.add_argument("--registration-sha")
    parser.add_argument("--phase", choices=tuple(SCOPE["phase_timeout_seconds"]))
    args = parser.parse_args()
    required = dict(
        check="tests", launch="software", execute="registration_sha", worker="registration_sha"
    )[args.action]
    if getattr(args, required) is None or (args.action == "worker" and args.phase is None):
        parser.error("Missing input for " + args.action)
    output = args.output.absolute()
    if args.action == "check":
        print(json.dumps(check(output, args.tests.absolute()), sort_keys=True))
    elif args.action == "launch":
        print(json.dumps(launch(output, args.software.absolute()), sort_keys=True))
    elif args.action == "execute":
        execute(output, args.registration_sha)
    else:
        worker(args.phase, output, args.registration_sha)
