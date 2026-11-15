"""Definitions of FR-4's and FR-5's first acceptance worlds (generic; §13 of the FR-4/FR-5 note).

`fr4_world(world)` builds the resolved_pump_tissue@3 definition from parameters.World:
- **today's parts:** one owner cell in a held bath, an impermeant plasma patch, the lumped
  compartment node, its bounding patch with the K+ counterion route (constant_field@1), and the
  nine species rows (Na, K, Cl, H as proton equivalents, B_c, B_L, ATP, ADP, Pi);
- **the pending parts,** under §7.4's published names, for the core's insertion points: the
  species registry entries (`standard_mu_RT`), the stage read (`stage_reads`), the transporter
  population (`transporters`, `transporter_controls`), the proton leak (`passive_routes`), the
  held fuel rows, and FR-1's compartment declaration.

`today_only(definition)` strips the pending parts. Today's parser refuses them by design until the
core lands them. Absent rows (a buffer at the other node, fuel outside the cytosol) carry 0, and
the registry's background policy (A7) decides how the inner model treats them.
"""

import copy
import math

from validation.compartment_ph.parameters import World, h_from_ph

SPECIES = (("Na", 1), ("K", 1), ("Cl", -1), ("H", 1), ("B_c", -1), ("B_L", -1),
           ("ATP", 0), ("ADP", 0), ("Pi", 0))
PENDING_MODEL_KEYS = ("stage_reads", "transporters", "passive_routes", "held_rows", "operators")
PENDING_EXPERIMENT_KEYS = ("transporter_controls", "passive_route_controls")
CELL, BATH, LUMEN = "cell_0", "bath_0", "lumen_0"
PLASMA, BOUNDING = "plasma_0", "bounding_0"


def _amounts(world, node):
    w = world
    if node == BATH:
        conc, volume = dict(w.bath_mM), 1.0
        rows = dict(Na=conc["Na"], K=conc["K"], Cl=conc["Cl"], H=h_from_ph(conc["pH"]))
        return {s: rows.get(s, 0.0) * volume for s, _ in SPECIES}, volume
    if node == CELL:
        conc, volume, buffer = dict(w.cytosol_mM), w.owner[0], w.cytosol_buffer
        extra = dict(B_c=buffer.total_mM * volume, **{k: v * volume for k, v in w.fuel_mM.items()})
    else:
        conc, volume, buffer = dict(w.lumen_mM), w.lumen_volume_pL, w.lumen_buffer
        extra = dict(B_L=buffer.total_mM * volume)
    out = {s: 0.0 for s, _ in SPECIES}
    out.update({k: conc[k] * volume for k in ("Na", "K", "Cl")})
    out["H"] = world.proton_equivalents_fmol(conc["pH"], buffer, volume)
    out.update(extra)
    return out, volume


def _node(world, node, *, outside=False, reservoir=False):
    amounts, volume = _amounts(world, node)
    z = dict(SPECIES)
    d = dict(id=node, volume_pL=volume, initial_amount_fmol=amounts,
             fixed_charge_equivalent_fmol=-math.fsum(z[s] * n for s, n in amounts.items()),
             initial_charge_C=0.0)
    if outside:
        d.update(reservoir=reservoir, boundary_potential_V=0.0)
    return d


def _patch(world, pid, outside, area, permeability):
    return dict(id=pid, inside=CELL, outside=outside, area_m2=area,
                capacitance_F=world.specific_capacitance_F_m2 * area,
                permeability_m_per_s={s: permeability.get(s, 0.0) for s, _ in SPECIES},
                law="constant_field@1", pump=None, calcium_pump=None)


def fr4_world(world=None, *, dt_s=None):
    """The FR-4 definition (today's parts plus the pending parts); world.control() is P_K = 0."""
    w = world or World()
    dt = dt_s or w.dt_s
    steps = int(round(w.end_s / dt))
    registry = {w.cytosol_buffer.name: w.cytosol_buffer, w.lumen_buffer.name: w.lumen_buffer}
    species = []
    for s, z in SPECIES:
        entry = dict(id=s, valence=z)
        if s in registry:  # §4.1: the acid form's potential relative to the base, mu_H = 0
            b = registry[s]
            entry.update(standard_mu_RT=dict(base=0.0, acid=b.mu_acid_minus_base_RT),
                         k_on_per_mM_s=b.k_on_per_mM_s)
        species.append(entry)
    model = dict(
        id="resolved_pump_tissue@3", temperature_K=w.temperature_K, species=species,
        cells=[_node(w, CELL)],
        extracellular=[_node(w, BATH, outside=True, reservoir=True),
                       _node(w, LUMEN, outside=True, reservoir=False)],
        membranes=[_patch(w, PLASMA, BATH, w.owner[1], {}),
                   _patch(w, BOUNDING, LUMEN, w.patch_area_m2, {"K": w.counterion_k_m_s})],
        junctions=[], faces=[], channels=[],
        closure=dict(law="resolved_capacitor_components_current_continuity@1",
                     gauge_reference=None),
        # --- pending (§7.4 names; the core's insertion points) ---
        stage_reads=[dict(read_id="rapid_proton_buffer@1", proton_row="H",
                          buffers={CELL: ["B_c"], LUMEN: ["B_L"]})],
        held_rows=dict(law="maintained_held_rows@1", node=CELL, rows=["ATP", "ADP", "Pi"]),
        transporters=[dict(id="pump_0", patch=BOUNDING, law="proton_atp_mass_action_positive@1",
                           capacity_fmol_s=w.pump_capacity_fmol_s, protons_per_cycle=w.pump_n,
                           km_proton_mM=w.km_proton_mM, km_atp_mM=w.km_atp_mM,
                           fuel=dict(node=CELL, rows=["ATP", "ADP", "Pi"],
                                     delta_g0_prime_J_mol=w.delta_g0_prime_J_mol,
                                     ph_ref=w.cytosol_mM["pH"], ph_band=w.fuel_ph_band))],
        passive_routes=[dict(id="proton_leak_0", patch=BOUNDING,
                             law="proton_constant_field_leak@1",
                             permeability_m_per_s=w.proton_leak_m_s)],
        operators=[dict(law="cell_owned_compartments@1",
                        compartments=[dict(id="compartment_0", node=LUMEN, patch=BOUNDING,
                                           owner=CELL, label="lumped population",
                                           reference=None, role="lumen")])],
    )
    experiment = dict(
        membrane_controls=[dict(membrane_id=m, schedule=[dict(time=0.0, availability=1.0)])
                           for m in (PLASMA, BOUNDING)],
        junction_controls=[], pump_controls=[], calcium_pump_controls=[], channel_controls=[],
        end_time=steps * dt,
        observation_times=[k * dt for k in range(0, steps + 1, max(1, steps // 900))],
        transporter_controls=[dict(transporter_id="pump_0",
                                   schedule=[dict(time=0.0, availability=1.0)])],
        passive_route_controls=[dict(route_id="proton_leak_0",
                                     schedule=[dict(time=0.0, availability=1.0)])],
    )
    execution = dict(
        dt=dt, capacity=1, extracellular_capacity=2, membrane_capacity=2, edge_capacity=0,
        face_capacity=0, channel_capacity=0, backend="cpu", jit=True, precision="float64",
        solver="imex_ars222_face_electromigration@1",
        field_solver="capacitive_reduction_gauged_damped_newton@2", max_steps=steps + 8,
        max_trace_bytes=2**31,
        material_balance_atol_fmol=dict(Na=1e-10, K=1e-10, Cl=1e-10, H=1e-16, B_c=1e-12,
                                        B_L=1e-12, ATP=1e-12, ADP=1e-12, Pi=1e-12))
    return dict(schema_version=1, model=model, experiment=experiment, execution=execution)


def fr5_world(damage_world, *, dt_s=None):
    """FR-5's definition: FR-4's plus the cargo X, the damage control state and its routes."""
    dw = damage_world
    base = fr4_world(dw.base, dt_s=dt_s)
    m, e = base["model"], base["experiment"]
    m["species"].append(dict(id="X", valence=0))
    for node in m["cells"] + m["extracellular"]:
        volume = node["volume_pL"]
        node["initial_amount_fmol"]["X"] = volume * (
            dw.cargo_cytosol_mM if node["id"] == CELL else
            dw.cargo_lumen_mM if node["id"] == LUMEN else dw.cargo_cytosol_mM)
    for patch in m["membranes"]:
        patch["permeability_m_per_s"]["X"] = 0.0
    base["execution"]["material_balance_atol_fmol"]["X"] = 1e-12
    m["patch_damage"] = [dict(id="damage_0", patch=BOUNDING, law="bounding_patch_damage@1",
                              initial_damage=0.0, injury_rate_per_s=dw.injury_rate_per_s,
                              resealing_rate_per_s=dw.resealing_rate_per_s)]
    m["passive_routes"] += [
        dict(id="cargo_transfer_0", patch=BOUNDING, law="passive_neutral_permeation@1",
             species="X", permeability_m_per_s=dw.cargo_transfer_m_s,
             factors=[dict(law="ph_conditioned_factor@1", compartment="compartment_0",
                           ph50=dw.ph50, slope=dw.ph_slope)]),
        dict(id="cargo_pore_0", patch=BOUNDING, law="passive_neutral_permeation@1", species="X",
             permeability_m_per_s=dw.pore_cargo_m_s, factors=[dict(law="damage", id="damage_0")]),
        dict(id="proton_pore_0", patch=BOUNDING, law="proton_constant_field_leak@1",
             permeability_m_per_s=dw.pore_proton_m_s, factors=[dict(law="damage", id="damage_0")]),
    ]
    t0, t1 = dw.injury_window_s
    e["damage_controls"] = [dict(damage_id="damage_0",
                                 injury=[dict(time=0.0, value=0.0), dict(time=t0, value=1.0),
                                         dict(time=t1, value=0.0)],
                                 resealing=[dict(time=0.0, value=0.0), dict(time=t1, value=1.0)])]
    return base


def today_only(definition):
    """The definition without its pending parts: what today's parser can read."""
    out = copy.deepcopy(definition)
    for key in PENDING_MODEL_KEYS + ("patch_damage",):
        out["model"].pop(key, None)
    for entry in out["model"]["species"]:
        for key in ("standard_mu_RT", "k_on_per_mM_s"):
            entry.pop(key, None)
    for key in PENDING_EXPERIMENT_KEYS + ("damage_controls",):
        out["experiment"].pop(key, None)
    return out
