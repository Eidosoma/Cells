"""resolved_pump_water@1 with closed water against resolved_pump_tissue@3 on the 825-node world.

tests/unit/test_surface_pump_water_equivalence.py covers the heredity single
cell and the seven-cell gated sheet. This driver covers W225, the 825-node
world (validation/tissue/resolved_scale_world.py as @3, NaV1.2 and Kir2.1 on
every patch, finite extracellular squares and a held ring), which runs longer
than a unit test:

* compiled with default XLA flags, IMEX Euler and ARS(2,2,2) at 1 ms over
  --steps steps with a NaV1.2 change at 1/3 and a pump change at 1/2 of the run:
  every @3 state field, observation and check diagnostic must be bitwise equal,
  and every water field exactly zero;
* uncompiled (jit off), ARS(2,2,2) over --eager-steps steps: the same;
* cost: wall time per step of @3 and of the water model with water open
  (closed-tissue water on the finite squares, a cost measurement only: that
  configuration is not a qualified water arm).

Writes result.json (verdict and per-case records) or failure.json (traceback).
Usage: python -m validation.tissue.pump_water_equivalence --output DIR
       [--steps 1200] [--eager-steps 3] [--cost-steps 200]
"""

import argparse
import json
import time
import traceback
from pathlib import Path

import jax

jax.config.update("jax_enable_x64", True)

import numpy as np  # noqa: E402

from cells.core.runner import run  # noqa: E402
from cells.core.specs import parse_spec  # noqa: E402
from cells.models import surface_pump_v3, surface_pump_water  # noqa: E402
from cells.numerics import surface_imex as imex  # noqa: E402
from validation.tissue import pump_water_fixtures as fixtures  # noqa: E402


def definitions(solver, steps, *, jit=True, availability=0.0):
    dt = 1e-3
    end = round(steps * dt, 9)
    raw = fixtures.scale_world(dt=dt, end_time=end, solver=solver)
    raw = fixtures.scheduled(
        raw,
        channel_change=(round(steps // 3 * dt, 9), 0.5),
        pump_change=(round(steps // 2 * dt, 9), 0.8),
    )
    raw["experiment"]["observation_times"] = [0.0, round(steps // 4 * dt, 9), end]
    raw["execution"]["jit"] = jit
    return parse_spec(raw), parse_spec(fixtures.with_water(raw, availability=availability))


def compare(reference, result):
    record = dict(state={}, observations={}, diagnostics={}, water_fields_zero=True)
    for key in surface_pump_v3.STATE_TYPE._fields:
        a, b = np.asarray(getattr(result.history, key)), np.asarray(getattr(reference.history, key))
        record["state"][key] = (
            "bitwise" if np.array_equal(a, b) else float(np.max(np.abs(a - b), initial=0))
        )
    for key, value in vars(reference.observations).items():
        a = np.asarray(getattr(result.observations, key))
        record["observations"][key] = (
            "bitwise" if np.array_equal(a, value) else float(np.max(np.abs(a - value), initial=0))
        )
    for key, value in reference.diagnostics.items():
        if key.startswith("max_"):
            other = result.diagnostics[key]
            record["diagnostics"][key] = "bitwise" if other == value else [value, other]
    for key in surface_pump_water.WATER_STATE_AXES:
        record["water_fields_zero"] &= not np.any(np.asarray(getattr(result.history, key)))
    record["bitwise"] = record["water_fields_zero"] and all(
        v == "bitwise"
        for part in ("state", "observations", "diagnostics")
        for v in record[part].values()
    )
    return record


def timed(spec):
    started = time.perf_counter()
    result = run(spec)
    return result, dict(result.timings, wall_seconds=time.perf_counter() - started)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--steps", type=int, default=1200)
    parser.add_argument("--eager-steps", type=int, default=3)
    parser.add_argument("--cost-steps", type=int, default=200)
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    cases = []
    try:
        for solver in (imex.EULER_ID, imex.ARS222_ID):
            reference, water = definitions(solver, args.steps)
            a, ta = timed(reference)
            b, tb = timed(water)
            cases.append(
                dict(case=f"compiled-{solver}", steps=args.steps, timings=[ta, tb]) | compare(a, b)
            )
            (out / "progress.json").write_text(json.dumps(cases, indent=2) + "\n")
        reference, water = definitions(imex.ARS222_ID, args.eager_steps, jit=False)
        a, ta = timed(reference)
        b, tb = timed(water)
        cases.append(
            dict(case="uncompiled-ars222", steps=args.eager_steps, timings=[ta, tb]) | compare(a, b)
        )
        reference, water = definitions(imex.ARS222_ID, args.cost_steps, availability=1.0)
        _, ta = timed(reference)
        _, tb = timed(water)
        cost = dict(
            steps=args.cost_steps,
            ionic_execute_seconds=ta["execute_seconds"],
            water_execute_seconds=tb["execute_seconds"],
            ratio=tb["execute_seconds"] / ta["execute_seconds"],
            timings=[ta, tb],
            note="water open on the finite squares: cost only, not a qualified water arm",
        )
        result = dict(
            verdict="pass" if all(c["bitwise"] for c in cases) else "fail",
            cases=cases,
            cost=cost,
        )
        (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    except Exception:
        (out / "failure.json").write_text(
            json.dumps(dict(cases=cases, traceback=traceback.format_exc()), indent=2) + "\n"
        )
        raise


if __name__ == "__main__":
    main()
