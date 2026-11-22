"""XC0's code-blind references: a fast integrity check of the registered files (about 10 s).

The full regeneration is test_xenopus_xc0_references_regenerate.py. Here: the files parse and agree; the band rule
is recomputed from the stored references and floors; the plant margins are recomputed from the stored rows; a small
deterministic subset of rows is regenerated from the formulas.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from validation.xenopus_bioelectric.references import claims_membrane, design, plants, symporter  # noqa: E402
from validation.xenopus_bioelectric.references.exact import context  # noqa: E402
from validation.xenopus_bioelectric.references.rows import Rows  # noqa: E402


@pytest.fixture(scope="module")
def stored():
    return json.loads(design.VALUES_FILE.read_text()), json.loads(design.BANDS_FILE.read_text())


@pytest.fixture(scope="module")
def registry(stored):
    values, bands = stored
    return Rows.from_documents(values, bands)


def test_files_parse_and_agree(stored):
    values, bands = stored
    assert set(values["families"]) == set(bands["families"])
    for fam, meta in bands["families"].items():
        assert set(meta["rows"]) == set(values["families"][fam]["values"]), fam
        assert meta["kind"] in {"abs", "sign", "exact_zero", "flag", "info"}
    assert design.VALUES_FILE.read_text() == design.dumps(values)       # canonical bytes
    assert design.BANDS_FILE.read_text() == design.dumps(bands)


def test_band_rule_recomputed_from_stored_references_and_floors(stored, registry):
    _, bands = stored
    assert registry.bands_json() == bands["families"]
    for fam, meta in bands["families"].items():
        if meta["kind"] in ("abs", "sign"):
            for key, row in meta["rows"].items():
                assert row["band"] >= 10 * row["floor"], (fam, key)


def test_registered_choices_of_the_erratum(stored):
    _, bands = stored
    fam = bands["families"]
    assert fam["C2.V_ghk_area"]["kind"] == "abs" and fam["C2.V_ghk_unit"]["kind"] == "info"
    assert fam["C8.bc_t_e"]["kind"] == "abs" and fam["C8.b_t_e"]["kind"] == "info"
    assert fam["C3.Q_over_CV_error"]["tol_abs"] == 1e-14 and fam["C7.relax_dQ"]["tol_abs"] == 1e-14
    assert fam["C7.pump_heat"]["kind"] == "abs" and fam["C7.pump_heat_nonneg"]["kind"] == "flag"


def test_plant_margins_recomputed_from_the_stored_rows(stored, registry):
    _, bands = stored
    with context():
        out = plants.run_plants(registry)
    assert out["plants"] == bands["plants"]
    assert out["zero_power"] == bands["zero_power"]
    for name, plant in out["plants"].items():
        assert plant["zero_power_undeclared_rows"] == {}, name
        smallest = plant["smallest_margin_expected_visible_rows"]
        assert smallest is None or smallest >= 1.0, name


def test_a_small_subset_is_regenerated_from_the_formulas(stored):
    values, _ = stored
    fams = values["families"]
    key = "primary|local|T291.15"
    with context():
        sub = Rows()
        claims_membrane.c0_c1_c2(sub, states=[key])
        for fam, rows in sub.values.items():
            for k, v in rows.items():
                assert fams[fam]["values"][k] == v, (fam, k)
        # a stall row and a King-Altman row
        s = symporter.s_params(n=2, NaN="21", NaP="9.9", BN="0.1", BP="0.1")
        from validation.xenopus_bioelectric.references.exact import fmt
        assert fmt(symporter.V_stall(s)) == fams["C6.v1_V_stall"]["values"]["n2|Nain21|Naout9.9|BP0.1|rB1|T291.15"]
        s2 = symporter.s_params(NaP="19.9", BP="10", BN="0.1", NaN="21", V="-0.0899")
        assert fmt(symporter.v2_ka(s2)[2]) == fams["C6.v2_J_over_k"]["values"]["NaP19.9|BP10|BN0.1|V-0.0899"]
