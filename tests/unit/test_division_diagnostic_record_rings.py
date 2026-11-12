"""The ring model (A3) with one ring reproduces R-full's prediction of record.

The registered J1 definition is run once (0 to J1 with the pulse train) at the record's
calibration (P_old and A/L) through the ring model's own code path and integrator
(cleft_rings_reference, BDF), and must give the record's Em within the record's reference term.
The helpers and the acceptance check are those of test_division_diagnostic_record.py.
"""

from tests.unit.test_division_diagnostic_record import check, geometry, record_egg
from validation.division import cleft_rings_reference as rings


def test_ring_model_with_one_ring_reproduces_the_record():
    r_b, r_m = geometry()
    d, egg = record_egg()
    check(d, egg, rings.runner(rings.Rings(1, r_b, r_m)))
