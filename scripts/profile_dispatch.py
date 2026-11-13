"""Field-solve loop iterations and window dispatch time on a backend (W1 hold worlds).

The W1 full-tissue hold spends about 10.6 s of each 200-step window of six 825-node
worlds inside the window executable's call on the L4, recorded by no timing
(window-timing-20261112-01). The leading hypothesis: the field solve's data-dependent
lax.while_loops (numerics/surface_field.solve: damped Newton with a backtracking
search) are driven from the host, one device-to-host round trip per loop test. This
harness measures the pieces, on the backend JAX selects (JAX_PLATFORMS, XLA_FLAGS):

  iterations  the field solve's Newton iterations and backtracking trials per step and
              world, on the NumPy host path of the same algorithm (deterministic), with
              the loop tests per batch step they imply for a batched (vmapped) solve
  solve       the model's field values (one field solve) of every world at its
              checkpoint state, vmapped: seconds inside the call against seconds
              until ready, repeated
  window      vectorized windows (cells.core.vector_windows) from the checkpoints: per
              window, seconds inside the executable call against seconds until its
              results are ready, and a digest of every window's outputs; --stop-time runs
              to a time and records a refusal; --save keeps every window's checkpoints
  split       one batch step split: the vmapped checked step, its start-of-step field
              solve and the device row checks, each compiled alone and timed
  edges       field solver version 3's floor multiple at saved states (--states): the
              smallest current_floor at which each state's field solve converges,
              batched and unbatched
  phases      the vectorized run path itself for --windows windows: its live phase
              markers (cells.core.phases, with times) and its timings grouped into
              preparation, execution, observation and output (a step profile to repeat
              on the CPU, the L4 and GH200 with the same arguments)
  compare     saved window runs against a repeated baseline pair (within its spread,
              same refusals and end times), or solve runs against the first (same
              convergence flags and iterations)

--loops masked replaces the field solve's while loops, while tracing, by fixed-count
loops of 16 masked iterations (each loop's bound is at most 16: max_iterations and
max_backtracks), so no loop test depends on data; compare the digests with --loops while
to check bitwise identity. XLA flags (for example the GPU command buffer types) come from
the environment and are recorded.

Inputs: --definitions (parse_spec JSON, one world each, or snapshot manifests holding
"spec") and --snapshot (a batch snapshot directory whose world-<i>/state.npz and clock
start world i, read directly: the snapshot's source and runtime are not checked; or start,
every world from its definition's start). --backend and --field-solver override each
definition's backend and field solver.

  JAX_PLATFORMS=cpu PYTHONPATH=src:. python scripts/profile_dispatch.py iterations \\
      --definitions world-1.json --snapshot snapshots/t00008.000 --steps 20 --out it.json
"""

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from time import perf_counter

os.environ.setdefault("JAX_ENABLE_X64", "1")

import jax  # noqa: E402
import jax.numpy as jnp  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cells.core import phases, vector_windows  # noqa: E402
from cells.core.batch import BatchSpec, WorldSpec  # noqa: E402
from cells.core.grid import EventGrid  # noqa: E402
from cells.core.schedule import control_values  # noqa: E402
from cells.core.specs import parse_spec  # noqa: E402
from cells.core.state import Checkpoint, initialise  # noqa: E402
from cells.core.windows import WindowPolicy  # noqa: E402
from cells.models.registry import get_model  # noqa: E402
from cells.numerics import surface_field, surface_transport  # noqa: E402

MASKED_TRIP = 16  # surface_field.solve's loop bounds: max_iterations 16, max_backtracks 12.


def provenance():
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
        "jax": jax.__version__,
        "devices": [str(d) for d in jax.devices()],
        "jax_platforms": os.environ.get("JAX_PLATFORMS"),
        "xla_flags": os.environ.get("XLA_FLAGS"),
    }


def definitions(args):
    """One specification per definition (a definition or a snapshot manifest's spec)."""
    specs = []
    for path in args.definitions:
        raw = json.loads(Path(path).read_text())
        raw = raw.get("spec", raw)
        if args.backend:
            raw["execution"]["backend"] = args.backend
        if args.field_solver:
            raw["execution"]["field_solver"] = args.field_solver
        specs.append(parse_spec(raw))
    return specs


def load(args):
    """(specs, checkpoints): one world per definition, started from the snapshot.

    --snapshot start: every world from its definition's own start (checkpoints None).
    """
    specs = definitions(args)
    if args.snapshot == "start":
        return specs, None
    return specs, checkpoints_at(specs, args.snapshot)


def checkpoints_at(specs, snapshot):
    """World i's checkpoint from snapshot/world-<i> (state.npz and the manifest's clock)."""
    checkpoints = {}
    for i, spec in enumerate(specs, start=1):
        directory = Path(snapshot) / f"world-{i}"
        clock = json.loads((directory / "manifest.json").read_text())["clock"]
        model, kind = get_model(spec.model), type(initialise(spec).layout)
        with np.load(directory / "state.npz") as archive:
            state = model.STATE_TYPE(*(archive[k] for k in model.STATE_TYPE._fields))
            layout = kind(*(archive[k] for k in kind._fields))
        checkpoints[i] = Checkpoint(state, layout, **clock)
    return checkpoints


@contextmanager
def masked_loops(enabled):
    """While tracing: every lax.while_loop as MASKED_TRIP masked iterations (fori_loop)."""
    if not enabled:
        yield
        return
    original = jax.lax.while_loop

    def while_loop(cond_fun, body_fun, init_val):
        def step(_, carry):
            go = cond_fun(carry)
            new = body_fun(carry)
            return jax.tree.map(lambda n, o: jnp.where(go, n, o), new, carry)

        return jax.lax.fori_loop(0, MASKED_TRIP, step, init_val)

    jax.lax.while_loop = while_loop
    try:
        yield
    finally:
        jax.lax.while_loop = original


def digest(tree):
    h = hashlib.sha256()
    for leaf in jax.tree.leaves(tree):
        a = np.ascontiguousarray(np.asarray(leaf))
        h.update(str((a.dtype, a.shape)).encode())
        h.update(a.tobytes())
    return h.hexdigest()


OPCODES = ("fusion", "custom-call", "while", "conditional", "dot", "triangular-solve", "scatter")


def hlo_counts(compiled):
    """Instructions of the optimized module by opcode: a proxy for kernels per execution
    of each computation (fusions and custom calls are kernels on a GPU)."""
    try:
        text = compiled.as_text()
    except Exception as error:  # Not every backend exposes its optimized module.
        return {"unavailable": repr(error)}
    counts = {name: 0 for name in OPCODES}
    for line in text.splitlines():
        if " = " not in line or line.lstrip().startswith(("ROOT %fused", "%fused")):
            continue
        for name in OPCODES:
            if f" {name}(" in line:
                counts[name] += 1
    return counts


def iterations(args):
    """Newton iterations and backtracking trials per field solve on the host path."""
    specs, checkpoints = load(args)
    solves, inside = [], [False]
    originals = (surface_field.solve, surface_field._offset_solve, surface_transport.transport)

    def solve(*a, **k):
        solves.append({"offset_solves": 0, "evaluations": 0})
        inside[0] = True
        try:
            return originals[0](*a, **k)
        finally:
            inside[0] = False

    def offset_solve(*a, **k):
        if inside[0]:
            solves[-1]["offset_solves"] += 1
        return originals[1](*a, **k)

    def transport(*a, **k):
        if inside[0]:
            solves[-1]["evaluations"] += 1
        return originals[2](*a, **k)

    surface_field.solve, surface_field._offset_solve = solve, offset_solve
    surface_transport.transport = transport
    per_world = {}
    try:
        for i, spec in enumerate(specs, start=1):
            model, start = get_model(spec.model), checkpoints[i]
            p = type(start.layout)(*(np.asarray(v) for v in start.layout))
            state = model.STATE_TYPE(*(np.asarray(v) for v in start.state))
            grid = EventGrid(spec)
            times = next(grid.windows(start.step_index, args.steps))
            table = control_values(spec, times[:-1])
            steps = []
            for k, dt in enumerate(np.diff(times)):
                control = type(table)(*(np.asarray(v[k]) for v in table))
                solves.clear()
                with np.errstate(all="ignore"):
                    state, valid = model.imex_step(state, float(dt), control, p, xp=np)
                steps.append(
                    [
                        {
                            "newton": s["offset_solves"] - 1,
                            "trials": s["evaluations"] - 1 - s["offset_solves"],
                        }
                        for s in solves
                    ]
                    + [{"valid": bool(valid)}]
                )
            per_world[str(i)] = steps
    finally:
        surface_field.solve, surface_field._offset_solve = originals[:2]
        surface_transport.transport = originals[2]
    # Loop tests per batch step for a vmapped solve: the batched loops run while any
    # world continues, so per solve (max Newton + 1) outer tests and, per outer
    # iteration, (max trials of that iteration + 1) inner tests (trials split evenly
    # per iteration here, as only their total is counted on the host path).
    tests = []
    for k in range(args.steps):
        rows = [per_world[w][k][:-1] for w in per_world]
        count = 0
        for j in range(max(len(r) for r in rows)):
            newton = max(r[j]["newton"] for r in rows if j < len(r))
            trials = max(r[j]["trials"] for r in rows if j < len(r))
            count += newton + 1 + trials + newton
        tests.append(count + 1)  # And the scan's own step test.
    return {
        "per_world": per_world,
        "loop_tests_per_batch_step": tests,
        "summary": {
            "field_solves_per_step": sorted({len(s) - 1 for w in per_world.values() for s in w}),
            "newton_per_solve": sorted(
                {d["newton"] for w in per_world.values() for s in w for d in s[:-1]}
            ),
            "trials_per_solve": sorted(
                {d["trials"] for w in per_world.values() for s in w for d in s[:-1]}
            ),
            "loop_tests_per_batch_step_mean": float(np.mean(tests)),
        },
    }


def solve_inputs(specs, checkpoints):
    inputs = []
    for i, spec in enumerate(specs, start=1):
        start = checkpoints[i]
        controls = control_values(spec, [start.time])
        control = type(controls)(*(np.asarray(v[0]) for v in controls))
        inputs.append((start.state, control, start.layout))
    return jax.tree.map(lambda *v: jnp.stack([jnp.asarray(x) for x in v]), *inputs)


def margins(out, count):
    """Per world: Newton iterations, largest normalized current residual and convergence."""
    return {
        "iterations": np.asarray(out.iterations).tolist(),
        "current_normalized_max": np.asarray(out.current_normalized)
        .reshape(count, -1)
        .max(axis=1)
        .tolist(),
        "converged": np.asarray(out.converged).tolist(),
    }


def solve_timing(args):
    """One vmapped field solve of every world at its checkpoint state, timed.

    --snapshots: the same compiled solve at every world's state in each further snapshot
    (for example every complete snapshot of a run), with each world's margin.
    """
    specs, checkpoints = load(args)
    model = get_model(specs[0].model)
    stacked = solve_inputs(specs, checkpoints)
    result = {}
    for variant in ("while", "masked") if args.loops == "both" else (args.loops,):
        with masked_loops(variant == "masked"):
            function = jax.jit(jax.vmap(lambda s, c, p: model.field_values(s, c, p)))
            started = perf_counter()
            compiled = function.lower(*stacked).compile()
            compile_seconds = perf_counter() - started
        calls = []
        for _ in range(args.repeat):
            started = perf_counter()
            out = compiled(*stacked)
            returned = perf_counter()
            jax.block_until_ready(out)
            calls.append({"call": returned - started, "ready": perf_counter() - started})
        result[variant] = {
            "compile_seconds": compile_seconds,
            "hlo_counts": hlo_counts(compiled),
            "calls": calls,
            "digest": digest(out),
            # Per world: the solve's Newton iterations, its largest normalized current
            # residual (convergence needs <= surface_field.NEWTON_TARGET) and convergence.
            **margins(out, len(specs)),
            "newton_target": surface_field.NEWTON_TARGET,
        }
        snapshots = {}
        for path in args.snapshots or ():
            later = checkpoints_at(specs, path)
            out = compiled(*solve_inputs(specs, later))
            snapshots[str(path)] = {"time": later[1].time, **margins(out, len(specs))}
        if snapshots:
            result[variant]["snapshots"] = snapshots
    return result


def timed_compile(original, masked, calls):
    """vector_windows.compile_window, tracing with masked loops if asked, whose executable
    records the seconds inside each call and until its results are ready."""

    def compile_window(model, call_args, rows):
        with masked_loops(masked):
            executable, seconds, memory = original(model, call_args, rows)

        def timed(*a):
            started = perf_counter()
            out = executable(*a)
            returned = perf_counter()
            jax.block_until_ready(out)
            calls.append({"call": returned - started, "ready": perf_counter() - started})
            return out

        calls.append({"compile": seconds, "hlo_counts": hlo_counts(executable)})
        return timed, seconds, memory

    return compile_window


def save_window(directory, k, checkpoints):
    """Every world's checkpoint after window k (state fields, time, step) as one npz."""
    arrays = {}
    for world, c in sorted(checkpoints.items()):
        arrays[f"world-{world}.time"] = np.asarray(c.time)
        arrays[f"world-{world}.step_index"] = np.asarray(c.step_index)
        for name, value in c.state._asdict().items():
            arrays[f"world-{world}.{name}"] = np.asarray(value)
    directory.mkdir(parents=True, exist_ok=True)
    np.savez(directory / f"window-{k}.npz", **arrays)


def window_timing(args):
    """Vectorized windows from the checkpoints: call and ready seconds per window.

    --stop-time: run windows until every world passes this time (instead of --windows);
    a refusal (WorldCheckError) ends the variant and is recorded. --save DIR: each
    window's checkpoints as DIR/<variant>/window-k.npz (for the compare part).
    """
    specs, checkpoints = load(args)
    batch = BatchSpec(
        tuple(WorldSpec(i, s) for i, s in enumerate(specs, start=1)),
        len(specs),
        2**53 - 1,
        2**53 - 1,
    )
    result = {}
    for variant in ("while", "masked") if args.loops == "both" else (args.loops,):
        calls, digests, refusal, ends = [], [], None, []
        original = vector_windows.compile_window
        vector_windows.compile_window = timed_compile(original, variant == "masked", calls)
        # Each variant traces and compiles its own executable: the module's executable
        # cache and JAX's trace caches would otherwise return the first variant's.
        vector_windows._EXECUTABLES.clear()
        jax.clear_caches()
        try:
            policy = WindowPolicy(args.steps, "checkpoints")
            for k, window in enumerate(
                vector_windows.iter_vector_windows(batch, policy, checkpoints)
            ):
                digests.append(
                    digest(
                        [
                            [(c.time, c.step_index, c.event_index, *c.state)]
                            for _, c in sorted(window.checkpoints.items())
                        ]
                    )
                )
                ends.append(min(c.time for c in window.checkpoints.values()))
                if args.save:
                    save_window(Path(args.save) / variant, k, window.checkpoints)
                if args.stop_time is None and k + 1 == args.windows:
                    break
                if args.stop_time is not None and ends[-1] >= args.stop_time - 1e-9:
                    break
        except vector_windows.WorldCheckError as error:
            refusal = {
                "message": str(error),
                "world_id": error.world_id,
                "interval": list(error.time_interval),
                "checks": list(getattr(error, "checks", ())),
            }
        finally:
            vector_windows.compile_window = original
        result[variant] = {
            "calls": calls,
            "window_digests": digests,
            "window_end_times": ends,
            "refusal": refusal,
        }
    return result


def split_timing(args):
    """One batch step split into its field solve and the rest, at the checkpoint states.

    Each piece is compiled alone (jit of the vmapped function) and timed (call and
    ready): the checked step (one IMEX step: one field solve at its start, then the
    stages), the start-of-step field solve (the model's field values), and the device
    row checks a window runs on each accepted row. rest = step - field solve.
    """
    specs, checkpoints = load(args)
    if checkpoints is None:
        raise SystemExit("split needs a --snapshot")
    model = get_model(specs[0].model)
    rows, constants, counts = [], [], []
    for i, spec in enumerate(specs, start=1):
        start = checkpoints[i]
        times = next(EventGrid(spec).windows(start.step_index, 1))
        controls = control_values(spec, times[:-1])
        control = type(controls)(*(np.asarray(v[0]) for v in controls))
        rows.append((start.state, np.asarray(float(times[1] - times[0])), control, start.layout))
        constants.append(model.device_check_constants(spec))
        counts.append(start.step_index + 1)
    s, dt, c, p = jax.tree.map(lambda *v: jnp.stack([jnp.asarray(x) for x in v]), *rows)
    stacked_constants = jax.tree.map(lambda *v: jnp.stack([jnp.asarray(x) for x in v]), *constants)
    steps = jnp.asarray(counts)
    result = {}
    for variant in ("while", "masked") if args.loops == "both" else (args.loops,):
        jax.clear_caches()
        pieces = {}
        with masked_loops(variant == "masked"):
            step = jax.jit(jax.vmap(lambda s, dt, c, p: model.checked_step(s, dt, c, p, p.active)))
            solve = jax.jit(jax.vmap(lambda s, c, p: model.field_values(s, c, p)))
            compiled = {}
            for name, function, arguments in (
                ("step", step, (s, dt, c, p)),
                ("field_solve", solve, (s, c, p)),
            ):
                started = perf_counter()
                compiled[name] = (function.lower(*arguments).compile(), arguments)
                pieces[name] = {
                    "compile_seconds": perf_counter() - started,
                    "hlo_counts": hlo_counts(compiled[name][0]),
                }
            moved, valid = compiled["step"][0](s, dt, c, p)
            check = jax.jit(jax.vmap(lambda a, b, p, k, n: model.device_checks(a, b, p, k, n)))
            arguments = (s, moved, p, stacked_constants, steps)
            started = perf_counter()
            compiled["device_checks"] = (check.lower(*arguments).compile(), arguments)
            pieces["device_checks"] = {
                "compile_seconds": perf_counter() - started,
                "hlo_counts": hlo_counts(compiled["device_checks"][0]),
            }
        for name, (executable, arguments) in compiled.items():
            calls = []
            for _ in range(args.repeat):
                started = perf_counter()
                out = executable(*arguments)
                returned = perf_counter()
                jax.block_until_ready(out)
                calls.append({"call": returned - started, "ready": perf_counter() - started})
            pieces[name]["calls"] = calls
            pieces[name]["ready_median_s"] = float(np.median([x["ready"] for x in calls]))
        pieces["step"]["valid"] = np.asarray(valid).tolist()
        pieces["rest_of_step_median_s"] = (
            pieces["step"]["ready_median_s"] - pieces["field_solve"]["ready_median_s"]
        )
        result[variant] = pieces
    return result


def phase_profile(args):
    """The run path's own phases: markers as they happen and the four phase totals."""
    import logging

    specs, checkpoints = load(args)
    batch = BatchSpec(
        tuple(WorldSpec(i, s) for i, s in enumerate(specs, start=1)),
        len(specs),
        2**53 - 1,
        2**53 - 1,
    )
    markers = []

    class Collect(logging.Handler):
        def emit(self, record):
            markers.append(dict(created=record.created, phase=record.phase, **record.fields))

    handler = Collect()
    phases.LOGGER.addHandler(handler)
    phases.LOGGER.setLevel(logging.DEBUG)
    timings, started = {}, perf_counter()
    try:
        windows = vector_windows.iter_vector_windows(
            batch, WindowPolicy(args.steps, "checkpoints"), checkpoints
        )  # Plans before returning.
        timings["preflight_seconds"] = perf_counter() - started
        for k, window in enumerate(windows):
            for name, value in window.timings.items():
                timings[name] = timings.get(name, 0.0) + value
            if k + 1 == args.windows:
                break
    finally:
        phases.LOGGER.removeHandler(handler)
    wall = perf_counter() - started
    origin = markers[0]["created"] if markers else 0.0
    for marker in markers:
        marker["seconds_since_first"] = marker.pop("created") - origin
    return {
        "markers": markers,
        "timings": timings,
        "phases": phases.phase_totals(timings),
        "wall_seconds": wall,
    }


def edge_floors(args):
    """Version 3's floor multiple at saved states: the smallest current_floor (ulps of eps
    times the incident sum) at which each state's field solve converges, batched (one
    vmap over all states) and unbatched (jit of one state).

    --states: a JSON list of {"definition": index into --definitions, "state": npz path,
    "time": seconds, "label": name}; the npz holds the model's state fields.
    """
    specs = definitions(args)
    entries = json.loads(Path(args.states).read_text())
    floors = [0.0, 1.0, 2.0, 3.0, 5.0, 10.0, 30.0, 100.0, 300.0, 1000.0]
    rows = []
    for entry in entries:
        spec = specs[entry["definition"]]
        model = get_model(spec.model)
        layout = initialise(spec).layout
        if "field_current_floor" not in layout._fields:
            raise SystemExit("edges needs definitions declaring the floor solver (--field-solver)")
        with np.load(entry["state"]) as archive:
            state = model.STATE_TYPE(*(archive[k] for k in model.STATE_TYPE._fields))
        controls = control_values(spec, [entry["time"]])
        control = type(controls)(*(np.asarray(v[0]) for v in controls))
        rows.append((model, state, control, layout))
    model = rows[0][0]

    def solved(s, c, p):
        v = model.field_values(s, c, p)
        return v.converged, jnp.max(v.current_normalized), v.iterations

    single, batched = jax.jit(solved), jax.jit(jax.vmap(solved))
    out = {label["label"]: {"unbatched": {}, "batched": {}} for label in entries}
    for floor in floors:
        layouts = [p._replace(field_current_floor=np.asarray(floor)) for _, _, _, p in rows]
        stacked = jax.tree.map(
            lambda *v: jnp.stack([jnp.asarray(x) for x in v]),
            *[(s, c, p) for (_, s, c, _), p in zip(rows, layouts, strict=True)],
        )
        b = batched(*stacked)
        for k, entry in enumerate(entries):
            a = single(rows[k][1], rows[k][2], layouts[k])
            out[entry["label"]]["unbatched"][str(floor)] = bool(a[0])
            out[entry["label"]]["batched"][str(floor)] = bool(b[0][k])
            out[entry["label"]]["fraction_of_target"] = {
                "unbatched": float(a[1]) / surface_field.NEWTON_TARGET,
                "batched": float(b[1][k]) / surface_field.NEWTON_TARGET,
            }
    for label in out.values():
        for kind in ("unbatched", "batched"):
            accepted = [float(f) for f, ok in label[kind].items() if ok]
            label[f"{kind}_floor_multiple_ulps"] = min(accepted) if accepted else None
    return {"floors": floors, "states": out}


def compare_runs(args):
    """Equivalence of saved window runs (--save) against a repeated baseline pair.

    --runs A B V...: run JSON files of the window part with --save; A and B are the baseline
    pair (the same program twice), each V a variant. Per window and state field: the
    largest |A - B| (the spread) and |A - V|. A variant is equivalent when every
    difference is within the spread (bitwise when the baseline repeats are), its refusals
    and window end times are identical, and it saved at least one window. speedup: the
    baseline's median seconds per window (windows 2 on) over the variant's.
    """
    records = [json.loads(Path(r).read_text()) for r in args.runs]
    if records[0]["part"] == "solve":
        return compare_solves(args.runs, records)

    def windows(record, variant):
        directory = Path(record["arguments"]["save"]) / variant
        return sorted(directory.glob("window-*.npz"), key=lambda q: int(q.stem.split("-")[1]))

    def largest(x, y):
        return {k: float(np.max(np.abs(x[k] - y[k]), initial=0.0)) for k in x.files}

    def window_seconds(record, variant):
        """Median seconds until ready of windows 2 on (window 1 carries first-call costs)."""
        ready = [c["ready"] for c in record[variant]["calls"] if "ready" in c][1:]
        return float(np.median(ready)) if ready else None

    out = {"baseline": [str(r) for r in args.runs[:2]], "variants": {}}
    for variant in ("while", "masked"):
        if variant not in records[0]:
            continue
        a, b = windows(records[0], variant), windows(records[1], variant)
        spread = [largest(np.load(x), np.load(y)) for x, y in zip(a, b, strict=False)]
        out[f"spread_{variant}"] = {
            "bitwise": all(v == 0.0 for w in spread for v in w.values()),
            "largest": max((v for w in spread for v in w.values()), default=0.0),
        }
        for path, record in zip(args.runs[2:], records[2:], strict=True):
            for other in ("while", "masked"):
                if other not in record:
                    continue
                v = windows(record, other)
                differences = [largest(np.load(x), np.load(y)) for x, y in zip(a, v, strict=False)]
                beyond = [
                    (k, key, d, spread[k][key] if k < len(spread) else 0.0)
                    for k, w in enumerate(differences)
                    for key, d in w.items()
                    if d > (spread[k][key] if k < len(spread) else 0.0)
                ]
                same_flags = record[other].get("refusal") == records[0][variant].get(
                    "refusal"
                ) and record[other].get("window_end_times") == records[0][variant].get(
                    "window_end_times"
                )
                out["variants"][f"{path}:{other} vs baseline {variant}"] = {
                    "windows": len(v),
                    "bitwise": all(d == 0.0 for w in differences for d in w.values()),
                    "beyond_spread": beyond[:10],
                    # No saved window (a refusal before the first) is never equivalent.
                    "equivalent": not beyond and same_flags and len(v) == len(a) > 0,
                    "same_refusal_and_end_times": same_flags,
                    "window_seconds": [
                        window_seconds(records[0], variant),
                        window_seconds(record, other),
                    ],
                    # Baseline over variant: above 1 means the variant is faster.
                    "speedup": (
                        window_seconds(records[0], variant) / window_seconds(record, other)
                        if window_seconds(record, other)
                        else None
                    ),
                }
    return out


def compare_solves(paths, records):
    """Solve runs against the first: identical convergence flags and Newton iterations,
    and the largest change of each world's largest normalized residual."""
    base = records[0]
    out = {"baseline": paths[0], "variants": {}}
    for path, record in zip(paths, records, strict=True):
        for variant in ("while", "masked"):
            if variant not in record or "while" not in base:
                continue
            a, b = base["while"], record[variant]
            out["variants"][f"{path}:{variant} vs baseline while"] = {
                "bitwise": a["digest"] == b["digest"],
                "same_converged": a["converged"] == b["converged"],
                "same_iterations": a["iterations"] == b["iterations"],
                "residual_change": float(
                    np.max(
                        np.abs(
                            np.subtract(a["current_normalized_max"], b["current_normalized_max"])
                        )
                    )
                ),
            }
    return out


PARTS = ("iterations", "solve", "window", "split", "phases", "edges", "compare")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("part", choices=PARTS)
    parser.add_argument("--definitions", nargs="+")
    parser.add_argument("--snapshot", help="a batch snapshot directory, or start")
    parser.add_argument("--snapshots", nargs="+", help="further snapshots to solve at (solve)")
    parser.add_argument("--backend", help="override each definition's backend (cpu or gpu)")
    parser.add_argument("--field-solver", help="override each definition's field solver")
    parser.add_argument("--steps", type=int, default=20, help="steps (iterations, window)")
    parser.add_argument("--windows", type=int, default=3, help="windows to run (window)")
    parser.add_argument("--stop-time", type=float, help="run windows to this time (window)")
    parser.add_argument("--save", help="directory for each window's checkpoints (window)")
    parser.add_argument("--states", help="JSON list of saved states (edges)")
    parser.add_argument("--runs", nargs="+", help="window run JSONs: baseline pair first (compare)")
    parser.add_argument("--repeat", type=int, default=5, help="calls to time (solve, split)")
    parser.add_argument("--loops", choices=("while", "masked", "both"), default="both")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.part != "compare" and not args.definitions:
        parser.error("--definitions is required")
    if args.part in ("iterations", "solve", "window", "split", "phases") and not args.snapshot:
        parser.error("--snapshot is required")
    started = perf_counter()
    parts = {
        "iterations": iterations,
        "solve": solve_timing,
        "window": window_timing,
        "split": split_timing,
        "phases": phase_profile,
        "edges": edge_floors,
        "compare": compare_runs,
    }
    result = {
        "kind": "cells.dispatch_profile@1",
        "part": args.part,
        "provenance": provenance(),
        "arguments": vars(args),
        **parts[args.part](args),
    }
    result["seconds"] = perf_counter() - started
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k in ("summary", "seconds")}, indent=1))


if __name__ == "__main__":
    main()
