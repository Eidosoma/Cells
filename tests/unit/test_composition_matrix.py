"""The composition matrix in docs/PUMP_COMPOSITE.md is the one the declarations give (D156 item 2).

validation/tissue/composition_matrix.py builds it from the registered operators' declarations
(pump_composite.structure_errors on every ordered pair, each with its requirements) and from its
list of rules at the definition. These tests fail when:
* the document's block differs from the regeneration: run
  `python -m validation.tissue.composition_matrix --write`;
* structure_errors gives a message the module does not recognise;
* a refusal has no tag, or a tag names no refusal (a new operator brings its tags);
* a tag is neither real nor nominal, a nominal tag cites no code, a rule cites no test, or a
  cited check, code or test does not exist;
* a registered law is missing from the document's operator table;
* a law-level rule marks a cell the declarations refuse (its mark would add nothing), or a rule
  behind a refusal of the declarations names a pair they admit.
"""

import pytest

from validation.tissue import composition_matrix as cm


@pytest.fixture(scope="module")
def cells():
    return cm.matrix()  # Refuses an unrecognised message, and a law refused alone.


def test_every_refusal_has_a_tag_and_every_tag_a_refusal(cells):
    found = set().union(*(cell["refusals"] for cell in cells.values()))
    assert sorted(found - set(cm.TAGS), key=str) == [], "untagged refusals"
    assert sorted(set(cm.TAGS) - found, key=str) == [], "tags without a refusal"


def test_tags_are_real_or_nominal_and_nominal_ones_cite_existing_code():
    for key, (tag, why, cites) in cm.TAGS.items():
        assert tag in (cm.REAL, cm.NOMINAL) and why, key
        assert cites or tag == cm.REAL, f"a nominal tag cites the code: {key}"
        for cite in cites:
            assert cm.defines(cite), cite


def test_every_rule_cites_an_existing_check_and_test():
    for rule in cm.RULES:
        assert rule["tag"] in (cm.REAL, cm.NOMINAL) and rule["level"] in ("law", "data"), rule
        assert all(law in cm.OPERATORS for law in rule["laws"]), rule["rule"]
        assert cm.defines(rule["check"]), rule["check"]
        assert rule["test"] and cm.defines(rule["test"]), (rule["rule"], rule["test"])


def test_marks_fall_on_admitted_cells_and_second_walls_on_refused_ones(cells):
    for rule in cm.RULES:
        assert rule["level"] == "law" or not (rule.get("marks") or rule.get("behind")), rule
        for pair in rule.get("marks", ()):
            assert not cells[pair]["refusals"], (rule["rule"], pair)
        for pair in rule.get("behind", ()):
            assert cells[pair]["refusals"], (rule["rule"], pair)


def test_every_registered_law_is_in_the_operator_table():
    text = cm.DOC.read_text()
    start = text.index("| Operator law | Block |")
    table = text[start : text.index("\n\n", start)]
    listed = {row.split("|")[1].strip().strip("`") for row in table.splitlines()[2:]}
    assert sorted(set(cm.LAWS) - listed) == []


def test_the_document_block_is_the_regeneration(cells):
    stale = "the matrix is stale: run python -m validation.tissue.composition_matrix --write"
    assert cm.document_block(cm.DOC.read_text()) == cm.render(cells), stale
