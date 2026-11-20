"""R-loop's registered references regenerate in full: the start, s0, the precursor's supply and F*
(loop_worlds.py --check), then both arms, the plants, the cut's power, persistence and the
regulator's range (loop_design.py --check), and D233's mean-field floor table (loop_floor.py
--check).

About 3 minutes of one CPU. The calibration against an emulated split is not regenerated (about
10 minutes; loop_design.py --calibrate). The fast integrity checks are test_fr7_references.py.
"""

from __future__ import annotations

from validation.fr7.references import loop_design, loop_floor, loop_worlds


def test_the_loop_inputs_regenerate():
    assert loop_worlds.main(["--check"]) == 0


def test_the_loop_design_regenerates():
    assert loop_design.main(["--check"]) == 0


def test_the_floor_table_regenerates():
    """D233's mean-field floor table, registered with the rows."""
    assert loop_floor.main(["--check"]) == 0
