#!/usr/bin/env python3
"""Build the viewer's data on the African clawed frog, Xenopus laevis: the species with its levels and
placeholder outlines of an adult, its side of the protein atlas, and its own proteins on shelves.

Six files are written, each from saved answers of public databases and three open papers:

    data/species/xenopus.json           the species file (schema/SPECIES.md)
    data/species/shapes/xenopus.json    placeholder outlines of an adult frog and its hind foot (schema/SPECIES_SHAPES.md)
    data/proteins/atlases/xenopus.json  its side of the protein atlas (schema/SPECIES_ATLAS.md)
    data/proteins/xenopus/              shelves.json, proteins.tsv and README.md (schema/SPECIES_PROTEINS.md,
                                        "A whole reference proteome")

It was decided on 19 November 2026 that the frog is added as a whole species, by these rules for its
proteins (docs/XENOPUS.md gives them with their counts):

    1. Both copies of a gene, on the L and on the S chromosomes, are shown, each as its own protein:
       UniProt's own gene-by-gene set of the proteome lists them as two genes, and nothing read here
       says they are one. No pair is merged.
    2. A reviewed entry wins over unreviewed twins of its gene: where one gene has a reviewed entry and
       unreviewed entries among the proteins of that set, only the reviewed entry is shown. A gene is
       the entries tied together by the NCBI gene identifiers that UniProt's cross-references give
       them. The build stops if the counts differ from those measured when the rule was decided.
    3. Every protein is marked with its copy, from UniProt's proteome component of its entry, never
       from its gene's symbol.
    4. A twin that is not shown stays findable: the shown entry names it, the page's search finds the
       shown protein by it, and its panel lists it as an unreviewed entry of the same gene, not shown.
    5. The genes that still stand twice or more, with unreviewed entries only, are counted and said.
    6. The gene symbols are UniProt's (CC BY 4.0). UniProt's entries name Xenbase's nomenclature as
       their source; Xenbase is named as a dependence read through UniProt, and nothing else of it is
       used: no Xenbase identifier, link to a gene or page of it is written or read here.
    7. The NCBI gene identifiers tie the entries together while building only; none is written.
    8. Nothing of another species changes.

Its cell is the mouse's and the planarian's: one cell of a sheet that stands for skin-like tissue. The
adult is drawn, and its life stages stand on a strip (schema/SPECIES_STAGES.md): the fertilised egg is drawn,
four stages between are named and not drawn. The stages are kept by hand in data/species/stages/xenopus.json;
this tool checks each of their numbers against the saved running text of the open paper it cites, and writes
the block into the species file with those papers among its sources.

    python3 tools/build_xenopus_atlas.py fetch --datasets DATA     the only step that uses the network
    python3 tools/build_xenopus_atlas.py build --datasets DATA     the same bytes every time
    python3 tools/build_xenopus_atlas.py members --out DIR         the members' files, for the page

DATA holds every species' downloads, one folder per source with a MANIFEST.json. The shelves'
machinery is tools/lib/proteome_shelves.py, which every species' tool shares, here with the human's
own table of an animal cell's shelves; the families asked of every species are those of
tools/build_mpneumoniae_atlas.py, read and never changed.

This is the viewer's reference data. Nothing of the frog is in the engine's picture here. Standard
library only.
"""

from __future__ import annotations

import argparse
import gzip
import html
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import build_mpneumoniae_atlas as M  # noqa: E402  the families asked of every species, read and never changed
from lib import proteome_shelves as P  # noqa: E402  the shelves' machinery

SNAPSHOT = ROOT / "data" / "proteins" / "inventory.snapshot.json"
SPECIES_FILE = ROOT / "data" / "species" / "xenopus.json"
STAGES_FILE = ROOT / "data" / "species" / "stages" / "xenopus.json"  # the frog's life stages, kept by hand
# The files of the project's record that the egg's own word, "planned", rests on, in the order the block cites them.
EGG_RECORD = ["docs/DECISIONS.md", "docs/DECISIONS.md", "docs/CELL_DIVISION_PLAN.md", "docs/CELL_DIVISION_DESIGN.md", "PROGRESS.md"]
SHAPES_FILE = ROOT / "data" / "species" / "shapes" / "xenopus.json"
ATLAS_FILE = ROOT / "data" / "proteins" / "atlases" / "xenopus.json"
OUT_DIR = ROOT / "data" / "proteins" / "xenopus"
PATHS = re.compile(r"/(?:home|mnt|Users|tmp)/")
MINE = "tools/build_xenopus_atlas.py of the visualizer"
TOOL = "tools/build_xenopus_atlas.py"

SPECIES_ID, LABEL, ORGANISM, TAXON, PROTEOME = "xenopus", "Frog", "Xenopus laevis", 8355, "UP000186698"
UNIPROT = "https://rest.uniprot.org"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
GENE_SETS = "https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/reference_proteomes"
KB = "xenopus/uniprot-xenopus-reference-proteome"
PAPERS_AT = "xenopus/europepmc-stage-sources-e1"  # read only: the gathering round's folder
HUMAN_KB, KB_DOCS, IPR, GO, BIG_PI = "human/uniprot-human-reviewed-proteome", "human/uniprot-docs-and-terms", "human/interpro-entries-tree-and-go", "human/geneontology-go-basic", "human/terms-big-pi"  # read only
PLACES_FILE = f"uniprotkb_{PROTEOME}_places.json.gz"
SIGNATURES_FILE = f"uniprotkb_{PROTEOME}_signatures.tsv.gz"
COMPONENT_FILE = f"uniprotkb_{PROTEOME}_proteome_component.tsv.gz"
CANONICAL_FILE = f"{PROTEOME}_{TAXON}.fasta.gz"
ALL = f"(proteome:{PROTEOME})"
# The database whose gene identifiers tie a gene's entries together, and how they begin: NCBI's gene identifiers, as
# UniProt's cross-references give them. They are used while building only, and no file is written with one.
GENE_DB = ("GeneID", "")
PLACE_FIELDS = "accession,id,protein_name,gene_primary,xref_geneid,length,protein_existence,cc_subcellular_location,ft_transmem,ft_intramem,ft_signal,ft_transit,ft_topo_dom,ft_lipid,cc_alternative_products,fragment"
UNIPROT_TERMS = r"We have chosen to apply the \[?Creative Commons Attribution 4\.0 International \(CC BY 4\.0\) License\]?(\([^)]*\))? to all copyrightable parts of our databases"

# The frog's own limits on its files' sizes, and how many members a file of members holds; every other species keeps
# the shared ones (tools/lib/proteome_shelves.py). Why: the frog's catalogue is the largest of all, with both copies of
# a gene shown, so its shelves are over the shared 1,000,000 bytes and its table over 3,000,000; and the page holds
# 459 of at most 511 published files, which the frog's members would grow by 18 at 2,000 a file and by 6 at 6,000
# (docs/XENOPUS.md gives the sizes). The shelves' bound is the one the proteins' overlay states for the frog, which
# the scene's reader holds the file to as well (data/proteins/overlay.json, shelves.limits).
OVERLAY_LIMITS = json.loads((ROOT / "data" / "proteins" / "overlay.json").read_text(encoding="utf-8"))["shelves"]["limits"][SPECIES_ID]
LIMITS = (OVERLAY_LIMITS["shelves_bytes"], 5_000_000, 6_500_000)  # shelves.json, any one file, the folder
MEMBERS_PER_FILE = 6000

# Placeholder names: some of UniProt's frog gene names, and protein names made from them, are placeholders of Xenbase's
# nomenclature that embed the gene's number there ("XB5993457.L"). A word that is XB followed by four or more digits,
# with or without .L or .S, is such a placeholder ("Hox-B9/HXC9" is not). With the switch False, a field that holds one
# is not written at all, never rewritten: no gene name for such a protein, no protein name where its name holds one, and
# a twin with such a gene name is named by its accession alone; the build counts each. True writes the names as UniProt
# gives them. It was decided on 19 November 2026 that they are not written: the user left the choice to the viewer's
# coordinator, who settled it with a second reviewer. Such a name is Xenbase's own number for the gene in a name's place,
# the tree writes no Xenbase identifier, and leaving it out can be undone where writing it into a public repository
# cannot. Flipping the switch and rebuilding changes the frog's table, shelves, README and members.
WRITE_PLACEHOLDER_NAMES = False
PLACEHOLDER = re.compile(r"\bXB\d{4,}(?:\.[LS])?\b")

# What was measured when the rules were decided (19 November 2026, UniProt release 2026_04): the build stops with
# what it found if they differ.
EXPECTED = {"set": 36429, "shown": 35004, "shown_reviewed": 3523, "dropped": 1425, "dropped_genes": 1410}

# The open paper the outlines' sizes rest on: the sentences of its running text that say what each measure is, and
# the cells of its Table 1 that the numbers are read from. Its frogs were adults kept as laboratory animals.
PAPER = {
    "key": "boswald2022", "pmc": "PMC9653714", "doi": "10.3390/ani12212986",
    "file": "PMC9653714_fulltext.xml", "record": "search_adult.json",
    "licence": [r"Creative Commons Attribution \(CC BY\) license", r"https://creativecommons\.org/licenses/by/4\.0/"],
    "holds": [
        r"Snout–vent length \(L\): length from the tip of the snout to the posterior margin of the cloaca \(cm\)",
        r"Cranial width \(CrW\): width from the left to the right side, measured directly behind the forelimbs \(cm\)",
        r"Caudal width \(CdW\): width from the left to the right side, measured directly in front of the hindlimbs \(cm\)",
        r"Thigh width \(TW\): the thigh width was measured at the broadest site \(cm\)",
    ],
    # Table 1: females (n, mean ± SD, range ...) and then males, in centimetres.
    "table": [
        r"Table 1 Table 1 Body weight and measurements of adult Xenopus laevis grouped according to sex\. Females Males",
        r"L \(cm\) 198 12\.1 ± 1\.0 8\.44–13\.97 12\.31 11\.74 12\.71 40 7\.7 ± 0\.3 7\.13–8\.26",
        r"CrW \(cm\) 198 5\.1 ± 0\.5 ",
        r"CdW \(cm\) 198 6\.2 ± 0\.7 ",
        r"TW \(cm\) 190 3\.4 ± 0\.3 ",
    ],
}
# The open papers the life stages rest on (data/species/stages/xenopus.json): each one's licence and DOI in its full
# text, and the words of its running text that the stages' names and numbers rest on, a few words round each, kept to
# check the saved text and never written out. The build stops where one is gone. Their records are Europe PMC's.
STAGE_PAPERS = {
    "zahn2022": {
        "pmc": "PMC9445888", "doi": "10.1242/dev.200356", "file": "zahn2022_fulltext.xml", "record": "search_stage_hpf.json",
        "licence": [r"Creative Commons Attribution License", r"https://creativecommons\.org/licenses/by/4\.0"],
        "holds": [
            r"Nieuwkoop and Faber based their staging system",  # the NF stages (Introduction, paragraph 3)
            r"the Xenopus egg, NF stage 1",  # "NF stages 1-6: zygote and cleavage", paragraph 1
            r"At room temperature \(23°C\), the first cell division occurs approximately 90 min post-fertilization",
            r"The fully cleaved two-cell embryo is NF stage 2",
            r"The second cleavage ∼20-30 min later .{0,80}four-cell embryo, NF stage 3",
            r"NF 35-36 marks a major behavioral transition as tadpoles naturally break free from their vitelline membrane to become free-swimming",  # "NF stages 29-38", paragraph 2
            r"NF stage 66 \(froglet with a fully resorbed tail",  # "NF stages 47-61", paragraph 1
        ],
        "says": "Its running text names the stages of the standard table of normal development, the NF stages, and gives the first cell division at about 90 min after fertilisation, at 23 °C, and the second 20 to 30 min after it.",
    },
    "sato2025": {
        "pmc": "PMC12838665", "doi": "10.3390/biom16010022", "file": "PMC12838665_fulltext.xml", "record": "search_egg_diam.json",
        "licence": [r"Creative Commons Attribution \(CC BY\) license", r"https://creativecommons\.org/licenses/by/4\.0/"],
        "holds": [r"externally fertilized eggs—approximately 1\.2 mm in diameter"],  # section 2.1, paragraph 1
        "says": "A review: its section 2.1 gives the frog's fertilised eggs a diameter of about 1.2 mm.",
    },
}
# The numbers of the stages that rest on those words: the egg's diameter, in micrometres, and the first division's time
# and temperature. The build stops where the block kept by hand gives others.
EGG_UM, FIRST_DIVISION = 1200, {"value": 90, "unit": "min", "about": True, "temperature_c": 23}
STAGE_NUMBERS_SAID = ("20 to 30 minutes", "23 °C")  # the four-cell stage's note gives its time from the first division

# The paper's means for the 198 females (Table 1), in micrometres: snout to vent, the width directly behind the
# forelimbs and directly in front of the hindlimbs, and a thigh's width (190 of them). The male's length for the fact.
BODY_UM, CRANIAL_UM, CAUDAL_UM, THIGH_UM, MALE_UM = 121000, 51000, 62000, 34000, 77000

SOURCES = {
    KB: {"what": f"UniProtKB: every entry of the reference proteome {PROTEOME} of Xenopus laevis, reviewed and unreviewed, with its name, gene, NCBI gene, length, level of evidence, stated places with the evidence for each, segments, signals and anchors; the proteome component of each; the InterPro entries and Gene Ontology terms of each; the proteome's record and counts; UniProt's gene-by-gene set of the proteome (one protein for each gene) with the page that explains it; UniProt's help page on its automatic annotation; and UniProt's statement of its licence, saved beside the data", "licence": "CC BY 4.0"},
    PAPERS_AT: {"what": "Open papers from Europe PMC, as their records there and their full texts", "licence": "each paper's own, as its full text states it"},
}

# Places that frog entries state and the human's table has no line for (filled as the build asks). Both are this
# file's reading, and docs/XENOPUS.md names them.
PLACES_MORE = {
    # The vocabulary: "The nematocyst is an organelle found in nematoblast (cnidoblast) cells ... principally found in
    # anemones and jellyfishes." A frog cell has none, so the statement is passed over and the entry's other
    # statements or features decide. Five unreviewed entries state it, each by a rule (ARBA).
    "Nematocyst": (None, P.ELSEWHERE),
    # The vocabulary: "a cell within a host organism"; a place of a virus's host, as the mouse's table reads it. Two
    # unreviewed entries state it, by a rule (ARBA).
    "Host cell": (None, P.ELSEWHERE),
}
# The cell the shared machinery places the frog's proteins in: an animal cell's, as the human's.
CELL = P.Cell(P.ANIMAL_CELL.shelves, {**P.ANIMAL_CELL.places, **PLACES_MORE}, P.ANIMAL_CELL.faces, P.ANIMAL_CELL.away, notes=P.ANIMAL_CELL.notes)

# The table adds the copy of its gene, the chromosomes its entry is placed on, and the unreviewed entries of the same
# gene that are not shown, beside a whole proteome's columns.
TABLE_COLUMNS = [*P.PROTEOME_COLUMNS, "copy", "chromosome", "same_gene"]
COPIES = ["L", "S", "L and S", "neither stated"]

# Xenbase, behind the gene names UniProt gives the frog's entries. Its terms as the gathering round saved them on
# 19 November 2026 (docs/XENOPUS.md); this tool reads no page of it. Only its site's address is given, as the other
# sources read through UniProt give theirs.
XENBASE = {
    "name": "Xenbase", "url": "https://www.xenbase.org/",
    "licence": "For research and education only: Xenbase's Terms & Conditions of Use, as saved on 19 November 2026, say \"Data are to be used only for purposes of research and education. Commercial use is prohibited without written permission from Xenbase.\"",
    "class": "non-commercial", "accessed": "2026-11-19",
}


# ---------------------------------------------------------------------------------------
# Fetch (the download step the species' tools share, with this tool's requests)
# ---------------------------------------------------------------------------------------

def requests():
    out = []

    def add(source, file, url, purpose, **more):
        out.append({"source": source, "file": file, "url": url, "purpose": purpose, **more})

    q = P.q
    stream = f"{UNIPROT}/uniprotkb/stream?query={q(ALL)}&compressed=true"
    add(KB, PLACES_FILE, f"{stream}&format=json&fields={PLACE_FIELDS}", "every entry of the proteome: its name, gene, NCBI gene, length and level of evidence, where the entry places it and on what evidence, its segments, signals and anchors", gzip=True)
    add(KB, SIGNATURES_FILE, f"{stream}&format=tsv&fields=accession,xref_interpro,go_id", "the InterPro entries and the Gene Ontology terms UniProt gives each entry", gzip=True)
    add(KB, COMPONENT_FILE, f"{stream}&format=tsv&fields=accession,xref_proteomes", "the proteome component (the chromosome) UniProt gives each entry", gzip=True)
    count = lambda query: f"{UNIPROT}/uniprotkb/search?query={q(query)}&size=1&fields=accession&format=json"
    for name, query in (("all", ALL), ("reviewed", f"{ALL} AND (reviewed:true)"), ("unreviewed", f"{ALL} AND (reviewed:false)"), ("reviewed_with_place", f"{ALL} AND (reviewed:true) AND (cc_scl_term:*)"), ("unreviewed_with_place", f"{ALL} AND (reviewed:false) AND (cc_scl_term:*)")):
        add(KB, f"count_{name}.json", count(query), f"how many entries of the proteome: {name.replace('_', ' ')} (the count is in the answer's header)")
    add(KB, f"proteome_{PROTEOME}.json", f"{UNIPROT}/proteomes/{PROTEOME}", "the proteome's own record: its counts and its genome assembly")
    add(KB, CANONICAL_FILE, f"{GENE_SETS}/Eukaryota/{PROTEOME}/{CANONICAL_FILE}", "UniProt's gene-by-gene set of the proteome: one protein for each gene. Only the names of its entries are read", gzip=True)
    add(KB, "reference_proteomes_README.txt", f"{GENE_SETS}/README", "UniProt's explanation of the gene-by-gene sets of its reference proteomes", contains="gene")
    add(KB, "help_arba.json", f"{UNIPROT}/help/arba", "UniProt's help page on ARBA, the rule system behind most statements of its unreviewed entries", contains="ARBA")
    add(KB, "terms_uniprot_license.json", f"{UNIPROT}/help/license", "UniProt's statement of its licence, saved beside the data it covers", contains="Creative Commons")
    add(PAPERS_AT, PAPER["file"], f"{EPMC}/{PAPER['pmc']}/fullTextXML", "the paper's full text, with its licence", contains="<article")
    return out


def fetch(datasets, refresh=False):
    return P.fetch(datasets, requests(), SOURCES, MINE, TOOL, refresh=refresh)


# ---------------------------------------------------------------------------------------
# The paper: its licence, its record, the sentences and the cells its numbers rest on
# ---------------------------------------------------------------------------------------

def flat(markup):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]+>", " ", markup))).strip()


def paper(d, spec=PAPER):
    """A paper's citation, checked: its full text states its licence (CC BY 4.0) and its DOI, its running text the
    sentences that say what each measure is, and its tables (where it gives numbers from them) the cells the numbers
    are read from. The build stops where one is gone. The citation is the one Europe PMC's record gives (the gathering
    round's search answer). `spec` is PAPER, or one of STAGE_PAPERS with its key."""
    key = spec.get("key")
    raw = d.text(PAPERS_AT, spec["file"])
    licence = " ".join(flat(block) for block in re.findall(r"(?s)<license\b.*?</license>", raw))
    if not all(re.search(pattern, licence) for pattern in spec["licence"]):
        raise SystemExit(f"{key}: its full text no longer states the licence CC BY 4.0; read it again")
    if f'<article-id pub-id-type="doi">{spec["doi"]}</article-id>' not in raw:
        raise SystemExit(f"{key}: its full text no longer gives the DOI {spec['doi']}")
    text = flat(re.sub(r"(?s)<(table-wrap|ref-list)\b.*?</\1>", " ", raw))
    for pattern in spec["holds"]:
        if not re.search(pattern, text):
            raise SystemExit(f"{key}: the saved text no longer holds what a number rests on ({pattern})")
    tables = flat(" ".join(re.findall(r"(?s)<table-wrap\b.*?</table-wrap>", raw)))
    for pattern in spec.get("table", []):
        if not re.search(pattern, tables):
            raise SystemExit(f"{key}: the saved tables no longer hold what a number rests on ({pattern})")
    record = next((item for item in json.loads(d.text(PAPERS_AT, spec["record"]))["resultList"]["result"] if item.get("pmcid") == spec["pmc"]), None)
    if record is None or (record.get("doi") or "").lower() != spec["doi"]:
        raise SystemExit(f"{key}: Europe PMC's record of it is not in the saved answer")
    # A record's words may carry markup, escaped or not (a title's italics): it is taken out after unescaping.
    clean = lambda words: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(words or ""))).strip().rstrip(".")
    where = f"{record['journalVolume']}({record['issue']}):{record['pageInfo']}"
    return f"{clean(record['authorString'])} ({record['pubYear']}) {clean(record['title'])}. {clean(record['journalTitle'])} {where}."


def stages(d):
    """The frog's life stages, as kept by hand (data/species/stages/xenopus.json), checked: every source they cite is one
    of the open papers above, whose saved text holds what each name and number rests on; the egg's diameter and the first
    division's time are the numbers those words give; and no stage gives a word of its own for what Cells models of it.
    Returns the block, as the species file carries it, and the papers' entries among the species' sources."""
    kept = json.loads(STAGES_FILE.read_text(encoding="utf-8"))
    if kept.get("format") != "cells.visualizer.species_stages@1" or kept.get("species") != SPECIES_ID:
        raise SystemExit(f"{STAGES_FILE.name}: not the frog's stages block")
    block = kept["stages"]
    sources = {}
    for key, spec in STAGE_PAPERS.items():
        cite = paper(d, {**spec, "key": key})
        sources[key] = {"text": f"{cite} {spec['says']}", "doi": spec["doi"], "licence": "CC BY 4.0", "class": "permissive", "accessed": d.day(PAPERS_AT, spec["file"])}
    cited = {key for key in block.get("system", {}).get("sources", [])}
    for stage in block["list"]:
        cited.update(stage.get("sources", []))
        cited.update(stage.get("time", {}).get("sources", []))
        for level in stage.get("levels", []):
            cited.update(level.get("sources", []))
        for fact in stage.get("cell", {}).get("facts", []):
            cited.update(fact.get("sources", []))
        if "modelled" in stage:
            # Decided on 19 November 2026, the engine's lead agreeing that the record supports it: the fertilised egg alone
            # gives a word of its own for what Cells models of it, and only "planned", on these files of the record. Any
            # other stage, word or record is refused here until it is decided in its turn.
            word = stage["modelled"]
            if stage["id"] != "egg" or word.get("state") != "planned" or [item.get("path") for item in word.get("record", [])] != EGG_RECORD:
                raise SystemExit(f"the stage {stage['id']} gives a word of its own for what Cells models of it ({word.get('state')}): only the egg's, planned, on its decided record, is given")
    if cited - set(sources):
        raise SystemExit(f"the stages cite {sorted(cited - set(sources))}, which are not among the open papers this tool checks")
    by_id = {stage["id"]: stage for stage in block["list"]}
    egg = next(level for level in by_id["egg"]["levels"] if level["id"] == "cell")
    if egg["shape"] != {"kind": "sphere", "across_um": EGG_UM} or egg.get("sources") != ["sato2025"]:
        raise SystemExit(f"the egg is drawn {egg['shape']}, not the sphere of {EGG_UM} µm that its source gives")
    time = {key: value for key, value in by_id["two-cell"]["time"].items() if key in FIRST_DIVISION}
    if time != FIRST_DIVISION or by_id["two-cell"]["time"]["sources"] != ["zahn2022"]:
        raise SystemExit(f"the two-cell stage's time is {by_id['two-cell']['time']}, not the first division's as its source gives it")
    if not all(words in by_id["four-cell"]["note"] for words in STAGE_NUMBERS_SAID):
        raise SystemExit("the four-cell stage's note no longer gives its time from the first division as its source does")
    # Decided on 19 November 2026: the frog opens on its fertilised egg. Its adult, the form this file describes, is a
    # press away on the strip. Any other opening stage, or none, is refused here until it is decided again.
    if block.get("opens_on") != "egg":
        raise SystemExit(f"the stages open on {block.get('opens_on', 'the file\'s own stage')!r}: the frog opens on its fertilised egg, as decided")
    return block, sources


# ---------------------------------------------------------------------------------------
# The outlines: an adult frog seen from above, its hind legs bent as in a kick, as a placeholder
# ---------------------------------------------------------------------------------------
#
# The length from snout to vent and the widths behind the forelimbs and in front of the hindlimbs are the paper's
# means for adult females; a thigh's width too. Where along the body those widths are drawn, the height, the head's
# shape, every limb's length, the feet and their webs and the pose are the picture's choice. The feet are drawn flat
# and level, so that the sheet of cells, which is drawn level, can lie on one.

GROUND_UM = 4000  # how high the belly is drawn above the ground: the picture's choice
VIEW = {"azimuth": 0, "polar": 0.5}  # the whole frog seen from above, its body level across the screen: the picture's choice
CRANIAL_AT, CAUDAL_AT = 0.36, 0.86  # where along the body the two widths are drawn, as shares of its length: the picture's choice
STEP_UM = 2420  # the stations of the head and body: 51, two of them at the widths' places


def body_profile(x):
    """The head and body's half width and half height at a distance x from the snout."""
    at_c, at_d = CRANIAL_AT * BODY_UM, CAUDAL_AT * BODY_UM
    if x <= at_c:
        wide = CRANIAL_UM / 2 * math.sin(math.pi / 2 * x / at_c) ** 0.6
    elif x <= at_d:
        t = (x - at_c) / (at_d - at_c)
        wide = CRANIAL_UM / 2 + (CAUDAL_UM - CRANIAL_UM) / 2 * t * t * (3 - 2 * t)
    else:
        wide = CAUDAL_UM / 2 * math.cos(math.pi / 2 * (x - at_d) / (BODY_UM - at_d)) ** 0.45
    return wide, 0.4 * wide


def limb(points, halves, flatten=1.0):
    """A limb's stations along a path of points [x, y, z], each with its half width (and its half height, times flatten)."""
    return [[round(x), round(y), round(z), round(half), round(half * flatten)] for (x, y, z), half in zip(points, halves)]


def along(points, steps):
    """Points along a path of corners, `steps` on each stretch, the corners included."""
    out = []
    for (a, b) in zip(points, points[1:]):
        for i in range(steps):
            t = i / steps
            out.append([a[k] + (b[k] - a[k]) * t for k in range(3)])
    out.append(list(points[-1]))
    return out


def outlines():
    body = []
    for i in range(round(BODY_UM / STEP_UM) + 1):
        x = i * STEP_UM
        wide, high = body_profile(x)
        body.append([x, round(GROUND_UM + high), 0, round(wide), round(high)])
    leg_y = GROUND_UM + 9000

    def hind(side):
        # From the hip, out and back to the bent knee, then back and in to the ankle: the thigh as wide as the paper's mean at its broadest.
        corners = [(BODY_UM - 9000, leg_y, side * 19000), (BODY_UM + 30000, leg_y, side * 58000), (BODY_UM + 62000, leg_y - 2000, side * 34000)]
        points = along(corners, 6)
        # The thigh at its broadest one station from the hip, tapering to the knee, then the shank to the ankle.
        halves = [THIGH_UM / 2 * (1 - 0.15 * max(0, i - 1) / 5) if i <= 6 else THIGH_UM / 2 * 0.85 - (THIGH_UM / 2 * 0.85 - 5200) * (i - 6) / 6 for i in range(len(points))]
        halves[0] = THIGH_UM / 2 * 0.9
        return limb(points, halves, flatten=0.55)

    def foot(side):
        # A flat blade from the ankle back, widening to the spread of its webbed toes, then rounding off: thin, and level.
        start = (BODY_UM + 62000, leg_y - 2000, side * 34000)
        stations = []
        for i in range(21):
            t = i / 20
            half = 5200 + 16000 * math.sin(math.pi * min(t / 0.8, 1) / 2) ** 1.2 if t <= 0.8 else 21200 * math.cos(math.pi / 2 * (t - 0.8) / 0.2) ** 0.5
            stations.append([round(start[0] + 54000 * t), round(start[1]), round(start[2] + side * 9000 * t), round(half), 1100 if t < 1 else 0])
        return stations

    def toes(side):
        # Five rays fanning from the ankle's end of the foot to its rim, on its upper face: the toes in its web.
        x0, y, z0 = BODY_UM + 62000, leg_y - 2000 + 1100, side * 34000
        paths = []
        for k in range(5):
            spread = (k - 2) / 2  # -1 to 1 across the foot
            start = [x0 + 0.15 * 54000, y, z0 + side * 9000 * 0.15]
            tip = [x0 + 54000 * (0.93 - 0.08 * spread * spread), y, z0 + side * 9000 * 0.93 + side * 17000 * spread]
            paths.append({"points": [[round(value) for value in start], [round(value) for value in tip]], "closed": False})
        return paths

    def fore(side):
        corners = [(38000, GROUND_UM + 6000, side * 21000), (50000, GROUND_UM + 3000, side * 36000), (30000, GROUND_UM + 1500, side * 46000)]
        points = along(corners, 4)
        halves = [5200 - 2800 * i / (len(points) - 1) for i in range(len(points))]
        return limb(points, halves, flatten=0.7)

    left = foot(-1)
    middle = left[10]
    foot_look = {"rings": {"every": 4, "first": 2, "points": 18}, "lines": [0.5, 1.5], "strength": 0.8, "alone": 0.95, "edge": 0.8, "pick": 10, "context": {"edge": 0.35, "fill": 0.05}}
    leg_look = {"rings": {"every": 3, "first": 1, "points": 16}, "strength": 0.5, "edge": 0.85, "fill": 0.05, "pick": 10, "context": {"edge": 0.35, "fill": 0.05}}
    arm_look = {"rings": {"every": 2, "first": 1, "points": 12}, "strength": 0.45, "edge": 0.8, "pick": 8}
    return {
        "format": "cells.visualizer.outline@1",
        "note": f"An adult frog seen from above, its hind legs bent as in a kick, as placeholder outlines. The head and body are drawn {BODY_UM / 10000:g} cm from the snout to the vent, {CRANIAL_UM / 10000:g} cm wide behind the forelimbs and {CAUDAL_UM / 10000:g} cm wide in front of the hindlimbs, and a thigh {THIGH_UM / 10000:g} cm wide at its broadest: the means one study measured in adult females kept as laboratory animals. The study is named in the species file. Where along the body the widths are drawn, the height, the head's shape, every limb's length, the feet and their webs and the pose are the picture's choice. The numbers were written out by tools/build_xenopus_atlas.py from one rounded body, a jointed loft for each limb, and one flat blade for each hind foot with five lines for its toes.",
        "tissue_on": {"at_um": [middle[0], middle[1] + middle[4], middle[2]], "clearance_um": 3, "note": "On the left hind foot, about half-way along it."},
        "parts": [
            {"name": "head and body", "group": "body", "kind": "loft", "stations": body, "rings": {"every": 3, "first": 1, "points": 28}, "lines": [0.25, 0.5, 0.75, 1.25, 1.5, 1.75], "strength": 0.5, "edge": 1, "fill": 0.07, "pick": 20, "context": {"edge": 0.4, "fill": 0.06}},
            {"name": "left hind leg", "group": "hind legs", "kind": "loft", "stations": hind(-1), **leg_look},
            {"name": "right hind leg", "group": "hind legs", "kind": "loft", "stations": hind(1), **leg_look},
            {"name": "left hind foot", "group": "hind feet", "kind": "loft", "stations": left, **foot_look},
            {"name": "left hind toes", "group": "hind feet", "kind": "lines", "paths": toes(-1), "strength": 0.55, "alone": 0.8},
            {"name": "right hind foot", "group": "hind feet", "kind": "loft", "stations": foot(1), **foot_look},
            {"name": "right hind toes", "group": "hind feet", "kind": "lines", "paths": toes(1), "strength": 0.55, "alone": 0.8},
            {"name": "left foreleg", "group": "forelegs", "kind": "loft", "stations": fore(-1), **arm_look},
            {"name": "right foreleg", "group": "forelegs", "kind": "loft", "stations": fore(1), **arm_look},
        ],
    }


# ---------------------------------------------------------------------------------------
# The two copies of a gene, and the twin rule
# ---------------------------------------------------------------------------------------

def components(d, every):
    """The proteome component UniProt gives each entry (the chromosomes it is placed on), and from it the copy of its
    gene: L where every component is an L chromosome, S where every one is an S chromosome, L and S where UniProt places
    the one entry on chromosomes of both, neither stated where it names none of them (an unplaced scaffold, the
    mitochondrion). The component file states no release of its own, so its entries must be those read."""
    lines = d.text(KB, COMPONENT_FILE).splitlines()
    if lines[0].split("\t") != ["Entry", "Proteomes"]:
        raise SystemExit("UniProt's table of proteome components is not the one asked for")
    placed = {}
    for line in lines[1:]:
        accession, said = line.split("\t")
        names = []
        for part in said.split("; "):
            proteome, _, name = part.partition(": ")
            if proteome != PROTEOME or not name:
                raise SystemExit(f"{accession}: a proteome component of another proteome ({part})")
            names.append(name)
        placed[accession] = names
    if set(placed) != set(every) or len(placed) != len(lines) - 1:
        raise SystemExit("the table of proteome components is not of the entries read; fetch both again")

    def copy(names):
        kinds = {match.group(1) for name in names for match in [re.match(r"Chromosome \d+(?:_\d+)?([LS])$", name)] if match}
        return "L and S" if kinds == {"L", "S"} else "L" if kinds == {"L"} else "S" if kinds == {"S"} else "neither stated"

    short = lambda name: name[len("Chromosome "):] if name.startswith("Chromosome ") else name
    return {accession: (copy(names), "; ".join(short(name) for name in names)) for accession, names in placed.items()}


def left_out_names(every):
    """The placeholder names (PLACEHOLDER): the entries whose gene name is one, and those whose protein name holds one.
    Unless WRITE_PLACEHOLDER_NAMES, each such field is emptied whole in the entries read, so that nothing built from them
    (the table, the shelves, the atlas, the twins named) writes it; a protein with no name is shown by its accession."""
    genes = {accession for accession, entry in every.items() if PLACEHOLDER.search(entry["gene"] or "")}
    names = {accession for accession, entry in every.items() if PLACEHOLDER.search(entry["name"] or "")}
    if not WRITE_PLACEHOLDER_NAMES:
        for accession in genes:
            every[accession]["gene"] = ""
        for accession in names:
            every[accession]["name"] = ""
    return genes, names


def reviewed_wins(entries):
    """The twin rule: where one gene has a reviewed entry and unreviewed entries among the proteins of UniProt's
    gene-by-gene set, only the reviewed one is shown. A gene is the entries tied together by the NCBI gene identifiers
    they share (an entry may carry several). Returns the entries shown, in the set's order; for each reviewed entry
    shown, the unreviewed entries of its gene that are not shown; and the counts."""
    parent = {}

    def root(key):
        while parent.setdefault(key, key) != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    for accession, entry in entries.items():
        root(accession)
        for gene_id in entry["genes"]:
            parent[root(accession)] = root(f"gene:{gene_id}")
    genes = defaultdict(list)
    for accession in entries:
        genes[root(accession)].append(accession)
    dropped, named = set(), defaultdict(list)
    won = twice = twice_entries = both_reviewed = 0
    for members in genes.values():
        if len(members) < 2:
            continue
        reviewed = [accession for accession in members if entries[accession]["reviewed"]]
        if not reviewed:
            twice += 1
            twice_entries += len(members)
            continue
        if len(reviewed) > 1:
            both_reviewed += 1
        twins = [accession for accession in members if not entries[accession]["reviewed"]]
        if twins:
            won += 1
            dropped.update(twins)
            for accession in reviewed:
                named[accession].extend(twins)
    shown = {accession: entry for accession, entry in entries.items() if accession not in dropped}
    counts = {"set": len(entries), "shown": len(shown), "shown_reviewed": sum(1 for e in shown.values() if e["reviewed"]), "dropped": len(dropped), "dropped_genes": won,
              "twice_unreviewed_genes": twice, "twice_unreviewed_entries": twice_entries, "genes_with_two_reviewed": both_reviewed, "twins_named_twice": sum(1 for twins in named.values() for _ in twins) - len(dropped)}
    found = {key: counts[key] for key in EXPECTED}
    if found != EXPECTED:
        raise SystemExit(f"the twin rule does not give the counts measured when it was decided: found {found}, measured {EXPECTED}")
    return shown, {accession: sorted(twins) for accession, twins in named.items()}, counts


def twin_said(written):
    """A twin as the panel and the search name it, its gene and then its accession, from the table's 'accession|gene'."""
    accession, _, gene = written.partition("|")
    return f"{gene} ({accession})" if gene else accession


def frog_marks(row):
    """The marks of the frog's own three columns, for cut_members: after the shared ones."""
    out = {"copy": row["copy"], "chromosome": row["chromosome"]}
    if row["same_gene"]:
        out["same_gene"] = [twin_said(written) for written in row["same_gene"].split(";")]
    return out


def named_by(d, shown):
    """How many of the proteins shown carry a gene name, as written here, for which UniProt's entry names Xenbase as a
    source of the name: the count behind Xenbase's line among the shelves' sources. Only the name of the source is read, never its
    identifier."""
    results = json.loads(d.text(KB, PLACES_FILE))["results"]
    count = 0
    for item in results:
        if item["primaryAccession"] not in shown or not shown[item["primaryAccession"]]["gene"]:
            continue  # not shown, or its gene name is not written
        sources = {evidence.get("source") for gene in item.get("genes") or [] for evidence in (gene.get("geneName") or {}).get("evidences", [])}
        count += "Xenbase" in sources
    return count


# ---------------------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------------------

def every_signature(d):
    """The InterPro entries UniProt gives every entry of the proteome, shown or not."""
    lines = d.text(KB, SIGNATURES_FILE).splitlines()
    if lines[0].split("\t") != ["Entry", "InterPro", "Gene Ontology IDs"]:
        raise SystemExit("UniProt's table of signatures and terms is not the one asked for")
    return {line.split("\t")[0]: set(filter(None, line.split("\t")[1].split(";"))) for line in lines[1:]}


def missed_by_marker(entries, every, signatures):
    """Where the protein shown for a gene lacks a unit's family that another entry of the same gene carries: the
    entry shown may be newer and not yet given its signatures. Returns a function that adds a sentence on each such
    gene to a unit's note, and the cases, for the report."""
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
                note += f" The frog's {name} is shown by its entry {marker}, which {lacks}; {P.plural(len(carriers), 'other entry', 'other entries')} of the same gene ({', '.join(carriers)}) carr{'ies' if len(carriers) == 1 else 'y'} the signature of {family['of']}. So the gene is a candidate by family too, though a search of the proteins shown does not list it."
        return note
    return more, cases


def build(datasets_folder, snapshot):
    d = P.Datasets(datasets_folder)
    must = lambda source, file, pattern, field=None: P.holds(d, source, file, pattern, field)
    must(KB, "terms_uniprot_license.json", UNIPROT_TERMS, "content")
    must(KB_DOCS, "terms_uniprot_license.json", UNIPROT_TERMS, "content")  # the copy beside the vocabulary of places, read from the human's folder
    must(IPR, "terms_interpro_license.html", r"All of the InterPro, Pfam, PRINTS and SFLD downloadable data provided on the InterPro website is freely available under CC0 1\.0 Universal")
    must(GO, "go_citation_policy.html", r"licensed under the Creative Commons Attribution 4\.0 Unported License")
    must(KB, "help_arba.json", r"ARBA", "content")
    must(*P.SAVED_TERMS["prosite"], r"distributed under the Creative Commons Attribution-NonCommercial-NoDerivatives \(CC BY-NC-ND 4\.0\) License")
    must(*P.SAVED_TERMS["hamap"], r"distributed under the Creative Commons Attribution \(CC BY 4\.0\) License")
    for tool in ("tmhmm", "signalp", "targetp"):
        must(*P.SAVED_TERMS[tool], rf"ACADEMIC SOFTWARE LICENSE AGREEMENT FOR END-USERS AT PUBLICLY FUNDED ACADEMIC, EDUCATION OR RESEARCH INSTITUTIONS FOR THE USE OF {tool}")
    must(*P.SAVED_TERMS["phobius"], r"Phobius is intended for academic users only")
    must(BIG_PI, "gpi_server.html", r"big-PI Predictor")
    must(KB_DOCS, "help_transmem.json", r"predicted by the application of the predictive tools TMHMM, Memsat, Phobius and the hydrophobic moment plot method", "content")
    must(KB_DOCS, "help_signal.json", r"predicted by the application of the predictive tools Phobius, Predotar, SignalP and TargetP", "content")
    cite = paper(d)
    stage_block, stage_sources = stages(d)  # the life stages, kept by hand, checked against their papers

    vocabulary = P.Vocabulary(d, KB_DOCS, CELL)
    every, read = P.read_proteome(d, KB, PLACES_FILE, vocabulary, GENE_DB)
    total, release, proteome = P.proteome_totals(d, KB, PLACES_FILE, SIGNATURES_FILE, PROTEOME, TAXON, vocabulary, every, read)
    placeholder_gene, placeholder_name = left_out_names(every)
    strain = (proteome.get("strain") or "").strip()
    copy_of = components(d, every)

    # --- the catalogue: UniProt's gene-by-gene set, both copies of each gene, and a reviewed entry over its twins -----
    in_set, together_set, stated = P.one_for_each_gene(d, KB, CANONICAL_FILE, every, total, proteome, "no_ncbi_gene")
    entries, twins, twin_counts = reviewed_wins(in_set)
    together = {accession: together_set[accession] for accession in entries}
    stated = {**stated, "shown": len(entries), "shown_reviewed": sum(1 for e in entries.values() if e["reviewed"]), "shown_unreviewed": sum(1 for e in entries.values() if not e["reviewed"]),
              "further": total["all"] - len(in_set), "not_shown": twin_counts["dropped"], "not_shown_genes": twin_counts["dropped_genes"],
              "twice_unreviewed_genes": twin_counts["twice_unreviewed_genes"], "twice_unreviewed_entries": twin_counts["twice_unreviewed_entries"],
              "no_ncbi_gene": sum(1 for e in entries.values() if not e["genes"])}
    of_gene = defaultdict(set)
    for accession, entry in every.items():
        for gene_id in entry["genes"]:
            of_gene[gene_id].add(accession)
    covered = set().union(set(entries), *(of_gene[gene_id] for entry in entries.values() for gene_id in entry["genes"]))
    stated["further_tied_to_a_shown_gene"] = len(covered) - len(entries)
    copies = Counter(copy_of[accession][0] for accession in entries)
    copies_reviewed = Counter(copy_of[accession][0] for accession in entries if entries[accession]["reviewed"])
    copies_not_shown = Counter(copy_of[accession][0] for accession in set(in_set) - set(entries))
    stated["copies"] = {copy: copies[copy] for copy in COPIES}
    placeholders = {"gene_names": len(placeholder_gene & set(entries)), "protein_names": len(placeholder_name & set(entries)), "twins": len(placeholder_gene & {twin for named_twins in twins.values() for twin in named_twins}), "written": WRITE_PLACEHOLDER_NAMES}
    stated["placeholder_names_not_written"] = {key: (0 if WRITE_PLACEHOLDER_NAMES else value) for key, value in placeholders.items() if key != "written"}
    by_xenbase = named_by(d, entries)
    # UniProt's gene names of the form LOC and a number whose number is the entry's own NCBI gene identifier, as UniProt's
    # cross-reference gives it: they are written as gene names; the count is said (rule 7, as worded on 19 November 2026).
    loc_names = {"all": sum(1 for entry in entries.values() if re.fullmatch(r"LOC\d+", entry["gene"] or "")), "own": sum(1 for entry in entries.values() if (found := re.fullmatch(r"LOC(\d+)", entry["gene"] or "")) and found.group(1) in entry["genes"])}

    filing = P.Filing(d, entries, KB, SIGNATURES_FILE, IPR, GO, catalogue=True)
    placed = {accession: P.place(entry, vocabulary) for accession, entry in entries.items()}
    gene = lambda accession: entries[accession]["gene"] or accession

    # --- the atlas: the families behind Cells' units, asked of this organism ---------------------------
    near, missed = missed_by_marker(entries, every, every_signature(d))
    units, unit_ids, beside = P.find_units(snapshot, entries, filing, P.human_signatures(d, HUMAN_KB), M.FAMILIES, M.UNITS, P.NOTHING, "the frog", other_said=", as on the planarian's side of the atlas", more=near)

    # --- the lines of the shelves -----------------------------------------------------------------------
    lines, alone, rest = P.make_lines(entries, placed, filing, unit_ids, CELL, per_file=MEMBERS_PER_FILE)
    sequence = P.in_order(entries, lines, alone, rest)
    shelf_counts, counts, bases, rules, evidence = P.counted(placed, CELL)
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
    s = stated
    shown_words = (
        f"UniProt's own gene-by-gene set of the proteome gives one protein for each gene, {twin_counts['set']:,}, and lists the two copies of a gene, on an L and on an S chromosome, as two genes: both are shown, each as its own protein. "
        f"Where a gene has a reviewed entry and unreviewed entries in that set, only the reviewed one is shown (decided on 19 November 2026): {s['not_shown']:,} unreviewed entries of {s['not_shown_genes']:,} genes are not shown, and each is named, in the mark 'same_gene', on the reviewed entry that stands for it, so that a search finds it. "
        f"{s['shown']:,} proteins are shown, {s['shown_reviewed']:,} with a reviewed entry and {s['shown_unreviewed']:,} with an unreviewed one. "
        f"{s['twice_unreviewed_genes']:,} genes still stand twice or more, with {s['twice_unreviewed_entries']:,} unreviewed entries and no reviewed one, since no record read here picks between them."
    )
    header = {
        "format": P.SHELF_FORMAT, "species": SPECIES_ID, "made": made,
        "from": f"UniProtKB release {release}: the reference proteome {PROTEOME} of Xenopus laevis{of_strain}, {s['entries']:,} entries ({s['reviewed']:,} reviewed, {s['unreviewed']:,} unreviewed) for {s['genes']:,} genes. {shown_words} The proteome's other {s['further']:,} entries are further forms of the same genes; each protein counts its gene's entries in the mark 'entries'.",
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
            "files": f"A file holds the members of consecutive lines: a new file begins where the next line would take it past {MEMBERS_PER_FILE:,} members, so a line is never split. 'file' names the file and 'at' the first and one past the last of its members there. The frog's files hold {MEMBERS_PER_FILE:,} where the others' hold {P.MEMBERS_PER_FILE:,}, so that its catalogue, the largest, adds fewer files to the page.",
            "places": "In the table a stated place is written with UniProt's identifiers, without their prefix: the place, then the topology and the face where the entry states them, joined by a full stop. 'place_words' gives the words of each.",
            "letters": P.letters(),
            "frog": "The table's last three columns are the frog's own: 'copy' and 'chromosome', from UniProt's proteome component of the entry, and 'same_gene', the unreviewed entries of the same gene that are not shown, each as its accession and its gene name joined by '|', several joined by ';'. They become the marks of the same names.",
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
        "entries": {"label": "Entries for its gene", "values": "number", "measured": False, "note": "The proteome's entries for the same gene, by the NCBI gene identifiers that UniProt gives each entry: this protein's own and the further forms of the gene.", "source": "UniProt"},
        "isoforms": {"label": "Isoforms described", "values": "number", "measured": False, "note": "The canonical sequence and the other sequences its own entry describes.", "source": "UniProt"},
        "seen": {"label": "Evidence that the protein exists", "values": [P.SEEN[level] for level in sorted(P.SEEN)], "measured": False, "note": "UniProt's level of evidence for the entry: at protein level, at transcript level, inferred from homology, predicted, or uncertain.", "source": "UniProt"},
        "evidence": {"label": "What stands behind the stated place", "values": [word for word, _, _ in P.EVIDENCE] + [P.NOT_GIVEN], "measured": False, "note": "From UniProt's evidence codes on the statement: an experiment in a paper the entry cites; likeness to a protein of which it is known; a curator's inference; a rule (a family rule or a sequence model that a curator applied, or, in an unreviewed entry, one of UniProt's automatic rule systems); not given, an older curated statement. Of several, the first in this order.", "source": "UniProt"},
        "where": {"label": "Stated place", "values": "text", "measured": False, "note": "The statement that decided the shelf, in UniProt's words: the place, then the topology and the face where the entry states them.", "source": "UniProt"},
        "also": {"label": "Also stated", "values": "text", "measured": False, "note": "The entry's other statements of place, in order and in UniProt's words.", "source": "UniProt"},
        "family": {"label": "Family, of which it is the only member here", "values": "text", "measured": False, "note": "The InterPro family's accession and name, for a protein listed among the only members of their families.", "source": "InterPro"},
        "of": {"label": "Stated for", "values": "text", "measured": False, "note": "The named form of the protein that the place is stated for, where the entry states none for the protein as a whole.", "source": "UniProt"},
        "copy": {"label": "Copy of its gene", "values": COPIES, "measured": False, "note": "The frog's chromosomes stand in two sets, which UniProt's proteome names 1L to 9_10L and 1S to 9_10S, and a gene of one set may have a copy in the other. The copy is read from the proteome component UniProt gives the protein's entry, never from its gene's symbol: L where every component is an L chromosome, S where every one is an S chromosome, L and S where UniProt places the one entry on chromosomes of both sets, and neither stated where it names an unplaced scaffold or the mitochondrion.", "source": "UniProt"},
        "chromosome": {"label": "Chromosome, as UniProt places the entry", "values": "text", "measured": False, "note": "The proteome components UniProt gives the protein's entry: a chromosome by its name (9_10L), several joined by a semicolon, or Unplaced, or Mitochondrion MT.", "source": "UniProt"},
        "same_gene": {"label": "Unreviewed entries of its gene, not shown", "values": "text", "measured": False, "search": True, "note": "Where a gene has a reviewed entry and unreviewed entries among the proteins of UniProt's gene-by-gene set, only the reviewed entry is shown (decided on 19 November 2026), and it names here the unreviewed entries of the same gene that are not shown, each by its gene name and its accession. A gene is the entries tied together by the NCBI gene identifiers that UniProt gives them. The page's search finds the reviewed entry by them.", "source": "UniProt"},
    }
    terms_day = lambda name: d.day(*P.SAVED_TERMS[name])
    own_said = "; ".join(f"{owner} {of(owner):,}" for owner in P.OWN_SYSTEMS if of(owner))
    sources = [
        {"name": "UniProt", "url": "https://www.uniprot.org/", "release": release, "accessed": d.day(KB, PLACES_FILE), "licence": "CC BY 4.0", "class": "permissive", "cite": P.CITE_UNIPROT,
         "holds": f"for each entry of the frog's reference proteome: its name, gene name, length and level of evidence, the places it states with the evidence for each, its membrane-spanning segments, signal peptide and anchors, its proteome component (the chromosome), and the InterPro entries and Gene Ontology terms UniProt gives it; its NCBI gene identifiers, used while building only to tie a gene's entries together; the gene-by-gene set of the proteome; and UniProt's vocabulary of places. The programs and rule systems of other owners behind its statements, and the nomenclature behind its gene names, are sources below. Placements that rest on UniProt's own automatic systems alone: {own_said or 'none'}"},
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
        {**XENBASE, "through": "UniProt",
         "holds": f"Nothing was downloaded from it but its statement of terms, in the round that gathered the frog's data, and nothing of it is copied. The gene names were read in UniProt's entries, whose evidence names Xenbase's nomenclature as the names' source: {by_xenbase:,} of the {s['shown']:,} proteins shown carry a gene name for which UniProt names it so. It was decided on 19 November 2026 that the names are used as read from UniProt, with Xenbase named behind them; no Xenbase identifier is written here, no page of it is linked but its site, and this tool reads none of its pages."},
    ]
    sources = [source for source in sources if source["name"] != "big-PI" or of("big-PI")]
    closing = {"marks": marks, "counts": counts, "shelf_counts": shelf_counts, "by_basis": P.by_basis(bases), "by_evidence": P.by_evidence(evidence), "sources": sources}

    body = P.shelves_text(header, lines, alone, rest, lone, no_family, tail, places, place_words, closing, len(family_total))
    for accession, said in twins.items():
        for twin in said:
            if "|" in twin or ";" in twin or "|" in every[twin]["gene"] or ";" in every[twin]["gene"]:
                raise SystemExit(f"{twin}: its accession or gene name holds the table's separator")
    shared = P.proteome_values(entries, together)
    more = lambda protein: [*shared(protein), *copy_of[protein], ";".join(f"{twin}|{every[twin]['gene']}" if every[twin]["gene"] else twin for twin in twins.get(protein, []))]
    table = P.table_text(TABLE_COLUMNS, sequence, entries, placed, filing, alone, unit_ids, more=more)

    # --- the species file and its outlines ---------------------------------------------------------------
    findings = Counter(unit["finding"] for unit in units.values())
    clauses = [f"{findings['found']} have proteins of the same family in the frog"]
    if findings["different family"]:
        clauses.append(f"{findings['different family']} are built from another family")
    if findings["none found"]:
        clauses.append(f"{findings['none found']} {'was' if findings['none found'] == 1 else 'were'} not found")
    machines = f"of the {len(units)} units of the law inventory, {P.listed(clauses)}; the other {findings['nothing to look for']} name no natural protein to look for"
    shape = outlines()
    sizes = f"{BODY_UM / 10000:g} cm from snout to vent, {CRANIAL_UM / 10000:g} cm wide behind the forelimbs and {CAUDAL_UM / 10000:g} cm in front of the hindlimbs, a thigh {THIGH_UM / 10000:g} cm wide"
    species = {
        "format": "cells.visualizer.species@1", "id": SPECIES_ID, "label": LABEL, "organism": ORGANISM, "taxon": TAXON,
        "plain": f"The African clawed frog of the laboratory: {s['genes']:,} genes in UniProt's reference proteome, on two sets of chromosomes, L and S, and {s['shown']:,} proteins shown, both copies of a gene among them. Its cell is drawn as the mouse's is: one cell of a sheet that stands for skin-like tissue. The frog is drawn as an adult; on the strip of its life stages its fertilised egg is drawn too, and four stages between are named and not drawn.",
        "group": "Animals", "order": 17, "default": False, "made": made,  # after the mouse, before the planarian
        "modelled": {"state": "generic", "text": "Cells models a generic cell and a sheet of such cells, not this animal. The sheet stands for skin-like tissue and is drawn on a hind foot for the scales only. The foot and the frog are placeholder outlines: nothing at those scales is simulated."},
        "levels": [
            {"id": "molecules"},
            {"id": "cell", "shape": {"kind": "prism", "sides": 6, "radius_um": 10.6, "height_um": 13, "corner_um": 2.4, "edge_um": 1.3},
             "note": "The cell drawn is one cell of the sheet, which stands for skin-like tissue; it is not a model of a frog's skin cell. Its shape and its sizes are the picture's choice: six flat sides where it meets its neighbours, an outer face and a base, about 20 µm across and as tall as the sheet's cells. The plate under the layer is scenery: Cells models nothing beneath the sheet.",
             "notes": [{"text": "One cell of the skin-like layer"}, {"text": "Its flat-sided shape is the picture's choice", "roomy": True}], "fade_out_um": [120, 190]},
            {"id": "tissue", "shape": {"kind": "cell sheet", "rings": 6, "beyond": [[8, 0.34], [10, 0.2], [11, 0.1]]},
             "note": "The sheet stands for skin-like tissue: a single layer of cells. It is drawn on the hind foot of the placeholder frog for the scales only; the simulated sheet is not the frog's skin.",
             "notes": [{"text": "The sheet stands for skin-like tissue: a single layer of cells", "short": "Stands for skin-like tissue"}], "fade_in_um": [100, 190]},
            {"id": "organ", "label": "Hind foot", "shape": {"kind": "outline", "ref": SPECIES_ID, "parts": ["left hind foot", "left hind toes"], "context": ["head and body", "left hind leg"]},
             "note": "The outline drawn is a frog's webbed hind foot, as a placeholder: a flat blade from the ankle, widening to the spread of its five toes, laid level so that the sheet of cells, drawn level, can lie on it. The foot is the picture's choice of organ, so that the sheet that stands for skin-like tissue lies on a part of the animal a visitor knows; no foot is modelled, and the foot's own cells are not modelled. The sheet is drawn on the foot so that the scales follow one another; it is not the foot's tissue. The foot's length, its breadth, its thickness and its shape are the picture's choice: no measurement of a foot was read for this file.",
             "sheet_mark": {"band": 0.15, "note": "The sheet, to scale: drawn on the foot for the scales only", "note_at_um": [0, 0, -16000]},
             "notes": [{"text": "A frog's hind foot: a placeholder outline"}, {"text": "The foot's own cells are not modelled", "lift": -22, "roomy": True}]},
            {"id": "organism", "label": "Whole frog", "shape": {"kind": "outline", "ref": SPECIES_ID},
             "note": f"The outline drawn is an adult frog seen from above, its hind legs bent as in a kick, as a placeholder: {sizes}, the means that one study measured in 198 adult females (190 for the thigh) kept as laboratory animals. Where along the body the widths are drawn, the height, the head's shape, every limb's length, the feet and the pose are the picture's choice. The sheet of cells is drawn on the left hind foot for the scales only.",
             "sources": [PAPER["key"]],
             "view": VIEW,
             "sheet_mark": {"band": 0.22, "note": "Here lies the sheet: too small to see, so its ring is not to scale", "note_at_um": [0, 0, -14000], "roomy": True},
             "notes": [{"text": "An adult frog: a placeholder outline"}]},
        ],
        "cell": {
            "facts": [
                {"label": "Proteins", "value": f"{s['genes']:,} genes in UniProt's reference proteome, with {s['entries']:,} entries: {s['reviewed']:,} reviewed by a curator and {s['unreviewed']:,} annotated automatically. Both copies of a gene are shown, each as its own protein; where a gene has a reviewed entry, its unreviewed entries in UniProt's gene-by-gene set ({s['not_shown']:,}) are not shown: {s['shown']:,} proteins in all", "sources": ["uniprot"]},
                {"label": "Copies", "value": f"of the {s['shown']:,} proteins shown, UniProt places {copies['L']:,} on an L chromosome, {copies['S']:,} on an S chromosome, {copies['L and S']:,} on chromosomes of both sets, and {copies['neither stated']:,} on neither (an unplaced scaffold, or the mitochondrion)", "sources": ["uniprot"]},
                {"label": "Cells' units", "value": machines, "sources": ["uniprot"]},
                {"label": "The outline's sizes", "value": f"{sizes}: the means of 198 adult females (190 for the thigh) kept as laboratory animals; males were {MALE_UM / 10000:g} cm from snout to vent", "sources": [PAPER["key"]]},
            ],
            "parts": {"membranes": 1, "wall": False, "nucleus": True, "organelles": ["er", "golgi", "mitochondria"]},
        },
        "stages": stage_block,
        "sources": {
            "uniprot": {"text": f"UniProt Consortium, UniProt release {release}: the reference proteome {PROTEOME} (Xenopus laevis{of_strain}), its entries, their proteome components and its gene-by-gene set.", "url": f"https://www.uniprot.org/proteomes/{PROTEOME}", "licence": "CC BY 4.0", "class": "permissive", "accessed": d.day(KB, PLACES_FILE)},
            PAPER["key"]: {"text": f"{cite} Its Table 1 gives, for 198 adult females kept as laboratory animals, a snout-vent length of 12.1 ± 1.0 cm, a width directly behind the forelimbs of 5.1 ± 0.5 cm and directly in front of the hindlimbs of 6.2 ± 0.7 cm, and (for 190) a thigh width of 3.4 ± 0.3 cm; for 40 males, a snout-vent length of 7.7 ± 0.3 cm.", "doi": PAPER["doi"], "licence": "CC BY 4.0", "class": "permissive", "accessed": d.day(PAPERS_AT, PAPER["file"])},
            **stage_sources,
        },
    }
    atlas = {
        "format": P.ATLAS_FORMAT,
        "species": {"id": SPECIES_ID, "label": LABEL, "organism": ORGANISM, "taxon": TAXON, "plain": f"The African clawed frog, with {s['genes']:,} genes in UniProt's reference proteome, on two sets of chromosomes, L and S. This is what the family signatures of Cells' units find among the {s['shown']:,} proteins shown."},
        "made": made,
        "method": [
            f"The frog's proteins are those of UniProt's gene-by-gene set of the reference proteome {PROTEOME} (release {release}), {twin_counts['set']:,}, which lists the two copies of a gene, on an L and on an S chromosome, as two genes. Both copies are shown, each as its own protein: nothing read here says they are one, and no pair is merged.",
            f"Where a gene has a reviewed entry and unreviewed entries in that set, only the reviewed one is shown (decided on 19 November 2026): {s['not_shown']:,} unreviewed entries of {s['not_shown_genes']:,} genes are not shown, and the reviewed entry names them on the shelves. A gene is the entries tied together by the NCBI gene identifiers UniProt gives them. {s['shown']:,} proteins are shown, {s['shown_reviewed']:,} with a reviewed entry and {s['shown_unreviewed']:,} with an unreviewed one.",
            f"{s['twice_unreviewed_genes']:,} genes still stand twice or more among them, with {s['twice_unreviewed_entries']:,} unreviewed entries and no reviewed one, since no record read here picks between them.",
            "Licences were read before anything was copied; each is stated in sources.",
            "Each unit's family was taken from its own human candidates, by the same InterPro signatures that the other species' atlases ask. The build checks that the candidates carry them.",
            "Each signature was looked for among the InterPro entries UniProt gives each protein. A unit counts as found only where a protein carries the signature of a family that makes the machine itself; an accessory family alone does not make it found.",
            "A frog protein is listed because its own entry carries the family's signature, never because its gene's symbol looks like that of a human candidate. Both copies of a gene are listed where both carry it.",
            P.TWO_FACTS,
            "Several units of one family (the Kv1 channels) list the same proteins, and nothing here says which protein does which unit's work.",
            "No similarity search was run, no source of orthology was read, and nothing is called an ortholog.",
        ],
        "sources": [
            {"name": "UniProt", "url": "https://www.uniprot.org/", "release": release, "accessed": d.day(KB, PLACES_FILE), "licence": "CC BY 4.0", "class": "permissive", "cite": P.CITE_UNIPROT, "holds": "the entries of the frog's proteins, reviewed and unreviewed, with the InterPro entries UniProt gives each; the signatures of the units' human candidates"},
            {"name": "InterPro", "url": "https://www.ebi.ac.uk/interpro/", "release": filing.release, "accessed": d.day(IPR, "entry.list"), "licence": "CC0 1.0", "class": "permissive", "cite": P.CITE_INTERPRO, "holds": "the identifiers and names of the family signatures"},
        ],
        "not_copied": "No sequence is copied. The NCBI gene identifiers that tie a gene's entries together are those UniProt gives its entries, used while building only; none is written here. The gene names are UniProt's, and the shelves name the nomenclature behind them.",
        "units": units,
        "extra": [],
    }
    report = {
        "release": release, "interpro": filing.release, "ontology": filing.ontology, "made": made, "strain": strain, "stated": stated, "read": dict(read), "twins": twin_counts, "placeholders": placeholders, "loc_names": loc_names,
        "copies": dict(copies), "copies_reviewed": dict(copies_reviewed), "copies_not_shown": dict(copies_not_shown), "named_by_xenbase": by_xenbase,
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
    report["sizes"] = P.within_limits(files_out, PATHS, limits=LIMITS)
    # The placeholder names, where they are not written: no gene or name field holds one (the table's, the shelves', the atlas's).
    if not WRITE_PLACEHOLDER_NAMES:
        for name in ("table", "shelves", "atlas", "species"):
            if PLACEHOLDER.search(files_out[name]):
                raise SystemExit(f"the {name} would hold a placeholder name: {PLACEHOLDER.search(files_out[name]).group(0)}")
    # Nothing of Xenbase but its name as a source: no identifier anywhere, and the name only in the shelves' source and the README.
    for name, text in files_out.items():
        if re.search(r"\bXB-[A-Z]+-\d", text) or re.search(r"xenbase\.org/[^\"]", text, re.I):
            raise SystemExit(f"the {name} would hold a Xenbase identifier or a page of it")
        if re.search(r"xenbase", text, re.I) and name not in ("shelves", "readme"):
            raise SystemExit(f"the {name} would name Xenbase, which only the shelves' sources and their README do")
    return files_out, report


def placeholder_sentence(counts):
    """The README's one sentence on the placeholder names, as the switch stands."""
    if counts["written"]:
        return f"UniProt's names are written as it gives them, among them placeholder names of Xenbase's nomenclature that embed the gene's number there (a word of XB and four or more digits): {counts['gene_names']:,} gene names and {counts['protein_names']:,} protein names of the proteins shown, and {counts['twins']:,} gene names of the twins not shown."
    return f"{counts['gene_names']:,} gene names and {counts['protein_names']:,} protein names of the proteins shown, and the gene names of {counts['twins']:,} twins not shown, are not written here: UniProt gives them, and they are placeholder names of Xenbase's nomenclature that embed the gene's number there (a word of XB and four or more digits); such a protein is shown by its accession."


def build_readme(report, header, closing):
    r = report
    names = {shelf["id"]: shelf["label"] for shelf in header["shelves"]}
    s = r["stated"]
    lines = [
        "# The frog: its own proteins, on shelves",
        "",
        "Generated by `tools/build_xenopus_atlas.py`; do not edit by hand. The note is `docs/XENOPUS.md`.",
        "",
        f"- `shelves.json`: {header['from']}",
        f"- `proteins.tsv`: one line for each of the {s['shown']:,} proteins shown, in the order of the shelves' lines, with the copy of its gene, its chromosome and the unreviewed entries of its gene that are not shown. No sequences, and no NCBI gene identifiers.",
        f"- The members' files are not kept here: `python3 tools/build_xenopus_atlas.py members --out DIR` cuts them from these two files, {MEMBERS_PER_FILE:,} members to a file.",
        "",
        "Nothing of the frog is in the engine's picture here. This is reference data for the viewer.",
        "",
        "## The two copies of a gene",
        "",
        "| Copy of its gene (UniProt's proteome component) | Proteins shown | Of them reviewed | Not shown (unreviewed twins) |",
        "| --- | ---: | ---: | ---: |",
        *[f"| {copy} | {r['copies'].get(copy, 0):,} | {r['copies_reviewed'].get(copy, 0):,} | {r['copies_not_shown'].get(copy, 0):,} |" for copy in COPIES],
        "",
        f"{s['not_shown']:,} unreviewed entries of {s['not_shown_genes']:,} genes are not shown, since a reviewed entry of the same gene is; each reviewed entry names them in its mark `same_gene`, and the page's search finds it by them. {s['twice_unreviewed_genes']:,} genes still stand twice or more, with {s['twice_unreviewed_entries']:,} unreviewed entries and no reviewed one.",
        "",
        placeholder_sentence(r["placeholders"]),
        "",
        f"No NCBI gene identifier is written as a column, a mark or a tie. {r['loc_names']['all']:,} of the gene names written are UniProt's (CC BY 4.0) of the form LOC and a number; in {r['loc_names']['own']:,} of them the number is the gene's own at NCBI, as UniProt's cross-reference gives it.",
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
        "## What rests on tools, rule systems and a nomenclature of other owners",
        "",
        "By the project's rule (the user, 15 November 2026), a value stands on the terms of the database it was read from, here UniProt's, and the tool behind it is named and counted. It is the project's rule, not a legal opinion. Nothing was downloaded from any of these but a statement of terms, and no tool was run. It was decided on 19 November 2026 that the frog's gene names are used as read from UniProt, with Xenbase named behind them.",
        "",
        "| Tool, rule system or nomenclature | Class | What rests on it |",
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
        f"twins: {r['twins']}; copies shown {r['copies']} (reviewed {r['copies_reviewed']}; not shown {r['copies_not_shown']}); gene names with Xenbase named: {r['named_by_xenbase']:,}",
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
        P.write_members(args.out_dir, args.out, first=P.proteome_marks, last=frog_marks)
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
