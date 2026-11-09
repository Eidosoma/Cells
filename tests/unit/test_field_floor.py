"""Field solver capacitive_reduction_gauged_damped_newton@3: version 2 plus the floor.

Version 3 iterates exactly as version 2, so on every fixture where version 2
converges the trajectories are bitwise the same. Where version 2 cannot reach
NEWTON_TARGET because the residual sits at its rounding floor (reproduced here
by an unattainable target), version 3 accepts it with every value unchanged. A
solve stopped above the floor is still refused.
"""

import copy

import jax
import numpy as np
import pytest

from cells.core.runner import run
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.state import initialise
from cells.models import surface_tissue as tissue
from cells.numerics import surface_field as field
from cells.numerics import surface_imex as imex
from validation.tissue import surface_pump_fixtures, surface_pump_v2_fixtures


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def definition(fixtures, arm, solver):
    raw = fixtures.definition(arm, solver=imex.ARS222_ID)
    raw["execution"]["field_solver"] = solver
    return raw


CASES = [
    (surface_pump_fixtures, "closed"),
    (surface_pump_fixtures, "release"),
    (surface_pump_fixtures, "clamped"),
    (surface_pump_v2_fixtures, "clamped"),
    (surface_pump_v2_fixtures, "closed"),
]


@pytest.mark.parametrize(("fixtures", "arm"), CASES)
def test_version_3_is_bitwise_version_2_where_version_2_converges(fixtures, arm):
    two = run(parse_spec(definition(fixtures, arm, field.FACTORED_SOLVER_ID)))
    three = run(parse_spec(definition(fixtures, arm, field.FLOOR_SOLVER_ID)))
    assert type(three.final.layout).__name__.endswith("FloorLayout")
    np.testing.assert_array_equal(two.times, three.times)
    for name, a, b in zip(two.history._fields, two.history, three.history, strict=True):
        np.testing.assert_array_equal(np.asarray(a), np.asarray(b), err_msg=name)
    assert two.diagnostics == three.diagnostics


def test_version_3_checkpoint_round_trips_and_resumes_bitwise(tmp_path):
    """A version 3 snapshot loads with its own layout type and resumes as run."""
    from cells.core.runner import branch_checkpoint
    from cells.io import load_snapshot, write_snapshot

    raw = definition(surface_pump_fixtures, "clamped", field.FLOOR_SOLVER_ID)
    whole = run(parse_spec(raw))
    half = copy.deepcopy(raw)
    half["experiment"].update(end_time=0.001, observation_times=[0.0, 0.001])
    for key in ("membrane_controls", "junction_controls", "pump_controls"):
        for group in half["experiment"].get(key, []):
            group["schedule"] = [c for c in group["schedule"] if c["time"] <= 0.001]
    first = run(parse_spec(half))
    saved = load_snapshot(write_snapshot(tmp_path / "half", parse_spec(half), first.final))
    assert type(saved.checkpoint.layout) is type(first.final.layout)
    spec = parse_spec(raw)
    resumed = run(spec, branch_checkpoint(saved.spec, saved.checkpoint, spec))
    for a, b in zip(resumed.final.state, whole.final.state, strict=True):
        np.testing.assert_array_equal(np.asarray(a), np.asarray(b))


def start_field(arm, solver):
    spec = parse_spec(definition(surface_pump_fixtures, arm, solver))
    start = initialise(spec)
    p = type(start.layout)(*(np.asarray(v) for v in start.layout))
    c = control_values(spec, [0.0])
    control = type(c)(*(v[0] for v in c))
    ci, co = tissue.physical_amounts(start.state, p)
    q = tissue.charge_increment(start.state, p, xp=np)
    n = p.active.size
    arguments = (
        np.where(p.active, ci / p.volume, 1.0),
        np.where(p.outside_active, co / p.extracellular_volume, 1.0),
        p.initial_cell_charge_C + q[:n],
        p.initial_outside_charge_C + q[n:],
        control.membrane,
        control.junction,
        p.boundary_V,
        tissue.field_layout(p),
    )
    return arguments


def flatten(values):
    """Every returned value except the convergence flag."""
    fields = (getattr(values, k) for k in values._fields if k != "converged")
    return [np.asarray(v) for value in fields for v in jax.tree.leaves(value)]


def test_version_3_accepts_a_root_at_the_rounding_floor(monkeypatch):
    """With NEWTON_TARGET unattainable, version 2 stalls at the floor; version 3 accepts."""
    two = start_field("clamped", field.FACTORED_SOLVER_ID)
    three = start_field("clamped", field.FLOOR_SOLVER_ID)
    monkeypatch.setattr(field, "NEWTON_TARGET", 0.0)
    stalled = field.solve(*two, xp=np)
    floor = field.solve(*three, xp=np)
    assert not bool(stalled.converged) and bool(floor.converged)
    for a, b in zip(flatten(stalled), flatten(floor), strict=True):
        np.testing.assert_array_equal(a, b)
    assert float(np.max(np.abs(floor.component_current_residual_A))) < 1e-24


@pytest.mark.parametrize("iterations", [0, 1])
def test_version_3_refuses_a_root_above_the_floor(iterations):
    """Stopped after 0 or 1 Newton steps, the residual (1e-18 A and up) is refused."""
    three = start_field("clamped", field.FLOOR_SOLVER_ID)
    stopped = field.solve(*three, xp=np, max_iterations=iterations)
    assert not bool(stopped.converged)
    assert float(np.max(np.abs(stopped.component_current_residual_A))) > 1e-19
    assert bool(field.solve(*three, xp=np).converged)


def test_pump_family_declares_version_2_or_3_only():
    raw = definition(surface_pump_fixtures, "clamped", field.SOLVER_ID)
    with pytest.raises(ConfigError, match="declared field solver"):
        parse_spec(raw)
    assert parse_spec(definition(surface_pump_fixtures, "clamped", field.FLOOR_SOLVER_ID))
