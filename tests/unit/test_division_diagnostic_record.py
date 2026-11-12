"""The J1 diagnostic extensions' null settings reproduce R-full's prediction of record.

Each case runs the registered J1 definition once (0 to J1 with the pulse train, LSODA) at the
record's calibration (P_old and A/L), through the extension's own code path, and must give the
record's Em within the record's reference term. The ring model's case (one ring) is in
test_division_diagnostic_record_rings.py, which uses this module's helpers.
"""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from validation.division import cleft_egg_reference as ref
from validation.division import cleft_rings_reference as rings
from validation.division import j1_diagnostic_runner as runner

RECORD = json.loads((Path(ref.__file__).parent / "j1_prediction_of_record.json").read_text())
REFERENCE_TERM_V = runner.REFERENCE_TERM_V


def record_egg(**changes):
    d = ref.load_declared()
    egg = ref.build(
        d, ref.scalar_values(d), p_old=RECORD["p_old_m_s"], a_over_l=RECORD["a_over_l_m"]
    )
    return d, replace(egg, **changes)


def geometry():
    d = ref.load_declared()
    face = ref.scalar_values(d)["new_membrane_area_at_j1_m2"] / 2.0
    return rings.ring_geometry(0.26e-6, face)


def check(d, egg, runner_fn=None):
    j1, _ = ref.j1_readout(d, egg, method="LSODA", runner=runner_fn)
    assert j1["em_V"] == pytest.approx(RECORD["prediction_of_record_V"], abs=REFERENCE_TERM_V)
    assert j1["rm_ohm"] == pytest.approx(488e3, rel=1e-6)


def test_depth_shape_with_alpha_zero_reproduces_the_record():
    r_b, r_m = geometry()
    d, egg = record_egg(access_shape=("depth", 0.0, runner.R_EGG_M, r_m, runner.R_EGG_M - r_b))
    assert egg.extended
    check(d, egg)


def test_ramp_shape_with_beta_one_reproduces_the_record():
    d, egg = record_egg(access_shape=("ramp", 1.0, 900.0, 1680.0))
    check(d, egg)
