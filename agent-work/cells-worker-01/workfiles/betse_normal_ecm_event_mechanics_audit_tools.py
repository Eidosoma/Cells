"""Read-only AST, import closure and byte-hash helpers; no scientific imports."""

import ast
import builtins
import hashlib
import json
import symtable
import sys
from pathlib import Path

ROOT = Path("/home/robert/Cells")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def signature(node):
    return ast.dump(node, include_attributes=False)


def functions(path):
    return {
        n.name: n for n in ast.parse(Path(path).read_text()).body if isinstance(n, ast.FunctionDef)
    }


def closure(start, *, reference=False):
    pending, closed = [start], {}
    while pending:
        relative = pending.pop()
        if relative in closed:
            continue
        path = ROOT / relative
        tree = ast.parse(path.read_text())
        compile(tree, relative, "exec")
        closed[relative] = sha(path)
        for parent in path.parents:
            if parent in (ROOT, ROOT / "src") or ROOT not in parent.parents:
                break
            if (parent / "__init__.py").is_file():
                pending.append(str((parent / "__init__.py").relative_to(ROOT)))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [item.name for item in node.names]
            elif isinstance(node, ast.ImportFrom):
                assert not node.level, (relative, "unresolved relative import")
                names = [node.module] + [node.module + "." + item.name for item in node.names]
            else:
                continue
            for name in names:
                head = name.split(".")[0]
                if reference:
                    assert head in sys.stdlib_module_names | {"validation"}, (relative, name)
                if head not in {"cells", "validation", "tests"}:
                    continue
                for base in (ROOT, ROOT / "src"):
                    for candidate in (
                        base / (name.replace(".", "/") + ".py"),
                        base / name.replace(".", "/") / "__init__.py",
                    ):
                        if candidate.is_file():
                            pending.append(str(candidate.relative_to(ROOT)))
    return closed


def compile_names(paths):
    for relative in paths:
        code = (ROOT / relative).read_text()
        compile(code, relative, "exec")
        table = symtable.symtable(code, relative, "exec")
        known = set(table.get_identifiers()) | set(dir(builtins)) | {"__file__", "__name__"}

        def unresolved(scope, known=known):
            missing = {
                s.get_name()
                for s in scope.get_symbols()
                if s.is_global() and s.is_referenced() and s.get_name() not in known
            }
            for child in scope.get_children():
                missing |= unresolved(child)
            return missing

        assert not unresolved(table), (relative, sorted(unresolved(table)))


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
