"""One detached saved-reference review and four-run native probe; no full campaign."""

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
sys.path.insert(0, str(HERE.parent / "pump_relaxation_scope"))
import relax_context as ctx  # noqa: E402
import relax_job as previous  # noqa: E402

c, write = ctx.c, previous.write
ROOT = c.ROOT
REFERENCE = ROOT / "runs/ref-005e-reference-scope-2026-09-17/scope-01"
REFERENCE_REG_SHA = "3a41f3bb4e51ab73c6894b810cd263a155c0476f85493aea7155fd47371892b2"
REFERENCE_SHA = "3a7710f88c309b16c2cca9739282801fc2b3b9bad8bf61253add4c816404d29c"
NATIVE_PYTHON = ROOT / "upstream/betse-venv/bin/python"
SCOPE = dict(
    purpose="Review saved references, then measure the main-case native ladder; not full parity",
    duration_s=0.01,
    variant="pump_leak",
    rows=[dict(dt_s=h, mode="observed") for h in (6.25e-6, 3.125e-6, 1.5625e-6)]
    + [dict(dt_s=1.5625e-6, mode="unobserved")],
    native_runs=4,
    cells_runs=0,
    new_reference_solves=0,
    cpu_affinity=[0, 1, 2, 3],
    phase_timeout_seconds=dict(review=180, native=900, comparison=600),
    total_timeout_seconds=1800,
    address_space_bytes=8 * 1024**3,
    per_file_bytes=128 * 1024**2,
    artifact_bytes=512 * 1024**2,
    free_disk_reserve_bytes=1024**3,
    scientific_tolerances_changed=False,
    production_changed=False,
    automatic_retry=False,
    automatic_polling=False,
    automatic_followup=False,
)
REQUIRED = {
    "test_reference_corruption",
    "test_independent_energy",
    "test_preparation",
    "test_prefix",
    "test_numerical_miss_retained",
    "test_launch_detached",
    "test_registration_tamper",
    "test_phase_failure_stops",
    "test_native_dispatch",
}


def sources():
    names = set(c.read(c.NATIVE / "registration.json", None)["sources_sha256"]) | set(ctx.sources())
    names.add("validation/betse/pump_coupled_audit/coupled_audit.py")
    names.update(str(p.relative_to(ROOT)) for p in HERE.glob("*.py"))
    return {n: c.sha(c.child(ROOT, n)) for n in sorted(names)}


def reference():
    registration = previous.authenticate(REFERENCE, REFERENCE_REG_SHA, full=True)
    done, _ = c.packet(
        REFERENCE,
        "completion.json",
        REFERENCE_SHA,
        extras=("launch.json", "runner.stdout.log", "runner.stderr.log"),
        count=24,
    )
    summary = c.read(REFERENCE / "reference.json", None)
    previous.gate(summary, registration, REFERENCE)
    c.need(
        done["status"] == summary["status"]
        and done["reference_sha256"] == c.sha(REFERENCE / "reference.json")
        and c.read(REFERENCE / "launch.json")["registration_sha256"] == REFERENCE_REG_SHA,
        "Reference completion binding",
    )
    for name in ("runner.stderr.log", "reference.stderr.log"):
        c.need((REFERENCE / name).read_bytes() == b"", "Reference stderr")
    return registration, summary


def receipt(path):
    c.need(path.is_relative_to(ROOT / "reports"), "Receipt location")
    result = c.e.software(path, 15)
    tests = ET.parse(path).getroot().findall("testsuite/testcase")
    c.need(
        REQUIRED <= {t.get("name", "").split("[")[0] for t in tests}
        and all("test_relax_probe" in t.get("classname", "") for t in tests),
        "Probe test coverage",
    )
    return result


def check(output, tests):
    previous.previous.fresh(output)
    c.need(tests.is_relative_to(ROOT / "reports") and not tests.exists(), "Fresh receipt")
    before, started = sources(), time.monotonic()
    output.mkdir(parents=True)
    write(output / "registration.json", dict(sources_sha256=before))
    previous.previous.archive(output, before)
    try:
        with (
            (output / "tests.stdout.log").open("x") as out,
            (output / "tests.stderr.log").open("x") as err,
        ):
            previous.run_child(
                [
                    str(ROOT / ".venv/bin/python"),
                    "-B",
                    "-m",
                    "pytest",
                    "-q",
                    "-W",
                    "error",
                    str(HERE / "test_relax_probe.py"),
                    "--junitxml=" + str(tests),
                    "--basetemp=" + str(output / "tests"),
                ],
                out,
                err,
                60,
            )
        software = receipt(tests)
        c.need(
            sources() == before and (output / "tests.stderr.log").read_bytes() == b"",
            "Software context/stderr",
        )
        files, links = c.inventory(output, pytest_links=True)
        result = dict(
            status="probe_software_pass",
            software=software,
            sources_sha256=before,
            files_sha256=files,
            pytest_internal_links=links,
            elapsed_seconds=time.monotonic() - started,
        )
        write(output / "completion.json", result)
        return dict(
            status=result["status"], software=software, elapsed_seconds=result["elapsed_seconds"]
        )
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
        done["status"] == "probe_software_pass" and done["sources_sha256"] == sources(),
        "Software/source binding",
    )
    c.capsule(path.parent, done["sources_sha256"])
    c.need(receipt(c.child(ROOT, done["software"]["path"])) == done["software"], "Software receipt")
    return dict(path=str(path.relative_to(ROOT)), sha256=c.sha(path), xml=done["software"])


def budget(output):
    files, _ = c.inventory(output)
    sizes = [(output / name).stat().st_size for name in files]
    c.need(
        all(n <= SCOPE["per_file_bytes"] for n in sizes)
        and sum(sizes) < SCOPE["artifact_bytes"] - 1024**2
        and shutil.disk_usage(output).free >= SCOPE["free_disk_reserve_bytes"],
        "Probe disk budget",
    )
    return sum(sizes)


def authenticate(output, expected, *, native=False):
    c.need(c.sha(output / "registration.json") == expected, "Probe registration identity")
    r = c.read(output / "registration.json", None)
    c.need(
        r["schema"] == "cells.pump_relaxation_probe@1"
        and r["scope"] == SCOPE
        and r["sources_sha256"] == sources()
        and r["reference_directory"] == str(REFERENCE.relative_to(ROOT))
        and r["reference_completion_sha256"]
        == REFERENCE_SHA
        == c.sha(REFERENCE / "completion.json")
        and r["reference_registration_sha256"]
        == REFERENCE_REG_SHA
        == c.sha(REFERENCE / "registration.json"),
        "Probe scope/source/reference changed",
    )
    c.capsule(output, r["sources_sha256"])
    c.need(
        software(c.child(ROOT, r["software"]["path"])) == r["software"], "Probe software changed"
    )
    if not native:
        c.need(r["runtime"] == ctx.runtime(), "Probe runtime changed")
    return r


def register(output, checked):
    previous.previous.fresh(output)
    proof = software(checked)
    reference()
    r = dict(
        schema="cells.pump_relaxation_probe@1",
        scope=SCOPE,
        sources_sha256=sources(),
        software=proof,
        runtime=ctx.runtime(),
        registered_utc=datetime.now(UTC).isoformat(),
        reference_directory=str(REFERENCE.relative_to(ROOT)),
        reference_completion_sha256=REFERENCE_SHA,
        reference_registration_sha256=REFERENCE_REG_SHA,
    )
    output.mkdir(parents=True)
    write(output / "registration.json", r)
    previous.previous.archive(output, r["sources_sha256"])
    budget(output)
    return r


def phase_gate(phase, result):
    if phase == "review":
        c.need(
            result["status"] == "focused_reference_review_pass"
            and result["reference_solves"] == 18
            and len(result["records"]) == 18
            and result["new_integrations"] == 0,
            "Reference review gate",
        )
    elif phase == "native":
        c.need(
            result["status"] == "native_probe_captured"
            and result["native_runs"] == 4
            and len(result["records"]) == 4,
            "Native probe coverage",
        )
    else:
        c.need(
            result["status"] == "native_probe_completed"
            and len(result["rows"]) == 3
            and result["observer_pair"]["failed_comparisons"] == 0
            and result["matched_10ms_qualified"] is False
            and result["six_control_ladder_qualified"] is False,
            "Native comparison gate",
        )
        # Numerical misses are a useful probe result, not a launch/harness failure.


def worker(phase, output, expected):
    r = authenticate(output, expected, native=phase == "native")
    previous.deadline(SCOPE["phase_timeout_seconds"][phase])
    resource.setrlimit(resource.RLIMIT_AS, (SCOPE["address_space_bytes"],) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (SCOPE["per_file_bytes"],) * 2)
    c.need(sorted(os.sched_getaffinity(0)) == SCOPE["cpu_affinity"], "Probe affinity")
    warnings.simplefilter("error")
    try:
        if phase == "review":
            import probe_review

            result = probe_review.run(
                c.read(REFERENCE / "registration.json", None),
                c.read(REFERENCE / "reference.json", None),
                REFERENCE,
            )
        else:
            import probe_native

            action = probe_native.capture if phase == "native" else probe_native.compare
            result = action(r, output, write, budget)
        phase_gate(phase, result)
        c.need(sources() == r["sources_sha256"], "Worker sources changed")
        result["worker_peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        write(output / (phase + ".json"), result)
    except BaseException:
        write(
            output / (phase + "-failure.json"),
            dict(status="phase_failed", traceback=traceback.format_exc()),
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def stderr_check(phase, text):
    if phase == "native":
        expected = "[probe_job.py] Ignoring cutting event, as cut profiles are disabled."
        c.need(text.splitlines() == [expected] * 8, "Unexpected native stderr")
    else:
        c.need(text == "", "Unexpected review/comparison stderr")


def execute(output, expected):
    c.need(not (output / "started.json").exists(), "Probe already attempted")
    started = time.monotonic()
    previous.deadline(SCOPE["total_timeout_seconds"])
    try:
        write(
            output / "started.json",
            dict(pid=os.getpid(), started_utc=datetime.now(UTC).isoformat()),
        )
        authenticate(output, expected)
        reference()
        elapsed = {}
        for phase, timeout in SCOPE["phase_timeout_seconds"].items():
            phase_start = time.monotonic()
            python = NATIVE_PYTHON if phase == "native" else ROOT / ".venv/bin/python"
            with (
                (output / (phase + ".stdout.log")).open("x") as out,
                (output / (phase + ".stderr.log")).open("x") as err,
            ):
                previous.run_child(
                    [
                        str(python),
                        "-B",
                        str(Path(__file__).resolve()),
                        "worker",
                        str(output),
                        "--phase",
                        phase,
                        "--registration-sha",
                        expected,
                    ],
                    out,
                    err,
                    timeout,
                )
            stderr_check(phase, (output / (phase + ".stderr.log")).read_text())
            phase_gate(phase, c.read(output / (phase + ".json"), None))
            budget(output)
            elapsed[phase] = time.monotonic() - phase_start
        authenticate(output, expected)
        reference()
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
                status="native_probe_completed",
                main_case_ladder_adequate=result["main_case_ladder_adequate"],
                native_runs=4,
                cells_runs=0,
                new_reference_solves=0,
                focused_reference_review_passed=True,
                phase_elapsed_seconds=elapsed,
                elapsed_seconds=time.monotonic() - started,
                finished_utc=datetime.now(UTC).isoformat(),
                files_sha256=files,
                matched_10ms_qualified=False,
                automatic_followup=False,
            ),
        )
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        write(
            output / "failure.json",
            dict(
                status="probe_failed_not_qualified",
                elapsed_seconds=time.monotonic() - started,
                traceback=traceback.format_exc(),
                automatic_retry=False,
                automatic_followup=False,
            ),
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def launch(output, checked):
    register(output, checked)
    expected = c.sha(output / "registration.json")
    with (
        (output / "runner.stdout.log").open("x") as out,
        (output / "runner.stderr.log").open("x") as err,
    ):
        process = subprocess.Popen(
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
                expected,
            ],
            cwd=ROOT,
            env=previous.previous.environment(),
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=err,
            start_new_session=True,
        )
    result = dict(
        status="launched_detached",
        pid=process.pid,
        registration_sha256=expected,
        launched_utc=datetime.now(UTC).isoformat(),
        automatic_polling=False,
    )
    write(output / "launch.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "launch", "execute", "worker"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--tests", type=Path)
    parser.add_argument("--software", type=Path)
    parser.add_argument("--registration-sha")
    parser.add_argument("--phase", choices=tuple(SCOPE["phase_timeout_seconds"]))
    args = parser.parse_args()
    output = args.output.absolute()
    needed = dict(
        check="tests", launch="software", execute="registration_sha", worker="registration_sha"
    )[args.action]
    if getattr(args, needed) is None or (args.action == "worker" and args.phase is None):
        parser.error("Missing required input for " + args.action)
    if args.action == "check":
        print(json.dumps(check(output, args.tests.absolute()), sort_keys=True))
    elif args.action == "launch":
        print(json.dumps(launch(output, args.software.absolute()), sort_keys=True))
    elif args.action == "execute":
        execute(output, args.registration_sha)
    else:
        worker(args.phase, output, args.registration_sha)
