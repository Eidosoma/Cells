"""Launch one bounded native preparation, detached, without polling or auto-follow-up."""

import argparse
import hashlib
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

import pump_context as ctx

c = ctx.c


def receipt(path):
    c.require(
        path.is_file() and path.is_relative_to(c.ROOT / "reports"), "Missing preflight checks"
    )
    suites = ET.parse(path).getroot().findall("testsuite")
    rows = [row for s in suites for row in s.findall("testcase")]
    c.require(len(rows) == sum(int(s.attrib["tests"]) for s in suites) >= 15, "Software coverage")
    c.require(
        all(int(s.get(k, "0")) == 0 for s in suites for k in ("failures", "errors", "skipped"))
        and all(row.find(k) is None for row in rows for k in ("failure", "error", "skipped")),
        "Software checks failed",
    )
    c.require(
        all("test_pump_loop_preflight" in row.attrib["classname"] for row in rows),
        "Wrong check suite",
    )
    return dict(path=str(path.relative_to(c.ROOT)), sha256=c.sha(path), tests=len(rows))


def authenticate(output):
    r = c.read(output / "registration.json")
    ctx.validate_protocol(r["protocol"])
    c.require(r["schema"] == "cells.betse_pump_loop_attempt@1", "Registration schema")
    c.require(
        r["sources_sha256"] == ctx.sources() and r["prerequisites"] == ctx.prerequisites(),
        "Source/prior changed",
    )
    c.require(r["upstream"] == c.inspect_source(), "Upstream source changed")
    c.require(r["software"] == receipt(c.ROOT / r["software"]["path"]), "Software receipt changed")
    with zipfile.ZipFile(output / "sources.zip") as archive:
        c.require(
            len(archive.namelist()) == len(r["sources_sha256"])
            and set(archive.namelist()) == r["sources_sha256"].keys(),
            "Capsule membership",
        )
        c.require(
            all(
                hashlib.sha256(archive.read(n)).hexdigest() == h
                for n, h in r["sources_sha256"].items()
            ),
            "Capsule bytes",
        )
    return r


def register(output, tests):
    c.require(
        output.is_relative_to(c.ROOT / "runs")
        and output != c.ROOT / "runs"
        and not output.exists(),
        "Fresh output required",
    )
    plan = c.read(ctx.PROTOCOL)
    ctx.validate_protocol(plan)
    r = dict(
        schema="cells.betse_pump_loop_attempt@1",
        protocol=plan,
        prerequisites=ctx.prerequisites(),
        sources_sha256=ctx.sources(),
        upstream=c.inspect_source(),
        software=receipt(tests),
        registered_utc=datetime.now(UTC).isoformat(),
        expected_geometry={k: c.read(ctx.GEOMETRY)[k] for k in ctx.GEOMETRY_FIELDS},
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


def environment():
    env = os.environ.copy()
    for name in ("PYTHONPATH", "PYTEST_ADDOPTS", "PYTEST_PLUGINS"):
        env.pop(name, None)
    env.update(
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONNOUSERSITE="1",
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        MPLBACKEND="Agg",
    )
    return env


def deadline(_sig, _frame):
    raise TimeoutError("Native pump preflight total deadline")


def execute(output):
    c.require(not (output / "started.json").exists(), "Attempt already executed")
    start = time.monotonic()
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
        with (
            (output / "native.stdout.log").open("x") as out,
            (output / "native.stderr.log").open("x") as err,
        ):
            subprocess.run(
                [
                    str(c.REFERENCE_PYTHON),
                    "-B",
                    str(Path(__file__).resolve()),
                    "worker",
                    str(output),
                ],
                cwd=c.ROOT,
                env=environment(),
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                check=True,
                timeout=bounds["worker_timeout_seconds"],
            )
        from pump_check import compare

        result = compare(r, c.read(output / "betse.json"))
        c.require(
            result["observed_steps"] == 48 and result["observer_pairs"] == 6, "Comparison coverage"
        )
        c.write(output / "checks.json", result)
        authenticate(output)
        files = {
            str(p.relative_to(output)): c.sha(p)
            for p in output.rglob("*")
            if p.is_file()
            and p.name not in ("runner.stdout.log", "runner.stderr.log", "launch.json")
        }
        c.require(not any(p.is_symlink() for p in output.rglob("*")), "Symlink in capture")
        used = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
        c.require(used < bounds["artifact_bytes"] - 1024**2, "Artifact quota")
        c.write(
            output / "completion.json",
            dict(
                status=result["status"],
                files_sha256=files,
                elapsed_seconds=time.monotonic() - start,
                finished_utc=datetime.now(UTC).isoformat(),
                native_runs=12,
                observed_steps=48,
                observer_pairs=6,
                artifact_bytes=used,
                production_changed=False,
                coupled_cells_betse_qualified=False,
                biology_validated=False,
                automatic_followup=False,
            ),
        )
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        c.write(
            output / "failure.json",
            dict(
                status="failed_not_qualified",
                elapsed_seconds=time.monotonic() - start,
                traceback=traceback.format_exc(),
                automatic_retry=False,
            ),
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def worker(output):
    try:
        r = authenticate(output)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            from pump_native import worker as native_worker

            c.write(output / "betse.json", native_worker(r, output))
    except BaseException:
        c.write(
            output / "native-failure.json",
            dict(status="native_failed", traceback=traceback.format_exc()),
        )
        raise


def launch(output, tests):
    register(output, tests)
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
        launched = dict(
            status="launched_detached",
            pid=child.pid,
            launched_utc=datetime.now(UTC).isoformat(),
            registration_sha256=c.sha(output / "registration.json"),
            automatic_polling=False,
        )
        c.write(output / "launch.json", launched)
        return launched
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
    parser.add_argument("--tests", type=Path)
    args = parser.parse_args()
    target = args.output.resolve()
    if args.action == "launch":
        c.require(args.tests is not None, "Missing --tests")
        print(json.dumps(launch(target, args.tests.resolve()), sort_keys=True))
    elif args.action == "execute":
        execute(target)
    else:
        worker(target)
