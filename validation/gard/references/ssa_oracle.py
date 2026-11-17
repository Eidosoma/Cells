"""Row 5. The SSA is exact: a host oracle with common random variates, and the
beta = 0 linear birth-death law of the total size.

Claim: the engine's stochastic simulation is the exact direct method on the law's
propensities. A biased channel choice must be caught.

Two references, each with teeth:

1. The host oracle (Gillespie 1977, the direct method). Given the run's declared
   convention and the uniforms the run consumed (diagnostic mode), the next event is
   fully determined. From state x with channel propensities a (in the declared order)
   and a0 = prefix[-1], the waiting time is tau = -ln(u1)/a0. The channel is the first j
   with prefix_j > u2 a0, under the run's declared rule. The oracle replays the run event
   by event, continuing across fissions from the recorded split and followed daughter.
   Every channel must agree, except near-ties. A near-tie is a u2 a0 within a relative
   ``TIE_RTOL`` of a prefix boundary, where summation-order rounding can legitimately flip
   the choice; it is counted and reported, never silently passed. Every time must agree to
   ``TIME_RTOL``. A run that declares no convention is refused.
2. At beta = 0 with uniform constants, births occur at lambda N (lambda = k_f Sum(rho)) and
   deaths at mu N (mu = k_b). The total size is the linear birth-death process. With
   m = e^{(lambda - mu) t}, one ancestor has
   P(0) = alpha, P(n) = (1 - alpha)(1 - g) g^{n-1} for n >= 1, where
   alpha = mu (m - 1)/(lambda m - mu) and g = lambda (m - 1)/(lambda m - mu)
   (Kendall 1948). N_0 ancestors convolve. The mean is N_0 m and the variance is
   N_0 (lambda + mu)/(lambda - mu) m (m - 1). The ensemble check tests the mean (z) and
   the whole law of N(t) (a chi-square on pooled cells) at registered times and level.

Planted control: a biased channel choice. Leaves are selected at 0.9 of their weight,
and time is still drawn from the true a0. Under common variates it changes channels at
once. In the ensemble it is again a linear birth-death process, with
lambda' = (lambda + mu) lambda/(lambda + 0.9 mu) and
mu' = (lambda + mu) 0.9 mu/(lambda + 0.9 mu). That gives the power, computed before any
record is read.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.stats import chi2, ncx2, norm

from .common import ALPHA, MIN_POWER, CheckResult
from .exchange_law import size_moments_beta0
from .kernels import ExchangeLaw, propensities

TIE_RTOL = 1e-12
TIME_RTOL = 1e-12
PLANTED_LEAVE_WEIGHT = 0.9

JOINS_THEN_LEAVES = "joins_then_leaves"
TAU_NEG_LOG_U1 = "neg_log_u1_over_a0"
SELECT_FIRST_PREFIX_GT = "first_prefix_gt_u2_a0"
UNIFORM_LOW52_HALF = "low52_plus_half_times_2^-52"


@dataclass(frozen=True)
class SSAConvention:
    """A run's declared direct-method convention."""

    channel_order: str
    tau: str
    select: str
    uniform: str

    KNOWN = {
        "channel_order": (JOINS_THEN_LEAVES,),
        "tau": (TAU_NEG_LOG_U1,),
        "select": (SELECT_FIRST_PREFIX_GT,),
        "uniform": (UNIFORM_LOW52_HALF,),
    }

    @staticmethod
    def from_declared(declared: dict | None) -> "SSAConvention":
        """Read a declared convention; refuse a missing or unknown one."""
        if not declared:
            raise ConventionMissing("the run declares no SSA convention; the oracle refuses it")
        missing = [k for k in SSAConvention.KNOWN if k not in declared]
        if missing:
            raise ConventionMissing(f"the run's SSA convention lacks {missing}")
        for key, allowed in SSAConvention.KNOWN.items():
            if declared[key] not in allowed:
                raise ConventionMissing(f"unknown SSA convention {key}={declared[key]!r}; known: {allowed}")
        return SSAConvention(**{k: declared[k] for k in SSAConvention.KNOWN})


class ConventionMissing(ValueError):
    """The run did not declare a convention the oracle needs."""


# The convention the engine side declared (relayed by the lead, 17 November 2026). The
# oracle never assumes it: every run must declare its own.
DECLARED_BY_ENGINE = dict(channel_order=JOINS_THEN_LEAVES, tau=TAU_NEG_LOG_U1,
                          select=SELECT_FIRST_PREFIX_GT, uniform=UNIFORM_LOW52_HALF)


def uniforms_from_words(words: np.ndarray) -> np.ndarray:
    """u = (m + 0.5) 2^-52 with m the low 52 bits of each 64-bit word, so 0 < u < 1."""
    w = np.asarray(words, dtype=np.uint64)
    m = (w & np.uint64((1 << 52) - 1)).astype(np.float64)
    return (m + 0.5) * 2.0 ** -52


def channel_vector(a_plus: np.ndarray, a_minus: np.ndarray, order: str = JOINS_THEN_LEAVES) -> np.ndarray:
    if order != JOINS_THEN_LEAVES:
        raise ConventionMissing(f"unknown channel order {order!r}")
    return np.concatenate([a_plus, a_minus])


def channel_event(j: int, n_types: int) -> tuple[int, int]:
    """Channel index -> (type, sign) for joins 0..G-1 then leaves 0..G-1."""
    return (j, +1) if j < n_types else (j - n_types, -1)


def signed_channel(type_: int, sign: int) -> int:
    """The engine's signed event code: +(i+1) for a join of i, -(i+1) for a leave."""
    return sign * (type_ + 1)


def select_channel(a: np.ndarray, u2: float, leave_weight: float = 1.0) -> tuple[int, float]:
    """First j with prefix_j > u2 * a0; returns (j, relative margin to the nearest boundary).

    ``leave_weight`` != 1 is the planted biased choice (leaves under-weighted); it is only
    used by tests and controls.
    """
    if leave_weight != 1.0:
        a = a.copy()
        a[a.size // 2:] *= leave_weight
    prefix = np.cumsum(a)
    a0 = prefix[-1]
    target = u2 * a0
    j = int(np.searchsorted(prefix, target, side="right"))
    if j >= a.size:  # rounding at u2 -> 1: take the last positive channel
        j = int(np.flatnonzero(a > 0)[-1])
    lower = prefix[j - 1] if j > 0 else 0.0
    margin = min(abs(target - lower), abs(prefix[j] - target)) / a0
    return j, float(margin)


def direct_step(law: ExchangeLaw, x: np.ndarray, u1: float, u2: float,
                leave_weight: float = 1.0) -> tuple[int, int, float, float]:
    """One direct-method event: (type, sign, tau, tie margin); tau is inf when stuck."""
    a_plus, a_minus = propensities(law, x)
    a = channel_vector(a_plus, a_minus)
    a0 = float(np.cumsum(a)[-1])
    if not a0 > 0.0:
        return -1, 0, math.inf, 1.0
    j, margin = select_channel(a, u2, leave_weight)
    tau = -math.log(u1) / a0
    type_, sign = channel_event(j, law.n_types)
    return type_, sign, tau, margin


def replay(law: ExchangeLaw, founder: np.ndarray, uniforms: np.ndarray, fission_mass: int,
           splits: np.ndarray, followed: np.ndarray, event_guard: int | None = None,
           leave_weight: float = 1.0) -> dict:
    """Replay a single lineage from its uniforms; fissions use the recorded splits.

    Returns the oracle's signed channels, event times, events per growth and tie margins.
    """
    x = np.array(founder, dtype=np.int64)
    G = law.n_types
    E = uniforms.shape[0]
    channels = np.zeros(E, dtype=np.int64)
    times = np.zeros(E, dtype=np.float64)
    margins = np.ones(E, dtype=np.float64)
    per_growth: list[int] = []
    t = 0.0
    f = 0
    in_growth = 0
    k = 0
    while k < E:
        type_, sign, tau, margin = direct_step(law, x, uniforms[k, 0], uniforms[k, 1], leave_weight)
        if type_ < 0:
            break
        x[type_] += sign
        t += tau
        channels[k] = signed_channel(type_, sign)
        times[k] = t
        margins[k] = margin
        k += 1
        in_growth += 1
        guard_hit = event_guard is not None and in_growth >= event_guard
        if x.sum() == fission_mass or guard_hit:
            per_growth.append(in_growth)
            in_growth = 0
            if f >= len(splits):
                break
            d1 = np.asarray(splits[f], dtype=np.int64)
            x = d1.copy() if int(followed[f]) == 0 else x - d1
            f += 1
    if in_growth:
        per_growth.append(in_growth)
    return dict(channels=channels[:k], times=times[:k], margins=margins[:k],
                events_per_growth=np.asarray(per_growth, dtype=np.int64), final_state=x)


def check_crn_replay(law: ExchangeLaw, founder: np.ndarray, uniforms: np.ndarray,
                     event_channel: np.ndarray, event_time: np.ndarray, fission_mass: int,
                     splits: np.ndarray, followed: np.ndarray, events_per_growth: np.ndarray | None,
                     event_guard: int | None = None) -> CheckResult:
    """Compare a run's event trace with the oracle's replay under the same uniforms."""
    uniforms = np.asarray(uniforms, dtype=np.float64)
    event_channel = np.asarray(event_channel, dtype=np.int64)
    event_time = np.asarray(event_time, dtype=np.float64)
    if uniforms.shape != (event_channel.size, 2):
        return CheckResult("ssa_crn_replay", False, dict(
            error=f"event_uniforms shape {uniforms.shape} does not match {event_channel.size} events"))
    rep = replay(law, founder, uniforms, fission_mass, splits, followed, event_guard)
    n = min(rep["channels"].size, event_channel.size)
    same = rep["channels"][:n] == event_channel[:n]
    differ = np.flatnonzero(~same)
    ties = differ[rep["margins"][differ] <= TIE_RTOL] if differ.size else differ
    real = np.setdiff1d(differ, ties)
    first_real = int(real[0]) if real.size else None
    # Times are compared up to the first differing channel (after it the paths diverge).
    upto = n if differ.size == 0 else int(differ[0])
    rel = np.abs(rep["times"][:upto] - event_time[:upto]) / np.maximum(np.abs(event_time[:upto]), 1e-300)
    max_rel = float(rel.max()) if upto else 0.0
    length_ok = rep["channels"].size == event_channel.size
    epg_ok = True
    if events_per_growth is not None:
        epg = np.asarray(events_per_growth, dtype=np.int64)
        mine = rep["events_per_growth"]
        epg_ok = bool(np.array_equal(epg[epg > 0], mine[mine > 0]))
    passed = bool(real.size == 0 and ties.size == 0 and length_ok and max_rel <= TIME_RTOL and epg_ok)
    return CheckResult("ssa_crn_replay", passed, dict(
        events_compared=n, oracle_events=int(rep["channels"].size), run_events=int(event_channel.size),
        differing_channels=int(differ.size), near_ties=int(ties.size), first_real_difference=first_real,
        max_relative_time_error=max_rel, time_rtol=TIME_RTOL, tie_rtol=TIE_RTOL,
        events_per_growth_match=epg_ok))


# ------------------------------------------------------------ birth-death reference

def birth_death_pmf(t: float, N0: int, lam: float, mu: float, tail: float = 1e-15) -> np.ndarray:
    """Exact pmf of N(t) for the linear birth-death process from N0 (absorbing 0)."""
    if lam <= 0:
        raise ValueError("lambda must be positive")
    if abs(lam - mu) < 1e-15:
        alpha = g = lam * t / (1.0 + lam * t)
    else:
        m = math.exp((lam - mu) * t)
        den = lam * m - mu
        alpha = mu * (m - 1.0) / den
        g = lam * (m - 1.0) / den
    mean, var = size_moments_beta0(t, N0, lam, mu, 1.0)
    nmax = int(mean[0] + 40.0 * math.sqrt(max(var[0], 1.0))) + 10
    one = np.empty(nmax + 1)
    one[0] = alpha
    n = np.arange(1, nmax + 1)
    one[1:] = (1 - alpha) * (1 - g) * g ** (n - 1)
    out = np.array([1.0])
    for _ in range(N0):
        out = np.convolve(out, one)[: nmax + 1]
    if 1.0 - out.sum() > 1e-9:
        raise ValueError("pmf truncation too coarse")
    return out


def pooled_cells(p: np.ndarray, expected_total: float, min_expected: float = 5.0) -> list[np.ndarray]:
    """Group adjacent support points so every cell expects at least ``min_expected``."""
    cells: list[list[int]] = []
    cur: list[int] = []
    acc = 0.0
    for k in range(p.size):
        cur.append(k)
        acc += p[k] * expected_total
        if acc >= min_expected:
            cells.append(cur)
            cur, acc = [], 0.0
    if cur:
        if cells:
            cells[-1].extend(cur)
        else:
            cells.append(cur)
    return [np.asarray(c) for c in cells]


def biased_rates(lam: float, mu: float, leave_weight: float = PLANTED_LEAVE_WEIGHT) -> tuple[float, float]:
    """Effective birth-death rates under the planted biased channel choice."""
    tot = lam + mu
    sel = lam + leave_weight * mu
    return tot * lam / sel, tot * leave_weight * mu / sel


def ensemble_power(times, N0: int, lam: float, mu: float, runs: int, alpha: float = ALPHA,
                   leave_weight: float = PLANTED_LEAVE_WEIGHT) -> dict:
    """Power of the mean and chi-square tests against the planted biased choice."""
    times = np.asarray(times, dtype=np.float64)
    lam1, mu1 = biased_rates(lam, mu, leave_weight)
    m0, v0 = size_moments_beta0(times, N0, lam, mu, 1.0)
    m1, v1 = size_moments_beta0(times, N0, lam1, mu1, 1.0)
    z = norm.isf(alpha / (4 * times.size))
    shift = np.abs(m1 - m0)
    se0, se1 = np.sqrt(v0 / runs), np.sqrt(v1 / runs)
    p_mean = norm.sf((z * se0 - shift) / se1) + norm.cdf((-z * se0 - shift) / se1)
    t_end = float(times[-1])
    p0 = birth_death_pmf(t_end, N0, lam, mu)
    p1 = birth_death_pmf(t_end, N0, lam1, mu1)
    size = max(p0.size, p1.size)
    p0 = np.pad(p0, (0, size - p0.size))
    p1 = np.pad(p1, (0, size - p1.size))
    cells = pooled_cells(p0, runs)
    q0 = np.array([p0[c].sum() for c in cells])
    q0[-1] += 1.0 - q0.sum()
    q1 = np.array([p1[c].sum() for c in cells])
    q1[-1] += 1.0 - q1.sum()
    nc = runs * float(np.sum((q1 - q0) ** 2 / q0))
    df = len(cells) - 1
    crit = chi2.isf(alpha / 2, df)
    p_chi = float(ncx2.sf(crit, df, nc))
    return dict(mean_test=float(np.max(p_mean)), chi_square=p_chi, lam_biased=lam1, mu_biased=mu1)


def check_birth_death_ensemble(times, sizes: np.ndarray, N0: int, lam: float, mu: float,
                               alpha: float = ALPHA, min_power: float = MIN_POWER) -> CheckResult:
    """``sizes`` is [run, time]: N(t) from beta = 0 runs, uniform constants, no fission.

    Half of ``alpha`` goes to the mean tests (Bonferroni over times) and half to one
    chi-square on the law of N at the last registered time.
    """
    times = np.asarray(times, dtype=np.float64)
    sizes = np.asarray(sizes, dtype=np.int64)
    R, T = sizes.shape
    m0, v0 = size_moments_beta0(times, N0, lam, mu, 1.0)
    z = (sizes.mean(axis=0) - m0) / np.sqrt(v0 / R)
    zcrit = norm.isf(alpha / (4 * T))
    p0 = birth_death_pmf(float(times[-1]), N0, lam, mu)
    cells = pooled_cells(p0, R)
    q0 = np.array([p0[c].sum() for c in cells])
    q0[-1] += 1.0 - q0.sum()
    last = sizes[:, -1]
    edges = np.array([c[0] for c in cells] + [np.iinfo(np.int64).max])
    obs = np.array([np.sum((last >= edges[k]) & (last < edges[k + 1])) for k in range(len(cells))])
    stat = float(np.sum((obs - R * q0) ** 2 / (R * q0)))
    df = len(cells) - 1
    crit = chi2.isf(alpha / 2, df)
    power = ensemble_power(times, N0, lam, mu, R, alpha)
    worst_power = min(power["mean_test"], power["chi_square"])
    best_power = max(power["mean_test"], power["chi_square"])
    passed = bool(np.all(np.abs(z) <= zcrit) and stat <= crit and best_power >= min_power)
    return CheckResult("ssa_birth_death_ensemble", passed, dict(
        runs=R, times=times, z_mean=z, z_crit=zcrit, chi_square=stat, chi_square_crit=crit, df=df,
        planted_power=power, worst_test_power=worst_power, min_power=min_power,
        underpowered=best_power < min_power))
