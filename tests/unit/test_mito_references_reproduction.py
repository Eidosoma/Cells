"""Beard 2005 reproduced by the independent reference (tier 3 by measurement).

The published arm runs at the declared inputs: the 2006 Table 1, Eq. 24 with Eq. 7's
proton term (Q02: what the published curves were computed with), T = 298.15 K, the matrix Mg2+ total at 1 mM, and the matrix charge anchored to Fig. 4D's
pH at [Pi]e = 0. It is checked against the published model curves of Figs. 4-5 and the
text's P50, within this reference's documented reproduction bands. The integrator must
match the exact Newton solve. Three planted controls must be caught: the 2005 Table 1,
the web XML's stale proton row, and the 2005 k_O2.

Measured at landing (19 Nov 2026, one core shared with other jobs, nice 10): about 80 s,
96 MB. The cost is in the 50-digit Newton solves (two sweeps and one low-oxygen sweep) and
seven integrations.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from validation.mitochondria.references import model as M
from validation.mitochondria.references import reproduce as R

TARGETS = json.loads(R.TARGETS.read_text())

# Reproduction bands of the published arm against the digitised published curves
# (|reproduced - published|, per quantity and state), set just above the published arm's
# measured agreement (reproduce.py, arm "published"). They record this reference's status;
# they are not an engine tolerance.
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
    grid = np.array([50.0, 20.0, 8.0, 4.0, 2.0, 1.2, 0.8, 0.6, 0.5, 0.42, 0.37, 0.33, 0.28, 0.2])
    lo = run.low_oxygen(1.0e-3, 0.0, 10e-3, o2_uM=grid)
    assert lo["P50_uM"] == pytest.approx(0.373, rel=0.02)
    cc = run.low_oxygen(0.5e-3, 0.87e-3, 10e-3, o2_uM=np.array([50.0]))
    assert cc["cytc_at_50uM"] == pytest.approx(0.14, abs=0.015)


def _state3_pi10(arm, charge):
    run = R.Runner(arm, charge=charge)
    h = run.held(ADP_e=1.3e-3, Pi_e=10e-3)
    y, _ = run.solve(h)
    return R.outputs(run.comp, h, y)


def test_steady_state_depends_only_on_the_two_inventories(published):
    """Three far-apart starts with the same invariants reach the same steady state."""
    run = published["run"]
    h = run.held(ADP_e=1.3e-3, Pi_e=3e-3)
    ends = []
    for kw in (dict(), dict(pH_x=7.4, K_x=0.09, dPsi=60.0, NADH_frac=0.1, QH2_frac=0.9, cytc_red_frac=0.6, Pi_x=0.5e-3),
               dict(pH_x=6.9, K_x=0.2, dPsi=220.0, NADH_frac=0.95, QH2_frac=0.05, cytc_red_frac=0.02, Pi_x=8e-3)):
        y0 = M.with_invariants(run.comp, M.initial_state(run.comp, h, **kw), charge=published["charge"],
                               mg_total=run.mg_x_total)
        ends.append(M.integrate(run.comp, h, y0, t_end=20000.0).y[:, -1])
    for e in ends[1:]:
        assert np.max(np.abs(e - ends[0]) / np.maximum(np.abs(ends[0]), 1e-12)) < 1e-9


def test_planted_controls_are_caught(published):
    """Each plant moves its row: the 2005 Table 1 and the 2005 k_O2 move the steady state;
    the web XML's stale proton row leaves the steady-state equations unchanged (its chain
    coefficients also sum to -10) but breaks the matrix-charge invariant, which drifts."""
    base = next(r for r in published["sweeps"]["state3"] if r["Pi_e_mM"] == 10.0)
    ko2 = _state3_pi10(M.Arm.published(overrides={"k_O2": 1.0e-6}), published["charge"])
    assert abs(ko2["cytc_red_frac"] - base["cytc_red_frac"]) > 0.05 and abs(ko2["dPsi_mV"] - base["dPsi_mV"]) > 1.0
    t2005 = R.Runner(M.Arm.published(table="e36"), charge=published["charge"])
    h = t2005.held(ADP_e=1.3e-3, Pi_e=10e-3)
    y = M.integrate(t2005.comp, h, t2005.start(h), t_end=4000.0).y[:, -1]
    o = R.outputs(t2005.comp, h, y)
    assert abs(o["cytc_red_frac"] - base["cytc_red_frac"]) > 0.05 or abs(o["dPsi_mV"] - base["dPsi_mV"]) > 1.0
    stale = M.compile_model(M.load(), M.Arm.published(H_x_row="stale_web_xml"))
    run = published["run"]
    h = run.held(ADP_e=1.3e-3, Pi_e=3e-3)
    y0 = M.with_invariants(run.comp, run.start(h), charge=published["charge"], mg_total=run.mg_x_total)
    y1 = M.integrate(stale, h, y0, t_end=20.0).y[:, -1]
    charge_drift = M.invariants(run.comp, y1)[1][1] - M.invariants(run.comp, y0)[1][1]
    assert abs(charge_drift) > 1e-5          # mol per l mito; the published row holds it to ~1e-14
