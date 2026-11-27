"""FR-45's shared site sets compiled, through the runner (D327; the design note's §16.2, on invented
values only, FR-45's first-run rule).

Seconds and reason (D224): about 60 s on two cores, measured at landing (the batch and vector row 31 s,
the windows 15 s, the run 11 s). It is the only compiled path through the shared-set half-step and its
bookings; the paths FR-45's runs take (runner.run, windows of one step, a resume) and the batch paths
(run_batch, run_vector_windowed) are asserted bitwise against each other; and the wash's compiled event
map is checked alone on a set world.

The world: a 0.75 uL node's own sites, a set of 18 fmol shared by Q1, bound at its own equilibrium with Q2
at its trace, and Q2. At 0.4 s 0.4 of the liquid is washed for a buffer holding Q2 at a chase
concentration and Q1 at its trace; Q2 then binds and displaces Q1 to the free-site root of the post-wash
totals. Every row passes the runner's host checks (each ledger, the moiety per set, the dissipation check).
"""

from decimal import Decimal, getcontext

import jax
import numpy as np
import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import parse_spec
from cells.execution.batch import BatchSpec, WorldSpec, run_batch
from cells.execution.runner import run
from cells.execution.vector_windows import run_vector_windowed
from cells.execution.windows import WindowPolicy, iter_windows
from cells.operators import site_occupancy as so
from cells.operators import wash_schedule as wash
from cells.registry.models import get_model
from validation.tissue import site_occupancy_fixtures as sfx
from validation.tissue import wash_schedule_fixtures as wfx

jax.config.update("jax_enable_x64", True)

V, S_FMOL, DT, T_E, END, F = 7.5e5, 18.0, 0.08, 0.4, 16.0, 0.4
RATES = {"bait": (4e4, 2.0), "chase": (6e4, 0.4)}  # k_on per mM per s, k_off per s.
THETA = 0.4  # Q1's start, at its own equilibrium with Q2 at its trace.
CHASE_mM = 1.5e-4


def world(chase_mM=CHASE_mM):
    k1, d1 = RATES["bait"]
    pops = [sfx.member("bait", ligand="Q1", k_on=k1, k_off=d1, theta0=THETA),
            sfx.member("chase", ligand="Q2", k_on=RATES["chase"][0], k_off=RATES["chase"][1])]  # fmt: skip
    copies = S_FMOL * so.SITES_PER_FMOL / 0.5
    raw = sfx.set_world(pops, [sfx.site_set(node="ecs_0", copies=copies)],
                        node_mM={"Q1": (d1 / k1) * THETA / (1 - THETA)}, volume=V, dt=DT, end=END,
                        observation_times=[0.0, T_E, END])  # fmt: skip
    buffer = {wfx.TRACER: sfx.TRACE_mM, "Q1": sfx.SET_TRACE_mM, "Q2": chase_mM}
    return wfx.with_wash(raw, ["ecs_0"], [(T_E, "ecs_0", F, buffer)])


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
    spec = parse_spec(world())
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
        scale = free + B[:, j] + collected + supplied
        assert np.all(np.abs(books - books[0]) <= 16 * eps * (k + 1) * scale), g
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


def test_windows_of_one_step_and_a_resume_are_the_runs_bits(ran):
    spec, result = ran
    names = type(result.history)._fields
    rows, mid = {}, None
    for window in iter_windows(spec, WindowPolicy(1, "full")):
        for i in range(len(window.times)):
            rows[window.start_step + i] = [np.asarray(v)[i] for v in window.history]
        if window.final.step_index == 150:
            mid = window.final
    history = [np.asarray(v) for v in result.history]
    for step, fields in rows.items():
        for name, a, b in zip(names, fields, (v[step] for v in history), strict=True):
            assert a.tobytes() == b.tobytes(), (step, name)
    resumed = {}
    for window in iter_windows(spec, WindowPolicy(1, "full"), mid):
        for i in range(len(window.times)):
            resumed[window.start_step + i] = [np.asarray(v)[i] for v in window.history]
    assert min(resumed) == 150 and max(resumed) == len(result.times) - 1
    for step, fields in resumed.items():
        for name, a, b in zip(names, fields, rows[step], strict=True):
            assert a.tobytes() == b.tobytes(), (step, name)


def test_a_two_world_batch_and_vector_windows_are_the_scalar_runs_bits(ran):
    """The batch paths (D327's ruling 2): the world beside a second world of another chase,
    through run_batch and run_vector_windowed; the first is the scalar run's bits on every row,
    the second the same on both paths and its own (its books are the paths' host checks)."""
    spec, result = ran
    other = parse_spec(world(chase_mM=2.6e-4))
    batch = BatchSpec((WorldSpec(1, spec), WorldSpec(2, other)), 2, 2**53 - 1, 2**53 - 1)
    batched = run_batch(batch)
    names = type(result.history)._fields
    for name in names:
        a, b = (
            np.asarray(getattr(batched.worlds[1].history, name)),
            np.asarray(getattr(result.history, name)),
        )
        assert a.tobytes() == b.tobytes(), name
    bound = [np.asarray(batched.worlds[w].final.state.site_bound_increment_fmol) for w in (1, 2)]
    assert not np.array_equal(*bound)  # Two worlds, not one copied.
    vector = run_vector_windowed(batch, WindowPolicy(64, "checkpoints"))
    for w, reference in ((1, result.final), (2, batched.worlds[2].final)):
        final = vector.worlds[w].final
        assert final.step_index == reference.step_index
        for name, a, b in zip(names, final.state, reference.state, strict=True):
            assert np.asarray(a).tobytes() == np.asarray(b).tobytes(), (w, name)
