"""BITSEY's printed search logs as data (a reader of saved outputs; BITSEY is never imported).

It reads a log that BITSEY's `zombie.py zombie_tumor_isolate ...` printed: the saved historical
logs of b2cb370's `cancer_GJ_sims/results_miRNA/` (tumor_isolate_1D_V1M, tumor_isolate_2D_V1M) or
a pinned run's bitsey.log (validation/gap_junction_tissue/bitsey_run.py). The format is BITSEY's,
read here from its printed lines alone:
- `Fixing ...` opens a strategy, `Starting binary search for ...` its search;
- `Now doing Kd=<repr> for <title>` opens a point, with D printed at full precision;
- the point's dump follows: `x=0,y=NN` rows of `Zeb/ZEB:miR200` plus BITSEY's state character
  (E, M or X), each integer-rounded (`:.0f`). A row whose last entries repeat ends in `...`:
  BITSEY's remove_trailing_dups keeps two copies of the repeated value, and the rest of the row is
  that value;
- `Kd=<4 significant digits> => fixed if True|False` closes the point;
- `Binary search for ... returning (<x0>,<x2>)` closes a search, its bracket at 4 significant
  digits.

`read(path, z)` returns the searches in order, each with its points (full-precision D, outcome and
dump) and its printed bracket. A search's bracket at full precision is its points': the largest D
that did not fix below the smallest that did.

Usage: python -m validation.gap_junction_tissue.bitsey_log LOG Z [--out FILE]
"""

import argparse
import hashlib
import json
import re
from pathlib import Path

POINT = re.compile(r"^Now doing Kd=(\S+) for (.*)$")
OUTCOME = re.compile(r"^\s*Kd=(\S+) => fixed if (True|False)\s*$")
RESULT = re.compile(r"^Binary search for (.*) returning \((\S+?),(\S+?)\)\s*$")
START = re.compile(r"^Starting binary search for (.*)$")
STRATEGY = re.compile(r"^Fixing (.*)$")
ROW = re.compile(r"^x=(\d+),y=\s*(\d+) (.*)$")
CELL = re.compile(r"(\d+)/(\d+):(\d+)([EMX])")
FIELD = re.compile(r"^Field=(\d+)x(\d+)x(\d+)$")


def parse_row(text, z):
    """One dump row: z cells of (Zeb mRNA, ZEB, miR200, state), the elided tail expanded."""
    cells = [
        dict(zeb_mrna=int(a), zeb_protein=int(b), mir200=int(c), state=s)
        for a, b, c, s in CELL.findall(text)
    ]
    if text.rstrip().endswith("..."):
        cells += [dict(cells[-1]) for _ in range(z - len(cells))]
    if len(cells) != z:
        raise ValueError(f"a dump row holds {len(cells)} cells, not {z}: {text[:80]!r}")
    return cells


def read(path, z=None):
    """The log's searches (module docstring)."""
    lines = Path(path).read_text().splitlines()
    field, searches, strategy, search, point, dump = None, [], None, None, None, None
    for line in lines:
        m = FIELD.match(line)
        if m and field is None:
            field = [int(v) for v in m.groups()]
            z = z or field[2]
        m = STRATEGY.match(line)
        if m:
            strategy = m.group(1)
            continue
        m = START.match(line)
        if m:
            search = dict(strategy=strategy, title=m.group(1), points=[], printed_bracket=None)
            searches.append(search)
            continue
        m = POINT.match(line)
        if m:
            point = dict(d=float(m.group(1)), d_printed=m.group(1), title=m.group(2))
            point.update(fixed=None, rows=[])
            dump = point["rows"]
            if search is None:  # A point outside a search: the disconnected stage has none.
                search = dict(strategy=strategy, title=None, points=[], printed_bracket=None)
                searches.append(search)
            search["points"].append(point)
            continue
        m = ROW.match(line)
        if m and dump is not None and point is not None and point["fixed"] is None:
            dump.append(dict(x=int(m.group(1)), y=int(m.group(2)), cells=parse_row(m.group(3), z)))
            continue
        m = OUTCOME.match(line)
        if m and point is not None:
            point.update(fixed=m.group(2) == "True", d_outcome_printed=m.group(1))
            point, dump = None, None
            continue
        m = RESULT.match(line)
        if m and search is not None:
            search["printed_bracket"] = [float(m.group(2)), float(m.group(3))]
            search["result_title"] = m.group(1)
            search = None
    for s in searches:
        s["bracket"] = bracket(s["points"])
    return dict(
        format="gap_junction_tissue.bitsey_log@1",
        path=str(path),
        sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        field=field,
        searches=searches,
    )


def bracket(points):
    """(lo, hi) of a search at full precision: the smallest D that fixed, and the largest below it
    that did not; whether the outcomes are monotone in D."""
    done = sorted((p["d"], p["fixed"]) for p in points if p["fixed"] is not None)
    fixed = [d for d, ok in done if ok]
    hi = min(fixed) if fixed else None
    lo = max((d for d, ok in done if not ok and (hi is None or d < hi)), default=None)
    outcomes = [ok for _, ok in done]
    return dict(lo=lo, hi=hi, monotone=outcomes == sorted(outcomes), points=len(done))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("log")
    parser.add_argument("z", type=int, nargs="?")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    data = read(args.log, args.z)
    if args.out:
        Path(args.out).write_text(json.dumps(data, indent=1))
    for s in data["searches"]:
        b = s["bracket"]
        printed = s["printed_bracket"]
        print(f"{s['strategy']} | {len(s['points'])} points | printed {printed} | lo {b['lo']} "
              f"hi {b['hi']} monotone {b['monotone']}")  # fmt: skip
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
