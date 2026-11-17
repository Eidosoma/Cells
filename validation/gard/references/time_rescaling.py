"""Row 2. Catalysis is kinetic only: uniform beta = c is a pure time rescaling.

Claim: catalysis scales rates and never the force. A uniform matrix must give the
beta = 0 process with time scaled by 1 + c, and the same event sequence under shared
uniforms. A factor applied to joins only must be caught.

Derivation. With beta_ij = c for all i, j: (beta x)_i = c N, so
b_i(x) = 1 + c N / N = 1 + c at every state. The pair-consistent leave factor is
b_i(x - e_i) = 1 + c (N - 1)/(N - 1) = 1 + c for N >= 2. Every join and leave
propensity, in both forms, is (1 + c) times its beta = 0 value. In the direct method,
the channel is the first j with prefix_j > u2 a0. Multiplying every a_j by
s = 1 + c multiplies every prefix and a0 by s, so the channel is the same for every u2.
The waiting time -ln(u1)/a0 is divided by s. Under shared uniforms the two runs make the
same events, and every event time, and every fission time, of the beta = c run is the
beta = 0 time divided by s. The splits are the same too, because the parents and the
partition uniforms are.

Exactness in floating point. If s is a power of two (c = 1 or 3), every product
s * a_j, every prefix and a0 scale exactly. c N / N = c exactly for these small
integers, so the choices are bitwise the same and t_c * s == t_0 bit for bit. For other
c the reference allows a relative ``RTOL_GENERAL`` on times. A channel flip then counts
as a failure unless it is a near-tie, which is reported.

Planted control: a factor on joins only. The join share of a0 changes, so the selected
channel moves for a band of u2, and a0 is no longer s a0. Both the sequence and the
times break.
"""

from __future__ import annotations

import math
from itertools import product

import numpy as np

from .common import CheckResult
from .kernels import ExactLaw, FORMS

RTOL_GENERAL = 1e-12


def is_power_of_two(s: float) -> bool:
    m, _ = math.frexp(s)
    return s > 0 and m == 0.5


def uniform_beta_identity_exact(G: int, c, max_mass: int, k_join=1, k_leave=1, rho="1/7") -> CheckResult:
    """On every state with 1 <= N <= max_mass, both forms: a(beta = c) == (1 + c) a(beta = 0) exactly."""
    from fractions import Fraction

    c = Fraction(c)
    worst = []
    n_checked = 0
    for form in FORMS:
        law_c = ExactLaw.make([[c] * G for _ in range(G)], k_join, k_leave, form, rho=Fraction(rho))
        law_0 = ExactLaw.make([[0] * G for _ in range(G)], k_join, k_leave, form, rho=Fraction(rho))
        for x in product(range(max_mass + 1), repeat=G):
            N = sum(x)
            if N < 1 or N > max_mass:
                continue
            pc, mc = law_c.propensities(x)
            p0, m0 = law_0.propensities(x)
            n_checked += 1
            if any(pc[i] != (1 + c) * p0[i] or mc[i] != (1 + c) * m0[i] for i in range(G)):
                worst.append((form, x))
    return CheckResult("uniform_beta_propensity_identity", not worst,
                       dict(states_checked=n_checked, failures=worst[:10], c=str(c)))


def check_time_rescaling(channels_0, times_0, channels_c, times_c, c: float,
                         splits_0=None, splits_c=None, fission_times_0=None, fission_times_c=None) -> CheckResult:
    """Compare a beta = 0 run and a uniform beta = c run that share uniforms."""
    ch0 = np.asarray(channels_0)
    chc = np.asarray(channels_c)
    t0 = np.asarray(times_0, dtype=np.float64)
    tc = np.asarray(times_c, dtype=np.float64)
    s = 1.0 + float(c)
    exact = is_power_of_two(s)
    n = min(ch0.size, chc.size)
    first_diff = np.flatnonzero(ch0[:n] != chc[:n])
    same_events = ch0.size == chc.size and first_diff.size == 0
    upto = n if first_diff.size == 0 else int(first_diff[0])
    if exact:
        time_ok = bool(np.array_equal(tc[:upto] * s, t0[:upto]))
        max_rel = float(np.max(np.abs(tc[:upto] * s - t0[:upto]) / np.maximum(t0[:upto], 1e-300))) if upto else 0.0
    else:
        max_rel = float(np.max(np.abs(tc[:upto] * s - t0[:upto]) / np.maximum(t0[:upto], 1e-300))) if upto else 0.0
        time_ok = max_rel <= RTOL_GENERAL
    split_ok = True
    if splits_0 is not None and splits_c is not None:
        split_ok = bool(np.array_equal(np.asarray(splits_0), np.asarray(splits_c)))
    ftime_ok = True
    if fission_times_0 is not None and fission_times_c is not None:
        f0 = np.asarray(fission_times_0, dtype=np.float64)
        fc = np.asarray(fission_times_c, dtype=np.float64)
        if f0.shape != fc.shape:
            ftime_ok = False
        elif exact:
            ftime_ok = bool(np.array_equal(fc * s, f0))
        else:
            ftime_ok = bool(np.all(np.abs(fc * s - f0) <= RTOL_GENERAL * np.abs(f0)))
    passed = bool(same_events and time_ok and split_ok and ftime_ok)
    return CheckResult("uniform_beta_time_rescaling", passed, dict(
        scale=s, exact_power_of_two=exact, events_0=int(ch0.size), events_c=int(chc.size),
        first_differing_event=None if first_diff.size == 0 else int(first_diff[0]),
        max_relative_time_error=max_rel, splits_equal=split_ok, fission_times_scaled=ftime_ok))
