"""FR-45's shared site sets compiled, through the runner (D327; the design note's §16.2, on invented
values only, FR-45's first-run rule).

Seconds and reason (D224): about 36 s on one core, measured at landing (the run 16 s, the windows 17 s).
It is the only compiled path through the shared-set half-step and its bookings; the paths FR-45's runs take
(runner.run, windows of one step, a resume) are asserted bitwise against each other, and the wash's
compiled event map is checked alone on a set world. The batch paths are test_site_competition_batch_runs.py's,
split from here to keep each file under the tier cap on one core.

The world (site_occupancy_fixtures.chase_world): ecs_0's own sites, a set of 18 fmol shared by Q1, bound at
its own equilibrium with Q2 at its trace, and Q2. At 0.36 s 0.4 of the liquid is washed for a buffer
holding Q2 at a chase concentration and Q1 at its trace; Q2 then binds and displaces Q1 to the free-site
root of the post-wash totals. Every row passes the runner's host checks (each ledger, the moiety per set,
the dissipation check).
"""

from decimal import Decimal, getcontext

import jax
import numpy as np
import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.execution.windows import WindowPolicy, iter_windows
from cells.operators import wash_schedule as wash
from cells.registry.models import get_model
from validation.tissue import site_occupancy_fixtures as sfx

jax.config.update("jax_enable_x64", True)

V, T_E, RATES = sfx.CHASE_VOLUME_pL, sfx.CHASE_WASH_S, sfx.CHASE_RATES


def _fields(history, k):
    return [np.asarray(v)[k] for v in history]


def _root(totals, K, S):
    getcontext().prec = 40
    lo, hi = Decimal(0), Decimal(S)
    for _ in range(200):
        r = (lo + hi) / 2
        f = r + sum(
            Decimal(n) * r / (Decimal(k) * Decimal(V) + r) for n, k in zip(totals, K, strict=True)
        )
        lo, hi = (lo, r) if f > Decimal(S) else (r, hi)
    return float((lo + hi) / 2)


@pytest.fixture(scope="module")
def ran():
    spec = parse_spec(sfx.chase_world())
    result = run(spec)  # Its host checks run on every accepted row; a failure raises.
    return spec, result


def test_bind_wash_unbind_keeps_every_book_and_meets_the_post_wash_root(ran):
    spec, result = ran
    _, p = get_model(spec.model).initial_values(spec)
    h = result.history
    steps = len(result.times)
    R = np.asarray(p.site_free_anchor_fmol) + np.asarray(h.site_free_increment_fmol)
    B = np.asarray(p.site_bound_anchor_fmol) + np.asarray(h.site_bound_increment_fmol)
    S = float(np.asarray(p.site_set_capacity_fmol)[0])
    eps = np.finfo(float).eps
    k = np.arange(steps)
    assert np.all(np.abs(R[:, 0] + B.sum(axis=1) - S) <= 16 * eps * (k + 1) * S)  # The moiety.
    node = [c.id for c in spec.model.extracellular].index("ecs_0")
    ids = list(spec.model.species_ids)
    for j, g in enumerate(("Q1", "Q2")):  # free + bound + collected - supplied, per ligand.
        row = ids.index(g)
        free = (
            np.asarray(p.extracellular_amount_reference)[row, node]
            + np.asarray(h.extracellular_amount_increment)[:, row, node]
        )
        collected = np.asarray(h.wash_collected_fmol)[:, row, node]
        supplied = np.asarray(h.wash_supplied_fmol)[:, row, node]
        books = free + B[:, j] + collected - supplied
        assert np.all(np.abs(books - books[0]) <= 1e-12), g  # fmol (the plan's §4); ~2e-14 seen.
    # The end state is the free-site root of its own totals, to the relaxation's 1e-9.
    end = steps - 1
    free_end = [np.asarray(p.extracellular_amount_reference)[ids.index(g), node]
                + np.asarray(h.extracellular_amount_increment)[end, ids.index(g), node]
                for g in ("Q1", "Q2")]  # fmt: skip
    totals = [float(free_end[j] + B[end, j]) for j in range(2)]
    K = [d / k_on for k_on, d in (RATES["bait"], RATES["chase"])]
    assert abs(R[end, 0] - _root(totals, K, S)) <= 1e-9 * S
    assert B[end, 1] > B[0, 1] and B[end, 0] < B[0, 0]  # Q2 displaced Q1.


def test_the_compiled_event_map_keeps_every_set_bit_for_bit(ran):
    spec, result = ran
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    node = [c.id for c in spec.model.extracellular].index("ecs_0")
    applied = np.asarray(result.history.wash_applied)[:, node]
    k = int(np.flatnonzero(applied == 0)[-1])  # The last row before the wash.
    assert applied[k + 1] == 1
    state = model.STATE_TYPE(*_fields(result.history, k))
    controls = cs.control_values(spec, [T_E])
    control = type(controls)(*(np.asarray(v[0]) for v in controls))
    after, ok = jax.jit(lambda s, c: wash.apply_events(s, c, p))(state, control)
    assert bool(ok) and np.asarray(after.wash_applied)[node] == 1
    for name in ("site_free_increment_fmol", "site_bound_increment_fmol"):
        assert (
            np.asarray(getattr(after, name)).tobytes() == np.asarray(getattr(state, name)).tobytes()
        )
    assert np.asarray(after.wash_collected_fmol)[:, node].sum() > 0


def _one_step_windows(spec, start, stop):
    """{step: [field rows]} of windows of one step from `start` (a checkpoint, or None for the
    definition's start) until the window ending at step `stop`, and the checkpoint at step MID."""
    rows, mid = {}, None
    for window in iter_windows(spec, WindowPolicy(1, "full"), start):
        for i in range(len(window.times)):
            rows[window.start_step + i] = [np.asarray(v)[i] for v in window.history]
        if window.final.step_index == MID:
            mid = window.final
        if window.final.step_index == STOP:
            break  # The rest of the run takes the same code path as these steps.
    return rows, mid


MID, STOP = 3, 40  # The wash is at step 6 (0.36 s): both passes cross it.


def test_windows_of_one_step_and_a_resume_are_the_runs_bits(ran):
    """Windows of one step through the wash (steps 0 to 40), and a resume from the checkpoint at
    step 3 over the same steps, each against runner.run's rows, bit for bit."""
    spec, result = ran
    names = type(result.history)._fields
    history = [np.asarray(v) for v in result.history]
    rows, mid = _one_step_windows(spec, None, STOP)
    assert min(rows) == 0 and max(rows) == STOP and mid is not None
    for step, fields in rows.items():
        for name, a, b in zip(names, fields, (v[step] for v in history), strict=True):
            assert a.tobytes() == b.tobytes(), (step, name)
    resumed, _ = _one_step_windows(spec, mid, STOP)
    assert min(resumed) == MID and max(resumed) == STOP
    for step, fields in resumed.items():
        for name, a, b in zip(names, fields, rows[step], strict=True):
            assert a.tobytes() == b.tobytes(), (step, name)
