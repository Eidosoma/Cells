"""One detached six-control 10 ms campaign; frozen science and durable outcomes."""

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
sys.path.insert(0, str(HERE.parent / "pump_relaxation_refine"))
import refined_job as old  # noqa: E402

c, ctx, helpers, write, ROOT = old.c, old.ctx, old.helpers, old.write, old.ROOT
PRIOR = ROOT / "runs/ref-005e-finer-native-2026-09-17/refinement-01"
PRIOR_REG = "71e7cfebc0a933f569e8bee4c7913ab509dfdbcc482120b63487e46115d42f10"
PRIOR_SHA = "c27ad36b6f9496c1622cbea64f3ee1dc4ed5b20143407b2234b219ee8472854d"
VARIANTS = ["pump_leak", "pump_only", "leak_only", "all_blocked", "half_density", "closed_boundary"]
STEPS = [1.5625e-6, 7.8125e-7, 3.90625e-7]
SCOPE = dict(
    duration_s=0.01,
    variants=VARIANTS,
    native_steps_s=STEPS,
    rows=[
        dict(id=identifier, role=identifier + "/" + role, dt_s=step, duration_s=0.01, mode=mode)
        for identifier in VARIANTS[1:]
        for role, step, mode in [(str(i), h, "observed") for i, h in enumerate(STEPS)]
        + [("quiet", STEPS[-1], "unobserved")]
    ],
    new_native_runs=20,
    new_native_updates=352000,
    reused_native_observed_rows=3,
    reused_finest_observer_pairs=1,
    finest_observer_pairs=6,
    cells_trajectories=24,
    cells_steps_s=[5e-5, 2.5e-5, 1.25e-5],
    cells_eager_step_s=5e-5,
    restart_step_s=2.5e-5,
    restart_time_s=0.005,
    restart_suffixes=6,
    new_reference_solves=0,
    reused_reference_solves=18,
    phase_timeout_seconds=dict(cells=1800, native=21600, comparison=5400),
    total_timeout_seconds=30000,
    cpu_affinity=[0, 1, 2, 3],
    worker_address_space_bytes=16 * 1024**3,
    per_file_bytes=128 * 1024**2,
    stream_bytes=128 * 1024**2,
    artifact_bytes=4 * 1024**3,
    free_disk_reserve_bytes=1024**3,
    production_changed=False,
    physics_changed=False,
    scientific_tolerances_changed=False,
    automatic_polling=False,
    automatic_retry=False,
    automatic_followup=False,
)


def sources():
    names = set(old.sources()) | {str(p.relative_to(ROOT)) for p in HERE.glob("*.py")}
    return {n: c.sha(c.child(ROOT, n)) for n in sorted(names)}


def reused_rows():
    return [
        old.PRIOR / "native/2/comparison.json",
        PRIOR / "native/medium/comparison.json",
        PRIOR / "native/fine/comparison.json",
    ]


def prerequisite_links():
    return dict(
        directory=str(PRIOR.relative_to(ROOT)),
        registration_sha256=PRIOR_REG,
        completion_sha256=PRIOR_SHA,
        files_sha256={
            str(p.relative_to(ROOT)): c.sha(p)
            for p in reused_rows()
            + [
                PRIOR / "comparison.json",
                old.PRIOR / "review.json",
                old.old.REFERENCE / "completion.json",
            ]
        },
    )


def prerequisites():
    old.authenticate(PRIOR, PRIOR_REG)
    old.prior()
    done, _ = c.packet(
        PRIOR,
        "completion.json",
        PRIOR_SHA,
        extras=("launch.json", "runner.stdout.log", "runner.stderr.log"),
        count=3403,
    )
    c.need(
        done["status"] == "refined_probe_completed" and done["main_case_ladder_adequate"] is True,
        "Successful finer-step prerequisite",
    )
    comparison = c.read(PRIOR / "comparison.json", None)
    old.gate("comparison", comparison)
    c.need(
        comparison["main_case_ladder_adequate"] is True
        and comparison["physics_changed"] is False
        and comparison["scientific_tolerances_changed"] is False,
        "Refinement disposition",
    )
    for row, path in zip(comparison["rows"], reused_rows(), strict=True):
        saved = c.read(path, None)
        c.need(row == {k: v for k, v in saved.items() if k != "common_points"}, "Reused row link")
    for phase in ("native", "comparison"):
        old.stderr_check(phase, (PRIOR / (phase + ".stderr.log")).read_text())
    c.need((PRIOR / "runner.stderr.log").read_bytes() == b"", "Prior controller stderr")
    return prerequisite_links()


def environment():
    return helpers.previous.environment() | {"JAX_ENABLE_X64": "true", "JAX_PLATFORMS": "cpu"}


def receipt(path):
    c.need(path.is_relative_to(ROOT / "reports"), "Software receipt location")
    result = c.e.software(path, 20)
    tests = ET.parse(path).getroot().findall("testsuite/testcase")
    required = {
        "test_preparation",
        "test_cells_adapter",
        "test_cells_smoke",
        "test_native_dispatch",
        "test_coarse_failure_policy",
        "test_cells_checks",
        "test_registration_binding",
        "test_detached_launch",
        "test_failure_stops",
    }
    c.need(
        required <= {t.get("name", "").split("[")[0] for t in tests}
        and all("test_matched" in t.get("classname", "") for t in tests),
        "Software coverage",
    )
    return result


def check(output, tests):
    helpers.previous.fresh(output)
    c.need(tests.is_relative_to(ROOT / "reports") and not tests.exists(), "Fresh software receipt")
    before, start = sources(), time.monotonic()
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
                    str(HERE / "test_matched.py"),
                    "--junitxml=" + str(tests),
                    "--basetemp=" + str(output / "tests"),
                ],
                out,
                err,
                60,
            )
        checked = receipt(tests)
        c.need(
            before == sources() and (output / "tests.stderr.log").read_bytes() == b"",
            "Software context/stderr",
        )
        files, links = c.inventory(output, pytest_links=True)
        result = dict(
            status="matched_software_pass",
            software=checked,
            sources_sha256=before,
            files_sha256=files,
            pytest_internal_links=links,
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
    result, _ = c.packet(path.parent, path.name, c.sha(path), pytest_links=True)
    c.need(
        result["status"] == "matched_software_pass" and result["sources_sha256"] == sources(),
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
        "Campaign disk budget",
    )
    return sum(sizes)


def authenticate(output, expected, *, native=False):
    c.need(c.sha(output / "registration.json") == expected, "Campaign registration digest")
    r = c.read(output / "registration.json", None)
    c.need(
        r["schema"] == "cells.pump_relaxation_matched@1"
        and r["scope"] == SCOPE
        and r["sources_sha256"] == sources()
        and r["prior"] == prerequisite_links()
        and c.sha(PRIOR / "completion.json") == PRIOR_SHA
        and c.sha(PRIOR / "registration.json") == PRIOR_REG,
        "Campaign scope/sources/prior changed",
    )
    c.capsule(output, r["sources_sha256"])
    c.need(software(c.child(ROOT, r["software"]["path"])) == r["software"], "Software binding")
    if not native:
        c.need(r["runtime"] == ctx.runtime(), "Runtime changed")
    return r


def register(output, checked):
    helpers.previous.fresh(output)
    proof, prior = software(checked), prerequisites()
    r = dict(
        schema="cells.pump_relaxation_matched@1",
        scope=SCOPE,
        prior=prior,
        sources_sha256=sources(),
        software=proof,
        runtime=ctx.runtime(),
        registered_utc=datetime.now(UTC).isoformat(),
    )
    output.mkdir(parents=True)
    write(output / "registration.json", r)
    helpers.previous.archive(output, r["sources_sha256"])
    budget(output)


def gate(phase, result):
    if phase == "cells":
        c.need(
            result["status"] == "matched_cells_completed"
            and result["trajectories"] == 24
            and len(result["records"]) == 24
            and result["restart_suffixes"] == 6
            and len(result["resumes"]) == 6
            and result["duration_s"] == 0.01
            and result["checks"]["passed"] is True,
            "Cells acceptance; native not authorized on miss",
        )
    elif phase == "native":
        c.need(
            result["status"] == "matched_native_captured"
            and result["native_runs"] == 20
            and [
                {k: v[k] for k in ("id", "role", "dt_s", "duration_s", "mode")}
                for v in result["records"]
            ]
            == SCOPE["rows"],
            "Native coverage",
        )
    else:
        c.need(
            result["status"] == "matched_comparison_completed"
            and set(result["cases"]) == set(VARIANTS)
            and result["matched_10ms_qualified"] is False
            and result["independent_review_pending"] is True,
            "Comparison coverage/scope",
        )


def stderr_check(phase, text):
    line = "[matched_job.py] Ignoring cutting event, as cut profiles are disabled."
    c.need(text.splitlines() == ([line] * 40 if phase == "native" else []), "Unexpected stderr")


def worker(phase, output, expected):
    r = authenticate(output, expected, native=phase == "native")
    helpers.deadline(SCOPE["phase_timeout_seconds"][phase])
    resource.setrlimit(resource.RLIMIT_AS, (SCOPE["worker_address_space_bytes"],) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (SCOPE["per_file_bytes"],) * 2)
    c.need(sorted(os.sched_getaffinity(0)) == SCOPE["cpu_affinity"], "Worker affinity")
    warnings.simplefilter("error")
    try:
        if phase == "cells":
            # The shared process helper deliberately scrubs JAX environment
            # overrides. Set the registered backend before any JAX import.
            os.environ.update(JAX_ENABLE_X64="true", JAX_PLATFORMS="cpu")
        import matched_work

        result = {
            "cells": matched_work.cells,
            "native": matched_work.capture,
            "comparison": matched_work.compare,
        }[phase](r, output, write, budget)
        c.need(r["sources_sha256"] == sources(), "Worker sources changed")
        result["worker_peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        # Preserve numerical misses before enforcing gates.
        write(output / (phase + ".json"), result)
        gate(phase, result)
    except BaseException:
        write(
            output / (phase + "-failure.json"),
            dict(status="worker_failed", traceback=traceback.format_exc()),
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def execute(output, expected):
    c.need(not (output / "started.json").exists(), "Campaign already attempted")
    start = time.monotonic()
    helpers.deadline(SCOPE["total_timeout_seconds"])
    try:
        write(
            output / "started.json",
            dict(pid=os.getpid(), started_utc=datetime.now(UTC).isoformat()),
        )
        r = authenticate(output, expected)
        c.need(r["prior"] == prerequisites(), "Prerequisite binding")
        elapsed = {}
        for phase, timeout in SCOPE["phase_timeout_seconds"].items():
            began = time.monotonic()
            python = old.old.NATIVE_PYTHON if phase == "native" else ROOT / ".venv/bin/python"
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
        c.need(r["prior"] == prerequisites(), "Prerequisites changed during run")
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
                status="matched_10ms_producer_pass_pending_review"
                if result["producer_passed"]
                else "matched_10ms_numerical_miss_not_qualified",
                producer_passed=result["producer_passed"],
                phase_elapsed_seconds=elapsed,
                elapsed_seconds=time.monotonic() - start,
                finished_utc=datetime.now(UTC).isoformat(),
                files_sha256=files,
                native_runs=20,
                cells_trajectories=24,
                restart_suffixes=6,
                reused_native_observed_rows=3,
                new_reference_solves=0,
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
                status="matched_campaign_failed_not_qualified",
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
                env=environment(),
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
