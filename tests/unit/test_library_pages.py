"""The library of plain-language pages (docs/LAW_DOCUMENTATION_DESIGN.md §3.3; D203): the page
tool's five claims over docs/library/, each with a planted error it must catch (D187).

- C1: every page names a registered piece or a model with declared structure, at its path, and
  once the pages are complete each of them has its page (planted: a law registered for the test
  with no page, under the complete check; a stray page);
- C2: every generated block, the index and the glossary's "Used by" lines equal a fresh render of
  the active registries' manifest, compared as text (planted: one unit changed in a copy of a page,
  and a page's sentence changed under a stale index);
- C3: the plain layers are present and within their limits (planted: an empty "In plain words", a
  sentence of 31 words, a symbol in it, the headings out of order, the mathematics with neither an
  equation nor its reason);
- C4: every relative link and anchor resolves, glossary terms included, by GitHub's anchor rule
  (planted: a link to a missing glossary term, and one to a missing file);
- C5: the format page's key tables equal the manifest's key sets, in both directions (planted: a
  key added to a copy of PIECE_KEYS, a key dropped from the page, and the format's name missing).

The tool's `--new` writes a page whose generated blocks are filled in, which C3 then holds
unfinished until its plain layers are written (planted: a page that exists, which it refuses).
"""

import pytest

from cells.registry import declarations
from cells.registry import laws as law_registry
from scripts import library_pages as library

KV1P5 = "docs/library/cells/laws/channel.kv1p5_mh@1.md"
TRANSPORTER = "docs/library/cells/kinds/kind.transporter@1.md"


@pytest.fixture(scope="module")
def doc():
    return declarations.manifest()


@pytest.fixture(scope="module")
def files():
    return library.load()


def test_c1_every_page_names_a_piece_and_every_piece_has_its_page_once_complete(doc, files):
    assert library.check_pages(doc, files) == []
    assert set(library.pages(files)) <= set(library.paged(doc))
    todo = library.check_pages(doc, files, complete=True)  # The pages not yet written, by name.
    assert len(todo) == len(library.paged(doc)) - len(library.pages(files)) > 0
    # Planted: a law registered for the test, in the tree as a built-in's would be, with no page.
    planted = law_registry.RouteLaw(
        "tests.route.planted_library_route@1", ("membrane",), "planted", host="cells.kind.passive_routes@1"
    )
    with law_registry.scope(law_registry.BUILTIN.extended(planted)):
        registered = declarations.manifest()
    (entry,) = (e for e in registered["pieces"] if e["id"] == "tests.route.planted_library_route@1")
    assert entry["module_path"] is None  # Registered from a test, outside the cells package.
    entry["module_path"] = "src/cells/models/inner_laws.py"
    page = "docs/library/tests/laws/route.planted_library_route@1.md"
    assert f"C1 {page}: law tests.route.planted_library_route@1 has no page" in library.check_pages(
        registered, files, complete=True
    )
    assert library.check_pages(registered, files) == []  # Partial: pages are written in batches.
    # Planted: a stray page, which names no registered piece.
    stray = "docs/library/cells/laws/no_such_law@1.md"
    assert library.check_pages(doc, dict(files, **{stray: files[KV1P5]})) == [
        f"C1 {stray}: names no registered piece or model with declared structure"
    ]


def test_c2_generated_blocks_the_index_and_the_backlinks_match_a_fresh_render(doc, files):
    assert library.check_blocks(doc, files) == []
    unit = "| Voltage domain | -0.12 to 0.06 | V |"
    assert unit in files[KV1P5]
    changed = files[KV1P5].replace(unit, "| Voltage domain | -0.12 to 0.06 | mV |")
    assert library.check_blocks(doc, dict(files, **{KV1P5: changed})) == [
        f"C2 {KV1P5}: block bounds is stale; run --write"
    ]
    said = library.sentence(files[KV1P5])
    resaid = files[KV1P5].replace(said, "A potassium channel that opens and shuts with voltage.")
    assert library.check_blocks(doc, dict(files, **{KV1P5: resaid})) == [
        f"C2 {library.INDEX}: the index is stale; run --write"
    ]
    assert library.write_all(doc, files) == {}  # Nothing to render again on the tree.


def test_c3_the_plain_layers_are_written_and_within_their_limits(doc, files):
    assert library.check_layers(doc, files) == []
    text = files[TRANSPORTER]
    plain = library.sections(text)["In plain words"]
    said = library.sentence(text)
    cases = {
        "'In plain words' is not written": text.replace(plain, ""),
        "the one sentence has 31 words": text.replace(said, " ".join(["word"] * 31)),
        "the one sentence holds a symbol ($)": text.replace(said, said + " Its rate is $J$."),
        "its headings are": text.replace("## Sources", "## References"),
        "'The mathematics' holds an equation": text.replace("$", ""),
    }
    for reason, broken in cases.items():
        found = library.check_layers(doc, {TRANSPORTER: broken})
        assert any(reason in f for f in found), (reason, found)


def test_c4_links_and_anchors_resolve_by_github_s_rule(files):
    assert library.check_links(files) == []
    assert library.slug("Each interface's own fields") == "each-interfaces-own-fields"
    assert library.slug("Water potential") == "water-potential"
    anchors = library.anchors(files[library.FORMAT_PAGE])
    assert {"channel-laws", "kinds", "operators", "family-interfaces", "the-id-rule"} <= set(
        anchors
    )
    term = files[KV1P5].replace("../../GLOSSARY.md#gate", "../../GLOSSARY.md#gating-charge", 1)
    gone = files[KV1P5].replace("../../../VOLTAGE_GATED_CHANNEL_SPEC.md", "../../../NO_SPEC.md", 1)
    assert library.check_links(dict(files, **{KV1P5: term})) == [
        f"C4 {KV1P5}: ../../GLOSSARY.md#gating-charge names no heading"
    ]
    assert library.check_links(dict(files, **{KV1P5: gone})) == [
        f"C4 {KV1P5}: ../../../NO_SPEC.md names no file"
    ]


def test_c5_the_format_page_s_key_tables_are_the_manifest_s(files):
    text, tables = files[library.FORMAT_PAGE], library.format_tables()
    assert library.check_format(text, tables, declarations.FORMAT) == []
    assert set(library.format_tables()) <= set(library.page_tables(text))
    added = dict(tables, **{"Piece keys": (*declarations.PIECE_KEYS, "summary")})
    assert library.check_format(text, added, declarations.FORMAT) == [
        f"C5 {library.FORMAT_PAGE}: 'Piece keys' lacks the code's key summary"
    ]
    dropped = text.replace("| `line` |", "| line |", 1)
    assert library.check_format(dropped, tables, declarations.FORMAT) == [
        f"C5 {library.FORMAT_PAGE}: 'Piece keys' lacks the code's key line"
    ]
    assert library.check_format(text, tables, "cells.declarations@4") == [
        f"C5 {library.FORMAT_PAGE}: it names the format cells.declarations@4"
    ]


def test_new_writes_a_page_with_its_blocks_filled_and_refuses_one_that_exists(doc, files):
    path, text = library.new_page(doc, files, "law", "cells.channel.kir2p1_mh2@1")  # A bare ID is in cells.
    assert path == "docs/library/cells/laws/channel.kir2p1_mh2@1.md"
    names = [m.group("name") for m in library.MARKER.finditer(text)]
    assert sorted(names) == sorted(library.BLOCKS.values())
    assert [f for f in library.check_blocks(doc, dict(files, **{path: text})) if path in f] == []
    unfinished = library.check_layers(doc, {path: text})
    assert any("the plain name is not written" in f for f in unfinished)
    assert any("'In plain words' is not written" in f for f in unfinished)
    with pytest.raises(SystemExit, match="exists"):
        library.new_page(doc, files, "law", "cells.channel.kv1p5_mh@1")
