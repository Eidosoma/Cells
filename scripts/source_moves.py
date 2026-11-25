"""D188's scripted source moves: one move map, one import rewriter, one verifier.

A move map names modules by their dotted names, old to new (docs/SOURCE_LAYOUT_MOVES_DESIGN.md).
The rewriter moves each file, keeping its bytes, then rewrites every reference to a moved module
in the files in scope, and only those references:
  - `import`, `from ... import`, aliases and relative imports (a relative import whose meaning
    the move would change becomes absolute);
  - attribute chains of a module imported without an alias (`pkg.mod.name`);
  - dotted module paths in strings and comments, with or without an attribute after them
    (mock targets, `-m` arguments, `module:function` entry points); a `from PKG import X` in
    free text (a program in a string with escapes, a comment) maps X by X's own new home when X
    is a moved module, as a Python from-import is mapped, not by PKG's;
  - file paths of moved modules in strings and comments, as `src/cells/<path>.py`, `cells/<path>`
    or a path relative to src/cells that starts with one of its folders.
A file the rewrite changed then gets ruff's import sorting (`--select I --fix`) and nothing else.
Nothing else is edited: no formatting, no hand edits. Strings that build a module path at run
time (a package prefix ending in a dot, an f-string) cannot be rewritten; scan lists them as
hazards and apply refuses a map that a hazard reaches. A package the map lists under "dissolve"
loses its package file (a docstring only) when every other file in its folder moves away; nothing
may name that package afterwards. cells.modules is reserved: no map moves into or out of it.

Scope: tracked files under src/, tests/, validation/, scripts/ and examples/ (Python, and the
shell, TOML and config files there), and pyproject.toml. Left alone: everything else (docs,
reports, records, JSON and Markdown anywhere, agent-work/, visualizer/), the map files, the
paths a map lists under "keep", and every line marked to keep: a line with a comment holding
`source-moves: keep` (in Python, a comment token; in a shell, TOML or config file, anywhere on
the line). The marker is for recorded text in code, a string that saved data repeats and code
compares, replays or regenerates (a preparation recipe's provenance, a registered protocol's
disclosure): an identifier that is never resolved as a module, so no move may change it.

The verifier replays the map on the base commit's tracked files in memory and requires the
head commit's tracked files to equal the result, byte for byte and mode for mode, so every
changed line is the rewriter's and nothing else changed. It also requires a second application
to change nothing, and every static `cells.*` import in scope to resolve in the result.

Usage (PYTHONPATH=src:. with the venv's Python; ruff from the same venv):
  python scripts/source_moves.py check MAP
  python scripts/source_moves.py scan MAP [--out JSON]
  python scripts/source_moves.py apply MAP [--stage]
  python scripts/source_moves.py verify MAP --base REV --head REV [--out JSON]
  python scripts/source_moves.py table MAP [--out JSON]   (the old-to-new path table)
  python scripts/source_moves.py ids MAP BASE_IDS HEAD_IDS [--base-log LOG --head-log LOG]
      [--out JSON]   (the collected-ID gate through the map)
  python scripts/source_moves.py selftest
All but ids and selftest take --tree DIR, the checkout to work on (default: this one).
Exit status: 0 ok, 1 a check failed, 2 the map or tree is refused.
"""

import argparse
import ast
import io
import json
import re
import subprocess
import sys
import tokenize
from collections import defaultdict
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
MAP_KIND = "cells.source_moves.map@1"
REPORT_KIND = "cells.source_moves.report@1"
PACKAGE = "cells"
SCOPE_DIRS = ("src/", "tests/", "validation/", "scripts/", "examples/")
SCOPE_FILES = ("pyproject.toml",)
TEXT_SUFFIXES = (".sh", ".toml", ".cfg", ".ini")
SELF = ("scripts/source_moves.py", "scripts/moves/")
RUFF = Path(sys.executable).with_name("ruff")
# First-party packages named explicitly: ruff otherwise decides by what exists on disk, and a
# moved package does not exist yet when the rewriter sorts.
ISORT = "lint.isort.known-first-party = ['cells', 'tests', 'validation']"
DOTTED = re.compile(r"(?<![\w.])" + PACKAGE + r"(?:\.[A-Za-z_]\w*)+(?![\w@])")
# A package prefix that run-time code completes: "cells.core." or "cells.core.".join(...)
PREFIX = re.compile(r"(?<![\w.])(" + PACKAGE + r"(?:\.[A-Za-z_]\w*)*)\.(?![\w.])")
RELATIVE = re.compile(r"^\s*from \.", re.M)
PATH = re.compile(
    r"(?<![\w./-])((?:src/)?" + PACKAGE + r"/)?((?:[A-Za-z_]\w*/)*[A-Za-z_]\w*\.py)(?![\w/])"
)


# Packages no move touches: cells.modules is the stable import surface for contributed modules,
# "one package whose path never moves" (D185, D195; docs/CORE_SEAMS_DESIGN.md section 8.5). A map
# may neither move a module into it or out of it nor create a package there; a tree that already
# holds it (seam F's provisional package) is moved around it.
RESERVED = (PACKAGE + ".modules",)


def _under(module, package):
    return module == package or module.startswith(package + ".")


class Refused(Exception):
    """The map or the tree cannot be moved as asked."""


# ------------------------------------------------------------------ the map


class MoveMap:
    """One move: {old module: new module}, the packages it creates, the paths it keeps."""

    def __init__(self, doc, name="map"):
        if doc.get("kind") != MAP_KIND:
            raise Refused(f"{name}: kind is not {MAP_KIND}")
        self.name = doc.get("move", name)
        self.pairs = {}
        for old, new in doc["modules"]:
            for m in (old, new):
                if not re.fullmatch(PACKAGE + r"(\.[A-Za-z_]\w*)+", m):
                    raise Refused(f"{name}: not a module name: {m!r}")
            if old in self.pairs:
                raise Refused(f"{name}: {old} is listed twice")
            self.pairs[old] = new
        news = list(self.pairs.values())
        if len(set(news)) != len(news):
            raise Refused(f"{name}: two modules move to one name")
        if set(news) & set(self.pairs):
            raise Refused(f"{name}: a module moves onto another moved module's old name")
        self.packages = dict(doc.get("packages", {}))
        # Packages dissolved by the move: each one's package file (a docstring only) is removed,
        # because every module in its folder moves away (D188 move 2: processes/).
        self.dissolve = list(doc.get("dissolve", []))
        for pkg in self.dissolve:
            if not re.fullmatch(PACKAGE + r"(\.[A-Za-z_]\w*)+", pkg) or pkg in self.pairs:
                raise Refused(f"{name}: cannot dissolve {pkg!r} (not a package name, or mapped)")
            if any(_under(m, pkg) for m in [*news, *self.packages]):
                raise Refused(f"{name}: a module or package moves into dissolved {pkg}")
        touched = [*self.pairs, *news, *self.packages, *self.dissolve]
        reserved = sorted(m for m in touched if any(_under(m, r) for r in RESERVED))
        if reserved:
            raise Refused(f"{name}: moves into or out of a reserved package: {reserved[:5]}")
        self.keep = {k["path"]: k["reason"] for k in doc.get("keep", [])}
        self.reviewed = {k["path"]: k["reason"] for k in doc.get("reviewed", [])}
        # Splits and merges are refactors, never part of a move commit: each is declared with
        # the separate commit that made it, for tools that follow src/cells by place.
        self.refactors = list(doc.get("refactors", []))
        self.files_table, self.parents = None, None  # Caches.

    def resolve(self, dotted):
        """The new name of a dotted reference (a module, or a module and attributes), or None."""
        parts = dotted.split(".")
        for k in range(len(parts), 1, -1):
            head = ".".join(parts[:k])
            if head in self.pairs:
                return ".".join([self.pairs[head], *parts[k:]])
        return None

    def kept(self, path):
        return path in self.keep or any(path.startswith(p) for p in SELF)

    def stale(self, dotted):
        """A dotted reference to a dissolved package that no moved module accounts for."""
        return self.resolve(dotted) is None and any(_under(dotted, p) for p in self.dissolve)


def module_path(dotted, files):
    """The tracked file of a dotted module: its .py, or its package's __init__.py, or None."""
    base = "src/" + dotted.replace(".", "/")
    for p in (base + ".py", base + "/__init__.py"):
        if p in files:
            return p
    return None


def dotted_of(path):
    """The dotted module name of a file under src/, or None."""
    p = PurePosixPath(path)
    if p.parts[0] != "src" or p.suffix != ".py":
        return None
    parts = list(p.with_suffix("").parts[1:])
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def in_scope(path):
    if path.startswith(SELF):
        return False
    if path in SCOPE_FILES:
        return True
    if not path.startswith(SCOPE_DIRS):
        return False
    return path.endswith(".py") or path.endswith(TEXT_SUFFIXES)


def plan_files(mp, files):
    """{old path: new path} of the moves still to make, and the package files to create.
    Refuses a module absent from the tree, a clash, and an unmapped module left in a package
    the map moves (a file that exists only on one branch)."""
    moves, done = {}, []
    for old, new in mp.pairs.items():
        src, dst = module_path(old, files), module_path(new, files)
        if src and dst:
            raise Refused(f"{old}: both {src} and {dst} exist")
        if src is None and dst is None:
            raise Refused(f"{old}: absent from the tree (and {new} too)")
        if src is None:
            done.append(old)  # Already moved: this map was applied here before.
            continue
        tail = "/__init__.py" if src.endswith("/__init__.py") else ".py"
        moves[src] = "src/" + new.replace(".", "/") + tail
    for src in moves:
        if src.endswith("/__init__.py"):  # A package moves: every module in it must move too.
            folder = src.rsplit("/", 1)[0] + "/"
            left = [f for f in files if f.startswith(folder) and f.endswith(".py")]
            left = [f for f in left if f not in moves]
            if left:
                raise Refused(f"{folder} moves, but the map does not list {left[:5]}")
    removes = []
    for pkg in mp.dissolve:  # Its package file goes; every other file in its folder must move.
        init = "src/" + pkg.replace(".", "/") + "/__init__.py"
        folder = init.rsplit("/", 1)[0] + "/"
        left = [f for f in files if f.startswith(folder) and f != init and f not in moves]
        if left:
            raise Refused(f"{pkg} dissolves, but the map does not move {left[:5]}")
        if init not in files:
            continue  # Already dissolved: this map was applied here before.
        if not _docstring_only(files[init][1]):
            raise Refused(f"{init}: a dissolved package's file may hold a docstring only")
        removes.append(init)
    creates = {}
    for pkg, text in mp.packages.items():
        path = "src/" + pkg.replace(".", "/") + "/__init__.py"
        if path in files and files[path][1].decode() != text:
            raise Refused(f"{path} exists with other content than the map's")
        if path not in files:
            creates[path] = text
    targets = set(moves.values()) | set(creates)
    for path in moves.values():  # Every new folder needs its package file.
        parent = PurePosixPath(path).parent
        while parent.as_posix() not in ("src", "src/" + PACKAGE):
            init = (parent / "__init__.py").as_posix()
            if init not in files and init not in targets:
                raise Refused(f"{path}: the map creates no {init}")
            parent = parent.parent
    clash = targets & (set(files) - set(moves))
    if clash:
        raise Refused(f"targets already exist: {sorted(clash)[:5]}")
    return moves, creates, done, removes


def _docstring_only(data):
    """A package file holding nothing but (at most) a docstring: dissolving it loses no name."""
    body = ast.parse(data.decode()).body
    return (
        all(
            isinstance(n, ast.Expr)
            and isinstance(n.value, ast.Constant)
            and isinstance(n.value.value, str)
            for n in body
        )
        and len(body) <= 1
    )


# ------------------------------------------------------------------ text rewrites


def _rewrite_dotted(text, mp, edits_out=None, base=0, skip=()):
    if PACKAGE + "." not in text:
        return text
    out, last = [], 0
    for m in DOTTED.finditer(text):
        if any(a <= m.start() < b for a, b in skip):
            continue  # Inside a from-import the text rule below has already mapped.
        new = mp.resolve(m.group(0))
        if new is None:
            continue
        out += [text[last : m.start()], new]
        last = m.end()
        if edits_out is not None:
            edits_out.append(("dotted", base + m.start(), m.group(0), new))
    return "".join(out) + text[last:]


_NAME_AS = r"[A-Za-z_]\w*(?:[ \t]+as[ \t]+[A-Za-z_]\w*)?"
FROM_TEXT = re.compile(  # After a word boundary, or after an escape (a program with "\n" in it).
    r"(?:(?<=\\[nt])|(?<![\w.\\]))from[ \t]+("
    + PACKAGE
    + r"(?:\.[A-Za-z_]\w*)*)[ \t]+import[ \t]+("
    + _NAME_AS
    + r"(?:[ \t]*,[ \t]*"
    + _NAME_AS
    + r")*)"
)


def _from_text(text, mp):
    """`from PKG import a, b as c` statements in free text (a string, a comment, a shell or TOML
    file), each mapped as the Python rewriter maps a from-import: an imported name that is a moved
    module goes to that module's new parent (with `as old_name` where its leaf is renamed), any
    other name stays with PKG's new name. The dotted rule alone maps PKG, the package, which is
    wrong for a submodule moving elsewhere (`from cells.core import devices` when core's package
    file and devices move to different folders). Names that diverge become one statement per new
    parent, joined by "; ". Returns [(start, end, replacement)], only for statements this rule
    changes differently from the dotted rule."""
    out = []
    for m in FROM_TEXT.finditer(text):
        base = m.group(1)
        names = [re.split(r"[ \t]+as[ \t]+", n.strip()) for n in m.group(2).split(",")]
        if not any(f"{base}.{n[0]}" in mp.pairs for n in names):
            continue  # No moved submodule: the dotted rule maps it.
        here = mp.resolve(base) or base
        groups, order = defaultdict(list), []
        for n in names:
            name, asname = n[0], (n[1] if len(n) > 1 else None)
            full = f"{base}.{name}"
            if full in mp.pairs:
                parent, _, leaf = mp.pairs[full].rpartition(".")
                item = (leaf, asname if asname else (None if leaf == name else name))
            else:
                parent, item = here, (name, asname)
            if parent not in groups:
                order.append(parent)
            groups[parent].append(item)
        statements = [
            f"from {p} import "
            + ", ".join(n if a in (None, n) else f"{n} as {a}" for n, a in groups[p])
            for p in order
        ]
        out.append((m.start(), m.end(), "; ".join(statements)))
    return out


def _old_files(mp):
    """{old path relative to src/cells: new one}, for module files and package folders."""
    if mp.files_table is not None:
        return mp.files_table
    out = {}
    for old, new in mp.pairs.items():
        a = old.split(".")[1:]
        b = new.split(".")[1:]
        out["/".join(a) + ".py"] = "/".join(b) + ".py"
        out["/".join(a) + "/__init__.py"] = "/".join(b) + "/__init__.py"
    mp.files_table = out
    return out


def _rewrite_paths(text, mp, top, edits_out=None, base=0):
    if ".py" not in text:
        return text
    table = _old_files(mp)
    out, last = [], 0
    for m in PATH.finditer(text):
        prefix, rel = m.group(1), m.group(2)
        if prefix is None and rel.split("/", 1)[0] not in top:
            continue  # A path relative to src/cells must start with one of its folders.
        if rel not in table:
            continue
        new = (prefix or "") + table[rel]
        out += [text[last : m.start()], new]
        last = m.end()
        if edits_out is not None:
            edits_out.append(("path", base + m.start(), m.group(0), new))
    return "".join(out) + text[last:]


def rewrite_text(text, mp, top, edits_out=None, base=0):
    """From-imports of moved modules (by each module's own new home), dotted module paths, then
    moved files' paths, in free text."""
    found = []
    spans = _from_text(text, mp) if "import" in text else []
    if spans:
        out, last, skip, shift = [], 0, [], 0
        for s, e, new in spans:
            out += [text[last:s], new]
            skip.append((s + shift, s + shift + len(new)))
            shift += len(new) - (e - s)
            found.append(("from-text", base + s, text[s:e], new))
            last = e
        text = "".join(out) + text[last:]
    else:
        skip = []
    text = _rewrite_dotted(text, mp, found, base, skip)
    text = _rewrite_paths(text, mp, top, found, base)
    if edits_out is not None:
        edits_out.extend(found)
    return text


KEEP_MARK = "source-moves: keep"


def kept_lines(text, python):
    """The lines (from 1) marked to keep: in Python, those with a comment holding KEEP_MARK (in a
    string it marks nothing); in other text, those holding it anywhere."""
    if KEEP_MARK not in text:
        return set()
    if not python:
        return {i for i, line in enumerate(text.splitlines(), 1) if KEEP_MARK in line}
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except tokenize.TokenError:
        return set()
    return {t.start[0] for t in tokens if t.type == tokenize.COMMENT and KEEP_MARK in t.string}


def _rewrite_text_keeping(text, mp, top, edits_out, kept):
    """rewrite_text line by line, the kept lines as they are (every text rule is line-local)."""
    out, base = [], 0
    for i, line in enumerate(text.splitlines(keepends=True), 1):
        out.append(line if i in kept else rewrite_text(line, mp, top, edits_out, base))
        base += len(line)
    return "".join(out)


def _line_of(text, offset):
    return text.count("\n", 0, offset) + 1


def _hazard_line(h):
    """A Python hazard's line ("file:line" in its where), or None."""
    tail = str(h.get("where", "")).rsplit(":", 1)[-1]
    return int(tail) if tail.isdigit() else None


def hazards_in_text(text, mp, where):
    """Package prefixes that run-time code completes, for packages holding moved modules."""
    out = []
    if mp.parents is None:
        mp.parents = {o.rsplit(".", 1)[0] for o in mp.pairs} | set(mp.pairs)
    moved_parents = mp.parents
    if PACKAGE + "." not in text:
        return out
    for m in PREFIX.finditer(text):
        if m.group(1) in moved_parents:
            out.append(dict(kind="prefix", where=where, text=m.group(0)))
    return out


# ------------------------------------------------------------------ the Python rewriter


class _Lines:
    """Offsets into a text by line, splitting on newlines only (as the tokenizer does)."""

    def __init__(self, text):
        self.text = text
        self.starts = [0] + [m.end() for m in re.finditer("\n", text)] + [len(text) + 1]

    def offset(self, lineno, col):
        """Offset of an AST position: 1-based line, UTF-8 byte column."""
        start = self.starts[lineno - 1]
        line = self.text[start : self.starts[lineno]]
        return start + len(line.encode()[:col].decode())

    def char(self, row, col):
        """Offset of a tokenizer position: 1-based row, character column."""
        return self.starts[row - 1] + col


def _absolute(module, level, own):
    """The absolute module of a relative import in module `own` (a module or a package)."""
    if not level:
        return module
    pkg = own["package"].split(".")
    if level - 1 > len(pkg) - 1:
        raise Refused(f"{own['name']}: relative import beyond the top package")
    pkg = pkg[: len(pkg) - level + 1]
    return ".".join([*pkg, module] if module else pkg)


def _own(dotted, path):
    is_pkg = path.endswith("/__init__.py")
    return dict(name=dotted, package=dotted if is_pkg else dotted.rpartition(".")[0])


def _module_span(text, lines, node):
    """(start, end) offsets of the module name in a `from X import` statement."""
    start = lines.offset(node.lineno, node.col_offset)
    end = lines.offset(node.end_lineno, node.end_col_offset)
    segment = text[start:end]
    local = _Lines(segment)
    span, seen = None, False
    for tok in tokenize.generate_tokens(io.StringIO(segment).readline):
        if tok.type == tokenize.NAME and tok.string == "from" and not seen:
            seen = True
            continue
        if tok.type == tokenize.NAME and tok.string == "import":
            break
        if seen and (tok.type == tokenize.NAME or tok.string in (".", "...")):
            a, b = local.char(*tok.start), local.char(*tok.end)
            span = (a, b) if span is None else (span[0], b)
    if span is None:
        raise Refused("cannot find a from-import's module")
    return start + span[0], start + span[1]


def _render_from(groups, level, indent):
    lines = []
    for parent, names in groups:
        items = []
        for name, asname in names:
            items.append(name if asname in (None, name) else f"{name} as {asname}")
        dots = "." * level
        lines.append(f"from {dots}{parent} import {', '.join(items)}")
    return ("\n" + indent).join(lines)


def _has_comment(text):
    try:
        return any(
            t.type == tokenize.COMMENT for t in tokenize.generate_tokens(io.StringIO(text).readline)
        )
    except (tokenize.TokenError, IndentationError):
        return True


EMBEDDED = dict(name="", package="")
STRING_PARTS = re.compile(r"^([rRuU]?)(\"\"\"|\'\'\'|\"|\')(.*)\2$", re.S)


def _embedded(tok, mp, modules, top, report):
    """A string holding a Python program that imports a cells module (a test's subprocess
    program): its body rewritten as Python, or None. Bodies with escapes cannot be mapped to
    source text and are left to the plain string rules, whose from-import rule maps each
    imported module by its own new home (scan still lists them as hazards, for review)."""
    m = STRING_PARTS.match(tok)
    if not m or "import" not in m.group(3) or PACKAGE not in m.group(3):
        return None, []
    prefix, quote, body = m.groups()
    if "\\" in body and not prefix.lower().startswith("r"):
        return None, [dict(kind="embedded-escapes", text=body[:80], reaches=None)]
    try:
        ast.parse(body)
    except SyntaxError:
        return None, []
    new, hazards = rewrite_python(body, mp, EMBEDDED, EMBEDDED, modules, top, report)
    return prefix + quote + new + quote, hazards


def rewrite_python(text, mp, own_old, own_new, modules, top, report):
    """One Python file's references to moved modules. `modules` is the set of every module
    name in the tree before the move (to tell a submodule from a name inside a module)."""
    tree = ast.parse(text)
    lines = _Lines(text)
    edits = []  # (start, end, replacement, kind, old)
    bare_roots = set()  # Names bound by `import a.b.c` without an alias.

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                new = mp.resolve(a.name)
                if a.asname is None and a.name.startswith(PACKAGE + "."):
                    bare_roots.add(a.name.split(".")[0])
                if new is None:
                    continue
                s = lines.offset(a.lineno, a.col_offset)
                if text[s : s + len(a.name)] != a.name:
                    raise Refused(
                        f"{own_old['name']}:{a.lineno}: an import name split across tokens"
                    )
                edits.append((s, s + len(a.name), new, "import", a.name))
        elif isinstance(node, ast.ImportFrom):
            base = _absolute(node.module, node.level, own_old)
            groups, order = defaultdict(list), []
            for a in node.names:
                full = f"{base}.{a.name}"
                # A submodule, whose parent may change: one in the tree, or a module the map moves
                # (on a tree merged after the move, the old module is no longer there).
                if a.name != "*" and (full in modules or full in mp.pairs):
                    target = mp.resolve(full) or full
                    parent, _, leaf = target.rpartition(".")
                    asname = a.asname if a.asname else (None if leaf == a.name else a.name)
                    item = (leaf, asname)
                else:  # A name inside the module.
                    parent = mp.resolve(base) or base
                    item = (a.name, a.asname)
                if parent not in groups:
                    order.append(parent)
                groups[parent].append(item)
            renamed = [(p, groups[p]) for p in order]
            same_items = len(renamed) == 1 and renamed[0][1] == [
                (a.name, a.asname) for a in node.names
            ]
            if node.level:
                try:
                    again = _absolute(node.module, node.level, own_new)
                except Refused:
                    again = None
                if same_items and renamed[0][0] == base and again == base:
                    continue  # The same text still means the same module from the new place.
            else:
                if same_items and renamed[0][0] == base:
                    continue
                if same_items:  # Only the module part changes: edit it in place.
                    s, e = _module_span(text, lines, node)
                    edits.append((s, e, renamed[0][0], "from", base))
                    continue
            start = lines.offset(node.lineno, node.col_offset)
            end = lines.offset(node.end_lineno, node.end_col_offset)
            if _has_comment(text[start:end]):
                raise Refused(
                    f"{own_old['name']}:{node.lineno}: a from-import to rewrite holds a comment"
                )
            indent = text[lines.starts[node.lineno - 1] : start]
            rendered = _render_from(renamed, 0, indent)
            edits.append((start, end, rendered, "from-split", text[start:end]))

    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    if bare_roots:
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Name) and node.id in bare_roots):
                continue
            chain, cur = [node.id], node
            nodes = [node]
            while isinstance(parents.get(cur), ast.Attribute) and parents[cur].value is cur:
                cur = parents[cur]
                chain.append(cur.attr)
                nodes.append(cur)
            for k in range(len(chain), 1, -1):
                dotted = ".".join(chain[:k])
                if dotted in mp.pairs:
                    n = nodes[k - 1]
                    s = lines.offset(node.lineno, node.col_offset)
                    e = lines.offset(n.end_lineno, n.end_col_offset)
                    if text[s:e] != dotted:
                        raise Refused(
                            f"{own_old['name']}:{node.lineno}: a dotted chain split across lines"
                        )
                    edits.append((s, e, mp.pairs[dotted], "chain", dotted))
                    break

    hazards = []
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except tokenize.TokenError as error:
        raise Refused(f"{own_old['name']}: {error}") from error
    constants = {
        n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
    }
    for tok in tokens:
        if tok.type not in (tokenize.STRING, tokenize.COMMENT, tokenize.FSTRING_MIDDLE):
            continue
        s, e = lines.char(*tok.start), lines.char(*tok.end)
        where = f"{own_old['name'] or ''}:{tok.start[0]}"
        if text[s:e] != tok.string:  # An f-string part with escaped braces: not rewritten.
            for h in hazards_in_text(tok.string, mp, where):
                hazards.append(dict(h, kind="f-string", reaches=None))
            continue
        found = []
        new = None
        if tok.type == tokenize.STRING:  # A program in a string: rewritten as Python.
            new, nested = _embedded(tok.string, mp, modules, top, [])
            hazards += [
                dict(h, where=where)
                for h in nested
                if h["kind"] == "embedded-escapes"
                and any(mp.resolve(d) for d in DOTTED.findall(tok.string))
            ]
            if new is not None and new != tok.string:
                edits.append((s, e, new, "embedded", tok.string))
                continue
        new = rewrite_text(tok.string, mp, top, found, s)
        if new != tok.string:
            kind = "comment" if tok.type == tokenize.COMMENT else "string"
            edits.append((s, e, new, kind, tok.string))
        if tok.type == tokenize.COMMENT:
            continue
        for h in hazards_in_text(tok.string, mp, where):
            prefix = h["text"].rstrip(".")
            h["reaches"] = sorted(
                c
                for c in constants
                if mp.resolve(f"{prefix}.{c}") or mp.resolve(f"{prefix}.{c.split('.')[0]}")
            )
            hazards.append(h)
        if tok.type == tokenize.FSTRING_MIDDLE:
            for h in hazards:
                if h["where"] == where and h["kind"] == "prefix":
                    h["kind"], h["reaches"] = "f-string", None  # Completed at run time.

    kept = kept_lines(text, python=True)
    if kept:  # A marked line keeps every byte: its edits and its hazards are dropped.
        edits = [
            x
            for x in edits
            if not kept & set(range(_line_of(text, x[0]), _line_of(text, max(x[0], x[1] - 1)) + 1))
        ]
        hazards = [h for h in hazards if _hazard_line(h) not in kept]
    edits.sort()
    for (s1, e1, *_), (s2, *_rest) in zip(edits, edits[1:], strict=False):
        if s2 < e1:
            raise Refused(f"{own_old['name']}: overlapping edits at {s1}")
    out, last = [], 0
    for s, e, new, kind, old in edits:
        out += [text[last:s], new]
        last = e
        report.append(dict(kind=kind, line=text.count("\n", 0, s) + 1, old=old, new=new))
    return "".join(out) + text[last:], hazards


def sort_imports(text, path):
    """ruff's import sorting (I001) only, with this tool's checkout's configuration."""
    proc = subprocess.run(
        [
            str(RUFF),
            "check",
            "--select",
            "I",
            "--fix",
            "--quiet",
            "--config",
            str(ROOT / "pyproject.toml"),
            "--config",
            ISORT,
            "--stdin-filename",
            path,
            "-",
        ],
        input=text,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    if proc.returncode not in (0, 1) or not proc.stdout:
        raise Refused(f"ruff failed on {path}: {proc.stderr.strip()[:300]}")
    return proc.stdout


# ------------------------------------------------------------------ the tree transform


def transform(files, mp):
    """The tree after one map: (files, report). files is {path: (mode, bytes)} of tracked files."""
    moves, creates, done, removes = plan_files(mp, files)
    modules = {dotted_of(p) for p in files if dotted_of(p)}
    top = {  # The folders of src/cells: a path relative to src/cells starts with one.
        PurePosixPath(p).parts[2]
        for p in files
        if p.startswith("src/" + PACKAGE + "/") and len(PurePosixPath(p).parts) > 3
    }
    out, report, hazards = {}, dict(moved=[], created=[], files={}, done=done), []
    report["dissolved"] = sorted(removes)
    back = {new: old for old, new in moves.items()}
    for path, (mode, data) in files.items():
        if path not in removes:
            out[moves.get(path, path)] = (mode, data)
    for path, text in creates.items():
        out[path] = ("100644", text.encode())
        report["created"].append(path)
    report["moved"] = sorted(moves.items())
    for path in sorted(out):
        old_path = back.get(path, path)
        if old_path in creates or not in_scope(path) or mp.kept(old_path):
            continue
        mode, data = out[path]
        try:
            text = data.decode()
        except UnicodeDecodeError:
            continue
        if PACKAGE not in text and not RELATIVE.search(text):
            continue
        edits = []
        if path.endswith(".py"):
            old_dotted = dotted_of(old_path) or ""
            new_dotted = dotted_of(path) or ""
            new, found = rewrite_python(
                text, mp, _own(old_dotted, old_path), _own(new_dotted, path), modules, top, edits
            )
            hazards += [dict(h, file=old_path) for h in found]
            if new != text:
                new = sort_imports(new, path)
        else:
            kept = kept_lines(text, python=False)
            if kept:
                new = _rewrite_text_keeping(text, mp, top, edits, kept)
                lines = text.splitlines(keepends=True)
                text_for_hazards = "".join(
                    "\n" if i in kept else line for i, line in enumerate(lines, 1)
                )
            else:
                new = rewrite_text(text, mp, top, edits)
                text_for_hazards = text
            hazards += [
                dict(h, file=old_path) for h in hazards_in_text(text_for_hazards, mp, old_path)
            ]
        if new != text:
            out[path] = (mode, new.encode())
            report["files"][path] = edits
    report["hazards"] = hazards
    return out, report


# ------------------------------------------------------------------ git and the tree


def git(*args, cwd=ROOT, data=None):
    proc = subprocess.run(["git", *args], cwd=cwd, input=data, capture_output=True)
    if proc.returncode:
        raise Refused(f"git {' '.join(args[:3])}: {proc.stderr.decode().strip()[:300]}")
    return proc.stdout


def tree_at(rev, cwd=ROOT):
    """{path: (mode, bytes)} of every file tracked at a revision."""
    listing = git("ls-tree", "-r", "-z", "--full-tree", rev, cwd=cwd).split(b"\0")
    rows = []
    for row in listing:
        if not row:
            continue
        meta, path = row.split(b"\t", 1)
        mode, kind, blob = meta.decode().split()
        if kind == "blob":
            rows.append((path.decode(), mode, blob))
    batch = git("cat-file", "--batch", cwd=cwd, data="".join(b + "\n" for _, _, b in rows).encode())
    out, pos = {}, 0
    for path, mode, _ in rows:
        header_end = batch.index(b"\n", pos)
        size = int(batch[pos:header_end].split()[2])
        start = header_end + 1
        out[path] = (mode, batch[start : start + size])
        pos = start + size + 1
    return out


def worktree_files(root):
    """{path: (mode, bytes)} of the worktree's tracked files, as they are on disk."""
    listing = git("ls-files", "-s", "-z", cwd=root).split(b"\0")
    out = {}
    for row in listing:
        if not row:
            continue
        meta, path = row.split(b"\t", 1)
        mode = meta.decode().split()[0]
        p = Path(root) / path.decode()
        if p.is_file():
            out[path.decode()] = (mode, p.read_bytes())
    return out


def unresolved_imports(files):
    """Static `cells.*` imports in scope that name no module (or no name) in the tree. A folder
    of modules without a package file is a namespace package (PEP 420), as Python imports it
    (cells/records/ held relations.py alone before move 2): its submodules resolve, and it
    defines no other name."""
    modules = {dotted_of(p): p for p in files if dotted_of(p)}
    namespaces = {
        ".".join(m.split(".")[:k]) for m in modules for k in range(1, m.count(".") + 1)
    } - set(modules)
    names = {}
    out = []

    def defined(mod):
        if mod not in names:
            tree = ast.parse(files[modules[mod]][1].decode())
            got = set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    got.add(node.name)
                elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    got.add(node.id)
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    got |= {(a.asname or a.name).split(".")[0] for a in node.names}
            names[mod] = got
        return names[mod]

    for path, (_, data) in sorted(files.items()):
        if not (path.endswith(".py") and in_scope(path)):
            continue
        try:
            tree = ast.parse(data.decode())
        except (SyntaxError, UnicodeDecodeError):
            continue
        own = dotted_of(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if (
                        a.name.startswith(PACKAGE + ".")
                        and a.name not in modules
                        and a.name not in namespaces
                    ):
                        out.append(f"{path}:{node.lineno}: import {a.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    if own is None:
                        continue
                    base = _absolute(node.module, node.level, _own(own, path))
                else:
                    base = node.module or ""
                if not (base == PACKAGE or base.startswith(PACKAGE + ".")):
                    continue
                if base not in modules and base not in namespaces:
                    out.append(f"{path}:{node.lineno}: from {base}")
                    continue
                for a in node.names:
                    if a.name != "*" and f"{base}.{a.name}" not in modules:
                        if base in namespaces or a.name not in defined(base):
                            out.append(f"{path}:{node.lineno}: from {base} import {a.name}")
    return out


def load_map(path):
    try:
        return MoveMap(json.loads(Path(path).read_text()), Path(path).stem)
    except (KeyError, ValueError) as error:
        raise Refused(f"{path}: {error}") from error


# ------------------------------------------------------------------ actions


def path_table(mp, files):
    """The old-to-new path table of one map, for tools that read src/cells by place: one row
    per file the move relocates, the package files it creates, and the map's declared refactors
    (splits or merges, each with its own commit), and the package files dissolved (removed, every
    module of their folder moving away). `to_legacy` is a key of the format, false since move 1."""
    moves, creates, done, removes = plan_files(mp, files)
    rows = [
        dict(
            old=old,
            new=new,
            kind="move",
            to_legacy=False,
            old_module=dotted_of(old),
            new_module=dotted_of(new),
        )
        for old, new in sorted(moves.items())
    ]
    rows += [
        dict(
            old=None,
            new=path,
            kind="created",
            to_legacy=False,
            old_module=None,
            new_module=dotted_of(path),
        )
        for path in sorted(creates)
    ]
    rows += [
        dict(
            old=path,
            new=None,
            kind="dissolved",
            to_legacy=False,
            old_module=dotted_of(path),
            new_module=None,
        )
        for path in sorted(removes)
    ]
    for r in mp.refactors:
        rows.append(dict(r, kind=r.get("kind", "split")))
    return dict(
        kind="cells.source_moves.path_table@1",
        move=mp.name,
        rows=rows,
        already_moved=done,
        identifiers_changed=[],
    )


def cmd_table(args):
    mp = load_map(args.map)
    table = path_table(mp, worktree_files(args.tree))
    text = json.dumps(table, indent=1) + "\n"
    if args.out:
        Path(args.out).write_text(text)
    print(json.dumps(dict(move=mp.name, rows=len(table["rows"]))))
    return 0


def cmd_check(args):
    mp = load_map(args.map)
    files = worktree_files(args.tree)
    moves, creates, done, removes = plan_files(mp, files)
    print(
        json.dumps(
            dict(
                move=mp.name,
                moves=len(moves),
                creates=sorted(creates),
                dissolves=sorted(removes),
                done=done,
            )
        )
    )
    return 0


def cmd_scan(args):
    mp = load_map(args.map)
    files = worktree_files(args.tree)
    out, report = transform(files, mp)
    left = defaultdict(list)  # References outside the rewriter's scope, left alone.
    olds = list(mp.pairs) + [f"src/{o.replace('.', '/')}" for o in mp.pairs]
    pattern = re.compile("|".join(re.escape(o) + r"(?![\w])" for o in olds))
    for path, (_, data) in files.items():
        if in_scope(path) and not mp.kept(path):
            continue
        try:
            text = data.decode()
        except UnicodeDecodeError:
            continue
        hits = pattern.findall(text)
        if hits:
            left[path.split("/")[0] if "/" in path else path].append((path, len(hits)))
    counts = defaultdict(int)
    for edits in report["files"].values():
        for e in edits:
            counts[e["kind"] if isinstance(e, dict) else e[0]] += 1
    summary = dict(
        kind=REPORT_KIND,
        move=mp.name,
        moved=len(report["moved"]),
        created=report["created"],
        files_rewritten=len(report["files"]),
        edits_by_kind=dict(counts),
        hazards=report["hazards"],
        left_alone={
            k: dict(files=len(v), references=sum(n for _, n in v)) for k, v in left.items()
        },
    )
    if args.out:
        Path(args.out).write_text(
            json.dumps(dict(summary, report=report, left_alone_files=left), indent=1) + "\n"
        )
    print(json.dumps(summary, indent=1))
    return 0


def _hazards_reaching(report, mp):
    """Hazards not yet reviewed for this map. A hazard is a string that run-time code completes
    to a module path under the parent package of a moved module; whether it reaches a moved
    module cannot be decided statically ("reaches" lists the file's own constants that
    complete it, a hint only). Each file holding one is either refactored to full module names
    before the move or listed under the map's "reviewed" with the reason it cannot reach. A
    reviewed file that the map moves keeps its review at its new path, so a second application,
    or a branch's own application after the move, finds it reviewed."""
    reviewed = set(mp.reviewed) | {_moved_path(p, mp) for p in mp.reviewed}
    return [h for h in report["hazards"] if not mp.kept(h["file"]) and h["file"] not in reviewed]


def _moved_path(path, mp):
    """A src/cells module file's path after the map (itself if the map does not move it)."""
    dotted = dotted_of(path)
    if not dotted or dotted not in mp.pairs:
        return path
    tail = "/__init__.py" if path.endswith("/__init__.py") else ".py"
    return "src/" + mp.pairs[dotted].replace(".", "/") + tail


def cmd_apply(args):
    mp = load_map(args.map)
    tree = Path(args.tree)
    if git("status", "--porcelain", "--untracked-files=no", cwd=tree).strip():
        raise Refused(f"{tree} has uncommitted changes: apply works on a clean head")
    files = worktree_files(tree)
    out, report = transform(files, mp)
    reached = _hazards_reaching(report, mp)
    if reached and not args.allow_hazards:
        raise Refused(f"hazards reach this map (fix them first, or keep the file): {reached[:5]}")
    for old, new in report["moved"]:
        (tree / new).parent.mkdir(parents=True, exist_ok=True)
        (tree / old).rename(tree / new)
    touched = [p for pair in report["moved"] for p in pair]
    for path in report["dissolved"]:  # A dissolved package's file (a docstring only).
        (tree / path).unlink()
        touched.append(path)
    for path, (_, data) in out.items():
        p = tree / path
        if not p.exists() or p.read_bytes() != data:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            touched.append(path)
    for old in [o for o, _ in report["moved"]] + report["dissolved"]:  # Folders now empty.
        parent = (tree / old).parent
        while parent != tree and parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
    if args.stage and touched:
        git(
            "add",
            "-A",
            "--pathspec-from-file=-",
            cwd=tree,
            data="\n".join(sorted(set(touched))).encode(),
        )
    print(
        json.dumps(
            dict(
                move=mp.name,
                moved=len(report["moved"]),
                created=report["created"],
                dissolved=report["dissolved"],
                files_rewritten=len(report["files"]),
                done=report["done"],
                hazards=len(reached),
            )
        )
    )
    return 0


def compare(expected, actual):
    """Paths that differ between two trees: [(path, why)]."""
    out = []
    for path in sorted(set(expected) | set(actual)):
        if path not in actual:
            out.append((path, "missing in head"))
        elif path not in expected:
            out.append((path, "not made by the map (an extra file)"))
        elif expected[path][0] != actual[path][0]:
            out.append((path, f"mode {actual[path][0]} != {expected[path][0]}"))
        elif expected[path][1] != actual[path][1]:
            a = expected[path][1].decode(errors="replace").splitlines()
            b = actual[path][1].decode(errors="replace").splitlines()
            line = next(
                (i + 1 for i, (x, y) in enumerate(zip(a, b, strict=False)) if x != y),
                min(len(a), len(b)) + 1,
            )
            out.append((path, f"content differs from the rewriter's, first at line {line}"))
    return out


HASH = re.compile(rb"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")


def hash_edits(before, after, report):
    """Files whose SHA-256-like literals differ before and after the move (D187: a hash is
    never updated, by hand or by this tool; a pin's path may change, its hash may not)."""
    back = {new: old for old, new in report["moved"]}
    out = []
    for path, (_, data) in after.items():
        old = before.get(back.get(path, path))
        if old is not None and old[1] != data:
            if sorted(HASH.findall(old[1])) != sorted(HASH.findall(data)):
                out.append((path, "a hash literal changed"))
    return out


def verify(mp, base, head, cwd=ROOT):
    before = base if isinstance(base, dict) else tree_at(base, cwd)
    actual = head if isinstance(head, dict) else tree_at(head, cwd)
    expected, report = transform(before, mp)
    problems = [dict(path=p, why=w) for p, w in compare(expected, actual)]
    problems += [dict(path=p, why=w) for p, w in hash_edits(before, actual, report)]
    again, report2 = transform(expected, mp)
    if again != expected:
        problems.append(dict(path="*", why="a second application changes the tree"))
    missing = unresolved_imports(expected)
    problems += [dict(path=m.split(":")[0], why=f"unresolved import: {m}") for m in missing]
    still = []
    gone = {  # Dissolved package files, as paths relative to src/cells.
        "/".join(p.split(".")[1:]) + "/__init__.py" for p in mp.dissolve
    }
    for path, (_, data) in expected.items():
        if in_scope(path) and not mp.kept(path) and path.endswith(".py"):
            text = data.decode(errors="replace")
            kept = kept_lines(text, python=True)  # Recorded text keeps its old names.
            for m in DOTTED.finditer(text):
                if kept and _line_of(text, m.start()) in kept:
                    continue
                if mp.resolve(m.group(0)) or mp.stale(m.group(0)):
                    still.append(f"{path}: {m.group(0)}")
            for m in PATH.finditer(text) if gone else ():
                if kept and _line_of(text, m.start()) in kept:
                    continue
                if m.group(2) in gone:
                    still.append(f"{path}: {m.group(0)}")
    problems += [dict(path=s.split(":")[0], why=f"old reference left: {s}") for s in still[:50]]
    return dict(
        kind=REPORT_KIND,
        move=mp.name,
        moved=len(report["moved"]),
        files_rewritten=len(report["files"]),
        hazards=report["hazards"],
        problems=problems,
        verdict="holds" if not problems else "refused",
    )


def cmd_verify(args):
    mp = load_map(args.map)
    result = verify(mp, args.base, args.head, cwd=args.tree)
    result |= dict(
        base=git("rev-parse", args.base, cwd=args.tree).decode().strip(),
        head=git("rev-parse", args.head, cwd=args.tree).decode().strip(),
        ruff=subprocess.run(
            [str(RUFF), "--version"], capture_output=True, text=True
        ).stdout.strip(),
    )
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=1) + "\n")
    print(
        json.dumps(
            {k: v for k, v in result.items() if k != "hazards"}
            | dict(hazards=len(result["hazards"])),
            indent=1,
        )
    )
    return 0 if result["verdict"] == "holds" else 1


# ------------------------------------------------------------------ the collected-ID gate


def map_top(mp):
    """The folders of src/cells that the map's modules live in: a path relative to src/cells
    names a moved file only if it starts with one of them."""
    return {m.split(".")[1] for pair in mp.pairs.items() for m in pair if m.count(".") > 1}


def compare_ids(mp, base, head):
    """The collected test IDs of two trees, through the map (design note section 17): each base
    ID is mapped by the rewriter's own text rules (dotted names and file paths of moved modules),
    so an ID that differs only by a path the map renames, as a parametrization naming a moved
    file does, is the same test. Returns the differences; empty when the gate holds."""
    top = map_top(mp)
    mapped = defaultdict(list)
    for test_id in base:
        mapped[rewrite_text(test_id, mp, top)].append(test_id)
    head = set(head)
    return dict(
        collisions=sorted(sorted(v) for v in mapped.values() if len(v) > 1),
        missing_in_head=sorted(k for k in mapped if k not in head),
        new_in_head=sorted(head - set(mapped)),
        renamed_by_the_map=sorted(
            (v[0], k) for k, v in mapped.items() if len(v) == 1 and v[0] != k
        ),
    )


def _error_lines(path):
    return [
        line.rstrip("\n")
        for line in Path(path).read_text().splitlines()
        if line.startswith("ERROR ")
    ]


def cmd_ids(args):
    mp = load_map(args.map)
    lines = {
        side: [x for x in Path(path).read_text().splitlines() if x.strip()]
        for side, path in (("base", args.base_ids), ("head", args.head_ids))
    }
    result = dict(kind=REPORT_KIND, move=mp.name, base=len(lines["base"]), head=len(lines["head"]))
    result["ids"] = compare_ids(mp, lines["base"], lines["head"])
    if args.base_log and args.head_log:  # Collection errors, compared the same way.
        result["errors"] = compare_ids(mp, _error_lines(args.base_log), _error_lines(args.head_log))
    blocking = [
        k
        for part in ("ids", "errors")
        if part in result
        for k in ("collisions", "missing_in_head", "new_in_head")
        if result[part][k]
    ]
    result["verdict"] = "same tests" if not blocking else "differs: " + ", ".join(blocking)
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=1) + "\n")
    summary = {
        part: {k: len(v) for k, v in result[part].items()}
        for part in ("ids", "errors")
        if part in result
    }
    print(
        json.dumps(
            dict(base=result["base"], head=result["head"], **summary, verdict=result["verdict"])
        )
    )
    return 0 if not blocking else 1


# ------------------------------------------------------------------ planted cases


SELFTEST_TREE = {
    "src/cells/__init__.py": '"""Cells."""\n',
    "src/cells/core/__init__.py": "",
    "src/cells/core/specs.py": "class ConfigError(ValueError):\n    pass\n",
    "src/cells/core/old_spec.py": (
        '"""Parses old worlds (see src/cells/models/old_model.py)."""\n\n'
        "from cells.core.specs import ConfigError\n"
        "from cells.models import old_model\n\n"
        'MODEL_ID = "old@1"\nKIND = "cells.old_spec@1"\n\n\n'
        "def parse(data):\n    return old_model.check(data) or ConfigError\n"
    ),
    "src/cells/models/__init__.py": "",
    "src/cells/models/old_model.py": "def check(data):\n    return None\n",
    "src/cells/models/keep.py": (
        "import importlib\n\n"
        "import cells.core.old_spec\n"
        "from cells.core import old_spec as spec\n"
        "from cells.core import old_spec, specs\n\n\n"
        "def run():\n"
        "    # cells.core.old_spec.parse is the parser\n"
        '    target = importlib.import_module("cells.core.old_spec")\n'
        "    return cells.core.old_spec.parse, spec, old_spec, specs, target\n"
    ),
    "tests/test_old.py": (
        "from unittest import mock\n\n"
        "from cells.core.old_spec import MODEL_ID, parse\n\n\n"
        "def test_old():\n"
        '    with mock.patch("cells.core.old_spec.parse"):\n'
        "        pass\n"
        '    assert MODEL_ID == "old@1" and parse\n'
        '    assert open("src/cells/core/old_spec.py") and "core/old_spec.py"\n'
    ),
    "tests/test_program.py": (
        "import subprocess\n\n"
        'PROGRAM = r"""\nfrom cells.core import old_spec as spec\nprint(spec.MODEL_ID)\n"""\n'
    ),
    "validation/pkg/__init__.py": "",
    "validation/pkg/tool.py": "from . import helper\n\nX = helper\n",
    "validation/pkg/helper.py": "Y = 'cells.core.old_spec:parse'\n",
    "docs/NOTE.md": "cells.core.old_spec stays named here.\n",
    "scripts/run.sh": "python -m cells.core.old_spec --help\n",
}
SELFTEST_MAP = {
    "kind": MAP_KIND,
    "move": "selftest",
    "modules": [
        ["cells.core.old_spec", "cells.held.core.old_spec"],
        ["cells.models.old_model", "cells.held.models.old_model"],
    ],
    "packages": {
        "cells.held": '"""Held."""\n',
        "cells.held.core": "",
        "cells.held.models": "",
    },
}


def _selftest_kept_lines(mp, files, checks):
    """The keep marker, a registered record's scope and namespace packages (18 November 2026)."""
    marked = dict(files)
    recorded = (
        '"""Recorded text."""\n\n'
        "PROVENANCE = dict(\n"
        '    flux="cells.core.old_spec.parse, as recorded",  # source-moves: keep (recorded)\n'
        '    live="cells.core.old_spec.parse",\n'
        ")\n"
        'IN_A_STRING = "cells.core.old_spec # source-moves: keep"\n'
    )
    marked["src/cells/models/recorded.py"] = ("100644", recorded.encode())
    marked["scripts/kept.sh"] = (
        "100644",
        b"python -m cells.core.old_spec  # source-moves: keep\npython -m cells.core.old_spec\n",
    )
    protocol = b'{"engine": "cells.core.old_spec (src/cells/core/old_spec.py)"}\n'
    marked["validation/pkg/pkg_protocol.json"] = ("100644", protocol)
    out, _ = transform(marked, mp)
    got = out["src/cells/models/recorded.py"][1].decode()
    checks["keep marker: the marked line keeps its old name, the next line is rewritten"] = (
        'flux="cells.core.old_spec.parse, as recorded",  # source-moves: keep' in got
        and 'live="cells.held.core.old_spec.parse"' in got
    )
    checks["keep marker: in a string it marks nothing"] = (
        'IN_A_STRING = "cells.held.core.old_spec # source-moves: keep"' in got
    )
    checks["keep marker: a shell line"] = out["scripts/kept.sh"][1] == (
        b"python -m cells.core.old_spec  # source-moves: keep\n"
        b"python -m cells.held.core.old_spec\n"
    )
    checks["a registered protocol's JSON is never rewritten"] = (
        out["validation/pkg/pkg_protocol.json"][1] == protocol
    )
    again, _ = transform(out, mp)
    checks["keep marker: a second application changes nothing"] = again == out
    # Non-vacuous: the moved tree holds cells.core.old_spec on the marked line, which verify's
    # old-reference scan would report but for the marker.
    checks["keep marker: verify holds, no old reference reported on a marked line"] = (
        verify(mp, marked, out)["verdict"] == "holds"
    )
    spaced = dict(out)
    spaced["src/cells/ns/mod.py"] = ("100644", b"X = 1\n")  # A namespace package (PEP 420).
    spaced["tests/test_ns.py"] = (
        "100644",
        b"from cells.ns import mod\nimport cells.ns.mod\nfrom cells.ns import X\n"
        b"from cells.nothing import mod\n",
    )
    missing = [m for m in unresolved_imports(spaced) if m.startswith("tests/test_ns.py")]
    checks["namespace package: its submodule resolves, other names and absent folders do not"] = (
        missing
        == ["tests/test_ns.py:3: from cells.ns import X", "tests/test_ns.py:4: from cells.nothing"]
    )
    # A branch merged after the move (core-fixes-m2, 18 November 2026): its new lines import
    # moved modules from their old packages, which the tree no longer holds. The map's own old
    # names say they are modules.
    merged = dict(out)
    merged["tests/test_late.py"] = (
        "100644",
        b"from cells.core import old_spec\nfrom cells.models import old_model as om\n",
    )
    late, _ = transform(merged, mp)
    checks["after the move: a from-import of a moved module by its old package is mapped"] = late[
        "tests/test_late.py"
    ][1] == (
        b"from cells.held.core import old_spec\nfrom cells.held.models import old_model as om\n"
    )


def cmd_selftest(args):
    files = {p: ("100644", t.encode()) for p, t in SELFTEST_TREE.items()}
    mp = MoveMap(SELFTEST_MAP)
    out, report = transform(files, mp)
    text = {p: d.decode() for p, (_, d) in out.items()}
    checks = {
        "moved": "src/cells/held/core/old_spec.py" in out
        and "src/cells/core/old_spec.py" not in out,
        "package files": text.get("src/cells/held/__init__.py") == '"""Held."""\n',
        "from-import module": "from cells.held.models import old_model"
        in text["src/cells/held/core/old_spec.py"],
        "docstring path": "src/cells/held/models/old_model.py"
        in text["src/cells/held/core/old_spec.py"],
        "kind id kept": 'KIND = "cells.old_spec@1"' in text["src/cells/held/core/old_spec.py"],
        "bare import and chain": "import cells.held.core.old_spec\n"
        in text["src/cells/models/keep.py"]
        and "return cells.held.core.old_spec.parse" in text["src/cells/models/keep.py"],
        "split from-import": "from cells.core import specs" in text["src/cells/models/keep.py"]
        and "from cells.held.core import old_spec" in text["src/cells/models/keep.py"]
        and "from cells.held.core import old_spec as spec" in text["src/cells/models/keep.py"],
        "comment": "# cells.held.core.old_spec.parse" in text["src/cells/models/keep.py"],
        "importlib string": '"cells.held.core.old_spec")' in text["src/cells/models/keep.py"],
        "mock target": 'mock.patch("cells.held.core.old_spec.parse")'
        in text["tests/test_old.py"],
        "paths": '"src/cells/held/core/old_spec.py"' in text["tests/test_old.py"]
        and '"held/core/old_spec.py"' in text["tests/test_old.py"],
        "entry point string": "cells.held.core.old_spec:parse"
        in text["validation/pkg/helper.py"],
        "embedded program": "from cells.held.core import old_spec as spec"
        in text["tests/test_program.py"],
        "relative import kept": text["validation/pkg/tool.py"]
        == SELFTEST_TREE["validation/pkg/tool.py"],
        "shell": "-m cells.held.core.old_spec" in text["scripts/run.sh"],
        "docs left alone": text["docs/NOTE.md"] == SELFTEST_TREE["docs/NOTE.md"],
        "imports sorted": text["src/cells/models/keep.py"].index("from cells.core import specs")
        < text["src/cells/models/keep.py"].index("from cells.held.core import old_spec"),
    }
    again, _ = transform(out, mp)
    checks["idempotent"] = again == out
    table = path_table(mp, files)["rows"]
    checks["path table"] = {
        "old": "src/cells/core/old_spec.py",
        "new": "src/cells/held/core/old_spec.py",
        "kind": "move",
        "to_legacy": False,
        "old_module": "cells.core.old_spec",
        "new_module": "cells.held.core.old_spec",
    } in table and sum(r["kind"] == "created" for r in table) == 3
    planted = dict(out)
    p = "src/cells/held/models/old_model.py"
    planted[p] = (planted[p][0], planted[p][1].replace(b"None", b"0"))
    checks["hand edit refused"] = verify(mp, files, planted)["verdict"] == "refused"
    checks["clean move holds"] = verify(mp, files, out)["verdict"] == "holds"
    extra = dict(out)
    extra["src/cells/held/models/extra.py"] = ("100644", b"X = 1\n")
    checks["extra file refused"] = verify(mp, files, extra)["verdict"] == "refused"
    pinned = dict(files)
    pinned["src/cells/models/pin.py"] = (
        "100644",
        b'P = {"src/cells/models/old_model.py": "' + b"a" * 64 + b'"}\n',
    )
    moved_pin, _ = transform(pinned, mp)
    checks["pin path rewritten, hash kept"] = (
        moved_pin["src/cells/models/pin.py"][1]
        == (b'P = {"src/cells/held/models/old_model.py": "' + b"a" * 64 + b'"}\n')
        and verify(mp, pinned, moved_pin)["verdict"] == "holds"
    )
    edited_pin = dict(moved_pin)
    edited_pin["src/cells/models/pin.py"] = (
        "100644",
        edited_pin["src/cells/models/pin.py"][1].replace(b"a" * 64, b"b" * 64),
    )
    checks["hash edit refused"] = any(
        p["why"] == "a hash literal changed" for p in verify(mp, pinned, edited_pin)["problems"]
    )
    branch = dict(files)
    branch["src/cells/models/new_on_branch.py"] = (
        "100644",
        b"from cells.core.old_spec import parse\n",
    )
    got, _ = transform(branch, mp)
    checks["branch addition rewritten"] = (
        b"from cells.held.core.old_spec import parse"
        in got["src/cells/models/new_on_branch.py"][1]
    )
    pkg_map = MoveMap(
        dict(
            SELFTEST_MAP,
            modules=[["cells.models", "cells.held.models"]],
            packages={"cells.held": ""},
        )
    )
    try:
        transform(files, pkg_map)
        checks["unlisted module in a moved package refused"] = False
    except Refused:
        checks["unlisted module in a moved package refused"] = True
    # D188 R1 created src/cells/held/__init__.py with the map's exact text: an existing package
    # file with the map's text is used as it is; one with other text is refused.
    existing = dict(files)
    existing["src/cells/held/__init__.py"] = ("100644", b'"""Held."""\n')
    try:
        got, rep = transform(existing, mp)
        checks["an existing identical package file is used, not created"] = (
            "src/cells/held/__init__.py" not in rep["created"]
            and got["src/cells/held/__init__.py"] == existing["src/cells/held/__init__.py"]
            and "src/cells/held/core/old_spec.py" in got
        )
    except Refused:
        checks["an existing identical package file is used, not created"] = False
    existing["src/cells/held/__init__.py"] = ("100644", b'"""Other text."""\n')
    try:
        transform(existing, mp)
        checks["an existing package file with other text is refused"] = False
    except Refused:
        checks["an existing package file with other text is refused"] = True
    absent = MoveMap(
        dict(SELFTEST_MAP, modules=[["cells.core.nowhere", "cells.held.core.nowhere"]])
    )
    try:
        transform(files, absent)
        checks["absent module refused"] = False
    except Refused:
        checks["absent module refused"] = True
    hazard = dict(files)
    hazard["src/cells/models/dynamic.py"] = (
        "100644",
        b'import importlib\nF = importlib.import_module("cells.core." + "old_spec")\n',
    )
    _, rep = transform(hazard, mp)
    checks["prefix hazard found"] = any(h["kind"] == "prefix" for h in rep["hazards"])
    rel = {
        "src/cells/__init__.py": "",
        "src/cells/a/__init__.py": "",
        "src/cells/a/m.py": "from . import n\nfrom .n import f\n",
        "src/cells/a/n.py": "def f():\n    pass\n",
    }
    rel = {p: ("100644", t.encode()) for p, t in rel.items()}
    rel_map = MoveMap(
        dict(
            kind=MAP_KIND,
            move="rel",
            modules=[["cells.a.m", "cells.b.m"]],
            packages={"cells.b": ""},
        )
    )
    got, _ = transform(rel, rel_map)
    checks["relative import made absolute when its file moves"] = (
        got["src/cells/b/m.py"][1].decode() == "from cells.a import n\nfrom cells.a.n import f\n"
    )
    # cells.modules (D195's surface) is reserved: a map that moves into or out of it, or creates a
    # package there, is refused; a tree that already holds it is moved around it.
    reserved = {
        "into it": dict(modules=[["cells.core.old_spec", "cells.modules.old_spec"]], packages={}),
        "out of it": dict(modules=[["cells.modules.surface", "cells.core.surface"]], packages={}),
        "a package there": dict(SELFTEST_MAP, packages={"cells.modules.extra": ""}),
    }
    refused = []
    for label, doc in reserved.items():
        try:
            MoveMap(dict(SELFTEST_MAP, **doc))
        except Refused as error:
            refused.append(label if "reserved" in str(error) else None)
    surface = dict(files)
    surface["src/cells/modules/__init__.py"] = (
        "100644",
        b'"""Provisional surface."""\n\nfrom cells.core.old_spec import parse\n',
    )
    got, _ = transform(surface, mp)
    checks["cells.modules reserved: refused into it, out of it and as a new package"] = (
        refused == list(reserved)
    )
    checks["cells.modules reserved: an existing surface stays in place, its imports rewritten"] = (
        got["src/cells/modules/__init__.py"][1]
        == b'"""Provisional surface."""\n\nfrom cells.held.core.old_spec import parse\n'
    )
    # A dissolved package (D188 move 2: processes/): its modules move to different homes, its
    # package file (a docstring only) is removed, and nothing may name the package afterwards.
    pkg_tree = {
        "src/cells/__init__.py": "",
        "src/cells/old/__init__.py": '"""Old laws."""\n',
        "src/cells/old/a.py": "A = 1\n",
        "src/cells/old/b.py": "B = 2\n",
        "tests/test_dissolve.py": (
            "from cells.old import a, b\n\n"
            'PROGRAM = "import sys\\nfrom cells.old import a\\n"\n\n\n'
            "def test_it():\n    assert a.A + b.B == 3\n"
        ),
    }
    pkg_tree = {p: ("100644", t.encode()) for p, t in pkg_tree.items()}
    pkg_doc = dict(
        kind=MAP_KIND,
        move="dissolve",
        modules=[["cells.old.a", "cells.new.a"], ["cells.old.b", "cells.other.b"]],
        packages={"cells.new": '"""New laws."""\n', "cells.other": ""},
        dissolve=["cells.old"],
    )
    dmap = MoveMap(pkg_doc)
    got, rep = transform(pkg_tree, dmap)
    t = got["tests/test_dissolve.py"][1].decode()
    checks["dissolve: the package file goes, its modules move apart, imports split"] = (
        "src/cells/old/__init__.py" not in got
        and rep["dissolved"] == ["src/cells/old/__init__.py"]
        and got["src/cells/new/__init__.py"][1] == b'"""New laws."""\n'
        and "from cells.new import a\nfrom cells.other import b\n" in t
        and "\\nfrom cells.new import a\\n" in t
        and verify(dmap, pkg_tree, got)["verdict"] == "holds"
        and transform(got, dmap)[0] == got
        and {"old": "src/cells/old/__init__.py", "new": None, "kind": "dissolved"}.items()
        <= next(r for r in path_table(dmap, pkg_tree)["rows"] if r["kind"] == "dissolved").items()
    )
    refusals = []
    for label, change in (
        ("a module left", dict(modules=[["cells.old.a", "cells.new.a"]])),
        ("a name in its file", None),
    ):
        tree = dict(pkg_tree)
        if change is None:
            tree["src/cells/old/__init__.py"] = ("100644", b'"""Old."""\n\nX = 1\n')
        try:
            transform(tree, MoveMap(dict(pkg_doc, **(change or {}))))
            refusals.append(None)
        except Refused:
            refusals.append(label)
    stale = dict(got)
    stale["tests/test_stale.py"] = ("100644", b'NAME = "cells.old"\n')
    checks["dissolve: a module left, a name in its file and a stale reference are refused"] = (
        refusals == ["a module left", "a name in its file"]
        and any(
            "old reference left" in p["why"] and "cells.old" in p["why"]
            for p in verify(
                dmap, dict(pkg_tree, **{"tests/test_stale.py": stale["tests/test_stale.py"]}), stale
            )["problems"]
        )
    )
    # D188 move 2: a reviewed hazard file that the map moves keeps its review at its new path, so
    # a second application (and a branch's own, after the move) is not refused for it.
    hz_tree = {
        "src/cells/__init__.py": "",
        "src/cells/core/__init__.py": "",
        "src/cells/core/hz.py": 'NAME = "cells.core." + "y"\n',
        "src/cells/core/y.py": "Y = 1\n",
    }
    hz_tree = {p: ("100644", t.encode()) for p, t in hz_tree.items()}
    hz_map = MoveMap(
        dict(
            kind=MAP_KIND,
            move="hz",
            modules=[["cells.core.hz", "cells.other.hz"], ["cells.core.y", "cells.other.y"]],
            packages={"cells.other": ""},
            reviewed=[dict(path="src/cells/core/hz.py", reason="planted: a prefix, reviewed")],
        )
    )
    first, rep1 = transform(hz_tree, hz_map)
    _, rep2 = transform(first, hz_map)
    real_moved_path = _moved_path
    try:
        globals()["_moved_path"] = lambda path, mp: path  # The planted control: no mapping.
        planted_reaching = _hazards_reaching(rep2, hz_map)
    finally:
        globals()["_moved_path"] = real_moved_path
    checks["a reviewed file that moves keeps its review at its new path (second application)"] = (
        any(h["file"] == "src/cells/core/hz.py" for h in rep1["hazards"])
        and any(h["file"] == "src/cells/other/hz.py" for h in rep2["hazards"])
        and not _hazards_reaching(rep1, hz_map)
        and not _hazards_reaching(rep2, hz_map)
        and bool(planted_reaching)
    )
    # D188 move 2: a from-import in free text (a program string with escapes, a comment) maps
    # each moved submodule by its own new home, not by its package's.
    escaped = dict(files)
    escaped["tests/test_escaped.py"] = (
        "100644",
        b'PROGRAM = "import sys\\nfrom cells.core import old_spec, specs\\n"\n'
        b'LINES = ("import sys\\n" "from cells.core import old_spec as o\\n")\n'
        b"# from cells.core import old_spec\n",
    )
    got, _ = transform(escaped, mp)
    t = got["tests/test_escaped.py"][1].decode()
    checks["text from-import: a moved submodule by its own home, the rest by the package's"] = (
        "import sys\\nfrom cells.held.core import old_spec; from cells.core import specs\\n" in t
        and '"from cells.held.core import old_spec as o\\n"' in t
        and "# from cells.held.core import old_spec\n" in t
        and transform(got, mp)[0] == got
    )
    split = {
        "src/cells/__init__.py": "",
        "src/cells/core/__init__.py": '"""Core."""\n',
        "src/cells/core/devices.py": "X = 1\n",
        "src/cells/core/specs.py": "Y = 2\n",
        "src/cells/models/__init__.py": "",
        "src/cells/models/registry.py": "Z = 3\n",
        "tests/test_split.py": (
            'A = "from cells.core import devices\\n"\n'
            'B = "from cells.core import devices, specs\\n"\n'
            'C = "from cells.models import registry as r\\n"\n'
            'D = "from cells.models import registry\\n"\n'
        ),
    }
    split = {p: ("100644", t.encode()) for p, t in split.items()}
    split_map = MoveMap(
        dict(
            kind=MAP_KIND,
            move="split",
            modules=[
                ["cells.core", "cells.definitions"],
                ["cells.core.devices", "cells.execution.devices"],
                ["cells.core.specs", "cells.definitions.specs"],
                ["cells.models.registry", "cells.registry.models"],
            ],
            packages={"cells.execution": "", "cells.registry": ""},
        )
    )
    got, _ = transform(split, split_map)
    t = got["tests/test_split.py"][1].decode()
    checks["text from-import: a package file and its submodules re-homed apart, a leaf renamed"] = (
        'A = "from cells.execution import devices\\n"' in t
        and 'B = "from cells.execution import devices; from cells.definitions import specs\\n"' in t
        and 'C = "from cells.registry import models as r\\n"' in t
        and 'D = "from cells.registry import models as registry\\n"' in t
        and transform(got, split_map)[0] == got
        # The planted error: the dotted rule alone maps the package, not the submodule.
        and _rewrite_dotted("from cells.core import devices", split_map)
        == "from cells.definitions import devices"
    )
    base_ids = [
        "tests/test_old.py::test_old",
        "tests/test_pin.py::test_pin[src/cells/core/old_spec.py-aaaa]",
        "tests/test_pin.py::test_pin[core/old_spec.py]",
        "tests/test_mod.py::test_mod[cells.models.old_model]",
        "tests/test_keep.py::test_keep[src/cells/core/specs.py]",
    ]
    head_ids = [
        "tests/test_old.py::test_old",
        "tests/test_pin.py::test_pin[src/cells/held/core/old_spec.py-aaaa]",
        "tests/test_pin.py::test_pin[held/core/old_spec.py]",
        "tests/test_mod.py::test_mod[cells.held.models.old_model]",
        "tests/test_keep.py::test_keep[src/cells/core/specs.py]",
    ]
    same = compare_ids(mp, base_ids, head_ids)
    checks["ids: a moved path or module in a parametrization is the same test"] = (
        not (same["collisions"] or same["missing_in_head"] or same["new_in_head"])
        and len(same["renamed_by_the_map"]) == 3
    )
    renamed = compare_ids(mp, base_ids, [*head_ids[:4], "tests/test_keep.py::test_kept"])
    checks["ids: a renamed test is caught"] = renamed["missing_in_head"] == [
        base_ids[4]
    ] and renamed["new_in_head"] == ["tests/test_keep.py::test_kept"]
    dropped = compare_ids(mp, base_ids, head_ids[1:])
    checks["ids: a dropped test is caught"] = dropped["missing_in_head"] == [base_ids[0]]
    stale = compare_ids(mp, base_ids, [*head_ids[:3], base_ids[3], head_ids[4]])
    checks["ids: an old module name left in a head ID is caught"] = stale["new_in_head"] == [
        base_ids[3]
    ]
    collide = compare_ids(
        mp,
        [base_ids[1], "tests/test_pin.py::test_pin[src/cells/held/core/old_spec.py-aaaa]"],
        [head_ids[1]],
    )
    checks["ids: two tests that the map makes one are caught"] = len(collide["collisions"]) == 1
    _selftest_kept_lines(mp, files, checks)
    failed = [k for k, v in checks.items() if not v]
    print(json.dumps(dict(checks=len(checks), failed=failed), indent=1))
    if failed and args.verbose:
        for p in sorted(text):
            print(f"== {p}\n{text[p]}")
    return 1 if failed else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "scan", "apply", "verify", "table"):
        p = sub.add_parser(name)
        p.add_argument("map")
        p.add_argument(
            "--tree", default=str(ROOT), help="the checkout to work on (default: this one)"
        )
        if name in ("scan", "table"):
            p.add_argument("--out")
        if name == "apply":
            p.add_argument("--stage", action="store_true", help="git add the scope afterwards")
            p.add_argument("--allow-hazards", action="store_true")
        if name == "verify":
            p.add_argument("--base", required=True)
            p.add_argument("--head", required=True)
            p.add_argument("--out")
    i = sub.add_parser("ids", help="the collected-ID gate through the map")
    i.add_argument("map")
    i.add_argument("base_ids", help="one test ID per line (pytest --collect-only -q, :: lines)")
    i.add_argument("head_ids")
    i.add_argument("--base-log", help="the base's collection log (its ERROR lines)")
    i.add_argument("--head-log")
    i.add_argument("--out")
    s = sub.add_parser("selftest")
    s.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    try:
        return dict(
            check=cmd_check,
            ids=cmd_ids,
            table=cmd_table,
            scan=cmd_scan,
            apply=cmd_apply,
            verify=cmd_verify,
            selftest=cmd_selftest,
        )[args.command](args)
    except Refused as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
