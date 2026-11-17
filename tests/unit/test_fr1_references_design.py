"""FR-1's registered design: the files equal their generator, the inputs copy is the FR lane's,
the controls are powered where the design says so, and nothing imports the engine.

Planted control: a changed number in the committed values must be caught.
"""

from __future__ import annotations

import json
import re

from validation.fr1.references import design


def test_committed_design_and_values_equal_their_generator():
    assert design.check() == []


def test_the_comparison_catches_a_changed_number():
    committed = json.loads(design.VALUES_FILE.read_text())
    changed = json.loads(json.dumps(committed))
    changed["R_step_map"]["0.001"]["x"][50] *= 1 + 1e-9
    assert design._same(committed, changed, "values")
    assert not design._same(committed, committed, "values")


def test_registered_power_and_inputs_identity():
    d = json.loads(design.DESIGN_FILE.read_text())
    assert d["inputs"]["git_blob"] == design.git_blob_id(design.INPUTS)
    for name, row in d["power"]["C3_C4_C5_closed_forms"].items():
        assert min(row["margins"].values()) >= 1e6, name
    for rung in d["power"]["C4_step_map"]["per_rung"]:
        assert min(rung["margin_against_map_to_rounding"].values()) >= design.MIN_MARGIN
        assert abs(rung["splitting"]["relative_over_leading"] - 1) < 10 * rung["dt_s"]
    assert len(d["settled_readings"]) == 9
    names = " ".join(z["control"] for z in d["zero_power"])
    assert "dropped -1" in names and "orientation" in names


def test_nothing_imports_the_engine():
    for path in sorted(design.HERE.glob("*.py")):
        text = path.read_text()
        assert not re.search(r"^\s*(import cells|from cells)", text, re.M), path
        assert "validation.tissue" not in text, path
