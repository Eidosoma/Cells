"""Compiled guards of cells.operator.isopotential_partition@1 (docs/CELL_DIVISION_S5_DESIGN.md §8.3).

Through the runner, whose host checks raise on any ledger, domain or dissipation failure (the
retiring path: every check reads the record added back):
* a 1 -> 2 division closes every check, and the daughters take their halves at the event;
* 1 -> 2 -> 4 closes every check, and the lineage names four granddaughters;
* restart before, at and after the event is bitwise (Q6). So is a restart from a snapshot written
  after the partition and continued in a fresh process;
* mixed batches (Q6): one vector-window program with device checks on every row. It runs worlds
  that differ only by value (event times, a world whose division never happens) and reproduces
  each world's own run to 1e-12 of each field's scale, bitwise against the batch reversed. A
  batch mixing a world with divisions and one without is refused;
* an idle partition (no divisions) runs bitwise as the composition without it (Q7);
* the step-end domain's closer branch under jit, through a stub whose view follows its split;
* the neighbour variant (§8.1): a gated contact to a depolarised neighbour, carrying a real
  history that retires into the record at the division;
* a bridge closing over 1 ms after an asymmetric division, with a restart at the event;
* FR-65 (docs/TURNOVER_CHANGING_VOLUME_DESIGN.md §6.1): S5's furrow world with its lumen and
  cells.operator.scheduled_species_turnover@1 in its cells, keyed by carriers (turnover_run, through
  the closure and restart tests, resumed once, across the division): the pending daughters and the
  retired parent untouched bit for
  bit, S's closed forms from each carrier's birth, every ledger the lumen's included; and the
  declared-mask twin, today's code, which writes S into a pending slot and is refused.
A few minutes on one core (each run compiles); the tier-1 smoke test is test_partition.py.
"""

import json
import subprocess
import sys
from types import SimpleNamespace

import jax
import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.batch import BatchSpec, WorldSpec
from cells.execution.runner import run
from cells.execution.vector_windows import run_vector_windowed
from cells.execution.windows import WindowPolicy
from cells.operators import partition
from cells.records.io import write_snapshot
from cells.registry.models import get_model
from tests import partition_fixtures as fx
from validation.tissue import composite_guard as guard

END = 0.004
TIMES = [0.0, 0.001, fx.EVENT, 0.003, END]


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def world(**kw):
    raw = fx.divided(end=kw.pop("end", END), **kw)
    raw["experiment"]["observation_times"] = TIMES if "second" not in kw else [0.0, 0.004, 0.005]
    return raw


@pytest.fixture(scope="module")
def division_run():
    spec = parse_spec(world())
    return spec, run(spec)


MAKE, CLEAR = 1e-4, 50.0  # fmol/s, 1/s: turnover's S in each cell (k h = 0.025 per half-step).


def turnover_world():
    raw = fx.with_turnover(fx.cleft_divided(end=END), make=MAKE, clear=CLEAR)
    raw["experiment"]["observation_times"] = TIMES
    return raw


@pytest.fixture(scope="module")
def turnover_run():
    """FR-65: S5's furrow world with its lumen, turnover making and clearing S in the parent and in
    each daughter from its birth. Seconds and reason (D224): about 30 s, one compile and 4 steps;
    the partition, insertion@2 and a lumen beside turnover are newly admitted together."""
    spec = parse_spec(turnover_world())
    return spec, run(spec)


@pytest.mark.parametrize("which", ["division_run", "turnover_run"])
def test_a_division_closes_every_check(which, request):
    spec, result = request.getfixturevalue(which)
    h, times = result.history, np.asarray(result.times)
    applied = np.asarray(h.division_applied)[:, 0]
    assert not applied[times <= fx.EVENT + 1e-12].any() and applied[times > fx.EVENT + 1e-12].all()
    after = np.flatnonzero(times > fx.EVENT + 1e-12)[0]
    increments = np.asarray(h.amount_increment)[after]
    assert not increments[:, 0].any()  # The parent's increment moved to its daughters.
    moved = np.asarray(h.partition_moved_fmol)[after]
    assert np.array_equal(moved.sum(axis=1), np.zeros(moved.shape[0]))
    heat = np.asarray(h.partition_retired_membrane_heat_pJ)[after]
    parent = np.zeros(heat.shape, dtype=bool)  # The parent's patches (the furrow world's two).
    parent[[k for k, m in enumerate(spec.model.membranes) if m.inside == "cell_0"]] = True
    assert (heat[parent] > 0).all() and not heat[~parent].any()
    phase = np.asarray(result.observations.partition_slot_phase)
    assert list(phase[0]) == [1, 0, 0] and list(phase[-1]) == [2, 1, 1]
    lineage = result.summary["lineage"] if hasattr(result, "summary") else None
    assert lineage is None or [r["carrier_id"] for r in lineage] == ["cell_0", "c1", "c2"]


def test_one_to_two_to_four_closes_every_check():
    result = run(parse_spec(world(end=0.005, second=0.003)))
    phase = np.asarray(result.observations.partition_slot_phase)[-1]
    assert list(phase) == [2, 2, 2, 1, 1, 1, 1]  # cell_0, d1, d2 retired; g1 to g4 live.


@pytest.mark.parametrize("which", ["division_run", "turnover_run"])
def test_restart_across_and_after_a_partition_is_bitwise(which, request, tmp_path):
    spec, value = request.getfixturevalue(which)
    # Before, at and after the event; turnover's world resumes once, before the event (across it:
    # each resume compiles its own rollout, about 75 s here; the lead's ruling of 26 November).
    for time in (0.001, fx.EVENT, 0.003) if which == "division_run" else (0.001,):
        checkpoint = value.checkpoint_at(time)
        resumed = run(spec, checkpoint)
        for a, b in zip(resumed.history, value.history, strict=True):
            assert np.array_equal(np.asarray(a), np.asarray(b)[checkpoint.step_index :]), time
    if which == "turnover_run":  # The fresh process is the partition's own (one compile more).
        return
    # A snapshot written after the partition, continued in a fresh process.
    checkpoint = value.checkpoint_at(0.003)
    write_snapshot(tmp_path / "checkpoint", value.spec, checkpoint)
    script = (
        "import jax, numpy as np; jax.config.update('jax_enable_x64', True)\n"
        "from cells.records.io import load_snapshot\nfrom cells.execution.runner import run\n"
        f"loaded = load_snapshot({str(tmp_path / 'checkpoint')!r})\n"
        "result = run(loaded.spec, loaded.checkpoint)\n"
        f"np.savez({str(tmp_path / 'fresh.npz')!r}, "
        "**{k: np.asarray(v) for k, v in zip(type(result.history)._fields, result.history)})\n"
    )
    subprocess.run([sys.executable, "-c", script], check=True, env=None, timeout=600)
    fresh = np.load(tmp_path / "fresh.npz")
    for name, b in zip(type(value.history)._fields, value.history, strict=True):
        assert np.array_equal(fresh[name], np.asarray(b)[checkpoint.step_index :]), name


def test_turnover_leaves_closed_slots_untouched_and_follows_each_carrier(turnover_run):
    """FR-65 §4.1 on turnover_run: the pending daughters d1 and d2 untouched bit for bit before
    their birth (S's increment and every turnover field zero), the retired parent untouched after
    its retirement (S's increment zero, its fields held), and S's amount following each carrier's
    closed form from its birth, n_b e^{-k(t - b)} + (P/k)(1 - e^{-k(t - b)}), to the bookings'
    rounding: the parent's from time 0, each daughter's from the share the partition gave it at
    the division (b = EVENT). Planted: a daughter's closed form from time 0 (a slot-keyed rate in
    force before its birth) misses it."""
    spec, result = turnover_run
    h, times = result.history, np.asarray(result.times)
    _, p = get_model(spec.model).initial_values(spec)
    row = list(spec.model.species_ids).index("S")
    anchor = np.asarray(p.amount_reference)[row]
    increment = np.asarray(h.amount_increment)[:, row]
    n = anchor[None, :] + increment
    born = times > fx.EVENT + 1e-12  # Rows after the step whose event divides.
    fields = ("turnover_produced_fmol", "turnover_cleared_fmol", "turnover_work_pJ")
    for slot in (1, 2):  # d1, d2: pending until the division.
        assert not increment[~born, slot].any()
        for name in fields:
            value = np.asarray(getattr(h, name))
            assert not (value[~born, slot] if value.ndim == 2 else value[~born, :, slot]).any()
    assert not increment[born, 0].any()  # The parent's moved to its daughters.
    for name in fields:
        value = np.asarray(getattr(h, name))
        held = value[born, 0] if value.ndim == 2 else value[born, :, 0]
        assert (held == held[0]).all(), name

    def closed(n_b, t, b):
        decay = np.expm1(-CLEAR * (t - b))
        return n_b + n_b * decay - (MAKE / CLEAR) * decay

    bound = 8 * np.finfo(float).eps * 2 * len(times) * float(np.max(n))
    assert np.max(np.abs(n[~born, 0] - closed(n[0, 0], times[~born], 0.0))) <= bound
    moved = np.asarray(h.partition_moved_fmol)[np.flatnonzero(born)[0], row]
    for slot in (1, 2):
        share = anchor[slot] + moved[slot]  # What the division gave the daughter.
        got = closed(share, times[born], fx.EVENT)
        assert np.max(np.abs(n[born, slot] - got)) <= bound, slot
        today = closed(anchor[slot], times[born], 0.0)  # Planted: its rate from time 0.
        assert np.max(np.abs(n[born, slot] - today)) > bound


def w3_divided():
    """FR-43 part 3's divided world (validation/fr43_part3/worlds.divided: membrane state, the
    partition and cells.operator.integer_unit_population@1 on the contact patch, its sites mapped)
    with W3_two_way_turnover's turnover (the spec world's P in the cell, k at the node), the cell
    routes keyed by carriers: the founder cell_0 from 0, c1 and c2 from their birth."""
    from validation.fr43_part3 import worlds as part3
    from validation.tissue import secreted_species_fixtures as ssf

    rates = part3.spec_worlds()["W3_two_way_turnover"]["turnover"]
    make, clear = rates["production_cell_fmol_per_s"], rates["clearance_node_per_s"]
    raw = part3.divided("W3_two_way_turnover")
    (at,) = [e["time"] for e in raw["experiment"]["partition_events"]]
    routes = [(f"make_{c}", c, "production") for c in ("cell_0", "d1", "d2")]
    controls = [("make_cell_0", "cell_0", [(0.0, make)])]
    controls += [(f"make_{d}", c, [(at, make)]) for d, c in (("d1", "c1"), ("d2", "c2"))]
    routes.append(("clear", "ecs_0", "clearance"))
    controls.append(("clear", None, [(0.0, clear)]))
    return ssf.with_turnover(raw, routes, controls), make, at


def test_turnover_beside_the_population_in_a_dividing_cell():
    """D327's check of a composition FR-65 newly admits (FR-43 part 3's co-writers note, §6.3:
    membrane state, the partition, the population and turnover parse together, in either order of
    the last two): W3's turnover in part 3's divided world, one run with every host check on every
    row (each writer's books in S's ledgers). Turnover's production follows the occupant rule
    there: the parent's is P t until the division and then held, each daughter's is P (t - b)
    from its birth b, and the pending daughters' S stays untouched before it. Planted: a
    daughter's production from time 0 misses. Seconds and reason (D224): about 40 s, one compile
    and 5 steps; the four operators are newly admitted together."""
    raw, make, at = w3_divided()
    spec = parse_spec(raw)
    result = run(spec)  # Every host check on every accepted row.
    h, times = result.history, np.asarray(result.times)
    row = list(spec.model.species_ids).index("S")
    produced = np.asarray(h.turnover_produced_fmol)[:, row]
    born = times > at + 1e-12  # Rows after the step whose event divides.
    eps = np.finfo(float).eps
    bound = 8 * eps * len(times) * make * float(times[-1])
    assert np.max(np.abs(produced[~born, 0] - make * times[~born])) <= bound
    assert (produced[born, 0] == produced[np.flatnonzero(born)[0] - 1, 0]).all()  # Held.
    assert not np.asarray(h.amount_increment)[~born, row][:, 1:3].any()
    for slot in (1, 2):
        assert not produced[~born, slot].any()
        assert np.max(np.abs(produced[born, slot] - make * (times[born] - at))) <= bound
        assert np.max(np.abs(produced[born, slot] - make * times[born])) > bound  # Planted.


def test_the_declared_mask_twin_writes_a_pending_slot_and_is_refused():
    """FR-65 §6.1, today's code at run level: turnover reading the declared masks (P2) with the
    daughters' rates in force from time 0 (P3, no leading zero) writes S into the pending slots d1
    and d2 from its first step, and @3's padded-slot domain refuses that step (D150 §5.3), before
    the partition's write at the birth could break S's ledger at a daughter (the design probe's
    hazard, at a rate small enough to pass the domain). turnover_run, the same world with the view's
    masks and the occupant tables, passes every check. Seconds and reason (D224): about 35 s, one
    compile, refused at its first step."""
    from cells.execution.errors import NumericalError
    from cells.operators import species_common as common
    from cells.operators import species_turnover as st

    half_step, tables = st.ScheduledSpeciesTurnover.half_step, common.route_tables

    def declared(self, state, h, control, p, *, xp, labels=None, view=None):
        if view is not None:  # P2: the view's masks replaced by the declared ones.
            view = view._replace(active=p.active, outside_active=p.outside_active)
        return half_step(self, state, h, control, p, xp=xp, labels=labels, view=view)

    def from_zero(*args, **kwargs):  # P3: a pending slot's leading idle entry dropped.
        return [t[1:] if len(t) > 1 and t[0][0] == 0.0 and t[1][0] > 0.0 and not any(t[0][1])
                else t for t in tables(*args, **kwargs)]  # fmt: skip

    jax.clear_caches()
    st.ScheduledSpeciesTurnover.half_step, common.route_tables = declared, from_zero
    try:
        with pytest.raises(NumericalError, match=r"domain failure on \[0\.0, 0\.001\]"):
            run(parse_spec(turnover_world()))
    finally:
        st.ScheduledSpeciesTurnover.half_step, common.route_tables = half_step, tables
        jax.clear_caches()


def vector_batch(specs):
    worlds = tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs))
    return run_vector_windowed(
        BatchSpec(worlds, len(worlds), 10**6, 2**31), WindowPolicy(2, "checkpoints")
    )


def test_a_batch_mixes_worlds_by_value(division_run):
    specs = [
        division_run[0],
        parse_spec(world(at=0.003)),
        parse_spec(world(events=False)),  # Its division never happens.
    ]
    batch, reversed_batch = vector_batch(specs), vector_batch(specs[::-1])
    for k in range(len(specs)):
        x = batch.worlds[k + 1].final.state
        y = reversed_batch.worlds[len(specs) - k].final.state
        for name in type(x)._fields:
            assert guard.compare_arrays(name, getattr(x, name), getattr(y, name)) is None, name
    for k, spec in enumerate(specs):
        single = division_run[1] if k == 0 else run(spec)
        final = batch.worlds[k + 1].final.state
        for name in type(final)._fields:
            a, b = np.asarray(getattr(final, name)), np.asarray(getattr(single.history, name))[-1]
            scale = np.max(np.abs(b), initial=0.0)
            assert np.max(np.abs(a - b), initial=0.0) <= 1e-12 * scale + 1e-30, (k, name)
        assert np.isfinite(batch.worlds[k + 1].diagnostics["max_energy_balance_error_pJ"])


def test_a_batch_mixing_static_structures_is_refused():
    specs = [parse_spec(world()), parse_spec(fx.without_divisions(end=END))]
    with pytest.raises(Exception, match="signature|batch|differ"):
        vector_batch(specs)


def test_an_idle_partition_runs_as_the_composition_without_it():
    a = run(parse_spec(fx.without_divisions(end=END)))
    b = run(parse_spec(fx.without_partition(end=END)))
    for name in type(b.history)._fields:
        assert np.array_equal(
            np.asarray(getattr(a.history, name)), np.asarray(getattr(b.history, name))
        ), name


def test_the_manifest_names_the_closer(division_run, tmp_path):
    from cells.records.io import write_run

    _, value = division_run
    write_run(tmp_path / "run", value)
    manifest = json.loads((tmp_path / "run" / "manifest.json").read_text())
    views = manifest["field_owners"]["views"]
    assert views["active"]["closers"] == [fx.PARTITION]


def test_the_record_is_state_wherever_state_goes(division_run, tmp_path):
    """Q11 on the written run, replayed on the host:
    * the history rows carry the record;
    * check_values on the saved history closes every ledger at the event row;
    * the observer's record columns equal the history's;
    * the summary's totals add the record;
    * the negative control: a replay with the record zeroed fails the local ledger at the
      first row after the event.
    A checkpoint after a partition carries the record too: its restart is bitwise
    (test_restart_across_and_after_a_partition_is_bitwise)."""
    from cells.execution.errors import NumericalError
    from cells.records.io import write_run

    spec, value = division_run
    model = get_model(spec.model)
    write_run(tmp_path / "run", value)
    saved = np.load(tmp_path / "run" / "trajectory.npz")
    history = model.STATE_TYPE(*(saved[name] for name in model.STATE_TYPE._fields))
    times = np.asarray(saved["accepted_times"])
    after = times > fx.EVENT + 1e-12
    record = np.asarray(history.partition_retired_membrane_heat_pJ)
    assert (record[after, 0] > 0).all() and not record[~after].any()
    steps = np.rint(times / fx.DT).astype(int)
    diagnostics = model.check_values(history, spec, steps)
    assert np.isfinite(diagnostics["max_energy_balance_relative"])
    for name in partition.RECORD.values():
        assert np.array_equal(saved[f"observed_{name}"], saved[name]), name
    summary = json.loads((tmp_path / "run" / "summary.json").read_text())
    totals = summary["partition_history_totals"]["membrane_dissipated_energy_pJ"]
    final = model._adjusted(model.STATE_TYPE(*(v[-1] for v in history)), _layout(spec), xp=np)
    assert totals["record"] > 0
    assert totals["total"] == pytest.approx(float(np.sum(final.membrane_dissipated_energy_pJ)))
    blank = history._replace(
        **{k: np.zeros_like(getattr(history, k)) for k in partition.RECORD.values()}
    )
    with pytest.raises(NumericalError, match="accounting failed: local$"):
        model.check_values(blank, spec, steps)


def _layout(spec):
    return get_model(spec.model).initial_values(spec)[1]


def test_the_step_end_domain_runs_on_the_device_with_a_closer():
    """_end_domain's closer branch under jit, through a stub whose view follows its split
    (fx.FollowsSplit): one step before the division and one with the bridge open and closing,
    each valid and bitwise the step of the composition without the stub."""
    spec = parse_spec(world(bridge=("linear", 0.001)))
    plain, follower = get_model(spec.model), fx.with_follower(spec)
    state, p = plain.initial_values(spec)
    partition_op = next(op for op in plain.operators if op.LAW_ID == fx.PARTITION)
    born, ok = partition_op.event(
        state,
        SimpleNamespace(partition_due=np.ones(1)),
        p,
        xp=np,
        view=lambda s: plain.view(p, s, xp=np),
    )
    assert ok
    steps = [jax.jit(lambda s, c, q, m=m: m.split_step(s, fx.DT, c, q)) for m in (plain, follower)]
    for start, time in ((state, 0.0), (born, fx.EVENT)):
        values = fx.cs.control_values(spec, [time])
        control = plain.CONTROL_TYPE(*(np.asarray(v[0]) for v in values))
        results = [step(start, control, p) for step in steps]
        (a, valid_a), (b, valid_b) = results
        assert bool(valid_a) and bool(valid_b), time
        for name in type(a)._fields:
            assert np.array_equal(np.asarray(getattr(a, name)), np.asarray(getattr(b, name))), name


def test_a_neighbour_contact_runs_through_the_division():
    """§8.1's variant on the device: the gated contact to a depolarised neighbour carries
    current and its gate moves; at the division it maps to the daughters (their gates the
    parent's, the parent's padding after it), its history retires into the record, and every
    check closes."""
    result = run(parse_spec(world(neighbour=True)))
    h, times = result.history, np.asarray(result.times)
    gate = np.asarray(h.junction_gate)  # [contact, contact_d1, contact_d2]
    before, after = times <= fx.EVENT + 1e-12, times > fx.EVENT + 1e-12
    assert (gate[before, 0] > 0).all() and not gate[before, 1:].any()
    assert gate[before, 0][-1] < gate[0, 0]  # The gate closes towards its minimum.
    assert not gate[after, 0].any() and (gate[after, 1:] > 0).all()
    transferred = np.asarray(h.junction_transferred)  # [time, species, edge]
    carried = np.abs(transferred[before][-1, :, 0]).max()
    assert carried > 1e-9  # fmol, far above rounding (about 1e-19 at this scale).
    record = np.asarray(h.partition_retired_junction_transferred_fmol)[after][0][:, 0]
    assert np.array_equal(record, transferred[before][-1, :, 0])  # Retired whole at the event.
    assert not transferred[after][:, :, 0].any()
    assert np.abs(transferred[-1, :, 1:]).max() > 1e-9  # The daughters' contacts carry.


def test_a_bridge_closes_through_the_run_and_restarts_bitwise():
    """An asymmetric division (unequal daughters, so the bridge carries current) whose bridge
    closes linearly over 1 ms on the device: every check closes, the bridge's gate is padding
    before the event and open after, its aperture reaches 0, and a restart at the event is
    bitwise."""
    raw = world(f=0.75, area_fraction=0.6, carriers={"Na": 0.5, "K": 0.5}, bridge=("linear", 0.001))
    spec = parse_spec(raw)
    result = run(spec)
    times = np.asarray(result.times)
    e = [j.id for j in spec.model.junctions].index("bridge_1")
    gate = np.asarray(result.history.junction_gate)[:, e]
    after = times > fx.EVENT + 1e-12
    assert not gate[~after].any() and (gate[after] == 1).all()
    aperture = np.asarray(result.history.bridge_aperture_m)[:, e]
    assert (aperture[~after] == fx.APERTURE_M).all() and aperture[-1] == 0.0
    transferred = np.asarray(result.history.junction_transferred)[:, :, e]
    assert np.abs(transferred[-1]).max() > 0  # Current crossed the bridge before it closed.
    checkpoint = result.checkpoint_at(fx.EVENT)
    resumed = run(spec, checkpoint)
    for a, b in zip(resumed.history, result.history, strict=True):
        assert np.array_equal(np.asarray(a), np.asarray(b)[checkpoint.step_index :])
