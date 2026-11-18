#!/usr/bin/env python3
"""Hold every machine file's sources to the copies they were read from (schema/MACHINES.md).

For each file in data/machines/:

- a permissive source's saved full text is there, its record beside it still states the
  licence the file gives (Europe PMC's "cc by" for "CC BY"), and every sentence of the file
  that names the source stands in that text, word for word once white space is set aside;
- UniProt's sentence of names agrees with the species' own proteins table in the tree;
- an open paper whose numbers alone are taken (`standing: open paper, numbers only`) is
  saved with a MANIFEST that says it is kept for analysis and not redistributed, and each
  term a number is found by (`read.find`) stands in its text. The file holds no sentence of
  it, and neither does this tool;
- each entry of the Protein Data Bank the file takes a value from (`structures`) is saved,
  under the folder its `pdb` source names, with the title and organisms the file gives, as
  that folder's MANIFEST records them from each entry's own record; and the PDB's terms are
  saved where the source says.

It writes nothing, uses the standard library alone, and parses the saved XML itself: the
downloads are data, never run.

    python3 tools/check_machine_sources.py [--datasets DIR]     (DIR holds every species' downloads)
"""
import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MACHINES = ROOT / "data" / "machines"
norm = lambda text: " ".join(text.split())
LICENCE_IN_RECORD = {"CC BY": "cc by", "CC BY 4.0": "cc by", "CC0": "cc0"}


def text_of(path):
    """The words of a JATS full text: its paragraphs, titles and table cells."""
    root = ET.parse(path).getroot()
    return norm(" ".join("".join(el.itertext()) for el in root.iter() if el.tag.split("}")[-1] in ("p", "title", "td", "th")))


def check(machine_file, datasets):
    machine = json.loads(machine_file.read_text(encoding="utf-8"))
    problems, done = [], 0
    where = machine_file.name
    texts = {}
    for key, source in machine["sources"].items():
        saved = source.get("saved", "")
        if not saved.endswith(".xml"):
            continue
        path = datasets / saved
        if not path.exists():
            problems.append(f"{where}: {key}: its saved text {saved} is not there")
            continue
        texts[key] = text_of(path)
        if source.get("standing") == "open paper, numbers only":
            manifest = path.parent / "MANIFEST.json"
            note = json.loads(manifest.read_text(encoding="utf-8")).get("note", "") if manifest.exists() else ""
            if "not redistributed" not in note:
                problems.append(f"{where}: {key}: its folder's MANIFEST does not say it is kept for analysis and not redistributed")
            continue
        record = path.parent / f"{key}_record.json"
        if not record.exists():
            problems.append(f"{where}: {key}: no record beside its text, so its licence cannot be read")
            continue
        found = (json.loads(record.read_text(encoding="utf-8")).get("resultList", {}).get("result") or [{}])[0].get("license")
        if found != LICENCE_IN_RECORD.get(source.get("licence")):
            problems.append(f"{where}: {key}: its record states the licence {found!r}, not the file's {source.get('licence')!r}")
    tsv = {}
    table = ROOT / "data" / "proteins" / machine["species"] / "proteins.tsv"
    if table.exists():
        lines = table.read_text(encoding="utf-8").splitlines()
        head = lines[0].split("\t")
        tsv = {row["id"]: row for row in (dict(zip(head, line.split("\t"))) for line in lines[1:])}
    for key, sentence in machine["sentences"].items():
        source = machine["sources"].get(sentence["source"], {})
        if sentence["source"] == "uniprot":
            for acc, name in re.findall(r'\b([OPQ][0-9][A-Z0-9]{3}[0-9])\s+"([^"]+)"', sentence["text"]):
                if tsv.get(acc, {}).get("name") != name:
                    problems.append(f"{where}: {key}: {acc} is named {tsv.get(acc, {}).get('name')!r} in the species' table, not {name!r}")
            done += 1
            continue
        if source.get("standing") == "open paper, numbers only":
            problems.append(f"{where}: {key}: a sentence of {sentence['source']}, whose numbers alone may be taken")
            continue
        if sentence["source"] in texts:
            if norm(sentence["text"]) not in texts[sentence["source"]]:
                problems.append(f"{where}: {key}: {sentence['source']}'s saved text no longer holds the sentence")
            done += 1

    def reads(node):
        if isinstance(node, dict):
            if isinstance(node.get("read"), dict):
                yield node["read"]
            for value in node.values():
                yield from reads(value)
        elif isinstance(node, list):
            for value in node:
                yield from reads(value)

    pdb = machine["sources"].get("pdb")
    if machine.get("structures"):
        manifest = datasets / (pdb or {}).get("saved", "")
        if not pdb or not manifest.is_file():
            problems.append(f"{where}: values from structures, and no saved MANIFEST of them ({(pdb or {}).get('saved')})")
        else:
            saved = {item.get("entry"): item for item in json.loads(manifest.read_text(encoding="utf-8")).get("files", [])}
            for item in machine["structures"]:
                record = saved.get(item["entry"])
                if not record or not (manifest.parent / record["name"]).is_file():
                    problems.append(f"{where}: the entry {item['entry']} is not saved")
                elif record.get("title") != item.get("title") or sorted(record.get("organisms", [])) != sorted(item.get("organisms", [])):
                    problems.append(f"{where}: {item['entry']}'s title or organisms differ from its record as saved")
                done += 1
            if not (datasets / pdb.get("terms", "")).is_file():
                problems.append(f"{where}: the Protein Data Bank's terms are not saved at {pdb.get('terms')}")
    for read in reads(machine):
        for term in read.get("find", []):
            if term not in texts.get(read["source"], ""):
                problems.append(f"{where}: {read['source']}'s saved text does not hold {term!r}, which a number is found by")
            done += 1
    return problems, done


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--datasets", default=os.environ.get("ECOLI_DATASETS", "/mnt/datasets/Cells"))
    args = parser.parse_args()
    datasets = Path(args.datasets)
    problems, done = [], 0
    files = sorted(MACHINES.glob("*.json"))
    for machine_file in files:
        found, count = check(machine_file, datasets)
        problems += found
        done += count
    print(f"{len(files)} machine file(s), {done} sentences and terms checked against the saved copies")
    for line in problems:
        print(f"FAIL  {line}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
