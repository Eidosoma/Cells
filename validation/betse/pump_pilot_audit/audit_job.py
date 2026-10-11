"""One detached, source-bound saved-data audit; no polling or automatic retry."""

import argparse
import json
import os
import resource
import signal
import subprocess
import time
import traceback
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import audit_evidence as context
import pilot_audit

e = context.e
BOUNDS = dict(
    cpu_affinity=[0, 1, 2, 3],
    timeout_seconds=900,
    per_file_bytes=32 * 1024**2,
    artifact_bytes=128 * 1024**2,
)


def receipt(path):
    e.require(path.is_relative_to(e.ROOT / "reports") and path.is_file(), "Missing audit receipt")
    result = e.software(path, 25)
    rows = ET.parse(path).getroot().findall("testsuite/testcase")
    e.require(
        all("test_pilot_audit" in row.attrib["classname"] for row in rows), "Wrong audit suite"
    )
    return result


def fresh(output):
    e.require(
        output.is_relative_to(e.ROOT / "runs")
        and output != e.ROOT / "runs"
        and not output.exists(),
        "Fresh audit directory required",
    )


def register(output, tests):
    fresh(output)
    software = receipt(tests)
    with e.model_fence():
        _, _, files = context.authenticate()
    sources = context.source_manifest()
    r = dict(
        schema="cells.refined_pump_pilot_review@1",
        decision="D120",
        capture=str(context.CAPTURE.relative_to(e.ROOT)),
        capture_registration_sha256=context.REGISTRATION_SHA,
        capture_completion_sha256=context.COMPLETION_SHA,
        capture_files_sha256=files,
        sources_sha256=sources,
        software=software,
        bounds=BOUNDS,
        decimal_digits=70,
        forbidden_imports=list(e.FORBIDDEN),
        registered_utc=datetime.now(UTC).isoformat(),
        original_failure_preserved=True,
        automatic_followup=False,
    )
    output.mkdir(parents=True)
    try:
        e.write(output / "registration.json", r)
        with zipfile.ZipFile(
            output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for name in sources:
                archive.write(e.ROOT / name, arcname=name)
    except BaseException:
        e.write(
            output / "registration-failure.json",
            dict(status="not_launched", traceback=traceback.format_exc()),
        )
        raise
    return r


def authenticate(output):
    r = e.read(output / "registration.json")
    e.require(
        r["schema"] == "cells.refined_pump_pilot_review@1"
        and r["bounds"] == BOUNDS
        and r["capture_registration_sha256"] == context.REGISTRATION_SHA
        and r["capture_completion_sha256"] == context.COMPLETION_SHA,
        "Audit registration changed",
    )
    context.capsule(output, r["sources_sha256"])
    e.require(r["sources_sha256"] == context.source_manifest(), "Audit source membership changed")
    e.require(receipt(e.ROOT / r["software"]["path"]) == r["software"], "Audit receipt changed")
    capture, sources, files = context.authenticate()
    e.require(files == r["capture_files_sha256"], "Capture changed during audit")
    return capture, sources


def budget(output):
    sizes = [p.stat().st_size for p in output.rglob("*") if p.is_file()]
    e.require(
        all(v <= BOUNDS["per_file_bytes"] for v in sizes)
        and sum(sizes) < BOUNDS["artifact_bytes"] - 1024**2,
        "Audit artifact budget",
    )
    return sum(sizes)


def payloads(output):
    return {
        str(p.relative_to(output)): e.sha(p)
        for p in sorted(output.rglob("*"))
        if p.is_file() and p.name not in ("launch.json", "runner.stdout.log", "runner.stderr.log")
    }


def execute(output):
    e.require(not (output / "started.json").exists(), "Audit already attempted")
    started = time.monotonic()

    def deadline(_signal, _frame):
        raise TimeoutError("Independent saved-data review exceeded 900 seconds")

    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, BOUNDS["timeout_seconds"])
    try:
        e.write(
            output / "started.json",
            dict(pid=os.getpid(), started_utc=datetime.now(UTC).isoformat()),
        )
        e.require(sorted(os.sched_getaffinity(0)) == BOUNDS["cpu_affinity"], "Audit CPU affinity")
        resource.setrlimit(resource.RLIMIT_FSIZE, (BOUNDS["per_file_bytes"],) * 2)
        with e.model_fence():
            r, sources = authenticate(output)
            result = pilot_audit.audit(r, sources, output)
            pilot_audit.all_pass(result)
            authenticate(output)
        used = budget(output)
        e.write(
            output / "completion.json",
            dict(
                status="bounded_refined_pump_pilot_independently_closed",
                elapsed_seconds=time.monotonic() - started,
                finished_utc=datetime.now(UTC).isoformat(),
                files_sha256=payloads(output),
                artifact_bytes=used,
                comparisons=result["comparisons"],
                failed_comparisons=0,
                native_law_transfer_conservation_link_comparisons=result[
                    "native_law_transfer_conservation_link_comparisons"
                ],
                native_observed_steps=6720,
                observer_pairs=18,
                exact_overlap_records=12,
                refinements=36,
                decoded_cells_trajectories=24,
                full_state_restart_suffixes=6,
                complete_checkpoint_links=6,
                original_failure_preserved=True,
                bounded_1ms_pilot_qualified=True,
                production_changed=False,
                biology_validated=False,
                gpu_tested=False,
                automatic_followup=False,
            ),
        )
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        record = dict(
            status="independent_review_failed_not_closed",
            elapsed_seconds=time.monotonic() - started,
            traceback=traceback.format_exc(),
            automatic_retry=False,
        )
        try:
            record["files_sha256"] = payloads(output)
        except BaseException:
            record["payload_manifest_error"] = traceback.format_exc()
        e.write(output / "failure.json", record)
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def launch(output, tests):
    register(output, tests)
    environment = {
        k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "JAX", "XLA"))
    }
    environment.update(
        PYTHONNOUSERSITE="1",
        PYTHONDONTWRITEBYTECODE="1",
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
    )
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
                    str(e.ROOT / ".venv/bin/python"),
                    "-B",
                    str(Path(__file__).resolve()),
                    "execute",
                    str(output),
                ],
                cwd=e.ROOT,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
            )
        ack = dict(
            status="launched_detached",
            pid=child.pid,
            launched_utc=datetime.now(UTC).isoformat(),
            registration_sha256=e.sha(output / "registration.json"),
            automatic_polling=False,
        )
        e.write(output / "launch.json", ack)
        return ack
    except BaseException:
        e.write(
            output / "launch-failure.json",
            dict(status="not_launched", traceback=traceback.format_exc()),
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("launch", "execute"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--tests", type=Path)
    args = parser.parse_args()
    if args.action == "launch":
        e.require(args.tests is not None, "Missing software receipt")
        print(json.dumps(launch(args.output.resolve(), args.tests.resolve()), sort_keys=True))
    else:
        execute(args.output.resolve())
