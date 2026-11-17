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

The table that says which shelf and side a stated place stands for is an animal cell's, in
tools/lib/proteome_shelves.py with the rest of the machinery that the species' tools share:
this file holds the human's sources, terms, checks and notes. Every protein is shown: a family has a line for each shelf that holds members of
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
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from lib.proteome_shelves import (  # noqa: E402  the machinery that every species' tool shares
    ANIMAL_CELL, BASIS_LETTER, CITE_INTERPRO, CITE_UNIPROT, CLIENT, ELSEWHERE, EVIDENCE, EVIDENCE_LETTER, FAMILY_COLUMNS, FOUR_SEGMENTS,
    FOUR_SIGNALS, FROM_SEGMENTS, FROM_SIGNAL, KINDS, LONE_UP_TO, MEMBER_COLUMNS, MEMBERS_FORMAT, MEMBERS_PER_FILE, NO_SHELF, NOT_GIVEN,
    NOT_RUN, ON_FACE, ON_PLACE, ON_SPANS, PART_COLUMNS, PART_KIND, PLACE_COLUMNS, PREDICTORS, RULES_USED, SAVED_TERMS, SEEN, SHELF_FORMAT,
    SHELVES_FILE, SIDES, TABLE_COLUMNS, TABLE_FILE, Datasets, Filing, Vocabulary, account, by_basis, by_evidence, compact, counted, digest,
    district_rows, holds, in_order, letters, lone_block, make_lines, natural, no_family_block, ontology_citation, ordered_sides, place,
    place_rows, plain, q, read_manifest, read_reviewed, rows_size, shelf_rows, shelves_text, table_text, through_uniprot, utc_now,
    whole_gzip, within_limits, write_members,
)

SNAPSHOT = ROOT / "data" / "proteins" / "inventory.snapshot.json"
OUT_DIR = ROOT / "data" / "proteins" / "human"
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
# schema/SPECIES_PROTEINS.md, "A curated proteome", fixes the shelves and the rules. The
# human's are an animal cell's six shelves, with the table that applies the rules to UniProt's
# vocabulary of subcellular locations (subcell.txt): ANIMAL_CELL in tools/lib/proteome_shelves.py,
# which the fruit fly's tool uses as it is and the thale cress's extends.

CELL = ANIMAL_CELL
SHELF_IDS, PLACES = CELL.ids, CELL.places


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
# once, by the tools of the other species (SAVED_TERMS). This tool fetches none of them again:
# the build reads those copies through their MANIFESTs, in the folder that holds every
# species' downloads.
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


def is_ours(manifest):
    return manifest is not None and MINE in manifest.get("note", "")


def fetch(datasets, refresh=False, pause=2.0, tries=6):
    """Ask every request whose file is not yet in its dataset folder; save the body as it
    came and describe it in the folder's MANIFEST. A folder another agent made is read and
    never written.

    The human's own downloader, stricter than the one the other species' tools share
    (proteome_shelves.fetch): it writes into no folder this tool did not make, even one
    with no MANIFEST, looks again for a MANIFEST another agent may have just written, and
    keeps each answer's Last-Modified."""
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

def check_terms(d, shared):
    """Each source's terms, read in its own saved page before anything of it is used.
    Returns the sentences the files quote."""
    said = {}

    def must(key, source, file, pattern, field=None):
        # A page another species' tool saved (file None) is read in the folder of every species' downloads.
        said[key] = holds(shared, *SAVED_TERMS[source], pattern, field) if file is None else holds(d, source, file, pattern, field)

    must("uniprot", KB_DOCS, "terms_uniprot_license.json", r"We have chosen to apply the \[?Creative Commons Attribution 4\.0 International \(CC BY 4\.0\) License\]?(\([^)]*\))? to all copyrightable parts of our databases", field="content")
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
    must("rulebase", "unirule", None, r"RuleBase rules", field="content")
    must("big_pi", BIG_PI, "gpi_server.html", r"big-PI Predictor")
    if re.search(r"(?i)licen[cs]e|terms of use|copyright|commercial", plain(d.text(BIG_PI, "gpi_server.html"))):
        raise SystemExit("the big-PI predictor's page now speaks of terms; read them and class it again")
    must("big_pi_named", KB_DOCS, "help_lipid.json", r"sites predicted by the 'big-Pi' predictor", field="content")
    must("two_agree", KB_DOCS, "help_transmem.json", r"at least two methods must return a positive prediction", field="content")
    # What UniProt's own pages say of the features the two feature rules read.
    must("segments", KB_DOCS, "help_transmem.json", r"predicted by the application of the predictive tools TMHMM, Memsat, Phobius and the hydrophobic moment plot method of Eisenberg and coworkers", field="content")
    must("signals", KB_DOCS, "help_signal.json", r"predicted by the application of the predictive tools Phobius, Predotar, SignalP and TargetP\. At least two methods must return a positive signal peptide prediction", field="content")
    must("signal_fate", KB_DOCS, "help_signal.json", r"Signal peptides are found in proteins that are targeted to the endoplasmic reticulum and eventually destined to be either secreted/extracellular/periplasmic/etc\., retained in the lumen of the endoplasmic reticulum, of the lysosome or of any other organelle along the secretory pathway", field="content")
    must("anchor", KB_DOCS, "help_lipid.json", r"the addition of a GPI-anchor may serve to anchor extracellular proteins to the outer face of the plasma membrane", field="content")
    must("anchor_lumen", KB_DOCS, "help_lipid.json", r"GPI-anchor addition takes place in the lumen of the endoplasmic reticulum", field="content")
    must("no_evidence", KB_DOCS, "help_transmem.json", r"The annotations which are missing evidence were created before we started to manually curate information with evidence", field="content")
    return said


# ---------------------------------------------------------------------------------------
# Build: the three files
# ---------------------------------------------------------------------------------------

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


# The inventory's roles, in its own words, that name a part going with a unit's machine rather than the part that
# does its work: an auxiliary subunit ("... auxiliary family; ..."), the sodium pump's beta subunits ("beta"), the
# uniplex's regulators ("uniplex") and the pump's FXYD regulators ("FXYD", "FXYD (gamma)"). An entry is drawn as
# going with the machine where every role the inventory gives it is one of these (16 November 2026; the 27 entries
# the shared table of accessory signatures also names).
GOES_WITH_ROLES = {"beta", "uniplex", "FXYD", "FXYD (gamma)"}
ROLES_NOTE = (
    "The human has no species atlas: a protein's unit is the inventory's own naming of its human entry. Where every role "
    "the inventory gives the entry names a part that goes with the machine (an auxiliary subunit, the sodium pump's beta "
    "subunits, the uniplex's regulators, the pump's FXYD regulators), the entry is listed here with its roles, in the "
    "inventory's words: it is drawn plain, not in the unit's shape, and is no candidate for the machine's own work. "
    "'families' names the families every one of whose proteins with a unit is listed so."
)


def goes_with(role):
    """Whether one of the inventory's roles names a part that goes with the machine (GOES_WITH_ROLES)."""
    return "auxiliary" in role or role in GOES_WITH_ROLES


def roles_block(units, roles, lines):
    """shelves.json's 'inventory_roles': the entries whose every role goes with the machine, and the families of only such."""
    going = {accession: sorted(roles[accession]) for accession in units if roles[accession] and all(goes_with(role) for role in roles[accession])}
    families = defaultdict(list)
    for line in lines:
        families[line["id"]].extend(line["proteins"])
    whole = sorted((family for family, members in families.items() if any(member in units for member in members) and all(member in going for member in members if member in units)), key=natural)
    return {"note": ROLES_NOTE, "proteins": {accession: going[accession] for accession in sorted(going, key=natural)}, "families": whole}


def build(datasets_folder, snapshot, terms_folder=None):
    d = Datasets(datasets_folder)
    # The terms that the other species' tools saved: in the folder that holds every species' downloads.
    shared = Datasets(terms_folder or Path(datasets_folder).resolve().parent)
    said = check_terms(d, shared)
    vocabulary = Vocabulary(d, KB_DOCS, CELL)
    entries, read = read_reviewed(d, KB, PLACES_FILE, vocabulary)
    filing = Filing(d, entries, KB, SIGNATURES_FILE, IPR, GO)
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

    lines, alone, rest = make_lines(entries, placed, filing, units, CELL)
    sequence = in_order(entries, lines, alone, rest)

    # --- counts ---------------------------------------------------------------------------
    key = lambda shelf: NO_SHELF if shelf is None else shelf
    shelf_counts, counts, bases, rules, evidence = counted(placed, CELL)
    family_total = Counter(filing.family.values())
    distinct = len({line["id"] for line in lines})
    lone_families = sum(1 for count in family_total.values() if count <= LONE_UP_TO)
    shelves, no_shelf = shelf_rows(CELL, shelf_counts, lines, alone, rest)
    groups = district_rows(lines, alone)

    # --- the places the entries state first, with the table's line for each ------------------
    places, place_words, first_places, used = place_rows(entries, placed, vocabulary)

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
    PLACE, SPANS, FACE = ON_PLACE, ON_SPANS, ON_FACE
    most = lambda owner: ", ".join(f"{rule} for {count:,}" for rule, count in list(rule_ids.get(owner, {}).items())[:3])

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
    lone = lone_block(alone, lone_families)
    no_family = no_family_block(filing, placed)
    files = sorted({line["file"] for line in [*lines, *alone, *rest]})
    tail = {
        "member_columns": MEMBER_COLUMNS,
        "members_from": {
            "table": f"data/proteins/human/{TABLE_FILE}",
            "format": MEMBERS_FORMAT,
            "order": f"The table's lines are the members in order: every line of the families as listed here, then every part of 'lone', then every part of 'no_family'; within each, by gene name. A line's members are the next 'count' lines of the table. For a family's line and for a part of no_family, 'under' is its id and 'shelf' its shelf (empty for none); for a part of 'lone', 'under' is the protein's own family and 'family' that family's name.",
            "files": f"A file holds the members of consecutive lines: a new file begins where the next line would take it past {MEMBERS_PER_FILE:,} members, so a line is never split, and one larger than that has a file of its own. 'file' names the file and 'at' the first and one past the last of its members there. A member's shelf is its line's.",
            "places": "In the table a stated place is written with UniProt's identifiers, without their prefix: the place, then the topology and the face where the entry states them, joined by a full stop (0039.9909 is SL-0039 with SL-9909). 'place_words' gives the words of each.",
            "letters": letters(),
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
                f"UniProt's curators annotate these features from experiments, from likeness to other proteins and from prediction; its own pages name the predictors: {PREDICTORS}. Each is named among the sources, with its terms and what rests on it: TMHMM, SignalP, TargetP and Phobius are given out for academic use. "
                "A segment is used only where one membrane is meant: not in the mitochondrion, whose two membranes are on different shelves, nor in a region of the cell that holds other membranes."
            ),
            "none": (
                "The entry states a membrane or a compartment and not the side (the protein then stands apart beside that shelf, with the place in its mark 'where'), or it states no place of the cell and carries no membrane-spanning segment and no signal peptide (the protein is then on no shelf). Nothing is placed by guess."
            ),
        },
        "placed_by": [{"rule": rule, "basis": basis, "what": what, "proteins": rules[rule]} for rule, basis, what in RULES_USED],
        "place_kinds": KINDS,
        "place_columns": PLACE_COLUMNS,
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
    closing = {
        "inventory_roles": roles_block(units, roles, lines),
        "marks": marks,
        "counts": counts,
        "shelf_counts": shelf_counts,
        "by_basis": by_basis(bases),
        "by_evidence": by_evidence(evidence),
        "sources": None,  # set below
    }
    made = max(d.last_day(), shared.last_day())
    header["made"] = made
    closing["sources"] = [
        {
            "name": "UniProt", "url": "https://www.uniprot.org/", "release": release, "accessed": d.day(KB, PLACES_FILE), "licence": "CC BY 4.0", "class": "permissive", "cite": CITE_UNIPROT,
            "holds": f"for each reviewed entry of the human reference proteome: its name, gene, length and level of evidence, the places it states with the evidence for each, its membrane-spanning segments and signal peptide, the isoforms it describes, the InterPro entries and the Gene Ontology terms UniProt gives it; and UniProt's vocabulary of places. Its own pages name the programs behind the segments and signal peptides it predicts ({PREDICTORS}); each is a source below, with what rests on it. Of UniProt's own: {of('RuleBase'):,} statements that a protein spans a membrane rest on a rule of its rule base (RuleBase), and {of('unnamed analysis'):,} stated places rest on a sequence analysis in entries that carry no segment or signal peptide of that kind, for which it names no program",
        },
        {
            "name": "InterPro", "url": "https://www.ebi.ac.uk/interpro/", "release": filing.release, "accessed": d.day(IPR, "entry.list"), "licence": "CC0 1.0", "class": "permissive", "cite": CITE_INTERPRO,
            "holds": "the type and name of each entry, the tree of broader and narrower entries, and the mapping of entries to Gene Ontology terms",
        },
        {
            "name": "Gene Ontology", "url": "https://geneontology.org/", "release": filing.ontology, "accessed": d.day(GO, "go-basic.obo"), "licence": "CC BY 4.0", "class": "permissive", "cite": ontology_citation(d, GO),
            "holds": "the names of terms and which term is a kind or a part of which; no term's text is copied beyond the names of the districts' terms",
        },
        # The rule systems and the programs behind what UniProt's entries state by rule or by
        # sequence analysis: each a source of its own, with its terms as its own page states
        # them, read through UniProt, and with what rests on it here.
        through_uniprot("PROSITE", shared.day(*SAVED_TERMS["prosite"]), f"Nothing was downloaded from it but its statement of terms, and nothing of it is copied. Its rules (ProRule) are named in UniProt's entries as what stands behind a statement. {of('PROSITE-ProRule'):,} placements rest on them alone: {of('PROSITE-ProRule', PLACE):,} by the statement of place that decides the shelf ({len(rule_ids.get('PROSITE-ProRule', {})):,} rules; most often {most('PROSITE-ProRule')}), {of('PROSITE-ProRule', SPANS):,} by the statement that the protein spans the membrane, and {of('PROSITE-ProRule', FROM_SEGMENTS):,} by a side read here from segments that a rule gives. They were read in UniProt's entries."),
        through_uniprot("HAMAP", shared.day(*SAVED_TERMS["hamap"]), f"Nothing was downloaded from it but its statement of terms. Its family rules are named in UniProt's entries as what stands behind a statement. {of('HAMAP-Rule'):,} placements rest on them alone: {of('HAMAP-Rule', PLACE):,} by the statement of place that decides the shelf ({len(rule_ids.get('HAMAP-Rule', {})):,} rules), {of('HAMAP-Rule', SPANS):,} by the statement that the protein spans the membrane, {of('HAMAP-Rule', FACE):,} by the stated face, and {of('HAMAP-Rule', FROM_SEGMENTS):,} by a side read here from segments that a rule gives."),
        through_uniprot("TMHMM", shared.day(*SAVED_TERMS["tmhmm"]), f"{NOT_RUN} {FOUR_SEGMENTS}. {of('segments'):,} placements rest on segments that an entry gives by sequence analysis alone: {of('segments', FROM_SEGMENTS):,} are read here from such segments (basis predicted; {rules['segment'] + rules['no place: segment']:,} are read from segments in all), and behind a curator's statement {of('segments', SPANS):,} are said to span the membrane on a sequence analysis and {of('segments', PLACE):,} have a stated place that rests on a sequence analysis in an entry with such segments."),
        through_uniprot("Phobius", shared.day(*SAVED_TERMS["phobius"]), f"{NOT_RUN} {FOUR_SEGMENTS}; and one of the four it names for signal peptides. The placements are those counted under TMHMM ({of('segments'):,}) and under SignalP ({of('signal'):,})."),
        through_uniprot("SignalP", shared.day(*SAVED_TERMS["signalp"]), f"{NOT_RUN} {FOUR_SIGNALS}. {of('signal'):,} placements rest on a signal peptide that an entry gives by sequence analysis alone: {of('signal', FROM_SIGNAL):,} are read here from such a signal (basis predicted; {rules['signal'] + rules['no place: signal']:,} are read from a signal peptide in all), and behind a curator's statement {of('signal', PLACE):,} have a stated place that rests on a sequence analysis in an entry with such a signal and no such segment."),
        through_uniprot("TargetP", shared.day(*SAVED_TERMS["targetp"]), f"{NOT_RUN} {FOUR_SIGNALS}. The placements are those counted under SignalP ({of('signal'):,})."),
        through_uniprot("Memsat", d.day(KB_DOCS, "help_transmem.json"), f"Nothing was downloaded from it. {FOUR_SEGMENTS}. The placements are those counted under TMHMM ({of('segments'):,})."),
        through_uniprot("Predotar", d.day(KB_DOCS, "help_signal.json"), f"Nothing was downloaded from it. {FOUR_SIGNALS}. The placements are those counted under SignalP ({of('signal'):,})."),
        through_uniprot("big-PI", d.day(BIG_PI, "gpi_server.html"), f"Nothing was downloaded from it but its own page, and the program was not run here. The predictor that UniProt's help names for the GPI anchors it predicts. {of('big-PI'):,} placements rest on a GPI anchor that the entry states on a sequence analysis alone: such an anchor puts the protein on the face away from the cytoplasm."),
    ]
    if [source["name"] for source in closing["sources"] if source.get("through")] != UPSTREAM:
        raise SystemExit("the sources read through UniProt are not the ones this tool names")

    body = shelves_text(header, lines, alone, rest, lone, no_family, tail, places, place_words, closing, len(family_total))

    # --- the table of proteins, in the members' order -----------------------------------------
    table = table_text(TABLE_COLUMNS, sequence, entries, placed, filing, alone, units)

    # --- what the README and the summary say ---------------------------------------------------
    sizes = sorted(family_total.values(), reverse=True)
    line_sizes = sorted((len(line["proteins"]) for line in lines), reverse=True)
    full = make_lines(entries, placed, filing, units, CELL, lone_up_to=0)
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
        "places_used": len(used), "first_places": len(first_places), "place_rows": places,
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
    report["sizes"] = within_limits(files_out, PATHS, folder=True)
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
        write_members(args.out_dir, args.out)
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
