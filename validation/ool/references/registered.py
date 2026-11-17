"""The registered OL1 worlds, written as exact parameters, and their JSON files.

The JSON files under ``designs/`` are the registration: the engine side reads them (the lead
relays their paths, never values). They are generated from the definitions below, and a test
holds the committed files byte-equal to the generator's output, so the two cannot drift.

**``ol1_wa``** (rows OL1-1 and OL1-4a, the kernel probe). One membrane with five species of its
own (A, B, C, D, E) and S, which also lives in the pool; the pool holds A (held, 1/4 mM) and S
and T (finite). Seven steps cover every kind of channel OL1 adds:
- x1, A@pool (held) -> A@membrane: a join from a held pool (reservoir work), catalysed by C;
- x2, S@pool -> S@membrane: a join from a finite pool (a dilute activity n/X);
- p1, 2 S@pool -> T@pool: a pool reaction, order two, so X = N_A V c0 enters the equilibrium;
- r1, A + B -> C: bimolecular in the membrane, the order changes;
- r2, 2 A -> D: an order-two draw without replacement;
- r3, A -> E: catalysed on the common state by E (autocatalysis, the discriminating case of
  §2.4), C (activation) and D (inhibition, beta = -1/2);
- r4, A + B + E -> C + E: termolecular, the catalyst E written on both sides (form (a)). It has
  r1's net change, so r1 and r4 are parallel channels (a two-cycle in the state graph).
Regular mixing on seven pairs; c0 = 1 mM, and the pool's volume makes X = 8.

**``ol1_wa_closed``** (rows OL1-2 and OL1-3, the closed world). The same membrane, pool and steps
without the held species and x1. Its moieties a = A + C + 2D + E, b = B + C and
s = S@membrane + S@pool + 2 T are conserved; from its initial state it has the states that
``probes.closed_world_states`` lists. B + C = 3 keeps the membrane non-empty, so no boundary
convention acts in it.

**``ol1_wb_m{M}``** (row OL1-4b, the large-system ladder). 2 S -> T in the pool at K = 1, the
dilute mass action §2.1 names, with no convention entering: the pool's free energy has one form,
and the membrane holds three inert molecules of L and takes no step. The pool's volume is
scaled with M (X = M) and the initial pool holds 2M molecules of S, so the concentrations are
the same on every rung. Its state space is one-dimensional (M + 1 states), so the master
equation is solved exactly on every rung.
"""

from __future__ import annotations

import json
import math
from fractions import Fraction
from pathlib import Path

from .world import WORLD_FORMAT, parse_world

REGISTERED_ON = "2026-11-17"
AVOGADRO = Fraction(602214076) * 10 ** 15
C0_MM = Fraction(1)
WB_RUNGS = (5, 20, 80, 320)
DESIGN_DIR = Path(__file__).resolve().parent / "designs"


def _q(x) -> dict:
    x = Fraction(x)
    return {"exact": str(x), "float": float(x)}


def _mu(exp_minus) -> dict:
    em = Fraction(exp_minus)
    return {"exp_minus": str(em), "float": -(math.log(em.numerator) - math.log(em.denominator))}


def _species(sid, moieties, **potentials):
    return {"id": sid, "moieties": dict(moieties), "identity": "label_only",
            "standard_mu_RT": {kind: _mu(v) for kind, v in potentials.items()}}


def _step(sid, locus, reactants, products, k, catalysts=()):
    return {"id": sid, "law": "cells.stochastic_mass_action@1", "locus": locus,
            "reactants": dict(reactants), "products": dict(products), "forward_rate_per_s": _q(k),
            "transition_state_factor": [
                {"catalyst": c, "beta": str(Fraction(b)), "ddG_kT": math.log1p(float(Fraction(b)))}
                for c, b in catalysts]}


def _volume_for_X(X) -> Fraction:
    """The volume (L) that makes X = N_A V c0 equal to X at c0 = C0_MM."""
    return Fraction(X) / (AVOGADRO * C0_MM / 1000)


def _world(wid, description, species, places, chi, steps, pool_X, initial_state):
    return {
        "format": WORLD_FORMAT,
        "id": wid,
        "registered": REGISTERED_ON,
        "description": description,
        "units": {"time": "s", "energy": "k_BT", "concentration": "mM", "volume": "L"},
        "temperature_K": 298.15,
        "standard_concentration_mM": _q(C0_MM),
        "avogadro_per_mol": _q(AVOGADRO),
        "phases": {"membrane": {"kind": "condensed"},
                   "pool": {"kind": "dilute", "volume_L": _q(_volume_for_X(pool_X)), "X": str(Fraction(pool_X))}},
        "species": species,
        "places": places,
        "regular_mixing_chi": [{"pair": [a, b], "chi": str(Fraction(v))} for a, b, v in chi],
        "steps": steps,
        "initial_state": dict(initial_state),
        "conventions_required": ["free_energy_form", "condensed_measure", "membrane_kinetics", "lumen_volume",
                                 "empty_catalyst_phase", "last_molecule"],
    }


WA_SPECIES = [
    _species("A", {"a": 1}, bilayer=1, solution=Fraction(1, 8)),
    _species("B", {"b": 1}, bilayer=1),
    _species("C", {"a": 1, "b": 1}, bilayer=2),
    _species("D", {"a": 2}, bilayer=Fraction(1, 2)),
    _species("E", {"a": 1}, bilayer=Fraction(3, 2)),
    _species("S", {"s": 1}, bilayer=4, solution=Fraction(1, 2)),
    _species("T", {"s": 2}, solution=Fraction(1, 2)),
]
WA_MEMBRANE_PLACES = [{"species": s, "phase": "membrane"} for s in ("A", "B", "C", "D", "E", "S")]
WA_POOL_PLACES = [{"species": "S", "phase": "pool"}, {"species": "T", "phase": "pool"}]
WA_HELD = {"species": "A", "phase": "pool", "held_mM": _q(Fraction(1, 4))}
WA_CHI = [("A", "B", 1), ("A", "C", Fraction(1, 2)), ("B", "D", -1), ("C", "E", 2), ("D", "E", Fraction(-1, 2)),
          ("S", "A", -1), ("S", "E", Fraction(1, 2))]
WA_INTERNAL_STEPS = [
    _step("x2", "membrane", {"S@pool": 1}, {"S@membrane": 1}, Fraction(1, 2)),
    _step("p1", "pool", {"S@pool": 2}, {"T@pool": 1}, 1),
    _step("r1", "membrane", {"A@membrane": 1, "B@membrane": 1}, {"C@membrane": 1}, 1),
    _step("r2", "membrane", {"A@membrane": 2}, {"D@membrane": 1}, Fraction(1, 2)),
    _step("r3", "membrane", {"A@membrane": 1}, {"E@membrane": 1}, 1,
          catalysts=[("E@membrane", 3), ("C@membrane", 1), ("D@membrane", Fraction(-1, 2))]),
    _step("r4", "membrane", {"A@membrane": 1, "B@membrane": 1, "E@membrane": 1},
          {"C@membrane": 1, "E@membrane": 1}, 2),
]
WA_POOL_X = 8


def world_documents() -> dict:
    """Every registered OL1 world, as the JSON documents the engine side reads."""
    docs = {}
    docs["ol1_wa"] = _world(
        "ol1_wa",
        "OL1 kernel-probe world: a membrane (A, B, C, D, E, S) and a pool (A held; S and T finite); joins "
        "from a held and a finite pool, a pool reaction, bimolecular, order-two, catalysed and "
        "termolecular membrane steps; ideal plus regular mixing.",
        WA_SPECIES, WA_MEMBRANE_PLACES + [WA_HELD] + WA_POOL_PLACES, WA_CHI,
        [_step("x1", "membrane", {"A@pool": 1}, {"A@membrane": 1}, 1, catalysts=[("C@membrane", 1)])]
        + WA_INTERNAL_STEPS, WA_POOL_X,
        {"A@membrane": 6, "B@membrane": 3, "C@membrane": 1, "D@membrane": 0, "E@membrane": 1, "S@membrane": 1,
         "S@pool": 6, "T@pool": 0})
    docs["ol1_wa_closed"] = _world(
        "ol1_wa_closed",
        "OL1 closed world: the ol1_wa membrane and pool without the held species and x1. Moieties "
        "a = A + C + 2D + E, b = B + C and s = S + 2T are conserved; the membrane is never empty.",
        WA_SPECIES, WA_MEMBRANE_PLACES + WA_POOL_PLACES, WA_CHI, WA_INTERNAL_STEPS, WA_POOL_X,
        {"A@membrane": 6, "B@membrane": 3, "C@membrane": 0, "D@membrane": 0, "E@membrane": 0, "S@membrane": 0,
         "S@pool": 4, "T@pool": 0})
    for M in WB_RUNGS:
        docs[f"ol1_wb_m{M}"] = _world(
            f"ol1_wb_m{M}",
            f"OL1 large-system ladder, rung M = {M}: 2 S -> T in the pool at K = 1 (exp(-mu0) 1 and 1), "
            f"forward rate 1/2 per s, X = {M}; an inert membrane of three L.",
            [_species("S", {"s": 1}, solution=1), _species("T", {"s": 2}, solution=1),
             _species("L", {"l": 1}, bilayer=1)],
            [{"species": "L", "phase": "membrane"}, {"species": "S", "phase": "pool"},
             {"species": "T", "phase": "pool"}],
            [],
            [_step("p1", "pool", {"S@pool": 2}, {"T@pool": 1}, Fraction(1, 2))], M,
            {"L@membrane": 3, "S@pool": 2 * M, "T@pool": 0})
    return docs


def variant_documents() -> dict:
    """Registered variants of the closed world, for row OL1-3: without any catalyst, and with
    every forward rate constant doubled (a uniform factor on every channel)."""
    import copy

    base = world_documents()["ol1_wa_closed"]
    out = {}
    unc = copy.deepcopy(base)
    unc["id"] = "ol1_wa_closed_uncatalysed"
    unc["description"] = "ol1_wa_closed with every catalyst removed (row OL1-3a)."
    for st in unc["steps"]:
        st["transition_state_factor"] = []
    out[unc["id"]] = unc
    x2 = copy.deepcopy(base)
    x2["id"] = "ol1_wa_closed_x2"
    x2["description"] = "ol1_wa_closed with every forward rate constant doubled (row OL1-3b)."
    for st in x2["steps"]:
        st["forward_rate_per_s"] = _q(2 * Fraction(st["forward_rate_per_s"]["exact"]))
    out[x2["id"]] = x2
    return out


def refusal_documents() -> dict:
    """Declarations the engine must refuse at parse (row OL1-4d), each ol1_wa with one defect.

    The reference's own parser refuses every one (``world.parse_world``); the tests hold that."""
    import copy

    base = world_documents()["ol1_wa"]

    def variant(rid, why, edit):
        doc = copy.deepcopy(base)
        doc["id"] = f"refuse_{rid}"
        doc["description"] = f"Must be refused: {why}."
        edit(doc)
        return doc

    def step(doc, sid):
        return next(s for s in doc["steps"] if s["id"] == sid)

    out = {}
    cases = [
        ("coefficient", "r1 written A + B -> 2 C, a coefficient off by one (moieties a and b unbalanced)",
         lambda d: step(d, "r1")["products"].update({"C@membrane": 2})),
        ("four_reactants", "r4 with four reactant molecules (2 A + B + E)",
         lambda d: step(d, "r4")["reactants"].update({"A@membrane": 2}) or step(d, "r4")["products"].update(
             {"C@membrane": 1, "E@membrane": 1, "A@membrane": 1})),
        ("four_products", "a step with four product molecules, 2 T -> 4 S in the pool",
         lambda d: d["steps"].append({**copy.deepcopy(step(d, "p1")), "id": "p4", "reactants": {"T@pool": 2},
                                      "products": {"S@pool": 4}})),
        ("non_integer", "r1 with a coefficient 1.5",
         lambda d: step(d, "r1")["reactants"].update({"A@membrane": 1.5})),
        ("dilute_catalyst", "p1 catalysed by a pool place (a dilute catalysing phase, refused by §0.2a)",
         lambda d: step(d, "p1")["transition_state_factor"].append(
             {"catalyst": "T@pool", "beta": "1", "ddG_kT": math.log1p(1.0)})),
        ("chi_diagonal", "regular mixing with a nonzero diagonal chi_AA",
         lambda d: d["regular_mixing_chi"].append({"pair": ["A", "A"], "chi": "1"})),
        ("changes_nothing", "a step E -> E",
         lambda d: d["steps"].append({**copy.deepcopy(step(d, "r3")), "id": "r0", "reactants": {"E@membrane": 1},
                                      "products": {"E@membrane": 1}, "transition_state_factor": []})),
        ("wrong_locus", "x2 (pool to membrane) declared with locus pool",
         lambda d: step(d, "x2").update({"locus": "pool"})),
        ("own_delta_G", "r1 carrying a standard free energy of its own",
         lambda d: step(d, "r1").update({"standard_delta_G_RT": -1.0})),
    ]
    for rid, why, edit in cases:
        out[f"refuse_{rid}"] = variant(rid, why, edit)
    return out


def canonical_bytes(doc: dict) -> bytes:
    """The registered byte form: JSON, one-space indent, keys in insertion order, no trailing newline."""
    return json.dumps(doc, indent=1).encode()


def write_designs(out_dir: str | Path, *, exist_ok: bool = False) -> list[Path]:
    """Write every registered world file into out_dir (``designs/`` holds the committed copies)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=exist_ok)
    paths = []
    for wid, doc in {**world_documents(), **variant_documents()}.items():
        parse_world(doc)  # every registered world parses under the reference's own rules
        p = out / f"{wid}.world.json"
        p.write_bytes(canonical_bytes(doc))
        paths.append(p)
    (out / "refusals").mkdir(exist_ok=True)
    for rid, doc in refusal_documents().items():
        p = out / "refusals" / f"{rid}.world.json"
        p.write_bytes(canonical_bytes(doc))
        paths.append(p)
    return paths


def registered_world(wid: str):
    """A registered world, read from its committed file."""
    from .world import load_world

    return load_world(DESIGN_DIR / f"{wid}.world.json")
