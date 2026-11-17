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
# What Cells models of a species, in the ladder every entry of the switch shares (schema/ENTRIES.md): each word asks
# of the record all that the one before asks, and more; tools/lib/entries.py holds what each asks.
STATES = ["generic", "proposed", "planned", "designed", "modelled"]
PLACES = ["absent", "present"]
ORGANELLES = ["er", "golgi", "mitochondria", "chloroplasts", "vacuole"]
# What each structure needs a cell to hold, and the reason given where it does not: one table, read here and by
# src/lenses/cell_structures.js (data/parts/structures.json), keyed by the map's part names.
STRUCTURES = json.loads((Path(__file__).resolve().parents[2] / "data" / "parts" / "structures.json").read_text(encoding="utf-8"))
ANIMAL_ORGANELLES = list(STRUCTURES["nucleated_organelles"])  # what a cell with a nucleus holds where its file does not say
# The size and number of an organelle (schema/SPECIES_SHAPES.md): how many, how large, or what share of the cell it fills.
ORGANELLE_SIZE_KEYS = {"count", "volume_fl", "across_um", "share", "sources"}
# What a cell's shape may be, with what each kind must and may take.
CELL_KINDS = {
    "sphere": ({"across_um"}, set()),
    "capsule": ({"length_um", "across_um"}, {"tip_um"}),
    "prism": ({"sides", "height_um"}, {"across_um", "radius_um", "corner_um", "edge_um"}),
}
PARTS = {"membranes", "wall", "nucleus", "organelles", "chromosome_kbp", "ribosomes", "appendages", "wall_nm", "organelle_sizes", "envelope", "proteins"}
ENVELOPE_KEYS = {"membrane_nm", "wall_nm", "outer_nm", "between_nm", "wall_to_outer_nm", "sources", "read"}  # the envelope's widths (schema/SPECIES_SHAPES.md)
PROTEIN_KEYS = {"count", "membrane", "sources", "membrane_from"}  # how many protein molecules the cell holds
# An appendage: a thread or a hair that stands out from the cell (schema/SPECIES.md, "Appendages are a general part").
APPENDAGE_KEYS = {"kind", "label", "count", "length_um", "width_nm", "where", "from", "base", "sources"}
APPENDAGE_KINDS = ("flagellum", "pilus")
APPENDAGE_WHERE = ("all over", "one pole", "both poles", "one side")
APPENDAGE_FROM = ("cell membrane", "inner membrane", "outer membrane")
LEVEL_FIELDS = {"id", "label", "shape", "note", "notes", "sources", "centre_um", "view", "label_um", "sheet_mark", "fade_in_um", "fade_out_um"}
PART_KINDS = {"loft", "lines", "discs"}


def holds_structure(parts, part):
    """Whether a cell with these parts holds the structure the map's part `part` is drawn at (None: no such structure)."""
    need = STRUCTURES["structures"].get(part)
    if need is None:
        return None
    if need["held_when"] == "nucleus":
        return bool(parts.get("nucleus"))
    organelles = parts.get("organelles")
    held = organelles if organelles is not None else (ANIMAL_ORGANELLES if parts.get("nucleus") else [])
    return need["held_when"].removeprefix("organelle:") in held
PATHS = re.compile(r"/(?:home|mnt|Users|tmp)/|[A-Za-z]:\\\\|\blocalhost\b")


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def positive(value):
    return number(value) and value > 0


DAY = re.compile(r"\d{4}-\d{2}-\d{2}$")


def left_out_sound(flag):
    """A species' own `left_out` on a capability (schema/SPECIES.md): since when, how the page names it, its short reason
    and what was decided, by whom and when, in plain words; nothing more."""
    keys = ("since", "says", "reason", "why")
    return isinstance(flag, dict) and set(flag) == set(keys) and all(isinstance(flag[key], str) and flag[key].strip() for key in keys) and bool(DAY.match(flag["since"]))


def point(value, length=3):
    return isinstance(value, list) and len(value) == length and all(number(item) for item in value)


class Reader:
    """Reads one folder of species files; collects warnings and remarks."""

    def __init__(self, folder, capabilities, left_out=(), parts=None):
        self.folder = Path(folder)
        self.capabilities = dict(capabilities)  # capability id -> the level it belongs to
        self.parts = dict(parts or {})  # capability id -> the map's part it is drawn at (the overlay's `part`), for the structures table
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
        # The heading the species stands under in the list of species; a few words, or not given.
        if data.get("group") is not None and not (isinstance(data["group"], str) and data["group"].strip() and len(data["group"]) <= 40):
            problems.append("group is a heading of a few words")
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
        # Appendages: each a kind the viewer can draw, with its count and sizes (a number or a
        # range of two), where it stands, the membrane it starts at, and the sources of its numbers.
        appendages = parts.get("appendages", [])
        if not isinstance(appendages, list):
            problems.append("cell.parts.appendages is a list")
            appendages = []
        amount = lambda value: positive(value) or (isinstance(value, list) and len(value) == 2 and all(positive(item) for item in value) and value[0] <= value[1])
        for index, item in enumerate(appendages):
            at = f"cell.parts.appendages[{index}]"
            if not isinstance(item, dict):
                problems.append(f"{at} is keyed")
                continue
            if set(item) - APPENDAGE_KEYS:
                problems.append(f"{at} has a key the contract does not give: {', '.join(sorted(set(item) - APPENDAGE_KEYS))}")
            if item.get("kind") not in APPENDAGE_KINDS:
                problems.append(f"{at}.kind is one of {', '.join(APPENDAGE_KINDS)}")
            if not (isinstance(item.get("label"), str) and item["label"].strip()):
                problems.append(f"{at} has no label")
            for key in ("count", "length_um", "width_nm"):
                if not amount(item.get(key)):
                    problems.append(f"{at}.{key} is a number above zero, or a range of two")
            if item.get("where") not in APPENDAGE_WHERE:
                problems.append(f"{at}.where is one of {', '.join(APPENDAGE_WHERE)}")
            if item.get("from") not in APPENDAGE_FROM:
                problems.append(f"{at}.from is one of {', '.join(APPENDAGE_FROM)}")
            if (item.get("from") == "cell membrane") != (parts.get("membranes", 1) == 1):
                problems.append(f"{at}.from names a membrane the cell does not have")
            cited = item.get("sources")
            if not (isinstance(cited, list) and cited and all(key in sources for key in cited)):
                problems.append(f"{at}.sources names keys of the species' sources")
            base = item.get("base")
            if base is not None and not (isinstance(base, dict) and set(base) == {"id", "label", "mark", "value"} and all(isinstance(value, str) and value.strip() for value in base.values())):
                problems.append(f"{at}.base gives an id, a label, and the mark and value of its proteins")
        held = set(ANIMAL_ORGANELLES if organelles is None and parts.get("nucleus") else organelles or [])
        # A wall's thickness, and the size and number of the organelles the cell holds: each a number or a range of two.
        if "wall_nm" in parts:
            if not amount(parts["wall_nm"]):
                problems.append("cell.parts.wall_nm is a number above zero, or a range of two")
            if not parts.get("wall"):
                problems.append("a wall's thickness is given only for a cell with a wall")
        # The envelope's widths, for a cell to scale: each a number above zero, with its source and where the number stands.
        envelope = parts.get("envelope")
        if envelope is not None:
            if not isinstance(envelope, dict) or set(envelope) - ENVELOPE_KEYS:
                problems.append(f"cell.parts.envelope takes {', '.join(sorted(ENVELOPE_KEYS))}")
                envelope = {}
            for key in ENVELOPE_KEYS - {"sources", "read"}:
                if key in envelope and not amount(envelope[key]):
                    problems.append(f"cell.parts.envelope.{key} is a number above zero, or a range of two")
            if not set(envelope) & (ENVELOPE_KEYS - {"sources", "read"}):
                problems.append("cell.parts.envelope gives no number")
            if any(key in envelope for key in ("wall_nm", "wall_to_outer_nm")) and not parts.get("wall"):
                problems.append("cell.parts.envelope gives a wall to a cell without one")
            if any(key in envelope for key in ("outer_nm", "between_nm", "wall_to_outer_nm")) and parts.get("membranes", 1) != 2:
                problems.append("cell.parts.envelope gives an outer membrane to a cell with one membrane")
            cited = envelope.get("sources")
            if not (isinstance(cited, list) and cited and all(key in sources for key in cited)):
                problems.append("cell.parts.envelope.sources names keys of the species' sources")
            read = envelope.get("read")
            if read is not None and not (isinstance(read, dict) and read.get("source") in (cited or []) and isinstance(read.get("where"), str) and read["where"].strip()):
                problems.append("cell.parts.envelope.read names one of its sources and where in it the numbers stand")
        # How many protein molecules the cell holds, and how many of them in its membrane: for the crowd drawn to scale.
        proteins = parts.get("proteins")
        if proteins is not None:
            if not isinstance(proteins, dict) or set(proteins) - PROTEIN_KEYS or not positive(proteins.get("count")):
                problems.append(f"cell.parts.proteins takes {', '.join(sorted(PROTEIN_KEYS))}, with a count above zero")
                proteins = {}
            if "membrane" in proteins and not (positive(proteins["membrane"]) and proteins["membrane"] <= proteins.get("count", 0)):
                problems.append("cell.parts.proteins.membrane is a number above zero, no more than the count")
            cited = proteins.get("sources")
            if not (isinstance(cited, list) and cited and all(key in sources for key in cited)):
                problems.append("cell.parts.proteins.sources names keys of the species' sources")
        sizes = parts.get("organelle_sizes", {})
        if not isinstance(sizes, dict):
            problems.append("cell.parts.organelle_sizes is keyed by organelle")
            sizes = {}
        for word, item in sizes.items():
            at = f"cell.parts.organelle_sizes.{word}"
            if word not in held:
                problems.append(f"{at}: the cell does not hold this organelle")
            if not isinstance(item, dict) or set(item) - ORGANELLE_SIZE_KEYS:
                problems.append(f"{at} takes {', '.join(sorted(ORGANELLE_SIZE_KEYS))}")
                continue
            for key in ("count", "volume_fl", "across_um"):
                if key in item and not amount(item[key]):
                    problems.append(f"{at}.{key} is a number above zero, or a range of two")
            share = item.get("share")
            if share is not None and not all(isinstance(value, (int, float)) and not isinstance(value, bool) and 0 < value <= 1 for value in (share if isinstance(share, list) and len(share) == 2 else [share])):
                problems.append(f"{at}.share is a part of the cell's volume, above 0 and at most 1, or a range of two")
            if not set(item) & {"count", "volume_fl", "across_um", "share"}:
                problems.append(f"{at} gives no number")
            cited = item.get("sources")
            if not (isinstance(cited, list) and cited and all(key in sources for key in cited)):
                problems.append(f"{at}.sources names keys of the species' sources")
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
            elif set(entry) - {"place", "why", "note", "left_out"}:
                problems.append(f"{key} takes place, why, note and left_out")
            elif "left_out" in entry and (entry["place"] != "present" or not left_out_sound(entry["left_out"])):
                problems.append(f"{key}.left_out is for a capability that is present: since (a date), says, reason and why, each a text, and nothing more")
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
        # The species' own cell type (schema/ENTRIES.md, CELL_TYPES.md): {id, label, loop}, `loop` the id of its looping run
        # among the packaged replays. The entries reader (tools/lib/entries.py) gives the species its cell types from it;
        # until the scene is read through that reader, the block is carried as it is, so that the Cell view finds the run.
        own_type = data.get("cell_type")
        if own_type is not None and not (
            isinstance(own_type, dict) and not set(own_type) - {"id", "label", "loop"}
            and all(isinstance(own_type[key], str) and own_type[key].strip() for key in own_type)
        ):
            problems.append("cell_type is {id, label, loop}, each a text that is not empty")

        if problems:
            self.warn(where, problems[0] if len(problems) == 1 else f"{problems[0]} (and {len(problems) - 1} more: {'; '.join(problems[1:4])})")
            return None

        # Within the contracts' letter, but worth a look.
        absent = {key for key, entry in capabilities.items() if entry["place"] == "absent"}
        for key, part in sorted(self.parts.items()):
            if key in self.capabilities and key not in absent and holds_structure(parts, part) is False:
                self.remark(where, f"{key} is present, but the cell holds no {STRUCTURES['structures'][part]['names']}: it cannot be drawn")
        tissue = "tissue" in ids
        for key, level in self.capabilities.items():
            if level == "tissue" and not tissue and key not in capabilities:
                self.remark(where, f"{key} belongs to a tissue, which this species does not have; it is listed with no_further_levels as its reason")
        out = {key: data[key] for key in ("id", "label", "organism", "taxon", "plain", "group", "order", "made", "modelled") if key in data}
        out["default"] = bool(data.get("default", False))
        out["levels"] = levels
        if further:
            out["no_further_levels"] = further
        # A capability this species keeps out of its own picture for now (its `left_out`): carried into the scene with
        # the flag, which the Cell view reads; the place and its note stay, so removing the flag draws it again.
        for key, entry in sorted(capabilities.items()):
            if "left_out" in entry and key not in self.left_out:
                self.remark(where, f"its place for {key} is left out of its picture since {entry['left_out']['since']}: {entry['left_out']['reason']}")
        waiting = sorted(key for key in capabilities if key in self.left_out)
        if waiting:
            self.remark(where, f"its place for {', '.join(waiting)} is not shown: left out of the picture for now")
            capabilities = {key: entry for key, entry in capabilities.items() if key not in self.left_out}
        out["cell"] = {"facts": facts, "parts": parts, "capabilities": capabilities}
        if own_type is not None:
            out["cell_type"] = {key: value.strip() for key, value in own_type.items()}
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


def read_species(folder, capabilities, left_out=(), parts=None):
    """(species, shapes, warnings, remarks) for the folder; all empty where it does not exist.

    `left_out` names the capabilities the map leaves out of the picture for now: a species' place
    for one is read and checked like any other, and left out of what is returned, with a remark.
    `parts` maps a capability to the map's part it is drawn at (the overlay's `part`): where it is
    drawn at a structure the cell does not hold (data/parts/structures.json), the build remarks on it.
    """
    reader = Reader(folder, capabilities, left_out, parts)
    species, shapes = reader.run()
    return species, shapes, reader.warnings, reader.remarks
