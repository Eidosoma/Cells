"""Every way a tracked Python file can reach another tracked Python file, read from a commit (no
checkout, reads only).

Mechanisms: import (absolute package path, module or name), rel (relative import), bare (a bare
module name: the same folder, or every folder that holds such a file), importlib (import_module or
__import__ with a constant), path (a string constant, not a docstring, that names a .py file: full
path, the end of a tracked path, or a base name in with_name, / and subprocess arguments), dotted
(a string constant that is the dotted path of a tracked module). An edge is (target, mechanism,
line, lazy); lazy is true inside a function body. The graph over-approximates: a base name shared
by several files gives an edge to each. Docstrings are not edges. dyn lists the calls that build a
name or a path at run time (spec_from_file_location, run_path, import_module of a variable,
private, module_path).
"""

import ast
import collections
import pathlib
import re
import subprocess
import sys
import threading

ROOTS = (
    "cells",
    "validation",
    "tests",
    "scripts",
    "examples",
    "cells_modules",
    "lean",
    "visualizer",
)
SKIP = ()  # lean/ and visualizer/ are read too (the second reader, A1); they are never edited
STD = set(sys.stdlib_module_names)
THIRD = set(
    (
        "numpy scipy jax jaxlib pytest betse ruamel matplotlib h5py beartype networkx yaml optax "
        "psutil pandas sympy mpmath hypothesis PIL shapely diffrax equinox lineax optimistix numba "
        "pyarrow zarr typing_extensions setuptools pip pkg_resources dill six toposort "
    ).split()
)


def blobs(repo, rev, want=None):
    out = subprocess.run(
        ["git", "-C", repo, "ls-tree", "-r", rev], capture_output=True, text=True, check=True
    ).stdout.splitlines()
    ent = []
    for line in out:
        meta, path = line.split("\t", 1)
        mode, typ, sha = meta.split()
        if typ == "blob" and mode != "120000" and (want is None or want(path)):
            ent.append((path, sha))
    p = subprocess.Popen(
        ["git", "-C", repo, "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE
    )

    def feed():
        for _, s in ent:
            p.stdin.write((s + "\n").encode())
        p.stdin.close()

    threading.Thread(target=feed, daemon=True).start()
    res = {}
    for path, _s in ent:
        n = int(p.stdout.readline().split()[2])
        res[path] = p.stdout.read(n)
        p.stdout.read(1)
    p.wait()
    return res


def modname(rel):
    parts = list(pathlib.PurePosixPath(rel).with_suffix("").parts)
    if parts[0] == "src":
        parts = parts[1:]
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


class Tree:
    def __init__(self, repo, rev):
        names = subprocess.run(
            ["git", "-C", repo, "ls-tree", "-r", "--name-only", rev],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()
        self.all = set(names)
        self.py = blobs(repo, rev, lambda p: p.endswith(".py") and not p.startswith(SKIP))
        self.index()

    def index(self):
        self.mod_of = {f: modname(f) for f in self.py}
        self.file_of = {}
        for f, m in self.mod_of.items():
            self.file_of.setdefault(m, f)
        self.by_base, self.by_pkg, self.suffix = (
            collections.defaultdict(list),
            collections.defaultdict(list),
            collections.defaultdict(list),
        )
        for f in self.py:
            p = pathlib.PurePosixPath(f)
            self.by_base[p.name].append(f)
            if p.name == "__init__.py":
                self.by_pkg[p.parent.name].append(f)
            parts = f.split("/")
            for k in range(2, len(parts) + 1):
                self.suffix["/".join(parts[-k:])].append(f)

    def resolve(self, name):
        while name:
            if name in self.file_of:
                return self.file_of[name]
            name = name.rsplit(".", 1)[0] if "." in name else ""
        return None

    def bare(self, here, top):
        same = [x for x in (f"{here}/{top}.py", f"{here}/{top}/__init__.py") if x in self.py]
        return same, [
            x
            for x in self.by_base.get(top + ".py", []) + self.by_pkg.get(top, [])
            if x not in same and not x.startswith("src/")
        ]

    def edges(self, f):
        src = self.py[f].decode("utf-8", "ignore")
        try:
            tree = ast.parse(src)
        except SyntaxError:
            return [], [("SyntaxError", 0, "")]
        m = self.mod_of[f]
        pkg = m if f.endswith("__init__.py") else (m.rsplit(".", 1)[0] if "." in m else "")
        here = str(pathlib.PurePosixPath(f).parent)
        out, dyn = [], []
        docs = set()
        for n in ast.walk(tree):
            if (
                isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and n.body
                and isinstance(n.body[0], ast.Expr)
                and isinstance(n.body[0].value, ast.Constant)
                and isinstance(n.body[0].value.value, str)
            ):
                docs.add(id(n.body[0].value))
            elif isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant):
                docs.add(id(n.value))

        def name_edge(name, line, lazy, mech):
            top = name.split(".")[0]
            if top in ROOTS:
                r = self.resolve(name)
                if r:
                    out.append((r, mech, line, lazy))
                return
            same, other = self.bare(here, top)
            if top in STD or top in THIRD:
                return
            for x in same:
                out.append((x, mech + "-bare-same", line, lazy))
            for x in other:
                out.append((x, mech + ("-bare-flat" if not same else "-bare-weak"), line, lazy))

        def walk(node, lazy):
            for n in ast.iter_child_nodes(node):
                z = lazy or isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
                if isinstance(n, ast.Import):
                    for a in n.names:
                        name_edge(a.name, n.lineno, lazy, "import")
                elif isinstance(n, ast.ImportFrom):
                    if n.level:
                        bp = pkg.split(".") if pkg else []
                        if n.level > 1:
                            bp = bp[: len(bp) - (n.level - 1)]
                        base = ".".join(bp + ([n.module] if n.module else []))
                        for q in [base] + [base + "." + a.name for a in n.names]:
                            r = self.resolve(q)
                            if r:
                                out.append((r, "rel", n.lineno, lazy))
                    else:
                        for q in [n.module or ""] + [
                            (n.module or "") + "." + a.name for a in n.names
                        ]:
                            name_edge(q, n.lineno, lazy, "import")
                elif isinstance(n, ast.Call):
                    fn = (
                        n.func.attr
                        if isinstance(n.func, ast.Attribute)
                        else n.func.id
                        if isinstance(n.func, ast.Name)
                        else ""
                    )
                    if fn in ("import_module", "__import__"):
                        if (
                            n.args
                            and isinstance(n.args[0], ast.Constant)
                            and isinstance(n.args[0].value, str)
                        ):
                            name_edge(n.args[0].value.lstrip("."), n.lineno, lazy, "importlib")
                        else:
                            dyn.append((fn, n.lineno, ast.unparse(n)[:200]))
                    elif fn in (
                        "spec_from_file_location",
                        "run_path",
                        "run_module",
                        "SourceFileLoader",
                        "private",
                        "module_path",
                        "load_module",
                        "load_source",
                    ):
                        dyn.append((fn, n.lineno, ast.unparse(n)[:240]))
                if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs:
                    for s in re.findall(r"[A-Za-z0-9_./\-]+\.py\b", n.value):
                        s = re.sub(r"^(\./)+", "", s).lstrip("/")
                        if s in self.py:
                            out.append((s, "path-full", n.lineno, z))
                            continue
                        if "/" in s:
                            rel = set(self.suffix.get(s, []))
                            base = pathlib.PurePosixPath(here)
                            for up in [base, *base.parents]:
                                c = str(up / s)
                                if c in self.py:
                                    rel.add(c)
                            for x in rel:
                                out.append((x, "path-end", n.lineno, z))
                        elif s != "__init__.py":
                            same = f"{here}/{s}"
                            if same in self.py:
                                out.append((same, "path-same", n.lineno, z))
                            for x in self.by_base.get(s, []):
                                if x != same:
                                    out.append(
                                        (
                                            x,
                                            "path-base"
                                            if same not in self.py
                                            else "path-base-weak",
                                            n.lineno,
                                            z,
                                        )
                                    )
                    if (
                        re.fullmatch(r"[A-Za-z_]\w*(\.[A-Za-z_]\w*)+", n.value)
                        and n.value.split(".")[0] in ROOTS
                    ):
                        r = self.file_of.get(n.value)
                        if r:
                            out.append((r, "dotted", n.lineno, z))
                walk(n, z)

        walk(tree, False)
        seen, uniq = set(), []
        for e in out:
            if e[0] != f and e not in seen:
                seen.add(e)
                uniq.append(e)
        return uniq, dyn

    def graph(self):
        g, d = {}, {}
        for f in self.py:
            g[f], d[f] = self.edges(f)
        return g, d


if __name__ == "__main__":
    import pickle

    t = Tree(sys.argv[1], sys.argv[2])
    g, d = t.graph()
    pickle.dump((g, d, t.all, set(t.py)), open(sys.argv[3], "wb"))
    print(len(t.py), "python files;", sum(map(len, g.values())), "edges")
