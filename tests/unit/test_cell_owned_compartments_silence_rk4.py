"""S1 to S3 under RK4 (FR-1; design §3.3): the scalar program at 0.1 ms.

The criteria are test_cell_owned_compartments_silence.py's, fixed before any run, checked on every
row of core/runner.run with every step observed, in the silence world W under RK4. One compile:
not tier 1.
"""

import jax

from cells.core.runner import run
from cells.core.specs import parse_spec
from validation.tissue import compartment_fixtures as cfx

jax.config.update("jax_enable_x64", True)


def test_the_rk4_program_is_silent():
    end, dt = 4e-4, 1e-4
    spec = parse_spec(cfx.loaded_compartment(end=end, dt=dt, solver="rk4"))
    result = run(spec)
    found = cfx.silence(spec, result.observations)
    assert found["s1"], "S1: an ion row of the compartment changed"
    assert found["s2"] <= 1.0 and found["s3"] <= 1.0, found
    assert found["rows"] == int(round(end / dt)) + 1
    assert found["loaded"] > 0.0
