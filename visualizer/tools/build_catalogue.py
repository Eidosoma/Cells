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


FRAME_WORDS = "origin at the centre of both subunits' atoms; y from the large subunit's centre to the small one's; x the whole particle's longest axis made square to y; z = x × y"


def part_of(name, label, body):
    """One body of a measured machine, as the catalogue gives it: its widths, its centre and its own axes in the machine's frame."""
    return {"id": name, "label": label, "across_nm": body["across_nm"], "centre_nm": body["centre_nm"], "axes": body["axes"], **({"farthest_nm": body["farthest_nm"]} if "farthest_nm" in body else {}), **({"entities": body["ids"]} if body.get("by") == "entities" else {})}


def measured_from_part(part, size, species, species_file, where, cite):
    """A machine's measure as its species' file states it for a part of its cell (the ribosome: two subunits and the whole)."""
    if not (isinstance(part.get("across_nm"), list) and len(part["across_nm"]) == 3):
        raise Breach(f"{where}: cell.parts.{size['part']} gives no size this tool reads (across_nm, three numbers): change the tool to read it")
    labels = {"large": "Large subunit", "small": "Small subunit"}
    parts = [part_of(name, labels.get(name, name), part[name]) for name in ("large", "small") if isinstance(part.get(name), dict)]
    return {
        "shape": "measured", "entry": part.get("entry"), "of": part.get("of"), "from": f"cell.parts.{size['part']} of the species' file",
        "whole": {"across_nm": part["across_nm"], **({"farthest_nm": part["farthest_nm"]} if "farthest_nm" in part else {})},
        "parts": parts, "between_nm": part.get("between_nm"),
        "beside": {key: part["beside"][key] for key in ("entry", "across_nm") if key in part["beside"]} if isinstance(part.get("beside"), dict) else None,
        "says": part.get("measured") or part.get("definition"), "sources": cite(species, part.get("sources") or [], species_file, where),
        # Whose part it is, where the species' file says the measure is another organism's (a bacterium drawn at E. coli's ribosome).
        **({"whose": part["note"]} if isinstance(part.get("note"), str) and part["note"].strip() else {}),
    }


def measured_from_file(overlay, size, where, inputs, own_source):
    """A machine's measure from the tool's own output that the overlay names (tools/measure_particle.py, run by the viewer):
    the whole, its named parts and, in the machine mode, each chain, all in the measure's own frame."""
    spec = overlay["measures"][size["measure"]]
    path = ROOT / spec["file"]
    record = read(path)
    inputs.add(rel(path))
    if record.get("tool") != "tools/measure_particle.py" or spec["entry"] not in record.get("measured", {}):
        raise Breach(f"{where}: {spec['file']} is not the tool's measure of {spec['entry']}")
    first = record["measured"][spec["entry"]]
    beside = record["measured"].get(spec.get("beside")) if spec.get("beside") else None
    labels = spec.get("parts") or {}
    # The ribosome's mode gives its two subunits at the top of the measure; the machine mode gives them under `parts`.
    named = first.get("parts") if isinstance(first.get("parts"), dict) else {name: first[name] for name in labels if isinstance(first.get(name), dict)}
    missing = [name for name in labels if name not in named]
    if missing:
        raise Breach(f"{where}: {spec['file']} has no part {missing[0]} of {spec['entry']}")
    def label_of(name):
        value = labels[name]
        return value if isinstance(value, str) else value["label"]
    parts = [{**part_of(name, label_of(name), named[name]), **({"hue": labels[name]["hue"]} if isinstance(labels[name], dict) and labels[name].get("hue") else {})} for name in labels]
    chains = [{"id": f"chain-{body['chain']}", "label": f"{body['description']}, chain {body['chain']}", "entity": body["entity"], "across_nm": body["across_nm"], "centre_nm": body["centre_nm"], "axes": body["axes"]} for body in first.get("chains") or []] if spec.get("chains") else []
    entities = first.get("entities") or []
    shares = [entity["modelled_share"] for entity in entities if entity.get("modelled_share") is not None]
    frame = first.get("frame") or {}
    return {
        "shape": "measured", "entry": spec["entry"], "of": spec["of"], "from": spec["file"],
        "whole": {"across_nm": first["whole"]["across_nm"], "farthest_nm": first["whole"]["farthest_nm"], **({"axes": first["whole"]["axes"]} if "axes" in first["whole"] else {})},
        "outline": spec.get("outline", "parts" if parts else "whole"),
        "parts": parts, "chains": chains,
        "between_nm": frame.get("between_centres_nm", first.get("between_centres_nm")),
        "kinds": len(entities) or None, "modelled": [min(shares), max(shares)] if shares else None,
        "beside": {"entry": beside["entry"], "across_nm": beside["whole"]["across_nm"]} if beside else None,
        **({"note": spec["note"]} if spec.get("note") else {}),
        "says": f"The viewer's own measure from the entry's coordinates, by {record['tool']}: {record['definition']}. The frame: {record.get('frame') or FRAME_WORDS}. The Protein Data Bank states no size.",
        "sources": [own_source(key) for key in spec["sources"]],
    }


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

    def own_source(key):
        source = (overlay.get("sources") or {}).get(key)
        if not source:
            raise Breach(f"{key} is not a source of the overlay")
        sources[f"catalogue:{key}"] = {name: source[name] for name in ("text", "doi", "url", "licence", "class", "accessed", "saved") if name in source}
        return f"catalogue:{key}"

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
            elif "protein" in named:
                # A protein of the species' own catalogue (data/proteins/<species>/proteins.tsv) whose entry names the machine.
                table = ROOT / "data" / "proteins" / species / "proteins.tsv"
                rows = table.read_text(encoding="utf-8").splitlines()
                columns = rows[0].split("\t")
                found = next((dict(zip(columns, row.split("\t"))) for row in rows[1:] if row.split("\t", 1)[0] == named["protein"]), None)
                if not found:
                    raise Breach(f"{where}: {rel(table)} holds no protein {named['protein']}")
                inputs.add(rel(table))
                entry["named"] = {"text": f"Its own proteins hold {found.get('gene') or found['id']} ({found['id']}), named in its entry “{found['name']}”.", "word": found.get("gene") or found["id"], "protein": found["id"], "file": rel(table), "sources": cite(species, ["uniprot"], species_file, where)}
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
                # A size measured by the viewer from a structure. The species' file's own statement of the part comes first
                # (cell.parts.ribosome: schema/SPECIES_SHAPES.md); where it states none, the measure the overlay names. Never both.
                part = (species_file["cell"].get("parts") or {}).get(size["part"])
                if part is not None:
                    entry["size"] = measured_from_part(part, size, species, species_file, where, cite)
                elif size.get("measure"):
                    entry["size"] = measured_from_file(overlay, size, where, inputs, own_source)
            elif isinstance(size, dict) and "measure" in size:
                entry["size"] = measured_from_file(overlay, size, where, inputs, own_source)
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
