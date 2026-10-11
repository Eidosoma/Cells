"""D127: preserve the failed D126 run, authenticate native reuse, run only Cells detached."""

import argparse
import json
import os
import resource
import signal
import subprocess
import time
import traceback
import warnings
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import resume_context as res
from resume_context import ctx, original

REQUIRED_TESTS = {
    "test_actual_script_logging_prefix",
    "test_saved_notices_reject_old_classifier",
    "test_saved_packet_native_hash_links",
    "test_changed_chunk_refused",
    "test_detached_launch_binds_registration",
    "test_controller_runs_only_cells",
    "test_failure_is_terminal",
    "test_worker_group_timeout_cleanup",
    "test_continuation_authentication_refuses_changes",
}


def receipt(path):
    ctx.need(path.is_relative_to(ctx.ROOT / "reports"), "Receipt location")
    suites = ET.parse(path).getroot().findall("testsuite")
    cases = [case for suite in suites for case in suite.findall("testcase")]
    ctx.need(
        len(cases) == sum(int(s.get("tests", "0")) for s in suites) >= 30
        and all(int(s.get(k, "0")) == 0 for s in suites for k in ("failures", "errors", "skipped"))
        and all(c.find(k) is None for c in cases for k in ("failure", "error", "skipped"))
        and all("test_live_resume" in c.get("classname", "") for c in cases)
        and REQUIRED_TESTS <= {c.get("name", "").split("[")[0] for c in cases},
        "Incomplete/nonpassing continuation software",
    )
    return dict(path=str(path.relative_to(ctx.ROOT)), sha256=ctx.sha(path), tests=len(cases))


def run_child(command, stdout, stderr, timeout):
    """Own/reap the entire worker group on failure, timeout or controller interruption."""
    child = subprocess.Popen(
        command,
        cwd=ctx.ROOT,
        env=ctx.environment(),
        stdin=subprocess.DEVNULL,
        stdout=stdout,
        stderr=stderr,
        start_new_session=True,
    )
    try:
        code = child.wait(timeout=timeout)
        if code:
            raise subprocess.CalledProcessError(code, command)
    except BaseException:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait()
        raise


def fresh(output):
    ctx.need(
        output.is_relative_to(ctx.ROOT / "runs")
        and output != ctx.ROOT / "runs"
        and not output.exists(),
        "Fresh continuation directory required",
    )
    ctx.path_for(ctx.ROOT, str(output.relative_to(ctx.ROOT)))


def check(output, tests):
    """Short software-only regression, with before/after source binding; no campaign."""
    from preflight_job import artifacts

    fresh(output)
    ctx.need(tests.is_relative_to(ctx.ROOT / "reports") and not tests.exists(), "Fresh receipt")
    ctx.path_for(ctx.ROOT, str(tests.relative_to(ctx.ROOT)))
    before = res.sources()
    output.mkdir(parents=True)
    start = time.monotonic()
    ctx.write(output / "registration.json", dict(sources_sha256=before, test_timeout_seconds=60))
    try:
        with (
            (output / "tests.stdout.log").open("x") as out,
            (output / "tests.stderr.log").open("x") as err,
        ):
            run_child(
                [
                    str(ctx.CELLS_PYTHON),
                    "-B",
                    "-m",
                    "pytest",
                    "-q",
                    "-W",
                    "error",
                    str(res.HERE / "test_live_resume.py"),
                    "--junitxml=" + str(tests),
                    "--basetemp=" + str(output / "tests"),
                ],
                out,
                err,
                60,
            )
        software = receipt(tests)
        ctx.need(res.sources() == before, "Sources changed during software checks")
        ctx.need((output / "tests.stderr.log").read_bytes() == b"", "Software stderr")
        result = dict(
            status="continuation_software_pass",
            software=software,
            sources_sha256=before,
            **artifacts(output),
            elapsed_seconds=time.monotonic() - start,
            full_campaign_launched=False,
            automatic_followup=False,
        )
        ctx.write(output / "completion.json", result)
        return {k: result[k] for k in ("status", "software", "elapsed_seconds")}
    except BaseException:
        ctx.write(
            output / "failure.json",
            dict(status="software_failed", traceback=traceback.format_exc()),
        )
        raise


def software(evidence):
    from preflight_job import artifacts

    path = ctx.path_for(ctx.ROOT, evidence)
    ctx.need(
        path.is_relative_to(ctx.ROOT / "runs") and path.name == "completion.json", "Software packet"
    )
    done = ctx.read(path)
    ctx.need(
        done["status"] == "continuation_software_pass"
        and done["sources_sha256"] == res.sources()
        and done["full_campaign_launched"] is False
        and done["automatic_followup"] is False
        and not (path.parent / "failure.json").exists(),
        "Changed/failed software context",
    )
    actual = artifacts(path.parent)
    ctx.need(
        actual["files_sha256"] == done["files_sha256"] | {"completion.json": ctx.sha(path)}
        and actual["pytest_internal_links"] == done["pytest_internal_links"],
        "Software artifacts changed",
    )
    ctx.need(
        receipt(ctx.ROOT / done["software"]["path"]) == done["software"], "Software XML changed"
    )
    return dict(path=evidence, sha256=ctx.sha(path), xml=done["software"])


def register(output, checked):
    fresh(output)
    prior = ctx.prerequisite()
    reused = res.failed_packet()
    old = ctx.read(res.FAILED / "registration.json")
    ctx.need(old["prior"] == prior, "Original prerequisite changed")
    r = dict(
        schema="cells.live_recording_continuation@1",
        decision="D127",
        duration_s=0.001,
        bounds=ctx.BOUNDS,
        prior=prior,
        software=software(checked),
        sources_sha256=res.sources(),
        reused_native=reused,
        native_labels=old["native_labels"],
        cells_keys=old["cells_keys"],
        phases=["cells"],
        new_native_runs=0,
        production_changed=False,
        scientific_tolerances_changed=False,
        automatic_retry=False,
        automatic_followup=False,
        registered_utc=datetime.now(UTC).isoformat(),
    )
    output.mkdir(parents=True)
    try:
        ctx.budget(output, reserve=64 * 1024**2)
        ctx.write(output / "registration.json", r)
        with zipfile.ZipFile(
            output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for name in r["sources_sha256"]:
                archive.write(ctx.ROOT / name, arcname=name)
        authenticate(output, ctx.sha(output / "registration.json"))
    except BaseException:
        ctx.write(
            output / "registration-failure.json",
            dict(status="not_launched", traceback=traceback.format_exc()),
        )
        raise
    return r


def authenticate(output, expected_sha):
    ctx.need(
        ctx.sha(output / "registration.json") == expected_sha, "Launch-bound registration changed"
    )
    r = ctx.read(output / "registration.json")
    ctx.need(
        r["schema"] == "cells.live_recording_continuation@1"
        and r["decision"] == "D127"
        and r["duration_s"] == 0.001
        and r["bounds"] == ctx.BOUNDS
        and r["phases"] == ["cells"]
        and r["new_native_runs"] == 0
        and all(
            r[k] is False
            for k in (
                "production_changed",
                "scientific_tolerances_changed",
                "automatic_retry",
                "automatic_followup",
            )
        ),
        "Continuation scope changed",
    )
    ctx.need(r["sources_sha256"] == res.sources(), "Frozen continuation sources changed")
    ctx.capsule(output, r["sources_sha256"])
    ctx.need(software(r["software"]["path"]) == r["software"], "Software evidence changed")
    ctx.need(res.failed_packet() == r["reused_native"], "Native reuse evidence changed")
    old = ctx.read(res.FAILED / "registration.json")
    ctx.need(
        all(r[k] == old[k] for k in ("prior", "native_labels", "cells_keys")),
        "Original scope changed",
    )
    return r


def worker(output, expected_sha):
    try:
        r = authenticate(output, expected_sha)
        resource.setrlimit(resource.RLIMIT_AS, (ctx.BOUNDS["cells_address_space_bytes"],) * 2)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            from matched_windows import worker as work

            result = work(output, r)
        ctx.write(output / "cells.json", result)
        original.gate("cells", result, r)
        authenticate(output, expected_sha)
    except BaseException:
        ctx.write(
            output / "cells-failure.json",
            dict(status="worker_failed", traceback=traceback.format_exc()),
        )
        raise


def execute(output, expected_sha):
    ctx.need(not (output / "started.json").exists(), "Continuation already attempted")
    start = time.monotonic()

    def deadline(_signal, _frame):
        raise TimeoutError("Continuation overall deadline")

    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, ctx.BOUNDS["timeout_seconds"])
    try:
        ctx.write(
            output / "started.json",
            dict(pid=os.getpid(), started_utc=datetime.now(UTC).isoformat()),
        )
        r = authenticate(output, expected_sha)
        ctx.need(ctx.prerequisite() == r["prior"], "Prerequisite changed before continuation")
        ctx.need(sorted(os.sched_getaffinity(0)) == ctx.BOUNDS["cpu_affinity"], "CPU affinity")
        resource.setrlimit(resource.RLIMIT_FSIZE, (ctx.BOUNDS["per_file_bytes"],) * 2)
        ctx.write(
            output / "native-reuse.json",
            dict(
                status="saved_native_phase_authenticated_pending_independent_review",
                **r["reused_native"],
            ),
        )
        with (
            (output / "cells.stdout.log").open("x") as out,
            (output / "cells.stderr.log").open("x") as err,
        ):
            run_child(
                [
                    str(ctx.CELLS_PYTHON),
                    "-B",
                    str(Path(__file__).resolve()),
                    "worker",
                    str(output),
                    "--registration-sha",
                    expected_sha,
                ],
                out,
                err,
                ctx.BOUNDS["cells_timeout_seconds"],
            )
        result = ctx.read(output / "cells.json")
        original.gate("cells", result, r)
        ctx.need((output / "cells.stderr.log").read_bytes() == b"", "Unexpected Cells stderr")
        authenticate(output, expected_sha)
        ctx.need(ctx.prerequisite() == r["prior"], "Prerequisite changed during continuation")
        used = ctx.budget(output)
        ctx.write(
            output / "completion.json",
            dict(
                status="live_recording_and_matched_windows_pass_pending_independent_review",
                files_sha256=original.payloads(output),
                elapsed_seconds=time.monotonic() - start,
                finished_utc=datetime.now(UTC).isoformat(),
                artifact_bytes_before_completion=used,
                native_runs_reused=36,
                new_native_runs=0,
                observer_pairs=18,
                observed_updates=6720,
                history_samples=13404,
                known_disabled_cut_notices=72,
                cells_full_trajectories=24,
                cells_window_runs=72,
                cells_disk_recordings=18,
                cells_restart_suffixes=6,
                cells_restart_window_runs=6,
                zero_length_runs=6,
                sparse_schedule_controls=2,
                original_attempt_stays_failed=True,
                native_memory_bounded=False,
                independent_live_review_complete=False,
                longer_horizon_qualified=False,
                production_changed=False,
                scientific_tolerances_changed=False,
                biology_validated=False,
                gpu_tested=False,
                automatic_followup=False,
            ),
        )
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        ctx.write(
            output / "failure.json",
            dict(
                status="live_window_continuation_failed",
                elapsed_seconds=time.monotonic() - start,
                traceback=traceback.format_exc(),
                automatic_retry=False,
            ),
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def launch(output, checked):
    register(output, checked)
    digest = ctx.sha(output / "registration.json")
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
                    str(ctx.CELLS_PYTHON),
                    "-B",
                    str(Path(__file__).resolve()),
                    "execute",
                    str(output),
                    "--registration-sha",
                    digest,
                ],
                cwd=ctx.ROOT,
                env=ctx.environment(),
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                start_new_session=True,
            )
        ack = dict(
            status="launched_detached",
            pid=child.pid,
            registration_sha256=digest,
            launched_utc=datetime.now(UTC).isoformat(),
            automatic_polling=False,
            new_native_runs=0,
        )
        ctx.write(output / "launch.json", ack)
        return ack
    except BaseException:
        ctx.write(
            output / "launch-failure.json",
            dict(status="not_launched", traceback=traceback.format_exc()),
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "launch", "execute", "worker"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--tests", type=Path)
    parser.add_argument("--checked")
    parser.add_argument("--registration-sha")
    args = parser.parse_args()
    if args.action == "check":
        ctx.need(args.tests is not None, "Missing software receipt")
        print(json.dumps(check(args.output.absolute(), args.tests.absolute()), sort_keys=True))
    elif args.action == "launch":
        ctx.need(args.checked is not None, "Missing source-bound software evidence")
        print(json.dumps(launch(args.output.absolute(), args.checked), sort_keys=True))
    else:
        ctx.need(args.registration_sha is not None, "Missing launch binding")
        (execute if args.action == "execute" else worker)(
            args.output.absolute(), args.registration_sha
        )
