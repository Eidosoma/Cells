"""L4 agreement of the composite on W1, W2 and G2-Q1 (docs/PUMP_COMPOSITE_V2_DESIGN.md §5).

A backend variant of each qualification's own registered protocol, by the method of
validation/betse/backend_variant.py. That module's tolerance helper is not imported here:
it sits beside BETSE-side modules (AGENTS.md), so up1 is restated below. The variant keeps
each protocol's worlds, quantities, references and judge. It adds measured backend terms:

* three blind L4 repeats A, B and D before the judged run C. The backend term is the
  largest |CPU reference - X| over the three; the run-to-run term is the largest difference
  between two of them (A-B, A-D, B-D), per world and quantity. One pair is not enough: on
  the L4 dispatch test's saved windows a further run exceeded 3 x one pair's spread in 2.8%
  of field entries (up to 13.6x), against 1.3% (up to 6.05x) for the spread of three runs
  (window-timing-20261112-01/results/l4-repeats.json). Each part uses its own difference
  measure: W1 absolute, max over records; W2 volume and route cycles relative and voltage
  absolute, per arm and branch; G2-Q1 the judge's own worst-difference function;
* a tolerance that is 3 x a sum of terms (W1's trajectories, G2-Q1) becomes
  max(registered, up1(3 x (registered / 3 + backend + run-to-run))). A fixed tolerance
  (W1's stationary bounds, W2) becomes max(registered, up1(3 x (backend + run-to-run))).
  With no added term the registered value is kept exactly: these protocols' tolerances
  are not rounded, and up1 alone would loosen them;
* stop rule, before the judged run C: stop if a backend term exceeds the registered sum
  (or a fixed tolerance), or if a W1 or W2 convergence or a W2 classification changed.
  Diagnose instead; do not register;
* verdict: each qualification's own driver runs on C with the variant protocol written
  here (its --protocol). C against the CPU reference is reported, not judged; so is
  |A - C| over the run-to-run term, per quantity (the deviation action): a judged run's
  own scatter beyond the repeats' shows there.

Actions:
  run --part {w1,w2,g2} --output FILE [--worlds NAME,...] [--backend {cpu,gpu}]
      the part's judged quantities (raw engine values) with the backend used and the run's
      seconds. The registered definitions declare the CPU, and a definition's declared
      backend selects its device, so an L4 repeat runs with --backend gpu (every
      definition's execution backend set, nothing else); the CPU reference runs as
      registered
  terms --part P --reference CPU --runs A B D --output FILE
      measured terms, with each repeat's backend term and each pair's run-to-run term; W2
      also reads the qualification's own w2-judge.json. Each of CPU, A, B and D is one file
      or a comma-separated list of the files of one run split over GPU gaps with run
      --worlds: they are merged (each world once, one backend), and A, B and D must cover
      the reference's worlds exactly
  variant --part P --terms FILE --output DIR
      variant.json (tolerances, stop rule, report rows with every repeat's and pair's
      term, the three repeats' files) and protocol.json
  deviation --part P --terms FILE --judged C --output FILE
      |A - C| per quantity (the part's own measure) and its ratio to the run-to-run term,
      A being the terms' first repeat
Everything written is PROPOSED until the lead registers it.
"""

import argparse
import copy
import itertools
import json
import math
import platform
import sys
from pathlib import Path
from time import perf_counter

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if __name__ == "__main__":
    for entry in (ROOT / "src", ROOT):
        if str(entry) not in sys.path:
            sys.path.insert(0, str(entry))

MARGIN = 3.0
REPEATS = ("A", "B", "D")  # The blind L4 repeats measured before the judged run C.
TISSUE = ROOT / "validation" / "tissue"
FILES = dict(
    w1=("pump_water_predictions.json", "pump_water_protocol.json"),
    w2=("pump_water_kcc_predictions.json", "pump_water_kcc_protocol.json"),
    g2=("cell_replacement_q1_predictions.json", "cell_replacement_protocol.json"),
)
# (saved quantity, the protocol's bound, relative?)
W2_QUANTITIES = (
    ("volume_pL", "volume_relative", True),
    ("membrane_voltage_V", "voltage_V", False),
    ("route_cycles_fmol_s", "cycles_relative", True),
)
W1_STATIONARY = W2_QUANTITIES[:2]
G2_KEYS = ("membrane_voltage_V", "slot_amount_fmol")
STATUS = "PROPOSED backend variant (composite L4 agreement), not registered."
# Registering a variant replaces this status with one beginning "registered" (a commit by
# the lead); judges then accept the file for a judged run (judged_protocol).


def up1(x):
    """Round up to one significant figure (the backend-variant method's rule)."""
    if x <= 0:
        return 0.0
    e = math.floor(math.log10(x))
    return float(f"{math.ceil(round(x / 10**e, 9)) * 10**e:.1e}")


def registered(part):
    """(predictions, protocol) of the part at this revision."""
    return tuple(json.loads((TISSUE / name).read_text()) for name in FILES[part])


BASES = {part: f"validation/tissue/{names[1]}" for part, names in FILES.items()}


# ------------------------------------------------------------------ judged runs


def tolerance_sites(part, base):
    """Key paths of the tolerances a backend variant may widen; nothing else may differ."""
    if part == "w1":
        sites = [
            ("tolerances", w, q) for w, quantities in base["tolerances"].items() for q in quantities
        ]
        return sites + [("stationary", bound) for _, bound, _ in W1_STATIONARY]
    if part == "w2":
        return [("stationary", bound) for _, bound, _ in W2_QUANTITIES]
    cases = base["pinned_tolerances"]["cases"]
    return [
        ("pinned_tolerances", "cases", case, entry, "tolerance")
        for case, entries in cases.items()
        for entry in entries
        if entry.startswith(("q3_", "q4_"))
    ]


def _at(tree, path):
    for key in path:
        tree = tree[key]
    return tree


def variant_errors(part, candidate, base):
    """Why `candidate` is not a registered backend variant of `base` (empty: it is one).

    Its backend_variant block says registered and names the base protocol. Every field but
    that block and the widened tolerances equals the registered protocol's (compared field by
    field against the registered file). A widened tolerance is never below the registered one.
    """
    block = candidate.get("backend_variant")
    if not isinstance(block, dict):
        return ["it has no backend_variant block"]
    errors = []
    status = block.get("status")
    if not (isinstance(status, str) and status.startswith("registered")):
        errors.append("its backend_variant status does not say registered")
    if block.get("base") != BASES[part]:
        errors.append(f"its backend_variant block does not name the base protocol {BASES[part]}")
    rest = copy.deepcopy({k: v for k, v in candidate.items() if k != "backend_variant"})
    for path in tolerance_sites(part, base):
        old = _at(base, path)
        try:
            new = _at(rest, path)
        except (KeyError, TypeError):
            errors.append(f"it lacks the tolerance {'/'.join(path)}")
            continue
        if type(new) not in (int, float) or new < old:
            errors.append(f"its tolerance {'/'.join(path)} is not a number at least as registered")
        _at(rest, path[:-1])[path[-1]] = old
    if rest != base:
        errors.append(
            "a field other than the widened tolerances differs from the registered protocol"
        )
    return errors


def judged_protocol(part, path):
    """(protocol, judged, reason) for a judge's --protocol file.

    A judged run takes the registered protocol itself or a registered backend variant of it;
    any other file is for dry runs only.
    """
    base = registered(part)[1]
    candidate = json.loads(Path(path).read_text())
    if candidate == base:
        return candidate, True, "the registered protocol"
    errors = variant_errors(part, candidate, base)
    if not errors:
        return candidate, True, f"a registered backend variant of {BASES[part]}"
    return candidate, False, "dry run only: " + "; ".join(errors)


# ------------------------------------------------------------------ run


def on_backend(tree, backend):
    """A copy of a predictions tree with every definition's execution backend set to
    `backend` (counted). The registered definitions declare the CPU, and a definition's
    declared backend selects its device (cells.core.devices.execution_device), so an L4 run
    must declare the GPU; nothing else changes."""
    count = 0

    def walk(value):
        nonlocal count
        if isinstance(value, list):
            return [walk(v) for v in value]
        if not isinstance(value, dict):
            return value
        out = {k: walk(v) for k, v in value.items()}
        execution = out.get("execution")
        if isinstance(execution, dict) and "backend" in execution:
            out["execution"] = {**execution, "backend": backend}
            count += 1
        return out

    return walk(tree), count


def with_backend(tree, backend):
    """(tree, record) for a judge's --backend: the tree itself when backend is None (the
    registered path, untouched), else on_backend's copy and {declared, definitions_set}."""
    if backend is None:
        return tree, None
    copy_, count = on_backend(tree, backend)
    return copy_, dict(declared=backend, definitions_set=count)


def predictions_for(part, backend):
    """(predictions, protocol, definitions set) of the part, on `backend` if given."""
    predictions, protocol = registered(part)
    if backend is None:
        return predictions, protocol, 0
    predictions, count = on_backend(predictions, backend)
    return predictions, protocol, count


def run_w1(worlds=None, backend=None):
    from validation.tissue import pump_water_qualification as w1q

    predictions, _, _ = predictions_for("w1", backend)
    out = dict(trajectories={}, stationary={})
    for name, path in w1q.TRAJECTORIES.items():
        if worlds and name not in worlds:
            continue
        raw = w1q.item(predictions, path)["definition"]
        observed, _, _ = w1q.engine_observations(raw, 1e-3)
        out["trajectories"][name] = {
            str(t): {
                k: np.asarray(v, dtype=float).tolist()
                for k, v in w1q.engine_quantities(name, obs, raw).items()
            }
            for t, obs in observed.items()
        }
    if not worlds or "P2_stationary" in worlds:
        for record in w1q.stationary_phase(predictions):
            ok = bool(record["converged"])
            out["stationary"][record["label"]] = dict(
                converged=ok,
                volume_pL=record["volume_pL"] if ok else None,
                membrane_voltage_V=record["state"]["membrane_voltage_V"]["membrane_0"]
                if ok
                else None,
            )
    return out


def w2_items(items):
    """{arm: {branch: judged quantities}} from W2 judge items (judge_arm or w2-judge.json)."""
    out = {}
    for i in items:
        out.setdefault(i["arm"], {})[str(i["branch"])] = dict(
            converged=bool(i["converged"]),
            classification=i.get("classification"),
            **{k: i.get(k) for k, _, _ in W2_QUANTITIES},
        )
    return out


def run_w2(worlds=None, backend=None):
    from validation.tissue import pump_water_kcc_qualification as w2q

    predictions, protocol, _ = predictions_for("w2", backend)
    items = []
    for arm in predictions["arms"]:
        if not worlds or arm in worlds:
            items += w2q.judge_arm(predictions, arm, protocol["stationary"])
    return w2_items(items)


def run_g2(worlds=None, backend=None):
    from validation.tissue import cell_replacement_judge as judge

    predictions, _, _ = predictions_for("g2", backend)
    out = {}
    for name, entry in predictions["cases"].items():
        if not worlds or name in worlds:
            _, result = judge.engine(entry["definition"])
            out[name] = judge.records(result, entry["definition"], 1e-3)
    return out


RUNS = dict(w1=run_w1, w2=run_w2, g2=run_g2)


def load_run(part, path):
    data = json.loads(Path(path).read_text())
    if part == "w2" and "items" in data:  # The qualification's own w2-judge.json.
        return w2_items(data["items"])
    return data["quantities"] if "quantities" in data else data


def world_keys(part, quantities):
    """The worlds a run's quantities hold (W1: its trajectories and stationary labels)."""
    if part == "w1":
        return {("trajectory", k) for k in quantities["trajectories"]} | {
            ("stationary", k) for k in quantities["stationary"]
        }
    return set(quantities)


def merge_runs(part, partial):
    """One run's quantities from its partial files ({world: ...} each, W1 split by kind).

    A run split over GPU gaps with run --worlds is the union of its parts. A world measured
    twice is refused: one run measures each world once.
    """
    merged = dict(trajectories={}, stationary={}) if part == "w1" else {}
    for quantities in partial:
        groups = ("trajectories", "stationary") if part == "w1" else (None,)
        for key in groups:
            into, values = (merged, quantities) if key is None else (merged[key], quantities[key])
            twice = sorted(set(into) & set(values))
            if twice:
                raise ValueError(f"{part}: worlds measured twice in one run: {twice}")
            into.update(values)
    return merged


def load_runs(part, paths):
    """(merged quantities, backend) of one run saved in one file or several (run --worlds).

    Every file of one run must be of this part and from one backend (device and versions).
    """
    datas = [json.loads(Path(p).read_text()) for p in paths]
    for path, data in zip(paths, datas, strict=True):
        if data.get("part", part) != part:
            raise ValueError(f"{path} is a {data['part']} run, not {part}")
    backends = {json.dumps(d.get("backend"), sort_keys=True) for d in datas}
    if len(backends) > 1:
        raise ValueError(f"{part}: the files of one run come from different backends")
    merged = merge_runs(part, [load_run(part, p) for p in paths])
    return merged, datas[0].get("backend")


def same_worlds(part, reference, **runs):
    """Refuse runs (by label: A, B, D or C) that do not cover the reference's worlds exactly."""
    expected = world_keys(part, reference)
    for label, run in runs.items():
        found = world_keys(part, run)
        if found != expected:
            missing, extra = sorted(expected - found), sorted(found - expected)
            raise ValueError(f"{part}: run {label} lacks {missing} and adds {extra}")


# ------------------------------------------------------------------ terms


def _max_abs(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    return float(np.max(np.abs(a - b), initial=0.0))


def _stationary_terms(x, y, quantities):
    entry = dict(changed=x["converged"] != y["converged"])
    if x["converged"] and y["converged"]:
        for key, bound, relative in quantities:
            d = abs(x[key] - y[key])
            entry[bound] = d / abs(x[key]) if relative and x[key] else d
    return entry


def terms_w1(x, y):
    trajectories = {}
    for name, records in x["trajectories"].items():
        worst = trajectories.setdefault(name, {})
        for time, quantities in records.items():
            for key, value in quantities.items():
                d = _max_abs(value, y["trajectories"][name][time][key])
                worst[key] = max(worst.get(key, 0.0), d)
    stationary = {
        label: _stationary_terms(r, y["stationary"][label], W1_STATIONARY)
        for label, r in x["stationary"].items()
    }
    return dict(trajectories=trajectories, stationary=stationary)


def terms_w2(x, y):
    out = {}
    for arm, branches in x.items():
        for branch, r in branches.items():
            s = y[arm][branch]
            entry = _stationary_terms(r, s, W2_QUANTITIES)
            entry["changed"] |= r["classification"] != s["classification"]
            out[f"{arm}/{branch}"] = entry
    return out


def terms_g2(x, y):
    from validation.tissue import cell_replacement_judge as judge

    return {
        name: {k: judge.worst(records, y[name], k) for k in G2_KEYS} for name, records in x.items()
    }


TERMS = dict(w1=terms_w1, w2=terms_w2, g2=terms_g2)


def worst(trees):
    """The elementwise worst of term trees of one part: the largest number, any change."""
    first = trees[0]
    if isinstance(first, dict):
        keys = list(first)
        for tree in trees[1:]:
            keys += [k for k in tree if k not in keys]
        return {k: worst([t[k] for t in trees if k in t]) for k in keys}
    if isinstance(first, bool):
        return any(trees)
    return max(trees)


def measured(part, reference, *runs):
    """The terms of the three L4 repeats A, B and D (REPEATS), in that order.

    backend: the largest |reference - X| over the repeats; run_to_run: the largest
    difference between two of them; with each repeat's backend term (backend_each) and each
    pair's run-to-run term (run_to_run_pairs), so a variant records all three.
    """
    if len(runs) != len(REPEATS):
        raise ValueError(
            f"{part}: the terms take {len(REPEATS)} L4 repeats ({', '.join(REPEATS)}), "
            f"not {len(runs)}"
        )
    each = {x: TERMS[part](reference, run) for x, run in zip(REPEATS, runs, strict=True)}
    pairs = {
        f"{x}-{y}": TERMS[part](runs[i], runs[j])
        for (i, x), (j, y) in itertools.combinations(enumerate(REPEATS), 2)
    }
    return dict(
        backend=worst(list(each.values())),
        run_to_run=worst(list(pairs.values())),
        backend_each=each,
        run_to_run_pairs=pairs,
    )


def ratios(deviation, run_to_run, path=()):
    """[(path, |A - C|, run-to-run, ratio or None)] over every numeric quantity; the ratio
    is None where the repeats agreed exactly but C differs (run-to-run 0, |A - C| > 0)."""
    if isinstance(deviation, dict):
        rows = []
        for key, value in deviation.items():
            inner = run_to_run.get(key, {}) if isinstance(run_to_run, dict) else {}
            rows += ratios(value, inner, (*path, key))
        return rows
    if isinstance(deviation, bool) or deviation is None:
        return []
    spread = run_to_run if isinstance(run_to_run, int | float) else 0.0
    ratio = deviation / spread if spread > 0 else (0.0 if deviation == 0 else None)
    return [("/".join(path), deviation, spread, ratio)]


def changes(tree, path=()):
    """Paths of the changed convergences or classifications in a term tree."""
    if isinstance(tree, dict):
        return [p for k, v in tree.items() for p in changes(v, (*path, k))]
    return ["/".join(path[:-1])] if path and path[-1] == "changed" and tree is True else []


def deviation(part, a, c, run_to_run):
    """|A - C| per quantity (the part's own measure) over the run-to-run term."""
    terms = TERMS[part](a, c)
    rows = ratios(terms, run_to_run)
    finite = [r for _, _, _, r in rows if r is not None]
    return dict(
        deviation=terms,
        rows=[dict(item=p, deviation=d, run_to_run=s, ratio=r) for p, d, s, r in rows],
        summary=dict(
            quantities=len(rows),
            largest_ratio=max(finite, default=0.0),
            above_1=sum(r > 1 for r in finite),
            above_3=sum(r > 3 for r in finite),
            unbounded=[p for p, _, _, r in rows if r is None],
            changed=changes(terms),
        ),
    )


# ------------------------------------------------------------------ variant


def widen(tolerance, backend, run_to_run, *, summed):
    """(new tolerance, stop): never below the registered tolerance (module docstring)."""
    added = backend + run_to_run
    base = tolerance / MARGIN if summed else 0.0
    new = tolerance if added == 0 else max(tolerance, up1(MARGIN * (base + added)))
    return new, backend > (base if summed else tolerance)


def _row(rows, name, tolerance, backend, run_to_run, *, summed, each, pairs):
    """One tolerance's report row, with every repeat's backend term and every pair's
    run-to-run term beside the largest of each (the ones the rule uses)."""
    new, stop = widen(tolerance, backend, run_to_run, summed=summed)
    rows.append(
        dict(
            item=name,
            registered=tolerance,
            registered_sum=tolerance / MARGIN if summed else None,
            backend=backend,
            run_to_run=run_to_run,
            backend_each=each,
            run_to_run_pairs=pairs,
            tolerance=new,
            widening=new / tolerance,
            stop=stop,
        )
    )
    return new


def _largest(entries, bound):
    """The largest value of one bound over worlds (0 where no world converged both)."""
    return max((e.get(bound, 0.0) for e in entries.values()), default=0.0)


def _fixed(rows, protocol_bounds, families, prefix):
    """Fixed bounds (W1 stationary, W2): the maxima over worlds of each term.

    families: backend and run_to_run (the worst over repeats and pairs, world by world),
    and backend_each and run_to_run_pairs ({label: that repeat's or pair's worlds}).
    """
    changed = [k for k, v in families["backend"].items() if v["changed"]]
    changed += [k for k, v in families["run_to_run"].items() if v["changed"]]
    bounds = {b for entry in families["backend"].values() for b in entry if b != "changed"}
    for bound in sorted(bounds):
        protocol_bounds[bound] = _row(
            rows,
            f"{prefix}{bound}",
            protocol_bounds[bound],
            _largest(families["backend"], bound),
            _largest(families["run_to_run"], bound),
            summed=False,
            each={x: _largest(e, bound) for x, e in families["backend_each"].items()},
            pairs={x: _largest(e, bound) for x, e in families["run_to_run_pairs"].items()},
        )
    return changed


def variant(part, protocol, terms):
    """The variant protocol (the part's own format) and its report rows.

    terms: measured()'s, or a terms file's (which also names the repeats' files). Terms of
    fewer than the three repeats are refused.
    """
    each, pairs = terms.get("backend_each", {}), terms.get("run_to_run_pairs", {})
    if sorted(each) != sorted(REPEATS) or len(pairs) != math.comb(len(REPEATS), 2):
        raise ValueError(
            f"{part}: the terms do not hold the {len(REPEATS)} repeats {', '.join(REPEATS)} "
            "(terms from one pair are not accepted)"
        )
    out, rows, changed = copy.deepcopy(protocol), [], []
    b, r = terms["backend"], terms["run_to_run"]

    def at(trees, *path):
        return {label: _at(tree, path) for label, tree in trees.items()}

    if part == "w1":
        for name, quantities in b["trajectories"].items():
            for key, tolerance in protocol["tolerances"][name].items():
                out["tolerances"][name][key] = _row(
                    rows,
                    f"{name}/{key}",
                    tolerance,
                    quantities[key],
                    r["trajectories"][name][key],
                    summed=True,
                    each=at(each, "trajectories", name, key),
                    pairs=at(pairs, "trajectories", name, key),
                )
        if b["stationary"]:
            families = dict(
                backend=b["stationary"],
                run_to_run=r["stationary"],
                backend_each=at(each, "stationary"),
                run_to_run_pairs=at(pairs, "stationary"),
            )
            changed = _fixed(rows, out["stationary"], families, "P2_stationary/")
    elif part == "w2":
        families = dict(backend=b, run_to_run=r, backend_each=each, run_to_run_pairs=pairs)
        changed = _fixed(rows, out["stationary"], families, "")
    else:
        pinned = out["pinned_tolerances"]["cases"]
        for name, by_key in b.items():
            entries = [(f"q3_{k}", k) for k in G2_KEYS]
            if "q4_membrane_voltage_V" in pinned[name]:
                entries.append(("q4_membrane_voltage_V", "membrane_voltage_V"))
            for entry, key in entries:
                pinned[name][entry]["tolerance"] = _row(
                    rows,
                    f"{name}/{entry}",
                    protocol["pinned_tolerances"]["cases"][name][entry]["tolerance"],
                    by_key[key],
                    r[name][key],
                    summed=True,
                    each=at(each, name, key),
                    pairs=at(pairs, name, key),
                )
    stop = changed + [row["item"] for row in rows if row["stop"]]
    # The protocol's own fields (its status included) are kept; the variant's are here.
    out["backend_variant"] = dict(
        status=STATUS,
        base=BASES[part],
        rule="max(registered, up1(3 x (registered sum + backend + run-to-run))); fixed "
        "tolerances max(registered, up1(3 x (backend + run-to-run))); registered kept "
        "exactly when nothing is added; backend: the largest |reference - X| over the L4 "
        "repeats A, B and D; run-to-run: the largest difference between two of them",
        repeats=dict(
            labels=list(REPEATS),
            reference=terms.get("reference"),
            runs=dict(zip(REPEATS, terms["runs"], strict=True)) if "runs" in terms else None,
            backends=dict(zip(REPEATS, terms["backends"], strict=True))
            if "backends" in terms
            else None,
        ),
        stop=bool(stop),
        stop_items=stop,
        rows=rows,
    )
    return out


# ------------------------------------------------------------------ main


def backend_info():
    import jax

    return dict(
        backend=jax.default_backend(),
        devices=[str(d) for d in jax.devices()],
        jax=jax.__version__,
        python=platform.python_version(),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="action", required=True)
    one = sub.add_parser("run")
    one.add_argument("--part", choices=tuple(RUNS), required=True)
    one.add_argument("--output", type=Path, required=True)
    one.add_argument("--worlds", type=lambda s: s.split(","), default=None)
    one.add_argument(
        "--backend",
        choices=("cpu", "gpu"),
        default=None,
        help="set every definition's execution backend (an L4 run: gpu; default as registered)",
    )
    files = lambda s: [Path(x) for x in s.split(",")]  # noqa: E731 (one run, comma-separated)
    two = sub.add_parser("terms")
    two.add_argument("--part", choices=tuple(RUNS), required=True)
    two.add_argument("--reference", type=files, required=True)
    two.add_argument("--runs", type=files, nargs=len(REPEATS), required=True, help="A B D")
    two.add_argument("--output", type=Path, required=True)
    three = sub.add_parser("variant")
    three.add_argument("--part", choices=tuple(RUNS), required=True)
    three.add_argument("--terms", type=Path, required=True)
    three.add_argument("--output", type=Path, required=True)
    four = sub.add_parser("deviation")
    four.add_argument("--part", choices=tuple(RUNS), required=True)
    four.add_argument("--terms", type=Path, required=True)
    four.add_argument("--judged", type=files, required=True, help="the judged run C")
    four.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.action == "run":
        import jax

        jax.config.update("jax_enable_x64", True)
        started = perf_counter()
        quantities = RUNS[args.part](args.worlds, args.backend)
        info = backend_info() | dict(
            declared=args.backend or "as registered",
            definitions_set=predictions_for(args.part, args.backend)[2],
        )
        record = dict(
            part=args.part,
            worlds=args.worlds,
            backend=info,
            seconds=perf_counter() - started,
            quantities=quantities,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(record, indent=1) + "\n")
    elif args.action == "terms":
        reference, _ = load_runs(args.part, args.reference)
        loaded = [load_runs(args.part, paths) for paths in args.runs]
        runs = [quantities for quantities, _ in loaded]
        same_worlds(args.part, reference, **dict(zip(REPEATS, runs, strict=True)))
        record = dict(
            part=args.part,
            reference=[str(p) for p in args.reference],
            labels=list(REPEATS),
            runs=[[str(p) for p in paths] for paths in args.runs],
            backends=[backend for _, backend in loaded],
            **measured(args.part, reference, *runs),
        )
        args.output.write_text(json.dumps(record, indent=1) + "\n")
    elif args.action == "deviation":
        terms = json.loads(args.terms.read_text())
        a, _ = load_runs(args.part, terms["runs"][0])
        c, backend = load_runs(args.part, args.judged)
        same_worlds(args.part, a, C=c)
        record = dict(
            part=args.part,
            terms=str(args.terms),
            a=terms["runs"][0],
            judged=[str(p) for p in args.judged],
            backend=backend,
            **deviation(args.part, a, c, terms["run_to_run"]),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(record, indent=1) + "\n")
        s = record["summary"]
        print(args.part, s["quantities"], "quantities; largest |A - C| / run-to-run",
              s["largest_ratio"], "; above 3:", s["above_3"], "; unbounded:",
              len(s["unbounded"]), "; changed:", s["changed"])  # fmt: skip
    else:
        terms = json.loads(args.terms.read_text())
        out = variant(args.part, registered(args.part)[1], terms)
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "protocol.json").write_text(json.dumps(out, indent=1) + "\n")
        report = dict(part=args.part, terms=str(args.terms), **out["backend_variant"])
        (args.output / "variant.json").write_text(json.dumps(report, indent=1) + "\n")
        widest = max((r["widening"] for r in report["rows"]), default=1.0)
        print(args.part, "stop" if report["stop"] else "no stop", len(report["rows"]), "rows;",
              "widest widening", widest)  # fmt: skip


if __name__ == "__main__":
    main()
