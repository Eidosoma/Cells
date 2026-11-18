"""OL3 (registered ahead of its engine; the equal-area case needs no ruling): the partition of a
dividing vesicle's contents, exactly, with a registered chi-square design (design §4.3-4.4,
§7.1 "Division admissibility and the partition").

**The membrane** (§4.4). At given daughter areas with equal areas per molecule, the daughters'
membrane counts N_1..N_k are fixed (they sum to the parent's N). Which molecules go where is a
uniformly random assignment, so the composition is multivariate hypergeometric:

    P(d) = prod_i [P_i! / prod_j d_ij!] / [N! / prod_j N_j!],

over integer matrices d with row sums P_i (the parent's count of species i) and column sums N_j.
(Unequal areas per molecule do not fix the counts; their rule waits for the lead's ruling.)

**The lumen** (§4.4). Each lumen molecule goes to daughter j independently with probability
V_j / V, so the contents are multinomial: P(l) = prod_s [L_s! / prod_j l_sj!] prod_j (V_j/V)^l_sj.

**Exact references.** ``hypergeometric_pmf`` and ``multinomial_pmf`` are exact (Fractions);
``enumerate_splits`` lists every admissible matrix, so the tests hold each pmf summing to one and
equal to a direct count of labelled assignments at small N.

**The registered chi-square design** (two daughters of equal area). The statistic is daughter
1's count of the first species, whose law is the hypergeometric marginal
C(P_0, x) C(N - P_0, N_1 - x)/C(N, N_1). Cells with expected count below five are pooled from the
tails; the test is Pearson's chi-square at alpha = 1e-3. Its power against each planted split is
computed before any record is read, from the planted law's own marginal (noncentral chi-square):
- ``split_055``: daughter sizes 0.55 N and 0.45 N where equal sizes are declared;
- ``binomial``: each membrane molecule placed independently with probability 1/2 (daughter sizes
  then vary);
The registered parent and number of splits must reach power 0.99 against both.
"""

from __future__ import annotations

import itertools
import math
from fractions import Fraction

import numpy as np
from scipy.stats import chi2, ncx2

from .common import ALPHA, MIN_POWER, CheckResult

REGISTERED_PARENT = (40, 30, 10)      # three amphiphile species, N = 80
REGISTERED_SPLITS = 400
PLANTED_SPLITS = ("split_055", "binomial")


def multinomial_coefficient(n: int, parts) -> int:
    out = math.factorial(n)
    for p in parts:
        out //= math.factorial(p)
    return out


def hypergeometric_pmf(parent, sizes, d) -> Fraction:
    """P(d) for a k-daughter membrane split with fixed daughter counts ``sizes``."""
    if any(sum(row) != P for row, P in zip(d, parent, strict=True)):
        return Fraction(0)
    if any(sum(d[i][j] for i in range(len(parent))) != sizes[j] for j in range(len(sizes))):
        return Fraction(0)
    num = 1
    for row, P in zip(d, parent, strict=True):
        num *= multinomial_coefficient(P, row)
    return Fraction(num, multinomial_coefficient(sum(parent), sizes))


def multinomial_pmf(counts, fractions, l) -> Fraction:
    """P(l) for a lumen split: species s's L_s molecules over daughters with probabilities f_j."""
    out = Fraction(1)
    for L, row in zip(counts, l, strict=True):
        if sum(row) != L:
            return Fraction(0)
        out *= multinomial_coefficient(L, row)
        for f, x in zip(fractions, row, strict=True):
            out *= Fraction(f) ** x
    return out


def compositions(total: int, parts: int):
    """Every tuple of ``parts`` non-negative integers summing to ``total``."""
    if parts == 1:
        yield (total,)
        return
    for first in range(total + 1):
        for rest in compositions(total - first, parts - 1):
            yield (first,) + rest


def enumerate_splits(parent, sizes):
    """Every split matrix with row sums ``parent`` and column sums ``sizes``."""
    rows = [list(compositions(P, len(sizes))) for P in parent]
    for d in itertools.product(*rows):
        if all(sum(r[j] for r in d) == sizes[j] for j in range(len(sizes))):
            yield d


def labelled_count_pmf(parent, sizes) -> dict:
    """The split law by brute force over labelled molecules (small N only): every assignment of
    N labelled molecules to daughters with the given sizes is equally likely."""
    species = [i for i, P in enumerate(parent) for _ in range(P)]
    N = len(species)
    counts: dict = {}
    total = 0
    for assign in itertools.product(range(len(sizes)), repeat=N):
        if [assign.count(j) for j in range(len(sizes))] != list(sizes):
            continue
        total += 1
        d = tuple(tuple(sum(1 for m, s in enumerate(species) if s == i and assign[m] == j)
                        for j in range(len(sizes))) for i in range(len(parent)))
        counts[d] = counts.get(d, 0) + 1
    return {d: Fraction(c, total) for d, c in counts.items()}


# ---------------------------------------------------------------- the chi-square design

def marginal_first_species(parent, N1: int) -> np.ndarray:
    """P(x) for daughter 1's count of species 0 (hypergeometric), x = 0..P_0."""
    P0, N = parent[0], sum(parent)
    den = math.comb(N, N1)
    return np.array([math.comb(P0, x) * math.comb(N - P0, N1 - x) / den for x in range(P0 + 1)])


def planted_marginal(parent, form: str) -> np.ndarray:
    P0, N = parent[0], sum(parent)
    if form == "split_055":
        return marginal_first_species(parent, int(round(0.55 * N)))
    if form == "binomial":
        return np.array([math.comb(P0, x) * 0.5 ** P0 for x in range(P0 + 1)])
    raise ValueError(form)


def pooled_cells(p: np.ndarray, n: int, min_expected: float = 5.0) -> list[list[int]]:
    """Contiguous cells, pooled from each tail until every expected count is at least five."""
    idx = list(range(len(p)))
    cells: list[list[int]] = []
    cur: list[int] = []
    for i in idx:
        cur.append(i)
        if p[cur].sum() * n >= min_expected:
            cells.append(cur)
            cur = []
    if cur:
        cells[-1].extend(cur)
    # pool the low tail into its neighbour as well, so each cell meets the minimum
    while len(cells) > 1 and p[cells[0]].sum() * n < min_expected:
        cells[1] = cells[0] + cells[1]
        cells.pop(0)
    return cells


def chi_square_design(parent=REGISTERED_PARENT, splits: int = REGISTERED_SPLITS, alpha: float = ALPHA) -> dict:
    N = sum(parent)
    p0 = marginal_first_species(parent, N // 2)
    cells = pooled_cells(p0, splits)
    e0 = np.array([p0[c].sum() for c in cells])
    dof = len(cells) - 1
    crit = float(chi2.isf(alpha, dof))
    power = {}
    for form in PLANTED_SPLITS:
        p1 = planted_marginal(parent, form)
        e1 = np.array([p1[c].sum() for c in cells])
        lam = splits * float(np.sum((e1 - e0) ** 2 / e0))
        power[form] = float(ncx2.sf(crit, dof, lam))
    return dict(parent=list(parent), splits=splits, cells=cells, expected=e0.tolist(), dof=dof, critical=crit,
                power=power, underpowered=[f for f, v in power.items() if v < MIN_POWER])


def chi_square_test(x1: np.ndarray, design: dict) -> CheckResult:
    """Daughter 1's count of species 0 in each recorded split, against the registered law."""
    if design["underpowered"]:
        return CheckResult("partition_chi_square", False, dict(problem="underpowered", design=design["power"]))
    x1 = np.asarray(x1, dtype=np.int64)
    n = x1.size
    if n != design["splits"]:
        return CheckResult("partition_chi_square", False, dict(problem=f"{n} splits; {design['splits']} registered"))
    obs = np.array([np.isin(x1, c).sum() for c in design["cells"]], dtype=float)
    exp = n * np.asarray(design["expected"])
    stat = float(np.sum((obs - exp) ** 2 / exp))
    return CheckResult("partition_chi_square", stat <= design["critical"],
                       dict(statistic=stat, critical=design["critical"], dof=design["dof"], splits=n))


def check_conservation(parent, daughters) -> CheckResult:
    """Every species' daughter counts sum exactly to the parent's (and none is negative)."""
    d = np.asarray(daughters, dtype=np.int64)
    ok = bool(np.all(d >= 0) and np.array_equal(d.sum(axis=-1), np.asarray(parent)))
    return CheckResult("partition_conserves_counts", ok, dict(parent=list(parent), sums=d.sum(axis=-1).tolist()))
