"""FR-33's region export and passive tracer (validation/regions), run on the FR-7 lane's example
world with its transferred species also cleared in the cell (validation/regions/example.py).

One compiled world of 500 steps of 1 ms, shared by both rows. Its cost and reason (D224): one
compile, about 30-60 s on a quiet CPU (88 s on a loaded light CPU). It keeps the region export's
five quantities and the tracer's cohorts working against their identities and closed forms.

The tracer's error at the mixing node is its trapezoid split's, second order in dt. It measured
2.5e-7 of the received cohort's scale and 9.5e-7 of the cell's own, against the bound 5e-6. The
donor, with no inflow, meets its closed form to 5.6e-15.
"""

import math

import numpy as np
import pytest

from validation.compartment_transfer import example as base
from validation.regions import example


@pytest.fixture(scope="module")
def out():
    return example.exports()


def _close(a, b, scale):
    return abs(a - b) <= 1e-12 * scale + 1e-18


def test_the_region_export_keeps_its_identities(out):
    st, sd = out["ST"], out["SD"]
    for rows in (st, sd):
        assert len(rows["times"]) >= 10
        for inside, outside, whole in zip(rows["inside_fmol"], rows["outside_fmol"],
                                          rows["whole_cell_fmol"], strict=True):  # fmt: skip
            assert _close(inside + outside, whole, whole)
    # ST, transfer out of its region: the region's loss is the release; the cell's loss is outside.
    a0 = st["inside_fmol"][0]
    for k in range(len(st["times"])):
        released = st["transfer_fmol"]["release"][k]
        assert _close(a0 - st["inside_fmol"][k], released, a0)
        assert st["loss_fmol"][base.NODE_T][k] == 0.0
        lost = st["loss_fmol"][base.CELL][k]
        assert _close(st["whole_cell_fmol"][0] - st["whole_cell_fmol"][k], lost, a0)
    assert st["transfer_fmol"]["release"][-1] > 0.3 * a0 and st["loss_fmol"][base.CELL][-1] > 0
    # SD, local destruction: its region's decrease is its loss, and nothing is transferred.
    d0 = sd["inside_fmol"][0]
    assert sd["transfer_fmol"] == {}
    for k in range(len(sd["times"])):
        lost = sd["loss_fmol"][base.NODE_D][k]
        assert _close(d0 - sd["inside_fmol"][k], lost, d0)
        assert _close(sd["whole_cell_fmol"][0] - sd["whole_cell_fmol"][k], lost, d0)


def test_the_tracer_names_the_cohort_that_lost_material(out):
    traced, closed = out["trace"], out["closed"]
    assert traced["closure_largest"] <= traced["closure_bound"]
    amount, loss = traced["amount"], traced["loss"]
    a0 = amount["from_ecs_0"][base.NODE_T][0]
    # Every node's cohorts sum to the engine's amount there; the cell is the mixing node.
    st = out["ST"]
    for k, t in enumerate(traced["times"]):
        if t in st["times"]:
            row = st["times"].index(t)
            for node in (base.CELL, base.NODE_T, base.NODE_D):
                held = sum(amount[c][node][k] for c in amount)
                assert _close(held, st["node_fmol"][node][row], a0)
    # The donor holds one cohort, without inflow, so its split is exact.
    assert np.allclose(amount["from_ecs_0"][base.NODE_T], closed["A_ecs0"], rtol=1e-12, atol=0)
    # At the mixing node, each cohort and its cumulative loss meet the closed forms.
    scale_a, scale_b = max(closed["A_cell"]), closed["B_cell"][0]
    for name, key, scale in (("from_ecs_0", "A", scale_a), ("in_cell", "B", scale_b)):
        got, lost = amount[name][base.CELL], loss[name][base.CELL]
        assert max(abs(g - c) for g, c in zip(got, closed[f"{key}_cell"], strict=True)) <= (
            5e-6 * scale
        )
        assert max(abs(g - c) for g, c in zip(lost, closed[f"{key}_lost"], strict=True)) <= (
            5e-6 * scale
        )
    # The cell's loss is named by cohort: the two shares sum to turnover's record.
    total = loss["from_ecs_0"][base.CELL][-1] + loss["in_cell"][base.CELL][-1]
    assert math.isclose(total, st["loss_fmol"][base.CELL][-1], rel_tol=1e-12)
    assert loss["unlabelled"][base.CELL][-1] == 0.0
