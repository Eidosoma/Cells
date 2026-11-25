"""Plant one fault at a time in the engine, in a scratch worktree, and run the rows on it.

Usage: carrier_plants.py TREE OUT.tsv [NAME ...]

The plants are those of carrier_plants.json: {name, what, file, old, new, rows, every}. A row that
stays carries a claim of a row that retires only where a plant of that claim makes it fail, so a
plant that its rows pass is a finding. TREE is a scratch worktree: each file is changed, and put
back. OUT gets one line per plant: its name, what is planted, the file, the rows, whether a row
failed, and the first reason. The rows run once without a plant first (the line `none`).
"""

import json
import os
import pathlib
import subprocess
import sys

tree, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
names = set(sys.argv[3:])
plants = json.loads(pathlib.Path(__file__).with_suffix(".json").read_text())
plants = [p for p in plants if not names or p["name"] in names]
environment = os.environ | {
    "PYTHONPATH": f"{tree}/src:{tree}",
    "JAX_ENABLE_X64": "1",
    "JAX_PLATFORMS": "cpu",
    "CUDA_VISIBLE_DEVICES": "",
    "PYTHONDONTWRITEBYTECODE": "1",
}


def run(rows):
    """(passed or failed, pytest's last line, the first reason)."""
    command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=line", *rows]
    done = subprocess.run(command, cwd=tree, env=environment, capture_output=True, text=True)
    lines = done.stdout.strip().splitlines() or [done.stderr[-200:]]
    reasons = [line.strip() for line in lines if line.startswith("E  ") or ".py:" in line]
    return "passed" if not done.returncode else "failed", lines[-1], (reasons or [""])[0][-200:]


def record(*values):
    with out.open("a") as handle:
        handle.write("\t".join(str(v).replace("\t", " ") for v in values) + "\n")


record("none", "nothing", "", *run(sorted({row for p in plants for row in p["rows"]})))
for p in plants:
    path = tree / p["file"]
    text = path.read_text()
    found = text.count(p["old"])
    if not (found == 1 or (found and p.get("every"))):
        record(p["name"], p["what"], p["file"], "not planted", f"the text stands {found} times", "")
        continue
    path.write_text(text.replace(p["old"], p["new"]))
    try:
        record(p["name"], p["what"], p["file"], *run(p["rows"]))
    finally:
        path.write_text(text)
