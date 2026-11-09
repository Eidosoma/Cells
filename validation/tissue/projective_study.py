"""Development studies of the projective mode (core/projective.py) against fine stepping.

Each case runs one definition twice from the same initial state: projective
(execution.projective, the ordinary runner) and fine (the same definition
without the block). The fine reference here is a development harness: the
same compiled checked-step burst kernel as the projective bursts
(core/projective._Bursts.advance), with the model's per-row check_values
omitted, so rows before the first jump agree bitwise and long references stay
affordable. A judged comparison uses a fully checked fine run instead.

Compared at every observation time (fine rows in both runs): the error
coordinates of models/surface_pump_projective.py (concentrations, membrane
voltages, gates). The estimate-based allowance of class q at time t is
S * tol_q * sum of estimate_normalized over the jumps accepted before t
(numerics/projective.error_estimate; S = ESTIMATE_FACTOR). Also written: the
projective report (jumps, rejections, fallbacks, energy defects, linear-ledger
records), step and wall-time speed-ups, and the fine engine diagnostics.

Usage:
  python -m validation.tissue.projective_study CASE [CASE ...] --output DIR
      [--end SECONDS] [--every SECONDS]
"""

import argparse
import json
import resource
import time
import traceback
from pathlib import Path

import jax
import numpy as np

jax.config.update("jax_enable_x64", True)

from cells.core.projective import _Bursts  # noqa: E402
from cells.core.runner import run  # noqa: E402
from cells.core.specs import parse_spec  # noqa: E402
from cells.core.state import initialise  # noqa: E402
from cells.models import surface_pump_projective as readouts  # noqa: E402
from cells.models.registry import get_model  # noqa: E402
from validation.tissue import projective_fixtures as fixtures  # noqa: E402

ESTIMATE_FACTOR = 2.0  # Allowance / summed first-order local-error estimates.
REFERENCE_WIDTH = 5000  # Fine steps per reference burst.


def case_pair1(args):
    """@1: an H-composition cell and a Na-loaded cell, each with its own held bath."""
    end = args.end
    raw = fixtures.pump_cells(
        [fixtures.H, fixtures.LOADED],
        end_time=end,
        observation_times=fixtures.grid_times(1e-3, end, args.every),
    )
    raw["execution"]["projective"] = fixtures.projective_block(
        [(10.0, end)],
        burst_steps=args.burst,
        slope_steps=args.slope,
        max_steps=args.max_steps,
        tolerance=_tolerance(args),
    )
    return raw


def case_cue1(args):
    """@1 pair with a pump block (availability 0.3) for 5 s inside the window."""
    end = args.end
    cue = round(0.5 * end)
    raw = fixtures.pump_cells(
        [fixtures.H, fixtures.LOADED],
        end_time=end,
        observation_times=fixtures.grid_times(1e-3, end, args.every),
        pump_controls={0: [(0.0, 1.0), (float(cue), 0.3), (float(cue + 5), 1.0)]},
    )
    raw["execution"]["projective"] = fixtures.projective_block(
        [(10.0, end)],
        burst_steps=args.burst,
        slope_steps=args.slope,
        max_steps=args.max_steps,
        tolerance=_tolerance(args),
    )
    return raw


def case_closed1(args):
    """@1 closed synthetic tissue: junction gate, faces, finite outside nodes."""
    end = args.end
    raw = fixtures.closed_tissue(
        end_time=end, observation_times=fixtures.grid_times(1e-3, end, args.every)
    )
    raw["execution"]["projective"] = fixtures.projective_block(
        [(5.0, end)],
        burst_steps=args.burst,
        slope_steps=args.slope,
        max_steps=args.max_steps,
        tolerance=_tolerance(args),
    )
    return raw


def _heredity(args, cells, *, cue=None):
    """@3 heredity cells (surface_pump_v3_fixtures.heredity_cells) with a projective block.

    cue: optional (start, stop) of a 9x Na-leak cue on cell 0 (a NaLeak channel
    switched on and off by its schedule), as in surface_pump_v3_study.
    """
    from cells.core.surface_pump_v3_spec import NALEAK_LAW_ID
    from validation.tissue import surface_pump_v3_fixtures as heredity

    end = args.end
    raw = heredity.heredity_cells(
        [c[:4] for c in cells],
        end_time=end,
        observation_times=fixtures.grid_times(1e-3, end, args.every),
        gate_voltages=[c[0] for c in cells],
    )
    if cue is not None:
        raw["model"]["channels"].append(
            dict(
                id="cue_0",
                membrane_id="membrane_0",
                kinetic_law=NALEAK_LAW_ID,
                max_permeability_m_per_s=9 * heredity.HEREDITY_PERMEABILITY["Na"],
                abundance=1.0,
                initial_gate=[],
                permeant_ions=[dict(species_id="Na", relative_permeability=1.0)],
            )
        )
        raw["experiment"]["channel_controls"].append(
            dict(
                channel_id="cue_0",
                schedule=[
                    dict(time=0.0, availability=0.0),
                    dict(time=cue[0], availability=1.0),
                    dict(time=cue[1], availability=0.0),
                ],
            )
        )
        raw["execution"]["channel_capacity"] += 1
    raw["execution"]["projective"] = fixtures.projective_block(
        [(args.window_start, end)],
        burst_steps=args.burst,
        slope_steps=args.slope,
        max_steps=args.max_steps,
        tolerance=_tolerance(args),
        row_checks=args.row_checks,
    )
    return raw


def _near_saddle():
    from validation.tissue import surface_pump_v3_fixtures as heredity

    u = heredity.HEREDITY_STATES["U"]
    return [(u[0] - 0.002, *u[1:4]), (u[0] + 0.002, *u[1:4])]


def case_relax3(args):
    """@3 pair started at the saddle composition, +-2 mV: slow relaxation on both branches."""
    return _heredity(args, _near_saddle())


def case_cue3(args):
    """relax3 with a 0.3 s 9x Na-leak cue on cell 0 at mid-horizon, inside the window."""
    start = round(0.5 * args.end, 3)
    return _heredity(args, _near_saddle(), cue=(start, round(start + 0.3, 3)))


def _tolerance(args):
    return dict(
        concentration_mM=args.tol_concentration,
        membrane_voltage_V=args.tol_voltage,
        gate=args.tol_gate,
    )


CASES = dict(
    pair1=case_pair1,
    cue1=case_cue1,
    closed1=case_closed1,
    relax3=case_relax3,
    cue3=case_cue3,
)


def fine_reference(spec, times):
    """States at the given grid times from unchecked fine bursts (development harness)."""
    from cells.core.grid import EventGrid

    model = get_model(spec.model)
    checkpoint = initialise(spec)
    grid = EventGrid(spec)
    bursts = _Bursts(spec, model, checkpoint.layout, REFERENCE_WIDTH)
    state, index, last = checkpoint.state, 0, len(grid) - 1
    targets = {grid.exact_index(t): t for t in times}
    rows = {}
    if 0 in targets:
        rows[targets[0]] = model.STATE_TYPE(*(np.asarray(v) for v in state))
    started = time.perf_counter()
    while index < last:
        count = min(REFERENCE_WIDTH, last - index)
        stamps = np.fromiter((grid[k] for k in range(index, index + count + 1)), np.float64)
        state, burst = bursts.advance(state, stamps)
        for k in range(1, count + 1):
            if index + k in targets:
                rows[targets[index + k]] = type(burst)(*(np.asarray(v[k]) for v in burst))
        index += count
    timing = dict(
        compile_seconds=bursts.compile_seconds,
        execute_seconds=bursts.execute_seconds,
        total_seconds=time.perf_counter() - started,
        steps=last,
    )
    return rows, timing


def compare(spec, result, rows):
    model, p = get_model(spec.model), readouts.host_layout(result.final.layout)
    tolerance = {k: getattr(spec.projective.tolerance, k) for k in readouts.COORDINATES}
    jumps = result.projective["jump_log"]
    table = []
    for t in spec.experiment.observation_times:
        i = int(np.flatnonzero(result.times == t)[0])
        mine = readouts.coordinates(model, type(rows[t])(*(v[i] for v in result.history)), p)
        theirs = readouts.coordinates(model, rows[t], p)
        estimate = sum(j["estimate_normalized"] for j in jumps if j["to_time_s"] <= t)
        entry = dict(time_s=t, kind=int(result.row_kinds[i]), estimate_sum=estimate)
        for k in readouts.COORDINATES:
            error = float(np.max(np.abs(mine[k] - theirs[k]), initial=0.0))
            allowance = ESTIMATE_FACTOR * tolerance[k] * estimate
            entry[k] = dict(error=error, allowance=allowance)
        table.append(entry)
    worst = {
        k: dict(
            max_error=max(e[k]["error"] for e in table),
            max_ratio=max(
                (e[k]["error"] / e[k]["allowance"] if e[k]["allowance"] > 0 else
                 (np.inf if e[k]["error"] > 0 else 0.0))
                for e in table
            ),
        )
        for k in readouts.COORDINATES
    }  # fmt: skip
    return table, worst


def summary(report):
    ledgers = {}
    for jump in report["jump_log"]:
        for name, value in jump["ledgers"].items():
            entry = ledgers.setdefault(name, dict(max_after=0.0, max_affine_excess=0.0))
            entry["max_after"] = max(entry["max_after"], value["after"])
            entry["max_affine_excess"] = max(entry["max_affine_excess"], value["affine_excess"])
    jumps = report["jump_log"]
    return dict(
        ledgers=ledgers,
        max_energy_defect_ratio=max(
            (j["energy_defect_pJ"] / j["energy_bound_pJ"] for j in jumps), default=0.0
        ),
        max_correction=max((j["correction_normalized"] for j in jumps), default=0.0),
        max_estimate=max((j["estimate_normalized"] for j in jumps), default=0.0),
        jump_seconds=[j["to_time_s"] - j["from_time_s"] for j in jumps],
    )


def run_case(name, args):
    raw = CASES[name](args)
    spec = parse_spec(raw)
    fine = dict(raw, execution={k: v for k, v in raw["execution"].items() if k != "projective"})
    fine_spec = parse_spec(fine)
    out = Path(args.output)
    started = time.perf_counter()
    result = run(spec)
    projective_wall = time.perf_counter() - started
    rows, reference_timing = fine_reference(fine_spec, spec.experiment.observation_times)
    table, worst = compare(spec, result, rows)
    report = dict(result.projective)
    entry = dict(
        case=name,
        definition=raw,
        projective_wall_s=projective_wall,
        projective_timings=result.timings,
        reference_timing=reference_timing,
        diagnostics=result.diagnostics,
        comparison=table,
        worst=worst,
        estimate_factor=ESTIMATE_FACTOR,
        summary=summary(report),
        report=report,
        peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
    )
    (out / f"{name}.json").write_text(json.dumps(entry, indent=1, default=_json) + "\n")
    return dict(
        case=name,
        fine_steps=report["fine_steps"],
        jumped_steps=report["jumped_steps"],
        step_speedup=report["step_speedup"],
        jumps=report["jumps"],
        rejections=report["rejections"],
        fallbacks=report["fallback_counts"],
        worst=worst,
    )


def _json(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer, np.bool_)):
        return value.item()
    if isinstance(value, complex):
        return [value.real, value.imag]
    return str(value)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("cases", nargs="+", choices=sorted(CASES))
    parser.add_argument("--output", required=True)
    parser.add_argument("--end", type=float, default=300.0)
    parser.add_argument("--every", type=float, default=30.0)
    parser.add_argument("--burst", type=int, default=2000)
    parser.add_argument("--slope", type=int, default=250)
    parser.add_argument("--max-steps", type=int, default=60000)
    parser.add_argument("--tol-concentration", type=float, default=1e-3)
    parser.add_argument("--tol-voltage", type=float, default=1e-5)
    parser.add_argument("--tol-gate", type=float, default=1e-4)
    parser.add_argument("--window-start", type=float, default=3.0)
    parser.add_argument("--row-checks", choices=("host", "device"), default="host")
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    status = {}
    for name in args.cases:
        began = time.perf_counter()
        try:
            status[name] = dict(status="completed", **run_case(name, args))
        except Exception as error:  # A failure is a result; keep it.
            status[name] = dict(
                status="failed", error=repr(error), traceback=traceback.format_exc()
            )
        status[name]["seconds"] = time.perf_counter() - began
        print(json.dumps({name: status[name]}, default=_json), flush=True)
    outcome = "failure" if any(v["status"] == "failed" for v in status.values()) else "result"
    (out / f"{outcome}.json").write_text(
        json.dumps(dict(cases=status, argv=vars(args)), indent=1, default=_json) + "\n"
    )


if __name__ == "__main__":
    main()
