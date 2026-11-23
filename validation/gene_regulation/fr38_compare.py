"""FR-38's comparison reader and judge (rule erratum 1, D308): the engine's runs of the rule's
worlds against FR-38's code-blind references (tag gr-refs-fr38-2026-11-22), read from their
interface alone, judged by validation/gene_regulation/fr38_rule.json as fr38_rule_erratum_1.json
amends it. The rule named this reader at its tag, and none existed (D308).

**How it was written.** The comparison's judge wrote it from the interface files' keys and array
shapes alone (`structure` prints them, never a value), not from the references' values, code,
README or tests. G4/FR-25's compare.py reads only G2's files, and registration.py's classes,
orders and scales are FR-25's, so neither serves this rule.

**The interface:** references/interface/release_r1.json (R1's ten cases, their limit checks and
cohorts), release_r2.json (R2's two runs), and release_inputs.json (the declared inputs), whose
bytes are the references' tag's.

**The name mapping** (`mapping`, engine export from reference quantity), per world:
- the readouts by their own names, except the release's: hold_tx gives H_tx_release, int_Qf_d1 and
  int_Qf_s1 the releases int_Q_tx_release_durable and _short_lived, and H_rel_d and H_rel_s the
  heats H_rel_tx_release_durable and _short_lived;
- survivors_<row>, the rule's survivors (the fate row minus the matched blank's): limit_checks'
  n_F_minus_blank of its fate;
- route 1, R1L's label_<row>_cohort: cohorts' route1_blank at p = 0.75, the references' route 1
  with the matched blank subtracted (their finding R-F1), since the shares carry no trace;
- route 2 (route2_<fate>), cohort.known_rate at each fate's gross k on the unlabelled run's
  releases: R1's cohorts' route2_exact at p = 0.75, and R2's cohort_route2.

Every other published quantity is listed as not compared, with its reason.

**Cases are matched by their declarations, never by position:**
- p, the machine option and H0, with a blank at H0 = 0;
- each declaration, with tau, both fates' rates and the window, is checked against the engine
  run's own definition.

R1L is R1 at p = 0.75 with labels, which change no physical readout, so it is compared with that
case.

**Units.**
- The readouts are G2's units (fmol, pJ), as the engine's are.
- limit_checks' and cohorts' amounts are copies, as the interface's keys state (H0_copies,
  absolute_distance_copies, R2's copies). Each is converted to fmol by COPY_FMOL.
- Before any comparison, `check_units` checks both units inside the interface alone:
  - limit_checks' fate rows are the readouts' in copies;
  - each cohort at its window's end lies between the window's releases times e^(-k t2) and the
    releases.

**The table** (`table`) is built from the engine's three runs at steps 4h, 2h and h alone, before
any reference value is read. Per readout and run it gives the rule's estimate, tolerance, floor,
order and window, at the compared times (R1's five, R2's 361, the cohort's two sample times). Route
2's tolerance is set per sample time from cohort.known_rate_error. The route agreement is reported
on each labelled run (erratum 1).

**The judge** (`judge`) reads the references through this reader, per the rule and erratum 1.
- A readout passes where its largest gap over the compared times is within its tolerance. At zero
  scale it passes only where the gap is exactly 0.
- The zero-rate fate's survivors (survivors_R at p = 0, survivors_R_s at p = 1) are judged as zero
  (erratum 1's ruling).
  - No molecule is released into that fate, so the row minus its blank is the row's own coupling
    through M, not a survivor.
  - The engine's |y(h)| must lie within floor_of_scale times the row's own magnitude, max |n_F| of
    the judged run at the compared times, and the reference must be 0 at every compared time.
  - The order check is skipped, as at the floor.
- Within a run, an out-of-window order makes the run inconclusive.
- Per world and overall, any failed run makes the verdict failed; else any inconclusive run makes
  it inconclusive; else it is passed.

Run (PYTHONPATH=src:. JAX_ENABLE_X64=1):
- python -m validation.gene_regulation.fr38_compare structure
- python -m validation.gene_regulation.fr38_compare mapping
- python -m validation.gene_regulation.fr38_compare table --r1 D4H D2H DH --r2 D4H D2H DH --out F
- the retry: table --retry --runs NAME ... --r1 D4H D2H DH [--r2 ...] --out F
- python -m validation.gene_regulation.fr38_compare judge TABLE [--retry RETRY_TABLE] --out F
"""

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

from cells.operators.templated_polymerisation import COPY_FMOL
from validation.gene_regulation import cohort, engine_run, release_check, worlds

HERE = Path(__file__).resolve().parent
RULE = HERE / "fr38_rule.json"
ERRATUM = HERE / "fr38_rule_erratum_1.json"
INTERFACE = HERE / "references" / "interface"
FILES = ("release_inputs.json", "release_r1.json", "release_r2.json")
REFERENCES_TAG = "gr-refs-fr38-2026-11-22"
SET = "test instance"
MATCH = 1e-12  # Relative: a case's declared inputs against the engine run's own definition.
UNITS = 1e-6  # Relative slack of the interface's own unit checks, whose units differ by 6e8.
TIME_TOLERANCE_S = 1e-9  # A compared time and an output match within it (no rounded key).
R2_TIMES = tuple(60.0 * k for k in range(361))  # The rule's "A1's outputs, every 60 s to 21,600 s".
RID = worlds.RELEASE
FATES = {"durable": ("R", "d"), "short_lived": ("R_s", "s")}  # Fate: (its row, the letter).
RENAMED = {  # The references' names for the release's own readouts: theirs, the engine's.
    "hold_tx": f"H_{RID}",
    "int_Qf_d1": f"int_Q_{RID}_durable",
    "int_Qf_s1": f"int_Q_{RID}_short_lived",
    "H_rel_d": f"H_rel_{RID}_durable",
    "H_rel_s": f"H_rel_{RID}_short_lived",
}
TRACKERS = {  # The references' tracker series (the lead, from their definitions; no value read).
    "CO": "route 2's exact cohort, compared at the sample times as cohorts' route2_exact (R1) and "
    "cohort_route2 (R2)",
    "LR": "the released molecules still present, equal by construction to limit_checks' "
    "n_F_minus_blank, compared as the survivors",
    "DL": "a reference-side diagnostic, LR's distance from the first-order value",
}
TRACKED = tuple(f"{k}_{x}" for k in TRACKERS for x in ("d", "s"))
A1_ONLY = ("n_X", "n_A", "n_ATP", "n_ADP", "n_P")


class ComparisonError(ValueError):
    """A comparison that cannot be made as registered: a refusal, never a gap."""


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _chain(c):
    return [*(f"C_{c}_{j}" for j in range(1, 9)), f"E_{c}", f"W_{c}", f"int_J_I_{c}",
            f"int_S_{c}", f"int_Q_{c}"]  # fmt: skip


SAME = {  # The readouts the engine exports under the references' own names, per world.
    "R1": ["n_N", "n_M", "n_Pi", "n_R", "n_R_s", "F_pol", *_chain("tx"), "int_D_R", "int_D_R_s",
           "G_minus_G0", "H_tx", "H_deg_R", "H_deg_R_s"],
    "R2": ["n_X", "n_N", "n_M", "n_A", "n_ATP", "n_ADP", "n_Pi", "n_R", "n_P", "n_R_s", "F_pol",
           "F_rib", *_chain("tx"), *_chain("tl"), *_chain("tl_s"), "int_D_R", "int_D_R_s",
           "int_D_P", "int_J_C", "G_minus_G0", "H_tx", "H_tl", "H_deg_R", "H_deg_P", "H_rc",
           "H_deg_R_s"],
}  # fmt: skip


def not_compared(world, key):
    """Why a published readout of `world` ("R1" or "R2") is not compared, or None where it is."""
    if key == "t":
        return "the time axis: matched at every compared time, not compared"
    if key.startswith("dG_") or key == "u":
        return "each move's dG and A1's u(t) are not exported (the rule's not_in_this_rule)"
    if key.startswith("C_sum_"):
        return "not an engine export: the engine exports each stage C_<chain>_j and E_<chain>"
    if key in TRACKED:
        return f"the references' tracker series: {TRACKERS[key[:2]]}"
    if world == "R1" and key in A1_ONLY:
        return (
            "not an engine export: R1 declares only the routes in use (§9.12 reading 1), so "
            "the engine's R1 holds no such row; the references carry A1's rows unmoved"
        )
    return None


def compared(world):
    """{engine export: the references' readout} of a world's readouts."""
    return {**{name: name for name in SAME[world]}, **{e: r for r, e in RENAMED.items()}}


def derived(world):
    """{engine readout: the reference quantity}, for the rule's derived readouts of `world`."""
    out = {f"route2_{f}": (f"cohorts['p=0.75, <machine>'].{x}[ts].route2_exact (copies)"
                           if world == "R1" else f"runs[<machine>].cohort_route2.{x}[ts].copies")
           for f, (_, x) in FATES.items()}  # fmt: skip
    if world == "R1":
        for _, (row, x) in FATES.items():
            out[f"survivors_{row}"] = (f"limit_checks['p=<p>, <machine>'].rows[t].fate_{x}.run."
                                       "n_F_minus_blank (copies)")  # fmt: skip
            out[f"label_{row}_cohort"] = (f"cohorts['p=0.75, <machine>'].{x}[ts].route1_blank "
                                          "(copies)")  # fmt: skip
    return out


def mapping():
    """The registered name mapping (erratum 1), as data: per world its compared readouts, its
    derived readouts and the runs that carry them, what is published and not compared, and the
    engine's exports the references do not publish."""
    sections = {
        "cases[]: decl, kind, world": "the case's declaration, matched to the engine run's own",
        "cases[] and runs[]: per_output_residuals, identity_levels, convergence, summary, "
        "label_run": "the references' own checks, not engine exports",
        "limit_checks[]: hold, released, fate_<x>.run's released_into and n_F": "the readouts "
        "hold_tx, int_Qf_<x>1 and n_<row> in copies, each compared once as its readout",
        "limit_checks[]: fate_<x>.run's released_still_present and distance_integrated": "the "
        "references' other routes to the survivors, which the rule defines as the row minus the "
        "blank",
        "limit_checks[]: limits and distances; requester_figures": "the requester's limit, not "
        "this comparison's (the rule's not_in_this_rule)",
        "cohorts[]: route1_sheet and the differences, ratios and limits": "route1_sheet is §9.8's "
        "formula before R-F1's blank; the rest are the references' own checks",
        "cohorts[] at p other than 0.75": "the rule's cohort is at p = 0.75 only",
        "variant_recharging; R2's development_check": "not worlds of the rule (R2A is its "
        "not_in_this_rule)",
        "release_inputs.json": "declarations, methods and the references' own tolerances",
    }
    return dict(
        kind="cells.gene_regulation.fr38_mapping@1",
        interface=dict(tag=REFERENCES_TAG, files=list(FILES)),
        worlds={
            w: dict(
                compared=compared(w),
                derived=derived(w),
                not_compared={
                    **{k: not_compared(w, k) for k in ("t", "dG_*", "u", "C_sum_*", *TRACKED)},
                    **({k: not_compared(w, k) for k in A1_ONLY} if w == "R1" else {}),
                },
            )  # fmt: skip
            for w in ("R1", "R2")
        },
        carried_by={
            "R1 p=<p> <machine>": "the compared readouts and survivors_<row>; route2_<fate> at "
            "p = 0.75",
            "R1 blank <machine>": "the compared readouts (H0 = 0)",
            "R1L p=0.75 <machine>": "the compared readouts against p = 0.75's case (labels change "
            "no physical readout), survivors_<row> and route 1",
            "R2 <machine>": "the compared readouts and route2_<fate>",
        },
        sections_not_compared=sections,
        engine_only=(
            "int_D_route_*, H_route_*, H_total and H_routes_sum (the routes' own, which the "
            "references publish as classes); n_<release>_<fate> (the class totals, equal to n_R "
            "and n_R_s at K = 1); and R1L's label_* other than the cohort's"
        ),
        units=dict(
            readouts="fmol and pJ, G2's units, the engine's",
            copies="limit_checks' and cohorts' amounts and R2's cohort_route2, each times "
            "COPY_FMOL into fmol, each checked inside the interface before any comparison",
        ),
    )


# ---------------------------------------------------------------------------------- the rule


def rule():
    """The registered rule as data, with its engine revision read from its engine entry."""
    data = json.loads(RULE.read_text())
    if data["order_window"]["low"] != "p - 0.5":
        raise ComparisonError("the rule's order window is not [p - 0.5, high]: not this reader's")
    revision = re.search(r"\b[0-9a-f]{40}\b", data["engine"])
    if revision is None:
        raise ComparisonError("the rule names no full engine revision")
    return dict(data, engine_revision=revision.group(0))


def declared_p(r, world, klass):
    hits = [d["p"] for d in r["order_declared"]
            if d["world"] == world and d["readout_class"] == klass]  # fmt: skip
    if len(hits) != 1:
        raise ComparisonError(f"the rule declares {len(hits)} orders for {world}'s {klass}")
    return hits[0]


def klass(name):
    """A readout's class by the rule's class_matching: the hold by its exact name, then by prefix;
    survivors are amounts, route 2 has its own tolerance."""
    if name == f"H_{RID}" or re.fullmatch(rf"H_{RID}_\d+", name):
        return "occupancy"
    for prefixes, c in ((("route2_",), "cohort, route 2"), (("label_",), "cohort, route 1"),
                        (("survivors_", "n_", "F_"), "amount"), (("C_", "E_", "W_"), "occupancy"),
                        (("int_",), "extent"), (("H_",), "heat")):  # fmt: skip
        if name.startswith(prefixes):
            return c
    if name == "G_minus_G0":
        return "free_energy"
    raise ComparisonError(f"readout {name} is in no class of the rule")


def world_of(run):
    return "R2" if run.startswith("R2 ") else "R1"


def readouts_of(run):
    """The table's readouts of one of the rule's runs (mapping's carried_by)."""
    w = world_of(run)
    names = list(compared(w))
    if w == "R2":
        return names + [f"route2_{f}" for f in FATES]
    kind, case, _ = run.split(" ")
    if case == "blank":
        return names
    names += [f"survivors_{row}" for row, _ in FATES.values()]
    if kind == "R1L":
        return names + [f"label_{row}_cohort" for row, _ in FATES.values()]
    return names + ([f"route2_{f}" for f in FATES] if case == "p=0.75" else [])


# ------------------------------------------------------------------------- the engine's side


def _index(times, t, what):
    hits = [i for i, x in enumerate(times) if abs(float(x) - float(t)) <= TIME_TOLERANCE_S]
    if len(hits) != 1:
        raise ComparisonError(f"{what}: {len(hits)} outputs at {t} s, not one")
    return hits[0]


def load(directory):
    """({world: record}, run_record) of an engine_run.py directory at the test instance; each record
    carries its path and sha256."""
    d = Path(directory)
    out = {}
    for path in sorted((d / engine_run.slug(SET)).glob("*.json")):
        record = json.loads(path.read_text())
        record["path"], record["sha256"] = str(path), _sha256(path)
        out[record["world"]] = record
    return out, json.loads((d / "run_record.json").read_text())


def _at(record, name, t):
    if name not in record["readouts"]:
        raise ComparisonError(f"{record['world']} exports no {name}")
    value = record["readouts"][name][_index(record["t"], t, f"{record['world']}'s {name}")]
    if not math.isfinite(value):
        raise ComparisonError(f"{record['world']}'s {name} is {value!r} at {t} s")
    return value


def route2(record, fate, window, ts):
    """(cohort.known_rate, its known_rate_error) in fmol: the run's own releases into `fate`
    during the window still present at ts, carried at the fate's gross k (erratum F)."""
    row = FATES[fate][0]
    t, _, Q, _ = cohort.read(record["path"], row)
    k = release_check.gross_rate(record, row)
    error = cohort.known_rate_error(t, Q, k, *window, ts)
    if error is None:
        raise ComparisonError(f"{record['world']}: route 2's grid error cannot be estimated")
    return cohort.known_rate(t, Q, k, *window, ts), error


def values(runs, run, name, times, window):
    """A readout of `run` at `times` in one step's runs: an export, or a derived readout."""
    record = runs[run]
    if name.startswith("survivors_"):
        blank = runs[f"R1 blank {run.split(' ')[2]}"]
        if blank["dt_s"] != record["dt_s"]:
            raise ComparisonError(f"{run}: its blank is at another step")
        row = name[len("survivors_") :]
        return [_at(record, f"n_{row}", t) - _at(blank, f"n_{row}", t) for t in times]
    if name.startswith("route2_"):
        return [route2(record, name[len("route2_") :], window, ts)[0] for ts in times]
    return [_at(record, name, t) for t in times]


def entry(r, world, name, triple, times):
    """The rule's estimate, tolerance, floor and order of one readout from its values at 4h, 2h
    and h (the rule's tolerance block), with y(h) itself."""
    p = declared_p(r, world, klass(name))
    y4, y2, y1 = triple
    fine = max(abs(a - b) for a, b in zip(y2, y1, strict=True))
    coarse = max(abs(a - b) for a, b in zip(y4, y2, strict=True))
    scale = max(abs(v) for v in y1)
    F, floor, cap = r["factor_of_safety"], r["floor_of_scale"], r["order_window"]["high"]
    estimate = fine / (2**p - 1)
    at_floor = F * estimate <= floor * scale
    order = math.log2(coarse / fine) if fine > 0 and coarse > 0 else None
    return dict(
        readout_class=klass(name), p=p, compared_times=list(times), engine=list(y1),
        estimate=estimate, scale=scale, tolerance=max(F * estimate, floor * scale),
        at_floor=at_floor, zero_scale=scale == 0, order=order,
        in_window=at_floor or (order is not None and p - 0.5 <= order <= cap),
        effective_factor=None if at_floor or order is None
        else F * (2**order - 1) / (2**p - 1),
    )  # fmt: skip


def idle_row(record):
    """The fate row of a run's zero-rate fate, from its own declared p: R at p = 0, R_s at p = 1,
    None otherwise (erratum 1's ruling)."""
    p = float(declaration(record)["p"])
    return "R" if p == 0 else "R_s" if p == 1 else None


def idle(r, e, row_scale):
    """Erratum 1's ruling on a zero-rate fate's survivors, judged as zero: the tolerance is
    floor_of_scale times the row's own magnitude (max |n_F| of the judged run at the compared
    times), the reference must be 0 at every compared time, and the order check is skipped."""
    return dict(
        e,
        zero_rate_fate=True,
        zero_scale=False,
        at_floor=True,
        in_window=True,
        effective_factor=None,
        row_scale=row_scale,
        tolerance=r["floor_of_scale"] * row_scale,
        order_check=(
            "skipped, as at the floor: no molecule is released into a zero-rate fate, so the row "
            "minus its blank is the row's coupling through M, whose step differences are rounding "
            "(erratum 1)"
        ),
    )


def route2_entry(r, record, fate, window, samples):
    """Route 2's tolerance per sample time (erratum 1): max(F g(ts), floor |y(ts)|), with g(ts)
    cohort.known_rate_error on the judged run's outputs; no order check."""
    per = []
    for ts in samples:
        y, g = route2(record, fate, window, ts)
        per.append(
            dict(
                ts=ts,
                engine=y,
                grid_error=g,
                scale=abs(y),
                tolerance=max(r["factor_of_safety"] * g, r["floor_of_scale"] * abs(y)),
            )
        )
    return dict(readout_class="cohort, route 2", per_sample=per, in_window=True)


def agreement(r, runs, run, window, samples):
    """§9.8's route agreement on a labelled run at its step (erratum 1): |route 1 - route 2| within
    route 2's grid error plus route 1's split, k_f (dt/2)^2/(12 tau) times route 1 (release_check's
    split_bound), route 2 on the run's unlabelled twin. Reported; it changes no verdict."""
    labelled, twin = runs[run], runs[run.replace("R1L ", "R1 ", 1)]
    out = []
    for fate, (row, _) in FATES.items():
        for ts in samples:
            one = _at(labelled, f"label_{row}_cohort", ts)
            two, g = route2(twin, fate, window, ts)
            split = release_check.split_bound(fate, labelled["dt_s"]) * abs(one)
            out.append(dict(run=run, fate=fate, ts=ts, route1=one, route2=two, grid_error=g,
                            split=split, agree=abs(one - two) <= g + split))  # fmt: skip
    return out


PROVENANCE = ("engine_revision", "checkout_dirty", "snapshot", "snapshot_patch_sha256", "dt_s",
              "created_utc")  # fmt: skip


def _support(run):
    """The runs a run's derived readouts read beside it: its machine option's blank (survivors) and,
    for R1L, its unlabelled twin (the route agreement). Support, not judged (erratum 1)."""
    if run.startswith("R2 ") or " blank " in run:
        return []
    blank = [f"R1 blank {run.split(' ')[2]}"]
    return blank + ([run.replace("R1L ", "R1 ", 1)] if run.startswith("R1L ") else [])


def table(directories, *, retry=False, only=None):
    """The engine-only table (no reference read): per run of the rule (or the retried runs
    `only`), each readout's entry, its status, and the route agreement. directories is
    {"R1": (4h, 2h, h), "R2": (4h, 2h, h)}; a retry may hold either world alone."""
    r = rule()
    steps = [float(s) for s in (r["retry"]["steps"] if retry else r["worlds"]["R1"]["steps_s"])]
    if not retry and set(directories) != {"R1", "R2"}:
        raise ComparisonError("the first table needs both worlds' runs")
    out, provenance, agree = {}, {}, []
    for w, dirs in directories.items():
        if [float(s) for s in r["worlds"][w]["steps_s"]] != [2.0, 1.0, 0.5]:
            raise ComparisonError(f"{w}'s registered steps are not 2, 1 and 0.5 s")
        block = r["worlds"][w]["cohort"]
        window, samples = tuple(block["window_s"]), [float(s) for s in block["sampled_at_s"]]
        if window != tuple(worlds.R1_WINDOW):
            raise ComparisonError(f"{w}'s window is not the engine worlds' R1_WINDOW")
        triple = []
        for d in dirs:
            runs, meta = load(d)
            provenance[str(d)] = {k: meta.get(k) for k in PROVENANCE}
            if meta.get("engine_revision") != r["engine_revision"] or meta.get("checkout_dirty"):
                raise ComparisonError(f"{d}: not a clean run of the rule's engine revision")
            if any(x["set"] != SET or x["dt_s"] != meta["dt_s"] for x in runs.values()):
                raise ComparisonError(f"{d}: a run not at the test instance or the folder's step")
            triple.append(runs)
        if [float(provenance[str(d)]["dt_s"]) for d in dirs] != steps:
            raise ComparisonError(f"{w}'s folders are not at steps {steps}")
        times = (
            R2_TIMES
            if w == "R2"
            else tuple(float(t) for t in r["worlds"]["R1"]["compared_times_s"])
        )
        for run in [n for n in r["worlds"][w]["runs"] if only is None or n in only]:
            absent = [(d, n) for d, runs in zip(dirs, triple, strict=True)
                      for n in [run, *_support(run)] if n not in runs]  # fmt: skip
            if absent:
                raise ComparisonError(f"{run}: {absent[0][1]} is not in {absent[0][0]}")
            readouts = {}
            for name in readouts_of(run):
                if klass(name) == "cohort, route 2":
                    readouts[name] = route2_entry(r, triple[2][run], name[len("route2_"):],
                                                  window, samples)  # fmt: skip
                    continue
                at = samples if klass(name) == "cohort, route 1" else times
                ys = [values(runs, run, name, at, window) for runs in triple]
                readouts[name] = entry(r, w, name, ys, at)
                if name == f"survivors_{idle_row(triple[2][run])}":
                    row = [_at(triple[2][run], f"n_{name[len('survivors_') :]}", t) for t in at]
                    readouts[name] = idle(r, readouts[name], max(abs(v) for v in row))
            outside = sorted(n for n, e in readouts.items() if not e["in_window"])
            out[run] = dict(
                world=w, status="inconclusive" if outside else "ready", outside_window=outside,
                judged_step_s=steps[-1], support=_support(run),
                records={str(runs[run]["dt_s"]): dict(path=runs[run]["path"],
                                                      sha256=runs[run]["sha256"])
                         for runs in triple},
                readouts=readouts,
            )  # fmt: skip
            if run.startswith("R1L "):
                agree += agreement(r, triple[2], run, window, samples)
    if only is not None and set(only) != set(out):
        raise ComparisonError(f"the retried runs {sorted(set(only) - set(out))} were not found")
    return dict(
        kind="cells.gene_regulation.fr38_table@1",
        rule=dict(path=str(RULE), sha256=_sha256(RULE)),
        erratum=dict(path=str(ERRATUM), sha256=_sha256(ERRATUM)),
        retry=retry, steps_s=list(steps), engine=provenance, runs=out, agreement=agree,
        note="built from the engine's runs alone, before any reference value is read",
    )  # fmt: skip


# --------------------------------------------------------------------------- the references


def _same(a, b):
    """Equal to MATCH relative (two zeros are equal, a zero and a nonzero are not)."""
    a, b = float(a), float(b)
    return abs(a - b) <= MATCH * max(abs(a), abs(b))


def _p(value):
    return format(float(value), "g")


class References:
    """FR-38's interface, read through its own structure (the module docstring)."""

    def __init__(self, directory=INTERFACE):
        self.directory = Path(directory)
        self.data = {f: json.loads((self.directory / f).read_text()) for f in FILES}
        self.sha256 = {f: _sha256(self.directory / f) for f in FILES}
        self.r1, self.r2 = self.data["release_r1.json"], self.data["release_r2.json"]

    def case(self, run, declared):
        """The R1 case of an engine run by its declaration: the machine and, for a blank, H0 = 0,
        else H0 > 0 at the run's p; then tau, both fates' rates, H0 and the window checked."""
        _, case, machine = run.split(" ")
        blank = case == "blank"
        hits = [
            c
            for c in self.r1["cases"]
            if c["decl"]["machine"] == machine
            and (
                (c["decl"]["H0_copies"] == 0)
                if blank
                else c["decl"]["H0_copies"] > 0 and _same(c["decl"]["p"], declared["p"])
            )
        ]
        if len(hits) != 1:
            raise ComparisonError(f"{run}: {len(hits)} reference cases match its declaration")
        self._check(run, hits[0]["decl"], declared, p=not blank)
        return hits[0]

    def run2(self, run, declared):
        """R2's reference run of an engine run, by its machine option, its declaration checked."""
        machine = run.split(" ")[1]
        hits = [x for x in self.r2["runs"] if x["machine"] == machine]
        if len(hits) != 1:
            raise ComparisonError(f"{run}: {len(hits)} reference runs have its machine")
        self._check(run, hits[0]["decl"], declared, p=True)
        return hits[0]

    @staticmethod
    def _check(run, decl, declared, *, p):
        """A reference declaration against the engine run's own: names the keys that differ,
        never their values."""
        keys = ("tau", "k_d", "k_s", "H0_copies") + (("p",) if p else ())
        wrong = [k for k in keys if not _same(decl[k], declared[k])]
        if len(decl["window"]) != 2 or not all(
            _same(a, b) for a, b in zip(decl["window"], declared["window"], strict=True)
        ):
            wrong.append("window")
        if decl["machine"] != declared["machine"] or wrong:
            raise ComparisonError(f"{run}: the reference's declared {wrong or 'machine'} differ")

    def _keys(self, world, readouts):
        """Every published readout is compared or listed with its reason, and each compared one
        is published (a missing comparison is refused, never read as agreement)."""
        mapped = set(compared(world).values())
        loose = sorted(k for k in readouts if k not in mapped and not_compared(world, k) is None)
        missing = sorted(mapped - set(readouts))
        if loose or missing:
            raise ComparisonError(f"{world}: unmapped {loose[:5]}, unpublished {missing[:5]}")

    def series(self, run, declared, wanted):
        """{engine readout: the reference at its compared times, in the engine's units}, for
        wanted = {engine readout: its compared times}, as the table holds them."""
        world = world_of(run)
        source = self.run2(run, declared) if world == "R2" else self.case(run, declared)
        readouts = source["readouts"]
        self._keys(world, readouts)
        if world == "R1" and readouts["t"] != source["t"]:
            raise ComparisonError(f"{run}: the case's two time axes differ")
        machine = run.split(" ")[-1]
        out, names_of = {}, compared(world)
        for name, at in wanted.items():
            if name in names_of:
                ref = readouts[names_of[name]]
                out[name] = [float(ref[_index(readouts["t"], t, f"{run}'s reference")]) for t in at]
                continue
            fate = name[len("route2_") :] if name.startswith("route2_") else None
            if name.startswith(("survivors_", "label_")):
                row = name.split("_", 1)[1].removesuffix("_cohort")
                fate = next(f for f, (r, _) in FATES.items() if r == row)
            letter = FATES[fate][1]
            if name.startswith("survivors_"):
                block = self.r1["limit_checks"][f"p={_p(declared['p'])}, {machine}"]
                if not _same(block["p"], declared["p"]):
                    raise ComparisonError(f"{run}: its limit check is at another p")
                rows = block["rows"]
                pick = [rows[_index([x["t"] for x in rows], t, f"{run}'s survivors")] for t in at]
                out[name] = [x[f"fate_{letter}"]["run"]["n_F_minus_blank"] * COPY_FMOL
                             for x in pick]  # fmt: skip
                continue
            if world == "R2":
                entries, key = source["cohort_route2"][letter], "copies"
            else:
                entries = self.r1["cohorts"][f"p=0.75, {machine}"][letter]
                key = "route1_blank" if name.startswith("label_") else "route2_exact"
            pick = [entries[_index([x["ts"] for x in entries], t, f"{run}'s cohort")] for t in at]
            out[name] = [x[key] * COPY_FMOL for x in pick]
        bad = sorted(n for n, v in out.items() if not all(math.isfinite(float(x)) for x in v))
        if bad:
            raise ComparisonError(f"{run}: the reference's {bad[:5]} hold a non-finite value")
        return out

    def check_units(self, window):
        """The interface's units, checked inside it alone (no engine value). Returns the count of
        values checked, or refuses at the first disagreement:
        - limit_checks' fate rows times COPY_FMOL are the readouts' rows (fmol), to 1e-9;
        - each cohort at its window's end, times COPY_FMOL, lies between the window's releases (the
          readouts' int_Qf, fmol) times e^(-k t2) and the releases, within UNITS."""
        checked = 0
        t2 = window[1]
        for key, block in self.r1["limit_checks"].items():
            p, machine = key.split(", ")
            hits = [
                c
                for c in self.r1["cases"]
                if c["decl"]["machine"] == machine
                and c["decl"]["H0_copies"] > 0
                and _same(c["decl"]["p"], p[2:])
            ]
            if len(hits) != 1:
                raise ComparisonError(f"limit check {key}: {len(hits)} cases")
            x = hits[0]["readouts"]
            for row in block["rows"]:
                i = _index(x["t"], row["t"], f"limit check {key}")
                for _, (name, letter) in FATES.items():
                    a, b = row[f"fate_{letter}"]["run"]["n_F"] * COPY_FMOL, x[f"n_{name}"][i]
                    if abs(a - b) > 1e-9 * max(abs(a), abs(b)):
                        raise ComparisonError(f"limit check {key}: its rows are not copies")
                    checked += 1
        cohorts = [
            (
                c["decl"],
                c["readouts"],
                self.r1["cohorts"][f"p=0.75, {c['decl']['machine']}"],
                ("route1_blank", "route2_exact"),
            )
            for c in self.r1["cases"]
            if c["decl"]["H0_copies"] > 0 and _same(c["decl"]["p"], 0.75)
        ]
        cohorts += [(x["decl"], x["readouts"], x["cohort_route2"], ("copies",))
                    for x in self.r2["runs"]]  # fmt: skip
        if len(cohorts) != 4:
            raise ComparisonError(f"{len(cohorts)} cohorts at p = 0.75, not R1's two and R2's two")
        for decl, x, block, keys in cohorts:
            i = _index(x["t"], t2, "a cohort's window end")
            for _, (_, letter) in FATES.items():
                released, k = x[f"int_Qf_{letter}1"][i], decl[f"k_{letter}"]
                (e,) = [e for e in block[letter] if abs(e["ts"] - t2) <= TIME_TOLERANCE_S]
                for key in keys:
                    c = e[key] * COPY_FMOL
                    low, high = released * math.exp(-k * t2) * (1 - UNITS), released * (1 + UNITS)
                    if not (released > 0 and low <= c <= high):
                        raise ComparisonError("a cohort's amount is not copies of its releases")
                    checked += 1
        return checked


def declaration(record):
    """The engine run's own release declaration, from its definition (references' keys)."""
    raw = record["definition"]
    (block,) = [o for o in raw["model"]["operators"] if o["law"] == worlds.POLYMERISATION]
    (release,) = [c["release"] for c in block["chains"] if c.get("release")]
    return dict(
        p=release["durable_fraction"],
        machine=release["machine"],
        H0_copies=release["initial_copies"][0],
        tau=release["dwell_s"],
        k_d=release_check.gross_rate(record, "R"),
        k_s=release_check.gross_rate(record, "R_s"),
        window=list(worlds.R1_WINDOW),
    )


# ------------------------------------------------------------------------------- the verdict


def _aggregate(statuses):
    """FR-25's precedence (D278, D282; erratum 1): any failed, failed; else any inconclusive,
    inconclusive; else passed."""
    statuses = list(statuses)
    if not statuses:
        raise ComparisonError("no run to aggregate")
    return "failed" if "failed" in statuses else (
        "inconclusive" if "inconclusive" in statuses else "passed")  # fmt: skip


def judge(first, retry=None, refs=None, erratum=None):
    """Each run's verdict against the table(s), each world's and FR-38's (the module docstring).
    The retry's table, due where the first holds an inconclusive run, replaces those runs."""
    r = rule()
    erratum = json.loads(ERRATUM.read_text()) if erratum is None else erratum
    if erratum["mapping"] != json.loads(json.dumps(mapping())):
        raise ComparisonError("erratum 1's mapping is not this reader's")
    for t in [first, *([retry] if retry else [])]:
        if t["rule"]["sha256"] != _sha256(RULE) or t["erratum"]["sha256"] != _sha256(ERRATUM):
            raise ComparisonError("a table was built under another rule or erratum")
    every = sorted([*r["worlds"]["R1"]["runs"], *r["worlds"]["R2"]["runs"]])
    if first["retry"] or sorted(first["runs"]) != every:
        raise ComparisonError("the first table must hold every run of the rule, at its steps")
    due = sorted(w for w, e in first["runs"].items() if e["status"] == "inconclusive")
    if due and retry is None:
        raise ComparisonError(f"the rule's retry is due for {due}: run it first")
    if retry is not None and (not retry["retry"] or sorted(retry["runs"]) != due):
        raise ComparisonError(f"the retry's table holds {sorted(retry['runs'])}, not {due}")
    final = {**first["runs"], **(retry["runs"] if retry else {})}
    refs = References() if refs is None else refs
    units = refs.check_units(tuple(r["worlds"]["R1"]["cohort"]["window_s"]))
    verdicts = {}
    for run, e in final.items():
        judged = e["records"][str(e["judged_step_s"])]
        if _sha256(judged["path"]) != judged["sha256"]:
            raise ComparisonError(f"{run}: its judged record changed after the table")
        record = dict(json.loads(Path(judged["path"]).read_text()), path=judged["path"])
        wanted = {name: x.get("compared_times") or [s["ts"] for s in x["per_sample"]]
                  for name, x in e["readouts"].items()}  # fmt: skip
        ref = refs.series(run, declaration(record), wanted)
        results = {}
        for name, x in e["readouts"].items():
            if x["readout_class"] == "cohort, route 2":
                per = [dict(ts=s["ts"], gap=abs(s["engine"] - v), tolerance=s["tolerance"],
                            grid_error=s["grid_error"])
                       for s, v in zip(x["per_sample"], ref[name], strict=True)]  # fmt: skip
                for s in per:
                    s["margin"] = s["gap"] / s["tolerance"] if s["tolerance"] else None
                    s["passed"] = s["gap"] <= s["tolerance"]
                results[name] = dict(
                    readout_class=x["readout_class"],
                    per_sample=per,
                    passed=all(s["passed"] for s in per),
                    margin=max((s["margin"] or 0.0) for s in per),
                )
                continue
            gap = max(abs(a - b) for a, b in zip(x["engine"], ref[name], strict=True))
            zero_rate = x.get("zero_rate_fate", False)
            reference_zero = all(v == 0 for v in ref[name]) if zero_rate else None
            if zero_rate:  # Erratum 1's ruling: judged as zero against the row's own floor.
                passed = reference_zero and gap <= x["tolerance"]
            else:
                passed = gap == 0 if x["zero_scale"] else gap <= x["tolerance"]
            results[name] = dict(
                readout_class=x["readout_class"], p=x["p"], gap=gap, tolerance=x["tolerance"],
                margin=gap / x["tolerance"] if x["tolerance"] else None, passed=passed,
                at_floor=x["at_floor"], zero_scale=x["zero_scale"], order=x["order"],
                in_window=x["in_window"], effective_factor=x["effective_factor"],
                scale=x["scale"], estimate=x["estimate"], compared_times=len(x["compared_times"]),
                zero_rate_fate=zero_rate, reference_zero=reference_zero,
                row_scale=x.get("row_scale"),
            )  # fmt: skip
        failed = sorted(n for n, x in results.items() if not x["passed"])
        status = "inconclusive" if e["status"] == "inconclusive" else (
            "failed" if failed else "passed")  # fmt: skip
        verdicts[run] = dict(world=e["world"], status=status, failed=failed,
                             outside_window=e["outside_window"], judged_step_s=e["judged_step_s"],
                             retried=run in due, readouts=results)  # fmt: skip
    by_world = {w: _aggregate(v["status"] for v in verdicts.values() if v["world"] == w)
                for w in ("R1", "R2")}  # fmt: skip
    nearest = sorted(((x["margin"] or 0.0, run, name) for run, v in verdicts.items()
                      for name, x in v["readouts"].items()), reverse=True)[:12]  # fmt: skip
    agree = [a for a in first["agreement"] if a["run"] not in due]
    agree += retry["agreement"] if retry else []
    return dict(
        kind="cells.gene_regulation.fr38_verdict@1",
        verdict=_aggregate(by_world.values()),
        worlds=by_world,
        runs=verdicts,
        nearest=[dict(margin=m, run=run, readout=name) for m, run, name in nearest],
        agreement=dict(
            all_agree=all(a["agree"] for a in agree),
            rows=agree,
            note="reported with the verdicts; it changes none (erratum 1)",
        ),
        retry=dict(due=due, run=retry is not None),
        references=dict(
            tag=REFERENCES_TAG,
            directory=str(refs.directory),
            sha256=refs.sha256,
            units_checked=units,
        ),
        rule=dict(path=str(RULE), sha256=_sha256(RULE)),
        erratum=dict(path=str(ERRATUM), sha256=_sha256(ERRATUM)),
        engine=dict(
            revision=r["engine_revision"],
            runs=first["engine"],
            retry_runs=retry["engine"] if retry else None,
        ),
        not_compared={w: m["not_compared"] for w, m in mapping()["worlds"].items()},
        not_blind=list(erratum.get("not_blind", [])),
    )


# ------------------------------------------------------------------------- keys and shapes


def _leaf(x):
    return None if isinstance(x, (dict, list)) else (
        "<bool>" if isinstance(x, bool) else "<number>" if isinstance(x, (int, float))
        else "<str>" if isinstance(x, str) else "<null>")  # fmt: skip


def _shape(x):
    if isinstance(x, dict):
        return ("dict", tuple((k, _shape(v)) for k, v in x.items()))
    if isinstance(x, list):
        return ("list", len(x), tuple(sorted({repr(_shape(v)) for v in x})))
    return _leaf(x)


def structure(x, indent=0, out=print):
    """Print x's keys and array shapes, never a value: leaves by type, dicts of one leaf type or
    of one shape folded, a list by its length and its first element's structure, and the keys by
    which any other element differs."""
    pad = "  " * indent
    if isinstance(x, dict):
        leaves = {_leaf(v) for v in x.values()}
        if x and None not in leaves and len(leaves) == 1:
            out(f"{pad}{{{len(x)} keys, each {leaves.pop()}}}: {list(x)}")
            return
        shapes = {_shape(v) for v in x.values()}
        if len(x) > 3 and None in leaves and len(leaves) == 1 and len(shapes) == 1:
            out(f"{pad}{{{len(x)} keys of one structure}}: {list(x)}")
            structure(next(iter(x.values())), indent + 1, out)
            return
        for k, v in x.items():
            out(f"{pad}{k}: {_leaf(v)}" if _leaf(v) else f"{pad}{k}:")
            if not _leaf(v):
                structure(v, indent + 1, out)
    elif isinstance(x, list):
        out(f"{pad}list[{len(x)}] of {sorted({_leaf(e) or type(e).__name__ for e in x})}")
        nested = [e for e in x if isinstance(e, (dict, list))]
        if nested:
            structure(nested[0], indent + 1, out)
            first = set(_paths(nested[0]))
            for i, e in enumerate(nested[1:], 1):
                extra, lost = sorted(set(_paths(e)) - first), sorted(first - set(_paths(e)))
                if extra or lost:
                    out(f"{pad}  [element {i}: keys added {extra}, missing {lost}]")


def _paths(x, prefix=""):
    if isinstance(x, dict):
        return [p for k, v in x.items() for p in _paths(v, f"{prefix}/{k}")]
    if isinstance(x, list):
        return [prefix] + [p for e in x if isinstance(e, (dict, list)) for p in _paths(e, prefix)]
    return [prefix]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("structure").add_argument("--interface", default=str(INTERFACE))
    sub.add_parser("mapping").add_argument("--out")
    t = sub.add_parser("table")
    t.add_argument("--r1", nargs=3)
    t.add_argument("--r2", nargs=3)
    t.add_argument("--retry", action="store_true")
    t.add_argument("--runs", nargs="+", help="the retry: the runs retried")
    t.add_argument("--out", required=True)
    j = sub.add_parser("judge")
    j.add_argument("table")
    j.add_argument("--retry")
    j.add_argument("--interface", default=str(INTERFACE))
    j.add_argument("--not-blind", help="a JSON list of the judge's further disclosures")
    j.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.command == "structure":
        for name in FILES:
            print(f"=== {name}")
            structure(json.loads((Path(args.interface) / name).read_text()))
        return 0
    if args.command == "mapping":
        text = json.dumps(mapping(), indent=1) + "\n"
        Path(args.out).write_text(text) if args.out else print(text, end="")
        return 0
    if args.command == "table":
        if args.retry != (args.runs is not None):
            parser.error("a retry names its runs, and only a retry does")
        dirs = {w: d for w, d in (("R1", args.r1), ("R2", args.r2)) if d}
        out = table(dirs, retry=args.retry, only=args.runs)
        Path(args.out).write_text(json.dumps(out, indent=1) + "\n")
        print(json.dumps({run: e["status"] for run, e in out["runs"].items()}))
        return 0
    first = json.loads(Path(args.table).read_text())
    retry = json.loads(Path(args.retry).read_text()) if args.retry else None
    out = judge(first, retry, References(args.interface))
    if args.not_blind:
        out["not_blind"] += [str(x) for x in json.loads(Path(args.not_blind).read_text())]
    source, patch = engine_run.provenance(Path(args.out).parent)
    if patch is not None:
        Path(f"{args.out}.checkout.patch").write_text(patch)
        source["dirty_diff"] = f"{args.out}.checkout.patch"
    out["judge_source"] = source
    out["tables"] = {p: _sha256(p) for p in [args.table, *([args.retry] if args.retry else [])]}
    Path(args.out).write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(dict(verdict=out["verdict"], worlds=out["worlds"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
