"""Small worlds for cells.operator.scheduled_compartment_wash@1 (FR-27, docs/COMPARTMENT_WASH_DESIGN.md).

All values are synthetic. The worlds are secreted_species_fixtures' quiescent worlds (passive cells,
zero ion permeability, every node at the bath's ion composition with a zero charge anchor), with
D150's neutral species S as the washed tracer.

* well: the tracer-wash example that FR-27 came from (D245). A closed 1 uL well, a finite node with
  no face, holds S; two site populations face it, on a specimen cell's patch and on a stand-in
  cell's patch for the vessel wall. Their constants put 60 fmol free, 30 bound to the specimen and
  10 to the wall at equilibrium at 60 nM free (K_d = 60 nM for both, the wall's binding ten times
  faster). These are the declared start, steady until a wash, so they are the stocks at the wash
  event. A saved row after the wash is a step later, one dt, and its bound stocks have begun to
  re-equilibrate. With wall="node" the wall's sites are owned by the well itself (FR-28).
* with_wash: the operator's block and its `compartment_wash_events` on any composite definition.
"""

import copy

from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import site_occupancy_fixtures as sfx

LAW = "cells.operator.scheduled_compartment_wash@1"
SAME = "same_as_compartment"
TRACER = fx.SPECIES
SITES_PER_FMOL = 602_214_076.0  # The site operator's exact constant.
V_WELL = 1.0e6  # pL: 1 uL.
TRACE_mM = 1e-12  # The tracer's trace: at most 1e-6 K_d of both populations.
SPECIMEN = dict(id="specimen_sites", patch="specimen_face", capacity=60.0, k_on=1.0e3, k_off=0.06)
WALL = dict(id="wall_sites", patch="wall_face", capacity=20.0, k_on=1.0e4, k_off=0.6)


def with_wash(raw, nodes, events, *, ions=SAME):
    """nodes: the washed node IDs; events: (time, node, fraction, {species: mM}) quadruples."""
    out = copy.deepcopy(raw)
    out["model"]["operators"].append(dict(law=LAW, nodes=list(nodes), ions=ions))
    out["experiment"]["compartment_wash_events"] = [
        dict(time=t, node=n, fraction=f, buffer_mM=dict(b)) for t, n, f, b in events
    ]
    return out


def _sites(site, bound, node=None):
    return sfx.population(
        site["id"],
        patch=site["patch"],
        face="outside",
        node=node,
        copies=site["capacity"] * SITES_PER_FMOL,  # S = alpha nu N / N_f with alpha = nu = 1.
        sites_per_copy=1,
        alpha=1.0,
        k_on=site["k_on"],
        k_off=site["k_off"],
        theta0=bound / site["capacity"],
        unit=site["id"].replace("_sites", "_site"),
    )


def well(
    *,
    free=60.0,
    specimen=30.0,
    wall_bound=10.0,
    sites=True,
    wall="stand-in",
    volume=V_WELL,
    dt=0.01,
    end=2.0,
    observation_times=None,
):
    """The well (`volume` pL) with `free` fmol of S and, with `sites`, the two populations at
    `specimen` and `wall` fmol bound; S at its trace elsewhere. wall: "stand-in", the wall's sites
    on an inert stand-in cell's patch (the review's world), or "node", owned by the well's own
    surface (FR-28, D268), with no stand-in cell."""
    stand_in = wall == "stand-in"
    raw = fx.world(
        cells=(("specimen", 1.0), ("wall_surface", 1.0)) if stand_in else (("specimen", 1.0),),
        nodes=(("well", volume),),
        baths=("bath",),
        contacts=(("specimen_face", "specimen", "well"), ("wall_face", "wall_surface", "well"))
        if stand_in
        else (("specimen_face", "specimen", "well"),),
        faces=(),
        dt=dt,
        end=end,
        observation_times=observation_times,
        trace_mM=TRACE_mM,
        concentrations_mM={"well": free / volume},
    )
    if not sites:
        return raw
    populations = [
        _sites(SPECIMEN, specimen),
        _sites(WALL, wall_bound, node=None if stand_in else "well"),
    ]
    return sfx.with_site_occupancy(raw, populations, ligands=[sfx.ligand(trace_mM=TRACE_mM)])
