"""templated_polymerisation@1's opt-in check (FR-38; D148, D284): with no release block, every
registered definition keeps its fingerprint, its structure and its program, and its run bit for
bit.

The registered definitions are FR-25's (fr25_rule.json and its retries): the sixteen worlds of
worlds.names(), at both potential sets, at the steps 2, 1, 0.5 and 0.25 s.

dump DIR [--runs] [--worlds NAME ...]: into a fresh DIR,
- definitions.json: for every registered definition, its fingerprint, the operator's batch
  signature and the composition's structure key;
- programs.json, with programs/: at dt 0.5 s, crossrev's programs
  (validation/tissue/composite_crossrev: the jaxpr text and closed-over constants of the checked
  step, the right-hand side and the device checks) and bindings (the initial state, the layout,
  the controls at every schedule time and the device-check constants: each array's dtype, shape
  and SHA-256);
- with --runs, runs.json: the SHA-256 of every state field at every saved time of the dt 0.5 s
  runs.
compare A B: every entry of A's files equal to B's, or each difference named; exits 1 on any.

Run with the source under test first on the path: PYTHONPATH=SRC:. JAX_ENABLE_X64=1 python -m
validation.gene_regulation.optin_check ...
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

STEPS = (2.0, 1.0, 0.5, 0.25)
PROGRAM_STEP = 0.5
FILES = ("definitions.json", "programs.json", "runs.json")


def _sha(array):
    array = np.ascontiguousarray(np.asarray(array))
    return dict(
        dtype=str(array.dtype),
        shape=list(array.shape),
        sha256=hashlib.sha256(array.tobytes()).hexdigest(),
    )


def _definitions(names, sets):
    from cells.definitions.specs import parse_spec
    from cells.operators import OPERATORS
    from cells.registry.models import get_model
    from validation.gene_regulation import worlds

    op = OPERATORS[worlds.POLYMERISATION]
    out = {}
    for label, symbols in sets.items():
        for name in names:
            for dt in STEPS:
                spec = parse_spec(worlds.world(name, dt=dt, symbols=symbols))
                (declaration,) = [d for d in spec.model.operators if d.law == worlds.POLYMERISATION]
                model = get_model(spec.model)
                out[f"{label} | {name} | dt {dt}"] = dict(
                    fingerprint=spec.fingerprint,
                    batch_signature=repr(op.batch_signature(declaration)),
                    structure_key=repr(getattr(model, "structure_key", None)),
                )
    return out


def _programs(names, sets, directory):
    import jax

    from cells.execution.schedule import control_values
    from validation.gene_regulation import worlds
    from validation.tissue import composite_crossrev as crossrev

    texts = directory / "programs"
    texts.mkdir()
    out = {}
    for label, symbols in sets.items():
        for name in names:
            raw = worlds.world(name, dt=PROGRAM_STEP, symbols=symbols)
            spec, model, arrays = crossrev._setup(raw)
            key = f"{label} | {name}"
            entry = {}
            for kind, closed in crossrev._traced(spec, model, arrays).items():
                text = str(closed)
                stem = f"{crossrev_slug(key)}.{kind}"
                (texts / f"{stem}.txt").write_text(text)
                entry[f"jaxpr.{kind}"] = hashlib.sha256(text.encode()).hexdigest()
                entry[f"consts.{kind}"] = hashlib.sha256(
                    crossrev.const_record(closed).encode()
                ).hexdigest()
            state, layout = model.initial_values(spec)
            times = sorted(
                {0.0, *(c.time for c in spec.experiment.changes), spec.experiment.end_time}
            )
            for prefix, tree in (
                ("state.", state),
                ("layout.", layout),
                ("control.", control_values(spec, times)),
            ):
                for field, value in tree._asdict().items():
                    entry[prefix + field] = _sha(value)
            for field, value in crossrev.check_constants(model, spec):
                entry["check." + field] = _sha(value)
            out[key] = entry
            jax.clear_caches()
    return out


def crossrev_slug(text):
    return "".join(ch if ch.isalnum() else "-" for ch in text).strip("-")


def _runs(names, sets):
    from cells.definitions.specs import parse_spec
    from validation.gene_regulation import engine_run, worlds

    out = {}
    for label, symbols in sets.items():
        for name in names:
            spec = parse_spec(worlds.world(name, dt=PROGRAM_STEP, symbols=symbols))
            states = engine_run.collect(spec)
            out[f"{label} | {name}"] = {
                str(step): {k: _sha(v)["sha256"] for k, v in state._asdict().items()}
                for step, state in sorted(states.items())
            }
            print(label, name, len(states), flush=True)
    return out


def dump(directory, *, runs=False, names=None):
    from validation.gene_regulation import sheet_check as sheet
    from validation.gene_regulation import worlds

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    everything = sheet.potential_sets()
    sets = {k: everything[k] for k in ("test instance", "Spirin's E_pep")}
    names = list(names or worlds.names())
    parts = {
        "definitions.json": lambda: _definitions(names, sets),
        "programs.json": lambda: _programs(names, sets, directory),
    }
    if runs:
        parts["runs.json"] = lambda: _runs(names, sets)
    for file, make in parts.items():
        (directory / file).write_text(json.dumps(make(), indent=1, sort_keys=True) + "\n")
        print(file, flush=True)


def compare(a, b):
    """The differences between two dumps' common files, each named; [] when identical."""
    a, b = Path(a), Path(b)
    found = []
    for file in FILES:
        if not (a / file).exists() or not (b / file).exists():
            continue
        left = json.loads((a / file).read_text())
        right = json.loads((b / file).read_text())
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                found.append(f"{file}: {key} is in one dump only")
                continue
            one, two = left[key], right[key]
            for entry in sorted(set(one) | set(two)):
                if one.get(entry) != two.get(entry):
                    found.append(f"{file}: {key}: {entry} differs")
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    d = sub.add_parser("dump")
    d.add_argument("directory")
    d.add_argument("--runs", action="store_true")
    d.add_argument("--worlds", nargs="+")
    c = sub.add_parser("compare")
    c.add_argument("a")
    c.add_argument("b")
    args = parser.parse_args(argv)
    if args.command == "dump":
        dump(args.directory, runs=args.runs, names=args.worlds)
        return 0
    found = compare(args.a, args.b)
    print("\n".join(found) if found else "identical")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
