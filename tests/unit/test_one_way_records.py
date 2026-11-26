"""FR-50's phase-1 compiled rows for the passive routes (fr50-one-way-records-v1 §5; D224): K1 and
K2 in one compiled world with two species, at the two registered steps, and its restart.

The world (validation/fr50/engine.routes_world, from the registered cases.json): a cell and a finite
node, 1 pL each, joined by a 1e-10 m^2 patch. S, at 1e-3 mM on both sides, crosses by a 1e-9 m/s
neutral route at zero net (K1). S2, at 1e-3 mM in the cell and 1e-6 mM in the node, crosses by a
1e-7 m/s one and relaxes at k = 0.02/s (K2). Both routes keep one-way records. Each row is judged
by the tagged judge's own checks (validation/fr50/judge.py) against the builder's closed forms
(validation/fr50/closed_forms.py):
- K1 at 0.1 s: each record within 1e-11 of a c t at every record time; the gap at most 1e-12 and
  closure on every row;
- K2 at 0.1 s and 0.05 s: each record's error falls 3.6-4.4 times between the steps, and the gap's
  3-5 times; the gap at most 1e-5 at 0.05 s; closure on every row of both runs;
- a restart from a checkpoint written at 100 s (0.1 s) is the uninterrupted run bit for bit, every
  field, the records and the gap included.

Three compiles (each step's run, and the resume), about 70 s on a light CPU. Their reason (D224):
FR-50's records are judged on compiled runs at the registered steps, and the restart on a written
checkpoint. The transporter's compiled row (K4) is test_one_way_records_transporter.py, so each file
stays under the tier cap.
"""

import json

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.records.io import load_snapshot, write_snapshot
from validation.fr50 import closed_forms, engine, judge

CASES = json.loads(judge.SPEC.read_text())["cases"]
K1, K2 = "K1_neutral_zero_net", "K2_neutral_relaxation"
END = "200"


def bits(value):
    return np.asarray(value).tobytes()


@pytest.fixture(scope="module")
def runs():
    """{dt: the routes world's run to 200 s}, at each of K2's registered steps."""
    out = {}
    for dt in judge.STEPS["K2"]:
        raw = engine.routes_world(CASES[K1], CASES[K2], dt=float(dt), end=float(END))
        out[dt] = run(parse_spec(raw))
    return out


def rows(runs, route, species):
    return {dt: engine.route_rows(result, dt, route, species) for dt, result in runs.items()}


def test_k1_records_at_zero_net_are_absolute_with_no_gap(runs):
    """K1-1, K1-2 and K1-3 at the registered step, by the judge's checks."""
    reference = closed_forms.k1(K1, CASES[K1])
    (dt,) = judge.STEPS["K1"]
    k1 = rows(runs, 0, "S")[dt]
    for check in (judge.check_absolute(reference, k1, dt), judge.check_gap(k1)):
        assert check["passed"], check
    assert judge.check_closure(k1)["passed"]


def test_k2_records_and_their_gap_converge_at_second_order(runs):
    """K2-1, K2-2 and K2-3, by the judge's checks."""
    reference = closed_forms.k2(K2, CASES[K2])
    k2 = rows(runs, 1, "S2")
    order, gap = judge.check_order(reference, k2), judge.check_gap_order(reference, k2)
    assert order["passed"], order
    assert gap["passed"], gap
    for run_rows in k2.values():
        assert judge.check_closure(run_rows)["passed"]


def test_a_restart_at_100_s_is_the_uninterrupted_run_bit_for_bit(runs, tmp_path):
    """K2-4 (the judge's check_restart on K2's route) and every field of every row after the
    checkpoint, through a written snapshot."""
    dt = judge.STEPS["K2"][0]
    full = runs[dt]
    checkpoint = full.checkpoint_at(float(judge.RESTART["K2"]))
    write_snapshot(tmp_path / "checkpoint", full.spec, checkpoint)
    loaded = load_snapshot(tmp_path / "checkpoint")
    resumed = run(loaded.spec, loaded.checkpoint)
    for a, b in zip(resumed.history, full.history, strict=True):
        assert bits(a) == bits(np.asarray(b)[checkpoint.step_index :])
    after = engine.route_rows(resumed, dt, 1, "S2")
    later = after["n"] > checkpoint.step_index
    state, whole = ({k: np.asarray(getattr(r.final.state, k)) for k in type(r.final.state)._fields}
                    for r in (resumed, full))  # fmt: skip
    out = dict(restart=dict(dt_s=dt, from_n=int(checkpoint.step_index),
                            **{q: v[later] for q, v in after.items()},
                            state=state, uninterrupted_state=whole))  # fmt: skip
    request = dict(restart_at_s=str(judge.RESTART["K2"]), restart_dt_s=dt)
    reference = closed_forms.k2(K2, CASES[K2])
    result = judge.check_restart(reference, out, rows(runs, 1, "S2"), request)
    assert result["passed"], result
