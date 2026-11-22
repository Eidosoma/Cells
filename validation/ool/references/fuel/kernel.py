"""Rows OL4-1 and OL4-2: the pair identity with fuel, and the cycle's drive, on kernel tables.

**OL4-1, the pair identity with fuel** (fuel note §5 check 1). For every step r and listed state n,
    ln a+_r(n) - ln a-_r(n') = -(F(n') - F(n)) + w_r,   w_r = -Sum_held nu_h mu_h,
with mu_h = mu0_h + ln(c_h/c0) (engine note §0.1, §3.1). The reference decides it exactly
(``laws.Law``: rates of the form r e^q, compared on (r, q)); on an engine's float table it is
checked by OL1's ``detailed_balance.identity`` within 64u(4 + |ln a+| + |ln a-| + |Delta F|).
The forward form a+ = k g(m) E(m) theta+(n) and the reverse rates are compared too
(``compare_rates``), so a propensity error that a consistent reverse would hide is still seen.

**OL4-2, the cycle's drive** (fuel note §5 check 3). Around any closed path of events in the
state space, Sum ln(a_along/a_back) = Sum_k (-Delta F_k + w_k) = Sum_k w_k, because F returns to its
value. So around a cycle that turns one fuel molecule into waste,
    Sum ln(a+/a-) = mu_F - mu_W,
and around every cycle that turns none it is 0: Kolmogorov's criterion then fails by exactly the
drive, on the fuel cycles only. In state space the fuel cycle has five steps: the recharge f1, B's
join, the core step a_i, the decay d_i and S's leave (the reverse of jS). The registered cycles
are:
- ``fuel``: that loop, through L1 and through L2, in two orders whose intermediate states differ
  (expected mu_F - mu_W);
- ``block``: in a held-block world, B's join from the held pool, a_i, d_i and S's leave to the held
  pool (expected mu_B - mu_S);
- ``exchange``: a1, d1, d2 reversed, a2 reversed: one L1 made from B and decayed, one L2 made from S
  and returned to B (expected 0);
- and OL1's squares and parallel two-cycles (``probes``), which close at any drive.
The expected value of each cycle is exp(Sum w) as an exact rational; in the reference the product
of the rate ratios around the cycle equals it exactly.

Planted: a fuel step without its reservoir work (OL4-1, residual |w|; OL4-2 off by the drive), the
drive of the wrong sign (off by twice the drive), the held activities dropped, the core step's
extent N(n) - r + 1 (forward form, ln(N/(N - 1))), the factor at each direction's own state
(OL1's E1 form) and catalysis on the forward channel only.
"""

from __future__ import annotations

import math
from fractions import Fraction

import numpy as np

from ..common import UNIT_ROUNDOFF, CheckResult
from ..detailed_balance import TOL_FACTOR, compare_rates, identity, kolmogorov, reference_table
from ..exact import RatExp
from ..probes import add, base_states, boundary_states, step_pairs, valid
from ..world import World

U = UNIT_ROUNDOFF


# ---------------------------------------------------------------------------- cycles

def _steps(world: World) -> dict:
    return {st.name: k for k, st in enumerate(world.steps)}


def cycle_templates(world: World) -> list:
    """(kind, [(step, sign), ...]) for every cycle shape the world's steps allow."""
    names = _steps(world)
    held = {p.species for p in world.places.values() if p.held}
    out = []
    for i in ("1", "2"):
        a, d = f"a{i}", f"d{i}"
        if "f1" in names and {"F", "W"} <= held:          # with finite fuel the loop does not close
            out.append(("fuel", [("f1", 1), ("jB", 1), (a, 1), (d, 1), ("jS", -1)]))
            out.append(("fuel", [("jS", -1), ("f1", 1), (a, 1), ("jB", 1), (d, 1)]))
        if "f1" not in names and {"B", "S"} <= held:
            out.append(("block", [("jB", 1), (a, 1), (d, 1), ("jS", -1)]))
            out.append(("block", [(a, 1), ("jB", 1), ("jS", -1), (d, 1)]))
    out.append(("exchange", [("a1", 1), ("d1", 1), ("d2", -1), ("a2", -1)]))
    return [(k, [(s, g) for s, g in path if s in names]) for k, path in out
            if all(s in names for s, _ in path)]


def walk(world: World, start, path) -> list | None:
    """The states visited by a path of events from ``start``, or None if a count goes negative or
    a reactant is missing on the way (the cycle must close where it started)."""
    names = _steps(world)
    n = tuple(int(v) for v in start)
    out = [n]
    for s, g in path:
        st = world.steps[names[s]]
        need = world.alpha(st) if g > 0 else world.beta_finite(st)
        if any(v < a for v, a in zip(n, need)):
            return None
        n = add(n, world.nu(st), g)
        if not valid(n):
            return None
        out.append(n)
    if out[-1] != out[0]:
        raise ValueError(f"path {path} does not close")
    return out


def registered_cycles(world: World, bases) -> list:
    """Every template from every base state where it is feasible, with a non-empty membrane at
    every visited state (``kept`` never empties it)."""
    mem = world.membrane_mask()
    out = []
    for n in bases:
        for kind, path in cycle_templates(world):
            states = walk(world, n, path)
            if states is None:
                continue
            if any(sum(v for v, m in zip(s, mem) if m) < 1 for s in states):
                continue
            out.append(dict(kind=kind, start=[int(v) for v in n], path=[[s, g] for s, g in path]))
    return out


def expected_exp(law, cycle: dict) -> Fraction:
    """exp(Sum_k w_k) around the cycle, exactly (exp(w) = 1/exp_minus_w per forward event)."""
    names = _steps(law.world)
    out = Fraction(1)
    for s, g in cycle["path"]:
        emw = law.exp_minus_w(law.world.steps[names[s]])
        out *= (1 / emw) ** g
    return out


def exact_cycle_product(law, cycle: dict) -> RatExp:
    """Prod_k a_along(n_k)/a_back(n_{k+1}) in the reference's exact law."""
    names = _steps(law.world)
    states = walk(law.world, cycle["start"], [(s, g) for s, g in cycle["path"]])
    out = RatExp(1)
    for k, (s, g) in enumerate(cycle["path"]):
        st = law.world.steps[names[s]]
        n, p = states[k], states[k + 1]
        along = law.forward(st, n) if g > 0 else law.reverse(st, n)
        back = law.reverse(st, p) if g > 0 else law.forward(st, p)
        out = out * along / back
    return out


def check_cycles(law, states, a_plus, a_minus, cycles) -> CheckResult:
    """OL4-2 on a table: each registered cycle's Sum ln(a_along/a_back) against ln exp(Sum w)."""
    idx = {tuple(int(v) for v in s): k for k, s in enumerate(states)}
    names = _steps(law.world)
    ap, am = np.asarray(a_plus, float), np.asarray(a_minus, float)
    worst, failing, checked, examples, by_kind = 0.0, 0, 0, [], {}
    for cyc in cycles:
        path = [(s, g) for s, g in cyc["path"]]
        sts = walk(law.world, cyc["start"], path)
        terms = []
        missing = False
        for k, (s, g) in enumerate(path):
            r = names[s]
            i, j = idx.get(sts[k]), idx.get(sts[k + 1])
            if i is None or j is None:
                missing = True
                break
            along = ap[i, r] if g > 0 else am[i, r]
            back = am[j, r] if g > 0 else ap[j, r]
            terms += [along, back]
        if missing:
            failing += 1
            examples.append(dict(cycle=cyc, problem="a state of the cycle is not in the table"))
            continue
        checked += 1
        if min(terms) <= 0 or not all(math.isfinite(t) for t in terms):
            failing += 1
            if len(examples) < 5:
                examples.append(dict(cycle=cyc, problem="a rate on the cycle is zero or infinite"))
            continue
        logs = [math.log(t) for t in terms]
        value = sum(logs[0::2]) - sum(logs[1::2])
        target = math.log(expected_exp(law, cyc))
        res = value - target
        tol = TOL_FACTOR * U * (len(logs) + sum(abs(x) for x in logs) + abs(target))
        by_kind.setdefault(cyc["kind"], []).append(value)
        worst = max(worst, abs(res))
        if abs(res) > tol:
            failing += 1
            if len(examples) < 5:
                examples.append(dict(kind=cyc["kind"], start=cyc["start"], value=value, expected=target,
                                     residual=res, tol=tol))
    summary = {k: dict(count=len(v), min=min(v), max=max(v)) for k, v in by_kind.items()}
    return CheckResult("cycle_drive", checked > 0 and failing == 0,
                       dict(cycles_checked=checked, cycles_failing=failing, max_abs_residual=worst,
                            sums_by_kind=summary, world=law.world.name, examples=examples))


def exact_cycles(law, cycles) -> CheckResult:
    """In the reference, every cycle's rate-ratio product equals exp(Sum w) exactly."""
    bad = []
    for cyc in cycles:
        prod = exact_cycle_product(law, cyc)
        if not (prod.q == 0 and prod.r == expected_exp(law, cyc)):
            bad.append(dict(kind=cyc["kind"], start=cyc["start"], product=repr(prod),
                            expected=str(expected_exp(law, cyc))))
    return CheckResult("exact_cycle_drive", len(cycles) > 0 and not bad,
                       dict(cycles=len(cycles), failing=len(bad), examples=bad[:5], world=law.world.name))


# ---------------------------------------------------------------------------- probe states

def probe_states(world: World, seed: int, n_base: int, max_count: int) -> tuple:
    """(states, bases): the kernel probe of a fuel world. The base states are OL1's seeded draws;
    the probe adds each base's one-event neighbours, every square's corners, every registered
    cycle's states, and OL1's boundary states (the empty state, one and two molecules of each place
    alone, each membrane step's reactant-only and product-only states)."""
    nus = [world.nu(st) for st in world.steps]
    bases = base_states(world, seed, n_base, max_count)
    states = set(boundary_states(world))
    for n in bases:
        states.add(n)
        for r in range(len(nus)):
            for sign in (1, -1):
                p = add(n, nus[r], sign)
                if valid(p):
                    states.add(p)
        for r, q in step_pairs(world):
            corners = [add(n, nus[r]), add(n, nus[q]), add(add(n, nus[r]), nus[q])]
            if all(valid(c) for c in corners):
                states.update(corners)
    cycles = registered_cycles(world, bases)
    for cyc in cycles:
        states.update(walk(world, cyc["start"], [(s, g) for s, g in cyc["path"]]))
    return np.array(sorted(states), dtype=np.int64), bases, cycles


# ---------------------------------------------------------------------------- the row

def check_kernel(law, states, a_plus, a_minus, cycles, ref: dict | None = None) -> dict:
    """Every OL4-1 and OL4-2 check on one kernel table."""
    ref = reference_table(law, states) if ref is None else ref
    return {
        "kolmogorov_squares": kolmogorov(law.world, states, a_plus, a_minus),
        "identity": identity(law, states, a_plus, a_minus, ref),
        "forward_form": compare_rates(law, states, a_plus, a_minus, "forward", ref),
        "reverse_rates": compare_rates(law, states, a_plus, a_minus, "reverse", ref),
        "cycle_drive": check_cycles(law, states, a_plus, a_minus, cycles),
    }
