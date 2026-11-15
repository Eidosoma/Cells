"""The species the viewer can show: their levels, shapes and what Cells models of each.

Reads every file in data/species/ (schema/SPECIES.md) and the shape files beside them
(schema/SPECIES_SHAPES.md), checks each against the two contracts, and returns what the
scene carries. A breach is a warning, so a strict build fails; a file that cannot be
read is one warning and is left out. Nothing here is the engine's: the engine has no
species switch.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

FORMAT = "cells.visualizer.species@1"
SHAPE_FORMAT = "cells.visualizer.outline@1"
LEVELS = ["molecules", "cell", "tissue", "organ", "organism"]
FURTHER = ["tissue", "organ", "organism"]
STATES = ["generic", "proposed", "modelled"]
PLACES = ["absent", "present"]
ORGANELLES = ["er", "golgi", "mitochondria"]
# What a cell's shape may be, with what each kind must and may take.
CELL_KINDS = {
    "sphere": ({"across_um"}, set()),
    "capsule": ({"length_um", "across_um"}, {"tip_um"}),
    "prism": ({"sides", "height_um"}, {"across_um", "radius_um", "corner_um", "edge_um"}),
}
PARTS = {"membranes", "wall", "nucleus", "organelles", "chromosome_kbp", "ribosomes"}
LEVEL_FIELDS = {"id", "label", "shape", "note", "notes", "sources", "centre_um", "view", "label_um", "sheet_mark", "fade_in_um", "fade_out_um"}
PART_KINDS = {"loft", "lines", "discs"}
# The structure a capability is drawn at, where it is not the cell as a whole.
NEEDS = {"cap.calcium": "er", "cap.trafficking": "golgi", "cap.mitochondria": "mitochondria"}
PATHS = re.compile(r"/(?:home|mnt|Users|tmp)/|[A-Za-z]:\\\\|\blocalhost\b")
SMALL_UM = 2.0  # a cell narrower than this is drawn in one size mode


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def positive(value):
    return number(value) and value > 0


def point(value, length=3):
    return isinstance(value, list) and len(value) == length and all(number(item) for item in value)


class Reader:
    """Reads one folder of species files; collects warnings and remarks."""

    def __init__(self, folder, capabilities, left_out=()):
        self.folder = Path(folder)
        self.capabilities = dict(capabilities)  # capability id -> the level it belongs to
        # Capabilities the map leaves out of the picture for now: a species may still name a place
        # for one (its file keeps it for the day it returns); the scene does not carry that place.
        self.left_out = set(left_out)
        self.warnings = []
        self.remarks = []
        self.shapes = {}

    def warn(self, where, text):
        self.warnings.append(f"species {where}: {text}")

    def remark(self, where, text):
        self.remarks.append(f"species {where}: {text}")

    # ------------------------------------------------------------ shape files

    def outline(self, name, where):
        """A shape file, read once. Returns its parts' names and groups, or None."""
        if name in self.shapes:
            return self.shapes[name]["_names"] if self.shapes[name] else None
        self.shapes[name] = None
        path = self.folder / "shapes" / f"{name}.json"
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]*", name or ""):
            self.warn(where, f"the shape file's name {name!r} is not a plain file name")
            return None
        try:
            text = path.read_text(encoding="utf-8")
            data = json.loads(text)
        except (OSError, ValueError) as error:
            self.warn(where, f"the shape file shapes/{name}.json cannot be read ({type(error).__name__})")
            return None
        label = f"shapes/{name}.json"
        problems = []
        if PATHS.search(text):
            problems.append("it holds a machine path or a host name")
        if not isinstance(data, dict) or data.get("format") != SHAPE_FORMAT:
            problems.append(f"its format is not {SHAPE_FORMAT}")
            data = {}
        on = data.get("tissue_on")
        if on is not None and not (isinstance(on, dict) and point(on.get("at_um")) and number(on.get("clearance_um", 0))):
            problems.append("tissue_on needs at_um, a point, and may give clearance_um")
        names = set()
        parts = data.get("parts")
        if not isinstance(parts, list) or not parts:
            problems.append("it has no parts")
            parts = []
        for index, part in enumerate(parts):
            tag = part.get("name") if isinstance(part, dict) else None
            if not isinstance(part, dict) or not isinstance(tag, str) or not tag.strip():
                problems.append(f"part {index + 1} has no name")
                continue
            if part.get("kind") not in PART_KINDS:
                problems.append(f"part {tag!r} has the unknown kind {part.get('kind')!r}")
                continue
            names.add(tag)
            if isinstance(part.get("group"), str):
                names.add(part["group"])
            if part["kind"] == "loft":
                stations = part.get("stations")
                if not isinstance(stations, list) or len(stations) < 2 or not all(isinstance(s, list) and len(s) in (5, 6, 8) and all(number(v) for v in s) for s in stations):
                    problems.append(f"part {tag!r}: a loft needs two or more stations of 5, 6 or 8 numbers")
                rings = part.get("rings")
                if rings is not None and not (isinstance(rings, dict) and positive(rings.get("points")) and (positive(rings.get("step")) or positive(rings.get("every")))):
                    problems.append(f"part {tag!r}: rings needs points, and step or every")
                if part.get("lines") is not None and not (isinstance(part["lines"], list) and all(number(v) for v in part["lines"])):
                    problems.append(f"part {tag!r}: lines is a list of turns")
            elif part["kind"] == "lines":
                paths = part.get("paths")
                if not isinstance(paths, list) or not paths or not all(isinstance(p, dict) and isinstance(p.get("points"), list) and len(p["points"]) >= 2 and all(point(v) for v in p["points"]) for p in paths):
                    problems.append(f"part {tag!r}: lines needs paths, each with two or more points")
            else:
                if not (isinstance(part.get("at"), list) and part["at"] and all(point(v) for v in part["at"]) and positive(part.get("radius_um"))):
                    problems.append(f"part {tag!r}: discs needs at, a list of points, and radius_um")
            for key in ("strength", "edge", "fill", "alone"):
                if key in part and not (number(part[key]) and 0 <= part[key] <= 1):
                    problems.append(f"part {tag!r}: {key} runs from 0 to 1")
        if problems:
            for problem in problems[:4]:
                self.warn(label, problem)
            if len(problems) > 4:
                self.warn(label, f"and {len(problems) - 4} more of the kind")
            return None
        data["_names"] = names
        self.shapes[name] = data
        return names

    # ------------------------------------------------------------ one species

    def shape(self, level, shape, where):
        """Checks a level's shape. Returns the problems found."""
        problems = []
        if not isinstance(shape, dict) or not isinstance(shape.get("kind"), str):
            return [f"the {level} level needs a shape with a kind"]
        kind = shape["kind"]
        given = set(shape) - {"kind"}
        if level == "cell":
            if kind not in CELL_KINDS:
                return [f"the cell's shape has the unknown kind {kind!r}"]
            needed, optional = CELL_KINDS[kind]
            if needed - given:
                problems.append(f"a {kind} needs {', '.join(sorted(needed - given))}")
            if given - needed - optional:
                problems.append(f"a {kind} does not take {', '.join(sorted(given - needed - optional))}")
            for key in given & (needed | optional):
                if not positive(shape[key]):
                    problems.append(f"the cell's {key} must be a number above zero")
            if kind == "prism":
                if ("across_um" in shape) == ("radius_um" in shape):
                    problems.append("a prism takes across_um or radius_um, one of the two")
                if not (isinstance(shape.get("sides"), int) and 3 <= shape["sides"] <= 12):
                    problems.append("a prism has 3 to 12 sides")
            if kind == "capsule" and positive(shape.get("length_um")) and positive(shape.get("across_um")) and shape["length_um"] < shape["across_um"]:
                problems.append("a capsule is at least as long as it is across")
            if kind == "capsule" and positive(shape.get("tip_um")) and positive(shape.get("across_um")) and shape["tip_um"] > shape["across_um"]:
                problems.append("a capsule's tip is no wider than the capsule")
        elif level == "tissue":
            if kind != "cell sheet":
                return [f"the tissue's shape has the unknown kind {kind!r}"]
            if given - {"rings", "beyond"}:
                problems.append(f"a cell sheet does not take {', '.join(sorted(given - {'rings', 'beyond'}))}")
            if not (isinstance(shape.get("rings"), int) and 1 <= shape["rings"] <= 12):
                problems.append("a cell sheet has 1 to 12 rings")
            beyond = shape.get("beyond", [])
            if not (isinstance(beyond, list) and all(point(item, 2) for item in beyond)):
                problems.append("beyond is a list of [ring, strength]")
        else:
            if kind != "outline":
                return [f"the {level}'s shape has the unknown kind {kind!r}"]
            if given - {"ref", "parts", "context"}:
                problems.append(f"an outline does not take {', '.join(sorted(given - {'ref', 'parts', 'context'}))}")
            names = self.outline(shape.get("ref"), where)
            if names is None:
                problems.append(f"the {level}'s shape file could not be used")
            else:
                for key in ("parts", "context"):
                    listed = shape.get(key, [])
                    if not (isinstance(listed, list) and all(isinstance(item, str) for item in listed)):
                        problems.append(f"{key} is a list of part names")
                    else:
                        missing = [item for item in listed if item not in names]
                        if missing:
                            problems.append(f"the shape file has no part named {', '.join(missing)}")
        return problems

    def framing(self, level, entry):
        """Checks the optional framing of a level."""
        problems = []
        name = level
        if set(entry) - LEVEL_FIELDS:
            problems.append(f"the {name} level does not take {', '.join(sorted(set(entry) - LEVEL_FIELDS))}")
        if "label" in entry and not (isinstance(entry["label"], str) and entry["label"].strip()):
            problems.append(f"the {name} level's label is empty")
        if "note" in entry and not (isinstance(entry["note"], str) and entry["note"].strip()):
            problems.append(f"the {name} level's note is empty")
        notes = entry.get("notes", [])
        if not isinstance(notes, list):
            problems.append(f"the {name} level's notes is a list")
            notes = []
        for item in notes:
            if isinstance(item, str) and item.strip():
                continue
            if not (isinstance(item, dict) and isinstance(item.get("text"), str) and item["text"].strip()) or ("at_um" in item and not point(item["at_um"])) or set(item) - {"text", "short", "at_um", "lift", "roomy"}:
                problems.append(f"a note of the {name} level needs text, and may give short, at_um, lift and roomy")
        for key in ("centre_um", "label_um"):
            if key in entry and not point(entry[key]):
                problems.append(f"the {name} level's {key} is a point")
        view = entry.get("view")
        if view is not None and not (isinstance(view, dict) and not set(view) - {"frame_um", "toward_um", "azimuth", "polar"} and ("frame_um" not in view or (point(view["frame_um"], 2) and all(positive(v) for v in view["frame_um"]))) and ("toward_um" not in view or point(view["toward_um"])) and all(number(view.get(key, 0)) for key in ("azimuth", "polar"))):
            problems.append(f"the {name} level's view takes frame_um, toward_um, azimuth and polar")
        for key in ("fade_in_um", "fade_out_um"):
            if key in entry and not (point(entry[key], 2) and 0 < entry[key][0] < entry[key][1]):
                problems.append(f"the {name} level's {key} is two rising distances")
        mark = entry.get("sheet_mark")
        if mark is not None and not (isinstance(mark, dict) and not set(mark) - {"band", "note", "note_at_um", "roomy"} and positive(mark.get("band", 0.02)) and ("note_at_um" not in mark or point(mark["note_at_um"]))):
            problems.append(f"the {name} level's sheet_mark takes band, note, note_at_um and roomy")
        return problems

    def species(self, path):
        """One species file as the scene carries it, or None with one warning."""
        where = path.name
        try:
            text = path.read_text(encoding="utf-8")
            data = json.loads(text)
        except (OSError, ValueError) as error:
            self.warn(where, f"it cannot be read ({type(error).__name__}); it is left out")
            return None
        if not isinstance(data, dict) or data.get("format") != FORMAT:
            self.warn(where, f"its format is not {FORMAT}; it is left out")
            return None
        problems = []
        if data.get("id") != path.stem:
            problems.append(f"its id {data.get('id')!r} is not the file's name")
        if PATHS.search(text):
            problems.append("it holds a machine path or a host name")
        for key in ("label", "organism", "plain"):
            if not (isinstance(data.get(key), str) and data[key].strip()):
                problems.append(f"it has no {key}")
        if not number(data.get("order")):
            problems.append("order is a number")
        if not isinstance(data.get("default", False), bool):
            problems.append("default is true or false")
        if not (isinstance(data.get("made"), str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", data["made"])):
            problems.append("made is a day, as 2026-11-14")
        if data.get("taxon") is not None and not isinstance(data["taxon"], int):
            problems.append("taxon is a whole number")
        modelled = data.get("modelled")
        if not (isinstance(modelled, dict) and modelled.get("state") in STATES and isinstance(modelled.get("text"), str) and modelled["text"].strip()):
            problems.append(f"modelled needs a state ({', '.join(STATES)}) and a text")
        sources = data.get("sources", {})
        if not isinstance(sources, dict):
            problems.append("sources is keyed")
            sources = {}
        for key, source in sources.items():
            if not (isinstance(source, dict) and isinstance(source.get("text"), str) and source["text"].strip() and (source.get("doi") or source.get("url")) and source.get("accessed")):
                problems.append(f"the source {key!r} needs a text, a doi or a url, and the day it was read")
            elif source.get("url") and not str(source["url"]).startswith("https://"):
                problems.append(f"the source {key!r} gives an address that is not https")

        # The levels, small to large.
        levels = data.get("levels")
        if not isinstance(levels, list) or not all(isinstance(entry, dict) for entry in levels):
            problems.append("levels is a list")
            levels = []
        ids = [entry.get("id") for entry in levels]
        if any(level not in LEVELS for level in ids):
            problems.append(f"a level's id is one of {', '.join(LEVELS)}")
        elif ids != sorted(set(ids), key=LEVELS.index):
            problems.append("the levels run from small to large, each once")
        for needed in ("molecules", "cell"):
            if needed not in ids:
                problems.append(f"it has no {needed} level")
        further = data.get("no_further_levels")
        if any(level not in ids for level in FURTHER) and not (isinstance(further, str) and further.strip()):
            problems.append("a species without tissue, organ or organism says so in no_further_levels")
        for entry in levels:
            level = entry.get("id")
            if level not in LEVELS:
                continue
            problems += self.framing(level, entry)
            if level != "molecules":
                problems += self.shape(level, entry.get("shape"), where)
            elif "shape" in entry:
                problems.append("the molecules level takes no shape")
            for key in entry.get("sources", []) if isinstance(entry.get("sources", []), list) else []:
                if key not in sources:
                    problems.append(f"the {level} level cites {key!r}, which is not among the sources")

        # The cell: what it holds, and which capabilities have a place in it.
        cell = data.get("cell")
        if not isinstance(cell, dict):
            problems.append("it has no cell")
            cell = {}
        parts = cell.get("parts", {})
        if not isinstance(parts, dict):
            problems.append("cell.parts is keyed")
            parts = {}
        if set(parts) - PARTS:
            problems.append(f"the viewer cannot draw the part {', '.join(sorted(set(parts) - PARTS))}")
        if "membranes" in parts and parts["membranes"] not in (1, 2):
            problems.append("a cell has 1 or 2 membranes")
        for key in ("wall", "nucleus"):
            if key in parts and not isinstance(parts[key], bool):
                problems.append(f"cell.parts.{key} is true or false")
        organelles = parts.get("organelles")
        if organelles is not None and not (isinstance(organelles, list) and all(item in ORGANELLES for item in organelles)):
            problems.append(f"organelles is a list from {', '.join(ORGANELLES)}")
            organelles = None
        for key in ("chromosome_kbp", "ribosomes"):
            if key in parts and not positive(parts[key]):
                problems.append(f"cell.parts.{key} is a number above zero")
        if parts.get("nucleus") and "chromosome_kbp" in parts:
            problems.append("a free chromosome is drawn only in a cell without a nucleus")
        held = set(ORGANELLES if organelles is None and parts.get("nucleus", True) else organelles or [])
        capabilities = cell.get("capabilities", {})
        if not isinstance(capabilities, dict):
            problems.append("cell.capabilities is keyed")
            capabilities = {}
        for key, entry in capabilities.items():
            if key not in self.capabilities:
                problems.append(f"{key} is not a capability of the map")
            elif not (isinstance(entry, dict) and entry.get("place") in PLACES):
                problems.append(f"{key} needs a place, absent or present")
            elif entry["place"] == "absent" and not (isinstance(entry.get("why"), str) and entry["why"].strip()):
                problems.append(f"{key} is absent without a why")
            elif set(entry) - {"place", "why", "note"}:
                problems.append(f"{key} takes place, why and note")
        facts = cell.get("facts", [])
        if not isinstance(facts, list):
            problems.append("cell.facts is a list")
            facts = []
        for fact in facts:
            if not (isinstance(fact, dict) and isinstance(fact.get("label"), str) and isinstance(fact.get("value"), str) and isinstance(fact.get("sources", []), list)):
                problems.append("a fact needs a label, a value and the keys of its sources")
            else:
                for key in fact.get("sources", []):
                    if key not in sources:
                        problems.append(f"the fact {fact['label']!r} cites {key!r}, which is not among the sources")
        if set(cell) - {"facts", "parts", "capabilities"}:
            problems.append(f"cell does not take {', '.join(sorted(set(cell) - {'facts', 'parts', 'capabilities'}))}")

        if problems:
            self.warn(where, problems[0] if len(problems) == 1 else f"{problems[0]} (and {len(problems) - 1} more: {'; '.join(problems[1:4])})")
            return None

        # Within the contracts' letter, but worth a look.
        absent = {key for key, entry in capabilities.items() if entry["place"] == "absent"}
        for key, structure in NEEDS.items():
            if key in self.capabilities and key not in absent and structure not in held:
                self.remark(where, f"{key} is present, but the cell holds no {structure}: it cannot be drawn")
        shape = next(entry["shape"] for entry in levels if entry["id"] == "cell")
        across = shape.get("across_um") or 2 * shape.get("radius_um", 0)
        if across < SMALL_UM:
            self.remark(where, f"its cell is {across:g} µm across, so it is drawn in one size mode")
        tissue = "tissue" in ids
        for key, level in self.capabilities.items():
            if level == "tissue" and not tissue and key not in capabilities:
                self.remark(where, f"{key} belongs to a tissue, which this species does not have; it is listed with no_further_levels as its reason")
        out = {key: data[key] for key in ("id", "label", "organism", "taxon", "plain", "order", "made", "modelled") if key in data}
        out["default"] = bool(data.get("default", False))
        out["levels"] = levels
        if further:
            out["no_further_levels"] = further
        waiting = sorted(key for key in capabilities if key in self.left_out)
        if waiting:
            self.remark(where, f"its place for {', '.join(waiting)} is not shown: left out of the picture for now")
            capabilities = {key: entry for key, entry in capabilities.items() if key not in self.left_out}
        out["cell"] = {"facts": facts, "parts": parts, "capabilities": capabilities}
        out["sources"] = sources
        return out

    def run(self):
        found = []
        if self.folder.is_dir():
            for path in sorted(self.folder.glob("*.json")):
                species = self.species(path)
                if species:
                    found.append(species)
        found.sort(key=lambda item: (item["order"], item["id"]))
        defaults = [item["id"] for item in found if item["default"]]
        if found and len(defaults) != 1:
            self.warn("files", f"exactly one species is the default; {len(defaults)} say so" + (f" ({', '.join(defaults)})" if defaults else ""))
            for item in found:
                item["default"] = item["id"] == (defaults[0] if defaults else found[0]["id"])
        used = {entry["shape"]["ref"] for item in found for entry in item["levels"] if entry.get("shape", {}).get("kind") == "outline"}
        shapes = {name: {key: value for key, value in data.items() if key != "_names"} for name, data in self.shapes.items() if data and name in used}
        return found, shapes


def read_species(folder, capabilities, left_out=()):
    """(species, shapes, warnings, remarks) for the folder; all empty where it does not exist.

    `left_out` names the capabilities the map leaves out of the picture for now: a species' place
    for one is read and checked like any other, and left out of what is returned, with a remark.
    """
    reader = Reader(folder, capabilities, left_out)
    species, shapes = reader.run()
    return species, shapes, reader.warnings, reader.remarks
