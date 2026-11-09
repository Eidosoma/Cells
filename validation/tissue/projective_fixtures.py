"""Worlds and projective blocks for the coarse projective mode (core/projective.py).

pump_cells(): independent resolved_pump_tissue@1 cells, each facing its own held
bath, with the heredity pre-screen's passive and pump parameters
(validation/tissue/surface_pump_v3_fixtures.py: BETSE v1.5.0 default-world
coefficients from the saved plain-BETSE extraction, Na leak x0.2, 310 K, fixed
volume) and no channel populations, which @1 does not have. Without Kir2.1
the H composition is not a steady state of @1: the cells relax over seconds
(membrane voltage) and hundreds of seconds (composition), the separation the
projective mode needs. Parameters are synthetic, not measurements.

projective_block(): an execution.projective block with every field explicit.
"""

import copy
import math

from cells.processes.electrochemistry import CHARGE_PER_FMOL

TEMPERATURE_K = 310.0
VOLUME_PL = 0.7505222518670602
AREA_M2 = 3.261272165616906e-10
CAPACITANCE_F = 0.05 * AREA_M2
PERMEABILITY = dict(
    Na=0.2 * 2.666666666666668e-10, K=1.333333333333334e-10, M=1.333333333333334e-10, P=0.0
)
BATH_mM = dict(Na=145.0, K=5.0, M=140.0, P=10.0)
FIXED_ANION_mM = 135.0
SPECIES = (("Na", 1), ("K", 1), ("M", -1), ("P", -1))
ARS = "imex_ars222_face_electromigration@1"
# (Vm V, Na, K, M mM): the heredity H composition and a depolarized, Na-loaded cell.
H = (-0.07955626004246525, 5.934560723484736, 136.17199964403224, 7.124496086230464)
LOADED = (-0.05, 12.0, 130.0, 10.0)


def pump_cells(cells, *, dt=1e-3, end_time=1.0, observation_times=None, solver=ARS,
               backend="cpu", pump_controls=None):  # fmt: skip
    """Independent @1 cells: [(Vm, Na, K, M), ...] in V and mM, one held bath each.

    pump_controls: optional {cell index: [(time, availability), ...]} schedules,
    for scheduled cues; every other pump is fully available.
    """
    ids = [s for s, _ in SPECIES]
    z = dict(SPECIES)
    model_cells, outside, membranes = [], [], []
    for i, (vm, na, k, mm) in enumerate(cells):
        amounts = dict(Na=na, K=k, M=mm, P=FIXED_ANION_mM)
        amounts = {s: amounts[s] * VOLUME_PL for s in ids}
        charge = CAPACITANCE_F * vm
        model_cells.append(
            dict(
                id=f"cell_{i}",
                volume_pL=VOLUME_PL,
                initial_amount_fmol=amounts,
                fixed_charge_equivalent_fmol=charge / CHARGE_PER_FMOL
                - math.fsum(z[s] * amounts[s] for s in ids),
                initial_charge_C=charge,
            )
        )
        outside.append(
            dict(
                id=f"bath_{i}",
                volume_pL=1.0,
                initial_amount_fmol=dict(BATH_mM),
                fixed_charge_equivalent_fmol=-math.fsum(z[s] * BATH_mM[s] for s in ids),
                initial_charge_C=0.0,
                reservoir=True,
                boundary_potential_V=0.0,
            )
        )
        membranes.append(
            dict(
                id=f"membrane_{i}",
                inside=f"cell_{i}",
                outside=f"bath_{i}",
                area_m2=AREA_M2,
                capacitance_F=CAPACITANCE_F,
                permeability_m_per_s=dict(PERMEABILITY),
                law="constant_field@1",
                pump=dict(
                    id=f"pump_{i}",
                    law="nak_atp_mass_action_positive@1",
                    roles=dict(sodium="Na", potassium="K"),
                    stoichiometry=dict(Na=-3, K=2),
                    capacity_fmol_per_s=1e-7 * AREA_M2 * 1e15,
                    km_na_mM=12.0,
                    km_k_mM=0.2,
                    km_atp_mM=0.5,
                    metabolism=dict(
                        kind="maintained_chemical_reservoirs@1",
                        atp_mM=1.5,
                        adp_mM=0.1,
                        pi_mM=0.1,
                        delta_g0_J_per_mol=-37000.0,
                    ),
                ),
            )
        )
    always = [dict(time=0.0, availability=1.0)]
    pumps = []
    for i, p in enumerate(membranes):
        schedule = (pump_controls or {}).get(i)
        rows = (
            copy.deepcopy(always)
            if schedule is None
            else [dict(time=t, availability=a) for t, a in schedule]
        )
        pumps.append(dict(pump_id=p["pump"]["id"], schedule=rows))
    times = [0.0, end_time] if observation_times is None else list(observation_times)
    return dict(
        schema_version=1,
        model=dict(
            id="resolved_pump_tissue@1",
            temperature_K=TEMPERATURE_K,
            species=[dict(id=s, valence=v) for s, v in SPECIES],
            cells=model_cells,
            extracellular=outside,
            membranes=membranes,
            junctions=[],
            faces=[],
            closure=dict(
                law="resolved_capacitor_components_current_continuity@1", gauge_reference=None
            ),
        ),
        experiment=dict(
            end_time=end_time,
            observation_times=times,
            membrane_controls=[
                dict(membrane_id=p["id"], schedule=copy.deepcopy(always)) for p in membranes
            ],
            junction_controls=[],
            pump_controls=pumps,
        ),
        execution=dict(
            dt=dt,
            capacity=len(cells),
            extracellular_capacity=len(cells),
            membrane_capacity=len(cells),
            edge_capacity=0,
            face_capacity=0,
            backend=backend,
            jit=True,
            precision="float64",
            solver=solver,
            field_solver="capacitive_reduction_gauged_damped_newton@2",
            max_steps=int(math.ceil(end_time / dt)) + 8,
            max_trace_bytes=2**33,
            material_balance_atol_fmol={s: 1e-10 for s in ids},
        ),
    )


def closed_tissue(*, dt=1e-3, end_time=1.0, observation_times=None, backend="cpu"):
    """The closed arm of validation/tissue/surface_pump_fixtures.py at a 1 ms IMEX step.

    Two cells joined by a gated junction, five finite outside nodes joined by
    faces and gauged at one node, Na/K pumps; no held bath, so no reservoir
    ledger accumulates. Synthetic parameters.
    """
    from validation.tissue import surface_pump_fixtures

    raw = surface_pump_fixtures.definition("closed", solver=ARS, padded=False, backend=backend)
    e, x = raw["experiment"], raw["execution"]
    e["end_time"] = end_time
    e["observation_times"] = [0.0, end_time] if observation_times is None else observation_times
    x.update(dt=dt, max_steps=int(math.ceil(end_time / dt)) + 8, max_trace_bytes=2**33)
    return raw


def grid_times(dt, until, every):
    """Observation times every `every` s as the accepted products i * dt (EventGrid)."""
    stride, steps = round(every / dt), round(until / dt)
    return [i * dt for i in range(0, steps, stride)] + [until]


def projective_block(windows, *, burst_steps=2000, slope_steps=250, rule="error_controlled",
                     max_steps=60000, min_steps=1000, max_growth=2.0, safety_factor=0.5,
                     tolerance=None, safety=None, row_checks="host"):  # fmt: skip
    """An execution.projective block; windows is [(start, end), ...] in s."""
    if rule == "fixed":
        jump = dict(rule="fixed", steps=max_steps, min_steps=min_steps)
    else:
        jump = dict(
            rule="error_controlled",
            max_steps=max_steps,
            min_steps=min_steps,
            max_growth=max_growth,
            safety_factor=safety_factor,
        )
    return dict(
        method="projective_forward_euler@1",
        windows=[dict(start_time=a, end_time=b) for a, b in windows],
        burst_steps=burst_steps,
        slope_steps=slope_steps,
        jump=jump,
        tolerance=dict(concentration_mM=1e-4, membrane_voltage_V=1e-5, gate=1e-4)
        | (tolerance or {}),
        safety=dict(
            max_membrane_voltage_rate_V_per_s=1e-3,
            max_gate_distance=1e-3,
            max_correction=1.0,
            energy_defect_rtol=2e-3,
            energy_defect_atol_pJ=1e-9,
            rejection_shrink=0.25,
            cooldown_bursts=2,
        )
        | (safety or {}),
        row_checks=row_checks,
    )
