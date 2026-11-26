"""Compiled guards of cells.operator.scheduled_membrane_trafficking@1 (FR-2 version 1): T2 and T5 of
docs/MEMBRANE_RETRIEVAL_DESIGN.md §8, through the runner and its host checks (a ledger, domain
or dissipation failure raises). Each check sits beside a planted error it catches. T7's restart,
T7's batch and T8 have files of their own (_restart, _batch and _sheet), split by cost.

* T2. A world with zero rates runs bitwise as the same world without the compartments'
  declaration and the operator (membrane state alone). Planted: a rate of 10^-9 of the patch over
  the run differs.
* T5. Retrieval, then recycling, on the dt grid (the fixtures' cycle world). The plasma Kir and
  NaV units follow N (A_k'/A_k)^e through retrieval, and the record R (A_b'/A_b)^e_r through
  recycling, at every observation. The heat never falls, and every host check holds. Planted: an
  exponent one part in 10^6 off is refused.
* T5 against the code-blind references (D224): the 48 compiled rows of the cycle world, at each
  observation, on the same run (validation/tissue/membrane_trafficking_comparison.py; a row
  passes when |engine - reference| <= its registered band).

"""

import jax
import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.operators import membrane_state
from cells.registry.models import get_model
from validation.tissue import composite_guard as guard
from validation.tissue import membrane_trafficking_comparison as mc
from validation.tissue import membrane_trafficking_fixtures as fx

END = 0.004
TIMES = [0.0, 0.001, 0.002, 0.003, END]


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


@pytest.fixture(scope="module")
def cycle_run():
    spec = parse_spec(fx.cycle())
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

    turn = int(np.argmin(np.abs(times - fx.CYCLE_CHANGE)))
    e, e_r = np.array(list(fx.CYCLE_E.values())), np.array(list(fx.CYCLE_E_R.values()))

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


# ------------------------------------------------------------------ T5 against the references

COMPILED = [r["id"] for r in mc.rows("compiled_cycle")]


@pytest.fixture(scope="module")
def cycle_layout(cycle_run):
    spec, result = cycle_run
    assert len(result.times) == 6  # One history row per observation, 0 to 5 ms.
    return fx.cycle(), get_model(spec.model).initial_values(spec)[1]


@pytest.mark.parametrize("row", COMPILED)
def test_compiled_cycle_row(cycle_run, cycle_layout, row):
    raw, p = cycle_layout
    r = mc.row_by_id()[row]
    v = mc.verdict(r, mc.compiled_value(r, raw, p, cycle_run[1].history))
    assert v["passed"], (row, v["engine"], v["deviation"], v["band"], v["margin"])
