"""FR-45's worlds, built from an object of the contract's `inputs` shape (validation/fr45/spec/TABLE.md §4.1).

One builder serves every world: a registered world's inputs (typed from SPEC §2, with the host-entity
addendum's values) and an invented world's (the format sample's, at TABLE §12.3 step 5). It forms the
composite definition the engine parses; nothing here runs or judges.

The bath form (TABLE §4.1): the held bath `bath`; the host entities the inputs name; every ion's and every
ligand's permeability 0.0 on every patch; every ligand declared beside the ions by the engine's species helper
(cells.registry.inventory_species) at the amounts `free_amounts` gives, its trace the smallest concentration it
has anywhere; the quiescent ions of validation/tissue/secreted_species_fixtures (each compartment at the bath's
ion composition with a zero charge anchor), so no ion moves.

The sets: a shared set (`shared` true) is a `site_sets` entry, owned by a node or by a patch's face, and its
populations are members; a one-population set (`shared` false) is its population's own inline sites, keyed in
the engine by the population's ID and mapped back to the set's name by `World.set_of_engine_key`.
"""

import copy
import math
from dataclasses import dataclass, field

from cells.definitions import pump_composite_spec as cs
from cells.registry.inventory_species import add_inventory_species
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import site_occupancy_fixtures as sfx
from validation.tissue import wash_schedule_fixtures as wfx

BATH = "bath"
FLOOR_FMOL = (
    1e-20  # The one floor the driver passes to the species helper for every ligand (TABLE §4).
)
DIFFUSIVITY = 1e-10  # m^2/s; no world has a face, so no ligand diffuses.
SOLVER = fx.IMEX
# The field solver every fixture of the suite declares (secreted_species_fixtures.world): the execution
# record states it, and N2's reviewer confirms it as the engine's default (TABLE §4).
FIELD_SOLVER = "cells.solver.capacitive_reduction_gauged_damped_newton@2"
WALL = dict(area=fx.WALL_AREA_M2, capacitance=fx.WALL_C_F)
CONTACT = dict(area=fx.CONTACT_AREA_M2, capacitance=fx.CONTACT_C_F)


@dataclass
class World:
    """The definition and the names the driver reads it by."""

    raw: dict
    inputs: dict
    set_of_engine_key: dict = field(default_factory=dict)  # engine set key -> the inputs' set ID
    facing: dict = field(default_factory=dict)  # the inputs' set ID -> its facing compartment
    washed_node: str | None = None


def _patch_values(inputs, patch):
    """(area m^2, capacitance F) of a patch: the inputs' host values where given, else the fixtures'."""
    host = inputs.get("host_values") or {}
    area = (host.get("areas") or {}).get(patch["id"])
    capacitance = (host.get("capacitances") or {}).get(patch["id"])
    default = WALL if patch["outside"] == BATH else CONTACT
    number = (int, float)
    return (
        area if isinstance(area, number) else default["area"],
        capacitance if isinstance(capacitance, number) else default["capacitance"],
    )


def _facing(inputs, entry):
    """The compartment a set faces: its node, or its patch's side."""
    if entry.get("face") is None:
        return entry["owner"]
    patch = next(p for p in inputs["patches"] if p["id"] == entry["owner"])
    return patch["inside"] if entry["face"] == "inside" else patch["outside"]


def _traces(inputs, volume):
    """{ligand: its declared trace, mM}: the smallest concentration it has in any compartment or in the wash's
    buffer, since the engine refuses any of them below the declared trace (the site design's §4.3). A
    registered world holds each ligand at its trace 1e-12 mM in every host compartment (TABLE §4.1)."""
    wash = inputs.get("wash") or {}
    out = {}
    for g in inputs["ligands"]:
        levels = [
            e["n_fmol"] / volume[e["node"]] for e in inputs["free_amounts"] if e["ligand"] == g
        ]
        if wash:
            levels.append(wash["buffer_mM"][g])
        out[g] = min(levels)
    return out


def _owner(entry):
    if entry.get("face") is None:
        return dict(node=entry["owner"])
    return dict(patch=entry["owner"], face=entry["face"])


def build(inputs, *, start=None):
    """A World from `inputs` (TABLE §4.1's shape). `start`: W1eq's start, {"initial_occupancy": {population:
    value}, "free_amounts": {(ligand, node): n}}, read by the driver from its file (TABLE §3)."""
    inputs = copy.deepcopy(inputs)
    if start:
        for pop in inputs["populations"]:
            pop["initial_occupancy"] = start["initial_occupancy"].get(
                pop["id"], pop["initial_occupancy"]
            )
        for entry in inputs["free_amounts"]:
            entry["n_fmol"] = start["free_amounts"].get(
                (entry["ligand"], entry["node"]), entry["n_fmol"]
            )
    nodes = {n["id"]: n for n in inputs["nodes"]}
    cells = [
        fx._node(n["id"], n["volume_pL"], outside=False)
        for n in inputs["nodes"]
        if n["kind"] == "cell"
    ]
    outside = [fx._node(BATH, nodes[BATH]["volume_pL"], reservoir=True)]
    outside += [
        fx._node(n["id"], n["volume_pL"])
        for n in inputs["nodes"]
        if n["kind"] == "node" and n["id"] != BATH
    ]
    membranes = [
        fx._patch(p["id"], p["inside"], p["outside"], *_patch_values(inputs, p))
        for p in inputs["patches"]
    ]
    end, dt = inputs["horizon_s"], inputs["dt_s"]
    temperature = (inputs.get("constants") or {}).get("temperature_K") or 310.0
    always = [dict(time=0.0, availability=1.0)]
    raw = dict(
        schema_version=1,
        model=dict(
            id="cells.model.resolved_pump_tissue@3",
            temperature_K=temperature,
            species=[dict(id=s, valence=z) for s, z in fx.ION_SPECIES],
            cells=cells,
            extracellular=outside,
            membranes=membranes,
            junctions=[],
            faces=[],
            closure=dict(
                law="cells.field_closure.resolved_capacitor_components_current_continuity@1",
                gauge_reference=None,
            ),
            channels=[],
        ),
        experiment=dict(
            end_time=end,
            observation_times=sorted({*inputs["observation_times_s"], end}),
            membrane_controls=[
                dict(membrane_id=p["id"], schedule=copy.deepcopy(always)) for p in membranes
            ],
            junction_controls=[],
            pump_controls=[],
            calcium_pump_controls=[],
            channel_controls=[],
        ),
        execution=dict(
            dt=dt,
            capacity=len(cells),
            extracellular_capacity=len(outside),
            membrane_capacity=len(membranes),
            edge_capacity=0,
            face_capacity=1,
            channel_capacity=0,
            backend="cpu",
            jit=True,
            precision="float64",
            solver=SOLVER,
            field_solver=FIELD_SOLVER,
            max_steps=int(math.ceil(end / dt)) + 8,
            max_trace_bytes=2**31,
            material_balance_atol_fmol={s: 1e-10 for s, _ in fx.ION_SPECIES},
        ),
    )
    raw = cs.frozen_definition(raw)  # The composite: @3 inside, the operators beside it.
    volume = {n: nodes[n]["volume_pL"] for n in nodes}
    trace = _traces(inputs, volume)
    for ligand in inputs["ligands"]:
        given = {
            e["node"]: e["n_fmol"] / volume[e["node"]]
            for e in inputs["free_amounts"]
            if e["ligand"] == ligand
        }
        raw = add_inventory_species(raw, ligand, trace_mM=trace[ligand], diffusivity_m2_per_s=DIFFUSIVITY,
                                    floor_fmol=FLOOR_FMOL, concentrations_mM=given)  # fmt: skip
        # The helper declares c V from c = n / V, which can miss n by an ulp; each amount is declared as written
        # (SPEC:104), and a trace as the product 1e-12 V the inputs hold (TABLE §4.1) [W-f].
        exact = {e["node"]: e["n_fmol"] for e in inputs["free_amounts"] if e["ligand"] == ligand}
        for node in (*raw["model"]["cells"], *raw["model"]["extracellular"]):
            if node["id"] in exact:
                node["initial_amount_fmol"][ligand] = exact[node["id"]]
    world = World(raw=raw, inputs=inputs)
    shared, populations, site_sets = {}, [], []
    for entry in inputs["sets"]:
        world.facing[entry["id"]] = _facing(inputs, entry)
        if entry["shared"]:
            shared[entry["id"]] = entry
            site_sets.append(dict(id=entry["id"], functional_unit=f"{entry['id']}_site", catalogue=None,
                                  owner=_owner(entry), copies=entry["copies"],
                                  sites_per_copy=entry["sites_per_copy"],
                                  accessible_fraction=entry["accessible_fraction"]))  # fmt: skip
    sets = {e["id"]: e for e in inputs["sets"]}
    for pop in inputs["populations"]:
        if pop["set"] in shared:
            populations.append(sfx.member(pop["id"], pop["set"], ligand=pop["ligand"], k_on=pop["k_on"],
                                          k_off=pop["k_off"], theta0=pop["initial_occupancy"]))  # fmt: skip
            continue
        entry = sets[pop["set"]]
        own = sfx.population(pop["id"], copies=entry["copies"], sites_per_copy=entry["sites_per_copy"],
                             alpha=entry["accessible_fraction"], k_on=pop["k_on"], k_off=pop["k_off"],
                             theta0=pop["initial_occupancy"], unit=f"{entry['id']}_site", **{
                                 "node": entry["owner"]} if entry.get("face") is None else {
                                 "patch": entry["owner"], "face": entry["face"]})  # fmt: skip
        own["ligand"] = pop["ligand"]
        populations.append(own)
        world.set_of_engine_key[pop["id"]] = entry["id"]
    for key in shared:
        world.set_of_engine_key[key] = key
    multipliers = {m["of"]: m["value"] for m in inputs.get("multipliers") or []}
    controls = {
        (p["id"], "binding"): [(0.0, multipliers.get(p["id"], 1.0))] for p in inputs["populations"]
    }
    ligands = [sfx.ligand(trace_mM=trace[g], species=g) for g in inputs["ligands"]]
    raw = sfx.with_site_occupancy(raw, populations, ligands=ligands, controls=controls,
                                  site_sets=site_sets or None)  # fmt: skip
    wash = inputs.get("wash")
    if wash:
        buffer = {g: wash["buffer_mM"][g] for g in inputs["ligands"]}
        raw = wfx.with_wash(
            raw, [wash["node"]], [(wash["time_s"], wash["node"], wash["fraction"], buffer)]
        )
        world.washed_node = wash["node"]
    world.raw = raw
    return world
