"""Row OL1-4b: mass action with registry potentials, in the large-system limit.

Claim (§2.1, §7.1). The exact SSA's means converge, as the volume grows, to the same network's
deterministic rate equations with k- = k+ exp(Sum nu mu0) (Kurtz 1972, from memory), checked
against an independent SciPy integration.

**The world** (``ol1_wb_m{M}``, registered): 2 S -> T in the pool, forward rate k = 1/2 per s,
K = exp(-(mu0_T - 2 mu0_S)) = 1, so k- = 1/2 per s, with X = N_A V c0 = M and 2M molecules of S at
the start (concentration 2 c0). Under the pool's mass action (§0.2a) the exact rates are

    a+(n_T) = k (2M - 2 n_T)(2M - 2 n_T - 1)/M,     a-(n_T) = k- n_T,

on the one-dimensional chain n_T = 0..M.

**The deterministic limit,** y = n_T/X, c_S = 2 - 2y:  dy/dt = 4k (1 - y)^2 - k- y. It is a
Riccati equation with constant coefficients. Its roots y- < y+ give, from y(0) = 0,

    y(t) = (y- - y+ R(t))/(1 - R(t)),   R(t) = (y-/y+) exp(-4k (y+ - y-) t),

and y- = (9 - sqrt 17)/8 = 0.6096 at k = k- = 1/2; the relaxation rate is 4k (y+ - y-) =
sqrt 17 / 2 = 2.06 per s. ``ode_solve`` integrates the general dilute rate equations with SciPy
(Radau, rtol 1e-12) from the world's declaration, independently of this closed form; the tests
hold the two equal to 1e-10.

**Why the test's null is the master equation, not the ODE.** For a nonlinear network the exact
mean differs from the ODE by O(1/X). A well-powered z-test against the ODE would reject a correct
engine on the small rungs. So the engine's ensemble means are tested against the exact mean of
the finite-X master equation on every rung (solved by ``expm_multiply`` on the M + 1 states),
and the master equation's approach to the ODE, |E[n_T]/X - y| = O(1/X), is a reference-only
fact, registered and checked in the tests (the gap falls by about 4 per rung, as X grows by 4).

**The statistics** (registered in ``designs/ol1_design.json``). On each of four rungs
(M = 5, 20, 80, 320), R independent runs to t = 2 s; at t = 0.25, 0.5, 1 and 2 s, the state after
the last event at or before t. Each of the 16 means is a z-test against the master equation's
mean with its exact variance; the family is Bonferroni-corrected to alpha = 1e-3 (two-sided,
z = 4.00). The power against each planted control is computed before any record is read, from
the planted law's own exact master equation (normal approximation for the mean of R runs):
- ``power_propensity``: n_S^2 in place of n_S (n_S - 1);
- ``dropped_c0``: X = N_A V without c0, a factor 1000;
- ``wrong_sign``: the reverse from exp(-DeltaF);
- ``coefficient``: S -> T run in place of 2 S -> T (refused at parse by the moiety check, and
  caught here if it were not);
- ``biased_selection``: the reverse channel selected at 0.9 of its weight, time from the true
  total (the chain is then the master equation with rates a0 a_j w_j / Sum w a).
The design fails as underpowered if any control's family power is below 0.99.
"""

from __future__ import annotations

import functools
import math

import numpy as np
import scipy.sparse as sp
from scipy.integrate import solve_ivp
from scipy.linalg import expm
from scipy.sparse.linalg import expm_multiply
from scipy.stats import norm

from .closed_world import generator_from_table
from .common import ALPHA, MIN_POWER, CheckResult
from .detailed_balance import reference_table
from .laws import Law
from .probes import closed_world_states
from .world import Step, World

OBSERVATION_TIMES = (0.25, 0.5, 1.0, 2.0)
ENSEMBLE_RUNS = 2000
PLANTED_ENSEMBLE = ("power_propensity", "dropped_c0", "wrong_sign", "coefficient", "biased_selection")
BIAS_WEIGHT = 0.9
DENSE_LIMIT = 2000
"""Chains up to this many states use a dense matrix exponential (scaling and squaring), which
stays fast and accurate for the stiff planted chains; larger chains use expm_multiply."""


# ---------------------------------------------------------------- the master equation

def chain(law: Law) -> tuple[np.ndarray, sp.csr_matrix]:
    """The world's reachable states from its initial state and the generator of the law."""
    w = law.world
    states = closed_world_states(w, w.initial_state)
    t = reference_table(law, states)
    return states, generator_from_table(w, states, t["a_plus"], t["a_minus"])


def biased_generator(law: Law, states, weight: float = BIAS_WEIGHT) -> sp.csr_matrix:
    """The chain of an SSA that selects reverse channels at ``weight`` of their propensity and
    draws time from the true total: each transition's rate becomes a0 w_j a_j / Sum_k w_k a_k."""
    t = reference_table(law, states)
    a_plus, a_minus = t["a_plus"].copy(), t["a_minus"].copy()
    a0 = a_plus.sum(1) + a_minus.sum(1)
    den = a_plus.sum(1) + weight * a_minus.sum(1)
    scale = np.where(den > 0, a0 / np.where(den > 0, den, 1.0), 0.0)
    return generator_from_table(law.world, states, a_plus * scale[:, None], weight * a_minus * scale[:, None])


def transient_moments(states, Q: sp.csr_matrix, initial, times) -> tuple[np.ndarray, np.ndarray]:
    """Exact means and variances of every coordinate at the given times (master equation)."""
    idx = {tuple(int(v) for v in s): k for k, s in enumerate(states)}
    p0 = np.zeros(len(states))
    p0[idx[tuple(int(v) for v in initial)]] = 1.0
    if len(states) <= DENSE_LIMIT:
        QT = Q.T.toarray()
        P = np.array([expm(QT * float(t)) @ p0 for t in times])
    else:
        QT = Q.T.tocsc()
        P = np.array([expm_multiply(QT * float(t), p0) for t in times])
    P = np.clip(P, 0.0, None)
    P /= P.sum(1, keepdims=True)
    S = np.asarray(states, float)
    means = P @ S
    second = P @ (S ** 2)
    return means, second - means ** 2


# ---------------------------------------------------------------- the deterministic limit

def riccati_wb(times, k: float = 0.5, k_minus: float = 0.5) -> np.ndarray:
    """Closed-form y(t) = n_T/X for 2 S -> T from c_S = 2, c_T = 0 (see the module docstring)."""
    a, b, c = 4 * k, -(8 * k + k_minus), 4 * k   # dy/dt = a y^2 + b y + c
    disc = math.sqrt(b * b - 4 * a * c)
    y_minus, y_plus = (-b - disc) / (2 * a), (-b + disc) / (2 * a)
    lam = a * (y_plus - y_minus)
    out = []
    for t in times:
        R = (y_minus / y_plus) * math.exp(-lam * t)
        out.append((y_minus - y_plus * R) / (1 - R))
    return np.array(out)


def ode_solve(world: World, times, rtol: float = 1e-12) -> np.ndarray:
    """The dilute network's rate equations in units of c0, integrated with SciPy (Radau).

    dc/dt = Sum_r nu_r (k_r prod c^alpha - k-_r prod c^beta), k-_r = k_r exp(Sum nu mu0), for a
    world whose finite places are dilute (membrane places, if any, take no step)."""
    places = world.finite
    X = [world.X(p.phase) if not p.membrane else None for p in places]
    em = [p.exp_minus_mu0 for p in places]
    stoich = []
    for st in world.steps:
        if st.locus == "membrane":
            raise ValueError("ode_solve covers dilute steps only")
        al, be = world.alpha(st), world.beta_finite(st)
        km = st.rate.exact
        for i, (a, b) in enumerate(zip(al, be)):
            km *= em[i] ** (a - b)
        stoich.append((np.array(al, float), np.array(be, float), float(st.rate.exact), float(km)))

    def rhs(_t, c):
        out = np.zeros_like(c)
        for al, be, kf, km in stoich:
            j = kf * np.prod(np.where(al > 0, c ** al, 1.0)) - km * np.prod(np.where(be > 0, c ** be, 1.0))
            out += (be - al) * j
        return out

    c0 = np.array([world.initial_state.get(p.name, 0) / float(X[i]) if X[i] else 0.0 for i, p in enumerate(places)])
    sol = solve_ivp(rhs, (0.0, float(times[-1])), c0, method="Radau", t_eval=list(times), rtol=rtol, atol=1e-14)
    if not sol.success:
        raise RuntimeError(sol.message)
    return sol.y.T


# ---------------------------------------------------------------- the registered design

def rung_world(M: int) -> World:
    from .registered import registered_world

    return registered_world(f"ol1_wb_m{M}")


def planted_chain(M: int, form: str, conv) -> tuple[np.ndarray, sp.csr_matrix, tuple]:
    """A planted control's chain on rung M (states, generator, initial state)."""
    w = rung_world(M)
    if form == "coefficient":
        # S -> T in place of 2 S -> T: built directly (the world parser refuses it, by design)
        n0 = w.state_from(w.initial_state)
        iS, iT = w.index("S@pool"), w.index("T@pool")
        tot = n0[iS] + n0[iT]
        states = []
        for nT in range(tot + 1):
            s = list(n0)
            s[iS], s[iT] = tot - nT, nT
            states.append(tuple(s))
        st = w.steps[0]
        k = float(st.rate.exact)
        em_S, em_T = float(w.places["S@pool"].exp_minus_mu0), float(w.places["T@pool"].exp_minus_mu0)
        a_plus = np.array([[k * s[iS]] for s in states])            # k X (n_S/X)
        a_minus = np.array([[k * em_S / em_T * s[iT]] for s in states])  # k- X (n_T/X)
        a_plus[-1, 0] = 0.0
        a_minus[0, 0] = 0.0
        fake = World(w.name + "_coefficient", w.c0_mM, w.avogadro, w.volumes_L, w.places, w.moieties, w.chi,
                     (Step(st.name, st.locus, {"S@pool": 1}, {"T@pool": 1}, st.rate, ()),), w.initial_state)
        return np.array(states), generator_from_table(fake, np.array(states), a_plus, a_minus), n0
    law = Law(w, conv, planted=None if form == "biased_selection" else form)
    states, Q = chain(law)
    if form == "biased_selection":
        Q = biased_generator(law, states)
    return states, Q, w.state_from(w.initial_state)


def z_critical(n_tests: int, alpha: float = ALPHA) -> float:
    return float(norm.isf(alpha / (2 * n_tests)))


def family_power(mu0, var0, mu1, var1, R: int, zc: float) -> float:
    """P(at least one |z| > zc) under the planted law, by a union lower bound: the largest
    single-test power (exact under the normal approximation for each test)."""
    best = 0.0
    for m0, v0, m1, v1 in zip(np.ravel(mu0), np.ravel(var0), np.ravel(mu1), np.ravel(var1)):
        se0 = math.sqrt(max(v0, 1e-300) / R)
        se1 = math.sqrt(max(v1, 1e-300) / R)
        shift = (m1 - m0) / se0
        ratio = se1 / se0
        p = norm.sf((zc - shift) / ratio) + norm.cdf((-zc - shift) / ratio)
        best = max(best, float(p))
    return best


def design_numbers(conv, rungs=None, R: int = ENSEMBLE_RUNS, times=OBSERVATION_TIMES) -> dict:
    """The registered ladder's null moments, the ODE gap, and each planted control's power."""
    from .registered import WB_RUNGS

    rungs = tuple(rungs or WB_RUNGS)
    zc = z_critical(len(rungs) * len(times))
    out = dict(rungs=list(rungs), runs=R, times=list(times), z_critical=zc, alpha=ALPHA, rung={})
    y_ode = riccati_wb(times)
    nulls = {}
    for M in rungs:
        w = rung_world(M)
        law = Law(w, conv)
        states, Q = chain(law)
        iT = w.index("T@pool")
        mu, var = transient_moments(states, Q, w.state_from(w.initial_state), times)
        nulls[M] = (mu[:, iT], var[:, iT])
        out["rung"][M] = dict(mean_T=mu[:, iT].tolist(), var_T=var[:, iT].tolist(),
                              ode_gap=(mu[:, iT] / M - y_ode).tolist())
    out["ode"] = y_ode.tolist()
    power = {}
    for form in PLANTED_ENSEMBLE:
        per_rung = []
        for M in rungs:
            states, Q, n0 = planted_chain(M, form, conv)
            w = rung_world(M)
            idx_T = w.index("T@pool")
            mu1, var1 = transient_moments(states, Q, n0, times)
            per_rung.append(family_power(nulls[M][0], nulls[M][1], mu1[:, idx_T], var1[:, idx_T], R, zc))
        power[form] = dict(per_rung=per_rung, family=max(per_rung))
    out["power"] = power
    out["underpowered"] = [f for f, p in power.items() if p["family"] < MIN_POWER]
    return out


@functools.lru_cache(maxsize=1)
def registered_ladder_design() -> dict:
    """The registered ladder's numbers (the pool takes no convention token; computed once)."""
    from .world import Conventions

    return design_numbers(Conventions(condensed_measure="multinomial", last_molecule="kept"))


# ---------------------------------------------------------------- the check on an ensemble

def ensemble_test(samples: dict, design: dict) -> CheckResult:
    """samples[M] = array [runs, times] of n_T at the registered times; z-tests against the
    master equation's exact means (Bonferroni over every rung and time)."""
    zc = design["z_critical"]
    rows, worst, fail = [], 0.0, False
    if design.get("underpowered"):
        return CheckResult("mass_action_ladder", False, dict(problem="underpowered design",
                                                             underpowered=design["underpowered"]))
    for M in design["rungs"]:
        x = np.asarray(samples[M], float)
        if x.ndim != 2 or x.shape[1] != len(design["times"]):
            return CheckResult("mass_action_ladder", False, dict(problem=f"rung {M}: samples shape {x.shape}"))
        R = x.shape[0]
        mu = np.asarray(design["rung"][M]["mean_T"])
        var = np.asarray(design["rung"][M]["var_T"])
        z = (x.mean(0) - mu) / np.sqrt(var / R)
        worst = max(worst, float(np.max(np.abs(z))))
        fail |= bool(np.any(np.abs(z) > zc))
        rows.append(dict(rung=M, runs=R, z=z.tolist(), mean=x.mean(0).tolist(), null=mu.tolist(),
                         distance_to_ode=(x.mean(0) / M - np.asarray(design["ode"])).tolist()))
    return CheckResult("mass_action_ladder", not fail, dict(z_critical=zc, max_abs_z=worst, rungs=rows))

