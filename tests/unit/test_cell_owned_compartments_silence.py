"""S1 to S3, the neutral compartment is electrically silent (FR-1; design §3.3): scalar programs.

The criteria, fixed before any run (closed-compartment-m1-20261114-01/HANDOFF.md):
- S1: at every accepted row, every ion row of the node's extracellular_amount_increment equals its
  initial value bitwise;
- S2: |V_b| <= (CHARGE_ATOL_C + CHARGE_RTOL max(|q_comp|, |C_b V_b|)) / C_b, with q_comp = 0;
- S3: (1/2) C_b V_b^2 <= (1/2) (CHARGE_ATOL_C + CHARGE_RTOL |C_b V_b|)^2 / C_b.
These are checked here on every row of the scalar program (core/runner.run, every step observed),
in the silence world W (validation/tissue/compartment_fixtures.loaded_compartment), with exchange
loading S into the compartment while no ion moves. The export rate changes at 5 ms.
- Under ARS(2,2,2) at 1 ms: the run, then restarts in process from checkpoints before, at and
  after the change, and through a written snapshot at the change, each bitwise against the run.
- Under RK4 at 0.1 ms: the run.
The windowed, vector-window and batch programs are test_cell_owned_compartments_paths.py. A few
compiles: not tier 1.
"""

import jax
import numpy as np

from cells.core.runner import run
from cells.core.specs import parse_spec
from validation.tissue import compartment_fixtures as cfx

jax.config.update("jax_enable_x64", True)

CHANGE = 0.005


def assert_silent(spec, observations, rows):
    found = cfx.silence(spec, observations)
    assert found["s1"], "S1: an ion row of the compartment changed"
    assert found["s2"] <= 1.0, f"S2: |V_b| at {found['s2']} of its bound"
    assert found["s3"] <= 1.0, f"S3: the capacitor energy at {found['s3']} of its bound"
    assert found["rows"] == rows
    assert found["loaded"] > 0.0  # S moved into the compartment.
    return found


def test_the_scalar_program_and_its_restarts_are_silent(tmp_path):
    from cells.io import load_snapshot, write_snapshot

    end, dt = 0.012, 1e-3
    spec = parse_spec(cfx.loaded_compartment(end=end, dt=dt, changes=[(CHANGE, 0.5)]))
    result = run(spec)  # Every host check, on every accepted row.
    assert_silent(spec, result.observations, int(round(end / dt)) + 1)
    for t in (0.003, CHANGE, 0.008):
        checkpoint = result.checkpoint_at(t)
        resumed = run(spec, checkpoint)
        for a, b in zip(resumed.history, result.history, strict=True):
            assert np.array_equal(np.asarray(a), np.asarray(b)[checkpoint.step_index :]), t
        assert cfx.silence(spec, resumed.observations)["s1"]
    checkpoint = result.checkpoint_at(CHANGE)
    write_snapshot(tmp_path / "checkpoint", result.spec, checkpoint)
    loaded = load_snapshot(tmp_path / "checkpoint")
    again = run(loaded.spec, loaded.checkpoint)
    for a, b in zip(again.history, result.history, strict=True):
        assert np.array_equal(np.asarray(a), np.asarray(b)[checkpoint.step_index :])
    assert cfx.silence(loaded.spec, again.observations)["s1"]


def test_the_rk4_program_is_silent():
    end, dt = 4e-4, 1e-4
    spec = parse_spec(cfx.loaded_compartment(end=end, dt=dt, solver="rk4"))
    result = run(spec)
    assert_silent(spec, result.observations, int(round(end / dt)) + 1)
