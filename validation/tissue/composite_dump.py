"""Save runs of named worlds and compare two saved sets bitwise (cross-revision guard).

D143's thin compositions replace a frozen model's implementation by the composite.
The frozen implementation then exists only in an earlier revision, so the guard
runs the same definitions in both revisions (the earlier one from its execution
snapshot) and compares the saved results: every state field (full history, or
the final state and the observation rows for long worlds), every observation
column and every max_ diagnostic, with np.array_equal (NaN-aware) as the
equivalence tests compare, and records whether the bit patterns are identical.

Usage:
  python composite_dump.py dump --output DIR [--worlds NAME,...]
  python composite_dump.py compare FROZEN_DIR THIN_DIR --output FILE
"""

import argparse
import copy
import json
import sys
import time
from pathlib import Path

import numpy as np

FULL_HISTORY_ROWS = 5000  # Longer runs save observations, the final state and diagnostics.


def _water_worlds():
    from validation.tissue import pump_water_fixtures as fx
    from validation.tissue import surface_pump_v3_fixtures as v3

    aquaporin = 5e-4

    def cell(state="H", *, end=0.2, dt=1e-3, solver="imex_ars222_face_electromigration@1", **kw):
        raw = fx.heredity_cell(state, dt=dt, end_time=end, solver=solver)
        raw["experiment"]["observation_times"] = [0.0, round(end / 2, 6), end]
        return fx.with_water(raw, **kw)

    def closed_ions(raw):
        for key in ("membrane_controls", "pump_controls", "channel_controls"):
            for group in raw["experiment"][key]:
                group["schedule"] = [dict(time=0.0, availability=0.0)]
        return raw

    def kicked(dt, end, solver="imex_ars222_face_electromigration@1"):
        state = v3.kicked(v3.HEREDITY_STATES["D"], 4.0)
        raw = v3.heredity_cells(
            [state], dt=dt, end_time=end, solver=solver, observation_times=[0.0, end / 2, end]
        )
        return fx.with_water(raw, pf_m_s=aquaporin)

    def sheet(end=0.03):
        raw = fx.gated_sheet(end_time=end)
        raw["experiment"]["observation_times"] = [0.0, end / 2, end]
        raw["model"]["junction_heat_booking"] = "trapezoid_nonnegative@1"
        return fx.with_water(raw, pf_m_s=aquaporin)

    def regulated(raw):
        return fx.with_symport(raw, flux_mmol_L_h=15.0, steepness=0.12)

    def equivalence(world, solver):
        maker = {
            "cell_H": lambda **k: fx.heredity_cell("H", **k),
            "cell_D": lambda **k: fx.heredity_cell("D", **k),
            "sheet7": fx.gated_sheet,
        }[world]
        raw = fx.scheduled(maker(dt=1e-3, end_time=1.2, solver=solver))
        raw["experiment"]["observation_times"] = [0.0, 0.4, 0.6, 1.2]
        return fx.with_water(raw, availability=0.0)

    worlds = {
        "water_on": lambda: cell("H", end=0.3, pf_m_s=aquaporin),
        "osmometer": lambda: closed_ions(
            cell(end=0.5, dt=2e-3, pf_m_s=aquaporin, bulk_modulus_Pa=0.0, pressure_offset_Pa=0.0)
        ),
        "euler_kicked": lambda: kicked(1e-3, 0.064, "imex_euler_face_electromigration@1"),
        "rk4_coupled": lambda: kicked(2.5e-6, 2.5e-4, "rk4"),
        "sheet_trapezoid": sheet,
        "route_on": lambda: regulated(cell("D", end=0.2, pf_m_s=aquaporin)),
        "route_none": lambda: fx.with_symport(cell("D", end=0.2, pf_m_s=aquaporin), membranes=[]),
        "route_blocked": lambda: fx.with_symport(
            cell("D", end=0.2, pf_m_s=aquaporin), availability=0.0
        ),
        "route_sheet": lambda: regulated(sheet(0.02)),
        "route_rk4": lambda: regulated(kicked(2.5e-6, 2.5e-4, "rk4")),
    }
    for world in ("cell_H", "cell_D", "sheet7"):
        for label, solver in (
            ("euler", "imex_euler_face_electromigration@1"),
            ("ars", "imex_ars222_face_electromigration@1"),
        ):
            worlds[f"closed_{world}_{label}"] = lambda w=world, s=solver: equivalence(w, s)
    return worlds


def _w1_worlds():
    from validation.tissue import pump_water_qualification as w1q

    root = Path(w1q.__file__).parent  # The predictions of the revision under test.
    predictions = json.loads((root / "pump_water_predictions.json").read_text())
    return {
        "W1_" + name: (
            lambda path=path: w1q.with_step(w1q.item(predictions, path)["definition"], 1e-3)
        )
        for name, path in w1q.TRAJECTORIES.items()
    }


def _w2_worlds():
    from validation.tissue import pump_water_kcc_qualification as w2q

    root = Path(w2q.__file__).parent
    predictions = json.loads((root / "pump_water_kcc_predictions.json").read_text())

    def trajectory(arm):
        raw = copy.deepcopy(w2q.definition(predictions, arm))
        raw["experiment"]["end_time"] = 1.0
        raw["experiment"]["observation_times"] = [0.0, 0.5, 1.0]
        raw["execution"]["max_steps"] = 2000
        return raw

    return {"W2_" + arm: (lambda arm=arm: trajectory(arm)) for arm in predictions["arms"]}


def worlds():
    return _water_worlds() | _w1_worlds() | _w2_worlds()


def dump(name, raw, out):
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.core.runner import run
    from cells.core.specs import parse_spec

    spec = parse_spec(raw)
    started = time.perf_counter()
    result = run(spec)
    arrays = {"times": np.asarray(result.times)}
    full = len(result.times) <= FULL_HISTORY_ROWS
    for key in type(result.history)._fields:
        value = np.asarray(getattr(result.history, key))
        arrays["history." + key] = value if full else value[-1:]
    for key, value in vars(result.observations).items():
        arrays["observations." + key] = np.asarray(value)
    np.savez(out / f"{name}.npz", **arrays)
    record = dict(
        world=name,
        model=raw["model"]["id"],
        full_history=full,
        rows=len(result.times),
        diagnostics={k: v for k, v in result.diagnostics.items() if k.startswith("max_")},
        wall_s=time.perf_counter() - started,
    )
    (out / f"{name}.json").write_text(json.dumps(record, indent=1, default=float) + "\n")
    return record


def compare(frozen, thin):
    report = {}
    for path in sorted(Path(frozen).glob("*.json")):
        name = path.stem
        other = Path(thin) / path.name
        if not other.exists():
            report[name] = dict(equal=False, missing=True)
            continue
        a, b = json.loads(path.read_text()), json.loads(other.read_text())
        differences = []
        if a["diagnostics"] != b["diagnostics"]:
            keys = [k for k in a["diagnostics"] if a["diagnostics"][k] != b["diagnostics"].get(k)]
            differences.append(dict(field="diagnostics", keys=keys))
        x, y = np.load(Path(frozen) / f"{name}.npz"), np.load(Path(thin) / f"{name}.npz")
        bits = True
        for key in x.files:
            if key not in y.files:
                differences.append(dict(field=key, kind="missing"))
                continue
            u, v = x[key], y[key]
            if u.shape != v.shape or u.dtype != v.dtype:
                differences.append(dict(field=key, kind="shape or dtype"))
                continue
            same = np.array_equal(u, v, equal_nan=u.dtype.kind == "f")
            if not same:
                matching = u == v
                if u.dtype.kind == "f":
                    matching |= np.isnan(u) & np.isnan(v)
                index = [int(i) for i in np.argwhere(~matching)[0]]
                differences.append(
                    dict(
                        field=key,
                        index=index,
                        frozen=u[tuple(index)].item(),
                        thin=v[tuple(index)].item(),
                    )
                )
            bits &= u.tobytes() == v.tobytes()
        report[name] = dict(
            equal=not differences,
            bitwise=not differences and bits,
            first=differences[0] if differences else None,
            arrays=len(x.files),
        )
    return report


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("dump", "compare"))
    parser.add_argument("dirs", nargs="*")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worlds", type=lambda s: s.split(","), default=None)
    args = parser.parse_args(argv)
    if args.action == "compare":
        report = compare(*args.dirs)
        verdict = "equal" if report and all(r["equal"] for r in report.values()) else "differs"
        args.output.write_text(json.dumps(dict(verdict=verdict, worlds=report), indent=1) + "\n")
        print(verdict, sum(r["equal"] for r in report.values()), "of", len(report))
        return
    args.output.mkdir(parents=True, exist_ok=True)
    for name, make in worlds().items():
        if args.worlds and name not in args.worlds:
            continue
        if (args.output / f"{name}.json").exists():
            continue  # Resumable.
        try:
            record = dump(name, make(), args.output)
            print(name, record["rows"], round(record["wall_s"], 1), "s", flush=True)
        except Exception as error:  # A refusal is evidence: record it.
            import traceback

            (args.output / f"{name}-failure.json").write_text(
                json.dumps(dict(world=name, error=repr(error), traceback=traceback.format_exc()))
            )
            print(name, "FAILED", repr(error), flush=True, file=sys.stderr)


if __name__ == "__main__":
    main()
