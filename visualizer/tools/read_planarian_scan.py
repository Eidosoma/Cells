#!/usr/bin/env python3
"""Reads the planarian's InterProScan scan into the tree (docs/PLANARIAN_ATLAS.md, "The planarian's own scan").

The atlas's table of the planarian's 18,882 predicted proteins carries, for each line, the InterPro entries
its own source gave it: WormBase ParaSite's older scan for the gene models, UniProt's for its entries. On
18 November 2026 all 18,882 were scanned again on this machine with InterProScan 5.78-109.0, with the member
databases whose terms allow it. This tool turns the scan's outputs into two files of the tree, from which
everything else is made without the scan's folder:

    data/proteins/planarian/interproscan_added.tsv
        one line for each protein that the scan gives an InterPro entry its own column lacks: the entries,
        each with the databases whose signatures reached it. The table's own column is never changed.
    data/proteins/planarian/interproscan.json
        the scan's record: the tool and its release, the day of the run (from the outputs), each file read
        with its SHA-256, and for each database its release as the outputs state it, its terms and class,
        how many of the proteins its pass ran on, what it matched and reached; what the scan confirmed,
        added and did not find of the table, by cause; what each database could see (for any InterPro
        Family entry of the dossier's release, which databases that were run have a signature in it); the
        check of the tool's entry list against the run; the entries dropped because the dossier's release
        does not hold them.

    python3 -I tools/read_planarian_scan.py build --scan SCAN --tool TOOL --datasets DATA
        reads SCAN/out/<pass>/chunk-0N.tsv and .json, SCAN/logs/<pass>.log and SCAN/input/chunk-0N.fasta
        (identifiers only), the tool's entry list (TOOL/work/kvs/idb/entries.json), the atlas's table, the
        dossier's InterPro release and the saved terms pages (both under DATA, each file through its
        folder's MANIFEST), and writes the two files and the note's block. A chunk counts only when both its
        outputs exist and its pass's log says it ended with exit 0. Nothing is written in SCAN.
    python3 -I tools/read_planarian_scan.py note [--check]
        writes (or checks) the block of docs/PLANARIAN_ATLAS.md that gives the record's numbers, from the
        record alone.
    python3 -I tools/read_planarian_scan.py report --datasets DATA [--out FILE]
        what the added entries would change for the two other readers of the table's column: the Protein
        atlas's candidates (tools/build_planarian_atlas.py) and the shelves. It changes no file of the tree.

The matches are the tool's own, with its own cutoffs: nothing is filtered here. A match is one signature on
one protein; the outputs' JSON lists every protein of its input, matched or not (identical sequences once,
with every identifier). Standard library only; the scan's files are read as data.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from lib import proteome_shelves as P  # noqa: E402  the downloads' reader (MANIFEST and SHA-256)

FORMAT = "cells.visualizer.interpro_scan@1"
TABLE = "data/proteins/planarian/predicted_proteins.tsv"
ADDED = "data/proteins/planarian/interproscan_added.tsv"
RECORD = "data/proteins/planarian/interproscan.json"
NOTE = "docs/PLANARIAN_ATLAS.md"
IPR = "human/interpro-entries-tree-and-go"  # the dossier's InterPro release (tools/gather_machines.py reads the same)
TERMS = "planarian/terms-interproscan-member-databases"
ENTRY_LIST = "work/kvs/idb/entries.json"
TOOL_RELEASE = "5.78-109.0"  # the release that was run; every output must say the same
PASSES = ("pass1", "pass1-prints", "pass2-panther")
# The analyses each pass was set to run (18 November 2026): a pass whose log names none yet is taken to run these, so
# that its databases are in the record from the start, run on no protein.
PLANNED = {"pass1": ["Pfam", "SFLD", "HAMAP", "CATH-Gene3D", "NCBIfam", "AntiFam", "CDD", "Coils"], "pass1-prints": ["PRINTS"], "pass2-panther": ["PANTHER"]}
CHUNKS = tuple(f"chunk-{n:02d}" for n in range(1, 7))
BEGIN, END = "<!-- planarian-scan: begin (written by tools/read_planarian_scan.py note) -->", "<!-- planarian-scan: end -->"

# The member databases the scan ran, each under one name, with the other spellings the tool's files use:
# the record's source key, the JSON's signature library, the name in the TSV and the logs, the name in the
# tool's entry list. Coils and AntiFam have no InterPro entries: they enter the record as counts only.
DATABASES = {
    "Pfam": {"key": "pfam", "json": "PFAM", "run": "Pfam", "list": "Pfam"},
    "PRINTS": {"key": "prints", "json": "PRINTS", "run": "PRINTS", "list": "PRINTS"},
    "SFLD": {"key": "sfld", "json": "SFLD", "run": "SFLD", "list": "SFLD"},
    "HAMAP": {"key": "hamap", "json": "HAMAP", "run": "Hamap", "list": "HAMAP"},
    "CATH-Gene3D": {"key": "gene3d", "json": "GENE3D", "run": "Gene3D", "list": "CATH-Gene3D"},
    "NCBIfam": {"key": "ncbifam", "json": "NCBIFAM", "run": "NCBIfam", "list": "NCBIFAM"},
    "PANTHER": {"key": "panther", "json": "PANTHER", "run": "PANTHER", "list": "PANTHER"},
    "CDD": {"key": "cdd", "json": "CDD", "run": "CDD", "list": "CDD"},
    "AntiFam": {"key": "antifam", "json": "ANTIFAM", "run": "AntiFam", "list": "AntiFam", "counts_only": True},
    "Coils": {"key": None, "json": "COILS", "run": "Coils", "list": "COILS", "counts_only": True},
}
BY_JSON = {spec["json"]: name for name, spec in DATABASES.items()}
BY_RUN = {spec["run"]: name for name, spec in DATABASES.items()}

# The sources of the record: each with its terms as read on its provider's page (saved in DATA/TERMS on
# 18 November 2026, checked here by the words given), its class in the terms of tests/licence_classes.test.mjs,
# and its citation where the saved pages give one (None where they do not: left to be filled).
SOURCES = {
    "interpro": {"name": "InterPro", "text": "InterPro: which member database's signature belongs to which InterPro entry, as the tool's own entry list and outputs give it, and the names and types of the entries at the dossier's release", "url": "https://www.ebi.ac.uk/interpro/",
                 "licence": "CC0 1.0 (InterPro's licence page: all of the InterPro, Pfam, PRINTS and SFLD downloadable data is freely available under CC0 1.0 Universal)", "class": "permissive",
                 "terms": ("interpro_license.html", r"All of the InterPro, Pfam, PRINTS and SFLD downloadable data provided on the InterPro website is freely available under CC0 1\.0 Universal"),
                 "citation": "Blum and others (2025) InterPro: the protein sequence classification resource in 2025. Nucleic Acids Res 53:D444-D456.", "citation_from": "the atlas's own list of sources (data/proteins/atlases/planarian.json), from Europe PMC's record of the paper"},
    "pfam": {"name": "Pfam", "text": "Pfam: its signatures (profile hidden Markov models) and the tool's matches of them on the planarian's proteins", "url": "https://www.ebi.ac.uk/interpro/entry/pfam/",
             "licence": "CC0 1.0 (InterPro's licence page; Pfam's own page: freely available under the Creative Commons Zero licence)", "class": "permissive",
             "terms": ("pfam.html", r"Pfam is freely available under the Creative Commons Zero"), "citation": "Paysan-Lafosse and others (2024) The Pfam protein families database: embracing AI/ML. Nucleic Acids Research. doi:10.1093/nar/gkae997. PMID 39540428.", "citation_from": "Pfam's own page on citing it, the first of its latest publications (saved as cite_pfam_citing.html)"},
    "prints": {"name": "PRINTS", "text": "PRINTS: its fingerprints and the tool's matches of them on the planarian's proteins", "url": "https://www.ebi.ac.uk/interpro/entry/prints/",
               "licence": "CC0 1.0 (InterPro's licence page)", "class": "permissive",
               "terms": ("interpro_license.html", r"InterPro, Pfam, PRINTS and SFLD downloadable data provided on the InterPro website is freely available under CC0"), "citation": "Attwood and others (2012) The PRINTS database: a fine-grained protein sequence annotation and analysis resource - its status in 2012. Database (Oxford) 2012:bas019. doi:10.1093/database/bas019. PMID 22508994.", "citation_from": "InterPro's page on PRINTS (saved as cite_interpro_prints.html)"},
    "sfld": {"name": "SFLD", "text": "SFLD (the Structure-Function Linkage Database): its signatures and the tool's matches of them on the planarian's proteins", "url": "https://www.ebi.ac.uk/interpro/entry/sfld/",
             "licence": "CC0 1.0 (InterPro's licence page)", "class": "permissive",
             "terms": ("interpro_license.html", r"InterPro, Pfam, PRINTS and SFLD downloadable data provided on the InterPro website is freely available under CC0"), "citation": None, "citation_asked": "InterPro's page on SFLD names no publication (saved as cite_interpro_sfld.html)"},
    "hamap": {"name": "HAMAP", "text": "HAMAP (SIB Swiss Institute of Bioinformatics): its family profiles and the tool's matches of them on the planarian's proteins", "url": "https://hamap.expasy.org/",
              "licence": "CC BY 4.0 (HAMAP's own page: distributed under the Creative Commons Attribution (CC BY 4.0) License)", "class": "permissive",
              "terms": ("hamap_about.html", r"distributed under the Creative Commons Attribution \(CC BY 4\.0\) License"),
              "citation": "HAMAP in 2015: updates to the protein family classification and annotation system. Nucleic Acids Res. 43:D1064-D1070 (2015).", "citation_from": "HAMAP's own page, which asks for it in these words"},
    "gene3d": {"name": "CATH-Gene3D", "text": "CATH-Gene3D: its domain models and the tool's matches of them on the planarian's proteins", "url": "https://www.cathdb.info/",
               "licence": "CC BY 4.0 (CATH's own pages: the CATH Protein Structure Classification Database is licensed under a Creative Commons Attribution 4.0 International License)", "class": "permissive",
               "terms": ("cath_license.html", r"is licensed under a Creative Commons Attribution 4\.0 International License"), "citation": None, "citation_asked": "CATH's licence page names the database's authors and no paper, and its publications page gave no text that could be read (saved as cite_cath_publications.html)"},
    "ncbifam": {"name": "NCBIfam", "text": "NCBIfam (NCBI, with TIGRFAMs): its protein family models and the tool's matches of them on the planarian's proteins; named as NCBIfam's wherever they are used", "url": "https://www.ncbi.nlm.nih.gov/genome/annotation_prok/evidence/",
                "licence": "CC BY-SA 4.0 (share-alike), as NCBI's page on TIGRFAMs states: TIGRFAMs data are made available under a Creative Commons Attribution-ShareAlike 4.0 license", "class": "permissive",
                "terms": ("ncbi_tigrfams.html", r"TIGRFAMs data are made available under a Creative Commons Attribution-ShareAlike 4\.0 license"),
                "citation": "Li W, O'Neill KR, Haft DH and others (2021) RefSeq: expanding the Prokaryotic Genome Annotation Pipeline reach with protein family model curation. Nucleic Acids Res 49(D1):D1020-D1028. PMID 33270901.", "citation_from": "NCBI's page on TIGRFAMs, which asks for the most recent publication describing NCBI's Prokaryotic Genome Annotation Pipeline and lists this one first among its references"},
    "panther": {"name": "PANTHER", "text": "PANTHER: its family models and the tool's matches of them on the planarian's proteins; named as PANTHER's wherever they are used", "url": "https://www.pantherdb.org/",
                "licence": "CC BY 4.0 for its data and data products, as PANTHER's terms page states; the page was read in a browser on 18 November 2026, its site refusing automated reads; its models as distributed with InterProScan may be copied and redistributed freely in accordance with InterPro's copyright agreement", "class": "permissive",
                "terms": ("panther_terms_from_browser.txt", r"PANTHER data and data products are licensed under the Creative Commons Attribution 4\.0 International License"), "citation": None, "citation_asked": "PANTHER's site refuses automated reads, and its terms page, read in a browser, names no paper"},
    "cdd": {"name": "CDD", "text": "CDD (NCBI's Conserved Domain Database): its domain models and the tool's matches of them on the planarian's proteins; named as CDD's wherever they are used", "url": "https://www.ncbi.nlm.nih.gov/Structure/cdd/cdd.shtml",
            "licence": "No open licence stated: CDD's own page states no terms, and NCBI's policies page none for CDD itself; it was decided on 18 November 2026 that a database whose provider states no terms may be used for this scan where it is publicly available", "class": "no stated terms",
            "absent": ("ncbi_cdd.html", r"(?i)licen[cs]e|terms of use|copyright|creative commons"), "citation": None, "citation_asked": "NCBI's help page for CDD lists a section on citing it, whose text is not in the saved page (cite_cdd_help.html)"},
    "antifam": {"name": "AntiFam", "text": "AntiFam: its models of spurious protein predictions, counted only (it has no InterPro entries)", "url": "https://www.ebi.ac.uk/interpro/",
                "licence": "CC0 1.0 (InterPro's page on AntiFam: freely available under the Creative commons Zero (CC0) licence)", "class": "permissive",
                "terms": ("interpro_antifam.html", r"AntiFam is freely available under the Creative commons Zero \(CC0\) licence"),
                "citation": "Ruth Y Eberhardt, Dan Haft, Marco Punta, Maria Martin, Claire O'Donovan, Alex Bateman. (2012) AntiFam: A tool to help identify spurious ORFs in protein annotation. Database:bas003. PMID: 22434837.", "citation_from": "InterPro's page on AntiFam, which asks for it in these words"},
}
TOOL = {"name": "InterProScan", "by": "EMBL-EBI", "licence": "Apache License 2.0", "is": "the tool that ran the databases' signatures on the proteins, not a database: it is named here and not classed as a source",
        "url": "https://interproscan-docs.readthedocs.io/en/v5/", "terms": ("interproscan5_howtorun.html", r"The InterProScan software itself is provided under the Apache License, Version 2\.0"), "citation": "Jones and others (2014) InterProScan 5: genome-scale protein function classification. Bioinformatics. PMID 24451626.", "citation_from": "InterPro's page on citing it and InterProScan's own (saved as cite_interpro_citing.html and cite_interproscan_citing.html)"}
COILS_TERMS = "The program ncoils (GNU General Public License, as the terms folder's note records): a program, not a database, with no InterPro entries; only its counts are kept"
LEFT_OUT = "PROSITE and SMART (not free to commercial users), SUPERFAMILY (a registration with its staff), PIRSF and PIRSR (PIR asks commercial users to inform it and report yearly), MobiDB-lite (it bundles a program under an academic licence agreement), FunFam (not needed), and SignalP, TMHMM and Phobius (vendors' licences)"

START = re.compile(r"^\S+ (?P<label>\S+) (?P<chunk>chunk-\d+): start \((?P<n>\d+) sequences; (?P<analyses>[^;]+);")
EXIT = re.compile(r"^\S+ (?P<label>\S+) (?P<chunk>chunk-\d+): exit (?P<code>\d+) after ")
OTHER = re.compile(r"^\S+ (?P<label>\S+) (?P<chunk>chunk-\d+): (?P<what>done before, skipped|stopped\b)")


class Breach(SystemExit):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def table_name(path: Path) -> str:
    """The table as the record names it: by its place in the tree (a test's own table by its place there)."""
    path = path.resolve()
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.name


def natural(identifier):
    return P.natural(identifier)


# ---------------------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------------------

def read_table(path: Path):
    """The atlas's table: each line's id, kind and own InterPro entries, in the table's order."""
    raw = path.read_bytes()
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8")), delimiter="\t"))
    own = {row["id"]: {e.strip() for e in (row.get("interpro") or "").split(";") if e.strip()} for row in rows}
    if len(own) != len(rows):
        raise Breach("two lines of the table share an id")
    return [row["id"] for row in rows], own, {row["id"]: row.get("kind") for row in rows}, sha256(raw)


def read_list(tool: Path):
    """The tool's own entry list, read once: each member signature's database and the InterPro entry it is
    integrated in, and each InterPro entry's type. Only these are kept of the file."""
    path = tool / ENTRY_LIST
    raw = path.read_bytes()
    entries = json.loads(raw)
    signatures, interpro = {}, {}
    for accession, item in entries.items():
        if item.get("database") == "InterPro":
            interpro[accession] = item.get("type")
        else:
            signatures[accession] = (item.get("database"), item.get("integrated"))
    del entries
    by_entry = defaultdict(set)
    for accession, (database, integrated) in signatures.items():
        if integrated:
            by_entry[integrated].add(database)
    return {"signatures": signatures, "interpro": interpro, "by_entry": by_entry, "sha256": sha256(raw), "highest": max(interpro) if interpro else None}


def read_logs(scan: Path):
    """Each chunk's state in each pass's log, the last word standing: a chunk is 'done' when its last start
    is followed by 'exit 0' (a later 'done before, skipped' keeps it so), with the analyses of that start."""
    state, read = {}, []
    for label in PASSES:
        path = scan / "logs" / f"{label}.log"
        if not path.exists():
            continue
        raw = path.read_bytes()
        read.append({"file": f"logs/{label}.log", "sha256": sha256(raw)})
        for line in raw.decode("utf-8").splitlines():
            for pattern in (START, EXIT, OTHER):
                found = pattern.match(line)
                if found:
                    break
            else:
                continue
            if found.group("label") != label:
                raise Breach(f"logs/{label}.log has a line of another pass: {line[:80]}")
            key = (label, found.group("chunk"))
            prior = state.get(key, {"state": None, "analyses": None, "sequences": None})
            if pattern is START:
                analyses = [a.strip() for a in found.group("analyses").split(",")]
                unknown = [a for a in analyses if a not in BY_RUN]
                if unknown:
                    raise Breach(f"logs/{label}.log names analyses this tool does not know: {unknown}")
                state[key] = {"state": "running", "analyses": [BY_RUN[a] for a in analyses], "sequences": int(found.group("n"))}
            elif pattern is EXIT:
                state[key] = {**prior, "state": "done" if found.group("code") == "0" and prior["state"] == "running" else f"exit {found.group('code')}"}
            elif found.group("what").startswith("stopped"):
                state[key] = {**prior, "state": "stopped"}
            # 'done before, skipped' leaves the state as it was
    return state, read


def fasta_ids(path: Path):
    ids = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.startswith(">"):
                ids.append(line[1:].split()[0])
    return ids


def read_output(scan: Path, label: str, chunk: str, analyses):
    """One chunk's outputs: its proteins (by identifier), its matches, its days, and the TSV's pairs."""
    base = scan / "out" / label / chunk
    json_raw, tsv_raw = (base.with_suffix(".json")).read_bytes(), (base.with_suffix(".tsv")).read_bytes()
    data = json.loads(json_raw)
    proteins, matches = [], []
    for result in data["results"]:
        ids = [x["id"] for x in result.get("xref") or []]
        proteins += ids
        for match in result.get("matches") or []:
            signature = match["signature"]
            library = signature["signatureLibraryRelease"]["library"]
            if library not in BY_JSON:
                raise Breach(f"out/{label}/{chunk}.json: a match of a library this tool does not know: {library}")
            name = BY_JSON[library]
            if name not in analyses:
                raise Breach(f"out/{label}/{chunk}.json: a match of {name}, which the log does not name for the chunk")
            entry = signature.get("entry") or {}
            for protein in ids:
                matches.append((protein, name, signature["accession"], entry.get("accession"), signature["signatureLibraryRelease"].get("version")))
    days, tsv_pairs = set(), set()
    for line in tsv_raw.decode("utf-8").splitlines():
        columns = line.split("\t")
        if len(columns) < 11:
            continue
        if columns[3] not in BY_RUN:
            raise Breach(f"out/{label}/{chunk}.tsv: an analysis this tool does not know: {columns[3]}")
        day = re.fullmatch(r"(\d{2})-(\d{2})-(\d{4})", columns[10])
        if not day:
            raise Breach(f"out/{label}/{chunk}.tsv: the date column reads {columns[10]!r}")
        days.add(f"{day.group(3)}-{day.group(2)}-{day.group(1)}")
        tsv_pairs.add((columns[0], BY_RUN[columns[3]], columns[4], columns[11] if len(columns) > 11 and columns[11].startswith("IPR") else None))
    files = [{"file": f"out/{label}/{chunk}.json", "sha256": sha256(json_raw)}, {"file": f"out/{label}/{chunk}.tsv", "sha256": sha256(tsv_raw)}]
    return {"proteins": proteins, "matches": matches, "days": days, "tsv_pairs": tsv_pairs, "version": data.get("interproscan-version"), "files": files}


# ---------------------------------------------------------------------------------------
# The record
# ---------------------------------------------------------------------------------------

def build_record(scan: Path, tool: Path, datasets: str, table_path: Path):
    d = P.Datasets(datasets)
    names = P.read_entry_names(d, IPR)
    release = re.search(r"Release ([\d.]+),", d.text(IPR, "release_notes.txt")).group(1)
    for key, source in SOURCES.items():
        if "terms" in source:
            P.holds(d, TERMS, source["terms"][0], source["terms"][1])
        if "absent" in source and re.search(source["absent"][1], P.plain(d.text(TERMS, source["absent"][0]))):
            raise Breach(f"{TERMS}/{source['absent'][0]} now states terms; read it again and class {source['name']} anew")
    P.holds(d, TERMS, TOOL["terms"][0], TOOL["terms"][1])
    terms_day = d.day(TERMS, TOOL["terms"][0])
    order, own, kinds, table_sha = read_table(table_path)
    table_ids = set(order)
    listing = read_list(tool)
    state, logs = read_logs(scan)

    files, versions, days = [], set(), set()
    run_on = defaultdict(set)              # database -> proteins its pass ran on
    covered = defaultdict(set)             # protein -> databases run on it
    passes = {}
    per = {name: {"matches": 0, "matched": set(), "signatures": set(), "entries": set(), "without_entry": 0, "release": set()} for name in DATABASES}
    found = defaultdict(lambda: defaultdict(set))   # protein -> entry -> databases
    pairs = defaultdict(set)               # signature -> the entries the outputs give it (None for none)
    tsv_differences = 0
    for label in PASSES:
        counted, analyses_seen = [], []
        for chunk in CHUNKS:
            item = state.get((label, chunk))
            base = scan / "out" / label / chunk
            exists = base.with_suffix(".tsv").exists() and base.with_suffix(".json").exists()
            if item and item["analyses"] and item["analyses"] not in analyses_seen:
                analyses_seen.append(item["analyses"])
            if not (item and item["state"] == "done" and exists):
                continue
            out = read_output(scan, label, chunk, item["analyses"])
            wanted = fasta_ids(scan / "input" / f"{chunk}.fasta")
            if sorted(out["proteins"]) != sorted(wanted) or len(wanted) != item["sequences"]:
                raise Breach(f"out/{label}/{chunk}.json does not list every protein of input/{chunk}.fasta once")
            stray = [p for p in out["proteins"] if p not in table_ids]
            if stray:
                raise Breach(f"out/{label}/{chunk}.json names proteins the table lacks: {stray[:3]}")
            files += out["files"]
            versions.add(out["version"])
            days |= out["days"]
            counted.append(chunk)
            for name in item["analyses"]:
                run_on[name].update(out["proteins"])
                for protein in out["proteins"]:
                    covered[protein].add(name)
            json_pairs = set()
            for protein, name, signature, entry, version in out["matches"]:
                row = per[name]
                row["matches"] += 1
                row["matched"].add(protein)
                row["signatures"].add(signature)
                row["release"].add(version)
                pairs[signature].add(entry)
                json_pairs.add((protein, name, signature, entry))
                if entry:
                    row["entries"].add(entry)
                    found[protein][entry].add(name)
                else:
                    row["without_entry"] += 1
            tsv_differences += len(json_pairs ^ out["tsv_pairs"])
        passes[label] = {"analyses": analyses_seen[-1] if analyses_seen else PLANNED[label], "analyses_from": "the log's start lines" if analyses_seen else "the pass as it was set to run: its log names none yet",
                         "chunks_counted": counted, "chunks": len(CHUNKS)}
    if versions - {TOOL_RELEASE}:
        raise Breach(f"the outputs are of another release of the tool than {TOOL_RELEASE}: {sorted(versions)}")

    # The check of the tool's entry list against the run: every signature-to-entry pair of the outputs.
    differences, not_listed = [], []
    for signature, entries in sorted(pairs.items()):
        listed = listing["signatures"].get(signature)
        if listed is None:
            not_listed.append(signature)
        elif entries != {listed[1]}:
            differences.append([signature, sorted(e or "none" for e in entries), listed[1]])

    # What the scan confirmed, added and did not find of each line.
    added, dropped = {}, defaultdict(int)
    confirmed = pairs_added = 0
    for protein in order:
        mine = found.get(protein, {})
        confirmed += sum(1 for e in mine if e in own[protein])
        gain = {}
        for entry, names_ in mine.items():
            if entry in own[protein]:
                continue
            if entry not in names:
                dropped[entry] += 1
                continue
            gain[entry] = sorted(names_)
        if gain:
            added[protein] = dict(sorted(gain.items()))
            pairs_added += len(gain)
    raw_of = {name: spec["list"] for name, spec in DATABASES.items()}
    missed = Counter()
    for protein in order:
        if not covered.get(protein):
            continue
        ran = {raw_of[name] for name in covered[protein]}
        for entry in own[protein] - set(found.get(protein, {})):
            if entry not in listing["interpro"]:
                missed["not_in_the_tools_list"] += 1
            elif not (listing["by_entry"].get(entry, set()) & ran):
                missed["no_database_run_has_a_signature"] += 1
            else:
                missed["a_database_run_has_one_and_did_not_match"] += 1
    only = Counter()
    for gain in added.values():
        for entry, names_ in gain.items():
            if len(names_) == 1:
                only[names_[0]] += 1

    # What the scan could see: for each InterPro Family entry of the dossier's release, which databases that
    # were run have a signature in it, by the tool's list. Each database keeps the shorter of its list and
    # its complement, both within the stated universe; an entry the tool's list lacks has no signature there.
    universe = sorted(a for a, v in names.items() if v["type"] == "Family")
    run_names = [name for name in DATABASES if not DATABASES[name].get("counts_only") and any(name in (p["analyses"] or []) for p in passes.values())]
    could_see = {}
    for name in run_names:
        with_ = [f for f in universe if raw_of[name] in listing["by_entry"].get(f, ())]
        if len(with_) <= len(universe) - len(with_):
            could_see[name] = {"with": " ".join(with_)}
        else:
            have = set(with_)
            could_see[name] = {"without": " ".join(f for f in universe if f not in have)}

    proteins = len(order)
    databases = {}
    for name, spec in DATABASES.items():
        if not any(name in (p["analyses"] or []) for p in passes.values()):
            continue
        row = per[name]
        label = next(label for label, p in passes.items() if name in (p["analyses"] or []))
        item = {"pass": label, "release": (sorted(row["release"])[0] if len(row["release"]) == 1 else (sorted(row["release"]) or None)),
                "release_from": "the outputs' JSON (signatureLibraryRelease)" if row["release"] else "no output of a counted chunk holds a match of it, so the outputs state no release",
                "proteins_run": len(run_on[name]), "of": proteins, "on_every_protein": run_on[name] == table_ids,
                "matches": row["matches"], "proteins_matched": len(row["matched"]), "signatures": len(row["signatures"])}
        if spec.get("counts_only"):
            item["counts_only"] = True
            item.update({"source": spec["key"]} if spec["key"] else {"terms": COILS_TERMS})
        else:
            item.update({"entries_reached": len(row["entries"]), "matches_without_entry": row["without_entry"], "source": spec["key"],
                         "added": sum(1 for gain in added.values() for names_ in gain.values() if name in names_), "added_by_it_alone": only[name]})
        databases[name] = item

    sources = {}
    for key, source in SOURCES.items():
        if key != "interpro" and not any(item.get("source") == key for item in databases.values()):
            continue
        out = {field: source[field] for field in ("name", "text", "url", "licence", "class", "citation") if field in source}
        for field in ("citation_from", "citation_asked"):
            if source.get(field):
                out[field] = source[field]
        file = (source.get("terms") or source.get("absent"))[0]
        out["terms_read"] = f"{file}, saved in {TERMS} ({d.day(TERMS, file)})"
        sources[key] = out

    day_list = sorted(days)
    record = {
        "format": FORMAT,
        "species": "planarian",
        "note": ("Generated by tools/read_planarian_scan.py from the scan's outputs, the tool's own entry list, the atlas's table and the dossier's InterPro release: do not edit. "
                 "The entries the scan added are in data/proteins/planarian/interproscan_added.tsv; the table's own column is unchanged. "
                 "Not plainly permissive: NCBIfam (CC BY-SA 4.0, share-alike) and CDD (no stated terms, used by the decision of 18 November 2026 that a database whose provider states no terms may be used for this scan where it is publicly available). "
                 "Each entry keeps the databases that found it, so that entries found by NCBIfam alone or by CDD alone can be counted or taken out without a new scan. docs/PLANARIAN_ATLAS.md says what the scan is."),
        "tool": {**{k: v for k, v in TOOL.items() if k != "terms"}, "release": TOOL_RELEASE, "release_from": "every output's JSON (interproscan-version)" if versions else "the release that was run: no output is counted yet", "terms_read": f"{TOOL['terms'][0]}, saved in {TERMS} ({terms_day})",
                 "options": "the lookup service of precalculated matches switched off (-dp); InterPro entries and Gene Ontology terms added to each match (-iprlookup, -goterms); outputs tsv and json"},
        "run": {"days": day_list, "days_from": "the date column of the outputs' TSV lines", "proteins": proteins, "chunks": len(CHUNKS),
                "table": {"file": table_name(table_path), "sha256": table_sha}, "passes": passes, "left_out": LEFT_OUT,
                "counted": "a chunk counts only when both its outputs exist and its pass's log says it ended with exit 0; a match is one signature on one protein, as the tool found it, with its own cutoffs"},
        "read": {"outputs": files, "logs": logs, "entry_list": {"file": f"{ENTRY_LIST} of InterProScan {TOOL_RELEASE}", "sha256": listing["sha256"], "highest_entry": listing["highest"]}},
        "databases": databases,
        "entries": {
            "confirmed": confirmed, "added": pairs_added, "proteins_gaining": len(added),
            "added_by_ncbifam_alone": only["NCBIfam"], "added_by_cdd_alone": only["CDD"],
            "dropped_not_in_dossier_release": {"pairs": sum(dropped.values()), "entries": len(dropped), "which": sorted(dropped)[:100], "release": release, "why": "an entry the dossier's InterPro release does not hold is dropped, and counted here (the first hundred named)"},
            "table_entries_not_found": {"pairs": sum(missed.values()), **{k: missed[k] for k in ("no_database_run_has_a_signature", "a_database_run_has_one_and_did_not_match", "not_in_the_tools_list")},
                                        "of": "the table's own entries on the proteins at least one counted pass ran on, by cause: no database run on the protein has a signature in the entry (by the tool's list); one has and did not match; the entry is not in the tool's list"},
            "as_pairs": "each count is of pairs of a protein and an InterPro entry",
        },
        "could_see": {"universe": f"the InterPro entries of the type Family in the dossier's release ({release}), {len(universe)} entries", "release": release, "family_entries": len(universe),
                      "rule": "for each database that was run, the Family entries in which the tool's entry list has a signature of it ('with'), or those in which it has none ('without'), whichever is shorter, as accessions parted by spaces; an entry that the tool's list does not hold has no signature of any database",
                      "databases": could_see},
        "check_of_the_list": {"pairs": len(pairs), "differences": len(differences), "not_in_the_list": len(not_listed), "of": "every signature of the outputs, with the InterPro entry the outputs give it, against the tool's own entry list", **({"listed": differences[:20]} if differences else {})},
        "tsv_and_json_differ": tsv_differences,
        "sources": sources,
    }
    return record, added


def added_text(added):
    lines = ["id\tadded"]
    for protein in sorted(added, key=natural):
        lines.append(protein + "\t" + ";".join(f"{entry}:{','.join(names)}" for entry, names in added[protein].items()))
    return "\n".join(lines) + "\n"


def read_added(path: Path):
    """The added entries as gather_machines.py and the tests read them: {id: {entry: [databases]}}."""
    out = {}
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "id\tadded":
        raise Breach(f"{path.name}: not a table of added entries")
    for line in lines[1:]:
        protein, field = line.split("\t")
        out[protein] = {item.split(":")[0]: item.split(":")[1].split(",") for item in field.split(";")}
    return out


def dumps(data):
    return json.dumps(data, indent=1, ensure_ascii=False) + "\n"


PATHS = re.compile(r"/(?:home|mnt|Users|tmp)/")
CLOCK = re.compile(r"\d{2}:\d{2}:\d{2}|T\d{2}:\d{2}")


# ---------------------------------------------------------------------------------------
# The note's block: the record's numbers, from the record alone
# ---------------------------------------------------------------------------------------

def note_block(record):
    run, entries = record["run"], record["entries"]
    days = run["days"]
    when = (days[0] if len(days) == 1 else f"{days[0]} to {days[-1]}") if days else "no chunk counted yet"
    lines = [BEGIN, "",
             f"The record as built ({when}; {len(record['read']['outputs'])} output files read). The full run replaces these numbers; the record's own count of proteins per database is what keeps a partial build truthful.", "",
             "| Pass | Chunks counted | Databases |", "| --- | --- | --- |"]
    for label, p in run["passes"].items():
        lines.append(f"| `{label}` | {len(p['chunks_counted'])} of {p['chunks']}{' (' + ', '.join(p['chunks_counted']) + ')' if p['chunks_counted'] else ''} | {', '.join(p['analyses'])}{'' if p['analyses_from'].startswith('the log') else ' (not started)'} |")
    lines += ["", "| Database | Release (outputs) | Proteins run on | Matches | Proteins matched | Entries reached | Matches with no entry | Added | Added by it alone |", "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for name, item in record["databases"].items():
        release = item["release"] if isinstance(item["release"], str) else ("not stated" if not item["release"] else ", ".join(item["release"]))
        cells = [f"{item['proteins_run']:,} of {item['of']:,}"] + [f"{item[k]:,}" if isinstance(item.get(k), int) else "" for k in ("matches", "proteins_matched", "entries_reached", "matches_without_entry", "added", "added_by_it_alone")]
        lines.append(f"| {name}{' (counts only)' if item.get('counts_only') else ''} | {release} | " + " | ".join(cells) + " |")
    missed = entries["table_entries_not_found"]
    lines += ["",
              f"- Entries confirmed (a protein's own entry found again): {entries['confirmed']:,}; added: {entries['added']:,}, on {entries['proteins_gaining']:,} proteins; added by NCBIfam alone: {entries['added_by_ncbifam_alone']:,}; by CDD alone: {entries['added_by_cdd_alone']:,}.",
              f"- Dropped because the dossier's InterPro release ({entries['dropped_not_in_dossier_release']['release']}) does not hold them: {entries['dropped_not_in_dossier_release']['pairs']:,} ({entries['dropped_not_in_dossier_release']['entries']:,} {'entry' if entries['dropped_not_in_dossier_release']['entries'] == 1 else 'entries'}).",
              f"- The table's own entries the scan did not find, on the proteins a counted pass ran on: {missed['pairs']:,}; no database run on the protein has a signature in the entry: {missed['no_database_run_has_a_signature']:,}; one has and did not match: {missed['a_database_run_has_one_and_did_not_match']:,}; not in the tool's list: {missed['not_in_the_tools_list']:,}.",
              f"- The tool's entry list against the run: {record['check_of_the_list']['pairs']:,} signatures compared, {record['check_of_the_list']['differences']} differences, {record['check_of_the_list']['not_in_the_list']} not in the list.",
              "", END]
    return "\n".join(lines)


def put_note(text, record):
    block = note_block(record)
    if BEGIN not in text or END not in text:
        raise Breach(f"{NOTE} has no block for the scan's numbers ({BEGIN} ... {END})")
    head, rest = text.split(BEGIN, 1)
    return head + block + rest.split(END, 1)[1]


# ---------------------------------------------------------------------------------------
# Part 3: what the added entries would change for the atlas's candidates and the shelves (a report)
# ---------------------------------------------------------------------------------------

def report(datasets, out=None):
    import build_planarian_atlas as A  # the atlas tool's own tables and rules, read and not changed
    record = json.loads((ROOT / RECORD).read_text(encoding="utf-8"))
    order, own, kinds, _ = read_table(ROOT / TABLE)
    added = read_added(ROOT / ADDED)
    union = {i: own[i] | set(added.get(i, {})) for i in order}
    atlas = json.loads((ROOT / "data/proteins/atlases/planarian.json").read_text(encoding="utf-8"))
    # The atlas's products, by family key: the unit's part (role, key) holds the products of that role.
    products = defaultdict(set)
    for unit_id, unit in atlas["units"].items():
        spec = A.UNITS.get(unit_id, {})
        for role, key in spec.get("parts", []):
            for product in unit.get("products") or []:
                if product["role"] == role:
                    products[key].update(item["id"] for item in product["ids"])
    joined = {}  # a UniProtKB line's gene model (the table's match column), so a gain is not counted twice
    for row in csv.DictReader(io.StringIO((ROOT / TABLE).read_text(encoding="utf-8")), delimiter="\t"):
        if row["db"] == "uniprot" and row.get("match"):
            joined[row["id"]] = row["match"]

    def carriers(key, signatures_of):
        family = A.FAMILIES[key]
        out_ = set()
        for i in order:
            have = signatures_of[i]
            first = next((s for s in family["signatures"] if s in have), None)
            if first and not any(s in have for s in family.get("without", [])):
                out_.add(i)
        return out_

    families = {}
    for key, family in A.FAMILIES.items():
        before, after = carriers(key, own), carriers(key, union)
        gained = sorted(after - before - products[key], key=natural)
        lost = sorted((before - after) | {i for i in products[key] if i in union and any(s in union[i] for s in family.get("without", []))}, key=natural)
        second = sorted({i for i in order for s in family.get("second", []) if s in union[i] and s not in own[i]}, key=natural)
        families[key] = {"name": family["name"], "signatures": family["signatures"], "by_column": len(before), "by_column_and_scan": len(after), "atlas_products": len(products[key]),
                         "gained": gained, "gained_by": {i: sorted({db for s in family["signatures"] for db in added.get(i, {}).get(s, [])}) for i in gained}, "lost": lost, "second_signature_gained": second}
    units = {}
    for unit_id, spec in A.UNITS.items():
        finding = atlas["units"][unit_id]["finding"]
        keys = [key for _, key in spec.get("parts", [])] + ([spec["replaces"]] if spec.get("replaces") else [])
        gain = sorted({i for key in keys for i in families[key]["gained"]}, key=natural)
        loss = sorted({i for key in keys for i in families[key]["lost"]}, key=natural)
        if gain or loss:
            units[unit_id] = {"finding": finding, "families": keys, "gained": gain, "lost": loss,
                              "would": ("gain a finding" if finding in ("none found", "different family") and gain else "change its products")}
    # The counts the units' notes give: every number in a note that equals a family's count of gene models today.
    counts = []
    for unit_id, unit in atlas["units"].items():
        spec = A.UNITS.get(unit_id, {})
        for _, key in spec.get("parts", []):
            item = families[key]
            models_now = sum(1 for i in products[key] if kinds.get(i) == "gene model")
            models_then = models_now + sum(1 for i in item["gained"] if kinds.get(i) == "gene model") - sum(1 for i in item["lost"] if kinds.get(i) == "gene model")
            if models_then != models_now and re.search(rf"\b{models_now}\b", unit["note"]):
                counts.append({"unit": unit_id, "family": key, "gene_models_now": models_now, "gene_models_with_scan": models_then, "note": unit["note"][:160]})
    # The shelves: each protein's family (or part of 'No family assigned') by the shelves' own rule, from the
    # column and from the column with the added entries; first checked to give back the members' table.
    d = P.Datasets(datasets)
    names = P.read_entry_names(d, IPR)
    parent = P.read_hierarchy(d, "planarian/interpro-hierarchy-and-go")

    def filed(signatures_of):
        shelf = type("Rows", (), {})()
        shelf.rows = [[None, i, None, None, None, None, ";".join(sorted(signatures_of[i]))] for i in order]
        shelf.kind = lambda a: names.get(a, {}).get("type")
        shelf.parent = parent
        shelf.depth = lambda a: A.Shelves.depth(shelf, a)
        shelf.broader = lambda a: A.Shelves.broader(shelf, a)
        A.Shelves.file_proteins(shelf)
        return {i: shelf.family.get(i) or f"no family: {shelf.part[i]}" for i in order}

    members = {row["id"]: row["under"] for row in csv.DictReader(io.StringIO((ROOT / "data/proteins/planarian/shelf_members.tsv").read_text(encoding="utf-8")), delimiter="\t")}
    now, then = filed(own), filed(union)
    as_members = {i: (v if not v.startswith("no family: ") else v[len("no family: "):]) for i, v in now.items()}
    agree = sum(1 for i in order if as_members[i] == members.get(i))
    moved = [i for i in order if now[i] != then[i]]
    gained_any = {i for i in order if union[i] != own[i]}
    shelves = {"reproduces_members_table": f"{agree:,} of {len(order):,} proteins filed as the members' table files them", "change_shelf": len(moved),
               "change_shelf_and_gained_an_entry": sum(1 for i in moved if i in gained_any), "change_shelf_and_gained_nothing": sum(1 for i in moved if i not in gained_any),
               "leave_no_family_assigned": sum(1 for i in moved if now[i].startswith("no family") and not then[i].startswith("no family")),
               "enter_no_family_assigned": sum(1 for i in moved if then[i].startswith("no family") and not now[i].startswith("no family")),
               "within_no_family_assigned": sum(1 for i in moved if now[i].startswith("no family") and then[i].startswith("no family")),
               "no_family_assigned_now": sum(1 for v in now.values() if v.startswith("no family")), "no_family_assigned_with_scan": sum(1 for v in then.values() if v.startswith("no family"))}
    # The other reading of "unplaced": the side "not known" (basis none) of the members' table. Of the shelves' steps, only
    # the place by function reads a protein's signatures (InterPro's Gene Ontology terms, with every broader term), and an
    # added entry can only add places. So a protein not placed today is placed by function with the scan at most where its
    # added entries' places alone leave no real doubt (the shelves' own rule), and exactly so where its own terms name none.
    sides = {row["id"]: (row["side"], row["basis"]) for row in csv.DictReader(io.StringIO((ROOT / "data/proteins/planarian/shelf_members.tsv").read_text(encoding="utf-8")), delimiter="\t")}
    ad = A.Datasets(Path(datasets) / "planarian")
    go_of = A.read_family_terms(ad)
    up, usable = A.broader_terms(A.read_ontology(ad)[0])
    unplaced = [i for i in order if sides.get(i) == ("not known", "none")]
    placeable = Counter({"placed inside by function, at most": 0, "placed outside by function, at most": 0})
    for i in unplaced:
        if not added.get(i):
            continue
        placeable["gain_an_entry"] += 1
        found = set()
        for entry in added[i]:
            for term in go_of.get(entry, []):
                if usable(term):
                    found |= up(usable(term))
        side = A.side_from_where([key for key, term, _ in A.WHERE if term in found])
        if side:
            placeable[f"placed {side} by function, at most"] += 1
    shelves["not_placed"] = {"now": len(unplaced), "gain_an_entry": placeable.pop("gain_an_entry", 0), **dict(sorted(placeable.items())),
                             "how": "the members' table's side 'not known' (basis none); an upper bound, since a protein's own terms (and its joined entries') can name a place that keeps the doubt"}
    rests = {label: p["chunks_counted"] for label, p in record["run"]["passes"].items()}
    result = {"rests_on": rests, "proteins_run": {name: item["proteins_run"] for name, item in record["databases"].items()},
              "atlas": {"units": units, "counts_in_notes": counts, "families": {k: v for k, v in families.items() if v["gained"] or v["lost"] or v["second_signature_gained"]}}, "shelves": shelves}
    text = dumps(result)
    if out:
        Path(out).write_text(text, encoding="utf-8")
    print(text if not out else f"wrote {out}")
    return 0


# ---------------------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("step", choices=["build", "note", "report"])
    parser.add_argument("--scan", help="the scan's folder (read only)")
    parser.add_argument("--tool", help="the tool's unpacked folder, which holds its entry list")
    parser.add_argument("--datasets", help="the datasets folder: the dossier's InterPro release and the saved terms pages")
    parser.add_argument("--table", default=str(ROOT / TABLE), help="the atlas's table (a test gives another)")
    parser.add_argument("--out", help="build: a folder for the two files instead of the tree (no note is written then); report: a file")
    parser.add_argument("--check", action="store_true", help="note: fail if the block is not what the record gives")
    args = parser.parse_args(argv)
    if args.step == "note":
        record = json.loads((ROOT / RECORD).read_text(encoding="utf-8"))
        text = (ROOT / NOTE).read_text(encoding="utf-8")
        new = put_note(text, record)
        if args.check:
            print("the note's block is the record's" if new == text else "the note's block is not the record's: run note", file=sys.stderr)
            return 0 if new == text else 1
        (ROOT / NOTE).write_text(new, encoding="utf-8")
        return 0
    if args.step == "report":
        if not args.datasets:
            parser.error("report needs --datasets")
        return report(args.datasets, args.out)
    if not (args.scan and args.tool and args.datasets):
        parser.error("build needs --scan, --tool and --datasets")
    record, added = build_record(Path(args.scan), Path(args.tool), args.datasets, Path(args.table))
    text = dumps(record)
    if PATHS.search(text) or CLOCK.search(text):
        raise Breach("the record would name a path of this machine or a clock time")
    folder = Path(args.out) if args.out else ROOT
    target_record, target_added = (folder / Path(RECORD).name, folder / Path(ADDED).name) if args.out else (ROOT / RECORD, ROOT / ADDED)
    target_record.write_text(text, encoding="utf-8")
    target_added.write_text(added_text(added), encoding="utf-8")
    if not args.out:
        (ROOT / NOTE).write_text(put_note((ROOT / NOTE).read_text(encoding="utf-8"), record), encoding="utf-8")
    counted = {label: len(p["chunks_counted"]) for label, p in record["run"]["passes"].items()}
    print(f"wrote {target_record.name} ({len(text.encode()):,} bytes) and {target_added.name} ({len(added):,} proteins gain {record['entries']['added']:,} entries); chunks counted: {counted}; "
          f"databases on every protein: {[n for n, i in record['databases'].items() if i['on_every_protein']]}; list differences: {record['check_of_the_list']['differences']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
