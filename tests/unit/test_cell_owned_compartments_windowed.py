"""S1 to S3 in the windowed program (FR-1; design §3.3).

The criteria are test_cell_owned_compartments_silence.py's, fixed before any run, checked on every
row of core/windows.run_windowed (the observations policy, every step observed) in the live-owner
world W+: every window's observations. The planted control (a), a K route on the bounding patch
(the refusal bypassed by monkeypatch, the same composition and program), must break S1 and S2 in
its windows. One program's compile: not tier 1.
"""

import jax

from cells.definitions.specs import parse_spec
from cells.execution.windows import WindowPolicy, run_windowed
from cells.operators import compartments as comp
from validation.tissue import compartment_fixtures as cfx

jax.config.update("jax_enable_x64", True)

END, DT = 0.008, 1e-3
ROWS = int(round(END / DT)) + 1


def windows(spec):
    seen = []
    run_windowed(spec, WindowPolicy(3, "observations"), sink=seen.append)
    assert len(seen) > 1
    return seen


def test_the_windowed_program_is_silent_and_its_planted_control_is_not(monkeypatch):
    spec = parse_spec(cfx.live_compartment(end=END, dt=DT))
    seen = windows(spec)
    assert sum(cfx.assert_silent_and_live(spec, w.observations) for w in seen) == ROWS
    monkeypatch.setattr(comp, "refuse_ion_routes", lambda *a: None)
    routed = parse_spec(cfx.live_compartment(end=END, dt=DT, planted_route=cfx.PLANTED_ROUTE))
    broken = [cfx.silence(routed, w.observations) for w in windows(routed)]
    assert not all(f["s1"] for f in broken)
    assert max(f["s2"] for f in broken) > 1.0
