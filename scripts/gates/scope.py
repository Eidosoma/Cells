"""The scope map, and the selection of tiers 1+2 for a landing with no src/ change (the testing plan
of 19 November 2026, item E, §10.5; D229 rule 3). Host only: nothing here imports cells or JAX.

  build RUN SNAPSHOT OUT_MAP [--python PY]
      The map, from a tiers run made with `scripts/test_tiers.py run --scope-map RUN/scope` on
      SNAPSHOT (the nightly's). Per test file, three kinds of dependency, each with its state in
      SNAPSHOT:
      - content: the modules its processes imported, the files they opened and the paths among a
        child's arguments, by digest (SNAPSHOT.json's);
      - existence: the paths they asked about (os.stat and its kin) and the files a failed import
        or a shadowing module would have been, by kind (a file, a folder or absent);
      - listing: the folders they listed, by the digest of their names. A third-party library's
        own scans of sys.path (jaxlib's plugin search through pkgutil, metadata lookups) depend
        only on the names discovery can use (DISCOVERY: distribution metadata, path files,
        extension modules and plugins), so its listings and existence questions are compared on
        those names alone; a new test file is not a JAX plugin.
      - A file's entry is complete only when its run ended within the cap, its outcome matched its
        row, its test process and every child that was not forked wrote an exit record, and the
        recorder reported no fault.
      - A file reads the repository's files when code other than the import system and pytest
        opened a repository path that is not one of its own modules or src/ read by src/ code,
        named one to a child, or (its own code, not a library's) listed a repository folder.
      - A file's children are unmapped when one of its processes started more children than
        recorded themselves (another program, or a child with a cleared environment).
      The map's verdict is the run's: passed when every file ran and matched its row.
  select HEAD BASE MAP OUT_DIR [--tiers REL] [--stopped FILE] [--python PY] [--max-age-hours H]
         [--always readers|scanners|none]
      The tier-1/2 files of HEAD's record that the landing can reach, as a tier subset for
      scripts/test_tiers.py run (OUT_DIR/subset.json, with the reasons in OUT_DIR/selection.json).
      Refused (exit 3; the gate then runs the full tiers) when FILE exists (a nightly failure not
      yet explained), the map is unreadable, failed or older than H hours (default 36), either
      snapshot is incomplete or dirty, src/ differs between HEAD and BASE (a src/ change keeps the
      full gate), or the interpreter is not the map's. Otherwise a file is selected when:
      - it is in the guard set, or its children are unmapped, or (D229's always-run set) it reads
        the repository's files (--always readers, the default) or lists its folders (--always
        scanners); --always none keeps only what the recorded paths require, for comparison;
      - it is new or changed against BASE, not in the map, or incomplete there;
      - its row's outcome differs from the map's;
      - any path it touched is in another state in HEAD than in the map's snapshot, or any
        directory it listed holds other names. The comparison is with the map's snapshot, not
        BASE: what changed on main since the nightly counts too, so an entry never goes stale.
"""

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_steps  # noqa: E402

KIND = "cells.scope_map@2"
REFUSED = 3
SKIP = ("__pycache__",)
# The names a library's own discovery can use (pkgutil plugin searches, importlib.metadata).
DISCOVERY = re.compile(r"(\.dist-info|\.egg-info|\.egg-link|\.pth|\.egg|\.so|\.pyd)$|plugin", re.I)


# ------------------------------------------------------------------------------------- states


class Tree:
    """A snapshot's states: a path's (file digest, directory or absent) and a directory's names."""

    def __init__(self, root):
        doc = json.loads((Path(root) / "SNAPSHOT.json").read_text())
        self.revision = doc.get("git_revision")
        self.files = {n: r.get("sha256") for n, r in doc.get("files", {}).items()}
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

    def listing(self, folder, discovery=False):
        names = sorted(n for n in self.children.get(folder, ()) if not discovery or DISCOVERY.search(n))
        return hashlib.sha256("\n".join(names).encode()).hexdigest()[:16] if names else "-"


def useful(path):
    return path and not any(part in SKIP for part in path.split("/"))


def source_of(path):
    """A compiled file's source (x/__pycache__/m.cpython-313.pyc is x/m.py), else the path."""
    parts = path.split("/")
    if len(parts) >= 2 and parts[-2] == "__pycache__" and parts[-1].endswith(".pyc"):
        return "/".join(parts[:-2] + [parts[-1].split(".", 1)[0] + ".py"])
    return path


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


def entry(logs, tree):
    """One test file's entry: its dependencies by kind, its reads and its children."""
    content, exists, lists, finds, why = set(), set(), set(), set(), []
    modules, reads, scans = set(), [], False
    processes = {}
    for name, rows in logs.items():
        head = next((r for r in rows if "process" in r), None)
        if head is None:
            why.append(f"{name}: no process record")
            continue
        processes[name] = {"pid": head["process"], "parent": head["parent"], "forked": head["forked"],
                           "argv": head["argv"], "spawns": [r["spawn"] for r in rows if "spawn" in r],
                           "exit": any(r.get("exit") for r in rows)}
        for r in rows:
            if "fault" in r:
                why.append(f"recorder fault: {r['fault']}")
            if r.get("exit"):
                modules.update(r["modules"])
                content.update(r["modules"])
                exists.update(p for p in r["absent"] if useful(p))
            by = r.get("by", "child")
            if "open" in r and useful(r["open"]):
                path = source_of(r["open"])
                content.add(path)
                if by == "import":
                    modules.add(path)
                elif by != "pytest":
                    reads.append((path, by))
            if "arg" in r and useful(r["arg"]):
                content.add(r["arg"])
                reads.append((r["arg"], "arg"))
            if "stat" in r and useful(r["stat"]):
                if by != "library":
                    exists.add(r["stat"])
                elif DISCOVERY.search(r["stat"].rsplit("/", 1)[-1]):
                    exists.add(r["stat"])
            if "list" in r and useful(r["list"]):
                if by == "library":
                    finds.add(r["list"])
                else:
                    lists.add(r["list"])
                    scans = True
    pids = {p["pid"] for p in processes.values()}
    roots = [p for p in processes.values() if p["parent"] not in pids and not p["forked"]
             and "pytest" in p["argv"]]  # Others are children of a child not recorded.
    if len(roots) != 1:
        why.append(f"{len(roots)} test processes recorded, not one")
    for p in processes.values():
        if not p["forked"] and not p["exit"]:
            why.append(f"process {p['pid']} ({' '.join(p['argv'][:3])}) wrote no exit record")
    unmapped = []
    for p in processes.values():
        children = sum(1 for q in processes.values() if q["parent"] == p["pid"] and not q["forked"])
        if len(p["spawns"]) > children:
            unmapped += [" ".join(s[:4]) for s in p["spawns"]][: 3]
    data = sorted({path for path, by in reads
                   if by == "arg" or (path not in modules and tree.kind(path) == "f"
                                      and not (path.startswith("src/") and by.startswith("repo:src/")))})
    return {"content": content, "exists": exists, "lists": lists, "finds": finds, "why": why,
            "reads": data, "scans": scans, "unmapped": unmapped}


def build(run_dir, snapshot, python):
    run_dir = Path(run_dir)
    run = json.loads((run_dir / "run.json").read_text())
    summary = json.loads((run_dir / "summary.json").read_text())
    scope = Path(run.get("scope_map") or run_dir / "scope")
    tree = Tree(snapshot)
    record = json.loads((Path(snapshot) / "tests" / "test_tiers.json").read_text())
    rows = {r["file"]: r for t in ("1", "2") for r in record["tiers"].get(t, [])}
    changed = {e["file"] for e in summary["changed_vs_record"]}
    files, every = {}, set()
    for row in run["files"]:
        name = row["file"]
        e = entry(read_file_logs(scope / name.replace("/", "__")), tree)
        if row.get("timed_out") or row.get("exit_code") is None:
            e["why"].append("did not end within the cap")
        if name in changed:
            e["why"].append("its outcome differed from its row")
        if name not in rows:
            e["why"].append("no tier-1/2 row")
        every |= e["content"] | e["exists"] | e["lists"] | e["finds"]
        files[name] = e
    paths = sorted(every)
    at = {p: i for i, p in enumerate(paths)}
    verdict = "passed" if not changed and len(run["files"]) == len(rows) else "failed"
    doc = {"kind": KIND, "built": gate_steps.utc(), "revision": tree.revision,
           "snapshot": str(Path(snapshot).resolve()), "run": str(run_dir.resolve()),
           "verdict": verdict, "interpreter": gate_steps.interpreter(python), "paths": paths,
           "content": [tree.state(p) for p in paths], "kind_of": [tree.kind(p) for p in paths],
           "names": [tree.listing(p) for p in paths],
           "discovery": [tree.listing(p, discovery=True) for p in paths], "files": {}}
    for name, e in sorted(files.items()):
        row = rows.get(name, {})
        doc["files"][name] = {
            "complete": not e["why"], "why": e["why"][:5],
            **{key: sorted(at[p] for p in e[key]) for key in ("content", "exists", "lists", "finds")},
            "reads_repository": bool(e["reads"] or e["scans"]), "scans": e["scans"],
            "reads": e["reads"][:20], "children_unmapped": e["unmapped"],
            "row": {"exit_code": row.get("exit_code"), "counts": row.get("counts")}}
    return doc


# ------------------------------------------------------------------------------------- select


def refusal(head, base, doc, stopped, python, max_age_hours):
    if stopped and Path(stopped).exists():
        return f"selection stopped: {stopped} (a nightly failure not yet explained)"
    if doc is None or doc.get("kind") != KIND:
        return "no readable scope map"
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


def select(head, base, doc, tiers_rel, always="readers"):
    record_path = Path(tiers_rel) if Path(tiers_rel).is_absolute() else Path(head) / tiers_rel
    record = json.loads(record_path.read_text())
    now, was = Tree(head), gate_steps.snapshot_files(base)
    paths = doc["paths"]
    test = {  # Per kind of dependency, whether a path is in another state at the head.
        "content": lambda i: now.state(paths[i]) != doc["content"][i],
        "exists": lambda i: now.kind(paths[i]) != doc["kind_of"][i],
        "lists": lambda i: now.listing(paths[i]) != doc["names"][i],
        "finds": lambda i: now.listing(paths[i], discovery=True) != doc["discovery"][i]}
    moved = {key: {i for i in {i for e in doc["files"].values() for i in e[key]} if check(i)}
             for key, check in test.items()}
    words = {"content": "touched paths changed since the map", "exists": "paths it asked about "
             "appeared, went or changed kind", "lists": "listed folders changed since the map",
             "finds": "a library's discovery would see other names"}
    subset, reasons, seconds = {"1": [], "2": [], "3": []}, {}, {"selected": 0.0, "all": 0.0}
    for tier in ("1", "2"):
        for row in record["tiers"].get(tier, []):
            name, why = row["file"], []
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
                if always == "readers" and entry["reads_repository"]:
                    why.append("reads the repository's files")
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
            if why:
                subset[tier].append(row)
                reasons[name] = why
                seconds["selected"] += row.get("seconds") or 0.0
    counts = defaultdict(int)
    for why in reasons.values():
        for w in why:
            counts[w.split(":")[0]] += 1
    out = {"kind": "cells.test_tiers@1", "fast_seconds": record.get("fast_seconds"),
           "cap_seconds": record.get("cap_seconds"), "tiers": subset,
           "note": "a scope selection of tiers 1+2 (scripts/gates/scope.py select)"}
    report = {"map": {"revision": doc["revision"], "built": doc["built"]},
              "selected": len(reasons), "of": sum(len(record["tiers"].get(t, [])) for t in ("1", "2")),
              "seconds_selected": round(seconds["selected"], 1), "seconds_all": round(seconds["all"], 1),
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
    s = sub.add_parser("select")
    for name in ("head", "base", "map", "out"):
        s.add_argument(name)
    s.add_argument("--tiers", default="tests/test_tiers.json")
    s.add_argument("--stopped")
    s.add_argument("--python", default=gate_steps.PYTHON)
    s.add_argument("--max-age-hours", type=float, default=36.0)
    s.add_argument("--always", choices=("readers", "scanners", "none"), default="readers")
    a = p.parse_args(argv)
    if a.step == "build":
        doc = build(a.run, a.snapshot, a.python)
        tmp = Path(a.out).with_name(f".{Path(a.out).name}.tmp")
        tmp.write_text(json.dumps(doc) + "\n")
        tmp.replace(a.out)
        incomplete = sorted(f for f, e in doc["files"].items() if not e["complete"])
        print(json.dumps({"verdict": doc["verdict"], "files": len(doc["files"]), "paths": len(doc["paths"]),
                          "incomplete": len(incomplete),
                          "reads_repository": sum(e["reads_repository"] for e in doc["files"].values()),
                          "scans": sum(e["scans"] for e in doc["files"].values()),
                          "children_unmapped": sum(bool(e["children_unmapped"]) for e in doc["files"].values())}))
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
    print(json.dumps({k: report[k] for k in ("selected", "of", "seconds_selected", "seconds_all",
                                             "reasons_counted")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
