"""FR-64's port checks: FR-51's judged engine rows and FR-50 phase 2's, base against head.

The lead's rulings of 27 November (docs/FR64_VOLTAGE_SHIFT_DESIGN.md §17.6). FR-64 moves FR-51's
block `reference` key into the population's voltage_shift. The live drivers translate the frozen
cases (validation/fr51/engine.py, validation/fr50/engine.py; D371 Q7), so each judge's engine rows
must be the base's, byte for byte. The registered verdicts stay D377's and D405's. The judges
themselves are rerun on the head by their own commands; this tool compares the rows.

**dump** writes every engine row for every case, honest and planted, under the code it runs in:
- FR-51 (`--fr51-references`, the tagged references' results directory):
  - each case at its references' voltages (validation.fr51.engine.engine);
  - each case of each JUDGED plant, under that plant (validation/fr51/plants.py).
- FR-50 phase 2 (`--fr50-references`): each case's request (validation/fr50/judge.request_for), and
  each case of each phase-2 plant under that plant (judge.PLANTS). E5's refusal rows, which have no
  reference, are asked for as the judge asks for them.

**compare** reads two dumps and lists every difference. A difference is any of these:
- a key on one side only;
- a dtype, shape or byte that differs;
- a value that is not an array and is unequal.

None is tolerated: an ulp stops the build for the lead's ruling (ruling 3).

**Run it as a script, not as a module,** from the head's checkout, with the snapshot under test
first on the path:

    cd SNAPSHOT && PYTHONPATH=SNAPSHOT/src:SNAPSHOT python -B \
        HEAD/validation/fr64/port_check.py dump \
        --fr51-references REFS51 --fr50-references REFS50 --out OUT

So the base, which lacks this file, runs its own drivers and engine. The tool imports nothing of
validation.fr64.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np


def _leaves(value, path=""):
    """(path, leaf) of a nested engine result: dicts by sorted key, lists and tuples by index."""
    if isinstance(value, dict):
        for key in sorted(value, key=str):
            yield from _leaves(value[key], f"{path}/{key}")
    elif isinstance(value, (list, tuple)) and not (
        value and all(isinstance(v, (int, float, np.floating, np.integer)) for v in value)
    ):
        for k, item in enumerate(value):
            yield from _leaves(item, f"{path}[{k}]")
    else:
        yield path, value


def _record(value):
    """A leaf as a comparable record: an array's dtype, shape and bytes, or a JSON value."""
    if isinstance(value, (np.ndarray, np.generic, list, tuple, float, int)) and not isinstance(
        value, bool
    ):
        array = np.asarray(value)
        if array.dtype != object:
            return {"dtype": str(array.dtype), "shape": list(array.shape),
                    "bytes": array.tobytes().hex()}  # fmt: skip
    return {"value": value if isinstance(value, (str, bool, type(None))) else repr(value)}


def _rows(result):
    return {path: _record(leaf) for path, leaf in _leaves(result)}


def dump_fr51(references):
    from validation.fr51 import engine, judge, plants

    refs = judge.read_results(Path(references))
    out = {}
    for case_id, ref in sorted(refs.items()):
        out[f"fr51/{case_id}/honest"] = _rows(engine.engine(case_id, ref.voltages))
    for name, (plant, _criterion, cases) in plants.JUDGED.items():
        with plant():
            for case_id in cases:
                result = engine.engine(case_id, refs[case_id].voltages)
                out[f"fr51/{case_id}/{name}"] = _rows(result)
    return out


def dump_fr50(references):
    from validation.fr50 import engine, judge

    refs = judge.read_results(Path(references), phase=2)
    out = {}
    for case_id, ref in sorted(refs.items()):
        out[f"fr50/{case_id}/honest"] = _rows(engine.engine(judge.request_for(ref)))
        for name, plant in judge.PLANTS.items():
            if plant["kind"] == ref.case_kind:
                result = engine.engine(judge.request_for(ref, plant=name))
                out[f"fr50/{case_id}/{name}"] = _rows(result)
    out["fr50/E5/honest"] = _rows(engine.engine(dict(kind="E5", plant=None)))  # As the judge asks.
    return out


def compare(base, head):
    """Every difference between two dumps, as lines (none: identical)."""
    out = []
    for group in sorted(set(base) | set(head)):
        if group not in base or group not in head:
            out.append(f"{group}: only in {'head' if group in head else 'base'}")
            continue
        a, b = base[group], head[group]
        for path in sorted(set(a) | set(b)):
            if path not in a or path not in b:
                out.append(f"{group}{path}: only in {'head' if path in b else 'base'}")
            elif a[path] != b[path]:
                out.append(f"{group}{path}: differs ({a[path].get('dtype', 'value')})")
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    dump = sub.add_parser("dump")
    dump.add_argument("--fr51-references", required=True)
    dump.add_argument("--fr50-references", required=True)
    dump.add_argument("--out", required=True, type=Path)
    both = sub.add_parser("compare")
    both.add_argument("base", type=Path)
    both.add_argument("head", type=Path)
    args = parser.parse_args(argv)
    if args.command == "dump":
        rows = dump_fr51(args.fr51_references) | dump_fr50(args.fr50_references)
        args.out.write_text(json.dumps(rows, sort_keys=True))
        print(f"{len(rows)} groups written to {args.out}")
        return 0
    differences = compare(json.loads(args.base.read_text()), json.loads(args.head.read_text()))
    print("\n".join(differences) if differences else "identical")
    return 1 if differences else 0


if __name__ == "__main__":
    sys.exit(main())
