"""R-tissue's static entry point reproduces R-full's prediction of record on S3's egg (S5 §7.2).

One R-tissue run of the registered J1 definition at the record's calibration (0 to J1 plus one
sample, Radau at rtol 1e-10, through R-full's runner hook): Em at J1 within 1e-10 V of the
record's -12.79494 mV, and Rm at J1 at its calibration target. A run of minutes (tier 3); the
full pulse-edge comparison with R-full is the cross-check's `pulses` part. No division here.
"""

import pytest

from validation.division import cleft_tissue_crosscheck as cross


def test_r_tissue_reproduces_the_prediction_of_record_on_s3s_egg():
    out = cross.part_record()
    assert out["record_em_V"] == pytest.approx(-0.01279494, abs=5e-9)
    assert abs(out["d_em_V"]) <= cross.TARGET_V
    assert out["rm_ohm"] == pytest.approx(488e3, rel=1e-6)
    assert out["passes"]
