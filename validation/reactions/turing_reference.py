"""Linear stability of a two-species reaction-diffusion system, and Schnakenberg's network as four
mass-action reactions: an independent reference for MG0c (D152, §6.3-§6.4).

Written from docs/SHARED_INVENTORY_REACTIONS_DESIGN.md §6.3, §6.4 and Appendix A ("dispersion",
"Schnakenberg in mass action"), and from textbooks (Turing 1952; Murray 2003, ch. 2; Schnakenberg
1979); never from the engine's operator code. NumPy and SciPy only (no `cells` import).
Interface: validation/reactions/REFERENCES_USAGE.md.

The analysis (Murray 2003, ch. 2). For u_t = f(u, v) + D_u lap u and v_t = g(u, v) + D_v lap v
with uniform steady state (u0, v0) and Jacobian J = [[f_u, f_v], [g_u, g_v]], a mode of wavenumber
k grows at sigma(k^2), the largest real part of the eigenvalues of J - k^2 diag(D_u, D_v).
Diffusion-driven instability needs tr J < 0, det J > 0 and D_v f_u + D_u g_v > 2 sqrt(D_u D_v
det J) > 0. The unstable band lies between the roots of D_u D_v k^4 - (D_v f_u + D_u g_v) k^2
+ det J = 0, and the critical ratio d_c = D_v/D_u is where it opens: with s = sqrt(d_c),
f_u s^2 - 2 sqrt(det J) s + g_v = 0, so s = (sqrt(det J) + sqrt(-f_v g_u))/f_u. On a zero-flux
domain of length L only k = n pi/L appear (Neumann eigenfunctions cos(n pi x/L)); on the
discrete chain of N = L/h nodes k^2 is replaced by lambda_n = (4/h^2) sin^2(n pi/(2N)).

Every function is unit-agnostic: pass the Jacobian, diffusivities and lengths in one consistent
system, non-dimensional (time 1/k, length l = sqrt(D_U/k), D_u = 1, D_v = d) or dimensional (J in
s^-1, D in m^2/s, lengths in m).

Schnakenberg (1979) in mass action (§6.4, Appendix A), with u = c_U/c*, tau = k t, x~ = x/l:
    0 -> U at a k c* (mM/s);  U -> 0 at k (s^-1);  0 -> V at b k c* (mM/s);
    2U + V -> 3U at k/c*^2 (mM^-2 s^-1);
    u_tau = a - u + u^2 v + lap u,   v_tau = b - u^2 v + d lap v,   d = D_V/D_U,
with uniform state u0 = a + b, v0 = b/(a + b)^2 and J = [[-1 + 2 u0 v0, u0^2], [-2 u0 v0, -u0^2]].
U and V share one moiety, so the fourth reaction is closed; the others are sources and a sink.
"""

import math

import numpy as np
from scipy.optimize import minimize_scalar

from validation.reactions import network_reference as nr

# ---------------------------------------------------------------------------- Schnakenberg


def schnakenberg_uniform_state(a, b):
    """(u0, v0) = (a + b, b/(a + b)^2), non-dimensional."""
    u0 = float(a) + float(b)
    return u0, float(b) / u0**2


def schnakenberg_jacobian(a, b):
    """The non-dimensional Jacobian at the uniform state (time unit 1/k) [2, 2]."""
    u0, v0 = schnakenberg_uniform_state(a, b)
    return np.array([[-1.0 + 2.0 * u0 * v0, u0**2], [-2.0 * u0 * v0, -(u0**2)]])


def schnakenberg_rate_constants(a, b, k_per_s, c_star_mM):
    """The four mass-action rate constants (§6.4): name -> (value, units)."""
    k, c = float(k_per_s), float(c_star_mM)
    return {
        "production_U": (float(a) * k * c, "mM/s"),
        "decay_U": (k, "1/s"),
        "production_V": (float(b) * k * c, "mM/s"),
        "autocatalysis": (k / c**2, "1/(mM^2 s)"),
    }


def schnakenberg_network(a, b, k_per_s, c_star_mM, names=("U", "V"), moiety="M", c0_mM=1.0):
    """Schnakenberg's network as four driven mass-action reactions (a `Network`)."""
    k = schnakenberg_rate_constants(a, b, k_per_s, c_star_mM)
    U, V = names
    species = (nr.Species(U, 0.0, {moiety: 1}), nr.Species(V, 0.0, {moiety: 1}))
    reactions = (
        nr.Reaction("production_U", "mass_action", {}, {U: 1}, rate_constant=k["production_U"][0]),
        nr.Reaction("decay_U", "mass_action", {U: 1}, {}, rate_constant=k["decay_U"][0]),
        nr.Reaction("production_V", "mass_action", {}, {V: 1}, rate_constant=k["production_V"][0]),
        nr.Reaction("autocatalysis", "mass_action", {U: 2, V: 1}, {U: 3},
                    rate_constant=k["autocatalysis"][0]),
    )
    return nr.Network(species=species, reactions=reactions, c0_mM=c0_mM)


def schnakenberg_uniform_amounts(a, b, c_star_mM, volume_pL):
    """The uniform state's amounts [2] (fmol): (u0, v0) c* V."""
    u0, v0 = schnakenberg_uniform_state(a, b)
    return np.array([u0, v0]) * float(c_star_mM) * float(volume_pL)


# ---------------------------------------------------------------------------- dispersion


def dispersion_eigenvalues(J, D_u, D_v, k2):
    """Both eigenvalues of J - k^2 diag(D_u, D_v) for each k^2 [..., 2] (complex)."""
    J = np.asarray(J, dtype=float)
    q = np.asarray(k2, dtype=float)
    M = np.broadcast_to(J, q.shape + (2, 2)).copy()
    M[..., 0, 0] -= q * D_u
    M[..., 1, 1] -= q * D_v
    return np.linalg.eigvals(M)


def growth_rate(J, D_u, D_v, k2):
    """sigma(k^2), the largest real part of the eigenvalues of J - k^2 diag(D_u, D_v).

    Closed form for 2 x 2, with the larger real root taken as det/(smaller root) when the trace
    is negative, so that sigma stays accurate near the band edges.
    """
    J = np.asarray(J, dtype=float)
    q = np.asarray(k2, dtype=float)
    a11 = J[0, 0] - q * D_u
    a22 = J[1, 1] - q * D_v
    tr = a11 + a22
    det = a11 * a22 - J[0, 1] * J[1, 0]
    disc = 0.25 * tr * tr - det
    root = np.sqrt(np.abs(disc))
    lower = 0.5 * tr - root
    real_larger = np.where(tr < 0.0, det / np.where(lower == 0.0, -np.inf, lower), 0.5 * tr + root)
    return np.where(disc >= 0.0, real_larger, 0.5 * tr)


def critical_ratio(J):
    """d_c = D_v/D_u at which the band opens: ((sqrt(det J) + sqrt(-f_v g_u))/f_u)^2."""
    J = np.asarray(J, dtype=float)
    det = J[0, 0] * J[1, 1] - J[0, 1] * J[1, 0]
    cross = -J[0, 1] * J[1, 0]
    if J[0, 0] <= 0.0 or det <= 0.0 or cross <= 0.0:
        raise ValueError("no diffusion-driven instability: need f_u > 0, det J > 0, f_v g_u < 0")
    return ((math.sqrt(det) + math.sqrt(cross)) / J[0, 0]) ** 2


def band_edges(J, D_u, D_v):
    """(k2_low, k2_high), the roots of D_u D_v k^4 - (D_v f_u + D_u g_v) k^2 + det J, or None."""
    J = np.asarray(J, dtype=float)
    det = J[0, 0] * J[1, 1] - J[0, 1] * J[1, 0]
    b = D_v * J[0, 0] + D_u * J[1, 1]
    a = D_u * D_v
    disc = b * b - 4.0 * a * det
    if b <= 0.0 or disc <= 0.0:
        return None
    high = (b + math.sqrt(disc)) / (2.0 * a)
    return det / (a * high), high  # The smaller root from the product of the roots.


def fastest_growing(J, D_u, D_v):
    """(k2*, sigma_max): the maximum of sigma over the band (None if there is no band).

    In the band the eigenvalues are real, and sigma(q), q = k^2, is the larger root of
    s^2 - T(q) s + Det(q) = 0 with T = tr J - q (D_u + D_v) and Det = det J - b q + a q^2
    (a = D_u D_v, b = D_v f_u + D_u g_v). Implicit differentiation puts the maximum at
    sigma = (b - 2 a q)/(D_u + D_v), and substituting it gives a quadratic in q,
    a (4a - s1^2) q^2 + 2a (s1 tr J - 2b) q + (b^2 - s1 tr J b + s1^2 det J) = 0, s1 = D_u + D_v,
    solved here in its stable form (a bounded search is the fallback, accurate only to ~1e-8).
    """
    band = band_edges(J, D_u, D_v)
    if band is None:
        return None
    J = np.asarray(J, dtype=float)
    a, s1 = D_u * D_v, D_u + D_v
    T0 = J[0, 0] + J[1, 1]
    det0 = J[0, 0] * J[1, 1] - J[0, 1] * J[1, 0]
    b = D_v * J[0, 0] + D_u * J[1, 1]
    A2 = a * (4.0 * a - s1 * s1)
    A1 = 2.0 * a * (s1 * T0 - 2.0 * b)
    A0 = b * b - s1 * T0 * b + s1 * s1 * det0
    roots = []
    if A2 == 0.0:
        roots = [-A0 / A1] if A1 != 0.0 else []
    else:
        disc = A1 * A1 - 4.0 * A2 * A0
        if disc >= 0.0:
            t = -0.5 * (A1 + math.copysign(math.sqrt(disc), A1))
            roots = [t / A2] + ([A0 / t] if t != 0.0 else [])
    inside = [q for q in roots if band[0] <= q <= band[1]]
    if inside:
        q = max(inside, key=lambda x: float(growth_rate(J, D_u, D_v, x)))
        return float(q), float(growth_rate(J, D_u, D_v, q))
    res = minimize_scalar(lambda q: -float(growth_rate(J, D_u, D_v, q)), bounds=band,
                          method="bounded", options={"xatol": 1e-13 * band[1]})
    return float(res.x), float(-res.fun)


def turing_analysis(J, D_u, D_v):
    """The conditions, the critical ratio, the band and the fastest mode, as a dict."""
    J = np.asarray(J, dtype=float)
    tr = float(J[0, 0] + J[1, 1])
    det = float(J[0, 0] * J[1, 1] - J[0, 1] * J[1, 0])
    lhs = float(D_v * J[0, 0] + D_u * J[1, 1])
    rhs = 2.0 * math.sqrt(D_u * D_v * det) if det > 0 else float("nan")
    try:
        d_c = critical_ratio(J)
    except ValueError:
        d_c = None
    fastest = fastest_growing(J, D_u, D_v)
    return {
        "trace": tr,
        "determinant": det,
        "stable_without_diffusion": tr < 0.0 and det > 0.0,
        "turing_inequality": (lhs, rhs),
        "diffusion_driven_instability": tr < 0.0 and det > 0.0 and lhs > rhs > 0.0,
        "critical_ratio": d_c,
        "band": band_edges(J, D_u, D_v),
        "k2_fastest": fastest[0] if fastest else None,
        "sigma_max": fastest[1] if fastest else None,
        "wavelength": 2.0 * math.pi / math.sqrt(fastest[0]) if fastest else None,
    }


# -------------------------------------------------------------------------------- domains


def _nodes(length, spacing):
    N = float(length) / float(spacing)
    if abs(N - round(N)) > 1e-9 * max(1.0, N):
        raise ValueError("length/spacing must be an integer number of nodes")
    return int(round(N))


def domain_modes(J, D_u, D_v, length, spacing=None, n_max=None):
    """Per mode n = 1, ..., n_max: k^2 = (n pi/L)^2, its discrete lambda_n and both sigmas.

    With spacing (the chain's h), N = L/h nodes, n_max defaults to N - 1 and the discrete
    values are filled; without it they are nan, and n_max defaults to the first mode beyond the
    band's upper edge (at least 1). Returns a dict of arrays.
    """
    L = float(length)
    if spacing is not None:
        N = _nodes(L, spacing)
        n_max = N - 1 if n_max is None else int(n_max)
    elif n_max is None:
        band = band_edges(J, D_u, D_v)
        top = band[1] if band else 1.0
        n_max = max(1, int(math.ceil(L * math.sqrt(top) / math.pi)) + 1)
    n = np.arange(1, int(n_max) + 1)
    k2 = (n * math.pi / L) ** 2
    if spacing is not None:
        lam = (4.0 / float(spacing) ** 2) * np.sin(n * math.pi / (2.0 * N)) ** 2
        sigma_d = growth_rate(J, D_u, D_v, lam)
    else:
        lam = np.full(n.shape, np.nan)
        sigma_d = np.full(n.shape, np.nan)
    return {
        "n": n,
        "k2_continuum": k2,
        "k2_discrete": lam,
        "sigma_continuum": growth_rate(J, D_u, D_v, k2),
        "sigma_discrete": sigma_d,
    }


def fastest_admissible_mode(J, D_u, D_v, length, spacing=None):
    """argmax of sigma_n over the modes with sigma_n > 0 (discrete if spacing), or None."""
    modes = domain_modes(J, D_u, D_v, length, spacing)
    sigma = modes["sigma_discrete"] if spacing is not None else modes["sigma_continuum"]
    if not (sigma > 0.0).any():
        return None
    return int(modes["n"][int(np.argmax(sigma))])


def admissible_unstable_modes(J, D_u, D_v, length, spacing=None):
    """The modes n >= 1 with sigma_n > 0 (discrete if spacing), ascending."""
    modes = domain_modes(J, D_u, D_v, length, spacing)
    sigma = modes["sigma_discrete"] if spacing is not None else modes["sigma_continuum"]
    return [int(n) for n in modes["n"][sigma > 0.0]]


def staircase(J, D_u, D_v, lengths, spacing=None):
    """The fastest admissible mode (or None) for each domain length: a list of (L, n)."""
    return [(float(L), fastest_admissible_mode(J, D_u, D_v, L, spacing)) for L in lengths]
