"""S1 to S3 in the windowed program (FR-1; design §3.3).

The criteria are test_cell_owned_compartments_silence.py's, fixed before any run, checked on every
row the program exposes, every step observed: core/windows.run_windowed with the observations
policy, every window's observations. The scalar program is test_cell_owned_compartments_silence.py
and RK4 test_cell_owned_compartments_silence_rk4.py. One program's compile per file: not tier 1.
"""

import jax

from cells.core.specs import parse_spec
from validation.tissue import compartment_fixtures as cfx

jax.config.update("jax_enable_x64", True)

END, DT = 0.008, 1e-3
ROWS = int(round(END / DT)) + 1
RATES = (0.2, 0.5, 0.05)


def silent(spec, observations):
    found = cfx.silence(spec, observations)
    assert found["s1"], "S1: an ion row of the compartment changed"
    assert found["s2"] <= 1.0 and found["s3"] <= 1.0, found
    return found["rows"]


def specs():
    return [parse_spec(cfx.loaded_compartment(end=END, dt=DT, export=r)) for r in RATES]


def test_the_windowed_program_is_silent():
    from cells.core.windows import WindowPolicy, run_windowed

    spec = specs()[0]
    seen = []
    run_windowed(spec, WindowPolicy(3, "observations"), sink=seen.append)
    assert len(seen) > 1
    assert sum(silent(spec, window.observations) for window in seen) == ROWS
