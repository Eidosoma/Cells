"""Small worlds for the secreted-species operators (D150 version 1, the secreted-species design).

All values are synthetic. Every world is quiescent in its ions, the species-only world of the
design's §7: passive cells (no pump, no channel, zero membrane permeability), every node at the
bath's ion composition with a zero charge anchor, and zero ion diffusivity on every face, so no ion
moves and the energy flows and bound are the species' own. The neutral species S is declared by
the engine's helper (cells.core.inventory_species) at a trace background, with a species-scale
material floor; guard worlds start it from a pre-formed profile (the lead's ruling 5).

* world: cells, each with a capacitive wall patch on the held bath ``bath`` (so every node is in a
  capacitor component with a held bath) and contact patches on finite outside nodes; faces between
  nodes and to held baths;
* secreting_cell: one cell with a contact patch on one finite node, the node joined by a face to
  the bath (a cell that secretes into its cleft, which leaks to the far field);
* face_free: one cell and its finite node joined only by the contact patch (the RK4 guard world of
  the operators' work, §4.2);
* with_turnover / with_exchange: the operators' blocks and schedules, on a composite definition.
"""

import copy
import math

import numpy as np

from cells.core import pump_composite_spec as cs
from cells.core.inventory_species import add_inventory_species

ION_SPECIES = (("Na", 1), ("K", 1), ("Cl", -1))
BATH_mM = dict(Na=145.0, K=5.0, Cl=150.0)
SPECIES = "S"
TRACE_mM = 1e-9
FLOOR_FMOL = 1e-20
D_S = 1e-10  # m^2/s, an effective (FRAP-kind) diffusivity, synthetic.
WALL_AREA_M2, WALL_C_F = 1e-10, 1e-12
CONTACT_AREA_M2, CONTACT_C_F = 1e-11, 1e-13
TURNOVER, EXCHANGE = "scheduled_species_turnover@1", "scheduled_species_exchange@1"
IMEX = "imex_ars222_face_electromigration@1"
JUNCTION_AREA_M2, JUNCTION_THRESHOLD_V, JUNCTION_MINIMUM = 1e-11, 0.015, 0.1
REPLACEMENT = "scheduled_cell_replacement@1"
FORMATION = dict(
    law="delayed_first_order_junction_formation@1",
    initial_abundance=0.0,
    lag_s=600.0,
    time_constant_s=1800.0,
    gate_at_arrival="law_open",
)
NO_ROUTES = dict(
    channel_permeability_m_per_s={},
    channel_abundance={},
    membrane_permeability_m_per_s={},
    pump_capacity_fmol_per_s_m2=None,
    calcium_pump_capacity_fmol_per_s_m2=None,
)


def grid_times(end, dt, every):
    """Observation times on accepted boundaries: k * dt for integer k, and the end."""
    stride, count = max(1, int(round(every / dt))), int(round(end / dt))
    return sorted(
        {*(k * stride * dt for k in range(count // stride + 1) if k * stride < count), end}
    )


def _node(name, volume, *, outside=True, reservoir=False):
    """A node at the bath's ion composition with a zero charge anchor (electroneutral)."""
    amounts = {s: BATH_mM[s] * volume for s, _ in ION_SPECIES}
    charge = math.fsum(z * amounts[s] for s, z in ION_SPECIES)
    node = dict(
        id=name,
        volume_pL=volume,
        initial_amount_fmol=amounts,
        fixed_charge_equivalent_fmol=-charge,
        initial_charge_C=0.0,
    )
    return node | (dict(reservoir=reservoir, boundary_potential_V=0.0) if outside else {})


def _patch(name, inside, outside, area, capacitance):
    return dict(
        id=name,
        inside=inside,
        outside=outside,
        area_m2=area,
        capacitance_F=capacitance,
        permeability_m_per_s={s: 0.0 for s, _ in ION_SPECIES},
        law="constant_field@1",
        pump=None,
        calcium_pump=None,
    )


def world(
    *,
    cells=(("cell_0", 1.0),),
    nodes=(("ecs_0", 1.0),),
    baths=("bath",),
    contacts=(("contact_0", "cell_0", "ecs_0"),),
    faces=(("face_0", "ecs_0", "bath", 1e-10, 1e-5),),
    junctions=(),
    dt=1e-3,
    end=0.004,
    observation_times=None,
    solver=IMEX,
    trace_mM=TRACE_mM,
    concentrations_mM=None,
    diffusivity=D_S,
):
    """A quiescent composite definition with no operators and the species S declared.

    cells: (id, volume pL); nodes: finite outside nodes (id, volume pL); baths: held baths (the
    first holds every cell's wall patch); contacts: (patch id, cell, node); faces: (id, sender,
    receiver, area m^2, length m); junctions: (id, sender, receiver), gated, with zero ion
    permeability (donor copies need one). concentrations_mM: S at named nodes (a pre-formed
    profile).
    """
    from cells.processes import junction_gate

    outside = [_node(b, 1.0, reservoir=True) for b in baths]
    outside += [_node(name, volume) for name, volume in nodes]
    cell_list = [_node(name, volume, outside=False) for name, volume in cells]
    membranes = [_patch(f"wall_{c}", c, baths[0], WALL_AREA_M2, WALL_C_F) for c, _ in cells]
    membranes += [_patch(p, c, o, CONTACT_AREA_M2, CONTACT_C_F) for p, c, o in contacts]
    face_list = [
        dict(
            id=f,
            sender=a,
            receiver=b,
            area_m2=area,
            length_m=length,
            diffusivity_m2_per_s={s: 0.0 for s, _ in ION_SPECIES},
            law="logmean_electrodiffusion@1",
        )
        for f, a, b, area, length in faces
    ]
    params = junction_gate.Parameters(JUNCTION_THRESHOLD_V, JUNCTION_MINIMUM)
    opened = float(junction_gate.kinetics(0.0, params, xp=np).target)  # Its value at Vj = 0.
    junction_list = [
        dict(
            id=j,
            sender=a,
            receiver=b,
            area_m2=JUNCTION_AREA_M2,
            permeability_m_per_s={s: 0.0 for s, _ in ION_SPECIES},
            law="constant_field@1",
            gate=dict(
                law=junction_gate.LAW_ID,
                threshold_voltage_V=JUNCTION_THRESHOLD_V,
                minimum_open_fraction=JUNCTION_MINIMUM,
                initial_gate=opened,
            ),
        )
        for j, a, b in junctions
    ]
    always = [dict(time=0.0, availability=1.0)]
    raw = dict(
        schema_version=1,
        model=dict(
            id="resolved_pump_tissue@3",
            temperature_K=310.0,
            species=[dict(id=s, valence=z) for s, z in ION_SPECIES],
            cells=cell_list,
            extracellular=outside,
            membranes=membranes,
            junctions=junction_list,
            faces=face_list,
            closure=dict(
                law="resolved_capacitor_components_current_continuity@1", gauge_reference=None
            ),
            channels=[],
        ),
        experiment=dict(
            end_time=end,
            observation_times=list(observation_times or [0.0, end]),
            membrane_controls=[
                dict(membrane_id=p["id"], schedule=copy.deepcopy(always)) for p in membranes
            ],
            junction_controls=[
                dict(junction_id=j["id"], schedule=copy.deepcopy(always)) for j in junction_list
            ],
            pump_controls=[],
            calcium_pump_controls=[],
            channel_controls=[],
        ),
        execution=dict(
            dt=dt,
            capacity=len(cell_list),
            extracellular_capacity=len(outside),
            membrane_capacity=len(membranes),
            edge_capacity=len(junction_list),
            face_capacity=max(1, len(face_list)),
            channel_capacity=0,
            backend="cpu",
            jit=True,
            precision="float64",
            solver=solver,
            field_solver="capacitive_reduction_gauged_damped_newton@2",
            max_steps=int(math.ceil(end / dt)) + 8,
            max_trace_bytes=2**31,
            material_balance_atol_fmol={s: 1e-10 for s, _ in ION_SPECIES},
        ),
    )
    raw = add_inventory_species(
        raw,
        SPECIES,
        trace_mM=trace_mM,
        diffusivity_m2_per_s=diffusivity,
        floor_fmol=FLOOR_FMOL,
        concentrations_mM=concentrations_mM,
    )
    return cs.frozen_definition(raw)


def secreting_cell(*, pool_mM=1e-3, node_mM=5e-4, **kwargs):
    """One cell secreting into its node, which leaks to the bath through one face; a pre-formed
    profile by default (the cell's pool and the node above the trace)."""
    profile = dict(cell_0=pool_mM, ecs_0=node_mM)
    return world(concentrations_mM=kwargs.pop("concentrations_mM", profile), **kwargs)


def face_free(*, pool_mM=1e-3, node_mM=5e-4, **kwargs):
    """One cell and its finite node joined only by the contact patch (no face)."""
    profile = dict(cell_0=pool_mM, ecs_0=node_mM)
    return world(faces=(), concentrations_mM=kwargs.pop("concentrations_mM", profile), **kwargs)


def identity(catalogue=None, evidence=None):
    return [dict(id=SPECIES, catalogue=catalogue, evidence=evidence)]


def with_turnover(raw, routes, controls, *, templates=(), species=None):
    """routes: (id, node, kind); controls: (route id, carrier id or None, [(time, rate), ...])."""
    out = copy.deepcopy(raw)
    out["model"]["operators"].append(
        dict(
            law=TURNOVER,
            species=species or identity(),
            routes=[dict(id=r, species=SPECIES, node=n, kind=k) for r, n, k in routes],
            templates=[dict(template_id=t, rates=dict(rates)) for t, rates in templates],
        )
    )
    out["experiment"]["turnover_controls"] = [
        dict(route_id=r, carrier_id=c, schedule=[dict(time=t, rate=v) for t, v in changes])
        for r, c, changes in controls
    ]
    return out


def with_exchange(raw, routes, controls, *, templates=(), species=None):
    """routes: (id, patch, direction, law); controls: (route id, carrier id, [(time, rate) or
    (time, rate, K_M), ...])."""
    out = copy.deepcopy(raw)
    out["model"]["operators"].append(
        dict(
            law=EXCHANGE,
            species=species or identity(),
            routes=[
                dict(id=r, species=SPECIES, patch=p, direction=d, law=law)
                for r, p, d, law in routes
            ],
            templates=[dict(template_id=t, rates=dict(rates)) for t, rates in templates],
        )
    )

    def change(entry):
        if len(entry) == 3:
            return dict(time=entry[0], rate=entry[1], saturation_mM=entry[2])
        return dict(time=entry[0], rate=entry[1])

    out["experiment"]["exchange_controls"] = [
        dict(route_id=r, carrier_id=c, schedule=[change(e) for e in changes])
        for r, c, changes in controls
    ]
    return out


def template(raw, cell_id, template_id, *, s_mM=None, routes=None):
    """A replacement template with one cell's declared state (S at s_mM if given)."""
    cell = next(c for c in raw["model"]["cells"] if c["id"] == cell_id)
    amounts = dict(cell["initial_amount_fmol"])
    if s_mM is not None:
        amounts[SPECIES] = s_mM * cell["volume_pL"]
    return dict(
        id=template_id,
        volume_pL=cell["volume_pL"],
        fixed_charge_equivalent_fmol=cell["fixed_charge_equivalent_fmol"],
        amounts_fmol=amounts,
        channel_gates={},
        route_values=copy.deepcopy(NO_ROUTES if routes is None else routes),
    )


def with_replacement(raw, templates=(), events=()):
    """replacement@1 first in the operator list; events: (time, slot, template, carrier) or
    (time, slot, template or None, carrier, donor) for a donor copy."""
    out = copy.deepcopy(raw)
    out["model"]["operators"].insert(
        0,
        dict(
            law=REPLACEMENT,
            junction_formation=dict(FORMATION),
            templates=[copy.deepcopy(t) for t in templates],
            template_capacity=max(1, len(templates)),
        ),
    )
    out["experiment"]["replacement_events"] = [
        dict(
            time=e[0],
            slot=e[1],
            newcomer="isolated_template" if len(e) == 4 else "donor_copy",
            template=e[2],
            donor=None if len(e) == 4 else e[4],
            carrier_id=e[3],
        )
        for e in events
    ]
    return out


# ------------------------------------------------------------------ the mixed world (probe 2's)

CHAIN = 6
CHAIN_NODE_PL = 1.0
CHAIN_FACE = (1e-10, 1e-5)  # Area m^2, length m.
CHAIN_ION_D = 1e-9
CHAIN_CONTACT_M2 = 1e-10
CHAIN_PROFILE_mM = {
    "cell_0": 1e-3,
    **{f"ecs_{i}": 5e-4 * 0.5**i for i in range(CHAIN)},  # Pre-formed: no jump of decades.
}


def heredity_chain(*, secreted, dt=1e-3, end=0.1, observation_times=None, profile=None):
    """Six heredity cells (state H) on their own held baths, each with a contact patch on a finite
    1 pL node; the nodes form a chain by faces (ion D 1e-9), the last joined to bath_5 (probe 2's
    world, design §11.1). The ions move: pumps, channels, junction-free contacts and ion faces.
    secreted: S declared (trace 1e-9 mM, D_S on every face, a pre-formed profile from cell_0 down
    the chain), else the four heredity species only. A composite definition with no operators."""
    from cells.processes.electrochemistry import CHARGE_PER_FMOL
    from validation.tissue import surface_pump_v3_fixtures as v3fx

    state = v3fx.HEREDITY_STATES["H"][:4]
    times = observation_times or [0.0, end]
    raw = v3fx.heredity_cells([state] * CHAIN, dt=dt, end_time=end, observation_times=times)
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    ids = [s["id"] for s in m["species"]]
    z = {s["id"]: s["valence"] for s in m["species"]}
    bath = dict(v3fx.HEREDITY_BATH_mM)
    contact_c = 0.05 * CHAIN_CONTACT_M2
    for i in range(CHAIN):
        vm = state[0]
        cell = m["cells"][i]
        # Electrically consistent start: the node at the bath's potential, the contact at Vm.
        cell["initial_charge_C"] = (v3fx.HEREDITY_CAPACITANCE_F + contact_c) * vm
        cell["fixed_charge_equivalent_fmol"] = cell["initial_charge_C"] / CHARGE_PER_FMOL - (
            math.fsum(z[s] * cell["initial_amount_fmol"][s] for s in ids)
        )
        amounts = {s: bath[s] * CHAIN_NODE_PL for s in ids}
        charge = -contact_c * vm
        m["extracellular"].append(
            dict(
                id=f"ecs_{i}",
                volume_pL=CHAIN_NODE_PL,
                initial_amount_fmol=amounts,
                fixed_charge_equivalent_fmol=charge / CHARGE_PER_FMOL
                - math.fsum(z[s] * amounts[s] for s in ids),
                initial_charge_C=charge,
                reservoir=False,
                boundary_potential_V=0.0,
            )
        )
        contact = copy.deepcopy(m["membranes"][i])
        contact.update(
            id=f"contact_{i}",
            outside=f"ecs_{i}",
            pump=None,
            calcium_pump=None,
            area_m2=CHAIN_CONTACT_M2,
            capacitance_F=contact_c,
        )
        m["membranes"].append(contact)
        e["membrane_controls"].append(
            dict(membrane_id=f"contact_{i}", schedule=[dict(time=0.0, availability=1.0)])
        )
    pairs = [(f"ecs_{i}", f"ecs_{i + 1}") for i in range(CHAIN - 1)]
    pairs.append((f"ecs_{CHAIN - 1}", f"bath_{CHAIN - 1}"))
    for k, (a, b) in enumerate(pairs):
        m["faces"].append(
            dict(
                id=f"face_{k}",
                sender=a,
                receiver=b,
                area_m2=CHAIN_FACE[0],
                length_m=CHAIN_FACE[1],
                diffusivity_m2_per_s={s: CHAIN_ION_D for s in ids},
                law="logmean_electrodiffusion@1",
            )
        )
    x.update(extracellular_capacity=2 * CHAIN, membrane_capacity=2 * CHAIN, face_capacity=CHAIN)
    if secreted:
        raw = add_inventory_species(
            raw,
            SPECIES,
            trace_mM=TRACE_mM,
            diffusivity_m2_per_s=D_S,
            floor_fmol=FLOOR_FMOL,
            concentrations_mM=CHAIN_PROFILE_mM if profile is None else profile,
        )
    return cs.frozen_definition(raw)


def chain_operators(raw, *, secrete=0.1, produce=1e-4, clear=0.5, uptake=1e6, ku=1e-6):
    """Both operators active on the chain: cell_0 produces and secretes into ecs_0, ecs_2 clears,
    cell_3 takes S up from ecs_3 (saturable) and cell_5 from ecs_5 (first-order)."""
    raw = with_turnover(
        raw,
        [("produce", "cell_0", "production"), ("clear", "ecs_2", "clearance")],
        [("produce", "cell_0", [(0.0, produce)]), ("clear", None, [(0.0, clear)])],
    )
    return with_exchange(
        raw,
        [
            ("secrete", "contact_0", "export", "first_order"),
            ("sink", "contact_3", "import", "saturable"),
            ("take_up", "contact_5", "import", "first_order"),
        ],
        [
            ("secrete", "cell_0", [(0.0, secrete)]),
            ("sink", "cell_3", [(0.0, uptake, 5e-4)]),
            ("take_up", "cell_5", [(0.0, ku)]),
        ],
    )
