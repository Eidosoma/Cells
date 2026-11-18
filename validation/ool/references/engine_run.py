"""Running the registered OL1 harness over an engine probe set, with a machine-readable verdict.

    python -m validation.ool.references.engine_run --probes DIR --out DIR

It converts the set (``engine_layout.convert``), runs every registered row with the harness
(``harness.run_rows``, unchanged), and writes ``verdict.json``:
- the pins: the engine's revision, the inputs' pin and their hashes, the references' revision;
- per row and per probed pair: the verdict, every check's numbers, and a short margin summary;
- the registered planted controls' magnitudes (the references' own, unchanged), and a few
  planted errors applied to the engine's own records, each of which must fail its check
  (informational: they show the checks have teeth on these records; no verdict rests on them).

Exit status: the harness's (0 pass, 1 a failed check, 2 missing or malformed records).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np

from . import closed_world, detailed_balance, harness, ledger
from .common import MissingRecord, RecordFormatError, jsonable
from .design import REGISTERED_MAGNITUDES, design_document
from .engine_layout import convert, copy_format
from .laws import Law
from .records import load_probe, load_run
from .registered import DESIGN_DIR, registered_world
from .ssa_oracle import ChannelTable
from .world import Conventions

MARGIN_KEYS = ("max_abs_log_ratio", "max_abs_residual", "max_abs_log_residual", "zero_pattern_mismatches",
               "singular_pattern_mismatches", "total_variation", "atol", "max_abs_z", "z_critical", "near_ties",
               "max_rel_time_error", "max_abs_closure", "cycles_checked", "edges_checked", "entries", "events",
               "rows", "declarations", "end_reason", "statistic", "critical", "bitwise")


def margins(check: dict) -> dict:
    d = check.get("detail", {})
    return {k: d[k] for k in MARGIN_KEYS if k in d}


def summarise(report: dict) -> dict:
    out = {}
    for row, r in report.items():
        out[row] = dict(title=r["title"], passed=r["passed"],
                        missing_or_malformed=r.get("missing_or_malformed"),
                        checks=[dict(name=c["name"], passed=c["passed"], margins=margins(c),
                                     conventions=c["detail"].get("conventions"), world=c["detail"].get("world"),
                                     part=c["detail"].get("part"))
                                for c in r.get("checks", [])])
    return out


def references_revision() -> dict:
    here = Path(__file__).resolve().parent
    def git(*args):
        return subprocess.run(["git", "-C", str(here), *args], capture_output=True, text=True).stdout.strip()
    return dict(revision=git("rev-parse", "HEAD"), dirty=bool(git("status", "--porcelain", "--", str(here))))


# ---------------------------------------------------------------- planted errors on the engine's records

def planted_on_engine(roles: dict) -> list:
    """Registered planted forms applied to the engine's own records; each must fail its check."""
    out = []
    # row OL1-1: the catalytic factor at each direction's own state, on the engine's reverse rates
    meta, arrays = load_probe(roles["kernel_probe"][0])
    w = registered_world("ol1_wa")
    law = Law(w, Conventions.from_declared(meta["conventions"]))
    states = np.asarray(arrays["input_states"])
    am = np.asarray(arrays["a_minus"], float).copy()
    for k, s in enumerate(states):
        p = tuple(int(v) for v in s)
        for r, st in enumerate(w.steps):
            if not law.cat[st.name] or not (0 < am[k, r] < np.inf):
                continue
            n = tuple(a - d for a, d in zip(p, law.nu[st.name]))
            m = tuple(min(a, b) for a, b in zip(n, p))
            am[k, r] *= float(Fraction(law.factor(st, p)) / Fraction(law.factor(st, m)))
    res = detailed_balance.kolmogorov(w, states, arrays["a_plus"], am)
    out.append(dict(row="OL1-1", planted="at_state_factor on the engine's reverse rates", check="kolmogorov",
                    caught=not res.passed, numbers=margins(res.as_dict())))
    # row OL1-2: catalysis in one direction only, on the engine's closed-world table
    meta, arrays = load_probe(roles["closed_world"][0])
    w = registered_world("ol1_wa_closed")
    law = Law(w, Conventions.from_declared(meta["conventions"]))
    states = np.asarray(arrays["input_states"])
    am = np.asarray(arrays["a_minus"], float).copy()
    for k, s in enumerate(states):
        p = tuple(int(v) for v in s)
        for r, st in enumerate(w.steps):
            if not law.cat[st.name] or not (0 < am[k, r] < np.inf):
                continue
            n = tuple(a - d for a, d in zip(p, law.nu[st.name]))
            m = tuple(min(a, b) for a, b in zip(n, p))
            am[k, r] /= float(law.factor(st, m))
    res = closed_world.check_closed_world(law, states, arrays["a_plus"], am)["stationary_law"]
    out.append(dict(row="OL1-2", planted="forward-only catalysis on the engine's table", check="stationary_law",
                    caught=not res.passed, numbers=margins(res.as_dict())))
    # row OL1-5: the engine's heat with its sign flipped
    rmeta, rec = load_run(roles["ledger_run"][0])
    w = registered_world("ol1_wa")
    law = Law(w, Conventions.from_declared(rmeta["conventions"]))
    table = ChannelTable.from_declared(rmeta["channels"], law)
    n0 = w.state_from(rmeta["initial_state"])
    res = ledger.check_ledger(law, table, n0, rec["event_channel"], rec["row_event"], rec["counts"],
                              -np.asarray(rec["heat_kT"]), rec["work_kT"])
    out.append(dict(row="OL1-5", planted="the engine's heat with its sign flipped", check="ledger_closure",
                    caught=not res.passed, numbers=margins(res.as_dict())))
    # row OL1-6: the other stream presented as the replay
    _, other = load_run(roles["other_stream"][0])
    from .streams import check_replay

    res = check_replay(rec, other, ("event_channel", "event_time", "row_event", "counts", "heat_kT", "work_kT"))
    out.append(dict(row="OL1-6", planted="the other stream's run presented as the replay", check="bitwise_replay",
                    caught=not res.passed, numbers=res.as_dict()["detail"]))
    return out


def row4_parts(roles: dict) -> dict:
    """Row OL1-4's four parts computed one by one, so a part that stops the row (status 2) does not
    hide the others' numbers. Informational: the registered verdict is the harness's."""
    from . import mass_action
    from .records import load_ensemble, load_refusals
    from .ssa_oracle import FloatRates, replay

    out = {}
    try:
        part_a = []
        for path in roles["kernel_probe"]:
            meta, arrays = load_probe(path)
            law = Law(registered_world("ol1_wa"), Conventions.from_declared(meta["conventions"]))
            res = detailed_balance.compare_rates(law, arrays["input_states"], arrays["a_plus"], arrays["a_minus"],
                                                 "forward")
            part_a.append(dict(conventions=meta["conventions"], passed=res.passed, margins=margins(res.as_dict())))
        out["a_forward_form"] = part_a
    except (MissingRecord, RecordFormatError) as exc:
        out["a_forward_form"] = dict(problem=str(exc))
    try:
        meta, arrays = load_ensemble(roles["wb_ensemble"])
        design = mass_action.registered_ladder_design()
        samples, ids_by_rung = {}, {}
        for M in design["rungs"]:
            x = np.asarray(arrays[f"observation_counts_m{M}"])
            samples[M] = x[:, :, registered_world(f"ol1_wb_m{M}").index("T@pool")]
            ids_by_rung[M] = set(meta["rungs"][str(M)]["streams"])
        res = mass_action.ensemble_test(samples, design)
        rungs = list(ids_by_rung)
        shared = {f"{a}&{b}": len(ids_by_rung[a] & ids_by_rung[b]) for i, a in enumerate(rungs) for b in rungs[i + 1:]}
        within = {M: len(ids) for M, ids in ids_by_rung.items()}
        out["b_large_system"] = dict(passed=res.passed, margins=margins(res.as_dict()), rungs=res.as_dict()["detail"].get("rungs"),
                                     distinct_streams_within_each_rung=within,
                                     stream_identities_shared_between_rungs=shared)
    except (MissingRecord, RecordFormatError, KeyError) as exc:
        out["b_large_system"] = dict(problem=str(exc))
    try:
        part_c, part_d = [], []
        for path in roles["ledger_run"]:
            rmeta, rec, law, table = harness.run_records(path)
            n0 = law.world.state_from(rmeta["initial_state"])
            res = replay(FloatRates(law), table, n0, rec["event_time"], rec["event_channel"], rec["event_uniforms"])
            part_c.append(dict(conventions=rmeta["conventions"], passed=res.passed, margins=margins(res.as_dict()),
                               end=harness.end_check(rmeta, path).as_dict()))
            mres = harness.moiety_check(law, table, n0, rec, path)
            part_d.append(dict(conventions=rmeta["conventions"], passed=mres.passed, detail=mres.as_dict()["detail"]))
        ref = harness.refusal_check(load_refusals(roles["refusals"]))
        out["c_exact_ssa"] = part_c
        out["d_moieties_and_refusals"] = dict(moieties=part_d, refusals=ref.as_dict())
    except (MissingRecord, RecordFormatError) as exc:
        out["c_d"] = dict(problem=str(exc))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="validation.ool.references.engine_run")
    ap.add_argument("--probes", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    verdict = dict(format="ool_references.verdict@1", references=references_revision(),
                   probes=str(Path(args.probes).resolve()))
    try:
        roles, prov = convert(args.probes, out / "canonical")
    except (MissingRecord, RecordFormatError) as exc:
        verdict.update(status=2, problem=f"the set does not parse: {exc}")
        (out / "verdict.json").write_text(json.dumps(jsonable(verdict), indent=1))
        print(verdict["problem"])
        return 2
    copy_format(args.probes, out)
    verdict["engine"] = prov
    tags = list(roles)
    status_all, reports, rows = 0, {}, {}
    status, report = harness.run_rows(roles[tags[0]])
    reports[tags[0]] = report
    status_all = max(status_all, status)
    for tag in tags[1:]:
        status, report = harness.run_rows(roles[tag], ["OL1-3", "OL1-4"])
        reports[tag] = report
        status_all = max(status_all, status)
    for tag, report in reports.items():
        for row, r in summarise(report).items():
            rows.setdefault(row, {})[f"wb_ensemble and rescale_pair from {tag}"] = r
    (out / "harness_reports.json").write_text(json.dumps(jsonable(reports), indent=1))
    verdict["rows"] = {row: dict(passed=all(v["passed"] for v in by.values()), by_pairs=by) for row, by in rows.items()}
    verdict["tally"] = dict(rows=len(rows), passed=sum(v["passed"] for v in verdict["rows"].values()))
    verdict["status"] = status_all
    verdict["diagnostics_row_OL1-4_by_part"] = {tag: row4_parts(roles[tag]) for tag in tags}
    try:
        verdict["planted_on_engine_records"] = planted_on_engine(roles[tags[0]])
    except (MissingRecord, RecordFormatError) as exc:  # pragma: no cover - only when a row already failed
        verdict["planted_on_engine_records"] = dict(problem=str(exc))
    design = design_document()
    verdict["registered_planted_controls"] = dict(
        magnitudes=REGISTERED_MAGNITUDES,
        ladder_power=design["rows"]["OL1-4"]["b_large_system"]["family_power"],
        note="the references' own planted controls, as registered (unchanged by this run)")
    verdict["registered_inputs"] = sorted(p.name for p in DESIGN_DIR.glob("*.json"))
    (out / "verdict.json").write_text(json.dumps(jsonable(verdict), indent=1))
    for row, v in verdict["rows"].items():
        print(f"{row}: {'pass' if v['passed'] else 'FAIL'}")
    print(f"status {status_all}; verdict {out / 'verdict.json'}")
    return status_all


if __name__ == "__main__":
    sys.exit(main())
