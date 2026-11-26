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

The co-writer worlds (FR-43 part 3's co-writers; docs/FR43_PART3_COWRITERS_DESIGN.md §5.2) put the
operator beside other writers of the rows it moves: D152's reactions, the gene unit, turnover,
exchange and site occupancy. Their values are synthetic, written here, none from a reference (the
registered comparison's worlds are validation/fr43_part3_cowriters'):
* units(...), with_units(...): a two-subunit site on any species and patch, placed in the list;
* cowriter_world(...): the face-free cell and node above, with extra neutral rows;
* beside_reactions(...), source_world(...): the operator beside a reaction source or sink of S;
* gene_world(...), beside_gene_unit(...), triple(...): the operator on the gene unit's rows;
* five_writers(...): S written by the operator, the reactions, turnover, exchange and sites.
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


# ------------------------------------------------------------------ co-writers (FR-43 part 3)

REACTIONS = "cells.operator.local_species_reactions@1"
TURNOVER = "cells.operator.scheduled_species_turnover@1"
EXCHANGE = "cells.operator.scheduled_species_exchange@1"
SITES = "cells.operator.site_occupancy@1"
SOURCE_mM_PER_S = 1.0  # The zero-order source of S in the cell (mM/s): c rises 1 mM/s.


def units(species=SPECIES, *, patch=PATCH, k_assemble=0.6, k_dissolve=1.0, conductance=0.3,
          read_at="cell", counts=(2, 0), seed=7, trace=64):  # fmt: skip
    """The operator with one site on `patch` of a two-subunit population moving `species`: two
    free subunits assemble into one active unit at k_assemble (1/s) times the species'
    concentration in mM where it is read (read_at "cell" or "outside"; None: unread), the active
    unit dissolves into two at k_dissolve (1/s) and conducts the species at `conductance` (pL/s);
    counts: the site's (free, active) units at the start."""
    read = None if read_at is None else dict(species=species, at=read_at)
    return dict(
        law=LAW,
        species=[dict(id=species, catalogue=None, evidence=None)],
        read_species=[],
        seed=seed,
        trace_events=trace,
        populations=[
            dict(
                id="units",
                unit_states=[dict(id="free", subunits=1), dict(id="active", subunits=2)],
                channels=[
                    dict(id="assemble", reactants={"free": 2}, products={"active": 1},
                         rate_per_s=k_assemble, read=read),
                    dict(id="dissolve", reactants={"active": 1}, products={"free": 2},
                         rate_per_s=k_dissolve, read=None),
                ],
                transfers=[
                    dict(id="flow", species=species,
                         conductance_pL_per_s={"free": 0.0, "active": conductance})
                ],
                division=None,
                sites=[
                    dict(id="site_0", patch=patch,
                         initial_counts={"free": counts[0], "active": counts[1]})
                ],
            )
        ],
        divisions=[],
    )  # fmt: skip


def with_units(raw, block, *, first=False):
    """raw with the operator's block declared last, or first (before every other operator)."""
    out = copy.deepcopy(raw)
    operators = out["model"]["operators"]
    operators.insert(0, copy.deepcopy(block)) if first else operators.append(copy.deepcopy(block))
    return out


def cowriter_world(extra=(), *, dt, end, every=None, cell_mM=1.0, node_mM=0.05, profile=None,
                   cell_pL=1.0, node_pL=0.5):  # fmt: skip
    """The face-free cell and its finite node joined by the contact patch (as base_world), S at
    cell_mM and node_mM, with the neutral rows `extra` (profile {species: {node: mM}})."""
    from validation.tissue import species_reactions_fixtures as rfx

    return rfx.species_world(
        tuple(extra),
        profile={SPECIES: {CELL: cell_mM, NODE: node_mM}, **(profile or {})},
        faces=False,
        cells=((CELL, cell_pL),),
        nodes=((NODE, node_pL),),
        dt=dt,
        end=end,
        observation_times=grid(end, dt, every or end),
    )


def beside_reactions(kind="source", *, at="cell", first=False, dt=0.02, end=0.04, every=None,
                     rate=None, block=None):  # fmt: skip
    """The operator beside D152's reactions writing S at `at` ("cell": cell_0, "outside": ecs_0):
    "source", a zero-order source of S (mass action with no reactant, rate in mM/s, default
    SOURCE_mM_PER_S); "sink", S + Y -> W (second order, rate in 1/(mM s), default 0.5); or
    "first_order", X -> S (rate in 1/s, default 0.2), a source with no static bound. first: the
    operator declared before the reactions. block: the operator's (default units())."""
    from validation.tissue import species_reactions_fixtures as rfx

    where = {"cells": [CELL]} if at == "cell" else {"outside": [NODE]}
    if kind == "source":
        extra, profile = (), {}
        listed = [rfx.species(SPECIES, moieties=None)]
        reaction = rfx.mass_action("make", where, {}, {SPECIES: 1}, rate or SOURCE_mM_PER_S)
    elif kind == "sink":
        extra, profile = ("Y", "W"), {"Y": {CELL: 5.0, NODE: 5.0}, "W": {CELL: 1e-6, NODE: 1e-6}}
        listed = [rfx.species(SPECIES, moieties={"n": 1}), rfx.species("Y", moieties={"y": 1}),
                  rfx.species("W", moieties={"n": 1, "y": 1})]  # fmt: skip
        reaction = rfx.mass_action("spend", where, {SPECIES: 1, "Y": 1}, {"W": 1}, rate or 0.5)
    elif kind == "first_order":
        extra, profile = ("X",), {"X": {CELL: 10.0, NODE: 10.0}}
        listed = [rfx.species(SPECIES, moieties={"n": 1}), rfx.species("X", moieties={"n": 1})]
        reaction = rfx.mass_action("make", where, {"X": 1}, {SPECIES: 1}, rate or 0.2)
    else:
        raise ValueError("kind is source, sink or first_order")
    raw = cowriter_world(extra, dt=dt, end=end, every=every, profile=profile)
    raw = rfx.with_reactions(raw, listed, [reaction], rfx.always([reaction["id"]]))
    return with_units(raw, units() if block is None else block, first=first)


SOURCE_SEED = 13  # Its first threshold, -ln u1 = 1.52, puts the first event near 0.9 s.


def source_world(*, dt=0.01, end=2.0, every=None, first=False):
    """The operator beside a zero-order source of S in the cell (beside_reactions "source"): the
    tier-2 world of test_integer_unit_population.py, and crossrev's and G1's co-writer world (the
    lead's L4). Two free subunits at the start, so nothing moves before the first event, and the
    clock reads c(t) = c0 + k t, whose first crossing is closed form."""
    block = units(seed=SOURCE_SEED)
    return beside_reactions("source", dt=dt, end=end, every=every or dt, first=first, block=block)


def _with_space(raw, *, node, cell, volume):
    """raw with a finite outside node `node` of `volume` pL behind its own patch from `cell`
    (validation/gene_regulation/worlds.with_export's node and patch, without the export): K+ and
    Y- at the bath's 140 mM, every other row at the gene worlds' trace, no permeability."""
    from validation.gene_regulation import worlds as gw

    out = copy.deepcopy(raw)
    m, e, x = out["model"], out["experiment"], out["execution"]
    rows = [s["id"] for s in m["species"] if s["id"] not in ("K", "Y")]
    amounts = {"K": gw.BACKGROUND_mM * volume, "Y": gw.BACKGROUND_mM * volume}
    amounts |= {r: gw.TRACE_mM * volume for r in rows}
    m["extracellular"].append(
        dict(id=node, volume_pL=volume, initial_amount_fmol=amounts,
             fixed_charge_equivalent_fmol=0.0, initial_charge_C=0.0, reservoir=False,
             boundary_potential_V=0.0)
    )  # fmt: skip
    x["extracellular_capacity"] = len(m["extracellular"])
    patch = f"{gw.EXPORT_PATCH}_{cell}_{node}"
    m["membranes"].append(
        dict(id=patch, inside=cell, outside=node, area_m2=gw.AREA_M2,
             capacitance_F=gw.CAPACITANCE_F_PER_M2 * gw.AREA_M2,
             permeability_m_per_s={"K": 0.0, "Y": 0.0, **dict.fromkeys(rows, 0.0)},
             law="cells.route.constant_field@1", pump=None, calcium_pump=None)
    )  # fmt: skip
    x["membrane_capacity"] = len(m["membranes"])
    e["membrane_controls"].append(
        dict(membrane_id=patch, schedule=[dict(time=0.0, availability=1.0)])
    )
    return out, patch


def _horizon(raw, *, end, every):
    out = copy.deepcopy(raw)
    dt = out["execution"]["dt"]
    out["experiment"]["end_time"] = float(end)
    out["experiment"]["observation_times"] = grid(end, dt, every or end)
    out["execution"]["max_steps"] = int(round(end / dt)) + 8
    return out


def gene_world(*, dt=0.5, end=2.0, every=None, copies=10, node_pL=1.0):
    """The gene unit's polymerase-limited world (validation/gene_regulation/worlds
    .polymerase_limited: N, M, ATP, ADP, Pi and the mRNA R), with a finite node space_0 behind its
    own patch from the gene's cell, and its patch's ID."""
    from validation.gene_regulation import worlds as gw

    raw, patch = _with_space(
        gw.polymerase_limited(copies, dt=dt), node=gw.SPACE, cell=gw.CELL, volume=node_pL
    )
    return _horizon(raw, end=end, every=every), patch


def beside_gene_unit(row="N", *, first=False, k_assemble=1e-3, dt=0.5, end=2.0, every=None,
                     solver=None, block=None):  # fmt: skip
    """The operator moving the gene unit's listed `row` (the nucleotide N, or the mRNA R) between
    the gene's cell and space_0, its clock reading the row in the cell; first: declared before the
    gene unit; solver: the execution's (None: the world's IMEX). k_assemble is small, since the
    rows are at mM and the gene unit's production counts in the event-rate bound."""
    raw, patch = gene_world(dt=dt, end=end, every=every)
    if solver is not None:
        raw["execution"]["solver"] = solver
    block = units(row, patch=patch, k_assemble=k_assemble) if block is None else block
    return with_units(raw, block, first=first)


def triple(order=("gene", "reactions", "units"), *, kind="sink", dt=0.5, end=2.0, every=None,
           k_assemble=1e-3, k_dissolve=1.0):  # fmt: skip
    """The gene unit, D152's reactions (validation/tissue/shared_inventory_fixtures.pair: N + X -> W
    for "sink", X -> N for "source") and the operator on one row, N, in the declared `order` of
    "gene", "reactions" and "units"."""
    from validation.gene_regulation import worlds as gw
    from validation.tissue import shared_inventory_fixtures as sif

    raw, patch = _with_space(sif.pair(kind, dt=dt), node=gw.SPACE, cell=gw.CELL, volume=1.0)
    raw = _horizon(raw, end=end, every=every)
    operators = {op["law"]: op for op in raw["model"]["operators"]}
    named = {
        "gene": operators[gw.POLYMERISATION],
        "reactions": operators[REACTIONS],
        "units": units("N", patch=patch, k_assemble=k_assemble, k_dissolve=k_dissolve),
    }
    others = [op for op in raw["model"]["operators"] if op["law"] not in (gw.POLYMERISATION,
                                                                           REACTIONS)]  # fmt: skip
    raw["model"]["operators"] = others + [named[name] for name in order]
    return raw


def with_exchange_of(raw, species, patch, cell, *, rate=0.05, first=False):
    """raw with D150's exchange of `species` across `patch` (a first-order export from `cell`, k_e
    = rate in 1/s): a second transfer of a row (secreted_species_fixtures.with_exchange for any
    species). first: declared before every other operator."""
    out = copy.deepcopy(raw)
    block = dict(
        law=EXCHANGE,
        species=[dict(id=species, catalogue=None, evidence=None)],
        routes=[dict(id="sec", species=species, patch=patch, direction="export",
                     law="first_order")],
        templates=[],
    )  # fmt: skip
    out["model"]["operators"].insert(0, block) if first else out["model"]["operators"].append(block)
    out["experiment"]["exchange_controls"] = [
        dict(route_id="sec", carrier_id=cell, schedule=[dict(time=0.0, rate=rate)])
    ]
    return out


def on_exported_row(row="R", *, dt=0.5, end=2.0):
    """The operator moving a row the gene unit claims alone (refused, design §3.4): with amendment
    T's export of the mRNA R into space_0 and its degradation there, R (the exported row) or M (its
    monomers, returned at the node)."""
    from validation.gene_regulation import worlds as gw

    raw = gw.with_export(gw.polymerase_limited(10, dt=dt), volume=1.0)
    patch = f"{gw.EXPORT_PATCH}_{gw.CELL}_{gw.SPACE}"
    return with_units(_horizon(raw, end=end, every=None), units(row, patch=patch, k_assemble=1e-3))


def exchange_of_labelled_row(*, dt=0.5, end=2.0):
    """D150's exchange of the gene unit's N, which FR-42's label owner labels (refused: the gene
    unit claims a labelled row alone), its label window inside the horizon."""
    from validation.gene_regulation import worlds as gw

    raw, patch = gene_world(dt=dt, end=end)
    raw = gw.with_share_labels(raw, rows=("N",), window=(dt, end - dt))
    return with_exchange_of(raw, "N", patch, gw.CELL)


def on_precursor(*, dt=0.5, end=2.0):
    """The operator moving the unit producer's precursor P beside the gene unit that makes it
    (validation/tissue/shared_inventory_fixtures.unit_pair; refused by the producer's R5, since a
    transfer's rate has no static bound)."""
    from validation.gene_regulation import worlds as gw
    from validation.tissue import shared_inventory_fixtures as sif

    raw, patch = _with_space(sif.unit_pair(dt=dt), node=gw.SPACE, cell=gw.CELL, volume=1.0)
    raw = _horizon(raw, end=end, every=None)
    return with_units(raw, units("P", patch=patch, k_assemble=1e-3))


def sites_on_listed_row(*, dt=0.5, end=2.0):
    """cells.operator.site_occupancy@1 binding the gene unit's N at space_0 (refused: a second
    conversion of a listed row, the lead's L1)."""
    from validation.gene_regulation import worlds as gw
    from validation.tissue import site_occupancy_fixtures as sof

    raw, patch = gene_world(dt=dt, end=end)
    population = sof.population(patch=patch, face="outside", k_on=0.2, k_off=0.5, copies=5e6)
    population["ligand"] = "N"
    ligand = sof.ligand(trace_mM=gw.TRACE_mM, species="N")
    return sof.with_site_occupancy(raw, [population], ligands=[ligand])


def gene_cowriters(*, dt=0.5, end=60.0, every=None):
    """The gene unit's run of design §5.2 (part 2's C2.3 pair with a transfer and a site on N): the
    gene unit and D152's sink N + X -> W on N (triple), D150's exchange of N from the gene's cell
    into space_0, and the operator moving N across the same patch, its clock reading N in the cell
    (k_assemble 0.1 per s per mM at N's 5 mM, k_dissolve 0.2 per s: about ten cycles a minute)."""
    from validation.gene_regulation import worlds as gw

    raw = triple(dt=dt, end=end, every=every, k_assemble=0.1, k_dissolve=0.2)
    patch = f"{gw.EXPORT_PATCH}_{gw.CELL}_{gw.SPACE}"
    return with_exchange_of(raw, "N", patch, gw.CELL)


def five_writers(*, dt=0.02, end=4.0, every=None, first=False):
    """S written by the operator, D152's reactions (X -> S and S + Y -> W in the cell), turnover
    (clearance at the node), exchange (a first-order export across the contact patch) and site
    occupancy (binding at the node, on the contact patch's outside face): every declared class of
    split writer of one neutral row (design §5.2). first: the operator declared first."""
    from validation.tissue import site_occupancy_fixtures as sof
    from validation.tissue import species_reactions_fixtures as rfx

    profile = {"X": {CELL: 10.0}, "Y": {CELL: 5.0}, "W": {CELL: 1e-6}}
    raw = cowriter_world(("X", "Y", "W"), dt=dt, end=end, every=every, profile=profile)
    raw = ssf.with_turnover(raw, [("clear", NODE, "clearance")], [("clear", None, [(0.0, 0.2)])])
    raw = ssf.with_exchange(
        raw, [("sec", PATCH, "export", "first_order")], [("sec", CELL, [(0.0, 0.05)])]
    )
    cell = {"cells": [CELL]}
    raw = rfx.with_reactions(
        raw,
        [rfx.species(SPECIES, moieties={"n": 1}), rfx.species("X", moieties={"n": 1}),
         rfx.species("Y", moieties={"y": 1}), rfx.species("W", moieties={"n": 1, "y": 1})],
        [rfx.mass_action("make", cell, {"X": 1}, {SPECIES: 1}, 0.02),
         rfx.mass_action("spend", cell, {SPECIES: 1, "Y": 1}, {"W": 1}, 0.04)],
        rfx.always(["make", "spend"]),
    )  # fmt: skip
    raw = sof.with_site_occupancy(
        raw, [sof.population(k_on=0.2, k_off=0.5, copies=5e6)],
        ligands=[sof.ligand(trace_mM=ssf.TRACE_mM)],
    )  # fmt: skip
    return with_units(raw, units(trace=64), first=first)
