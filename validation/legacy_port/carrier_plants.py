"""Plant one fault at a time in the engine, in a scratch worktree, and run the rows on it.

Usage: carrier_plants.py TREE OUT.tsv [--plants FILE.json] [NAME ...]

The plants are those of carrier_plants.json: {name, lines, what, edits: [[file, old, new], ...],
rows, every}. A row that stays carries a claim of a row that retires only where a plant of that
claim makes it fail, so a plant that its rows pass is a finding. TREE is a scratch worktree: each
file is changed, and put back.

OUT gets one line per plant. Its outcome says how the rows saw it, by where each failing row
crashed:
- assertion: in the test (or a check of validation/), while the row ran;
- engine raise: in src/, while the row ran: a ledger, a domain or a refusal of the engine's own,
  which is a real detection and not the row's;
- fixture raise: the same in src/, while a fixture of the row ran;
- other: anywhere else (a library, a test's own error), which counts for nothing;
- not seen: every row passed;
- not run: a row could not be collected or imported, or none ran, which counts for nothing;
- not planted: the text to replace does not stand once (or at all, with `every`).
The rows run once without a plant first. Where one of them fails, nothing is recorded and the tool
stops.

pytest loads this file as its plugin (-p carrier_plants), which writes where each row crashed.
"""

import argparse
import collections
import json
import os
import pathlib
import subprocess
import sys
import tempfile

REPORT = "CARRIER_PLANTS_REPORT"
seen = []


def pytest_runtest_logreport(report):
    if report.when == "call" or report.outcome != "passed":
        crash = getattr(report.longrepr, "reprcrash", None)
        seen.append(
            dict(
                row=report.nodeid,
                when=report.when,
                outcome=report.outcome,
                path=getattr(crash, "path", None),
                line=getattr(crash, "lineno", None),
                message=(getattr(crash, "message", None) or "")[:300],
            )
        )


def pytest_collectreport(report):
    if report.failed:
        seen.append(dict(row=report.nodeid, when="collect", outcome="failed", path=None))


def pytest_sessionfinish():
    pathlib.Path(os.environ[REPORT]).write_text(json.dumps(seen))


def label(row, tree):
    """How one failing row saw the plant (the module docstring)."""
    if row["when"] == "collect":
        return "not run"
    where = pathlib.Path(row["path"] or "").resolve()
    inside = where.relative_to(tree).parts[0] if where.is_relative_to(tree) else ""
    if inside == "src":
        return "engine raise" if row["when"] == "call" else "fixture raise"
    if inside in ("tests", "validation") and row["when"] == "call":
        told = row["message"].split("\n")[0]
        if told.startswith(("assert", "AssertionError", "Failed: ")):
            return "assertion"
    return "other"


def run(tree, rows):
    """({label: [failing row, ...]}, how many passed, pytest's last line, the seconds)."""
    with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as folder:
        report = pathlib.Path(folder) / "report.json"
        environment = os.environ | {
            "PYTHONPATH": f"{tree}/src:{tree}:{pathlib.Path(__file__).parent}",
            "JAX_ENABLE_X64": "1",
            "JAX_PLATFORMS": "cpu",
            "CUDA_VISIBLE_DEVICES": "",
            "PYTHONDONTWRITEBYTECODE": "1",
            REPORT: str(report),
        }
        command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
        command += ["-p", pathlib.Path(__file__).stem, "--tb=short", *rows]
        done = subprocess.run(command, cwd=tree, env=environment, capture_output=True, text=True)
        found = json.loads(report.read_text()) if report.exists() else []
    lines = done.stdout.strip().splitlines() or [done.stderr[-200:]]
    kinds = collections.defaultdict(list)
    for row in found:
        if row["outcome"] == "failed":
            kinds[label(row, tree)].append(row)
    passed = sum(row["outcome"] == "passed" and row["when"] == "call" for row in found)
    if not passed and not kinds:
        kinds["not run"].append(dict(row="-", path=None))
    return kinds, passed, lines[-1]


def told(kinds, tree):
    """The first failing row of each label, and where it crashed."""
    out = []
    for name, rows in sorted(kinds.items()):
        row = rows[0]
        where = str(row.get("path") or "").replace(f"{tree}/", "")
        out.append(f"{name}: {row['row'].split('::')[-1]} at {where}:{row.get('line')}")
    return "; ".join(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tree")
    parser.add_argument("out")
    parser.add_argument("names", nargs="*")
    parser.add_argument("--plants", default=pathlib.Path(__file__).with_suffix(".json"))
    given = parser.parse_args()
    tree, out = pathlib.Path(given.tree).resolve(), pathlib.Path(given.out)
    plants = json.loads(pathlib.Path(given.plants).read_text())
    plants = [p for p in plants if not given.names or p["name"] in given.names]
    missing = set(given.names) - {p["name"] for p in plants}
    if missing or not plants:
        sys.exit(f"no such plant: {sorted(missing)}")

    def record(*values):
        with out.open("a") as handle:
            handle.write("\t".join(" ".join(str(v).split()) for v in values) + "\n")

    kinds, passed, last = run(tree, sorted({row for p in plants for row in p["rows"]}))
    if kinds:
        sys.exit(f"a row fails with nothing planted: {told(kinds, tree)} | {last}")
    record("none", "", "nothing planted", "", "", f"{passed} passed", last, "")
    for p in plants:
        texts, problem = {}, None
        for file, old, new in p["edits"]:
            path = tree / file
            now = path.read_text()
            texts.setdefault(path, now)
            count = now.count(old)
            if not (count == 1 or (count and p.get("every"))):
                problem = f"{file}: the text stands {count} times"
                break
            path.write_text(now.replace(old, new))
        files = " ".join(dict.fromkeys(file for file, *_ in p["edits"]))
        rows = " ".join(p["rows"])
        try:
            if problem:
                record(p["name"], p["lines"], p["what"], files, rows, "not planted", problem, "")
                continue
            kinds, passed, last = run(tree, p["rows"])
            outcome = ", ".join(f"{len(v)} {k}" for k, v in sorted(kinds.items())) or "not seen"
            record(p["name"], p["lines"], p["what"], files, rows, outcome, last, told(kinds, tree))
        finally:
            for path, text in texts.items():
                path.write_text(text)


if __name__ == "__main__":
    main()
