"""The zero-flux chain: an independent reference for reaction-diffusion on @3's species rows.

Written from docs/SHARED_INVENTORY_REACTIONS_DESIGN.md §6.2-§6.4 and Appendix A ("the zero-flux
chain", "linear evolution per mode"), and from textbooks; never from the engine's operator code.
NumPy and SciPy only (no `cells` import). Interface: validation/reactions/REFERENCES_USAGE.md.

The chain: N nodes of equal volume V (pL) at spacing h (m), joined by faces of conductance
kappa = D_s A/h with face area A = V/h, so that kappa/V = D_s/h^2 (s^-1) and
    dn_s,i/dt = sum_r nu_sr J_r(c_i) + (D_s/h^2) (n_s,i+1 - 2 n_s,i + n_s,i-1),
with zero flux through the two ends (one face each). Units: D in m^2/s, h in m, so lambda_n is
in m^-2 and D lambda_n in s^-1.

Modes (Crank 1975, ch. 14, for the closed forms of linear reaction and diffusion): the Neumann
cosines cos(n pi (i + 1/2)/N), n = 0, ..., N - 1, are exact eigenvectors of the chain's
Laplacian with eigenvalues -lambda_n, lambda_n = (4/h^2) sin^2(n pi/(2N)) (the discrete cosine
transform of type II diagonalises it). A field is f_i = sum_n a_n cos(n pi (i + 1/2)/N), so
a_0 is the mean and a_n = (2/N) sum_i f_i cos(n pi (i + 1/2)/N) for n >= 1. A linear network
with rate matrix K couples species only within a mode, and each mode's coefficient vector
evolves exactly as a_n(t) = expm[(K - lambda_n diag(D)) t] a_n(0) (scipy.linalg.expm: scaling
and squaring, Al-Mohy & Higham 2009); a uniform source enters mode 0 only.

The engine order's linear step map (Appendix A): for a linear network, one composite step
P(dt/2) I(dt) P(dt/2) maps each mode by R T_n R, where R is the SSPRK(3,3) half-step's affine
map (y' = M y + q, M = I + Z + Z^2/2 + Z^3/6 with Z = (dt/2) K; Shu & Osher 1988) and T_n is
@3's species transport for z = 0 under ARS(2,2,2), 1 - dt D lambda_n + (dt D lambda_n)^2/2
per species (Appendix A, from probe 1). It predicts the engine's linear worlds to rounding,
given that order; it is not an exact solution.

The nonlinear integration: the semi-discrete system above, for any declared network, by DOP853
(Hairer, Norsett & Wanner 1993) at rtol 1e-12 by default, segment by segment between records,
optionally with each node's reaction heat and work, dH_i/dt = RT sum_passive J A and
dW_i/dt = sum_driven J (nu . mu_i) (the reactions' bookings only; face heat is @3's).
"""

import math
from dataclasses import dataclass

import numpy as np
from scipy.integrate import solve_ivp
from scipy.linalg import expm

from validation.reactions import network_reference as nr

# ------------------------------------------------------------------------------- modes


def mode_basis(N):
    """C[n, i] = cos(n pi (i + 1/2)/N), n, i = 0, ..., N - 1 [N, N]."""
    n = np.arange(N)[:, None]
    i = np.arange(N)[None, :]
    return np.cos(np.pi * n * (i + 0.5) / N)


def chain_eigenvalues(N, spacing_m):
    """lambda_n = (4/h^2) sin^2(n pi/(2N)) [N] (m^-2); they tend to (n pi/L)^2, L = N h."""
    n = np.arange(N)
    return (4.0 / spacing_m**2) * np.sin(n * np.pi / (2.0 * N)) ** 2


def chain_laplacian(N, spacing_m):
    """The zero-flux chain's Laplacian [N, N] (m^-2): end nodes have one face."""
    L = np.zeros((N, N))
    for i in range(N - 1):
        L[i, i + 1] += 1.0
        L[i + 1, i] += 1.0
        L[i, i] -= 1.0
        L[i + 1, i + 1] -= 1.0
    return L / spacing_m**2


def mode_coefficients(field):
    """Mode coefficients a_n of a field [..., N] (any leading axes, e.g. [S, N]): [..., N]."""
    f = np.asarray(field, dtype=float)
    N = f.shape[-1]
    a = (2.0 / N) * (f @ mode_basis(N).T)
    a[..., 0] *= 0.5
    return a


def field_from_modes(coefficients):
    """The field f_i = sum_n a_n cos(n pi (i + 1/2)/N) from coefficients [..., N]."""
    a = np.asarray(coefficients, dtype=float)
    return a @ mode_basis(a.shape[-1])


def dominant_mode(field, species=0):
    """argmax over n >= 1 of |a_n| for one species row of a field [S, N] (or a row [N])."""
    f = np.asarray(field, dtype=float)
    row = f if f.ndim == 1 else f[species]
    a = mode_coefficients(row)
    return int(1 + np.argmax(np.abs(a[1:])))


def fit_growth_rate(times_s, amplitudes):
    """Least-squares slope of ln|a(t)| against t (s^-1), with its residual RMS (in ln)."""
    t = np.asarray(times_s, dtype=float)
    y = np.log(np.abs(np.asarray(amplitudes, dtype=float)))
    A = np.vstack([t, np.ones_like(t)]).T
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    rms = float(np.sqrt(np.mean((A @ coef - y) ** 2)))
    return float(coef[0]), rms


# --------------------------------------------------------------------- linear networks


def linear_rates(network, multipliers=None):
    """The rate matrix K [S, S] (s^-1, on concentrations) and uniform source p [S] (mM/s).

    dc/dt = K c + p holds exactly for networks of mass action of order 0 or 1 and passive
    reactions with one reactant and one product (coefficient 1 each), without factors; any
    other route with a nonzero multiplier raises ValueError. multipliers [R] (default 1).
    """
    cn = nr.compile_network(network)
    S, R = cn.nu.shape
    m = np.ones(R) if multipliers is None else np.asarray(multipliers, dtype=float).reshape(R)
    K = np.zeros((S, S))
    p = np.zeros(S)
    for r in range(R):
        if m[r] == 0.0:
            continue
        if cn.factors[r]:
            raise ValueError(f"{cn.reactions[r]}: factors make a route nonlinear")
        nu_r = cn.nu[:, r]
        reac = np.flatnonzero(cn.alpha[:, r])
        if cn.law[r] == nr.MASS_ACTION:
            order = cn.alpha[:, r].sum()
            if order == 0:
                p += nu_r * m[r] * cn.rate_constant[r]
            elif order == 1:
                K[:, reac[0]] += nu_r * m[r] * cn.rate_constant[r]
            else:
                raise ValueError(f"{cn.reactions[r]}: order {order:g} is nonlinear")
        elif cn.law[r] == nr.PASSIVE:
            prod = np.flatnonzero(cn.beta[:, r])
            if cn.alpha[:, r].sum() != 1 or cn.beta[:, r].sum() != 1:
                raise ValueError(f"{cn.reactions[r]}: only A <=> B passive routes are linear")
            K[:, reac[0]] += nu_r * m[r] * cn.k_f[r]
            K[:, prod[0]] -= nu_r * m[r] * cn.k_f[r] * math.exp(cn.g[r])
        else:
            raise ValueError(f"{cn.reactions[r]}: michaelis_menten is nonlinear")
    return K, p


def mode_propagator(K, diffusivities, lam, t):
    """expm[(K - lam diag(D)) t] [S, S]: one mode's exact linear propagator (lam in m^-2)."""
    K = np.asarray(K, dtype=float)
    D = np.diag(np.asarray(diffusivities, dtype=float))
    return expm((K - lam * D) * float(t))


def propagate_modes(K, diffusivities, N, spacing_m, coefficients0, t, source=None):
    """Exact mode coefficients [S, N] at time t from coefficients0 [S, N] (§6.2, Appendix A).

    source [S] (field units per second, e.g. mM/s): a uniform production, which enters mode 0.
    """
    a0 = np.asarray(coefficients0, dtype=float)
    S = a0.shape[0]
    lam = chain_eigenvalues(N, spacing_m)
    out = np.empty_like(a0)
    for n in range(N):
        out[:, n] = mode_propagator(K, diffusivities, lam[n], t) @ a0[:, n]
    if source is not None and np.any(source):
        aug = np.zeros((S + 1, S + 1))
        aug[:S, :S] = K
        aug[:S, S] = np.asarray(source, dtype=float)
        out[:, 0] = (expm(aug * float(t)) @ np.concatenate([a0[:, 0], [1.0]]))[:S]
    return out


def propagate_field(K, diffusivities, spacing_m, field0, t, source=None):
    """The exact field [S, N] at time t from field0 [S, N] (concentrations or amounts)."""
    f0 = np.asarray(field0, dtype=float)
    a = propagate_modes(K, diffusivities, f0.shape[1], spacing_m, mode_coefficients(f0), t, source)
    return field_from_modes(a)


def full_propagator(K, diffusivities, N, spacing_m, t):
    """expm of the whole linear system [S N, S N], species-major (index s N + i): a check."""
    A = np.kron(np.asarray(K, dtype=float), np.eye(N))
    A += np.kron(np.diag(np.asarray(diffusivities, dtype=float)), chain_laplacian(N, spacing_m))
    return expm(A * float(t))


def half_step_linear_map(K, h_s, source=None):
    """The SSPRK(3,3) half-step's affine map for dc/dt = K c + p: (M, q), c' = M c + q."""
    K = np.asarray(K, dtype=float)
    S = K.shape[0]
    Z = float(h_s) * K
    eye = np.eye(S)
    M = eye + Z + Z @ Z / 2.0 + Z @ Z @ Z / 6.0
    p = np.zeros(S) if source is None else np.asarray(source, dtype=float)
    q = float(h_s) * (eye + Z / 2.0 + Z @ Z / 6.0) @ p
    return M, q


def transport_polynomial(diffusivities, lam, dt_s):
    """@3's species transport on one mode under ARS(2,2,2): diag(1 - x + x^2/2), x = dt D lam."""
    x = float(dt_s) * np.asarray(diffusivities, dtype=float) * lam
    return np.diag(1.0 - x + 0.5 * x * x)


def strang_mode_map(K, diffusivities, lam, dt_s, source=None):
    """One composite step P(dt/2) I(dt) P(dt/2) on one mode: (M, q), a' = M a + q.

    Pass the source only for mode 0 (lam = 0); other modes see none.
    """
    M_r, q_r = half_step_linear_map(K, 0.5 * float(dt_s), source)
    T = transport_polynomial(diffusivities, lam, dt_s)
    return M_r @ T @ M_r, M_r @ T @ q_r + q_r


# ------------------------------------------------------------------- nonlinear chain


@dataclass(frozen=True)
class ChainTrajectory:
    """Records of the semi-discrete system. Axes: T records, S species, N nodes."""

    times: np.ndarray  # [T] (s)
    amounts: np.ndarray  # [T, S, N] (fmol)
    heat: np.ndarray | None  # [T, N] cumulative reaction heat (pJ), if RT was given
    work: np.ndarray | None  # [T, N] cumulative reaction work (pJ), if RT was given
    rtol: float
    evaluations: int


def integrate_chain(network, amounts_fmol, volume_pL, spacing_m, diffusivities_m2_per_s, times_s,
                    multipliers=None, RT_pJ_per_fmol=None, rtol=1e-12, atol=None):
    """Integrate the semi-discrete reaction-diffusion system on a zero-flux chain (DOP853).

    amounts_fmol [S, N] > 0 at t = 0; volume_pL the common node volume; spacing_m h;
    diffusivities [S] (m^2/s); times_s the record times (>= 0, non-decreasing); multipliers [R]
    or [R, N] (constant); RT_pJ_per_fmol to integrate each node's reaction H and W too.
    atol: absolute tolerance on amounts scaled by each species' largest start amount (default
    1e-3 rtol). Returns a ChainTrajectory.
    """
    cn = nr.compile_network(network)
    n0 = np.array(amounts_fmol, dtype=float)
    S, N = n0.shape
    if S != len(cn.species):
        raise ValueError("amounts must be [species, node]")
    if not (np.isfinite(n0).all() and (n0 > 0).all()):
        raise ValueError("start amounts must be finite and > 0")
    V = float(volume_pL)
    Vv = np.full(N, V)
    m = nr._multipliers(cn, multipliers, None, N)
    rate = np.asarray(diffusivities_m2_per_s, dtype=float).reshape(S) / float(spacing_m) ** 2
    scale = n0.max(axis=1)
    energies = RT_pJ_per_fmol is not None
    RT = float(RT_pJ_per_fmol) if energies else 0.0
    mu0p = RT * (cn.mu0_RT - math.log(cn.c0))
    nu = cn.nu
    passive = cn.passive[:, None]
    driven = cn.driven[:, None]
    SN = S * N

    def rhs(_t, y):
        n = y[:SN].reshape(S, N) * scale[:, None]
        with np.errstate(all="ignore"):
            r = nr._evaluate(cn, n, Vv, m)
        flux = np.diff(n, axis=1)  # n_{i+1} - n_i on the N - 1 faces
        div = np.zeros((S, N))
        div[:, :-1] += flux
        div[:, 1:] -= flux
        dn = nu @ r.net + rate[:, None] * div
        out = [(dn / scale[:, None]).ravel()]
        if energies:
            with np.errstate(all="ignore"):
                mu = RT * np.log(n / V) + mu0p[:, None]
            out.append(RT * np.sum(np.where(passive, r.net * r.affinity, 0.0), axis=0))
            out.append(np.sum(np.where(driven, r.net * (nu.T @ mu), 0.0), axis=0))
        return np.concatenate(out)

    if atol is None:
        atol = 1e-3 * rtol
    atol_vec = np.full(SN, float(atol))
    if energies:
        atol_vec = np.concatenate([atol_vec, np.full(2 * N, rtol * 1e-3 * RT * float(scale.max()))])
    y = np.concatenate([(n0 / scale[:, None]).ravel(), np.zeros(2 * N if energies else 0)])
    times = np.asarray(times_s, dtype=float)
    if times.ndim != 1 or (np.diff(times) < 0).any() or (times.size and times[0] < 0):
        raise ValueError("record times must be >= 0 and non-decreasing")
    T = times.size
    amounts = np.empty((T, S, N))
    heat = np.empty((T, N)) if energies else None
    work = np.empty((T, N)) if energies else None
    t, evaluations = 0.0, 0
    for k, t_next in enumerate(times):
        if t_next > t:
            with np.errstate(all="ignore"):
                sol = solve_ivp(rhs, (t, t_next), y, method="DOP853", rtol=rtol, atol=atol_vec)
            if not sol.success:
                raise RuntimeError(f"DOP853 failed: {sol.message}")
            evaluations += sol.nfev
            y, t = sol.y[:, -1], t_next
        amounts[k] = y[:SN].reshape(S, N) * scale[:, None]
        if energies:
            heat[k] = y[SN:SN + N]
            work[k] = y[SN + N:]
    return ChainTrajectory(times, amounts, heat, work, float(rtol), int(evaluations))
