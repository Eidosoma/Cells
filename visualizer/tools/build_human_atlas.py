#!/usr/bin/env python3
"""Build the human's own proteins for the atlas's shelves.

The protein atlas draws the functional units of the Cells law inventory, and the inventory
already names the human gene products that would make each unit. This tool makes the other
half for the human (schema/SPECIES_PROTEINS.md): the species' own proteins, whether or not
Cells has a law for them, laid out on shelves. A shelf is a membrane, and every protein
sits outside it, in it or inside it.

The catalogue is UniProt's reviewed human proteome: one canonical protein for each
reviewed entry of the reference proteome UP000005640. Its isoforms are a count, and the
unreviewed entries are not listed; the files say how many of each there are. Curators
state where most of these proteins are, so the human has several shelves, one for each
membrane the statements tell apart, and a protein stands where its entry first places it.

Three steps, kept apart:

    python3 tools/build_human_atlas.py fetch --datasets DATA
        asks public databases and saves every answer as it came under DATA, one folder
        for each source with a MANIFEST.json that gives every file's address, time and
        SHA-256. The only step that uses the network.

    python3 tools/build_human_atlas.py build --datasets DATA
        reads only DATA, the inventory snapshot and the pages of terms that the other
        species' tools saved beside DATA (--terms), checks every file against its
        MANIFEST and every source's terms in its saved page, and writes, in
        data/proteins/human/, shelves.json, proteins.tsv and README.md: the same bytes
        every time.

    python3 tools/build_human_atlas.py members --out OUT
        cuts the shelves' member files, which the page publishes beside it, from the two
        files in data/proteins/human/. It reads nothing else.

The table that says which shelf and side a stated place stands for is at the top of this
file. Every protein is shown: a family has a line for each shelf that holds members of
it, a protein that is the only member of its family is listed with the others like it,
and a protein with no family under a wider grouping.

This is the viewer's reference data. It is not the engine's protein catalogue and it
makes no claim about the engine: the laws are the same for every species, and a protein
here is tied to the inventory only where the inventory itself names its accession.

Nothing is taken from the Human Protein Atlas: it is kept for a link only, and its terms
are saved beside the other sources' so that the choice can be checked.

Requests carry a generic client name and nothing about who asks. Standard library only.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SNAPSHOT = ROOT / "data" / "proteins" / "inventory.snapshot.json"
OUT_DIR = ROOT / "data" / "proteins" / "human"
CLIENT = "atlas-builder/1.0"
PATHS = re.compile(r"/(?:home|mnt|Users)/")

TAXON = 9606
ORGANISM = "Homo sapiens"
PROTEOME = "UP000005640"
UNIPROT = "https://rest.uniprot.org"
UNIPROT_DOCS = "https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/docs"
INTERPRO_FILES = "https://ftp.ebi.ac.uk/pub/databases/interpro/current_release"
MINE = "the visualizer's human proteome agent"


# ---------------------------------------------------------------------------------------
# The table: which shelf and which side a stated place stands for
# ---------------------------------------------------------------------------------------
#
# schema/SPECIES_PROTEINS.md, "A curated proteome", fixes the shelves and the rules. This
# table applies them to UniProt's own vocabulary of subcellular locations (subcell.txt):
# every term an entry uses is resolved to a line here through the vocabulary's own links,
# and the build stops at a term it cannot resolve or that two lines claim.

SHELVES = [
    {"id": "cell", "label": "Cell membrane", "outside": "Outside the cell", "inside": "Inside the cell: in the cytoplasm"},
    {"id": "er", "label": "Endoplasmic reticulum membrane", "outside": "On the cytoplasmic face of the endoplasmic reticulum", "inside": "In the endoplasmic reticulum's lumen"},
    {"id": "mito", "label": "Mitochondrial inner membrane", "outside": "Between the mitochondrion's two membranes", "inside": "In the mitochondrial matrix"},
    {"id": "nucleus", "label": "Nuclear envelope", "outside": "On the cytoplasmic face of the nuclear envelope", "inside": "In the nucleus"},
    {"id": "other", "label": "Other membranes", "outside": "On the cytoplasmic face of one of the other membranes", "inside": "Within one of the other compartments"},
    {"id": "membrane", "label": "A membrane, not told which", "outside": "Beyond a membrane: outside the cell, or within a compartment", "inside": "On the cytoplasmic side of a membrane"},
]
SHELF_IDS = [shelf["id"] for shelf in SHELVES]
SHELF_NOTES = {
    "other": "The cell's remaining membranes together: those of the Golgi apparatus, endosomes, lysosomes, peroxisomes and vesicles, and the mitochondrion's outer membrane. Each protein here names its compartment in the mark 'where'.",
    "membrane": "The proteins that an entry places in a membrane without naming it, and those with no stated place whose entry carries a membrane-spanning segment or a signal peptide.",
}
NO_SHELF = "no shelf"  # the name under which the file counts the proteins that are on none

# What a term of the vocabulary names, against its shelf's membrane:
MEMBRANE = "membrane"    # the membrane itself, or a part of it: the side comes from the words that follow, or from the entry's features
INSIDE = "inside"        # what the membrane encloses
OUTSIDE = "outside"      # what lies beyond the membrane
WHOLE = "whole"          # a compartment that one membrane bounds, or a structure at the membrane, with no part or face named: the entry's features may settle the side
REGION = "region"        # a region that holds more than one membrane, or none: only a later, narrower statement settles the side
ELSEWHERE = "elsewhere"  # not a place of the cell: the statement is passed over
KINDS = {
    MEMBRANE: "the shelf's membrane, or a part of it",
    INSIDE: "what the membrane encloses",
    OUTSIDE: "what lies beyond the membrane",
    WHOLE: "a compartment that one membrane bounds, or a structure at the membrane, with no part or face named",
    REGION: "a region with more than one membrane, or none",
    ELSEWHERE: "not a place of the cell",
}

# UniProt's term -> (shelf, what the term names). A term that is not listed takes the line
# of the terms it is a kind of, else of the term before it in UniProt's own path for it
# ("Cytoplasm, cytoskeleton, spindle"), else of the terms it is a part of. A term that
# names a membrane and resolves to a compartment or a region is that place's membrane.
PLACES = {
    # the cell membrane, and what it encloses or faces
    "Cell membrane": ("cell", MEMBRANE),
    "Clathrin-coated pit": ("cell", MEMBRANE),              # the vocabulary: "regions of the cell membrane"
    "Cytoplasm": ("cell", INSIDE),
    "Cornified envelope": ("cell", INSIDE),                 # the vocabulary: "formed beneath the plasma membrane"
    "Secreted": ("cell", OUTSIDE),
    "Extracellular vesicle": ("cell", OUTSIDE),             # the vocabulary: "vesicles that have been released by cells"
    "Extracellular vesicle membrane": ("cell", OUTSIDE),
    "Cell surface": ("cell", WHOLE),                        # the vocabulary: "the outermost side of the cell"; in the membrane or on it is not said
    "Cell junction": ("cell", WHOLE),                       # a contact between cells: at the cell membrane
    "Cell projection": ("cell", REGION),
    "Synapse": ("cell", REGION),
    "Midbody": ("cell", REGION),
    "Cleavage furrow": ("cell", REGION),
    "Perikaryon": ("cell", REGION),
    "Photoreceptor inner segment": ("cell", REGION),
    "Cell tip": ("cell", REGION),
    # the nucleus
    "Nucleus": ("nucleus", INSIDE),
    "Chromosome": ("nucleus", INSIDE),                      # this file's reading: the chromosomes lie within the nucleus, except while a cell divides
    "Nucleus envelope": ("nucleus", WHOLE),
    "Nuclear pore complex": ("nucleus", WHOLE),             # the vocabulary: a part of the nuclear envelope; which face a protein of it is on is not said
    # the endoplasmic reticulum
    "Endoplasmic reticulum": ("er", WHOLE),
    "Endoplasmic reticulum lumen": ("er", INSIDE),
    "Sarcoplasmic reticulum": ("er", WHOLE),                # the vocabulary: "a highly specialized form of the smooth endoplasmic reticulum"
    "Sarcoplasmic reticulum lumen": ("er", INSIDE),
    # the mitochondrion: its inner membrane is the shelf
    "Mitochondrion": ("mito", REGION),
    "Mitochondrion envelope": ("mito", REGION),
    "Mitochondrion membrane": ("mito", REGION),             # the vocabulary: "used when it is not known if the protein is found in or associated with the inner or outer mitochondrial membrane"
    "Mitochondrion inner membrane": ("mito", MEMBRANE),
    "Mitochondrion matrix": ("mito", INSIDE),
    "Mitochondrion intermembrane space": ("mito", OUTSIDE),
    "Mitochondrion outer membrane": ("other", MEMBRANE),    # the contract: on the shelf of the other membranes
    # the other compartments
    "Golgi apparatus": ("other", WHOLE),
    "Golgi apparatus lumen": ("other", INSIDE),
    "Endosome": ("other", WHOLE),
    "Endosome lumen": ("other", INSIDE),
    "Lysosome": ("other", WHOLE),
    "Lysosome lumen": ("other", INSIDE),
    "Peroxisome": ("other", WHOLE),
    "Peroxisome matrix": ("other", INSIDE),
    "Vesicle": ("other", WHOLE),
    "Cytoplasmic vesicle lumen": ("other", INSIDE),
    "Melanosome": ("other", WHOLE),
    "Vacuole": ("other", WHOLE),
    "Cytoplasmic granule": ("other", WHOLE),
    "Cytoplasmic granule lumen": ("other", INSIDE),
    "Preautophagosomal structure": ("other", WHOLE),
    "Endoplasmic reticulum-Golgi intermediate compartment": ("other", WHOLE),
    "Endoplasmic reticulum-Golgi intermediate compartment lumen": ("other", INSIDE),
    "Lipid droplet": ("other", REGION),                     # the vocabulary: "covered by a unique phospholipid monolayer": it has no lumen and nothing spans it
    # a membrane that is not named
    "Membrane": ("membrane", MEMBRANE),
    "Endomembrane system": ("membrane", MEMBRANE),
    # not a place of the cell
    "Virion": (None, ELSEWHERE),
    "Target membrane": (None, ELSEWHERE),
}
GENERIC = ("Membrane", "Endomembrane system")  # parents that every membrane has: followed last

# The words of a membrane's topology and of its faces, by UniProt's identifiers.
SPANS = {"SL-9904", "SL-9905", "SL-9906", "SL-9907", "SL-9908", "SL-9909"}  # single-pass (of any type) and multi-pass
ANCHORED = {"SL-9902", "SL-9920"}                                           # GPI-anchor, GPI-like-anchor
NOT_SPANNING = {"SL-9901", "SL-9903"}                                       # lipid-anchor, peripheral membrane protein
# A stated face -> the side, by shelf. The cytoplasm is inside the cell membrane and beyond
# every internal membrane; on the shelf of a membrane that is not named, "outside" is the
# side away from the cytoplasm.
FACES = {
    "Cytoplasmic side": {"cell": "inside", "membrane": "inside", "er": "outside", "other": "outside", "nucleus": "outside", "mito": "outside"},
    "Extracellular side": {"cell": "outside", "membrane": "outside"},
    "Lumenal side": {"er": "inside", "other": "inside", "membrane": "outside"},
    "Matrix side": {"mito": "inside", "other": "inside"},
    "Intermembrane side": {"mito": "outside", "other": "inside"},
    "Nucleoplasmic side": {"nucleus": "inside"},
}
# The side away from the cytoplasm, where a protein that was exported ends up: outside the
# cell, or within a compartment along the secretory pathway. UniProt's own pages say so of
# the signal peptide and of the GPI anchor (help_signal.json, help_lipid.json).
AWAY = {"cell": "outside", "membrane": "outside", "er": "inside", "other": "inside"}

# How a protein came to its side, in the order the rules are tried. The first five read the
# entry's words; the next two read its features; the rest leave the side not known.
RULES_USED = [
    ("place", "stated", "The place itself is on one side: within a compartment, or beyond a membrane."),
    ("spans", "stated", "The entry states that the protein spans the membrane (single-pass or multi-pass)."),
    ("face", "stated", "The entry states which face of the membrane the protein is on."),
    ("anchor", "stated", "The entry states a GPI anchor and no face: such an anchor holds a protein on the face away from the cytoplasm."),
    ("later part", "stated", "The first place names no side, and a later statement of the same entry names a part of that place and gives the side."),
    ("segment", "predicted", "The entry states the membrane or the compartment and not the side, and it carries a membrane-spanning segment: in the membrane."),
    ("signal", "predicted", "The entry states the membrane or the compartment and not the side, and it carries a signal peptide and no membrane-spanning segment: on the side away from the cytoplasm."),
    ("no place: segment", "predicted", "No place of the cell is stated, and the entry carries a membrane-spanning segment: in a membrane, not told which."),
    ("no place: signal", "predicted", "No place of the cell is stated, and the entry carries a signal peptide and no segment: beyond a membrane, outside the cell or within a compartment."),
    ("side not stated", "none", "The entry states the membrane or the compartment, and nothing in it settles the side."),
    ("no place", "none", "No place of the cell is stated and nothing is predicted: on no shelf."),
]

# What stands behind a stated place, from UniProt's evidence codes; of several, the first listed here.
EVIDENCE = [
    ("experiment", ["ECO:0000269"], "an experiment in a paper the entry cites"),
    ("similarity", ["ECO:0000250"], "likeness to a protein of which it is known"),
    ("curator", ["ECO:0000305", "ECO:0000303"], "a curator's inference, or an author's statement that names no experiment"),
    ("rule", ["ECO:0000255"], "a sequence model or a family rule, applied by a curator"),
]
NOT_GIVEN = "not given"  # the entry gives no evidence code: an older curated statement
SEEN = {1: "protein", 2: "transcript", 3: "homology", 4: "predicted", 5: "uncertain"}  # UniProt's five levels of evidence that a protein exists


# ---------------------------------------------------------------------------------------
# Fetch: what is asked, and how each answer is kept
# ---------------------------------------------------------------------------------------
#
# Downloads are kept the way the project keeps them: one folder per source under a datasets
# folder, each with a MANIFEST.json that gives every file's address, time and SHA-256. The
# build reads a file only through its MANIFEST and checks it against the SHA-256 there.

REVIEWED = f"(proteome:{PROTEOME}) AND (reviewed:true)"
PLACE_FIELDS = "accession,id,protein_name,gene_primary,length,protein_existence,cc_subcellular_location,ft_transmem,ft_intramem,ft_signal,ft_transit,ft_topo_dom,ft_lipid,cc_alternative_products,fragment"
KB = "uniprot-human-reviewed-proteome"
KB_DOCS = "uniprot-docs-and-terms"
IPR = "interpro-entries-tree-and-go"
GO = "geneontology-go-basic"
HPA = "terms-human-protein-atlas"
BIG_PI = "terms-big-pi"
# The terms of the rule systems and programs behind UniProt's statements were read and saved
# once, by the tools of the other species. This tool fetches none of them again: the build
# reads those copies through their MANIFESTs, in the folder that holds every species' downloads.
SAVED_TERMS = {
    "prosite": ("syn3a/terms-prosite", "prosite_license.html"),
    "hamap": ("mpneumoniae/terms-upstream-tools", "upstream_hamap_about.html"),
    "tmhmm": ("mpneumoniae/terms-upstream-tools", "upstream_tmhmm_licence.html"),
    "signalp": ("mpneumoniae/terms-upstream-tools", "upstream_signalp_licence.html"),
    "targetp": ("mpneumoniae/terms-upstream-tools", "upstream_targetp_licence.html"),
    "phobius": ("mpneumoniae/terms-upstream-tools", "upstream_phobius_download.html"),
    "unirule": ("planarian/terms-upstream-tools", "uniprot_help_unirule.json"),
}
PLACES_FILE = f"uniprotkb_{PROTEOME}_reviewed_places.json.gz"
SIGNATURES_FILE = f"uniprotkb_{PROTEOME}_reviewed_signatures.tsv.gz"
# UniProt's own pages on how it annotates what is read here; each is quoted in the note.
HELP_PAGES = ["subcellular_location", "transmem", "intramem", "topo_dom", "signal", "transit", "lipid", "evidences", "protein_existence", "canonical_and_isoforms"]
SOURCES = {
    KB: {
        "what": f"UniProtKB: every reviewed entry of the human reference proteome {PROTEOME} with its name, gene, length, level of evidence, stated subcellular locations with the evidence for each, membrane-spanning segments, signal and transit peptides, lipid anchors and the isoforms it describes; the InterPro entries and Gene Ontology terms UniProt gives each; the proteome's own record; and counts of the reviewed and unreviewed entries",
        "licence": "CC BY 4.0",
    },
    KB_DOCS: {
        "what": "UniProt's controlled vocabulary of subcellular locations, membrane topologies and orientations (subcell.txt), its licence page, and its help pages on how locations, membrane-spanning segments, signal peptides, lipid anchors, evidence codes, the level of evidence and isoforms are annotated",
        "licence": "CC BY 4.0",
    },
    IPR: {
        "what": "InterPro release files: the name and type of each entry, the tree of parent and child entries, the mapping of entries to Gene Ontology terms, the release notes, and InterPro's licence page",
        "licence": "CC0 1.0",
    },
    GO: {
        "what": "The Gene Ontology (go-basic.obo), read for the is_a and part_of links between terms, with the consortium's page on citing and licence",
        "licence": "CC BY 4.0",
    },
    HPA: {
        "what": "The Human Protein Atlas's licence page, saved so that the choice to take nothing from it can be checked. No data file of the Human Protein Atlas was downloaded",
        "licence": "CC BY 4.0 for all copyrightable parts of its database, as its own page states, with the warning that data of third parties in it may carry other terms; nothing is taken from it",
    },
    BIG_PI: {
        "what": "The page of the big-PI predictor, the program UniProt's help names for the GPI anchors it predicts, saved to read its terms; it states none. Only the page was asked: no sequence was sent and no program was run. The page is kept because a few sides in the human shelves rest on a GPI anchor that an entry states on a sequence analysis",
        "licence": "No open licence stated: the predictor's own page gives no terms of use",
    },
}


def q(text):
    return urllib.parse.quote(text, safe="")


def requests():
    """Every request of the fetch step: the dataset folder, the file there, the address and
    what it is for. "contains" is a text the body must hold to be kept."""
    out = []

    def add(source, file, url, purpose, **more):
        out.append({"source": source, "file": file, "url": url, "purpose": purpose, **more})

    stream = f"{UNIPROT}/uniprotkb/stream?query={q(REVIEWED)}&compressed=true"
    add(KB, PLACES_FILE, f"{stream}&format=json&fields={PLACE_FIELDS}", "every reviewed entry of the proteome: its name, gene, length and level of evidence, where the entry places it and on what evidence, its membrane-spanning segments, signals and lipid anchors, and its isoforms", gzip=True)
    add(KB, SIGNATURES_FILE, f"{stream}&format=tsv&fields=accession,xref_interpro,go_id", "the InterPro entries and the Gene Ontology terms UniProt gives each reviewed entry", gzip=True)
    count = lambda query, more="": f"{UNIPROT}/uniprotkb/search?query={q(query)}&size=1&fields=accession&format=json{more}"
    add(KB, "count_reviewed.json", count(REVIEWED), "how many reviewed entries the proteome holds (the count is in the answer's header)")
    add(KB, "count_reviewed_with_isoforms.json", count(REVIEWED, "&includeIsoform=true"), "how many sequences the reviewed entries describe when each isoform is counted")
    add(KB, "count_unreviewed.json", count(f"(proteome:{PROTEOME}) AND (reviewed:false)"), "how many unreviewed entries the proteome holds")
    add(KB, "count_all.json", count(f"(proteome:{PROTEOME})"), "how many entries the proteome holds in all")
    add(KB, "count_reviewed_with_place.json", count(f"{REVIEWED} AND (cc_scl_term:*)"), "how many reviewed entries state a subcellular location, by UniProt's own search")
    add(KB, f"proteome_{PROTEOME}.json", f"{UNIPROT}/proteomes/{PROTEOME}", "the proteome's own record: its description, its counts and its genome assembly")
    add(KB_DOCS, "subcell.txt", f"{UNIPROT_DOCS}/subcell.txt", "UniProt's vocabulary of subcellular locations, topologies and orientations, with which term is a kind or a part of which", contains="Controlled vocabulary of subcellular")
    add(KB_DOCS, "terms_uniprot_license.json", f"{UNIPROT}/help/license", "UniProt's licence")
    for page in HELP_PAGES:
        add(KB_DOCS, f"help_{page}.json", f"{UNIPROT}/help/{page}", f"UniProt's help page '{page}': how it annotates what is read here")
    add(IPR, "entry.list", f"{INTERPRO_FILES}/entry.list", "the name and type of each InterPro entry", contains="ENTRY_AC")
    add(IPR, "ParentChildTreeFile.txt", f"{INTERPRO_FILES}/ParentChildTreeFile.txt", "which InterPro entry is a narrower kind of which")
    add(IPR, "interpro2go", f"{INTERPRO_FILES}/interpro2go", "the Gene Ontology terms InterPro gives each of its entries")
    add(IPR, "release_notes.txt", f"{INTERPRO_FILES}/release_notes.txt", "the InterPro release these files belong to")
    add(IPR, "terms_interpro_license.html", "https://interpro-documentation.readthedocs.io/en/latest/license.html", "InterPro's licence")
    add(GO, "go-basic.obo", "https://current.geneontology.org/ontology/go-basic.obo", "the Gene Ontology's terms and the links between them")
    add(GO, "go_citation_policy.html", "https://geneontology.org/docs/go-citation-policy/", "the Gene Ontology's licence")
    add(HPA, "licence.html", "https://www.proteinatlas.org/about/licence", "the Human Protein Atlas's licence, read before deciding that nothing is taken from it", contains="Human Protein Atlas")
    add(BIG_PI, "gpi_server.html", "https://mendel.imp.ac.at/gpi/gpi_server.html", "the big-PI predictor's own page, read for its terms; UniProt's help names the program for the GPI anchors it predicts", contains="big-PI Predictor")
    return out


def utc_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def digest(path):
    sha, md5 = hashlib.sha256(), hashlib.md5()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            sha.update(block)
            md5.update(block)
    return sha.hexdigest(), md5.hexdigest()


def read_manifest(folder):
    path = Path(folder) / "MANIFEST.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def is_ours(manifest):
    return manifest is not None and MINE in manifest.get("note", "")


def whole_gzip(body):
    try:
        gzip.decompress(body)
        return True
    except (OSError, EOFError):
        return False


def fetch(datasets, refresh=False, pause=2.0, tries=6):
    """Ask every request whose file is not yet in its dataset folder; save the body as it
    came and describe it in the folder's MANIFEST. A folder another agent made is read and
    never written."""
    datasets = Path(datasets)
    asked = failed = 0
    for request in requests():
        folder = datasets / request["source"]
        manifest = read_manifest(folder)
        held = (folder / request["file"]).exists() and any(item["name"] == request["file"] for item in (manifest or {}).get("files", []))
        if held and not (refresh and is_ours(manifest)):
            continue
        if folder.exists() and not is_ours(manifest):
            print(f"missing  {request['source']}/{request['file']}: the folder was made by another agent, so nothing is written there", flush=True)
            failed += 1
            continue
        record, body = {}, None
        call = urllib.request.Request(request["url"], headers={"User-Agent": CLIENT, "Accept-Encoding": "identity"})
        for attempt in range(tries):
            record, body = {"asked": utc_now()}, None
            try:
                with urllib.request.urlopen(call, timeout=1800) as answer:
                    body = answer.read()
                    record["status"] = answer.status
                    for header, key in [("X-Total-Results", "total_results"), ("X-UniProt-Release", "uniprot_release"), ("X-UniProt-Release-Date", "uniprot_release_date"), ("Last-Modified", "last_modified"), ("Content-Type", "content_type")]:
                        if answer.headers.get(header):
                            record[key] = answer.headers[header]
                # An answer that was cut short, or an error page sent as an answer, is not kept.
                if request.get("gzip") and not whole_gzip(body):
                    record["status"], body = 0, None
                    record["error"] = "the answer is not a whole gzip file"
                elif request.get("contains") and request["contains"].encode() not in body:
                    record["status"], body = 0, None
                    record["error"] = "the answer is not the listing asked for"
                else:
                    break
            except urllib.error.HTTPError as error:
                record["status"] = error.code
                if error.code < 500 and error.code != 429:
                    break
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                record["status"] = 0
                record["error"] = str(getattr(error, "reason", error))[:200]
            # A busy service: wait and ask again.
            if attempt + 1 < tries:
                time.sleep(20)
        asked += 1
        if record.get("status") != 200 or body is None:
            failed += 1
            print(f"{record.get('status')}  {request['source']}/{request['file']}  {record.get('error', '')}", flush=True)
            continue
        # The folder is made only if it is not there at this moment; one that another agent
        # has just made is left alone.
        folder.mkdir(parents=True, exist_ok=True)
        manifest = read_manifest(folder)
        if manifest is None and any(folder.iterdir()):
            print(f"skipped  {request['source']}/{request['file']}: the folder holds files and no MANIFEST of this tool", flush=True)
            failed += 1
            continue
        if manifest is not None and not is_ours(manifest):
            print(f"skipped  {request['source']}/{request['file']}: the folder was just made by another agent", flush=True)
            failed += not (folder / request["file"]).exists()
            continue
        (folder / request["file"]).write_bytes(body)
        sha, md5 = digest(folder / request["file"])
        entry = {
            "name": request["file"], "url": request["url"], "role": request["purpose"], "retrieved_utc": record["asked"], "http_status": record["status"],
            "content_type": record.get("content_type"), "size_bytes": len(body), "sha256": sha, "md5": md5,
            "expected_size": None, "expected_md5": None, "ok": True, "error": None,
        }
        for key in ("total_results", "uniprot_release", "uniprot_release_date", "last_modified"):
            if record.get(key) is not None:
                entry["x_" + key] = record[key]
        manifest = manifest or {"source_id": request["source"], "files": []}
        manifest["record"] = SOURCES[request["source"]]
        manifest["files"] = sorted([item for item in manifest["files"] if item["name"] != entry["name"]] + [entry], key=lambda item: item["name"])
        manifest["manifest_written_utc"] = utc_now()
        manifest["note"] = f"Added by {MINE}: downloaded as untrusted data by tools/build_human_atlas.py of the Cells checkout. Nothing here was executed."
        (folder / "MANIFEST.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"200  {request['source']}/{request['file']}  {len(body)}", flush=True)
        time.sleep(pause)
    print(f"asked {asked} request(s), {failed} failed or missing, under {datasets}")
    return failed


# ---------------------------------------------------------------------------------------
# Build: read the saved downloads
# ---------------------------------------------------------------------------------------

class Datasets:
    """The downloads, each read through its folder's MANIFEST and checked against it."""

    def __init__(self, folder):
        self.folder = Path(folder)
        self.read = {}

    def entry(self, source, file):
        if (source, file) not in self.read:
            manifest = read_manifest(self.folder / source)
            if manifest is None:
                raise SystemExit(f"no dataset folder {source!r} with a MANIFEST; run the fetch step first")
            entry = next((item for item in manifest["files"] if item["name"] == file), None)
            if entry is None or not (self.folder / source / file).exists():
                raise SystemExit(f"the dataset folder {source} does not hold {file!r}; run the fetch step first")
            if digest(self.folder / source / file)[0] != entry["sha256"]:
                raise SystemExit(f"{source}/{file} is not the file its MANIFEST describes")
            self.read[source, file] = entry
        return self.read[source, file]

    def path(self, source, file):
        self.entry(source, file)
        return self.folder / source / file

    def text(self, source, file):
        if file.endswith(".gz"):
            return gzip.decompress(self.path(source, file).read_bytes()).decode("utf-8")
        return self.path(source, file).read_text(encoding="utf-8", errors="replace")

    def day(self, source, file):
        return self.entry(source, file)["retrieved_utc"][:10]

    def last_day(self):
        return max(entry["retrieved_utc"][:10] for entry in self.read.values())

    def total(self, source, file):
        return int(self.entry(source, file)["x_total_results"])


def plain(markup):
    """Markup as running text, for looking up a sentence in a saved page."""
    import html

    markup = re.sub(r"(?s)<(script|style)[^>]*>.*?</\1>", " ", markup)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]+>", " ", markup))).strip()


def natural(identifier):
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", identifier)]


def check_terms(d, shared):
    """Each source's terms, read in its own saved page before anything of it is used.
    Returns the sentences the files quote."""
    said = {}

    def must(key, source, file, pattern, markup=True, field=None):
        text = shared.text(*SAVED_TERMS[source]) if file is None else d.text(source, file)
        if field:
            text = json.loads(text)[field]
        text = plain(text) if markup else text
        found = re.search(pattern, text)
        if not found:
            raise SystemExit(f"{source}/{file} no longer states its terms as they were read; read the page again before building")
        said[key] = found.group(0)

    must("uniprot", KB_DOCS, "terms_uniprot_license.json", r"We have chosen to apply the \[?Creative Commons Attribution 4\.0 International \(CC BY 4\.0\) License\]?(\([^)]*\))? to all copyrightable parts of our databases", markup=False, field="content")
    must("interpro", IPR, "terms_interpro_license.html", r"All of the InterPro, Pfam, PRINTS and SFLD downloadable data provided on the InterPro website is freely available under CC0 1\.0 Universal")
    must("go", GO, "go_citation_policy.html", r"licensed under the Creative Commons Attribution 4\.0 Unported License")
    must("hpa", HPA, "licence.html", r"The Human Protein Atlas is licensed under the Creative Commons Attribution 4\.0 International License for all copyrightable parts of our database\. Data subject to third-party constraints may also be included")
    must("prosite", "prosite", None, r"distributed under the Creative Commons Attribution-NonCommercial-NoDerivatives \(CC BY-NC-ND 4\.0\) License")
    must("prosite_fee", "prosite", None, r"Commercial users are asked to pay a yearly license fee")
    must("hamap", "hamap", None, r"HAMAP is copyrighted by the SIB Swiss Institute of Bioinformatics and distributed under the Creative Commons Attribution \(CC BY 4\.0\) License")
    for tool in ("tmhmm", "signalp", "targetp"):
        must(f"{tool}_for", tool, None, rf"ACADEMIC SOFTWARE LICENSE AGREEMENT FOR END-USERS AT PUBLICLY FUNDED ACADEMIC, EDUCATION OR RESEARCH INSTITUTIONS FOR THE USE OF {tool}")
        must(f"{tool}_others", tool, None, r"If you are not a member of a publicly funded Academic and/or Education and/or Research Institution you must obtain a commercial license")
        must(f"{tool}_use", tool, None, r"free non-exclusive license to use the Software for internal research purposes only")
    must("phobius", "phobius", None, r"Phobius is intended for academic users only")
    must("phobius_use", "phobius", None, r"I agree to use the obtained software only for private study, education or nonprofit research")
    must("rulebase", "unirule", None, r"RuleBase rules", markup=False, field="content")
    must("big_pi", BIG_PI, "gpi_server.html", r"big-PI Predictor")
    if re.search(r"(?i)licen[cs]e|terms of use|copyright|commercial", plain(d.text(BIG_PI, "gpi_server.html"))):
        raise SystemExit("the big-PI predictor's page now speaks of terms; read them and class it again")
    must("big_pi_named", KB_DOCS, "help_lipid.json", r"sites predicted by the 'big-Pi' predictor", markup=False, field="content")
    must("two_agree", KB_DOCS, "help_transmem.json", r"at least two methods must return a positive prediction", markup=False, field="content")
    # What UniProt's own pages say of the features the two feature rules read.
    must("segments", KB_DOCS, "help_transmem.json", r"predicted by the application of the predictive tools TMHMM, Memsat, Phobius and the hydrophobic moment plot method of Eisenberg and coworkers", markup=False, field="content")
    must("signals", KB_DOCS, "help_signal.json", r"predicted by the application of the predictive tools Phobius, Predotar, SignalP and TargetP\. At least two methods must return a positive signal peptide prediction", markup=False, field="content")
    must("signal_fate", KB_DOCS, "help_signal.json", r"Signal peptides are found in proteins that are targeted to the endoplasmic reticulum and eventually destined to be either secreted/extracellular/periplasmic/etc\., retained in the lumen of the endoplasmic reticulum, of the lysosome or of any other organelle along the secretory pathway", markup=False, field="content")
    must("anchor", KB_DOCS, "help_lipid.json", r"the addition of a GPI-anchor may serve to anchor extracellular proteins to the outer face of the plasma membrane", markup=False, field="content")
    must("anchor_lumen", KB_DOCS, "help_lipid.json", r"GPI-anchor addition takes place in the lumen of the endoplasmic reticulum", markup=False, field="content")
    must("no_evidence", KB_DOCS, "help_transmem.json", r"The annotations which are missing evidence were created before we started to manually curate information with evidence", markup=False, field="content")
    return said


# ---------------------------------------------------------------------------------------
# UniProt's vocabulary of places, and the table applied to it
# ---------------------------------------------------------------------------------------

class Vocabulary:
    """subcell.txt: each term's name, its path as UniProt writes it, and what it is a kind
    or a part of; and each location's line of the table, resolved through those links."""

    def __init__(self, d):
        text = d.text(KB_DOCS, "subcell.txt")
        self.release = re.search(r"^Release:\s+(\S+) of", text, re.M).group(1)
        self.terms, current = {}, None
        for line in text.splitlines():
            code, _, value = line.partition("   ")
            if code in ("ID", "IT", "IO"):
                current = {"kind": {"ID": "location", "IT": "topology", "IO": "face"}[code], "name": value.rstrip("."), "is_a": [], "part_of": [], "path": None}
            elif current is not None:
                if code == "AC":
                    current["accession"] = value.strip()
                    self.terms[value.strip()] = current
                elif code == "HI":
                    current["is_a"].append(value.rstrip("."))
                elif code == "HP":
                    current["part_of"].append(value.rstrip("."))
                elif code == "SL":
                    current["path"] = value.rstrip(".")
                elif code == "//":
                    current = None
        self.by_name = {term["name"]: term for term in self.terms.values() if term["kind"] == "location"}
        self.lower = {name.lower(): name for name in self.by_name}
        unknown = sorted(name for name in PLACES if name not in self.by_name)
        if unknown:
            raise SystemExit(f"the table names places the vocabulary does not have: {unknown}")
        for accession in sorted(SPANS | ANCHORED | NOT_SPANNING):
            if self.terms.get(accession, {}).get("kind") != "topology":
                raise SystemExit(f"{accession} is no longer a topology of the vocabulary; read it again")
        faces = {term["name"] for term in self.terms.values() if term["kind"] == "face"}
        if set(FACES) - faces:
            raise SystemExit(f"the table names faces the vocabulary does not have: {sorted(set(FACES) - faces)}")
        self.memo, self.above = {}, {}

    def parents(self, name, links):
        return [parent for link in links for parent in self.by_name[name][link] if parent in self.by_name]

    def broader(self, name):
        """Every term the place is a kind or a part of, however far."""
        if name not in self.above:
            found, stack = set(), [name]
            while stack:
                for parent in self.parents(stack.pop(), ("is_a", "part_of")):
                    if parent not in found:
                        found.add(parent)
                        stack.append(parent)
            self.above[name] = found
        return self.above[name]

    def is_membrane(self, name):
        return name == "Membrane" or "Membrane" in self.broader(name)

    def resolve(self, name, trail=()):
        """The table's line for a place: (shelf, what it names, how it was resolved, the
        table's term it rests on), or None."""
        if name in self.memo:
            return self.memo[name]
        rank = {MEMBRANE: 4, INSIDE: 3, OUTSIDE: 3, REGION: 2, WHOLE: 1, ELSEWHERE: 0}
        out = None
        if name in PLACES:
            out = (*PLACES[name], "table", name)
        else:
            # First what the term is a kind of; then the place written before it in UniProt's
            # own path for the term; then what it is a part of.
            def by_links(links, how):
                above = [self.resolve(parent, (*trail, name)) for parent in self.parents(name, links) if parent not in GENERIC and parent not in trail]
                found = sorted({line[:2] for line in above if line}, key=str)
                if not found:
                    return None
                best = max(found, key=lambda line: rank[line[1]])
                level = [line for line in found if rank[line[1]] == rank[best[1]]]
                if len({line[0] for line in found if line[1] != ELSEWHERE}) > 1 or len(level) > 1:
                    raise SystemExit(f"the vocabulary puts {name!r} under lines of the table that disagree ({found}); give it a line of its own")
                return (best[0], best[1], how, next(line[3] for line in above if line and line[:2] == best))

            out = by_links(("is_a",), "kind of")
            if out is None:
                path = [part.strip() for part in self.by_name[name]["path"].split(",")]
                before = self.lower.get(path[-2].lower()) if len(path) > 1 else None
                if before and before != name and before not in trail:
                    found = self.resolve(before, (*trail, name))
                    if found:
                        out = (found[0], found[1], "path", found[3])
            if out is None:
                out = by_links(("part_of",), "part of")
            if out is None and self.is_membrane(name):
                out = (*PLACES["Membrane"], "a membrane, not named", "Membrane")
            if out and out[1] in (WHOLE, REGION) and self.is_membrane(name):
                out = (out[0], MEMBRANE, out[2] + ", a membrane", out[3])
        if not trail:
            self.memo[name] = out
        return out


# ---------------------------------------------------------------------------------------
# The entries: what each states and carries
# ---------------------------------------------------------------------------------------

def evidence_of(evidences, where):
    codes = {item["evidenceCode"] for item in evidences or []}
    if not codes:
        return NOT_GIVEN
    for word, wanted, _ in EVIDENCE:
        if codes & set(wanted):
            return word
    raise SystemExit(f"{where}: an evidence code the table does not know ({sorted(codes)}); read UniProt's page on evidence again")


ANALYSIS = "sequence analysis"  # UniProt's evidence for what its curators take from a prediction program
OTHER = "other"                 # an experiment, likeness or a curator's own inference stands behind it


def behind(evidences):
    """What a statement or a feature rests on when nothing else stands behind it: the rule
    systems its evidence names, or a sequence analysis. "other" where an experiment,
    likeness or a curator's inference stands behind it too; "not given" where the entry
    gives no evidence code."""
    codes = {item["evidenceCode"] for item in evidences or []}
    if not codes:
        return (NOT_GIVEN,)
    if codes != {"ECO:0000255"}:
        return (OTHER,)
    return tuple(sorted({item.get("source") or ANALYSIS for item in evidences}))


def rules_named(evidences):
    return sorted({f"{item['source']}:{item.get('id')}" for item in evidences or [] if item["evidenceCode"] == "ECO:0000255" and item.get("source")})


def read_entries(d, vocabulary):
    """Every reviewed entry of the proteome: its name, gene, length and level of evidence,
    the places it states, in order, and the features the rules read."""
    results = json.loads(d.text(KB, PLACES_FILE))["results"]
    entries, counts = {}, Counter({"entries that state a place": 0, "comments on an infection, not read": 0})
    for item in results:
        accession = item["primaryAccession"]
        if not item["entryType"].startswith("UniProtKB reviewed"):
            raise SystemExit(f"{accession} is not a reviewed entry")
        description = item["proteinDescription"]
        name = (description.get("recommendedName") or (description.get("submissionNames") or [{}])[0]).get("fullName", {}).get("value", "")
        genes = item.get("genes") or []
        gene = genes[0].get("geneName", {}).get("value", "") if genes else ""
        features = Counter(feature["type"] for feature in item.get("features", []))
        displayed, described = None, 0
        for comment in item.get("comments", []):
            if comment["commentType"] == "ALTERNATIVE PRODUCTS":
                for isoform in comment.get("isoforms", []):
                    status = isoform.get("isoformSequenceStatus")
                    if status == "Displayed":
                        displayed = isoform["name"]["value"]
                    described += status == "Described"
        # The places: comments on where the protein is during an infection are not read.
        comments, states = [], False
        for comment in item.get("comments", []):
            if comment["commentType"] != "SUBCELLULAR LOCATION" or not comment.get("subcellularLocations"):
                continue
            states = True
            note = " ".join(text.get("value", "") for text in comment.get("note", {}).get("texts", []))
            if note.startswith("(Microbial infection)"):
                counts["comments on an infection, not read"] += 1
                continue
            comments.append(comment)
        counts["entries that state a place"] += states
        general = [comment for comment in comments if not comment.get("molecule")]
        of = None
        if general:
            chosen, how = general, "the entry as a whole"
        elif any(comment["molecule"] == f"Isoform {displayed}" for comment in comments):
            chosen, how = [comment for comment in comments if comment["molecule"] == f"Isoform {displayed}"], "the canonical isoform"
        elif comments:
            of = comments[0]["molecule"]
            chosen, how = [comment for comment in comments if comment["molecule"] == of], "another named form"
        else:
            chosen, how = [], None
        if how:
            counts[f"place stated for {how}"] += 1
        statements = []
        for comment in chosen:
            for stated in comment["subcellularLocations"]:
                term = vocabulary.terms.get(stated["location"].get("id"))
                if term is None or term["kind"] != "location" or term["path"] != stated["location"]["value"]:
                    raise SystemExit(f"{accession} states a place the vocabulary does not hold as written: {stated['location']}")
                line = vocabulary.resolve(term["name"])
                if line is None:
                    raise SystemExit(f"the table has no line for {term['name']!r} ({accession}); add one")
                topology, face = stated.get("topology"), stated.get("orientation")
                for part, kind in ((topology, "topology"), (face, "face")):
                    known = vocabulary.terms.get(part.get("id"), {}) if part else None
                    if part and (known.get("kind") != kind or known.get("path") != part["value"]):
                        raise SystemExit(f"{accession} states a {kind} the vocabulary does not hold as written: {part}")
                statements.append({
                    "name": term["name"], "words": stated["location"]["value"], "accession": term["accession"], "shelf": line[0], "kind": line[1], "under": line[3],
                    "topology": topology["id"] if topology else None, "topology_words": topology["value"] if topology else None,
                    "face": vocabulary.terms[face["id"]]["name"] if face else None, "face_accession": face["id"] if face else None,
                    "evidence": evidence_of(stated["location"].get("evidences"), accession),
                    "by_rule": sorted({source.get("source") for source in stated["location"].get("evidences") or [] if source["evidenceCode"] == "ECO:0000255" and source.get("source")}),
                    "topology_evidence": evidence_of(topology.get("evidences"), accession) if topology else None,
                    "behind": behind(stated["location"].get("evidences")), "rules": rules_named(stated["location"].get("evidences")),
                    "topology_behind": behind(topology.get("evidences")) if topology else None,
                    "face_behind": behind(face.get("evidences")) if face else None,
                })
        segment_evidence = {evidence["evidenceCode"] for feature in item.get("features", []) if feature["type"] == "Transmembrane" for evidence in feature.get("evidences", [])}
        signal_evidence = {evidence["evidenceCode"] for feature in item.get("features", []) if feature["type"] == "Signal" for evidence in feature.get("evidences", [])}
        entries[accession] = {
            "id": accession, "name": name, "gene": gene, "length": item["sequence"]["length"],
            "seen": int(item["proteinExistence"].split(":")[0]), "isoforms": 1 + described,
            "statements": statements, "of": of, "segments": features["Transmembrane"], "signal": features["Signal"] > 0,
            "segments_only_predicted": bool(features["Transmembrane"]) and segment_evidence == {"ECO:0000255"},
            "signal_only_predicted": features["Signal"] > 0 and signal_evidence == {"ECO:0000255"},
            "segments_behind": behind([evidence for feature in item.get("features", []) if feature["type"] == "Transmembrane" for evidence in feature.get("evidences", [])]) if features["Transmembrane"] else None,
            "signal_behind": behind([evidence for feature in item.get("features", []) if feature["type"] == "Signal" for evidence in feature.get("evidences", [])]) if features["Signal"] else None,
        }
    if len(entries) != len(results):
        raise SystemExit("two entries share an accession")
    return entries, counts


def read_signatures(d, entries):
    """The InterPro entries and the Gene Ontology terms UniProt gives each entry."""
    lines = d.text(KB, SIGNATURES_FILE).splitlines()
    if lines[0].split("\t") != ["Entry", "InterPro", "Gene Ontology IDs"]:
        raise SystemExit("UniProt's table of signatures and terms is not the one asked for")
    signatures, terms = {}, {}
    for line in lines[1:]:
        accession, found, ontology = line.split("\t")
        signatures[accession] = [signature for signature in found.split(";") if signature]
        terms[accession] = [term.strip() for term in ontology.split(";") if term.strip()]
    if set(signatures) != set(entries):
        raise SystemExit("the two downloads from UniProt are not of the same entries; fetch both again")
    return signatures, terms


# ---------------------------------------------------------------------------------------
# The side of each protein
# ---------------------------------------------------------------------------------------

def side_by_words(statement):
    """The side that the words of one statement give, with the rule's name; or (None, None)."""
    shelf, kind = statement["shelf"], statement["kind"]
    if kind in (INSIDE, OUTSIDE):
        return kind, "place"
    if statement["topology"] in SPANS:
        return ("in", "spans") if kind in (MEMBRANE, WHOLE) else (None, None)
    if statement["face"]:
        side = FACES[statement["face"]].get(shelf)
        if side is None and kind == MEMBRANE:
            raise SystemExit(f"the table has no side for the {statement['face']!r} of a membrane on the shelf {shelf!r}; add one")
        return (side, "face") if side else (None, None)
    if statement["topology"] in ANCHORED and kind in (MEMBRANE, WHOLE) and shelf in AWAY:
        return AWAY[shelf], "anchor"
    return None, None


def place(entry, vocabulary):
    """Where one protein stands: its shelf, side and basis, the rule that gave them, the
    statement that decided and the other statements."""
    statements = entry["statements"]
    of_cell = [statement for statement in statements if statement["kind"] != ELSEWHERE]
    result = lambda shelf, side, basis, rule, decided=None: {
        "shelf": shelf, "side": side, "basis": basis, "rule": rule, "where": decided,
        "also": [statement for statement in statements if statement is not decided],
        "evidence": (decided or (of_cell[0] if of_cell else None) or {}).get("evidence"),
    }
    if not of_cell:
        if entry["segments"]:
            return result("membrane", "in", "predicted", "no place: segment")
        if entry["signal"]:
            return result("membrane", "outside", "predicted", "no place: signal")
        return result(None, "not known", "none", "no place")
    first = of_cell[0]
    side, rule = side_by_words(first)
    if side:
        return result(first["shelf"], side, "stated", rule, first)
    # A later statement that names a part or a kind of the first place, and gives the side.
    for later in of_cell[1:]:
        if first["name"] in vocabulary.broader(later["name"]):
            side, rule = side_by_words(later)
            if side:
                return {**result(later["shelf"], side, "stated", "later part", later), "words_rule": rule}
    # The entry's own features, where one membrane is meant and the words do not say otherwise.
    one_membrane = first["kind"] in (MEMBRANE, WHOLE)
    if entry["segments"] and one_membrane and first["topology"] not in NOT_SPANNING | ANCHORED:
        return result(first["shelf"], "in", "predicted", "segment", first)
    if entry["signal"] and not entry["segments"] and one_membrane and first["shelf"] in AWAY:
        return result(first["shelf"], AWAY[first["shelf"]], "predicted", "signal", first)
    return result(first["shelf"], "not known", "none", "side not stated", first)


# ---------------------------------------------------------------------------------------
# Families and districts, by the rules of the planarian's shelves
# ---------------------------------------------------------------------------------------
#
# A family has the same id in every species only if it is chosen the same way: the rule
# below and the districts' table are those of tools/build_planarian_atlas.py, word for
# word in what they do. tests/human_atlas.test.mjs holds the two files' districts equal.

SHELF_FORMAT = "cells.visualizer.species_proteins@1"
MEMBERS_FORMAT = "cells.visualizer.species_protein_members@1"
SHELVES_FILE = "shelves.json"
TABLE_FILE = "proteins.tsv"
TABLE_COLUMNS = ["id", "gene", "name", "length", "isoforms", "seen", "under", "shelf", "side", "basis", "evidence", "place", "also", "units", "family", "of"]
SIDES = ["outside", "in", "inside", "not known"]
SIDE_TIE = ["in", "outside", "inside", "not known"]  # where a line's members are split evenly
MEMBERS_PER_FILE = 2000
# A family with at most this many members in the whole catalogue has no line of its own:
# it does not open. Its protein is listed with the others like it, and names its family.
# 0 gives every family its lines; the file then passes its limit of 1 MB.
LONE_UP_TO = 1
LIMIT_SHELVES, LIMIT_FILE, LIMIT_FOLDER = 1_000_000, 3_000_000, 3_000_000
# The table writes the basis and the evidence with one letter each, to stay within its size.
BASIS_LETTER = {"stated": "s", "predicted": "p", "none": "n"}
EVIDENCE_LETTER = {"experiment": "e", "similarity": "s", "curator": "c", "rule": "r", NOT_GIVEN: "n"}

DISTRICTS = [
    ("channels", "Channels", [("GO:0015267", "channel activity")]),
    ("transport", "Transporters and pumps", [("GO:0005215", "transporter activity"), ("GO:0055085", "transmembrane transport"), ("GO:0006811", "monoatomic ion transport")]),
    ("signalling", "Receptors and signalling", [("GO:0038023", "signaling receptor activity"), ("GO:0060089", "molecular transducer activity"), ("GO:0007165", "signal transduction"), ("GO:0005102", "signaling receptor binding")]),
    ("genes", "DNA, RNA and making proteins", [("GO:0010467", "gene expression"), ("GO:0006259", "DNA metabolic process"), ("GO:0003677", "DNA binding"), ("GO:0003723", "RNA binding"), ("GO:0140110", "transcription regulator activity"), ("GO:0006355", "regulation of DNA-templated transcription"), ("GO:0006325", "chromatin organization"), ("GO:0005840", "ribosome"), ("GO:0140640", "catalytic activity, acting on a nucleic acid")]),
    ("proteins", "Protein folding, change, sorting and breakdown", [("GO:0006457", "protein folding"), ("GO:0006508", "proteolysis"), ("GO:0036211", "protein modification process"), ("GO:0015031", "protein transport"), ("GO:0016192", "vesicle-mediated transport"), ("GO:0140096", "catalytic activity, acting on a protein")]),
    ("structure", "Cytoskeleton, movement and adhesion", [("GO:0005856", "cytoskeleton"), ("GO:0007010", "cytoskeleton organization"), ("GO:0003774", "cytoskeletal motor activity"), ("GO:0007018", "microtubule-based movement"), ("GO:0007155", "cell adhesion"), ("GO:0031012", "extracellular matrix"), ("GO:0005929", "cilium"), ("GO:0005198", "structural molecule activity")]),
    ("metabolism", "Enzymes and metabolism", [("GO:0003824", "catalytic activity"), ("GO:0008152", "metabolic process")]),
]
OTHER_DISTRICT = ("other", "Other functions")
NO_DISTRICT = ("unclassed", "Not classed by function")
DISTRICT_ORDER = [key for key, _, _ in DISTRICTS] + [OTHER_DISTRICT[0], NO_DISTRICT[0]]
DISTRICT_LABEL = {**{key: label for key, label, _ in DISTRICTS}, OTHER_DISTRICT[0]: OTHER_DISTRICT[1], NO_DISTRICT[0]: NO_DISTRICT[1]}


def read_entry_names(d):
    entries = {}
    for line in d.text(IPR, "entry.list").splitlines()[1:]:
        columns = line.split("\t")
        if len(columns) >= 3:
            entries[columns[0]] = {"type": columns[1], "name": columns[2]}
    return entries


def read_hierarchy(d):
    """InterPro's tree: each entry's parent, the broader entry it is a kind of."""
    parent, stack = {}, []
    for line in d.text(IPR, "ParentChildTreeFile.txt").splitlines():
        if not line.strip():
            continue
        depth = (len(line) - len(line.lstrip("-"))) // 2
        accession = line.lstrip("-").split("::")[0]
        stack = stack[:depth]
        if depth:
            parent[accession] = stack[-1]
        stack.append(accession)
    return parent


def read_family_terms(d):
    """InterPro's mapping of its entries to Gene Ontology terms."""
    terms = defaultdict(list)
    for line in d.text(IPR, "interpro2go").splitlines():
        found = re.match(r"InterPro:(IPR\d+) .* ; (GO:\d+)$", line)
        if found and found.group(2) not in terms[found.group(1)]:
            terms[found.group(1)].append(found.group(2))
    return dict(terms)


def read_ontology(d):
    """The Gene Ontology: each term's name and the broader terms it is a kind or a part of."""
    terms, current = {}, None
    text = d.text(GO, "go-basic.obo")
    for line in text.splitlines():
        if line == "[Term]":
            current = {"up": [], "alt": []}
            continue
        if line.startswith("["):
            current = None
            continue
        if current is None or ": " not in line:
            continue
        key, value = line.split(": ", 1)
        if key == "id":
            terms[value] = current
        elif key == "name":
            current["name"] = value
        elif key == "is_a":
            current["up"].append(value.split(" ! ")[0])
        elif key == "relationship" and value.startswith("part_of "):
            current["up"].append(value.split()[1])
        elif key == "alt_id":
            current["alt"].append(value)
        elif key == "is_obsolete":
            current["obsolete"] = True
        elif key == "replaced_by":
            current["replaced_by"] = value
    for term in list(terms):
        for other in terms[term]["alt"]:
            terms.setdefault(other, {"same_as": term})
    version = re.search(r"^data-version: (\S+)", text[:400], re.M)
    for _, _, wanted in DISTRICTS:
        for term, name in wanted:
            if terms.get(term, {}).get("name") != name:
                raise SystemExit(f"the ontology no longer calls {term} {name!r}; choose the districts' terms again")
    return terms, version.group(1)


def broader_terms(terms):
    """For a term, itself and every broader term, by the kind-of and part-of links."""
    memo = {}

    def up(term):
        if term not in memo:
            out = {term}
            for other in terms[term]["up"]:
                if other in terms:
                    out |= up(other)
            memo[term] = out
        return memo[term]

    def usable(term):
        entry = terms.get(term)
        if entry is None:
            return None
        if "same_as" in entry:
            return entry["same_as"]
        if entry.get("obsolete"):
            return usable(entry["replaced_by"]) if entry.get("replaced_by") else None
        return term

    return up, usable


def ontology_citation(d):
    """The two papers the Gene Ontology asks to be cited, in its own page's words."""
    page = plain(d.text(GO, "go_citation_policy.html"))
    first = re.search(r"(Ashburner et al\. Gene ontology: tool for the unification of biology\. [^\[]*?DOI: \S+)", page)
    latest = re.search(r"(The Gene Ontology Consortium\. The Gene Ontology knowledgebase in \d{4}\. [^\[]*?DOI: \S+)", page)
    if not first or not latest:
        raise SystemExit("the Gene Ontology's saved page no longer names the two papers to cite; read it again")
    return f"{first.group(1)}; {latest.group(1)}"


class Filing:
    """One family for each protein, and the district its terms put it in."""

    def __init__(self, d, entries):
        self.names = read_entry_names(d)
        self.parent = read_hierarchy(d)
        self.release = re.search(r"Release ([\d.]+),", d.text(IPR, "release_notes.txt")).group(1)
        self.signatures, self.entry_terms = read_signatures(d, entries)
        self.signature_terms = read_family_terms(d)
        self.terms, self.ontology = read_ontology(d)
        self.up, self.usable = broader_terms(self.terms)
        self.kind = lambda accession: self.names.get(accession, {}).get("type")
        self.file_proteins()
        self.class_proteins()

    def depth(self, accession):
        depth = 0
        while accession in self.parent:
            accession, depth = self.parent[accession], depth + 1
        return depth

    def broader(self, accession):
        out = []
        while accession in self.parent:
            accession = self.parent[accession]
            out.append(accession)
        return out

    def file_proteins(self):
        """family[id] is the family the protein is filed under; part[id] the part of "no family"."""
        narrowest, carried = {}, Counter()
        for protein, found in self.signatures.items():
            families = [s for s in found if self.kind(s) == "Family"]
            covered = {b for family in families for b in self.broader(family)}
            narrowest[protein] = [family for family in families if family not in covered]
            carried.update(set(found))
        held = Counter(family for families in narrowest.values() for family in families)
        self.family, self.part, self.several = {}, {}, 0
        for protein, families in narrowest.items():
            if families:
                # The narrowest family; of several unrelated ones, the deepest in InterPro's
                # tree, then the one fewest proteins of this catalogue are in, then the first.
                self.several += len(families) > 1
                self.family[protein] = min(families, key=lambda f: (-self.depth(f), held[f], f))
                continue
            wider = [s for s in self.signatures[protein] if self.kind(s) == "Homologous_superfamily"]
            if wider:
                self.part[protein] = min(wider, key=lambda s: (carried[s], s))
            else:
                self.part[protein] = "other-signature" if self.signatures[protein] else "no-signature"
        self.retired = len({s for found in self.signatures.values() for s in found if s not in self.names})

    def class_proteins(self):
        """classed[id] is the district the protein's own terms put it in."""
        self.classed, self.dropped, self.matched = {}, set(), Counter()
        for protein, found in self.signatures.items():
            direct = [term for signature in found for term in self.signature_terms.get(signature, [])] + self.entry_terms[protein]
            terms = set()
            for term in direct:
                usable = self.usable(term)
                if usable:
                    terms |= self.up(usable)
                else:
                    self.dropped.add(term)
            hits = [key for key, _, wanted in DISTRICTS if any(term in terms for term, _ in wanted)]
            self.matched[len(hits)] += 1
            self.classed[protein] = hits[0] if hits else OTHER_DISTRICT[0] if terms else NO_DISTRICT[0]

    def district(self, proteins, loose=False):
        """A family's members are one kind of protein, so the district most of its classed
        members fall in speaks for it; of equal counts, the first district. A part of
        "no family" is a looser grouping (loose): it stands in a district only if more
        than half of all its members fall there."""
        found = Counter(self.classed[protein] for protein in proteins)
        order = [key for key, _, _ in DISTRICTS]
        best = max(order, key=lambda key: (found.get(key, 0), -order.index(key)))
        if loose:
            best = max([*order, OTHER_DISTRICT[0]], key=lambda key: found.get(key, 0))
            return best if 2 * found.get(best, 0) > len(proteins) else NO_DISTRICT[0]
        if found.get(best):
            return best
        return OTHER_DISTRICT[0] if found.get(OTHER_DISTRICT[0]) else NO_DISTRICT[0]


def majority(sides):
    """The side most members sit on; of equals, the first in SIDE_TIE."""
    return max(SIDE_TIE, key=lambda side: (sides.get(side, 0), -SIDE_TIE.index(side)))


def ordered_sides(counts):
    return {side: counts[side] for side in SIDES if counts.get(side)}


def shelf_rank(shelf):
    return SHELF_IDS.index(shelf) if shelf is not None else len(SHELF_IDS)


PART_KIND = lambda part: "superfamily" if part.startswith("IPR") else "other signature" if part == "other-signature" else "no signature"
PART_LABEL = {"other-signature": "A domain, repeat or site signature, and no family or superfamily", "no-signature": "No signature of any kind"}
PART_RANK = {"superfamily": 0, "other signature": 1, "no signature": 2}
LONE_LABEL = "The only member of its family"


def make_lines(entries, placed, filing, units, lone_up_to=None):
    """The lines of the file, in the order the members follow: a family's line for each
    shelf that holds members of it, then the proteins that are the only member of their
    family, by shelf, district and side, then the parts of "no family" for each shelf."""
    lone_up_to = LONE_UP_TO if lone_up_to is None else lone_up_to
    order = lambda protein: (entries[protein]["gene"] == "", natural(entries[protein]["gene"].upper()), protein)
    total = Counter(filing.family.values())
    grouped, lone, parts = defaultdict(list), defaultdict(list), defaultdict(list)
    for protein in sorted(entries, key=order):
        shelf, side = placed[protein]["shelf"], placed[protein]["side"]
        if protein in filing.family:
            family = filing.family[protein]
            if total[family] <= lone_up_to:
                lone[shelf, filing.classed[protein], side].append(protein)
            else:
                grouped[family, shelf].append(protein)
        else:
            parts[filing.part[protein], shelf].append(protein)
    held = lambda proteins: sorted({unit for protein in proteins for unit in units.get(protein, ())}, key=natural)
    sides_of = lambda proteins: Counter(placed[protein]["side"] for protein in proteins)
    lines = []
    for (family, shelf), proteins in grouped.items():
        sides = sides_of(proteins)
        lines.append({"what": "family", "id": family, "label": filing.names[family]["name"], "shelf": shelf, "side": majority(sides), "group": filing.district(proteins), "sides": sides, "proteins": proteins, "units": held(proteins), "total": total[family]})
    lines.sort(key=lambda line: (shelf_rank(line["shelf"]), DISTRICT_ORDER.index(line["group"]), -len(line["proteins"]), line["id"]))
    alone = []
    for (shelf, group, side), proteins in lone.items():
        alone.append({"what": "lone", "id": f"lone-{group}-{side.replace(' ', '-')}", "label": LONE_LABEL, "kind": "lone", "shelf": shelf, "side": side, "group": group, "sides": sides_of(proteins), "proteins": proteins, "units": held(proteins)})
    alone.sort(key=lambda line: (shelf_rank(line["shelf"]), DISTRICT_ORDER.index(line["group"]), SIDES.index(line["side"])))
    rest = []
    for (part, shelf), proteins in parts.items():
        sides = sides_of(proteins)
        rest.append({"what": "part", "id": part, "label": filing.names[part]["name"] if part.startswith("IPR") else PART_LABEL[part], "kind": PART_KIND(part), "shelf": shelf, "side": majority(sides), "group": filing.district(proteins, loose=True), "sides": sides, "proteins": proteins, "units": held(proteins)})
    rest.sort(key=lambda line: (shelf_rank(line["shelf"]), PART_RANK[line["kind"]], -len(line["proteins"]), line["id"]))
    # The members' files: lines in their order, a new file where the next line would take
    # the file past its size; a line larger than a file has one of its own.
    file_index, used = 0, 0
    for line in [*lines, *alone, *rest]:
        count = len(line["proteins"])
        if used and used + count > MEMBERS_PER_FILE:
            file_index, used = file_index + 1, 0
        line["file"], line["at"] = f"members-{file_index:02d}.json", [used, used + count]
        used += count
    return lines, alone, rest


def line_row(line, columns):
    values = {**line, "count": len(line["proteins"]), "sides": ordered_sides(line["sides"])}
    return [values[column] for column in columns]


FAMILY_COLUMNS = ["id", "label", "shelf", "side", "group", "count", "sides", "file", "at", "units", "total"]
PART_COLUMNS = ["id", "label", "kind", "shelf", "side", "group", "count", "sides", "file", "at", "units"]
compact = lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def rows_size(lines, columns):
    """The bytes the lines take in the file, each on a row of its own."""
    return sum(len(("  " + compact(line_row(line, columns)) + ",\n").encode("utf-8")) for line in lines)


def code(statement):
    """A statement as the table writes it: UniProt's identifiers of the place, the topology
    and the face, without their prefix."""
    return ".".join(part[3:] for part in (statement["accession"], statement["topology"], statement["face_accession"]) if part)


def words(statement):
    return "; ".join(part for part in (statement["words"], statement["topology_words"], statement["face"]) if part)


# ---------------------------------------------------------------------------------------
# Build: the three files
# ---------------------------------------------------------------------------------------

def account(entries, placed):
    """What the placements rest on that a rule system or a prediction program computed, by
    UniProt's evidence codes and rule identifiers. Two kinds are kept apart: a side that
    this file reads from a feature (basis predicted), and a curator's statement that
    itself rests on such a result. A protein is counted once for each owner it rests on."""
    on = defaultdict(lambda: defaultdict(set))  # owner -> what rests on it -> proteins
    rule_ids = defaultdict(Counter)
    for accession, item in placed.items():
        entry, decided, rule = entries[accession], item["where"], item["rule"]
        words_rule = item.get("words_rule", rule)
        if decided:
            for owner in decided["behind"]:
                if owner == ANALYSIS:
                    # A place stated on a sequence analysis: inferred from the predicted feature the entry carries.
                    owner = "segments" if entry["segments_behind"] == (ANALYSIS,) else "signal" if entry["signal_behind"] == (ANALYSIS,) else "unnamed analysis"
                on[owner]["the stated place"].add(accession)
            for named in decided["rules"] if set(decided["behind"]) - {OTHER, NOT_GIVEN, ANALYSIS} else []:
                rule_ids[named.split(":")[0]][named.split(":")[1]] += 1
            word = decided["topology_behind"] if words_rule in ("spans", "anchor") else decided["face_behind"] if words_rule == "face" else None
            for owner in word or ():
                what = {"spans": "the statement that it spans the membrane", "anchor": "the stated GPI anchor", "face": "the stated face"}[words_rule]
                on["big-PI" if owner == ANALYSIS and words_rule == "anchor" else "segments" if owner == ANALYSIS else owner][what].add(accession)
        if rule in ("segment", "no place: segment"):
            for owner in entry["segments_behind"]:
                on["segments" if owner == ANALYSIS else owner]["a side read from its segments"].add(accession)
        if rule in ("signal", "no place: signal"):
            for owner in entry["signal_behind"]:
                on["signal" if owner == ANALYSIS else owner]["a side read from its signal peptide"].add(accession)
    out = {}
    for owner, found in on.items():
        if owner in (OTHER, NOT_GIVEN):
            continue
        out[owner] = {"placements": len(set().union(*found.values())), **{what: len(proteins) for what, proteins in sorted(found.items())}}
    return out, {owner: dict(sorted(found.items(), key=lambda pair: (-pair[1], pair[0]))) for owner, found in rule_ids.items()}


DTU_LICENCE = "Academic licence of DTU Health Tech: free to publicly funded academic, education or research institutions for internal research, and any other user must obtain a commercial licence. It is a licence of the program: no clause speaks of predictions made with it"
NOT_RUN = "Nothing was downloaded from it but its statement of terms, and the program was not run here."
FOUR_SEGMENTS = "One of the four methods UniProt names for the membrane-spanning segments of its reviewed entries; it keeps a segment that at least two of them find, and does not say which"
FOUR_SIGNALS = "One of the four methods UniProt names for the signal peptides of its reviewed entries; it keeps a signal that at least two of them find, and does not say which"
UPSTREAM = ["PROSITE", "HAMAP", "TMHMM", "Phobius", "SignalP", "TargetP", "Memsat", "Predotar", "big-PI"]  # each a source read through UniProt


def compartment(term):
    """The compartment a term of the table belongs to: its lumen and its matrix are the compartment's."""
    return re.sub(r" (lumen|matrix)$", "", term).replace("Cytoplasmic vesicle", "Vesicle")


def unit_products(snapshot):
    """The inventory's own human entries: accession -> the units that name it, and its roles."""
    units, roles = defaultdict(set), defaultdict(set)
    for unit in snapshot["units"]:
        for product in unit.get("products") or []:
            if product.get("human_uniprot"):
                units[product["human_uniprot"]].add(unit["id"])
                roles[product["human_uniprot"]].add(product.get("role", ""))
    return {accession: sorted(found, key=natural) for accession, found in units.items()}, roles


def build(datasets_folder, snapshot, terms_folder=None):
    d = Datasets(datasets_folder)
    # The terms that the other species' tools saved: in the folder that holds every species' downloads.
    shared = Datasets(terms_folder or Path(datasets_folder).resolve().parent)
    said = check_terms(d, shared)
    vocabulary = Vocabulary(d)
    entries, read = read_entries(d, vocabulary)
    filing = Filing(d, entries)
    units, roles = unit_products(snapshot)
    missing = sorted(set(units) - set(entries))
    placed = {accession: place(entry, vocabulary) for accession, entry in entries.items()}

    # What the downloads themselves say of the proteome, checked against what was read.
    proteome = json.loads(d.text(KB, f"proteome_{PROTEOME}.json"))
    release = d.entry(KB, PLACES_FILE)["x_uniprot_release"]
    stated = {"reviewed": d.total(KB, "count_reviewed.json"), "sequences": d.total(KB, "count_reviewed_with_isoforms.json"), "unreviewed": d.total(KB, "count_unreviewed.json"), "all": d.total(KB, "count_all.json"), "with_place": d.total(KB, "count_reviewed_with_place.json"), "genes": proteome["geneCount"]}
    if any(d.entry(KB, file)["x_uniprot_release"] != release for file in (SIGNATURES_FILE, "count_reviewed.json", "count_reviewed_with_isoforms.json", "count_unreviewed.json", "count_all.json", "count_reviewed_with_place.json")) or vocabulary.release != release:
        raise SystemExit("the downloads from UniProt are not of one release; fetch them again")
    if stated["reviewed"] != len(entries) or stated["sequences"] != sum(entry["isoforms"] for entry in entries.values()) or stated["with_place"] != read["entries that state a place"]:
        raise SystemExit(f"the entries read do not add up to UniProt's own counts: {stated}")
    if stated["reviewed"] + stated["unreviewed"] != stated["all"] or proteome["proteinCount"] != stated["all"]:
        raise SystemExit("the proteome's counts do not add up")

    lines, alone, rest = make_lines(entries, placed, filing, units)
    sequence = [protein for line in [*lines, *alone, *rest] for protein in line["proteins"]]
    if len(sequence) != len(entries) or len(set(sequence)) != len(entries):
        raise SystemExit("a protein is filed twice or not at all")

    # --- counts ---------------------------------------------------------------------------
    key = lambda shelf: NO_SHELF if shelf is None else shelf
    all_sides = Counter(item["side"] for item in placed.values())
    shelf_counts = {name: {side: 0 for side in SIDES} for name in [*SHELF_IDS, NO_SHELF]}
    for item in placed.values():
        shelf_counts[key(item["shelf"])][item["side"]] += 1
    bases = Counter((item["side"], item["basis"]) for item in placed.values())
    rules = Counter(item["rule"] for item in placed.values())
    evidence = Counter(item["evidence"] for item in placed.values() if item["evidence"])
    family_total = Counter(filing.family.values())
    distinct = len({line["id"] for line in lines})
    lone_families = sum(1 for count in family_total.values() if count <= LONE_UP_TO)
    shelves = []
    for shelf in SHELVES:
        on = [line for line in lines if line["shelf"] == shelf["id"]]
        here = sum(len(line["proteins"]) for line in alone if line["shelf"] == shelf["id"])
        shelves.append({**shelf, **({"note": SHELF_NOTES[shelf["id"]]} if shelf["id"] in SHELF_NOTES else {}), "proteins": sum(shelf_counts[shelf["id"]].values()), "families": len(on) + here, "lines": len(on), "lone": here, "no_family": sum(len(line["proteins"]) for line in rest if line["shelf"] == shelf["id"])})
    none = [line for line in lines if line["shelf"] is None]
    here = sum(len(line["proteins"]) for line in alone if line["shelf"] is None)
    no_shelf = {"proteins": sum(shelf_counts[NO_SHELF].values()), "families": len(none) + here, "lines": len(none), "lone": here, "no_family": sum(len(line["proteins"]) for line in rest if line["shelf"] is None)}
    groups = []
    for group in DISTRICT_ORDER:
        wanted = next((wanted for key_, _, wanted in DISTRICTS if key_ == group), None)
        said_from = "Gene Ontology terms: " + ", ".join(f"{name} ({term})" for term, name in wanted) if wanted else "The line's proteins carry Gene Ontology terms, and none of the districts' terms" if group == OTHER_DISTRICT[0] else "The line's proteins carry no Gene Ontology term"
        on = [line for line in lines if line["group"] == group]
        groups.append({"id": group, "label": DISTRICT_LABEL[group], "from": said_from, "lines": len(on), "proteins": sum(len(line["proteins"]) for line in on), "lone": sum(len(line["proteins"]) for line in alone if line["group"] == group)})

    # --- the places the entries state first, with the table's line for each ------------------
    first_places = Counter(item["where"]["name"] for item in placed.values() if item["where"])
    used = {statement["name"] for entry in entries.values() for statement in entry["statements"]}
    place_rows = []
    for name in sorted(used, key=lambda name: (-first_places[name], name)):
        shelf, kind, how, under = vocabulary.resolve(name)
        place_rows.append([vocabulary.by_name[name]["accession"], vocabulary.by_name[name]["path"], shelf, kind, how, under, first_places[name]])
    codes_used = {part for entry in entries.values() for statement in entry["statements"] for part in code(statement).split(".")}
    place_words = {term["accession"][3:]: term["path"] for term in sorted(vocabulary.terms.values(), key=lambda term: term["accession"]) if term["accession"][3:] in codes_used}

    # --- what rests on rules and on predictors ----------------------------------------------
    by_rule = Counter()
    for item in placed.values():
        if item["where"] and item["where"]["evidence"] == "rule":
            for source in item["where"]["by_rule"] or ["sequence analysis"]:
                by_rule[source] += 1
    spans_by = Counter(item["where"]["topology_evidence"] for item in placed.values() if item["rule"] == "spans")
    feature_rules = sum(rules[rule] for rule in ("segment", "signal", "no place: segment", "no place: signal"))
    by_segment = [a for a, item in placed.items() if item["rule"] in ("segment", "no place: segment")]
    by_signal = [a for a, item in placed.items() if item["rule"] in ("signal", "no place: signal")]
    rests = {
        "segment placements": len(by_segment), "of them by sequence analysis alone": sum(1 for a in by_segment if entries[a]["segments_only_predicted"]),
        "signal placements": len(by_signal), "of them by sequence analysis alone ": sum(1 for a in by_signal if entries[a]["signal_only_predicted"]),
        "spans stated on a sequence analysis": spans_by["rule"], "places stated on a sequence analysis": by_rule["sequence analysis"],
        "places stated on a PROSITE rule": by_rule["PROSITE-ProRule"], "places stated on a HAMAP rule": by_rule["HAMAP-Rule"],
    }
    if set(by_rule) - {"sequence analysis", "PROSITE-ProRule", "HAMAP-Rule"}:
        raise SystemExit(f"a statement rests on a rule system the sources do not name: {sorted(by_rule)}")
    # Every placement that rests on what a rule system or a program computed, by owner.
    resting, rule_ids = account(entries, placed)
    if set(resting) - {"PROSITE-ProRule", "HAMAP-Rule", "RuleBase", "segments", "signal", "big-PI", "unnamed analysis"}:
        raise SystemExit(f"a placement rests on a rule system or an analysis the sources do not name: {sorted(resting)}")
    of = lambda owner, what="placements": resting.get(owner, {}).get(what, 0)
    PLACE, SPANS, FACE, ANCHOR = "the stated place", "the statement that it spans the membrane", "the stated face", "the stated GPI anchor"
    FROM_SEGMENTS, FROM_SIGNAL = "a side read from its segments", "a side read from its signal peptide"
    most = lambda owner: ", ".join(f"{rule} for {count:,}" for rule, count in list(rule_ids.get(owner, {}).items())[:3])

    cite_uniprot = "The UniProt Consortium, UniProt: the Universal Protein Knowledgebase in 2025, Nucleic Acids Res. 53:D609-D617 (2025)"
    cite_interpro = "Blum and others (2025) InterPro: the protein sequence classification resource in 2025. Nucleic Acids Res 53:D444-D456."
    header = {
        "format": SHELF_FORMAT,
        "species": "human",
        "made": None,  # set below, once every download has been read
        "from": (
            f"UniProtKB release {release}: the {stated['reviewed']:,} reviewed entries of the human reference proteome {PROTEOME}, one canonical protein each. "
            f"Their entries describe {stated['sequences'] - stated['reviewed']:,} further isoforms ({stated['sequences']:,} sequences in all), given here as a count on each protein. "
            f"The proteome's {stated['unreviewed']:,} unreviewed entries are not listed: it holds {stated['all']:,} entries in all, for {stated['genes']:,} genes."
        ),
        "from_counts": {"reviewed": stated["reviewed"], "isoforms": stated["sequences"] - stated["reviewed"], "sequences": stated["sequences"], "unreviewed": stated["unreviewed"], "entries": stated["all"], "genes": stated["genes"], "state_a_place": stated["with_place"]},
        "predicted": False,
        "shelves": shelves,
        "no_shelf": no_shelf,
        "groups": groups,
        "groups_from": (
            "A protein's Gene Ontology terms are those InterPro maps to any of its signatures and those UniProt gives its entry. "
            "With every broader term (by the ontology's kind-of and part-of links), the protein falls in the first district, in the order listed, one of whose terms it carries. "
            "A family's line stands in the district most of its classed members on that shelf fall in; of equal counts, the first listed. A protein that is the only member of its family stands in its own district. "
            "A part of no_family is a looser grouping: it stands in a district only if more than half of all its members on that shelf fall there. The choice of the districts' terms and their order is the viewer's, and is the planarian's."
        ),
        "family_from": (
            f"A family is an InterPro entry of the type Family (InterPro {filing.release}). A protein is filed under the narrowest family among the InterPro entries UniProt gives it: one that is not a broader kind of another it carries, by InterPro's tree of entries. "
            f"Where several unrelated families remain ({filing.several:,} proteins), it is the deepest in that tree, then the one fewest proteins of this catalogue are in, then the first by accession. This is the rule of the planarian's file, so a family has the same id in both."
        ),
        "family_columns": FAMILY_COLUMNS,
        "family_notes": {
            "lines": "A family has one line for each shelf that holds members of it, and one with a null shelf for its members that are on no shelf. A line is identified by id and shelf together; side, group, count, sides, file, at and units are of its members on that shelf alone.",
            "side": "The side most of the line's members sit on; of equal counts, a membrane first.",
            "units": "The inventory units whose own human entries are members on this line.",
            "total": "The family's members on every shelf and on none.",
            "counts": "distinct_families is the number of families that have lines; families_in_all counts also the families of one, whose proteins are under 'lone'. In 'shelves' and 'no_shelf', 'families' is every family with a member there (its lines and its lone proteins), 'lines' the families' lines there, 'lone' the proteins that are the only member of their family, 'no_family' those with none.",
        },
    }
    lone_sides = Counter(side for line in alone for side, count in line["sides"].items() for _ in range(count))
    lone = {
        "label": LONE_LABEL,
        "count": sum(len(line["proteins"]) for line in alone),
        "families": lone_families,
        "sides": ordered_sides(lone_sides),
        "parts_from": (
            f"A family with a single member in this catalogue does not open, so it has no line among the families: {lone_families:,} families of one. "
            "Their proteins are listed here together, one part for each shelf, district and side, and each names its family in its mark 'family'. A part is not a family."
        ),
        "part_columns": PART_COLUMNS,
    }
    no_family_sides = Counter(placed[protein]["side"] for protein in filing.part)
    no_family = {
        "label": "No family assigned",
        "count": len(filing.part),
        "sides": ordered_sides(no_family_sides),
        "parts_from": (
            "A protein with no family is filed under one part. If it carries an InterPro entry of the type Homologous superfamily, the part is that superfamily: a wider grouping than a family, by shared structure. "
            "Of several superfamilies it is the one fewest proteins of this catalogue carry, then the first by accession. The other two parts hold the proteins with only a domain, repeat or site signature, and those with no signature at all. A part has one line for each shelf, as a family has."
        ),
        "part_columns": PART_COLUMNS,
    }
    files = sorted({line["file"] for line in [*lines, *alone, *rest]})
    predictors = "TMHMM, Memsat, Phobius and a hydrophobic moment plot for the segments; Phobius, Predotar, SignalP and TargetP for the signal peptides"
    tail = {
        "member_columns": ["id", "label", "gene", "side", "basis", "length", "unit", "marks"],
        "members_from": {
            "table": f"data/proteins/human/{TABLE_FILE}",
            "format": MEMBERS_FORMAT,
            "order": f"The table's lines are the members in order: every line of the families as listed here, then every part of 'lone', then every part of 'no_family'; within each, by gene name. A line's members are the next 'count' lines of the table. For a family's line and for a part of no_family, 'under' is its id and 'shelf' its shelf (empty for none); for a part of 'lone', 'under' is the protein's own family and 'family' that family's name.",
            "files": f"A file holds the members of consecutive lines: a new file begins where the next line would take it past {MEMBERS_PER_FILE:,} members, so a line is never split, and one larger than that has a file of its own. 'file' names the file and 'at' the first and one past the last of its members there. A member's shelf is its line's.",
            "places": "In the table a stated place is written with UniProt's identifiers, without their prefix: the place, then the topology and the face where the entry states them, joined by a full stop (0039.9909 is SL-0039 with SL-9909). 'place_words' gives the words of each.",
            "letters": {"basis": {letter: word for word, letter in BASIS_LETTER.items()}, "evidence": {letter: word for word, letter in EVIDENCE_LETTER.items()}, "seen": {str(level): SEEN[level] for level in sorted(SEEN)}},
            "step": "python3 tools/build_human_atlas.py members --out DIR writes the files from the two files.",
        },
        "side_notes": {
            "stated": (
                "The protein's reviewed UniProtKB entry states where it is, and the first place it states decides the shelf and the side: a place within a compartment or beyond a membrane, a membrane the protein is said to span, or a membrane with the face the protein is on. "
                "A GPI anchor with no face stated is taken to hold the protein on the face away from the cytoplasm, as UniProt's own page on lipid anchors describes it. Where the first place names no side, a later statement of the same entry that names a part of that place decides. "
                "Statements on where a protein is during an infection are not read, and a place that is not of the cell (a virus particle, a target cell's membrane) is passed over. The mark 'evidence' says what stands behind the statement."
            ),
            "predicted": (
                "Read from the entry's own features, where its words do not give the side. A membrane-spanning segment puts the protein in the membrane; a signal peptide with no such segment puts it on the side away from the cytoplasm: outside the cell, or within a compartment. "
                f"Where the entry states the membrane or the compartment, the protein stands on that shelf ({rules['segment'] + rules['signal']:,} proteins); where it states no place, on the shelf of a membrane that is not named ({rules['no place: segment'] + rules['no place: signal']:,} proteins). "
                f"UniProt's curators annotate these features from experiments, from likeness to other proteins and from prediction; its own pages name the predictors: {predictors}. Each is named among the sources, with its terms and what rests on it: TMHMM, SignalP, TargetP and Phobius are given out for academic use. "
                "A segment is used only where one membrane is meant: not in the mitochondrion, whose two membranes are on different shelves, nor in a region of the cell that holds other membranes."
            ),
            "none": (
                "The entry states a membrane or a compartment and not the side (the protein then stands apart beside that shelf, with the place in its mark 'where'), or it states no place of the cell and carries no membrane-spanning segment and no signal peptide (the protein is then on no shelf). Nothing is placed by guess."
            ),
        },
        "placed_by": [{"rule": rule, "basis": basis, "what": what, "proteins": rules[rule]} for rule, basis, what in RULES_USED],
        "place_kinds": KINDS,
        "place_columns": ["id", "words", "shelf", "names", "resolved", "under", "first"],
        "place_notes": "Every place the entries state, in UniProt's words, with the shelf and what the place names against its membrane (place_kinds), how the table's line was reached and which of the table's terms it rests on, and how many proteins it places as the statement that decided.",
    }
    marks = {
        "isoforms": {"label": "Isoforms described", "values": "number", "measured": False, "note": "The canonical sequence and the other sequences its entry describes. The marker stands for the canonical one.", "source": "UniProt"},
        "seen": {"label": "Evidence that the protein exists", "values": [SEEN[level] for level in sorted(SEEN)], "measured": False, "note": "UniProt's level of evidence for the entry: at protein level, at transcript level, inferred from homology, predicted, or uncertain.", "source": "UniProt"},
        "evidence": {"label": "What stands behind the stated place", "values": [word for word, _, _ in EVIDENCE] + [NOT_GIVEN], "measured": False, "note": "From UniProt's evidence codes on the statement: " + "; ".join(f"{word}: {what}" for word, _, what in EVIDENCE) + f"; {NOT_GIVEN}: the entry gives no code, an older curated statement. Of several, the first in this order.", "source": "UniProt"},
        "where": {"label": "Stated place", "values": "text", "measured": False, "note": "The statement that decided the shelf, in UniProt's words: the place, then the topology and the face where the entry states them.", "source": "UniProt"},
        "also": {"label": "Also stated", "values": "text", "measured": False, "note": "The entry's other statements of place, in order and in UniProt's words.", "source": "UniProt"},
        "family": {"label": "Family, of which it is the only member here", "values": "text", "measured": False, "note": "The InterPro family's accession and name, for a protein listed among the only members of their families.", "source": "InterPro"},
        "of": {"label": "Stated for", "values": "text", "measured": False, "note": "The named form of the protein that the place is stated for, where the entry states none for the protein as a whole or for its canonical isoform.", "source": "UniProt"},
    }
    counts = {side: all_sides.get(side, 0) for side in SIDES}
    closing = {
        "marks": marks,
        "counts": counts,
        "shelf_counts": shelf_counts,
        "by_basis": {side: {basis: bases[side, basis] for basis in ("stated", "predicted", "none") if bases.get((side, basis))} for side in SIDES},
        "by_evidence": {word: evidence.get(word, 0) for word in [word for word, _, _ in EVIDENCE] + [NOT_GIVEN]},
        "sources": None,  # set below
    }
    made = max(d.last_day(), shared.last_day())
    header["made"] = made
    closing["sources"] = [
        {
            "name": "UniProt", "url": "https://www.uniprot.org/", "release": release, "accessed": d.day(KB, PLACES_FILE), "licence": "CC BY 4.0", "class": "permissive", "cite": cite_uniprot,
            "holds": f"for each reviewed entry of the human reference proteome: its name, gene, length and level of evidence, the places it states with the evidence for each, its membrane-spanning segments and signal peptide, the isoforms it describes, the InterPro entries and the Gene Ontology terms UniProt gives it; and UniProt's vocabulary of places. Its own pages name the programs behind the segments and signal peptides it predicts ({predictors}); each is a source below, with what rests on it. Of UniProt's own: {of('RuleBase'):,} statements that a protein spans a membrane rest on a rule of its rule base (RuleBase), and {of('unnamed analysis'):,} stated places rest on a sequence analysis in entries that carry no segment or signal peptide of that kind, for which it names no program",
        },
        {
            "name": "InterPro", "url": "https://www.ebi.ac.uk/interpro/", "release": filing.release, "accessed": d.day(IPR, "entry.list"), "licence": "CC0 1.0", "class": "permissive", "cite": cite_interpro,
            "holds": "the type and name of each entry, the tree of broader and narrower entries, and the mapping of entries to Gene Ontology terms",
        },
        {
            "name": "Gene Ontology", "url": "https://geneontology.org/", "release": filing.ontology, "accessed": d.day(GO, "go-basic.obo"), "licence": "CC BY 4.0", "class": "permissive", "cite": ontology_citation(d),
            "holds": "the names of terms and which term is a kind or a part of which; no term's text is copied beyond the names of the districts' terms",
        },
        # The rule systems and the programs behind what UniProt's entries state by rule or by
        # sequence analysis: each a source of its own, with its terms as its own page states
        # them, read through UniProt, and with what rests on it here.
        {
            "name": "PROSITE", "url": "https://prosite.expasy.org/prosite_license.html", "licence": "CC BY-NC-ND 4.0; commercial users are asked to pay a yearly licence fee", "class": "non-commercial", "accessed": shared.day(*SAVED_TERMS["prosite"]), "through": "UniProt",
            "holds": f"Nothing was downloaded from it but its statement of terms, and nothing of it is copied. Its rules (ProRule) are named in UniProt's entries as what stands behind a statement. {of('PROSITE-ProRule'):,} placements rest on them alone: {of('PROSITE-ProRule', PLACE):,} by the statement of place that decides the shelf ({len(rule_ids.get('PROSITE-ProRule', {})):,} rules; most often {most('PROSITE-ProRule')}), {of('PROSITE-ProRule', SPANS):,} by the statement that the protein spans the membrane, and {of('PROSITE-ProRule', FROM_SEGMENTS):,} by a side read here from segments that a rule gives. They were read in UniProt's entries.",
        },
        {
            "name": "HAMAP", "url": "https://hamap.expasy.org/hamap_about.html", "licence": "CC BY 4.0", "class": "permissive", "accessed": shared.day(*SAVED_TERMS["hamap"]), "through": "UniProt",
            "holds": f"Nothing was downloaded from it but its statement of terms. Its family rules are named in UniProt's entries as what stands behind a statement. {of('HAMAP-Rule'):,} placements rest on them alone: {of('HAMAP-Rule', PLACE):,} by the statement of place that decides the shelf ({len(rule_ids.get('HAMAP-Rule', {})):,} rules), {of('HAMAP-Rule', SPANS):,} by the statement that the protein spans the membrane, {of('HAMAP-Rule', FACE):,} by the stated face, and {of('HAMAP-Rule', FROM_SEGMENTS):,} by a side read here from segments that a rule gives.",
        },
        {
            "name": "TMHMM", "url": "https://services.healthtech.dtu.dk/services/TMHMM-2.0/", "licence": DTU_LICENCE, "class": "non-commercial", "accessed": shared.day(*SAVED_TERMS["tmhmm"]), "through": "UniProt",
            "holds": f"{NOT_RUN} {FOUR_SEGMENTS}. {of('segments'):,} placements rest on segments that an entry gives by sequence analysis alone: {of('segments', FROM_SEGMENTS):,} are read here from such segments (basis predicted; {rules['segment'] + rules['no place: segment']:,} are read from segments in all), and behind a curator's statement {of('segments', SPANS):,} are said to span the membrane on a sequence analysis and {of('segments', PLACE):,} have a stated place that rests on a sequence analysis in an entry with such segments.",
        },
        {
            "name": "Phobius", "url": "https://phobius.sbc.su.se/download", "licence": "For academic users only: the program may be used for private study, education or nonprofit research, and other users are asked to write to its author. The terms are of the program: they do not speak of predictions made with it", "class": "non-commercial", "accessed": shared.day(*SAVED_TERMS["phobius"]), "through": "UniProt",
            "holds": f"{NOT_RUN} {FOUR_SEGMENTS}; and one of the four it names for signal peptides. The placements are those counted under TMHMM ({of('segments'):,}) and under SignalP ({of('signal'):,}).",
        },
        {
            "name": "SignalP", "url": "https://services.healthtech.dtu.dk/services/SignalP-5.0/", "licence": DTU_LICENCE, "class": "non-commercial", "accessed": shared.day(*SAVED_TERMS["signalp"]), "through": "UniProt",
            "holds": f"{NOT_RUN} {FOUR_SIGNALS}. {of('signal'):,} placements rest on a signal peptide that an entry gives by sequence analysis alone: {of('signal', FROM_SIGNAL):,} are read here from such a signal (basis predicted; {rules['signal'] + rules['no place: signal']:,} are read from a signal peptide in all), and behind a curator's statement {of('signal', PLACE):,} have a stated place that rests on a sequence analysis in an entry with such a signal and no such segment.",
        },
        {
            "name": "TargetP", "url": "https://services.healthtech.dtu.dk/services/TargetP-2.0/", "licence": DTU_LICENCE, "class": "non-commercial", "accessed": shared.day(*SAVED_TERMS["targetp"]), "through": "UniProt",
            "holds": f"{NOT_RUN} {FOUR_SIGNALS}. The placements are those counted under SignalP ({of('signal'):,}).",
        },
        {
            "name": "Memsat", "url": "https://www.uniprot.org/help/transmem", "licence": "Terms not read: UniProt's help names Memsat without a version or an address, so no page of terms could be tied to the program it runs", "class": "no stated terms", "accessed": d.day(KB_DOCS, "help_transmem.json"), "through": "UniProt",
            "holds": f"Nothing was downloaded from it. {FOUR_SEGMENTS}. The placements are those counted under TMHMM ({of('segments'):,}).",
        },
        {
            "name": "Predotar", "url": "https://www.uniprot.org/help/signal", "licence": "Terms not read: the program's own page answers this tool with a check for a browser, so its terms could not be read", "class": "no stated terms", "accessed": d.day(KB_DOCS, "help_signal.json"), "through": "UniProt",
            "holds": f"Nothing was downloaded from it. {FOUR_SIGNALS}. The placements are those counted under SignalP ({of('signal'):,}).",
        },
        {
            "name": "big-PI", "url": "https://mendel.imp.ac.at/gpi/gpi_server.html", "licence": "No open licence stated: the predictor's own page gives no terms of use", "class": "no stated terms", "accessed": d.day(BIG_PI, "gpi_server.html"), "through": "UniProt",
            "holds": f"Nothing was downloaded from it but its own page, and the program was not run here. The predictor that UniProt's help names for the GPI anchors it predicts. {of('big-PI'):,} placements rest on a GPI anchor that the entry states on a sequence analysis alone: such an anchor puts the protein on the face away from the cytoplasm.",
        },
    ]
    if [source["name"] for source in closing["sources"] if source.get("through")] != UPSTREAM:
        raise SystemExit("the sources read through UniProt are not the ones this tool names")

    family_rows = [line_row(line, FAMILY_COLUMNS) for line in lines]
    lone_rows = [line_row(line, PART_COLUMNS) for line in alone]
    part_rows = [line_row(line, PART_COLUMNS) for line in rest]
    rows = lambda items, pad=" ": "[\n" + ",\n".join(f"{pad} " + compact(item) for item in items) + f"\n{pad}]"
    nested = lambda block, items: json.dumps(block, indent=1, ensure_ascii=False).replace("\n", "\n ")[:-3] + ',\n  "parts": ' + rows(items, "  ") + "\n }"
    body = json.dumps(header, indent=1, ensure_ascii=False)[:-2]
    body += ',\n "families": ' + rows(family_rows)
    body += f',\n "distinct_families": {distinct},\n "family_lines": {len(lines)},\n "families_in_all": {len(family_total)}'
    body += ',\n "lone": ' + nested(lone, lone_rows)
    body += ',\n "no_family": ' + nested(no_family, part_rows)
    body += "," + json.dumps(tail, indent=1, ensure_ascii=False)[1:-2]
    body += ',\n "places": ' + rows(place_rows)
    body += ',\n "place_words": ' + json.dumps(place_words, ensure_ascii=False, separators=(", ", ": "))
    body += "," + json.dumps(closing, indent=1, ensure_ascii=False)[1:] + "\n"
    json.loads(body)

    # --- the table of proteins, in the members' order -----------------------------------------
    lone_of = {protein for line in alone for protein in line["proteins"]}
    table_rows = []
    for protein in sequence:
        entry, item = entries[protein], placed[protein]
        under = filing.family.get(protein) or filing.part[protein]
        table_rows.append([
            protein, entry["gene"], entry["name"], str(entry["length"]), str(entry["isoforms"]), str(entry["seen"]), under, item["shelf"] or "", item["side"], BASIS_LETTER[item["basis"]], EVIDENCE_LETTER[item["evidence"]] if item["evidence"] else "",
            code(item["where"]) if item["where"] else "", ",".join(code(statement) for statement in item["also"]), ";".join(units.get(protein, [])),
            filing.names[under]["name"] if protein in lone_of else "", entry["of"] or "",
        ])
    for row in table_rows:
        if any("\t" in value or "\n" in value for value in row):
            raise SystemExit(f"{row[0]}: a value of the table holds a tab or a line break")
    table = "\n".join("\t".join(row) for row in [TABLE_COLUMNS, *table_rows]) + "\n"

    # --- what the README and the summary say ---------------------------------------------------
    sizes = sorted(family_total.values(), reverse=True)
    line_sizes = sorted((len(line["proteins"]) for line in lines), reverse=True)
    full = make_lines(entries, placed, filing, units, lone_up_to=0)
    whole_family = defaultdict(list)
    for protein, family in filing.family.items():
        whole_family[family].append(protein)
    one_line_each = sum(len(("  " + compact([family, filing.names[family]["name"], "membrane", "not known", "signalling", len(proteins), ordered_sides(Counter(placed[p]["side"] for p in proteins)), "members-00.json", [10000, 10000 + len(proteins)], [], {key(shelf): count for shelf, count in Counter(placed[p]["shelf"] for p in proteins).items()}]) + ",\n").encode("utf-8")) for family, proteins in whole_family.items())
    by_family_shelf = Counter((filing.family[protein], placed[protein]["shelf"]) for protein in filing.family)
    most_on_a_shelf = defaultdict(int)
    for (family, _), count in by_family_shelf.items():
        most_on_a_shelf[family] = max(most_on_a_shelf[family], count)
    report = {
        "release": release, "interpro": filing.release, "ontology": filing.ontology, "made": made, "stated": stated, "read": dict(read), "terms": said,
        "shelf_counts": shelf_counts, "counts": counts, "bases": {f"{side} / {basis}": count for (side, basis), count in sorted(bases.items())}, "rules": {rule: rules[rule] for rule, _, _ in RULES_USED},
        "evidence": dict(evidence), "by_rule": dict(by_rule), "spans_by": {str(word): count for word, count in spans_by.items()}, "feature_rules": feature_rules, "rests": rests, "resting": resting, "rule_ids": rule_ids,
        "families": len(family_total), "in_families": len(filing.family), "several": filing.several, "no_family": len(filing.part), "retired": filing.retired, "dropped": len(filing.dropped),
        "family_sizes": {"one": sum(1 for size in sizes if size == 1), "two to four": sum(1 for size in sizes if 2 <= size <= 4), "five or more": sum(1 for size in sizes if size >= 5), "ten or more": sum(1 for size in sizes if size >= 10), "fifty or more": sum(1 for size in sizes if size >= 50)},
        "largest_families": [[filing.names[family]["name"], count] for family, count in sorted(family_total.items(), key=lambda item: (-item[1], item[0]))[:12]],
        "lines": len(lines), "distinct": distinct, "lone": lone["count"], "lone_families": lone_families, "lone_parts": len(alone), "part_lines": len(rest),
        "parts": dict(Counter(PART_KIND(part) for part in set(filing.part.values()))), "part_proteins": dict(Counter(PART_KIND(part) for part in filing.part.values())),
        "line_sizes": {"one": sum(1 for size in line_sizes if size == 1), "two to four": sum(1 for size in line_sizes if 2 <= size <= 4), "five or more": sum(1 for size in line_sizes if size >= 5)},
        "five_in_all": sum(1 for size in sizes if size >= 5), "five_in_all_under_five_everywhere": sum(1 for family, count in family_total.items() if count >= 5 and most_on_a_shelf[family] < 5),
        "per_shelf": {key(shelf): {
            "proteins": sum(shelf_counts[key(shelf)].values()),
            "lines": sum(1 for line in lines if line["shelf"] == shelf), "families": len({line["id"] for line in lines if line["shelf"] == shelf}),
            "lines of five or more": sum(1 for line in lines if line["shelf"] == shelf and len(line["proteins"]) >= 5), "lines of one to four": sum(1 for line in lines if line["shelf"] == shelf and len(line["proteins"]) < 5),
            "lines of families of five or more in all": sum(1 for line in lines if line["shelf"] == shelf and line["total"] >= 5), "of those, lines of one to four": sum(1 for line in lines if line["shelf"] == shelf and line["total"] >= 5 and len(line["proteins"]) < 5),
            "lines by the side they stand on": {side: sum(1 for line in lines if line["shelf"] == shelf and line["side"] == side) for side in SIDES},
            "lone parts": sum(1 for line in alone if line["shelf"] == shelf), "lone proteins": sum(len(line["proteins"]) for line in alone if line["shelf"] == shelf),
            "parts of no family": sum(1 for line in rest if line["shelf"] == shelf), "proteins with no family": sum(len(line["proteins"]) for line in rest if line["shelf"] == shelf),
            "largest lines": [[line["label"], len(line["proteins"])] for line in sorted((line for line in lines if line["shelf"] == shelf), key=lambda line: (-len(line["proteins"]), line["id"]))[:6]],
        } for shelf in [*SHELF_IDS, None]},
        "layouts": {
            "this file": len(body.encode("utf-8")),
            "family lines here": rows_size(lines, FAMILY_COLUMNS), "lone parts here": rows_size(alone, PART_COLUMNS), "parts of no family": rows_size(rest, PART_COLUMNS),
            "every family a line on each shelf: lines": len(full[0]), "every family a line on each shelf: bytes of its lines": rows_size(full[0], FAMILY_COLUMNS),
            "one line for each family, with counts by shelf: lines": len(whole_family), "one line for each family, with counts by shelf: bytes of its lines": one_line_each,
        },
        "groups": groups, "classed": dict(Counter(filing.classed.values())), "matched": {str(count): number for count, number in sorted(filing.matched.items())},
        "units": {"accessions": len(units), "missing": missing, "units": len({unit for found in units.values() for unit in found}), "placed": dict(Counter(f"{key(placed[a]['shelf'])} / {placed[a]['side']} / {placed[a]['basis']}" for a in units if a in placed)), "not in a membrane": sorted(f"{a} {entries[a]['gene']} ({', '.join(sorted(roles[a]))}): {key(placed[a]['shelf'])} / {placed[a]['side']}" for a in units if a in placed and placed[a]["side"] != "in"), "in no family": sorted(a for a in units if a in filing.part), "lines with units": sum(1 for line in [*lines, *alone, *rest] if line["units"])},
        "member_files": files, "largest_file": max(Counter(line["file"] for line in [*lines, *alone, *rest] for _ in line["proteins"]).values()),
        "places_used": len(used), "first_places": len(first_places), "place_rows": place_rows,
        "per_protein": {protein: [key(placed[protein]["shelf"]), placed[protein]["side"], placed[protein]["basis"], placed[protein]["rule"]] for protein in sequence},
        "first_inside_or_outside_with_segments": sum(1 for a, item in placed.items() if item["rule"] == "place" and entries[a]["segments"]),
        "stated_for": {name: read[name] for name in sorted(read) if name.startswith("place stated for")}, "infection": read.get("comments on an infection, not read", 0),
        "elsewhere_only": sum(1 for entry in entries.values() if entry["statements"] and all(statement["kind"] == ELSEWHERE for statement in entry["statements"])),
        "segments_only_predicted": {rule: [sum(1 for a, item in placed.items() if item["rule"] == rule and entries[a]["segments_only_predicted"]), rules[rule]] for rule in ("segment", "no place: segment")},
        "unnamed": {"stated": sum(1 for item in placed.values() if item["shelf"] == "membrane" and item["where"]), "predicted": sum(1 for item in placed.values() if item["shelf"] == "membrane" and not item["where"])},
        "other_by_compartment": dict(Counter(compartment(item["where"]["under"]) for item in placed.values() if item["shelf"] == "other" and item["where"]).most_common()),
    }
    files_out = {"shelves": body, "table": table}
    files_out["readme"] = build_readme(report, header, lone, no_family, tail, closing)
    for name, text in files_out.items():
        if PATHS.search(text):
            raise SystemExit(f"the {name} would hold a machine path")
    size = {name: len(text.encode("utf-8")) for name, text in files_out.items()}
    if size["shelves"] >= LIMIT_SHELVES or max(size.values()) >= LIMIT_FILE or sum(size.values()) >= LIMIT_FOLDER:
        raise SystemExit(f"the files have outgrown their limits: {size}")
    report["sizes"] = size
    return files_out, report


def build_readme(report, header, lone, no_family, tail, closing):
    """The note beside the files, from what the build counted."""
    r = report
    stated, rules, per_shelf = r["stated"], r["rules"], r["per_shelf"]
    n = lambda number: f"{number:,}"
    shelf_rows = "\n".join(
        f"| `{shelf['id']}` | {shelf['label']} | {n(shelf['proteins'])} | " + " | ".join(n(r["shelf_counts"][shelf["id"]][side]) for side in SIDES) + f" | {n(shelf['lines'])} | {n(shelf['lone'])} | {n(shelf['no_family'])} |"
        for shelf in header["shelves"]
    )
    none = header["no_shelf"]
    shelf_rows += f"\n| | On no shelf | {n(none['proteins'])} | 0 | 0 | 0 | {n(none['proteins'])} | {n(none['lines'])} | {n(none['lone'])} | {n(none['no_family'])} |"
    rule_rows = "\n".join(f"| {item['rule']} | {item['basis']} | {n(item['proteins'])} | {item['what']} |" for item in tail["placed_by"])
    table_rows = "\n".join(f"| {name} | `{shelf}` | {kind} |" if shelf else f"| {name} | | {kind} |" for name, (shelf, kind) in PLACES.items())
    most = "\n".join(f"| {words_} | `{shelf}` | {kind} | {n(first)} |" for _, words_, shelf, kind, _, _, first in r["place_rows"][:24])
    others = list(r["other_by_compartment"].items())
    group_rows = "\n".join(f"| {group['label']} | {n(group['lines'])} | {n(group['proteins'])} | {n(group['lone'])} | {group['from']} |" for group in header["groups"])
    marks = "\n".join(f"| `{name}` | {mark['label']} | {', '.join(str(value) for value in mark['values']) if isinstance(mark['values'], list) else 'a ' + mark['values']} | {mark['note']} |" for name, mark in closing["marks"].items())
    sources = "\n".join(
        f"| {source['name']}{' ' + source['release'] if source.get('release') else ''} | {source['licence']} | {source['class']}{' (read through ' + source['through'] + ')' if source.get('through') else ''} | {source['holds'][0].upper() + source['holds'][1:]} |"
        for source in closing["sources"]
    )
    units = r["units"]
    largest = r["largest_families"]
    evidence = r["evidence"]
    return f"""# The human's own proteins, for the atlas's shelves

Made by `tools/build_human_atlas.py` on {r['made']} from saved downloads; the same bytes every
time. The form is fixed in `schema/SPECIES_PROTEINS.md`. This is the viewer's reference
data. It is not the engine's protein catalogue and it says nothing about the engine: a
protein here is tied to the law inventory only where the inventory itself names its
accession.

| File | Holds |
| --- | --- |
| `{SHELVES_FILE}` | The shelves, the families' lines on them, and how every side was read |
| `{TABLE_FILE}` | One line for each protein, in the order the lines read them |
| `README.md` | This note |

## What is in, and what is out

- **In: {n(stated['reviewed'])} proteins.** One for each reviewed entry (Swiss-Prot) of UniProt's human
  reference proteome {PROTEOME}, release {r['release']}: the entry's canonical sequence.
- **As a count: {n(stated['sequences'] - stated['reviewed'])} further isoforms.** The entries describe {n(stated['sequences'])} sequences in
  all; each protein carries how many its entry describes (`isoforms`). An isoform is not
  a marker of its own.
- **Out: {n(stated['unreviewed'])} unreviewed entries.** The proteome holds {n(stated['all'])} entries for
  {n(stated['genes'])} genes. The unreviewed ones are computer-annotated sequences, most of them other
  or partial sequences of the same genes; none is listed here.
- **No sequences** are kept, and nothing is taken from the Human Protein Atlas: it is
  kept for a link only.

## The shelves

A shelf is a membrane, and a protein sits outside it, in it or inside it. Curators state
where most of these proteins are, so the human has several shelves, and a protein stands
where its entry first places it.

| Shelf | Membrane | Proteins | Outside | In | Inside | Side not known | Families' lines | Lone | No family |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{shelf_rows}

- **`other`** stands for the cell's remaining membranes together: those of the Golgi
  apparatus, endosomes, lysosomes, peroxisomes and vesicles, and the mitochondrion's outer
  membrane. Each protein there names its compartment in its mark `where`. By the
  compartment of the statement that decided: {', '.join(f'{name[0].lower() + name[1:] if not name.startswith(("Golgi", "Endoplasmic")) else name} {n(count)}' for name, count in others)}.
  The Golgi apparatus is the one that could be a shelf of its own; it is left here because
  it holds about half of what the smallest shelf holds.
- **`membrane`** is for a membrane that is not named: {n(r['unnamed']['stated'])} proteins whose entry says
  only "Membrane" (or the endomembrane system), and {n(r['unnamed']['predicted'])} with no stated place whose
  entry carries a membrane-spanning segment ({n(rules['no place: segment'])}) or a signal peptide ({n(rules['no place: signal'])}). Its
  "outside" is the side away from the cytoplasm: outside the cell, or within a compartment.
- **Side not known** on a shelf: the entry states the membrane or the compartment and
  not the side. The protein counts for that shelf and is drawn apart beside it.
- **On no shelf**: {n(rules['no place'])} proteins. Their entries state no place of the cell and carry no
  membrane-spanning segment and no signal peptide. Nothing is placed by guess.

## How a protein gets its shelf and side

The rules, in the order they are tried:

| Rule | Basis | Proteins | What it reads |
| --- | --- | ---: | --- |
{rule_rows}

- **Which statement is read.** {n(r['stated_for']['place stated for the entry as a whole'])} entries state a place for the protein as a whole;
  {n(r['stated_for']['place stated for the canonical isoform'])} state one only for named forms, the canonical isoform among them, and that one
  is read; {n(r['stated_for']['place stated for another named form'])} state one only for other named forms (a processed chain, another
  isoform), and the first is read, with the form named in the mark `of`. {n(r['infection'])} comments
  on where a protein is during an infection are not read. {n(r['elsewhere_only'])} entries state only a
  place that is not of the cell (a virus particle).
- **The first place decides.** The other statements are kept, in order, in the mark
  `also`. For {n(r['first_inside_or_outside_with_segments'])} proteins the first place is within a compartment or beyond a
  membrane while the entry also carries membrane-spanning segments: they stand where the
  first statement puts them.
- **What stands behind the deciding statement** (`evidence`): {n(evidence.get('experiment', 0))} an experiment,
  {n(evidence.get('similarity', 0))} likeness to another protein, {n(evidence.get('curator', 0))} a curator's inference or an author's
  statement, {n(evidence.get('rule', 0))} a sequence model or a family rule, {n(evidence.get(NOT_GIVEN, 0))} with no evidence code
  (older curated statements).
- **The two feature rules** ({n(r['feature_rules'])} proteins) read the entry's membrane-spanning segments
  and signal peptide. UniProt's curators annotate those from experiments, from likeness
  and from prediction; its own help pages name the predictors (TMHMM, Memsat, Phobius
  and a hydrophobic moment plot for the segments; Phobius, Predotar, SignalP and TargetP
  for the signal peptides). A segment is used only where one membrane is meant: not for
  the mitochondrion, whose two membranes are on different shelves, nor for a region of
  the cell that holds other membranes.
- **Spanning is often a prediction too.** Of the {n(rules['spans'])} proteins placed in a membrane
  because the entry states that they span it, the statement itself rests on a sequence
  analysis for {n(r['spans_by'].get('rule', 0))}, on a curator's inference for {n(r['spans_by'].get('curator', 0))}, on likeness for {n(r['spans_by'].get('similarity', 0))}, on
  an experiment for {n(r['spans_by'].get('experiment', 0))}, and carries no code for {n(r['spans_by'].get(NOT_GIVEN, 0))}. ("A sequence analysis" here counts
  the few that a family rule gives.) The basis is "stated" because the curated entry
  states it.

### The table

Every place an entry states is a term of UniProt's vocabulary (`subcell.txt`). The tool
gives these terms a shelf and says what each names against the shelf's membrane; every
other term takes the line of the terms it is a kind of, else of the term before it in
UniProt's own path for it, else of the terms it is a part of. A term that names a
membrane and resolves to a compartment or a region is that place's membrane.

| Term | Shelf | What it names |
| --- | --- | --- |
{table_rows}

What a term names: {'; '.join(f'**{kind}**, {what}' for kind, what in KINDS.items())}.

The places that decide most often ({n(r['first_places'])} different ones decide for at least one
protein; `{SHELVES_FILE}` lists all {n(r['places_used'])} that the entries state, under `places`):

| Place, in UniProt's words | Shelf | What it names | Proteins |
| --- | --- | --- | ---: |
{most}

## Families that open, proteins on their own, and no family

- **Families.** A family is an InterPro entry of the type Family (InterPro {r['interpro']}), chosen
  by the rule of the planarian's file, so that a family has the same id in both: the
  narrowest family among the InterPro entries UniProt gives the protein; of several
  unrelated ones ({n(r['several'])} proteins), the deepest in InterPro's tree, then the smallest
  here, then the first. {n(r['families'])} families hold {n(r['in_families'])} proteins. The largest are
  {largest[0][0]} ({n(largest[0][1])}), {largest[1][0]} ({n(largest[1][1])}) and {largest[2][0]} ({n(largest[2][1])}).
- **A family has a line for each shelf that holds members of it**, and one with no shelf
  for its members that are on none: {n(r['lines'])} lines of {n(r['distinct'])} families. {n(r['line_sizes']['five or more'])} lines hold five
  proteins or more, {n(r['line_sizes']['two to four'])} hold two to four and {n(r['line_sizes']['one'])} hold one. Each line gives the
  family's members in all (`total`): {n(r['five_in_all'])} families have five or more, and {n(r['five_in_all_under_five_everywhere'])} of
  those have fewer than five on every shelf.
- **On their own.** {n(r['lone_families'])} families have a single member in this catalogue. A family of
  one does not open, so it has no line: its protein is listed under `lone`, in {n(r['lone_parts'])} parts,
  one for each shelf, district and side, and names its family in its mark `family`.
  Giving each of them a line would take the file past its limit of 1 MB.
- **No family.** {n(r['no_family'])} proteins carry no family signature. None is dropped: they are
  listed under `no_family`, in parts, each with a line for each shelf. {n(r['parts']['superfamily'])} parts are
  InterPro superfamilies, a wider grouping by shared structure, and hold {n(r['part_proteins']['superfamily'])}; {n(r['part_proteins']['other signature'])}
  proteins carry only a domain, repeat or site signature; {n(r['part_proteins']['no signature'])} carry no signature
  of any kind.

A line stands in a district:

| District | Families' lines | Their proteins | Lone proteins | From |
| --- | ---: | ---: | ---: | --- |
{group_rows}

A protein's Gene Ontology terms are those InterPro maps to any of its signatures and
those UniProt gives its entry. The protein falls in the first district, in the order of
the table, one of whose terms it carries; a line stands where most of its classed members
fall. The districts, their terms and their order are the planarian's, so the two species
can be compared. They fit the human less well: UniProt gives nearly every human entry
terms of its own, so {n(sum(number for count, number in r['matched'].items() if int(count) > 1))} proteins carry the terms of two districts or more and the
order decides between them.

## Tied to the atlas

The inventory's candidate products name {n(units['accessions'])} human entries, for {n(units['units'])} of its units. Every
one is a protein of this catalogue and carries its units' ids (`units`), and so do the
lines that hold them ({n(units['lines with units'])} lines). {n(len(units['in no family']))} of them have no family and stand in a part
of `no_family`.

## The marks

| Mark | What it says | Values | Note |
| --- | --- | --- | --- |
{marks}

## `{TABLE_FILE}`

{n(stated['reviewed'])} lines under a header, tab-separated, in the order the lines of `{SHELVES_FILE}`
read them: every line of the families, then every part of `lone`, then every part of
`no_family`; within each, by gene name.

| Column | Meaning |
| --- | --- |
| `id` | The entry's UniProtKB accession |
| `gene` | Its first gene name, where it has one |
| `name` | The protein's recommended name |
| `length` | Residues of the canonical sequence |
| `isoforms` | Sequences the entry describes, the canonical one included |
| `seen` | UniProt's level of evidence that the protein exists: {', '.join(f'{level} {SEEN[level]}' for level in sorted(SEEN))} |
| `under` | The InterPro family it is filed under; for a protein with no family, the part: a superfamily's accession, `other-signature` or `no-signature` |
| `shelf` | Its shelf, or empty for none |
| `side` | `outside`, `in`, `inside` or `not known` |
| `basis` | {', '.join(f'`{letter}` {word}' for word, letter in BASIS_LETTER.items())} |
| `evidence` | What stands behind the stated place: {', '.join(f'`{letter}` {word}' for word, letter in EVIDENCE_LETTER.items())}; empty where no place of the cell is stated |
| `place` | The statement that decided, in UniProt's identifiers without their prefix: the place, then the topology and the face where stated, joined by a full stop (`0039.9909` is SL-0039 with SL-9909). `{SHELVES_FILE}` gives the words of each under `place_words` |
| `also` | The entry's other statements, written the same way, separated by commas |
| `units` | The inventory units that name this entry |
| `family` | For a protein listed under `lone`, its family's name |
| `of` | The named form the place is stated for, where it is not the protein as a whole or its canonical isoform |

**How a line's members are read.** The lines follow one another in the table: a line's
members are the next `count` lines. For the page they are cut into {len(r['member_files'])} files of at most
{MEMBERS_PER_FILE:,} members: a file holds consecutive lines and a line is never split. `{SHELVES_FILE}`
gives each line's file and its place there (`file`, `at`). `python3
tools/build_human_atlas.py members --out DIR` writes the files; they are published
beside the page and are not kept in the repository.

## Sources and terms

| Source | Terms | Class | What was taken |
| --- | --- | --- | --- |
{sources}

- Each source's terms were read in its own page, saved beside the downloads, before
  anything of it was used; the build checks the sentence in each saved page.
- **What UniProt's entries state by rule or by sequence analysis is named.** Each rule
  system and each program behind such statements is a source of its own, read through
  UniProt, with the placements that rest on it alone: PROSITE's rules {n(r['resting'].get('PROSITE-ProRule', {}).get('placements', 0))}, HAMAP's {n(r['resting'].get('HAMAP-Rule', {}).get('placements', 0))},
  the four programs UniProt names for the segments it predicts {n(r['resting'].get('segments', {}).get('placements', 0))}, the four for signal
  peptides {n(r['resting'].get('signal', {}).get('placements', 0))}, and the one for GPI anchors {n(r['resting'].get('big-PI', {}).get('placements', 0))}. Everything was read in UniProt's
  entries, which are CC BY 4.0; no file of a rule system was downloaded and no program
  was run. PROSITE's terms do not allow commercial use; TMHMM, SignalP, TargetP and
  Phobius are given out for academic use; the terms of Memsat and Predotar could not be
  read, and the page of the GPI predictor states none. `docs/HUMAN_PROTEOME.md` sets out
  both kinds of dependence for each: a side this file reads from a feature, and a
  curator's statement that itself rests on such a result.
- **The Human Protein Atlas** states that it is licensed under CC BY 4.0 for all
  copyrightable parts of its database, and warns that data of third parties in it may
  carry other terms. Nothing is taken from it: it is kept for a link from each protein,
  which the page's link patterns do not hold yet.

## Rebuild

    python3 tools/build_human_atlas.py fetch --datasets DATA
    python3 tools/build_human_atlas.py build --datasets DATA
    python3 tools/build_human_atlas.py members --out OUT

`fetch` is the only step that uses the network. `build` reads only the saved downloads
and the inventory snapshot, and checks each file against its MANIFEST.
"""


# ---------------------------------------------------------------------------------------
# Members: the files the page publishes beside it
# ---------------------------------------------------------------------------------------

def cut_members(folder):
    """The members' files, cut from the two files of the repository as shelves.json says:
    {file name: text}. Reads nothing else."""
    folder = Path(folder)
    shelves = json.loads((folder / SHELVES_FILE).read_text(encoding="utf-8"))
    with open(folder / TABLE_FILE, encoding="utf-8") as handle:
        header = handle.readline().rstrip("\n").split("\t")
        table = [dict(zip(header, line.rstrip("\n").split("\t"))) for line in handle]
    said = shelves["place_words"]
    place = lambda written: "; ".join(said[part] for part in written.split("."))
    letters = shelves["members_from"]["letters"]
    lines = [("family", dict(zip(shelves["family_columns"], row))) for row in shelves["families"]]
    lines += [("lone", dict(zip(shelves["lone"]["part_columns"], row))) for row in shelves["lone"]["parts"]]
    lines += [("part", dict(zip(shelves["no_family"]["part_columns"], row))) for row in shelves["no_family"]["parts"]]
    files, cursor = defaultdict(list), 0
    for what, line in lines:
        rows = table[cursor:cursor + line["count"]]
        cursor += line["count"]
        if len(files[line["file"]]) != line["at"][0] or len(rows) != line["at"][1] - line["at"][0]:
            raise SystemExit(f"the members of {line['id']} on {line['shelf']} are not where {SHELVES_FILE} says they are")
        for row in rows:
            if row["shelf"] != (line["shelf"] or "") or (what != "lone" and row["under"] != line["id"]) or (what == "lone" and (row["side"] != line["side"] or not row["family"])):
                raise SystemExit(f"{row['id']} is not a member of the line {line['id']} on {line['shelf']}: the two files are not of one build")
            marks = {"isoforms": int(row["isoforms"]), "seen": letters["seen"][row["seen"]]}
            if row["evidence"]:
                marks["evidence"] = letters["evidence"][row["evidence"]]
            if row["place"]:
                marks["where"] = place(row["place"])
            if row["also"]:
                marks["also"] = [place(written) for written in row["also"].split(",")]
            if what == "lone":
                marks["family"] = [row["under"], row["family"]]
            if row["of"]:
                marks["of"] = row["of"]
            files[line["file"]].append([row["id"], row["name"], row["gene"], row["side"], letters["basis"][row["basis"]], int(row["length"]), row["units"].split(";") if row["units"] else None, marks])
    if cursor != len(table):
        raise SystemExit(f"the table holds {len(table)} proteins and the lines {cursor}")
    out = {}
    for file in sorted(files):
        head = {"format": MEMBERS_FORMAT, "species": shelves["species"], "file": file, "columns": shelves["member_columns"]}
        out[file] = json.dumps(head, indent=1, ensure_ascii=False)[:-2] + ',\n "members": [\n' + ",\n".join("  " + compact(member) for member in files[file]) + "\n ]\n}\n"
        json.loads(out[file])
    return out


def summary(report):
    r = report
    lines = [
        f"UniProt {r['release']}, InterPro {r['interpro']}, Gene Ontology {r['ontology']}; made {r['made']}",
        f"in: {r['stated']['reviewed']:,} reviewed entries ({r['stated']['sequences']:,} sequences with their isoforms); out: {r['stated']['unreviewed']:,} unreviewed entries; {r['stated']['all']:,} in all, {r['stated']['genes']:,} genes; {r['stated']['with_place']:,} state a place",
        f"places read: {r['read']}; entries that state only a place that is not of the cell: {r['elsewhere_only']}",
        "by shelf: " + "; ".join(f"{shelf} {sum(sides.values()):,} {sides}" for shelf, sides in r["shelf_counts"].items()),
        f"sides: {r['counts']}",
        f"side and basis: {r['bases']}",
        f"rules: {r['rules']}",
        f"evidence behind the deciding statement: {r['evidence']}; of those by rule: {r['by_rule']}; evidence of 'spans': {r['spans_by']}",
        f"first place inside or outside while the entry carries segments: {r['first_inside_or_outside_with_segments']}; segments that are only predicted, by rule: {r['segments_only_predicted']}",
        f"families: {r['families']:,} holding {r['in_families']:,} proteins (tie-break among unrelated families: {r['several']:,}); no family: {r['no_family']:,} in {r['parts']} holding {r['part_proteins']}; signatures no longer in InterPro: {r['retired']}; terms no longer usable: {r['dropped']}",
        f"  family sizes: {r['family_sizes']}; largest: {r['largest_families'][:8]}",
        f"lines: {r['lines']:,} of {r['distinct']:,} families; by size: {r['line_sizes']}; lone: {r['lone']:,} proteins of {r['lone_families']:,} families in {r['lone_parts']} parts; lines of the parts of no family: {r['part_lines']}",
        f"families of five or more in all: {r['five_in_all']}; of those with fewer than five on every shelf: {r['five_in_all_under_five_everywhere']}",
        f"layouts: {r['layouts']}",
        "districts: " + "; ".join(f"{group['id']} {group['lines']:,} lines, {group['proteins']:,} proteins, {group['lone']:,} lone" for group in r["groups"]),
        f"proteins by the district their own terms give: {r['classed']}; districts matched by one protein: {r['matched']}",
        f"rests on a rule system or a program, by owner: {r['resting']}",
        f"  rules named: " + "; ".join(f"{owner}: {len(found)} rules, most often {list(found.items())[:5]}" for owner, found in r["rule_ids"].items()),
        f"units: {r['units']}",
        f"member files: {len(r['member_files'])}, the largest of {r['largest_file']:,}; places used: {r['places_used']}, as the deciding statement: {r['first_places']}",
        f"sizes: {r['sizes']}",
    ]
    for shelf, found in r["per_shelf"].items():
        lines.append(f"  {shelf}: {found}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("step", choices=["fetch", "build", "members"], help="fetch asks the databases and saves the answers; build reads only what was saved; members cuts the shelves' member files from the repository's two files")
    parser.add_argument("--datasets", help="fetch, build: the folder of downloads, one folder per source with a MANIFEST.json (kept outside the repository)")
    parser.add_argument("--terms", help="build: the folder that holds every species' downloads, where the other species' tools saved the terms of the rule systems and programs (default: the folder above --datasets)")
    parser.add_argument("--refresh", action="store_true", help="fetch: ask again even where an answer is saved")
    parser.add_argument("--out-dir", default=str(OUT_DIR), help="build: the folder for shelves.json, the table and their README.md; members: the folder that holds them")
    parser.add_argument("--out", help="members: the folder to write the member files into")
    parser.add_argument("--report", help="build: also write what was counted, as JSON, to this file (kept outside the repository)")
    args = parser.parse_args()
    if args.step == "members":
        if not args.out:
            parser.error("members needs --out")
        Path(args.out).mkdir(parents=True, exist_ok=True)
        for name, text in cut_members(args.out_dir).items():
            (Path(args.out) / name).write_text(text, encoding="utf-8")
            print(f"wrote {Path(args.out) / name} ({len(text.encode('utf-8')):,} bytes)")
        return
    if not args.datasets:
        parser.error(f"{args.step} needs --datasets")
    if args.step == "fetch":
        sys.exit(1 if fetch(Path(args.datasets), refresh=args.refresh) else 0)
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    files, report = build(Path(args.datasets), snapshot, Path(args.terms) if args.terms else None)
    folder = Path(args.out_dir)
    folder.mkdir(parents=True, exist_ok=True)
    for name, target in (("shelves", SHELVES_FILE), ("table", TABLE_FILE), ("readme", "README.md")):
        (folder / target).write_text(files[name], encoding="utf-8")
        print(f"wrote {folder / target} ({len(files[name].encode('utf-8')):,} bytes)")
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(summary(report))


if __name__ == "__main__":
    main()
