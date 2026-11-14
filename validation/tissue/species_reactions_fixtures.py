"""Small worlds for local_species_reactions@1 (D152 version 1, the shared-inventory design).

All values are synthetic. Every world is D150's quiescent species-only world
(secreted_species_fixtures.world: passive cells, every node at the bath's ion composition with a
zero charge anchor, zero ion diffusivity on every face), so no ion moves. Its species S is one of
the network's species; the others are declared by the engine's helper
(cells.core.inventory_species), a neutral, membrane-impermeant row each, at a trace background
with a species-scale material floor and a pre-formed (resolved) profile where the network acts.

* species_world: the base world (one cell, its finite node ecs_0, the held bath; faces optional)
  with more inventory species;
* enzyme_network: the canonical small network on S, E, C and P, every law and node kind once (the
  passive binding E + S <-> C and the catalytic step C -> E + P in the cell, Michaelis-Menten S -> P
  catalysed by E at ecs_0, a zeroth-order source of S in the cell and a first-order sink of P at
  ecs_0 under Hill inhibition by S), at the 7-species cap (3 ions, S, E, C, P);
* with_reactions: the operator's block and its schedule on a composite definition;
* the guard worlds of §3.4 (face-free: the network is the only energy flow): driven_only,
  passive_relaxation, enzyme_recipe (probe 2d's share case; resolved for the class switch),
  crossing (probe 2e's quadrature case), reversal_onset (probe 2g's known limit, at the first step
  or a mid-run switch-on); and mixed_chain, C2's heredity chain with a reacting pair.
"""

import copy
import math

from cells.core.inventory_species import add_inventory_species
from validation.tissue import secreted_species_fixtures as fx

REACTIONS = "local_species_reactions@1"
PASSIVE = "ideal_detailed_balance_mass_action@1"
TRACE_mM = fx.TRACE_mM
FLOOR_FMOL = fx.FLOOR_FMOL
D_SPECIES = fx.D_S
NETWORK_SPECIES = ("S", "E", "C", "P")
# A resolved profile of the enzyme network where it acts (mM); everything else at the trace.
ENZYME_PROFILE = dict(
    S=dict(cell_0=1e-3, ecs_0=5e-4),
    E=dict(cell_0=1e-4, ecs_0=1e-4),
    C=dict(cell_0=1e-5),
    P=dict(cell_0=1e-5, ecs_0=1e-5),
)


def species_world(extra=("E", "C", "P"), *, profile=None, faces=True, **kwargs):
    """fx.world (S declared) with the neutral species `extra` added; profile {species: {node: mM}}.

    faces=False removes every face (the face-free world: the network is the only flow).
    kwargs go to fx.world (cells, nodes, contacts, dt, end, solver, observation_times, ...)."""
    profile = dict(profile or {})
    if not faces:
        kwargs["faces"] = ()
    raw = fx.world(concentrations_mM=profile.get(fx.SPECIES), **kwargs)
    for name in extra:
        raw = add_inventory_species(
            raw,
            name,
            trace_mM=TRACE_mM,
            diffusivity_m2_per_s=D_SPECIES,
            floor_fmol=FLOOR_FMOL,
            concentrations_mM=profile.get(name),
        )
    return raw


def species(name, *, moieties=None, mu=0.0, catalogue=None, evidence=None):
    return dict(
        id=name, moieties=moieties, standard_mu_RT=mu, catalogue=catalogue, evidence=evidence
    )


def mass_action(name, sites, reactants, products, k, factors=()):
    return dict(
        id=name,
        sites=copy.deepcopy(sites),
        reactants=dict(reactants),
        products=dict(products),
        law="mass_action",
        rate_constant=k,
        factors=list(factors),
    )


def michaelis_menten(name, sites, substrate, products, rate, km, *, catalyst=None, factors=()):
    """rate: k_cat (1/s) with a catalyst, V_max (mM/s) without (the law's two keys, ruling Q8)."""
    key = "catalytic_rate_per_s" if catalyst is not None else "max_rate_mM_per_s"
    return {
        "id": name,
        "sites": copy.deepcopy(sites),
        "reactants": {substrate: 1},
        "products": dict(products),
        "law": "michaelis_menten",
        "catalyst": catalyst,
        key: rate,
        "saturation_mM": km,
        "factors": list(factors),
    }


def passive(name, sites, reactants, products, kf):
    return dict(
        id=name,
        sites=copy.deepcopy(sites),
        reactants=dict(reactants),
        products=dict(products),
        law=PASSIVE,
        forward_rate_per_s=kf,
        factors=[],
    )


def hill(law, name, half_saturation_mM, coefficient):
    return dict(
        law=law, species=name, half_saturation_mM=half_saturation_mM, hill_coefficient=coefficient
    )


def with_reactions(raw, species_list, reactions, controls, *, c0=1.0):
    """controls: (reaction id, site or None, [(time, multiplier), ...])."""
    out = copy.deepcopy(raw)
    out["model"]["operators"].append(
        dict(
            law=REACTIONS,
            standard_concentration_mM=c0,
            species=copy.deepcopy(list(species_list)),
            reactions=copy.deepcopy(list(reactions)),
        )
    )
    out["experiment"]["reaction_controls"] = [
        dict(
            reaction_id=r,
            site=site,
            schedule=[dict(time=t, multiplier=m) for t, m in changes],
        )
        for r, site, changes in controls
    ]
    return out


def enzyme_species(*, mu=(0.0, 0.0, -2.0, -1.0)):
    """S, E, C and P with moieties X (substrate) and Y (enzyme): S = X, E = Y, C = XY, P = X."""
    moieties = dict(S={"X": 1}, E={"Y": 1}, C={"X": 1, "Y": 1}, P={"X": 1})
    return [
        species(name, moieties=moieties[name], mu=value)
        for name, value in zip(NETWORK_SPECIES, mu, strict=True)
    ]


def enzyme_reactions():
    cell, node = {"cells": ["cell_0"]}, {"outside": ["ecs_0"]}
    return [
        passive("binding", cell, {"E": 1, "S": 1}, {"C": 1}, 10.0),
        mass_action("catalysis", cell, {"C": 1}, {"E": 1, "P": 1}, 1.0),
        michaelis_menten("conversion", node, "S", {"P": 1}, 1.0, 5e-4, catalyst="E"),
        mass_action("supply", cell, {}, {"S": 1}, 1e-4),
        mass_action(
            "removal", node, {"P": 1}, {}, 0.5, factors=[hill("hill_inhibition", "S", 1e-3, 2.0)]
        ),
    ]


def enzyme_network(multipliers=None, *, c0=1.0, mu=(0.0, 0.0, -2.0, -1.0), **kwargs):
    """The canonical network (module docstring) on species_world, every multiplier `multipliers`
    ({reaction id: value}, default 1) from time 0. kwargs go to species_world."""
    kwargs.setdefault("profile", ENZYME_PROFILE)
    raw = species_world(**kwargs)
    reactions = enzyme_reactions()
    values = dict.fromkeys((r["id"] for r in reactions), 1.0) | dict(multipliers or {})
    controls = [(r["id"], None, [(0.0, values[r["id"]])]) for r in reactions]
    return with_reactions(raw, enzyme_species(mu=mu), reactions, controls, c0=c0)


def two_factor_network(**kwargs):
    """The enzyme network with both factor kinds: the supply activated by C and inhibited by P
    (two factors), the removal inhibited by S (one factor and one padded slot)."""
    raw = enzyme_network(**kwargs)
    block = raw["model"]["operators"][0]
    supply = next(r for r in block["reactions"] if r["id"] == "supply")
    supply["factors"] = [
        hill("hill_activation", "C", 2e-5, 1.5),
        hill("hill_inhibition", "P", 5e-5, 2.0),
    ]
    return raw


def without_reactions(raw):
    """The same composite definition without the reaction operator and its schedule."""
    plain = copy.deepcopy(raw)
    plain["model"]["operators"] = [
        block for block in plain["model"]["operators"] if block["law"] != REACTIONS
    ]
    del plain["experiment"]["reaction_controls"]
    return plain


# ------------------------------------------------------------------ guard worlds (design §3.4)

KD_mM, KON = 1e-3, 1e3  # Probe 2d's and 2g's binding: K_d (mM) and k_on (1/(mM s)).


def always(names, value=1.0):
    """Every reaction at one multiplier from time 0 (controls for with_reactions)."""
    return [(name, None, [(0.0, value)]) for name in names]


def face_free_network(extra, species_list, reactions, controls, *, profile, end, dt, c0=1.0, **kw):
    """A face-free species-only world (§3.4, guard 1): one 1 pL cell and its finite node joined only
    by their contact patch, so the network is the world's only energy flow."""
    kw.setdefault("observation_times", fx.grid_times(end, dt, end / 4))
    raw = species_world(extra, profile=profile, faces=False, end=end, dt=dt, **kw)
    return with_reactions(raw, species_list, reactions, controls, c0=c0)


def driven_only(*, end=0.05, dt=1e-3, **kw):
    """Driven routes only: S -> P and 0 -> S in the cell, P -> 0 under Hill inhibition at ecs_0."""
    cell, node = {"cells": ["cell_0"]}, {"outside": ["ecs_0"]}
    reactions = [
        mass_action("convert", cell, {"S": 1}, {"P": 1}, 1.0),
        mass_action("supply", cell, {}, {"S": 1}, 1e-4),
        mass_action(
            "remove", node, {"P": 1}, {}, 0.5, factors=[hill("hill_inhibition", "S", 1e-3, 2.0)]
        ),
    ]
    names = [r["id"] for r in reactions]
    profile = dict(S=dict(cell_0=1e-3, ecs_0=5e-4), P=dict(cell_0=1e-5, ecs_0=1e-5))
    moieties = [species("S", moieties={"X": 1}), species("P", moieties={"X": 1}, mu=-1.0)]
    return face_free_network(
        ("P",), moieties, reactions, always(names), profile=profile, end=end, dt=dt, **kw
    )


def passive_relaxation(*, end=30.0, dt=0.1, ratio=10.0, **kw):
    """A closed passive S <-> P (K = ratio) in the cell, from equal concentrations (1e-3 mM)."""
    reactions = [passive("relax", {"cells": ["cell_0"]}, {"S": 1}, {"P": 1}, 1.0)]
    moieties = [
        species("S", moieties={"X": 1}),
        species("P", moieties={"X": 1}, mu=-math.log(ratio)),
    ]
    profile = dict(S=dict(cell_0=1e-3), P=dict(cell_0=1e-3))
    return face_free_network(
        ("P",), moieties, reactions, always(["relax"]), profile=profile, end=end, dt=dt, **kw
    )


def enzyme_recipe(trace_mM, *, end=1.0, dt=0.025, catalysis=None, resolved=False, **kw):
    """Probe 2d's recipe in the cell: passive E + S <-> C (k_on 1e3 /(mM s), K_d 1e-3 mM, c0 1 mM)
    and driven C -> E + P (1/s), E at 1e-4 mM and S at 1e-3 mM; C and P at `trace_mM` (a passive
    switch-on from the trace at a mixed node, the share's case), or pre-formed at 1e-5 mM
    (resolved). catalysis: the catalytic step's schedule [(time, multiplier), ...] (default on)."""
    cell = {"cells": ["cell_0"]}
    reactions = [
        passive("binding", cell, {"E": 1, "S": 1}, {"C": 1}, KON * 1.0),
        mass_action("catalysis", cell, {"C": 1}, {"E": 1, "P": 1}, 1.0),
    ]
    level = 1e-5 if resolved else trace_mM
    profile = dict(
        S=dict(cell_0=1e-3), E=dict(cell_0=1e-4), C=dict(cell_0=level), P=dict(cell_0=level)
    )
    moieties = [
        species("S", moieties={"X": 1}),
        species("E", moieties={"Y": 1}),
        species("C", moieties={"X": 1, "Y": 1}, mu=math.log(KD_mM / 1.0)),
        species("P", moieties={"X": 1}),
    ]
    controls = [
        ("binding", None, [(0.0, 1.0)]),
        ("catalysis", None, list(catalysis or [(0.0, 1.0)])),
    ]
    return face_free_network(
        ("E", "C", "P"), moieties, reactions, controls, profile=profile, end=end, dt=dt, **kw
    )


def crossing(*, end=0.5, dt=0.1, sink=1.0, offset=0.01, **kw):
    """Probe 2e's crossing: passive S <-> P (K = 1, 1/s) with a driven sink S -> 0 in the cell,
    S a hair (offset) above the passive equilibrium, so the sink carries the state across it
    within the first half-step (the quadrature's case)."""
    cell = {"cells": ["cell_0"]}
    reactions = [
        passive("exchange", cell, {"S": 1}, {"P": 1}, 1.0),
        mass_action("sink", cell, {"S": 1}, {}, sink),
    ]
    profile = dict(S=dict(cell_0=1e-3 * (1 + offset)), P=dict(cell_0=1e-3))
    moieties = [species("S", moieties={"X": 1}), species("P", moieties={"X": 1})]
    controls = always(["exchange", "sink"])
    return face_free_network(
        ("P",), moieties, reactions, controls, profile=profile, end=end, dt=dt, **kw
    )


def reversal_onset(trace_mM, *, end=0.1, dt=0.025, switch_on=0.0, **kw):
    """Probe 2g's recipe (the known limit, §3.3): passive R + L <-> C (k_on 1e3 /(mM s), K_d 1e-3
    mM) with R at 1e-3 mM and C pre-loaded at 1e-4 mM, L at `trace_mM`; a driven source 0 -> L at
    1e-2 mM/s carries L across its equilibrium (1e-4 mM) within one half-step. Both routes are off
    until switch_on (a mid-run switch-on from the same state when > 0)."""
    cell = {"cells": ["cell_0"]}
    reactions = [
        passive("binding", cell, {"R": 1, "L": 1}, {"C": 1}, KON * 1.0),
        mass_action("source", cell, {}, {"L": 1}, 1e-2),
    ]
    profile = dict(R=dict(cell_0=1e-3), C=dict(cell_0=1e-4), L=dict(cell_0=trace_mM))
    moieties = [
        species("R", moieties={"Y": 1}),
        species("L", moieties={"X": 1}),
        species("C", moieties={"X": 1, "Y": 1}, mu=math.log(KD_mM / 1.0)),
    ]
    schedule = [(0.0, 1.0)] if switch_on == 0.0 else [(0.0, 0.0), (switch_on, 1.0)]
    controls = [(name, None, list(schedule)) for name in ("binding", "source")]
    return face_free_network(
        ("R", "L", "C"), moieties, reactions, controls, profile=profile, end=end, dt=dt, **kw
    )


def mixed_chain(level_mM, *, end=0.1, dt=1e-3, observation_times=None):
    """C2's mixed world (§10.4): D150's heredity chain (six heredity cells whose ions move, six
    finite nodes in a chain of faces) with a reacting pair A, B at `level_mM` on every node: passive
    A <-> B (mu°_B/RT = -1, 1/s) at every finite node, a driven source of A at ecs_0 and a driven
    sink of B at ecs_2. The shared energy bound is the ions' (D150's probe 2 part C method)."""
    raw = fx.heredity_chain(
        secreted=False, dt=dt, end=end, observation_times=observation_times or [0.0, end / 2, end]
    )
    nodes = [f"ecs_{i}" for i in range(fx.CHAIN)]
    for name, level in (("A", level_mM), ("B", 0.5 * level_mM)):
        raw = add_inventory_species(
            raw,
            name,
            trace_mM=TRACE_mM,
            diffusivity_m2_per_s=D_SPECIES,
            floor_fmol=FLOOR_FMOL,
            concentrations_mM={n: level for n in nodes},
        )
    reactions = [
        passive("swap", {"outside": "all"}, {"A": 1}, {"B": 1}, 1.0),
        mass_action("make", {"outside": ["ecs_0"]}, {}, {"A": 1}, 0.1 * level_mM),
        mass_action("drain", {"outside": ["ecs_2"]}, {"B": 1}, {}, 0.5),
    ]
    moieties = [species("A", moieties={"X": 1}), species("B", moieties={"X": 1}, mu=-1.0)]
    return with_reactions(raw, moieties, reactions, always(["swap", "make", "drain"]))
