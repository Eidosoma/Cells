"""Bounded 0.1/1 s reference and residual study after the fresh 10 ms closeout."""

import argparse
import copy
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def runtime():
    return {
        "python": sys.version,
        "machine": platform.machine(),
        "packages": {n: importlib.metadata.version(n) for n in ("numpy", "scipy")},
    }


def source_files():
    return {
        str(p.relative_to(ROOT)): sha(p)
        for p in sorted((ROOT / "validation/betse").rglob("*"))
        if p.is_file() and p.suffix in (".py", ".json")
    }


def modules():
    sys.path.insert(0, str(ROOT / "validation/betse/pump_matched_pilot"))
    sys.path.insert(0, str(ROOT / "validation/betse/pump_relaxation_scope"))
    import pilot_reference
    import relax_reference

    return pilot_reference, relax_reference


def row(root, index):
    root = Path(root)
    registration = read(root / "registration.json")
    if runtime() != registration["runtime"] or source_files() != registration["sources_sha256"]:
        raise ValueError("Reference source/runtime differs from frozen registration")
    item = registration["rows"][index]
    directory = root / "rows" / str(index)
    reference, analysis = modules()
    with analysis.model_fence():
        case = dict(
            registration["preparation"]["cases"][item["case"]], end_time_s=item["duration_s"]
        )
        plan = item["plan"]
        record = reference.integrate(case, item["setting"], plan)
        write(directory / "trajectory.json", record)
        # Inspect serialized float64 evidence through the existing independent checker.
        record = read(directory / "trajectory.json")
        result = analysis.summary(case, record, plan, reference.equations)
        import numpy as np

        n = len(case["volume_pL"])
        window = np.asarray(record["states"])[-101:]
        rates = np.asarray([reference.equations.rhs(case, y, (1.0, 1.0)) for y in window])
        inside_rates = (
            rates[:, : 3 * n].reshape((-1, n, 3)) / np.asarray(case["volume_pL"])[None, :, None]
        )
        outside_rates = rates[:, 3 * n : 3 * n + 3] / case["outside_volume_pL"]
        result["last_tenth_window"] = {
            "start_s": record["times_s"][-101],
            "end_s": item["duration_s"],
            "max_abs_inside_concentration_rate_mM_s": np.max(np.abs(inside_rates), axis=0).tolist(),
            "max_abs_outside_concentration_rate_mM_s": np.max(
                np.abs(outside_rates), axis=0
            ).tolist(),
            "inside_amount_drift_fmol": (window[-1, : 3 * n] - window[0, : 3 * n])
            .reshape((n, 3))
            .tolist(),
            "outside_amount_drift_fmol": (
                window[-1, 3 * n : 3 * n + 3] - window[0, 3 * n : 3 * n + 3]
            ).tolist(),
            "voltage_drift_V": (
                np.asarray(record["voltage_V"])[-1] - np.asarray(record["voltage_V"])[-101]
            ).tolist(),
        }
        result.update(
            case=item["case"],
            duration_s=item["duration_s"],
            setting=item["setting"],
            solver_stats=record["stats"],
            trajectory_sha256=sha(directory / "trajectory.json"),
            steady_state_qualified=False,
        )
        write(directory / "result.json", result)
    return result


def controller(root):
    root = Path(root)
    registration = read(root / "registration.json")
    began = time.monotonic()
    write(root / "started.json", {"pid": os.getpid(), "time": time.time()})
    cores = registration["cpu_affinity"]

    def execute(index):
        directory = root / "rows" / str(index)
        directory.mkdir()
        environment = os.environ.copy()
        environment.update(
            OMP_NUM_THREADS="1",
            OPENBLAS_NUM_THREADS="1",
            MKL_NUM_THREADS="1",
            PYTHONDONTWRITEBYTECODE="1",
        )
        try:
            with (
                (directory / "stdout.log").open("x") as out,
                (directory / "stderr.log").open("x") as err,
            ):
                remaining = registration["max_wall_seconds"] - (time.monotonic() - began)
                if remaining <= 0:
                    raise TimeoutError("Reference campaign wall budget exhausted")
                subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        str(Path(__file__).resolve()),
                        "_row",
                        str(root),
                        str(index),
                    ],
                    env=environment,
                    stdout=out,
                    stderr=err,
                    check=True,
                    timeout=min(180, remaining),
                )
            size = sum(p.stat().st_size for p in directory.iterdir() if p.is_file())
            if size > 32 * 1024**2 or shutil.disk_usage(root).free < 4 * 1024**3:
                raise ValueError("Reference row exceeded disk budget/reserve")
            return {
                "index": index,
                "status": "passed",
                "result_sha256": sha(directory / "result.json"),
            }
        except BaseException as exc:
            write(
                directory / "failure.json",
                {"status": "failed", "error": str(exc), "traceback": traceback.format_exc()},
            )
            return {"index": index, "status": "failed"}

    with ThreadPoolExecutor(max_workers=min(4, len(cores))) as pool:
        rows = list(pool.map(execute, range(len(registration["rows"]))))
    references, analysis = modules()
    gates, gate_failures = {}, []
    with analysis.model_fence():
        for duration in registration["horizons_s"]:
            selected = [
                (i, r) for i, r in enumerate(registration["rows"]) if r["duration_s"] == duration
            ]
            if any(rows[i]["status"] != "passed" for i, _ in selected):
                gate_failures.append(str(duration))
                continue
            records = {
                r["case"] + "/" + r["setting"]["id"]: read(
                    root / "rows" / str(i) / "trajectory.json"
                )
                for i, r in selected
            }
            try:
                gates[str(duration)] = references.gate(selected[0][1]["plan"], records)
            except BaseException as exc:
                gates[str(duration)] = {
                    "status": "failed",
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                }
                gate_failures.append(str(duration))
    status = (
        "reference_residual_study_pass" if not gate_failures else "reference_residual_study_failed"
    )
    result = {
        "status": status,
        "rows": rows,
        "reference_gates": gates,
        "elapsed_seconds": time.monotonic() - began,
        "finished_time": time.time(),
        "registration_sha256": sha(root / "registration.json"),
        "steady_state_qualified": False,
        "native_runs": 0,
        "cells_runs": 0,
        "biological_validation": False,
        "automatic_followup": False,
    }
    write(root / "result.json", result)
    write(
        root / ("completion.json" if not gate_failures else "failure.json"),
        {
            "status": status,
            "result_sha256": sha(root / "result.json"),
            "elapsed_seconds": result["elapsed_seconds"],
        },
    )
    return result


def launch(parent, output):
    parent, output = parent.resolve(), output.resolve()
    allowed = Path(os.environ.get("CELLS_OUTPUT_ROOT", "/mnt/workspaces")).resolve()
    if allowed not in output.parents or output.exists():
        raise ValueError("Require a new directory under the configured workspace/scratch root")
    completion = read(parent / "completion.json")
    if completion["status"] != "fresh_10ms_numerical_review_pass" or completion[
        "registration_sha256"
    ] != sha(parent / "registration.json"):
        raise ValueError("Require the completed fresh 10 ms parent")
    prepared = parent / "prepare/preparation.json"
    if read(parent / "prepare/completion.json")["files_sha256"]["preparation.json"] != sha(
        prepared
    ):
        raise ValueError("Parent native preparation changed")
    original = read(parent / "registration.json")["protocol"]
    rows = []
    for duration in (0.1, 1.0):
        plan = copy.deepcopy(original)
        plan["duration_s"] = duration
        plan["reference"].update(
            sample_dt_s=duration / 1000,
            max_rhs_calls_per_solve=200000,
            max_accepted_steps_per_solve=20000,
        )
        for setting in plan["reference"]["solves"]:
            setting["max_step_s"] = duration / (1000 if setting["id"] == "dop853_base" else 2000)
        for case in plan["variants"]:
            for setting in plan["reference"]["solves"]:
                rows.append(
                    {"case": case, "duration_s": duration, "setting": setting, "plan": plan}
                )
    output.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(output.parent).free < 6 * 1024**3:
        raise ValueError("Need 2 GiB artifact allowance plus 4 GiB disk reserve")
    output.mkdir()
    (output / "rows").mkdir()
    source = output / "source"
    for name in ("validation/betse", "src", "configs"):
        shutil.copytree(
            ROOT / name, source / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
        )
    registration = {
        "kind": "pump_relaxation_reference_residuals@1",
        "parent": str(parent),
        "parent_completion_sha256": sha(parent / "completion.json"),
        "parent_preparation_sha256": sha(prepared),
        "preparation": read(prepared),
        "horizons_s": [0.1, 1.0],
        "rows": rows,
        "runtime": runtime(),
        "sources_sha256": source_files(),
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "max_wall_seconds": 1800,
        "per_row_wall_seconds": 180,
        "equations_changed": False,
        "scientific_tolerances_changed": False,
        "changed_numerics": (
            "Explicitly larger maximum adaptive steps, 1001 common samples, and raised work caps"
        ),
        "steady_state_thresholds": None,
        "steady_state_qualified": False,
        "automatic_polling": False,
        "automatic_followup": False,
    }
    write(output / "registration.json", registration)
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(source / "src")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    with (output / "stdout.log").open("x") as out, (output / "stderr.log").open("x") as err:
        process = subprocess.Popen(
            [
                sys.executable,
                "-B",
                str(source / "validation/betse/long_relaxation/run.py"),
                "_controller",
                str(output),
            ],
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=err,
            start_new_session=True,
            close_fds=True,
        )
    result = {
        "status": "launched",
        "pid": process.pid,
        "output": str(output),
        "reference_solves": len(rows),
        "max_wall_seconds": 1800,
        "allocated_cpus": len(registration["cpu_affinity"]),
    }
    write(output / "launch.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("launch")
    start.add_argument("--parent", type=Path, required=True)
    start.add_argument("--output", type=Path, required=True)
    for name in ("status", "_controller", "_row"):
        command = commands.add_parser(name)
        command.add_argument("output", type=Path)
        if name == "_row":
            command.add_argument("index", type=int)
    args = parser.parse_args()
    try:
        if args.command == "launch":
            result = launch(args.parent, args.output)
        elif args.command == "status":
            result = next(
                (
                    read(args.output / n)
                    for n in ("result.json", "failure.json", "started.json", "launch.json")
                    if (args.output / n).exists()
                ),
                {"status": "not_started"},
            )
        elif args.command == "_row":
            result = row(args.output, args.index)
        else:
            result = controller(args.output)
        print(json.dumps(result, allow_nan=False))
    except BaseException as exc:
        if (
            hasattr(args, "output")
            and args.output.exists()
            and args.command == "_controller"
            and not (args.output / "failure.json").exists()
        ):
            write(
                args.output / "failure.json",
                {"status": "failed", "error": str(exc), "traceback": traceback.format_exc()},
            )
        raise


if __name__ == "__main__":
    main()
