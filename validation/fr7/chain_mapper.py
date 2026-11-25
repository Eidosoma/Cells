"""FR-7 F3's mapper: R-chain's registered world inputs to the engine's definitions.

The references (validation/fr7/references/, registered code-blind on 19 November 2026 and tagged
fr7-references-registered-2026-11-19) declare six synthetic worlds in
interface/inputs.json. This module reads that file only, never the references' implementation,
and declares each world for the engine:
* the composite resolved_pump_composite@1 over resolved_pump_tissue@3;
* R-cell's pump-free cell: one cell with one constant-field patch facing a bath held at 0 V;
* the gate-free, K-only population (kleak_always_open@1), declared in membrane_entity_state@1 at
  the registered reference density, at abundance N0 / (A rho_ref);
* the template T and the precursor P, two neutral inventory species (D150's identity form) under
  scheduled_species_turnover@1: T's production schedule and clearance, and P's supply and
  clearance where declared;
* species_regulated_availability@2: the template's Hill activation (K, n, b) routed onto the unit
  producer's assembly rate (B1', target_half_steps), at the registered operating range;
* population_unit_turnover@1: one route on the population, with the registered nu, stages m
  (maturation_time_s = m / kappa), initial units in each stage (M0), k_a and k_r on all of N.

The start is the registered one: the cell's amounts, its background charge, and the charge
C V0 at the declared initial V.

The template's tail is the plain mean-field one.
* The cell holds the declared dose alone: the inventory helper's concentrations_mM replaces its
  trace there. The trace stays in the bath, which the template, impermeant on every patch and
  junction, can neither enter nor leave.
* A world with no initial template (the pulses before their onset, and W6) starts the cell at
  TRACE_mM, since @3 refuses a zero amount; the template's factor cannot see it (F_T = b to 1e-20).
* From there the template follows D150's turnover alone: its declared production and an exact
  first-order clearance in every half-step, with no floor, clamp or reset. An amount that would not
  stay positive refuses the step.
* FLOOR_FMOL is the species' material-ledger tolerance (material_balance_atol_fmol) only, never a
  bound on the state.

The engine's layout choices, none of them physics:
* the bath is a 1 pL reservoir, as the coupling protocol's cells declare it;
* the population and patch IDs are this module's own;
* the template's and precursor's diffusivity and floor are D150's form only, since the cell has no
  face.

The synthetic labels are the references' (D217). Development, not judged.
"""

import copy
import math
from pathlib import Path

from cells.definitions import pump_composite_spec as cs
from cells.laws.electrochemistry import F
from cells.registry.inventory_species import add_inventory_species
from validation import id_table
from validation.fr7 import unit_turnover_fixtures as fx

ROOT = Path(__file__).resolve().parents[2]
INTERFACE = ROOT / "validation" / "fr7" / "references" / "interface"
TEMPLATE, PRECURSOR = "template", fx.PRECURSOR
CELL, BATH, PATCH, POPULATION, ROUTE = "cell_0", "bath_0", "patch_0", "kleak_0", "units"
COUPLING = "c_template"
TRACE_mM = 1e-15
FLOOR_FMOL = 1e-20  # The species ledger's floor, as the coupling protocol declares it.
DIFFUSIVITY = fx.DIFFUSIVITY  # Inert: the cell has no face.
IMEX = "imex_ars222_face_electromigration@1"
FIELD_SOLVER = "capacitive_reduction_gauged_damped_newton@2"
CLOSURE = "resolved_capacitor_components_current_continuity@1"
CHARGE_PER_FMOL = F * 1e-15


def inputs(path=None):
    """The registered inputs (interface/inputs.json, or the given copy of it)."""
    return id_table.load(path or INTERFACE / "inputs.json")


def _identity(name):
    return [dict(id=name, catalogue=None, evidence=None)]


def _node(name, volume, amounts, background, charge, *, outside=False):
    node = dict(
        id=name,
        volume_pL=volume,
        initial_amount_fmol=dict(amounts),
        fixed_charge_equivalent_fmol=background,
        initial_charge_C=charge,
    )
    return node | (dict(reservoir=True, boundary_potential_V=0.0) if outside else {})


def _schedule(changes, key):
    return [{"time": float(t), key: float(v)} for t, v in changes]


def definition(inp, name, *, dt=None, end=None, rows=None):
    """The engine's definition of world `name` of the registered inputs `inp`, run with the
    declared step (or dt) to its horizon (or end), observed at its rows (or `rows`)."""
    w = inp["worlds"][name]
    cell, pop = inp["cell"], inp["cell"]["population"]
    species, valence = list(cell["species"]), list(cell["valence"])
    dt = inp["step"]["dt_s"] if dt is None else dt
    end = w["horizon_s"] if end is None else end
    rows = [t for t in (w["rows_s"] if rows is None else rows) if t <= end]
    start = w["cell_start"]
    amounts = dict(zip(species, start["initial_amounts_fmol"], strict=True))
    background = start["background_fmol"]
    charge = cell["capacitance_F"] * start["initial_V"]
    total = CHARGE_PER_FMOL * math.fsum(
        (background, *(z * amounts[s] for s, z in zip(species, valence, strict=True)))
    )
    if abs(total - charge) > 1e-20:  # @3's own tolerance on the charge anchor.
        raise ValueError(
            f"{name}: the registered start's charge and C V0 differ by {total - charge}"
        )
    bath_amounts = {s: c * 1.0 for s, c in zip(species, cell["bath_mM"], strict=True)}
    bath_background = -math.fsum(z * bath_amounts[s] for s, z in zip(species, valence, strict=True))
    area = cell["patch_area_m2"]
    units = w["units"]
    if list(pop["relative_permeability"]) != [0.0, 1.0, 0.0]:
        raise ValueError("The engine's gate-free population here is kleak_always_open@1 (K only)")
    raw = dict(
        schema_version=1,
        model=dict(
            id="resolved_pump_tissue@3",
            temperature_K=inp["constants"]["temperature_K"],
            species=[dict(id=s, valence=z) for s, z in zip(species, valence, strict=True)],
            cells=[_node(CELL, cell["volume_pL"], amounts, background, charge)],
            extracellular=[_node(BATH, 1.0, bath_amounts, bath_background, 0.0, outside=True)],
            membranes=[
                dict(
                    id=PATCH,
                    inside=CELL,
                    outside=BATH,
                    area_m2=area,
                    capacitance_F=cell["capacitance_F"],
                    permeability_m_per_s=dict(
                        zip(species, cell["leak_permeability_m_s"], strict=True)
                    ),
                    law="constant_field@1",
                    pump=None,
                    calcium_pump=None,
                )
            ],
            junctions=[],
            faces=[],
            closure=dict(law=CLOSURE, gauge_reference=None),
            channels=[
                dict(
                    id=POPULATION,
                    membrane_id=PATCH,
                    kinetic_law="kleak_always_open@1",
                    max_permeability_m_per_s=pop["permeability_m_s"],
                    abundance=units["N0"] / (area * pop["reference_density_per_m2"]),
                    initial_gate=[],
                    permeant_ions=[dict(species_id="K", relative_permeability=1.0)],
                )
            ],
        ),
        experiment=dict(
            end_time=end,
            observation_times=rows if rows[-1] == end else [*rows, end],
            membrane_controls=[
                dict(membrane_id=PATCH, schedule=_schedule([(0, 1)], "availability"))
            ],
            junction_controls=[],
            pump_controls=[],
            calcium_pump_controls=[],
            channel_controls=[
                dict(channel_id=POPULATION, schedule=_schedule([(0, 1)], "availability"))
            ],
        ),
        execution=dict(
            dt=dt,
            capacity=1,
            extracellular_capacity=1,
            membrane_capacity=1,
            edge_capacity=0,
            face_capacity=1,
            channel_capacity=1,
            backend="cpu",
            jit=True,
            precision="float64",
            solver=IMEX,
            field_solver=FIELD_SOLVER,
            max_steps=int(math.ceil(end / dt)) + 8,
            max_trace_bytes=2**31,
            material_balance_atol_fmol={s: 1e-10 for s in species},
        ),
    )
    template, precursor = w["template"], w["precursor"]
    volume = cell["volume_pL"]
    for species_id, n0 in ((TEMPLATE, template["n0_fmol"]), (PRECURSOR, precursor["n0_fmol"])):
        raw = add_inventory_species(
            raw,
            species_id,
            trace_mM=TRACE_mM,
            diffusivity_m2_per_s=DIFFUSIVITY,
            floor_fmol=FLOOR_FMOL,
            concentrations_mM={CELL: n0 / volume if n0 > 0 else TRACE_mM},
        )
    raw = cs.frozen_definition(raw)
    return _with_operators(raw, inp, w)


def _with_operators(raw, inp, w):
    out = copy.deepcopy(raw)
    pop, units = inp["cell"]["population"], w["units"]
    template, precursor, factor = w["template"], w["precursor"], w["factor"]
    state = dict(
        law=fx.STATE,
        populations=[
            dict(
                channel_id=POPULATION,
                functional_unit=POPULATION.split("_")[0],
                catalogue=None,
                reference_density_per_m2=pop["reference_density_per_m2"],
            )
        ],
    )
    routes = [
        dict(id="t_production", species=TEMPLATE, node=CELL, kind="production"),
        dict(id="t_clearance", species=TEMPLATE, node=CELL, kind="clearance"),
    ]
    controls = [
        dict(
            route_id="t_production",
            carrier_id=CELL,
            schedule=_schedule(template["production"], "rate"),
        ),
        dict(
            route_id="t_clearance",
            carrier_id=CELL,
            schedule=_schedule([(0.0, template["clearance_per_s"])], "rate"),
        ),
    ]
    if precursor["supply_fmol_per_s"] or precursor["clearance_per_s"]:
        routes += [
            dict(id="p_supply", species=PRECURSOR, node=CELL, kind="production"),
            dict(id="p_clearance", species=PRECURSOR, node=CELL, kind="clearance"),
        ]
        controls += [
            dict(
                route_id="p_supply",
                carrier_id=CELL,
                schedule=_schedule([(0.0, precursor["supply_fmol_per_s"])], "rate"),
            ),
            dict(
                route_id="p_clearance",
                carrier_id=CELL,
                schedule=_schedule([(0.0, precursor["clearance_per_s"])], "rate"),
            ),
        ]
    turnover = dict(
        law=fx.TURNOVER,
        species=_identity(PRECURSOR) + _identity(TEMPLATE),
        routes=routes,
        templates=[],
    )
    coupling = dict(
        law="species_regulated_availability@2",
        species=_identity(TEMPLATE),
        states=[],
        couplings=[
            dict(
                id=COUPLING,
                target=dict(
                    operator=fx.LAW,
                    control="unit_assembly_rate",
                    ids=[ROUTE],
                    evaluation="target_half_steps",
                    operating_range=list(inp["clearance"]["operating_range_mM"]),
                ),
                source={"species": TEMPLATE},
                law=factor["law"],
                half_saturation_mM=factor["K_mM"],
                hill_coefficient=factor["n"],
                basal=factor["basal"],
            )
        ],
    )
    m = units["stages"]
    producer = dict(
        law=fx.LAW,
        species=_identity(PRECURSOR),
        routes=[
            fx.route(
                ROUTE,
                POPULATION,
                nu=units["nu"],
                pools=m,
                tau=m / units["maturation_per_s"] if m else None,
                initial=units["M0"],
            )
        ],
    )
    out["model"]["operators"] = [state, turnover, coupling, producer]
    e = out["experiment"]
    e["turnover_controls"] = controls
    e["coupling_controls"] = [dict(coupling_id=COUPLING, schedule=[dict(time=0.0, enabled=1)])]
    e["regulatory_writes"] = []
    e["unit_turnover_controls"] = [
        dict(
            route_id=ROUTE,
            schedule=[
                dict(
                    time=0.0,
                    assembly_rate_per_s=units["assembly_per_s"],
                    removal_rate_per_s=units["removal_per_s"],
                )
            ],
        )
    ]
    return out
