"""Small worlds for cells.operator.scheduled_bath_composition@1 (FR-10, docs/BATH_SCHEDULE_DESIGN.md).

All values are synthetic. The worlds are secreted_species_fixtures' quiescent worlds (passive
cells, zero membrane permeability, zero ion diffusivity on every face, every node at the bath's ion
composition), so the energy flows and bounds are the neutral species S's own: the species-only
worlds of D150 §7. The bath schedule is added with its formula units and events.

* dosed_world: the first delivery world's dose leg: cell_0 with its wall patch on the held bath
  `bath`, a contact patch on the finite node ecs_0, which face_0 joins to the bath. S starts from a
  declared profile (resolved by default, the bath at `c0` and the node and cell near it).
* with_bath_schedule: the operator's block and events on any composite definition.
* fr10-dose-schedule-v1's worlds (validation/tissue/bath_schedule_protocol.json: worlds and
  refusal_classes): chain_world (W1, and with no event W1's control and W4's idle pair),
  ion_world (W2), ledger_world (W3), truncated (W5's restart pieces), batch_worlds (W5's batch),
  water_world (W6), staircase_world (W7), refusal_pairs (every refusal class beside its admitted
  neighbour), and reference_inputs, the registered input file of the code-blind references
  (validation/bath_schedule/reference_inputs.json). B2's ion world and the staircase came from the
  workspace's milestone probes (bath-schedule-20261114-01/m2-probes/probe_m2.py and
  staircase/staircase_probe.py), which stay there as frozen run inputs.
"""

import copy
import math

from validation.tissue import secreted_species_fixtures as fx

LAW = "cells.operator.scheduled_bath_composition@1"
CARGO = {"cargo": {fx.SPECIES: 1}}  # S is neutral: its own formula unit.
SALTS = {"NaCl": {"Na": 1, "Cl": 1}, "KCl": {"K": 1, "Cl": 1}}


def with_bath_schedule(raw, baths, units, events):
    """baths: held bath IDs; units: {name: {species: count}}; events: (time, baths, {unit: mM})
    triples."""
    out = copy.deepcopy(raw)
    out["model"]["operators"].append(
        dict(
            law=LAW,
            baths=list(baths),
            formula_units={k: dict(v) for k, v in units.items()},
        )
    )
    out["experiment"]["bath_composition_events"] = [
        dict(time=t, baths=list(b), formula_units_mM=dict(o)) for t, b, o in events
    ]
    return out


def dosed_world(
    *,
    c0=1e-3,
    profile=None,
    dt=1e-3,
    end=0.05,
    solver=fx.IMEX,
    trace_mM=None,
    observation_times=None,
    face=(1e-10, 1e-5),
):
    """The species-only dose leg (module docstring): the bath at c0, the node and cell resolved
    near it unless `profile` ({node: mM}) says otherwise. A composite definition with no
    operators; add the schedule with with_bath_schedule."""
    concentrations = dict(bath=c0, ecs_0=0.9 * c0, cell_0=0.5 * c0)
    if profile is not None:
        concentrations = dict(profile, bath=profile.get("bath", c0))
    kwargs = {} if trace_mM is None else dict(trace_mM=trace_mM)
    return fx.world(
        cells=(("cell_0", 1.0),),
        nodes=(("ecs_0", 1.0),),
        baths=("bath",),
        contacts=(("contact_0", "cell_0", "ecs_0"),),
        faces=(("face_0", "ecs_0", "bath", face[0], face[1]),),
        dt=dt,
        end=end,
        observation_times=observation_times or [0.0, end],
        solver=solver,
        concentrations_mM=concentrations,
        **kwargs,
    )


# ------------------------------------------------------------------ fr10-dose-schedule-v1's worlds

ARS, RK4 = fx.IMEX, "rk4"
DECLARED_DT = 1e-3  # s: the declared step, the coarsest the step rule admits under ARS with events
RK4_DT = 1e-4  # s: the largest step the step rule admits under RK4 with events
RECORD_EVERY_S = 0.01
FACE_10 = (1e-9, 1e-5)  # (area m^2, length m): kappa/V = 10/s at a 1 pL node (D_S = 1e-10 m^2/s)
FACE_5 = (5e-10, 1e-5)  # 5/s
CHAIN_LEVELS_mM = (1e-3, 1e-2, 1e-3)  # S at the bath: steady, up tenfold, down tenfold
CHAIN_EVENTS_S = (1.0, 2.0)
CHAIN_END_S = 3.0
ION_OWNER_mM = dict(Na=10.0, K=140.0, Cl=20.0)  # probe I's cytosol
ION_WALL_K_M_S = 5e-10
ION_EVENT_S, ION_END_S = 0.5, 2.0
ION_STEP_mM = 45.0  # KCl for NaCl: K 5 to 50 mM, Na 145 to 100 mM
TRACE_mM, STAIR, STAIRS, DWELL_S = 1e-15, 100.0, 6, 0.3
BATCH_LEVELS_mM = ((1e-3, 1e-2), (1e-3, 3e-3), (1e-3,))  # up tenfold, up threefold, none
WATER_UNITS = {"NaM": {"Na": 1, "M": 1}, "KM": {"K": 1, "M": 1}}
BOUND_OWNER_mM = dict(Na=140.0, K=10.0, Cl=20.0)  # R12: the bath's K step raises max(c) 10 to 50
BOUND_RATIO_AT_1MS = 1.2  # R12: dt x the explicit rate at the worst composition, at 1 ms
# R12's admitted neighbour: the same world at 0.1 ms. At 0.25 ms (dt x the rate about 0.3 after the
# K step) the run-time IMEX energy ledger refuses it ("Resolved pump accounting failed: energy"; the
# rehearsal of 17 November 2026); at 0.1 ms its largest energy ratio is 0.18 of the bound.
R12_NEIGHBOUR_DT = 1e-4


def on_grid(t, dt):
    return round(t / dt) * dt


def chain_world(
    *, dt=DECLARED_DT, solver=ARS, levels=CHAIN_LEVELS_mM, events=True, operator=True,
    end=CHAIN_END_S, face_0=FACE_10,
):
    """W1: S on the chain bath -face_0- ecs_0 -face_1- ecs_1 (1 pL nodes; face_0 at 10/s, face_1
    at 5/s), two inert cells (each with its wall on the bath and a contact on one node, so every
    node is in a capacitor component with the held bath), S at steady state levels[0] everywhere,
    S impermeant at every patch; the bath stepped to levels[1],
    levels[2], ... at CHAIN_EVENTS_S. events=False declares the operator with no event (W1's
    control, W4's idle side); operator=False leaves it out (W4's other side)."""
    c0 = levels[0]
    raw = fx.world(
        cells=(("cell_0", 1.0), ("cell_1", 1.0)),
        nodes=(("ecs_0", 1.0), ("ecs_1", 1.0)),
        baths=("bath",),
        contacts=(("contact_0", "cell_0", "ecs_0"), ("contact_1", "cell_1", "ecs_1")),
        faces=(("face_0", "ecs_0", "bath", *face_0), ("face_1", "ecs_0", "ecs_1", *FACE_5)),
        dt=dt,
        end=end,
        observation_times=fx.grid_times(end, dt, RECORD_EVERY_S),
        solver=solver,
        concentrations_mM=dict(bath=c0, ecs_0=c0, ecs_1=c0, cell_0=c0, cell_1=c0),
    )
    if not operator:
        return raw
    timeline = (
        [(on_grid(t, dt), ["bath"], {"cargo": c - c0})
         for t, c in zip(CHAIN_EVENTS_S, levels[1:], strict=False)]
        if events else []
    )
    return with_bath_schedule(raw, ["bath"], CARGO, timeline)


def ion_world(
    *, dt=DECLARED_DT, solver=ARS, step_mM=ION_STEP_mM, events=True, end=ION_END_S,
    event_s=ION_EVENT_S, owner=None, wall_k_m_s=ION_WALL_K_M_S,
):
    """W2 (probe I's world): one passive cell (1 pL) on the held bath (Na 145, K 5, Cl 150 mM),
    its cytosol at `owner` (probe I's Na 10, K 140, Cl 20 mM), a K permeability on its wall, at
    rest at E_K through its charge anchor; at event_s, KCl replaces NaCl by step_mM (negative:
    NaCl replaces KCl). events=False declares the operator with no event (W2's control)."""
    from cells.laws.electrochemistry import CHARGE_PER_FMOL, F, R

    owner = dict(ION_OWNER_mM if owner is None else owner)
    raw = fx.world(
        cells=(("cell_0", 1.0),), nodes=(), contacts=(), faces=(), dt=dt, end=end, solver=solver,
        observation_times=fx.grid_times(end, dt, RECORD_EVERY_S),
    )
    m = raw["model"]
    cell = m["cells"][0]
    for species, mM in owner.items():
        cell["initial_amount_fmol"][species] = mM * cell["volume_pL"]
    wall = next(patch for patch in m["membranes"] if patch["id"] == "wall_cell_0")
    wall["permeability_m_per_s"]["K"] = wall_k_m_s
    e_k = R * m["temperature_K"] / F * math.log(fx.BATH_mM["K"] / owner["K"])
    charge = wall["capacitance_F"] * e_k
    ions = math.fsum(z * cell["initial_amount_fmol"][s] for s, z in fx.ION_SPECIES)
    cell["initial_charge_C"] = charge
    cell["fixed_charge_equivalent_fmol"] = charge / CHARGE_PER_FMOL - ions
    timeline = (
        [(on_grid(event_s, dt), ["bath"], {"NaCl": -step_mM, "KCl": step_mM})] if events else []
    )
    return with_bath_schedule(raw, ["bath"], SALTS, timeline)


def ledger_world():
    """W3 (milestone 1's B3 world): the dose leg under RK4 at 0.1 ms, every row observed, S at the
    bath stepped from 1e-3 to 1.5e-3 mM at step 20 of 60."""
    end = 60 * RK4_DT
    raw = dosed_world(
        dt=RK4_DT, end=end, solver=RK4, observation_times=fx.grid_times(end, RK4_DT, RK4_DT)
    )
    return with_bath_schedule(raw, ["bath"], CARGO, [(20 * RK4_DT, ["bath"], {"cargo": 5e-4})])


def truncated(raw, end):
    """W5's first piece: raw ended at `end` (its events before `end`, its observations up to it
    and `end` itself), with raw's own execution block, so the full definition may resume from its
    checkpoint (cells.execution.runner.branch_checkpoint keeps the execution block fixed)."""
    out = copy.deepcopy(raw)
    x = out["experiment"]
    x["end_time"] = end
    x["observation_times"] = sorted({t for t in x["observation_times"] if t < end} | {end})
    x["bath_composition_events"] = [e for e in x["bath_composition_events"] if e["time"] < end]
    return out


def batch_worlds(*, dt=DECLARED_DT):
    """W5's batch: W1's chain with three schedules on the same bath, one event each at 1 s (up
    tenfold, up threefold) or none."""
    return [chain_world(dt=dt, levels=levels, events=len(levels) > 1) for levels in BATCH_LEVELS_mM]


def water_world(offsets):
    """W6: milestone 1's water world, a heredity cell beside water@1 with its held bath bath_0,
    scheduled at 0.05 s by `offsets` over the units NaM and KM (M an anion)."""
    from cells.definitions import pump_composite_spec as cs
    from validation.tissue import pump_water_fixtures as wfx

    raw = cs.frozen_definition(
        wfx.with_water(wfx.heredity_cell("D", end_time=0.1), pf_m_s=5e-4, bath_pressure_Pa=12.5)
    )
    return with_bath_schedule(raw, ["bath_0"], WATER_UNITS, [(0.05, ["bath_0"], offsets)])


def staircase_world(*, solver=ARS, stairs=STAIRS, stair=STAIR):
    """W7 (the staircase probe's admitted protocol): the dose leg beside a face at 10/s, S at the
    trace everywhere, the bath raised to TRACE_mM x stair^stairs (1e-3 mM) by `stairs` stairs, each
    held DWELL_S, then two dwells at the dose."""
    dt = DECLARED_DT if solver == ARS else RK4_DT
    times = [on_grid(DWELL_S * k + 10 * dt, dt) for k in range(stairs)]
    end = on_grid(times[-1] + 2 * DWELL_S, dt)
    raw = dosed_world(
        dt=dt, end=end, solver=solver, trace_mM=TRACE_mM, face=FACE_10,
        profile=dict(bath=TRACE_mM, ecs_0=TRACE_mM, cell_0=TRACE_mM),
        observation_times=fx.grid_times(end, dt, RECORD_EVERY_S),
    )
    levels = [TRACE_mM * stair ** (k + 1) for k in range(stairs)]
    events = [(t, ["bath"], {"cargo": c - TRACE_mM}) for t, c in zip(times, levels, strict=True)]
    return with_bath_schedule(raw, ["bath"], CARGO, events)


def _neutral_step(c0, c1, *, solver=ARS, dt=None, face=FACE_10, steps=50):
    """The dose leg from c0 to c1 mM (the bath's S) at step 10 of `steps`, from the resolved
    profile at c0 (milestone 2's steps-test form)."""
    dt = (DECLARED_DT if solver == ARS else RK4_DT) if dt is None else dt
    raw = dosed_world(c0=c0, dt=dt, end=steps * dt, solver=solver, face=face)
    return with_bath_schedule(raw, ["bath"], CARGO, [(10 * dt, ["bath"], {"cargo": c1 - c0})])


def bound_permeability():
    """R12's wall K permeability (m/s): the constant-field slope conductance of the explicit-rate
    bound, F^2/RT P A max(c) over the cell's capacitance (surface_pump.explicit_rate_bound's
    membrane term), times 1 ms, equals BOUND_RATIO_AT_1MS at the worst composition (the bath's K at
    50 mM above the cytosol's 10 mM); so the declared composition gives a fifth of it."""
    from cells.laws.electrochemistry import F, R

    worst_mM = fx.BATH_mM["K"] + ION_STEP_mM
    slope = F * F / (R * 310.0)
    rate_per_permeability = slope * fx.WALL_AREA_M2 * worst_mM / fx.WALL_C_F
    return BOUND_RATIO_AT_1MS / (DECLARED_DT * rate_per_permeability)


def bound_world(*, dt=DECLARED_DT, events=True, end=1.0):
    """R12: W2's cell with a low cytosolic K (BOUND_OWNER_mM) and a wall K permeability from
    bound_permeability(), the bath's K stepped 5 to 50 mM at 0.5 s."""
    return ion_world(
        dt=dt, end=end, owner=BOUND_OWNER_mM, wall_k_m_s=bound_permeability(), events=events
    )


def refusal_pairs():
    """Every refusal class of the protocol (refusal_classes), as {class: (refused, admitted)}:
    raw definitions, the refused one refused at the definition by the check the class names, its
    neighbour admitted. R12's neighbour runs at 0.1 ms, and R12 adds the declared composition
    alone at 1 ms (admitted: the worst composition decides). R3's neighbour is W7's staircase.
    R9_the_species_cap is retired (the lead's ruling, 23 November 2026): FR-43 (D315) raised the
    species cap from 16 to 1,024 after the judged run, so its 17-species world is admitted; the cap
    is an engine limit with its own tests (tests/unit/test_species_cap*.py). The registered results
    stay reproducible at their tags."""
    short = dict(end=0.6, event_s=0.5)
    salt_units = {"bad": {"K": 1}}
    big_units = {"big": {"Na": 1000, "Cl": 1000}}
    held_bath = ledger_world()
    finite = copy.deepcopy(held_bath)
    block = next(op for op in finite["model"]["operators"] if op["law"] == LAW)
    block["baths"] = ["ecs_0"]
    finite["experiment"]["bath_composition_events"] = []
    charged = copy.deepcopy(held_bath)
    block = next(op for op in charged["model"]["operators"] if op["law"] == LAW)
    block["formula_units"] = {**block["formula_units"], **salt_units}
    big = copy.deepcopy(held_bath)
    block = next(op for op in big["model"]["operators"] if op["law"] == LAW)
    block["formula_units"] = {**block["formula_units"], **big_units}
    return {
        "R1_past_a_neutral_corner": (_neutral_step(1e-3, 1.01e-2), _neutral_step(1e-3, 1e-2)),
        "R2_a_measured_failure": (_neutral_step(1e-6, 1e-3), _neutral_step(1e-5, 1e-3)),
        "R3_a_dose_from_nothing": (staircase_world(stairs=1, stair=1e12), staircase_world()),
        "R4_past_the_down_corner": (
            _neutral_step(1.01e-2, 1.01e-4), _neutral_step(1e-2, 1e-4)),
        "R5_past_the_K_corner": (
            ion_world(step_mM=45.5, **short), ion_world(step_mM=45.0, **short)),
        "R6_an_unmeasured_ion_direction": (
            ion_world(step_mM=-2.5, **short), ion_world(step_mM=2.5, **short)),
        "R7_a_faster_face": (
            _neutral_step(1e-3, 1e-2, face=(1.1e-9, 1e-5)), _neutral_step(1e-3, 1e-2)),
        "R8_outside_the_measured_steps": (
            [_neutral_step(1e-3, 1e-2, dt=2e-3), _neutral_step(1e-3, 1e-2, solver=RK4, dt=2e-4)],
            [_neutral_step(1e-3, 1e-2), _neutral_step(1e-3, 1e-2, solver=RK4)]),
        "R10_a_charged_unit": (charged, big),
        "R11_an_anisosmotic_step": (water_world({"KM": 10.0}),
                                    water_world({"NaM": -10.0, "KM": 10.0})),
        "R12_beyond_the_explicit_bound": (
            bound_world(dt=DECLARED_DT), bound_world(dt=R12_NEIGHBOUR_DT)),
        "R13_not_a_held_bath": (finite, held_bath),
    }
