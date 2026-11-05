"""Project an exact INIT dependency plan without importing or editing its producers.

The caller supplies authenticated source bytes and review hashes. Projection
does not authenticate those reviews, adopt a provider, or release execution.
Existing source_snapshot tools remain responsible for immutable input capture.
"""

import ast
import hashlib
import json
import re
from pathlib import PurePosixPath


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _tree(raw):
    if type(raw) is not bytes or len(raw) > 2**21:
        raise ValueError("Bounded exact source bytes required")
    return ast.parse(raw)


def node_at(raw, slot):
    values = [
        node.value
        for node in _tree(raw).body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == slot[0]
    ]
    if len(values) != 1:
        raise ValueError("One declared top-level assignment required: " + str(slot))
    node = values[0]
    for key in slot[1:]:
        if type(key) is int and isinstance(node, (ast.Tuple, ast.List)):
            node = node.elts[key]
        elif isinstance(node, ast.Dict):
            matches = [
                v
                for k, v in zip(node.keys, node.values, strict=True)
                if k is not None and ast.literal_eval(k) == key
            ]
            if len(matches) != 1:
                raise ValueError("One declared mapping member required")
            node = matches[0]
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "dict"
            and not node.args
        ):
            matches = [kw.value for kw in node.keywords if kw.arg == key]
            if len(matches) != 1:
                raise ValueError("One declared dict keyword required")
            node = matches[0]
        else:
            raise ValueError("Unsupported declaration path: " + str(slot))
    return node


def _span(raw, node):
    lines = raw.splitlines(keepends=True)
    return (
        sum(map(len, lines[: node.lineno - 1])) + node.col_offset,
        sum(map(len, lines[: node.end_lineno - 1])) + node.end_col_offset,
    )


def byte_template(raw, *, slots, kind):
    """Preserve every byte except the separately checked canonical pin literals."""
    if (
        type(slots) is not tuple
        or not slots
        or len(set(slots)) != len(slots)
        or any(type(n) is not str for n in slots)
        or type(kind) is not str
    ):
        raise ValueError("Exact template slot roster and kind required")
    tree, spans = _tree(raw), []
    for name in slots:
        writes = [
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and n.id == name
        ]
        node = node_at(raw, (name,))
        if len(writes) != 1 or not isinstance(node, ast.Constant) or node.lineno != node.end_lineno:
            raise ValueError("One canonical literal back-reference required")
        value = node.value
        if value is not None and (
            type(value) is not str or re.fullmatch("[0-9a-f]{64}", value) is None
        ):
            raise ValueError("None or exact SHA256 back-reference required")
        start, end = _span(raw, node)
        allowed = (
            (b"None",) if value is None else (repr(value).encode(), json.dumps(value).encode())
        )
        if raw[start:end] not in allowed:
            raise ValueError("Plain canonical back-reference literal required")
        spans.append((start, end))
    normalized, cursor = [], 0
    for start, end in sorted(spans):
        normalized.extend((raw[cursor:start], b"None"))
        cursor = end
    normalized.append(raw[cursor:])
    return digest(kind.encode() + b"\0" + b"".join(normalized))


def _selector(text):
    match = re.fullmatch(r"(\w+)(?:\[(\w+)\])?", text)
    if match is None:
        raise ValueError("Declared simple source selector required")
    return tuple(part for part in match.groups() if part is not None)


def project(plan, sources, reviews, *, preserve=(), review_documents=None):
    """Return candidate bytes and a reversible report; perform no file writes."""
    aliases, recipes, requirements = (
        plan["module_aliases"],
        plan["recipes"],
        plan["required_assignments"],
    )
    if len(set(aliases.values())) != len(aliases) or set(sources) != set(aliases.values()):
        raise ValueError("Exact unique planned source roster required")
    before = dict(sources)
    for raw in before.values():
        _tree(raw)
    if any(
        type(name) is not str or re.fullmatch(r"R_[A-Za-z_]\w*", name) is None for name in reviews
    ):
        raise ValueError("Review names must use the R_ namespace, never dependency expressions")
    if any(
        type(value) is not str or re.fullmatch("[0-9a-f]{64}", value) is None
        for value in reviews.values()
    ):
        raise ValueError("Exact review hashes required; review acceptance is external")
    documents = {} if review_documents is None else review_documents
    if type(documents) is not dict:
        raise ValueError("Exact declared review document mapping required")
    for name, row in documents.items():
        if (
            type(name) is not str
            or name not in reviews
            or type(row) is not dict
            or set(row) != {"path", "sha256"}
            or type(row["sha256"]) is not str
            or row["sha256"] != reviews[name]
        ):
            raise ValueError("Review document must bind its declared review hash")
        path = row["path"]
        if (
            type(path) is not str
            or not 1 < len(path) <= 4096
            or not path.startswith("/")
            or path.startswith("//")
            or any(ord(char) < 32 or ord(char) == 127 for char in path)
            or ".." in PurePosixPath(path).parts
            or str(PurePosixPath(path)) != path
        ):
            raise ValueError("Canonical absolute review document path required")
    documents = {name: dict(row) for name, row in documents.items()}
    order = plan["topological_order"]
    if (
        len(set(order)) != len(order)
        or set(order) != set(aliases) | set(recipes)
        or set(aliases) & set(recipes)
    ):
        raise ValueError("Complete unique dependency order required")
    working, operations, materializations = dict(before), [], []

    def replace(path, node, value, label):
        raw = working[path]
        start, end = _span(raw, node)
        old = raw[start:end]
        if old != value:
            working[path] = raw[:start] + value + raw[end:]
            operations.append(
                dict(path=path, label=label, start=start, before=old.decode(), after=value.decode())
            )

    for row in plan.get("required_declaration_splits", ()):
        path, slots = row["path"], row["slots"]
        matches = [
            n
            for n in _tree(working[path]).body
            if isinstance(n, ast.Assign)
            and [t.id for t in n.targets if isinstance(t, ast.Name)] == slots
        ]
        if (
            len(matches) != 1
            or len(matches[0].targets) != len(slots)
            or not isinstance(matches[0].value, ast.Constant)
        ):
            raise ValueError("Exact declared chained assignment required")
        value = ast.literal_eval(matches[0].value)
        replace(
            path,
            matches[0],
            "\n".join(name + " = " + repr(value) for name in slots).encode(),
            "split:" + ",".join(slots),
        )

    for alias, row in requirements.items():
        path = aliases[alias]
        if row.get("path", path) != path:
            raise ValueError("Assignment target differs from alias")
        for name in sorted({_selector(slot)[0] for slot in row["slots"]}):
            node = node_at(working[path], (name,))
            if not isinstance(node, ast.Call):
                continue
            if not (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "dict"
                and node.func.attr == "fromkeys"
                and len(node.args) == 1
                and isinstance(node.args[0], ast.Name)
                and not node.keywords
            ):
                raise ValueError("Only declared dict.fromkeys gates may be materialized")
            roster_name = node.args[0].id
            roster = ast.literal_eval(node_at(working[path], (roster_name,)))
            if type(roster) is not dict or any(
                type(k) is not str or type(v) is not str for k, v in roster.items()
            ):
                raise ValueError("Exact declared module roster required")
            materializations.append(
                dict(
                    path=path,
                    slot=name,
                    module_roster=roster_name,
                    exact_keys_in_order=list(roster),
                )
            )
            replace(
                path, node, repr(dict.fromkeys(roster)).encode(), "materialize_declared_map:" + name
            )

    full, interfaces = {}, {}

    def resolve(text):
        text = text.split(" [", 1)[0]
        if "=" in text:
            pairs = [part.strip().split("=", 1) for part in text.split(",")]
            if any(re.fullmatch("[a-z_]+", key) is None for key, _ in pairs) or len(
                {k for k, _ in pairs}
            ) != len(pairs):
                raise ValueError("Unique declared mapping names required")
            return {key: resolve(value) for key, value in pairs}
        if text in reviews:
            return reviews[text]
        match = re.fullmatch(r"([HTD])\((\w+)\)", text)
        if match:
            category, name = match.groups()
            if category == "D":
                if name not in documents:
                    raise ValueError("Missing declared review document: " + text)
                return dict(documents[name])
            values = full if category == "H" else interfaces
            if name not in values:
                raise ValueError("Unresolved or cyclic dependency: " + text)
            return values[name]
        if text.startswith(("H(", "T(", "D(", "R_")):
            raise ValueError("Unknown dependency or review: " + text)
        return text

    def fill(alias, excluded=()):
        path = aliases[alias]
        for slot, expression in requirements.get(alias, {}).get("slots", {}).items():
            parts = _selector(slot)
            if parts[0] in excluded:
                continue
            value = resolve(expression)
            node = node_at(working[path], parts)
            if not isinstance(node, (ast.Constant, ast.Dict)):
                raise ValueError("Only exact declared literal slots may change")
            if ast.literal_eval(node) != value:
                raw = (
                    json.dumps(value, indent=4).encode()
                    if type(value) is dict
                    else repr(value).encode()
                )
                replace(path, node, raw, slot)

    for name in order:
        if name in recipes:
            row = recipes[name]
            target = row["target"]
            alias = next(a for a, path in aliases.items() if path == target)
            fill(alias, row["excluded_slots"])
            interfaces[name] = byte_template(
                working[target], slots=tuple(row["excluded_slots"]), kind=row["binding_kind"]
            )
        else:
            fill(name)
            full[name] = digest(working[aliases[name]])

    for name, expected in full.items():
        if digest(working[aliases[name]]) != expected:
            raise ValueError("Dependency order changed an already sealed full image")
    for name, expected in interfaces.items():
        row = recipes[name]
        if (
            byte_template(
                working[row["target"]], slots=tuple(row["excluded_slots"]), kind=row["binding_kind"]
            )
            != expected
        ):
            raise ValueError("Dependency order changed an already sealed template")
    for alias, row in requirements.items():
        for slot, expression in row["slots"].items():
            if ast.literal_eval(node_at(working[aliases[alias]], _selector(slot))) != resolve(
                expression
            ):
                raise ValueError("Final source dependency mismatch")
    reverse = dict(working)
    for row in reversed(operations):
        path, start, new, old = (
            row["path"],
            row["start"],
            row["after"].encode(),
            row["before"].encode(),
        )
        if reverse[path][start : start + len(new)] != new:
            raise ValueError("Non-reversible literal operation")
        reverse[path] = reverse[path][:start] + old + reverse[path][start + len(new) :]
    if reverse != before:
        raise ValueError("Candidate does not reverse to the exact source image")
    kinds = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)

    def definitions(data):
        return [ast.dump(n) for n in _tree(data).body if isinstance(n, kinds)]

    for path, raw in working.items():
        if definitions(raw) != definitions(before[path]):
            raise ValueError("Source body or import changed")
        compile(raw, path, "exec", dont_inherit=True)
    for path, slot in preserve:
        if ast.dump(node_at(before[path], slot)) != ast.dump(node_at(working[path], slot)):
            raise ValueError("Explicit held or legacy slot changed")
    report = dict(
        full_hashes=full,
        normalized_interfaces=interfaces,
        literal_operations=operations,
        map_materializations=materializations,
        before_source_pins={p: digest(raw) for p, raw in before.items()},
        final_hashes={p: digest(raw) for p, raw in working.items()},
        changed_paths=[p for p in working if working[p] != before[p]],
        all_other_bytes_and_function_class_import_ASTs_exact=True,
        all_operations_reversible=True,
        source_files_written=False,
        actual_execution_released=False,
        reviews_authenticated_by_projection=False,
    )
    if documents:
        report["review_documents"] = documents
    return working, report
