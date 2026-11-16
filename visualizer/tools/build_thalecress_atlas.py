#!/usr/bin/env python3
"""Build the viewer's data on thale cress, Arabidopsis thaliana: the species with its levels and
placeholder outlines, its side of the protein atlas, and its own proteins on a plant cell's shelves.

Six files are written, each from saved answers of public databases and one open paper:

    data/species/thalecress.json           the species file (schema/SPECIES.md)
    data/species/shapes/thalecress.json    placeholder outlines of a leaf and a rosette (schema/SPECIES_SHAPES.md)
    data/proteins/atlases/thalecress.json  its side of the protein atlas (schema/SPECIES_ATLAS.md)
    data/proteins/thalecress/              shelves.json, proteins.tsv and README.md (schema/SPECIES_PROTEINS.md)

The catalogue is UniProt's whole reference proteome, as the fruit fly's is: one protein for each
gene, the one UniProt's own gene-by-gene set gives, reviewed or not. A plant cell has membranes an
animal cell lacks, so it has three shelves more: the plastid's envelope, the thylakoid membrane
inside it, and the vacuole's membrane.

    python3 tools/build_thalecress_atlas.py fetch --datasets DATA     the only step that uses the network
    python3 tools/build_thalecress_atlas.py build --datasets DATA     the same bytes every time
    python3 tools/build_thalecress_atlas.py members --out DIR         the members' files, for the page

The reading of entries, the gene-by-gene catalogue and the members' files are the fruit fly tool's;
the shelves' machinery is the human tool's; the families asked of every species are the M. pneumoniae
tool's; the download step, the papers' checks and the accessory families are the E. coli tool's.
A change to any of them shows in this tool's byte-for-byte test.

This is the viewer's reference data. Nothing of the plant is in the engine. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import build_human_atlas as H  # noqa: E402
import build_mpneumoniae_atlas as M  # noqa: E402
import build_ecoli_atlas as E  # noqa: E402
import build_fruitfly_atlas as F  # noqa: E402

SNAPSHOT = ROOT / "data" / "proteins" / "inventory.snapshot.json"
SPECIES_FILE = ROOT / "data" / "species" / "thalecress.json"
SHAPES_FILE = ROOT / "data" / "species" / "shapes" / "thalecress.json"
ATLAS_FILE = ROOT / "data" / "proteins" / "atlases" / "thalecress.json"
OUT_DIR = ROOT / "data" / "proteins" / "thalecress"
PATHS = re.compile(r"/(?:home|mnt|Users|tmp)/")
MINE = "the visualizer's thale cress agent"
TOOL = "tools/build_thalecress_atlas.py"

SPECIES_ID, LABEL, ORGANISM, TAXON, PROTEOME = "thalecress", "Thale cress", "Arabidopsis thaliana", 3702, "UP000006548"
UNIPROT = "https://rest.uniprot.org"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
GENE_SETS = "https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/reference_proteomes"
KB = "thalecress/uniprot-thalecress-reference-proteome"
PAPERS_AT = "thalecress/europepmc-open-papers"
FLY_KB = "fruitfly/uniprot-fruitfly-reference-proteome"  # read only: UniProt's help page on its automatic annotation
PLACES_FILE = f"uniprotkb_{PROTEOME}_places.json.gz"
SIGNATURES_FILE = f"uniprotkb_{PROTEOME}_signatures.tsv.gz"
CANONICAL_FILE = f"{PROTEOME}_{TAXON}.fasta.gz"
ALL = f"(proteome:{PROTEOME})"
PLACE_FIELDS = "accession,id,protein_name,gene_primary,xref_araport,length,protein_existence,cc_subcellular_location,ft_transmem,ft_intramem,ft_signal,ft_transit,ft_topo_dom,ft_lipid,cc_alternative_products,fragment"

# The open paper the cell's and the plant's numbers rest on, with the sentences it must hold.
PAPERS = {
    "tolleter2024": {
        "pmc": "PMC10988163", "doi": "10.1017/qpb.2024.1", "licence": "CC BY",
        "holds": [
            r"spongy cells are smaller \(60 pL\) than palisade cells \(100 pL\)",
            r"hollow cylinder of radius r c = 23\.7 μm",
            r"Chloroplast numbers per cell \(100\) and average chloroplast volume \(93 fL\) in mesophyll palisade cells",
            r"vacuoles represent the largest fraction of the cellular volume in a leaf \(84%",
            r"The averaged cell wall thickness was 150 nm for epidermal pavement cells and mesophyll cells",
            r"reference leaf 6 with a surface of 121 mm 2",
            r"3-week-old Arabidopsis thaliana Col-0 rosette with 29 leaves, and a total leaf area of 10,500 mm 2",
        ],
    },
}
SOURCES = {
    KB: {"what": f"UniProtKB: every entry of the reference proteome {PROTEOME} of Arabidopsis thaliana, reviewed and unreviewed, with its name, gene, Araport gene, length, level of evidence, stated places with the evidence for each, segments, signals, transit peptides and anchors; the InterPro entries and Gene Ontology terms of each; the proteome's record and counts; and UniProt's gene-by-gene set of the proteome (one protein for each gene)", "licence": "CC BY 4.0"},
    PAPERS_AT: {"what": "One open paper from Europe PMC, as its record there (with its licence) and its full text: a quantitative atlas of the Arabidopsis leaf, for the sizes and numbers of a leaf cell and its parts", "licence": "CC BY, as its record at Europe PMC states"},
}

# ---------------------------------------------------------------------------------------
# A plant cell's shelves: the human's six, and three for the membranes an animal cell lacks
# ---------------------------------------------------------------------------------------
#
# The plastid has two levels. Its envelope (two membranes, one shelf) has the stroma inside it and
# the cytoplasm beyond. The thylakoid membrane lies in the stroma: its lumen is inside, the stroma
# beyond. A protein free in the stroma stands on the envelope's shelf, inside; one held at the
# thylakoid membrane and facing the stroma stands on the thylakoid's shelf, outside.

M_, IN_, OUT_, WHOLE_, REGION_, ELSE_ = H.MEMBRANE, H.INSIDE, H.OUTSIDE, H.WHOLE, H.REGION, H.ELSEWHERE
_human = {shelf["id"]: shelf for shelf in H.SHELVES}
SHELVES = [
    {**_human["cell"], "outside": "Outside the cell: in its wall and in the space around it"},
    _human["er"],
    _human["mito"],
    {"id": "plastid", "label": "Plastid envelope", "outside": "On the cytoplasmic face of the plastid's envelope", "inside": "Within the plastid: in its stroma"},
    {"id": "thylakoid", "label": "Thylakoid membrane", "outside": "In the plastid's stroma, at the thylakoid membrane", "inside": "In the thylakoid's lumen"},
    {"id": "vacuole", "label": "Vacuole membrane", "outside": "On the cytoplasmic face of the vacuole's membrane", "inside": "In the vacuole"},
    _human["nucleus"],
    _human["other"],
    _human["membrane"],
]
SHELF_NOTES = {
    "cell": "A plant cell has a wall beyond its membrane. A protein of the wall, or of the space outside the membrane, stands here on the outside, and its mark 'where' names the wall. A protein of the plasmodesmata, the channels that join a plant's cells through the wall, stands on this shelf too.",
    "plastid": "The plastid's two envelope membranes stand as one shelf: a protein in either of them is in the envelope, and its mark 'where' says which where the entry does. A protein free in the stroma stands here, on the inside. Most of the plant's plastids are chloroplasts; the entries' words say which kind.",
    "thylakoid": "The membrane inside the chloroplast. Its lumen is on the inside; the stroma lies beyond it, so a protein held at this membrane and facing the stroma stands on the outside, while a protein free in the stroma stands on the plastid envelope's shelf.",
    "vacuole": "The membrane of the vacuole, a plant cell's largest compartment.",
    **H.SHELF_NOTES,
}
PLACES = {
    **{name: line for name, line in H.PLACES.items() if name != "Vacuole"},
    "Plastid": ("plastid", WHOLE_),
    "Plastid stroma": ("plastid", IN_),
    "Plastid envelope": ("plastid", WHOLE_),            # the two membranes; which, and which face, is not said
    "Plastid membrane": ("plastid", M_),
    "Plastid inner membrane": ("plastid", M_),
    "Plastid outer membrane": ("plastid", M_),
    "Plastid intermembrane space": ("plastid", REGION_),  # between the envelope's two membranes: neither the stroma nor the cytoplasm
    "Plastoglobule": ("plastid", IN_),                   # a lipid body of the chloroplast
    "Chloroplast nucleoid": ("plastid", IN_),
    "Thylakoid": ("thylakoid", WHOLE_),
    "Plastid thylakoid": ("thylakoid", WHOLE_),
    "Plastid thylakoid membrane": ("thylakoid", M_),
    "Plastid thylakoid lumen": ("thylakoid", IN_),
    "Vacuole": ("vacuole", WHOLE_),
    "Vacuole membrane": ("vacuole", M_),
    "Vacuole lumen": ("vacuole", IN_),
    "Prevacuolar compartment": ("other", WHOLE_),
    "Symplast": ("cell", IN_),                           # the vocabulary: the cytoplasms of the plant's cells, joined by plasmodesmata
    "Periplasm": (None, ELSE_),
}
FACES = {
    **H.FACES,
    "Cytoplasmic side": {**H.FACES["Cytoplasmic side"], "plastid": "outside", "vacuole": "outside"},
    "Lumenal side": {**H.FACES["Lumenal side"], "thylakoid": "inside", "vacuole": "inside"},
    "Stromal side": {"thylakoid": "outside", "plastid": "inside"},
    "Intermembrane side": {**H.FACES["Intermembrane side"], "plastid": "in"},  # between the envelope's two membranes: within the envelope
}
AWAY = {**H.AWAY, "vacuole": "inside"}  # the vacuole lies along the secretory pathway
UPSTREAM = F.UPSTREAM
TABLE_COLUMNS = F.TABLE_COLUMNS
listed, plural, some = E.listed, E.plural, F.some


def requests():
    out = []

    def add(source, file, url, purpose, **more):
        out.append({"source": source, "file": file, "url": url, "purpose": purpose, **more})

    q = H.q
    stream = f"{UNIPROT}/uniprotkb/stream?query={q(ALL)}&compressed=true"
    add(KB, PLACES_FILE, f"{stream}&format=json&fields={PLACE_FIELDS}", "every entry of the proteome: its name, gene, Araport gene, length and level of evidence, where the entry places it and on what evidence, its segments, signals, transit peptides and anchors", gzip=True)
    add(KB, SIGNATURES_FILE, f"{stream}&format=tsv&fields=accession,xref_interpro,go_id", "the InterPro entries and the Gene Ontology terms UniProt gives each entry", gzip=True)
    count = lambda query: f"{UNIPROT}/uniprotkb/search?query={q(query)}&size=1&fields=accession&format=json"
    for name, query in (("all", ALL), ("reviewed", f"{ALL} AND (reviewed:true)"), ("unreviewed", f"{ALL} AND (reviewed:false)"), ("reviewed_with_place", f"{ALL} AND (reviewed:true) AND (cc_scl_term:*)"), ("unreviewed_with_place", f"{ALL} AND (reviewed:false) AND (cc_scl_term:*)")):
        add(KB, f"count_{name}.json", count(query), f"how many entries of the proteome: {name.replace('_', ' ')} (the count is in the answer's header)")
    add(KB, f"proteome_{PROTEOME}.json", f"{UNIPROT}/proteomes/{PROTEOME}", "the proteome's own record: its counts and its genome assembly")
    add(KB, CANONICAL_FILE, f"{GENE_SETS}/Eukaryota/{PROTEOME}/{CANONICAL_FILE}", "UniProt's gene-by-gene set of the proteome: one protein for each gene. Only the names of its entries are read", gzip=True)
    for key, paper in PAPERS.items():
        add(PAPERS_AT, f"{key}_record.json", f"{EPMC}/search?format=json&resultType=core&query=PMCID:{paper['pmc']}", "the paper's record at Europe PMC, with its licence", contains=paper["pmc"])
        add(PAPERS_AT, f"{key}_fulltext.xml", f"{EPMC}/{paper['pmc']}/fullTextXML", "the paper's full text", contains="<article")
    return out


def fetch(datasets, refresh=False):
    E.requests, E.SOURCES, E.MINE, E.TOOL = requests, SOURCES, MINE, TOOL
    return E.fetch(datasets, refresh=refresh)


def adopt():
    """Give the shared machinery this organism's folders and a plant cell's shelves."""
    F.KB, F.PLACES_FILE, F.SIGNATURES_FILE, F.CANONICAL_FILE, F.GENE_DB = KB, PLACES_FILE, SIGNATURES_FILE, CANONICAL_FILE, ("Araport", "AT")
    F.adopt(None)
    H.SHELVES, H.SHELF_IDS, H.SHELF_NOTES = SHELVES, [shelf["id"] for shelf in SHELVES], SHELF_NOTES
    H.PLACES, H.FACES, H.AWAY = PLACES, FACES, AWAY
    E.PAPERS, E.PAPERS_AT = PAPERS, PAPERS_AT


# ---------------------------------------------------------------------------------------
# The outlines: one leaf, and a rosette of leaves, as placeholders
# ---------------------------------------------------------------------------------------

LEAF_UM, LEAF_WIDE_UM, LEAVES, HUB_UM = 17000, 9000, 8, 2000  # the picture's choice; the leaf's area is near the paper's 121 mm²


def outlines():
    width = lambda t: LEAF_WIDE_UM * math.sin(math.pi * t) ** 0.55 if 0 < t < 1 else 0
    steps = [step / 16 for step in range(17)]
    blade = [[round(HUB_UM + LEAF_UM * t), 0, 0, round(width(t)), 200 if 0 < t < 1 else 0] for t in steps]
    others = []
    for index in range(1, LEAVES):
        angle, scale = 2 * math.pi * index / LEAVES, 0.72 + 0.28 * ((index * 5) % LEAVES) / LEAVES
        along, across = (math.cos(angle), math.sin(angle)), (-math.sin(angle), math.cos(angle))
        point = lambda t, side: [round((HUB_UM + LEAF_UM * scale * t) * along[0] + side * width(t) * scale / 2 * across[0]), 0, round((HUB_UM + LEAF_UM * scale * t) * along[1] + side * width(t) * scale / 2 * across[1])]
        others.append({"points": [point(t, 1) for t in steps] + [point(t, -1) for t in reversed(steps[1:-1])], "closed": True})
    return {
        "format": "cells.visualizer.outline@1",
        "note": f"One leaf of thale cress and a rosette of {LEAVES} leaves seen from above, as placeholder outlines. The leaf is drawn {LEAF_UM // 1000} mm long and {LEAF_WIDE_UM // 1000} mm wide: the picture's choice of a blade whose area is near the 121 mm² that one open paper gives for its reference leaf (the paper is named in the species file). The number of leaves, their lengths, the rosette's width and the leaf's thickness are the picture's choice, and no measurement was read for them. The numbers were written out by tools/build_thalecress_atlas.py from one rounded blade, turned about the plant's centre.",
        "tissue_on": {"at_um": [HUB_UM + LEAF_UM // 2, 103, 0], "clearance_um": 3, "note": "On the upper side of one leaf, half-way along it."},
        "parts": [
            {"name": "leaf", "group": "leaf", "kind": "loft", "stations": blade, "rings": {"every": 4, "first": 2, "points": 18}, "lines": [0.5, 1.5], "strength": 0.8, "alone": 0.95, "edge": 0.8, "pick": 10},
            {"name": "other leaves", "kind": "lines", "paths": others, "strength": 0.7},
        ],
    }


# ---------------------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------------------

def build(datasets_folder, snapshot):
    d = H.Datasets(datasets_folder)
    must = lambda source, file, pattern, field=None: re.search(pattern, json.loads(d.text(source, file))[field] if field else H.plain(d.text(source, file))) or sys.exit(f"{source}/{file} no longer states its terms as they were read; read the page again before building")
    KB_DOCS, IPR, GO, BIG_PI = F.KB_DOCS, F.IPR, F.GO, F.BIG_PI
    must(KB_DOCS, "terms_uniprot_license.json", r"We have chosen to apply the \[?Creative Commons Attribution 4\.0 International \(CC BY 4\.0\) License\]?(\([^)]*\))? to all copyrightable parts of our databases", "content")
    must(IPR, "terms_interpro_license.html", r"All of the InterPro, Pfam, PRINTS and SFLD downloadable data provided on the InterPro website is freely available under CC0 1\.0 Universal")
    must(GO, "go_citation_policy.html", r"licensed under the Creative Commons Attribution 4\.0 Unported License")
    must(FLY_KB, "help_arba.json", r"ARBA", "content")
    must(*H.SAVED_TERMS["prosite"], r"distributed under the Creative Commons Attribution-NonCommercial-NoDerivatives \(CC BY-NC-ND 4\.0\) License")
    must(*H.SAVED_TERMS["hamap"], r"distributed under the Creative Commons Attribution \(CC BY 4\.0\) License")
    for tool in ("tmhmm", "signalp", "targetp"):
        must(*H.SAVED_TERMS[tool], rf"ACADEMIC SOFTWARE LICENSE AGREEMENT FOR END-USERS AT PUBLICLY FUNDED ACADEMIC, EDUCATION OR RESEARCH INSTITUTIONS FOR THE USE OF {tool}")
    must(*H.SAVED_TERMS["phobius"], r"Phobius is intended for academic users only")
    must(BIG_PI, "gpi_server.html", r"big-PI Predictor")
    must(KB_DOCS, "help_transmem.json", r"predicted by the application of the predictive tools TMHMM, Memsat, Phobius and the hydrophobic moment plot method", "content")
    must(KB_DOCS, "help_signal.json", r"predicted by the application of the predictive tools Phobius, Predotar, SignalP and TargetP", "content")
    must(KB_DOCS, "help_transit.json", r"predicted by the application of the predictive tools \[Mitofates\]\([^)]*\), \[Predotar\]\([^)]*\) and \[TargetP\]\([^)]*\)", "content")

    adopt()
    vocabulary = H.Vocabulary(d)
    text = re.sub(r"\s+", " ", re.sub(r"\nDE   ", " ", d.text(KB_DOCS, "subcell.txt")))
    for sentence in ("The plasmodesma (plural plasmodesmata) is a plasma membrane-lined channel that crosses the cell wall between two adjacent plant cells", "formed by the cytoplasms of individual cells connected by plasmodesmata"):
        if sentence not in text:
            raise SystemExit(f"UniProt's vocabulary of places no longer says: {sentence}")
    every, read = F.read_entries(d, vocabulary)
    raw = {item["primaryAccession"]: item for item in json.loads(d.text(KB, PLACES_FILE))["results"]}
    release = d.entry(KB, PLACES_FILE)["x_uniprot_release"]
    proteome = json.loads(d.text(KB, f"proteome_{PROTEOME}.json"))
    total = {name: d.total(KB, f"count_{name}.json") for name in ("all", "reviewed", "unreviewed", "reviewed_with_place", "unreviewed_with_place")}
    if any(d.entry(KB, file)["x_uniprot_release"] != release for file in (SIGNATURES_FILE, "count_all.json", "count_reviewed.json", "count_unreviewed.json")) or vocabulary.release != release:
        raise SystemExit("the downloads from UniProt are not of one release; fetch them again")
    if total["all"] != len(every) or total["reviewed"] != sum(1 for e in every.values() if e["reviewed"]) or total["reviewed"] + total["unreviewed"] != total["all"] or proteome["proteinCount"] != total["all"] or proteome["taxonomy"]["taxonId"] != TAXON:
        raise SystemExit(f"the entries read do not add up to UniProt's own counts: {total}")
    if total["reviewed_with_place"] != read["reviewed, states a place"] or total["unreviewed_with_place"] != read["unreviewed, states a place"]:
        raise SystemExit(f"the entries that state a place are not as many as UniProt's search finds: {dict(read)} against {total}")

    # --- the catalogue: one protein for each gene, as UniProt's gene-by-gene set gives it ---------------
    chosen = F.canonical(d)
    missing = [accession for accession in chosen if accession not in every]
    if missing:
        raise SystemExit(f"{len(missing)} proteins of the gene-by-gene set are not entries of the proteome as fetched ({missing[:5]}); fetch both again")
    entries = {accession: every[accession] for accession in chosen}
    of_gene = defaultdict(set)
    for accession, entry in every.items():
        for gene_id in entry["flybase"]:  # the field holds the gene identifiers of the database named in F.GENE_DB: here Araport's
            of_gene[gene_id].add(accession)
    together = {accession: len(set().union({accession}, *(of_gene[gene_id] for gene_id in entry["flybase"]))) for accession, entry in entries.items()}
    covered = set().union(set(entries), *(of_gene[gene_id] for entry in entries.values() for gene_id in entry["flybase"]))
    stated = {
        "entries": total["all"], "reviewed": total["reviewed"], "unreviewed": total["unreviewed"], "genes": proteome["geneCount"],
        "shown": len(entries), "shown_reviewed": sum(1 for e in entries.values() if e["reviewed"]), "shown_unreviewed": sum(1 for e in entries.values() if not e["reviewed"]),
        "further": total["all"] - len(entries), "further_tied_to_a_shown_gene": len(covered) - len(entries), "no_araport_gene": sum(1 for e in entries.values() if not e["flybase"]),
    }
    if abs(stated["shown"] - stated["genes"]) > 0.01 * stated["genes"]:
        raise SystemExit(f"the gene-by-gene set holds {stated['shown']:,} proteins and the proteome counts {stated['genes']:,} genes")
    filing = H.Filing(d, entries)
    placed = {accession: H.place(entry, vocabulary) for accession, entry in entries.items()}
    gene = lambda accession: entries[accession]["gene"] or accession
    order = lambda accessions: sorted(set(accessions), key=lambda a: H.natural(gene(a).lower()))
    by_gene = lambda accessions: [gene(a) for a in order(accessions)]
    at_plasmodesma = [a for a, entry in entries.items() if any(statement["name"] == "Plasmodesma" for statement in entry["statements"])]

    # --- the atlas: the families behind Cells' units, asked of this organism ---------------------------
    carriers = defaultdict(list)
    for accession, found in filing.signatures.items():
        for signature in found:
            carriers[signature].append(accession)
    human_lines = d.text(F.HUMAN_KB, "uniprotkb_UP000005640_reviewed_signatures.tsv.gz").splitlines()[1:]
    human_signatures = {line.split("\t")[0]: set(line.split("\t")[1].split(";")) for line in human_lines}
    signature_name = lambda signature: filing.names[signature]["name"]
    carried = lambda family: order(accession for signature in family["signatures"] for accession in carriers.get(signature, []))
    said = lambda families: f"{listed(family['of'] for family in families)} ({', '.join(signature for family in families for signature in family['signatures'])})"
    units, unit_of, beside = {}, defaultdict(set), {}
    for unit in snapshot["units"]:
        spec = M.UNITS[unit["id"]]
        if spec.get("finding"):
            units[unit["id"]] = {"finding": spec["finding"], "note": F.NOTHING[unit["id"]], "products": []}
            continue
        families = [(key, M.FAMILIES[key]) for key in spec["parts"]]
        candidates = [product["human_uniprot"] for product in unit.get("products") or [] if product.get("human_uniprot")]
        for _, family in families:
            if family.get("human", True) and not any(set(family["signatures"]) & human_signatures.get(candidate, set()) for candidate in candidates):
                raise SystemExit(f"{unit['id']}: none of its human candidates carries the signature of {family['of']}; the question is not the unit's")
        own = [family for key, family in families if key not in E.ACCESSORY and family.get("human", True)]
        other = [family for key, family in families if key not in E.ACCESSORY and not family.get("human", True)]
        going_with = [family for key, family in families if key in E.ACCESSORY]
        if any(carried(family) for family in own):
            finding, shown = "found", [family for family in [*own, *going_with] if carried(family)]
        elif any(carried(family) for family in other):
            finding, shown = "different family", [family for family in other if carried(family)]
        else:
            finding, shown = "none found", []
        products, listed_here = [], set()
        for family in shown:
            for accession in carried(family):
                if accession in listed_here:
                    continue
                listed_here.add(accession)
                entry = entries[accession]
                which = [signature for signature in family["signatures"] if accession in carriers.get(signature, [])]
                products.append({
                    "name": entry["name"], "gene": entry["gene"] or None, "role": family["of"], "ids": [{"db": "uniprot", "id": accession}], "length": entry["length"],
                    "evidence": "reviewed entry" if entry["reviewed"] else "family signature",
                    "evidence_note": f"Its {'reviewed' if entry['reviewed'] else 'unreviewed'} UniProtKB entry carries {', '.join(which)} ({'; '.join(signature_name(s) for s in which)}). A signature says the family, not which member does the unit's work.",
                    "citation": None,
                })
                unit_of[accession].add(unit["id"])
        hits = order(listed_here)
        if finding == "found":
            note = f"{plural(len(hits), 'protein')} of its {len(entries):,} carr{'ies' if len(hits) == 1 else 'y'} the signature of {said(shown)}: {some(by_gene(hits))}. Each is a candidate by its family alone: no source read here says which of them does the unit's work in the plant."
        elif finding == "different family":
            note = f"None of its {len(entries):,} proteins carries the signature of {said(own)}, the family the engine's law names. {plural(len(hits), 'protein')} carr{'ies' if len(hits) == 1 else 'y'} that of {said(shown)}, the other family this machine is asked for: {some(by_gene(hits))}."
        else:
            only = [(family, carried(family)) for family in going_with if carried(family)]
            aside = " ".join(f"{plural(len(found), 'protein')} ({some(by_gene(found))}) carr{'ies' if len(found) == 1 else 'y'} that of {family['of']}, which go with the machine and make none by themselves: no candidate for the unit." for family, found in only)
            note = f"None of its {len(entries):,} proteins carries the signature of {said([*own, *other])}. {aside} The unit's human candidates carry {'them' if len(own) + len(other) > 1 or len(own[0]['signatures']) > 1 else 'it'}, so the search finds the family where it exists.".replace("  ", " ")
            if any(key in ("connexin", "innexin") for key, _ in families):
                note += f" A plant's cells are joined in another way: by plasmodesmata, channels lined by the cell membrane that cross the wall between two cells (UniProt's vocabulary). {plural(len(at_plasmodesma), 'protein')} of the catalogue {'is' if len(at_plasmodesma) == 1 else 'are'} stated to be there; they stand on the cell membrane's shelf."
            for family, found in only:
                for accession in found:
                    beside[accession] = family["of"]
        units[unit["id"]] = {"finding": finding, "note": note, "products": products}
    if set(units) != {unit["id"] for unit in snapshot["units"]}:
        raise SystemExit("the units of the atlas are not the units of the inventory")
    unit_ids = {accession: sorted(found, key=H.natural) for accession, found in unit_of.items()}

    # --- the lines of the shelves -----------------------------------------------------------------------
    lines, alone, rest = H.make_lines(entries, placed, filing, unit_ids)
    sequence = [protein for line in [*lines, *alone, *rest] for protein in line["proteins"]]
    if len(sequence) != len(entries) or len(set(sequence)) != len(entries):
        raise SystemExit("a protein is filed twice or not at all")
    SIDES, NO_SHELF = H.SIDES, H.NO_SHELF
    key = lambda shelf: NO_SHELF if shelf is None else shelf
    shelf_counts = {name: {side: 0 for side in SIDES} for name in [*H.SHELF_IDS, NO_SHELF]}
    for item in placed.values():
        shelf_counts[key(item["shelf"])][item["side"]] += 1
    counts = {side: sum(found[side] for found in shelf_counts.values()) for side in SIDES}
    bases = Counter((item["side"], item["basis"]) for item in placed.values())
    rules = Counter(item["rule"] for item in placed.values())
    evidence = Counter(item["evidence"] for item in placed.values() if item["evidence"])

    def sure(accession):
        item = placed[accession]
        return "predicted from a segment or a signal" if item["basis"] == "predicted" else "not known" if item["basis"] == "none" else {"experiment": "stated, on an experiment", "similarity": "stated, by likeness", "curator": "stated, by a curator's inference", "rule": "stated, by a rule", H.NOT_GIVEN: "stated, with no evidence given"}[item["evidence"]]
    kinds = ["stated, on an experiment", "stated, by likeness", "stated, by a curator's inference", "stated, with no evidence given", "stated, by a rule", "predicted from a segment or a signal", "not known"]
    how_sure = {kind: {"reviewed": 0, "unreviewed": 0} for kind in kinds}
    for accession in entries:
        how_sure[sure(accession)]["reviewed" if entries[accession]["reviewed"] else "unreviewed"] += 1
    # What a plant cell adds, counted apart: the plastid's two levels, the vacuole, the wall and the plasmodesmata.
    first = lambda accession: placed[accession]["where"]["name"] if placed[accession]["where"] else None
    on = lambda shelf, side: shelf_counts[shelf][side]
    plant = {
        "the plastid's envelope: in either of its two membranes": on("plastid", "in"),
        "the plastid's envelope, inside: free in the stroma, or within the plastid": on("plastid", "inside"),
        "the plastid's envelope, outside: on its cytoplasmic face": on("plastid", "outside"),
        "in the plastid, with no part of it named: beside the envelope's shelf, side not known": on("plastid", "not known"),
        "the thylakoid membrane: in it": on("thylakoid", "in"),
        "the thylakoid membrane, inside: in the lumen": on("thylakoid", "inside"),
        "the thylakoid membrane, outside: held at it and facing the stroma": on("thylakoid", "outside"),
        "at the thylakoid, side not known": on("thylakoid", "not known"),
        "the vacuole's membrane: in it": on("vacuole", "in"),
        "the vacuole, inside": on("vacuole", "inside"),
        "the vacuole's membrane, outside: on its cytoplasmic face": on("vacuole", "outside"),
        "at the vacuole, side not known": on("vacuole", "not known"),
        "in the wall: the cell membrane's shelf, outside": sum(1 for a in entries if first(a) == "Cell wall"),
        "in the space outside the membrane (the apoplast): the cell membrane's shelf, outside": sum(1 for a in entries if first(a) == "Apoplast"),
        "at the plasmodesmata, by any statement of the entry: the cell membrane's shelf": len(at_plasmodesma),
    }
    family_total = Counter(filing.family.values())
    distinct = len({line["id"] for line in lines})
    lone_families = sum(1 for size in family_total.values() if size <= H.LONE_UP_TO)
    shelves = []
    for shelf in SHELVES:
        here_lines = [line for line in lines if line["shelf"] == shelf["id"]]
        here = sum(len(line["proteins"]) for line in alone if line["shelf"] == shelf["id"])
        shelves.append({**shelf, **({"note": SHELF_NOTES[shelf["id"]]} if shelf["id"] in SHELF_NOTES else {}), "proteins": sum(shelf_counts[shelf["id"]].values()), "families": len(here_lines) + here, "lines": len(here_lines), "lone": here, "no_family": sum(len(line["proteins"]) for line in rest if line["shelf"] == shelf["id"])})
    none = [line for line in lines if line["shelf"] is None]
    here = sum(len(line["proteins"]) for line in alone if line["shelf"] is None)
    no_shelf = {"proteins": sum(shelf_counts[NO_SHELF].values()), "families": len(none) + here, "lines": len(none), "lone": here, "no_family": sum(len(line["proteins"]) for line in rest if line["shelf"] is None)}
    groups = []
    for group in H.DISTRICT_ORDER:
        asked = next((terms for key_, _, terms in H.DISTRICTS if key_ == group), None)
        said_from = "Gene Ontology terms: " + ", ".join(f"{name} ({term})" for term, name in asked) if asked else "The line's proteins carry Gene Ontology terms, and none of the districts' terms" if group == H.OTHER_DISTRICT[0] else "The line's proteins carry no Gene Ontology term"
        here_lines = [line for line in lines if line["group"] == group]
        groups.append({"id": group, "label": H.DISTRICT_LABEL[group], "from": said_from, "lines": len(here_lines), "proteins": sum(len(line["proteins"]) for line in here_lines), "lone": sum(len(line["proteins"]) for line in alone if line["group"] == group)})
    first_places = Counter(item["where"]["name"] for item in placed.values() if item["where"])
    used = {statement["name"] for entry in entries.values() for statement in entry["statements"]}
    place_rows = []
    for name in sorted(used, key=lambda name: (-first_places[name], name)):
        shelf, kind, how, under = vocabulary.resolve(name)
        place_rows.append([vocabulary.by_name[name]["accession"], vocabulary.by_name[name]["path"], shelf, kind, how, under, first_places[name]])
    codes_used = {part for entry in entries.values() for statement in entry["statements"] for part in H.code(statement).split(".")}
    place_words = {term["accession"][3:]: term["path"] for term in sorted(vocabulary.terms.values(), key=lambda term: term["accession"]) if term["accession"][3:] in codes_used}

    resting, rule_ids = H.account(entries, placed)
    if set(resting) - F.OWNERS:
        raise SystemExit(f"a placement rests on a rule system or a program this tool does not name: {sorted(set(resting) - F.OWNERS)}")
    of = lambda owner, what="placements": resting.get(owner, {}).get(what, 0)
    PLACE, SPANS, FACE = "the stated place", "the statement that it spans the membrane", "the stated face"
    FROM_SEGMENTS, FROM_SIGNAL = "a side read from its segments", "a side read from its signal peptide"
    named = lambda owner: f"{of(owner):,} ({of(owner, FROM_SEGMENTS):,} by a side read from segments, {of(owner, FROM_SIGNAL):,} from a signal peptide, {of(owner, SPANS) + of(owner, PLACE) + of(owner, FACE):,} behind a statement)"
    # A place stated on a sequence analysis that names no program: where the entry carries a transit
    # peptide given by sequence analysis alone, UniProt's help names the three programs behind it.
    analysed = [a for a, item in placed.items() if item["where"] and item["where"]["behind"] == (H.ANALYSIS,) and entries[a]["segments_behind"] != (H.ANALYSIS,) and entries[a]["signal_behind"] != (H.ANALYSIS,)]
    transit_only = lambda a: (lambda found: bool(found) and all(e["evidenceCode"] == "ECO:0000255" and not e.get("source") for f in found for e in f.get("evidences", [{"evidenceCode": ""}])))([f for f in raw[a].get("features", []) if f["type"] == "Transit peptide"])
    by_transit = [a for a in analysed if transit_only(a)]
    if len(analysed) != of("unnamed analysis", PLACE):
        raise SystemExit(f"the places stated on an unnamed analysis are counted two ways: {len(analysed)} and {of('unnamed analysis', PLACE)}")
    predictors = "TMHMM, Memsat, Phobius and a hydrophobic moment plot for the segments; Phobius, Predotar, SignalP and TargetP for the signal peptides"
    ruling = "By the project's rule (the user, 15 November 2026), a value stands on the terms of the database it was read from, and the tool behind it is named and counted: the project's rule, not a legal opinion."
    for paper in PAPERS:
        E.paper_text(d, paper)
    made = d.last_day()
    header = {
        "format": H.SHELF_FORMAT, "species": SPECIES_ID, "made": made,
        "from": f"UniProtKB release {release}: the reference proteome {PROTEOME} of Arabidopsis thaliana, {stated['entries']:,} entries ({stated['reviewed']:,} reviewed, {stated['unreviewed']:,} unreviewed) for {stated['genes']:,} genes. One protein is shown for each gene, the one that UniProt's own gene-by-gene set of the proteome gives: {stated['shown']:,} proteins, {stated['shown_reviewed']:,} with a reviewed entry and {stated['shown_unreviewed']:,} with an unreviewed one. The proteome's other {stated['further']:,} entries are further forms of the same genes; each protein counts its gene's entries in the mark 'entries'.",
        "from_counts": stated,
        "predicted": False,
        "curated": {"note": "A reviewed entry was written by a curator; an unreviewed one was annotated automatically, by rule systems and prediction programs. The table says, for the proteins shown, what stands behind each one's place.", "columns": ["what stands behind the place", "reviewed", "unreviewed"], "rows": [[kind, how_sure[kind]["reviewed"], how_sure[kind]["unreviewed"]] for kind in kinds]},
        "shelves": shelves, "no_shelf": no_shelf,
        "plant": {"rule": "The plastid has two levels. Its envelope, two membranes standing as one shelf, has the stroma inside it and the cytoplasm beyond: a protein in either membrane is in the envelope, and a protein free in the stroma stands on that shelf, inside. The thylakoid membrane lies in the stroma, with its lumen inside and the stroma beyond: a protein held at it and facing the stroma stands on the thylakoid's shelf, outside. The vacuole has a shelf of its own. A protein of the wall or of the space outside the cell membrane stands on the cell membrane's shelf, outside, as a secreted protein does, and so does one of the plasmodesmata, which join a plant's cells.", "counts": plant},
        "groups": groups,
        "groups_from": "A protein's Gene Ontology terms are those InterPro maps to any of its signatures and those UniProt gives its entry. With every broader term (by the ontology's kind-of and part-of links), the protein falls in the first district, in the order listed, one of whose terms it carries. A family's line stands in the district most of its classed members on that shelf fall in; of equal counts, the first listed. A protein that is the only member of its family stands in its own district. A part of no_family stands in a district only if more than half of all its members on that shelf fall there. The choice of the districts' terms and their order is the viewer's, and is the same for every species; the terms were chosen for animal cells, and a plant's own work (photosynthesis, the wall) falls under the districts they name.",
        "family_from": f"A family is an InterPro entry of the type Family (InterPro {filing.release}). A protein is filed under the narrowest family among the InterPro entries UniProt gives it: one that is not a broader kind of another it carries, by InterPro's tree of entries. Where several unrelated families remain ({filing.several:,} proteins), it is the deepest in that tree, then the one fewest proteins of this catalogue are in, then the first by accession. This is the rule of every species' file, so a family has the same id in each.",
        "family_columns": H.FAMILY_COLUMNS,
        "family_notes": {
            "lines": "A family has one line for each shelf that holds members of it, and one with a null shelf for its members that are on no shelf. A line is identified by id and shelf together; side, group, count, sides, file, at and units are of its members on that shelf alone.",
            "side": "The side most of the line's members sit on; of equal counts, a membrane first.",
            "units": "The inventory units for which a member on this line carries the family's signature: candidates by family alone.",
            "total": "The family's members on every shelf and on none.",
            "counts": "distinct_families is the number of families that have lines; families_in_all counts also the families of one, whose proteins are under 'lone'.",
        },
    }
    lone_sides = Counter(side for line in alone for side, n in line["sides"].items() for _ in range(n))
    lone = {"label": H.LONE_LABEL, "count": sum(len(line["proteins"]) for line in alone), "families": lone_families, "sides": H.ordered_sides(lone_sides), "parts_from": f"A family with a single member in this catalogue does not open, so it has no line among the families: {lone_families:,} families of one. Their proteins are listed here together, one part for each shelf, district and side, and each names its family in its mark 'family'. A part is not a family.", "part_columns": H.PART_COLUMNS}
    no_family = {"label": "No family assigned", "count": len(filing.part), "sides": H.ordered_sides(Counter(placed[protein]["side"] for protein in filing.part)), "parts_from": "A protein with no family is filed under one part. If it carries an InterPro entry of the type Homologous superfamily, the part is that superfamily: a wider grouping than a family, by shared structure. Of several superfamilies it is the one fewest proteins of this catalogue carry, then the first by accession. The other two parts hold the proteins with only a domain, repeat or site signature, and those with no signature at all. A part has one line for each shelf, as a family has.", "part_columns": H.PART_COLUMNS}
    files = sorted({line["file"] for line in [*lines, *alone, *rest]})
    tail = {
        "member_columns": ["id", "label", "gene", "side", "basis", "length", "unit", "marks"],
        "members_from": {
            "table": f"data/proteins/{SPECIES_ID}/{H.TABLE_FILE}", "format": H.MEMBERS_FORMAT,
            "order": "The table's lines are the members in order: every line of the families as listed here, then every part of 'lone', then every part of 'no_family'; within each, by gene name. A line's members are the next 'count' lines of the table. For a family's line and for a part of no_family, 'under' is its id and 'shelf' its shelf (empty for none); for a part of 'lone', 'under' is the protein's own family and 'family' that family's name.",
            "files": f"A file holds the members of consecutive lines: a new file begins where the next line would take it past {H.MEMBERS_PER_FILE:,} members, so a line is never split. 'file' names the file and 'at' the first and one past the last of its members there.",
            "places": "In the table a stated place is written with UniProt's identifiers, without their prefix: the place, then the topology and the face where the entry states them, joined by a full stop. 'place_words' gives the words of each.",
            "letters": {"basis": {letter: word for word, letter in H.BASIS_LETTER.items()}, "evidence": {letter: word for word, letter in H.EVIDENCE_LETTER.items()}, "seen": {str(level): H.SEEN[level] for level in sorted(H.SEEN)}},
            "step": f"python3 {TOOL} members --out DIR writes the files from the two files.",
        },
        "side_notes": {
            "stated": "The protein's UniProtKB entry states where it is, and the first place it states decides the shelf and the side. For a reviewed entry the statement is a curator's, and the mark 'evidence' says what stands behind it: an experiment, likeness to another protein, the curator's inference, or a rule. For an unreviewed entry no curator wrote it: the statement was made by one of UniProt's rule systems, and its evidence is 'rule'.",
            "predicted": f"Read from the entry's own features, where its words do not give the side. A membrane-spanning segment puts the protein in a membrane; a signal peptide with no such segment puts it on the side away from the cytoplasm. Where the entry states no place, the protein stands on the shelf of a membrane that is not named. A transit peptide, which sends a protein into a plastid or a mitochondrion, is not read here: where a curator states such a place on it, the place is stated. In a reviewed entry UniProt's pages name the predictors behind the predicted features: {predictors}. In an unreviewed entry the program is named on each feature. Each is named among the sources, with its terms and what rests on it. {ruling}",
            "none": "The entry states a membrane or a place and not the side (the protein then stands apart beside that shelf, with the place in its mark 'where'), or it states no place of the cell and carries no membrane-spanning segment and no signal peptide (the protein is then on no shelf). Nothing is placed by guess.",
        },
        "placed_by": [{"rule": rule, "basis": basis, "what": what, "proteins": rules[rule]} for rule, basis, what in H.RULES_USED],
        "place_kinds": H.KINDS,
        "place_columns": ["id", "words", "shelf", "names", "resolved", "under", "first"],
        "place_notes": "Every place the entries state, in UniProt's words, with the shelf and what the place names against its membrane (place_kinds), how the table's line was reached and which of the table's terms it rests on, and how many proteins it places as the statement that decided.",
    }
    marks = {
        "reviewed": {"label": "Curated entry", "values": [True, False], "measured": False, "note": "Whether the protein's UniProtKB entry is reviewed, written by a curator, or unreviewed, annotated automatically.", "source": "UniProt"},
        "entries": {"label": "Entries for its gene", "values": "number", "measured": False, "note": "The proteome's entries for the same gene, by the Araport gene that UniProt gives each entry: this protein's own and the further forms of the gene. The marker stands for the one UniProt's gene-by-gene set names.", "source": "UniProt"},
        "isoforms": {"label": "Isoforms described", "values": "number", "measured": False, "note": "The canonical sequence and the other sequences its own entry describes.", "source": "UniProt"},
        "seen": {"label": "Evidence that the protein exists", "values": [H.SEEN[level] for level in sorted(H.SEEN)], "measured": False, "note": "UniProt's level of evidence for the entry: at protein level, at transcript level, inferred from homology, predicted, or uncertain.", "source": "UniProt"},
        "evidence": {"label": "What stands behind the stated place", "values": [word for word, _, _ in H.EVIDENCE] + [H.NOT_GIVEN], "measured": False, "note": "From UniProt's evidence codes on the statement: an experiment in a paper the entry cites; likeness to a protein of which it is known; a curator's inference; a rule (a family rule or a sequence model that a curator applied, or, in an unreviewed entry, one of UniProt's automatic rule systems); not given, an older curated statement. Of several, the first in this order.", "source": "UniProt"},
        "where": {"label": "Stated place", "values": "text", "measured": False, "note": "The statement that decided the shelf, in UniProt's words: the place, then the topology and the face where the entry states them.", "source": "UniProt"},
        "also": {"label": "Also stated", "values": "text", "measured": False, "note": "The entry's other statements of place, in order and in UniProt's words.", "source": "UniProt"},
        "family": {"label": "Family, of which it is the only member here", "values": "text", "measured": False, "note": "The InterPro family's accession and name, for a protein listed among the only members of their families.", "source": "InterPro"},
        "of": {"label": "Stated for", "values": "text", "measured": False, "note": "The named form of the protein that the place is stated for, where the entry states none for the protein as a whole.", "source": "UniProt"},
    }
    cite_uniprot = "The UniProt Consortium, UniProt: the Universal Protein Knowledgebase in 2025, Nucleic Acids Res. 53:D609-D617 (2025)"
    cite_interpro = "Blum and others (2025) InterPro: the protein sequence classification resource in 2025. Nucleic Acids Res 53:D444-D456."
    terms_day = lambda name: d.day(*H.SAVED_TERMS[name])
    own_said = "; ".join(f"{owner} {of(owner):,}" for owner in F.OWN_SYSTEMS if of(owner))
    sources = [
        {"name": "UniProt", "url": "https://www.uniprot.org/", "release": release, "accessed": d.day(KB, PLACES_FILE), "licence": "CC BY 4.0", "class": "permissive", "cite": cite_uniprot,
         "holds": f"for each entry of the plant's reference proteome: its name, gene, Araport gene, length and level of evidence, the places it states with the evidence for each, its membrane-spanning segments, signal peptide and anchors, and the InterPro entries and Gene Ontology terms UniProt gives it; the gene-by-gene set of the proteome; and UniProt's vocabulary of places. The programs and rule systems of other owners behind its statements are sources below. Placements that rest on UniProt's own automatic systems or on an analysis for which it names no program: {own_said or 'none'}. Of the {of('unnamed analysis', PLACE):,} places stated on such an analysis, {len(by_transit):,} are in entries whose transit peptide is given by sequence analysis alone; UniProt's help names three programs for those"},
        {"name": "InterPro", "url": "https://www.ebi.ac.uk/interpro/", "release": filing.release, "accessed": d.day(IPR, "entry.list"), "licence": "CC0 1.0", "class": "permissive", "cite": cite_interpro, "holds": "the type and name of each entry, the tree of broader and narrower entries, and the mapping of entries to Gene Ontology terms"},
        {"name": "Gene Ontology", "url": "https://geneontology.org/", "release": filing.ontology, "accessed": d.day(GO, "go-basic.obo"), "licence": "CC BY 4.0", "class": "permissive", "cite": H.ontology_citation(d), "holds": "the names of terms and which term is a kind or a part of which; no term's text is copied beyond the names of the districts' terms"},
        {"name": "PROSITE", "url": "https://prosite.expasy.org/prosite_license.html", "licence": "CC BY-NC-ND 4.0; commercial users are asked to pay a yearly licence fee", "class": "non-commercial", "accessed": terms_day("prosite"), "through": "UniProt",
         "holds": f"Nothing was downloaded from it but its statement of terms, and nothing of it is copied. Its rules (ProRule) are named in UniProt's entries as what stands behind a statement. {of('PROSITE-ProRule'):,} placements rest on them alone: {of('PROSITE-ProRule', PLACE):,} by the statement of place that decides the shelf ({len(rule_ids.get('PROSITE-ProRule', {})):,} rules), {of('PROSITE-ProRule', SPANS):,} by the statement that the protein spans the membrane, and {of('PROSITE-ProRule', FROM_SEGMENTS) + of('PROSITE-ProRule', FROM_SIGNAL):,} by a side read here from a feature that a rule gives."},
        {"name": "HAMAP", "url": "https://hamap.expasy.org/hamap_about.html", "licence": "CC BY 4.0", "class": "permissive", "accessed": terms_day("hamap"), "through": "UniProt",
         "holds": f"Nothing was downloaded from it but its statement of terms. Its family rules are named in UniProt's entries as what stands behind a statement: {of('HAMAP-Rule'):,} placements rest on them alone."},
        {"name": "TMHMM", "url": "https://services.healthtech.dtu.dk/services/TMHMM-2.0/", "licence": H.DTU_LICENCE, "class": "non-commercial", "accessed": terms_day("tmhmm"), "through": "UniProt",
         "holds": f"{H.NOT_RUN} {H.FOUR_SEGMENTS}. In reviewed entries {of('segments'):,} placements rest on segments that an entry gives by sequence analysis alone ({of('segments', FROM_SEGMENTS):,} read here from such segments, {of('segments', SPANS):,} statements of spanning, {of('segments', PLACE):,} stated places). In unreviewed entries UniProt names the program on each feature: TMHMM on {named('TMHMM')}."},
        {"name": "Phobius", "url": "https://phobius.sbc.su.se/download", "licence": "For academic users only: the program may be used for private study, education or nonprofit research, and other users are asked to write to its author. The terms are of the program: they do not speak of predictions made with it", "class": "non-commercial", "accessed": terms_day("phobius"), "through": "UniProt",
         "holds": f"{H.NOT_RUN} In reviewed entries, one of the four methods for segments and of the four for signal peptides: the placements counted under TMHMM ({of('segments'):,}) and SignalP ({of('signal'):,}). In unreviewed entries UniProt names it on each feature: {named('Phobius')}."},
        {"name": "SignalP", "url": "https://services.healthtech.dtu.dk/services/SignalP-5.0/", "licence": H.DTU_LICENCE, "class": "non-commercial", "accessed": terms_day("signalp"), "through": "UniProt",
         "holds": f"{H.NOT_RUN} {H.FOUR_SIGNALS}. In reviewed entries {of('signal'):,} placements rest on a signal peptide that an entry gives by sequence analysis alone. In unreviewed entries UniProt names the program on each feature: SignalP on {named('SignalP')}."},
        {"name": "TargetP", "url": "https://services.healthtech.dtu.dk/services/TargetP-2.0/", "licence": H.DTU_LICENCE, "class": "non-commercial", "accessed": terms_day("targetp"), "through": "UniProt", "holds": f"{H.NOT_RUN} {H.FOUR_SIGNALS}. The placements are those counted under SignalP for reviewed entries ({of('signal'):,})."},
        {"name": "Memsat", "url": "https://www.uniprot.org/help/transmem", "licence": "Terms not read: UniProt's help names Memsat without a version or an address, so no page of terms could be tied to the program it runs", "class": "no stated terms", "accessed": d.day(KB_DOCS, "help_transmem.json"), "through": "UniProt", "holds": f"Nothing was downloaded from it. {H.FOUR_SEGMENTS}. The placements are those counted under TMHMM for reviewed entries ({of('segments'):,})."},
        {"name": "Predotar", "url": "https://www.uniprot.org/help/signal", "licence": "Terms not read: the program's own page answers this tool with a check for a browser, so its terms could not be read", "class": "no stated terms", "accessed": d.day(KB_DOCS, "help_signal.json"), "through": "UniProt", "holds": f"Nothing was downloaded from it. {H.FOUR_SIGNALS}. The placements are those counted under SignalP for reviewed entries ({of('signal'):,})."},
        {"name": "big-PI", "url": "https://mendel.imp.ac.at/gpi/gpi_server.html", "licence": "No open licence stated: the predictor's own page gives no terms of use", "class": "no stated terms", "accessed": d.day(BIG_PI, "gpi_server.html"), "through": "UniProt",
         "holds": f"Nothing was downloaded from it but its own page, and the program was not run here. The predictor that UniProt's help names for the GPI anchors it predicts. {of('big-PI'):,} placements rest on a GPI anchor that the entry states on a sequence analysis alone: such an anchor puts the protein on the face away from the cytoplasm."},
    ]
    sources = [source for source in sources if source["name"] != "big-PI" or of("big-PI")]
    closing = {"marks": marks, "counts": counts, "shelf_counts": shelf_counts, "by_basis": {side: {basis: bases[side, basis] for basis in ("stated", "predicted", "none") if bases.get((side, basis))} for side in SIDES}, "by_evidence": {word: evidence.get(word, 0) for word in [word for word, _, _ in H.EVIDENCE] + [H.NOT_GIVEN]}, "sources": sources}

    compact = H.compact
    rows = lambda items, pad=" ": "[\n" + ",\n".join(f"{pad} " + compact(item) for item in items) + f"\n{pad}]"
    nested = lambda block, items: json.dumps(block, indent=1, ensure_ascii=False).replace("\n", "\n ")[:-3] + ',\n  "parts": ' + rows(items, "  ") + "\n }"
    body = json.dumps(header, indent=1, ensure_ascii=False)[:-2]
    body += ',\n "families": ' + rows([H.line_row(line, H.FAMILY_COLUMNS) for line in lines])
    body += f',\n "distinct_families": {distinct},\n "family_lines": {len(lines)},\n "families_in_all": {len(family_total)}'
    body += ',\n "lone": ' + nested(lone, [H.line_row(line, H.PART_COLUMNS) for line in alone])
    body += ',\n "no_family": ' + nested(no_family, [H.line_row(line, H.PART_COLUMNS) for line in rest])
    body += "," + json.dumps(tail, indent=1, ensure_ascii=False)[1:-2]
    body += ',\n "places": ' + rows(place_rows)
    body += ',\n "place_words": ' + json.dumps(place_words, ensure_ascii=False, separators=(", ", ": "))
    body += "," + json.dumps(closing, indent=1, ensure_ascii=False)[1:] + "\n"
    json.loads(body)

    lone_of = {protein for line in alone for protein in line["proteins"]}
    table_rows = []
    for protein in sequence:
        entry, item = entries[protein], placed[protein]
        under = filing.family.get(protein) or filing.part[protein]
        table_rows.append([
            protein, entry["gene"], entry["name"], str(entry["length"]), str(entry["isoforms"]), str(entry["seen"]), under, item["shelf"] or "", item["side"], H.BASIS_LETTER[item["basis"]], H.EVIDENCE_LETTER[item["evidence"]] if item["evidence"] else "",
            H.code(item["where"]) if item["where"] else "", ",".join(H.code(statement) for statement in item["also"]), ";".join(unit_ids.get(protein, [])),
            filing.names[under]["name"] if protein in lone_of else "", entry["of"] or "", "1" if entry["reviewed"] else "0", str(together[protein]),
        ])
    for row in table_rows:
        if any("\t" in value or "\n" in value for value in row):
            raise SystemExit(f"{row[0]}: a value of the table holds a tab or a line break")
    table = "\n".join("\t".join(row) for row in [TABLE_COLUMNS, *table_rows]) + "\n"

    # --- the species file and its outlines ---------------------------------------------------------------
    findings = Counter(unit["finding"] for unit in units.values())
    found_units = {unit: [product["gene"] for product in found["products"]] for unit, found in units.items() if found["products"]}
    junctions = [units[unit]["finding"] for unit in ("U36", "U37", "U38")]
    pump = units["U39"]["finding"]
    if set(junctions) != {"none found"} or pump != "none found":
        raise SystemExit(f"the species file says the plant has no gap junctions and no sodium-potassium pump; the atlas finds {junctions} and {pump}")
    box_um = 47  # the width of the cylinder the paper uses for a palisade cell: twice its radius of 23.7 µm, rounded
    high_um = round(100e3 / box_um ** 2)  # the picture's choice: the height at which a square box of that width holds the paper's 100 pL
    plastid_um = round(2 * (3 * 93 / (4 * math.pi)) ** (1 / 3), 1)  # the width of a sphere of the paper's 93 fL
    species = {
        "format": "cells.visualizer.species@1", "id": SPECIES_ID, "label": LABEL, "organism": ORGANISM, "taxon": TAXON,
        "plain": f"A small flowering plant of the laboratory: {stated['genes']:,} genes in UniProt's reference proteome, with one protein shown for each. Its cells have a wall, a large vacuole and chloroplasts, and membranes that an animal cell lacks.",
        "group": "Plants", "order": 70, "default": False, "made": made,
        "modelled": {"state": "generic", "text": "Cells models a generic cell and a sheet of such cells, with laws that name the channels and pumps of animal cells. No plant cell is modelled, and the project's record names no model of this plant. The leaf and the rosette are placeholder outlines: nothing at those scales is simulated."},
        "levels": [
            {"id": "molecules"},
            {"id": "cell", "shape": {"kind": "prism", "sides": 4, "across_um": box_um, "height_um": high_um, "corner_um": 4},
             "note": f"The cell drawn is a box with a wall, for a cell of the leaf's upper layer (a palisade cell). It is {box_um} µm across, the width of the cylinder that one paper uses for such a cell, and {high_um} µm high: the picture's choice of the height at which a box of that width holds the 100 picolitres the paper gives. Its square outline is the picture's choice too. No plant cell is modelled.",
             "notes": [{"text": "A leaf cell, as a box with a wall"}, {"text": "Its square outline is the picture's choice", "roomy": True}], "sources": ["tolleter2024"], "fade_out_um": [280, 440]},
            {"id": "tissue", "shape": {"kind": "cell sheet", "rings": 6, "beyond": [[8, 0.34], [10, 0.2], [11, 0.1]]},
             "note": "The sheet stands for the one Cells simulates: a single layer of coupled cells. It is drawn packed in squares, as box-shaped cells stand side against side; that packing is the picture's choice, and the sheets Cells has run are joined in sixes. It stands for no particular tissue of the plant, and a plant's cells are joined by plasmodesmata, which the sheet does not model.",
             "notes": [{"text": "The sheet Cells simulates: a single layer of coupled cells", "short": "The simulated sheet"}], "fade_in_um": [240, 440]},
            {"id": "organ", "label": "Leaf", "shape": {"kind": "outline", "ref": SPECIES_ID, "parts": ["leaf"], "context": ["other leaves"]},
             "note": f"The outline drawn is one leaf of the rosette, as a placeholder. The leaf is the picture's choice of organ: it is what a visitor knows of the plant, and where its chloroplasts work. No leaf is modelled. The sheet of cells is drawn on the leaf so that the scales follow one another; it is not the leaf's tissue. The leaf is drawn {LEAF_UM // 1000} mm long and {LEAF_WIDE_UM // 1000} mm wide: the picture's choice of a blade whose area is near the 121 mm² that one paper gives for its reference leaf.",
             "sheet_mark": {"band": 0.02, "note": "The sheet, to scale: drawn on the leaf for the scales only"},
             "notes": [{"text": "A leaf: a placeholder outline"}, {"text": "The leaf's own cells are not modelled", "lift": -22, "roomy": True}], "sources": ["tolleter2024"]},
            {"id": "organism", "label": "Whole plant", "shape": {"kind": "outline", "ref": SPECIES_ID},
             "note": f"The outline drawn is a rosette of {LEAVES} leaves seen from above, as a placeholder. The sheet of cells is drawn on one leaf for the scales only. The number of leaves, their lengths and the rosette's width are the picture's choice: the paper's three-week-old rosette has 29 leaves, and no measurement of a rosette's width was read for this file. The plant's stem, flowers and roots are not drawn.",
             "sheet_mark": {"band": 0.02, "note": "The sheet, to scale", "roomy": True}, "notes": [{"text": "A rosette of leaves: a placeholder outline"}], "sources": ["tolleter2024"]},
        ],
        "cell": {
            "facts": [
                {"label": "Proteins", "value": f"{stated['genes']:,} genes in UniProt's reference proteome, with {stated['entries']:,} entries: {stated['reviewed']:,} reviewed by a curator and {stated['unreviewed']:,} annotated automatically. One protein is shown for each gene", "sources": ["uniprot"]},
                {"label": "A leaf cell's size", "value": "100 picolitres for a cell of the leaf's upper layer (a palisade cell) and 60 for one of the layer below, by one paper's atlas of the leaf, which takes the palisade cell as a cylinder of radius 23.7 µm", "sources": ["tolleter2024"]},
                {"label": "Chloroplasts", "value": "100 in a palisade cell, each of 93 femtolitres on average", "sources": ["tolleter2024"]},
                {"label": "Vacuole", "value": "the largest part of a leaf's cellular volume: 84%", "sources": ["tolleter2024"]},
                {"label": "Wall", "value": "150 nm thick on average, for the leaf's skin cells and inner cells", "sources": ["tolleter2024"]},
                {"label": "Leaf and rosette", "value": "the paper's reference leaf has a surface of 121 mm²; its three-week-old rosette has 29 leaves with 10,500 mm² of leaf in all", "sources": ["tolleter2024"]},
                {"label": "What joins its cells", "value": f"plasmodesmata, channels lined by the cell membrane that cross the wall between two cells; {len(at_plasmodesma)} of its proteins are stated to be there", "sources": ["uniprot"]},
                {"label": "Cells' machines", "value": f"of the 49 units of the law inventory, {findings['found']} have proteins of the same family in the plant; {findings['none found']} were not found, the gap junctions and the sodium-potassium pump among them", "sources": ["uniprot"]},
            ],
            "parts": {
                "membranes": 1, "wall": True, "wall_nm": 150, "nucleus": True, "organelles": ["er", "golgi", "mitochondria", "chloroplasts", "vacuole"],
                "organelle_sizes": {
                    "chloroplasts": {"count": 100, "volume_fl": 93, "across_um": plastid_um, "sources": ["tolleter2024"]},
                    "vacuole": {"share": 0.84, "sources": ["tolleter2024"]},
                },
            },
            "capabilities": {
                "cap.junctions": {"place": "absent", "why": "A plant's cells are not joined by gap junctions: none of its proteins carries the signature of connexins or innexins. They are joined by plasmodesmata, channels through the wall, which Cells does not model."},
                "cap.pumps": {"place": "present", "note": "Not the sodium-potassium pump of animal cells: none of its proteins carries the signature of that pump's own chain. Other pumps of the same wide family are found; the units that find them say which."},
            },
        },
        "capability_sources": {"cap.junctions": ["uniprot"], "cap.pumps": ["uniprot"]},
        "sources": {
            "uniprot": {"text": f"UniProt Consortium, UniProt release {release}: the reference proteome {PROTEOME} (Arabidopsis thaliana), its entries and its gene-by-gene set, and UniProt's vocabulary of subcellular locations.", "url": f"https://www.uniprot.org/proteomes/{PROTEOME}", "licence": "CC BY 4.0", "class": "permissive", "accessed": d.day(KB, PLACES_FILE)},
            "tolleter2024": {"text": E.paper_cite(d, "tolleter2024"), "doi": PAPERS["tolleter2024"]["doi"], "licence": "CC BY", "class": "permissive", "accessed": d.day(PAPERS_AT, "tolleter2024_fulltext.xml")},
        },
    }
    atlas = {
        "format": "cells.visualizer.species_atlas@1",
        "species": {"id": SPECIES_ID, "label": LABEL, "organism": ORGANISM, "taxon": TAXON, "plain": f"A small flowering plant of the laboratory, with {stated['genes']:,} genes in UniProt's reference proteome. The units of the law inventory are machines of animal cells; this is what their family signatures find among the one protein shown for each gene."},
        "made": made,
        "method": [
            f"The plant's proteins are the {len(entries):,} of UniProt's gene-by-gene set of the reference proteome {PROTEOME} (release {release}): one for each gene, {stated['shown_reviewed']:,} with a reviewed entry and {stated['shown_unreviewed']:,} with an unreviewed one.",
            "Licences were read before anything was copied; each is stated in sources.",
            "Each unit's family was taken from its own human candidates, by the same InterPro signatures that the other species' atlases ask. The build checks that the candidates carry them.",
            "Each signature was looked for among the InterPro entries UniProt gives each protein. A unit counts as found only where a protein carries the signature of a family that makes the machine itself; an accessory family alone does not make it found.",
            "A plant has channels and pumps of families of its own, which no unit of the inventory stands for. They are not listed here: the search asks only for the families of Cells' units. 'Different family' is given only where the inventory's table names another family for the same machine, and it names none that a plant has.",
            "A product with a reviewed entry is listed as a reviewed entry, one with an unreviewed entry as a family signature. Either is a candidate by family, and nothing here says which protein does which unit's work.",
            "No similarity search was run, and nothing is called an ortholog.",
        ],
        "sources": [
            {"name": "UniProt", "url": "https://www.uniprot.org/", "release": release, "accessed": d.day(KB, PLACES_FILE), "licence": "CC BY 4.0", "class": "permissive", "cite": cite_uniprot, "holds": "the entries of the plant's proteins, reviewed and unreviewed, with the InterPro entries UniProt gives each; the signatures of the units' human candidates; the vocabulary's words on plasmodesmata"},
            {"name": "InterPro", "url": "https://www.ebi.ac.uk/interpro/", "release": filing.release, "accessed": d.day(IPR, "entry.list"), "licence": "CC0 1.0", "class": "permissive", "cite": cite_interpro, "holds": "the identifiers and names of the family signatures"},
        ],
        "not_copied": "No sequence is copied. The plant's own database, TAIR, is linked to nowhere and nothing was downloaded from it: its pages refused this tool, so its terms could not be read. The Araport genes used here are those UniProt gives its entries.",
        "units": units,
        "extra": [],
    }
    report = {
        "release": release, "interpro": filing.release, "ontology": filing.ontology, "made": made, "stated": stated, "read": dict(read),
        "shelf_counts": shelf_counts, "counts": counts, "bases": {f"{side} / {basis}": n for (side, basis), n in sorted(bases.items())}, "rules": {rule: rules[rule] for rule, _, _ in H.RULES_USED},
        "evidence": dict(evidence), "how_sure": how_sure, "plant": plant, "resting": resting, "rule_systems": {owner: len(found) for owner, found in rule_ids.items()},
        "unnamed_analysis": {"places": len(analysed), "with a transit peptide given by analysis alone": len(by_transit), "of those, first stated at": dict(Counter(first(a) for a in by_transit).most_common(6))},
        "families": len(family_total), "in_families": len(filing.family), "several": filing.several, "no_family": len(filing.part),
        "family_sizes": {"one": sum(1 for size in family_total.values() if size == 1), "two to four": sum(1 for size in family_total.values() if 2 <= size <= 4), "five or more": sum(1 for size in family_total.values() if size >= 5)},
        "largest_families": [[filing.names[family]["name"], n] for family, n in sorted(family_total.items(), key=lambda pair: (-pair[1], pair[0]))[:8]],
        "lines": len(lines), "distinct": distinct, "lone": lone["count"], "lone_parts": len(alone), "part_lines": len(rest), "groups": groups, "member_files": files, "places_used": len(used),
        "findings": dict(findings), "found_units": found_units, "beside": {gene(a): what for a, what in beside.items()},
        "with_units": len(unit_ids), "entries_per_gene": dict(sorted(Counter(min(n, 6) for n in together.values()).items())), "plastid_um": plastid_um, "box": [box_um, high_um],
    }
    files_out = {"shelves": body, "table": table, "species": json.dumps(species, indent=1, ensure_ascii=False) + "\n", "shapes": json.dumps(outlines(), ensure_ascii=False, separators=(",", ":")) + "\n", "atlas": json.dumps(atlas, indent=1, ensure_ascii=False) + "\n"}
    files_out["readme"] = build_readme(report, header, closing)
    for name, text_ in files_out.items():
        if PATHS.search(text_):
            raise SystemExit(f"the {name} would hold a machine path")
    size = {name: len(text_.encode("utf-8")) for name, text_ in files_out.items()}
    if size["shelves"] >= H.LIMIT_SHELVES or max(size.values()) >= H.LIMIT_FILE:
        raise SystemExit(f"the files have outgrown their limits: {size}")
    report["sizes"] = size
    return files_out, report


def build_readme(report, header, closing):
    r = report
    names = {shelf["id"]: shelf["label"] for shelf in header["shelves"]}
    lines = [
        "# Thale cress: its own proteins, on a plant cell's shelves",
        "",
        "Generated by `tools/build_thalecress_atlas.py`; do not edit by hand. The note is `docs/THALECRESS.md`.",
        "",
        f"- `shelves.json`: {header['from']}",
        f"- `proteins.tsv`: one line for each of the {r['stated']['shown']:,} proteins shown, in the order of the shelves' lines. No sequences.",
        "- The members' files are not kept here: `python3 tools/build_thalecress_atlas.py members --out DIR` cuts them from these two files.",
        "",
        "Nothing of the plant is in the engine. This is reference data for the viewer.",
        "",
        "## Shelves",
        "",
        "| Shelf | Proteins | Outside | In | Inside | Side not known |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
        *[f"| {names.get(name, 'On no shelf')} | {sum(found.values()):,} | {found['outside']:,} | {found['in']:,} | {found['inside']:,} | {found['not known']:,} |" for name, found in r["shelf_counts"].items()],
        "",
        f"- **What a plant cell adds.** {header['plant']['rule']}",
        *[f"  - {what}: {n:,}" for what, n in header["plant"]["counts"].items()],
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
        f"a plant cell's own: {r['plant']}",
        f"families: {r['families']:,} holding {r['in_families']:,} (sizes {r['family_sizes']}); no family {r['no_family']:,}; lines {r['lines']:,} of {r['distinct']:,}; lone {r['lone']:,} in {r['lone_parts']} parts; part lines {r['part_lines']}; largest {r['largest_families'][:5]}",
        f"rests on, by owner: {r['resting']}; rules named: {r['rule_systems']}; unnamed analysis: {r['unnamed_analysis']}",
        f"atlas: {r['findings']}; accessory only {r['beside']}; proteins with units {r['with_units']}",
        "found: " + "; ".join(f"{unit} {len(genes)} ({', '.join(str(g) for g in genes[:4])})" for unit, genes in r["found_units"].items()),
        f"entries per gene (6 = six or more): {r['entries_per_gene']}; member files: {r['member_files']}; places used: {r['places_used']}; sizes: {r['sizes']}; chloroplast {r['plastid_um']} µm across; box {r['box']}",
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
        Path(args.out).mkdir(parents=True, exist_ok=True)
        for name, text in F.cut_members(args.out_dir).items():
            (Path(args.out) / name).write_text(text, encoding="utf-8")
            print(f"wrote {Path(args.out) / name} ({len(text.encode('utf-8')):,} bytes)")
        return
    if not args.datasets:
        parser.error(f"{args.step} needs --datasets")
    if args.step == "fetch":
        sys.exit(1 if fetch(Path(args.datasets), refresh=args.refresh) else 0)
    files, report = build(Path(args.datasets), json.loads(SNAPSHOT.read_text(encoding="utf-8")))
    folder = Path(args.out_dir)
    for target, name in [(folder / H.SHELVES_FILE, "shelves"), (folder / H.TABLE_FILE, "table"), (folder / "README.md", "readme"), (Path(args.out_species), "species"), (Path(args.out_shapes), "shapes"), (Path(args.out_atlas), "atlas")]:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(files[name], encoding="utf-8")
        print(f"wrote {target.name} ({len(files[name].encode('utf-8')):,} bytes)")
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(summary(report))


if __name__ == "__main__":
    main()
