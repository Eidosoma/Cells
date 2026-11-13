"""Compiled guards of isopotential_partition@1 (docs/CELL_DIVISION_S5_DESIGN.md §8.3).

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
* a bridge closing over 1 ms after an asymmetric division, with a restart at the event.
A few minutes on one core (each run compiles); the tier-1 smoke test is test_partition.py.
"""

import json
import subprocess
import sys
from types import SimpleNamespace

import jax
import numpy as np
import pytest

from cells.core.batch import BatchSpec, WorldSpec
from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.core.vector_windows import run_vector_windowed
from cells.core.windows import WindowPolicy
from cells.io import write_snapshot
from cells.models.registry import get_model
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


def test_a_division_closes_every_check(division_run):
    _, result = division_run
    h, times = result.history, np.asarray(result.times)
    applied = np.asarray(h.division_applied)[:, 0]
    assert not applied[times <= fx.EVENT + 1e-12].any() and applied[times > fx.EVENT + 1e-12].all()
    after = np.flatnonzero(times > fx.EVENT + 1e-12)[0]
    increments = np.asarray(h.amount_increment)[after]
    assert not increments[:, 0].any()  # The parent's increment moved to its daughters.
    moved = np.asarray(h.partition_moved_fmol)[after]
    assert np.array_equal(moved.sum(axis=1), np.zeros(moved.shape[0]))
    heat = np.asarray(h.partition_retired_membrane_heat_pJ)[after]
    assert heat[0] > 0 and not heat[1:].any()
    phase = np.asarray(result.observations.partition_slot_phase)
    assert list(phase[0]) == [1, 0, 0] and list(phase[-1]) == [2, 1, 1]
    lineage = result.summary["lineage"] if hasattr(result, "summary") else None
    assert lineage is None or [r["carrier_id"] for r in lineage] == ["cell_0", "c1", "c2"]


def test_one_to_two_to_four_closes_every_check():
    result = run(parse_spec(world(end=0.005, second=0.003)))
    phase = np.asarray(result.observations.partition_slot_phase)[-1]
    assert list(phase) == [2, 2, 2, 1, 1, 1, 1]  # cell_0, d1, d2 retired; g1 to g4 live.


def test_restart_across_and_after_a_partition_is_bitwise(division_run, tmp_path):
    spec, value = division_run
    for time in (0.001, fx.EVENT, 0.003):  # Before, at and after the event.
        checkpoint = value.checkpoint_at(time)
        resumed = run(spec, checkpoint)
        for a, b in zip(resumed.history, value.history, strict=True):
            assert np.array_equal(np.asarray(a), np.asarray(b)[checkpoint.step_index :]), time
    # A snapshot written after the partition, continued in a fresh process.
    checkpoint = value.checkpoint_at(0.003)
    write_snapshot(tmp_path / "checkpoint", value.spec, checkpoint)
    script = (
        "import jax, numpy as np; jax.config.update('jax_enable_x64', True)\n"
        "from cells.io import load_snapshot\nfrom cells.core.runner import run\n"
        f"loaded = load_snapshot({str(tmp_path / 'checkpoint')!r})\n"
        "result = run(loaded.spec, loaded.checkpoint)\n"
        f"np.savez({str(tmp_path / 'fresh.npz')!r}, "
        "**{k: np.asarray(v) for k, v in zip(type(result.history)._fields, result.history)})\n"
    )
    subprocess.run([sys.executable, "-c", script], check=True, env=None, timeout=600)
    fresh = np.load(tmp_path / "fresh.npz")
    for name, b in zip(type(value.history)._fields, value.history, strict=True):
        assert np.array_equal(fresh[name], np.asarray(b)[checkpoint.step_index :]), name


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
    from cells.io import write_run

    _, value = division_run
    write_run(tmp_path / "run", value)
    manifest = json.loads((tmp_path / "run" / "manifest.json").read_text())
    views = manifest["field_owners"]["views"]
    assert views["active"]["closers"] == [fx.PARTITION]


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
