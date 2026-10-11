"""One registered gated pilot, detached. No automatic audit, retry or polling."""

import argparse
import hashlib
import importlib
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

import pilot_context as ctx

c = ctx.c
PHASES = ("mapping", "reference", "betse", "cells")


def receipt(path):
    c.require(
        path.is_file() and path.is_relative_to(c.ROOT / "reports"), "Missing software receipt"
    )
    suites = ET.parse(path).getroot().findall("testsuite")
    rows = [row for s in suites for row in s.findall("testcase")]
    c.require(len(rows) == sum(int(s.attrib["tests"]) for s in suites) >= 20, "Software coverage")
    c.require(
        all(int(s.get(k, "0")) == 0 for s in suites for k in ("failures", "errors", "skipped"))
        and all(row.find(k) is None for row in rows for k in ("failure", "error", "skipped")),
        "Nonpassing software",
    )
    c.require(
        all("test_matched_pump" in row.attrib["classname"] for row in rows), "Wrong software suite"
    )
    return dict(path=str(path.relative_to(c.ROOT)), sha256=c.sha(path), tests=len(rows))


def validate_protocol(p):
    c.require(
        p == c.read(ctx.PROTOCOL) and p["prior_completion_sha256"] == ctx.AUDIT_SHA,
        "Unregistered pilot",
    )
    c.require(
        p["duration_s"] == 0.001 and len(p["variants"]) == 6 and len(set(p["variants"])) == 6,
        "Pilot extent",
    )
    c.require(
        p["native_runs"] == 2 * len(p["variants"]) * len(p["native_steps_s"]) == 36,
        "Native coverage",
    )
    c.require(
        p["cells_trajectories"] == len(p["variants"]) * (len(p["cells_steps_s"]) + 1) == 24,
        "Cells coverage",
    )
    c.require(
        p["reference_solves"] == len(p["variants"]) * len(p["reference"]["solves"]) == 18,
        "Reference coverage",
    )
    for step in p["native_steps_s"] + p["cells_steps_s"]:
        for t in p["common_times_s"]:
            c.require(
                abs(t / step - round(t / step)) < 1e-10, "Common time not on native/Cells mesh"
            )
    c.require(
        all(
            p[k] is False
            for k in (
                "production_changed",
                "biological_parameters_fitted",
                "automatic_polling",
                "automatic_retry",
                "automatic_followup",
            )
        ),
        "Expanded/automatic scope",
    )


def authenticate(output, *, native=False):
    r = c.read(output / "registration.json")
    validate_protocol(r["protocol"])
    c.require(
        r["schema"] == "cells.matched_pump_pilot_attempt@1" and r["prior"] == ctx.prior(),
        "Prior/schema changed",
    )
    c.require(r["sources_sha256"] == ctx.sources(), "Pilot source changed")
    c.require(
        r["native_preparation"] == c.read(ctx.CAPTURE / "registration.json"),
        "Native prerequisite changed",
    )
    c.require(r["cases"] == ctx.cases(), "Measured initial mapping changed")
    c.require(r["software"] == receipt(c.ROOT / r["software"]["path"]), "Software receipt changed")
    c.require(c.inspect_source() == r["native_preparation"]["upstream"], "Native checkout changed")
    if not native:
        c.require(ctx.runtime() == r["cells_reference_runtime"], "Cells/reference runtime changed")
    with zipfile.ZipFile(output / "sources.zip") as archive:
        c.require(
            len(archive.namelist()) == len(r["sources_sha256"])
            and set(archive.namelist()) == r["sources_sha256"].keys(),
            "Source capsule membership",
        )
        c.require(
            all(
                hashlib.sha256(archive.read(n)).hexdigest() == h
                for n, h in r["sources_sha256"].items()
            ),
            "Source capsule bytes",
        )
    return r


def register(output, tests):
    c.require(
        output.is_relative_to(c.ROOT / "runs")
        and output != c.ROOT / "runs"
        and not output.exists(),
        "Fresh pilot directory required",
    )
    p = c.read(ctx.PROTOCOL)
    validate_protocol(p)
    previous = c.read(ctx.CAPTURE / "registration.json")
    rows = ctx.native_rows()
    r = dict(
        schema="cells.matched_pump_pilot_attempt@1",
        protocol=p,
        prior=ctx.prior(),
        native_preparation=previous,
        cases=ctx.cases(),
        native_geometry=rows["pump_leak/observed"]["geometry"],
        native_initial={
            v: rows[v + "/observed"]["trace"]["initial"]["physical"] for v in p["variants"]
        },
        sources_sha256=ctx.sources(),
        software=receipt(tests),
        cells_reference_runtime=ctx.runtime(),
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


def environment():
    env = os.environ.copy()
    for name in ("PYTHONPATH", "PYTEST_ADDOPTS", "PYTEST_PLUGINS"):
        env.pop(name, None)
    env.update(
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONNOUSERSITE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        JAX_PLATFORMS="cpu",
        JAX_ENABLE_X64="true",
        JAX_DISABLE_JIT="false",
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        MPLBACKEND="Agg",
    )
    return env


def phase_gate(phase, result):
    if phase == "mapping":
        c.require(
            result["status"] == "held_state_mapping_pass"
            and result["held_states"] == 48
            and result["backend_evaluations"] == 144,
            "Mapping gate",
        )
    elif phase == "reference":
        c.require(
            result["gate"]["status"] == "independent_reference_gate_pass"
            and result["reference_solves"] == 18,
            "Independent reference gate",
        )
    elif phase == "betse":
        c.require(
            result["native_runs"] == 36 and result["observer_pairs"] == 18, "Native coverage gate"
        )
    else:
        c.require(
            phase == "cells" and result["trajectories"] == 24 and result["restart_suffixes"] == 6,
            "Cells coverage gate",
        )


def worker(phase, output):
    try:
        r = authenticate(output, native=phase == "betse")
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            module = importlib.import_module(
                "pilot_native" if phase == "betse" else "pilot_" + phase
            )
            result = module.worker(r, output)
            c.write(output / (phase + ".json"), result)
            phase_gate(phase, result)
    except BaseException:
        c.write(
            output / (phase + "-failure.json"),
            dict(status="worker_failed", phase=phase, traceback=traceback.format_exc()),
        )
        raise


def deadline(_sig, _frame):
    raise TimeoutError("Matched pump pilot total deadline")


def execute(output):
    c.require(not (output / "started.json").exists(), "Pilot already attempted")
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
        for phase in PHASES:
            python = c.REFERENCE_PYTHON if phase == "betse" else c.CELLS_PYTHON
            with (
                (output / (phase + ".stdout.log")).open("x") as out,
                (output / (phase + ".stderr.log")).open("x") as err,
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
                    stdout=out,
                    stderr=err,
                    check=True,
                    timeout=bounds["worker_timeout_seconds"][phase],
                )
            phase_gate(phase, c.read(output / (phase + ".json")))
            authenticate(output)
            used = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
            c.require(used < bounds["artifact_bytes"] - 1024**2, "Pilot artifact budget")
            c.write(
                output / (phase + "-complete.json"),
                dict(status="phase_pass", phase=phase, elapsed_seconds=time.monotonic() - start),
            )
        from pilot_compare import compare

        result = compare(r, output)
        c.write(output / "comparison.json", result)
        authenticate(output)
        c.require(not any(p.is_symlink() for p in output.rglob("*")), "Symlink in pilot artifacts")
        files = {
            str(p.relative_to(output)): c.sha(p)
            for p in output.rglob("*")
            if p.is_file()
            and p.name not in ("runner.stdout.log", "runner.stderr.log", "launch.json")
        }
        used = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
        c.require(used < bounds["artifact_bytes"] - 1024**2, "Final artifact budget")
        c.write(
            output / "completion.json",
            dict(
                status=result["status"],
                files_sha256=files,
                elapsed_seconds=time.monotonic() - start,
                finished_utc=datetime.now(UTC).isoformat(),
                comparisons=result["comparisons"],
                native_runs=36,
                cells_trajectories=24,
                reference_solves=18,
                restart_suffixes=6,
                observer_pairs=18,
                artifact_bytes=used,
                production_changed=False,
                biology_validated=False,
                gpu_tested=False,
                automatic_followup=False,
            ),
        )
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        c.write(
            output / "failure.json",
            dict(
                status="pilot_failed_not_qualified",
                elapsed_seconds=time.monotonic() - start,
                traceback=traceback.format_exc(),
                automatic_retry=False,
            ),
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


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
        receipt = dict(
            status="launched_detached",
            pid=child.pid,
            launched_utc=datetime.now(UTC).isoformat(),
            registration_sha256=c.sha(output / "registration.json"),
            automatic_polling=False,
        )
        c.write(output / "launch.json", receipt)
        return receipt
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
