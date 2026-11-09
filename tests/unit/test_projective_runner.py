"""Projective execution through cells.core.runner.run on a one-cell resolved_pump_tissue@1 world.

Rejected jumps leave the fine engine's rows bitwise; accepted jumps are checked,
verified by the next burst and recorded; no jump crosses a scheduled input
change or an observation; jumped rows are restartable accepted boundaries.
Compiles the IMEX burst kernel and the ordinary rollout once each (slow).
"""

import jax
import numpy as np
import pytest

from cells.core.grid import EventGrid
from cells.core.projective import ROW_FINE, ROW_JUMP, ProjectiveRunResult
from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.numerics import surface_field as field
from validation.tissue import projective_fixtures as fixtures

LOOSE = dict(concentration_mM=1e-2, membrane_voltage_V=2e-3, gate=1e-2)
CUE = 6.0  # Pump availability 1 -> 0.5 at CUE s.
# Fine absolute floor of each linear ledger: the fixture's material tolerance,
# the field charge floor and the work floors of surface_pump's checks.
FLOORS = dict(
    local=1e-10,
    outside=1e-10,
    total=1e-10,
    charge=field.CHARGE_ATOL_C,
    electrode=field.CHARGE_ATOL_C,
    global_charge=field.CHARGE_ATOL_C,
    reservoir_work=3e-12,
    electrode_work=3e-12,
    metabolic_work=3e-12,
)


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def world(end_time, observation_times, **block):
    raw = fixtures.pump_cells(
        [fixtures.H],
        end_time=end_time,
        observation_times=observation_times,
        pump_controls={0: [(0.0, 1.0), (CUE, 0.5)]} if end_time > CUE else None,
    )
    if block:
        raw["execution"]["projective"] = fixtures.projective_block(**block)
    return raw


@pytest.fixture(scope="module")
def rejected():
    """Every jump rejected (max_correction below rounding) against the fine run."""
    times = [0.0, 0.75, 1.5]
    fine = run(parse_spec(world(1.5, times)))
    projective = run(
        parse_spec(
            world(
                1.5,
                times,
                windows=[(0.3, 1.5)],
                burst_steps=100,
                slope_steps=25,
                max_steps=400,
                min_steps=50,
                tolerance=dict(concentration_mM=10.0, membrane_voltage_V=1.0, gate=1.0),
                safety=dict(
                    max_correction=1e-300,
                    cooldown_bursts=0,
                    max_membrane_voltage_rate_V_per_s=10.0,
                    max_gate_distance=1.0,
                ),
                row_checks="device",
            )
        )
    )
    return fine, projective


@pytest.fixture(scope="module")
def accepted():
    times = [0.0, 3.0, 8.0, 10.0]
    return run(
        parse_spec(
            world(
                10.0,
                times,
                windows=[(1.0, 10.0)],
                burst_steps=100,
                slope_steps=25,
                max_steps=4000,
                min_steps=50,
                tolerance=LOOSE,
                row_checks="device",
            )
        )
    )


def test_rejected_jumps_leave_the_fine_rows_bitwise(rejected):
    fine, projective = rejected
    assert type(projective) is ProjectiveRunResult
    report = projective.projective
    assert report["jumps"] == 0 and report["rejections"] >= 1
    assert all(r["reason"] == "correction" for r in report["rejection_log"])
    assert report["discarded_fine_steps"] == 100 * report["rejections"]
    np.testing.assert_array_equal(projective.times, fine.times)
    assert np.all(projective.row_kinds == ROW_FINE)
    for a, b in zip(projective.history, fine.history, strict=True):
        np.testing.assert_array_equal(np.asarray(a), np.asarray(b))
    for a, b in zip(projective.final.state, fine.final.state, strict=True):
        np.testing.assert_array_equal(np.asarray(a), np.asarray(b))
    np.testing.assert_array_equal(
        projective.observations.membrane_voltage_V, fine.observations.membrane_voltage_V
    )
    assert projective.final.step_index == fine.final.step_index


def test_accepted_jumps_are_checked_verified_and_recorded(accepted):
    report, spec = accepted.projective, accepted.spec
    safety = spec.projective.safety
    assert report["jumps"] >= 2 and report["jumped_steps"] > 0
    assert report["fine_steps"] + report["jumped_steps"] == len(EventGrid(spec)) - 1
    assert np.count_nonzero(accepted.row_kinds == ROW_JUMP) == report["jumps"]
    for jump in report["jump_log"]:
        assert jump["correction_normalized"] <= safety.max_correction
        assert jump["a_posteriori_normalized"] <= safety.max_correction
        assert jump["energy_defect_pJ"] <= jump["energy_bound_pJ"]
        for name, ledger in jump["ledgers"].items():
            # Affine in the state: the jumped residual is the affine combination of
            # the two rows' residuals up to the extrapolation's rounding, which
            # uses at most a quarter of the ledger's fine absolute floor.
            assert ledger["affine_excess"] <= 0.25 * FLOORS[name], name
    # Every observation is a fine row; restarts from a jumped row use its grid index.
    for t in spec.experiment.observation_times:
        assert accepted.row_kinds[np.flatnonzero(accepted.times == t)[0]] == ROW_FINE
    jump = report["jump_log"][0]
    point = accepted.checkpoint_at(jump["to_time_s"])
    assert point.step_index == EventGrid(spec).exact_index(jump["to_time_s"])
    assert accepted.final.step_index == len(EventGrid(spec)) - 1
    assert accepted.diagnostics["max_energy_balance_relative"] > 0


def test_no_jump_crosses_an_event_or_an_observation(accepted):
    spec = accepted.spec
    burst = spec.projective.burst_steps * spec.execution.dt
    points = [c.time for c in spec.experiment.changes] + list(spec.experiment.observation_times)
    for jump in accepted.projective["jump_log"]:
        assert not any(
            jump["from_time_s"] < t < jump["to_time_s"] + burst - 1e-9 for t in points
        ), jump
    # The cue is followed by fine steps through its slope rows before any jump.
    after = [j["from_time_s"] for j in accepted.projective["jump_log"] if j["from_time_s"] > CUE]
    assert not after or min(after) - CUE >= 2 * spec.projective.slope_steps * spec.execution.dt


def test_a_jumped_row_is_a_restartable_boundary(accepted):
    jump = accepted.projective["jump_log"][-1]
    resumed = run(accepted.spec, accepted.checkpoint_at(jump["to_time_s"]))
    assert resumed.times[0] == jump["to_time_s"] and resumed.final.time == accepted.final.time
