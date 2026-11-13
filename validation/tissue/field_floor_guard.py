"""Guards 1 and 2 of docs/FIELD_FLOOR_ACCEPTANCE_DESIGN.md: field solver version 3 against 2.

Version 3 (surface_field.FLOOR_SOLVER_ID) iterates as version 2 and adds, after the Newton
loop, an acceptance test against the attainable current floor. Its layout has one more leaf,
the floor in ulps (field_current_floor). The guards check that nothing else changes.

* jaxprs (guard 1): for every world of validation/tissue/composite_crossrev.py's sets (base,
  qualification; plus the 825-node study tissue itself), trace the checked step and the
  right-hand side with each declaration. Then, in version 3's jaxprs, follow every value
  computed from the floor leaf, through every nested jaxpr (calls, while, cond, scan). A
  value is "value"-tainted when it depends on the floor's magnitude, and "control"-tainted
  when it depends on the floor only through booleans. Guard: no output is value-tainted,
  the validity is control-tainted, and no equation of version 2 disappears; the equations
  version 3 adds are listed by primitive.
* bindings (guard 1): every initial state, layout and control array of both declarations is
  identical, except the added layout leaf, which holds CURRENT_FLOOR_ULPS.
* runs PART (guard 2): validation/tissue/composite_guard.py's parts (w1, w2, g2, g2-order,
  w37) with its pair (frozen, composite) replaced by (version 2, version 3) of one
  definition. Every state, observation column and max_ diagnostic is compared bitwise, and
  so are the device row checks where the part runs them. g2-vmap and scale are this
  module's own: G2-Q1's vectorized cohorts, and the 825-node world (the study tissue, closed
  water, event-free replacement) with device row checks.

Usage (PYTHONPATH at the revision under test):
  python -m validation.tissue.field_floor_guard jaxprs OUT.json [SET]
  python -m validation.tissue.field_floor_guard bindings OUT.json [SET]
  python -m validation.tissue.field_floor_guard runs PART --output DIR [--worlds NAME,...]
"""

import collections
import copy
import json
import sys
from pathlib import Path

import numpy as np

CLEAN, CONTROL, VALUE = 0, 1, 2


def declared(raw, solver):
    out = copy.deepcopy(raw)
    out["execution"]["field_solver"] = solver
    return out


def version_pair(raw):
    """(version 2, version 3) specifications of one definition (composite_guard.pair_specs)."""
    from cells.core.specs import parse_spec
    from cells.numerics import surface_field as field

    return (
        parse_spec(declared(raw, field.FACTORED_SOLVER_ID)),
        parse_spec(declared(raw, field.FLOOR_SOLVER_ID)),
    )


def guard_worlds(world_set):
    from validation.tissue import composite_crossrev as crossrev
    from validation.tissue import surface_pump_v3_study as study

    if world_set == "base":
        return crossrev.worlds()
    if world_set != "qualification":
        raise SystemExit(f"Unknown world set {world_set!r} (base or qualification)")
    out = crossrev.qualification_worlds()
    out["S825_tissue"] = study.tissue_definition(
        dt=1e-3, end_time=0.2, observation_times=[0.0, 0.1, 0.2]
    )
    return out


# Taint analysis of the floor leaf through a jaxpr.


def _sub_jaxprs(params):
    for value in params.values():
        items = value if isinstance(value, (list, tuple)) else (value,)
        for item in items:
            jaxpr = getattr(item, "jaxpr", None)
            if jaxpr is not None and hasattr(jaxpr, "eqns"):
                yield jaxpr  # A ClosedJaxpr.
            elif hasattr(item, "eqns"):
                yield item  # A Jaxpr.


def _inner(jaxpr):
    return jaxpr.jaxpr if hasattr(jaxpr, "jaxpr") and hasattr(jaxpr.jaxpr, "eqns") else jaxpr


def _is_bool(var):
    return str(getattr(var.aval, "dtype", "")) == "bool"


# Multi-operand primitives whose i-th output is their i-th operand.
IDENTITIES = frozenset({"optimization_barrier", "device_put", "copy", "copy_p"})


def taints(jaxpr, inputs, used=None):
    """Output taints of a (closed) jaxpr for input taints; used collects tainted primitives."""
    jaxpr = _inner(jaxpr)
    used = collections.Counter() if used is None else used
    env = {}

    def read(v):
        return CLEAN if hasattr(v, "val") else env.get(v, CLEAN)

    for var, taint in zip(jaxpr.invars, inputs, strict=True):
        env[var] = taint
    for var in jaxpr.constvars:
        env[var] = CLEAN
    for eqn in jaxpr.eqns:
        ins = [read(v) for v in eqn.invars]
        name = eqn.primitive.name
        if max(ins, default=CLEAN) == CLEAN:
            outs = [CLEAN] * len(eqn.outvars)
        elif name == "while":
            outs = _while(eqn, ins, used)
        elif name == "cond":
            outs = _cond(eqn, ins, used)
        elif name == "scan":
            outs = _scan(eqn, ins, used)
        elif name in IDENTITIES and len(ins) == len(eqn.outvars):
            outs = list(ins)  # Each output is its own operand.
        else:
            subs = list(_sub_jaxprs(eqn.params))
            inner = _inner(subs[0]) if len(subs) == 1 else None
            if (
                inner is not None
                and len(inner.invars) == len(ins)
                and len(inner.outvars) == len(eqn.outvars)
            ):  # A call (pjit, custom_jvp_call, checkpoint, ...): follow its body.
                outs = taints(subs[0], ins, used)
            elif max(ins) == VALUE:  # Every output depends on every input (conservative).
                outs = [CONTROL if _is_bool(v) else VALUE for v in eqn.outvars]
            else:
                outs = [CONTROL] * len(eqn.outvars)
            used[(name, max(ins))] += 1
        for var, taint in zip(eqn.outvars, outs, strict=True):
            env[var] = taint
    return [read(v) for v in jaxpr.outvars]


def _while(eqn, ins, used):
    p = eqn.params
    nc, nb = p["cond_nconsts"], p["body_nconsts"]
    cond_consts, body_consts, carry = ins[:nc], ins[nc : nc + nb], list(ins[nc + nb :])
    while True:
        (predicate,) = taints(p["cond_jaxpr"], cond_consts + carry, used)
        body = taints(p["body_jaxpr"], body_consts + carry, used)
        floor = CONTROL if predicate != CLEAN else CLEAN
        new = [max(a, b, floor) for a, b in zip(carry, body, strict=True)]
        if new == carry:
            return carry
        carry = new


def _cond(eqn, ins, used):
    index, operands = ins[0], ins[1:]
    outs = None
    for branch in eqn.params["branches"]:
        result = taints(branch, operands, used)
        outs = result if outs is None else [max(a, b) for a, b in zip(outs, result, strict=True)]
    floor = CONTROL if index != CLEAN else CLEAN
    return [max(t, floor) for t in outs]


def _scan(eqn, ins, used):
    p = eqn.params
    nc, nk = p["num_consts"], p["num_carry"]
    consts, carry, xs = ins[:nc], list(ins[nc : nc + nk]), ins[nc + nk :]
    while True:
        result = taints(p["jaxpr"], consts + carry + xs, used)
        new = [max(a, b) for a, b in zip(carry, result[:nk], strict=True)]
        if new == carry:
            return carry + result[nk:]
        carry = new


def primitive_counts(jaxpr, counts=None):
    """Every equation's primitive, nested jaxprs included (once per occurrence)."""
    counts = collections.Counter() if counts is None else counts
    for eqn in _inner(jaxpr).eqns:
        counts[eqn.primitive.name] += 1
        for sub in _sub_jaxprs(eqn.params):
            primitive_counts(sub, counts)
    return counts


def _traced(raw):
    """(jaxprs by function, flat input paths, state) of a world's checked step and rhs."""
    import jax
    import jax.numpy as jnp

    from validation.tissue import composite_crossrev as crossrev

    spec, model, (s, c, p) = crossrev._setup(raw)
    dt = jnp.asarray(spec.execution.dt)

    def step(s, dt, c, q):
        return model.checked_step(s, dt, c, q, q.active)

    def rhs(s, c, q):
        return model.rhs(s, c, q, q.active)

    paths = {
        "checked_step": [
            jax.tree_util.keystr(k)
            for k, _ in jax.tree_util.tree_flatten_with_path((s, dt, c, p))[0]
        ],
        "rhs": [
            jax.tree_util.keystr(k) for k, _ in jax.tree_util.tree_flatten_with_path((s, c, p))[0]
        ],
    }
    jaxprs = {
        "checked_step": jax.make_jaxpr(step)(s, dt, c, p),
        "rhs": jax.make_jaxpr(rhs)(s, c, p),
    }
    return jaxprs, paths, s


def jaxprs(out, world_set="base"):
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.core.specs import parse_spec
    from cells.core.state import initialise
    from cells.numerics import surface_field as field

    record = dict(world_set=world_set, worlds={})
    same = True
    for name, raw in guard_worlds(world_set).items():
        entry = {}
        try:
            p = initialise(parse_spec(raw)).layout
            free = [getattr(p, k) for k in p._fields if k.endswith("offset_free")]
            entry["free_offsets"] = int(np.sum(free[0])) if free else None
            entry["declared"] = raw["execution"].get("field_solver")
            j2, _, _ = _traced(declared(raw, field.FACTORED_SOLVER_ID))
            j3, paths, state = _traced(declared(raw, field.FLOOR_SOLVER_ID))
            for function in ("checked_step", "rhs"):
                floor = [i for i, k in enumerate(paths[function]) if "field_current_floor" in k]
                if len(floor) != 1:
                    raise ValueError(f"{function}: {len(floor)} floor leaves")
                inputs = [VALUE if i in floor else CLEAN for i in range(len(paths[function]))]
                used = collections.Counter()
                outs = taints(j3[function], inputs, used)
                c2, c3 = primitive_counts(j2[function]), primitive_counts(j3[function])
                removed, added = c2 - c3, c3 - c2
                result = dict(
                    output_taints=collections.Counter(
                        {CLEAN: "clean", CONTROL: "control", VALUE: "value"}[t] for t in outs
                    ),
                    tainted_primitives={
                        f"{k[0]}:{'value' if k[1] == VALUE else 'control'}": v
                        for k, v in sorted(used.items())
                    },
                    removed=dict(removed),
                    added=dict(sorted(added.items())),
                    equations=[sum(c2.values()), sum(c3.values())],
                )
                ok = VALUE not in outs and not removed and used
                if function == "checked_step":
                    n = len(jax.tree_util.tree_leaves(state))
                    result["validity_taint"] = outs[n]
                    ok = ok and outs[n] == CONTROL and len(outs) == n + 1
                result["ok"] = bool(ok)
                entry[function] = result
                same &= bool(ok)
        except Exception as error:  # A world that cannot declare version 3 is evidence.
            entry["error"] = repr(error)
            same = False
        record["worlds"][name] = entry
        print(
            name,
            json.dumps({k: v.get("ok") if isinstance(v, dict) else v for k, v in entry.items()}),
            flush=True,
        )
    record["verdict"] = "pass" if same else "fail"
    Path(out).write_text(json.dumps(record, indent=1, default=str) + "\n")
    print("verdict", record["verdict"], flush=True)
    return same


def bindings(out, world_set="base"):
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.core.schedule import control_values
    from cells.models.registry import get_model
    from cells.numerics import surface_field as field

    record = dict(world_set=world_set, worlds={})
    same = True
    for name, raw in guard_worlds(world_set).items():
        arrays = []
        try:
            for spec in version_pair(raw):
                state, layout = get_model(spec.model).initial_values(spec)
                times = sorted(
                    {0.0, *(c.time for c in spec.experiment.changes), spec.experiment.end_time}
                )
                flat = {}
                for prefix, tree in (
                    ("state.", state),
                    ("layout.", layout),
                    ("control.", control_values(spec, times)),
                ):
                    for key, value in tree._asdict().items():
                        flat[prefix + key] = np.asarray(value)
                arrays.append(flat)
            a, b = arrays
            extra = sorted(set(b) - set(a))
            differs = [
                k
                for k in sorted(set(a) & set(b))
                if a[k].dtype != b[k].dtype
                or a[k].shape != b[k].shape
                or a[k].tobytes() != b[k].tobytes()
            ]
            floor = b.get("layout.field_current_floor")
            ok = (
                not differs
                and not (set(a) - set(b))
                and extra == ["layout.field_current_floor"]
                and floor is not None
                and float(floor) == field.CURRENT_FLOOR_ULPS
            )
            entry = dict(ok=bool(ok), arrays=len(a), extra=extra, differs=differs[:8])
        except Exception as error:
            entry = dict(ok=False, error=repr(error))
        same &= entry["ok"]
        record["worlds"][name] = entry
        print(name, entry, flush=True)
    record["verdict"] = "pass" if same else "fail"
    Path(out).write_text(json.dumps(record, indent=1) + "\n")
    print("verdict", record["verdict"], flush=True)
    return same


# Guard 2: composite_guard's parts, with (version 2, version 3) pairs.


def part_g2_vmap(args, record):
    """G2-Q1's vectorized cohorts (composite_guard.part_g2_vmap) under both declarations."""
    from cells.core.batch import BatchSpec, WorldSpec
    from cells.core.vector_windows import run_vector_windowed
    from cells.core.windows import WindowPolicy
    from cells.numerics import surface_field as field
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
    for label, raws in (("2_W7", w7), ("8_C9", c9)):

        def evaluate(raws=raws):
            from cells.core.specs import parse_spec

            results = []
            for solver in (field.FACTORED_SOLVER_ID, field.FLOOR_SOLVER_ID):
                specs = [parse_spec(declared(r, solver)) for r in raws]
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
                    d = guard.compare_arrays(f"world {w}.{key}", getattr(x, key), getattr(y, key))
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


def part_scale(args, record):
    """The 825-node world: the study tissue (the hold's model), closed water, event-free."""
    from validation.tissue import cell_replacement_fixtures as fx
    from validation.tissue import composite_guard as guard
    from validation.tissue import pump_water_fixtures as wfx
    from validation.tissue import surface_pump_v3_study as study

    raw = study.tissue_definition(dt=1e-3, end_time=0.2, observation_times=[0.0, 0.1, 0.2])
    worlds = dict(
        S825_tissue=raw,
        S825_closed_water=wfx.with_water(raw, availability=0.0),
        S825_event_free=fx.with_replacement(raw),
    )
    for name, definition in worlds.items():
        if args.worlds and name not in args.worlds:
            continue

        def evaluate(definition=definition):
            report, first, second = guard.runner_pair(definition)
            report["device"] = guard.device_pair(first, second)
            return report

        record(name, evaluate)


def runs(argv):
    from validation.tissue import composite_guard as guard

    guard.pair_specs = version_pair  # Every part's pair: version 2, then version 3.
    guard.PARTS = dict(
        w1=guard.part_w1,
        w2=guard.part_w2,
        g2=guard.part_g2,
        **{"g2-order": guard.part_g2_order, "g2-vmap": part_g2_vmap},
        w37=guard.part_w37,
        scale=part_scale,
    )
    guard.main(argv)


if __name__ == "__main__":
    action = sys.argv[1]
    if action == "jaxprs":
        sys.exit(0 if jaxprs(*sys.argv[2:4]) else 1)
    elif action == "bindings":
        sys.exit(0 if bindings(*sys.argv[2:4]) else 1)
    elif action == "runs":
        runs(sys.argv[2:])
    else:
        raise SystemExit(f"Unknown action {action!r} (jaxprs, bindings or runs)")
