"""R-ode (Appendix A.2 and A.3): the declared binding and internalisation network, integrated.

**The law (A.2).** For population k facing node i(k), with receiving cell r(k):

    J_k = m_b,k (k_on,k c_i(k) R_k - k_off,k B_k),     I_k = m_i,k k_int,k B_k,
    dB_k/dt = J_k - I_k,   dR_k/dt = -J_k + I_k,
    dn_i/dt = -sum_{k: i(k) = i} J_k + sum_{k: r(k) = i} I_k,

with c = n/V (mM), R + B = S_k = alpha nu N / N_f (fmol, N_f = 602,214,076 per fmol) and the
multipliers m piecewise constant over declared epochs.

**Heat and work (A.3),** carried as states. dH/dt = RT sum_k J_k A_k with
A_k = ln(c R_k/(K_d,k B_k)) >= 0, and dW/dt = sum_k I_k (mu_r + mu_R - mu_B) =
RT sum_k I_k [ln(c_r/K_d,k) + ln(R_k/B_k)]. A_k diverges where B or R is zero, so the heat is
integrated in a regular form. Using dB/dt = J - I and dR/dt = I - J with S fixed,

    J A = J ln(c/K_d) + I ln(R/B) - d/dt [R ln(R/S) + B ln(B/S)],

so H = RT [Y - (Phi(t) - Phi(0))], with dY/dt = sum_k J_k ln(c_k/K_d,k) + I_k ln(R_k/B_k) (every
term finite: I ln(R/B) = m k_int B ln(R/B) -> 0 as B -> 0) and Phi = sum_k xlogy(R, R/S) +
xlogy(B, B/S). The ledger d(sum G_node) + d(sum G_site) + H - W = 0 then checks the integration
against state functions (``energy``).

**Methods.** The primary is SciPy's Radau at rtol 1e-12, the second DOP853 at rtol 1e-13, epoch
by epoch; each state's atol is rtol x 1e-6 x its own scale. The floor is their difference plus
half an ulp.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

import numpy as np
from scipy.integrate import solve_ivp
from scipy.special import xlogy

from . import energy
from .exact import SITES_PER_FMOL, exact

RTOL_PRIMARY = 1e-12
RTOL_SECOND = 1e-13


def sites_fmol(copies, sites_per_copy, accessible_fraction) -> Fraction:
    """S = alpha nu N / N_f (fmol), exact."""
    return exact(accessible_fraction) * exact(sites_per_copy) * exact(copies) / SITES_PER_FMOL


@dataclass
class Population:
    node: str
    S: float                    # accessible sites, fmol
    k_on: float                 # 1/(mM s)
    k_off: float                # 1/s
    k_int: float = 0.0          # 1/s
    receiver: str | None = None
    B0: float = 0.0             # fmol

    @property
    def K_d(self) -> float:
        return self.k_off / self.k_on


@dataclass
class Network:
    volumes: dict               # node -> pL
    n0: dict                    # node -> fmol (ligand), every value > 0 (D150's trace)
    populations: list
    RT: float                   # pJ/fmol
    epochs: list = field(default_factory=lambda: [(0.0, None)])
    """[(t_start, {population index: (m_b, m_i)} or None for all ones)], increasing from 0."""

    def __post_init__(self):
        for p in self.populations:
            if p.k_on <= 0 or p.k_off <= 0:
                raise ValueError("k_on and k_off must be positive (irreversible binding refused)")
            if p.k_int < 0 or not 0 <= p.B0 <= p.S or p.S <= 0:
                raise ValueError("k_int >= 0 and 0 <= B0 <= S > 0 are required")
            if p.node not in self.volumes or (p.receiver and p.receiver not in self.volumes):
                raise ValueError("a population names an unknown node")
        if any(v <= 0 for v in self.n0.values()):
            raise ValueError("every ligand row must start positive (D150's trace)")


def _multipliers(net: Network, e: int) -> np.ndarray:
    m = np.ones((len(net.populations), 2))
    spec = net.epochs[e][1]
    if spec:
        for k, (mb, mi) in spec.items():
            m[int(k)] = (mb, mi)
    return m


def _rhs_factory(net: Network, nodes: list, m: np.ndarray):
    idx = {n: i for i, n in enumerate(nodes)}
    V = np.array([float(net.volumes[n]) for n in nodes])
    face = np.array([idx[p.node] for p in net.populations])
    recv = np.array([idx[p.receiver] if p.receiver else -1 for p in net.populations])
    S = np.array([p.S for p in net.populations])
    kon = np.array([p.k_on for p in net.populations])
    koff = np.array([p.k_off for p in net.populations])
    kint = np.array([p.k_int for p in net.populations])
    Kd = koff / kon
    N, K = len(nodes), len(net.populations)

    def rhs(_t, y):
        n = y[:N]
        B = np.clip(y[N:N + K], 0.0, S)
        R = S - B
        c = n / V
        J = m[:, 0] * (kon * c[face] * R - koff * B)
        Iflux = m[:, 1] * kint * B
        dn = np.zeros(N)
        np.add.at(dn, face, -J)
        has = recv >= 0
        np.add.at(dn, recv[has], Iflux[has])
        with np.errstate(divide="ignore", invalid="ignore"):
            lnRB = np.where(B > 0, np.log(np.where(R > 0, R, 1.0) / np.where(B > 0, B, 1.0)), 0.0)
        IlnRB = np.where(B > 0, Iflux * lnRB, 0.0)
        dY = np.sum(J * np.log(c[face] / Kd) + IlnRB)
        cr = np.where(has, c[np.where(has, recv, 0)], 1.0)
        dW = net.RT * np.sum(np.where(has, Iflux * np.log(cr / Kd), 0.0) + IlnRB)
        return np.concatenate([dn, J - Iflux, Iflux, [dY, dW]])
    return rhs, N, K, S


def _integrate(net: Network, times, method: str, rtol: float) -> dict:
    nodes = sorted(net.volumes)
    times = np.asarray(times, dtype=np.float64)
    texact = [exact(t) for t in times]
    starts = [exact(t) for t, _ in net.epochs] + [max(texact)]
    y = np.concatenate([[float(net.n0[n]) for n in nodes], [p.B0 for p in net.populations],
                        np.zeros(len(net.populations)), [0.0, 0.0]])
    scale = np.concatenate([[max(float(net.n0[n]), 1e-30) for n in nodes],
                            [p.S for p in net.populations], [p.S for p in net.populations],
                            [max(p.S for p in net.populations)] * 2])
    out = np.full((times.size, y.size), np.nan)
    for e in range(len(net.epochs)):
        m = _multipliers(net, e)
        rhs, N, K, S = _rhs_factory(net, nodes, m)
        t0, t1 = starts[e], starts[e + 1]
        last = e == len(net.epochs) - 1
        sel = [k for k, t in enumerate(texact) if t0 <= t and (t < t1 or (last and t == t1))]
        taus = [float(texact[k] - t0) for k in sel]
        span = float(t1 - t0)
        if span > 0:
            sol = solve_ivp(rhs, (0.0, span), y, method=method, rtol=rtol,
                            atol=rtol * 1e-6 * scale, t_eval=sorted(set(taus + [span])))
            if not sol.success:
                raise RuntimeError(f"{method} failed in epoch {e}: {sol.message}")
            at = {float(t): sol.y[:, i] for i, t in enumerate(sol.t)}
            for k, tau in zip(sel, taus, strict=True):
                out[k] = at[tau]
            y = at[span]
        else:
            for k in sel:
                out[k] = y
    N, K = len(nodes), len(net.populations)
    S = np.array([p.S for p in net.populations])
    B = np.clip(out[:, N:N + K], 0.0, S)
    R = S - B
    phi = np.sum(xlogy(R, R / S) + xlogy(B, B / S), axis=1)
    H = net.RT * (out[:, N + 2 * K] - (phi - phi[0]))
    return {"nodes": nodes, "n_fmol": out[:, :N], "B_fmol": B, "R_fmol": R,
            "internalised_fmol": out[:, N + K:N + 2 * K], "heat_pJ": H,
            "work_pJ": out[:, N + 2 * K + 1]}


def integrate(net: Network, times) -> dict:
    """R-ode at the record times: amounts, pools, internalised amounts, heat and work, with the
    floor (|Radau - DOP853| + half an ulp) of each, and the ledger residual at each record."""
    prim = _integrate(net, times, "Radau", RTOL_PRIMARY)
    sec = _integrate(net, times, "DOP853", RTOL_SECOND)
    out = dict(prim)
    for key in ("n_fmol", "B_fmol", "R_fmol", "internalised_fmol", "heat_pJ", "work_pJ"):
        a, b = prim[key], sec[key]
        out[f"{key}_floor"] = np.abs(a - b) + 0.5 * np.spacing(np.abs(a))
    out["ledger_residual_pJ"] = ledger(net, out)
    return out


def ledger(net: Network, run: dict) -> np.ndarray:
    """d(sum G_node) + d(sum G_site) + H - W at each record, from the run's states."""
    nodes = run["nodes"]
    res = []
    for k in range(run["n_fmol"].shape[0]):
        Gn = sum(energy.node_free_energy(run["n_fmol"][k, i], net.volumes[n], net.RT)
                 for i, n in enumerate(nodes))
        Gs = sum(energy.site_free_energy(run["B_fmol"][k, j], p.S, p.K_d, net.RT)
                 for j, p in enumerate(net.populations))
        res.append((Gn, Gs))
    G0n, G0s = res[0]
    return np.array([(Gn - G0n) + (Gs - G0s) + run["heat_pJ"][k] - run["work_pJ"][k]
                     for k, (Gn, Gs) in enumerate(res)])
