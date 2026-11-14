"""The exact node kinetics, their dissipation and work integrals, passive equilibria and the
closed forms of Appendix A: an independent reference for local_species_reactions@1 (D152).

Written from docs/SHARED_INVENTORY_REACTIONS_DESIGN.md Appendix A ("the dissipation integral for
the references", "closed-form references") and §3.3; never from the engine's operator code.
NumPy and SciPy only (no `cells` import). Interface: validation/reactions/REFERENCES_USAGE.md.

The dissipation integral (probe 2d's method, Appendix A). At one node with constant multipliers,
the amounts follow dn/dt = nu J(n), and along that exact flow
    dH/dt = RT sum_passive J_r A_r >= 0,      dW/dt = sum_driven J_r sum_s nu_sr mu_s,
with mu_s = RT ln(n_s/V) + mu0'_s, so that W - H = G(n(t)) - G(n(0)) (the free-energy balance
of a reaction network, Rao & Esposito 2016; the dissipative structure of Mielke 2011). H is the
true heat that the operator's mixed-node bookings approximate; at a passive-only node it equals
-dG, at a driven-only node it is 0 and W = dG. The extents xi_r(t) = int J_r dt are integrated
too. Integration is by DOP853 (Hairer, Norsett & Wanner 1993, explicit Runge-Kutta of order 8
with step-size control), in the log-amounts ln n_s, which keeps a trace's relative accuracy and
its positivity; every record time is a step endpoint (segment by segment, never an
interpolant), and a multiplier change is never integrated across (one call per constant
multiplier; continue_from chains the calls).

Passive equilibrium: the minimiser of G over the stoichiometric class n0 + span(nu_passive),
found by a damped Newton iteration on the convex G (any closed detailed-balanced network
relaxes to it; Rao & Esposito 2016). For A <=> B at a common c0 it is
c_B/c_A = exp(-(mu0_B - mu0_A)/RT).

Closed forms (Appendix A): turnover, n(t) = n0 e^-kt + (P/k)(1 - e^-kt); Michaelis-Menten
depletion, K_M ln(S0/S) + (S0 - S) = V_max t, solved through the Lambert W function (Schnell &
Mendoza 1997) and refined by Newton's method in ln S.
"""

import math
from dataclasses import dataclass

import numpy as np
from scipy.integrate import solve_ivp
from scipy.special import lambertw

from validation.reactions import network_reference as nr


@dataclass(frozen=True)
class NodeTrajectory:
    """Records of the exact node kinetics. Axes: T records, S species, R reactions, N nodes."""

    times: np.ndarray  # [T] (s), absolute
    amounts: np.ndarray  # [T, S, N] (fmol)
    extents: np.ndarray  # [T, R, N] cumulative xi_r (fmol)
    heat: np.ndarray  # [T, N] true H (pJ), cumulative
    work: np.ndarray  # [T, N] true W (pJ), cumulative
    delta_G: np.ndarray  # [T, N] G(n(t)) - G(n(origin)) (pJ), increment form, cumulative
    closure: np.ndarray  # [T, N] W - H - delta_G (pJ): the integration's own balance
    origin: np.ndarray  # [S, N] the amounts at the first call's start
    rtol: float
    evaluations: int  # right-hand-side evaluations over all nodes and segments


def _node_rhs(cn, V, m, RT, mu0p):
    S, R = cn.nu.shape
    lnV = math.log(V)
    passive = cn.passive
    driven = cn.driven
    nu = cn.nu
    Vv = np.array([V])
    mm = m[:, None]

    def rhs(_t, y):
        # Trial stages far from the solution can overflow; the controller rejects them.
        with np.errstate(all="ignore"):
            z = y[:S]
            n = np.exp(z)
            r = nr._evaluate(cn, n[:, None], Vv, mm)
            J = r.net[:, 0]
            mu = RT * (z - lnV) + mu0p
            dH = RT * np.sum(np.where(passive, J * r.affinity[:, 0], 0.0))
            dW = np.sum(np.where(driven, J * (nu.T @ mu), 0.0))
            return np.concatenate([(nu @ J) / n, J, [dH, dW]])

    return rhs


def integrate_node(network, amounts_fmol, volumes_pL, RT_pJ_per_fmol, times_s, multipliers=None,
                   sites=None, rtol=1e-13, atol_log=None, atol_extent_fmol=None,
                   atol_energy_pJ=None, continue_from=None):
    """Integrate the exact kinetics of independent nodes with H and W, at constant multipliers.

    amounts_fmol [S, N] (or [S]), all > 0; volumes_pL [N] or scalar; times_s the record times
    (s), non-decreasing, absolute (from 0, or from continue_from's last time); multipliers [R] or
    [R, N]; sites [R, N]. Tolerances: rtol for every component; atol_log (default rtol) on
    ln n; atol_extent_fmol (default rtol * 1e-3 * max n) on the extents; atol_energy_pJ (default
    rtol * 1e-3 * RT * max n) on H and W. continue_from: a NodeTrajectory whose last record is
    the start (amounts_fmol is then ignored and may be None), for a multiplier change.
    Returns a NodeTrajectory holding only the requested records.
    """
    cn = nr.compile_network(network)
    S, R = cn.nu.shape
    RT = float(RT_pJ_per_fmol)
    if continue_from is not None:
        n0 = continue_from.amounts[-1]
        t0 = float(continue_from.times[-1])
        base = (continue_from.extents[-1], continue_from.heat[-1], continue_from.work[-1])
        origin = continue_from.origin
    else:
        n0 = np.array(amounts_fmol, dtype=float)
        n0 = n0[:, None] if n0.ndim == 1 else n0
        t0 = 0.0
        base = (np.zeros((R, n0.shape[1])), np.zeros(n0.shape[1]), np.zeros(n0.shape[1]))
        origin = n0
    n0, V = nr._state(cn, n0, volumes_pL)
    if not (np.isfinite(n0).all() and (n0 > 0).all()):
        raise ValueError("the start amounts must be finite and > 0")
    N = n0.shape[1]
    m = nr._multipliers(cn, multipliers, sites, N)
    times = np.asarray(times_s, dtype=float)
    if times.ndim != 1 or (np.diff(times) < 0).any() or (times.size and times[0] < t0):
        raise ValueError("record times must be non-decreasing and not before the start")
    mu0p = RT * (cn.mu0_RT - math.log(cn.c0))
    scale = float(np.max(n0))
    atol_log = rtol if atol_log is None else atol_log
    atol_x = rtol * 1e-3 * scale if atol_extent_fmol is None else atol_extent_fmol
    atol_e = rtol * 1e-3 * RT * scale if atol_energy_pJ is None else atol_energy_pJ
    atol = np.concatenate([np.full(S, atol_log), np.full(R, atol_x), [atol_e, atol_e]])
    T = times.size
    amounts = np.empty((T, S, N))
    extents = np.empty((T, R, N))
    heat = np.empty((T, N))
    work = np.empty((T, N))
    evaluations = 0
    for i in range(N):
        rhs = _node_rhs(cn, V[i], m[:, i], RT, mu0p)
        y = np.concatenate([np.log(n0[:, i]), np.zeros(R), [0.0, 0.0]])
        t = t0
        for k, t_next in enumerate(times):
            if t_next > t:
                with np.errstate(all="ignore"):
                    sol = solve_ivp(rhs, (t, t_next), y, method="DOP853", rtol=rtol, atol=atol)
                if not sol.success:
                    raise RuntimeError(f"DOP853 failed at node {i}: {sol.message}")
                evaluations += sol.nfev
                y, t = sol.y[:, -1], t_next
            amounts[k, :, i] = np.exp(y[:S])
            extents[k, :, i] = base[0][:, i] + y[S:S + R]
            heat[k, i] = base[1][i] + y[S + R]
            work[k, i] = base[2][i] + y[S + R + 1]
    delta_G = np.empty((T, N))
    for k in range(T):
        dG = nr.free_energy_change(cn, origin, amounts[k] - origin, V, RT)
        delta_G[k] = dG["delta_G"]
    return NodeTrajectory(
        times=times,
        amounts=amounts,
        extents=extents,
        heat=heat,
        work=work,
        delta_G=delta_G,
        closure=work - heat - delta_G,
        origin=origin,
        rtol=float(rtol),
        evaluations=int(evaluations),
    )


# ------------------------------------------------------------------- passive equilibrium


@dataclass(frozen=True)
class Equilibrium:
    """The passive equilibrium of one node's closed passive network."""

    amounts: np.ndarray  # [S] (fmol)
    affinities: np.ndarray  # [R] residual A_r at the equilibrium (passive routes; 0 elsewhere)
    equilibrium_constants: np.ndarray  # [R] K_r = exp(-sum_s nu_sr mu0_s/RT) (activities)
    log_quotient: np.ndarray  # [R] sum_s nu_sr ln a_s at the equilibrium (= ln K_r)
    delta_G: float  # G(equilibrium) - G(start) (pJ, increment form; <= 0) if RT is given
    iterations: int


def equilibrium_constants(network):
    """K_r = exp(-sum_s nu_sr mu0_s/RT) per reaction [R], in activities a = c/c0."""
    cn = nr.compile_network(network)
    return np.exp(-cn.g)


def passive_equilibrium_ratio(mu0_A_RT, mu0_B_RT):
    """c_B/c_A = exp(-(mu0_B - mu0_A)/RT) for A <=> B at a common c0 (Appendix A)."""
    return math.exp(-(float(mu0_B_RT) - float(mu0_A_RT)))


def passive_equilibrium(network, amounts_fmol, volume_pL, RT_pJ_per_fmol=None, tol=1e-15,
                        max_iterations=200):
    """The equilibrium of the network's passive reactions at one node (driven ones ignored).

    amounts_fmol [S] > 0 is the start; the equilibrium lies in n0 + span(nu_passive).
    Returns an Equilibrium; delta_G is nan unless RT_pJ_per_fmol is given.
    """
    cn = nr.compile_network(network)
    n0 = np.array(amounts_fmol, dtype=float).reshape(-1)
    V = float(volume_pL)
    if not (n0 > 0).all():
        raise ValueError("start amounts must be > 0")
    nu_p = cn.nu[:, cn.passive]
    if nu_p.shape[1] == 0:
        raise ValueError("the network has no passive reaction")
    U, sv, _ = np.linalg.svd(nu_p, full_matrices=False)
    B = U[:, sv > 1e-10 * sv[0]]
    potential = cn.mu0_RT  # mu0/RT

    def phi(n):  # G/RT up to a constant
        return float(np.sum(n * (np.log(n / (V * cn.c0)) + potential - 1.0)))

    eta = np.zeros(B.shape[1])
    n = n0.copy()
    iterations = 0
    for _ in range(max_iterations):
        iterations += 1
        grad = B.T @ (np.log(n / (V * cn.c0)) + potential)
        affinity = -(nu_p.T @ (np.log(n / (V * cn.c0)) + potential))
        if np.max(np.abs(affinity)) <= tol:
            break
        hess = B.T @ (B / n[:, None])
        step = -np.linalg.solve(hess, grad)
        d = B @ step
        alpha = 1.0
        negative = d < 0
        if negative.any():
            alpha = min(1.0, 0.99 * float(np.min(-n[negative] / d[negative])))
        f0 = phi(n)
        while alpha > 1e-30:
            trial = n0 + B @ (eta + alpha * step)
            if (trial > 0).all() and phi(trial) <= f0 + 1e-14 * abs(f0) + 1e-300:
                break
            alpha *= 0.5
        eta = eta + alpha * step
        n_new = n0 + B @ eta
        if np.array_equal(n_new, n):
            break
        n = n_new
    ln_a = np.log(n / (V * cn.c0))
    aff = np.zeros(len(cn.reactions))
    aff[cn.passive] = -(nu_p.T @ (ln_a + potential))
    dG = np.nan
    if RT_pJ_per_fmol is not None:
        dG = float(nr.free_energy_change(cn, n0, n - n0, V, RT_pJ_per_fmol)["delta_G"][0])
    return Equilibrium(
        amounts=n,
        affinities=aff,
        equilibrium_constants=np.exp(-cn.g),
        log_quotient=cn.nu.T @ ln_a,
        delta_G=dG,
        iterations=iterations,
    )


# -------------------------------------------------------------------------- closed forms


def turnover_amount(n0_fmol, production_fmol_per_s, k_per_s, t_s):
    """Open linear kinetics 0 -> A at P, A -> 0 at k: n(t) = n0 e^-kt + (P/k)(1 - e^-kt)."""
    t = np.asarray(t_s, dtype=float)
    k = float(k_per_s)
    return float(n0_fmol) * np.exp(-k * t) - (float(production_fmol_per_s) / k) * np.expm1(-k * t)


def michaelis_menten_substrate(S0_mM, K_M_mM, V_max_mM_per_s, t_s):
    """S(t) from K_M ln(S0/S) + (S0 - S) = V_max t (mM), for an irreversible depletion S -> P.

    With a catalyst read at constant c_E, V_max = k_cat c_E. Accurate to a few ulps times the
    problem's own condition number, about 1 + V_max t/K_M.
    """
    S0, KM, Vm = float(S0_mM), float(K_M_mM), float(V_max_mM_per_s)
    t = np.atleast_1d(np.asarray(t_s, dtype=float))
    out = np.empty(t.shape)
    for idx, ti in np.ndenumerate(t):
        L = math.log(S0 / KM) + (S0 - Vm * ti) / KM  # ln of W's argument
        if L < -30.0:
            w = math.exp(L)
        elif L < 700.0:
            w = float(lambertw(math.exp(L)).real)
        else:
            w = L - math.log(L)
            for _ in range(60):
                w = L - math.log(w)
        y = math.log(KM * w)
        for _ in range(6):
            F = KM * (math.log(S0) - y) + S0 - math.exp(y) - Vm * ti
            y -= F / (-KM - math.exp(y))
        out[idx] = math.exp(y)
    return out.reshape(np.shape(t_s)) if np.ndim(t_s) else float(out[0])
