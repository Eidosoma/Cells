#!/usr/bin/env python3
"""Build the architecture scene from a Cells checkout and the curated overlay.

What comes from the checkout (and so cannot drift from it):
  * which files belong to each part, their counts and lines;
  * which part uses which, from the import statements;
  * every registered operator of the composite model, with the declarations of its
    contract (what it requires, writes, provides, reads and conflicts with);
  * model identifiers, the plan's gates and the shared-state entities.

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
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from lib.protein_atlas import LENS_GROUPS, RELATION_KINDS, Atlas, left_out_flag  # noqa: E402
from lib.species import read_species  # noqa: E402
from lib.static_eval import Evaluator, Package, Unresolved, plain  # noqa: E402

SCENE_FORMAT = "cells.visualizer.scene@1"
DECLARATIONS = (
    "LAW_ID STEP_ID EVENT SPLIT PROCESS RK4 REQUIRES ENTITY_WRITES VIEW_FIELDS VIEW_READS "
    "CONTROL_FACTORS CONFLICTS_VIEW ACCEPTS_WRITES CLOSES RETIRES HEAT_FIELDS WORK_FIELDS "
    "LEDGERS EXPERIMENT_KEYS STATE_AXES"
).split()


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
    """The checkout to read: --repo, else the nearest tree that holds src/cells."""
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


# ---------------------------------------------------------------- the build


class Build:
    def __init__(self, repo, overlay, proteins=None):
        self.repo = repo
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
        module = self.package.module("cells.models.operators")
        config = self.overlay["operators"]
        found = {}
        registered = [
            node.func.args[0].id
            for node in ast.walk(module.env["OPERATORS"])
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Call)
            and getattr(node.func.func, "id", "") == "check_declarations"
        ]
        for class_name in registered:
            _, dotted, attribute = module.imports[class_name]
            source = self.package.module(dotted)
            values, unresolved = self.evaluator.class_attributes(source, attribute, set(DECLARATIONS))
            values = plain(values)
            law = values.get("LAW_ID")
            if not isinstance(law, str):
                self.warnings.append(f"operator {class_name}: LAW_ID unresolved; skipped")
                continue
            needed = [name for name in unresolved if name != "STATE_AXES"]
            if needed:
                self.warnings.append(f"operator {law}: unresolved declarations {needed}")
            path = source.path.relative_to(self.repo).as_posix()
            found[law] = {"class": class_name, "path": path, "values": values}
        for law in config["items"]:
            if law not in found:
                self.warnings.append(f"overlay names operator {law}, which is not registered")
        for law, record in found.items():
            curated = config["items"].get(law)
            if curated is None:
                self.warnings.append(f"registered operator {law} has no overlay entry")
                curated = {"label": law}
            identifier = f"op.{law}"
            paths = [record["path"], *curated.get("files", [])]
            for path in paths:
                self.owner[path] = identifier
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
                    "detail": first_paragraph(self.repo / record["path"]),
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

    def components(self):
        compiled = []
        for component in self.overlay["components"]:
            patterns = [glob_regex(pattern) for pattern in component.get("match", [])]
            compiled.append((component, patterns))
        matched = defaultdict(list)
        for path in self.files:
            if path in self.owner:
                continue
            for component, patterns in compiled:
                if any(pattern.match(path) for pattern in patterns):
                    self.owner[path] = component["id"]
                    matched[component["id"]].append(path)
                    break
        for component, _ in compiled:
            paths = matched.get(component["id"], [])
            python = [path for path in paths if path.endswith(".py")]
            lines = sum(count_lines(self.repo / path) for path in python)
            facts = []
            if paths:
                facts.append(["Files", f"{len(paths):,}"])
            if python:
                facts.append(["Lines of Python", f"{lines:,}"])
            members, models = [], []
            for path in python:
                if not path.startswith("src/cells/models/") or path.count("/") != 3:
                    continue
                module = self.package.module(self.package.dotted_of(self.repo / path))
                try:
                    model = self.evaluator.constant(module, "MODEL_ID")
                except Unresolved:
                    model = None
                if isinstance(model, str):
                    models.append(model)
                    members.append({"label": model, "detail": Path(path).name})
                if module and "device_checks" in module.functions:
                    members.append({"label": "device checks", "detail": Path(path).name})
            if models:
                facts.append(["Model identifiers", f"{len(set(models))}"])
            patterns = component.get("match", [])
            literal = [pattern for pattern in patterns if "*" not in pattern and "?" not in pattern]
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
        engine = [path for path in self.files if path.startswith("src/cells/") and path.endswith(".py")]
        missing = [path for path in engine if path not in self.owner]
        if missing:
            self.warnings.append(f"{len(missing)} engine files belong to no part: {join_names(missing, 8)}")
        return {"engine_files": len(engine), "engine_files_placed": len(engine) - len(missing)}

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
    parser.add_argument("--repo", help="the Cells checkout to read (default: the main checkout)")
    parser.add_argument("--overlay", default=str(HERE.parent / "data" / "architecture" / "overlay.json"))
    parser.add_argument("--out", default=str(HERE.parent / "data" / "architecture" / "architecture.scene.json"))
    parser.add_argument("--proteins", default=str(HERE.parent / "data" / "proteins"), help="folder with the protein inventory's snapshot and overlay")
    parser.add_argument("--atlases", help="folder with the species atlases (default: atlases/ in the proteins folder; it need not exist)")
    parser.add_argument("--species", default=str(HERE.parent / "data" / "species"), help="folder with the species files and their shapes (schema/SPECIES.md; it need not exist)")
    parser.add_argument("--machines", default=str(HERE.parent / "data" / "machines"), help="folder with the machine files (schema/MACHINES.md; it need not exist)")
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
    build = Build(repo, overlay, proteins)
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
    species, shapes, breaches, noted = read_species(arguments.species, {item["id"]: item["scale"] for item in overlay["capabilities"]}, hidden)
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
          f"{counts['engine_files_placed']} of {counts['engine_files']} engine files placed")
    print("by kind:", counts["by_kind"])
    print("by status:", counts["by_status"])
    if build.proteins:
        stamp = build.proteins["stamp"]
        print(f"protein inventory of {stamp['created']} (engine read at {stamp['read_at']}): {stamp['records']} law records, found {stamp['found']}")
        if stamp["renamed"]:
            print("  renamed since:", ", ".join(f"{item['from']} -> {item['to']}" for item in stamp["renamed"]))
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
