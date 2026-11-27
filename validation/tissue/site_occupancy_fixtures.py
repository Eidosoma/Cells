"""Small worlds for cells.operator.site_occupancy@1 (FR-3, docs/SITE_OCCUPANCY_DESIGN.md).

All values are synthetic. The worlds are secreted_species_fixtures' quiescent worlds (passive
cells, zero ion permeability, every node at the bath's ion composition with a zero charge anchor),
with D150's neutral species S as the ligand, so the energy flows and bounds are the ligand's own.

* face_free_sites: D150's face-free topology (§1.2 of the compartment note): cell_0 with its wall
  patch on the held bath, and its contact patch contact_0 the only patch of the finite node ecs_0,
  which no face names. The ligand S is at `node_mM` in ecs_0 and `cell_mM` in the cell, the trace
  elsewhere. Populations are added with `population(...)`.
* with_site_occupancy: the operator's block and its `site_controls` on any composite definition.
"""

import copy

from validation.tissue import secreted_species_fixtures as fx

LAW = "cells.operator.site_occupancy@1"
LIGAND = fx.SPECIES
TRACE_mM = 1e-12  # At most 1e-6 K_d for every population below (K_d >= 1e-6 mM).


def ligand(trace_mM=TRACE_mM, catalogue=None, evidence=None, species=LIGAND):
    return dict(id=species, catalogue=catalogue, evidence=evidence, trace_mM=trace_mM)


def population(
    pid="r0",
    *,
    patch="contact_0",
    face="outside",
    contact=None,
    side=None,
    node=None,
    copies=1e5,
    sites_per_copy=1,
    alpha=0.5,
    k_on=1e3,
    k_off=1.0,
    theta0=0.0,
    k_int=None,
    destination="cell",
    unit="site_unit_a",
    catalogue=None,
):
    owner = (
        dict(node=node)
        if node is not None
        else dict(contact=contact, side=side)
        if contact is not None
        else dict(patch=patch, face=face)
    )
    return dict(
        id=pid,
        functional_unit=unit,
        catalogue=catalogue,
        owner=owner,
        copies=copies,
        sites_per_copy=sites_per_copy,
        accessible_fraction=alpha,
        ligand=LIGAND,
        association_rate_per_mM_per_s=k_on,
        dissociation_rate_per_s=k_off,
        initial_occupancy=theta0,
        internalisation=None if k_int is None else dict(rate_per_s=k_int, destination=destination),
    )


def with_site_occupancy(raw, populations, *, ligands=None, controls=None, site_sets=None):
    """populations: population(...) or member(...) dicts; controls: {(population, route): [(time,
    m), ...]}, by default a constant 1 on every declared route; site_sets: site_set(...) dicts
    (FR-45), the key left out when None."""
    out = copy.deepcopy(raw)
    block = dict(law=LAW, species=ligands or [ligand()])
    if site_sets is not None:
        block["site_sets"] = [dict(s) for s in site_sets]
    block["populations"] = [dict(p) for p in populations]
    out["model"]["operators"].append(block)
    routes = {}
    for p in populations:
        routes[(p["id"], "binding")] = [(0.0, 1.0)]
        if p["internalisation"] is not None:
            routes[(p["id"], "internalisation")] = [(0.0, 1.0)]
    routes.update(controls or {})
    out["experiment"]["site_controls"] = [
        dict(
            population=pid,
            route=route,
            schedule=[dict(time=t, multiplier=m) for t, m in changes],
        )
        for (pid, route), changes in routes.items()
    ]
    return out


def face_free_sites(
    populations=None,
    *,
    node_mM=1e-3,
    cell_mM=1e-3,
    dt=1e-3,
    end=0.02,
    solver=fx.IMEX,
    observation_times=None,
    controls=None,
    ligands=None,
):
    """The face-free world with site populations (module docstring); populations=None gives one
    outward population on the contact, binding only."""
    raw = fx.face_free(
        pool_mM=cell_mM,
        node_mM=node_mM,
        dt=dt,
        end=end,
        solver=solver,
        trace_mM=TRACE_mM,
        observation_times=observation_times or fx.grid_times(end, dt, dt),
    )
    pops = [population()] if populations is None else populations
    return with_site_occupancy(raw, pops, ligands=ligands, controls=controls)


# ------------------------------------------------------------------ FR-26: a replaced slot

OCCUPANT_LAW = "cells.operator.site_occupant_replacement@1"


def with_occupant(raw, templates):
    """cells.operator.site_occupant_replacement@1 (W) after the site operator. templates: {template id:
    {population id: (initial occupancy, binding multiplier, internalisation multiplier or
    None)}}."""
    out = copy.deepcopy(raw)
    out["model"]["operators"].append(
        dict(
            law=OCCUPANT_LAW,
            templates=[
                dict(
                    template_id=tid,
                    populations={
                        pid: dict(
                            initial_occupancy=v[0],
                            binding_multiplier=v[1],
                            **({} if v[2] is None else {"internalisation_multiplier": v[2]}),
                        )
                        for pid, v in pops.items()
                    },
                )
                for tid, pops in templates.items()
            ],
        )
    )
    return out


def replaced_sites(
    populations,
    occupants=None,
    *,
    t_e=0.005,
    dt=1e-3,
    end=0.01,
    observation_times=None,
    slot="cell_1",
):
    """Two cells on the bath joined by the gated junction j0, each with a contact patch on the
    finite node ecs_0 (contact_0, contact_1), S at 1 uM everywhere; cell_1 replaced at t_e by a
    newcomer from template T (cell_1's declared state); the populations; and, with `occupants`
    ({population id: (theta', binding, internalisation or None)} for T), W after the site
    operator. FR-26's worlds."""
    raw = fx.world(
        cells=(("cell_0", 1.0), ("cell_1", 1.0)),
        nodes=(("ecs_0", 1.0),),
        contacts=(("contact_0", "cell_0", "ecs_0"), ("contact_1", "cell_1", "ecs_0")),
        faces=(),
        junctions=(("j0", "cell_0", "cell_1"),),
        dt=dt,
        end=end,
        observation_times=observation_times,
        trace_mM=TRACE_mM,
        concentrations_mM=dict(cell_0=1e-3, cell_1=1e-3, ecs_0=1e-3),
    )
    template = fx.template(raw, slot, "T", s_mM=1e-3)
    raw = fx.with_replacement(raw, [template], [(t_e, slot, "T", f"{slot}_new")])
    raw = with_site_occupancy(raw, populations)
    return raw if occupants is None else with_occupant(raw, {"T": occupants})


# ------------------------------------------------------------------ FR-45: shared site sets
#
# Invented values only: none is an input of FR-45's registered worlds. The ligands Q1, Q2 and Q3
# are D150-declared neutral species beside S, each at SET_TRACE_mM wherever no amount is given.

SET_TRACE_mM = 2e-12  # At most 1e-6 K_d for every member below (K_d >= 1e-5 mM).
SET_LIGANDS = ("Q1", "Q2", "Q3")


def site_set(sid="lattice", *, node=None, patch="contact_0", face="outside", copies=3e5,
             sites_per_copy=1, alpha=0.5, unit="lattice_site", catalogue=None):  # fmt: skip
    """A shared site set (FR-45) on a patch's face, or on a finite node's own surface (node=)."""
    owner = dict(node=node) if node is not None else dict(patch=patch, face=face)
    return dict(id=sid, functional_unit=unit, catalogue=catalogue, owner=owner, copies=copies,
                sites_per_copy=sites_per_copy, accessible_fraction=alpha)  # fmt: skip


def member(pid, sites="lattice", *, ligand="Q1", k_on=1.8e3, k_off=0.45, theta0=0.0, k_int=None):
    """A population on a shared set (FR-45): its ligand and rates; its owner and counts are its
    set's. k_int declares the internalisation that version 1 refuses beside sets."""
    return dict(id=pid, sites=sites, ligand=ligand, association_rate_per_mM_per_s=k_on,
                dissociation_rate_per_s=k_off, initial_occupancy=theta0,
                internalisation=None if k_int is None else dict(rate_per_s=k_int, destination="cell"))  # fmt: skip


def set_world(populations, site_sets, *, ligands=SET_LIGANDS[:2], node_mM=None, cell_mM=None,
              dt=2e-3, end=0.02, observation_times=None, controls=None, volume=1.3,
              faces=(), cells=(("cell_0", 0.9),), contacts=(("contact_0", "cell_0", "ecs_0"),)):  # fmt: skip
    """FR-45's development world: D150's face-free cell (cell_0, 0.9 pL, walled on the held bath,
    its contact patch contact_0 the only patch of the finite node ecs_0, of `volume` pL), with the
    ligands declared beside S at `node_mM` ({ligand: mM}) in ecs_0 and `cell_mM` in cell_0, each
    at SET_TRACE_mM elsewhere; the site operator with `site_sets` and `populations` (member(...)
    or population(...) dicts). faces, cells and contacts go to secreted_species_fixtures.world."""
    from cells.registry.inventory_species import add_inventory_species

    raw = fx.world(cells=cells, nodes=(("ecs_0", volume),), contacts=contacts, faces=faces, dt=dt,
                   end=end, trace_mM=TRACE_mM,
                   observation_times=observation_times or fx.grid_times(end, dt, dt))  # fmt: skip
    node_mM, cell_mM = dict(node_mM or {}), dict(cell_mM or {})
    for name in ligands:
        given = {
            k: v for k, v in (("ecs_0", node_mM.get(name)), ("cell_0", cell_mM.get(name))) if v
        }
        raw = add_inventory_species(raw, name, trace_mM=SET_TRACE_mM, diffusivity_m2_per_s=1e-10,
                                    floor_fmol=fx.FLOOR_FMOL, concentrations_mM=given)  # fmt: skip
    species = [ligand(trace_mM=SET_TRACE_mM, species=name) for name in ligands]
    return with_site_occupancy(raw, populations, ligands=species, controls=controls,
                               site_sets=site_sets)  # fmt: skip


def two_cell_set_world(*, on_slot=False, replaced=True, dt=1e-3, end=0.01, observation_times=None):
    """FR-45 beside replacement@1: two cells on the bath (cell_0 0.9 pL, cell_1 1.1 pL) joined by
    the gated junction j0, each with a contact patch on the finite node ecs_0 (1.3 pL); with
    `replaced`, cell_1 replaced at 5 ms by a newcomer from template T (its declared state); Q1
    and Q2 competing for one set on contact_1 (cell_1's, on the slot) or contact_0 (off it)."""
    from cells.registry.inventory_species import add_inventory_species

    raw = fx.world(cells=(("cell_0", 0.9), ("cell_1", 1.1)), nodes=(("ecs_0", 1.3),),
                   contacts=(("contact_0", "cell_0", "ecs_0"), ("contact_1", "cell_1", "ecs_0")),
                   faces=(), junctions=(("j0", "cell_0", "cell_1"),), dt=dt, end=end,
                   observation_times=observation_times, trace_mM=TRACE_mM)  # fmt: skip
    if replaced:
        raw = fx.with_replacement(
            raw, [fx.template(raw, "cell_1", "T")], [(0.005, "cell_1", "T", "n1")]
        )
    for name, mM in (("Q1", 2.4e-3), ("Q2", 1.3e-3)):
        raw = add_inventory_species(raw, name, trace_mM=SET_TRACE_mM, diffusivity_m2_per_s=1e-10,
                                    floor_fmol=fx.FLOOR_FMOL, concentrations_mM={"ecs_0": mM})  # fmt: skip
    pops = [member("m1", ligand="Q1"), member("m2", ligand="Q2", k_on=1.1e3, k_off=0.25)]
    sets = [site_set(patch="contact_1" if on_slot else "contact_0")]
    species = [ligand(trace_mM=SET_TRACE_mM, species=g) for g in ("Q1", "Q2")]
    return with_site_occupancy(raw, pops, ligands=species, site_sets=sets)


# ------------------------------------------------------------------ FR-45's compiled world

CHASE_VOLUME_pL = 7.5e5  # A 0.75 uL node.
CHASE_SITES_fmol = 18.0
CHASE_DT, CHASE_WASH_S, CHASE_END_S, CHASE_FRACTION = 0.06, 0.36, 18.0, 0.4
CHASE_RATES = {"bait": (4e4, 1.7), "chase": (6e4, 0.35)}  # k_on per mM per s, k_off per s.
CHASE_THETA = 0.4  # Q1's start, at its own equilibrium with Q2 at its trace.
CHASE_mM = 1.5e-4


def chase_world(chase_mM=CHASE_mM):
    """FR-45's compiled world (tests/unit/test_site_competition_runs.py and
    test_site_competition_batch_runs.py; invented values): ecs_0's own sites, a set of 18 fmol shared
    by Q1, bound at its own equilibrium with Q2 at its trace, and Q2. At 0.36 s, 0.4 of the liquid
    is washed for a buffer holding Q2 at chase_mM and Q1 at its trace; Q2 then binds and displaces
    Q1 to the free-site root of the post-wash totals."""
    from cells.operators.site_occupancy import SITES_PER_FMOL
    from validation.tissue import wash_schedule_fixtures as wfx

    (k1, d1), (k2, d2) = CHASE_RATES["bait"], CHASE_RATES["chase"]
    pops = [member("bait", ligand="Q1", k_on=k1, k_off=d1, theta0=CHASE_THETA),
            member("chase", ligand="Q2", k_on=k2, k_off=d2)]  # fmt: skip
    raw = set_world(pops, [site_set(node="ecs_0", copies=CHASE_SITES_fmol * SITES_PER_FMOL / 0.5)],
                    node_mM={"Q1": (d1 / k1) * CHASE_THETA / (1 - CHASE_THETA)},
                    volume=CHASE_VOLUME_pL, dt=CHASE_DT, end=CHASE_END_S,
                    observation_times=[0.0, CHASE_WASH_S, CHASE_END_S])  # fmt: skip
    buffer = {wfx.TRACER: 3e-12, "Q1": SET_TRACE_mM, "Q2": chase_mM}
    return wfx.with_wash(raw, ["ecs_0"], [(CHASE_WASH_S, "ecs_0", CHASE_FRACTION, buffer)])
