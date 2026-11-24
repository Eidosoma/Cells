"""The rule at zero uncertainty, one function for FR-47's qualification and Protocol D's
re-registration (D323): each (observable, time) pair is classified from the model before the run.

- **constant:** the reference, or the model's structure, predicts that every exact replica holds
  one value. Every replica must equal it exactly, and one wrong replica fails. No sample statistic
  is formed, so no rounding of a sum can pass or fail it (Protocol D's D6 artifact).
- **derived:** two routes to one constant by different arithmetic, the only place a tolerance
  enters. |y − y_ref| must be at most a bound derived from the arithmetic, never declared, as
  release_check's bounds are (validation/gene_regulation/release_check.py).
- **spread:** the reference predicts spread. Identical replicas still face the spread test.
  - With the reference's own mean, variance σ² and fourth central moment μ₄ (FR-47), the mean's
    z = (ȳ − m)/√(σ²/M), and the spread's z = (s² − σ²)/√Var(s²), with
    Var(s²) = (μ₄ − σ⁴(M − 3)/(M − 1))/M for M independent replicas.
  - A protocol without a reference variance (Protocol D) judges its spread pairs by its own
    registered criterion. This module supplies the classification and the constant and derived
    rules it shares.

The bands are the protocols' own: pass at |z| ≤ z_pass, fail beyond z_fail, inconclusive between.
`python -m validation.assembly_lineages_v2.agreement check` runs the synthetic checks, on made-up
values only.
"""

import json
import math
import sys

import numpy as np

CONSTANT, DERIVED, SPREAD = "constant", "derived", "spread"
CLASSES = (CONSTANT, DERIVED, SPREAD)


def _bits(values):
    return np.asarray(values, dtype=np.float64).view(np.uint64)


def judge_constant(values, expected):
    """Every replica equals the predicted constant, bit for bit; one wrong replica fails."""
    values = np.asarray(values, dtype=np.float64)
    off = int(np.sum(_bits(values) != _bits(np.float64(expected))))
    return {"class": CONSTANT, "replicas": int(values.size), "replicas_off": off,
            "passes": off == 0, "fails": off > 0}  # fmt: skip


def judge_derived(values, expected, tolerance):
    """Two routes to one constant by different arithmetic: every |y − y_ref| is within the bound
    derived from that arithmetic (`tolerance`, a number the protocol derives, never fits)."""
    if not (isinstance(tolerance, float) and math.isfinite(tolerance) and tolerance >= 0.0):
        raise ValueError("a derived tolerance is a finite non-negative float")
    gap = float(np.max(np.abs(np.asarray(values, dtype=np.float64) - float(expected))))
    return {"class": DERIVED, "largest_gap": gap, "tolerance": tolerance,
            "passes": gap <= tolerance, "fails": gap > tolerance}  # fmt: skip


def spread_variance(var, mu4, m):
    """Var(s²) of the unbiased sample variance of m independent replicas, from the population's
    variance and fourth central moment: (μ₄ − σ⁴(m − 3)/(m − 1))/m."""
    return (mu4 - var * var * (m - 3) / (m - 1)) / m


def judge_spread(values, mean, var, mu4, *, z_pass=4.5, z_fail=6.0):
    """The reference's mean, variance and fourth central moment against the replicas: the mean's z
    with the reference's own SD, and the spread's z from the reference's fourth moment. Identical
    replicas (s² = 0) face the spread test like any other."""
    values = np.asarray(values, dtype=np.float64)
    m = int(values.size)
    if not (var > 0.0 and m >= 2):
        raise ValueError("a spread pair has a positive reference variance and two replicas or more")
    z_mean = (float(np.mean(values)) - mean) / math.sqrt(var / m)
    v_s2 = spread_variance(var, mu4, m)
    if not v_s2 > 0.0:
        raise ValueError("Var(s²) from the reference is not positive")
    z_spread = (float(np.var(values, ddof=1)) - var) / math.sqrt(v_s2)
    worst = max(abs(z_mean), abs(z_spread))
    return {"class": SPREAD, "z_mean": z_mean, "z_spread": z_spread,
            "passes": worst <= z_pass, "fails": worst > z_fail}  # fmt: skip


def judge(values, reference, *, z_pass=4.5, z_fail=6.0):
    """One pair under its class, fixed before the run. `reference` holds `class` and, by class,
    `value` (constant), `value` and `tolerance` (derived), or `mean`, `var` and `mu4` (spread)."""
    kind = reference["class"]
    if kind == CONSTANT:
        return judge_constant(values, reference["value"])
    if kind == DERIVED:
        return judge_derived(values, reference["value"], reference["tolerance"])
    if kind == SPREAD:
        return judge_spread(values, reference["mean"], reference["var"], reference["mu4"],
                            z_pass=z_pass, z_fail=z_fail)  # fmt: skip
    raise ValueError(f"a pair's class is one of {CLASSES}, fixed before the run, not {kind!r}")


# ------------------------------------------------------------------ the synthetic checks


def _bernoulli_sum_moments(p):
    """Mean, variance and fourth central moment of a sum of independent Bernoulli(p_i): cumulants of
    independent terms add, κ₂ = Σ p(1 − p), κ₄ = Σ p(1 − p)(1 − 6p(1 − p)), μ₄ = κ₄ + 3κ₂²."""
    p = np.asarray(p, dtype=np.float64)
    k2 = float(np.sum(p * (1 - p)))
    k4 = float(np.sum(p * (1 - p) * (1 - 6 * p * (1 - p))))
    return float(np.sum(p)), k2, k4 + 3 * k2 * k2


def check():
    rng = np.random.default_rng(20261123)
    out = {}
    ok = judge_constant(np.full(128, 100.0), 100.0)
    one_off = judge_constant(np.r_[np.full(127, 100.0), 101.0], 100.0)
    signed = judge_constant(np.zeros(4), -0.0)
    out["constant: every replica equal passes; one wrong replica fails; bits decide"] = {
        "ok": ok["passes"] and one_off["fails"] and one_off["replicas_off"] == 1
        and signed["fails"]}  # fmt: skip
    within = judge_derived([1.0 + 1e-15, 1.0 - 1e-15], 1.0, 4e-15)
    beyond = judge_derived([1.0 + 1e-13], 1.0, 4e-15)
    out["derived: within the derived bound passes, beyond fails"] = {
        "ok": within["passes"] and beyond["fails"]}
    # spread: a sum of independent molecules, its moments from cumulants, against draws of it
    p = rng.uniform(0.05, 0.6, size=400)
    mean, var, mu4 = _bernoulli_sum_moments(p)
    draws = (rng.uniform(size=(128, p.size)) < p).sum(axis=1).astype(np.float64)
    honest = judge_spread(draws, mean, var, mu4)
    identical = judge_spread(np.full(128, round(mean)), mean, var, mu4)
    shifted = judge_spread(draws + 0.1 * math.sqrt(var) * 6, mean, var, mu4)
    out["spread: honest draws pass; identical replicas fail the spread test; a shift fails"] = {
        "z_honest": [honest["z_mean"], honest["z_spread"]],
        "z_identical_spread": identical["z_spread"], "z_shifted_mean": shifted["z_mean"],
        "ok": honest["passes"] and identical["fails"] and shifted["fails"]}  # fmt: skip
    # Var(s²) = (μ₄ − σ⁴(m − 3)/(m − 1))/m, against Monte Carlo at m = 128 (R samples of s²)
    m, R = 128, 20000
    s2 = np.empty(R)
    for i in range(R):
        s2[i] = np.var((rng.uniform(size=(m, p.size)) < p).sum(axis=1), ddof=1)
    predicted = spread_variance(var, mu4, m)
    empirical = float(np.var(s2, ddof=1))
    rel_se = math.sqrt(2.0 / (R - 1)) * 1.2  # Var's own relative SE, with a kurtosis allowance
    out["Var(s²) from the fourth moment, against 20,000 samples of s² at m = 128"] = {
        "predicted": predicted, "empirical": empirical, "ratio": empirical / predicted,
        "ok": abs(empirical / predicted - 1.0) <= 4.5 * rel_se}  # fmt: skip
    try:
        judge(np.ones(3), {"class": "exact"})
        refused = False
    except ValueError:
        refused = True
    out["an undeclared class is refused"] = {"ok": refused}
    return out


if __name__ == "__main__":
    if sys.argv[1:] != ["check"]:
        raise SystemExit("usage: python -m validation.assembly_lineages_v2.agreement check")
    results = check()
    print(json.dumps(results, indent=1))
    raise SystemExit(0 if all(r["ok"] for r in results.values()) else 1)
