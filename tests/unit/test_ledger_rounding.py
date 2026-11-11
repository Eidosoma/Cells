"""Rounding in the resolved pump ledgers and the reaction_transport@1 guards.

Electrode ledger: each IMEX step books the change of the held nodes' plate charges
that its start and end charge states determine, so the ledger telescopes onto the
electrode check's reference (it drifted linearly with the step count before). It
feeds no rate. Seeded errors of physical size, a per-step electrode leak of 1e-12
of a step's transfer and a single mis-signed transfer, still fail the host and the
device checks at the same row. Global charge allows its rounding per accepted step
like the running ledgers: the seeded supply leaks now pass, and the stated
persistent-leak and one-off floors are tested. reaction_transport@1: the allowance
grows linearly with the step count at the derived worst-case rate, and the
resulting detection limit is stated. A pinned junction gate sets no gate-rate step
bound.
"""

import math

import jax
import numpy as np
import pytest

from cells.core.errors import NumericalError
from cells.core.runner import run
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.models import (
    reaction_transport,
    surface_pump,
    surface_pump_v2,
    surface_pump_v3,
    surface_tissue,
)
from cells.models.registry import get_model
from cells.numerics import surface_field
from cells.numerics import surface_imex as imex
from cells.processes.electrochemistry import CHARGE_PER_FMOL
from validation.tissue import surface_pump_v3_fixtures as fixtures

EPS = np.finfo(float).eps
ELECTRODE = ("electrode_charge_transferred_C", "electrode_work_pJ")


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def relaxing(version, *, end_time=2.0):
    """Two held-bath cells relaxing from U +-2 mV, as resolved_pump_tissue@version."""
    cells, gates = fixtures.relaxing_cells(2)
    raw = fixtures.heredity_cells(cells, end_time=end_time, gate_voltages=gates)
    if version < 3:
        raw["model"]["channels"], raw["experiment"]["channel_controls"] = [], []
        raw["execution"]["channel_capacity"] = 0
        raw = fixtures.as_pump_tissue(raw, version)
    return raw


MODELS = {1: surface_pump, 2: surface_pump_v2, 3: surface_pump_v3}


@pytest.fixture(scope="module")
def runs():
    result = {}
    for version in (1, 2, 3):
        spec = parse_spec(relaxing(version))
        value = run(spec)
        model = MODELS[version]
        history = model.STATE_TYPE(*(np.asarray(v) for v in value.history))
        _, p = model.initial_values(spec)
        result[version] = model, spec, value, history, p
    return result


@pytest.mark.parametrize("version", [1, 2, 3])
def test_electrode_ledger_telescopes_on_relaxing_held_bath_cells(version, runs):
    """2000 steps at 1 ms: the electrode residual stays at rounding, not 1e-25 C.

    Before the step booked the plate-charge change of its states, the same run
    reached about 8e-26 C per bath here (ratio 0.27 of the electrode bound) and
    grew linearly, refusing such worlds after about 35 s.
    """
    model, spec, value, history, p = runs[version]
    assert get_model(spec.model) is model
    d = value.diagnostics
    assert d["max_electrode_charge_error_C"] <= 1e-27
    assert d["max_global_charge_bound_ratio"] <= 0.05
    assert d["max_capacitor_charge_error_C"] <= 3e-25
    held = np.asarray(p.reservoir)
    assert np.all(np.abs(history.electrode_charge_transferred_C[-1, held]) > 1e-14)  # Moving.


@pytest.mark.parametrize("version", [1, 2, 3])
def test_electrode_ledger_feeds_no_rate(version):
    """A step's state does not depend on the electrode ledgers it starts from."""
    model = MODELS[version]
    spec = parse_spec(relaxing(version, end_time=0.01))
    state, p = model.initial_values(spec)
    controls = control_values(spec, [0.0])
    control = type(controls)(*(v[0] for v in controls))
    held = np.asarray(p.reservoir)
    shifted = state._replace(
        electrode_charge_transferred_C=np.where(held, 1e-12, 0.0),
        electrode_work_pJ=np.where(held, 3.0, 0.0),
    )
    a, ok_a = model.imex_step(state, 1e-3, control, p, xp=np)
    b, ok_b = model.imex_step(shifted, 1e-3, control, p, xp=np)
    assert ok_a and ok_b
    for key in model.STATE_TYPE._fields:
        if key not in ELECTRODE:
            np.testing.assert_array_equal(getattr(a, key), getattr(b, key), err_msg=key)
    increment = a.electrode_charge_transferred_C - state.electrode_charge_transferred_C
    np.testing.assert_allclose(  # Within an ulp of the 1e-12 C ledger it was added to.
        b.electrode_charge_transferred_C - shifted.electrode_charge_transferred_C,
        increment,
        rtol=0,
        atol=4e-28,
    )
    assert np.all(np.abs(increment[held]) > 0)


def device_rows(model, spec, history, p):
    previous = type(history)(*(np.concatenate((v[:1], v[:-1])) for v in history))
    checks = jax.jit(jax.vmap(model.device_checks, in_axes=(0, 0, None, None, 0)))
    steps = np.arange(len(history.amount_increment))
    failed, _ = checks(previous, history, p, model.device_check_constants(spec), steps)
    failed = np.asarray(failed)
    rows = np.flatnonzero(failed.any(axis=1))
    if not len(rows):
        return None, None
    row = int(rows[0])
    return row, model.device_failure_message(model.DEVICE_CHECKS[int(np.argmax(failed[row]))])


def host_first_failure(model, spec, history):
    """First row whose host check fails (check_values tests rows in order)."""

    def fails(j):
        try:
            model.check_values(
                type(history)(*(v[: j + 1] for v in history)), spec, steps=np.arange(j + 1)
            )
        except NumericalError as error:
            return str(error)
        return None

    rows = len(history.amount_increment)
    if fails(rows - 1) is None:
        return None, None
    low, high = 0, rows - 1  # fails(high) is set; find the first failing row.
    while low < high:
        middle = (low + high) // 2
        if fails(middle) is None:
            low = middle + 1
        else:
            high = middle
    return low, fails(low)


def seeded(history, p, fault, row, size=1e-12):
    """A copy of the history with one physical-size error from ``row`` on.

    Leaks grow by ``size`` of the largest per-step exchange at each step.
    """
    values = {k: np.array(v, copy=True) for k, v in history._asdict().items()}
    bath = int(np.flatnonzero(p.reservoir)[0])
    k = 1  # K
    rows = np.arange(len(values["amount_increment"]))
    after = np.clip(rows - row + 1, 0, None)
    if fault == "supply_leak":  # size of a step's K exchange at that bath, every step.
        step = np.max(np.abs(np.diff(values["reservoir_supplied"][:, k, bath])))
        values["reservoir_supplied"][:, k, bath] += size * step * after
    elif fault == "electrode_leak":  # size of a step's plate-charge change, every step.
        step = np.max(np.abs(np.diff(values["electrode_charge_transferred_C"][:, bath])))
        values["electrode_charge_transferred_C"][:, bath] += size * step * after
    elif fault == "mis_signed":  # One step's K membrane transfer booked with the wrong sign.
        patch = 0
        cell = int(p.membrane_cell[patch])
        moved = values["membrane_transferred"][row, k, patch]
        moved -= values["membrane_transferred"][row - 1, k, patch]
        values["amount_increment"][row:, k, cell] += 2 * moved
    return type(history)(**values)


@pytest.mark.parametrize("version", [1, 2, 3])
@pytest.mark.parametrize("fault", ["electrode_leak", "mis_signed"])
def test_seeded_errors_fail_host_and_device_at_the_same_row(version, fault, runs):
    model, spec, _, history, p = runs[version]
    row = 100
    corrupted = seeded(history, p, fault, row)
    host = host_first_failure(model, spec, corrupted)
    device = device_rows(model, spec, corrupted, p)
    assert host[0] is not None and device[0] is not None, (host, device)
    if fault == "mis_signed":  # A step fault: the same row exactly.
        assert host == device == (row, "Resolved pump accounting failed: local")
    else:
        # A growing leak crosses its bound gradually; host and device residuals
        # agree to rounding (not bitwise), so their crossing rows may differ by
        # a row or two. The leak is caught within 2 s by the same check.
        assert host[1] == device[1] and abs(host[0] - device[0]) <= 3, (host, device)
        assert row < host[0] < 2000 and host[1].endswith(("global_charge", "electrode")), host


# Supply leaks and the global-charge floors. The global-charge allowance grows by
# LEDGER_STEP_ROUNDING eps x moved charge (surface_pump.moved_charge) per accepted
# step, so a persistent supply leak is caught only above about 2.5 eps x moved
# charge per step; a one-off error must exceed (256 + 2.5 n) eps x moved charge
# + 3e-25 C after n steps. With Kir2.1 and NaV1.2 (@3) the largest per-step K
# exchange at the bath, which sizes a seed, is 11x smaller than without channels,
# so @3's seed is 1e-11 of a step and @1/@2's 1e-12.
SUPPLY_LEAK_SEED = {1: 1e-12, 2: 1e-12, 3: 1e-11}


@pytest.mark.parametrize("version", [1, 2, 3])
def test_seeded_supply_leaks_stay_below_the_global_charge_floor(version, runs):
    """The seeded supply leaks are 0.19 (@1, @2) and 0.32 (@3) of the per-step floor.

    Before the per-step allowance they failed global_charge at rows 430 and 401
    of this 2 s run (reduced sensitivity, recorded at landing). Now they stay
    below the bound (at most 0.39 and 0.53 of it), on the host and the device.
    """
    model, spec, _, history, p = runs[version]
    corrupted = seeded(history, p, "supply_leak", 100, SUPPLY_LEAK_SEED[version])
    assert host_first_failure(model, spec, corrupted) == (None, None)
    assert device_rows(model, spec, corrupted, p) == (None, None)


@pytest.mark.parametrize("version", [1, 2, 3])
def test_supply_leak_at_twice_the_per_step_floor_fails_host_and_device(version, runs):
    """A supply leak of 2 x 2.5 eps x the run's moved charge per step fails global_charge."""
    model, spec, _, history, p = runs[version]
    bath = int(np.flatnonzero(p.reservoir)[0])
    step = np.max(np.abs(np.diff(history.reservoir_supplied[:, 1, bath])))  # As seeded() sizes.
    last = type(history)(*(v[-1] for v in history))
    floor = surface_pump.LEDGER_STEP_ROUNDING * EPS * surface_pump.moved_charge(last, p)
    corrupted = seeded(history, p, "supply_leak", 100, 2 * floor / (CHARGE_PER_FMOL * step))
    host = host_first_failure(model, spec, corrupted)
    device = device_rows(model, spec, corrupted, p)
    message = surface_pump.LEDGER_MESSAGE + "global_charge"
    assert host[1] == device[1] == message and abs(host[0] - device[0]) <= 3, (host, device)
    assert 100 < host[0] < 2000, host


def test_seeded_leak_size_is_physical(runs):
    """The leaks above are 1e-12 of a real step's exchange: about 2e-27 C per step."""
    _, _, _, history, p = runs[1]
    bath = int(np.flatnonzero(p.reservoir)[0])
    supply = np.max(np.abs(np.diff(history.reservoir_supplied[:, 1, bath])))
    assert 1e-28 < 1e-12 * supply * CHARGE_PER_FMOL < 1e-25


# --- running work and material ledgers ---------------------------------------------


def test_ledger_step_allowance_states_its_detection_floor():
    """2.5 eps x n: 5.6e-13 after 1 s, 3.3e-11 after 1 min, 2.0e-9 after 1 h (dt 1 ms)."""
    assert math.isclose(surface_pump.LEDGER_STEP_ROUNDING, 2.5)
    for seconds, floor in ((1, 5.6e-13), (60, 3.3e-11), (3600, 2.0e-9)):
        n = round(seconds / 1e-3)
        assert math.isclose(surface_pump.LEDGER_STEP_ROUNDING * EPS * n, floor, rel_tol=0.02)


def metabolic_case(runs, version):
    """The run's last row, its magnitudes and the metabolic ledger's fixed bound."""
    model, spec, _, history, p = runs[version]
    row = type(history)(*(v[-1] for v in history))
    magnitudes = {1: surface_pump.pump_magnitudes, 2: surface_pump_v2.calcium_magnitudes}
    magnitude = magnitudes.get(version, surface_pump_v3.channel_magnitudes)(row, p)[-1]
    return model, spec, history, p, row, np.asarray(magnitude)


@pytest.mark.parametrize("version", [1, 2, 3])
@pytest.mark.parametrize("seconds", [1, 60, 3600])
def test_work_ledger_allowance_detects_twice_its_floor_at_each_horizon(version, seconds, runs):
    """A metabolic booking error of twice the allowance at n steps fails, half passes."""
    model, spec, history, p, row, magnitude = metabolic_case(runs, version)
    n = round(seconds / 1e-3)
    allowance = 3e-12 + surface_pump.LEDGER_STEP_ROUNDING * EPS * n * magnitude
    patch = int(np.argmax(magnitude[: row.metabolic_work_pJ.size]))  # Largest Na/K work.
    one = type(history)(*(v[-1:] for v in history))
    for factor, detected in ((2.0, True), (0.5, False)):
        work = np.array(one.metabolic_work_pJ, copy=True)
        work[0, patch] += factor * allowance[patch]
        seeded = one._replace(metabolic_work_pJ=work)
        try:
            model.check_values(seeded, spec, steps=[n])
            message = None
        except NumericalError as error:
            message = str(error)
        assert (message is not None) == detected, (factor, message)
        assert not detected or message.endswith("metabolic_work")
        # The device check gives the same verdict with the same count.
        checks = jax.jit(model.device_checks)
        row = type(seeded)(*(v[0] for v in seeded))
        failed, _ = checks(row, row, p, model.device_check_constants(spec), n)
        failed = np.asarray(failed)
        assert bool(failed.any()) == detected
        assert not detected or model.DEVICE_CHECKS[int(np.argmax(failed))] == "metabolic_work"


def seeded_charge_verdicts(runs, version, seconds, factor):
    """(host message, first failed device check) for a K supply error of factor x the allowance.

    The allowance is global charge's at the run's last row with n = seconds / 1 ms
    accepted steps. The error is charge-weighted K supply at a held bath.
    """
    model, spec, history, p, row, _ = metabolic_case(runs, version)
    n = round(seconds / 1e-3)
    moved = surface_pump.moved_charge(row, p)
    allowance = (
        surface_pump.global_charge_bound(row, p)
        + surface_pump.LEDGER_STEP_ROUNDING * EPS * n * moved
    )
    bath = int(np.flatnonzero(p.reservoir)[0])
    one = type(history)(*(v[-1:] for v in history))
    supplied = np.array(one.reservoir_supplied, copy=True)
    supplied[0, 1, bath] += factor * allowance / CHARGE_PER_FMOL  # K, z = +1.
    seeded = one._replace(reservoir_supplied=supplied)
    try:
        model.check_values(seeded, spec, steps=[n])
        message = None
    except NumericalError as error:
        message = str(error).removeprefix(surface_pump.LEDGER_MESSAGE)
    checks = jax.jit(model.device_checks)
    seeded_row = type(seeded)(*(v[0] for v in seeded))
    failed, _ = checks(seeded_row, seeded_row, p, model.device_check_constants(spec), n)
    failed = np.asarray(failed)
    device = model.DEVICE_CHECKS[int(np.argmax(failed))] if failed.any() else None
    return message, device


@pytest.mark.parametrize("version", [1, 2, 3])
@pytest.mark.parametrize("seconds", [1, 60])
def test_global_charge_allowance_detects_twice_its_floor_at_each_horizon(version, seconds, runs):
    """Global charge allows (256 + 2.5 n) eps of the moved charge: 2x fails, 0.5x passes.

    Below the material allowance at these horizons, so only the charge
    accounting sees the error; host and device agree.
    """
    for factor, expected in ((2.0, "global_charge"), (0.5, None)):
        assert seeded_charge_verdicts(runs, version, seconds, factor) == (expected, expected)


@pytest.mark.parametrize("version", [1, 2, 3])
def test_hour_scale_charge_error_is_caught_first_by_the_material_ledger(version, runs):
    """After 1 h of steps the charge allowance (2e-9 of the moved charge) exceeds one
    species' material allowance, so twice it in K supply fails the outside ledger first."""
    assert seeded_charge_verdicts(runs, version, 3600, 2.0) == ("outside", "outside")


def test_global_charge_detection_floor_is_stated():
    """(256 + 2.5 n) eps: 6.1e-13 after 1 s, 3.3e-11 after 1 min, 2.0e-9 after 1 h (1 ms)."""
    for seconds, floor in ((1, 6.1e-13), (60, 3.3e-11), (3600, 2.0e-9)):
        n = round(seconds / 1e-3)
        rounding = surface_pump.GLOBAL_CHARGE_ROUNDING + surface_pump.LEDGER_STEP_ROUNDING * EPS * n
        assert math.isclose(rounding, floor, rel_tol=0.02)


def test_work_ledger_bound_scales_with_the_row_step_count(runs):
    """Running ledgers gain 2.5 eps n x magnitude; the other bounds do not change."""
    _, spec, history, p, row, _ = metabolic_case(runs, 1)
    tol = np.asarray(spec.execution.material_balance_atol_fmol)
    magnitudes = surface_pump.pump_magnitudes(row, p)
    _, zero = surface_pump.ledger_limits(row, p, tol, 2e-3, steps=0, magnitudes=magnitudes)
    _, later = surface_pump.ledger_limits(row, p, tol, 2e-3, steps=10**6, magnitudes=magnitudes)
    for name, a, b, m in zip(surface_pump.LEDGERS, zero, later, magnitudes, strict=True):
        if m is None:
            np.testing.assert_array_equal(a, b, err_msg=name)
        else:
            np.testing.assert_allclose(b - a, 2.5 * EPS * 10**6 * m, rtol=1e-12, err_msg=name)


def stepped_spec():
    from validation.tissue import surface_pump_fixtures

    raw = surface_pump_fixtures.definition("clamped", solver=imex.ARS222_ID)
    raw["experiment"]["end_time"] = 0.0012
    raw["experiment"]["observation_times"] = [0.0, 0.0007, 0.0012]
    return parse_spec(raw)


def test_host_windows_check_each_row_with_its_global_step_count(monkeypatch):
    """Windowed host checks pass every row its index from t = 0, across windows."""
    from cells.core.batch import BatchSpec, WorldSpec
    from cells.core.batch_windows import run_batch_windowed
    from cells.core.grid import EventGrid
    from cells.core.windows import WindowPolicy, run_windowed

    spec, seen = stepped_spec(), []
    original = surface_pump.check_values

    def spy(state, spec, steps=None):
        rows = 1 if state.amount_increment.ndim == 2 else len(state.amount_increment)
        if steps is not None:
            assert len(steps) == rows
            seen.append([int(k) for k in steps])
        return original(state, spec, steps=steps)

    monkeypatch.setattr(surface_pump, "check_values", spy)
    last = len(EventGrid(spec)) - 1
    policy = WindowPolicy(5, "checkpoints")
    for execute in (
        lambda: run_windowed(spec, policy),
        lambda: run_batch_windowed(BatchSpec((WorldSpec(1, spec),), 1, 10**6, 2**31), policy),
    ):
        seen.clear()
        execute()
        assert last > 5 and seen, seen
        # Window checks: consecutive global indices covering 0..last. Observation
        # tail rechecks: the observed rows' own indices.
        windows = [s for s in seen if s == list(range(s[0], s[0] + len(s)))]
        assert {k for s in windows for k in s} == set(range(last + 1)), seen
        assert any(s[0] >= 5 and len(s) > 1 for s in windows), seen
        observed = {round(t / spec.execution.dt) for t in spec.experiment.observation_times}
        assert all(set(s) <= observed for s in seen if s not in windows), seen


def test_device_window_checks_see_global_step_counts(monkeypatch):
    """The device check of row j of a window gets the window's start step + j."""
    from cells.core.batch import BatchSpec, WorldSpec
    from cells.core.grid import EventGrid
    from cells.core.vector_windows import WorldCheckError, run_vector_windowed
    from cells.core.windows import WindowPolicy

    spec = stepped_spec()
    last = len(EventGrid(spec)) - 1
    target = last - 1  # In a later window: a window-local count never reaches it.
    assert target > 5
    original = surface_pump.device_checks

    def device_checks(previous, row, p, constants, steps):
        failed, values = original(previous, row, p, constants, steps)
        return failed.at[1].set(failed[1] | (steps >= target)), values

    monkeypatch.setattr(surface_pump, "device_checks", device_checks)
    cohort = BatchSpec((WorldSpec(1, spec),), 1, 10**6, 2**31)
    with pytest.raises(WorldCheckError) as caught:
        run_vector_windowed(cohort, WindowPolicy(5, "checkpoints"))
    assert caught.value.step_index == target
    assert caught.value.checks[0] == surface_pump.DEVICE_CHECKS[1]


def projective_world(row_checks):
    from validation.tissue import projective_fixtures

    raw = projective_fixtures.pump_cells(
        [projective_fixtures.H], end_time=6.0, observation_times=[0.0, 3.0, 6.0]
    )
    raw["execution"]["projective"] = projective_fixtures.projective_block(
        [(1.0, 6.0)],
        burst_steps=100,
        slope_steps=25,
        max_steps=2000,
        min_steps=50,
        tolerance=dict(concentration_mM=1e-2, membrane_voltage_V=2e-3, gate=1e-2),
        row_checks=row_checks,
    )
    return parse_spec(raw)


def test_projective_checks_see_global_step_counts(monkeypatch):
    """Bursts pass consecutive indices, a jump its two rows' indices; the device too."""
    from cells.core.grid import EventGrid

    seen, original = [], surface_pump.check_values

    def spy(state, spec, steps=None):
        seen.append(None if steps is None else [int(k) for k in steps])
        return original(state, spec, steps=steps)

    monkeypatch.setattr(surface_pump, "check_values", spy)
    spec = projective_world("host")
    grid = EventGrid(spec)
    report = run(spec).projective
    assert report["jumps"] >= 1 and None not in seen
    jumps = [s for s in seen if len(s) == 2 and s[1] > s[0] + 1]
    landed = {grid.exact_index(j["to_time_s"]) for j in report["jump_log"]}
    assert {s[1] for s in jumps} >= landed  # Every accepted jump's row was checked at j.
    bursts = [s for s in seen if s not in jumps]
    assert all(s == list(range(s[0], s[0] + len(s))) for s in bursts)
    assert any(s[0] in landed for s in bursts)  # A burst verifying a jump starts at j.
    monkeypatch.setattr(surface_pump, "check_values", original)
    # Device row checks: a check keyed on the global index fails at that row,
    # beyond the last jump, so a jump-relative count would miss it.
    target = max(landed) + 30
    device = surface_pump.device_checks

    def keyed(previous, row, p, constants, steps):
        failed, values = device(previous, row, p, constants, steps)
        return failed.at[1].set(failed[1] | (steps == target)), values

    monkeypatch.setattr(surface_pump, "device_checks", keyed)
    with pytest.raises(NumericalError, match=f"at {grid[target]} s"):
        run(projective_world("device"))


# --- component net charge (field gauge) ----------------------------------------------


def pump_fixture(arm, version=1, **execution):
    from validation.tissue import surface_pump_fixtures, surface_pump_v2_fixtures

    fixtures = {1: surface_pump_fixtures, 2: surface_pump_v2_fixtures}[version]
    raw = fixtures.definition(arm, solver=imex.ARS222_ID)
    raw["execution"].update(execution)
    return raw


def field_layout_of(spec, model=surface_pump):
    _, p = model.initial_values(spec)
    p = type(p)(*(np.asarray(v) for v in p))
    return p, surface_tissue.field_layout(p)


def test_representatives_are_the_gauge_and_each_floating_component_owner():
    _, closed = field_layout_of(parse_spec(pump_fixture("closed")))
    _, release = field_layout_of(parse_spec(pump_fixture("release")))
    np.testing.assert_array_equal(np.flatnonzero(surface_field.representatives(closed)), [3, 5, 7])
    np.testing.assert_array_equal(closed.offset_free, [True, True, False])  # Gauge last.
    assert np.flatnonzero(closed.gauge_mask).tolist() == [7 - closed.surface.cell_active.size]
    np.testing.assert_array_equal(np.flatnonzero(surface_field.representatives(release)), [5])


def test_field_convergence_leaves_out_the_representative_net_charge():
    """A representative's charge enters no potential: it is reported, not converged on."""
    from cells.core.state import initialise

    spec = parse_spec(pump_fixture("release"))
    p, layout = field_layout_of(spec)
    state = initialise(spec).state
    c = control_values(spec, [0.0])
    control = type(c)(*(v[0] for v in c))
    before = surface_tissue.field_values(state, control, p, xp=np)
    charged = p._replace(initial_outside_charge_C=p.initial_outside_charge_C.copy())
    rep = int(np.flatnonzero(surface_field.representatives(layout))[0])
    n = p.active.size
    charged.initial_outside_charge_C[rep - n] += 1e-20  # About 3e4 x its bound.
    after = surface_tissue.field_values(state, control, charged, xp=np)
    assert bool(before.converged) and bool(after.converged)
    assert after.charge_normalized > 1e4 and before.charge_normalized < 1
    np.testing.assert_allclose(after.charge_residual_C[rep] - before.charge_residual_C[rep], -1e-20)
    np.testing.assert_array_equal(after.potential_V, before.potential_V)


def test_component_allowance_uses_its_own_increments_or_the_world_at_the_gauge():
    _, layout = field_layout_of(parse_spec(pump_fixture("closed")))
    size = layout.active.size
    increment = np.arange(1.0, size + 1.0) * 1e-12
    charge = np.zeros(size)
    extra = surface_field.charge_tolerance(charge, increment, 1000, layout) - (
        surface_field.charge_tolerance(charge, increment, 0, layout)
    )
    rounding = surface_field.COMPONENT_STEP_ROUNDING * EPS * 1000
    expected = np.zeros(size)
    for rep, members in ((3, [0, 3, 4]), (5, [1, 5, 6])):  # Floating: own increments.
        expected[rep] = rounding * increment[members].sum()
    expected[7] = rounding * increment.sum()  # The gauge's component: the world's.
    np.testing.assert_allclose(extra, expected, rtol=1e-12, atol=0)


@pytest.mark.parametrize("version", [1, 2])
def test_seeded_net_charge_in_a_floating_component_fails_host_and_device_at_its_row(version):
    """1e-13 fmol of K booked into a floating component's outside node and no ledger.

    That is 1e-24 C, ten times the capacitor bound and 1/200 of the material
    tolerance: the component net-charge check alone catches it, at that row.
    """
    model = {1: surface_pump, 2: surface_pump_v2}[version]
    spec = parse_spec(pump_fixture("release", version))
    value = run(spec)
    history = model.STATE_TYPE(*(np.asarray(v) for v in value.history))
    _, p = model.initial_values(spec)
    layout = surface_tissue.field_layout(type(p)(*(np.asarray(v) for v in p)))
    node = int(np.flatnonzero(surface_field.representatives(layout))[0]) - p.active.size
    row, k = 10, 1
    amounts = history.extracellular_amount_increment.copy()
    amounts[row:, k, node] += 1e-13
    corrupted = history._replace(extracellular_amount_increment=amounts)
    assert 1e-13 < 0.01 * min(spec.execution.material_balance_atol_fmol)
    expected = (row, "Resolved pump accounting failed: charge")
    assert host_first_failure(model, spec, corrupted) == expected
    assert device_rows(model, spec, corrupted, p) == expected
    assert host_first_failure(model, spec, history) == (None, None)


@pytest.mark.parametrize("version", [1, 2])
def test_seeded_net_charge_on_the_gauge_component_fails_host_and_device_at_its_row(version):
    """A K booking on the closed world's gauge node (its own component) and no ledger.

    The gauge row allows the world's summed increments, so its floor is the
    capacitor bound plus that allowance: twice the floor at row 5 of a 1 ms run
    fails host and device at that row, half of it passes every row.
    """
    model = {1: surface_pump, 2: surface_pump_v2}[version]
    raw = pump_fixture("closed", version, dt=1e-3, max_steps=20)
    raw["experiment"].update(end_time=0.01, observation_times=[0.0, 0.01])
    spec = parse_spec(raw)
    history = model.STATE_TYPE(*(np.asarray(v) for v in run(spec).history))
    _, p = model.initial_values(spec)
    host = type(p)(*(np.asarray(v) for v in p))
    layout = surface_tissue.field_layout(host)
    n, gauge = host.active.size, int(np.flatnonzero(layout.gauge_mask)[0])
    assert not layout.offset_free[-1] and layout.floating_basis[n + gauge, -1] == 1
    row, k = 5, 1
    state = type(history)(*(v[row] for v in history))
    q = np.r_[host.initial_cell_charge_C, host.initial_outside_charge_C]
    q = q + surface_tissue.charge_increment(state, host, xp=np)
    bound = surface_tissue.capacitor_tolerance(q, state, host, row)[n + gauge]
    residual = abs(model.balances(state, host)["charge"][n + gauge])
    floor = (bound - residual) / CHARGE_PER_FMOL  # fmol of K at the gauge node.
    assert 0 < floor < 1e-14 < 0.01 * min(spec.execution.material_balance_atol_fmol)
    expected = (row, "Resolved pump accounting failed: charge")
    for factor, detected in ((2.0, True), (0.5, False)):
        amounts = history.extracellular_amount_increment.copy()
        amounts[row:, k, gauge] += factor * floor
        corrupted = history._replace(extracellular_amount_increment=amounts)
        found = expected if detected else (None, None)
        assert host_first_failure(model, spec, corrupted) == found, factor
        assert device_rows(model, spec, corrupted, p) == found, factor


def test_closed_fixture_runs_past_the_fixed_bound_refusal():
    """The gauged closed world at 1 ms: the fixed bound refused it within 5 s."""
    end = 5.0
    raw = pump_fixture("closed", dt=1e-3, max_steps=round(end / 1e-3) + 8)
    raw["experiment"].update(end_time=end, observation_times=[0.0, end])
    spec = parse_spec(raw)
    value = run(spec)
    final = surface_pump.STATE_TYPE(*(np.asarray(v) for v in value.final.state))
    p, layout = field_layout_of(spec)
    rep = np.flatnonzero(surface_field.representatives(layout))
    q = np.r_[p.initial_cell_charge_C, p.initial_outside_charge_C]
    q = q + surface_tissue.charge_increment(final, p, xp=np)
    residual = np.abs(surface_pump.balances(final, p)["charge"])
    fixed = surface_field.CHARGE_ATOL_C + surface_field.CHARGE_RTOL * np.abs(q)
    steps = value.final.step_index
    bound = surface_tissue.capacitor_tolerance(q, final, p, steps)
    assert steps == 5000
    assert np.all(residual[rep] < 1e-2 * bound[rep]), residual[rep] / bound[rep]
    unrepresented = np.setdiff1d(np.arange(q.size), rep)  # Solved rows keep the fixed bound.
    np.testing.assert_array_equal(bound[unrepresented], fixed[unrepresented])
    # The gauge row passed the fixed bound on the way, which refused this world before.
    assert value.diagnostics["max_capacitor_charge_error_C"] > surface_field.CHARGE_ATOL_C


# --- reaction_transport@1 -----------------------------------------------------------


def strip_definition(cells=16, steps=2000):
    from validation.morphogenesis import mg0a_gradient as mg

    graph = mg.strip(cells)
    dt = mg.stable_dt(graph)
    end = steps * dt
    return graph, mg.definition(graph, end_time=end, dt=dt, observation_times=[0.0, end])


def test_reaction_transport_allowance_grows_with_the_horizon_and_detects_errors():
    graph, raw = strip_definition()
    spec = parse_spec(raw)
    value = run(spec)
    history = reaction_transport.STATE_TYPE(*(np.asarray(v) for v in value.history))
    steps = reaction_transport.horizon_steps(spec)
    assert steps == len(value.times) - 1 == 2000
    total = float(np.sum(history.amount[0]))
    bound = EPS * total * (512 + reaction_transport.STEP_ROUNDING * steps)
    assert value.diagnostics["max_balance_error_fmol"] < 0.1 * bound

    def refused(history):
        try:
            reaction_transport.check_values(history, spec)
        except NumericalError as error:
            return str(error)
        return None

    # A single mis-signed contact transfer: the per-cell accounting fails.
    transferred = history.transferred.copy()
    transferred[1000:, 0, 0] *= -1
    assert "accounting" in refused(history._replace(transferred=transferred))
    # A persistent leak from one tissue cell is held to that cell's own
    # allowance, 1024 eps x scale + STEP_ROUNDING eps x steps x its magnitudes
    # (amount and incident ledgers): twice it is caught, half of it is not.
    cell, final = 1, history.amount[-1]
    touched = np.abs(history.transferred[-1, 0, :2]).sum()  # Edges 0 and 1 meet cell 1.
    magnitude = abs(history.amount[0, 0, cell]) + abs(final[0, cell]) + touched
    magnitude += abs(history.converted[-1, cell])
    scale = max(1.0, abs(history.amount[0, 0, cell]) + abs(history.transferred[-1, 0, 0]))
    scale += abs(history.transferred[-1, 0, 1]) + abs(history.converted[-1, cell])
    allowance = 1024 * EPS * scale + reaction_transport.STEP_ROUNDING * EPS * steps * magnitude
    rows = np.arange(len(history.amount))
    for factor, detected in ((2.0, True), (0.5, False)):
        amount = history.amount.copy()
        amount[:, 0, cell] += factor * allowance * rows / rows[-1]
        message = refused(history._replace(amount=amount))
        assert (message is not None) == detected, (factor, message)
        assert not detected or "accounting" in message


def test_reaction_transport_guard_admits_the_mg0a_drift_rate():
    """The measured worst drift (0.085 eps x total per step) is inside the allowance."""
    assert reaction_transport.STEP_ROUNDING > 10 * 0.085
    assert math.isclose(reaction_transport.STEP_ROUNDING, 2.5)


# --- junction gate step bound ---------------------------------------------------------


def chain(minimum, *, dt):
    states = fixtures.HEREDITY_STATES
    raw = fixtures.heredity_cells([states["H"][:4]] * 2, dt=dt, end_time=0.1)
    raw["model"]["junctions"] = [
        dict(
            id="junction_0",
            sender="cell_0",
            receiver="cell_1",
            area_m2=1e-11,
            permeability_m_per_s=dict(Na=1e-9, K=1e-9, M=1e-9, P=0.0),
            law="constant_field@1",
            gate=dict(
                law="junction_voltage_relaxation@1",
                threshold_voltage_V=0.0,
                minimum_open_fraction=minimum,
                initial_gate=1.0,
            ),
        )
    ]
    raw["experiment"]["junction_controls"] = [
        dict(junction_id="junction_0", schedule=[dict(time=0.0, availability=1.0)])
    ]
    raw["execution"]["edge_capacity"] = 1
    return raw


def test_pinned_junction_gate_sets_no_gate_step_bound():
    """Minimum open fraction 1 pins the gate at 1 (zero rate); 0.5 keeps the bound."""
    from cells.core.runner import timeline

    pinned = parse_spec(chain(1.0, dt=8e-3))
    assert surface_pump.junction_gate_rate_bound(pinned) == 0.0
    timeline(pinned)  # 8 ms: no gate-rate refusal for a pinned gate.
    free = parse_spec(chain(0.5, dt=8e-3))
    assert math.isclose(surface_pump.junction_gate_rate_bound(free), 21.3)
    with pytest.raises(ConfigError, match="junction step"):
        timeline(free)
    assert imex.ARS222_ID == pinned.execution.solver
