"""The pair check of cells.operator.integer_unit_population@1: every world of the operator, traced
and run at two revisions, and compared field by field and program by program (the passivity proof of
a change that adds leaves where nothing reads them).

Its origin is D400's development pair check of the per-event counts (the counts fix's D148 round,
26 November 2026: `/mnt/workspaces/Cells/fr43-cowriters-build-20261126/trace-counts-dev/`, its
paircheck.py, normalized.py, shape_compare.py and divided_check.py), brought into the checkout
for FR-52 at the lead's direction and generalized from that one leaf to any declared new leaves.
Its logic is D400's: only the leaf names, the leaf checks and the paths became arguments.

For each world (definitions built once, as JSON, and read by both revisions), each revision
(PYTHONPATH at its own snapshot) writes, with `trace`:
- the four programs composite_crossrev traces (checked step, rhs, device checks, with margins):
  the full jaxpr text, its constant record, and the text after dead-code elimination with the new
  state leaves' outputs unused (jax's dce_jaxpr; a revision without them keeps every output);
- the bindings (composite_crossrev's: initial state, layout, controls, check constants);
- every state field at every step of a windowed run with full recording.
`compare` then holds: every program's eliminated text and constant record equal; every binding
present in both equal, and the head's extra bindings exactly the new leaves; every field present
in both equal at every step, bit for bit; the head's only extra state fields the new state
leaves, each passing its named leaf check:
- "trace-counts" (D400): the counts recorded at each row's last event are the carried counts,
  and the slots beyond hold -1;
- "zero-size" (FR-52 where no cohort is declared): the leaf holds no value at any row.
`normalized` and `shapes` print what is left of each eliminated step's difference (alpha-renamed,
or with every name replaced, the loops' ft_in/ft_out lines dropped). `divided` removes, from the
head's eliminated step of a dividing world, the lines that and a finiteness test of a new leaf into
the step's validity (the partition's check over every field), and compares what is left.

Usage (from a revision's snapshot, its PYTHONPATH; JAX_ENABLE_X64=1, CPUs per AGENTS.md):
  python -B -m validation.fr43_part3.pair_check build DEFS
  python -B -m validation.fr43_part3.pair_check build-registration DEFS INPUTS   (needs
      validation.fr43_part3_cowriters: the registration's invented W5 and W6)
  python -B -m validation.fr43_part3.pair_check trace DEFS OUT --new FIELD [FIELD ...]
  python -B -m validation.fr43_part3.pair_check compare BASE HEAD OUT_JSON --new FIELD ...
      [--new-layout FIELD ...] [--check FIELD=trace-counts|zero-size ...]
  python -B -m validation.fr43_part3.pair_check normalized BASE HEAD OUT_JSON
  python -B -m validation.fr43_part3.pair_check shapes BASE HEAD OUT_JSON
  python -B -m validation.fr43_part3.pair_check divided BASE HEAD WORLD --new FIELD ...
"""

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

import numpy as np

KINDS = ("checked_step", "rhs", "device_checks", "device_checks_margins")
STATE_OUTPUTS = {"checked_step": 1, "rhs": 0}  # Programs whose outputs are the state (+ extras).
DEFINED = re.compile(r"\b([a-z]{1,4}):[a-z]")
TOKEN = re.compile(r"\b[a-z]{1,4}\b")


# ------------------------------------------------------------------ the worlds


def build(defs):
    """D400's seven worlds of the operator from validation/fr43_part3/worlds.py, as JSON."""
    from validation.fr43_part3 import worlds as w

    defs = Path(defs)
    defs.mkdir(parents=True, exist_ok=True)
    made = {
        "reactions_integer_source": w.source_world(dt=0.01, end=2.0),
        "part3_W1": w.spec_world("W1_two_subunits_feedback", dt=0.02, end=6.0, every=0.02),
        "part3_W3": w.spec_world("W3_two_way_turnover", dt=0.01, end=2.0, every=0.01),
        "five_writers": w.five_writers(dt=0.02, end=4.0),
        "gene_cowriters": w.gene_cowriters(dt=0.5, end=60.0),
        "divided_with_trace": w.divided(sites=1, transfer=True, counts={"free": 0, "active": 1},
                                        at=0.2, end=0.4, dt=0.01, every=0.01, seed=5),
        "many_sites_no_trace": w.many_sites("W1_two_subunits_feedback", 8, dt=0.02, end=1.0,
                                            every=0.02, seed=3, trace=0),
    }  # fmt: skip
    for name, raw in made.items():
        (defs / f"{name}.json").write_text(json.dumps(raw, sort_keys=True))
    print(sorted(made))


def build_registration(defs, inputs):
    """The co-writers registration's invented W5 and W6 at their coarsest rungs (D400's two)."""
    from validation.fr43_part3_cowriters import worlds

    defs = Path(defs)
    defs.mkdir(parents=True, exist_ok=True)
    data = worlds.read_inputs(inputs)
    for label, name in (
        ("registration_W5", "W5 reactions-first h=0.0244140625 c0"),
        ("registration_W6", "W6 gene-first h=0.46875 c0"),
    ):
        raw = worlds.definition(data, worlds.find_run(data, name))
        (defs / f"{label}.json").write_text(json.dumps(raw, sort_keys=True))
    print("registration_W5, registration_W6")


# ------------------------------------------------------------------ one revision


def eliminated(closed, fields, kind, new):
    """The closed jaxpr's text after dead-code elimination: for the checked step and the rhs,
    whose outputs are the state's leaves in field order (the step's validity after them), the new
    leaves' outputs unused where the state holds them; the row checks keep every output."""
    from jax._src.interpreters import partial_eval as pe

    jaxpr = closed.jaxpr
    used = [True] * len(jaxpr.outvars)
    held = [f for f in new if f in fields]
    if held and kind in STATE_OUTPUTS:
        if len(jaxpr.outvars) != len(fields) + STATE_OUTPUTS[kind]:
            raise ValueError(f"{kind}: {len(jaxpr.outvars)} outputs for {len(fields)} fields")
        for f in held:
            used[fields.index(f)] = False
    out, used_inputs = pe.dce_jaxpr(jaxpr, used, instantiate=False)
    return str(out), [i for i, u in enumerate(used_inputs) if not u]


def crossrev_bindings(raw, target):
    """composite_crossrev.bindings' arrays for one definition (its loop body, one world)."""
    from cells.definitions.specs import parse_spec
    from cells.execution.schedule import control_values
    from cells.registry.models import get_model
    from validation.tissue import composite_crossrev as crossrev

    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, layout = model.initial_values(spec)
    times = sorted({0.0, *(c.time for c in spec.experiment.changes), spec.experiment.end_time})
    arrays = {}
    for prefix, tree in (("state.", state), ("layout.", layout),
                         ("control.", control_values(spec, times))):  # fmt: skip
        for key, value in tree._asdict().items():
            arrays[prefix + key] = np.asarray(value)
    for key, value in crossrev.check_constants(model, spec):
        arrays["check." + key] = value
    np.savez(target, **arrays)


def trace(defs, out, new):
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.definitions.specs import parse_spec
    from cells.execution.windows import WindowPolicy, iter_windows
    from validation.tissue import composite_crossrev as crossrev

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    report = {}
    for path in sorted(Path(defs).glob("*.json")):
        name, raw = path.stem, json.loads(path.read_text())
        spec, model, arrays = crossrev._setup(raw)
        fields = list(model.STATE_TYPE._fields)
        row = dict(fields=fields, dropped={})
        for kind, closed in crossrev._traced(spec, model, arrays).items():
            (out / f"{name}.{kind}.txt").write_text(str(closed))
            (out / f"{name}.{kind}.consts.json").write_text(crossrev.const_record(closed))
            text, dropped = eliminated(closed, fields, kind, new)
            (out / f"{name}.{kind}.dce.txt").write_text(text)
            row["dropped"][kind] = dropped
        crossrev_bindings(raw, out / f"{name}.bindings.npz")
        spec = parse_spec(raw)
        steps = int(round(spec.experiment.end_time / spec.execution.dt))
        rows = {}
        for window in iter_windows(spec, WindowPolicy(steps, "full"), None):
            for i, _ in enumerate(np.asarray(window.times)):
                rows[window.start_step + i] = [np.asarray(v)[i] for v in window.history]
        order = sorted(rows)
        stacked = {f: np.stack([rows[k][j] for k in order]) for j, f in enumerate(fields)}
        np.savez(out / f"{name}.rows.npz", **stacked)
        row["steps"] = len(order)
        report[name] = row
        print(name, "traced and run:", len(order), "rows", flush=True)
    (out / "trace.json").write_text(json.dumps(report, indent=1))


# ------------------------------------------------------------------ the comparison


def same_array(a, b):
    return a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()


def check_trace_counts(rows, leaf):
    """D400's leaf check: the counts recorded at each row's last event are the carried counts,
    and the unused slots hold -1. (rows and sites checked, departures)."""
    recorded, events, counts = rows[leaf], rows["integer_events"], rows["integer_counts"]
    checked = bad = 0
    capacity = recorded.shape[2]
    for k in range(recorded.shape[0]):
        for s in range(recorded.shape[1]):
            n = int(events[k, s])
            if 0 < n <= capacity:
                checked += 1
                bad += not np.array_equal(recorded[k, s, n - 1], counts[k, s])
            if n < capacity and not np.all(recorded[k, s, n:] == -1):
                bad += 1
    return dict(capacity=int(capacity), rows_sites_checked=checked, departures=bad)


def check_zero_size(rows, leaf):
    """FR-52's leaf check where no cohort is declared: the leaf holds no value at any row."""
    size = int(rows[leaf][0].size) if len(rows[leaf]) else 0
    return dict(values_per_row=size, departures=int(size != 0))


LEAF_CHECKS = {"trace-counts": check_trace_counts, "zero-size": check_zero_size}


def compare(base, head, out_json, new, new_layout=(), checks=None):
    base, head = Path(base), Path(head)
    tb = json.loads((base / "trace.json").read_text())
    th = json.loads((head / "trace.json").read_text())
    checks = dict(checks or {})
    expected_bindings = sorted([f"state.{f}" for f in new] + [f"layout.{f}" for f in new_layout])
    result, faults = {}, []
    for name in sorted(set(tb) | set(th)):
        if name not in tb or name not in th:
            faults.append(f"{name}: in one revision only")
            continue
        r = {}
        extra = [f for f in th[name]["fields"] if f not in tb[name]["fields"]]
        missing = [f for f in tb[name]["fields"] if f not in th[name]["fields"]]
        r["head_only_fields"], r["base_only_fields"] = extra, missing
        if sorted(extra) != sorted(new) or missing:
            faults.append(f"{name}: fields differ beyond the new leaves: {extra}, {missing}")
        for kind in KINDS:
            for suffix in ("dce.txt", "consts.json"):
                a = (base / f"{name}.{kind}.{suffix}").read_bytes()
                b = (head / f"{name}.{kind}.{suffix}").read_bytes()
                r[f"{kind}.{suffix}"] = "identical" if a == b else "DIFFERS"
                if a != b:
                    faults.append(f"{name}: {kind}.{suffix} differs")
            full = (base / f"{name}.{kind}.txt").read_bytes() == (
                head / f"{name}.{kind}.txt"
            ).read_bytes()
            r[f"{kind}.txt"] = "identical" if full else "differs (the new leaves)"
        ba = np.load(base / f"{name}.bindings.npz")
        ha = np.load(head / f"{name}.bindings.npz")
        only = sorted(set(ha.files) - set(ba.files))
        gone = sorted(set(ba.files) - set(ha.files))
        unequal = [k for k in sorted(set(ba.files) & set(ha.files)) if not same_array(ba[k], ha[k])]
        r["bindings"] = dict(common=len(set(ba.files) & set(ha.files)), unequal=unequal,
                             head_only=only, base_only=gone)  # fmt: skip
        if unequal or gone or only != expected_bindings:
            faults.append(f"{name}: bindings {unequal}, {only}, {gone}")
        br = np.load(base / f"{name}.rows.npz")
        hr = np.load(head / f"{name}.rows.npz")
        unequal_rows = [f for f in br.files if not same_array(br[f], hr[f])]
        r["rows"] = dict(steps=int(br[br.files[0]].shape[0]), fields_compared=len(br.files),
                         unequal=unequal_rows)  # fmt: skip
        if unequal_rows:
            faults.append(f"{name}: fields differ at some step: {unequal_rows}")
        for leaf, check in checks.items():
            found = LEAF_CHECKS[check](hr, leaf)
            r[f"leaf {leaf}"] = found
            if found["departures"]:
                faults.append(f"{name}: the new leaf {leaf} fails its check ({found})")
        result[name] = r
    verdict = dict(worlds=len(result), new=list(new), new_layout=list(new_layout), faults=faults,
                   verdict="pass" if not faults else "FAIL", per_world=result)  # fmt: skip
    Path(out_json).write_text(json.dumps(verdict, indent=1))
    print(verdict["verdict"], len(result), "worlds;", faults)
    return 0 if not faults else 1


def renamed(text):
    """The text's lines, the loops' ft_in/ft_out lines dropped, variables renamed in order of
    first appearance (alpha-renaming)."""
    defined = set(DEFINED.findall(text))
    names = {}

    def sub(m):
        t = m.group(0)
        return names.setdefault(t, f"v{len(names)}") if t in defined else t

    kept = [x for x in text.splitlines() if "ft_in=" not in x and "ft_out=" not in x]
    return [TOKEN.sub(sub, x) for x in kept]


def canonical(text):
    """The text's lines with every variable replaced by "_", ft_in/ft_out lines dropped: the
    operations, their parameters, shapes and dtypes in order, wiring aside."""
    defined = set(DEFINED.findall(text))
    return [TOKEN.sub(lambda m: "_" if m.group(0) in defined else m.group(0), x)
            for x in text.splitlines() if "ft_in=" not in x and "ft_out=" not in x]  # fmt: skip


def _step_differences(base, head, out_json, form):
    base, head = Path(base), Path(head)
    out = {}
    for a in sorted(base.glob("*.checked_step.dce.txt")):
        la, lb = form(a.read_text()), form((head / a.name).read_text())
        codes = difflib.SequenceMatcher(a=la, b=lb, autojunk=False).get_opcodes()
        ops = [(t, la[i1:i2], lb[j1:j2]) for t, i1, i2, j1, j2 in codes if t != "equal"]
        out[a.name.split(".")[0]] = [dict(op=t, base=x, head=y) for t, x, y in ops]
    Path(out_json).write_text(json.dumps(out, indent=1))
    for k, v in out.items():
        print(k, "identical" if not v else json.dumps(v)[:900])
    return 0


def divided(base, head, world, new_shapes):
    """The dividing world's eliminated step: remove the head's lines that and a finiteness test of
    a new leaf into the validity (x: a bool of the leaf's shape, broadcast True for an integer leaf
    or is_finite of it for a float one; y = reduce_and x; z = and w y), read w for z wherever z is
    read, alpha-rename both programs, and compare."""
    a = (Path(base) / f"{world}.checked_step.dce.txt").read_text()
    lines = (Path(head) / f"{world}.checked_step.dce.txt").read_text().splitlines()
    removed = []
    for shape in new_shapes:
        test = r"(broadcast_in_dim.* True:bool\[\]|is_finite [a-z]+)$"
        pattern = re.compile(r"\s*([a-z]+):bool\[" + re.escape(shape) + r"\] = " + test)
        i = next((k for k, x in enumerate(lines) if pattern.match(lines[k])), None)
        if i is None:
            continue
        x = re.match(r"\s*([a-z]+):", lines[i]).group(1)
        reduce = r"\s*([a-z]+):bool\[\] = reduce_and\[[^\]]*\] " + x + r"$"
        y = re.match(reduce, lines[i + 1]).group(1)
        m = re.match(r"\s*([a-z]+):bool\[\] = and ([a-z]+) " + y + r"$", lines[i + 2])
        z, w = m.group(1), m.group(2)
        lines = lines[:i] + [re.sub(r"\b" + z + r"\b", w, line) for line in lines[i + 3 :]]
        removed.append(dict(shape=shape, lines=[x, y, f"{z} = and {w} {y}"]))
    same = renamed(a) == renamed("\n".join(lines))
    print(f"removed {removed}; identical after: {same}")
    return 0 if same else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build").add_argument("defs")
    p = sub.add_parser("build-registration")
    p.add_argument("defs")
    p.add_argument("inputs")
    p = sub.add_parser("trace")
    p.add_argument("defs")
    p.add_argument("out")
    p.add_argument("--new", nargs="+", default=[])
    p = sub.add_parser("compare")
    p.add_argument("base")
    p.add_argument("head")
    p.add_argument("out_json")
    p.add_argument("--new", nargs="+", default=[])
    p.add_argument("--new-layout", nargs="+", default=[])
    p.add_argument("--check", nargs="+", default=[])
    for name in ("normalized", "shapes"):
        p = sub.add_parser(name)
        p.add_argument("base")
        p.add_argument("head")
        p.add_argument("out_json")
    p = sub.add_parser("divided")
    p.add_argument("base")
    p.add_argument("head")
    p.add_argument("world")
    p.add_argument("--shapes", nargs="+", required=True, help="the new leaves' shapes, e.g. 0,2,4")
    args = parser.parse_args(argv)
    if args.command == "build":
        return build(args.defs)
    if args.command == "build-registration":
        return build_registration(args.defs, args.inputs)
    if args.command == "trace":
        return trace(args.defs, args.out, args.new)
    if args.command == "compare":
        checks = dict(item.split("=", 1) for item in args.check)
        return compare(args.base, args.head, args.out_json, args.new, args.new_layout, checks)
    if args.command in ("normalized", "shapes"):
        form = renamed if args.command == "normalized" else canonical
        return _step_differences(args.base, args.head, args.out_json, form)
    return divided(args.base, args.head, args.world, args.shapes)


if __name__ == "__main__":
    sys.exit(main() or 0)
