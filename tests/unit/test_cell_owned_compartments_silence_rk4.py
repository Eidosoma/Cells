"""S1 to S3 under RK4 (FR-1; design §3.3): the scalar program at 0.1 ms.

The criteria are test_cell_owned_compartments_silence.py's, fixed before any run, checked on every
row of core/runner.run with every step observed, in the live-owner world W+ under RK4. The planted
control (a), a K route on the bounding patch (the refusal bypassed by monkeypatch, the same
composition and program), must break S1 and S2. One compile: not tier 1.
"""

import jax

from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.models.operators import compartments as comp
from validation.tissue import compartment_fixtures as cfx

jax.config.update("jax_enable_x64", True)

END, DT = 4e-4, 1e-4


def test_the_rk4_program_is_silent_and_its_planted_control_is_not(monkeypatch):
    spec = parse_spec(cfx.live_compartment(end=END, dt=DT, solver="rk4"))
    cfx.assert_silent_and_live(spec, run(spec).observations, int(round(END / DT)) + 1)
    monkeypatch.setattr(comp, "refuse_ion_routes", lambda *a: None)
    routed = parse_spec(
        cfx.live_compartment(end=END, dt=DT, solver="rk4", planted_route=cfx.PLANTED_ROUTE)
    )
    cfx.assert_broken(routed, run(routed).observations, route=True)
