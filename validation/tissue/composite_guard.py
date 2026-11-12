"""Bitwise guards of resolved_pump_composite@1 against the frozen models (D143, design §3.7).

compare_runs(reference, result) compares two runner results field by field, as
the frozen models' own equivalence tests do (np.array_equal on every state field,
observation column and max_ diagnostic), and reports the first differing field,
row and index, plus whether the bit patterns are identical too (signed zeros).
The detached qualification-world guards (main) run each frozen definition and
its composite form (core/pump_composite_spec.frozen_definition) and write one
result or failure JSON per world.

Usage: python -m validation.tissue.composite_guard PART --output DIR [--worlds NAME,...]
"""

import numpy as np


def _first(a, b):
    """(row, index, a value, b value) of the first entry where a and b differ."""
    a, b = np.asarray(a), np.asarray(b)
    same = a == b
    if a.dtype.kind == "f":
        same |= np.isnan(a) & np.isnan(b)
    where = np.argwhere(~same)
    if not len(where):
        return None
    index = tuple(int(i) for i in where[0])
    return dict(index=list(index), reference=a[index].item(), value=b[index].item())


def compare_arrays(name, a, b):
    """None when equal (np.array_equal, NaN-aware), else the first difference."""
    a, b = np.asarray(a), np.asarray(b)
    if a.shape != b.shape or a.dtype != b.dtype:
        return dict(
            field=name,
            kind="shape or dtype",
            reference=[list(a.shape), str(a.dtype)],
            value=[list(b.shape), str(b.dtype)],
        )
    if a.dtype.kind == "f":
        equal = np.array_equal(a, b, equal_nan=True)
    else:
        equal = np.array_equal(a, b)
    if equal:
        return None
    return dict(field=name, kind="value", **_first(a, b))


def bit_identical(a, b):
    a, b = np.asarray(a), np.asarray(b)
    return a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes()


def compare_runs(reference, result, *, history_fields=None, observation_fields=None):
    """Compare two runner results; returns dict(equal, bitwise, first, compared).

    history_fields: the frozen model's state fields (default: all of the
    reference's); observation_fields likewise. Each must exist in the result
    under the same name. first is the first difference in the order times,
    history, observations, diagnostics.
    """
    differences, bits = [], True
    if not np.array_equal(np.asarray(reference.times), np.asarray(result.times)):
        differences.append(dict(field="times", kind="value"))
    fields = history_fields or type(reference.history)._fields
    for name in fields:
        a, b = getattr(reference.history, name), getattr(result.history, name, None)
        if b is None:
            differences.append(dict(field="history." + name, kind="missing"))
            continue
        d = compare_arrays("history." + name, a, b)
        if d is not None:
            differences.append(d)
        bits &= bit_identical(a, b)
    columns = observation_fields or tuple(vars(reference.observations))
    for name in columns:
        a = getattr(reference.observations, name)
        b = getattr(result.observations, name, None)
        if b is None:
            differences.append(dict(field="observations." + name, kind="missing"))
            continue
        d = compare_arrays("observations." + name, a, b)
        if d is not None:
            differences.append(d)
        bits &= bit_identical(a, b)
    for key, value in reference.diagnostics.items():
        if not key.startswith("max_"):
            continue
        other = result.diagnostics.get(key)
        if other != value:
            differences.append(
                dict(field="diagnostics." + key, kind="value", reference=value, value=other)
            )
    return dict(
        equal=not differences,
        bitwise=not differences and bits,
        first=differences[0] if differences else None,
        differences=len(differences),
        compared=dict(
            history=len(fields), observations=len(columns), rows=int(len(reference.times))
        ),
    )


def assert_same(reference, result, **kw):
    report = compare_runs(reference, result, **kw)
    assert report["equal"], report["first"]
    return report


# ---------------------------------------------------------------- qualification worlds


def _paths():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "validation" / "tissue"
    return dict(
        w1=root / "pump_water_predictions.json",
        w2=root / "pump_water_kcc_predictions.json",
        g2=root / "cell_replacement_q1_predictions.json",
    )


def _load(name):
    import json

    return json.loads(_paths()[name].read_text())


def pair_specs(raw):
    from cells.core import pump_composite_spec as cs
    from cells.core.specs import parse_spec

    return parse_spec(raw), parse_spec(cs.frozen_definition(raw))


def runner_pair(raw):
    """Frozen and composite runs through core/runner.run (host checks on every row)."""
    import time

    from cells.core.runner import run

    frozen, composite = pair_specs(raw)
    started = time.perf_counter()
    a = run(frozen)
    middle = time.perf_counter()
    b = run(composite)
    report = compare_runs(a, b)
    report["seconds"] = dict(frozen=middle - started, composite=time.perf_counter() - middle)
    return report, (frozen, a), (composite, b)


def windowed_pair(raw, window_steps=4000):
    """Frozen and composite runs through core/windows.run_windowed (observations policy)."""
    import time

    from cells.core.windows import WindowPolicy, run_windowed

    out = []
    for spec in pair_specs(raw):
        seen = []
        started = time.perf_counter()
        result = run_windowed(spec, WindowPolicy(window_steps, "observations"), sink=seen.append)
        out.append((spec, result, seen, time.perf_counter() - started))
    (_, a, wa, sa), (_, b, wb, sb) = out
    differences = []
    names = tuple(vars(wa[0].observations)) if wa else ()
    for k, (x, y) in enumerate(zip(wa, wb, strict=True)):
        for name in names:
            d = compare_arrays(
                f"window {k}.observations.{name}",
                getattr(x.observations, name),
                getattr(y.observations, name),
            )
            if d is not None:
                differences.append(d)
    for name in type(a.final.state)._fields:
        d = compare_arrays(
            "final." + name, getattr(a.final.state, name), getattr(b.final.state, name)
        )
        if d is not None:
            differences.append(d)
    for key, value in a.diagnostics.items():
        if key.startswith("max_") and b.diagnostics.get(key) != value:
            differences.append(
                dict(field="diagnostics." + key, reference=value, value=b.diagnostics.get(key))
            )
    return dict(
        equal=not differences,
        first=differences[0] if differences else None,
        differences=len(differences),
        windows=len(wa),
        observation_columns=len(names),
        seconds=dict(frozen=sa, composite=sb),
    )


_EVALUATORS = {}


def _evaluators(model, steps):
    """rhs, its state Jacobian and the k-step map of a model, compiled once per model.

    The control, layout and step are arguments, so worlds of one shape share the
    compiled functions (a model object is kept in the key's value, so its id is not
    reused while cached).
    """
    import jax
    import jax.numpy as jnp

    key = (id(model), steps)
    if key not in _EVALUATORS:

        def rhs(s, control, p):
            return model.rhs(s, control, p, p.active)

        def step_map(s, control, p, dt):
            def body(carry, _):
                moved, ok = model.checked_step(carry[0], dt, control, p, p.active)
                return (moved, carry[1] & ok), None

            (final, ok), _ = jax.lax.scan(body, (s, jnp.asarray(True)), None, length=steps)
            return final, ok

        _EVALUATORS[key] = (
            model,
            (jax.jit(rhs), jax.jit(jax.jacfwd(rhs)), jax.jit(step_map)),
        )
    return _EVALUATORS[key][1]


def evaluation_pair(raw, states, *, steps=4):
    """rhs, its state Jacobian and the k-step map, frozen and composite, at given states.

    states: frozen-model state NamedTuples (numpy). The stationary analyses
    (stationary_continuation_analysis@1) evaluate exactly these functions, so
    bitwise agreement here makes their Newton solutions identical.
    """
    import jax
    import jax.numpy as jnp

    from cells.core.schedule import control_values
    from cells.models.registry import get_model

    frozen, composite = pair_specs(raw)
    out = []
    functions = []
    for spec in (frozen, composite):
        model = get_model(spec.model)
        _, p = model.initial_values(spec)
        controls = control_values(spec, [0.0])
        control = type(controls)(*(jnp.asarray(v[0]) for v in controls))
        p = jax.tree.map(jnp.asarray, p)
        dt = jnp.asarray(spec.execution.dt)
        functions.append((model, *_evaluators(model, steps), control, p, dt))
    for label, state in states.items():
        values = []
        for model, rhs, jac, step_map, control, p, dt in functions:
            s = model.STATE_TYPE(
                *(jnp.asarray(getattr(state, k)) for k in model.STATE_TYPE._fields)
            )
            values.append((rhs(s, control, p), jac(s, control, p), step_map(s, control, p, dt)))
        (r0, j0, m0), (r1, j1, m1) = values
        differences = []
        for name in type(r0)._fields:
            d = compare_arrays("rhs." + name, getattr(r0, name), getattr(r1, name))
            if d is not None:
                differences.append(d)
            d = compare_arrays("step_map." + name, getattr(m0[0], name), getattr(m1[0], name))
            if d is not None:
                differences.append(d)
            for wrt in type(r0)._fields:
                d = compare_arrays(
                    f"jacobian.{name}.{wrt}",
                    getattr(getattr(j0, name), wrt),
                    getattr(getattr(j1, name), wrt),
                )
                if d is not None:
                    differences.append(d)
        if bool(m0[1]) != bool(m1[1]):
            differences.append(
                dict(field="step_map.valid", reference=bool(m0[1]), value=bool(m1[1]))
            )
        out.append(
            dict(
                state=label,
                equal=not differences,
                first=differences[0] if differences else None,
                differences=len(differences),
                step_map_valid=bool(m0[1]),
            )
        )
    return out


def device_pair(first, second, chunk=512):
    """Device row checks of every accepted row, frozen and composite: bits and values."""
    import jax
    import jax.numpy as jnp

    from cells.models.registry import get_model

    outputs = []
    for spec, result in (first, second):
        model = get_model(spec.model)
        p = jax.tree.map(jnp.asarray, model.initial_values(spec)[1])
        constants = model.device_check_constants(spec)
        check = jax.jit(
            jax.vmap(lambda a, b, s, m=model, p=p, c=constants: m.device_checks(a, b, p, c, s))
        )
        h, n = result.history, len(result.times)
        bits, values = [], []
        for start in range(1, n, chunk):
            stop = min(n, start + chunk)
            prev = jax.tree.map(
                lambda v, a=start, b=stop: jnp.asarray(np.asarray(v)[a - 1 : b - 1]), h
            )
            rows = jax.tree.map(lambda v, a=start, b=stop: jnp.asarray(np.asarray(v)[a:b]), h)
            f, v = check(prev, rows, jnp.arange(start, stop) + result.start_step)
            bits.append(np.asarray(f))
            values.append(np.asarray(v))
        outputs.append((np.concatenate(bits), np.concatenate(values)))
    (b0, v0), (b1, v1) = outputs
    first_difference = compare_arrays("device.failed", b0, b1) or compare_arrays(
        "device.values", v0, v1
    )
    return dict(
        equal=first_difference is None,
        first=first_difference,
        failing_rows=int(np.count_nonzero(b0.any(axis=1))),
        rows=int(len(b0)),
    )


def _w1_trajectories():
    from validation.tissue import pump_water_qualification as w1q

    predictions = _load("w1")
    return predictions, {
        name: w1q.item(predictions, path)["definition"] for name, path in w1q.TRAJECTORIES.items()
    }


def part_w1(args, record):
    from validation.tissue import pump_water_qualification as w1q

    _, worlds = _w1_trajectories()
    for name, raw in worlds.items():
        if args.worlds and name not in args.worlds:
            continue
        record(name, lambda raw=raw: windowed_pair(w1q.with_step(raw, 1e-3)))


def part_w1_dt(args, record):
    from validation.tissue import pump_water_qualification as w1q

    _, worlds = _w1_trajectories()
    for name, raw in worlds.items():
        if args.worlds and name not in args.worlds:
            continue
        for dt in w1q.STEPS_S:
            if dt == 1e-3:
                continue  # Part w1.
            record(f"{name}@{dt:g}", lambda raw=raw, dt=dt: windowed_pair(w1q.with_step(raw, dt)))


def _w1_states():
    """The P2 stationary guesses (H, U, D) and the frozen Newton solutions."""
    from cells.analysis import stationary as sa
    from cells.core.specs import parse_spec
    from cells.models import surface_pump_v3

    predictions = _load("w1")
    raw = predictions["P2"]["definition"]
    spec = parse_spec(raw)
    pb = sa.problem(spec)
    ids = list(spec.model.species_ids)
    v0 = raw["model"]["cells"][0]["volume_pL"]
    states = {}
    approved = predictions["P2"]["states"]["approved"]
    for label, reference in zip(("H", "U", "D"), approved, strict=False):
        base = sa._numpy(pb.base)
        volume = reference["volume_pL"]
        increment = np.array(base.amount_increment, dtype=float)
        for sid in ("Na", "K", "M"):
            k = ids.index(sid)
            increment[k, 0] = (
                reference["concentration_mM"][sid] * volume - pb.p.amount_reference[k, 0]
            )
        target, _ = surface_pump_v3.channel_kinetics(
            np.full(pb.p.channel_laws.shape, reference["membrane_voltage_V"]),
            np.asarray(pb.p.channel_laws),
            xp=np,
        )
        gate = np.where(np.asarray(pb.p.channel_gate_active), target, base.channel_gate)
        guess = base._replace(
            amount_increment=increment,
            volume_increment_pL=np.array([volume - v0]),
            channel_gate=gate,
        )
        states["guess_" + label] = guess
        solution = sa.newton(pb, pb.coordinates(guess))
        if solution.converged:
            states["solution_" + label] = sa._numpy(pb.embed(solution.u)[0])
    return raw, states


def part_w1_stationary(args, record):
    raw, states = _w1_states()
    record("P2_stationary", lambda: dict(points=evaluation_pair(raw, states)))


def part_w1_drift(args, record):
    """A shortened W1 drift: the P2 cell from the frozen stationary H state (60 s at 1 ms)."""
    from validation.tissue import pump_water_qualification as w1q

    predictions = _load("w1")
    records = w1q.stationary_phase(predictions)
    start = next(r for r in records if r["label"] == "H" and r["converged"])
    raw = w1q.stationary_definition(predictions, start, 60.0 / 3600.0, interval_s=10.0)
    record("P2_drift_H_60s", lambda: windowed_pair(w1q.with_step(raw, 1e-3), window_steps=20000))


def _w2_arm_states(predictions, arm):
    from cells.analysis import stationary as sa
    from cells.core.specs import parse_spec
    from validation.tissue import pump_water_kcc_qualification as w2q

    raw = w2q.definition(predictions, arm)
    pb = sa.problem(parse_spec(raw))
    states = {}
    for reference in predictions["arms"][arm]["states"]:
        if not reference["converged"]:
            continue
        label = f"branch_{reference['branch']}"  # Branches are numbered.
        guess = w2q.guess(pb, reference)
        states["guess_" + label] = sa._numpy(pb.embed(guess)[0])
        solution = sa.newton(pb, guess)
        if solution.converged:
            states["solution_" + label] = sa._numpy(pb.embed(solution.u)[0])
    return raw, states


def part_w2(args, record):
    import copy

    predictions = _load("w2")
    for arm in predictions["arms"]:
        if args.worlds and arm not in args.worlds:
            continue

        def evaluate(arm=arm):
            raw, states = _w2_arm_states(predictions, arm)
            trajectory = copy.deepcopy(raw)
            trajectory["experiment"]["end_time"] = 1.0
            trajectory["experiment"]["observation_times"] = [0.0, 0.5, 1.0]
            trajectory["execution"]["max_steps"] = 2000
            report = runner_pair(trajectory)[0]
            return dict(points=evaluation_pair(raw, states), trajectory_1s=report)

        record(arm, evaluate)


def _g2_cases():
    from validation.tissue import cell_replacement_qualification as qual

    predictions = _load("g2")
    return {name: entry["definition"] for name, entry in predictions["cases"].items()}, qual


def part_g2(args, record):
    cases, qual = _g2_cases()
    for name, raw in cases.items():
        if args.worlds and name not in args.worlds:
            continue

        def evaluate(raw=raw):
            report, first, second = runner_pair(qual.at_dt(raw, 1e-3))
            report["device"] = device_pair(first, second)
            return report

        record(name, evaluate)


def part_g2_order(args, record):
    from validation.tissue import cell_replacement_judge as judge

    cases, qual = _g2_cases()
    for name in judge.Q5_CASES:
        for dt in judge.Q5_DTS:
            record(
                f"{name}@{dt:g}",
                lambda raw=cases[name], dt=dt: runner_pair(qual.at_dt(raw, dt))[0],
            )


def part_g2_vmap(args, record):
    import copy

    from cells.core import pump_composite_spec as cs
    from cells.core.batch import BatchSpec, WorldSpec
    from cells.core.specs import parse_spec
    from cells.core.vector_windows import run_vector_windowed
    from cells.core.windows import WindowPolicy

    cases, qual = _g2_cases()
    w7 = [qual.at_dt(cases[n], 1e-3) for n in ("W7/literature", "W7/short_lag")]
    c9 = [qual.at_dt(cases[n], 1e-3) for n in cases if n.startswith("C9/")]
    extra = copy.deepcopy(c9[0])
    end = extra["experiment"]["end_time"]
    extra["experiment"]["replacement_events"][0]["time"] = int(round(0.2 * end / 1e-3)) * 1e-3
    extra2 = copy.deepcopy(c9[3])
    extra2["experiment"]["replacement_events"][0]["time"] = int(round(0.3 * end / 1e-3)) * 1e-3
    c9 += [extra, extra2]
    for label, raws in (("2_W7", w7), ("8_C9", c9)):

        def evaluate(raws=raws):
            results = []
            for convert in (copy.deepcopy, cs.frozen_definition):
                specs = [parse_spec(convert(r)) for r in raws]
                cohort = BatchSpec(
                    tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs)),
                    len(specs),
                    10**8,
                    2**33,
                )
                results.append(run_vector_windowed(cohort, WindowPolicy(1000, "checkpoints")))
            differences = []
            for w in results[0].worlds:
                x, y = results[0].worlds[w].final.state, results[1].worlds[w].final.state
                for key in type(x)._fields:
                    d = compare_arrays(f"world {w}.{key}", getattr(x, key), getattr(y, key))
                    if d is not None:
                        differences.append(d)
                for key, value in results[0].worlds[w].diagnostics.items():
                    other = results[1].worlds[w].diagnostics.get(key)
                    if key.startswith("max_") and other != value:
                        differences.append(dict(field=f"world {w}.diagnostics.{key}"))
            return dict(
                equal=not differences,
                first=differences[0] if differences else None,
                worlds=len(raws),
            )

        record(label, evaluate)


def part_w37(args, record):
    from cells.core.cell_replacement_spec import exact_event_times
    from validation.stationary import worlds
    from validation.tissue import cell_replacement_fixtures as fx
    from validation.tissue import cell_replacement_judge as judge
    from validation.tissue import cell_replacement_qualification as qual

    registered = judge.REGISTERED
    raw = fx.heredity_sheet(6, 3, scale=0.3, dt=1e-3, end_time=3.0)
    raw["experiment"]["observation_times"] = [0.0, 3.0]
    raw["model"]["junction_heat_booking"] = qual.BOOKING
    cells, _ = worlds.hexagon(6)
    rings = [worlds.ring(c) for c in cells]
    rims = [i for i, r in enumerate(rings) if r == 3]
    inners = [i for i, r in enumerate(rings) if r == 1]
    slots = [*(rims[k] for k in registered["w37_rim"]), inners[registered["w37_inner"]]]
    h = next(i for i, r in enumerate(rings) if r == 6)
    (t,) = exact_event_times((registered["w37_step"],), 1e-3)
    template = fx.template_from_cell(raw, f"cell_{h}", "h")
    events = [(t, f"cell_{i}", "h", f"n{i}") for i in slots]
    raw = fx.with_replacement(raw, [template], events)

    def evaluate():
        report, first, second = runner_pair(raw)
        report["device"] = device_pair(first, second)
        return report

    record("W37", evaluate)


def part_scale(args, record):
    """The 825-node world (200 steps): empty, closed-water and event-free compositions."""
    from cells.core import pump_composite_spec as cs
    from cells.core.runner import run
    from cells.core.specs import parse_spec
    from validation.tissue import cell_replacement_fixtures as fx
    from validation.tissue import pump_water_fixtures as wfx
    from validation.tissue import surface_pump_v3_study as study

    raw = study.tissue_definition(dt=1e-3, end_time=0.2, observation_times=[0.0, 0.1, 0.2])
    cache = {}

    def reference():
        if "inner" not in cache:
            cache["inner"] = run(parse_spec(raw))
        return cache["inner"]

    def against_inner(composite_raw):
        result = run(parse_spec(composite_raw))
        return compare_runs(reference(), result, history_fields=type(reference().history)._fields)

    closed = wfx.with_water(raw, availability=0.0)
    idle = fx.with_replacement(raw)
    record("empty_vs_resolved_pump_tissue_3", lambda: against_inner(cs.frozen_definition(raw)))
    record(
        "closed_water_vs_resolved_pump_tissue_3",
        lambda: against_inner(cs.frozen_definition(closed)),
    )
    record("closed_water_vs_resolved_pump_water_1", lambda: runner_pair(closed)[0])
    record(
        "event_free_vs_resolved_pump_tissue_3", lambda: against_inner(cs.frozen_definition(idle))
    )
    record("event_free_vs_resolved_pump_replacement_1", lambda: runner_pair(idle)[0])


PARTS = {
    "w1": part_w1,
    "w1-dt": part_w1_dt,
    "w1-stationary": part_w1_stationary,
    "w1-drift": part_w1_drift,
    "w2": part_w2,
    "g2": part_g2,
    "g2-order": part_g2_order,
    "g2-vmap": part_g2_vmap,
    "w37": part_w37,
    "scale": part_scale,
}


def _provenance():
    import json
    import os
    import platform
    import subprocess
    import sys
    import time
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    common = dict(
        argv=sys.argv,
        host=platform.node(),
        cpus=sorted(os.sched_getaffinity(0)),
        root=str(root),
        utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    snapshot = root / "SNAPSHOT.json"
    if snapshot.is_file():  # An execution snapshot (validation/source_snapshot.py).
        record = json.loads(snapshot.read_text())
        return common | dict(
            revision=record["git_revision"],
            patch_sha256=record["patch_sha256"],
            dirty=bool(record["selected_status_porcelain_v1_z"]),
        )
    command = ["git", "-C", str(root)]

    def output(*args):
        return subprocess.run([*command, *args], capture_output=True, text=True).stdout.strip()

    return common | dict(
        revision=output("rev-parse", "HEAD"),
        dirty=output("status", "--porcelain", "--untracked-files=no"),
    )


def main(argv=None):
    import argparse
    import json
    import time
    import traceback
    from pathlib import Path

    import jax

    jax.config.update("jax_enable_x64", True)
    parser = argparse.ArgumentParser()
    parser.add_argument("part", choices=sorted(PARTS))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worlds", type=lambda s: s.split(","), default=None)
    args = parser.parse_args(argv)
    out = args.output / args.part
    out.mkdir(parents=True, exist_ok=False)
    summary = dict(part=args.part, provenance=_provenance(), worlds={})

    def record(name, evaluate):
        safe = name.replace("/", "_")
        started = time.perf_counter()
        try:
            result = evaluate()
            result = dict(world=name, wall_s=time.perf_counter() - started, **result)
            path = out / f"{safe}.json"
            equal = result.get("equal")
            if equal is None and "points" in result:
                equal = all(p["equal"] for p in result["points"]) and result.get(
                    "trajectory_1s", {}
                ).get("equal", True)
            summary["worlds"][name] = dict(equal=bool(equal), file=path.name)
        except Exception as error:  # A refusal or crash is evidence: record it.
            result = dict(
                world=name,
                wall_s=time.perf_counter() - started,
                error=repr(error),
                traceback=traceback.format_exc()[-6000:],
            )
            path = out / f"{safe}-failure.json"
            summary["worlds"][name] = dict(equal=False, failure=path.name)
        path.write_text(json.dumps(result, indent=1, default=float) + "\n")
        (out / "summary.json").write_text(json.dumps(summary, indent=1, default=float) + "\n")
        print(
            name, summary["worlds"][name], round(time.perf_counter() - started, 1), "s", flush=True
        )

    PARTS[args.part](args, record)
    worlds = summary["worlds"].values()
    summary["verdict"] = "equal" if worlds and all(w["equal"] for w in worlds) else "differs"
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=float) + "\n")
    print("verdict", summary["verdict"], flush=True)


if __name__ == "__main__":
    main()
