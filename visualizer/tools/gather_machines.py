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
- A species with no curated record of its machines (the planarian, the mycoplasmas: gather.json's
  route "family") looks for them by family, in a reference species that has a record: a protein of
  its atlas table that carries the narrowest InterPro family of one of the reference machine's parts
  is a candidate for that part, never more. Its own entries in the Protein Data Bank are found by its
  taxon; where none holds enough of the candidates, the machine has none in hand of its own and the
  reference's entry is named, with its organism.
- Where gather.json's atlas block names the species' own scan of its proteins (the planarian's
  InterProScan run, read into the tree by tools/read_planarian_scan.py), the entries it added to a
  line count as carried by that line, and a family that no line carries and that the table's own
  column cannot place is "not in the table" where a database the scan ran on every protein has a
  signature in it (schema/MACHINE_DOSSIERS.md). Every other species is written as before.

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
IPR = "human/interpro-entries-tree-and-go"
UNIPROT_TERMS = ("human/uniprot-docs-and-terms", "terms_uniprot_license.json")
PDB_TERMS = ("ecoli/wwpdb-terms", "wwpdb_usage_policies.html")
SEARCH = "https://search.rcsb.org/rcsbsearch/v2/query"
UNIPROT = "https://rest.uniprot.org/uniprotkb/stream"
KEYWORDS_FILE = "uniprotkb_reviewed_keywords.tsv.gz"
SUBUNIT_FILE = "uniprotkb_reviewed_subunit.tsv.gz"


def uniprot_scope(block):
    """'reviewed' (the saved copies hold the reviewed entries alone: E. coli, the human) or 'all'
    (the saved copies hold every entry of the proteome, and the atlas keeps one for each gene: the
    mouse, the fruit fly, thale cress). With 'all', only the atlas's own entries are read."""
    return (block.get("uniprot") or {}).get("scope", "reviewed")


def keywords_file(block):
    return KEYWORDS_FILE if uniprot_scope(block) == "reviewed" else "uniprotkb_keywords.tsv.gz"


def subunit_file(block):
    return SUBUNIT_FILE if uniprot_scope(block) == "reviewed" else "uniprotkb_subunit.tsv.gz"


def proteome_query(block):
    query = f"(proteome:{block['uniprot']['proteome']})"
    return query + " AND (reviewed:true)" if uniprot_scope(block) == "reviewed" else query
# A sentence of a SUBUNIT comment that says how many copies of the protein go together: a word for a
# homo-oligomer, a ring named by its number, or a number of subunits.
HOMOMER = re.compile(r"\bhomo-?[a-z]*mer|\b[a-z]+meric rings?\b|\b(\d+|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen)\s+[A-Za-z0-9-]*\s*subunits\b", re.I)
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
        if block.get("route") == "family":
            if block["reference"] not in config["species"] or config["species"][block["reference"]].get("route") == "family":
                raise Breach(f"{species}: its reference {block['reference']} is not a species with a record of its own")
            continue
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
        self.scope = uniprot_scope(block)
        middle = "_reviewed" if self.scope == "reviewed" else ""
        self.places = f"uniprotkb_{proteome}{middle}_places.json.gz"
        self.signatures = f"uniprotkb_{proteome}{middle}_signatures.tsv.gz"
        table = ROOT / "data" / "proteins" / species / "proteins.tsv"
        atlas_ids = {row["id"] for row in csv.DictReader(io.StringIO(table.read_text(encoding="utf-8")), delimiter="\t")}
        keep = (lambda accession: True) if self.scope == "reviewed" else (lambda accession: accession in atlas_ids)
        raw = json.loads(d.text(kb, self.places))["results"]
        self.release = d.entry(kb, self.places).get("x_uniprot_release")
        if d.entry(kb, self.signatures).get("x_uniprot_release") != self.release:
            raise Breach(f"{species}: the two UniProt downloads are not of one release")
        self.entries = {}
        for item in raw:
            if not keep(item["primaryAccession"]):
                continue
            names = item.get("proteinDescription", {}).get("recommendedName", {}).get("fullName", {}).get("value")
            gene = next((g["geneName"]["value"] for g in item.get("genes") or [] if g.get("geneName")), None)
            self.entries[item["primaryAccession"]] = {"gene": gene, "name": names, "entry_name": item.get("uniProtkbId"), "keywords": sorted({k["name"] for k in item.get("keywords") or []})}
        self.keywords_from = None
        extra = block["uniprot"].get("keywords")
        if extra:
            rows = list(csv.reader(d.text(extra, keywords_file(block)).splitlines(), delimiter="\t"))
            column = rows[0].index("Keywords")
            said = {row[0]: sorted({k.strip() for k in row[column].split(";") if k.strip()}) for row in rows[1:]}
            for accession, item in self.entries.items():
                if item["keywords"]:
                    raise Breach(f"{species}: the saved entries give keywords already; {extra} is not needed")
                item["keywords"] = said.get(accession, [])
            self.keywords_from = {"folder": extra, "file": keywords_file(block), "release": d.entry(extra, keywords_file(block)).get("x_uniprot_release")}
        self.terms, self.interpro = {}, {}
        rows = list(csv.reader(d.text(kb, self.signatures).splitlines(), delimiter="\t"))
        column, families = rows[0].index("Gene Ontology IDs"), rows[0].index("InterPro")
        for row in rows[1:]:
            if not keep(row[0]):
                continue
            self.terms[row[0]] = [t.strip() for t in row[column].split(";") if t.strip()]
            self.interpro[row[0]] = [t.strip() for t in row[families].split(";") if t.strip()]
        # UniProt's own words on what an entry's protein forms (its SUBUNIT comment), where saved.
        self.subunit, self.subunit_from = {}, None
        folder = block["uniprot"].get("subunit")
        if folder:
            rows = list(csv.reader(d.text(folder, subunit_file(block)).splitlines(), delimiter="\t"))
            column = rows[0].index("Subunit structure")
            self.subunit = {row[0]: row[column] for row in rows[1:] if row[column]}
            self.subunit_from = {"folder": folder, "file": subunit_file(block), "release": d.entry(folder, subunit_file(block)).get("x_uniprot_release")}
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
    if machine.get("go") and not named and not machine.get("seed"):
        # No entry of the species carries the term: nothing was searched for, and nothing is found.
        terms = machine["go"]
        out["proteins"] = {"columns": ["id", "gene", "label", "tier", "go", "keyword", "entities", "in_atlas"], "rows": [], "counts": {}}
        out["join"] = {"atlas": proteome.atlas_file, "by": "the atlas's id: a UniProt accession", "parts": 0, "parts_in_atlas": 0, "held_by_entry": 0, "all": 0, "all_in_atlas": 0, "not_in_atlas": []}
        out["named"] = {"by": "Gene Ontology", "terms": [[t, proteome.ontology["name"](t)] for t in terms], "keyword": machine.get("keyword") or [], "seed": None, "count": 0, "seed_text": None,
                        "text": "No UniProt entry of the species in its atlas carries the Gene Ontology's term " + " or ".join(f"{proteome.ontology['name'](t)} ({t})" for t in terms) + " or a narrower one.", "sources": ["uniprot", "go"]}
        out["structure"] = None
        out["no_structure"] = "None in hand: no protein of the species is named with the machine, so no entry was looked for."
        return out
    # The candidates and the chosen entry.
    ids, total, day = saved_candidates(d, block, kind["id"])
    facts = {i: entry_facts(e, lineage_taxon) for i, e in saved_entries(d, block, kind["id"], ids).items()}
    facts, left_out = leave_out(config, block["species_id"], kind["id"], facts)
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
    # An entry is the machine's only where it holds at least two of the proteins sought (or the one,
    # where one is sought); an entry of one protein of a larger machine is named, not taken.
    sought = keyworded or wanted
    # An entry is the machine's only where it holds at least one of the proteins sought that no other
    # machine of the species seeks: an entry that holds only proteins two machines share (a subunit
    # common to three RNA polymerases) is another machine's.
    others = set().union(*[v for k, v in (block.get("sought_by_kind") or {}).items() if k != kind["id"]]) if block.get("sought_by_kind") else set()
    own = sought - others
    shared_only = []
    if own and not machine.get("entry"):
        keep = []
        for f in ranked:
            held = {a for e in f["entities"] if e["same_organism"] for a in e["accessions"] if a in sought}
            (keep if held & own or not held else shared_only).append(f)
        ranked = keep
    lone = None
    if ranked and not machine.get("entry") and score(ranked[0], sought, proteome.lengths)["present"] < min(2, len(sought)):
        lone, ranked = ranked[0], []
    if not ranked:
        chosen = None
    else:
        chosen = ranked[0]
    if machine.get("entry"):
        chosen = facts[machine["entry"]["id"]]
    if machine.get("structure") is False or chosen is None:
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
    fractions = fraction_statements(proteome, [r[0] for r in rows if r[3] != "named"])
    if fractions:
        out["uniprot_fractions"] = fractions
    said = homomer_statements(proteome, [r[0] for r in rows if r[3] != "named"])
    if said:
        out["uniprot_subunit"] = {"note": "The sentences of each part's UniProt entry (its SUBUNIT comment) that say how many copies of the protein go together, in UniProt's own words, its evidence tags left out.", "sources": ["uniprot"], "items": said}
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
        "text": (f"{len(named)} of the species' " + ("reviewed UniProt entries" if proteome.scope == "reviewed" else "UniProt entries in its atlas") + " carry the Gene Ontology's term " + " or ".join(f"{proteome.ontology['name'](t)} ({t})" for t in terms) + " or a narrower one" + (f"; {len(keyworded)} of them also carry UniProt's keyword " + " or ".join(machine['keyword']) if machine.get('keyword') else "") + ".")
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
    if not ranked:
        out["structure"] = None
        out["no_structure"] = (f"None in hand of the species' own: the best entry of RCSB's search of {day}, {lone['entry']}, holds one of the {len(sought)} proteins sought, and an entry of one protein of a larger machine is not taken."
                               if lone else (f"None in hand of the species' own: the entries of RCSB's search of {day} that hold its proteins hold only proteins another machine of the species also seeks ({', '.join(f['entry'] for f in shared_only[:3])}{' and others' if len(shared_only) > 3 else ''})."
                                             if shared_only else (f"None in hand of the species' own: every entry of RCSB's search of {day} that holds its proteins is left out by gather.json, each because its own title names another complex (left_out)."
                                                                  if left_out else f"None in hand of the species' own: RCSB's search of {day} found no experimental entry with a polymer entity from an organism under taxon {block['lineage'][0]} ({block['lineage'][1]}) that is one of the machine's proteins.")))
        elsewhere = (block.get("elsewhere_from") or {}).get(kind["id"])
        if elsewhere:
            out["structure_elsewhere"] = elsewhere
        if left_out:
            out["left_out"] = left_out
        return out
    out["structure"] = structure(d, datasets, machine, chosen, ranked, total, day, proteome, named, keyworded, seed_set, block, sources)
    if left_out:
        out["structure"]["left_out"] = left_out
    note_holds_more(config, block["species_id"], kind["id"], out["structure"])
    out["structure"]["in_entry_only"] = {"count": len(entry_only), "note": "Proteins of the species that the entry holds and the ontology does not name with the machine: left out of the measure.", "proteins": entry_only}
    return out


def homomer_statements(proteome, accessions):
    """For each protein, the sentences of its UniProt SUBUNIT comment that say how many copies of it
    go together (a homo-oligomer, a ring named by its number, a number of subunits), as UniProt writes
    them, its evidence tags removed."""
    out = []
    for accession in accessions:
        text = proteome.subunit.get(accession)
        if not text:
            continue
        text = re.sub(r"\s*\{ECO:[^}]*\}", "", text)
        # The column joins an entry's SUBUNIT comments; one about an infection describes another organism's protein with it.
        comments = [c.strip().rstrip(";").strip() for c in re.split(r"(?:^|;\s*)SUBUNIT:\s*", text) if c.strip() and not c.strip().startswith("(Microbial infection)")]
        said = [re.sub(r"\.\.$", ".", sentence.strip()) for comment in comments for sentence in re.split(r"(?<=[.])\s+(?=[A-Z])", comment) if HOMOMER.search(sentence)]
        if said:
            out.append({"id": accession, "gene": proteome.gene(accession), "says": said})
    return out


FRACTION = re.compile(r"\bcomponent of the ([A-Za-z][A-Za-z ()/-]*?(?:fragment|fraction))\b(?: of the enzyme)?", re.I)


def fraction_statements(proteome, accessions):
    """The part of the machine that a part's own UniProt SUBUNIT comment places it in, where the
    comment says so of the entry itself ("This is a component of the iron-sulfur (IP) fragment of
    the enzyme"): grouped by the fragment or fraction it names, in UniProt's words. A sentence that
    lists other proteins by name is not read, so nothing is matched by a name."""
    groups, said, unplaced = defaultdict(list), {}, []
    for accession in accessions:
        text = re.sub(r"\s*\{ECO:[^}]*\}", "", proteome.subunit.get(accession, ""))
        found = None
        for sentence in re.split(r"(?<=[.])\s+(?=[A-Z])", re.sub(r"(?:^|;\s*)SUBUNIT:\s*", " ", text)):
            hit = FRACTION.search(sentence)
            if hit and re.match(r"^\s*(This (is )?a component|Component|This is the largest subunit of complex I and it is a component)", sentence.strip()):
                found = (hit.group(1).strip(), sentence.strip())
                break
        if found:
            groups[found[0]].append(accession)
            said[accession] = found[1]
        else:
            unplaced.append(accession)
    if not groups:
        return None
    return {"by": "UniProt's SUBUNIT comment of each part, where it names the fragment or fraction of the machine the entry's own protein is a component of",
            "groups": {name: ids for name, ids in sorted(groups.items())}, "unplaced": unplaced,
            "sentences": [{"id": a, "gene": proteome.gene(a), "says": said[a]} for a in accessions if a in said], "sources": ["uniprot"]}


def read_complex_portal(d, block, config):
    """The Complex Portal's curated complexes of the species: each with its members by UniProt
    accession (an isoform or chain suffix removed) and the stoichiometry it gives (0: not known).
    Nothing is read while gather.json's switch for the source is off (sources_held.complex_portal)."""
    spec = block.get("complex_portal")
    if not spec or not source_used(config, "complex_portal"):
        return None
    rows = list(csv.reader(d.text(spec["folder"], spec["file"]).splitlines(), delimiter="\t"))
    head = rows[0]
    at = {name.lstrip("#"): i for i, name in enumerate(head)}
    out = []
    for row in rows[1:]:
        members = {}
        others = 0
        for item in row[at["Identifiers (and stoichiometry) of molecules in complex"]].split("|"):
            found = re.match(r"^([A-Z0-9]+)(?:-[A-Z0-9_]+)?\((\d+)\)$", item.strip())
            if found and re.match(r"^[OPQ][0-9][A-Z0-9]{3}[0-9]$|^[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}$", found.group(1)):
                members[found.group(1)] = members.get(found.group(1), 0) + int(found.group(2))
            else:
                others += 1
        out.append({"id": row[at["Complex ac"]], "name": row[at["Recommended name"]], "members": members, "other_members": others})
    return {"complexes": out, "file": f"{spec['folder']}/{spec['file']}", "day": d.day(spec["folder"], spec["file"])}


def source_used(config, name):
    """A source that gather.json holds (sources_held.<name>.use false) is read by no step."""
    held = (config.get("sources_held") or {}).get(name)
    return True if held is None else bool(held.get("use"))


def complex_portal_for(portal, parts):
    """The Complex Portal's complexes whose members are parts of the machine, by accession: the
    most parts first, then the fewest members that are not parts."""
    if not portal or not parts:
        return None
    hits = []
    for complex_ in portal["complexes"]:
        shared = [a for a in complex_["members"] if a in parts]
        if shared:
            hits.append((-len(shared), len(complex_["members"]) - len(shared) + complex_["other_members"], complex_["id"], complex_, shared))
    hits.sort(key=lambda h: (h[0], h[1], h[2]))
    if not hits:
        return {"note": "No complex of the Complex Portal's file for the species has a part of this machine among its members.", "file": portal["file"], "complexes": [], "sources": ["complex_portal"]}
    return {"note": "The Complex Portal's curated complexes that hold parts of this machine, matched by UniProt accession: the most parts first, then the fewest members that are not parts. Stoichiometry is the Complex Portal's (0 where it gives none).",
            "file": portal["file"],
            "complexes": [{"id": c["id"], "name": c["name"], "parts_held": -n, "of_parts": len(parts), "members": len(c["members"]) + c["other_members"],
                           "stoichiometry": {a: c["members"][a] for a in sorted(shared)}, "members_not_parts": sorted(a for a in c["members"] if a not in parts), "other_members": c["other_members"]}
                          for n, extra, _, c, shared in hits[:3]],
            "sources": ["complex_portal"]}


def sub_assemblies(machine, item, portal, parts, ontology):
    """The parts of a machine that its own records name: the narrower Gene Ontology terms its parts
    carry (each with the parts that carry it), and the Complex Portal's complexes whose members are
    all parts of the machine and fewer than all (each with its members)."""
    roots = set(machine.get("go") or [])
    by_term = defaultdict(list)
    for row in item["proteins"]["rows"]:
        if row[3] == "named":
            continue
        for term in row[4]:
            if term not in roots:
                by_term[term].append(row[0])
    terms = {t: {"name": ontology["name"](t), "parts": ids} for t, ids in sorted(by_term.items())}
    complexes = []
    for complex_ in (portal or {}).get("complexes") or []:
        members = set(complex_["members"])
        if len(members) >= 2 and members < parts:
            complexes.append({"id": complex_["id"], "name": complex_["name"], "parts": sorted(members), "stoichiometry": {a: complex_["members"][a] for a in sorted(members)}})
    if not terms and not complexes:
        return None
    return {"note": "Parts of the machine that its records name: narrower Gene Ontology terms its parts carry (as UniProt gives them)" + (", and the Complex Portal's complexes whose members are all parts of the machine and fewer than all" if complexes else "") + ". Nothing is matched by a name.",
            "go": terms, **({"complex_portal": sorted(complexes, key=lambda c: (-len(c["parts"]), c["id"]))} if complexes else {}), "sources": ["go", "uniprot"] + (["complex_portal"] if complexes else [])}


def read_paxdb(d, block, proteome):
    """PaxDb's abundances in one dataset of the species, joined to the species' UniProt accessions
    by an identifier: E. coli's by the locus (b number) its STRING identifier carries, the human's
    by PaxDb's own links from its identifiers to UniProt entry names."""
    spec = block.get("paxdb")
    if not spec:
        return None
    text = d.text(spec["folder"], spec["dataset"])
    header = {line[1:].split(":", 1)[0].strip(): line[1:].split(":", 1)[1].strip() for line in text.splitlines() if line.startswith("#") and ":" in line}
    values = {}
    for line in text.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        gene, string_id, abundance = line.split("\t")[:3]
        values[string_id] = float(abundance)
    to_accession = {}
    if spec["join"] == "locus":
        by_locus = {row.get("locus"): accession for accession, row in proteome.atlas.items() if row.get("locus")}
        for string_id in values:
            locus = string_id.split(".", 1)[1]
            if locus in by_locus:
                to_accession[string_id] = by_locus[locus]
    else:
        by_name = {item["entry_name"]: accession for accession, item in proteome.entries.items() if item.get("entry_name")}
        prefix = spec["taxon_prefix"]
        for line in d.text(spec.get("links_folder", spec["folder"]), spec["links"]).splitlines():
            if not line.startswith(prefix):
                continue
            string_id, name = line.split("\t")[:2]
            if string_id in values and name in by_name:
                to_accession[string_id] = by_name[name]
    abundance = {}
    for string_id, accession in to_accession.items():
        abundance[accession] = values[string_id]
    return {"dataset": spec["dataset"], "id": header.get("id"), "name": header.get("name"), "abundance": abundance, "file": f"{spec['folder']}/{spec['dataset']}",
            "joined": len(to_accession), "values": len(values)}


def paxdb_for(pax, rows):
    if not pax:
        return None
    parts = [(r[0], r[1]) for r in rows if r[3] != "named"]
    found = [[a, g, pax["abundance"][a]] for a, g in parts if a in pax["abundance"]]
    return {"note": "PaxDb's abundance of each part in one of its datasets, as that database gives it: parts per million of the dataset's protein molecules (PaxDb's page calls its values protein abundance, ppm). It is no count of copies in a cell.",
            "dataset": pax["dataset"], "dataset_id": pax["id"], "dataset_name": pax["name"], "unit": "ppm",
            "items": found, "missing": [a for a, g in parts if a not in pax["abundance"]], "sources": ["paxdb"]}


def note_holds_more(config, species, kind, structure):
    """An entry kept for a machine that holds other complexes besides it (a supercomplex, a ribosome
    with the polymerase on it): gather.json's entries_noted says so, and the dossier carries it beside
    the title, with how many polymer entities of the entry are left out of the measure."""
    if not structure:
        return
    for item in config.get("entries_noted") or []:
        if item["species"] == species and item["kind"] == kind and item["entry"] == structure["entry"]:
            if item["title"] != structure["title"]:
                raise Breach(f"{species}, {kind}: {item['entry']}'s title is {structure['title']!r}, not {item['title']!r} as gather.json says")
            others = [e for e in structure["entities"] if e["role"].startswith("left out")]
            if not sum(1 for e in others if "polypeptide" in e["type"]) >= 2:
                raise Breach(f"{species}, {kind}: {item['entry']} is noted as holding other complexes, and leaves out fewer than two proteins")
            structure["holds_more"] = {"says": item["holds"], "why": item["why"], "left_out_entities": len(others)}


def leave_out(config, species, kind, facts):
    """The entries gather.json leaves out of a machine's ranking (an entry of another machine, by its
    own title), each checked against the title the saved answer gives."""
    gone = []
    for item in config.get("entries_left_out") or []:
        if item["species"] != species or item["kind"] != kind:
            continue
        found = facts.get(item["entry"])
        if found is None:
            raise Breach(f"{species}, {kind}: {item['entry']} is left out and is not among the saved candidates")
        if found["title"] != item["title"]:
            raise Breach(f"{species}, {kind}: {item['entry']}'s title is {found['title']!r}, not {item['title']!r} as gather.json says")
        gone.append({"entry": item["entry"], "title": item["title"], "why": item["why"]})
    return {k: v for k, v in facts.items() if k not in {g["entry"] for g in gone}}, gone


def sought_proteins(d, block, machine, proteome):
    """The proteins a machine's structure is sought by: those of its seed entry, or those named with
    it by its term that also carry its keyword where it has one, or all those named with it."""
    if machine.get("seed"):
        ids, _, _ = saved_candidates(d, block, machine["kind"])
        entries = saved_entries(d, block, machine["kind"], ids)
        seed = entries.get(machine["seed"])
        if not seed:
            return set()
        return {a for e in entry_facts(seed, block["lineage"][0])["entities"] if e["same_organism"] for a in e["accessions"] if a in proteome.entries}
    named = named_proteins(proteome, machine) if machine.get("go") else {}
    return {a for a, item in named.items() if item["keyword"]} if machine.get("keyword") else set(named)


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
        if item.get("scale") and not item.get("written"):
            raise Breach(f"{key}: a number given with a power of ten says how it is written")
        out.append({"value": item["value"], **({"scale": item["scale"], "written": item["written"]} if item.get("scale") else {}), **({"cites": item["cites"]} if item.get("cites") else {}), "unit": item.get("unit", "per cell"), "counts": item["counts"], "cell": item["cell"], "source": key, "where": f"{item['where']['section']}, paragraph {item['where']['paragraph']}", "as_written": item["says"]})
    return out


# ---------------------------------------------------------------------------------------
# A species' file
# ---------------------------------------------------------------------------------------

def build_species(d, datasets, config, kinds, species, block, ontology, built=None):
    built = built or {}
    block = {**block, "species_id": species}
    proteome = Proteome(d, species, block, ontology)
    sources = {
        "uniprot": {"text": f"UniProtKB, release {proteome.release}: the " + ("reviewed entries" if proteome.scope == "reviewed" else "entries the species' atlas keeps, one for each gene, reviewed or not,") + f" of the reference proteome {proteome.proteome} ({block['organism']}), their keywords and the Gene Ontology terms UniProt gives them, read from the saved copies in {proteome.kb}" + (f", the keywords from {proteome.keywords_from['folder']} (release {proteome.keywords_from['release']})" if proteome.keywords_from else "") + (f", the SUBUNIT comments from {proteome.subunit_from['folder']} (release {proteome.subunit_from['release']})" if proteome.subunit_from else "") + ".", "url": "https://www.uniprot.org", "licence": "CC BY 4.0", "class": "permissive"},
        "go": {"text": f"The Gene Ontology, go-basic.obo, version {ontology['version']}: the terms' names and their is_a and part_of links.", "url": "https://geneontology.org", "licence": "CC BY 4.0", "class": "permissive"},
    }
    by_protein = defaultdict(list)
    if block.get("elsewhere") and built.get(block["elsewhere"]):
        reference = built[block["elsewhere"]]
        block = {**block, "elsewhere_from": {m["kind"]: {"organism": m["structure"]["organism"], "entry": m["structure"]["entry"], "title": m["structure"]["title"], "method": m["structure"]["method"], "resolution_A": m["structure"]["resolution_A"],
                                                         "measurable": m["structure"]["measurable"], "file": m["structure"]["file"], "call": m["structure"]["measure"]["call"],
                                                         "from": f"the {reference['label'].lower() if reference['label'] in ('Human', 'Mouse') else reference['label']} dossier's own structure: its parts are that species' proteins, by entity ids", "sources": [f"reference_{block['elsewhere']}"]}
                                             for m in reference["data"]["machines"] if m.get("structure")}}
        sources[f"reference_{block['elsewhere']}"] = {"text": f"The {reference['label'].lower() if reference['label'] in ('Human', 'Mouse') else reference['label']} dossier (data/catalogue/dossiers/{block['elsewhere']}.json): its structures, each with its own sources there.", "url": None, "licence": "CC0 1.0 (the Protein Data Bank), as the reference dossier's sources state", "class": "permissive"}
    block = {**block, "sought_by_kind": {m["kind"]: sought_proteins(d, block, m, proteome) for m in block["machines"]}}
    machines = [dossier(d, datasets, config, kinds, species, block, machine, proteome, sources, by_protein) for machine in block["machines"]]
    portal = read_complex_portal(d, block, config)
    pax = read_paxdb(d, block, proteome)
    for machine, item in zip(block["machines"], machines):
        parts = {r[0] for r in item["proteins"]["rows"] if r[3] != "named"}
        found = complex_portal_for(portal, parts)
        if found:
            item["complex_portal"] = found
        named_parts = sub_assemblies(machine, item, portal, parts, ontology)
        if named_parts:
            item["sub_assemblies"] = named_parts
        values = paxdb_for(pax, item["proteins"]["rows"])
        if values:
            item["paxdb"] = values
    if portal:
        sources["complex_portal"] = {"text": f"The Complex Portal (EMBL-EBI): its curated complexes of {block['organism']}, the file {portal['file']} as served on {portal['day']}.", "url": "https://www.ebi.ac.uk/complexportal/", "licence": "CC0 1.0, as the Complex Portal 2022 paper (Nucleic Acids Res, section Data access options > Data licencing) states for the resource's data; saved in human/terms-complex-portal-g", "class": "permissive"}
    if pax:
        sources["paxdb"] = {"text": f"PaxDb, release 6.1: the dataset {pax['dataset']} ({pax['name']}, PaxDb dataset id {pax['id']}); {pax['joined']} of its {pax['values']} values joined to the species' UniProt entries.", "url": "https://pax-db.org/", "licence": "CC BY 4.0, as PaxDb's home page declares for the database; saved in human/terms-paxdb-g", "class": "permissive"}
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
            "proteins": ("A protein is named with a machine where its reviewed UniProt entry carries" if proteome.scope == "reviewed" else "A protein is named with a machine where the UniProt entry the atlas keeps for its gene (reviewed or not) carries") + " the machine's Gene Ontology term or a narrower one. 'part': named with it (and carrying one of its keywords, where gather.json gives them) and held by the chosen entry as an entity of the species, or a protein of the species in the machine's seed entry. 'part by keyword': named with it and carrying the keyword, not held by the entry. 'named': named with it by the term alone. A protein of the species that the entry holds and the ontology does not name with the machine is counted under the structure ('in_entry_only') and left out of the measure. No protein is matched by a name.",
            "structure": f"Candidates are the experimental entries of the Protein Data Bank in which a polymer entity from an organism under taxon {block['lineage'][0]} ({block['lineage'][1]}) is, by RCSB's mapping, one of the machine's proteins; every hit is read. They are ranked by the proteins present; then an entry in which those proteins' residues with coordinates add up to at least {int(MEASURABLE * 100)} per cent of them before one with less; then an entry at {FINE} Å or better before a coarser one (an entry with no resolution, of nuclear magnetic resonance, counts as coarser); then the fewest other polymer entities (partners, nucleic acids, other organisms' proteins); then the proteins nearly whole (at least {int(WHOLE * 100)} per cent of the protein's own length with coordinates in every copy); then the proteins' lengths with coordinates added up in whole proteins; then resolution; then the most copies of them in the first biological assembly; then id. gather.json may name another entry, and says why.",
            "measure": "The call is in the terms of tools/measure_particle.py --machine: what is not the machine is left out by entity id (nucleic acids that are not its parts, other organisms' proteins, proteins of the species not named with it); each part is NAME=ENTITY,ENTITY. A size measured so is the viewer's own; the Protein Data Bank states none.",
            "join": "Each protein is joined to the Protein atlas by the atlas's own id (RCSB's mapping of an entity to UniProt; the entry file's own reference is kept beside it). by_protein gives, for each protein of the atlas, the machines it is a part of, with the tier.",
            "measurable": "measurable speaks of the proteins the entry holds: their residues with coordinates add up to at least 70 per cent of them. How much of the machine the entry holds is said beside it (whole.present of whole.proteins_wanted).",
        },
        "made": {"generator": "visualizer/tools/gather_machines.py", "uniprot_release": proteome.release, **({"keywords_release": proteome.keywords_from["release"]} if proteome.keywords_from else {}), "ontology": ontology["version"], "atlas": proteome.atlas_file},
        "machines": machines,
        "by_protein": {a: sorted(k, key=lambda item: item["machine"]) for a, k in sorted(by_protein.items())},
        "sources": dict(sorted(sources.items())),
    }, proteome


# ---------------------------------------------------------------------------------------
# A species with no curated record of its machines: candidates by family signature
# ---------------------------------------------------------------------------------------
#
# For a species whose proteins have no curated Gene Ontology record (the planarian's gene models,
# the mycoplasmas), a machine's proteins are looked for by family: each part of the machine in the
# reference species (the human for an animal, E. coli for a bacterium) has its narrowest InterPro
# families (entries of the type Family that no other Family entry of the same protein lies under);
# a protein of the species that carries one of those signatures is a candidate for that part. Such
# a protein is a candidate, never a counterpart: a family says what a protein is like, not what it
# does in this cell.

class Families:
    def __init__(self, d):
        self.names = P.read_entry_names(d, IPR)
        self.parent = P.read_hierarchy(d, IPR)
        self.release = re.search(r"Release ([\d.]+),", d.text(IPR, "release_notes.txt")).group(1)

    def above(self, accession):
        out = set()
        while accession in self.parent:
            accession = self.parent[accession]
            out.add(accession)
        return out

    def narrowest(self, signatures):
        families = [s for s in signatures if self.names.get(s, {}).get("type") == "Family"]
        covered = {a for f in families for a in self.above(f)}
        return sorted(f for f in families if f not in covered)


def read_table(species, atlas):
    path = ROOT / atlas["table"]
    rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8")), delimiter="\t"))
    return rel(path), rows


# A species' own scan of its proteins (the planarian's InterProScan run, docs/PLANARIAN_ATLAS.md), where gather.json's
# atlas block names one (`scan`: its record and its table of added entries, both written by tools/read_planarian_scan.py).
# The entries a scan added to a line count as carried by that line (by_family), but not in the number rule: `newest`,
# and so `known_to_all`, read the table's own column alone, since the scan's entries would carry the highest number
# past the families that only a database it did not run could show, and those would be called "not in the table"
# falsely. Beside the number rule there is a database rule: a family that no line carries and that the number rule
# cannot place is "not in the table" where a database the scan ran has a signature in it and that database's pass ran
# on every protein of the table. Where either fails, the family goes up the tree as before.
SCAN_FORMAT = "cells.visualizer.interpro_scan@1"


class Scan:
    def __init__(self, spec, table_file, table_ids, families):
        self.record_file, self.added_file = spec["record"], spec["added"]
        self.record = read_json(ROOT / self.record_file)
        if self.record.get("format") != SCAN_FORMAT:
            raise Breach(f"{self.record_file} is not {SCAN_FORMAT}")
        if self.record["run"]["table"]["sha256"] != hashlib.sha256((ROOT / table_file).read_bytes()).hexdigest():
            raise Breach(f"{self.record_file} was made against another copy of {table_file}: run tools/read_planarian_scan.py build again")
        universe = {a for a, v in families.names.items() if v.get("type") == "Family"}
        seen = self.record["could_see"]
        if seen["release"] != families.release or seen["family_entries"] != len(universe):
            raise Breach(f"{self.record_file} was made against InterPro {seen['release']}, not the dossier's {families.release}")
        lines = (ROOT / self.added_file).read_text(encoding="utf-8").splitlines()
        if not lines or lines[0] != "id\tadded":
            raise Breach(f"{self.added_file} is not a table of added entries")
        self.added = {}
        for line in lines[1:]:
            protein, field = line.split("\t")
            self.added[protein] = {item.split(":")[0]: item.split(":")[1].split(",") for item in field.split(";")}
        stray = sorted(set(self.added) - table_ids)
        if stray:
            raise Breach(f"{self.added_file} names proteins the table lacks: {stray[:3]}")
        self.databases = self.record["databases"]
        # The databases whose pass ran on every protein of the table: only these can say that no line carries a family.
        self.complete = [name for name, item in self.databases.items() if item["on_every_protein"] and not item.get("counts_only")]
        self.sees = {name: (set(held["with"].split()) if "with" in held else universe - set(held["without"].split())) for name, held in seen["databases"].items()}
        self.tool = f"{self.record['tool']['name']} {self.record['tool']['release']}"

    def settles(self, family):
        """The databases, run on every protein, that have a signature in the family (none: the scan cannot say)."""
        return [name for name in self.complete if family in self.sees.get(name, ())]

    def source(self, name):
        """The dossier's source for one database of the scan, copied from the scan's record with its terms and class."""
        if name == "InterPro":
            key, said = "interpro", self.record["sources"]["interpro"]
            text = f"InterPro, as the entry list of {self.tool} gives it: which member database's signature belongs to which InterPro entry, for the entries the species' own scan added; the scan's record ({self.record_file}) names it."
        else:
            key = self.databases[name]["source"]
            said, release = self.record["sources"][key], self.databases[name]["release"]
            text = f"{said['name']}{' ' + release if isinstance(release, str) else ''}, as {self.tool} ran it on the species' proteins: its signatures' matches, and the families it could show; the scan's record ({self.record_file}) gives its terms and counts."
        return f"scan_{key}", {"text": text, "url": said.get("url"), "licence": said["licence"], "class": said["class"]}


def lines_by_family(table, atlas, scan=None):
    """Which lines carry each InterPro entry (by_family), and the highest entry each group of lines carries (newest). A
    scan's added entries are carried too, in by_family alone; own_family and newest read the table's own column."""
    by_family = defaultdict(list)
    newest = {}
    for row in table:
        group = row.get(atlas["kind"]) if atlas.get("kind") else "all"
        for signature in (row.get(atlas["signatures"]) or "").split(";"):
            if signature.strip():
                by_family[signature.strip()].append(row[atlas["id"]])
                newest[group] = max(newest.get(group, ""), signature.strip())
    own_family = by_family
    if scan:
        own_family = {entry: list(ids) for entry, ids in by_family.items()}
        for protein, gained in scan.added.items():
            for entry in gained:
                by_family[entry].append(protein)
    return by_family, own_family, newest


SCAN_NOTE = ("A part of the reference is 'part' (held by the reference's entry) or 'part by keyword' (named by its keyword and not held). A line's entries are its own column's and "
             "those the species' own scan added to it (scan.added). Each narrowest family of a part is matched as 'narrowest' (some line carries it); 'not in the table' (no line "
             "carries it, and either every group of lines was scanned, in its own column, at a release that knew it, or a database that the species' own scan ran on every protein has "
             "a signature in the family: either way this says what the table holds, not that the species lacks the protein; scan.rests_on_it names the second kind, with the "
             "databases); 'broader' (newer than a scan of the table, the species' own scan cannot settle it, so the nearest broader Family that some line carries is used) or 'cannot "
             "tell' (the same, and no broader Family is carried). scans_newest gives, for each group of lines, the highest InterPro entry its own column carries.")


SCAN_RULE = (" A protein's signatures are its line's own and the InterPro entries that the species' own scan ({tool}, {record}) found on it and its line lacks ({added}). Those count "
             "as carried by the line, but the highest entry that each group of lines carries is read from the table's own column alone. A family that no line carries is 'not in the "
             "table' where every group of lines was scanned, in its own column, at a release that knew it, or where a database that the scan ran on every protein of the table has a "
             "signature in it; otherwise the nearest broader Family that some line carries is used, or the table cannot tell.")


def scan_words(out, scan, candidates, rests_on_scan, changed, head_candidates, lost, scan_used, sources):
    """What a machine's dossier says of the species' own scan, beside the rows: which families rest on it, through which
    databases, what it changed; and the scan's databases a value rests on, each a source with its own terms."""
    # The machine's sentence (named.text) stays as the number rule writes it: its numbers are the rows' own, which the
    # catalogue and the page count again, and its words hold under both rules. The scan's part is said beside the rows.
    only = sorted((i for i in candidates if not candidates[i]["own"]), key=P.natural)
    keys = []
    for name in sorted(scan_used) + (["InterPro"] if scan_used else []):
        key, source = scan.source(name)
        sources[key] = source
        keys.append(key)
    out["named"]["sources"] = out["named"]["sources"] + sorted(keys)
    out["looked_for"]["note"] = SCAN_NOTE
    out["looked_for"]["scan"] = {
        "record": scan.record_file, "added": scan.added_file, "tool": scan.tool,
        "on_every_protein": scan.complete,
        "rests_on_it": [rests_on_scan[f] for f in sorted(rests_on_scan)],
        "rests_on_it_columns": ["narrowest", "level", "through"],
        "family_rows_changed": len(changed),
        "changed": changed, "changed_columns": ["gene", "narrowest", "level by the table's own column", "level with the scan"],
        "candidates_only_by_it": only,
        "no_longer_candidates": sorted(head_candidates - set(candidates), key=P.natural),
        "candidates_lost_by_part": lost, "candidates_lost_columns": ["gene", "candidates by the table's own column that the scan's rule no longer gives the part"],
    }


def family_level(f, by_family, known_to_all, families, scan=None):
    """One narrowest family's level (schema/MACHINE_DOSSIERS.md): (the family matched, its level, the scan's databases
    that a 'not in the table' rests on, or None). In order: some line carries it ('narrowest'); the number rule (it is
    numbered at or below what every group of lines carries in its own column: 'not in the table'); the database rule
    (a database the scan ran on every protein has a signature in it: 'not in the table'); else up the tree."""
    if by_family.get(f):
        return f, "narrowest", None
    if f <= known_to_all:
        return None, "not in the table", None
    through = scan.settles(f) if scan else []
    if through:
        return None, "not in the table", through
    chain = sorted((a for a in families.above(f) if families.names.get(a, {}).get("type") == "Family"), key=lambda a: -len(families.above(a)))
    hit = next((a for a in chain if by_family.get(a)), None)
    return hit, ("broader" if hit else "cannot tell"), None


def search_own_body(lineage_taxon):
    return {"query": {"type": "terminal", "service": "text", "parameters": {"attribute": "rcsb_entity_source_organism.taxonomy_lineage.id", "operator": "exact_match", "value": str(lineage_taxon)}},
            "return_type": "entry", "request_options": {"results_content_type": ["experimental"], "sort": [{"sort_by": "rcsb_entry_info.resolution_combined", "direction": "asc"}], "return_all_hits": True}}


def fetch_own(datasets, species, block, refresh):
    """The species' own entries: a search of the Protein Data Bank by its taxon alone, and what
    each entry holds. An empty answer (no entry) is kept as a record of the search."""
    folder, failed = block["rcsb"], 0
    name = "search_own.json"
    if refresh or not (Path(datasets) / folder / name).exists():
        body = search_own_body(block["lineage"][0])
        status, ctype, content = ask(SEARCH, body)
        role = f"RCSB's search for every experimental entry with a polymer entity from an organism under taxon {block['lineage'][0]} ({block['lineage'][1]}), best resolution first, every hit"
        if status == 204:
            # RCSB answers 204 with no body where nothing matches: the tool writes that answer down.
            content, ctype = json.dumps({"total_count": 0, "result_set": []}).encode(), "application/json"
            role += "; RCSB answered 204 (no content), so no entry matched, and this file was written by the tool to record that answer"
        elif status != 200:
            print(f"{status}  {folder}/{name}")
            return 1
        save(datasets, folder, name, SEARCH, role, body, content, ctype, RCSB_RECORD, status=status)
        print(f"200  {folder}/{name}")
    found = json.loads((Path(datasets) / folder / name).read_text(encoding="utf-8"))
    ids = [row["identifier"] for row in found.get("result_set") or []]
    for k in range(0, len(ids), BATCH):
        part = f"entries_own_{k // BATCH:02d}.json"
        if (Path(datasets) / folder / part).exists() and not refresh:
            continue
        body = {"query": ENTRY_QUERY, "variables": {"ids": ids[k:k + BATCH]}}
        status, ctype, content = ask(GRAPHQL, body)
        if status != 200 or b'"errors"' in content[:200]:
            print(f"{status}  {folder}/{part}")
            failed += 1
            continue
        save(datasets, folder, part, GRAPHQL, f"RCSB's data service: what the species' own entries hold ({len(ids[k:k + BATCH])} entries)", body, content, ctype, RCSB_RECORD)
        print(f"200  {folder}/{part}")
        time.sleep(1)
    return failed


def own_entries(d, block):
    folder = block["rcsb"]
    found = json.loads(d.text(folder, "search_own.json"))
    ids = [row["identifier"] for row in found.get("result_set") or []]
    out = {}
    for k in range(0, len(ids), BATCH):
        answer = json.loads(d.text(folder, f"entries_own_{k // BATCH:02d}.json"))
        for entry in answer["data"]["entries"]:
            out[entry["rcsb_id"]] = entry_facts(entry, block["lineage"][0])
    return out, d.day(folder, "search_own.json")


def family_dossier(d, config, kinds, species, block, machine_ref, reference, families, table, own, own_day, by_protein, sources, scan=None):
    atlas = block["atlas"]
    kind = kinds[machine_ref["kind"]]
    ref_proteome = reference["proteome"]
    by_family, own_family, newest = lines_by_family(table, atlas, scan)
    # InterPro numbers its entries in order. The table's lines were scanned by more than one source
    # (gene models by one, UniProt's entries by another), maybe at different releases; an entry
    # numbered above the highest one that every group of lines carries is taken to be newer than at
    # least one of the scans, so that its absence there says nothing.
    known_to_all = min(newest.values()) if newest else ""
    rows_by_id = {row[atlas["id"]]: row for row in table}
    accession_to_id = {}
    for row in table:
        for column in atlas.get("accessions") or []:
            for accession in (row.get(column) or "").split(";"):
                if accession.strip():
                    accession_to_id.setdefault(accession.strip(), row[atlas["id"]])
    parts_ref = [dict(zip(machine_ref["proteins"]["columns"], r)) for r in machine_ref["proteins"]["rows"]]
    parts_ref = [p for p in parts_ref if p["tier"] != "named"]
    looked, candidates = [], {}
    # With a scan: the families whose level rests on it (and through which databases), the family rows whose level it
    # changed from what the table's own column gives, and the candidates the table's own column alone gives.
    rests_on_scan, changed, head_candidates, scan_used, lost = {}, [], set(), set(), []
    for part in parts_ref:
        fams = families.narrowest(ref_proteome.interpro.get(part["id"], []))
        # A family that no line of the species' table carries may be one its signatures' scan never
        # knew (the table's scan can be of an older InterPro release than the reference's): the search
        # then goes up the family's tree to the nearest Family that some line carries, and says so.
        # Where no Family of the chain is carried by any line, the part is "cannot tell".
        used, levels, head_found = [], [], set()
        for f in fams:
            hit, level, through = family_level(f, by_family, known_to_all, families, scan)
            levels.append([f, families.names[f]["name"], hit, families.names[hit]["name"] if hit else None, level])
            if hit:
                used.append(hit)
            if scan:
                was_hit, was, _ = family_level(f, own_family, known_to_all, families)
                head_found.update(own_family.get(was_hit, []) if was_hit else [])
                if not through and hit and not own_family.get(hit):
                    through = sorted({name for i in by_family[hit] for name in scan.added.get(i, {}).get(hit, [])})
                if through:
                    rests_on_scan[f] = [f, level, through]
                    scan_used.update(through)
                if was != level:
                    changed.append([part["gene"], f, was, level])
        found = sorted({i for f in used for i in by_family.get(f, [])}, key=P.natural)
        if scan:
            head_candidates.update(head_found)
            if head_found - set(found):
                lost.append([part["gene"], sorted(head_found - set(found), key=P.natural)])
        outcome = "no family signature" if not fams else ("candidates" if found else ("cannot tell" if any(level[4] == "cannot tell" for level in levels) else "not in the table"))
        looked.append({"reference": part["id"], "gene": part["gene"], "tier": part["tier"], "families": levels, "candidates": found, "outcome": outcome})
        for i in found:
            item = candidates.setdefault(i, {"families": set(), "stands_for": set(), "broader": False, "own": False, "through": set()})
            item["families"].update(f for f in used if i in by_family.get(f, []))
            item["stands_for"].add(part["gene"])
            item["broader"] = item["broader"] or any(level[4] == "broader" and i in by_family.get(level[2], []) for level in levels)
            for f in used:
                if i in own_family.get(f, []):
                    item["own"] = True
                elif scan and i in by_family.get(f, []):
                    item["through"].update(scan.added[i][f])
    rows = []
    for i in sorted(candidates, key=P.natural):
        row = rows_by_id[i]
        how = "by a broader family" if candidates[i]["broader"] else "by the narrowest family"
        if scan and not candidates[i]["own"]:
            # Found only through entries the scan added: said in words, so that it is told apart from a candidate by the table's own entry.
            how += f", which only the entries the species' own scan added to its line carry ({', '.join(sorted(candidates[i]['through']))})"
        scan_used.update(candidates[i]["through"])
        rows.append([i, row.get(atlas.get("gene") or "", "") or None, row.get(atlas["label"]) or None, row.get(atlas["kind"]) if atlas.get("kind") else None,
                     sorted(candidates[i]["families"]), sorted(candidates[i]["stands_for"], key=lambda g: (P.natural(g.lower()), g)), (row.get(atlas["match"]) or None) if atlas.get("match") else None,
                     how])
        by_protein[i].append({"machine": kind["id"], "tier": "candidate by family"})
    covered = [x for x in looked if x["candidates"]]
    no_family = [x["gene"] for x in looked if not x["families"]]
    cannot = [x["gene"] for x in looked if x["outcome"] == "cannot tell"]
    not_in_table = [x["gene"] for x in looked if x["outcome"] == "not in the table"]
    held_ref = [x for x in looked if x["tier"] == "part"]
    # Where the species' own data marks a machine's proteins (Syn3A's genome record, by product names),
    # the two sets are set side by side: the mark is not the rule, and nothing is taken from it here.
    own_mark = None
    mark = (block.get("own_mark") or {})
    if kind["id"] in (mark.get("values") or {}):
        marked = {r[0] for r in mark["rows"] if (r[1] or {}).get(mark["mark"]) == mark["values"][kind["id"]]}
        found = set(candidates)
        own_mark = {"file": mark["file"], "mark": mark["mark"], "value": mark["values"][kind["id"]], "marked": len(marked), "both": len(marked & found),
                    "marked_only": sorted(marked - found, key=P.natural), "candidates_only": sorted(found - marked, key=P.natural)}
    out = {
        "kind": kind["id"], "label": kind["label"], "group": kind["group"], "group_proposed": kind["group"] in {g["id"] for g in config["groups_proposed"]},
        **({"plain": kind["plain"]} if kind.get("plain") else {}),
        "named": {
            "by": "family signature", "reference": block["reference"],
            "text": f"{len(rows)} of the species' proteins carry the narrowest InterPro family (or, where no line of the species' table carries that family, the nearest broader one that some line carries) of at least one of the {len(parts_ref)} parts of the {reference['label'].lower() if reference['label'] in ('Human', 'Mouse') else reference['label']}'s {kind['label'].lower() if kind['label'][1:].islower() else kind['label']}: candidates for {len(covered)} of those parts ({sum(1 for x in held_ref if x['candidates'])} of the {len(held_ref)} that the reference's entry holds). For {len(not_in_table)} no line of the species' table carries the family, which says what the table holds, not that the species lacks the protein; for {len(cannot)} the table can tell nothing, its scan being older than the family; {len(no_family)} have no family signature to look for.",
            "sources": ["interpro", "atlas_table", f"reference_{block['reference']}"],
        },
        "proteins": {"columns": ["id", "gene", "label", "kind", "families", "stands_for", "same_as", "how"], "rows": rows, "counts": {"candidate by family": len(rows)}},
        "looked_for": {"columns": ["reference", "gene", "tier", "families", "candidates", "outcome"], "family_columns": ["narrowest", "its name", "matched", "its name", "level"],
                       "rows": [[x["reference"], x["gene"], x["tier"], x["families"], x["candidates"], x["outcome"]] for x in looked],
                       "parts": len(looked), "with_candidates": len(covered), "not_in_the_table": not_in_table, "cannot_tell": cannot, "no_family": no_family, "scans_newest": dict(sorted(newest.items())),
                       "held_parts": len(held_ref), "held_parts_with_candidates": sum(1 for x in held_ref if x["candidates"]),
                       "note": "A part of the reference is 'part' (held by the reference's entry) or 'part by keyword' (named by its keyword and not held). Each of its narrowest families is matched as 'narrowest' (some line carries it), 'not in the table' (no line carries it, though every group of lines was scanned at a release that knew it: this says what the table holds, not that the species lacks the protein), 'broader' (it is newer than a scan of the table, so the nearest broader Family that some line carries is used) or 'cannot tell' (newer than a scan, and no broader Family is carried). scans_newest gives, for each group of lines, the highest InterPro entry it carries."},
        "join": {"atlas": atlas["table"], "by": f"the atlas's id ({atlas['id']})", "candidates": len(rows), "in_atlas": len(rows), "not_in_atlas": []},
    }
    if own_mark:
        out["own_mark"] = own_mark
    if scan:
        scan_words(out, scan, candidates, rests_on_scan, changed, head_candidates, lost, scan_used, sources)
    # The structure: the species' own entry where one holds enough of the candidates; else the reference's, said as of its organism.
    wanted = {a for i in candidates for column in atlas.get("accessions") or [] for a in (rows_by_id[i].get(column) or "").split(";") if a.strip()}
    lengths = {a: int(rows_by_id[i][atlas["length"]]) for i in candidates for column in atlas.get("accessions") or [] for a in (rows_by_id[i].get(column) or "").split(";") if a.strip() and str(rows_by_id[i].get(atlas["length"]) or "").isdigit()}
    own_here, left_out = leave_out(config, species, kind["id"], own) if wanted else (own, [])
    ranked = sorted(own_here.values(), key=lambda f: score(f, wanted, lengths)["key"]) if wanted else []
    best = ranked[0] if ranked and score(ranked[0], wanted, lengths)["present"] else None
    held_parts = set()
    if best:
        for entity in best["entities"]:
            for a in entity["accessions"] if entity["same_organism"] else []:
                if a in accession_to_id and accession_to_id[a] in candidates:
                    held_parts |= candidates[accession_to_id[a]]["stands_for"]
    # An own entry is the machine's where it holds candidates for at least half of the parts that have
    # candidates, and for at least two parts where the reference's machine has two or more.
    needed = max((len(covered) + 1) // 2, min(2, len(parts_ref)))
    use_own = bool(best) and len(covered) > 0 and len(held_parts) >= needed
    own_says = f"A search of the Protein Data Bank by the species' taxon ({block['lineage'][0]}, {block['lineage'][1]}) on {own_day} found {len(own)} entr{'y' if len(own) == 1 else 'ies'} of the species" + (f"; the best for this machine, {best['entry']}, holds candidates for {len(held_parts)} of the {len(covered)} parts with candidates." if best else ("; none holds a candidate of this machine." if own else "."))
    compared = [{"entry": c["id"], "by": c["by"], "rank": None, "note": "not an entry of the species, so not ranked here"} for c in (block.get("compare") or {}).get(kind["id"], [])]
    if use_own:
        out["structure"] = own_structure(d, block["datasets"], species, best, ranked, wanted, lengths, candidates, accession_to_id, rows_by_id, atlas, block, machine_ref, sources, own_says)
    else:
        ref = machine_ref.get("structure")
        out["structure"] = None
        out["structure_elsewhere"] = ({"organism": ref["organism"], "entry": ref["entry"], "title": ref["title"], "method": ref["method"], "resolution_A": ref["resolution_A"], "measurable": ref["measurable"], "file": ref["file"], "call": ref["measure"]["call"], "from": f"the {reference['label']} dossier's own structure: its parts are that species' proteins, by entity ids", "sources": [f"reference_{block['reference']}"]}
                                      if ref else None)
        if ref and ref.get("compared"):
            out["structure_elsewhere"]["reference_compared"] = ref["compared"]
        out["no_structure"] = ("None in hand of the species' own. " + own_says) if ref else ("None in hand. " + own_says + f" The {reference['label']} dossier names none either.")
        if compared and out["structure_elsewhere"]:
            out["structure_elsewhere"]["compared"] = compared
    if use_own and compared:
        out["structure"]["compared"] = compared
    if left_out:
        (out["structure"] if use_own else out).__setitem__("left_out", left_out)
    note_holds_more(config, species, kind["id"], out.get("structure"))
    return out


def own_structure(d, datasets, species, best, ranked, wanted, lengths, candidates, accession_to_id, rows_by_id, atlas, block, machine_ref, sources, own_says):
    """The measure call for the species' own entry: a candidate's entity is a part, named by the
    candidate's gene (or id); every other entity is left out. RNA chains gather.json names are parts."""
    parts, exclude, entities = defaultdict(list), [], []
    rna = {str(k): v for k, v in (block.get("rna_entities") or {}).get(best["entry"], {}).items()}
    # Where the reference's own structure groups its parts by sub-term or keyword (a ribosome's two subunits),
    # a candidate is measured in the group of the part it stands for.
    reference_structure = machine_ref.get("structure") or {}
    ref_groups = {e["gene"]: e["part"] for e in reference_structure.get("entities") or [] if e["role"] == "part" and e.get("gene")}
    ref_by_group = any(group not in {re.sub(r"[^A-Za-z0-9_-]", "_", gene) for gene in ref_groups} for group in ref_groups.values())
    for entity in best["entities"]:
        ids = [accession_to_id[a] for a in entity["accessions"] if entity["same_organism"] and a in accession_to_id and accession_to_id[a] in candidates]
        if ids:
            row = rows_by_id[ids[0]]
            groups = {ref_groups.get(gene) for gene in candidates[ids[0]]["stands_for"]} - {None}
            group = groups.pop() if len(groups) == 1 and ref_by_group else re.sub(r"[^A-Za-z0-9_-]", "_", row.get(atlas.get("gene") or "") or ids[0])
            role = "part (candidate by family)"
        elif entity["id"] in rna:
            if rna[entity["id"]]["description"] != entity["description"]:
                raise Breach(f"{best['entry']} entity {entity['id']} is {entity['description']!r}, not {rna[entity['id']]['description']!r} as gather.json says")
            group, role = rna[entity["id"]]["part"], "part (RNA)" if entity["same_organism"] else "part (RNA, of another organism by the entry's record)"
        else:
            group = None
            role = "left out: " + ("a nucleic acid" if "polypeptide" not in entity["type"] else ("another organism's protein" if not entity["same_organism"] else "a protein of the species that is no candidate of the machine"))
        (parts[group].append(entity["id"]) if group else exclude.append(entity["id"]))
        entities.append({"id": entity["id"], "description": entity["description"], "type": entity["type"], "accessions": entity["accessions"], "atlas_id": ids[0] if ids else None,
                         "organism": entity["organism"], "same_organism": entity["same_organism"], "copies": entity["copies"], "copies_in_assembly": entity["copies_in_assembly"],
                         "with_coordinates": entity["observed_share"], "of_protein": share_of_protein(entity, lengths) if ids else None, "role": role, "part": group})
    present = score(best, wanted, lengths)
    measurable = present["present"] > 0 and not present["equivalents"] < MEASURABLE * present["present"]
    key = f"pdb{best['entry'].lower()}"
    sources[key] = pdb_source(best)
    use_assembly = best["assembly_differs"]
    name, held = held_file(d, datasets, best["entry"], use_assembly, None, f"{species}/wwpdb-{machine_ref['kind']}-g")
    if held:
        tables = read_cif_tables(d.path(held[0], name))
        own_refs = defaultdict(list)
        for row in tables["_struct_ref."]:
            if row.get("db_name") == "UNP":
                own_refs[row.get("entity_id")].append(row.get("pdbx_db_accession"))
        described = {row.get("id") for row in tables["_entity."]}
        for entity in entities:
            if entity["id"] not in described:
                raise Breach(f"{best['entry']}: the file has no entity {entity['id']}")
            entity["file_reference"] = sorted(own_refs.get(entity["id"], [])) or None
            entity["file_agrees"] = None if not entity["accessions"] else bool(set(entity["accessions"]) & set(entity["file_reference"] or []))
    file_at = f"{held[0]}/{name}" if held else None
    frame = (reference_structure.get("measure") or {}).get("frame")
    frame = frame if frame and all(f in parts for f in frame) else None
    call = " ".join(["python3 -I tools/measure_particle.py --machine", f"DATASETS/{file_at}" if file_at else name] + ([f"--exclude {','.join(exclude)}"] if exclude else []) + [f"--part {g}={','.join(i)}" for g, i in parts.items()] + ([f"--frame-from {frame[0]} --frame-to {frame[1]}"] if frame else []) + ["--out OUT.json"])
    return {
        "entry": best["entry"], "title": best["title"], "method": best["method"] or None, "resolution_A": best["resolution_A"], "released": best["released"],
        "organism": "; ".join(sorted({e["organism"] for e in entities if e["same_organism"] and e["organism"]})) or None, "same_organism": True,
        "measurable": measurable,
        "measurable_says": f"It holds {present['present']} of the {len(wanted)} candidates' accessions sought, and their residues with coordinates add up to {present['equivalents']} whole proteins.",
        "own_search": own_says,
        "file": file_at, "file_to_fetch": None if file_at else name, "assembly": best["assembly_details"] if use_assembly else None,
        "entities": entities,
        "measure": {"exclude": exclude, "parts": dict(parts), "frame": frame, "call": call},
        "chosen_by": "first by the rule, among the species' own entries",
        "candidates": [{"entry": f["entry"], "method": f["method"], "resolution_A": f["resolution_A"], **{k: v for k, v in score(f, wanted, lengths).items() if k != "key"}} for f in ranked[:6]],
        "sources": [key],
    }


def build_family_species(d, datasets, config, kinds, species, block, built, families):
    block = {**block, "datasets": datasets}
    reference = built[block["reference"]]
    atlas = block["atlas"]
    table_file, table = read_table(species, atlas)
    scan = Scan(atlas["scan"], table_file, {row[atlas["id"]] for row in table}, families) if atlas.get("scan") else None
    own, own_day = own_entries(d, block)
    if block.get("own_mark"):
        shelves = read_json(ROOT / block["own_mark"]["file"])
        at = {name: i for i, name in enumerate(shelves["columns"])}
        block = {**block, "own_mark": {**block["own_mark"], "rows": [[row[at["id"]], row[at["marks"]]] for row in shelves["proteins"]]}}
    sources = {
        "interpro": {"text": f"InterPro, release {families.release}: each entry's name and type, and the tree of broader and narrower entries, read from the saved copies in {IPR}.", "url": "https://www.ebi.ac.uk/interpro/", "licence": "CC0 1.0", "class": "permissive"},
        "atlas_table": {"text": atlas["source"], "url": None, "licence": atlas["licence"], "class": "permissive"},
        f"reference_{block['reference']}": {"text": f"The {reference['label']} dossier (data/catalogue/dossiers/{block['reference']}.json): its machines' parts, their UniProt entries' InterPro signatures (UniProtKB, release {reference['proteome'].release}), and its structures, each with its own sources there.", "url": None, "licence": "CC BY 4.0 (UniProt) and CC0 1.0 (the Protein Data Bank), as the reference dossier's sources state", "class": "permissive"},
    }
    by_protein = defaultdict(list)
    wanted_kinds = block.get("machines") or "all"
    machines = []
    not_looked_for = []
    for machine_ref in reference["data"]["machines"]:
        if wanted_kinds != "all" and machine_ref["kind"] not in wanted_kinds:
            continue
        if not any(row[3] != "named" for row in machine_ref["proteins"]["rows"]):
            # The reference has no part of this machine to look for (only proteins named with it): nothing is looked for.
            not_looked_for.append({"kind": machine_ref["kind"], "why": f"The {reference['label'].lower() if reference['label'] in ('Human', 'Mouse') else reference['label']} dossier gives the machine no part, only proteins named with it, so there is no family to look for."})
            continue
        machines.append(family_dossier(d, config, kinds, species, block, machine_ref, reference, families, table, own, own_day, by_protein, sources, scan))
    species_file = read_json(ROOT / "data" / "species" / f"{species}.json")
    read_papers = {}
    for item in machines:
        counts = per_cell(d, config, species, block, {"kind": item["kind"], "per_cell": (block.get("per_cell") or {}).get(item["kind"], [])}, species_file, sources, read_papers)
        if counts:
            item["per_cell"] = counts
    return {
        "format": FORMAT, "route": "family",
        "species": species, "label": block["label"], "organism": block["organism"], "taxon": block["taxon"], "reference": block["reference"],
        "note": "Generated by visualizer/tools/gather_machines.py from data/catalogue/gather.json, the species' own proteins, InterPro's files, the reference species' dossier and the saved answers of the Protein Data Bank: do not edit. The contract is schema/MACHINE_DOSSIERS.md.",
        "rules": {
            "proteins": f"The species has no curated record of its machines, so each machine's proteins are looked for by family. Each part of the machine in the {reference['label']} dossier has its narrowest InterPro families (entries of the type Family under which no other Family entry of the same protein lies); a protein of the species whose signatures include one of them is a candidate for that part ('candidate by family'). A candidate is never called the part or a counterpart: a family says what a protein is like, not what it does in this cell. No protein is matched by a name." + (SCAN_RULE.format(tool=scan.tool, record=scan.record_file, added=scan.added_file) if scan else ""),
            "structure": f"The species' own entries are found by a search of the Protein Data Bank by its taxon alone; one is used where it holds candidates for at least half of the parts that have candidates, and for at least two parts where the reference's machine has two or more, ranked as the reference dossier ranks. Otherwise the machine has no structure of its own ('None in hand'), and the reference dossier's entry is named under structure_elsewhere, with its organism.",
            "join": f"Each candidate is a line of the atlas's own table ({atlas['table']}) by its id. by_protein gives, for each of them, the machines it is a candidate of.",
        },
        "made": {"generator": "visualizer/tools/gather_machines.py", "interpro": families.release, "atlas": table_file, "reference": f"data/catalogue/dossiers/{block['reference']}.json", **({"scan": scan.record_file} if scan else {})},
        "machines": machines,
        "not_looked_for": not_looked_for,
        "by_protein": {a: sorted(k, key=lambda item: item["machine"]) for a, k in sorted(by_protein.items(), key=lambda kv: P.natural(kv[0]))},
        "sources": dict(sorted(sources.items())),
    }


def build(datasets):
    config, kinds = load_config()
    d = P.Datasets(datasets)
    d.entry(*UNIPROT_TERMS)
    d.entry(*PDB_TERMS)
    ontology = load_ontology(d)
    out, built = {}, {}
    families = None
    for species, block in config["species"].items():
        if block.get("route") == "family":
            continue
        data, proteome = build_species(d, datasets, config, kinds, species, block, ontology, built)
        out[species] = data
        built[species] = {"data": data, "proteome": proteome, "label": block["label"]}
    for species, block in config["species"].items():
        if block.get("route") != "family":
            continue
        families = families or Families(d)
        out[species] = build_family_species(d, datasets, config, kinds, species, block, built, families)
    out = {species: out[species] for species in config["species"]}
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


def save(datasets, folder, name, url, role, body, content, content_type, record, extra=None, status=200):
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
        entry = {"name": file_name, "url": file_url, "method": ("POST" if file_url and body is not None else ("GET" if file_url else None)), "role": file_role, "retrieved_utc": when, "http_status": status if file_url else None, "content_type": file_type, "size_bytes": (path / file_name).stat().st_size, "sha256": sha, "ok": True, "error": None, **((extra or {}) if file_url else {})}
        manifest["files"] = sorted([f for f in manifest["files"] if f["name"] != file_name] + [entry], key=lambda f: f["name"])
    manifest["record"] = record
    manifest["manifest_written_utc"] = when
    manifest["note"] = f"Added by {MINE}: asked of the source by {TOOL} of the Cells checkout with a generic client name, kept as untrusted data and read only by that tool's own code with python3 -I. Nothing here was run."
    manifest_path.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


KEYWORDS_RECORD = {"what": "UniProtKB: the keywords of every reviewed entry of the species' reference proteome, which the saved copy of its entries does not give", "licence": "CC BY 4.0 (UniProt's licence page, saved in human/uniprot-docs-and-terms/)"}
PAPERS_RECORD = {"what": "Open papers found through Europe PMC, each as its record (with the licence Europe PMC states for it) and its full text, read by tools/gather_machines.py for the numbers per cell that data/catalogue/gather.json names, with where each stands; no text, figure or data file of them is taken", "licence": "Each paper's own, as its record states; numbers only are taken"}
SUBUNIT_RECORD = {"what": "UniProtKB: the SUBUNIT comment of every reviewed entry of the species' reference proteome, which says what the protein forms with copies of itself and with others", "licence": "CC BY 4.0 (UniProt's licence page, saved in human/uniprot-docs-and-terms/)"}
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
        extra = (block.get("uniprot") or {}).get("keywords")
        if extra and not (Path(datasets) / extra / keywords_file(block)).exists():
            query = proteome_query(block)
            url = f"{UNIPROT}?query={P.q(query)}&compressed=true&format=tsv&fields=accession,keyword"
            call = urllib.request.Request(url, headers={"User-Agent": CLIENT, "Accept-Encoding": "identity"})
            with urllib.request.urlopen(call, timeout=1800) as answer:
                content, ctype, release = answer.read(), answer.headers.get("Content-Type"), answer.headers.get("X-UniProt-Release")
            if not P.whole_gzip(content):
                raise Breach("UniProt's answer is not a whole gzip file")
            save(datasets, extra, keywords_file(block), url, "the keywords of every " + ("reviewed " if uniprot_scope(block) == "reviewed" else "") + "entry of the proteome", None, content, ctype, KEYWORDS_RECORD, extra={"x_uniprot_release": release})
            print(f"200  {extra}/{keywords_file(block)}")
            d = P.Datasets(datasets)
        numbers = [item for machine in (block.get("machines") if block.get("route") != "family" else None) or [] for item in machine.get("per_cell") or []] + [item for items in (block.get("per_cell") or {}).values() for item in items] if block.get("route") == "family" else [item for machine in block.get("machines") or [] for item in machine.get("per_cell") or []]
        for key in sorted({item["source"] for item in numbers if "source" in item}):
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
        extra = (block.get("uniprot") or {}).get("subunit")
        if extra and not (Path(datasets) / extra / subunit_file(block)).exists():
            query = proteome_query(block)
            url = f"{UNIPROT}?query={P.q(query)}&compressed=true&format=tsv&fields=accession,cc_subunit"
            call = urllib.request.Request(url, headers={"User-Agent": CLIENT, "Accept-Encoding": "identity"})
            with urllib.request.urlopen(call, timeout=1800) as answer:
                content, ctype, release = answer.read(), answer.headers.get("Content-Type"), answer.headers.get("X-UniProt-Release")
            if not P.whole_gzip(content):
                raise Breach("UniProt's answer is not a whole gzip file")
            save(datasets, extra, subunit_file(block), url, "the SUBUNIT comment of every " + ("reviewed " if uniprot_scope(block) == "reviewed" else "") + "entry of the proteome", None, content, ctype, SUBUNIT_RECORD, extra={"x_uniprot_release": release})
            print(f"200  {extra}/{subunit_file(block)}")
            d = P.Datasets(datasets)
        for item in block.get("downloads") or []:
            if (Path(datasets) / item["folder"] / item["name"]).exists() and not refresh:
                continue
            if item.get("source") and not source_used(config, item["source"]):
                print(f"held     {item['folder']}/{item['name']}: gather.json holds {item['source']}")
                continue
            status, ctype, content = ask(item["url"])
            if status != 200 or not content:
                print(f"{status}  {item['folder']}/{item['name']}")
                failed += 1
                continue
            save(datasets, item["folder"], item["name"], item["url"], item["role"], None, content, ctype, {"what": item["what"], "licence": item["licence"]})
            print(f"200  {item['folder']}/{item['name']}")
            time.sleep(1)
        if block.get("route") == "family":
            failed += fetch_own(datasets, species, block, refresh)
            continue
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
                    print(f"nothing to search for {species} {kind}: no entry carries its term")
                    continue
                body = search_body(accessions, block["lineage"][0])
                status, ctype, content = ask(SEARCH, body)
                role = f"RCSB's search for {kind}: experimental entries with a polymer entity mapped to one of {len(accessions)} UniProt accessions, from an organism under taxon {block['lineage'][0]}, best resolution first, every hit"
                if status == 204:
                    # RCSB answers 204 with no body where nothing matches: the tool writes that answer down.
                    content, ctype = json.dumps({"total_count": 0, "result_set": []}).encode(), "application/json"
                    role += "; RCSB answered 204 (no content), so no entry matched, and this file was written by the tool to record that answer"
                elif status != 200:
                    print(f"{status}  search {species} {kind}")
                    failed += 1
                    continue
                save(datasets, folder, answer, SEARCH, role, body, content, ctype, RCSB_RECORD, status=status)
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
    if species_only and config["species"][species_only].get("route") == "family":
        block = config["species"][species_only]
        reference = block["reference"]
        data, proteome = build_species(d, datasets, config, kinds, reference, config["species"][reference], ontology)
        family = build_family_species(d, datasets, config, kinds, species_only, block, {reference: {"data": data, "proteome": proteome, "label": config["species"][reference]["label"]}}, Families(d))
        for item in family["machines"]:
            s = item.get("structure")
            if not s or not s.get("file_to_fetch") or (kinds_only and item["kind"] not in kinds_only):
                continue
            name, folder = s["file_to_fetch"], f"{species_only}/wwpdb-{item['kind']}-g"
            status, ctype, content = ask(f"{FILES}/{name}")
            if status != 200 or not P.whole_gzip(content):
                print(f"{status}  {folder}/{name}")
                failed += 1
                continue
            save(datasets, folder, name, f"{FILES}/{name}", "the entry's mmCIF file, as the PDB archive serves it" + ("; its first biological assembly" if s["assembly"] else ""), None, content, ctype, PDB_RECORD,
                 extra={"entry": s["entry"], "title": s["title"], "method": s["method"], "resolution_A": s["resolution_A"], "organisms": sorted({e["organism"] for e in s["entities"] if e["organism"]}), "organisms_from": "the entry's source records as RCSB's data service serves them (rcsb_entity_source_organism)", "chosen": f"first by {TOOL}'s rule among the species' own entries"})
            print(f"200  {folder}/{name}")
            time.sleep(1)
        print(f"{failed} failed")
        return failed
    for species, block in config["species"].items():
        if species_only and species != species_only:
            continue
        if block.get("route") == "family":
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
