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


def with_site_occupancy(raw, populations, *, ligands=None, controls=None):
    """populations: population(...) dicts; controls: {(population, route): [(time, m), ...]},
    by default a constant 1 on every declared route."""
    out = copy.deepcopy(raw)
    out["model"]["operators"].append(
        dict(law=LAW, species=ligands or [ligand()], populations=[dict(p) for p in populations])
    )
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
