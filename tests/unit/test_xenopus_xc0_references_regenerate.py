"""XC0's code-blind references: the full regeneration (about 5 minutes; for tier 3). The fast integrity check is
test_xenopus_xc0_references.py."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from validation.xenopus_bioelectric.references import design  # noqa: E402

REFS = ROOT / "validation" / "xenopus_bioelectric" / "references"


@pytest.fixture(scope="module")
def docs():
    return design.documents()


def test_reference_values_regenerate_byte_for_byte(docs):
    values, _ = docs
    assert design.VALUES_FILE.read_text() == design.dumps(values)


def test_bands_and_plants_regenerate_byte_for_byte(docs):
    _, bands = docs
    assert design.BANDS_FILE.read_text() == design.dumps(bands)


def test_internal_checks_hold(docs):
    values, bands = docs
    checks = values["internal_checks"]
    assert checks["max_abs_identity_residual_fmol"] < 1e-40       # RK4 keeps the charge identity exactly
    assert checks["max_ode_error_estimate"] < 1e-8                # Richardson error estimates of every ODE row
    fams = bands["families"]
    for fam, meta in fams.items():
        assert set(meta["rows"]) == set(values["families"][fam]["values"]), fam
        for row in meta["rows"].values():
            assert row["band"] >= 0 and row["floor"] >= 0


def test_every_plant_is_seen_where_it_is_expected_to_be(docs):
    _, bands = docs
    for name, plant in bands["plants"].items():
        assert plant["zero_power_undeclared_rows"] == {}, name
        smallest = plant["smallest_margin_expected_visible_rows"]
        assert smallest is None or smallest >= 1.0, name       # None: every row is a declared zero-power row


def test_nothing_here_imports_the_engine_or_a_reference_simulator():
    for path in REFS.glob("*.py"):
        text = path.read_text()
        for line in text.splitlines():
            stripped = line.strip()
            assert not stripped.startswith(("import cells", "from cells", "import betse", "from betse")), (path.name, line)


def test_inputs_copy_is_the_frozen_declared_input_set():
    import json

    inputs = json.loads((REFS / "reference_inputs.json").read_text())
    assert inputs["schema"] == "xenopus_xc0_declared_inputs@2"
    assert inputs["frozen_for_the_references"] == "19 November 2026, 13:35 UTC"
    assert Decimal(str(inputs["temperature_K"]["value"])) == Decimal("291.15")
