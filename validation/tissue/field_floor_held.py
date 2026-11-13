"""A field solve held just under version 3's floor cap (guard 6's extra case).

Field solver version 3 (surface_field.FLOOR_SOLVER_ID) also accepts a solve whose current
residual is within CURRENT_FLOOR_ULPS ulps of its potentials
(docs/FIELD_FLOOR_ACCEPTANCE_DESIGN.md). On the W1 hold's 825-node tissue that cap is far
above NEWTON_TARGET, so version 3 loosens
acceptance that far. held_solves() replaces surface_field.solve during a host-path (NumPy)
run. Each solve finds its root as usual, then moves the floating offsets along a direction
until the residual reaches `fraction` of the cap, located by bisection against the solve's
own acceptance test. It returns the solve's values there, with no Newton iteration from that
offset. The run's row checks (the model's check_values and device_checks) and ledger margins
then show whether a solve accepted at the cap keeps the records sound.

Directions: "uniform" moves every free offset alike; "largest" moves only the free component
with the largest incident face current.

Usage (evidence on a saved world, CPU):
  python -m validation.tissue.field_floor_held OUT.json --definition SPEC.json [--state STATE.npz]
      [--warm STEPS] [--steps N] [--fraction F] [--direction uniform|largest]
  python -m validation.tissue.field_floor_held OUT.json --study [...]   (the 825-node study world)
SPEC.json is a definition or a snapshot manifest (its "spec"); it is declared version 3 here.
"""

import contextlib
import json

import numpy as np

from cells.numerics import surface_field as field

DIRECTIONS = ("uniform", "largest")


def at(arguments, layout, offset, floor=None):
    """surface_field.solve's values at a given offset, with no Newton iteration from it.

    floor: another current_floor (ulps) for the acceptance test, else the layout's.
    """
    if floor is not None:
        layout = layout._replace(current_floor=np.asarray(float(floor)))
    original = field._offset_solve
    field._offset_solve = lambda *a, **k: np.array(offset, copy=True)  # The initial offset.
    try:
        return _SOLVE[0](*arguments, layout, xp=np, max_iterations=0)
    finally:
        field._offset_solve = original


def root(arguments, layout):
    """(values, offset, exact): the solve's root and its offset, rebuilt from its own steps.

    The offset is the solve's initial offset plus each Newton step (the loop's first trial);
    exact is whether at() reproduces the root's potentials bitwise from it.
    """
    seen, original = [], field._offset_solve

    def record(*a, **k):
        result = original(*a, **k)
        seen.append(np.array(result, copy=True))
        return result

    field._offset_solve = record
    try:
        values = _SOLVE[0](*arguments, layout, xp=np)
    finally:
        field._offset_solve = original
    offset = seen[0]
    for delta in seen[1:]:
        offset = offset + delta
    exact = np.array_equal(at(arguments, layout, offset).potential_V, values.potential_V)
    return values, offset, exact


def direction(arguments, layout, offset, kind):
    free = np.where(layout.offset_free, 1.0, 0.0)
    if kind == "uniform":
        return free
    if kind != "largest":
        raise ValueError(f"Unknown direction {kind!r} (uniform or largest)")
    current = np.abs(at(arguments, layout, offset).rates.face_current_A)
    incident = np.abs(layout.face_incidence) @ current
    out = np.zeros_like(free)
    out[int(np.argmax(np.where(layout.offset_free, incident, -np.inf)))] = 1.0
    return out


_SOLVE = [field.solve]  # The engine's solve, kept while held_solves() replaces it.


@contextlib.contextmanager
def held_solves(fraction=0.95, kind="uniform", records=None):
    """Replace surface_field.solve (host path) by roots moved to `fraction` of the cap.

    records: a list that receives one dict per solve. A solve that does not converge, has no
    free offset, or whose root offset cannot be rebuilt exactly is returned unchanged.
    """
    records = [] if records is None else records

    def solve(*arguments, xp=np, max_iterations=16, max_backtracks=12):
        *arguments, layout = arguments
        values, offset, exact = root(arguments, layout)
        if not (bool(values.converged) and np.any(layout.offset_free) and exact):
            records.append(dict(held=False, converged=bool(values.converged), exact=exact))
            return values
        d = direction(arguments, layout, offset, kind)

        def accepted(shift):
            return bool(at(arguments, layout, offset + shift * d).converged)

        low, high = 0.0, 1e-24
        for _ in range(200):  # Bracket the cap: 1e-24 V doubled up to 1e36 V.
            if not accepted(high):
                break
            low, high = high, 2.0 * high
        else:
            raise RuntimeError("No refusal along the direction: the cap is not bracketed")
        # Acceptance along a direction need not be one interval (each |R_k| is V-shaped in
        # the shift). Bisect, then look for a refusal inside [0, low] and bisect again below
        # it, so low is the first boundary seen from the root.
        for _ in range(20):
            for _ in range(60):
                middle = 0.5 * (low + high)
                low, high = (middle, high) if accepted(middle) else (low, middle)
            inside = [j for j in range(1, 8) if not accepted(low * j / 8)]
            if not inside:
                break
            low, high = low * (inside[0] - 1) / 8, low * inside[0] / 8
        used = fraction
        while used > 1e-3 and not accepted(used * low):
            used *= 0.8  # A refused gap finer than the scan: back off toward the root.
        moved = offset + used * low * d
        result = at(arguments, layout, moved)
        records.append(
            dict(
                held=True,
                shift_V=used * low,
                fraction_used=used,
                converged=bool(result.converged),
                converged_at_0p9_cap=bool(
                    at(arguments, layout, moved, floor=0.9 * float(layout.current_floor)).converged
                ),
                fraction_of_target=float(np.max(result.current_normalized)) / field.NEWTON_TARGET,
                root_fraction_of_target=float(np.max(values.current_normalized))
                / field.NEWTON_TARGET,
            )
        )
        return result

    _SOLVE[0] = field.solve
    field.solve = solve
    try:
        yield records
    finally:
        field.solve = _SOLVE[0]


def host_run(spec, state, steps, *, start_step=0, cap_ulps=None):
    """(history, step validity) of `steps` host-path IMEX steps from state at start_step.

    cap_ulps: another current floor for the layout (a positive control of the checks).
    """
    from cells.core.grid import EventGrid
    from cells.core.schedule import control_values
    from cells.core.state import initialise
    from cells.models.registry import get_model

    model = get_model(spec.model)
    start = initialise(spec)
    p = type(start.layout)(*(np.asarray(v) for v in start.layout))
    if cap_ulps is not None:
        p = p._replace(field_current_floor=np.asarray(float(cap_ulps)))
    times = next(EventGrid(spec).windows(start_step, steps))
    table = control_values(spec, times[:-1])
    state = type(start.state)(*(np.asarray(v) for v in state))
    rows, valid = [state], []
    with np.errstate(all="ignore"):
        for k in range(steps):
            control = type(table)(*(np.asarray(v[k]) for v in table))
            dt = float(times[k + 1] - times[k])
            state, ok = model.imex_step(state, dt, control, p, xp=np)
            valid.append(bool(ok))
            rows.append(state)
    history = type(state)(*(np.stack([getattr(r, f) for r in rows]) for f in state._fields))
    return history, valid


def jitted_run(spec, steps):
    """The state after `steps` jitted checked steps from the definition's start (CPU)."""
    import jax

    from cells.core.grid import EventGrid
    from cells.core.schedule import control_values
    from cells.core.state import initialise
    from cells.models.registry import get_model

    model = get_model(spec.model)
    start = initialise(spec)
    times = next(EventGrid(spec).windows(0, steps))
    table = control_values(spec, times[:-1])
    step, state = jax.jit(model.checked_step), start.state
    for k in range(steps):
        control = type(table)(*(np.asarray(v[k]) for v in table))
        state, ok = step(
            state, float(times[k + 1] - times[k]), control, start.layout, start.layout.active
        )
        if not bool(ok):
            raise RuntimeError(f"The warm-up step {k + 1} was refused")
    return type(state)(*(np.asarray(v) for v in state))


def ledger_ratios(history, spec, *, start_step=0):
    """Largest |ledger| / bound over the rows, per ledger (the host check's own bounds)."""
    from cells.core.state import initialise
    from cells.models import surface_pump as first
    from cells.models.registry import get_model

    model = get_model(spec.model)
    start = initialise(spec)
    p = type(start.layout)(*(np.asarray(v) for v in start.layout))
    tol = np.asarray(spec.execution.material_balance_atol_fmol)
    rtol = first.ENERGY_RTOL[spec.execution.solver]
    worst = {}
    for k in range(len(history.amount_increment)):
        row = type(history)(*(v[k] for v in history))
        _, limits = first.ledger_limits(
            row,
            p,
            tol,
            rtol,
            steps=start_step + k,
            magnitudes=model.channel_magnitudes(row, p, xp=np),
        )
        for (name, value), bound in zip(model.balances(row, p).items(), limits, strict=True):
            ratio = float(np.max(np.abs(value) / bound, initial=0.0))
            worst[name] = max(worst.get(name, 0.0), ratio)
    return worst


def device_failures(history, spec, *, start_step=0):
    """Rows whose device row checks fail (the vectorized runs' per-row checks)."""
    import jax
    import jax.numpy as jnp

    from cells.models.registry import get_model

    model = get_model(spec.model)
    p = jax.tree.map(jnp.asarray, model.initial_values(spec)[1])
    constants = model.device_check_constants(spec)
    check = jax.jit(lambda a, b, s: model.device_checks(a, b, p, constants, s))
    failed = []
    for k in range(1, len(history.amount_increment)):
        previous = type(history)(*(jnp.asarray(v[k - 1]) for v in history))
        row = type(history)(*(jnp.asarray(v[k]) for v in history))
        bits, _ = check(previous, row, start_step + k)
        if bool(np.any(np.asarray(bits))):
            failed.append(k)
    return failed


def differences(a, b):
    """{field: (largest |a - b|, largest |a|)} for every state field that differs."""
    out = {}
    for name in a._fields:
        x, y = np.asarray(getattr(a, name)), np.asarray(getattr(b, name))
        if not np.array_equal(x, y):
            out[name] = (float(np.max(np.abs(x - y))), float(np.max(np.abs(x), initial=0.0)))
    return out


def compare(spec, state, steps, *, start_step=0, fraction=0.95, kind="uniform", cap_ulps=None):
    """The normal and the held host runs from one state: checks, ledgers and differences.

    cap_ulps: hold under another cap (the layout's current floor), a positive control:
    how far a solve must be from its root before a row check or ledger refuses.
    """
    from cells.models.registry import get_model

    model = get_model(spec.model)
    rows = list(range(start_step, start_step + steps + 1))
    out = {}
    histories = {}
    for label in ("normal", "held"):
        context = held_solves(fraction, kind) if label == "held" else contextlib.nullcontext([])
        with context as records:
            history, valid = host_run(
                spec,
                state,
                steps,
                start_step=start_step,
                cap_ulps=cap_ulps if label == "held" else None,
            )
        histories[label] = history
        entry = dict(
            steps_valid=all(valid),
            first_invalid_step=valid.index(False) if False in valid else None,
            all_held=bool(records) and all(r["held"] for r in records),
            solves=list(records),
        )
        try:
            entry["check_values"] = model.check_values(history, spec, steps=rows)
        except Exception as error:  # A refusal is the finding.
            entry["check_values_error"] = repr(error)
        entry["ledger_ratios"] = ledger_ratios(history, spec, start_step=start_step)
        entry["device_failed_rows"] = device_failures(history, spec, start_step=start_step)
        out[label] = entry
    out["state_differences"] = differences(histories["normal"], histories["held"])
    return out


def main(argv=None):
    import argparse
    from pathlib import Path

    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.core.specs import parse_spec

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--definition", type=Path)
    source.add_argument("--study", action="store_true")
    parser.add_argument("--state", type=Path, help="state.npz; its clock is beside it")
    parser.add_argument("--warm", type=int, default=0)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--fraction", type=float, default=0.95)
    parser.add_argument("--direction", choices=DIRECTIONS, action="append")
    parser.add_argument(
        "--cap",
        type=float,
        action="append",
        help="hold under this cap in ulps instead of the layout's (a positive control)",
    )
    args = parser.parse_args(argv)
    if args.study:
        from validation.tissue import surface_pump_v3_study as study

        raw = study.tissue_definition(dt=1e-3, end_time=10.0, observation_times=[0.0, 10.0])
    else:
        raw = json.loads(args.definition.read_text())
        raw = raw.get("spec", raw)
    raw["execution"]["backend"] = "cpu"
    raw["execution"]["field_solver"] = field.FLOOR_SOLVER_ID
    spec = parse_spec(raw)
    from cells.models.registry import get_model

    model = get_model(spec.model)
    start_step = args.warm
    if args.state is not None:
        clock = json.loads((args.state.parent / "manifest.json").read_text())["clock"]
        with np.load(args.state) as archive:
            state = model.STATE_TYPE(*(archive[k] for k in model.STATE_TYPE._fields))
        start_step = int(clock["step_index"]) + args.warm
        if args.warm:
            raise SystemExit("--warm starts from the definition's own start, not --state")
    else:
        from cells.core.state import initialise

        state = jitted_run(spec, args.warm) if args.warm else initialise(spec).state
    record = dict(
        definition=str(args.definition) if args.definition else "surface_pump_v3_study 825-node",
        state=str(args.state) if args.state else None,
        start_step=start_step,
        steps=args.steps,
        fraction=args.fraction,
        floor_ulps=field.CURRENT_FLOOR_ULPS,
        directions={},
    )
    for kind in args.direction or ["uniform", "largest"]:
        for cap in args.cap or [None]:
            label = kind if cap is None else f"{kind}@cap{cap:g}"
            record["directions"][label] = compare(
                spec,
                state,
                args.steps,
                start_step=start_step,
                fraction=args.fraction,
                kind=kind,
                cap_ulps=cap,
            )
            held = record["directions"][label]["held"]
            print(
                label,
                held["steps_valid"],
                held.get("check_values_error"),
                held["device_failed_rows"],
                json.dumps(held["ledger_ratios"]),
                flush=True,
            )
    args.out.write_text(json.dumps(record, indent=1, default=float) + "\n")


if __name__ == "__main__":
    main()
