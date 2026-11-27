#!/usr/bin/env python3
"""Create the DS2 Protein atlas from a UniProtKB UP000008243 TSV export."""

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path


PROTEOME = "UP000008243"
GROUPS = [
    ("surface", "S-layer, pili and motility", r"s-layer|cell surface glycoprotein|pilin|archaell|flagellin|twitching motility"),
    ("shape", "Cell shape and division", r"cetz|cell division|ftsz|sep[fF]|halofilin|volactin|bactofilin"),
    ("translation", "Translation", r"ribosom|translation factor|aminoacyl.trna|trna synthetase"),
    ("nucleic", "DNA and RNA", r"polymerase|transcription|helicase|nuclease|recombinase|replication|rna-binding"),
    ("transport", "Membrane transport", r"transporter|permease|symporter|antiporter|efflux|importer|channel protein"),
    ("modification", "Protein maintenance and modification", r"chaperon|proteasom|protease|ubiquitin|protein kinase|methyltransferase"),
    ("metabolism", "Metabolism and energy", r"synthetase|synthase|dehydrogenase|transferase|reductase|isomerase|lyase|oxid|hydrolase|kinase|phosphatase"),
    ("other", "Other annotations", r".*"),
]
CLASSIFIERS = [(key, re.compile(pattern, re.I)) for key, _, pattern in GROUPS]


def location(text):
    words = text.partition("Note=")[0].lower()
    if re.search(r"\b(?:single-pass|multi-pass|transmembrane)\b", words):
        side = "in"
    elif re.search(r"\b(?:s-layer|secreted|extracellular)\b", words):
        side = "outside"
    elif re.search(r"\b(?:cytoplasm|cytosol)\b", words):
        side = "inside"
    else:
        return "not known", "none"
    return side, "stated"


def catalogue(table, release, date):
    with table.open(encoding="utf-8", newline="") as stream:
        source = list(csv.DictReader(stream, delimiter="\t"))
    if not source or len({row["Entry"] for row in source}) != len(source):
        raise ValueError("The UniProtKB table must hold distinct protein accessions.")
    proteins, counts, reviews = [], Counter(), Counter()
    for row in sorted(source, key=lambda item: item["Entry"]):
        name = row["Protein names"].split(" (EC ", 1)[0]
        gene = row["Gene Names (primary)"] or row["Gene Names (ordered locus)"]
        review = row["Reviewed"]
        if review not in {"reviewed", "unreviewed"}:
            raise ValueError(f"{row['Entry']} has an unrecognised UniProtKB review status")
        side, basis = location(row["Subcellular location [CC]"])
        group = next(key for key, pattern in CLASSIFIERS if pattern.search(name))
        marks = {"review": review}
        if row["Gene Names (ordered locus)"]:
            marks["locus"] = row["Gene Names (ordered locus)"]
        proteins.append([row["Entry"], name, gene, "cell", side, basis, group, int(row["Length"]), None, marks])
        counts[side] += 1
        reviews[review] += 1
    return {
        "format": "cells.visualizer.species_proteins@1",
        "species": "haloferax",
        "label": "Haloferax",
        "organism": "Haloferax volcanii DS2",
        "made": date,
        "from": f"UniProtKB {release}, DS2 reference proteome {PROTEOME}: {len(proteins):,} entries, {reviews['reviewed']:,} reviewed and {reviews['unreviewed']:,} unreviewed.",
        "from_counts": {**reviews, "entries": len(proteins)},
        "shelves": [{"id": "cell", "label": "Cytoplasmic membrane", "outside": "Cell surface and outside", "inside": "Cytoplasm"}],
        "groups": [{"id": key, "label": heading, "from": "Viewer groups by UniProtKB protein names"} for key, heading, _ in GROUPS],
        "columns": ["id", "label", "gene", "shelf", "side", "basis", "group", "length", "unit", "marks"],
        "marks": {
            "review": {"label": "UniProtKB curation", "values": ["reviewed", "unreviewed"], "search": True, "source": "UniProtKB",
                       "words": {"reviewed": "Manually reviewed", "unreviewed": "Automatically annotated"}},
            "locus": {"label": "DS2 locus", "search": True, "source": "UniProtKB"},
        },
        "proteins": proteins,
        "counts": dict(counts),
        "unit_note": "The atlas records the DS2 proteome and UniProtKB annotations.",
        "method": [
            "The reference proteome includes both reviewed and unreviewed UniProtKB entries.",
            "Shelf placement uses explicit terms in the UniProtKB location field. Protein-name groups help navigation.",
        ],
        "sources": [{
            "name": "UniProtKB",
            "cite": f"UniProt Consortium, UniProtKB release {release}, reference proteome {PROTEOME}.",
            "url": f"https://www.uniprot.org/proteomes/{PROTEOME}",
            "licence": "CC BY 4.0",
            "class": "permissive",
            "accessed": date,
            "holds": "Accessions, protein and gene names, loci, lengths, curation status and location annotations.",
        }],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("table", type=Path)
    parser.add_argument("--release", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    data = catalogue(args.table, args.release, args.date)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
