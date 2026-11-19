"""Beard 2005 reproduced by the independent reference (tier 3 by measurement).

The published arm runs at the declared inputs: the 2006 Table 1, Eq. 24 with Eq. 7's
proton term (Q02: what the published curves were computed with), T = 298.15 K, the matrix Mg2+ total at 1 mM, and the matrix charge anchored to Fig. 4D's
pH at [Pi]e = 0. It is checked against the published model curves of Figs. 4-5 and the
text's P50, within this reference's documented reproduction bands. The integrator must
match the exact Newton solve. Three planted controls must be caught: the 2005 Table 1,
the web XML's stale proton row, and the 2005 k_O2.

It costs about 1-2 minutes on one free core. It runs two integrations, about 40
50-digit Newton solves, and one low-oxygen sweep. The cost was measured at landing.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from validation.mitochondria.references import model as M
from validation.mitochondria.references import reproduce as R

TARGETS = json.loads(R.TARGETS.read_text())

# Documented reproduction bands of the published arm against the digitised published curves
# (|reproduced - published|, per quantity and state; README "Reproduction"). They are this
# reference's status, not an engine tolerance.
BANDS = {
    ("NADH_frac", "state4"): 0.006, ("NADH_frac", "state3"): 0.02,
    ("MVO2_per_cyta", "state4"): 1.5, ("MVO2_per_cyta", "state3"): 3.5,
    ("cytc_red_frac", "state4"): 0.003, ("cytc_red_frac", "state3"): 0.005,
    ("pH_x", "state4"): 0.006, ("pH_x", "state3"): 0.009,
    ("dPsi_mV", "state4"): 0.7, ("dPsi_mV", "state3"): 0.7,
}


@pytest.fixture(scope="module")
def published():
    run = R.Runner(M.Arm.published())
    charge = run.calibrate_charge()
    sweeps = {"state4": run.sweep(0.0, check_every=False), "state3": run.sweep(1.3e-3, check_every=False)}
    rows, cyta = R.compare(sweeps, TARGETS, "with")
    return {"run": run, "charge": charge, "sweeps": sweeps, "rows": rows}


def test_integrator_agrees_with_the_exact_steady_state(published):
    for state, rows in published["sweeps"].items():
        assert rows[0]["integration_vs_newton_rel"] < 1e-9, state
        for r in rows:
            assert r["newton_residual"] < 1e-30


def test_published_curves_within_documented_bands(published):
    bad = [r for r in published["rows"] if not r["anchor"]
           and abs(r["diff"]) > BANDS[(r["quantity"], r["curve"])]]
    assert not bad, [(r["panel"], r["curve"], r["Pi_e_mM"], r["published"], r["reproduced"]) for r in bad]


def test_p50_and_cytochrome_c_from_the_text(published):
    run = published["run"]
    lo = run.low_oxygen(1.0e-3, 0.0, 10e-3)
    assert lo["P50_uM"] == pytest.approx(0.373, rel=0.02)
    cc = run.low_oxygen(0.5e-3, 0.87e-3, 10e-3, o2_uM=np.array([50.0]))
    assert cc["cytc_at_50uM"] == pytest.approx(0.14, abs=0.015)


def _state3_pi10(arm, charge):
    run = R.Runner(arm, charge=charge)
    h = run.held(ADP_e=1.3e-3, Pi_e=10e-3)
    y, _ = run.solve(h)
    return R.outputs(run.comp, h, y)


def test_planted_controls_are_caught(published):
    base = next(r for r in published["sweeps"]["state3"] if r["Pi_e_mM"] == 10.0)
    t2005 = _state3_pi10(M.Arm.published(table="e36"), published["charge"])
    assert abs(t2005["cytc_red_frac"] - base["cytc_red_frac"]) > 0.05
    ko2 = _state3_pi10(M.Arm.published(overrides={"k_O2": 1.0e-6}), published["charge"])
    assert abs(ko2["cytc_red_frac"] - base["cytc_red_frac"]) > 0.05 and abs(ko2["dPsi_mV"] - base["dPsi_mV"]) > 1.0
    # the stale row conserves a different combination, so the anchored inventory no longer
    # holds the matrix charge: the steady state moves
    stale = R.Runner(M.Arm.published(H_x_row="stale_web_xml"))
    stale.calibrate_charge()
    h = stale.held(ADP_e=1.3e-3, Pi_e=10e-3)
    y, _ = stale.solve(h)
    o = R.outputs(stale.comp, h, y)
    assert abs(o["pH_x"] - base["pH_x"]) > 0.01 or abs(o["dPsi_mV"] - base["dPsi_mV"]) > 1.0
