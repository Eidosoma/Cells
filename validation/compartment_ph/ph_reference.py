"""FR-4's references: buffered compartment acidification by a proton pump with a counterion,
under the rapid-buffer closure (R-closure, Appendix A) and under full protonation kinetics
(R-kinetic, Appendix A.2), an independent reference.

Written from docs/COMPARTMENT_PH_TRANSFER_DESIGN.md's equations and appendix (§2-§4, §5.1, §6,
§7.1, §13.1 and Appendix A), without reading the engine. numpy, scipy and the standard library,
plus validation.coupling.piecewise_ode (another independent reference's integrator).

The world (Appendix A): an owner cytosol c (volume V_c) and a lumped lumen L (V_L) joined by a
bounding patch of area A_b and capacitance C_b; the owner faces a held bath through an impermeant
plasma patch of capacitance C_p. Each node holds ions (Na, K, Cl), buffers HB_k <-> H+ + B_k (base
valence z_k) and protons.
* **R-closure** (A): the states are H_eq (free plus bound protons, counted from the base forms),
  each buffer's total and the ions; the free h solves g(h) = h + sum_k Bk h/(h + K_k) - Heq = 0
  (§4.1; one buffer in closed form, several by Brent's method in ln h).
* **R-kinetic** (A.2): the states are the free n_H and each buffer's n_HB and n_B, with
  r_k = k_off a_k - k_on h b_k (mM/s), k_off = k_on K_k; it does not share the closure's
  assumption, and its limit as k_on grows is R-closure.
* K_k = c0 exp(dmu_k) with dmu_k = (mu0(HB_k) - mu0(B_k) - mu0(H+))/RT, the registry's potentials
  (§4.1); c0 = 1000 mM; pH = -log10(h/c0).
* Transport, positive from c (inside) to L (outside), in fmol/s (Appendix A; 1e15 fmol/mol):
  - constant field (§7.1): J_s = 1e15 P_s A_b psi(u)(c_in - c_out e^-u), u = z_s F V_b/(RT),
    psi(u) = u/(1 - e^-u); the proton leak reads the free h on both sides (z = 1);
  - the pump (§6): dG_cyc = dG'_ATP + n [RT ln(h_L/h_c) - F V_b],
    dG'_ATP = dG'0 + RT ln(c_ADP c_Pi/(c_ATP c0)), S = [1 + (K_H/h_c)^n]^-1 [1 + K_ATP/c_ATP]^-1,
    J_cyc = k a S (1 - exp(dG_cyc/RT)), moving n H+ from c to L per cycle;
  - K2(b), the self-consistent reversed pump (fr4_acidification_v1's controls.K2_planted_sign at
    e71f1200; ``Pump.reversed_sides``): the same law with its two sides exchanged, so a forward
    cycle moves n H+ from L to c, dG_cyc = dG'_ATP + n [RT ln(h_c/h_L) + F V_b] and
    S = [1 + (K_H/h_L)^n]^-1 [1 + K_ATP/c_ATP]^-1; fuel, work and heat as declared;
  - V_b = phi_c - phi_L = -q_L/C_b; phi_c = (q_c + q_L)/C_p; q = 1e-15 F (fixed + sum z n).
* Energy (Appendix A): dG_stored + Q = W with W = int (-dG'_ATP) J_cyc dt,
  Q = int [-dG_cyc J_cyc + sum_routes J (mu~_in - mu~_out) + (R-kinetic) sum_k -V r_k dG_k] dt,
  G_stored = sum_nodes [sum over every proton form and ion of n (mu0 + RT (ln(c/c0) - 1))]
  + C_b V_b^2/2 + C_p phi_c^2/2 (pJ: 1e-3 x fmol x J/mol, 1e12 x J). At the closure's speciation
  this is §4.4's G*; mu0(H+) = mu0(B_k) = 0 and mu0(HB_k) = RT dmu_k (only differences enter).
* The envelope (§4.2): lambda_k = k_on (h + b_k + K_k) against rho = |dHeq/dt / V| / (beta/ln 10),
  beta = ln 10 (h + sum_k Bk K_k h/(h + K_k)^2); inside when lambda >= 1e3 rho.

Sources: Grabe M, Oster G. J Gen Physiol 2001;117:329-344 (organelle acidification with buffer
capacity and counterions); Keener J, Sneyd J. Mathematical Physiology I, 2nd ed. Springer; 2009
(buffering, the rapid-buffer approximation); Goldman DE. J Gen Physiol 1943;27:37-60 (the
constant-field flux); Hairer E, Wanner G. Solving ODEs II. Springer; 1996 (Radau IIA).
"""

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import brentq

from validation.coupling import piecewise_ode

FMOL_PER_MOL = 1e15
LN10 = math.log(10.0)
IONS = ("Na", "K", "Cl")
Z_ION = {"Na": 1, "K": 1, "Cl": -1}


# ---------------------------------------------------------------- the world


@dataclass(frozen=True)
class Constants:
    faraday_C_per_mol: float
    gas_J_per_mol_K: float
    temperature_K: float
    standard_mM: float = 1000.0  # c0 (§2)

    @property
    def rt(self):
        """RT in J/mol."""
        return self.gas_J_per_mol_K * self.temperature_K


@dataclass(frozen=True)
class Buffer:
    """A buffer at a node: its total (mM), base valence z_k, the registry's
    dmu = (mu0(HB) - mu0(B) - mu0(H+))/RT (so K = c0 e^dmu, pK = -dmu/ln 10), and k_on
    (mM^-1 s^-1; R-kinetic and the envelope only)."""

    total_mM: float
    base_valence: int
    delta_mu0_RT: float
    k_on_per_mM_per_s: float = math.nan

    def K_mM(self, c0):
        return c0 * math.exp(self.delta_mu0_RT)


@dataclass(frozen=True)
class Node:
    volume_pL: float
    pH0: float
    ions_mM: dict  # {Na, K, Cl: mM}
    buffers: tuple = ()


@dataclass(frozen=True)
class Pump:
    """cells.cycle.proton_atp_mass_action_positive@1 (§6) with held (maintained) fuel at the cytosol.
    ``reversed_sides``: K2(b), the declared law with its two sides exchanged (protons taken from
    the lumen, saturating on h_L, given to the cytosol); the fuel stays at the cytosol."""

    n: int
    capacity_fmol_per_s: float
    K_H_mM: float
    K_ATP_mM: float
    ATP_mM: float
    ADP_mM: float
    Pi_mM: float
    dG0_prime_J_per_mol: float
    availability: float = 1.0
    reversed_sides: bool = False


@dataclass(frozen=True)
class World:
    constants: Constants
    cytosol: Node
    lumen: Node
    patch_area_m2: float
    patch_capacitance_F: float
    plasma_capacitance_F: float
    permeability_m_s: dict = field(default_factory=dict)  # {ion: P} on the bounding patch
    proton_permeability_m_s: float = 0.0
    pump: object = None


def check_world(world):
    w = world
    c = w.constants
    if not all(math.isfinite(x) and x > 0 for x in (c.faraday_C_per_mol, c.gas_J_per_mol_K,
                                                     c.temperature_K, c.standard_mM)):
        raise ValueError("constants are finite and > 0")
    for name, node in (("cytosol", w.cytosol), ("lumen", w.lumen)):
        if not (math.isfinite(node.volume_pL) and node.volume_pL > 0 and math.isfinite(node.pH0)):
            raise ValueError(f"{name}: a positive volume and a finite pH0")
        if set(node.ions_mM) != set(IONS) or any(not (x > 0) for x in node.ions_mM.values()):
            raise ValueError(f"{name}: Na, K and Cl, each > 0 mM")
        for b in node.buffers:
            if not (math.isfinite(b.total_mM) and b.total_mM >= 0
                    and math.isfinite(b.delta_mu0_RT)):
                raise ValueError(f"{name}: buffer totals >= 0 and finite potentials")
    if not all(math.isfinite(x) and x > 0 for x in (w.patch_area_m2, w.patch_capacitance_F,
                                                     w.plasma_capacitance_F)):
        raise ValueError("the patch area and the capacitances are > 0")
    if any(s not in IONS or not (p >= 0) for s, p in w.permeability_m_s.items()):
        raise ValueError("ion permeabilities are >= 0, for Na, K and Cl")
    if not (w.proton_permeability_m_s >= 0):
        raise ValueError("the proton permeability is >= 0")
    p = w.pump
    if p is not None:
        if not (isinstance(p.n, int) and 1 <= p.n <= 4):
            raise ValueError("the pump's n is an integer in 1..4 (§6)")
        if not all(x > 0 for x in (p.K_H_mM, p.K_ATP_mM, p.ATP_mM, p.ADP_mM, p.Pi_mM)):
            raise ValueError("pump constants and fuel are > 0")
        if not (p.capacity_fmol_per_s >= 0 and 0 <= p.availability <= 1):
            raise ValueError("capacity >= 0 and availability in [0, 1]")
        if not isinstance(p.reversed_sides, bool):
            raise ValueError("reversed_sides is a bool")


# ---------------------------------------------------------------- the closure


def free_proton(Heq_mM, buffers, c0):
    """h (mM) solving h + sum_k Bk h/(h + K_k) = Heq (§4.1). buffers: [(Bk_mM, K_mM)]. One
    buffer: the closed form without cancellation; several: Brent's method in ln h on
    [Heq/(1 + sum Bk/K_k), Heq]."""
    if not Heq_mM > 0:
        raise ValueError("H_eq > 0: a node whose protons all sit in buffer is not a state")
    active = [(B, K) for B, K in buffers if B > 0]
    if not active:
        return Heq_mM
    if len(active) == 1:
        B, K = active[0]
        beta1 = K + B - Heq_mM
        root = math.sqrt(beta1 * beta1 + 4.0 * K * Heq_mM)
        return 2.0 * K * Heq_mM / (beta1 + root) if beta1 >= 0 else 0.5 * (-beta1 + root)
    lo = Heq_mM / (1.0 + sum(B / K for B, K in active))

    def g(x):
        h = math.exp(x)
        return h + sum(B * h / (h + K) for B, K in active) - Heq_mM

    if lo >= Heq_mM:
        return Heq_mM
    return math.exp(brentq(g, math.log(lo), math.log(Heq_mM), xtol=1e-15,
                           rtol=4 * 2.220446049250313e-16, maxiter=300))


def buffer_capacity(h, buffers):
    """beta = ln 10 (h + sum_k Bk K_k h/(h + K_k)^2) (mM per pH unit)."""
    return LN10 * (h + sum(B * K * h / (h + K) ** 2 for B, K in buffers))


def pH(h_mM, c0):
    return -math.log10(h_mM / c0)


def psi(u):
    """u/(1 - e^-u), 1 at u = 0 (series below |u| = 1e-6)."""
    if abs(u) < 1e-6:
        return 1.0 + u / 2.0 + u * u / 12.0
    return u / -math.expm1(-u)


# ---------------------------------------------------------------- the model


class _Model:
    """Shared transport, charge and energy of both references; ``kinetic`` selects the state."""

    def __init__(self, world, kinetic, k_on_override=None):
        check_world(world)
        self.w = w = world
        self.kinetic = kinetic
        c = w.constants
        self.F, self.rt, self.c0 = c.faraday_C_per_mol, c.rt, c.standard_mM
        self.nodes = (w.cytosol, w.lumen)
        self.V = (w.cytosol.volume_pL, w.lumen.volume_pL)
        self.buf = []  # per node: [(B_tot fmol, K mM, z, dmu, k_on)]
        for i, node in enumerate(self.nodes):
            row = []
            for b in node.buffers:
                k_on = b.k_on_per_mM_per_s
                if k_on_override is not None and k_on_override[i] is not None:
                    k_on = k_on_override[i]
                row.append((b.total_mM * self.V[i], b.K_mM(self.c0), b.base_valence,
                            b.delta_mu0_RT, k_on))
            self.buf.append(row)
        if kinetic:
            for row in self.buf:
                for _, _, _, _, k_on in row:
                    if not (math.isfinite(k_on) and k_on > 0):
                        raise ValueError("R-kinetic needs every buffer's k_on > 0")
        # Initial state at the declared pH0: the equilibrium speciation (§13, A.2).
        self.h0 = [self.c0 * 10.0 ** (-node.pH0) for node in self.nodes]
        self.ions0 = [{s: node.ions_mM[s] * self.V[i] for s in IONS}
                      for i, node in enumerate(self.nodes)]
        self.Heq0, self.fixed = [], []
        for i in range(2):
            h0, V = self.h0[i], self.V[i]
            bound = sum(Bt / V * h0 / (h0 + K) for Bt, K, *_ in self.buf[i]) * V
            heq = V * h0 + bound
            charge = heq + sum(z * Bt for Bt, _, z, _, _ in self.buf[i]) + sum(
                Z_ION[s] * self.ions0[i][s] for s in IONS)
            self.Heq0.append(heq)
            self.fixed.append(-charge)  # each node starts at q = 0
        # Layout.
        self.ion_moving = [s for s in IONS if w.permeability_m_s.get(s, 0.0) > 0.0]
        if kinetic:
            self.nb = [len(r) for r in self.buf]
            per_node = [1 + 2 * nb for nb in self.nb]
            self.offset = [0, per_node[0]]
            base = per_node[0] + per_node[1]
        else:
            self.offset = [0, 1]
            base = 2
        self.iion = base  # moving ions: c then L, in ion_moving order
        self.iW = base + 2 * len(self.ion_moving)
        self.iQ = self.iW + 1
        self.iC = self.iW + 2  # cycles
        self.iR = self.iW + 3  # R-kinetic's reaction heat, a share of Q kept apart (A.2)
        self.size = self.iW + 4
        y0 = np.zeros(self.size)
        for i in range(2):
            o = self.offset[i]
            if kinetic:
                h0, V = self.h0[i], self.V[i]
                y0[o] = h0 * V
                for k, (Bt, K, *_rest) in enumerate(self.buf[i]):
                    a = Bt * h0 / (h0 + K)
                    y0[o + 1 + 2 * k] = a
                    y0[o + 2 + 2 * k] = Bt - a
            else:
                y0[o] = self.Heq0[i]
        for j, s in enumerate(self.ion_moving):
            y0[self.iion + j] = self.ions0[0][s]
            y0[self.iion + len(self.ion_moving) + j] = self.ions0[1][s]
        self.y0 = y0
        scale = np.abs(y0).copy()
        if kinetic:
            for i in range(2):
                o = self.offset[i]
                for k, (Bt, *_r) in enumerate(self.buf[i]):
                    scale[o + 1 + 2 * k] = scale[o + 2 + 2 * k] = max(Bt, 1e-30)
        G0 = abs(1e-3 * self.rt * max(float(np.max(np.abs(y0[:self.iW]))), 1e-30))
        scale[self.iW] = scale[self.iQ] = scale[self.iR] = G0
        scale[self.iC] = max(float(np.max(np.abs(y0[:self.iW]))), 1e-30)
        self.scale = scale

    # -- reading a state
    def speciation(self, y):
        """Per node: dict(h, n_H, forms [(n_HB, n_B)], ions {s: n}, charge_fmol)."""
        out = []
        for i in range(2):
            o, V = self.offset[i], self.V[i]
            ions = dict(self.ions0[i])
            for j, s in enumerate(self.ion_moving):
                ions[s] = float(y[self.iion + j + (len(self.ion_moving) if i else 0)])
            if self.kinetic:
                nH = float(y[o])
                forms = [(float(y[o + 1 + 2 * k]), float(y[o + 2 + 2 * k]))
                         for k in range(self.nb[i])]
                h = nH / V
            else:
                Heq = float(y[o])
                pairs = [(Bt / V, K) for Bt, K, *_ in self.buf[i]]
                h = free_proton(Heq / V, pairs, self.c0)
                nH = h * V
                forms = [(Bt * h / (h + K), Bt * K / (h + K)) for Bt, K, *_ in self.buf[i]]
            charge = self.fixed[i] + nH + sum(
                (z + 1) * a + z * b for (a, b), (_, _, z, _, _) in zip(forms, self.buf[i],
                                                                       strict=True))
            charge += sum(Z_ION[s] * ions[s] for s in IONS)
            out.append(dict(h=h, n_H=nH, forms=forms, ions=ions, charge_fmol=charge))
        return out

    def potentials(self, sp):
        qc = sp[0]["charge_fmol"] * self.F / FMOL_PER_MOL
        qL = sp[1]["charge_fmol"] * self.F / FMOL_PER_MOL
        return -qL / self.w.patch_capacitance_F, (qc + qL) / self.w.plasma_capacitance_F

    def transport(self, sp, Vb):
        """Every flux (fmol/s, c to L), the pump's cycle rate, dG_cyc, dG'_ATP (J/mol), and the
        heat and work rates (pJ/s)."""
        w, F, rt = self.w, self.F, self.rt
        A = w.patch_area_m2
        hc, hL = sp[0]["h"], sp[1]["h"]
        u1 = F * Vb / rt
        out = dict(J_ions={}, heat_rate=0.0, work_rate=0.0)
        for s in self.ion_moving:
            u = Z_ION[s] * u1
            cin, cout = sp[0]["ions"][s] / self.V[0], sp[1]["ions"][s] / self.V[1]
            J = FMOL_PER_MOL * w.permeability_m_s[s] * A * psi(u) * (cin - cout * math.exp(-u))
            out["J_ions"][s] = J
            out["heat_rate"] += 1e-3 * J * (rt * math.log(cin / cout) + Z_ION[s] * F * Vb)
        JH = FMOL_PER_MOL * w.proton_permeability_m_s * A * psi(u1) * (hc - hL * math.exp(-u1))
        out["J_H"] = JH
        out["heat_rate"] += 1e-3 * JH * (rt * math.log(hc / hL) + F * Vb)
        p = w.pump
        if p is None:
            out.update(J_cyc=0.0, dG_cyc=0.0, dG_ATP=0.0, J_H_pump=0.0)
            return out
        dG_atp = p.dG0_prime_J_per_mol + rt * math.log(p.ADP_mM * p.Pi_mM
                                                         / (p.ATP_mM * self.c0))
        # A forward cycle moves n H+ from its source side to its sink side: c to L as declared,
        # L to c reversed (K2(b)). V_b = phi_c - phi_L.
        if p.reversed_sides:
            h_src, h_snk, dphi = hL, hc, Vb  # phi_sink - phi_source = phi_c - phi_L
        else:
            h_src, h_snk, dphi = hc, hL, -Vb
        dG_cyc = dG_atp + p.n * (rt * math.log(h_snk / h_src) + F * dphi)
        x = dG_cyc / rt
        if abs(x) > 80.0:
            raise RuntimeError(f"the pump's |dG_cyc/RT| = {abs(x):.3g} exceeds its domain 80")
        log_sat = (-math.log1p((p.K_H_mM / h_src) ** p.n) - math.log1p(p.K_ATP_mM / p.ATP_mM))
        Jc = p.capacity_fmol_per_s * p.availability * math.exp(log_sat) * -math.expm1(x)
        out.update(J_cyc=Jc, dG_cyc=dG_cyc, dG_ATP=dG_atp,
                   J_H_pump=(-1.0 if p.reversed_sides else 1.0) * p.n * Jc)  # c to L
        out["heat_rate"] += 1e-3 * (-dG_cyc) * Jc
        out["work_rate"] = 1e-3 * (-dG_atp) * Jc
        return out

    def reactions(self, sp):
        """R-kinetic: per node, per buffer, (V r_k in fmol/s, dG_k in J/mol)."""
        out = []
        for i in range(2):
            V, h = self.V[i], sp[i]["h"]
            row = []
            for (a, b), (_, K, _, _, k_on) in zip(sp[i]["forms"], self.buf[i], strict=True):
                ac, bc = a / V, b / V
                r = k_on * K * ac - k_on * h * bc  # mM/s
                dG = self.rt * (math.log(h * bc / (K * ac)) if ac > 0 and bc > 0 else 0.0)
                row.append((V * r, dG))
            out.append(row)
        return out

    def rhs(self, t, y):
        sp = self.speciation(y)
        Vb, _ = self.potentials(sp)
        tr = self.transport(sp, Vb)
        dH = tr["J_H_pump"] + tr["J_H"]  # protons moved c -> L
        out = np.zeros(self.size)
        if self.kinetic:
            rx = self.reactions(sp)
            for i, sign in ((0, -1.0), (1, 1.0)):
                o = self.offset[i]
                out[o] = sign * dH + sum(Vr for Vr, _ in rx[i])
                for k, (Vr, _) in enumerate(rx[i]):
                    out[o + 1 + 2 * k] = -Vr
                    out[o + 2 + 2 * k] = Vr
            reaction_heat = -1e-3 * sum(Vr * dG for row in rx for Vr, dG in row)
        else:
            out[self.offset[0]] = -dH
            out[self.offset[1]] = dH
            reaction_heat = 0.0
        m = len(self.ion_moving)
        for j, s in enumerate(self.ion_moving):
            out[self.iion + j] = -tr["J_ions"][s]
            out[self.iion + m + j] = tr["J_ions"][s]
        out[self.iW] = tr["work_rate"]
        out[self.iQ] = tr["heat_rate"] + reaction_heat
        out[self.iC] = tr["J_cyc"]
        out[self.iR] = reaction_heat
        return out

    def stored_free_energy(self, y):
        """G_stored (pJ), Appendix A's: every proton form and ion, plus the capacitors."""
        sp = self.speciation(y)
        rt, c0 = self.rt, self.c0
        g = 0.0
        for i in range(2):
            V = self.V[i]

            def term(n, mu0, V=V):
                return 0.0 if n == 0 else n * (mu0 + rt * (math.log(n / V / c0) - 1.0))

            g += term(sp[i]["n_H"], 0.0)
            for (a, b), (_, _, _, dmu, _) in zip(sp[i]["forms"], self.buf[i], strict=True):
                g += term(a, rt * dmu) + term(b, 0.0)
            for s in IONS:
                g += term(sp[i]["ions"][s], 0.0)
        Vb, phic = self.potentials(sp)
        return 1e-3 * g + 1e12 * (0.5 * self.w.patch_capacitance_F * Vb ** 2
                                  + 0.5 * self.w.plasma_capacitance_F * phic ** 2)

    def envelope(self, y):
        """Per node: (min_k lambda_k, rho, beta) at the state (§4.2)."""
        sp = self.speciation(y)
        Vb, _ = self.potentials(sp)
        tr = self.transport(sp, Vb)
        dH = tr["J_H_pump"] + tr["J_H"]
        out = []
        for i, sign in ((0, -1.0), (1, 1.0)):
            V, h = self.V[i], sp[i]["h"]
            pairs = [(Bt / V, K) for Bt, K, *_ in self.buf[i]]
            beta = buffer_capacity(h, pairs)
            rho = abs(sign * dH / V) / (beta / LN10)
            lam = min((k_on * (h + b / V + K) for (_, b), (_, K, _, _, k_on)
                       in zip(sp[i]["forms"], self.buf[i], strict=True)), default=math.inf)
            out.append((lam, rho, beta))
        return out


class PHRun:
    """One run. ``at[t]``: dict(pH_c, pH_L, h_c, h_L (mM), Heq_c, Heq_L (fmol), ions_c, ions_L
    (fmol), Vb, phi_c (V), J_cyc, J_H, J_H_pump (the pump's protons, c to L), J_ions (fmol/s),
    dG_cyc (J/mol), cycles (fmol), work_pJ,
    heat_pJ, reaction_heat_pJ (R-kinetic's share of the heat; 0 in R-closure), stored_change_pJ,
    energy_residual_pJ (dG_stored + Q - W), envelope_ratio (lambda/rho per node, §4.2) and
    buffer_capacity (beta per node, mM per pH unit))."""

    def __init__(self, model, run, record):
        self.model, self.run = model, run
        self.steps = run.steps
        self.G0 = model.stored_free_energy(model.y0)
        self.at = {t: self.observe(t) for t in record}

    def observe(self, t):
        m = self.model
        y = self.run.state(t)
        sp = m.speciation(y)
        Vb, phic = m.potentials(sp)
        tr = m.transport(sp, Vb)
        env = m.envelope(y)
        G = m.stored_free_energy(y)
        W, Q = float(y[m.iW]), float(y[m.iQ])
        heq = [sp[i]["n_H"] + sum(a for a, _ in sp[i]["forms"]) for i in range(2)]
        return dict(
            t=t, pH_c=pH(sp[0]["h"], m.c0), pH_L=pH(sp[1]["h"], m.c0), h_c=sp[0]["h"],
            h_L=sp[1]["h"], Heq_c=heq[0], Heq_L=heq[1],
            ions_c=dict(sp[0]["ions"]), ions_L=dict(sp[1]["ions"]), Vb=Vb, phi_c=phic,
            J_cyc=tr["J_cyc"], J_H=tr["J_H"], J_H_pump=tr["J_H_pump"],
            J_ions=dict(tr["J_ions"]), dG_cyc=tr["dG_cyc"],
            cycles=float(y[m.iC]), work_pJ=W, heat_pJ=Q, reaction_heat_pJ=float(y[m.iR]),
            stored_change_pJ=G - self.G0,
            energy_residual_pJ=(G - self.G0) + Q - W,
            envelope_ratio=[lam / rho if rho > 0 else math.inf for lam, rho, _ in env],
            buffer_capacity=[beta for _, _, beta in env],
        )

    def series(self, key, times):
        return np.array([self.observe(t)[key] for t in times])


def integrate(world, t_end, *, record=(), kinetic=False, k_on=None, rtol=1e-11, method="Radau",
              atol_fraction=1e-6):
    """R-closure (kinetic=False) or R-kinetic (kinetic=True; ``k_on`` = (cytosol, lumen) overrides
    of the buffers' k_on, None keeps the declared) from 0 to t_end; Radau at rtol 1e-11
    (Appendix A); each state's atol is rtol x atol_fraction x its own scale."""
    model = _Model(world, kinetic, k_on)
    record = tuple(sorted({float(t) for t in record}))
    points = sorted({0.0, float(t_end), *record})
    run = piecewise_ode.Run(lambda t0, t1: (model.rhs, None), model.y0, points, rtol=rtol,
                            atol=rtol * atol_fraction * model.scale, method=method)
    return PHRun(model, run, record)


# ---------------------------------------------------------------- the acceptance world (§13.1)


def acceptance_world(*, P_K=5e-10, constants=None, k_on=1e7, reversed_pump=False):
    """§13 and §13.1's world: a 10 um owner cytosol, a lumped lumen of 1000 compartments of 250 nm,
    the pump (n = 2) on held fuel, the proton leak and the K+ counterion; ``P_K = 0`` is the
    negative control K1; ``reversed_pump=True`` is K2(b), the pump's two sides exchanged."""
    const = constants or Constants(96485.33212, 8.314462618, 310.0)
    ions = {"Na": 10.0, "K": 140.0, "Cl": 10.0}
    return World(
        constants=const,
        cytosol=Node(4.18879, 7.2, ions, (Buffer(50.0, -1, -7.2 * LN10, k_on),)),
        lumen=Node(6.54498e-2, 7.2, ions, (Buffer(40.0, -1, -6.0 * LN10, k_on),)),
        patch_area_m2=7.85398e-10,
        patch_capacitance_F=7.85398e-12,
        plasma_capacitance_F=1.25664e-9 * 0.01,
        permeability_m_s={"K": P_K} if P_K > 0 else {},
        proton_permeability_m_s=6e-7,
        pump=Pump(n=2, capacity_fmol_per_s=8.3027e-3, K_H_mM=1e-4, K_ATP_mM=0.1, ATP_mM=3.0,
                  ADP_mM=0.3, Pi_mM=3.0, dG0_prime_J_per_mol=-30.5e3,
                  reversed_sides=reversed_pump),
    )
