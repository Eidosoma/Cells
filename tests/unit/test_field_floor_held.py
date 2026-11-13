"""Field solver version 3 on resolved_pump_tissue@3: the solve and the cap (guard 6).

On an @3 fixture version 3 accepts a root at the rounding floor that version 2 cannot
certify, with every value unchanged, and refuses a solve stopped above the floor.

On the 825-node study tissue (the W1 hold's structure: 225 cells, 600 outside nodes, 172
free offsets) version 3's cap lies far above NEWTON_TARGET, so version 3 loosens acceptance
that far (docs/FIELD_FLOOR_ACCEPTANCE_DESIGN.md). A solve held just under the cap
(validation/tissue/field_floor_held.py) must still pass every host row check and ledger and
every device row check, and move the state only at rounding level.
"""

import jax
import numpy as np
import pytest

from cells.core.schedule import control_values
from cells.core.specs import parse_spec
from cells.core.state import initialise
from cells.models import surface_pump_v3 as model
from cells.numerics import surface_field as field
from cells.numerics import surface_imex as imex
from validation.tissue import field_floor_held as held
from validation.tissue import surface_pump_v3_fixtures as fixtures


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def definition(arm, solver):
    raw = fixtures.definition(arm, solver=imex.ARS222_ID)
    raw["execution"]["field_solver"] = solver
    return raw


def start_field(arm, solver):
    """The arguments of the start state's field solve, as the model's readouts pass them."""
    spec = parse_spec(definition(arm, solver))
    start = initialise(spec)
    p = type(start.layout)(*(np.asarray(v) for v in start.layout))
    state = type(start.state)(*(np.asarray(v) for v in start.state))
    table = control_values(spec, [0.0])
    control = type(table)(*(np.asarray(v[0]) for v in table))
    seen, solve = [], field.solve

    def capture(*arguments, **keywords):
        seen.append(arguments)
        return solve(*arguments, **keywords)

    field.solve = capture
    try:
        model.readouts(state, control, p, xp=np)
    finally:
        field.solve = solve
    (arguments,) = seen
    return arguments


def flatten(values):
    """Every returned value except the convergence flag."""
    fields = (getattr(values, k) for k in values._fields if k != "converged")
    return [np.asarray(v) for value in fields for v in jax.tree.leaves(value)]


def test_version_3_accepts_a_root_at_the_rounding_floor(monkeypatch):
    """With NEWTON_TARGET unattainable, version 2 stalls at the floor; version 3 accepts."""
    two = start_field("open", field.FACTORED_SOLVER_ID)
    three = start_field("open", field.FLOOR_SOLVER_ID)
    assert isinstance(three[-1], field.FloorLayout)
    monkeypatch.setattr(field, "NEWTON_TARGET", 0.0)
    stalled = field.solve(*two, xp=np)
    floor = field.solve(*three, xp=np)
    assert not bool(stalled.converged) and bool(floor.converged)
    assert int(floor.iterations) > 0
    for a, b in zip(flatten(stalled), flatten(floor), strict=True):
        np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize("iterations", [0, 1])
def test_version_3_refuses_a_root_above_the_floor(iterations):
    """A solve stopped after 0 or 1 Newton steps is far above the floor and refused."""
    three = start_field("open", field.FLOOR_SOLVER_ID)
    stopped = field.solve(*three, xp=np, max_iterations=iterations)
    assert not bool(stopped.converged)
    assert bool(field.solve(*three, xp=np).converged)


WARM_STEPS = 100  # Host steps from the electroneutral start: the potentials have grown.


@pytest.fixture(scope="module")
def warmed_tissue():
    """The 825-node study tissue as version 3 after WARM_STEPS host-path steps."""
    from validation.tissue import surface_pump_v3_study as study

    jax.config.update("jax_enable_x64", True)
    raw = study.tissue_definition(dt=1e-3, end_time=1.0, observation_times=[0.0, 1.0])
    raw["execution"]["field_solver"] = field.FLOOR_SOLVER_ID
    spec = parse_spec(raw)
    history, valid = held.host_run(spec, initialise(spec).state, WARM_STEPS)
    assert all(valid)
    return spec, type(history)(*(v[-1] for v in history))


def test_a_solve_held_just_under_the_cap_keeps_every_row_and_ledger_check(warmed_tissue):
    """Version 3 accepts the held solves version 2 refuses; the records stay sound."""
    spec, state = warmed_tissue
    assert int(np.sum(initialise(spec).layout.field_offset_free)) == 172
    out = held.compare(spec, state, 2, start_step=WARM_STEPS, kind="largest")
    normal, moved = out["normal"], out["held"]
    assert normal["steps_valid"] and moved["steps_valid"]
    assert [r["held"] for r in moved["solves"]] == [True, True]
    for solve in moved["solves"]:
        assert solve["converged"] and not solve["converged_at_0p9_cap"]  # Just under the cap.
        assert solve["fraction_of_target"] > 100.0  # Far beyond version 2's acceptance.
    for entry in (normal, moved):
        assert "check_values_error" not in entry  # Every host row check and ledger passes.
        assert entry["device_failed_rows"] == []
        assert max(entry["ledger_ratios"].values()) < 1.0
    for name, (difference, scale) in out["state_differences"].items():
        assert difference <= 1e-12 * scale, name
