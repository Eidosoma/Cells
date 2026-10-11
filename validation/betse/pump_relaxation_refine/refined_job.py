"""Detached smaller-step follow-up to the completed 10 ms native probe."""

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
sys.path.insert(0, str(HERE.parent / "pump_relaxation_probe"))
import probe_job as old  # noqa: E402

c, ctx, write, ROOT = old.c, old.ctx, old.write, old.ROOT
helpers = old.previous
PRIOR = ROOT / "runs/ref-005e-native-probe-2026-09-17/probe-01"
PRIOR_REG = "c7ab26e3fdde3d9a46471508b20f7275b0622d0ef72c859445bd464d7a31746a"
PRIOR_SHA = "cd0c629469baa03d162b39a06a038701516d27dc97f0a3a78b64a8d8ad3c7414"
SCOPE = dict(
    purpose="Resolve the main-case native timestep miss without changing the science",
    rows=[
        dict(role=role, dt_s=step, duration_s=duration, mode=mode)
        for role, step, duration, mode in (
            ("medium", 7.8125e-7, 0.01, "observed"),
            ("fine", 3.90625e-7, 0.01, "observed"),
            ("fine_quiet", 3.90625e-7, 0.01, "unobserved"),
            ("fine_1ms", 3.90625e-7, 0.001, "observed"),
        )
    ],
    reused_step_s=1.5625e-6,
    native_runs=4,
    native_updates=66560,
    cells_runs=0,
    new_reference_solves=0,
    reference_review_reused=True,
    phase_timeout_seconds=dict(native=3000, comparison=1200),
    total_timeout_seconds=4500,
    cpu_affinity=[0, 1, 2, 3],
    worker_address_space_bytes=16 * 1024**3,
    stream_bytes=128 * 1024**2,
    per_file_bytes=128 * 1024**2,
    artifact_bytes=512 * 1024**2,
    free_disk_reserve_bytes=1024**3,
    physics_changed=False,
    scientific_tolerances_changed=False,
    automatic_retry=False,
    automatic_polling=False,
    automatic_followup=False,
)


def sources():
    names = set(old.sources()) | {str(p.relative_to(ROOT)) for p in HERE.glob("*.py")}
    return {n: c.sha(c.child(ROOT, n)) for n in sorted(names)}


def prior():
    old.authenticate(PRIOR, PRIOR_REG)
    done, _ = c.packet(
        PRIOR,
        "completion.json",
        PRIOR_SHA,
        extras=("launch.json", "runner.stdout.log", "runner.stderr.log"),
        count=947,
    )
    c.need(
        done["status"] == "native_probe_completed"
        and done["main_case_ladder_adequate"] is False
        and done["focused_reference_review_passed"] is True,
        "Prior probe disposition",
    )
    old.phase_gate("review", c.read(PRIOR / "review.json", None))
    comparison = c.read(PRIOR / "comparison.json", None)
    old.phase_gate("comparison", comparison)
    finest = comparison["rows"][-1]
    c.need(
        finest["dt_s"] == SCOPE["reused_step_s"]
        and finest["failed_comparisons"] == 1
        and list(finest["failed_groups"].values()) == [1]
        and next(iter(finest["failed_groups"])).endswith("/energy_balance"),
        "Prior miss changed",
    )
    coarse = c.read(PRIOR / "native/2/comparison.json", None)
    c.need({k: v for k, v in coarse.items() if k != "common_points"} == finest, "Coarse row link")
    for phase in ("review", "native", "comparison"):
        old.stderr_check(phase, (PRIOR / (phase + ".stderr.log")).read_text())
    c.need((PRIOR / "runner.stderr.log").read_bytes() == b"", "Prior controller stderr")
    old.reference()
    return dict(
        directory=str(PRIOR.relative_to(ROOT)),
        completion_sha256=PRIOR_SHA,
        registration_sha256=PRIOR_REG,
        review_sha256=c.sha(PRIOR / "review.json"),
        coarse_comparison_sha256=c.sha(PRIOR / "native/2/comparison.json"),
    )


def receipt(path):
    c.need(path.is_relative_to(ROOT / "reports"), "Software receipt location")
    result = c.e.software(path, 12)
    tests = ET.parse(path).getroot().findall("testsuite/testcase")
    required = {
        "test_large_stream",
        "test_unchanged_chunk_bytes",
        "test_preparation",
        "test_native_dispatch",
        "test_limits_restored",
        "test_numerical_miss_retained",
        "test_detached_launch",
        "test_failure_stops",
        "test_registration_tamper",
    }
    c.need(
        required <= {t.get("name", "").split("[")[0] for t in tests}
        and all("test_refined_probe" in t.get("classname", "") for t in tests),
        "Software coverage",
    )
    return result


def check(output, tests):
    helpers.previous.fresh(output)
    c.need(tests.is_relative_to(ROOT / "reports") and not tests.exists(), "Fresh software receipt")
    before, started = sources(), time.monotonic()
    output.mkdir(parents=True)
    write(output / "registration.json", dict(sources_sha256=before))
    helpers.previous.archive(output, before)
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
                    str(HERE / "test_refined_probe.py"),
                    "--junitxml=" + str(tests),
                    "--basetemp=" + str(output / "tests"),
                ],
                out,
                err,
                60,
            )
        checked = receipt(tests)
        c.need(
            sources() == before and (output / "tests.stderr.log").read_bytes() == b"",
            "Software context",
        )
        files, links = c.inventory(output, pytest_links=True)
        result = dict(
            status="refined_software_pass",
            sources_sha256=before,
            software=checked,
            files_sha256=files,
            pytest_internal_links=links,
            elapsed_seconds=time.monotonic() - started,
        )
        write(output / "completion.json", result)
        return dict(
            status=result["status"], software=checked, elapsed_seconds=result["elapsed_seconds"]
        )
    except BaseException:
        write(
            output / "failure.json",
            dict(status="software_failed", traceback=traceback.format_exc()),
        )
        raise


def software(path):
    c.need(path.is_relative_to(ROOT / "runs") and path.name == "completion.json", "Software path")
    result, _ = c.packet(path.parent, path.name, c.sha(path), pytest_links=True)
    c.need(
        result["status"] == "refined_software_pass" and result["sources_sha256"] == sources(),
        "Software/source mismatch",
    )
    c.capsule(path.parent, result["sources_sha256"])
    c.need(receipt(c.child(ROOT, result["software"]["path"])) == result["software"], "Software XML")
    return dict(path=str(path.relative_to(ROOT)), sha256=c.sha(path), xml=result["software"])


def budget(output):
    files, _ = c.inventory(output)
    sizes = [(output / name).stat().st_size for name in files]
    c.need(
        all(v <= SCOPE["per_file_bytes"] for v in sizes)
        and sum(sizes) < SCOPE["artifact_bytes"] - 1024**2
        and shutil.disk_usage(output).free >= SCOPE["free_disk_reserve_bytes"],
        "Refinement disk budget",
    )
    return sum(sizes)


def authenticate(output, expected, *, native=False):
    c.need(c.sha(output / "registration.json") == expected, "Refinement registration digest")
    r = c.read(output / "registration.json", None)
    c.need(
        r["schema"] == "cells.pump_relaxation_refinement@1"
        and r["scope"] == SCOPE
        and r["sources_sha256"] == sources()
        and r["reference_directory"] == str(old.REFERENCE.relative_to(ROOT))
        and r["reference_completion_sha256"]
        == old.REFERENCE_SHA
        == c.sha(old.REFERENCE / "completion.json")
        and r["prior"]["directory"] == str(PRIOR.relative_to(ROOT))
        and r["prior"]["completion_sha256"] == PRIOR_SHA == c.sha(PRIOR / "completion.json")
        and r["prior"]["registration_sha256"] == PRIOR_REG == c.sha(PRIOR / "registration.json")
        and r["prior"]["review_sha256"] == c.sha(PRIOR / "review.json")
        and r["prior"]["coarse_comparison_sha256"] == c.sha(PRIOR / "native/2/comparison.json"),
        "Refinement scope/sources/prior changed",
    )
    c.capsule(output, r["sources_sha256"])
    c.need(software(c.child(ROOT, r["software"]["path"])) == r["software"], "Software binding")
    if not native:
        c.need(r["runtime"] == ctx.runtime(), "Runtime changed")
    return r


def register(output, checked):
    helpers.previous.fresh(output)
    proof, prerequisite = software(checked), prior()
    r = dict(
        schema="cells.pump_relaxation_refinement@1",
        scope=SCOPE,
        prior=prerequisite,
        sources_sha256=sources(),
        software=proof,
        runtime=ctx.runtime(),
        reference_directory=str(old.REFERENCE.relative_to(ROOT)),
        reference_completion_sha256=old.REFERENCE_SHA,
        registered_utc=datetime.now(UTC).isoformat(),
    )
    output.mkdir(parents=True)
    write(output / "registration.json", r)
    helpers.previous.archive(output, r["sources_sha256"])
    budget(output)


def gate(phase, result):
    if phase == "native":
        c.need(
            result["status"] == "refined_native_captured"
            and result["native_runs"] == 4
            and [
                {k: v[k] for k in ("role", "dt_s", "duration_s", "mode")} for v in result["records"]
            ]
            == SCOPE["rows"],
            "Native coverage",
        )
    else:
        c.need(
            result["status"] == "refined_probe_completed"
            and len(result["rows"]) == 3
            and [v["dt_s"] for v in result["rows"]] == [1.5625e-6, 7.8125e-7, 3.90625e-7]
            and result["observer_pair"]["failed_comparisons"] == 0
            and result["fine_physical_prefix"]["steps"] == 2560
            and result["matched_10ms_qualified"] is False,
            "Comparison coverage",
        )


def worker(phase, output, expected):
    r = authenticate(output, expected, native=phase == "native")
    helpers.deadline(SCOPE["phase_timeout_seconds"][phase])
    resource.setrlimit(resource.RLIMIT_AS, (SCOPE["worker_address_space_bytes"],) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (SCOPE["per_file_bytes"],) * 2)
    c.need(sorted(os.sched_getaffinity(0)) == SCOPE["cpu_affinity"], "Worker affinity")
    warnings.simplefilter("error")
    try:
        import refined_work

        result = (refined_work.capture if phase == "native" else refined_work.compare)(
            r, output, write, budget
        )
        gate(phase, result)
        c.need(r["sources_sha256"] == sources(), "Worker sources changed")
        result["worker_peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        write(output / (phase + ".json"), result)
    except BaseException:
        write(
            output / (phase + "-failure.json"),
            dict(status="worker_failed", traceback=traceback.format_exc()),
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def stderr_check(phase, text):
    expected = "[refined_job.py] Ignoring cutting event, as cut profiles are disabled."
    c.need(text.splitlines() == ([expected] * 8 if phase == "native" else []), "Unexpected stderr")


def execute(output, expected):
    c.need(not (output / "started.json").exists(), "Refinement already attempted")
    start = time.monotonic()
    helpers.deadline(SCOPE["total_timeout_seconds"])
    try:
        write(
            output / "started.json",
            dict(pid=os.getpid(), started_utc=datetime.now(UTC).isoformat()),
        )
        r = authenticate(output, expected)
        c.need(r["prior"] == prior(), "Prerequisite binding")
        elapsed = {}
        for phase, timeout in SCOPE["phase_timeout_seconds"].items():
            began = time.monotonic()
            python = old.NATIVE_PYTHON if phase == "native" else ROOT / ".venv/bin/python"
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
                        expected,
                    ],
                    out,
                    err,
                    timeout,
                )
            stderr_check(phase, (output / (phase + ".stderr.log")).read_text())
            gate(phase, c.read(output / (phase + ".json"), None))
            budget(output)
            elapsed[phase] = time.monotonic() - began
        authenticate(output, expected)
        c.need(r["prior"] == prior(), "Prerequisites changed during run")
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
                status="refined_probe_completed",
                main_case_ladder_adequate=result["main_case_ladder_adequate"],
                native_runs=4,
                cells_runs=0,
                new_reference_solves=0,
                reused_native_comparisons=1,
                phase_elapsed_seconds=elapsed,
                elapsed_seconds=time.monotonic() - start,
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
                status="refined_probe_failed_not_qualified",
                traceback=traceback.format_exc(),
                elapsed_seconds=time.monotonic() - start,
                automatic_retry=False,
                automatic_followup=False,
            ),
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def launch(output, checked):
    register(output, checked)
    try:
        digest = c.sha(output / "registration.json")
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
            pid=process.pid,
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
    needed = dict(
        check="tests", launch="software", execute="registration_sha", worker="registration_sha"
    )[args.action]
    if getattr(args, needed) is None or (args.action == "worker" and args.phase is None):
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
