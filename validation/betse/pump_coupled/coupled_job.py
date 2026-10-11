"""Source-bound coupled numerical candidate, detached and user-polled."""

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

import coupled_plan as plan

c = plan.c
HERE = Path(__file__).resolve().parent
SOURCES = tuple(
    f"validation/betse/pump_coupled/{name}"
    for name in (
        "coupled_plan.py",
        "coupled_reference.py",
        "coupled_candidate.py",
        "coupled_compare.py",
        "coupled_job.py",
        "test_coupled_pump.py",
    )
) + (
    "validation/betse/contact.py",
    "validation/betse/pump_contact/pump_array.py",
    "validation/betse/pump_contact/pump_reference.py",
    "src/cells/numerics/fixed_step.py",
    "src/cells/processes/electrochemistry.py",
    "docs/KINETIC_PUMP_INTEGRATION.md",
    "reports/REF005A_PUMP_CONTACT_CLOSEOUT.md",
    "reports/NUM011_KINETIC_PUMP_HANDOFF.md",
)


def source_hashes():
    return {name: c.sha(c.ROOT / name) for name in SOURCES}


def software(path):
    path = path.resolve()
    c.require(path.is_relative_to(c.ROOT / "reports"), "Use reports software receipt")
    suites = ET.parse(path).getroot().findall("testsuite")
    count = sum(int(s.attrib["tests"]) for s in suites)
    c.require(
        count >= 20
        and all(
            all(int(s.attrib.get(k, 0)) == 0 for k in ("errors", "failures", "skipped"))
            for s in suites
        ),
        "Coupled software checks not passing",
    )
    identities = [
        row.attrib["classname"] + "::" + row.attrib["name"]
        for s in suites
        for row in s.findall("testcase")
    ]
    c.require(
        len(identities) == count == len(set(identities))
        and all("test_coupled_pump" in n for n in identities),
        "Software coverage",
    )
    return {
        "path": str(path.relative_to(c.ROOT)),
        "sha256": c.sha(path),
        "tests": count,
        "identities": identities,
    }


def authenticate(output):
    r = c.read(output / "registration.json")
    c.require(r["schema"] == "cells.kinetic_pump_coupled_registration@1", "Wrong registration")
    c.require(r["protocol"] == plan.protocol(), "Changed numerical protocol")
    c.require(r["sources_sha256"] == source_hashes(), "Changed candidate source")
    c.require(r["prior_closeout"] == plan.predecessor(), "Changed source-contact gate")
    c.require(r["accepted_runtime"] == c.authenticate_cells()["runtime"], "Production changed")
    c.require(r["preservation_sha256"] == c.sha(c.PRESERVATION), "Preservation changed")
    c.require(r["software"] == software(c.ROOT / r["software"]["path"]), "Software changed")
    with zipfile.ZipFile(output / "sources.zip") as archive:
        c.require(
            set(archive.namelist()) == set(SOURCES) and len(archive.namelist()) == len(SOURCES),
            "Capsule members",
        )
        c.require(
            all(
                hashlib.sha256(archive.read(n)).hexdigest() == h
                for n, h in r["sources_sha256"].items()
            ),
            "Capsule bytes changed",
        )
    return r


def worker(output, engine):
    r = authenticate(output)
    p = r["protocol"]
    c.require(not (output / f"{engine}.json").exists(), "Worker result already exists")
    expected = (
        c.locked_reference_packages()
        if engine == "reference"
        else r["candidate_environment"]["packages"]
    )
    c.require(c.environment()["packages"] == expected, "Worker package environment changed")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        if engine == "reference":
            import coupled_reference as reference

            results = {
                case["id"]: {
                    method: reference.integrate(case, p, method)
                    for method in p["reference_methods"]
                }
                for case in p["cases"]
            }
        else:
            import coupled_candidate as candidate
            import numpy as np

            results = {}
            for case in p["cases"]:
                trajectories, finest, exact = {}, {}, True
                for dt in p["rk4_steps_s"]:
                    inputs = plan.controls(case, dt)
                    stride = round(p["sample_dt_s"] / dt)
                    for name, rollout in (
                        ("numpy", candidate.numpy_rollout),
                        ("jax_jit", candidate.jax_rollout),
                    ):
                        states = rollout(case, dt, inputs)
                        key = f"{name}/{dt}"
                        trajectories[key] = {
                            "times_s": [k * dt for k in range(0, len(states), stride)],
                            "state": states[::stride].tolist(),
                            "step_s": dt,
                            "full_state": states.tolist(),
                        }
                        if dt == p["rk4_steps_s"][-1]:
                            split = round(0.006 / dt)
                            checkpoint = json.loads(
                                json.dumps(states[split].tolist(), allow_nan=False)
                            )
                            restarted = rollout(case, dt, inputs[split:], initial=checkpoint)
                            exact &= bool(np.array_equal(restarted, states[split:]))
                            finest[name] = {
                                "time_s": split * dt,
                                "complete_state": checkpoint,
                                "suffix_state": restarted.tolist(),
                                "exact": bool(np.array_equal(restarted, states[split:])),
                            }
                results[case["id"]] = {
                    "trajectories": trajectories,
                    "restart_exact": exact,
                    "checkpoints": finest,
                }
    c.write(
        output / f"{engine}.json",
        {
            "registration_sha256": c.sha(output / "registration.json"),
            "engine": engine,
            "results": results,
            "warnings": [str(w.message) for w in caught],
            "environment": c.environment(),
        },
    )
    c.require(not caught, "Worker warnings retained; not qualified")


def environment(output):
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "JAX_PLATFORMS": "cpu",
            "JAX_ENABLE_X64": "true",
            "JAX_DISABLE_JIT": "false",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(output / "mpl"),
        }
    )
    return env


def deadline(_signal, _frame):
    raise TimeoutError("Coupled pump candidate deadline")


def execute(output):
    c.require(not (output / "started.json").exists(), "Execution already attempted")
    started = time.monotonic()
    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, plan.protocol()["total_timeout_seconds"])
    try:
        c.write(
            output / "started.json",
            {"started_utc": datetime.now(UTC).isoformat(), "pid": os.getpid()},
        )
        r = authenticate(output)
        p = r["protocol"]
        c.require(sorted(os.sched_getaffinity(0)) == p["cpu_affinity"], "Wrong CPUs")
        resource.setrlimit(resource.RLIMIT_FSIZE, (p["per_file_bytes"],) * 2)
        for engine, python in (("reference", c.REFERENCE_PYTHON), ("candidate", c.CELLS_PYTHON)):
            with (
                (output / f"{engine}.stdout.log").open("x") as out,
                (output / f"{engine}.stderr.log").open("x") as err,
            ):
                subprocess.run(
                    [
                        str(python),
                        "-B",
                        str(Path(__file__).resolve()),
                        "worker",
                        str(output),
                        "--engine",
                        engine,
                    ],
                    cwd=c.ROOT,
                    env=environment(output),
                    stdin=subprocess.DEVNULL,
                    stdout=out,
                    stderr=err,
                    check=True,
                    timeout=p["worker_timeout_seconds"],
                )
        reference, candidate = (
            c.read(output / f"{name}.json") for name in ("reference", "candidate")
        )
        c.require(
            all(
                x["registration_sha256"] == c.sha(output / "registration.json")
                and not x["warnings"]
                for x in (reference, candidate)
            ),
            "Worker provenance mismatch",
        )
        from coupled_compare import compare

        result = compare(p, reference["results"], candidate["results"])
        c.write(output / "comparison.json", result)
        c.require(result["status"] == "pass", "Coupled candidate rejected; comparisons retained")
        authenticate(output)
        used = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
        c.require(used < p["artifact_bytes"] - 1024**2, "Artifact budget exceeded")
        c.write(
            output / "completion.json",
            {
                "status": "coupled_candidate_pass_pending_audit",
                "finished_utc": datetime.now(UTC).isoformat(),
                "elapsed_seconds": time.monotonic() - started,
                "cases": len(p["cases"]),
                "reference_trajectories": 12,
                "candidate_trajectories": 24,
                "candidate_restarts": 12,
                "state_comparisons": result["state_comparisons"],
                "artifact_bytes_before_receipt": used,
                "files_sha256": {
                    n: c.sha(output / n)
                    for n in (
                        "registration.json",
                        "sources.zip",
                        "started.json",
                        "reference.json",
                        "candidate.json",
                        "comparison.json",
                    )
                },
                "production_changed": False,
                "production_pump_implemented": False,
                "independent_capture_audit_complete": False,
                "native_betse_trajectory_qualified": False,
                "biology_validated": False,
                "gpu_tested": False,
                "automatic_retry": False,
                "automatic_followup": False,
            },
        )
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        c.write(
            output / "failure.json",
            {
                "status": "failed_not_qualified",
                "elapsed_seconds": time.monotonic() - started,
                "traceback": traceback.format_exc(),
                "automatic_retry": False,
            },
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def register(output, tests):
    c.require(
        output.is_relative_to(c.ROOT / "runs")
        and output != c.ROOT / "runs"
        and not output.exists(),
        "Use fresh output",
    )
    r = {
        "schema": "cells.kinetic_pump_coupled_registration@1",
        "protocol": plan.protocol(),
        "sources_sha256": source_hashes(),
        "prior_closeout": plan.predecessor(),
        "accepted_runtime": c.authenticate_cells()["runtime"],
        "preservation_sha256": c.sha(c.PRESERVATION),
        "software": software(tests),
        "candidate_environment": c.environment(),
        "registered_utc": datetime.now(UTC).isoformat(),
    }
    output.mkdir(parents=True)
    try:
        c.write(output / "registration.json", r)
        with zipfile.ZipFile(
            output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for name in SOURCES:
                archive.write(c.ROOT / name, arcname=name)
        authenticate(output)
    except BaseException:
        c.write(
            output / "registration-failure.json",
            {"status": "not_launched", "traceback": traceback.format_exc()},
        )
        raise
    return r


def launch(output, tests):
    r = register(output, tests)
    try:
        with (
            (output / "runner.stdout.log").open("x") as out,
            (output / "runner.stderr.log").open("x") as err,
        ):
            child = subprocess.Popen(
                [
                    "taskset",
                    "-c",
                    ",".join(map(str, r["protocol"]["cpu_affinity"])),
                    str(c.CELLS_PYTHON),
                    "-B",
                    str(Path(__file__).resolve()),
                    "execute",
                    str(output),
                ],
                cwd=c.ROOT,
                env=environment(output),
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                start_new_session=True,
            )
        receipt = {
            "status": "launched_detached",
            "pid": child.pid,
            "launched_utc": datetime.now(UTC).isoformat(),
            "registration_sha256": c.sha(output / "registration.json"),
            "automatic_polling": False,
            "automatic_retry": False,
            "automatic_followup": False,
        }
        c.write(output / "launch.json", receipt)
        return receipt
    except BaseException:
        c.write(
            output / "launch-failure.json",
            {"status": "launch_failed", "traceback": traceback.format_exc()},
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("launch", "execute", "worker"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--tests", type=Path)
    parser.add_argument("--engine", choices=("reference", "candidate"))
    args = parser.parse_args()
    output = args.output.resolve()
    if args.action == "launch":
        c.require(args.tests is not None, "Need test receipt")
        print(json.dumps(launch(output, args.tests), sort_keys=True))
    elif args.action == "execute":
        execute(output)
    else:
        c.require(args.engine is not None, "Need engine")
        worker(output, args.engine)
