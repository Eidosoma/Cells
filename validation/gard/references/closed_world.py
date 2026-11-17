"""Row 4. The stationary law of a closed world: the product form for every beta.

Claim: in a closed world (M_i molecules of type i in all, a finite reservoir), the
pair-consistent kernel's stationary law is
    pi(x) proportional to (N - 1)! prod_i theta_i^{x_i} C(M_i, x_i),
    theta_i = k_f,i / (k_b,i V),
whatever beta is. The single-event form departs from it.

Derivation. The state space is {x : 0 <= x_i <= M_i, N >= 1}. The last molecule never
leaves, so N = 0, which would be absorbing, is excluded. The join x -> x + e_i runs at
k_f,i ((M_i - x_i)/V) N b_i(x). Its pair-consistent reverse runs at
k_b,i (x_i + 1) b_i(x). The ratio is theta_i N (M_i - x_i)/(x_i + 1). For the product
form above, pi(x + e_i)/pi(x) = N theta_i C(M_i, x_i + 1)/C(M_i, x_i), which is the
same. So pi satisfies detailed balance on every edge. The box is connected by these moves,
so pi is the unique stationary law, with no beta in it.

The product form is normalisable here because the state space is finite. With a held
reservoir the same measure, (N - 1)! prod (K_i rho_i)^{x_i}/x_i!, has mass marginal
proportional to s^N / N with s = Sum K_i rho_i (multinomial theorem). It is normalisable
only for s < 1, as a logarithmic series. The preprint's s = 100, so its lineage worlds
have no stationary law and the closed world carries this claim.

The finite-state master equation is solved exactly in rationals (Gauss-Jordan) for
N_G = 2 and 3 at small M, and in float64 (sparse LU) at larger M.

P2 (GARD_DESIGN §2.2; parameters from the design lane, relayed by the lead): M = (8, 8),
theta = 0.05, only beta_11 = 50. My solve gives the single-event form's total variation
from the product form as 0.579293 (registered as ``P2_TV_BETA11``). With only
beta_12 = 50 it gives 0.153475. The design's values are 0.5793 and 0.15.

The rank-one exception (GARD_DESIGN §2.5): if 1 + beta = u v^T, then
b_i(x) = u_i (v . x)/N. The single-event chain is then reversible, with
pi_se(x) proportional to pi(x) N / (v . x), a shifted equilibrium. This is checked
exactly.

Planted control: the single-event form must depart (total variation above
``TV_DEPARTS``) wherever beta is not rank-one-shifted.
"""

from __future__ import annotations

import itertools
import math
from fractions import Fraction

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from .common import CheckResult
from .kernels import ClosedReservoir, ExactLaw, ExchangeLaw, propensities

TV_FLOAT_ATOL = 1e-10
TV_DEPARTS = 1e-6
P2_TV_BETA11 = 0.579293
P2_TV_BETA12 = 0.153475


def closed_states(M) -> list[tuple[int, ...]]:
    return [x for x in itertools.product(*[range(m + 1) for m in M]) if sum(x) >= 1]


def exact_rates(law: ExactLaw, states) -> dict:
    """Outgoing rates per state, exact."""
    out = {}
    G = law.n_types
    for x in states:
        ap, am = law.propensities(x)
        r = {}
        for i in range(G):
            if ap[i] > 0:
                y = list(x); y[i] += 1
                r[tuple(y)] = ap[i]
            if am[i] > 0:
                y = list(x); y[i] -= 1
                r[tuple(y)] = am[i]
        out[x] = r
    return out


def stationary_exact(states, rates) -> dict:
    """Solve pi Q = 0, sum pi = 1 in rationals (Gauss-Jordan); returns {state: Fraction}."""
    idx = {s: k for k, s in enumerate(states)}
    n = len(states)
    A = [[Fraction(0)] * (n + 1) for _ in range(n)]
    for x in states:
        tot = sum(rates[x].values(), Fraction(0))
        A[idx[x]][idx[x]] -= tot
        for y, r in rates[x].items():
            A[idx[y]][idx[x]] += r
    A[n - 1] = [Fraction(1)] * n + [Fraction(1)]
    for c in range(n):
        p = next(r for r in range(c, n) if A[r][c] != 0)
        A[c], A[p] = A[p], A[c]
        piv = A[c][c]
        A[c] = [v / piv for v in A[c]]
        for r in range(n):
            if r != c and A[r][c] != 0:
                f = A[r][c]
                A[r] = [a - f * b for a, b in zip(A[r], A[c])]
    return {s: A[idx[s]][n] for s in states}


def product_form_exact(law: ExactLaw, states) -> dict:
    w = {x: law.weight(x) for x in states}
    Z = sum(w.values(), Fraction(0))
    return {x: w[x] / Z for x in states}


def generator_float(law: ExchangeLaw, states) -> sp.csr_matrix:
    idx = {s: k for k, s in enumerate(states)}
    I, J, V = [], [], []
    G = law.n_types
    for x in states:
        xa = np.asarray(x, dtype=np.int64)
        ap, am = propensities(law, xa)
        tot = 0.0
        for i in range(G):
            for rate, step in ((ap[i], 1), (am[i], -1)):
                if rate > 0:
                    y = list(x); y[i] += step
                    I.append(idx[x]); J.append(idx[tuple(y)]); V.append(rate); tot += rate
        I.append(idx[x]); J.append(idx[x]); V.append(-tot)
    n = len(states)
    return sp.csr_matrix((V, (I, J)), shape=(n, n))


def generator_from_table(states, join: np.ndarray, leave: np.ndarray) -> sp.csr_matrix:
    """A generator from tabulated propensities (closed-world rates) at the listed states."""
    idx = {tuple(int(v) for v in s): k for k, s in enumerate(states)}
    I, J, V = [], [], []
    for k, s in enumerate(states):
        x = tuple(int(v) for v in s)
        tot = 0.0
        for i in range(len(x)):
            for rate, step in ((join[k, i], 1), (leave[k, i], -1)):
                if rate > 0:
                    y = list(x); y[i] += step
                    y = tuple(y)
                    if y not in idx:
                        raise ValueError(f"rate from {x} leads outside the listed states to {y}")
                    I.append(k); J.append(idx[y]); V.append(float(rate)); tot += float(rate)
        I.append(k); J.append(k); V.append(-tot)
    n = len(states)
    return sp.csr_matrix((V, (I, J)), shape=(n, n))


def stationary_float(Q: sp.csr_matrix) -> np.ndarray:
    n = Q.shape[0]
    A = Q.T.tolil()
    A[n - 1, :] = np.ones(n)
    rhs = np.zeros(n)
    rhs[-1] = 1.0
    return spla.spsolve(A.tocsc(), rhs)


def product_form_float(states, theta, M) -> np.ndarray:
    theta = np.broadcast_to(np.asarray(theta, dtype=np.float64), (len(M),))
    lw = np.array([math.lgamma(sum(x)) + sum(x[i] * math.log(theta[i]) + math.log(math.comb(M[i], x[i]))
                                             for i in range(len(M))) for x in states])
    p = np.exp(lw - lw.max())
    return p / p.sum()


def theta_law(beta, theta, M, form) -> ExchangeLaw:
    """A closed world in the theta parameterisation: k_f = theta, k_b = 1, V = 1."""
    G = len(M)
    return ExchangeLaw(np.asarray(beta, dtype=np.float64), np.full(G, float(theta)), np.ones(G),
                       ClosedReservoir(np.asarray(M, dtype=np.float64), 1.0), form)


def check_closed_world_float(beta, theta, M, form: str) -> CheckResult:
    states = closed_states(M)
    law = theta_law(beta, theta, M, form)
    pi = stationary_float(generator_float(law, states))
    p0 = product_form_float(states, theta, M)
    tv = float(0.5 * np.abs(pi - p0).sum())
    expect_match = form == "pair-consistent"
    passed = tv <= TV_FLOAT_ATOL if expect_match else tv > TV_DEPARTS
    return CheckResult("closed_world_stationary_law", bool(passed), dict(
        form=form, M=list(M), theta=theta, states=len(states), total_variation=tv,
        tolerance=TV_FLOAT_ATOL if expect_match else TV_DEPARTS))


def _exact(value) -> Fraction:
    """Read a decimal float by its repr (0.05 -> 1/20) so decimal parameters stay exact."""
    return Fraction(repr(float(value))) if isinstance(value, float) else Fraction(value)


def check_closed_world_exact(beta, theta, M, form: str) -> CheckResult:
    states = closed_states(M)
    law = ExactLaw.make(beta, _exact(theta), 1, form, total=M, volume=1)
    pi = stationary_exact(states, exact_rates(law, states))
    p0 = product_form_exact(law, states)
    tv = sum((abs(pi[s] - p0[s]) for s in states), Fraction(0)) / 2
    expect_match = form == "pair-consistent"
    passed = (tv == 0) if expect_match else (tv > 0)
    return CheckResult("closed_world_stationary_law_exact", bool(passed), dict(
        form=form, M=list(M), theta=str(theta), states=len(states), total_variation=float(tv), exact_zero=tv == 0))


def check_rank_one_exception(u, v, theta, M) -> CheckResult:
    """Single-event chain with 1 + beta = u v^T: stationary law pi(x) N / (v . x), exactly."""
    G = len(M)
    beta = [[Fraction(u[i]) * Fraction(v[j]) - 1 for j in range(G)] for i in range(G)]
    if any(b < 0 for row in beta for b in row):
        raise ValueError("u v^T - 1 must be nonnegative")
    states = closed_states(M)
    law = ExactLaw.make(beta, _exact(theta), 1, "single-event", total=M, volume=1)
    pi = stationary_exact(states, exact_rates(law, states))
    w = {x: law.weight(x) * Fraction(sum(x), sum(Fraction(v[j]) * x[j] for j in range(G))) for x in states}
    Z = sum(w.values(), Fraction(0))
    ok = all(pi[x] == w[x] / Z for x in states)
    return CheckResult("rank_one_exception", ok, dict(M=list(M), u=[str(a) for a in u], v=[str(a) for a in v]))


def check_closed_table(states, join, leave, theta, M, form: str) -> CheckResult:
    """Row 4 against the engine: its propensities on a closed world, already in closed-world form."""
    states = [tuple(int(v) for v in s) for s in np.asarray(states)]
    want = set(closed_states(M))
    if set(states) != want:
        return CheckResult("closed_world_engine_table", False, dict(
            error="the table's states are not the closed world's state space",
            missing=len(want - set(states)), extra=len(set(states) - want)))
    pi = stationary_float(generator_from_table(states, np.asarray(join), np.asarray(leave)))
    p0 = product_form_float(states, theta, M)
    tv = float(0.5 * np.abs(pi - p0).sum())
    expect_match = form == "pair-consistent"
    passed = tv <= TV_FLOAT_ATOL if expect_match else tv > TV_DEPARTS
    return CheckResult("closed_world_engine_table", bool(passed), dict(
        form=form, M=list(M), theta=theta, total_variation=tv))


def held_to_closed(states, join_held, leave, rho_held, k_join, k_leave, theta, M):
    """Convert a held-supply kernel table to closed-world rates.

    The join is linear in rho, so a_closed = a_held (M_i - x_i)/(V rho_i) with
    V = k_f/(k_b theta). The leave does not depend on the reservoir.
    """
    states = np.asarray(states, dtype=np.float64)
    K = np.asarray(k_join, dtype=np.float64) / np.asarray(k_leave, dtype=np.float64)
    V = K / float(theta)
    scale = (np.asarray(M, dtype=np.float64)[None, :] - states) / (V[None, :] * np.asarray(rho_held)[None, :])
    return np.asarray(join_held) * scale, np.asarray(leave)
