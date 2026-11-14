"""R-ops: an independent reference of the S5 partition map, with the bridge's closure law.

Written from docs/CELL_DIVISION_S5_DESIGN.md (Appendix A.1, A.2, A.6 and A.7, with §3.2-§3.6
and §7.1) and the physics, not from engine code. numpy only, with its own dense nodal solve of
the capacitor network. R-tissue (validation/division/cleft_tissue_reference.py) applies it at
each division, and the engine's event map is compared with it (design §7.4 and §8.3 Q2:
64 eps x magnitude per quantity).

Units, as in Appendix A: SI, except amounts in fmol and volumes in pL (so n/V is in mM =
mol/m3), and free energies in pJ.

The map (A.6), for a parent P with live patches k (area fraction a_k to the first daughter D1)
and volume fraction f:
1. the pre-event potentials by A.2, and the patch charges q_k = C_k V_k;
2. the mismatch dq = sum_k (a_k - f) q_k, carried by declared species:
   delta_s = 1e15 t_s dq / (z_s F) fmol;
3. contents n_D1 = f n_P + delta, n_D2 = n_P - n_D1; volumes and backgrounds f, complement;
   the increment form: anchors f and complement, increments f Delta_P + delta and complement,
   the parent's increment moved out;
4. patches (area, capacitance) by a_k, populations (abundance by their patch's a_k, gates
   copied), contacts to neighbours (area by a_e, gate copied); the parent's @3 history moves to
   the retirement record;
5. liveness: P, its patches, populations and contacts retire; D1, D2, theirs and the bridge
   (aperture a_0) become live. Gates of junctions (the lead's addition to A.6 item 5, 13
   November): a contact that is not live (pending, or with a retired endpoint) reads gate 0; the
   bridge becomes live with its declared gate (1: fixed open, A.7); the daughter contacts e1 and
   e2 take g_e (step 4);
6. identities: Q_D1 = sum_k a_k q_k; potentials continuous; dq_b = 0 and dU = 0; material
   conserved; dG = G(D1) + G(D2) - G(P) >= 0 with G(n, V) = 1e-3 RT sum_s n_s (ln(n_s/V) - 1);
   the booked work W = dG + 1e12 (dU - sum_b phi_b dq_b).
A daughter amount <= 0 refuses the event (PartitionRefused); the input is never modified.

Readings of Appendix A taken here (also in the S5 references' HANDOFF):
* Node charges are carried explicitly (Cell.charge_C, Cleft.charge_C) and the daughters' are
  Q_D1 = f Q_P + dq and Q_D2 = Q_P - Q_D1, which is sum_k a_k q_k by A.6 step 6. A.1 writes a
  node's charge as 1e-15 F (sum z n + X); at egg scale that sum cancels about eight digits (R-full
  carries charge as state for the same reason), so it is reported only as a consistency identity
  ("charge_content_*").
* The increment form of A.6 step 3 applies to every split extensive quantity that has an anchor
  (design §3.2-§3.3): amounts, patch area and capacitance, and population abundance. Contact
  areas are declared (no increment) and split once.
* The parent's charge anchor (Cell.charge_reference_C, design §3.3) splits f and complement.
* Bridges in the snapshot are @3 junctions with an aperture and gates. A parent with a bridge
  whose aperture is above zero is refused (design §3.8: its closure must end first, so a second
  division of a daughter needs the linear law); a closed bridge of the parent retires with it,
  reads gate 0, and its history moves to the record.
* Junction gates are reported for every junction slot the event touches, before and after
  ("junction_gates_before", "junction_gates_after"), with 0 for a slot that is not live.
* The record holds every history entry of a retiring slot: the parent's patches, the
  populations on them, its contacts and its closed bridges; the post-event history holds zeros
  there, so record + post-event = pre-event exactly (the add-back of design §3.5).
* Magnitudes (for 64 eps x magnitude): the sum of the absolute values of the terms entering each
  quantity, where a solved potential enters with the componentwise forward-error scale of a
  backward-stable solve, |K_ff^-1| (|K_ff| |phi_f| + M_f + |K_fb| |phi_b|).
* The amendment to A.8 (the lead's ruling, 14 November): a cell's node charge, an input cell's and
  a daughter's alike, has the magnitude M_i = |Q_i| + |Q-bar_i| + 1e-15 F sum_s |z_s Delta_s,i|,
  with Q-bar_i its declared charge anchor and Delta_i its increments (for a daughter, its split
  anchor and the increments this map computes); a cleft's is |Q_c|. The term enters every
  potential's magnitude through |K_ff^-1| (above) and every output that depends on the charges
  or the potentials. apply(..., charge_term=False) gives the magnitudes without it.
* The bridge's closure law (A.7, design §4.1) is written here, beside the map that opens the
  bridge (aperture, bridge_diffusivities, bridge_conductance).
"""

import math
from dataclasses import dataclass, field

import numpy as np

F = 6.02214076e23 * 1.602176634e-19  # C/mol (exact SI product N_A e)
R = 6.02214076e23 * 1.380649e-23  # J/(mol K) (exact SI product N_A k_B)
EPS = float(np.finfo(float).eps)
TOLERANCE_EPS = 64  # Design A.8: pass at 64 eps x magnitude.
HISTORY_KINDS = (
    "membrane_transferred_fmol",  # [species] per patch
    "membrane_heat_pJ",  # per patch
    "junction_transferred_fmol",  # [species] per contact or bridge
    "junction_heat_pJ",  # per contact or bridge
    "channel_transferred_fmol",  # [species] per population
    "channel_heat_pJ",  # [species] per population
)


class PartitionRefused(ValueError):
    """The event is refused; the pre-event state stands (A.6 step 7)."""


# ---------------------------------------------------------------- state


@dataclass(frozen=True)
class Cell:
    """A live cell: declared anchors and state increments, as design §3.2 holds them."""

    reference_fmol: tuple  # anchor amounts per species
    increment_fmol: tuple  # increments per species; amounts = reference + increment
    volume_pL: float
    background_fmol: float  # fixed background X (fmol of charge equivalent)
    charge_C: float  # node charge Q (carried explicitly; module notes)
    charge_reference_C: float = 0.0  # declared charge anchor (split f, complement)

    @property
    def amounts_fmol(self):
        return np.add(self.reference_fmol, self.increment_fmol)


@dataclass(frozen=True)
class Cleft:
    """A live finite outside node (no background)."""

    amounts_fmol: tuple
    volume_pL: float
    charge_C: float


@dataclass(frozen=True)
class Patch:
    """A live patch between its cell and an outside node (a cleft or a held node)."""

    cell: str
    node: str
    area_reference_m2: float
    capacitance_reference_F: float
    area_increment_m2: float = 0.0
    capacitance_increment_F: float = 0.0

    @property
    def area_m2(self):
        return self.area_reference_m2 + self.area_increment_m2

    @property
    def capacitance_F(self):
        return self.capacitance_reference_F + self.capacitance_increment_F


@dataclass(frozen=True)
class Population:
    """A channel population on a patch: abundance (units) and gate values (intensive)."""

    patch: str
    abundance_reference: float
    abundance_increment: float = 0.0
    gates: tuple = ()

    @property
    def abundance(self):
        return self.abundance_reference + self.abundance_increment


@dataclass(frozen=True)
class Contact:
    """A junction between two cells (a neighbour contact): declared area, gate values."""

    cells: tuple  # (cell, cell)
    area_m2: float
    gates: tuple = ()


@dataclass(frozen=True)
class Bridge:
    """A cytoplasmic bridge (an @3 junction) between two cells, at its current aperture."""

    cells: tuple
    aperture_m: float
    gates: tuple = (1.0,)  # fixed open (A.7)


@dataclass(frozen=True)
class Snapshot:
    """The live tissue at one instant: what the map reads and what it returns."""

    species: tuple
    z: tuple
    temperature_K: float
    held: dict  # held node -> potential (V)
    cells: dict  # name -> Cell
    clefts: dict  # name -> Cleft
    patches: dict  # name -> Patch
    populations: dict = field(default_factory=dict)  # name -> Population
    contacts: dict = field(default_factory=dict)  # name -> Contact
    bridges: dict = field(default_factory=dict)  # name -> Bridge
    history: dict = field(default_factory=dict)  # kind -> {slot: value}


@dataclass(frozen=True)
class Division:
    """One declared division (design §3.1): the parent's slots mapped to the daughters'."""

    parent: str
    daughters: tuple  # (D1, D2)
    f: float  # volume fraction to D1
    patches: dict  # parent patch -> (patch of D1, patch of D2, a_k)
    populations: dict = field(default_factory=dict)  # parent population -> (on D1's, on D2's)
    contacts: dict = field(default_factory=dict)  # parent contact -> (D1-M, D2-M, a_e)
    carriers: dict = field(default_factory=dict)  # species -> transference number t_s
    bridge: str = ""  # the bridge between the daughters ("" for none)
    bridge_a0_m: float = 0.0
    bridge_gates: tuple = (1.0,)  # the bridge's declared gate: fixed open (A.7)


@dataclass
class Result:
    """The post-event snapshot, every output of A.6 steps 2-6, and their magnitudes."""

    snapshot: Snapshot
    values: dict
    magnitudes: dict
    identities: dict  # name -> (residual, magnitude): exact in real arithmetic

    def worst(self):
        """(name, residual / (EPS x magnitude)) of the identity furthest from exactness."""
        ratios = {
            k: float(np.max(np.abs(r) / np.maximum(m, np.finfo(float).tiny)) / EPS)
            for k, (r, m) in self.identities.items()
        }
        name = max(ratios, key=ratios.get)
        return name, ratios[name]


# ---------------------------------------------------------------- capacitor network (A.2)


def charge_term_C(cell, z):
    """|Q-bar| + 1e-15 F sum_s |z_s Delta_s| (C): the amendment to A.8's magnitude of a cell's
    node charge, from the cell's declared charge anchor and its increments (the lead's ruling,
    14 November)."""
    return abs(cell.charge_reference_C) + 1e-15 * F * math.fsum(
        abs(zs * d) for zs, d in zip(z, cell.increment_fmol, strict=True)
    )


def nodal_solve(free, held, edges, charges, extra=None):
    """Potentials of the capacitor network K = sum_k C_k e_k e_k^T (A.2).

    free: the free nodes (the solve's order); held: {node: potential}; edges: [(inside, outside,
    C)] over the live patches; charges: {free node: Q (C)}; extra: {free node: an additional
    magnitude of its charge (C)}, the cells' charge terms. K_ff phi_f = Q_f - K_fb phi_b.
    Returns (phi, magnitude): phi {node: V} over free and held nodes; magnitude {node: V}, for a
    free node |K_ff^-1| (|K_ff| |phi_f| + |Q_f| + extra_f + |K_fb| |phi_b|) (the componentwise
    forward-error scale of a backward-stable solve, with the charges' own terms carried through
    it), and |phi_b| for a held node.
    """
    index = {node: i for i, node in enumerate(free)}
    n = len(free)
    K = np.zeros((n, n))
    rhs = np.array([float(charges[node]) for node in free])
    rhs_scale = np.abs(rhs)
    for inside, outside, c in edges:
        a, b = index.get(inside), index.get(outside)
        if a is None and b is None:
            raise ValueError(f"a patch between two held nodes: {inside}, {outside}")
        for x, other in ((a, b), (b, a)):
            if x is None:
                continue
            K[x, x] += c
            if other is not None:
                K[x, other] -= c
        if a is None:
            rhs[b] += c * held[inside]
            rhs_scale[b] += c * abs(held[inside])
        elif b is None:
            rhs[a] += c * held[outside]
            rhs_scale[a] += c * abs(held[outside])
    for node, term in (extra or {}).items():
        rhs_scale[index[node]] += term
    if n and np.linalg.cond(K) > 1e12:
        raise PartitionRefused("a capacitor component without a held node (floating)")
    phi_f = np.linalg.solve(K, rhs) if n else np.zeros(0)
    scale = np.abs(np.linalg.inv(K)) @ (np.abs(K) @ np.abs(phi_f) + rhs_scale) if n else phi_f
    phi = dict(held)
    phi.update({node: float(phi_f[i]) for node, i in index.items()})
    magnitude = {node: abs(v) for node, v in held.items()}
    magnitude.update({node: float(scale[i]) for node, i in index.items()})
    return phi, magnitude


def network(snapshot):
    """(free nodes, edges, charges) of a snapshot: cells then clefts, in declared order."""
    free = [*snapshot.cells, *snapshot.clefts]
    edges = [(p.cell, p.node, p.capacitance_F) for p in snapshot.patches.values()]
    charges = {name: c.charge_C for name, c in snapshot.cells.items()}
    charges.update({name: c.charge_C for name, c in snapshot.clefts.items()})
    return free, edges, charges


def electrostatics(snapshot, charge_term=True):
    """A.2 on a snapshot: potentials, patch voltages and charges, plate charges, energy U (J),
    each with its magnitude (with the cells' charge terms when charge_term)."""
    free, edges, charges = network(snapshot)
    extra = None
    if charge_term:
        extra = {name: charge_term_C(c, snapshot.z) for name, c in snapshot.cells.items()}
    phi, mag_phi = nodal_solve(free, snapshot.held, edges, charges, extra)
    v, q, mag_v, mag_q = {}, {}, {}, {}
    for name, p in snapshot.patches.items():
        v[name] = phi[p.cell] - phi[p.node]
        mag_v[name] = mag_phi[p.cell] + mag_phi[p.node]
        q[name] = p.capacitance_F * v[name]
        mag_q[name] = abs(p.capacitance_F) * mag_v[name]
    plate = {b: 0.0 for b in snapshot.held}
    mag_plate = {b: 0.0 for b in snapshot.held}
    for name, p in snapshot.patches.items():
        if p.node in snapshot.held:  # q_b = (K phi)_b = sum C (phi_b - phi_i) = -sum q_k
            plate[p.node] -= q[name]
            mag_plate[p.node] += mag_q[name]
    energy = 0.5 * math.fsum(p.capacitance_F * v[k] ** 2 for k, p in snapshot.patches.items())
    mag_energy = math.fsum(
        abs(p.capacitance_F) * abs(v[k]) * mag_v[k] for k, p in snapshot.patches.items()
    )
    return dict(
        phi=phi,
        phi_mag=mag_phi,
        patch_V=v,
        patch_V_mag=mag_v,
        patch_q_C=q,
        patch_q_mag=mag_q,
        plate_C=plate,
        plate_mag=mag_plate,
        energy_J=energy,
        energy_mag=mag_energy,
    )


def free_energy_pJ(amounts_fmol, volume_pL, temperature_K):
    """G(n, V) = 1e-3 RT sum_s n_s (ln(n_s / V) - 1) (pJ; n in fmol, V in pL), A.6 step 6."""
    rt = R * temperature_K
    return 1e-3 * rt * math.fsum(n * (math.log(n / volume_pL) - 1.0) for n in amounts_fmol)


def free_energy_mag(amounts_fmol, amounts_mag, volume_pL, volume_mag, temperature_K):
    rt = R * temperature_K
    return (
        1e-3
        * rt
        * math.fsum(
            m * (abs(math.log(n / volume_pL)) + 1.0) + abs(n) * volume_mag / volume_pL
            for n, m in zip(amounts_fmol, amounts_mag, strict=True)
        )
    )


def relative_entropy_term(n, m):
    """m phi(n / m) = n ln(n / m) - n + m >= 0, accurate when n is close to m."""
    x = (n - m) / m
    if abs(x) < 1e-3:  # phi(1 + x) = sum_k>=2 (-1)^k x^k / (k (k - 1))
        return m * math.fsum((-1) ** k * x**k / (k * (k - 1)) for k in range(2, 10))
    return m * ((1.0 + x) * math.log1p(x) - x)


def unmixing_pJ(n1, v1, n2, v2, temperature_K):
    """The free-energy change of a split, in the cancellation-free form (always >= 0):
    1e-3 RT sum_s sum_i m_is phi(n_is / m_is), with n_s = n1_s + n2_s and
    m_is = n_s V_i / (V1 + V2); it equals G(D1) + G(D2) - G(P) when the parts sum to the whole."""
    rt = R * temperature_K
    w1 = v1 / (v1 + v2)
    w2 = v2 / (v1 + v2)
    terms = []
    for a, b in zip(n1, n2, strict=True):
        total = a + b
        terms += [relative_entropy_term(a, total * w1), relative_entropy_term(b, total * w2)]
    return 1e-3 * rt * math.fsum(terms)


def unmixing_leading_pJ(delta_fmol, parent_fmol, f, temperature_K):
    """Leading order of the unmixing term: 1e-3 RT sum_s delta_s^2 / (2 n_s f (1 - f))."""
    rt = R * temperature_K
    return (
        1e-3
        * rt
        * math.fsum(
            d * d / (2.0 * n * f * (1.0 - f)) for d, n in zip(delta_fmol, parent_fmol, strict=True)
        )
    )


# ---------------------------------------------------------------- the map (A.6)


def check_snapshot(snapshot):
    """Every live slot's endpoints are live: patches (cell, outside node), populations (patch),
    contacts and bridges (cells); history slots are live slots."""
    s = snapshot
    if len(s.species) != len(s.z):
        raise PartitionRefused("species and valences differ in length")
    outside = {*s.clefts, *s.held}
    for name, c in [*s.cells.items(), *s.clefts.items()]:
        if not c.volume_pL > 0.0:
            raise PartitionRefused(f"node {name} has a non-positive volume")
    for name, p in s.patches.items():
        if p.cell not in s.cells or p.node not in outside:
            raise PartitionRefused(f"patch {name} joins {p.cell} to {p.node}: not live")
        if not (p.capacitance_F > 0.0 and p.area_m2 > 0.0):
            raise PartitionRefused(f"patch {name} has a non-positive area or capacitance")
    for name, pop in s.populations.items():
        if pop.patch not in s.patches:
            raise PartitionRefused(f"population {name} is on patch {pop.patch}: not live")
        if not pop.abundance >= 0.0:
            raise PartitionRefused(f"population {name} has a negative abundance")
    for name, c in [*s.contacts.items(), *s.bridges.items()]:
        if len(c.cells) != 2 or not all(x in s.cells for x in c.cells):
            raise PartitionRefused(f"junction {name} joins {c.cells}: not live cells")
    for name, c in s.contacts.items():
        if not c.area_m2 >= 0.0:
            raise PartitionRefused(f"contact {name} has a negative area")
    slots = {*s.patches, *s.populations, *s.contacts, *s.bridges}
    for kind, entries in s.history.items():
        if kind not in HISTORY_KINDS:
            raise PartitionRefused(f"history kind {kind!r} is not one of {HISTORY_KINDS}")
        missing = set(entries) - slots
        if missing:
            raise PartitionRefused(f"history {kind} of slots that are not live: {sorted(missing)}")


def _check(snapshot, division):
    s, d = snapshot, division
    check_snapshot(s)
    if d.parent not in s.cells:
        raise PartitionRefused(f"parent {d.parent} is not a live cell")
    if len(d.daughters) != 2 or d.daughters[0] == d.daughters[1]:
        raise PartitionRefused("a division has two distinct daughters")
    for name in d.daughters:
        if name in s.cells or name in s.clefts or name in s.held:
            raise PartitionRefused(f"daughter {name} is already live")
    if not 0.0 < d.f < 1.0:
        raise PartitionRefused(f"f = {d.f} is outside (0, 1)")
    live = {k for k, p in s.patches.items() if p.cell == d.parent}
    if set(d.patches) != live:
        raise PartitionRefused(
            f"the patch map must cover the parent's live patches exactly: {sorted(live)}"
        )
    new_names = set(d.daughters)
    for k, (k1, k2, a) in d.patches.items():
        if not 0.0 < a < 1.0:
            raise PartitionRefused(f"a_k = {a} of patch {k} is outside (0, 1)")
        for name in (k1, k2):
            if name in s.patches or name in new_names:
                raise PartitionRefused(f"daughter patch {name} is already live or repeated")
            new_names.add(name)
    on_parent = {j for j, pop in s.populations.items() if pop.patch in live}
    if set(d.populations) != on_parent:
        raise PartitionRefused(
            f"the population map must cover the parent's populations: {sorted(on_parent)}"
        )
    for j1, j2 in d.populations.values():
        for name in (j1, j2):
            if name in s.populations or name in new_names:
                raise PartitionRefused(f"daughter population {name} is already live or repeated")
            new_names.add(name)
    touching = {e for e, c in s.contacts.items() if d.parent in c.cells}
    if set(d.contacts) != touching:
        raise PartitionRefused(
            f"the contact map must cover the parent's contacts: {sorted(touching)}"
        )
    for e, (e1, e2, a_e) in d.contacts.items():
        if not 0.0 <= a_e <= 1.0:
            raise PartitionRefused(f"a_e = {a_e} of contact {e} is outside [0, 1]")
        if d.parent == s.contacts[e].cells[0] == s.contacts[e].cells[1]:
            raise PartitionRefused(f"contact {e} joins the parent to itself")
        for name in (e1, e2):
            if name in s.contacts or name in s.bridges or name in new_names:
                raise PartitionRefused(f"daughter contact {name} is already live or repeated")
            new_names.add(name)
    for b, bridge in s.bridges.items():
        if d.parent in bridge.cells and bridge.aperture_m > 0.0:
            raise PartitionRefused(f"bridge {b} of the parent is open (aperture > 0)")
    if d.bridge:
        if d.bridge in s.bridges or d.bridge in s.contacts or d.bridge in new_names:
            raise PartitionRefused(f"bridge {d.bridge} is already live or repeated")
        if not (d.bridge_a0_m > 0.0 and math.isfinite(d.bridge_a0_m)):
            raise PartitionRefused("the bridge's aperture a_0 must be positive and finite")
        if not all(0.0 <= g <= 1.0 for g in d.bridge_gates):
            raise PartitionRefused("the bridge's gates must lie in [0, 1]")
    mismatch = any(a != d.f for _, _, a in d.patches.values())
    if mismatch or d.carriers:
        index = {name: i for i, name in enumerate(s.species)}
        if not d.carriers:
            raise PartitionRefused("mismatch carriers are required when some a_k differs from f")
        for name, t in d.carriers.items():
            if name not in index or s.z[index[name]] == 0:
                raise PartitionRefused(f"carrier {name} is not a charged species")
            if not t >= 0.0:
                raise PartitionRefused(f"carrier {name} has a negative transference number")
        if abs(math.fsum(d.carriers.values()) - 1.0) > 4 * EPS:
            raise PartitionRefused("the transference numbers must sum to 1")


def _split(total, fraction):
    """(fraction x total, total - that): A.6's first-daughter-then-complement form."""
    first = fraction * total
    return first, total - first


def apply(snapshot, division, *, charge_term=True):
    """The partition map of A.6 on one snapshot; returns a Result (the input is not modified).

    Raises PartitionRefused for an inadmissible division or a daughter amount <= 0 (A.6 step 7).
    charge_term: the magnitudes carry the cells' charge terms (A.8 as amended on 14 November);
    False gives the magnitudes without them (the values are the same either way).
    """
    s, d = snapshot, division
    _check(s, d)
    z = np.array(s.z, dtype=float)
    nspecies = len(s.species)
    f = d.f
    parent = s.cells[d.parent]
    d1, d2 = d.daughters
    values, mags, identities = {}, {}, {}

    # 1. Pre-event electrostatics.
    pre = electrostatics(s, charge_term)
    q, mag_q = pre["patch_q_C"], pre["patch_q_mag"]

    def term(cell):
        return charge_term_C(cell, s.z) if charge_term else 0.0

    m_parent = abs(parent.charge_C) + term(parent)  # The parent's charge magnitude (A.8).

    # 2. Mismatch charge and its carriers.
    dq = math.fsum((a - f) * q[k] for k, (_, _, a) in d.patches.items())
    mag_dq = math.fsum((abs(a) + f) * mag_q[k] for k, (_, _, a) in d.patches.items())
    delta = np.zeros(nspecies)
    mag_delta = np.zeros(nspecies)
    for i, name in enumerate(s.species):
        t = d.carriers.get(name, 0.0)
        if t:
            delta[i] = 1e15 * t * dq / (s.z[i] * F)
            mag_delta[i] = 1e15 * t * mag_dq / (abs(s.z[i]) * F)
    values.update(mismatch_C=dq, delta_fmol=delta)
    mags.update(mismatch_C=mag_dq, delta_fmol=mag_delta)

    # 3. Contents: amounts, the increment form, volumes, backgrounds, charges.
    ref_p = np.asarray(parent.reference_fmol, dtype=float)
    inc_p = np.asarray(parent.increment_fmol, dtype=float)
    n_p = ref_p + inc_p
    mag_n_p = np.abs(ref_p) + np.abs(inc_p)
    n1 = f * n_p + delta
    n2 = n_p - n1
    mag_n1 = f * mag_n_p + mag_delta
    mag_n2 = mag_n_p + mag_n1
    if not (np.all(np.isfinite(n1)) and np.all(np.isfinite(n2))):
        raise PartitionRefused("a non-finite daughter amount")
    if np.any(n1 <= 0.0) or np.any(n2 <= 0.0):
        raise PartitionRefused(f"a daughter amount <= 0 (n_D1 = {n1}, n_D2 = {n2})")
    ref1, ref2 = _split(ref_p, f)
    inc1 = f * inc_p + delta
    inc2 = inc_p - inc1
    mag_inc1 = f * np.abs(inc_p) + mag_delta
    mag_inc2 = np.abs(inc_p) + mag_inc1
    v1, v2 = _split(parent.volume_pL, f)
    x1, x2 = _split(parent.background_fmol, f)
    qref1, qref2 = _split(parent.charge_reference_C, f)
    charge1 = f * parent.charge_C + dq
    charge2 = parent.charge_C - charge1
    cell1 = Cell(tuple(ref1), tuple(inc1), v1, x1, charge1, qref1)
    cell2 = Cell(tuple(ref2), tuple(inc2), v2, x2, charge2, qref2)
    base1 = f * m_parent + mag_dq
    base2 = m_parent + base1
    mag_charge1 = base1 + term(cell1)  # Each daughter's own anchor and increments (A.8).
    mag_charge2 = base2 + term(cell2)
    values.update(
        amounts_D1_fmol=n1,
        amounts_D2_fmol=n2,
        reference_D1_fmol=ref1,
        reference_D2_fmol=ref2,
        increment_D1_fmol=inc1,
        increment_D2_fmol=inc2,
        moved_fmol={d.parent: -inc_p, d1: inc1, d2: inc2},
        volume_D1_pL=v1,
        volume_D2_pL=v2,
        background_D1_fmol=x1,
        background_D2_fmol=x2,
        charge_reference_D1_C=qref1,
        charge_reference_D2_C=qref2,
        charge_D1_C=charge1,
        charge_D2_C=charge2,
    )
    mags.update(
        amounts_D1_fmol=mag_n1,
        amounts_D2_fmol=mag_n2,
        reference_D1_fmol=f * np.abs(ref_p),
        reference_D2_fmol=(1.0 + f) * np.abs(ref_p),
        increment_D1_fmol=mag_inc1,
        increment_D2_fmol=mag_inc2,
        moved_fmol={d.parent: np.abs(inc_p), d1: mag_inc1, d2: mag_inc2},
        volume_D1_pL=f * parent.volume_pL,
        volume_D2_pL=(1.0 + f) * parent.volume_pL,
        background_D1_fmol=f * abs(parent.background_fmol),
        background_D2_fmol=(1.0 + f) * abs(parent.background_fmol),
        charge_reference_D1_C=f * abs(parent.charge_reference_C),
        charge_reference_D2_C=(1.0 + f) * abs(parent.charge_reference_C),
        charge_D1_C=mag_charge1,
        charge_D2_C=mag_charge2,
    )
    identities["amounts_sum"] = (n1 + n2 - n_p, mag_n1 + mag_n2 + mag_n_p)
    identities["reference_sum"] = (ref1 + ref2 - ref_p, (2.0 + 2.0 * f) * np.abs(ref_p))
    identities["moved_sum"] = (inc1 + inc2 - inc_p, mag_inc1 + mag_inc2 + np.abs(inc_p))
    identities["amounts_increment_form"] = (
        (ref1 + inc1) - n1,
        f * np.abs(ref_p) + mag_inc1 + mag_n1,
    )
    identities["volume_sum"] = (v1 + v2 - parent.volume_pL, 4.0 * parent.volume_pL)
    identities["background_sum"] = (
        x1 + x2 - parent.background_fmol,
        4.0 * abs(parent.background_fmol),
    )
    identities["charge_sum"] = (
        charge1 + charge2 - parent.charge_C,
        mag_charge1 + mag_charge2 + m_parent,
    )
    split_q = math.fsum(a * q[k] for k, (_, _, a) in d.patches.items())
    identities["charge_follows_patches"] = (
        charge1 - split_q,
        mag_charge1 + math.fsum(mag_q[k] for k in d.patches) + m_parent,
    )
    content = 1e-15 * F * (math.fsum(z * n_p) + parent.background_fmol)
    content_mag = 1e-15 * F * (math.fsum(np.abs(z) * mag_n_p) + abs(parent.background_fmol))
    for name, n_d, mag_n_d, x_d, charge_d, mag_charge_d in (
        (d1, n1, mag_n1, x1, charge1, mag_charge1),
        (d2, n2, mag_n2, x2, charge2, mag_charge2),
    ):
        own = 1e-15 * F * (math.fsum(z * n_d) + x_d)
        own_mag = 1e-15 * F * (math.fsum(np.abs(z) * mag_n_d) + 2.0 * abs(x_d))
        # Holds when the parent's explicit charge equals its content (to its rounding).
        identities[f"charge_content_{name}"] = (
            own - charge_d - (content - parent.charge_C) * (f if name == d1 else 1.0 - f),
            own_mag + mag_charge_d + content_mag + m_parent,
        )

    # 4. Patches, populations, contacts, the record.
    patches = {k: p for k, p in s.patches.items() if p.cell != d.parent}
    area_moved, cap_moved = {}, {}
    for k, (k1, k2, a) in d.patches.items():
        p = s.patches[k]
        aref1, aref2 = _split(p.area_reference_m2, a)
        ainc1, ainc2 = _split(p.area_increment_m2, a)
        cref1, cref2 = _split(p.capacitance_reference_F, a)
        cinc1, cinc2 = _split(p.capacitance_increment_F, a)
        patches[k1] = Patch(d1, p.node, aref1, cref1, ainc1, cinc1)
        patches[k2] = Patch(d2, p.node, aref2, cref2, ainc2, cinc2)
        area_moved.update({k: -p.area_increment_m2, k1: ainc1, k2: ainc2})
        cap_moved.update({k: -p.capacitance_increment_F, k1: cinc1, k2: cinc2})
        a1, a2 = _split(p.area_m2, a)
        c1, c2 = _split(p.capacitance_F, a)
        values.update({f"area_{k1}_m2": a1, f"area_{k2}_m2": a2})
        values.update({f"capacitance_{k1}_F": c1, f"capacitance_{k2}_F": c2})
        a_mag = abs(p.area_reference_m2) + abs(p.area_increment_m2)
        c_mag = abs(p.capacitance_reference_F) + abs(p.capacitance_increment_F)
        mags.update({f"area_{k1}_m2": a * a_mag, f"area_{k2}_m2": (1.0 + a) * a_mag})
        mags.update({f"capacitance_{k1}_F": a * c_mag, f"capacitance_{k2}_F": (1.0 + a) * c_mag})
        identities[f"area_sum_{k}"] = (a1 + a2 - p.area_m2, 4.0 * a_mag)
        identities[f"capacitance_sum_{k}"] = (c1 + c2 - p.capacitance_F, 4.0 * c_mag)
        identities[f"area_moved_sum_{k}"] = (
            ainc1 + ainc2 - p.area_increment_m2,
            4.0 * abs(p.area_increment_m2),
        )
        identities[f"capacitance_moved_sum_{k}"] = (
            cinc1 + cinc2 - p.capacitance_increment_F,
            4.0 * abs(p.capacitance_increment_F),
        )
        identities[f"capacitance_increment_form_{k}"] = (
            (cref1 + cinc1) - c1,
            4.0 * a * c_mag,
        )
    values.update(area_moved_m2=area_moved, capacitance_moved_F=cap_moved)
    populations = {j: pop for j, pop in s.populations.items() if j not in d.populations}
    units_moved = {}
    for j, (j1, j2) in d.populations.items():
        pop = s.populations[j]
        k1, k2, a = d.patches[pop.patch]
        nref1, nref2 = _split(pop.abundance_reference, a)
        ninc1, ninc2 = _split(pop.abundance_increment, a)
        populations[j1] = Population(k1, nref1, ninc1, tuple(pop.gates))
        populations[j2] = Population(k2, nref2, ninc2, tuple(pop.gates))
        units_moved.update({j: -pop.abundance_increment, j1: ninc1, j2: ninc2})
        n_mag = abs(pop.abundance_reference) + abs(pop.abundance_increment)
        identities[f"abundance_sum_{j}"] = (
            populations[j1].abundance + populations[j2].abundance - pop.abundance,
            4.0 * n_mag,
        )
        identities[f"units_moved_sum_{j}"] = (
            ninc1 + ninc2 - pop.abundance_increment,
            4.0 * abs(pop.abundance_increment),
        )
    values.update(units_moved=units_moved)
    contacts = {e: c for e, c in s.contacts.items() if e not in d.contacts}
    for e, (e1, e2, a_e) in d.contacts.items():
        c = s.contacts[e]
        other = c.cells[1] if c.cells[0] == d.parent else c.cells[0]
        area1, area2 = _split(c.area_m2, a_e)
        contacts[e1] = Contact((d1, other), area1, tuple(c.gates))
        contacts[e2] = Contact((d2, other), area2, tuple(c.gates))
        identities[f"contact_area_sum_{e}"] = (area1 + area2 - c.area_m2, 4.0 * abs(c.area_m2))
    bridges = {b: x for b, x in s.bridges.items() if d.parent not in x.cells}
    if d.bridge:
        bridges[d.bridge] = Bridge((d1, d2), d.bridge_a0_m, tuple(d.bridge_gates))
    retired_bridges = {b for b, x in s.bridges.items() if d.parent in x.cells}
    retiring = set(d.patches) | set(d.populations) | set(d.contacts) | retired_bridges
    # Junction gates: a slot that is not live reads 0 (the lead's addition to A.6 item 5).
    gates_before, gates_after = {}, {}
    for e, (e1, e2, _) in d.contacts.items():
        g = tuple(s.contacts[e].gates)
        zero = tuple(0.0 for _ in g)
        gates_before.update({e: g, e1: zero, e2: zero})
        gates_after.update({e: zero, e1: g, e2: g})
    for b in retired_bridges:
        g = tuple(s.bridges[b].gates)
        gates_before[b] = g
        gates_after[b] = tuple(0.0 for _ in g)
    if d.bridge:
        gates_before[d.bridge] = tuple(0.0 for _ in d.bridge_gates)
        gates_after[d.bridge] = tuple(d.bridge_gates)
    values.update(junction_gates_before=gates_before, junction_gates_after=gates_after)
    record, history = {}, {}
    for kind, entries in s.history.items():
        record[kind] = {slot: v for slot, v in entries.items() if slot in retiring}
        history[kind] = {
            slot: (np.zeros(np.shape(v)) if np.ndim(v) else 0.0) if slot in retiring else v
            for slot, v in entries.items()
        }
    values.update(record=record)

    # 5. Liveness and the post-event snapshot.
    cells = {name: c for name, c in s.cells.items() if name != d.parent}
    cells[d1] = cell1
    cells[d2] = cell2
    after = Snapshot(
        species=s.species,
        z=s.z,
        temperature_K=s.temperature_K,
        held=dict(s.held),
        cells=cells,
        clefts=dict(s.clefts),
        patches=patches,
        populations=populations,
        contacts=contacts,
        bridges=bridges,
        history=history,
    )

    # Node charges and their magnitudes (A.8 as amended), before and after.
    before_q = {name: c.charge_C for name, c in [*s.cells.items(), *s.clefts.items()]}
    before_m = {name: abs(c.charge_C) + term(c) for name, c in s.cells.items()}
    before_m.update({name: abs(c.charge_C) for name, c in s.clefts.items()})
    after_q = {name: c.charge_C for name, c in [*cells.items(), *s.clefts.items()]}
    after_m = {name: before_m[name] for name in cells if name not in (d1, d2)}
    after_m.update({d1: mag_charge1, d2: mag_charge2})
    after_m.update({name: abs(c.charge_C) for name, c in s.clefts.items()})
    values.update(charges_before_C=before_q, charges_after_C=after_q)
    mags.update(charges_before_C=before_m, charges_after_C=after_m)

    # 6. Identities of the post-event state.
    post = electrostatics(after, charge_term)
    phi0, phi1 = pre["phi"], post["phi"]
    m0, m1 = pre["phi_mag"], post["phi_mag"]
    values.update(
        potentials_before_V=dict(phi0),
        potentials_after_V=dict(phi1),
        patch_q_before_C=dict(q),
        patch_q_after_C=dict(post["patch_q_C"]),
        plate_before_C=dict(pre["plate_C"]),
        plate_after_C=dict(post["plate_C"]),
    )
    mags.update(potentials_before_V=dict(m0), potentials_after_V=dict(m1))
    for name in (d1, d2):
        identities[f"isopotential_{name}"] = (phi1[name] - phi0[d.parent], m1[name] + m0[d.parent])
    for name in [*cells, *s.clefts]:
        if name not in (d1, d2):
            identities[f"potential_unchanged_{name}"] = (
                phi1[name] - phi0[name],
                m1[name] + m0[name],
            )
    for k, (k1, k2, a) in d.patches.items():
        for kd, share in ((k1, a), (k2, 1.0 - a)):
            identities[f"patch_charge_{kd}"] = (
                post["patch_q_C"][kd] - share * q[k],
                post["patch_q_mag"][kd] + 2.0 * mag_q[k],
            )
    image = {b: post["plate_C"][b] - pre["plate_C"][b] for b in s.held}
    image_mag = {b: post["plate_mag"][b] + pre["plate_mag"][b] for b in s.held}
    d_energy = post["energy_J"] - pre["energy_J"]
    d_energy_mag = post["energy_mag"] + pre["energy_mag"]
    for b in s.held:
        identities[f"image_charge_{b}"] = (image[b], image_mag[b])
    identities["capacitor_energy"] = (d_energy, d_energy_mag)
    values.update(image_charge_C=image, capacitor_energy_change_J=d_energy)
    mags.update(image_charge_C=image_mag, capacitor_energy_change_J=d_energy_mag)

    temperature = s.temperature_K
    g1 = free_energy_pJ(n1, v1, temperature)
    g2 = free_energy_pJ(n2, v2, temperature)
    g0 = free_energy_pJ(n_p, parent.volume_pL, temperature)
    g_mag = (
        free_energy_mag(n1, mag_n1, v1, f * parent.volume_pL, temperature)
        + free_energy_mag(n2, mag_n2, v2, (1.0 + f) * parent.volume_pL, temperature)
        + free_energy_mag(n_p, mag_n_p, parent.volume_pL, parent.volume_pL, temperature)
    )
    d_g = g1 + g2 - g0
    gap = unmixing_pJ(n1, v1, n2, v2, temperature)
    identities["free_energy_forms"] = (d_g - gap, g_mag)
    work = d_g + 1e12 * (d_energy - math.fsum(s.held[b] * image[b] for b in s.held))
    work_mag = g_mag + 1e12 * (
        d_energy_mag + math.fsum(abs(s.held[b]) * image_mag[b] for b in s.held)
    )
    values.update(
        free_energy_change_pJ=d_g,
        free_energy_parts_pJ=(g1, g2, g0),
        unmixing_pJ=gap,
        unmixing_leading_pJ=unmixing_leading_pJ(delta, n_p, f, temperature),
        work_pJ=work,
    )
    mags.update(free_energy_change_pJ=g_mag, unmixing_pJ=g_mag, work_pJ=work_mag)
    return Result(after, values, mags, identities)


# ---------------------------------------------------------------- the bridge (A.7, design §4.1)


def aperture(a0_m, law, tau_s, birth_s, t):
    """a(t): a_0 before the birth t_b; then linear a_0 max(0, 1 - (t - t_b)/tau) or exponential
    a_0 exp(-(t - t_b)/tau). An infinite tau keeps a_0. The linear law is exactly 0 from its
    closure end t_b + tau on (the ratio (t - t_b)/tau can round below 1 there)."""
    if law not in ("linear", "exponential"):
        raise ValueError(f"closure law {law!r}")
    if t <= birth_s:
        return a0_m
    if law == "linear":
        if t >= closure_end(law, tau_s, birth_s):
            return 0.0
        return a0_m * max(0.0, 1.0 - (t - birth_s) / tau_s)
    return a0_m * math.exp(-(t - birth_s) / tau_s)


def closure_end(law, tau_s, birth_s):
    """The time the aperture reaches 0 (linear law), else infinity."""
    return birth_s + tau_s if law == "linear" else math.inf


def free_conductivity(composition_mM, z, diffusivity_m2_s, temperature_K):
    """sigma_free = (F^2 / RT) sum_s z_s^2 c_s D_s (S/m; c in mol/m3), A.7."""
    return (F * F / (R * temperature_K)) * math.fsum(
        zs * zs * c * dd for zs, c, dd in zip(z, composition_mM, diffusivity_m2_s, strict=True)
    )


def bridge_diffusivities(diffusivity_m2_s, sigma_cyt_S_m, composition_mM, z, temperature_K):
    """D_s^cyt = D_s sigma_cyt / sigma_free, one obstruction factor for every species (A.7)."""
    ratio = sigma_cyt_S_m / free_conductivity(composition_mM, z, diffusivity_m2_s, temperature_K)
    return tuple(dd * ratio for dd in diffusivity_m2_s)


def bridge_conductance(a_m, cyt_diffusivity_m2_s, composition_mM, z, temperature_K):
    """G_b = (F^2 / RT) sum_s z_s^2 c_s (2 a D_s^cyt) at equal concentrations c (S); it is
    2 a sigma_cyt at the declared composition (A.7)."""
    return 2.0 * a_m * free_conductivity(composition_mM, z, cyt_diffusivity_m2_s, temperature_K)
