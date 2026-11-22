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
verdict A B: the opt-in's D148 case 2 (the lead's ruling, 22 November 2026), from a before dump A
and an after dump B, written to B/verdict.json: every definition's entries equal; every state
field of every run equal at every saved time, the after dump adding only the release's fields,
empty; every program's closed-over constants and existing bindings equal, its added bindings only
the release's, empty; and its jaxprs' equations equal once the equations with an empty output are
set aside (variables' names aside, as one primitive and output types per equation). Exits 1 on any
other difference.

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


# The release's fields (templated_polymerisation's STATE_AXES, LAYOUT_FIELDS and CONTROL_FIELDS).
RELEASE_FIELDS = dict(
    state=("poly_hold_fmol", "poly_hold_released_fmol", "poly_release_heat_pJ"),
    layout=(
        "poly_rel_chain",
        "poly_rel_rate",
        "poly_rel_held",
        "poly_rel_at_release",
        "poly_rel_classes",
        "poly_rel_fate",
        "poly_rel_hold0_fmol",
    ),
    control=("polymerisation_release_fraction", "polymerisation_release_class"),
)
EMPTY = hashlib.sha256(b"").hexdigest()


def _empty(kind):
    """Whether a jaxpr type such as f64[2,0] has an empty dimension."""
    return "[" in kind and "0" in kind[kind.index("[") + 1 : -1].split(",")


def equations(text):
    """Counter of (primitive, output types) of a jaxpr text's equations whose outputs are none of
    them empty, at every depth; names and parameters aside. A sub-jaxpr whose every argument with
    a dimension is empty (a zero-size field's own helper, such as its where) is set aside whole."""
    from collections import Counter

    found, header, skipping = Counter(), None, False
    for raw in text.splitlines():
        line = raw.strip()
        if skipping:
            skipping = not line.startswith("in (")
            continue
        if "{ lambda" in line:
            header = line
        elif header is not None:
            header += " " + line
        if header is not None:
            if ". let" not in header:
                continue
            arguments = header.split("{ lambda", 1)[1].split(". let", 1)[0]
            shaped = [t.split(":", 1)[1] for t in arguments.split() if ":" in t]
            shaped = [t for t in shaped if "[" in t and t[t.index("[") + 1 : -1]]
            skipping = bool(shaped) and all(_empty(t) for t in shaped)
            rest, header = header.split(". let", 1)[1].strip(), None
            if skipping or not rest:
                skipping = skipping and not rest.startswith("in (")
                continue
            line = rest
        if " = " not in line or line.startswith(("let ", "in ")):
            continue
        left, right = line.split(" = ", 1)
        types = tuple(token.split(":", 1)[1] for token in left.split() if ":" in token)
        if any(_empty(t) for t in types):
            continue
        found[(right.split("[")[0].split()[0], types)] += 1
    return found


def verdict(before, after):
    """The opt-in's verdict (module docstring), written to after/verdict.json."""
    before, after = Path(before), Path(after)
    bad, notes = [], dict(added_state=set(), added_bindings=set(), programs_differing=0)
    load = {k: (json.loads((before / k).read_text()), json.loads((after / k).read_text()))
            for k in FILES}  # fmt: skip
    one, two = load["definitions.json"]
    if one != two:
        bad.append("definitions.json differs")
    one, two = load["runs.json"]
    for key in sorted(set(one) | set(two)):
        if set(one.get(key, {})) != set(two.get(key, {})):
            bad.append(f"runs: {key}: the saved steps differ")
            continue
        for step, fields in one[key].items():
            later = two[key][step]
            for field, digest in later.items():
                if field not in fields:
                    notes["added_state"].add(field)
                    if field not in RELEASE_FIELDS["state"] or digest != EMPTY:
                        bad.append(f"runs: {key} at step {step}: {field} added, not empty")
                elif fields[field] != digest:
                    bad.append(f"runs: {key} at step {step}: {field} differs")
            bad += [f"runs: {key} at step {step}: {f} gone" for f in fields if f not in later]
    one, two = load["programs.json"]
    release = {f"{kind}.{name}" for kind, names in RELEASE_FIELDS.items() for name in names}
    for key in sorted(set(one) | set(two)):
        a, b = one.get(key, {}), two.get(key, {})
        for entry in sorted(set(a) | set(b)):
            if entry.startswith("jaxpr."):
                continue
            if entry not in a:
                notes["added_bindings"].add(entry)
                if entry not in release or 0 not in b[entry]["shape"]:
                    bad.append(f"programs: {key}: {entry} added, not an empty release field")
            elif a[entry] != b.get(entry):
                bad.append(f"programs: {key}: {entry} differs")
        stem = crossrev_slug(key)
        for kind in sorted(k[len("jaxpr.") :] for k in a if k.startswith("jaxpr.")):
            if a[f"jaxpr.{kind}"] == b.get(f"jaxpr.{kind}"):
                continue
            notes["programs_differing"] += 1
            texts = [(d / "programs" / f"{stem}.{kind}.txt").read_text() for d in (before, after)]
            if equations(texts[0]) != equations(texts[1]):
                bad.append(f"programs: {key}: {kind}'s equations differ beyond the empty fields")
    record = dict(
        kind="cells.gene_regulation.optin_verdict@1",
        before=str(before),
        after=str(after),
        passed=not bad,
        differences=bad,
        added_state_fields=sorted(notes["added_state"]),
        added_bindings=sorted(notes["added_bindings"]),
        programs_with_other_text=notes["programs_differing"],
    )
    (after / "verdict.json").write_text(json.dumps(record, indent=1) + "\n")
    return record


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
    v = sub.add_parser("verdict")
    v.add_argument("a")
    v.add_argument("b")
    args = parser.parse_args(argv)
    if args.command == "dump":
        dump(args.directory, runs=args.runs, names=args.worlds)
        return 0
    if args.command == "verdict":
        record = verdict(args.a, args.b)
        print(json.dumps({k: v for k, v in record.items() if k != "differences"}, indent=1))
        print("\n".join(record["differences"][:20]))
        return 0 if record["passed"] else 1
    found = compare(args.a, args.b)
    print("\n".join(found) if found else "identical")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
