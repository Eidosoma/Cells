"""Detached software/smoke preflight only; NEVER launch the full live campaign."""

import argparse
import json
import os
import resource
import shutil
import signal
import subprocess
import time
import traceback
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import live_context as ctx

TIMEOUT = 300
ARTIFACT_BYTES = 256 * 1024**2
TEST_TIMEOUT = 240


def artifacts(output):
    """Record pytest's internal current aliases explicitly, without following them."""
    files, links, size = {}, {}, 0
    for path in sorted(output.rglob("*")):
        name = str(path.relative_to(output))
        if path.is_symlink():
            ctx.need(path.resolve().is_relative_to(output), "Escaping preflight alias")
            links[name] = os.readlink(path)
        elif path.is_file():
            size += path.stat().st_size
            ctx.need(path.stat().st_size <= ctx.BOUNDS["per_file_bytes"], "Preflight file quota")
            if name not in ("launch.json", "runner.stdout.log", "runner.stderr.log"):
                files[name] = ctx.sha(path)
        else:
            ctx.need(path.is_dir(), "Nonregular preflight artifact")
    ctx.need(size < ARTIFACT_BYTES - 1024**2, "Preflight aggregate quota")
    return dict(files_sha256=files, pytest_internal_links=links, artifact_bytes=size)


def authenticate(output, expected_sha):
    ctx.need(
        ctx.sha(output / "registration.json") == expected_sha, "Preflight registration changed"
    )
    r = ctx.read(output / "registration.json")
    ctx.need(
        r["schema"] == "cells.live_recording_software_preflight@1"
        and r["sources_sha256"] == ctx.sources(),
        "Preflight context changed",
    )
    ctx.capsule(output, r["sources_sha256"])
    return r


def run_tests(command, stdout, stderr):
    """Own a fresh process group so a deadline cannot orphan native/JAX smokes."""
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
        code = child.wait(timeout=TEST_TIMEOUT)
        if code:
            raise subprocess.CalledProcessError(code, command)
    except BaseException:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait()
        raise


def register(output, receipt):
    ctx.need(
        output.is_relative_to(ctx.ROOT / "runs")
        and output != ctx.ROOT / "runs"
        and not output.exists(),
        "Fresh preflight directory required",
    )
    ctx.need(
        receipt.is_relative_to(ctx.ROOT / "reports") and not receipt.exists(),
        "Fresh test receipt required",
    )
    prior = ctx.prerequisite()
    r = dict(
        schema="cells.live_recording_software_preflight@1",
        decision="D125",
        prior=prior,
        sources_sha256=ctx.sources(),
        receipt=str(receipt.relative_to(ctx.ROOT)),
        timeout_seconds=TIMEOUT,
        test_timeout_seconds=TEST_TIMEOUT,
        artifact_bytes=ARTIFACT_BYTES,
        per_file_bytes=ctx.BOUNDS["per_file_bytes"],
        cpu_affinity=[0, 1, 2, 3],
        native_smoke_timeout_seconds=35,
        cells_smoke_timeout_seconds=120,
        full_campaign_launched=False,
        automatic_followup=False,
        automatic_retry=False,
        created_utc=datetime.now(UTC).isoformat(),
    )
    output.mkdir(parents=True)
    try:
        ctx.budget(output, reserve=ARTIFACT_BYTES)
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


def execute(output, expected_sha):
    ctx.need(not (output / "started.json").exists(), "Preflight already attempted")
    start = time.monotonic()

    def deadline(_signal, _frame):
        raise TimeoutError("Preflight overall deadline")

    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, TIMEOUT)
    try:
        ctx.write(
            output / "started.json",
            dict(started_utc=datetime.now(UTC).isoformat(), pid=os.getpid()),
        )
        r = authenticate(output, expected_sha)
        ctx.need(sorted(os.sched_getaffinity(0)) == r["cpu_affinity"], "Preflight CPU affinity")
        ctx.need(ctx.prerequisite() == r["prior"], "Preflight prerequisite changed")
        receipt = ctx.ROOT / r["receipt"]
        ctx.need(
            not receipt.exists() and not (output / "tests").exists(),
            "Preflight would overwrite evidence",
        )
        resource.setrlimit(resource.RLIMIT_FSIZE, (ctx.BOUNDS["per_file_bytes"],) * 2)
        with (
            (output / "tests.stdout.log").open("x") as stdout,
            (output / "tests.stderr.log").open("x") as stderr,
        ):
            run_tests(
                [
                    str(ctx.CELLS_PYTHON),
                    "-B",
                    "-m",
                    "pytest",
                    "-q",
                    str(ctx.HERE / "test_live_recording.py"),
                    "--junitxml=" + str(receipt),
                    "--basetemp=" + str(output / "tests"),
                ],
                stdout=stdout,
                stderr=stderr,
            )
        from live_job import receipt as verify_receipt

        software = verify_receipt(receipt)
        authenticate(output, expected_sha)
        ctx.need(ctx.prerequisite() == r["prior"], "Prerequisite changed during preflight")
        ctx.need(
            shutil.disk_usage(output).free >= ctx.BOUNDS["free_disk_reserve_bytes"],
            "Preflight free-disk reserve",
        )
        ctx.write(
            output / "completion.json",
            dict(
                status="live_window_software_preflight_pass",
                software=software,
                **artifacts(output),
                elapsed_seconds=time.monotonic() - start,
                finished_utc=datetime.now(UTC).isoformat(),
                full_campaign_launched=False,
                independent_live_review_complete=False,
                production_changed=False,
                longer_horizon_qualified=False,
                automatic_followup=False,
            ),
        )
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        ctx.write(
            output / "failure.json",
            dict(
                status="software_preflight_failed",
                elapsed_seconds=time.monotonic() - start,
                traceback=traceback.format_exc(),
                full_campaign_launched=False,
                automatic_retry=False,
            ),
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def launch(output, receipt):
    register(output, receipt)
    expected_sha = ctx.sha(output / "registration.json")
    try:
        with (
            (output / "runner.stdout.log").open("x") as stdout,
            (output / "runner.stderr.log").open("x") as stderr,
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
                    expected_sha,
                ],
                cwd=ctx.ROOT,
                env=ctx.environment(),
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
            )
        ack = dict(
            status="launched_detached_preflight_only",
            pid=child.pid,
            registration_sha256=expected_sha,
            launched_utc=datetime.now(UTC).isoformat(),
            automatic_polling=False,
            full_campaign_launched=False,
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
    parser.add_argument("action", choices=("launch", "execute"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--registration-sha")
    args = parser.parse_args()
    if args.action == "launch":
        ctx.need(args.receipt is not None, "Missing --receipt")
        print(json.dumps(launch(args.output.resolve(), args.receipt.resolve()), sort_keys=True))
    else:
        ctx.need(args.registration_sha is not None, "Missing registration binding")
        execute(args.output.resolve(), args.registration_sha)
