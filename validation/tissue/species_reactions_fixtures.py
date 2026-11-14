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
* with_reactions: the operator's block and its schedule on a composite definition.
"""

import copy

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
    return dict(
        id=name,
        sites=copy.deepcopy(sites),
        reactants={substrate: 1},
        products=dict(products),
        law="michaelis_menten",
        catalyst=catalyst,
        rate_constant=rate,
        saturation_mM=km,
        factors=list(factors),
    )


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


def without_reactions(raw):
    """The same composite definition without the reaction operator and its schedule."""
    plain = copy.deepcopy(raw)
    plain["model"]["operators"] = [
        block for block in plain["model"]["operators"] if block["law"] != REACTIONS
    ]
    del plain["experiment"]["reaction_controls"]
    return plain
