"""The entries the species switch offers, in three kinds: species, cell types and model systems.

schema/ENTRIES.md sets out what they share (ids, the `modelled` ladder, citations of the
project's record, sources and their licence classes, the switch, the address); schema/CELL_TYPES.md
and schema/MODEL_SYSTEMS.md the two new kinds. This module stands beside tools/lib/species.py,
which reads the species themselves exactly as it does today; it calls that reader unchanged, and
adds to each species its cell types, and beside the species the model systems.

A breach is a warning, so a strict build fails; an entry with a breach is left out, with one
warning. Nothing here is the engine's: the engine has no species switch, no cell-type object on
main and no model system.

Two entry points: read_entries(...) reads the folders; check(...) takes what is already parsed,
so that a test needs no files.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .species import PARTS, ORGANELLES, Reader, read_species

CELL_FORMAT = "cells.visualizer.cell_type@1"
MODEL_FORMAT = "cells.visualizer.model_system@1"

# The ladder of what Cells models of an entry (schema/ENTRIES.md): each word asks of the record
# all that the one before asks, and more. The kinds that may use each word, and the page's words.
LADDER = ["generic", "proposed", "planned", "designed", "modelled"]
WORDS = {"species": LADDER, "cell type": LADDER, "model system": LADDER[1:]}
PAGE_WORDS = {"generic": "Generic cell", "proposed": "Proposed, not modelled", "planned": "Planned, not modelled", "designed": "Designed, not modelled", "modelled": "Modelled"}
CITATION_KEYS = {"path", "where"}
NOTE_KEYS = {"id", "label", "text", "record"}  # a sourced note of an entry (schema/ENTRIES.md, "Notes")
OWN = "visualizer/"  # the prefix of a path that is one of the viewer's own files (tools/extract_architecture.py, own_file)

# The views a model system may have, each with its fixed list of levels (schema/MODEL_SYSTEMS.md).
VIEW_KINDS = {
    "assembly": {
        "run_format": "cells.visualizer.assembly_run@1",  # schema/ASSEMBLY_RUN.md, the view's own contract
        "levels": ["molecules", "assembly", "population", "lineage"],
        "required": ["molecules", "assembly"],
        "labels": {"molecules": "Molecules", "assembly": "One assembly", "population": "Population", "lineage": "Lineages"},
    },
    "physarum": {
        "run_format": None,
        "levels": ["network", "vein"],
        "required": ["network", "vein"],
        "labels": {"network": "Plasmodium", "vein": "Vein cutaway"},
    },
    "vesicle": {
        "run_format": "cells.visualizer.assembly_run@2",
        "levels": ["vesicle", "membrane", "molecule"],
        "required": ["vesicle"],
        "labels": {"vesicle": "Vesicle", "membrane": "Membrane", "molecule": "Molecule"},
    },
}
CLOCKS = ("fission", "second")  # a run's time.base (schema/ASSEMBLY_RUN.md); compared with it, never a rate
RUN_KINDS = ("example", "development", "experiment")
NOT_OF_A_MODEL = ("organism", "taxon", "cell", "cell_type", "cell_types", "no_further_levels", "default_cell_type")
MODEL_KEYS = {"format", "id", "label", "is", "plain", "group", "order", "made", "modelled", "view", "levels", "clock", "runs", "facts", "sources", "notes"}
MODEL_LEVEL_KEYS = {"id", "label", "shows", "waits", "note"}

# A cell type's own levels, and the keys of its file (schema/CELL_TYPES.md).
CELL_LEVELS = ["cell", "tissue"]
CELL_KEYS = {"format", "species", "id", "label", "short", "order", "plain", "modelled", "extends", "differs", "levels", "parts", "capabilities", "engine", "loop", "proteins", "facts", "sources", "notes"}
OWN_FIELDS = {"id", "label", "short", "order", "modelled", "differs", "extends", "format", "species"}  # never taken from a parent
ENGINE_KEYS = {"definition", "structure", "parameter_set", "models", "operators", "says", "provisional"}
SPECIES_KEYS = {"cell_type", "cell_types", "default_cell_type"}  # what a species file gains, at its top level

# The licence classes, read from a licence's text as tests/licence_classes.test.mjs reads them.
CLASSES = ("permissive", "non-commercial", "no stated terms")
NON_COMMERCIAL = re.compile(r"CC BY-NC|^Academic licence\b|^For academic users only\b")
NO_TERMS = re.compile(r"^(No open licence stated|no licence stated|no open licence|Terms not read\b)")
PERMISSIVE = re.compile(r"^CC BY\b(?!-NC)|^CC0\b|[Nn]o restrictions?\b|places no restriction|[Ii]mposes no restrictions|no use restrictions|^Public domain|BSD 3-Clause|^Bibliographic facts only")
NUMBERS_ONLY = "open paper, numbers only"  # D186's standing (schema/MACHINES.md)
ID = re.compile(r"[a-z0-9][a-z0-9-]*")
PATHS = re.compile(r"/(?:home|mnt|Users|tmp)/|[A-Za-z]:\\\\|\blocalhost\b")


def class_of(licence):
    if not isinstance(licence, str):
        return None
    if NON_COMMERCIAL.search(licence):
        return "non-commercial"
    if NO_TERMS.search(licence):
        return "no stated terms"
    return "permissive" if PERMISSIVE.search(licence) else None


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def text(value):
    return isinstance(value, str) and bool(value.strip())


class Entries:
    """Checks entries already parsed. `tracked` is the set of tracked paths of the engine's main (None:
    not checked); `own` is the viewer's folder, where a `visualizer/` path must name a file (None: not
    checked); `shapes` reads a level's shape and framing as the species reader does."""

    def __init__(self, capabilities, tracked=None, own=None, shapes=None, models=None):
        self.capabilities = dict(capabilities)
        # The models the engine's declarations manifest lists with their declared structure (rows), by either
        # spelling: what a modelled entry may name (None: not checked).
        self.models = set(models) if models is not None else None
        self.tracked = set(tracked) if tracked is not None else None
        self.own = Path(own) if own is not None else None
        self.shapes = shapes or Reader(Path("."), capabilities)
        self.warnings = []
        self.remarks = []

    def warn(self, where, message):
        self.warnings.append(f"entry {where}: {message}")

    def remark(self, where, message):
        self.remarks.append(f"entry {where}: {message}")

    # ------------------------------------------------------------ what every kind shares

    def citations(self, items, where, label="record"):
        """A list of citations of the project's record: each a tracked file of main or one of the viewer's own."""
        problems = []
        if not isinstance(items, list):
            return [f"{label} is a list of citations"]
        for index, item in enumerate(items):
            at = f"{label}[{index}]"
            if not isinstance(item, dict) or not text(item.get("path")):
                problems.append(f"{at} needs a path")
                continue
            extra = set(item) - CITATION_KEYS
            if extra:
                problems.append(f"{at} takes path and where only, not {', '.join(sorted(extra))}: a file that exists only on a development branch is named in words in the viewer's own note, and the note is cited")
            path = item["path"]
            if path.startswith(OWN):
                if self.own is not None and not (self.own / path[len(OWN):]).is_file():
                    problems.append(f"{at} cites {path}, which is not a file of the viewer's folder")
            elif self.tracked is not None and path not in self.tracked:
                problems.append(f"{at} cites {path}, which is not a tracked file of main")
        return problems

    def notes(self, notes, where):
        """An entry's `notes`: a list of sourced notes, each {id, label, text, record}, its record checked as every citation is."""
        if notes is None:
            return []
        if not isinstance(notes, list):
            return ["notes is a list of {id, label, text, record}"]
        problems, seen = [], set()
        for index, note in enumerate(notes):
            at = f"notes[{index}]"
            if not isinstance(note, dict):
                problems.append(f"{at} is {{id, label, text, record}}")
                continue
            if set(note) - NOTE_KEYS:
                problems.append(f"{at} takes id, label, text and record, not {', '.join(sorted(set(note) - NOTE_KEYS))}")
            if not (isinstance(note.get("id"), str) and ID.fullmatch(note["id"])):
                problems.append(f"{at}'s id is a plain word")
            elif note["id"] in seen:
                problems.append(f"{at}: two notes have the id {note['id']!r}")
            else:
                seen.add(note["id"])
            for key in ("label", "text"):
                if not text(note.get(key)):
                    problems.append(f"{at} has no {key}")
            record = note.get("record")
            if not (isinstance(record, list) and record):
                problems.append(f"{at} cites the record its words rest on (record): a note is sourced, as a word of the ladder is")
            else:
                problems += self.citations(record, where, f"{at}.record")
        return problems

    def modelled(self, block, kind, where, record_required=True):
        """The `modelled` block: one word of the ladder that the kind may use, its text, and what the word asks of the record."""
        if not isinstance(block, dict):
            return ["modelled needs a state and a text"]
        state = block.get("state")
        problems = []
        if state not in WORDS[kind]:
            return [f"modelled.state is one of {', '.join(WORDS[kind])} for a {kind}, not {state!r}"]
        if not text(block.get("text")):
            problems.append("modelled needs a text")
        if set(block) - {"state", "text", "record", "design", "model"}:
            problems.append(f"modelled takes state, text, record, design and model, not {', '.join(sorted(set(block) - {'state', 'text', 'record', 'design', 'model'}))}")
        if state == "generic":
            if text(block.get("text")) and "generic" not in block["text"]:
                problems.append("a generic entry's text says which generic model stands in for it")
        record = block.get("record")
        if record is not None:
            problems += self.citations(record, where)
        if state != "generic" and record_required and not (isinstance(record, list) and record):
            problems.append(f"a {kind} that is {state} cites the record behind the word (modelled.record)")
        if LADDER.index(state) >= LADDER.index("designed"):
            design = block.get("design")
            if not text(design):
                problems.append(f"a {kind} that is {state} gives its design note's path (modelled.design)")
            elif design.startswith(OWN) or (self.tracked is not None and design not in self.tracked):
                problems.append(f"modelled.design {design!r} is not a tracked file of main: a design note on a development branch moves no word")
        if state == "modelled" and not text(block.get("model")):
            problems.append("a modelled entry names its registered model (modelled.model)")
        elif state == "modelled" and self.models is not None and block["model"] not in self.models:
            problems.append(f"modelled.model {block['model']!r} is not a model the engine's declarations list with its declared structure")
        return problems

    def sources(self, sources, where):
        """Keyed sources, each with its text, a doi or a url, its licence, its class and the day it was read."""
        problems = []
        if not isinstance(sources, dict):
            return ["sources is keyed"]
        for key, source in sources.items():
            if not (isinstance(source, dict) and text(source.get("text")) and (source.get("doi") or source.get("url")) and source.get("accessed")):
                problems.append(f"the source {key!r} needs a text, a doi or a url, and the day it was read")
                continue
            if source.get("url") and not str(source["url"]).startswith("https://"):
                problems.append(f"the source {key!r} gives an address that is not https")
            if source.get("class") not in CLASSES:
                problems.append(f"the source {key!r} needs a class: {', '.join(CLASSES)}")
            elif source["class"] != class_of(source.get("licence")):
                problems.append(f"the source {key!r}: its class {source['class']!r} does not follow from its licence {source.get('licence')!r}")
        return problems

    def standing(self, sources, keys, what, numbers_only=False):
        """Whether the sources behind a value may stand there: permissive, or for a number alone an open paper's (D186)."""
        problems = []
        for key in keys if isinstance(keys, list) else []:
            source = sources.get(key) if isinstance(sources, dict) else None
            if not isinstance(source, dict):
                problems.append(f"{what} cites {key!r}, which is not among the sources")
            elif source.get("class") != "permissive" and not (numbers_only and source.get("standing") == NUMBERS_ONLY):
                problems.append(f"{what} rests on {key!r}, which is not permissive: such a source is a pointer in `see`, and nothing is taken from it")
        return problems

    def facts(self, facts, sources):
        problems = []
        if not isinstance(facts, list):
            return ["facts is a list"]
        for fact in facts:
            if not (isinstance(fact, dict) and text(fact.get("label")) and text(fact.get("value")) and isinstance(fact.get("sources", []), list)):
                problems.append("a fact needs a label, a value and the keys of its sources")
                continue
            numbered = bool(re.search(r"\d", fact["value"]))
            problems += self.standing(sources, fact.get("sources", []), f"the fact {fact['label']!r}", numbers_only=numbered)
        return problems

    # ------------------------------------------------------------ cell types

    def cell_type(self, data, where, species_ids):
        """One cell type's file, checked. Returns the problems found."""
        problems = []
        if not isinstance(data, dict) or data.get("format") != CELL_FORMAT:
            return [f"its format is not {CELL_FORMAT}"]
        stem = where.rsplit("/", 1)[-1].removesuffix(".json")
        if stem != f"{data.get('species')}.{data.get('id')}":
            problems.append("a cell type's file is named <species>.<id>.json, as its species and id say")
        if data.get("species") not in species_ids:
            problems.append(f"its species {data.get('species')!r} is not a species of the folder")
        if not (isinstance(data.get("id"), str) and ID.fullmatch(data["id"])):
            problems.append("its id is a plain word")
        if PATHS.search(json.dumps(data)):
            problems.append("it holds a machine path or a host name")
        extra = set(data) - CELL_KEYS
        if extra:
            problems.append(f"a cell type does not take {', '.join(sorted(extra))}")
        for key in ("label", "plain"):
            if not text(data.get(key)):
                problems.append(f"it has no {key}")
        if not number(data.get("order")):
            problems.append("order is a number")
        if "modelled" in data or "extends" not in data:
            problems += self.modelled(data.get("modelled"), "cell type", where)
            if isinstance(data.get("modelled"), dict) and data["modelled"].get("state") == "generic":
                problems.append("a cell type of a file of its own is not generic: only a species' own cell is")
        sources = data.get("sources", {})
        problems += self.sources(sources, where)
        problems += self.facts(data.get("facts", []), sources if isinstance(sources, dict) else {})
        problems += self.notes(data.get("notes"), where)
        levels = data.get("levels", [])
        if not (isinstance(levels, list) and all(isinstance(level, dict) for level in levels)):
            problems.append("levels is a list")
            levels = []
        ids = [level.get("id") for level in levels]
        if any(level not in CELL_LEVELS for level in ids):
            problems.append(f"a cell type gives only its own levels: {', '.join(CELL_LEVELS)}; the organ and the body are its species'")
        elif ids != sorted(set(ids), key=CELL_LEVELS.index):
            problems.append("the levels run from small to large, each once")
        else:
            for level in levels:
                problems += self.shapes.framing(level["id"], level)
                if "shape" in level:
                    problems += self.shapes.shape(level["id"], level["shape"], where)
                problems += self.standing(sources, level.get("sources", []), f"the {level['id']} level")
        parts = data.get("parts", {})
        if not isinstance(parts, dict):
            problems.append("parts is keyed")
        else:
            if set(parts) - PARTS:
                problems.append(f"the viewer cannot draw the part {', '.join(sorted(set(parts) - PARTS))}")
            if "organelles" in parts and not (isinstance(parts["organelles"], list) and all(item in ORGANELLES for item in parts["organelles"])):
                problems.append(f"organelles is a list from {', '.join(ORGANELLES)}")
            if "membranes" in parts and parts["membranes"] not in (1, 2):
                problems.append("a cell has 1 or 2 membranes")
        capabilities = data.get("capabilities", {})
        if not isinstance(capabilities, dict):
            problems.append("capabilities is keyed")
            capabilities = {}
        for key, entry in capabilities.items():
            if key not in self.capabilities:
                problems.append(f"{key} is not a capability of the map")
                continue
            if not (isinstance(entry, dict) and entry.get("place") in ("absent", "present")):
                problems.append(f"{key} needs a place, absent or present")
                continue
            if entry["place"] == "absent" and not text(entry.get("why")):
                problems.append(f"{key} is absent without a why")
            if set(entry) - {"place", "why", "note", "state", "says", "record", "design", "model"}:
                problems.append(f"{key} takes place, why, note, state, says, record, design and model")
            if "state" in entry:
                word = {"state": entry["state"], "text": entry.get("says"), **{field: entry[field] for field in ("record", "design", "model") if field in entry}}
                problems += [f"{key}: {problem}" for problem in self.modelled(word, "cell type", where)]
        engine = data.get("engine")
        if engine is not None:
            if not isinstance(engine, dict) or set(engine) - ENGINE_KEYS:
                problems.append(f"engine takes {', '.join(sorted(ENGINE_KEYS))}")
            else:
                for key in ("definition", "parameter_set"):
                    if engine.get(key) is not None and not text(engine[key]):
                        problems.append(f"engine.{key} is an id, or null")
                for key in ("structure", "models", "operators"):
                    if key in engine and not (isinstance(engine[key], list) and all(text(item) for item in engine[key])):
                        problems.append(f"engine.{key} is a list of ids")
                if any(engine.get(key) for key in ("definition", "parameter_set", "structure")) and engine.get("provisional") is not True:
                    problems.append("an engine binding is marked provisional while the lead's answers are provisional")
        if data.get("loop") is not None and not text(data["loop"]):
            problems.append("loop is a packaged replay's id, or null")
        proteins = data.get("proteins")
        if proteins is not None:
            if not (isinstance(proteins, dict) and text(proteins.get("mark")) and text(proteins.get("value"))):
                problems.append("proteins names a mark and a value of the species' own proteins")
            else:
                problems += self.standing(sources, proteins.get("sources", []), "the cell type's set of proteins")
        if "extends" in data:
            if not text(data["extends"]):
                problems.append("extends names a cell type of the same species")
            differs = data.get("differs")
            if not (isinstance(differs, dict) and differs.get("in") in ("parameters", "structures") and text(differs.get("says"))):
                problems.append("a cell type that extends another says how it differs: differs.in (parameters or structures) and differs.says")
            elif "record" in differs:
                problems += self.citations(differs["record"], where, "differs.record")
        elif "differs" in data:
            problems.append("differs belongs to a cell type that extends another")
        return problems

    # ------------------------------------------------------------ model systems

    def model_system(self, data, where, species_ids):
        """One model system's file, checked. Returns the problems found."""
        problems = []
        if not isinstance(data, dict) or data.get("format") != MODEL_FORMAT:
            return [f"its format is not {MODEL_FORMAT}"]
        stem = where.rsplit("/", 1)[-1].removesuffix(".json")
        if data.get("id") != stem:
            problems.append(f"its id {data.get('id')!r} is not the file's name")
        if not (isinstance(data.get("id"), str) and ID.fullmatch(data["id"])):
            problems.append("its id is a plain word")
        if data.get("id") in species_ids:
            problems.append(f"its id {data.get('id')!r} is a species' id: species and model systems share one set of ids")
        if PATHS.search(json.dumps(data)):
            problems.append("it holds a machine path or a host name")
        organism = [key for key in NOT_OF_A_MODEL if key in data]
        if organism:
            problems.append(f"a model system is not an organism: it takes no {', '.join(organism)}")
        if "default" in data:
            problems.append("a model system is never the page's default")
        extra = set(data) - MODEL_KEYS - set(NOT_OF_A_MODEL) - {"default"}
        if extra:
            problems.append(f"a model system does not take {', '.join(sorted(extra))}")
        for key in ("label", "is", "plain", "group"):
            if not text(data.get(key)):
                problems.append(f"it has no {key}")
        if text(data.get("group")) and len(data["group"]) > 40:
            problems.append("group is a heading of a few words")
        if not number(data.get("order")):
            problems.append("order is a number")
        if not (isinstance(data.get("made"), str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", data["made"])):
            problems.append("made is a day, as 2026-11-16")
        problems += self.modelled(data.get("modelled"), "model system", where)
        view = data.get("view")
        kind = view.get("kind") if isinstance(view, dict) else None
        if kind == "physarum":
            if not ID.fullmatch(str(view.get("protein_atlas", ""))):
                problems.append("the Physarum preview names its protein catalogue")
            if not re.fullmatch(r"models\.[a-z0-9_]+", str(view.get("engine_part", ""))):
                problems.append("the Physarum preview names its Engine catalogue part")
            if data.get("runs") or data.get("clock"):
                problems.append("the Physarum anatomy preview takes no run or clock")
        if kind not in VIEW_KINDS:
            problems.append(f"view.kind is one of {', '.join(VIEW_KINDS)}, not {kind!r}")
        else:
            allowed = VIEW_KINDS[kind]["levels"]
            levels = data.get("levels")
            if not (isinstance(levels, list) and all(isinstance(level, dict) for level in levels)):
                problems.append("levels is a list")
            else:
                ids = [level.get("id") for level in levels]
                if any(level not in allowed for level in ids):
                    problems.append(f"a model system's levels come from its view's list: {', '.join(allowed)}")
                elif ids != sorted(set(ids), key=allowed.index):
                    problems.append(f"the levels stand in their view's order ({', '.join(allowed)}), each once")
                for needed in VIEW_KINDS[kind]["required"]:
                    if needed not in ids:
                        problems.append(f"it has no {needed} level")
                for level in levels:
                    if set(level) - MODEL_LEVEL_KEYS:
                        problems.append(f"a level takes {', '.join(sorted(MODEL_LEVEL_KEYS))}")
                    for key in ("label", "shows", "waits", "note"):
                        if key in level and not text(level[key]):
                            problems.append(f"the {level.get('id')} level's {key} is empty")
        clock = data.get("clock")
        if clock is not None and not (isinstance(clock, dict) and clock.get("base") in CLOCKS and text(clock.get("says")) and not set(clock) - {"base", "says"}):
            problems.append(f"clock is {{base, says}}, base one of {', '.join(CLOCKS)}: a label only, since a run states its own clock")
        runs = data.get("runs", [])
        if not (isinstance(runs, list) and all(isinstance(run, dict) and text(run.get("file")) and text(run.get("label")) and run.get("kind") in RUN_KINDS and not set(run) - {"file", "label", "kind"} for run in runs)):
            problems.append(f"runs is a list of {{file, label, kind}}, kind one of {', '.join(RUN_KINDS)}")
        else:
            for run in runs:
                if not run["file"].startswith("data/") or ".." in run["file"]:
                    problems.append(f"the run file {run['file']!r} is a path under the viewer's data/")
                elif self.own is not None:
                    path = self.own / run["file"]
                    if not path.is_file():
                        problems.append(f"the run file {run['file']} is not there")
                    elif kind in VIEW_KINDS:
                        try:
                            held = json.loads(path.read_text(encoding="utf-8"))
                        except (OSError, ValueError):
                            held = {}
                        if held.get("format") != VIEW_KINDS[kind]["run_format"]:
                            problems.append(f"the run file {run['file']} is not of its view's format, {VIEW_KINDS[kind]['run_format']}")
                        elif (held.get("model") or {}).get("id") != data.get("id"):
                            problems.append(f"the run file {run['file']} is a run of {(held.get('model') or {}).get('id')!r}, not of this model system")
                        elif clock is not None and (held.get("time") or {}).get("base") != clock.get("base"):
                            problems.append(f"the run file {run['file']} counts {(held.get('time') or {}).get('base')!r}: the run's clock is shown, and this label would not be")
                        elif (run["kind"] == "example") != ("example" in held):
                            problems.append(f"the run file {run['file']} is {'not ' if 'example' not in held else ''}an example, and the entry says it is{' ' if run['kind'] == 'example' else ' not'}")
        sources = data.get("sources", {})
        problems += self.sources(sources, where)
        problems += self.facts(data.get("facts", []), sources if isinstance(sources, dict) else {})
        problems += self.notes(data.get("notes"), where)
        return problems

    # ------------------------------------------------------------ putting them together

    def run(self, species, raw_species, cells, models):
        """species: what the species reader gave; raw_species: each species file as written, by id (for
        the keys the species reader passes over); cells and models: parsed files, by file name.
        Returns (species with their cell types, model systems)."""
        species_ids = {item["id"] for item in species}
        by_species = {}
        for name, data in sorted(cells.items()):
            problems = self.cell_type(data, name, species_ids)
            if problems:
                self.warn(name, problems[0] if len(problems) == 1 else f"{problems[0]} (and {len(problems) - 1} more: {'; '.join(problems[1:4])})")
                continue
            by_species.setdefault(data["species"], {})[data["id"]] = data
        out_species = []
        for item in species:
            raw = raw_species.get(item["id"], {})
            where = f"{item['id']}.json"
            problems = []
            given = raw.get("cell_type", {})
            if not isinstance(given, dict) or set(given) - {"id", "label", "loop"} or ("id" in given and not (isinstance(given["id"], str) and ID.fullmatch(given["id"]))):
                problems.append("cell_type is {id, label, loop}, its id a plain word")
                given = {}
            # What Cells models of the species: the ladder's word, with the record behind every word above generic.
            problems += self.modelled(raw.get("modelled", item.get("modelled")), "species", where)
            own_id = given.get("id", "cell")
            own = {
                "id": own_id,
                "label": given.get("label") or ("Generic cell" if item["modelled"]["state"] == "generic" else "Its cell"),
                "own": True,
                "modelled": item["modelled"],
                "levels": [level for level in item["levels"] if level["id"] in CELL_LEVELS],
                "parts": item["cell"].get("parts", {}),
                "capabilities": item["cell"].get("capabilities", {}),
                "facts": item["cell"].get("facts", []),
                "loop": given.get("loop"),
            }
            named = raw.get("cell_types", [])
            if not (isinstance(named, list) and all(isinstance(value, str) for value in named)):
                problems.append("cell_types is a list of cell-type ids")
                named = []
            files = by_species.get(item["id"], {})
            for type_id in named:
                if type_id == own_id:
                    problems.append(f"the cell type {type_id!r} is its own cell block's: name another")
                elif type_id not in files:
                    self.warn(where, f"it names the cell type {type_id!r}, which has no sound file data/cells/{item['id']}.{type_id}.json: that type is left out")
            for type_id in sorted(set(files) - set(named)):
                self.remark(where, f"the cell type {type_id!r} has a file and is not named in cell_types: it is not shown")
            types = {own_id: own}
            resolved = {}

            def resolve(type_id, seen=()):
                if type_id in resolved:
                    return resolved[type_id]
                if type_id == own_id:
                    return own
                data = files[type_id]
                parent_id = data.get("extends")
                if parent_id is None:
                    merged = {key: value for key, value in data.items() if key != "format"}
                elif parent_id in seen or parent_id == type_id:
                    raise ValueError(f"the cell types {' -> '.join([*seen, type_id, parent_id])} extend one another in a loop")
                elif parent_id != own_id and (parent_id not in files or parent_id not in named):
                    raise ValueError(f"the cell type {type_id!r} extends {parent_id!r}, which is not a cell type of {item['id']}")
                else:
                    parent = resolve(parent_id, (*seen, type_id))
                    merged = {key: value for key, value in parent.items() if key not in OWN_FIELDS and key != "own"}
                    merged.update({key: value for key, value in data.items() if key != "format"})
                    if "modelled" not in data:
                        merged["modelled"] = parent["modelled"]
                resolved[type_id] = merged
                return merged

            for type_id in [value for value in named if value in files]:
                try:
                    types[type_id] = resolve(type_id)
                except ValueError as error:
                    self.warn(where, f"{error}: the cell type {type_id!r} is left out")
            default = raw.get("default_cell_type", own_id)
            if default not in types:
                problems.append(f"default_cell_type {default!r} is not one of its cell types")
            if problems:
                self.warn(where, problems[0] if len(problems) == 1 else f"{problems[0]} (and {len(problems) - 1} more: {'; '.join(problems[1:4])})")
                continue
            entry = dict(item)
            # What Cells models of the species at a life stage (schema/SPECIES_STAGES.md): held to the ladder and its record as the
            # species' own word is; a stage whose word is not sound leaves the species without its stages, with a warning.
            for stage in (item.get("stages") or {}).get("list", []):
                said = self.modelled(stage["modelled"], "species", f"{where} at its stage {stage['id']}") if "modelled" in stage else []
                if said:
                    self.warn(where, f"its stage {stage['id']}: {said[0]}; the species is shown without its stages")
                    entry.pop("stages", None)
                    break
            entry["cell_types"] = [types[own_id], *sorted((value for key, value in types.items() if key != own_id), key=lambda value: (value["order"], value["id"]))]
            entry["default_cell_type"] = default
            out_species.append(entry)
        out_models = []
        for name, data in sorted(models.items()):
            problems = self.model_system(data, name, species_ids)
            if problems:
                self.warn(name, problems[0] if len(problems) == 1 else f"{problems[0]} (and {len(problems) - 1} more: {'; '.join(problems[1:4])})")
                continue
            entry = {key: value for key, value in data.items() if key != "format"}
            labels = VIEW_KINDS[data["view"]["kind"]]["labels"]
            entry["levels"] = [{"label": labels[level["id"]], **level} for level in data["levels"]]
            entry["kind"] = "model system"
            out_models.append(entry)
        out_models.sort(key=lambda value: (value["order"], value["id"]))
        return out_species, out_models


def check(species, raw_species, cells, models, capabilities, tracked=None, own=None):
    """The entries from what is already parsed: (species, models, warnings, remarks). See Entries.run."""
    entries = Entries(capabilities, tracked=tracked, own=own)
    out_species, out_models = entries.run(species, raw_species, cells, models)
    return out_species, out_models, entries.warnings, entries.remarks


def _read_folder(folder):
    found, warnings = {}, []
    if folder is not None and Path(folder).is_dir():
        for path in sorted(Path(folder).glob("*.json")):
            try:
                found[path.name] = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                warnings.append(f"entry {path.name}: it cannot be read ({type(error).__name__}); it is left out")
    return found, warnings


def read_entries(species_folder, cells_folder, models_folder, capabilities, left_out=(), tracked=None, own=None, parts=None, declared=None):
    """(species, shapes, models, warnings, remarks) for the folders. The species are read by
    tools/lib/species.py exactly as the scene reads them today; each gains its cell types
    (`cell_types`, `default_cell_type`). Folders that do not exist give nothing. `parts` maps a
    capability to the map's part it is drawn at, for the species reader's remarks. `declared`: the models the engine's
    declarations list with their declared structure, which a modelled entry must name (None: not checked). It is
    kept apart from `models`, the model systems' own files read below."""
    species, shapes, warnings, remarks = read_species(species_folder, capabilities, left_out, parts)
    raw_species = {}
    for path in sorted(Path(species_folder).glob("*.json")) if Path(species_folder).is_dir() else []:
        try:
            raw_species[path.stem] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass  # the species reader has warned of it
    cells, cell_warnings = _read_folder(cells_folder)
    models, model_warnings = _read_folder(models_folder)
    entries = Entries(capabilities, tracked=tracked, own=own, shapes=Reader(Path(species_folder), capabilities, left_out), models=declared)
    out_species, out_models = entries.run(species, raw_species, cells, models)
    return out_species, shapes, out_models, warnings + cell_warnings + model_warnings + entries.warnings, remarks + entries.remarks
