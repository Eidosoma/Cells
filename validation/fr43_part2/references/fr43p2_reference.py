"""FR-43 part 2: code-blind reference solutions (two writers on one pool, fixed and swelling volume).

Written from the equations alone: the gene unit's laws (docs/TEMPLATED_POLYMERISATION_LAWS.md
sections 0-2, 3.1, 3.2, 3.4 and 4.1-4.8) and the network, water and bath laws quoted in the
references specification (LAWS.md and READOUTS.md, as amended 23 November 2026). Only numpy, scipy
and the standard library are used; nothing here imports the engine.

The whole coupled system is integrated unsplit: the cell's species amounts, the gene unit's free
machines and complexes by stage, the cell's volume (when water is declared) and every cumulative
book (extents, heats and works) as quadrature components of one ODE.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

import numpy as np
from scipy.integrate import solve_ivp

N_AVOGADRO = 6.02214076e23  # 1/mol, SI-exact
K_BOLTZMANN = 1.380649e-23  # J/K, SI-exact
R_GAS = N_AVOGADRO * K_BOLTZMANN  # J/(mol K): the double-precision product (LAWS.md, amended)

NAN = float("nan")
PASSIVE = "ideal_detailed_balance_mass_action@1"
DRIVEN = "mass_action"


def _log(x: float) -> float:
    """ln x, or NaN for a non-positive trial value (the stiff solvers then reject the step)."""
    return math.log(x) if x > 0.0 else NAN


def _single_value(schedule: list[dict], key: str) -> float:
    """The declared schedules are constant from t = 0; refuse anything else."""
    if len(schedule) != 1 or float(schedule[0]["time"]) != 0.0:
        raise ValueError(f"only a single schedule entry at t = 0 is supported, got {schedule}")
    return float(schedule[0][key])


@dataclass
class Chain:
    route: str
    pool: str
    product: str
    residues: int  # L
    stages: int  # m
    per_stage: int  # r = L/m
    speed: float  # v, residues/s
    copies: int  # template copies T
    draws: dict[str, float]  # per residue
    releases: dict[str, float]  # per residue
    saturation: dict[str, float]  # K_d (mM) per draw
    k_init: float  # k_I, 1/(mM s)


@dataclass
class Degradation:
    route: str
    polymer: str
    residues: int
    monomers: dict[str, float]  # per residue
    rate: float  # k_s, 1/s


@dataclass
class Transfer:
    route: str
    stoich: dict[str, float]
    saturation: dict[str, float]
    share: float
    capacity: float  # V_C, mM/s


@dataclass
class Reaction:
    rid: str
    law: str  # DRIVEN or PASSIVE
    reactants: dict[str, float]
    products: dict[str, float]
    k: float  # driven: k in mM^(1-q)/s; passive: k_f in 1/s at c0
    multiplier: float
    nu: dict[str, float] = field(default_factory=dict)


@dataclass
class Water:
    bulk_modulus: float  # K, Pa
    n_imp: float  # fmol
    v_ref: float  # pL
    p0: float  # Pa
    v_min: float
    v_max: float
    lp: float  # m/(Pa s)
    area: float  # m^2
    availability: float
    psi_out: float  # Pa, fixed (held bath)


class World:
    """One cell on a held bath, read from a declared world file."""

    def __init__(self, path: str, network_k_factor: float = 1.0):
        with open(path) as fh:
            d = json.load(fh)
        self.path = path
        model, exp = d["model"], d["experiment"]
        self.T = float(model["temperature_K"])
        self.RT_J = R_GAS * self.T  # J/mol = Pa m^3/mol
        self.RT_pJ = self.RT_J * 1e-3  # pJ/fmol (1 fmol x 1 kJ/mol = 1 pJ)

        (cell,) = model["cells"]
        (bath,) = model["extracellular"]
        if not bath.get("reservoir", False):
            raise ValueError("the bath must be held")
        self.cell_id = cell["id"]
        self.species = [s["id"] for s in model["species"]]
        self.idx = {s: i for i, s in enumerate(self.species)}
        self.n0 = [float(cell["initial_amount_fmol"][s]) for s in self.species]
        self.V0 = float(cell["volume_pL"])
        self.bath_conc = {s: float(bath["initial_amount_fmol"][s]) / float(bath["volume_pL"])
                          for s in self.species}
        # Nothing but water crosses the membrane: every solute permeability must be 0.
        for mem in model["membranes"]:
            for s, p in mem["permeability_m_per_s"].items():
                if p != 0.0:
                    raise ValueError(f"nonzero permeability for {s}")
        # Declared moieties (weights per molecule), for the identity checks only.
        self.moieties = {m["id"]: {s: float(w) for s, w in m["weights"].items()}
                         for m in model.get("moieties", [])}
        # Registry potentials (mu°/RT at the model's standard concentration), where declared.
        self.registry_c0 = model.get("standard_concentration_mM")
        self.registry_mu = {s["id"]: float(s["standard_mu_RT"]) for s in model["species"]
                            if "standard_mu_RT" in s}

        ops = {op["law"]: op for op in model["operators"]}
        self.gene = False
        if "templated_polymerisation@1" in ops:
            self._read_gene(ops["templated_polymerisation@1"], exp)
        self.reactions: list[Reaction] = []
        self.net_mu: dict[str, float] = {}
        self.net_c0 = None
        self.net_moieties: dict[str, dict[str, float]] = {}
        if "local_species_reactions@1" in ops:
            self._read_network(ops["local_species_reactions@1"], exp, network_k_factor)
        self.water = None
        if "ideal_osmosis_linear_compliance_water@1" in ops:
            self._read_water(ops["ideal_osmosis_linear_compliance_water@1"], model, exp)
        self.end_time = float(exp["end_time"])
        self.observation_times = [float(t) for t in exp["observation_times"]]
        self._layout()

    # ------------------------------------------------------------------ reading
    def _read_gene(self, op: dict, exp: dict) -> None:
        # The scheduled values, one per route id (LAWS.md, amended): tx -> k_I, deg_R -> k_s,
        # recharge -> V_C.
        controls = {c["route_id"]: _single_value(c["schedule"], "value")
                    for c in exp["polymerisation_controls"]}
        (pool,) = op["pools"]
        if pool["cell"] != self.cell_id:
            raise ValueError("pool not in the cell")
        self.pool_id = pool["id"]
        # A pool's `machines` is a count of molecules in its cell, like a chain's template copies
        # (LAWS.md, amendment 2): M_q = machines x 1e15/N_A fmol. F_q, the complexes and every
        # flux stay in fmol.
        self.machines_copies = float(pool["machines"])
        self.machines_total = self.machines_copies * 1e15 / N_AVOGADRO
        (ch,) = op["chains"]
        L, m = int(ch["residues"]), int(ch["stages"])
        if L % m:
            raise ValueError("stages must divide residues")
        self.chain = Chain(
            route=ch["id"], pool=ch["pool"], product=ch["product"], residues=L, stages=m,
            per_stage=L // m, speed=float(ch["speed_per_s"]), copies=int(ch["template"]["copies"]),
            draws={k: float(v) for k, v in ch["draws"].items()},
            releases={k: float(v) for k, v in ch["releases"].items()},
            saturation={k: float(v) for k, v in ch["saturation_mM"].items()},
            k_init=controls[ch["id"]])
        if set(self.chain.saturation) != set(self.chain.draws):
            raise ValueError("each draw saturates in its own row (section 4.2)")
        (dg,) = op["degradations"]
        self.degradation = Degradation(
            route=dg["id"], polymer=dg["polymer"], residues=int(dg["residues"]),
            monomers={k: float(v) for k, v in dg["monomers"].items()}, rate=controls[dg["id"]])
        (tr,) = op["transfers"]
        self.transfer = Transfer(
            route=tr["id"], stoich={k: float(v) for k, v in tr["stoichiometry"].items()},
            saturation={k: float(v) for k, v in tr["saturation_mM"].items()},
            share=float(tr["share"]), capacity=controls[tr["id"]])
        self.gene_c0 = float(op["standard_concentration_mM"])
        self.gene_mu = {s["id"]: float(s["standard_mu_RT"]) for s in op["species"]}
        for s, mu in self.gene_mu.items():
            if self.registry_mu.get(s) != mu:
                raise ValueError(f"the gene unit's potential for {s} is not the registry's")
        # The cited standard free energies are declarations only (LAWS.md, amended): kept for
        # NOTES.md's consistency check; every rate and booking reads the potentials.
        sfe = dg["standard_free_energy"]
        self.deg_cited_RT = (float(sfe["dG_kJ_mol"]) / (self.RT_J * 1e-3)
                             + float(sfe.get("dG_RT_offset", 0.0)))
        self.rc_cited_RT = float(tr["standard_free_energy"]["dG_RT"])
        self.gene = True

    def _read_network(self, op: dict, exp: dict, k_factor: float) -> None:
        mult = {c["reaction_id"]: _single_value(c["schedule"], "multiplier")
                for c in exp["reaction_controls"]}
        self.net_c0 = float(op["standard_concentration_mM"])
        self.net_mu = {s["id"]: float(s["standard_mu_RT"]) for s in op["species"]}
        self.net_moieties = {s["id"]: {k: float(v) for k, v in s.get("moieties", {}).items()}
                             for s in op["species"]}
        for r in op["reactions"]:
            if r["sites"]["cells"] != [self.cell_id] or r["factors"]:
                raise ValueError("unsupported reaction site or factor")
            if r["law"] == DRIVEN:
                k = float(r["rate_constant"])
            elif r["law"] == PASSIVE:
                k = float(r["forward_rate_per_s"])
            else:
                raise ValueError(r["law"])
            rx = Reaction(rid=r["id"], law=r["law"],
                          reactants={s: float(v) for s, v in r["reactants"].items()},
                          products={s: float(v) for s, v in r["products"].items()},
                          k=k * k_factor, multiplier=mult[r["id"]])
            # the declared order (reactants, then products): a set's order would follow Python's
            # per-process string hashing, and with it the summation order of dG_r's last bits
            for s in list(rx.reactants) + [p for p in rx.products if p not in rx.reactants]:
                rx.nu[s] = rx.products.get(s, 0.0) - rx.reactants.get(s, 0.0)
            if "N" in rx.nu and rx.law != DRIVEN:
                raise ValueError("N's network books are defined for a one-way (driven) route")
            self.reactions.append(rx)

    def _read_water(self, op: dict, model: dict, exp: dict) -> None:
        (comp,) = op["compartments"]
        (bath,) = op["baths"]
        (wm,) = op["membranes"]
        if comp["compartment_id"] != self.cell_id:
            raise ValueError("water compartment is not the cell")
        mem = {m["id"]: m for m in model["membranes"]}[wm["membrane_id"]]
        avail = {c["membrane_id"]: _single_value(c["schedule"], "availability")
                 for c in exp["water_controls"]}[wm["membrane_id"]]
        p_b = float(bath["hydrostatic_pressure_Pa"])
        psi_out = p_b - self.RT_J * sum(self.bath_conc.values())
        self.water = Water(
            bulk_modulus=float(comp["bulk_modulus_Pa"]), n_imp=float(comp["impermeant_amount_fmol"]),
            v_ref=float(comp["reference_volume_pL"]), p0=float(comp["pressure_offset_Pa"]),
            v_min=float(comp["minimum_volume_pL"]), v_max=float(comp["maximum_volume_pL"]),
            lp=float(wm["hydraulic_permeability_m_per_Pa_s"]), area=float(mem["area_m2"]),
            availability=avail, psi_out=psi_out)

    # ------------------------------------------------------------------ layout
    def _layout(self) -> None:
        names = [f"n.{s}" for s in self.species]
        if self.gene:
            names.append(f"F.{self.pool_id}")
            names += [f"C.{self.chain.route}.{j}" for j in range(1, self.chain.stages + 1)]
        if self.water:
            names.append("V")
        acc = []
        if self.gene:
            acc += ["ext.init", "ext.exits", "ext.rel", "ext.deg", "ext.rc", "H.tx", "H.deg", "H.rc"]
        for rx in self.reactions:
            acc += [f"ext.net.{rx.rid}", f"dG.net.{rx.rid}"]
        if self.water:
            acc += ["H.water", "W.bath"]
        self.state_names = names
        self.acc_names = acc
        self.names = names + acc
        self.pos = {nm: i for i, nm in enumerate(self.names)}
        self.n_state = len(names)
        self._prepare()

    def _prepare(self) -> None:
        """Index and coefficient tuples for the right-hand side."""
        idx = self.idx
        if self.gene:
            ch, dg, tr = self.chain, self.degradation, self.transfer
            lnc0 = math.log(self.gene_c0)
            m0 = {s: self.gene_mu[s] - lnc0 for s in self.gene_mu}  # mu°/RT - ln c0
            self._mu_res = self.gene_mu[ch.product] / ch.residues  # mu°_res/RT (section 3.1)
            self._tx_terms = ([(idx[s], v, m0[s]) for s, v in ch.releases.items()]
                              + [(idx[s], -v, m0[s]) for s, v in ch.draws.items()])
            self._tx_sat = [(idx[s], K) for s, K in ch.saturation.items()]
            self._prod = (idx[ch.product], m0[ch.product])
            self._deg_mono = [(idx[s], v, m0[s]) for s, v in dg.monomers.items()]
            self._rc_terms = [(idx[s], v, m0[s]) for s, v in tr.stoich.items()]
            self._rc_sat = [(idx[s], K) for s, K in tr.saturation.items()]
            self._draw_rows = [(idx[s], v) for s, v in ch.draws.items()]
            self._release_rows = [(idx[s], v) for s, v in ch.releases.items()]
            self._mono_rows = [(idx[s], v * dg.residues) for s, v in dg.monomers.items()]
            self._rc_rows = [(idx[s], v) for s, v in tr.stoich.items()]
            self._iF = self.pos[f"F.{self.pool_id}"]
            self._iC = self.pos[f"C.{ch.route}.1"]
            self._gene_N = (tr.stoich.get("N", 0.0),
                            (ch.releases.get("N", 0.0) - ch.draws.get("N", 0.0)) * ch.per_stage)
        self._rx = []
        for rx in self.reactions:
            m0 = {s: self.net_mu[s] - math.log(self.net_c0) for s in rx.nu}
            self._rx.append((
                rx,
                [(idx[s], a) for s, a in rx.reactants.items()],
                [(idx[s], b) for s, b in rx.products.items()],
                [(idx[s], v, m0[s]) for s, v in rx.nu.items()],
                math.exp(sum(v * self.net_mu[s] for s, v in rx.nu.items())),
            ))
        self._iV = self.pos.get("V")

    def y0(self) -> np.ndarray:
        y = list(self.n0)
        if self.gene:
            y.append(self.machines_total)
            y += [0.0] * self.chain.stages
        if self.water:
            y.append(self.V0)
        y += [0.0] * len(self.acc_names)
        return np.array(y, dtype=float)

    # ------------------------------------------------------------------ rates
    def fluxes(self, y) -> dict:
        """Every flux, affinity and rate at state y (amounts in fmol, V in pL); rates of the
        amounts in 'dn', of the free machines and complexes in 'dF' and 'dC', of the volume in
        'dV', and of every book in 'acc'."""
        ns = len(self.species)
        n = [float(v) for v in y[:ns]]
        V = float(y[self._iV]) if self.water else self.V0
        lnV = math.log(V)
        RT = self.RT_pJ
        out = {"V": V}
        dn = [0.0] * ns
        acc = {}
        if self.gene:
            ch, dg, tr = self.chain, self.degradation, self.transfer
            r = ch.per_stage
            Fq = float(y[self._iF])
            C = [float(c) for c in y[self._iC:self._iC + ch.stages]]
            # 4.1 initiation: J_I = u k_I c_T F, c_T = T c1, c1 = 1e15/(N_A V) mM; u = 1 (no factor)
            J_I = ch.k_init * ch.copies * (1e15 / (N_AVOGADRO * V)) * Fq
            # 4.2 elongation: J_j = kappa C_j phi; phi = prod_d c_d/(K_d + c_d) (1 - e^x),
            # x = dG_tx/RT = mu°_res/RT + sum releases nu mu/RT - sum draws nu mu/RT (3.4)
            x = self._mu_res
            for i, v, m0 in self._tx_terms:
                x += v * (m0 + _log(n[i]) - lnV)
            sat = 1.0
            for i, K in self._tx_sat:
                c = n[i] / V
                sat *= c / (K + c)
            phi = sat * -math.expm1(x)
            kappa = ch.speed / r
            J = [kappa * c * phi for c in C]
            S = sum(J)
            Q = J[-1]
            # 3.4 release: dG_rel = mu_R - L mu°_res = RT ln a_R
            ip, m0p = self._prod
            mu_prod = m0p + _log(n[ip]) - lnV
            dG_rel = mu_prod - ch.residues * self._mu_res
            # 4.4 degradation: D = k_s n_R (1 - e^(dG_deg/(L RT))), dG_deg = L sum mono mu - mu_R
            dG_deg = -mu_prod
            for i, v, m0 in self._deg_mono:
                dG_deg += dg.residues * v * (m0 + _log(n[i]) - lnV)
            D = dg.rate * n[ip] * -math.expm1(dG_deg / dg.residues)
            # 4.5 recharging: J_C = V V_C prod sat (1 - e^(dG_rc/(share RT)))
            dG_rc = 0.0
            for i, v, m0 in self._rc_terms:
                dG_rc += v * (m0 + _log(n[i]) - lnV)
            satc = 1.0
            for i, K in self._rc_sat:
                c = n[i] / V
                satc *= c / (K + c)
            J_C = V * tr.capacity * satc * -math.expm1(dG_rc / tr.share)
            # 4.7 equations of motion: rows, machines and complexes
            for i, v in self._draw_rows:
                dn[i] -= v * r * S
            for i, v in self._release_rows:
                dn[i] += v * r * S
            dn[ip] += Q - D
            for i, v in self._mono_rows:
                dn[i] += v * D
            for i, v in self._rc_rows:
                dn[i] += v * J_C
            dC = [J_I - J[0]] + [J[j - 1] - J[j] for j in range(1, ch.stages)]
            # 3.4 heat classes (pJ/s): every stage exit books r (-dG_tx), the last also -dG_rel
            acc.update({
                "ext.init": J_I, "ext.exits": S, "ext.rel": Q, "ext.deg": D, "ext.rc": J_C,
                "H.tx": RT * (r * S * -x + Q * -dG_rel),
                "H.deg": RT * D * -dG_deg,
                "H.rc": RT * J_C * -dG_rc,
            })
            out.update(J_I=J_I, J=J, S=S, Q=Q, D=D, J_C=J_C, x_tx=x, dG_rc=dG_rc,
                       dG_deg=dG_deg, dG_rel=dG_rel, phi=phi, dF=Q - J_I, dC=dC,
                       gene_rate_N=self._gene_N[0] * J_C + self._gene_N[1] * S)
        net_rate = {}
        net_rate_N = 0.0
        for rx, reac, prod, terms, keq_inv in self._rx:
            if rx.law == DRIVEN:  # J = m k V prod c^alpha
                Jr = rx.multiplier * rx.k * V
                for i, a in reac:
                    Jr *= (n[i] / V) ** a
            else:  # J = m V c0 k_f [prod a^alpha - exp(sum nu mu°/RT) prod a^beta]
                c0 = self.net_c0
                fwd = 1.0
                for i, a in reac:
                    fwd *= (n[i] / (V * c0)) ** a
                bwd = keq_inv
                for i, b in prod:
                    bwd *= (n[i] / (V * c0)) ** b
                Jr = rx.multiplier * V * c0 * rx.k * (fwd - bwd)
            # dG_r/RT = sum nu (mu°/RT + ln(c/c0)), the network's potentials at its own c0
            dGr = 0.0
            for i, v, m0 in terms:
                dGr += v * (m0 + _log(n[i]) - lnV)
                dn[i] += v * Jr
            net_rate[rx.rid] = Jr
            net_rate_N += rx.nu.get("N", 0.0) * Jr
            acc[f"ext.net.{rx.rid}"] = Jr
            acc[f"dG.net.{rx.rid}"] = Jr * dGr * RT  # pJ/s
            out[f"dG_RT.net.{rx.rid}"] = dGr
        out["net_rate"] = net_rate
        out["network_rate_N"] = net_rate_N
        if self.water:
            w = self.water
            Pi = self.RT_J * (sum(n) + w.n_imp) / V  # Pa (fmol/pL = mol/m^3)
            P = w.bulk_modulus * (V / w.v_ref - 1.0) + w.p0
            psi = P - Pi
            Qw = 1e15 * w.area * w.lp * w.availability * (psi - w.psi_out)  # pL/s, cell -> out
            acc["H.water"] = 1e-3 * Qw * (psi - w.psi_out)
            acc["W.bath"] = 1e-3 * w.psi_out * -Qw  # the bath's supply to the cell is -Q
            out.update(Pi=Pi, P=P, psi=psi, Qw=Qw, dV=-Qw)
        out["dn"] = dn
        out["acc"] = acc
        return out

    def rhs(self, t, y):
        f = self.fluxes(y)
        dy = f["dn"]
        if self.gene:
            dy.append(f["dF"])
            dy += f["dC"]
        if self.water:
            dy.append(f["dV"])
        acc = f["acc"]
        dy += [acc[nm] for nm in self.acc_names]
        return np.array(dy, dtype=float)

    def recharge_flux(self, t, y) -> float:
        return self.fluxes(y)["J_C"]

    # ------------------------------------------------------------------ energies
    def f_linear_terms(self) -> dict[str, float]:
        """(mu°_s/RT - ln c0) per row for F (READOUTS.md, amended): the registry's where it
        declares the row, else the network's at its own c0, else 0 (mu° = 0 at c0 = 1 mM)."""
        terms = {}
        for s in self.species:
            if s in self.registry_mu:
                terms[s] = self.registry_mu[s] - math.log(float(self.registry_c0))
            elif s in self.net_mu:
                terms[s] = self.net_mu[s] - math.log(self.net_c0)
            else:
                terms[s] = 0.0
        return terms

    def free_energy(self, y) -> float:
        """F(N, V) = sum_s RT n_s (ln(n_s/V) - 1) + RT (mu°_s/RT - ln c0) n_s over the cell's
        species rows only (pJ)."""
        V = float(y[self._iV]) if self.water else self.V0
        lin = self.f_linear_terms()
        F = 0.0
        for i, s in enumerate(self.species):
            ns = float(y[i])
            F += self.RT_pJ * ns * (math.log(ns / V) - 1.0 + lin[s])
        return F

    def elastic_energy(self, y) -> float:
        """U(V) = integral of P dV from V_ref (pJ): 1e-3 [K (V-Vr)^2/(2 Vr) + P0 (V-Vr)]."""
        if not self.water:
            return 0.0
        w = self.water
        V = float(y[self._iV])
        return 1e-3 * (w.bulk_modulus * (V - w.v_ref) ** 2 / (2.0 * w.v_ref) + w.p0 * (V - w.v_ref))

    def residues_in_transit(self, y) -> float:
        """W = r sum_j (j - 1) C_j (fmol of residues)."""
        ch = self.chain
        return ch.per_stage * sum(j * float(y[self._iC + j]) for j in range(ch.stages))

    def transit_free_energy(self, y) -> float:
        """Section 3.4's mu°_res W (pJ), which F leaves out: residues in transit carry their
        per-residue potential and no concentration term."""
        if not self.gene:
            return 0.0
        return self.RT_pJ * self._mu_res * self.residues_in_transit(y)


# ---------------------------------------------------------------------- integration
ATOL_AMOUNT = 1e-30  # fmol (amounts, machines, complexes, extents) and pL (volume)
ATOL_ENERGY = 1e-20  # pJ (heats and works)


def default_atol(world: World) -> np.ndarray:
    """Absolute tolerances far below every component's own scale, so that the relative tolerance
    governs every component, the trace ones included.

    The heat and work books get a floor of 1e-20 pJ instead of 1e-30: an integrand such as
    J dG starts at exactly 0 where a route starts at equilibrium (X -> N with N = X and equal
    potentials), and its last-digit roundoff (about 1e-18 pJ/s) would otherwise pin the step."""
    return np.array([ATOL_ENERGY if nm.startswith(("H.", "W.", "dG.")) else ATOL_AMOUNT
                     for nm in world.names])


def _segments(world, bounds, y, method, rtol, atol, events=None, **kw):
    states, roots, nfev, steps = [y.copy()], [], 0, 0
    for t0, t1 in zip(bounds[:-1], bounds[1:]):
        sol = solve_ivp(world.rhs, (t0, t1), y, method=method, rtol=rtol, atol=atol,
                        events=events, **kw)
        if not sol.success:
            raise RuntimeError(f"{method} failed on [{t0}, {t1}]: {sol.message}")
        y = sol.y[:, -1].copy()
        states.append(y.copy())
        nfev += sol.nfev
        steps += len(sol.t) - 1
        if events is not None:
            roots += [float(t) for t in sol.t_events[0] if t0 < t < t1]
    return states, roots, nfev, steps


def integrate(world: World, times, method="Radau", rtol=1e-11, atol=None, **kw):
    """Integrate segment by segment, so every reported time is a step end (no dense output).

    With a gene unit, recharging's books are split by the sign of J_C (READOUTS.md, amended).
    Pass 1 locates every sign change of J_C; pass 2 integrates again with those times as further
    step ends, so between consecutive ends J_C keeps one sign and each increment of the smooth
    integral of J_C goes whole to production (J_C > 0) or to consumption (J_C < 0)."""
    times = [float(t) for t in times]
    atol = default_atol(world) if atol is None else atol
    y0 = world.y0()
    info = {"method": method, "rtol": rtol}
    if not world.gene:
        states, _, nfev, steps = _segments(world, times, y0, method, rtol, atol, **kw)
        info.update(nfev=nfev, steps=steps)
        return np.array(states), info
    event = world.recharge_flux
    _, roots, nfev1, steps1 = _segments(world, times, y0, method, rtol, atol, events=[event], **kw)
    bounds = sorted(set(times) | set(roots))
    states, _, nfev2, steps2 = _segments(world, bounds, y0, method, rtol, atol, **kw)
    # walk the ends: J_C's sign on each interval is its sign at t = 0, flipped at every root
    sign0 = 1.0 if world.recharge_flux(0.0, y0) > 0 else -1.0
    i_rc = world.pos["ext.rc"]
    pos_acc, neg_acc = [0.0], [0.0]
    for k in range(1, len(bounds)):
        flips = sum(1 for rt in roots if rt <= bounds[k - 1])
        sign = sign0 * (-1.0) ** flips
        inc = float(states[k][i_rc] - states[k - 1][i_rc])
        pos_acc.append(pos_acc[-1] + (inc if sign > 0 else 0.0))
        neg_acc.append(neg_acc[-1] + (-inc if sign < 0 else 0.0))
    keep = [bounds.index(t) for t in times]
    info.update(nfev=nfev1 + nfev2, steps=steps2, recharge_sign_changes_s=roots,
                rc_produced=[pos_acc[k] for k in keep], rc_consumed=[neg_acc[k] for k in keep])
    return np.array([states[k] for k in keep]), info


# ---------------------------------------------------------------------- readouts
def readouts(world: World, times, Y, info) -> dict[str, list[float]]:
    """READOUTS.md's quantities (names and units as given there) at each time."""
    pos = world.pos
    ro: dict[str, list[float]] = {}

    def put(name, val):
        ro.setdefault(name, []).append(float(val))

    for k, y in enumerate(Y):
        f = world.fluxes(y)
        for i, s in enumerate(world.species):
            put(f"amount_fmol.{s}", y[i])
        if world.gene:
            ch = world.chain
            # transcription's books by process, signed; recharging's split by J_C's sign
            put("gene_produced_N_fmol", info["rc_produced"][k])
            put("gene_consumed_N_fmol", ch.per_stage * y[pos["ext.exits"]] + info["rc_consumed"][k])
        if any("N" in rx.nu for rx in world.reactions):
            n_prod = sum(rx.nu["N"] * y[pos[f"ext.net.{rx.rid}"]]
                         for rx in world.reactions if rx.nu.get("N", 0.0) > 0)
            n_cons = sum(-rx.nu["N"] * y[pos[f"ext.net.{rx.rid}"]]
                         for rx in world.reactions if rx.nu.get("N", 0.0) < 0)
            put("network_produced_N_fmol", n_prod)
            put("network_consumed_N_fmol", n_cons)
        if world.gene:
            put("gene_rate_N_fmol_per_s", f["gene_rate_N"])
        if any("N" in rx.nu for rx in world.reactions):
            put("network_rate_N_fmol_per_s", f["network_rate_N"])
        if len(world.reactions) == 1:
            put("network_route_rate_fmol_per_s", f["net_rate"][world.reactions[0].rid])
        if world.gene:
            ch = world.chain
            put(f"gene_state.free_machines.{world.pool_id}", y[world._iF])
            for j in range(1, ch.stages + 1):
                put(f"gene_state.complexes.{ch.route}.stage_{j}", y[world._iC + j - 1])
            put(f"gene_state.engaged.{ch.route}", sum(y[world._iC:world._iC + ch.stages]))
            put(f"gene_state.residues_in_transit.{ch.route}", world.residues_in_transit(y))
            put(f"gene_state.initiations.{ch.route}", y[pos["ext.init"]])
            put(f"gene_state.stage_exits.{ch.route}", y[pos["ext.exits"]])
            put(f"gene_state.releases.{ch.route}", y[pos["ext.rel"]])
            put(f"gene_state.degradations.{world.degradation.route}", y[pos["ext.deg"]])
            put(f"gene_state.turnovers.{world.transfer.route}", y[pos["ext.rc"]])
        if world.water:
            put("volume_pL", y[pos["V"]])
            put("free_energy_pJ", world.free_energy(y))
            put("elastic_energy_pJ", world.elastic_energy(y))
            put("water_heat_pJ", y[pos["H.water"]])
            put("bath_water_work_pJ", y[pos["W.bath"]])
            put("network_heat_pJ", network_heat(world, y))
            put("network_work_pJ", network_work(world, y))
            if world.gene:
                put("gene_heat_pJ", y[pos["H.tx"]] + y[pos["H.deg"]] + y[pos["H.rc"]])
    return ro


def network_heat(world: World, y) -> float:
    """A passive route books heat -dG of its moves; a driven route books none (LAWS.md)."""
    return sum(-y[world.pos[f"dG.net.{rx.rid}"]] for rx in world.reactions if rx.law == PASSIVE)


def network_work(world: World, y) -> float:
    """A driven route books work dG of its moves; a passive route books none (LAWS.md)."""
    return sum(y[world.pos[f"dG.net.{rx.rid}"]] for rx in world.reactions if rx.law == DRIVEN)


def checks(world: World, Y, info) -> dict[str, float]:
    """The identities, as the largest residual over the reported rows (absolute, in the unit of
    the quantity, and relative to its scale where one exists)."""
    pos = world.pos
    y0 = Y[0]
    out = {}
    if world.gene:
        ch = world.chain
        iN = world.idx["N"]
        # C2.2's identity: n_N(t) = n_N(0) + the gene unit's net books + the network's net books
        net = [sum(rx.nu.get("N", 0.0) * y[pos[f"ext.net.{rx.rid}"]] for rx in world.reactions)
               for y in Y]
        gene = [info["rc_produced"][k] - ch.per_stage * Y[k][pos["ext.exits"]]
                - info["rc_consumed"][k] for k in range(len(Y))]
        out["N_books_identity_fmol"] = max(abs(Y[k][iN] - y0[iN] - gene[k] - net[k])
                                           for k in range(len(Y)))
        out["recharging_split_vs_signed_integral_fmol"] = max(
            abs(info["rc_produced"][k] - info["rc_consumed"][k] - Y[k][pos["ext.rc"]])
            for k in range(len(Y)))
        out["machines_identity_fmol"] = max(
            abs(y[world._iF] + sum(y[world._iC:world._iC + ch.stages]) - world.machines_total)
            for y in Y)
        out["residues_identity_fmol"] = max(
            abs(ch.per_stage * y[pos["ext.exits"]] - world.residues_in_transit(y)
                - ch.residues * y[pos["ext.rel"]]) for y in Y)
        ip = world.idx[ch.product]
        out["products_identity_fmol"] = max(
            abs(y[ip] - y0[ip] - y[pos["ext.rel"]] + y[pos["ext.deg"]]) for y in Y)
        for mid, w in world.moieties.items():
            w_res = w.get(ch.product, 0.0) / ch.residues

            def total(y):
                return (sum(w.get(s, 0.0) * y[i] for i, s in enumerate(world.species))
                        + w_res * world.residues_in_transit(y))
            out[f"moiety_{mid}_identity_fmol"] = max(abs(total(y) - total(y0)) for y in Y)
    # the energy identity: d(F + U + G_transit) = works - heats, over every process
    rows = []
    for y in Y:
        dF = (world.free_energy(y) + world.elastic_energy(y) + world.transit_free_energy(y)
              - world.free_energy(y0) - world.elastic_energy(y0) - world.transit_free_energy(y0))
        work = network_work(world, y) + (y[pos["W.bath"]] if world.water else 0.0)
        heat = network_heat(world, y) + (y[pos["H.water"]] if world.water else 0.0)
        if world.gene:
            heat += y[pos["H.tx"]] + y[pos["H.deg"]] + y[pos["H.rc"]]
        rows.append((dF - (work - heat), abs(dF) + abs(work) + abs(heat)))
    scale = max(s for _, s in rows)
    out["energy_identity_pJ"] = max(abs(r) for r, _ in rows)
    out["energy_identity_relative_to_scale"] = out["energy_identity_pJ"] / scale if scale else 0.0
    return out


def compare(a: dict, b: dict) -> dict[str, dict[str, float]]:
    """Per quantity: e = max_i |a_i - b_i| / max_i |b_i| (CRITERIA.md's normalisation), and the
    largest pointwise relative difference |a_i - b_i| / |b_i| over nonzero b_i."""
    out = {}
    for k in b:
        x = np.asarray(a[k], dtype=float)
        z = np.asarray(b[k], dtype=float)
        scale = float(np.max(np.abs(z)))
        d = np.abs(x - z)
        e = float(np.max(d) / scale) if scale > 0 else float(np.max(d))
        nz = np.abs(z) > 0
        pw = float(np.max(d[nz] / np.abs(z[nz]))) if nz.any() else 0.0
        out[k] = {"e_max_normalised": e, "max_pointwise_relative": pw, "max_abs": float(np.max(d))}
    return out
