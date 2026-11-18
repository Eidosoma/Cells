"""FR-10's registered design: the files equal their generator, the design is powered, and the
references are code-blind.

Planted controls: a changed number in the committed values, and a tolerance above a ceiling.
"""

from __future__ import annotations

import json
import re

from validation.fr10.references import design
from validation.fr10.references.common import HERE, MIN_MARGIN


def test_committed_design_and_values_equal_their_generator():
    assert design.check() == []


def test_the_comparison_catches_a_changed_number():
    committed = json.loads(design.VALUES_FILE.read_text())
    changed = json.loads(json.dumps(committed))
    changed["R_ion"]["V_m_V"][100] *= 1 + 1e-9
    assert design._same(committed, changed, "values")
    assert not design._same(committed, committed, "values")


def test_the_registered_design_is_powered_at_every_dt():
    d = json.loads(design.DESIGN_FILE.read_text())
    assert d["min_margin"] == MIN_MARGIN
    for world in ("W1", "W2"):
        for row in d["power"][world]["per_dt"]:
            for unit, margin in row["honest_margin"].items():
                assert margin >= MIN_MARGIN, (world, row["dt_s"], unit, margin)
            for control, dev in row["controls"].items():
                for unit, ceiling in row["ceiling"].items():
                    assert dev[unit] >= MIN_MARGIN * ceiling * (1 - 1e-12), (world, control)
        for order in d["power"][world]["observed_order"]["ars_implicit"]:
            assert abs(order - 2.0) < 0.05
    names = {z["control"].split(" ")[0] for z in d["zero_power"]}
    assert {"dose_in_mM", "accumulate", "dG_no_minus_one,"} <= names
    assert d["inputs"]["git_blob"] == design.git_blob_id(HERE / "reference_inputs.json")


def test_nothing_imports_the_engine():
    for path in sorted(HERE.glob("*.py")):
        text = path.read_text()
        assert not re.search(r"^\s*(import cells|from cells)", text, re.M), path
        assert "validation.tissue" not in text, path
