"""FR-50's phase-1 compiled row for the transporter (fr50-one-way-records-v1 §5; D224): K4, a
neutral ATP-driven transporter at equilibrium.

The world (validation/fr50/engine.transporter_world, from the registered cases.json, in the
composite fixture's form, so the records cross the composite's step): a 1 pL cell on the held
bath. The transporter on its wall patch moves Y (0.25 mM inside, 1 mM in the bath) on held fuel
(ATP 1 mM, ADP and Pi 0.5 mM, every mu°/RT 0, c0 1 mM), so dG_cyc = 0 and J+ = J- = k a S. Run at
0.1 s to 100 s and judged by the tagged judge's own checks (validation/fr50/judge.py) against the
builder's closed form (validation/fr50/closed_forms.py):
- K4-1: each cycle record within 1e-11 of k a S t at every record time;
- K4-2: |net| at most 1e-12 F, and the gap at most 1e-12, on every row;
- K4-3: closure on every row.

One compile, about 25 s on a light CPU. Its reason (D224): the transporter's records are judged on
a compiled run at the registered step, and in a composite, which no other row runs.
"""

import json

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from validation.fr50 import closed_forms, engine, judge

CASES = json.loads(judge.SPEC.read_text())["cases"]
K4 = "K4_transporter_equilibrium"


def test_k4_records_at_equilibrium_are_absolute_with_no_net_and_no_gap():
    reference = closed_forms.k4(K4, CASES[K4])
    (dt,) = judge.STEPS["K4"]
    end = float(reference.times_raw[-1])
    spec = parse_spec(engine.transporter_world(CASES[K4], dt=float(dt), end=end, inner=False))
    result = run(spec)
    rows = engine.transporter_rows(result, dt)
    assert rows["F"][-1] > 0 and rows["B"][-1] > 0
    for check in (
        judge.check_absolute(reference, rows, dt),
        judge.check_net_and_gap(rows),
        judge.check_closure(rows),
    ):
        assert check["passed"], check
