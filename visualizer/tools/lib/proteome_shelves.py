"""What the tools that build a species' own proteins share (schema/SPECIES_PROTEINS.md).

Each species has a tool of its own, tools/build_<species>_atlas.py, which holds what is the
species' own: its sources and their terms, its shelves and its table of places, its rules and
exceptions, its species file and its notes. This module holds the machinery the tools share,
and keeps no state of its own: a function is given what it reads, so several species can be
built in one process, one after the other, in any order. The human's, E. coli's, the fruit
fly's and thale cress's tools use it; the older tools of the planarian, Syn3A and
M. pneumoniae keep machinery of their own, which reads their sources differently.

    reading     the saved downloads, each through its folder's MANIFEST (Datasets); the step
                that saves them (fetch); the pages of terms; the open papers
    placing     UniProt's vocabulary of places, a cell's shelves and its table of places (Cell),
                the two readings of UniProt's entries (a reviewed proteome, a whole one), and
                the rules that put a protein on a shelf and a side from what its entry states
    filing      one family for each protein, and the district its terms put it in (Filing)
    lines       the families' lines, the parts of 'lone' and of 'no_family', and the counts
    writing     shelves.json, proteins.tsv and the members' files
    the atlas   the families of Cells' units, asked of a species' catalogue

The rules are those of the planarian's shelves (tools/build_planarian_atlas.py), so that a
family has the same id in every species. A change here shows in every species' byte-for-byte
test. Standard library only.
"""

from __future__ import annotations

import gzip
import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

CLIENT = "atlas-builder/1.0"  # requests carry a generic client name and nothing about who asks


# ---------------------------------------------------------------------------------------
# Reading: the saved downloads
# ---------------------------------------------------------------------------------------
#
# Downloads are kept the way the project keeps them: one folder per source under a datasets
# folder, each with a MANIFEST.json that gives every file's address, time and SHA-256. The
# build reads a file only through its MANIFEST and checks it against the SHA-256 there.

def q(text):
    return urllib.parse.quote(text, safe="")


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


def whole_gzip(body):
    try:
        gzip.decompress(body)
        return True
    except (OSError, EOFError):
        return False


class Datasets:
    """The downloads, each read through its folder's MANIFEST and checked against it. The
    day of the latest file read so far is the day a build was made from (last_day)."""

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


def fetch(datasets, requests, sources, mine, tool, refresh=False, pause=1.2, tries=6):
    """Ask every request whose file is not yet saved; keep the body as it came and describe it
    in its folder's MANIFEST. A folder another agent made is read and never written.

    requests: dicts of the folder ("source", under datasets), the file, the address, what it is
    for ("purpose"), and optionally "gzip" (the body must be a whole gzip file) and "contains"
    (a text the body must hold). sources: each folder's record for its MANIFEST. mine: the name
    that marks a MANIFEST as written by this tool; tool: the tool's path, named in the MANIFEST."""
    datasets = Path(datasets)
    asked = failed = 0
    for request in requests:
        folder = datasets / request["source"]
        manifest = read_manifest(folder)
        ours = manifest is not None and mine in manifest.get("note", "")
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
            record, body = {"asked": utc_now()}, None
            try:
                with urllib.request.urlopen(call, timeout=1800) as answer:
                    body = answer.read()
                    record["status"] = answer.status
                    for header, key in [("X-Total-Results", "total_results"), ("X-UniProt-Release", "uniprot_release"), ("X-UniProt-Release-Date", "uniprot_release_date"), ("Content-Type", "content_type")]:
                        if answer.headers.get(header):
                            record[key] = answer.headers[header]
                if request.get("gzip") and not whole_gzip(body):
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
        manifest = read_manifest(folder)
        if manifest is None and any(folder.iterdir()):
            print(f"skipped  {request['source']}/{request['file']}: the folder holds files and no MANIFEST of this tool", flush=True)
            failed += 1
            continue
        (folder / request["file"]).write_bytes(body)
        sha, md5 = digest(folder / request["file"])
        entry = {"name": request["file"], "url": request["url"], "role": request["purpose"], "retrieved_utc": record["asked"], "http_status": record["status"], "content_type": record.get("content_type"), "size_bytes": len(body), "sha256": sha, "md5": md5, "expected_size": None, "expected_md5": None, "ok": True, "error": None}
        for key in ("total_results", "uniprot_release", "uniprot_release_date"):
            if record.get(key) is not None:
                entry["x_" + key] = record[key]
        manifest = manifest or {"source_id": request["source"].split("/")[-1], "files": []}
        manifest["record"] = sources[request["source"]]
        manifest["files"] = sorted([item for item in manifest["files"] if item["name"] != entry["name"]] + [entry], key=lambda item: item["name"])
        manifest["manifest_written_utc"] = utc_now()
        manifest["note"] = f"Added by {mine}: downloaded as untrusted data by {tool} of the Cells checkout. Nothing here was executed."
        (folder / "MANIFEST.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"200  {request['source']}/{request['file']}  {len(body)}", flush=True)
        time.sleep(pause)
    print(f"asked {asked} request(s), {failed} failed or missing, under {datasets}")
    return failed


def plain(markup):
    """Markup as running text, for looking up a sentence in a saved page."""
    markup = re.sub(r"(?s)<(script|style)[^>]*>.*?</\1>", " ", markup)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]+>", " ", markup))).strip()


def natural(identifier):
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", identifier)]


def holds(d, source, file, pattern, field=None):
    """The words in which a saved page states its terms, checked before anything of the source
    is used: the build stops if they are gone. A page saved as JSON is read in its field
    `field`, a page of markup as running text."""
    text = d.text(source, file)
    text = json.loads(text)[field] if field else plain(text)
    found = re.search(pattern, text)
    if not found:
        raise SystemExit(f"{source}/{file} no longer states its terms as they were read; read the page again before building")
    return found.group(0)


# The terms of the rule systems and programs behind UniProt's statements were read and saved
# once, by the tools of the older species: (folder, file) under the folder that holds every
# species' downloads. No tool fetches them again; each build reads those copies.
SAVED_TERMS = {
    "prosite": ("syn3a/terms-prosite", "prosite_license.html"),
    "hamap": ("mpneumoniae/terms-upstream-tools", "upstream_hamap_about.html"),
    "tmhmm": ("mpneumoniae/terms-upstream-tools", "upstream_tmhmm_licence.html"),
    "signalp": ("mpneumoniae/terms-upstream-tools", "upstream_signalp_licence.html"),
    "targetp": ("mpneumoniae/terms-upstream-tools", "upstream_targetp_licence.html"),
    "phobius": ("mpneumoniae/terms-upstream-tools", "upstream_phobius_download.html"),
    "unirule": ("planarian/terms-upstream-tools", "uniprot_help_unirule.json"),
}


def human_signatures(d, human_kb):
    """The InterPro entries of each reviewed human entry, from the human's saved table: what the
    units' human candidates carry."""
    lines = d.text(human_kb, "uniprotkb_UP000005640_reviewed_signatures.tsv.gz").splitlines()[1:]
    return {line.split("\t")[0]: set(line.split("\t")[1].split(";")) for line in lines}


# ---------------------------------------------------------------------------------------
# Reading: open papers, each as its record at Europe PMC and its full text
# ---------------------------------------------------------------------------------------
#
# papers: key -> {"pmc", "doi", "holds": the sentences a fact rests on, "text": a citation as
# written (else the record's), ...}; folder: the dataset folder that holds them.

def paper_text(d, folder, papers, key):
    """A paper's running text, with the licence its record gives; the build stops if a sentence a fact rests on is gone."""
    record = json.loads(d.text(folder, f"{key}_record.json"))["resultList"]["result"]
    found = next((item for item in record if item.get("pmcid") == papers[key]["pmc"]), None)
    if found is None or (found.get("license") or "").lower() != "cc by" or (found.get("doi") or "").lower() != papers[key]["doi"].lower():
        raise SystemExit(f"{key}: its record at Europe PMC no longer gives the licence CC BY and the paper's DOI; read it again")
    raw = d.text(folder, f"{key}_fulltext.xml")
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]+>", " ", re.sub(r"(?s)<(table-wrap|ref-list)\b.*?</\1>", " ", raw))))
    text = re.sub(r"\s*\[[\d\s,\[\]]*\]\s*,?", " ", text)  # the numbers of its references
    text = re.sub(r"\s+", " ", text).replace(" ,", ",").replace(" .", ".")
    for pattern in papers[key]["holds"]:
        if not re.search(pattern, text):
            raise SystemExit(f"{key}: the saved text no longer holds what a fact rests on ({pattern})")
    return text


def paper_cite(d, folder, papers, key):
    """A paper's citation: as written in its tool, or as its saved record at Europe PMC gives it."""
    if papers[key].get("text"):
        return papers[key]["text"]
    record = next(item for item in json.loads(d.text(folder, f"{key}_record.json"))["resultList"]["result"] if item.get("pmcid") == papers[key]["pmc"])
    clean = lambda words: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", words or ""))).strip().rstrip(".")
    journal = record.get("journalInfo", {})
    where = " ".join(part for part in (clean(journal.get("journal", {}).get("title")), f"{journal.get('volume')}:{record.get('pageInfo')}" if journal.get("volume") and record.get("pageInfo") else journal.get("volume") or "") if part)
    return f"{clean(record['authorString'])} ({record['pubYear']}) {clean(record['title'])}. {where}."


# ---------------------------------------------------------------------------------------
# Words for the notes
# ---------------------------------------------------------------------------------------

def listed(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1] if items else ""


def plural(count, one, many=None):
    return f"{count:,} {one if count == 1 else many or one + 's'}"


def some(names, most=10):
    names = list(names)
    return listed(names) if len(names) <= most else ", ".join(names[:most]) + f" and {len(names) - most} more"


# ---------------------------------------------------------------------------------------
# Placing: a cell's shelves, and the table of which shelf and side a stated place stands for
# ---------------------------------------------------------------------------------------
#
# schema/SPECIES_PROTEINS.md, "A curated proteome", fixes the shelves and the rules. A cell's
# table applies them to UniProt's own vocabulary of subcellular locations (subcell.txt): every
# term an entry uses is resolved to a line of the table through the vocabulary's own links,
# and the build stops at a term it cannot resolve or that two lines claim.

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
GENERIC = ("Membrane", "Endomembrane system")  # parents that every membrane has: followed last

# The words of a membrane's topology, by UniProt's identifiers.
SPANS = {"SL-9904", "SL-9905", "SL-9906", "SL-9907", "SL-9908", "SL-9909"}  # single-pass (of any type) and multi-pass
ANCHORED = {"SL-9902", "SL-9920"}                                           # GPI-anchor, GPI-like-anchor
NOT_SPANNING = {"SL-9901", "SL-9903"}                                       # lipid-anchor, peripheral membrane protein


class Cell:
    """A cell's shelves and its table of places, as a species' tool gives them.

    shelves: the shelves in order, each {"id", "label", "outside", "inside"}; notes: a note
    for some of them, by id. places: UniProt's term -> (shelf, what the term names); a term
    that is not listed takes the line of the terms it is a kind of, else of the term before it
    in UniProt's own path for it ("Cytoplasm, cytoskeleton, spindle"), else of the terms it is
    a part of, and a term that names a membrane and resolves to a compartment or a region is
    that place's membrane. faces: a stated face -> the side, by shelf. away: the side away from
    the cytoplasm, where an exported protein ends up, by shelf. not_spanning: the topologies
    that hold a protein at a membrane without spanning it."""

    def __init__(self, shelves, places, faces, away, notes=None, not_spanning=NOT_SPANNING):
        self.shelves = shelves
        self.ids = [shelf["id"] for shelf in shelves]
        self.places = places
        self.faces = faces
        self.away = away
        self.notes = notes or {}
        self.not_spanning = set(not_spanning)

    def rank(self, shelf):
        return self.ids.index(shelf) if shelf is not None else len(self.ids)


# An animal cell: the human's shelves and table, which the fruit fly's tool uses as they are
# and the thale cress's extends.
ANIMAL_CELL = Cell(
    shelves=[
        {"id": "cell", "label": "Cell membrane", "outside": "Outside the cell", "inside": "Inside the cell: in the cytoplasm"},
        {"id": "er", "label": "Endoplasmic reticulum membrane", "outside": "On the cytoplasmic face of the endoplasmic reticulum", "inside": "In the endoplasmic reticulum's lumen"},
        {"id": "mito", "label": "Mitochondrial inner membrane", "outside": "Between the mitochondrion's two membranes", "inside": "In the mitochondrial matrix"},
        {"id": "nucleus", "label": "Nuclear envelope", "outside": "On the cytoplasmic face of the nuclear envelope", "inside": "In the nucleus"},
        {"id": "other", "label": "Other membranes", "outside": "On the cytoplasmic face of one of the other membranes", "inside": "Within one of the other compartments"},
        {"id": "membrane", "label": "A membrane, not told which", "outside": "Beyond a membrane: outside the cell, or within a compartment", "inside": "On the cytoplasmic side of a membrane"},
    ],
    notes={
        "other": "The cell's remaining membranes together: those of the Golgi apparatus, endosomes, lysosomes, peroxisomes and vesicles, and the mitochondrion's outer membrane. Each protein here names its compartment in the mark 'where'.",
        "membrane": "The proteins that an entry places in a membrane without naming it, and those with no stated place whose entry carries a membrane-spanning segment or a signal peptide.",
    },
    places={
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
    },
    # A stated face -> the side, by shelf. The cytoplasm is inside the cell membrane and beyond
    # every internal membrane; on the shelf of a membrane that is not named, "outside" is the
    # side away from the cytoplasm.
    faces={
        "Cytoplasmic side": {"cell": "inside", "membrane": "inside", "er": "outside", "other": "outside", "nucleus": "outside", "mito": "outside"},
        "Extracellular side": {"cell": "outside", "membrane": "outside"},
        "Lumenal side": {"er": "inside", "other": "inside", "membrane": "outside"},
        "Matrix side": {"mito": "inside", "other": "inside"},
        "Intermembrane side": {"mito": "outside", "other": "inside"},
        "Nucleoplasmic side": {"nucleus": "inside"},
    },
    # The side away from the cytoplasm, where a protein that was exported ends up: outside the
    # cell, or within a compartment along the secretory pathway. UniProt's own pages say so of
    # the signal peptide and of the GPI anchor (help_signal.json, help_lipid.json).
    away={"cell": "outside", "membrane": "outside", "er": "inside", "other": "inside"},
)

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


class Vocabulary:
    """subcell.txt: each term's name, its path as UniProt writes it, and what it is a kind
    or a part of; and each location's line of a cell's table, resolved through those links."""

    def __init__(self, d, kb_docs, cell):
        self.cell = cell
        text = d.text(kb_docs, "subcell.txt")
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
        unknown = sorted(name for name in cell.places if name not in self.by_name)
        if unknown:
            raise SystemExit(f"the table names places the vocabulary does not have: {unknown}")
        for accession in sorted(SPANS | ANCHORED | cell.not_spanning):
            if self.terms.get(accession, {}).get("kind") != "topology":
                raise SystemExit(f"{accession} is no longer a topology of the vocabulary; read it again")
        faces = {term["name"] for term in self.terms.values() if term["kind"] == "face"}
        if set(cell.faces) - faces:
            raise SystemExit(f"the table names faces the vocabulary does not have: {sorted(set(cell.faces) - faces)}")
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
        places = self.cell.places
        rank = {MEMBRANE: 4, INSIDE: 3, OUTSIDE: 3, REGION: 2, WHOLE: 1, ELSEWHERE: 0}
        out = None
        if name in places:
            out = (*places[name], "table", name)
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
                out = (*places["Membrane"], "a membrane, not named", "Membrane")
            if out and out[1] in (WHOLE, REGION) and self.is_membrane(name):
                out = (out[0], MEMBRANE, out[2] + ", a membrane", out[3])
        if not trail:
            self.memo[name] = out
        return out


# ---------------------------------------------------------------------------------------
# Reading UniProt's entries: what each states and carries
# ---------------------------------------------------------------------------------------
#
# Two readings. A reviewed proteome (the human's, E. coli's): every entry is a curator's, and
# an evidence code the table above does not know stops the build. A whole reference proteome
# (the fruit fly's, thale cress's): reviewed entries and unreviewed ones, whose statements are
# made by UniProt's rule systems and programs, named on each evidence. Both give each entry
# the same fields; an entry of a whole proteome also says whether it is reviewed, and the
# genes of the database that ties a gene's entries together.

ANALYSIS = "sequence analysis"  # UniProt's evidence for what its curators take from a prediction program
OTHER = "other"                 # an experiment, likeness or a curator's own inference stands behind it


def evidence_of(evidences, where):
    codes = {item["evidenceCode"] for item in evidences or []}
    if not codes:
        return NOT_GIVEN
    for word, wanted, _ in EVIDENCE:
        if codes & set(wanted):
            return word
    raise SystemExit(f"{where}: an evidence code the table does not know ({sorted(codes)}); read UniProt's page on evidence again")


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


def _isoforms(item):
    """The isoform an entry displays, and how many others it describes."""
    displayed, described = None, 0
    for comment in item.get("comments", []):
        if comment["commentType"] == "ALTERNATIVE PRODUCTS":
            for isoform in comment.get("isoforms", []):
                status = isoform.get("isoformSequenceStatus")
                if status == "Displayed":
                    displayed = isoform["name"]["value"]
                described += status == "Described"
    return displayed, described


def _place_comments(item):
    """The entry's comments on its place, without those on where it is during an infection:
    (the comments, whether it states a place at all, how many on an infection were passed over)."""
    comments, states, infection = [], False, 0
    for comment in item.get("comments", []):
        if comment["commentType"] != "SUBCELLULAR LOCATION" or not comment.get("subcellularLocations"):
            continue
        states = True
        note = " ".join(text.get("value", "") for text in comment.get("note", {}).get("texts", []))
        if note.startswith("(Microbial infection)"):
            infection += 1
            continue
        comments.append(comment)
    return comments, states, infection


def _chosen(comments, displayed):
    """The comments that are read: those for the protein as a whole; else those for the
    canonical isoform; else those for the first other named form. (comments, how, the form)."""
    general = [comment for comment in comments if not comment.get("molecule")]
    if general:
        return general, "the entry as a whole", None
    if any(comment["molecule"] == f"Isoform {displayed}" for comment in comments):
        return [comment for comment in comments if comment["molecule"] == f"Isoform {displayed}"], "the canonical isoform", None
    if comments:
        of = comments[0]["molecule"]
        return [comment for comment in comments if comment["molecule"] == of], "another named form", of
    return [], None, None


def _check_parts(vocabulary, accession, topology, face):
    for part, kind in ((topology, "topology"), (face, "face")):
        known = vocabulary.terms.get(part.get("id"), {}) if part else None
        if part and (known.get("kind") != kind or known.get("path") != part["value"]):
            raise SystemExit(f"{accession} states a {kind} the vocabulary does not hold as written: {part}")


def _term(vocabulary, accession, stated):
    term = vocabulary.terms.get(stated["location"].get("id"))
    if term is None or term["kind"] != "location" or term["path"] != stated["location"]["value"]:
        raise SystemExit(f"{accession} states a place the vocabulary does not hold as written: {stated['location']}")
    return term


def _name(item):
    description = item["proteinDescription"]
    return (description.get("recommendedName") or (description.get("submissionNames") or [{}])[0]).get("fullName", {}).get("value", "")


def read_reviewed(d, kb, file, vocabulary):
    """Every entry of a reviewed proteome: its name, gene, length and level of evidence, the
    places it states, in order, and the features the rules read."""
    results = json.loads(d.text(kb, file))["results"]
    entries, counts = {}, Counter({"entries that state a place": 0, "comments on an infection, not read": 0})
    for item in results:
        accession = item["primaryAccession"]
        if not item["entryType"].startswith("UniProtKB reviewed"):
            raise SystemExit(f"{accession} is not a reviewed entry")
        name = _name(item)
        genes = item.get("genes") or []
        gene = genes[0].get("geneName", {}).get("value", "") if genes else ""
        features = Counter(feature["type"] for feature in item.get("features", []))
        displayed, described = _isoforms(item)
        comments, states, infection = _place_comments(item)
        counts["comments on an infection, not read"] += infection
        counts["entries that state a place"] += states
        chosen, how, of = _chosen(comments, displayed)
        if how:
            counts[f"place stated for {how}"] += 1
        statements = []
        for comment in chosen:
            for stated in comment["subcellularLocations"]:
                term = _term(vocabulary, accession, stated)
                line = vocabulary.resolve(term["name"])
                if line is None:
                    raise SystemExit(f"the table has no line for {term['name']!r} ({accession}); add one")
                topology, face = stated.get("topology"), stated.get("orientation")
                _check_parts(vocabulary, accession, topology, face)
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


# What stands behind a statement of a whole proteome, by UniProt's evidence codes. A reviewed
# entry's are a curator's; an unreviewed entry's are automatic: a rule system (ARBA, UniRule)
# or a program named on the feature.
RULE_CODES = {"ECO:0000255", "ECO:0000256", "ECO:0000259"}
# ECO:0000312, a statement a curator took over from another database (one fly entry has it), is counted with the curator's own.
WORDS = {"ECO:0000269": "experiment", "ECO:0000250": "similarity", "ECO:0000305": "curator", "ECO:0000303": "curator", "ECO:0000312": "curator", **{code: "rule" for code in RULE_CODES}}


def evidence_of_any(evidences, unknown):
    codes = {item["evidenceCode"] for item in evidences or []}
    if not codes:
        return NOT_GIVEN
    unknown.update(codes - set(WORDS))
    words = {WORDS[code] for code in codes if code in WORDS}
    return next((word for word in ("experiment", "similarity", "curator", "rule") if word in words), NOT_GIVEN)


def owner_of(item):
    """The rule system or the program an evidence names: a curator's sequence analysis names none."""
    source = item.get("source")
    if source == "SAM":  # UniProt's automatic sequence analysis names the program on the feature
        return item.get("id") or "unnamed analysis"
    return source or (ANALYSIS if item["evidenceCode"] == "ECO:0000255" else "unnamed analysis")


def behind_any(evidences):
    codes = {item["evidenceCode"] for item in evidences or []}
    if not codes:
        return (NOT_GIVEN,)
    if codes - RULE_CODES:
        return (OTHER,)
    return tuple(sorted({owner_of(item) for item in evidences}))


def rules_named_any(evidences):
    return sorted({f"{item['source']}:{item.get('id')}" for item in evidences or [] if item["evidenceCode"] in RULE_CODES and item.get("source") not in (None, "SAM")})


# UniProt's own rule systems and analyses behind a whole proteome's statements, and every owner
# a placement of a whole proteome may rest on.
OWN_SYSTEMS = ("ARBA", "RuleBase", "PIRNR", "SAAS", "unnamed analysis")
OWNERS = {"PROSITE-ProRule", "HAMAP-Rule", "segments", "signal", "big-PI", "TMHMM", "Phobius", "SignalP", *OWN_SYSTEMS}


def read_proteome(d, kb, file, vocabulary, gene_db):
    """Every entry of a whole reference proteome, reviewed and unreviewed, as read_reviewed
    reads a reviewed one, with what an unreviewed entry adds: whether it is reviewed, and its
    genes in the database gene_db = (name, how its identifiers begin), under "genes"."""
    results = json.loads(d.text(kb, file))["results"]
    entries, counts, unknown_codes, unknown_places = {}, Counter(), Counter(), Counter()
    for item in results:
        accession = item["primaryAccession"]
        reviewed = item["entryType"].startswith("UniProtKB reviewed")
        name = _name(item)
        genes = item.get("genes") or []
        gene = next((g[key]["value"] for g in genes for key in ("geneName", "orderedLocusNames", "orfNames") if isinstance(g.get(key), dict)), "")
        if not gene and genes:
            gene = next((names[0]["value"] for g in genes for key in ("orfNames", "orderedLocusNames") for names in [g.get(key) or []] if names), "")
        gene_ids = sorted({ref["id"] for ref in item.get("uniProtKBCrossReferences", []) if ref["database"] == gene_db[0] and ref["id"].startswith(gene_db[1])})
        features = Counter(feature["type"] for feature in item.get("features", []))
        displayed, described = _isoforms(item)
        comments, states, _ = _place_comments(item)
        counts["reviewed, states a place" if reviewed else "unreviewed, states a place"] += states
        chosen, _, of = _chosen(comments, displayed)
        statements = []
        for comment in chosen:
            for stated in comment["subcellularLocations"]:
                term = _term(vocabulary, accession, stated)
                line = vocabulary.resolve(term["name"])
                if line is None:
                    unknown_places[term["name"]] += 1
                    continue
                topology, face = stated.get("topology"), stated.get("orientation")
                _check_parts(vocabulary, accession, topology, face)
                location = stated["location"].get("evidences")
                statements.append({
                    "name": term["name"], "words": stated["location"]["value"], "accession": term["accession"], "shelf": line[0], "kind": line[1], "under": line[3],
                    "topology": topology["id"] if topology else None, "topology_words": topology["value"] if topology else None,
                    "face": vocabulary.terms[face["id"]]["name"] if face else None, "face_accession": face["id"] if face else None,
                    "evidence": evidence_of_any(location, unknown_codes), "by_rule": sorted({owner_of(source) for source in location or [] if source["evidenceCode"] in RULE_CODES and source.get("source")}),
                    "topology_evidence": evidence_of_any(topology.get("evidences"), unknown_codes) if topology else None,
                    "behind": behind_any(location), "rules": rules_named_any(location),
                    "topology_behind": behind_any(topology.get("evidences")) if topology else None,
                    "face_behind": behind_any(face.get("evidences")) if face else None,
                })
        of_type = lambda kind: [evidence for feature in item.get("features", []) if feature["type"] == kind for evidence in feature.get("evidences", [])]
        entries[accession] = {
            "id": accession, "name": name, "gene": gene, "length": item["sequence"]["length"], "reviewed": reviewed, "genes": gene_ids,
            "seen": int(item["proteinExistence"].split(":")[0]), "isoforms": 1 + described,
            "statements": statements, "of": of, "segments": features["Transmembrane"], "signal": features["Signal"] > 0,
            "segments_only_predicted": bool(features["Transmembrane"]) and not ({e["evidenceCode"] for e in of_type("Transmembrane")} - RULE_CODES),
            "signal_only_predicted": features["Signal"] > 0 and not ({e["evidenceCode"] for e in of_type("Signal")} - RULE_CODES),
            "segments_behind": behind_any(of_type("Transmembrane")) if features["Transmembrane"] else None,
            "signal_behind": behind_any(of_type("Signal")) if features["Signal"] else None,
        }
    if unknown_codes or unknown_places:
        raise SystemExit(f"evidence codes the table does not know: {dict(unknown_codes)}; places the table has no line for: {dict(unknown_places)}")
    if len(entries) != len(results):
        raise SystemExit("two entries share an accession")
    return entries, counts


def gene_set(d, kb, file):
    """UniProt's gene-by-gene set of a proteome: the accessions of its entries, in the file's order."""
    found = [line.split("|")[1] for line in d.text(kb, file).splitlines() if line.startswith(">")]
    if len(found) != len(set(found)):
        raise SystemExit("the gene-by-gene set names an entry twice")
    return found


def proteome_totals(d, kb, places_file, signatures_file, proteome_id, taxon, vocabulary, every, read):
    """A whole proteome's counts as UniProt gives them, checked against the entries read:
    (the counts, the release, the proteome's own record)."""
    release = d.entry(kb, places_file)["x_uniprot_release"]
    proteome = json.loads(d.text(kb, f"proteome_{proteome_id}.json"))
    total = {name: d.total(kb, f"count_{name}.json") for name in ("all", "reviewed", "unreviewed", "reviewed_with_place", "unreviewed_with_place")}
    if any(d.entry(kb, file)["x_uniprot_release"] != release for file in (signatures_file, "count_all.json", "count_reviewed.json", "count_unreviewed.json")) or vocabulary.release != release:
        raise SystemExit("the downloads from UniProt are not of one release; fetch them again")
    if total["all"] != len(every) or total["reviewed"] != sum(1 for e in every.values() if e["reviewed"]) or total["reviewed"] + total["unreviewed"] != total["all"] or proteome["proteinCount"] != total["all"] or proteome["taxonomy"]["taxonId"] != taxon:
        raise SystemExit(f"the entries read do not add up to UniProt's own counts: {total}")
    if total["reviewed_with_place"] != read["reviewed, states a place"] or total["unreviewed_with_place"] != read["unreviewed, states a place"]:
        raise SystemExit(f"the entries that state a place are not as many as UniProt's search finds: {dict(read)} against {total}")
    return total, release, proteome


def one_for_each_gene(d, kb, canonical_file, every, total, proteome, no_gene):
    """The catalogue of a whole proteome: one protein for each gene, as UniProt's gene-by-gene
    set gives it. Returns the entries shown, how many of the proteome's entries each one's
    genes have (itself included), and the counts; no_gene names the count of the proteins
    shown whose entry gives no gene of the database."""
    chosen = gene_set(d, kb, canonical_file)
    missing = [accession for accession in chosen if accession not in every]
    if missing:
        raise SystemExit(f"{len(missing)} proteins of the gene-by-gene set are not entries of the proteome as fetched ({missing[:5]}); fetch both again")
    entries = {accession: every[accession] for accession in chosen}
    of_gene = defaultdict(set)
    for accession, entry in every.items():
        for gene_id in entry["genes"]:
            of_gene[gene_id].add(accession)
    together = {accession: len(set().union({accession}, *(of_gene[gene_id] for gene_id in entry["genes"]))) for accession, entry in entries.items()}
    covered = set().union(set(entries), *(of_gene[gene_id] for entry in entries.values() for gene_id in entry["genes"]))
    stated = {
        "entries": total["all"], "reviewed": total["reviewed"], "unreviewed": total["unreviewed"], "genes": proteome["geneCount"],
        "shown": len(entries), "shown_reviewed": sum(1 for e in entries.values() if e["reviewed"]), "shown_unreviewed": sum(1 for e in entries.values() if not e["reviewed"]),
        "further": total["all"] - len(entries), "further_tied_to_a_shown_gene": len(covered) - len(entries), no_gene: sum(1 for e in entries.values() if not e["genes"]),
    }
    if abs(stated["shown"] - stated["genes"]) > 0.01 * stated["genes"]:
        raise SystemExit(f"the gene-by-gene set holds {stated['shown']:,} proteins and the proteome counts {stated['genes']:,} genes")
    return entries, together, stated


def read_signatures(d, kb, file, entries, catalogue=False):
    """The InterPro entries and the Gene Ontology terms UniProt gives each entry. With
    catalogue, the table may hold more entries than the catalogue, and only its own are read."""
    lines = d.text(kb, file).splitlines()
    if lines[0].split("\t") != ["Entry", "InterPro", "Gene Ontology IDs"]:
        raise SystemExit("UniProt's table of signatures and terms is not the one asked for")
    signatures, terms = {}, {}
    for line in lines[1:]:
        accession, found, ontology = line.split("\t")
        if catalogue and accession not in entries:
            continue
        signatures[accession] = [signature for signature in found.split(";") if signature]
        terms[accession] = [term.strip() for term in ontology.split(";") if term.strip()]
    if set(signatures) != set(entries):
        raise SystemExit("the table of signatures does not hold every protein of the catalogue; fetch both again" if catalogue else "the two downloads from UniProt are not of the same entries; fetch both again")
    return signatures, terms


# ---------------------------------------------------------------------------------------
# Placing: the side of each protein
# ---------------------------------------------------------------------------------------

def side_by_words(statement, cell):
    """The side that the words of one statement give, with the rule's name; or (None, None)."""
    shelf, kind = statement["shelf"], statement["kind"]
    if kind in (INSIDE, OUTSIDE):
        return kind, "place"
    if statement["topology"] in SPANS:
        return ("in", "spans") if kind in (MEMBRANE, WHOLE) else (None, None)
    if statement["face"]:
        side = cell.faces[statement["face"]].get(shelf)
        if side is None and kind == MEMBRANE:
            raise SystemExit(f"the table has no side for the {statement['face']!r} of a membrane on the shelf {shelf!r}; add one")
        return (side, "face") if side else (None, None)
    if statement["topology"] in ANCHORED and kind in (MEMBRANE, WHOLE) and shelf in cell.away:
        return cell.away[shelf], "anchor"
    return None, None


def place(entry, vocabulary):
    """Where one protein stands, by the vocabulary's cell: its shelf, side and basis, the rule
    that gave them, the statement that decided and the other statements."""
    cell = vocabulary.cell
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
    side, rule = side_by_words(first, cell)
    if side:
        return result(first["shelf"], side, "stated", rule, first)
    # A later statement that names a part or a kind of the first place, and gives the side.
    for later in of_cell[1:]:
        if first["name"] in vocabulary.broader(later["name"]):
            side, rule = side_by_words(later, cell)
            if side:
                return {**result(later["shelf"], side, "stated", "later part", later), "words_rule": rule}
    # The entry's own features, where one membrane is meant and the words do not say otherwise.
    one_membrane = first["kind"] in (MEMBRANE, WHOLE)
    if entry["segments"] and one_membrane and first["topology"] not in cell.not_spanning | ANCHORED:
        return result(first["shelf"], "in", "predicted", "segment", first)
    if entry["signal"] and not entry["segments"] and one_membrane and first["shelf"] in cell.away:
        return result(first["shelf"], cell.away[first["shelf"]], "predicted", "signal", first)
    return result(first["shelf"], "not known", "none", "side not stated", first)


# ---------------------------------------------------------------------------------------
# Filing: families and districts, by the rules of the planarian's shelves
# ---------------------------------------------------------------------------------------
#
# A family has the same id in every species only if it is chosen the same way: the rule
# below and the districts' table are those of tools/build_planarian_atlas.py, word for
# word in what they do. tests/human_atlas.test.mjs holds the two files' districts equal.

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


def read_entry_names(d, ipr):
    entries = {}
    for line in d.text(ipr, "entry.list").splitlines()[1:]:
        columns = line.split("\t")
        if len(columns) >= 3:
            entries[columns[0]] = {"type": columns[1], "name": columns[2]}
    return entries


def read_hierarchy(d, ipr):
    """InterPro's tree: each entry's parent, the broader entry it is a kind of."""
    parent, stack = {}, []
    for line in d.text(ipr, "ParentChildTreeFile.txt").splitlines():
        if not line.strip():
            continue
        depth = (len(line) - len(line.lstrip("-"))) // 2
        accession = line.lstrip("-").split("::")[0]
        stack = stack[:depth]
        if depth:
            parent[accession] = stack[-1]
        stack.append(accession)
    return parent


def read_family_terms(d, ipr):
    """InterPro's mapping of its entries to Gene Ontology terms."""
    terms = defaultdict(list)
    for line in d.text(ipr, "interpro2go").splitlines():
        found = re.match(r"InterPro:(IPR\d+) .* ; (GO:\d+)$", line)
        if found and found.group(2) not in terms[found.group(1)]:
            terms[found.group(1)].append(found.group(2))
    return dict(terms)


def read_ontology(d, go):
    """The Gene Ontology: each term's name and the broader terms it is a kind or a part of."""
    terms, current = {}, None
    text = d.text(go, "go-basic.obo")
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


def ontology_citation(d, go):
    """The two papers the Gene Ontology asks to be cited, in its own page's words."""
    page = plain(d.text(go, "go_citation_policy.html"))
    first = re.search(r"(Ashburner et al\. Gene ontology: tool for the unification of biology\. [^\[]*?DOI: \S+)", page)
    latest = re.search(r"(The Gene Ontology Consortium\. The Gene Ontology knowledgebase in \d{4}\. [^\[]*?DOI: \S+)", page)
    if not first or not latest:
        raise SystemExit("the Gene Ontology's saved page no longer names the two papers to cite; read it again")
    return f"{first.group(1)}; {latest.group(1)}"


class Filing:
    """One family for each protein, and the district its terms put it in. kb and signatures:
    the folder and the file of UniProt's table of InterPro entries and Gene Ontology terms;
    ipr and go: the folders of InterPro's files and of the Gene Ontology; catalogue: the table
    may hold more entries than the catalogue (read_signatures)."""

    def __init__(self, d, entries, kb, signatures, ipr, go, catalogue=False):
        self.names = read_entry_names(d, ipr)
        self.parent = read_hierarchy(d, ipr)
        self.release = re.search(r"Release ([\d.]+),", d.text(ipr, "release_notes.txt")).group(1)
        self.signatures, self.entry_terms = read_signatures(d, kb, signatures, entries, catalogue)
        self.signature_terms = read_family_terms(d, ipr)
        self.terms, self.ontology = read_ontology(d, go)
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

    def carriers(self):
        """signature -> the proteins that carry it."""
        out = defaultdict(list)
        for accession, found in self.signatures.items():
            for signature in found:
                out[signature].append(accession)
        return out


# ---------------------------------------------------------------------------------------
# Lines: the families' lines, the parts of 'lone' and of 'no_family'
# ---------------------------------------------------------------------------------------

SHELF_FORMAT = "cells.visualizer.species_proteins@1"
MEMBERS_FORMAT = "cells.visualizer.species_protein_members@1"
SHELVES_FILE = "shelves.json"
TABLE_FILE = "proteins.tsv"
TABLE_COLUMNS = ["id", "gene", "name", "length", "isoforms", "seen", "under", "shelf", "side", "basis", "evidence", "place", "also", "units", "family", "of"]
# A whole proteome's table adds whether the entry is reviewed, and how many entries its gene has.
PROTEOME_COLUMNS = [*TABLE_COLUMNS, "reviewed", "entries"]
MEMBER_COLUMNS = ["id", "label", "gene", "side", "basis", "length", "unit", "marks"]
PLACE_COLUMNS = ["id", "words", "shelf", "names", "resolved", "under", "first"]
SIDES = ["outside", "in", "inside", "not known"]
SIDE_TIE = ["in", "outside", "inside", "not known"]  # where a line's members are split evenly
NO_SHELF = "no shelf"  # the name under which a file counts the proteins that are on none
MEMBERS_PER_FILE = 2000
# A family with at most this many members in the whole catalogue has no line of its own:
# it does not open. Its protein is listed with the others like it, and names its family.
# 0 gives every family its lines; the human's file then passes its limit of 1 MB.
LONE_UP_TO = 1
LIMIT_SHELVES, LIMIT_FILE, LIMIT_FOLDER = 1_000_000, 3_000_000, 3_000_000
# The table writes the basis and the evidence with one letter each, to stay within its size.
BASIS_LETTER = {"stated": "s", "predicted": "p", "none": "n"}
EVIDENCE_LETTER = {"experiment": "e", "similarity": "s", "curator": "c", "rule": "r", NOT_GIVEN: "n"}
FAMILY_COLUMNS = ["id", "label", "shelf", "side", "group", "count", "sides", "file", "at", "units", "total"]
PART_COLUMNS = ["id", "label", "kind", "shelf", "side", "group", "count", "sides", "file", "at", "units"]
PART_KIND = lambda part: "superfamily" if part.startswith("IPR") else "other signature" if part == "other-signature" else "no signature"
PART_LABEL = {"other-signature": "A domain, repeat or site signature, and no family or superfamily", "no-signature": "No signature of any kind"}
PART_RANK = {"superfamily": 0, "other signature": 1, "no signature": 2}
LONE_LABEL = "The only member of its family"


def majority(sides):
    """The side most members sit on; of equals, the first in SIDE_TIE."""
    return max(SIDE_TIE, key=lambda side: (sides.get(side, 0), -SIDE_TIE.index(side)))


def ordered_sides(counts):
    return {side: counts[side] for side in SIDES if counts.get(side)}


def make_lines(entries, placed, filing, units, cell, lone_up_to=None):
    """The lines of the file, in the order the members follow: a family's line for each
    shelf of the cell that holds members of it, then the proteins that are the only member of
    their family, by shelf, district and side, then the parts of "no family" for each shelf."""
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
    lines.sort(key=lambda line: (cell.rank(line["shelf"]), DISTRICT_ORDER.index(line["group"]), -len(line["proteins"]), line["id"]))
    alone = []
    for (shelf, group, side), proteins in lone.items():
        alone.append({"what": "lone", "id": f"lone-{group}-{side.replace(' ', '-')}", "label": LONE_LABEL, "kind": "lone", "shelf": shelf, "side": side, "group": group, "sides": sides_of(proteins), "proteins": proteins, "units": held(proteins)})
    alone.sort(key=lambda line: (cell.rank(line["shelf"]), DISTRICT_ORDER.index(line["group"]), SIDES.index(line["side"])))
    rest = []
    for (part, shelf), proteins in parts.items():
        sides = sides_of(proteins)
        rest.append({"what": "part", "id": part, "label": filing.names[part]["name"] if part.startswith("IPR") else PART_LABEL[part], "kind": PART_KIND(part), "shelf": shelf, "side": majority(sides), "group": filing.district(proteins, loose=True), "sides": sides, "proteins": proteins, "units": held(proteins)})
    rest.sort(key=lambda line: (cell.rank(line["shelf"]), PART_RANK[line["kind"]], -len(line["proteins"]), line["id"]))
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


def in_order(entries, lines, alone, rest):
    """Every protein in the order the lines read them; the build stops if one is filed twice or not at all."""
    sequence = [protein for line in [*lines, *alone, *rest] for protein in line["proteins"]]
    if len(sequence) != len(entries) or len(set(sequence)) != len(entries):
        raise SystemExit("a protein is filed twice or not at all")
    return sequence


def line_row(line, columns):
    values = {**line, "count": len(line["proteins"]), "sides": ordered_sides(line["sides"])}
    return [values[column] for column in columns]


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
# Counts
# ---------------------------------------------------------------------------------------

def counted(placed, cell):
    """The placements counted: by shelf and side (with the proteins on no shelf), by side, by
    side and basis, by rule, and by what stands behind the deciding statement."""
    key = lambda shelf: NO_SHELF if shelf is None else shelf
    shelf_counts = {name: {side: 0 for side in SIDES} for name in [*cell.ids, NO_SHELF]}
    for item in placed.values():
        shelf_counts[key(item["shelf"])][item["side"]] += 1
    counts = {side: sum(found[side] for found in shelf_counts.values()) for side in SIDES}
    bases = Counter((item["side"], item["basis"]) for item in placed.values())
    rules = Counter(item["rule"] for item in placed.values())
    evidence = Counter(item["evidence"] for item in placed.values() if item["evidence"])
    return shelf_counts, counts, bases, rules, evidence


def by_basis(bases):
    return {side: {basis: bases[side, basis] for basis in ("stated", "predicted", "none") if bases.get((side, basis))} for side in SIDES}


def by_evidence(evidence):
    return {word: evidence.get(word, 0) for word in [word for word, _, _ in EVIDENCE] + [NOT_GIVEN]}


def shelf_rows(cell, shelf_counts, lines, alone, rest, notes=None):
    """Each shelf of the cell with its note (from notes, else the cell's) and its counts; and
    the same counts of the proteins on no shelf."""
    notes = cell.notes if notes is None else notes
    shelves = []
    for shelf in cell.shelves:
        on = [line for line in lines if line["shelf"] == shelf["id"]]
        here = sum(len(line["proteins"]) for line in alone if line["shelf"] == shelf["id"])
        shelves.append({**shelf, **({"note": notes[shelf["id"]]} if shelf["id"] in notes else {}), "proteins": sum(shelf_counts[shelf["id"]].values()), "families": len(on) + here, "lines": len(on), "lone": here, "no_family": sum(len(line["proteins"]) for line in rest if line["shelf"] == shelf["id"])})
    none = [line for line in lines if line["shelf"] is None]
    here = sum(len(line["proteins"]) for line in alone if line["shelf"] is None)
    no_shelf = {"proteins": sum(shelf_counts[NO_SHELF].values()), "families": len(none) + here, "lines": len(none), "lone": here, "no_family": sum(len(line["proteins"]) for line in rest if line["shelf"] is None)}
    return shelves, no_shelf


def district_rows(lines, alone):
    """Each district, with the Gene Ontology terms that put a protein in it, and its counts."""
    groups = []
    for group in DISTRICT_ORDER:
        wanted = next((terms for key, _, terms in DISTRICTS if key == group), None)
        said_from = "Gene Ontology terms: " + ", ".join(f"{name} ({term})" for term, name in wanted) if wanted else "The line's proteins carry Gene Ontology terms, and none of the districts' terms" if group == OTHER_DISTRICT[0] else "The line's proteins carry no Gene Ontology term"
        on = [line for line in lines if line["group"] == group]
        groups.append({"id": group, "label": DISTRICT_LABEL[group], "from": said_from, "lines": len(on), "proteins": sum(len(line["proteins"]) for line in on), "lone": sum(len(line["proteins"]) for line in alone if line["group"] == group)})
    return groups


def place_rows(entries, placed, vocabulary):
    """Every place the entries state, with the table's line for each and how many proteins it
    places as the statement that decided; and the words of each identifier the table uses.
    Returns (rows, words, how many each place decides, the places used)."""
    first_places = Counter(item["where"]["name"] for item in placed.values() if item["where"])
    used = {statement["name"] for entry in entries.values() for statement in entry["statements"]}
    rows = []
    for name in sorted(used, key=lambda name: (-first_places[name], name)):
        shelf, kind, how, under = vocabulary.resolve(name)
        rows.append([vocabulary.by_name[name]["accession"], vocabulary.by_name[name]["path"], shelf, kind, how, under, first_places[name]])
    codes_used = {part for entry in entries.values() for statement in entry["statements"] for part in code(statement).split(".")}
    place_words = {term["accession"][3:]: term["path"] for term in sorted(vocabulary.terms.values(), key=lambda term: term["accession"]) if term["accession"][3:] in codes_used}
    return rows, place_words, first_places, used


def lone_block(alone, lone_families):
    """The file's 'lone': the proteins that are the only member of their family, in parts."""
    lone_sides = Counter(side for line in alone for side, count in line["sides"].items() for _ in range(count))
    return {
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


def no_family_block(filing, placed):
    """The file's 'no_family': the proteins with no family, in parts."""
    return {
        "label": "No family assigned",
        "count": len(filing.part),
        "sides": ordered_sides(Counter(placed[protein]["side"] for protein in filing.part)),
        "parts_from": (
            "A protein with no family is filed under one part. If it carries an InterPro entry of the type Homologous superfamily, the part is that superfamily: a wider grouping than a family, by shared structure. "
            "Of several superfamilies it is the one fewest proteins of this catalogue carry, then the first by accession. The other two parts hold the proteins with only a domain, repeat or site signature, and those with no signature at all. A part has one line for each shelf, as a family has."
        ),
        "part_columns": PART_COLUMNS,
    }


def letters():
    """The letters of the table's basis, evidence and level of evidence, as members_from gives them."""
    return {"basis": {letter: word for word, letter in BASIS_LETTER.items()}, "evidence": {letter: word for word, letter in EVIDENCE_LETTER.items()}, "seen": {str(level): SEEN[level] for level in sorted(SEEN)}}


# The kinds of what stands behind a protein's place, for a whole proteome's curated and automatic entries.
SURE = ["stated, on an experiment", "stated, by likeness", "stated, by a curator's inference", "stated, with no evidence given", "stated, by a rule", "predicted from a segment or a signal", "not known"]


def how_sure(entries, placed):
    """What stands behind each protein's place, counted for reviewed and for unreviewed entries."""
    def sure(accession):
        item = placed[accession]
        return "predicted from a segment or a signal" if item["basis"] == "predicted" else "not known" if item["basis"] == "none" else {"experiment": "stated, on an experiment", "similarity": "stated, by likeness", "curator": "stated, by a curator's inference", "rule": "stated, by a rule", NOT_GIVEN: "stated, with no evidence given"}[item["evidence"]]
    out = {kind: {"reviewed": 0, "unreviewed": 0} for kind in SURE}
    for accession in entries:
        out[sure(accession)]["reviewed" if entries[accession]["reviewed"] else "unreviewed"] += 1
    return out


# ---------------------------------------------------------------------------------------
# What the placements rest on that a rule system or a program computed
# ---------------------------------------------------------------------------------------

# What rests on an owner, as account() counts it.
ON_PLACE, ON_SPANS, ON_FACE, ON_ANCHOR = "the stated place", "the statement that it spans the membrane", "the stated face", "the stated GPI anchor"
FROM_SEGMENTS, FROM_SIGNAL = "a side read from its segments", "a side read from its signal peptide"


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
                on[owner][ON_PLACE].add(accession)
            for named in decided["rules"] if set(decided["behind"]) - {OTHER, NOT_GIVEN, ANALYSIS} else []:
                rule_ids[named.split(":")[0]][named.split(":")[1]] += 1
            word = decided["topology_behind"] if words_rule in ("spans", "anchor") else decided["face_behind"] if words_rule == "face" else None
            for owner in word or ():
                what = {"spans": ON_SPANS, "anchor": ON_ANCHOR, "face": ON_FACE}[words_rule]
                on["big-PI" if owner == ANALYSIS and words_rule == "anchor" else "segments" if owner == ANALYSIS else owner][what].add(accession)
        if rule in ("segment", "no place: segment"):
            for owner in entry["segments_behind"]:
                on["segments" if owner == ANALYSIS else owner][FROM_SEGMENTS].add(accession)
        if rule in ("signal", "no place: signal"):
            for owner in entry["signal_behind"]:
                on["signal" if owner == ANALYSIS else owner][FROM_SIGNAL].add(accession)
    out = {}
    for owner, found in on.items():
        if owner in (OTHER, NOT_GIVEN):
            continue
        out[owner] = {"placements": len(set().union(*found.values())), **{what: len(proteins) for what, proteins in sorted(found.items())}}
    return out, {owner: dict(sorted(found.items(), key=lambda pair: (-pair[1], pair[0]))) for owner, found in rule_ids.items()}


# ---------------------------------------------------------------------------------------
# The sources every species' shelves name
# ---------------------------------------------------------------------------------------

CITE_UNIPROT = "The UniProt Consortium, UniProt: the Universal Protein Knowledgebase in 2025, Nucleic Acids Res. 53:D609-D617 (2025)"
CITE_INTERPRO = "Blum and others (2025) InterPro: the protein sequence classification resource in 2025. Nucleic Acids Res 53:D444-D456."
PREDICTORS = "TMHMM, Memsat, Phobius and a hydrophobic moment plot for the segments; Phobius, Predotar, SignalP and TargetP for the signal peptides"
RULING = "By the project's rule (the user, 15 November 2026), a value stands on the terms of the database it was read from, and the tool behind it is named and counted: the project's rule, not a legal opinion."
DTU_LICENCE = "Academic licence of DTU Health Tech: free to publicly funded academic, education or research institutions for internal research, and any other user must obtain a commercial licence. It is a licence of the program: no clause speaks of predictions made with it"
NOT_RUN = "Nothing was downloaded from it but its statement of terms, and the program was not run here."
FOUR_SEGMENTS = "One of the four methods UniProt names for the membrane-spanning segments of its reviewed entries; it keeps a segment that at least two of them find, and does not say which"
FOUR_SIGNALS = "One of the four methods UniProt names for the signal peptides of its reviewed entries; it keeps a signal that at least two of them find, and does not say which"
# The rule systems and the programs behind what UniProt's entries state by rule or by sequence
# analysis, each a source of its own, read through UniProt: its address, its terms as its own
# page states them, and their class. What rests on it is the species' own, in "holds".
THROUGH_UNIPROT = {
    "PROSITE": ("https://prosite.expasy.org/prosite_license.html", "CC BY-NC-ND 4.0; commercial users are asked to pay a yearly licence fee", "non-commercial"),
    "HAMAP": ("https://hamap.expasy.org/hamap_about.html", "CC BY 4.0", "permissive"),
    "TMHMM": ("https://services.healthtech.dtu.dk/services/TMHMM-2.0/", DTU_LICENCE, "non-commercial"),
    "Phobius": ("https://phobius.sbc.su.se/download", "For academic users only: the program may be used for private study, education or nonprofit research, and other users are asked to write to its author. The terms are of the program: they do not speak of predictions made with it", "non-commercial"),
    "SignalP": ("https://services.healthtech.dtu.dk/services/SignalP-5.0/", DTU_LICENCE, "non-commercial"),
    "TargetP": ("https://services.healthtech.dtu.dk/services/TargetP-2.0/", DTU_LICENCE, "non-commercial"),
    "Memsat": ("https://www.uniprot.org/help/transmem", "Terms not read: UniProt's help names Memsat without a version or an address, so no page of terms could be tied to the program it runs", "no stated terms"),
    "Predotar": ("https://www.uniprot.org/help/signal", "Terms not read: the program's own page answers this tool with a check for a browser, so its terms could not be read", "no stated terms"),
    "big-PI": ("https://mendel.imp.ac.at/gpi/gpi_server.html", "No open licence stated: the predictor's own page gives no terms of use", "no stated terms"),
}


def through_uniprot(name, accessed, holds_):
    """A rule system's or a program's entry among a file's sources, read through UniProt."""
    url, licence, kind = THROUGH_UNIPROT[name]
    return {"name": name, "url": url, "licence": licence, "class": kind, "accessed": accessed, "through": "UniProt", "holds": holds_}


# ---------------------------------------------------------------------------------------
# Writing: shelves.json, proteins.tsv and the members' files
# ---------------------------------------------------------------------------------------

def shelves_text(header, lines, alone, rest, lone, no_family, tail, places, place_words, closing, families_in_all, highlights=None):
    """shelves.json: the header, then each line of the families, of 'lone' and of 'no_family'
    on a row of its own, then the tail, the places and the closing. highlights: rows that
    closing["highlights"] lists, each on a row of its own after its columns."""
    rows = lambda items, pad=" ": "[\n" + ",\n".join(f"{pad} " + compact(item) for item in items) + f"\n{pad}]"
    nested = lambda block, items: json.dumps(block, indent=1, ensure_ascii=False).replace("\n", "\n ")[:-3] + ',\n  "parts": ' + rows(items, "  ") + "\n }"
    body = json.dumps(header, indent=1, ensure_ascii=False)[:-2]
    body += ',\n "families": ' + rows([line_row(line, FAMILY_COLUMNS) for line in lines])
    body += f',\n "distinct_families": {len({line["id"] for line in lines})},\n "family_lines": {len(lines)},\n "families_in_all": {families_in_all}'
    body += ',\n "lone": ' + nested(lone, [line_row(line, PART_COLUMNS) for line in alone])
    body += ',\n "no_family": ' + nested(no_family, [line_row(line, PART_COLUMNS) for line in rest])
    body += "," + json.dumps(tail, indent=1, ensure_ascii=False)[1:-2]
    body += ',\n "places": ' + rows(places)
    body += ',\n "place_words": ' + json.dumps(place_words, ensure_ascii=False, separators=(", ", ": "))
    text = json.dumps(closing, indent=1, ensure_ascii=False)
    if highlights is not None:
        columns = closing["highlights"]["columns"]
        mark = '"columns": ' + json.dumps(columns, indent=1, ensure_ascii=False).replace("\n", "\n  ")
        if text.count(mark) != 1:
            raise SystemExit("the highlights' columns are not where the writer expects them")
        text = text.replace(mark, '"columns": ' + compact(columns) + ',\n  "rows": ' + rows(highlights, "  "))
    body += "," + text[1:] + "\n"
    json.loads(body)
    return body


def table_text(columns, sequence, entries, placed, filing, alone, units, more=None):
    """proteins.tsv: one line for each protein, in the members' order, under the columns.
    more(protein): the values of the species' own columns, after the shared ones."""
    lone_of = {protein for line in alone for protein in line["proteins"]}
    table_rows = []
    for protein in sequence:
        entry, item = entries[protein], placed[protein]
        under = filing.family.get(protein) or filing.part[protein]
        table_rows.append([
            protein, entry["gene"], entry["name"], str(entry["length"]), str(entry["isoforms"]), str(entry["seen"]), under, item["shelf"] or "", item["side"], BASIS_LETTER[item["basis"]], EVIDENCE_LETTER[item["evidence"]] if item["evidence"] else "",
            code(item["where"]) if item["where"] else "", ",".join(code(statement) for statement in item["also"]), ";".join(units.get(protein, [])),
            filing.names[under]["name"] if protein in lone_of else "", entry["of"] or "", *(more(protein) if more else ()),
        ])
    for row in table_rows:
        if any("\t" in value or "\n" in value for value in row):
            raise SystemExit(f"{row[0]}: a value of the table holds a tab or a line break")
    return "\n".join("\t".join(row) for row in [columns, *table_rows]) + "\n"


def within_limits(files_out, paths, folder=False):
    """The files' sizes; the build stops if a file would hold a machine path (paths), or if
    the files outgrow their limits (and, with folder, the folder its limit)."""
    for name, text in files_out.items():
        if paths.search(text):
            raise SystemExit(f"the {name} would hold a machine path")
    size = {name: len(text.encode("utf-8")) for name, text in files_out.items()}
    if size["shelves"] >= LIMIT_SHELVES or max(size.values()) >= LIMIT_FILE or (folder and sum(size.values()) >= LIMIT_FOLDER):
        raise SystemExit(f"the files have outgrown their limits: {size}")
    return size


def cut_members(folder, first=None, last=None):
    """The members' files, cut from the two files of the repository as shelves.json says:
    {file name: text}. Reads nothing else. first(row) and last(row): the marks of a
    species' own columns, before the shared marks and after them."""
    folder = Path(folder)
    shelves = json.loads((folder / SHELVES_FILE).read_text(encoding="utf-8"))
    with open(folder / TABLE_FILE, encoding="utf-8") as handle:
        header = handle.readline().rstrip("\n").split("\t")
        table = [dict(zip(header, line.rstrip("\n").split("\t"))) for line in handle]
    said = shelves["place_words"]
    place_said = lambda written: "; ".join(said[part] for part in written.split("."))
    letters_ = shelves["members_from"]["letters"]
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
            marks = {**(first(row) if first else {}), "isoforms": int(row["isoforms"]), "seen": letters_["seen"][row["seen"]]}
            if row["evidence"]:
                marks["evidence"] = letters_["evidence"][row["evidence"]]
            if row["place"]:
                marks["where"] = place_said(row["place"])
            if row["also"]:
                marks["also"] = [place_said(written) for written in row["also"].split(",")]
            if what == "lone":
                marks["family"] = [row["under"], row["family"]]
            if row["of"]:
                marks["of"] = row["of"]
            if last:
                marks.update(last(row))
            files[line["file"]].append([row["id"], row["name"], row["gene"], row["side"], letters_["basis"][row["basis"]], int(row["length"]), row["units"].split(";") if row["units"] else None, marks])
    if cursor != len(table):
        raise SystemExit(f"the table holds {len(table)} proteins and the lines {cursor}")
    out = {}
    for file in sorted(files):
        head = {"format": MEMBERS_FORMAT, "species": shelves["species"], "file": file, "columns": shelves["member_columns"]}
        out[file] = json.dumps(head, indent=1, ensure_ascii=False)[:-2] + ',\n "members": [\n' + ",\n".join("  " + compact(member) for member in files[file]) + "\n ]\n}\n"
        json.loads(out[file])
    return out


def proteome_values(entries, together):
    """The values of a whole proteome's own two columns, for table_text."""
    return lambda protein: ["1" if entries[protein]["reviewed"] else "0", str(together[protein])]


def proteome_marks(row):
    """The marks of a whole proteome's own two columns, for cut_members: before the shared ones."""
    return {"reviewed": row["reviewed"] == "1", "entries": int(row["entries"])}


def write_members(shelves_folder, out, first=None, last=None):
    """The members step of a species' tool: cut the files and write them into out."""
    Path(out).mkdir(parents=True, exist_ok=True)
    for name, text in cut_members(shelves_folder, first, last).items():
        (Path(out) / name).write_text(text, encoding="utf-8")
        print(f"wrote {Path(out) / name} ({len(text.encode('utf-8')):,} bytes)")


# ---------------------------------------------------------------------------------------
# The atlas: the families of Cells' units, asked of a species' catalogue
# ---------------------------------------------------------------------------------------
#
# A unit's families are those the units' table gives it (tools/build_mpneumoniae_atlas.py,
# FAMILIES and UNITS), each with the InterPro signatures that find it. A unit counts as found
# only where a protein carries the signature of a family that makes the machine itself.

# The families of a unit that only go with its machine: a regulator, or a subunit that forms
# no channel or pump by itself. A unit is found where a protein carries the signature of one
# of its other families; a protein with only such a family's signature is no candidate.
ACCESSORY = {"nav_beta", "kv_beta", "cav_beta", "cav_a2d", "bk_beta", "nka_beta", "fxyd", "emre", "micu"}

# The whole note of a unit for which the inventory names no natural gene product.
NOTHING = {
    "U18": "The inventory gives this unit no gene product: it is a default shape of current, not a named channel.",
    "U34": "A background conductance that the inventory ties to no protein.",
    "U35": "A lumped permeability of the whole membrane, not a population of proteins.",
    "U46": "A slot that each model configuration fills with a transporter of its own; it has no fixed protein in any species.",
    "U48": "A protein cage designed in the laboratory, with no gene in any organism, so there is nothing to look for in this one.",
    "U49": "A lumped water permeability of the membrane; water channels (aquaporins) are not part of it.",
}


def find_units(snapshot, entries, filing, human, families_table, units_table, nothing, organism, other_said="", more=None):
    """Each unit of the inventory, asked of a catalogue of one protein for each gene: found,
    built from a different family, or none found, with its note and its products.

    human: the InterPro entries of each human entry (human_signatures); families_table and
    units_table: the units' families and what each unit asks; nothing: the note of a unit for
    which there is nothing to look for; organism: how a note names the species ("the fly");
    other_said: what the note of a different family adds after naming it; more(unit id, its
    families, the finding, the note): the note with what the species adds. Returns the units,
    the units of each protein, and the proteins that carry an accessory family alone."""
    gene = lambda accession: entries[accession]["gene"] or accession
    order = lambda accessions: sorted(set(accessions), key=lambda a: natural(gene(a).lower()))
    by_gene = lambda accessions: [gene(a) for a in order(accessions)]
    carriers = filing.carriers()
    signature_name = lambda signature: filing.names[signature]["name"]
    carried = lambda family: order(accession for signature in family["signatures"] for accession in carriers.get(signature, []))
    said = lambda families: f"{listed(family['of'] for family in families)} ({', '.join(signature for family in families for signature in family['signatures'])})"
    units, unit_of, beside = {}, defaultdict(set), {}
    for unit in snapshot["units"]:
        spec = units_table[unit["id"]]
        if spec.get("finding"):
            units[unit["id"]] = {"finding": spec["finding"], "note": nothing[unit["id"]], "products": []}
            continue
        families = [(key, families_table[key]) for key in spec["parts"]]
        candidates = [product["human_uniprot"] for product in unit.get("products") or [] if product.get("human_uniprot")]
        for _, family in families:
            if family.get("human", True) and not any(set(family["signatures"]) & human.get(candidate, set()) for candidate in candidates):
                raise SystemExit(f"{unit['id']}: none of its human candidates carries the signature of {family['of']}; the question is not the unit's")
        own = [family for key, family in families if key not in ACCESSORY and family.get("human", True)]      # the families the engine's law names
        other = [family for key, family in families if key not in ACCESSORY and not family.get("human", True)]  # another family that makes the same machine
        going_with = [family for key, family in families if key in ACCESSORY]
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
            note = f"{plural(len(hits), 'protein')} of its {len(entries):,} carr{'ies' if len(hits) == 1 else 'y'} the signature of {said(shown)}: {some(by_gene(hits))}. Each is a candidate by its family alone: no source read here says which of them does the unit's work in {organism}."
        elif finding == "different family":
            note = f"None of its {len(entries):,} proteins carries the signature of {said(own)}, the family the engine's law names. {plural(len(hits), 'protein')} carr{'ies' if len(hits) == 1 else 'y'} that of {said(shown)}, the other family this machine is asked for{other_said}: {some(by_gene(hits))}."
        else:
            only = [(family, carried(family)) for family in going_with if carried(family)]
            aside = " ".join(f"{plural(len(found), 'protein')} ({some(by_gene(found))}) carr{'ies' if len(found) == 1 else 'y'} that of {family['of']}, which go with the machine and make none by themselves: no candidate for the unit." for family, found in only)
            note = f"None of its {len(entries):,} proteins carries the signature of {said([*own, *other])}. {aside} The unit's human candidates carry {'them' if len(own) + len(other) > 1 or len(own[0]['signatures']) > 1 else 'it'}, so the search finds the family where it exists.".replace("  ", " ")
            for family, found in only:
                for accession in found:
                    beside[accession] = family["of"]
        if more:
            note = more(unit["id"], families, finding, note)
        units[unit["id"]] = {"finding": finding, "note": note, "products": products}
    if set(units) != {unit["id"] for unit in snapshot["units"]}:
        raise SystemExit("the units of the atlas are not the units of the inventory")
    unit_ids = {accession: sorted(found, key=natural) for accession, found in unit_of.items()}
    return units, unit_ids, beside
