"""Compiled guards of S5a's composed worlds (docs/CELL_DIVISION_S5_DESIGN.md §8.1, Q1, Q6, Q9).

Through the runner, whose host checks raise on any ledger, domain or dissipation failure (the
retiring path):
* the furrow world (tests/partition_fixtures.cleft_divided), asymmetric (f 0.75, a 0.6, mismatch
  carriers) with a bridge closing over 1 ms. The furrow and the cleft open at the onset, the
  lumen fills as the furrow grows, the partition moves the furrow's growth to the daughters'
  furrows, which keep growing, and the cleft stays open. Every check closes, and a restart at
  the event is bitwise;
* 1 -> 2 -> 4 with a linear bridge and an injection into d1 until its own division, so the
  bridge carries current. Every check closes, and the bridge retires with the second
  divisions into the record;
* an exponential closure on a terminal division: every check closes, and the aperture is
  a_0 exp(-(t - t_b) / tau) at the records.
A few minutes on one core (each world compiles).
"""

import jax
import numpy as np
import pytest

from cells.core.runner import run
from cells.core.specs import parse_spec
from tests import partition_fixtures as fx

END = 0.004
TIMES = [0.0, fx.ONSET, fx.EVENT, 0.003, END]


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def test_the_furrow_world_runs_through_onset_division_and_closure():
    raw = fx.cleft_divided(
        f=0.75, area_fraction=0.6, carriers={"Na": 0.5, "K": 0.5}, bridge=("linear", 0.001)
    )
    raw["experiment"]["observation_times"] = TIMES
    spec = parse_spec(raw)
    result = run(spec)
    h = result.history
    times = np.asarray(result.times)
    row = {t: int(np.flatnonzero(np.isclose(times, t, rtol=0, atol=1e-12))[0]) for t in TIMES}
    patches = [m.id for m in spec.model.membranes]
    cleft = [c.id for c in spec.model.extracellular].index("cleft")
    furrow, kids = patches.index("furrow"), [patches.index(k) for k in ("furrow_d1", "furrow_d2")]

    def at(field, t):
        return np.asarray(getattr(h, field))[row[t]]

    # The onset at the start of the step leaving 1 ms, the division at the one leaving 2 ms.
    assert [at("insertion_opened", t)[furrow] for t in TIMES] == [0, 0, 1, 1, 1]
    assert [at("division_applied", t)[0] for t in TIMES] == [0, 0, 0, 1, 1]
    lumen = [at("lumen_volume_increment_pL", t)[cleft] for t in TIMES]
    assert lumen[1] == 0 and lumen[2] > 0 and lumen[3] > lumen[2] and lumen[4] > lumen[3]
    area = [at("membrane_area_increment_m2", t) for t in TIMES]
    assert area[2][furrow] > 0 and area[3][furrow] == 0  # Moved to the daughters.
    assert (area[4][kids] > area[3][kids]).all()  # The daughters' furrows keep growing.
    observed = np.asarray(result.observations.lumen_volume_pL)[:, cleft]
    assert observed[0] == 0 and (observed[2:] > fx.CLEFT_PL).all()  # Padding, then the lumen.
    e = [j.id for j in spec.model.junctions].index("bridge_1")
    assert [at("junction_gate", t)[e] for t in TIMES] == [0, 0, 0, 1, 1]
    assert np.asarray(h.bridge_aperture_m)[-1, e] == 0.0
    checkpoint = result.checkpoint_at(fx.EVENT)
    resumed = run(spec, checkpoint)
    for a, b in zip(resumed.history, result.history, strict=True):
        assert np.array_equal(np.asarray(a), np.asarray(b)[checkpoint.step_index :])


def test_one_to_two_to_four_with_a_bridge():
    raw = fx.divided(bridge=("linear", 0.001), second=0.003, end=0.005, injection=1e-12)
    raw["experiment"]["observation_times"] = [0.0, fx.EVENT, 0.003, 0.004, 0.005]
    spec = parse_spec(raw)
    result = run(spec)
    h = result.history
    phase = np.asarray(result.observations.partition_slot_phase)[-1]
    assert list(phase) == [2, 2, 2, 1, 1, 1, 1]  # cell_0, d1, d2 retired; g1 to g4 live.
    e = [j.id for j in spec.model.junctions].index("bridge_1")
    times = np.asarray(result.times)
    first, second = times <= fx.EVENT + 1e-12, times <= 0.003 + 1e-12
    gate = np.asarray(h.junction_gate)[:, e]
    assert not gate[first].any() and (gate[second & ~first] == 1).all() and not gate[~second].any()
    carried = np.asarray(h.junction_transferred)[np.flatnonzero(second)[-1], :, e]
    record = np.asarray(h.partition_retired_junction_transferred_fmol)[-1, :, e]
    assert np.abs(carried).max() > 1e-12 and np.array_equal(record, carried)
    assert not np.asarray(h.junction_transferred)[-1, :, e].any()


def test_an_exponential_closure_on_a_terminal_division():
    tau = 0.0005
    raw = fx.divided(bridge=("exponential", tau))
    raw["experiment"]["observation_times"] = [0.0, fx.EVENT, 0.003, END]
    result = run(parse_spec(raw))
    aperture = np.asarray(result.history.bridge_aperture_m)[:, 0]
    times = np.asarray(result.times)
    expected = fx.APERTURE_M * np.exp(-np.maximum(times - fx.EVENT, 0.0) / tau)
    assert np.allclose(aperture, expected, rtol=1e-13, atol=0)
