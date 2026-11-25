"""The scope map, and the selection of tiers 1+2 for a landing with no src/ change (the testing plan
of 19 November 2026, item E, §10.5; D229 rule 3, as D358 amends it). Host only: nothing here imports
cells or JAX.

  build RUN SNAPSHOT OUT_MAP [--python PY] [--prune-traces]
      The map, from a tiers run made with `scripts/test_tiers.py run --scope-map RUN/scope --trace
      RUN/trace` on SNAPSHOT (the nightly's). Per test file, its kinds of dependency, each with its
      state in SNAPSHOT:
      - content: the modules its processes imported, the files they opened and the paths among a
        child's arguments, by digest (SNAPSHOT.json's);
      - existence: the paths they asked about (os.stat and its kin), by kind (a file, a folder or
        absent), and for a file by its size and whether it is executable (the one mode bit git
        keeps);
      - listing: the folders they listed, by the digest of their names and those names' kinds. The
        standard library's discovery for a library (jaxlib's plugin search through pkgutil, metadata
        lookups) depends only on the names discovery can use (DISCOVERY: distribution metadata, path
        files, extension modules and plugins), so its listings and existence questions are compared
        on those names alone; a new test file is not a JAX plugin. Any other listing counts whole;
      - imports: the names its imports looked up, in the repository's folders on sys.path and in its
        packages. A file that such a lookup would now find, first or at all, reaches the test: a new
        module that shadows another, a package beside a module of its name, a module that an import
        or find_spec did not find. These replace the import system's own listings.
      - A file's entry is complete only when its run ended within the cap, its outcome matched its
        row, its test process and every child that was not forked wrote an exit record (but for a
        killed child that touched nothing of the tree, and a process that another program replaced),
        the recorder reported no fault and no link made into the tree, and the trace shows nothing
        that the entry lacks.
      - A file reads the repository's files when code other than the import system and pytest
        opened a repository path that is not one of its own modules or src/ read by src/ code,
        named one to a child, or (its own code, not a library's) listed a repository folder.
      - A file's children are unmapped when one of its processes started a child, or was replaced by
        a program, that neither recorded itself (matched by its process number and arguments) nor
        is accounted for by its arguments alone (answered: no program there, git outside the tree or
        asking for a repository in it, uname -p, fc-list).
      - The trace (strace's view of the same run: opens, listings, processes) is a standing check
        of the recorder. An entry that lacks a regular repository file a process opened, or a
        folder one listed, is incomplete, and a program the recorder did not see leaves the file's
        children unmapped. An entry whose trace is missing or not whole is not traced.
      The map's verdict is the run's: passed when every file ran and matched its row. What the trace
      found, per file, is the map's trace key; --prune-traces removes the traces that found nothing.
  select HEAD BASE MAP OUT_DIR [--tiers REL] [--stopped FILE] [--python PY] [--max-age-hours H]
         [--always untraced|readers|scanners|none]
      The tier-1/2 files of HEAD's record that the landing can reach, as a tier subset for
      scripts/test_tiers.py run (OUT_DIR/subset.json, with the reasons in OUT_DIR/selection.json).
      Refused (exit 3; the gate then runs the full tiers) when FILE exists (a nightly failure not
      yet explained), the map is unreadable, of another kind, failed or older than H hours (default
      36), either snapshot is incomplete or dirty, src/ differs between HEAD and BASE (a src/ change
      keeps the full gate), or the interpreter is not the map's. Otherwise a file is selected when:
      - it is in the guard set, or its children are unmapped;
      - it is new or changed against BASE, not in the map, or incomplete there;
      - its row's outcome differs from the map's;
      - any path it touched is in another state in HEAD than in the map's snapshot, any folder it
        listed holds other names or kinds, or an import of its would find another file. The
        comparison is with the map's snapshot, not BASE: what changed on main since the nightly
        counts too, so an entry never goes stale.
      - --always adds to these. untraced (the default, D358) adds the files that read the
        repository's files and whose entry no trace checked. readers is D229's rule and the
        fallback: every file that reads the repository's files; scanners, every one that lists its
        folders; none adds nothing. The selection also counts what readers would have selected.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_steps  # noqa: E402

KIND = "cells.scope_map@3"
REFUSED = 3
SKIP = ("__pycache__",)
RECORDER = "scripts/gates/scope_inject"  # In every recorded process; none of its code asked for it.
# The names a library's own discovery can use (pkgutil plugin searches, importlib.metadata).
DISCOVERY = re.compile(r"(\.dist-info|\.egg-info|\.egg-link|\.pth|\.egg|\.so|\.pyd)$|plugin", re.I)
MODULE = re.compile(r"^([^.]+)(\.py|\.pyc|(?:\.abi3[^.]*|\.cpython[^.]*)?\.so)$")  # A file an import finds.


# ------------------------------------------------------------------------------------- states


class Tree:
    """A snapshot's states: a path's (file digest, directory or absent), what asking about it tells,
    a directory's names, and what an import finds there."""

    def __init__(self, root):
        doc = json.loads((Path(root) / "SNAPSHOT.json").read_text())
        self.revision = doc.get("git_revision")
        rows = doc.get("files", {})
        self.files = {n: r.get("sha256") for n, r in rows.items()}
        self.sizes = {n: f"{(r.get('observation') or {}).get('size')}:"
                         f"{'x' if (r.get('snapshot_mode') or 0) & 0o111 else '-'}" for n, r in rows.items()}
        self.children = defaultdict(set)
        for name in list(self.files) + ["SNAPSHOT.json"]:
            parts = name.split("/")
            for i in range(len(parts)):
                self.children["/".join(parts[:i]) or "."].add(parts[i])

    def state(self, path):
        if path == "SNAPSHOT.json":
            return f"snapshot:{self.revision}"
        if path in self.files:
            return f"f:{self.files[path]}"
        return "d" if path in self.children else "-"

    def kind(self, path):
        return "f" if path in self.files or path == "SNAPSHOT.json" else (
            "d" if path in self.children else "-")

    def asked(self, path):
        return f"f:{self.sizes[path]}" if path in self.sizes else self.kind(path)

    def inside(self, folder):
        """{name: path} of a folder's entries."""
        return {n: n if folder == "." else f"{folder}/{n}" for n in self.children.get(folder, ())}

    def listing(self, folder, discovery=False):
        names = sorted(f"{n}:{self.kind(p)}" for n, p in self.inside(folder).items()
                       if not discovery or DISCOVERY.search(n))
        return hashlib.sha256("\n".join(names).encode()).hexdigest()[:16] if names else "-"

    def importable(self, folder):
        """What an import can find in a folder, as "NAME HOW": a module file's suffix, "/" for a
        folder, and "/__init__" with a suffix for a package."""
        found = set()
        for name, path in self.inside(folder).items():
            if path in self.children:
                if "." not in name:
                    found.add(f"{name} /")
                    found |= {f"{name} /{n}" for n in self.children[path]
                              if n.startswith("__init__.") and MODULE.match(n)}
            elif MODULE.match(name):
                found.add(" ".join(MODULE.match(name).groups()))
        return found


def useful(path):
    return path and not any(part in SKIP for part in path.split("/"))


def source_of(path):
    """A compiled file's source (x/__pycache__/m.cpython-313.pyc is x/m.py), else the path."""
    parts = path.split("/")
    if len(parts) >= 2 and parts[-2] == "__pycache__" and parts[-1].endswith(".pyc"):
        return "/".join(parts[:-2] + [parts[-1].split(".", 1)[0] + ".py"])
    return path


def module_place(path):
    """(folder, name) an import found a module file by: a/b.py in a as b, a/b/__init__.py likewise."""
    folder, _, name = path.rpartition("/")
    if name.startswith("__init__."):
        folder, _, name = folder.rpartition("/")
    return folder or ".", name.split(".", 1)[0]


# -------------------------------------------------------------------------------------- build


def read_file_logs(folder):
    """{log file name: rows} of one test file's processes."""
    logs = {}
    for log in sorted(Path(folder).glob("*.jsonl")) if Path(folder).is_dir() else []:
        rows = []
        for line in log.read_text(errors="replace").splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                rows.append({"fault": "an unreadable line"})
        logs[log.name] = rows
    return logs


CLONES = ("clone", "clone3", "fork", "vfork")
UNSEEN = ("open_by_handle_at", "io_uring_setup")  # They open files that no other traced call shows.
CHILD = re.compile(r" = (\d+)$")
OPENED = re.compile(r" = \d+<((?:[^<>\\]|\\.)*)>$")  # -y gives the path the kernel opened.
LISTED = re.compile(r"^getdents(?:64)?\(\d+<((?:[^<>\\]|\\.)*)>, ")
ESCAPE = re.compile(r"\\([0-7]{1,3}|.)")


def plain(path):
    """strace's printed path as text (it escapes what is not printable ASCII, and < and >)."""
    if "\\" not in path:
        return path
    one = {"n": "\n", "t": "\t", "r": "\r", "v": "\v", "f": "\f"}
    raw = ESCAPE.sub(lambda m: chr(int(m.group(1), 8)) if m.group(1)[0] in "01234567"
                     else one.get(m.group(1), m.group(1)), path)
    return raw.encode("latin1", "replace").decode("utf-8", "surrogateescape")


def read_trace(folder, root):
    """(what strace saw of one test file's processes in the tree at ROOT, None), or (None, why its view
    is not whole). Per process: the files it opened (with a line of the trace), the folders it
    listed, the programs it ran and its parent."""
    opened, listed, ran, parent, threads = {}, defaultdict(set), defaultdict(list), {}, set()
    logs = {int(p.name.split(".")[1]): p for p in Path(folder).glob("t.*")} if Path(folder).is_dir() else {}
    if not logs:
        return None, "no trace"
    root = str(root)
    rows = []  # (thread, the tree's path, the line, whether it is a listing)
    for thread, log in sorted(logs.items()):
        lines = log.read_text(errors="surrogateescape").splitlines()
        if not lines or not lines[-1].startswith("+++ "):
            return None, f"{log.name} has no end (a process outlived the test file, or strace did not)"
        for line in lines:
            call = line.partition("(")[0]
            if call in CLONES:
                found = CHILD.search(line)
                if found:
                    parent[int(found.group(1))] = thread
                    if "CLONE_THREAD" in line:
                        threads.add(int(found.group(1)))
            elif call in ("execve", "execveat"):
                ran[thread].append(line)
            elif call in UNSEEN:
                return None, f"{log.name} holds {call}"
            elif root in line:
                found = LISTED.match(line) or OPENED.search(line)
                path = plain(found.group(1)) if found else ""
                if path == root or path.startswith(root + "/"):
                    rows.append((thread, path[len(root) + 1:] or ".", line, bool(LISTED.match(line))))
    gone = sorted(set(parent) - set(logs))
    if gone:
        return None, f"no trace of the process or thread {gone[0]}"

    def process(thread):
        while thread in threads:
            thread = parent[thread]
        return thread

    for thread, path, line, listing in rows:
        if listing:
            listed[process(thread)].add(path)
        else:
            opened.setdefault(path, line)
    programs = defaultdict(list)
    for thread, lines in sorted(ran.items()):
        programs[process(thread)] += lines
    return {"opened": opened, "listed": listed, "ran": programs,
            "parent": {t: process(p) for t, p in parent.items() if t not in threads}}, None


GIT_ASKS = ("rev-parse", "status", "show")  # The commands traced in a tree that is no repository.


def git_asks(argv, cwd, root):
    """The tree's paths that a git child asks about, or None when its arguments alone do not say. Traced
    (D358): git in the tree, which is no repository, asks for .git, .git/HEAD and HEAD in its folder
    and each one above, and stops; git elsewhere reads the tree only through a path it is given."""
    def within(path):
        path = os.path.normpath(os.path.join(folder, path))
        return path == root or path.startswith(root + "/")

    folder, rest, given = cwd, list(argv[1:]), []
    while rest and rest[0].startswith("-"):
        option = rest.pop(0)
        if option in ("-C", "-c") and rest:
            value = rest.pop(0)
            if option == "-C":
                folder = os.path.normpath(os.path.join(folder, value))
            else:
                given.append(value)
        elif option not in ("--no-optional-locks", "--literal-pathspecs"):
            return None
    if not rest:
        return None
    if rest[0] == "init" and len(rest) > 1 and not rest[-1].startswith("-"):
        folder = os.path.normpath(os.path.join(folder, rest.pop()))  # It looks for no repository first.
    if not within("."):
        pieces = [p for a in given + rest for p in (a, *a.split("=")[1:]) if p]
        return None if any(within(p) for p in pieces) else set()
    if rest[0] not in GIT_ASKS or any(root in a for a in given + rest):
        return None
    asks, at = set(), os.path.relpath(folder, root)
    while True:
        asks |= {os.path.normpath(os.path.join(at, n)) for n in (".git", ".git/HEAD", "HEAD")}
        if at == ".":
            return asks
        at = os.path.dirname(at) or "."


def answered(argv, program, cwd, git_names_tree, root):
    """The tree's paths that a child without a record asked about, when its arguments alone say so
    (D358's argument rules), or None: the child is then unmapped."""
    if program is None:  # Nowhere: no child ran, and its path is among the arguments' paths.
        return set()
    if program.startswith(root + "/"):
        return None
    name = os.path.basename(program)
    if name == "uname" and argv[1:] == ["-p"]:  # platform.processor()
        return set()
    if name == "fc-list" and not any(root in a for a in argv):  # matplotlib's font search
        return set()
    if name == "git" and not git_names_tree:
        return git_asks(argv, cwd, root)
    return None


def entry(logs, tree, trace=None):
    """One test file's entry: its dependencies by kind, its reads and its children, checked against
    strace's view of the same run when there is one."""
    content, exists, lists, finds, why = set(), set(), set(), set(), []
    roots, tops, subs, known = set(), set(), set(), set()
    modules, reads, scans, processes = set(), [], False, []
    for name, rows in logs.items():
        head = next((r for r in rows if "process" in r), None)
        if head is None:
            why.append(f"{name}: no process record")
            continue
        p = {"pid": head["process"], "parent": head["parent"], "forked": head["forked"],
             "argv": head["argv"], "root": head.get("root"), "exit": any(r.get("exit") for r in rows),
             "starts": [r for r in rows if "child" in r or "exec" in r], "touched": False}
        processes.append(p)
        for r in rows:
            by, via = r.get("by", "child"), r.get("via")
            if "fault" in r:
                why.append(f"recorder fault: {r['fault']}")
            if "link" in r:
                why.append(f"a link to {r['link']} was made: what was read through it is not recorded")
            if r.get("exit"):
                modules.update(r["modules"])
                content.update(r["modules"])
            if "root" in r and "process" not in r:
                roots.add(r["root"])
            if "top" in r:
                tops.add(r["top"])
            if "sub" in r:
                subs.add((r["sub"], r["name"]))
            if "open" in r and useful(r["open"]):
                path = source_of(r["open"])
                content.add(path)
                p["touched"] |= not path.startswith(RECORDER)
                if by == "import":
                    modules.add(path)
                elif by != "pytest":
                    reads.append((path, by))
                if tree.kind(path) == "d" and by not in ("import", "pytest"):
                    lists.add(path)  # A folder opened: a descriptor can be listed from C.
                    scans |= by != "library"
            if "arg" in r and useful(r["arg"]):
                content.add(r["arg"])
                reads.append((r["arg"], "arg"))
                p["touched"] = True
            if "stat" in r and useful(r["stat"]):
                p["touched"] |= not r["stat"].startswith(RECORDER)
                if by != "library" or not via or DISCOVERY.search(r["stat"].rsplit("/", 1)[-1]):
                    exists.add(r["stat"])
            if "list" in r and useful(r["list"]):
                if via == "metadata" or (via == "pkgutil" and by == "library"):
                    finds.add(r["list"])  # Discovery: whoever asks, only names it can use count.
                elif by in ("import", "pytest"):
                    known.add(r["list"])
                else:
                    lists.add(r["list"])
                    scans |= by != "library"
                    p["touched"] = True
                    if r.get("entries"):  # Its code holds the entries, which tell their sizes and modes.
                        exists.update(path for path in tree.inside(r["list"]).values())
    subs.update(module_place(m) for m in modules if MODULE.match(m.rsplit("/", 1)[-1]))
    # The import system's own listings are replaced by the names it looked up; one of any other
    # folder (a finder that code built itself) counts whole.
    lists |= known & {r["list"] for rows in logs.values() for r in rows
                      if r.get("by") == "import" and "list" in r} - roots - {f for f, _ in subs}
    pids = {p["pid"] for p in processes}
    tests = [p for p in processes if p["parent"] not in pids and not p["forked"]
             and "pytest" in p["argv"]]  # Others are children of a child not recorded.
    if len(tests) != 1:
        why.append(f"{len(tests)} test processes recorded, not one")
    for p in processes:
        replaced = any("exec" in r for r in p["starts"])
        if not p["forked"] and not p["exit"] and not replaced and (p["touched"] or p in tests):
            why.append(f"process {p['pid']} ({' '.join(p['argv'][:3])}) wrote no exit record")
    unmapped, seen = [], set()
    for p in processes:
        for r in p["starts"]:
            pid, argv = (r["child"], r["argv"]) if "child" in r else (p["pid"], r["exec"])
            if any(q["pid"] == pid and q is not p and not q["forked"] and q["argv"] == argv
                   for q in processes):
                continue
            asks = None if pid is None else answered(argv, r.get("program"), r["cwd"], r.get("git"),
                                                     p["root"])
            if asks is None:
                unmapped.append(" ".join(argv[:4]))
            else:
                exists |= asks
            seen.add(pid)
    found = {}
    if trace is not None:
        found = trace_finds(trace, tree, processes, seen, content, lists, lists | finds | known | roots)
        if found.get("files") or found.get("listings"):
            why.append("the trace shows what the entry lacks: "
                       f"{sorted([*found.get('files', ()), *found.get('listings', ())])[:5]}")
        unmapped += [f"(the trace) {line[:80]}" for line in found.get("programs", ())]
    data = sorted({path for path, by in reads
                   if by == "arg" or (path not in modules and tree.kind(path) == "f"
                                      and not (path.startswith("src/") and by.startswith("repo:src/")))})
    return {"content": content, "exists": exists, "lists": lists, "finds": finds, "roots": roots,
            "tops": tops, "subs": subs, "why": why, "reads": data, "scans": scans, "unmapped": unmapped,
            "found": found}


def trace_finds(trace, tree, processes, seen, content, lists, listed):
    """What the trace shows and the entry lacks: regular files opened, folders listed (a process
    without a record may have listed only what the test's own code did), and programs run by a
    process that neither recorded itself nor was SEEN starting, nor descends from one that was."""
    recorded, found = defaultdict(int), {}
    for p in processes:
        recorded[p["pid"]] += not p["forked"]
    files = {p: line for p, line in trace["opened"].items()
             if useful(source_of(p)) and tree.kind(source_of(p)) == "f" and source_of(p) not in content}
    folders = {f for pid, folders in trace["listed"].items() for f in folders
               if useful(f) and f not in (listed if pid in recorded else lists)}

    def known(pid):
        while pid is not None and pid not in seen:
            if pid in recorded:
                return False
            pid = trace["parent"].get(pid)
        return pid is not None

    programs = [line for pid, lines in sorted(trace["ran"].items())
                if len(lines) > recorded.get(pid, 0) and not known(pid) for line in lines[-1:]]
    if files:
        found["files"] = {p: line[:300] for p, line in sorted(files.items())[:20]}
    if folders:
        found["listings"] = sorted(folders)[:20]
    if programs:
        found["programs"] = programs[:20]
    return found


def build(run_dir, snapshot, python, prune=False):
    run_dir = Path(run_dir)
    run = json.loads((run_dir / "run.json").read_text())
    summary = json.loads((run_dir / "summary.json").read_text())
    scope, traces = Path(run.get("scope_map") or run_dir / "scope"), run.get("trace")
    tree = Tree(snapshot)
    record = json.loads((Path(snapshot) / "tests" / "test_tiers.json").read_text())
    rows = {r["file"]: r for t in ("1", "2") for r in record["tiers"].get(t, [])}
    changed = {e["file"] for e in summary["changed_vs_record"]}
    files, every, tops, subs = {}, set(), set(), set()
    traced, not_traced, found = 0, {}, {}
    for row in run["files"]:
        name = row["file"]
        slug = name.replace("/", "__")
        logs = read_file_logs(scope / slug)
        root = next((r["root"] for rs in logs.values() for r in rs if "process" in r and "root" in r),
                    str(Path(snapshot).resolve()))
        seen, problem = read_trace(Path(traces) / slug, root) if traces else (
            None, run.get("trace_refused") or "the run was not traced")
        e = entry(logs, tree, seen)
        e["traced"] = seen is not None
        if seen is None:
            not_traced[name] = problem
        else:
            traced += 1
            if e["found"]:
                found[name] = e["found"]
            elif prune:
                shutil.rmtree(Path(traces) / slug, ignore_errors=True)
        if row.get("timed_out") or row.get("exit_code") is None:
            e["why"].append("did not end within the cap")
        if name in changed:
            e["why"].append("its outcome differed from its row")
        if name not in rows:
            e["why"].append("no tier-1/2 row")
        every |= e["content"] | e["exists"] | e["lists"] | e["finds"] | e["roots"]
        tops |= e["tops"]
        subs |= e["subs"]
        files[name] = e
    paths, names, places = sorted(every), sorted(tops), sorted(subs)
    at, top_at, sub_at = ({p: i for i, p in enumerate(ps)} for ps in (paths, names, places))
    verdict = "passed" if not changed and len(run["files"]) == len(rows) else "failed"
    folders = {f for f, _ in subs} | {r for e in files.values() for r in e["roots"]}
    doc = {"kind": KIND, "built": gate_steps.utc(), "revision": tree.revision,
           "snapshot": str(Path(snapshot).resolve()), "run": str(run_dir.resolve()),
           "verdict": verdict, "interpreter": gate_steps.interpreter(python),
           "trace": {"traced": traced, "not_traced": not_traced, "found": found}, "paths": paths,
           "content": [tree.state(p) for p in paths], "asked": [tree.asked(p) for p in paths],
           "names": [tree.listing(p) for p in paths],
           "discovery": [tree.listing(p, discovery=True) for p in paths], "tops": names, "subs": places,
           "importable": {f: sorted(tree.importable(f)) for f in sorted(folders)}, "files": {}}
    for name, e in sorted(files.items()):
        row = rows.get(name, {})
        doc["files"][name] = {
            "complete": not e["why"], "why": e["why"][:5], "traced": e["traced"],
            **{key: sorted(at[p] for p in e[key])
               for key in ("content", "exists", "lists", "finds", "roots")},
            "tops": sorted(top_at[n] for n in e["tops"]), "subs": sorted(sub_at[s] for s in e["subs"]),
            "reads_repository": bool(e["reads"] or e["scans"]), "scans": e["scans"],
            "reads": e["reads"][:20], "children_unmapped": e["unmapped"][:5],
            "row": {"exit_code": row.get("exit_code"), "counts": row.get("counts")}}
    return doc


# ------------------------------------------------------------------------------------- select


def refusal(head, base, doc, stopped, python, max_age_hours):
    if stopped and Path(stopped).exists():
        return f"selection stopped: {stopped} (a nightly failure not yet explained)"
    if doc is None or not str(doc.get("kind")).startswith(KIND.partition("@")[0] + "@"):
        return "no readable scope map"
    if doc["kind"] != KIND:
        return f"the map is {doc['kind']}, and this tool reads {KIND}: a passing nightly records it again"
    if doc.get("verdict") != "passed":
        return f"the map's nightly run {doc.get('verdict')}"
    built = datetime.strptime(doc["built"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - built).total_seconds() / 3600
    if age > max_age_hours:
        return f"the map is {age:.1f} hours old (more than {max_age_hours})"
    for tree in (head, base):
        _, problems = gate_steps.snapshot(tree)
        if problems:
            return f"snapshot problems: {problems}"
    changed = gate_steps.src_changed(head, base)
    if changed:
        return f"src/ changed ({changed[:3]}): a src/ change keeps the full gate"
    if python and gate_steps.interpreter(python) != doc.get("interpreter"):
        return "the interpreter is not the map's"
    return None


def select(head, base, doc, tiers_rel, always="untraced"):
    record_path = Path(tiers_rel) if Path(tiers_rel).is_absolute() else Path(head) / tiers_rel
    record = json.loads(record_path.read_text())
    now, was = Tree(head), gate_steps.snapshot_files(base)
    paths, tops, subs = doc["paths"], doc["tops"], doc["subs"]
    test = {  # Per kind of dependency, whether a path is in another state at the head.
        "content": lambda i: now.state(paths[i]) != doc["content"][i],
        "exists": lambda i: now.asked(paths[i]) != doc["asked"][i],
        "lists": lambda i: now.listing(paths[i]) != doc["names"][i],
        "finds": lambda i: now.listing(paths[i], discovery=True) != doc["discovery"][i]}
    moved = {key: {i for i in {i for e in doc["files"].values() for i in e[key]} if check(i)}
             for key, check in test.items()}
    words = {"content": "touched paths changed since the map", "exists": "paths it asked about "
             "appeared, went or changed kind, size or mode", "lists": "listed folders changed since the map",
             "finds": "a library's discovery would see other names"}
    # The names that an import would find in a folder in a way it did not at the map's snapshot.
    fresh = {folder: {new.split(" ")[0] for new in now.importable(folder) - set(had)}
             for folder, had in doc["importable"].items()}
    fresh = {folder: names for folder, names in fresh.items() if names}
    new_subs = {i for i, (folder, name) in enumerate(subs) if name in fresh.get(folder, ())}

    def found_anew(entry):
        seen = {tops[i] for i in entry["tops"]} if fresh else set()
        return sorted({f"{paths[i]}/{n}" for i in entry["roots"] for n in fresh.get(paths[i], ()) if n in seen}
                      | {"/".join(subs[i]) for i in entry["subs"] if i in new_subs})

    subset, reasons, seconds = {"1": [], "2": [], "3": []}, {}, {"selected": 0.0, "all": 0.0}
    old = {"selected": 0, "seconds_selected": 0.0}  # D229's rule, for comparison.
    for tier in ("1", "2"):
        for row in record["tiers"].get(tier, []):
            name, why, reader = row["file"], [], False
            entry = doc["files"].get(name)
            seconds["all"] += row.get("seconds") or 0.0
            if name in gate_steps.GUARDS:
                why.append("the guard set")
            if was.get(name) != now.files.get(name):
                why.append("new or changed")
            if entry is None:
                why.append("not in the map")
            elif not entry["complete"]:
                why.append(f"incomplete in the map: {entry['why'][:1]}")
            else:
                reader = entry["reads_repository"]
                if always == "readers" and reader:
                    why.append("reads the repository's files")
                if always == "untraced" and reader and not entry["traced"]:
                    why.append("reads the repository's files, and no trace checked its entry")
                if always == "scanners" and entry["scans"]:
                    why.append("lists the repository's folders")
                if entry["children_unmapped"]:
                    why.append(f"children not mapped: {entry['children_unmapped'][:1]}")
                if entry["row"] != {"exit_code": row.get("exit_code"), "counts": row.get("counts")}:
                    why.append("its row's outcome differs from the map's")
                for key, text in words.items():
                    hit = [paths[i] for i in entry[key] if i in moved[key]]
                    if hit:
                        why.append(f"{text}: {hit[:3]}")
                hit = found_anew(entry)
                if hit:
                    why.append(f"an import would find another file: {hit[:3]}")
            if why:
                subset[tier].append(row)
                reasons[name] = why
                seconds["selected"] += row.get("seconds") or 0.0
            if reader or why:
                old["selected"] += 1
                old["seconds_selected"] += row.get("seconds") or 0.0
    counts = defaultdict(int)
    for why in reasons.values():
        for w in why:
            counts[w.split(":")[0]] += 1
    out = {"kind": "cells.test_tiers@1", "fast_seconds": record.get("fast_seconds"),
           "cap_seconds": record.get("cap_seconds"), "tiers": subset,
           "note": "a scope selection of tiers 1+2 (scripts/gates/scope.py select)"}
    report = {"map": {"revision": doc["revision"], "built": doc["built"]}, "always": always,
              "selected": len(reasons), "of": sum(len(record["tiers"].get(t, [])) for t in ("1", "2")),
              "seconds_selected": round(seconds["selected"], 1), "seconds_all": round(seconds["all"], 1),
              "readers_rule": {**old, "seconds_selected": round(old["seconds_selected"], 1)},
              "reasons_counted": dict(sorted(counts.items())), "paths_changed_since_the_map": sorted(
                  paths[i] for i in moved["content"])[:50], "files": reasons}
    return out, report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="step", required=True)
    b = sub.add_parser("build")
    b.add_argument("run")
    b.add_argument("snapshot")
    b.add_argument("out")
    b.add_argument("--python", default=gate_steps.PYTHON)
    b.add_argument("--prune-traces", action="store_true")
    s = sub.add_parser("select")
    for name in ("head", "base", "map", "out"):
        s.add_argument(name)
    s.add_argument("--tiers", default="tests/test_tiers.json")
    s.add_argument("--stopped")
    s.add_argument("--python", default=gate_steps.PYTHON)
    s.add_argument("--max-age-hours", type=float, default=36.0)
    s.add_argument("--always", choices=("untraced", "readers", "scanners", "none"), default="untraced")
    a = p.parse_args(argv)
    if a.step == "build":
        doc = build(a.run, a.snapshot, a.python, a.prune_traces)
        tmp = Path(a.out).with_name(f".{Path(a.out).name}.tmp")
        tmp.write_text(json.dumps(doc) + "\n")
        tmp.replace(a.out)
        entries = doc["files"].values()
        print(json.dumps({"verdict": doc["verdict"], "files": len(doc["files"]), "paths": len(doc["paths"]),
                          "incomplete": sum(not e["complete"] for e in entries),
                          "reads_repository": sum(e["reads_repository"] for e in entries),
                          "scans": sum(e["scans"] for e in entries),
                          "children_unmapped": sum(bool(e["children_unmapped"]) for e in entries),
                          "traced": doc["trace"]["traced"], "trace_found": sorted(doc["trace"]["found"])}))
        return 0
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    try:
        doc = json.loads(Path(a.map).read_text())
    except (OSError, ValueError):
        doc = None
    why = refusal(a.head, a.base, doc, a.stopped, a.python, a.max_age_hours)
    if why:
        gate_steps.write_json(out / "selection.json", {"refused": why})
        print(json.dumps({"refused": why}))
        return REFUSED
    subset, report = select(a.head, a.base, doc, a.tiers, a.always)
    gate_steps.write_json(out / "subset.json", subset)
    gate_steps.write_json(out / "selection.json", report)
    print(json.dumps({k: report[k] for k in ("selected", "of", "seconds_selected", "seconds_all", "always",
                                             "readers_rule", "reasons_counted")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
