"""FR-50's phase-2 compiled row for World 2 (fr50-one-way-records-v1 §3 and §5; D224): @3's own
one-way records in the composite fixture's form (no operator), so the records cross the
composite's step (the lead's ruling 3, 26 November 2026). Two cells joined by a junction carrying
S (E2) and their nodes joined by a face carrying S (E3), at equal concentrations and potentials,
built from the registered cases.json (validation/fr50/engine) and judged by the tagged judge's own
checks against the builder's closed forms: each record within 1e-11 of its closed form at every
record time, its gap at most 1e-12, closure on every row. It runs 1,000 steps of 5 ms, to 5 s,
with the closed forms every 0.5 s: the registered horizon (100 s, 20,000 steps) is the judged
run's, and its steady records are the same at any time.

One compile, about 25 s on a light CPU. Its reason (D224): the composite's step is the second path
that runs the records, and no other row runs it.
"""

import json

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from validation.fr50 import closed_forms, engine, judge

CASES = json.loads(judge.SPEC.read_text())["cases"]
FR50 = engine._cases()
REFERENCES = {ref.case_kind: ref for ref in closed_forms.phase_2(CASES).values()}


def test_world_2_s_records_cross_the_composite_s_step_absolute_and_closed():
    """E2-1 to E2-3 and E3-1 to E3-3 at the engine's step, in the composite fixture's form."""
    dt, times = engine.PHASE_2_STEPS["world_2"], [str(0.5 * i) for i in range(11)]
    raw = engine.world_2(FR50["E2"], FR50["E3"], dt=float(dt), end=5.0, inner=False)
    assert raw["model"]["id"] == "cells.model.resolved_pump_composite@1"
    result = run(parse_spec(raw))
    for kind, build in (("E2", closed_forms.e2), ("E3", closed_forms.e3)):
        ref = build(REFERENCES[kind].case_id, REFERENCES[kind].declared, times=times)
        rows = engine.own_rows(result, dt, engine.PAIRS[kind])
        assert rows["F"][-1] > 0 and rows["B"][-1] > 0
        for name, check in dict(
            absolute=judge.check_absolute(ref, rows, dt),
            gap=judge.check_gap(rows),
            closure=judge.check_closure(rows),
        ).items():
            assert check["passed"], (kind, name, check)
