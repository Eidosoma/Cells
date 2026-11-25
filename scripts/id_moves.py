"""The scripted ID rename (D345, D346, D371, D383; docs/ID_HIERARCHY_DESIGN.md §5): the table, the
hazard scan, the token rewriter, the verifier and the collected-ID map. Shaped as D188's
scripts/source_moves.py is, and built on its git helpers.

Every live piece's ID becomes `cells.<family>.<name>@major`. Names and majors are kept, interface
and schema IDs keep their names, and an old ID is refused at parse. Everything under src/cells is
live.

**The data** (scripts/moves/):
- `id-rename-choices.json`, edited by hand: the seeds (the IDs that no registry holds, each a live
  module's constant or the keys of a lookup table, with its family), the IDs kept with their
  reasons, the hash-pinned files with their choices, the frozen rules' exceptions, the plants'
  families, the test IDs the ids rule keeps and the reviewed hazards. The family words are not in
  it: registry/ids.py is their only home;
- the map, written by `table`: its rows, the kept list and what the rewriter leaves alone;
- the frozen list, written by `frozen` at a given base.

**The table** has three sources (§5): the registries, loaded in a process of their own as the
manifest loads them; the seeds; and the reconciliation of every `name@major` in scope. It is
refused while a live ID is unplaced: one that live src holds (as a literal or, by a census of the
loaded modules, as a computed value), or that a live model's JSON definition spells, and that
neither the table nor the kept list holds. It is refused while registry/ids.py lacks a row's word,
and while a plant's family is not seen, unless --rehearsal, which marks the map as not final.

**A choice that the tree has overtaken is refused, by `check` and by `table`:** a part of the
choices that the tool does not read; a seed whose constant or table is gone, whose IDs a registry
row or another seed holds, or whose family is no word; a kept ID that nothing live spells, or that
a row, an interface or another entry holds; a plant that no file spells, or that a row holds; a
pin that its file no longer quotes; a path that no tracked file has, as an entry's own, as a pattern
or cited in a reason; and a family word that registry/ids.py gives two places, as a merge can. A
registry's row never overrides a choice in silence.

**The plants** (D371 Q8) are the pieces a test or a driver declares for itself. Each gets the
three-part ID of its own family, in its own files only: the family comes from the type or the
helper that declares it, or from the choices. The engine's table does not hold them.

**The rewriter** maps whole tokens, longest match, and keeps every other byte:
- it skips a token after `/` (the page rule's) and every line marked `id-moves: keep` (in Python a
  comment, in a shell or TOML file anywhere on the line);
- the page rule renames docs/library/<namespace>/<section>/<name>@<major>.md to
  <family>.<name>@<major>.md in its folder, and the path strings in scope that name such a page;
- in a record of test IDs it maps the test IDs only, by the `ids` rule: a token there may follow
  `-`, which joins a test's parameters;
- it writes src/cells/registry/renamed_ids.py, {old: new} for every old spelling.
No formatting and no hand edit: `rewrap` wraps the lines the move makes too long, for a commit of
its own. It cuts a plain string that fills a line, where its value stays the same, and then lets
ruff format the lines around it; `rewrapped` requires the same AST and the same comments.
`apply --paths` is the same token rule on a lane's own files, outside the scope; --suffix .md adds
its pages.

**Its scope** is the tracked Python, JSON, shell and TOML files under src/, tests/, validation/,
scripts/, examples/ and configs/. Left alone: the frozen files, the pinned files whose choice is to
leave them, the files listed under keep, scripts/moves/, this file, renamed_ids.py and everything
outside those folders.

**The scan** names every place that reads or makes an ID other than as a whole token: computed, cut,
split over literals, tested or matched in part (by a literal, or through a name, a loop, another
file's constant or an argument), inside a path or a file name, in an expected message, sorted by,
pinned by a hash. A hazard stands until the tree no longer holds it or a review in the choices gives
the reason why it is none, and `apply` refuses while one stands. Beside them it lists the live
readers of the files the move leaves (and whether they name the table of renamed IDs: one that does
not may read no ID, or translate in its own way), what frozen code does with part of an ID, and the
paths outside the tree that code names.

**The verifier** replays the map on the base commit's tracked files in memory and requires the head
to equal the result, byte for byte and mode for mode. It also requires that a second application
changes nothing, that no hash literal changed, that each string's decoded value changed by the
token rule and nothing else (Python by AST, JSON by its values), and that no old spelling is left
in scope: as a token, or in any other form (after `-`, after `/`, after an escape's letter, with an
escaped dot, inside a longer token). `leftovers` is that last rule on a tree's files, for a guard
that stays in force after the move (H1b's).

Usage (PYTHONPATH=src:. with the venv's Python, from a checkout):
  python scripts/id_moves.py check
  python scripts/id_moves.py table [--rehearsal] [--out MAP] [--tsv FILE] [--compare TSV]
  python scripts/id_moves.py frozen --base REV [--out TSV] [--compare TSV]
  python scripts/id_moves.py scan [--out JSON] [--by-hand TSV] [--skipped JSON]
  python scripts/id_moves.py apply [--stage] [--paths PATH ... [--suffix .md]]
  python scripts/id_moves.py verify --base REV --head REV [--out JSON]
  python scripts/id_moves.py ids BASE_IDS HEAD_IDS [--base-log LOG --head-log LOG] [--out JSON]
      [--declare FOLDER, the lists for the gate's own ID step]
  python scripts/id_moves.py rewrap --base REV [--out JSON]
  python scripts/id_moves.py rewrapped --base REV --head REV
  python scripts/id_moves.py selftest
All but ids and selftest take --tree DIR, the checkout to work on (default: this one); --choices,
--map and --frozen name other data files. Exit status: 0 ok, 1 a check failed, 2 refused.

The order at the base: `frozen --out`, `table`, `frozen --lists` for the owners; commit the list and
the map; `scan`; `apply --stage`, a commit that holds nothing else; `verify`; `ids` on the collected
test IDs of both; `rewrap`, its own commit; `rewrapped`.
"""

import argparse
import ast
import contextlib
import difflib
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import tokenize
from collections import Counter, defaultdict
from fnmatch import fnmatchcase
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from source_moves import (  # noqa: E402  (D188's tool, in this folder)
    RUFF,
    Refused,
    compare,
    git,
    tree_at,
    worktree_files,
)

ROOT = Path(__file__).resolve().parents[1]
CHOICES_KIND = "cells.id_moves.choices@1"
MAP_KIND = "cells.id_moves.map@1"
REPORT_KIND = "cells.id_moves.report@1"
CHOICES = "scripts/moves/id-rename-choices.json"
MAP = "scripts/moves/id-rename-map.json"
FROZEN = "scripts/moves/id-rename-frozen.tsv"
RENAMED = "src/cells/registry/renamed_ids.py"
SELF = ("scripts/id_moves.py", "scripts/moves/")
KEEP_MARK = "id-moves: keep"
NAMESPACE = "cells"
LIVE = "src/cells/"

WORD = r"[A-Za-z][A-Za-z0-9_]*"
_ID = rf"(?:{WORD}\.)*{WORD}@[1-9][0-9]*"
ID = re.compile(_ID)  # With fullmatch: a whole ID, in any namespace.
TOKEN = re.compile(rf"(?<![A-Za-z0-9_.@-])({_ID})(?![A-Za-z0-9_])")
# The ids rule's token: `-` joins a test's parameters, so a token may follow it.
TEST_TOKEN = re.compile(rf"(?<![A-Za-z0-9_.@])({_ID})(?![A-Za-z0-9_])")
# A name and its major whatever stands before it: what the token rule may not see.
LOOSE = re.compile(rf"(?<![A-Za-z0-9_])({WORD}@[1-9][0-9]*)(?![A-Za-z0-9_])")
# An ID right after an escape's letter (a pattern's \\b, a string's \\n): no token starts there.
ESCAPED = re.compile(rf"\\[A-Za-z]((?:{WORD}\.)*{WORD}@[1-9][0-9]*)(?![A-Za-z0-9_])")
NEW = re.compile(r"[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*\.[a-z][A-Za-z0-9_]*@[1-9][0-9]*")
# A recorded test ID, as a JSON string's content: no escape can stand in one that holds an ID.
TEST_ID = re.compile(r'(?<=")((?:[A-Za-z0-9_./-]+::)*test_[A-Za-z0-9_]+(?:\[[^"\\]*\])?)(?=")')
SECTIONS = ("laws", "kinds", "operators", "models")
LIBRARY = "docs/library/"
PAGE = re.compile(
    r"(?<![\w.-])((?:docs/library/)?)([a-z][a-z0-9_]*)/("
    + "|".join(SECTIONS)
    + rf")/({WORD}@[1-9][0-9]*)(?=\.md(?![\w-]))"
)
HASH = re.compile(rb"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")
HEX = re.compile(r"(?<![0-9A-Za-z])[0-9a-f]{12,64}(?![0-9A-Za-z])")


# ------------------------------------------------------------------ IDs


def qualified(identifier):
    """The namespaced form of an old ID: a bare one is in cells (D185)."""
    return identifier if "." in identifier.split("@", 1)[0] else f"{NAMESPACE}.{identifier}"


def bare(identifier):
    """An ID without the cells namespace."""
    return identifier.removeprefix(NAMESPACE + ".")


def new_id(old, family):
    namespace, rest = qualified(old).split(".", 1)
    return f"{namespace}.{family}.{rest}"


def spellings(old):
    """Every old spelling of a piece: a cells piece is spelled bare and namespaced."""
    key = qualified(old)
    return sorted({key, bare(key), old})


# ------------------------------------------------------------------ files in scope


def in_scope(path, choices_scope):
    dirs, suffixes = tuple(choices_scope["dirs"]), tuple(choices_scope["suffixes"])
    return path.startswith(dirs) and path.endswith(suffixes)


def scope_of(path):
    return path.split("/")[0]


def text_of(data):
    """The text of a file's bytes, or None where it is not UTF-8."""
    try:
        return data.decode()
    except UnicodeDecodeError:
        return None


def lines_of(text):
    """The text's lines without their newlines, splitting on newlines only (a carriage return, a
    form feed or a Unicode separator stays in its line), so joining them gives the text back."""
    return text.split("\n")


def line_of(text, offset):
    return text.count("\n", 0, offset) + 1


def kept_lines(text, python):
    """The lines (from 1) marked to keep: in Python those with a comment holding KEEP_MARK, in any
    other text those holding it anywhere."""
    if KEEP_MARK not in text:
        return set()
    if not python:
        return {i for i, line in enumerate(lines_of(text), 1) if KEEP_MARK in line}
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError):
        return set()
    return {t.start[0] for t in tokens if t.type == tokenize.COMMENT and KEEP_MARK in t.string}


# ------------------------------------------------------------------ the choices and the map


def load_json(path, kind):
    try:
        doc = json.loads(Path(path).read_text())
    except (OSError, ValueError) as error:
        raise Refused(f"{path}: {error}") from error
    if not isinstance(doc, dict) or doc.get("kind") != kind:
        raise Refused(f"{path}: its kind is not {kind}")
    return doc


# The parts of a choices file: those every one holds, and those it may hold.
CHOICE_PARTS = ("kind", "move", "scope", "seeds", "keep", "pinned", "frozen", "plants", "reviewed")
MORE_PARTS = ("description", "ids_kept")
SEED_KEYS = {"module", "name", "family", "keys", "piece", "named_in", "ruling", "note"}


def check_choices(doc):
    """Why a choices file cannot be used (empty: it can), read alone."""
    out = [f"no part {k!r}" for k in CHOICE_PARTS if k not in doc]
    out += [f"the tool reads no part {k!r}" for k in doc if k not in (*CHOICE_PARTS, *MORE_PARTS)]
    if out:
        return out
    for row in doc["seeds"]:
        where = f"seed {row.get('module')}.{row.get('name')}"
        out += [f"{where}: no {k}" for k in ("module", "name", "family") if k not in row]
        out += [f"{where}: the tool reads no {k!r}" for k in sorted(set(row) - SEED_KEYS)]
    for row in doc["pinned"]:
        if row["choice"] not in row["choices"]:
            out.append(f"{row['path']}: {row['choice']!r} is not one of {row['choices']}")
    return out


def load_choices(path):
    doc = load_json(path, CHOICES_KIND)
    problems = check_choices(doc)
    if problems:
        raise Refused(f"{path}: " + "; ".join(problems))
    return doc


def read_frozen(path):
    """{path: [[rule, reason, owner], ...]} of a frozen list (one tab-separated line for each
    rule that holds a file); empty where there is no such file."""
    out = defaultdict(list)
    if path and Path(path).is_file():
        for line in Path(path).read_text().splitlines():
            if line and not line.startswith("#"):
                name, *rest = line.split("\t")
                out[name].append(rest)
    return dict(out)


class Map:
    """The rename: {old spelling: new ID} and what the rewriter leaves alone."""

    def __init__(self, doc, frozen=None):
        if doc.get("kind") != MAP_KIND:
            raise Refused(f"the map's kind is not {MAP_KIND}")
        self.doc, self.final = doc, doc["final"]
        self.rows = doc["rows"]
        self.new = {}
        for row in self.rows:
            for old in row["old"]:
                if self.new.setdefault(old, row["new"]) != row["new"]:
                    raise Refused(f"{old} is renamed to both {self.new[old]} and {row['new']}")
        twice = set(self.new) & {row["new"] for row in self.rows}
        if twice:
            raise Refused(f"an old spelling is also a new ID: {sorted(twice)[:3]}")
        self.names = defaultdict(set)  # A name and its major -> its new IDs.
        for old, new in self.new.items():
            self.names[old.rsplit(".", 1)[-1]].add(new)
        self.news = set(self.new.values())
        self.page_names = {new.split(".", 1)[1] for new in self.news}
        self.plants = defaultdict(dict)  # {path: {old: new}}: a plant is renamed in its own files.
        for row in doc.get("plants", ()):
            for path in row["files"]:
                self.plants[path].update(dict.fromkeys(row["old"], row["new"]))
        self.tables = {}
        self.scope = doc["scope"]
        self.test_ids = set(self.scope["test_ids"])
        self.frozen = dict(frozen or {})
        self.left = dict(doc["left"])  # {path: why}: the pinned and keep choices.

    def table(self, path):
        """{old: new} of one file: the rows, and the plants that the file declares or names."""
        if path not in self.plants:
            return self.new
        if path not in self.tables:
            self.tables[path] = {**self.new, **self.plants[path]}
        return self.tables[path]

    # -------------------------------------------------------------- what is left alone

    def excluded(self, path):
        """Why the rewriter leaves a file alone, or None."""
        if not in_scope(path, self.scope):
            return "outside the scope"
        if path.startswith(SELF):
            return "the tool's own"
        if path == RENAMED:
            return "holds old spellings by design"
        if path in self.frozen:
            return "frozen"
        return self.left.get(path)

    # -------------------------------------------------------------- the token and page rules

    def tokens(self, line, found=None, token=TOKEN, path=""):
        """One line's old spellings, whole tokens, longest match, none after `/`."""
        if "@" not in line:
            return line
        table = self.table(path)

        def sub(m):
            new = table.get(m[1])
            if new is None or line[m.start() - 1 : m.start()] == "/":
                return m[0]
            if found is not None:
                found.append((m[1], new))
            return new

        return token.sub(sub, line)

    def pages(self, line, found=None, path=""):
        """The library page paths in one line, whose pages the page rule renames."""
        if "@" not in line or ".md" not in line:
            return line

        def sub(m):
            new = self.page_name(m[2], m[4], path)
            if new is None:
                return m[0]
            if found is not None:
                found.append((m[0], f"{m[1]}{m[2]}/{m[3]}/{new}"))
            return f"{m[1]}{m[2]}/{m[3]}/{new}"

        return PAGE.sub(sub, line)

    def page_name(self, namespace, rest, path=""):
        """A page's new name, `<family>.<name>@<major>`, from its folder's namespace, or None."""
        new = self.table(path).get(f"{namespace}.{rest}")
        return None if new is None else new.split(".", 1)[1]

    def page_path(self, path):
        """Where the page rule moves a tracked file (itself where it moves nothing)."""
        m = PAGE.match(path) if path.startswith(LIBRARY) else None
        if m is None or path[m.end() :] != ".md":
            return path
        new = self.page_name(m[2], m[4])
        return path if new is None else f"{m[1]}{m[2]}/{m[3]}/{new}.md"

    def line(self, line, found=None, token=TOKEN, path=""):
        return self.pages(self.tokens(line, found, token, path), found, path)

    def test_id(self, test_id):
        """A collected test ID through the map: the ids rule, with its file's plants."""
        return self.line(test_id, None, TEST_TOKEN, test_id.split("::")[0])

    def text(self, path, text, found=None):
        """A file's text through the rules, its kept lines as they are."""
        if path in self.test_ids:
            return TEST_ID.sub(lambda m: self.record_id(m[0], found), text)
        if "@" not in text:
            return text
        kept = kept_lines(text, path.endswith(".py"))
        return "\n".join(
            line if i in kept else self.line(line, found, TOKEN, path)
            for i, line in enumerate(lines_of(text), 1)
        )

    def record_id(self, test_id, found):
        new = self.test_id(test_id)
        if new != test_id and found is not None:
            found.append((test_id, new))
        return new

    # -------------------------------------------------------------- what is left over

    def left_over(self, path, text):
        """[(line, kind, text)]: every old spelling in a text in scope, as a token or in another
        form (after `-`, after an escaped dot, after `/`), less the kept lines and a test-ID
        record's other text."""
        out = []
        if "@" not in text:
            return out
        kept = kept_lines(text, path.endswith(".py"))
        for i, line in enumerate(lines_of(text), 1):
            if "@" not in line or i in kept:
                continue
            if path in self.test_ids:
                parts = [m[0] for m in TEST_ID.finditer(line)]
                found = [w for p in parts for w in self._over(p, TEST_TOKEN, "")]
            else:
                found = self._over(line, TOKEN, path)
            out += [(i, kind, word) for kind, word in found]
        return out

    def _over(self, line, token, path):
        out = []
        seen = set()
        table = self.table(path)
        for m in token.finditer(line):
            seen.add(m.end())
            if m[1] in table:
                if line[m.start() - 1 : m.start()] != "/" or not self._in_page(line, m):
                    out.append(("token", m[1]))
            elif "." in m[1] and m[1] not in self.news and m[1].rsplit(".", 1)[1] in self.names:
                if line[m.start() - 1 : m.start()] != "/" or m[1] not in self.page_names:
                    out.append(("longer token", m[1]))  # Not a renamed page's own name.
        for m in LOOSE.finditer(line):
            if m[1] not in self.names or m.end() in seen:
                continue
            if any(line.endswith(new[: -len(m[1])], 0, m.start()) for new in self.names[m[1]]):
                continue  # The tail of a new ID that the token cannot start at.
            before = line[max(0, m.start() - 1) : m.start()]
            out.append((f"after {before!r}", line[max(0, m.start() - 24) : m.end() + 6]))
        for m in ESCAPED.finditer(line):
            if m[1] in table:
                out.append(("after an escape", line[max(0, m.start() - 24) : m.end() + 6]))
        return out

    def _in_page(self, line, m):
        """Whether a token after `/` is a page path's, of a page the map does not rename."""
        return any(
            p.start() <= m.start() < p.end() and self.page_name(p[2], p[4]) is None
            for p in PAGE.finditer(line)
        )


def load_map(path, frozen=None):
    return Map(load_json(path, MAP_KIND), frozen)


RENAMED_HEAD = '''\
"""The renamed IDs (D345): {old spelling: new ID}, so that an old one is refused by naming its new
one. Generated by the rename's tool, scripts/id_moves.py; never edited by hand."""

RENAMED = {
'''


def render_renamed(mp):
    """renamed_ids.py: a docstring and one dict literal."""
    rows = []
    for old, new in sorted(mp.new.items()):
        line = f'    "{old}": "{new}",'
        rows.append(line if len(line) <= 100 else line + "  # noqa: E501")
    return (RENAMED_HEAD + "\n".join([*rows, "}"]) + "\n").encode()


# ------------------------------------------------------------------ the tree transform


def transform(files, mp, renamed=True):
    """The tree after the map: (files, report). files is {path: (mode, bytes)} of tracked files."""
    out, report = {}, dict(files={}, pages=[], not_text=[], left={})
    for path, (mode, data) in files.items():
        new_path = mp.page_path(path)
        if new_path != path:
            if new_path in files:
                raise Refused(f"{path}: both it and {new_path} exist")
            report["pages"].append((path, new_path))
        if in_scope(path, mp.scope) and b"@" in data:
            why, text, found = mp.excluded(path), text_of(data), []
            if text is None:
                report["not_text"].append(path)
            elif why is None:
                new = mp.text(path, text, found)
                if new != text:
                    report["files"][path] = found
                    data = new.encode()
            elif not path.startswith(SELF) and path != RENAMED:
                mp.text(path, text, found)
                if found:  # A file left alone that holds old spellings.
                    report["left"][path] = (why, len(found))
        out[new_path] = (mode, data)
    if renamed:
        mode = files.get(RENAMED, ("100644", b""))[0]
        out[RENAMED] = (mode, render_renamed(mp))
    return out, report


def decoded(path, text):
    """The decoded strings of a file, in order: a Python file's constants by AST, a JSON file's
    keys and values. None where it cannot be parsed."""
    try:
        if path.endswith(".py"):
            return [
                n.value if isinstance(n.value, str) else n.value.decode("latin-1")
                for n in ast.walk(ast.parse(text))
                if isinstance(n, ast.Constant) and isinstance(n.value, (str, bytes))
            ]
        return list(json_strings(json.loads(text)))
    except (SyntaxError, ValueError):
        return None


def json_strings(value):
    if isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from json_strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from json_strings(v)
    elif isinstance(value, str):
        yield value


def decoded_problems(path, before, after, mp):
    """Where a file's decoded strings did not change by the rules and by nothing else: an ID after
    an escape, or split over two literals, which the text rule cannot see; or a file that no longer
    parses. A line marked to keep is a file's own business: such a file is not checked here."""
    if not path.endswith((".py", ".json")) or path in mp.test_ids:
        return []
    if kept_lines(before, path.endswith(".py")):
        return []
    a = decoded(path, before)
    b = a if before == after else decoded(path, after)
    if a is None:
        return []
    if b is None:
        return [(path, "it no longer parses")]
    if len(a) != len(b):
        return [(path, "its strings are not the same in number")]
    out = []
    for x, y in zip(a, b, strict=True):
        want = "\n".join(mp.line(s, None, TOKEN, path) for s in lines_of(x)) if "@" in x else x
        if want != y:
            out.append((path, f"a string's value: {x[:80]!r} became {y[:80]!r}"))
    return out


def hash_edits(before, after, report):
    """Files whose 64-digit hex literals differ before and after (D187: a hash is never updated,
    by hand or by this tool)."""
    back = {new: old for old, new in report["pages"]}
    out = []
    for path, (_, data) in after.items():
        old = before.get(back.get(path, path))
        if (
            old is not None
            and old[1] != data
            and sorted(HASH.findall(old[1])) != sorted(HASH.findall(data))
        ):
            out.append((path, "a hash literal changed"))
    return out


def leftovers(files, mp):
    """[(path, line, kind, text)]: every old spelling left in scope outside the exclusions, in any
    form; what the moved tree must not hold."""
    out = []
    for path, (_, data) in sorted(files.items()):
        text = None if mp.excluded(path) or not A_MAJOR.search(data) else text_of(data)
        if text is not None:
            out += [(path, *found) for found in mp.left_over(path, text)]
    return out


def verify(mp, base, head, cwd=ROOT):
    """The replay of the map on `base` against `head`: each is a revision, or a tree's files."""
    before = base if isinstance(base, dict) else tree_at(base, cwd)
    actual = head if isinstance(head, dict) else tree_at(head, cwd)
    expected, report = transform(before, mp)
    problems = [dict(path=p, why=w) for p, w in compare(expected, actual)]
    problems += [dict(path=p, why=w) for p, w in hash_edits(before, actual, report)]
    again, _ = transform(expected, mp)
    if again != expected:
        problems.append(dict(path="*", why="a second application changes the tree"))
    for path, (_, data) in before.items():  # A file the rewriter left is checked too.
        if path.endswith((".py", ".json")) and mp.excluded(path) is None and A_MAJOR.search(data):
            old, new = text_of(data), text_of(actual.get(path, ("", b""))[1])
            if old is not None and new is not None:
                problems += [dict(path=p, why=w) for p, w in decoded_problems(path, old, new, mp)]
    problems += [
        dict(path=path, line=i, why=f"an old spelling is left ({kind}): {word}")
        for path, i, kind, word in leftovers(expected, mp)
    ]
    for path in report["not_text"]:
        if any(old.encode() in before[path][1] for old in mp.new):
            problems.append(dict(path=path, why="not UTF-8 text, and it holds an old spelling"))
    return dict(
        kind=REPORT_KIND,
        final=mp.final,
        files_rewritten=len(report["files"]),
        pages_renamed=len(report["pages"]),
        tokens=sum(map(len, report["files"].values())),
        lines=sum(
            a != b
            for p in report["files"]
            for a, b in zip(
                lines_of(text_of(before[p][1])), lines_of(text_of(expected[p][1])), strict=True
            )
        ),
        left_alone=dict(Counter(why for why, _ in report["left"].values())),
        problems=problems,
        verdict="holds" if not problems else "refused",
    )


# ------------------------------------------------------------------ the engine, in its own process


def engine_dump(tree, keys=()):
    """What the tree's engine holds, read in a process of its own with the tree's src first on its
    path: the registries as the manifest loads them, the interfaces, the family words and the
    grammar of registry/ids.py, the keys of each named lookup table (None where it is gone), the
    law types by name, and the census: every `name@major` reachable from a module's namespace, so a
    computed ID is seen too."""
    env = dict(os.environ, PYTHONPATH=f"{tree}/src:{tree}", PYTHONDONTWRITEBYTECODE="1")
    env.setdefault("JAX_PLATFORMS", "cpu")
    proc = subprocess.run(
        [sys.executable, "-B", str(Path(__file__).resolve()), "_engine", "--tree", str(tree)],
        input=json.dumps(dict(keys=[list(k) for k in keys])),
        capture_output=True,
        text=True,
        cwd=str(tree),
        env=env,
    )
    if proc.returncode or not proc.stdout:
        raise Refused(f"the tree's engine does not load: {proc.stderr.strip()[-600:]}")
    return json.loads(proc.stdout)


def cmd_engine(args):
    """The child process of engine_dump."""
    import dataclasses
    import importlib
    import pkgutil
    import types
    from collections.abc import Mapping

    asked = json.loads(sys.stdin.read())
    real, sys.stdout = sys.stdout, sys.stderr  # Nothing but the answer on stdout.
    import cells
    from cells.registry import declarations, ids, kind_registry, model_table
    from cells.registry import laws as law_registry
    from cells.registry import operators as operator_registry

    if not Path(cells.__file__).resolve().is_relative_to(Path(args.tree).resolve()):
        raise SystemExit(f"cells is {cells.__file__}, not the tree's")
    laws, kinds = law_registry.active(), kind_registry.active()
    operators = operator_registry.active()
    out = dict(
        laws=[
            dict(
                declared=law.law_id,
                interface=type(law).interface,
                host=law.host,
                module=laws.module(key),
            )
            for key, law in laws._laws.items()
        ],
        kinds=[dict(declared=k.kind_id, model_key=m) for m, k in kinds.model_keys().items()],
        operators=[
            dict(declared=op.LAW_ID, module=type(op).__module__) for op in operators.operators()
        ],
        family_operators=[
            dict(
                declared=d.operator_id,
                interface=type(d).interface,
                host=d.host,
                module=operators.module(d.operator_id),
            )
            for d in operators.family_operators()
        ],
        models=[
            dict(declared=key, type=m.type, module=m.module)
            for key, m in model_table.MODELS.items()
        ],
        interfaces=sorted(
            {
                *law_registry.INTERFACES,
                *law_registry.FAMILY_INTERFACES,
                declarations.KIND_INTERFACE,
                operator_registry.COMPOSITE_INTERFACE,
            }
        ),
        composite_interface=operator_registry.COMPOSITE_INTERFACE,
        kind_interface=declarations.KIND_INTERFACE,
        ids=dict(
            law_families=dict(ids.LAW_FAMILIES),
            families=sorted(ids.FAMILIES),
            piece=ids._PIECE.pattern,
        ),
    )
    places = (*ids.FIXED_FAMILIES, *set(ids.LAW_FAMILIES.values()), *ids.SUBLAW_FAMILIES)
    out["ids"]["twice"] = sorted(w for w, n in Counter(places).items() if n > 1)
    failed = {}
    for info in pkgutil.walk_packages(cells.__path__, "cells."):
        if not info.name.endswith("__main__"):
            try:
                importlib.import_module(info.name)
            except Exception as error:  # Reported, never skipped in silence.
                failed[info.name] = f"{type(error).__name__}: {error}"
    out["not_imported"] = failed
    found = defaultdict(list)

    def walk(value, where, depth, seen):
        if isinstance(value, str):
            if ID.fullmatch(value):
                found[value].append(where)
            return
        if depth == 0 or id(value) in seen:
            return
        if isinstance(value, Mapping):
            seen.add(id(value))
            for k, v in list(value.items()):
                walk(k, f"{where} (a key)", depth - 1, seen)
                walk(v, f"{where}[{str(k)[:40]!r}]", depth - 1, seen)
        elif isinstance(value, (tuple, list, set, frozenset)):
            seen.add(id(value))
            for i, v in enumerate(value):
                walk(v, f"{where}[{i}]", depth - 1, seen)
        elif isinstance(value, type):
            if value.__module__.startswith("cells."):
                seen.add(id(value))
                for k, v in list(vars(value).items()):
                    if not k.startswith("__"):
                        walk(v, f"{where}.{k}", depth - 1, seen)
        elif dataclasses.is_dataclass(value):
            seen.add(id(value))
            for f in dataclasses.fields(value):
                walk(getattr(value, f.name, None), f"{where}.{f.name}", depth - 1, seen)

    for name, module in sorted(sys.modules.items()):
        if name.startswith("cells.") and module:
            for k, v in list(vars(module).items()):
                if not k.startswith("__") and not isinstance(v, types.ModuleType):
                    walk(v, f"{name}.{k}", 6, set())
    out["census"] = {k: v[:3] for k, v in sorted(found.items())}

    def subtypes(cls):
        for sub in cls.__subclasses__():
            yield sub
            yield from subtypes(sub)

    out["law_types"] = {
        t.__name__: t.interface for t in subtypes(law_registry.Law) if t.interface
    } | {name.__name__: i for i, name in law_registry.INTERFACES.items()}
    out["operator_types"] = sorted(
        {t.__name__ for t in subtypes(operator_registry.FamilyOperator)}
        | {"FamilyOperator", "Operator"}
        | {type(op).__name__ for op in operators.operators()}
    )
    out["keys"] = {}
    for module, name in asked["keys"]:
        table = None
        with contextlib.suppress(ImportError):
            table = getattr(importlib.import_module(module), name, None)
        out["keys"][f"{module}.{name}"] = None if table is None else list(table)
    real.write(json.dumps(out) + "\n")
    return 0


# ------------------------------------------------------------------ what the tracked files say


def module_of(path):
    """The dotted module name of a file under src/."""
    return path[len("src/") : -len(".py")].replace("/", ".").removesuffix(".__init__")


def strings_of(tree):
    """A Python tree's string constants that are not statements (a docstring or a bare string is
    prose and places nothing)."""
    prose = {
        id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Expr)
    }  # A string statement's own constant.
    return [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in prose
    ]


def definitions(value, models):
    """(model ID, object) for each nested object of JSON data that is a definition of a model in
    `models`: it holds "model", an ID or an object with an ID."""
    if isinstance(value, dict):
        model = value.get("model")
        identifier = model.get("id") if isinstance(model, dict) else model
        if isinstance(identifier, str) and identifier in models:
            yield identifier, value
        for v in value.values():
            yield from definitions(v, models)
    elif isinstance(value, list):
        for v in value:
            yield from definitions(v, models)


def keyed_strings(value, key=""):
    """(the key that carries it, string) of every string in JSON data; a key is carried by
    "<key>"."""
    if isinstance(value, dict):
        for k, v in value.items():
            yield "<key>", k
            yield from keyed_strings(v, k)
    elif isinstance(value, list):
        for v in value:
            yield from keyed_strings(v, key)
    elif isinstance(value, str):
        yield key, value


AN_ID = re.compile(rb"[A-Za-z0-9_]@[1-9]")  # A quick test: a file without it spells no ID.
A_MAJOR = re.compile(rb"@[1-9]")  # And one without it spells none even in two literals.
SCHEMA_KEYS = {"kind", "format", "schema", "record_kind", "report_kind"}
SCHEMA_NAME = re.compile(
    r"(^|_)(KIND|KINDS|FORMAT|FORMATS|SCHEMA|RECORD|RECORDS|REPORT|MANIFEST|CHECKPOINT|VIEW|"
    r"PROTOCOL|RESULT|SPEC_KIND|TABLE|MAP)(_|$)"
)


class Source:
    """The IDs that the tracked files spell, by where and how they spell them."""

    def __init__(self, files, scope, under=""):
        self.constants = {}  # (module, name) -> [value, "path:line"]
        self.quoted = defaultdict(lambda: defaultdict(list))  # scope -> ID -> [site]
        self.json = {}  # path -> data
        self.json_ids = defaultdict(lambda: defaultdict(list))  # scope -> ID -> [(path, key)]
        self.carried = defaultdict(Counter)  # ID -> the schema keys that carry it
        for path, (_, data) in sorted(files.items()):
            if not (path.startswith(under) and in_scope(path, scope)) or not AN_ID.search(data):
                continue
            text = None if path.startswith(SELF) or path == RENAMED else text_of(data)
            if text is None:
                continue
            if path.endswith(".py"):
                self.python(path, text)
            elif path.endswith(".json"):
                self.json_file(path, text)

    def python(self, path, text):
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return
        where = scope_of(path)
        for n in strings_of(tree):
            if ID.fullmatch(n.value):
                self.quoted[where][n.value].append(f"{path}:{n.lineno}")
        for n in ast.walk(tree):
            if isinstance(n, ast.Dict):
                pairs = [(k.value, v) for k, v in zip(n.keys, n.values, strict=True)
                         if isinstance(k, ast.Constant)]  # fmt: skip
            elif isinstance(n, ast.Call):
                pairs = [(k.arg, k.value) for k in n.keywords]
            else:
                continue
            for k, v in pairs:
                if k in SCHEMA_KEYS and isinstance(v, ast.Constant) and isinstance(v.value, str):
                    if ID.fullmatch(v.value):
                        self.carried[v.value][k] += 1
        if path.startswith("src/"):
            for n in tree.body:
                target = value = None
                if isinstance(n, ast.Assign) and len(n.targets) == 1:
                    target, value = n.targets[0], n.value
                elif isinstance(n, ast.AnnAssign):
                    target, value = n.target, n.value
                if (
                    isinstance(target, ast.Name)
                    and isinstance(value, ast.Constant)
                    and isinstance(value.value, str)
                    and ID.fullmatch(value.value)
                ):
                    key = (module_of(path), target.id)
                    self.constants[key] = [value.value, f"{path}:{n.lineno}"]
                    if SCHEMA_NAME.search(target.id):
                        self.carried[value.value][f"the constant {target.id}"] += 1

    def json_file(self, path, text):
        try:
            data = json.loads(text)
        except ValueError:
            return
        self.json[path] = data
        for key, value in keyed_strings(data):
            if ID.fullmatch(value):
                self.json_ids[scope_of(path)][value].append((path, key))
                if key in SCHEMA_KEYS:
                    self.carried[value][key] += 1

    def live(self):
        """{ID: [site]} of live src's literals."""
        return self.quoted["src"]


# ------------------------------------------------------------------ the table


def _row(declared, piece, family, source, **more):
    return dict(
        dict(interface=None, host=None, module=None),
        old=spellings(declared),
        new=new_id(declared, family),
        family=family,
        piece=piece,
        source=source,
        **more,
    )


def seed_values(seed, engine, source, spelled):
    """(a seed's IDs, why it gives none): a constant's value, or the keys of a lookup table that no
    row in `spelled` ({spelling: its row's source}) holds."""
    where = f"the seed {seed['module']}.{seed['name']}"
    if seed["family"] not in engine["ids"]["families"]:
        return [], f"{where}: registry/ids.py has no family word {seed['family']!r}"
    if seed.get("keys"):
        keys = engine["keys"].get(f"{seed['module']}.{seed['name']}")
        if not keys:
            return [], f"{where}: its table is gone or empty"
        own = [k for k in keys if not set(spellings(k)) & set(spelled)]
        return own, None if own else f"{where}: other rows hold all {len(keys)} of its keys"
    found = source.constants.get((seed["module"], seed["name"]))
    if found is None:
        return [], f"{where}: the constant is gone"
    held = next((spelled[s] for s in spellings(found[0]) if s in spelled), None)
    return [found[0]], f"{where}: {found[0]} is held by the {held}" if held else None


def build_rows(choices, engine, source):
    """(rows, problems): every candidate row, and why one could not be made or is made twice."""
    rows, problems, spelled = [], [], {}
    words = engine["ids"]["law_families"]

    def add(row):
        rows.append(row)
        spelled.update(dict.fromkeys(row["old"], row["source"]))

    for law in engine["laws"]:
        word = words.get(law["interface"])
        if word is None:
            problems.append(f"{law['declared']}: no family word for {law['interface']}")
            continue
        add(
            _row(
                law["declared"],
                "law",
                word,
                f"law registry: {law['module']}",
                interface=law["interface"],
                host=law["host"],
                module=law["module"],
            )
        )
    for kind in engine["kinds"]:
        add(
            _row(
                kind["declared"],
                "kind",
                "kind",
                f"kind registry: {kind['model_key']}",
                interface=engine["kind_interface"],
            )
        )
    for section, interface in (("operators", engine["composite_interface"]),
                               ("family_operators", None)):  # fmt: skip
        for op in engine[section]:
            add(
                _row(
                    op["declared"],
                    "operator",
                    "operator",
                    f"operator registry: {op['module']}",
                    interface=op.get("interface", interface),
                    host=op.get("host"),
                    module=op["module"],
                )
            )
    for model in engine["models"]:
        add(
            _row(
                model["declared"],
                "model",
                "model",
                f"model table: {model['module']}",
                module=model["module"],
            )
        )
    for seed in choices["seeds"]:
        values, why = seed_values(seed, engine, source, spelled)
        if why:
            problems.append(why)
            continue
        for value in values:
            add(
                _row(
                    value,
                    seed.get("piece", seed["family"]),
                    seed["family"],
                    f"seed {seed['module']}.{seed['name']}",
                    module=seed["module"],
                )
            )
    rows.sort(key=lambda r: (r["family"], r["new"]))
    return rows, problems


def collisions(rows, engine, source):
    """The collision report: {check: [findings]}. Every check but the last must be empty; the last
    lists the old spellings that a schema-named key also carries, for reading."""
    by_new, by_old = defaultdict(set), defaultdict(set)
    for row in rows:
        by_new[row["new"]].add(row["old"][0])
        for old in row["old"]:
            by_old[old].add((row["piece"], row["new"]))
    interfaces = {s for i in engine["interfaces"] for s in spellings(i)}
    words = {r["family"] for r in rows} | set(engine["ids"]["families"])
    dotted = {  # A test spells examples of the grammar: it holds no schema's name of its own.
        i: scope
        for held in (source.quoted, source.json_ids)
        for scope in sorted(held, key=lambda s: s == "tests", reverse=True)
        for i in held[scope]
        if i.split("@")[0].count(".") > 1
    }
    return {
        "two old keys to one new ID": sorted(n for n, k in by_new.items() if len(k) > 1),
        "one spelling naming two pieces": sorted(
            f"{o}: {sorted(p)}" for o, p in by_old.items() if len(p) > 1
        ),
        "an old spelling equal to an interface": sorted(o for o in by_old if o in interfaces),
        "an old spelling equal to a new ID": sorted(set(by_old) & set(by_new)),
        "a new ID that the tree already spells": sorted(set(dotted) & set(by_new)),
        "a name of three or more parts whose second part is a family word": sorted(
            i
            for i, scope in dotted.items()
            if scope != "tests"
            and i not in by_new
            and i.startswith("cells.")
            and i.split(".")[1] in words
        ),  # fmt: skip
        "a new ID that is not namespace.family.name@major": sorted(
            n for n in by_new if not NEW.fullmatch(n)
        ),
        "listed: an old spelling that a schema-named key carries": sorted(
            f"{o} ({', '.join(sorted(source.carried[o]))})" for o in by_old if source.carried.get(o)
        ),
    }


def live_ids(rows, engine, source):
    """({ID: [site]} that live src holds, as a literal or at run time; {ID: [site]} that a live
    model's definition spells)."""
    models = {old for row in rows if row["piece"] == "model" for old in row["old"]}
    live, spelled = defaultdict(list), defaultdict(list)
    for i, sites in source.live().items():
        live[i] += sites
    for i, where in engine["census"].items():
        live[i] += [f"{w} (at run time)" for w in where]
    for path, data in source.json.items():
        for model, value in definitions(data, models):
            for key, s in keyed_strings(value):
                if ID.fullmatch(s):
                    spelled[s].append(f"{path} (key {key}, model {model})")
    return live, spelled


def reconcile(rows, choices, engine, source):
    """Every ID in scope placed: (kept, unplaced, classes). `kept` is {class: [bare IDs]}; an
    unplaced ID is one that live src holds, or a live model's definition spells, and nothing
    places: [(ID, why, [sites])]."""
    table = {old for row in rows for old in row["old"]}
    interfaces = {s for i in engine["interfaces"] for s in spellings(i)}
    hand = {}
    for cls, entries in choices["keep"]["ids"].items():
        for entry in entries:
            for s in spellings(entry["id"]):
                hand[s] = cls
    live, live_definitions = live_ids(rows, engine, source)
    unplaced = []
    for held, why in ((live, "live src holds it"),
                      (live_definitions, "a live model's definition spells it")):  # fmt: skip
        for i, sites in sorted(held.items()):
            if i in table or i in interfaces or i in hand:
                continue
            if held is live_definitions and (
                any(k in SCHEMA_KEYS for k in source.carried.get(i, ())) and i not in live
            ):
                continue  # A nested record's own kind, which no source holds.
            unplaced.append((i, why, sites[:4]))
    kept = {
        "interface": sorted({bare(i) for i in engine["interfaces"]}),
        **{cls: sorted(bare(e["id"]) for e in es) for cls, es in choices["keep"]["ids"].items()},
    }
    classes = Counter()
    seen = {
        bare(i)
        for scope in (*source.quoted.values(), *source.json_ids.values())
        for i in scope
        if i.split("@")[0].count(".") <= 1
    } | {bare(i) for i in engine["census"]}
    for i in seen:
        all_spellings = spellings(i)
        if any(s in table for s in all_spellings):
            classes["the table"] += 1
        elif any(s in interfaces for s in all_spellings):
            classes["interface"] += 1
        elif any(s in hand for s in all_spellings):
            classes["kept: " + next(hand[s] for s in all_spellings if s in hand)] += 1
        elif any(s in live or s in live_definitions for s in all_spellings):
            classes["unplaced"] += 1
        else:
            classes["no source holds it"] += 1
    return kept, unplaced, dict(classes)


# A path in prose, with a folder: from the checkout's root, or from src/cells.
CITED = re.compile(r"(?<![\w./-])((?:[\w.-]+/)+[\w.-]+\.(?:py|json|sh|md|toml|tsv))(?![\w/])")


def choices_problems(choices, rows, engine, source, files):
    """What the choices name that the tree has overtaken, beside the seeds (build_rows): a kept ID
    or a plant that is gone or that another holds, and a path that is gone."""
    out = [f"registry/ids.py gives the word {w!r} two places" for w in engine["ids"]["twice"]]
    table = {s: row["source"] for row in rows for s in row["old"]}
    interfaces = {s for i in engine["interfaces"] for s in spellings(i)}
    live, spelled = live_ids(rows, engine, source)
    seen = {}
    for cls, entries in choices["keep"]["ids"].items():
        for entry in entries:
            names = spellings(entry["id"])
            held = next((table[s] for s in names if s in table), None)
            if held is None and set(names) & interfaces:
                held = "interfaces"
            twice = next((seen[s] for s in names if s in seen), None)
            if held or twice:
                out.append(f"kept {entry['id']} ({cls}): held by the {held or twice}")
            elif not any(s in live or s in spelled for s in names):
                out.append(f"kept {entry['id']} ({cls}): nothing live spells it")
            seen.update(dict.fromkeys(names, f"kept list ({cls})"))
    plants, tokens = choices["plants"], set()
    for path, (_, data) in files.items():
        if path.startswith(("tests/", "validation/", "scripts/")) and path.endswith(".py"):
            if AN_ID.search(data) and not path.startswith(SELF):
                tokens.update(m[1] for m in TOKEN.finditer(text_of(data) or ""))
    for identifier, said in {**plants["families"], **plants.get("not_plants", {})}.items():
        held = next((table[s] for s in spellings(identifier) if s in table), None)
        if held:
            out.append(f"plant {identifier}: held by the {held}")
        elif identifier not in tokens:
            out.append(f"plant {identifier}: no test and no driver spells it")
        if isinstance(said, dict):
            out += [f"plant {identifier}: {p} is gone" for p in said if p != "*" and p not in files]
    frozen = choices["frozen"]
    paths = [("scope", p) for p in choices["scope"]["test_ids"]]
    for part, entries in (("pinned", choices["pinned"]), ("keep", choices["keep"]["files"]),
                          ("frozen, live", frozen["live"]),
                          ("frozen, declared", frozen["declared"])):  # fmt: skip
        paths += [(part, r["path"]) for r in entries]
    for r in choices["pinned"]:
        paths += [(f"pinned {r['path']}, by", p) for p in r.get("pinned_by", ())]
        own = digests_of(files[r["path"]][1]).values() if r["path"] in files else ()
        for p in r.get("pinned_by", ()) if own else ():
            held = HEX.findall(text_of(files[p][1]) or "") if p in files else None
            if held is not None and not any(d.startswith(h) for h in held for d in own):
                out.append(f"pinned {r['path']}: {p} quotes no hash of it")
    paths += [("ids_kept", r["test"].split("::")[0]) for r in choices.get("ids_kept", ())]
    out += [f"{part}: {p} is gone" for part, p in paths if p not in files]
    out += [
        f"reviewed: no file is {r['path']} ({r['reason']})"
        for r in choices["reviewed"]
        if not any(fnmatchcase(p, r["path"]) for p in files)
    ]
    for part in ("seeds", "keep", "pinned", "frozen", "plants", "reviewed", "ids_kept"):
        for text in json_strings(prose_of(choices.get(part, ()))):
            for m in CITED.finditer(text):
                if m[1] not in files and LIVE + m[1] not in files:
                    out.append(f"{part}: a reason cites {m[1]}, which is gone: {text[:80]}")
    return out


def prose_of(value):
    """The reasons, notes and rulings in a part of the choices, with nothing else."""
    if isinstance(value, dict):
        return [
            x if isinstance(x, str) else prose_of(x)
            for k, x in value.items()
            if not isinstance(x, str) or k in ("reason", "note", "ruling", "named_in")
        ]
    return [prose_of(x) for x in value] if isinstance(value, (list, tuple)) else []


def left_alone(choices):
    """{path: why} of the files in scope that the choices leave as they are."""
    out = {r["path"]: "pinned by hash, left" for r in choices["pinned"] if r["choice"] == "leave"}
    out.update((r["path"], f"kept: {r['reason']}") for r in choices["keep"]["files"])
    return out


def make_map(choices, engine, source, revision, rehearsal):
    """(map, rows, report): refused only by the caller, which reads the report."""
    rows, problems = build_rows(choices, engine, source)
    kept, unplaced, classes = reconcile(rows, choices, engine, source)
    doc = dict(
        kind=MAP_KIND,
        move=choices["move"],
        final=not rehearsal,
        revision=revision,
        scope=choices["scope"],
        rows=rows,
        left=left_alone(choices),
        kept=kept,
        plants=[],
    )
    return doc, rows, dict(
        problems=problems, unplaced=unplaced, collisions=collisions(rows, engine, source),
        classes=classes, not_imported=engine["not_imported"],
    )  # fmt: skip


def engine_types(engine):
    """What places a plant by its declaring type: the law types and the modules that declare a law,
    each with its family, and the kinds' and operators' types."""
    words = engine["ids"]["law_families"]
    return dict(
        laws={t: words[i] for t, i in sorted(engine["law_types"].items()) if i in words},
        kinds=["Kind"],
        operators=engine["operator_types"],
        modules={
            r["module"]: words[r["interface"]] for r in engine["laws"] if r["interface"] in words
        },
    )


TSV = ("old", "new", "family", "piece", "interface", "source")


def tsv_lines(rows):
    out = []
    for row in rows:
        for old in row["old"]:
            values = [old, row["new"], row["family"], row["piece"], row["interface"],
                      row["source"]]  # fmt: skip
            out.append("\t".join(str(v) for v in values))
    return ["\t".join(TSV), *sorted(out)]


def compare_tables(ours, theirs):
    """The differences of two table.tsv files, row by row: old spelling, new ID, family (the piece
    and the interface are listed apart)."""

    def read(lines):
        head, *rest = lines
        names = head.split("\t")
        return {f[0]: dict(zip(names, f, strict=True)) for f in (x.split("\t") for x in rest)}

    a, b = read(ours), read(theirs)
    out = dict(only_ours=sorted(set(a) - set(b)), only_theirs=sorted(set(b) - set(a)), differ=[],
               piece_or_interface=[])  # fmt: skip
    for old in sorted(set(a) & set(b)):
        for key in ("new", "family"):
            if a[old][key] != b[old][key]:
                out["differ"].append([old, key, a[old][key], b[old][key]])
        for key in ("piece", "interface"):
            if a[old][key] != b[old][key]:
                out["piece_or_interface"].append([old, key, a[old][key], b[old][key]])
    return dict(rows=len(a), their_rows=len(b), **out)


# ------------------------------------------------------------------ the frozen list

# A registration-style tag's name; a spec-like path; a freezing commit's subject (§6).
REGISTRATION = re.compile(
    r"regist|judge|references?\b|references-|erratum|amendment|criteria|-rule|sheet|predictions|"
    r"declaration|tag-a|spec-amend|supplement|protocol"
)
SPEC_LIKE = re.compile(
    r"(^|/)(references|spec)/|REGISTRATION|CRITERIA|AMENDMENT|ERRATUM|judge|_rule|protocol|registr|"
    r"predict|RUNG|sheet|designs?/|criteria"
)
FREEZES = re.compile(r"^(freeze|register)\b", re.I)
# Words of a commit that registers or freezes what it commits, whatever its subject begins with.
SAYS_REGISTERED = re.compile(
    r"\b(pre-?)?regist(er(ed|s)?|ration)\b|\bfro?ee?zen?\b|\bsealed\b|before any .*\boutput\b", re.I
)
FROZEN_ROOT = "validation"


def _is_ancestor(a, b, cwd):
    code = subprocess.run(
        ["git", "merge-base", "--is-ancestor", a, b], cwd=cwd, capture_output=True
    ).returncode
    if code not in (0, 1):
        raise Refused(f"git merge-base {a[:8]} {b[:8]} failed")
    return code == 0


def _blobs(tree, rev, under=FROZEN_ROOT):
    out = {}
    for row in git("ls-tree", "-r", "-z", rev, "--", under, cwd=tree).decode().split("\0"):
        if row:
            meta, path = row.split("\t", 1)
            out[path] = meta.split()[2]
    return out


def frozen_rules(tree, base):
    """{path: {(rule, reason)}} of the frozen files under validation/ at `base`, by the three rules
    of the design's section 6:
    - tag: what a registration-style tag's own non-merge commits changed (on the base's first-parent
      line its own commit unless a merge; from a side branch those reachable from it but not from
      M^1, M the first-parent merge that brought it in; unmerged, those the base does not reach);
    - merge: for such a tag at a first-parent merge, its branch's own non-merge commits, spec-like
      paths only;
    - commit: files whose last change is a commit whose subject begins "Freeze" or "Register".
    The tag and merge rules take a file only where its blob at the base is still the tag's."""

    def g(*words):
        return git(*words, cwd=tree).decode()

    base = g("rev-parse", f"{base}^{{commit}}").strip()
    line = g("rev-list", "--first-parent", base).split()
    place = {c: i for i, c in enumerate(line)}
    here = _blobs(tree, base)
    out, changed, at = defaultdict(set), {}, {}

    def paths_of(commit):
        if commit not in changed:
            changed[commit] = g(
                "diff-tree", "--no-commit-id", "-r", "-z", "--name-only", commit, "--", FROZEN_ROOT
            ).split("\0")
        return [p for p in changed[commit] if p]

    def first_containing(commit):
        lo, hi = 0, len(line) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if _is_ancestor(commit, line[mid], tree):
                lo = mid
            else:
                hi = mid - 1
        return line[lo]

    for tag in g("tag", "-l").split():
        if tag.startswith("trial/") or not REGISTRATION.search(tag):
            continue
        commit = g("rev-parse", f"{tag}^{{commit}}").strip()
        rule, own = "tag", [commit]
        if commit in place:
            if len(g("rev-list", "--parents", "-n", "1", commit).split()) > 2:
                rule = "merge"
                own = g("rev-list", "--no-merges", commit, f"^{commit}^1").split()
        elif _is_ancestor(commit, base, tree):
            merge = first_containing(commit)
            own = g("rev-list", "--no-merges", commit, f"^{merge}^1").split()
        else:
            own = g("rev-list", "--no-merges", commit, f"^{base}").split()
        names = {p for k in own for p in paths_of(k)}
        if names and commit not in at:
            at[commit] = _blobs(tree, commit)
        for path in names:
            if rule == "merge" and not SPEC_LIKE.search(path):
                continue
            if path in here and here[path] == at[commit].get(path):
                out[path].add((rule, tag))
    for row in g("log", "--format=%H %s", base, "--", FROZEN_ROOT).splitlines():
        commit, _, subject = row.partition(" ")
        if FREEZES.match(subject):
            for path in paths_of(commit):
                if (
                    path in here
                    and g("log", "-1", "--format=%H", base, "--", path).strip() == commit
                ):
                    out[path].add(("commit", commit[:8]))
    return dict(out)


def frozen_list(tree, path, choices, also=None):
    """{path: why} of the frozen files: the recorded list where there is one, the rules at `also`
    (a revision) where it is given or no list is recorded, and the declared files; less the live
    exceptions. So a branch's own registrations, made since the list, are left alone too."""
    out = read_frozen(path)
    if also is not None or not out:
        for name, found in frozen_rules(tree, also or "HEAD").items():
            out.setdefault(name, sorted(found))
    for row in choices["frozen"]["declared"]:
        out.setdefault(row["path"], [["declared", row["reason"]]])
    for row in choices["frozen"]["live"]:
        out.pop(row["path"], None)
    return out


def owner_of(path, rule, reason, owners):
    """Who confirms a frozen file: the tag's leading word (as the choices' owners name it), or, for
    the commit rule, its folder."""
    if rule == "commit":
        return "/".join(path.split("/")[:2])
    for prefix, owner in owners.items():
        if reason.startswith(prefix):
            return owner
    return re.split(r"[-.]", reason)[0]


def python_imports(path, tree, modules):
    """The tracked modules under tests/, validation/ and scripts/ that a Python file imports."""
    out = set()
    package = path.rsplit("/", 1)[0].replace("/", ".")
    for n in ast.walk(tree):
        names = []
        if isinstance(n, ast.Import):
            names = [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            name = n.module or ""
            if n.level:
                parts = package.split(".")
                name = ".".join(parts[: len(parts) - n.level + 1] + ([name] if name else []))
            names = [name, *(f"{name}.{a.name}" for a in n.names)]
        for name in names:
            if name in modules:
                out.add(modules[name])
            elif f"tests.{name}" in modules:  # A tests module by its bare name.
                out.add(modules[f"tests.{name}"])
    return out


def imports_engine(tree):
    return any(
        (isinstance(n, ast.Import) and any(a.name.split(".")[0] == "cells" for a in n.names))
        or (isinstance(n, ast.ImportFrom) and (n.module or "").split(".")[0] == "cells")
        for n in ast.walk(tree)
    )


def frozen_both_ways(tree, base, frozen, mp):
    """(missed, live): the files the map would change that the rules may have missed, with why each
    looks registered, and the frozen Python that holds old spellings in code and that live code
    imports."""
    files = tree_at(base, tree)
    missed, live = [], []
    here = _blobs(tree, base)
    texts = {}
    for path, (_, data) in files.items():
        if in_scope(path, mp.scope) and path.startswith(FROZEN_ROOT + "/") and b"@" in data:
            text = text_of(data)
            if text is not None and mp.text(path, text) != text:
                texts[path] = text
    for path, text in sorted(texts.items()):
        if path in frozen:
            continue
        signs = []
        for row in git("log", "--format=%H %s", base, "--", path, cwd=tree).decode().splitlines():
            commit, _, subject = row.partition(" ")
            if SAYS_REGISTERED.search(subject):
                then = subprocess.run(
                    ["git", "rev-parse", "-q", "--verify", f"{commit}:{path}"],
                    cwd=tree, capture_output=True, text=True,
                ).stdout.strip()  # fmt: skip
                same = "unchanged since" if then == here.get(path) else "changed since"
                signs.append(f"{commit[:8]} ({same}): {subject[:90]}")
        if path.endswith(".json"):
            with contextlib.suppress(ValueError):
                data = json.loads(text)
                if isinstance(data, dict):
                    signs += [
                        f"its {k}: {str(data[k])[:60]}"
                        for k in ("registered", "registration", "status")
                        if k in data and data[k] not in (False, None, "")
                    ]
        if SPEC_LIKE.search(path):
            signs.append("a spec-like path")
        if signs:
            missed.append((path, signs))
    modules, imports, engine = {}, defaultdict(set), set()
    pythons = [
        p for p in files
        if p.endswith(".py") and p.startswith(("tests/", "validation/", "scripts/"))
    ]  # fmt: skip
    for path in pythons:
        modules[path[:-3].replace("/", ".").removesuffix(".__init__")] = path
    for path in pythons:
        text = text_of(files[path][1])
        with contextlib.suppress(SyntaxError, ValueError):
            parsed = ast.parse(text)
            for target in python_imports(path, parsed, modules):
                imports[target].add(path)
            if path in frozen and imports_engine(parsed):
                engine.add(path)
    for path in sorted(frozen):
        if path.endswith(".py") and path in texts:
            code = sum(
                len([1 for m in TOKEN.finditer(n.value) if m[1] in mp.new])
                for n in strings_of(ast.parse(texts[path]))
            )
            readers = sorted(p for p in imports[path] if p not in frozen)
            if code and (readers or path in engine):
                live.append((path, code, path in engine, readers))
    return missed, live


def cmd_frozen(args):
    choices_path, map_path, _ = data_paths(args)
    choices = load_choices(choices_path)
    if args.lists and not Path(map_path).exists():
        raise Refused(f"--lists reads the map for both directions, and {map_path} is not there: "
                      "write the list with --out, then the table, then --lists")  # fmt: skip
    rules = frozen_rules(args.tree, args.base)
    settings = choices["frozen"]
    live = {r["path"]: r["reason"] for r in settings["live"]}
    rows, kept = [], {}
    for path, found in sorted(rules.items()):
        if path in live:
            kept[path] = dict(reason=live[path], rules=sorted(found))
            continue
        for rule, reason in sorted(found):
            rows.append((path, rule, reason, owner_of(path, rule, reason, settings["owners"])))
    for row in settings["declared"]:
        rows.append((row["path"], "declared", row["reason"], row.get("owner", "the lead")))
    frozen = {r[0] for r in rows}
    if args.out:
        Path(args.out).write_text("".join("\t".join(r) + "\n" for r in sorted(rows)))
    by_owner = defaultdict(set)
    for path, _, _, owner in rows:
        by_owner[owner].add(path)
    report = dict(
        base=git("rev-parse", args.base, cwd=args.tree).decode().strip(),
        files=len(frozen),
        by_rule=dict(Counter(r for _, r in {(p, r) for p, r, *_ in rows})),
        frozen_by_rule_but_live=kept,
        owners={o: len(p) for o, p in sorted(by_owner.items())},
    )
    if args.compare:
        theirs = defaultdict(set)
        for line in Path(args.compare).read_text().splitlines():
            path, rule, reason = line.split("\t")[:3]
            if rule != "pin":
                theirs[path].add((rule, reason))
        ours = defaultdict(set)
        for path, found in rules.items():
            ours[path] = found
        report["compared"] = dict(
            their_files=len(theirs),
            only_ours={p: sorted(ours[p]) for p in sorted(set(ours) - set(theirs))},
            only_theirs={p: sorted(theirs[p]) for p in sorted(set(theirs) - set(ours))},
            other_reasons={
                p: dict(ours=sorted(ours[p] - theirs[p]), theirs=sorted(theirs[p] - ours[p]))
                for p in sorted(set(ours) & set(theirs))
                if ours[p] != theirs[p]
            },
        )
    print(json.dumps(report, indent=1))
    if args.lists:
        mp = Map(load_json(map_path, MAP_KIND))
        missed, ran = frozen_both_ways(args.tree, args.base, frozen, mp)
        with Path(args.lists).open("w") as out:
            for owner, paths in sorted(by_owner.items()):
                print(f"== {owner}: {len(paths)} frozen files", file=out)
                for p in sorted(paths):
                    why = ", ".join(f"{r} {x}" for q, r, x, _ in sorted(rows) if q == p)
                    print(f"  {p}  ({why})", file=out)
            print(
                f"\n== not frozen by any rule, but registered by its signs: {len(missed)}", file=out
            )
            for path, signs in missed:
                print(f"  {path}", file=out)
                for sign in signs:
                    print(f"      {sign}", file=out)
            print(
                f"\n== frozen Python with old spellings in code that runs today: {len(ran)}",
                file=out,
            )
            for path, code, engine, readers in ran:
                said = "calls the engine; " if engine else ""
                by = ", ".join(readers) or "no live file"
                print(f"  {path}  ({code} in code; {said}imported by {by})",
                      file=out)  # fmt: skip
        print(json.dumps(dict(missed=len(missed), frozen_code_that_runs=len(ran)), indent=1))
    return 0


# ------------------------------------------------------------------ plants

DECLARERS = {"law_id": "law", "kind_id": "kind", "operator_id": "operator", "LAW_ID": "operator"}
OPERATOR_FLAGS = {"EVENT", "SPLIT", "PROCESS", "RK4", "DECLARATION_ONLY"}


class Plants:
    """The pieces that tests and drivers declare themselves (D371 Q8): each takes the three-part
    shape, its family from its declaring type. `types` names the engine's: {"laws": {type: family},
    "kinds": [...], "operators": [...], "modules": {module: family of the law it declares}}."""

    def __init__(self, files, mp, types, hand=None):
        self.mp, self.types, self.hand = mp, types, dict(hand or {})
        self.placed = defaultdict(lambda: defaultdict(list))  # ID -> family -> [site]
        self.rest = defaultdict(list)  # ID -> [(site, why)]: declared, and its family not seen.
        self.named = defaultdict(set)  # ID -> the files that spell it
        self.imports = {}  # path -> the tracked modules it imports
        here = {
            path: data
            for path, (_, data) in sorted(files.items())
            if path.startswith(("tests/", "validation/", "scripts/")) and path.endswith(".py")
        }
        self.modules = {p[:-3].replace("/", ".").removesuffix(".__init__"): p for p in here}
        for path, data in here.items():
            if mp.excluded(path) is None and AN_ID.search(data):
                with contextlib.suppress(SyntaxError, ValueError):
                    self.file(path, ast.parse(text_of(data)))
                for m in TOKEN.finditer(text_of(data)):
                    if self.open(m[1]):
                        self.named[m[1]].add(path)

    def open(self, identifier):
        """Whether a declared ID is a plant that waits for its shape."""
        return (
            isinstance(identifier, str)
            and ID.fullmatch(identifier) is not None
            and identifier not in self.mp.new
            and identifier not in self.mp.news
            and identifier.split("@")[0].count(".") < 2
        )

    def place(self, path, node, identifier, family):
        if not self.open(identifier):
            return
        site = f"{path}:{node.lineno}"
        if family is None:
            self.rest[identifier].append((site, "its declaring type is not seen"))
        else:
            self.placed[identifier][family].append(site)

    def file(self, path, tree):
        types = self.types
        values, modules, classes = {}, {}, {}
        for n in ast.walk(tree):
            if (
                isinstance(n, ast.Assign)
                and len(n.targets) == 1
                and isinstance(n.targets[0], ast.Name)
            ):
                values.setdefault(n.targets[0].id, []).append((n.lineno, n.value))
            elif isinstance(n, ast.ImportFrom) and n.module:
                for a in n.names:
                    modules[a.asname or a.name] = f"{n.module}.{a.name}"
            elif isinstance(n, ast.Import):
                for a in n.names:
                    modules[a.asname or a.name] = a.name
            elif isinstance(n, ast.ClassDef):
                classes[n.name] = [b.attr if isinstance(b, ast.Attribute) else getattr(b, "id", "")
                                   for b in n.bases]  # fmt: skip
        self.imports[path] = python_imports(path, tree, self.modules)

        def text(node, depth=0):
            """A constant's text, a module-level name's, or a template's ("id@1".replace(...))."""
            if isinstance(node, ast.Constant):
                return node.value if isinstance(node.value, str) else None
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "replace"
            ):
                return text(node.func.value, depth + 1)
            if isinstance(node, ast.Name) and depth < 4:
                for _, value in reversed(values.get(node.id, [])):
                    return text(value, depth + 1)
            return None

        def family(node, depth=0):
            """The family of the law an expression gives, or None."""
            if depth > 6:
                return None
            if isinstance(node, ast.Call):
                f = node.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                if name in types["laws"]:
                    return types["laws"][name]
                if name == "lookup" and node.args:
                    new = self.mp.new.get(text(node.args[0]) or "")
                    if new is not None:
                        return new.split(".")[1]
                    if isinstance(node.args[0], ast.Attribute):
                        return family(node.args[0], depth + 1)
                    return None
                if name == "replace" and node.args:
                    return family(node.args[0], depth + 1)
                if name == "_replace" and isinstance(f, ast.Attribute):
                    return family(f.value, depth + 1)
                return None
            if isinstance(node, ast.Attribute):
                whole = ast.unparse(node.value)
                module = modules.get(whole)
                if module in types["modules"]:
                    return types["modules"][module]
                return None
            if isinstance(node, ast.Name):
                if node.id in modules and modules[node.id].rpartition(".")[0] in types["modules"]:
                    return types["modules"][modules[node.id].rpartition(".")[0]]
                for _, value in reversed(values.get(node.id, [])):
                    found = family(value, depth + 1)
                    if found is not None:
                        return found
            return None

        def is_operator(name, depth=0):
            if name in types["operators"] or name == "Operator":
                return True
            return depth < 6 and any(is_operator(b, depth + 1) for b in classes.get(name, ()))

        def law_family(name, depth=0):
            if name in types["laws"]:
                return types["laws"][name]
            found = [law_family(b, depth + 1) for b in classes.get(name, ()) if depth < 6]
            return next((f for f in found if f), None)

        # A helper of the file's own: a function with a parameter that becomes a piece's ID.
        helpers = {}
        for n in ast.walk(tree):
            if isinstance(n, ast.FunctionDef):
                for param, kind in self.becomes(n, types, is_operator, family):
                    helpers.setdefault(n.name, []).append((param, kind))

        for n in ast.walk(tree):
            if isinstance(n, ast.ClassDef):
                for item in n.body:
                    if isinstance(item, ast.Assign) and any(
                        isinstance(x, ast.Name) and x.id == "LAW_ID" for x in item.targets
                    ):
                        kind = "operator" if is_operator(n.name) else None
                        if kind or n.bases:
                            self.place(path, item, text(item.value), kind)
            elif isinstance(n, ast.Dict):
                for k, v in zip(n.keys, n.values, strict=True):
                    if isinstance(k, ast.Constant) and k.value == "LAW_ID":
                        self.place(path, v, text(v), "operator")
            elif isinstance(n, ast.Call):
                f = n.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                given = {k.arg: k.value for k in n.keywords}
                first = n.args[0] if n.args else None
                if "LAW_ID" in given and (name == "dict" or OPERATOR_FLAGS & set(given)):
                    self.place(path, n, text(given["LAW_ID"]), "operator")
                if name in types["laws"]:
                    self.place(path, n, text(given.get("law_id", first)), types["laws"][name])
                elif name in types["kinds"]:
                    self.place(path, n, text(given.get("kind_id", first)), "kind")
                elif name in types["operators"] and name not in ("Operator",):
                    self.place(path, n, text(given.get("operator_id", first)), "operator")
                elif name in classes:  # A type of the test's own, by its bases.
                    own = law_family(name)
                    if own or is_operator(name):
                        self.place(path, n, text(given.get("law_id", first)), own or "operator")
                elif name in ("replace", "_replace"):
                    base = first if name == "replace" else getattr(f, "value", None)
                    for key, what in DECLARERS.items():
                        if key in given and key != "LAW_ID":
                            found = what if what != "law" else family(base)
                            self.place(path, n, text(given[key]), found)
                for (place, param), kind in helpers.get(name, ()):
                    value = given.get(param, n.args[place] if place < len(n.args) else None)
                    if value is not None:
                        self.place(path, n, text(value), kind)

    @staticmethod
    def becomes(function, types, is_operator, family):
        """((place, parameter), family) of each parameter of a function that its body makes a
        piece's ID: LAW_ID = p in a class, LAW_ID=p or kind_id=p in a call, law_id=p of a law."""
        params = {a.arg: i for i, a in enumerate(function.args.args)}
        out = []
        for n in ast.walk(function):
            pairs = []
            if isinstance(n, ast.ClassDef):
                for item in n.body:
                    if isinstance(item, ast.Assign) and is_operator(n.name):
                        if any(getattr(x, "id", "") == "LAW_ID" for x in item.targets):
                            pairs.append((item.value, "operator"))
            elif isinstance(n, ast.Call):
                name = (
                    n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
                )
                given = {k.arg: k.value for k in n.keywords}
                if "LAW_ID" in given and (name == "dict" or OPERATOR_FLAGS & set(given)):
                    pairs.append((given["LAW_ID"], "operator"))
                if "kind_id" in given:
                    pairs.append((given["kind_id"], "kind"))
                if "law_id" in given and name == "replace" and n.args:
                    pairs.append((given["law_id"], family(n.args[0])))
                if name in types["laws"]:
                    first = n.args[0] if n.args else None
                    pairs.append((given.get("law_id", first), types["laws"][name]))
            for value, kind in pairs:
                if isinstance(value, ast.Name) and value.id in params:
                    out.append(((params[value.id], value.id), kind))
        return out

    def by_hand(self, identifier, path):
        """The family that the choices give a plant, in a file or everywhere, or None."""
        said = self.hand.get(identifier)
        return said.get(path, said.get("*")) if isinstance(said, dict) else said

    def rows(self):
        """([plant row], [by hand]): one row for each plant and family, with the files where it is
        that family's; and the plants whose family nothing gives, with why and where."""
        rows, left = [], []
        for identifier in sorted({*self.placed, *self.rest, *(set(self.hand) & set(self.named))}):
            families = self.placed.get(identifier, {})
            at = {f: {s.split(":")[0] for s in sites} for f, sites in families.items()}
            declared = {p for paths in at.values() for p in paths}
            declared |= {s.split(":")[0] for s, _ in self.rest.get(identifier, ())}
            if isinstance(self.hand.get(identifier), dict):
                declared |= set(self.hand[identifier]) & self.named[identifier]
            named = self.named[identifier]
            namespaced = "." in identifier.split("@")[0]
            if not namespaced:  # A bare plant: where it is declared, and where that is imported.
                named = {p for p in named if self.imports.get(p, set()) & declared}
            files, unknown = defaultdict(set), []
            for path in named | declared:
                family = self.by_hand(identifier, path)
                for found in ({f for f, paths in at.items() if path in paths}, set(at)):
                    if family is None and len(found) == 1:
                        (family,) = found
                if family is None:
                    unknown.append(path)
                else:
                    files[family].add(path)
            if unknown:
                why = f"declared in {sorted(families)}" if families else "its type is not seen"
                left.append((identifier, why, sorted(unknown)))
            for family, paths in sorted(files.items()):
                rows.append(
                    dict(
                        old=[identifier] if namespaced else spellings(identifier),
                        new=new_id(identifier, family),
                        family=family,
                        piece="plant",
                        sites=sorted(families.get(family, [])),
                        files=sorted(paths),
                    )
                )
        return rows, left

    def undeclared(self):
        """The namespaced IDs, cells' own apart, that tests and drivers spell and no declaration
        places: refusal tests' values, and names of their own, for reading."""
        known = {*self.placed, *self.rest, *self.hand}
        return {
            i: sorted(p)
            for i, p in sorted(self.named.items())
            if i not in known and "." in i and not i.startswith("cells.")
        }


# ------------------------------------------------------------------ the hazards

HOLE = "\0"
WORDS = re.compile(r"[^A-Za-z0-9_.@\0]+")
CUTS = {"split", "rsplit", "partition", "rpartition"}
TESTS = {
    "startswith": lambda value, lit: value.startswith(lit),
    "endswith": lambda value, lit: value.endswith(lit),
    "removeprefix": lambda value, lit: value.startswith(lit),
    "removesuffix": lambda value, lit: value.endswith(lit),
    "find": lambda value, lit: value.find(lit),
    "rfind": lambda value, lit: value.rfind(lit),
    "index": lambda value, lit: value.find(lit),
    "rindex": lambda value, lit: value.rfind(lit),
    "fnmatch": lambda value, lit: fnmatchcase(value, lit),
    "fnmatchcase": lambda value, lit: fnmatchcase(value, lit),
    "in": lambda value, lit: lit in value,
}
REGEXES = {"compile", "match", "fullmatch", "search", "findall", "finditer", "sub", "subn", "split"}
CONTEXTS = ("{}", '"{}"', "'{}'", "`{}`", " {} ", "({})", '_ID = "{}"', '"law": "{}",')
# Lines that read module names, not IDs: a prefix test or a cut at a dot there is no hazard.
MODULES = re.compile(
    r"sys\.modules|__name__|\bmodules?\b|\.module\b|alias|\bimport|find_spec|meta_path|fullname|"
    r"\ba\.name\b|\bnode\b|ast\.|package"
)
ORDER = re.compile(
    r"(sorted|\.sort|\bmin|\bmax)\(.*(law_id|kind_id|LAW_ID|operator_id|kinetic_law)"
)
# A word after other text, at a literal's end or before a pattern's next mark: where an expected
# message holds the start of an ID, the move's longer ID no longer follows the text before it.
STARTS = re.compile(r"(?<=[\s\"'(\[:=,])([A-Za-z][A-Za-z0-9_]{4,})(?=$|[.\\(\[*+?])")
# The start of a namespaced ID, wherever it stands: the family now comes between the two.
SPACED = re.compile(
    rf"(?<![A-Za-z0-9_.@/-])({NAMESPACE}\.([A-Za-z][A-Za-z0-9_]*))(?![A-Za-z0-9_@]|\.\w)"
)
# An ID's start up to its @, without the major.
NO_MAJOR = re.compile(rf"(?<![A-Za-z0-9_.@-])((?:{WORD}\.)*{WORD})@(?![A-Za-z0-9_])")
WIDTH = re.compile(r"[<>=|]?[US]([0-9]+)")
FILE_NAME = re.compile(r"\.(md|json|py|npz|npy|csv|tsv|txt|png|svg|log|toml|sh)\b")


def template(node):
    """The text an expression builds, a HOLE for each part known at run time only; None where it
    builds none: an f-string, a chain of +, a % format, a .format call or a "@".join."""
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else None
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) else HOLE for v in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, b = template(node.left), template(node.right)
        if a is None and b is None:
            return None
        return (HOLE if a is None else a) + (HOLE if b is None else b)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        a = template(node.left) if isinstance(node.left, ast.Constant) else None
        return None if a is None else re.sub(r"%[-+ #0-9.]*[a-zA-Z]", HOLE, a)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        held = node.func.value
        if isinstance(held, ast.Constant) and isinstance(held.value, str):
            if node.func.attr == "format":
                return re.sub(r"\{[^{}]*\}", HOLE, held.value)
            if node.func.attr == "join" and held.value == "@":
                return HOLE + "@" + HOLE
    return None


CONTAINERS = {"tuple", "list", "set", "frozenset", "dict", "sorted", "reversed", "enumerate", "zip",
              "iter", "items", "keys", "values", "union", "copy", "fromkeys", "param"}  # fmt: skip
CONSTANT = re.compile(r"_*[A-Z][A-Z0-9_]*")
CALLED = re.compile(rb"\b([A-Za-z_]\w*)\(")
ASSIGNED = re.compile(rb"(?m)^[ ]{0,8}((?:[A-Za-z_]\w*, )*[A-Za-z_]\w*)[ ]*(?::[^=\n]+)?=(?!=)")
# A value of these names is an ID: a cut of one at `_`, or a slice, is a hazard.
LAWLIKE = re.compile(
    r"(\w+_)?(law|law_id|kind_id|model_id|operator_id|solver_id|inner_model|interface|identifier)",
    re.IGNORECASE,
)


def called(node):
    """The last name of an expression: a variable, an attribute, or a subscript's text."""
    if isinstance(node, ast.Call):
        return called(node.args[0]) if getattr(node.func, "id", "") == "str" and node.args else ""
    if isinstance(node, ast.Subscript):
        node = node.slice
    if isinstance(node, ast.Constant):
        return str(node.value)
    return getattr(node, "attr", getattr(node, "id", ""))


class Names:
    """The strings that a Python file's names may hold: constants, the members and the keys of
    literal containers, loops over them, parameters' defaults and the arguments passed for them. A
    name is one set for its whole file, whatever its scope: more than it holds, and never less of
    these. A name that starts with `.` is another file's constant."""

    def __init__(self, tree):
        self.strings, self.names = defaultdict(set), defaultdict(set)
        self.functions, calls = defaultdict(list), []
        for n in ast.walk(tree):
            if isinstance(n, ast.Assign):
                for target in n.targets:
                    self.bind(target, n.value)
            elif isinstance(n, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
                self.bind(n.target, n.value)
            elif isinstance(n, (ast.For, ast.AsyncFor, ast.comprehension)):
                self.bind(n.target, n.iter)
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                args = [*n.args.posonlyargs, *n.args.args]
                for a, default in zip(reversed(args), reversed(n.args.defaults), strict=False):
                    self.hold(a.arg, default)
                for a, default in zip(n.args.kwonlyargs, n.args.kw_defaults, strict=True):
                    self.hold(a.arg, default)
                names = [a.arg for a in args]
                self.functions[getattr(n, "name", "")].append(
                    names[1:] if names[:1] in (["self"], ["cls"]) else names
                )
            elif isinstance(n, ast.Call):
                calls.append(n)
            elif isinstance(n, ast.ImportFrom):
                for x in n.names:
                    self.names[x.asname or x.name].add("." + x.name)
        self.given = defaultdict(list)  # {function: [the parts of a call's arguments]}.
        for n in calls:
            name = n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
            if name == "parametrize" and len(n.args) > 1:
                for x in self.parts(n.args[0])[0]:
                    for one in re.findall(r"\w+", x):
                        self.hold(one, n.args[1])
            args = [(i, self.parts(a)) for i, a in enumerate(n.args)]
            args += [(k.arg, self.parts(k.value)) for k in n.keywords if k.arg]
            if name and any(strings or names for _, (strings, names) in args):
                self.given[name].append(args)
        for name in list(self.functions):
            for strings, names, param in self.passed(name, self.functions[name]):
                self.strings[param] |= strings
                self.names[param] |= names - {param}

    def passed(self, function, signatures):
        """[(strings, names, parameter)]: what this file's calls of a function pass."""
        for args in self.given.get(function, ()):
            for at, (strings, names) in args:
                for params in signatures:
                    if at in params or isinstance(at, int) and at < len(params):
                        yield strings, names, at if at in params else params[at]

    def hold(self, name, value):
        strings, names = self.parts(value)
        self.strings[name] |= strings
        self.names[name] |= names - {name}

    def bind(self, target, value):
        if isinstance(target, (ast.Tuple, ast.List)):
            same = isinstance(value, (ast.Tuple, ast.List)) and len(value.elts) == len(target.elts)
            for i, one in enumerate(target.elts):
                self.bind(one, value.elts[i] if same else value)
        elif isinstance(target, ast.Starred):
            self.bind(target.value, value)
        elif isinstance(target, ast.Name):
            self.hold(target.id, value)
        elif isinstance(target, ast.Attribute):
            self.hold(target.attr, value)

    def parts(self, node):
        """(the strings an expression may hold, the names it may take them from)."""
        strings, names, todo = set(), set(), [node]
        while todo:
            n = todo.pop()
            if isinstance(n, ast.Constant):
                strings |= {n.value} if isinstance(n.value, str) else set()
            elif isinstance(n, (ast.Tuple, ast.List, ast.Set)):
                todo += n.elts
            elif isinstance(n, ast.Dict):
                todo += [*filter(None, n.keys), *n.values]
            elif isinstance(n, (ast.Starred, ast.Subscript, ast.NamedExpr)):
                todo.append(n.value)
            elif isinstance(n, ast.IfExp):
                todo += [n.body, n.orelse]
            elif isinstance(n, ast.BoolOp):
                todo += n.values
            elif isinstance(n, ast.BinOp):
                built = template(n)
                if built is None:
                    todo += [n.left, n.right]  # Containers, or what cannot be seen.
                elif HOLE not in built:
                    strings.add(built)
            elif isinstance(n, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
                todo.append(n.elt)
            elif isinstance(n, ast.Name):
                names.add(n.id)
            elif isinstance(n, ast.Attribute):
                names |= {n.attr} | ({"." + n.attr} if CONSTANT.fullmatch(n.attr) else set())
            elif isinstance(n, ast.Call):
                f = n.func
                if (f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")) in CONTAINERS:
                    todo += [*n.args, *(k.value for k in n.keywords)]
                    strings |= {k.arg for k in n.keywords if k.arg}
                    todo += [f.value] if isinstance(f, ast.Attribute) else []
        return strings, names

    def resolved(self, parts, others):
        """The strings an expression's parts may hold, with the other files' constants (a function
        of a constant's name), and every name on the way."""
        out, names = set(parts[0]), parts[1]
        seen, todo = set(), list(names)
        while todo:
            name = todo.pop()
            if name in seen:
                continue
            seen.add(name)
            if name.startswith("."):
                if CONSTANT.fullmatch(name[1:]):
                    out |= others(name[1:])
            else:
                out |= self.strings.get(name, set())
                todo += self.names.get(name, ())
        return out, seen


class Scanner:
    """The hazards of one map on one tree's files."""

    def __init__(self, files, mp, types=None):
        self.files, self.mp = files, mp
        # The constants of a name, the names of a file and the functions looked up, by need.
        self.held_by, self.file_names, self.looked_up, self.indexed = {}, {}, set(), None
        self.pairs = sorted(mp.new.items())
        self.short = {o.rsplit(".", 1)[-1].split("@")[0] for o in mp.new}  # Names alone.
        self.longest = max(map(len, mp.new.values()), default=0)
        self.whole = {*mp.new, *mp.news}  # A tree may hold either: a branch, after the move.
        self.types = types or {}
        self.found = []
        self.known = {}  # What a literal, a pattern or a template was already found to do.
        self.inside = []  # (path, line, ID): IDs inside longer strings, which the rule rewrites.
        self.outside = []  # (path, line, text): what Python in scope names outside the tree.
        self.read_by = []  # (left file, reader, line): a live reader of a file the move leaves.
        self.frozen_code = []  # What frozen Python does with part of an ID, as hazards.
        self.left, self.bases, self.modules = {}, Counter(), {}

    def leave(self, left):
        """The files that the move leaves and that hold old spellings, whose readers are listed."""
        self.left = left
        self.bases = Counter(Path(p).name for p in self.files)
        self.modules = {
            p[:-3].replace("/", ".").removesuffix(".__init__"): p
            for p in self.files
            if p.endswith(".py") and p.startswith(("tests/", "validation/", "scripts/"))
        }
        self.named_left = defaultdict(list)
        for path in left:
            if not path.endswith(".py"):
                self.named_left[Path(path).name].append(path)

    def names_left(self, path, node):
        """A string that names a left data file: its name alone where no other file has it, or from
        a folder above it, or with a folder of its path."""
        said = node.value
        for target in self.named_left.get(said.rsplit("/", 1)[-1], ()) if self.left else ():
            folder = str(Path(path).parent)
            if (
                self.bases[Path(target).name] == 1
                or ("/" in said and target.endswith("/" + said.lstrip("./")))
                or f"{Path(target).parent}/".startswith(f"{folder}/")
            ):
                self.read_by.append((target, path, node.lineno))

    def add(self, cls, path, line, text, what):
        self.found.append(
            dict(cls=cls, path=path, line=line, text=" ".join(str(text).split())[:200], what=what)
        )

    def index(self):
        """({function: [the files that call it]}, {constant: [the files that assign it]}) of the
        Python files in scope."""
        if self.indexed is None:
            calls, constants = defaultdict(list), defaultdict(list)
            for path, (_, data) in self.files.items():
                if path.endswith(".py") and path.startswith(tuple(self.mp.scope["dirs"])):
                    for name in set(CALLED.findall(data)):
                        calls[name.decode()].append(path)
                    assigned = {x for m in ASSIGNED.findall(data) for x in m.split(b", ")}
                    for name in assigned:
                        constants[name.decode()].append(path)
            self.indexed = calls, constants
        return self.indexed

    def names_of(self, path, tree=None):
        if path not in self.file_names:
            try:
                self.file_names[path] = Names(tree or ast.parse(self.files[path][1]))
            except (SyntaxError, ValueError):
                self.file_names[path] = None
        return self.file_names[path]

    def others(self, name):
        """The strings of every constant of this name, in any Python file in scope."""
        if name not in self.held_by:
            self.held_by[name] = found = set()  # One that needs itself ends here.
            for path in self.index()[1].get(name, ()):
                names = self.names_of(path)
                if names is not None:
                    found |= names.resolved((set(), {name}), self.others)[0]
        return self.held_by[name]

    def through(self, path, tree, node):
        """The strings that an argument which is no literal may hold: the names it takes them from,
        and for a parameter what the calls of its function in other files pass."""
        names = self.names_of(path, tree)
        if names is None:
            return set()
        _, seen = names.resolved(names.parts(node), self.others)
        for function, signatures in names.functions.items():
            if function and (path, function) not in self.looked_up:
                if any(p in seen for params in signatures for p in params):
                    self.looked_up.add((path, function))
                    module = Path(path).stem.encode()  # A caller elsewhere names the module.
                    for q in self.index()[0].get(function, ()):
                        calls = q != path and module in self.files[q][1]
                        other = self.names_of(q) if calls else None
                        if other is not None:
                            for strings, taken, param in other.passed(function, signatures):
                                given = other.resolved((strings, taken), self.others)[0]
                                names.strings[param] |= given
        return names.resolved(names.parts(node), self.others)[0]

    def changes(self, name, lit):
        """The old spellings for which a test of part of an ID answers otherwise after the move."""
        if (name, lit) not in self.known:
            test = TESTS[name]
            self.known[name, lit] = [o for o, n in self.pairs if test(o, lit) != test(n, lit)]
        return self.known[name, lit]

    # -------------------------------------------------------------- one file

    def scan(self):
        for path, (_, data) in sorted(self.files.items()):
            why = self.mp.excluded(path)
            if path.endswith(".py") and (why == "frozen" or path in self.mp.left):
                self.frozen(path, text_of(data))
            if why is not None:
                continue
            text = text_of(data)
            if text is None:
                if any(o.encode() in data for o in self.mp.new):
                    self.add("not text", path, 0, path, "not UTF-8, and it holds an old spelling")
                continue
            after = self.mp.text(path, text) if "@" in text else text
            if "@" in text:
                self.text(path, text, after)
            if path.endswith(".py"):
                self.python(path, text, after)
            elif path.endswith(".json") and after != text:
                self.values(path, text, after)
                self.sorted_json(path, text, after)
        return self.found

    def frozen(self, path, text):
        """What frozen code does with part of an ID: no edit can help it, so its readers must."""
        kept = self.found, self.inside, self.outside, self.read_by
        self.found, self.inside, self.outside, self.read_by = [], [], [], []
        if text is not None:
            self.python(path, text, text)
        parts = {"partial", "cut", "regex", "name", "computed"}
        self.frozen_code += [h for h in self.found if h["cls"] in parts]
        self.found, self.inside, self.outside, self.read_by = kept

    def text(self, path, text, after):
        for line, kind, word in self.mp.left_over(path, after):
            cls = "escaped dot" if kind == "after '.'" and "\\." in word else "unseen"
            self.add(cls, path, line, word, f"an old spelling the token rule leaves ({kind})")
        if path in self.mp.test_ids or not AN_ID.search(text.encode()):
            return
        kept = kept_lines(text, path.endswith(".py"))
        for i, line in enumerate(lines_of(text), 1):
            if "@" not in line or i in kept:
                continue
            for m in TOKEN.finditer(line):
                if m[1] not in self.mp.new:
                    continue
                said = line.strip()
                if line[m.start() - 1 : m.start()] == "/":
                    if any(p.start() <= m.start() < p.end() for p in PAGE.finditer(line)):
                        self.add(
                            "page path", path, i, said, "a library page's path: the page rule's"
                        )
                    else:
                        self.add("path", path, i, said, "an old spelling inside a path")
                elif FILE_NAME.match(line, m.end()):
                    self.add("file name", path, i, said, "an old spelling that names a file")
                if re.search(r"\btest_\w+\[[^\]]*$", line[: m.start()]):
                    self.add("test ID", path, i, said, "a recorded test ID holds an old spelling")

    def held(self, path, line, text):
        table = self.mp.table(path)
        return [(path, line, m[1]) for m in TOKEN.finditer(text) if m[1] in table]

    def values(self, path, text, after):
        if path.endswith(".json"):
            for value in decoded(path, text) or ():
                if "@" in value and ID.fullmatch(value) is None:
                    self.inside += self.held(path, 0, value)
        for _, why in decoded_problems(path, text, after, self.mp):
            self.add("decoded", path, 0, why, "the text rule and the decoded value disagree")

    def one_key(self, path, line, keys):
        """Keys of one mapping or members of one set that are two before and one after."""
        table, seen = self.mp.table(path), {}
        for key in keys:
            if isinstance(key, str):
                new = table.get(key, key)
                if seen.setdefault(new, key) != key:
                    self.add("one key", path, line, f"{seen[new]} and {key}", f"both become {new}")

    def sorted_json(self, path, text, after):
        """A JSON file written with its keys sorted, which the move leaves unsorted."""

        def pairs(found):
            self.one_key(path, 0, [k for k, _ in found])
            return dict(found)

        try:
            a, b = json.loads(text, object_pairs_hook=pairs), json.loads(after)
        except ValueError:
            return
        for indent in (None, 1, 2, 4):
            for ascii_only in (True, False):
                options = dict(indent=indent, sort_keys=True, ensure_ascii=ascii_only)
                if json.dumps(a, **options) == text.rstrip("\n"):
                    if json.dumps(b, **options) != after.rstrip("\n"):
                        self.add("sorted JSON", path, 0, path, "its keys are sorted, and not after")
                    return

    # -------------------------------------------------------------- a Python file

    def python(self, path, text, after):
        try:
            tree = ast.parse(text)
        except SyntaxError:
            if after != text:
                self.add("not parsed", path, 0, path, "Python that does not parse")
            return
        lines = lines_of(text)

        def source(node):
            """A node's own text, on one line."""
            rows = lines[node.lineno - 1 : node.end_lineno]
            if not rows:
                return ""
            rows[-1] = rows[-1].encode()[: node.end_col_offset].decode(errors="replace")
            rows[0] = rows[0].encode()[node.col_offset :].decode(errors="replace")
            return " ".join(" ".join(rows).split())[:200]

        def around(node):
            return "\n".join(lines[max(0, node.lineno - 5) : node.end_lineno + 2])

        self.tree = tree
        inside = set()  # The operands of a chain of +, which the chain's own template covers.
        prose = set()  # Docstrings and bare strings.
        strange = []
        for n in ast.walk(tree):
            if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add):
                inside |= {id(n.left), id(n.right)}
            elif isinstance(n, ast.Expr):
                prose.add(id(n.value))
            if isinstance(n, (ast.JoinedStr, ast.BinOp, ast.Call)) and id(n) not in inside:
                self.computed(path, n, source)
            if isinstance(n, ast.JoinedStr):
                self.adjacent(path, n, source)
            elif isinstance(n, ast.Call):
                self.call(path, n, source, around)
            elif isinstance(n, ast.Compare):
                self.membership(path, n, source)
            elif isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Slice):
                if LAWLIKE.fullmatch(called(n.value)) and (n.slice.lower or n.slice.upper):
                    self.add("cut", path, n.lineno, source(n), "a slice of an ID")
            elif isinstance(n, (ast.Dict, ast.Set)) and after != text:
                keys = n.keys if isinstance(n, ast.Dict) else n.elts
                self.one_key(path, n.lineno, [getattr(k, "value", None) for k in keys])
            elif isinstance(n, ast.Constant) and isinstance(n.value, str):
                m = WIDTH.fullmatch(n.value) if len(n.value) < 8 else None
                said = lines[n.lineno - 1].strip()
                if m and 1 < int(m[1]) < self.longest and re.search(r"dtype|astype", said):
                    self.add("width", path, n.lineno, said,
                             f"a text width below the longest new ID's {self.longest}")  # fmt: skip
                if id(n) not in prose:
                    self.message(path, n, source)
                    self.without_major(path, n, source)
                    self.names_left(path, n)
                    if n.value.startswith("/mnt/"):
                        self.outside.append((path, n.lineno, n.value))
                    if "@" in n.value and ID.fullmatch(n.value) is None:
                        self.inside += self.held(path, n.lineno, n.value)
                if "@" in n.value and after == text:
                    strange += [
                        n for x in lines_of(n.value) if self.mp.line(x, None, TOKEN, path) != x
                    ]
        if self.left:
            for target in python_imports(path, tree, self.modules) & set(self.left):
                self.read_by.append((target, path, 0))
        if after != text:
            self.values(path, text, after)
        elif strange and not kept_lines(text, True):  # A decoded ID that no text rule rewrote.
            for n in strange:
                self.add("decoded", path, n.lineno, source(n), "an old spelling in a decoded value")
        if path.startswith(LIVE):
            for i, line in enumerate(lines, 1):
                if ORDER.search(line) and "qualified(" not in line:
                    self.add("order", path, i, line.strip(), "a sort over declared spellings")

    def message(self, path, node, source):
        for m in SPACED.finditer(node.value):
            if not re.search(r"[_0-9]", m[2]) and m[2] not in self.short:
                continue  # A plain word: a module's name, or a file's.
            if m[1] not in self.known:
                self.known[m[1]] = next((o for o in self.mp.new if o.startswith(m[1])), None)
            if self.known[m[1]]:
                what = f"{m[1]!r} is the start of {self.known[m[1]]}, and not of its new ID"
                self.add("message", path, node.lineno, source(node), what)
                return
        for m in STARTS.finditer(node.value):
            word = m[1]
            if not re.search(r"[_0-9]", word):
                continue  # A plain word.
            if word in self.short and m.end() < len(node.value):
                continue  # A whole name before a dot or a pattern's mark: a module, not an ID.
            if word not in self.known:
                starts = [n for n in self.mp.names if n.startswith(word)]
                self.known[word] = starts[0] if starts else None
            if self.known[word]:
                what = f"{word!r} is the start of {self.known[word]}, after other text"
                self.add("message", path, node.lineno, source(node), what)
                return

    def without_major(self, path, node, source):
        for m in NO_MAJOR.finditer(node.value):
            if m[1].removeprefix(NAMESPACE + ".") in self.short:
                self.add("partial", path, node.lineno, source(node), f"{m[0]!r} without its major")
                return

    def computed(self, path, node, source):
        built = template(node)
        if built is None:
            return
        if HOLE not in built:  # Literals joined by +, whose ends no token rule joins.
            parts = [n.value for n in ast.walk(node) if isinstance(n, ast.Constant)]
            if "@" in built and len(parts) > 1:
                token = [m[1] for m in TOKEN.finditer(built) if m[1] in self.mp.table(path)]
                whole = [m[1] for x in parts for m in TOKEN.finditer(str(x))]
                split = [x for x in token if token.count(x) > whole.count(x)]
                if split:
                    self.add("computed", path, node.lineno, source(node),
                             f"joined literals make {split[0]}")  # fmt: skip
            return
        for word in WORDS.split(built):
            literal = word.replace(HOLE, "")
            if HOLE not in word or not ("@" in literal or word.startswith("cells." + HOLE)):
                continue
            if word not in self.known:
                pattern = re.compile("[A-Za-z0-9_.@]*".join(map(re.escape, word.split(HOLE))))
                self.known[word] = [o for o, _ in self.pairs if pattern.fullmatch(o)]
            hits = self.known[word]
            if hits:
                self.add(
                    "computed",
                    path,
                    node.lineno,
                    source(node),
                    f"{word.replace(HOLE, '{}')} can be {hits[0]} (of {len(hits)})",
                )
                return

    def adjacent(self, path, node, source):
        for i, part in enumerate(node.values):
            if not isinstance(part, ast.Constant) or "@" not in str(part.value):
                continue
            for m in TOKEN.finditer(part.value):
                if m[1] not in self.mp.new:
                    continue
                before = i > 0 and m.start() == 0
                after = i + 1 < len(node.values) and m.end() == len(part.value)
                if before or after:
                    self.add("f-string", path, node.lineno, source(node),
                             f"{m[1]} touches a part known at run time only")  # fmt: skip

    def call(self, path, n, source, around):
        f = n.func
        name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
        literals = [
            a.value for a in n.args if isinstance(a, ast.Constant) and isinstance(a.value, str)
        ]
        literals += [
            e.value for a in n.args if isinstance(a, (ast.Tuple, ast.List)) for e in a.elts
            if isinstance(e, ast.Constant) and isinstance(e.value, str)
        ]  # fmt: skip
        if name in (*TESTS, "match", "search", "fullmatch", "compile") and self.by_name(n, name):
            self.named(path, n, name, source)
        if not literals:
            return
        if name in CUTS and literals[0] == "_" and isinstance(f, ast.Attribute):
            if LAWLIKE.fullmatch(called(f.value)):
                self.add("cut", path, n.lineno, source(n), "cuts an ID at '_'")
        if name in CUTS and literals[0] in ("@", ".", "cells.", "@1"):
            if literals[0] != "." or not MODULES.search(around(n)):
                self.add("cut", path, n.lineno, source(n), f"cuts a text at {literals[0]!r}")
        elif name == "replace" and ("@" in literals[0] or literals[0].startswith("cells.")):
            if literals[0] not in self.whole:
                self.add("cut", path, n.lineno, source(n), f"replaces {literals[0]!r} in a text")
        if name in TESTS:
            for lit in literals:
                if name in ("find", "rfind", "index", "rindex") and lit not in ("@", "."):
                    continue  # A list's index, or a place in other text.
                hits = self.changes(name, lit) if len(lit) > 1 or lit == "@" else []
                if hits and lit not in self.whole:
                    if lit in ("cells", "cells.") and MODULES.search(around(n)):
                        continue  # It tests module names.
                    self.add(
                        "partial",
                        path,
                        n.lineno,
                        source(n),
                        f"{name} {lit!r}: not so for {hits[0]} (of {len(hits)})",
                    )
        if (
            name in REGEXES
            and isinstance(f, ast.Attribute)
            and isinstance(f.value, ast.Name)
            and f.value.id == "re"
            and isinstance(n.args[0], ast.Constant)
        ):
            self.regex(path, n, literals[0], source)

    @staticmethod
    def by_name(n, name):
        """Whether a test's argument, or a pattern, is no literal: a name that may hold one."""
        args = n.args[1:] if name.startswith("fnmatch") else n.args[:1]
        return args and not isinstance(args[0], (ast.Constant, ast.JoinedStr, ast.Tuple, ast.List))

    def named(self, path, n, name, source):
        """A test of part of an ID, or a pattern, that reads it through a name."""
        is_test = name in TESTS
        if name in ("find", "rfind", "index", "rindex"):
            return  # A list's index, or a place in other text.
        if not is_test and not (
            isinstance(n.func, ast.Attribute) and getattr(n.func.value, "id", "") == "re"
        ):
            return
        arg = n.args[1] if name.startswith("fnmatch") else n.args[0]
        found = []
        for lit in sorted(self.through(path, self.tree, arg)):
            if is_test and lit not in self.whole and re.search(r"[_0-9@.]", lit):
                hits = self.changes(name, lit)  # Not a plain word: a name holds those at large.
                found += [f"{lit!r}: not so for {hits[0]} (of {len(hits)})"] if hits else []
            elif not is_test and len(lit) < 400:
                self.regex(path, n, lit, source)
        if found:
            what = f"{name}, by name, {found[0]}; strings that answer otherwise: {len(found)}"
            self.add("partial", path, n.lineno, source(n), what)

    def regex(self, path, n, pattern, source):
        if ("regex", pattern) not in self.known:
            self.known["regex", pattern] = self.rereads(pattern)
        if self.known["regex", pattern]:
            self.add("regex", path, n.lineno, source(n), self.known["regex", pattern])

    def rereads(self, pattern):
        """How a pattern reads an old spelling and its new ID differently, or None."""
        try:
            rx = re.compile(pattern)
        except re.error:
            return None
        for old, new in self.pairs:
            for context in CONTEXTS:
                a, b = self.reads(rx, context, old), self.reads(rx, context, new)
                if a != b and (a[0] or "@" in pattern):
                    return f"{pattern[:60]!r} reads {a} of {old} and {b} of its new ID"
        return None

    @staticmethod
    def reads(rx, context, identifier):
        """What a pattern reads of an ID in a context: whether it matches, and the ID's part in
        each group ("ID" for the whole)."""
        text = context.format(identifier)
        m = rx.search(text)
        if m is None:
            return (False,)
        parts = []
        for g in (m[0], *m.groups()):
            said = g or ""
            if "ID" in said.replace(identifier, "ID"):
                parts.append("ID" if said == identifier else "ID in a text")
            else:
                parts.append("a part" if said and said in identifier else "text")
        return (True, *parts)

    def membership(self, path, n, source):
        if len(n.ops) != 1:
            return
        left, right = n.left, n.comparators[0]
        if isinstance(n.ops[0], (ast.In, ast.NotIn)):
            if (
                isinstance(left, ast.Constant)
                and isinstance(left.value, str)
                and len(left.value) > 2
                and left.value not in self.whole
                and isinstance(right, (ast.Name, ast.Attribute, ast.Subscript, ast.Call))
            ):
                hits = self.changes("in", left.value)
                if hits:
                    self.add(
                        "partial",
                        path,
                        n.lineno,
                        source(n),
                        f"{left.value!r} in it: not so for {hits[0]} (of {len(hits)})",
                    )
            elts = right.elts if isinstance(right, (ast.Tuple, ast.List, ast.Set)) else []
        else:
            elts = [left, right]
        for e in elts:
            if isinstance(e, ast.Constant) and isinstance(e.value, str) and e.value in self.short:
                self.add("name", path, n.lineno, source(n),
                         f"compares with {e.value!r}, an ID's name without its major")  # fmt: skip


# -------------------------------------------------------------- hashes


def hex_words(files, mp):
    """{hex word: [paths]} of the hex literals, 12 to 64 digits, of the files in scope."""
    out = defaultdict(set)
    for path, (_, data) in files.items():
        if path.startswith(tuple(mp.scope["dirs"])) and not path.startswith(SELF):
            text = text_of(data)
            if text is not None:
                for m in HEX.finditer(text):
                    out[m[0]].add(path)
    return out


def digests_of(data):
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "sha1": hashlib.sha1(data).hexdigest(),
        "md5": hashlib.md5(data).hexdigest(),
        "git blob": hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest(),
    }


def quoted_in(digest, words, lengths):
    """Where a digest, or a prefix of it of 12 digits or more, is quoted."""
    return {
        p for n in lengths if n <= len(digest) and digest[:n] in words for p in words[digest[:n]]
    }


def hash_pins(files, mp, changed):
    """[(pinned path, kind, [pinning paths])] of the files the move changes."""
    words = hex_words(files, mp)
    lengths = sorted({len(w) for w in words})
    out = []
    for path in sorted(changed):
        for kind, digest in digests_of(files[path][1]).items():
            by = quoted_in(digest, words, lengths) - {path}
            if by:
                out.append((path, kind, sorted(by)))
    return out, words


def objects_of(value):
    if isinstance(value, (dict, list)):
        yield value
        for v in value.values() if isinstance(value, dict) else value:
            yield from objects_of(v)


CANONICAL = {
    "compact": dict(sort_keys=True, separators=(",", ":")),
    "compact, not ASCII only": dict(sort_keys=True, separators=(",", ":"), ensure_ascii=False),
    "compact, unsorted": dict(separators=(",", ":")),
    "default": dict(sort_keys=True),
    "default, not ASCII only": dict(sort_keys=True, ensure_ascii=False),
    "default, unsorted": dict(),
    "indent 1": dict(sort_keys=True, indent=1),
    "indent 2": dict(sort_keys=True, indent=2),
}


def digest_pins(files, changed, words):
    """[(path, how, digest, [quoting paths])]: digests of a JSON file's own nested objects, in each
    canonical form, that a file in scope quotes."""
    out = []
    for path in sorted(changed):
        if not path.endswith(".json"):
            continue
        try:
            data = json.loads(text_of(files[path][1]))
        except ValueError:
            continue
        seen = set()
        for obj in objects_of(data):
            for how, options in CANONICAL.items():
                try:
                    text = json.dumps(obj, **options)
                except ValueError:
                    continue
                for tail in ("", "\n"):
                    digest = hashlib.sha256((text + tail).encode()).hexdigest()
                    if digest in words and digest not in seen:
                        seen.add(digest)
                        out.append((path, how, digest, sorted(words[digest])))
    return out


def reviewed_by(hazard, reviews):
    for i, r in enumerate(reviews):
        if (
            hazard["cls"] in r["cls"]
            and fnmatchcase(hazard["path"], r["path"])
            and re.search(r.get("text", ""), hazard["text"])
        ):
            return i
    return None


def moved(files):
    """Whether the move has reached a tree: its table of renamed IDs holds some."""
    return bool(A_MAJOR.search(files.get(RENAMED, ("", b""))[1]))


def run_scan(files, mp, choices):
    """Every hazard of the map on the files, each with the review that settles it, if any."""
    _, report = transform(files, mp, renamed=False)
    changed = set(report["files"])
    scanner = Scanner(files, mp)
    scanner.leave(report["left"])
    hazards = scanner.scan()
    pins, words = hash_pins(files, mp, changed)  # Only the files the move changes.
    listed = {r["path"]: r for r in choices["pinned"]}
    for path, kind, by in pins:
        row = listed.get(path)
        what = f"its {kind} is quoted by {', '.join(by)}"
        scanner.add("hash pin", path, 0, f"{path} {kind}", what)
        if row is not None:
            hazards[-1]["choice"] = row["choice"]
    nested = defaultdict(list)
    for path, how, digest, by in digest_pins(files, changed, words):
        nested[path].append((how, digest, by))
    for path, rows in sorted(nested.items()):
        row = listed.get(path)
        scanner.add(
            "nested digest",
            path,
            0,
            f"{path} {len(rows)} digests",
            "; ".join(f"{how}: {d[:12]} in {by[0]}" for how, d, by in rows),
        )
        if row is not None:
            hazards[-1]["choice"] = row["choice"]
    if mp.doc.get("types") and not moved(files):  # After it, the strict grammar asks for them.
        rows, by_hand = Plants(files, mp, mp.doc["types"], choices["plants"]["families"]).rows()
        held = {(o, p) for p, table in mp.plants.items() for o in table}
        for row in rows:
            for path in row["files"]:
                if (row["old"][0], path) not in held:
                    what = f"a {row['family']} plant that the map lacks"
                    scanner.add("plant", path, 0, row["old"][0], what)
        for identifier, why, paths in by_hand:
            scanner.add("plant", paths[0], 0, identifier, f"a plant to place by hand: {why}")
    used = Counter()
    for h in hazards:
        i = reviewed_by(h, choices["reviewed"])
        if i is not None:
            h["reviewed"] = choices["reviewed"][i]["reason"]
            used[i] += 1
        elif "choice" in h:
            h["reviewed"] = f"the choice is made: {h['choice']}"
    stale = [r for i, r in enumerate(choices["reviewed"]) if not used[i]]
    report["inside"] = scanner.inside
    report["outside"] = scanner.outside
    report["frozen_code"] = scanner.frozen_code
    report["left_readers"] = left_readers(files, report["left"], scanner.read_by)
    return hazards, report, stale


def left_readers(files, left, reads):
    """One row for each live reader of a file that the move leaves with old spellings, and whether
    it names the table of renamed IDs. A reader that builds the file's name is not seen."""
    first = {}
    for target, reader, line in reads:
        first.setdefault((target, reader), line)
    return [
        dict(
            left=target,
            why=left[target][0],
            reader=reader,
            line=line,
            names_the_table=b"id_table" in files[reader][1],
        )
        for (target, reader), line in sorted(first.items())
    ]


# ------------------------------------------------------------------ actions: check and table


def data_paths(args):
    tree = Path(args.tree)
    out = []
    for value, default in ((args.choices, CHOICES), (args.map, MAP), (args.frozen, FROZEN)):
        out.append(Path(value) if value else tree / default)
    return out


def revision_of(tree):
    """The head, and whether a tracked file other than the tool's own data is changed."""
    head = git("rev-parse", "HEAD", cwd=tree).decode().strip()
    status = git("status", "--porcelain", "--untracked-files=no", cwd=tree).decode()
    return dict(head=head, dirty=any(not x[3:].startswith(SELF) for x in status.splitlines()))


def stale_map(mp, tree, rev):
    """Why a map is not of a tree that the move has not reached: an ID that came since has no row.
    None where it is, and after the move (a branch in flight merges main and is rewritten with
    main's map)."""
    renamed = git("ls-tree", "-r", "--name-only", rev, "--", RENAMED, cwd=tree).strip()
    if renamed and A_MAJOR.search(git("cat-file", "blob", f"{rev}:{RENAMED}", cwd=tree)):
        return None
    revision = mp.doc["revision"]
    if revision["dirty"]:
        return "the map is of a tree with uncommitted changes"
    try:
        names = git("diff", "--name-only", "-z", revision["head"], rev, cwd=tree).decode()
    except Refused:
        return f"the map's revision {revision['head']} is not in this repository"
    since = [p for p in names.split("\0") if in_scope(p, mp.scope) and not p.startswith(SELF)]
    if since:
        said = f"{len(since)} files in scope changed since the map's revision"
        return f"{said} {revision['head'][:8]}: write the table again (first: {since[0]})"
    return None


def key_seeds(choices):
    return [(s["module"], s["name"]) for s in choices["seeds"] if s.get("keys")]


def cmd_check(args):
    choices_path, _, frozen_path = data_paths(args)
    choices = load_choices(choices_path)
    files = worktree_files(args.tree)
    source = Source(files, choices["scope"])
    engine = engine_dump(args.tree, key_seeds(choices))
    rows, problems = build_rows(choices, engine, source)
    problems += choices_problems(choices, rows, engine, source, files)
    print(
        json.dumps(
            dict(
                rows=len(rows),
                seeds=len(choices["seeds"]),
                kept={k: len(v) for k, v in choices["keep"]["ids"].items()},
                pinned=dict(Counter(r["choice"] for r in choices["pinned"])),
                reviewed=len(choices["reviewed"]),
                frozen=len(read_frozen(frozen_path)),
                problems=problems,
            ),
            indent=1,
        )
    )
    return 1 if problems else 0


def cmd_table(args):
    choices_path, _, _ = data_paths(args)
    choices = load_choices(choices_path)
    files = worktree_files(args.tree)
    source = Source(files, choices["scope"])
    engine = engine_dump(args.tree, key_seeds(choices))
    revision = revision_of(args.tree)
    doc, rows, report = make_map(choices, engine, source, revision, args.rehearsal)
    doc["types"] = engine_types(engine)
    planted, by_hand = Plants(
        files,
        Map(doc, frozen_list(args.tree, data_paths(args)[2], choices)),
        doc["types"],
        choices["plants"]["families"],
    ).rows()
    if choices["plants"]["apply"]:
        doc["plants"] = planted
    found = report["collisions"]
    stops = [f"a piece or a seed: {p}" for p in report["problems"]]
    stops += [f"a choice: {p}" for p in choices_problems(choices, rows, engine, source, files)]
    stops += [f"a module did not import: {m}: {e}" for m, e in report["not_imported"].items()]
    stops += [f"unplaced: {i} ({why}): {'; '.join(sites)}" for i, why, sites in report["unplaced"]]
    stops += [
        f"collision, {check}: {item}"
        for check, items in found.items()
        if not check.startswith("listed")
        for item in items
    ]
    ids = engine["ids"]  # The grammar module: the new IDs keep it.
    piece = re.compile(ids["piece"])
    stops += [f"registry/ids.py's pattern refuses {r['new']}" for r in doc["rows"]
              if not piece.fullmatch(r["new"])]  # fmt: skip
    absent = sorted({r["family"] for r in doc["rows"]} - set(ids["families"]))
    stops += [f"registry/ids.py has no family word {w}" for w in absent]
    if not args.rehearsal:
        stops += [f"a plant's family is not seen: {i} ({why}): {s[0]}" for i, why, s in by_hand]
    print(
        json.dumps(
            dict(
                revision=revision,
                final=doc["final"],
                rows=len(doc["rows"]),
                old_spellings=sum(len(r["old"]) for r in doc["rows"]),
                by_family=dict(Counter(r["family"] for r in doc["rows"])),
                kept={k: len(v) for k, v in doc["kept"].items()},
                classes=report["classes"],
                plants=dict(Counter(r["family"] for r in planted)),
                plants_by_hand=[f"{i} ({why}): {s[0]}" for i, why, s in by_hand],
                collisions=found,
            ),
            indent=1,
        )
    )
    if args.tsv:
        Path(args.tsv).write_text("\n".join(tsv_lines(rows)) + "\n")
    if args.compare:
        result = compare_tables(tsv_lines(rows), Path(args.compare).read_text().splitlines())
        print(json.dumps(dict(compared_with=Path(args.compare).name, **result), indent=1))
    if stops:
        for line in stops:
            print(f"refused: {line}", file=sys.stderr)
        return 2
    if args.out:
        Path(args.out).write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    if not doc["final"]:
        print("a rehearsal: this map is not final", file=sys.stderr)
    return 0


def by_hand_found(path, hazards, files, mp):
    """The rows of a by-hand list (site, class, needed, fails, what) against the hazards: for each
    row the hazards at its site, or what the tool does there instead; and the hazards that no row
    names."""
    rows, named = [], set()
    for line in Path(path).read_text().splitlines()[1:]:
        site, cls, needed, fails, what = line.split("\t")
        name, _, number = site.rpartition(":")
        if not number.isdigit():
            name, number = site, None
        wanted = {int(number)} if number else set()
        for said in re.findall(r"lines? ([0-9, and]+)|\(((?:\w+ )*[0-9]+(?:, [0-9]+)*)\)", what):
            wanted |= {int(x) for x in re.findall(r"[0-9]+", " ".join(said))}
        here = [h for h in hazards if h["path"] == name and (not wanted or h["line"] in wanted)]
        named |= {id(h) for h in here}
        done = None
        if name in mp.test_ids:
            done = "its test IDs are mapped by the ids rule"
        elif name in mp.plants and any(
            mp.line(x, None, TOKEN, name) != x
            for i, x in enumerate(lines_of(text_of(files[name][1])), 1)
            if i in wanted
        ):
            done = "its plants are renamed by the map"
        elif not in_scope(name, mp.scope):
            done = "outside the scope"
        rows.append(
            dict(
                site=site,
                cls=cls,
                needed=needed,
                found=sorted({f"{h['cls']}:{h['line']}" for h in here}),
                instead=done if not here else None,
            )
        )
    beyond = [h for h in hazards if id(h) not in named]
    return rows, beyond


def skipped_found(path, hazards, files, mp):
    """The rows of a skipped list ([kind, path, line, text]) against what the tool does."""
    out = Counter()
    left = []
    at = {(h["path"], h["line"]): h["cls"] for h in hazards}
    for kind, name, line, text in json.loads(Path(path).read_text()):
        old = lines_of(text_of(files[name][1]))[line - 1]
        if name in mp.test_ids and TEST_ID.sub(lambda m: mp.test_id(m[0]), old) != old:
            out["mapped by the ids rule"] += 1
        elif mp.pages(old) != old:
            out["mapped by the page rule"] += 1
        elif (name, line) in at:
            out[f"a hazard: {at[name, line]}"] += 1
        else:
            left.append([kind, name, line, text])
    return dict(out), left


def cmd_scan(args):
    choices_path, map_path, frozen_path = data_paths(args)
    choices = load_choices(choices_path)
    mp = load_map(map_path, frozen_list(args.tree, frozen_path, choices))
    files = worktree_files(args.tree)
    hazards, report, stale = run_scan(files, mp, choices)
    standing = [h for h in hazards if "reviewed" not in h]
    summary = dict(
        kind=REPORT_KIND,
        final=mp.final,
        files_to_change=len(report["files"]),
        files_left_that_hold_old_spellings=dict(Counter(w for w, _ in report["left"].values())),
        pages=report["pages"],
        hazards=dict(Counter(h["cls"] for h in hazards)),
        standing=dict(Counter(h["cls"] for h in standing)),
        inside_longer_strings=dict(Counter(scope_of(p) for p, _, _ in report["inside"])),
        readers_of_files_left=dict(
            Counter(
                ("names the table" if r["names_the_table"] else "does not name the table")
                + f", {r['why']}"
                for r in report["left_readers"]
            )
        ),
        frozen_code_that_reads_part_of_an_id=len(report["frozen_code"]),
        names_paths_outside_the_tree=len({p for p, _, _ in report["outside"]}),
        stale_reviews=len(stale),
    )
    if args.by_hand:
        rows, beyond = by_hand_found(args.by_hand, hazards, files, mp)
        summary["by_hand"] = dict(
            rows=len(rows),
            found=sum(bool(r["found"]) for r in rows),
            done_otherwise=[f"{r['site']}: {r['instead']}" for r in rows if r["instead"]],
            not_found=[r["site"] for r in rows if not (r["found"] or r["instead"])],
            standing_beyond_them=len([h for h in beyond if "reviewed" not in h]),
        )
        report["by_hand"] = rows
        report["beyond"] = beyond
    if args.skipped:
        found, left = skipped_found(args.skipped, hazards, files, mp)
        summary["skipped"] = dict(found=found, not_found=left)
    if args.out:
        doc = dict(summary, standing_list=standing, hazard_list=hazards, stale=stale, report=report)
        Path(args.out).write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(summary, indent=1))
    for h in standing[: args.show]:
        print(f"{h['cls']}: {h['path']}:{h['line']}: {h['text'][:110]}  [{h['what'][:110]}]")
    if len(standing) > args.show:
        print(f"... and {len(standing) - args.show} more (--out has them all)")
    return 1 if standing else 0


# ------------------------------------------------------------------ actions: apply and verify


def cmd_apply(args):
    choices_path, map_path, frozen_path = data_paths(args)
    choices, tree = load_choices(choices_path), Path(args.tree)
    mp = load_map(map_path)
    if git("status", "--porcelain", "--untracked-files=no", cwd=tree).strip():
        raise Refused(f"{tree} has uncommitted changes: apply works on a clean head")
    if not mp.final and not args.rehearsal:
        raise Refused("the map is a rehearsal's, not final (--rehearsal for a scratch copy)")
    stale = stale_map(mp, tree, "HEAD")
    if stale and not args.paths and not args.rehearsal:
        raise Refused(stale)
    files = worktree_files(tree)
    mp.frozen = frozen_list(tree, frozen_path, choices, "HEAD")
    if args.paths:  # A lane's own files: the token rule alone, wherever they are.
        return apply_paths(tree, files, mp, args)
    hazards, _, _ = run_scan(files, mp, choices)
    standing = [h for h in hazards if "reviewed" not in h]
    if standing and not args.allow_hazards:
        first = [f"{h['cls']}: {h['path']}:{h['line']}" for h in standing[:5]]
        raise Refused(f"{len(standing)} hazards stand (scan lists them): {first}")
    out, report = transform(files, mp)
    touched = write_tree(tree, files, out, report)
    if args.stage and touched:
        git("add", "-A", "--pathspec-from-file=-", cwd=tree,
            data="\n".join(sorted(touched)).encode())  # fmt: skip
    print(
        json.dumps(
            dict(
                final=mp.final,
                files_rewritten=len(report["files"]),
                tokens=sum(map(len, report["files"].values())),
                pages=report["pages"],
                renamed_ids=RENAMED,
                left=dict(Counter(why for why, _ in report["left"].values())),
                frozen_beyond_the_list=sorted(set(mp.frozen) - set(read_frozen(frozen_path))),
                stale_map=stale,
                hazards_standing=len(standing),
            ),
            indent=1,
        )
    )
    return 0


def apply_paths(tree, files, mp, args):
    wanted = [p.rstrip("/") for p in args.paths]
    suffixes = (*mp.scope["suffixes"], *(args.suffix or ()))
    found = {}
    for path, (_, data) in files.items():
        if not any(path == w or path.startswith(w + "/") for w in wanted):
            continue
        text = text_of(data) if path.endswith(suffixes) and path not in mp.frozen else None
        if text is not None and mp.text(path, text) != text:
            found[path] = mp.text(path, text)
    for path, text in found.items():
        (tree / path).write_bytes(text.encode())
    if args.stage and found:
        git("add", "--pathspec-from-file=-", cwd=tree, data="\n".join(sorted(found)).encode())
    print(json.dumps(dict(paths=wanted, files_rewritten=sorted(found)), indent=1))
    return 0


def write_tree(tree, files, out, report):
    """Write a transformed tree; returns the paths touched. A file keeps its mode: a page moves
    with its own, and a rewritten file is written in place."""
    touched = set()
    for old, new in report["pages"]:
        (tree / new).parent.mkdir(parents=True, exist_ok=True)
        (tree / old).rename(tree / new)
        touched |= {old, new}
    for path, (_, data) in out.items():
        p = tree / path
        if not p.exists() or p.read_bytes() != data:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            touched.add(path)
    return touched


def cmd_verify(args):
    choices_path, map_path, frozen_path = data_paths(args)
    choices = load_choices(choices_path)
    mp = load_map(map_path, frozen_list(args.tree, frozen_path, choices, args.base))
    result = verify(mp, args.base, args.head, cwd=args.tree)
    stale = stale_map(mp, args.tree, args.base)
    if stale and mp.final:
        result["problems"].append(dict(path="*", why=stale))
        result["verdict"] = "refused"
    result |= dict(
        stale_map=stale,
        base=git("rev-parse", args.base, cwd=args.tree).decode().strip(),
        head=git("rev-parse", args.head, cwd=args.tree).decode().strip(),
        frozen_beyond_the_list=sorted(set(mp.frozen) - set(read_frozen(frozen_path))),
    )
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=1) + "\n")
    shown = dict(result, problems=result["problems"][: args.show])
    print(json.dumps(dict(shown, problem_count=len(result["problems"])), indent=1))
    return 0 if result["verdict"] == "holds" else 1


# ------------------------------------------------------------------ the collected-ID gate


def compare_ids(mp, base, head, kept=()):
    """The collected test IDs of two trees, through the map's ids rule. Returns the differences;
    empty when the gate holds. `kept` names the tests ("file::test") whose IDs stay as they are: a
    parameter there is built from split literals, which the move does not see."""
    mapped = defaultdict(list)
    for test_id in base:
        same = test_id.split("[", 1)[0] in kept
        mapped[test_id if same else mp.test_id(test_id)].append(test_id)
    head = set(head)
    return dict(
        collisions=sorted(sorted(v) for v in mapped.values() if len(v) > 1),
        missing_in_head=sorted(k for k in mapped if k not in head),
        new_in_head=sorted(head - set(mapped)),
        renamed_by_the_map=sorted((v[0], k) for k, v in mapped.items() if v[0] != k),
    )


def declared_ids(result, head):
    """What the landing gate is told before it compares the collected IDs: the base's IDs that the
    map renames, which the head lacks (its removals), and the files of their new IDs (its
    additions)."""
    renamed = [(old, new) for old, new in result["renamed_by_the_map"] if new in head]
    removed = sorted(old for old, _ in renamed if old not in head)
    return removed, sorted({new.split("::", 1)[0] for old, new in renamed if old not in head})


def recorded_ids(path):
    """{"file::test"} of a tier-3 record's tests."""
    doc = json.loads(Path(path).read_text())
    return {f"{f}::{row[0]}" for f, entry in doc["files"].items() for row in entry.get("tests", ())}


def cmd_ids(args):
    choices_path, map_path, _ = data_paths(args)
    mp = load_map(map_path)
    kept = {r["test"]: r["reason"] for r in load_choices(choices_path).get("ids_kept", ())}
    lines = {
        side: [x for x in Path(path).read_text().splitlines() if "::" in x]
        for side, path in (("base", args.base_ids), ("head", args.head_ids))
    }
    result = dict(kind=REPORT_KIND, base=len(lines["base"]), head=len(lines["head"]))
    result["ids"] = compare_ids(mp, lines["base"], lines["head"], kept)
    if args.base_log and args.head_log:  # Collection errors, compared the same way.
        errors = [
            [x for x in Path(p).read_text().splitlines() if x.startswith("ERROR ")]
            for p in (args.base_log, args.head_log)
        ]
        result["errors"] = compare_ids(mp, *errors)
    blocking = [
        k
        for part in ("ids", "errors")
        if part in result
        for k in ("collisions", "missing_in_head", "new_in_head")
        if result[part][k]
    ]
    for record in args.record or ():  # A record's own IDs: each that was collected still is.
        recorded, base, head = recorded_ids(record), set(lines["base"]), set(lines["head"])
        through = {i: mp.test_id(i) for i in recorded}
        renamed = {i: n for i, n in through.items() if n != i}
        lost = sorted(n for i, n in through.items() if i in base and n not in head)
        strict = sum(
            n != mp.line(i) for i, n in renamed.items()
        )  # Those that only the ids rule sees.
        result.setdefault("records", {})[record] = dict(
            ids=len(recorded), renamed=len(renamed), seen_by_the_ids_rule_alone=strict, lost=lost
        )
        if lost:
            blocking.append(f"a recorded ID of {record} is gone")
    result["verdict"] = "same tests" if not blocking else "differs: " + ", ".join(blocking)
    if args.declare:
        folder = Path(args.declare)
        folder.mkdir(parents=True, exist_ok=True)
        for name, rows in zip(
            ("removed-ok.txt", "additions-from.txt"),
            declared_ids(result["ids"], set(lines["head"])),
            strict=True,
        ):
            (folder / name).write_text("".join(f"{x}\n" for x in rows))
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=1) + "\n")
    summary = {
        part: {k: len(v) for k, v in result[part].items()}
        for part in ("ids", "errors")
        if part in result
    }
    records = {k: dict(v, lost=len(v["lost"])) for k, v in result.get("records", {}).items()}
    print(json.dumps(dict(base=result["base"], head=result["head"], **summary, records=records,
                          verdict=result["verdict"]), indent=1))  # fmt: skip
    return 0 if not blocking else 1


# ------------------------------------------------------------------ the long-line rewrap

WIDEST = 100


def comments_of(text):
    return [
        t.string
        for t in tokenize.generate_tokens(io.StringIO(text).readline)
        if t.type == tokenize.COMMENT
    ]


def same_code(a, b):
    """Whether two Python texts are one program: equal syntax trees (docstrings included) and the
    same comments in the same order."""
    try:
        return ast.dump(ast.parse(a)) == ast.dump(ast.parse(b)) and comments_of(a) == comments_of(b)
    except (SyntaxError, tokenize.TokenError):
        return False


def newly_long(before, after):
    """The lines (from 1) that are too long now and were not; in two texts whose lines differ in
    number, the changed and the new ones that are too long."""
    a, b = lines_of(before), lines_of(after)
    if len(a) == len(b):
        return [
            i
            for i, (x, y) in enumerate(zip(a, b, strict=True), 1)
            if len(y) > WIDEST and len(x) <= WIDEST
        ]
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    same = {m.b + k for m in matcher.get_matching_blocks() for k in range(m.size)}
    return [i for i, y in enumerate(b, 1) if len(y) > WIDEST and i - 1 not in same]


def prose_lines(text):
    """The lines that only a comment or a multi-line string holds: no formatter wraps them."""
    out = {}
    for t in tokenize.generate_tokens(io.StringIO(text).readline):
        if t.type == tokenize.COMMENT and not t.line[: t.start[1]].strip():
            out[t.start[0]] = "a comment"
        elif t.type == tokenize.STRING and t.end[0] > t.start[0]:
            out.update(dict.fromkeys(range(t.start[0], t.end[0] + 1), "a multi-line string"))
        elif t.type == tokenize.FSTRING_MIDDLE and t.end[0] > t.start[0]:
            out.update(dict.fromkeys(range(t.start[0], t.end[0] + 1), "a multi-line string"))
    return out


def ruff_range(text, line, path):
    """ruff's formatting of the statement that holds one line; the text as it is where it fails."""
    proc = subprocess.run(
        [str(RUFF), "format", "--range", f"{line}-{line + 1}", "--stdin-filename", path,
         "--config", str(ROOT / "pyproject.toml"), "-"],
        input=text, capture_output=True, text=True, cwd=ROOT,
    )  # fmt: skip
    return proc.stdout if proc.returncode == 0 and proc.stdout else text


A_LITERAL = re.compile(r"""^(\s*)([rRfFbBuU]{0,2})(["'])((?:(?!\3).)*)\3([,)\]}:]*)$""")


def split_literal(text, line):
    """The text with a line that one literal fills cut in two at a space, each with its quotes; the
    text as it is where the line is no such line, or where the two would be other code."""
    rows = lines_of(text)
    m = A_LITERAL.match(rows[line - 1])
    if m is None or rows[line - 1].lstrip().startswith(('"""', "'''")):
        return text
    indent, prefix, quote, body, tail = m.groups()
    room = WIDEST - len(indent) - len(prefix) - 2
    cut = body.rfind(" ", 0, room) + 1
    if cut < 20 or len(body) - cut + len(indent) + len(prefix) + 2 + len(tail) > WIDEST:
        return text
    rows[line - 1 : line] = [
        f"{indent}{prefix}{quote}{body[:cut]}{quote}",
        f"{indent}{prefix}{quote}{body[cut:]}{quote}{tail}",
    ]
    new = "\n".join(rows)
    return new if same_code(text, new) else text


def rewrap_text(text, lines, path):
    """(text, [(line, why)]): the statements that hold the given lines wrapped, a line that one
    literal fills cut in two, and the lines that stay too long: prose, or a text that neither
    splits."""
    prose, left = prose_lines(text), []
    for line in sorted(lines, reverse=True):  # From the end, so the numbers above stay.
        if line in prose:
            left.append((line, prose[line]))
            continue
        new = split_literal(text, line)
        if new == text:
            new = ruff_range(text, line, path)
        if new == text:
            left.append((line, "ruff leaves it"))
        elif not same_code(text, new):
            left.append((line, "ruff's form is not the same code"))
        else:
            text = new
    return text, sorted(left)


def cmd_rewrap(args):
    tree = Path(args.tree)
    before = tree_at(args.base, tree)
    after = worktree_files(tree)
    back = {}
    result = dict(files=0, lines=0, left=Counter(), still_long=0)
    detail = {}
    for path, (_, data) in sorted(after.items()):
        old = before.get(back.get(path, path))
        if not path.endswith(".py") or old is None or old[1] == data or path == RENAMED:
            continue
        text = text_of(data)
        lines = newly_long(text_of(old[1]), text)
        if not lines:
            continue
        new, left = rewrap_text(text, lines, path)
        result["lines"] += len(lines)
        result["left"].update(why for _, why in left)
        detail[path] = left
        if new != text:
            result["files"] += 1
            (tree / path).write_bytes(new.encode())
        result["still_long"] += sum(len(x) > WIDEST for x in lines_of(new)) - sum(
            len(x) > WIDEST for x in lines_of(text_of(old[1]))
        )
    if args.out:
        Path(args.out).write_text(json.dumps(dict(result, detail=detail), indent=1) + "\n")
    print(json.dumps(result, indent=1))
    return 0


def rewrapped_problems(before, after):
    """Why a commit is not a rewrap of its base: a file that is not Python, came or went, changed
    its mode, or is not the same code."""
    out = []
    for path in sorted(set(before) | set(after)):
        a, b = before.get(path), after.get(path)
        if a == b:
            continue
        if a is None or b is None:
            out.append((path, "it came or went"))
        elif a[0] != b[0]:
            out.append((path, "its mode changed"))
        elif not path.endswith(".py"):
            out.append((path, "it is not Python"))
        elif not same_code(text_of(a[1]), text_of(b[1])):
            out.append((path, "it is not the same code"))
    return out


def cmd_rewrapped(args):
    before, after = tree_at(args.base, args.tree), tree_at(args.head, args.tree)
    problems = rewrapped_problems(before, after)
    changed = sum(before.get(p) != v for p, v in after.items())
    print(
        json.dumps(
            dict(files=changed, problems=problems, verdict="refused" if problems else "holds"),
            indent=1,
        )
    )
    return 1 if problems else 0


def _selftest_rewrap(checks):
    call = "def f():\n    value = call(first_argument, 'x@1', second_argument)\n    return value\n"
    longer = call.replace("'x@1'", f"'cells.wave.{'x' * 60}@1'")
    prose = '"""Text:\n' + "wave_mh@1 " * 9 + '\n"""\n# ' + "wave_mh@1 " * 9 + "\n"
    before, after = prose + call, prose.replace("wave_mh@1", "cells.wave.wave_mh@1") + longer
    lines = newly_long(before, after)
    new, left = rewrap_text(after, lines, "tests/p.py")
    checks["rewrap: the statement is wrapped, the docstring and the comment stay"] = (
        len(lines) == 3
        and sorted(why for _, why in left) == ["a comment", "a multi-line string"]
        and same_code(after, new)
        and new != after
        and all(len(x) <= WIDEST for x in lines_of(new) if "call" in x or "argument" in x)
    )
    checks["rewrap: in a file whose lines a later commit changed in number, the new long lines"] = (
        newly_long(before, "import x\n" + after) == [i + 1 for i in lines]
        and newly_long(before + "Y = 1\n" * 3, after) == lines
    )
    said = 'X = (\n    f"{a} ' + "a word " * 14 + 'wave_mh@1"\n)\n'
    cut, kept = rewrap_text(said, [2], "tests/p.py")
    checks["rewrap: a line that one literal fills is cut at a space, and stays one value"] = (
        kept == [] and same_code(said, cut) and max(map(len, lines_of(cut))) <= WIDEST
    )
    a = {"tests/p.py": ("100644", after.encode()), "configs/a.json": ("100644", b"{}")}
    good = dict(a, **{"tests/p.py": ("100644", new.encode())})
    checks["rewrapped: the rewrap holds; another value, a lost comment, another file do not"] = (
        rewrapped_problems(a, good) == []
        and all(
            [p for p, _ in rewrapped_problems(a, dict(good, **{path: ("100644", data)}))] == [path]
            for path, data in (
                ("tests/p.py", new.replace("first_argument", "other_argument").encode()),
                ("tests/p.py", new.replace("# cells", "# ").encode()),
                ("configs/a.json", b"{ }"),
                ("tests/new.py", b""),
            )
        )
        and [
            w
            for _, w in rewrapped_problems(
                a, dict(good, **{"tests/p.py": ("100755", new.encode())})
            )
        ]
        == ["its mode changed"]
    )


# ------------------------------------------------------------------ planted cases


def _plant_choices(**more):
    doc = dict(
        kind=CHOICES_KIND,
        move="selftest",
        scope=dict(
            dirs=["src/", "tests/", "validation/", "scripts/", "configs/"],
            suffixes=[".py", ".json", ".sh", ".toml"],
            test_ids=["tests/record.json"],
        ),
        seeds=[dict(module="cells.steps", name="METHOD_ID", family="solver")],
        keep=dict(ids={}, files=[]),
        pinned=[],
        frozen=dict(live=[], declared=[], owners={}),
        plants=dict(apply=True, families={}),
        reviewed=[],
    )
    doc.update(more)
    return doc


def _plant_engine(**more):
    doc = dict(
        laws=[
            dict(
                declared="wave_mh@1", interface="cells.wave_law@1", host="cells.host@3", module="m"
            ),
            dict(declared="cells.ion_pump@1", interface="cells.pump_law@1", host="k", module="m"),
        ],
        kinds=[dict(declared="cells.carrier@1", model_key="carriers")],
        operators=[dict(declared="wash@1", module="cells.operators.wash")],
        family_operators=[],
        models=[dict(declared="host@3", type="inner", module="m")],
        interfaces=["cells.wave_law@1", "cells.pump_law@1", "cells.kind@1", "cells.operator@1"],
        composite_interface="cells.operator@1",
        kind_interface="cells.kind@1",
        ids=dict(
            law_families={"cells.wave_law@1": "wave", "cells.pump_law@1": "pump"},
            families=["kind", "model", "operator", "pump", "solver", "wave"],
            piece=NEW.pattern,
            twice=[],
        ),
        census={"wave_mh@1": ["cells.laws.wave.LAW_ID"], "imex_two@1": ["cells.steps.METHOD_ID"]},
        keys={},
        not_imported={},
    )
    doc.update(more)
    return doc


_PLANTED = {
    "src/cells/__init__.py": '"""Cells."""\n',
    "src/cells/laws/wave.py": (
        '"""The wave law, wave_mh@1 (cells.wave_law@1)."""\n\n'
        'LAW_ID = "wave_mh@1"\nINTERFACE = "cells.wave_law@1"\nFORMAT = "cells.declarations@2"\n'
    ),
    "src/cells/steps.py": 'METHOD_ID = "imex_two@1"\n',
    "tests/test_wave.py": (
        "from cells.laws import wave\n\n"
        "ROWS = {'cells.wave_mh@1': 1, \"wave_mh@10\": 2, 'xwave_mh@1': 3, 'wave_mh@1b': 4}\n"
        'PROSE = "wave_mh@1, host@3 and cells.ion_pump@1; old_tissue@4 stays"\n'
        'RECORDED = "wave_mh@1 as the tag spells it"  # id-moves: keep (a registered text)\n'
        'IN_A_STRING = "wave_mh@1 # id-moves: keep"\n'
        'PAGE = "docs/library/cells/laws/wave_mh@1.md"\n'
        'OTHER = "docs/library/cells/laws/no_such@1.md"\n'
        'PATHS = "runs/wave_mh@1/out"\n'
    ),
    "tests/record.json": (
        '{"files": {"tests/test_wave.py": {"tests": [["test_a[cell-imex_two@1]", "passed"],\n'
        ' ["test_b[imex_two@1-closed]", "failed", ["E  assert <host@3 of wave_m...>"]]]}}}\n'
    ),
    "validation/frozen/judge.py": 'LAW = "wave_mh@1"\n',
    "validation/live.py": 'LAW = "wave_mh@1"\r\nMODEL = "host@3"\r\n',
    "configs/world.json": (
        '{"model": {"id": "host@3"}, "law": "wave_mh@1", "kind": "cells.carrier@1"}'
    ),
    "scripts/run.sh": "#!/bin/bash\nrun wave_mh@1 # id-moves: keep\nrun wave_mh@1\n",
    "docs/library/cells/laws/wave_mh@1.md": "# wave_mh@1\n",
    "docs/NOTE.md": "wave_mh@1 stays here\n",
    "lean/claim.py": 'LAW = "wave_mh@1"\n',
}


def _planted_files(**more):
    files = {p: ("100644", x.encode()) for p, x in _PLANTED.items()}
    files["scripts/run.sh"] = ("100755", files["scripts/run.sh"][1])
    files.update({p.replace("__", "/"): v for p, v in more.items()})
    return files


def _planted_map(files=None, choices=None, engine=None, rehearsal=False, frozen=()):
    files = files or _planted_files()
    choices, engine = choices or _plant_choices(), engine or _plant_engine()
    source = Source(files, choices["scope"])
    doc, rows, report = make_map(choices, engine, source, dict(head="x", dirty=False), rehearsal)
    return Map(doc, {p: [["tag", "t", "o"]] for p in frozen}), rows, report


def _refused(action, says=""):
    try:
        action()
    except Refused as error:
        return says in str(error)
    return False


def _selftest_table(checks):
    files = _planted_files()
    mp, rows, report = _planted_map(files)
    checks["table: a piece has its bare and its namespaced spelling, and its family's new ID"] = (
        mp.new["wave_mh@1"] == mp.new["cells.wave_mh@1"] == "cells.wave.wave_mh@1"
        and mp.new["cells.ion_pump@1"] == "cells.pump.ion_pump@1"
        and mp.new["cells.carrier@1"] == "cells.kind.carrier@1"
        and mp.new["wash@1"] == "cells.operator.wash@1"
        and mp.new["host@3"] == "cells.model.host@3"
        and mp.new["imex_two@1"] == "cells.solver.imex_two@1"
        and len(rows) == 6
    )
    checks["table: the planted tree is placed, with its classes"] = (
        [i for i, *_ in report["unplaced"]] == ["cells.declarations@2"]
        and report["problems"] == []
        and not any(v for k, v in report["collisions"].items() if not k.startswith("listed"))
    )
    keep = dict(ids={"format": [dict(id="cells.declarations@2", reason="r")]}, files=[])
    placed = _plant_choices(keep=keep)
    _, _, ok = _planted_map(files, placed)
    checks["table: an ID on the kept list is placed"] = ok["unplaced"] == []
    live = _planted_files(src__cells__x__py=("100644", b""))
    live = dict(files, **{"src/cells/x.py": ("100644", b'X = "unheard_of@1"\n')})
    checks["table: a live literal that nothing places is named with its site"] = [
        (i, sites) for i, _, sites in _planted_map(live, placed)[2]["unplaced"]
    ] == [("unheard_of@1", ["src/cells/x.py:1"])]
    prose = dict(
        files, **{"src/cells/x.py": ("100644", b'"""A note on unheard_of@1."""\n"un@1"\n')}
    )
    checks["table: a docstring or a bare string places nothing and is not live"] = (
        _planted_map(prose, placed)[2]["unplaced"] == []
    )
    census = _plant_engine(census={"computed_x@1": ["cells.x.TABLE (a key)"]})
    checks["table: a computed ID is seen by the census"] = [
        (i, sites) for i, _, sites in _planted_map(files, placed, census)[2]["unplaced"]
    ] == [("computed_x@1", ["cells.x.TABLE (a key) (at run time)"])]
    world = b'{"model": "host@3", "field": {"law": "odd_law@1"}}'
    defined = dict(files, **{"configs/w.json": ("100644", world)})
    checks["table: an ID in a live model's definition that nothing places is refused"] = [
        i for i, *_ in _planted_map(defined, placed)[2]["unplaced"]
    ] == ["odd_law@1"]
    checks["table: an interface is kept, and an ID that nothing live holds is in no row"] = (
        "wave_law@1" in mp.doc["kept"]["interface"] and "old_tissue@4" not in mp.new
    )
    ids = dict(_plant_engine()["ids"], law_families={"cells.wave_law@1": "wave"})
    checks["table: an interface without a word is a problem"] = any(
        "no family word for cells.pump_law@1" in x
        for x in _planted_map(files, placed, _plant_engine(ids=ids))[2]["problems"]
    )
    twin = _plant_engine(operators=[dict(declared="wave_mh@1", module="m")])
    rows2, _ = build_rows(placed, twin, Source(files, placed["scope"]))
    found = collisions(rows2, twin, Source(files, placed["scope"]))
    checks["table: one spelling naming two pieces is a collision"] = bool(
        found["one spelling naming two pieces"]
    )
    clash = _plant_engine(interfaces=["cells.wave_law@1", "cells.wash@1"])
    checks["table: an old spelling equal to an interface is a collision"] = collisions(
        rows, clash, Source(files, placed["scope"])
    )["an old spelling equal to an interface"] == ["cells.wash@1", "wash@1"]
    checks["map: one old spelling with two new IDs is refused"] = _refused(
        lambda: Map(dict(kind=MAP_KIND, final=True, left={}, scope=placed["scope"], rows=rows2)),
        "renamed to both",
    )
    ours = tsv_lines(rows)
    theirs = [x.replace("cells.wave.wave_mh@1", "cells.ripple.wave_mh@1") for x in ours]
    del theirs[1]
    result = compare_tables(ours, theirs)
    checks["table: a comparison finds a changed and a missing row"] = (
        len(result["only_ours"]) == 1
        and {d[0] for d in result["differ"]} == {"wave_mh@1", "cells.wave_mh@1"}
        and compare_tables(ours, ours)["differ"] == []
    )


def _selftest_rewriter(checks):
    files = _planted_files()
    mp, _, _ = _planted_map(files, frozen=["validation/frozen/judge.py"])
    out, report = transform(files, mp)
    text = {p: d.decode() for p, (_, d) in out.items()}
    wave = text["tests/test_wave.py"]
    checks["longest match, whole tokens: the namespaced spelling, and no part of a longer one"] = (
        "ROWS = {'cells.wave.wave_mh@1': 1, \"wave_mh@10\": 2, 'xwave_mh@1': 3, 'wave_mh@1b': 4}"
        in wave
    )
    checks["IDs inside a longer string; an ID that no row holds is left alone"] = (
        'PROSE = "cells.wave.wave_mh@1, cells.model.host@3 and cells.pump.ion_pump@1; '
        'old_tissue@4 stays"' in wave
    )
    checks["keep marker: a comment keeps its line, a string marks nothing, a shell line too"] = (
        'RECORDED = "wave_mh@1 as the tag spells it"  # id-moves: keep' in wave
        and 'IN_A_STRING = "cells.wave.wave_mh@1 # id-moves: keep"' in wave
        and text["scripts/run.sh"]
        == "#!/bin/bash\nrun wave_mh@1 # id-moves: keep\nrun cells.wave.wave_mh@1\n"
    )
    checks["page rule: the path of a renamed page, not of another"] = (
        'PAGE = "docs/library/cells/laws/wave.wave_mh@1.md"' in wave
        and 'OTHER = "docs/library/cells/laws/no_such@1.md"' in wave
    )
    checks["a token after / is left alone"] = 'PATHS = "runs/wave_mh@1/out"' in wave
    checks["page rule: the page moves in its folder, its text unchanged"] = (
        text.get("docs/library/cells/laws/wave.wave_mh@1.md") == "# wave_mh@1\n"
        and "docs/library/cells/laws/wave_mh@1.md" not in text
        and report["pages"]
        == [("docs/library/cells/laws/wave_mh@1.md", "docs/library/cells/laws/wave.wave_mh@1.md")]
    )
    checks["interface and schema IDs keep their names"] = (
        'INTERFACE = "cells.wave_law@1"\nFORMAT = "cells.declarations@2"'
        in text["src/cells/laws/wave.py"]
    )
    checks["docstrings are rewritten as any text is"] = (
        '"""The wave law, cells.wave.wave_mh@1 (cells.wave_law@1)."""'
        in text["src/cells/laws/wave.py"]
    )
    checks["a frozen file, the docs and lean are left alone"] = all(
        text[p] == _PLANTED[p]
        for p in ("validation/frozen/judge.py", "docs/NOTE.md", "lean/claim.py")
    ) and report["left"] == {"validation/frozen/judge.py": ("frozen", 1)}
    checks["line endings, a missing final newline and the modes are kept"] = (
        out["validation/live.py"][1]
        == b'LAW = "cells.wave.wave_mh@1"\r\nMODEL = "cells.model.host@3"\r\n'
        and out["configs/world.json"][1].endswith(b'"cells.kind.carrier@1"}')
        and {p: m for p, (m, _) in out.items() if m != "100644"} == {"scripts/run.sh": "100755"}
    )
    odd = dict(
        files, **{"tests/odd.py": ("100644", b'A = "wave_mh@1"\x0c\nB = "\xe2\x80\xa8wave_mh@1"')}
    )
    checks["a form feed and a Unicode line separator stay in their lines"] = (
        transform(odd, mp)[0]["tests/odd.py"][1]
        == b'A = "cells.wave.wave_mh@1"\x0c\nB = "\xe2\x80\xa8cells.wave.wave_mh@1"'
    )
    checks["a record of test IDs: a joined ID is mapped, its error text is not"] = (
        '"test_a[cell-cells.solver.imex_two@1]"' in text["tests/record.json"]
        and '"test_b[cells.solver.imex_two@1-closed]"' in text["tests/record.json"]
        and "E  assert <host@3 of wave_m...>" in text["tests/record.json"]
    )
    renamed = {}
    exec(compile(out[RENAMED][1], RENAMED, "exec"), renamed)
    checks["renamed_ids.py: one dict literal, every old spelling, and the rewriter leaves it"] = (
        renamed["RENAMED"] == mp.new
        and transform(out, mp)[0][RENAMED] == out[RENAMED]
        and [type(n).__name__ for n in ast.parse(out[RENAMED][1]).body] == ["Expr", "Assign"]
    )
    again, _ = transform(out, mp)
    checks["idempotent"] = again == out
    both = dict(files)
    both["docs/library/cells/laws/wave.wave_mh@1.md"] = ("100644", b"x")
    checks["a page whose new path exists is refused"] = _refused(
        lambda: transform(both, mp), "both it and"
    )
    late = dict(out, **{"tests/late.py": ("100644", b'LAW = "host@3"\n')})
    checks["a branch merged after the move: its own new references are rewritten"] = (
        transform(late, mp)[0]["tests/late.py"][1] == b'LAW = "cells.model.host@3"\n'
    )
    return files, mp, out


def _selftest_verify(checks, files, mp, out):
    def why(head, base=files, the_map=mp):
        return [p["why"] for p in verify(the_map, base, head)["problems"]]

    plain = dict(files)
    for path in ("tests/test_wave.py",):  # Its path token is a leftover, planted below.
        plain[path] = (
            plain[path][0],
            plain[path][1].replace(b'PATHS = "runs/wave_mh@1/out"\n', b""),
        )
    good, _ = transform(plain, mp)
    checks["verify: a clean move holds"] = why(good, plain) == []
    flipped = dict(good)
    data = bytearray(flipped["validation/live.py"][1])
    data[0] ^= 1
    flipped["validation/live.py"] = ("100644", bytes(data))
    checks["verify: one flipped byte is refused"] = any(
        "content differs" in w for w in why(flipped, plain)
    )
    checks["verify: a changed mode is refused"] = any(
        w.startswith("mode")
        for w in why(dict(good, **{"scripts/run.sh": ("100644", good["scripts/run.sh"][1])}), plain)
    )
    checks["verify: an extra file and a missing file are refused"] = any(
        "extra file" in w for w in why(dict(good, **{"src/cells/extra.py": ("100644", b"")}), plain)
    ) and any(
        "missing in head" in w for w in why({p: v for p, v in good.items() if p != RENAMED}, plain)
    )
    hand = dict(
        good, **{"src/cells/steps.py": ("100644", b'METHOD_ID = "cells.solver.imex_three@1"\n')}
    )
    checks["verify: a hand edit is refused"] = any("content differs" in w for w in why(hand, plain))
    pin = dict(plain, **{"tests/pin.py": ("100644", b'P = {"wave_mh@1": "' + b"a" * 64 + b'"}\n')})
    pinned, _ = transform(pin, mp)
    edited = dict(pinned)
    edited["tests/pin.py"] = ("100644", pinned["tests/pin.py"][1].replace(b"a" * 64, b"b" * 64))
    checks["verify: a hash beside an ID stays, and an edited hash is refused"] = why(
        pinned, pin
    ) == [] and "a hash literal changed" in why(edited, pin)
    checks["verify: an old spelling after / is left over"] = any(
        w.startswith("an old spelling is left") for w in why(out)
    )
    for name, text in (
        ("an escaped dot", rb'R = r"cells\.wave_mh@1 x"'),
        ("a token after a hyphen", b'R = "a-wave_mh@1"'),
        ("another namespace's", b'R = "tests.wave_mh@1"'),
        ("an ID after a pattern's escape", rb'R = r"\bwave_mh@1\b"'),
    ):
        odd = dict(plain, **{"tests/odd.py": ("100644", text + b"\n")})
        left = verify(mp, odd, transform(odd, mp)[0])["problems"]
        checks[f"verify: {name} is left over"] = [p["path"] for p in left] == ["tests/odd.py"]
    escaped = dict(plain, **{"tests/odd.py": ("100644", b'R = "a\\nwave_mh@1"\n')})
    got = verify(mp, escaped, transform(escaped, mp)[0])["problems"]
    checks["verify: an ID after an escape is caught by its decoded value"] = any(
        "a string's value" in p["why"] for p in got
    )
    split = dict(plain, **{"tests/odd.py": ("100644", b'R = "wave_" "mh@1"\n')})
    got = verify(mp, split, transform(split, mp)[0])["problems"]
    checks["verify: an ID split over two literals is caught by its decoded value"] = any(
        "a string's value" in p["why"] for p in got
    )
    binary = dict(plain, **{"configs/b.json": ("100644", b'\xff"wave_mh@1"')})
    got = verify(mp, binary, transform(binary, mp)[0])["problems"]
    checks["verify: a file that is not text and holds an old spelling is refused"] = any(
        "not UTF-8" in p["why"] for p in got
    )


def _selftest_ids(checks, mp):
    base = [
        "tests/test_wave.py::test_a[cell-imex_two@1]",
        "tests/test_wave.py::test_b[imex_two@1-closed]",
        "tests/test_wave.py::test_c",
        "tests/test_wave.py::test_d[docs/library/cells/laws/wave_mh@1.md]",
    ]
    head = [
        "tests/test_wave.py::test_a[cell-cells.solver.imex_two@1]",
        "tests/test_wave.py::test_b[cells.solver.imex_two@1-closed]",
        "tests/test_wave.py::test_c",
        "tests/test_wave.py::test_d[docs/library/cells/laws/wave.wave_mh@1.md]",
    ]
    same = compare_ids(mp, base, head)
    checks["ids: an ID joined by a hyphen, one before one and a page's path are the same tests"] = (
        not (same["collisions"] or same["missing_in_head"] or same["new_in_head"])
        and len(same["renamed_by_the_map"]) == 3
    )
    checks["ids: the gate is told the renamed IDs and the files of the new ones"] = declared_ids(
        compare_ids(mp, ["tests/a.py::t[wave_mh@1]", "tests/b.py::u"],
                    ["tests/a.py::t[cells.wave.wave_mh@1]", "tests/b.py::u"]),
        {"tests/a.py::t[cells.wave.wave_mh@1]", "tests/b.py::u"},
    ) == (["tests/a.py::t[wave_mh@1]"], ["tests/a.py"])  # fmt: skip
    checks["ids: a dropped test, a new one and an old spelling in the head are caught"] = (
        compare_ids(mp, base, head[1:])["missing_in_head"] == [head[0]]
        and compare_ids(mp, base, [*head, "tests/x.py::test_new"])["new_in_head"]
        == ["tests/x.py::test_new"]
        and compare_ids(mp, base, [base[0], *head[1:]])["new_in_head"] == [base[0]]
    )
    checks["ids: a test whose IDs are kept is compared as it is"] = compare_ids(
        mp, base, [base[0], *head[1:]], {"tests/test_wave.py::test_a"}
    )["new_in_head"] == [] and compare_ids(mp, base, head, {"tests/test_wave.py::test_a"})[
        "missing_in_head"
    ] == [base[0]]
    checks["ids: two tests that the map makes one are caught"] = (
        len(compare_ids(mp, [base[0], head[0]], head)["collisions"]) == 1
    )


def _selftest_scan(checks, mp):
    lines = {
        "computed": b'for i in (1, 2):\n    X = f"wave_m{chr(104)}@{i}"\n',
        "computed, joined": b'X = "cells." + LAW_ID\n',
        "computed, format": b'X = "wave_{}@1".format(kind)\n',
        "computed, percent": b'X = "wave_%s@1" % kind\n',
        "computed, split": b'X = "wave_" + "mh@1"\n',
        "f-string": b'X = f"wave_mh@1{suffix}"\n',
        "cut": b'X = law.split("@")[0]\n',
        "partial": b'X = law.startswith("wave")\n',
        "partial, in": b'X = "kind" in law\n',
        "partial, without its major": b'FAMILY = ("wave_mh@", "tide@")\n',
        "partial, by a constant": b'FAMILY = "wave_m"\nX = law.startswith(FAMILY)\n',
        "partial, by a loop over keys": b'NO = {"wave_m": "not it"}\n'
        b"for p, why in NO.items():\n    if law.startswith(p):\n        raise E(why)\n",
        "partial, by a member": b'A = ("wave_m",)\nX = any(law.startswith(p) for p in A)\n',
        "partial, by a parameter": b"def of(law, start):\n    return law.startswith(start)\n\n\n"
        b'X = of(law, "wave_m")\n',
        "partial, by a default": b'def of(law, p="wave_m"):\n    return law.startswith(p)\n',
        "regex, by a constant": b'import re\nP = r"^[a-z_]+@\\d+$"\nX = re.compile(P)\n',
        "cut, at _": b'X = law.split("_")[0]\n',
        "cut, a slice": b"X = spec.law_id[:4]\n",
        "regex": b'import re\nX = re.compile(r"^[a-z_]+@\\d+$")\n',
        "name": b'X = family == "wave_mh"\n',
        "escaped dot": b'X = r"cells\\.wave_mh@1 x"\n',
        "unseen": b'X = "a-wave_mh@1"\n',
        "message": b'with raises(E, match="requires wave_m"):\n    f()\n',
        "message, a whole name at its end": b'assert "is not wave_mh" in str(e)\n',
        "message, a pattern": b'with raises(E, match=r"requires imex_t\\S* first"):\n    f()\n',
        "message, a namespaced start": b'with raises(E, match="which cells.wave_m"):\n    f()\n',
        "message, one that starts it": b'assert "cells.wave_m" in str(e)\n',
        "path": b'X = "runs/wave_mh@1/out"\n',
        "page path": b'X = "docs/library/cells/laws/wave_mh@1.md"\n',
        "file name": b'X = "wave_mh@1.json"\n',
        "test ID": b'X = "tests/test_a.py::test_a[wave_mh@1]"\n',
        "width": b'import numpy as np\nX = np.array([], dtype="U12")\n',
        "decoded": b'X = "a\\nwave_mh@1"\n',
    }
    for name, text in lines.items():
        found = Scanner({"tests/p.py": ("100644", text)}, mp).scan()
        checks[f"scan: {name}"] = name.split(",")[0] in {h["cls"] for h in found}
    quiet = {
        "a role and an end": b'X = f"{role}@membrane"\n',
        "module names": b"import sys\nX = [n for n in sys.modules if n.startswith('cells.')]\n",
        "an unrelated prefix": b'X = name.startswith("junction")\n',
        "a whole ID": b'X = law == "wave_mh@1"\n',
        "whole IDs in joined literals": b'X = "wave_mh@1, " + "host@3"\n',
        "a pattern of any ID": b'import re\nX = re.compile(r"[A-Za-z0-9_.]+@[0-9]+")\n',
        "an unrelated name": b'X = family == "wash_basin"\n',
        "the start of an ID alone, or in a path": b'X = "wave_m"\nY = "runs/wave_m"\n',
        "a module of an ID's name": b'X = "the wave_mh.rate function"\n',
        "a module, or a file, of the package": b'X = "cells.wave"\nY = "cells.wave_mh.rate"\n',
        "a module's name, by name": b'P = "cells"\nX = name.startswith(P + ".")\n',
        "a plain word, by name": b'P = "wave"\nX = name.startswith(P)\n',
        "another value's cut": b'X = cell.split("_")[0]\nY = cell[:4]\n',
        "a list's index, by name": b'ID = "wave_m"\nX = names.index(ID)\n',
    }
    for name, text in quiet.items():
        found = Scanner({"tests/p.py": ("100644", text)}, mp).scan()
        checks[f"scan: {name} is no hazard"] = found == []
    others = {
        "validation/family.py": ("100644", b'FAMILY = ("wave_m",)\n'),
        "tests/p.py": ("100644", b"import family\n\nX = law.startswith(family.FAMILY)\n"),
    }
    starts = b"def of(law, start):\n    return law.startswith(start)\n"
    passed = {
        "tests/helper.py": ("100644", starts),
        "tests/p.py": ("100644", b'import helper\n\nX = helper.of(law, "wave_m")\n'),
        "tests/q.py": ("100644", b'X = of(law, "tide_x")\n'),
    }
    for name, files in (("constant", others), ("argument", passed)):
        found = Scanner(files, mp).scan()
        checks[f"scan: a start of an ID, by another file's {name}"] = [h["cls"] for h in found] == [
            "partial"
        ]
    frozen = Map(mp.doc, {"tests/p.py": [["tag", "t", "o"]]})
    checks["scan: a frozen file's hazards are not the move's"] = (
        Scanner({"tests/p.py": ("100644", lines["cut"])}, frozen).scan() == []
    )
    left = {
        "validation/ref/spec.json": ("100644", b'{"law": "wave_mh@1"}'),
        "validation/ref/judge.py": ("100644", b'LAW = "wave_mh@1"\nX = law.startswith("wave_m")\n'),
        "validation/run.py": ("100644", b'DATA = HERE / "ref/spec.json"\n'),
        "validation/table.py": ("100644", b'import id_table\n\nX = id_table.load("spec.json")\n'),
        "tests/test_j.py": ("100644", b'from validation.ref import judge\nP = "/mnt/saved/run"\n'),
        "tests/test_k.py": ("100644", b'X = "other.json"\n'),
    }
    frozen = Map(mp.doc, {p: [["tag", "t", "o"]] for p in left if p.startswith("validation/ref/")})
    hazards, found, _ = run_scan(left, frozen, _plant_choices())
    rows = {(r["left"], r["reader"], r["names_the_table"]) for r in found["left_readers"]}
    checks["scan: readers of what the move leaves, and what frozen code tests, are listed"] = (
        hazards == []
        and rows
        == {
            ("validation/ref/spec.json", "validation/run.py", False),
            ("validation/ref/spec.json", "validation/table.py", True),
            ("validation/ref/judge.py", "tests/test_j.py", False),
        }
        and [h["path"] for h in found["frozen_code"]] == ["validation/ref/judge.py"]
        and found["outside"] == [("tests/test_j.py", 2, "/mnt/saved/run")]
    )
    files = {"tests/p.py": ("100644", lines["cut"])}
    reviewed = _plant_choices(
        reviewed=[
            dict(cls=["cut"], path="tests/*", text="split", reason="r"),
            dict(cls=["regex"], path="*", reason="nothing"),
        ]
    )
    hazards, _, stale = run_scan(files, mp, reviewed)
    checks["scan: a review settles its hazard, and a review of nothing is listed"] = [
        h["reviewed"] for h in hazards
    ] == ["r"] and [r["reason"] for r in stale] == ["nothing"]
    law = b'LAW = "wave_mh@1"\n'
    pin = hashlib.sha256(law).hexdigest()
    for name, quoted in (("hash", pin), ("hash prefix", pin[:16])):
        pinned = {
            "validation/live.py": ("100644", law),
            "validation/protocol.json": ("100644", json.dumps(dict(sha256=quoted)).encode()),
        }
        hazards, _, _ = run_scan(pinned, mp, _plant_choices())
        checks[f"scan: a quoted {name} of a file the move changes"] = [
            (h["cls"], h["path"]) for h in hazards
        ] == [("hash pin", "validation/live.py")]
    longer = {"tests/l.py": ("100644", b'X = "wave_mh@1 and host@3"\nY = "wash@1"\n')}
    checks["scan: IDs inside longer strings are listed, and are no hazard"] = (
        lambda found: (
            found[0] == [] and [i for _, _, i in found[1]["inside"]] == ["wave_mh@1", "host@3"]
        )
    )(run_scan(longer, mp, _plant_choices()))
    ruled = _plant_choices(pinned=[dict(path="validation/live.py", kind="python", choice="re-spell",
                                        choices=["re-spell", "leave"], pinned_by=[])])  # fmt: skip
    hazards, _, _ = run_scan(pinned, mp, ruled)
    checks["scan: a pin whose choice is made does not stand"] = all(
        "reviewed" in h for h in hazards
    )
    nested = dict(law="wave_mh@1")
    digest = hashlib.sha256(json.dumps(nested, sort_keys=True).encode()).hexdigest()
    doc = dict(world=nested, stated=digest)
    hazards, _, _ = run_scan(
        {"configs/a.json": ("100644", json.dumps(doc).encode())}, mp, _plant_choices()
    )
    checks["scan: a digest of a nested object, which re-spelling leaves stale"] = (
        "nested digest" in {h["cls"] for h in hazards}
    )
    keyed = json.dumps({"imex_two@1": 1, "ion_pump@1": 2}, sort_keys=True)
    hazards = Scanner({"configs/s.json": ("100644", keyed.encode())}, mp).scan()
    checks["scan: a JSON file whose keys are sorted before and not after"] = [
        h["cls"] for h in hazards
    ] == ["sorted JSON"]
    for path, text in (
        ("configs/k.json", b'{"a": [{"ion_pump@1": 1, "cells.ion_pump@1": 2}]}'),
        ("tests/k.py", b'K = {"ion_pump@1": 1, "cells.ion_pump@1": 2}\n'),
        ("tests/k.py", b'K = {"ion_pump@1", "cells.ion_pump@1"}\n'),
    ):
        hazards = Scanner({path: ("100644", text)}, mp).scan()
        checks[f"scan: two keys that become one, {path} ({text[4:6].decode()})"] = "one key" in {
            h["cls"] for h in hazards
        }


def _selftest_plants(checks, mp):
    """A test's own pieces, placed by their declaring types."""
    types = dict(
        laws={"WaveLaw": "wave", "PumpLaw": "pump"},
        kinds=["Kind"],
        operators=["LineageOperator", "Operator"],
        modules={"cells.laws.wave": "wave"},
    )
    head = "from dataclasses import replace\n\nfrom cells.laws import wave\n\n"
    cases = {
        "a law's type": ('WaveLaw("tests.p@1")', "wave"),
        "a kind": ('Kind(kind_id="tests.p@1")', "kind"),
        "an operator's class": ('class X(Operator):\n    LAW_ID = "tests.p@1"', "operator"),
        "a subclass of the test's own": (
            'class Own(WaveLaw):\n    pass\n\n\nOwn("tests.p@1")',
            "wave",
        ),
        "a copy of a module's law": ('replace(wave.LAW, law_id="tests.p@1")', "wave"),
        "a copy of a law looked up": (
            'law = active().lookup("cells.ion_pump@1")\nreplace(law, law_id="tests.p@1")',
            "pump",
        ),
        "a helper's parameter": (
            "def op(law):\n    class R(Operator):\n        LAW_ID = law\n\n    return R\n\n\n"
            'op("tests.p@1")',
            "operator",
        ),
        "a class made of a dict": (
            'type("X", (Operator,), dict(LAW_ID="tests.p@1", EVENT=True))',
            "operator",
        ),
        "a template": ('Kind(kind_id="tests.p@1".replace("p", name))', "kind"),
        "a name": ('P = "tests.p@1"\nPumpLaw(P)', "pump"),
    }
    for name, (code, family) in cases.items():
        files = {"tests/p.py": ("100644", (head + code + "\n").encode())}
        rows, hand = Plants(files, mp, types).rows()
        checks[f"plants: {name}"] = hand == [] and [r["new"] for r in rows] == [
            f"tests.{family}.p@1"
        ]
    unseen = {"tests/p.py": ("100644", b'replace(mystery, law_id="tests.p@1")\n')}
    checks["plants: a type that is not seen is left to hand, and a hand choice places it"] = [
        h[:2] for h in Plants(unseen, mp, types).rows()[1]
    ] == [("tests.p@1", "its type is not seen")] and Plants(
        unseen, mp, types, {"tests.p@1": "wave"}
    ).rows()[0][0]["new"] == "tests.wave.p@1"
    two = {
        "tests/a.py": ("100644", b'WaveLaw("tests.p@1")\n'),
        "tests/b.py": ("100644", b'Kind(kind_id="tests.p@1")\n'),
        "tests/c.py": ("100644", b'X = "tests.p@1"\n'),
    }
    rows, hand = Plants(two, mp, types).rows()
    checks["plants: one ID in two families is each file's own, and a third file's by hand"] = {
        r["new"]: r["files"] for r in rows
    } == {"tests.wave.p@1": ["tests/a.py"], "tests.kind.p@1": ["tests/b.py"]} and [
        (i, where) for i, _, where in hand
    ] == [("tests.p@1", ["tests/c.py"])]
    chosen = {"tests.p@1": {"tests/c.py": "pump"}}
    checks["plants: a hand choice for one file"] = {
        r["new"]: r["files"] for r in Plants(two, mp, types, chosen).rows()[0]
    }.get("tests.pump.p@1") == ["tests/c.py"]
    bare_files = {
        "tests/a.py": ("100644", b'class X(Operator):\n    LAW_ID = "own@1"\n'),
        "tests/b.py": ("100644", b'from tests.a import X\n\nM = "own@1 is refused"\n'),
        "tests/c.py": ("100644", b'M = "own@1, a word of its own"\n'),
    }
    rows, _ = Plants(bare_files, mp, types).rows()
    planted = Map(dict(mp.doc, plants=rows))
    out, _ = transform(bare_files, planted)
    checks["plants: a bare one is renamed where it is declared and imported, and nowhere else"] = (
        out["tests/a.py"][1].endswith(b'LAW_ID = "cells.operator.own@1"\n')
        and b"cells.operator.own@1 is refused" in out["tests/b.py"][1]
        and out["tests/c.py"] == bare_files["tests/c.py"]
        and b"own@1" not in out[RENAMED][1]
        and transform(out, planted)[0] == out
        and planted.test_id("tests/a.py::test_x[own@1-b]")
        == ("tests/a.py::test_x[cells.operator.own@1-b]")
        and planted.test_id("tests/c.py::test_x[own@1]") == "tests/c.py::test_x[own@1]"
    )
    lacking = Map(dict(mp.doc, types=types))
    hazards, _, _ = run_scan(bare_files, lacking, _plant_choices())
    checks["scan: a declared plant that the map does not rename"] = {
        (h["cls"], h["path"]) for h in hazards
    } == {("plant", "tests/a.py"), ("plant", "tests/b.py")}
    after = dict(bare_files) | {
        RENAMED: ("100644", b'RENAMED = {"wave_mh@1": "cells.wave.wave_mh@1"}\n')
    }
    checks["scan: after the move no plant is asked for"] = not any(
        h["cls"] == "plant" for h in run_scan(after, lacking, _plant_choices())[0]
    )


def _selftest_frozen(checks):
    """The three rules on a planted repository, both ways."""
    with tempfile.TemporaryDirectory() as folder:
        env = dict(os.environ, GIT_AUTHOR_NAME="p", GIT_AUTHOR_EMAIL="p@p", GIT_COMMITTER_NAME="p",
                   GIT_COMMITTER_EMAIL="p@p", GIT_CONFIG_GLOBAL="/dev/null")  # fmt: skip
        tree = Path(folder)

        def run(*words):
            subprocess.run(["git", *words], cwd=tree, env=env, check=True, capture_output=True)

        def commit(subject, **files):
            for name, text in files.items():
                path = tree / name.replace("__", "/")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
            run("add", ".")
            run("commit", "-q", "-m", subject)

        run("init", "-q", "-b", "main")
        commit("base", validation__a__note_py="x = 1\n", src__cells__m_py="y = 1\n")
        commit("A spec", validation__a__spec_py='L = "wave_mh@1"\n')
        run("tag", "a-registered-1")
        commit("Freeze the b predictions", validation__b__predictions_py='L = "wave_mh@1"\n')
        commit(
            "Pre-register c",
            validation__c__design_json='{"registered": "2026", "law": "wave_mh@1"}',
        )
        run("checkout", "-q", "-b", "side")
        commit(
            "the d judge",
            validation__d__judge_py='L = "wave_mh@1"\n',
            validation__d__tool_py="t = 1\n",
        )
        commit("the e reference", validation__e__ref_py='L = "wave_mh@1"\n')
        run("tag", "e-references-1")
        run("checkout", "-q", "main")
        commit("other work", src__cells__n_py="z = 1\n")
        run("merge", "-q", "--no-ff", "-m", "Merge side", "side")
        run("tag", "d-judge-merged-1")
        commit("a live edit", validation__a__note_py="x = 2\n", validation__d__tool_py="t = 2\n")
        commit(
            "a reader",
            tests__test_r_py="from validation.e import ref\n",
            validation__e____init___py="",
        )
        rules = {p: {r for r, _ in found} for p, found in frozen_rules(tree, "main").items()}
        checks["frozen: the tag, merge and commit rules, each with its file"] = rules == {
            "validation/a/spec_py": {"tag"},
            "validation/b/predictions_py": {"commit"},
            "validation/d/judge_py": {"merge", "tag"},
            "validation/d/tool_py": set(),
            "validation/e/ref_py": {"tag"},
        } or {p: r for p, r in rules.items() if r} == {
            "validation/a/spec_py": {"tag"},
            "validation/b/predictions_py": {"commit"},
            "validation/d/judge_py": {"merge", "tag"},
            "validation/e/ref_py": {"tag"},
        }
        checks["frozen: a file edited since its tag is not frozen"] = (
            "validation/d/tool_py" not in rules and "validation/a/note_py" not in rules
        )
        checks["frozen: a base before the merge does not hold the branch's files"] = (
            "validation/d/judge_py" not in frozen_rules(tree, "a-registered-1")
        )
        for name in ("c/design_json", "e/ref_py"):  # As the tool names files, by suffix.
            old = tree / "validation" / name
            old.rename(old.with_name(old.name.replace("_", ".")))
        run("add", "-A", ".")
        run("commit", "-q", "-m", "names")
        mp, _, _ = _planted_map()
        frozen = {"validation/e/ref.py"}
        missed, live = frozen_both_ways(tree, "main", frozen, mp)
        checks["frozen, both ways: a registered file that the rules miss"] = any(
            path == "validation/c/design.json" and any("registered" in s for s in signs)
            for path, signs in missed
        )
    with tempfile.TemporaryDirectory() as folder:
        tree = Path(folder)

        def run(*words):
            subprocess.run(["git", *words], cwd=tree, env=env, check=True, capture_output=True)

        for name, text in {
            "validation/e/__init__.py": "",
            "validation/e/ref.py": 'from cells import x\nL = "wave_mh@1"\n',
            "tests/test_r.py": "from validation.e import ref\n",
        }.items():
            (tree / name).parent.mkdir(parents=True, exist_ok=True)
            (tree / name).write_text(text)
        run("init", "-q", "-b", "main")
        run("add", ".")
        run("commit", "-q", "-m", "base")
        mp, _, _ = _planted_map()
        _, live = frozen_both_ways(tree, "main", {"validation/e/ref.py"}, mp)
        checks["frozen, both ways: frozen code that live code runs"] = live == [
            ("validation/e/ref.py", 1, True, ["tests/test_r.py"])
        ]


def _planted_repository(folder, files):
    """A git repository of planted files, with one commit; returns a runner of git in it."""
    tree = Path(folder)
    env = dict(os.environ, GIT_AUTHOR_NAME="p", GIT_AUTHOR_EMAIL="p@p", GIT_COMMITTER_NAME="p",
               GIT_COMMITTER_EMAIL="p@p", GIT_CONFIG_GLOBAL="/dev/null")  # fmt: skip

    def run(*words):
        words = ["git", *words]
        return subprocess.run(words, cwd=tree, env=env, check=True, capture_output=True).stdout

    for name, (mode, data) in files.items():
        (tree / name).parent.mkdir(parents=True, exist_ok=True)
        (tree / name).write_bytes(data)
        (tree / name).chmod(0o755 if mode == "100755" else 0o644)
    run("init", "-q", "-b", "main")
    run("add", ".")
    run("commit", "-q", "-m", "base")
    return run


def _selftest_end_to_end(checks):
    """apply and verify on a planted repository, as they are called."""
    with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as data:
        files = _planted_files()
        files["tests/test_wave.py"] = (
            "100644",
            files["tests/test_wave.py"][1].replace(b'PATHS = "runs/wave_mh@1/out"\n', b""),
        )
        run = _planted_repository(folder, files)
        tree = Path(folder)
        (tree / "validation/own").mkdir()
        (tree / "validation/own/spec.py").write_text('LAW = "wave_mh@1"\n')
        run("add", "validation/own/spec.py")
        run("commit", "-q", "-m", "a spec")
        run("tag", "own-registered-1")  # A registration that the recorded list does not hold.
        (tree / "tests/late.py").write_text('LAW = "host@3"\n')
        run("add", "tests/late.py")
        run("commit", "-q", "-m", "later work")
        choices = _plant_choices(frozen=dict(
            live=[dict(path="validation/live.py", reason="a live tool")],
            declared=[dict(path="validation/frozen/judge.py", reason="declared")],
            owners={}))  # fmt: skip
        mp, _, _ = _planted_map(files, choices, rehearsal=True)
        paths = {n: Path(data) / f"{n}.json" for n in ("choices", "map")}
        paths["choices"].write_text(json.dumps(choices))
        paths["map"].write_text(json.dumps(dict(mp.doc, plants=[])))
        common = ["--tree", folder, "--choices", str(paths["choices"]), "--map", str(paths["map"]),
                  "--frozen", str(Path(data) / "none.tsv")]  # fmt: skip

        def call(*words):
            with (
                contextlib.redirect_stdout(io.StringIO()) as out,
                contextlib.redirect_stderr(io.StringIO()),
            ):
                code = main([*words, *common])
            return code, out.getvalue()

        frozen = frozen_list(folder, Path(data) / "none.tsv", choices, "HEAD")
        checks["frozen: the rules' files, the declared ones, less the live exceptions"] = {
            "validation/own/spec.py",
            "validation/frozen/judge.py",
        } <= set(frozen) and "validation/live.py" not in frozen
        checks["apply: a map that is not final is refused"] = call("apply")[0] == 2
        before, head = (run("rev-parse", r).decode().strip() for r in ("HEAD~1", "HEAD"))

        def dated(head, dirty=False):
            return dict(mp.doc, plants=[], final=True, revision=dict(head=head, dirty=dirty))

        refused = []
        for doc in (dated(before), dated(head, dirty=True), dated("0" * 40)):
            paths["map"].write_text(json.dumps(doc))
            refused.append(call("apply", "--allow-hazards")[0] == 2)
        checks["apply: a map of another tree, or of a changed one, is refused before the move"] = (
            all(refused) and stale_map(Map(dated(head)), tree, "HEAD") is None
        )
        paths["map"].write_text(json.dumps(dated(head)))
        code, _ = call("apply", "--allow-hazards", "--stage")
        run("commit", "-q", "-m", "the move")
        checks["apply: rewrites the tree, renames the page, leaves the frozen files"] = (
            code == 0
            and (tree / "tests/late.py").read_text() == 'LAW = "cells.model.host@3"\n'
            and (tree / "docs/library/cells/laws/wave.wave_mh@1.md").exists()
            and not (tree / "docs/library/cells/laws/wave_mh@1.md").exists()
            and (tree / "validation/own/spec.py").read_text() == 'LAW = "wave_mh@1"\n'
            and (tree / "validation/frozen/judge.py").read_text() == 'LAW = "wave_mh@1"\n'
            and os.access(tree / "scripts/run.sh", os.X_OK)
        )
        checks["verify: the applied move holds"] = (
            call("verify", "--base", "HEAD~1", "--head", "HEAD")[0] == 0
        )
        paths["map"].write_text(json.dumps(dated(before)))
        checks["verify: a map that is not its base's is refused; after the move none is stale"] = (
            call("verify", "--base", "HEAD~1", "--head", "HEAD")[0] == 1
            and stale_map(Map(dated(before)), tree, "HEAD") is None
        )
        paths["map"].write_text(json.dumps(dated(head)))
        (tree / "tests/late.py").write_text('LAW = "wave_mh@1"\n')
        dirty = call("apply", "--rehearsal", "--allow-hazards")[0] == 2
        run("checkout", "-q", "--", "tests/late.py")
        again = call("apply", "--rehearsal", "--allow-hazards")[0] == 0
        clean = subprocess.run(["git", "status", "--porcelain"], cwd=tree, capture_output=True)
        checks["apply: refused on a tree with changes; again, it changes nothing"] = (
            dirty and again and clean.stdout == b""
        )
        spec = tree / "src/cells/steps.py"
        spec.write_bytes(spec.read_bytes().replace(b"imex", b"Imex"))
        run("commit", "-q", "-am", "one byte")
        checks["verify: one flipped byte is caught in a commit"] = (
            call("verify", "--base", "HEAD~2", "--head", "HEAD")[0] == 1
        )
        call("apply", "--rehearsal", "--paths", "docs")
        before = (tree / "docs/NOTE.md").read_text()
        call("apply", "--rehearsal", "--paths", "docs", "--suffix", ".md")
        checks["apply --paths: a page only where its suffix is asked for"] = (
            before == "wave_mh@1 stays here\n"
            and (tree / "docs/NOTE.md").read_text() == "cells.wave.wave_mh@1 stays here\n"
        )
        run("commit", "-q", "-am", "docs")
        code, _ = call("apply", "--rehearsal", "--paths", "lean")
        checks["apply --paths: a lane's own files, outside the scope, by the token rule alone"] = (
            code == 0 and (tree / "lean/claim.py").read_text() == 'LAW = "cells.wave.wave_mh@1"\n'
        )


def _selftest_choices(checks):
    checks["choices: a choice outside its list is refused"] = check_choices(
        _plant_choices()
    ) == [] and any(
        "is not one of" in x
        for x in check_choices(
            _plant_choices(pinned=[dict(path="p", choice="x", choices=["leave"])])
        )
    )
    group = dict(g=dict(choice="bare"))
    checks["choices: a part that the tool does not read, as a group, is refused; so is a lack"] = (
        check_choices(_plant_choices(groups=group)) == ["the tool reads no part 'groups'"]
        and check_choices({k: v for k, v in _plant_choices().items() if k != "seeds"})
        == ["no part 'seeds'"]
    )
    grouped = dict(module="cells.steps", name="METHOD_ID", family="solver", group="g")
    checks["choices: a seed's key that the tool does not read, as its group, is refused"] = (
        check_choices(_plant_choices(seeds=[grouped]))
        == ["seed cells.steps.METHOD_ID: the tool reads no 'group'"]
        and check_choices(_plant_choices(seeds=[dict(module="m", name="N")]))
        == ["seed m.N: no family"]
    )
    choices = _plant_choices(
        pinned=[dict(path="validation/live.py", kind="data", choice="leave", choices=["leave"])],
        keep=dict(ids={}, files=[dict(path="scripts/run.sh", reason="a planted keep")]),
    )
    files = _planted_files()
    mp, _, _ = _planted_map(files, choices)
    out, report = transform(files, mp)
    kept = ("validation/live.py", "scripts/run.sh")
    checks["choices: a pinned and a kept file are left, and counted"] = all(
        out[p] == files[p] for p in kept
    ) and {p: why for p, (why, _) in report["left"].items()} == {
        "validation/live.py": "pinned by hash, left",
        "scripts/run.sh": "kept: a planted keep",
    }


def _selftest_overtaken(checks):
    """A planted case for each choice that the tree has overtaken: gone, or held by another."""
    files = _planted_files()
    files["tests/test_plant.py"] = ("100644", b'LAW = "tests.own@1"\n')
    pin = hashlib.sha256(files["validation/live.py"][1]).hexdigest()
    files["configs/pins.json"] = ("100644", json.dumps({"validation/live.py": pin}).encode())
    kept_format = dict(id="cells.declarations@2", reason="a format (laws/wave.py FORMAT)")

    def problems(engine=None, files=files, **more):
        choices = _plant_choices(**more)
        engine = engine or _plant_engine()
        source = Source(files, choices["scope"])
        rows, found = build_rows(choices, engine, source)
        return found + choices_problems(choices, rows, engine, source, files)

    def keep(*ids, where="format", **more):
        return dict(keep=dict(ids={where: list(ids)}, files=[]), **more)

    def seed(**more):
        return dict(dict(module="cells.steps", name="METHOD_ID", family="solver"), **more)

    entry = dict(choice="leave", choices=["leave"])
    whole = dict(
        **keep(kept_format),
        seeds=[seed(note="scripts/run.sh runs it")],
        pinned=[dict(entry, path="validation/live.py", pinned_by=["configs/pins.json"])],
        frozen=dict(
            live=[dict(path="validation/live.py", reason="r")],
            declared=[dict(path="validation/frozen/judge.py", reason="r")],
            owners={},
        ),
        plants=dict(apply=True, families={"tests.own@1": {"tests/test_plant.py": "wave"}}),
        reviewed=[dict(cls=["cut"], path="validation/*.py", text="x", reason="r")],
        ids_kept=[dict(test="tests/test_wave.py::test_a", reason="r")],
    )
    checks["overtaken: choices that the tree bears out have no problem"] = problems(**whole) == []
    planted = {
        "a seed whose constant is gone": (
            dict(seeds=[seed(name="GONE")]),
            "the seed cells.steps.GONE: the constant is gone",
        ),
        "a seed whose table is gone": (
            dict(seeds=[seed(name="TABLE", keys=True)]),
            "the seed cells.steps.TABLE: its table is gone or empty",
        ),
        "a seed that another seed holds": (
            dict(seeds=[seed(), seed()]),
            "the seed cells.steps.METHOD_ID: imex_two@1 is held by the seed cells.steps.METHOD_ID",
        ),
        "a seed whose family is no word": (
            dict(seeds=[seed(family="ripple")]),
            "the seed cells.steps.METHOD_ID: registry/ids.py has no family word 'ripple'",
        ),
        "a kept ID that nothing live spells": (
            keep(kept_format, dict(id="cells.declarations@1", reason="r")),
            "kept cells.declarations@1 (format): nothing live spells it",
        ),
        "a kept ID that a registry holds": (
            keep(dict(id="wave_mh@1", reason="r")),
            "kept wave_mh@1 (format): held by the law registry: m",
        ),
        "a kept ID that a seed holds": (
            keep(dict(id="cells.imex_two@1", reason="r")),
            "kept cells.imex_two@1 (format): held by the seed cells.steps.METHOD_ID",
        ),
        "a kept ID that is an interface": (
            keep(dict(id="wave_law@1", reason="r")),
            "kept wave_law@1 (format): held by the interfaces",
        ),
        "a kept ID given twice": (
            keep(kept_format, kept_format),
            "kept cells.declarations@2 (format): held by the kept list (format)",
        ),
        "a plant that no file spells": (
            dict(plants=dict(apply=True, families={"tests.gone@1": "wave"})),
            "plant tests.gone@1: no test and no driver spells it",
        ),
        "a plant that a row holds": (
            dict(plants=dict(apply=True, families={"host@3": "wave"})),
            "plant host@3: held by the model table: m",
        ),
        "a plant's own file that is gone": (
            dict(plants=dict(apply=True, families={"tests.own@1": {"tests/gone.py": "wave"}})),
            "plant tests.own@1: tests/gone.py is gone",
        ),
        "a pinned path that is gone": (
            dict(pinned=[dict(entry, path="validation/gone.py")]),
            "pinned: validation/gone.py is gone",
        ),
        "a pin that its file no longer quotes": (
            dict(
                pinned=[
                    dict(entry, path="validation/frozen/judge.py", pinned_by=["configs/pins.json"])
                ]
            ),
            "pinned validation/frozen/judge.py: configs/pins.json quotes no hash of it",
        ),
        "a pin's own file that is gone": (
            dict(pinned=[dict(entry, path="validation/live.py", pinned_by=["configs/no.json"])]),
            "pinned validation/live.py, by: configs/no.json is gone",
        ),
        "a kept file that is gone": (
            dict(keep=dict(ids={}, files=[dict(path="scripts/gone.sh", reason="r")])),
            "keep: scripts/gone.sh is gone",
        ),
        "a live exception that is gone": (
            dict(frozen=dict(live=[dict(path="validation/x.py", reason="r")], declared=[])),
            "frozen, live: validation/x.py is gone",
        ),
        "a declared file that is gone": (
            dict(frozen=dict(live=[], declared=[dict(path="validation/x.py", reason="r")])),
            "frozen, declared: validation/x.py is gone",
        ),
        "a review of no file": (
            dict(reviewed=[dict(cls=["cut"], path="validation/no_*.py", text="x", reason="why")]),
            "reviewed: no file is validation/no_*.py (why)",
        ),
        "a record of test IDs that is gone": (
            dict(scope=dict(_plant_choices()["scope"], test_ids=["tests/gone.json"])),
            "scope: tests/gone.json is gone",
        ),
        "a kept test whose file is gone": (
            dict(ids_kept=[dict(test="tests/test_gone.py::test_a", reason="r")]),
            "ids_kept: tests/test_gone.py is gone",
        ),
        "a path that a reason cites and that is gone": (
            keep(dict(kept_format, reason="read by old/model.py:3 and by laws/wave.py")),
            "keep: a reason cites old/model.py, which is gone: "
            "read by old/model.py:3 and by laws/wave.py",
        ),
    }
    for what, (more, said) in planted.items():
        checks[f"overtaken: {what}"] = said in problems(**more)
    ids = dict(_plant_engine()["ids"], twice=["wave"])
    checks["overtaken: a family word that registry/ids.py gives two places"] = problems(
        _plant_engine(ids=ids), **whole
    ) == ["registry/ids.py gives the word 'wave' two places"]
    for registry in (
        dict(laws=[dict(declared="imex_two@1", interface="cells.wave_law@1", host="h",
                        module="m")]),
        dict(models=[dict(declared="cells.imex_two@1", type="family", module="m")]),
    ):  # fmt: skip
        found = problems(_plant_engine(**registry), **keep(kept_format))
        checks[f"overtaken: a seed that a registry holds ({', '.join(registry)})"] = (
            len(found) == 1
            and found[0].startswith("the seed cells.steps.METHOD_ID: imex_two@1 is held by the ")
            and "imex_two@1" in {o for r in _planted_map(
                files, _plant_choices(), _plant_engine(**registry))[1] for o in r["old"]}
        )  # fmt: skip
    table = dict(keys={"cells.steps.TABLE": ["wave_mh@1", "imex_two@1"]})
    part = problems(_plant_engine(**table), seeds=[seed(name="TABLE", keys=True)],
                    **keep(kept_format))  # fmt: skip
    whole_table = dict(keys={"cells.steps.TABLE": ["wave_mh@1", "cells.wash@1"]})
    checks["overtaken: a table that other rows hold in part is no problem, and in whole one"] = (
        part == []
        and "the seed cells.steps.TABLE: other rows hold all 2 of its keys"
        in problems(_plant_engine(**whole_table), seeds=[seed(name="TABLE", keys=True)],
                    **keep(kept_format))
    )  # fmt: skip


def cmd_selftest(args):
    checks = {}
    _selftest_choices(checks)
    _selftest_overtaken(checks)
    _selftest_table(checks)
    files, mp, out = _selftest_rewriter(checks)
    _selftest_verify(checks, files, mp, out)
    _selftest_ids(checks, mp)
    _selftest_scan(checks, mp)
    _selftest_plants(checks, mp)
    _selftest_frozen(checks)
    _selftest_end_to_end(checks)
    _selftest_rewrap(checks)
    failed = [k for k, v in checks.items() if not v]
    print(json.dumps(dict(checks=len(checks), failed=failed), indent=1))
    return 1 if failed else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    commands = dict(
        check=cmd_check,
        table=cmd_table,
        frozen=cmd_frozen,
        scan=cmd_scan,
        apply=cmd_apply,
        verify=cmd_verify,
        ids=cmd_ids,
        rewrap=cmd_rewrap,
        rewrapped=cmd_rewrapped,
        selftest=cmd_selftest,
        _engine=cmd_engine,
    )

    def command(name, help_text=None):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--tree", default=str(ROOT), help="the checkout (default: this one)")
        p.add_argument("--choices", help=f"the choices file (default: {CHOICES})")
        p.add_argument("--map", help=f"the map (default: {MAP})")
        p.add_argument("--frozen", help=f"the frozen list (default: {FROZEN})")
        return p

    command("check", "the choices against the tree: what is gone, or held by another")
    command("_engine")
    p = command("table", "build the table, refused while an ID is unplaced or a choice overtaken")
    p.add_argument("--rehearsal", action="store_true",
                   help="a plant's family may be unseen; not final")  # fmt: skip
    p.add_argument("--out", help="write the map here")
    p.add_argument("--tsv", help="write every candidate row here, one line for each old spelling")
    p.add_argument("--compare", help="another table.tsv, compared row by row")
    p = command("frozen", "the frozen list at a base, by the three rules")
    p.add_argument("--base", required=True)
    p.add_argument("--out", help="write the list here (path, rule, reason, owner)")
    p.add_argument("--compare", help="another frozen list, compared file by file")
    p.add_argument("--lists", help="write one list for each owner, and both directions, here")
    p = command("scan", "the hazards; fails while one stands that no review settles")
    p.add_argument("--out", help="write every hazard here")
    p.add_argument("--by-hand", help="a by-hand list, each of whose sites must be found")
    p.add_argument("--skipped", help="a list of old spellings that the token rule does not see")
    p.add_argument("--show", type=int, default=40, help="how many standing hazards to print")
    p = command("apply", "rewrite the tree")
    p.add_argument("--stage", action="store_true", help="git add what it changed")
    p.add_argument("--rehearsal", action="store_true", help="a map that is not final is allowed")
    p.add_argument("--allow-hazards", action="store_true")
    p.add_argument("--paths", nargs="+", help="only these files and folders, by the token rule")
    p.add_argument("--suffix", action="append", help="with --paths: another suffix, as .md")
    p = command("verify", "the replay of the map on the base against the head")
    p.add_argument("--base", required=True)
    p.add_argument("--head", required=True)
    p.add_argument("--out")
    p.add_argument("--show", type=int, default=60, help="how many problems to print")
    p = command("ids", "the collected test IDs of two trees, through the map")
    p.add_argument("base_ids", help="one test ID per line (pytest --collect-only -q)")
    p.add_argument("head_ids")
    p.add_argument("--base-log", help="the base's collection log (its ERROR lines)")
    p.add_argument("--head-log")
    p.add_argument("--record", action="append", help="a record of test IDs (the base's)")
    p.add_argument("--declare", help="write the gate's removals and additions into this folder")
    p.add_argument("--out")
    p = command("rewrap", "wrap the lines that the move made too long, in the worktree")
    p.add_argument("--base", required=True, help="the revision before the move")
    p.add_argument("--out")
    p = command("rewrapped", "whether a commit only rewraps its base, by its syntax trees")
    p.add_argument("--base", required=True)
    p.add_argument("--head", required=True)
    command("selftest", "the planted cases")
    args = parser.parse_args(argv)
    args.tree = str(Path(args.tree).resolve())
    try:
        return commands[args.command](args)
    except Refused as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
