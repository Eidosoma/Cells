"""Row OL1-1 (and OL1-4a): every channel keeps local detailed balance; the forward form is
the declared kinetics.

Claim (§0.1, §2.1, §7.1). For every step r and state n, ln(a+_r(n)/a-_r(n + nu_r)) = -DeltaF_r(n),
with F the one free-energy function of §2.2, and a+_r(n) = k g(m) E(m) theta+(n) (§2.1, §2.4).

Three checks on the engine's kernel table at the registered probe states, from the weakest
assumption to the strongest:

1. **Kolmogorov's criterion, convention-free.** On every registered square (n, r, q), the
   product of the rates around the cycle n -> n + nu_r -> n + nu_r + nu_q -> n + nu_q -> n
   equals the product around the reverse cycle; and for parallel steps (equal net change) the
   two-cycle n -> n + nu by one step and back by the other closes. This holds for every F, so
   it needs no declared convention and cannot be satisfied by comparing the engine with itself.
   It does not see a wrong F, a sign error in DeltaF, or a wrong forward form: dynamics that are
   reversible with respect to some other function pass it.
2. **The identity with the reference's F,** under the declared conventions:
   |ln a-_r(n + nu) - ln a+_r(n) - DeltaF_r(n)| on every listed edge. It catches a wrong F (a
   wrong mixing measure, Stirling for ln n!, a sign error), which Kolmogorov cannot.
3. **The forward form** (row OL1-4a): a+ equals k g(m) E(m) theta+(n) with falling factorials,
   the encounter volume's power and the held activities' c0. It catches the propensity errors
   that a consistent reverse would hide from checks 1 and 2.

Tolerances (derived). Each log-rate the engine reports carries an absolute error of at most a
few units of roundoff times (1 + |ln a| + |DeltaF|), from forming a product of at most a dozen
factors and one exponential. A sum of eight such logs therefore errs by at most
8 * 8 u (1 + max |ln a| + |DeltaF|); the tolerance used is 64 u (8 + Sum |ln a| + Sum |DeltaF|),
which bounds it with margin. For the registered probe (counts at most 14, |ln a| < 30) it is
below 3e-12. Every planted form misses it by at least nine orders of magnitude (README.md).

Boundary channels: under ``last_molecule = extinct`` a channel that empties the membrane is
one-way (the empty state is absorbing). It is excluded from checks 1 and 2, and its rate is
compared with the continued form directly (``compare_rates``).
"""

from __future__ import annotations

import math

import numpy as np

from .common import UNIT_ROUNDOFF, CheckResult
from .laws import Law
from .probes import add, squares, two_cycles
from .world import World

U = UNIT_ROUNDOFF
TOL_FACTOR = 64.0


def reference_table(law: Law, states) -> dict:
    """The reference's exact rates at every listed state, as float arrays and exact logs."""
    S, R = len(states), len(law.world.steps)
    a_plus = np.zeros((S, R))
    a_minus = np.zeros((S, R))
    ln_plus = np.full((S, R), -np.inf)
    ln_minus = np.full((S, R), -np.inf)
    one_way_plus = np.zeros((S, R), dtype=bool)
    one_way_minus = np.zeros((S, R), dtype=bool)
    delta = np.full((S, R), np.nan)
    for k, s in enumerate(states):
        p = tuple(int(v) for v in s)
        for r, st in enumerate(law.world.steps):
            f = law.forward(st, p)
            b = law.reverse(st, p)
            if not f.is_zero():
                ln_plus[k, r] = f.log()
                a_plus[k, r] = math.exp(ln_plus[k, r])
                one_way_plus[k, r] = law.one_way_forward(st, p)
                if not one_way_plus[k, r]:
                    delta[k, r] = law.delta_F_minus_w(st, p)
            if not b.is_zero():
                ln_minus[k, r] = b.log()
                a_minus[k, r] = math.exp(ln_minus[k, r])
                one_way_minus[k, r] = law.one_way_reverse(st, p)
    return dict(a_plus=a_plus, a_minus=a_minus, ln_plus=ln_plus, ln_minus=ln_minus, one_way_plus=one_way_plus,
                one_way_minus=one_way_minus, delta_F_minus_w=delta)


def _index(states) -> dict:
    return {tuple(int(v) for v in s): k for k, s in enumerate(states)}


def _logs(a: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore"):
        return np.where(a > 0, np.log(np.where(a > 0, a, 1.0)), -np.inf)


def kolmogorov(world: World, states, a_plus, a_minus) -> CheckResult:
    """Kolmogorov's criterion on every registered square and two-cycle (convention-free).

    A cycle is checked when all its rates are positive. One-way boundary channels (the
    extinct boundary) lead to or from the absorbing empty membrane, which no square of
    positive rates can contain, so no token is needed to skip them."""
    idx = _index(states)
    lp, lm = _logs(np.asarray(a_plus, float)), _logs(np.asarray(a_minus, float))
    nus = [world.nu(st) for st in world.steps]
    worst, n_checked, n_fail, n_skipped, examples = 0.0, 0, 0, 0, []
    for n, r, q in squares(world, states):
        a, b, c = idx[n], idx[add(n, nus[r])], idx[add(n, nus[q])]
        top = idx[add(add(n, nus[r]), nus[q])]
        terms_f = (lp[a, r], lp[b, q], lm[top, r], lm[c, q])
        terms_b = (lp[a, q], lp[c, r], lm[top, q], lm[b, r])
        if not all(np.isfinite(terms_f + terms_b)):
            n_skipped += 1
            continue
        res = sum(terms_f) - sum(terms_b)
        tol = TOL_FACTOR * U * (8 + sum(abs(t) for t in terms_f + terms_b))
        n_checked += 1
        if abs(res) > tol:
            n_fail += 1
            if len(examples) < 5:
                examples.append(dict(n=n, steps=(world.steps[r].name, world.steps[q].name), residual=res, tol=tol))
        worst = max(worst, abs(res))
    for n, r, q in two_cycles(world, states):
        a, b = idx[n], idx[add(n, nus[r])]
        terms = (lp[a, r], lm[b, q], lp[a, q], lm[b, r])
        if not all(np.isfinite(terms)):
            n_skipped += 1
            continue
        res = terms[0] + terms[1] - terms[2] - terms[3]
        tol = TOL_FACTOR * U * (4 + sum(abs(t) for t in terms))
        n_checked += 1
        if abs(res) > tol:
            n_fail += 1
            if len(examples) < 5:
                examples.append(dict(n=n, steps=(world.steps[r].name, world.steps[q].name), residual=res, tol=tol,
                                     cycle="parallel"))
        worst = max(worst, abs(res))
    return CheckResult("kolmogorov", n_checked > 0 and n_fail == 0,
                       dict(cycles_checked=n_checked, cycles_failing=n_fail, cycles_skipped=n_skipped,
                            max_abs_log_ratio=worst, examples=examples))


def identity(law: Law, states, a_plus, a_minus, ref: dict | None = None) -> CheckResult:
    """ln a-(n + nu) - ln a+(n) = F(n + nu) - F(n) - w under the reference's F and the declared
    conventions, on every listed edge whose forward rate the reference gives as positive and
    two-way."""
    ref = reference_table(law, states) if ref is None else ref
    idx = _index(states)
    lp, lm = _logs(np.asarray(a_plus, float)), _logs(np.asarray(a_minus, float))
    worst, n_checked, n_fail, examples = 0.0, 0, 0, []
    for st_i, st in enumerate(law.world.steps):
        nu = law.nu[st.name]
        for n, k in idx.items():
            p = add(n, nu)
            if p not in idx or not np.isfinite(ref["ln_plus"][k, st_i]) or ref["one_way_plus"][k, st_i]:
                continue
            if not (np.isfinite(lp[k, st_i]) and np.isfinite(lm[idx[p], st_i])):
                n_checked += 1
                n_fail += 1
                if len(examples) < 5:
                    examples.append(dict(n=n, step=st.name, problem="a rate the reference gives as positive is zero"))
                continue
            dF = float(ref["delta_F_minus_w"][k, st_i])
            res = (lm[idx[p], st_i] - lp[k, st_i]) - dF
            tol = TOL_FACTOR * U * (4 + abs(lp[k, st_i]) + abs(lm[idx[p], st_i]) + abs(dF))
            n_checked += 1
            if abs(res) > tol:
                n_fail += 1
                if len(examples) < 5:
                    examples.append(dict(n=n, step=st.name, residual=res, tol=tol))
            worst = max(worst, abs(res))
    return CheckResult("identity_with_reference_F", n_checked > 0 and n_fail == 0,
                       dict(edges_checked=n_checked, edges_failing=n_fail, max_abs_residual=worst,
                            conventions=law.conv.as_dict(), examples=examples))


def compare_rates(law: Law, states, a_plus, a_minus, which: str = "forward", ref: dict | None = None) -> CheckResult:
    """The engine's forward (or reverse) rates against the reference's, state by state."""
    ref = reference_table(law, states) if ref is None else ref
    eng = np.asarray(a_plus if which == "forward" else a_minus, float)
    lref = ref["ln_plus"] if which == "forward" else ref["ln_minus"]
    leng = _logs(eng)
    zero_mismatch = int(np.sum(np.isfinite(lref) != np.isfinite(leng)))
    both = np.isfinite(lref) & np.isfinite(leng)
    res = np.zeros_like(lref)
    res[both] = leng[both] - lref[both]
    dF = np.nan_to_num(np.abs(ref["delta_F_minus_w"]), nan=0.0).max() if which == "reverse" else 0.0
    tol = TOL_FACTOR * U * (4 + 2 * np.abs(np.where(both, lref, 0.0)) + dF)
    bad = np.argwhere(np.abs(res) > tol)
    examples = [dict(state=tuple(int(v) for v in states[k]), step=law.world.steps[r].name, residual=float(res[k, r]))
                for k, r in bad[:5]]
    return CheckResult(f"{which}_rates_match_reference",
                       zero_mismatch == 0 and len(bad) == 0,
                       dict(entries=int(both.sum()), zero_pattern_mismatches=zero_mismatch, failing=int(len(bad)),
                            max_abs_log_residual=float(np.max(np.abs(res))) if res.size else 0.0,
                            conventions=law.conv.as_dict(), examples=examples))


def check_kernel_table(law: Law, states, a_plus, a_minus, ref: dict | None = None) -> dict:
    """All row OL1-1 and OL1-4a checks on one kernel table; returns {name: CheckResult}.

    ``ref`` is the reference's table for ``law`` on ``states`` (computed when not given)."""
    ref = reference_table(law, states) if ref is None else ref
    return {
        "kolmogorov": kolmogorov(law.world, states, a_plus, a_minus),
        "identity": identity(law, states, a_plus, a_minus, ref),
        "forward_form": compare_rates(law, states, a_plus, a_minus, "forward", ref),
        "reverse_rates": compare_rates(law, states, a_plus, a_minus, "reverse", ref),
    }
