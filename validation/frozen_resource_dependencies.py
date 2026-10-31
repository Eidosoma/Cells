"""Find literal sibling data reads without importing frozen scientific modules.

This is a preparation check, not a complete Python dependency resolver. Other
read expressions are reported for explicit review; output writes are excluded.
"""

import ast
import hashlib
from pathlib import Path, PurePosixPath

MAX_SOURCE_BYTES = 2 * 2**20
MAX_RESOURCE_BYTES = 64 * 2**20


def _path(root, relative):
    if not isinstance(relative, str):
        raise ValueError("Require a relative source/resource path")
    parts = PurePosixPath(relative)
    if (
        parts.is_absolute()
        or not parts.parts
        or any(p in ("", ".", "..") for p in relative.split("/"))
    ):
        raise ValueError("Require an explicit path inside the frozen source root")
    path = root.joinpath(*parts.parts)
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise ValueError("Frozen resource paths cannot contain symlinks")
        if parent == root:
            break
    return path


def _bytes(path, limit):
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Frozen dependency exceeds its preparation byte bound: " + str(path))
    return data


def _path_constructor(node, constructors):
    return (
        isinstance(node, ast.Call)
        and ast.unparse(node.func) in constructors
        and len(node.args) == 1
        and not node.keywords
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == "__file__"
    )


def _read_receiver(node):
    builtin = isinstance(node.func, ast.Name) and node.func.id == "open"
    if isinstance(node.func, ast.Attribute) and node.func.attr in ("read_text", "read_bytes"):
        return node.func.value
    if not builtin and not (isinstance(node.func, ast.Attribute) and node.func.attr == "open"):
        return None
    offset = 1 if builtin else 0
    mode = (
        node.args[offset]
        if len(node.args) > offset
        else next((k.value for k in node.keywords if k.arg == "mode"), ast.Constant("r"))
    )
    if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
        if any(flag in mode.value for flag in "wax"):
            return None
    if builtin:
        return node.args[0] if node.args else node.func
    return node.func.value


def audit_literal_sibling_reads(source_root, source_sha256):
    """Check pinned modules and bind present sibling resources; report unresolved reads.

    Supported: ``Path(__file__).with_name('literal').read_*()`` or ``.open()``
    with pathlib import aliases. Dynamic/other reads need a separate declared
    resource manifest or manual source review. No imported code is executed.
    """
    root = Path(source_root).absolute()
    required, unresolved, modules = [], [], []
    for relative, expected in sorted(source_sha256.items()):
        if not relative.endswith(".py"):
            continue
        path = _path(root, relative)
        raw = _bytes(path, MAX_SOURCE_BYTES)
        digest = hashlib.sha256(raw).hexdigest()
        if digest != expected:
            raise ValueError("Frozen source hash differs: " + relative)
        tree = ast.parse(raw, filename=relative)
        constructors = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == "pathlib":
                constructors.update(a.asname or a.name for a in node.names if a.name == "Path")
            elif isinstance(node, ast.Import):
                constructors.update(
                    (a.asname or a.name) + ".Path" for a in node.names if a.name == "pathlib"
                )
        modules.append(dict(path=relative, sha256=digest))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            receiver = _read_receiver(node)
            if receiver is None:
                continue
            row = dict(module=relative, line=node.lineno, expression=ast.unparse(node))
            if not (
                isinstance(receiver, ast.Call)
                and isinstance(receiver.func, ast.Attribute)
                and receiver.func.attr == "with_name"
                and _path_constructor(receiver.func.value, constructors)
                and len(receiver.args) == 1
                and not receiver.keywords
                and isinstance(receiver.args[0], ast.Constant)
                and isinstance(receiver.args[0].value, str)
            ):
                unresolved.append(row)
                continue
            name = receiver.args[0].value
            if not name or "/" in name or "\\" in name or name in (".", ".."):
                raise ValueError("Invalid literal sibling filename")
            resource = str(PurePosixPath(relative).with_name(name))
            target = _path(root, resource)
            present = target.is_file()
            content = _bytes(target, MAX_RESOURCE_BYTES) if present else None
            row.update(
                resource=resource,
                present=present,
                sha256=hashlib.sha256(content).hexdigest() if present else None,
            )
            required.append(row)
    return dict(
        kind="cells.literal_sibling_resource_audit@1",
        modules=modules,
        required_resources=required,
        missing_resources=sorted({r["resource"] for r in required if not r["present"]}),
        unresolved_reads=unresolved,
        complete_dependency_closure_claim=False,
        scientific_imports_or_evaluations=0,
    )
