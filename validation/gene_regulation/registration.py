"""FR-25's registered tolerance (D268): the engine's comparison with G2's code-blind references
judged pass, fail or inconclusive, against tolerances set from the engine's own step error alone.
G6's registration is not part of it.

**What is not blind.** The development gaps (runs at 872a6a8e, dt 0.5 and 1.0 s) were read before
this rule was written. The rule's soundness rests on its tolerance coming from the engine's step
error alone, never from a gap to G2. The judged runs are fresh, at G4's landed head, which differs
from those runs only in its summation order, at rounding level.

**The two tags.**
1. The rule (RULE, written by `rule`) is tagged before the fresh runs launch.
2. The table (`table`, built from the three engine runs with no reference read) is tagged before
   anything is compared with G2.

**The rule**, per readout and world, from three engine runs at steps 4h, 2h and h (2, 1 and 0.5 s):
- **The estimate:** est = max_t |y(2h) - y(h)| / (2^p - 1), with p declared per world kind and
  readout class (P_DECLARED, each with the scheme's reason).
- **The tolerance:** max(F est, FLOOR scale), with scale = max_t |y(h)| and F = 3. F is Roache's
  grid-convergence-index factor of safety for an assumed order with two grids (ROACHE).
- **At the floor:** where the tolerance is the floor, it is judged against the floor and the order
  check is skipped. J-bar's differences are rounding noise, so its order means nothing.
- **Elsewhere, the order check:** the observed order q = log2(max|y(4h) - y(2h)| /
  max|y(2h) - y(h)|) must lie in [p - 0.5, 3.5]. Otherwise the world is inconclusive.
  - The lower bound keeps the estimate from being too small.
  - The upper bound, SSPRK(3,3)'s order plus the same margin, caps the looseness at a faster order.
    That looseness is (2^q - 1)/(2^p - 1) times the step error, at most about 10 times it.
  - No readout has a reason in the scheme to converge above third order. A higher q would show
    cancellation or a step outside the asymptotic range, which the retry can resolve.
- **Judged at step h:** a readout passes where max |y(h) - G2| over G2's required times is at most
  its tolerance.
- **Reported, not judged:** per readout, its observed order q and its effective factor, 3 (2^q -
  1)/(2^p - 1): the tolerance against the step error at the observed order.
- **Each world** is inconclusive if any readout's order falls outside its window; failed if any
  readout fails; passed if every readout passes and every required time is matched.
- **FR-25 passes** only when every world passes. An inconclusive world gets one finer triple, steps
  1, 0.5 and 0.25 s, under the same rule, judged at 0.25 s, and nothing else (RETRY).

**What a pass covers.** G2's trajectories at both test instances, at dt = 0.5 s, within 3 times
the step-error estimate at the scheme's formal order. Each move's dG and A1's u are not exported,
and the corners and interior points stay with G6.

Run:
- `python -m validation.gene_regulation.registration rule --out FILE`
- `python -m validation.gene_regulation.registration table RUN_4H RUN_2H RUN_H --out FILE`
- `python -m validation.gene_regulation.registration judge TABLE RUN_H --out FILE`
"""

import argparse
import json
import math
from pathlib import Path

from validation.gene_regulation import compare

F = 3.0
FLOOR = 1e-9  # Of each readout's scale: the references' own resolution (their check: 4.1e-10).
WINDOW = 0.5  # q >= p - WINDOW.
ORDER_CAP = 3.5  # q <= ORDER_CAP: SSPRK(3,3)'s order plus the margin, for every judged readout.
STEPS = (2.0, 1.0, 0.5)
RETRY = dict(steps=(1.0, 0.5, 0.25), once=True, judged_step=0.25, worlds="inconclusive only")
SETS = ("test instance", "Spirin's E_pep")
ROACHE = (
    "Roache PJ (1994) Perspective: a method for uniform reporting of grid refinement studies. "
    "J. Fluids Eng. 116:405-413: the grid-convergence index GCI = Fs |e|/(r^p - 1), with factor "
    "of safety Fs = 3 for two grids at an assumed order and 1.25 for three or more grids at an "
    "observed order. Checked against secondary sources (NASA NPARC's grid-convergence tutorial; "
    "Phillips "
    "and Roy 2014, J. Fluids Eng.); the 1994 paper itself was not reached"
)
CLASSES = {  # readout class: the prefixes it holds
    "amount": ("n_", "F_"),
    "occupancy": ("C_", "E_", "W_"),
    "extent": ("int_",),
    "heat": ("H_",),
    "free_energy": ("G_minus_G0",),
    "release_rate": ("J_bar_",),
}
SSPRK = "SSPRK(3,3) on the operator's own variables, third order; the inner step leaves them"
SPLIT = (
    "the split step: the regulator's turnover and the coupling's routed factor act in their own "
    "parts around the operator, Strang's second order"
)
AVF = (
    "each route's heat is its share of the exact total by divided-difference potentials (the "
    "average-vector-field split), a second-order discrete gradient. The development runs showed "
    "it: pol T=100's H_rc at order 1.98 (2.5e-7 at dt 1.0, 6.3e-8 at dt 0.5), the recharging route "
    "near its equilibrium"
)
P_DECLARED = {  # (world kind, class): (p, the scheme's reason)
    **{("A1-M", c): (3, SSPRK) for c in ("amount", "occupancy", "extent", "release_rate")},
    ("A1-M", "free_energy"): (3, "G is a function of the state, which is third order: " + SSPRK),
    ("A1-M", "heat"): (2, AVF),
    **{("A1", c): (2, SPLIT) for c in CLASSES},
}


def kind(world):
    return "A1" if world == "A1" else "A1-M"


def klass(name):
    for c, prefixes in CLASSES.items():
        if name.startswith(prefixes):
            return c
    raise ValueError(f"readout {name} is in no class")


def rule():
    """The rule as data, the file to tag before the fresh runs (module docstring)."""
    return dict(
        kind="cells.gene_regulation.fr25_rule@1",
        steps_s=list(STEPS),
        judged_step_s=STEPS[-1],
        sets=list(SETS),
        worlds="the sixteen of worlds.names()",
        classes={c: list(v) for c, v in CLASSES.items()},
        order_declared=[
            dict(world_kind=k, readout_class=c, p=p, reason=r)
            for (k, c), (p, r) in sorted(P_DECLARED.items())
        ],  # fmt: skip
        factor_of_safety=F,
        factor_source=ROACHE,
        floor_of_scale=FLOOR,
        order_window=dict(low="p - 0.5", high=ORDER_CAP),
        retry={**RETRY, "steps": list(RETRY["steps"])},
        not_blind=(
            "the development gaps (872a6a8e runs, dt 0.5 and 1.0 s) were read before this rule; "
            "its soundness rests on its tolerance coming from step error alone; the judged runs "
            "are fresh, at G4's landed head, which differs from those runs only in its summation "
            "order"
        ),
        orders_seen=(
            "the development orders (between the dt 1.0 and 0.5 s gaps to G2) were seen before the "
            "window was set to [p - 0.5, 3.5]: of 696 readouts above the floor, the largest order "
            "is 3.38, and four sit below p - 0.5, pol T=100's F_pol and E_tx at 2.466 at both "
            "test instances. Under this rule, such a world is inconclusive and takes the retry"
        ),
    )


def _series(record):
    return {round(float(t), 9): i for i, t in enumerate(record["t"])}, record["readouts"]


def _difference(a, b, name):
    """max |a - b| of a readout over the two runs' common outputs (J-bar: its one value)."""
    (ia, ra), (ib, rb) = _series(a), _series(b)
    if name.startswith("J_bar"):
        return abs(ra[name][0] - rb[name][0])
    common = sorted(set(ia) & set(ib))
    if not common:
        raise ValueError(f"{name}: the runs share no output")
    return max(abs(ra[name][ia[t]] - rb[name][ib[t]]) for t in common)


def table(coarse, middle, fine):
    """The table of one triple of engine runs, each {(set, world): record}: per world, its status
    and each readout's estimate, order and tolerance in its own units (module docstring)."""
    out = {}
    for key, f in sorted(fine.items()):
        m, c = middle[key], coarse[key]
        world = f["world"]
        readouts, statuses = {}, []
        for name, values in f["readouts"].items():
            try:
                cls = klass(name)
            except ValueError:
                continue  # Not a readout G2 judges (route heats, the routes' sums, H_total).
            if name.startswith(("H_route_", "H_routes_sum", "H_total")):
                continue
            p, _ = P_DECLARED[(kind(world), cls)]
            d_fine, d_coarse = _difference(m, f, name), _difference(c, m, name)
            scale = max(abs(v) for v in values) or 1.0
            est = d_fine / (2**p - 1)
            tolerance = max(F * est, FLOOR * scale)
            at_floor = F * est <= FLOOR * scale
            order = math.log2(d_coarse / d_fine) if d_fine > 0 and d_coarse > 0 else None
            in_window = at_floor or (order is not None and p - WINDOW <= order <= ORDER_CAP)
            readouts[name] = dict(readout_class=cls, p=p, estimate=est, tolerance=tolerance,
                                  scale=scale, at_floor=at_floor, order=order,
                                  in_window=in_window)  # fmt: skip
            statuses.append(in_window)
        out[f"{key[0]} | {world}"] = dict(
            set=key[0],
            world=world,
            status="ready" if all(statuses) else "inconclusive",
            outside_window=sorted(n for n, r in readouts.items() if not r["in_window"]),
            readouts=readouts,
        )
    return dict(kind="cells.gene_regulation.fr25_table@1", rule=rule(), worlds=out)


def effective_factor(readout):
    """F (2^q - 1)/(2^p - 1): the tolerance against the step error at the observed order q; None
    where q is unknown or the readout is at the floor (reported, not judged)."""
    q = readout["order"]
    if q is None or readout["at_floor"]:
        return None
    return F * (2**q - 1) / (2 ** readout["p"] - 1)


def judge(table_record, fine, refs=None):
    """Each world's verdict against the table (module docstring), and FR-25's."""
    refs = compare.References() if refs is None else refs
    verdicts = {}
    for label, entry in table_record["worlds"].items():
        key = (entry["set"], entry["world"])
        record = fine[key]
        result = compare.compare_record(refs, record)
        if result["compared"] != "trajectory":
            raise ValueError(f"{label}: the registration judges G2's trajectories only")
        failed = sorted(
            n for n, r in entry["readouts"].items()
            if n in result["absolute_gaps"] and result["absolute_gaps"][n] > r["tolerance"]
        )  # fmt: skip
        unjudged = sorted(n for n in result["absolute_gaps"] if n not in entry["readouts"])
        if unjudged:
            raise ValueError(f"{label}: readouts {unjudged[:3]} have no registered tolerance")
        status = "inconclusive" if entry["status"] == "inconclusive" else (
            "failed" if failed else "passed")  # fmt: skip
        verdicts[label] = dict(
            status=status,
            failed=failed,
            outside_window=entry["outside_window"],
            expected_times=result["expected_times"],
            matched_times=result["matched_times"],
            margins={
                n: result["absolute_gaps"][n] / entry["readouts"][n]["tolerance"]
                for n in result["absolute_gaps"]
            },  # fmt: skip
            observed_orders={n: entry["readouts"][n]["order"] for n in result["absolute_gaps"]},
            effective_factors={  # Reported, not judged: 3 (2^q - 1)/(2^p - 1).
                n: effective_factor(entry["readouts"][n]) for n in result["absolute_gaps"]
            },
        )
    statuses = [v["status"] for v in verdicts.values()]
    overall = "passed" if all(s == "passed" for s in statuses) else (
        "failed" if "failed" in statuses else "inconclusive")  # fmt: skip
    return dict(kind="cells.gene_regulation.fr25_verdict@1", verdict=overall, worlds=verdicts)


def runs(directory):
    """{(set, world): record} of an engine_run.py output directory."""
    out = {}
    for path in sorted(Path(directory).glob("*/*.json")):
        record = json.loads(path.read_text())
        out[(record["set"], record["world"])] = record
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("rule").add_argument("--out", required=True)
    t = sub.add_parser("table")
    t.add_argument("coarse")
    t.add_argument("middle")
    t.add_argument("fine")
    t.add_argument("--out", required=True)
    j = sub.add_parser("judge")
    j.add_argument("table")
    j.add_argument("fine")
    j.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.command == "rule":
        out = rule()
    elif args.command == "table":
        out = table(runs(args.coarse), runs(args.middle), runs(args.fine))
    else:
        out = judge(json.loads(Path(args.table).read_text()), runs(args.fine))
    Path(args.out).write_text(json.dumps(out, indent=1) + "\n")
    print(out.get("verdict", out["kind"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
