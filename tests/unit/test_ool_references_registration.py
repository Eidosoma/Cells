"""OL5 references, the registration: the committed design files equal their generators, every
registered world parses, every registered refusal is refused, and the convention menu refuses
what it must.

Planted controls: a committed file that differs from its generator by one byte; a missing, an
unknown and a refused token; a float that is not its exact value; each registered defect.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from validation.ool.references import design as D
from validation.ool.references import registered as R
from validation.ool.references.common import RecordFormatError
from validation.ool.references.world import (
    CONVENTION_MENU,
    Conventions,
    every_convention,
    load_world,
    parse_world,
)


def test_committed_world_files_equal_the_generator():
    docs = {**R.world_documents(), **R.variant_documents(), "ol1_boundary": R.boundary_document()}
    for wid, doc in docs.items():
        assert (R.DESIGN_DIR / f"{wid}.world.json").read_bytes() == R.canonical_bytes(doc), wid
    for rid, doc in R.refusal_documents().items():
        assert (R.DESIGN_DIR / "refusals" / f"{rid}.world.json").read_bytes() == R.canonical_bytes(doc), rid
    on_disk = {p.name for p in R.DESIGN_DIR.glob("*.world.json")}
    assert on_disk == {f"{wid}.world.json" for wid in docs}


def test_committed_design_files_equal_the_generator(tmp_path):
    written = D.write_design(tmp_path)
    for p in written:
        assert (R.DESIGN_DIR / p.name).read_bytes() == p.read_bytes(), p.name
    # planted: one changed byte is seen
    p = written[0]
    p.write_bytes(p.read_bytes()[:-1] + b" ")
    assert (R.DESIGN_DIR / p.name).read_bytes() != p.read_bytes()


def test_registered_counts_and_menu():
    kp = json.loads((R.DESIGN_DIR / D.KERNEL_PROBE_FILE).read_text())
    cw = json.loads((R.DESIGN_DIR / D.CLOSED_WORLD_FILE).read_text())
    assert (kp["count"], cw["count"]) == (589, 387)
    menu = json.loads((R.DESIGN_DIR / D.CONVENTIONS_FILE).read_text())
    assert menu["menu"] == {k: list(v) for k, v in CONVENTION_MENU.items()}
    assert menu["refused"] == {"free_energy_form": ["continuum"]}
    assert [c.as_dict()["condensed_measure"] + "+" + c.last_molecule for c in every_convention()] == [
        "multinomial+kept", "multinomial+reversible", "multinomial_less_one+kept", "multinomial_less_one+extinct"]


def test_every_registered_world_parses_and_is_balanced():
    for wid in R.world_documents():
        w = R.registered_world(wid)
        assert w.steps and w.initial_state
    w = R.registered_world("ol1_wa")
    assert [p.name for p in w.finite] == ["A@membrane", "B@membrane", "C@membrane", "D@membrane", "E@membrane",
                                          "S@membrane", "S@pool", "T@pool"]
    assert w.X("pool") == 8 and R.registered_world("ol1_wb_m80").X("pool") == 80


@pytest.mark.parametrize("path", sorted((R.DESIGN_DIR / "refusals").glob("*.world.json")), ids=lambda p: p.stem)
def test_every_registered_refusal_is_refused(path: Path):
    with pytest.raises(RecordFormatError):
        load_world(path)


def test_the_menu_refuses_missing_unknown_and_refused_tokens():
    good = Conventions(condensed_measure="multinomial", last_molecule="kept").as_dict()
    assert Conventions.from_declared(good).c == 0
    for key in good:
        bad = dict(good)
        del bad[key]
        with pytest.raises(RecordFormatError):
            Conventions.from_declared(bad)
    with pytest.raises(RecordFormatError):
        Conventions.from_declared(dict(good, free_energy_form="continuum"))
    with pytest.raises(RecordFormatError):
        Conventions.from_declared(dict(good, membrane_kinetics="per_volume"))
    with pytest.raises(RecordFormatError):
        Conventions.from_declared(dict(good, last_molecule="extinct"))          # extinct needs c = 1
    with pytest.raises(RecordFormatError):
        Conventions.from_declared(dict(good, condensed_measure="multinomial_less_one", last_molecule="reversible"))
    with pytest.raises(RecordFormatError):
        Conventions.from_declared(None)


def test_a_float_that_is_not_its_exact_value_is_refused():
    doc = R.world_documents()["ol1_wa"]
    doc = json.loads(R.canonical_bytes(doc))
    doc["steps"][1]["forward_rate_per_s"]["float"] = 0.5000001
    with pytest.raises(RecordFormatError):
        parse_world(doc)
    doc = json.loads(R.canonical_bytes(R.world_documents()["ol1_wa"]))
    doc["species"][2]["standard_mu_RT"]["bilayer"]["float"] += 1e-9
    with pytest.raises(RecordFormatError):
        parse_world(doc)
