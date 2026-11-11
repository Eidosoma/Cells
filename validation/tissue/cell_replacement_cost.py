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

    # The same map applied --steps times inside one compiled scan (no dispatch per call).
    def repeated(s, c, q):
        def body(x, _):
            return replacement.event_map(x, jnp.asarray(slots), c, q), None

        return jax.lax.scan(body, s, None, length=args.steps)[0]

    looped = jax.jit(repeated).lower(state, due_control, p).compile()
    jax.block_until_ready(looped(state, due_control, p))
    in_scan = []
    for _ in range(args.repeats):
        started = time.perf_counter()
        jax.block_until_ready(looped(state, due_control, p))
        in_scan.append(1e3 * (time.perf_counter() - started) / args.steps)
    return dict(
        compile_s=compile_s,
        per_call_ms=[1e3 * t for t in times],
        median_ms=1e3 * float(np.median(times)),
        in_scan_per_application_ms=in_scan,
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


def part_parse(args):
    """parse_spec and schedule host costs against the number of events (127-cell sheet).

    Unique templates: one per newcomer (D133 draws), each checked once by a host field
    solve in check_definition. Shared: one template for every event. event_index and
    control_values are timed per call over a 1024-step window, as held_controls uses them.
    """
    from cells.core.schedule import event_index

    raw = fx.heredity_sheet(6, 3, scale=0.3, dt=DT, end_time=3000.0)
    raw["experiment"]["observation_times"] = [0.0, 3000.0]
    cells = len(raw["model"]["cells"])
    out = dict(cells=cells, cases=[])
    for count, unique in ((10, True), (100, True), (300, True), (300, False), (2250, False)):
        steps = [int(round((k + 0.5) * 3000.0 / count / DT)) for k in range(count)]
        times = exact_event_times(steps, DT)
        templates, events = [], []
        for k, t in enumerate(times):
            name = f"t{k}" if unique else "t0"
            if unique or k == 0:
                template = fx.template_from_cell(raw, "cell_0", name)
                template["route_values"]["channel_permeability_m_per_s"] = {
                    "nav1p2_m3h_regularized@1": 2.5e-7 * (1 + 1e-3 * (k % 7))
                }
                templates.append(template)
            events.append((t, f"cell_{(37 * k) % cells}", name, f"n{k}"))
        definition = fx.with_replacement(raw, templates, events)
        started = time.perf_counter()
        spec = parse_spec(definition)
        parse_s = time.perf_counter() - started
        window = np.arange(1024) * DT + times[count // 2] - 512 * DT
        started = time.perf_counter()
        for t in window:
            event_index(spec, float(t))
        index_ms = 1e3 * (time.perf_counter() - started) / len(window)
        started = time.perf_counter()
        control_values(spec, window)
        controls_s = time.perf_counter() - started
        out["cases"].append(
            dict(
                events=count,
                unique_templates=unique,
                parse_s=parse_s,
                event_index_ms_per_call=index_ms,
                control_values_s_per_1024_steps=controls_s,
            )
        )
        print(out["cases"][-1], flush=True)
    return out


def part_swap(args):
    """D->H replacements under IMEX through the row-checked runner (127-cell sheet).

    The written 37-cell disc at s 0.3 (declared D states), default formation (A0 0,
    lag 600 s, tau 1800 s): two rim D cells and one interior D cell get the isolated-H
    template at step 200. core/runner.run applies every host row check; this part
    then reports, per row, each ledger's largest |residual| / bound (electrode first).
    """
    from cells.core.runner import run
    from cells.models import surface_pump as first
    from validation.stationary import worlds

    seconds = args.steps * DT
    raw = fx.heredity_sheet(6, 3, scale=0.3, dt=DT, end_time=seconds)
    raw["experiment"]["observation_times"] = [0.0, seconds]
    cells, _ = worlds.hexagon(6)
    rings = [worlds.ring(c) for c in cells]
    rim = [i for i, r in enumerate(rings) if r == 3][:2]
    inner = [i for i, r in enumerate(rings) if r == 1][:1]
    h = next(i for i, r in enumerate(rings) if r == 6)
    template = fx.template_from_cell(raw, f"cell_{h}", "h")
    (t,) = exact_event_times((200,), DT)
    events = [(t, f"cell_{i}", "h", f"n{i}") for i in (*rim, *inner)]
    spec = parse_spec(fx.with_replacement(raw, [template], events))
    started = time.perf_counter()
    result = run(spec)
    wall = time.perf_counter() - started
    p = replacement.initial_values(spec)[1]
    tol = np.asarray(spec.execution.material_balance_atol_fmol)
    rtol = first.ENERGY_RTOL[spec.execution.solver]
    names = list(first.LEDGERS)
    ratios = []
    for i in range(len(result.times)):
        row = replacement.STATE_TYPE(*(np.asarray(v[i]) for v in result.history))
        b = replacement.balances(row, p)
        _, limits = first.ledger_limits(
            row, p, tol, rtol, steps=i, magnitudes=replacement.magnitudes(row, p, xp=np)
        )
        ratios.append(
            [
                float(np.max(np.abs(np.asarray(v)) / np.broadcast_to(bd, np.shape(v)), initial=0))
                for v, bd in zip(b.values(), limits, strict=True)
            ]
        )
    ratios = np.asarray(ratios)
    k = int(np.flatnonzero(result.times == t)[0])
    v = np.asarray(
        [
            replacement.field_values(
                replacement.STATE_TYPE(*(np.asarray(x[i]) for x in result.history)),
                replacement.Control(
                    *(np.asarray(c[0]) for c in control_values(spec, [result.times[i]]))
                ),
                p,
                xp=np,
            ).rates.membrane_voltage_V
            for i in (k, k + 1, len(result.times) - 1)
        ]
    )
    replaced = [*rim, *inner]
    return dict(
        cells=len(cells),
        steps=args.steps,
        replaced_slots=replaced,
        replaced_rings=[rings[i] for i in replaced],
        event_time_s=t,
        wall_s=wall,
        ledgers=names,
        max_ratio_overall=dict(zip(names, ratios.max(axis=0).tolist(), strict=True)),
        ratio_after_event=dict(zip(names, ratios[k + 1].tolist(), strict=True)),
        ratio_at_end=dict(zip(names, ratios[-1].tolist(), strict=True)),
        electrode_ratio_series=ratios[:, names.index("electrode")][
            :: max(1, args.steps // 50)
        ].tolist(),
        replaced_voltage_mV=dict(
            at_event=(1e3 * v[0][replaced]).tolist(),
            after=(1e3 * v[1][replaced]).tolist(),
            end=(1e3 * v[2][replaced]).tolist(),
        ),
        generation_end=np.asarray(result.history.generation)[-1].tolist(),
    )


PARTS = dict(
    overhead=part_overhead,
    eventmap=part_eventmap,
    sheet=part_sheet,
    parse=part_parse,
    swap=part_swap,
)


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
