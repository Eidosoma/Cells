#!/usr/bin/env python3
"""Build the architecture scene from a Cells checkout and the curated overlay.

What comes from the checkout (and so cannot drift from it):
  * which files belong to each part, their counts and lines;
  * which part uses which, from the import statements;
  * the plan's gates and the shared-state entities.

What comes from the engine's declarations manifest (data/engine/declarations.json,
cells.declarations@3), written by the engine at the checkout's own revision from a clean tree
(a manifest of another major or revision, or from a tree with changes, is refused):
  * every registered operator of the composite model, with the declarations of its
    contract (what it requires, writes, provides, reads and conflicts with);
  * the laws and kinds the engine registers, each on the part that holds its file;
  * the active models; the older families' model identifiers, listed by ID only, are not drawn.
Read from the source beside it, because the manifest does not hold them apart: an operator's
RK4, ACCEPTS_WRITES, VIEW_FIELDS (the head of its `provides`) and CONTROL_FACTORS (the tail of
its `controls`); and each model module's MODEL_ID, only to place a declared model on its part
(the manifest names the module that declares a model's structure, not the one that runs it).

What comes from the overlay (data/architecture/overlay.json), each with a source:
  * the layers and the grouping of files into parts;
  * statuses, plain-language lines and planned parts;
  * the capability map drawn on the cell, and the experiments and references.

What comes from the protein inventory's snapshot (data/proteins/, see
tools/import_protein_inventory.py): the functional units of the protein atlas, each linked
to the engine part that holds its law. Every law record is checked against the checkout.
Species atlases beside it (data/proteins/atlases/, see schema/SPECIES_ATLAS.md) say which
gene products of another species would make each unit; each file is checked against its
contract, and a file that breaks it is warned about.

What an overlay flags as left out of the picture for now (`left_out`, on a capability of the
cell map or on a unit of the protein atlas) is not added to the scene: no part, no link, no
count. The scene names it once, in `left_out`, with how the page says it and why. Removing
the flag brings it back.

Standard library only. It parses source with ``ast`` and never imports ``cells``.

    python3 tools/extract_architecture.py            # reads the main checkout
    python3 tools/extract_architecture.py --repo PATH --out PATH --strict
"""

from __future__ import annotations

import argparse
import ast
import datetime
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from lib.protein_atlas import LENS_GROUPS, RELATION_KINDS, Atlas, left_out_flag  # noqa: E402
from lib.entries import read_entries  # noqa: E402
from lib.static_eval import Evaluator, Package, Unresolved, plain  # noqa: E402

SCENE_FORMAT = "cells.visualizer.scene@1"


# ---------------------------------------------------------------- small helpers


def git(repo, *arguments):
    done = subprocess.run(
        ["git", "-C", str(repo), *arguments], capture_output=True, text=True, check=False
    )
    return done.stdout if done.returncode == 0 else ""


def own_file(path):
    """Whether a cited path is a file of the viewer's own folder, the one this tool runs from."""
    prefix = "visualizer/"
    if not path.startswith(prefix):
        return False
    home = HERE.parent.resolve()
    target = (home / path[len(prefix):]).resolve()
    return home in target.parents and target.is_file()


def pinned(base, name):
    """A link base on a branch's tip (".../blob/main/") as the same base at `name`, a revision or another branch."""
    if not base or not name or "/blob/main/" not in base:
        return base
    return base.replace("/blob/main/", f"/blob/{name}/")


def find_repo(explicit):
    """The checkout to read: --repo, else the one CELLS_ENGINE_REPO names, else the nearest tree that holds src/cells."""
    explicit = explicit or os.environ.get("CELLS_ENGINE_REPO")
    if explicit:
        return Path(explicit).resolve()
    candidates = [HERE.parent.parent]
    common = git(HERE, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
    if common:
        candidates.append(Path(common).parent)
    for candidate in candidates:
        if (candidate / "src" / "cells").is_dir():
            return candidate.resolve()
    raise SystemExit("No checkout with src/cells found; pass --repo.")


def glob_regex(pattern):
    """A path glob where * stays inside one directory and ** crosses directories."""
    out, index = [], 0
    while index < len(pattern):
        if pattern.startswith("**/", index):
            out.append("(?:.*/)?")
            index += 3
        elif pattern.startswith("**", index):
            out.append(".*")
            index += 2
        elif pattern[index] == "*":
            out.append("[^/]*")
            index += 1
        elif pattern[index] == "?":
            out.append("[^/]")
            index += 1
        else:
            out.append(re.escape(pattern[index]))
            index += 1
    return re.compile("".join(out) + r"\Z")


def first_paragraph(path):
    try:
        doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8")))
    except (SyntaxError, OSError, UnicodeDecodeError):
        return None
    return paragraph(doc)


def paragraph(doc):
    """A docstring's first paragraph on one line, or None."""
    if not doc:
        return None
    return " ".join(doc.strip().split("\n\n")[0].split())


def count_lines(path):
    try:
        return sum(1 for _ in path.open("rb"))
    except OSError:
        return 0


def table_after(lines, start):
    """Rows (lists of cells) of the first markdown table at or after line ``start``."""
    rows, inside = [], False
    for line in lines[start:]:
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if not all(set(cell) <= set("-: ") for cell in cells):
                rows.append(cells)
            inside = True
        elif inside or line.startswith("#"):
            break
    return rows


def unmark(text):
    """Markdown emphasis and links reduced to their text."""
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    return text.replace("**", "").replace("`", "").strip()


def join_names(names, limit=6):
    names = list(names)
    shown = ", ".join(names[:limit])
    return shown + (f" and {len(names) - limit} more" if len(names) > limit else "")


DECLARATIONS_KIND = "cells.declarations@3"
DECLARATIONS_FILE = HERE.parent / "data" / "engine" / "declarations.json"


def is_drawn_on_its_part(piece):
    """A piece of the manifest drawn as a member of the part that holds its file: a law, a kind, or a model family's
    own operator (an operator of an interface other than the composite's cells.operator@1)."""
    return piece.get("piece") in ("law", "kind") or (piece.get("piece") == "operator" and piece.get("interface") != "cells.operator@1")


def model_module(path):
    """A model module: src/cells/models/<file>.py, or a model family's package, src/cells/models/<family>/__init__.py
    (the assembly-lineage family, 17 November 2026, declares its MODEL_ID there)."""
    parts = path.split("/")
    return parts[:3] == ["src", "cells", "models"] and (len(parts) == 4 or (len(parts) == 5 and parts[4] == "__init__.py"))


def read_declarations(path, revision):
    """The engine's declarations manifest (docs/library/DECLARATIONS_FORMAT.md in the engine), checked.

    It is the engine's own record of what it declares: every registered law, kind and operator, every
    active model, and the older families by ID only. The map learns its operators and models from it,
    never from the engine's registries. Refused: another major of `kind`, a manifest written at
    another revision than the checkout the scene is built from, and one written from a tree with
    changes (`dirty`), since then it states pieces no revision holds.
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise SystemExit(f"{path}: the engine's declarations cannot be read ({error})")
    kind = data.get("kind") if isinstance(data, dict) else None
    if not isinstance(kind, str) or kind.rsplit("@", 1)[0] != DECLARATIONS_KIND.rsplit("@", 1)[0]:
        raise SystemExit(f"{path}: not the engine's declarations manifest (kind {kind!r})")
    if kind != DECLARATIONS_KIND:
        raise SystemExit(f"{path}: {kind} is a major this reader does not know; it reads {DECLARATIONS_KIND}")
    if not revision or data.get("revision") != revision:
        raise SystemExit(f"{path}: written at {data.get('revision')}, but the scene is built at {revision or 'no revision'}: write the manifest again at that revision (data/engine/README.md)")
    if data.get("dirty") is not False:
        raise SystemExit(f"{path}: written from a tree with changes (dirty: {data.get('dirty')!r}); it must come from a clean checkout")
    return data


# ---------------------------------------------------------------- the build


class Build:
    def __init__(self, repo, overlay, proteins=None, declarations=None):
        self.repo = repo
        self.declarations_path = Path(declarations) if declarations else DECLARATIONS_FILE
        self._declarations = None
        self.viewer_ids = json.loads((HERE.parent / "data/engine/viewer-ids.json").read_text())
        self.aliases = self.viewer_ids["aliases"]
        self.overlay = overlay
        self.protein_data = proteins  # (snapshot, overlay, folder of species atlases) of the protein atlas, or None
        self.proteins = None
        self.warnings = []
        self.entities = {}
        self.relations = {}
        self.package = Package(repo / "src" / "cells", "cells")
        self.evaluator = Evaluator(self.package)
        self.files = [line for line in git(repo, "ls-files").splitlines() if line]
        self.ahead = []  # cited sources that are the viewer's own files and not yet tracked in the checkout read
        self.git = lambda *arguments: git(repo, *arguments)
        self.owner = {}  # repo-relative path -> entity id
        self.statuses = {status["id"] for status in overlay["statuses"]}
        # What an overlay flags as left out of the picture for now (`left_out` on a capability
        # or on a unit of the protein atlas): never added to the scene, and named once in it.
        self.left_out = []
        # Texts that stand in while something is left out: (where, id, field) -> the wording, or None for none.
        self.rewords = {}
        self.reworded = set()
        # The engine's own path tables of its source moves (D188: scripts/moves/<move>-table.json, committed
        # with each move): old path -> (new path, the move). Read so that a record made before a move, the
        # protein inventory's, finds a file at its new place; the overlay itself is carried through the moves
        # by tools/move_paths.py.
        self.moves = self.read_moves()
        # Held legacy code (the overlay's `legacy`): the files under its folder are left out of the picture.
        # On 17 November 2026 the user decided that the map shows no legacy code (D196). A part whose files all stand
        # there is left out, with that reason; a part with active files as well shows those only.
        self.legacy_rule = overlay.get("legacy")
        if self.legacy_rule:
            left_out_flag("legacy", {"says": "held legacy code", **self.legacy_rule})
            if not str(self.legacy_rule.get("folder", "")).endswith("/"):
                raise SystemExit("legacy: 'folder' must name a folder, ending in /")
        self.legacy = {}  # a file under the legacy folder -> the part whose pattern held it, or None

    def read_moves(self):
        moved = {}
        for path in sorted(item for item in self.files if re.fullmatch(r"scripts/moves/[^/]+-table\.json", item)):
            try:
                table = json.loads((self.repo / path).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self.warnings.append(f"{path}: the move's path table cannot be read")
                continue
            if table.get("kind") != "cells.source_moves.path_table@1":
                self.warnings.append(f"{path}: not a path table (kind {table.get('kind')!r})")
                continue
            for row in table.get("rows", []):
                if row.get("kind") == "move":
                    moved[row["old"]] = (row["new"], table.get("move") or path)
        return moved

    @property
    def declarations(self):
        """The engine's manifest, read once, at the checkout's own revision."""
        if self._declarations is None:
            self._declarations = read_declarations(self.declarations_path, git(self.repo, "rev-parse", "HEAD").strip())
        if self.viewer_ids["revision"] != self._declarations["revision"]:
            raise SystemExit("The identifier moves and declarations are from different revisions.")
        return self._declarations

    def is_legacy(self, path):
        return bool(self.legacy_rule) and path.startswith(self.legacy_rule["folder"])

    def current_path(self, path):
        """Where a file named before a move of the engine's source stands now (the file itself if it never moved)."""
        seen = set()
        while path in self.moves and path not in seen:
            seen.add(path)
            path = self.moves[path][0]
        return path

    # ------------------------------------------------------------ what is left out of the picture

    def is_left_out(self, identifier):
        return any(item["id"] == identifier for item in self.left_out)

    def leave_out(self, identifier, kind, label, flag, **more):
        """Record a part that its overlay flags as left out, with the wordings that stand in meanwhile."""
        left_out_flag(identifier, flag)
        self.left_out.append({"id": identifier, "kind": kind, "label": label, **more, "since": flag["since"], "says": flag["says"], "reason": flag["reason"]})
        for change in flag.get("rewords", []):
            if not isinstance(change, dict) or not all(isinstance(change.get(key), str) for key in ("in", "id", "field")) or "to" not in change:
                raise SystemExit(f"{identifier}: a wording under left_out needs 'in', 'id', 'field' and 'to'")
            self.rewords[(change["in"], change["id"], change["field"])] = change["to"]

    def reword(self, where, identifier, field, text):
        """The text of a field as the page shows it: its own, unless something left out gives another wording."""
        key = (where, identifier, field)
        if key not in self.rewords:
            return text
        self.reworded.add(key)
        return self.rewords[key]

    # ------------------------------------------------------------ entities and edges

    def add(self, entity):
        if entity["id"] in self.entities:
            raise SystemExit(f"duplicate entity id {entity['id']}")
        status = entity.get("status")
        if status is not None and status not in self.statuses:
            raise SystemExit(f"{entity['id']}: unknown status {status}")
        entity.setdefault("facts", [])
        entity.setdefault("sources", [])
        self.entities[entity["id"]] = entity
        return entity

    def link(self, source, target, kind, label=None, weight=1):
        if source == target:
            return
        key = (source, target, kind)
        if kind == "conflicts":
            key = (*sorted((source, target)), kind)
        relation = self.relations.get(key)
        if relation is None:
            relation = {"from": key[0], "to": key[1], "kind": kind, "weight": 0, "labels": []}
            self.relations[key] = relation
        relation["weight"] += weight
        if label and label not in relation["labels"]:
            relation["labels"].append(label)

    # ------------------------------------------------------------ operators

    def operators(self):
        config = self.overlay["operators"]
        found = {}
        # The composite's operators, as the engine declares them (its manifest's `pieces`). Four things the
        # manifest does not hold apart are read from the operator's own class, found by the manifest's module and
        # class name: RK4 (whether it runs under an RK4 inner step), ACCEPTS_WRITES (the increments it accepts
        # from other operators), which of its `provides` are view fields rather than readout columns
        # (VIEW_FIELDS, the head of `provides`), and which of its `controls` are availabilities it multiplies
        # rather than its own control fields (CONTROL_FACTORS, the tail of `controls`). Each is checked against the
        # manifest where the manifest holds it.
        for piece in self.declarations["pieces"]:
            if piece.get("piece") != "operator":
                continue
            if piece.get("interface") != "cells.operator@1":
                # A model family's own operator, of an interface of its family's (a family operator, seam F): it has
                # no part in the composite's contract, and is drawn on the part that holds its file, as a law is.
                continue
            law, fields = piece["declared_id"], piece.get("fields") or {}
            class_name, path = fields.get("class_name"), piece.get("module_path")
            reads = piece.get("reads") or []
            values = {
                "LAW_ID": law,
                "STEP_ID": fields.get("step_method"),
                "EVENT": "event" in (fields.get("parts") or []),
                "SPLIT": "split" in (fields.get("parts") or []),
                "PROCESS": "process" in (fields.get("parts") or []),
                "REQUIRES": list((piece.get("requires") or {}).get("laws") or []),
                "ENTITY_WRITES": dict(piece.get("writes") or {}),
                "VIEW_READS": [read["name"] for read in reads if read.get("mode") == "current"],
                "CONFLICTS_VIEW": [read["name"] for read in reads if read.get("mode") in ("fixed", "reference")],
                "CLOSES": list(fields.get("closes") or []),
                "RETIRES": fields.get("retires"),
                "HEAT_FIELDS": list((piece.get("energy") or {}).get("heat") or []),
                "WORK_FIELDS": list((piece.get("energy") or {}).get("work") or []),
                "LEDGERS": list(piece.get("ledgers") or []),
                "EXPERIMENT_KEYS": list(fields.get("experiment_keys") or []),
                "STATE_AXES": dict(piece.get("owns") or {}),
            }
            provides = list(piece.get("provides") or [])
            source = self.package.module(piece["module"]) if piece.get("module") else None
            if source is None or not class_name:
                self.warnings.append(f"operator {law}: the manifest names no class the map can read ({piece.get('module')}, {class_name})")
                own, unresolved = {}, []
            else:
                own, unresolved = self.evaluator.class_attributes(source, class_name, {"LAW_ID", "RK4", "ACCEPTS_WRITES", "VIEW_FIELDS", "CONTROL_FACTORS"})
            if unresolved:
                self.warnings.append(f"operator {law}: unresolved in {class_name}: {sorted(unresolved)}")
            own = plain(own)
            if own.get("LAW_ID") != law:
                self.warnings.append(f"operator {law}: the manifest names {class_name} in {path}, whose LAW_ID is {own.get('LAW_ID')!r}")
            view = list(own.get("VIEW_FIELDS") or [])
            if provides[: len(view)] != view:
                self.warnings.append(f"operator {law}: its view fields in the source are not the first of the manifest's provides")
            values["VIEW_FIELDS"] = view
            controls, factors = list(piece.get("controls") or []), list(own.get("CONTROL_FACTORS") or [])
            if factors and controls[-len(factors):] != factors:
                self.warnings.append(f"operator {law}: the availabilities it multiplies in the source are not the last of the manifest's controls")
            values["CONTROL_FACTORS"] = factors
            values["RK4"] = own.get("RK4")
            values["ACCEPTS_WRITES"] = own.get("ACCEPTS_WRITES") or {}
            node = source.classes.get(class_name) if source is not None and class_name else None
            found[law] = {"class": class_name, "path": path, "values": values, "class_doc": paragraph(ast.get_docstring(node)) if node else None}
        for law in config["items"]:
            if law not in found:
                self.warnings.append(f"overlay names operator {law}, which is not registered")
        # A module may declare more than one operator (a next version beside the first). Its file stays the part of the
        # first operator the manifest lists, so that every file keeps one part; each operator's detail is then its own
        # class's docstring, not the module's.
        shared = Counter(record["path"] for record in found.values())
        for law, record in found.items():
            curated = config["items"].get(law)
            if curated is None:
                self.warnings.append(f"registered operator {law} has no overlay entry")
                curated = {"label": law}
            identifier = f"op.{law}"
            paths = [record["path"], *curated.get("files", [])]
            for path in paths:
                self.owner.setdefault(path, identifier)
            record["id"] = identifier
            values = record["values"]
            parts = [
                name
                for name, flag in (("event map", "EVENT"), ("split half-steps", "SPLIT"), ("in-step process", "PROCESS"))
                if values.get(flag)
            ]
            facts = [["Law", law], ["Class", record["class"]]]
            if parts:
                facts.append(["Parts of the step", ", ".join(parts)])
            if values.get("STEP_ID"):
                facts.append(["Step method", values["STEP_ID"]])
            if values.get("RK4"):
                facts.append(["Under an RK4 inner step", values["RK4"]])
            if values.get("EXPERIMENT_KEYS"):
                facts.append(["Schedule in a definition", ", ".join(values["EXPERIMENT_KEYS"])])
            for label, key in (("Heat booked in", "HEAT_FIELDS"), ("Work booked in", "WORK_FIELDS"), ("Own ledgers", "LEDGERS")):
                if values.get(key):
                    facts.append([label, join_names(values[key])])
            if values.get("STATE_AXES"):
                facts.append(["State it owns", f"{len(values['STATE_AXES'])} fields"])
            self.add(
                {
                    "id": identifier,
                    "label": curated.get("label", law),
                    "kind": "operator",
                    "group": config["layer"],
                    "status": curated.get("status"),
                    "as_of": curated.get("as_of"),
                    "plain": curated.get("plain", ""),
                    "detail": (record["class_doc"] if shared[record["path"]] > 1 and record["class_doc"] else first_paragraph(self.repo / record["path"])),
                    "facts": facts,
                    "sources": [{"path": path} for path in paths] + curated.get("sources", []),
                    "files": paths,
                }
            )
        self.found_operators = found

    def operator_relations(self):
        found = self.found_operators
        field_entity = self.overlay["shared_state"]["fields"]
        state_id = self.state_ids
        providers, acceptors, closers = defaultdict(list), {}, defaultdict(list)
        for law, record in found.items():
            values = record["values"]
            for field in values.get("VIEW_FIELDS") or []:
                providers[field].append(record["id"])
            for field in values.get("CLOSES") or []:
                closers[field].append(record["id"])
            for field in values.get("ACCEPTS_WRITES") or {}:
                acceptors[field] = record["id"]
        by_law = {law: record["id"] for law, record in found.items()}
        for law, record in found.items():
            identifier, values = record["id"], record["values"]
            entity = self.entities[identifier]
            if "models.composite" in self.entities:
                self.link(identifier, "models.composite", "operator_of")
            for required in values.get("REQUIRES") or []:
                if required in by_law:
                    self.link(identifier, by_law[required], "requires")
                else:
                    self.warnings.append(f"{law} requires {required}, which is not registered")
            ledgers = []
            for field in values.get("ENTITY_WRITES") or {}:
                if field in acceptors and acceptors[field] != identifier:
                    self.link(identifier, acceptors[field], "writes", field)
                if field in field_entity:
                    self.link(identifier, state_id[field_entity[field]], "writes", field)
                elif field not in acceptors:
                    ledgers.append(field)
            if ledgers:
                entity["facts"].append(["Books into the inner model's ledgers", join_names(ledgers)])
            for field in values.get("VIEW_FIELDS") or []:
                if field in field_entity:
                    self.link(identifier, state_id[field_entity[field]], "provides", field)
            for field in values.get("CONTROL_FACTORS") or []:
                if field in field_entity:
                    self.link(identifier, state_id[field_entity[field]], "writes", f"scales the {field} availability")
            for field in values.get("CLOSES") or []:
                if field in field_entity:
                    self.link(identifier, state_id[field_entity[field]], "writes", f"closes {field} slots")
            for field in values.get("VIEW_READS") or []:
                for provider in providers.get(field, []):
                    if provider != identifier:
                        self.link(identifier, provider, "reads", field)
            for field in values.get("CONFLICTS_VIEW") or []:
                for other in providers.get(field, []) + closers.get(field, []):
                    if other != identifier:
                        self.link(identifier, other, "conflicts", field)
            # Each view field has exactly one provider: the composite refuses a second one.
            for field in values.get("VIEW_FIELDS") or []:
                for other in providers.get(field, []):
                    if other != identifier:
                        self.link(identifier, other, "conflicts", f"both provide {field}")
            for label, key in (("Provides", "VIEW_FIELDS"), ("Reads as declared", "CONFLICTS_VIEW")):
                if values.get(key):
                    entity["facts"].append([label, join_names(values[key])])

    # ------------------------------------------------------------ components

    def place_models(self, matched):
        """Where each model the engine declares is drawn: {(part, file): [(model, detail)]}.

        The models are the manifest's `models`, and only they are drawn as models. The manifest names the module that
        declares a model's structure (its spec, mostly under src/cells/definitions/), not the module that runs it, so a model
        is drawn on the part of the model module that names it (MODEL_ID, read from the source for this placing only:
        src/cells/models/<file>.py, or a family's package, src/cells/models/<family>/__init__.py). A declared model
        that no model module names is drawn on the part that holds its declaring module. A MODEL_ID the manifest does
        not list as active, an older family's, is not drawn (self.undeclared_models).
        """
        declared = {}
        for model in self.declarations["models"]:
            declared[model["declared_id"]] = declared[model["id"]] = model["declared_id"]
        placed, drawn = defaultdict(list), set()
        self.undeclared_models = []  # (part, model ID, file)
        for part, paths in matched.items():
            for path in paths:
                if not model_module(path):
                    continue
                module = self.package.module(self.package.dotted_of(self.repo / path))
                try:
                    model = self.evaluator.constant(module, "MODEL_ID")
                except Unresolved:
                    model = None
                if isinstance(model, str) and model in declared:
                    placed[(part, path)].append((declared[model], Path(path).name))
                    drawn.add(declared[model])
                elif isinstance(model, str):
                    self.undeclared_models.append((part, model, path))
                    self.warnings.append(f"{path} names model {model} outside the active registry")
        for model in self.declarations["models"]:
            if model["declared_id"] in drawn:
                continue
            part = self.owner.get(model.get("module_path"))
            if part:
                placed[(part, model["module_path"])].append((model["declared_id"], f"declared in {Path(model['module_path']).name}"))
            else:
                self.warnings.append(f"model {model['declared_id']}: declared in {model.get('module_path')}, which no part of the map holds")
        return placed

    def components(self):
        self.pieces_drawn = set()  # the laws, kinds and family operators drawn as members of their parts
        compiled = []
        for component in self.overlay["components"]:
            patterns = [glob_regex(pattern) for pattern in component.get("match", [])]
            compiled.append((component, patterns))
        matched, held = defaultdict(list), defaultdict(list)
        for path in self.files:
            if path in self.owner:
                continue
            for component, patterns in compiled:
                if any(pattern.match(path) for pattern in patterns):
                    if self.is_legacy(path):
                        self.legacy[path] = component["id"]
                        held[component["id"]].append(path)
                    else:
                        self.owner[path] = component["id"]
                        matched[component["id"]].append(path)
                    break
            else:
                if self.is_legacy(path):
                    self.legacy[path] = None
        placed = self.place_models(matched)
        for component, _ in compiled:
            paths = matched.get(component["id"], [])
            patterns = component.get("match", [])
            retired = bool(patterns) and not held.get(component["id"]) and all(self.is_legacy(pattern) for pattern in patterns)
            if not paths and (retired or held.get(component["id"])):
                # Every file of this part is held legacy code: the part is left out of the picture.
                rule = self.legacy_rule
                self.leave_out(component["id"], "component", component["label"], {"since": rule["since"], "says": component["label"], "reason": "its source was removed from the engine" if retired else rule["reason"]}, layer=component["layer"], files=len(held.get(component["id"], [])))
                continue
            python = [path for path in paths if path.endswith(".py")]
            lines = sum(count_lines(self.repo / path) for path in python)
            facts = []
            if paths:
                facts.append(["Files", f"{len(paths):,}"])
            if python:
                facts.append(["Lines of Python", f"{lines:,}"])
            members, models = [], []
            for path in python:
                for model, detail in placed.get((component["id"], path), []):
                    models.append(model)
                    members.append({"label": model, "detail": detail})
                if model_module(path):
                    module = self.package.module(self.package.dotted_of(self.repo / path))
                    if module and "device_checks" in module.functions:
                        members.append({"label": "device checks", "detail": Path(path).name})
            if models:
                facts.append(["Model identifiers", f"{len(set(models))}"])
            if component.get("facts_from") == "declarations":
                # The manifest's own counts, on the part that writes it: what the map read, and at which revision.
                manifest = self.declarations
                pieces = Counter(piece["piece"] for piece in manifest["pieces"])
                facts += [
                    ["Read by this map", f"{manifest['kind']}, written at {manifest['revision'][:8]}"],
                    ["Laws, kinds and operators", f"{pieces['law']}, {pieces['kind']} and {pieces['operator']}"],
                    ["Active models", f"{len(manifest['models'])}"],
                ]
            # The laws, kinds and family operators the engine declares from this part's files (its manifest's
            # module_path). A family operator is an operator of an interface other than the composite's.
            declared = [piece for piece in self.declarations["pieces"] if is_drawn_on_its_part(piece) and piece.get("module_path") in paths]
            for label, kind in (("Laws it declares", "law"), ("Kinds it declares", "kind"), ("Family operators it declares", "operator")):
                own = sorted((piece for piece in declared if piece["piece"] == kind), key=lambda piece: piece["declared_id"])
                if own:
                    facts.append([label, f"{len(own)}"])
                    for piece in own:
                        what = f"operator ({piece.get('interface')})" if kind == "operator" else kind
                        members.append({"label": piece["declared_id"], "detail": f"{what}, declared in {Path(piece['module_path']).name}"})
                    self.pieces_drawn.update(piece["declared_id"] for piece in own)
            patterns = component.get("match", [])
            literal = [pattern for pattern in patterns if "*" not in pattern and "?" not in pattern and pattern in paths]
            detail = None
            if literal and len(python) <= 6 and (self.repo / literal[0]).is_file():
                detail = first_paragraph(self.repo / literal[0])
            entity = {
                "id": component["id"],
                "label": component["label"],
                "kind": "component",
                "group": component["layer"],
                "status": component.get("status"),
                "as_of": component.get("as_of"),
                "plain": component.get("plain", ""),
                "detail": detail,
                "facts": facts,
                "members": members,
                "sources": list(component.get("sources", [])),
                "files": paths if len(paths) <= 12 else [],
                "weight": lines,
            }
            if component.get("match") and not paths:
                if component.get("catch_all"):
                    continue  # Every file found a more specific part.
                self.warnings.append(f"{component['id']}: its patterns match no tracked file")
            self.add(entity)
        tiers = self.repo / "tests" / "test_tiers.json"
        if tiers.is_file() and "val.tiers" in self.entities:
            record = json.loads(tiers.read_text(encoding="utf-8"))
            for name, value in sorted(record.get("tiers", {}).items()):
                if isinstance(value, dict) and isinstance(value.get("files"), (list, dict)):
                    value = value["files"]
                count = len(value) if isinstance(value, (dict, list)) else None
                if count is not None:
                    self.entities["val.tiers"]["facts"].append([f"Tier {name} test files", f"{count:,}"])

    def uses(self):
        """An edge between two parts for every import of one part's module by another's."""
        for path, owner in sorted(self.owner.items()):
            if not (path.startswith("src/cells/") and path.endswith(".py")):
                continue
            module = self.package.module(self.package.dotted_of(self.repo / path))
            if module is None:
                continue
            for dotted in module.imported_modules():
                target = self.package.path_of(dotted)
                if target is None:
                    continue
                other = self.owner.get(target.relative_to(self.repo).as_posix())
                if other and other != owner and owner in self.entities and other in self.entities:
                    self.link(owner, other, "uses")

    def coverage(self):
        read = [path for path in self.files if path.startswith("src/cells/") and path.endswith(".py")]
        legacy = [path for path in read if self.is_legacy(path)]
        engine = [path for path in read if not self.is_legacy(path)]
        missing = [path for path in engine if path not in self.owner]
        if missing:
            self.warnings.append(f"{len(missing)} engine files belong to no part: {join_names(missing, 8)}")
        # `engine_files` counts the files the map draws from; those under the legacy folder are counted apart.
        return {"engine_files": len(engine), "engine_files_placed": len(engine) - len(missing), "engine_files_read": len(read), "engine_files_legacy": len(legacy)}

    # ------------------------------------------------------------ plan document

    def shared_state(self):
        config = self.overlay["shared_state"]
        lines = (self.repo / config["doc"]).read_text(encoding="utf-8").splitlines()
        start = next((i for i, line in enumerate(lines) if line.lstrip("# ").strip() == config["heading"]), None)
        rows = table_after(lines, start + 1)[1:] if start is not None else []
        if not rows:
            self.warnings.append(f"shared-state table not found in {config['doc']}")
        self.state_ids = {}
        for row in rows:
            name = unmark(row[0])
            identifier = "state." + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
            self.state_ids[name] = identifier
            self.add(
                {
                    "id": identifier,
                    "label": name,
                    "kind": "state",
                    "group": config["layer"],
                    "status": None,
                    "plain": config["plain"].get(name, ""),
                    "note": config["note"],
                    "facts": [["Owns", unmark(row[1])], ["Others contribute", unmark(row[2])]],
                    "sources": [{"path": config["doc"], "where": config["heading"]}],
                }
            )
        for field, name in config["fields"].items():
            if name not in self.state_ids:
                raise SystemExit(f"overlay maps {field} to unknown entity {name}")

    def gates(self):
        config = self.overlay["gates"]
        lines = (self.repo / config["doc"]).read_text(encoding="utf-8").splitlines()
        parsed = []
        for index, line in enumerate(lines):
            match = re.match(r"###\s+Gate:\s+(.*)", line)
            if match:
                name = re.sub(r"\s*\(.*\)\s*$", "", match.group(1)).strip()
                rows = table_after(lines, index + 1)
                deliverables = [unmark(row[0]) for row in rows[1:]] if rows and rows[0][0] == "Deliverable" else []
                parsed.append((name, deliverables))
        names = {name.lower() for name, _ in parsed}
        for name in config["items"]:
            if name not in names:
                self.warnings.append(f"overlay names gate '{name}', which {config['doc']} does not have")
        for order, (name, deliverables) in enumerate(parsed):
            curated = config["items"].get(name.lower())
            if curated is None:
                self.warnings.append(f"gate '{name}' has no overlay entry")
                curated = {"label": name.capitalize()}
            identifier = f"gate.{order + 1}"
            facts = [["Order in the plan", f"{order + 1} of {len(parsed)}"]]
            self.add(
                {
                    "id": identifier,
                    "label": curated.get("label", name),
                    "kind": "gate",
                    "group": config["layer"],
                    "status": None,
                    "order": order,
                    "plain": curated.get("plain", ""),
                    "note": curated.get("note"),
                    "facts": facts,
                    "members": [{"label": item} for item in deliverables],
                    "sources": [{"path": config["doc"], "where": f"Gate: {name}"}],
                }
            )
            for target in curated.get("delivers", []):
                self.pending.append((identifier, target, "delivers", None))

    # ------------------------------------------------------------ biology map

    def capabilities(self):
        # A capability flagged `left_out` is not in the scene. The engine parts that implement
        # it stay on the map, and each says so in its own text (the flag's `engine_note`).
        for capability in self.overlay["capabilities"]:
            flag = capability.get("left_out")
            if not flag:
                continue
            self.leave_out(capability["id"], "capability", capability["label"], flag, part=capability["part"])
            for target in capability.get("implemented_by", []):
                if flag.get("engine_note") and target in self.entities:
                    self.entities[target]["plain"] = f"{self.entities[target].get('plain', '')} {flag['engine_note']}".strip()
        for capability in self.overlay["capabilities"]:
            if capability.get("left_out"):
                continue
            self.add(
                {
                    "id": capability["id"],
                    "label": capability["label"],
                    "kind": "capability",
                    "group": "biology",
                    "status": capability.get("status"),
                    "as_of": capability.get("as_of"),
                    "representation": capability.get("representation"),
                    "runs_in": capability.get("runs_in", []),
                    "part": capability["part"],
                    "scale": capability["scale"],
                    "plain": capability.get("plain", ""),
                    "sources": list(capability.get("sources", [])),
                }
            )
            for target in capability.get("implemented_by", []):
                self.pending.append((capability["id"], target, "implements", None))
        for scale in self.overlay["scales"]:
            self.add(
                {
                    "id": scale["id"],
                    "label": scale["label"],
                    "kind": "scale",
                    "group": "biology",
                    "status": scale.get("status"),
                    "order": scale["order"],
                    "plain": self.reword("scales", scale["id"], "plain", scale.get("plain", "")),
                    "note": self.reword("scales", scale["id"], "note", scale.get("note")),
                    "sources": list(scale.get("sources", [])),
                }
            )

    # ------------------------------------------------------------ assembly

    def run(self):
        self.pending = []
        self.operators()
        self.components()
        for piece in self.declarations["pieces"]:
            if is_drawn_on_its_part(piece) and piece["declared_id"] not in self.pieces_drawn:
                self.warnings.append(f"{piece['piece']} {piece['declared_id']}: declared in {piece.get('module_path')}, which no drawn part holds")
        self.shared_state()
        self.gates()
        self.capabilities()
        self.operator_relations()
        self.uses()
        if self.protein_data:
            self.proteins = Atlas(self, *self.protein_data).run()
        for relation in self.overlay["relations"]:
            self.pending.append((relation["from"], relation["to"], relation["kind"], relation.get("label")))
        kinds = {kind["id"] for kind in self.overlay["relation_kinds"]}
        for source, target, kind, label in self.pending:
            if self.is_left_out(source) or self.is_left_out(target):
                continue  # what is left out of the picture takes its links with it
            for end in (source, target):
                if end not in self.entities:
                    raise SystemExit(f"relation {source} -> {target} ({kind}): unknown part {end}")
            if kind not in kinds:
                raise SystemExit(f"relation {source} -> {target}: unknown kind {kind}")
            self.link(source, target, kind, label)
        coverage = self.coverage()
        tracked = set(self.files)
        # A source under visualizer/ is one of the viewer's own notes. It lives in the folder this tool runs from
        # and reaches the checkout read here with the branch's next merge, so it is looked for in this folder too.
        # One found only here is named in a remark: its link on the page opens once that checkout has it.
        for entity in self.entities.values():
            for source in entity.get("sources", []):
                if source.get("revision"):
                    result = subprocess.run(["git", "-C", str(self.repo), "cat-file", "-e", f"{source['revision']}:{source['path']}"], capture_output=True)
                    if result.returncode:
                        self.warnings.append(f"{entity['id']}: missing historical source {source['path']} at {source['revision']}")
                    continue
                if source["path"] in tracked:
                    continue
                if own_file(source["path"]):
                    if source["path"] not in self.ahead:
                        self.ahead.append(source["path"])
                    continue
                self.warnings.append(f"{entity['id']}: cited source {source['path']} is not a tracked file")
        relations = []
        for relation in self.relations.values():
            labels = relation.pop("labels")
            if labels:
                relation["label"] = join_names(labels, 5)
            relations.append(relation)
        relations.sort(key=lambda item: (item["kind"], item["from"], item["to"]))
        entities = []
        for entity in self.entities.values():
            entities.append({key: value for key, value in entity.items() if value not in (None, [], "")})
        return entities, relations, coverage


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", help="the Cells checkout to read (default: the one CELLS_ENGINE_REPO names, else the main checkout)")
    parser.add_argument("--overlay", default=str(HERE.parent / "data" / "architecture" / "overlay.json"))
    parser.add_argument("--out", default=str(HERE.parent / "data" / "architecture" / "architecture.scene.json"))
    parser.add_argument("--proteins", default=str(HERE.parent / "data" / "proteins"), help="folder with the protein inventory's snapshot and overlay")
    parser.add_argument("--atlases", help="folder with the species atlases (default: atlases/ in the proteins folder; it need not exist)")
    parser.add_argument("--species", default=str(HERE.parent / "data" / "species"), help="folder with the species files and their shapes (schema/SPECIES.md; it need not exist)")
    parser.add_argument("--cells", default=str(HERE.parent / "data" / "cells"), help="folder with the cell types' files (schema/CELL_TYPES.md; it need not exist)")
    parser.add_argument("--models", default=str(HERE.parent / "data" / "models"), help="folder with the model systems' files (schema/MODEL_SYSTEMS.md; it need not exist)")
    parser.add_argument("--machines", default=str(HERE.parent / "data" / "machines"), help="folder with the machine files (schema/MACHINES.md; it need not exist)")
    parser.add_argument("--declarations", default=str(DECLARATIONS_FILE), help="the engine's declarations manifest, written at the revision of the checkout read (data/engine/README.md)")
    parser.add_argument("--strict", action="store_true", help="exit with an error if anything is warned about")
    arguments = parser.parse_args()

    repo = find_repo(arguments.repo)
    overlay = json.loads(Path(arguments.overlay).read_text(encoding="utf-8"))
    folder = Path(arguments.proteins)
    proteins = None
    if (folder / "inventory.snapshot.json").is_file():
        proteins = tuple(json.loads((folder / name).read_text(encoding="utf-8")) for name in ("inventory.snapshot.json", "overlay.json"))
        # The species atlases beside them (schema/SPECIES_ATLAS.md): any number of files, or none.
        # Each species' own proteins lie in a folder of its own there (schema/SPECIES_PROTEINS.md).
        proteins += (Path(arguments.atlases) if arguments.atlases else folder / "atlases", folder)
    build = Build(repo, overlay, proteins, declarations=arguments.declarations)
    entities, relations, coverage = build.run()

    revision = git(repo, "rev-parse", "--short", "HEAD").strip()
    # The revision the map states must be one that others can find. The checkout read may stand at a commit that was
    # never pushed, or that was amended before it was: on 16 November 2026 the map, a published page and a picture
    # for the project's README stated one that exists nowhere else. So where the checkout has a remote, its HEAD must
    # be on a remote branch as last fetched; a checkout with no remote (an export, a test's copy) is taken as it is.
    if git(repo, "remote").strip() and not git(repo, "branch", "-r", "--contains", "HEAD").strip():
        build.warnings.append(f"the checkout read stands at {revision}, which is on no remote branch as last fetched: the map would state a revision that others cannot find (read it again once that revision is pushed)")
    # The species the viewer can show (schema/SPECIES.md): any number of files, or none. A species'
    # place for a capability that is left out of the picture stays in its file and is not shown.
    hidden = {item["id"] for item in build.left_out if item["kind"] == "capability"}
    remarks_machines = []
    # The entries of the species switch (schema/ENTRIES.md): the species as the species reader reads them, each with its cell
    # types, and the model systems beside them. A citation of the record is a tracked file of the checkout read or one of the
    # viewer's own; a model system's run files are published beside the page, at models/<id>/<name>.json.
    species, shapes, models, breaches, noted = read_entries(
        arguments.species, arguments.cells, arguments.models, {item["id"]: item["scale"] for item in overlay["capabilities"]}, hidden,
        tracked=build.files, own=HERE.parent, parts={item["id"]: item["part"] for item in overlay["capabilities"]},
        # A modelled entry names a model the engine declares with its structure (schema/ENTRIES.md).
        declared={name for model in build.declarations["models"] if model.get("rows")
                  for name in [model["id"], *(old for old, new in build.aliases.items() if new == model["id"])]},
    )
    for model in models:
        for run in model.get("runs", []):
            run["path"] = f"models/{model['id']}/{Path(run['file']).name}"  # where the page fetches it (tools/lib/build_page.mjs, modelFiles)
    build.warnings.extend(breaches)
    # A species may be held back from the picture for now (the overlay's `species_held`): its
    # files stay in the repository and are read and checked like any other, and the scene
    # carries nothing of it (no species, shape, atlas or proteins) but one line among what is
    # left out, which says why. Taking the entry out of the overlay brings the species in.
    for identifier, hold in sorted((overlay.get("species_held") or {}).items()):
        if not all(isinstance(hold.get(key), str) and hold[key].strip() for key in ("since", "says", "reason")):
            build.warnings.append(f"held back: {identifier} needs since, says and reason")
            continue
        known = [item for item in species if item["id"] == identifier]
        held_model = [item for item in models if item["id"] == identifier]
        if held_model:  # a model system may be held back the same way (schema/MODEL_SYSTEMS.md)
            models = [item for item in models if item["id"] != identifier]
            build.left_out.append({"id": f"model.{identifier}", "kind": "model system", "label": held_model[0].get("label") or identifier, "since": hold["since"], "says": hold["says"], "reason": hold["reason"]})
            continue
        if not known:
            build.warnings.append(f"held back: there is no species file for {identifier}")
            continue
        species = [item for item in species if item["id"] != identifier]
        used = {level["shape"]["ref"] for item in species for level in item["levels"] if level.get("shape", {}).get("kind") == "outline"}
        shapes = {key: value for key, value in shapes.items() if key in used}
        if build.proteins:
            for key in ("atlases", "shelves"):
                build.proteins[key] = [item for item in build.proteins.get(key, []) if item["id"] != identifier]
        build.left_out.append({"id": f"species.{identifier}", "kind": "species", "label": known[0].get("label") or identifier, "since": hold["since"], "says": hold["says"], "reason": hold["reason"]})
    # Machines (schema/MACHINES.md): a species' entry names each machine that has a file of its own, by its id,
    # its label and the file, which is published beside the page and fetched when the visitor looks closer. A
    # species without one is written exactly as before.
    machines_folder = Path(arguments.machines)
    shown = {item["id"]: item for item in species}
    for path in sorted(machines_folder.glob("*.json")) if machines_folder.is_dir() else []:
        try:
            machine = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as error:
            build.warnings.append(f"machine {path.name}: not JSON ({error})")
            continue
        if machine.get("format") != "cells.visualizer.machine@1":
            build.warnings.append(f"machine {path.name}: its format is {machine.get('format')!r}")
            continue
        if path.name != f"{machine.get('species')}.{machine.get('id')}.json":
            build.warnings.append(f"machine {path.name}: a machine file is named <species>.<machine>.json")
            continue
        owner = shown.get(machine["species"])
        if owner is None:
            remarks_machines.append(f"machine {path.name}: its species is not shown, so the scene carries nothing of it")
            continue
        at = machine.get("at") or {}
        bases = [item.get("base", {}).get("id") for item in owner.get("cell", {}).get("parts", {}).get("appendages", []) if item.get("kind") == at.get("appendage")]
        if "appendage" in at and at.get("base") not in bases:
            build.warnings.append(f"machine {path.name}: no {at.get('appendage')} of {owner['id']} has the base {at.get('base')!r}")
            continue
        owner.setdefault("machines", []).append({"id": machine["id"], "label": machine.get("label") or machine["id"], "called": machine.get("called"), "at": at, "file": f"machines/{path.name}"})
    model_groups = [
        {**group, "description": build.reword("model_groups", group["id"], "description", group.get("description"))} if "description" in group else group
        for group in overlay["model_groups"]
    ]
    # A wording that stands in for a text that is not there was written for nothing: say so.
    for where, identifier, field in sorted(set(build.rewords) - build.reworded):
        build.warnings.append(f"left out: the wording for {field} of {identifier} ({where}) stands in for nothing the scene has")
    remarks = []
    if build.proteins:
        build.proteins["stamp"]["checked_at"] = revision
        remarks = build.proteins.pop("remarks", [])  # on the species atlases; reported below, not written
    remarks += noted
    remarks += remarks_machines
    remarks += [f"cited source {path} is the viewer's own and not yet in the checkout read: its link on the page opens once the branch is merged there" for path in build.ahead]
    # Only tracked files are read, so an untracked file does not make the reading dirty.
    dirty = bool(git(repo, "status", "--porcelain", "--untracked-files=no", "--", "src", "docs", "PROGRESS.md").strip())
    scene = {
        "format": SCENE_FORMAT,
        "kind": "architecture",
        "title": overlay["title"],
        "caveat": overlay["caveat"],
        "meta": {
            "as_of": overlay["as_of"],
            "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "revision": revision,
            "revision_date": git(repo, "log", "-1", "--format=%cs").strip(),
            "dirty": dirty,
            "generator": "visualizer/tools/extract_architecture.py",
            # Where a source's path links to. The engine's files are linked at the revision the map was read at, not at
            # the branch's tip: files move (D188 relocates most of src/cells), and a page that was published must keep
            # pointing at what it cited. The viewer's own files are linked on its branch, which is never rewritten and
            # holds notes that main gets only at its next merge.
            "source_base_url": pinned(overlay.get("source_base_url"), git(repo, "rev-parse", "HEAD").strip()),
            "own_source_base_url": pinned(overlay.get("source_base_url"), "visualizer"),
            # What the engine declares, as the map read it: its manifest, at the scene's own revision.
            "declarations": {
                "kind": build.declarations["kind"],
                "revision": build.declarations["revision"],
                "pieces": dict(Counter(piece["piece"] for piece in build.declarations["pieces"])),
                "models": len(build.declarations["models"]),
            },
            "counts": {
                **coverage,
                "parts": len(entities),
                "relations": len(relations),
                "by_kind": dict(Counter(entity["kind"] for entity in entities)),
                "by_status": dict(Counter(entity.get("status", "unstated") for entity in entities)),
            },
            "warnings": build.warnings,
        },
        "statuses": overlay["statuses"],
        "representations": overlay["representations"],
        "model_groups": model_groups,
        "relation_kinds": overlay["relation_kinds"] + (RELATION_KINDS if build.proteins else []),
        "groups": [{**layer, "lens": "engine"} for layer in overlay["layers"]] + LENS_GROUPS,
        "proteins": build.proteins,
        "species": species,
        "models": models,
        "shapes": shapes,
        # What the overlays flag as left out of the picture for now, each with how the page
        # names it and why. Nothing else in the scene points at these: no part, link or count.
        "left_out": build.left_out,
        "entities": entities,
        "relations": relations,
        "timeline": None,
        "channels": [],
    }
    out = Path(arguments.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(scene, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    counts = scene["meta"]["counts"]
    print(f"read {repo.name} at {revision}{' (dirty)' if dirty else ''}")
    print(f"{counts['parts']} parts, {counts['relations']} relations; "
          f"{counts['engine_files_placed']} of {counts['engine_files']} engine files placed"
          + (f", {counts['engine_files_legacy']} left out as legacy code ({counts['engine_files_read']} read)" if counts.get("engine_files_legacy") else ""))
    print("by kind:", counts["by_kind"])
    print("by status:", counts["by_status"])
    declared = build.declarations
    composite = sum(1 for piece in declared["pieces"] if piece.get("piece") == "operator" and piece.get("interface") == "cells.operator@1")
    family = sum(1 for piece in declared["pieces"] if piece.get("piece") == "operator") - composite
    print(f"read from the engine's declarations ({declared['kind']} at {declared['revision'][:8]}): {composite} composite operators, {family} family operators, "
          f"{len(declared['models'])} active models")
    for part, model, path in build.undeclared_models:
        print(f"  not drawn as a declared model: {model} ({path}, in {part}), outside the active registry")
    if build.proteins:
        stamp = build.proteins["stamp"]
        print(f"protein inventory of {stamp['created']} (engine read at {stamp['read_at']}): {stamp['records']} law records, found {stamp['found']}")
        if stamp["renamed"]:
            print("  renamed since:", ", ".join(f"{item['from']} -> {item['to']}" for item in stamp["renamed"]))
        if stamp.get("moved"):
            moves = sorted({item["move"] for item in stamp["moved"]})
            print(f"  found at their new place, through the engine's path tables ({', '.join(moves)}): {len(stamp['moved'])} files the inventory names")
        if stamp.get("in_legacy"):
            records = sum(len(items) for items in stamp["in_legacy"].values())
            print(f"  law records whose files are held legacy code, left out with it: {records}, in units {', '.join(stamp['in_legacy'])}")
        if stamp["gained"]:
            print(f"  identifiers the engine gained since, not reviewed by the inventory: {stamp['gained']['added']} ({stamp['gained']['where']})")
        for atlas in build.proteins.get("atlases", []):
            if not atlas.get("reference"):
                counts = atlas["counts"]
                print(f"species atlas {atlas['id']} of {atlas['made']}: products for {counts['with_products']} of {counts['units']} units, "
                      f"{counts['products']} gene products, {counts['candidates']} of them candidates")
    for item in (build.proteins or {}).get("shelves", []):
        sides = ", ".join(f"{count:,} {side}" for side, count in item["counts"].items())
        whole = f"{item['families']:,} families and {item['no_family']:,} with none, in {len(item['members'])} files of members" if item["kind"] == "families" else "one marker each"
        print(f"species proteins {item['id']} of {item['made']}: {item['proteins']:,} proteins ({sides}); {whole}; beside the page: {item['file']} ({item['bytes'] / 1024:.0f} KB)")
    for item in species:
        levels = ", ".join(level["id"] for level in item["levels"])
        print(f"species {item['id']}{' (the page opens on it)' if item['default'] else ''}: {levels}; modelled: {item['modelled']['state']}")
        for machine in item.get("machines", []):
            print(f"  machine {machine['id']} ({machine['label']}) at {machine['at']}; beside the page: {machine['file']} ({(machines_folder / Path(machine['file']).name).stat().st_size / 1024:.0f} KB)")
    for item in models:
        print(f"model system {item['id']} under {item['group']!r}: {', '.join(level['id'] for level in item['levels'])}; modelled: {item['modelled']['state']}; runs beside the page: {', '.join(run['path'] for run in item.get('runs', [])) or 'none'}")
    for item in build.left_out:
        print(f"left out of the picture since {item['since']}: {item['id']} ({item['says']}): {item['reason']}")
    for remark in remarks:
        print("remark:", remark)
    for warning in build.warnings:
        print("warning:", warning)
    print(f"wrote {out.name} ({out.stat().st_size / 1024:.0f} KB)")
    if arguments.strict and build.warnings:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
