"""FR-6's A5'': a channel driven through a regulatory state with a per-cell prior.

Planted controls: a swapped prior, one prior for both cells, an ignored prior, and the state
bypassed. Each must depart far beyond the honest second-order stand-in's error; a changed
registered value must be caught.
"""

from __future__ import annotations

import json
import re

import numpy as np
import pytest

from validation.coupling import cells_reference as rc
from validation.fr6.references import a5pp, design, worlds

INP = json.loads(worlds.INPUTS.read_text())
BLK = INP["worlds"]["a5pp_prior"]


@pytest.fixture(scope="module")
def ref():
    return a5pp.reference(BLK, INP["constants"])


def test_the_registered_inputs_equal_their_generator():
    assert INP == json.loads(json.dumps(worlds.build()))
    s0 = {c: cb["state_s1_initial"] for c, cb in BLK["cells"].items()}
    assert s0 == {"a": 0.1, "b": 0.8}
    dose = [cb["regulator_X"] for cb in BLK["cells"].values()]
    assert dose[0] == dose[1]                                 # the same dose in both cells


def test_the_reference_against_an_independent_integration(ref):
    w = worlds.to_world(BLK, INP["constants"])
    rec = tuple(BLK["record_times_s"])
    tight = {k: v / 1000 for k, v in rc.ATOL.items()}
    lsoda = a5pp.observables(rc.simulate(w, BLK["end_s"], record=rec, rtol=1e-12, atol=tight,
                                         method="LSODA"), rec)
    assert np.abs(lsoda["V_V"] - ref["V_V"]).max() < 1e-11
    assert np.abs(lsoda["s"] - ref["s"]).max() < 1e-10
    assert ref["V0_V"] == {"a": -0.06, "b": -0.06}
    assert abs(ref["s"][0, 0] - 0.1) < 1e-15 and abs(ref["s"][0, 1] - 0.8) < 1e-15


def test_the_prior_tells_the_cells_apart_at_every_rung(ref):
    ctrl = a5pp.controls(BLK, INP["constants"], ref)
    honest = []
    for dt in INP["dt_ladder_s"][:2]:
        s = a5pp.stand_in(BLK, dt, INP["constants"])
        honest.append(np.abs(s["V_V"] - ref["V_V"]).max())
    assert 1.9 < np.log2(honest[0] / honest[1]) < 2.1          # second order
    for name in ("s0_swapped", "s0_shared_a", "s0_shared_b", "s0_shared_mean", "s0_ignored",
                 "state_bypassed"):
        assert ctrl[name]["V_V"] > 1e3 * honest[0], name
    assert ctrl["k_on_1pct"]["V_V"] > 10 * honest[0]


def test_the_registered_design_and_values():
    d = json.loads(design.DESIGN_FILE.read_text())
    assert d["inputs"]["git_blob"] == design.git_blob_id(worlds.INPUTS)
    for name in ("s0_swapped", "s0_shared_a", "s0_shared_b", "s0_shared_mean", "s0_ignored"):
        assert all(d["caught_at_margin_10"][name]["V_V"]), name
    orders = d["ladder_stand_in"]["observed_order"]["V_V"]
    assert all(abs(o - 2) < 0.1 for o in orders)
    v = json.loads(design.VALUES_FILE.read_text())
    r = design.jsonable(a5pp.reference(BLK, INP["constants"]))
    assert not design._same(v["V_V"], r["V_V"], "V_V", rtol=1e-8)
    changed = json.loads(json.dumps(v["V_V"]))
    changed[10][1] *= 1 + 1e-6
    assert design._same(changed, r["V_V"], "V_V", rtol=1e-8)


def test_nothing_imports_the_engine():
    for path in sorted(design.HERE.glob("*.py")):
        text = path.read_text()
        assert not re.search(r"^\s*(import cells|from cells)", text, re.M), path
        assert "validation.tissue" not in text, path
