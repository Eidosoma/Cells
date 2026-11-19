"""The capacitor network of a world, solved densely at 60 digits (T4's independent method).

Written from FR-2's design statement 1 §12 ("a dense nodal capacitor solve of the state before and
after: nodes are the cells, then the outside nodes; held nodes sit at their potentials; charges are
the anchors plus F Σ z n; each active patch adds C (e_i − e_o)(e_i − e_o)ᵀ") and from
MEMBRANE_RETRIEVAL_DESIGN §2.2. No engine code is read.

**Constants** (the lead's ruling, 19 November 2026): the exact SI defining constants,
F = N_A e and R = N_A k_B, with CHARGE_PER_FMOL = F × 1e-15 C/fmol, MOL_PER_FMOL = 1e-15 and
M3_PER_PL = 1e-15, all at 60 digits.

**Conventions** (the declared inputs' own): a patch's voltage is V = φ_inside − φ_outside; its
inside plate holds +C V and its outside plate −C V. A node's charge is the sum of the plates on its
side. For a cell or a free node that is its **charge anchor, the declared initial charge**, moved by
the amounts: q = anchor + CHARGE_PER_FMOL Σ_s z_s (n_s − n_s,0). (The declared anchors equal
CHARGE_PER_FMOL (Σ z n_0 + the fixed-charge equivalent); ``anchor_consistency`` checks it.) A held
node sits at its potential, and its plates' charge is whatever its electrode and reservoir supply.
"""

from __future__ import annotations

import copy
from decimal import Decimal

from validation.core_seams.references import exact as X
from validation.core_seams.references.exact import context, dec

with context():
    FARADAY = X.dec(X.FARADAY)                     # C/mol
    GAS_CONSTANT = X.dec(X.GAS_CONSTANT)           # J/(mol K)
    MOL_PER_FMOL = Decimal("1e-15")
    M3_PER_PL = Decimal("1e-15")
    CHARGE_PER_FMOL = FARADAY * MOL_PER_FMOL       # C/fmol


class World:
    """Nodes, patches, ion amounts and valences: the declared state of a world, never an engine's.

    - nodes: {id: {"kind": "cell" | "free" | "held", "volume_pL", "anchor_C" (cell, free),
      "potential_V" (held), "reference_mM" {species: c} (held)}}
    - patches: {id: {"inside", "outside", "area_m2", "capacitance_F"}}
    - amounts: {node: {species: fmol}} for cells and free nodes
    - valences: {species: z}; T_K the temperature."""

    def __init__(self, nodes: dict, patches: dict, amounts: dict, valences: dict, T_K):
        self.nodes = copy.deepcopy(nodes)
        self.patches = copy.deepcopy(patches)
        self.amounts = {n: {s: dec(v) for s, v in a.items()} for n, a in amounts.items()}
        self.initial = {n: dict(a) for n, a in self.amounts.items()}
        self.valences = {s: int(z) for s, z in valences.items()}
        self.T_K = dec(T_K)
        with context():
            for p in self.patches.values():
                p["area_m2"] = dec(p["area_m2"])
                p["capacitance_F"] = dec(p["capacitance_F"])
            for nd in self.nodes.values():
                for key in ("volume_pL", "anchor_C", "potential_V"):
                    if key in nd and nd[key] is not None:
                        nd[key] = dec(nd[key])

    def copy(self) -> "World":
        w = World.__new__(World)
        w.nodes = copy.deepcopy(self.nodes)
        w.patches = copy.deepcopy(self.patches)
        w.amounts = {n: dict(a) for n, a in self.amounts.items()}
        w.initial = self.initial
        w.valences = dict(self.valences)
        w.T_K = self.T_K
        return w

    # ----------------------------------------------------------------------------------------
    def free_nodes(self) -> list:
        return [n for n, nd in self.nodes.items() if nd["kind"] != "held"]

    def held_nodes(self) -> list:
        return [n for n, nd in self.nodes.items() if nd["kind"] == "held"]

    def charge(self, node) -> Decimal:
        """A cell's or free node's charge (C): its anchor plus CHARGE_PER_FMOL Σ z (n − n_0)."""
        with context():
            q = dec(self.nodes[node].get("anchor_C", 0) or 0)
            n0 = self.initial.get(node, {})
            for s, n in self.amounts.get(node, {}).items():
                q += CHARGE_PER_FMOL * self.valences[s] * (n - n0.get(s, Decimal(0)))
            return q

    def laplacian(self) -> dict:
        """K[a][b] = Σ over patches of C (e_in − e_out)(e_in − e_out)ᵀ."""
        ids = list(self.nodes)
        K = {a: {b: Decimal(0) for b in ids} for a in ids}
        with context():
            for p in self.patches.values():
                i, o, C = p["inside"], p["outside"], p["capacitance_F"]
                K[i][i] += C
                K[o][o] += C
                K[i][o] -= C
                K[o][i] -= C
        return K

    def solve(self) -> dict:
        """Every node's potential (V): held nodes at theirs, the rest from K φ = q."""
        K = self.laplacian()
        free, held = self.free_nodes(), self.held_nodes()
        with context():
            phi_h = {h: dec(self.nodes[h]["potential_V"]) for h in held}
            A = [[K[a][b] for b in free] for a in free]
            rhs = [self.charge(a) - sum((K[a][h] * phi_h[h] for h in held), Decimal(0))
                   for a in free]
            x = X.solve(A, rhs)
            out = dict(phi_h)
            out.update(dict(zip(free, x, strict=True)))
            return out

    def voltage(self, phi: dict, patch) -> Decimal:
        p = self.patches[patch]
        with context():
            return phi[p["inside"]] - phi[p["outside"]]

    def energy_J(self, phi: dict) -> Decimal:
        """½ Σ C V² over the patches (J)."""
        with context():
            return sum((p["capacitance_F"] * (phi[p["inside"]] - phi[p["outside"]]) ** 2
                        for p in self.patches.values()), Decimal(0)) / 2

    def held_charge(self, phi: dict) -> dict:
        """Each held node's charge (K φ)_h, the plates on its side, which its clamp supplies (C)."""
        K = self.laplacian()
        with context():
            return {h: sum((K[h][b] * phi[b] for b in self.nodes), Decimal(0))
                    for h in self.held_nodes()}

    def chemical_G_pJ(self, nodes=None) -> Decimal:
        """RT Σ n (ln(n/V) − 1) over cells and free outside nodes, n/V in mM (pJ), 60 digits.
        (Standard parts cancel for every move the operator makes; §12's T6 term.)"""
        with context():
            RT = GAS_CONSTANT * self.T_K
            G = Decimal(0)
            for nd_id in (nodes if nodes is not None else self.free_nodes()):
                V = dec(self.nodes[nd_id]["volume_pL"])
                for _s, n in self.amounts.get(nd_id, {}).items():
                    if n > 0:
                        G += n * (((n / V).ln()) - 1)
            return RT * G * MOL_PER_FMOL * Decimal(10) ** 12


# --------------------------------------------------------------------------------------------
# Honest float64 floors (the F4 lesson: a tolerance below the engine's own rounding is no check)
# --------------------------------------------------------------------------------------------

UNIT_ROUNDOFF = Decimal(2) ** -53
K_OPS = 4          # a few roundings per product or difference
FLOOR_MODELS = ("absolute_storage", "increment_storage")


def charge_floor(world: World, node, model: str = "absolute_storage") -> Decimal:
    """The worst-case rounding of a float64 engine's charge of a cell or free node (C), under one
    of two storage models (the operator's code is not read, so both are registered):

    - ``absolute_storage``: the charge formed as F Σ z n + its fixed part, from stored absolute
      amounts: u [(S + 1) CHARGE_PER_FMOL Σ_s |z_s n_s| + |anchor| + Σ_h |K_mh φ_h|], S its
      species. The sum cancels: the declared cell's 213 fmol of ions hold a net 0.013 fmol, and a
      pool's 15 fmol a net 0 plus the carriers' 1e-4.
    - ``increment_storage``: the charge formed as the anchor plus F Σ z (n − n0), from stored
      increments (§3 names the carriers' write ``extracellular_amount_increment``):
      u [|anchor| + (S + 1) CHARGE_PER_FMOL Σ_s |z_s (n_s − n0_s)| + Σ_h |K_mh φ_h|]."""
    with context():
        nd = world.nodes[node]
        amounts = world.amounts.get(node, {})
        n0 = world.initial.get(node, {})
        S = len(amounts)
        if model == "absolute_storage":
            ions = sum((CHARGE_PER_FMOL * abs(world.valences[s]) * abs(n)
                        for s, n in amounts.items()), Decimal(0))
        elif model == "increment_storage":
            ions = sum((CHARGE_PER_FMOL * abs(world.valences[s]) * abs(n - n0.get(s, 0))
                        for s, n in amounts.items()), Decimal(0))
        else:
            raise ValueError(model)
        total = (S + 1) * ions + abs(dec(nd.get("anchor_C", 0) or 0))
        K = world.laplacian()
        for h in world.held_nodes():
            total += abs(K[node][h] * dec(world.nodes[h]["potential_V"]))
        return UNIT_ROUNDOFF * total


def inverse(world: World) -> dict:
    """K_ff⁻¹ over the cells and free nodes, column by column at 60 digits."""
    K = world.laplacian()
    free = world.free_nodes()
    A = [[K[a][b] for b in free] for a in free]
    out = {a: {} for a in free}
    with context():
        for j, b in enumerate(free):
            e = [Decimal(1) if i == j else Decimal(0) for i in range(len(free))]
            col = X.solve(A, e)
            for i, a in enumerate(free):
                out[a][b] = col[i]
    return out


def solve_floor(world: World, phi: dict) -> Decimal:
    """The dense solve's own rounding on any potential: u K_OPS × (free nodes) × max|φ| (V)."""
    with context():
        return UNIT_ROUNDOFF * K_OPS * len(world.free_nodes()) * max(abs(x) for x in phi.values())


def _absolute(world: World, inv: dict, phi: dict, model: str) -> tuple:
    """Each node's and each patch's floor against exact values: |K⁻¹| e + the solve's."""
    free = world.free_nodes()
    e = {n: charge_floor(world, n, model) for n in free}
    sf = solve_floor(world, phi)
    node = {}
    for m in world.nodes:
        node[m] = (Decimal(0) if world.nodes[m]["kind"] == "held"
                   else sum((abs(inv[m][n]) * e[n] for n in free), Decimal(0)) + sf)
    volt = {}
    for pid, p in world.patches.items():
        i, o = p["inside"], p["outside"]
        w = {n: (inv[i][n] if i in inv else Decimal(0)) - (inv[o][n] if o in inv else Decimal(0))
             for n in free}
        volt[pid] = sum((abs(w[n]) * e[n] for n in free), Decimal(0)) + 2 * sf
    return node, volt, e


def potential_floors(before: World, after: World, phi_before: dict, phi_after: dict,
                     changed: set, model: str = "absolute_storage") -> dict:
    """Floors on each potential and patch voltage before and after a half-step against exact
    values (V), and on each node's change of potential across it (an engine against itself).

    For the change, a node whose amounts did not move (``changed`` lists those that did) carries
    the same charge rounding before and after, so only the change of K⁻¹ acts on it; a changed
    node's roundings are independent."""
    Ib, Ia = inverse(before), inverse(after)
    nb, vb, eb = _absolute(before, Ib, phi_before, model)
    na, va, ea = _absolute(after, Ia, phi_after, model)
    free = after.free_nodes()
    sb, sa = solve_floor(before, phi_before), solve_floor(after, phi_after)
    change = {}
    with context():
        for m in after.nodes:
            if after.nodes[m]["kind"] == "held":
                change[m] = Decimal(0)
                continue
            d = Decimal(0)
            for n in free:
                if n in changed:
                    d += abs(Ia[m][n]) * ea[n] + abs(Ib[m][n]) * eb[n]
                else:
                    d += abs(Ia[m][n] - Ib[m][n]) * max(ea[n], eb[n])
            change[m] = d + sa + sb
    return {"change": change, "before": nb, "after": na, "voltage_before": vb,
            "voltage_after": va}
