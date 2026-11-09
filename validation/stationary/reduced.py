"""Independent reduced references for the stationary-analysis targets.

numpy/scipy only, built on validation/morphogenesis/mg0b_theory.py (which
imports no Cells code): one cell facing a held bath with gates at their voltage
steady state, fixed volume, and the cell voltage slaved to its charge,
V = F vol (Na + K - M - P) / C, as in the heredity pre-screen. Provides

* slow_rhs: dc/dt (mM/s) of the three mobile species;
* slow_jacobian: its Jacobian by Richardson-extrapolated central differences
  (steps h and h/2), with the difference of the two levels as error estimate;
* fold: an edge of the fixed-composition bistable window, I(V) = 0 = dI/dV,
  solved directly (the theory's bistable_range brackets the edge on a 0.01 mV
  root grid, which misses root pairs closer than one grid cell).

The engine's linearisation also carries the gates; its adiabatic (quasi-steady
gate) reduction, the Schur complement adiabatic_ions(), is what the reduced
Jacobian approximates without gate lag.
"""

import math

import numpy as np
from scipy import optimize

MOBILE = ("Na", "K", "M")


def theory():
    from validation.morphogenesis import mg0b_theory

    return mg0b_theory


def voltage(p, c3):
    t = theory()
    na, k, m = c3
    return t.F * p.volume_m3 * (na + k - m - p.fixed_anion_mM) / p.capacitance_F


def slow_rhs(p, c3, u=0.0):
    """mM/s of Na, K, M (inward positive) at composition c3 = (Na, K, M) in mM."""
    t = theory()
    c = dict(zip(MOBILE, c3, strict=True))
    j = t.fluxes(p, c, voltage(p, c3), u)
    return np.array([j[s] for s in MOBILE]) / p.volume_m3


def _rates_at(p, c3, v, u):
    """dc/dt (mM/s) at composition c3 and an explicitly given voltage v."""
    t = theory()
    j = t.fluxes(p, dict(zip(MOBILE, c3, strict=True)), v, u)
    return np.array([j[s] for s in MOBILE]) / p.volume_m3


def slow_jacobian(p, c3, u=0.0, h=1e-6, h_v=1e-6):
    """(Jacobian, elementwise error estimate) in 1/s at c3 (mM).

    J = d/dc at fixed V + d/dV (x) dV/dc, dV/dc = F vol z / C exactly. Splitting
    keeps the difference quotients free of the voltage's cancellation (V is a
    difference of ~100 mM terms giving ~0.02 mM, whose rounding a quotient in
    c would amplify by 1/h). Each quotient is central, at steps (h, h/2) in mM
    and (h_v, h_v/2) in V, Richardson-extrapolated; the error estimate is
    |fine - coarse| (3/4 of the coarse O(h^2) error, a conservative bound on
    the O(h^4) extrapolated one) plus the quotients' rounding, 8 eps max|f| / h.
    """
    t = theory()
    c3 = np.asarray(c3, dtype=float)
    v = voltage(p, c3)
    f0 = _rates_at(p, c3, v, u)

    def composition(step):
        jac = np.zeros((3, 3))
        for i in range(3):
            up, down = c3.copy(), c3.copy()
            up[i] += step
            down[i] -= step
            jac[:, i] = (_rates_at(p, up, v, u) - _rates_at(p, down, v, u)) / (2 * step)
        return jac

    def potential(step):
        return (_rates_at(p, c3, v + step, u) - _rates_at(p, c3, v - step, u)) / (2 * step)

    c_coarse, c_fine = composition(h), composition(h / 2)
    v_coarse, v_fine = potential(h_v), potential(h_v / 2)
    dv_dc = t.F * p.volume_m3 / p.capacitance_F * np.array([t.VALENCE[s] for s in MOBILE])
    jac_c, jac_v = (4 * c_fine - c_coarse) / 3, (4 * v_fine - v_coarse) / 3
    eps = np.finfo(float).eps
    rounding = 8 * eps * np.max(np.abs(f0))  # two evaluations per quotient
    err_c = np.abs(c_fine - c_coarse) + rounding / h
    err_v = np.abs(v_fine - v_coarse) + rounding / h_v
    jac = jac_c + np.outer(jac_v, dv_dc)
    error = err_c + np.outer(err_v, np.abs(dv_dc)) + 4 * eps * np.abs(jac)
    return jac, error


def correction(p, c3, u=0.0):
    """Newton correction (mM) at a reference slow state and the voltage change (V) it implies."""
    c3 = np.asarray(c3, dtype=float)
    jac, _ = slow_jacobian(p, c3, u)
    delta = -np.linalg.solve(jac, slow_rhs(p, c3, u))
    return delta, voltage(p, c3 + delta) - voltage(p, c3)


def eigen_bounds(jac, error):
    """Eigenvalues and first-order bounds kappa_i ||dJ||_2 (Bauer-Fike per eigenvalue)."""
    import scipy.linalg

    values, left, right = scipy.linalg.eig(jac, left=True, right=True)
    left = left / np.linalg.norm(left, axis=0)
    right = right / np.linalg.norm(right, axis=0)
    kappa = 1 / np.abs(np.sum(np.conj(left) * right, axis=0))
    bound = kappa * np.linalg.norm(error, 2)
    order = np.argsort(-values.real)
    return values[order], bound[order]


def adiabatic_ions(jac, ions, gates):
    """Quasi-steady-gate reduction A - B D^-1 C of a Jacobian on (ions, gates) indices."""
    a = jac[np.ix_(ions, ions)]
    if not len(gates):
        return a
    b, c, d = jac[np.ix_(ions, gates)], jac[np.ix_(gates, ions)], jac[np.ix_(gates, gates)]
    return a - b @ np.linalg.solve(d, c)


def fold(p, c, u_bracket, v_bracket, h=1e-6):
    """(u, V) of a window edge: I(V) has a double root. Brackets must enclose it.

    For each u the extremum of I(V) inside v_bracket is located by brentq on
    the central-difference slope; the edge is where that extremum crosses zero.
    """
    t = theory()

    def slope(v, u):
        return (t.current_A(p, c, v + h, u) - t.current_A(p, c, v - h, u)) / (2 * h)

    def extremum(u):
        return optimize.brentq(lambda v: float(slope(v, u)), *v_bracket, xtol=1e-15)

    def value(u):
        return float(t.current_A(p, c, extremum(u), u))

    u = optimize.brentq(value, *u_bracket, xtol=1e-14)
    return u, extremum(u)


def graph_laplacian(n, edges):
    lap = np.zeros((n, n))
    for i, j in edges:
        lap[i, i] += 1
        lap[j, j] += 1
        lap[i, j] -= 1
        lap[j, i] -= 1
    return lap


def graph_residual(p, c, u, coupling_S, lap, v):
    """-I(V_i) - G (L V)_i (A): cells at frozen composition c, ohmic junctions G.

    With equal compositions on both sides a constant-field junction current is
    exactly ohmic, G (V_j - V_i), so this is the fast I-V state of a sheet of
    identical cells (the MG0b reduced chain on a general graph).
    """
    t = theory()
    return -t.current_A(p, c, v, u) - coupling_S * (lap @ v)


def graph_jacobian(p, c, u, coupling_S, lap, v, h=1e-7):
    t = theory()
    slope = (t.current_A(p, c, v + h, u) - t.current_A(p, c, v - h, u)) / (2 * h)
    return -np.diag(slope) - coupling_S * lap


def graph_state(p, c, u, coupling_S, lap, v0, tol=1e-15):
    """Newton for a stationary graph state from v0; (V, correction size V) or (None, inf)."""
    v = np.asarray(v0, dtype=float).copy()
    for _ in range(50):
        r = graph_residual(p, c, u, coupling_S, lap, v)
        step = np.linalg.solve(graph_jacobian(p, c, u, coupling_S, lap, v), -r)
        if not np.all(np.isfinite(step)) or np.max(np.abs(step)) > 0.05:
            return None, math.inf
        v = v + step
        if np.max(np.abs(step)) <= tol:
            break
    else:
        return None, math.inf
    r = graph_residual(p, c, u, coupling_S, lap, v)
    last = np.linalg.solve(graph_jacobian(p, c, u, coupling_S, lap, v), -r)
    return v, float(np.max(np.abs(last)))


def graph_leading_rate(p, c, u, coupling_S, lap, v, capacitance_F):
    """Largest eigenvalue (1/s) of the graph model's C dV/dt linearisation."""
    return (
        float(np.max(np.linalg.eigvalsh(graph_jacobian(p, c, u, coupling_S, lap, v))))
        / capacitance_F
    )


def graph_fold(p, c, u, unit_S, lap, v0, lo, hi, *, ratio=1.05, iterations=60):
    """Coupling (units of unit_S) where the branch through v0 at lo ends (a fold).

    Natural continuation in geometric steps until Newton from the previous
    state fails, then bisection on existence; both branches merge at the fold,
    so existence brackets it. Returns (fold, bracket width, last state).
    """
    g, v = lo, graph_state(p, c, u, lo * unit_S, lap, v0)[0]
    if v is None:
        raise ValueError("No graph state at the lower coupling")
    while True:
        trial = min(g * ratio, hi)
        w, _ = graph_state(p, c, u, trial * unit_S, lap, v)
        if w is None:
            break
        g, v = trial, w
        if g >= hi:
            return None, 0.0, v
    a, b, va = g, trial, v
    for _ in range(iterations):
        mid = 0.5 * (a + b)
        w, _ = graph_state(p, c, u, mid * unit_S, lap, va)
        if w is None:
            b = mid
        else:
            a, va = mid, w
        if b - a <= 1e-13 * b:
            break
    return 0.5 * (a + b), b - a, va


def graph_fold_extrapolated(p, c, u, unit_S, lap, v_fold, fold, offsets=(1e-4, 2e-4)):
    """Independent check of a fold: the leading eigenvalue squared is linear in G* - G.

    Solves the state at fold (1 - offset) for two offsets, extrapolates the
    leading eigenvalue's square to zero and returns that coupling.
    """
    points = []
    v = v_fold
    for offset in offsets:
        g = fold * (1 - offset)
        v, _ = graph_state(p, c, u, g * unit_S, lap, v)
        if v is None:
            return None
        lead = np.max(np.linalg.eigvalsh(graph_jacobian(p, c, u, g * unit_S, lap, v)))
        points.append((g, lead * lead))
    (g1, s1), (g2, s2) = points
    return g1 + s1 * (g1 - g2) / (s2 - s1)


def grid_miss_bound(p, c, u_edge, v_edge, spacing=1e-5, h=1e-5):
    """How far inside the true edge a root-grid bisection can stop (control units).

    Near the edge I(V) ~ a (V - V_e)^2 + b (u - u_e); its two roots are closer
    than one grid cell for |u - u_e| < a spacing^2 / (4 |b|).
    """
    t = theory()
    a = (
        t.current_A(p, c, v_edge + h, u_edge)
        - 2 * t.current_A(p, c, v_edge, u_edge)
        + t.current_A(p, c, v_edge - h, u_edge)
    ) / (2 * h * h)
    b = (t.current_A(p, c, v_edge, u_edge + 1e-6) - t.current_A(p, c, v_edge, u_edge - 1e-6)) / 2e-6
    return float(abs(a) * spacing**2 / (4 * abs(b))) if b else math.inf
