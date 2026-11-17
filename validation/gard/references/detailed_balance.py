"""Row 3. Local detailed balance of the pair-consistent form; the single-event form is
refused as passive.

Claim: for every propensity pair, ln(a_i^+(x) / a_i^-(x + e_i)) equals the declared
affinity A_i(x) = ln(K_i rho_i N / (x_i + 1)) to rounding. K_i = k_f,i / k_b,i, and
in a closed world rho_i = (M_i - x_i)/V. A law that fails is refused as passive.

Derivation (pair-consistent). a_i^+(x) = k_f,i rho_i N b_i(x). The reverse leave from
x + e_i carries b_i((x + e_i) - e_i) = b_i(x). The ratio is k_f,i rho_i N /
(k_b,i (x_i + 1)) = exp A_i(x), with no beta in it.

The single-event form (preprint p. 10) uses b_i at the pre-event state, so its leave
from x + e_i carries b_i(x + e_i) = 1 + ((beta x)_i + beta_ii)/(N + 1). The residual is
ln[b_i(x) / b_i(x + e_i)], zero only when (beta x)_i = N beta_ii. The arriving molecule
catalyses its own leave through beta_ii, and the weights dilute from 1/N to 1/(N + 1).

P1, the unit square x -> +e_1 -> +e_2 -> -e_1 -> -e_2 in a two-type world with only
beta_11 = beta nonzero. The single-event cycle ratio is
R = b_1(x) b_1(x + e_1 + e_2) / [b_1(x + e_2) b_1(x + e_1)]. At x = (1, 1) that is
(1 + beta/2)^2 / [(1 + beta/3)(1 + 2 beta/3)]. ln R = 0.0124, 0.0803, 0.1129 and 0.1173
for beta = 1, 10, 100 and 1000, matching GARD_DESIGN §2.2. At (40, 40), ln R runs from
1.7e-5 to 1.5e-4. The pair-consistent ratio is exactly 1.

Tolerance. Each float propensity carries at most about (G + 4) unit roundoffs. So the log
ratio is off by at most about 2 (G + 4) u, about 2.3e-14 at G = 100. ``LDB_ATOL`` = 1e-12
leaves a margin above 40x, and stays far below every single-event residual on the probes.

Planted control: the single-event form must come out "refused as passive".
"""

from __future__ import annotations

from fractions import Fraction

import numpy as np

from .common import CheckResult
from .kernels import ExactLaw, ExchangeLaw, PAIR_CONSISTENT, join_affinity, propensities

LDB_ATOL = 1e-12
PROPENSITY_RTOL = 1e-13
PASSIVE = "passive"
REFUSED = "refused_as_passive"

P1_BETAS = (1, 10, 100, 1000)


def make_probe_states(rng: np.random.Generator, n_states: int = 200, n_types: int = 100) -> np.ndarray:
    """Random assembly states for the kernel identity, registered by seed.

    Masses cover the lineage range 40-80 and the small-assembly edge (1-5). The number of
    distinct types runs from one up to 60; molecules spread over them multinomially.
    """
    out = np.zeros((n_states, n_types), dtype=np.int64)
    for s in range(n_states):
        N = int(rng.integers(1, 6)) if s % 10 == 0 else int(rng.integers(40, 81))
        k = int(rng.integers(1, min(N, 60) + 1))
        types = rng.choice(n_types, size=k, replace=False)
        counts = np.ones(k, dtype=np.int64)
        if N > k:
            counts += rng.multinomial(N - k, np.full(k, 1.0 / k))
        out[s, types] = counts
    return out


def ldb_residuals_from_table(join: np.ndarray, leave_up: np.ndarray, affinity: np.ndarray) -> np.ndarray:
    """ln(a_i^+(x)) - ln(a_i^-(x + e_i)) - A_i(x) on every (state, type) pair with both rates > 0."""
    join = np.asarray(join, dtype=np.float64)
    leave_up = np.asarray(leave_up, dtype=np.float64)
    ok = (join > 0) & (leave_up > 0) & np.isfinite(affinity)
    r = np.full(join.shape, np.nan)
    r[ok] = np.log(join[ok]) - np.log(leave_up[ok]) - affinity[ok]
    return r


def kernel_table(law: ExchangeLaw, states: np.ndarray) -> dict:
    """The reference's own table: join and leave at x, leave of type i at x + e_i, and A_i(x)."""
    S, G = states.shape
    join = np.zeros((S, G))
    leave = np.zeros((S, G))
    leave_up = np.zeros((S, G))
    aff = np.zeros((S, G))
    for s in range(S):
        x = states[s]
        join[s], leave[s] = propensities(law, x)
        aff[s] = join_affinity(law, x)
        for i in range(G):
            y = x.copy()
            y[i] += 1
            leave_up[s, i] = propensities(law, y)[1][i]
    return dict(join=join, leave=leave, leave_up=leave_up, affinity=aff)


def classify(max_abs_residual: float, atol: float = LDB_ATOL) -> str:
    return PASSIVE if max_abs_residual <= atol else REFUSED


def check_local_detailed_balance(law: ExchangeLaw, states: np.ndarray, table: dict | None = None,
                                 declared_verdict: str | None = None) -> CheckResult:
    """The kernel identity on probe states. ``table`` holds the engine's propensities.

    Without a table, the reference's own propensities are used. With one, its propensities
    must also match the reference form to ``PROPENSITY_RTOL``. The verdict is "passive" only
    for a residual within ``LDB_ATOL``. A declared verdict that disagrees fails the check.
    """
    ref = kernel_table(law, states)
    t = ref if table is None else table
    detail: dict = {}
    form_ok = True
    if table is not None:
        for name in ("join", "leave", "leave_up"):
            got = np.asarray(table[name], dtype=np.float64)
            want = ref[name]
            if got.shape != want.shape:
                return CheckResult("local_detailed_balance", False, dict(error=f"{name} shape {got.shape}"))
            scale = np.maximum(np.abs(want), np.finfo(float).tiny)
            rel = float(np.max(np.abs(got - want) / scale))
            detail[f"max_rel_{name}_vs_reference"] = rel
            form_ok &= rel <= PROPENSITY_RTOL
    r = ldb_residuals_from_table(t["join"], t["leave_up"], ref["affinity"])
    max_abs = float(np.nanmax(np.abs(r)))
    verdict = classify(max_abs)
    expect_passive = law.form == PAIR_CONSISTENT
    verdict_ok = (verdict == PASSIVE) == expect_passive
    declared_ok = declared_verdict is None or (declared_verdict == PASSIVE) == (verdict == PASSIVE)
    detail.update(form=law.form, states=int(states.shape[0]), pairs=int(np.sum(np.isfinite(r))),
                  max_abs_residual=max_abs, atol=LDB_ATOL, verdict=verdict,
                  declared_verdict=declared_verdict, propensities_match_form=form_ok)
    return CheckResult("local_detailed_balance", bool(form_ok and verdict_ok and declared_ok), detail)


def square_cycle_ratio(law: ExactLaw, x: tuple[int, int]) -> Fraction:
    """Forward over reverse rate product around x -> +e1 -> +e2 -> -e1 -> -e2 (exact)."""
    a = (x[0] + 1, x[1])
    b = (x[0] + 1, x[1] + 1)
    c = (x[0], x[1] + 1)
    p = {s: law.propensities(s) for s in (x, a, b, c)}
    fwd = p[x][0][0] * p[a][0][1] * p[b][1][0] * p[c][1][1]
    rev = p[x][0][1] * p[c][0][0] * p[b][1][1] * p[a][1][0]
    return fwd / rev


def p1_expected_single_event(beta: int, x: tuple[int, int] = (1, 1)) -> Fraction:
    """Closed form of P1's single-event cycle ratio for only beta_11 = beta nonzero."""
    def b1(m):
        return 1 + Fraction(beta * m[0], m[0] + m[1])
    return (b1(x) * b1((x[0] + 1, x[1] + 1))) / (b1((x[0], x[1] + 1)) * b1((x[0] + 1, x[1])))


def check_p1_square(form: str, x: tuple[int, int] = (1, 1), betas=P1_BETAS) -> CheckResult:
    """P1 in exact arithmetic: pair-consistent ratios are 1, single-event ones match the closed form."""
    rows = []
    ok = True
    for beta in betas:
        law = ExactLaw.make([[beta, 0], [0, 0]], "1/100", "1/10000", form, rho="1/100")
        R = square_cycle_ratio(law, x)
        expect = Fraction(1) if form == PAIR_CONSISTENT else p1_expected_single_event(beta, x)
        ok &= R == expect
        rows.append(dict(beta11=beta, ln_ratio=float(np.log(float(R))), exact=str(R)))
    return CheckResult("p1_square", bool(ok), dict(form=form, state=x, rows=rows))
