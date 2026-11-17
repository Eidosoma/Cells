"""The comparison harness: runs every OL1 reference row against saved records.

It is written without the engine. Every input is a saved record or a registered file, and any
record a row needs that is absent fails that row loudly, naming what is missing.

Usage:
    python -m validation.ool.references.harness make-probes OUT_DIR
    python -m validation.ool.references.harness run --roles ROLES.json [--rows OL1-1,...] [--out REPORT.json]

ROLES.json maps each role to a record directory, or to a list of directories (one per probed
convention pair) for ``kernel_probe``, ``closed_world``, ``closed_world_uncatalysed``,
``ledger_run``, ``replay`` and ``other_stream``. ``rescale_pair`` maps to
{"base": DIR, "scaled": DIR}. The layouts are in ``records.py``; the rows and roles in README.md.

Exit status: 0 when every requested row passes; 1 when a check fails; 2 when a record, a role or
a declared token is missing or malformed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np

from . import catalysis, closed_world, detailed_balance, ledger, mass_action, streams
from .common import CheckResult, MissingRecord, RecordFormatError, jsonable
from .design import (
    BOUNDARY_PROBE_FILE,
    CLOSED_WORLD_FILE,
    KERNEL_PROBE_FILE,
    LEDGER_RUN,
    PROBED_CONVENTIONS,
    RESCALE_RUN,
)
from .laws import Law
from .records import load_ensemble, load_probe, load_refusals, load_run
from .registered import DESIGN_DIR, WB_RUNGS, registered_world
from .ssa_oracle import ChannelTable, FloatRates, check_convention, replay
from .world import Conventions

ROWS = {
    "OL1-1": ("Every channel keeps local detailed balance", ("kernel_probe", "boundary_probe")),
    "OL1-2": ("A closed world relaxes to exp(-F/k_BT)", ("closed_world",)),
    "OL1-3": ("Catalysis is kinetic only", ("closed_world_uncatalysed", "rescale_pair")),
    "OL1-4": ("Mass action with registry potentials", ("kernel_probe", "wb_ensemble", "ledger_run", "refusals")),
    "OL1-5": ("The ledgers for reactions", ("ledger_run",)),
    "OL1-6": ("Streams and replay", ("ledger_run", "replay", "other_stream")),
}


# ------------------------------------------------------------------ registered inputs

def registered_states(name: str) -> np.ndarray:
    doc = json.loads((DESIGN_DIR / name).read_text())
    return np.asarray(doc["states"], dtype=np.int64)


def make_probes(out_dir) -> Path:
    """Copy every registered input into OUT_DIR (the engine side reads these files)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=False)
    for f in sorted(DESIGN_DIR.rglob("*.json")):
        dest = out / f.relative_to(DESIGN_DIR)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, dest)
    (out / "inputs.json").write_text(json.dumps(dict(
        numpy=np.__version__, note="registered inputs of the OL1 references; the probe states are echoed by the "
                                   "engine and compared bitwise"), indent=1))
    return out


# ------------------------------------------------------------------ helpers

def as_list(x) -> list:
    return [x] if isinstance(x, (str, Path)) else list(x)


class Context:
    def __init__(self, roles: dict):
        self.roles = roles

    def path(self, role: str):
        if role not in self.roles:
            raise MissingRecord(f"role {role!r} was not supplied")
        return self.roles[role]


def law_for(world_id: str, conventions: dict) -> Law:
    return Law(registered_world(world_id), Conventions.from_declared(conventions))


def echo_check(meta: dict, arrays: dict, expected_states: np.ndarray, world_id: str, where: str) -> None:
    if meta.get("world") != world_id:
        raise RecordFormatError(f"{where}: world {meta.get('world')!r}, {world_id!r} expected")
    w = registered_world(world_id)
    if list(meta["steps"]) != [st.name for st in w.steps] or list(meta["places"]) != [p.name for p in w.finite]:
        raise RecordFormatError(f"{where}: step or place order differs from the registered world")
    states = np.asarray(arrays.get("input_states"))
    if states.shape != expected_states.shape or not np.array_equal(states, expected_states):
        raise RecordFormatError(f"{where}: the echoed input_states differ from the registered probe states")


def pair_of(conventions: dict) -> tuple:
    c = Conventions.from_declared(conventions)
    return (c.condensed_measure, c.last_molecule)


REGISTERED_PAIRS = sorted((p["condensed_measure"], p["last_molecule"]) for p in PROBED_CONVENTIONS)


def require_registered_pairs(metas: list, role: str) -> None:
    """A per-pair role must hold exactly the registered convention pairs, once each."""
    pairs = sorted(pair_of(m["conventions"]) for m in metas)
    if pairs != REGISTERED_PAIRS:
        raise RecordFormatError(f"role {role!r} holds the convention pairs {pairs}; the registered design "
                                f"probes exactly {REGISTERED_PAIRS}, once each")


def probe_tables(role_paths, world_id: str, states_file: str) -> list:
    expected = registered_states(states_file)
    out = []
    loaded = [load_probe(path) for path in as_list(role_paths)]
    require_registered_pairs([m for m, _ in loaded], f"probe of {world_id}")
    for path, (meta, arrays) in zip(as_list(role_paths), loaded, strict=True):
        echo_check(meta, arrays, expected, world_id, str(path))
        a_plus, a_minus = np.asarray(arrays["a_plus"], float), np.asarray(arrays["a_minus"], float)
        if a_plus.shape != (len(expected), len(meta["steps"])) or a_minus.shape != a_plus.shape:
            raise RecordFormatError(f"{path}: a_plus/a_minus shape {a_plus.shape}, {a_minus.shape}")
        out.append((meta, expected, a_plus, a_minus))
    return out


def run_records(path) -> tuple[dict, dict, Law, ChannelTable]:
    meta, arrays = load_run(path)
    check_convention(meta["ssa"])
    law = law_for(meta["world"], meta["conventions"])
    table = ChannelTable.from_declared(meta["channels"], law)
    return meta, arrays, law, table


def tagged(res: CheckResult, **tags) -> CheckResult:
    res.detail = dict(tags, **res.detail)
    return res


# ------------------------------------------------------------------ the rows

def row_1(ctx: Context) -> list:
    out = []
    for role, world_id, states_file in (("kernel_probe", "ol1_wa", KERNEL_PROBE_FILE),
                                        ("boundary_probe", "ol1_boundary", BOUNDARY_PROBE_FILE)):
        for meta, states, ap, am in probe_tables(ctx.path(role), world_id, states_file):
            law = law_for(world_id, meta["conventions"])
            res = detailed_balance.check_kernel_table(law, states, ap, am)
            keys = ("kolmogorov", "identity", "reverse_rates") if role == "kernel_probe" else (
                "kolmogorov", "identity", "forward_form", "reverse_rates")
            for key in keys:
                out.append(tagged(res[key], world=world_id, conventions=meta["conventions"]))
    return out


def row_2(ctx: Context) -> list:
    out = []
    for meta, states, ap, am in probe_tables(ctx.path("closed_world"), "ol1_wa_closed", CLOSED_WORLD_FILE):
        law = law_for("ol1_wa_closed", meta["conventions"])
        for res in closed_world.check_closed_world(law, states, ap, am).values():
            out.append(tagged(res, conventions=meta["conventions"]))
    return out


def row_3(ctx: Context) -> list:
    out = []
    for meta, states, ap, am in probe_tables(ctx.path("closed_world_uncatalysed"), "ol1_wa_closed_uncatalysed",
                                             CLOSED_WORLD_FILE):
        law = law_for("ol1_wa_closed_uncatalysed", meta["conventions"])
        res = closed_world.check_closed_world(law, states, ap, am)["stationary_law"]
        out.append(tagged(res, world="ol1_wa_closed_uncatalysed", conventions=meta["conventions"]))
    pair = ctx.path("rescale_pair")
    if not isinstance(pair, dict) or set(pair) != {"base", "scaled"}:
        raise RecordFormatError("rescale_pair must map to {'base': DIR, 'scaled': DIR}")
    mb, ab, _, _ = run_records(pair["base"])
    ms, as_, _, _ = run_records(pair["scaled"])
    if (mb["world"], ms["world"]) != ("ol1_wa_closed", "ol1_wa_closed_x2"):
        raise RecordFormatError("rescale_pair: the worlds must be ol1_wa_closed and ol1_wa_closed_x2")
    sizes = (len(np.asarray(ab.get("event_channel", []))), len(np.asarray(as_.get("event_channel", []))))
    out.append(CheckResult("registered_run_length", sizes == (RESCALE_RUN["events"],) * 2,
                           dict(events=list(sizes), registered=RESCALE_RUN["events"])))
    if mb["stream"] != ms["stream"]:
        out.append(CheckResult("uniform_factor_rescales_time", False, dict(problem="the two runs declare different streams")))
    else:
        out.append(catalysis.check_time_rescaling(ab, as_))
    return out


def row_4(ctx: Context) -> list:
    out = []
    for meta, states, ap, am in probe_tables(ctx.path("kernel_probe"), "ol1_wa", KERNEL_PROBE_FILE):
        law = law_for("ol1_wa", meta["conventions"])
        out.append(tagged(detailed_balance.compare_rates(law, states, ap, am, "forward"), part="a",
                          conventions=meta["conventions"]))
    meta, arrays = load_ensemble(ctx.path("wb_ensemble"))
    rungs = list(WB_RUNGS)
    for M in rungs:
        x = np.asarray(arrays.get(f"observation_counts_m{M}", np.empty((0, 0, 0))))
        if x.ndim != 3 or x.shape[0] != mass_action.ENSEMBLE_RUNS or x.shape[1] != len(mass_action.OBSERVATION_TIMES):
            raise RecordFormatError(f"wb_ensemble rung {M}: {x.shape[:2]} runs and times; the registered design "
                                    f"is {mass_action.ENSEMBLE_RUNS} runs at {len(mass_action.OBSERVATION_TIMES)} times")
    design = mass_action.registered_ladder_design()
    samples, streams_seen = {}, set()
    for M in design["rungs"]:
        key = f"observation_counts_m{M}"
        if key not in arrays or str(M) not in meta["rungs"]:
            raise MissingRecord(f"wb_ensemble lacks rung {M}")
        ids = [str(s) for s in meta["rungs"][str(M)].get("streams", [])]
        x = np.asarray(arrays[key])
        if len(ids) != x.shape[0] or len(set(ids)) != len(ids) or streams_seen & set(ids):
            raise RecordFormatError(f"wb_ensemble rung {M}: every run needs its own stream identity")
        streams_seen |= set(ids)
        idx_T = registered_world(f"ol1_wb_m{M}").index("T@pool")
        samples[M] = x[:, :, idx_T]
    out.append(tagged(mass_action.ensemble_test(samples, design), part="b"))
    run_metas(ctx.path("ledger_run"), "ledger_run")
    for path in as_list(ctx.path("ledger_run")):
        rmeta, rec, law, table = run_records(path)
        names = ("event_time", "event_channel", "event_uniforms")
        et, ec, eu = need_arrays(rec, names, path)
        n0 = law.world.state_from(rmeta["initial_state"])
        out.append(tagged(replay(FloatRates(law), table, n0, et, ec, eu), part="c", conventions=rmeta["conventions"]))
        out.append(tagged(moiety_check(law, table, n0, rec, path), part="d", conventions=rmeta["conventions"]))
    out.append(tagged(refusal_check(load_refusals(ctx.path("refusals"))), part="d"))
    return out


def need_arrays(rec: dict, names, where) -> list:
    absent = [n for n in names if n not in rec]
    if absent:
        raise MissingRecord(f"{where} lacks {absent}")
    return [np.asarray(rec[n]) for n in names]


def moiety_check(law: Law, table: ChannelTable, n0, rec: dict, where) -> CheckResult:
    """Every moiety over the finite places changes only by what held places exchange."""
    ec, row_event, counts = need_arrays(rec, ("event_channel", "row_event", "counts"), where)
    Wm = np.array(law.world.moiety_matrix(), dtype=np.int64)
    code_to_row = {c: j for j, c in enumerate(table.code)}
    nus = np.array([law.nu[st.name] for st in law.world.steps], dtype=np.int64)
    held = np.array([1 if law.nu_h[st.name] else 0 for st in law.world.steps])
    delta = np.zeros((len(ec) + 1, Wm.shape[0]), dtype=np.int64)
    bad_steps = set()
    for e, code in enumerate(ec):
        j = code_to_row[int(code)]
        r, s = table.step[j], table.sign[j]
        d = Wm @ (s * nus[r])
        if np.any(d) and not held[r]:
            bad_steps.add(law.world.steps[r].name)
        delta[e + 1] = delta[e] + d
    start = Wm @ np.asarray(n0, dtype=np.int64)
    problems = []
    for k, e in enumerate(np.asarray(row_event, dtype=np.int64)):
        got = Wm @ np.asarray(counts[k], dtype=np.int64)
        if not np.array_equal(got, start + delta[e]):
            problems.append(dict(row=k, moieties=got.tolist(), expected=(start + delta[e]).tolist()))
    return CheckResult("moieties_conserved", not problems and not bad_steps,
                       dict(moieties=law.world.moiety_names(), rows=int(len(row_event)), problems=problems[:5],
                            unbalanced_steps=sorted(bad_steps)))


def refusal_check(record: dict) -> CheckResult:
    expected = sorted(p.stem.replace(".world", "") for p in (DESIGN_DIR / "refusals").glob("*.world.json"))
    missing = [r for r in expected if r not in record]
    accepted = [r for r in expected if r in record and not record[r].get("refused")]
    return CheckResult("registered_refusals", not missing and not accepted,
                       dict(declarations=len(expected), missing=missing, accepted=accepted))


def registered_rows(events: int) -> list:
    """The ledger run's registered rows: every ``row_every_events`` events, and the last."""
    every = LEDGER_RUN["row_every_events"]
    return sorted(set(range(0, events + 1, every)) | {events})


def run_metas(paths, role: str) -> list:
    metas = [load_run(p)[0] for p in as_list(paths)]
    require_registered_pairs(metas, role)
    return metas


def row_5(ctx: Context) -> list:
    out = []
    run_metas(ctx.path("ledger_run"), "ledger_run")
    for path in as_list(ctx.path("ledger_run")):
        meta, rec, law, table = run_records(path)
        ec, row_event, counts, heat, work = need_arrays(
            rec, ("event_channel", "row_event", "counts", "heat_kT", "work_kT"), path)
        n0 = law.world.state_from(meta["initial_state"])
        if meta["world"] != LEDGER_RUN["world"] or law.world.state_from(meta["initial_state"]) != \
                registered_world(LEDGER_RUN["world"]).state_from(registered_world(LEDGER_RUN["world"]).initial_state):
            raise RecordFormatError(f"{path}: the ledger run must start {LEDGER_RUN['world']} from its registered state")
        out.append(CheckResult("registered_run_length", len(ec) == LEDGER_RUN["max_events"],
                               dict(events=int(len(ec)), registered=LEDGER_RUN["max_events"])))
        if [int(e) for e in row_event] != registered_rows(len(ec)):
            raise RecordFormatError(f"{path}: row_event {[int(e) for e in row_event][:6]}... is not the registered "
                                    f"rows (every {LEDGER_RUN['row_every_events']} events, and the last)")
        out.append(tagged(ledger.check_ledger(law, table, n0, ec, row_event, counts, heat, work),
                          conventions=meta["conventions"]))
    return out


def row_6(ctx: Context) -> list:
    out = []
    base = as_list(ctx.path("ledger_run"))
    rep = as_list(ctx.path("replay"))
    other = as_list(ctx.path("other_stream"))
    if not (len(base) == len(rep) == len(other)):
        raise RecordFormatError("ledger_run, replay and other_stream must list one run per probed pair, in order")
    for role, paths in (("ledger_run", base), ("replay", rep), ("other_stream", other)):
        run_metas(paths, role)
    for b, r, o in zip(base, rep, other):
        mb, ab, _, _ = run_records(b)
        mr, ar, _, _ = run_records(r)
        mo, ao, _, _ = run_records(o)
        if mr["stream"] != mb["stream"] or mr["conventions"] != mb["conventions"]:
            out.append(CheckResult("bitwise_replay", False, dict(problem="the replay declares another identity")))
        else:
            out.append(tagged(streams.check_replay(ab, ar, ("event_channel", "event_time", "row_event", "counts",
                                                            "heat_kT", "work_kT")), conventions=mb["conventions"]))
        if mo["stream"] == mb["stream"]:
            out.append(CheckResult("distinct_streams", False, dict(problem="other_stream declares the same identity")))
        else:
            out.append(tagged(streams.check_distinct_streams(ab, ao), conventions=mb["conventions"]))
    return out


ROW_FUNCTIONS = {"OL1-1": row_1, "OL1-2": row_2, "OL1-3": row_3, "OL1-4": row_4, "OL1-5": row_5, "OL1-6": row_6}


def run_rows(roles: dict, rows=None) -> tuple[int, dict]:
    ctx = Context(roles)
    report, status = {}, 0
    for row in rows or list(ROWS):
        title, _needs = ROWS[row]
        try:
            results = ROW_FUNCTIONS[row](ctx)
            passed = all(r.passed for r in results) and bool(results)
            report[row] = dict(title=title, passed=passed, checks=[r.as_dict() for r in results])
            if not passed:
                status = max(status, 1)
        except (MissingRecord, RecordFormatError) as exc:
            report[row] = dict(title=title, passed=False, missing_or_malformed=str(exc))
            status = 2
    return status, report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="validation.ool.references.harness")
    sub = ap.add_subparsers(dest="cmd", required=True)
    mp = sub.add_parser("make-probes")
    mp.add_argument("out_dir")
    rp = sub.add_parser("run")
    rp.add_argument("--roles", required=True)
    rp.add_argument("--rows", default=None)
    rp.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    if args.cmd == "make-probes":
        print(make_probes(args.out_dir))
        return 0
    roles = json.loads(Path(args.roles).read_text())
    rows = args.rows.split(",") if args.rows else None
    status, report = run_rows(roles, rows)
    text = json.dumps(jsonable(dict(status=status, rows=report)), indent=1)
    if args.out:
        Path(args.out).write_text(text)
    for row, r in report.items():
        print(f"{row}: {'pass' if r['passed'] else 'FAIL'} - {r['title']}"
              + (f" [{r['missing_or_malformed']}]" if "missing_or_malformed" in r else ""))
    return status


if __name__ == "__main__":
    sys.exit(main())
