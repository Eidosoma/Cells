"""FR-50's phase-2 compiled rows (fr50-one-way-records-v1 §3 and §5; D224): @3's own one-way
records (its model key one_way_records) in the registered protocol's two worlds, built from the
registered cases.json (validation/fr50/engine), each row judged by the tagged judge's own checks
(validation/fr50/judge.py) against the builder's closed forms (validation/fr50/closed_forms.py):
- World 1, @3 alone, 1,000 steps of 0.1 ms (the engine's step; the cases register none): one cell
  on the held bath at V = E_K, K crossing by the wall patch's own route (E1) and by a gate-free K
  population under FR-51's block (E4). Each record is within 1e-11 of its closed form at every
  record time, its gap at most 1e-12 and closure holds on every row, and E4's split differs from
  channel_rates' flux by at most 4 ulps of their sum at every row (the kernel closure). A restart
  from a checkpoint written at mid-run (0.05 s) is the uninterrupted run bit for bit, every field,
  the records and the gaps included;
- World 2 in the composite fixture's form (no operator), so the records cross the composite's
  step (the lead's ruling 3, 26 November 2026): two cells joined by a junction carrying S (E2) and
  their nodes joined by a face carrying S (E3), at equal concentrations and potentials. Each
  record is absolute, gap-free and closed, as above. It runs 1,000 steps of 5 ms, to 5 s, with the
  closed forms at every 0.5 s: the registered horizon (100 s, 20,000 steps) is the judged run's,
  and its steady records are the same at any time.

Three compiles (World 1, its resume, World 2), about 75 s on two light CPUs (CPUs 6 and 7).
Their reason (D224): the records are judged on compiled runs, the restart on a written
checkpoint, and the composite's step is the second path that runs them.
"""

import json

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.records.io import load_snapshot, write_snapshot
from validation.fr50 import closed_forms, engine, judge

CASES = json.loads(judge.SPEC.read_text())["cases"]
FR50 = engine._cases()
REFERENCES = {ref.case_kind: ref for ref in closed_forms.phase_2(CASES).values()}


def bits(value):
    return np.asarray(value).tobytes()


@pytest.fixture(scope="module")
def world_1():
    dt = engine.PHASE_2_STEPS["world_1"]
    end = REFERENCES["E1"].times_raw[-1]
    spec = parse_spec(engine.world_1(FR50["E1"], FR50["E4"], dt=float(dt), end=float(end)))
    return dt, spec, run(spec)


def judged(kind, rows, dt, ref=None):
    """{criterion: result} of the absolute, gap and closure checks on one case's rows."""
    ref = ref or REFERENCES[kind]
    return dict(
        absolute=judge.check_absolute(ref, rows, dt),
        gap=judge.check_gap(rows),
        closure=judge.check_closure(rows),
    )


def test_world_1_s_records_are_absolute_closed_and_its_split_closes_to_the_flux(world_1):
    """E1-1 to E1-3 and E4-1 to E4-4 at the engine's step, by the judge's checks."""
    dt, _, result = world_1
    for kind in ("E1", "E4"):
        rows = engine.own_rows(result, dt, engine.PAIRS[kind])
        assert rows["F"][-1] > 0 and rows["B"][-1] > 0
        for name, check in judged(kind, rows, dt).items():
            assert check["passed"], (kind, name, check)
    split = engine.channel_split_rows(result)
    closure = judge.check_kernel_closure(
        split["split_forward"], split["split_backward"], split["channel_flux"],
        [f"n={n}" for n in range(split["channel_flux"].size)],
    )  # fmt: skip
    assert closure["passed"], closure


def test_world_1_restarted_at_mid_run_is_the_uninterrupted_run_bit_for_bit(world_1, tmp_path):
    """E1-R and E4-R (the judge's check_restart) and every field of every row after the checkpoint,
    through a written snapshot."""
    dt, spec, full = world_1
    at = str(REFERENCES["E1"].times[-1] / 2)
    checkpoint = full.checkpoint_at(float(at))
    write_snapshot(tmp_path / "checkpoint", full.spec, checkpoint)
    loaded = load_snapshot(tmp_path / "checkpoint")
    resumed = run(loaded.spec, loaded.checkpoint)
    for a, b in zip(resumed.history, full.history, strict=True):
        assert bits(a) == bits(np.asarray(b)[checkpoint.step_index :])
    state, whole = (
        {k: np.asarray(getattr(r.final.state, k)) for k in type(r.final.state)._fields}
        for r in (resumed, full)
    )
    for kind in ("E1", "E4"):
        rows = engine.own_rows(full, dt, engine.PAIRS[kind])
        after = engine.own_rows(resumed, dt, engine.PAIRS[kind])
        later = after["n"] > checkpoint.step_index
        out = dict(restart=dict(dt_s=dt, from_n=int(checkpoint.step_index),
                                **{q: v[later] for q, v in after.items()},
                                state=state, uninterrupted_state=whole))  # fmt: skip
        request = dict(restart_at_s=at, restart_dt_s=None)
        result = judge.check_restart(REFERENCES[kind], out, {dt: rows}, request)
        assert result["passed"], (kind, result)


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
        for name, check in judged(kind, rows, dt, ref).items():
            assert check["passed"], (kind, name, check)
