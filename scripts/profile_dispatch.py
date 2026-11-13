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
              results are ready, and a digest of every window's outputs

--loops masked replaces the field solve's while loops, while tracing, by fixed-count
loops of 16 masked iterations (each loop's bound is at most 16: max_iterations and
max_backtracks), so no loop test depends on data; compare the digests with --loops while
to check bitwise identity. XLA flags (for example the GPU command buffer types) come from
the environment and are recorded.

Inputs: --definitions (parse_spec JSON, one world each) and --snapshot (a batch snapshot
directory whose world-<i>/state.npz and clock start world i; read directly, the snapshot's
source and runtime are not checked). --backend overrides each definition's backend.

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

from cells.core import vector_windows  # noqa: E402
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


def load(args):
    """(specs, checkpoints): one world per definition, started from the snapshot."""
    specs, checkpoints = [], {}
    for i, path in enumerate(args.definitions, start=1):
        raw = json.loads(Path(path).read_text())
        if args.backend:
            raw["execution"]["backend"] = args.backend
        spec = parse_spec(raw)
        specs.append(spec)
        directory = Path(args.snapshot) / f"world-{i}"
        clock = json.loads((directory / "manifest.json").read_text())["clock"]
        model, kind = get_model(spec.model), type(initialise(spec).layout)
        with np.load(directory / "state.npz") as archive:
            state = model.STATE_TYPE(*(archive[k] for k in model.STATE_TYPE._fields))
            layout = kind(*(archive[k] for k in kind._fields))
        checkpoints[i] = Checkpoint(state, layout, **clock)
    return specs, checkpoints


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


def solve_timing(args):
    """One vmapped field solve of every world at its checkpoint state, timed."""
    specs, checkpoints = load(args)
    model = get_model(specs[0].model)
    inputs = []
    for i, spec in enumerate(specs, start=1):
        start = checkpoints[i]
        controls = control_values(spec, [start.time])
        control = type(controls)(*(np.asarray(v[0]) for v in controls))
        inputs.append((start.state, control, start.layout))
    stacked = jax.tree.map(lambda *v: jnp.stack([jnp.asarray(x) for x in v]), *inputs)
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
            "iterations": np.asarray(out.iterations).tolist(),
            "current_normalized_max": np.max(np.asarray(out.current_normalized), axis=-1).tolist(),
            "converged": np.asarray(out.converged).tolist(),
            "newton_target": surface_field.NEWTON_TARGET,
        }
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


def window_timing(args):
    """Vectorized windows from the checkpoints: call and ready seconds per window."""
    specs, checkpoints = load(args)
    batch = BatchSpec(
        tuple(WorldSpec(i, s) for i, s in enumerate(specs, start=1)),
        len(specs),
        2**53 - 1,
        2**53 - 1,
    )
    result = {}
    for variant in ("while", "masked") if args.loops == "both" else (args.loops,):
        calls, digests = [], []
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
                if k + 1 == args.windows:
                    break
        finally:
            vector_windows.compile_window = original
        result[variant] = {"calls": calls, "window_digests": digests}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("part", choices=("iterations", "solve", "window"))
    parser.add_argument("--definitions", nargs="+", required=True)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--backend", help="override each definition's backend (cpu or gpu)")
    parser.add_argument("--steps", type=int, default=20, help="steps (iterations, window)")
    parser.add_argument("--windows", type=int, default=3, help="windows to run (window)")
    parser.add_argument("--repeat", type=int, default=5, help="calls to time (solve)")
    parser.add_argument("--loops", choices=("while", "masked", "both"), default="both")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    started = perf_counter()
    parts = {"iterations": iterations, "solve": solve_timing, "window": window_timing}
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
