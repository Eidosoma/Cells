"""FR-7's registered references regenerate in full: every world's reference rows, bounds, bands,
plants, margins and zero-power list, and R-clear's clearance design (design.py --check).

About 2.5 minutes of one CPU: run deliberately (tier 3 by measurement). The fast integrity checks
are test_fr7_references.py.
"""

from __future__ import annotations

from validation.fr7.references import design, worlds


def test_the_inputs_regenerate():
    assert worlds.main(["--check"]) == 0


def test_the_whole_design_regenerates():
    assert design.main(["--check"]) == 0
