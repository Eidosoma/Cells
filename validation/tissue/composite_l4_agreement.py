"""L4 agreement of the composite on W1, W2 and G2-Q1 (docs/PUMP_COMPOSITE_V2_DESIGN.md §5).

A backend variant of each qualification's own registered protocol, by the method of
validation/betse/backend_variant.py. That module's tolerance helper is not imported here:
it sits beside BETSE-side modules (AGENTS.md), so up1 is restated below. The variant keeps
each protocol's worlds, quantities, references and judge. It adds measured backend terms:

* backend |CPU reference - L4 run A| and run-to-run |A - B|, per world and quantity. Each
  part uses its own difference measure: W1 absolute, max over records; W2 volume and route
  cycles relative and voltage absolute, per arm and branch; G2-Q1 the judge's own
  worst-difference function;
* a tolerance that is 3 x a sum of terms (W1's trajectories, G2-Q1) becomes
  max(registered, up1(3 x (registered / 3 + backend + run-to-run))). A fixed tolerance
  (W1's stationary bounds, W2) becomes max(registered, up1(3 x (backend + run-to-run))).
  With no added term the registered value is kept exactly: these protocols' tolerances
  are not rounded, and up1 alone would loosen them;
* stop rule, before the judged run C: stop if a backend term exceeds the registered sum
  (or a fixed tolerance), or if a W1 or W2 convergence or a W2 classification changed.
  Diagnose instead; do not register;
* verdict: each qualification's own driver runs on C with the variant protocol written
  here (its --protocol). C against the CPU reference is reported, not judged.

Actions:
  run --part {w1,w2,g2} --output FILE [--worlds NAME,...]
      the part's judged quantities (raw engine values) with the backend used
  terms --part P --reference CPU --runs A B --output FILE
      measured terms; W2 also reads the qualification's own w2-judge.json
  variant --part P --terms FILE --output DIR
      variant.json (tolerances, stop rule, report rows) and protocol.json
Everything written is PROPOSED until the lead registers it.
"""

import argparse
import copy
import json
import math
import platform
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if __name__ == "__main__":
    for entry in (ROOT / "src", ROOT):
        if str(entry) not in sys.path:
            sys.path.insert(0, str(entry))

MARGIN = 3.0
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


def up1(x):
    """Round up to one significant figure (the backend-variant method's rule)."""
    if x <= 0:
        return 0.0
    e = math.floor(math.log10(x))
    return float(f"{math.ceil(round(x / 10**e, 9)) * 10**e:.1e}")


def registered(part):
    """(predictions, protocol) of the part at this revision."""
    return tuple(json.loads((TISSUE / name).read_text()) for name in FILES[part])


# ------------------------------------------------------------------ run


def run_w1(worlds=None):
    from validation.tissue import pump_water_qualification as w1q

    predictions, _ = registered("w1")
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


def run_w2(worlds=None):
    from validation.tissue import pump_water_kcc_qualification as w2q

    predictions, protocol = registered("w2")
    items = []
    for arm in predictions["arms"]:
        if not worlds or arm in worlds:
            items += w2q.judge_arm(predictions, arm, protocol["stationary"])
    return w2_items(items)


def run_g2(worlds=None):
    from validation.tissue import cell_replacement_judge as judge

    predictions, _ = registered("g2")
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


def measured(part, reference, a, b):
    """The backend term (reference against A) and the run-to-run term (A against B)."""
    return dict(backend=TERMS[part](reference, a), run_to_run=TERMS[part](a, b))


# ------------------------------------------------------------------ variant


def widen(tolerance, backend, run_to_run, *, summed):
    """(new tolerance, stop): never below the registered tolerance (module docstring)."""
    added = backend + run_to_run
    base = tolerance / MARGIN if summed else 0.0
    new = tolerance if added == 0 else max(tolerance, up1(MARGIN * (base + added)))
    return new, backend > (base if summed else tolerance)


def _row(rows, name, tolerance, backend, run_to_run, *, summed):
    new, stop = widen(tolerance, backend, run_to_run, summed=summed)
    rows.append(
        dict(
            item=name,
            registered=tolerance,
            registered_sum=tolerance / MARGIN if summed else None,
            backend=backend,
            run_to_run=run_to_run,
            tolerance=new,
            widening=new / tolerance,
            stop=stop,
        )
    )
    return new


def _fixed(rows, protocol_bounds, families, prefix):
    """Fixed bounds (W1 stationary, W2): the maxima over worlds of each term."""
    changed = [k for k, v in families["backend"].items() if v["changed"]]
    changed += [k for k, v in families["run_to_run"].items() if v["changed"]]
    bounds = {b for entry in families["backend"].values() for b in entry if b != "changed"}
    for bound in sorted(bounds):
        backend = max(e.get(bound, 0.0) for e in families["backend"].values())
        again = max(e.get(bound, 0.0) for e in families["run_to_run"].values())
        protocol_bounds[bound] = _row(
            rows, f"{prefix}{bound}", protocol_bounds[bound], backend, again, summed=False
        )
    return changed


def variant(part, protocol, terms):
    """The variant protocol (the part's own format) and its report rows."""
    out, rows, changed = copy.deepcopy(protocol), [], []
    b, r = terms["backend"], terms["run_to_run"]
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
                )
        if b["stationary"]:
            families = dict(backend=b["stationary"], run_to_run=r["stationary"])
            changed = _fixed(rows, out["stationary"], families, "P2_stationary/")
    elif part == "w2":
        changed = _fixed(rows, out["stationary"], dict(backend=b, run_to_run=r), "")
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
                )
    stop = changed + [row["item"] for row in rows if row["stop"]]
    # The protocol's own fields (its status included) are kept; the variant's are here.
    out["backend_variant"] = dict(
        status=STATUS,
        rule="max(registered, up1(3 x (registered sum + backend + run-to-run))); fixed "
        "tolerances max(registered, up1(3 x (backend + run-to-run))); registered kept "
        "exactly when nothing is added",
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
    two = sub.add_parser("terms")
    two.add_argument("--part", choices=tuple(RUNS), required=True)
    two.add_argument("--reference", type=Path, required=True)
    two.add_argument("--runs", type=Path, nargs=2, required=True)
    two.add_argument("--output", type=Path, required=True)
    three = sub.add_parser("variant")
    three.add_argument("--part", choices=tuple(RUNS), required=True)
    three.add_argument("--terms", type=Path, required=True)
    three.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.action == "run":
        import jax

        jax.config.update("jax_enable_x64", True)
        quantities = RUNS[args.part](args.worlds)
        record = dict(
            part=args.part, worlds=args.worlds, backend=backend_info(), quantities=quantities
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(record, indent=1) + "\n")
    elif args.action == "terms":
        reference, a, b = (load_run(args.part, p) for p in (args.reference, *args.runs))
        record = dict(
            part=args.part,
            reference=str(args.reference),
            runs=[str(p) for p in args.runs],
            **measured(args.part, reference, a, b),
        )
        args.output.write_text(json.dumps(record, indent=1) + "\n")
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
