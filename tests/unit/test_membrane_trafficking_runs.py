"""Compiled guards of scheduled_membrane_trafficking@1 (FR-2 version 1): T2, T5, T7 and T8 of
docs/MEMBRANE_RETRIEVAL_DESIGN.md §8, through the runner and its host checks (a ledger, domain
or dissipation failure raises). Each check sits beside a planted error it catches.

* T2. A world with zero rates runs bitwise as the same world without the compartments'
  declaration and the operator (membrane state alone). Planted: a rate of 10^-9 of the patch over
  the run differs.
* T5. Retrieval, then recycling, on the dt grid. The plasma Kir and NaV units follow
  N (A_k'/A_k)^e through retrieval, and the record R (A_b'/A_b)^e_r through recycling, at every
  observation. The heat never falls, and every host check holds. Planted: an exponent one part in
  10^6 off is refused.
* T7. Restart before, at and after a schedule change is bitwise, through a written snapshot too.
  A vmapped batch is bitwise against the same worlds in reversed order, and reproduces each
  world's own run to 1e-12 of each field's scale.
* T8. The seven-cell sheet (pumps, Kir, NaV, gated junctions, a held bath per cell), with one pool
  per cell (21 field nodes), a frozen regulatory state at s = 1/2 coupled to every Kir
  population, and retrieval of every plasma patch.
  - The factor and the removal both act on @3's inputs: each Kir population's effective
    abundance-weighted availability is F N(t) / (A rho), with N(t) = N0 A(t)/A0 (e = 1).
  - Planted: the same world without the coupling, and without the retrieval, each moves it off.

The compartments admission is the operators owner's; the development shim admits these worlds until
it is on main (the lead's ruling 12).
"""

import jax
import numpy as np
import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import parse_spec
from cells.execution.batch import BatchSpec, WorldSpec
from cells.execution.runner import run
from cells.execution.vector_windows import run_vector_windowed
from cells.execution.windows import WindowPolicy
from cells.operators import membrane_state
from cells.records.io import load_snapshot, write_snapshot
from cells.registry.models import get_model
from tests import membrane_trafficking_development_shim as shim  # FR-2 DEVELOPMENT SHIM
from validation.tissue import composite_guard as guard
from validation.tissue import membrane_trafficking_fixtures as fx
from validation.tissue import regulated_availability_fixtures as rafx

END = 0.004
TIMES = [0.0, 0.001, 0.002, 0.003, END]
CHANGE = 0.002
# The cycle world runs one step past END, so every resume below leaves two steps or more. A resume
# that leaves one step compiles a scan of one step, which XLA's while-loop simplifier replaces by
# its body; fused differently there, that step rounds as the compiler chooses. The 3 ms resume of
# a 4 ms world differed in the carriers' work at one version of this operator, and was bitwise with
# that pass disabled and at the next version, whose valid steps compute the same arithmetic
# (fr2-retrieval-v1-20261119/probes/restart_one_step.*, reported to the lead).
CYCLE_END = 0.005
CYCLE_TIMES = [*TIMES[:-1], END, CYCLE_END]
E = {"kir_0": 1.0, "nav_0": 0.5}
E_R = {"kir_0": 2.0, "nav_0": 1.0}


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


@pytest.fixture(scope="module", autouse=True)
def admitted():
    """FR-2 DEVELOPMENT SHIM (the lead's ruling 12): removed before the first gate. Once for the
    module, so a run and its restart share one composition (the shim clears the composite's cache,
    and a checkpoint's state type is its composition's)."""
    with shim.admission():
        yield


def cycle(retrieval=0.1, recycling=0.3):
    """One cell: retrieval at `retrieval` of the plasma area per ms until CHANGE, then recycling
    at `recycling` of the pool's declared area per ms."""
    raw = fx.pooled_cells(1, end=CYCLE_END, observation_times=CYCLE_TIMES)
    entry = fx.route(raw, 0, retrieval=E, recycling=E_R)
    plasma = fx.patch(raw, "membrane_0")["area_m2"]
    pool = fx.patch(raw, "pool_membrane_0")["area_m2"]
    rates = (retrieval * plasma / fx.DT, recycling * pool / fx.DT)
    plan = fx.schedule(
        entry["id"], [(0.0, rates[0]), (CHANGE, 0.0)], [(0.0, 0.0), (CHANGE, rates[1])]
    )
    return fx.with_trafficking(raw, [entry], [plan])


@pytest.fixture(scope="module")
def cycle_run(admitted):
    spec = parse_spec(cycle())
    return spec, run(spec)


# ------------------------------------------------------------------ T2: idleness


def test_zero_rates_run_bitwise_as_membrane_state_alone():
    raw = fx.pooled_cells(1, end=END, observation_times=TIMES)
    plain = dict(raw, model=dict(raw["model"], operators=raw["model"]["operators"][:1]))
    entry = fx.route(raw, 0)
    zero = fx.with_trafficking(raw, [entry], [fx.schedule(entry["id"], [(0.0, 0.0)])])
    alone = run(parse_spec(plain))
    idle = run(parse_spec(zero))
    guard.assert_same(alone, idle, history_fields=type(alone.history)._fields)
    # Planted: a rate of 1e-9 of the patch over the run is seen.
    tiny = fx.with_trafficking(
        raw, [entry], [fx.schedule(entry["id"], [(0.0, fx.rate(raw, 0, 1e-9))])]
    )
    moved = run(parse_spec(tiny))
    assert not guard.compare_runs(alone, moved, history_fields=type(alone.history)._fields)["equal"]


# ------------------------------------------------------------------ T5: down-regulation and return


def test_a_scheduled_cycle_follows_the_closed_forms_under_the_host_checks(cycle_run):
    spec, result = cycle_run  # The runner's host checks raise on any ledger or domain failure.
    _, p = get_model(spec.model).initial_values(spec)
    h = result.history
    rows = [type(h)(*(np.asarray(v)[i] for v in h)) for i in range(len(result.times))]
    times = np.asarray(result.times)
    k, b = int(p.trafficking_route_plasma[0]), int(p.trafficking_route_pool[0])

    def area(row, slot):
        return float(membrane_state.area(row, p, xp=np)[slot])

    def units(row):
        return np.asarray(membrane_state.units(row, p, xp=np))

    def record(row):
        return np.asarray(row.trafficking_internalised_units[0])

    turn = int(np.argmin(np.abs(times - CHANGE)))
    e, e_r = np.array(list(E.values())), np.array(list(E_R.values()))

    def worst(exponents):
        out = 0.0
        for row in rows[: turn + 1]:  # Retrieval: N (A_k'/A_k)^e.
            expected = units(rows[0]) * (area(row, k) / area(rows[0], k)) ** exponents[0]
            out = max(out, float(np.max(np.abs(units(row) / expected - 1))))
        for row in rows[turn:]:  # Recycling: R (A_b'/A_b)^e_r.
            expected = record(rows[turn]) * (area(row, b) / area(rows[turn], b)) ** exponents[1]
            out = max(out, float(np.max(np.abs(record(row) / expected - 1))))
        return out

    assert worst((e, e_r)) < 1e-12
    assert worst((e * (1 + 1e-6), e_r)) > 1e-9  # Planted: an exponent off by 1e-6.
    heat = np.asarray(h.trafficking_dissipated_energy_pJ)[:, 0]
    assert np.all(np.diff(heat) >= 0) and heat[-1] > 0
    assert (
        float(h.trafficking_retrieved_m2[-1][0]) > 0 and float(h.trafficking_recycled_m2[-1][0]) > 0
    )
    np.testing.assert_allclose(units(rows[-1]) + record(rows[-1]), units(rows[0]), rtol=1e-13)


# ------------------------------------------------------------------ T7: restart and batches


def test_restart_across_the_schedule_change_is_bitwise(cycle_run, tmp_path):
    spec, value = cycle_run
    names = type(value.history)._fields
    for time in (0.001, CHANGE, 0.003):  # Before, at and after the change (2+ steps left).
        checkpoint = value.checkpoint_at(time)
        resumed = run(spec, checkpoint)
        rows = zip(names, resumed.history, value.history, strict=True)
        for name, a, b in rows:  # Each field named, so a difference says where it is.
            assert np.array_equal(np.asarray(a), np.asarray(b)[checkpoint.step_index :]), (
                time,
                name,
            )
    checkpoint = value.checkpoint_at(0.003)
    write_snapshot(tmp_path / "checkpoint", value.spec, checkpoint)
    loaded = load_snapshot(tmp_path / "checkpoint")
    resumed = run(loaded.spec, loaded.checkpoint)
    for name, a, b in zip(names, resumed.history, value.history, strict=True):
        assert np.array_equal(np.asarray(a), np.asarray(b)[checkpoint.step_index :]), name


def vector_batch(specs):
    worlds = tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs))
    return run_vector_windowed(
        BatchSpec(worlds, len(worlds), 10**6, 2**31), WindowPolicy(4, "checkpoints")
    )


def test_the_vmapped_batch_reproduces_each_world(cycle_run):
    specs = [parse_spec(cycle(retrieval=r)) for r in (0.05, 0.1, 0.15)]
    batch = vector_batch(specs)
    reversed_batch = vector_batch(specs[::-1])
    for i in range(len(specs)):  # World IDs are 1, 2, ... in each batch's order.
        x = batch.worlds[i + 1].final.state
        y = reversed_batch.worlds[len(specs) - i].final.state
        for name in type(x)._fields:
            assert guard.compare_arrays(name, getattr(x, name), getattr(y, name)) is None, name
    for world, spec in zip(batch.worlds, specs, strict=True):
        single = cycle_run[1] if spec == cycle_run[0] else run(spec)
        final = batch.worlds[world].final.state
        for name in type(final)._fields:
            a, b = np.asarray(getattr(final, name)), np.asarray(getattr(single.history, name))[-1]
            scale = np.max(np.abs(b), initial=0.0)
            if name == "trafficking_work_pJ":  # Its terms cancel: their accumulated magnitude.
                terms = np.asarray(single.history.trafficking_energy_magnitude_pJ)[-1]
                scale = max(scale, float(np.max(terms)))
            assert np.max(np.abs(a - b), initial=0.0) <= 1e-12 * scale + 1e-30, (world, name)
        assert np.isfinite(batch.worlds[world].diagnostics["max_energy_balance_error_pJ"])


# ------------------------------------------------------------------ T8: a composed world

HALF = 0.5  # The frozen state's level: F = s on every Kir population.


def sheet(*, coupling=True, retrieval=True):
    raw = rafx.sheet(end=END, observation_times=TIMES)
    n = len(raw["model"]["cells"])
    for i in range(n):
        fx.add_pool(raw, i)
    raw["model"]["operators"] = [
        fx.membrane_state(raw),
        dict(law=fx.COMPARTMENTS, compartments=[fx.compartment(i) for i in range(n)]),
    ]
    if coupling:
        cells = [c["id"] for c in raw["model"]["cells"]]
        kir = [c["id"] for c in raw["model"]["channels"] if c["id"].startswith("kir_")]
        raw = rafx.with_coupling(
            raw,
            species=[rafx.REGULATOR],
            states=[rafx.frozen("s", cells, HALF)],
            couplings=[rafx.fraction("kir", "channel", kir, "s")],
        )
    routes = [fx.route(raw, i, retrieval={f"kir_{i}": 1.0, f"nav_{i}": 0.0}) for i in range(n)]
    rate = 0.1 if retrieval else 0.0
    plans = [
        fx.schedule(r["id"], [(0.0, fx.rate(raw, i, rate, over=END))]) for i, r in enumerate(routes)
    ]
    return fx.with_trafficking(raw, routes, plans)


def test_the_coupling_factor_and_the_retrieval_both_act_on_kir():
    spec = parse_spec(sheet())
    result = run(spec)  # 21 field nodes, under the 64-node cap; every host check holds.
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    kir = [i for i, c in enumerate(spec.model.channels) if c.id.startswith("kir_")]
    h = result.history
    rows = [type(h)(*(np.asarray(v)[t] for v in h)) for t in range(len(result.times))]
    controls = cs.control_values(spec, list(result.times))

    def conducting(row, t):
        """F x availability x abundance x area, per Kir population: @3's conductance factor."""
        control = model.CONTROL_TYPE(*(np.asarray(v)[t] for v in controls))
        view = model.view(p, row, xp=np)
        effective = np.asarray(model.control_view(control, row, p, xp=np).channel)[kir]
        patch = np.asarray(p.channel_membranes)[kir]
        return (
            effective
            * np.asarray(view.channel_abundance)[kir]
            * np.asarray(view.membrane_area)[patch]
        )

    start = conducting(rows[0], 0)
    patch = np.asarray(p.channel_membranes)[kir]
    for t, row in enumerate(rows):
        ratio = (
            np.asarray(membrane_state.area(row, p, xp=np))[patch]
            / np.asarray(p.membrane_area)[patch]
        )
        # e = 1: N(t) = N0 A(t)/A0; the factor F = 1/2 throughout (frozen state).
        np.testing.assert_allclose(conducting(row, t), start * ratio, rtol=1e-12)
    scheduled = np.asarray(controls.channel)[0][kir]
    n0 = np.asarray(p.channel_abundance)[kir] * np.asarray(p.membrane_area)[patch]
    np.testing.assert_allclose(start, HALF * scheduled * n0, rtol=1e-14)
    assert np.all(ratio < 1)  # The retrieval acted.
    # Planted: without the coupling the factor is gone; without the retrieval the removal is.
    for planted, broken in ((sheet(coupling=False), "factor"), (sheet(retrieval=False), "removal")):
        other = parse_spec(planted)
        out = run(other)
        model2 = get_model(other.model)
        _, p2 = model2.initial_values(other)
        last = type(out.history)(*(np.asarray(v)[-1] for v in out.history))
        c2 = cs.control_values(other, [out.times[-1]])
        control = model2.CONTROL_TYPE(*(np.asarray(v)[0] for v in c2))
        view = model2.view(p2, last, xp=np)
        kir2 = [i for i, c in enumerate(other.model.channels) if c.id.startswith("kir_")]
        value = (
            np.asarray(model2.control_view(control, last, p2, xp=np).channel)[kir2]
            * np.asarray(view.channel_abundance)[kir2]
            * np.asarray(view.membrane_area)[np.asarray(p2.channel_membranes)[kir2]]
        )
        assert not np.allclose(value, conducting(rows[-1], len(rows) - 1), rtol=1e-6, atol=0.0), (
            broken
        )
