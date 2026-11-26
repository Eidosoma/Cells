"""Engine worlds matched to the independent coupling references (A4: R-feedback; A5: R-cell).

docs/INVENTORY_COUPLING_DESIGN.md §4.3 to §4.4 (A4, A5) and Appendix A.5. One declaration, a
reference `World` built from validation/coupling/cells_reference's documented classes only
(validation/coupling/REFERENCES_USAGE.md; their code is not read here), is translated into the
engine's definition: cells.model.resolved_pump_composite@1 over cells.model.resolved_pump_tissue@3, with
cells.operator.species_regulated_availability@1 and, for a regulator, D150's cells.operator.scheduled_species_turnover@1.
Both describe pump-free cells, each with one constant-field patch on a held bath at 0 V,
gate-free K-leak populations (cells.channel.kleak_always_open@1), contacts with their gate held open (the
junction gate at a minimum of 1), and the operator's states and couplings.

* `feedback_world` (A4): two cells joined by a contact, a state of Na in both, its complement on
  the contact (side both, basal b): inventory -> effective control -> electrical response ->
  inventory.
* `cell_world` (A5): one cell with a K-leak population, a neutral regulator X with D150's turnover
  and a production pulse, read at once (a Hill inhibition) on the population.
* `engine_definition(world, dt, end, times)`: the engine's definition of a reference World.
* `regulator_species`: the regulators' engine species, neutral and impermeant.

All values are synthetic. The engine's constants are the reference's inputs (F, R, 310 K).
"""

import copy
import math

from cells.definitions import pump_composite_spec as cs
from cells.laws.electrochemistry import F, R
from cells.registry.inventory_species import add_inventory_species
from validation.coupling import cells_reference as rc
from validation.coupling import state_reference as rs
from validation.tissue import regulated_availability_fixtures as rf

SPECIES, Z = ("Na", "K", "Cl"), (1, 1, -1)
BATH_mM = (145.0, 5.0, 150.0)  # Held, 0 V.
TEMPERATURE_K = 310.0
CONSTANTS = rc.Constants(F, R, TEMPERATURE_K)
IMEX = "cells.solver.imex_ars222_face_electromigration@1"
FIELD_SOLVER = "cells.solver.capacitive_reduction_gauged_damped_newton@2"
GATE_THRESHOLD_V = 0.015  # Immaterial: the gate's minimum is 1, so it stays open.
FLOOR_FMOL = 1e-20
D_REGULATOR = 1e-10


# ------------------------------------------------------------------ the two worlds


def feedback_world(
    *,
    k_on=5.0,
    k_off=1.0,
    s0=(0.2, 0.6),
    half_saturation=20.0,
    coefficient=4.0,
    basal=0.2,
    enabled=1,
    contact_P=2e-8,
    held_input=None,
    start=None,
):
    """A4's world: cells a (Na-rich) and b, each a 2 pL cell on a 4 pF patch, joined by a contact
    with its gate open; a state s1 of Na in both (a Hill activation); its complement on the
    contact (side both, basal b). held_input: {cell: Na mM} replaces the Na input by a regulator
    held at that level (the open loop). start: {"mM": {cell: (Na, K, Cl)}, "V": {cell: V}, "s":
    {cell: s}} starts from a state already relaxed through the contact (`relaxed`)."""
    if start is None:
        cells = {
            "a": rc.Cell(2.0, (40.0, 110.0, 30.0)),
            "b": rc.Cell(2.0, (12.0, 140.0, 30.0)),
        }
        initial = {"a": s0[0], "b": s0[1]}
    else:
        cells = {
            c: rc.Cell(2.0, tuple(start["mM"][c]), initial_V=start["V"][c]) for c in ("a", "b")
        }
        initial = dict(start["s"])
    leak = (2e-11, 4e-10, 1e-10)
    patches = {f"p_{c}": rc.Patch(c, 4e-10, 4e-12, leak) for c in cells}
    contacts = {"e": rc.Contact(("a", "b"), 1e-10, (contact_P,) * 3)}
    regulators = {}
    source = "Na"
    if held_input is not None:
        regulators["Xna"] = rc.Regulator(
            {
                c: rs.Turnover(mM * cells[c].volume_pL, cells[c].volume_pL)
                for c, mM in held_input.items()
            }
        )
        source = "Xna"
    states = {
        "s1": rc.State(
            ("a", "b"),
            (rc.Input("hill_activation", source, half_saturation, coefficient),),
            k_on,
            k_off,
            initial=initial,
        )
    }
    couplings = {
        "c_e": rc.Coupling(
            "e", "state_complement", "s1", basal=basal, side="both", enabled=((0.0, enabled),)
        )
    }
    return rc.World(
        CONSTANTS,
        SPECIES,
        Z,
        BATH_mM,
        cells,
        patches,
        contacts=contacts,
        regulators=regulators,
        states=states,
        couplings=couplings,
    )


def cell_world(
    *,
    regulator_mM=1e-3,
    clearance=5.0,
    pulse=(0.2, 0.5),
    pulse_factor=10.0,
    half_saturation=3e-3,
    coefficient=2.0,
    basal=0.1,
    enabled=1,
    population_P=2e-9,
    population_schedule=((0.0, 1.0),),
):
    """A5's world: one 2 pL cell on a 4 pF patch with a K-leak population; a neutral regulator X
    held at its anchor by D150's turnover (production = clearance x anchor), raised toward
    pulse_factor x anchor over the pulse; X read at once on the population (a Hill inhibition
    with a basal level)."""
    volume = 2.0
    cells = {"c0": rc.Cell(volume, (15.0, 140.0, 10.0))}
    patches = {"p_c0": rc.Patch("c0", 4e-10, 4e-12, (1e-11, 1e-10, 5e-11))}
    populations = {
        "kleak": rc.Population("p_c0", population_P, (0.0, 1.0, 0.0), schedule=population_schedule)
    }
    n0 = regulator_mM * volume
    base = clearance * n0
    segments = (
        (0.0, base, clearance),
        (pulse[0], pulse_factor * base, clearance),
        (pulse[1], base, clearance),
    )
    regulators = {"X": rc.Regulator({"c0": rs.Turnover(n0, volume, segments)})}
    couplings = {
        "c_k": rc.Coupling(
            "kleak",
            "hill_inhibition",
            "X",
            basal=basal,
            K_mM=half_saturation,
            n=coefficient,
            enabled=((0.0, enabled),),
        )
    }
    return rc.World(
        CONSTANTS,
        SPECIES,
        Z,
        BATH_mM,
        cells,
        patches,
        populations=populations,
        regulators=regulators,
        couplings=couplings,
    )


def relaxed(make, t_relax, **kwargs):
    """A4's world started from the reference's own state at t_relax, after the contact has
    equalized the cells' voltages (the fast transient), so no stiff transient enters the dt study:
    the cells' composition, potential and state there become the new start."""
    world = make(**kwargs)
    run = rc.simulate(world, t_relax, record=(t_relax,))
    row = run.at[t_relax]
    start = dict(
        mM={c: tuple(row["mM"][c]) for c in world.cells},
        V=dict(row["V"]),
        s={cell: row["s"][(state, cell)] for state, cell in run.slots},
    )
    return lambda **more: make(start=start, **{**kwargs, **more})


# ------------------------------------------------------------------ the translation


def _schedule(changes):
    return [dict(time=float(t), availability=float(a)) for t, a in changes]


def _node(name, volume, mM, *, outside=False, charge_C=0.0, background_fmol=None):
    amounts = {s: c * volume for s, c in zip(SPECIES, mM, strict=True)}
    if background_fmol is None:  # Electroneutral at its charge.
        background_fmol = charge_C / (F * 1e-15) - math.fsum(
            z * amounts[s] for s, z in zip(SPECIES, Z, strict=True)
        )
    node = dict(
        id=name,
        volume_pL=volume,
        initial_amount_fmol=amounts,
        fixed_charge_equivalent_fmol=background_fmol,
        initial_charge_C=charge_C,
    )
    return node | (dict(reservoir=True, boundary_potential_V=0.0) if outside else {})


def regulator_species(world):
    return sorted(world.regulators)


def engine_definition(world, *, dt, end, times, initial):
    """The engine's definition of `world` (a reference World), run with step dt to `end`,
    observed at `times` (exact multiples of dt). initial: {cell: (V, background_fmol)}, the start
    both sides share (the reference's run.initial, or the engine's own)."""
    rc.check_world(world)
    cells = list(world.cells)
    capacitance = {
        c: math.fsum(p.capacitance_F for p in world.patches.values() if p.cell == c) for c in cells
    }
    model_cells = []
    for c in cells:
        V, background = initial[c]
        cell = world.cells[c]
        model_cells.append(
            _node(
                c, cell.volume_pL, cell.mM, charge_C=capacitance[c] * V, background_fmol=background
            )
        )
    bath = _node("bath", 1.0, world.bath_mM, outside=True)
    membranes = [
        dict(
            id=name,
            inside=p.cell,
            outside="bath",
            area_m2=p.area_m2,
            capacitance_F=p.capacitance_F,
            permeability_m_per_s=dict(zip(SPECIES, p.permeability_m_s, strict=True)),
            law="cells.route.constant_field@1",
            pump=None,
            calcium_pump=None,
        )
        for name, p in world.patches.items()
    ]
    channels = []
    for name, q in world.populations.items():
        if tuple(q.relative) != (0.0, 1.0, 0.0) or q.opening != 1.0:
            raise ValueError(
                "The engine's gate-free K leak is cells.channel.kleak_always_open@1 (K only, open)"
            )
        channels.append(
            dict(
                id=name,
                membrane_id=q.patch,
                kinetic_law="cells.channel.kleak_always_open@1",
                max_permeability_m_per_s=q.permeability_m_s,
                abundance=q.abundance,
                initial_gate=[],
                permeant_ions=[dict(species_id="K", relative_permeability=1.0)],
            )
        )
    junctions = []
    for name, e in world.contacts.items():
        if e.gate != 1.0:
            raise ValueError("The engine's contact gate is held open at 1 (its minimum)")
        junctions.append(
            dict(
                id=name,
                sender=e.cells[0],
                receiver=e.cells[1],
                area_m2=e.area_m2,
                permeability_m_per_s=dict(zip(SPECIES, e.permeability_m_s, strict=True)),
                law="cells.route.constant_field@1",
                gate=dict(
                    law="cells.junction.junction_voltage_relaxation@1",
                    threshold_voltage_V=GATE_THRESHOLD_V,
                    minimum_open_fraction=1.0,
                    initial_gate=1.0,
                ),
            )
        )
    raw = dict(
        schema_version=1,
        model=dict(
            id="cells.model.resolved_pump_tissue@3",
            temperature_K=world.constants.temperature_K,
            species=[dict(id=s, valence=z) for s, z in zip(SPECIES, Z, strict=True)],
            cells=model_cells,
            extracellular=[bath],
            membranes=membranes,
            junctions=junctions,
            faces=[],
            closure=dict(
                law="cells.field_closure.resolved_capacitor_components_current_continuity@1",
                gauge_reference=None,
            ),
            channels=channels,
        ),
        experiment=dict(
            end_time=end,
            observation_times=list(times),
            membrane_controls=[
                dict(membrane_id=m["id"], schedule=_schedule(((0.0, 1.0),))) for m in membranes
            ],
            junction_controls=[
                dict(junction_id=name, schedule=_schedule(e.schedule))
                for name, e in world.contacts.items()
            ],
            pump_controls=[],
            calcium_pump_controls=[],
            channel_controls=[
                dict(channel_id=name, schedule=_schedule(q.schedule))
                for name, q in world.populations.items()
            ],
        ),
        execution=dict(
            dt=dt,
            capacity=len(model_cells),
            extracellular_capacity=1,
            membrane_capacity=len(membranes),
            edge_capacity=len(junctions),
            face_capacity=1,
            channel_capacity=len(channels),
            backend="cpu",
            jit=True,
            precision="float64",
            solver=IMEX,
            field_solver=FIELD_SOLVER,
            max_steps=int(math.ceil(end / dt)) + 8,
            max_trace_bytes=2**31,
            material_balance_atol_fmol={s: 1e-10 for s in SPECIES},
        ),
    )
    for name, regulator in sorted(world.regulators.items()):
        concentrations = {c: t.n0_fmol / t.volume_pL for c, t in regulator.amounts.items()}
        trace = min(concentrations.values())
        raw = add_inventory_species(
            raw,
            name,
            trace_mM=trace,
            diffusivity_m2_per_s=D_REGULATOR,
            floor_fmol=FLOOR_FMOL,
            concentrations_mM=concentrations,
        )
    raw = cs.frozen_definition(raw)
    raw = _with_operator(raw, world)
    return _with_turnover(raw, world)


def _with_operator(raw, world):
    if not world.states and not world.couplings:
        return raw
    read = sorted(
        {i.species for s in world.states.values() for i in s.inputs}
        | {c.source for c in world.couplings.values() if c.source not in world.states}
    )
    states = []
    for name, s in world.states.items():
        initial = s.initial if isinstance(s.initial, dict) else {c: s.initial for c in s.cells}
        level = None if math.isnan(s.crossing_level) else s.crossing_level
        states.append(
            rf.state(
                name,
                list(s.cells),
                [(i.law, i.species, i.K_mM, i.n) for i in s.inputs],
                on=s.k_on_per_s,
                off=s.k_off_per_s,
                initial=dict(initial),
                level=level,
            )
        )
    couplings, switches = [], {}
    for name, c in world.couplings.items():
        control = "junction" if c.target in world.contacts else "channel"
        if c.source in world.states:
            entry = rf.coupling(
                name, control, [c.target], ("state", c.source), c.law, side=c.side, basal=c.basal
            )
        else:
            entry = rf.hill_coupling(
                name, control, [c.target], c.source, c.law, c.K_mM, c.n, side=c.side, basal=c.basal
            )
        couplings.append(entry)
        switches[name] = [(float(t), int(v)) for t, v in c.enabled]
    return rf.with_coupling(
        raw, species=read, states=states, couplings=couplings, switches=switches
    )


def _with_turnover(raw, world):
    if not world.regulators:
        return raw
    routes, controls = [], []
    for name, regulator in sorted(world.regulators.items()):
        for cell, turnover in sorted(regulator.amounts.items()):
            for kind, index in (("production", 1), ("clearance", 2)):
                route = f"{kind}_{name}_{cell}"
                routes.append(dict(id=route, species=name, node=cell, kind=kind))
                controls.append(
                    dict(
                        route_id=route,
                        carrier_id=cell,
                        schedule=[
                            dict(time=float(seg[0]), rate=float(seg[index]))
                            for seg in turnover.segments
                        ],
                    )
                )
    out = copy.deepcopy(raw)
    out["model"]["operators"].insert(
        0,
        dict(
            law="cells.operator.scheduled_species_turnover@1",
            species=rf.identities(sorted(world.regulators)),
            routes=routes,
            templates=[],
        ),
    )
    out["experiment"]["turnover_controls"] = controls
    return out
