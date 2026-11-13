"""Tier-1 smoke test of electrode_current_injection@1 (docs/PUMP_COMPOSITE_V2_DESIGN.md §4).

The operator's half-step on a bound @3 heredity cell, in NumPy (no compile): both polarities
booked at f I h / (z F), the host ledgers closing after injection, the start state selected
bitwise without current, the refusal when a cell cannot supply a removed carrier, and the
definition refusals. The compiled runs are test_current_injection_runs.py.
"""

from types import SimpleNamespace

import numpy as np
import pytest

from cells.core.specs import ConfigError, parse_spec
from cells.models.registry import get_model
from cells.processes.electrochemistry import CHARGE_PER_FMOL
from tests.unit.test_current_injection_runs import DT, definition


@pytest.fixture(scope="module")
def bound():
    spec = parse_spec(definition([(0, 1e-12)]))
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    return spec, model, model.operators[0], state, p


def step(op, state, p, current):
    return op.half_step(
        state, DT / 2, SimpleNamespace(injection_current_A=np.array([current])), p, xp=np
    )


def test_both_polarities_and_their_bookings(bound):
    spec, _, op, state, p = bound
    species = list(spec.model.species_ids)
    k, m = species.index("K"), species.index("M")
    current = 1e-12
    entered, ok = step(op, state, p, current)
    assert ok
    dk, dm = (
        0.4912 * current * DT / 2 / CHARGE_PER_FMOL,
        0.5088 * current * DT / 2 / CHARGE_PER_FMOL,
    )
    change = entered.amount_increment - state.amount_increment
    assert change[k, 0] == pytest.approx(dk, rel=1e-12) and change[m, 0] == pytest.approx(
        -dm, rel=1e-12
    )
    assert entered.injection_supplied_fmol[k, 0] == pytest.approx(dk, rel=1e-12)
    assert entered.injection_removed_fmol[m, 0] == pytest.approx(dm, rel=1e-12)
    assert entered.injection_charge_C[0] == pytest.approx(current * DT / 2, rel=1e-12)
    back, ok = step(op, entered, p, -current)  # The other polarity: K out, M in.
    assert ok
    assert back.injection_removed_fmol[k, 0] == pytest.approx(dk, rel=1e-12)
    assert back.injection_supplied_fmol[m, 0] == pytest.approx(dm, rel=1e-12)
    assert back.injection_charge_C[0] == pytest.approx(0.0, abs=1e-30)


def test_the_host_ledgers_close_after_injection(bound):
    _, model, op, state, p = bound
    entered, _ = step(op, state, p, 1e-12)
    for name, residual in model.balances(entered, p).items():
        assert np.max(np.abs(residual), initial=0.0) < 1e-12, name


def test_no_current_selects_the_start_state(bound):
    _, _, op, state, p = bound
    idle, ok = step(op, state, p, 0.0)
    assert ok
    for a, b in zip(idle, state, strict=True):
        assert np.asarray(a).tobytes() == np.asarray(b).tobytes()


def test_a_cell_that_cannot_supply_a_removed_carrier_refuses(bound):
    _, _, op, state, p = bound
    with np.errstate(invalid="ignore"):  # The refused half-step's free energy is NaN.
        _, ok = step(op, state, p, -1e-3)  # 1 mA for half a step empties the cell's K.
    assert not ok


@pytest.mark.parametrize(
    ("carriers", "currents", "message"),
    [
        ({"K": 0.5, "M": 0.4}, [(0, 1e-12)], "sum to 1"),
        ({"K": 1.0, "Cl": 0.0}, [(0, 1e-12)], "positive"),
        ({"Cl": 1.0}, [(0, 1e-12)], "charged species"),
        ({"K": 1.0}, [(0, 1e-12), (1.5, 0.0)], "multiple of dt"),
    ],
)
def test_definition_refusals(carriers, currents, message):
    with pytest.raises(ConfigError, match=message):
        spec = parse_spec(definition(currents, carriers=carriers))
        get_model(spec.model).check_definition(spec)


def test_the_rm1_judged_run_needs_a_registered_protocol_and_a_clean_snapshot(tmp_path):
    import hashlib
    import json

    from validation.tissue import injection_rm1 as rm1

    protocol = json.loads(rm1.PROTOCOL.read_text())
    # The checked-in protocol is registered (lead, 12 November); its proposed form is refused.
    assert protocol["status"].startswith("registered")
    proposed = dict(protocol, status="PROPOSED (test)")
    assert "not registered" in rm1.judged_run_refusal(proposed, tmp_path)
    registered = dict(protocol, status="registered at a lead's commit (test)")
    assert "clean execution snapshot" in rm1.judged_run_refusal(registered, tmp_path)
    clean = dict(status="complete", patch_sha256=hashlib.sha256(b"").hexdigest())
    (tmp_path / "SNAPSHOT.json").write_text(json.dumps(clean))
    assert rm1.judged_run_refusal(registered, tmp_path) is None
    dirty = dict(clean, patch_sha256=hashlib.sha256(b"a change").hexdigest())
    (tmp_path / "SNAPSHOT.json").write_text(json.dumps(dirty))
    assert "uncommitted changes" in rm1.judged_run_refusal(registered, tmp_path)
    assert protocol["tolerance_ohm"] == pytest.approx(
        3 * (protocol["engine_step_term_ohm"] + protocol["reference_term_ohm"]), rel=1e-15
    )


# ---------------------------------------------------------------- at a capacitance view (S3)

LAW = "electrode_current_injection@1"
LIMITS = dict(charge=1e-24, electrode=1e-24, global_charge=1e-24)


def at_view(current=0.0):
    """Two clamps with the membrane state, insertion and an electrode (insertion's fixtures)."""
    from tests import membrane_insertion_fixtures as mfx

    raw = mfx.with_operators(mfx.two_clamps(), {"membrane_0": ({}, None, [(0.0, 0.0)])})
    cell = raw["model"]["cells"][0]["id"]
    raw["model"]["operators"].append(
        dict(law=LAW, electrodes=[dict(cell_id=cell, carriers={"K": 0.4912, "M": 0.5088})])
    )
    schedule = [dict(time=0.0, current_A=current)]
    raw["experiment"]["injection_controls"] = [dict(cell_id=cell, schedule=schedule)]
    return raw


def test_with_a_capacitance_view_injection_books_the_views_plate_charges():
    """After insertion changed a capacitance, injection books the clamps' plate charges and
    the capacitor energy at the view, so every ledger closes. The declared layout's booking,
    which is used when no field input is provided, would leave the electrode ledger open."""
    spec = parse_spec(at_view())
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    _, insertion, injection = model.operators
    c = np.asarray(p.membrane_capacitance)
    grow = SimpleNamespace(
        insertion_rate_m2_s=np.array([0.3 * c[0] / 0.05 / (DT / 2), 0.0]),
        insertion_open=np.ones(2),
    )
    grown, ok = insertion.half_step(state, DT / 2, grow, p, xp=np)
    assert ok
    current = 1e-12
    control = SimpleNamespace(injection_current_A=np.array([current]))
    view = model.view(p, grown, xp=np)
    after, ok = injection.half_step(grown, DT / 2, control, p, xp=np, view=view)
    assert ok
    # One cell between two clamps: its potential moves by dQ / sum C at the view, and each
    # clamp's plate charge by -C_b dQ / sum C.
    view_c = c + np.asarray(grown.membrane_capacitance_increment_F)
    image = -view_c * current * DT / 2 / view_c.sum()
    booked = after.electrode_charge_transferred_C - grown.electrode_charge_transferred_C
    np.testing.assert_allclose(booked, image, rtol=1e-10)
    for name, residual in model.balances(after, p).items():
        assert np.max(np.abs(residual), initial=0.0) < LIMITS.get(name, 1e-15), name
    declared, _ = injection.half_step(grown, DT / 2, control, p, xp=np)  # No view.
    assert np.max(np.abs(model.balances(declared, p)["electrode"])) > 1e-20


def test_the_view_reaches_injection_only_with_a_field_input():
    from cells.models.operators import OPERATORS

    assert OPERATORS[LAW].BOOKS_AT_VIEW
    alone = get_model(parse_spec(definition([(0, 1e-12)])).model)
    assert not alone.field_inputs  # The half-step call is then the declared-layout one.
    assert get_model(parse_spec(at_view()).model).field_inputs
