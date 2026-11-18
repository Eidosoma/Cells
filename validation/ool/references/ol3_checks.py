"""Row OL3-1: the partition probe. C3x and the lumen split at registered parents, replayed from
each attempt's own uniforms and tested against their exact laws (§0.2c rules 9 and 10).

A partition probe gives, for each registered parent (``designs/ol3_parents.json``), M attempts,
each with its block of uniforms (N + k + N_L, in rules 9-10's order) and the daughters' membrane
and lumen counts.

- ``replay``: every attempt's daughters equal ``partition.split_from_uniforms`` on its uniforms
  (the membrane exactly; the lumen exactly but where a lumen uniform lies within 1e-12 of a
  cumulative weight, a near-tie the summation order may flip).
- ``membrane_law``: Pearson's chi-square of the daughters' count matrices against the exact law
  (``partition.exact_law``; at equal areas it is the balanced hypergeometric with a random order),
  cells with expected count below 5 pooled, and any outcome outside the law's support failing at
  once. Family-wise alpha 1e-3 over the parents (Bonferroni).
- ``lumen_weights``: given each attempt's membrane, its lumen is multinomial with
  p_j = V_sph(A_j)/Sum V_sph(A_l). The statistic Z = Sum c_j (l_j - L p_j) / sd, with
  c_j = W_j - mean W, is N(0, 1) under the rule and moves against weights by area (p_j ~ W_j) or
  by equal shares (p_j = 1/k). Two-sided, at the same family-wise alpha.

Powers (registered): the chi-square's noncentrality M Sum (p1 - p0)^2/p0 (with mass outside the
support detected at once); the lumen test's mean shift over its standard deviation, from the
reference's own split law at the registered parents.
"""

from __future__ import annotations

import math
from fractions import Fraction

import numpy as np
from scipy.stats import chi2, ncx2, norm

from . import partition as PT
from .common import ALPHA, MIN_POWER
from .population import TIE_RTOL, HostStreams

PLANTED_LUMEN = ("lumen_by_area", "lumen_equal")


def weights(daughters_membrane, areas_k, planted=None) -> list:
    W = [sum(int(n) * int(a) for n, a in zip(row, areas_k)) for row in daughters_membrane]
    if planted == "lumen_by_area":
        return [w / sum(W) for w in W]
    if planted == "lumen_equal":
        return [1.0 / len(W)] * len(W)
    return PT.lumen_weights(daughters_membrane, areas_k)


def split(parent: dict, u: list, planted=None) -> dict:
    counts, areas, lumen, k = parent["counts"], parent["k_area"], parent["lumen"], parent["k"]
    N = sum(counts)
    mem_planted = planted if planted in PT.PLANTED_SPLITS else None
    mem, pi = PT.c3x(list(counts), list(areas), k, u[: N + k], mem_planted)
    p = weights(mem, areas, planted if planted in PLANTED_LUMEN else None)
    lum = PT.lumen_split(list(lumen), p, pi, u[N + k:])
    return dict(membrane=mem, lumen=lum, pi=pi, weights=p)


def standin_attempts(parent: dict, M: int, seed: int, key: int, planted=None) -> list:
    src = HostStreams(seed)
    n = sum(parent["counts"]) + parent["k"] + sum(parent["lumen"])
    out = []
    for c in range(M):
        u = src.get(2, key, c, n)
        s = split(parent, u, planted)
        out.append(dict(counter=c, u=u, membrane=s["membrane"], lumen=s["lumen"]))
    return out


def replay(parent: dict, attempts: list) -> dict:
    N, k = sum(parent["counts"]), parent["k"]
    need = N + k + sum(parent["lumen"])
    bad, ties = [], 0
    for a in attempts:
        u = list(a["u"])
        if len(u) != need:
            bad.append(dict(counter=a.get("counter"), problem=f"{len(u)} uniforms, {need} needed"))
            continue
        s = split(parent, u)
        if s["membrane"] != [list(r) for r in a["membrane"]]:
            bad.append(dict(counter=a.get("counter"), where="membrane", reference=s["membrane"], recorded=a["membrane"]))
            continue
        if s["lumen"] != [list(r) for r in a["lumen"]]:
            cum = np.cumsum([s["weights"][s["pi"][b]] for b in range(k)])[:-1]
            lu = np.asarray(u[N + k:])
            if lu.size and np.min(np.abs(lu[:, None] - cum[None, :])) <= TIE_RTOL:
                ties += 1
                continue
            bad.append(dict(counter=a.get("counter"), where="lumen", reference=s["lumen"], recorded=a["lumen"]))
    return dict(passed=not bad and len(attempts) > 0, attempts=len(attempts), near_ties=ties, mismatches=bad[:5])


def _law(parent: dict, planted=None) -> dict:
    mem_planted = planted if planted in PT.PLANTED_SPLITS else None
    return PT.exact_law(list(parent["counts"]), list(parent["k_area"]), parent["k"], mem_planted)


def _bins(p0: dict, M: int) -> list:
    """Cells of the honest law with expected count >= 5, the rest pooled into one cell."""
    keys = sorted(p0, key=lambda x: (-float(p0[x]), x))
    big = [[x] for x in keys if float(p0[x]) * M >= 5]
    small = [x for x in keys if float(p0[x]) * M < 5]
    if small:
        big.append(small)
    if len(big) > 1 and sum(float(p0[x]) for x in big[-1]) * M < 5:
        tail = big.pop()
        big[-1] = big[-1] + tail
    return big


def membrane_design(parent: dict, M: int, alpha: float) -> dict:
    p0 = _law(parent)
    bins = _bins(p0, M)
    dof = max(len(bins) - 1, 1)
    crit = float(chi2.isf(alpha, dof))
    power = {}
    for form in ("g1_sizes", "no_pi", "largest_c", "ties_last"):
        p1 = _law(parent, form)
        outside = float(sum(v for x, v in p1.items() if x not in p0))
        lam = M * sum((float(sum(p1.get(x, Fraction(0)) for x in b)) - float(sum(p0[x] for x in b))) ** 2
                      / float(sum(p0[x] for x in b)) for b in bins)
        pw = float(ncx2.sf(crit, dof, lam)) if lam > 0 else alpha
        power[form] = 1.0 - (1.0 - outside) ** M * (1.0 - pw) if outside > 0 else pw
        power[form + "_tv"] = float(PT.total_variation(p0, p1))
    return dict(outcomes=len(p0), cells=len(bins), dof=dof, critical=crit, power=power)


def membrane_law(parent: dict, attempts: list, alpha: float) -> dict:
    p0 = _law(parent)
    M = len(attempts)
    obs = {}
    for a in attempts:
        key = tuple(tuple(int(x) for x in r) for r in a["membrane"])
        obs[key] = obs.get(key, 0) + 1
    outside = {str(x): c for x, c in obs.items() if x not in p0}
    bins = _bins(p0, M)
    stat = 0.0
    for b in bins:
        e = M * float(sum(p0[x] for x in b))
        o = sum(obs.get(x, 0) for x in b)
        stat += (o - e) ** 2 / e
    dof = max(len(bins) - 1, 1)
    pval = float(chi2.sf(stat, dof))
    return dict(passed=not outside and pval > alpha, chi_square=stat, dof=dof, p_value=pval, alpha=alpha,
                outside_support=outside)


def _lumen_terms(parent: dict, membrane, lumen) -> tuple:
    W = [sum(int(n) * int(a) for n, a in zip(row, parent["k_area"])) for row in membrane]
    c = np.asarray(W, float) - np.mean(W)
    p = np.asarray(PT.lumen_weights(membrane, parent["k_area"]))
    num, var = 0.0, 0.0
    for s, L in enumerate(parent["lumen"]):
        l = np.asarray([row[s] for row in lumen], float)
        num += float(np.sum(c * (l - L * p)))
        var += L * float(np.sum(c * c * p) - np.sum(c * p) ** 2)
    return num, var


def lumen_weights_test(parent: dict, attempts: list, alpha: float) -> dict:
    num = var = 0.0
    for a in attempts:
        x, v = _lumen_terms(parent, a["membrane"], a["lumen"])
        num += x
        var += v
    if var <= 0:
        return dict(passed=True, z=0.0, note="no area contrast: the test has no power here (zero-power entry)")
    z = num / math.sqrt(var)
    crit = float(norm.isf(alpha / 2))
    return dict(passed=abs(z) <= crit, z=z, critical=crit, alpha=alpha)


def lumen_design(parent: dict, M: int, alpha: float, samples: int = 400, seed: int = 2026111803) -> dict:
    """Mean shift of the lumen statistic per attempt under each planted weighting, from the
    reference's own membrane law (sampled) and the exact multinomial means."""
    src = HostStreams(seed)
    N, k = sum(parent["counts"]), parent["k"]
    shift = {f: 0.0 for f in PLANTED_LUMEN}
    var = 0.0
    for c in range(samples):
        u = src.get(2, 0, c, N + k)
        mem, _ = PT.c3x(list(parent["counts"]), list(parent["k_area"]), k, u)
        W = [sum(int(n) * int(a) for n, a in zip(row, parent["k_area"])) for row in mem]
        cc = np.asarray(W, float) - np.mean(W)
        p = np.asarray(PT.lumen_weights(mem, parent["k_area"]))
        for L in parent["lumen"]:
            var += L * float(np.sum(cc * cc * p) - np.sum(cc * p) ** 2)
            for f in PLANTED_LUMEN:
                q = np.asarray(weights(mem, parent["k_area"], f))
                shift[f] += L * float(np.sum(cc * (q - p)))
    crit = float(norm.isf(alpha / 2))
    power = {}
    for f in PLANTED_LUMEN:
        if var <= 0:
            power[f] = 0.0
            continue
        mu = shift[f] / samples * M / math.sqrt(var / samples * M)
        power[f] = float(norm.sf(crit - mu) + norm.cdf(-crit - mu))
    return dict(power=power, per_attempt_sd=math.sqrt(var / samples) if var > 0 else 0.0)


def design(parents: list, M: int) -> dict:
    alpha = ALPHA / (2 * len(parents))
    out = {}
    for par in parents:
        out[par["id"]] = dict(membrane=membrane_design(par, M, alpha), lumen=lumen_design(par, M, alpha))
    planted = {}
    for f in ("g1_sizes", "no_pi") + PLANTED_LUMEN:
        miss = 1.0
        for par in parents:
            pw = out[par["id"]]["membrane"]["power"].get(f, out[par["id"]]["lumen"]["power"].get(f, 0.0))
            miss *= 1.0 - pw
        planted[f] = 1.0 - miss
    return dict(alpha_per_test=alpha, parents=out, family_power=planted,
                underpowered=[f for f, v in planted.items() if v < MIN_POWER])


def check(parents: list, attempts_by_parent: dict, M: int) -> dict:
    alpha = ALPHA / (2 * len(parents))
    res = {}
    ok = True
    for par in parents:
        att = attempts_by_parent.get(par["id"])
        if att is None or len(att) < M:
            res[par["id"]] = dict(passed=False, problem=f"{0 if att is None else len(att)} attempts, {M} registered")
            ok = False
            continue
        r = dict(replay=replay(par, att), membrane=membrane_law(par, att, alpha), lumen=lumen_weights_test(par, att, alpha))
        r["passed"] = all(x["passed"] for x in r.values())
        ok = ok and r["passed"]
        res[par["id"]] = r
    return dict(passed=ok, parents=res)
