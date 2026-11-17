"""Row 1. The exchange law (mean field): its closed form at beta = 0.

Claim: the engine's exchange law is the GARD rate law. At beta = 0 its mean field
has a closed form, and a wrong k_b must be caught.

Derivation. The rate law (PNAS 2000 Eq. 4; BMC 2014 Eq. 2, buffered rho; preprint
p. 10) is dn_i/dt = b_i(n) (k_f,i rho_i N - k_b,i n_i). At beta = 0, b_i = 1. With
uniform k_f and k_b, summing over i gives dN/dt = (k_f Sum(rho) - k_b) N, so

    N(t) = N_0 e^{r t},   r = k_f Sum(rho) - k_b.

Variation of constants on dn_i/dt + k_b n_i = k_f rho_i N_0 e^{r t}, with
r + k_b = k_f Sum(rho) = lambda, gives

    n_i(t) = n_i(0) e^{-k_b t} + (rho_i / Sum(rho)) N_0 (e^{r t} - e^{-k_b t}).

The composition x_i = n_i/N relaxes to rho_i/Sum(rho) at rate lambda. That rate has
no k_b in it, so only N(t) and n_i(t) carry k_b. With per-type constants the system is
linear, dn/dt = (u 1^T - diag(k_b)) n with u_i = k_f,i rho_i, and n(t) = expm(A t) n_0.

Why the stochastic engine can be held to it. At beta = 0 every propensity is linear in
the state: a_i^+ = k_f rho_i N and a_i^- = k_b n_i. The master equation's first moments
therefore close exactly. The ensemble mean of n_i(t) obeys the same linear ODE, with no
moment-closure error. Without fission, and without hitting N = 1, the engine's ensemble
mean must match the closed form within its sampling error. The boundary rule never
acts in the registered design: from N_0 = 20 with mu/lambda = 1/2, reaching N = 1 by
t = 2 has probability below 1e-5.

Planted control: k_b 10 % too large (``PLANTED_KB_FACTOR``). The power to catch it is
computed from the design before any data are read. If it falls below ``MIN_POWER`` the
check fails as underpowered rather than passing vacuously.
"""

from __future__ import annotations

import numpy as np
from scipy.linalg import expm
from scipy.stats import norm

from .common import ALPHA, MIN_POWER, CheckResult

PLANTED_KB_FACTOR = 1.1

# Registered design for the ensemble check (rows 1 and 5 share it).
REGISTERED_DESIGN = dict(
    k_join=1.0,
    k_leave=0.5,
    rho=(0.1, 0.2, 0.3, 0.4),
    founder=(5, 5, 5, 5),
    times=(0.5, 1.0, 1.5, 2.0),
    runs=500,
)


def rate_law_flux(beta: np.ndarray, k_join, k_leave, rho, n: np.ndarray) -> np.ndarray:
    """The GARD rate law J_i(n) = b_i(n) (k_f,i rho_i N - k_b,i n_i), any beta."""
    n = np.asarray(n, dtype=np.float64)
    N = n.sum()
    b = 1.0 + (np.asarray(beta, dtype=np.float64) @ n) / N
    return b * (np.asarray(k_join) * np.asarray(rho) * N - np.asarray(k_leave) * n)


def closed_form_beta0(t, n0, k_join, k_leave, rho) -> tuple[np.ndarray, np.ndarray]:
    """Mean-field n_i(t) and N(t) at beta = 0; returns arrays [T, G] and [T].

    Uniform scalar k_join and k_leave use the scalar closed form above. Per-type
    constants use the exact linear solution n(t) = expm(A t) n_0.
    """
    t = np.atleast_1d(np.asarray(t, dtype=np.float64))
    n0 = np.asarray(n0, dtype=np.float64)
    rho = np.asarray(rho, dtype=np.float64)
    G = n0.size
    if np.ndim(k_join) == 0 and np.ndim(k_leave) == 0:
        kf, kb = float(k_join), float(k_leave)
        lam = kf * rho.sum()
        r = lam - kb
        N0 = n0.sum()
        e_r = np.exp(r * t)[:, None]
        e_b = np.exp(-kb * t)[:, None]
        n = n0[None, :] * e_b + (rho / rho.sum())[None, :] * N0 * (e_r - e_b)
        return n, N0 * e_r[:, 0]
    kf = np.broadcast_to(np.asarray(k_join, dtype=np.float64), (G,))
    kb = np.broadcast_to(np.asarray(k_leave, dtype=np.float64), (G,))
    A = np.outer(kf * rho, np.ones(G)) - np.diag(kb)
    n = np.stack([expm(A * tk) @ n0 for tk in t])
    return n, n.sum(axis=1)


def size_moments_beta0(t, N0: int, k_join: float, k_leave: float, rho_sum: float):
    """Mean and variance of N(t) for the linear birth-death process (uniform k).

    Birth rate lambda N with lambda = k_f Sum(rho); death rate mu N with mu = k_b.
    For one ancestor, with m = e^{(lambda - mu) t}, E = m and
    Var = (lambda + mu)/(lambda - mu) m (m - 1) (Kendall 1948). For lambda = mu,
    Var = 2 lambda t. N_0 independent ancestors add.
    """
    t = np.atleast_1d(np.asarray(t, dtype=np.float64))
    lam = k_join * rho_sum
    mu = k_leave
    if np.isclose(lam, mu, rtol=0, atol=1e-15):
        return N0 * np.ones_like(t), N0 * 2.0 * lam * t
    m = np.exp((lam - mu) * t)
    return N0 * m, N0 * (lam + mu) / (lam - mu) * m * (m - 1.0)


def planted_power(times, N0: int, k_join: float, k_leave: float, rho_sum: float, runs: int,
                  kb_factor: float = PLANTED_KB_FACTOR, alpha: float = ALPHA) -> float:
    """Power of the mean-N(t) test to catch k_b * kb_factor; a lower bound for the family."""
    times = np.asarray(times, dtype=np.float64)
    m0, v0 = size_moments_beta0(times, N0, k_join, k_leave, rho_sum)
    m1, v1 = size_moments_beta0(times, N0, k_join, k_leave * kb_factor, rho_sum)
    z = norm.isf(alpha / (2 * times.size))
    se0 = np.sqrt(v0 / runs)
    se1 = np.sqrt(v1 / runs)
    shift = np.abs(m1 - m0)
    power = norm.sf((z * se0 - shift) / se1) + norm.cdf((-z * se0 - shift) / se1)
    return float(np.max(power))


def check_ensemble_means(times, counts: np.ndarray, n0, k_join: float, k_leave: float, rho,
                         alpha: float = ALPHA, min_power: float = MIN_POWER) -> CheckResult:
    """Ensemble means of N(t) and n_i(t) against the beta = 0 closed form.

    ``counts`` is [run, time, type] from beta = 0 runs without fission. N(t) uses the
    closed-form variance; the per-type means use the sample variance. Both are
    Bonferroni-corrected at ``alpha``. The design's power against the planted wrong k_b
    must reach ``min_power``.
    """
    times = np.asarray(times, dtype=np.float64)
    counts = np.asarray(counts)
    if counts.ndim != 3 or counts.shape[1] != times.size:
        raise ValueError("counts must be [run, time, type] matching times")
    R, T, G = counts.shape
    rho = np.asarray(rho, dtype=np.float64)
    N0 = int(np.sum(n0))
    n_mean, N_mean = closed_form_beta0(times, n0, k_join, k_leave, rho)
    _, N_var = size_moments_beta0(times, N0, k_join, k_leave, rho.sum())
    sizes = counts.sum(axis=2)
    z_size = (sizes.mean(axis=0) - N_mean) / np.sqrt(N_var / R)
    crit_size = norm.isf(alpha / (2 * T))
    sd_types = counts.std(axis=0, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        z_types = (counts.mean(axis=0) - n_mean) / (sd_types / np.sqrt(R))
    z_types = np.where(sd_types > 0, z_types, 0.0)
    crit_types = norm.isf(alpha / (2 * T * G))
    power = planted_power(times, N0, k_join, k_leave, rho.sum(), R)
    passed = bool(np.all(np.abs(z_size) <= crit_size) and np.all(np.abs(z_types) <= crit_types)
                  and power >= min_power)
    return CheckResult("exchange_law_beta0_ensemble_means", passed, dict(
        runs=R, times=times, z_size=z_size, crit_size=crit_size,
        max_abs_z_types=float(np.max(np.abs(z_types))), crit_types=crit_types,
        planted_kb_factor=PLANTED_KB_FACTOR, planted_power=power, min_power=min_power,
        underpowered=power < min_power))
