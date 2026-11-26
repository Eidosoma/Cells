"""FR-7 F4's mapper: R-loop's registered inputs to the engine's definitions of the closed loop.

R-loop (validation/fr7/references/, registered code-blind and tagged
fr7-references-rloop-2026-11-19) declares F4's world in interface/loop_inputs.json: the probe
world of D231, its template scaled by D233. This module reads that file only, never the
references' implementation, and declares the world for the engine.

**The model.** The composite cells.model.resolved_pump_composite@1 over cells.model.resolved_pump_tissue@3, holding:
* **the cell:** the heredity cell H at the registered volume per area, with the registered start
  (amounts, the fixed charge X, and the charge C V at the start's V), and one constant-field
  patch facing a bath held at 0 V;
* **the Na/K pump** (cells.cycle.nak_atp_mass_action_positive@1) on held fuel pools, with ΔG0 over the 1 M
  standard state, which the law fixes and the inputs declare;
* **the populations in cells.operator.membrane_entity_state@1:** kir_0, a gate-free K leak (cells.channel.kleak_always_open@1),
  and naleak_0, the Na-leak units (cells.channel.naleak_always_open@1, carrying the cell's whole Na leak), each
  at its registered reference density and units;
* **under cells.operator.scheduled_species_turnover@1,** the template and the precursor, two neutral inventory
  species: the template's production schedule and first-order clearance, and the precursor's
  supply S_P and clearance k_P;
* **cells.operator.species_regulated_availability@2,** with:
  - the regulatory state s_na (cells.regulation.hill_regulated_two_state@1, a Hill activation by cytosolic Na), at
    its registered start s;
  - two operator routes on the unit producer's assembly rate of the route naleak_units, in
    declared order: the template's Hill activation (K, n, b_T) at the operating range [0, 1] mM,
    then s_na's complement (b = 0). The rate is k_a F_T F_loop;
* **cells.operator.population_unit_turnover@1,** with nu, m = 0, k_a and k_r on all of N.

**The arms.**
* **closed:** the loop on throughout.
* **clamped:** the loop's coupling switched off at t_d, and the producer's k_a stepped there to
  k_a F*_engine, where F*_engine is the engine's own applied loop factor at the closed arm's row
  t_d. The caller passes it and checks it against the registered F* and its bound.

**The template's tail is the plain mean-field one.**
* The cell holds the registered dose alone: the inventory helper's concentrations_mM replaces the
  trace there.
* The trace stays in the bath, which the template, impermeant on every patch and junction, can
  neither enter nor leave.
* From there only D150's turnover moves the template: an exact first-order clearance in every
  half-step, with no floor, clamp or reset. An amount that would not stay positive refuses the
  step.
* FLOOR_FMOL is the species' material-ledger tolerance only.
* dosed=False, the engine's drift check, starts the template at TRACE_mM instead: the closed loop
  with no template, whose own steady state the registered start is.

The synthetic labels are the references' (D217). Development, not judged.
"""

import copy
import math
from pathlib import Path

from cells.definitions import pump_composite_spec as cs
from cells.laws.electrochemistry import F
from cells.laws.pumps import nak_atp_mass_action_positive as pump_law
from cells.registry.inventory_species import add_inventory_species
from validation import id_table
from validation.fr7 import unit_turnover_fixtures as fx

ROOT = Path(__file__).resolve().parents[2]
INTERFACE = ROOT / "validation" / "fr7" / "references" / "interface"
TEMPLATE, PRECURSOR = "template", fx.PRECURSOR
CELL, BATH, PATCH, PUMP = "cell_0", "bath_0", "membrane_0", "pump_0"
ROUTE, STATE_ID = "naleak_units", "s_na"
TRACE_mM = 1e-15
FLOOR_FMOL = 1e-20  # The species ledger's floor, as the coupling protocol declares it.
IMEX = "cells.solver.imex_ars222_face_electromigration@1"
FIELD_SOLVER = "cells.solver.capacitive_reduction_gauged_damped_newton@2"
CLOSURE = "cells.field_closure.resolved_capacitor_components_current_continuity@1"
CHARGE_PER_FMOL = F * 1e-15
LAWS = {
    "gate-free K leak (cells.channel.kleak_always_open@1), K only": "cells.channel.kleak_always_open@1",
    "gate-free Na leak (cells.channel.naleak_always_open@1), Na only": "cells.channel.naleak_always_open@1",
}


def inputs(path=None):
    """The registered loop inputs (interface/loop_inputs.json, or the given copy of it)."""
    return id_table.load(path or INTERFACE / "loop_inputs.json")


def _identity(name):
    return [dict(id=name, catalogue=None, evidence=None)]


def _schedule(changes, key):
    return [{"time": float(t), key: float(v)} for t, v in changes]


def _channel(entry, membrane, species, area):
    """An @3 population entry from a registered population (its law, permeability, the one ion
    it conducts, and its abundance a = N / (A rho_ref))."""
    law = LAWS[entry["law"]]
    ions = [s for s, r in zip(species, entry["relative_permeability"], strict=True) if r > 0]
    if len(ions) != 1:
        raise ValueError(f"{entry['id']}: a gate-free leak population conducts one ion")
    units = entry.get("units", entry.get("N0"))
    return dict(
        id=entry["id"],
        membrane_id=membrane,
        kinetic_law=law,
        max_permeability_m_per_s=entry["permeability_m_s"],
        abundance=units / (area * entry["reference_density_per_m2"]),
        initial_gate=[],
        permeant_ions=[dict(species_id=ions[0], relative_permeability=1.0)],
    )


def definition(inp, *, arm="closed", f_star=None, dosed=True, end=None, rows=None, dt=None):
    """The engine's definition of F4's `arm` ("closed" or "clamped", the latter with f_star, the
    engine's own applied loop factor at t_d), from the registered inputs `inp`."""
    loop = inp["loop"]
    cell, pump, units = loop["cell"], loop["pump"], loop["units"]
    start = loop["start"]
    species, valence = list(cell["species"]), list(cell["valence"])
    if pump["standard_state_mM"] != pump_law.STANDARD_STATE_mM:
        raise ValueError("The registered standard state is not the pump law's 1 M")
    if arm not in ("closed", "clamped") or (arm == "clamped") != (f_star is not None):
        raise ValueError("arm is closed, or clamped with the engine's own F*")
    dt = loop["dt_s"] if dt is None else dt
    end = loop["horizon_s"] if end is None else end
    rows = [t for t in (loop["rows_s"] if rows is None else rows) if t <= end]
    amounts = dict(zip(species, start["amounts_fmol"], strict=True))
    background = start["background_fmol"]
    charge = cell["capacitance_F"] * start["V"]
    total = CHARGE_PER_FMOL * math.fsum(
        (background, *(z * amounts[s] for s, z in zip(species, valence, strict=True)))
    )
    if abs(total - charge) > 1e-20:  # @3's own tolerance on the charge anchor.
        raise ValueError(f"The registered start's charge and C V differ by {total - charge}")
    bath = {s: c * 1.0 for s, c in zip(species, cell["bath_mM"], strict=True)}
    area = cell["patch_area_m2"]
    populations = [*cell["fixed_populations"], units]
    raw = dict(
        schema_version=1,
        model=dict(
            id="cells.model.resolved_pump_tissue@3",
            temperature_K=cell["temperature_K"],
            species=[dict(id=s, valence=z) for s, z in zip(species, valence, strict=True)],
            cells=[
                dict(
                    id=CELL,
                    volume_pL=cell["volume_pL"],
                    initial_amount_fmol=amounts,
                    fixed_charge_equivalent_fmol=background,
                    initial_charge_C=charge,
                )
            ],
            extracellular=[
                dict(
                    id=BATH,
                    volume_pL=1.0,
                    initial_amount_fmol=bath,
                    fixed_charge_equivalent_fmol=-math.fsum(
                        z * bath[s] for s, z in zip(species, valence, strict=True)
                    ),
                    initial_charge_C=0.0,
                    reservoir=True,
                    boundary_potential_V=0.0,
                )
            ],
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
                    law="cells.route.constant_field@1",
                    pump=dict(
                        id=PUMP,
                        law="cells.cycle.nak_atp_mass_action_positive@1",
                        roles=dict(sodium="Na", potassium="K"),
                        stoichiometry=dict(Na=-3, K=2),
                        capacity_fmol_per_s=pump["capacity_fmol_cycles_per_s"],
                        km_na_mM=pump["km_na_mM"],
                        km_k_mM=pump["km_k_mM"],
                        km_atp_mM=pump["km_atp_mM"],
                        metabolism=dict(
                            kind="cells.fuel_kind.maintained_chemical_reservoirs@1",
                            atp_mM=pump["atp_mM"],
                            adp_mM=pump["adp_mM"],
                            pi_mM=pump["pi_mM"],
                            delta_g0_J_per_mol=pump["deltaG0_J_per_mol"],
                        ),
                    ),
                    calcium_pump=None,
                )
            ],
            junctions=[],
            faces=[],
            closure=dict(law=CLOSURE, gauge_reference=None),
            channels=[_channel(p, PATCH, species, area) for p in populations],
        ),
        experiment=dict(
            end_time=end,
            observation_times=rows if rows[-1] == end else [*rows, end],
            membrane_controls=[
                dict(membrane_id=PATCH, schedule=_schedule([(0, 1)], "availability"))
            ],
            junction_controls=[],
            pump_controls=[
                dict(pump_id=PUMP, schedule=_schedule([(0, pump["availability"])], "availability"))
            ],
            calcium_pump_controls=[],
            channel_controls=[
                dict(channel_id=p["id"], schedule=_schedule([(0, 1)], "availability"))
                for p in populations
            ],
        ),
        execution=dict(
            dt=dt,
            capacity=1,
            extracellular_capacity=1,
            membrane_capacity=1,
            edge_capacity=0,
            face_capacity=1,
            channel_capacity=len(populations),
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
    template = loop["template"]
    volume = cell["volume_pL"]
    dose = template["n0_fmol"] / volume if dosed and template["n0_fmol"] > 0 else TRACE_mM
    for species_id, mM in ((PRECURSOR, start["n_P_fmol"] / volume), (TEMPLATE, dose)):
        raw = add_inventory_species(
            raw,
            species_id,
            trace_mM=TRACE_mM,
            diffusivity_m2_per_s=fx.DIFFUSIVITY,
            floor_fmol=FLOOR_FMOL,
            concentrations_mM={CELL: mM},
        )
    raw = cs.frozen_definition(raw)
    return _with_operators(raw, loop, arm, f_star)


def _with_operators(raw, loop, arm, f_star):
    out = copy.deepcopy(raw)
    cell, units, start = loop["cell"], loop["units"], loop["start"]
    precursor, regulator, template = loop["precursor"], loop["regulator"], loop["template"]
    factor = template["factor"]
    state = dict(
        law=fx.STATE,
        populations=[
            dict(
                channel_id=p["id"],
                functional_unit=p["id"].split("_")[0],
                catalogue=None,
                reference_density_per_m2=p["reference_density_per_m2"],
            )
            for p in [*cell["fixed_populations"], units]
        ],
    )
    turnover = dict(
        law=fx.TURNOVER,
        species=_identity(PRECURSOR) + _identity(TEMPLATE),
        routes=[
            dict(id="t_production", species=TEMPLATE, node=CELL, kind="production"),
            dict(id="t_clearance", species=TEMPLATE, node=CELL, kind="clearance"),
            dict(id="p_supply", species=PRECURSOR, node=CELL, kind="production"),
            dict(id="p_clearance", species=PRECURSOR, node=CELL, kind="clearance"),
        ],
        templates=[],
    )
    target = dict(
        operator=fx.LAW, control="unit_assembly_rate", ids=[ROUTE], evaluation="target_half_steps"
    )
    route = regulator["route"]
    coupling = dict(
        law="cells.operator.species_regulated_availability@2",
        species=_identity(TEMPLATE) + _identity("Na"),
        states=[
            dict(
                id=STATE_ID,
                law=regulator["law"],
                cells=[CELL],
                inputs=[
                    dict(
                        law="hill_activation",
                        species="Na",
                        half_saturation_mM=regulator["K_mM"],
                        hill_coefficient=regulator["n"],
                    )
                ],
                on_rate_per_s=regulator["k_on_per_s"],
                off_rate_per_s=regulator["k_off_per_s"],
                initial=start["s"],
                crossing_level=None,
            )
        ],
        couplings=[
            dict(
                id="c_template",
                target=dict(target, operating_range=list(template["operating_range_mM"])),
                source={"species": TEMPLATE},
                law=factor["law"],
                half_saturation_mM=factor["K_mM"],
                hill_coefficient=factor["n"],
                basal=factor["basal"],
            ),
            dict(
                id="c_loop",
                target=dict(target, operating_range=[0.0, 1.0]),
                source={"state": STATE_ID},
                law=route["law"],
                basal=route["basal"],
            ),
        ],
    )
    producer = dict(
        law=fx.LAW,
        species=_identity(PRECURSOR),
        routes=[
            fx.route(
                ROUTE,
                units["id"],
                nu=units["nu"],
                pools=units["stages"],
                tau=None,
                initial=start["M_units"],
            )
        ],
    )
    out["model"]["operators"] = [state, turnover, coupling, producer]
    e = out["experiment"]
    t_d = loop["arms"]["t_d_s"]
    clamped = arm == "clamped"
    e["coupling_controls"] = [
        dict(coupling_id="c_template", schedule=[dict(time=0.0, enabled=1)]),
        dict(
            coupling_id="c_loop",
            schedule=[dict(time=0.0, enabled=1)] + ([dict(time=t_d, enabled=0)] if clamped else []),
        ),
    ]
    e["regulatory_writes"] = []
    k_a, k_r = units["assembly_per_s"], units["removal_per_s"]
    schedule = [dict(time=0.0, assembly_rate_per_s=k_a, removal_rate_per_s=k_r)]
    if clamped:
        schedule.append(dict(time=t_d, assembly_rate_per_s=k_a * f_star, removal_rate_per_s=k_r))
    e["unit_turnover_controls"] = [dict(route_id=ROUTE, schedule=schedule)]
    e["turnover_controls"] = [
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
        dict(
            route_id="p_supply",
            carrier_id=CELL,
            schedule=_schedule([(0.0, start["supply_fmol_per_s"])], "rate"),
        ),
        dict(
            route_id="p_clearance",
            carrier_id=CELL,
            schedule=_schedule([(0.0, precursor["clearance_per_s"])], "rate"),
        ),
    ]
    return out
