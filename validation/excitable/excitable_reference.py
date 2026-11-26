"""Excitable-tissue reference (Track E): cells with NaV1.2, Kir2.1 and Kv1.5 populations, leaks,
the Na/K pump and gap junctions, an independent reference.

Written from the equations appendix docs/EXCITABLE_TISSUE_EQUATIONS.md (draft of 14 November 2026,
Track E's branch, read as that one file), without reading the engine, the probe driver or the
probe's records. numpy and scipy only, plus validation.coupling.piecewise_ode (another
independent reference's segment-by-segment integrator).

The model (appendix §2-§6; SI units, amounts in fmol, concentrations in mM = mol/m^3):
* N cells in a chain, cell i joined to i + 1 by one gap junction; each cell faces its own held
  bath at 0 V. Species Na (+1), K (+1), M (-1, permeant) and P (-1, impermeant, constant).
* V_i = q_i / C_i, with q_i(t) = C_i V_i(0) + F sum_s z_s (N_si(t) - N_si(0)) (§2): the charge is
  a state (R-tissue's layout), and M follows from it.
* every route: J = a p [c1 B(-x) - c2 B(x)], x = z F (phi1 - phi2)/(R T), B(x) = x/(e^x - 1)
  (§3), outward or i -> i + 1 positive, in mol/s.
* membrane permeability of s: the leak, plus each population P_max * availability * opening
  (NaV1.2 m^3 h for Na; Kir2.1 m h^2 and Kv1.5 m h for K), plus the stimulus populations
  (P_stim for Na and for K while on).
* gates dg/dt = (g_inf(V) - g)/tau(V) (§4); the pump nu = nu_max sat (1 - e^a) (§5), moving
  3 Na out and 2 K in per cycle; junction permeabilities s_c D_s (5e-8/26e-9) (§6).
Integration: scipy's Radau (rtol 1e-10 by default) with the block-tridiagonal Jacobian sparsity,
segment by segment between breakpoints at every stimulus edge and record, so records are
integration end points; crossing times, peaks and the largest dV/dt are refined by re-integration
from the bracketing solver step.

Sources: Hodgkin AL, Huxley AF. J Physiol 1952;117:500-544 (the gate kinetics); Goldman DE.
J Gen Physiol 1943;27:37-60 and Hodgkin AL, Katz B. J Physiol 1949;108:37-77 (the constant-field
flux); Keener J, Sneyd J. Mathematical Physiology I and II, 2nd ed., Springer 2009 (excitability,
the discrete cable, propagation); Plonsey R, Barr RC. Bioelectricity: A Quantitative Approach,
3rd ed., Springer 2007 (cable theory). The channel laws are BETSE v1.5.0's as restated in the
appendix, a parity reference with no biological calibration (appendix, Sources).
"""

import math
import time
from dataclasses import dataclass, replace

import numpy as np
from scipy.optimize import brentq
from scipy.sparse import csr_matrix
from scipy.special import expit

from validation.coupling import piecewise_ode

FMOL = 1e-15  # mol per fmol
SPECIES = ("Na", "K", "M", "P")
Z = np.array([1.0, 1.0, -1.0, -1.0])
NA, K, M, P = range(4)
PER_CELL = 9  # charge, N_Na, N_K, NaV m h, Kir m h, Kv m h
GATE_DOMAIN_V = (-0.120, 0.060)  # appendix §4: the laws' declared range
JUNCTION_LIMIT_V = 0.120  # appendix §6: the engine refuses a larger transjunctional voltage


# ---------------------------------------------------------------- laws


def bernoulli(x):
    """B(x) = x/(e^x - 1), B(0) = 1, with the series 1 - x/2 + x^2/12 for |x| < 1e-5 (appendix
    §3; the series' error there is below 1e-21). B(-x) = B(x) + x."""
    x = np.asarray(x, dtype=float)
    small = np.abs(x) < 1e-5
    # expm1 capped at 700: B(x) < 1e-300 there, and no overflow warning far outside the domain.
    if not small.any():
        return x / np.expm1(np.minimum(x, 700.0))
    out = np.empty(x.shape)
    big = ~small
    out[big] = x[big] / np.expm1(np.minimum(x[big], 700.0))
    xs = x[small]
    out[small] = 1.0 - xs / 2.0 + xs * xs / 12.0
    return out


def ghk_flux(pa, x, c1, c2):
    """J = pa [c1 B(-x) - c2 B(x)] (mol/s) for pa = area * permeability (m^3/s), x = z F dphi/RT;
    B(-x) = B(x) + x, so one evaluation of B serves both terms."""
    b = bernoulli(x)
    return pa * (c1 * (b + x) - c2 * b)


def kv15(V):
    """Kv1.5 (appendix §4): (m_inf, tau_m, h_inf, tau_h), times in s; opening m h."""
    return (expit((V + 0.0060) / 0.0064), 0.008330 - 0.1163 * V,
            expit(-(V + 0.0253) / 0.0035), 1.620000 - 15.500 * V)


def kir21(V):
    """Kir2.1 (appendix §4): (m_inf, tau_m, h_inf, tau_h); opening m h^2."""
    return (expit(-(V + 0.09648) / 0.02326),
            0.0037 - 0.00337 * expit(-(V + 0.0329) / 0.02793),
            expit((V + 0.16828) / 0.04413),
            0.00085 + 0.3063 * expit((V + 0.11829) / 0.02723))


def nav12(V):
    """NaV1.2 (appendix §4), rates per ms, u = (V + 0.025)/0.009: (m_inf, tau_m, h_inf, tau_h);
    opening m^3 h. h_inf is its own logistic, not alpha_h/(alpha_h + beta_h)."""
    V = np.asarray(V, dtype=float)
    u = (V + 0.025) / 0.009
    w1 = -(V + 0.040) / 0.005
    w2 = (V + 0.065000123) / 0.005
    b = bernoulli(np.stack([u, w1, w2]))
    am, bm = 0.182 * 9.0 * (b[0] + u), 0.124 * 9.0 * b[0]  # B(-u) = B(u) + u
    ah, bh = 0.024 * 5.0 * b[1], 0.0091 * 5.0 * b[2]
    return am / (am + bm), 0.001 / (am + bm), expit(-(V + 0.055) / 0.0062), 0.001 / (ah + bh)


def gate_steady_state(V):
    """The six gates at their steady state at V: NaV m h, Kir m h, Kv m h."""
    n, r, k = nav12(V), kir21(V), kv15(V)
    return np.array([n[0], n[2], r[0], r[2], k[0], k[2]])


@dataclass(frozen=True)
class Constants:
    faraday_C_per_mol: float
    gas_J_per_mol_K: float
    temperature_K: float

    @property
    def rt(self):
        return self.gas_J_per_mol_K * self.temperature_K


@dataclass(frozen=True)
class Pump:
    """cells.cycle.nak_atp_mass_action_positive@1 (appendix §5)."""

    nu_max_mol_per_m2_s: float
    dG0_J_per_mol: float
    ATP_mM: float
    ADP_mM: float
    Pi_mM: float
    K_Na_mM: float
    K_K_mM: float
    K_ATP_mM: float
    standard_mM: float = 1000.0  # the 1000 mM in RT ln(ADP Pi/(ATP 1000 mM))


def pump_rate(pump, constants, area, c_in, c_out, V):
    """The cycle rate nu (mol/s), vectorised over cells; c_in, c_out are [species, cell].

    Delta mu_s = RT ln(c_in/c_out) + z F V (inward), G = G_drive - 3 Delta mu_Na + 2 Delta mu_K,
    a = G/RT, nu = nu_max sat (1 - e^a), with 1 - e^a formed as -expm1(a) (the same value)."""
    rt, F = constants.rt, constants.faraday_C_per_mol
    drive = pump.dG0_J_per_mol + rt * math.log(pump.ADP_mM * pump.Pi_mM
                                               / (pump.ATP_mM * pump.standard_mM))
    # -3 (RT ln(cNa_i/cNa_o) + F V) + 2 (RT ln(cK_i/cK_o) + F V), over RT:
    a = (drive / rt - 3.0 * np.log(c_in[NA] / c_out[NA]) + 2.0 * np.log(c_in[K] / c_out[K])
         - F * V / rt)
    sat = (1.0 / (1.0 + (pump.K_Na_mM / c_in[NA]) ** 3) / (1.0 + (pump.K_K_mM / c_out[K]) ** 2)
           / (1.0 + pump.K_ATP_mM / pump.ATP_mM))
    return pump.nu_max_mol_per_m2_s * area * sat * -np.expm1(a)  # 1 - e^a


# ---------------------------------------------------------------- the tissue


@dataclass(frozen=True)
class Stimulus:
    """A K leak and a Na leak population, each of permeability P (m/s), in the listed cells,
    on for t in each window [t_on, t_off) (appendix §6)."""

    cells: tuple
    permeability_m_s: float
    windows: tuple  # ((t_on, t_off), ...)


@dataclass(frozen=True)
class Tissue:
    """A chain of n cells (n = 1: a single cell). Per-cell arrays may be given for P_NaV, P_Kir,
    P_Kv, c_m and the availabilities, and per-junction s_c (length n - 1), so a modified segment
    is declared by its arrays."""

    constants: Constants
    n: int
    volume_pL: float
    area_m2: float
    c_m_F_per_m2: object  # scalar or (n,)
    leak_m_s: tuple  # (Na, K, M, P)
    P_NaV_m_s: object
    P_Kir_m_s: object
    P_Kv_m_s: object
    pump: Pump
    bath_mM: tuple  # (Na, K, M, P)
    initial_mM: tuple  # (Na, K, M, P), every cell
    s_c: object = 0.0  # scalar or (n - 1,)
    junction_area_m2: float = 0.0
    junction_D_m2_s: tuple = (0.0, 0.0, 0.0, 0.0)
    junction_scale: float = 0.0  # p = s_c D (junction_scale): 5e-8/26e-9 in the appendix
    availability_NaV: object = 1.0
    availability_Kir: object = 1.0
    availability_Kv: object = 1.0
    stimuli: tuple = ()
    pump_on: bool = True

    def per_cell(self, value):
        out = np.broadcast_to(np.asarray(value, dtype=float), (self.n,)).copy()
        return out

    def per_junction(self, value):
        return np.broadcast_to(np.asarray(value, dtype=float), (max(self.n - 1, 0),)).copy()


@dataclass(frozen=True)
class Start:
    """The initial state: V(0) per cell (the charge follows), the potential whose steady state
    sets the gates, and a kick per cell (appendix §6: the initial Na amount raised by C dV/F, so
    that V(0) = V_start + dV with the gates unchanged)."""

    V: object  # scalar or (n,)
    gates_at_V: object  # scalar or (n,)
    kick_V: object = 0.0  # scalar or (n,)


class Model:
    """Index tables and the right-hand side of one tissue."""

    def __init__(self, tissue, start):
        t = tissue
        self.t = t
        self.n = t.n
        self.F = t.constants.faraday_C_per_mol
        self.rt = t.constants.rt
        self.capacitance = t.per_cell(t.c_m_F_per_m2) * t.area_m2  # F
        self.volume = t.volume_pL  # pL
        self.leak = np.asarray(t.leak_m_s, dtype=float)
        self.P_nav = t.per_cell(t.P_NaV_m_s) * t.per_cell(t.availability_NaV)
        self.P_kir = t.per_cell(t.P_Kir_m_s) * t.per_cell(t.availability_Kir)
        self.P_kv = t.per_cell(t.P_Kv_m_s) * t.per_cell(t.availability_Kv)
        self.bath = np.asarray(t.bath_mM, dtype=float)[:, None] * np.ones((1, self.n))
        self.junction = (t.per_junction(t.s_c)[None, :] * np.asarray(t.junction_D_m2_s)[:, None]
                         * t.junction_scale * t.junction_area_m2)  # [species, junction] m^3/s
        V0 = t.per_cell(start.V)
        kick = t.per_cell(start.kick_V)
        self.N0 = (np.asarray(t.initial_mM, dtype=float)[:, None] * self.volume
                   * np.ones((1, self.n)))
        self.N0[NA] += self.capacitance * kick / (self.F * FMOL)  # fmol
        self.V0 = V0 + kick
        self.Q0 = self.capacitance * self.V0 / (self.F * FMOL)  # fmol of charge equivalent
        gates = np.stack([gate_steady_state(v) for v in t.per_cell(start.gates_at_V)], axis=1)
        y = np.empty((self.n, PER_CELL))
        y[:, 0] = self.Q0
        y[:, 1] = self.N0[NA]
        y[:, 2] = self.N0[K]
        y[:, 3:] = gates.T
        self.y0 = y.ravel()
        self.sparsity = self._sparsity()
        self._fast_tables()

    def _fast_tables(self):
        """Constants of the fast right-hand side (rhs): the same laws as kv15, kir21, nav12,
        pump_rate and ghk_flux, with their logistic and Bernoulli arguments as affine maps of V,
        one evaluation of each per call, and B(-x) = B(x) + x. rhs_reference is the readable
        form; the self-tests hold the two together."""
        t, A = self.t, self.t.area_m2
        self.cap_factor = FMOL * self.F / self.capacitance
        self.f_rt = self.F / self.rt
        # Logistic arguments (V + b)/a as V/a + b/a: Kv m, Kv h, Kir m, Kir tau_m, Kir h,
        # Kir tau_h, NaV h_inf.
        a = np.array([0.0064, -0.0035, -0.02326, -0.02793, 0.04413, 0.02723, -0.0062])
        b = np.array([0.0060, 0.0253, 0.09648, 0.0329, 0.16828, 0.11829, 0.055])
        self.log_a, self.log_b = (1.0 / a)[:, None], (b / a)[:, None]
        # NaV's Bernoulli arguments: (V + 0.025)/0.009, -(V + 0.040)/0.005, (V + 0.065000123)/0.005.
        a = np.array([0.009, -0.005, 0.005])
        b = np.array([0.025, 0.040, 0.065000123])
        self.nav_a, self.nav_b = (1.0 / a)[:, None], (b / a)[:, None]
        self.leak_pa = self.leak * A
        self.nav_pa, self.kir_pa, self.kv_pa = self.P_nav * A, self.P_kir * A, self.P_kv * A
        pump, rt = t.pump, self.rt
        drive = pump.dG0_J_per_mol + rt * math.log(pump.ADP_mM * pump.Pi_mM
                                                   / (pump.ATP_mM * pump.standard_mM))
        cb = np.asarray(t.bath_mM, dtype=float)
        self.pump_a = drive / rt + 3.0 * math.log(cb[NA]) - 2.0 * math.log(cb[K])
        self.pump_sat = (pump.nu_max_mol_per_m2_s * A / (1.0 + (pump.K_K_mM / cb[K]) ** 2)
                         / (1.0 + pump.K_ATP_mM / pump.ATP_mM))
        self.pump_K = pump.K_Na_mM
        self.cb = cb

    def _sparsity(self):
        n, m = self.n, PER_CELL
        rows, cols = [], []
        for i in range(n):
            for j in range(max(0, i - 1), min(n, i + 2)):
                for a in range(m):
                    for b in range(m):
                        rows.append(i * m + a)
                        cols.append(j * m + b)
        return csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(n * m, n * m))

    def stimulus_permeability(self, t0, t1):
        """P_stim per cell on (t0, t1) (segments never straddle an edge)."""
        mid = 0.5 * (t0 + t1)
        out = np.zeros(self.n)
        for s in self.t.stimuli:
            if any(on <= mid < off for on, off in s.windows):
                out[list(s.cells)] += s.permeability_m_s
        return out

    def breakpoints(self):
        return sorted({x for s in self.t.stimuli for w in s.windows for x in w})

    def unpack(self, y):
        y = y.reshape(self.n, PER_CELL)
        Q, NNa, NK = y[:, 0], y[:, 1], y[:, 2]
        N = np.empty((4, self.n))
        N[NA], N[K] = NNa, NK
        # q - q0 = F sum z dN, with P constant: M follows from the charge.
        N[M] = self.N0[M] + (NNa - self.N0[NA]) + (NK - self.N0[K]) - (Q - self.Q0)
        N[P] = self.N0[P]
        V = Q * FMOL * self.F / self.capacitance
        return V, N, y[:, 3:]

    def fluxes(self, y, p_stim):
        """(V, concentrations, gates, membrane flux [species, cell], pump rate [cell], junction
        flux [species, junction]) in mol/s."""
        V, N, g = self.unpack(y)
        c = N / self.volume
        mN, hN, mR, hR, mV, hV = g.T
        perm = np.repeat(self.leak[:, None], self.n, axis=1)
        perm[NA] += self.P_nav * mN**3 * hN + p_stim
        perm[K] += self.P_kir * mR * hR**2 + self.P_kv * mV * hV + p_stim
        x = Z[:, None] * (self.F * V / self.rt)[None, :]
        J = ghk_flux(perm * self.t.area_m2, x, c, self.bath)
        nu = (pump_rate(self.t.pump, self.t.constants, self.t.area_m2, c, self.bath, V)
              if self.t.pump_on else np.zeros(self.n))
        if self.n > 1:
            xj = Z[:, None] * (self.F * (V[:-1] - V[1:]) / self.rt)[None, :]
            Jj = ghk_flux(self.junction, xj, c[:, :-1], c[:, 1:])
        else:
            Jj = np.zeros((4, 0))
        return V, c, g, J, nu, Jj

    def rhs(self, y, p_stim):
        """The right-hand side (fast form; see _fast_tables)."""
        n = self.n
        Y = y.reshape(n, PER_CELL)
        Q, NNa, NK = Y[:, 0], Y[:, 1], Y[:, 2]
        mN, hN, mR, hR, mV, hV = Y[:, 3], Y[:, 4], Y[:, 5], Y[:, 6], Y[:, 7], Y[:, 8]
        V = Q * self.cap_factor
        vol = self.volume
        cNa, cK = NNa / vol, NK / vol
        cM = (self.N0[M] + (NNa - self.N0[NA]) + (NK - self.N0[K]) - (Q - self.Q0)) / vol
        L = expit(self.log_a * V + self.log_b)
        x = self.f_rt * V
        nav = self.nav_a * V + self.nav_b
        if n > 1:
            dx = x[:-1] - x[1:]
            B = bernoulli(np.concatenate([x, dx, nav.ravel()]))
            bx, bj, bn = B[:n], B[n:2 * n - 1], B[2 * n - 1:].reshape(3, n)
        else:
            B = bernoulli(np.concatenate([x, nav.ravel()]))
            bx, bn = B[:1], B[1:].reshape(3, 1)
        a_stim = p_stim * self.t.area_m2
        pa_na = self.leak_pa[NA] + self.nav_pa * mN * mN * mN * hN + a_stim
        pa_k = self.leak_pa[K] + self.kir_pa * mR * hR * hR + self.kv_pa * mV * hV + a_stim
        cb = self.cb
        # z = +1: J = pa (c_in (b + x) - c_out b); z = -1: J = pa (c_in b - c_out (b + x)).
        bpx = bx + x
        J_na = pa_na * (cNa * bpx - cb[NA] * bx)
        J_k = pa_k * (cK * bpx - cb[K] * bx)
        J_m = self.leak_pa[M] * (cM * bx - cb[M] * bpx)
        if self.t.pump_on:
            r = self.pump_K / cNa
            a = self.pump_a + np.log(cK * cK / (cNa * cNa * cNa)) - x
            nu = self.pump_sat / (1.0 + r * r * r) * -np.expm1(a)
        else:
            nu = 0.0
        dNa = (-J_na - 3.0 * nu) / FMOL
        dK = (-J_k + 2.0 * nu) / FMOL
        dM = -J_m / FMOL
        if n > 1:
            pj = self.junction
            bjx = bj + dx
            jna = pj[NA] * (cNa[:-1] * bjx - cNa[1:] * bj) / FMOL
            jk = pj[K] * (cK[:-1] * bjx - cK[1:] * bj) / FMOL
            jm = pj[M] * (cM[:-1] * bj - cM[1:] * bjx) / FMOL
            dNa[:-1] -= jna
            dNa[1:] += jna
            dK[:-1] -= jk
            dK[1:] += jk
            dM[:-1] -= jm
            dM[1:] += jm
        u = nav[0]
        am, bm = 1.638 * (bn[0] + u), 1.116 * bn[0]  # 0.182 * 9 and 0.124 * 9 (per ms)
        out = np.empty((n, PER_CELL))
        out[:, 0] = dNa + dK - dM
        out[:, 1] = dNa
        out[:, 2] = dK
        out[:, 3] = (am / (am + bm) - mN) * (am + bm) * 1000.0
        out[:, 4] = (L[6] - hN) * (0.12 * bn[1] + 0.0455 * bn[2]) * 1000.0
        out[:, 5] = (L[2] - mR) / (0.0037 - 0.00337 * L[3])
        out[:, 6] = (L[4] - hR) / (0.00085 + 0.3063 * L[5])
        out[:, 7] = (L[0] - mV) / (0.008330 - 0.1163 * V)
        out[:, 8] = (L[1] - hV) / (1.620000 - 15.500 * V)
        return out.ravel()

    def rhs_reference(self, y, p_stim):
        """The right-hand side in the appendix's own form (kv15, kir21, nav12, pump_rate)."""
        V, c, g, J, nu, Jj = self.fluxes(y, p_stim)
        dN = -J / FMOL  # fmol/s
        dN[NA] -= 3.0 * nu / FMOL
        dN[K] += 2.0 * nu / FMOL
        if self.n > 1:
            dN[:, :-1] -= Jj / FMOL
            dN[:, 1:] += Jj / FMOL
        dN[P] = 0.0
        out = np.empty((self.n, PER_CELL))
        out[:, 0] = Z @ dN
        out[:, 1] = dN[NA]
        out[:, 2] = dN[K]
        n_, r_, k_ = nav12(V), kir21(V), kv15(V)
        out[:, 3] = (n_[0] - g[:, 0]) / n_[1]
        out[:, 4] = (n_[2] - g[:, 1]) / n_[3]
        out[:, 5] = (r_[0] - g[:, 2]) / r_[1]
        out[:, 6] = (r_[2] - g[:, 3]) / r_[3]
        out[:, 7] = (k_[0] - g[:, 4]) / k_[1]
        out[:, 8] = (k_[2] - g[:, 5]) / k_[3]
        return out.ravel()

    def dVdt(self, y, p_stim):
        return self.rhs(y, p_stim).reshape(self.n, PER_CELL)[:, 0] * FMOL * self.F \
            / self.capacitance

    def atol(self, atol):
        a = np.empty((self.n, PER_CELL))
        a[:, 0] = atol["charge"]
        a[:, 1:3] = atol["amount"]
        a[:, 3:] = atol["gate"]
        return a.ravel()


# Absolute tolerances: the charge (fmol, about 1e-2 at rest: 1e-14 is 6e-14 V), the amounts
# (fmol, 4 to 100) and the gates.
ATOL = dict(charge=1e-14, amount=1e-12, gate=1e-12)


# ---------------------------------------------------------------- runs


class Run:
    """One integration. ``at[t]`` gives {V, mM, gates} at each record time; ``V(t)`` gives the
    potentials anywhere by re-integration; the methods below locate crossings, peaks and the
    largest dV/dt."""

    def __init__(self, model, run, record, wall_s):
        self.model, self.run, self.wall_s = model, run, wall_s
        self.steps = run.steps
        self.t_end = run.t_end
        self._cache = None
        self.at = {t: self.observe(t) for t in record}

    def state(self, t):
        return self.run.state(t)

    def V(self, t):
        return self.model.unpack(self.run.state(t))[0]

    def p_stim(self, t, side="right"):
        """The stimulus permeability in force just after (or before) t."""
        eps = 1e-12 * max(1.0, abs(t))
        lo, hi = (t, t + eps) if side == "right" else (t - eps, t)
        return self.model.stimulus_permeability(lo, hi)

    def observe(self, t):
        y = self.run.state(t)
        V, N, g = self.model.unpack(y)
        return dict(t=t, V=V.copy(), mM=(N / self.model.volume).copy(), gates=g.copy())

    def dVdt(self, t, side="right"):
        return self.model.dVdt(self.run.state(t), self.p_stim(t, side))

    # -- the stored steps, with V and dV/dt of every cell
    def _arrays(self):
        """(T, V, D, segment, step) at every stored step: V and dV/dt [step, cell] (dV/dt with
        the stimulus of the step's segment). A segment boundary appears once per segment."""
        if self._cache is None:
            m = self.model
            T, Vs, Ds, S, J = [], [], [], [], []
            for si, (t0, t1, _, _, ts, ys) in enumerate(self.run.segments):
                p = m.stimulus_permeability(t0, t1)
                for j in range(len(ts)):
                    T.append(ts[j])
                    Vs.append(m.unpack(ys[j])[0])
                    Ds.append(m.dVdt(ys[j], p))
                    S.append(si)
                    J.append(j)
            self._cache = (np.array(T), np.array(Vs), np.array(Ds), np.array(S), np.array(J))
        return self._cache

    def _exact(self, k, t):
        """The state at t by re-integration from stored step k (t in k's segment)."""
        T, _, _, S, J = self._arrays()
        t0, t1, fun, jac, ts, ys = self.run.segments[S[k]]
        if t == T[k]:
            return ys[J[k]]
        return self.run.integrate(fun, jac, T[k], t, ys[J[k]])

    def _V_and_dV(self, k, t, cell):
        T, _, _, S, _ = self._arrays()
        t0, t1 = self.run.segments[S[k]][:2]
        y = self._exact(k, t)
        p = self.model.stimulus_permeability(t0, t1)
        return float(self.model.unpack(y)[0][cell]), float(self.model.dVdt(y, p)[cell])

    @staticmethod
    def _hermite(h, v0, v1, d0, d1, s):
        """The cubic Hermite interpolant, its first and second derivatives (per unit t) at s."""
        h00, h10 = 2 * s**3 - 3 * s**2 + 1, s**3 - 2 * s**2 + s
        h01, h11 = -2 * s**3 + 3 * s**2, s**3 - s**2
        v = h00 * v0 + h10 * h * d0 + h01 * v1 + h11 * h * d1
        dv = ((6 * s**2 - 6 * s) * v0 + (3 * s**2 - 4 * s + 1) * h * d0
              + (-6 * s**2 + 6 * s) * v1 + (3 * s**2 - 2 * s) * h * d1) / h
        d2v = ((12 * s - 6) * v0 + (6 * s - 4) * h * d0 + (-12 * s + 6) * v1
               + (6 * s - 2) * h * d1) / (h * h)
        return v, dv, d2v

    def crossing(self, cell, level, *, direction=+1, t_from=0.0, t_to=math.inf):
        """The first t in [t_from, t_to] at which V_cell crosses level in the given direction
        (+1 upward, -1 downward): a change of sign of direction * (V - level) from negative to
        >= 0 between two stored steps of one segment. Located on the cubic Hermite interpolant
        of the stored V and dV/dt, then refined by Newton's method on re-integrations from the
        bracketing step (Brent's method if Newton leaves the bracket). None if none."""
        T, V, D, S, _ = self._arrays()
        g = direction * (V[:, cell] - level)
        same = S[1:] == S[:-1]
        hits = np.nonzero(same & (g[:-1] < 0.0) & (g[1:] >= 0.0) & (T[1:] >= t_from)
                          & (T[:-1] <= t_to))[0]
        for k0 in hits:
            ta, tb = T[k0], T[k0 + 1]
            h = tb - ta
            v0, v1, d0, d1 = V[k0, cell], V[k0 + 1, cell], D[k0, cell], D[k0 + 1, cell]

            def herm(s, v0=v0, v1=v1, d0=d0, d1=d1, h=h):
                return direction * (self._hermite(h, v0, v1, d0, d1, s)[0] - level)

            s0 = brentq(herm, 0.0, 1.0, xtol=1e-15) if herm(0.0) < 0.0 <= herm(1.0) else 1.0
            t = ta + s0 * h
            for _ in range(4):  # Newton on the exact solution
                v, dv = self._V_and_dV(k0, t, cell)
                if dv == 0.0:
                    break
                step = (v - level) / dv
                t_new = t - step
                if not ta <= t_new <= tb:
                    t = float(brentq(lambda x, k0=k0: direction * (self._V_and_dV(k0, x, cell)[0]
                                                                   - level),
                                     ta, tb, xtol=1e-14, rtol=4 * np.finfo(float).eps))
                    break
                t = t_new
                if abs(step) <= 1e-14 * max(1.0, abs(t)):
                    break
            if t_from <= t <= t_to:
                return float(t)
        return None

    def crossings(self, cell, level, *, direction=+1, t_from=0.0, t_to=math.inf):
        """Every crossing in order (see crossing)."""
        out, t = [], t_from
        while True:
            c = self.crossing(cell, level, direction=direction, t_from=t, t_to=t_to)
            if c is None:
                return out
            out.append(c)
            t = c + 1e-12 * max(1.0, c)

    def extremum(self, cell, t_from, t_to, *, kind="max", quantity="V"):
        """(t, value) of the largest (kind "max") or smallest V, or of the largest dV/dt
        (quantity "dVdt"), of a cell on [t_from, t_to].

        V: the best stored step, then the stationary point of the cubic Hermite interpolant in
        its neighbouring brackets, one Newton step on dV/dt = 0 (with the interpolant's second
        derivative), and the value by re-integration. dV/dt: the vertex of the parabola through
        the best stored step and its neighbours, refined once more on three re-integrated
        points. Values at stored steps are kept when the refinement does not improve on them."""
        T, V, D, S, _ = self._arrays()
        sign = 1.0 if kind == "max" else -1.0
        inside = np.nonzero((T >= t_from) & (T <= t_to))[0]
        series = V[:, cell] if quantity == "V" else D[:, cell]
        k = int(inside[np.argmax(sign * series[inside])])
        best_t, best = float(T[k]), float(series[k])
        neighbours = [j for j in (k - 1, k + 1) if 0 <= j < len(T) and S[j] == S[k]
                      and t_from <= T[j] <= t_to]
        if quantity == "V":
            w = np.zeros(self.model.n)
            w[cell] = 1.0
            return self.weighted_extremum(w, t_from, t_to, kind=kind)
        if len(neighbours) == 2:
            a, b = neighbours[0], neighbours[1]
            t_v = self._vertex(T[a], T[k], T[b], D[a, cell], D[k, cell], D[b, cell])
            if t_v is not None and T[a] < t_v < T[b]:
                base = a
                d_v = self._V_and_dV(base, t_v, cell)[1]
                delta = 0.25 * min(t_v - T[a], T[b] - t_v)
                pts = [(t_v + e, self._V_and_dV(base, t_v + e, cell)[1]) for e in (-delta, delta)]
                t_w = self._vertex(pts[0][0], t_v, pts[1][0], pts[0][1], d_v, pts[1][1])
                if t_w is not None and pts[0][0] < t_w < pts[1][0]:
                    d_w = self._V_and_dV(base, t_w, cell)[1]
                    if d_w >= d_v:
                        t_v, d_v = t_w, d_w
                if d_v > best:
                    best_t, best = float(t_v), float(d_v)
        return best_t, best

    def weighted_extremum(self, w, t_from, t_to, *, kind="max"):
        """(t, value) of the largest (kind "max") or smallest w . V on [t_from, t_to], w a
        weight per cell (a cell: a unit vector; a junction's voltage V_i - V_j: e_i - e_j). The
        best stored step, then the stationary point of the cubic Hermite interpolant of w . V in
        its neighbouring brackets, one Newton step on d(w . V)/dt = 0, and the value by
        re-integration; the stored value is kept when that does not improve on it."""
        T, V, D, S, _ = self._arrays()
        w = np.asarray(w, dtype=float)
        g, dg = V @ w, D @ w
        sign = 1.0 if kind == "max" else -1.0
        inside = np.nonzero((T >= t_from) & (T <= t_to))[0]
        k = int(inside[np.argmax(sign * g[inside])])
        best_t, best = float(T[k]), float(g[k])
        m = self.model

        def exact(base, t):
            t0, t1 = self.run.segments[S[base]][:2]
            y = self._exact(base, t)
            p = m.stimulus_permeability(t0, t1)
            return float(w @ m.unpack(y)[0]), float(w @ m.dVdt(y, p))

        for j in (k - 1, k + 1):
            if not (0 <= j < len(T) and S[j] == S[k] and t_from <= T[j] <= t_to):
                continue
            a, b = min(j, k), max(j, k)
            h = T[b] - T[a]
            args = (h, g[a], g[b], dg[a], dg[b])
            c = np.array([3 * (2 * g[a] + h * dg[a] - 2 * g[b] + h * dg[b]),
                          2 * (-3 * g[a] - 2 * h * dg[a] + 3 * g[b] - h * dg[b]),
                          h * dg[a]])  # h d(w . V)/dt of the interpolant, in s
            roots = np.roots(c) if abs(c[0]) > 0 else ([-c[2] / c[1]] if c[1] else [])
            for s in roots:
                if abs(np.imag(s)) > 0 or not 0.0 < np.real(s) < 1.0:
                    continue
                s = float(np.real(s))
                _, _, d2v = self._hermite(*args, s)
                t = T[a] + s * h
                v, dv_exact = exact(a, t)
                if d2v != 0.0:
                    t2 = t - dv_exact / d2v
                    if T[a] <= t2 <= T[b]:
                        v2, _ = exact(a, t2)
                        if sign * v2 >= sign * v:
                            t, v = t2, v2
                if sign * v > sign * best:
                    best_t, best = float(t), float(v)
        return best_t, best

    def junction_voltage_max(self, i, t_from=0.0, t_to=None):
        """(t, V_i - V_(i+1)) at the largest |V_i - V_(i+1)| on [t_from, t_to] (junction i)."""
        t_to = self.t_end if t_to is None else t_to
        w = np.zeros(self.model.n)
        w[i], w[i + 1] = 1.0, -1.0
        hi = self.weighted_extremum(w, t_from, t_to, kind="max")
        lo = self.weighted_extremum(w, t_from, t_to, kind="min")
        return hi if abs(hi[1]) >= abs(lo[1]) else lo

    @staticmethod
    def _vertex(t0, t1, t2, f0, f1, f2):
        """The vertex of the parabola through three points, or None if they are collinear."""
        den = (t0 - t1) * (t0 - t2) * (t1 - t2)
        A = (t2 * (f1 - f0) + t1 * (f0 - f2) + t0 * (f2 - f1)) / den
        B = (t2 * t2 * (f0 - f1) + t1 * t1 * (f2 - f0) + t0 * t0 * (f1 - f2)) / den
        return None if A == 0.0 else -B / (2.0 * A)

    def excursions(self):
        """The smallest and largest V of any cell at the stored steps, and the largest
        |V_i - V_i+1| (appendix §4 and §6 ask for them to be reported)."""
        m = self.model
        lo, hi, dj = math.inf, -math.inf, 0.0
        for *_, ys in self.run.segments:
            for y in ys:
                V = m.unpack(y)[0]
                lo, hi = min(lo, float(V.min())), max(hi, float(V.max()))
                if m.n > 1:
                    dj = max(dj, float(np.max(np.abs(np.diff(V)))))
        return dict(V_min=lo, V_max=hi, junction_max=dj,
                    outside_gate_domain=lo < GATE_DOMAIN_V[0] or hi > GATE_DOMAIN_V[1],
                    junction_over_limit=dj > JUNCTION_LIMIT_V)


def simulate(tissue, start, t_end, *, record=(), rtol=1e-10, atol=None, method="Radau",
             max_step=math.inf):
    """Integrate from 0 to t_end; returns a Run."""
    started = time.perf_counter()
    model = Model(tissue, start)
    record = tuple(sorted({float(t) for t in record}))
    points = sorted({0.0, float(t_end), *record,
                     *(b for b in model.breakpoints() if 0.0 < b < t_end)})
    tolerances = dict(ATOL, **(atol or {}))

    def segment(t0, t1):
        p = model.stimulus_permeability(t0, t1)
        return (lambda t, y: model.rhs(y, p)), None

    sparsity = model.sparsity if model.n >= 4 else None  # dense below four cells
    run = piecewise_ode.Run(segment, model.y0, points, rtol=rtol, atol=model.atol(tolerances),
                            method=method, max_step=max_step, jac_sparsity=sparsity)
    return Run(model, run, record, time.perf_counter() - started)


# ---------------------------------------------------------------- the appendix's worlds


def appendix_constants(temperature_K=310.0):
    """§1: F = N_A e and R = N_A k_B, the exact SI products, at T."""
    na, e, kb = 6.02214076e23, 1.602176634e-19, 1.380649e-23
    return Constants(na * e, na * kb, temperature_K)


H_MM = (5.934560723484736, 136.17199964403224, 7.124496086230464, 135.0)  # §7.1, H's composition
V_H = -0.07955626004246525  # §7.1, the heredity rest
POINTS = {  # §7.2 and §8.6: c_m, P_NaV, P_Kir, P_Kv
    "heredity": dict(c_m=0.05, P_NaV=2.5e-7, P_Kir=1e-8, P_Kv=0.0),
    "point2": dict(c_m=0.05, P_NaV=1e-6, P_Kir=1e-8, P_Kv=3e-7),
    "A": dict(c_m=0.01, P_NaV=1e-6, P_Kir=1e-8, P_Kv=3e-7),  # §8.6 candidate A (the generic)
    "B": dict(c_m=0.01, P_NaV=2.5e-7, P_Kir=1e-8, P_Kv=1e-7),  # §8.6 candidate B (fallback)
}


def appendix_tissue(point, n=1, s_c=0.0, *, constants=None, **changes):
    """The appendix's cell (§2, §3, §5, §6, §7.1) at one of §7.2's points, as a chain of n."""
    p = POINTS[point]
    area = 3.261272165616906e-10
    tissue = Tissue(
        constants=constants or appendix_constants(),
        n=n,
        volume_pL=0.7505222518670602,
        area_m2=area,
        c_m_F_per_m2=p["c_m"],
        leak_m_s=(5.3333333333333356e-11, 1.333333333333334e-10, 1.333333333333334e-10, 0.0),
        P_NaV_m_s=p["P_NaV"],
        P_Kir_m_s=p["P_Kir"],
        P_Kv_m_s=p["P_Kv"],
        pump=Pump(nu_max_mol_per_m2_s=1e-7, dG0_J_per_mol=-37000.0, ATP_mM=1.5, ADP_mM=0.1,
                  Pi_mM=0.1, K_Na_mM=12.0, K_K_mM=0.2, K_ATP_mM=0.5),
        bath_mM=(145.0, 5.0, 140.0, 10.0),
        initial_mM=H_MM,
        s_c=s_c,
        junction_area_m2=9.25e-6 / math.sqrt(3.0) * 1.0e-5,
        junction_D_m2_s=(1.33e-9, 1.96e-9, 1.0e-9, 0.0),
        junction_scale=5.0e-8 / 26.0e-9,
    )
    return replace(tissue, **changes)


def stimulus(cells, P, *windows):
    return Stimulus(tuple(cells), float(P), tuple((float(a), float(b)) for a, b in windows))


