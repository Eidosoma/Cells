#!/usr/bin/env python3
"""Builds the Machines catalogue (schema/MACHINE_CATALOGUE.md): data/catalogue/catalogue.json.

Reads the hand-kept overlay (data/catalogue/overlay.json), the species files (data/species/),
the species' own proteins (data/proteins/<species>/shelves.json) and the machine files
(data/machines/), and writes one catalogue: the groups, the kinds of machine, and one entry for
each machine a species' record names, with what the records give of it: the words that name it,
a count, a size, the proteins its species' data marks with it, and its closer view where it has
one. Every number is copied with its sources from a species file: a fact, or a size the file states
for a part of its cell. Nothing is computed, no paper is read here, and nothing of the engine is run.

    python3 tools/build_catalogue.py              # writes data/catalogue/catalogue.json
    python3 tools/build_catalogue.py --out -      # to standard output
    python3 tools/build_catalogue.py --check      # fails if the file on disk is not what it would write

The output holds no clock time, so the same inputs give the same bytes.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORMAT = "cells.visualizer.machine_catalogue@1"
OVERLAY_FORMAT = "cells.visualizer.machine_catalogue_overlay@1"
OUT = ROOT / "data" / "catalogue" / "catalogue.json"


class Breach(Exception):
    pass


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def marked_proteins(species: str, mark: str, value: str):
    """The proteins of a species' own data that carry `mark` = `value`, with how the mark is given."""
    path = ROOT / "data" / "proteins" / species / "shelves.json"
    data = read(path)
    about = (data.get("marks") or {}).get(mark)
    if not about:
        raise Breach(f"{rel(path)} has no mark {mark}")
    items = []
    if "proteins" in data and "columns" in data:
        columns = data["columns"]
        for row in data["proteins"]:
            protein = dict(zip(columns, row))
            if (protein.get("marks") or {}).get(mark) == value:
                items.append([protein["id"], protein.get("gene"), protein.get("label")])
    else:
        highlights = data.get("highlights") or {}
        at = {name: index for index, name in enumerate(highlights.get("columns") or [])}
        for row in highlights.get("rows") or []:
            if row[at["mark"]] == mark and row[at["value"]] == value:
                items.append([row[at["id"]], row[at["gene"]], None])
    if not items:
        raise Breach(f"{rel(path)}: no protein carries {mark} = {value}")
    return {"mark": mark, "value": value, "from": rel(path), "label": about.get("label"), "by": about.get("note"), "source": about.get("source"), "items": items}


def fact(species_file: dict, label: str, where: str):
    for item in species_file["cell"].get("facts") or []:
        if item["label"] == label:
            return item
    raise Breach(f"{where}: the species file has no fact {label!r}")


def build():
    overlay_path = ROOT / "data" / "catalogue" / "overlay.json"
    overlay = read(overlay_path)
    if overlay.get("format") != OVERLAY_FORMAT:
        raise Breach(f"{rel(overlay_path)} is not {OVERLAY_FORMAT}")
    groups = {group["id"]: group for group in overlay["groups"]}
    kinds = {}
    for kind in overlay["kinds"]:
        if kind["group"] not in groups:
            raise Breach(f"the kind {kind['id']} names no group of the overlay: {kind['group']}")
        for line in kind.get("records") or []:
            key = line["ref"] if isinstance(line, dict) else line
            if key not in overlay["records"]:
                raise Breach(f"the kind {kind['id']} names no record of the overlay: {key}")
            if isinstance(line, dict) and not (line.get("status") and line.get("says")):
                raise Breach(f"the kind {kind['id']}: a record line of its own gives both its status and what it says")
        kinds[kind["id"]] = dict(kind)
    sources = {}
    entries = []
    inputs = {rel(overlay_path)}

    def cite(species: str, keys, species_file: dict, where: str):
        out = []
        for key in keys:
            source = (species_file.get("sources") or {}).get(key)
            if not source:
                raise Breach(f"{where}: {key} is not a source of the {species} file")
            sources[f"{species}:{key}"] = {name: source[name] for name in ("text", "doi", "url", "licence", "class", "standing", "where", "accessed") if name in source}
            out.append(f"{species}:{key}")
        return out

    for species, wanted in overlay["species"].items():
        species_path = ROOT / "data" / "species" / f"{species}.json"
        species_file = read(species_path)
        inputs.add(rel(species_path))
        seen = set()
        for item in wanted:
            kind = kinds.get(item["kind"])
            where = f"{species}, {item['kind']}"
            if not kind:
                raise Breach(f"{where}: no such kind")
            if item["kind"] in seen:
                raise Breach(f"{where}: listed twice")
            seen.add(item["kind"])
            entry = {"id": kind["id"], "species": species, "label": item.get("label") or kind.get("label")}
            # What names it: a capability's note of the species file, with that capability's sources, or a record of the viewer.
            named = item["named"]
            if "capability" in named:
                note = (species_file["cell"].get("capabilities") or {}).get(named["capability"])
                words = (note or {}).get("note") or (note or {}).get("why") or ""
                if named["word"] not in words:
                    raise Breach(f"{where}: {named['capability']} does not say {named['word']!r}")
                # The sentence that names it, not the whole note: the note may go on to other things.
                sentence = next(part for part in re.split(r"(?<=[.!?])\s+(?=[A-Z])", words) if named["word"] in part)
                entry["named"] = {"text": sentence, "word": named["word"], "capability": named["capability"], "file": rel(species_path), "sources": cite(species, (species_file.get("capability_sources") or {}).get(named["capability"], []), species_file, where)}
            else:
                record = overlay["records"][named["record"]]
                said = (ROOT.parent / record["path"]).read_text(encoding="utf-8") if record["path"].startswith("visualizer/") else ""
                if named["word"] not in said:
                    raise Breach(f"{where}: {record['path']} does not say {named['word']!r}")
                entry["named"] = {"word": named["word"], "record": named["record"]}
            # How many a cell has: a fact of the species file, whole, with its sources.
            if "count" in item:
                found = fact(species_file, item["count"]["fact"], where)
                entry["count"] = {"label": found["label"], "text": found["value"], "sources": cite(species, found["sources"], species_file, where)}
                if item["count"].get("says"):
                    entry["count"]["says"] = item["count"]["says"]
            # How big: the overlay's sentence from a paper, checked against the saved text, or a fact of the species file.
            size = item.get("size")
            if isinstance(size, dict) and "part" in size:
                # A size the species file states for one of its cell's parts (the ribosome's, measured by the viewer from a
                # structure: schema/SPECIES_SHAPES.md): read from there with its sources, never held here a second time.
                part = (species_file["cell"].get("parts") or {}).get(size["part"])
                if part is not None:
                    whole = part.get("whole") if isinstance(part.get("whole"), dict) else part
                    across = whole.get("across_nm")
                    if not (isinstance(across, list) and len(across) == 3 and all(isinstance(n, (int, float)) for n in across)):
                        raise Breach(f"{where}: cell.parts.{size['part']} gives no size this tool reads (across_nm, three numbers, on the part or its 'whole'): change the tool to read it")
                    entry["size"] = {"shape": "ellipsoid", "across_nm": across, "part": f"cell.parts.{size['part']}", "says": whole.get("definition") or part.get("definition"), "sources": cite(species, part.get("sources") or [], species_file, where)}
            elif isinstance(size, dict) and "fact" in size:
                found = fact(species_file, size["fact"], where)
                numbers = [str(n) for n in size["long_nm"]]
                if not all(re.search(rf"(^|\D){n}(\D|$)", found["value"]) for n in numbers):
                    raise Breach(f"{where}: the fact {size['fact']!r} does not give {numbers}")
                entry["size"] = {"shape": size["shape"], "long_nm": size["long_nm"], "text": found["value"], "sources": cite(species, found["sources"], species_file, where), "width": "the picture's choice: no source in hand gives it"}
            # The proteins the species' own data marks with it.
            if "proteins" in item:
                entry["proteins"] = marked_proteins(species, item["proteins"]["mark"], item["proteins"]["value"])
                inputs.add(entry["proteins"]["from"])
            # A closer view: the machine file of the species (schema/MACHINES.md).
            if kind.get("machine_file"):
                path = ROOT / "data" / "machines" / f"{species}.{kind['machine_file']}.json"
                machine = read(path)
                inputs.add(rel(path))
                if machine["id"] != kind["id"]:
                    raise Breach(f"{rel(path)}: its id {machine['id']} is not the kind's {kind['id']}: a machine has one identity")
                entry["closer"] = {"file": f"machines/{path.name}", "levels": [{"id": level["id"], "label": level["label"], "says": level["says"]} for level in machine["levels"]], "modelled": machine["modelled"]["text"]}
                kind.setdefault("plain", machine["plain"])
                kind.setdefault("label", machine["label"])
                if not entry["label"]:
                    entry["label"] = machine["label"]
            entries.append(entry)
    for kind in kinds.values():
        if not kind.get("plain"):
            raise Breach(f"the kind {kind['id']} has no plain line")
    for key, source in sources.items():
        if source.get("class") not in ("permissive", "non-commercial", "no stated terms"):
            raise Breach(f"{key} has no class")
    return {
        "format": FORMAT,
        "note": "Generated by visualizer/tools/build_catalogue.py from the files in `made.from`: do not edit. The contract is schema/MACHINE_CATALOGUE.md.",
        "made": {"generator": "visualizer/tools/build_catalogue.py", "from": sorted(inputs)},
        "decided": overlay["decided"],
        "groups": overlay["groups"],
        "records": overlay["records"],
        "units_left_out": overlay["units_left_out"],
        "kinds": list(kinds.values()),
        "entries": entries,
        "sources": dict(sorted(sources.items())),
    }


def dumps(catalogue) -> str:
    return json.dumps(catalogue, indent=1, ensure_ascii=False) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", default=str(OUT), help="where to write it; - for standard output")
    parser.add_argument("--check", action="store_true", help="fail if the file on disk is not what this would write")
    args = parser.parse_args(argv)
    try:
        text = dumps(build())
    except Breach as breach:
        print(f"error: {breach}", file=sys.stderr)
        return 1
    if args.check:
        same = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print("the catalogue is as the tool writes it" if same else f"{rel(OUT)} is not what the tool writes: run it again", file=sys.stderr)
        return 0 if same else 1
    if args.out == "-":
        sys.stdout.write(text)
    else:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}: {len(json.loads(text)['entries'])} entries", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
