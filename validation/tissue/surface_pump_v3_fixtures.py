"""Synthetic resolved pump worlds with channel populations for resolved_pump_tissue@3.

definition(): the resolved_pump_tissue@2 fixture (validation/tissue/
surface_pump_v2_fixtures.py) declared as @3, with eight populations covering
the five laws: one Kv1.5, Kir2.1, NaV1.2 or leak population per patch plus
Kir2.1 and NaV1.2 on patch 0, so populations share patches and the leaks are
mixed with gated laws. Parameters are synthetic, not measurements. With
channels=False the world has no populations: the @2 equivalence world.

reference(): the same world as resolved_tissue@8 (RK4, dense field), whose
shared catalog holds the same Kv1.5, Kir2.1, NaV1.2 and leak equations under
their earlier law IDs; the IDs are read from the catalog modules so the
reference follows their renaming.

heredity_cells(): independent single cells, each facing its own held bath, with
the heredity pre-screen's parameters (heredity-design-20261108-01, design.json
and prescreen_slow_states_v6.py): BETSE v1.5.0 default-world coefficients from
the saved plain-BETSE extraction, Na leak x0.2, Kir2.1 1e-8 m/s and NaV1.2
2.5e-7 m/s, 310 K, fixed volume. The pre-screen's slow steady states are
HEREDITY_STATES.
"""

import copy
import math

import numpy as np

from cells.core import surface_kinetic_spec
from cells.core.surface_pump_v3_spec import (
    KIR2P1_LAW_ID,
    KLEAK_LAW_ID,
    KV1P5_LAW_ID,
    NALEAK_LAW_ID,
    NAV1P2_LAW_ID,
)
from cells.processes import (
    junction_gate,
    potassium_catalog,
    potassium_channels,
    sodium_catalog,
    sodium_channels,
    voltage_gates,
)
from cells.processes.electrochemistry import CHARGE_PER_FMOL
from validation.tissue import surface_pump_v2_fixtures as second

ARMS = second.first.ARMS
# (id, patch, law, ion, permeability m/s, abundance, initial gate)
CHANNELS = (
    ("channel_0", 0, KV1P5_LAW_ID, "K", 3e-10, 0.5, [0.2, 0.7]),
    ("channel_1", 1, KIR2P1_LAW_ID, "K", 3e-10, 0.6, [0.25, 0.7]),
    ("channel_2", 2, NAV1P2_LAW_ID, "Na", 2e-10, 0.3, [0.15, 0.8]),
    ("channel_3", 3, KV1P5_LAW_ID, "K", 3e-10, 0.8, [0.35, 0.7]),
    ("channel_4", 0, KIR2P1_LAW_ID, "K", 3e-10, 0.5, [0.65, 0.35]),
    ("channel_5", 0, NAV1P2_LAW_ID, "Na", 2e-10, 0.4, [0.35, 0.6]),
    ("channel_6", 1, KLEAK_LAW_ID, "K", 1e-10, 1.0, []),
    ("channel_7", 3, NALEAK_LAW_ID, "Na", 5e-11, 1.0, []),
)


def channel(cid, patch, law, ion, permeability, abundance, gate):
    return dict(
        id=cid,
        membrane_id=f"membrane_{patch}",
        kinetic_law=law,
        max_permeability_m_per_s=permeability,
        abundance=abundance,
        initial_gate=list(gate),
        permeant_ions=[dict(species_id=ion, relative_permeability=1.0)],
    )


def definition(
    arm="open",
    *,
    backend="cpu",
    padded=True,
    solver="rk4",
    temperature_K=298.15,
    calcium=True,
    channels=True,
):
    raw = second.definition(
        arm,
        backend=backend,
        padded=padded,
        solver=solver,
        temperature_K=temperature_K,
        calcium=calcium,
    )
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    m["id"] = "resolved_pump_tissue@3"
    rows = CHANNELS if channels else ()
    m["channels"] = [channel(*row) for row in rows]
    schedule = (
        [dict(time=0.0, availability=0.0), dict(time=0.00073, availability=0.8)]
        if arm == "release"
        else [dict(time=0.0, availability=0.8)]
    )
    e["channel_controls"] = [
        dict(channel_id=row[0], schedule=copy.deepcopy(schedule)) for row in rows
    ]
    x["channel_capacity"] = len(rows) + int(padded and channels)
    return raw


def reference(arm="open", *, backend="cpu", padded=True):
    """The calcium-free definition() world as resolved_tissue@8 (RK4, dense field)."""
    return catalog_reference(definition(arm, backend=backend, padded=padded, calcium=False))


def catalog_reference(raw):
    """A calcium-free @3 definition at 298.15 K as resolved_tissue@8 (RK4, dense field)."""
    raw = copy.deepcopy(raw)
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    m["id"] = surface_kinetic_spec.CATALOG_MODEL_ID
    old = {
        KV1P5_LAW_ID: voltage_gates.LAW_ID,
        KIR2P1_LAW_ID: potassium_channels.KIR_LAW_ID,
        NAV1P2_LAW_ID: sodium_channels.LAW_ID,
        KLEAK_LAW_ID: next(k for k, v in potassium_catalog.POTASSIUM_LAWS.items() if v == "KLeak"),
        NALEAK_LAW_ID: next(k for k, v in sodium_catalog.SODIUM_LAWS.items() if v == "NaLeak"),
    }
    for c in m["channels"]:
        # The catalog keeps two (unused) relaxation gates for its leak laws.
        c["kinetic_law"], c["initial_gate"] = old[c["kinetic_law"]], c["initial_gate"] or [1, 1]
    for p in m["membranes"]:
        if p.pop("calcium_pump") is not None:
            raise ValueError("resolved_tissue@8 has no calcium pump")
    for p in m["junctions"]:
        p["gate"]["law"] = junction_gate.LAW_ID
    del e["calcium_pump_controls"]
    x.update(solver="rk4", field_solver="capacitive_reduction_gauged_damped_newton@1")
    return raw


# Pre-screen inputs (prescreen_single_cell_v3.load_world on the saved extraction).
HEREDITY_TEMPERATURE_K = 310.0
HEREDITY_VOLUME_PL = 0.7505222518670602
HEREDITY_AREA_M2 = 3.261272165616906e-10
HEREDITY_CAPACITANCE_F = 0.05 * HEREDITY_AREA_M2
# BETSE default Dm/tm (2e-18, 1e-18, 1e-18 m^2/s over 7.5 nm) with the Na leak x0.2.
HEREDITY_PERMEABILITY = dict(
    Na=0.2 * 2.666666666666668e-10, K=1.333333333333334e-10, M=1.333333333333334e-10, P=0.0
)
HEREDITY_BATH_mM = dict(Na=145.0, K=5.0, M=140.0, P=10.0)
HEREDITY_FIXED_ANION_mM = 135.0
HEREDITY_KIR_M_S = 1e-8
HEREDITY_NAV_M_S = 2.5e-7
HEREDITY_SPECIES = (("Na", 1), ("K", 1), ("M", -1), ("P", -1))
# prescreen-06.json (bath K 5 mM, Na leak x0.2, Kir 1e-8, NaV 2.5e-7): slow steady
# states (Vm, Na, K, M) with their fastest relaxation time (s).
HEREDITY_STATES = dict(
    H=(-0.07955626004246525, 5.934560723484736, 136.17199964403224, 7.124496086230464, 0.2577),
    U=(-0.039445199111173515, 9.54993007165825, 157.41934251996847, 31.978174491271798, None),
    D=(-0.02151770525721294, 10.128960373786892, 187.42791036044505, 62.56150561208027, 0.0889),
)


def steady_gates(voltage):
    """Kir2.1 and NaV1.2 (m, h) gates at their steady state for a membrane voltage (V)."""
    codes = np.array([1, 2])
    target, _ = sodium_channels.kinetics(np.full(2, voltage), codes, xp=np)
    return [float(v) for v in target[:, 0]], [float(v) for v in target[:, 1]]


def heredity_cells(cells, *, dt=1e-3, end_time=1.0, solver="imex_ars222_face_electromigration@1",
                   observation_times=None, backend="cpu", nav_m_s=HEREDITY_NAV_M_S,
                   kir_m_s=HEREDITY_KIR_M_S, gate_voltages=None,
                   temperature_K=HEREDITY_TEMPERATURE_K):  # fmt: skip
    """Independent heredity cells: [(Vm, Na, K, M) initial state, ...] in V and mM.

    Each cell's charge is its capacitor charge C*Vm. The fixed background absorbs
    the pre-screen's root-finding residual (at most 2e-4 mM-equivalent), so a
    declared steady state is the law's steady state. gate_voltages (default the
    initial voltages) sets the steady-state gates.
    """
    ids = [s for s, _ in HEREDITY_SPECIES]
    z = dict(HEREDITY_SPECIES)
    voltages = [c[0] for c in cells] if gate_voltages is None else list(gate_voltages)
    model_cells, outside, membranes, channels = [], [], [], []
    for i, (vm, na, k, mm) in enumerate(cells):
        amounts = dict(Na=na, K=k, M=mm, P=HEREDITY_FIXED_ANION_mM)
        amounts = {s: amounts[s] * HEREDITY_VOLUME_PL for s in ids}
        charge = HEREDITY_CAPACITANCE_F * vm
        model_cells.append(
            dict(
                id=f"cell_{i}",
                volume_pL=HEREDITY_VOLUME_PL,
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
                initial_amount_fmol=dict(HEREDITY_BATH_mM),
                fixed_charge_equivalent_fmol=-math.fsum(z[s] * HEREDITY_BATH_mM[s] for s in ids),
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
                area_m2=HEREDITY_AREA_M2,
                capacitance_F=HEREDITY_CAPACITANCE_F,
                permeability_m_per_s=dict(HEREDITY_PERMEABILITY),
                law="constant_field@1",
                pump=dict(
                    id=f"pump_{i}",
                    law="nak_atp_mass_action_positive@1",
                    roles=dict(sodium="Na", potassium="K"),
                    stoichiometry=dict(Na=-3, K=2),
                    capacity_fmol_per_s=1e-7 * HEREDITY_AREA_M2 * 1e15,
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
                calcium_pump=None,
            )
        )
        kir_gate, nav_gate = steady_gates(voltages[i])
        for name, law, ion, permeability, gate in (
            ("kir", KIR2P1_LAW_ID, "K", kir_m_s, kir_gate),
            ("nav", NAV1P2_LAW_ID, "Na", nav_m_s, nav_gate),
        ):
            channels.append(
                dict(
                    id=f"{name}_{i}",
                    membrane_id=f"membrane_{i}",
                    kinetic_law=law,
                    max_permeability_m_per_s=permeability,
                    abundance=1.0,
                    initial_gate=gate,
                    permeant_ions=[dict(species_id=ion, relative_permeability=1.0)],
                )
            )
    always = [dict(time=0.0, availability=1.0)]
    times = [0.0, end_time] if observation_times is None else list(observation_times)
    return dict(
        schema_version=1,
        model=dict(
            id="resolved_pump_tissue@3",
            temperature_K=temperature_K,
            species=[dict(id=s, valence=v) for s, v in HEREDITY_SPECIES],
            cells=model_cells,
            extracellular=outside,
            membranes=membranes,
            junctions=[],
            faces=[],
            closure=dict(
                law="resolved_capacitor_components_current_continuity@1", gauge_reference=None
            ),
            channels=channels,
        ),
        experiment=dict(
            end_time=end_time,
            observation_times=times,
            membrane_controls=[
                dict(membrane_id=p["id"], schedule=copy.deepcopy(always)) for p in membranes
            ],
            junction_controls=[],
            pump_controls=[
                dict(pump_id=p["pump"]["id"], schedule=copy.deepcopy(always)) for p in membranes
            ],
            calcium_pump_controls=[],
            channel_controls=[
                dict(channel_id=c["id"], schedule=copy.deepcopy(always)) for c in channels
            ],
        ),
        execution=dict(
            dt=dt,
            capacity=len(cells),
            extracellular_capacity=len(cells),
            membrane_capacity=len(cells),
            edge_capacity=0,
            face_capacity=0,
            channel_capacity=len(channels),
            backend=backend,
            jit=True,
            precision="float64",
            solver=solver,
            field_solver="capacitive_reduction_gauged_damped_newton@2",
            max_steps=int(math.ceil(end_time / dt)) + 8,
            max_trace_bytes=2**31,
            material_balance_atol_fmol={s: 1e-10 for s in ids},
        ),
    )


def kicked(state, millivolts):
    """A pre-screen state with Na added (or removed) to move Vm by the given mV."""
    vm, na, k, mm, _ = state
    delta = HEREDITY_CAPACITANCE_F * 1e-3 * millivolts
    return (vm + 1e-3 * millivolts, na + delta / CHARGE_PER_FMOL / HEREDITY_VOLUME_PL, k, mm)


# Off-steady gates for single_patch(): (law, ion, permeability m/s, gate).
PATCH_CHANNELS = (
    ("kv", KV1P5_LAW_ID, "K", 3e-9, [0.2, 0.7]),
    ("kir", KIR2P1_LAW_ID, "K", 1e-8, [0.6, 0.4]),
    ("nav", NAV1P2_LAW_ID, "Na", 2.5e-7, [0.3, 0.6]),
    ("kleak", KLEAK_LAW_ID, "K", 2e-10, []),
    ("naleak", NALEAK_LAW_ID, "Na", 1e-10, []),
)


def single_patch(*, dt=2.5e-6, end_time=0.001, solver="rk4", temperature_K=298.15, voltage=-0.06):
    """One heredity-sized cell and patch carrying all five laws, gates off steady state.

    The patch faces a held bath, so its currents are the only dynamics: NaV1.2
    opens and inactivates, Kv1.5/Kir2.1 relax, the leaks carry fixed fractions.
    """
    _, na, k, mm, _ = HEREDITY_STATES["H"]
    raw = heredity_cells(
        [(voltage, na, k, mm)],
        dt=dt,
        end_time=end_time,
        solver=solver,
        observation_times=[
            0.0,
            round(end_time / 4 / dt) * dt,
            round(end_time / 2 / dt) * dt,
            end_time,
        ],
        temperature_K=temperature_K,
    )
    raw["model"]["channels"] = [
        channel(name, 0, law, ion, permeability, 1.0, gate)
        for name, law, ion, permeability, gate in PATCH_CHANNELS
    ]
    always = [dict(time=0.0, availability=1.0)]
    raw["experiment"]["channel_controls"] = [
        dict(channel_id=row[0], schedule=copy.deepcopy(always)) for row in PATCH_CHANNELS
    ]
    raw["execution"]["channel_capacity"] = len(PATCH_CHANNELS)
    return raw
