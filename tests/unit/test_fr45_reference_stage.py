"""FR-4's and FR-5's reference stage (validation/tissue/compartment_ph_reference_stage.py).

The references run from the declared parameters, checked first against their own transcription of
§13; FR-5's start is the one extract, passed as tr.Start, and a row 0 that is not the extract's
start is refused; the judge's arithmetic on the references' records reproduces the references'
readout (931fb38a). Reference runs only, no engine: about 50 s on one CPU, most of it the last
test's six 400 s runs.
"""

from dataclasses import replace

import pytest

from validation.compartment_ph import ph_reference as ph
from validation.compartment_ph_engine import definitions as defs
from validation.compartment_ph_engine.parameters import ARM_R, ARM_T, World
from validation.tissue import compartment_ph_reference_stage as stage


@pytest.fixture(scope="module")
def extract():
    return stage.self_check_extract()


def test_the_declared_parameters_agree_with_the_references_transcription():
    report = stage.consistency()
    assert report["ok"], [k for k, v in report["items"].items() if not v["ok"]]
    with pytest.raises(SystemExit, match="disagree"):
        stage.check_consistency(replace(World(), proton_leak_m_s=6.1e-7))


def test_the_extract_becomes_tr_start_with_the_declared_cargo(extract):
    start = stage.tr_start(extract, ARM_R)
    cell, lumen = (extract["nodes"][n]["amounts_fmol"] for n in (defs.CELL, defs.LUMEN))
    assert start.Heq_fmol == (cell["H"], lumen["H"])
    assert start.ions_fmol == ({i: cell[i] for i in ph.IONS}, {i: lumen[i] for i in ph.IONS})
    built = defs.fr5_world(ARM_R, start=extract)
    nodes = {n["id"]: n for n in built["model"]["cells"] + built["model"]["extracellular"]}
    assert start.X_fmol == (nodes[defs.CELL]["initial_amount_fmol"]["X"],
                            nodes[defs.LUMEN]["initial_amount_fmol"]["X"])


def test_a_short_run_starts_at_the_extract_and_a_moved_start_is_refused(extract):
    out = stage.fr5_reference(extract, arms=("T",), end_s=3.0)
    assert set(out["worlds"]) == {"T", "T_control", "T_floor"}
    assert all(c["ok"] for c in out["start_checks"].values())
    assert out["worlds"]["T"]["record_s"] == [0.0, 1.0, 2.0, 3.0]
    moved = dict(extract, readouts=dict(extract["readouts"],
                                        pH_L=extract["readouts"]["pH_L"] + 1e-9))
    with pytest.raises(SystemExit, match="row 0"):
        stage.fr5_reference(moved, arms=("T",), end_s=1.0)


def test_the_judges_arithmetic_on_the_references_reproduces_their_readout(tmp_path):
    report = stage.self_check(tmp_path)
    t, r = report["arms"]["T"]["claims"], report["arms"]["R"]["claims"]
    assert t["pre_over_above"] == pytest.approx(13.69, abs=0.01)
    assert t["up_s"] == pytest.approx(73.081, abs=0.01)
    assert t["down_s"] == pytest.approx(326.882, abs=0.01)
    assert r["released_in_window"] == pytest.approx(0.8736, abs=1e-4)
    assert r["up_s"] == pytest.approx(113.081, abs=0.01)
    assert r["down_s"] == pytest.approx(366.882, abs=0.01)
    assert t["returns_before_end"] == r["returns_before_end"] == 1
    for arm in (ARM_T, ARM_R):
        assert report["arms"][arm.arm]["budget_fmol"] == pytest.approx(
            1e-3 * arm.base.lumen_volume_pL, rel=1e-12)
