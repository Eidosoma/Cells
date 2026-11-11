"""resolved_pump_replacement@1: scheduled cell replacement on resolved_pump_tissue@3.

* Without events (every junction formed), the model reproduces @3 bitwise: every
  @3 state field, observation and check diagnostic, compiled (IMEX Euler and
  ARS(2,2,2)) and uncompiled; the replacement fields stay zero.
* With events (one slot, two ends of a junction at once, a second generation, a D
  template), every @3 ledger closes through @3's own row checks; removal and
  supply equal the departing amounts and the template; the event is applied at
  the start of the step leaving t_e; the formation law is the closed form.
* A checkpoint before, at or after an event restarts bitwise.
* Faults in the supply, charge, energy or generation bookings are refused, host and
  device alike.
* Definitions off the grid, creating routes, on floating components and the like
  are refused.
"""

import jax
import numpy as np
import pytest

from cells.core.cell_replacement_spec import exact_event_times
from cells.core.errors import NumericalError
from cells.core.runner import run
from cells.core.specs import ConfigError, parse_spec
from cells.models import cell_replacement as model
from cells.models import surface_pump_v3
from cells.models.surface_pump_checks import CheckConstants
from cells.numerics import surface_imex as imex
from cells.processes import junction_formation as formation
from cells.processes import junction_gate
from cells.processes.electrochemistry import CHARGE_PER_FMOL
from validation.tissue import cell_replacement_fixtures as fx
from validation.tissue import surface_pump_v3_fixtures as v3fx

DT = 1e-3
STEPS = 50
END = STEPS * DT
T1, T2, T3 = exact_event_times((10, 20, 30), DT)
OBSERVED = exact_event_times((0, 10, 11, 30, 31, STEPS), DT)


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def sheet(solver=imex.ARS222_ID, end=END):
    raw = fx.heredity_sheet(1, 0, dt=DT, end_time=end, solver=solver)
    raw["experiment"]["observation_times"] = [t for t in OBSERVED if t <= end]
    return raw


def templates(raw):
    return [fx.template_from_cell(raw, "cell_1", "h"), fx.template_from_cell(raw, "cell_3", "d")]


EVENTS = (
    (T1, "cell_0", "h", "n1"),
    (T2, "cell_2", "h", "n2"),
    (T2, "cell_5", "h", "n3"),  # Junction (2, 5): both ends at once.
    (T3, "cell_0", "d", "n4"),  # Second generation of cell_0, from a D state.
    (T3, "cell_3", "h", "n5"),  # Junction (0, 3): both ends at once.
)


def replaced(solver=imex.ARS222_ID, events=EVENTS, **kw):
    raw = sheet(solver)
    return parse_spec(fx.with_replacement(raw, templates(raw), events, **kw))


@pytest.fixture(scope="module")
def runs():
    raw = sheet()
    return dict(
        base=run(parse_spec(raw)),
        events=run(replaced()),
    )


# ------------------------------------------------------------------ law


def test_formation_advance_is_the_closed_form():
    p = formation.Parameters(0.2, 0.3, 50.0)
    lag, deficit = formation.arrival(p, xp=np)
    age = 0.0
    for h in (0.1, 0.15, 0.1, 2.0, 17.0, 0.0):
        lag, deficit = formation.advance(lag, deficit, h, p, xp=np)
        age += h
        assert abs(formation.abundance(deficit) - formation.closed_form(age, p, xp=np)) < 1e-15
    assert formation.advance(0.0, 0.0, 5.0, p, xp=np) == (0.0, 0.0)


# ------------------------------------------------------------------ definition


def test_definition_round_trip_and_light_schedule_records():
    spec = replaced()
    assert parse_spec(spec.to_dict()) == spec
    changes = spec.experiment.changes
    assert [c.time for c in changes] == [0.0, T1, T2, T3]
    assert [len(c.events) for c in changes] == [0, 1, 2, 2]
    assert all(c.inner is changes[0].inner for c in changes)  # Shared, not re-tabulated.
    control = model.control_values(spec, [0.0, T1 - DT, T1, T3])
    assert control.generation[:, 0].tolist() == [0, 0, 1, 2]
    assert control.template[:, 0].tolist() == [0, 0, 1, 2]
    assert control.generation[:, 3].tolist() == [0, 0, 0, 1]


@pytest.mark.parametrize(
    "change, message",
    [
        (lambda r: r["experiment"]["replacement_events"][0].update(time=0.0105), "strictly inside"),
        (lambda r: r["experiment"]["replacement_events"][0].update(time=0.0), "strictly inside"),
        (lambda r: r["experiment"]["replacement_events"][0].update(time=END), "strictly inside"),
        (lambda r: r["experiment"]["replacement_events"][1].update(slot="cell_0", time=T1), "one"),
        (lambda r: r["experiment"]["replacement_events"][0].update(template="x"), "declared"),
        (lambda r: r["experiment"]["replacement_events"][1].update(carrier_id="n1"), "unique"),
        (lambda r: r["experiment"]["replacement_events"][0].update(carrier_id="cell_4"), "unique"),
        (lambda r: r["model"]["replacement"]["templates"][0].update(volume_pL=1.0), "volume"),
        (
            lambda r: r["model"]["replacement"]["templates"][0]["route_values"][
                "membrane_permeability_m_per_s"
            ].update(P=1e-9),
            "create",
        ),
        (
            lambda r: r["model"]["replacement"]["templates"][0]["route_values"].update(
                calcium_pump_capacity_fmol_per_s_m2=1.0
            ),
            "create",
        ),
        (lambda r: r["model"]["replacement"]["templates"][0]["channel_gates"].clear(), "gates"),
        (
            lambda r: r["model"]["replacement"]["junction_formation"].update(time_constant_s=10.0),
            "40",
        ),
        (
            lambda r: r["model"]["replacement"]["junction_formation"].update(
                gate_at_arrival="kept"
            ),
            "gate_at_arrival",
        ),
        (lambda r: r["model"]["replacement"].update(template_capacity=1), "template_capacity"),
    ],
)
def test_invalid_definitions_are_refused(change, message):
    raw = sheet()
    raw = fx.with_replacement(raw, templates(raw), EVENTS)
    change(raw)
    with pytest.raises(ConfigError, match=message):
        parse_spec(raw)


def test_template_route_values_select_the_occupant_parameters():
    raw = sheet()
    t = fx.template_from_cell(raw, "cell_1", "h")
    t["route_values"]["channel_permeability_m_per_s"] = {"nav1p2_m3h_regularized@1": 2e-7}
    t["route_values"]["membrane_permeability_m_per_s"] = {"Na": 4e-11}
    t["route_values"]["pump_capacity_fmol_per_s_m2"] = 9e7
    spec = parse_spec(fx.with_replacement(raw, [t], [(T1, "cell_0", "h", "n1")]))
    state, p = model.initial_values(spec)
    after = state._replace(occupant_template=np.where(np.arange(7) == 0, 1, 0))
    view = model.ionic_layout(p, after, xp=np)
    nav = [i for i, c in enumerate(spec.model.channels) if c.id == "nav_0"][0]
    other = [i for i, c in enumerate(spec.model.channels) if c.id == "nav_1"][0]
    assert view.channel_permeability[nav] == 2e-7
    assert view.channel_permeability[other] == p.channel_permeability[other]
    assert view.membrane_permeability[0, 0] == 4e-11
    assert view.membrane_permeability[1, 0] == p.membrane_permeability[1, 0]
    assert view.pump_capacity[0] == 9e7 * p.membrane_area[0]
    assert np.array_equal(model.ionic_layout(p, state, xp=np).pump_capacity, p.pump_capacity)


# ------------------------------------------------------------------ no events


def assert_reproduces(reference, result):
    np.testing.assert_array_equal(result.times, reference.times)
    for key in surface_pump_v3.STATE_TYPE._fields:
        a, b = np.asarray(getattr(result.history, key)), np.asarray(getattr(reference.history, key))
        assert a.shape == b.shape and np.array_equal(a, b), key
    for key in model.REPLACEMENT_STATE_AXES:
        assert not np.any(np.asarray(getattr(result.history, key))), key
    for key, value in vars(reference.observations).items():
        assert np.array_equal(np.asarray(getattr(result.observations, key)), value), key
    for key, value in reference.diagnostics.items():
        if key.startswith("max_"):
            assert result.diagnostics[key] == value, key


@pytest.mark.parametrize("solver", (imex.EULER_ID, imex.ARS222_ID))
def test_without_events_reproduces_resolved_pump_tissue_3_bitwise(solver):
    raw = sheet(solver)
    assert_reproduces(run(parse_spec(raw)), run(parse_spec(fx.with_replacement(raw))))


def test_without_events_uncompiled_reproduces_resolved_pump_tissue_3_bitwise():
    raw = sheet(end=8 * DT)
    raw["experiment"]["observation_times"] = [0.0, 8 * DT]
    raw["execution"]["jit"] = False
    assert_reproduces(run(parse_spec(raw)), run(parse_spec(fx.with_replacement(raw))))


# ------------------------------------------------------------------ events


def row(result, time):
    return int(np.flatnonzero(result.times == time)[0])


def test_events_close_every_ledger_through_the_inner_checks(runs):
    result = runs["events"]
    h = result.history
    assert np.asarray(h.generation)[-1].tolist() == [2, 0, 1, 1, 0, 1, 0]
    assert np.asarray(h.occupant_template)[-1].tolist() == [2, 0, 1, 1, 0, 1, 0]
    # run() already applied the host checks; repeat them with explicit step counts.
    steps = list(range(len(result.times)))
    diagnostics = model.check_values(h, result.spec, steps)
    assert diagnostics["max_balance_error_fmol"] < 1e-12
    # The energy residual is the IMEX scheme's own (the event-free run's is larger here).
    base = runs["base"].diagnostics["max_energy_balance_error_pJ"]
    assert diagnostics["max_energy_balance_error_pJ"] <= base


@pytest.mark.parametrize("gate", ("law_open", "law_steady"))
def test_the_event_map_leaves_every_ledger_unchanged(runs, gate):
    """Applied to an accepted mid-run row, the event map changes no ledger residual."""
    rule = dict(fx.FORMATION, gate_at_arrival=gate)
    spec = replaced(formation=rule)
    result = runs["events"]
    p = model.initial_values(spec)[1]
    k = row(result, T3)
    before = model.STATE_TYPE(*(np.asarray(v[k]) for v in result.history))
    control = model.Control(*(np.asarray(v[0]) for v in model.control_values(spec, [T3])))
    after, ok = model.apply_events(before, control, p, xp=np)
    assert ok and after.generation.tolist() == [2, 0, 1, 1, 0, 1, 0]
    b0, b1 = model.balances(before, p), model.balances(after, p)
    # Rounding of whole-content terms: amounts (fmol), charges and free energies.
    eps = 64 * np.finfo(float).eps
    moved = after.replacement_removed_fmol + after.replacement_supplied_fmol
    charge = CHARGE_PER_FMOL * np.sum(np.abs(np.asarray(p.valence)) * moved)
    energy = np.sum(after.replacement_energy_magnitude_pJ)
    tolerances = dict(
        local=eps * np.max(moved),
        total=eps * np.max(moved),
        energy=eps * energy,
        global_charge=eps * charge,
        electrode=0.0,
        charge=0.0,
    )
    for name, tolerance in tolerances.items():
        assert np.max(np.abs(np.asarray(b1[name]) - np.asarray(b0[name]))) <= tolerance, name
    image = np.asarray(after.electrode_charge_transferred_C - before.electrode_charge_transferred_C)
    assert np.any(image != 0)  # The held baths' image charge is booked.


def test_removal_and_supply_book_the_departing_and_template_amounts(runs):
    result, spec = runs["events"], runs["events"].spec
    h, p = result.history, model.initial_values(spec)[1]
    amounts = np.asarray(p.amount_reference) + np.asarray(h.amount_increment)
    k1, k3 = row(result, T1), row(result, T3)
    t_h = np.asarray(spec.model.replacement.templates[0].amounts_fmol)
    t_d = np.asarray(spec.model.replacement.templates[1].amounts_fmol)
    removed = np.asarray(h.replacement_removed_fmol)
    supplied = np.asarray(h.replacement_supplied_fmol)
    assert np.array_equal(removed[k1 + 1, :, 0], amounts[k1, :, 0])  # The departing carrier.
    assert np.array_equal(supplied[k1 + 1, :, 0], t_h)
    assert np.array_equal(removed[k3 + 1, :, 0], amounts[k1, :, 0] + amounts[k3, :, 0])
    assert np.array_equal(supplied[k3 + 1, :, 0], t_h + t_d)
    assert not np.any(removed[: k1 + 1])  # Nothing before the step leaving t_e.


def test_event_rows_and_formation_follow_the_declared_semantics(runs):
    base, result = runs["base"], runs["events"]
    k1 = row(result, T1)
    for key in surface_pump_v3.STATE_TYPE._fields:  # Identical up to the row at t_e.
        a, b = np.asarray(getattr(result.history, key)), np.asarray(getattr(base.history, key))
        assert np.array_equal(a[: k1 + 1], b[: k1 + 1]), key
    deficit = np.asarray(result.history.junction_abundance_deficit)
    lag = np.asarray(result.history.junction_lag_remaining_s)
    edges = [
        k for k, j in enumerate(result.spec.model.junctions) if "cell_0" in (j.sender, j.receiver)
    ]
    assert np.all(deficit[k1 + 1, edges] == 1.0) and np.all(deficit[k1, edges] == 0.0)
    assert np.allclose(lag[k1 + 1, edges], 600.0 - DT, rtol=0, atol=1e-12)
    observed = result.observations.junction_abundance
    assert observed.shape[1] == len(result.spec.model.junctions)


def test_formation_follows_the_closed_form_in_a_run():
    formation_ = dict(fx.FORMATION, initial_abundance=0.25, lag_s=0.0, time_constant_s=40.0)
    result = run(replaced(events=((T1, "cell_0", "h", "n1"),), formation=formation_))
    k1 = row(result, T1)
    edge = [
        k for k, j in enumerate(result.spec.model.junctions) if "cell_0" in (j.sender, j.receiver)
    ]
    age = result.times[k1 + 1 :] - T1
    expected = formation.closed_form(age, formation.Parameters(0.25, 0.0, 40.0), xp=np)
    got = 1 - np.asarray(result.history.junction_abundance_deficit)[k1 + 1 :, edge[0]]
    assert np.max(np.abs(got - expected)) < 1e-14


def test_law_steady_sets_the_gate_steady_state_at_the_post_event_voltage():
    steady = dict(fx.FORMATION, initial_abundance=1.0, lag_s=0.0, gate_at_arrival="law_steady")
    spec = replaced(events=((T1, "cell_3", "h", "n1"),), formation=steady)
    state, p = model.initial_values(spec)
    control = model.Control(*(np.asarray(v[0]) for v in model.control_values(spec, [T1])))
    after, ok = model.apply_events(state, control, p, xp=np)
    assert ok
    v = model.field_values(after, control, p, xp=np).rates.junction_voltage_V
    target = junction_gate.kinetics(
        v, junction_gate.Parameters(p.junction_threshold_voltage, p.junction_minimum), xp=np
    ).target
    edge = np.asarray(p.junction_sender == 3) | np.asarray(p.junction_receiver == 3)
    assert np.allclose(after.junction_gate[edge], target[edge], rtol=0, atol=1e-15)
    assert np.array_equal(after.junction_gate[~edge], state.junction_gate[~edge])


@pytest.mark.parametrize("time", (T1 - DT, T1, T1 + DT))
def test_restart_at_an_event_is_bitwise(runs, time):
    result = runs["events"]
    restarted = run(result.spec, result.checkpoint_at(time))
    k = row(result, time)
    for key in model.STATE_TYPE._fields:
        a = np.asarray(getattr(restarted.history, key))
        b = np.asarray(getattr(result.history, key))[k:]
        assert np.array_equal(a, b), key


def test_the_event_map_sets_the_law_open_gate_and_the_template_state():
    spec = replaced(events=((T1, "cell_0", "h", "n1"),))
    state, p = model.initial_values(spec)
    control = model.Control(*(np.asarray(v[0]) for v in model.control_values(spec, [T1])))
    after, ok = model.apply_events(state, control, p, xp=np)
    assert ok
    edge = np.asarray(p.junction_sender == 0) | np.asarray(p.junction_receiver == 0)
    params = junction_gate.Parameters(p.junction_threshold_voltage, p.junction_minimum)
    opened = junction_gate.kinetics(np.zeros_like(p.junction_threshold_voltage), params, xp=np)
    assert np.array_equal(after.junction_gate[edge], opened.target[edge])
    assert np.array_equal(after.junction_gate[~edge], state.junction_gate[~edge])
    template = spec.model.replacement.templates[0]
    amounts = np.asarray(p.amount_reference) + after.amount_increment
    assert np.allclose(amounts[:, 0], template.amounts_fmol, rtol=1e-15, atol=0)
    own = [i for i, c in enumerate(spec.model.channels) if c.membrane_id == "membrane_0"]
    donor = [i for i, c in enumerate(spec.model.channels) if c.membrane_id == "membrane_1"]
    assert np.array_equal(after.channel_gate[:, own], state.channel_gate[:, donor])
    assert np.all(after.junction_abundance_deficit[edge] == 1.0)
    assert after.generation.tolist() == [1, 0, 0, 0, 0, 0, 0]


def test_held_components_are_found_on_the_capacitor_graph():
    from types import SimpleNamespace

    # Nodes 0, 1 cells; 2, 3 outside. 0-2 with bath 2; 1-3 floating (3 a gauge, not a bath).
    c = np.zeros((4, 4))
    c[0, 2] = c[2, 0] = c[1, 3] = c[3, 1] = -1.0
    layout = SimpleNamespace(
        field_capacitor_matrix=c,
        field_fixed=np.array([False, False, True, True]),
        field_active=np.ones(4, dtype=bool),
        active=np.ones(2, dtype=bool),
        reservoir=np.array([True, False]),
    )
    assert model.held_cells(layout).tolist() == [True, False]


def test_a_schedule_mismatch_refuses_the_step():
    spec = replaced(events=((T1, "cell_0", "h", "n1"),))
    state, p = model.initial_values(spec)
    control = model.Control(*(np.asarray(v[0]) for v in model.control_values(spec, [T1])))
    bad = control._replace(generation=np.where(np.arange(7) == 0, 2, 0))
    assert not model.apply_events(state, bad, p, xp=np)[1]


# ------------------------------------------------------------------ faults


FAULTS = {
    "supply": ("replacement_supplied_fmol", lambda v: v * (1 + 1e-6), "local"),
    "charge": ("replacement_charge_C", lambda v: v + 1e-18, "global_charge"),
    "energy": ("replacement_free_energy_pJ", lambda v: v + 1.0, "energy"),
    "generation": ("generation", lambda v: v + 5, "domain"),
}


@pytest.mark.parametrize("fault", FAULTS)
def test_faults_are_refused_on_host_and_device(runs, fault):
    name, corrupt, check = FAULTS[fault]
    result = runs["events"]
    h, p = result.history, model.initial_values(result.spec)[1]
    k = row(result, T3) + 1
    rows = [model.STATE_TYPE(*(np.asarray(v[i]) for v in h)) for i in (k - 1, k)]
    value = np.array(getattr(rows[1], name), copy=True)
    value[..., 0] = corrupt(value[..., 0])
    bad = rows[1]._replace(**{name: value})
    with pytest.raises(NumericalError):
        model.check_values(bad, result.spec, [k])
    constants = CheckConstants(*(np.asarray(v) for v in model.device_check_constants(result.spec)))
    failed, _ = model.device_checks(
        jax.tree.map(np.asarray, rows[0]), jax.tree.map(np.asarray, bad), p, constants, k
    )
    flags = dict(zip(model.DEVICE_CHECKS, np.asarray(failed).tolist(), strict=True))
    assert flags[check] and sum(flags.values()) >= 1
    clean, _ = model.device_checks(rows[0], rows[1], p, constants, k)
    assert not np.any(np.asarray(clean))


# ------------------------------------------------------------------ wider worlds


def reference_raw():
    """@3's padded reference world: finite outside nodes, faces, Ca pumps, a gauge and a
    mid-run channel release (IMEX ARS(2,2,2))."""
    raw = v3fx.definition("release", solver=imex.ARS222_ID)
    raw["experiment"]["end_time"] = 0.0012
    raw["experiment"]["observation_times"] = [0.0, 0.0007, 0.0012]
    return raw


def rk4_sheet():
    """The heredity sheet with RK4 at @3's NaV1.2 RK4 step bound (2.5 us), 40 steps."""
    raw = fx.heredity_sheet(1, 0, dt=2.5e-6, end_time=40 * 2.5e-6, solver="rk4")
    raw["experiment"]["observation_times"] = [0.0, 20 * 2.5e-6, 40 * 2.5e-6]
    return raw


@pytest.mark.parametrize("world", ("padded", "rk4"))
def test_without_events_reproduces_wider_worlds_bitwise(world):
    raw = reference_raw() if world == "padded" else rk4_sheet()
    assert_reproduces(run(parse_spec(raw)), run(parse_spec(fx.with_replacement(raw))))


def test_events_on_the_padded_reference_world_close_every_ledger():
    raw = reference_raw()
    dt = raw["execution"]["dt"]
    t1, t2 = exact_event_times((4, 9), dt)
    templates = [
        fx.template_from_cell(raw, "cell_0", "own_0"),
        fx.template_from_cell(raw, "cell_1", "own_1"),
    ]
    events = ((t1, "cell_0", "own_0", "n1"), (t2, "cell_0", "own_0", "n2"))
    result = run(parse_spec(fx.with_replacement(raw, templates, events)))  # Host checks.
    assert np.asarray(result.history.generation)[-1][:2].tolist() == [2, 0]
    # cell_1 faces finite outside nodes only (its component has the gauge, no bath).
    floating = ((t1, "cell_1", "own_1", "n1"),)
    with pytest.raises(ConfigError, match="held-bath"):
        parse_spec(fx.with_replacement(raw, templates, floating))


def test_events_with_rk4_close_every_ledger():
    """H newcomers in H slots (small charge displacement): see docs/CELL_REPLACEMENT.md.

    A D<->H swap displaces about 1e-12 C on the slot; @3's RK4 electrode ledger then
    exceeds its relative bound (2e-12) by a few percent within about 30 steps.
    """
    raw = rk4_sheet()
    t1, t2 = exact_event_times((4, 9), 2.5e-6)
    events = ((t1, "cell_0", "h", "n1"), (t2, "cell_0", "h", "n2"), (t2, "cell_1", "h", "n3"))
    result = run(parse_spec(fx.with_replacement(raw, templates(raw), events)))  # Host checks.
    assert np.asarray(result.history.generation)[-1].tolist() == [2, 1, 0, 0, 0, 0, 0]


def test_template_route_values_act_in_a_compiled_run():
    """A newcomer's own parameter draw: NaV1.2, Na leak and pump capacity overrides."""
    raw = sheet()
    plain = fx.template_from_cell(raw, "cell_1", "plain")
    drawn = fx.template_from_cell(raw, "cell_1", "drawn")
    drawn["route_values"].update(
        channel_permeability_m_per_s={"nav1p2_m3h_regularized@1": 3.0e-7},
        membrane_permeability_m_per_s={"Na": 8e-11},
        pump_capacity_fmol_per_s_m2=1.2e8,
    )
    results = {
        name: run(parse_spec(fx.with_replacement(raw, [t], [(T1, "cell_0", name, "n1")])))
        for name, t in (("plain", plain), ("drawn", drawn))
    }
    k = row(results["plain"], T1)
    nav = [i for i, c in enumerate(results["plain"].spec.model.channels) if c.id == "nav_0"][0]
    flux = {n: r.observations.channel_flux_fmol_s for n, r in results.items()}
    times = {n: r.observations.times for n, r in results.items()}
    after = int(np.flatnonzero(times["plain"] > T1)[0])
    assert not np.allclose(flux["plain"][after, :, nav], flux["drawn"][after, :, nav])
    for key in surface_pump_v3.STATE_TYPE._fields:  # Identical until the event.
        a = np.asarray(getattr(results["plain"].history, key))[: k + 1]
        b = np.asarray(getattr(results["drawn"].history, key))[: k + 1]
        assert np.array_equal(a, b), key


def test_law_steady_compiled_with_an_inner_schedule_change_between_events():
    raw = sheet()
    for control in raw["experiment"]["channel_controls"]:
        if control["channel_id"].startswith("nav_"):
            control["schedule"] = [
                dict(time=0.0, availability=control["schedule"][0]["availability"]),
                dict(time=T2, availability=0.5),
            ]
    steady = dict(fx.FORMATION, initial_abundance=1.0, lag_s=0.0, gate_at_arrival="law_steady")
    events = ((T1, "cell_0", "h", "n1"), (T3, "cell_3", "h", "n2"))
    spec = parse_spec(fx.with_replacement(raw, templates(raw), events, formation=steady))
    assert [c.time for c in spec.experiment.changes] == [0.0, T1, T2, T3]
    result = run(spec)  # Compiled, host-checked.
    assert np.asarray(result.history.generation)[-1].tolist() == [1, 0, 0, 1, 0, 0, 0]
    k = row(result, T3)
    state = model.STATE_TYPE(*(np.asarray(v[k]) for v in result.history))
    p = model.initial_values(spec)[1]
    control = model.Control(*(np.asarray(v[0]) for v in model.control_values(spec, [T3])))
    expected, _ = model.apply_events(state, control, p, xp=np)
    compiled = jax.jit(lambda s, c, q: model.apply_events(s, c, q))(state, control, p)[0]
    assert np.allclose(
        np.asarray(compiled.junction_gate), expected.junction_gate, rtol=0, atol=1e-14
    )


# ------------------------------------------------------------------ donor copies (D139)

FAST_NAV = dict(fx.NO_ROUTES, channel_permeability_m_per_s={"nav1p2_m3h_regularized@1": 3e-7})
DONOR_EVENTS = (
    (T1, "cell_0", None, "c1", "cell_3"),  # Copy of the D centre; the slot's own routes.
    (T2, "cell_4", "fast_nav", "c2", "cell_3"),  # Copy with a route-only template...
    (T2, "cell_3", "h", "c3"),  # ...while the donor itself is replaced at the same time.
)


def donor_spec(events=DONOR_EVENTS):
    raw = sheet()
    return parse_spec(
        fx.with_replacement(raw, [*templates(raw), fx.route_template("fast_nav", FAST_NAV)], events)
    )


@pytest.fixture(scope="module")
def donor_run():
    return run(donor_spec())


def test_donor_copy_takes_the_donor_state_before_events_at_its_time(donor_run):
    result, spec = donor_run, donor_run.spec
    h, p = result.history, model.initial_values(spec)[1]
    amounts = np.asarray(p.amount_reference) + np.asarray(h.amount_increment)
    gates = np.asarray(h.channel_gate)
    k1, k2 = row(result, T1), row(result, T2)
    chan = {c.id: i for i, c in enumerate(spec.model.channels)}
    supplied = np.asarray(h.replacement_supplied_fmol)
    assert np.array_equal(supplied[k1 + 1, :, 0], amounts[k1, :, 3])
    assert np.array_equal(supplied[k2 + 1, :, 4], amounts[k2, :, 3])  # Pre-event donor.
    state = model.STATE_TYPE(*(np.asarray(v[k2]) for v in h))
    control = model.Control(*(np.asarray(v[0]) for v in model.control_values(spec, [T2])))
    after, ok = model.apply_events(state, control, p, xp=np)
    assert ok
    for law in ("nav", "kir"):
        assert np.array_equal(
            after.channel_gate[:, chan[f"{law}_4"]], gates[k2, :, chan[f"{law}_3"]]
        )
    assert np.asarray(h.occupant_template)[-1].tolist() == [0, 0, 0, 1, 3, 0, 0]
    view = model.ionic_layout(p, after, xp=np)
    assert view.channel_permeability[chan["nav_4"]] == 3e-7
    assert view.channel_permeability[chan["nav_0"]] == p.channel_permeability[chan["nav_0"]]


def test_donor_copies_close_every_ledger_and_restart_bitwise(donor_run):
    result = donor_run
    diagnostics = model.check_values(result.history, result.spec, list(range(len(result.times))))
    assert diagnostics["max_balance_error_fmol"] < 1e-12
    for time in (T1, T2):
        restarted = run(result.spec, result.checkpoint_at(time))
        k = row(result, time)
        for key in model.STATE_TYPE._fields:
            a = np.asarray(getattr(restarted.history, key))
            assert np.array_equal(a, np.asarray(getattr(result.history, key))[k:]), key


def test_donor_copies_agree_on_host_and_device(donor_run):
    """@3's device-check comparison (test_surface_pump_v3_device_checks) on donor rows."""
    from cells.models import surface_pump
    from cells.numerics import surface_field

    result = donor_run
    h, p = result.history, model.initial_values(result.spec)[1]
    constants = model.device_check_constants(result.spec)
    rows = [model.STATE_TYPE(*(np.asarray(v[i]) for v in h)) for i in range(len(result.times))]
    check = jax.jit(lambda a, b, s: model.device_checks(a, b, p, constants, s))
    tol = np.asarray(result.spec.execution.material_balance_atol_fmol).min()
    bounds = {  # Smallest bound of each rounding residual (host bounds).
        "max_balance_error_fmol": tol,
        "max_extracellular_balance_error_fmol": tol,
        "max_global_balance_error_fmol": tol,
        "max_capacitor_charge_error_C": surface_field.CHARGE_ATOL_C,
        "max_electrode_charge_error_C": surface_field.CHARGE_ATOL_C,
        "max_global_charge_error_C": surface_pump.GLOBAL_CHARGE_ATOL_C,
        "max_reservoir_work_error_pJ": 3e-12,
        "max_electrode_work_error_pJ": 3e-12,
        "max_metabolic_work_error_pJ": 3e-12,
        "max_global_charge_bound_ratio": 1.0,
    }
    for i in range(1, len(rows)):
        failed, values = check(rows[i - 1], rows[i], i)
        assert not np.any(np.asarray(failed)), i
        host = model.check_values(rows[i], result.spec, [i])
        device = dict(zip(model.DEVICE_DIAGNOSTICS, np.asarray(values).tolist(), strict=True))
        for key, value in host.items():
            if key in bounds:
                assert abs(device[key] - value) <= 0.02 * bounds[key], (i, key)
            else:  # Energy: truncation, plus the rounding of the booked replacement terms.
                booked = 64 * np.finfo(float).eps * np.sum(rows[i].replacement_energy_magnitude_pJ)
                assert abs(device[key] - value) <= 1e-9 * abs(value) + 1e-15 + booked, (i, key)
    k = row(result, T2) + 1
    bad = rows[k]._replace(replacement_supplied_fmol=rows[k].replacement_supplied_fmol * 1.000001)
    with pytest.raises(NumericalError, match="local"):
        model.check_values(bad, result.spec, [k])
    failed, _ = check(rows[k - 1], bad, k)
    assert dict(zip(model.DEVICE_CHECKS, np.asarray(failed).tolist(), strict=True))["local"]


def test_donor_copies_are_labelled_as_an_inheritance_route(donor_run):
    records = model.summarize(donor_run.history, donor_run.diagnostics, donor_run.spec)["lineage"]
    newcomers = {r["carrier_id"]: r for r in records if not r["founder"]}
    assert newcomers["c1"]["newcomer"] == "donor_copy" and newcomers["c1"]["inheritance_route"]
    assert newcomers["c2"]["donor"] == "cell_3" and newcomers["c2"]["donor_carrier"] == "cell_3"
    assert newcomers["c3"]["newcomer"] == "isolated_template"
    assert not newcomers["c3"]["inheritance_route"]
    raw = donor_spec().to_dict()
    kinds = [e["newcomer"] for e in raw["experiment"]["replacement_events"]]
    assert kinds == ["donor_copy", "isolated_template", "donor_copy"]  # Sorted by (time, slot).


@pytest.mark.parametrize(
    "events, message",
    [
        (((T1, "cell_0", None, "c1", "cell_6"),), "shares no junction"),
        (((T1, "cell_0", None, "c1", "cell_0"),), "donor"),
        (((T1, "cell_0", "h", "c1", "cell_3"),), "route-only"),
        (((T1, "cell_0", "fast_nav", "c1"),), "full template"),
        (((T1, "cell_0", None, "c1"),), "full template"),
    ],
)
def test_invalid_donor_copies_are_refused(events, message):
    with pytest.raises(ConfigError, match=message):
        donor_spec(events)
