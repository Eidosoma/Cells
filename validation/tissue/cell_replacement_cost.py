"""Cost of resolved_pump_replacement@1 against resolved_pump_tissue@3 (development, not judged).

Engine models: resolved_pump_tissue@3 and resolved_pump_replacement@1 (inner @3),
IMEX ARS(2,2,2) at dt 1 ms, compiled checked steps in lax.scan with held controls
(execute time only; compile reported separately). Parts (one JSON each in --output):

  overhead  the 825-node scale world (validation/tissue/surface_pump_v3_study.
            tissue_definition): @3's step against the wrapper's with no events
            (formation updates, occupant view, schedule predicate; the event map
            skipped by lax.cond), single world; and vmapped over --worlds replicas,
            where lax.cond becomes a select, so the event map runs every step.
  eventmap  the event map alone on the 825-node world, one slot due, compiled, with
            device-resident inputs (the first, superseded run converted host arrays
            on every call).
  sheet     a 217-cell heredity sheet (held baths, written disc), @3 against the
            wrapper with one replacement per 0.2 s (literature formation rule),
            through the windowed runner (host checks included), one world.

Usage: python -m validation.tissue.cell_replacement_cost PART --output DIR
       [--steps N] [--worlds B] [--repeats R]
"""

import argparse
import json
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

jax.config.update("jax_enable_x64", True)

from cells.core.cell_replacement_spec import exact_event_times  # noqa: E402
from cells.core.schedule import control_values  # noqa: E402
from cells.core.specs import parse_spec  # noqa: E402
from cells.models import cell_replacement as replacement  # noqa: E402
from cells.models.registry import get_model  # noqa: E402
from validation.tissue import cell_replacement_fixtures as fx  # noqa: E402
from validation.tissue import surface_pump_v3_study as study  # noqa: E402

DT = 1e-3


def scale_world(steps):
    raw = study.tissue_definition(dt=DT, end_time=steps * DT, observation_times=[0.0, steps * DT])
    return raw


def rollout(model, spec, steps, worlds=None):
    """(compile s, execute s per step) of a scan of checked steps at the t=0 controls."""
    state, p = model.initial_values(spec)
    control = type(control_values(spec, [0.0]))(
        *(np.asarray(v[0]) for v in control_values(spec, [0.0]))
    )
    dt = jnp.asarray(DT)

    def scan(state, control, p):
        def advance(s, _):
            s, ok = model.checked_step(s, dt, control, p, p.active)
            return s, ok

        return jax.lax.scan(advance, state, None, length=steps)

    if worlds:
        stack = lambda tree: jax.tree.map(lambda v: jnp.stack([jnp.asarray(v)] * worlds), tree)  # noqa: E731
        state, control, p = stack(state), stack(control), stack(p)
        function = jax.jit(jax.vmap(scan))
    else:
        function = jax.jit(scan)
    started = time.perf_counter()
    compiled = function.lower(state, control, p).compile()
    compile_s = time.perf_counter() - started
    final, ok = compiled(state, control, p)  # warm
    jax.block_until_ready(final)
    started = time.perf_counter()
    final, ok = compiled(state, control, p)
    jax.block_until_ready(final)
    execute = time.perf_counter() - started
    return dict(
        compile_s=compile_s,
        execute_s=execute,
        per_step_ms=1e3 * execute / steps,
        all_valid=bool(np.all(np.asarray(ok))),
        worlds=worlds or 1,
    )


def part_overhead(args):
    raw = scale_world(args.steps)
    base = parse_spec(raw)
    wrapped = parse_spec(fx.with_replacement(raw))
    out = dict(nodes=len(base.model.cells) + len(base.model.extracellular), steps=args.steps)
    for label, spec in (("resolved_pump_tissue@3", base), ("resolved_pump_replacement@1", wrapped)):
        model = get_model(spec.model)
        out[label] = dict(
            single=[rollout(model, spec, args.steps) for _ in range(args.repeats)],
            vmap=rollout(model, spec, args.steps, worlds=args.worlds) if args.worlds else None,
        )
    return out


def part_eventmap(args):
    raw = scale_world(args.steps)
    spec = parse_spec(fx.with_replacement(raw))
    state, p = replacement.initial_values(spec)
    controls = replacement.control_values(spec, [0.0])
    control = replacement.Control(*(np.asarray(v[0]) for v in controls))
    # One slot due: its template is a copy of cell 1's declared state (a valid template row).
    m = spec.model
    p = p._replace(
        template_amount_fmol=np.asarray(m.cells[1].initial_amount_fmol)[None, :],
    )
    due_control = control._replace(
        generation=np.where(np.arange(control.generation.size) == 0, 1, 0),
        template=np.where(np.arange(control.generation.size) == 0, 1, 0),
    )
    slots = np.asarray(p.active) & (np.asarray(due_control.generation) == 1)
    function = jax.jit(lambda s, c, q: replacement.event_map(s, jnp.asarray(slots), c, q))
    # Device-resident inputs, as inside a compiled window (no per-call host conversion).
    state, due_control, p = jax.device_put((state, due_control, p))
    started = time.perf_counter()
    compiled = function.lower(state, due_control, p).compile()
    compile_s = time.perf_counter() - started
    jax.block_until_ready(compiled(state, due_control, p))
    times = []
    for _ in range(args.repeats * 20):
        started = time.perf_counter()
        jax.block_until_ready(compiled(state, due_control, p))
        times.append(time.perf_counter() - started)
    return dict(
        compile_s=compile_s,
        per_call_ms=[1e3 * t for t in times],
        median_ms=1e3 * float(np.median(times)),
    )


def part_sheet(args):
    from cells.core.windows import WindowPolicy, run_windowed

    seconds = args.steps * DT
    raw = fx.heredity_sheet(8, 2, scale=0.3, dt=DT, end_time=seconds)
    raw["experiment"]["observation_times"] = [0.0, seconds]
    template = fx.template_from_cell(raw, "cell_0", "h")
    ring = [i for i, c in enumerate(raw["model"]["cells"])]
    steps = range(200, args.steps, 200)
    times = exact_event_times(steps, DT)
    events = [(t, f"cell_{ring[(7 * k) % len(ring)]}", "h", f"n{k}") for k, t in enumerate(times)]
    out = dict(cells=len(raw["model"]["cells"]), steps=args.steps, events=len(events))
    for label, definition in (
        ("resolved_pump_tissue@3", raw),
        ("resolved_pump_replacement@1", fx.with_replacement(raw, [template], events)),
    ):
        spec = parse_spec(definition)
        started = time.perf_counter()
        result = run_windowed(spec, WindowPolicy(1000, "checkpoints"))
        out[label] = dict(
            wall_s=time.perf_counter() - started,
            timings=result.timings if hasattr(result, "timings") else None,
        )
    return out


PARTS = dict(overhead=part_overhead, eventmap=part_eventmap, sheet=part_sheet)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("part", choices=sorted(PARTS))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--worlds", type=int, default=0)
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    result = PARTS[args.part](args)
    result.update(
        part=args.part,
        argv=sys.argv,
        wall_s=time.perf_counter() - started,
        peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        host=platform.node(),
        jax=jax.__version__,
        devices=[str(d) for d in jax.devices()],
        revision=subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
        ).stdout.strip(),
        dirty=subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout,
    )
    path = args.output / f"{args.part}.json"
    with open(path, "x") as f:
        json.dump(result, f, indent=1, default=float)
    print(
        json.dumps(
            {k: v for k, v in result.items() if k not in ("argv",)}, indent=1, default=float
        )[:4000]
    )


if __name__ == "__main__":
    main()
