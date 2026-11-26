"""Engine worlds for the gap-junction cancer replication (cells.model.resolved_pump_tissue@3 as it is).

Nothing here adds physics. The worlds use @3's own laws:
* cells.route.constant_field@1 on membranes and junctions, for one neutral species `mR` (valence 0, so the
  constant-field flux is Fick's flux P A (c_out - c_in));
* held reservoirs (cells.field_closure.resolved_capacitor_components_current_continuity@1 closes the field; with no
  charged species every voltage is zero);
* cells.junction.junction_voltage_relaxation@1 gates pinned open (minimum open fraction 1);
* the IMEX solver cells.solver.imex_ars222_face_electromigration@1, whose explicit-rate bound covers neutral
  species on membranes and junctions (surface_pump.neutral_material_rate).

The linear communication network is the preprint's "intuitive model" (its equations 1-2 and
appendix): a cell with generation i_gen0 = K_dec u and linear decay K_dec has the steady
input-output law [mR] = u - i_exit / G_eq with G_eq = V K_dec. The world gives each cell exactly
that law through its Norton equivalent, which the preprint itself draws: a membrane of
conductance P A = V K_dec to a reservoir held at the unloaded value u. With c the cell's
concentration, V dc/dt = P A (u - c) - (junction and probe outflows), which is the preprint's
balance term for term. It is a linear model only: the full EMT model's bistable switch is not
reduced this way (and runs into the gaps that `refusals` records).

Parameters (declared, not from the preprint, which reports the linear model in ratios): a sphere
of radius 5 um, K_dec = 0.05 1/s (a nominal rate: every reported quantity depends only on G_GJ /
G_eq and the unloaded values), junction area 1e-11 m^2, membrane capacitance 0.05 F/m^2.

Each network builder returns a Network: the cells, junctions and probes, and the cells' centres in
um for the run view (a prescribed 2D layout after the preprint's drawings, touching spheres; the
engine has no geometry for these worlds, so the layout changes no result). Every run is observed
every OBSERVE_EVERY_S, which adds rows to the record and changes no step.
"""

import copy
import math
from typing import NamedTuple

from cells.definitions.surface_tissue_spec import NODE_BOUNDS
from cells.records import run_view

SPECIES = "mR"
R_CELL_M = 5e-6
V_CELL_PL = 4.0 / 3.0 * math.pi * R_CELL_M**3 * 1e15
A_CELL_M2 = 4.0 * math.pi * R_CELL_M**2
K_DEC_PER_S = 0.05
G_EQ1_M3_S = K_DEC_PER_S * V_CELL_PL * 1e-15  # One cell's Norton (decay) conductance.
JUNCTION_AREA_M2 = 1e-11
SPECIFIC_CAPACITANCE_F_M2 = 0.05
SOLVER = "cells.solver.imex_ars222_face_electromigration@1"
FIELD_SOLVER = "cells.solver.capacitive_reduction_gauged_damped_newton@2"
GATE_LAW = "cells.junction.junction_voltage_relaxation@1"
# dt times @3's explicit rate (its stability bound is 1) at most 0.04. The binding constraint is
# @3's energy check (2e-3 of the booked flows under ARS(2,2,2)), not stability. Two dt studies
# (gap-junction-20261117/runs/smoke-01/dt_fig5net100.json, runs/dev-01/dt_fig3g50.json):
#   Figure 5a's network at g = 100 (rate 40.1/s): refused at dt x rate 0.63 and 0.31; passed at
#     0.157 (energy residual 1.4e-3 of the flows) and 0.078 (3.5e-4);
#   Figure 3's two cells at g = 50 (rate 5.1/s): refused at 0.080; passed at 0.040 (6.4e-4) and
#     0.020 (1.6e-4).
# The residual is second order in dt with a world-dependent coefficient. The compared quantity,
# the steady state, is the scheme's fixed point and does not depend on dt.
STEP_BOUND_MARGIN = 0.04
BASE_DT_S = 0.25  # 1/4 s, exact in binary, so every observation time is an exact grid point.
END_S = 600.0  # 30 slowest-mode time constants (1/K_dec = 20 s): residual e^-30 at most.
SETTLE_S = 10.0  # The steady-state check compares end - SETTLE_S with end.
OBSERVE_EVERY_S = 2.0  # Observation rows for the record and the viewer (a multiple of every dt).


class Network(NamedTuple):
    """cells: (id, unloaded mM, size); edges: (id, i, j, g); probes: (id, i, held mM, g);
    centres_um: one (x, y) per cell, for the run view only."""

    cells: tuple
    edges: tuple
    probes: tuple
    centres_um: tuple


def radius_um(size):
    return R_CELL_M * 1e6 * size ** (1.0 / 3.0)


def geometry(network, source):
    """The run view's prescribed geometry: the cells as touching spheres in the plane."""
    return run_view.Geometry(
        unit="um",
        dimensions=2,
        sets={
            "cell": {
                "kind": "spheres",
                "centres": [list(c) for c in network.centres_um],
                "radius": [radius_um(size) for _, _, size in network.cells],
            }
        },
        source=source,
    )


def _node(node_id, mM, volume_pL, *, reservoir):
    node = dict(
        id=node_id,
        volume_pL=volume_pL,
        initial_amount_fmol={SPECIES: mM * volume_pL},
        fixed_charge_equivalent_fmol=0.0,
        initial_charge_C=0.0,
    )
    if reservoir:
        node.update(reservoir=True, boundary_potential_V=0.0)
    return node


def _membrane(membrane_id, cell_id, outside_id, conductance_m3_s, size):
    area = A_CELL_M2 * size ** (2.0 / 3.0)
    return dict(
        id=membrane_id,
        inside=cell_id,
        outside=outside_id,
        area_m2=area,
        capacitance_F=SPECIFIC_CAPACITANCE_F_M2 * area,
        permeability_m_per_s={SPECIES: conductance_m3_s / area},
        law="cells.route.constant_field@1",
        pump=None,
        calcium_pump=None,
    )


def explicit_rate(cells, edges, probes):
    """@3's neutral material rate for this network (1/s): 2 max_i sum P A / V_i."""
    total = [size * G_EQ1_M3_S for _, _, size in cells]
    for _, i, j, g in edges:
        total[i] += g * G_EQ1_M3_S
        total[j] += g * G_EQ1_M3_S
    for _, i, _, g in probes:
        total[i] += g * G_EQ1_M3_S
    return 2.0 * max(
        t / (size * V_CELL_PL * 1e-15) for t, (_, _, size) in zip(total, cells, strict=True)
    )


def step(cells, edges, probes):
    """BASE_DT_S halved until dt * rate <= STEP_BOUND_MARGIN (END_S stays an exact grid point)."""
    dt, rate = BASE_DT_S, explicit_rate(cells, edges, probes)
    while dt * rate > STEP_BOUND_MARGIN:
        dt /= 2.0
    return dt


def linear_network(cells, edges=(), probes=(), *, junction_scale=1.0, end=END_S, dt=None):
    """A cells.model.resolved_pump_tissue@3 definition of linear cells joined by junctions.

    cells: (id, unloaded mM, size), size scaling the volume and so G_eq = size G_EQ1;
    edges: (id, i, j, g) with G_GJ = g G_EQ1; probes: (id, i, held mM, g), an extra membrane of
    conductance g G_EQ1 from cell i to its own held reservoir (a load at the cell, for the
    Norton measurement). junction_scale multiplies every junction permeability (the planted
    control). Each cell starts at its unloaded value, as Figure 3b's cells do."""
    dt = step(cells, edges, probes) if dt is None else dt
    model_cells, outside, membranes = [], [], []
    for cell_id, unloaded, size in cells:
        volume = size * V_CELL_PL
        model_cells.append(_node(cell_id, unloaded, volume, reservoir=False))
        outside.append(_node(f"{cell_id}_source", unloaded, 1.0, reservoir=True))
        membranes.append(
            _membrane(f"{cell_id}_norton", cell_id, f"{cell_id}_source", size * G_EQ1_M3_S, size)
        )
    for probe_id, i, held, g in probes:
        outside.append(_node(f"{probe_id}_held", held, 1.0, reservoir=True))
        membranes.append(
            _membrane(probe_id, cells[i][0], f"{probe_id}_held", g * G_EQ1_M3_S, cells[i][2])
        )
    junctions = [
        dict(
            id=edge_id,
            sender=cells[i][0],
            receiver=cells[j][0],
            area_m2=JUNCTION_AREA_M2,
            permeability_m_per_s={SPECIES: junction_scale * g * G_EQ1_M3_S / JUNCTION_AREA_M2},
            law="cells.route.constant_field@1",
            gate=dict(
                law=GATE_LAW, threshold_voltage_V=0.0, minimum_open_fraction=1.0, initial_gate=1.0
            ),
        )
        for edge_id, i, j, g in edges
    ]
    always = [dict(time=0.0, availability=1.0)]
    if end > SETTLE_S:
        every = [k * OBSERVE_EVERY_S for k in range(int(end // OBSERVE_EVERY_S) + 1)]
        observe = sorted({*every, end - SETTLE_S, end})
    else:
        observe = [0.0, end]
    return dict(
        schema_version=1,
        model=dict(
            id="cells.model.resolved_pump_tissue@3",
            temperature_K=310.0,
            species=[dict(id=SPECIES, valence=0)],
            cells=model_cells,
            extracellular=outside,
            membranes=membranes,
            junctions=junctions,
            faces=[],
            closure=dict(
                law="cells.field_closure.resolved_capacitor_components_current_continuity@1", gauge_reference=None
            ),
            channels=[],
        ),
        experiment=dict(
            end_time=end,
            observation_times=observe,
            membrane_controls=[
                dict(membrane_id=p["id"], schedule=copy.deepcopy(always)) for p in membranes
            ],
            junction_controls=[
                dict(junction_id=j["id"], schedule=copy.deepcopy(always)) for j in junctions
            ],
            pump_controls=[],
            calcium_pump_controls=[],
            channel_controls=[],
        ),
        execution=dict(
            dt=dt,
            capacity=len(model_cells),
            extracellular_capacity=len(outside),
            membrane_capacity=len(membranes),
            edge_capacity=len(junctions),
            face_capacity=0,
            channel_capacity=0,
            backend="cpu",
            jit=True,
            precision="float64",
            solver=SOLVER,
            field_solver=FIELD_SOLVER,
            max_steps=int(math.ceil(end / dt)) + 8,
            max_trace_bytes=2**31,
            material_balance_atol_fmol={SPECIES: 1e-10},
        ),
    )


# --- The preprint's networks -------------------------------------------------------------------


def figure3(g, unloaded=(5.0, 10.0)):
    """Two equal cells, A and B, at their unloaded values, joined by G_GJ = g G_eq."""
    cells = (("A", unloaded[0], 1.0), ("B", unloaded[1], 1.0))
    d = 2.0 * radius_um(1.0)
    return Network(cells, (("gj_AB", 0, 1, g),), (), ((0.0, 0.0), (d, 0.0)))


def figure5_lumped(g, ratio=4.0 / 3.0, unloaded=(10.0, 5.0)):
    """Figure 5b's model: cell B `ratio` times cell A (equation 2 with G_eq,B = ratio G_eq,A)."""
    cells = (("A", unloaded[0], 1.0), ("B", unloaded[1], ratio))
    d = radius_um(1.0) + radius_um(ratio)
    return Network(cells, (("gj_AB", 0, 1, g),), (), ((0.0, 0.0), (d, 0.0)))


def figure5_network(g, unloaded=(10.0, 5.0)):
    """Figure 5a as drawn: A with two backup cells, B with three, every junction G_GJ = g G_eq."""
    cells = [("A", unloaded[0], 1.0), ("B", unloaded[1], 1.0)]
    cells += [(f"A{k}", unloaded[0], 1.0) for k in (1, 2)]
    cells += [(f"B{k}", unloaded[1], 1.0) for k in (1, 2, 3)]
    edges = [("gj_AB", 0, 1, g), ("gj_A1", 0, 2, g), ("gj_A2", 0, 3, g)]
    edges += [("gj_B1", 1, 4, g), ("gj_B2", 1, 5, g), ("gj_B3", 1, 6, g)]
    d = 2.0 * radius_um(1.0)

    def at(origin, degrees):
        return (origin + d * math.cos(math.radians(degrees)), d * math.sin(math.radians(degrees)))

    centres = [(0.0, 0.0), (d, 0.0), at(0.0, 150.0), at(0.0, 210.0)]
    centres += [at(d, 60.0), at(d, 0.0), at(d, -60.0)]
    return Network(tuple(cells), tuple(edges), (), tuple(centres))


def chain(n, held, *, g=1.0, g_probe=1.0, unloaded=1.0):
    """A straight chain of n cells (cell n-1 the port), G_GJ = g G_eq, loaded at the port by a
    probe of conductance g_probe G_eq to a reservoir held at `held` (Figure 8's exit current)."""
    cells = tuple((f"c{k}", unloaded, 1.0) for k in range(n))
    edges = tuple((f"gj_{k}", k, k + 1, g) for k in range(n - 1))
    d = 2.0 * radius_um(1.0)
    centres = tuple((k * d, 0.0) for k in range(n))
    return Network(cells, edges, (("probe", n - 1, held, g_probe),), centres)


# --- Gap probes: the engine's own refusals and registries, definition time only -----------------


def junction_route_reaction(junction_permeability_m_s):
    """A two-cell composite world in which the neutral species S has a junction route (when the
    permeability is positive) and cells.operator.local_species_reactions@1 makes S in both cells: the
    preprint's miRNA, which is made and destroyed in each cell and crosses junctions."""
    from validation.tissue import secreted_species_fixtures as sfx
    from validation.tissue import species_reactions_fixtures as rfx

    raw = sfx.world(
        cells=(("cell_0", 1.0), ("cell_1", 1.0)),
        nodes=(),
        contacts=(),
        faces=(),
        junctions=(("j_0", "cell_0", "cell_1"),),
        concentrations_mM={"cell_0": 1e-3, "cell_1": 1e-3},
    )
    raw["model"]["junctions"][0]["permeability_m_per_s"][sfx.SPECIES] = junction_permeability_m_s
    sites = {"cells": "all"}
    return rfx.with_reactions(
        raw,
        [rfx.species(sfx.SPECIES)],
        [rfx.mass_action("make_S", sites, {}, {sfx.SPECIES: 1}, 1e-6)],
        [("make_S", None, [(0.0, 1.0)])],
    )


def junction_route_passive():
    """junction_route_reaction's world with no @3 junction route for S, carried instead by a
    cells.kind.passive_routes@1 route (cells.route.passive_neutral_permeation@1) on the junction."""
    raw = junction_route_reaction(0.0)
    raw["model"]["passive_routes"] = [
        dict(id="s_route", junction="j_0", law=PASSIVE_LAW, species="S", permeability_m_per_s=1e-9)
    ]
    return raw


def emt_switch_probe(cells=(("cell_0", 1.0),), junctions=()):
    """One cell with the preprint's EMT switch written as cells.operator.local_species_reactions@1 reactions:
    the structure of its Figure 2 and Methods with synthetic values (the preprint prints none).

    miR200 (u) and Zeb mRNA (m) are made at rate g (1 + lambda x^n/K^n) / (1 + x^n/K^n) of ZEB (z),
    the modified Hill form: an inhibition source plus lambda times an activation source. ZEB is
    translated from m through six miR200 binding sites at fast equilibrium: with r = u/x0, the
    rate g3 m sum_i C(6,i) l_i r^i/(1 + r)^6, each term the reaction m -> m + z with i Hill
    activations and 6 - i Hill inhibitions of u (n = 1, K = x0). Each species decays at first
    order. Snail is a fixed input folded into the rate constants. No species has a route."""
    from validation.tissue import species_reactions_fixtures as rfx

    names = ("u", "m", "z")
    raw = rfx.species_world(
        extra=names,
        faces=False,
        cells=cells,
        nodes=(),
        contacts=(),
        junctions=junctions,
        profile={name: {cell_id: 1e-3 for cell_id, _ in cells} for name in names},
    )
    sites = {"cells": "all"}
    k_half, x0 = 1e-3, 1e-3  # mM, synthetic.
    reactions = []
    for name, n in (("u", 3), ("m", 2)):
        reactions.append(
            rfx.mass_action(
                f"{name}_low",
                sites,
                {},
                {name: 1},
                1e-5,
                [rfx.hill("hill_inhibition", "z", k_half, n)],
            )
        )
        reactions.append(
            rfx.mass_action(
                f"{name}_high",
                sites,
                {},
                {name: 1},
                2e-5,
                [rfx.hill("hill_activation", "z", k_half, n)],
            )
        )
    for i in range(7):
        factors = [rfx.hill("hill_activation", "u", x0, 1.0)] * i
        factors += [rfx.hill("hill_inhibition", "u", x0, 1.0)] * (6 - i)
        reactions.append(
            rfx.mass_action(f"z_site{i}", sites, {"m": 1}, {"m": 1, "z": 1}, 1e-3, factors)
        )
    for name, k in (("u", 0.05), ("m", 0.5), ("z", 0.1)):
        reactions.append(rfx.mass_action(f"{name}_decay", sites, {name: 1}, {}, k))
    controls = [(r["id"], None, [(0.0, 1.0)]) for r in reactions]
    return rfx.with_reactions(raw, [rfx.species(n) for n in names], reactions, controls)


# --- The linear model as written (part aswritten) ------------------------------------------------

AS_WRITTEN_SCALE_mM = 1e-3  # One unit of the preprint's [mR] is 1 uM here: a trace beside the ions.
AS_WRITTEN_SPECIES = "S"  # The inventory species the fixtures declare (neutral, trace background).
PASSIVE_LAW = "cells.route.passive_neutral_permeation@1"


def as_written(network, *, dt=None, end=END_S, junction_scale=1.0):
    """The preprint's linear cells as it writes them, in cells.model.resolved_pump_composite@1 over @3.

    Each cell: generation K_dec u and first-order decay K_dec (cells.operator.local_species_reactions@1: one
    zeroth-order source per unloaded value at its cells, one decay at every cell). Each junction:
    a cells.kind.passive_routes@1 route of cells.route.passive_neutral_permeation@1 for the species, P A = g G_eq1,
    its junction's gate pinned open. Each probe: the same law on a patch from the port cell to its
    own held bath. The ions sit at the bath's composition with zero permeability (the species-only
    world of the secreted-species fixtures), so nothing but the species moves. Volumes, G_eq and
    dt are those of linear_network; amounts are in uM (AS_WRITTEN_SCALE_mM)."""
    from validation.tissue import secreted_species_fixtures as sfx
    from validation.tissue import species_reactions_fixtures as rfx

    cells, edges, probes = network.cells, network.edges, network.probes
    dt = step(cells, edges, probes) if dt is None else dt
    scale, species = AS_WRITTEN_SCALE_mM, AS_WRITTEN_SPECIES
    observe = sorted(
        {
            *(k * OBSERVE_EVERY_S for k in range(int(end // OBSERVE_EVERY_S) + 1)),
            end - SETTLE_S,
            end,
        }
    )
    baths = ("bath", *(f"{probe_id}_held" for probe_id, *_ in probes))
    profile = {cell_id: u * scale for cell_id, u, _ in cells}
    profile.update({f"{probe_id}_held": held * scale for probe_id, _, held, _ in probes})
    raw = sfx.world(
        cells=tuple((cell_id, size * V_CELL_PL) for cell_id, _, size in cells),
        nodes=(),
        baths=baths,
        contacts=tuple(
            (f"{probe_id}_patch", cells[i][0], f"{probe_id}_held") for probe_id, i, _, _ in probes
        ),
        faces=(),
        junctions=tuple((edge_id, cells[i][0], cells[j][0]) for edge_id, i, j, _ in edges),
        dt=dt,
        end=end,
        observation_times=observe,
        concentrations_mM=profile,
    )
    m = raw["model"]
    for junction in m["junctions"]:
        junction["gate"].update(
            threshold_voltage_V=0.0, minimum_open_fraction=1.0, initial_gate=1.0
        )
    routes = []
    for (edge_id, _, _, g), junction in zip(edges, m["junctions"], strict=True):
        p = junction_scale * g * G_EQ1_M3_S / junction["area_m2"]
        routes.append(
            dict(
                id=f"{edge_id}_route",
                junction=edge_id,
                law=PASSIVE_LAW,
                species=species,
                permeability_m_per_s=p,
            )
        )
    patches = {p["id"]: p for p in m["membranes"]}
    for probe_id, _, _, g in probes:
        patch = patches[f"{probe_id}_patch"]
        p = g * G_EQ1_M3_S / patch["area_m2"]
        routes.append(
            dict(
                id=f"{probe_id}_route",
                patch=patch["id"],
                law=PASSIVE_LAW,
                species=species,
                permeability_m_per_s=p,
            )
        )
    m["passive_routes"] = routes
    sites_by_value = {}
    for cell_id, u, _ in cells:
        sites_by_value.setdefault(u, []).append(cell_id)
    reactions = [
        rfx.mass_action(f"make_{k}", {"cells": ids}, {}, {species: 1}, K_DEC_PER_S * u * scale)
        for k, (u, ids) in enumerate(sorted(sites_by_value.items()))
    ]
    reactions.append(rfx.mass_action("decay", {"cells": "all"}, {species: 1}, {}, K_DEC_PER_S))
    controls = [(r["id"], None, [(0.0, 1.0)]) for r in reactions]
    return rfx.with_reactions(raw, [rfx.species(species)], reactions, controls)


def emt_switch_two_cells_passive():
    """emt_switch_probe's switch in two cells joined by a junction whose passive route carries
    miR200 (u): the preprint's neither-condition model, definition only, synthetic values."""
    raw = emt_switch_probe(
        cells=(("cell_0", 1.0), ("cell_1", 1.0)), junctions=(("j_0", "cell_0", "cell_1"),)
    )
    raw["model"]["passive_routes"] = [
        dict(id="u_route", junction="j_0", law=PASSIVE_LAW, species="u", permeability_m_per_s=1e-9)
    ]
    return raw


def lattice_nodes(shape):
    """Field nodes a lattice of cells on one shared bath needs (cells + 1)."""
    return math.prod(shape) + 1


def shared_bath(n):
    """n unconnected cells on one held bath: the node count of a tissue of n cells. Two steps
    long, so only the definition's own checks can refuse it."""
    raw = linear_network((("c0", 1.0, 1.0),), end=2 * BASE_DT_S, dt=BASE_DT_S)
    m, x = raw["model"], raw["execution"]
    m["cells"] = [_node(f"c{k}", 1.0, V_CELL_PL, reservoir=False) for k in range(n)]
    m["extracellular"] = [_node("bath", 1.0, 1.0, reservoir=True)]
    m["membranes"] = [_membrane(f"m{k}", f"c{k}", "bath", G_EQ1_M3_S, 1.0) for k in range(n)]
    raw["experiment"]["membrane_controls"] = [
        dict(membrane_id=p["id"], schedule=[dict(time=0.0, availability=1.0)])
        for p in m["membranes"]
    ]
    x.update(capacity=n, extracellular_capacity=1, membrane_capacity=n)
    return raw


FIELD_NODE_BOUND = NODE_BOUNDS[FIELD_SOLVER]
