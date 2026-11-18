"""Write the viewer's table of the law-port inventory: the laws no active model declares behind the atlas's units.

On 17 November 2026 the project decided to port tested older laws to the active engine
(D211, the engine's docs/DECISIONS.md). Its first step was a read-only inventory of
the law IDs behind the Protein atlas's units that no active model declares, one row per law,
each with a mark: "port as is", "fold into an owner's planned law" or "not a port". This tool
reads that inventory, given by path, and writes the table the page reads
(data/laws/law_port.json, cells.visualizer.law_port@1, held to schema/LAWS_LIBRARY.md):

    for each row  its law ID (or, for a row without one, what the inventory calls it),
                  its units, its mark and its tests' class
    as a whole    the inventory's own kind, made and head, and the counts

Nothing else of the inventory is copied, and no path is written, so the same inventory gives
the same bytes wherever it lies. The inventory is another session's working record: it is
read, never written. The page's words for each mark live in src/lenses/law_port.js.

The tool refuses (exit status 2, nothing written) an inventory of another kind, and fails if
its rows do not hold 47 laws to port as is, 5 to fold into an owner's planned law and 2 that
are not a port, on 38 units; if a law to port as is has no passing test (its words say
"tested"); if a law to fold is not the cardiac lane's (its words say so); or if the
inventory's own counts of its marks differ from its rows.

    python3 -I tools/extract_law_port.py --inventory PATH/inventory.json [--out data/laws/law_port.json | -]

Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FORMAT = "cells.visualizer.law_port@1"
# The inventory's kind: its name and major, and any words it adds in brackets ("(working record, D211)").
KIND = re.compile(r"^cells\.law_port_inventory@1(?: \([^()]*\))?$")
# A law ID as the atlas writes it: a name and a version, with no space (cagpotassium_numeric_mM_scale@1 has capitals).
LAW_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*@[0-9]+$")
UNIT = re.compile(r"^U[0-9]{2}$")
# The three marks, in the order the page says them, and how many rows each holds (D211's inventory of 17 November 2026).
MARKS = {"port as is": 47, "fold into an owner's planned law": 5, "not a port": 2}
UNITS = 38
# The tests' classes that pass (the inventory's definitions: a, a passing kernel-against-reference
# test; b, passing family-level tests only; c, failing or skipped; d, no test).
PASSING = {"a", "b"}
# Who a law to fold goes to, as the page says it: the cardiac lane.
FOLD_OWNER = "Cardiac lane"


class Refused(Exception):
    """An inventory the tool will not read, or one whose rows do not hold what the page says of them."""


def units_of(text, law):
    units = [part.strip() for part in str(text).split(",") if part.strip()]
    if not units or not all(UNIT.match(unit) for unit in units):
        raise Refused(f"{law}: its atlas_units are not a list of units: {text!r}")
    if len(set(units)) != len(units):
        raise Refused(f"{law}: a unit is named twice: {text!r}")
    return units


def build(inventory):
    kind = inventory.get("kind")
    if not isinstance(kind, str) or not KIND.match(kind):
        raise Refused(f"not a cells.law_port_inventory@1 inventory: kind is {kind!r}")
    for key in ("made", "head"):
        if not isinstance(inventory.get(key), str) or not inventory[key]:
            raise Refused(f"the inventory states no {key}")
    rows = inventory.get("rows")
    if not isinstance(rows, list) or not rows:
        raise Refused("the inventory has no rows")
    out, seen = [], set()
    for row in rows:
        law = row.get("law_id")
        if not isinstance(law, str) or not law:
            raise Refused(f"a row has no law_id: {json.dumps(row)[:120]}")
        if law in seen:
            raise Refused(f"{law} is listed twice")
        seen.add(law)
        mark = (row.get("owner") or {}).get("mark")
        if mark not in MARKS:
            raise Refused(f"{law}: a mark the page has no words for: {mark!r}")
        test_class = (row.get("tests") or {}).get("test_class")
        if test_class not in {"a", "b", "c", "d"}:
            raise Refused(f"{law}: a tests' class the inventory does not define: {test_class!r}")
        if mark == "port as is" and test_class not in PASSING:
            raise Refused(f"{law}: to be ported as is, but its tests' class is {test_class!r}, not a passing one")
        if mark == "fold into an owner's planned law" and not str((row.get("owner") or {}).get("owner", "")).startswith(FOLD_OWNER):
            raise Refused(f"{law}: to be folded, but not into the cardiac lane's laws")
        out.append({"law": law, "has_id": bool(LAW_ID.match(law)), "units": units_of(row.get("atlas_units"), law), "mark": mark, "test_class": test_class})
    marks = Counter(row["mark"] for row in out)
    if dict(marks) != MARKS:
        raise Refused(f"the marks are {dict(marks)}, not {MARKS}")
    stated = (inventory.get("counts") or {}).get("owner_mark")
    if stated is not None and stated != dict(marks):
        raise Refused(f"the inventory's own counts of its marks ({stated}) are not its rows' ({dict(marks)})")
    units = sorted({unit for row in out for unit in row["units"]})
    if len(units) != UNITS:
        raise Refused(f"the rows name {len(units)} units, not {UNITS}")
    return {
        "format": FORMAT,
        "note": "The law-port inventory's rows, as the page reads them: each law no active model declares behind the Protein atlas's units, with its units, its mark and its tests' class. Made by tools/extract_law_port.py from the inventory, which it reads and never writes; not edited by hand (schema/LAWS_LIBRARY.md).",
        "inventory": {"kind": kind, "made": inventory["made"], "head": inventory["head"]},
        "counts": {"rows": len(out), "units": len(units), "marks": {mark: marks[mark] for mark in MARKS}, "test_class": dict(sorted(Counter(row["test_class"] for row in out).items()))},
        "rows": out,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--inventory", required=True, help="the law-port inventory (cells.law_port_inventory@1), read and never written")
    parser.add_argument("--out", default=str(ROOT / "data" / "laws" / "law_port.json"), help="the table to write, or - for standard output")
    args = parser.parse_args(argv)
    try:
        data = build(json.loads(Path(args.inventory).read_text()))
    except Refused as refused:
        print(f"refused: {refused}", file=sys.stderr)
        return 2
    text = json.dumps(data, indent=1, ensure_ascii=False) + "\n"
    if args.out == "-":
        sys.stdout.write(text)
    else:
        Path(args.out).write_text(text)
        counts = data["counts"]
        print(f"{counts['rows']} laws on {counts['units']} units ({', '.join(f'{n} {mark}' for mark, n in counts['marks'].items())}); "
              f"inventory made {data['inventory']['made']} at {data['inventory']['head'][:8]} -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
