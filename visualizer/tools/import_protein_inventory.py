#!/usr/bin/env python3
"""Make the viewer's slim copy of the Cells law inventory.

The inventory is stage 2 of docs/PROTEIN_CATALOGUE_PLAN.md: every engine law that acts on
a functional unit (a channel, a pump, a junction channel), with its candidate gene
products, its assembly and the kind of evidence behind it. It is saved as evidence
outside the repository. The protein atlas view needs a small part of it inside the page,
so this tool writes a read-only snapshot under data/proteins/.

It is a snapshot of an inventory, not a catalogue: the catalogue's design (stage 3) has
not begun and belongs to the engine.

    python3 tools/import_protein_inventory.py --inventory PATH/law_inventory_v2.json

Left out on purpose: machine paths, Xenbase identifiers, and every field the view does
not show. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAPSHOT_FORMAT = "cells.visualizer.protein_inventory_snapshot@1"
ACCEPTED = {"cells.protein_catalogue.law_inventory@2"}
PATHS = re.compile(r"/(?:home|mnt|Users)/")
PDB = re.compile(r"PDB (\d[A-Z0-9]{3})")


def clean(value):
    """The value without empty members, so the snapshot holds only what is stated."""
    if isinstance(value, dict):
        out = {key: clean(item) for key, item in value.items()}
        return {key: item for key, item in out.items() if item not in (None, "", [], {})}
    if isinstance(value, list):
        return [clean(item) for item in value]
    return value


def access(method, pattern):
    for line in method:
        match = re.search(pattern, line)
        if match:
            return match.group(1)
    return None


def unit_record(unit):
    statuses = sorted(set(unit["law_statuses"]))
    if len(statuses) != 1:
        raise SystemExit(f"{unit['id']}: laws of several statuses {statuses}; decide how the view shows that")
    assembly = unit.get("assembly") or {}
    return {
        "id": unit["id"],
        "name": unit["name"],
        "kind": unit["kind"],
        "status": statuses[0],
        "laws": unit["laws"],
        "products": [
            {"gene": product["gene"], "role": product.get("role"), "human_uniprot": product.get("human_uniprot")}
            for product in unit.get("candidate_products") or []
        ],
        "assembly": {"stoichiometry": assembly.get("stoichiometry"), "sources": assembly.get("sources") or []},
        "note": unit.get("note"),
    }


def law_record(law):
    coefficients = law.get("coefficients") or {}
    published = coefficients.get("published_model") or {}
    return {
        "id": law.get("law_id"),
        "identity": law.get("identity"),
        "record_type": law["record_type"],
        "file": law["file"],
        "unit": law["functional_unit"],
        "also_in": law.get("also_in"),
        "status": law["status"],
        "evidence_kind": law.get("evidence_kind"),
        "ion_routes": law.get("ion_routes"),
        "coefficients": coefficients.get("source"),
        "published": {
            "citation": published.get("citation"),
            "organism": published.get("organism"),
            "cell_type": published.get("cell_type"),
            "preparation": published.get("preparation"),
            "pmid": published.get("pmid"),
        },
        # Anchors are dropped: the viewer links to the document, not into it.
        "docs": sorted({path.split("#")[0] for path in coefficients.get("cells_docs") or []}),
        "notes": law.get("notes"),
    }


def product_record(record):
    human = record.get("human") or {}
    return {
        "human": {"accession": human.get("accession"), "protein_name": human.get("protein_name"), "length": human.get("length")},
        # UniProt entries found by gene name. Xenbase identifiers are not copied.
        "xenopus_laevis": [
            {"accession": entry["accession"], "reviewed": bool(entry.get("reviewed")), "gene": entry.get("gene_names")}
            for entry in record.get("xenopus_laevis") or []
        ],
    }


def structure_record(entry):
    assembly = entry.get("assembly_1") or {}
    symmetry = (assembly.get("symmetry") or [[None, None, None]])[0]
    citation = entry.get("citation") or {}
    return {
        "pdb": entry["pdb"],
        "title": entry.get("title"),
        "method": entry.get("method") or [],
        "resolution_A": entry.get("resolution_A"),
        "released": entry.get("released"),
        "assembly": {"copies": assembly.get("oligomeric_count"), "kind": symmetry[1], "symmetry": symmetry[2]},
        "citation": {
            "title": citation.get("title"),
            "journal": citation.get("journal_abbrev"),
            "year": citation.get("year"),
            "doi": citation.get("pdbx_database_id_DOI"),
            "pmid": citation.get("pdbx_database_id_PubMed"),
        },
        "entities": [
            {
                "description": item.get("description"),
                "uniprot": item.get("uniprot") or [],
                "organism": item.get("organism") or [],
                "copies": item.get("copies_in_assembly_1"),
            }
            for item in entry.get("entities") or []
        ],
    }


def build(inventory):
    kind = inventory.get("kind")
    if kind not in ACCEPTED:
        raise SystemExit(f"{kind}: not an inventory this tool knows ({', '.join(sorted(ACCEPTED))})")
    method = inventory.get("method") or []
    units = [unit_record(unit) for unit in inventory["functional_units"]]
    laws = [law_record(law) for law in inventory["laws"]]
    cited = {gene for unit in units for gene in (product["gene"] for product in unit["products"])}
    products = {gene: product_record(record) for gene, record in sorted(inventory["gene_products"].items()) if gene in cited}
    # Only the structures a unit's assembly cites are shown, so only those are kept.
    shown = {pdb for unit in units for source in unit["assembly"]["sources"] for pdb in PDB.findall(source)}
    structures = [structure_record(entry) for entry in inventory["structure_exemplars"] if entry["pdb"] in shown]
    absent = sorted(shown - {entry["pdb"] for entry in structures})
    if absent:
        raise SystemExit(f"an assembly cites structures the inventory has no record of: {absent}")

    counts = inventory["counts"]
    checks = {
        "functional units": (len(units), counts["functional_units"]),
        "records": (len(laws), counts["records"]),
        "units by status": (dict(Counter(unit["status"] for unit in units)), counts["functional_units_by_status"]),
        "laws by status": (
            dict(Counter(law["status"] for law in laws if law["record_type"] == "law")),
            counts["laws_by_status"],
        ),
    }
    for name, (found, stated) in checks.items():
        if found != stated:
            raise SystemExit(f"{name}: the inventory states {stated}, its records give {found}")
    missing = sorted(cited - set(products))
    if missing:
        raise SystemExit(f"candidate genes without a product record: {missing}")

    uniprot_release = access(method, r"release (\d{4}_\d{2})")
    uniprot_date = access(method, r"rest\.uniprot\.org.*accessed (\d{4}-\d{2}-\d{2})")
    rcsb_date = access(method, r"RCSB.*accessed (\d{4}-\d{2}-\d{2})")
    snapshot = {
        "format": SNAPSHOT_FORMAT,
        "note": (
            "A slim, read-only copy of the Cells law inventory, made for the viewer by "
            "visualizer/tools/import_protein_inventory.py. It is not a catalogue: the catalogue's design "
            "(docs/PROTEIN_CATALOGUE_PLAN.md, stage 3) has not begun. Do not edit; run the tool again."
        ),
        "inventory": {
            "kind": kind,
            "created": inventory.get("created_utc"),
            "read_at_revision": (inventory.get("source_revision") or "")[:7],
            "scope": inventory.get("scope"),
            "status_vocabulary": inventory.get("status_vocabulary"),
            "counts": {
                key: counts[key]
                for key in (
                    "records", "laws", "model_records", "functional_units", "laws_by_status",
                    "functional_units_by_status", "assigned_laws_by_evidence_kind", "candidate_genes",
                    "candidate_genes_with_xenopus_laevis_entry",
                )
            },
        },
        "sources": [
            {
                "name": "Cells law inventory",
                "holds": "functional units, laws, statuses, kinds of evidence, assembly statements and notes",
                "licence": "MIT, with the Cells repository",
            },
            {
                "name": "UniProt",
                "url": "https://www.uniprot.org/",
                "holds": "accessions, protein names and lengths of the candidate gene products: reviewed human entries, and Xenopus laevis entries found by gene name",
                "release": uniprot_release,
                "accessed": uniprot_date,
                "licence": "CC BY 4.0",
                "cite": "The UniProt Consortium, UniProt: the Universal Protein Knowledgebase in 2025, Nucleic Acids Res. 53:D609-D617 (2025)",
            },
            {
                "name": "RCSB Protein Data Bank",
                "url": "https://www.rcsb.org/",
                "holds": "titles, methods, resolutions, assembly copies and symmetries, and primary citations of the reference structures",
                "accessed": rcsb_date,
                "licence": "CC0 1.0",
                "cite": "each structure's primary citation is kept with it",
            },
        ],
        "not_copied": (
            "No Xenbase data, no Human Protein Atlas data and no AlphaFold models are copied. "
            "The view only links to those sites."
        ),
        "units": units,
        "laws": laws,
        "products": products,
        "structures": structures,
    }
    snapshot = clean(snapshot)
    text = json.dumps(snapshot, ensure_ascii=False)
    if PATHS.search(text):
        raise SystemExit("a machine path would be written to the snapshot; extend the import to leave it out")
    if "xenbase" in text.lower().replace("no xenbase data", ""):
        raise SystemExit("a Xenbase field would be written to the snapshot")
    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--inventory", required=True, help="the inventory JSON to read (law_inventory_v2.json)")
    parser.add_argument("--out", default=str(HERE.parent / "data" / "proteins" / "inventory.snapshot.json"))
    arguments = parser.parse_args()

    inventory = json.loads(Path(arguments.inventory).read_text(encoding="utf-8"))
    snapshot = build(inventory)
    out = Path(arguments.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snapshot, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    described = snapshot["inventory"]
    print(f"read {described['kind']} of {described['created']}, engine read at {described['read_at_revision']}")
    print(
        f"{len(snapshot['units'])} units, {len(snapshot['laws'])} law records, "
        f"{len(snapshot['products'])} gene products, {len(snapshot['structures'])} reference structures"
    )
    print(f"wrote {out.name} ({out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
