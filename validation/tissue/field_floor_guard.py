"""Guards 1 and 2 of docs/FIELD_FLOOR_ACCEPTANCE_DESIGN.md: field solver version 3 against 2.

Version 3 (surface_field.FLOOR_SOLVER_ID) iterates as version 2 and adds, after the Newton
loop, an acceptance test against the attainable current floor. Its layout has one more leaf,
the floor in ulps (field_current_floor). The guards check that nothing else changes.

* jaxprs (guard 1): for every world of validation/tissue/composite_crossrev.py's sets (base,
  qualification; plus the 825-node study tissue itself), or of given definition files
  (SET files), trace the checked step, the right-hand side and the device row checks with
  each declaration. Then, in version 3's jaxprs, follow every value
  computed from the floor leaf, through every nested jaxpr (calls, while, cond, scan). A
  value is "value"-tainted when it depends on the floor's magnitude, and "control"-tainted
  when it depends on the floor only through booleans. Guard: no output is value-tainted,
  the validity is control-tainted, and no equation of version 2 disappears; the equations
  version 3 adds are listed by primitive.
  Counts see no constant, and not two exchanged ones, so from 25 November 2026 (D148) the
  programs and their constants are compared too (compare_programs, Pairing). Version 3's program,
  with each acceptance test taken out and the `or` that joins it read as the solve's own
  convergence, must be version 2's:
  - program: every equation an output is computed from, at every depth and in order, is version
    2's under one renaming of variables, with each literal and closed-over array bit for bit. It
    contains the backward slice of every output, the validity's too. Beyond it, version 3 has the
    floor leaf and the acceptance tests (each printed once, under acceptance_tests), nothing else;
  - constants: every literal at full precision and every closed-over array (composite_crossrev's
    record) of version 3's program; beyond version 2's it has the tests' own and no others;
  - device_check_constants: model.device_check_constants is equal.
  A definition that selects the step-doubled energy check also gets doubled_step, the step its runs
  take. A definition that version 2 refuses at parse is traced under version 2 unparsed
  (version_specs; the record says so under version_2).
  Where the pairing is not exact: a dead equation is compared by counts (XLA removes it); a custom
  rule's derivative is compared by its name (the rules are JAX's own; its body is paired); a
  nested jaxpr is paired whole, not sliced by output; a loop that carries the floor leaf is refused
  as "not comparable", which is a limit of the tool and not a difference.
* bindings (guard 1): every initial state, layout and control array of both declarations is
  identical, except the added layout leaf, which holds CURRENT_FLOOR_ULPS.
* runs PART (guard 2): validation/tissue/composite_guard.py's parts (w1, w2, g2, g2-order,
  w37) with its pair (frozen, composite) replaced by (version 2, version 3) of one
  definition. Every state, observation column and max_ diagnostic is compared bitwise, and
  so are the device row checks where the part runs them. g2-vmap and scale are this
  module's own: G2-Q1's vectorized cohorts, and the 825-node world (the study tissue, closed
  water, event-free replacement) with device row checks.

FR-17 stage 1 (docs/FIELD_SOLVER_INTERFACE_DESIGN.md §8.5) reuses guard 2's runs with another
candidate: runs --candidate ID pairs version 2 with ID (here the sparse field solver) instead of
version 3, every part alike.

Before a campaign declares version 3 in a run of record, both guard 1 commands run on its frozen
snapshot S, with its own definitions, one per world or structure it runs (parsed definitions, batch
definitions or snapshot manifests; an ensemble's request is not read, its worlds' definitions are):
  export PYTHONPATH=S/src:S JAX_ENABLE_X64=1 JAX_PLATFORMS=cpu PYTHONDONTWRITEBYTECODE=1
  python -P -m validation.tissue.field_floor_guard jaxprs jaxprs.json files DEFINITION.json ...
  python -P -m validation.tissue.field_floor_guard bindings bindings.json files DEFINITION.json ...
with the runs' own python (they trace and bind; no step runs). Each record must say verdict "pass"
and hold every definition. In the jaxprs record, source's paths are S's, each definition's declared
is version 3's ID, each function's program.result is "equal" and its constants.ok true,
checked_step's acceptance_tests is at least 1, and version_2 is there only for a definition that
version 2 refuses. An earlier run does not replace this one: the programs compared are the
snapshot's. Not compared: host code (parse's start check, observations, check_values: NumPy), the
rollouts around the step, and what vmap makes of it.

Usage (PYTHONPATH at the revision under test):
  python -m validation.tissue.field_floor_guard jaxprs OUT.json [SET [DEFINITION.json ...]]
  python -m validation.tissue.field_floor_guard bindings OUT.json [SET [DEFINITION.json ...]]
  python -m validation.tissue.field_floor_guard runs PART --output DIR [--worlds NAME,...]
                                                    [--candidate ID]
"""

import collections
import copy
import dataclasses
import hashlib
import inspect
import json
import sys
import time
from pathlib import Path

import numpy as np

CLEAN, CONTROL, VALUE = 0, 1, 2
CANDIDATE = "cells.solver.capacitive_reduction_gauged_damped_newton@3"  # runs' second declaration (--candidate)


def declared(raw, solver):
    out = copy.deepcopy(raw)
    out["execution"]["field_solver"] = solver
    return out


def version_pair(raw):
    """(version 2, version 3) specifications of one definition (composite_guard.pair_specs)."""
    from cells.definitions.specs import parse_spec
    from cells.numerics import surface_field as field

    return (
        parse_spec(declared(raw, field.FACTORED_SOLVER_ID)),
        parse_spec(declared(raw, CANDIDATE)),
    )


def version_specs(raw):
    """(version 2, version 3) specifications of one definition, and version 2's refusal (or None).

    Version 2 refuses at parse a definition whose start its field solve cannot certify (XC0's P1LB,
    declared version 3 for that reason). Its specification is then version 3's with the field
    solver replaced and the parse check skipped, so version 2 binds its own layout and its program
    can be traced. A traced program does not depend on whether a start is certified."""
    from cells.definitions.specs import ConfigError, parse_spec
    from cells.numerics import surface_field as field

    three = parse_spec(declared(raw, field.FLOOR_SOLVER_ID))
    try:
        return parse_spec(declared(raw, field.FACTORED_SOLVER_ID)), three, None
    except ConfigError as error:
        execution = dataclasses.replace(three.execution, field_solver=field.FACTORED_SOLVER_ID)
        return dataclasses.replace(three, execution=execution), three, str(error)


def guard_worlds(world_set, paths=()):
    """base, qualification, or files: definitions at paths, or snapshot manifests (a batch's, or a
    batch's definition, holds one per world: PATH#WORLD_ID)."""
    from validation.tissue import composite_crossrev as crossrev
    from validation.tissue import surface_pump_v3_study as study

    if world_set == "base":
        return crossrev.worlds()
    if world_set == "files":
        out = {}
        for path in paths:
            raw = json.loads(Path(path).read_text())
            raw = raw.get("spec", raw)
            if raw.get("kind") == "independent_worlds":
                out.update({f"{path}#{w['world_id']}": w["simulation"] for w in raw["worlds"]})
            else:
                out[str(path)] = raw
        for raw in out.values():
            raw["execution"]["backend"] = "cpu"
        return out
    if world_set != "qualification":
        raise SystemExit(f"Unknown world set {world_set!r} (base, qualification or files)")
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


def _scan_counts(params):
    """(constants, carried values) of a scan (JAX 0.11 keeps them as the parts of ft_in)."""
    if "num_consts" in params:
        return params["num_consts"], params["num_carry"]
    consts, carry, _ = params["ft_in"].unpack()
    return len(consts), len(carry)


def _scan(eqn, ins, used):
    p = eqn.params
    nc, nk = _scan_counts(p)
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


# The programs and their constants (D148): version 3's program, its acceptance tests taken out, is
# version 2's, equation by equation.

LEAF = "field_current_floor"  # The layout leaf only version 3 has.
# An acceptance test's equations that read the floor, in order (surface_field.solve): the floor in
# ulps x eps, x the incident sum, |residual| <= it, at every component.
FLOOR_CHAIN = ("mul", "mul", "le", "reduce_and")
EPS = float(np.finfo(float).eps)  # Their one literal.
# jit's parameters with one entry per operand.
PER_OPERAND = frozenset({"donated_invars", "in_shardings", "in_layouts"})
SHOWN = 8  # Differences written out per function; every one is counted.


class NotComparable(Exception):
    """A construct the pairing does not read: a limit of the tool, not a difference."""


class _Misaligned(Exception):
    """One level's equations cannot be paired further (the difference is recorded)."""


def _literal(atom):
    return hasattr(atom, "val")


def _literal_value(atom):
    """A literal as its program holds it, in its own dtype."""
    return np.asarray(atom.val, dtype=atom.aval.dtype)


def _digest(array):
    array = np.ascontiguousarray(np.asarray(array))
    return hashlib.sha256(array.tobytes()).hexdigest()


def _literal_text(atom):
    """A literal's dtype and its value at full precision (an array literal's digest)."""
    value = _literal_value(atom)
    if value.ndim:
        return f"{value.dtype}{list(value.shape)} sha256:{_digest(value)}"
    return f"{value.dtype} {value.item()!r}"


def literal_counts(jaxpr, counts=None):
    """Every literal of a jaxpr, nested jaxprs included (once per occurrence)."""
    counts = collections.Counter() if counts is None else counts
    jaxpr = _inner(jaxpr)
    atoms = [v for eqn in jaxpr.eqns for v in eqn.invars] + list(jaxpr.outvars)
    counts.update(_literal_text(v) for v in atoms if _literal(v))
    for eqn in jaxpr.eqns:
        for sub in _sub_jaxprs(eqn.params):
            literal_counts(sub, counts)
    return counts


def _count(eqn, primitives, literals):
    """Add one equation's primitives and literals, nested jaxprs included."""
    primitives[eqn.primitive.name] += 1
    literals.update(_literal_text(v) for v in eqn.invars if _literal(v))
    for sub in _sub_jaxprs(eqn.params):
        primitive_counts(sub, primitives)
        literal_counts(sub, literals)


def _type(atom):
    aval = atom.aval
    shape, weak = getattr(aval, "shape", ()), getattr(aval, "weak_type", False)
    return str(getattr(aval, "dtype", aval)), tuple(shape), bool(weak)


def _same_array(x, y):
    x, y = np.asarray(x), np.asarray(y)
    return x.dtype == y.dtype and x.shape == y.shape and x.tobytes() == y.tobytes()


def _same(x, y):
    """Two parameter values: containers item by item, arrays and floats bit for bit."""
    if type(x) is not type(y):
        return False
    if isinstance(x, (tuple, list)):
        return len(x) == len(y) and all(map(_same, x, y))
    if isinstance(x, dict):
        return x.keys() == y.keys() and all(_same(x[k], y[k]) for k in x)
    if isinstance(x, float) or (hasattr(x, "tobytes") and hasattr(x, "shape")):
        return _same_array(x, y)
    return x is y or bool(x == y) or repr(x) == repr(y)


def _function_name(value):
    """A function parameter's name (a custom rule, for example); None for another parameter."""
    if hasattr(value, "call_wrapped"):  # A traced custom rule.
        return str(getattr(value.debug_info, "func_name", value))
    return value.__qualname__ if inspect.isroutine(value) else None


def _is_jaxpr(value):
    return hasattr(value, "eqns") or hasattr(getattr(value, "jaxpr", None), "eqns")


def _bodies(value):
    """The jaxprs a parameter holds, itself or in a tuple (with its Nones); else nothing."""
    items = value if isinstance(value, (tuple, list)) else (value,)
    return list(items) if any(map(_is_jaxpr, items)) else []


def _operands_at(eqn, variables):
    return [i for i, v in enumerate(eqn.invars) if not _literal(v) and v in variables]


def _hands_on(eqn):
    """Whether each output is its own operand (a barrier)."""
    return eqn.primitive.name in IDENTITIES and len(eqn.invars) == len(eqn.outvars)


def _drop(items, at):
    return type(items)(v for i, v in enumerate(items) if i not in at)


def _entries(eqn, at):
    """Where operands at positions `at` enter eqn's nested jaxprs: ({parameter: input positions},
    {parameter that lists or counts operands: (version 2's, version 3's) as they must agree})."""
    p, name = eqn.params, eqn.primitive.name
    if name == "cond" and 0 not in at:
        return {"branches": [i - 1 for i in at]}, {}
    if name == "while":
        nc, nb = p["cond_nconsts"], p["body_nconsts"]
        if all(i < nc + nb for i in at):
            cond = [i for i in at if i < nc]
            body = [i - nc for i in at if i >= nc]
            return {"cond_jaxpr": cond, "body_jaxpr": body}, {
                "cond_nconsts": lambda x, y: (x, y - len(cond)),
                "body_nconsts": lambda x, y: (x, y - len(body)),
            }
    elif name == "scan":
        if all(i < _scan_counts(p)[0] for i in at):

            def parts(x, y):
                x, y = ([len(part) for part in v.unpack()] for v in (x, y))
                return x, [y[0] - len(at), *y[1:]]

            return {"jaxpr": at}, {"num_consts": lambda x, y: (x, y - len(at)), "ft_in": parts}
    else:  # A call (jit, custom_jvp_call, checkpoint): one body, an input per operand.
        holders = {k: b[0] for k, v in p.items() if len(b := _bodies(v)) == 1}
        if len(holders) == 1:
            ((key, body),) = holders.items()
            if len(_inner(body).invars) == len(eqn.invars):
                lists = dict.fromkeys(PER_OPERAND, lambda x, y: (x, _drop(y, at)))
                counts = {"num_consts": lambda x, y: (x, y - sum(i < y for i in at))}
                return {key: at}, {**lists, **counts}
    raise NotComparable(f"{name} takes the floor leaf as operand {at} (a loop's carry, or a call)")


def _feeding(jaxpr, variables, joins=()):
    """(the equations that variables are computed from, the joins on the way): a backward slice.
    A join is read as the operand joins gives it, and is not itself one of the equations."""
    wanted, equations, passed = {v for v in variables if not _literal(v)}, set(), set()
    for i in reversed(range(len(jaxpr.eqns))):
        eqn = jaxpr.eqns[i]
        if not eqn.effects and not any(v in wanted for v in eqn.outvars):
            continue
        if i in joins:
            passed.add(i)
            wanted.add(joins[i])
        else:
            equations.add(i)
            wanted.update(v for v in eqn.invars if not _literal(v))
    return equations, passed


class Pairing:
    """Version 3's program paired with version 2's, in order and at every depth.

    The two are allowed to differ in two places only:
    * the floor leaf: one more input, and so one more operand of each barrier, cond, jit or loop
      it passes through (a loop's constant, not its carry);
    * the acceptance tests: after a field solve's Newton loop, the equations computed from the
      leaf (FLOOR_CHAIN), the equations that feed only those, and the join, the `or` of the test
      with the solve's own convergence, `and(accepted, norm <= NEWTON_TARGET)`, which nothing
      else reads. The pairing leaves a test out and reads its join as that convergence.
    Every other equation an output is computed from is paired with version 2's: the same
    primitive, parameters and operands under one renaming of variables, each literal and
    closed-over array bit for bit, each result's type, the effects and the context, and nested
    jaxprs alike. A dead equation (no output reads it, so XLA removes it) is compared by the counts
    of its primitives and literals only: where a world has no face or no junction, part of each
    test is dead.
    """

    def __init__(self, target):
        self.target = target  # NEWTON_TARGET of the source under test.
        self.paired = self.count = 0
        self.differences, self.texts = [], []
        self.named = collections.Counter()  # Function parameters, compared by name.
        # Primitives and literals: the acceptance tests', and each version's dead equations'.
        self.added = (collections.Counter(), collections.Counter())
        self.dead = [(collections.Counter(), collections.Counter()) for _ in range(2)]
        self.top, self.joins = {}, {}  # The outer level: version 3's equation -> version 2's.

    def differ(self, where, what, two=None, three=None):
        self.count += 1
        if len(self.differences) < SHOWN:
            shown = dict(version_2=two, version_3=three)
            shown = {k: str(v)[:6000] for k, v in shown.items() if v is not None}
            self.differences.append(dict(where=where, what=what, **shown))

    def stop(self, *args):
        self.differ(*args)
        raise _Misaligned

    def bind(self, two, three, rename, where, what):
        """Version 3's variables are version 2's, in order."""
        if len(two) != len(three):
            self.stop(where, f"{len(two)} {what} in version 2, {len(three)} in version 3")
        for i, (x, y) in enumerate(zip(two, three, strict=True)):
            if _type(x) != _type(y):
                self.differ(where, f"{what} {i}: {_type(x)} in version 2, {_type(y)} in version 3")
            rename[y] = x

    def operand(self, x, y, rename, where, what, two=None, three=None):
        if _literal(x) and _literal(y):
            if _type(x) != _type(y) or not _same_array(_literal_value(x), _literal_value(y)):
                words = f"{what}: {_literal_text(x)} in version 2, {_literal_text(y)} in version 3"
                self.differ(where, words, two, three)
        elif _literal(x) or _literal(y) or rename.get(y) is not x:
            self.differ(where, f"{what}: another value", two, three)

    def level(self, two, three, leaf, where, top=False):
        """Pair one level's equations. leaf: the positions of version 3's inputs that hold the
        floor leaf."""
        if two is three:  # One object: a cached nested jaxpr.
            self.paired += sum(primitive_counts(two).values())
            return
        arrays = [list(getattr(j, "consts", None) or ()) for j in (two, three)]
        two, three = _inner(two), _inner(three)
        if len(arrays[0]) != len(arrays[1]):
            words = "{} closed-over arrays in version 2, {} in version 3"
            self.stop(where, words.format(*map(len, arrays)))
        for i, (x, y) in enumerate(zip(*arrays, strict=True)):
            if not _same_array(x, y):
                x, y = (f"{v.dtype}{list(v.shape)} sha256:{_digest(v)}" for v in (x, y))
                self.differ(where, f"closed-over array {i}", x, y)
        leaves, rename = {three.invars[i] for i in leaf}, {}
        inputs = [v for v in three.invars if v not in leaves]
        ours = [*two.constvars, *two.invars]
        self.bind(ours, [*three.constvars, *inputs], rename, where, "inputs")
        live = [sorted(_feeding(j, j.outvars)[0]) for j in (two, three)]
        for j, kept, dead in zip((two, three), live, self.dead, strict=True):
            for i in sorted(set(range(len(j.eqns))) - set(kept)):
                _count(j.eqns[i], *dead)
        tests, joins = self.acceptance(three, live[1], leaves, where)
        rest = iter(live[0])
        for i in live[1]:
            eqn, at = three.eqns[i], f"{where}/{i} {three.eqns[i].primitive.name}"
            if i in tests:
                continue
            if i in joins:
                rename[eqn.outvars[0]] = rename.get(joins[i])
                continue
            k = next(rest, None)
            if k is None:
                self.stop(at, "only version 3 has this equation", None, eqn)
            if top:
                self.top[i] = k
            self.equation(two.eqns[k], eqn, leaves, rename, at)
        k = next(rest, None)
        if k is not None:
            self.stop(f"{where}/{k} in version 2", "only version 2 has it", two.eqns[k], None)
        if len(two.outvars) != len(three.outvars):
            counts = [len(j.outvars) for j in (two, three)]
            self.stop(where, "{} outputs in version 2, {} in version 3".format(*counts))
        for i, (x, y) in enumerate(zip(two.outvars, three.outvars, strict=True)):
            self.operand(x, y, rename, where, f"output {i}")
        if top:
            self.joins = joins

    def equation(self, two, three, leaves, rename, where):
        at = _operands_at(three, leaves)
        handed = at if _hands_on(three) else []
        if two.primitive.name != three.primitive.name:
            self.stop(where, "another primitive", two, three)
        operands = [v for i, v in enumerate(three.invars) if i not in at]
        if len(two.invars) != len(operands):
            self.stop(where, "another number of operands", two, three)
        for i, (x, y) in enumerate(zip(two.invars, operands, strict=True)):
            self.operand(x, y, rename, where, f"operand {i}", two, three)
        self.parameters(two, three, at, where)
        if not _same(two.effects, three.effects) or not _same(two.ctx, three.ctx):
            self.differ(where, "another effect or context", two, three)
        outputs = [v for i, v in enumerate(three.outvars) if i not in handed]
        self.bind(two.outvars, outputs, rename, where, "results")
        self.paired += 1

    def parameters(self, two, three, at, where):
        if two.params.keys() != three.params.keys():
            return self.differ(where, "other parameters", two, three)
        nested = any(map(_bodies, three.params.values()))
        entries, without = _entries(three, at) if at and nested else ({}, {})
        for key, x in two.params.items():
            y = three.params[key]
            if key in without:
                x, y = without[key](x, y)
            a, b = _bodies(x), _bodies(y)
            names = _function_name(x), _function_name(y)
            if a and list(map(_is_jaxpr, a)) == list(map(_is_jaxpr, b)):
                for i, (p, q) in enumerate(zip(a, b, strict=True)):
                    try:
                        if _is_jaxpr(p):
                            self.level(p, q, entries.get(key, ()), f"{where}/{key}{i}")
                    except _Misaligned:  # Within it; the equation itself is paired.
                        pass
            elif None not in names:
                self.named[f"{three.primitive.name} {key} {names[1]}"] += 1
                if names[0] != names[1]:
                    self.differ(where, f"{key}: {names[0]} in version 2, {names[1]} in version 3")
            elif not _same(x, y):
                self.differ(where, f"{key}: {x!r} in version 2, {y!r} in version 3", two, three)

    def acceptance(self, jaxpr, live, leaves, where):
        """A level's acceptance tests: (their equations, {join: the solve's own convergence}).
        leaves grows by the variables that barriers hand the leaf on to."""
        read, joins, made, users = set(), {}, {}, collections.defaultdict(list)
        tainted = set()  # Computed from the leaf.
        for i in live:
            eqn = jaxpr.eqns[i]
            operands = [v for v in eqn.invars if not _literal(v)]
            for v in operands:
                users[v].append(i)
            made.update(dict.fromkeys(eqn.outvars, i))
            on_leaf, on_test = (any(v in s for v in operands) for s in (leaves, tainted))
            if not (on_leaf or on_test):
                continue
            if on_leaf and not on_test:
                if _hands_on(eqn):
                    leaves.update(eqn.outvars[k] for k in _operands_at(eqn, leaves))
                    continue
                if any(map(_bodies, eqn.params.values())):
                    continue  # The leaf enters a nested jaxpr (parameters, level).
            others = [v for v in operands if v not in tainted]
            if eqn.primitive.name == "or" and len(others) == 1 and not on_leaf:
                joins[i] = others[0]
                continue
            read.add(i)
            tainted.update(eqn.outvars)
        for i, v in enumerate(jaxpr.outvars):
            if not _literal(v):
                users[v].append(None)
                if v in tainted or v in leaves:
                    self.differ(where, f"output {i} reads the floor outside an acceptance test")
        equations = set(read)  # With the equations that feed only them.
        for i in reversed(live):
            uses = [u for v in jaxpr.eqns[i].outvars for u in users[v]]
            if i not in joins and uses and all(u in equations for u in uses):
                equations.add(i)
        covered = set()
        for i, convergence in joins.items():
            (test,) = (v for v in jaxpr.eqns[i].invars if v is not convergence)
            # Not through an earlier test (a half step's, whose state the next one starts from).
            own = sorted(_feeding(jaxpr, [test], joins)[0] & equations)
            covered.update(own)
            chain = [jaxpr.eqns[k] for k in own if k in read]
            names = tuple(eqn.primitive.name for eqn in chain)
            scale = [float(_literal_value(v)) for eqn in chain for v in eqn.invars if _literal(v)]
            at = f"{where}/{i} or"
            if names != FLOOR_CHAIN or scale != [EPS]:
                self.differ(at, f"an acceptance test that reads the floor by {names}, {scale}")
            if not self.converges(jaxpr, convergence, made) or users[convergence] != [i]:
                self.differ(at, "joined to something other than the field solve's convergence")
            self.texts.append(_program_text(jaxpr, [*own, i]))
        for i in sorted(equations - covered):
            self.differ(where, "reads the floor outside a test", None, jaxpr.eqns[i])
        for i in sorted(equations | set(joins)):
            _count(jaxpr.eqns[i], *self.added)
        return equations, joins

    def converges(self, jaxpr, variable, made):
        """Whether variable is and(accepted, norm <= NEWTON_TARGET)."""
        if variable not in made or jaxpr.eqns[made[variable]].primitive.name != "and":
            return False
        for v in jaxpr.eqns[made[variable]].invars:
            source = jaxpr.eqns[made[v]] if not _literal(v) and v in made else None
            if source is not None and source.primitive.name == "le":
                bound = source.invars[1]
                if _literal(bound) and float(_literal_value(bound)) == self.target:
                    return True
        return False


def _program_text(jaxpr, indices):
    """Some of a jaxpr's equations, printed as a program of the values they read from the rest."""
    eqns = [jaxpr.eqns[i] for i in indices]
    made = {v for e in eqns for v in e.outvars}
    operands = (v for e in eqns for v in e.invars if not _literal(v))
    inputs = list(dict.fromkeys(v for v in operands if v not in made))
    outputs = list(eqns[-1].outvars)
    return str(jaxpr.replace(constvars=[], invars=inputs, outvars=outputs, eqns=eqns))


def compare_programs(two, three, leaf, target, gates=()):
    """Version 3's traced program against version 2's (Pairing), and their constants.

    two, three: closed jaxprs; leaf: the positions of three's inputs that hold the floor leaf;
    target: NEWTON_TARGET; gates: the positions of the outputs that say whether a step is
    accepted. Returns (program, constants, the acceptance tests' texts), the first two being the
    record's fields:

    program: result is "equal", "differs" (the first differences are written out) or "not
    comparable" (a construct the pairing does not read). accounted says that the paired, test and
    dead equations are all of both programs' equations. slice is the backward slice of every
    output but the gates at the outer level (a nested jaxpr is one equation): its size, whether it
    is the same in both versions, and the acceptance tests on the way, each read as the solve's
    own convergence (the outputs pass through where(valid, new, old)).
    constants: the literals of version 3's program with their counts, what version 2's multiset has
    beyond them and the reverse (which must be the acceptance tests' own, dead ones included), and
    the closed-over arrays as composite_crossrev.const_record writes them, equal in both."""
    from validation.tissue import composite_crossrev as crossrev

    pairing, result, limit = Pairing(target), "equal", None
    try:
        pairing.level(two, three, leaf, "top", top=True)
    except _Misaligned:
        pass
    except NotComparable as error:
        result, limit = "not comparable", str(error)
    result = "differs" if pairing.count else result
    c2, c3 = primitive_counts(two), primitive_counts(three)
    dead_added, dead_removed = (
        tuple(a - b for a, b in zip(pairing.dead[i], pairing.dead[1 - i], strict=True))
        for i in (1, 0)
    )
    accounted = (
        pairing.paired + sum(pairing.dead[0][0].values()) == sum(c2.values())
        and not (c2 - c3)
        and c3 - c2 == pairing.added[0] + dead_added[0]
        and not dead_removed[0]
    )
    program = dict(
        result=result,
        accounted=accounted,
        paired_equations=pairing.paired,
        dead_equations=[sum(d[0].values()) for d in pairing.dead],
        acceptance_tests=len(pairing.texts),
        acceptance_primitives=dict(sorted(pairing.added[0].items())),
        acceptance_dead=dict(sorted(dead_added[0].items())),
        compared_by_name=dict(pairing.named),
        differences=pairing.differences,
        difference_count=pairing.count,
    )
    if limit is not None:
        program["not_comparable"] = limit
    if result == "equal":
        a, b = _inner(two), _inner(three)
        outputs = [k for k in range(len(a.outvars)) if k not in gates]
        ours, _ = _feeding(a, [a.outvars[k] for k in outputs])
        theirs, passed = _feeding(b, [b.outvars[k] for k in outputs], pairing.joins)
        program["slice"] = dict(
            outputs=len(outputs),
            equations=len(ours),
            equal={pairing.top.get(i) for i in theirs} == ours,
            acceptance_tests=len(passed),
        )
    x, y = literal_counts(two), literal_counts(three)
    own = pairing.added[1] + dead_added[1]
    arrays = [json.loads(crossrev.const_record(j))["consts"] for j in (two, three)]
    constants = dict(
        ok=not (x - y) and y - x == own and not dead_removed[1] and arrays[0] == arrays[1],
        literals=[sum(x.values()), sum(y.values())],
        literals_removed=dict(sorted((x - y).items())),
        literals_added=dict(sorted((y - x).items())),
        acceptance_literals=dict(sorted(own.items())),
        literal_values=dict(sorted(y.items())),
        closed_arrays=[len(a) for a in arrays],
        arrays=arrays[1] if arrays[0] == arrays[1] else arrays,
    )
    return program, constants, pairing.texts


def compare_check_constants(two, three):
    """model.device_check_constants of both versions' setups, name by name."""
    from validation.tissue import composite_crossrev as crossrev

    rows = []
    for spec, model, _ in (two, three):
        rows.append(
            {
                name: dict(dtype=str(v.dtype), shape=list(v.shape), sha256=_digest(v))
                for name, v in crossrev.check_constants(model, spec)
            }
        )
    differs = [k for k in sorted({*rows[0], *rows[1]}) if rows[0].get(k) != rows[1].get(k)]
    out = dict(ok=not differs, constants=rows[1])
    if differs:
        out.update(differs=differs, version_2=rows[0])
    return out


def _setup(spec):
    """composite_crossrev._setup of a specification: (spec, model, (state, control, layout))."""
    import jax
    import jax.numpy as jnp

    from cells.execution.schedule import control_values
    from cells.registry.models import get_model

    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    controls = control_values(spec, [0.0])
    control = type(controls)(*(np.asarray(v[0]) for v in controls))
    return spec, model, jax.tree.map(jnp.asarray, (state, control, p))


def _traced(raw):
    """_trace of a definition as it is declared."""
    from validation.tissue import composite_crossrev as crossrev

    return _trace(*crossrev._setup(raw))


def _trace(spec, model, arrays):
    """(jaxprs by function, flat input paths, state): the checked step, the right-hand
    side and the device row checks, as composite_crossrev traces them (dt traced); and, for a
    definition that selects the step-doubled energy check, doubled_step, the step its runs take
    (cells.execution.energy_check: the checked step whole and in halves, with the energy terms)."""
    import jax
    import jax.numpy as jnp

    s, c, p = arrays
    dt = jnp.asarray(spec.execution.dt)
    constants = model.device_check_constants(spec)

    def step(s, dt, c, q):
        return model.checked_step(s, dt, c, q, q.active)

    def rhs(s, c, q):
        return model.rhs(s, c, q, q.active)

    def checks(s, q):
        return model.device_checks(s, s, q, constants, 3)

    def keys(tree):
        return [jax.tree_util.keystr(k) for k, _ in jax.tree_util.tree_flatten_with_path(tree)[0]]

    paths = {
        "checked_step": keys((s, dt, c, p)),
        "rhs": keys((s, c, p)),
        "device_checks": keys((s, p)),
    }
    jaxprs = {
        "checked_step": jax.make_jaxpr(step)(s, dt, c, p),
        "rhs": jax.make_jaxpr(rhs)(s, c, p),
        "device_checks": jax.make_jaxpr(checks)(s, p),
    }
    if getattr(spec, "energy_check", None) is not None:
        from cells.execution import energy_check

        doubled = energy_check.doubled(model.checked_step, *energy_check.terms(model, spec, p))
        paths["doubled_step"] = paths["checked_step"]
        jaxprs["doubled_step"] = jax.make_jaxpr(lambda s, dt, c, q: doubled(s, dt, c, q, q.active))(
            s, dt, c, p
        )
    return jaxprs, paths, s


def jaxprs(out, world_set="base", paths=()):
    import jax

    jax.config.update("jax_enable_x64", True)
    import cells
    from cells.definitions.specs import parse_spec
    from cells.execution.state import initialise
    from cells.numerics import surface_field as field
    from validation.tissue import composite_crossrev as crossrev

    modules = dict(cells=cells.__file__, composite_crossrev=crossrev.__file__, tool=__file__)
    record = dict(
        world_set=world_set,
        source={k: str(Path(v).resolve()) for k, v in modules.items()},
        acceptance_tests={},
        worlds={},
    )
    same = True
    for name, raw in guard_worlds(world_set, paths).items():
        entry, started = {}, time.perf_counter()
        try:
            p = initialise(parse_spec(raw)).layout
            free = [getattr(p, k) for k in p._fields if k.endswith("offset_free")]
            entry["free_offsets"] = int(np.sum(free[0])) if free else None
            entry["declared"] = raw["execution"].get("field_solver")
            *specs, refused = version_specs(raw)
            if refused is not None:
                entry["version_2"] = f"traced unparsed; its parse refuses the definition: {refused}"
            two, three = map(_setup, specs)
            entry["device_check_constants"] = compare_check_constants(two, three)
            same &= entry["device_check_constants"]["ok"]
            j2, paths2, _ = _trace(*two)
            j3, paths, state = _trace(*three)
            for function in j3:
                floor = [i for i, k in enumerate(paths[function]) if LEAF in k]
                if len(floor) != 1:
                    raise ValueError(f"{function}: {len(floor)} floor leaves")
                if [k for k in paths[function] if LEAF not in k] != paths2[function]:
                    raise ValueError(f"{function}: the inputs differ by more than the floor leaf")
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
                result["floor_used"] = bool(used)
                # The step and rhs use the floor (their validity); the row checks need not.
                ok = (
                    VALUE not in outs
                    and not removed
                    and (bool(used) or function == "device_checks")
                )
                n = len(jax.tree_util.tree_leaves(state))
                # The validities: the step's, and the half steps' of a step-doubled step, after its
                # four energy values.
                gates = dict(checked_step=(n,), doubled_step=(n, n + 5)).get(function, ())
                if gates:
                    result["validity_taint"] = outs[n]
                    ok = ok and all(outs[k] == CONTROL for k in gates)
                    ok = ok and len(outs) == gates[-1] + 1
                program, constants, texts = compare_programs(
                    j2[function], j3[function], floor, field.NEWTON_TARGET, gates
                )
                for text in texts:
                    key = _digest(np.frombuffer(text.encode(), np.uint8))[:16]
                    record["acceptance_tests"].setdefault(key, text)
                result.update(program=program, constants=constants)
                ok = (
                    ok
                    and program["result"] == "equal"
                    and program["accounted"]
                    and program["slice"]["equal"]
                    and bool(texts) == (function != "device_checks")
                    and constants["ok"]
                )
                result["ok"] = bool(ok)
                entry[function] = result
                same &= bool(ok)
        except Exception as error:  # A world that cannot declare version 3 is evidence.
            entry["error"] = repr(error)
            same = False
        entry["seconds"] = round(time.perf_counter() - started, 1)
        record["worlds"][name] = entry
        Path(out).write_text(json.dumps(record, indent=1, default=str) + "\n")  # Kept if stopped.
        print(
            name,
            json.dumps({k: v.get("ok") if isinstance(v, dict) else v for k, v in entry.items()}),
            flush=True,
        )
    record["verdict"] = "pass" if same else "fail"
    Path(out).write_text(json.dumps(record, indent=1, default=str) + "\n")
    print("verdict", record["verdict"], flush=True)
    return same


def bindings(out, world_set="base", paths=()):
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.execution.schedule import control_values
    from cells.numerics import surface_field as field
    from cells.registry.models import get_model

    record = dict(world_set=world_set, worlds={})
    same = True
    for name, raw in guard_worlds(world_set, paths).items():
        arrays = []
        try:
            *specs, refused = version_specs(raw)
            for spec in specs:
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
            if refused is not None:
                entry["version_2"] = f"bound unparsed; its parse refuses the definition: {refused}"
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
    from cells.execution.batch import BatchSpec, WorldSpec
    from cells.execution.vector_windows import run_vector_windowed
    from cells.execution.windows import WindowPolicy
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
            from cells.definitions.specs import parse_spec

            results = []
            for solver in (field.FACTORED_SOLVER_ID, CANDIDATE):
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
    global CANDIDATE
    from validation.tissue import composite_guard as guard

    argv = list(argv)
    if "--candidate" in argv:
        at = argv.index("--candidate")
        CANDIDATE = argv[at + 1]
        del argv[at : at + 2]
    guard.pair_specs = version_pair  # Every part's pair: version 2, then the candidate.
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
        sys.exit(0 if jaxprs(sys.argv[2], *sys.argv[3:4], paths=sys.argv[4:]) else 1)
    elif action == "bindings":
        sys.exit(0 if bindings(sys.argv[2], *sys.argv[3:4], paths=sys.argv[4:]) else 1)
    elif action == "runs":
        runs(sys.argv[2:])
    else:
        raise SystemExit(f"Unknown action {action!r} (jaxprs, bindings or runs)")
