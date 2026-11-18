"""OL2's checks on probe tables (code-blind; ``ol2`` holds the law, ``population`` the runs).

A kernel probe gives, at each registered one-vesicle state (n, l, p) and for each declared
vesicle step c in the world's order, the forward rate a+ at the state, the rate of the reverse
event at the state, the two directions' lysis flags (the event's end state beyond sigma_max) and
the state's derived geometry.

- ``kolmogorov``: every registered square of two steps closes, Sum ln a around it = 0
  (convention-free cycle closure, §0.2b rule 2); squares through a lysing edge are skipped, and a
  square with a zero rate on one side only fails.
- ``identity``: ln a-(n') - ln a+(n) = F(n') - F(n) - w with the reference's F on every registered
  edge (§0.2b rule 2, the exact-F claim; the products' rule is not claimed).
- ``forward_form``: a+ = k E(m) rho0 theta+ for joins (both encounter tokens) and entries, OL1's
  count_on_m for membrane steps, the floor's zero pattern in both directions (§0.2c rule 5), and
  the lysis flags (strict sigma > sigma_max on the end state, §0.2c rule 8).
- ``geometry``: W, A, R, V_osm, V_sph, V and sigma at every registered state (§0.2c rules 4 and 6,
  §0.2d 1 and 3).
- ``stationary_check``: a closed world's generator relaxes to exp(-F)/Z (total variation).

Tolerances (registered): forward rates and geometry to 1e-12 relative (products of declared
floats); identity and cycle closure to 1e-8 absolute in ln a, which admits an engine that
evaluates F directly at |F| <= 1e6 k_BT (rounding about 2e-10 per evaluation; the registered
probe states reach 9.3e5); the tension to 1e-9 of k_BT N_A c_ext R/2 (a difference of two
near-equal densities); the stationary law to 1e-7 in total variation.
"""

from __future__ import annotations

import math

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from .ol2 import N_A, Law2, Vesicle2

FORWARD_RTOL = 1e-12
LOG_ATOL = 1e-8
GEOMETRY_RTOL = 1e-12
TENSION_RTOL = 1e-9
STATIONARY_TV = 1e-7
DERIVED = ("W", "A_m2", "R_m", "V_osm_L", "V_sph_L", "V_L", "tension_N_per_m")


def _ves(s):
    return Vesicle2(tuple(s[0]), tuple(s[1])), tuple(s[2])


def kernel_table(law: Law2, states) -> dict:
    """The reference's table at registered states: [S, C] arrays per direction."""
    chs = law.w.vesicle_channels()
    S, C = len(states), len(chs)
    out = {k: np.zeros((S, C)) for k in ("a_plus", "a_minus")}
    out["lyses_plus"] = np.zeros((S, C), dtype=bool)
    out["lyses_minus"] = np.zeros((S, C), dtype=bool)
    out["derived"] = np.zeros((S, len(DERIVED)))
    for i, s in enumerate(states):
        v, p = _ves(s)
        d = law.derived(v)
        out["derived"][i] = [d[k] for k in DERIVED]
        for c, ch in enumerate(chs):
            for sign, key in ((1, "plus"), (-1, "minus")):
                r = law.rate(v, p, ch, sign)
                out[f"a_{key}"][i, c] = r
                if r > 0:
                    out[f"lyses_{key}"][i, c] = law.lyses(law.after(v, p, ch, sign)[0])
    return out


def _key(v: Vesicle2, p) -> tuple:
    return (tuple(v.n), tuple(v.l), tuple(p))


def squares(law: Law2, states) -> list:
    """(state, step a, step b, [state + a, state + b, state + a + b]) with all four registered."""
    listed = {(tuple(s[0]), tuple(s[1]), tuple(s[2])) for s in states}
    chs = law.w.vesicle_channels()
    out = []
    for s in states:
        v, p = _ves(s)
        for a in range(len(chs)):
            e1 = law.after(v, p, chs[a], 1)
            if e1 is None:
                continue
            for b in range(a + 1, len(chs)):
                e2 = law.after(v, p, chs[b], 1)
                top = law.after(*e1, chs[b], 1)
                if e2 is None or top is None:
                    continue
                ks = [_key(*e1), _key(*e2), _key(*top)]
                if all(k in listed for k in ks):
                    out.append((_key(v, p), a, b, ks))
    return out


def kolmogorov(law: Law2, states, table) -> dict:
    idx = {(tuple(s[0]), tuple(s[1]), tuple(s[2])): i for i, s in enumerate(states)}
    ap, am = np.asarray(table["a_plus"], float), np.asarray(table["a_minus"], float)
    lp = np.asarray(table["lyses_plus"], bool)
    worst, checked, failing = 0.0, 0, 0
    for k0, a, b, (k1, k2, k3) in squares(law, states):
        i0, i1, i2, i3 = idx[k0], idx[k1], idx[k2], idx[k3]
        f = (ap[i0, a], ap[i1, b], am[i3, a], am[i2, b])
        g = (ap[i0, b], ap[i2, a], am[i3, b], am[i1, a])
        if lp[i0, a] or lp[i1, b] or lp[i0, b] or lp[i2, a]:
            continue
        if any(x <= 0 for x in f + g):
            if any(x > 0 for x in f) and any(x > 0 for x in g) and (all(x > 0 for x in f) != all(x > 0 for x in g)):
                checked += 1
                failing += 1
                worst = math.inf
            continue
        checked += 1
        if not all(math.isfinite(x) for x in f + g):
            failing += 1
            worst = math.inf
            continue
        res = abs(sum(math.log(x) for x in f) - sum(math.log(x) for x in g))
        failing += res > LOG_ATOL
        worst = max(worst, res)
    return dict(passed=checked > 0 and failing == 0, checked=checked, failing=failing, max_abs_log_ratio=worst,
                tolerance=LOG_ATOL)


def identity(law: Law2, states, table) -> dict:
    """ln a-(n') - ln a+(n) = F(n') - F(n) - w on every registered edge (n' not lysing)."""
    idx = {(tuple(s[0]), tuple(s[1]), tuple(s[2])): i for i, s in enumerate(states)}
    chs = law.w.vesicle_channels()
    ap, am = np.asarray(table["a_plus"], float), np.asarray(table["a_minus"], float)
    lp = np.asarray(table["lyses_plus"], bool)
    worst, checked, failing = 0.0, 0, 0
    for i, s in enumerate(states):
        v, p = _ves(s)
        for c, ch in enumerate(chs):
            if ap[i, c] <= 0 or lp[i, c]:
                continue
            v2, p2 = law.after(v, p, ch, 1)
            j = idx.get(_key(v2, p2))
            if j is None:
                continue
            checked += 1
            if not (am[j, c] > 0 and math.isfinite(am[j, c]) and math.isfinite(ap[i, c])):
                failing += 1
                worst = math.inf
                continue
            e = law.dF(v, p, v2, p2) - law.work(ch, +1)
            res = abs(math.log(am[j, c]) - math.log(ap[i, c]) - e)
            failing += res > LOG_ATOL
            worst = max(worst, res)
    return dict(passed=checked > 0 and failing == 0, checked=checked, failing=failing, max_abs_residual=worst,
                tolerance=LOG_ATOL)


def forward_form(law: Law2, states, table) -> dict:
    ref = kernel_table(law, states)
    eng, rf = np.asarray(table["a_plus"], float), ref["a_plus"]
    zero = int(np.sum((eng > 0) != (rf > 0)))
    both = (eng > 0) & (rf > 0)
    with np.errstate(invalid="ignore", divide="ignore"):
        res = np.abs(np.log(eng[both]) - np.log(rf[both])) if both.any() else np.zeros(0)
    res = np.where(np.isfinite(res), res, np.inf)
    worst = float(res.max()) if res.size else 0.0
    lys = int(np.sum(np.asarray(table["lyses_plus"], bool) != ref["lyses_plus"])
              + np.sum(np.asarray(table["lyses_minus"], bool) != ref["lyses_minus"]))
    rev_zero = int(np.sum((np.asarray(table["a_minus"], float) > 0) != (ref["a_minus"] > 0)))
    return dict(passed=zero == 0 and rev_zero == 0 and lys == 0 and worst <= FORWARD_RTOL,
                zero_pattern_mismatches=zero + rev_zero, lysis_flag_mismatches=lys, max_abs_log_residual=worst,
                tolerance=FORWARD_RTOL)


def geometry(law: Law2, states, table) -> dict:
    ref = kernel_table(law, states)["derived"]
    eng = np.asarray(table["derived"], float)
    if eng.shape != ref.shape:
        return dict(passed=False, problem=f"derived shape {eng.shape}, {ref.shape} expected")
    worst = {}
    failing = 0
    for c, name in enumerate(DERIVED):
        if name == "W":
            bad = int(np.sum(eng[:, c] != ref[:, c]))
            worst[name] = bad
            failing += bad
            continue
        if name == "tension_N_per_m":
            scale = np.array([law.w.kT * 1e3 * N_A * law.w.c_ext_M * law.radius(int(W)) / 2 for W in ref[:, 0]])
            d = np.abs(eng[:, c] - ref[:, c]) / np.maximum(scale, 1e-300)
            tol = TENSION_RTOL
        else:
            with np.errstate(invalid="ignore", divide="ignore"):
                d = np.abs(eng[:, c] - ref[:, c]) / np.abs(ref[:, c])
            d = np.where(ref[:, c] == 0, np.abs(eng[:, c]), d)
            tol = GEOMETRY_RTOL
        worst[name] = float(np.max(d)) if d.size else 0.0
        failing += int(np.sum(~(d <= tol)))
    return dict(passed=failing == 0, failing=failing, max_relative_difference=worst)


def stationary(transitions, states) -> np.ndarray:
    """The stationary law of the generator whose rates ``transitions(state)`` gives."""
    idx = {s: i for i, s in enumerate(states)}
    rows, cols, vals = [], [], []
    for s, i in idx.items():
        tot = 0.0
        for t, r in transitions(s):
            if t not in idx:
                raise ValueError(f"a rate leads outside the closed world: {t}")
            rows.append(i)
            cols.append(idx[t])
            vals.append(r)
            tot += r
        rows.append(i)
        cols.append(i)
        vals.append(-tot)
    n = len(idx)
    A = sp.csr_matrix((vals, (rows, cols)), shape=(n, n)).T.tolil()
    A[n - 1, :] = np.ones(n)
    b = np.zeros(n)
    b[n - 1] = 1.0
    return np.asarray(spla.spsolve(A.tocsc(), b))


def boltzmann(law: Law2, states, slots: int) -> np.ndarray:
    lw = -np.array([law.F(list(s[:slots]), s[slots]) for s in states])
    lw -= lw.max()
    w = np.exp(lw)
    return w / w.sum()


def closed_world_transitions(law: Law2, slots: int):
    """Transitions of a closed world of ``slots`` vesicles sharing a finite pool (vesicle steps
    only), on states (v_0, ..., v_{K-1}, p)."""
    chs = law.w.vesicle_channels()

    def tr(state):
        ves, p = list(state[:slots]), state[slots]
        out = []
        for j in range(slots):
            for ch in chs:
                for sign in (1, -1):
                    r = law.rate(ves[j], p, ch, sign)
                    if r > 0:
                        v2, p2 = law.after(ves[j], p, ch, sign)
                        nv = list(ves)
                        nv[j] = v2
                        out.append((tuple(nv) + (p2,), r))
        return out

    return tr


def stationary_from_table(states, slots: int, a_plus, a_minus, law: Law2):
    """The stationary law from a probe's own table on a closed world's registered states."""
    idx = {s: i for i, s in enumerate(states)}
    chs = law.w.vesicle_channels()

    def tr(state):
        i = idx[state]
        out = []
        for j in range(slots):
            for c, ch in enumerate(chs):
                for sign, arr in ((1, a_plus), (-1, a_minus)):
                    r = float(arr[i, j, c])
                    if r > 0:
                        v2, p2 = law.after(state[j], state[slots], ch, sign)
                        nv = list(state[:slots])
                        nv[j] = v2
                        out.append((tuple(nv) + (p2,), r))
        return out

    return stationary(tr, states)


def stationary_check(law: Law2, honest: Law2, states, slots: int, table=None) -> dict:
    """``table`` (a_plus, a_minus as [S, slots, C]) is a probe's; without it, ``law``'s own rates."""
    if table is None:
        pi = stationary(closed_world_transitions(law, slots), states)
    else:
        pi = stationary_from_table(states, slots, table["a_plus"], table["a_minus"], honest)
    tv = 0.5 * float(np.sum(np.abs(pi - boltzmann(honest, states, slots))))
    return dict(passed=tv <= STATIONARY_TV, total_variation=tv, tolerance=STATIONARY_TV)
