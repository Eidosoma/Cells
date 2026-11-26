"""R-cell and R-feedback: constant-field cells with regulated availabilities, an independent
reference for cells.operator.species_regulated_availability@1.

Written from docs/INVENTORY_COUPLING_DESIGN.md Appendix A.5 (with §4.3) and S5's Appendix A.1-A.3
(docs/CELL_DIVISION_S5_DESIGN.md), in the style and state layout of R-tissue
(validation/division/cleft_tissue_reference.py, read as a reference, not engine code). It was
written without reading the operator or its tests. It imports R-full's constant-field flux law
(validation/division/cleft_egg_reference.ghk_flux, qualified at S3, as R-tissue does) and
nothing else from validation.division: no J1 input, no partition (the J2 bright line, S5 §10.1).
numpy and scipy otherwise.

The world (pump-free; SI units, amounts in fmol, volumes in pL, so n/V is in mM = mol/m^3):
* species s with valence z_s (S5's worlds: Na +1, K +1, Cl -1). The constants F (C/mol) and
  R (J/(mol K)) and the temperature T are inputs, never module constants.
* cells i: a declared volume V_i (pL), amounts n_si (fmol) and a fixed background X_i (fmol of
  charge equivalent). The node charge is Q_i = 1e-15 F (sum_s z_s n_si + X_i).
* the held bath: potential 0, composition c_sb fixed; it supplies whatever it exchanges.
* patches k of cell i, all facing the bath (capacitance C_k, area A_k, leak permeabilities P_ks
  per unit area). The capacitor graph is then diagonal: phi_i = Q_i / sum_k C_k (S5 A.2).
* channel populations p on patch k (A.5): one more constant-field route per species, with P_ks A_k
  replaced by P r_s N o a_p(t) A_k (permeability P, relative permeability r_s, abundance N,
  opening o, 1 for a gate-free law such as cells.channel.kleak_always_open@1, and availability a_p(t)).
* contacts e between cells a(e) (first) and b(e) (second): J_es = P_es A_e g a_e(t) psi(x)
  (c_s,a - c_s,b e^(-x)), x = z_s F (phi_a - phi_b)/(R T), with a fixed gate g.
* every route: J = PA psi(x) (c_in - c_out e^(-x)), psi(x) = x/(1 - e^(-x)) (S5 A.3), outward
  (or first to second) positive, in mol/s.
* availabilities (A.2): a(t) = a_sched(t) * prod_r F_r(t) over the couplings targeting the
  element, in declared order; a_sched is a piecewise-constant schedule; F_r = b + (1 - b) f (R-fac),
  1 while the coupling is switched off; a contact route's side reads its first cell, its second
  cell, or both (the product).
* sources: a regulatory state of the cell (state_fraction, state_complement), or a species of the
  cell through a Hill law. A regulator is a neutral, impermeant species with closed-form turnover
  (R-state's Turnover): it enters neither the electrostatics nor the transport (A.5). An ion read
  by a Hill coupling is the true instantaneous coupling, which the engine refuses (ruling 1); it
  is admitted here as a limit only.
* regulatory states (A.3): ds/dt = k_on u (1 - s) - k_off s, u = prod_j f_j(c_j) of the cell's
  ions or regulators, integrated with the ions (R-feedback), with the exposure dU/dt = u.

State layout (R-tissue's): per cell, the charge Q/(1e-15 F) in fmol and the amounts of every
species but the last charged one (the follower, recovered from the charge, so V keeps its digits);
then (s, U) per (state, cell); then the cumulative bath-to-tissue exchange per species (fmol).
Integration: scipy's Radau at rtol 1e-10 (R-tissue's setting), with absolute tolerances per state
kind, segment by segment between breakpoints at every record, schedule change, switch change and
regulator segment start (piecewise_ode). Records are integration end points, never dense output.

Sources: Goldman DE. J Gen Physiol 1943;27:37-60; Hodgkin AL, Katz B. J Physiol 1949;108:37-77
(the constant-field flux); Keener J, Sneyd J. Mathematical Physiology I, 2nd ed., Springer 2009;
Hille B. Ion Channels of Excitable Membranes, 3rd ed., Sinauer 2001.
"""

import math
import time
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import brentq

from validation.coupling import factor_reference as fr
from validation.coupling import piecewise_ode
from validation.coupling import state_reference as rs
from validation.division.cleft_egg_reference import ghk_flux  # R-full's law (S3-qualified)

FMOL = 1e-15  # mol per fmol
# Absolute tolerances per state kind, for cells of tissue scale (node charges of order 1e-3 fmol):
# R-tissue's SMALL values for the charge and the amounts.
ATOL = dict(charge=1e-15, amount=1e-12, state=1e-14, exposure=1e-12, exchange=1e-12)


# ---------------------------------------------------------------- the world


@dataclass(frozen=True)
class Constants:
    faraday_C_per_mol: float
    gas_J_per_mol_K: float
    temperature_K: float

    @property
    def rt(self):
        return self.gas_J_per_mol_K * self.temperature_K


@dataclass(frozen=True)
class Cell:
    """A cell: volume (pL) and initial concentrations (mM, every species). Its start: give
    initial_V (V) or background_fmol (X); with neither, the zero-current potential of its routes
    to the bath (leaks and populations at their availability at 0+, contacts excluded)."""

    volume_pL: float
    mM: tuple
    initial_V: float = math.nan
    background_fmol: float = math.nan


@dataclass(frozen=True)
class Patch:
    """A membrane patch of a cell, facing the bath, with constant-field leaks."""

    cell: str
    area_m2: float
    capacitance_F: float
    permeability_m_s: tuple  # leak P_s per unit area, every species


@dataclass(frozen=True)
class Population:
    """A gate-free channel population on a patch: P r_s N o a(t) A_k per species s."""

    patch: str
    permeability_m_s: float
    relative: tuple  # r_s, every species (cells.channel.kleak_always_open@1: 1 for K, 0 otherwise)
    abundance: float = 1.0
    opening: float = 1.0
    schedule: tuple = ((0.0, 1.0),)  # ((t_start_s, a_sched), ...), from 0, piecewise constant


@dataclass(frozen=True)
class Contact:
    """A junction between cells[0] (first, a(e)) and cells[1] (second, b(e))."""

    cells: tuple
    area_m2: float
    permeability_m_s: tuple  # P_s per unit area, every species
    gate: float = 1.0
    schedule: tuple = ((0.0, 1.0),)


@dataclass(frozen=True)
class Regulator:
    """A neutral, impermeant species with closed-form turnover in each cell that declares it:
    {cell: state_reference.Turnover}, each Turnover at that cell's volume."""

    amounts: dict


@dataclass(frozen=True)
class Input:
    """A Hill input of a regulatory state: law, the species or regulator read in the state's
    cell, K (mM) and n."""

    law: str
    species: str
    K_mM: float
    n: float


@dataclass(frozen=True)
class State:
    """A regulatory state (hill_regulated_two_state) in each of its cells."""

    cells: tuple
    inputs: tuple
    k_on_per_s: float
    k_off_per_s: float
    initial: object = 0.0  # s0: one value, or {cell: s0}
    crossing_level: float = math.nan


@dataclass(frozen=True)
class Coupling:
    """A factor on one element (a population or a contact) from one source."""

    target: str
    law: str
    source: str  # a state (state laws) or a species or regulator (Hill laws)
    basal: float = 0.0
    K_mM: float = math.nan
    n: float = math.nan
    side: object = None  # contacts: "first", "second" or "both"; populations: None
    enabled: tuple = ((0.0, 1),)  # ((t_start_s, 0 or 1), ...), from 0


@dataclass(frozen=True)
class World:
    constants: Constants
    species: tuple
    z: tuple
    bath_mM: tuple
    cells: dict
    patches: dict
    populations: dict = field(default_factory=dict)
    contacts: dict = field(default_factory=dict)
    regulators: dict = field(default_factory=dict)
    states: dict = field(default_factory=dict)
    couplings: dict = field(default_factory=dict)  # declared order = insertion order


def _finite(x):
    return isinstance(x, (int, float)) and math.isfinite(x)


def _check_schedule(name, schedule, values=None):
    starts = [a for a, _ in schedule]
    if not schedule or starts[0] != 0.0 or starts != sorted(set(starts)):
        raise ValueError(f"{name}: a schedule starts at 0 and strictly increases")
    for _, v in schedule:
        if values is not None and v not in values:
            raise ValueError(f"{name}: schedule values are {values}")
        if not (_finite(v) and 0.0 <= v <= 1.0):
            raise ValueError(f"{name}: schedule values lie in [0, 1]")


def schedule_value(schedule, t0, t1):
    """The piecewise-constant value on (t0, t1) (segments never straddle a change)."""
    mid = 0.5 * (t0 + t1)
    value = schedule[0][1]
    for start, v in schedule:
        if start > mid:
            break
        value = v
    return value


def initial_states(state, cells):
    if isinstance(state.initial, dict):
        if set(state.initial) != set(cells):
            raise ValueError("a per-cell initial value covers exactly the state's cells")
        return {c: float(state.initial[c]) for c in cells}
    return {c: float(state.initial) for c in cells}


def check_world(w):
    """Refuse an inadmissible world (the reference's own domain)."""
    c = w.constants
    if not all(_finite(x) and x > 0 for x in (c.faraday_C_per_mol, c.gas_J_per_mol_K,
                                               c.temperature_K)):
        raise ValueError("F, R and T are finite and > 0")
    ns = len(w.species)
    if len(w.z) != ns or len(set(w.species)) != ns or not any(w.z):
        raise ValueError("unique species, one valence each, at least one charged")
    if len(w.bath_mM) != ns or not all(_finite(x) and x > 0 for x in w.bath_mM):
        raise ValueError("the bath declares a positive concentration of every species")
    for name, cell in w.cells.items():
        if not (_finite(cell.volume_pL) and cell.volume_pL > 0) or len(cell.mM) != ns:
            raise ValueError(f"cell {name}: a positive volume and every species' concentration")
        if not all(_finite(x) and x > 0 for x in cell.mM):
            raise ValueError(f"cell {name}: concentrations are positive")
        if math.isfinite(cell.initial_V) and math.isfinite(cell.background_fmol):
            raise ValueError(f"cell {name}: give initial_V or background_fmol, not both")
    for name, p in w.patches.items():
        if p.cell not in w.cells:
            raise ValueError(f"patch {name}: no cell {p.cell}")
        if not (_finite(p.area_m2) and p.area_m2 > 0 and _finite(p.capacitance_F)
                and p.capacitance_F > 0):
            raise ValueError(f"patch {name}: a positive area and capacitance")
        if len(p.permeability_m_s) != ns or not all(_finite(x) and x >= 0
                                                     for x in p.permeability_m_s):
            raise ValueError(f"patch {name}: a non-negative permeability per species")
    for name in w.cells:
        if not any(p.cell == name for p in w.patches.values()):
            raise ValueError(f"cell {name} has no patch on the bath (a floating node)")
    for name, pop in w.populations.items():
        if pop.patch not in w.patches:
            raise ValueError(f"population {name}: no patch {pop.patch}")
        if not (_finite(pop.permeability_m_s) and pop.permeability_m_s >= 0):
            raise ValueError(f"population {name}: permeability")
        if len(pop.relative) != ns or not all(_finite(x) and x >= 0 for x in pop.relative):
            raise ValueError(f"population {name}: a non-negative relative permeability each")
        if not (_finite(pop.abundance) and pop.abundance >= 0 and _finite(pop.opening)
                and 0 <= pop.opening <= 1):
            raise ValueError(f"population {name}: abundance >= 0 and opening in [0, 1]")
        _check_schedule(f"population {name}", pop.schedule)
    names = [*w.patches, *w.populations, *w.contacts]
    if len(set(names)) != len(names):
        raise ValueError("patch, population and contact names are distinct")
    for name, e in w.contacts.items():
        if len(e.cells) != 2 or e.cells[0] == e.cells[1] or any(x not in w.cells for x in e.cells):
            raise ValueError(f"contact {name} joins two distinct cells")
        if not (_finite(e.area_m2) and e.area_m2 > 0 and _finite(e.gate) and 0 <= e.gate <= 1):
            raise ValueError(f"contact {name}: a positive area and a gate in [0, 1]")
        if len(e.permeability_m_s) != ns or not all(_finite(x) and x >= 0
                                                     for x in e.permeability_m_s):
            raise ValueError(f"contact {name}: a non-negative permeability per species")
        _check_schedule(f"contact {name}", e.schedule)
    for name, reg in w.regulators.items():
        if name in w.species:
            raise ValueError(f"regulator {name} is named like an ion species")
        for cell, turnover in reg.amounts.items():
            if cell not in w.cells:
                raise ValueError(f"regulator {name}: no cell {cell}")
            if turnover.volume_pL != w.cells[cell].volume_pL:
                raise ValueError(f"regulator {name} in {cell}: the Turnover's volume is the cell's")

    def present(source, cell):
        return source in w.species or (source in w.regulators
                                       and cell in w.regulators[source].amounts)

    for name, st in w.states.items():
        if not st.cells or len(set(st.cells)) != len(st.cells) or any(c not in w.cells
                                                                       for c in st.cells):
            raise ValueError(f"state {name}: distinct declared cells")
        if not st.inputs:
            raise ValueError(f"state {name}: at least one input")
        for inp in st.inputs:
            if inp.law not in fr.HILL_LAWS:
                raise ValueError(f"state {name}: input laws are {fr.HILL_LAWS}")
            if not (_finite(inp.K_mM) and inp.K_mM > 0 and _finite(inp.n) and inp.n > 0):
                raise ValueError(f"state {name}: K > 0 and n > 0")
            if any(not present(inp.species, c) for c in st.cells):
                raise ValueError(f"state {name}: {inp.species} is not declared in every cell")
        if not all(_finite(r) and r >= 0 for r in (st.k_on_per_s, st.k_off_per_s)):
            raise ValueError(f"state {name}: rates are finite and >= 0")
        if not all(0.0 <= v <= 1.0 for v in initial_states(st, st.cells).values()):
            raise ValueError(f"state {name}: initial values lie in [0, 1]")
        theta = st.crossing_level
        if not (math.isnan(theta) or 0.0 <= theta <= 1.0):
            raise ValueError(f"state {name}: the crossing level lies in [0, 1]")
    for name, cp in w.couplings.items():
        if cp.target not in w.populations and cp.target not in w.contacts:
            raise ValueError(f"coupling {name}: no population or contact {cp.target}")
        if cp.law not in fr.LAWS:
            raise ValueError(f"coupling {name}: law is one of {fr.LAWS}")
        if not (_finite(cp.basal) and 0.0 <= cp.basal < 1.0):
            raise ValueError(f"coupling {name}: the basal level lies in [0, 1)")
        if cp.target in w.populations:
            if cp.side is not None:
                raise ValueError(f"coupling {name}: a population target has no side")
            cells = (w.patches[w.populations[cp.target].patch].cell,)
        else:
            if cp.side not in fr.SIDES:
                raise ValueError(f"coupling {name}: a contact side is one of {fr.SIDES}")
            first, second = w.contacts[cp.target].cells
            cells = {"first": (first,), "second": (second,), "both": (first, second)}[cp.side]
        if cp.law in fr.STATE_LAWS:
            if cp.source not in w.states:
                raise ValueError(f"coupling {name}: a state law reads a declared state")
            if any(c not in w.states[cp.source].cells for c in cells):
                raise ValueError(f"coupling {name}: state {cp.source} is not in a cell it reads")
        else:
            if not (_finite(cp.K_mM) and cp.K_mM > 0 and _finite(cp.n) and cp.n > 0):
                raise ValueError(f"coupling {name}: K > 0 and n > 0")
            if any(not present(cp.source, c) for c in cells):
                raise ValueError(f"coupling {name}: {cp.source} is not declared in a cell it reads")
        _check_schedule(f"coupling {name}", cp.enabled, values=(0, 1))


# ---------------------------------------------------------------- the model


class _Model:
    """Index tables and the right-hand side of one world (one code path for the integrator and
    the records)."""

    def __init__(self, w, atol):
        self.w = w
        self.F = w.constants.faraday_C_per_mol
        self.rt = w.constants.rt
        self.z = tuple(w.z)
        self.ns = len(self.z)
        self.follower = max(i for i, x in enumerate(self.z) if x != 0)
        self.others = [i for i in range(self.ns) if i != self.follower]
        self.cells = list(w.cells)
        self.ci = {c: i for i, c in enumerate(self.cells)}
        self.block = 1 + len(self.others)
        self.volume = [w.cells[c].volume_pL for c in self.cells]
        self.capacitance = [math.fsum(p.capacitance_F for p in w.patches.values() if p.cell == c)
                            for c in self.cells]
        self.sidx = {s: k for k, s in enumerate(w.species)}
        self.regs = [(r, c) for r, reg in w.regulators.items() for c in reg.amounts]
        self.ri = {pair: j for j, pair in enumerate(self.regs)}
        self.turnovers = [w.regulators[r].amounts[c] for r, c in self.regs]
        self.pairs = [(s, c) for s, st in w.states.items() for c in st.cells]
        self.pi = {pair: i for i, pair in enumerate(self.pairs)}
        self.pair_specs = []  # (k_on, k_off, [(law, source, K, n)])
        for st, c in self.pairs:
            spec = w.states[st]
            inputs = [(inp.law, self._source(inp.species, c), inp.K_mM, inp.n)
                      for inp in spec.inputs]
            self.pair_specs.append((spec.k_on_per_s, spec.k_off_per_s, inputs))
        self.elements = [*w.populations, *w.contacts]
        self.ei = {e: i for i, e in enumerate(self.elements)}
        self.coupling_names = list(w.couplings)
        self.routes = [[] for _ in self.elements]  # per element: [(coupling index, sides)]
        for j, cp in enumerate(w.couplings.values()):
            if cp.target in w.populations:
                cells = (w.patches[w.populations[cp.target].patch].cell,)
            else:
                first, second = w.contacts[cp.target].cells
                cells = {"first": (first,), "second": (second,), "both": (first, second)}[cp.side]
            if cp.law in fr.STATE_LAWS:
                sides = [("state", self.pi[(cp.source, c)]) for c in cells]
            else:
                sides = [("hill", self._source(cp.source, c)) for c in cells]
            self.routes[self.ei[cp.target]].append((j, cp.law, cp.basal, cp.K_mM, cp.n, sides))
        self.patch_table = [(self.ci[p.cell], [p.permeability_m_s[k] * p.area_m2
                                               for k in range(self.ns)])
                            for p in w.patches.values()]
        self.population_table = []
        for name, pop in w.populations.items():
            patch = w.patches[pop.patch]
            scale = pop.permeability_m_s * pop.abundance * pop.opening * patch.area_m2
            self.population_table.append((self.ci[patch.cell], self.ei[name],
                                          [scale * pop.relative[k] for k in range(self.ns)]))
        self.contact_table = []
        for name, e in w.contacts.items():
            scale = e.area_m2 * e.gate
            self.contact_table.append((self.ci[e.cells[0]], self.ci[e.cells[1]], self.ei[name],
                                       [scale * e.permeability_m_s[k] for k in range(self.ns)]))
        self.state_base = len(self.cells) * self.block
        self.exchange_base = self.state_base + 2 * len(self.pairs)
        self.size = self.exchange_base + self.ns
        kinds = (["charge"] + ["amount"] * len(self.others)) * len(self.cells)
        kinds += ["state", "exposure"] * len(self.pairs) + ["exchange"] * self.ns
        self.atol = np.array([atol[k] for k in kinds])
        self.background = [0.0] * len(self.cells)

    def _source(self, source, cell):
        """("ion", cell index, species index) or ("regulator", index)."""
        if source in self.sidx:
            return ("ion", self.ci[cell], self.sidx[source])
        return ("regulator", self.ri[(source, cell)], None)

    # -- piecewise constants
    def controls(self, t0, t1):
        """On (t0, t1): a_sched per element and enabled per coupling, in table order."""
        w = self.w
        sched = [schedule_value((w.populations.get(e) or w.contacts[e]).schedule, t0, t1)
                 for e in self.elements]
        enabled = [bool(schedule_value(cp.enabled, t0, t1)) for cp in w.couplings.values()]
        return sched, enabled

    # -- the core
    def unpack(self, y):
        """(charges in fmol, amounts [cell][species] fmol, concentrations mM, potentials V)."""
        m, z, f = self.block, self.z, self.follower
        charge, amounts, conc, phi = [], [], [], []
        for i in range(len(self.cells)):
            q = float(y[i * m])
            n = [0.0] * self.ns
            for j, s in enumerate(self.others):
                n[s] = float(y[i * m + 1 + j])
            n[f] = (q - self.background[i] - math.fsum(z[s] * n[s] for s in self.others)) / z[f]
            charge.append(q)
            amounts.append(n)
            conc.append([x / self.volume[i] for x in n])
            phi.append(q * FMOL * self.F / self.capacitance[i])
        return charge, amounts, conc, phi

    def _value(self, source, conc, regs):
        kind, a, b = source
        x = conc[a][b] if kind == "ion" else regs[a]
        if not (math.isfinite(x) and x >= 0.0):
            raise RuntimeError(f"a negative or non-finite source concentration {x}")
        return x

    def core(self, t, y, sched, enabled, conc_override=None, s_override=None):
        """Every intermediate at (t, y): (charge, amounts, conc, phi, regulators, s, u,
        route factors [(element, coupling index, F)], availabilities [(a_sched, G, a_eff)] and
        the route fluxes [(outward cell, inward cell or -1, element or None, [J_s mol/s])])."""
        charge, amounts, conc, phi = self.unpack(y)
        if conc_override is not None:
            conc = conc_override
        regs = [float(tv.concentration(t)) for tv in self.turnovers]
        sb = self.state_base
        s = [float(y[sb + 2 * j]) for j in range(len(self.pairs))]
        if s_override is not None:
            s = s_override
        u = []
        for _, _, inputs in self.pair_specs:
            value = 1.0
            for law, source, K, n in inputs:
                value = value * fr.hill_scalar(law, self._value(source, conc, regs), K, n)
            u.append(value)
        factors, avail = [], []
        for e, routes in enumerate(self.routes):
            g = 1.0
            for j, law, basal, K, n, sides in routes:
                if not enabled[j]:
                    value = 1.0
                else:
                    value = 1.0
                    for kind, ref in sides:
                        if kind == "state":
                            f = s[ref] if law == "state_fraction" else 1.0 - s[ref]
                        else:
                            f = fr.hill_scalar(law, self._value(ref, conc, regs), K, n)
                        value = value * (basal + (1.0 - basal) * f)
                factors.append((e, j, value))
                g = g * value
            avail.append((sched[e], g, sched[e] * g))
        z, F, rt, bath, ns = self.z, self.F, self.rt, self.w.bath_mM, self.ns
        flux = []
        for i, pa in self.patch_table:
            x = F * phi[i] / rt
            flux.append((i, -1, None, [ghk_flux(pa[k], z[k], x, conc[i][k], bath[k])
                                       for k in range(ns)]))
        for i, e, pa in self.population_table:
            x = F * phi[i] / rt
            a_eff = avail[e][2]
            flux.append((i, -1, e, [ghk_flux(a_eff * pa[k], z[k], x, conc[i][k], bath[k])
                                    for k in range(ns)]))
        for a, b, e, pa in self.contact_table:
            x = F * (phi[a] - phi[b]) / rt
            a_eff = avail[e][2]
            flux.append((a, b, e, [ghk_flux(a_eff * pa[k], z[k], x, conc[a][k], conc[b][k])
                                   for k in range(ns)]))
        return charge, amounts, conc, phi, regs, s, u, factors, avail, flux

    def rhs(self, t, y, sched, enabled):
        _, _, _, _, _, s, u, _, _, flux = self.core(t, y, sched, enabled)
        nc, ns, z = len(self.cells), self.ns, self.z
        dn = [[0.0] * ns for _ in range(nc)]  # fmol/s
        dq = [[] for _ in range(nc)]  # charge-rate terms (fmol/s)
        exchange = [[] for _ in range(ns)]
        for i, j, _, J in flux:
            for k in range(ns):
                rate = J[k] / FMOL
                dn[i][k] -= rate
                dq[i].append(-z[k] * rate)
                if j >= 0:
                    dn[j][k] += rate
                    dq[j].append(z[k] * rate)
                else:
                    exchange[k].append(rate)
        out = np.empty(self.size)
        m = self.block
        for i in range(nc):
            out[i * m] = math.fsum(dq[i])
            for jj, k in enumerate(self.others):
                out[i * m + 1 + jj] = dn[i][k]
        sb = self.state_base
        for idx, (k_on, k_off, _) in enumerate(self.pair_specs):
            out[sb + 2 * idx] = k_on * u[idx] * (1.0 - s[idx]) - k_off * s[idx]
            out[sb + 2 * idx + 1] = u[idx]
        for k in range(ns):
            out[self.exchange_base + k] = -math.fsum(exchange[k])  # bath -> tissue
        return out

    def evaluate(self, t, y, sched, enabled):
        """The core's values, keyed by name (for the records)."""
        charge, amounts, conc, phi, regs, s, u, factors, avail, flux = self.core(t, y, sched,
                                                                                 enabled)
        return dict(
            charge=charge, amounts=amounts, conc=conc, phi=phi,
            regulators={pair: regs[j] for j, pair in enumerate(self.regs)},
            s={pair: s[j] for j, pair in enumerate(self.pairs)},
            u={pair: u[j] for j, pair in enumerate(self.pairs)},
            factors={(self.coupling_names[j], self.elements[e]): v for e, j, v in factors},
            avail={self.elements[e]: avail[e] for e in range(len(self.elements))},
            flux={**{name: f for name, f in zip(self.w.patches, flux, strict=False)},
                  **{self.elements[f[2]]: f for f in flux if f[2] is not None}},
        )

    # -- the start
    def bath_current(self, i, v, sched, enabled, s0):
        """The outward current (A) of cell i's bath routes at potential v, at t = 0+, with every
        cell at its initial composition and the states at s0 (contacts excluded)."""
        z, F, rt, ns, bath = self.z, self.F, self.rt, self.ns, self.w.bath_mM
        conc = [list(self.w.cells[c].mM) for c in self.cells]
        y = np.zeros(self.size)
        for j in range(len(self.pairs)):
            y[self.state_base + 2 * j] = s0[j]
        x = F * v / rt
        total = []
        for c, pa in self.patch_table:
            if c == i:
                total += [z[k] * ghk_flux(pa[k], z[k], x, conc[i][k], bath[k]) for k in range(ns)]
        if self.population_table:
            avail = self.core(0.0, y, sched, enabled, conc_override=conc, s_override=list(s0))[8]
            for c, e, pa in self.population_table:
                if c == i:
                    total += [z[k] * ghk_flux(avail[e][2] * pa[k], z[k], x, conc[i][k], bath[k])
                              for k in range(ns)]
        return F * math.fsum(total)

    def start(self, first_segment):
        """The initial state vector and {cell: (V0, background, charge)}."""
        w, z, F = self.w, self.z, self.F
        sched, enabled = self.controls(*first_segment)
        s0 = [initial_states(w.states[st], w.states[st].cells)[c] for st, c in self.pairs]
        y = np.zeros(self.size)
        initial = {}
        for i, name in enumerate(self.cells):
            cell = w.cells[name]
            n = [x * cell.volume_pL for x in cell.mM]
            content = math.fsum(z[k] * n[k] for k in range(self.ns))
            if math.isfinite(cell.background_fmol):
                background = cell.background_fmol
                charge = content + background
                v0 = charge * FMOL * F / self.capacitance[i]
            else:
                if math.isfinite(cell.initial_V):
                    v0 = cell.initial_V
                else:
                    v0 = brentq(lambda v, i=i: self.bath_current(i, v, sched, enabled, s0),
                                -0.25, 0.25, xtol=1e-15, rtol=4 * fr.EPS)
                charge = self.capacitance[i] * v0 / (F * FMOL)
                background = charge - content
            self.background[i] = background
            y[i * self.block] = charge
            for j, k in enumerate(self.others):
                y[i * self.block + 1 + j] = n[k]
            initial[name] = dict(V=v0, background_fmol=background, charge_fmol=charge)
        for idx in range(len(self.pairs)):
            y[self.state_base + 2 * idx] = s0[idx]
        return y, initial


# ---------------------------------------------------------------- running


class CellsRun:
    """One run. ``at[t]`` is the record at each requested time (see the usage note);
    ``observe(t)`` gives a record at any t by re-integration; ``crossings[(state, cell)]`` is t*
    for every state with a crossing level; ``crossing_step(state, cell, dt)`` gives k*."""

    def __init__(self, model, run, record, initial, wall_s, points):
        self.model, self.run, self.initial, self.wall_s = model, run, initial, wall_s
        self.steps = run.steps
        self.points = points
        self.at = {t: self.observe(t) for t in record}
        self.crossings = {}
        for st, spec in model.w.states.items():
            if math.isnan(spec.crossing_level):
                continue
            for c in spec.cells:
                self.crossings[(st, c)] = self.crossing(st, c, spec.crossing_level)

    @property
    def slots(self):
        """The (state, cell) pairs in declared order: states, then each state's cells (the
        engine's flat regulatory_slot axis, §7.1 item 1)."""
        return list(self.model.pairs)

    def observe(self, t):
        """The record at t. The state (V, amounts, s, U) is continuous. Quantities that use a
        schedule or a switch are given three ways:
        * unsuffixed, the as-built convention (§7.1 item 3, §1.9): the switches in force before
          t (a row at a switch time shows the pre-event switch) against the availability
          schedules from t on;
        * "..._left": switches and schedules just before t;
        * "..._right": switches and schedules from t on.
        Away from an event time the three coincide."""
        m, w = self.model, self.model.w
        y = self.run.state(t)
        pts = self.points
        j = int(np.searchsorted(pts, t, side="right"))
        right = (pts[j - 1], pts[j]) if j < len(pts) else (pts[-2], pts[-1])
        k = int(np.searchsorted(pts, t, side="left"))
        left = (pts[k - 1], pts[k]) if k >= 1 else right
        sched_r, enabled_r = m.controls(*right)
        sched_l, enabled_l = m.controls(*left)
        ev_right = m.evaluate(t, y, sched_r, enabled_r)
        ev_left = m.evaluate(t, y, sched_l, enabled_l)
        ev = m.evaluate(t, y, sched_r, enabled_l)  # as built
        F = m.F
        rec = dict(t=t, V={}, charge_C={}, amounts_fmol={}, mM={}, background_fmol={})
        for i, c in enumerate(m.cells):
            rec["V"][c] = ev["phi"][i]
            rec["charge_C"][c] = ev["charge"][i] * FMOL * F
            rec["amounts_fmol"][c] = tuple(ev["amounts"][i])
            rec["mM"][c] = tuple(ev["conc"][i])
            rec["background_fmol"][c] = m.background[i]
        rec["regulators_mM"] = dict(ev["regulators"])
        rec["s"] = dict(ev["s"])
        rec["U"] = {pair: float(y[m.state_base + 2 * i + 1]) for i, pair in enumerate(m.pairs)}
        rec["u"] = dict(ev["u"])
        rec["routes"] = {r: dict(F=ev["factors"][r], F_left=ev_left["factors"][r],
                                 F_right=ev_right["factors"][r]) for r in ev["factors"]}
        rec["elements"] = {}

        def current(e, element):
            return F * math.fsum(zk * J for zk, J in zip(m.z, e["flux"][element][3],
                                                       strict=True))

        for element in ev["avail"]:
            entry = {}
            for suffix, e in (("", ev), ("_left", ev_left), ("_right", ev_right)):
                a, g, eff = e["avail"][element]
                entry.update({f"a_sched{suffix}": a, f"G{suffix}": g, f"a_eff{suffix}": eff,
                              f"current_A{suffix}": current(e, element)})
            rec["elements"][element] = entry
        rec["patch_current_A"] = {p: F * math.fsum(zk * J for zk, J in
                                                   zip(m.z, ev["flux"][p][3], strict=True))
                                  for p in w.patches}
        rec["exchanged_fmol"] = tuple(float(x) for x in y[m.exchange_base:])
        return rec

    def crossing(self, state, cell, theta):
        """t* = the first t with s >= theta for (state, cell) (0 if s0 >= theta; inf if not by
        t_end), refined by Brent's method on re-integrations."""
        idx = self.model.state_base + 2 * self.model.pi[(state, cell)]
        return self.run.first_crossing(lambda t, y: y[idx], theta)

    def crossing_step(self, state, cell, dt, theta=None):
        theta = self.model.w.states[state].crossing_level if theta is None else theta
        idx = self.model.state_base + 2 * self.model.pi[(state, cell)]
        return rs.crossing_step(lambda t: float(self.run.state(t)[idx]),
                                self.crossing(state, cell, theta), theta, dt, self.run.t_end)


def compare(a, b, record):
    """Max |a - b| per observable over the records of two runs of one world: V, amounts, mM,
    s, U, F (routes), a_eff, current (elements) and crossing (t*)."""
    out = dict(V=0.0, amounts=0.0, mM=0.0, s=0.0, U=0.0, F=0.0, a_eff=0.0, current=0.0)
    for t in record:
        ra, rb = a.at[t], b.at[t]
        for c in ra["V"]:
            out["V"] = max(out["V"], abs(ra["V"][c] - rb["V"][c]))
            out["amounts"] = max(out["amounts"], *(abs(x - y) for x, y in zip(
                ra["amounts_fmol"][c], rb["amounts_fmol"][c], strict=True)))
            out["mM"] = max(out["mM"], *(abs(x - y) for x, y in zip(ra["mM"][c], rb["mM"][c],
                                                                      strict=True)))
        for k in ra["s"]:
            out["s"] = max(out["s"], abs(ra["s"][k] - rb["s"][k]))
            out["U"] = max(out["U"], abs(ra["U"][k] - rb["U"][k]))
        for k in ra["routes"]:
            out["F"] = max(out["F"], abs(ra["routes"][k]["F"] - rb["routes"][k]["F"]))
        for e in ra["elements"]:
            out["a_eff"] = max(out["a_eff"], abs(ra["elements"][e]["a_eff"]
                                                 - rb["elements"][e]["a_eff"]))
            out["current"] = max(out["current"], abs(ra["elements"][e]["current_A"]
                                                     - rb["elements"][e]["current_A"]))
    out["crossing"] = max((abs(a.crossings[k] - b.crossings[k]) for k in a.crossings),
                          default=0.0)
    return out


def floor(world, t_end, record, *, rtol=1e-10, atol=None, factor=100.0, method="Radau"):
    """The numerical floor of a run of any world: the run at (rtol, atol) and one at
    rtol / factor and atol / (10 factor), compared per observable (compare). Returns
    (the run, the tight run, the differences); the differences estimate the first run's error."""
    base = dict(ATOL, **(atol or {}))
    run = simulate(world, t_end, record=record, rtol=rtol, atol=base, method=method)
    tight = simulate(world, t_end, record=record, rtol=rtol / factor, method=method,
                     atol={k: v / (10.0 * factor) for k, v in base.items()})
    return run, tight, compare(run, tight, record)


def breakpoints(world, t_end, record=()):
    w = world
    points = {0.0, float(t_end), *(float(t) for t in record)}
    for x in (*w.populations.values(), *w.contacts.values()):
        points |= {a for a, _ in x.schedule}
    for cp in w.couplings.values():
        points |= {a for a, _ in cp.enabled}
    for reg in w.regulators.values():
        for turnover in reg.amounts.values():
            points |= set(turnover.breakpoints())
    return sorted(p for p in points if 0.0 <= p <= t_end)


def simulate(world, t_end, *, record=(), rtol=1e-10, atol=None, method="Radau",
             max_step=math.inf):
    """Integrate a world from 0 to t_end; returns a CellsRun. ``atol`` is a dict over the state
    kinds of ATOL (charge and amounts in fmol, state, exposure in s, exchange in fmol); a dict
    with some keys overrides only those."""
    started = time.perf_counter()
    check_world(world)
    if not (_finite(t_end) and t_end > 0):
        raise ValueError("t_end is finite and > 0")
    record = tuple(sorted({float(t) for t in record}))
    if any(not 0.0 <= t <= t_end for t in record):
        raise ValueError("records lie in [0, t_end]")
    model = _Model(world, dict(ATOL, **(atol or {})))
    points = breakpoints(world, t_end, record)
    y0, initial = model.start((points[0], points[1]))

    def segment(t0, t1):
        sched, enabled = model.controls(t0, t1)
        return (lambda t, y: model.rhs(t, y, sched, enabled)), None

    run = piecewise_ode.Run(segment, y0, points, rtol=rtol, atol=model.atol, method=method,
                            max_step=max_step)
    return CellsRun(model, run, record, initial, time.perf_counter() - started,
                    np.array(points))
