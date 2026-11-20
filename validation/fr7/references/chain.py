"""R-chain: the linear chain from template to conductance, an independent reference for FR-7's F3.

Written from docs/ABUNDANCE_TO_FUNCTION_DESIGN.md (sections 4, 5, 7 and 9), D217, D218 and D231,
the coupling note's Appendix A (the factor law; D150's turnover as a closed form) and R-cell's form
(validation/coupling/cells_reference.py, read as reference code). Its author never read the engine,
the FR-7 lane's files or any engine test. numpy and scipy only; nothing imports `cells`. It imports
R-full's constant-field flux law (validation.division.cleft_egg_reference.ghk_flux, as R-cell does)
and the coupling references' segment integrator (validation.coupling.piecewise_ode).

The chain (one cell; amounts in fmol, volumes in pL, so n/V is in mM; units are counts):
* the template T, a neutral cytosolic species: dn_T/dt = P_T(t) - k_T n_T with P_T piecewise
  constant from 0 (a dose is n_T(0) > 0, a production pulse a segment with P_T > 0); closed form
  per segment;
* the factor F_T = b + (1 - b) c^n/(K^n + c^n), c = n_T/V, routed onto the unit producer's rate;
* the precursor: dn_P/dt = S_P - k_P n_P - k_a F_T n_P (S_P and k_P are zero in a finite pool);
* the units: dM_1/dt = c_u k_a F_T n_P - kappa M_1, dM_j/dt = kappa (M_{j-1} - M_j) for
  j = 2..m, dN/dt = kappa M_m - k_r N; with m = 0 the units enter N directly. c_u = N_A 1e-15/nu
  units per fmol for nu precursor molecules per unit. Removal k_r acts on all of N, declared
  units included;
* the ledgers: W, the precursor consumed into units (fmol); R, the units removed; C_P, the
  precursor cleared (fmol). The material total T = n_P + (sum_j M_j + N + R)/c_u + C_P - S_P t is
  conserved. The template's produced and cleared amounts close its own balance;
* the conductance: the population's permeability-area product P N/rho_ref (m^3/s), the view's
  P a A with a = N/(A rho_ref), on R-cell's pump-free capacitor graph: one cell, one patch facing
  a held bath at 0 V, constant-field leaks, and the gate-free population.

Three computations, independent of one another:
* the closed forms and quadrature (`reference_chain`): n_T, F_T, the exposure U and, in a finite
  pool, n_P in closed form (Appendix A.3's U, with this module's own closed form for a production
  segment at n = 2); the units as the convolution of the consumption flux with the chain's
  closed-form impulse responses, by Gauss-Legendre panels;
* the chain as an ODE (`simulate`, ions off), DOP853 at rtol 1e-13;
* the cell with the chain inside (`simulate`, ions on), Radau, as R-cell integrates.
Plants are `Variant`s of the ODE. The held factor is also emulated exactly, step by step
(`stepped`).
"""

import math
from bisect import bisect_right
from dataclasses import dataclass

import numpy as np
from scipy.linalg import expm
from scipy.optimize import brentq
from scipy.signal import lfilter
from scipy.special import gammainc

from validation.coupling import piecewise_ode
from validation.division.cleft_egg_reference import ghk_flux  # R-full's law (S3-qualified)

FMOL = 1e-15  # mol per fmol
GL_NODES = 20
PANEL_S = 5.0


def units_per_fmol(nu, avogadro):
    """c_u: units per fmol of precursor for nu precursor molecules per unit."""
    return avogadro * FMOL / nu


def hill_activation(c, K, n):
    """c^n/(K^n + c^n) = 1/(1 + (K/c)^n); 0 at c = 0 (numpy-broadcast)."""
    c = np.asarray(c, dtype=float)
    with np.errstate(divide="ignore", over="ignore"):
        r = np.where(c > 0.0, (K / np.where(c > 0.0, c, 1.0)) ** n, np.inf)
    return 1.0 / (1.0 + r)


def hill_scalar(c, K, n):
    if c <= 0.0:
        return 0.0
    try:
        return 1.0 / (1.0 + (K / c) ** n)
    except OverflowError:
        return 0.0


# ---------------------------------------------------------------- variants (the plants)


@dataclass(frozen=True)
class Variant:
    """The reference (every default) or one plant."""

    name: str = "reference"
    nu_delta: int = 0  # nu_off_by_one: c_u from nu + 1
    cu_per_mol: bool = False  # cu_without_1e-15: c_u = N_A/nu
    stages_delta: int = 0  # maturation_stage_skipped: m - 1
    removal_on_increment: bool = False  # removal_on_increment_only: k_r (N - N_0)
    route_on_clearance: bool = False  # route_on_precursor_clearance
    factor_lag_s: float = 0.0  # the factor read at t - lag: the held factor's shift model
    factor_from_amount: bool = False  # extra: the factor read from n_T as if it were mM


REFERENCE = Variant()


def plant_variants(dt):
    """The registered plants. `factor_held_from_step_start` is modelled here by its shift
    (F read at t - dt/2, equal to the held factor to O(dt^2) at step ends); its chain rows are
    also emulated exactly by `stepped`."""
    return {
        "nu_off_by_one": Variant("nu_off_by_one", nu_delta=1),
        "cu_without_1e-15": Variant("cu_without_1e-15", cu_per_mol=True),
        "maturation_stage_skipped": Variant("maturation_stage_skipped", stages_delta=-1),
        "removal_on_increment_only": Variant("removal_on_increment_only",
                                             removal_on_increment=True),
        "route_on_precursor_clearance": Variant("route_on_precursor_clearance",
                                                route_on_clearance=True),
        "factor_held_from_step_start": Variant("factor_held_from_step_start",
                                               factor_lag_s=0.5 * dt),
        "factor_from_amount": Variant("factor_from_amount", factor_from_amount=True),
    }


# ---------------------------------------------------------------- the template


class Template:
    """D150's turnover of the template in the cytosol: dn/dt = P(t) - k n, P piecewise constant
    from 0. n(t) = n_j e^(-k tau) + (P/k)(1 - e^(-k tau)) on a segment from t_j (Appendix A.3).
    Negative times continue the first segment analytically (used only by the shift model)."""

    def __init__(self, n0_fmol, clearance_per_s, production):
        self.n0, self.k = float(n0_fmol), float(clearance_per_s)
        seg = [(float(a), float(p)) for a, p in production]
        starts = [a for a, _ in seg]
        if not seg or starts[0] != 0.0 or starts != sorted(set(starts)):
            raise ValueError("production segments start at 0 and strictly increase")
        if not (self.k > 0.0 and self.n0 >= 0.0 and all(p >= 0.0 for _, p in seg)):
            raise ValueError("the template needs k > 0, n0 >= 0 and P >= 0")
        self.starts = np.array(starts)
        self.rates = np.array([p for _, p in seg])
        n, prod = [self.n0], [0.0]
        for j in range(len(seg) - 1):
            tau = seg[j + 1][0] - seg[j][0]
            n.append(float(self._step(n[-1], seg[j][1], tau)))
            prod.append(prod[-1] + seg[j][1] * tau)
        self.n_at, self.prod_at = np.array(n), np.array(prod)
        self._starts = starts
        self._n = n
        self._rates = [p for _, p in seg]

    def _step(self, n, p, tau):
        return n * np.exp(-self.k * tau) - (p / self.k) * np.expm1(-self.k * tau)

    def breakpoints(self):
        return [float(a) for a in self.starts[1:]]

    def _index(self, t):
        return np.clip(np.searchsorted(self.starts, t, side="right") - 1, 0, None)

    def amount(self, t):
        t = np.asarray(t, dtype=float)
        j = self._index(t)
        return self._step(self.n_at[j], self.rates[j], t - self.starts[j])

    def amount_scalar(self, t):
        j = max(bisect_right(self._starts, t) - 1, 0)
        tau = t - self._starts[j]
        return self._n[j] * math.exp(-self.k * tau) - (self._rates[j] / self.k) * math.expm1(
            -self.k * tau)

    def produced(self, t):
        t = np.asarray(t, dtype=float)
        j = self._index(t)
        return self.prod_at[j] + self.rates[j] * (t - self.starts[j])

    def cleared(self, t):
        """The cleared amount, k times the integral of n, by the balance n0 + produced - n."""
        return self.n0 + self.produced(t) - self.amount(t)

    def exposure(self, t, volume_pL, K, n):
        """U(t) = integral from 0 to t of c^n/(K^n + c^n), c = n_T/V. Closed form on a decay
        segment, (1/(n k)) ln[(K^n + c_j^n)/(K^n + c^n)], and on a production segment at n = 2;
        Gauss-Legendre quadrature on a production segment otherwise."""
        t = np.atleast_1d(np.asarray(t, dtype=float))
        j_all = self._index(t)
        base = [0.0]
        for j in range(len(self.starts) - 1):
            base.append(base[-1] + float(self._segment_exposure(j, np.array(
                [self.starts[j + 1] - self.starts[j]]), volume_pL, K, n)[0]))
        out = np.empty_like(t)
        for j in np.unique(j_all):
            sel = j_all == j
            out[sel] = base[j] + self._segment_exposure(j, t[sel] - self.starts[j], volume_pL,
                                                        K, n)
        return out

    def _segment_exposure(self, j, tau, V, K, n):
        k, p, cj = self.k, self.rates[j], self.n_at[j] / V
        if p == 0.0:
            # (1/(n k)) log1p(((c_j/K)^n - (c/K)^n)/(1 + (c/K)^n)), (c_j/K)^n - (c/K)^n
            # = -(c_j/K)^n expm1(-n k tau)
            xj = (cj / K) ** n
            x = xj * np.exp(-n * k * tau)
            return np.log1p(-xj * np.expm1(-n * k * tau) / (1.0 + x)) / (n * k)
        a = p / (k * V)
        if n == 2.0:
            d = cj - a
            c = a + d * np.exp(-k * tau)
            dc = -d * np.expm1(-k * tau)  # c_j - c
            h_a = a * a / (K * K + a * a)
            lead = K * K / ((K * K + a * a) * k)
            return h_a * tau + lead * (0.5 * np.log1p(dc * (cj + c) / (K * K + c * c))
                                       + (a / K) * np.arctan(K * dc / (K * K + cj * c)))
        return np.array([self._quadrature_exposure(j, float(s), V, K, n) for s in tau])

    def _quadrature_exposure(self, j, tau, V, K, n, panel=2.0):
        if tau == 0.0:
            return 0.0
        edges = np.linspace(0.0, tau, max(1, int(math.ceil(abs(tau) / panel))) + 1)
        x, w = np.polynomial.legendre.leggauss(GL_NODES)
        total = 0.0
        for a, b in zip(edges, edges[1:], strict=False):
            s = 0.5 * (a + b) + 0.5 * (b - a) * x
            c = self._step(self.n_at[j], self.rates[j], s) / V
            total += 0.5 * (b - a) * float(np.dot(w, hill_activation(c, K, n)))
        return total


# ---------------------------------------------------------------- the world


class World:
    """One registered R-chain world, from the inputs' common blocks and its own entry, under a
    variant (the reference by default)."""

    def __init__(self, inputs, name, variant=REFERENCE):
        c, cell, w = inputs["constants"], inputs["cell"], inputs["worlds"][name]
        self.name, self.variant = name, variant
        self.avogadro = c["avogadro_per_mol"]
        self.F = c["faraday_C_per_mol"]
        self.rt = c["gas_J_per_mol_K"] * c["temperature_K"]
        self.species, self.z = tuple(cell["species"]), tuple(cell["valence"])
        self.bath = tuple(cell["bath_mM"])
        self.volume = cell["volume_pL"]
        self.area, self.cap = cell["patch_area_m2"], cell["capacitance_F"]
        self.leak = tuple(cell["leak_permeability_m_s"])
        pop = cell["population"]
        self.P, self.rel = pop["permeability_m_s"], tuple(pop["relative_permeability"])
        self.rho = pop["reference_density_per_m2"]
        self.cyt = tuple(cell["initial_mM"])
        self.V0 = w["cell_start"]["initial_V"]
        tp = w["template"]
        self.template = Template(tp["n0_fmol"], tp["clearance_per_s"], tp["production"])
        f = w["factor"]
        self.K, self.n, self.b = f["K_mM"], f["n"], f["basal"]
        p = w["precursor"]
        self.nP0, self.S, self.kP = p["n0_fmol"], p["supply_fmol_per_s"], p["clearance_per_s"]
        u = w["units"]
        self.nu, self.ka = u["nu"], u["assembly_per_s"]
        self.kappa, self.kr = u["maturation_per_s"], u["removal_per_s"]
        self.N0, self.M0_declared = u["N0"], tuple(u["M0"])
        self.m_declared = u["stages"]
        self.horizon, self.rows = w["horizon_s"], tuple(w["rows_s"])
        v = variant
        self.cu_declared = units_per_fmol(self.nu, self.avogadro)
        nu = self.nu + v.nu_delta
        self.cu = self.avogadro / nu if v.cu_per_mol else units_per_fmol(nu, self.avogadro)
        self.m = self.m_declared + v.stages_delta
        if self.m < 0:
            raise ValueError(f"{name}: the variant {v.name} does not apply (m = 0)")
        M0 = list(self.M0_declared)
        while len(M0) > self.m:  # a skipped stage: its units join the stage after it
            last = M0.pop()
            if M0:
                M0[-1] += last
        self.M0 = tuple(M0)
        self.N_start = self.N0 + (sum(self.M0_declared) - sum(self.M0) if self.m == 0 else 0.0)

    # -- the factor
    def concentration(self, t):
        nT = self.template.amount(t)
        return nT if self.variant.factor_from_amount else nT / self.volume

    def factor(self, t):
        """F_T from the template state at t (no lag), as the variant reads the concentration."""
        return self.b + (1.0 - self.b) * hill_activation(self.concentration(t), self.K, self.n)

    def drive(self, t):
        """D = (F_T - b)/(1 - b) from the cytosolic concentration (R-clear's drive, no
        compartment)."""
        return hill_activation(self.template.amount(t) / self.volume, self.K, self.n)

    def factor_scalar(self, t):
        nT = self.template.amount_scalar(t - self.variant.factor_lag_s)
        c = nT if self.variant.factor_from_amount else nT / self.volume
        return self.b + (1.0 - self.b) * hill_scalar(c, self.K, self.n)

    # -- the units' linear part
    def unit_matrix(self):
        """B for the states (M_1..M_m, N): maturation kappa, removal k_r on N."""
        m = self.m
        B = np.zeros((m + 1, m + 1))
        for j in range(m):
            B[j, j] = -self.kappa
            if j > 0:
                B[j, j - 1] = self.kappa
        if m > 0:
            B[m, m - 1] = self.kappa
        B[m, m] = -self.kr
        return B

    def unit_start(self):
        return np.array([*self.M0, self.N_start], dtype=float)

    def kernels(self, s):
        """Impulse responses of (M_1..M_m, N) at lag s >= 0 to one unit entering M_1 (or N when
        m = 0): kappa^(j-1) s^(j-1)/(j-1)! e^(-kappa s), and
        (kappa/delta)^m e^(-k_r s) P(m, delta s), delta = kappa - k_r, P the regularized lower
        incomplete gamma function."""
        s = np.asarray(s, dtype=float)
        out = [(self.kappa * s) ** (j - 1) / math.factorial(j - 1) * np.exp(-self.kappa * s)
               for j in range(1, self.m + 1)]
        if self.m == 0:
            out.append(np.exp(-self.kr * s))
        else:
            delta = self.kappa - self.kr
            if not delta > 0.0:
                raise ValueError("the closed-form kernel needs kappa > k_r")
            out.append((self.kappa / delta) ** self.m * np.exp(-self.kr * s)
                       * gammainc(self.m, delta * s))
        return out


# ---------------------------------------------------------------- closed forms and quadrature


def _panels(boundaries, nodes=GL_NODES):
    x, w = np.polynomial.legendre.leggauss(nodes)
    a, b = boundaries[:-1, None], boundaries[1:, None]
    return 0.5 * (a + b) + 0.5 * (b - a) * x[None, :], 0.5 * (b - a) * w[None, :]


def grid(world, rows, panel_s=PANEL_S):
    edges = {0.0, float(world.horizon), *map(float, rows), *world.template.breakpoints()}
    edges |= set(np.arange(0.0, world.horizon, panel_s).tolist())
    return np.array(sorted(e for e in edges if 0.0 <= e <= world.horizon))


def reference_chain(world, rows, panel_s=PANEL_S):
    """The chain at the rows from closed forms and quadrature (reference variant only).

    Returns arrays per quantity: n_T, c, F_T, D, U, n_P, M (list), N, W, C_P, R, total,
    template_produced, template_cleared."""
    if world.variant != REFERENCE:
        raise ValueError("the quadrature path computes the reference only")
    w = world
    rows = np.asarray(rows, dtype=float)
    edges = grid(w, rows, panel_s)
    tau, wt = _panels(edges)
    U_nodes = w.template.exposure(tau.ravel(), w.volume, w.K, w.n).reshape(tau.shape)
    F_nodes = w.factor(tau)
    lam0 = w.kP + w.ka * w.b

    def Lam(t, U):
        return lam0 * t + w.ka * (1.0 - w.b) * U

    if w.S == 0.0:
        nP_nodes = w.nP0 * np.exp(-Lam(tau, U_nodes))
    else:
        # n_P = e^(-Lam) [n_P0 + S J], J(t) = integral of e^Lam; J at panel starts by panel sums,
        # inside a panel by a second Gauss-Legendre rule on [a, tau]
        x, wq = np.polynomial.legendre.leggauss(GL_NODES)
        full = np.sum(wt * np.exp(Lam(tau, U_nodes)), axis=1)
        J_start = np.concatenate([[0.0], np.cumsum(full)])[:-1]
        a = edges[:-1, None, None]
        inner = a + (tau[:, :, None] - a) * 0.5 * (1.0 + x[None, None, :])
        U_inner = w.template.exposure(inner.ravel(), w.volume, w.K, w.n).reshape(inner.shape)
        part = np.sum(0.5 * (tau[:, :, None] - a) * wq[None, None, :]
                      * np.exp(Lam(inner, U_inner)), axis=2)
        J_nodes = J_start[:, None] + part
        nP_nodes = np.exp(-Lam(tau, U_nodes)) * (w.nP0 + w.S * J_nodes)
    cons_nodes = w.ka * F_nodes * nP_nodes  # fmol/s into units
    q_nodes = w.cu * cons_nodes
    W_edges = np.concatenate([[0.0], np.cumsum(np.sum(wt * cons_nodes, axis=1))])
    C_edges = np.concatenate([[0.0], np.cumsum(np.sum(wt * w.kP * nP_nodes, axis=1))])
    idx = np.searchsorted(edges, rows)
    if not np.allclose(edges[idx], rows, rtol=0, atol=0):
        raise RuntimeError("every row is a panel edge")
    B, x0 = w.unit_matrix(), w.unit_start()
    units = np.empty((rows.size, w.m + 1))
    for r, (t, i) in enumerate(zip(rows, idx, strict=True)):
        hom = expm(B * t) @ x0
        sel_tau, sel_q, sel_w = tau[:i], q_nodes[:i], wt[:i]
        ker = w.kernels(t - sel_tau)
        units[r] = hom + np.array([np.sum(sel_w * sel_q * g) for g in ker])
    U_rows = w.template.exposure(rows, w.volume, w.K, w.n)
    if w.S == 0.0:
        nP_rows = w.nP0 * np.exp(-Lam(rows, U_rows))
    else:  # the J at a row (an edge) is the panel sum up to it
        J_edges = np.concatenate([[0.0], np.cumsum(np.sum(wt * np.exp(Lam(tau, U_nodes)),
                                                          axis=1))])
        nP_rows = np.exp(-Lam(rows, U_rows)) * (w.nP0 + w.S * J_edges[idx])
    W, C_P = W_edges[idx], C_edges[idx]
    M = [units[:, j] for j in range(w.m)]
    N = units[:, w.m]
    in_units = units.sum(axis=1)
    R = w.cu * W + x0.sum() - in_units
    total = nP_rows + (in_units + R) / w.cu + C_P - w.S * rows
    nT = w.template.amount(rows)
    return dict(n_T=nT, c=nT / w.volume, F_T=w.factor(rows), D=w.drive(rows), U=U_rows,
                n_P=nP_rows, M=M, N=N, W=W, C_P=C_P, R=R, total=total,
                template_produced=w.template.produced(rows),
                template_cleared=w.template.cleared(rows))


# ---------------------------------------------------------------- the ODE (chain, and the cell)


class Model:
    """The chain's ODE under a variant, with the cell's ions (R-cell's layout: the charge in fmol,
    then every species' amount but the follower, the last charged one) or without them."""

    def __init__(self, world, ions=True):
        w = self.w = world
        self.ions = ions
        z = w.z
        self.ns = len(z)
        self.follower = max(i for i, x in enumerate(z) if x != 0)
        self.others = [i for i in range(self.ns) if i != self.follower]
        nb = (1 + len(self.others)) if ions else 0
        self.i_nP, self.i_M = nb, nb + 1
        self.i_N = nb + 1 + w.m
        self.i_W, self.i_R, self.i_C = self.i_N + 1, self.i_N + 2, self.i_N + 3
        self.size = self.i_C + 1
        self.leak_pa = [w.leak[s] * w.area for s in range(self.ns)]
        self.unit_pa = [w.P * w.rel[s] / w.rho for s in range(self.ns)]  # m^3/s per unit
        self.background = 0.0

    def start(self):
        w, y = self.w, np.zeros(self.size)
        if self.ions:
            n = [x * w.volume for x in w.cyt]
            charge = w.cap * w.V0 / (w.F * FMOL)
            self.background = charge - math.fsum(w.z[s] * n[s] for s in range(self.ns))
            y[0] = charge
            for j, s in enumerate(self.others):
                y[1 + j] = n[s]
        y[self.i_nP] = w.nP0
        y[self.i_M:self.i_M + w.m] = w.M0
        y[self.i_N] = w.N_start
        return y

    def atol(self, scale=1.0):
        a = np.empty(self.size)
        if self.ions:
            a[0] = 1e-15 * scale
            a[1:self.i_nP] = 1e-12 * scale
        a[self.i_nP] = 1e-22 * scale
        a[self.i_M:self.i_N + 1] = 1e-10 * scale
        a[self.i_W], a[self.i_R], a[self.i_C] = 1e-22 * scale, 1e-10 * scale, 1e-22 * scale
        return a

    def ion_state(self, y):
        """(amounts per species in fmol, V)."""
        w = self.w
        n = [0.0] * self.ns
        for j, s in enumerate(self.others):
            n[s] = float(y[1 + j])
        n[self.follower] = (float(y[0]) - self.background - math.fsum(
            w.z[s] * n[s] for s in self.others)) / w.z[self.follower]
        return n, float(y[0]) * FMOL * w.F / w.cap

    def fluxes(self, y, N):
        """Outward fluxes (mol/s) per species: (leak, population)."""
        w = self.w
        n, phi = self.ion_state(y)
        u = w.F * phi / w.rt
        leak, pop = [], []
        for s in range(self.ns):
            c_in = n[s] / w.volume
            leak.append(ghk_flux(self.leak_pa[s], w.z[s], u, c_in, w.bath[s]))
            pop.append(ghk_flux(self.unit_pa[s] * N, w.z[s], u, c_in, w.bath[s]))
        return leak, pop

    def rhs(self, t, y):
        w, v = self.w, self.w.variant
        f = w.factor_scalar(t)
        nP = y[self.i_nP]
        if v.route_on_clearance:
            cons, clr = w.ka * nP, w.kP * f * nP
        else:
            cons, clr = w.ka * f * nP, w.kP * nP
        out = np.empty(self.size)
        out[self.i_nP] = w.S - clr - cons
        q = w.cu * cons
        m, iM = w.m, self.i_M
        if m > 0:
            out[iM] = q - w.kappa * y[iM]
            for j in range(1, m):
                out[iM + j] = w.kappa * (y[iM + j - 1] - y[iM + j])
            inflow = w.kappa * y[iM + m - 1]
        else:
            inflow = q
        N = y[self.i_N]
        removal = w.kr * (N - w.N0) if v.removal_on_increment else w.kr * N
        out[self.i_N] = inflow - removal
        out[self.i_W], out[self.i_R], out[self.i_C] = cons, removal, clr
        if self.ions:
            leak, pop = self.fluxes(y, N)
            dn = [-(leak[s] + pop[s]) / FMOL for s in range(self.ns)]
            out[0] = math.fsum(w.z[s] * dn[s] for s in range(self.ns))
            for j, s in enumerate(self.others):
                out[1 + j] = dn[s]
        return out

    def _ion_block(self, y, N):
        w = self.w
        leak, pop = self.fluxes(y, N)
        dn = [-(leak[s] + pop[s]) / FMOL for s in range(self.ns)]
        out = [math.fsum(w.z[s] * dn[s] for s in range(self.ns))]
        out += [dn[s] for s in self.others]
        return np.array(out)

    def jac(self, t, y):
        """The Jacobian: the chain's linear part exactly, the ion block (in the charge, the
        amounts and N) by central differences."""
        w, v = self.w, self.w.variant
        J = np.zeros((self.size, self.size))
        f = w.factor_scalar(t)
        dcons, dclr = (w.ka, w.kP * f) if v.route_on_clearance else (w.ka * f, w.kP)
        iP, iM, iN, m = self.i_nP, self.i_M, self.i_N, w.m
        J[iP, iP] = -(dcons + dclr)
        if m > 0:
            J[iM, iP] = w.cu * dcons
            for j in range(m):
                J[iM + j, iM + j] = -w.kappa
                if j > 0:
                    J[iM + j, iM + j - 1] = w.kappa
            J[iN, iM + m - 1] = w.kappa
        else:
            J[iN, iP] = w.cu * dcons
        J[iN, iN] = -w.kr
        J[self.i_W, iP], J[self.i_R, iN], J[self.i_C, iP] = dcons, w.kr, dclr
        if self.ions:
            nb = iP
            N = float(y[iN])
            for col in list(range(nb)) + [iN]:
                h = 1e-7 * max(abs(float(y[col])), 1e-3 if col == 0 else 1.0)
                yp, ym = y.copy(), y.copy()
                yp[col] += h
                ym[col] -= h
                Np = float(yp[iN]) if col == iN else N
                Nm = float(ym[iN]) if col == iN else N
                J[:nb, col] = (self._ion_block(yp, Np) - self._ion_block(ym, Nm)) / (2.0 * h)
        return J

    def record(self, t, y):
        w = self.w
        N = float(y[self.i_N])
        M = [float(y[self.i_M + j]) for j in range(w.m)]
        R = float(y[self.i_R])
        nP, W, C = float(y[self.i_nP]), float(y[self.i_W]), float(y[self.i_C])
        # F_T at a row is the factor of the row's own template state (a lag changes only which
        # value the producer used, not the row's)
        rec = dict(t=t, n_P=nP, M=M, N=N, W=W, R=R, C_P=C,
                   total=nP + (sum(M) + N + R) / w.cu_declared + C - w.S * t,
                   PA=w.P * N / w.rho, F_T=float(w.factor(t)))
        if self.ions:
            n, phi = self.ion_state(y)
            _, pop = self.fluxes(y, N)
            rec.update(V=phi, amounts=n,
                       I_pop=w.F * math.fsum(w.z[s] * pop[s] for s in range(self.ns)))
        return rec


def simulate(world, rows, *, ions=True, rtol=None, method=None, atol_scale=1.0):
    """Integrate the chain (and the cell) from 0 to the horizon; records at the rows, each an
    integration end point (piecewise_ode). Defaults: Radau at rtol 1e-12 with the ions, DOP853
    at rtol 1e-13 without."""
    model = Model(world, ions=ions)
    method = method or ("Radau" if ions else "DOP853")
    rtol = rtol if rtol is not None else (1e-12 if ions else 1e-13)
    lag = world.variant.factor_lag_s
    points = {0.0, float(world.horizon), *map(float, rows)}
    for b in world.template.breakpoints():
        points |= {b, b + lag}
    points = sorted(p for p in points if 0.0 <= p <= world.horizon)
    y0 = model.start()

    def segment(t0, t1):
        return model.rhs, (model.jac if method in ("Radau", "BDF", "LSODA") else None)

    run = piecewise_ode.Run(segment, y0, points, rtol=rtol, atol=model.atol(atol_scale),
                            method=method)
    return [model.record(float(t), run.state(float(t))) for t in rows], run.steps


# ---------------------------------------------------------------- the held factor, exactly


def _g2(x):
    """x + expm1(-x) = x^2/2 - x^3/6 + ..., without cancellation."""
    x = np.asarray(x, dtype=float)
    series = x * x * (0.5 - x * (1.0 / 6.0 - x * (1.0 / 24.0 - x / 120.0)))
    return np.where(x < 1e-3, series, x + np.expm1(-x))


SCHEMES = ("held_start", "held_mid", "trapezoid", "strang")


def stepped(world, dt, rows, scheme="held_start"):
    """The chain stepped exactly at step dt under one treatment of the factor. Reference
    parameters only.

    * `held_start`: F_T(t_k) held over [t_k, t_k + dt); the plant `factor_held_from_step_start`
      (first order).
    * `held_mid`: F_T(t_k + dt/2) held (second order).
    * `trapezoid`: F_T(t_k) over the first half-step, F_T(t_k + dt) over the second (second
      order; what a producer's two half-steps read when the template's turnover follows it in
      a Strang sequence).
    * `strang`: the producer's two half-steps (F_T at the midpoint, its units entering M_1 at
      once) around one exact step of maturation and removal (second order; a split chain).

    Each (sub)step is exact for its held factor: the precursor in closed form, the units by
    e^(B h) with a 5-point Gauss-Legendre rule for the input over the sub-step (exact to rounding
    at these rates); the recursion runs as a cascade of first-order filters (E is lower
    triangular)."""
    w = world
    if w.variant != REFERENCE:
        raise ValueError("the stepped emulation takes the reference world")
    if scheme not in SCHEMES:
        raise ValueError(f"scheme is one of {SCHEMES}")
    K = int(round(w.horizon / dt))
    if abs(K * dt - w.horizon) > 1e-9 * w.horizon:
        raise ValueError("the horizon is a whole number of steps")
    k_rows = np.rint(np.asarray(rows) / dt).astype(int)
    tk = np.arange(K) * dt
    if scheme == "trapezoid":  # two held sub-steps per step
        h, sub = 0.5 * dt, 2
        F = np.empty(2 * K)
        F[0::2], F[1::2] = w.factor(tk), w.factor(tk + dt)
    else:
        h, sub = dt, 1
        F = w.factor(tk + (0.0 if scheme == "held_start" else 0.5 * dt))
    lam = w.kP + w.ka * F
    x = lam * h
    one_minus_a = -np.expm1(-x)
    s_k = w.S * one_minus_a / lam
    L = np.cumsum(x)  # A_{k+1} = e^(-L[k])
    n_end = np.exp(-L) * (w.nP0 + np.cumsum(s_k * np.exp(L)))
    n_start = np.concatenate([[w.nP0], n_end[:-1]])
    int_nP = n_start * one_minus_a / lam + w.S * _g2(x) / (lam * lam)
    cons, clr = w.ka * F * int_nP, w.kP * int_nP
    B = w.unit_matrix()
    x0 = w.unit_start()
    if scheme == "strang":
        # x_{k+1} = E (x_k + c_u c1_k e_1) + c_u c2_k e_1, c1 and c2 the half-steps' consumption
        E = expm(B * dt)
        hh = 0.5 * dt
        xh = lam * hh
        a_h = np.exp(-xh)
        n_mid = a_h * n_start + w.S * (-np.expm1(-xh)) / lam
        c1 = w.ka * F * (n_start * (-np.expm1(-xh)) / lam + w.S * _g2(xh) / (lam * lam))
        c2 = w.ka * F * (n_mid * (-np.expm1(-xh)) / lam + w.S * _g2(xh) / (lam * lam))
        v = w.cu * (c1[:, None] * E[:, 0][None, :])
        v[:, 0] += w.cu * c2
    else:
        # x_{k+1} = E x_k + v_k, v_k = c_u k_a F_k sum_g w_g n_P(t_k + s_g) e^(B(h - s_g)) e_1
        E = expm(B * h)
        xg, wg = np.polynomial.legendre.leggauss(5)
        sg, wg = 0.5 * h * (1.0 + xg), 0.5 * h * wg
        cols = np.array([expm(B * (h - s))[:, 0] for s in sg])  # (5, m + 1)
        nP_g = (n_start[:, None] * np.exp(-lam[:, None] * sg[None, :])
                + w.S * (-np.expm1(-lam[:, None] * sg[None, :])) / lam[:, None])
        v = (w.cu * w.ka * F)[:, None] * ((nP_g * wg[None, :]) @ cols)
    n_sub = F.size
    states = np.empty((w.m + 1, n_sub + 1))
    for j in range(w.m + 1):
        drive = v[:, j].copy()
        for i in range(j):
            drive += E[j, i] * states[i, :n_sub]
        y, _ = lfilter([1.0], [1.0, -E[j, j]], drive, zi=[E[j, j] * x0[j]])
        states[j, 0], states[j, 1:] = x0[j], y
    idx = k_rows * sub
    nP_all = np.concatenate([[w.nP0], n_end])
    W = np.concatenate([[0.0], np.cumsum(cons)])
    C = np.concatenate([[0.0], np.cumsum(clr)])
    units = states[:, idx]
    in_units = units.sum(axis=0)
    R = w.cu * W[idx] + x0.sum() - in_units
    nP = nP_all[idx]
    tr = np.asarray(rows, dtype=float)
    return dict(n_P=nP, M=[units[j] for j in range(w.m)], N=units[w.m], W=W[idx],
                C_P=C[idx], R=R,
                total=nP + (in_units + R) / w.cu + C[idx] - w.S * tr,
                PA=w.P * units[w.m] / w.rho, steps=K)


# ---------------------------------------------------------------- the cell's potential


def zero_current_potential(world, N, mM):
    """The potential (V) at which the cell's routes to the bath carry no net current, at
    concentrations mM and N units (the start, and the quasi-steady V of a row)."""
    w = world

    def current(V):
        u = w.F * V / w.rt
        total = []
        for s in range(len(w.z)):
            pa = w.leak[s] * w.area
            total.append(w.z[s] * ghk_flux(pa, w.z[s], u, mM[s], w.bath[s]))
            total.append(w.z[s] * ghk_flux(w.P * w.rel[s] * N / w.rho, w.z[s], u, mM[s],
                                           w.bath[s]))
        return math.fsum(total)

    return brentq(current, -0.3, 0.3, xtol=1e-16, rtol=4.0 * np.finfo(float).eps)


def quasi_steady_sensitivity(world, N, mM, rel=1e-4):
    """dV/d ln N of the zero-current potential at fixed concentrations (V per e-fold), by a
    central difference in ln N."""
    up = zero_current_potential(world, N * math.exp(rel), mM)
    down = zero_current_potential(world, N * math.exp(-rel), mM)
    return (up - down) / (2.0 * rel)
