"""Analytic limits of the excitable-tissue reference (Track E): the linear passive cable of a
discrete chain and the strong-coupling (isopotential) limit.

Written from the equations appendix (docs/EXCITABLE_TISSUE_EQUATIONS.md, §2-§6) and cable
theory, without engine code; numpy and scipy only.

* **The discrete passive cable.** With every gated population unavailable, a uniform chain
  linearised about a uniform rest V_r obeys
      C dv_i/dt = -i_r - g_m v_i + g_j (v_(i+1) - 2 v_i + v_(i-1)) - s_i(t) (i_s + g_s v_i),
  with sealed ends and v = V - V_r. Here i_r is the passive membrane's current at V_r (nonzero
  when V_r is the rest with the channels available: the passive cell then drifts) and g_m its
  slope conductance there (leaks and pump, composition frozen). g_j is the junction's slope
  conductance at zero transjunctional voltage and equal compositions,
  g_j = (F^2/RT) a_j sum_s z_s^2 p_s c_s (the derivative of the constant-field flux at x = 0),
  and a stimulated cell's routes (s_i = 1 while on) are linearised about V_r too: their
  current i_s at V_r and slope conductance g_s.
  The modes are the cosines of the Neumann chain, cos(k pi (i + 1/2)/N), with eigenvalues
  g_m + 2 g_j (1 - cos(k pi/N)); a steady injection decays as r^i with r + 1/r = 2 + g_m/g_j
  (the discrete space constant -1/ln r cells). Cable theory: Plonsey & Barr (2007); Keener &
  Sneyd (2009), vol. II.
* **The strong-coupling limit.** As s_c grows, the junctions equalise V across the chain and a
  uniform chain of N cells, n_s of them stimulated, tends to one cell whose stimulus permeability
  is P_stim n_s / N (the stimulus averaged over the equal areas): ``lumped_cell``.
"""

import math
from dataclasses import replace

import numpy as np
from scipy.linalg import expm

from validation.excitable import excitable_reference as er


def passive_linearisation(tissue, V_rest, *, p_stim=0.0, dV=1e-7):
    """The linear cable's coefficients at V_rest, as a dict:
    * i_rest_A, g_m_S: the outward current and slope conductance of one cell's membrane with
      every gated population unavailable (leaks and pump, the initial composition);
    * g_j_S: the junction's slope conductance at zero transjunctional voltage and equal
      compositions (the exact derivative of the flux at x = 0);
    * i_stim_A, g_s_S, E_s_V: the stimulus routes' outward current and slope conductance at
      V_rest, and their zero-current potential (for reference), at p_stim (m/s).
    Central differences in V of width dV for the slopes."""
    passive = replace(tissue, n=1, s_c=0.0, availability_NaV=0.0, availability_Kir=0.0,
                      availability_Kv=0.0, stimuli=())
    F, rt = tissue.constants.faraday_C_per_mol, tissue.constants.rt
    c = np.asarray(tissue.initial_mM, dtype=float)

    def membrane_current(v):
        """The passive cell's outward current (A) at v, its composition the initial one."""
        m = er.Model(passive, er.Start(V=v, gates_at_V=V_rest))
        return -m.dVdt(m.y0, np.zeros(1))[0] * m.capacitance[0]

    i_rest = membrane_current(V_rest)
    g_m = (membrane_current(V_rest + dV) - membrane_current(V_rest - dV)) / (2 * dV)
    if p_stim > 0.0:
        area = tissue.area_m2
        bath = np.asarray(tissue.bath_mM, dtype=float)

        def stim_current(v):
            x = er.Z * F * v / rt
            pa = np.array([p_stim, p_stim, 0.0, 0.0]) * area
            return F * float(np.sum(er.Z * er.ghk_flux(pa, x, c, bath)))

        g_s = (stim_current(V_rest + dV) - stim_current(V_rest - dV)) / (2 * dV)
        from scipy.optimize import brentq

        E_s = brentq(stim_current, -0.1, 0.1, xtol=1e-15)
        i_stim = stim_current(V_rest)
    else:
        g_s, E_s, i_stim = 0.0, 0.0, 0.0
    pj = (tissue.per_junction(tissue.s_c)[0] if tissue.n > 1 else float(tissue.s_c)) \
        * np.asarray(tissue.junction_D_m2_s) * tissue.junction_scale * tissue.junction_area_m2
    g_j = F * F / rt * float(np.sum(er.Z**2 * pj * c))
    return dict(i_rest_A=i_rest, g_m_S=g_m, g_j_S=g_j, i_stim_A=i_stim, g_s_S=g_s, E_s_V=E_s)


def space_constant_cells(g_m, g_j):
    """-1/ln r with r + 1/r = 2 + g_m/g_j, r < 1: the decay per cell of a steady injection."""
    alpha = g_m / g_j
    r = 1.0 + alpha / 2.0 - math.sqrt(alpha + alpha * alpha / 4.0)
    return -1.0 / math.log(r), r


def cable_matrix(n, g_m, g_j):
    """The conductance matrix G (S) of the sealed discrete cable: -G v is the current."""
    G = np.zeros((n, n))
    for i in range(n):
        G[i, i] = g_m
        for j in (i - 1, i + 1):
            if 0 <= j < n:
                G[i, i] += g_j
                G[i, j] -= g_j
    return G


def neumann_modes(n, g_m, g_j):
    """Eigenvalues g_m + 2 g_j (1 - cos(k pi/n)) and orthonormal eigenvectors
    cos(k pi (i + 1/2)/n) of the sealed cable matrix (columns), k = 0..n-1."""
    k = np.arange(n)
    i = np.arange(n)[:, None]
    vec = np.cos(k[None, :] * math.pi * (i + 0.5) / n)
    vec /= np.linalg.norm(vec, axis=0)
    return g_m + 2.0 * g_j * (1.0 - np.cos(k * math.pi / n)), vec


def linear_cable_response(n, C, lin, V_rest, stimulated, windows, times):
    """v(t) = V - V_r of the linear cable at the given times, from v(0) = 0: exact piecewise
    matrix exponentials of C dv/dt = -i_r - (G + G_s(t)) v - i_s 1_stim(t), with the
    coefficients ``lin`` of passive_linearisation (V_rest is where they were taken)."""
    g_m, g_j, g_s = lin["g_m_S"], lin["g_j_S"], lin["g_s_S"]
    i_s, i_r = lin["i_stim_A"], lin["i_rest_A"]
    del V_rest
    G = cable_matrix(n, g_m, g_j)
    S = np.zeros(n)
    S[list(stimulated)] = 1.0
    edges = sorted({0.0, *(x for w in windows for x in w), *times})
    out, v, t_prev = {}, np.zeros(n), 0.0
    for t in edges[1:]:
        mid = 0.5 * (t_prev + t)
        on = any(a <= mid < b for a, b in windows)
        A = -(G + np.diag(S * g_s if on else np.zeros(n))) / C
        b = (-(S * i_s if on else np.zeros(n)) - i_r) / C
        dt = t - t_prev
        # Augmented exponential for v' = A v + b, exact over the interval.
        M = np.zeros((n + 1, n + 1))
        M[:n, :n], M[:n, n] = A * dt, b * dt
        E = expm(M)
        v = E[:n, :n] @ v + E[:n, n]
        t_prev = t
        if t in times:
            out[t] = v.copy()
    return out


def lumped_cell(tissue):
    """The strong-coupling limit of a uniform chain: one cell with the stimulus permeability of
    each stimulus averaged over the chain (P n_s/N). Refuses a chain with per-cell differences."""
    for name in ("c_m_F_per_m2", "P_NaV_m_s", "P_Kir_m_s", "P_Kv_m_s", "availability_NaV",
                 "availability_Kir", "availability_Kv"):
        values = tissue.per_cell(getattr(tissue, name))
        if not np.all(values == values[0]):
            raise ValueError(f"lumped_cell takes a uniform chain ({name} varies)")
        tissue = replace(tissue, **{name: float(values[0])})
    stimuli = tuple(er.Stimulus((0,), s.permeability_m_s * len(s.cells) / tissue.n, s.windows)
                    for s in tissue.stimuli)
    return replace(tissue, n=1, s_c=0.0, stimuli=stimuli)
