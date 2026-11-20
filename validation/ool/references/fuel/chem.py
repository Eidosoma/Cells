"""The chemistry of option (d) without geometry, as exact parameters and ``ool_references.world@1``
documents (fuel note §3 (d), at tag ol4-fuel-note-2026-11-20).

**Species and moieties** (note §3 (d), "Moieties"). B (the activated building block), S (the spent
block), L1 and L2 (two amphiphiles) share the block's moiety ``block``; F (fuel) and W (waste)
share the fuel's moiety ``fuel``. Each species declares a standard potential per phase kind
(``solution`` for the pool, ``bilayer`` for the membrane), written exactly as exp(-mu0/k_BT). No
step carries a standard free energy of its own: every step's balance comes from these potentials.

**Places.** F and W are pool places only, held (a declared concentration) or finite (note §3 (d),
"Places"). B and S have a pool place and a membrane place. L1 and L2 have a membrane place, and a
pool place where a world declares their exchange.

**Steps** (all ``cells.stochastic_mass_action@1``, kinetics ``count_on_m`` for the membrane locus):
- ``f1``, locus pool: F + S -> B + W, the fuel recharging the spent block (note §3 (d));
- ``jB``, ``jS`` (and ``jL1``, ``jL2`` where declared), locus membrane: a molecule joins the
  membrane from its pool place; its leave is the reverse;
- ``a1``, ``a2``, locus membrane: B + L_i -> 2 L_i, catalysed by its own product L_i through the
  transition-state factor g = 1 + beta x_Li (beta > 0);
- ``d1``, ``d2``, locus membrane: L_i -> S, uncatalysed.

Worlds without fuel (the held-block worlds and (d0)) omit F, W and ``f1``.

**The reduced model's quantities** (note §2.3). With these potentials,
Delta1 = mu0_L(bilayer) - mu0_B(bilayer) and Delta2 = mu0_S(bilayer) - mu0_L(bilayer), so
e^Delta1 = em_B_bil/em_L_bil and e^Delta2 = em_L_bil/em_S_bil. The cycle's drive with held fuel and
waste is mu_F - mu_W = mu0_F - mu0_W + ln(c_F/c_W) (note §3, "Options"); the block's potentials
cancel around every closed cycle.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from fractions import Fraction

from ..world import WORLD_FORMAT

AVOGADRO = Fraction(602214076) * 10 ** 15
C0_MM = Fraction(1)
REGISTERED_ON = "2026-11-20"
SOURCE = "docs/ORIGIN_OF_LIFE_FUEL_DESIGN.md at tag ol4-fuel-note-2026-11-20"
BLOCK = ("B", "S", "L1", "L2")
LAW_ID = "cells.stochastic_mass_action@1"


def q(x) -> dict:
    """An exact quantity: the rational as a string beside its float."""
    x = Fraction(x)
    return {"exact": str(x), "float": float(x)}


def mu(exp_minus) -> dict:
    em = Fraction(exp_minus)
    return {"exp_minus": str(em), "float": -(math.log(em.numerator) - math.log(em.denominator))}


def volume_for_X(X) -> Fraction:
    """The volume (L) at which X = N_A V c0 equals X, with c0 = 1 mM."""
    return Fraction(X) / (AVOGADRO * C0_MM / 1000)


@dataclass(frozen=True)
class Chem:
    """Exact parameters of (d)'s chemistry. ``em_*`` are exp(-mu0/k_BT); rate constants are per
    second; ``X`` is the pool's N_A V c0. ``held`` maps a pool species to its held concentration
    (mM); every other pool place is finite. ``L_pool`` declares L1 and L2 pool places and joins."""

    em_B_sol: Fraction
    em_B_bil: Fraction
    em_S_sol: Fraction
    em_S_bil: Fraction
    em_L_bil: Fraction
    k_f: Fraction
    k_jB: Fraction
    k_jS: Fraction
    k1: Fraction
    k2: Fraction
    beta: Fraction
    X: Fraction
    held: dict = field(default_factory=dict)
    em_F_sol: Fraction = Fraction(1)
    em_W_sol: Fraction = Fraction(1)
    em_L_sol: Fraction = Fraction(1)
    k_jL: Fraction = Fraction(1)
    fuel: bool = True
    L_pool: bool = False

    def with_(self, **kw) -> "Chem":
        """A copy with some fields replaced (numbers as Fractions)."""
        return replace(self, **{k: v if isinstance(v, (bool, dict)) else Fraction(v) for k, v in kw.items()})

    # -- the reduced model's constants (note §2.3)
    @property
    def e_delta1(self) -> Fraction:
        return self.em_B_bil / self.em_L_bil

    @property
    def e_delta2(self) -> Fraction:
        return self.em_L_bil / self.em_S_bil

    def drive_exp(self) -> Fraction | None:
        """exp(mu_F - mu_W) with held fuel and waste, exactly; None unless both are held."""
        if not self.fuel or "F" not in self.held or "W" not in self.held:
            return None
        # mu_h = mu0_h + ln(c_h/c0); exp(mu0) = 1/em
        return (Fraction(self.held["F"]) / self.em_F_sol) / (Fraction(self.held["W"]) / self.em_W_sol)

    def block_drive_exp(self) -> Fraction | None:
        """exp(mu_B - mu_S) with B and S held in the pool (the held-block worlds); None otherwise."""
        if "B" not in self.held or "S" not in self.held:
            return None
        return (Fraction(self.held["B"]) / self.em_B_sol) / (Fraction(self.held["S"]) / self.em_S_sol)


def _species(sid: str, moieties: dict, **potentials) -> dict:
    return {"id": sid, "moieties": dict(moieties), "identity": "label_only",
            "standard_mu_RT": {kind: mu(v) for kind, v in potentials.items()}}


def _step(sid, locus, reactants, products, k, catalysts=()) -> dict:
    return {"id": sid, "law": LAW_ID, "locus": locus, "reactants": dict(reactants), "products": dict(products),
            "forward_rate_per_s": q(k),
            "transition_state_factor": [{"catalyst": c, "beta": str(Fraction(b)),
                                         "ddG_kT": math.log1p(float(Fraction(b)))} for c, b in catalysts]}


def species_documents(c: Chem) -> list:
    out = [_species("B", {"block": 1}, solution=c.em_B_sol, bilayer=c.em_B_bil),
           _species("S", {"block": 1}, solution=c.em_S_sol, bilayer=c.em_S_bil)]
    for L in ("L1", "L2"):
        if c.L_pool:
            out.append(_species(L, {"block": 1}, solution=c.em_L_sol, bilayer=c.em_L_bil))
        else:
            out.append(_species(L, {"block": 1}, bilayer=c.em_L_bil))
    if c.fuel:
        out += [_species("F", {"fuel": 1}, solution=c.em_F_sol), _species("W", {"fuel": 1}, solution=c.em_W_sol)]
    return out


def place_documents(c: Chem) -> list:
    """Membrane places first (B, S, L1, L2), then the pool's, in a fixed order."""
    out = [{"species": s, "phase": "membrane"} for s in BLOCK]
    pool = ["B", "S"] + (["L1", "L2"] if c.L_pool else []) + (["F", "W"] if c.fuel else [])
    for s in pool:
        d = {"species": s, "phase": "pool"}
        if s in c.held:
            d["held_mM"] = q(c.held[s])
        out.append(d)
    return out


def step_documents(c: Chem) -> list:
    out = []
    if c.fuel:
        out.append(_step("f1", "pool", {"F@pool": 1, "S@pool": 1}, {"B@pool": 1, "W@pool": 1}, c.k_f))
    out.append(_step("jB", "membrane", {"B@pool": 1}, {"B@membrane": 1}, c.k_jB))
    out.append(_step("jS", "membrane", {"S@pool": 1}, {"S@membrane": 1}, c.k_jS))
    if c.L_pool:
        out.append(_step("jL1", "membrane", {"L1@pool": 1}, {"L1@membrane": 1}, c.k_jL))
        out.append(_step("jL2", "membrane", {"L2@pool": 1}, {"L2@membrane": 1}, c.k_jL))
    for i in ("1", "2"):
        cats = [(f"L{i}@membrane", c.beta)] if c.beta != 0 else []
        out.append(_step(f"a{i}", "membrane", {"B@membrane": 1, f"L{i}@membrane": 1}, {f"L{i}@membrane": 2}, c.k1,
                         catalysts=cats))
    for i in ("1", "2"):
        out.append(_step(f"d{i}", "membrane", {f"L{i}@membrane": 1}, {"S@membrane": 1}, c.k2))
    return out


def world_document(wid: str, description: str, c: Chem, initial_state: dict, *, role_note: str = "",
                   extra: dict | None = None) -> dict:
    """A registered world without geometry (``ool_references.world@1``)."""
    doc = {
        "format": WORLD_FORMAT,
        "id": wid,
        "registered": REGISTERED_ON,
        "source": SOURCE,
        "description": description,
        "units": {"time": "s", "energy": "k_BT", "concentration": "mM", "volume": "L"},
        "temperature_K": 298.15,
        "standard_concentration_mM": q(C0_MM),
        "avogadro_per_mol": q(AVOGADRO),
        "phases": {"membrane": {"kind": "condensed"},
                   "pool": {"kind": "dilute", "volume_L": q(volume_for_X(c.X)), "X": str(Fraction(c.X))}},
        "species": species_documents(c),
        "places": place_documents(c),
        "regular_mixing_chi": [],
        "steps": step_documents(c),
        "initial_state": dict(initial_state),
        "conventions_required": ["free_energy_form", "condensed_measure", "membrane_kinetics", "lumen_volume",
                                 "empty_catalyst_phase", "last_molecule"],
        "probed_conventions": [{"condensed_measure": "multinomial", "last_molecule": "kept"}],
        "provenance": "unsourced: every value is a declared test parameter of OL5's fuel references",
    }
    if role_note:
        doc["note"] = role_note
    if extra:
        doc.update(extra)
    return doc
