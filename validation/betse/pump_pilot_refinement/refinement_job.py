"""One explicitly amended, detached native refinement; no polling or follow-ups."""

import argparse
import hashlib
import importlib
import json
import os
import resource
import shutil
import signal
import subprocess
import time
import traceback
import warnings
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import refinement_context as ctx
from pilot_job import environment

c = ctx.c
PHASES = ("reuse", "betse", "comparison")


def receipt(path):
    c.require(
        path.is_file() and path.is_relative_to(c.ROOT / "reports"), "Missing software receipt"
    )
    suites = ET.parse(path).getroot().findall("testsuite")
    rows = [v for s in suites for v in s.findall("testcase")]
    c.require(len(rows) == sum(int(s.attrib["tests"]) for s in suites) >= 20, "Software coverage")
    c.require(
        all(int(s.get(k, "0")) == 0 for s in suites for k in ("failures", "errors", "skipped"))
        and all(v.find(k) is None for v in rows for k in ("failure", "error", "skipped")),
        "Nonpassing software",
    )
    c.require(all("test_refinement" in v.attrib["classname"] for v in rows), "Wrong software suite")
    return dict(path=str(path.relative_to(c.ROOT)), sha256=c.sha(path), tests=len(rows))


def authenticate(output, *, native=False):
    r = c.read(output / "registration.json")
    ctx.validate(r["amendment"])
    c.require(
        r["schema"] == "cells.refined_pump_pilot_attempt@1" and r["prior"] == ctx.prior(),
        "Prerequisite/schema changed",
    )
    c.require(r["protocol"] == ctx.effective_protocol(r["amendment"]), "Effective criteria changed")
    original = c.read(ctx.PRIOR / "registration.json")
    for name in (
        "cases",
        "native_geometry",
        "native_initial",
        "native_preparation",
        "cells_reference_runtime",
    ):
        c.require(r[name] == original[name], "Preserved preparation changed: " + name)
    c.require(r["reuse_files_sha256"] == ctx.reuse_manifest(), "Reuse manifest changed")
    c.require(r["sources_sha256"] == ctx.sources(), "Frozen refinement source changed")
    c.require(r["software"] == receipt(c.ROOT / r["software"]["path"]), "Software receipt changed")
    c.require(
        c.inspect_source() == r["native_preparation"]["upstream"], "Pinned native source changed"
    )
    if not native:
        c.require(ctx.base.runtime() == r["cells_reference_runtime"], "Comparison runtime changed")
    with zipfile.ZipFile(output / "sources.zip") as archive:
        c.require(
            len(archive.namelist()) == len(r["sources_sha256"])
            and set(archive.namelist()) == set(r["sources_sha256"]),
            "Source capsule membership",
        )
        c.require(
            all(
                hashlib.sha256(archive.read(n)).hexdigest() == h
                for n, h in r["sources_sha256"].items()
            ),
            "Source capsule bytes",
        )
    if (output / "reuse.json").exists():
        c.require(
            all(c.sha(output / n) == h for n, h in r["reuse_files_sha256"].items()),
            "Copied evidence changed",
        )
    return r


def register(output, tests):
    c.require(
        output.is_relative_to(c.ROOT / "runs")
        and output != c.ROOT / "runs"
        and not output.exists(),
        "Fresh refinement directory required",
    )
    amendment = c.read(ctx.PROTOCOL)
    ctx.validate(amendment)
    c.require(
        shutil.disk_usage(c.ROOT / "runs").free
        >= amendment["resources"]["minimum_free_disk_bytes"],
        "Insufficient disk headroom",
    )
    software = receipt(tests)
    prior = ctx.prior()
    original = c.read(ctx.PRIOR / "registration.json")
    r = {
        name: original[name]
        for name in (
            "cases",
            "native_geometry",
            "native_initial",
            "native_preparation",
            "cells_reference_runtime",
        )
    }
    r.update(
        schema="cells.refined_pump_pilot_attempt@1",
        amendment=amendment,
        protocol=ctx.effective_protocol(amendment),
        prior=prior,
        sources_sha256=ctx.sources(),
        reuse_files_sha256=ctx.reuse_manifest(),
        software=software,
        registered_utc=datetime.now(UTC).isoformat(),
    )
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
            dict(status="not_launched", traceback=traceback.format_exc()),
        )
        raise
    return r


def gate(phase, result):
    if phase == "reuse":
        c.require(
            result["status"] == "saved_evidence_reused"
            and result["cells_trajectories"] == 24
            and result["reference_solves"] == 18
            and result["restart_suffixes"] == 6
            and result["new_solver_runs"] == 0,
            "Reuse gate",
        )
    elif phase == "betse":
        c.require(
            result["native_runs"] == 36 and result["observer_pairs"] == 18, "Native coverage gate"
        )
    else:
        c.require(
            phase == "comparison"
            and result["status"] == "refined_pump_pilot_pass_pending_independent_review"
            and result["failed_comparisons"] == 0
            and len(result["exact_overlap_records"]) == 12
            and len(result["refinement"]) == 36
            and all(v["passed"] for v in result["refinement"].values()),
            "Refined numerical comparison failed; retain full report",
        )


def worker(phase, output):
    try:
        r = authenticate(output, native=phase == "betse")
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            if phase == "reuse":
                result = ctx.reuse(output, r["reuse_files_sha256"])
            elif phase == "betse":
                # This is the exact frozen producer used in D117. Only the new
                # registration supplies the finer steps and recording budgets.
                result = importlib.import_module("pilot_native").worker(r, output)
            else:
                c.require(phase == "comparison", "Unknown phase")
                result = importlib.import_module("refinement_check").compare(r, output)
        c.write(output / (phase + ".json"), result)
        gate(phase, result)
    except BaseException:
        c.write(
            output / (phase + "-failure.json"),
            dict(status="worker_failed", phase=phase, traceback=traceback.format_exc()),
        )
        raise


def budget(output, bounds):
    paths = list(output.rglob("*"))
    c.require(not any(p.is_symlink() for p in paths), "Symlink in outputs")
    sizes = [p.stat().st_size for p in paths if p.is_file()]
    c.require(all(v <= bounds["per_file_bytes"] for v in sizes), "Per-file artifact budget")
    used = sum(sizes)
    c.require(used < bounds["artifact_bytes"] - 1024**2, "Aggregate artifact budget")
    return used


def payloads(output):
    return {
        str(p.relative_to(output)): c.sha(p)
        for p in sorted(output.rglob("*"))
        if p.is_file() and p.name not in ("runner.stdout.log", "runner.stderr.log", "launch.json")
    }


def execute(output):
    c.require(not (output / "started.json").exists(), "Refinement already attempted")
    start = time.monotonic()

    def deadline(_sig, _frame):
        raise TimeoutError("Refined pump campaign total deadline")

    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, c.read(ctx.PROTOCOL)["resources"]["total_timeout_seconds"])
    try:
        c.write(
            output / "started.json",
            dict(pid=os.getpid(), started_utc=datetime.now(UTC).isoformat()),
        )
        r = authenticate(output)
        bounds = r["protocol"]["resources"]
        c.require(sorted(os.sched_getaffinity(0)) == bounds["cpu_affinity"], "CPU affinity")
        resource.setrlimit(resource.RLIMIT_FSIZE, (bounds["per_file_bytes"],) * 2)
        for phase in PHASES:
            python = c.REFERENCE_PYTHON if phase == "betse" else c.CELLS_PYTHON
            with (
                (output / (phase + ".stdout.log")).open("x") as stdout,
                (output / (phase + ".stderr.log")).open("x") as stderr,
            ):
                subprocess.run(
                    [
                        str(python),
                        "-B",
                        str(Path(__file__).resolve()),
                        "worker",
                        str(output),
                        "--phase",
                        phase,
                    ],
                    cwd=c.ROOT,
                    env=environment(),
                    stdin=subprocess.DEVNULL,
                    stdout=stdout,
                    stderr=stderr,
                    check=True,
                    timeout=bounds["worker_timeout_seconds"][phase],
                )
            gate(phase, c.read(output / (phase + ".json")))
            authenticate(output)
            budget(output, bounds)
            c.write(
                output / (phase + "-complete.json"),
                dict(status="phase_pass", phase=phase, elapsed_seconds=time.monotonic() - start),
            )
        result = c.read(output / "comparison.json")
        used = budget(output, bounds)
        c.write(
            output / "completion.json",
            dict(
                status=result["status"],
                files_sha256=payloads(output),
                elapsed_seconds=time.monotonic() - start,
                finished_utc=datetime.now(UTC).isoformat(),
                comparisons=result["comparisons"],
                artifact_bytes=used,
                native_runs=36,
                native_observed_steps=6720,
                observer_pairs=18,
                exact_overlap_records=12,
                reused_cells_trajectories=24,
                reused_reference_solves=18,
                reused_restart_suffixes=6,
                new_cells_trajectories=0,
                new_reference_solves=0,
                scientific_tolerances_changed=False,
                production_changed=False,
                biology_validated=False,
                gpu_tested=False,
                automatic_followup=False,
            ),
        )
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        record = dict(
            status="refinement_failed_not_qualified",
            elapsed_seconds=time.monotonic() - start,
            traceback=traceback.format_exc(),
            automatic_retry=False,
        )
        try:
            record["files_sha256"] = payloads(output)
        except BaseException:
            record["payload_manifest_error"] = traceback.format_exc()
        c.write(output / "failure.json", record)
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def launch(output, tests):
    register(output, tests)
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
                    str(c.CELLS_PYTHON),
                    "-B",
                    str(Path(__file__).resolve()),
                    "execute",
                    str(output),
                ],
                cwd=c.ROOT,
                env=environment(),
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
            )
        ack = dict(
            status="launched_detached",
            pid=child.pid,
            launched_utc=datetime.now(UTC).isoformat(),
            registration_sha256=c.sha(output / "registration.json"),
            automatic_polling=False,
        )
        c.write(output / "launch.json", ack)
        return ack
    except BaseException:
        c.write(
            output / "launch-failure.json",
            dict(status="not_launched", traceback=traceback.format_exc()),
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("launch", "execute", "worker"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--phase", choices=PHASES)
    parser.add_argument("--tests", type=Path)
    args = parser.parse_args()
    target = args.output.resolve()
    if args.action == "launch":
        c.require(args.tests is not None, "Missing --tests")
        print(json.dumps(launch(target, args.tests.resolve()), sort_keys=True))
    elif args.action == "execute":
        execute(target)
    else:
        c.require(args.phase is not None, "Missing --phase")
        worker(args.phase, target)
