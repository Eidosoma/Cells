"""Row 6. The fission partition: exact binomial and multivariate-hypergeometric pmfs.

Claim: the split of a parent P (counts P_i, mass N) into daughter 1 (d) and daughter
2 (P - d) follows the world's declared rule exactly. The sources give two:

- binomial, p = 1/2 (PNAS 2000, Fig. 1 legend; the preprint's O-02, O-03, T1-03 and
  T2-03). Each molecule goes to daughter 1 independently with probability p:
  Pr(d | P) = prod_i C(P_i, d_i) p^{d_i} (1 - p)^{P_i - d_i}.
- multivariate hypergeometric, exact size (the preprint's T2-02, floor(N/2) molecules
  into the first daughter; T1-02, exactly 40; BMC 2014, "two progenies of same size").
  Daughter 1 is a uniformly random n1-subset of the N labelled molecules:
  Pr(d | P) = prod_i C(P_i, d_i) / C(N, n1), with sum d = n1 = floor(f N).

The engine names these ``binomial`` and ``exact_fraction`` (with fraction f).

References. (1) Enumeration at small N: every labelled assignment (2^N for the binomial,
C(N, n1) subsets for the exact split) is aggregated and must reproduce the formula in exact
rationals. (2) A chi-square at N = 80 that conditions on each parent. The statistic is
S_A = sum_{i in A} d_i, with A the shortest index-ordered prefix of types holding at
least half the parent's mass. Under the binomial rule S_A ~ Bin(m_A, p); under the exact
rule S_A ~ HG(N, m_A, n1). Each split gives a randomized PIT
U = F(S - 1) + V Pr(S), with V uniform from a registered seed. U is exactly uniform
under the declared rule. The U are binned into ``BINS`` equal cells and tested at
``ALPHA``. Exact constraints are also checked: 0 <= d <= P, and sum d = n1 for the exact
rule.

Planted control: "a split at 0.55". For the binomial rule that means p = 0.55; for the
exact rule, floor(0.55 N) molecules go to daughter 1. The power against it is computed
exactly from the parents (non-central chi-square on the exact PIT cell probabilities)
before any split is read. A design below ``MIN_POWER`` fails as underpowered.
``REGISTERED_PARENT`` and ``REGISTERED_FISSIONS`` are the design registered for the
engine's fixed-parent run: 16 types of five molecules each (mass 80) and 400 splits.
"""

from __future__ import annotations

import itertools
import math
from fractions import Fraction

import numpy as np
from scipy.stats import binom, chi2, hypergeom, ncx2

from .common import ALPHA, MIN_POWER, CheckResult

BINS = 10
PLANTED_FRACTION = 0.55
PIT_SEED = 20261117
REGISTERED_PARENT = np.array([5] * 16, dtype=np.int64)
REGISTERED_FISSIONS = 400


def binomial_pmf(d, P, p=Fraction(1, 2)) -> Fraction:
    p = Fraction(p)
    out = Fraction(1)
    for di, Pi in zip(d, P):
        if not 0 <= di <= Pi:
            return Fraction(0)
        out *= math.comb(Pi, di) * p ** di * (1 - p) ** (Pi - di)
    return out


def mvhg_pmf(d, P, n1: int) -> Fraction:
    if sum(d) != n1 or any(not 0 <= di <= Pi for di, Pi in zip(d, P)):
        return Fraction(0)
    num = 1
    for di, Pi in zip(d, P):
        num *= math.comb(Pi, di)
    return Fraction(num, math.comb(sum(P), n1))


def _labelled(P) -> list[int]:
    return [i for i, c in enumerate(P) for _ in range(c)]


def enumerate_binomial(P, p=Fraction(1, 2)) -> dict:
    """Aggregate all 2^N labelled assignments, each with its exact probability."""
    p = Fraction(p)
    mol = _labelled(P)
    out: dict = {}
    for mask in range(1 << len(mol)):
        d = [0] * len(P)
        k = 0
        for b, t in enumerate(mol):
            if mask >> b & 1:
                d[t] += 1
                k += 1
        w = p ** k * (1 - p) ** (len(mol) - k)
        out[tuple(d)] = out.get(tuple(d), Fraction(0)) + w
    return out


def enumerate_mvhg(P, n1: int) -> dict:
    mol = _labelled(P)
    total = math.comb(len(mol), n1)
    out: dict = {}
    for sub in itertools.combinations(range(len(mol)), n1):
        d = [0] * len(P)
        for b in sub:
            d[mol[b]] += 1
        out[tuple(d)] = out.get(tuple(d), Fraction(0)) + Fraction(1, total)
    return out


def check_enumeration(P, rule: str, p=Fraction(1, 2), fraction=Fraction(1, 2)) -> CheckResult:
    P = [int(v) for v in P]
    N = sum(P)
    if rule == "binomial":
        enum = enumerate_binomial(P, p)
        formula = {d: binomial_pmf(d, P, p) for d in itertools.product(*[range(c + 1) for c in P])}
    else:
        n1 = math.floor(Fraction(fraction) * N)
        enum = enumerate_mvhg(P, n1)
        formula = {d: mvhg_pmf(d, P, n1) for d in itertools.product(*[range(c + 1) for c in P])
                   if sum(d) == n1}
    keys = set(enum) | {d for d, v in formula.items() if v > 0}
    bad = [d for d in keys if enum.get(d, Fraction(0)) != formula.get(d, Fraction(0))]
    total = sum(enum.values(), Fraction(0))
    return CheckResult("partition_enumeration", not bad and total == 1, dict(
        rule=rule, parent=P, mass=N, outcomes=len(keys), mismatches=len(bad), enumerated_total=str(total)))


# ------------------------------------------------------------------- chi-square

def half_mass_prefix(P: np.ndarray) -> np.ndarray:
    """Boolean mask of the shortest index-ordered prefix of types holding >= half the mass."""
    P = np.asarray(P, dtype=np.int64)
    c = np.cumsum(P)
    k = int(np.searchsorted(c, math.ceil(c[-1] / 2.0), side="left"))
    mask = np.zeros(P.size, dtype=bool)
    mask[: k + 1] = True
    return mask


def statistic_pmf(P: np.ndarray, rule: str, p: float = 0.5, fraction: float = 0.5) -> np.ndarray:
    """pmf of S_A on 0..m_A for the given rule."""
    P = np.asarray(P, dtype=np.int64)
    N = int(P.sum())
    mA = int(P[half_mass_prefix(P)].sum())
    s = np.arange(mA + 1)
    if rule == "binomial":
        return binom.pmf(s, mA, p)
    n1 = int(math.floor(fraction * N))
    return hypergeom.pmf(s, N, mA, n1)


def pit_cell_probabilities(pmf0: np.ndarray, pmf1: np.ndarray, bins: int = BINS) -> tuple[np.ndarray, float]:
    """Exact probability of each PIT cell under pmf1 when the PIT uses pmf0.

    Mass that pmf1 puts where pmf0 is zero cannot be transformed. It is returned
    separately as the probability of an outcome impossible under the declared rule.
    """
    F0 = np.concatenate([[0.0], np.cumsum(pmf0)])
    edges = np.linspace(0.0, 1.0, bins + 1)
    cells = np.zeros(bins)
    impossible = 0.0
    for s in range(max(pmf0.size, pmf1.size)):
        w1 = pmf1[s] if s < pmf1.size else 0.0
        w0 = pmf0[s] if s < pmf0.size else 0.0
        if w1 == 0.0:
            continue
        if w0 == 0.0:
            impossible += w1
            continue
        lo = F0[s]
        hi = lo + w0
        if hi <= lo:  # a cell narrower than float resolution at lo: all of it in lo's bin
            cells[min(int(np.searchsorted(edges, lo, side="right")) - 1, bins - 1)] += w1
            continue
        overlap = np.clip(np.minimum(hi, edges[1:]) - np.maximum(lo, edges[:-1]), 0.0, None)
        cells += w1 * overlap / (hi - lo)
    return cells, impossible


def planted_power(parents: np.ndarray, rule: str, p: float = 0.5, fraction: float = 0.5,
                  alpha: float = ALPHA, bins: int = BINS) -> dict:
    """Power of the PIT chi-square (and the exact checks) against a split at 0.55."""
    parents = np.atleast_2d(np.asarray(parents, dtype=np.int64))
    F = parents.shape[0]
    mean_cells = np.zeros(bins)
    p_possible = 1.0
    for P in parents:
        pmf0 = statistic_pmf(P, rule, p, fraction)
        pmf1 = statistic_pmf(P, rule, PLANTED_FRACTION, PLANTED_FRACTION) if rule == "binomial" else \
            statistic_pmf(P, rule, fraction=PLANTED_FRACTION)
        cells, impossible = pit_cell_probabilities(pmf0, pmf1, bins)
        mean_cells += cells / max(1.0 - impossible, 1e-300) / F
        p_possible *= 1.0 - impossible
    crit = chi2.isf(alpha, bins - 1)
    nc = F * bins * float(np.sum((mean_cells - 1.0 / bins) ** 2))
    chi_power = float(ncx2.sf(crit, bins - 1, nc))
    exact_power = 1.0 - p_possible
    if rule == "exact_fraction":
        masses = parents.sum(axis=1)
        if np.any(np.floor(PLANTED_FRACTION * masses) != np.floor(fraction * masses)):
            exact_power = 1.0  # the daughter's size alone refutes the planted split
    return dict(chi_square=chi_power, exact_constraints=float(exact_power),
                combined=float(1.0 - (1.0 - chi_power) * (1.0 - exact_power)))


def check_partition_records(parents: np.ndarray, splits: np.ndarray, rule: str, p: float = 0.5,
                            fraction: float = 0.5, alpha: float = ALPHA, min_power: float = MIN_POWER,
                            bins: int = BINS, pit_seed: int = PIT_SEED) -> CheckResult:
    """Exact constraints and the conditional PIT chi-square over recorded splits."""
    parents = np.atleast_2d(np.asarray(parents, dtype=np.int64))
    splits = np.atleast_2d(np.asarray(splits, dtype=np.int64))
    if parents.shape != splits.shape:
        return CheckResult("fission_partition", False, dict(error=f"shapes {parents.shape} vs {splits.shape}"))
    F = parents.shape[0]
    bounds_ok = bool(np.all(splits >= 0) and np.all(splits <= parents))
    size_ok = True
    if rule == "exact_fraction":
        n1 = np.floor(fraction * parents.sum(axis=1)).astype(np.int64)
        size_ok = bool(np.all(splits.sum(axis=1) == n1))
    power = planted_power(parents, rule, p, fraction, alpha, bins)
    rng = np.random.default_rng(pit_seed)
    V = rng.random(F)
    U = np.empty(F)
    impossible = 0
    for f in range(F):
        P = parents[f]
        pmf = statistic_pmf(P, rule, p, fraction)
        s = int(splits[f][half_mass_prefix(P)].sum())
        if s >= pmf.size or pmf[s] == 0.0:
            impossible += 1
            U[f] = np.nan
            continue
        U[f] = (pmf[:s].sum() if s > 0 else 0.0) + V[f] * pmf[s]
    ok_U = U[np.isfinite(U)]
    obs = np.histogram(ok_U, bins=np.linspace(0.0, 1.0, bins + 1))[0]
    exp = ok_U.size / bins
    stat = float(np.sum((obs - exp) ** 2 / exp)) if ok_U.size else float("inf")
    crit = chi2.isf(alpha, bins - 1)
    enough = power["combined"] >= min_power
    passed = bool(bounds_ok and size_ok and impossible == 0 and stat <= crit and enough)
    return CheckResult("fission_partition", passed, dict(
        rule=rule, fissions=F, bounds_ok=bounds_ok, exact_size_ok=size_ok, impossible_outcomes=impossible,
        chi_square=stat, chi_square_crit=crit, bins=bins, alpha=alpha, planted_power=power,
        min_power=min_power, underpowered=not enough))


def check_partition_exact(parents: np.ndarray, splits: np.ndarray, rule: str, fraction: float | None = None,
                          name: str = "fission_partition_exact") -> CheckResult:
    """The exact constraints on recorded splits: 0 <= d <= P, and sum d = floor(f N) for the exact rule."""
    if rule not in ("binomial", "exact_fraction"):
        return CheckResult(name, False, dict(error=f"unknown partition rule {rule!r}"))
    parents = np.atleast_2d(np.asarray(parents, dtype=np.int64))
    splits = np.atleast_2d(np.asarray(splits, dtype=np.int64))
    if parents.shape != splits.shape:
        return CheckResult(name, False, dict(error=f"shapes {parents.shape} vs {splits.shape}"))
    bounds = np.all((splits >= 0) & (splits <= parents), axis=1)
    sizes = np.ones(parents.shape[0], dtype=bool)
    if rule == "exact_fraction":
        sizes = splits.sum(axis=1) == np.floor(float(fraction) * parents.sum(axis=1)).astype(np.int64)
    bad = np.flatnonzero(~(bounds & sizes))
    return CheckResult(name, bool(bad.size == 0), dict(rule=rule, fissions=int(parents.shape[0]),
                                                      failing_fissions=bad[:10].tolist()))
