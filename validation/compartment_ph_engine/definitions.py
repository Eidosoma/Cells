"""Definitions of FR-4's and FR-5's first acceptance worlds (generic; §13 of the FR-4/FR-5 note).

`fr4_world(world)` builds the cells.model.resolved_pump_tissue@3 definition from parameters.World:
- one owner cell in a held bath, an impermeant plasma patch, the lumped compartment node and its
  bounding patch with the K+ counterion route (cells.route.constant_field@1), and the nine species rows (Na,
  K, Cl, H as proton equivalents, B_c, B_L, ATP, ADP, Pi) with their species-registry entries;
- the declared kinds (§7.4 (k)): B4's rapid-buffer closure (`stage_reads`,
  cells.kind.rapid_proton_buffer@1), the proton pump (`transporters`, cells.kind.transporter@1, on held
  fuel whose rows the kind holds) and the proton leak (`passive_routes`, cells.kind.passive_routes@1).
  Δ_rG'° is the registry's: the fuel rows' potentials (`fuel_potentials_RT`);
- FR-1's compartment declaration (`operators`), for the composite path.

`development_world(definition)` is the definition without the compartment operator: @3 plus the
kinds, as the development rungs run it (the lead's ruling, 15 November 2026). Before registration
the declared world runs with the operator and is shown bitwise equal to it, or the protocol's world
is corrected as a dated pre-run correction.

`today_only(definition)` strips what today's parser refuses: the compartment operator, FR-5's
damage state, conditions and schedules, and the passive routes that declare factors (FR-5's,
dropped whole). FR-5's parts are the FR-4/FR-5 note's §16 forms: `patch_damage`
(cells.kind.patch_damage@1) and `ph_conditions` (cells.kind.ph_condition@1, at a node by its ID) are the
routing door's sources, and a route's `factors` lists their IDs in declared order; the schedules
take the core's gap-6 format when it lands (`damage_controls` is the draft's placeholder).
Rows that do not apply at a node carry the world's declared trace (absent rows are refused, the
operators' PLAN §2.4), with `background` (trace_mM, floor_fmol) on B_c, B_L, ATP, ADP and Pi. The
closure's mask is the declared (node, row) pairs, so a trace is never a live buffer.

Records: every rung of every world records every `RECORD_EVERY_S` (1 s) on the step grid, so the
rungs of a dt ladder share their record times (keyed by integer second) with each other and with
the references: 901 rows for FR-4's 900 s, 401 for FR-5's 400 s.

FR-5's start (§13.2) is one **start extract** (`START_KIND`): the amounts and charges of FR-4's
engine checkpoint at 1800 s, written once by the run that made the checkpoint. `fr5_world(...,
start=extract)` takes its amounts and charges (each node's fixed charge then follows from them,
as the excision transplants do), and the references read the same extract as `tr.Start`.
"""

import copy
import hashlib
import json
import math
from dataclasses import replace

from validation.compartment_ph_engine.parameters import CHARGE_PER_FMOL, R, World, h_from_ph

SPECIES = (("Na", 1), ("K", 1), ("Cl", -1), ("H", 1), ("B_c", -1), ("B_L", -1),
           ("ATP", 0), ("ADP", 0), ("Pi", 0))
PENDING_MODEL_KEYS = ("operators", "patch_damage", "ph_conditions")
COMPOSITE_MODEL = (
    "cells.model.resolved_pump_composite@1"  # declared_world's: @3 inner, FR-1's operator
)
BACKGROUND_ROWS = ("B_c", "B_L", "ATP", "ADP", "Pi")
PENDING_EXPERIMENT_KEYS = ("damage_controls",)
FUEL_ROWS = ("ATP", "ADP", "Pi")
PUMP_LAW = "cells.cycle.proton_atp_mass_action_positive@1"
HELD_FUEL = "cells.fuel_kind.maintained_held_rows@1"
CELL, BATH, LUMEN = "cell_0", "bath_0", "lumen_0"
PLASMA, BOUNDING = "plasma_0", "bounding_0"
RECORD_EVERY_S = 1.0
START_KIND = "cells.compartment_ph_start@1"
START_PRODUCERS = ("engine", "reference_self_check")
FR5_CONTROLS = ("f_equals_1", "d_equals_0")  # arm T's control (no condition); arm R's (no damage)
DAMAGE, CONDITION = "damage_0", "acid_0"  # FR-5's routing-door sources (the note's §16.2)


def record_stride(end_s, dt_s, every_s=RECORD_EVERY_S):
    """(steps, stride): the run's steps and the steps between records, refused unless the records
    fall on the step grid every `every_s` and the run ends on a record."""
    steps, stride = round(end_s / dt_s), round(every_s / dt_s)
    if abs(stride * dt_s - every_s) > 1e-9 * every_s or steps % stride or abs(
            steps * dt_s - end_s) > 1e-9 * end_s:
        raise ValueError(f"records every {every_s} s are not on the {dt_s} s grid to {end_s} s")
    return steps, stride


def _amounts(world, node):
    w = world
    if node == BATH:
        conc, volume = dict(w.bath_mM), 1.0
        rows = dict(Na=conc["Na"], K=conc["K"], Cl=conc["Cl"], H=h_from_ph(conc["pH"]))
        return {s: rows.get(s, w.trace_mM) * volume for s, _ in SPECIES}, volume
    if node == CELL:
        conc, volume, buffer = dict(w.cytosol_mM), w.owner[0], w.cytosol_buffer
        extra = dict(B_c=buffer.total_mM * volume, **{k: v * volume for k, v in w.fuel_mM.items()})
    else:
        conc, volume, buffer = dict(w.lumen_mM), w.lumen_volume_pL, w.lumen_buffer
        extra = dict(B_L=buffer.total_mM * volume)
    out = {s: w.trace_mM * volume for s, _ in SPECIES}  # absent rows: the declared trace
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
                law="cells.route.constant_field@1", pump=None, calcium_pump=None)


def fuel_potentials_RT(world):
    """The fuel rows' registry potentials (mu°'/RT at c0). Only the reaction's sum is declared,
    Δ_rG'° = mu°'(ADP) + mu°'(Pi) - mu°'(ATP) (a generic value, §13), so ATP and Pi carry 0."""
    return dict(ATP=0.0, ADP=world.delta_g0_prime_J_mol / (R * world.temperature_K), Pi=0.0)


def fr4_world(world=None, *, dt_s=None):
    """The FR-4 definition (today's parts plus the pending parts); world.control() is P_K = 0."""
    w = world or World()
    dt = dt_s or w.dt_s
    steps, stride = record_stride(w.end_s, dt)
    registry = {w.cytosol_buffer.name: w.cytosol_buffer, w.lumen_buffer.name: w.lumen_buffer}
    species = []
    for s, z in SPECIES:
        entry = dict(id=s, valence=z)
        if s in registry:  # §4.1: the acid form's potential relative to the base, mu_H = 0
            b = registry[s]
            # The operators' registry keys (e66fea95): the base form's mu°/RT at valence z and the
            # protonated form's at z + 1, at the same c0.
            entry.update(standard_mu_RT=0.0, protonated_standard_mu_RT=b.mu_acid_minus_base_RT)
        if s == "H":
            entry.update(standard_mu_RT=0.0)  # the proton row declares its own potential
        if s in FUEL_ROWS:  # Δ_rG'° comes from the registry only (B3)
            entry.update(standard_mu_RT=fuel_potentials_RT(w)[s])
        if s in BACKGROUND_ROWS:
            entry.update(background=dict(trace_mM=w.trace_mM, floor_fmol=w.trace_floor_fmol))
        species.append(entry)
    model = dict(
        id="cells.model.resolved_pump_tissue@3", temperature_K=w.temperature_K, species=species,
        cells=[_node(w, CELL)],
        extracellular=[_node(w, BATH, outside=True, reservoir=True),
                       _node(w, LUMEN, outside=True, reservoir=False)],
        membranes=[_patch(w, PLASMA, BATH, w.owner[1], {}),
                   _patch(w, BOUNDING, LUMEN, w.patch_area_m2, {"K": w.counterion_k_m_s})],
        junctions=[], faces=[], channels=[],
        closure=dict(law="cells.field_closure.resolved_capacitor_components_current_continuity@1",
                     gauge_reference=None),
        # --- pending (§7.4 names; the core's insertion points) ---
        standard_concentration_mM=w.standard_concentration_mM,
        stage_reads=[dict(read_id="cells.kind.rapid_proton_buffer@1", proton_row="H",
                          buffers={CELL: ["B_c"], LUMEN: ["B_L"]},
                          k_on_per_mM_s={b.name: b.k_on_per_mM_s for b in registry.values()})],
        transporters=[dict(id="pump_0", patch=BOUNDING, law=PUMP_LAW,
                           capacity_fmol_s=w.pump_capacity_fmol_s, stoichiometry=w.pump_n,
                           km_role_mM=w.km_proton_mM, km_atp_mM=w.km_atp_mM, role="H",
                           fuel=dict(kind=HELD_FUEL, node=CELL, rows=list(FUEL_ROWS),
                                     ph_ref=w.cytosol_mM["pH"], ph_band=w.fuel_ph_band))],
        passive_routes=[dict(id="proton_leak_0", patch=BOUNDING,
                             law="cells.route.proton_constant_field_leak@1",
                             permeability_m_per_s=w.proton_leak_m_s)],
        operators=[dict(law="cells.operator.cell_owned_compartments@1",
                        compartments=[dict(id="compartment_0", node=LUMEN, patch=BOUNDING,
                                           owner=CELL, label="lumped population",
                                           reference=None, role="lumen")])],
    )
    experiment = dict(
        membrane_controls=[dict(membrane_id=m, schedule=[dict(time=0.0, availability=1.0)])
                           for m in (PLASMA, BOUNDING)],
        junction_controls=[], pump_controls=[], calcium_pump_controls=[], channel_controls=[],
        end_time=steps * dt,
        observation_times=[k * dt for k in range(0, steps + 1, stride)],
    )
    execution = dict(
        dt=dt,
        capacity=1,
        extracellular_capacity=2,
        membrane_capacity=2,
        edge_capacity=0,
        face_capacity=0,
        channel_capacity=0,
        backend="cpu",
        jit=True,
        precision="float64",
        solver="cells.solver.imex_ars222_face_electromigration@1",
        field_solver="cells.solver.capacitive_reduction_gauged_damped_newton@2",
        max_steps=steps + 8,
        max_trace_bytes=2**31,
        material_balance_atol_fmol=dict(
            Na=1e-10, K=1e-10, Cl=1e-10, H=1e-16, **{s: w.trace_floor_fmol for s in BACKGROUND_ROWS}
        ),
    )
    return dict(schema_version=1, model=model, experiment=experiment, execution=execution)


def fr5_world(damage_world, *, dt_s=None, start=None, control=None):
    """FR-5's definition for one arm (parameters.ARM_T or ARM_R): FR-4's plus the cargo X, the
    damage control state and its routes, over the arm's horizon.

    `start` is the start extract (`read_start`) of FR-4's engine checkpoint at
    dw.start_checkpoint_s: each node takes its amounts and charge, and its fixed charge follows
    from them (charge / CHARGE_PER_FMOL - sum z n); X is added at its declared start amounts
    (neutral, so the charges stand). Without it the definition keeps FR-4's pH 7.2 start, which is
    not FR-5's declared start: the qualification generator refuses to run it. The definition
    holds exactly schema_version, model, experiment and execution (parse_spec's keys): the
    extract's identity is the part's record's (the generator's `_with_start`). `control` is
    "f_equals_1" (the conditioned route without its factor: arm T's control) or "d_equals_0" (no
    injury, so d stays 0: arm R's control). A cargo pore of zero permeability is left out (arm T's
    proton-only pore), as in the references' arms. The condition names the lumen's node (a kind's
    parse sees the base model's nodes, not FR-1's identity map: the note's §16.2)."""
    dw = damage_world
    if control not in (None, *FR5_CONTROLS):
        raise ValueError(f"unknown FR-5 control {control!r}")
    base = fr4_world(replace(dw.base, end_s=dw.horizon_s), dt_s=dt_s or dw.dt_s)
    m, e = base["model"], base["experiment"]
    z = dict(SPECIES)
    if start is not None:
        if abs(start["time_s"] - dw.start_checkpoint_s) > 1e-9 * dw.start_checkpoint_s:
            raise ValueError("the start extract is not at the arm's declared checkpoint time")
        for node in m["cells"] + m["extracellular"]:
            taken = start["nodes"][node["id"]]
            amounts = {s_: float(taken["amounts_fmol"][s_]) for s_, _ in SPECIES}
            node["initial_amount_fmol"] = amounts
            node["initial_charge_C"] = float(taken["charge_C"])
            node["fixed_charge_equivalent_fmol"] = float(taken["charge_C"]) / CHARGE_PER_FMOL - \
                math.fsum(z[s_] * n for s_, n in amounts.items())
    m["species"].append(dict(id="X", valence=0))
    for node in m["cells"] + m["extracellular"]:
        volume = node["volume_pL"]
        node["initial_amount_fmol"]["X"] = volume * (
            dw.cargo_cytosol_mM if node["id"] == CELL else
            dw.cargo_lumen_mM if node["id"] == LUMEN else dw.cargo_cytosol_mM)
    for patch in m["membranes"]:
        patch["permeability_m_per_s"]["X"] = 0.0
    base["execution"]["material_balance_atol_fmol"]["X"] = 1e-12
    m["patch_damage"] = [dict(id=DAMAGE, patch=BOUNDING, law="cells.damage.bounding_patch_damage@1",
                              initial_damage=0.0, injury_rate_per_s=dw.injury_rate_per_s,
                              resealing_rate_per_s=dw.resealing_rate_per_s)]
    m["ph_conditions"] = [
        dict(
            id=CONDITION,
            node=LUMEN,
            law="cells.transfer_factor.ph_conditioned_factor@1",
            ph50=dw.ph50,
            slope=dw.ph_slope,
        )
    ]
    m["passive_routes"].append(
        dict(id="cargo_transfer_0", patch=BOUNDING, law="cells.route.passive_neutral_permeation@1",
             species="X", permeability_m_per_s=dw.cargo_transfer_m_s,
             factors=[] if control == "f_equals_1" else [CONDITION]))
    if dw.pore_cargo_m_s > 0:
        m["passive_routes"].append(
            dict(id="cargo_pore_0", patch=BOUNDING, law="cells.route.passive_neutral_permeation@1",
                 species="X", permeability_m_per_s=dw.pore_cargo_m_s, factors=[DAMAGE]))
    m["passive_routes"].append(
        dict(id="proton_pore_0", patch=BOUNDING, law="cells.route.proton_constant_field_leak@1",
             permeability_m_per_s=dw.pore_proton_m_s, factors=[DAMAGE]))
    t0, t1 = dw.injury_window_s
    injury = [dict(time=0.0, value=0.0)] + ([] if control == "d_equals_0" else [
        dict(time=t0, value=1.0), dict(time=t1, value=0.0)])
    resealing = [dict(time=0.0, value=0.0), dict(time=t1, value=1.0)]
    # A breakpoint after the horizon governs no step, and the core refuses one (§7.4 (l)): a
    # shortened horizon (the generator's quick pass) keeps the points up to its end only.
    end = e["end_time"]
    e["damage_controls"] = [dict(damage_id=DAMAGE,
                                 injury=[x for x in injury if x["time"] <= end],
                                 resealing=[x for x in resealing if x["time"] <= end])]
    return base


# ------------------------------------------------------------------------ the start extract


def start_extract(*, producer, nodes, readouts, time_s, dt_s, source, engine_snapshot=None,
                  world="fr4_world(replace(World(), end_s=1800.0))"):
    """FR-5's start (§13.2) as one record: every node's amounts of FR-4's nine rows (fmol) and
    its charge (C) at `time_s`, with the producing run's readouts (pH_c, pH_L, V_b_V) beside them.
    `producer` is "engine" (FR-4's engine checkpoint: the only start a judged run accepts) or
    "reference_self_check" (the reference's own state, for checking the tools before the engine
    runs)."""
    extract = dict(kind=START_KIND, producer=producer, world=world, time_s=float(time_s),
                   dt_s=dt_s, species=[s for s, _ in SPECIES], nodes=nodes, readouts=readouts,
                   source=source, engine_snapshot=engine_snapshot)
    check_start(extract)
    return extract


def check_start(extract):
    """Refuse an extract that is not a complete FR-5 start (kind, producer, every node and row)."""
    if extract.get("kind") != START_KIND or extract.get("producer") not in START_PRODUCERS:
        raise ValueError("not an FR-5 start extract (kind or producer)")
    rows = {s for s, _ in SPECIES}
    for node in (CELL, LUMEN, BATH):
        taken = extract["nodes"].get(node)
        if taken is None or set(taken["amounts_fmol"]) != rows or "charge_C" not in taken:
            raise ValueError(f"the start extract lacks node {node}'s nine rows or its charge")
        if not all(math.isfinite(v) and v > 0 for v in taken["amounts_fmol"].values()):
            raise ValueError(f"the start extract has a non-positive amount at {node}")
    if set(extract["readouts"]) != {"pH_c", "pH_L", "V_b_V"}:
        raise ValueError("the start extract's readouts are pH_c, pH_L and V_b_V")


def canonical_sha256(value):
    """A record's identity: SHA-256 of its canonical JSON (floats keep every bit)."""
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode()).hexdigest()


def start_sha256(extract):
    """The start extract's identity (canonical_sha256)."""
    return canonical_sha256(extract)


def read_start(path):
    with open(path) as handle:
        extract = json.load(handle)
    check_start(extract)
    return extract


def development_world(definition):
    """The definition as the development rungs run it: without FR-1's compartment operator, so
    @3 plus the kinds (the lead's ruling, 15 November 2026)."""
    out = copy.deepcopy(definition)
    out["model"].pop("operators", None)
    return out


def declared_world(definition):
    """The definition as the declared world runs, FR-1's compartment operator included: the
    composite's form (cells.model.resolved_pump_composite@1 with @3 as its inner model and the definition's
    own operators block). The operator adds identity and refusals only, so its records must be
    bitwise development_world's (docs/CLOSED_COMPARTMENT_DESIGN.md §3.4.1)."""
    out = copy.deepcopy(definition)
    m = out["model"]
    m["inner_model"] = m["id"]
    m["id"] = COMPOSITE_MODEL
    return out


def today_only(definition):
    """The definition without its pending parts: what today's parser can read."""
    out = copy.deepcopy(definition)
    out.pop("start", None)
    for key in PENDING_MODEL_KEYS:
        out["model"].pop(key, None)
    routes = [r for r in out["model"].get("passive_routes", ()) if not r.get("factors")]
    out["model"].pop("passive_routes", None)
    if routes:
        out["model"]["passive_routes"] = routes
    for key in PENDING_EXPERIMENT_KEYS:
        out["experiment"].pop(key, None)
    return out
