"""The calcium store's worlds (docs/CALCIUM_STORE_AND_CHANNELS_DESIGN.md, sections 6 to 8 and 14).

Every number is synthetic and these worlds' own: no captured world's, and no measurement's. Each
world is a definition of cells.model.resolved_pump_composite@1 over cells.model.resolved_pump_tissue@3, closed (one
gauge, no held bath), with the registered laws alone:
- a store per cell: a finite outside node that no face names, bounded by one patch of its cell,
  declared by cells.operator.cell_owned_compartments@1;
- on each plasma patch: @3's own permeabilities for Na, K and Cl; a calcium leak and a calcium
  channel (cells.channel.cav1p2_m2h@1); a pump (cells.cycle.atp_driven_transporter_mass_action_positive@2) and the
  exchanger (cells.cycle.sodium_calcium_exchange_symmetric_barrier@1);
- on each bounding patch: @3's own permeabilities for K and Cl; a calcium leak; a release, gated
  by two species conditions at the cell (cells.transfer_factor.hill_product_factor@1: one reads IP3, one reads
  calcium); a pump;
- in each cell and each store: calcium binding a buffer in two steps (cells.operator.local_species_reactions@1).

- store_world: one cell, one finite outside node, its numbers those of reference_spec/inputs.json
  (`store_world`), so the code-blind references and these definitions read one file.
- two_cells: two such cells on one outside node, `local` (the gauge), with two more outside
  nodes, near and far, joined to it by faces, a junction between the cells and a calcium route on
  it. Near and far give two free field offsets, so it declares field solver version 3 (D147).
"""

import copy
import json
import math
from pathlib import Path

from cells.laws.electrochemistry import CHARGE_PER_FMOL

SPECIFICATION = Path(__file__).parent / "reference_spec" / "inputs.json"
SPECIES = (
    ("Na", 1), ("K", 1), ("Cl", -1), ("Ca", 2), ("B", -2), ("CaB", 0), ("Ca2B", 2),
    ("ATP", 0), ("ADP", 0), ("Pi", 0), ("IP3", -3),
)  # fmt: skip
VALENCE = dict(SPECIES)
IONS = ("Na", "K", "Cl", "Ca")
TRACE_mM, TRACE_FLOOR_FMOL = 1e-9, 1e-15  # An absent row's declared background, inert there.
ION_FLOOR_FMOL = 1e-10
IMEX = "cells.solver.imex_ars222_face_electromigration@1"
VERSION_2 = "cells.solver.capacitive_reduction_gauged_damped_newton@2"
VERSION_3 = "cells.solver.capacitive_reduction_gauged_damped_newton@3"  # Near and far: free offsets (D147).
CONSTANT_FIELD = "cells.route.passive_constant_field_permeation@1"
PUMP = "cells.cycle.atp_driven_transporter_mass_action_positive@2"
EXCHANGER = "cells.cycle.sodium_calcium_exchange_symmetric_barrier@1"
CHANNEL = "cells.channel.cav1p2_m2h@1"
CONDITION = "cells.transfer_factor.hill_product_factor@1"
REACTIONS = "cells.operator.local_species_reactions@1"
COMPARTMENTS = "cells.operator.cell_owned_compartments@1"
HELD_FUEL = (("ATP", "N"), ("ADP", "N"), ("Pi", "N"))
FORMS = dict(activation="hill_activation", inhibition="hill_inhibition")


def specification():
    """The reference specification's numbers (reference_spec/inputs.json)."""
    return json.loads(SPECIFICATION.read_text())


def _node(name, volume, amounts, charge, *, outside=False):
    """A node: the rows it is given, the trace of every other, and the fixed charge that gives it
    `charge` (C)."""
    full = {s: float(amounts.get(s, TRACE_mM * volume)) for s, _ in SPECIES}
    out = dict(
        id=name,
        volume_pL=volume,
        initial_amount_fmol=full,
        fixed_charge_equivalent_fmol=charge / CHARGE_PER_FMOL
        - math.fsum(VALENCE[s] * n for s, n in full.items()),
        initial_charge_C=charge,
    )
    return out | (dict(reservoir=False, boundary_potential_V=0.0) if outside else {})


def _patch(name, inside, outside, data):
    return dict(
        id=name,
        inside=inside,
        outside=outside,
        area_m2=data["area_m2"],
        capacitance_F=data["capacitance_F"],
        permeability_m_per_s={s: data["permeability_m_per_s"].get(s, 0.0) for s, _ in SPECIES},
        law="cells.route.constant_field@1",
        pump=None,
        calcium_pump=None,
    )


def _condition(name, node, reads):
    return dict(
        id=name,
        node=node,
        law=CONDITION,
        reads=[
            dict(
                species=r["species"],
                form=FORMS[r["form"]],
                half_saturation_mM=r["half_saturation_mM"],
                hill_coefficient=r["hill_coefficient"],
            )
            for r in reads
        ],
    )


def _population(name, patch, law, capacity, roles, parameters, held=()):
    return dict(
        id=name,
        host=patch,
        law=law,
        orientation={"N": "a"},  # Both cycles' N end is the patch's cell.
        capacity_fmol_s=capacity,
        roles=roles,
        parameters=parameters,
        held_rows=[list(row) for row in held],
    )


def cell_block(k, data):
    """One cell's part of a definition (its nodes, patches, routes, conditions, channel, pumps,
    exchanger and compartment), the suffix _k on every ID. `data` has the form of the
    specification's `store_world`."""
    cell, store, plasma, bounding = f"cell_{k}", f"store_{k}", f"plasma_{k}", f"bounding_{k}"
    nodes, patches = data["nodes"], data["patches"]
    v_m, v_b = patches["plasma"]["initial_voltage_V"], patches["bounding"]["initial_voltage_V"]
    c_m, c_b = patches["plasma"]["capacitance_F"], patches["bounding"]["capacitance_F"]
    q_store = -c_b * v_b
    q_cell = c_m * v_m - q_store  # The whole cell's charge is C_m V_m (section 2.8).
    fuel = dict(ATP="ATP", ADP="ADP", Pi="Pi")
    conditions = [
        _condition(f"{name}_{k}", cell, c["reads"]) for name, c in data["conditions"].items()
    ]
    routes = []
    for name, r in data["calcium_routes"].items():
        route = dict(
            id=f"{name}_{k}",
            patch=plasma if r["patch"] == "plasma" else bounding,
            law=CONSTANT_FIELD,
            species="Ca",
            permeability_m_per_s=r["permeability_m_per_s"],
        )
        if r.get("factors"):
            route["factors"] = [f"{c}_{k}" for c in r["factors"]]
        routes.append(route)
    channel = data["calcium_channel"]
    populations = [
        _population(
            f"{name}_{k}",
            plasma if pump["patch"] == "plasma" else bounding,
            PUMP,
            pump["capacity_fmol_per_s"],
            dict(role="Ca", **fuel),
            dict(
                stoichiometry=pump["stoichiometry"],
                km_role_mM=pump["K_role_mM"],
                km_atp_mM=pump["K_ATP_mM"],
            ),
            HELD_FUEL,
        )
        for name, pump in data["pumps"].items()
    ]
    x = data["exchanger"]
    populations.append(
        _population(
            f"exchanger_{k}",
            plasma,
            EXCHANGER,
            x["capacity_fmol_per_s"],
            dict(Na="Na", Ca="Ca"),
            dict(km_na_mM=x["K_Na_mM"], km_ca_mM=x["K_Ca_mM"]),
        )
    )
    return dict(
        cell=_node(cell, nodes["cell"]["volume_pL"], nodes["cell"]["amounts_fmol"], q_cell),
        store=_node(
            store,
            nodes["store"]["volume_pL"],
            nodes["store"]["amounts_fmol"],
            q_store,
            outside=True,
        ),
        outside_charge=-c_m * v_m,  # What the outside node holds against the whole cell.
        patches=[
            _patch(plasma, cell, data["outside"], patches["plasma"]),
            _patch(bounding, cell, store, patches["bounding"]),
        ],
        routes=routes,
        conditions=conditions,
        channel=dict(
            id=f"channel_{k}",
            membrane_id=plasma,
            kinetic_law=CHANNEL,
            max_permeability_m_per_s=channel["max_permeability_m_per_s"],
            abundance=channel["abundance"],
            initial_gate=[channel["initial_m"], channel["initial_h"]],
            permeant_ions=[dict(species_id="Ca", relative_permeability=1.0)],
        ),
        populations=populations,
        compartment=dict(
            id=f"store_space_{k}",
            node=store,
            patch=bounding,
            owner=cell,
            label=None,
            reference=None,
            role="lumen",
        ),
    )


def _buffer_operator(buffers, cells, stores):
    sites = {"cells": list(cells), "outside": list(stores)}
    moieties = dict(Ca=dict(Ca=1), B=dict(B=1), CaB=dict(Ca=1, B=1), Ca2B=dict(Ca=2, B=1))
    return dict(
        law=REACTIONS,
        standard_concentration_mM=1.0,
        species=[
            dict(id=s, moieties=moieties[s], standard_mu_RT=mu, catalogue=None, evidence=None)
            for s, mu in buffers["standard_mu_RT"].items()
        ],
        reactions=[
            dict(
                id=r["id"],
                sites=copy.deepcopy(sites),
                reactants=r["reactants"],
                products=r["products"],
                law="cells.species_reaction.ideal_detailed_balance_mass_action@1",
                forward_rate_per_s=r["forward_rate_per_s"],
                factors=[],
            )
            for r in buffers["reactions"]
        ],
    )


def definition(blocks, outside, *, data, gauge, faces, junctions, junction_routes, buffers, dt,
               steps, observe, field_solver):  # fmt: skip
    """A composite definition of the cells `blocks` (cell_block) and the other outside nodes. The
    stores follow `outside` in the node order, so no store is its component's first outside node."""
    entries = []
    for s, z in SPECIES:
        entry = dict(id=s, valence=z)
        if s in data["buffers"]["standard_mu_RT"]:
            entry["standard_mu_RT"] = data["buffers"]["standard_mu_RT"][s]
        if s in data["fuel_potentials_RT"]:
            entry["standard_mu_RT"] = data["fuel_potentials_RT"][s]
        if s not in IONS:
            entry["background"] = dict(trace_mM=TRACE_mM, floor_fmol=TRACE_FLOOR_FMOL)
        entries.append(entry)
    membranes = [p for b in blocks for p in b["patches"]]
    channels = [b["channel"] for b in blocks]
    operators = [dict(law=COMPARTMENTS, compartments=[b["compartment"] for b in blocks])]
    cells, stores = [b["cell"]["id"] for b in blocks], [b["store"]["id"] for b in blocks]
    if buffers:
        operators.append(_buffer_operator(data["buffers"], cells, stores))
    model = dict(
        id="cells.model.resolved_pump_composite@1",
        inner_model="cells.model.resolved_pump_tissue@3",
        temperature_K=data["temperature_K"],
        standard_concentration_mM=data["standard_concentration_mM"],
        species=entries,
        cells=[b["cell"] for b in blocks],
        extracellular=[*outside, *(b["store"] for b in blocks)],
        membranes=membranes,
        junctions=junctions,
        faces=faces,
        channels=channels,
        closure=dict(
            law="cells.field_closure.resolved_capacitor_components_current_continuity@1", gauge_reference=gauge
        ),
        passive_routes=[r for b in blocks for r in b["routes"]] + junction_routes,
        transporters=[t for b in blocks for t in b["populations"]],
        species_conditions=[c for b in blocks for c in b["conditions"]],
        operators=operators,
    )
    on, full = [dict(time=0.0, availability=1.0)], [dict(time=0.0, multiplier=1.0)]
    experiment = dict(
        membrane_controls=[dict(membrane_id=p["id"], schedule=list(on)) for p in membranes],
        junction_controls=[dict(junction_id=j["id"], schedule=list(on)) for j in junctions],
        pump_controls=[],
        calcium_pump_controls=[],
        channel_controls=[dict(channel_id=c["id"], schedule=list(on)) for c in channels],
        end_time=steps * dt,
        observation_times=[k * dt for k in observe],
    )
    if buffers:
        experiment["reaction_controls"] = [
            dict(reaction_id=r["id"], site=None, schedule=list(full))
            for r in data["buffers"]["reactions"]
        ]
    floors = {s: ION_FLOOR_FMOL if s in IONS else TRACE_FLOOR_FMOL for s, _ in SPECIES}
    execution = dict(
        dt=dt,
        capacity=len(blocks),
        extracellular_capacity=len(model["extracellular"]),
        membrane_capacity=len(membranes),
        edge_capacity=len(junctions),
        face_capacity=len(faces),
        channel_capacity=len(channels),
        backend="cpu",
        jit=True,
        precision="float64",
        solver=IMEX,
        field_solver=field_solver,
        max_steps=steps + 8,
        max_trace_bytes=2**28,
        material_balance_atol_fmol=floors,
    )
    return dict(schema_version=1, model=model, experiment=experiment, execution=execution)


def store_data(*, v_store_V=None):
    """The specification's one-cell world, with another initial store voltage where one is given."""
    data = copy.deepcopy(specification()["store_world"])
    data["outside"] = "outside"
    if v_store_V is not None:
        data["patches"]["bounding"]["initial_voltage_V"] = v_store_V
    return data


def store_world(*, dt, steps, observe=None, v_store_V=None, buffers=True, data=None):
    """The one-cell closed store world (module docstring): `steps` steps of dt, recorded at the
    steps in `observe` (default: the start and the end)."""
    data = store_data(v_store_V=v_store_V) if data is None else data
    block, node = cell_block(0, data), data["nodes"]["outside"]
    outside = _node(
        "outside", node["volume_pL"], node["amounts_fmol"], block["outside_charge"], outside=True
    )
    return definition(
        [block], [outside], data=data, gauge="outside", faces=[], junctions=[], junction_routes=[],
        buffers=buffers, dt=dt, steps=steps, observe=observe or (0, steps), field_solver=VERSION_2,
    )  # fmt: skip


# ------------------------------------------------------------------ the two-cell closed world

NEAR_FAR = dict(
    local=dict(volume_pL=2.4, mM=dict(Na=141.0, K=5.1, Cl=123.0, Ca=1.35)),
    near=dict(volume_pL=1.3, mM=dict(Na=127.0, K=7.4, Cl=116.0, Ca=1.1)),
    far=dict(volume_pL=3.4, mM=dict(Na=149.0, K=4.4, Cl=131.0, Ca=1.6)),
)
FACES = (("face_0", "local", "near"), ("face_1", "near", "far"), ("face_2", "far", "local"))
FACE_AREA_M2, FACE_LENGTH_M = 1.3e-11, 2.6e-5
DIFFUSIVITY = dict(Na=1.31e-9, K=1.93e-9, Cl=2.01e-9, Ca=7.6e-10)
JUNCTION = dict(
    area_m2=1.2e-10,
    permeability_m_per_s=dict(Na=2.3e-10, K=4.2e-10, Cl=3.1e-10),
    calcium_m_per_s=1.7e-8,
    threshold_voltage_V=0.017,
    minimum_open_fraction=0.12,
    initial_gate=0.72,
)
STORE_VOLTAGE_V = -0.005
# The second cell, against the specification's first: each number scales the first cell's (`v_m` is
# its own), and the concentrations in `cell_mM` and `store_mM` differ too, so that a read of the
# other cell's or the other store's row is told apart.
SECOND = dict(
    volume=1.35, store_volume=1.28, plasma=1.24, bounding=1.17, capacity=1.31, v_m=-0.046,
    permeability=0.91, release=1.12,
    cell_mM=dict(Na=1.12, Ca=1.45, IP3=0.82), store_mM=dict(K=0.97, Ca=0.88),
)  # fmt: skip


def second_data():
    """The second cell's numbers: the first cell's, each scaled (SECOND), its voltage its own."""
    data, s = store_data(v_store_V=STORE_VOLTAGE_V), SECOND
    for name, factor in (("cell", s["volume"]), ("store", s["store_volume"])):
        node, mM = data["nodes"][name], s[f"{name}_mM"]
        node["volume_pL"] *= factor
        node["amounts_fmol"] = {
            k: v * factor * mM.get(k, 1.0) for k, v in node["amounts_fmol"].items()
        }
    for name in ("plasma", "bounding"):
        patch = data["patches"][name]
        patch["area_m2"] *= s[name]
        patch["capacitance_F"] *= s[name]
        patch["permeability_m_per_s"] = {
            k: v * s["permeability"] for k, v in patch["permeability_m_per_s"].items()
        }
    data["patches"]["plasma"]["initial_voltage_V"] = s["v_m"]
    data["calcium_routes"]["release"]["permeability_m_per_s"] *= s["release"]
    for pump in data["pumps"].values():
        pump["capacity_fmol_per_s"] *= s["capacity"]
    data["exchanger"]["capacity_fmol_per_s"] *= s["capacity"]
    return data


def two_cells(*, dt, steps, observe=None, edit=None):
    """The two-cell closed world (module docstring). `edit(data_0, data_1)`, where given, changes
    the two cells' numbers before the definition is built."""
    first, second = store_data(v_store_V=STORE_VOLTAGE_V), second_data()
    for data in (first, second):
        data["outside"] = "local"
    if edit is not None:
        edit(first, second)
    blocks = [cell_block(0, first), cell_block(1, second)]
    charge = math.fsum(b["outside_charge"] for b in blocks)
    outside = [
        _node(
            name,
            n["volume_pL"],
            {s: c * n["volume_pL"] for s, c in n["mM"].items()},
            charge if name == "local" else 0.0,
            outside=True,
        )
        for name, n in NEAR_FAR.items()
    ]
    faces = [
        dict(
            id=name,
            sender=a,
            receiver=b,
            area_m2=FACE_AREA_M2,
            length_m=FACE_LENGTH_M,
            diffusivity_m2_per_s={s: DIFFUSIVITY.get(s, 0.0) for s, _ in SPECIES},
            law="cells.route.logmean_electrodiffusion@1",
        )
        for name, a, b in FACES
    ]
    j = JUNCTION
    junctions = [
        dict(
            id="junction",
            sender="cell_0",
            receiver="cell_1",
            area_m2=j["area_m2"],
            permeability_m_per_s={s: j["permeability_m_per_s"].get(s, 0.0) for s, _ in SPECIES},
            law="cells.route.constant_field@1",
            gate=dict(
                law="cells.junction.junction_voltage_relaxation@1",
                threshold_voltage_V=j["threshold_voltage_V"],
                minimum_open_fraction=j["minimum_open_fraction"],
                initial_gate=j["initial_gate"],
            ),
        )
    ]
    junction_routes = [
        dict(
            id="junction_calcium",
            junction="junction",
            law=CONSTANT_FIELD,
            species="Ca",
            permeability_m_per_s=j["calcium_m_per_s"],
        )
    ]
    return definition(
        blocks, outside, data=first, gauge="local", faces=faces, junctions=junctions,
        junction_routes=junction_routes, buffers=True, dt=dt, steps=steps,
        observe=observe or (0, steps), field_solver=VERSION_3,
    )  # fmt: skip
