"""R-tissue: a graph-general R-full with prescribed divisions, an independent reference for S5.

Written from docs/CELL_DIVISION_S5_DESIGN.md (Appendix A, §7.2 and §10.1) and the physics, not
from engine code; numpy/scipy only. It is R-full (validation/division/cleft_egg_reference.py)
generalised to a graph, in R-full's style, and it imports R-full's transport laws (ghk_flux,
access_flux), which S3 qualified against the engine. It adds the graph solve, the bridge, the
contacts and the division events, and R-ops (validation/division/partition_reference.py) is
applied at each division.

The model (Appendix A; SI units, amounts in fmol, volumes in pL, so n/V is in mM):
* nodes: cells and clefts are free, the bath is held at 0 V. Liveness: a founder cell is live
  from t = 0; a daughter from its division; a parent until its division (then retired). A
  patch is live with its cell (and from its onset, for an onset patch), a cleft from the onset
  of its patches, a face when both its nodes are, a junction (contact or bridge) when both its
  cells are. A junction that is not live reads gate 0 (the lead's addition to A.6 item 5);
* capacitor graph by patches: K = sum_k C_k e_k e_k^T over the live patches, K_ff phi_f = Q_f.
  Node charges are explicit states (R-full's layout per free node: the charge, then the amount
  of every species but the last charged one, which follows from the charge); one insertion-heat
  state follows;
* membranes: constant-field, P_k,s A_k per patch; faces: R-full's log-mean or constant-field
  access with k = (A/L) D_s; contacts: constant-field junctions g P_s A_e; bridges:
  constant-field junctions with P A = 2 g a(t) D_s^cyt and the closure law of A.7;
* insertion: dA/dt = r_k (piecewise constant, declared per patch), dC/dt = c_d r_k at fixed
  free-node charges, heat (1/2) sum c_d r_k V_k^2;
* lumens: V_c = w sum_live A_k / 2 (A.5, with V_on = w A_on / 2), filled at bath composition;
  a cleft opens with its onset patches at zero charge, its species but the follower at bath
  composition (R-full's convention);
* injection: R-full's pulse trains into declared cells, carried by declared species;
* divisions: at each division time, in declared order, R-ops' map on the live tissue, then the
  onsets due at that time. A parent whose bridge is still open is refused (its closure must end
  first: the linear law; design §3.8).
Integration: scipy's Radau at rtol 1e-10 (R-full's), absolute tolerances as R-full's per state
kind, breakpoints at every onset, division, closure end, schedule change, pulse edge and record.
Only the live states are integrated in each segment, so rtol keeps its meaning with pending
slots. Records at a time are taken after the events at that time (R-full's convention).

Two entry points (the J2 bright line, design §10.1): simulate_static, for a world without
divisions (R-tissue's cross-check against R-full on S3's egg calls it, from
cleft_tissue_crosscheck.py), and simulate_divisions, for prescribed divisions, which refuses a
world converted from an R-full egg (from_egg). R-ops is loaded on the division path only, so a
static run never loads the partition map. This module reads no declared input of any
experiment: every world is passed in.
"""

import math
import time
from dataclasses import dataclass, field

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

from validation.division import cleft_egg_reference as rfull

F, R, FMOL = rfull.F, rfull.R, 1e-15  # The exact SI products (R-ops uses the same).
EPS = float(np.finfo(float).eps)


def _rops():
    """R-ops (validation/division/partition_reference.py), loaded on the division path only, so
    the static entry point never loads the partition map (the J2 bright line, design §10.1)."""
    from validation.division import partition_reference

    return partition_reference


BATH = "bath"
ORIGIN_WORLD = "world"
ORIGIN_EGG = "rfull_egg"  # from_egg; refused by simulate_divisions (design §10.1)
# Absolute tolerances per state kind (fmol, pJ): R-full's, at egg scale (node charges of order
# 10 fmol), which the cross-check against R-full needs. Scale them to the world: on a cell of
# tissue scale (node charges of order 1e-3 fmol) these defaults leave about 4e-10 V in Vm, where
# atol = dict(cell_charge=1e-15, cleft_charge=1e-17, cell_amount=1e-12, cleft_amount=1e-14,
# heat=1e-15) agrees with a thousandfold tighter set to 2e-14 V (the S5 references' evidence,
# run-02/atol_check.json).
ATOL = dict(cell_charge=1e-9, cell_amount=1e-6, cleft_charge=1e-9, cleft_amount=1e-9, heat=1e-12)


# ---------------------------------------------------------------- the world


@dataclass(frozen=True)
class CellSpec:
    """A cell. A founder declares its volume and composition; a daughter's come from its
    division (leave them unset)."""

    volume_pL: float = math.nan
    mM: tuple = ()  # initial concentration of every species (founders)
    initial_V: float = math.nan  # founders: start here; NaN: the zero-current potential


@dataclass(frozen=True)
class CleftSpec:
    gap_width_m: float


@dataclass(frozen=True)
class PatchSpec:
    """A membrane patch between its cell and an outside node (the bath or a cleft).

    A founder's patch (no onset) declares its area and capacitance and faces the bath. An onset
    patch declares its area at onset A_on (capacitance c_d A_on unless declared) and faces a
    cleft. A daughter's patch (no onset) is written by its division."""

    cell: str
    node: str
    permeability_m_s: tuple  # per unit area, per species
    area_m2: float = math.nan
    capacitance_F: float = math.nan
    specific_capacitance_F_m2: float = 0.0  # c_d of inserted membrane
    onset_s: float = math.nan
    schedule: tuple = ()  # ((t_start, rate_m2_s), ...): absolute times, rate 0 before the first


@dataclass(frozen=True)
class FaceSpec:
    """An access face between two outside nodes; the flux is positive from nodes[0]."""

    nodes: tuple
    a_over_l_m: float
    diffusivity_m2_s: tuple
    law: str = "logmean"  # or "constant_field"


@dataclass(frozen=True)
class ContactSpec:
    """A junction between two cells (constant-field, P_s A g with a fixed gate). A founders'
    contact declares its area and gate; a daughter contact's come from its division."""

    cells: tuple
    permeability_m_s: tuple  # per unit area
    area_m2: float = math.nan
    gate: float = 1.0


@dataclass(frozen=True)
class InjectionSpec:
    cell: str
    pulses: rfull.Pulses
    carriers: dict  # species -> fraction of the current (sum 1)


@dataclass(frozen=True)
class BridgeSpec:
    """The cytoplasmic bridge a division opens between its daughters (A.7)."""

    a0_m: float
    diffusivity_m2_s: tuple  # D_s^cyt (partition_reference.bridge_diffusivities)
    law: str = "linear"  # or "exponential"
    tau_s: float = math.inf
    gate: float = 1.0  # fixed open


@dataclass(frozen=True)
class DivisionSpec:
    parent: str
    daughters: tuple
    time_s: float
    f: float
    patches: dict  # parent patch -> (patch of D1, patch of D2, a_k)
    carriers: dict = field(default_factory=dict)  # species -> transference number
    contacts: dict = field(default_factory=dict)  # parent contact -> (of D1, of D2, a_e)
    bridge: str = ""
    bridge_spec: BridgeSpec = None


@dataclass(frozen=True)
class World:
    temperature_K: float
    bath_mM: tuple
    cells: dict
    patches: dict
    clefts: dict = field(default_factory=dict)
    faces: dict = field(default_factory=dict)
    contacts: dict = field(default_factory=dict)
    injections: tuple = ()
    divisions: dict = field(default_factory=dict)
    species: tuple = ("Na", "K", "Cl")
    z: tuple = (1, 1, -1)
    origin: str = ORIGIN_WORLD


def _finite_positive(x):
    return isinstance(x, (int, float)) and math.isfinite(x) and x > 0.0


def schedule_rate(schedule, t0, t1):
    """The insertion rate on [t0, t1] (segments never straddle a schedule change)."""
    mid = 0.5 * (t0 + t1)
    rate = 0.0
    for start, r in schedule:
        if start > mid:
            break
        rate = r
    return rate


def inserted_area(schedule, t_ref, t):
    """The area inserted on [t_ref, t] by a piecewise-constant schedule."""
    added = 0.0
    for i, (start, r) in enumerate(schedule):
        stop = schedule[i + 1][0] if i + 1 < len(schedule) else math.inf
        lo, hi = max(start, t_ref), min(stop, t)
        if hi > lo:
            added += r * (hi - lo)
    return added


def pulse_current(pulses, t0):
    """The injected current on the segment starting at t0 (R-full's current_at rule)."""
    p = pulses
    if not p.enabled or t0 < p.first_onset_s:
        return 0.0
    k = int(math.floor((t0 - p.first_onset_s) / p.period_s + 1e-12))
    start = p.onset(k)
    if start - 1e-12 <= t0 < start + p.duration_s - 1e-9:
        return p.sign(k) * p.amplitude_A
    return 0.0


def lifetimes(world):
    """{cell: (birth, death)}: founders from 0, daughters from their division; a parent until
    its division."""
    out = {name: [0.0, math.inf] for name in world.cells}
    for d in world.divisions.values():
        out[d.parent][1] = d.time_s
        for name in d.daughters:
            out[name][0] = d.time_s
    return {k: tuple(v) for k, v in out.items()}


def check_world(world):
    """Refuse an inadmissible world (Appendix A and design §3.8, as they bear on R-tissue)."""
    w = world
    ns = len(w.species)
    if len(w.z) != ns or not any(w.z):
        raise ValueError("species and valences must match, with a charged species")
    if len(w.bath_mM) != ns or not all(_finite_positive(c) for c in w.bath_mM):
        raise ValueError("the bath declares a positive concentration of every species")
    parents = [d.parent for d in w.divisions.values()]
    daughters = [x for d in w.divisions.values() for x in d.daughters]
    if len(set(parents)) != len(parents) or len(set(daughters)) != len(daughters):
        raise ValueError("a cell is at most one division's parent and one division's daughter")
    for name in [*parents, *daughters]:
        if name not in w.cells:
            raise ValueError(f"division cell {name} is not declared")
    life = lifetimes(w)
    for name, c in w.cells.items():
        if name in daughters:
            if not math.isnan(c.volume_pL) or c.mM or not math.isnan(c.initial_V):
                raise ValueError(f"daughter {name} takes its contents from its division")
        else:
            if not _finite_positive(c.volume_pL) or len(c.mM) != ns:
                raise ValueError(f"founder {name} declares its volume and composition")
            if not all(_finite_positive(x) for x in c.mM):
                raise ValueError(f"founder {name} has a non-positive concentration")
    born_patches = {x: d for d in w.divisions.values() for v in d.patches.values() for x in v[:2]}
    for name, p in w.patches.items():
        if p.cell not in w.cells:
            raise ValueError(f"patch {name}: no cell {p.cell}")
        if p.node != BATH and p.node not in w.clefts:
            raise ValueError(f"patch {name}: no outside node {p.node}")
        if len(p.permeability_m_s) != ns or not all(
            math.isfinite(x) and x >= 0.0 for x in p.permeability_m_s
        ):
            raise ValueError(f"patch {name}: a non-negative permeability per species")
        if not (math.isfinite(p.specific_capacitance_F_m2) and p.specific_capacitance_F_m2 >= 0):
            raise ValueError(f"patch {name}: specific capacitance")
        starts = [s for s, _ in p.schedule]
        if starts != sorted(starts) or any(not (r >= 0.0) for _, r in p.schedule):
            raise ValueError(f"patch {name}: the schedule is sorted, with rates >= 0")
        if any(r > 0.0 for _, r in p.schedule) and not p.specific_capacitance_F_m2 > 0.0:
            raise ValueError(f"patch {name}: inserted membrane needs its specific capacitance")
        if math.isfinite(p.onset_s):
            if p.node == BATH:
                raise ValueError(f"onset patch {name} faces a cleft (A.4)")
            if not (_finite_positive(p.area_m2) and p.onset_s >= 0.0):
                raise ValueError(f"onset patch {name} declares its area at onset")
            cap = p.capacitance_F
            if not (_finite_positive(cap) or (math.isnan(cap) and p.specific_capacitance_F_m2)):
                raise ValueError(f"onset patch {name}: capacitance at onset")
            birth, death = life[p.cell]
            if not birth <= p.onset_s < death:  # Divisions come before onsets at one time.
                raise ValueError(f"onset of patch {name} outside its cell's life")
            live = (p.onset_s, death)
        elif name in born_patches:
            if not (math.isnan(p.area_m2) and math.isnan(p.capacitance_F)):
                raise ValueError(f"daughter patch {name} takes its area from its division")
            live = life[p.cell]
        else:
            if p.cell in daughters:
                raise ValueError(f"patch {name} of daughter {p.cell} is in no division's map")
            if p.node != BATH:
                raise ValueError(f"founder patch {name} faces the bath (a cleft opens at onset)")
            if not (_finite_positive(p.area_m2) and _finite_positive(p.capacitance_F)):
                raise ValueError(f"founder patch {name} declares its area and capacitance")
            live = life[p.cell]
        for i, (start, r) in enumerate(p.schedule):
            stop = p.schedule[i + 1][0] if i + 1 < len(p.schedule) else math.inf
            if r > 0.0 and (start < live[0] or stop > live[1]):
                raise ValueError(f"patch {name}: insertion outside its living interval")
    for name, face in w.faces.items():
        a, b = face.nodes
        if a == b or any(x != BATH and x not in w.clefts for x in (a, b)) or BATH == a == b:
            raise ValueError(f"face {name} joins two distinct outside nodes")
        if face.law not in ("logmean", "constant_field") or len(face.diffusivity_m2_s) != ns:
            raise ValueError(f"face {name}: law and diffusivities")
        if not (math.isfinite(face.a_over_l_m) and face.a_over_l_m >= 0.0):
            raise ValueError(f"face {name}: A/L")
    born_contacts = {x for d in w.divisions.values() for v in d.contacts.values() for x in v[:2]}
    for name, c in w.contacts.items():
        if len(c.cells) != 2 or c.cells[0] == c.cells[1] or any(x not in w.cells for x in c.cells):
            raise ValueError(f"contact {name} joins two distinct declared cells")
        if len(c.permeability_m_s) != ns or not 0.0 <= c.gate <= 1.0:
            raise ValueError(f"contact {name}: permeability and gate")
        if name in born_contacts:
            if not math.isnan(c.area_m2):
                raise ValueError(f"daughter contact {name} takes its area from its division")
        elif any(x in daughters for x in c.cells) or not _finite_positive(c.area_m2):
            raise ValueError(f"contact {name}: founders' contacts declare an area")
    for inj in w.injections:
        if inj.cell not in w.cells:
            raise ValueError(f"injection into {inj.cell}: not declared")
        index = {s: i for i, s in enumerate(w.species)}
        if any(s not in index or w.z[index[s]] == 0 for s in inj.carriers):
            raise ValueError("injection carriers are charged species")
        if (
            any(not x >= 0.0 for x in inj.carriers.values())
            or abs(math.fsum(inj.carriers.values()) - 1.0) > 4 * EPS
        ):
            raise ValueError("injection carrier fractions are >= 0 and sum to 1")
    # The divisions in event order (time, then declared order), replaying contact liveness.
    live_contacts = {e for e in w.contacts if e not in born_contacts}
    for dname, d in sorted(w.divisions.items(), key=lambda item: item[1].time_s):
        birth, _ = life[d.parent]
        if not (math.isfinite(d.time_s) and d.time_s >= birth):
            raise ValueError(f"division {dname}: its parent is not live at its time")
        if d.parent in daughters and not d.time_s > birth:
            raise ValueError(f"division {dname}: the parent divides after its own birth")
        live_patches = {
            k
            for k, p in w.patches.items()
            if p.cell == d.parent and not (math.isfinite(p.onset_s) and p.onset_s >= d.time_s)
        }
        if set(d.patches) != live_patches:
            raise ValueError(
                f"division {dname}: the patch map covers the parent's live patches "
                f"{sorted(live_patches)}"
            )
        for k, (k1, k2, _) in d.patches.items():
            parent = w.patches[k]
            for kd, cell in ((k1, d.daughters[0]), (k2, d.daughters[1])):
                child = w.patches.get(kd)
                if child is None or child.cell != cell or math.isfinite(child.onset_s):
                    raise ValueError(f"division {dname}: {kd} is a base patch of {cell}")
                if (child.node, child.permeability_m_s, child.specific_capacitance_F_m2) != (
                    parent.node,
                    parent.permeability_m_s,
                    parent.specific_capacitance_F_m2,
                ):
                    raise ValueError(f"division {dname}: {kd} keeps {k}'s node and parameters")
        touching = {e for e in live_contacts if d.parent in w.contacts[e].cells}
        if set(d.contacts) != touching:
            raise ValueError(f"division {dname}: the contact map covers {sorted(touching)}")
        live_contacts -= touching
        live_contacts |= {x for e1, e2, _ in d.contacts.values() for x in (e1, e2)}
        for e, (e1, e2, _) in d.contacts.items():
            other = [x for x in w.contacts[e].cells if x != d.parent][0]
            for ed, cell in ((e1, d.daughters[0]), (e2, d.daughters[1])):
                child = w.contacts.get(ed)
                if child is None or set(child.cells) != {cell, other}:
                    raise ValueError(f"division {dname}: contact {ed} joins {cell} and {other}")
                if child.permeability_m_s != w.contacts[e].permeability_m_s:
                    raise ValueError(f"division {dname}: contact {ed} keeps {e}'s permeability")
        b = d.bridge_spec
        if d.bridge:
            if b is None or not _finite_positive(b.a0_m) or b.law not in ("linear", "exponential"):
                raise ValueError(f"division {dname}: the bridge declares a0, its law and tau")
            if not (b.tau_s > 0.0 and 0.0 <= b.gate <= 1.0 and len(b.diffusivity_m2_s) == ns):
                raise ValueError(f"division {dname}: bridge tau, gate and diffusivities")
        # The parent's own bridge (from its birth) must have closed (design §3.8).
        for other in w.divisions.values():
            if d.parent in other.daughters and other.bridge:
                spec = other.bridge_spec
                if _rops().aperture(spec.a0_m, spec.law, spec.tau_s, other.time_s, d.time_s) > 0.0:
                    raise ValueError(
                        f"division {dname}: the parent's bridge {other.bridge} is still open"
                    )
    for name in w.cells:
        on_bath = [k for k, p in w.patches.items() if p.cell == name and p.node == BATH]
        if not on_bath:
            raise ValueError(f"cell {name} has no patch on the bath (a floating component)")


def from_egg(egg):
    """R-full's one-cell cleft egg (the registered Model: no diagnostic extensions) as a world
    without divisions: the egg, its old membrane to the bath, the new membrane from its onset
    facing the cleft, the access face, and the pulse train. Its origin bars it from
    simulate_divisions (design §10.1)."""
    if egg.extended or egg.new_faces != "lumen" or egg.old_capacitance_rate_F_s != 0.0:
        raise ValueError("from_egg converts R-full's registered model only")
    if not egg.schedule or egg.schedule[0][0] > egg.onset_s:
        raise ValueError("from_egg needs an insertion schedule that starts by the onset")
    # R-full's area integrates the schedule from its first start, which may precede the onset:
    # the patch opens with R-full's area at the onset, then the schedule from the onset on.
    current = [rate for start, rate in egg.schedule if start <= egg.onset_s][-1]
    schedule = ((egg.onset_s, current), *((s, r) for s, r in egg.schedule if s > egg.onset_s))
    old = rfull.SPECIES
    return World(
        temperature_K=egg.temperature_K,
        bath_mM=tuple(egg.bath_mM),
        species=old,
        z=rfull.Z,
        cells={"egg": CellSpec(egg.cytosol_volume_m3 / FMOL, tuple(egg.cytosol_mM), egg.initial_V)},
        clefts={"cleft": CleftSpec(egg.gap_width_m)},
        patches={
            "old": PatchSpec(
                "egg",
                BATH,
                tuple(egg.p_old * w for w in egg.old_relative),
                area_m2=egg.old_area_m2,
                capacitance_F=egg.old_capacitance_F,
            ),
            "new": PatchSpec(
                "egg",
                "cleft",
                tuple(egg.new_permeability),
                area_m2=egg.area(egg.onset_s),
                specific_capacitance_F_m2=egg.new_specific_capacitance_F_m2,
                onset_s=egg.onset_s,
                schedule=schedule,
            ),
        },
        faces={
            "access": FaceSpec(("cleft", BATH), egg.a_over_l_m, tuple(egg.access_D), egg.access_law)
        },
        injections=(
            InjectionSpec(
                "egg", egg.pulses, {"K": egg.pulses.carrier_K, "Cl": egg.pulses.carrier_Cl}
            ),
        ),
        origin=ORIGIN_EGG,
    )


# ---------------------------------------------------------------- the integration


@dataclass
class TissueRun:
    """Records of one R-tissue run."""

    world: World
    at: dict  # time -> record (after the events at that time)
    onset_V: list  # per injection: {pulse k: V of its cell at the front edge}
    sample_V: list  # per injection: {pulse k: V one sample time after the front edge}
    events: list  # per division: dict(time_s, division, before, map, result) (R-ops)
    initial: dict  # founder -> dict(V, background_fmol, charge_fmol)
    steps: int
    wall_s: float


class _Segment:
    """Constants of one integration interval: the live graph, rates, currents and apertures."""

    def __init__(self, tissue, t0, t1):
        w = tissue.world
        self.t0 = t0
        self.tissue = tissue
        self.rt = R * w.temperature_K
        self.z = w.z
        self.follower = tissue.follower
        self.others = tissue.others
        self.bath = tuple(w.bath_mM)
        self.supply_charge = math.fsum(z * c for z, c in zip(w.z, w.bath_mM, strict=True))
        self.nodes = [*tissue.live_cells(), *tissue.live_clefts()]
        self.index = {node: i for i, node in enumerate(self.nodes)}
        self.ncell = len(tissue.live_cells())
        self.volume = [tissue.volume[x] for x in self.nodes[: self.ncell]]
        self.background = [tissue.background[x] for x in self.nodes[: self.ncell]]
        n = len(self.nodes)
        self.K0 = np.zeros((n, n))
        self.K1 = np.zeros((n, n))
        self.patches = []
        for name in tissue.live_patches():
            p = w.patches[name]
            t_ref, a_ref, c_ref = tissue.patch_ref[name]
            added = inserted_area(p.schedule, t_ref, t0)
            area0 = a_ref + added
            cap0 = c_ref + p.specific_capacitance_F_m2 * added
            rate = schedule_rate(p.schedule, t0, t1)
            i = self.index[p.cell]
            o = self.index.get(p.node, -1)
            dc = p.specific_capacitance_F_m2 * rate
            for K, c in ((self.K0, cap0), (self.K1, dc)):
                K[i, i] += c
                if o >= 0:
                    K[o, o] += c
                    K[i, o] -= c
                    K[o, i] -= c
            self.patches.append((name, i, o, area0, cap0, rate, dc, tuple(p.permeability_m_s)))
        self.clefts = []
        for x in self.nodes[self.ncell :]:
            facing = [j for j, q in enumerate(self.patches) if w.patches[q[0]].node == x]
            gap = w.clefts[x].gap_width_m
            fill = gap * math.fsum(self.patches[j][5] for j in facing) / 2.0  # dV/dt (m3/s)
            self.clefts.append((self.index[x], gap, facing, fill))
        self.faces = []
        for name in tissue.live_faces():
            face = w.faces[name]
            a, b = (self.index.get(x, -1) for x in face.nodes)
            k = tuple(face.a_over_l_m * d for d in face.diffusivity_m2_s)
            self.faces.append((name, a, b, k, face.law))
        self.junctions = []
        for name in tissue.live_contacts():
            c = w.contacts[name]
            area, gate = tissue.contact_state[name]
            pa = tuple(gate * p * area for p in c.permeability_m_s)
            a, b = (self.index[x] for x in c.cells)
            self.junctions.append((name, a, b, pa, None))
        for name in tissue.live_bridges():
            cells, spec, born = tissue.bridge_state[name]
            coef = tuple(2.0 * spec.gate * d for d in spec.diffusivity_m2_s)
            a, b = (self.index[x] for x in cells)
            self.junctions.append((name, a, b, coef, (spec, born)))
        self.injection = []
        for inj in w.injections:
            if inj.cell in self.index:
                current = pulse_current(inj.pulses, t0)
                if current:
                    carried = [
                        (w.species.index(s), x / w.z[w.species.index(s)])
                        for s, x in inj.carriers.items()
                    ]
                    self.injection.append((self.index[inj.cell], current, carried))
        self.block = 1 + len(self.others)

    def concentrations(self, t, y):
        """Concentrations (mM) of every node, cleft volumes (pL) and patch areas at (t, y)."""
        dt = t - self.t0
        area = [q[3] + q[5] * dt for q in self.patches]
        volume = list(self.volume)
        for _, gap, facing, _ in self.clefts:
            volume.append(gap * math.fsum(area[j] for j in facing) / 2.0 / FMOL)
        background = self.background + [0.0] * len(self.clefts)
        z, f, m = self.z, self.follower, self.block
        conc, amounts = [], []
        for i in range(len(self.nodes)):
            block = y[i * m : (i + 1) * m]
            n = [0.0] * len(z)
            for j, s in enumerate(self.others):
                n[s] = block[1 + j]
            n[f] = (
                block[0]
                - background[i]
                - math.fsum(z[s] * block[1 + j] for j, s in enumerate(self.others))
            ) / z[f]
            amounts.append(n)
            conc.append([x / volume[i] for x in n])
        return conc, amounts, volume, area

    def potentials(self, t, y):
        m = self.block
        charge = np.asarray(y[0 : len(self.nodes) * m : m]) * (FMOL * F)
        K = self.K0 + (t - self.t0) * self.K1
        return np.linalg.solve(K, charge)

    def junction_pa(self, t, junction):
        _, _, _, coef, bridge = junction
        if bridge is None:
            return coef
        spec, born = bridge
        a = _rops().aperture(spec.a0_m, spec.law, spec.tau_s, born, t)
        return tuple(a * c for c in coef)

    def rhs(self, t, y):
        z, rt, bath = self.z, self.rt, self.bath
        conc, _, _, area = self.concentrations(t, y)
        phi = self.potentials(t, y).tolist()
        nn = len(self.nodes)
        ns = len(z)
        dn = [[0.0] * ns for _ in range(nn)]  # fmol/s
        dq = [[] for _ in range(nn)]  # charge-rate terms (mol/s)
        heat = []
        for j, (_, i, o, _, _, rate, dc, perm) in enumerate(self.patches):
            phi_o = phi[o] if o >= 0 else 0.0
            v = phi[i] - phi_o
            u = F * v / rt
            c_in = conc[i]
            c_out = conc[o] if o >= 0 else bath
            a = area[j]
            for s in range(ns):
                flux = rfull.ghk_flux(perm[s] * a, z[s], u, c_in[s], c_out[s])
                dn[i][s] -= flux
                dq[i].append(-z[s] * flux)
                if o >= 0:
                    dn[o][s] += flux
                    dq[o].append(z[s] * flux)
            if rate:
                heat.append(0.5 * v * v * dc * 1e12)
        for _, a, b, k, law in self.faces:
            phi_a = phi[a] if a >= 0 else 0.0
            phi_b = phi[b] if b >= 0 else 0.0
            u = F * (phi_a - phi_b) / rt
            c_a = conc[a] if a >= 0 else bath
            c_b = conc[b] if b >= 0 else bath
            for s in range(ns):
                flux = rfull.access_flux(law, k[s], z[s], u, c_a[s], c_b[s])
                for x, sign in ((a, -1.0), (b, 1.0)):
                    if x >= 0:
                        dn[x][s] += sign * flux
                        dq[x].append(sign * z[s] * flux)
        for junction in self.junctions:
            _, a, b, _, _ = junction
            pa = self.junction_pa(t, junction)
            u = F * (phi[a] - phi[b]) / rt
            for s in range(ns):
                flux = rfull.ghk_flux(pa[s], z[s], u, conc[a][s], conc[b][s])
                dn[a][s] -= flux
                dn[b][s] += flux
                dq[a].append(-z[s] * flux)
                dq[b].append(z[s] * flux)
        for i, _, _, fill in self.clefts:
            if fill:
                for s in range(ns):
                    dn[i][s] += bath[s] * fill
                dq[i].append(self.supply_charge * fill)
        for i, current, carried in self.injection:
            for s, share in carried:
                dn[i][s] += share * current / F
            dq[i].append(current / F)
        m = self.block
        out = np.empty(nn * m + 1)
        for i in range(nn):
            out[i * m] = math.fsum(dq[i]) / FMOL
            for j, s in enumerate(self.others):
                out[i * m + 1 + j] = dn[i][s] / FMOL
        out[-1] = math.fsum(heat)
        return out

    def snapshot(self, t, y):
        """A record of the live tissue at (t, y)."""
        w = self.tissue.world
        conc, amounts, volume, area = self.concentrations(t, y)
        phi = self.potentials(t, y)
        dt = t - self.t0
        m = self.block
        record = dict(t=t, V={}, phi={}, cells={}, lumens={}, patches={}, junctions={})
        for i, node in enumerate(self.nodes):
            record["phi"][node] = float(phi[i])
            entry = dict(
                mM=list(conc[i]),
                amounts_fmol=list(amounts[i]),
                volume_pL=volume[i],
                charge_C=float(y[i * m]) * FMOL * F,
            )
            if i < self.ncell:
                record["V"][node] = float(phi[i])
                entry["background_fmol"] = self.background[i]
                record["cells"][node] = entry
            else:
                record["lumens"][node] = entry
        energy, plate = [], []
        for j, (name, i, o, _, cap0, _, dc, _) in enumerate(self.patches):
            v = float(phi[i] - (phi[o] if o >= 0 else 0.0))
            cap = cap0 + dc * dt
            record["patches"][name] = dict(area_m2=area[j], capacitance_F=cap, V=v)
            energy.append(0.5 * cap * v * v)
            if o < 0:
                plate.append(-cap * v)
        for junction in self.junctions:
            name, a, b, _, bridge = junction
            pa = self.junction_pa(t, junction)
            u = F * float(phi[a] - phi[b]) / self.rt
            current = F * math.fsum(
                self.z[s] * rfull.ghk_flux(pa[s], self.z[s], u, conc[a][s], conc[b][s])
                for s in range(len(self.z))
            )
            entry = dict(cells=(self.nodes[a], self.nodes[b]), current_A=current)
            if bridge is None:
                entry.update(kind="contact", gate=self.tissue.contact_state[name][1])
            else:
                spec, born = bridge
                entry.update(
                    kind="bridge",
                    gate=spec.gate,
                    aperture_m=_rops().aperture(spec.a0_m, spec.law, spec.tau_s, born, t),
                )
            record["junctions"][name] = entry
        # A junction slot that is not live reads gate 0 (the lead's addition to A.6 item 5).
        record["junction_gates"] = {
            name: record["junctions"][name]["gate"] if name in record["junctions"] else 0.0
            for name in [*w.contacts, *(d.bridge for d in w.divisions.values() if d.bridge)]
        }
        record.update(
            heat_pJ=float(y[-1]),
            capacitor_energy_J=math.fsum(energy),
            plate_charge_C=math.fsum(plate),
            phase=self.tissue.phases(),
        )
        return record


class _Tissue:
    """Liveness and the state of every slot between segments."""

    def __init__(self, world):
        self.world = world
        z = world.z
        self.follower = max(i for i, x in enumerate(z) if x != 0)
        self.others = [i for i in range(len(z)) if i != self.follower]
        self.cell_phase = {name: "pending" for name in world.cells}
        self.cleft_phase = {name: "pending" for name in world.clefts}
        self.patch_phase = {name: "pending" for name in world.patches}
        self.contact_phase = {name: "pending" for name in world.contacts}
        self.bridge_phase = {d.bridge: "pending" for d in world.divisions.values() if d.bridge}
        self.state = {}  # free node -> [charge (fmol), amounts of the other species (fmol)]
        self.volume = {}  # cell -> pL
        self.background = {}  # cell -> fmol
        self.patch_ref = {}  # patch -> (t_ref, area at t_ref, capacitance at t_ref)
        self.contact_state = {}  # contact -> (area, gate)
        self.bridge_state = {}  # bridge -> (cells, spec, birth)
        self.heat = 0.0

    def live_cells(self):
        return [x for x, s in self.cell_phase.items() if s == "live"]

    def live_clefts(self):
        return [x for x, s in self.cleft_phase.items() if s == "live"]

    def live_patches(self):
        return [x for x, s in self.patch_phase.items() if s == "live"]

    def live_faces(self):
        live = {BATH, *self.live_clefts()}
        return [x for x, f in self.world.faces.items() if all(n in live for n in f.nodes)]

    def live_contacts(self):
        return [x for x, s in self.contact_phase.items() if s == "live"]

    def live_bridges(self):
        return [x for x, s in self.bridge_phase.items() if s == "live"]

    def phases(self):
        return dict(
            cells=dict(self.cell_phase),
            clefts=dict(self.cleft_phase),
            patches=dict(self.patch_phase),
            contacts=dict(self.contact_phase),
            bridges=dict(self.bridge_phase),
        )

    def amounts(self, node):
        """Every species' amount of a live free node (the follower from the charge)."""
        z, block = self.world.z, self.state[node]
        n = [0.0] * len(z)
        for j, s in enumerate(self.others):
            n[s] = block[1 + j]
        x = self.background.get(node, 0.0)
        n[self.follower] = (
            block[0] - x - math.fsum(z[s] * block[1 + j] for j, s in enumerate(self.others))
        ) / z[self.follower]
        return n

    def start(self):
        """Founders at their initial potential (R-full's initial_state rule)."""
        w = self.world
        daughters = {x for d in w.divisions.values() for x in d.daughters}
        initial = {}
        for name, c in w.cells.items():
            if name in daughters:
                continue
            base = [
                (k, p)
                for k, p in w.patches.items()
                if p.cell == name and not math.isfinite(p.onset_s)
            ]
            if math.isfinite(c.initial_V):
                v0 = c.initial_V
            else:
                pa = [
                    math.fsum(p.permeability_m_s[s] * p.area_m2 for _, p in base)
                    for s in range(len(w.z))
                ]
                v0 = zero_current_potential(pa, c.mM, w.bath_mM, w.z, w.temperature_K)
            n = [x * c.volume_pL for x in c.mM]
            charge = math.fsum(p.capacitance_F for _, p in base) * v0 / (F * FMOL)
            background = charge - math.fsum(z * x for z, x in zip(w.z, n, strict=True))
            self.cell_phase[name] = "live"
            self.volume[name] = c.volume_pL
            self.background[name] = background
            self.state[name] = [charge, *(n[s] for s in self.others)]
            for k, p in base:
                self.patch_phase[k] = "live"
                self.patch_ref[k] = (0.0, p.area_m2, p.capacitance_F)
            initial[name] = dict(V=v0, background_fmol=background, charge_fmol=charge)
        for name, c in w.contacts.items():
            if all(self.cell_phase[x] == "live" for x in c.cells):
                self.contact_phase[name] = "live"
                self.contact_state[name] = (c.area_m2, c.gate)
        return initial

    def onsets(self, t):
        """Open the onset patches due at t, and their clefts (A.4)."""
        w = self.world
        opened = []
        for name, p in w.patches.items():
            if self.patch_phase[name] == "pending" and math.isfinite(p.onset_s) and p.onset_s <= t:
                if self.cell_phase[p.cell] != "live":
                    raise ValueError(f"onset of patch {name}: its cell {p.cell} is not live")
                if self.cleft_phase[p.node] == "live":
                    raise ValueError(f"onset of patch {name}: its cleft {p.node} is already open")
                cap = p.capacitance_F
                if math.isnan(cap):
                    cap = p.specific_capacitance_F_m2 * p.area_m2
                self.patch_phase[name] = "live"
                self.patch_ref[name] = (t, p.area_m2, cap)
                opened.append(name)
        for node in {w.patches[k].node for k in opened}:
            facing = [k for k in self.live_patches() if w.patches[k].node == node]
            volume = (
                w.clefts[node].gap_width_m
                * math.fsum(w.patches[k].area_m2 for k in facing)
                / 2.0
                / FMOL
            )
            self.cleft_phase[node] = "live"
            self.state[node] = [0.0, *(w.bath_mM[s] * volume for s in self.others)]
        return opened

    def divide(self, t, dname):
        """R-ops' map at the division's time, then the new liveness (A.6). Returns the pre-event
        R-ops snapshot, the R-ops Division applied and R-ops' result (R-ops' default
        magnitudes; only the result's values are used here)."""
        rops = _rops()
        w = self.world
        d = w.divisions[dname]
        seg = _Segment(self, t, t)
        y = self.pack(seg)
        conc, amounts, volume, area = seg.concentrations(t, y)
        cells, clefts, patches = {}, {}, {}
        for i, node in enumerate(seg.nodes):
            charge = self.state[node][0] * FMOL * F
            if i < seg.ncell:
                cells[node] = rops.Cell(
                    (0.0,) * len(w.z), tuple(amounts[i]), volume[i], self.background[node], charge
                )
            else:
                clefts[node] = rops.Cleft(tuple(amounts[i]), volume[i], charge)
        for name, _, _, area0, cap0, _, _, _ in seg.patches:
            p = w.patches[name]
            patches[name] = rops.Patch(p.cell, p.node, area0, cap0)
        contacts = {}
        for e in self.live_contacts():
            area_e, gate = self.contact_state[e]
            contacts[e] = rops.Contact(w.contacts[e].cells, area_e, (gate,))
        bridges = {}
        for b in self.live_bridges():
            cells_b, spec, born = self.bridge_state[b]
            a = rops.aperture(spec.a0_m, spec.law, spec.tau_s, born, t)
            bridges[b] = rops.Bridge(cells_b, a, (spec.gate,))
        snapshot = rops.Snapshot(
            w.species,
            w.z,
            w.temperature_K,
            {BATH: 0.0},
            cells,
            clefts,
            patches,
            contacts=contacts,
            bridges=bridges,
        )
        spec = d.bridge_spec
        division = rops.Division(
            d.parent,
            tuple(d.daughters),
            d.f,
            dict(d.patches),
            {},
            dict(d.contacts),
            dict(d.carriers),
            d.bridge,
            spec.a0_m if d.bridge else 0.0,
            (spec.gate,) if d.bridge else (1.0,),
        )
        result = rops.apply(snapshot, division)
        after = result.snapshot
        self.cell_phase[d.parent] = "retired"
        for k in d.patches:
            self.patch_phase[k] = "retired"
        for e in d.contacts:
            self.contact_phase[e] = "retired"
        for b in bridges:
            if d.parent in bridges[b].cells:
                self.bridge_phase[b] = "retired"
        for name in d.daughters:
            cell = after.cells[name]
            n = cell.amounts_fmol
            self.cell_phase[name] = "live"
            self.volume[name] = cell.volume_pL
            self.background[name] = cell.background_fmol
            self.state[name] = [cell.charge_C / (F * FMOL), *(float(n[s]) for s in self.others)]
        for k1, k2, _ in d.patches.values():
            for kd in (k1, k2):
                self.patch_phase[kd] = "live"
                self.patch_ref[kd] = (t, after.patches[kd].area_m2, after.patches[kd].capacitance_F)
        for e1, e2, _ in d.contacts.values():
            for ed in (e1, e2):
                self.contact_phase[ed] = "live"
                self.contact_state[ed] = (after.contacts[ed].area_m2, after.contacts[ed].gates[0])
        if d.bridge:
            self.bridge_phase[d.bridge] = "live"
            self.bridge_state[d.bridge] = (tuple(d.daughters), spec, t)
        return snapshot, division, result

    def pack(self, seg):
        return np.array([x for node in seg.nodes for x in self.state[node]] + [self.heat])

    def unpack(self, seg, y):
        m = seg.block
        for i, node in enumerate(seg.nodes):
            self.state[node] = [float(x) for x in y[i * m : (i + 1) * m]]
        self.heat = float(y[-1])

    def atol(self, seg, atol):
        out = []
        for i in range(len(seg.nodes)):
            kind = "cell" if i < seg.ncell else "cleft"
            out += [atol[f"{kind}_charge"]] + [atol[f"{kind}_amount"]] * len(self.others)
        return np.array(out + [atol["heat"]])


def ghk_current(v, pa, c_in, c_out, z, temperature_K):
    """Outward current (A) of a constant-field membrane at voltage v."""
    u = F * v / (R * temperature_K)
    return F * math.fsum(
        zs * rfull.ghk_flux(p, zs, u, a, b) for zs, p, a, b in zip(z, pa, c_in, c_out, strict=True)
    )


def zero_current_potential(pa, c_in, c_out, z, temperature_K, bracket=(-0.2, 0.2)):
    """The zero-current potential of a constant-field membrane (R-full's root rule)."""
    return brentq(
        lambda v: ghk_current(v, pa, c_in, c_out, z, temperature_K),
        *bracket,
        xtol=1e-15,
        rtol=4 * EPS,
    )


def _breakpoints(world, t_end, record):
    points = {0.0, t_end, *(t for t in record if 0.0 <= t <= t_end)}
    for p in world.patches.values():
        if math.isfinite(p.onset_s) and p.onset_s < t_end:
            points.add(p.onset_s)
        points |= {start for start, _ in p.schedule if 0.0 <= start < t_end}
    for d in world.divisions.values():
        if d.time_s < t_end:
            points.add(d.time_s)
        if d.bridge:
            end = _rops().closure_end(d.bridge_spec.law, d.bridge_spec.tau_s, d.time_s)
            if end < t_end:
                points.add(end)
    for inj in world.injections:
        p = inj.pulses
        if p.enabled:
            k = 0
            while p.onset(k) < t_end:
                t = p.onset(k)
                points |= {t, *(x for x in (t + p.sample_s, t + p.duration_s) if x <= t_end)}
                k += 1
    return sorted(points)


def _check_injections(world, t_end):
    life = lifetimes(world)
    for inj in world.injections:
        p = inj.pulses
        if not p.enabled:
            continue
        birth, death = life[inj.cell]
        k = 0
        while p.onset(k) < t_end:
            if p.onset(k) < birth or p.onset(k) + max(p.duration_s, p.sample_s) > death:
                raise ValueError(f"injection into {inj.cell} outside its living interval")
            k += 1


def _simulate(world, t_end, *, record=(), rtol=1e-10, method="Radau", atol=None):
    started = time.perf_counter()
    check_world(world)
    _check_injections(world, t_end)
    tolerances = dict(ATOL, **(atol or {}))
    tissue = _Tissue(world)
    initial = tissue.start()
    points = _breakpoints(world, t_end, record)
    record = set(record)
    pulse_of_onset, pulse_of_sample = [], []
    for inj in world.injections:
        p = inj.pulses
        onsets, samples = {}, {}
        if p.enabled:
            k = 0
            while p.onset(k) <= t_end:
                onsets[p.onset(k)] = k
                samples[p.onset(k) + p.sample_s] = k
                k += 1
        pulse_of_onset.append(onsets)
        pulse_of_sample.append(samples)
    onset_V = [{} for _ in world.injections]
    sample_V = [{} for _ in world.injections]
    at, events = {}, []
    applied = set()
    steps = 0

    def cell_potential(seg, t, y, cell):
        return float(seg.potentials(t, y)[seg.index[cell]])

    seg = None
    for t0, t1 in zip(points, points[1:], strict=False):
        for name, d in world.divisions.items():
            if name not in applied and d.time_s <= t0:
                before, mapping, result = tissue.divide(t0, name)
                events.append(
                    dict(time_s=t0, division=name, before=before, map=mapping, result=result)
                )
                applied.add(name)
        tissue.onsets(t0)
        seg = _Segment(tissue, t0, t1)
        y = tissue.pack(seg)
        for j, inj in enumerate(world.injections):
            if t0 in pulse_of_onset[j]:
                onset_V[j][pulse_of_onset[j][t0]] = cell_potential(seg, t0, y, inj.cell)
        if t0 in record:
            at[t0] = seg.snapshot(t0, y)
        sol = solve_ivp(
            seg.rhs, (t0, t1), y, method=method, rtol=rtol, atol=tissue.atol(seg, tolerances)
        )
        if not sol.success:
            raise RuntimeError(f"integration failed on [{t0}, {t1}]: {sol.message}")
        steps += sol.t.size - 1
        y = sol.y[:, -1].copy()
        tissue.unpack(seg, y)
        for j, inj in enumerate(world.injections):
            if t1 in pulse_of_sample[j]:
                sample_V[j][pulse_of_sample[j][t1]] = cell_potential(seg, t1, y, inj.cell)
    y = tissue.pack(seg)
    if t_end in record:
        at[t_end] = seg.snapshot(t_end, y)
    for j, inj in enumerate(world.injections):
        if t_end in pulse_of_onset[j]:
            onset_V[j][pulse_of_onset[j][t_end]] = cell_potential(seg, t_end, y, inj.cell)
    return TissueRun(
        world, at, onset_V, sample_V, events, initial, steps, time.perf_counter() - started
    )


def simulate_static(world, t_end, *, record=(), rtol=1e-10, method="Radau", atol=None):
    """Integrate a world without divisions from t = 0 to t_end; returns a TissueRun."""
    if world.divisions:
        raise ValueError("simulate_static runs a world without divisions (see simulate_divisions)")
    return _simulate(world, t_end, record=record, rtol=rtol, method=method, atol=atol)


def simulate_divisions(world, t_end, *, record=(), rtol=1e-10, method="Radau", atol=None):
    """Integrate a world with prescribed divisions (R-ops at each); returns a TissueRun.

    A world converted from an R-full egg is refused (the J2 bright line, design §10.1). Pass
    atol scaled to the world: the defaults (ATOL) are R-full's, for egg-scale charges."""
    if world.origin != ORIGIN_WORLD:
        raise ValueError(
            "simulate_divisions refuses a world converted from an R-full egg "
            "(the J2 bright line, design §10.1)"
        )
    return _simulate(world, t_end, record=record, rtol=rtol, method=method, atol=atol)


# ---------------------------------------------------------------- R-full's runner hook


def _rfull_snapshot(rec):
    """A record of the egg world in R-full's snapshot keys (Run.at)."""
    live = "cleft" in rec["lumens"]
    new = rec["patches"].get("new")
    cell = rec["cells"]["egg"]
    lumen = rec["lumens"].get("cleft")
    return dict(
        V=rec["V"]["egg"],
        phi_lumen=rec["phi"].get("cleft", 0.0),
        v_new=new["V"] if live else rec["V"]["egg"],
        area=new["area_m2"] if live else 0.0,
        c_new=new["capacitance_F"] if live else 0.0,
        cytosol_mM=list(cell["mM"]),
        lumen_mM=list(lumen["mM"]) if live else None,
        heat_pJ=rec["heat_pJ"],
        capacitor_energy_J=rec["capacitor_energy_J"],
        state=[
            cell["charge_C"] / (F * FMOL),
            *cell["amounts_fmol"][:2],
            *([lumen["charge_C"] / (F * FMOL), *lumen["amounts_fmol"][:2]] if live else [0.0] * 3),
            rec["heat_pJ"],
        ],
    )


def runner(egg, t_end, *, rtol=1e-10, method="Radau", record=()):
    """R-full's runner hook (rm_at, calibrate_old, calibrate_access, j1_readout): the egg run
    through R-tissue's static entry point; returns R-full's Run."""
    run = simulate_static(from_egg(egg), t_end, record=record, rtol=rtol, method=method)
    first = run.initial["egg"]
    at = {t: _rfull_snapshot(rec) for t, rec in run.at.items()}
    return rfull.Run(
        egg,
        first["background_fmol"],
        first["V"],
        dict(run.onset_V[0]),
        dict(run.sample_V[0]),
        at,
        run.steps,
        run.wall_s,
    )
