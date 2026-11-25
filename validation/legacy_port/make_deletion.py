"""Prepare the legacy deletion from the removal list, in a throwaway worktree, uncommitted.

Usage: make_deletion.py REPO REV LIST_TSV WORKTREE [--edits JSON] [--optional-edits JSON]
[--without-optional] [--retirements] [--base LIST_HEAD] [--branch NAME] [--out DIR]

It makes WORKTREE (detached at REV, or on a new branch NAME), removes every file whose row says
`goes` (git rm), and those of the optional batch, which the user approved on 25 November 2026
(--without-optional leaves it), applies the edits that belong to the deletion's own commit, stages
them by path, and reports. Give a new WORKTREE for each head. It commits nothing and runs no test.
Its report, the definitions that leave and the commit's message go to DIR (by default the current
folder).

The edits: (1) tests/unit/test_continuity_bypass.py, EXEMPT: every entry that names a file that
goes, and the group counts in its comments; (2) --edits, a list that make_edits.py writes: top-level
definitions to remove from a Python file that stays, texts to replace, and a note under a document's
title; then the imports that only the removed code used (ruff F401) and the formatting;
(3) --optional-edits, the same, for the optional batch; (4) tests/test_tiers.json: the rows of files
that the staged tree lacks, in all three tiers (scripts/gates/gate_steps.py refuses a head with
one). An edit that cannot be applied is reported, never skipped silently.

--retirements prepares the second commit, on a REV that holds the first: it removes the files whose
row says `retires` and makes the edits (1) and (4), no other.

With --branch it refuses, before any worktree: while a row of the list says "open, before the
deletion" (or, for the second commit, "open, before the second commit"); while a row on which the
user was asked lacks "approved by the user"; and while the list is not a committed file. It refuses,
with the branch left uncommitted, while a row that had to move first is not in the staged tree.
"""

import argparse
import ast
import collections
import csv
import json
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import reach

ap = argparse.ArgumentParser()
ap.add_argument("repo")
ap.add_argument("rev")
ap.add_argument("list")
ap.add_argument("worktree")
ap.add_argument("--without-optional", action="store_true")
ap.add_argument("--retirements", action="store_true")
ap.add_argument("--branch")
ap.add_argument("--edits")
ap.add_argument("--optional-edits")
ap.add_argument("--base", default="903f821e")
ap.add_argument("--out", default=".")
a = ap.parse_args()
SECOND = a.retirements
BATCH = not (a.without_optional or SECOND)
if SECOND and (a.edits or a.optional_edits):
    sys.exit("--retirements takes no edits: the first commit made them")
if BATCH and a.edits and not a.optional_edits:
    sys.exit("the optional batch needs --optional-edits; --without-optional leaves the batch")
W = pathlib.Path(a.worktree)


def git(*x, cwd=None, check=True):
    r = subprocess.run(["git", "-C", str(cwd or a.repo), *x], capture_output=True, text=True)
    if check and r.returncode:
        sys.exit(f"git {x[:3]} failed: {r.stderr[-400:]}")
    return r.stdout


RUFF = str(pathlib.Path(sys.executable).with_name("ruff"))
OUT = pathlib.Path(a.out)
out = []


def say(*x):
    s = " ".join(str(y) for y in x)
    out.append(s)
    print(s)


head = git("rev-parse", a.rev).strip()
if W.exists():
    sys.exit(f"{W} exists: give a new worktree path")
rows = list(csv.DictReader(open(a.list), delimiter="\t"))
# The list's own revision, where it is a committed file.
at = pathlib.Path(a.list).resolve()
kept = git("ls-files", "--error-unmatch", at.name, cwd=at.parent, check=False).strip()
changed = git("status", "--porcelain", "--", at.name, cwd=at.parent, check=False).strip()
listed = git("rev-parse", "HEAD", cwd=at.parent).strip() if kept and not changed else None
say("the list's revision:", listed[:10] if listed else "none: it is not a committed file")
take = [
    r
    for r in rows
    if r["kind"] != "name"
    and (
        r["action"] == "retires"
        if SECOND
        else r["action"] == "goes" or (BATCH and r["action"] == "optional_batch")
    )
]
GATES = ("open, before the deletion", "open, before the second commit")[: 2 if SECOND else 1]
first = [r for r in rows if r["state"].startswith(GATES)]
for st, n in collections.Counter(r["state"] for r in first).items():
    say(
        "NOT YET:",
        n,
        "rows |",
        st,
        "|",
        [r["path"] for r in first if r["state"] == st],
    )
asked = [
    r
    for r in rows
    if re.search(r"\bB[12]: ", r["reason"])
    or (BATCH and r["action"] == "optional_batch")
    or (SECOND and r["action"] == "retires")
]
unapproved = [r["path"] for r in asked if "approved by the user" not in r["state"]]
say(
    "rows on which the user was asked (B1, B2, the optional batch, the retirements):",
    len(asked),
    "| not yet approved:",
    unapproved,
)
if unapproved and a.branch:
    sys.exit(f"refused: {len(unapproved)} rows are not approved by the user; no branch is made")
if a.branch and not listed:
    sys.exit("refused: the list is not a committed file; no branch is made")
if first and a.branch:
    sys.exit(
        f"refused: {len(first)} rows of the list are open before this commit; no branch is made"
    )
git("worktree", "add", *(["-b", a.branch] if a.branch else ["--detach"]), str(W), head)
tree = set(git("ls-files", cwd=W).split("\n")) - {""}
say(
    "head",
    head[:10],
    "| list",
    a.list,
    "| rows",
    len(rows),
    "| to remove",
    len(take),
    "" if BATCH else "(without the optional batch)",
)


# 0. The definitions that the gate's fingerprints hold, before (the tool's own enumeration; the
# three folders that scripts/gates/fingerprints_landing.sh gives it).
def definitions():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "fingerprints_" + str(len(sys.modules)), W / "scripts/gates/fingerprints.py"
    )
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    d = m.Harness.definitions([W / "configs", W / "examples", W / "validation"], None)
    return {m.tree_relative(k) for k in d}


before_defs = definitions()
# 1. Remove.
present = [r["path"] for r in take if r["path"] in tree]
absent = [r for r in take if r["path"] not in tree]
done = [r["path"] for r in absent if r["state"].startswith("done")]
missing = [r["path"] for r in absent if not r["state"].startswith("done")]
for i in range(0, len(present), 200):
    git("rm", "-q", "--", *present[i : i + 200], cwd=W)
say(
    "removed",
    len(present),
    "| already gone, as the list says",
    len(done),
    "| NOT FOUND",
    len(missing),
    missing[:10],
)
say("by kind", dict(collections.Counter(r["kind"] for r in take if r["path"] in tree)))
gone, want = (
    set(present),
    {
        line.split("\t")[1]
        for line in git("diff", "--name-status", "9b0debe6^", "9b0debe6").splitlines()
        if line.startswith("D")
    },
)
say(
    "9b0debe6 deletes",
    len(want),
    "files;",
    len(want - gone - set(done)),
    "of them not removed here",
    sorted(want - gone - set(done))[:5],
)
left = [p for p in git("ls-files", cwd=W).split("\n") if p.startswith("src/cells/legacy")]
say("files left under src/cells/legacy", len(left), left[:5])
# 2. Files that go but changed since the list's head: a builder may have started to use one.
moved = [
    line
    for line in git("diff", "--name-only", a.base, head).splitlines()
    if line in {r["path"] for r in take}
]
say("files that go and changed between", a.base, "and this head:", len(moved), moved[:10])
new = [
    line.split("\t")[1]
    for line in git("diff", "--name-status", a.base, head).splitlines()
    if line.startswith("A")
]
say("files added since", a.base + ":", len(new), new[:12])
# 3. Edits.
G = {r["path"] for r in take}
edited = []
p = W / "tests/unit/test_continuity_bypass.py"
if p.exists():
    s = p.read_text()
    lines = s.splitlines(keepends=True)
    t = ast.parse(s)
    d = next(
        n.value
        for n in t.body
        if isinstance(n, ast.Assign)
        and any(isinstance(x, ast.Name) and x.id == "EXEMPT" for x in n.targets)
    )
    cut = [
        (k.lineno, v.end_lineno, k.value)
        for k, v in zip(d.keys, d.values, strict=False)
        if k.value in G or not (W / k.value).exists()
    ]
    keep = [k.value for k in d.keys if k.value not in {c[2] for c in cut}]
    reads = sum(
        1
        for k, v in zip(d.keys, d.values, strict=False)
        if k.value in keep and isinstance(v, ast.Name) and v.id == "READ"
    )
    for x, y, _ in sorted(cut, reverse=True):
        del lines[x - 1 : y]
    s2 = "".join(lines)
    m = re.search(
        r"(# Read-only comparisons, audits and writers of their own output) \((\d+)\)\.", s2
    )
    if m:
        s2 = s2.replace(m.group(0), f"{m.group(1)} ({reads}).")
    # a comment line left with no entry under it
    s2 = re.sub(
        r"\n    # Same-process restart and independent references\.\n(?=    # |\})", "\n", s2
    )
    p.write_text(s2)
    ast.parse(s2)
    edited.append(str(p.relative_to(W)))
    say("EXEMPT: removed", len(cut), "entries, kept", len(keep), "; read-only group now", reads)
    [say("     ", c[2]) for c in cut]
else:
    say("EDIT NOT APPLIED: no tests/unit/test_continuity_bypass.py")
for e in (json.load(open(a.edits)) if a.edits else []) + (
    json.load(open(a.optional_edits)) if BATCH and a.optional_edits else []
):
    q = W / e["file"]
    if not q.exists():
        say("EDIT NOT APPLIED: no", e["file"])
        continue
    if "note" in e:
        L = q.read_text().split("\n")
        k = 1
        if not L[0].startswith("# "):
            say("EDIT NOT APPLIED: no title in", e["file"])
            continue
        while k < len(L) and L[k].strip():
            k += 1
        if e.get("after_note"):
            while k < len(L) and not L[k].startswith(">"):
                k += 1
            while k < len(L) and L[k].startswith(">"):
                k += 1
        q.write_text("\n".join(L[:k]) + "\n\n" + e["note"] + "\n".join(L[k:]).lstrip("\n"))
        edited.append(e["file"])
        say("note in", e["file"])
        continue
    s = q.read_text()
    lines = s.splitlines(keepends=True)
    spans, found = [], set()
    py = e["file"].endswith(".py")
    for n in ast.parse(s).body if py else []:
        nm = (
            n.name
            if isinstance(n, (ast.FunctionDef, ast.ClassDef))
            else next((x.id for x in getattr(n, "targets", []) if isinstance(x, ast.Name)), None)
        )
        if nm in e.get("names", []):
            x = min([n.lineno] + [k.lineno for k in getattr(n, "decorator_list", [])])
            spans.append((x, n.end_lineno))
            found.add(nm)
    if set(e.get("names", [])) - found:
        say("EDIT NOT APPLIED IN FULL:", e["file"], "has no", sorted(set(e["names"]) - found))
    for x, y in sorted(spans, reverse=True):
        if isinstance(
            ast.parse("".join(lines[x - 1 : y])).body[0], (ast.FunctionDef, ast.ClassDef)
        ):
            while x > 1 and not lines[x - 2].strip():
                x -= 1
        del lines[x - 1 : y]
    s = "".join(lines)
    for old, new in e.get("replace", []):
        if s.count(old) != 1:
            say(
                "EDIT NOT APPLIED IN FULL:",
                e["file"],
                "text found",
                s.count(old),
                "times:",
                old[:70],
            )
            continue
        s = s.replace(old, new)
    q.write_text(s)
    edited.append(e["file"])
    if py:  # imports that the removed definitions alone used; then the file as ruff would leave it
        ast.parse(s)
        subprocess.run(
            [RUFF, "check", "--select", "F401", "--fix", "-q", str(q)],
            capture_output=True,
            text=True,
            cwd=W,
        )
        subprocess.run([RUFF, "format", "-q", str(q)], capture_output=True, text=True, cwd=W)
    say(
        "edit",
        e["file"],
        "removed",
        sorted(found),
        "| text edits",
        len(e.get("replace", [])),
        "|",
        e.get("why", ""),
    )
if edited:
    pys = [x for x in edited if x.endswith(".py")]
    c = subprocess.run(
        [RUFF, "check", "--output-format", "concise", *[str(W / x) for x in pys]],
        capture_output=True,
        text=True,
        cwd=W,
    )

    def fmt(x, text):
        return subprocess.run(
            [RUFF, "format", "--check", "-q", "--stdin-filename", x, "-"],
            input=text,
            capture_output=True,
            text=True,
            cwd=W,
        ).returncode

    worse = [
        x for x in pys if fmt(x, (W / x).read_text()) and not fmt(x, git("show", f"{head}:{x}"))
    ]
    say(
        "ruff check of the edited files:",
        c.returncode,
        c.stdout.strip()[-200:].replace(chr(10), " ; "),
        "| formatted before and not after:",
        worse,
    )
# 3b. The tier record: the rows of files that this tree lacks (gate_steps.py's own predicate).
q = W / "tests/test_tiers.json"
s = q.read_text()
d = json.loads(s)
if json.dumps(d, indent=1) + "\n" != s:
    say("EDIT NOT APPLIED: tests/test_tiers.json is not as json.dumps(indent=1) writes it")
else:
    cut = {}
    for t, rs in d["tiers"].items():
        cut[t] = [r["file"] for r in rs if not (W / r["file"]).is_file()]
        d["tiers"][t] = [r for r in rs if (W / r["file"]).is_file()]
    q.write_text(json.dumps(d, indent=1) + "\n")
    edited.append("tests/test_tiers.json")
    say(
        "tests/test_tiers.json: rows dropped",
        {t: len(v) for t, v in cut.items()},
        "| left",
        {t: len(v) for t, v in d["tiers"].items()},
        "| dropped rows whose file the list does not remove",
        [f for v in cut.values() for f in v if f not in gone][:5],
    )
if edited:
    git("add", "--", *edited, cwd=W)
# 3c. The definitions that left.
lost = sorted(before_defs - definitions())
NAME = f"{head[:8]}{'-retirements' if SECOND else '' if BATCH else '-without-optional'}"
D = OUT / f"removed_definitions-{NAME}.txt"
D.write_text("".join(k + "\n" for k in lost))
say(
    "definitions (configs, examples, validation) before",
    len(before_defs),
    "| that leave",
    len(lost),
    "in",
    len({k.split(".json")[0] for k in lost}),
    "files | new",
    len(definitions() - before_defs),
    "|",
    D.name,
)
# 3d. Names that go from files that stay, and the rows that had to move first.
for r in rows:
    if r["kind"] != "name":
        continue
    f, _, n = r["path"].partition("#")
    if r["action"] == "goes" and (W / f).exists():
        have = {
            x.name
            for x in ast.parse((W / f).read_text()).body
            if isinstance(x, (ast.FunctionDef, ast.ClassDef))
        } | {
            y.id
            for x in ast.parse((W / f).read_text()).body
            if isinstance(x, ast.Assign)
            for y in x.targets
            if isinstance(y, ast.Name)
        }
        if n in have:
            say("NAME STILL DEFINED:", r["path"])
moved_bad = []
for r in rows:
    if r["kind"] == "name" and r["action"] == "retargeted" and r["state"].startswith("done"):
        for f, n in re.findall(r"(tests/unit/\w+\.py)::(\w+)", r["becomes"]):
            ok = (W / f).exists() and n in {
                x.name
                for x in ast.walk(ast.parse((W / f).read_text()))
                if isinstance(x, ast.FunctionDef)
            }
            say(
                "moved row",
                "in the staged tree:" if ok else "MISSING FROM THE STAGED TREE:",
                f + "::" + n,
            )
            if not ok:
                moved_bad.append(n)
if moved_bad and a.branch:
    sys.exit(
        f"refused: rows that had to move first are not in the staged tree: {moved_bad} "
        "(the branch and its worktree stay, uncommitted)"
    )
subprocess.run(
    [
        "find",
        str(W / "src"),
        str(W / "validation"),
        str(W / "tests"),
        "-type",
        "d",
        "-empty",
        "-delete",
    ]
)
T = git("write-tree", cwd=W).strip()
# 4. Checks on the staged tree: imports that do not resolve, edges to a removed file, names of
# removed paths.
tr = reach.Tree(a.repo, T)
full = reach.Tree(a.repo, head)


def unresolved(tree):
    """(file, message) for every import of cells, validation, tests or scripts, and every attribute
    of an imported module of these, that resolves to nothing in the tree. A local variable that
    shadows a module gives a false message, so only messages new since head count."""
    live = {f: b.decode("utf-8", "ignore") for f, b in tree.py.items()}
    trees = {f: ast.parse(s) for f, s in live.items()}
    mods = {tree.mod_of[f]: f for f in live}
    pk = set()
    for m in mods:
        for k in range(1, m.count(".") + 1):
            pk.add(".".join(m.split(".")[:k]))
    cache, bad = {}, set()

    def names(f):
        if f in cache:
            return cache[f]
        o, star = set(), False
        for n in ast.walk(trees[f]):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                o.add(n.name)
            elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                o.add(n.id)
            elif isinstance(n, ast.ImportFrom):
                star |= any(x.name == "*" for x in n.names)
                o |= {x.asname or x.name for x in n.names}
            elif isinstance(n, ast.Import):
                o |= {x.asname or x.name.split(".")[0] for x in n.names}
        cache[f] = (o, star or "__getattr__" in o)
        return cache[f]

    for f, t in trees.items():
        al = {}
        for n in ast.walk(t):
            if isinstance(n, ast.Import):
                for x in n.names:
                    if (
                        x.name.split(".")[0]
                        in ("cells", "validation", "tests", "scripts", "lean", "visualizer")
                        and x.name not in mods
                        and x.name not in pk
                    ):
                        bad.add((f, f"no module {x.name}"))
            elif isinstance(n, ast.ImportFrom) and not n.level and n.module:
                for x in n.names:
                    if f"{n.module}.{x.name}" in mods:
                        al[x.asname or x.name] = mods[f"{n.module}.{x.name}"]
                if n.module.split(".")[0] not in (
                    "cells",
                    "validation",
                    "tests",
                    "scripts",
                    "lean",
                    "visualizer",
                ):
                    continue
                if n.module not in mods and n.module not in pk:
                    bad.add((f, f"no module {n.module}"))
                    continue
                for x in n.names:
                    if (
                        x.name == "*"
                        or f"{n.module}.{x.name}" in mods
                        or f"{n.module}.{x.name}" in pk
                    ):
                        continue
                    if n.module in mods:
                        o, star = names(mods[n.module])
                        if x.name not in o and not star:
                            bad.add((f, f"{n.module} has no {x.name}"))
                    else:
                        bad.add((f, f"no {x.name} in package {n.module}"))
        for n in ast.walk(t):
            if (
                isinstance(n, ast.Attribute)
                and isinstance(n.value, ast.Name)
                and n.value.id in al
                and isinstance(n.ctx, ast.Load)
                and not n.attr.startswith("__")
            ):
                if al[n.value.id].endswith("__init__.py"):
                    continue
                o, star = names(al[n.value.id])
                if n.attr not in o and not star:
                    bad.add((f, f"{al[n.value.id]} has no {n.attr}"))
    return bad, live


now, live = unresolved(tr)
before, _ = unresolved(full)
bad = collections.defaultdict(list)
for f, m in sorted(now - before):
    bad[f].append(m)
R = {r["path"]: r for r in rows}
say(
    "remaining Python files",
    len(live),
    "| with an import or a module attribute that stops resolving here",
    len(bad),
)
for f in sorted(bad):
    say(
        "     ",
        R.get(f, {}).get("action", "NOT ON THE LIST"),
        f,
        R.get(f, {}).get("owner", ""),
        bad[f][:3],
    )
hit = collections.defaultdict(set)
for f in live:
    es, _ = full.edges(f) if f in full.py else ([], [])
    for x, m, _l, _z in es:
        if x in G and "weak" not in m:
            hit[f].add((m, x))
say("remaining files that still name or reach a removed file", len(hit))
for f in sorted(hit):
    say("     ", R.get(f, {}).get("action", "NOT ON THE LIST"), f, sorted(hit[f])[:2], len(hit[f]))
other = reach.blobs(
    a.repo,
    T,
    lambda q: (
        not q.startswith(("lean/", "visualizer/", "reports/", "docs/", "scripts/moves/"))
        and q.endswith((".toml", ".sh", ".yml", ".yaml", ".cfg", ".ini"))
    ),
)
for f, b in other.items():
    m = sorted(
        {
            x
            for x in re.findall(
                r"(?:src|tests|validation|scripts|configs|examples)/[A-Za-z0-9_./\-]+",
                b.decode("utf-8", "ignore"),
            )
            if x.rstrip(".,;:") in G
        }
    )
    if m:
        say("     a tool or setting names a removed file:", f, m[:3])
openrows = [
    (r["path"], r["owner"], r["state"])
    for r in rows
    if r["action"] in ("edited", "retargeted")
    and not r["state"].startswith("done")
    and (r["kind"] != "doc" or "deletion" in r["state"])
]
say("rows of the list still open (documents: only those that go with the deletion):", len(openrows))
[say("     ", *x) for x in openrows]
lv = reach.blobs(
    a.repo,
    T,
    lambda q: (
        q.startswith(("lean/", "visualizer/"))
        and q.endswith(
            (".json", ".mjs", ".js", ".py", ".lean", ".toml", ".sh", ".html", ".ts", ".txt")
        )
    ),
)
say(
    "text files of lean/ and visualizer/ that name a removed path (theirs to change):",
    [
        (f, len(m))
        for f, b in sorted(lv.items())
        for m in [
            {
                x.rstrip(".,;:")
                for x in re.findall(
                    r"(?:src|tests|validation|scripts|configs|examples)/[A-Za-z0-9_./\-]+",
                    b.decode("utf-8", "ignore"),
                )
            }
            & G
        ]
        if m
    ],
)
st = git("diff", "--cached", "--name-status", cwd=W).splitlines()
say(
    "staged:",
    dict(collections.Counter(line[0] for line in st)),
    "| staged tree",
    T,
    "| nothing committed",
)
WHAT = (
    "The rows that retire with the legacy cleanup" if SECOND else "The legacy deletion"
) + ", made from the removal list"
PART = "" if SECOND or not BATCH else ", the optional batch among them"
(OUT / f"message-{NAME}.txt").write_text(
    f"{WHAT}\n\n"
    f"Made by validation/legacy_port/make_deletion.py on {head[:8]}, from the list at "
    f"{listed[:8] if listed else 'no commit'}:\n"
    f"{len(present)} files removed, {len(edited)} edited{PART}. The tag pre-cleanup-2026-11-25\n"
    "keeps everything that leaves.\n\n"
    "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n"
)
(OUT / f"report-{NAME}.txt").write_text("\n".join(out) + "\n")
