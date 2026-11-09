"""Rounding in the resolved pump ledgers and the reaction_transport@1 guards.

Electrode ledger: each IMEX step books the change of the held nodes' plate charges
that its start and end charge states determine, so the ledger telescopes onto the
electrode check's reference (it drifted linearly with the step count before). It
feeds no rate. Seeded errors of physical size, a per-step leak of 1e-12 of a step's
transfer and a single mis-signed transfer, still fail the host and the device
checks at the same row. reaction_transport@1: the allowance grows linearly with
the step count at the derived worst-case rate, and the resulting detection limit
is stated. A pinned junction gate sets no gate-rate step bound.
"""

import math

import jax
import numpy as np
import pytest

from cells.core.errors import NumericalError
from cells.core.runner import run
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.models import reaction_transport, surface_pump, surface_pump_v2, surface_pump_v3
from cells.models.registry import get_model
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
    checks = jax.jit(jax.vmap(model.device_checks, in_axes=(0, 0, None, None)))
    failed, _ = checks(previous, history, p, model.device_check_constants(spec))
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
            model.check_values(type(history)(*(v[: j + 1] for v in history)), spec)
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


def seeded(history, p, fault, row):
    """A copy of the history with one physical-size error from ``row`` on."""
    values = {k: np.array(v, copy=True) for k, v in history._asdict().items()}
    bath = int(np.flatnonzero(p.reservoir)[0])
    k = 1  # K
    rows = np.arange(len(values["amount_increment"]))
    after = np.clip(rows - row + 1, 0, None)
    if fault == "supply_leak":  # 1e-12 of a step's K exchange at that bath, every step.
        step = np.max(np.abs(np.diff(values["reservoir_supplied"][:, k, bath])))
        values["reservoir_supplied"][:, k, bath] += 1e-12 * step * after
    elif fault == "electrode_leak":  # 1e-12 of a step's plate-charge change, every step.
        step = np.max(np.abs(np.diff(values["electrode_charge_transferred_C"][:, bath])))
        values["electrode_charge_transferred_C"][:, bath] += 1e-12 * step * after
    elif fault == "mis_signed":  # One step's K membrane transfer booked with the wrong sign.
        patch = 0
        cell = int(p.membrane_cell[patch])
        moved = values["membrane_transferred"][row, k, patch]
        moved -= values["membrane_transferred"][row - 1, k, patch]
        values["amount_increment"][row:, k, cell] += 2 * moved
    return type(history)(**values)


@pytest.mark.parametrize("version", [1, 2])
@pytest.mark.parametrize("fault", ["supply_leak", "electrode_leak", "mis_signed"])
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


def test_seeded_leak_size_is_physical(runs):
    """The leaks above are 1e-12 of a real step's exchange: about 2e-27 C per step."""
    _, _, _, history, p = runs[1]
    bath = int(np.flatnonzero(p.reservoir)[0])
    supply = np.max(np.abs(np.diff(history.reservoir_supplied[:, 1, bath])))
    assert 1e-28 < 1e-12 * supply * CHARGE_PER_FMOL < 1e-25


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
