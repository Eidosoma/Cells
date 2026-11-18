#!/usr/bin/env python3
"""Build the viewer's data on the laboratory mouse, Mus musculus: the species with its levels and
placeholder outlines, its side of the protein atlas, and its own proteins on shelves.

Six files are written, each from saved answers of public databases and one open paper:

    data/species/mouse.json           the species file (schema/SPECIES.md)
    data/species/shapes/mouse.json    placeholder outlines of the mouse and its ears (schema/SPECIES_SHAPES.md)
    data/proteins/atlases/mouse.json  its side of the protein atlas (schema/SPECIES_ATLAS.md)
    data/proteins/mouse/              shelves.json, proteins.tsv and README.md (schema/SPECIES_PROTEINS.md,
                                      "A whole reference proteome")

The user, 16 November 2026: "we should probably also add the mouse ... same skin cell". Its cell
is therefore the planarian's: one cell of a sheet that stands for skin-like tissue. The catalogue
is UniProt's whole reference proteome of the mouse, reviewed entries and unreviewed ones, as the
fruit fly's is (the user, of the fly, 15 November 2026: "on whole reference proteome"). One
protein is shown for each gene: the one that UniProt's own gene-by-gene set of the proteome gives
as canonical. The proteome's other entries for the same gene are a count on it.

    python3 tools/build_mouse_atlas.py fetch --datasets DATA     the only step that uses the network
    python3 tools/build_mouse_atlas.py build --datasets DATA     the same bytes every time
    python3 tools/build_mouse_atlas.py members --out DIR         the members' files, for the page

DATA holds every species' downloads, one folder per source with a MANIFEST.json. The shelves'
machinery is tools/lib/proteome_shelves.py, which every species' tool shares, here with the
human's own table of an animal cell's shelves; the families asked of every species are those of
tools/build_mpneumoniae_atlas.py, read and never changed. A change to either shows in this tool's
byte-for-byte test.

This is the viewer's reference data. Nothing of the mouse is in the engine. Standard library only.
"""

from __future__ import annotations

import argparse
import html
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
SPECIES_FILE = ROOT / "data" / "species" / "mouse.json"
SHAPES_FILE = ROOT / "data" / "species" / "shapes" / "mouse.json"
ATLAS_FILE = ROOT / "data" / "proteins" / "atlases" / "mouse.json"
OUT_DIR = ROOT / "data" / "proteins" / "mouse"
PATHS = re.compile(r"/(?:home|mnt|Users|tmp)/")
MINE = "the visualizer's mouse agent"
TOOL = "tools/build_mouse_atlas.py"

SPECIES_ID, LABEL, ORGANISM, TAXON, PROTEOME = "mouse", "Mouse", "Mus musculus", 10090, "UP000000589"
UNIPROT = "https://rest.uniprot.org"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
GENE_SETS = "https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/reference_proteomes"
KB = "mouse/uniprot-mouse-reference-proteome"
MGI = "mouse/terms-mgi"
PAPERS_AT = "mouse/europepmc-open-papers"
HUMAN_KB, KB_DOCS, IPR, GO, BIG_PI = "human/uniprot-human-reviewed-proteome", "human/uniprot-docs-and-terms", "human/interpro-entries-tree-and-go", "human/geneontology-go-basic", "human/terms-big-pi"  # read only
PLACES_FILE = f"uniprotkb_{PROTEOME}_places.json.gz"
SIGNATURES_FILE = f"uniprotkb_{PROTEOME}_signatures.tsv.gz"
CANONICAL_FILE = f"{PROTEOME}_{TAXON}.fasta.gz"
ALL = f"(proteome:{PROTEOME})"
GENE_DB = ("MGI", "MGI:")  # the database whose gene identifiers tie a gene's entries together, and how they begin
PLACE_FIELDS = "accession,id,protein_name,gene_primary,xref_mgi,length,protein_existence,cc_subcellular_location,ft_transmem,ft_intramem,ft_signal,ft_transit,ft_topo_dom,ft_lipid,cc_alternative_products,fragment"
UNIPROT_TERMS = r"We have chosen to apply the \[?Creative Commons Attribution 4\.0 International \(CC BY 4\.0\) License\]?(\([^)]*\))? to all copyrightable parts of our databases"

# The open paper the outlines' sizes rest on, with the sentences of its running text and the cells of
# its table that the numbers are read from. Its mice were wild house mice, trapped, not laboratory mice.
PAPERS = {
    "islam2021": {
        "pmc": "PMC8388387", "doi": "10.3390/ani11082162", "licence": "CC BY",
        "holds": [
            r"Body \(Head and body\) length \( A to B \), Right ear length \( D to E \)",
            r"Tail length \( B to C, B marks anus\)",
        ],
        # Table 2: the external measurements, mean ± SD, of the four Mus musculus, in millimetres.
        "table": [
            r"Table 2 The external body linear measurements \(mean ± SD\) of the commensal rodents of Qatar\. Sl\. No\. Parameters \* Mus musculus \( n = 4\) Rattus norvegicus \( n = 120\) Rattus rattus \( n = 24\) 1 Body weight 18\.8 ± 2\.2",
            r"3 Tail length 85\.3 ± 4\.1 191\.4",
            r"4 Body length 78\.5 ± 2\.4 207\.1",
            r"5 Right ear length 13\.3 ± 1\.7 18\.9",
            r"The body weight was measured in grams and the rest of the parameters were measured in millimeters",
        ],
    },
}
BODY_UM, TAIL_UM, EAR_UM = 78500, 85300, 13300  # the paper's means of head and body, tail and ear: see PAPERS

SOURCES = {
    KB: {"what": f"UniProtKB: every entry of the reference proteome {PROTEOME} of Mus musculus, reviewed and unreviewed, with its name, gene, MGI gene, length, level of evidence, stated places with the evidence for each, segments, signals and anchors; the InterPro entries and Gene Ontology terms of each; the proteome's record and counts; UniProt's gene-by-gene set of the proteome (one protein for each gene) with the page that explains it; UniProt's help page on its automatic annotation; and UniProt's statement of its licence, saved beside the data", "licence": "CC BY 4.0"},
    MGI: {"what": "The statement of terms of Mouse Genome Informatics (MGI), read before linking to it. Nothing else of MGI was downloaded: the MGI genes used here are those UniProt gives its entries", "licence": "CC BY 4.0 for MGI's data and annotations, as the page states"},
    PAPERS_AT: {"what": "One open paper from Europe PMC, as its record there (with its licence) and its full text: a morphometric study of house mice and rats trapped in Qatar, for the length of a mouse's head and body, tail and ear", "licence": "CC BY, as its record at Europe PMC states"},
}

# Places that mouse entries state and the human's table has no line for (filled as the build asks).
# Both are this file's reading, and docs/MOUSE.md names them.
PLACES_MORE = {
    # The vocabulary: "an organelle found in 'amitochondrial' unicellular organisms". An animal cell has
    # none, so a statement of it is passed over and the entry's other statements or features decide.
    # Two entries of one gene (Glyctk) state it: the reviewed one by likeness to the human's entry.
    "Mitosome matrix": (None, P.ELSEWHERE),
    # The vocabulary: "a cell within a host organism"; a place of a virus's host, as E. coli's table
    # reads "Host cell membrane". Five unreviewed entries of one gene state it, by a rule.
    "Host cell": (None, P.ELSEWHERE),
}
# The cell the shared machinery places the mouse's proteins in: an animal cell's, as the human's.
CELL = P.Cell(P.ANIMAL_CELL.shelves, {**P.ANIMAL_CELL.places, **PLACES_MORE}, P.ANIMAL_CELL.faces, P.ANIMAL_CELL.away, notes=P.ANIMAL_CELL.notes)

TABLE_COLUMNS = P.PROTEOME_COLUMNS


# ---------------------------------------------------------------------------------------
# Fetch (the download step the species' tools share, with this tool's requests)
# ---------------------------------------------------------------------------------------

def requests():
    out = []

    def add(source, file, url, purpose, **more):
        out.append({"source": source, "file": file, "url": url, "purpose": purpose, **more})

    q = P.q
    stream = f"{UNIPROT}/uniprotkb/stream?query={q(ALL)}&compressed=true"
    add(KB, PLACES_FILE, f"{stream}&format=json&fields={PLACE_FIELDS}", "every entry of the proteome: its name, gene, MGI gene, length and level of evidence, where the entry places it and on what evidence, its segments, signals and anchors", gzip=True)
    add(KB, SIGNATURES_FILE, f"{stream}&format=tsv&fields=accession,xref_interpro,go_id", "the InterPro entries and the Gene Ontology terms UniProt gives each entry", gzip=True)
    count = lambda query: f"{UNIPROT}/uniprotkb/search?query={q(query)}&size=1&fields=accession&format=json"
    for name, query in (("all", ALL), ("reviewed", f"{ALL} AND (reviewed:true)"), ("unreviewed", f"{ALL} AND (reviewed:false)"), ("reviewed_with_place", f"{ALL} AND (reviewed:true) AND (cc_scl_term:*)"), ("unreviewed_with_place", f"{ALL} AND (reviewed:false) AND (cc_scl_term:*)")):
        add(KB, f"count_{name}.json", count(query), f"how many entries of the proteome: {name.replace('_', ' ')} (the count is in the answer's header)")
    add(KB, f"proteome_{PROTEOME}.json", f"{UNIPROT}/proteomes/{PROTEOME}", "the proteome's own record: its counts and its genome assembly")
    add(KB, CANONICAL_FILE, f"{GENE_SETS}/Eukaryota/{PROTEOME}/{CANONICAL_FILE}", "UniProt's gene-by-gene set of the proteome: one protein for each gene. Only the names of its entries are read", gzip=True)
    add(KB, "reference_proteomes_README.txt", f"{GENE_SETS}/README", "UniProt's explanation of the gene-by-gene sets of its reference proteomes", contains="gene")
    add(KB, "help_arba.json", f"{UNIPROT}/help/arba", "UniProt's help page on ARBA, the rule system behind most statements of its unreviewed entries", contains="ARBA")
    add(KB, "terms_uniprot_license.json", f"{UNIPROT}/help/license", "UniProt's statement of its licence, saved beside the data it covers", contains="Creative Commons")
    add(MGI, "mgi_copyright.html", "https://www.informatics.jax.org/mgihome/other/copyright.shtml", "MGI's statement of its terms of use", contains="MGI")
    for key, paper in PAPERS.items():
        add(PAPERS_AT, f"{key}_record.json", f"{EPMC}/search?format=json&resultType=core&query=PMCID:{paper['pmc']}", "the paper's record at Europe PMC, with its licence", contains=paper["pmc"])
        add(PAPERS_AT, f"{key}_fulltext.xml", f"{EPMC}/{paper['pmc']}/fullTextXML", "the paper's full text", contains="<article")
    return out


def fetch(datasets, refresh=False):
    return P.fetch(datasets, requests(), SOURCES, MINE, TOOL, refresh=refresh)


def table_holds(d, folder, key):
    """The cells of a paper's tables that a number is read from: the build stops if one is gone.
    The shared reading of a paper's running text leaves its tables out, so they are read here."""
    raw = d.text(folder, f"{key}_fulltext.xml")
    tables = " ".join(re.findall(r"(?s)<table-wrap\b.*?</table-wrap>", raw))
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]+>", " ", tables))).strip()
    for pattern in PAPERS[key]["table"]:
        if not re.search(pattern, text):
            raise SystemExit(f"{key}: the saved tables no longer hold what a number rests on ({pattern})")


# ---------------------------------------------------------------------------------------
# The outlines: a mouse on its feet, with its ears laid back, as a placeholder
# ---------------------------------------------------------------------------------------
#
# The lengths of the head and body, of the tail and of the ear are the paper's means (PAPERS).
# Every width, the height, the ear's breadth and thickness, the way the ears lie and the tail's
# curve are the picture's choice. The ears are drawn flat and laid back, so that the sheet of
# cells, which is drawn level, can lie on one.

GROUND_UM = 3000  # how high the belly is drawn above the ground: the picture's choice
EAR_AT_UM, EAR_OUT, EAR_RISE = 15500, 0.82, 0.12  # where on the head the ears stand, how far out they point (the sine of their angle to the body), how much they rise


def body_profile(x):
    """The head and body's half width and half height at a distance x from the nose."""
    hump = lambda x, start, end, peak: peak * math.sin(math.pi * (x - start) / (end - start)) ** 0.55 if start < x < end else 0
    wide = max(hump(x, -800, 30000, 6200), hump(x, 17000, BODY_UM + 1600, 14000))
    high = max(hump(x, -800, 30000, 5600), hump(x, 17000, BODY_UM + 1600, 12000))
    return wide, high


def outlines():
    body = []
    for x in range(0, BODY_UM + 1, 1570):
        wide, high = body_profile(x)
        body.append([x, round(GROUND_UM + high), 0, round(wide), round(high)])
    # The tail: from the base of the body, curving to one side and down to the ground, TAIL_UM along its middle line.
    base_y = body[-1][1]
    curve = lambda t, k: (k * 0.95 * t, base_y * (1 - t) ** 1.6 + 600 * t, k * 0.22 * math.sin(1.1 * math.pi * t))
    length = lambda k: sum(math.dist(curve(i / 40, k), curve((i + 1) / 40, k)) for i in range(40))
    k = TAIL_UM
    for _ in range(30):
        k *= TAIL_UM / length(k)
    tail = []
    for i in range(25):
        t = i / 24
        dx, y, dz = curve(t, k)
        half = 1300 - 950 * t
        tail.append([round(BODY_UM + dx), round(y), round(dz), round(half), round(half)])
    # The ears: thin rounded blades, laid back from the top of the head.
    _, head_high = body_profile(EAR_AT_UM)
    top = GROUND_UM + 2 * head_high - 500
    back = math.sqrt(1 - EAR_OUT ** 2)

    def ear(side):
        stations = []
        for i in range(21):
            t = i / 20
            half = 5600 * math.sin(math.pi * (t + 0.08) / 1.08) ** 0.6 if t < 1 else 0
            stations.append([round(EAR_AT_UM + EAR_UM * back * t), round(top + EAR_UM * EAR_RISE * t), round(side * (4200 + EAR_UM * EAR_OUT * t)), round(half), 150 if t < 1 else 0])
        return stations

    left = ear(-1)
    middle = left[10]
    ear_look = {"rings": {"every": 4, "first": 2, "points": 18}, "lines": [0.5, 1.5], "strength": 0.8, "alone": 0.95, "edge": 0.8, "pick": 10, "context": {"edge": 0.35, "fill": 0.05}}
    return {
        "format": "cells.visualizer.outline@1",
        "note": f"A mouse on its feet, with its ears laid back flat, as placeholder outlines. The head and body are drawn {BODY_UM / 1000:g} mm long from the nose to the base of the tail, the tail {TAIL_UM / 1000:g} mm and each ear {EAR_UM / 1000:g} mm: the means one study measured in four house mice trapped in Qatar, wild mice and not laboratory mice. The study is named in the species file. Every width, the height, the ear's breadth and thickness, the way the ears lie and the tail's curve are the picture's choice. The numbers were written out by tools/build_mouse_atlas.py from two rounded humps for the head and the body, a tapering tail, and one thin blade for each ear.",
        "tissue_on": {"at_um": [middle[0], middle[1] + middle[4], middle[2]], "clearance_um": 3, "note": "On the left ear, about half-way along it."},
        "parts": [
            {"name": "head and body", "group": "body", "kind": "loft", "stations": body, "rings": {"every": 3, "first": 1, "points": 28}, "lines": [0.25, 0.5, 0.75, 1.25, 1.5, 1.75], "strength": 0.5, "edge": 1, "fill": 0.07, "pick": 20, "context": {"edge": 0.4, "fill": 0.06}},
            {"name": "tail", "group": "body", "kind": "loft", "stations": tail, "rings": {"every": 4, "first": 2, "points": 12}, "strength": 0.45, "edge": 0.8, "pick": 8},
            {"name": "left ear", "group": "ears", "kind": "loft", "stations": left, **ear_look},
            {"name": "right ear", "group": "ears", "kind": "loft", "stations": ear(1), **ear_look},
        ],
    }


# ---------------------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------------------

# What the project's record decides of the mouse: D155, point 5, of 14 November 2026 (docs/MOUSE.md names the
# record's other mentions). "Nothing of it is built" rests on the design note it points to, which holds no code and
# was accepted for the generic cell's work only, and on no mouse in the engine's code or PROGRESS.md on main.
RECORD = "In the project's record the mouse is named for a planned comparison: in the work on excitable tissue, a generic cell comes first for qualification, then the mouse for the first comparison, then the human (decision D155, 14 November 2026). That comparison concerns heart muscle cells, and nothing of it is built yet."


def every_signature(d):
    """The InterPro entries UniProt gives every entry of the proteome, shown or not."""
    lines = d.text(KB, SIGNATURES_FILE).splitlines()
    if lines[0].split("\t") != ["Entry", "InterPro", "Gene Ontology IDs"]:
        raise SystemExit("UniProt's table of signatures and terms is not the one asked for")
    return {line.split("\t")[0]: set(filter(None, line.split("\t")[1].split(";"))) for line in lines[1:]}


def missed_by_marker(entries, every, signatures):
    """Where the protein shown for a gene lacks a unit's family that another entry of the same gene
    carries: one protein is shown for each gene, the one UniProt's gene-by-gene set names, and that
    entry may be newer and not yet given its signatures. Returns a function that adds a sentence on
    each such gene to a unit's note, and the cases, for the report."""
    of_gene = {}
    for accession, entry in every.items():
        for gene_id in entry["genes"]:
            of_gene.setdefault(gene_id, set()).add(accession)
    shown = set(entries)
    shown_of = {gene_id: sorted(accessions & shown) for gene_id, accessions in of_gene.items()}
    genes_of = {}  # a signature -> the genes that one of whose entries carries it
    for gene_id, accessions in of_gene.items():
        for accession in accessions:
            for signature in signatures.get(accession, ()):
                genes_of.setdefault(signature, set()).add(gene_id)
    cases = []

    def more(unit_id, families, finding, note):
        for key, family in families:
            if key in P.ACCESSORY:
                continue  # an accessory family alone makes no machine: no near miss to name
            wanted = set(family["signatures"])
            for gene_id in sorted(set().union(*(genes_of.get(signature, set()) for signature in wanted)), key=P.natural):
                markers = shown_of[gene_id]
                if not markers or any(signatures.get(marker, set()) & wanted for marker in markers):
                    continue
                carriers = sorted(accession for accession in of_gene[gene_id] if signatures.get(accession, set()) & wanted)
                if not carriers:
                    continue
                marker = markers[0]
                name = entries[marker]["gene"] or marker
                lacks = "carries no InterPro entry yet" if not signatures.get(marker) else "does not carry it"
                cases.append({"unit": unit_id, "family": key, "gene": name, "marker": marker, "carriers": carriers})
                note += f" The mouse's {name} is shown by its entry {marker}, the one UniProt's gene-by-gene set names, which {lacks}; {P.plural(len(carriers), 'other entry', 'other entries')} of the same gene ({', '.join(carriers)}) carr{'ies' if len(carriers) == 1 else 'y'} the signature of {family['of']}. So the gene is a candidate by family too, though a search of the proteins shown does not list it."
        return note
    return more, cases


def build(datasets_folder, snapshot):
    d = P.Datasets(datasets_folder)
    must = lambda source, file, pattern, field=None: P.holds(d, source, file, pattern, field)
    must(KB, "terms_uniprot_license.json", UNIPROT_TERMS, "content")
    must(KB_DOCS, "terms_uniprot_license.json", UNIPROT_TERMS, "content")  # the copy beside the vocabulary of places, read from the human's folder
    must(IPR, "terms_interpro_license.html", r"All of the InterPro, Pfam, PRINTS and SFLD downloadable data provided on the InterPro website is freely available under CC0 1\.0 Universal")
    must(GO, "go_citation_policy.html", r"licensed under the Creative Commons Attribution 4\.0 Unported License")
    # MGI's statement of its terms: nothing of MGI is taken (its genes are read in UniProt's entries), and its terms are read all the same.
    must(MGI, "mgi_copyright.html", r"MGI data and annotations are licensed under a Creative Commons Attribution 4\.0 International License \(CC-BY\)")
    must(KB, "help_arba.json", r"ARBA", "content")
    must(*P.SAVED_TERMS["prosite"], r"distributed under the Creative Commons Attribution-NonCommercial-NoDerivatives \(CC BY-NC-ND 4\.0\) License")
    must(*P.SAVED_TERMS["hamap"], r"distributed under the Creative Commons Attribution \(CC BY 4\.0\) License")
    for tool in ("tmhmm", "signalp", "targetp"):
        must(*P.SAVED_TERMS[tool], rf"ACADEMIC SOFTWARE LICENSE AGREEMENT FOR END-USERS AT PUBLICLY FUNDED ACADEMIC, EDUCATION OR RESEARCH INSTITUTIONS FOR THE USE OF {tool}")
    must(*P.SAVED_TERMS["phobius"], r"Phobius is intended for academic users only")
    must(BIG_PI, "gpi_server.html", r"big-PI Predictor")
    must(KB_DOCS, "help_transmem.json", r"predicted by the application of the predictive tools TMHMM, Memsat, Phobius and the hydrophobic moment plot method", "content")
    must(KB_DOCS, "help_signal.json", r"predicted by the application of the predictive tools Phobius, Predotar, SignalP and TargetP", "content")
    for paper in PAPERS:
        P.paper_text(d, PAPERS_AT, PAPERS, paper)
        table_holds(d, PAPERS_AT, paper)

    vocabulary = P.Vocabulary(d, KB_DOCS, CELL)
    every, read = P.read_proteome(d, KB, PLACES_FILE, vocabulary, GENE_DB)
    total, release, proteome = P.proteome_totals(d, KB, PLACES_FILE, SIGNATURES_FILE, PROTEOME, TAXON, vocabulary, every, read)
    strain = (proteome.get("strain") or "").strip()

    # --- the catalogue: one protein for each gene, as UniProt's gene-by-gene set gives it ---------------
    entries, together, stated = P.one_for_each_gene(d, KB, CANONICAL_FILE, every, total, proteome, "no_mgi_gene")
    filing = P.Filing(d, entries, KB, SIGNATURES_FILE, IPR, GO, catalogue=True)
    placed = {accession: P.place(entry, vocabulary) for accession, entry in entries.items()}
    gene = lambda accession: entries[accession]["gene"] or accession

    # --- the atlas: the families behind Cells' units, asked of this organism ---------------------------
    near, missed = missed_by_marker(entries, every, every_signature(d))
    units, unit_ids, beside = P.find_units(snapshot, entries, filing, P.human_signatures(d, HUMAN_KB), M.FAMILIES, M.UNITS, P.NOTHING, "the mouse", other_said=", as on the planarian's side of the atlas", more=near)

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
    of_strain = f" (strain {strain})" if strain else ""
    header = {
        "format": P.SHELF_FORMAT, "species": SPECIES_ID, "made": made,
        "from": f"UniProtKB release {release}: the reference proteome {PROTEOME} of Mus musculus{of_strain}, {stated['entries']:,} entries ({stated['reviewed']:,} reviewed, {stated['unreviewed']:,} unreviewed) for {stated['genes']:,} genes. One protein is shown for each gene, the one that UniProt's own gene-by-gene set of the proteome gives: {stated['shown']:,} proteins, {stated['shown_reviewed']:,} with a reviewed entry and {stated['shown_unreviewed']:,} with an unreviewed one. The proteome's other {stated['further']:,} entries are further forms of the same genes; each protein counts its gene's entries in the mark 'entries'.",
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
        "entries": {"label": "Entries for its gene", "values": "number", "measured": False, "note": "The proteome's entries for the same gene, by the MGI gene that UniProt gives each entry: this protein's own and the further forms of the gene. The marker stands for the one UniProt's gene-by-gene set names.", "source": "UniProt"},
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
         "holds": f"for each entry of the mouse's reference proteome: its name, gene, MGI gene, length and level of evidence, the places it states with the evidence for each, its membrane-spanning segments, signal peptide and anchors, and the InterPro entries and Gene Ontology terms UniProt gives it; the gene-by-gene set of the proteome; and UniProt's vocabulary of places. The programs and rule systems of other owners behind its statements are sources below. Placements that rest on UniProt's own automatic systems alone: {own_said or 'none'}"},
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
    clauses = [f"{findings['found']} have proteins of the same family in the mouse"]
    if findings["different family"]:
        clauses.append(f"{findings['different family']} are built from another family")
    if findings["none found"]:
        clauses.append(f"{findings['none found']} {'was' if findings['none found'] == 1 else 'were'} not found")
    machines = f"of the {len(units)} units of the law inventory, {P.listed(clauses)}; the other {findings['nothing to look for']} name no natural protein to look for"
    shape = outlines()
    paper = PAPERS["islam2021"]
    species = {
        "format": "cells.visualizer.species@1", "id": SPECIES_ID, "label": LABEL, "organism": ORGANISM, "taxon": TAXON,
        "plain": f"The laboratory mouse: {stated['genes']:,} genes in UniProt's reference proteome, with one protein shown for each. Its cell is drawn as the planarian's is: one cell of a sheet that stands for skin-like tissue.",
        "group": "Animals", "order": 15, "default": False, "made": made,  # after the human, before the planarian
        "modelled": {"state": "generic", "text": f"Cells models a generic cell and a sheet of such cells, not this animal. The sheet stands for skin-like tissue and is drawn on the ear for the scales only. The ear and the mouse are placeholder outlines: nothing at those scales is simulated. {RECORD}"},
        "levels": [
            {"id": "molecules"},
            {"id": "cell", "shape": {"kind": "prism", "sides": 6, "radius_um": 10.6, "height_um": 13, "corner_um": 2.4, "edge_um": 1.3},
             "note": "The cell drawn is one cell of the sheet, which stands for skin-like tissue; it is not a model of a mouse's skin cell. Its shape and its sizes are the picture's choice: six flat sides where it meets its neighbours, an outer face and a base, about 20 µm across and as tall as the sheet's cells. The plate under the layer is scenery: Cells models nothing beneath the sheet.",
             "notes": [{"text": "One cell of the skin-like layer"}, {"text": "Its flat-sided shape is the picture's choice", "roomy": True}], "fade_out_um": [120, 190]},
            {"id": "tissue", "shape": {"kind": "cell sheet", "rings": 6, "beyond": [[8, 0.34], [10, 0.2], [11, 0.1]]},
             "note": "The sheet stands for skin-like tissue: a single layer of cells. It is drawn on the ear of the placeholder mouse for the scales only; the simulated sheet is not the mouse's skin.",
             "notes": [{"text": "The sheet stands for skin-like tissue: a single layer of cells", "short": "Stands for skin-like tissue"}], "fade_in_um": [100, 190]},
            {"id": "organ", "label": "Ear", "shape": {"kind": "outline", "ref": SPECIES_ID, "parts": ["left ear"], "context": ["head and body", "right ear"]},
             "note": f"The outline drawn is a mouse's ear, as a placeholder: a thin rounded blade, laid back flat from the head so that the sheet of cells, drawn level, can lie on it. The ear is the picture's choice of organ, so that the sheet that stands for skin-like tissue lies on a part of the animal a visitor knows; no ear is modelled, and the ear's own cells are not modelled. The sheet is drawn on the ear so that the scales follow one another; it is not the ear's tissue. The ear is drawn {EAR_UM / 1000:g} mm long, the mean that one study measured in four house mice trapped in Qatar, wild mice and not laboratory mice; its breadth, its thickness, its shape and the way it lies are the picture's choice.",
             "sources": ["islam2021"],
             "sheet_mark": {"band": 0.15, "note": "The sheet, to scale: drawn on the ear for the scales only", "note_at_um": [0, 0, 1800]},
             "notes": [{"text": "A mouse's ear: a placeholder outline"}, {"text": "The ear's own cells are not modelled", "lift": -22, "roomy": True}]},
            {"id": "organism", "label": "Whole mouse", "shape": {"kind": "outline", "ref": SPECIES_ID},
             "note": f"The outline drawn is a mouse on its feet, as a placeholder: {BODY_UM / 1000:g} mm from the nose to the base of the tail, with a tail of {TAIL_UM / 1000:g} mm, the means that one study measured in four house mice trapped in Qatar. Those were wild house mice, not laboratory mice, so the sizes are indicative. The widths, the height and the proportions are the picture's choice. The sheet of cells is drawn on the left ear for the scales only.",
             "sources": ["islam2021"],
             # Framed a little wider than its parts and toward the head, so that the panel on the left covers none of it.
             "view": {"frame_um": [270000, 160000], "toward_um": [-8000, 0, 0]},
             "sheet_mark": {"band": 0.22, "note": "Here lies the sheet: too small to see, so its ring is not to scale", "note_at_um": [0, 0, -9000], "roomy": True},
             "notes": [{"text": "A mouse: a placeholder outline"}]},
        ],
        "cell": {
            "facts": [
                {"label": "Proteins", "value": f"{stated['genes']:,} genes in UniProt's reference proteome, with {stated['entries']:,} entries: {stated['reviewed']:,} reviewed by a curator and {stated['unreviewed']:,} annotated automatically. One protein is shown for each gene", "sources": ["uniprot"]},
                {"label": "Cells' units", "value": machines, "sources": ["uniprot"]},
                {"label": "The outlines' sizes", "value": f"head and body {BODY_UM / 1000:g} mm, tail {TAIL_UM / 1000:g} mm, ear {EAR_UM / 1000:g} mm: the means of four house mice trapped in Qatar, wild and not laboratory mice", "sources": ["islam2021"]},
            ],
            "parts": {"membranes": 1, "wall": False, "nucleus": True, "organelles": ["er", "golgi", "mitochondria"]},
        },
        "sources": {
            "uniprot": {"text": f"UniProt Consortium, UniProt release {release}: the reference proteome {PROTEOME} (Mus musculus{of_strain}), its entries and its gene-by-gene set.", "url": f"https://www.uniprot.org/proteomes/{PROTEOME}", "licence": "CC BY 4.0", "class": "permissive", "accessed": d.day(KB, PLACES_FILE)},
            "islam2021": {"text": f"{P.paper_cite(d, PAPERS_AT, PAPERS, 'islam2021')} Its Table 2 gives, for four house mice (Mus musculus) trapped in Qatar, a head and body length of 78.5 ± 2.4 mm, a tail of 85.3 ± 4.1 mm and a right ear of 13.3 ± 1.7 mm.", "doi": paper["doi"], "licence": "CC BY", "class": "permissive", "accessed": d.day(PAPERS_AT, "islam2021_fulltext.xml")},
        },
    }
    atlas = {
        "format": P.ATLAS_FORMAT,
        "species": {"id": SPECIES_ID, "label": LABEL, "organism": ORGANISM, "taxon": TAXON, "plain": f"The laboratory mouse, with {stated['genes']:,} genes in UniProt's reference proteome. This is what the family signatures of Cells' units find among the one protein shown for each gene."},
        "made": made,
        "method": [
            f"The mouse's proteins are the {len(entries):,} of UniProt's gene-by-gene set of the reference proteome {PROTEOME} (release {release}): one for each gene, {stated['shown_reviewed']:,} with a reviewed entry and {stated['shown_unreviewed']:,} with an unreviewed one.",
            "Licences were read before anything was copied; each is stated in sources.",
            "Each unit's family was taken from its own human candidates, by the same InterPro signatures that the other species' atlases ask. The build checks that the candidates carry them.",
            "Each signature was looked for among the InterPro entries UniProt gives each protein. A unit counts as found only where a protein carries the signature of a family that makes the machine itself; an accessory family alone does not make it found.",
            "A mouse protein is listed because its own entry carries the family's signature, never because its gene's symbol looks like that of a human candidate.",
            P.TWO_FACTS,
            "Several units of one family (the Kv1 channels) list the same proteins, and nothing here says which protein does which unit's work.",
            "No similarity search was run, no source of orthology was read, and nothing is called an ortholog.",
        ],
        "sources": [
            {"name": "UniProt", "url": "https://www.uniprot.org/", "release": release, "accessed": d.day(KB, PLACES_FILE), "licence": "CC BY 4.0", "class": "permissive", "cite": P.CITE_UNIPROT, "holds": "the entries of the mouse's proteins, reviewed and unreviewed, with the InterPro entries UniProt gives each; the signatures of the units' human candidates"},
            {"name": "InterPro", "url": "https://www.ebi.ac.uk/interpro/", "release": filing.release, "accessed": d.day(IPR, "entry.list"), "licence": "CC0 1.0", "class": "permissive", "cite": P.CITE_INTERPRO, "holds": "the identifiers and names of the family signatures"},
        ],
        "not_copied": "No sequence is copied. Mouse Genome Informatics (MGI) is linked to; nothing was downloaded from it but its statement of terms, and the MGI genes used here are those UniProt gives its entries.",
        "units": units,
        "extra": [],
    }
    report = {
        "release": release, "interpro": filing.release, "ontology": filing.ontology, "made": made, "strain": strain, "stated": stated, "read": dict(read),
        "shelf_counts": shelf_counts, "counts": counts, "bases": {f"{side} / {basis}": n for (side, basis), n in sorted(bases.items())}, "rules": {rule: rules[rule] for rule, _, _ in P.RULES_USED},
        "evidence": dict(evidence), "how_sure": how_sure, "resting": resting, "rule_systems": {owner: len(found) for owner, found in rule_ids.items()},
        "families": len(family_total), "in_families": len(filing.family), "several": filing.several, "no_family": len(filing.part),
        "family_sizes": {"one": sum(1 for size in family_total.values() if size == 1), "two to four": sum(1 for size in family_total.values() if 2 <= size <= 4), "five or more": sum(1 for size in family_total.values() if size >= 5)},
        "largest_families": [[filing.names[family]["name"], n] for family, n in sorted(family_total.items(), key=lambda pair: (-pair[1], pair[0]))[:8]],
        "lines": len(lines), "distinct": distinct, "lone": lone["count"], "lone_parts": len(alone), "part_lines": len(rest), "groups": groups, "member_files": files, "places_used": len(used),
        "findings": dict(findings), "found_units": {unit: [product["gene"] for product in found["products"]] for unit, found in units.items() if found["products"]}, "beside": {gene(a): what for a, what in beside.items()},
        "products": sum(len(found["products"]) for found in units.values()), "products_reviewed": sum(1 for found in units.values() for product in found["products"] if product["entry"] == P.ENTRY_REVIEWED),
        "with_units": len(unit_ids), "entries_per_gene": dict(sorted(Counter(min(n, 6) for n in together.values()).items())),
        "tissue_on": shape["tissue_on"]["at_um"], "missed_by_marker": missed,
    }
    files_out = {"shelves": body, "table": table, "species": json.dumps(species, indent=1, ensure_ascii=False) + "\n", "shapes": json.dumps(shape, ensure_ascii=False, separators=(",", ":")) + "\n", "atlas": json.dumps(atlas, indent=1, ensure_ascii=False) + "\n"}
    files_out["readme"] = build_readme(report, header, closing)
    report["sizes"] = P.within_limits(files_out, PATHS)
    return files_out, report


def build_readme(report, header, closing):
    r = report
    names = {shelf["id"]: shelf["label"] for shelf in header["shelves"]}
    lines = [
        "# The mouse: its own proteins, on shelves",
        "",
        "Generated by `tools/build_mouse_atlas.py`; do not edit by hand. The note is `docs/MOUSE.md`.",
        "",
        f"- `shelves.json`: {header['from']}",
        f"- `proteins.tsv`: one line for each of the {r['stated']['shown']:,} proteins shown, in the order of the shelves' lines. No sequences.",
        "- The members' files are not kept here: `python3 tools/build_mouse_atlas.py members --out DIR` cuts them from these two files.",
        "",
        "Nothing of the mouse is in the engine. This is reference data for the viewer.",
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
        f"- {r['with_units']:,} proteins carry the family signature of one of Cells' units and name it.",
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
        f"UniProt {r['release']}, InterPro {r['interpro']}, Gene Ontology {r['ontology']}; made {r['made']}; strain {r['strain'] or 'not given'}",
        f"proteome: {r['stated']}; read: {r['read']}",
        "by shelf: " + "; ".join(f"{shelf} {sum(sides.values()):,} {sides}" for shelf, sides in r["shelf_counts"].items()),
        f"sides: {r['counts']}; side and basis: {r['bases']}",
        f"rules: {r['rules']}",
        f"how sure: {r['how_sure']}",
        f"evidence behind the deciding statement: {r['evidence']}",
        f"families: {r['families']:,} holding {r['in_families']:,} (sizes {r['family_sizes']}); no family {r['no_family']:,}; lines {r['lines']:,} of {r['distinct']:,}; lone {r['lone']:,} in {r['lone_parts']} parts; part lines {r['part_lines']}; largest {r['largest_families'][:5]}",
        f"rests on, by owner: {r['resting']}; rules named: {r['rule_systems']}",
        f"atlas: {r['findings']}; products {r['products']} ({r['products_reviewed']} reviewed); accessory only {r['beside']}; proteins with units {r['with_units']}; missed by the marker {[(case['unit'], case['gene']) for case in r['missed_by_marker']]}",
        "found: " + "; ".join(f"{unit} {len(genes)} ({', '.join(str(g) for g in genes[:4])})" for unit, genes in r["found_units"].items()),
        f"entries per gene (6 = six or more): {r['entries_per_gene']}; member files: {r['member_files']}; places used: {r['places_used']}; sizes: {r['sizes']}; sheet on {r['tissue_on']}",
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
