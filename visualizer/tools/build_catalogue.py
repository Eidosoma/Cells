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


def measured_from_file(spec, where, inputs, own_source, gathered=None):
    """A machine's measure from the tool's own output that the overlay names (tools/measure_particle.py, run by the viewer):
    the whole, its named parts and, in the machine mode, each chain, all in the measure's own frame. With the machine's
    dossier (`gathered`): a part that names its genes carries their proteins, and where the measured entry is the dossier's
    own, each chain carries the protein its entity is, by the dossier's reading of the entry (never by a name).
    A structure bench can give the deposited entity's own label, source organism and protein directly."""
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
    if spec.get("entities"):
        annotations = spec["entities"]
        if set(annotations) != {chain["entity"] for chain in chains}:
            raise Breach(f"{where}: the structure's annotations must name every measured polymer entity")
        for chain in chains:
            annotation = annotations[chain["entity"]]
            chain["label"] = f"{annotation['label']}, {chain['id'].replace('-', ' ', 1)}"
            chain.update({key: annotation[key] for key in ("organism", "protein", "in_atlas", "hue") if key in annotation})
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


SHAPES = ROOT / "data" / "catalogue" / "shapes"

# A dossier's sentence that reaches a panel is said without a file's or a field's name: the gatherer's words keep them
# (they speak of its own files), the page's do not. Each rewrite is exact; a sentence that still holds such a name stops
# the build, so that a new one is mended here or in its dossier, never shown.
PLAIN = [
    (" is left out by gather.json, each because its own title names another complex (left_out).", " is left out, each because its own title names another complex; they are listed below."),
    (" has a file of its own (data/machines/ecoli.flagellar-motor.json) whose ", " has a file of its own, whose "),
    # The shape files' definition (schema/MACHINE_SHAPES.md) names the field that lists the pieces dropped.
    (", smaller ones dropped (listed under dropped)", ", smaller ones dropped, each listed in the shape's file"),
]
# The dossier's word for a machine named only by its family route (schema/MACHINE_DOSSIERS.md).
FAMILY = "family signature"
TOOL_WORDS = re.compile(r"gather\.json|\.py\b|\((?:data|tools|schema|src)/|listed under dropped|\b(?:left_out|holds_more|structure_elsewhere|not_looked_for|no_structure|looked_for|by_protein|per_cell|in_atlas|own_mark|sub_assemblies|left_out_entities|proteins_wanted)\b")


# The organelles' sizes (schema/MACHINE_CATALOGUE.md, "Organelles"): each shape and the numbers its fact must give.
ORGANELLE_SIZES = {"sphere": ("across_um",), "lens": ("across_um",), "stack": ("across_um",), "capsule": ("across_um", "long_um"), "sheet": ("thick_nm",)}


def organelle_entry(item, entry, species, species_file, species_path, where, cite):
    """An organelle of a species' shelf: what names it (its species' file's cell.parts) and its size (a fact of that file,
    whole, with its sources: the cell type and species the paper measured are in the fact's own words), never a second number."""
    parts = species_file["cell"].get("parts") or {}
    named = item.get("named") or {}
    part = named.get("part")
    # Held where the species' file says so: the nucleus, its `organelles` (which the Cell view draws), or its `shelf` (organelles the
    # Cell view does not draw, which stand on the Machines view's shelf alone and which the Cell view ignores).
    held = bool(parts.get("nucleus")) if part == "nucleus" else part in (parts.get("organelles") or []) or part in (parts.get("shelf") or [])
    if not part or not held or not named.get("words"):
        raise Breach(f"{where}: an organelle is named by its species' file's cell.parts, with its words: {part!r} is not held there")
    out = {**entry, "named": {"text": f"{species_file['label']}'s species file: its cell holds {named['words']}.", "part": part, "file": rel(species_path)}}
    size = item.get("size")
    if size and "held" in size:
        # A size that rests on a paper under a non-commercial licence (the owner's ruling of 20 November 2026): read from the held file,
        # which the page never carries; into the bench go only the size drawn, the words for its basis and the file's path.
        held_path = ROOT / "data" / "catalogue" / "held_sizes.json"
        held_file = read(held_path)
        if held_file.get("format") != "cells.visualizer.held_sizes@1":
            raise Breach(f"{rel(held_path)} is not cells.visualizer.held_sizes@1")
        entry_held = ((held_file.get("species") or {}).get(species) or {}).get(size["held"])
        keys = ORGANELLE_SIZES.get(size.get("shape"))
        # A sphere's width, or a capsule's width and length (a centriole's barrel): each as the held file draws it.
        long = size.get("long_um") != entry_held.get("drawn_long_um") if entry_held and size.get("shape") == "capsule" else False
        if not entry_held or not keys or entry_held.get("shape") != size["shape"] or size.get("across_um") != entry_held.get("drawn_um") or long:
            raise Breach(f"{where}: the held file gives no size {size['held']!r} of this shape drawn at {size.get('across_um')}")
        if (entry_held.get("source") or {}).get("class") != "non-commercial":
            raise Breach(f"{where}: a held size rests on a non-commercial source; a permissive one belongs in the species' file")
        out["size"] = {"shape": size["shape"], "across_um": size["across_um"], **({"long_um": size["long_um"]} if size["shape"] == "capsule" else {}), "held": True, "words": entry_held["page_words"], "file": rel(held_path)}
        if size.get("fact"):
            found = fact(species_file, size["fact"], where)
            out["size"].update({"label": found["label"], "text": found["value"], "sources": cite(species, found["sources"], species_file, where), **({"why": size["fact_why"]} if size.get("fact_why") else {})})
    elif size and "part" in size:
        # The size its species' file states for that part of its cell (cell.parts.organelle_sizes), with its sources: never a second number.
        stated = ((parts.get("organelle_sizes") or {}).get(size["part"]) or {})
        if size.get("shape") not in ORGANELLE_SIZES or "across_um" not in stated:
            raise Breach(f"{where}: its species' file states no width for {size['part']!r} in cell.parts.organelle_sizes")
        across = stated["across_um"] if isinstance(stated["across_um"], list) else [stated["across_um"]]
        out["size"] = {"shape": size["shape"], "across_um": across, "label": size["part"], "text": f"its species' file states its cell's {size['part']} {', '.join(str(n) for n in across)} µm across (cell.parts.organelle_sizes)", "sources": cite(species, stated.get("sources") or [], species_file, where)}
    elif size:
        found = fact(species_file, size["fact"], where)
        keys = ORGANELLE_SIZES.get(size.get("shape"))
        if not keys or sorted(key for key in size if key.endswith(("_um", "_nm"))) != sorted(keys):
            raise Breach(f"{where}: an organelle's size is one of {sorted(ORGANELLE_SIZES)}, with its numbers")
        for key in keys:
            for number in size[key]:
                if not re.search(rf"(^|[^\d.]){re.escape(str(number))}([^\d]|$)", found["value"]):
                    raise Breach(f"{where}: the fact {size['fact']!r} does not give {number}")
        # `what`: words for what the fact's number is, where the model's measure takes it as another (a sheet's bilayer
        # separation drawn as its thickness); words only, never a number.
        if re.search(r"\d", size.get("what", "")):
            raise Breach(f"{where}: a size's `what` is words, with no number")
        out["size"] = {"shape": size["shape"], **{key: size[key] for key in keys}, "label": found["label"], "text": found["value"], "sources": cite(species, found["sources"], species_file, where), **({"what": size["what"]} if size.get("what") else {})}
    elif item.get("no_size"):
        out["no_size"] = item["no_size"]
    return out


def plain(text, where):
    """A dossier's sentence as a panel says it (PLAIN); a file's or a field's name left in it is a breach."""
    if not isinstance(text, str):
        return text
    for old, new in PLAIN:
        text = text.replace(old, new)
    found = TOOL_WORDS.search(text)
    if found:
        raise Breach(f"{where}: its panel would say {found.group(0)!r}: {text[:140]}")
    return text


def gathered_entry(machine, dossier, entry, source, where=""):
    """What a machine's dossier adds to its entry (schema/MACHINE_DOSSIERS.md), each said as what it is: its proteins by tier
    (or, for a species by family, its candidates, never called parts, and what was looked for, part by part); PaxDb's
    abundance; UniProt's SUBUNIT sentences; the sub-assemblies the Gene Ontology and UniProt name; the entry the gathering
    picked, with its own title, where its size is not measured from it; another organism's entry where the species has
    none; and what was left out, and why."""
    if machine.get("vault"):
        return vault_entry(machine, dossier, source, where)
    columns = machine["proteins"]["columns"]
    rows = [dict(zip(columns, row)) for row in machine["proteins"]["rows"]]
    family = dossier.get("route") == "family"
    out = {"proteins": [[row["id"], row.get("gene"), row.get("label"), "candidate by family" if family else row["tier"], *([row.get("stands_for") or []] if family else [])] for row in rows]}
    out["in_atlas"] = all(row.get("in_atlas", True) for row in rows) if not family else machine["join"].get("in_atlas") == machine["join"].get("candidates")
    if family:
        out["route"] = {"by": "family", "reference": dossier.get("reference") or machine["named"].get("reference"), "text": machine["named"]["text"]}
        looked = machine.get("looked_for") or {}
        at = {name: index for index, name in enumerate(looked.get("columns") or [])}
        out["looked_for"] = [[row[at["gene"]], row[at["tier"]], row[at["outcome"]], len(row[at["candidates"]] or [])] for row in looked.get("rows") or []]
        if machine.get("own_mark"):
            mark = machine["own_mark"]
            out["own_mark"] = {"mark": mark["mark"], "value": mark["value"], "marked": mark["marked"], "both": mark["both"], "marked_only": len(mark.get("marked_only") or []), "candidates_only": len(mark.get("candidates_only") or [])}
    if machine.get("paxdb"):
        pax = machine["paxdb"]
        out["paxdb"] = {"dataset": pax["dataset_name"], "unit": pax["unit"], "items": pax["items"], "source": source("paxdb")}
    if machine.get("uniprot_subunit"):
        out["subunit"] = [[item["gene"], item["id"], item["says"]] for item in machine["uniprot_subunit"]["items"] if item.get("says")]
    named = {}
    for term, value in ((machine.get("sub_assemblies") or {}).get("go") or {}).items():
        named[f"{value['name']} ({term})"] = value["parts"]
    if named:
        out["sub_assemblies"] = named
    if machine.get("uniprot_fractions"):
        out["fractions"] = machine["uniprot_fractions"]["groups"]
    if machine.get("forms"):
        # The Complex Portal's entries that are forms of the machine (schema/MACHINE_DOSSIERS.md, "Forms"): lines of its panel,
        # never machines. Each: its identifier and name, its protein members, the parts of the machine it holds and the machine's
        # parts, its stoichiometry (the portal's, in the dossier's compact form), its evidence code and, where the portal marks
        # it as taken from another species' entry, that entry and its species.
        words = dossier.get("forms_evidence") or {}
        items = machine["forms"]["items"]
        out["forms"] = {"evidence": {code: words[code] for code in sorted({form["evidence"] for form in items})},
                        "items": [[form["id"], form["name"], form["proteins"], form["parts_held"], form["of_parts"], form["stoichiometry"], form["evidence"], [[x["id"], x["of"]] for x in form.get("inferred_from") or []]] for form in items],
                        "source": source("complex_portal")}
    structure = machine.get("structure") or {}
    measured = (entry.get("size") or {}).get("entry")
    if structure.get("entry") and (not measured or measured.split("-assembly")[0] != structure["entry"]):
        whole = structure.get("whole") or {}
        key = f"pdb{structure['entry'].lower()}"
        out["pick"] = {"entry": structure["entry"], "title": structure.get("title"), "resolution_A": structure.get("resolution_A"), "present": whole.get("present"), "wanted": whole.get("proteins_wanted"), "measurable": structure.get("measurable"),
                       **({"holds_more": {"says": plain(structure["holds_more"]["says"], where), "left_out_entities": structure["holds_more"].get("left_out_entities")}} if structure.get("holds_more") else {}),
                       "source": source(key) if key in dossier["sources"] else None}
    elsewhere = machine.get("structure_elsewhere")
    if elsewhere and not structure.get("entry") and (not measured or measured.split("-assembly")[0] != elsewhere.get("entry")):
        key = f"pdb{elsewhere['entry'].lower()}"
        out["elsewhere"] = {"entry": elsewhere["entry"], "organism": elsewhere["organism"], "title": elsewhere.get("title"), "resolution_A": elsewhere.get("resolution_A"), "source": source(key) if key in dossier["sources"] else None}
    if machine.get("no_structure") and not structure.get("entry"):
        out["no_structure"] = plain(machine["no_structure"], where)
    if machine.get("left_out"):
        out["left_out"] = [[item["entry"], item.get("title"), plain(item.get("why"), where)] for item in machine["left_out"]]
    return out


def vault_entry(machine, dossier, source, where):
    """What the vault's dossier adds to its entry (schema/MACHINE_DOSSIERS.md, "The vault"): its proteins with the tier of the
    footing each stands on, the footings apart, the UniProt lines that name the particle with the evidence each carries, the
    Complex Portal's entry, the family's signatures, what the Protein Data Bank holds of the species' own, and the preprint's
    statements, each with its place. The card says each footing in its own words; nothing here calls a candidate a part."""
    columns = machine["proteins"]["columns"]
    rows = [dict(zip(columns, row)) for row in machine["proteins"]["rows"]]
    vault = machine["vault"]
    preprint = {**vault["preprint"], "source": source(vault["preprint"]["source"])}
    out = {"proteins": [[row["id"], row.get("gene"), row.get("label"), row["tier"]] for row in rows], "in_atlas": all(row["in_atlas"] for row in rows),
           "vault": {**vault, "preprint": preprint, "sources": [source(key) for key in machine["named"]["sources"]]}}
    if machine.get("no_structure") and not machine.get("structure"):
        out["no_structure"] = plain(machine["no_structure"], where)
    return out


def shape_of(size, species, kind, where, inputs):
    """The shape file a measured size is drawn by at the Shape level (schema/MACHINE_SHAPES.md), where one is published:
    the file named as the size's measure (`shapes/<measure>.json`), else the species' own (`<species>.<kind>`), else,
    for a size the species' file draws at another's measure, the shape of that same entry. Its entry must be the size's,
    and every surface must name a chain or a part the size names: a shape never crosses to another entry."""
    named = re.match(r"^data/catalogue/measures/([a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*)\.json$", size.get("from") or "")
    candidates = [SHAPES / f"{named.group(1)}.json"] if named else [SHAPES / f"{species}.{kind}.json", *sorted(SHAPES.glob(f"*.{kind}.json"))]
    entry, assembly = (size.get("entry") or "").split("-assembly")[0], ((size.get("entry") or "").split("-assembly") + [None])[1]
    for path in candidates:
        if not path.exists():
            continue
        data = read(path)
        if data.get("entry") != entry or (data.get("assembly") or None) != assembly:
            if named or path.name == f"{species}.{kind}.json":
                raise Breach(f"{where}: {rel(path)} is a shape of {data.get('entry')}, not of the measured {size.get('entry')}")
            continue
        chains = {chain["id"] for chain in size.get("chains") or []}
        parts = {part["id"] for part in size.get("parts") or []}
        for mesh in data["meshes"]:
            if mesh.get("chain") and chains and mesh["id"] not in chains:
                raise Breach(f"{where}: {rel(path)} has a surface {mesh['id']} that is no chain of the measure")
            if mesh.get("part") and parts and mesh["part"] not in parts:
                raise Breach(f"{where}: {rel(path)} has a surface of the part {mesh['part']}, which the measure does not name")
        inputs.add(rel(path))
        counts = data.get("counts") or {}
        return {"file": f"shapes/{path.name}", "of": path.name.split(".")[0], "entry": data["entry"], **({"assembly": data["assembly"]} if data.get("assembly") else {}),
                "definition": plain(data["definition"], where), "width_nm": data["parameters"]["width_nm"], "by": data["parameters"]["by"],
                **({"setting_width_nm": data["parameters"]["setting_width_nm"]} if data["parameters"].get("setting_width_nm") else {}),
                "triangles": counts.get("triangles"), **({"tones": True} if data.get("tones") else {})}
    return None


def structure_bench(species, path, group_ids, kinds, sources, inputs):
    """Build an experimental-structure bench for a model system without a Cell anatomy file."""
    data = read(path)
    if data["format"] != "cells.visualizer.structure_bench@1":
        raise Breach(f"{rel(path)} is not a structure bench")
    inputs.add(rel(path))
    shelf_path = ROOT / "data" / "proteins" / species / "shelves.json"
    atlas = set()
    if shelf_path.exists():
        shelf = read(shelf_path)
        column = shelf["columns"].index("id")
        atlas = {row[column] for row in shelf["proteins"]}
        inputs.add(rel(shelf_path))
    entries, by_protein, seen = [], {}, set()
    organism = data["organism"]
    for item in data["items"]:
        kind = item["id"]
        where = f"{species}, {kind}"
        if kind in kinds or item["group"] not in group_ids:
            raise Breach(f"{where}: the kind must be unique and name a group of the catalogue")
        kinds[kind] = {**{key: item[key] for key in ("id", "label", "group", "plain")}, "records": []}
        structures = item.get("structures") or []
        if not structures:
            raise Breach(f"{where}: no experimental structures to display")
        representative = structures[0]
        for row in structures:
            if not re.fullmatch(r"[0-9][A-Z0-9]{3}", row["id"]) or row["id"] in seen:
                raise Breach(f"{where}: invalid or repeated PDB ID {row['id']}")
            seen.add(row["id"])
        pdb = representative["id"]
        source = f"pdb:{pdb}"
        sources[source] = {
            "text": f"Protein Data Bank entry {pdb}: {representative['title']}",
            "doi": f"10.2210/pdb{pdb}/pdb",
            "url": f"https://www.rcsb.org/structure/{pdb}",
            "licence": "CC0 1.0",
            "class": "permissive",
            "accessed": data["searched"],
        }
        entities = {}
        for ident, annotation in item["entities"].items():
            accession = annotation.get("protein")
            in_atlas = annotation["organism"] == organism and accession in atlas
            entities[ident] = {**annotation, **({"in_atlas": True} if in_atlas else {})}
            if in_atlas:
                link = [kind, "deposited chain"]
                machines = by_protein.setdefault(accession, [])
                if link not in machines:
                    machines.append(link)
        spec = {
            "file": f"data/catalogue/measures/{species}.{kind}.json",
            "entry": f"{pdb}-assembly{item['assembly']}",
            "of": " and ".join([organism, *representative.get("partner_organisms", [])]),
            "outline": "whole",
            "chains": True,
            "entities": entities,
            "sources": [source],
        }
        size = measured_from_file(spec, where, inputs, lambda key: key)
        surface = shape_of(size, species, kind, where, inputs)
        if not surface:
            raise Breach(f"{where}: the representative needs a published surface")
        size["surface"] = surface
        entries.append({
            "id": kind, "species": species, "label": item["label"],
            "named": {"text": f"Protein Data Bank entry {pdb}", "by": "experimental structure", "sources": [source]},
            "size": size,
            "structures": structures,
        })
    return entries, by_protein, {"label": data["label"], "organism": organism, "structures": len(seen), "searched": data["searched"]}


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
            kinds[machine["kind"]] = {"id": kind["id"], "label": kind["label"], "group": kind["group"], **({"plain": kind["plain"]} if kind.get("plain") else {}), "records": ["fr13"], "from": "gather",
                                      **({"identified_by": kind["identified_by"], "identity": kind["identity"], "absence": kind["absence"]} if kind.get("identified_by") else {})}
    sources = {}
    entries = []
    organelles = []
    by_protein = {}
    none_found = {}
    structure_benches = {}
    inputs = {rel(overlay_path), *([rel(gather_path)] if gather_path.exists() else []), *(f"data/catalogue/dossiers/{species}.json" for species in dossiers)}

    def gathered_source(species, key):
        source = dossiers[species]["sources"].get(key)
        if not source:
            raise Breach(f"the {species} dossiers cite {key}, which they do not hold")
        name = f"gathered:{species}:{key}"
        sources[name] = {field: source[field] for field in ("text", "doi", "url", "licence", "class", "standing", "accessed") if field in source}
        return name

    # A species in which the vault was looked for and none of its three footings reached a protein: what was looked for, said
    # on the kind (the page says it where a visitor names the vault in that species), never as an absence.
    for species_, dossier_ in sorted(dossiers.items()):
        if dossier_.get("vault_looked") and "vault" in kinds:
            kinds["vault"].setdefault("looked", {})[species_] = {"words": dossier_["vault_looked"]["words"], "sources": [gathered_source(species_, key) for key in dossier_["vault_looked"]["sources"]]}

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
            # An organelle (a kind of a group that stands on the shelf): no machine, kept apart from the bench's entries.
            if groups[kind["group"]].get("stands") == "shelf":
                organelles.append(organelle_entry(item, entry, species, species_file, species_path, where, cite))
                continue
            # A label of the species' own where its dossier's one term names the kind with a numeral the kind's label lacks
            # (the human's "RNA polymerase II, core complex": RNA polymerase II, beside I and III).
            terms = ((gathered.get(item["kind"]) or {}).get("named") or {}).get("terms") or []
            if not item.get("label") and len(terms) == 1 and entry["label"]:
                numbered = re.match(rf"^({re.escape(entry['label'])} (?:I{{1,3}}|IV|V))\b", terms[0][1], re.I)
                if numbered:
                    entry["label"] = entry["label"] + numbered.group(1)[len(entry["label"]):]
            # What names it: a capability's note of the species file, with that capability's sources, or a record of the viewer;
            # where the overlay names nothing, the dossier's sentence on the Gene Ontology and UniProt, with their sources.
            machine = gathered.get(item["kind"])
            said = None
            if machine:
                said = {"text": plain(machine["named"]["text"], where), "by": machine["named"]["by"], "sources": [gathered_source(species, key) for key in machine["named"]["sources"]]}
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
                written = (ROOT.parent / record["path"]).read_text(encoding="utf-8") if record["path"].startswith("visualizer/") else ""
                if named["word"] not in written:
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
                        # The paper's own number as it writes it (`written`, with its power of ten), never one worked out here;
                        # and whom it cites, where it gives another paper's number.
                        counted.append({"value": number["value"], **({"written": number["written"]} if number.get("written") else {}), **({"cites": number["cites"]} if number.get("cites") else {}), "unit": number["unit"], "counts": plain(number["counts"], where), "cell": plain(number["cell"], where), "where": plain(number["where"], where), "source": gathered_source(species, number["source"])})
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
                    entry["size"] = measured_from_file(overlay["measures"][size["measure"]], where, inputs, own_source)
            elif isinstance(size, dict) and "measure" in size:
                entry["size"] = measured_from_file(overlay["measures"][size["measure"]], where, inputs, own_source, machine)
            elif isinstance(size, dict) and "fact" in size:
                found = fact(species_file, size["fact"], where)
                numbers = [str(n) for n in size["long_nm"]]
                if not all(re.search(rf"(^|\D){n}(\D|$)", found["value"]) for n in numbers):
                    raise Breach(f"{where}: the fact {size['fact']!r} does not give {numbers}")
                entry["size"] = {"shape": size["shape"], "long_nm": size["long_nm"], "text": found["value"], "sources": cite(species, found["sources"], species_file, where), "width": "the picture's choice: no source in hand gives it"}
            if (entry.get("size") or {}).get("shape") == "measured":
                shape = shape_of(entry["size"], species, kind["id"], where, inputs)
                if shape:
                    entry["size"]["surface"] = shape
            if item.get("no_size"):
                entry["no_size"] = item["no_size"]
            # Its proteins as the dossier gives them, by tier (schema/MACHINE_DOSSIERS.md), and the entry the gathering would
            # measure it from, where that is not the entry its size is measured from.
            if machine:
                entry["gathered"] = gathered_entry(machine, dossier, entry, lambda key: gathered_source(species, key), where)
            # The proteins the species' own data marks with it.
            if "proteins" in item:
                entry["proteins"] = marked_proteins(species, item["proteins"]["mark"], item["proteins"]["value"])
                inputs.add(entry["proteins"]["from"])
            # A closer view: the machine file of the species (schema/MACHINES.md).
            if kind.get("machine_file") and (ROOT / "data" / "machines" / f"{species}.{kind['machine_file']}.json").exists():
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
            # A machine that only its dossier's family route names, and for which it found no candidate: not on the bench,
            # in no count or tray; the species' list of what was looked for by family and not found holds it, with its
            # reference machine and what was looked for, part by part.
            route = (entry.get("gathered") or {}).get("route") or {}
            if route.get("by") == "family" and (entry.get("named") or {}).get("by") == FAMILY and not entry["gathered"]["proteins"]:
                none_found.setdefault(species, []).append({"id": kind["id"], "label": entry["label"], "group": kind["group"], "reference": route["reference"], "looked_for": entry["gathered"]["looked_for"], "text": route["text"], "sources": entry["named"]["sources"]})
                continue
            entries.append(entry)
    for species, file in (overlay.get("structure_benches") or {}).items():
        if species in overlay["species"]:
            raise Breach(f"{species}: two ways to build the same bench")
        added, by_protein[species], structure_benches[species] = structure_bench(species, ROOT / file, groups, kinds, sources, inputs)
        entries.extend(added)
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
                size = measured_from_file(overlay["measures"][key], f"unit_sizes {unit}", inputs, own_source)
                # A unit's shape, where one is published for its measure (schema/MACHINE_SHAPES.md: a unit by its page id).
                shape = shape_of(size, "unit", unit, f"unit_sizes {unit}", inputs)
                if shape:
                    size["surface"] = shape
                units.setdefault(unit, {})[finding] = size
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
        "organelles": organelles,
        "by_protein": by_protein,
        "none_found": none_found,
        "structure_benches": structure_benches,
        **({"unit_sizes": unit_sizes} if unit_sizes else {}),
        "sources": dict(sorted(sources.items())),
    }


def dumps(catalogue) -> str:
    return json.dumps(catalogue, indent=1, ensure_ascii=False) + "\n"


BENCHES = ROOT / "data" / "catalogue" / "benches"
BENCH_FORMAT = "cells.visualizer.machine_bench@1"


def split(whole):
    """The catalogue as the page reads it: what every bench needs (the groups, the kinds with the species that have each,
    the records, the sources, the units' sizes, and an index of the benches) in `catalogue.json`, which the page carries;
    and each species' bench (its entries, and its proteins' machines for the atlas's way back) in a file of its own,
    `benches/<species>.json`, published beside the page and read when that bench is shown."""
    species = []
    for entry in whole["entries"]:
        if entry["species"] not in species:
            species.append(entry["species"])
    benches = {}
    for name in species:
        entries = [entry for entry in whole["entries"] if entry["species"] == name]
        shelf = [entry for entry in whole.get("organelles") or [] if entry["species"] == name]
        benches[name] = {"format": BENCH_FORMAT, "species": name, "note": "Generated by visualizer/tools/build_catalogue.py with catalogue.json: do not edit.", "entries": entries, "by_protein": whole["by_protein"].get(name, {}),
                         **({"none_found": whole["none_found"][name]} if whole.get("none_found", {}).get(name) else {}),
                         **({"organelles": shelf} if shelf else {})}
    having = {}
    for entry in whole["entries"] + (whole.get("organelles") or []):
        having.setdefault(entry["id"], []).append(entry["species"])
    core = {key: value for key, value in whole.items() if key not in ("entries", "organelles", "by_protein", "none_found", "structure_benches")}
    core["kinds"] = [{**kind, "species": having.get(kind["id"], [])} for kind in whole["kinds"]]
    core["benches"] = {name: {"file": f"catalogue/{name}.json", "machines": len(benches[name]["entries"]),
                              **({"organelles": len(benches[name]["organelles"])} if benches[name].get("organelles") else {}),
                              **whole["structure_benches"].get(name, {})} for name in species}
    return core, benches


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", default=str(OUT), help="where to write the catalogue's core; - for the whole catalogue (core and benches together) on standard output")
    parser.add_argument("--check", action="store_true", help="fail if the files on disk are not what this would write")
    args = parser.parse_args(argv)
    try:
        whole = build()
    except Breach as breach:
        print(f"error: {breach}", file=sys.stderr)
        return 1
    if args.out == "-":
        sys.stdout.write(dumps(whole))
        return 0
    core, benches = split(whole)
    texts = {OUT: dumps(core), **{BENCHES / f"{name}.json": dumps(bench) for name, bench in benches.items()}}
    if args.check:
        stale = [rel(path) for path, text in texts.items() if not path.exists() or path.read_text(encoding="utf-8") != text]
        stale += [rel(path) for path in BENCHES.glob("*.json") if path not in texts]
        print("the catalogue is as the tool writes it" if not stale else f"{', '.join(stale)}: not what the tool writes; run it again", file=sys.stderr)
        return 0 if not stale else 1
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(texts.pop(OUT), encoding="utf-8")
    BENCHES.mkdir(parents=True, exist_ok=True)
    for path in BENCHES.glob("*.json"):
        if path not in texts:
            path.unlink()
    for path, text in texts.items():
        path.write_text(text, encoding="utf-8")
    print(f"wrote {args.out}: {len(whole['entries'])} entries, on {len(benches)} benches beside it", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
