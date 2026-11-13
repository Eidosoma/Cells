"""Cross-revision run guard of an in-place fix to shared qualified code (D148, drafted).

D148 admits an in-place fix only when, fix against no fix, no physical field changes in any
qualified world in any program, every judge's registered numbers are unchanged, and the
ledger accumulators change at most at the rounding level. The first S3 use is
surface_tissue.capacitor_change (docs/PUMP_COMPOSITE_V2_DESIGN.md §3, prerequisite (c)).

dump runs a part's worlds in one revision (PYTHONPATH at its execution snapshot) and saves
each run: every state field's history, observation column and max_ diagnostic, and the
device row checks of every row where the model has them. compare reads two saved sets and
classifies every difference as physical or ledger (LEDGER_FIELDS, ledger_diagnostic).

Parts and their programs:
* dumps: the 17 saved runs of composite_dump.py (scalar, core/runner.run);
* base, injection: crossrev's base and injection worlds (scalar, device checks);
* egg: the Rm1 egg with its two pulses to 420 s (scalar; host checks recorded, not
  enforced, because without the fix its electrode ledger fails there);
* qualification: G2-Q1's nine cases, W37, and the 825-node world as @3, as its empty
  composition, with closed water and with event-free replacement (scalar, device checks);
* w1: W1's six judged trajectories at 1 ms (windowed, core/windows.run_windowed, as the
  judge runs them: every window's observations and the final state);
* pump: resolved_pump_tissue@1 and @2 worlds, RK4 and IMEX (scalar, device checks);
* cohorts: Q6's cohorts, 2 W7 worlds and 8 C9 worlds (vmapped vector windows,
  core/vector_windows; and the lax_map batch, core/batch).

Usage:
  python inplace_fix_guard.py dump PART[,PART...] --output DIR [--worlds NAME,...]
  python inplace_fix_guard.py compare BEFORE AFTER --output FILE
"""

import argparse
import copy
import json
import sys
import time
import traceback
from pathlib import Path

import numpy as np

# Fields booked from capacitor_change's plate charges and patch voltages: the electrode
# ledger, and the image charge, work and energy terms of the operators that book with it.
LEDGER_FIELDS = (
    "electrode_charge_transferred_C",
    "electrode_work_pJ",
    "injection_image_charge_C",
    "injection_work_pJ",
    "injection_energy_magnitude_pJ",
    "replacement_image_charge_C",
    "replacement_free_energy_pJ",
    "replacement_energy_magnitude_pJ",
)


def ledger_diagnostic(key):
    """A max_ diagnostic that is a ledger residual or its ratio to a bound."""
    return key.startswith("max_") and ("_error" in key or key.endswith(("_ratio", "_relative")))


def _crossrev():
    from validation.tissue import composite_crossrev as crossrev

    return crossrev


def _dumps():
    from validation.tissue import composite_dump as dumps

    names = [
        "water_on",
        "osmometer",
        "rk4_coupled",
        "route_on",
        "route_none",
        "route_rk4",
        "replacement_events",
        "replacement_donors",
        "replacement_rk4",
    ]
    for arm in ("red_cell_4", "red_cell_15", "red_cell_20", "neuron_scale_model_derived"):
        names += [f"W2_{arm}-lew_s1", f"W2_{arm}-kaji_s0.12"]
    built = dumps.worlds()
    return {name: built[name] for name in names}


def _egg():
    from validation.tissue import injection_rm1 as rm1

    def build():
        raw = copy.deepcopy(rm1.definition(1e-3))
        raw["experiment"]["end_time"] = 420.0
        raw["experiment"]["observation_times"] = [float(t) for t in np.arange(0.0, 420.1, 20.0)]
        raw["execution"]["max_steps"] = 420008
        return raw

    return {"egg_rm1_420s": build}


def _qualification():
    from cells.core import pump_composite_spec as cs
    from validation.tissue import surface_pump_v3_study as study

    worlds = _crossrev().qualification_worlds()
    out = {k: (lambda v=v: v) for k, v in worlds.items() if k.startswith(("G2_", "W37", "S825"))}
    raw = study.tissue_definition(dt=1e-3, end_time=0.2, observation_times=[0.0, 0.1, 0.2])
    out["S825_resolved_pump_tissue_3"] = lambda: raw
    out["S825_empty"] = lambda: cs.frozen_definition(raw)
    return out


def _w1():
    worlds = _crossrev().qualification_worlds()
    return {k: (lambda v=v: v) for k, v in worlds.items() if k.startswith("W1_")}


def _pump():
    from validation.tissue import surface_pump_fixtures as v1
    from validation.tissue import surface_pump_v2_fixtures as v2

    imex = "imex_ars222_face_electromigration@1"
    return {
        f"{tag}_{arm}_{name}": (
            lambda f=f, arm=arm, solver=solver: f.definition(arm, solver=solver)
        )
        for tag, f in (("v1", v1), ("v2", v2))
        for arm in ("open",)
        for name, solver in (("rk4", "rk4"), ("imex", imex))
    }


def _cohorts():
    from validation.tissue import composite_guard as guard

    cases, qual = guard._g2_cases()
    w7 = [qual.at_dt(cases[n], 1e-3) for n in ("W7/literature", "W7/short_lag")]
    c9 = [qual.at_dt(cases[n], 1e-3) for n in cases if n.startswith("C9/")]
    extra = copy.deepcopy(c9[0])
    end = extra["experiment"]["end_time"]
    extra["experiment"]["replacement_events"][0]["time"] = int(round(0.2 * end / 1e-3)) * 1e-3
    extra2 = copy.deepcopy(c9[3])
    extra2["experiment"]["replacement_events"][0]["time"] = int(round(0.3 * end / 1e-3)) * 1e-3
    c9 += [extra, extra2]
    return {"Q6_2_W7": lambda: w7, "Q6_8_C9": lambda: c9}


PARTS = {
    "dumps": (_dumps, "scalar", False),
    "base": (lambda: {k: (lambda v=v: v) for k, v in _crossrev().worlds().items()}, "scalar", True),
    "injection": (
        lambda: {k: (lambda v=v: v) for k, v in _crossrev().injection_worlds().items()},
        "scalar",
        True,
    ),
    "egg": (_egg, "scalar-recorded", False),
    "qualification": (_qualification, "scalar", True),
    "w1": (_w1, "windowed", False),
    "pump": (_pump, "scalar", True),
    "cohorts": (_cohorts, "cohort", False),
}


def _device_rows(spec, result, chunk=512):
    """The device row checks of every accepted row: failure flags and values."""
    import jax
    import jax.numpy as jnp

    from cells.models.registry import get_model

    model = get_model(spec.model)
    if not hasattr(model, "device_checks"):
        return {}
    p = jax.tree.map(jnp.asarray, model.initial_values(spec)[1])
    constants = model.device_check_constants(spec)
    check = jax.jit(
        jax.vmap(lambda a, b, s, m=model, p=p, c=constants: m.device_checks(a, b, p, c, s))
    )
    h, n = result.history, len(result.times)
    bits, values = [], []
    for start in range(1, n, chunk):
        stop = min(n, start + chunk)
        prev = jax.tree.map(lambda v, a=start, b=stop: jnp.asarray(np.asarray(v)[a - 1 : b - 1]), h)
        rows = jax.tree.map(lambda v, a=start, b=stop: jnp.asarray(np.asarray(v)[a:b]), h)
        f, v = check(prev, rows, jnp.arange(start, stop) + result.start_step)
        bits.append(np.asarray(f))
        values.append(np.asarray(v))
    if not bits:
        return {}
    return {"device.failed": np.concatenate(bits), "device.values": np.concatenate(values)}


def _quiet_host_checks():
    """Record-only host checks (the egg part): the runner's checks return zeros."""
    from cells.models import pump_composite_adapter as adapter
    from cells.models import surface_pump as first

    def quiet(state, spec, p, *, domain, balances, magnitudes, dissipation, steps=None):
        keys = (*("max_" + k for k in first.LEDGER_DIAGNOSTICS), "max_energy_balance_relative")
        return {**dict.fromkeys(keys, 0.0), "max_global_charge_bound_ratio": 0.0}

    first.checked_rows = quiet
    adapter.checked_rows = quiet


def _electrode_ledger(spec, result):
    """Host electrode ledger of every row (transferred - held plate charges), recomputed."""
    from cells.models import pump_composite_adapter as adapter
    from cells.models import surface_tissue as tissue
    from cells.models.registry import get_model

    model = get_model(spec.model)
    layout = model.initial_values(spec)[1]
    bound = adapter.inner_layout(layout) if hasattr(model, "inner_state") else layout
    inner = model.inner_state if hasattr(model, "inner_state") else (lambda s: s)
    h, n = result.history, bound.active.size
    out = []
    for r in range(len(result.times)):
        row = type(h)(*(np.asarray(v[r]) for v in h))
        _, cap, _ = tissue.capacitor_change(inner(row), bound, xp=np)
        out.append(row.electrode_charge_transferred_C - np.where(bound.reservoir, cap[n:], 0.0))
    return np.asarray(out)


def _scalar(name, raw, out, *, device, recorded=False):
    from cells.core.runner import run
    from cells.core.specs import parse_spec

    spec = parse_spec(raw)
    started = time.perf_counter()
    result = run(spec)
    wall = time.perf_counter() - started
    arrays = {"times": np.asarray(result.times)}
    for key in type(result.history)._fields:
        arrays["history." + key] = np.asarray(getattr(result.history, key))
    for key, value in vars(result.observations).items():
        arrays["observations." + key] = np.asarray(value)
    if device:
        arrays.update(_device_rows(spec, result))
    if recorded:
        arrays["host.electrode_ledger_C"] = _electrode_ledger(spec, result)
    np.savez_compressed(out / f"{name}.npz", **arrays)
    return dict(
        program="scalar",
        model=raw["model"]["id"],
        rows=len(result.times),
        diagnostics={k: v for k, v in result.diagnostics.items() if k.startswith("max_")},
        timings={k: float(v) for k, v in result.timings.items()},
        wall_s=wall,
        steps=len(result.times) - 1,
    )


def _windowed(name, raw, out, window_steps=4000):
    from cells.core.specs import parse_spec
    from cells.core.windows import WindowPolicy, run_windowed

    spec = parse_spec(raw)
    seen = []
    started = time.perf_counter()
    result = run_windowed(spec, WindowPolicy(window_steps, "observations"), sink=seen.append)
    wall = time.perf_counter() - started
    arrays = {}
    for k, window in enumerate(seen):
        for key, value in vars(window.observations).items():
            arrays[f"window{k}.observations.{key}"] = np.asarray(value)
    for key in type(result.final.state)._fields:
        arrays["final." + key] = np.asarray(getattr(result.final.state, key))
    np.savez_compressed(out / f"{name}.npz", **arrays)
    return dict(
        program="windowed",
        model=raw["model"]["id"],
        windows=len(seen),
        diagnostics={k: v for k, v in result.diagnostics.items() if k.startswith("max_")},
        timings={k: float(v) for k, v in result.timings.items()},
        wall_s=wall,
    )


def _cohort(name, raws, out):
    from cells.core.batch import BatchSpec, WorldSpec, run_batch
    from cells.core.specs import parse_spec
    from cells.core.vector_windows import run_vector_windowed
    from cells.core.windows import WindowPolicy

    specs = [parse_spec(copy.deepcopy(r)) for r in raws]
    cohort = BatchSpec(
        tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs)), len(specs), 10**8, 2**33
    )
    arrays, record = {}, dict(program="cohort", worlds=len(specs), diagnostics={}, wall_s={})
    started = time.perf_counter()
    vector = run_vector_windowed(cohort, WindowPolicy(1000, "checkpoints"))
    record["wall_s"]["vector"] = time.perf_counter() - started
    started = time.perf_counter()
    batch = run_batch(cohort)
    record["wall_s"]["batch"] = time.perf_counter() - started
    for label, result in (("vector", vector), ("batch", batch)):
        for w, world in result.worlds.items():
            for key in type(world.final.state)._fields:
                arrays[f"{label}.world{w}.final.{key}"] = np.asarray(
                    getattr(world.final.state, key)
                )
            if label == "batch":
                for key in type(world.history)._fields:
                    arrays[f"batch.world{w}.history.{key}"] = np.asarray(
                        getattr(world.history, key)
                    )
            record["diagnostics"][f"{label}.world{w}"] = {
                k: v for k, v in world.diagnostics.items() if k.startswith("max_")
            }
    np.savez_compressed(out / f"{name}.npz", **arrays)
    return record


def dump(parts, out, names=None):
    import jax

    jax.config.update("jax_enable_x64", True)
    out.mkdir(parents=True, exist_ok=True)
    for part in parts:
        build, program, device = PARTS[part]
        if program == "scalar-recorded":
            _quiet_host_checks()
        for name, make in build().items():
            if names and name not in names:
                continue
            if (out / f"{name}.json").exists():
                continue  # Resumable.
            try:
                if program in ("scalar", "scalar-recorded"):
                    record = _scalar(
                        name, make(), out, device=device, recorded=program == "scalar-recorded"
                    )
                elif program == "windowed":
                    record = _windowed(name, make(), out)
                else:
                    record = _cohort(name, make(), out)
                record.update(world=name, part=part)
                (out / f"{name}.json").write_text(
                    json.dumps(record, indent=1, default=float) + "\n"
                )
                print(part, name, round(float(np.sum(list(_seconds(record)))), 1), "s", flush=True)
            except Exception as error:  # A refusal is evidence: record it.
                (out / f"{name}-failure.json").write_text(
                    json.dumps(
                        dict(
                            world=name,
                            part=part,
                            error=repr(error),
                            traceback=traceback.format_exc(),
                        )
                    )
                )
                print(part, name, "FAILED", repr(error), flush=True, file=sys.stderr)


def _seconds(record):
    wall = record.get("wall_s", 0.0)
    return wall.values() if isinstance(wall, dict) else [wall]


def _field(key):
    """The state field an array key names, or None for observations and other arrays."""
    for marker in (".history.", ".final.", "history.", "final."):
        if marker in key:
            return key.split(marker, 1)[1]
    return None


def compare(before, after):
    """Every difference of two saved sets, classified as physical or ledger, per world."""
    report = {}
    for path in sorted(Path(before).glob("*.json")):
        if path.stem.endswith("-failure"):
            continue
        name, other = path.stem, Path(after) / path.name
        if not other.exists():
            failure = Path(after) / f"{path.stem}-failure.json"
            report[name] = dict(missing=True, after_failed=failure.exists())
            continue
        a, b = json.loads(path.read_text()), json.loads(other.read_text())
        x, y = np.load(Path(before) / f"{name}.npz"), np.load(Path(after) / f"{name}.npz")
        physical, ledger = [], {}
        for key in sorted(set(x.files) | set(y.files)):
            if key not in x.files or key not in y.files:
                physical.append(dict(array=key, kind="missing on one side"))
                continue
            u, v = x[key], y[key]
            if u.shape != v.shape or u.dtype != v.dtype:
                physical.append(dict(array=key, kind="shape or dtype"))
                continue
            if u.tobytes() == v.tobytes():
                continue
            field = _field(key)
            is_ledger = (field in LEDGER_FIELDS) or key in (
                "device.values",
                "host.electrode_ledger_C",
            )
            if is_ledger:
                d = np.abs(u.astype(float) - v.astype(float))
                ledger[key] = dict(
                    max_abs_difference=float(np.nanmax(d)),
                    max_abs_value=float(np.nanmax(np.abs(np.r_[u.ravel(), v.ravel()]))),
                )
            else:
                same = u == v
                if u.dtype.kind == "f":
                    same |= np.isnan(u) & np.isnan(v)
                where = np.argwhere(~same)
                index = [int(i) for i in where[0]] if len(where) else []
                physical.append(
                    dict(
                        array=key,
                        kind="value" if len(where) else "bits (signed zero or NaN payload)",
                        index=index,
                        differing=int(len(where)),
                    )
                )
        diagnostics = {"ledger": {}, "physical": {}}
        da, db = a.get("diagnostics", {}), b.get("diagnostics", {})
        flat_a = _flatten(da)
        flat_b = _flatten(db)
        for key in sorted(set(flat_a) | set(flat_b)):
            if flat_a.get(key) != flat_b.get(key):
                group = "ledger" if ledger_diagnostic(key.rsplit(".", 1)[-1]) else "physical"
                diagnostics[group][key] = [flat_a.get(key), flat_b.get(key)]
        report[name] = dict(
            part=a.get("part"),
            physical_identical=not physical and not diagnostics["physical"],
            physical=physical,
            ledger=ledger,
            diagnostics=diagnostics,
            seconds=dict(before=list(_seconds(a)), after=list(_seconds(b))),
            timings=dict(before=a.get("timings"), after=b.get("timings")),
        )
    for path in sorted(Path(before).glob("*-failure.json")):
        name = path.stem[: -len("-failure")]
        report[name] = dict(
            before_failed=True,
            after_failed=(Path(after) / path.name).exists(),
            physical_identical=None,
        )
    return report


def _flatten(diagnostics):
    out = {}
    for key, value in diagnostics.items():
        if isinstance(value, dict):
            out.update({f"{key}.{k}": v for k, v in value.items()})
        else:
            out[key] = value
    return out


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("dump", "compare"))
    parser.add_argument("args", nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worlds", type=lambda s: s.split(","), default=None)
    args = parser.parse_args(argv)
    if args.action == "dump":
        parts = args.args[0].split(",")
        unknown = [p for p in parts if p not in PARTS]
        if unknown:
            raise SystemExit(f"unknown parts {unknown}; parts are {sorted(PARTS)}")
        dump(parts, args.output, args.worlds)
        return
    report = compare(*args.args)
    worlds = [r for r in report.values() if r.get("physical_identical") is not None]
    violations = sorted(k for k, r in report.items() if r.get("physical_identical") is False)
    verdict = "physical identical" if worlds and not violations else "physical differs"
    summary = dict(verdict=verdict, worlds=len(report), violations=violations, report=report)
    args.output.write_text(json.dumps(summary, indent=1, default=float) + "\n")
    print(verdict, len(worlds), "compared;", len(violations), "with physical differences")


if __name__ == "__main__":
    main()
