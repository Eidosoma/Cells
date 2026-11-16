"""Read the engine's declared pieces from its code, without running it, and write the Laws library's list.

The list is data/laws/pieces.json, held to schema/LAWS_LIBRARY.md. Each piece says where it
was read (the ref, the revision and the file), what of it was read from the code and what is
the viewer's curated words, which frames declare it, and a status only where a record states
one, with that record.

The code is read through git at a revision (`git show`), so no checkout is changed and no
file is written but the output. Python is parsed with ast by the viewer's own static reader
(tools/lib/static_eval.py); nothing of `cells` is imported or run.

    python3 tools/extract_laws.py [--repo PATH] [--ref main] [--candidate integration-d172] [--out data/laws/pieces.json | -] [--strict]

`--candidate` names a branch whose pieces are not on main yet (the landing candidate). Its
pieces that main lacks are listed as standing on it; once it has landed, it adds nothing and
the tool says so. Standard library only.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))
from static_eval import Evaluator, Package, Unresolved, plain  # noqa: E402

FORMAT = "cells.visualizer.laws@1"
ID = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)?@[0-9]+$")
# Where module-level constants name pieces, and which names do (schema/LAWS_LIBRARY.md, "How a piece is found").
CONSTANT_FOLDERS = ("src/cells/processes/", "src/cells/numerics/", "src/cells/coupling/", "src/cells/core/", "src/cells/models/")
OPERATOR_DECLARATIONS = (
    "LAW_ID STEP_ID EVENT SPLIT PROCESS RK4 REQUIRES ENTITY_WRITES VIEW_FIELDS VIEW_READS "
    "CONTROL_FACTORS CONFLICTS_VIEW ACCEPTS_WRITES CLOSES RETIRES HEAT_FIELDS WORK_FIELDS "
    "LEDGERS EXPERIMENT_KEYS"
).split()


def constant_kind(name, path):
    """What a module-level constant of this name names, or None: the rule of the contract."""
    if "SOLVER" in name or "METHOD" in name or name in ("ARS222_ID", "EULER_ID"):
        return "solver"
    if "LAW" in name:
        return "law"
    if name == "READ_ID":
        return "read"
    if name == "KIND_ID" and path.startswith("src/cells/processes/"):
        return "route kind"
    return None


# ---------------------------------------------------------------- reading a revision through git


def git(repo, *arguments):
    done = subprocess.run(["git", "-C", str(repo), *arguments], capture_output=True, text=True, check=False)
    return done.stdout if done.returncode == 0 else ""


class GitPath:
    """A file at a revision, standing in for a Path where the static reader reads one."""

    def __init__(self, repo, revision, relative):
        self.repo, self.revision, self.relative = repo, revision, relative
        self.name = PurePosixPath(relative).name

    def read_text(self, encoding="utf-8"):
        done = subprocess.run(["git", "-C", str(self.repo), "show", f"{self.revision}:{self.relative}"], capture_output=True, check=False)
        if done.returncode:
            raise FileNotFoundError(self.relative)
        return done.stdout.decode(encoding)

    def __str__(self):
        return self.relative


class GitPackage(Package):
    """src/cells at one revision, addressed by dotted module name (static_eval's Package, read through git)."""

    def __init__(self, repo, revision):
        super().__init__(Path("src/cells"), "cells")
        self.repo, self.revision = repo, revision
        listed = git(repo, "ls-tree", "-r", "--name-only", revision, "--", "src/cells")
        self.files = {line for line in listed.splitlines() if line.endswith(".py")}

    def path_of(self, dotted):
        if dotted != self.name and not dotted.startswith(self.name + "."):
            return None
        base = "/".join(["src", "cells", *dotted.split(".")[1:]])
        for candidate in (base + ".py", base + "/__init__.py"):
            if candidate in self.files:
                return GitPath(self.repo, self.revision, candidate)
        return None

    def dotted(self, relative):
        parts = ["cells", *PurePosixPath(relative).with_suffix("").parts[2:]]
        if parts[-1] == "__init__":
            parts.pop()
        return ".".join(parts)


class Reading:
    """Everything the tool reads at one revision."""

    def __init__(self, repo, ref):
        self.repo, self.ref = repo, ref
        self.revision = git(repo, "rev-parse", "--short", f"{ref}^{{commit}}").strip()
        if not self.revision:
            raise SystemExit(f"{ref} is not a revision of {repo}")
        self.date = git(repo, "log", "-1", "--format=%cs", self.revision).strip()
        self.package = GitPackage(repo, self.revision)
        self.evaluator = Evaluator(self.package)
        self.warnings = []

    def module(self, relative):
        return self.package.module(self.package.dotted(relative)) if relative in self.package.files else None

    def value(self, relative, name):
        module = self.module(relative)
        if module is None or name not in module.env:
            return None
        try:
            return plain(self.evaluator.constant(module, name))
        except Unresolved:
            return None

    def node_value(self, module, node):
        """The value of a small expression: a literal, a module-level name, or a module's constant (alias.NAME)."""
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            try:
                return plain(self.evaluator.constant(module, node.id))
            except Unresolved:
                return None
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            target = module.imports.get(node.value.id)
            if not target:
                return None
            dotted = target[1] if target[0] == "module" else f"{target[1]}.{target[2]}"
            other = self.package.module(dotted)
            if other is None:
                return None
            try:
                return plain(self.evaluator.constant(other, node.attr))
            except Unresolved:
                return None
        return None

    def doc(self, relative):
        """The first paragraph of a module's docstring, as its own words."""
        module = self.module(relative)
        if module is None:
            return None
        text = ast.get_docstring(module.tree) or ""
        line = " ".join(text.strip().split("\n\n")[0].split())
        return line[:300] or None

    def holds(self, identifier):
        """The files of src/cells at this revision in which the identifier stands as a string literal."""
        found = git(self.repo, "grep", "-l", "-F", f'"{identifier}"', self.revision, "--", "src/cells")
        return sorted(line.split(":", 1)[1] for line in found.splitlines() if ":" in line)

    def on_remote(self):
        """Whether others can find this revision: on a remote branch as last fetched (the map's extractor's rule, 06684552)."""
        if not git(self.repo, "remote").strip():
            return None  # a checkout with no remote (a test's copy) is taken as it is
        return bool(git(self.repo, "branch", "-r", "--contains", self.revision).strip())


# ---------------------------------------------------------------- what the code holds


def catalogue(reading):
    """Every LAW_CODES table in processes/: the older families' channel laws, with what the tables say of each."""
    laws = {}
    for relative in sorted(reading.package.files):
        if not relative.startswith("src/cells/processes/"):
            continue
        module = reading.module(relative)
        if "LAW_CODES" not in module.env:
            continue
        codes = reading.value(relative, "LAW_CODES")
        if not isinstance(codes, dict):
            reading.warnings.append(f"{relative}: LAW_CODES unresolved")
            continue
        tables = {name: reading.value(relative, name) for name in ("LAW_PERMEABILITIES", "GATE_POWERS", "STATE_COUNTS")}
        for law, code in codes.items():
            entry = laws.setdefault(law, {"codes": set(), "tables": [], "fields": {}})
            entry["codes"].add(code)
            entry["tables"].append(relative)
            fields = entry["fields"]
            if isinstance(tables["LAW_PERMEABILITIES"], dict) and law in tables["LAW_PERMEABILITIES"]:
                fields.setdefault("permeant", tables["LAW_PERMEABILITIES"][law])
            if isinstance(tables["GATE_POWERS"], dict) and law in tables["GATE_POWERS"]:
                fields.setdefault("gate_powers", tables["GATE_POWERS"][law])
            if isinstance(tables["STATE_COUNTS"], dict) and law in tables["STATE_COUNTS"]:
                fields.setdefault("gate_states", tables["STATE_COUNTS"][law])
    return laws


def constants(reading):
    """Module-level constants whose name says they name a piece, and whose value is an identifier."""
    found = {}
    for relative in sorted(reading.package.files):
        if not relative.startswith(CONSTANT_FOLDERS) or relative.startswith("src/cells/models/operators/"):
            continue
        module = reading.module(relative)
        for name, node in module.env.items():
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str) or not ID.match(node.value):
                continue
            kind = constant_kind(name, relative)
            if kind:
                found.setdefault(node.value, []).append({"path": relative, "name": name, "kind": kind})
    return found


def operators(reading):
    """The composite's registry, OPERATORS, with each operator's contract declarations."""
    relative = "src/cells/models/operators/__init__.py"
    module = reading.module(relative)
    if module is None or "OPERATORS" not in module.env:
        reading.warnings.append("no operator registry read")
        return []
    registered = [
        node.func.args[0].id
        for node in ast.walk(module.env["OPERATORS"])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Call) and getattr(node.func.func, "id", "") == "check_declarations"
    ]
    out = []
    for class_name in registered:
        _, dotted, attribute = module.imports[class_name]
        source = reading.package.module(dotted)
        values, unresolved = reading.evaluator.class_attributes(source, attribute, set(OPERATOR_DECLARATIONS))
        values = plain(values)
        law = values.get("LAW_ID")
        if not isinstance(law, str):
            reading.warnings.append(f"operator {class_name}: LAW_ID unresolved; left out")
            continue
        parts = [word for word, flag in (("event map", "EVENT"), ("split half-steps", "SPLIT"), ("in-step process", "PROCESS")) if values.get(flag)]
        fields = {"class": class_name, "parts": parts}
        for key, out_key in (("STEP_ID", "step_method"), ("RK4", "under_rk4"), ("REQUIRES", "requires"), ("VIEW_FIELDS", "provides"), ("VIEW_READS", "reads_current"),
                             ("CONFLICTS_VIEW", "reads_declared"), ("CONTROL_FACTORS", "multiplies"), ("ENTITY_WRITES", "writes"), ("HEAT_FIELDS", "heat"),
                             ("WORK_FIELDS", "work"), ("LEDGERS", "ledgers"), ("EXPERIMENT_KEYS", "schedule")):
            value = values.get(key)
            if value:
                fields[out_key] = sorted(value) if key == "ENTITY_WRITES" and isinstance(value, dict) else value
        out.append({"id": law, "path": str(source.path), "fields": fields, "unresolved": [name for name in unresolved if name != "STATE_AXES"]})
    return out


DECLARATION_CLASSES = ("ChannelLaw", "JunctionLaw", "PumpLaw", "RouteLaw")


def class_default(module, class_name, field):
    """A dataclass field's default, where the class body gives it as a literal."""
    node = module.classes.get(class_name)
    for statement in node.body if node else []:
        if isinstance(statement, ast.AnnAssign) and getattr(statement.target, "id", "") == field and isinstance(statement.value, ast.Constant):
            return statement.value.value
    return None


def declarations(reading, module, name):
    """Each declaration call of a registry such as CHANNEL_LAWS: its identifier (the first argument) and its provenance tag."""
    node = module.env.get(name)
    if node is None:
        return []
    found = []
    for call in ast.walk(node):
        if isinstance(call, ast.Call) and getattr(call.func, "id", "") in DECLARATION_CLASSES and call.args:
            value = reading.node_value(module, call.args[0])
            if isinstance(value, str) and ID.match(value):
                given = next((keyword.value for keyword in call.keywords if keyword.arg == "provenance"), None)
                tag = reading.node_value(module, given) if given is not None else class_default(module, call.func.id, "provenance")
                found.append({"id": value, "provenance": tag, "class": call.func.id})
    return found


def call_ids(reading, module, name):
    """The identifiers a registry such as CHANNEL_LAWS declares, in its order."""
    return [entry["id"] for entry in declarations(reading, module, name)]


def inner_model(reading):
    """What @3 declares at this revision: its registries in models/inner_laws.py where that file is, else its closed table."""
    rows = []
    inner = "src/cells/models/inner_laws.py"
    spec = "src/cells/core/surface_pump_v3_spec.py"
    module = reading.module(inner)
    if module is not None:
        for label, name in (("Channel laws", "CHANNEL_LAWS"), ("Junction law", "JUNCTION_LAWS"), ("Pumps", "PUMP_LAWS")):
            found = declarations(reading, module, name)
            rows.append({"label": label, "pieces": [entry["id"] for entry in found], "read": {"path": inner, "name": name},
                         "provenance": {entry["id"]: entry["provenance"] for entry in found if entry["provenance"]}})
        routes = call_ids(reading, module, "ROUTE_LAWS") or [value for value in (reading.value(inner, "MEMBRANE_ROUTE_LAW_ID"), reading.value(inner, "FACE_ROUTE_LAW_ID")) if value]
        rows.append({"label": "Routes", "pieces": routes, "read": {"path": inner, "name": "ROUTE_LAWS" if "ROUTE_LAWS" in module.env else "MEMBRANE_ROUTE_LAW_ID, FACE_ROUTE_LAW_ID"}})
        fuel = reading.value(inner, "MAINTAINED_FUEL_ID")
        rows.append({"label": "Fuel", "pieces": [fuel] if fuel else [], "read": {"path": inner, "name": "MAINTAINED_FUEL_ID"}})
    else:
        codes = reading.value(spec, "LAW_CODES")
        if isinstance(codes, dict):
            rows.append({"label": "Channel laws", "pieces": sorted(codes, key=codes.get), "read": {"path": spec, "name": "LAW_CODES"}})
    heat = reading.value(spec, "TRAPEZOID_JUNCTION_HEAT")
    if heat:
        rows.append({"label": "Heat booking", "pieces": [heat], "read": {"path": spec, "name": "TRAPEZOID_JUNCTION_HEAT"}})
    kinds = sorted(identifier for identifier, _ in inner_kinds(reading))
    if kinds:
        rows.append({"label": "Kinds", "pieces": kinds, "read": {"path": "src/cells/models/inner_kinds/", "name": "KIND_ID"}})
    solvers = reading.value("src/cells/core/surface_pump_spec.py", "SOLVERS")
    if solvers:
        rows.append({"label": "Solvers", "pieces": list(solvers), "read": {"path": "src/cells/core/surface_pump_spec.py", "name": "SOLVERS"}})
    # The inner model's own registry codes (not the older families' catalogue codes), and the next free one.
    codes = reading.value(spec, "LAW_CODES")
    if rows and rows[0]["label"] == "Channel laws" and isinstance(codes, dict):
        rows[0]["codes"] = {law: codes[law] for law in rows[0]["pieces"] if law in codes}
        rows[0]["codes_read"] = {"path": spec, "name": "LAW_CODES"}
        rows[0]["next_code"] = max(codes.values()) + 1
    return {"id": reading.value(spec, "MODEL_ID"), "rows": [row for row in rows if row["pieces"]]}


def inner_kinds(reading):
    """Each built-in kind of models/inner_kinds/ with its own pieces: what it imports from processes/, and its own identifiers."""
    out = []
    for relative in sorted(reading.package.files):
        if not relative.startswith("src/cells/models/inner_kinds/") or relative.endswith("__init__.py"):
            continue
        module = reading.module(relative)
        kind = reading.value(relative, "KIND_ID")
        if not isinstance(kind, str):
            continue
        pieces = []
        for local, target in module.imports.items():
            if target[0] == "name" and target[1] == "cells.processes":
                other = reading.package.module(f"cells.processes.{target[2]}")
                for name in ("LAW_ID", "READ_ID"):
                    if other is not None and name in other.env:
                        value = reading.node_value(other, ast.Name(id=name))
                        if isinstance(value, str) and ID.match(value):
                            pieces.append(value)
        for name, node in module.env.items():
            if name == "KIND_ID":
                continue
            value = reading.node_value(module, node) if isinstance(node, (ast.Constant, ast.Name, ast.Attribute)) else None
            values = value if isinstance(value, list) else [value]
            pieces += [item for item in values if isinstance(item, str) and ID.match(item) and not item.startswith("cells.")]
        out.append((kind, {"path": relative, "pieces": sorted(set(pieces))}))
    return out


def model_ids(reading):
    """Every module-level MODEL_ID literal: the model families."""
    found = {}
    for relative in sorted(reading.package.files):
        module = reading.module(relative)
        node = module.env.get("MODEL_ID")
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and ID.match(node.value):
            found.setdefault(node.value, relative)
    return found


def read_all(reading):
    return {
        "catalogue": catalogue(reading),
        "constants": constants(reading),
        "operators": operators(reading),
        "inner": inner_model(reading),
        "kinds": inner_kinds(reading),
        "models": model_ids(reading),
        "metabolism": reading.value("src/cells/core/kinetic_finite_spec.py", "METABOLISM_ID"),
    }


# ---------------------------------------------------------------- the viewer's own records: statuses and boxes


def glob_regex(pattern):
    """A path glob where * stays inside one directory and ** crosses directories (the map's extractor's rule)."""
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
    return re.compile("^" + "".join(out) + "$")


class Records:
    """The Engine view's records: its boxes (overlay components, matched to files), its operators' and models' statuses."""

    def __init__(self, architecture_overlay, scene):
        self.levels = {status["id"]: status["label"] for status in architecture_overlay["statuses"]}
        self.components = [(component, [glob_regex(pattern) for pattern in component.get("match", [])]) for component in architecture_overlay["components"] if component.get("match")]
        self.entities = {entity["id"]: entity for entity in scene["entities"]}
        self.operator_labels = {law: item.get("label") for law, item in architecture_overlay["operators"]["items"].items()}
        self.scene_revision = scene.get("meta", {}).get("revision")

    @staticmethod
    def source_of(sources):
        """The first source with a place in it, else the first; as the record gives it."""
        chosen = next((source for source in sources or [] if source.get("where")), (sources or [None])[0])
        return {key: chosen[key] for key in ("path", "where") if chosen.get(key)} if chosen else None

    def status(self, entity_id):
        entity = self.entities.get(entity_id)
        if not entity or not entity.get("status") or entity["status"] not in self.levels:
            return None
        source = self.source_of(entity.get("sources"))
        if not source:
            return None  # a status with no source is not carried
        return {"level": entity["status"], "label": self.levels[entity["status"]], "as_of": entity.get("as_of"), "source": source, "record": f"data/architecture/architecture.scene.json: {entity_id}"}

    def box(self, path):
        """The Engine view's box that holds a file: the first that matches, the catch-all last."""
        if not path:
            return None
        hit = None
        for component, patterns in self.components:
            if any(pattern.match(path) for pattern in patterns):
                if component.get("catch_all"):
                    hit = hit or component
                else:
                    hit = component
                    break
        if not hit or hit.get("catch_all") or hit.get("status") not in self.levels:
            return None
        source = self.source_of(hit.get("sources"))
        if not source:
            return None
        return {"id": hit["id"], "label": hit["label"], "level": hit["status"], "level_label": self.levels[hit["status"]], "as_of": hit.get("as_of"), "source": source}


# ---------------------------------------------------------------- the list


class Build:
    def __init__(self, main, candidate, overlay, records, inventory):
        self.main, self.candidate, self.overlay, self.records = main, candidate, overlay, records
        self.inventory = inventory
        self.units = {unit["id"]: unit for unit in inventory["units"]}
        self.inventory_laws = {law["id"]: law for law in inventory["laws"] if "id" in law}
        self.families = {family["id"]: family for family in overlay["families"]}
        self.warnings = []
        self.pieces = {}

    def family_of(self, identifier, kind, read_fields):
        if identifier in self.overlay["family_of"]:
            return self.overlay["family_of"][identifier], "family_of"
        if kind == "operator":
            return "operators", "kind"
        if kind == "kind":
            return "kinds", "kind"
        if kind == "solver":
            return "solvers", "kind"
        if kind == "fuel kind":
            return "fuel", "kind"
        unit = self.units.get(self.inventory_laws.get(identifier, {}).get("unit"))
        if unit and unit["kind"] in self.overlay["unit_kind_family"]:
            return self.overlay["unit_kind_family"][unit["kind"]], "unit kind"
        if kind == "channel law":
            ions = [row[0] for row in read_fields.get("permeant") or []]
            return ({"Na": "sodium", "K": "potassium", "Ca": "calcium"}.get(ions[0], "leak") if len(ions) == 1 else "hcn"), "permeant ions"
        return "other", "rule"

    def add(self, identifier, kind, where, read, source_reading):
        if identifier in self.pieces:
            return self.pieces[identifier]
        piece = {"id": identifier, "kind": kind, "where": where}
        fields = dict(read.get("fields") or {})
        path = read.get("path")
        if path and source_reading is not None:
            doc = source_reading.doc(path)
            if doc:
                fields["doc"] = doc
        piece["read"] = {"ref": source_reading.ref, "revision": source_reading.revision, "path": path, "found_by": read["found_by"], "fields": fields}
        if read.get("also"):
            piece["read"]["also"] = read["also"]
        family, why = self.family_of(identifier, kind, fields)
        curated = {"family": family, "family_by": why}
        law = self.inventory_laws.get(identifier)
        if law and self.units.get(law.get("unit")):
            curated["unit"] = self.units[law["unit"]]["name"]
            curated["unit_by"] = f"the protein inventory of {self.inventory['inventory']['created']} (engine {self.inventory['inventory']['read_at_revision']})"
        if kind == "operator" and self.records.operator_labels.get(identifier):
            curated["label"] = self.records.operator_labels[identifier]
        piece["family"] = family
        piece["curated"] = curated
        status = self.records.status(f"op.{identifier}") if kind == "operator" else None
        piece["status"] = status
        box = self.records.box(path) if where == "main" and kind != "operator" else None
        if box:
            piece["box"] = box
        self.pieces[identifier] = piece
        return piece

    def gather(self, data, reading, where):
        """Add every piece the code holds at a reading, in a fixed order."""
        for law, entry in sorted(data["catalogue"].items(), key=lambda item: (min(item[1]["codes"]), item[0])):
            if len(entry["codes"]) > 1:
                self.warnings.append(f"{law}: more than one registry code {sorted(entry['codes'])}")
            fields = {"code": min(entry["codes"]), **entry["fields"]}
            # The law's own module where the inventory names one whose table lists it; else the first
            # table whose module holds the id as written; else the first table that lists it.
            own = self.inventory_laws.get(law, {}).get("file")
            holds = set(reading.holds(law))
            path = own if own in entry["tables"] else next((table for table in entry["tables"] if table in holds), entry["tables"][0])
            self.add(law, "channel law", where, {"path": path, "found_by": "LAW_CODES table", "fields": fields, "also": entry["tables"][:6]}, reading)
        for operator in data["operators"]:
            self.add(operator["id"], "operator", where, {"path": operator["path"], "found_by": "OPERATORS registry", "fields": operator["fields"]}, reading)
        for kind, entry in data["kinds"]:
            self.add(kind, "kind", where, {"path": entry["path"], "found_by": "KIND_ID", "fields": {"pieces": entry["pieces"]}}, reading)
        for identifier, places in sorted(data["constants"].items()):
            first = places[0]
            kind = {"law": "law", "read": "read", "route kind": "route kind", "solver": "solver"}[first["kind"]]
            self.add(identifier, kind, where, {"path": first["path"], "found_by": f"{first['name']} constant", "fields": {}, "also": [place["path"] for place in places[1:6]]}, reading)
        for kind, entry in data["kinds"]:
            for identifier in entry["pieces"]:
                if identifier not in self.pieces:
                    holds = reading.holds(identifier)
                    kind_name = "fuel kind" if identifier in ("maintained_held_rows@1", "finite_fuel_rows@1") else "law"
                    self.add(identifier, kind_name, where, {"path": holds[0] if holds else entry["path"], "found_by": f"a piece of {kind}", "fields": {}}, reading)
        for row in data["inner"]["rows"]:
            for identifier in row["pieces"]:
                if identifier not in self.pieces:
                    holds = reading.holds(identifier)
                    kind = "solver" if row["label"] in ("Solvers", "Heat booking") else "fuel kind" if row["label"] == "Fuel" else "law"
                    self.add(identifier, kind, where, {"path": holds[0] if holds else row["read"]["path"], "found_by": f"{row['read']['name']} of the inner model", "fields": {}}, reading)
        if data["metabolism"] and data["metabolism"] not in self.pieces:
            self.add(data["metabolism"], "fuel kind", where, {"path": "src/cells/core/kinetic_finite_spec.py", "found_by": "METABOLISM_ID constant", "fields": {}}, reading)
        # The protein inventory's laws that no rule above found, each held to the code: its identifier must stand in it.
        for identifier, law in sorted(self.inventory_laws.items()):
            if identifier in self.pieces or identifier in data["models"]:
                continue
            holds = reading.holds(identifier)
            if not holds:
                continue
            path = law.get("file") if law.get("file") in holds else holds[0]
            self.add(identifier, "law", where, {"path": path, "found_by": "the protein inventory's record, found in the code", "fields": {}}, reading)
        # Each operator's step method, which the lead counts as a piece; last, so that a law found
        # by another rule (a junction's formation law that an operator also names as its step) stays a law.
        for operator in data["operators"]:
            step = operator["fields"].get("step_method")
            if isinstance(step, str) and ID.match(step) and step not in self.pieces:
                self.add(step, "solver", where, {"path": operator["path"], "found_by": f"STEP_ID of {operator['id']}", "fields": {}}, reading)

    def kinds_named(self):
        """Name each piece's kind in the contract's words, now that every piece is in."""
        names = {"channel law": "channel law", "operator": "operator", "kind": "kind", "solver": "solver", "fuel kind": "fuel kind", "read": "read", "route kind": "route kind"}
        for piece in self.pieces.values():
            if piece["kind"] in names:
                continue
            family = piece["family"]
            piece["kind"] = {"routes": "route law", "junctions": "junction law", "pumps": "pump law", "release": "release law", "factors": "factor", "fuel": "fuel kind", "solvers": "solver"}.get(family, "law" if family != "leak" else "channel law")

    def designed(self):
        for entry in self.overlay["designed"]:
            if entry["id"] in self.pieces:
                self.warnings.append(f"{entry['id']} is named as designed, and the code holds it: take it out of the overlay")
                continue
            self.pieces[entry["id"]] = {
                "id": entry["id"], "kind": entry["kind"], "where": "design", "family": entry["family"], "read": None,
                "curated": {"family": entry["family"], "family_by": "designed", "named_in": entry["named_in"]}, "status": None,
            }


REGISTRIES = {
    "Channel laws": "inner_laws.py", "Junction law": "inner_laws.py", "Pumps": "inner_laws.py", "Routes": "inner_laws.py", "Fuel": "inner_laws.py",
    "Heat booking": "the inner model's structure", "Kinds": "the kind registry", "Solvers": "a solver or step method",
}
REGISTRY_ORDER = ["inner_laws.py", "the kind registry", "a registered kind", "OPERATORS", "a registered operator", "the inner model's structure", "a solver or step method", "an older family", "no registry", None]


def registries(build, all_frames, kinds, reading, operators_read):
    """Where each piece stands registered (schema/LAWS_LIBRARY.md, "What counts as a piece": the lead's provisional answers)."""
    inner = next((frame for frame in all_frames if frame["kind"] == "inner model"), None)
    named = {}
    for row in inner["rows"] if inner else []:
        for identifier in row["pieces"]:
            named.setdefault(identifier, {"registry": REGISTRIES.get(row["label"], "an older family"), "path": row["read"]["path"], "name": row["read"]["name"], "provenance": (row.get("provenance") or {}).get(identifier)})
    own = {identifier: kind for kind, entry in kinds for identifier in entry["pieces"]}
    for piece in build.pieces.values():
        if piece["where"] == "design":
            piece["registry"] = None
            continue
        entry = named.get(piece["id"])
        if entry:
            piece["registry"] = entry["registry"]
            piece["registered_in"] = {key: entry[key] for key in ("path", "name") if entry[key]}
            if entry["provenance"]:
                piece["read"]["fields"]["provenance"] = entry["provenance"]
        elif piece["id"] in own:
            piece["registry"] = "a registered kind"
            piece["registered_in"] = {"kind": own[piece["id"]]}
        elif piece["kind"] == "operator":
            piece["registry"] = "OPERATORS"
        elif piece["kind"] == "solver":
            piece["registry"] = "a solver or step method"
        elif piece["read"]["found_by"] == "LAW_CODES table":
            piece["registry"] = "an older family"  # the older families' channel catalogue (D167)
        else:
            # A named law in no registry, unless a registered operator's own module names it.
            holder = next((operator["id"] for operator in operators_read for path in reading.holds(piece["id"]) if path == operator["path"]), None)
            piece["registry"] = "a registered operator" if holder else "no registry"
            if holder:
                piece["registered_in"] = {"operator": holder}
        if "@" not in piece["id"]:
            piece["read"]["fields"]["unversioned"] = True


def frames(build, main_data, candidate_data, main, candidate):
    """The models and what each declares: the inner model, the composite, the compositions, and the older families."""
    overlay = build.overlay["frames"]
    records = build.records
    out = []

    def boxes(ids):
        found = [{"id": entity_id, "name": records.entities[entity_id]["label"], **records.status(entity_id)} for entity_id in ids if records.status(entity_id)]
        return found

    # The inner model: from main where main holds its declarations, else from the candidate, with main's closed table beside it.
    inner_main = main_data["inner"]
    has_main_declarations = main.module("src/cells/models/inner_laws.py") is not None
    source = inner_main if has_main_declarations or candidate_data is None else candidate_data["inner"]
    reading = main if source is inner_main else candidate
    rows = [{**row, "read": {**row["read"], "ref": reading.ref, "revision": reading.revision}} for row in source["rows"]]
    if source is not inner_main:
        closed = next((row for row in inner_main["rows"] if row["label"] == "Channel laws"), None)
        if closed:
            for row in rows:
                if row["label"] == "Channel laws":
                    row["closed_on_main"] = {"path": closed["read"]["path"], "name": closed["read"]["name"], "pieces": closed["pieces"], "ref": main.ref, "revision": main.revision}
    identity = inner_main["id"]
    words = overlay.get(identity, {})
    out.append({"id": identity, "kind": "inner model", "label": words.get("label"), "short": words.get("short"), "plain": words.get("plain"),
                "read": {"ref": main.ref, "revision": main.revision, "path": "src/cells/core/surface_pump_v3_spec.py", "found_by": "MODEL_ID"},
                "rows": rows, "boxes": boxes(words.get("box", []))})
    composite_id = main.value("src/cells/core/pump_composite_spec.py", "MODEL_ID")
    words = overlay.get(composite_id, {})
    out.append({"id": composite_id, "kind": "composite", "label": words.get("label"), "short": words.get("short"), "plain": words.get("plain"), "inner": identity,
                "read": {"ref": main.ref, "revision": main.revision, "path": "src/cells/core/pump_composite_spec.py", "found_by": "MODEL_ID"},
                "development_status": main.value("src/cells/core/pump_composite_spec.py", "DEVELOPMENT_STATUS"),
                "rows": [{"label": "Operators, in a definition's order", "pieces": [operator["id"] for operator in main_data["operators"]], "read": {"path": "src/cells/models/operators/__init__.py", "name": "OPERATORS", "ref": main.ref, "revision": main.revision}, "any_order": True}],
                "boxes": boxes(words.get("box", []))})
    for composition in overlay["compositions"]:
        holds = main.holds(composition["id"])
        if "src/cells/core/pump_composite_spec.py" not in holds:
            build.warnings.append(f"{composition['id']}: not named in pump_composite_spec.py at {main.revision}; left out")
            continue
        out.append({"id": composition["id"], "kind": "composition", "short": composition["short"], "inner": composition["inner"],
                    "read": {"ref": main.ref, "revision": main.revision, "path": "src/cells/core/pump_composite_spec.py", "found_by": "named in frozen_definition"},
                    "rows": [{"label": "Operators", "pieces": composition["operators"], "curated": {"blocks": composition["blocks"], "source": overlay["compositions_source"]}}],
                    "boxes": boxes(composition.get("box", []))})
    shown = {frame["id"] for frame in out}
    for identifier, path in sorted(main_data["models"].items()):
        if identifier in shown:
            continue
        out.append({"id": identifier, "kind": "older family", "read": {"ref": main.ref, "revision": main.revision, "path": path, "found_by": "MODEL_ID"}, "rows": []})
    return out


def declare(build, all_frames, kinds):
    """Who declares each piece: a frame's row names it, or it is a kind's piece and the frame names the kind, or the frame holds the inner model."""
    kind_of = {identifier: kind for kind, entry in kinds for identifier in entry["pieces"]}
    by_frame = {frame["id"]: frame for frame in all_frames}
    for piece in build.pieces.values():
        piece["declared_by"] = []
    for frame in all_frames:
        names = {identifier for row in frame["rows"] for identifier in row["pieces"]}
        inner = by_frame.get(frame.get("inner"))
        inner_names = {identifier for row in (inner["rows"] if inner else []) for identifier in row["pieces"]}
        for piece in build.pieces.values():
            identifier = piece["id"]
            if identifier in names:
                piece["declared_by"].append({"frame": frame["id"], "how": "direct"})
            elif kind_of.get(identifier) in names:
                piece["declared_by"].append({"frame": frame["id"], "how": "kind", "via": kind_of[identifier]})
            elif identifier in inner_names or kind_of.get(identifier) in inner_names:
                piece["declared_by"].append({"frame": frame["id"], "how": "inner", "via": frame["inner"]})
    for frame in all_frames:
        for row in frame["rows"]:
            for identifier in row["pieces"]:
                if identifier not in build.pieces:
                    build.warnings.append(f"frame {frame['id']} names {identifier}, which no rule found")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", help="the Cells checkout to read (default: the main checkout)")
    parser.add_argument("--ref", default="main", help="the revision whose pieces stand on main (default: main)")
    parser.add_argument("--candidate", help="a branch whose pieces are not on main yet (the landing candidate)")
    parser.add_argument("--overlay", default=str(HERE.parent / "data" / "laws" / "overlay.json"))
    parser.add_argument("--architecture", default=str(HERE.parent / "data" / "architecture" / "overlay.json"))
    parser.add_argument("--scene", default=str(HERE.parent / "data" / "architecture" / "architecture.scene.json"))
    parser.add_argument("--inventory", default=str(HERE.parent / "data" / "proteins" / "inventory.snapshot.json"))
    parser.add_argument("--out", default=str(HERE.parent / "data" / "laws" / "pieces.json"), help="where to write it; - for standard output")
    parser.add_argument("--strict", action="store_true", help="exit with an error if anything is warned about")
    arguments = parser.parse_args()

    repo = Path(arguments.repo).resolve() if arguments.repo else find_repo()
    load = lambda path: json.loads(Path(path).read_text(encoding="utf-8"))
    overlay, records = load(arguments.overlay), Records(load(arguments.architecture), load(arguments.scene))
    main_reading = Reading(repo, arguments.ref)
    candidate_reading = Reading(repo, arguments.candidate) if arguments.candidate else None
    warnings = []
    remote = main_reading.on_remote()
    if remote is False:
        warnings.append(f"{arguments.ref} stands at {main_reading.revision}, which is on no remote branch as last fetched: the list would state a revision that others cannot find (read it again once that revision is pushed)")
    landed = False
    if candidate_reading is not None:
        landed = subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", candidate_reading.revision, main_reading.revision]).returncode == 0
        if landed:
            warnings.append(f"{arguments.candidate} ({candidate_reading.revision}) has landed on {arguments.ref}: it adds nothing, and the list is read from {arguments.ref} alone")
            candidate_reading = None
    main_data = read_all(main_reading)
    candidate_data = read_all(candidate_reading) if candidate_reading else None
    build = Build(main_reading, candidate_reading, overlay, records, load(arguments.inventory))
    build.gather(main_data, main_reading, "main")
    if candidate_data:
        build.gather(candidate_data, candidate_reading, "candidate")
    build.kinds_named()
    build.designed()
    all_frames = frames(build, main_data, candidate_data, main_reading, candidate_reading)
    kinds = main_data["kinds"] + (candidate_data["kinds"] if candidate_data else [])
    declare(build, all_frames, kinds)
    registries(build, all_frames, kinds, main_reading, main_data["operators"])
    # In the code and not registered: not pieces yet (the lead's provisional answer). Kept apart, never counted.
    unregistered = []
    for entry in overlay.get("not_registered", []):
        piece = build.pieces.pop(entry["id"], None)
        if piece is None:
            warnings.append(f"{entry['id']} is named as not registered, and no rule found it in the code")
            continue
        unregistered.append({"id": entry["id"], "read": piece["read"], "words": entry["words"], "by": entry["by"]})
    warnings += main_reading.warnings + (candidate_reading.warnings if candidate_reading else []) + build.warnings
    for piece in build.pieces.values():
        if any(word in piece["id"] for word in overlay["references"]):
            warnings.append(f"{piece['id']}: named after a reference simulator; left out")
    references = overlay["references"]
    pieces = [piece for piece in build.pieces.values() if not any(word in piece["id"] for word in references)]
    order = {family["id"]: index for index, family in enumerate(overlay["families"])}
    rank = {"main": 0, "candidate": 1, "design": 2}
    # In a family: what is registered, then what stands in an older family; then by where it stands, code and id.
    older = lambda piece: piece.get("registry") in ("an older family", "no registry")  # drawn apart, above the registered
    pieces.sort(key=lambda piece: (order[piece["family"]], older(piece), rank[piece["where"]], (piece.get("read") or {}).get("fields", {}).get("code", 10**6), piece["id"]))
    counts = {
        "pieces": len(pieces),
        "by_where": dict(Counter(piece["where"] for piece in pieces)),
        "by_family": {family["id"]: sum(piece["family"] == family["id"] for piece in pieces) for family in overlay["families"]},
        "frames": dict(Counter(frame["kind"] for frame in all_frames)),
        "by_registry": {name: sum(piece.get("registry") == name for piece in pieces) for name in REGISTRY_ORDER if name},
        "unregistered": len(unregistered),
    }
    stamp = {
        "generator": "visualizer/tools/extract_laws.py",
        "main": {"ref": arguments.ref, "revision": main_reading.revision, "date": main_reading.date, "on_remote": remote},
        "candidate": {"ref": arguments.candidate, "revision": candidate_reading.revision, "date": candidate_reading.date, "on_remote": candidate_reading.on_remote(), "words": "the landing candidate, not on main yet"} if candidate_reading else None,
        "landed": {"ref": arguments.candidate} if landed else None,
        "records": {"scene_revision": records.scene_revision, "inventory": f"{build.inventory['inventory']['created']} (engine {build.inventory['inventory']['read_at_revision']})"},
        "overlay_as_of": overlay["as_of"],
        "what_counts": overlay["what_counts"],
        "warnings": warnings,
    }
    out = {
        "format": FORMAT,
        "stamp": stamp,
        "families": overlay["families"],
        "shelves": overlay["shelves"],
        "counts": counts,
        "pieces": pieces,
        "unregistered": unregistered,
        "frames": all_frames,
        "older_words": overlay["frames"]["older"],
    }
    text = json.dumps(out, indent=1, ensure_ascii=False) + "\n"
    if arguments.out == "-":
        sys.stdout.write(text)
    else:
        target = Path(arguments.out)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        print(f"read {arguments.ref} at {main_reading.revision}" + (f", and {arguments.candidate} at {candidate_reading.revision}" if candidate_reading else ""), file=sys.stderr)
        print(f"{counts['pieces']} pieces: {counts['by_where']}; frames {counts['frames']}", file=sys.stderr)
    for warning in warnings:
        print("warning:", warning, file=sys.stderr)
    if arguments.strict and warnings:
        raise SystemExit(1)


def find_repo():
    """The main checkout: the nearest tree that holds src/cells, as the map's extractor finds it."""
    candidates = [HERE.parent.parent]
    common = git(HERE, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
    if common:
        candidates.append(Path(common).parent)
    for candidate in candidates:
        if (candidate / "src" / "cells").is_dir():
            return candidate.resolve()
    raise SystemExit("No checkout with src/cells found; pass --repo.")


if __name__ == "__main__":
    main()
