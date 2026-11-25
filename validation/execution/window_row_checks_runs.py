"""Scalar windowed runs with host and device row checks: wall time, handbacks and outputs.

Development evidence for docs/WINDOW_DEVICE_CHECKS_DESIGN.md §9.6: C5 (the measured speedups)
and C1 on long runs. Each world runs through cells.execution.windows.run_windowed, the production
path, in each requested mode (WindowPolicy row_checks), at the given window size and recording.
Per run it records:
- the wall time, the WindowedResult's timings and resources (in device mode the row-check
  report: the windows the host decided, by reason, and each ledger's largest ratio to its bound);
- digests of the final checkpoint's arrays and of every window's observations (a sink).
Where a world runs in both modes, the digests must be equal: its outputs are bitwise. Each run
is its own process, so no mode reuses another's compiled programs; the definition each world
ran is kept beside its records (OUT/NAME.definition.json).

Worlds: --definition NAME=PATH (a definition file); --baseline DIR --worlds SET/WORLD (a results
baseline's saved definitions, validation/results_baseline.py); --fr4 NAME=END_S (FR-4's
development world at dt 1 ms to END_S, validation/compartment_ph_engine/). --steps NAME=N runs a
world to N steps of its dt instead (observed at its start and end).

Usage (venv-cpu, CPU only, the source on PYTHONPATH):
  python -m validation.execution.window_row_checks_runs OUT [worlds] [--steps NAME=N ...] \\
      [--window-steps 1000] [--recording observations] [--modes host device]
Writes OUT/NAME.MODE.json per run, OUT/NAME.compare.json per world run in both modes, and
OUT/summary.json (with the source's identity).
"""

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import traceback
from dataclasses import replace
from pathlib import Path
from time import perf_counter

import numpy as np


def source():
    """The source's identity: its snapshot record, else its git state."""
    root = Path(__file__).resolve().parents[2]
    snapshot = root / "SNAPSHOT.json"
    if snapshot.exists():
        record = json.loads(snapshot.read_text())
        keys = ("git_revision", "dirty", "status", "patch_sha256")
        return dict(root=str(root), snapshot={k: record.get(k) for k in keys if k in record})
    from validation import executed_sources  # noqa: PLC0415
    executed_sources.refuse_untracked(root, "window_row_checks_runs' source record")  # D259

    run = lambda *a: subprocess.run(  # noqa: E731
        ["git", "-C", str(root), *a], capture_output=True, text=True
    ).stdout.strip()
    return dict(
        root=str(root),
        git_revision=run("rev-parse", "HEAD"),
        dirty=run("status", "--porcelain", "--untracked-files=no"),
    )


def worlds(args):
    from validation import id_table

    out = []
    for key in args.worlds:
        set_name, name = key.split("/", 1)
        path = args.baseline / set_name / (name.replace("/", "__") + ".json")
        out.append((key, id_table.load(path)["definition"]))
    for item in args.definition:
        name, path = item.split("=", 1)
        out.append((name, json.loads(Path(path).read_text())))
    for item in args.fr4:
        from validation.compartment_ph_engine.definitions import development_world, fr4_world
        from validation.compartment_ph_engine.parameters import World

        name, end = item.split("=", 1)
        out.append((name, development_world(fr4_world(replace(World(), end_s=float(end))))))
    steps = dict(item.split("=", 1) for item in args.steps)
    return [(name, horizon(raw, int(steps[name])) if name in steps else raw) for name, raw in out]


def horizon(raw, steps):
    """The definition run to `steps` of its dt, observed at its start and end."""
    raw = json.loads(json.dumps(raw))
    end = steps * raw["execution"]["dt"]
    raw["experiment"]["end_time"] = end
    raw["experiment"]["observation_times"] = [0.0, end]
    raw["execution"]["max_steps"] = max(raw["execution"].get("max_steps", 0), steps + 8)
    return raw


class Digests:
    """A sink: the SHA-256 of every window's observation arrays, in order."""

    def __init__(self):
        self.observations = hashlib.sha256()
        self.windows = 0

    def __call__(self, window):
        self.windows += 1
        for name, value in vars(window.observations).items():
            value = np.ascontiguousarray(value)
            self.observations.update(f"{name}:{value.dtype}:{value.shape}".encode())
            self.observations.update(value.tobytes())


def state_digest(checkpoint):
    digest = hashlib.sha256()
    for value in checkpoint.state:
        value = np.ascontiguousarray(np.asarray(value))
        digest.update(f"{value.dtype}:{value.shape}".encode())
        digest.update(value.tobytes())
    return digest.hexdigest()


def run_one(name, raw, mode, args):
    from cells.definitions.specs import parse_spec
    from cells.execution.windows import WindowPolicy, run_windowed

    record = dict(name=name, mode=mode, window_steps=args.window_steps, recording=args.recording)
    started = perf_counter()
    try:
        spec = parse_spec(json.loads(json.dumps(raw)))
        sink = Digests()
        policy = WindowPolicy(args.window_steps, args.recording, mode)
        result = run_windowed(spec, policy, sink=sink)
        record.update(
            status="completed",
            steps=int(result.final.step_index - result.start_step),
            end_time=float(result.final.time),
            windows=result.resources["windows"],
            timings=result.timings,
            resources=result.resources,
            diagnostics=result.diagnostics,
            final_state_sha256=state_digest(result.final),
            observations_sha256=sink.observations.hexdigest(),
        )
    except Exception as error:  # noqa: BLE001 (a refusal is the record)
        record.update(
            status="refused",
            error_type=type(error).__name__,
            message=str(error),
            traceback=traceback.format_exc()[-4000:],
        )
    record["wall_seconds"] = perf_counter() - started
    return record


def compare(runs):
    host, device = runs.get("host"), runs.get("device")
    if host is None or device is None:
        return None
    keys = ("status", "steps", "final_state_sha256", "observations_sha256", "error_type", "message")
    same = {k: host.get(k) == device.get(k) for k in keys}
    out = dict(bitwise=all(same.values()), fields=same)
    if host.get("status") == device.get("status") == "completed":
        out.update(
            host_seconds=host["wall_seconds"],
            device_seconds=device["wall_seconds"],
            speedup=host["wall_seconds"] / device["wall_seconds"],
        )
    return out


def brief(record):
    if record.get("status") != "completed":
        return {k: record.get(k) for k in ("status", "error_type", "message", "wall_seconds")}
    timings = record["timings"]
    out = dict(
        steps=record["steps"],
        windows=record["windows"],
        wall_seconds=record["wall_seconds"],
        compile_seconds=timings.get("window_compile_or_cache_seconds"),
        execute_seconds=timings.get("window_execute_seconds"),
        analysis_seconds=timings.get("window_analysis_seconds"),
    )
    report = record["resources"].get("row_checks")
    if report is not None:
        handed = sum(report["host_decided"].values())
        out.update(
            device_row_check_seconds=timings.get("window_device_row_check_seconds"),
            host_row_check_seconds=timings.get("window_host_row_check_seconds"),
            host_decided=report["host_decided"],
            handback_rate=handed / report["windows"] if report["windows"] else None,
            max_ratio=max(report["max_ratios"].values(), default=None),
            max_ratios=report["max_ratios"],
        )
    return out


def child(out, name, mode, args):
    """One run in this process: OUT/NAME.definition.json in mode, to OUT/NAME.MODE.json."""
    import jax

    jax.config.update("jax_enable_x64", True)
    stem = name.replace("/", "__")
    raw = json.loads((out / f"{stem}.definition.json").read_text())
    record = run_one(name, raw, mode, args)
    (out / f"{stem}.{mode}.json").write_text(json.dumps(record, indent=1, default=str) + "\n")
    return 0 if record["status"] == "completed" else 3


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--worlds", nargs="*", default=[])
    parser.add_argument("--definition", nargs="*", default=[], help="NAME=PATH")
    parser.add_argument("--fr4", nargs="*", default=[], help="NAME=END_S (dt 1 ms)")
    parser.add_argument("--steps", nargs="*", default=[], help="NAME=N")
    parser.add_argument("--window-steps", type=int, default=1000)
    parser.add_argument("--recording", default="observations")
    parser.add_argument("--modes", nargs="+", default=["host", "device"])
    parser.add_argument("--run", nargs=2, metavar=("NAME", "MODE"), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.run:
        return child(args.out, *args.run, args)
    import jax

    args.out.mkdir(parents=True, exist_ok=True)
    summary = dict(
        kind="cells.window_row_checks_runs@1",
        source=source(),
        environment=dict(
            jax=jax.__version__,
            numpy=np.__version__,
            python=platform.python_version(),
            cpu_affinity=sorted(os.sched_getaffinity(0)),
            nice=os.nice(0),
            JAX_PLATFORMS=os.environ.get("JAX_PLATFORMS"),
            XLA_FLAGS=os.environ.get("XLA_FLAGS"),
        ),
        arguments=dict(window_steps=args.window_steps, recording=args.recording, modes=args.modes),
        worlds={},
    )
    common = ["--window-steps", str(args.window_steps), "--recording", args.recording]
    for name, raw in worlds(args):
        stem = name.replace("/", "__")
        (args.out / f"{stem}.definition.json").write_text(json.dumps(raw, indent=1) + "\n")
        runs = {}
        for mode in args.modes:
            print(f"{name} {mode}: start", flush=True)
            command = [sys.executable, "-B", "-m", __spec__.name, str(args.out), *common]
            subprocess.run([*command, "--run", name, mode], check=False)
            path = args.out / f"{stem}.{mode}.json"
            runs[mode] = (
                json.loads(path.read_text())
                if path.exists()
                else dict(name=name, mode=mode, status="crashed", wall_seconds=None)
            )
            print(
                f"{name} {mode}: {runs[mode]['status']} {runs[mode]['wall_seconds']} s", flush=True
            )
        verdict = compare(runs)
        if verdict is not None:
            (args.out / f"{stem}.compare.json").write_text(json.dumps(verdict, indent=1) + "\n")
        summary["worlds"][name] = dict(
            runs={mode: brief(r) for mode, r in runs.items()}, compare=verdict
        )
        (args.out / "summary.json").write_text(json.dumps(summary, indent=1, default=str) + "\n")
    failed = [
        n for n, w in summary["worlds"].items() if w["compare"] and not w["compare"]["bitwise"]
    ]
    print("not bitwise:", failed or "none", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
