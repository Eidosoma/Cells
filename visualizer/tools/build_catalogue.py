#!/usr/bin/env python3
"""Builds the Machines catalogue (schema/MACHINE_CATALOGUE.md): data/catalogue/catalogue.json.

Reads the hand-kept overlay (data/catalogue/overlay.json), the species files (data/species/),
the species' own proteins (data/proteins/<species>/shelves.json), the machine files
(data/machines/) and the gathered dossiers (data/catalogue/gather.json and
data/catalogue/dossiers/<species>.json: schema/MACHINE_DOSSIERS.md), and writes one catalogue: the groups, the kinds of machine, and one entry for
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
    return {"id": name, "label": label, "across_nm": body["across_nm"], "centre_nm": body["centre_nm"], "axes": body["axes"], **({"farthest_nm": body["farthest_nm"]} if "farthest_nm" in body else {}), **({"entities": body["ids"]} if body.get("by") == "entities" else {}), **({"chains": [f"chain-{chain}" for chain in body["ids"]]} if body.get("by") == "chains" else {})}


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


def measured_from_file(overlay, size, where, inputs, own_source, gathered=None):
    """A machine's measure from the tool's own output that the overlay names (tools/measure_particle.py, run by the viewer):
    the whole, its named parts and, in the machine mode, each chain, all in the measure's own frame. With the machine's
    dossier (`gathered`): a part that names its genes carries their proteins, and where the measured entry is the dossier's
    own, each chain carries the protein its entity is, by the dossier's reading of the entry (never by a name)."""
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
    if gathered:
        rows = [dict(zip(gathered["proteins"]["columns"], row)) for row in gathered["proteins"]["rows"]]
        by_gene = {}
        for row in rows:
            by_gene.setdefault(row["gene"], []).append(row["id"])
        for part in parts:
            genes = (labels.get(part["id"]) or {}).get("genes") if isinstance(labels.get(part["id"]), dict) else None
            if genes:
                missing = [gene for gene in genes if gene not in by_gene]
                if missing:
                    raise Breach(f"{where}: the part {part['id']} names genes its dossier does not: {missing}")
                part["proteins"] = sorted({accession for gene in genes for accession in by_gene[gene]})
        structure = gathered.get("structure") or {}
        if structure.get("entry") and structure["entry"] == spec["entry"].split("-assembly")[0]:
            proteins = {entity["id"]: entity["accessions"][0] for entity in structure.get("entities") or [] if entity.get("role") == "part" and len(entity.get("accessions") or []) == 1}
            for chain in chains:
                if chain["entity"] in proteins:
                    chain["protein"] = proteins[chain["entity"]]
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
        **({"membrane": spec["membrane"]} if spec.get("membrane") else {}),
        "says": f"The viewer's own measure from the entry's coordinates, by {record['tool']}: {record['definition']}. The frame: {record.get('frame') or FRAME_WORDS}. The Protein Data Bank states no size.",
        "sources": [own_source(key) for key in spec["sources"]],
    }


def build():
    overlay_path = ROOT / "data" / "catalogue" / "overlay.json"
    overlay = read(overlay_path)
    if overlay.get("format") != OVERLAY_FORMAT:
        raise Breach(f"{rel(overlay_path)} is not {OVERLAY_FORMAT}")
    groups = {group["id"]: group for group in overlay["groups"]}
    # The gathered dossiers (schema/MACHINE_DOSSIERS.md): the kinds looked for, and for each species with a dossier file,
    # its machines, their proteins by tier, counts per cell from open papers, and each protein's machines.
    gather_path = ROOT / "data" / "catalogue" / "gather.json"
    gather = read(gather_path) if gather_path.exists() else {"kinds": []}
    gathered_kinds = {kind["id"]: kind for kind in gather.get("kinds") or []}
    dossiers = {}
    for path in sorted((ROOT / "data" / "catalogue" / "dossiers").glob("*.json")):
        dossier = read(path)
        if dossier.get("format") != "cells.visualizer.machine_dossiers@1":
            raise Breach(f"{rel(path)} is not a file of dossiers")
        dossiers[dossier["species"]] = dossier
    kinds = {}
    for kind in overlay["kinds"]:
        # A kind of the overlay takes from gather.json only what it does not say itself.
        for key in ("label", "group", "plain"):
            if not kind.get(key) and gathered_kinds.get(kind["id"], {}).get(key):
                kind = {**kind, key: gathered_kinds[kind["id"]][key]}
        if kind["group"] not in groups:
            raise Breach(f"the kind {kind['id']} names no group of the overlay: {kind['group']}")
        for line in kind.get("records") or []:
            key = line["ref"] if isinstance(line, dict) else line
            if key not in overlay["records"]:
                raise Breach(f"the kind {kind['id']} names no record of the overlay: {key}")
            if isinstance(line, dict) and not (line.get("status") and line.get("says")):
                raise Breach(f"the kind {kind['id']}: a record line of its own gives both its status and what it says")
        kinds[kind["id"]] = dict(kind)
    # A kind a dossier names that the overlay does not: gather.json's label, group and plain line, and FR-13's line.
    for dossier in dossiers.values():
        for machine in dossier["machines"]:
            if machine["kind"] in kinds:
                continue
            kind = gathered_kinds.get(machine["kind"])
            if not kind or kind.get("group") not in groups:
                raise Breach(f"the dossiers' kind {machine['kind']} has no group of the overlay")
            kinds[machine["kind"]] = {"id": kind["id"], "label": kind["label"], "group": kind["group"], **({"plain": kind["plain"]} if kind.get("plain") else {}), "records": ["fr13"], "from": "gather"}
    sources = {}
    entries = []
    by_protein = {}
    inputs = {rel(overlay_path), *([rel(gather_path)] if gather_path.exists() else []), *(f"data/catalogue/dossiers/{species}.json" for species in dossiers)}

    def gathered_source(species, key):
        source = dossiers[species]["sources"].get(key)
        if not source:
            raise Breach(f"the {species} dossiers cite {key}, which they do not hold")
        name = f"gathered:{species}:{key}"
        sources[name] = {field: source[field] for field in ("text", "doi", "url", "licence", "class", "standing", "accessed") if field in source}
        return name

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
        dossier = dossiers.get(species)
        gathered = {machine["kind"]: machine for machine in (dossier or {}).get("machines") or []}
        listed = {item["kind"] for item in wanted}
        # The machines a dossier names that the overlay does not list come after the overlay's own, in the dossier's order.
        wanted = list(wanted) + [{"kind": kind} for kind in gathered if kind not in listed]
        if dossier:
            by_protein[species] = {accession: [[item["machine"], item["tier"]] for item in machines] for accession, machines in sorted(dossier["by_protein"].items())}
        for item in wanted:
            kind = kinds.get(item["kind"])
            where = f"{species}, {item['kind']}"
            if not kind:
                raise Breach(f"{where}: no such kind")
            if item["kind"] in seen:
                raise Breach(f"{where}: listed twice")
            seen.add(item["kind"])
            entry = {"id": kind["id"], "species": species, "label": item.get("label") or kind.get("label")}
            # What names it: a capability's note of the species file, with that capability's sources, or a record of the viewer;
            # where the overlay names nothing, the dossier's sentence on the Gene Ontology and UniProt, with their sources.
            machine = gathered.get(item["kind"])
            said = None
            if machine:
                said = {"text": machine["named"]["text"], "by": machine["named"]["by"], "sources": [gathered_source(species, key) for key in machine["named"]["sources"]]}
            named = item.get("named")
            if not named:
                if not said:
                    raise Breach(f"{where}: nothing names it")
                entry["named"] = said
            elif "capability" in named:
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
            if named and said:
                entry["also_named"] = said
            # How many a cell has: a fact of the species file, whole, with its sources.
            if "count" in item:
                found = fact(species_file, item["count"]["fact"], where)
                entry["count"] = {"label": found["label"], "text": found["value"], "sources": cite(species, found["sources"], species_file, where)}
                if item["count"].get("says"):
                    entry["count"]["says"] = item["count"]["says"]
            elif machine and machine.get("per_cell"):
                # Else the dossier's: a fact of the species file it points to, or an open paper's number with where it stands.
                counted = []
                for number in machine["per_cell"]:
                    if "fact" in number:
                        found = fact(species_file, number["fact"], where)
                        entry["count"] = {"label": found["label"], "text": found["value"], "sources": cite(species, found["sources"], species_file, where)}
                    else:
                        counted.append({"value": number["value"], "unit": number["unit"], "counts": number["counts"], "cell": number["cell"], "where": number["where"], "source": gathered_source(species, number["source"])})
                if counted:
                    entry["per_cell"] = counted
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
                entry["size"] = measured_from_file(overlay, size, where, inputs, own_source, machine)
            elif isinstance(size, dict) and "fact" in size:
                found = fact(species_file, size["fact"], where)
                numbers = [str(n) for n in size["long_nm"]]
                if not all(re.search(rf"(^|\D){n}(\D|$)", found["value"]) for n in numbers):
                    raise Breach(f"{where}: the fact {size['fact']!r} does not give {numbers}")
                entry["size"] = {"shape": size["shape"], "long_nm": size["long_nm"], "text": found["value"], "sources": cite(species, found["sources"], species_file, where), "width": "the picture's choice: no source in hand gives it"}
            if item.get("no_size"):
                entry["no_size"] = item["no_size"]
            # Its proteins as the dossier gives them, by tier (schema/MACHINE_DOSSIERS.md), and the entry the gathering would
            # measure it from, where that is not the entry its size is measured from.
            if machine:
                columns = machine["proteins"]["columns"]
                rows = [dict(zip(columns, row)) for row in machine["proteins"]["rows"]]
                entry["gathered"] = {"proteins": [[row["id"], row["gene"], row["label"], row["tier"]] for row in rows], "in_atlas": all(row["in_atlas"] for row in rows)}
                structure = machine.get("structure") or {}
                measured = (entry.get("size") or {}).get("entry")
                if structure.get("entry") and (not measured or measured.split("-assembly")[0] != structure["entry"]):
                    whole = structure.get("whole") or {}
                    entry["gathered"]["pick"] = {"entry": structure["entry"], "resolution_A": structure.get("resolution_A"), "present": whole.get("present"), "wanted": whole.get("proteins_wanted"), "measurable": structure.get("measurable"), "source": gathered_source(species, f"pdb{structure['entry'].lower()}") if f"pdb{structure['entry'].lower()}" in dossier["sources"] else None}
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
    # The units of the law inventory with a size: by the finding of each species' atlas (the inventory's own species
    # counts as "found"), a measure of a structure of the unit's own kind, or of the family the species builds it from.
    unit_sizes = overlay.get("unit_sizes")
    if unit_sizes:
        units = {}
        for unit, by_finding in unit_sizes["units"].items():
            if not re.fullmatch(r"unit\.U\d+", unit) or unit in overlay["units_left_out"]["units"]:
                raise Breach(f"unit_sizes: {unit} is no unit of the law inventory that is a protein assembly")
            for finding, key in by_finding.items():
                if finding not in ("found", "different family"):
                    raise Breach(f"unit_sizes: {unit}: {finding!r} is no finding of an atlas")
                units.setdefault(unit, {})[finding] = measured_from_file(overlay, {"measure": key}, f"unit_sizes {unit}", inputs, own_source)
        unit_sizes = {"note": unit_sizes["note"], "species": unit_sizes["species"], "units": units}
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
        "by_protein": by_protein,
        **({"unit_sizes": unit_sizes} if unit_sizes else {}),
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
