"""FR-33's region export and passive tracer (validation/regions), run on the FR-7 lane's example
world with its transferred species also cleared and made in the cell
(validation/regions/example.py).

Two compiled worlds: the example's, 500 steps of 1 ms shared by the first two rows, and the
reviewer's two-node diffusion, 100 steps of 0.01 s, for the third. Their cost and reason (D224): two
compiles, about a minute on the timed lane. They keep the region export's quantities and the
tracer's cohorts working against their identities and closed forms, and keep the tracer refusing a
two-way movement its net records cannot see.

The tracer's error at the mixing node is its trapezoid split's, second order in dt, and set by the
inflow within a step relative to the node's amount (validation/regions/readouts.py, "Its limit").
The bounds below hold the measured errors with a margin. Without inflow its split is exact.
"""

import math

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.registry.models import get_model
from validation.compartment_transfer import example as base
from validation.regions import example, readouts


@pytest.fixture(scope="module")
def run():
    return example.run()


@pytest.fixture(scope="module")
def out(run):
    return example.exports(run)


def _close(a, b, scale):
    return abs(a - b) <= 1e-12 * scale + 1e-18


def test_the_region_export_keeps_its_identities(run, out):
    st, sd = out["ST"], out["SD"]
    for rows in (st, sd):
        assert len(rows["times"]) >= 10
        for inside, outside, whole in zip(rows["inside_fmol"], rows["outside_fmol"],
                                          rows["whole_cell_fmol"], strict=True):  # fmt: skip
            assert _close(inside + outside, whole, whole)
    # ST over [ecs_0]: the region's decrease is the release, and the cell's loss and production,
    # outside the region, change the whole cell.
    a0 = st["inside_fmol"][0]
    for k in range(len(st["times"])):
        assert _close(a0 - st["inside_fmol"][k], st["transfer_fmol"]["release"][k], a0)
        assert st["loss_fmol"][base.NODE_T][k] == 0.0
        net = st["loss_fmol"][base.CELL][k] - st["produced_fmol"][base.CELL][k]
        assert _close(st["whole_cell_fmol"][0] - st["whole_cell_fmol"][k], net, a0)
    assert st["transfer_fmol"]["release"][-1] > 0.3 * a0 and st["loss_fmol"][base.CELL][-1] > 0
    # SD over [ecs_1], local destruction: the region's decrease is its loss, and nothing moves.
    d0 = sd["inside_fmol"][0]
    assert sd["transfer_fmol"] == {}
    for k in range(len(sd["times"])):
        lost = sd["loss_fmol"][base.NODE_D][k]
        assert _close(d0 - sd["inside_fmol"][k], lost, d0)
        assert _close(sd["whole_cell_fmol"][0] - sd["whole_cell_fmol"][k], lost, d0)
    # A region of two nodes, the cell and ecs_1: the release flows into it.
    spec, times, states = run
    two = readouts.region_rows(spec, times, states, base.ST, [base.CELL, base.NODE_D],
                               samples=st["times"])  # fmt: skip
    for k in range(len(two["times"])):
        assert _close(two["inside_fmol"][k], st["outside_fmol"][k], a0)
        gain = (two["transfer_fmol"]["release"][k] + two["produced_fmol"][base.CELL][k]
                - two["loss_fmol"][base.CELL][k])  # fmt: skip
        assert _close(two["inside_fmol"][k] - two["inside_fmol"][0], gain, a0)
    # A region outside one cell's nodes is refused.
    with pytest.raises(ValueError, match="not the nodes of one cell"):
        readouts.region_rows(spec, times, states, base.ST, [base.NODE_T, "bath"])


def test_the_tracer_names_the_cohort_that_lost_material(run, out, monkeypatch):
    traced, closed, st = out["trace"], out["closed"], out["ST"]
    amount, loss, moved = traced["amount"], traced["loss"], traced["transfer"]
    a0 = amount["from_ecs_0"][base.NODE_T][0]
    # Every node's cohorts sum to the engine's amount there; the cell is the mixing node.
    for k, t in enumerate(traced["times"]):
        if t in st["times"]:
            row = st["times"].index(t)
            for node in (base.CELL, base.NODE_T, base.NODE_D):
                held = sum(amount[c][node][k] for c in amount)
                assert _close(held, st["node_fmol"][node][row], a0)
    # At the mixing node each cohort and its cumulative loss meet the closed forms: the received
    # one, the cell's own, and the made material, labelled pulse, then chase.
    for name, key, bound in (("from_ecs_0", "A", 1e-6), ("in_cell", "B", 5e-6),
                             ("pulse", "pulse", 5e-6), ("chase", "chase", 5e-6)):  # fmt: skip
        scale = max(closed[f"{key}_cell"])
        got, lost = amount[name][base.CELL], loss[name][base.CELL]
        assert max(abs(g - c) for g, c in zip(got, closed[f"{key}_cell"], strict=True)) <= (
            bound * scale
        ), name
        assert max(abs(g - c) for g, c in zip(lost, closed[f"{key}_lost"], strict=True)) <= (
            bound * scale
        ), name
    # The cell's loss is named by cohort: the shares sum to turnover's record there.
    total = sum(loss[c][base.CELL][-1] for c in loss)
    assert math.isclose(total, st["loss_fmol"][base.CELL][-1], rel_tol=1e-12)
    assert loss["unlabelled"][base.CELL][-1] == 0.0 and amount["chase"][base.CELL][0] == 0.0
    # The release carries the donor's one cohort.
    assert math.isclose(moved["from_ecs_0"]["release"][-1], st["transfer_fmol"]["release"][-1],
                        rel_tol=1e-12)  # fmt: skip
    assert moved["in_cell"]["release"][-1] == 0.0
    # Without inflow the split is exact: two cohorts at the donor keep their fractions.
    spec, times, states = run
    split = readouts.trace(spec, times, states, base.ST,
                           {"p30": {base.NODE_T: 0.3}, "p70": {base.NODE_T: 0.7}})  # fmt: skip
    p30, p70 = (np.array(split["amount"][c][base.NODE_T]) for c in ("p30", "p70"))
    assert np.max(np.abs(p30 / (p30 + p70) - 0.3)) <= 1e-14
    # A mover the tracer does not read breaks the closure, and the trace is refused.
    whole = readouts.world_map
    monkeypatch.setattr(readouts, "world_map", lambda s, x: dict(whole(s, x), routes=[]))
    with pytest.raises(ValueError, match="do not close"):
        readouts.trace(spec, times, states, base.ST, example.COHORTS)


def test_a_two_way_movement_the_net_records_cannot_see_is_refused():
    """The reviewer's case (validation/regions/example.py): equal totals exchanging by diffusion."""
    spec = parse_spec(example.two_node_diffusion())
    times, states = readouts.runs(spec)
    with pytest.raises(ValueError, match="face face_lr diffuses it"):
        readouts.trace(spec, times, states, "S", {"label": {"left": 0.9, "right": 0.1}})
    # The explicit label row carries the label through the face's own law: 0.3 fmol on the right.
    _, layout = get_model(spec.model).initial_values(spec)
    labelled = readouts.world_map(spec, "L")
    right = labelled["nodes"].index("right")
    assert abs(times[-1] - 1.0) < 1e-12
    amount = readouts.node_records(spec, layout, states[-1], labelled)[0][right]
    assert abs(amount - 0.3) <= 1e-5
    total = readouts.node_records(spec, layout, states[-1], readouts.world_map(spec, "S"))[0]
    assert abs(total[right] - 1.0) <= 1e-12  # S's own totals never move.
