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
    def __init__(self, repo, overlay):
        self.repo = repo
        self.overlay = overlay
        self.warnings = []
        self.entities = {}
        self.relations = {}
        self.package = Package(repo / "src" / "cells", "cells")
        self.evaluator = Evaluator(self.package)
        self.files = [line for line in git(repo, "ls-files").splitlines() if line]
        self.owner = {}  # repo-relative path -> entity id
        self.statuses = {status["id"] for status in overlay["statuses"]}

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
        for capability in self.overlay["capabilities"]:
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
                    "plain": scale.get("plain", ""),
                    "note": scale.get("note"),
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
        for relation in self.overlay["relations"]:
            self.pending.append((relation["from"], relation["to"], relation["kind"], relation.get("label")))
        kinds = {kind["id"] for kind in self.overlay["relation_kinds"]}
        for source, target, kind, label in self.pending:
            for end in (source, target):
                if end not in self.entities:
                    raise SystemExit(f"relation {source} -> {target} ({kind}): unknown part {end}")
            if kind not in kinds:
                raise SystemExit(f"relation {source} -> {target}: unknown kind {kind}")
            self.link(source, target, kind, label)
        coverage = self.coverage()
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
    parser.add_argument("--strict", action="store_true", help="exit with an error if anything is warned about")
    arguments = parser.parse_args()

    repo = find_repo(arguments.repo)
    overlay = json.loads(Path(arguments.overlay).read_text(encoding="utf-8"))
    build = Build(repo, overlay)
    entities, relations, coverage = build.run()

    revision = git(repo, "rev-parse", "--short", "HEAD").strip()
    dirty = bool(git(repo, "status", "--porcelain", "--", "src", "docs", "PROGRESS.md").strip())
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
            "source_base_url": overlay.get("source_base_url"),
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
        "model_groups": overlay["model_groups"],
        "relation_kinds": overlay["relation_kinds"],
        "groups": overlay["layers"],
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
    for warning in build.warnings:
        print("warning:", warning)
    print(f"wrote {out.name} ({out.stat().st_size / 1024:.0f} KB)")
    if arguments.strict and build.warnings:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
