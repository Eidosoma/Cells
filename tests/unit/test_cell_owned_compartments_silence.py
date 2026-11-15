"""S1 to S3, the neutral compartment is electrically silent (FR-1; design §3.3): the scalar program.

The criteria, fixed before any run (closed-compartment-m1-20261114-01/HANDOFF.md):
- S1: at every accepted row, every ion row of the node's extracellular_amount_increment equals its
  initial value bitwise;
- S2: |V_b| <= (CHARGE_ATOL_C + CHARGE_RTOL max(|q_comp|, |C_b V_b|)) / C_b, with q_comp = 0;
- S3: (1/2) C_b V_b^2 <= (1/2) (CHARGE_ATOL_C + CHARGE_RTOL |C_b V_b|)^2 / C_b.
They are checked on every row of core/runner.run (every step observed, ARS(2,2,2) at 1 ms) in the
live-owner world W+ (validation/tissue/compartment_fixtures.live_compartment): K leaves the owner
through its wall at an owner potential near -0.06 V while exchange loads S into the compartment,
so a check that could fail is live (the lead's ruling; the quiescent W's runs are superseded).

Planted controls, each in the same program and composition (so no new compile), bypassing one of
the declaration's refusals in a test-only way (monkeypatch): (a) a K route on the bounding patch
must break S1 and S2; (b) a compartment charge anchor must break S2. The restart is
test_cell_owned_compartments_restart.py, RK4 _silence_rk4.py, and the windowed, vector-window and
batch programs _windowed.py, _vector.py and _batch.py. One compile: not tier 1.
"""

import jax

from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.models.operators import compartments as comp
from validation.tissue import compartment_fixtures as cfx

jax.config.update("jax_enable_x64", True)

END, DT = 0.012, 1e-3
ROWS = int(round(END / DT)) + 1


def test_the_scalar_program_is_silent_and_its_planted_controls_are_not(monkeypatch):
    spec = parse_spec(cfx.live_compartment(end=END, dt=DT))
    result = run(spec)  # Every host check, on every accepted row.
    assert cfx.assert_silent_and_live(spec, result.observations, ROWS) == ROWS
    assert cfx.silence(spec, result.observations)["loaded"] > 0.0  # S moved in.
    monkeypatch.setattr(comp, "refuse_ion_routes", lambda *a: None)
    monkeypatch.setattr(comp, "refuse_charge_anchor", lambda *a: None)
    routed = parse_spec(cfx.live_compartment(end=END, dt=DT, planted_route=cfx.PLANTED_ROUTE))
    cfx.assert_broken(routed, run(routed).observations, route=True)
    anchored = parse_spec(cfx.live_compartment(end=END, dt=DT, planted_anchor=cfx.PLANTED_ANCHOR_C))
    cfx.assert_broken(anchored, run(anchored).observations, route=False)
