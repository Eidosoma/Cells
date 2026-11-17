#!/usr/bin/env python3
"""Gathers the evidence for the Machines catalogue (schema/MACHINE_DOSSIERS.md).

For each species and each machine that data/catalogue/gather.json looks for, it writes a dossier
into data/catalogue/dossiers/<species>.json: the machine's proteins as the species' own proteins
in the Protein atlas (by the atlas's own identifier), how each was found, how many of them the
atlas holds, the Protein Data Bank entry a size can be measured from (its parts by entity ids, in
the terms of tools/measure_particle.py --machine), how many a cell holds where an open paper gives
a number, and every source with its licence. It also writes, for each protein, the machines it is
a part of, which is what the atlas needs to say "part of" on a protein.

    python3 -I tools/gather_machines.py fetch ecoli --datasets DATA
        asks RCSB's search and data services and the PDB archive for what is not yet saved, into
        folders of this tool's own under DATA/<species>/ (each with a MANIFEST.json: address, time,
        SHA-256, and the body of a POST beside its answer). The only step that uses the network.
    python3 -I tools/gather_machines.py build --datasets DATA
        reads only DATA (every file checked against its MANIFEST), the species' own proteins and
        gather.json, and writes the dossiers: the same bytes every time.
    python3 -I tools/gather_machines.py check --datasets DATA
        fails if a dossier on disk is not what build would write.

The rules, said once (and in each dossier):
- A protein is named with a machine where its reviewed UniProt entry carries the machine's Gene
  Ontology term or a narrower one (by the ontology's is_a and part_of links). Where gather.json
  gives UniProt keywords for the machine, only an entry that also carries one of them is a part
  by that rule; the others are "named with it". Nothing is matched by a name.
- A Protein Data Bank entry is a candidate where one of its polymer entities is, by RCSB's mapping,
  one of those proteins and its source organism is of the species. Candidates are ranked (each
  dossier's rules.structure says it in full): the machine's proteins present; then measurable (their
  residues with coordinates add up to at least 70 per cent of them); then 4.5 Å or better; then the
  fewest other polymer entities; then the proteins at least 80 per cent whole; then whole-protein
  equivalents; then resolution; then copies assembled; then the entry id. The first is chosen,
  unless gather.json names another and says why.
- Tiers: "part", a protein named with the machine (by the term, and the keyword where one is
  given) that the chosen entry holds as an entity of the species, or a protein of the species in a
  seed entry; "part by keyword", one named with it that carries the keyword and that the entry does
  not hold; "named", one named with it by the term alone. A protein of the species that the entry
  holds and the ontology does not name with the machine is counted under the structure and left
  out of the measure. An entry of another organism names no protein of the species.

Requests carry a generic client name and nothing about who asks. Standard library only; nothing
of the engine is read or run.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from lib import proteome_shelves as P  # noqa: E402  the downloads' reader (MANIFEST and SHA-256) and the ontology's reader

CONFIG = ROOT / "data" / "catalogue" / "gather.json"
OUT = ROOT / "data" / "catalogue" / "dossiers"
FORMAT = "cells.visualizer.machine_dossiers@1"
CONFIG_FORMAT = "cells.visualizer.machine_gather@1"
TOOL = "tools/gather_machines.py"
MINE = "the visualizer's machines-gathering agent (G)"
CLIENT = "data-client/1.0"
GO = "human/geneontology-go-basic"
UNIPROT_TERMS = ("human/uniprot-docs-and-terms", "terms_uniprot_license.json")
PDB_TERMS = ("ecoli/wwpdb-terms", "wwpdb_usage_policies.html")
SEARCH = "https://search.rcsb.org/rcsbsearch/v2/query"
UNIPROT = "https://rest.uniprot.org/uniprotkb/stream"
KEYWORDS_FILE = "uniprotkb_reviewed_keywords.tsv.gz"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
GRAPHQL = "https://data.rcsb.org/graphql"
FILES = "https://files.rcsb.org/download"
BATCH = 20          # entries per question to the data service
WHOLE = 0.8         # a protein counts as whole in an entry where at least this share of its residues has coordinates
MEASURABLE = 0.7    # an entry can give a size where its proteins' residues with coordinates add up to at least this share of them
FINE = 4.5          # an entry at this resolution or better, in ångströms, is ranked before a coarser one with as many of the proteins
PATHS = re.compile(r"/(?:home|mnt|Users|tmp)/")
WORDS = re.compile(r"\b(modelled|modeled|qualified|judged|simulated)\b", re.I)

ENTRY_QUERY = """query($ids:[String!]!){entries(entry_ids:$ids){rcsb_id struct{title} exptl{method}
 rcsb_entry_info{resolution_combined deposited_polymer_entity_instance_count polymer_entity_count}
 rcsb_accession_info{initial_release_date}
 assemblies{rcsb_id pdbx_struct_assembly{details oligomeric_count} pdbx_struct_assembly_gen{asym_id_list oper_expression}}
 polymer_entities{rcsb_polymer_entity{pdbx_description} entity_poly{type rcsb_sample_sequence_length}
  rcsb_entity_source_organism{ncbi_taxonomy_id ncbi_scientific_name taxonomy_lineage{id}}
  rcsb_polymer_entity_container_identifiers{entity_id asym_ids auth_asym_ids reference_sequence_identifiers{database_name database_accession}}
  polymer_entity_instances{rcsb_polymer_entity_instance_container_identifiers{asym_id auth_asym_id} rcsb_polymer_instance_feature_summary{type count coverage}}}}}"""


class Breach(SystemExit):
    pass


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


# ---------------------------------------------------------------------------------------
# What gather.json asks
# ---------------------------------------------------------------------------------------

def load_config():
    config = read_json(CONFIG)
    if config.get("format") != CONFIG_FORMAT:
        raise Breach(f"{rel(CONFIG)} is not {CONFIG_FORMAT}")
    kinds = {kind["id"]: kind for kind in config["kinds"]}
    if len(kinds) != len(config["kinds"]):
        raise Breach("a kind is listed twice in gather.json")
    for species, block in config["species"].items():
        seen = set()
        for machine in block["machines"]:
            if machine["kind"] not in kinds:
                raise Breach(f"{species}: no kind {machine['kind']}")
            if machine["kind"] in seen:
                raise Breach(f"{species}: {machine['kind']} is listed twice")
            seen.add(machine["kind"])
            if not (machine.get("go") or machine.get("seed")):
                raise Breach(f"{species}, {machine['kind']}: neither a Gene Ontology term nor a seed entry names its proteins")
    return config, kinds


# ---------------------------------------------------------------------------------------
# The species' own proteins: UniProt's entries, the ontology, the atlas
# ---------------------------------------------------------------------------------------

class Proteome:
    """The species' reviewed UniProt entries (names, genes, keywords, Gene Ontology terms) and the
    atlas's own table, read from the saved copies through their MANIFESTs."""

    def __init__(self, d, species, block, ontology):
        kb, proteome = block["uniprot"]["folder"], block["uniprot"]["proteome"]
        self.kb, self.proteome = kb, proteome
        self.places = f"uniprotkb_{proteome}_reviewed_places.json.gz"
        self.signatures = f"uniprotkb_{proteome}_reviewed_signatures.tsv.gz"
        raw = json.loads(d.text(kb, self.places))["results"]
        self.release = d.entry(kb, self.places).get("x_uniprot_release")
        if d.entry(kb, self.signatures).get("x_uniprot_release") != self.release:
            raise Breach(f"{species}: the two UniProt downloads are not of one release")
        self.entries = {}
        for item in raw:
            names = item.get("proteinDescription", {}).get("recommendedName", {}).get("fullName", {}).get("value")
            gene = next((g["geneName"]["value"] for g in item.get("genes") or [] if g.get("geneName")), None)
            self.entries[item["primaryAccession"]] = {"gene": gene, "name": names, "keywords": sorted({k["name"] for k in item.get("keywords") or []})}
        self.keywords_from = None
        extra = block["uniprot"].get("keywords")
        if extra:
            rows = list(csv.reader(d.text(extra, KEYWORDS_FILE).splitlines(), delimiter="\t"))
            column = rows[0].index("Keywords")
            said = {row[0]: sorted({k.strip() for k in row[column].split(";") if k.strip()}) for row in rows[1:]}
            for accession, item in self.entries.items():
                if item["keywords"]:
                    raise Breach(f"{species}: the saved entries give keywords already; {extra} is not needed")
                item["keywords"] = said.get(accession, [])
            self.keywords_from = {"folder": extra, "file": KEYWORDS_FILE, "release": d.entry(extra, KEYWORDS_FILE).get("x_uniprot_release")}
        self.terms = {}
        rows = list(csv.reader(d.text(kb, self.signatures).splitlines(), delimiter="\t"))
        column = rows[0].index("Gene Ontology IDs")
        for row in rows[1:]:
            self.terms[row[0]] = [t.strip() for t in row[column].split(";") if t.strip()]
        table = ROOT / "data" / "proteins" / species / "proteins.tsv"
        self.atlas_file = rel(table)
        self.atlas = {row["id"]: row for row in csv.DictReader(io.StringIO(table.read_text(encoding="utf-8")), delimiter="\t")}
        self.ontology = ontology
        self.lengths = {accession: int(row["length"]) for accession, row in self.atlas.items() if (row.get("length") or "").isdigit()}

    def gene(self, accession):
        row = self.atlas.get(accession)
        return (row or {}).get("gene") or (self.entries.get(accession) or {}).get("gene") or accession

    def label(self, accession):
        row = self.atlas.get(accession)
        return (row or {}).get("name") or (self.entries.get(accession) or {}).get("name")

    def marked(self, term):
        """The entries that carry the term or a narrower one, each with the terms it carries that put it there."""
        up, usable = self.ontology["up"], self.ontology["usable"]
        out = {}
        for accession, terms in self.terms.items():
            via = sorted({u for u in (usable(t) for t in terms) if u and term in up(u)})
            if via:
                out[accession] = via
        return out


def load_ontology(d):
    terms, version = P.read_ontology(d, GO)
    up, usable = P.broader_terms(terms)
    return {"terms": terms, "version": version, "up": up, "usable": usable, "name": lambda t: terms[t]["name"]}


# ---------------------------------------------------------------------------------------
# A machine's proteins by the ontology and the keywords
# ---------------------------------------------------------------------------------------

def named_proteins(proteome, machine):
    """{accession: {"go": [terms that put it there], "keyword": [keywords of the machine it carries]}}"""
    found = {}
    for term in machine.get("go") or []:
        if proteome.ontology["usable"](term) != term:
            raise Breach(f"{machine['kind']}: {term} is not a current term of the ontology")
        for accession, via in proteome.marked(term).items():
            found.setdefault(accession, {"go": [], "keyword": []})
            found[accession]["go"] = sorted(set(found[accession]["go"]) | set(via))
    for accession, item in found.items():
        item["keyword"] = [k for k in machine.get("keyword") or [] if k in proteome.entries[accession]["keywords"]]
    return found


# ---------------------------------------------------------------------------------------
# The Protein Data Bank: the search, the data service's answers, the entries' own files
# ---------------------------------------------------------------------------------------

def search_body(accessions, lineage_taxon):
    """RCSB's search: experimental entries with a polymer entity mapped to one of the accessions,
    from an organism under the species' taxon, best resolution first."""
    return {
        "query": {"type": "group", "logical_operator": "and", "nodes": [
            {"type": "terminal", "service": "text", "parameters": {"attribute": "rcsb_polymer_entity_container_identifiers.reference_sequence_identifiers.database_accession", "operator": "in", "value": sorted(accessions)}},
            {"type": "terminal", "service": "text", "parameters": {"attribute": "rcsb_polymer_entity_container_identifiers.reference_sequence_identifiers.database_name", "operator": "exact_match", "value": "UniProt"}},
            {"type": "terminal", "service": "text", "parameters": {"attribute": "rcsb_entity_source_organism.taxonomy_lineage.id", "operator": "exact_match", "value": str(lineage_taxon)}},
        ]},
        "return_type": "entry",
        "request_options": {"results_content_type": ["experimental"], "sort": [{"sort_by": "rcsb_entry_info.resolution_combined", "direction": "asc"}], "return_all_hits": True},
    }


def oper_count(expression):
    """How many operators an assembly's operator expression applies: '1', '1,2', '(1-6)', '(1-6)(7,8)'."""
    total = 1
    groups = re.findall(r"\(([^)]*)\)", expression) or [expression]
    for group in groups:
        n = 0
        for piece in group.split(","):
            piece = piece.strip()
            if "-" in piece:
                a, b = piece.split("-")
                n += int(b) - int(a) + 1
            elif piece:
                n += 1
        total *= max(n, 1)
    return total


def entry_facts(entry, lineage_taxon):
    """One candidate entry as the data service gives it: its entities with organism, accession,
    copies in the deposited model and in its first assembly, and the share of residues with
    coordinates."""
    entities = []
    first = (entry.get("assemblies") or [None])[0]
    in_assembly = Counter()
    if first:
        for gen in first.get("pdbx_struct_assembly_gen") or []:
            times = oper_count(gen["oper_expression"])
            listed = gen["asym_id_list"] if isinstance(gen["asym_id_list"], list) else gen["asym_id_list"].split(",")
            for asym in listed:
                in_assembly[asym.strip()] += times
    for item in entry.get("polymer_entities") or []:
        ids = item["rcsb_polymer_entity_container_identifiers"]
        refs = [r["database_accession"] for r in ids.get("reference_sequence_identifiers") or [] if r["database_name"] == "UniProt"]
        organisms = item.get("rcsb_entity_source_organism") or []
        lineage = {int(level["id"]) for organism in organisms for level in organism.get("taxonomy_lineage") or [] if str(level["id"]).isdigit()}
        shares = []
        for instance in item.get("polymer_entity_instances") or []:
            missing = sum(f.get("coverage") or 0 for f in instance.get("rcsb_polymer_instance_feature_summary") or [] if f["type"] == "UNOBSERVED_RESIDUE_XYZ")
            shares.append(round(1 - missing, 3))
        entities.append({
            "id": ids["entity_id"], "description": item["rcsb_polymer_entity"]["pdbx_description"], "type": item["entity_poly"]["type"],
            "length": item["entity_poly"]["rcsb_sample_sequence_length"], "accessions": refs,
            "organism": "; ".join(sorted({o["ncbi_scientific_name"] for o in organisms if o.get("ncbi_scientific_name")})) or None,
            "taxa": sorted({o["ncbi_taxonomy_id"] for o in organisms if o.get("ncbi_taxonomy_id")}),
            "same_organism": lineage_taxon in lineage, "chains": ids.get("auth_asym_ids") or [],
            "copies": len(ids.get("asym_ids") or []), "copies_in_assembly": sum(in_assembly[a] for a in ids.get("asym_ids") or []) if first else None,
            "observed_share": min(shares) if shares else None,
        })
    entities.sort(key=lambda e: int(e["id"]))
    resolution = (entry.get("rcsb_entry_info") or {}).get("resolution_combined") or [None]
    deposited = (entry.get("rcsb_entry_info") or {}).get("deposited_polymer_entity_instance_count")
    assembly_count = (first or {}).get("pdbx_struct_assembly", {}).get("oligomeric_count") if first else None
    in_first = sum(e["copies_in_assembly"] or 0 for e in entities) if first else None
    return {
        "entry": entry["rcsb_id"], "title": (entry.get("struct") or {}).get("title"), "method": "; ".join(m["method"] for m in entry.get("exptl") or []),
        "resolution_A": resolution[0], "released": ((entry.get("rcsb_accession_info") or {}).get("initial_release_date") or "")[:10],
        "deposited_chains": deposited, "assembly_chains": in_first,
        "assembly_differs": bool(first) and in_first != deposited, "assembly_details": (first or {}).get("pdbx_struct_assembly", {}).get("details") if first else None,
        "entities": entities, "oligomeric_count": assembly_count,
    }


def share_of_protein(entity, lengths):
    """The share of the protein's own length (its UniProt entry's) that has coordinates in every
    copy: the entity's sequence length times the share of it with coordinates (RCSB's count of
    residues without coordinates), over the entry's length, at most 1."""
    length = max((lengths.get(a) or 0 for a in entity["accessions"]), default=0)
    if not length or entity["observed_share"] is None:
        return None
    return round(min(1.0, entity["length"] * entity["observed_share"] / length), 3)


def score(facts, wanted, lengths):
    """How a candidate ranks: the machine's proteins present, those of them nearly whole, the
    copies of them assembled, the other polymer entities, resolution, id."""
    present, whole = set(), set()
    others = copies = 0
    share = {}
    for entity in facts["entities"]:
        hit = [a for a in entity["accessions"] if a in wanted] if entity["same_organism"] else []
        if hit:
            present.update(hit)
            copies += entity["copies_in_assembly"] or entity["copies"]
            got = share_of_protein(entity, lengths) or 0
            for accession in hit:
                share[accession] = max(share.get(accession, 0), got)
            if got >= WHOLE:
                whole.update(hit)
        else:
            others += 1
    resolution = facts["resolution_A"] if facts["resolution_A"] is not None else 99.0
    equivalents = round(sum(share.values()), 2)
    return {"present": len(present), "whole": len(whole), "equivalents": equivalents, "copies": copies, "others": others, "resolution_A": facts["resolution_A"],
            "key": (-len(present), equivalents < MEASURABLE * len(present), resolution > FINE, others, -len(whole), -round(equivalents), resolution, -copies, facts["entry"])}


def read_cif_tables(path: Path, wanted=("_entity.", "_entity_poly.", "_struct_ref.")):
    """The few mmCIF tables this tool reads (entity, entity_poly, struct_ref), from an untrusted file:
    a plain tokenizer, standard library only; it stops at the atom records."""
    text = gzip.decompress(path.read_bytes()).decode("utf-8", errors="replace")
    lines = text.splitlines()
    tables = defaultdict(list)
    i, n = 0, len(lines)

    def tokens(chunk):
        out, j = [], 0
        while j < len(chunk):
            c = chunk[j]
            if c.isspace():
                j += 1
            elif c in "'\"":
                k = j + 1
                while k < len(chunk) and not (chunk[k] == c and (k + 1 == len(chunk) or chunk[k + 1].isspace())):
                    k += 1
                out.append(chunk[j + 1:k])
                j = k + 1
            else:
                k = j
                while k < len(chunk) and not chunk[k].isspace():
                    k += 1
                out.append(chunk[j:k])
                j = k
        return out

    def values_from(start):
        """Tokens from line `start` on, with ;-delimited text fields, until the next tag, loop or block."""
        out, j = [], start
        while j < n:
            line = lines[j]
            if line.startswith(";"):
                field = [line[1:]]
                j += 1
                while j < n and not lines[j].startswith(";"):
                    field.append(lines[j])
                    j += 1
                out.append("\n".join(field).strip())
                j += 1
                continue
            stripped = line.strip()
            if stripped.startswith("_") or stripped.startswith("loop_") or stripped.startswith("#") or stripped.startswith("data_"):
                break
            out.extend(tokens(line))
            j += 1
        return out, j

    while i < n:
        line = lines[i].strip()
        if line.startswith("_atom_site.") or (line == "loop_" and i + 1 < n and lines[i + 1].startswith("_atom_site.")):
            break
        if line == "loop_":
            j = i + 1
            names = []
            while j < n and lines[j].startswith("_"):
                names.append(lines[j].strip())
                j += 1
            category = names[0].split(".")[0] + "." if names else ""
            values, j = values_from(j)
            if category in wanted and names:
                width = len(names)
                for k in range(0, len(values) - width + 1, width):
                    tables[category].append({name.split(".", 1)[1]: values[k + m] for m, name in enumerate(names)})
            i = j
            continue
        if line.startswith("_") and line.split(".")[0] + "." in wanted:
            category = line.split(".")[0] + "."
            row = {}
            while i < n and lines[i].strip().startswith(category):
                parts = tokens(lines[i].strip())
                key = parts[0].split(".", 1)[1]
                if len(parts) > 1:
                    row[key] = parts[1]
                    i += 1
                else:
                    values, i = values_from(i + 1)
                    row[key] = values[0] if values else ""
            tables[category].append(row)
            continue
        i += 1
    return tables


# ---------------------------------------------------------------------------------------
# Saved answers
# ---------------------------------------------------------------------------------------

def rcsb_files(block, kind):
    folder = block["rcsb"]
    return folder, f"search_{kind}.json", f"search_{kind}.body.json"


def saved_candidates(d, block, kind):
    folder, answer, _ = rcsb_files(block, kind)
    found = json.loads(d.text(folder, answer))
    ids = [row["identifier"] for row in found.get("result_set") or []]
    return ids, found.get("total_count", 0), d.day(folder, answer)


def saved_entries(d, block, kind, ids):
    folder = block["rcsb"]
    out = {}
    for k in range(0, len(ids), BATCH):
        answer = json.loads(d.text(folder, f"entries_{kind}_{k // BATCH:02d}.json"))
        if answer.get("errors"):
            raise Breach(f"{folder}/entries_{kind}_{k // BATCH:02d}.json holds errors: {answer['errors'][:1]}")
        for entry in answer["data"]["entries"]:
            out[entry["rcsb_id"]] = entry
    return out


def held_file(d, datasets, entry, assembly, pinned=None, own=None):
    """Where the chosen entry's file is saved: the folder gather.json pins, else this tool's own
    folder for the machine, else any folder under the datasets whose MANIFEST lists it."""
    name = f"{entry}-assembly1.cif.gz" if assembly else f"{entry}.cif.gz"
    for folder in (pinned, own):
        if folder and (Path(datasets) / folder / "MANIFEST.json").exists() and any(item.get("name") == name for item in read_json(Path(datasets) / folder / "MANIFEST.json").get("files") or []):
            return name, [folder]
    if pinned:
        raise Breach(f"gather.json pins {pinned} for {name}, and it does not hold it")
    hits = []
    for manifest in sorted(Path(datasets).glob("*/*/MANIFEST.json")):
        try:
            listed = read_json(manifest)
        except (OSError, ValueError):
            continue
        if any(item.get("name") == name for item in listed.get("files") or []):
            hits.append(f"{manifest.parent.parent.name}/{manifest.parent.name}")
    return name, hits


# ---------------------------------------------------------------------------------------
# One machine's dossier
# ---------------------------------------------------------------------------------------

def dossier(d, datasets, config, kinds, species, block, machine, proteome, sources, by_protein):
    kind = kinds[machine["kind"]]
    lineage_taxon, lineage_name = block["lineage"]
    out = {"kind": kind["id"], "label": machine.get("label") or kind["label"], "group": kind["group"], "group_proposed": kind["group"] in {g["id"] for g in config["groups_proposed"]}}
    if kind.get("plain"):
        out["plain"] = kind["plain"]
    named = named_proteins(proteome, machine) if machine.get("go") else {}
    keyworded = {a for a, item in named.items() if item["keyword"]} if machine.get("keyword") else set(named)
    # The candidates and the chosen entry.
    ids, total, day = saved_candidates(d, block, kind["id"])
    facts = {i: entry_facts(e, lineage_taxon) for i, e in saved_entries(d, block, kind["id"], ids).items()}
    seed_set = set()
    if machine.get("seed"):
        seed = facts.get(machine["seed"])
        if not seed:
            raise Breach(f"{species}, {kind['id']}: the seed entry {machine['seed']} is not among the saved answers")
        seed_set = {a for e in seed["entities"] if e["same_organism"] for a in e["accessions"] if a in proteome.entries}
        keyworded = set(seed_set)
        machine = {**machine, "keyword": None}
    wanted = set(named) | seed_set
    ranked = sorted(facts.values(), key=lambda f: score(f, keyworded or wanted, proteome.lengths)["key"])
    if not ranked:
        raise Breach(f"{species}, {kind['id']}: no candidate entry was found")
    chosen = ranked[0]
    if machine.get("entry"):
        chosen = facts[machine["entry"]["id"]]
    if machine.get("structure") is False:
        chosen = {"entities": []}
    # The proteins, by tier.
    in_entry = {}
    for entity in chosen["entities"]:
        if entity["same_organism"]:
            for accession in entity["accessions"]:
                in_entry.setdefault(accession, []).append(entity["id"])
    rows, tiers = [], Counter()
    every = sorted(set(named) | seed_set | {a for a in in_entry if a in proteome.entries or a in proteome.atlas}, key=lambda a: (P.natural(proteome.gene(a).lower()), a))
    for accession in every:
        item = named.get(accession, {"go": [], "keyword": []})
        entities = in_entry.get(accession, [])
        if seed_set:
            tier = "part" if accession in seed_set else ("named" if accession in named else "in entry only")
        elif accession in named and accession in keyworded and entities:
            tier = "part"
        elif accession in named and accession in keyworded and machine.get("keyword"):
            tier = "part by keyword"
        elif accession in named:
            tier = "named"
        else:
            tier = "in entry only"
        tiers[tier] += 1
        rows.append([accession, proteome.gene(accession), proteome.label(accession), tier, item["go"], item["keyword"], entities, accession in proteome.atlas])
        if tier in ("part", "part by keyword"):
            by_protein[accession].append({"machine": kind["id"], "tier": tier})
    # A protein of the species that the entry holds and the ontology does not name with the machine is
    # no protein of it: it stands with the structure, counted, and is left out of the measure.
    entry_only = [{"id": r[0], "gene": r[1], "label": r[2], "entities": r[6], "in_atlas": r[7]} for r in rows if r[3] == "in entry only"]
    rows = [r for r in rows if r[3] != "in entry only"]
    tiers.pop("in entry only", None)
    out["proteins"] = {"columns": ["id", "gene", "label", "tier", "go", "keyword", "entities", "in_atlas"], "rows": rows, "counts": dict(sorted(tiers.items()))}
    out["join"] = {
        "atlas": proteome.atlas_file, "by": "the atlas's id: a UniProt accession",
        "parts": sum(1 for r in rows if r[3] in ("part", "part by keyword")), "parts_in_atlas": sum(1 for r in rows if r[3] in ("part", "part by keyword") and r[7]),
        "held_by_entry": sum(1 for r in rows if r[3] == "part"),
        "all": len(rows), "all_in_atlas": sum(1 for r in rows if r[7]),
        "not_in_atlas": [r[0] for r in rows if not r[7]],
    }
    terms = machine.get("go") or []
    out["named"] = {
        "by": "Gene Ontology" if terms else "Protein Data Bank entry",
        "terms": [[t, proteome.ontology["name"](t)] for t in terms],
        "keyword": machine.get("keyword") or [],
        "seed": machine.get("seed"),
        "count": len(named) if terms else len(seed_set),
        "seed_text": f"The parts are the proteins of the species in Protein Data Bank entry {machine['seed']}: {len(seed_set)}." if machine.get("seed") else None,
        "text": (f"{len(named)} of the species' reviewed UniProt entries carry the Gene Ontology's term " + " or ".join(f"{proteome.ontology['name'](t)} ({t})" for t in terms) + " or a narrower one" + (f"; {len(keyworded)} of them also carry UniProt's keyword " + " or ".join(machine['keyword']) if machine.get('keyword') else "") + ".")
        if terms else f"{len(seed_set)} of the species' proteins are the entities of Protein Data Bank entry {machine['seed']} from the species; no term of the Gene Ontology names this machine's proteins in the saved entries.",
        "sources": (["uniprot", "go"] if terms else ["uniprot"]) + ([f"pdb{machine['seed'].lower()}"] if machine.get("seed") else []),
    }
    if machine.get("seed"):
        sources[f"pdb{machine['seed'].lower()}"] = pdb_source(facts[machine["seed"]])
    # The structure.
    if machine.get("structure") is False:
        out["structure"] = None
        out["no_structure"] = machine["why"]
        return out
    out["structure"] = structure(d, datasets, machine, chosen, ranked, total, day, proteome, named, keyworded, seed_set, block, sources)
    out["structure"]["in_entry_only"] = {"count": len(entry_only), "note": "Proteins of the species that the entry holds and the ontology does not name with the machine: left out of the measure.", "proteins": entry_only}
    return out


def pdb_source(facts):
    how = f"{facts['method'].capitalize()}, {facts['resolution_A']} Å" if facts["method"] and facts["resolution_A"] is not None else (facts["method"].capitalize() if facts["method"] else "RCSB's record of the entry gives no experimental method and no resolution")
    return {"text": f"Protein Data Bank entry {facts['entry']}: {facts['title']}. {how}.", "url": f"https://www.rcsb.org/structure/{facts['entry']}", "licence": "CC0 1.0", "class": "permissive"}


def structure(d, datasets, machine, chosen, ranked, total, day, proteome, named, keyworded, seed_set, block, sources):
    wanted = keyworded or set(named) | seed_set
    use_assembly = chosen["assembly_differs"]
    name, held = held_file(d, datasets, chosen["entry"], use_assembly, machine.get("held"), f"{block['species_id']}/wwpdb-{machine['kind']}-g")
    entities = []
    parts = defaultdict(list)
    exclude = []
    rna = {str(k): v for k, v in (machine.get("rna_entities") or {}).get(chosen["entry"], {}).items()}
    for entity in chosen["entities"]:
        accessions = [a for a in entity["accessions"]] if entity["same_organism"] else []
        mine = [a for a in accessions if a in wanted]
        with_it = [a for a in accessions if a in named and a not in wanted]
        if mine:
            role = "part"
            group = part_name(machine, mine[0], proteome, named)
        elif with_it:
            role = "named with it"
            group = proteome.gene(with_it[0])
        elif entity["id"] in rna:
            if rna[entity["id"]]["description"] != entity["description"]:
                raise Breach(f"{chosen['entry']} entity {entity['id']} is {entity['description']!r}, not {rna[entity['id']]['description']!r} as gather.json says")
            role = "part (RNA)" if entity["same_organism"] else "part (RNA, of another organism by the entry's record)"
            group = rna[entity["id"]]["part"]
        else:
            role = "left out: " + ("a nucleic acid" if "polypeptide" not in entity["type"] else ("another organism's protein" if not entity["same_organism"] else "a protein of the species not named with the machine"))
            group = None
        if group:
            parts[group].append(entity["id"])
        else:
            exclude.append(entity["id"])
        entities.append({
            "id": entity["id"], "description": entity["description"], "type": entity["type"], "accessions": entity["accessions"],
            "gene": proteome.gene(accessions[0]) if accessions else None, "organism": entity["organism"], "same_organism": entity["same_organism"],
            "copies": entity["copies"], "copies_in_assembly": entity["copies_in_assembly"], "with_coordinates": entity["observed_share"], "of_protein": share_of_protein(entity, proteome.lengths) if accessions else None, "role": role, "part": group,
        })
    # Check the entities against the file's own tables where the file is saved.
    checked = None
    if held:
        folder = held[0]
        tables = read_cif_tables(d.path(folder, name))
        own = defaultdict(list)
        for row in tables["_struct_ref."]:
            if row.get("db_name") == "UNP":
                own[row.get("entity_id")].append(row.get("pdbx_db_accession"))
        described = {row.get("id"): row.get("pdbx_description") for row in tables["_entity."]}
        for entity in entities:
            if entity["id"] not in described:
                raise Breach(f"{chosen['entry']}: the file has no entity {entity['id']}")
            entity["file_reference"] = sorted(own.get(entity["id"], [])) or None
            entity["file_agrees"] = None if not entity["accessions"] else bool(set(entity["accessions"]) & set(entity["file_reference"] or []))
        checked = f"{folder}/{name}"
    calls = [f"--part {group}={','.join(ids)}" for group, ids in parts.items()]
    frame = machine.get("frame")
    if frame and not all(f in parts for f in frame):
        frame = None
    file_at = checked or f"(to fetch) {name}"
    call = " ".join(["python3 -I tools/measure_particle.py --machine", f"DATASETS/{file_at}" if checked else name] + ([f"--exclude {','.join(exclude)}"] if exclude else []) + calls + ([f"--frame-from {frame[0]} --frame-to {frame[1]}"] if frame else []) + ["--out OUT.json"])
    key = f"pdb{chosen['entry'].lower()}"
    sources[key] = pdb_source(chosen)
    present = score(chosen, wanted, proteome.lengths)
    measurable = present["present"] > 0 and not present["equivalents"] < MEASURABLE * present["present"]
    ranks = {f["entry"]: k + 1 for k, f in enumerate(ranked)}
    compare = []
    for other in machine.get("compare") or []:
        found = next((f for f in ranked if f["entry"] == other["id"]), None)
        compare.append({"entry": other["id"], "by": other["by"], "rank": ranks.get(other["id"]), "of": len(ranked), **({k: v for k, v in score(found, wanted, proteome.lengths).items() if k != "key"} if found else {"note": "not among the saved candidates"})})
    return {
        "entry": chosen["entry"], "title": chosen["title"], "method": chosen["method"] or None, "resolution_A": chosen["resolution_A"], "released": chosen["released"],
        "organism": "; ".join(sorted({e["organism"] for e in entities if e["same_organism"] and e["organism"]})) or None,
        "same_organism": any(e["same_organism"] for e in entities),
        "measurable": measurable,
        "measurable_says": (f"It holds {present['present']} of the {len(wanted)} proteins sought, and their residues with coordinates add up to {present['equivalents']} whole proteins." + ("" if measurable else f" That is less than {int(MEASURABLE * 100)} per cent of the proteins it holds: no size of the machine should be read from it.")),
        "compared": compare,
        "whole": {"proteins_wanted": len(wanted), "present": present["present"], "nearly_whole": present["whole"], "equivalents": present["equivalents"], "copies": present["copies"], "rule": f"a protein is nearly whole where the entity's residues with coordinates (RCSB's count of residues without coordinates, in every copy) are at least {int(WHOLE * 100)} per cent of its UniProt entry's length"},
        "file": checked, "file_to_fetch": None if checked else name, "assembly": chosen["assembly_details"] if use_assembly else None,
        "assembly_note": (f"The deposited model holds {chosen['deposited_chains']} chains and the first biological assembly {chosen['assembly_chains']}: measure the assembly's file." if use_assembly else f"The deposited model and the first biological assembly hold the same {chosen['deposited_chains']} chains: measure the entry's own file."),
        "entities": entities,
        "measure": {"exclude": exclude, "parts": {g: ids for g, ids in parts.items()}, "frame": frame, "call": call},
        "chosen_by": machine["entry"]["why"] if machine.get("entry") else "first by the rule",
        "candidates": [{"entry": f["entry"], "method": f["method"], "resolution_A": f["resolution_A"], **{k: v for k, v in score(f, wanted, proteome.lengths).items() if k != "key"}} for f in ranked[:6]],
        "search": {"asked": day, "hits": total, "read": len(ranked), "file": f"{block['rcsb']}/search_{machine['kind']}.json"},
        "sources": [key],
    }


def part_name(machine, accession, proteome, named):
    """The part a protein's entity is measured in: by the machine's sub-terms or keywords where
    gather.json gives them, else by the protein's own gene."""
    by = machine.get("parts_by") or {}
    for part, term in (by.get("go") or {}).items():
        if any(term in proteome.ontology["up"](via) for via in named.get(accession, {}).get("go", [])):
            return part
    for part, keyword in (by.get("keyword") or {}).items():
        if keyword in proteome.entries.get(accession, {}).get("keywords", []):
            return part
    return re.sub(r"[^A-Za-z0-9_-]", "_", proteome.gene(accession))


# ---------------------------------------------------------------------------------------
# How many a cell holds: numbers from open papers, each found where gather.json says
# ---------------------------------------------------------------------------------------

def paper_files(key, paper):
    return f"{key}_record.json", f"{key}_fulltext.xml"


def paragraphs(xml_text):
    """The body's paragraphs of a saved JATS full text, each with the titles of the sections it
    stands in and its number within its section (from 1). The file is untrusted: it is parsed as
    data with the standard library and nothing in it is followed."""
    root = ET.fromstring(xml_text)
    body = root.find(".//body")
    out = []

    def text(element):
        return re.sub(r"\s+", " ", "".join(element.itertext())).strip()

    def walk(element, trail):
        n = 0
        for child in element:
            if child.tag == "sec":
                title = child.find("title")
                walk(child, trail + [text(title) if title is not None else ""])
            elif child.tag == "p":
                n += 1
                out.append((" > ".join(trail), n, text(child)))
    if body is not None:
        walk(body, [])
    return out


def licence_of(record):
    said = (record.get("license") or "").strip().lower()
    if said in ("cc by", "cc-by"):
        return "CC BY (the article's licence, as Europe PMC's record of it states)", "permissive"
    if said == "cc0":
        return "CC0 (the article's licence, as Europe PMC's record of it states)", "permissive"
    if said.startswith("cc by-nc"):
        return f"{said.upper()} (the article's licence, as Europe PMC's record of it states)", "non-commercial"
    return "No open licence stated in Europe PMC's record of the article", "no stated terms"


def paper_source(d, folder, key, paper):
    record_file, text_file = paper_files(key, paper)
    found = json.loads(d.text(folder, record_file))["resultList"]["result"]
    record = next((r for r in found if r.get("pmcid") == paper["pmc"]), None)
    if not record:
        raise Breach(f"{folder}/{record_file} is not the record of {paper['pmc']}")
    journal = record.get("journalInfo") or {}
    licence, klass = licence_of(record)
    citation = f"{record.get('authorString', '').rstrip('.')} ({record.get('pubYear')}). {record.get('title', '').rstrip('.')}. {journal.get('journal', {}).get('title', '')} {journal.get('volume', '')}".strip()
    source = {"text": re.sub(r"<[^>]+>", "", citation), "doi": record.get("doi"), "url": f"https://europepmc.org/article/PMC/{paper['pmc']}", "licence": licence, "class": klass, "accessed": d.day(folder, text_file), "standing": "open paper, numbers only"}
    return source, paragraphs(d.text(folder, text_file))


def per_cell(d, config, species, block, machine, species_file, sources, read_papers):
    out = []
    for item in machine.get("per_cell") or []:
        if "fact" in item:
            fact = next((f for f in species_file["cell"].get("facts") or [] if f["label"] == item["fact"]), None)
            if not fact:
                raise Breach(f"{species}, {machine['kind']}: the species file has no fact {item['fact']!r}")
            for k in fact["sources"]:
                sources[f"species:{k}"] = {name: species_file["sources"][k][name] for name in ("text", "doi", "url", "licence", "class", "standing", "where", "accessed") if name in species_file["sources"][k]}
            out.append({"fact": item["fact"], "file": f"data/species/{species}.json", "counts": item["counts"], "sources": [f"species:{k}" for k in fact["sources"]]})
            continue
        key = item["source"]
        paper = config["papers"][key]
        folder = block["papers"]
        if key not in read_papers:
            read_papers[key] = paper_source(d, folder, key, paper)
        source, paras = read_papers[key]
        at = [text for trail, n, text in paras if trail == item["where"]["section"] and n == item["where"]["paragraph"]]
        if len(at) != 1:
            raise Breach(f"{key}: no paragraph {item['where']['paragraph']} under {item['where']['section']!r}")
        for number in item["says"]:
            if not re.search(rf"(^|[^\d.,]){re.escape(number)}([^\d]|$)", at[0]):
                raise Breach(f"{key}: the paragraph does not give {number}")
        if source["class"] == "non-commercial":
            raise Breach(f"{key} is under a non-commercial licence: it is asked for first, and no number of it is taken")
        sources[key] = source
        out.append({"value": item["value"], "unit": item.get("unit", "per cell"), "counts": item["counts"], "cell": item["cell"], "source": key, "where": f"{item['where']['section']}, paragraph {item['where']['paragraph']}", "as_written": item["says"]})
    return out


# ---------------------------------------------------------------------------------------
# A species' file
# ---------------------------------------------------------------------------------------

def build_species(d, datasets, config, kinds, species, block, ontology):
    block = {**block, "species_id": species}
    proteome = Proteome(d, species, block, ontology)
    sources = {
        "uniprot": {"text": f"UniProtKB, release {proteome.release}: the reviewed entries of the reference proteome {proteome.proteome} ({block['organism']}), their keywords and the Gene Ontology terms UniProt gives them, read from the saved copies in {proteome.kb}" + (f", the keywords from {proteome.keywords_from['folder']} (release {proteome.keywords_from['release']})" if proteome.keywords_from else "") + ".", "url": "https://www.uniprot.org", "licence": "CC BY 4.0", "class": "permissive"},
        "go": {"text": f"The Gene Ontology, go-basic.obo, version {ontology['version']}: the terms' names and their is_a and part_of links.", "url": "https://geneontology.org", "licence": "CC BY 4.0", "class": "permissive"},
    }
    by_protein = defaultdict(list)
    machines = [dossier(d, datasets, config, kinds, species, block, machine, proteome, sources, by_protein) for machine in block["machines"]]
    species_file = read_json(ROOT / "data" / "species" / f"{species}.json")
    read_papers = {}
    for machine, item in zip(block["machines"], machines):
        counts = per_cell(d, config, species, block, machine, species_file, sources, read_papers)
        if counts:
            item["per_cell"] = counts
    return {
        "format": FORMAT,
        "species": species, "label": block["label"], "organism": block["organism"], "taxon": block["taxon"],
        "note": "Generated by visualizer/tools/gather_machines.py from data/catalogue/gather.json, the saved answers of UniProt, the Gene Ontology and the Protein Data Bank, and the species' own proteins: do not edit. The contract is schema/MACHINE_DOSSIERS.md.",
        "rules": {
            "proteins": "A protein is named with a machine where its reviewed UniProt entry carries the machine's Gene Ontology term or a narrower one. 'part': named with it (and carrying one of its keywords, where gather.json gives them) and held by the chosen entry as an entity of the species, or a protein of the species in the machine's seed entry. 'part by keyword': named with it and carrying the keyword, not held by the entry. 'named': named with it by the term alone. A protein of the species that the entry holds and the ontology does not name with the machine is counted under the structure ('in_entry_only') and left out of the measure. No protein is matched by a name.",
            "structure": f"Candidates are the experimental entries of the Protein Data Bank in which a polymer entity from an organism under taxon {block['lineage'][0]} ({block['lineage'][1]}) is, by RCSB's mapping, one of the machine's proteins; every hit is read. They are ranked by the proteins present; then an entry in which those proteins' residues with coordinates add up to at least {int(MEASURABLE * 100)} per cent of them before one with less; then an entry at {FINE} Å or better before a coarser one (an entry with no resolution, of nuclear magnetic resonance, counts as coarser); then the fewest other polymer entities (partners, nucleic acids, other organisms' proteins); then the proteins nearly whole (at least {int(WHOLE * 100)} per cent of the protein's own length with coordinates in every copy); then the proteins' lengths with coordinates added up in whole proteins; then resolution; then the most copies of them in the first biological assembly; then id. gather.json may name another entry, and says why.",
            "measure": "The call is in the terms of tools/measure_particle.py --machine: what is not the machine is left out by entity id (nucleic acids that are not its parts, other organisms' proteins, proteins of the species not named with it); each part is NAME=ENTITY,ENTITY. A size measured so is the viewer's own; the Protein Data Bank states none.",
            "join": "Each protein is joined to the Protein atlas by the atlas's own id (RCSB's mapping of an entity to UniProt; the entry file's own reference is kept beside it). by_protein gives, for each protein of the atlas, the machines it is a part of, with the tier.",
            "measurable": "measurable speaks of the proteins the entry holds: their residues with coordinates add up to at least 70 per cent of them. How much of the machine the entry holds is said beside it (whole.present of whole.proteins_wanted).",
        },
        "made": {"generator": "visualizer/tools/gather_machines.py", "uniprot_release": proteome.release, **({"keywords_release": proteome.keywords_from["release"]} if proteome.keywords_from else {}), "ontology": ontology["version"], "atlas": proteome.atlas_file},
        "machines": machines,
        "by_protein": {a: sorted(k, key=lambda item: item["machine"]) for a, k in sorted(by_protein.items())},
        "sources": dict(sorted(sources.items())),
    }


def build(datasets):
    config, kinds = load_config()
    d = P.Datasets(datasets)
    d.entry(*UNIPROT_TERMS)
    d.entry(*PDB_TERMS)
    ontology = load_ontology(d)
    out = {}
    for species, block in config["species"].items():
        out[species] = build_species(d, datasets, config, kinds, species, block, ontology)
    for species, data in out.items():
        text = dumps(data)
        if PATHS.search(text):
            raise Breach(f"{species}: the dossier names a path of this machine")
        if WORDS.search(json.dumps([m.get("plain", "") + m["named"]["text"] for m in data["machines"]])):
            raise Breach(f"{species}: a dossier's words say what Cells does of a machine")
    return out


def dumps(data):
    return json.dumps(data, indent=1, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------------------------------
# Fetch: the only step that uses the network
# ---------------------------------------------------------------------------------------

def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def ask(url, body=None, tries=4):
    data = json.dumps(body).encode() if body is not None else None
    call = urllib.request.Request(url, data=data, headers={"User-Agent": CLIENT, "Accept-Encoding": "identity", **({"Content-Type": "application/json"} if data else {})})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(call, timeout=600) as answer:
                return answer.status, answer.headers.get("Content-Type"), answer.read()
        except urllib.error.HTTPError as error:
            if error.code < 500 and error.code != 429:
                return error.code, None, b""
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        time.sleep(15 * (attempt + 1))
    return 0, None, b""


def save(datasets, folder, name, url, role, body, content, content_type, record, extra=None):
    """Keep an answer as it came, in a folder of this tool's own, and describe it in the MANIFEST.
    A folder another agent made is never written."""
    path = Path(datasets) / folder
    manifest_path = path / "MANIFEST.json"
    manifest = read_json(manifest_path) if manifest_path.exists() else None
    if manifest is not None and MINE not in manifest.get("note", ""):
        raise Breach(f"{folder} was made by another agent: nothing is written there")
    if manifest is None and path.exists() and any(path.iterdir()):
        raise Breach(f"{folder} holds files and no MANIFEST of this tool")
    path.mkdir(parents=True, exist_ok=True)
    files = []
    if body is not None:
        body_name = name.replace(".json", ".body.json")
        (path / body_name).write_text(json.dumps(body, indent=1) + "\n", encoding="utf-8")
        files.append((body_name, None, "the body of the POST whose answer is " + name, "application/json"))
    (path / name).write_bytes(content)
    files.append((name, url, role, content_type))
    manifest = manifest or {"source_id": Path(folder).name, "files": []}
    when = utc()
    for file_name, file_url, file_role, file_type in files:
        sha = hashlib.sha256((path / file_name).read_bytes()).hexdigest()
        entry = {"name": file_name, "url": file_url, "method": ("POST" if file_url and body is not None else ("GET" if file_url else None)), "role": file_role, "retrieved_utc": when, "http_status": 200 if file_url else None, "content_type": file_type, "size_bytes": (path / file_name).stat().st_size, "sha256": sha, "ok": True, "error": None, **((extra or {}) if file_url else {})}
        manifest["files"] = sorted([f for f in manifest["files"] if f["name"] != file_name] + [entry], key=lambda f: f["name"])
    manifest["record"] = record
    manifest["manifest_written_utc"] = when
    manifest["note"] = f"Added by {MINE}: asked of the source by {TOOL} of the Cells checkout with a generic client name, kept as untrusted data and read only by that tool's own code with python3 -I. Nothing here was run."
    manifest_path.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


KEYWORDS_RECORD = {"what": "UniProtKB: the keywords of every reviewed entry of the species' reference proteome, which the saved copy of its entries does not give", "licence": "CC BY 4.0 (UniProt's licence page, saved in human/uniprot-docs-and-terms/)"}
PAPERS_RECORD = {"what": "Open papers found through Europe PMC, each as its record (with the licence Europe PMC states for it) and its full text, read by tools/gather_machines.py for the numbers per cell that data/catalogue/gather.json names, with where each stands; no text, figure or data file of them is taken", "licence": "Each paper's own, as its record states; numbers only are taken"}
RCSB_RECORD = {"what": "Answers of RCSB's search service (search.rcsb.org) and data service (data.rcsb.org), each beside the body of the question that was asked, read to choose for each machine the Protein Data Bank entry its size can be measured from", "licence": "CC0 1.0: \"Data files contained in the PDB archive are available under the CC0 1.0 Universal (CC0 1.0) Public Domain Dedication.\" (the wwPDB's usage policies, saved in ecoli/wwpdb-terms/); RCSB's services serve the archive's data"}
PDB_RECORD = {"what": "Entries of the Protein Data Bank chosen by tools/gather_machines.py for a machine's size, each as its mmCIF file (the first biological assembly where it differs from the deposited model)", "licence": RCSB_RECORD["licence"]}


def fetch(datasets, species_only=None, kinds_only=None, refresh=False):
    config, kinds = load_config()
    d = P.Datasets(datasets)
    ontology = load_ontology(d)
    failed = 0
    for species, block in config["species"].items():
        if species_only and species != species_only:
            continue
        extra = block["uniprot"].get("keywords")
        if extra and not (Path(datasets) / extra / KEYWORDS_FILE).exists():
            query = f"(proteome:{block['uniprot']['proteome']}) AND (reviewed:true)"
            url = f"{UNIPROT}?query={P.q(query)}&compressed=true&format=tsv&fields=accession,keyword"
            call = urllib.request.Request(url, headers={"User-Agent": CLIENT, "Accept-Encoding": "identity"})
            with urllib.request.urlopen(call, timeout=1800) as answer:
                content, ctype, release = answer.read(), answer.headers.get("Content-Type"), answer.headers.get("X-UniProt-Release")
            if not P.whole_gzip(content):
                raise Breach("UniProt's answer is not a whole gzip file")
            save(datasets, extra, KEYWORDS_FILE, url, "the keywords of every reviewed entry of the proteome", None, content, ctype, KEYWORDS_RECORD, extra={"x_uniprot_release": release})
            print(f"200  {extra}/{KEYWORDS_FILE}")
            d = P.Datasets(datasets)
        for key in sorted({item["source"] for machine in block["machines"] for item in machine.get("per_cell") or [] if "source" in item}):
            paper = config["papers"][key]
            for name, url, role in ((paper_files(key, paper)[0], f"{EPMC}/search?format=json&resultType=core&query=PMCID:{paper['pmc']}", "the paper's record at Europe PMC, with its licence"), (paper_files(key, paper)[1], f"{EPMC}/{paper['pmc']}/fullTextXML", "the paper's full text, read for the numbers gather.json names and nothing else")):
                if (Path(datasets) / block["papers"] / name).exists() and not refresh:
                    continue
                status, ctype, content = ask(url)
                if status != 200 or (name.endswith(".xml") and b"<article" not in content) or (name.endswith(".json") and paper["pmc"].encode() not in content):
                    print(f"{status}  {block['papers']}/{name}")
                    failed += 1
                    continue
                save(datasets, block["papers"], name, url, role, None, content, ctype, PAPERS_RECORD)
                print(f"200  {block['papers']}/{name}")
                time.sleep(1)
        proteome = Proteome(d, species, block, ontology)
        for machine in block["machines"]:
            kind = machine["kind"]
            if kinds_only and kind not in kinds_only:
                continue
            folder, answer, _ = rcsb_files(block, kind)
            held = (Path(datasets) / folder / answer).exists() and not refresh
            if not held:
                named = named_proteins(proteome, machine) if machine.get("go") else {}
                accessions = sorted(named)
                if machine.get("seed"):
                    status, ctype, content = ask(GRAPHQL, {"query": ENTRY_QUERY, "variables": {"ids": [machine["seed"]]}})
                    seed = json.loads(content)["data"]["entries"][0]
                    accessions = sorted({a for e in entry_facts(seed, block["lineage"][0])["entities"] if e["same_organism"] for a in e["accessions"]})
                if not accessions:
                    print(f"nothing to search for {species} {kind}")
                    failed += 1
                    continue
                body = search_body(accessions, block["lineage"][0])
                status, ctype, content = ask(SEARCH, body)
                if status != 200:
                    print(f"{status}  search {species} {kind}")
                    failed += 1
                    continue
                save(datasets, folder, answer, SEARCH, f"RCSB's search for {kind}: experimental entries with a polymer entity mapped to one of {len(accessions)} UniProt accessions, from an organism under taxon {block['lineage'][0]}, best resolution first, every hit", body, content, ctype, RCSB_RECORD)
                print(f"200  {folder}/{answer}")
                time.sleep(1)
            d = P.Datasets(datasets)
            ids, total, _ = saved_candidates(d, block, kind)
            if machine.get("seed") and machine["seed"] not in ids:
                ids = [machine["seed"]] + ids
            if machine.get("entry") and machine["entry"]["id"] not in ids:
                ids = ids + [machine["entry"]["id"]]
            for k in range(0, len(ids), BATCH):
                name = f"entries_{kind}_{k // BATCH:02d}.json"
                if (Path(datasets) / folder / name).exists() and not refresh:
                    continue
                body = {"query": ENTRY_QUERY, "variables": {"ids": ids[k:k + BATCH]}}
                status, ctype, content = ask(GRAPHQL, body)
                if status != 200 or b'"errors"' in content[:200]:
                    print(f"{status}  {folder}/{name}")
                    failed += 1
                    continue
                save(datasets, folder, name, GRAPHQL, f"RCSB's data service: what the entries of {kind}'s search hold ({len(ids[k:k + BATCH])} entries)", body, content, ctype, RCSB_RECORD)
                print(f"200  {folder}/{name}")
                time.sleep(1)
    print(f"{failed} failed")
    return failed


def fetch_files(datasets, species_only=None, kinds_only=None):
    """The chosen entries' files, where no folder under the datasets holds them yet."""
    config, kinds = load_config()
    d = P.Datasets(datasets)
    ontology = load_ontology(d)
    failed = 0
    for species, block in config["species"].items():
        if species_only and species != species_only:
            continue
        block = {**block, "species_id": species}
        proteome = Proteome(d, species, block, ontology)
        sources, by_protein = {}, defaultdict(list)
        for machine in block["machines"]:
            if kinds_only and machine["kind"] not in kinds_only:
                continue
            try:
                item = dossier(d, datasets, config, kinds, species, block, machine, proteome, sources, by_protein)
            except SystemExit as stop:
                print(f"skipped {species} {machine['kind']}: {stop}")
                failed += 1
                continue
            name = (item["structure"] or {}).get("file_to_fetch")
            if not name:
                continue
            folder = f"{species}/wwpdb-{machine['kind']}-g"
            status, ctype, content = ask(f"{FILES}/{name}")
            if status != 200 or not P.whole_gzip(content):
                print(f"{status}  {folder}/{name}")
                failed += 1
                continue
            s = item["structure"]
            save(datasets, folder, name, f"{FILES}/{name}", "the entry's mmCIF file, as the PDB archive serves it" + ("; its first biological assembly" if s["assembly"] else ""), None, content, ctype, PDB_RECORD,
                 extra={"entry": s["entry"], "title": s["title"], "method": s["method"], "resolution_A": s["resolution_A"], "organisms": sorted({e["organism"] for e in s["entities"] if e["organism"]}), "organisms_from": "the entry's source records as RCSB's data service serves them (rcsb_entity_source_organism)", "chosen": f"first of {len(s['candidates'])} shown by {TOOL}'s rule among {s['search']['read']} candidates of RCSB's search ({s['search']['hits']} hits)"})
            print(f"200  {folder}/{name}")
            d = P.Datasets(datasets)
            time.sleep(1)
    print(f"{failed} failed")
    return failed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("step", choices=["fetch", "fetch-files", "build", "check"])
    parser.add_argument("species", nargs="?")
    parser.add_argument("--kinds", nargs="*")
    parser.add_argument("--datasets", default="/mnt/datasets/Cells")
    parser.add_argument("--refresh", action="store_true", help="fetch: ask again what this tool saved before")
    args = parser.parse_args(argv)
    if args.step == "fetch":
        return 1 if fetch(args.datasets, args.species, args.kinds, args.refresh) else 0
    if args.step == "fetch-files":
        return 1 if fetch_files(args.datasets, args.species, args.kinds) else 0
    built = build(args.datasets)
    if args.step == "check":
        bad = [s for s, data in built.items() if not (OUT / f"{s}.json").exists() or (OUT / f"{s}.json").read_text(encoding="utf-8") != dumps(data)]
        print("the dossiers are as the tool writes them" if not bad else f"not what the tool writes: {', '.join(bad)}", file=sys.stderr)
        return 1 if bad else 0
    OUT.mkdir(parents=True, exist_ok=True)
    for species, data in built.items():
        (OUT / f"{species}.json").write_text(dumps(data), encoding="utf-8")
        print(f"wrote {rel(OUT / (species + '.json'))}: {len(data['machines'])} machines", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
