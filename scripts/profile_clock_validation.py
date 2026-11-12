"""Host-side clock validation cost on the CPU (core.grid.checked_grid); no GPU.

Every window plan (each run, restart and segment start of iter_windows and
iter_vector_windows) checks its definition's whole declared clock with
core.grid.checked_grid: the model's step checks on chunks of at most 1024 steps.
This harness times that validation for one definition on a long declared clock:

  parse_seconds           parse_spec of the definition (not part of validation)
  initial_values_seconds  one model.initial_values(spec), the definition's bound
                          layout, with the surface-field bind inside it
                          (bind_seconds); minima of --repeat calls
  check_steps_seconds     one direct model.check_steps call on the first chunk
  chunk_parts_seconds     per chunk: grid rows, control table (control_values)
                          and model.check_steps, over the first --chunks chunks
  sample                  checked_grid itself, stopped after --chunks and after
                          2 x --chunks chunks (EventGrid.windows ends early); the
                          per-chunk cost is the difference, extrapolated to all
                          chunks of the clock
  full                    the whole checked_grid(spec), with --full

Each timed checked_grid also counts the layout builds it makes
(surface_tissue.initial_values, surface_field.bind), the control tables it builds
(control_values as core.grid calls it) and the model.check_steps calls, by
wrapping those functions for the measurement only.

Definitions: --definition PATH (a parse_spec JSON, such as a saved world
definition), or --small CELLS: independent resolved_pump_tissue@3 heredity cells
(validation/tissue/surface_pump_v3_fixtures.py) on a 4218 s clock at 1 ms with an
observation every 0.48 s (8788 times), the clock of the W1 full-tissue probe.

--cohort PATH...: instead, the whole vectorized preflight of those definitions as
one cohort (one world each): core.vector_windows.plan_vector_windows with 200-step
checkpoint windows from their initial states, as a cost probe's segment start
makes it (parsing, cohort admission and every distinct definition's checked_grid),
with the same counts.

  JAX_PLATFORMS=cpu PYTHONPATH=src:. taskset -c 6 python \\
      scripts/profile_clock_validation.py --definition world-1.json --full --out r.json
"""

import argparse
import json
import os
import platform
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from time import perf_counter

os.environ["JAX_PLATFORMS"] = "cpu"
os.environ.setdefault("JAX_ENABLE_X64", "1")

import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cells.core import grid as grid_module  # noqa: E402
from cells.core.grid import EventGrid, checked_grid  # noqa: E402
from cells.core.schedule import control_values  # noqa: E402
from cells.core.specs import parse_spec  # noqa: E402
from cells.models import surface_tissue  # noqa: E402
from cells.models.registry import get_model  # noqa: E402
from cells.numerics import surface_field  # noqa: E402


def provenance():
    """The checkout's Git revision and dirty paths, or a frozen snapshot's record."""

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True
        ).stdout.strip()

    try:
        source = {
            "git_revision": git("rev-parse", "HEAD"),
            "dirty_paths": git("status", "--porcelain", "--untracked-files=no").splitlines(),
        }
    except (OSError, subprocess.CalledProcessError):  # validation/source_snapshot.py copy
        snapshot = json.loads((ROOT / "SNAPSHOT.json").read_text())
        source = {
            "snapshot": str(ROOT / "SNAPSHOT.json"),
            "git_revision": snapshot["git_revision"],
            "dirty": bool(snapshot["selected_status_porcelain_v1_z"]),
        }
    return source | {
        "python": sys.executable,
        "platform": platform.platform(),
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "jax_platforms": os.environ["JAX_PLATFORMS"],
    }


def small_definition(cells):
    from validation.tissue import surface_pump_v3_fixtures as fixtures

    end, dt = 4218.0, 1e-3
    times = [k * dt for k in range(0, 4_218_000, 480)] + [end]
    h = fixtures.HEREDITY_STATES["H"]
    return fixtures.heredity_cells([h[:4]] * cells, dt=dt, end_time=end, observation_times=times)


@contextmanager
def counted():
    """Count layout builds, control tables and model.check_steps calls (restored after)."""
    counts = {"initial_values": 0, "bind": 0, "control_values": 0, "check_steps": 0}
    patched = [
        (surface_tissue, "initial_values", "initial_values"),
        (surface_field, "bind", "bind"),
        (grid_module, "control_values", "control_values"),
    ]
    originals = [(module, name, getattr(module, name)) for module, name, _ in patched]

    def counting(function, key):
        def wrapper(*args, **kwargs):
            counts[key] += 1
            return function(*args, **kwargs)

        return wrapper

    for (module, name, key), (_, _, function) in zip(patched, originals, strict=True):
        setattr(module, name, counting(function, key))
    try:
        yield counts
    finally:
        for module, name, function in originals:
            setattr(module, name, function)


@contextmanager
def chunk_limit(limit):
    """EventGrid.windows yields at most limit chunks (None: all) and counts them."""
    original, seen = EventGrid.windows, [0]

    def windows(self, start_step, window_steps):
        for row in original(self, start_step, window_steps):
            if limit is not None and seen[0] == limit:
                return
            seen[0] += 1
            yield row

    EventGrid.windows = windows
    try:
        yield seen
    finally:
        EventGrid.windows = original


def timed_checked_grid(spec, limit):
    model = get_model(spec.model)
    original = model.check_steps
    with counted() as counts, chunk_limit(limit) as seen:

        def check_steps(*args, **kwargs):
            counts["check_steps"] += 1
            return original(*args, **kwargs)

        model.check_steps = check_steps
        try:
            start = perf_counter()
            checked_grid(spec)
            seconds = perf_counter() - start
        finally:
            model.check_steps = original
    return {"chunks": seen[0], "seconds": seconds, "calls": dict(counts)}


def minimum_seconds(function, repeat):
    best = float("inf")
    for _ in range(repeat):
        start = perf_counter()
        function()
        best = min(best, perf_counter() - start)
    return best


def chunk_parts(spec, chunks):
    """Mean seconds per chunk of each part of the per-chunk model.check_steps call."""
    model, grid = get_model(spec.model), EventGrid(spec)
    parts = {"grid_rows": 0.0, "control_table": 0.0, "check_steps": 0.0}
    windows = grid.windows(0, 1024)
    for _ in range(chunks):
        start = perf_counter()
        times = next(windows)
        middle = perf_counter()
        table = control_values(spec, times[:-1])
        late = perf_counter()
        model.check_steps(spec, np.diff(times), table)
        end = perf_counter()
        for key, seconds in zip(parts, (middle - start, late - middle, end - late), strict=True):
            parts[key] += seconds / chunks
    return parts


def profile(raw, args):
    result = {}
    start = perf_counter()
    spec = parse_spec(raw)
    result["parse_seconds"] = perf_counter() - start
    model, grid = get_model(spec.model), EventGrid(spec)
    m = spec.model
    result["definition"] = {
        "model": getattr(model, "MODEL_ID", model.__name__),
        "solver": spec.execution.solver,
        "dt": spec.execution.dt,
        "end_time": spec.experiment.end_time,
        "clock_steps": len(grid) - 1,
        "observations": len(spec.experiment.observation_times),
        "cells": len(m.cells),
        "outside_nodes": len(m.extracellular),
        "membranes": len(m.membranes),
        "junctions": len(m.junctions),
        "faces": len(m.faces),
        "channels": len(getattr(m, "channels", ())),
    }
    binds = []
    original = surface_field.bind

    def timed_bind(*a, **k):
        begin = perf_counter()
        try:
            return original(*a, **k)
        finally:
            binds.append(perf_counter() - begin)

    surface_field.bind = timed_bind
    try:
        result["initial_values_seconds"] = minimum_seconds(
            lambda: model.initial_values(spec), args.repeat
        )
    finally:
        surface_field.bind = original
    result["bind_seconds"] = min(binds)
    first = next(grid.windows(0, 1024))
    table = control_values(spec, first[:-1])
    result["check_steps_seconds"] = minimum_seconds(
        lambda: model.check_steps(spec, np.diff(first), table), args.repeat
    )
    result["chunk_parts_seconds"] = chunk_parts(spec, args.chunks)
    small = timed_checked_grid(spec, args.chunks)
    large = timed_checked_grid(spec, 2 * args.chunks)
    per_chunk = (large["seconds"] - small["seconds"]) / (large["chunks"] - small["chunks"])
    total_chunks = -(-(len(grid) - 1) // 1024)
    result["sample"] = {
        "runs": [small, large],
        "per_chunk_seconds": per_chunk,
        "clock_chunks": total_chunks,
        "extrapolated_checked_grid_seconds": small["seconds"]
        + per_chunk * (total_chunks - small["chunks"]),
    }
    if args.full:
        result["full"] = timed_checked_grid(spec, None)
    return result


def profile_cohort(paths):
    """plan_vector_windows of one world per definition (200-step checkpoint windows)."""
    from cells.core.batch import BatchSpec, WorldSpec
    from cells.core.vector_windows import plan_vector_windows
    from cells.core.windows import WindowPolicy

    start = perf_counter()
    worlds = tuple(
        WorldSpec(i, parse_spec(json.loads(Path(p).read_text())))
        for i, p in enumerate(paths, start=1)
    )
    parse_seconds = perf_counter() - start
    batch = BatchSpec(worlds, len(worlds), 2**53 - 1, 2**53 - 1)
    with counted() as counts, chunk_limit(None) as seen:
        start = perf_counter()
        plan = plan_vector_windows(batch, WindowPolicy(200, "checkpoints"))
        seconds = perf_counter() - start
    return {
        "worlds": len(worlds),
        "parse_seconds": parse_seconds,
        "plan_vector_windows_seconds": seconds,
        "checked_chunks": seen[0],
        "calls": dict(counts),
        "window_width": plan.width,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--definition", help="parse_spec JSON definition")
    source.add_argument("--small", type=int, metavar="CELLS", help="heredity cells on 4218 s")
    source.add_argument("--cohort", nargs="+", help="definitions planned as one cohort")
    parser.add_argument("--chunks", type=int, default=4, help="chunks per sample (default 4)")
    parser.add_argument("--repeat", type=int, default=3, help="calls per minimum (default 3)")
    parser.add_argument("--full", action="store_true", help="also time the whole checked_grid")
    parser.add_argument("--out", help="write the JSON result here (default: stdout only)")
    args = parser.parse_args()
    result = {"kind": "cells.clock_validation_profile@1", "provenance": provenance()}
    if args.cohort:
        result |= {"source": args.cohort, **profile_cohort(args.cohort)}
    else:
        raw = (
            json.loads(Path(args.definition).read_text())
            if args.definition
            else small_definition(args.small)
        )
        result |= {
            "source": args.definition or f"small:{args.small}",
            "chunks": args.chunks,
            "repeat": args.repeat,
            **profile(raw, args),
        }
    text = json.dumps(result, indent=1)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
