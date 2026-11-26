"""FR-43 part 3's worlds for cells.operator.integer_unit_population@1, built from the references' spec.

Each world of references/spec/part3.json becomes a composite definition: one quiescent cell and
its finite outside node joined by a contact patch (validation/tissue/secreted_species_fixtures:
no face, zero ion and species permeability, so nothing but the operator moves S), the cell's wall
on a held bath, and the operator with one site on the contact patch. The declared values are the
spec's, read from the one file, so the engine's worlds and the references' are one declaration.

* spec_world(world_id, dt=..., end=..., every=...): a spec world as a raw definition;
* population(...), block(...): the operator's declaration pieces;
* many_sites(...): one patch holding many independent sites (C3.3's and C3.5's statistics);
* divided(...): the parent cell divided by cells.operator.isopotential_partition@1, the sites mapped (C3.5).
"""

import copy
import json
from pathlib import Path

from validation.tissue import secreted_species_fixtures as ssf

LAW = "cells.operator.integer_unit_population@1"
SPEC = Path(__file__).resolve().parent / "references" / "spec" / "part3.json"
PATCH = "contact_0"
CELL, NODE = "cell_0", "ecs_0"
SPECIES = ssf.SPECIES  # "S"


def spec_worlds():
    with SPEC.open() as f:
        return {w["id"]: w for w in json.load(f)["worlds"]}


def population(world, *, sites, division=None, name="units"):
    """The operator's population from a spec world's unit states, channels and transfer."""
    channels = []
    for c in world["channels"]:
        read = c["read"]
        channels.append(
            dict(
                id=c["id"],
                reactants=dict(c["reactants"]),
                products=dict(c["products"]),
                rate_per_s=c["rate_constant_per_s"],
                read=None
                if read is None
                else dict(
                    species=read["species"], at="cell" if read["at"] == "cell" else "outside"
                ),
            )
        )
    transfer = world["transfer"]
    transfers = []
    if transfer is not None:
        transfers.append(
            dict(
                id="flow",
                species=transfer["species"],
                conductance_pL_per_s=dict(transfer["conductance_pL_per_s_per_unit"]),
            )
        )
    return dict(
        id=name,
        unit_states=[dict(id=u["id"], subunits=u["subunits"]) for u in world["unit_states"]],
        channels=channels,
        transfers=transfers,
        division=division,
        sites=sites,
    )


def site(name, counts, *, patch=PATCH):
    return dict(id=name, patch=patch, initial_counts=dict(counts))


def block(populations, *, seed, trace=256, divisions=()):
    return dict(
        law=LAW,
        species=ssf.identity(),
        read_species=[],
        seed=seed,
        trace_events=trace,
        populations=list(populations),
        divisions=[dict(parent=p, daughters=list(d)) for p, d in divisions],
    )


def grid(end, dt, every):
    return ssf.grid_times(end, dt, every)


def base_world(world, *, dt, end, every):
    """The face-free cell and node at the spec world's volumes and initial amounts of S."""
    volumes, amounts = world["volumes_pL"], world["initial_amounts_fmol"]
    profile = {CELL: amounts["cell"] / volumes["cell"], NODE: amounts["node"] / volumes["node"]}
    return ssf.world(
        cells=((CELL, volumes["cell"]),),
        nodes=((NODE, volumes["node"]),),
        faces=(),
        dt=dt,
        end=end,
        observation_times=grid(end, dt, every),
        concentrations_mM=profile,
    )


def spec_world(world_id, *, dt, end=None, every=None, trace=256, seed=None):
    """A spec world as a raw composite definition (its own seed and site unless given)."""
    world = spec_worlds()[world_id]
    end = world["horizon_s"] if end is None else end
    every = 1.0 if every is None else every
    raw = base_world(world, dt=dt, end=end, every=every)
    counts = world["initial_counts"]
    units = population(world, sites=[site("site_0", counts)])
    seed = world["stream"]["seed"] if seed is None else seed
    raw["model"]["operators"].append(block([units], seed=seed, trace=trace))
    if world["turnover"] is not None:
        t = world["turnover"]
        raw = ssf.with_turnover(
            raw,
            [("make", CELL, "production"), ("clear", NODE, "clearance")],
            [
                ("make", CELL, [(0.0, t["production_cell_fmol_per_s"])]),
                ("clear", None, [(0.0, t["clearance_node_per_s"])]),
            ],
        )
        # The operator follows turnover: both are split parts; the order is declared.
        ops = raw["model"]["operators"]
        ops.append(ops.pop(ops.index(next(o for o in ops if o["law"] == LAW))))
    return raw


def many_sites(world_id, count, *, dt, end, every, seed, trace=0, rates=None, counts=None):
    """One patch with `count` independent sites of the spec world's population and no transfer:
    C3.3's statistics (each site an independent two-state process when rates are constant)."""
    world = copy.deepcopy(spec_worlds()[world_id])
    world["transfer"] = None
    for c in world["channels"]:
        c["read"] = None
        if rates is not None:
            c["rate_constant_per_s"] = rates[c["id"]]
    raw = base_world(world, dt=dt, end=end, every=every)
    counts = world["initial_counts"] if counts is None else counts
    units = population(world, sites=[site(f"site_{i}", counts) for i in range(count)])
    raw["model"]["operators"].append(block([units], seed=seed, trace=trace))
    return raw


PARTITION = "cells.operator.isopotential_partition@1"
STATE = "cells.operator.membrane_entity_state@1"
DAUGHTERS = ("d1", "d2")


def divided(
    world_id="W1_two_subunits_feedback",
    *,
    sites=1,
    transfer=True,
    counts=None,
    rates=None,
    f=0.5,
    at=0.02,
    dt=0.01,
    end=0.05,
    every=0.01,
    seed=11,
    trace=8,
):
    """The spec world's cell divided once by cells.operator.isopotential_partition@1 at `at` (volume fraction f,
    every patch at the partition's default area fraction, so the site's patch takes f too), with
    `sites` parent sites on the contact patch, each mapped onto one site at each daughter's contact
    patch (C3.5). counts: each parent's initial counts (default the spec world's); rates: {channel:
    rate} overrides (0 freezes the units until the division); transfer False drops the route."""
    from cells.definitions import partition_spec as ps

    world = copy.deepcopy(spec_worlds()[world_id])
    if not transfer:
        world["transfer"] = None
        for c in world["channels"]:
            c["read"] = None
    for c in world["channels"]:
        if rates is not None:
            c["rate_constant_per_s"] = rates[c["id"]]
    raw = base_world(world, dt=dt, end=end, every=every)
    division = ps.add_division(
        raw, division_id="first", parent=CELL, daughters=DAUGHTERS, volume_fraction=f
    )
    counts = world["initial_counts"] if counts is None else counts
    zero = {k: 0 for k in counts}
    parents = [site(f"site_{i}", counts) for i in range(sites)]
    kids = [
        site(f"site_{i}_{d}", zero, patch=f"{PATCH}_{d}") for i in range(sites) for d in DAUGHTERS
    ]
    units = population(world, sites=parents + kids, division="independent_segregation")
    maps = [(f"site_{i}", tuple(f"site_{i}_{d}" for d in DAUGHTERS)) for i in range(sites)]
    raw["model"]["operators"] = [
        dict(law=STATE, populations=[]),
        dict(law=PARTITION, divisions=[division]),
        block([units], seed=seed, trace=trace, divisions=maps),
    ]
    raw["experiment"]["partition_events"] = [dict(division="first", time=at, carriers=["c1", "c2"])]
    return raw
