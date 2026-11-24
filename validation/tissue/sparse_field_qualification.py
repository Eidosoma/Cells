"""FR-17 stage 1's run comparison and timing on the gap-junction replication's worlds
(docs/FIELD_SOLVER_INTERFACE_DESIGN.md §8.5 items 2, 4 and 6; GJ-N1's amendment 1, item 3).

windows runs one world under one field solver through the production window path
(validation/gap_junction_tissue/neither.execute's: cells.execution.windows.iter_windows with
WindowPolicy(the shape's window steps, "observations", "device"), every engine check running) for
a number of windows, and saves every window's observations, the final state and the diagnostics,
with each window's wall and process CPU seconds (the first window's include its compile).
compare reads two saved runs and reports, array by array, whether the bytes are identical, whether
the values are equal (signed zeros aside), and the largest difference against the largest value;
arrays of the ledger fields (validation/tissue/inplace_fix_guard.LEDGER_FIELDS) are marked.

The worlds are neither.coupled_world's at D = 0 and at the bracket's upper end (1e-13 m^2/s), on
the field (25 x 25) and on the line, started from the line's pinned stage-1 state
(neither.STAGE1_END_UNITS, as crossrev's replication set starts them): the field's own stage 1 is
not run, and no GJ-N1 criterion is computed. The field solver is set on the definition
(execution.field_solver), so both runs share every other byte of it.

Usage (PYTHONPATH at an execution snapshot, JAX_ENABLE_X64=1 JAX_PLATFORMS=cpu):
  python -m validation.tissue.sparse_field_qualification windows WORLD SOLVER WINDOWS OUTDIR
  python -m validation.tissue.sparse_field_qualification compare DIR_A DIR_B OUT.json
WORLD: gj_field_d0, gj_field_d1e-13, gj_line_d0 or gj_line_d1e-13. SOLVER: 2 (version 2) or
sparse (sparse_capacitive_reduction_gauged_damped_newton@1).
"""

import json
import resource
import sys
import time
from pathlib import Path

import numpy as np

SOLVERS = {
    "2": "capacitive_reduction_gauged_damped_newton@2",
    "sparse": "sparse_capacitive_reduction_gauged_damped_newton@1",
}


def world(name, windows):
    """(definition, window steps) of a named world, its end at `windows` production windows."""
    from validation.gap_junction_tissue import neither

    _, shape, d = name.split("_")
    d = {"d0": 0.0, "d1e-13": neither.BRACKET[1]}[d]
    neighbours = neither.tissue(shape)[3]
    steps = neither.WINDOW_STEPS_OF[shape]
    dt = neither.step(d, neighbours)
    raw = neither.coupled_world(d, neither.STAGE1_END_UNITS, end=windows * steps * dt, shape=shape)
    return raw, steps


def windows(name, solver, count, out):
    import jax

    from cells.definitions.specs import parse_spec
    from cells.execution.windows import WindowPolicy, iter_windows

    jax.config.update("jax_enable_x64", True)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    raw, steps = world(name, count)
    raw["execution"]["field_solver"] = SOLVERS[solver]
    started = (time.perf_counter(), time.process_time())
    spec = parse_spec(raw)
    parsed = (time.perf_counter(), time.process_time())
    arrays, wall, cpu, diagnostics, last = {}, [], [], {}, None
    clock = parsed
    for k, window in enumerate(iter_windows(spec, WindowPolicy(steps, "observations", "device"))):
        now = (time.perf_counter(), time.process_time())
        wall.append(now[0] - clock[0])
        cpu.append(now[1] - clock[1])
        clock = now
        last = window
        for key, value in window.diagnostics.items():
            diagnostics[key] = max(diagnostics.get(key, -np.inf), float(value))
        if window.observations is not None:
            for key, value in vars(window.observations).items():
                arrays[f"window{k}.observations.{key}"] = np.asarray(value)
    for key in type(last.final.state)._fields:
        arrays["final." + key] = np.asarray(getattr(last.final.state, key))
    np.savez_compressed(out / "run.npz", **arrays)
    record = dict(
        world=name,
        field_solver=SOLVERS[solver],
        layout=type(last.final.layout).__name__,
        windows=len(wall),
        window_steps=steps,
        steps=int(last.final.step_index),
        final_time_s=float(last.final.time),
        dt_s=spec.execution.dt,
        parse_s=parsed[0] - started[0],
        window_wall_s=wall,
        window_cpu_s=cpu,
        diagnostics=diagnostics,
        definition_sha256=spec.fingerprint,
        max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    )
    (out / "run.json").write_text(json.dumps(record, indent=1) + "\n")
    tail = wall[1:] or wall
    print(name, solver, f"{len(wall)} windows, step {np.median(tail) / steps * 1e3:.2f} ms wall "
          f"(median after the first window), first window {wall[0]:.1f} s", flush=True)  # fmt: skip


def compare(a, b, out):
    from validation.tissue.inplace_fix_guard import LEDGER_FIELDS

    x, y = np.load(Path(a) / "run.npz"), np.load(Path(b) / "run.npz")
    ra, rb = (json.loads((Path(d) / "run.json").read_text()) for d in (a, b))
    arrays = {}
    for key in sorted(set(x.files) | set(y.files)):
        if key not in x.files or key not in y.files:
            arrays[key] = dict(missing=True)
            continue
        u, v = x[key], y[key]
        field = key.rsplit(".", 1)[-1]
        entry = dict(ledger=field in LEDGER_FIELDS, identical=u.tobytes() == v.tobytes())
        if u.shape != v.shape or u.dtype != v.dtype:
            entry.update(shape_or_dtype=True)
        elif not entry["identical"]:
            if u.dtype.kind in "fc":
                d = np.abs(u.astype(float) - v.astype(float))
                scale = float(np.nanmax(np.abs(np.r_[u.ravel(), v.ravel()]), initial=0.0))
                entry.update(
                    equal=bool(np.array_equal(u, v, equal_nan=True)),
                    differing=int(np.count_nonzero(u != v)),
                    max_abs_difference=float(np.nanmax(d, initial=0.0)),
                    max_abs_value=scale,
                    max_relative=float(np.nanmax(d, initial=0.0)) / scale if scale else None,
                )
            else:
                entry.update(equal=False, differing=int(np.count_nonzero(u != v)))
        arrays[key] = entry
    physical = sorted(k for k, e in arrays.items() if not e.get("identical") and not e["ledger"])
    ledger = sorted(k for k, e in arrays.items() if not e.get("identical") and e["ledger"])
    diagnostics = {
        k: [ra["diagnostics"].get(k), rb["diagnostics"].get(k)]
        for k in sorted(set(ra["diagnostics"]) | set(rb["diagnostics"]))
        if ra["diagnostics"].get(k) != rb["diagnostics"].get(k)
    }
    report = dict(
        a=dict(dir=str(a), field_solver=ra["field_solver"], layout=ra["layout"]),
        b=dict(dir=str(b), field_solver=rb["field_solver"], layout=rb["layout"]),
        world=ra["world"],
        same_definition_but_field_solver=ra["world"] == rb["world"],
        arrays_compared=len(arrays),
        bitwise_identical=not physical and not ledger and not diagnostics,
        physical_differing=physical,
        ledger_differing=ledger,
        diagnostics_differing=diagnostics,
        arrays={k: e for k, e in arrays.items() if not e.get("identical")},
    )
    Path(out).write_text(json.dumps(report, indent=1) + "\n")
    print(ra["world"], "identical" if report["bitwise_identical"] else
          f"differs: {len(physical)} physical, {len(ledger)} ledger arrays, "
          f"{len(diagnostics)} diagnostics")  # fmt: skip


if __name__ == "__main__":
    action, *args = sys.argv[1:]
    if action == "windows":
        windows(args[0], args[1], int(args[2]), args[3])
    elif action == "compare":
        compare(*args)
    else:
        raise SystemExit(__doc__)
