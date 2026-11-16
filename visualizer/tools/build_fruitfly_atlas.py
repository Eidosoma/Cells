#!/usr/bin/env python3
"""Build the viewer's data on the fruit fly, Drosophila melanogaster: the species with its levels and
placeholder outlines, its side of the protein atlas, and its own proteins on shelves.

Six files are written, each from saved answers of public databases:

    data/species/fruitfly.json           the species file (schema/SPECIES.md)
    data/species/shapes/fruitfly.json    placeholder outlines of the fly and its wings (schema/SPECIES_SHAPES.md)
    data/proteins/atlases/fruitfly.json  its side of the protein atlas (schema/SPECIES_ATLAS.md)
    data/proteins/fruitfly/              shelves.json, proteins.tsv and README.md (schema/SPECIES_PROTEINS.md,
                                         "A curated proteome"), for the whole reference proteome

The catalogue is UniProt's whole reference proteome of the fly, reviewed entries and unreviewed ones
(the user, 15 November 2026: "on whole reference proteome"). One protein is shown for each gene: the
one that UniProt's own gene-by-gene set of the proteome gives as canonical. The proteome's other
entries for the same gene are a count on it.

    python3 tools/build_fruitfly_atlas.py fetch --datasets DATA     the only step that uses the network
    python3 tools/build_fruitfly_atlas.py build --datasets DATA     the same bytes every time
    python3 tools/build_fruitfly_atlas.py members --out DIR         the members' files, for the page

DATA holds every species' downloads, one folder per source with a MANIFEST.json. The shelves'
machinery (the download step, the reading of a whole proteome's entries, the vocabulary of places,
the placement, the families, the districts, the lines, the files and the search for the families of
Cells' units) is tools/lib/proteome_shelves.py, which every species' tool shares, here with the
human's own table of an animal cell's shelves; the families asked of every species are those of
tools/build_mpneumoniae_atlas.py, read and never changed. A change to either shows in this tool's
byte-for-byte test.

This is the viewer's reference data. Nothing of the fly is in the engine. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import build_mpneumoniae_atlas as M  # noqa: E402  the families asked of every species, read and never changed
from lib import proteome_shelves as P  # noqa: E402  the shelves' machinery

SNAPSHOT = ROOT / "data" / "proteins" / "inventory.snapshot.json"
SPECIES_FILE = ROOT / "data" / "species" / "fruitfly.json"
SHAPES_FILE = ROOT / "data" / "species" / "shapes" / "fruitfly.json"
ATLAS_FILE = ROOT / "data" / "proteins" / "atlases" / "fruitfly.json"
OUT_DIR = ROOT / "data" / "proteins" / "fruitfly"
PATHS = re.compile(r"/(?:home|mnt|Users|tmp)/")
MINE = "the visualizer's fruit fly agent"
TOOL = "tools/build_fruitfly_atlas.py"

SPECIES_ID, LABEL, ORGANISM, TAXON, PROTEOME = "fruitfly", "Fruit fly", "Drosophila melanogaster", 7227, "UP000000803"
UNIPROT = "https://rest.uniprot.org"
GENE_SETS = "https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/reference_proteomes"
KB = "fruitfly/uniprot-fruitfly-reference-proteome"
FLYBASE = "fruitfly/terms-flybase"
HUMAN_KB, KB_DOCS, IPR, GO, BIG_PI = "human/uniprot-human-reviewed-proteome", "human/uniprot-docs-and-terms", "human/interpro-entries-tree-and-go", "human/geneontology-go-basic", "human/terms-big-pi"
PLACES_FILE = f"uniprotkb_{PROTEOME}_places.json.gz"
SIGNATURES_FILE = f"uniprotkb_{PROTEOME}_signatures.tsv.gz"
CANONICAL_FILE = f"{PROTEOME}_{TAXON}.fasta.gz"
ALL = f"(proteome:{PROTEOME})"
PLACE_FIELDS = "accession,id,protein_name,gene_primary,xref_flybase,length,protein_existence,cc_subcellular_location,ft_transmem,ft_intramem,ft_signal,ft_transit,ft_topo_dom,ft_lipid,cc_alternative_products,fragment"
FLYBASE_TERMS = r"All annotations and data produced by FlyBase that are accessible from flybase\.org are distributed under a Creative Commons Attribution 4\.0 International License \(CC BY 4\.0\)"

SOURCES = {
    KB: {"what": f"UniProtKB: every entry of the reference proteome {PROTEOME} of Drosophila melanogaster, reviewed and unreviewed, with its name, gene, FlyBase gene, length, level of evidence, stated places with the evidence for each, segments, signals and anchors; the InterPro entries and Gene Ontology terms of each; the proteome's record and counts; UniProt's gene-by-gene set of the proteome (one protein for each gene) with the page that explains it; and UniProt's help page on its automatic annotation", "licence": "CC BY 4.0"},
    FLYBASE: {"what": "FlyBase's own statement of its licences, read before linking to it. Nothing else of FlyBase was downloaded", "licence": "CC BY 4.0 for its annotations and data, as the page states"},
}

# Places that fly entries state and the human's table has no line for (filled as the build asks).
PLACES_MORE = {}
# The cell the shared machinery places the fly's proteins in: an animal cell's, as the human's.
CELL = P.Cell(P.ANIMAL_CELL.shelves, {**P.ANIMAL_CELL.places, **PLACES_MORE}, P.ANIMAL_CELL.faces, P.ANIMAL_CELL.away, notes=P.ANIMAL_CELL.notes)

UPSTREAM = ["PROSITE", "HAMAP", "TMHMM", "Phobius", "SignalP", "TargetP", "Memsat", "Predotar", "big-PI"]
TABLE_COLUMNS = P.PROTEOME_COLUMNS

GENE_DB = ("FlyBase", "FBgn")  # the database whose gene identifiers tie a gene's entries together, and how they begin


# ---------------------------------------------------------------------------------------
# Fetch (the download step the species' tools share, with this tool's requests)
# ---------------------------------------------------------------------------------------

def requests():
    out = []

    def add(source, file, url, purpose, **more):
        out.append({"source": source, "file": file, "url": url, "purpose": purpose, **more})

    q = P.q
    stream = f"{UNIPROT}/uniprotkb/stream?query={q(ALL)}&compressed=true"
    add(KB, PLACES_FILE, f"{stream}&format=json&fields={PLACE_FIELDS}", "every entry of the proteome: its name, gene, FlyBase gene, length and level of evidence, where the entry places it and on what evidence, its segments, signals and anchors", gzip=True)
    add(KB, SIGNATURES_FILE, f"{stream}&format=tsv&fields=accession,xref_interpro,go_id", "the InterPro entries and the Gene Ontology terms UniProt gives each entry", gzip=True)
    count = lambda query: f"{UNIPROT}/uniprotkb/search?query={q(query)}&size=1&fields=accession&format=json"
    for name, query in (("all", ALL), ("reviewed", f"{ALL} AND (reviewed:true)"), ("unreviewed", f"{ALL} AND (reviewed:false)"), ("reviewed_with_place", f"{ALL} AND (reviewed:true) AND (cc_scl_term:*)"), ("unreviewed_with_place", f"{ALL} AND (reviewed:false) AND (cc_scl_term:*)")):
        add(KB, f"count_{name}.json", count(query), f"how many entries of the proteome: {name.replace('_', ' ')} (the count is in the answer's header)")
    add(KB, f"proteome_{PROTEOME}.json", f"{UNIPROT}/proteomes/{PROTEOME}", "the proteome's own record: its counts and its genome assembly")
    add(KB, CANONICAL_FILE, f"{GENE_SETS}/Eukaryota/{PROTEOME}/{CANONICAL_FILE}", "UniProt's gene-by-gene set of the proteome: one protein for each gene. Only the names of its entries are read", gzip=True)
    add(KB, "reference_proteomes_README.txt", f"{GENE_SETS}/README", "UniProt's explanation of the gene-by-gene sets of its reference proteomes", contains="gene")
    add(KB, "help_arba.json", f"{UNIPROT}/help/arba", "UniProt's help page on ARBA, the rule system behind most statements of its unreviewed entries", contains="ARBA")
    add(FLYBASE, "flybase_about.html", "https://wiki.flybase.org/wiki/FlyBase:About", "FlyBase's statement of its licences", contains="FlyBase")
    return out


def fetch(datasets, refresh=False):
    return P.fetch(datasets, requests(), SOURCES, MINE, TOOL, refresh=refresh)


# ---------------------------------------------------------------------------------------
# The outlines: a fly with its wings folded back, as a placeholder
# ---------------------------------------------------------------------------------------

BODY_UM, WING_UM = 2500, 2000  # the picture's choice: no measurement was read for this file


def outlines():
    hump = lambda x, start, end, peak: peak * math.sin(math.pi * (x - start) / (end - start)) ** 0.55 if start < x < end else 0
    body = []
    for x in range(0, BODY_UM + 1, 50):
        wide = max(hump(x, 0, 520, 700), hump(x, 430, 1420, 880), hump(x, 1300, BODY_UM, 900))
        high = max(hump(x, 0, 520, 620), hump(x, 430, 1420, 920), hump(x, 1300, BODY_UM, 780))
        body.append([x, 0, 0, round(wide), round(high)])
    wing = lambda side: [[round(950 + WING_UM * t), round(430 + 60 * t), round(side * (260 + 120 * t)), round(880 * math.sin(math.pi * t) ** 0.55) if 0 < t < 1 else 0, 14 if 0 < t < 1 else 0] for t in [step / 20 for step in range(21)]]
    wing_look = {"rings": {"every": 4, "first": 2, "points": 18}, "lines": [0.5, 1.5], "strength": 0.8, "alone": 0.95, "edge": 0.8, "pick": 10}
    return {
        "format": "cells.visualizer.outline@1",
        "note": f"A fruit fly with its wings folded back over its body, as placeholder outlines. The fly is drawn {BODY_UM / 1000:g} mm long and each wing {WING_UM / 1000:g} mm long: these sizes, the widths and the proportions are the picture's choice, and no measurement was read for them. The numbers were written out by tools/build_fruitfly_atlas.py from three rounded humps for the head, the thorax and the abdomen, and one flat blade for each wing.",
        "tissue_on": {"at_um": [1950, 468, -320], "clearance_um": 3, "note": "On the left wing, about half-way along it."},
        "parts": [
            {"name": "body", "kind": "loft", "stations": body, "rings": {"from": 0.04, "to": 0.97, "step": 0.04, "points": 28}, "lines": [0.25, 0.5, 0.75, 1.25, 1.5, 1.75], "strength": 0.5, "edge": 1, "fill": 0.07, "pick": 20, "context": {"edge": 0.4, "fill": 0.06}},
            {"name": "left wing", "group": "wings", "kind": "loft", "stations": wing(-1), **wing_look},
            {"name": "right wing", "group": "wings", "kind": "loft", "stations": wing(1), **wing_look},
        ],
    }


# ---------------------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------------------

# Proteins a reader would look for under a unit that the search by signature does not list.
NEAR = {"U11": ["Shab"], "U12": ["Shab"]}


def said_near(entries, filing):
    """A unit's note, with a sentence on each protein a reader would look for there and the
    search by signature does not list: what it carries instead."""
    def more(unit_id, families, finding, note):
        for near in NEAR.get(unit_id, []):
            accession = next(a for a in entries if entries[a]["gene"] == near)
            under = filing.family.get(accession)
            if finding != "none found" or not under:
                raise SystemExit(f"{unit_id}: the sentence on {near} no longer holds; read the unit's finding again")
            note += f" The fly's {near}, a voltage-gated potassium channel by its entry's name (\"{entries[accession]['name']}\"), carries the signature of another family of such channels ({under}, {filing.names[under]['name']}) and not this one, so a search by signature does not list it."
        return note
    return more


def build(datasets_folder, snapshot):
    d = P.Datasets(datasets_folder)
    must = lambda source, file, pattern, field=None: P.holds(d, source, file, pattern, field)
    must(KB_DOCS, "terms_uniprot_license.json", r"We have chosen to apply the \[?Creative Commons Attribution 4\.0 International \(CC BY 4\.0\) License\]?(\([^)]*\))? to all copyrightable parts of our databases", "content")
    must(IPR, "terms_interpro_license.html", r"All of the InterPro, Pfam, PRINTS and SFLD downloadable data provided on the InterPro website is freely available under CC0 1\.0 Universal")
    must(GO, "go_citation_policy.html", r"licensed under the Creative Commons Attribution 4\.0 Unported License")
    # The fetch step asks for FlyBase's statement of its licences; the build does not need it, since nothing of FlyBase is taken.
    must(KB, "help_arba.json", r"ARBA", "content")
    must(*P.SAVED_TERMS["prosite"], r"distributed under the Creative Commons Attribution-NonCommercial-NoDerivatives \(CC BY-NC-ND 4\.0\) License")
    must(*P.SAVED_TERMS["hamap"], r"distributed under the Creative Commons Attribution \(CC BY 4\.0\) License")
    for tool in ("tmhmm", "signalp", "targetp"):
        must(*P.SAVED_TERMS[tool], rf"ACADEMIC SOFTWARE LICENSE AGREEMENT FOR END-USERS AT PUBLICLY FUNDED ACADEMIC, EDUCATION OR RESEARCH INSTITUTIONS FOR THE USE OF {tool}")
    must(*P.SAVED_TERMS["phobius"], r"Phobius is intended for academic users only")
    must(BIG_PI, "gpi_server.html", r"big-PI Predictor")
    must(KB_DOCS, "help_transmem.json", r"predicted by the application of the predictive tools TMHMM, Memsat, Phobius and the hydrophobic moment plot method", "content")
    must(KB_DOCS, "help_signal.json", r"predicted by the application of the predictive tools Phobius, Predotar, SignalP and TargetP", "content")

    vocabulary = P.Vocabulary(d, KB_DOCS, CELL)
    every, read = P.read_proteome(d, KB, PLACES_FILE, vocabulary, GENE_DB)
    total, release, proteome = P.proteome_totals(d, KB, PLACES_FILE, SIGNATURES_FILE, PROTEOME, TAXON, vocabulary, every, read)

    # --- the catalogue: one protein for each gene, as UniProt's gene-by-gene set gives it ---------------
    entries, together, stated = P.one_for_each_gene(d, KB, CANONICAL_FILE, every, total, proteome, "no_flybase_gene")
    filing = P.Filing(d, entries, KB, SIGNATURES_FILE, IPR, GO, catalogue=True)
    placed = {accession: P.place(entry, vocabulary) for accession, entry in entries.items()}
    gene = lambda accession: entries[accession]["gene"] or accession

    # --- the atlas: the families behind Cells' units, asked of this organism ---------------------------
    units, unit_ids, beside = P.find_units(snapshot, entries, filing, P.human_signatures(d, HUMAN_KB), M.FAMILIES, M.UNITS, P.NOTHING, "the fly", other_said=", as on the planarian's side of the atlas", more=said_near(entries, filing))

    # --- the lines of the shelves -----------------------------------------------------------------------
    lines, alone, rest = P.make_lines(entries, placed, filing, unit_ids, CELL)
    sequence = P.in_order(entries, lines, alone, rest)
    shelf_counts, counts, bases, rules, evidence = P.counted(placed, CELL)
    # How sure: what stands behind each protein's place, for curated entries and for automatic ones.
    how_sure, kinds = P.how_sure(entries, placed), P.SURE
    family_total = Counter(filing.family.values())
    distinct = len({line["id"] for line in lines})
    lone_families = sum(1 for size in family_total.values() if size <= P.LONE_UP_TO)
    shelves, no_shelf = P.shelf_rows(CELL, shelf_counts, lines, alone, rest)
    groups = P.district_rows(lines, alone)
    places, place_words, first_places, used = P.place_rows(entries, placed, vocabulary)

    resting, rule_ids = P.account(entries, placed)
    if set(resting) - P.OWNERS:
        raise SystemExit(f"a placement rests on a rule system or a program this tool does not name: {sorted(set(resting) - P.OWNERS)}")
    of = lambda owner, what="placements": resting.get(owner, {}).get(what, 0)
    PLACE, SPANS, FACE, FROM_SEGMENTS, FROM_SIGNAL = P.ON_PLACE, P.ON_SPANS, P.ON_FACE, P.FROM_SEGMENTS, P.FROM_SIGNAL
    named = lambda owner: f"{of(owner):,} ({of(owner, FROM_SEGMENTS):,} by a side read from segments, {of(owner, FROM_SIGNAL):,} from a signal peptide, {of(owner, SPANS) + of(owner, PLACE) + of(owner, FACE):,} behind a statement)"
    made = d.last_day()
    header = {
        "format": P.SHELF_FORMAT, "species": SPECIES_ID, "made": made,
        "from": f"UniProtKB release {release}: the reference proteome {PROTEOME} of Drosophila melanogaster, {stated['entries']:,} entries ({stated['reviewed']:,} reviewed, {stated['unreviewed']:,} unreviewed) for {stated['genes']:,} genes. One protein is shown for each gene, the one that UniProt's own gene-by-gene set of the proteome gives: {stated['shown']:,} proteins, {stated['shown_reviewed']:,} with a reviewed entry and {stated['shown_unreviewed']:,} with an unreviewed one. The proteome's other {stated['further']:,} entries are further forms of the same genes; each protein counts its gene's entries in the mark 'entries'.",
        "from_counts": stated,
        "predicted": False,
        "curated": {"note": "A reviewed entry was written by a curator; an unreviewed one was annotated automatically, by rule systems and prediction programs. The table says, for the proteins shown, what stands behind each one's place.", "columns": ["what stands behind the place", "reviewed", "unreviewed"], "rows": [[kind, how_sure[kind]["reviewed"], how_sure[kind]["unreviewed"]] for kind in kinds]},
        "shelves": shelves, "no_shelf": no_shelf, "groups": groups,
        "groups_from": "A protein's Gene Ontology terms are those InterPro maps to any of its signatures and those UniProt gives its entry. With every broader term (by the ontology's kind-of and part-of links), the protein falls in the first district, in the order listed, one of whose terms it carries. A family's line stands in the district most of its classed members on that shelf fall in; of equal counts, the first listed. A protein that is the only member of its family stands in its own district. A part of no_family stands in a district only if more than half of all its members on that shelf fall there. The choice of the districts' terms and their order is the viewer's, and is the planarian's and the human's.",
        "family_from": f"A family is an InterPro entry of the type Family (InterPro {filing.release}). A protein is filed under the narrowest family among the InterPro entries UniProt gives it: one that is not a broader kind of another it carries, by InterPro's tree of entries. Where several unrelated families remain ({filing.several:,} proteins), it is the deepest in that tree, then the one fewest proteins of this catalogue are in, then the first by accession. This is the rule of the planarian's and the human's files, so a family has the same id in each.",
        "family_columns": P.FAMILY_COLUMNS,
        "family_notes": {
            "lines": "A family has one line for each shelf that holds members of it, and one with a null shelf for its members that are on no shelf. A line is identified by id and shelf together; side, group, count, sides, file, at and units are of its members on that shelf alone.",
            "side": "The side most of the line's members sit on; of equal counts, a membrane first.",
            "units": P.UNITS_NOTE,
            "total": "The family's members on every shelf and on none.",
            "counts": "distinct_families is the number of families that have lines; families_in_all counts also the families of one, whose proteins are under 'lone'.",
        },
    }
    lone = P.lone_block(alone, lone_families)
    no_family = P.no_family_block(filing, placed)
    files = sorted({line["file"] for line in [*lines, *alone, *rest]})
    tail = {
        "member_columns": P.MEMBER_COLUMNS,
        "members_from": {
            "table": f"data/proteins/{SPECIES_ID}/{P.TABLE_FILE}", "format": P.MEMBERS_FORMAT,
            "order": "The table's lines are the members in order: every line of the families as listed here, then every part of 'lone', then every part of 'no_family'; within each, by gene name. A line's members are the next 'count' lines of the table. For a family's line and for a part of no_family, 'under' is its id and 'shelf' its shelf (empty for none); for a part of 'lone', 'under' is the protein's own family and 'family' that family's name.",
            "files": f"A file holds the members of consecutive lines: a new file begins where the next line would take it past {P.MEMBERS_PER_FILE:,} members, so a line is never split. 'file' names the file and 'at' the first and one past the last of its members there.",
            "places": "In the table a stated place is written with UniProt's identifiers, without their prefix: the place, then the topology and the face where the entry states them, joined by a full stop. 'place_words' gives the words of each.",
            "letters": P.letters(),
            "step": f"python3 {TOOL} members --out DIR writes the files from the two files.",
        },
        "side_notes": {
            "stated": "The protein's UniProtKB entry states where it is, and the first place it states decides the shelf and the side. For a reviewed entry the statement is a curator's, and the mark 'evidence' says what stands behind it: an experiment, likeness to another protein, the curator's inference, or a rule. For an unreviewed entry no curator wrote it: the statement was made by one of UniProt's rule systems, and its evidence is 'rule'.",
            "predicted": f"Read from the entry's own features, where its words do not give the side. A membrane-spanning segment puts the protein in a membrane; a signal peptide with no such segment puts it on the side away from the cytoplasm. Where the entry states no place, the protein stands on the shelf of a membrane that is not named. In a reviewed entry UniProt's curators annotate these features, and its pages name the predictors behind the predicted ones: {P.PREDICTORS}. In an unreviewed entry the program is named on each feature. Each is named among the sources, with its terms and what rests on it. {P.RULING}",
            "none": "The entry states a membrane or a place and not the side (the protein then stands apart beside that shelf, with the place in its mark 'where'), or it states no place of the cell and carries no membrane-spanning segment and no signal peptide (the protein is then on no shelf). Nothing is placed by guess.",
        },
        "placed_by": [{"rule": rule, "basis": basis, "what": what, "proteins": rules[rule]} for rule, basis, what in P.RULES_USED],
        "place_kinds": P.KINDS,
        "place_columns": P.PLACE_COLUMNS,
        "place_notes": "Every place the entries state, in UniProt's words, with the shelf and what the place names against its membrane (place_kinds), how the table's line was reached and which of the table's terms it rests on, and how many proteins it places as the statement that decided.",
        # How the atlas found each protein listed with a unit, where it is not the default (schema/SPECIES_PROTEINS.md).
        **({"found_by": found_by} if (found_by := P.found_by_block(units, P.line_families(lines))) else {}),
    }
    marks = {
        "reviewed": {"label": "Curated entry", "values": [True, False], "measured": False, "note": "Whether the protein's UniProtKB entry is reviewed, written by a curator, or unreviewed, annotated automatically.", "source": "UniProt"},
        "entries": {"label": "Entries for its gene", "values": "number", "measured": False, "note": "The proteome's entries for the same gene, by the FlyBase gene that UniProt gives each entry: this protein's own and the further forms of the gene. The marker stands for the one UniProt's gene-by-gene set names.", "source": "UniProt"},
        "isoforms": {"label": "Isoforms described", "values": "number", "measured": False, "note": "The canonical sequence and the other sequences its own entry describes.", "source": "UniProt"},
        "seen": {"label": "Evidence that the protein exists", "values": [P.SEEN[level] for level in sorted(P.SEEN)], "measured": False, "note": "UniProt's level of evidence for the entry: at protein level, at transcript level, inferred from homology, predicted, or uncertain.", "source": "UniProt"},
        "evidence": {"label": "What stands behind the stated place", "values": [word for word, _, _ in P.EVIDENCE] + [P.NOT_GIVEN], "measured": False, "note": "From UniProt's evidence codes on the statement: an experiment in a paper the entry cites; likeness to a protein of which it is known; a curator's inference; a rule (a family rule or a sequence model that a curator applied, or, in an unreviewed entry, one of UniProt's automatic rule systems); not given, an older curated statement. Of several, the first in this order.", "source": "UniProt"},
        "where": {"label": "Stated place", "values": "text", "measured": False, "note": "The statement that decided the shelf, in UniProt's words: the place, then the topology and the face where the entry states them.", "source": "UniProt"},
        "also": {"label": "Also stated", "values": "text", "measured": False, "note": "The entry's other statements of place, in order and in UniProt's words.", "source": "UniProt"},
        "family": {"label": "Family, of which it is the only member here", "values": "text", "measured": False, "note": "The InterPro family's accession and name, for a protein listed among the only members of their families.", "source": "InterPro"},
        "of": {"label": "Stated for", "values": "text", "measured": False, "note": "The named form of the protein that the place is stated for, where the entry states none for the protein as a whole.", "source": "UniProt"},
    }
    terms_day = lambda name: d.day(*P.SAVED_TERMS[name])
    own_said = "; ".join(f"{owner} {of(owner):,}" for owner in P.OWN_SYSTEMS if of(owner))
    sources = [
        {"name": "UniProt", "url": "https://www.uniprot.org/", "release": release, "accessed": d.day(KB, PLACES_FILE), "licence": "CC BY 4.0", "class": "permissive", "cite": P.CITE_UNIPROT,
         "holds": f"for each entry of the fly's reference proteome: its name, gene, FlyBase gene, length and level of evidence, the places it states with the evidence for each, its membrane-spanning segments, signal peptide and anchors, and the InterPro entries and Gene Ontology terms UniProt gives it; the gene-by-gene set of the proteome; and UniProt's vocabulary of places. The programs and rule systems of other owners behind its statements are sources below. Placements that rest on UniProt's own automatic systems alone: {own_said or 'none'}"},
        {"name": "InterPro", "url": "https://www.ebi.ac.uk/interpro/", "release": filing.release, "accessed": d.day(IPR, "entry.list"), "licence": "CC0 1.0", "class": "permissive", "cite": P.CITE_INTERPRO, "holds": "the type and name of each entry, the tree of broader and narrower entries, and the mapping of entries to Gene Ontology terms"},
        {"name": "Gene Ontology", "url": "https://geneontology.org/", "release": filing.ontology, "accessed": d.day(GO, "go-basic.obo"), "licence": "CC BY 4.0", "class": "permissive", "cite": P.ontology_citation(d, GO), "holds": "the names of terms and which term is a kind or a part of which; no term's text is copied beyond the names of the districts' terms"},
        P.through_uniprot("PROSITE", terms_day("prosite"), f"Nothing was downloaded from it but its statement of terms, and nothing of it is copied. Its rules (ProRule) are named in UniProt's entries as what stands behind a statement. {of('PROSITE-ProRule'):,} placements rest on them alone: {of('PROSITE-ProRule', PLACE):,} by the statement of place that decides the shelf ({len(rule_ids.get('PROSITE-ProRule', {})):,} rules), {of('PROSITE-ProRule', SPANS):,} by the statement that the protein spans the membrane, and {of('PROSITE-ProRule', FROM_SEGMENTS) + of('PROSITE-ProRule', FROM_SIGNAL):,} by a side read here from a feature that a rule gives."),
        P.through_uniprot("HAMAP", terms_day("hamap"), f"Nothing was downloaded from it but its statement of terms. Its family rules are named in UniProt's entries as what stands behind a statement: {of('HAMAP-Rule'):,} placements rest on them alone."),
        P.through_uniprot("TMHMM", terms_day("tmhmm"), f"{P.NOT_RUN} {P.FOUR_SEGMENTS}. In reviewed entries {of('segments'):,} placements rest on segments that an entry gives by sequence analysis alone ({of('segments', FROM_SEGMENTS):,} read here from such segments, {of('segments', SPANS):,} statements of spanning, {of('segments', PLACE):,} stated places). In unreviewed entries UniProt names the program on each feature: TMHMM on {named('TMHMM')}."),
        P.through_uniprot("Phobius", terms_day("phobius"), f"{P.NOT_RUN} In reviewed entries, one of the four methods for segments and of the four for signal peptides: the placements counted under TMHMM ({of('segments'):,}) and SignalP ({of('signal'):,}). In unreviewed entries UniProt names it on each feature: {named('Phobius')}."),
        P.through_uniprot("SignalP", terms_day("signalp"), f"{P.NOT_RUN} {P.FOUR_SIGNALS}. In reviewed entries {of('signal'):,} placements rest on a signal peptide that an entry gives by sequence analysis alone. In unreviewed entries UniProt names the program on each feature: SignalP on {named('SignalP')}."),
        P.through_uniprot("TargetP", terms_day("targetp"), f"{P.NOT_RUN} {P.FOUR_SIGNALS}. The placements are those counted under SignalP for reviewed entries ({of('signal'):,})."),
        P.through_uniprot("Memsat", d.day(KB_DOCS, "help_transmem.json"), f"Nothing was downloaded from it. {P.FOUR_SEGMENTS}. The placements are those counted under TMHMM for reviewed entries ({of('segments'):,})."),
        P.through_uniprot("Predotar", d.day(KB_DOCS, "help_signal.json"), f"Nothing was downloaded from it. {P.FOUR_SIGNALS}. The placements are those counted under SignalP for reviewed entries ({of('signal'):,})."),
        P.through_uniprot("big-PI", d.day(BIG_PI, "gpi_server.html"), f"Nothing was downloaded from it but its own page, and the program was not run here. The predictor that UniProt's help names for the GPI anchors it predicts. {of('big-PI'):,} placements rest on a GPI anchor that the entry states on a sequence analysis alone: such an anchor puts the protein on the face away from the cytoplasm."),
    ]
    sources = [source for source in sources if source["name"] != "big-PI" or of("big-PI")]
    closing = {"marks": marks, "counts": counts, "shelf_counts": shelf_counts, "by_basis": P.by_basis(bases), "by_evidence": P.by_evidence(evidence), "sources": sources}

    body = P.shelves_text(header, lines, alone, rest, lone, no_family, tail, places, place_words, closing, len(family_total))
    table = P.table_text(TABLE_COLUMNS, sequence, entries, placed, filing, alone, unit_ids, more=P.proteome_values(entries, together))

    # --- the species file and its outlines ---------------------------------------------------------------
    findings = Counter(unit["finding"] for unit in units.values())
    species = {
        "format": "cells.visualizer.species@1", "id": SPECIES_ID, "label": LABEL, "organism": ORGANISM, "taxon": TAXON,
        "plain": f"The fruit fly of the laboratory: {stated['genes']:,} genes in UniProt's reference proteome, with one protein shown for each. Many of the channels and pumps Cells has laws for have a counterpart of the same family in it.",
        "group": "Animals", "order": 25, "default": False, "made": made,  # after the other animals, before the bacteria
        "modelled": {"state": "generic", "text": "Cells models a generic cell and a sheet of such cells, not this animal. The sheet is drawn on a wing for the scales only. The wings and the fly are placeholder outlines: nothing at those scales is simulated."},
        "levels": [
            {"id": "molecules"},
            {"id": "cell", "shape": {"kind": "prism", "sides": 6, "radius_um": 10.6, "height_um": 13, "corner_um": 2.4, "edge_um": 1.3},
             "note": "The cell drawn is a generic animal cell, as one of a layer; it is not a model of a cell type of the fly. Its shape and its sizes are the picture's choice: six flat sides where it meets its neighbours, about 20 µm across.",
             "notes": [{"text": "A generic animal cell, as one of a layer"}, {"text": "Its flat-sided shape is the picture's choice", "roomy": True}], "fade_out_um": [120, 190]},
            {"id": "tissue", "shape": {"kind": "cell sheet", "rings": 6, "beyond": [[8, 0.34], [10, 0.2], [11, 0.1]]},
             "note": "The sheet is the one Cells simulates: a single layer of coupled cells. It stands for no particular tissue of the fly.",
             "notes": [{"text": "The sheet Cells simulates: a single layer of coupled cells", "short": "The simulated sheet"}], "fade_in_um": [100, 190]},
            {"id": "organ", "label": "Wing", "shape": {"kind": "outline", "ref": SPECIES_ID, "parts": ["wings"], "context": ["body"]},
             "note": f"The outline drawn is a fly's two wings, folded back over its body, as a placeholder. The wing is the picture's choice of organ: a visitor knows it, and the project's record names the Drosophila wing disc as a long-term target of its work on how a tissue takes its shape (the user's decisions of 9 November 2026 on the morphogenesis plan). No wing and no wing disc is modelled. The sheet of cells is drawn on a wing so that the scales follow one another; it is not the wing's tissue. Each wing is drawn {WING_UM / 1000:g} mm long: the picture's choice, since no measurement was read for this file.",
             "sheet_mark": {"band": 0.05, "note": "The sheet, to scale: drawn on a wing for the scales only"},
             "notes": [{"text": "A fly's wings: a placeholder outline"}, {"text": "The wing's own cells are not modelled", "lift": -22, "roomy": True}]},
            {"id": "organism", "label": "Whole fly", "shape": {"kind": "outline", "ref": SPECIES_ID},
             "note": f"The outline drawn is a fruit fly with its wings folded back, {BODY_UM / 1000:g} mm long, as a placeholder. The sheet of cells is drawn on a wing for the scales only. The fly's length, its width and its proportions are the picture's choice: no measurement was read for this file.",
             "sheet_mark": {"band": 0.05, "note": "The sheet, to scale", "roomy": True}, "notes": [{"text": "A fruit fly: a placeholder outline"}]},
        ],
        "cell": {
            "facts": [
                {"label": "Proteins", "value": f"{stated['genes']:,} genes in UniProt's reference proteome, with {stated['entries']:,} entries: {stated['reviewed']:,} reviewed by a curator and {stated['unreviewed']:,} annotated automatically. One protein is shown for each gene", "sources": ["uniprot"]},
                {"label": "Cells' machines", "value": f"of the 49 units of the law inventory, {findings['found']} have proteins of the same family in the fly and {findings['different family']} are built from another family; {findings['none found']} were not found", "sources": ["uniprot"]},
            ],
            "parts": {"membranes": 1, "wall": False, "nucleus": True, "organelles": ["er", "golgi", "mitochondria"]},
        },
        "sources": {"uniprot": {"text": f"UniProt Consortium, UniProt release {release}: the reference proteome {PROTEOME} (Drosophila melanogaster), its entries and its gene-by-gene set.", "url": f"https://www.uniprot.org/proteomes/{PROTEOME}", "licence": "CC BY 4.0", "class": "permissive", "accessed": d.day(KB, PLACES_FILE)}},
    }
    atlas = {
        "format": P.ATLAS_FORMAT,
        "species": {"id": SPECIES_ID, "label": LABEL, "organism": ORGANISM, "taxon": TAXON, "plain": f"The fruit fly of the laboratory, with {stated['genes']:,} genes in UniProt's reference proteome. This is what the family signatures of Cells' machines find among the one protein shown for each gene."},
        "made": made,
        "method": [
            f"The fly's proteins are the {len(entries):,} of UniProt's gene-by-gene set of the reference proteome {PROTEOME} (release {release}): one for each gene, {stated['shown_reviewed']:,} with a reviewed entry and {stated['shown_unreviewed']:,} with an unreviewed one.",
            "Licences were read before anything was copied; each is stated in sources.",
            "Each unit's family was taken from its own human candidates, by the same InterPro signatures that the other species' atlases ask. The build checks that the candidates carry them.",
            "Each signature was looked for among the InterPro entries UniProt gives each protein. A unit counts as found only where a protein carries the signature of a family that makes the machine itself; an accessory family alone does not make it found.",
            "Where no protein carries the family the engine's law names and proteins carry another family asked for the same machine (innexins, for gap junctions), the finding is 'different family'.",
            P.TWO_FACTS,
            "Several units of one family (the Kv1 channels) list the same proteins, and nothing here says which protein does which unit's work.",
            "No similarity search was run, and nothing is called an ortholog.",
        ],
        "sources": [
            {"name": "UniProt", "url": "https://www.uniprot.org/", "release": release, "accessed": d.day(KB, PLACES_FILE), "licence": "CC BY 4.0", "class": "permissive", "cite": P.CITE_UNIPROT, "holds": "the entries of the fly's proteins, reviewed and unreviewed, with the InterPro entries UniProt gives each; the signatures of the units' human candidates"},
            {"name": "InterPro", "url": "https://www.ebi.ac.uk/interpro/", "release": filing.release, "accessed": d.day(IPR, "entry.list"), "licence": "CC0 1.0", "class": "permissive", "cite": P.CITE_INTERPRO, "holds": "the identifiers and names of the family signatures"},
        ],
        "not_copied": "No sequence is copied. FlyBase is linked to; nothing was downloaded from it, and the FlyBase genes used here are those UniProt gives its entries.",
        "units": units,
        "extra": [],
    }
    report = {
        "release": release, "interpro": filing.release, "ontology": filing.ontology, "made": made, "stated": stated, "read": dict(read),
        "shelf_counts": shelf_counts, "counts": counts, "bases": {f"{side} / {basis}": n for (side, basis), n in sorted(bases.items())}, "rules": {rule: rules[rule] for rule, _, _ in P.RULES_USED},
        "evidence": dict(evidence), "how_sure": how_sure, "resting": resting, "rule_systems": {owner: len(found) for owner, found in rule_ids.items()},
        "families": len(family_total), "in_families": len(filing.family), "several": filing.several, "no_family": len(filing.part),
        "family_sizes": {"one": sum(1 for size in family_total.values() if size == 1), "two to four": sum(1 for size in family_total.values() if 2 <= size <= 4), "five or more": sum(1 for size in family_total.values() if size >= 5)},
        "largest_families": [[filing.names[family]["name"], n] for family, n in sorted(family_total.items(), key=lambda pair: (-pair[1], pair[0]))[:8]],
        "lines": len(lines), "distinct": distinct, "lone": lone["count"], "lone_parts": len(alone), "part_lines": len(rest), "groups": groups, "member_files": files, "places_used": len(used),
        "findings": dict(findings), "found_units": {unit: [product["gene"] for product in found["products"]] for unit, found in units.items() if found["products"]}, "beside": {gene(a): what for a, what in beside.items()},
        "with_units": len(unit_ids), "entries_per_gene": dict(sorted(Counter(min(n, 6) for n in together.values()).items())),
    }
    files_out = {"shelves": body, "table": table, "species": json.dumps(species, indent=1, ensure_ascii=False) + "\n", "shapes": json.dumps(outlines(), ensure_ascii=False, separators=(",", ":")) + "\n", "atlas": json.dumps(atlas, indent=1, ensure_ascii=False) + "\n"}
    files_out["readme"] = build_readme(report, header, closing)
    report["sizes"] = P.within_limits(files_out, PATHS)
    return files_out, report


def build_readme(report, header, closing):
    r = report
    names = {shelf["id"]: shelf["label"] for shelf in header["shelves"]}
    lines = [
        "# The fruit fly: its own proteins, on shelves",
        "",
        "Generated by `tools/build_fruitfly_atlas.py`; do not edit by hand. The note is `docs/FRUITFLY.md`.",
        "",
        f"- `shelves.json`: {header['from']}",
        f"- `proteins.tsv`: one line for each of the {r['stated']['shown']:,} proteins shown, in the order of the shelves' lines. No sequences.",
        "- The members' files are not kept here: `python3 tools/build_fruitfly_atlas.py members --out DIR` cuts them from these two files.",
        "",
        "Nothing of the fly is in the engine. This is reference data for the viewer.",
        "",
        "## Shelves",
        "",
        "| Shelf | Proteins | Outside | In | Inside | Side not known |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
        *[f"| {names.get(name, 'On no shelf')} | {sum(found.values()):,} | {found['outside']:,} | {found['in']:,} | {found['inside']:,} | {found['not known']:,} |" for name, found in r["shelf_counts"].items()],
        "",
        "## How sure the places are",
        "",
        "| What stands behind the place | Reviewed entries | Unreviewed entries |",
        "| --- | ---: | ---: |",
        *[f"| {kind} | {found['reviewed']:,} | {found['unreviewed']:,} |" for kind, found in r["how_sure"].items()],
        "",
        "## Families",
        "",
        f"- {r['families']:,} InterPro families hold {r['in_families']:,} proteins: {r['family_sizes']['one']:,} of one, {r['family_sizes']['two to four']:,} of two to four, {r['family_sizes']['five or more']:,} of five or more. {r['no_family']:,} proteins have no family.",
        f"- {r['lines']:,} lines of {r['distinct']:,} families; the {r['lone']:,} only members of their families stand in {r['lone_parts']} parts; the proteins with no family in {r['part_lines']} lines.",
        "- The largest: " + "; ".join(f"{name} ({n})" for name, n in r["largest_families"]) + ".",
        f"- {r['with_units']:,} proteins carry the family signature of one of Cells' machines and name its units.",
        "",
        "## What rests on tools and rule systems of other owners",
        "",
        "By the project's rule (the user, 15 November 2026), a value stands on the terms of the database it was read from, here UniProt's, and the tool behind it is named and counted. It is the project's rule, not a legal opinion. Nothing was downloaded from any of these tools, and none was run.",
        "",
        "| Tool or rule system | Class | What rests on it |",
        "| --- | --- | --- |",
        *[f"| {source['name']} | {source['class']} | {source['holds']} |" for source in closing["sources"] if source.get("through")],
        "",
        "## Sources",
        "",
        *[f"- **{source['name']}** ({source['licence']}; read {source['accessed']}): {source['holds']}." for source in closing["sources"] if not source.get("through")],
        "",
    ]
    return "\n".join(lines)


def summary(report):
    r = report
    return "\n".join([
        f"UniProt {r['release']}, InterPro {r['interpro']}, Gene Ontology {r['ontology']}; made {r['made']}",
        f"proteome: {r['stated']}; read: {r['read']}",
        "by shelf: " + "; ".join(f"{shelf} {sum(sides.values()):,} {sides}" for shelf, sides in r["shelf_counts"].items()),
        f"sides: {r['counts']}; side and basis: {r['bases']}",
        f"rules: {r['rules']}",
        f"how sure: {r['how_sure']}",
        f"evidence behind the deciding statement: {r['evidence']}",
        f"families: {r['families']:,} holding {r['in_families']:,} (sizes {r['family_sizes']}); no family {r['no_family']:,}; lines {r['lines']:,} of {r['distinct']:,}; lone {r['lone']:,} in {r['lone_parts']} parts; part lines {r['part_lines']}; largest {r['largest_families'][:5]}",
        f"rests on, by owner: {r['resting']}; rules named: {r['rule_systems']}",
        f"atlas: {r['findings']}; accessory only {r['beside']}; proteins with units {r['with_units']}",
        "found: " + "; ".join(f"{unit} {len(genes)} ({', '.join(str(g) for g in genes[:4])})" for unit, genes in r["found_units"].items()),
        f"entries per gene (6 = six or more): {r['entries_per_gene']}; member files: {r['member_files']}; places used: {r['places_used']}; sizes: {r['sizes']}",
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("step", choices=["fetch", "build", "members"])
    parser.add_argument("--datasets", help="fetch, build: the folder that holds every species' downloads")
    parser.add_argument("--refresh", action="store_true", help="fetch: ask again even where an answer is saved")
    parser.add_argument("--out-dir", default=str(OUT_DIR), help="build: the folder for shelves.json, the table and their README.md; members: the folder that holds them")
    parser.add_argument("--out-species", default=str(SPECIES_FILE))
    parser.add_argument("--out-shapes", default=str(SHAPES_FILE))
    parser.add_argument("--out-atlas", default=str(ATLAS_FILE))
    parser.add_argument("--out", help="members: the folder to write the member files into")
    parser.add_argument("--report", help="build: also write what was counted, as JSON, to this file (kept outside the repository)")
    args = parser.parse_args()
    if args.step == "members":
        if not args.out:
            parser.error("members needs --out")
        P.write_members(args.out_dir, args.out, first=P.proteome_marks)
        return
    if not args.datasets:
        parser.error(f"{args.step} needs --datasets")
    if args.step == "fetch":
        sys.exit(1 if fetch(Path(args.datasets), refresh=args.refresh) else 0)
    files, report = build(Path(args.datasets), json.loads(SNAPSHOT.read_text(encoding="utf-8")))
    folder = Path(args.out_dir)
    for target, name in [(folder / P.SHELVES_FILE, "shelves"), (folder / P.TABLE_FILE, "table"), (folder / "README.md", "readme"), (Path(args.out_species), "species"), (Path(args.out_shapes), "shapes"), (Path(args.out_atlas), "atlas")]:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(files[name], encoding="utf-8")
        print(f"wrote {target.name} ({len(files[name].encode('utf-8')):,} bytes)")
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(summary(report))


if __name__ == "__main__":
    main()
