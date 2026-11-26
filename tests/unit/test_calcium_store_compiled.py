"""The one-cell store world, compiled (docs/CALCIUM_STORE_AND_CHANNELS_DESIGN.md, section 14, row
13): validation/calcium_store/worlds.py's store_world, of the registered laws, its store starting
at -5 mV. Ten steps in two windows meet every criterion of tests/calcium_store_fixtures.py; a
restart from the written checkpoint repeats the second window bit for bit; and the first window's
end, imported as a new definition, continues the run (planted: the store's charge anchor dropped,
so its voltage starts at 0). Planted in the criteria, each missed: a pump without its voltage,
the exchanger's two ions exchanged, one patch's capacitance 0.01% off. The first window's rows
are also those of row 12's NumPy steps, to rounding. With a pool's path on its calcium channel the
world conducts calcium exactly on the path (planted: the base alone, the path one event early or
late), and a restart between two switches repeats the rest bit for bit.

Seconds: 45 to 60 on the shared CPUs, of which 30 to 45 are its one compile (a window's program,
which the restarts, the import and the driven world reuse), so tier 2; the driven world's part is
4. The reason (D224): a closed world with a store, the store's charge anchor, a gated release and
a restart are in no other row's one program, and a driven world with a store is in no other row.
"""

import copy
import math

import numpy as np
import pytest

from cells.assembly_pool import resolve, schedule
from cells.definitions.specs import parse_spec
from cells.execution.windows import iter_windows
from tests import calcium_store_fixtures as rows
from tests.unit.test_assembly_pool import DRIVING, LEVELS
from tests.unit.test_composed_worlds import OBSERVABLE, conducts, held
from validation.calcium_store import worlds


@pytest.fixture(scope="module")
def one():
    return rows.run_one()


def test_the_store_world_moves_as_its_equations_and_restarts(one, tmp_path):
    v = one.column("membrane_voltage_V")[:, list(one.patches).index("bounding_0")]
    assert v[0] == pytest.approx(worlds.STORE_VOLTAGE_V, abs=1e-12)
    assert abs(v[-1]) < abs(v[0])  # The store's voltage relaxes.
    rows.agrees(one)
    rows.restarts(one, tmp_path)


def test_the_compiled_steps_are_the_numpy_steps(one):
    """Row 12's steps (host_step) are these: five of them, every field of every row, to rounding.
    Planted: a step longer by 1e-9 of itself."""

    def off(dt):
        model, state, control, p = rows.bound(one.spec)
        history, worst = one.windows[0].history, 0.0
        for k in range(1, rows.WINDOW + 1):
            state, valid = rows.host_step(model, state, dt, control, p)
            assert valid
            for name, value in state._asdict().items():
                compiled = np.asarray(getattr(history, name))[k]
                size = np.max(np.abs(compiled), initial=0.0)
                if size > 0:
                    worst = max(worst, np.max(np.abs(np.asarray(value) - compiled)) / size)
        return worst

    assert off(rows.DT) <= 1e-12 < off(rows.DT * (1 + 1e-9))


def imported(run, *, anchor=True):
    """A definition that starts at the run's first window's end: its amounts, charges and gates. The
    store's charge is dropped where anchor is False, and the outside node takes what keeps the world
    closed."""
    raw, row = copy.deepcopy(run.raw), rows.WINDOW
    amounts, v, charges = run.amounts(), run.potentials(), {}
    for p in raw["model"]["membranes"]:
        q = p["capacitance_F"] * (v[p["inside"]][row] - v[p["outside"]][row])
        charges[p["inside"]] = charges.get(p["inside"], 0.0) + q
        charges[p["outside"]] = charges.get(p["outside"], 0.0) - q
    if not anchor:
        charges["outside"] += charges["store_0"]
        charges["store_0"] = 0.0
    for node in (*raw["model"]["cells"], *raw["model"]["extracellular"]):
        n = dict(zip(run.species, amounts[node["id"]][row].tolist(), strict=True))
        node["initial_amount_fmol"], node["initial_charge_C"] = n, charges[node["id"]]
        node["fixed_charge_equivalent_fmol"] = charges[node["id"]] / worlds.CHARGE_PER_FMOL
        node["fixed_charge_equivalent_fmol"] -= math.fsum(
            worlds.VALENCE[s] * amount for s, amount in n.items()
        )
    gates = run.column("channel_gate")[row]
    for k, channel in enumerate(raw["model"]["channels"]):
        channel["initial_gate"] = gates[:, k].tolist()
    raw["experiment"]["end_time"] = rows.WINDOW * rows.DT
    raw["experiment"]["observation_times"] = [k * rows.DT for k in range(rows.WINDOW + 1)]
    return raw


def test_the_first_windows_end_imports_with_its_store_charge(one):
    """A world whose routes charge its store resumes from its own state, the store's charge with it
    (refusal 5's reason)."""
    later = one.column("membrane_voltage_V")[rows.WINDOW :]
    amounts = one.column("extracellular_amount")[rows.WINDOW :]
    for anchor in (True, False):
        (window,) = iter_windows(parse_spec(imported(one, anchor=anchor)), rows.POLICY)
        volts = np.max(np.abs(np.asarray(window.observations.membrane_voltage_V) - later))
        assert (volts <= 1e-9) == anchor, volts
        if anchor:
            moved = np.abs(np.asarray(window.observations.extracellular_amount) - amounts)
            assert np.max(moved) <= 1e-11


def test_planted_criteria_of_the_store_world_miss(one):
    assert "store_pump_0" in rows.misses_moved(one, voltage_dropped=True)
    assert set(rows.misses_moved(one, ions_exchanged=True)) == {"exchanger_0"}
    assert rows.misses_potentials(one, capacitance=1.0001)


def test_a_pool_on_its_calcium_channel_drives_the_world_and_restarts(one):
    """The world resolved with a path of a pool, a switch each 9.7 us, and run by the same program.
    The pool's own rows hold how its kernel gives a path (test_assembly_pool.py)."""
    ionic = copy.deepcopy(one.raw)
    end = ionic["experiment"]["end_time"]
    ionic["experiment"]["observation_times"] = [0.0, end]
    ionic["execution"]["max_steps"] = 200  # Ten steps and the switches.
    pool = DRIVING | dict(
        model="cells.model.finite_bond_assembly@1", seed=2027, worlds=1, end_time_s=end
    )
    entry = dict(channels=["channel_0"], observable=OBSERVABLE, levels=dict(LEVELS), pool=pool)
    composed = resolve.parse_composed(dict(schema_version=1, ionic=ionic, pools=[entry]))
    times = [k * 9.7e-6 for k in range(13)]
    levels = [1.0 - k % 2 for k in range(13)]
    path = list(zip(times, levels, strict=True))
    given = schedule.SwitchPath(tuple(times), tuple(levels), tuple(range(13)), end, 12)
    spec = resolve.resolve_world(composed, 0, [given]).spec

    windows = list(iter_windows(spec, rows.POLICY))
    ca = list(spec.model.species_ids).index("Ca")
    clock = np.concatenate([w.times[k > 0 :] for k, w in enumerate(windows)])
    moved = np.concatenate(
        [np.asarray(w.history.channel_transferred)[k > 0 :, ca, 0] for k, w in enumerate(windows)]
    )
    assert conducts(clock, moved, lambda t: held(path, t))
    early = [(times[max(i - 1, 0)], level) for i, level in enumerate(levels)]
    late = [(0.0, 1.0), *zip((*times[2:], end), levels[1:], strict=True)]
    for wrong in ([(0.0, 1.0)], early, late):
        assert not conducts(clock, moved, lambda t, p=wrong: held(p, t))

    start = windows[0].final
    assert times[1] < start.time < times[-1]
    again = list(iter_windows(spec, rows.POLICY, start))
    for mine, whole in zip(again, windows[1:], strict=True):
        for name in type(whole.history)._fields:
            assert rows.bits(getattr(mine.history, name)) == rows.bits(getattr(whole.history, name))
