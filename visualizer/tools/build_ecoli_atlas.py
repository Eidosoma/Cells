#!/usr/bin/env python3
"""Build the viewer's data on Escherichia coli K-12: the species, its side of the protein atlas, and its own proteins on shelves.

Five files are written, each from saved answers of public databases and two open papers:

    data/species/ecoli.json            the species file (schema/SPECIES.md): its levels, the
                                       cell's shape and parts, and which of Cells' capabilities
                                       have a place in it
    data/proteins/atlases/ecoli.json   its side of the protein atlas (schema/SPECIES_ATLAS.md):
                                       an entry for every unit of the law inventory
    data/proteins/ecoli/               shelves.json, where each protein of UniProt's reviewed
                                       reference proteome stands against the cell's two
                                       membranes and how that is known (schema/SPECIES_PROTEINS.md,
                                       "A curated proteome"); proteins.tsv, one line per protein;
                                       and the README that explains both

Three steps, kept apart:

    python3 tools/build_ecoli_atlas.py fetch --datasets DATA
        asks the databases for what is not yet saved under DATA/ecoli/, one folder per source
        with a MANIFEST.json (address, time, SHA-256). The only step that uses the network.
        What the other species' tools saved under DATA (UniProt's vocabulary and help pages,
        InterPro's and the Gene Ontology's files, the terms of the tools behind UniProt's
        predictions) is read where it lies and never written.

    python3 tools/build_ecoli_atlas.py build --datasets DATA
        reads only DATA and the inventory snapshot, checks every file against its MANIFEST,
        and writes the files above: the same bytes every time.

    python3 tools/build_ecoli_atlas.py members --out DIR
        cuts the files of the shelves' members from the repository's two files, for the page.

The shelves are filed by the same rules as the human's and the planarian's, so that a
family has one id in every species: the machinery is that of tools/build_human_atlas.py,
used here with this organism's own table of places, and the families asked of every species
are those of tools/build_mpneumoniae_atlas.py. A change to either shows in this tool's
byte-for-byte test.

This is the viewer's reference data. Nothing of this organism is in the engine: the
project's record adds it as a data-only organism (decision D179). Requests carry a generic
client name and nothing about who asks. Standard library only.
"""

from __future__ import annotations

import argparse
import html
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
sys.path.insert(0, str(HERE))
import build_human_atlas as H  # noqa: E402  the shelves' machinery: vocabulary, placement, families, districts, lines
import build_mpneumoniae_atlas as M  # noqa: E402  the families asked of every species

SNAPSHOT = ROOT / "data" / "proteins" / "inventory.snapshot.json"
SPECIES_FILE = ROOT / "data" / "species" / "ecoli.json"
ATLAS_FILE = ROOT / "data" / "proteins" / "atlases" / "ecoli.json"
OUT_DIR = ROOT / "data" / "proteins" / "ecoli"
CLIENT = "atlas-builder/1.0"
PATHS = re.compile(r"/(?:home|mnt|Users|tmp)/")
MINE = "the visualizer's E. coli agent"

SPECIES_ID = "ecoli"
LABEL = "E. coli"
ORGANISM = "Escherichia coli K-12"
TAXON = 83333            # Escherichia coli (strain K12), as UniProt's proteome names it
PROTEOME = "UP000000625"  # UniProt's reference proteome of strain K-12
GENOME = "U00096.3"      # the genome record of strain K-12 substrain MG1655
BACTERIA = 2             # the taxon every control count is asked of
UNIPROT = "https://rest.uniprot.org"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# The dataset folders, under the folder that holds every species' downloads.
KB = "ecoli/uniprot-ecoli-k12-reviewed-proteome"
NCBI = "ecoli/ncbi-U00096.3"
PAPERS_AT = "ecoli/europepmc-open-papers"
TERMS = "ecoli/terms-ecoli-databases"
HUMAN_KB = "human/uniprot-human-reviewed-proteome"   # read only: the signatures of the units' human candidates
KB_DOCS = "human/uniprot-docs-and-terms"            # read only: UniProt's vocabulary, licence and help pages
IPR = "human/interpro-entries-tree-and-go"          # read only
GO = "human/geneontology-go-basic"                  # read only
GENBANK_TERMS = (NCBI, "terms_ncbi_genbank.html")  # NCBI's own statement on the use of GenBank data
PLACES_FILE = f"uniprotkb_{PROTEOME}_reviewed_places.json.gz"
SIGNATURES_FILE = f"uniprotkb_{PROTEOME}_reviewed_signatures.tsv.gz"
REVIEWED = f"(proteome:{PROTEOME}) AND (reviewed:true)"
PLACE_FIELDS = "accession,id,protein_name,gene_primary,gene_oln,length,protein_existence,cc_subcellular_location,ft_transmem,ft_intramem,ft_signal,ft_transit,ft_topo_dom,ft_lipid,cc_alternative_products,fragment,keyword"

# The two open papers a fact of the species file rests on, with the sentence each must hold.
PAPERS = {
    "volkmer2011": {
        "pmc": "PMC3146540", "doi": "10.1371/journal.pone.0023126", "licence": "CC BY",
        "text": "Volkmer B, Heinemann M (2011) Condition-dependent cell volume and concentration of Escherichia coli to facilitate data conversion for systems biology modeling. PLoS One 6:e23126.",
        "holds": [
            r"the average length of the rod-shaped bacterium E\. coli was determined to lie between 1\.6 and 3\.1 µm",
            r"the average width was determined as 0\.7–1\.1 µm",
            r"between 1\.6 µm for stationary cells and 3\.9 µm for cells growing on LB medium",
            r"cell width to be condition-independent \(1\.26 µm ±0\.16 µm\)",
            r"obtaining a volume range from 1\.5 to 4\.4 fl",
        ],
    },
    "urich2008": {
        "pmc": "PMC2424134", "doi": "10.1371/journal.pone.0002527", "licence": "CC BY",
        "text": "Urich T, Lanzén A, Qi J, Huson DH, Schleper C, Schuster SC (2008) Simultaneous assessment of soil microbial community structure and function through analysis of the meta-transcriptome. PLoS One 3:e2527.",
        "holds": [r"E\. coli cells have been estimated to contain between 6,800 and 72,000 ribosomes, depending on the growth phase"],
    },
}
RIBOSOMES_DRAWN = 6800  # the low end of the range the paper gives

SOURCES = {
    KB: {
        "what": f"UniProtKB: every reviewed entry of the reference proteome {PROTEOME} of Escherichia coli K-12 with its name, gene, locus, length, level of evidence, keywords, stated subcellular locations with the evidence for each, membrane-spanning segments, signal peptides and lipid anchors; the InterPro entries and Gene Ontology terms UniProt gives each; the proteome's own record; counts of its entries; and, for each family signature asked, how many reviewed entries of bacteria carry it",
        "licence": "CC BY 4.0",
    },
    NCBI: {"what": f"NCBI's summary of the genome record {GENOME} (Escherichia coli K-12 substrain MG1655): its title, length and topology; and GenBank's statement on the use of its data. No sequence was downloaded", "licence": "NCBI places no restrictions on the use or distribution of the GenBank data"},
    TERMS: {"what": "The pages on which two databases of this organism state their terms, read before deciding that nothing is taken from them: BioCyc's page on downloads (for EcoCyc) and the front page of STEPdb", "licence": "Each page is its owner's: kept as the record of what was read"},
    PAPERS_AT: {"what": "Two open papers from Europe PMC, each as its record there (with its licence) and its full text: one for the cell's size and volume, one for the number of its ribosomes", "licence": "CC BY, each as its record at Europe PMC states"},
}


# The organism's own databases, read for their terms and pointed to: nothing is taken from them.
POINTERS = [
    {"name": "EcoCyc", "url": "https://ecocyc.org/", "page": "https://biocyc.org/download.shtml", "file": "biocyc_download.html", "contains": "BioCyc",
     "must": r"Access to the BioCyc data files requires a paid BioCyc subscription", "none_of": None,
     "licence": "No open licence stated: its page on downloads says that access to the data files requires a paid subscription",
     "holds": "Nothing is taken from it: a pointer to the curated database of this strain's genes, proteins, pathways and regulation, where a reader finds what curators say of each protein beyond its place."},
    {"name": "STEPdb", "url": "https://stepdb.eu/", "page": "https://stepdb.eu/", "file": "stepdb_home.html", "contains": "STEPdb",
     "must": r"All datasets are freely available for download", "none_of": r"(?i)licen[cs]e|terms of use|copyright|commercial|creative commons",
     "licence": "No open licence stated: its page says that all datasets are freely available for download, and states no terms of use",
     "holds": "Nothing is taken from it: a pointer to a database of where each protein of this strain is found (the cytoplasm, the inner membrane, the periplasm, the outer membrane, outside the cell), gathered from experiments, the literature and curated prediction."},
]


# ---------------------------------------------------------------------------------------
# The table: which shelf and which side a stated place stands for, in a cell with two membranes
# ---------------------------------------------------------------------------------------
#
# The inner membrane's shelf comes first, as the contract has it for the mitochondrion's two
# membranes: what lies between the two membranes is beyond the inner one (its "outside"),
# and a protein held at the outer membrane and facing that space is on the outer shelf's
# "inside". A protein free in the periplasm therefore stands on the inner shelf, outside.

SHELVES = [
    {"id": "inner", "label": "Cell inner membrane", "outside": "In the periplasm, between the cell's two membranes", "inside": "Inside the cell: in the cytoplasm"},
    {"id": "outer", "label": "Cell outer membrane", "outside": "Outside the cell", "inside": "On the periplasmic face of the outer membrane"},
    {"id": "membrane", "label": "A membrane, not told which", "outside": "Beyond the inner membrane: in the periplasm, at the outer membrane or outside the cell", "inside": "On the cytoplasmic side of a membrane"},
]
M_, IN_, OUT_, WHOLE_, REGION_, ELSE_ = H.MEMBRANE, H.INSIDE, H.OUTSIDE, H.WHOLE, H.REGION, H.ELSEWHERE
PLACES = {
    "Cell inner membrane": ("inner", M_),
    "Cell membrane": ("inner", M_),                  # the vocabulary: "Known as the cell inner membrane in prokaryotes with 2 membranes"
    "Cytoplasm": ("inner", IN_),
    "Bacterial microcompartment": ("inner", IN_),    # the vocabulary: shells of protein that enclose enzymes, in the cytoplasm
    "Periplasm": ("inner", OUT_),                    # the vocabulary: "the space between the inner and outer membrane in Gram-negative bacteria"
    "Cell wall": ("inner", OUT_),                    # the vocabulary: the wall "is surrounded by the outer membrane" in such bacteria: it lies between the two
    "Cell outer membrane": ("outer", M_),
    "Secreted": ("outer", OUT_),
    "Fimbrium": ("outer", OUT_),                     # the vocabulary: an appendage that extends from the cell surface
    "Cell surface": ("outer", WHOLE_),               # the vocabulary: "the outermost side of the cell"; in the membrane or on it is not said
    "Bacterial flagellum": ("outer", REGION_),       # its filament and hook lie outside, its basal body reaches through both membranes: the words give no side
    "Bacterial flagellum basal body": ("inner", REGION_),  # this file's reading: the rod and rings start at the inner membrane; which part a protein is in is not said
    "Membrane": ("membrane", M_),
    "Endomembrane system": ("membrane", M_),
    "Host cell membrane": (None, ELSE_),
}
FACES = {
    "Cytoplasmic side": {"inner": "inside", "membrane": "inside"},
    "Periplasmic side": {"inner": "outside", "outer": "inside", "membrane": "outside"},  # of either membrane, the periplasm lies beyond the inner one
    "Extracellular side": {"outer": "outside", "membrane": "outside"},
}
# Where an exported protein ends up: beyond the inner membrane. Of the outer membrane it is not told.
AWAY = {"inner": "outside", "membrane": "outside"}
PEPTIDOGLYCAN_ANCHOR = "SL-9900"  # bound to the wall: it does not span a membrane
LIPID_ANCHOR = "SL-9901"
# The rules that place a protein, in the order they are tried, in this organism's words.
RULES_SAID = {
    "place": "The place itself is on one side: the cytoplasm, the periplasm, or outside the cell.",
    "spans": "The entry states that the protein spans the membrane (single-pass or multi-pass).",
    "face": "The entry states which face of the membrane the protein is on.",
    "anchor": "The entry states an anchor that holds a protein on the face away from the cytoplasm, and no face. No entry of this organism states one.",
    "later part": "The first place names no side, and a later statement of the same entry names a part of that place and gives the side.",
    "segment": "The entry states the membrane and not the side, and it carries a membrane-spanning segment: in the membrane.",
    "signal": "The entry states the inner membrane, or a membrane it does not name, and not the side, and it carries a signal peptide and no membrane-spanning segment: beyond the inner membrane. Of a protein stated at the outer membrane a signal peptide settles nothing, since every such protein has crossed the inner membrane.",
    "no place: segment": "No place of the cell is stated, and the entry carries a membrane-spanning segment: in a membrane, not told which.",
    "no place: signal": "No place of the cell is stated, and the entry carries a signal peptide and no segment: beyond the inner membrane, and how far is not told.",
    "side not stated": "The entry states the membrane or the place, and nothing in it settles the side.",
    "no place": "No place of the cell is stated and nothing is predicted: on no shelf.",
}
# The families of a unit that only go with its machine: a regulator, or a subunit that forms
# no channel or pump by itself. A unit is found where a protein carries the signature of one
# of its other families; a protein with only such a family's signature is no candidate.
ACCESSORY = {"nav_beta", "kv_beta", "cav_beta", "cav_a2d", "bk_beta", "nka_beta", "fxyd", "emre", "micu"}

# The assemblies a protein belongs to (the contract's mark `complex`), by the Gene Ontology's
# cellular-component terms as UniProt gives them to an entry, with every narrower term.
COMPLEXES = [
    ("flagellum", "GO:0009288", "bacterial-type flagellum"),
    ("chemoreceptor array", "GO:0098561", "methyl accepting chemotaxis protein complex"),
    ("ribosome", "GO:0005840", "ribosome"),
    ("RNA polymerase", "GO:0000428", "DNA-directed RNA polymerase complex"),
    ("ATP synthase", "GO:0045259", "proton-transporting ATP synthase complex"),
]
CHEMOTAXIS_KEYWORD = "Chemotaxis"
P_TYPE = "IPR001757"   # P-type ATPases, the wider family of the animal ion pumps
F_ATPASE = "IPR000194"  # the nucleotide-binding domain of the ATP synthase's alpha and beta subunits
MARKED = ["chemotaxis", "complex"]  # the marks whose holders the file also lists by line (highlights)
EXISTENCE = {1: "evidence at protein level", 2: "evidence at transcript level", 3: "inferred from homology", 4: "predicted", 5: "uncertain"}
TABLE_COLUMNS = [*H.TABLE_COLUMNS, "locus", "chemotaxis", "complex"]
UPSTREAM = ["PROSITE", "HAMAP", "TMHMM", "Phobius", "SignalP", "TargetP", "Memsat", "Predotar"]


def adopt():
    """Give the shared machinery this organism's tables and folders."""
    H.KB, H.KB_DOCS, H.IPR, H.GO = KB, KB_DOCS, IPR, GO
    H.PLACES_FILE, H.SIGNATURES_FILE = PLACES_FILE, SIGNATURES_FILE
    H.SHELVES, H.SHELF_IDS = SHELVES, [shelf["id"] for shelf in SHELVES]
    H.PLACES, H.FACES, H.AWAY = PLACES, FACES, AWAY
    H.NOT_SPANNING = {"SL-9901", "SL-9903", PEPTIDOGLYCAN_ANCHOR}


# ---------------------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------------------

def signatures_asked():
    asked = [signature for family in M.FAMILIES.values() for signature in family["signatures"]] + list(M.BACTERIAL_CHANNELS) + [M.PROTEASOME, P_TYPE, F_ATPASE]
    return sorted(set(asked))


def requests():
    out = []

    def add(source, file, url, purpose, **more):
        out.append({"source": source, "file": file, "url": url, "purpose": purpose, **more})

    q = H.q
    stream = f"{UNIPROT}/uniprotkb/stream?query={q(REVIEWED)}&compressed=true"
    add(KB, PLACES_FILE, f"{stream}&format=json&fields={PLACE_FIELDS}", "every reviewed entry of the proteome: its name, gene, locus, length, level of evidence and keywords, where the entry places it and on what evidence, its membrane-spanning segments, signals and lipid anchors", gzip=True)
    add(KB, SIGNATURES_FILE, f"{stream}&format=tsv&fields=accession,xref_interpro,go_id", "the InterPro entries and the Gene Ontology terms UniProt gives each reviewed entry", gzip=True)
    count = lambda query, more="": f"{UNIPROT}/uniprotkb/search?query={q(query)}&size=1&fields=accession&format=json{more}"
    add(KB, "count_reviewed.json", count(REVIEWED), "how many reviewed entries the proteome holds (the count is in the answer's header)")
    add(KB, "count_reviewed_with_isoforms.json", count(REVIEWED, "&includeIsoform=true"), "how many sequences the reviewed entries describe when each isoform is counted")
    add(KB, "count_unreviewed.json", count(f"(proteome:{PROTEOME}) AND (reviewed:false)"), "how many unreviewed entries the proteome holds")
    add(KB, "count_all.json", count(f"(proteome:{PROTEOME})"), "how many entries the proteome holds in all")
    add(KB, "count_reviewed_with_place.json", count(f"{REVIEWED} AND (cc_scl_term:*)"), "how many reviewed entries state a subcellular location, by UniProt's own search")
    add(KB, f"proteome_{PROTEOME}.json", f"{UNIPROT}/proteomes/{PROTEOME}", "the proteome's own record: its description, its counts and its genome assembly")
    for signature in signatures_asked():
        add(KB, f"count_bacteria_{signature}.json", count(f"(xref:interpro-{signature}) AND (taxonomy_id:{BACTERIA}) AND (reviewed:true)"), f"the control for {signature}: how many reviewed entries of bacteria carry it")
    add(NCBI, f"genbank_{GENOME}_summary.json", f"{EUTILS}/esummary.fcgi?db=nuccore&id={GENOME}&retmode=json", "the genome record's title, length and topology", contains='"slen"')
    add(NCBI, GENBANK_TERMS[1], "https://www.ncbi.nlm.nih.gov/genbank/", "GenBank's statement on the use of its data", contains="GenBank Overview")
    for pointer in POINTERS:
        add(TERMS, pointer["file"], pointer["page"], f"{pointer['name']}: the page on which its terms were read, before deciding that nothing is taken from it", contains=pointer["contains"])
    for key, paper in PAPERS.items():
        add(PAPERS_AT, f"{key}_record.json", f"{EPMC}/search?format=json&resultType=core&query=PMCID:{paper['pmc']}", "the paper's record at Europe PMC, with its licence", contains=paper["pmc"])
        add(PAPERS_AT, f"{key}_fulltext.xml", f"{EPMC}/{paper['pmc']}/fullTextXML", "the paper's full text", contains="<article")
    return out


def fetch(datasets, refresh=False, pause=1.2, tries=6):
    """Ask every request whose file is not yet saved; keep the body as it came and describe it
    in its folder's MANIFEST. A folder another agent made is read and never written."""
    datasets = Path(datasets)
    asked = failed = 0
    for request in requests():
        folder = datasets / request["source"]
        manifest = H.read_manifest(folder)
        ours = manifest is not None and MINE in manifest.get("note", "")
        held = (folder / request["file"]).exists() and any(item["name"] == request["file"] for item in (manifest or {}).get("files", []))
        if held and not (refresh and ours):
            continue
        if folder.exists() and manifest is not None and not ours:
            print(f"missing  {request['source']}/{request['file']}: the folder was made by another agent, so nothing is written there", flush=True)
            failed += 1
            continue
        record, body = {}, None
        call = urllib.request.Request(request["url"], headers={"User-Agent": CLIENT, "Accept-Encoding": "identity"})
        for attempt in range(tries):
            record, body = {"asked": H.utc_now()}, None
            try:
                with urllib.request.urlopen(call, timeout=1800) as answer:
                    body = answer.read()
                    record["status"] = answer.status
                    for header, key in [("X-Total-Results", "total_results"), ("X-UniProt-Release", "uniprot_release"), ("X-UniProt-Release-Date", "uniprot_release_date"), ("Content-Type", "content_type")]:
                        if answer.headers.get(header):
                            record[key] = answer.headers[header]
                if request.get("gzip") and not H.whole_gzip(body):
                    record["status"], body = 0, None
                    record["error"] = "the answer is not a whole gzip file"
                elif request.get("contains") and request["contains"].encode() not in body:
                    record["status"], body = 0, None
                    record["error"] = "the answer is not what was asked for"
                else:
                    break
            except urllib.error.HTTPError as error:
                record["status"] = error.code
                if error.code < 500 and error.code != 429:
                    break
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                record["status"] = 0
                record["error"] = str(getattr(error, "reason", error))[:200]
            if attempt + 1 < tries:
                time.sleep(20)
        asked += 1
        if record.get("status") != 200 or body is None:
            failed += 1
            print(f"{record.get('status')}  {request['source']}/{request['file']}  {record.get('error', '')}", flush=True)
            continue
        folder.mkdir(parents=True, exist_ok=True)
        manifest = H.read_manifest(folder)
        if manifest is None and any(folder.iterdir()):
            print(f"skipped  {request['source']}/{request['file']}: the folder holds files and no MANIFEST of this tool", flush=True)
            failed += 1
            continue
        (folder / request["file"]).write_bytes(body)
        sha, md5 = H.digest(folder / request["file"])
        entry = {"name": request["file"], "url": request["url"], "role": request["purpose"], "retrieved_utc": record["asked"], "http_status": record["status"], "content_type": record.get("content_type"), "size_bytes": len(body), "sha256": sha, "md5": md5, "expected_size": None, "expected_md5": None, "ok": True, "error": None}
        for key in ("total_results", "uniprot_release", "uniprot_release_date"):
            if record.get(key) is not None:
                entry["x_" + key] = record[key]
        manifest = manifest or {"source_id": request["source"].split("/")[-1], "files": []}
        manifest["record"] = SOURCES[request["source"]]
        manifest["files"] = sorted([item for item in manifest["files"] if item["name"] != entry["name"]] + [entry], key=lambda item: item["name"])
        manifest["manifest_written_utc"] = H.utc_now()
        manifest["note"] = f"Added by {MINE}: downloaded as untrusted data by tools/build_ecoli_atlas.py of the Cells checkout. Nothing here was executed."
        (folder / "MANIFEST.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"200  {request['source']}/{request['file']}  {len(body)}", flush=True)
        time.sleep(pause)
    print(f"asked {asked} request(s), {failed} failed or missing, under {datasets}")
    return failed


# ---------------------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------------------

def listed(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1] if items else ""


def plural(count, one, many=None):
    return f"{count:,} {one if count == 1 else many or one + 's'}"


def paper_text(d, key):
    """A paper's running text, with the licence its record gives; the build stops if a sentence a fact rests on is gone."""
    record = json.loads(d.text(PAPERS_AT, f"{key}_record.json"))["resultList"]["result"]
    found = next((item for item in record if item.get("pmcid") == PAPERS[key]["pmc"]), None)
    if found is None or (found.get("license") or "").lower() != "cc by" or found.get("doi") != PAPERS[key]["doi"]:
        raise SystemExit(f"{key}: its record at Europe PMC no longer gives the licence CC BY and the paper's DOI; read it again")
    raw = d.text(PAPERS_AT, f"{key}_fulltext.xml")
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]+>", " ", re.sub(r"(?s)<(table-wrap|ref-list)\b.*?</\1>", " ", raw))))
    text = re.sub(r"\s*\[[\d\s,\[\]]*\]\s*,?", " ", text)  # the numbers of its references
    text = re.sub(r"\s+", " ", text).replace(" ,", ",").replace(" .", ".")
    for pattern in PAPERS[key]["holds"]:
        if not re.search(pattern, text):
            raise SystemExit(f"{key}: the saved text no longer holds what a fact rests on ({pattern})")
    return text


def check_terms(d):
    """Each source's terms, read in its own saved page before anything of it is used."""
    def must(source, file, pattern, field=None):
        text = d.text(source, file)
        text = json.loads(text)[field] if field else H.plain(text)
        if not re.search(pattern, text):
            raise SystemExit(f"{source}/{file} no longer states its terms as they were read; read the page again before building")

    must(KB_DOCS, "terms_uniprot_license.json", r"We have chosen to apply the \[?Creative Commons Attribution 4\.0 International \(CC BY 4\.0\) License\]?(\([^)]*\))? to all copyrightable parts of our databases", field="content")
    must(IPR, "terms_interpro_license.html", r"All of the InterPro, Pfam, PRINTS and SFLD downloadable data provided on the InterPro website is freely available under CC0 1\.0 Universal")
    must(GO, "go_citation_policy.html", r"licensed under the Creative Commons Attribution 4\.0 Unported License")
    must(*GENBANK_TERMS, r"NCBI places no restrictions on the use or distribution of the GenBank data")
    must(*H.SAVED_TERMS["prosite"], r"distributed under the Creative Commons Attribution-NonCommercial-NoDerivatives \(CC BY-NC-ND 4\.0\) License")
    must(*H.SAVED_TERMS["hamap"], r"HAMAP is copyrighted by the SIB Swiss Institute of Bioinformatics and distributed under the Creative Commons Attribution \(CC BY 4\.0\) License")
    for tool in ("tmhmm", "signalp", "targetp"):
        must(*H.SAVED_TERMS[tool], rf"ACADEMIC SOFTWARE LICENSE AGREEMENT FOR END-USERS AT PUBLICLY FUNDED ACADEMIC, EDUCATION OR RESEARCH INSTITUTIONS FOR THE USE OF {tool}")
    must(*H.SAVED_TERMS["phobius"], r"Phobius is intended for academic users only")
    must(KB_DOCS, "help_transmem.json", r"predicted by the application of the predictive tools TMHMM, Memsat, Phobius and the hydrophobic moment plot method of Eisenberg and coworkers", field="content")
    must(KB_DOCS, "help_signal.json", r"predicted by the application of the predictive tools Phobius, Predotar, SignalP and TargetP\. At least two methods must return a positive signal peptide prediction", field="content")
    for pointer in POINTERS:
        text = H.plain(d.text(TERMS, pointer["file"]))
        if not re.search(pointer["must"], text) or (pointer["none_of"] and re.search(pointer["none_of"], text)):
            raise SystemExit(f"{pointer['name']}: its page no longer states its terms as they were read; read it again and class it again")


def unit_tail(parts, own):
    """The sentence that closes a unit's note, by what the unit is."""
    if any(part in ("connexin", "innexin") for part in parts):
        return "Gap junctions join the neighbouring cells of a tissue, and this organism lives as single cells."
    if any(part in ("serca", "ip3r", "ryr") for part in parts):
        return "No entry of its proteome states a place in an endoplasmic reticulum, the store this machine sits in."
    if "mcu" in parts:
        return "It is a bacterium: no entry of its proteome states a place in a mitochondrion."
    if any(part in ("nka_alpha", "pmca") for part in parts):
        return f"The wider family, the P-type ATPases, has {plural(len(own['p_type']), 'member')} here ({listed(own['p_type'])}), listed under extra; none carries this signature."
    if any(part in ("kcc", "nkcc", "ncx") for part in parts):
        return "Its own transporters are in its protein catalogue."
    return f"Its own ion channels are of bacterial families that no unit of the inventory stands for: {own['channels']} proteins, listed under extra."


def vocabulary_says(d, sentences):
    """UniProt's vocabulary of places still holds the sentences this file's words rest on."""
    text = re.sub(r"\s+", " ", re.sub(r"\nDE   ", " ", d.text(KB_DOCS, "subcell.txt")))
    for sentence in sentences:
        if sentence not in text:
            raise SystemExit(f"UniProt's vocabulary of places no longer says: {sentence}")


def build(datasets_folder, snapshot):
    adopt()
    d = H.Datasets(datasets_folder)
    check_terms(d)
    vocabulary = H.Vocabulary(d)
    vocabulary_says(d, [
        "Known as the cell inner membrane in prokaryotes with 2 membranes.",
        "separates the cytoplasm from the periplasm in prokaryotes with 2 membranes.",
        "separates the prokaryotic periplasm from its cell surroundings.",
        "The periplasm is the space between the inner and outer membrane in Gram-negative bacteria.",
        "is surrounded by the outer membrane in bacteria with 2 membranes",
        "plays a role in cell shape, cell stability",
        "is not surrounded by a membrane.",
    ])
    entries, read = H.read_entries(d, vocabulary)
    # This file's reading: a lipid-anchored protein whose entry says "Cell membrane", with no
    # experiment behind the statement, stands on the shelf of a membrane that is not named.
    anchored = Counter()
    for entry in entries.values():
        for index, statement in enumerate(entry["statements"]):
            if statement["topology"] != LIPID_ANCHOR:
                continue
            anchored[statement["name"]] += index == 0
            if statement["name"] == "Cell membrane" and statement["evidence"] != "experiment":
                statement["shelf"] = "membrane"
    filing = H.Filing(d, entries)
    placed = {accession: H.place(entry, vocabulary) for accession, entry in entries.items()}
    moved = [accession for accession, item in placed.items() if item["where"] and item["where"]["name"] == "Cell membrane" and item["where"]["topology"] == LIPID_ANCHOR and item["shelf"] == "membrane"]
    moved_behind = Counter(placed[accession]["where"]["evidence"] for accession in moved)
    if set(moved_behind) - {"rule", "curator", "similarity", H.NOT_GIVEN}:
        raise SystemExit(f"a lipid anchor at the cell membrane has evidence this file does not expect: {dict(moved_behind)}")
    said_places = {statement["words"] for entry in entries.values() for statement in entry["statements"]}
    for absent in ("Endoplasmic reticulum", "Golgi", "Mitochondrion", "Nucleus"):
        if any(absent in words for words in said_places):
            raise SystemExit(f"an entry states a place in the {absent}; the species file says that none does")
    raw = {item["primaryAccession"]: item for item in json.loads(d.text(KB, PLACES_FILE))["results"]}
    release = d.entry(KB, PLACES_FILE)["x_uniprot_release"]
    proteome = json.loads(d.text(KB, f"proteome_{PROTEOME}.json"))
    stated = {"reviewed": d.total(KB, "count_reviewed.json"), "sequences": d.total(KB, "count_reviewed_with_isoforms.json"), "unreviewed": d.total(KB, "count_unreviewed.json"), "all": d.total(KB, "count_all.json"), "with_place": d.total(KB, "count_reviewed_with_place.json"), "genes": proteome["geneCount"]}
    if any(d.entry(KB, file)["x_uniprot_release"] != release for file in (SIGNATURES_FILE, "count_reviewed.json", "count_reviewed_with_isoforms.json", "count_unreviewed.json", "count_all.json", "count_reviewed_with_place.json")) or vocabulary.release != release:
        raise SystemExit("the downloads from UniProt are not of one release; fetch them again")
    if stated["reviewed"] != len(entries) or stated["sequences"] != sum(entry["isoforms"] for entry in entries.values()) or stated["with_place"] != read["entries that state a place"] or stated["reviewed"] + stated["unreviewed"] != stated["all"] or proteome["proteinCount"] != stated["all"] or proteome["taxonomy"]["taxonId"] != TAXON:
        raise SystemExit(f"the entries read do not add up to UniProt's own counts: {stated}")
    gene = lambda accession: entries[accession]["gene"] or accession
    by_gene = lambda accessions: sorted((gene(a) for a in accessions), key=lambda name: H.natural(name.lower()))
    locus = {a: next((name["value"] for g in item.get("genes") or [] for name in g.get("orderedLocusNames") or [] if name["value"].startswith("b")), "") for a, item in raw.items()}
    keywords = {a: {word["name"] for word in item.get("keywords") or []} for a, item in raw.items()}

    # --- the marks: chemotaxis by UniProt's keyword, the assemblies by the Gene Ontology -------
    for word, term, name in COMPLEXES:
        if filing.terms.get(term, {}).get("name") != name:
            raise SystemExit(f"the ontology no longer calls {term} {name!r}; choose the assemblies' terms again")
    complex_of = {}
    for accession in entries:
        terms = set()
        for term in filing.entry_terms[accession]:
            usable = filing.usable(term)
            if usable:
                terms |= filing.up(usable)
        hit = next((word for word, term, _ in COMPLEXES if term in terms), None)
        if hit:
            complex_of[accession] = hit
    chemotaxis = {a for a, words in keywords.items() if CHEMOTAXIS_KEYWORD in words}
    wanted = {"cheA", "cheW", "cheY", "cheZ", "cheR", "cheB", "tsr", "tar", "trg", "tap", "aer", "motA", "motB", "fliG", "fliM", "fliN"}
    if wanted - {gene(a) for a in chemotaxis}:
        raise SystemExit(f"UniProt's keyword no longer marks the chemotaxis proteins this file promises: {sorted(wanted - {gene(a) for a in chemotaxis})}")

    # --- the atlas: the families behind Cells' units, asked of this organism ---------------------
    carriers = defaultdict(list)
    for accession, found in filing.signatures.items():
        for signature in found:
            carriers[signature].append(accession)
    control = {signature: d.total(KB, f"count_bacteria_{signature}.json") for signature in signatures_asked()}
    human_lines = d.text(HUMAN_KB, "uniprotkb_UP000005640_reviewed_signatures.tsv.gz").splitlines()[1:]
    human_signatures = {line.split("\t")[0]: set(line.split("\t")[1].split(";")) for line in human_lines}
    order = lambda accessions: sorted(set(accessions), key=lambda a: H.natural(gene(a).lower()))
    channel_hits = {signature: by_gene(carriers.get(signature, [])) for signature in M.BACTERIAL_CHANNELS}
    channels = order(accession for signature in M.BACTERIAL_CHANNELS for accession in carriers.get(signature, []))
    channels_said = "; ".join(f"{what} ({listed(channel_hits[signature])})" for signature, what in M.BACTERIAL_CHANNELS.items() if channel_hits[signature])
    own = {"p_type": by_gene(carriers.get(P_TYPE, [])), "channels": len(channels)}
    signature_name = lambda signature: filing.names[signature]["name"]
    carried = lambda family: order(accession for signature in family["signatures"] for accession in carriers.get(signature, []))
    units, beside = {}, {}  # beside: a protein with only an accessory family's signature -> [the family, the units that asked]
    for unit in snapshot["units"]:
        spec = M.UNITS[unit["id"]]
        if spec.get("finding"):
            if unit.get("products"):
                raise SystemExit(f"{unit['id']} has candidates in the inventory; it cannot be '{spec['finding']}'")
            units[unit["id"]] = {"finding": spec["finding"], "note": NOTHING[unit["id"]](own, channel_hits), "products": []}
            continue
        families = [(key, M.FAMILIES[key]) for key in spec["parts"]]
        signatures = [signature for _, family in families for signature in family["signatures"]]
        candidates = [product["human_uniprot"] for product in unit.get("products") or [] if product.get("human_uniprot")]
        for _, family in families:
            if family.get("human", True) and not any(set(family["signatures"]) & human_signatures.get(candidate, set()) for candidate in candidates):
                raise SystemExit(f"{unit['id']}: none of its human candidates carries the signature of {family['of']}; the question is not the unit's")
        makers = [family for key, family in families if key not in ACCESSORY]
        found = order(accession for family in makers for accession in carried(family))
        if found or not makers:
            # No unit's own family is carried by a protein of this organism today. If one is, the entry,
            # its products and the species file's sentences on channels and pumps are to be written for it.
            raise SystemExit(f"{unit['id']}: {by_gene(found)} carry the signature of the family that makes this machine; this tool writes no such entry yet")
        only = [(family, carried(family)) for key, family in families if key in ACCESSORY and carried(family)]
        many = len(signatures) > 1
        elsewhere = sum(control[signature] for signature in signatures)
        said = f"Among the reviewed UniProtKB entries of all bacteria, {plural(elsewhere, 'entry carries', 'entries carry')} {'one of the signatures asked' if many else 'it'}." if elsewhere else f"No reviewed UniProtKB entry of any bacterium carries {'any of the signatures asked' if many else 'it'} either."
        proof = f" The unit's human candidates carry {'them' if sum(len(family['signatures']) for _, family in families if family.get('human', True)) > 1 else 'it'}, so the search finds the family where it exists."
        if only:
            asked = f"the signature of {listed(family['of'] for family in makers)} ({', '.join(signature for family in makers for signature in family['signatures'])}), the family that makes the machine itself"
            aside = " ".join(
                f"{plural(len(hits), 'protein')} ({listed(by_gene(hits))}) carr{'ies' if len(hits) == 1 else 'y'} that of {family['of']} ({', '.join(signature for signature in family['signatures'] if carriers.get(signature))}), which go with the machine and make none by themselves: with nothing to go with, {'it is' if len(hits) == 1 else 'they are'} no candidate for the unit, and {'is' if len(hits) == 1 else 'are'} listed under extra."
                for family, hits in only
            )
            note = f"None of the {len(entries):,} proteins of its reference proteome carries {asked}. {aside} {said}{proof}"
            for family, hits in only:
                for accession in hits:
                    beside.setdefault(accession, [family, []])[1].append(unit["id"])
        else:
            asked = f"the signature of {listed(family['of'] for _, family in families)} ({', '.join(signatures)})"
            note = f"None of the {len(entries):,} proteins of its reference proteome carries {asked}. {said}{proof} {unit_tail(spec['parts'], own)}"
        units[unit["id"]] = {"finding": "none found", "note": note, "products": []}
    if set(units) != {unit["id"] for unit in snapshot["units"]}:
        raise SystemExit("the units of the atlas are not the units of the inventory")
    unit_ids = {}  # no protein of this organism is a candidate for a unit: none is drawn as one

    # The organism's own membrane machines that bear on what the atlas draws and match no unit.
    extra, seen_extra = [], set()

    def add_extra(accession, role, signature, why):
        if accession in seen_extra:
            return
        seen_extra.add(accession)
        entry = entries[accession]
        extra.append({"name": entry["name"], "gene": entry["gene"] or None, "role": role, "ids": [{"db": "uniprot", "id": accession}], "length": entry["length"], "evidence": "reviewed entry", "evidence_note": f"Its reviewed UniProtKB entry names it \"{entry['name']}\", with UniProt's level of evidence \"{EXISTENCE[entry['seen']]}\". The entry carries {signature} ({signature_name(signature)}).", "citation": None, "why": why})

    for signature, what in M.BACTERIAL_CHANNELS.items():
        for accession in order(carriers.get(signature, [])):
            add_extra(accession, "channel", signature, f"Carries the signature of {what}. The law inventory has no unit for this family; it is one of the cell's own channels.")
    for accession in order(carriers.get(P_TYPE, [])):
        add_extra(accession, "ion pump", P_TYPE, "A P-type ATPase, of the wider family of the animal ion pumps; it carries the signature of neither the sodium-potassium pump nor the calcium pumps that the inventory has units for.")
    for accession in order(carriers.get(F_ATPASE, [])):
        if complex_of.get(accession) == "ATP synthase":
            add_extra(accession, "catalytic head", F_ATPASE, "Part of the cell's F-type ATP synthase, which sits in its inner membrane. The law inventory has no F-type ATPase.")
    for accession in order(beside):
        family, asked_by = beside[accession]
        signature = next(signature for signature in family["signatures"] if accession in carriers.get(signature, []))
        add_extra(accession, "accessory-subunit family", signature, f"Carries the family signature of {family['of']}, which go with a channel and make none by themselves. No protein of this organism carries the signature of a family that makes such a channel, so it is a candidate for no unit ({asked_by[0]} to {asked_by[-1]} asked for it).")

    # --- the lines of the shelves ---------------------------------------------------------------
    lines, alone, rest = H.make_lines(entries, placed, filing, unit_ids)
    sequence = [protein for line in [*lines, *alone, *rest] for protein in line["proteins"]]
    if len(sequence) != len(entries) or len(set(sequence)) != len(entries):
        raise SystemExit("a protein is filed twice or not at all")
    SIDES, NO_SHELF = H.SIDES, H.NO_SHELF
    key = lambda shelf: NO_SHELF if shelf is None else shelf
    all_sides = Counter(item["side"] for item in placed.values())
    shelf_counts = {name: {side: 0 for side in SIDES} for name in [*H.SHELF_IDS, NO_SHELF]}
    for item in placed.values():
        shelf_counts[key(item["shelf"])][item["side"]] += 1
    bases = Counter((item["side"], item["basis"]) for item in placed.values())
    rules = Counter(item["rule"] for item in placed.values())
    evidence = Counter(item["evidence"] for item in placed.values() if item["evidence"])
    family_total = Counter(filing.family.values())
    distinct = len({line["id"] for line in lines})
    lone_families = sum(1 for count in family_total.values() if count <= H.LONE_UP_TO)
    plain_words = sum(1 for item in placed.values() if item["where"] and item["where"]["name"] == "Cell membrane" and item["shelf"] == "inner")
    unnamed = sum(1 for item in placed.values() if item["where"] and item["shelf"] == "membrane" and item["where"]["name"] != "Cell membrane")
    behind_moved = "; ".join(f"{what}: {moved_behind[word]}" for word, what in (("rule", "a rule of PROSITE or HAMAP"), ("curator", "a curator's inference"), ("similarity", "likeness to another protein"), (H.NOT_GIVEN, "no evidence given")) if moved_behind[word])
    shelf_notes = {
        "inner": f"Here stand also the {plain_words} proteins whose entry says \"Cell membrane\" and not which: UniProt's vocabulary says that the cell membrane is known as the inner membrane where a cell has two. The lipid-anchored ones among them stand on the shelf of a membrane that is not named.",
        "outer": "On its inside stand only proteins that an entry places at the outer membrane's periplasmic face. A protein free in the periplasm stands on the inner membrane's shelf, on its outside.",
        "membrane": f"Three kinds of protein. The {unnamed} that an entry places in a membrane without naming it. The {len(moved)} lipid-anchored ones whose entry says \"Cell membrane\" with no experiment behind the statement ({behind_moved}): this file reads those words as not telling which membrane, since an entry that tells the membrane of a lipid-anchored protein names it, \"Cell inner membrane\" in {anchored['Cell inner membrane']} entries and \"Cell outer membrane\" in {anchored['Cell outer membrane']}. And the {rules['no place: signal'] + rules['no place: segment']} with no stated place whose entry carries a signal peptide: such a protein was carried across the inner membrane, and how far beyond it is not told.",
    }
    shelves = []
    for shelf in SHELVES:
        on = [line for line in lines if line["shelf"] == shelf["id"]]
        here = sum(len(line["proteins"]) for line in alone if line["shelf"] == shelf["id"])
        shelves.append({**shelf, "note": shelf_notes[shelf["id"]], "proteins": sum(shelf_counts[shelf["id"]].values()), "families": len(on) + here, "lines": len(on), "lone": here, "no_family": sum(len(line["proteins"]) for line in rest if line["shelf"] == shelf["id"])})
    none = [line for line in lines if line["shelf"] is None]
    here = sum(len(line["proteins"]) for line in alone if line["shelf"] is None)
    no_shelf = {"proteins": sum(shelf_counts[NO_SHELF].values()), "families": len(none) + here, "lines": len(none), "lone": here, "no_family": sum(len(line["proteins"]) for line in rest if line["shelf"] is None)}
    groups = []
    for group in H.DISTRICT_ORDER:
        asked = next((asked for key_, _, asked in H.DISTRICTS if key_ == group), None)
        said_from = "Gene Ontology terms: " + ", ".join(f"{name} ({term})" for term, name in asked) if asked else "The line's proteins carry Gene Ontology terms, and none of the districts' terms" if group == H.OTHER_DISTRICT[0] else "The line's proteins carry no Gene Ontology term"
        on = [line for line in lines if line["group"] == group]
        groups.append({"id": group, "label": H.DISTRICT_LABEL[group], "from": said_from, "lines": len(on), "proteins": sum(len(line["proteins"]) for line in on), "lone": sum(len(line["proteins"]) for line in alone if line["group"] == group)})

    first_places = Counter(item["where"]["name"] for item in placed.values() if item["where"])
    used = {statement["name"] for entry in entries.values() for statement in entry["statements"]}
    place_rows = []
    for name in sorted(used, key=lambda name: (-first_places[name], name)):
        shelf, kind, how, under = vocabulary.resolve(name)
        place_rows.append([vocabulary.by_name[name]["accession"], vocabulary.by_name[name]["path"], shelf, kind, how, under, first_places[name]])
    codes_used = {part for entry in entries.values() for statement in entry["statements"] for part in H.code(statement).split(".")}
    place_words = {term["accession"][3:]: term["path"] for term in sorted(vocabulary.terms.values(), key=lambda term: term["accession"]) if term["accession"][3:] in codes_used}

    # What stands between the two membranes, by the rule this file builds by.
    on = lambda shelf, side, rule=None: sum(1 for item in placed.values() if item["shelf"] == shelf and item["side"] == side and (rule is None or (item["rule"] == "place") == rule))
    between = {
        "free in the periplasm or in the wall: the inner membrane's shelf, outside": on("inner", "outside", True),
        "held at the inner membrane and facing the periplasm: the inner membrane's shelf, outside": on("inner", "outside", False),
        "held at the outer membrane and facing the periplasm: the outer membrane's shelf, inside": on("outer", "inside"),
        "beyond the inner membrane, in a place that is not told: the shelf of a membrane that is not named, outside": on("membrane", "outside"),
    }

    resting, rule_ids = H.account(entries, placed)
    signal_on = Counter(item["shelf"] for item in placed.values() if item["rule"] == "signal")
    if set(signal_on) - {"inner", "membrane"} or rules["no place: segment"]:
        raise SystemExit("a signal peptide or a segment places a protein where the file's words do not say")
    if set(resting) - {"PROSITE-ProRule", "HAMAP-Rule", "RuleBase", "segments", "signal", "unnamed analysis"}:
        raise SystemExit(f"a placement rests on a rule system or an analysis the sources do not name: {sorted(resting)}")
    of = lambda owner, what="placements": resting.get(owner, {}).get(what, 0)
    PLACE, SPANS, FACE = "the stated place", "the statement that it spans the membrane", "the stated face"
    FROM_SEGMENTS, FROM_SIGNAL = "a side read from its segments", "a side read from its signal peptide"
    predictors = "TMHMM, Memsat, Phobius and a hydrophobic moment plot for the segments; Phobius, Predotar, SignalP and TargetP for the signal peptides"
    ruling = "By the project's rule (the user, 15 November 2026), a value stands on the terms of the database it was read from, and the tool behind it is named and counted: the project's rule, not a legal opinion."

    made = d.last_day()
    header = {
        "format": H.SHELF_FORMAT,
        "species": SPECIES_ID,
        "made": made,
        "from": f"UniProtKB release {release}: the {stated['reviewed']:,} reviewed entries of the reference proteome {PROTEOME} of Escherichia coli strain K-12, one protein each; with the other forms that {sum(1 for entry in entries.values() if entry['isoforms'] > 1)} of them describe, {stated['sequences']:,} sequences. The proteome holds {plural(stated['unreviewed'], 'unreviewed entry', 'unreviewed entries')}: every protein of it is listed, for {stated['genes']:,} genes.",
        "from_counts": {"reviewed": stated["reviewed"], "isoforms": stated["sequences"] - stated["reviewed"], "sequences": stated["sequences"], "unreviewed": stated["unreviewed"], "entries": stated["all"], "genes": stated["genes"], "state_a_place": stated["with_place"]},
        "predicted": False,
        "shelves": shelves,
        "no_shelf": no_shelf,
        "between": {"rule": "A protein free in the space between the two membranes (the periplasm, and the wall that lies in it) stands on the inner membrane's shelf, on its outside. A protein held at a membrane and facing that space stands on that membrane's shelf, on the side that faces the space: the outside of the inner shelf, the inside of the outer. A protein known only to lie beyond the inner membrane stands on the outside of the shelf of a membrane that is not named.", "counts": between},
        "groups": groups,
        "groups_from": "A protein's Gene Ontology terms are those InterPro maps to any of its signatures and those UniProt gives its entry. With every broader term (by the ontology's kind-of and part-of links), the protein falls in the first district, in the order listed, one of whose terms it carries. A family's line stands in the district most of its classed members on that shelf fall in; of equal counts, the first listed. A protein that is the only member of its family stands in its own district. A part of no_family is a looser grouping: it stands in a district only if more than half of all its members on that shelf fall there. The choice of the districts' terms and their order is the viewer's, and is the planarian's and the human's.",
        "family_from": f"A family is an InterPro entry of the type Family (InterPro {filing.release}). A protein is filed under the narrowest family among the InterPro entries UniProt gives it: one that is not a broader kind of another it carries, by InterPro's tree of entries. Where several unrelated families remain ({filing.several:,} proteins), it is the deepest in that tree, then the one fewest proteins of this catalogue are in, then the first by accession. This is the rule of the planarian's and the human's files, so a family has the same id in each.",
        "family_columns": H.FAMILY_COLUMNS,
        "family_notes": {
            "lines": "A family has one line for each shelf that holds members of it, and one with a null shelf for its members that are on no shelf. A line is identified by id and shelf together; side, group, count, sides, file, at and units are of its members on that shelf alone.",
            "side": "The side most of the line's members sit on; of equal counts, a membrane first.",
            "units": "The inventory units for which a member on this line carries the family's signature: candidates by family alone.",
            "total": "The family's members on every shelf and on none.",
            "counts": "distinct_families is the number of families that have lines; families_in_all counts also the families of one, whose proteins are under 'lone'. In 'shelves' and 'no_shelf', 'families' is every family with a member there (its lines and its lone proteins), 'lines' the families' lines there, 'lone' the proteins that are the only member of their family, 'no_family' those with none.",
        },
    }
    lone_sides = Counter(side for line in alone for side, count in line["sides"].items() for _ in range(count))
    lone = {"label": H.LONE_LABEL, "count": sum(len(line["proteins"]) for line in alone), "families": lone_families, "sides": H.ordered_sides(lone_sides), "parts_from": f"A family with a single member in this catalogue does not open, so it has no line among the families: {lone_families:,} families of one. Their proteins are listed here together, one part for each shelf, district and side, and each names its family in its mark 'family'. A part is not a family.", "part_columns": H.PART_COLUMNS}
    no_family = {"label": "No family assigned", "count": len(filing.part), "sides": H.ordered_sides(Counter(placed[protein]["side"] for protein in filing.part)), "parts_from": "A protein with no family is filed under one part. If it carries an InterPro entry of the type Homologous superfamily, the part is that superfamily: a wider grouping than a family, by shared structure. Of several superfamilies it is the one fewest proteins of this catalogue carry, then the first by accession. The other two parts hold the proteins with only a domain, repeat or site signature, and those with no signature at all. A part has one line for each shelf, as a family has.", "part_columns": H.PART_COLUMNS}
    files = sorted({line["file"] for line in [*lines, *alone, *rest]})
    complexes_said = {word: by_gene(a for a, found in complex_of.items() if found == word) for word, _, _ in COMPLEXES}
    tail = {
        "member_columns": ["id", "label", "gene", "side", "basis", "length", "unit", "marks"],
        "members_from": {
            "table": f"data/proteins/{SPECIES_ID}/{H.TABLE_FILE}",
            "format": H.MEMBERS_FORMAT,
            "order": "The table's lines are the members in order: every line of the families as listed here, then every part of 'lone', then every part of 'no_family'; within each, by gene name. A line's members are the next 'count' lines of the table. For a family's line and for a part of no_family, 'under' is its id and 'shelf' its shelf (empty for none); for a part of 'lone', 'under' is the protein's own family and 'family' that family's name.",
            "files": f"A file holds the members of consecutive lines: a new file begins where the next line would take it past {H.MEMBERS_PER_FILE:,} members, so a line is never split. 'file' names the file and 'at' the first and one past the last of its members there. A member's shelf is its line's.",
            "places": "In the table a stated place is written with UniProt's identifiers, without their prefix: the place, then the topology and the face where the entry states them, joined by a full stop (0037.9909 is SL-0037 with SL-9909). 'place_words' gives the words of each.",
            "letters": {"basis": {letter: word for word, letter in H.BASIS_LETTER.items()}, "evidence": {letter: word for word, letter in H.EVIDENCE_LETTER.items()}, "seen": {str(level): H.SEEN[level] for level in sorted(H.SEEN)}},
            "step": "python3 tools/build_ecoli_atlas.py members --out DIR writes the files from the two files.",
        },
        "side_notes": {
            "stated": "The protein's reviewed UniProtKB entry states where it is, and the first place it states decides the shelf and the side: the cytoplasm, the periplasm or outside the cell; a membrane the protein is said to span; or a membrane with the face the protein is on. Where the first place names no side, a later statement of the same entry that names a part of that place decides. The mark 'evidence' says what stands behind the statement.",
            "predicted": f"Read from the entry's own features, where its words do not give the side. A membrane-spanning segment puts the protein in the membrane its entry states ({rules['segment']} proteins). A signal peptide with no such segment says that the protein was carried across the inner membrane: it stands on the outside of the inner membrane's shelf where the entry states that membrane ({signal_on['inner']} proteins), and on the outside of the shelf of a membrane that is not named where the entry does not tell the membrane ({signal_on['membrane']}) or states no place ({rules['no place: signal']}). UniProt's curators annotate these features from experiments, from likeness to other proteins and from prediction; its own pages name the predictors: {predictors}. Each is named among the sources, with its terms and what rests on it. {ruling}",
            "none": "The entry states a membrane or a place and not the side (the protein then stands apart beside that shelf, with the place in its mark 'where'), or it states no place of the cell and carries no membrane-spanning segment and no signal peptide (the protein is then on no shelf). Nothing is placed by guess.",
        },
        "placed_by": [{"rule": rule, "basis": basis, "what": RULES_SAID[rule], "proteins": rules[rule]} for rule, basis, _ in H.RULES_USED],
        "place_kinds": H.KINDS,
        "place_columns": ["id", "words", "shelf", "names", "resolved", "under", "first"],
        "place_notes": "Every place the entries state, in UniProt's words, with the shelf and what the place names against its membrane (place_kinds), how the table's line was reached and which of the table's terms it rests on, and how many proteins it places as the statement that decided. One reading of this file goes beyond the table: a lipid-anchored protein whose entry says \"Cell membrane\", with no experiment behind the statement, stands on the shelf of a membrane that is not named (that shelf's note says why and how many).",
    }
    marks = {
        "isoforms": {"label": "Forms described", "values": "number", "measured": False, "note": "The canonical sequence and the other sequences its entry describes: in this organism, forms that start at another codon of the same gene. The marker stands for the canonical one.", "source": "UniProt"},
        "seen": {"label": "Evidence that the protein exists", "values": [H.SEEN[level] for level in sorted(H.SEEN)], "measured": False, "note": "UniProt's level of evidence for the entry: at protein level, at transcript level, inferred from homology, predicted, or uncertain.", "source": "UniProt"},
        "evidence": {"label": "What stands behind the stated place", "values": [word for word, _, _ in H.EVIDENCE] + [H.NOT_GIVEN], "measured": False, "note": "From UniProt's evidence codes on the statement: " + "; ".join(f"{word}: {what}" for word, _, what in H.EVIDENCE) + f"; {H.NOT_GIVEN}: the entry gives no code, an older curated statement. Of several, the first in this order.", "source": "UniProt"},
        "where": {"label": "Stated place", "values": "text", "measured": False, "note": "The statement that decided the shelf, in UniProt's words: the place, then the topology and the face where the entry states them.", "source": "UniProt"},
        "also": {"label": "Also stated", "values": "text", "measured": False, "note": "The entry's other statements of place, in order and in UniProt's words.", "source": "UniProt"},
        "family": {"label": "Family, of which it is the only member here", "values": "text", "measured": False, "note": "The InterPro family's accession and name, for a protein listed among the only members of their families.", "source": "InterPro"},
        "of": {"label": "Stated for", "values": "text", "measured": False, "note": "The named form of the protein that the place is stated for, where the entry states none for the protein as a whole.", "source": "UniProt"},
        "locus": {"label": "Locus", "values": "text", "measured": False, "note": "The gene's ordered locus name in the genome of strain K-12 substrain MG1655 (its b number), as UniProt gives it.", "source": "UniProt"},
        "chemotaxis": {"label": "Chemotaxis", "values": [True], "measured": False, "note": f"The entry carries UniProt's keyword 'Chemotaxis': the receptors, the proteins that pass their signal on, the motor's switch and stator, and the binding proteins that report sugars and peptides. {len(chemotaxis)} proteins: {listed(by_gene(chemotaxis))}.", "source": "UniProt"},
        "complex": {"label": "Assembly it is part of", "values": [word for word, _, _ in COMPLEXES], "measured": False, "note": "By the Gene Ontology's cellular-component terms that UniProt gives the entry, with every narrower term: " + "; ".join(f"{word} ({name}, {term}): {len(complexes_said[word])}" for word, term, name in COMPLEXES) + ". Of several, the first listed.", "source": "Gene Ontology"},
    }
    counts = {side: all_sides.get(side, 0) for side in SIDES}
    cite_uniprot = "The UniProt Consortium, UniProt: the Universal Protein Knowledgebase in 2025, Nucleic Acids Res. 53:D609-D617 (2025)"
    cite_interpro = "Blum and others (2025) InterPro: the protein sequence classification resource in 2025. Nucleic Acids Res 53:D444-D456."
    terms_day = lambda name: d.day(*H.SAVED_TERMS[name])
    sources = [
        {"name": "UniProt", "url": "https://www.uniprot.org/", "release": release, "accessed": d.day(KB, PLACES_FILE), "licence": "CC BY 4.0", "class": "permissive", "cite": cite_uniprot,
         "holds": f"for each reviewed entry of the reference proteome: its name, gene, locus, length, level of evidence and keywords, the places it states with the evidence for each, its membrane-spanning segments and signal peptide, and the InterPro entries and Gene Ontology terms UniProt gives it; and UniProt's vocabulary of places. The programs that its pages name behind the segments and signal peptides it predicts are sources below. Of its own: {plural(of('RuleBase'), 'statement rests', 'statements rest')} on a rule of its rule base, and {plural(of('unnamed analysis'), 'stated place rests', 'stated places rest')} on a sequence analysis for which it names no program"},
        {"name": "InterPro", "url": "https://www.ebi.ac.uk/interpro/", "release": filing.release, "accessed": d.day(IPR, "entry.list"), "licence": "CC0 1.0", "class": "permissive", "cite": cite_interpro, "holds": "the type and name of each entry, the tree of broader and narrower entries, and the mapping of entries to Gene Ontology terms"},
        {"name": "Gene Ontology", "url": "https://geneontology.org/", "release": filing.ontology, "accessed": d.day(GO, "go-basic.obo"), "licence": "CC BY 4.0", "class": "permissive", "cite": H.ontology_citation(d), "holds": "the names of terms and which term is a kind or a part of which; no term's text is copied beyond the names of the districts' and the assemblies' terms"},
        {"name": "PROSITE", "url": "https://prosite.expasy.org/prosite_license.html", "licence": "CC BY-NC-ND 4.0; commercial users are asked to pay a yearly licence fee", "class": "non-commercial", "accessed": terms_day("prosite"), "through": "UniProt",
         "holds": f"Nothing was downloaded from it but its statement of terms, and nothing of it is copied. Its rules (ProRule) are named in UniProt's entries as what stands behind a statement. {of('PROSITE-ProRule'):,} placements rest on them alone: {of('PROSITE-ProRule', PLACE):,} by the statement of place that decides the shelf ({len(rule_ids.get('PROSITE-ProRule', {})):,} rules), {of('PROSITE-ProRule', SPANS):,} by the statement that the protein spans the membrane, and {of('PROSITE-ProRule', FROM_SEGMENTS) + of('PROSITE-ProRule', FROM_SIGNAL):,} by a side read here from a feature that a rule gives."},
        {"name": "HAMAP", "url": "https://hamap.expasy.org/hamap_about.html", "licence": "CC BY 4.0", "class": "permissive", "accessed": terms_day("hamap"), "through": "UniProt",
         "holds": f"Nothing was downloaded from it but its statement of terms. Its family rules are named in UniProt's entries as what stands behind a statement. {of('HAMAP-Rule'):,} placements rest on them alone: {of('HAMAP-Rule', PLACE):,} by the statement of place that decides the shelf ({len(rule_ids.get('HAMAP-Rule', {})):,} rules), {of('HAMAP-Rule', SPANS):,} by the statement that the protein spans the membrane, {of('HAMAP-Rule', FACE):,} by the stated face, and {of('HAMAP-Rule', FROM_SEGMENTS) + of('HAMAP-Rule', FROM_SIGNAL):,} by a side read here from a feature that a rule gives."},
        {"name": "TMHMM", "url": "https://services.healthtech.dtu.dk/services/TMHMM-2.0/", "licence": H.DTU_LICENCE, "class": "non-commercial", "accessed": terms_day("tmhmm"), "through": "UniProt",
         "holds": f"{H.NOT_RUN} {H.FOUR_SEGMENTS}. {of('segments'):,} placements rest on segments that an entry gives by sequence analysis alone: {of('segments', FROM_SEGMENTS):,} are read here from such segments (basis predicted; {rules['segment'] + rules['no place: segment']:,} are read from segments in all), and behind a curator's statement {of('segments', SPANS):,} are said to span the membrane on a sequence analysis and {of('segments', PLACE):,} have a stated place that rests on a sequence analysis in an entry with such segments."},
        {"name": "Phobius", "url": "https://phobius.sbc.su.se/download", "licence": "For academic users only: the program may be used for private study, education or nonprofit research, and other users are asked to write to its author. The terms are of the program: they do not speak of predictions made with it", "class": "non-commercial", "accessed": terms_day("phobius"), "through": "UniProt",
         "holds": f"{H.NOT_RUN} {H.FOUR_SEGMENTS}; and one of the four it names for signal peptides. The placements are those counted under TMHMM ({of('segments'):,}) and under SignalP ({of('signal'):,})."},
        {"name": "SignalP", "url": "https://services.healthtech.dtu.dk/services/SignalP-5.0/", "licence": H.DTU_LICENCE, "class": "non-commercial", "accessed": terms_day("signalp"), "through": "UniProt",
         "holds": f"{H.NOT_RUN} {H.FOUR_SIGNALS}. {of('signal'):,} placements rest on a signal peptide that an entry gives by sequence analysis alone: {of('signal', FROM_SIGNAL):,} are read here from such a signal (basis predicted; {rules['signal'] + rules['no place: signal']:,} are read from a signal peptide in all), and behind a curator's statement {of('signal', PLACE):,} have a stated place that rests on a sequence analysis in an entry with such a signal and no such segment."},
        {"name": "TargetP", "url": "https://services.healthtech.dtu.dk/services/TargetP-2.0/", "licence": H.DTU_LICENCE, "class": "non-commercial", "accessed": terms_day("targetp"), "through": "UniProt", "holds": f"{H.NOT_RUN} {H.FOUR_SIGNALS}. The placements are those counted under SignalP ({of('signal'):,})."},
        {"name": "Memsat", "url": "https://www.uniprot.org/help/transmem", "licence": "Terms not read: UniProt's help names Memsat without a version or an address, so no page of terms could be tied to the program it runs", "class": "no stated terms", "accessed": d.day(KB_DOCS, "help_transmem.json"), "through": "UniProt", "holds": f"Nothing was downloaded from it. {H.FOUR_SEGMENTS}. The placements are those counted under TMHMM ({of('segments'):,})."},
        {"name": "Predotar", "url": "https://www.uniprot.org/help/signal", "licence": "Terms not read: the program's own page answers this tool with a check for a browser, so its terms could not be read", "class": "no stated terms", "accessed": d.day(KB_DOCS, "help_signal.json"), "through": "UniProt", "holds": f"Nothing was downloaded from it. {H.FOUR_SIGNALS}. The placements are those counted under SignalP ({of('signal'):,})."},
    ]
    # The organism's own databases are pointed to in the README and the note, not here: the scene carries
    # every species' sources, within a limit, and nothing of these two is in the file.
    pointers = [{"name": pointer["name"], "url": pointer["url"], "licence": pointer["licence"], "class": "no stated terms", "accessed": d.day(TERMS, pointer["file"]), "holds": pointer["holds"]} for pointer in POINTERS]
    # The marks that pick out a machine: each protein that carries one, with the line it stands on.
    line_of = {}
    for kind, found in (("family", lines), ("lone", alone), ("part", rest)):
        for line in found:
            for protein in line["proteins"]:
                line_of[protein] = (kind, line["id"])
    marked = {"chemotaxis": {a: True for a in chemotaxis}, "complex": complex_of}
    highlight_rows = []
    for name in MARKED:
        values = [True] if name == "chemotaxis" else [word for word, _, _ in COMPLEXES]
        for value in values:
            for accession in order(a for a, found in marked[name].items() if found == value):
                highlight_rows.append([name, value, accession, entries[accession]["gene"], *line_of[accession], placed[accession]["shelf"], placed[accession]["side"]])
    highlights = {
        "note": "For the marks that pick out a machine (chemotaxis, and the assemblies of 'complex'): each protein that carries the mark, with the line it stands on, so that a page can light the markers that hold them without opening every family. 'kind' says whether 'under' is a family, a part of 'lone' or a part of 'no_family'; a null shelf is no shelf.",
        "columns": ["mark", "value", "id", "gene", "kind", "under", "shelf", "side"],
    }
    if [source["name"] for source in sources if source.get("through")] != UPSTREAM:
        raise SystemExit("the sources read through UniProt are not the ones this tool names")
    closing = {"marks": marks, "highlights": highlights, "counts": counts, "shelf_counts": shelf_counts, "by_basis": {side: {basis: bases[side, basis] for basis in ("stated", "predicted", "none") if bases.get((side, basis))} for side in SIDES}, "by_evidence": {word: evidence.get(word, 0) for word in [word for word, _, _ in H.EVIDENCE] + [H.NOT_GIVEN]}, "sources": sources}

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
    text = json.dumps(closing, indent=1, ensure_ascii=False)
    mark = '"columns": [\n   "mark",\n   "value",\n   "id",\n   "gene",\n   "kind",\n   "under",\n   "shelf",\n   "side"\n  ]'
    if text.count(mark) != 1:
        raise SystemExit("the highlights' columns are not where the writer expects them")
    text = text.replace(mark, '"columns": ' + compact(highlights["columns"]) + ',\n  "rows": ' + rows(highlight_rows, "  "))
    body += "," + text[1:] + "\n"
    json.loads(body)

    lone_of = {protein for line in alone for protein in line["proteins"]}
    table_rows = []
    for protein in sequence:
        entry, item = entries[protein], placed[protein]
        under = filing.family.get(protein) or filing.part[protein]
        table_rows.append([
            protein, entry["gene"], entry["name"], str(entry["length"]), str(entry["isoforms"]), str(entry["seen"]), under, item["shelf"] or "", item["side"], H.BASIS_LETTER[item["basis"]], H.EVIDENCE_LETTER[item["evidence"]] if item["evidence"] else "",
            H.code(item["where"]) if item["where"] else "", ",".join(H.code(statement) for statement in item["also"]), ";".join(unit_ids.get(protein, [])),
            filing.names[under]["name"] if protein in lone_of else "", entry["of"] or "", locus[protein], "1" if protein in chemotaxis else "", complex_of.get(protein, ""),
        ])
    for row in table_rows:
        if any("\t" in value or "\n" in value for value in row):
            raise SystemExit(f"{row[0]}: a value of the table holds a tab or a line break")
    table = "\n".join("\t".join(row) for row in [TABLE_COLUMNS, *table_rows]) + "\n"

    # --- the species file ---------------------------------------------------------------------
    summary = json.loads(d.text(NCBI, f"genbank_{GENOME}_summary.json"))["result"]
    record = next(value for key_, value in summary.items() if key_ != "uids")
    if record.get("accessionversion") != GENOME or "K-12" not in record.get("title", "") or record.get("topology") != "circular":
        raise SystemExit("the genome record's summary is not the one this file names")
    genome_length = int(record["slen"])
    for paper in PAPERS:
        paper_text(d, paper)
    description = proteome["description"]
    for sentence in ("Gram-negative straight rod, which either uses peritrichous flagella for mobility or is nonmotile", "facultatively anaerobic chemoorganotroph capable of both respiratory and fermentative metabolism", "colonizes the lower gut of animals and survives when released to the natural environment"):
        if sentence not in description:
            raise SystemExit("UniProt's description of the proteome no longer says what a fact rests on")
    proteasome = order(carriers.get(M.PROTEASOME, []))
    if len(proteasome) > 1:
        raise SystemExit("several proteins carry the proteasome's signature; write the sentence on them again")
    proteasome_said = f"One of its proteins carries the signature of the proteasome's subunits: its entry names it \"{entries[proteasome[0]]['name']}\"." if proteasome else "None of its proteins carries the signature of the proteasome's subunits."
    two_component = sum(1 for words in keywords.values() if "Two-component regulatory system" in words)
    by_name = {gene(a): a for a in entries}
    names_needed = {"secY": "Protein translocase subunit SecY", "tatA": "Sec-independent protein translocase protein TatA", "ftsZ": "Cell division protein FtsZ", "aqpZ": "Aquaporin Z"}
    for needed, name in names_needed.items():
        if entries.get(by_name.get(needed), {}).get("name") != name:
            raise SystemExit(f"the proteome no longer names {needed} {name!r}, which a sentence of the species file rests on")
    if "aqpZ" not in channel_hits["IPR000425"] or not channels:
        raise SystemExit("the proteins of bacterial channel families are not the ones the species file speaks of")
    synthase = [a for a, found in complex_of.items() if found == "ATP synthase"]
    if not synthase or any(placed[a]["shelf"] != "inner" for a in synthase) or any(placed[by_name[name]]["shelf"] != "inner" for name in own["p_type"]):
        raise SystemExit("the ATP synthase or a P-type ATPase is not stated at the inner membrane; the species file says that they are")
    secreted = sum(1 for item in placed.values() if item["where"] and item["where"]["name"] == "Secreted")
    porins = sum(1 for words in keywords.values() if "Porin" in words)
    if not secreted or not porins:
        raise SystemExit("no protein is stated to be secreted, or none carries the keyword Porin; the species file says that some do")
    uniprot_source = {"text": f"UniProt Consortium, UniProt release {release}: the reviewed entries of the reference proteome {PROTEOME} (Escherichia coli strain K-12), the proteome's own description, and UniProt's vocabulary of subcellular locations.", "url": f"https://www.uniprot.org/proteomes/{PROTEOME}", "licence": "CC BY 4.0", "class": "permissive", "accessed": d.day(KB, PLACES_FILE)}
    species_sources = {
        "uniprot": uniprot_source,
        "genbank": {"text": f"GenBank {GENOME}: {record['title']}.", "url": f"https://www.ncbi.nlm.nih.gov/nuccore/{GENOME}", "licence": "No restriction: \"NCBI places no restrictions on the use or distribution of the GenBank data\".", "class": "permissive", "accessed": d.day(NCBI, f"genbank_{GENOME}_summary.json")},
        **{key_: {"text": paper["text"], "doi": paper["doi"], "licence": "CC BY", "class": "permissive", "accessed": d.day(PAPERS_AT, f"{key_}_fulltext.xml")} for key_, paper in PAPERS.items()},
    }
    capabilities = {
        "cap.membrane": {"place": "present", "note": "It has two membranes. By UniProt's vocabulary the inner one separates the cytoplasm from the periplasm, and the outer one the periplasm from the cell's surroundings. No source read for this file measured a voltage across either."},
        "cap.channels": {"place": "present", "note": f"Not the channels of animal cells: none of its proteins carries the signature of a channel family that Cells has a law for. {len(channels)} of its proteins carry the signature of a bacterial channel family: {channels_said}."},
        "cap.pumps": {"place": "present", "note": f"Not the pumps of animal cells: none of its proteins carries the signature of the sodium-potassium pump. Its P-type ATPases ({listed(own['p_type'])}) and its ATP synthase are stated to be in the inner membrane."},
        "cap.junctions": {"place": "absent", "why": "It lives as single cells and has no gap junctions: none of its proteins carries the signature of connexins or innexins."},
        "cap.extracellular": {"place": "present", "note": "Two spaces lie beyond its inner membrane: the periplasm, between its two membranes, and what surrounds the cell, the lower gut of an animal or wherever it is released."},
        "cap.water": {"place": "present", "note": "By UniProt's vocabulary a wall lies between its two membranes and plays a part in the cell's shape and stability. One of its proteins, AqpZ, carries the signature of the aquaporin family."},
        "cap.calcium": {"place": "absent", "why": "It has no endoplasmic reticulum, the store this capability concerns: no entry of its proteome states a place in one, and none of its proteins carries the signature of the store's calcium pump or of its release channels."},
        "cap.energy": {"place": "present", "note": "It lives by respiration and by fermentation, with or without oxygen; its ATP synthase is stated to be in the inner membrane."},
        "cap.mitochondria": {"place": "absent", "why": "It is a bacterium and has no mitochondria: no entry of its proteome states a place in one. Its ATP synthase is in the inner membrane."},
        "cap.circuits": {"place": "present", "note": f"At the chromosome, which lies in a region of the cytoplasm that no membrane surrounds: there is no nucleus. {two_component} of its proteins carry UniProt's keyword for two-component regulatory systems."},
        "cap.grn": {"place": "absent", "why": "It forms no tissue, so there is nothing for gene networks to be coupled across. Gene expression within the one cell belongs with regulatory circuits."},
        "cap.trafficking": {"place": "absent", "why": "It has no endoplasmic reticulum and no Golgi: no entry of its proteome states a place in either. By the names of their entries, its proteins cross or enter the inner membrane through the Sec and Tat translocases."},
        "cap.assembly": {"place": "present", "note": "Its assemblies are its ribosomes, RNA polymerase, the ATP synthase, its flagella and its chemoreceptor arrays. The designed protein cage that Cells models is not one of its proteins."},
        "cap.machines": {"place": "present", "note": f"Its ribosomes, RNA polymerase, the ATP synthase, the protein translocases and the motor of its flagella. {proteasome_said}"},
        "cap.secretion": {"place": "present", "note": "Some of its proteins are stated to be secreted, and porins and transporters carry molecules across its two membranes. Signalling between its own cells was not looked for."},
        "cap.repair": {"place": "present", "note": "The place would be its envelope. No source read for this file describes an injury of it or its resealing in this organism."},
        "cap.division": {"place": "present", "note": "It divides as a single cell: its proteome names the cell division protein FtsZ."},
        "cap.replacement": {"place": "absent", "why": "It forms no tissue, so there is no neighbour for a new cell to replace."},
        "cap.mechanics": {"place": "absent", "why": "It forms no sheet: its cells share no edges to pull on. Its own movement, swimming with flagella, is not what this capability models."},
        "cap.sheet": {"place": "absent", "why": "It lives as single cells and forms no sheet of coupled cells."},
    }
    species = {
        "format": "cells.visualizer.species@1",
        "id": SPECIES_ID,
        "label": LABEL,
        "organism": ORGANISM,
        "taxon": TAXON,
        "plain": f"A rod-shaped bacterium of the animal gut: {len(entries):,} proteins in UniProt's reference proteome of strain K-12, in a cell a few micrometres long with two membranes and a wall between them. It swims with flagella.",
        "group": "Bacteria",
        "order": 50,
        "default": False,
        "made": made,
        "modelled": {"state": "proposed", "text": "The project's record adds it as a data-only organism, for a proposed track whose first stage is bacterial chemotaxis in a well-mixed cell; the track is on hold (decision D179, 15 November 2026). Nothing of it is in the engine: no organism definition, no model and no run."},
        "levels": [
            {"id": "molecules"},
            {"id": "cell", "label": "One cell", "shape": {"kind": "capsule", "length_um": 2.5, "across_um": 1}, "note": f"Drawn as a rod 2.5 µm long and 1 µm across: the picture's choice, within the ranges given for the cell. Its second membrane and its wall are drawn as clear shells around the cell membrane, and its {RIBOSOMES_DRAWN:,} ribosomes are the low end of the range one paper gives. The real cell also carries flagella and fimbriae on its surface, which this shape cannot show.", "sources": ["volkmer2011", "urich2008", "uniprot"]},
        ],
        "no_further_levels": "A single-celled organism: each cell lives on its own, so there is no tissue, organ or body.",
        "cell": {
            "facts": [
                {"label": "Shape and size", "value": "a straight rod; earlier work put its average length between 1.6 and 3.1 µm and its width at 0.7 to 1.1 µm, and one study measured 1.6 µm (cells at rest) to 3.9 µm (cells growing on a rich medium) in length and 1.26 µm in width", "sources": ["volkmer2011", "uniprot"]},
                {"label": "Volume", "value": "1.5 to 4.4 femtolitres, by the conditions it grows in", "sources": ["volkmer2011"]},
                {"label": "Envelope", "value": "two membranes: the inner one separates the cytoplasm from the periplasm, the outer one the periplasm from the cell's surroundings; the cell wall lies between them", "sources": ["uniprot"]},
                {"label": "Inside", "value": "a bacterium, with no nucleus: its chromosome lies in a region of the cytoplasm that no membrane surrounds", "sources": ["uniprot"]},
                {"label": "Chromosome", "value": f"one circle of {genome_length:,} base pairs", "sources": ["genbank"]},
                {"label": "Proteins", "value": f"{len(entries):,} in UniProt's reference proteome of strain K-12, every one with a reviewed entry", "sources": ["uniprot"]},
                {"label": "Ribosomes", "value": "between 6,800 and 72,000 in a cell, depending on its phase of growth, as one open paper sums up earlier estimates", "sources": ["urich2008"]},
                {"label": "Movement", "value": "swims with flagella that grow all over its surface, or does not move", "sources": ["uniprot"]},
                {"label": "Chemotaxis", "value": f"{len(chemotaxis)} of its proteins carry UniProt's keyword for chemotaxis ({listed(by_gene(chemotaxis))}), and {len(complexes_said['flagellum'])} are parts of the flagellum by the Gene Ontology terms UniProt gives them", "sources": ["uniprot"]},
                {"label": "Energy", "value": "respiration and fermentation: it lives with or without oxygen", "sources": ["uniprot"]},
                {"label": "Where it lives", "value": "the lower gut of animals; it survives when released to the natural environment", "sources": ["uniprot"]},
                {"label": "Ion channels", "value": f"none of the animal families Cells has laws for; {len(channels)} proteins of bacterial channel families ({listed(by_gene(channels))})", "sources": ["uniprot"]},
                {"label": "Signalling", "value": f"{two_component} proteins carry UniProt's keyword for two-component regulatory systems", "sources": ["uniprot"]},
                {"label": "Strain", "value": f"K-12; the genome record is of its substrain MG1655, and UniProt's proteome is of the same genome assembly ({proteome['genomeAssembly']['assemblyId']})", "sources": ["genbank", "uniprot"]},
            ],
            "parts": {"membranes": 2, "wall": True, "nucleus": False, "chromosome_kbp": round(genome_length / 1000), "ribosomes": RIBOSOMES_DRAWN},
            "capabilities": capabilities,
        },
        "capability_sources": {key_: ["uniprot"] for key_ in capabilities if key_ not in ("cap.grn", "cap.replacement", "cap.mechanics", "cap.sheet", "cap.repair", "cap.junctions")} | {"cap.junctions": ["uniprot"]},
        "sources": species_sources,
    }
    species_text = json.dumps(species, indent=1, ensure_ascii=False) + "\n"

    # --- the atlas file -----------------------------------------------------------------------
    findings = Counter(unit["finding"] for unit in units.values())
    atlas = {
        "format": "cells.visualizer.species_atlas@1",
        "species": {"id": SPECIES_ID, "label": LABEL, "organism": ORGANISM, "taxon": TAXON, "plain": f"A rod-shaped bacterium of the animal gut with {len(entries):,} proteins in UniProt's reference proteome of strain K-12. The units of the law inventory are machines of animal cells; this is what the same families' signatures find in it."},
        "made": made,
        "method": [
            f"The organism's proteins are the {len(entries):,} reviewed entries of UniProt's reference proteome {PROTEOME} (release {release}), one protein each.",
            "Licences were read before anything was copied; each is stated in sources.",
            "A unit counts as found only where a protein carries the signature of a family that makes the machine itself (the subunit that forms the channel, or the pump's own chain). A protein that carries only the signature of a family that goes with the machine (a regulator, an accessory subunit) is no candidate: the unit's note names it, and it is listed under extra. This reading is the file's own.",
            "Each unit's family was taken from its own human candidates, by the same InterPro signatures that the planarian, Syn3A and M. pneumoniae atlases ask. The build checks that the candidates carry them.",
            f"Each signature was looked for among the InterPro entries UniProt gives each of the {len(entries):,} proteins. No unit's own family was found; {plural(len(beside), 'protein carries', 'proteins carry')} the signature of an accessory family alone.",
            "A control for every signature: how many reviewed UniProtKB entries of all bacteria carry it; each unit's note gives what came back.",
f"{len(M.BACTERIAL_CHANNELS)} further signatures, of the channels a bacterium could have (potassium, chloride, magnesium, water and membrane-stretch channels), were looked for as well; the {len(channels)} proteins that carry them are listed under extra ({channels_said}), with the cell's P-type ATPases and the catalytic head of its ATP synthase.",
            "No similarity search was run, and nothing is called an ortholog.",
        ],
        "sources": [
            {"name": "UniProt", "url": "https://www.uniprot.org/", "release": release, "accessed": d.day(KB, PLACES_FILE), "licence": "CC BY 4.0", "class": "permissive", "cite": cite_uniprot, "holds": "the reviewed entries of the organism's proteins, with the InterPro entries UniProt gives each; the signatures of the units' human candidates; the control counts"},
            {"name": "InterPro", "url": "https://www.ebi.ac.uk/interpro/", "release": filing.release, "accessed": d.day(IPR, "entry.list"), "licence": "CC0 1.0", "class": "permissive", "cite": cite_interpro, "holds": "the identifiers and names of the family signatures"},
        ],
        "not_copied": "No sequence is copied. Nothing is taken from the organism's own curated databases: EcoCyc's data files need a paid subscription, and STEPdb states no terms of use. Both are named in the note as places to read.",
        "units": units,
        "extra": extra,
    }
    atlas_text = json.dumps(atlas, indent=1, ensure_ascii=False) + "\n"

    report = {
        "release": release, "interpro": filing.release, "ontology": filing.ontology, "made": made, "stated": stated, "read": dict(read),
        "shelf_counts": shelf_counts, "counts": counts, "bases": {f"{side} / {basis}": count for (side, basis), count in sorted(bases.items())}, "rules": {rule: rules[rule] for rule, _, _ in H.RULES_USED},
        "evidence": dict(evidence), "between": between, "resting": resting, "rule_ids": rule_ids,
        "families": len(family_total), "in_families": len(filing.family), "several": filing.several, "no_family": len(filing.part),
        "family_sizes": {"one": sum(1 for size in family_total.values() if size == 1), "two to four": sum(1 for size in family_total.values() if 2 <= size <= 4), "five or more": sum(1 for size in family_total.values() if size >= 5)},
        "largest_families": [[filing.names[family]["name"], count] for family, count in sorted(family_total.items(), key=lambda item: (-item[1], item[0]))[:10]],
        "family_ids": sorted(family_total), "lines": len(lines), "distinct": distinct, "lone": lone["count"], "lone_families": lone_families, "lone_parts": len(alone), "part_lines": len(rest),
        "groups": groups, "member_files": files, "places_used": len(used), "place_rows": place_rows,
        "chemotaxis": {gene(a): [key(placed[a]["shelf"]), placed[a]["side"], placed[a]["basis"], complex_of.get(a, "")] for a in sorted(chemotaxis, key=lambda a: gene(a).lower())},
        "complexes": {word: {gene(a): [key(placed[a]["shelf"]), placed[a]["side"]] for a in sorted((a for a, found in complex_of.items() if found == word), key=lambda a: H.natural(gene(a).lower()))} for word, _, _ in COMPLEXES},
        "findings": dict(findings), "found_units": {unit: [product["gene"] for product in found["products"]] for unit, found in units.items() if found["products"]}, "extra": [item["gene"] for item in extra],
        "channels": channel_hits, "p_type": own["p_type"], "proteasome": by_gene(proteasome), "control": control, "genome_length": genome_length,
        "moved": {"proteins": by_gene(moved), "behind": dict(moved_behind), "lipid_anchors_first_stated_at": dict(anchored), "cell_membrane_on_inner": plain_words, "membrane_not_named": unnamed},
        "beside": {gene(accession): [family["of"], asked_by] for accession, (family, asked_by) in beside.items()}, "highlights": len(highlight_rows),
        "pointers": pointers, "two_component": two_component, "isoforms": {gene(a): entry["isoforms"] for a, entry in entries.items() if entry["isoforms"] > 1},
        "per_protein": {protein: [key(placed[protein]["shelf"]), placed[protein]["side"], placed[protein]["basis"], placed[protein]["rule"]] for protein in sequence},
    }
    files_out = {"shelves": body, "table": table, "species": species_text, "atlas": atlas_text}
    files_out["readme"] = build_readme(report, header, tail, closing, lone, no_family)
    for name, text in files_out.items():
        if PATHS.search(text):
            raise SystemExit(f"the {name} would hold a machine path")
    size = {name: len(text.encode("utf-8")) for name, text in files_out.items()}
    if size["shelves"] >= H.LIMIT_SHELVES or max(size.values()) >= H.LIMIT_FILE:
        raise SystemExit(f"the files have outgrown their limits: {size}")
    report["sizes"] = size
    return files_out, report


# The whole note of a unit for which the inventory names no natural gene product.
NOTHING = {
    "U18": lambda own, hits: "The inventory gives this unit no gene product: it is a default shape of current, not a named channel." + (f" This organism has a protein with the potassium channel domain ({listed(hits['IPR013099'])}), listed under extra." if hits.get("IPR013099") else ""),
    "U34": lambda own, hits: "A background conductance that the inventory ties to no protein.",
    "U35": lambda own, hits: "A lumped permeability of the whole membrane, not a population of proteins.",
    "U46": lambda own, hits: "A slot that each model configuration fills with a transporter of its own; it has no fixed protein in any species. This organism's own transporters are in its protein catalogue.",
    "U48": lambda own, hits: "A protein cage designed in the laboratory, with no gene in any organism, so there is nothing to look for in this one.",
    "U49": lambda own, hits: "A lumped water permeability of the membrane; water channels (aquaporins) are not part of it." + (f" {plural(len(hits['IPR000425']), 'protein')} of this organism carr{'ies' if len(hits['IPR000425']) == 1 else 'y'} the aquaporin family's signature ({listed(hits['IPR000425'])}), listed under extra." if hits.get("IPR000425") else ""),
}


def build_readme(report, header, tail, closing, lone, no_family):
    r = report
    sides = lambda found: ", ".join(f"{count:,} {side}" for side, count in found.items() if count)
    lines = [
        "# Escherichia coli K-12: its own proteins, on shelves",
        "",
        "Generated by `tools/build_ecoli_atlas.py`; do not edit by hand. The note is `docs/ECOLI.md`.",
        "",
        "## What is here",
        "",
        f"- `shelves.json`: {header['from']} Each stands against one of the cell's two membranes, outside it, in it or inside it, in the format of `schema/SPECIES_PROTEINS.md` (a curated proteome on several shelves).",
        f"- `proteins.tsv`: one line for each of the {r['stated']['reviewed']:,} proteins, in the order of the shelves' lines. No sequences.",
        "- The files of the families' members are not kept here: `python3 tools/build_ecoli_atlas.py members --out DIR` cuts them from these two files, and the page builder does so when it needs them.",
        "",
        "Nothing of this organism is in the engine. It is reference data for the viewer.",
        "",
        "## Shelves",
        "",
        "| Shelf | Proteins | Outside | In | Inside | Side not known |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    names = {shelf["id"]: shelf["label"] for shelf in header["shelves"]}
    for name, found in r["shelf_counts"].items():
        lines.append(f"| {names.get(name, 'On no shelf')} | {sum(found.values()):,} | {found['outside']:,} | {found['in']:,} | {found['inside']:,} | {found['not known']:,} |")
    lines += [
        "",
        f"- **The space between the two membranes.** {header['between']['rule']} Counted: " + "; ".join(f"{what}: {count:,}" for what, count in header["between"]["counts"].items()) + ".",
        *[f"- **{shelf['label']}.** {shelf['note']}" for shelf in header["shelves"]],
        "- **How each side is known:** " + "; ".join(f"{label}: {count:,}" for label, count in r["bases"].items()) + ".",
        "- **Rules, in the order they are tried:** " + "; ".join(f"{item['rule']} ({item['basis']}): {item['proteins']:,}" for item in tail["placed_by"]) + ".",
        f"- **Half the proteome states no place.** {r['stated']['with_place']:,} entries state one; the others stand on no shelf unless a signal peptide says they left the cytoplasm.",
        "",
        "## Families and districts",
        "",
        f"- {r['families']:,} InterPro families hold {r['in_families']:,} proteins: {r['family_sizes']['one']:,} of one, {r['family_sizes']['two to four']:,} of two to four, {r['family_sizes']['five or more']:,} of five or more. {r['no_family']:,} proteins have no family.",
        f"- {r['lines']:,} lines of {r['distinct']:,} families (a line for each shelf a family has members on); the {r['lone']:,} proteins that are the only member of their family stand in {r['lone_parts']} parts; the proteins with no family in {r['part_lines']} lines.",
        "- The largest families: " + "; ".join(f"{name} ({count})" for name, count in r["largest_families"][:8]) + ".",
        "- Districts: " + "; ".join(f"{group['label']} ({group['proteins'] + group['lone']:,})" for group in r["groups"]) + ".",
        "",
        "## Chemotaxis and the assemblies",
        "",
        f"- **`chemotaxis`** ({len(r['chemotaxis'])} proteins, by UniProt's keyword): " + "; ".join(f"{name} ({found[0]}, {found[1]})" for name, found in r["chemotaxis"].items()) + ".",
    ]
    for word, found in r["complexes"].items():
        lines.append(f"- **`complex`: {word}** ({len(found)}): " + ", ".join(f"{name} ({place[0]}, {place[1]})" for name, place in found.items()) + ".")
    lines.append(f"- The page offers a mark to show by only where a species has one marker for each protein. Here the proteins stand in families, so each member carries its marks, and `shelves.json` lists under `highlights` every protein that carries one with the line it stands on ({r['highlights']} lines).")
    lines += [
        "",
        "## What rests on tools whose own terms are not permissive",
        "",
        "By the project's rule (the user, 15 November 2026), a value stands on the terms of the database it was read from, here UniProt's, and the tool behind it is named and counted. It is the project's rule, not a legal opinion. Nothing was downloaded from any of these tools, and none was run.",
        "",
        "| Tool or rule system | Its terms | Class | What rests on it |",
        "| --- | --- | --- | --- |",
    ]
    for source in closing["sources"]:
        if source.get("through"):
            lines.append(f"| {source['name']} | {source['licence']} | {source['class']} | {source['holds']} |")
    lines += [
        "",
        "## Sources",
        "",
    ]
    for source in closing["sources"]:
        if not source.get("through") and source["class"] == "permissive":
            lines.append(f"- **{source['name']}** ({source['licence']}; read {source['accessed']}): {source['holds']}.")
    lines += ["", "Read for their terms and pointed to; nothing is taken from them:", ""]
    for source in r["pointers"]:
        lines.append(f"- **[{source['name']}]({source['url']})** ({source['licence']}; read {source['accessed']}). {source['holds']}")
    lines += [
        "",
        "## To rebuild",
        "",
        "```",
        "python3 tools/build_ecoli_atlas.py fetch --datasets DATA   # the only step that uses the network",
        "python3 tools/build_ecoli_atlas.py build --datasets DATA   # the same bytes every time",
        "```",
        "",
        "DATA is the folder that holds every species' downloads, one folder per source with a MANIFEST.",
        "",
    ]
    return "\n".join(lines)


def cut_members(folder):
    """The members' files, cut from the two files of the repository as shelves.json says."""
    folder = Path(folder)
    shelves = json.loads((folder / H.SHELVES_FILE).read_text(encoding="utf-8"))
    with open(folder / H.TABLE_FILE, encoding="utf-8") as handle:
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
            raise SystemExit(f"the members of {line['id']} on {line['shelf']} are not where {H.SHELVES_FILE} says they are")
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
            if row["locus"]:
                marks["locus"] = row["locus"]
            if row["chemotaxis"]:
                marks["chemotaxis"] = True
            if row["complex"]:
                marks["complex"] = row["complex"]
            files[line["file"]].append([row["id"], row["name"], row["gene"], row["side"], letters["basis"][row["basis"]], int(row["length"]), row["units"].split(";") if row["units"] else None, marks])
    if cursor != len(table):
        raise SystemExit(f"the table holds {len(table)} proteins and the lines {cursor}")
    out = {}
    for file in sorted(files):
        head = {"format": H.MEMBERS_FORMAT, "species": shelves["species"], "file": file, "columns": shelves["member_columns"]}
        out[file] = json.dumps(head, indent=1, ensure_ascii=False)[:-2] + ',\n "members": [\n' + ",\n".join("  " + H.compact(member) for member in files[file]) + "\n ]\n}\n"
        json.loads(out[file])
    return out


def summary(report):
    r = report
    return "\n".join([
        f"UniProt {r['release']}, InterPro {r['interpro']}, Gene Ontology {r['ontology']}; made {r['made']}",
        f"in: {r['stated']['reviewed']:,} reviewed entries; unreviewed: {r['stated']['unreviewed']:,}; genes {r['stated']['genes']:,}; {r['stated']['with_place']:,} state a place; read: {r['read']}",
        "by shelf: " + "; ".join(f"{shelf} {sum(sides.values()):,} {sides}" for shelf, sides in r["shelf_counts"].items()),
        f"sides: {r['counts']}; side and basis: {r['bases']}",
        f"rules: {r['rules']}",
        f"between the membranes: {r['between']}",
        f"evidence behind the deciding statement: {r['evidence']}",
        f"families: {r['families']:,} holding {r['in_families']:,} proteins (sizes {r['family_sizes']}); no family {r['no_family']:,}; lines {r['lines']:,} of {r['distinct']:,}; lone {r['lone']:,} in {r['lone_parts']} parts; part lines {r['part_lines']}",
        f"largest: {r['largest_families'][:6]}",
        "districts: " + "; ".join(f"{group['id']} {group['lines']:,} lines, {group['proteins']:,} proteins, {group['lone']:,} lone" for group in r["groups"]),
        f"rests on a rule system or a program, by owner: {r['resting']}",
        f"chemotaxis: {r['chemotaxis']}",
        "assemblies: " + "; ".join(f"{word} {len(found)}" for word, found in r["complexes"].items()),
        f"atlas: {r['findings']}; found {r['found_units']}; accessory only {r['beside']}; extra {r['extra']}",
        f"lipid anchors at 'Cell membrane' moved to the unnamed membrane: {len(r['moved']['proteins'])} {r['moved']['behind']}; first stated at {r['moved']['lipid_anchors_first_stated_at']}; 'Cell membrane' on inner {r['moved']['cell_membrane_on_inner']}; membrane not named {r['moved']['membrane_not_named']}",
        f"channels: {r['channels']}; P-type: {r['p_type']}; proteasome signature: {r['proteasome']}",
        f"member files: {r['member_files']}; places used: {r['places_used']}; sizes: {r['sizes']}",
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("step", choices=["fetch", "build", "members"])
    parser.add_argument("--datasets", help="fetch, build: the folder that holds every species' downloads, one folder per source with a MANIFEST.json (kept outside the repository)")
    parser.add_argument("--refresh", action="store_true", help="fetch: ask again even where an answer is saved")
    parser.add_argument("--out-dir", default=str(OUT_DIR), help="build: the folder for shelves.json, the table and their README.md; members: the folder that holds them")
    parser.add_argument("--out-species", default=str(SPECIES_FILE), help="build: where the species file is written")
    parser.add_argument("--out-atlas", default=str(ATLAS_FILE), help="build: where the atlas file is written")
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
    files, report = build(Path(args.datasets), snapshot)
    folder = Path(args.out_dir)
    folder.mkdir(parents=True, exist_ok=True)
    targets = [(folder / H.SHELVES_FILE, "shelves"), (folder / H.TABLE_FILE, "table"), (folder / "README.md", "readme"), (Path(args.out_species), "species"), (Path(args.out_atlas), "atlas")]
    for target, name in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(files[name], encoding="utf-8")
        print(f"wrote {target.name} ({len(files[name].encode('utf-8')):,} bytes)")
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(summary(report))


if __name__ == "__main__":
    main()
