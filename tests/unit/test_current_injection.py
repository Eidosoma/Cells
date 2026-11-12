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
    assert protocol["status"].startswith("PROPOSED")
    assert "not registered" in rm1.judged_run_refusal(protocol, tmp_path)
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
