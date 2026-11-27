"""Cross-revision guard of a thin composition (D143): compiled programs and bindings.

When a frozen model's module becomes a thin composition, its earlier implementation
exists only in an earlier revision. This tool runs in each revision (the earlier one
from its execution snapshot, validation/source_snapshot.py) and saves, for a set of
frozen-format definitions:

* jaxprs: the text of the traced checked step, right-hand side and device row
  checks (tracing only, no XLA compile), and beside each text the dtype, shape and
  SHA-256 of every constant the traced program closes over, at any depth
  (NAME.KIND.consts.json). jaxpr text does not print a closed-over array's values: two
  programs that differ only in such a constant print identically, so the constants are
  compared separately. The device row checks close over the model's check constants.
  From 16 November 2026 the device row checks are also traced with margins=True
  (device_checks_margins), the program a scalar window runs under WindowPolicy
  row_checks="device" (docs/WINDOW_DEVICE_CHECKS_DESIGN.md §9.6). An older revision has
  no such text; compare reads only its first argument's files, so give the older side first.
  Identical text and constants mean identical compiled programs for every world of
  those shapes and static choices; the step size is a traced input, so it covers every dt;
* bindings: every initial state, layout and control array (at every schedule time), and
  the model's device-check constants (check.FIELD).

compare checks the two saved sets: jaxpr text equality, constant digests (dtype, shape
and bytes, in tracing order) and binding arrays (dtype, shape and bytes). Identical
programs on identical inputs run identically on a CPU. Outputs written before constants
were recorded (13 November 2026) have no .consts.json files: compare says so, and its
verdict then covers the texts and bindings only.

Seven world sets: base (small worlds of every structure: routes, sheets, RK4, events,
donors, padding), qualification (the guarded qualification worlds themselves:
W1's trajectories, W2's arms and G2-Q1's cases), injection (electrode injection
without a field-input provider, the Rm1 egg included), volume (replacement@2 over
water, v2 design §2; recorded from its first revision on, with constants), kinds
(kind-declaring worlds, D187 rule 2: FR-4's development and declared worlds and FR-5's arm
T; recorded from 16 November 2026, after D172's landing), acceptances (quick worlds of the
judged acceptances of 17 and 18 November 2026, FR-1's, FR-3's, FR-10's and FR-6's A5'', from
their protocols' own generators: docs/CORE_SEAMS_DESIGN.md §18; recorded from 18 November 2026) and
replication (quick worlds of the gap-junction replication, from its driver's own generators: the
linear model in both forms and the neither condition's line, sheet and a ladder point, D219;
recorded from 18 November 2026). The replication set has its own record: its bindings add every
step's controls and each schedule change's step, and its device row checks are traced on a
transition, the previous and current states independent inputs, beside production's window check
program (replication_bindings, replication_jaxprs).
For the qualification set, bindings are also saved at every step size of the dt studies the
guards did not repeat (W1's and Q5's), since dt enters the bound inputs (step counts,
event steps) as well as the traced program.

Usage (PYTHONPATH at the revision under test; SET is base, the default, qualification,
injection, volume, kinds, acceptances or replication):
  python -m validation.tissue.composite_crossrev jaxprs DIR [SET]
  python -m validation.tissue.composite_crossrev bindings DIR [SET]
  python -m validation.tissue.composite_crossrev compare A B
"""

import hashlib
import json
import sys
from pathlib import Path

import numpy as np


def worlds():
    """Frozen-format definitions: water@1, water@2 (routes, none, sheets, RK4) and replacement@1."""
    from cells.definitions.cell_replacement_spec import exact_event_times
    from validation.tissue import cell_replacement_fixtures as rfx
    from validation.tissue import pump_water_fixtures as wfx
    from validation.tissue import surface_pump_v3_fixtures as v3fx

    out = {}
    raw = wfx.heredity_cell("D", end_time=0.1)
    raw["experiment"]["observation_times"] = [0.0, 0.1]
    out["water"] = wfx.with_water(raw, pf_m_s=5e-4, bath_pressure_Pa=12.5)
    sheet = wfx.with_water(wfx.gated_sheet(end_time=0.01), pf_m_s=5e-4)
    sheet["model"]["junction_heat_booking"] = "cells.heat.trapezoid_nonnegative@1"
    out["water_sheet"] = sheet
    out["symport"] = wfx.with_symport(out["water"], flux_mmol_L_h=15.0, steepness=0.12)
    out["symport_none"] = wfx.with_symport(out["water"], membranes=[])
    out["symport_sheet"] = wfx.with_symport(sheet, flux_mmol_L_h=4.0)
    rk4 = wfx.with_water(
        wfx.heredity_cell("D", dt=2.5e-6, end_time=1e-4, solver="rk4"), pf_m_s=5e-4
    )
    rk4["experiment"]["observation_times"] = [0.0, 1e-4]
    out["water_rk4"] = rk4
    out["symport_rk4"] = wfx.with_symport(rk4, flux_mmol_L_h=15.0, steepness=0.12)
    dt = 1e-3
    t1, t2, t3 = exact_event_times((10, 20, 30), dt)
    cells = rfx.heredity_sheet(1, 0, dt=dt, end_time=0.05)
    cells["experiment"]["observation_times"] = [0.0, 0.05]
    templates = [
        rfx.template_from_cell(cells, "cell_1", "h"),
        rfx.template_from_cell(cells, "cell_3", "d"),
    ]
    events = ((t1, "cell_0", "h", "n1"), (t2, "cell_2", "h", "n2"), (t3, "cell_0", "d", "n4"))
    out["replacement"] = rfx.with_replacement(cells, templates, events)
    fast = dict(
        rfx.NO_ROUTES, channel_permeability_m_per_s={"cells.channel.nav1p2_m3h_regularized@1": 3e-7}
    )
    donor_events = (
        (t1, "cell_0", None, "c1", "cell_3"),
        (t2, "cell_4", "fast_nav", "c2", "cell_3"),
    )
    out["replacement_donors"] = rfx.with_replacement(
        cells, [*templates, rfx.route_template("fast_nav", fast)], donor_events
    )
    steady = dict(rfx.FORMATION, initial_abundance=1.0, lag_s=0.0, gate_at_arrival="law_steady")
    out["replacement_steady"] = rfx.with_replacement(cells, templates, events, formation=steady)
    drawn = rfx.template_from_cell(cells, "cell_1", "drawn")
    drawn["route_values"].update(
        channel_permeability_m_per_s={"cells.channel.nav1p2_m3h_regularized@1": 3.0e-7},
        membrane_permeability_m_per_s={"Na": 8e-11},
        pump_capacity_fmol_per_s_m2=1.2e8,
    )
    out["replacement_routes"] = rfx.with_replacement(
        cells, [drawn], [(t1, "cell_0", "drawn", "n1")]
    )
    padded = v3fx.definition("release", solver="cells.solver.imex_ars222_face_electromigration@1")
    padded["experiment"]["end_time"] = 0.0012
    padded["experiment"]["observation_times"] = [0.0, 0.0012]
    p1, p2 = exact_event_times((4, 9), padded["execution"]["dt"])
    own = [
        rfx.template_from_cell(padded, "cell_0", "own_0"),
        rfx.template_from_cell(padded, "cell_1", "own_1"),
    ]
    out["replacement_padded"] = rfx.with_replacement(
        padded, own, ((p1, "cell_0", "own_0", "n1"), (p2, "cell_0", "own_0", "n2"))
    )
    return out


def qualification_worlds(all_steps=False):
    """The guarded qualification worlds, as their guards run them.

    W1's judged trajectories, W2's arms, G2-Q1's cases, W37, and the 825-node world with
    closed water and with event-free replacement, each at its guarded step size (W1,
    G2-Q1, W37 and the 825-node world at 1 ms, W2 at its definition's). With all_steps,
    also W1's trajectories at every step size of W1's dt study and Q5's cases at every
    step size of Q5. FR52_cohorts is FR-52's qualification world, its two cohorts declared
    (validation/fr52_cohorts/worlds.qualification, at 10 ms; the lead's P3 and its ruling on
    the amendment's §9.4): the program with the cohort record, beside the reactions set's
    co-writer world, which runs the operator with none.
    """
    from validation import id_table
    from validation.fr52_cohorts import worlds as cohorts
    from validation.tissue import cell_replacement_fixtures as rfx
    from validation.tissue import cell_replacement_judge as judge
    from validation.tissue import cell_replacement_qualification as g2q
    from validation.tissue import pump_water_fixtures as wfx
    from validation.tissue import pump_water_kcc_qualification as w2q
    from validation.tissue import pump_water_qualification as w1q
    from validation.tissue import surface_pump_v3_study as study

    root = Path(w1q.__file__).parent  # The predictions of the revision under test.
    w1, w2, g2 = (
        id_table.load(root / name)
        for name in (
            "pump_water_predictions.json",
            "pump_water_kcc_predictions.json",
            "cell_replacement_q1_predictions.json",
        )
    )
    out = {}
    for name, path in w1q.TRAJECTORIES.items():
        raw = w1q.item(w1, path)["definition"]
        for dt in w1q.STEPS_S if all_steps else (1e-3,):
            out[f"W1_{name}@{dt:g}"] = w1q.with_step(raw, dt)
    for arm in w2["arms"]:
        out["W2_" + arm] = w2q.definition(w2, arm)
    for case, entry in g2["cases"].items():
        for dt in judge.Q5_DTS if all_steps and case in judge.Q5_CASES else (1e-3,):
            out[f"G2_{case.replace('/', '_')}@{dt:g}"] = g2q.at_dt(entry["definition"], dt)
    out["W37"] = _w37()
    tissue = study.tissue_definition(dt=1e-3, end_time=0.2, observation_times=[0.0, 0.1, 0.2])
    out["S825_closed_water"] = wfx.with_water(tissue, availability=0.0)
    out["S825_event_free"] = rfx.with_replacement(tissue)
    out["FR52_cohorts"] = cohorts.qualification()
    return out


def _w37():
    """The W37 world of composite_guard.part_w37: rim and inner replacements."""
    from cells.definitions.cell_replacement_spec import exact_event_times
    from validation.stationary import worlds as hexagons
    from validation.tissue import cell_replacement_fixtures as rfx
    from validation.tissue import cell_replacement_judge as judge
    from validation.tissue import cell_replacement_qualification as g2q

    registered = judge.REGISTERED
    raw = rfx.heredity_sheet(6, 3, scale=0.3, dt=1e-3, end_time=3.0)
    raw["experiment"]["observation_times"] = [0.0, 3.0]
    raw["model"]["junction_heat_booking"] = g2q.BOOKING
    cells, _ = hexagons.hexagon(6)
    rings = [hexagons.ring(c) for c in cells]
    rims = [i for i, r in enumerate(rings) if r == 3]
    inners = [i for i, r in enumerate(rings) if r == 1]
    slots = [*(rims[k] for k in registered["w37_rim"]), inners[registered["w37_inner"]]]
    h = next(i for i, r in enumerate(rings) if r == 6)
    (t,) = exact_event_times((registered["w37_step"],), 1e-3)
    template = rfx.template_from_cell(raw, f"cell_{h}", "h")
    events = [(t, f"cell_{i}", "h", f"n{i}") for i in slots]
    return rfx.with_replacement(raw, [template], events)


def injection_worlds():
    """cells.operator.electrode_current_injection@1 without a field-input provider, as its runs use it: the
    heredity cell with both polarities, and the Rm1 egg at its judged step (1 ms)."""
    from cells.definitions import pump_composite_spec as cs
    from validation.tissue import injection_rm1 as rm1
    from validation.tissue import pump_water_fixtures as wfx

    base = wfx.heredity_cell("H", dt=1e-3, end_time=0.004)
    base["experiment"]["observation_times"] = [0.0, 0.004]
    raw = cs.frozen_definition(base)
    cell = raw["model"]["cells"][0]["id"]
    carriers = {"K": 0.4912, "M": 0.5088}
    raw["model"]["operators"] = [
        dict(
            law="cells.operator.electrode_current_injection@1",
            electrodes=[dict(cell_id=cell, carriers=carriers)],
        )
    ]
    schedule = [dict(time=0.0, current_A=1e-12), dict(time=0.002, current_A=-1e-12)]
    raw["experiment"]["injection_controls"] = [dict(cell_id=cell, schedule=schedule)]
    return dict(injection_cell=raw, injection_rm1=rm1.definition(1e-3))


def volume_worlds():
    """cells.operator.scheduled_cell_replacement@2 over water (v2 design §2): the heredity sheet with templates
    at their own arrival volumes and a copy of the centre into the ring, and without events."""
    from cells.definitions.cell_replacement_spec import exact_event_times
    from validation.tissue import cell_replacement_fixtures as rfx

    dt = 1e-3
    t1, t2 = exact_event_times((10, 20), dt)
    raw = rfx.heredity_sheet(1, 0, dt=dt, end_time=0.03)
    raw["experiment"]["observation_times"] = [0.0, 0.03]
    v0 = raw["model"]["cells"][0]["volume_pL"]
    templates = [
        rfx.template_from_cell(raw, "cell_1", "h"),
        rfx.template_from_cell(raw, "cell_3", "d"),
    ]
    templates[0]["volume_pL"], templates[1]["volume_pL"] = 0.97 * v0, 1.03 * v0
    events = (
        (t1, "cell_0", "h", "n1"),
        (t1, "cell_1", "d", "n2"),
        (t2, "cell_0", None, "c1", "cell_3"),
    )
    return dict(
        volume_events=rfx.over_water(raw, templates, events),
        volume_idle=rfx.over_water(raw, templates),
    )


def _first_steps(definition, steps=5):
    """The definition over its first steps, recorded at its start and end."""
    import copy

    out = copy.deepcopy(definition)
    dt = out["execution"]["dt"]
    out["experiment"]["end_time"] = steps * dt
    out["experiment"]["observation_times"] = [0.0, steps * dt]
    out["execution"]["max_steps"] = steps + 8
    return out


def kinds_worlds():
    """Kind-declaring worlds (validation/compartment_ph_engine/definitions.py), the other sets
    declaring none: FR-4's development world (@3 with the three built-in kinds, the
    transporter's controls and the exact-booked neutral route), its declared world (the
    composite with FR-1's compartment operator) and FR-5's arm T development world in the form
    today's parser reads (definitions.today_only: its damage factors and patch operator are
    pending), each over its first five steps. Out of tree until 16 November 2026 (core-next's
    kinds_crossrev.py)."""
    from validation.compartment_ph_engine import definitions as defs
    from validation.compartment_ph_engine import parameters as par

    fr4 = _first_steps(defs.fr4_world())
    declared = defs.declared_world(fr4)
    declared.pop("start", None)
    fr5 = _first_steps(defs.fr5_world(par.ARM_T, control="f_equals_1"))
    return {
        "fr4_development": defs.development_world(fr4),
        "fr4_declared": declared,
        "fr5_t_development": defs.today_only(defs.development_world(fr5)),
    }


def acceptances_worlds():
    """Quick worlds of the judged acceptances that the core-seams pass's files serve
    (docs/CORE_SEAMS_DESIGN.md §18), each built by its registered protocol's own generator:

    * FR-1, fr1-closed-compartment-v1 (compartment_acceptance_fixtures):
      cells.operator.cell_owned_compartments@1 with exchange@1's first-order export from the cytosol into the
      compartment, beside turnover@1's first-order clearance at its node (C6, load_and_degrade)
      or beside D152's first-order S -> P there (C7, load_and_react);
    * FR-3, fr3-site-occupancy-v1 (site_occupancy_acceptance_fixtures): cells.operator.site_occupancy@1 with an
      outward population internalising into its cell and an inward one on the cell's wall
      (q5_inward), and with the internalisation multiplier off, on at 5 s and off at 10 s
      (q5_class_switch);
    * FR-10, fr10-dose-schedule-v1 (bath_schedule_fixtures): cells.operator.scheduled_bath_composition@1's ion
      world, KCl for NaCl at 0.5 s beside a K-permeable cell under ARS at 1 ms (W2), and its
      ledger world, the dose leg's bath S stepped at step 20 of 60 under RK4 at 0.1 ms (W3);
    * FR-6's A5'', fr6-a5pp-v1 (a5pp_acceptance_fixtures): cells.operator.species_regulated_availability@1
      with cells.regulation.hill_regulated_two_state@1, two cells' K-leak populations driven through the state
      from the per-cell prior s0 = 0.1 and 0.8, the same regulator dose by turnover@1, at 1 ms.

    The unscheduled worlds run over their first five steps. §18 asks for the judged worlds' first
    few steps; a world with a schedule change after time 0 keeps its registered horizon instead,
    since the operators refuse a change outside the horizon (the lead accepted this, 18 November
    2026). crossrev runs nothing, so the horizon enters the records only through the schedule's
    times: over their first five steps, the unscheduled worlds' records equal their registered
    horizons' (measured at b5d3faf0)."""
    from validation.tissue import a5pp_acceptance_fixtures as a5pp
    from validation.tissue import bath_schedule_fixtures as bath
    from validation.tissue import compartment_acceptance_fixtures as compartment
    from validation.tissue import site_occupancy_acceptance_fixtures as occupancy

    return {
        "fr1_load_and_degrade": _first_steps(compartment.load_and_degrade()),
        "fr1_load_and_react": _first_steps(compartment.load_and_react()),
        "fr3_q5_inward": _first_steps(occupancy.registered_world("q5_inward")),
        "fr3_q5_class_switch": occupancy.registered_world("q5_class_switch"),
        "fr10_ion": bath.ion_world(),
        "fr10_ledger": bath.ledger_world(),
        "fr6_a5pp": a5pp.registered_world(),
    }


REPLICATION = (
    "linear_norton",
    "linear_as_written",
    "neither_line",
    "neither_sheet",
    "neither_ladder",
)
REPLICATION_LADDER_D_M2_S = 5e-14  # The ladder's top point (gap-junction-20261117/runs/ladder-01).


def replication_world(name, *, junction_scale=1.0, d=None):
    """One world of the replication set (replication_worlds), built by its driver's own generator at
    its registered horizon and cut to its first five steps. junction_scale multiplies every junction
    permeability of the linear model (the driver's planted control, K1); d is a neither world's
    junction diffusion constant (m^2/s), by default its registered one."""
    from validation.gap_junction_tissue import neither
    from validation.gap_junction_tissue import worlds as gj

    if name in ("linear_norton", "linear_as_written"):
        chain = gj.chain(3, 0.5)
        if name == "linear_norton":
            raw = gj.linear_network(
                chain.cells, chain.edges, chain.probes, junction_scale=junction_scale
            )
        else:
            raw = gj.as_written(chain, junction_scale=junction_scale)
        return _first_steps(raw)
    registered = {
        "neither_line": (neither.X2_M2_S, "line"),
        "neither_sheet": (neither.X2_M2_S, "sheet"),
        "neither_ladder": (REPLICATION_LADDER_D_M2_S, "line"),
    }
    default, shape = registered[name]
    d = default if d is None else d
    return _first_steps(neither.coupled_world(d, neither.STAGE1_END_UNITS, shape=shape))


def replication_worlds():
    """Quick worlds of the gap-junction replication (docs/GAP_JUNCTION_CANCER_REPLICATION.md, D219),
    each built by its driver's generator (validation/gap_junction_tissue/) and cut to its first five
    steps. They carry the replication's two neutral transport laws: @3's neutral permeant species
    and the passive routes' neutral law on a junction host.

    * The linear model on Figure 8's chain of three cells, G_GJ = G_eq, its port loaded by a
      reservoir held at 0.5 (the first of the two loads its Norton conductance is measured from),
      in both of its forms:
      - linear_norton: cells.model.resolved_pump_tissue@3's own cells.route.constant_field@1 membranes and junctions for
        one neutral permeant species, with held reservoirs (worlds.linear_network);
      - linear_as_written: cells.model.resolved_pump_composite@1 over @3, cells.operator.local_species_reactions@1's source
        and decay in each cell, and cells.route.passive_neutral_permeation@1 routes on the junctions and on
        the probe's patch (worlds.as_written).
    * The neither condition's coupled stage (neither.coupled_world): the EMT switch as
      cells.operator.local_species_reactions@1 reactions, with miR200 on cells.route.passive_neutral_permeation@1 junction
      routes. Each starts from stage 1's pinned end state (neither.STAGE1_END_UNITS), since
      crossrev runs nothing:
      - neither_line: BITSEY's 1x1x25 line at the 1D search's threshold x2 (step 1/8 s);
      - neither_sheet: the 9x9 sheet of section 7.6 at x2 (1/16 s);
      - neither_ladder: the line at the ladder's top point, 5e-14 m^2/s (1/32 s).
    Every junction gate is cells.junction.junction_voltage_relaxation@1, pinned open.

    The set has its own record (replication_jaxprs, replication_bindings), which closes two blind
    spots of the other sets' (an external review, 18 November 2026): it records each schedule
    change's step and every step's controls, so a change one step later moves the record; and it
    traces the device row checks of a transition, the previous and the current state independent
    inputs, beside production's window check program."""
    return {name: replication_world(name) for name in REPLICATION}


def _replication_traced(spec, model, arrays):
    """Closed jaxprs of the replication set's programs, each traced on the inputs production gives
    it: the checked step and the right-hand side (as _traced); the device row checks of one
    transition, with the previous and the current state independent inputs and the accepted-step
    count traced, margins off and on (row_checks' scalar windows run them on); and production's own
    window check program, row_checks._window_checks, over a window of two rows. A change that makes
    the checks compare a row with itself therefore changes the record."""
    import functools

    import jax
    import jax.numpy as jnp

    from cells.execution import row_checks

    s, c, p = arrays
    dt = jnp.asarray(spec.execution.dt)  # Traced, as in the runner's rollout.
    first = jnp.asarray(0, dtype=jnp.int64)  # The accepted-step count, traced as the windows do.
    count = jnp.asarray(1, dtype=jnp.int64)
    constants = model.device_check_constants(spec)
    history = jax.tree.map(lambda x: jnp.stack([x, x]), s)

    def step(s, dt, c, q):
        return model.checked_step(s, dt, c, q, q.active)

    def rhs(s, c, q):
        return model.rhs(s, c, q, q.active)

    def checks(previous, row, q, steps):
        return model.device_checks(previous, row, q, constants, steps)

    def checks_margins(previous, row, q, steps):
        return model.device_checks(previous, row, q, constants, steps, margins=True)

    window = functools.partial(row_checks._window_checks, checks=model.device_checks)
    return dict(
        checked_step=jax.make_jaxpr(step)(s, dt, c, p),
        rhs=jax.make_jaxpr(rhs)(s, c, p),
        device_checks=jax.make_jaxpr(checks)(s, s, p, first),
        device_checks_margins=jax.make_jaxpr(checks_margins)(s, s, p, first),
        window_checks=jax.make_jaxpr(window)(s, history, count, first, p, constants),
    )


def replication_jaxprs(directory):
    """jaxprs for the replication set: _replication_traced's five programs of each world."""
    import jax

    jax.config.update("jax_enable_x64", True)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, raw in replication_worlds().items():
        for kind, closed in _replication_traced(*_setup(raw)).items():
            (directory / f"{name}.{kind}.txt").write_text(str(closed))
            (directory / f"{name}.{kind}.consts.json").write_text(const_record(closed))
        print(name, flush=True)


def replication_bindings(directory):
    """bindings for the replication set. As bindings, each world's initial state, layout and
    device-check constants (state., layout., check.); in place of the controls at the change times,
    the schedule's timing:
    * steps.control.FIELD: every control array at the start of every integration step, as the
      runner binds them (control_values at the EventGrid's boundaries), so that a change one step
      later moves a row;
    * steps.dt: each step's size (runner.integration_steps);
    * timing.grid: the EventGrid's boundaries; timing.change_time and timing.change_step: each
      schedule change's time and its boundary's index (EventGrid.exact_index); timing.event_index:
      the change in force at each step's start (schedule.event_index)."""
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.definitions.specs import parse_spec
    from cells.execution.grid import EventGrid
    from cells.execution.runner import integration_steps
    from cells.execution.schedule import control_values, event_index
    from cells.registry.models import get_model

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, raw in replication_worlds().items():
        spec = parse_spec(raw)
        model = get_model(spec.model)
        state, layout = model.initial_values(spec)
        grid = EventGrid(spec)
        times = np.array([grid[i] for i in range(len(grid))], dtype=np.float64)
        changes = [change.time for change in spec.experiment.changes]
        arrays = {}
        for prefix, tree in (
            ("state.", state),
            ("layout.", layout),
            ("steps.control.", control_values(spec, times[:-1])),
        ):
            for key, value in tree._asdict().items():
                arrays[prefix + key] = np.asarray(value)
        arrays["steps.dt"] = np.asarray(integration_steps(spec, times), dtype=np.float64)
        arrays["timing.grid"] = times
        arrays["timing.change_time"] = np.asarray(changes, dtype=np.float64)
        arrays["timing.change_step"] = np.asarray(
            [grid.exact_index(t) for t in changes], dtype=np.int64
        )
        arrays["timing.event_index"] = np.asarray(
            [event_index(spec, float(t)) for t in times[:-1]], dtype=np.int64
        )
        for key, value in check_constants(model, spec):
            arrays["check." + key] = value
        np.savez(directory / f"{name}.npz", **arrays)
        print(name, len(arrays), flush=True)


def _worlds(world_set, all_steps):
    if world_set == "base":
        return worlds()
    if world_set == "qualification":
        return qualification_worlds(all_steps)
    if world_set == "injection":
        return injection_worlds()
    if world_set == "volume":
        return volume_worlds()
    if world_set == "kinds":
        return kinds_worlds()
    if world_set == "acceptances":
        return acceptances_worlds()
    if world_set == "replication":
        return replication_worlds()
    raise SystemExit(
        f"Unknown world set {world_set!r} "
        "(base, qualification, injection, volume, kinds, acceptances or replication)"
    )


def _setup(raw):
    import jax
    import jax.numpy as jnp

    from cells.definitions.specs import parse_spec
    from cells.execution.schedule import control_values
    from cells.registry.models import get_model

    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    controls = control_values(spec, [0.0])
    control = type(controls)(*(np.asarray(v[0]) for v in controls))
    return spec, model, jax.tree.map(jnp.asarray, (state, control, p))


def jaxprs(directory, world_set="base"):
    if world_set == "replication":  # Its own programs (replication_jaxprs).
        return replication_jaxprs(directory)
    import jax

    jax.config.update("jax_enable_x64", True)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, raw in _worlds(world_set, all_steps=False).items():
        for kind, closed in _traced(*_setup(raw)).items():
            (directory / f"{name}.{kind}.txt").write_text(str(closed))
            (directory / f"{name}.{kind}.consts.json").write_text(const_record(closed))
        print(name, flush=True)


def _traced(spec, model, arrays):
    """Closed jaxprs of the checked step, right-hand side and device row checks."""
    import jax
    import jax.numpy as jnp

    s, c, p = arrays
    dt = jnp.asarray(spec.execution.dt)  # Traced, as in the runner's rollout.
    constants = model.device_check_constants(spec)

    def step(s, dt, c, q):
        return model.checked_step(s, dt, c, q, q.active)

    def rhs(s, c, q):
        return model.rhs(s, c, q, q.active)

    def checks(s, q):
        return model.device_checks(s, s, q, constants, 3)

    def checks_margins(s, q):  # The scalar windows' device checks (WindowPolicy row_checks).
        return model.device_checks(s, s, q, constants, 3, margins=True)

    return dict(
        checked_step=jax.make_jaxpr(step)(s, dt, c, p),
        rhs=jax.make_jaxpr(rhs)(s, c, p),
        device_checks=jax.make_jaxpr(checks)(s, p),
        device_checks_margins=jax.make_jaxpr(checks_margins)(s, p),
    )


def closed_consts(closed):
    """Every constant a closed jaxpr holds, at any depth, in tracing order, each once.

    The parameters that hold jaxprs (jit, scan, cond branches) are visited. JAX 0.11's
    make_jaxpr returns a closed jaxpr that may be its own .jaxpr, so an object's equations
    are walked even after its constants are taken.
    """
    found, seen, taken = [], set(), set()

    def visit(value):
        if isinstance(value, (tuple, list)):
            for item in value:
                visit(item)
            return
        if not (hasattr(value, "eqns") or hasattr(value, "jaxpr")) or id(value) in seen:
            return
        seen.add(id(value))
        for const in getattr(value, "consts", None) or ():
            if id(const) not in taken:
                taken.add(id(const))
                found.append(const)
        inner = getattr(value, "jaxpr", None)
        if inner is not None and inner is not value:
            visit(inner)
        for eqn in getattr(value, "eqns", None) or ():
            for param in eqn.params.values():
                visit(param)

    visit(closed)
    return found


def const_record(closed):
    """Canonical JSON of the dtype, shape and SHA-256 of each closed-over constant."""
    rows = []
    for const in closed_consts(closed):
        array = np.ascontiguousarray(np.asarray(const))
        digest = hashlib.sha256(array.tobytes()).hexdigest()
        rows.append(dict(dtype=str(array.dtype), shape=list(array.shape), sha256=digest))
    return json.dumps(dict(count=len(rows), consts=rows), indent=1, sort_keys=True) + "\n"


def check_constants(model, spec):
    """(name, array) of the model's device-check constants; none for a model without them."""
    import jax

    if not hasattr(model, "device_check_constants"):
        return []
    leaves, _ = jax.tree_util.tree_flatten_with_path(model.device_check_constants(spec))
    return [(jax.tree_util.keystr(path).lstrip("."), np.asarray(leaf)) for path, leaf in leaves]


def bindings(directory, world_set="base"):
    if world_set == "replication":  # Its own record, with the schedule's timing.
        return replication_bindings(directory)
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.definitions.specs import parse_spec
    from cells.execution.schedule import control_values
    from cells.registry.models import get_model

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, raw in _worlds(world_set, all_steps=True).items():
        spec = parse_spec(raw)
        model = get_model(spec.model)
        state, layout = model.initial_values(spec)
        times = sorted({0.0, *(c.time for c in spec.experiment.changes), spec.experiment.end_time})
        arrays = {}
        for prefix, tree in (
            ("state.", state),
            ("layout.", layout),
            ("control.", control_values(spec, times)),
        ):
            for key, value in tree._asdict().items():
                arrays[prefix + key] = np.asarray(value)
        for key, value in check_constants(model, spec):
            arrays["check." + key] = value
        np.savez(directory / f"{name}.npz", **arrays)
        print(name, len(arrays), flush=True)


def compare(a, b):
    """Print each saved item's verdict; True when every item is identical.

    Every jaxpr text of A is compared with B's, and so are its constants. If neither side
    recorded a text's constants (outputs from before they were recorded), that is
    reported and the verdict covers the texts and bindings only. If only one side recorded
    them, they differ.
    """
    a, b = Path(a), Path(b)
    same, unrecorded = True, 0
    counts = {"jaxpr texts": [0, 0], "constants": [0, 0], "bindings": [0, 0]}
    for path in sorted(a.glob("*.txt")):
        other = b / path.name
        equal = other.exists() and path.read_text() == other.read_text()
        same &= equal
        counts["jaxpr texts"][0] += equal
        counts["jaxpr texts"][1] += 1
        print(path.name, "identical" if equal else "DIFFERS")
        mine = a / (path.name[: -len(".txt")] + ".consts.json")
        theirs = b / mine.name
        if not mine.exists() and not theirs.exists():
            unrecorded += 1
            continue
        both = mine.exists() and theirs.exists()
        equal = both and json.loads(mine.read_text()) == json.loads(theirs.read_text())
        same &= equal
        counts["constants"][0] += equal
        counts["constants"][1] += 1
        print(mine.name, "identical" if equal else "DIFFERS" + ("" if both else " (one side)"))
    for path in sorted(a.glob("*.npz")):
        counts["bindings"][1] += 1
        if not (b / path.name).exists():
            same = False
            print(path.name, "DIFFERS (missing in", b, ")")
            continue
        x, y = np.load(path), np.load(b / path.name)
        names = set(x.files) | set(y.files)
        diffs = [
            k
            for k in sorted(names)
            if k not in x.files
            or k not in y.files
            or x[k].dtype != y[k].dtype
            or x[k].shape != y[k].shape
            or x[k].tobytes() != y[k].tobytes()
        ]
        same &= not diffs
        counts["bindings"][0] += not diffs
        print(path.name, "identical" if not diffs else f"DIFFERS {diffs[:8]}", len(names))
    if unrecorded:
        print("constants not recorded on either side for", unrecorded, "texts")
    print("summary", ", ".join(f"{k} {n} of {m} identical" for k, (n, m) in counts.items()))
    note = " (texts and bindings; constants not recorded)" if unrecorded and same else ""
    print("verdict", ("identical" if same else "differs") + note)
    return same


if __name__ == "__main__":
    action = sys.argv[1]
    if action == "jaxprs":
        jaxprs(*sys.argv[2:4])
    elif action == "bindings":
        bindings(*sys.argv[2:4])
    else:
        sys.exit(0 if compare(sys.argv[2], sys.argv[3]) else 1)
