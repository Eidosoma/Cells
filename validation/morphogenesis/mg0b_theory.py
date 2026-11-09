"""MG0b independent reduced model: single-cell I(V) and the discrete bistable chain.

numpy/scipy only; no Cells code is imported. The equations transcribe the laws
that resolved_pump_tissue@3 declares (src/cells/processes/potassium_channels.py,
sodium_channels.py, kinetic_pump.py, the constant-field membrane flux), applied
to one cell facing a held bath, with gates at their voltage steady states and
the cytoplasm composition held fixed ("fast" I-V). The engine solves the full
system (gate kinetics, ion drift, pumps, capacitor closure, junction
electrodiffusion); this model predicts its stationary voltage structure.

Theory (McNamara et al. 2020 Nat Phys 16:357, PMC8008956; Keener 1987 SIAM J
Appl Math 47:556): a chain of cells coupled by junction conductance G,
C dV_i/dt = -I(V_i) + G (V_{i+1} - 2 V_i + V_{i-1}). With bistable I(V) a wall
between the stable states H and D is stationary in the continuum only at the
Maxwell point (equal areas, integral_H^D I dV = 0); otherwise it moves to
expand the state of lower potential U(V) = integral I dV. Its width scales as
sqrt(G): the continuum wall at the Maxwell point has width
(V_D - V_H) sqrt(G / (2 max U)) cells, where U is measured from V_H. On a
discrete chain the wall is pinned (propagation failure) below a critical
coupling G*(u) that depends on the detuning u from the Maxwell point.
"""

import math
from dataclasses import dataclass, replace

import numpy as np
from scipy import integrate, optimize, sparse

AVOGADRO = 6.02214076e23
ELEMENTARY_CHARGE = 1.602176634e-19
BOLTZMANN = 1.380649e-23
F = AVOGADRO * ELEMENTARY_CHARGE
R = AVOGADRO * BOLTZMANN
VALENCE = dict(Na=1, K=1, M=-1, P=-1)
MOBILE = ("Na", "K", "M")


@dataclass(frozen=True)
class CellParameters:
    """One cell and its held bath. SI units except concentrations (mM = mol/m^3)."""

    temperature_K: float
    area_m2: float
    capacitance_F: float
    volume_m3: float
    permeability_m_s: dict  # membrane base permeabilities Na, K, M
    bath_mM: dict
    fixed_anion_mM: float
    kir_m_s: float
    nav_m_s: float
    nav_availability: float
    control_m_s: float  # Na-leak control population at availability 1
    pump_capacity_mol_s: float
    pump: dict  # km_na_mM, km_k_mM, km_atp_mM, atp_mM, adp_mM, pi_mM, delta_g0_J_per_mol


def bernoulli(x):
    x = np.asarray(x, dtype=float)
    small = np.abs(x) < 1e-4
    safe = np.where(small, 1.0, x)
    series = 1 - x / 2 + x**2 / 12 - x**4 / 720
    return np.where(small, series, safe / np.expm1(safe))


def logistic(x):
    return 1.0 / (1.0 + np.exp(-x))


def kir_opening(v):
    """Kir2.1 m*h^2 at the gates' steady state (m_inf, h_inf)."""
    m = logistic(-(v + 0.09648) / 0.02326)
    h = logistic((v + 0.16828) / 0.04413)
    return m * h * h


def nav_opening(v):
    """NaV1.2 m^3*h at the gates' steady state."""
    shifted = (v + 0.025) / 0.009
    activation = 0.182 * 9 * bernoulli(-shifted)
    deactivation = 0.124 * 9 * bernoulli(shifted)
    m = activation / (activation + deactivation)
    h = 1 / (1 + np.exp((v + 0.055) / 0.0062))
    return m**3 * h


def inward_flux_mol_s(p, species, c_in, v, permeability):
    """Constant-field (GHK) inward flux of one species."""
    x = VALENCE[species] * F * v / (R * p.temperature_K)
    return p.area_m2 * permeability * (p.bath_mM[species] * bernoulli(x) - c_in * bernoulli(-x))


def pump_cycles_mol_s(p, c, v):
    """3 Na out / 2 K in ATPase with maintained pools (forward cycles positive)."""
    q = p.pump
    rt = R * p.temperature_K
    drive = q["delta_g0_J_per_mol"] + rt * (
        math.log(q["adp_mM"]) + math.log(q["pi_mM"]) - math.log(q["atp_mM"]) - math.log(1000.0)
    )
    mu_na = rt * np.log(c["Na"] / p.bath_mM["Na"]) + F * v
    mu_k = rt * np.log(c["K"] / p.bath_mM["K"]) + F * v
    a = (drive - 3 * mu_na + 2 * mu_k) / rt
    saturation = (
        1
        / (1 + (q["km_na_mM"] / c["Na"]) ** 3)
        / (1 + (q["km_k_mM"] / p.bath_mM["K"]) ** 2)
        / (1 + q["km_atp_mM"] / q["atp_mM"])
    )
    departure = np.where(a >= 0, np.exp(a) * np.expm1(-a), -np.expm1(a))
    return p.pump_capacity_mol_s * saturation * departure


def fluxes(p, c, v, u):
    """Net inward fluxes (mol/s) of Na, K, M at control availability u."""
    na_perm = p.permeability_m_s["Na"] + u * p.control_m_s
    na_perm = na_perm + p.nav_m_s * p.nav_availability * nav_opening(v)
    k_perm = p.permeability_m_s["K"] + p.kir_m_s * kir_opening(v)
    cycles = pump_cycles_mol_s(p, c, v)
    return dict(
        Na=inward_flux_mol_s(p, "Na", c["Na"], v, na_perm) - 3 * cycles,
        K=inward_flux_mol_s(p, "K", c["K"], v, k_perm) + 2 * cycles,
        M=inward_flux_mol_s(p, "M", c["M"], v, p.permeability_m_s["M"]),
    )


def current_A(p, c, v, u):
    """Outward membrane current I(V) at fixed composition c (positive = outward)."""
    j = fluxes(p, c, v, u)
    return -F * sum(VALENCE[s] * j[s] for s in MOBILE)


GRID_V = np.linspace(-0.118, 0.058, 17601)


def fast_states(p, c, u, grid=GRID_V):
    """Zeros of I(V) on the voltage domain, sorted; stable ones have dI/dV > 0."""
    current = current_A(p, c, grid, u)
    s = np.sign(current)
    roots = []
    for i in np.flatnonzero(s[:-1] * s[1:] < 0):
        roots.append(
            optimize.brentq(
                lambda v: float(current_A(p, c, v, u)), grid[i], grid[i + 1], xtol=1e-15
            )
        )
    return roots


def potential(p, c, u, v_from, v_to, n=4001):
    """U(v_to) - U(v_from) with U = integral of I dV (A V), Gauss-Legendre."""
    x, w = np.polynomial.legendre.leggauss(64)
    edges = np.linspace(v_from, v_to, max(2, n // 64))
    total = 0.0
    for a, b in zip(edges[:-1], edges[1:], strict=True):
        vv = 0.5 * (b - a) * x + 0.5 * (a + b)
        total += 0.5 * (b - a) * float(np.dot(w, current_A(p, c, vv, u)))
    return total


def slope_conductance_S(p, c, v, u, h=1e-7):
    return float((current_A(p, c, v + h, u) - current_A(p, c, v - h, u)) / (2 * h))


def slow_states(p, u, grid=None):
    """Full ionic steady states (Na, K, M balanced; near-electroneutral, fixed volume).

    For each V, Na and K follow from their (monotone) balances and M from its
    Nernst equilibrium; the electroneutral residual Na + K - M - P - C V/(F vol)
    is then solved for V. Returns [(V, {Na, K, M}), ...] sorted by V.
    """
    grid = np.linspace(-0.110, 0.0, 221) if grid is None else grid

    def composition(v):
        m = p.bath_mM["M"] * math.exp(F * v / (R * p.temperature_K))
        c = dict(Na=12.0, K=140.0, M=m)
        for _ in range(40):
            na = optimize.brentq(
                lambda x, c=c: fluxes(p, {**c, "Na": x}, v, u)["Na"], 1e-6, 5e3, xtol=1e-14
            )
            k = optimize.brentq(
                lambda x, c=c, na=na: fluxes(p, {**c, "Na": na, "K": x}, v, u)["K"],
                1e-6,
                5e4,
                xtol=1e-14,
            )
            done = abs(na - c["Na"]) < 1e-13 * na and abs(k - c["K"]) < 1e-13 * k
            c = dict(Na=na, K=k, M=m)
            if done:
                break
        return c

    def residual(v):
        c = composition(v)
        return (
            c["Na"] + c["K"] - c["M"] - p.fixed_anion_mM - p.capacitance_F * v / (F * p.volume_m3)
        )

    values = np.array([residual(v) for v in grid])
    out = []
    for i in np.flatnonzero(np.sign(values[:-1]) * np.sign(values[1:]) < 0):
        v = optimize.brentq(residual, grid[i], grid[i + 1], xtol=1e-15)
        out.append((v, composition(v)))
    return out


def junction_conductance_S(p, c, area_m2, permeability_m_s, open_fraction=1.0):
    """Ohmic conductance of a constant-field junction between equal compositions."""
    return (
        F**2
        / (R * p.temperature_K)
        * area_m2
        * open_fraction
        * sum(VALENCE[s] ** 2 * permeability_m_s[s] * c[s] for s in MOBILE)
    )


def maxwell_control(p, u_lo, u_hi, n=15):
    """Self-consistent Maxwell point: composition = slow H state at the same u.

    Scans [u_lo, u_hi] for a sign change of the H-to-D potential difference
    among bistable points, then refines it with brentq. Returns (u_M,
    composition, fast states). At u_M the fast I-V of a cell in its own slow H
    composition has equal areas between H and D.
    """

    def integral(u):
        v_h, c = slow_states(p, u)[0]
        fast = fast_states(p, c, u)
        return None if len(fast) < 3 else potential(p, c, u, fast[0], fast[2])

    grid = np.linspace(u_lo, u_hi, n)
    values = [integral(u) for u in grid]
    for a, b, fa, fb in zip(grid[:-1], grid[1:], values[:-1], values[1:], strict=True):
        if fa is not None and fb is not None and fa * fb <= 0:
            u_m = optimize.brentq(integral, a, b, xtol=1e-12)
            break
    else:
        raise ValueError("No Maxwell point among bistable controls in the bracket")
    v_h, c = slow_states(p, u_m)[0]
    return u_m, c, fast_states(p, c, u_m)


def bistable_range(p, c, u_lo=0.0, u_hi=1.0, n=401):
    """Control interval with three fast states at fixed composition c (grid + bisection)."""
    us = np.linspace(u_lo, u_hi, n)
    three = np.array([len(fast_states(p, c, u)) >= 3 for u in us])
    idx = np.flatnonzero(three)
    if not len(idx):
        return None

    def edge(a, b, inside_at_a):
        for _ in range(50):
            mid = 0.5 * (a + b)
            if (len(fast_states(p, c, mid)) >= 3) == inside_at_a:
                a = mid
            else:
                b = mid
        return 0.5 * (a + b)

    lo = us[idx[0]] if idx[0] == 0 else edge(us[idx[0]], us[idx[0] - 1], True)
    hi = us[idx[-1]] if idx[-1] == n - 1 else edge(us[idx[-1]], us[idx[-1] + 1], True)
    return lo, hi


# ---------------------------------------------------------------- reduced chain


@dataclass(frozen=True)
class Chain:
    """coupling_S: one conductance for every junction, or an array of n - 1."""

    cell: CellParameters
    composition: dict
    n: int
    coupling_S: object


def _couplings(chain):
    return np.broadcast_to(np.asarray(chain.coupling_S, dtype=float), (chain.n - 1,))


def chain_rhs(chain, v, u):
    """dV/dt for the chain (no-flux ends); u is a scalar or per-cell array."""
    g = _couplings(chain)
    flow = g * (v[1:] - v[:-1])  # Junction current into cell i from i + 1.
    lap = np.zeros_like(v)
    lap[:-1] += flow
    lap[1:] -= flow
    return (-current_A(chain.cell, chain.composition, v, u) + lap) / chain.cell.capacitance_F


def chain_jacobian(chain, v, u, h=1e-7):
    c = chain.composition
    di = (current_A(chain.cell, c, v + h, u) - current_A(chain.cell, c, v - h, u)) / (2 * h)
    g = _couplings(chain)
    degree = np.zeros(chain.n)
    degree[:-1] += g
    degree[1:] += g
    return sparse.diags([g, -di - degree, g], [-1, 0, 1]).tocsc() / chain.cell.capacitance_F


def integrate_chain(chain, v0, u_of_t, t_end, t_eval, breakpoints=()):
    """Reduced-chain trajectory (BDF, exact tridiagonal Jacobian).

    u_of_t(t) and chain_of_t are piecewise constant; integration restarts at
    every breakpoint so no step straddles a control change. u_of_t may return
    (u, chain) to change couplings as well.
    """

    def resolve(t):
        value = u_of_t(t)
        return value if isinstance(value, tuple) else (value, chain)

    edges = sorted({0.0, *(b for b in breakpoints if 0 < b < t_end), t_end})
    t_eval = np.asarray(t_eval, dtype=float)
    out = np.empty((len(t_eval), len(v0)))
    v = np.asarray(v0, dtype=float)
    for a, b in zip(edges[:-1], edges[1:], strict=True):
        u, current = resolve(0.5 * (a + b))
        wanted = t_eval[(t_eval > a) & (t_eval <= b)]
        points = np.unique(np.append(wanted, b))
        solution = integrate.solve_ivp(
            lambda t, y, u=u, current=current: chain_rhs(current, y, u),
            (a, b),
            v,
            method="BDF",
            jac=lambda t, y, u=u, current=current: chain_jacobian(current, y, u),
            t_eval=points,
            rtol=1e-9,
            atol=1e-12,
            max_step=0.05,
        )
        if not solution.success:
            raise RuntimeError(solution.message)
        for k, t in enumerate(points):
            out[t_eval == t] = solution.y[:, k]
        v = solution.y[:, -1]
    out[t_eval == 0.0] = np.asarray(v0, dtype=float)
    return out


def stationary_front(chain, u, v_h, v_d, centre, width):
    """Newton solution of the stationary wall near a tanh guess (None if it fails)."""
    x = np.arange(chain.n)
    guess = v_h + (v_d - v_h) * 0.5 * (1 + np.tanh((x - centre) / max(width, 0.3)))
    scale = 0.1  # s: residuals in volts, near the membrane time constant.
    solution = optimize.root(
        lambda v: chain_rhs(chain, v, u) * scale,
        guess,
        jac=lambda v: chain_jacobian(chain, v, u).toarray() * scale,
        method="hybr",
        tol=1e-13,
    )
    if not solution.success or np.max(np.abs(chain_rhs(chain, solution.x, u))) > 1e-9:
        return None
    return solution.x


def wall_width_cells(v, v_h, v_d):
    """(V_D - V_H) / max nearest-neighbour step: the maximum-slope width in cells."""
    return float(abs(v_d - v_h) / np.max(np.abs(np.diff(v))))


def front_position(v, v_h, v_d):
    """Number of D-like cells: sum of (V - V_H)/(V_D - V_H), a continuous wall position."""
    return float(np.sum((np.asarray(v) - v_h) / (v_d - v_h)))


def continuum_width_cells(p, c, u, v_h, v_d, coupling_S, points=200001):
    """Maxwell-point continuum wall width (V_D - V_H) sqrt(G / (2 max U)) in cells.

    U(V) = integral from V_H of I dV, by cumulative Simpson on a fine grid.
    """
    vs = np.linspace(v_h, v_d, points)
    u_values = integrate.cumulative_simpson(current_A(p, c, vs, u), x=vs, initial=0.0)
    return abs(v_d - v_h) * math.sqrt(coupling_S / (2 * np.max(u_values)))


def pinned(chain, u, v_h, v_d, *, settle=2.0, test=20.0, tolerance=0.5):
    """Dynamic pinning test: does a settled wall move less than `tolerance` cells?"""
    x = np.arange(chain.n)
    v0 = np.where(x < chain.n // 2, v_h, v_d)
    traj = integrate_chain(chain, v0, lambda t: u, settle + test, [settle, settle + test])
    shift = front_position(traj[1], v_h, v_d) - front_position(traj[0], v_h, v_d)
    return abs(shift) < tolerance, shift


def critical_coupling(chain, u, v_h, v_d, g_lo, g_hi, *, rel=0.01, **kw):
    """Bisection (log scale) for the pinning threshold G*: pinned below, moving above."""
    lo_pinned = pinned(replace(chain, coupling_S=g_lo), u, v_h, v_d, **kw)[0]
    hi_pinned = pinned(replace(chain, coupling_S=g_hi), u, v_h, v_d, **kw)[0]
    if not lo_pinned or hi_pinned:
        raise ValueError("Bracket does not straddle the pinning threshold")
    while g_hi / g_lo > 1 + rel:
        mid = math.sqrt(g_lo * g_hi)
        if pinned(replace(chain, coupling_S=mid), u, v_h, v_d, **kw)[0]:
            g_lo = mid
        else:
            g_hi = mid
    return math.sqrt(g_lo * g_hi)
