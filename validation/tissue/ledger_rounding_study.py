"""Rounding in the resolved pump ledgers and the reaction_transport@1 guards (evidence runs).

Parts (each writes <part>[-<label>].json in --output; failures are kept as results):
  trajectory  run a definition JSON (--definition, optionally --end) through the
              runner and save every accepted state field (npz) with the diagnostics,
              for a before/after comparison of two source trees.
  compare     compare two trajectory directories (--base, --fix): every state field
              bitwise except the electrode ledgers, whose differences are reported.
  electrode   2-cell held-bath @3 world (no channels): each step's electrode
              increment is taken exactly (ledger zeroed) and the ledger residual is
              split into accumulation rounding and per-step increment error.
  relax       relaxing @3 held-bath cells (pre-screen U composition, Vm +-2 mV per
              cell) at 1 ms for --minutes in runner windows; every accepted row passes
              check_values; per-window ledger ratios.
  fine        the heredity write cell at 15.625 us over 1 s (64,000 steps) through
              the runner (the reference refused before the electrode fix).
  reaction    MG0a's a/4 strip (256 cells, 1e6 pL reservoir) to 40/k in runner
              windows: the reaction_transport@1 guards over 3.2e5 RK4 steps.
Usage:
  python -m validation.tissue.ledger_rounding_study PART --output DIR [options]
"""

import argparse
import copy
import json
import math
import resource
import time
import traceback
from pathlib import Path

import jax
import numpy as np

jax.config.update("jax_enable_x64", True)


def _run_windows(raw, *, window_s, record=None):
    """Runner windows (branch checkpoints) of one definition; diagnostics per window."""
    from cells.core.runner import branch_checkpoint, run
    from cells.core.specs import parse_spec

    end, dt = raw["experiment"]["end_time"], raw["execution"]["dt"]
    steps = max(1, round(window_s / dt))
    ends, k = [], steps
    while k * dt < end - 0.5 * dt:
        ends.append(k * dt)
        k += steps
    ends.append(end)
    previous, checkpoint, windows = None, None, []
    for stop in ends:
        window = copy.deepcopy(raw)
        ex = window["experiment"]
        ex["end_time"] = stop
        ex["observation_times"] = [stop]
        for key in ("membrane_controls", "junction_controls", "pump_controls"):
            for group in ex.get(key, []):
                group["schedule"] = [c for c in group["schedule"] if c["time"] <= stop]
        for group in ex.get("channel_controls", []):
            group["schedule"] = [c for c in group["schedule"] if c["time"] <= stop]
        spec = parse_spec(window)
        if checkpoint is not None:
            checkpoint = branch_checkpoint(previous, checkpoint, spec)
        started = time.perf_counter()
        value = run(spec, checkpoint)
        entry = dict(end_s=stop, wall_s=time.perf_counter() - started)
        entry.update({k: float(v) for k, v in value.diagnostics.items() if np.isscalar(v)})
        if record is not None:
            entry.update(record(value))
        windows.append(entry)
        previous, checkpoint = spec, value.final
    return windows


def part_trajectory(args):
    from cells.core.runner import run
    from cells.core.specs import parse_spec

    raw = json.loads(Path(args.definition).read_text())
    if args.end is not None:
        raw["experiment"]["end_time"] = args.end
        raw["experiment"]["observation_times"] = [0.0, args.end]
        for key in ("membrane_controls", "junction_controls", "pump_controls", "channel_controls"):
            for group in raw["experiment"].get(key, []):
                group["schedule"] = [c for c in group["schedule"] if c["time"] <= args.end]
    raw["execution"]["backend"] = "cpu"
    value = run(parse_spec(raw))
    np.savez_compressed(
        Path(args.output) / f"trajectory-{args.label}.npz",
        times=np.asarray(value.times),
        **{k: np.asarray(v) for k, v in value.history._asdict().items()},
    )
    return dict(
        definition=str(args.definition),
        end_time_s=raw["experiment"]["end_time"],
        steps=len(value.times) - 1,
        diagnostics=value.diagnostics,
    )


ELECTRODE_LEDGERS = ("electrode_charge_transferred_C", "electrode_work_pJ")


def part_compare(args):
    report = {}
    for path in sorted(Path(args.base).glob("trajectory-*.npz")):
        other = Path(args.fix) / path.name
        a, b = np.load(path), np.load(other)
        fields, electrode = {}, {}
        for key in a.files:
            x, y = a[key], b[key]
            if key in ELECTRODE_LEDGERS:
                scale = max(float(np.max(np.abs(x), initial=0)), 1e-300)
                electrode[key] = dict(
                    max_abs_difference=float(np.max(np.abs(x - y), initial=0)),
                    max_relative_to_ledger=float(np.max(np.abs(x - y), initial=0)) / scale,
                )
            else:
                fields[key] = bool(x.shape == y.shape and np.array_equal(x, y))
        report[path.stem] = dict(
            bitwise_identical=all(fields.values()),
            differing_fields=[k for k, v in fields.items() if not v],
            electrode_ledgers=electrode,
        )
    return report


def heredity_raw(cells, *, dt, end_time, gate_voltages, channels=True):
    from validation.tissue import surface_pump_v3_fixtures as fixtures

    raw = fixtures.heredity_cells(cells, dt=dt, end_time=end_time, gate_voltages=gate_voltages)
    if not channels:
        raw["model"]["channels"], raw["experiment"]["channel_controls"] = [], []
        raw["execution"]["channel_capacity"] = 0
    return raw


def part_electrode(args):
    import jax.numpy as jnp

    from cells.core.specs import parse_spec
    from cells.core.surface_pump_v3_spec import control_values
    from cells.models import surface_pump_v3 as model
    from cells.models import surface_tissue as tissue
    from validation.tissue import surface_pump_v3_fixtures as fixtures

    steps, dt = args.steps, 1e-3
    states = fixtures.HEREDITY_STATES
    raw = heredity_raw(
        [states["H"][:4], fixtures.kicked(states["D"], -5)],
        dt=dt,
        end_time=steps * dt,
        gate_voltages=[states["H"][0], states["D"][0]],
        channels=False,
    )
    spec = parse_spec(raw)
    state, p = model.initial_values(spec)
    controls = control_values(spec, [0.0])
    control = type(controls)(*(v[0] for v in controls))
    step = jax.jit(lambda y: model.checked_step(y, dt, control, p, p.active))
    host = type(p)(*(np.asarray(v) for v in p))
    held, n = np.asarray(host.reservoir), host.active.size

    def plate(row):
        return tissue.capacitor_change(row, host, xp=np)[1][n:][held]

    start = plate(model.STATE_TYPE(*(np.asarray(v) for v in state)))
    increments, rows = [], []
    marks = {1, 10, 100, 1000, 2000, 5000, 10000, 20000, steps}
    for k in range(1, steps + 1):
        zeroed = state._replace(
            electrode_charge_transferred_C=jnp.zeros_like(state.electrode_charge_transferred_C)
        )
        probe, ok_probe = step(zeroed)
        state, ok = step(state)
        if not (bool(ok) and bool(ok_probe)):
            raise RuntimeError(f"Step refused at {k}")
        increments.append(np.asarray(probe.electrode_charge_transferred_C)[held])
        if k in marks:
            row = model.STATE_TYPE(*(np.asarray(v) for v in state))
            ledger = row.electrode_charge_transferred_C[held]
            exact = np.array([math.fsum(x[i] for x in increments) for i in range(held.sum())])
            truth = plate(row) - start
            b = model.balances(row, host)
            rows.append(
                dict(
                    step=k,
                    ledger_C=ledger.tolist(),
                    accumulation_error_C=(ledger - exact).tolist(),
                    increment_error_C=(exact - truth).tolist(),
                    electrode_residual_C=(ledger - truth).tolist(),
                    global_charge_C=float(b["global_charge"]),
                    global_charge_bound_C=float(model.global_charge_bound(row, host)),
                )
            )
    return dict(dt_s=dt, cells=["H", "D-5mV"], rows=rows)


def part_relax(args):
    from validation.tissue import surface_pump_v3_fixtures as fixtures

    cells, gates = fixtures.relaxing_cells(args.cells)
    raw = heredity_raw(cells, dt=1e-3, end_time=60.0 * args.minutes, gate_voltages=gates)

    def record(value):
        vm = np.asarray(value.observations.membrane_voltage_V[-1])
        return dict(vm_mV=(1e3 * vm[: args.cells]).tolist())

    windows = _run_windows(raw, window_s=args.window, record=record)
    keys = [k for k in windows[0] if k.startswith("max_")]
    return dict(
        cells=args.cells,
        minutes=args.minutes,
        dt_s=1e-3,
        windows=windows,
        worst={k: max(w[k] for w in windows) for k in keys},
    )


def part_fine(args):
    from validation.tissue import surface_pump_v3_study as study

    end, dt = 1.0, 1.5625e-5
    raw = study.write_definition(dt, end_time=end, times=study.grid_times(dt, end))
    windows = _run_windows(raw, window_s=0.25)
    keys = [k for k in windows[0] if k.startswith("max_")]
    return dict(dt_s=dt, steps=round(end / dt), windows=windows,
                worst={k: max(w[k] for w in windows) for k in keys})  # fmt: skip


def part_reaction(args):
    from validation.morphogenesis import mg0a_gradient as mg

    graph = mg.strip(mg.STRIP_CELLS * 4, width_um=mg.CELL_WIDTH_UM / 4)
    dt = mg.stable_dt(graph)
    end = mg._strip_horizon(graph, dt)
    raw = mg.definition(graph, end_time=end, dt=dt, observation_times=[0.0, end])
    started = time.perf_counter()
    result, info = mg.run_segmented(raw)
    return dict(
        cells=graph.n,
        dt_s=dt,
        end_time_s=end,
        steps=round(end / dt),
        wall_s=time.perf_counter() - started,
        run=info,
    )


PARTS = dict(
    trajectory=part_trajectory,
    compare=part_compare,
    electrode=part_electrode,
    relax=part_relax,
    fine=part_fine,
    reaction=part_reaction,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("part", choices=sorted(PARTS))
    parser.add_argument("--output", required=True)
    parser.add_argument("--label", default="")
    parser.add_argument("--definition")
    parser.add_argument("--end", type=float)
    parser.add_argument("--base")
    parser.add_argument("--fix")
    parser.add_argument("--steps", type=int, default=20000)
    parser.add_argument("--cells", type=int, default=2)
    parser.add_argument("--minutes", type=float, default=30.0)
    parser.add_argument("--window", type=float, default=20.0)
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    name = args.part + (f"-{args.label}" if args.label else "")
    started = time.perf_counter()
    try:
        report = dict(status="completed", **PARTS[args.part](args))
    except Exception as error:  # A refusal is a result; keep it.
        report = dict(status="failed", error=repr(error), traceback=traceback.format_exc())
    report.update(
        wall_s=time.perf_counter() - started,
        peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
    )
    (out / f"{name}.json").write_text(json.dumps(report, indent=1, default=float) + "\n")
    print(json.dumps({name: report["status"]}), flush=True)


if __name__ == "__main__":
    main()
