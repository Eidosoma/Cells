"""Row OL1-2: a closed world relaxes to exp(-F/k_BT). Row OL1-3a: its stationary law does not
depend on the catalysts.

Claim (§0.1, §7.1). In a closed world (no held species, no fission), the stationary law of the
event-pair dynamics is pi = exp(-F)/Z, whatever the kinetic factors s >= 0, catalysis included.

Derivation. Suppose a+_r(n) w(n) = a-_r(n') w(n') on every edge n -> n' = n + nu_r of the world's
finite state graph, with w = exp(-F). Then pi = w/Z satisfies detailed balance edge by edge, so
it balances the flow into and out of every state, and it is stationary. The registered closed
world is connected (``probes.closed_world_states`` builds it by search from the initial state),
so the chain is irreducible and pi is its unique stationary law. Catalysts change a+ and a- by
the same factor g(m) and leave the edge identity, hence pi, unchanged: that is row OL1-3a. The
reference decides the edge identity exactly, in RatExp, on every edge and under every token.

The check on the engine:
1. its rate table on every state of the closed world is turned into a generator, using only
   transitions to listed states (a rate that leads outside is a failure);
2. the generator's stationary law is solved in float64 (sparse LU, with one balance equation
   replaced by the normalisation);
3. its total variation from exp(-F)/Z, computed from the exact logarithms with a log-sum-exp,
   must be at most ``TV_ATOL``. It is set from the solve's conditioning: the generator's rates
   span under eight decades and the state count is 127, so the float solve errs by well under
   1e-12; ``TV_ATOL`` = 1e-10 leaves margin.
Kolmogorov's criterion on every square of the closed world is checked too, without conventions.

Planted controls (registered TVs from ``planted_tvs``): the factor at each direction's own state
(E1's form), a one-sided composition-dependent reverse rate (E2's lesson), and catalysis in the
forward direction only (row OL1-3a).

**The design's probes, reproduced** (self-tests of this enumerator, not engine thresholds):
- **E1** (§0.1): A <-> B <-> C in one assembly, N = 6, 28 states; forward rate constants 1 and
  K1 = 3, K2 = 1/2 (exp(-mu0) = 1, 3, 3/2); catalysts beta_1B = 5, beta_1C = 2 on A -> B and
  beta_2A = 7 on B -> C. The kinetic split (forward constants 1, reverse 1/K) is identified by
  reproduction: it is the one of four natural splits that gives the design's total variation,
  0.0829822, exactly. (Reverse constants 1 with forward K give 0.0842; the planted form's
  stationary law depends on the split, which a reversible law's does not.) The planted form's
  worst cycle ratio is 143/128 at (5, 1, 0).
- **E2** (§0.1): one assembly exchanging two types with a finite reservoir of 5 + 5 molecules,
  36 states; joins at M_i - n_i, the law pi(n) proportional to prod theta_i^n_i C(M_i, n_i)
  omega^(n_1 n_2) with theta = (2, 3), omega = 3/2 per contact, and leaves from that law,
  n_i theta_i^-1 omega^-n_j. The planted form drops omega from type 2's leave. Its total
  variation is 0.5407884 and its worst cycle ratio 2/3. Its per-contact omega is not §2.2's
  (1/2N) Sum chi n n, so E2 tests the enumerator only; the engine-facing regular-mixing world is
  ``ol1_wa_closed``.
"""

from __future__ import annotations

import math
from fractions import Fraction

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from .common import CheckResult
from .detailed_balance import kolmogorov, reference_table
from .exact import RatExp
from .laws import Law
from .probes import add
from .world import World, parse_world

TV_ATOL = 1e-10
E1_TV = 0.08298222756944511
E1_WORST_CYCLE = Fraction(143, 128)
E2_TV = 0.5407883773166593
E2_WORST_CYCLE = Fraction(2, 3)


# ---------------------------------------------------------------- generators and solves

def generator_from_table(world: World, states, a_plus, a_minus) -> sp.csr_matrix:
    """Q[i, j] = rate i -> j from a kernel table on a closed world's listed states."""
    idx = {tuple(int(v) for v in s): k for k, s in enumerate(states)}
    nus = [world.nu(st) for st in world.steps]
    rows, cols, vals = [], [], []
    a_plus, a_minus = np.asarray(a_plus, float), np.asarray(a_minus, float)
    for k, s in enumerate(states):
        n = tuple(int(v) for v in s)
        total = 0.0
        for r, nu in enumerate(nus):
            for rate, target in ((a_plus[k, r], add(n, nu)), (a_minus[k, r], add(n, nu, -1))):
                if rate > 0:
                    if target not in idx:
                        raise ValueError(f"a rate at {n} (step {world.steps[r].name}) leads outside the "
                                         f"listed states, to {target}")
                    rows.append(k)
                    cols.append(idx[target])
                    vals.append(float(rate))
                    total += float(rate)
        rows.append(k)
        cols.append(k)
        vals.append(-total)
    S = len(states)
    return sp.csr_matrix((vals, (rows, cols)), shape=(S, S))


def stationary_float(Q: sp.csr_matrix) -> np.ndarray:
    """pi Q = 0, Sum pi = 1, by a sparse LU solve with the last balance row replaced."""
    S = Q.shape[0]
    A = Q.T.tolil()
    A[S - 1, :] = np.ones(S)
    b = np.zeros(S)
    b[S - 1] = 1.0
    pi = spla.spsolve(A.tocsc(), b)
    return np.asarray(pi, float)


def stationary_exact(states, rates: dict) -> dict:
    """pi Q = 0 and Sum pi = 1 in rationals (Gauss-Jordan); rates = {state: {target: Fraction}}."""
    idx = {s: k for k, s in enumerate(states)}
    S = len(states)
    A = [[Fraction(0)] * (S + 1) for _ in range(S)]
    for x in states:
        tot = sum(rates[x].values(), Fraction(0))
        A[idx[x]][idx[x]] -= tot
        for y, r in rates[x].items():
            A[idx[y]][idx[x]] += r
    A[S - 1] = [Fraction(1)] * S + [Fraction(1)]
    for c in range(S):
        p = next(r for r in range(c, S) if A[r][c] != 0)
        A[c], A[p] = A[p], A[c]
        piv = A[c][c]
        A[c] = [v / piv for v in A[c]]
        for r in range(S):
            if r != c and A[r][c] != 0:
                f = A[r][c]
                A[r] = [a - f * b for a, b in zip(A[r], A[c])]
    return {s: A[idx[s]][S] for s in states}


def boltzmann(law: Law, states) -> np.ndarray:
    """exp(-F)/Z over the listed states, from the exact log-weights (log-sum-exp)."""
    lw = np.array([law.weight(tuple(int(v) for v in s)).log() for s in states])
    lw -= lw.max()
    w = np.exp(lw)
    return w / w.sum()


def total_variation(p, q) -> float:
    return 0.5 * float(np.sum(np.abs(np.asarray(p, float) - np.asarray(q, float))))


# ---------------------------------------------------------------- the exact edge identity

def exact_edge_identity(law: Law, states) -> CheckResult:
    """a+(n) w(n) == a-(n') w(n') exactly on every edge of the listed states."""
    listed = {tuple(int(v) for v in s) for s in states}
    n_edges, failing = 0, []
    for n in sorted(listed):
        wn = law.weight(n)
        for st in law.world.steps:
            f = law.forward(st, n)
            if f.is_zero():
                continue
            p = add(n, law.nu[st.name])
            if p not in listed:
                return CheckResult("exact_edge_identity", False,
                                   dict(problem=f"the edge {n} -> {p} leaves the listed states"))
            n_edges += 1
            if not (f * wn == law.reverse(st, p) * law.weight(p)):
                failing.append((n, st.name))
    return CheckResult("exact_edge_identity", n_edges > 0 and not failing,
                       dict(edges=n_edges, failing=len(failing), examples=failing[:5],
                            conventions=law.conv.as_dict()))


# ---------------------------------------------------------------- the check on a table

def check_closed_world(law: Law, states, a_plus, a_minus) -> dict:
    """Row OL1-2 on an engine's closed-world table, against exp(-F)/Z under the declared tokens."""
    out = {}
    try:
        Q = generator_from_table(law.world, states, a_plus, a_minus)
    except ValueError as exc:
        return {"generator": CheckResult("generator", False, dict(problem=str(exc)))}
    pi = stationary_float(Q)
    target = boltzmann(law, states)
    tv = total_variation(pi, target)
    out["stationary_law"] = CheckResult("stationary_law_is_exp_minus_F", tv <= TV_ATOL,
                                        dict(total_variation=tv, atol=TV_ATOL, states=len(states),
                                             min_pi=float(pi.min()), conventions=law.conv.as_dict()))
    out["kolmogorov"] = kolmogorov(law.world, states, a_plus, a_minus)
    return out


def planted_tvs(world: World, conv, states, forms: dict) -> dict:
    """Each planted form's total variation from exp(-F)/Z on the closed world (float solve)."""
    honest = Law(world, conv)
    target = boltzmann(honest, states)
    out = {}
    for label, (form, params) in forms.items():
        law = Law(world, conv, planted=form, planted_params=params)
        t = reference_table(law, states)
        pi = stationary_float(generator_from_table(world, states, t["a_plus"], t["a_minus"]))
        out[label] = total_variation(pi, target)
    return out


# ---------------------------------------------------------------- the design's E1 and E2

def e1_world() -> World:
    """The design's E1 as an ``ool_references.world@1`` world (not registered for the engine).

    Under ``count_on_m`` with N fixed, A -> B fires at k n_A g and its reverse at k- n_B g, with
    k- = k exp(mu0_B - mu0_A): the design's forward constants 1 and reverse constants 1/K."""
    def sp_(sid, em):
        em = Fraction(em)
        return {"id": sid, "moieties": {"x": 1},
                "standard_mu_RT": {"bilayer": {"exp_minus": str(em), "float": -math.log(em)}}}

    def st_(sid, r, p, cats):
        return {"id": sid, "locus": "membrane", "reactants": {f"{r}@membrane": 1}, "products": {f"{p}@membrane": 1},
                "forward_rate_per_s": {"exact": "1", "float": 1.0},
                "transition_state_factor": [{"catalyst": f"{c}@membrane", "beta": str(b), "ddG_kT": math.log1p(b)}
                                            for c, b in cats]}

    doc = {"format": "ool_references.world@1", "id": "design_e1",
           "standard_concentration_mM": {"exact": "1", "float": 1.0},
           "avogadro_per_mol": {"exact": "602214076000000000000000", "float": 6.02214076e23},
           "phases": {"membrane": {"kind": "condensed"}},
           "species": [sp_("A", 1), sp_("B", 3), sp_("C", Fraction(3, 2))],
           "places": [{"species": s, "phase": "membrane"} for s in ("A", "B", "C")],
           "steps": [st_("ab", "A", "B", [("B", 5), ("C", 2)]), st_("bc", "B", "C", [("A", 7)])]}
    return parse_world(doc)


def e1_states(N: int = 6) -> list:
    return [(a, b, N - a - b) for a in range(N + 1) for b in range(N + 1 - a)]


def exact_rates_dict(law: Law, states) -> dict:
    """{state: {target: Fraction}} for a law whose rates are rational (no chi)."""
    out = {}
    listed = set(states)
    for n in states:
        r = {}
        for st in law.world.steps:
            for val, target in ((law.forward(st, n), add(n, law.nu[st.name])),
                                (law.reverse(st, n), add(n, law.nu[st.name], -1))):
                if not val.is_zero():
                    if val.q != 0:
                        raise ValueError("exact_rates_dict needs rational rates (no regular mixing)")
                    if target not in listed:
                        raise ValueError(f"a rate at {n} leads outside the listed states, to {target}")
                    r[target] = r.get(target, Fraction(0)) + val.r
        out[n] = r
    return out


def e1_reproduction(form: str | None) -> dict:
    """E1's exact stationary law under the given form; TV from the product form, worst cycle."""
    from .world import Conventions

    w = e1_world()
    conv = Conventions(condensed_measure="multinomial", last_molecule="kept")
    law = Law(w, conv, planted=form)
    states = e1_states()
    pi = stationary_exact(states, exact_rates_dict(law, states))
    honest = Law(w, conv)
    wts = {s: honest.weight(s).r for s in states}
    Z = sum(wts.values(), Fraction(0))
    tv = sum(abs(pi[s] - wts[s] / Z) for s in states) / 2
    worst = Fraction(1)
    for (a, b, c) in states:
        if a >= 1 and b >= 1:
            n = (a, b, c)
            n1, n2, n3 = (a - 1, b + 1, c), (a - 1, b, c + 1), (a, b - 1, c + 1)
            ab, bc = w.steps
            fwd = law.forward(ab, n) * law.forward(bc, n1) * law.reverse(ab, n2) * law.reverse(bc, n3)
            bwd = law.forward(bc, n) * law.forward(ab, n3) * law.reverse(bc, n2) * law.reverse(ab, n1)
            ratio = (fwd / bwd).r
            if abs(math.log(ratio)) > abs(math.log(worst)):
                worst = ratio
    return dict(tv=tv, tv_float=float(tv), worst_cycle_ratio=worst, states=len(states))


def e2_reproduction(planted: bool) -> dict:
    """E2's exact stationary law (finite reservoir, per-contact omega), as the design states it."""
    M, theta, omega = (5, 5), (Fraction(2), Fraction(3)), Fraction(3, 2)
    states = [(i, j) for i in range(M[0] + 1) for j in range(M[1] + 1)]
    wt = {s: theta[0] ** s[0] * theta[1] ** s[1] * math.comb(M[0], s[0]) * math.comb(M[1], s[1])
          * omega ** (s[0] * s[1]) for s in states}
    Z = sum(wt.values(), Fraction(0))

    def rates(s):
        n1, n2 = s
        r = {}
        if n1 < M[0]:
            r[(n1 + 1, n2)] = Fraction(M[0] - n1)
        if n2 < M[1]:
            r[(n1, n2 + 1)] = Fraction(M[1] - n2)
        if n1 > 0:
            r[(n1 - 1, n2)] = n1 / theta[0] * omega ** (-n2)
        if n2 > 0:
            r[(n1, n2 - 1)] = n2 / theta[1] * (1 if planted else omega ** (-n1))
        return r

    table = {s: rates(s) for s in states}
    pi = stationary_exact(states, table)
    tv = sum(abs(pi[s] - wt[s] / Z) for s in states) / 2
    worst = Fraction(1)
    for i in range(M[0]):
        for j in range(M[1]):
            a, b, c, d = (i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)
            fwd = table[a][b] * table[b][c] * table[c][d] * table[d][a]
            bwd = table[a][d] * table[d][c] * table[c][b] * table[b][a]
            ratio = fwd / bwd
            if abs(math.log(ratio)) > abs(math.log(worst)):
                worst = ratio
    return dict(tv=tv, tv_float=float(tv), worst_cycle_ratio=worst, states=len(states))


def weight_ratio_is_exact(law: Law, n, p) -> RatExp:
    return law.weight(p) / law.weight(n)
