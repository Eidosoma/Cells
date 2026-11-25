"""Registered protocols by the engine model IDs they name (G2's re-qualification list, D176).

Scans every protocol file under validation/ (JSON files whose name contains "protocol", and the
parity protocols in validation/betse/protocols/) for the engine model IDs it names (any string
equal to a model ID in cells.registry.models, or a composite or operator law ID that
registry models declare), and reports each file's status line and the models. A protocol is
affected by D172 when it names resolved_pump_tissue@3 or a model built on it (an operator
composition, water, replacement, division, species, reactions, coupling); the older families
(@1, @2 and the rest) are out of scope (the core's summation scope). Read-only.
Usage: PYTHONPATH=src:. python -m validation.protocol_models [--json OUT]
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# An ID's name@major, its last part: a bare spelling and a full one (D345) give the same key, so a
# protocol that is never rewritten still names its models.
ID = re.compile(r"\b([a-z][a-z0-9_]*@\d+)\b")


def protocol_files():
    files = set(ROOT.glob("validation/**/*protocol*.json"))
    files |= set(ROOT.glob("validation/betse/protocols/*.json"))
    files |= set(ROOT.glob("validation/**/protocols/*.json"))
    return sorted(p for p in files if p.is_file())


def status_of(data):
    for key in ("status", "registration"):
        value = data.get(key) if isinstance(data, dict) else None
        if isinstance(value, str):
            return value
        if isinstance(value, dict) and isinstance(value.get("status"), str):
            return value["status"]
    return None


def engine_model_ids():
    """Model IDs the engine declares (MODEL_ID / *_MODEL_ID string constants in src/cells)."""
    declared = re.compile(r"\b[A-Z_]*MODEL_ID\s*=\s*\"(?:cells\.model\.)?([a-z][a-z0-9_]*@\d+)\"")
    out = set()
    for path in (ROOT / "src" / "cells").rglob("*.py"):
        out.update(declared.findall(path.read_text()))
    return out


def in_scope(model):
    """D172's scope (the core's summation scope): resolved_pump_tissue@3 and the families built
    on it (composite, water, replacement); resolved_pump_tissue@1 and @2 and the older families
    are out."""
    name, major = model.split("@")
    if name == "resolved_pump_tissue":
        return major == "3"
    return name.startswith(("resolved_pump_", "pump_composite"))


def scan():
    known = engine_model_ids()
    rows = []
    for path in protocol_files():
        try:
            text = path.read_text()
            data = json.loads(text)
        except (OSError, ValueError):
            continue
        ids = sorted(set(ID.findall(text)))
        models = sorted(i for i in ids if i in known) if known else ids
        status = status_of(data)
        rows.append(dict(
            file=str(path.relative_to(ROOT)),
            status=(status or "")[:200],
            registered=bool(status and re.search(r"\bregistered\b", status, re.I)
                            and not re.search(r"\bnot registered\b|PROPOSED", status)),
            models=models,
            affected=any(in_scope(m) for m in models),
        ))  # fmt: skip
    return dict(known_models=sorted(known), rows=rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    result = scan()
    if args.json:
        args.json.write_text(json.dumps(result, indent=1) + "\n")
    for r in result["rows"]:
        if r["models"]:
            mark = "R" if r["registered"] else "-"
            print(f"{mark} {'A' if r['affected'] else ' '} {r['file']}: {', '.join(r['models'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
