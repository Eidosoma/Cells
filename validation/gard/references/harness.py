"""Comparison harness: runs every reference against an engine's saved records.

It is written without the engine. Every input is a saved record, and any record a row
needs that is absent fails that row loudly, naming what is missing. Exit status: 0 when
every requested row passes; 1 when a row fails; 2 when a row cannot run because a record
is missing or malformed.

Usage:
    python -m validation.gard.references.harness make-probes OUT_DIR
    python -m validation.gard.references.harness run --roles ROLES.json [--rows 1,2,...] [--out REPORT.json]

ROLES.json maps each role to a path, or a list of paths for ``beta0_ensemble``,
``restart`` and ``branches``. Run roles are run bundles (``records.load_bundle``).
Probe roles are directories holding ``probe.json``, ``probe.npz`` and ``manifest.json``.
The engine side writes them from the inputs that ``make-probes`` writes; README.md lists
every role and record.
"""

from __future__ import annotations

import argparse
import functools
import json
import math
import sys
from pathlib import Path

import numpy as np

from . import closed_world, conservation, detailed_balance, exchange_law, fission_partition, ledger
from . import observers, ssa_oracle, streams, time_rescaling
from .common import CheckResult, jsonable
from .kernels import (PAIR_CONSISTENT, SINGLE_EVENT, ExchangeLaw, HeldReservoir, PREPRINT, canonical_form,
                      gard_beta)
from .records import Bundle, MissingRecord, RecordFormatError, load_bundle
from .ssa_oracle import ChannelTable, ConventionMissing

KERNEL_PROBE_SEED = 20261117
OBSERVER_PROBE_SEED = 20261118
CLOSED_WORLD_CONFIGS = (
    dict(name="p2_beta11", beta=[[50.0, 0.0], [0.0, 0.0]], M=(8, 8), theta=0.05),
    dict(name="p2_beta12", beta=[[0.0, 50.0], [0.0, 0.0]], M=(8, 8), theta=0.05),
    dict(name="three_types", beta=None, M=(4, 4, 4), theta=0.1),
)
ROWS = {
    1: ("The exchange law (mean field)", ("beta0_ensemble",)),
    2: ("Catalysis is kinetic only", ("rescale_beta0", "rescale_betac")),
    3: ("Local detailed balance (pair-consistent)", ("kernel_probe",)),
    4: ("The stationary law in a closed world", ("closed_world",)),
    5: ("The SSA is exact", ("lineage", "lineage_diagnostic", "beta0_ensemble")),
    6: ("The fission partition", ("partition_probe",)),
    7: ("Conservation", ("lineage", "lineage_single_event")),
    8: ("The thermodynamic ledger", ("lineage", "lineage_single_event")),
    9: ("Streams", ("lineage", "replay", "batched", "restart", "branches")),
    10: ("Observers", ("lineage", "observer_probe", "f12_table")),
}
MULTI_ROLES = ("beta0_ensemble", "restart", "branches")


# ------------------------------------------------------------------ probe inputs

def three_type_beta() -> np.ndarray:
    return gard_beta(3, np.random.default_rng(KERNEL_PROBE_SEED + 3))


@functools.lru_cache(maxsize=1)
def probe_input_arrays() -> dict:
    """The registered probe inputs, regenerated deterministically from their seeds (read-only)."""
    rng = np.random.default_rng(KERNEL_PROBE_SEED)
    G = PREPRINT["n_types"]
    beta = gard_beta(G, rng)
    states = detailed_balance.make_probe_states(rng, 200, G)
    out = {"kernel_probe_inputs": dict(beta=beta, states=states, k_join=np.full(G, PREPRINT["k_join"]),
                                       k_leave=np.full(G, PREPRINT["k_leave"]), rho=np.full(G, PREPRINT["rho"]))}
    for cfg in CLOSED_WORLD_CONFIGS:
        b = np.asarray(cfg["beta"]) if cfg["beta"] is not None else three_type_beta()
        n = len(cfg["M"])
        out[f"closed_world_{cfg['name']}_inputs"] = dict(
            beta=b, states=np.asarray(closed_world.closed_states(cfg["M"]), dtype=np.int64), M=np.asarray(cfg["M"]),
            theta=np.float64(cfg["theta"]), k_join=np.ones(n), k_leave=np.ones(n), rho=np.ones(n))
    out["observer_probe_inputs"] = observers.make_observer_probes(np.random.default_rng(OBSERVER_PROBE_SEED))
    return out


def make_probe_inputs(out_dir: str | Path) -> Path:
    """Write the registered probe inputs the engine side evaluates."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=False)
    for name, arrays in probe_input_arrays().items():
        np.savez(out / f"{name}.npz", **arrays)
    (out / "partition_probe_inputs.json").write_text(json.dumps(dict(
        parent=fission_partition.REGISTERED_PARENT.tolist(), splits=fission_partition.REGISTERED_FISSIONS,
        rules=[dict(partition="exact_fraction", fraction=0.5), dict(partition="binomial", p=0.5)]), indent=1))
    (out / "README.txt").write_text(
        "Registered probe inputs for the GARD component references (see README.md in the package).\n")
    return out


# ------------------------------------------------------------------ role loading

def load_probe(path: str | Path) -> tuple[dict, dict]:
    p = Path(path)
    missing = [f for f in ("probe.json", "probe.npz", "manifest.json") if not (p / f).is_file()]
    if missing:
        raise MissingRecord(f"probe {p} lacks {missing}")
    meta = json.loads((p / "probe.json").read_text())
    with np.load(p / "probe.npz", allow_pickle=False) as npz:
        arrays = {k: npz[k] for k in npz.files}
    return meta, arrays


def require(arrays: dict, names, where: str) -> list[np.ndarray]:
    missing = [n for n in names if n not in arrays]
    if missing:
        raise MissingRecord(f"{where} lacks {missing}")
    return [np.asarray(arrays[n]) for n in names]


class Context:
    def __init__(self, roles: dict):
        self.roles = roles
        self._cache: dict = {}

    def path(self, role: str):
        if role not in self.roles:
            raise MissingRecord(f"role {role!r} was not supplied")
        return self.roles[role]

    def bundle(self, role: str) -> Bundle:
        if role not in self._cache:
            self._cache[role] = load_bundle(self.path(role))
        return self._cache[role]

    def bundles(self, role: str) -> list[Bundle]:
        key = ("many", role)
        if key not in self._cache:
            paths = self.path(role)
            paths = [paths] if isinstance(paths, str) else list(paths)
            if not paths:
                raise MissingRecord(f"role {role!r} lists no bundles")
            self._cache[key] = [load_bundle(p) for p in paths]
        return self._cache[key]

    def probe(self, role: str) -> tuple[dict, dict]:
        return load_probe(self.path(role))


def law_of(bundle: Bundle) -> ExchangeLaw:
    w = bundle.world
    return ExchangeLaw(w.beta, w.k_join, w.k_leave, HeldReservoir(w.rho), canonical_form(bundle.run.form),
                       w.boundary)


def lineage_arrays(b: Bundle) -> dict:
    """The lineage records, with event codes read through the declared channel table."""
    names = ("assembly_count", "joined_total", "left_total", "discarded_total", "exchange_heat_kT",
             "fission_work_kT", "discarded_free_energy_kT", "log_weight", "ledger_residual_kT", "row_event",
             "fission_split", "fission_followed", "fission_similarity", "event_channel", "events_per_growth",
             "event_time")
    out = dict(zip(names, b.require(*names)))
    out["event_channel"] = canonical_events(b)
    return out


def check_founder_declared(b: Bundle) -> None:
    if b.run.founder != "world":
        raise RecordFormatError(f"{b.path}: run founder is {b.run.founder!r}, expected 'world'")
    if b.run.world_id and b.world.world_id and b.run.world_id != b.world.world_id:
        raise RecordFormatError(f"{b.path}: run names world {b.run.world_id}, world record is {b.world.world_id}")


def channel_table(b: Bundle) -> ChannelTable:
    """The run's declared channel table; a run without one is refused."""
    try:
        return ChannelTable.from_declared(b.run.channels, b.world.n_types, b.world.type_names)
    except ConventionMissing as exc:
        raise MissingRecord(f"{b.path}/run.json: {exc}") from exc


def canonical_events(b: Bundle) -> np.ndarray:
    (codes,) = b.require("event_channel")
    try:
        return channel_table(b).canonical(codes)
    except ConventionMissing as exc:
        raise RecordFormatError(f"{b.path}: {exc}") from exc


def time_unit(b: Bundle):
    """The run's time unit; the world's and the run's declarations must agree when both exist."""
    w_unit = (b.world.units or {}).get("time") if isinstance(b.world.units, dict) else None
    r_unit = (b.run.time or {}).get("unit") if isinstance(b.run.time, dict) else None
    if w_unit is not None and r_unit is not None and w_unit != r_unit:
        raise RecordFormatError(f"{b.path}: world time unit {w_unit!r} but run time unit {r_unit!r}")
    return w_unit if w_unit is not None else r_unit


def same_units(*bundles: Bundle) -> None:
    units = {time_unit(b) for b in bundles}
    if len(units) > 1:
        raise RecordFormatError(f"compared runs declare different time units: {sorted(map(str, units))}")


# ------------------------------------------------------------------ rows

def row1(ctx: Context) -> list[CheckResult]:
    runs = ctx.bundles("beta0_ensemble")
    times, counts, w = ensemble_counts(runs)
    k_join, k_leave = uniform_constants(w)
    return [exchange_law.check_ensemble_means(times, counts, w.founder, k_join, k_leave, w.rho)]


def uniform_constants(w) -> tuple[float, float]:
    if np.ptp(w.k_join) != 0 or np.ptp(w.k_leave) != 0:
        raise RecordFormatError("the beta = 0 ensemble needs uniform k_join and k_leave")
    return float(w.k_join[0]), float(w.k_leave[0])


def ensemble_counts(runs: list[Bundle]):
    """Counts [run, time, type] at the registered times from each run's event trace."""
    times = np.asarray(exchange_law.REGISTERED_DESIGN["times"], dtype=np.float64)
    w0 = runs[0].world
    same_units(*runs)
    if np.any(w0.beta != 0):
        raise RecordFormatError("the beta0_ensemble world must have beta = 0")
    out = np.zeros((len(runs), times.size, w0.n_types), dtype=np.int64)
    for r, b in enumerate(runs):
        w = b.world
        if w.world_id != w0.world_id:
            raise RecordFormatError(f"{b.path}: ensemble runs must share one world")
        (et,) = b.require("event_time")
        ch = canonical_events(b)
        ft = b.optional("fission_time")
        if ft is not None and ft.size and ft[0] <= times[-1]:
            raise RecordFormatError(f"{b.path}: a fission at t = {ft[0]} precedes the last registered time")
        t_end = b.run_raw.get("t_end")
        reached = (et.size and et[-1] >= times[-1]) or (t_end is not None and float(t_end) >= times[-1])
        if not reached:
            raise RecordFormatError(f"{b.path}: cannot tell that the run reached t = {times[-1]} "
                                    "(no later event and no declared t_end)")
        out[r] = counts_at_times(w.founder, et, ch, times)
    return times, out, w0


def counts_at_times(founder, event_time, event_channel, times) -> np.ndarray:
    """Composition [time, type] after every event with event_time <= t, from the trace."""
    founder = np.asarray(founder, dtype=np.int64)
    ch = np.asarray(event_channel, dtype=np.int64)
    delta = np.zeros((ch.size + 1, founder.size), dtype=np.int64)
    if ch.size:
        delta[np.arange(1, ch.size + 1), np.abs(ch) - 1] = np.sign(ch)
    path = founder[None, :] + np.cumsum(delta, axis=0)
    idx = np.searchsorted(np.asarray(event_time), np.asarray(times), side="right")
    return path[idx]


def row2(ctx: Context) -> list[CheckResult]:
    b0, bc = ctx.bundle("rescale_beta0"), ctx.bundle("rescale_betac")
    if np.any(b0.world.beta != 0):
        raise RecordFormatError("rescale_beta0 must have beta = 0")
    c_vals = np.unique(bc.world.beta)
    if c_vals.size != 1 or c_vals[0] <= 0:
        raise RecordFormatError("rescale_betac must have one uniform positive beta")
    if not np.array_equal(b0.world.founder, bc.world.founder):
        raise RecordFormatError("the rescaling pair must share a founder")
    if json.dumps(b0.run.stream, sort_keys=True) != json.dumps(bc.run.stream, sort_keys=True):
        raise RecordFormatError("the rescaling pair must share its stream keys")
    same_units(b0, bc)
    t0, s0, f0 = b0.require("event_time", "fission_split", "fission_time")
    tc, sc, fc = bc.require("event_time", "fission_split", "fission_time")
    ch0, chc = canonical_events(b0), canonical_events(bc)
    res = [time_rescaling.check_time_rescaling(ch0, t0, chc, tc, float(c_vals[0]), s0, sc, f0, fc)]
    res.append(time_rescaling.uniform_beta_identity_exact(3, int(c_vals[0]) if float(c_vals[0]).is_integer()
                                                          else 1, 5))
    return res


def row3(ctx: Context) -> list[CheckResult]:
    meta, arr = ctx.probe("kernel_probe")
    beta, states, kj, kl, rho = require(arr, ("beta", "states", "k_join", "k_leave", "rho"), "kernel_probe")
    reg = _registered_inputs()["kernel"]
    if not (np.array_equal(beta, reg["beta"]) and np.array_equal(states, reg["states"])):
        raise RecordFormatError("kernel_probe was not evaluated on the registered inputs")
    out = []
    for form in (PAIR_CONSISTENT, SINGLE_EVENT):
        tag = form.replace("-", "_")
        join, leave, leave_up = require(arr, (f"join_{tag}", f"leave_{tag}", f"leave_up_{tag}"), "kernel_probe")
        verdicts = meta.get("check_verdict")
        if not isinstance(verdicts, dict) or form not in verdicts:
            raise MissingRecord(f"kernel_probe/probe.json lacks check_verdict[{form!r}]")
        law = ExchangeLaw(beta, kj, kl, HeldReservoir(rho), form)
        out.append(detailed_balance.check_local_detailed_balance(
            law, states, dict(join=join, leave=leave, leave_up=leave_up), verdicts[form]))
    for form in (PAIR_CONSISTENT, SINGLE_EVENT):
        out.append(detailed_balance.check_p1_square(form))
    return out


def row4(ctx: Context) -> list[CheckResult]:
    meta, arr = ctx.probe("closed_world")
    out = []
    for cfg in CLOSED_WORLD_CONFIGS:
        reg = _registered_inputs()[f"closed_{cfg['name']}"]
        for form in (PAIR_CONSISTENT, SINGLE_EVENT):
            tag = f"{cfg['name']}_{form.replace('-', '_')}"
            states, join, leave = require(arr, (f"states_{tag}", f"join_{tag}", f"leave_{tag}"), "closed_world")
            if not np.array_equal(states, reg["states"]):
                raise RecordFormatError(f"closed_world {tag} was not evaluated on the registered states")
            cj, cl = closed_world.held_to_closed(states, join, leave, reg["rho"], reg["k_join"], reg["k_leave"],
                                                 float(reg["theta"]), tuple(reg["M"]))
            out.append(closed_world.check_closed_table(states, cj, cl, float(reg["theta"]), tuple(reg["M"]), form))
    return out


def row5(ctx: Context) -> list[CheckResult]:
    b, bd = ctx.bundle("lineage"), ctx.bundle("lineage_diagnostic")
    out = []
    conv_raw = bd.run.ssa_convention
    try:
        ssa_oracle.SSAConvention.from_declared(conv_raw)
    except ssa_oracle.ConventionMissing as exc:
        raise MissingRecord(f"{bd.path}: {exc}") from exc
    same_units(b, bd)
    ch, et = b.require("event_channel", "event_time")
    chd, etd, u, split, fol, epg = bd.require("event_channel", "event_time", "event_uniforms", "fission_split",
                                              "fission_followed", "events_per_growth")
    unchanged = bool(np.array_equal(ch, chd) and np.array_equal(et, etd))
    out.append(CheckResult("diagnostic_mode_leaves_events_unchanged", unchanged, dict(events=int(ch.size))))
    w = bd.world
    out.append(ssa_oracle.check_crn_replay(law_of(bd), w.founder, u, chd, etd, w.fission_mass, split, fol, epg,
                                           channel_table(bd), w.event_guard))
    runs = ctx.bundles("beta0_ensemble")
    times, counts, w0 = ensemble_counts(runs)
    k_join, k_leave = uniform_constants(w0)
    out.append(ssa_oracle.check_birth_death_ensemble(times, counts.sum(axis=2), int(w0.founder.sum()),
                                                     k_join * float(w0.rho.sum()), k_leave))
    return out


def row6(ctx: Context) -> list[CheckResult]:
    meta, arr = ctx.probe("partition_probe")
    out = []
    for rule in ("exact_fraction", "binomial"):
        parents, splits = require(arr, (f"parents_{rule}", f"splits_{rule}"), "partition_probe")
        if not np.all(parents == fission_partition.REGISTERED_PARENT[None, :]):
            raise RecordFormatError(f"partition_probe {rule}: parents differ from the registered parent")
        out.append(fission_partition.check_partition_records(parents, splits, rule))
    for P, rule in (([3, 2, 2, 1], "exact_fraction"), ([3, 2, 1], "binomial")):
        out.append(fission_partition.check_enumeration(P, rule))
    return out


def lineage_pair(ctx: Context) -> tuple[Bundle, Bundle]:
    a, s = ctx.bundle("lineage"), ctx.bundle("lineage_single_event")
    for b in (a, s):
        check_founder_declared(b)
        if b.run.mode != "single_lineage":
            raise RecordFormatError(f"{b.path}: mode {b.run.mode!r}; only single_lineage is covered")
    if canonical_form(a.run.form) != PAIR_CONSISTENT or canonical_form(s.run.form) != SINGLE_EVENT:
        raise RecordFormatError("lineage must be pair-consistent and lineage_single_event single-event")
    if a.world.world_id != s.world.world_id or not np.array_equal(a.world.founder, s.world.founder):
        raise RecordFormatError("the two forms must share one world and one founder")
    same_units(a, s)
    return a, s


def row7(ctx: Context) -> list[CheckResult]:
    out = []
    for b in lineage_pair(ctx):
        r = lineage_arrays(b)
        res = conservation.check_conservation(b.world.founder, r["assembly_count"], r["joined_total"],
                                              r["left_total"], r["discarded_total"], r["fission_split"],
                                              r["fission_followed"], r["event_channel"], r["events_per_growth"],
                                              r["row_event"])
        res.detail["form"] = b.run.form
        out.append(res)
    return out


def row8(ctx: Context) -> list[CheckResult]:
    out = []
    for b in lineage_pair(ctx):
        r = lineage_arrays(b)
        out.append(ledger.check_ledger(law_of(b), r["assembly_count"], r["exchange_heat_kT"], r["fission_work_kT"],
                                       r["discarded_free_energy_kT"], r["log_weight"], r["ledger_residual_kT"],
                                       r["fission_split"], r["fission_followed"], r["row_event"],
                                       r["event_channel"], b.world.founder))
    return out


def row9(ctx: Context) -> list[CheckResult]:
    a, rep, bat = ctx.bundle("lineage"), ctx.bundle("replay"), ctx.bundle("batched")
    out = [streams.check_bitwise_replay(a.arrays, rep.arrays, a.run_raw, rep.run_raw),
           streams.check_batch_invariance(a.arrays, bat.arrays, a.run_raw, bat.run_raw)]
    for rb in ctx.bundles("restart"):
        spec = rb.run_raw.get("restart")
        if not isinstance(spec, dict) or not {"row", "event", "fission"} <= set(spec):
            raise MissingRecord(f"{rb.path}/run.json lacks restart.row, restart.event and restart.fission")
        out.append(streams.check_restart(a.arrays, rb.arrays, int(spec["row"]), int(spec["event"]),
                                         int(spec["fission"])))
    branches = ctx.bundles("branches")
    for br in branches:
        br.require("event_channel")
    out.append(streams.check_branch_independence([br.arrays for br in branches], [br.run.stream for br in branches]))
    return out


def row10(ctx: Context) -> list[CheckResult]:
    b = ctx.bundle("lineage")
    r = lineage_arrays(b)
    count = r["assembly_count"][:, :, 0]
    F = r["fission_split"].shape[0]
    parents = count[1:1 + 2 * F:2]
    daughters = count[2:2 + 2 * F:2]
    out = [observers.check_fission_similarity(parents, r["fission_split"], r["fission_followed"], daughters,
                                              r["fission_similarity"])]
    meta, arr = ctx.probe("observer_probe")
    P, D, H, I = require(arr, ("probe_parent", "probe_daughter", "H", "inherited"), "observer_probe")
    reg = _registered_inputs()["observer"]
    if not (np.array_equal(P, reg["probe_parent"]) and np.array_equal(D, reg["probe_daughter"])):
        raise RecordFormatError("observer_probe was not evaluated on the registered probes")
    out.append(observers.check_observer_probes(P, D, H, I))
    meta, arr = ctx.probe("f12_table")
    (table,) = require(arr, ("verdicts",), "f12_table")
    if "bit_order" not in meta:
        raise MissingRecord("f12_table/probe.json lacks bit_order")
    out.append(observers.check_f12_table(table, meta["bit_order"]))
    return out


RUNNERS = {1: row1, 2: row2, 3: row3, 4: row4, 5: row5, 6: row6, 7: row7, 8: row8, 9: row9, 10: row10}
_REGISTERED: dict = {}


def _registered_inputs() -> dict:
    """The registered probe inputs, computed once per process (no files written)."""
    if not _REGISTERED:
        arrays = probe_input_arrays()
        _REGISTERED.update(kernel=arrays["kernel_probe_inputs"], observer=arrays["observer_probe_inputs"],
                           **{f"closed_{c['name']}": arrays[f"closed_world_{c['name']}_inputs"]
                              for c in CLOSED_WORLD_CONFIGS})
    return _REGISTERED


def run_rows(roles: dict, rows=None) -> dict:
    rows = sorted(ROWS) if rows is None else sorted(rows)
    ctx = Context(roles)
    report = {"rows": {}, "status": 0}
    for n in rows:
        title, needs = ROWS[n]
        entry = {"title": title, "roles": list(needs)}
        try:
            results = RUNNERS[n](ctx)
            entry["checks"] = [r.as_dict() for r in results]
            entry["passed"] = all(r.passed for r in results)
            if not entry["passed"]:
                report["status"] = max(report["status"], 1)
        except (MissingRecord, RecordFormatError, ConventionMissing, FileNotFoundError) as exc:
            entry["passed"] = False
            entry["error"] = f"{type(exc).__name__}: {exc}"
            report["status"] = 2
        report["rows"][str(n)] = entry
    return jsonable(report)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m validation.gard.references.harness")
    sub = ap.add_subparsers(dest="cmd", required=True)
    mp = sub.add_parser("make-probes")
    mp.add_argument("out_dir")
    rp = sub.add_parser("run")
    rp.add_argument("--roles", required=True)
    rp.add_argument("--rows", default="all")
    rp.add_argument("--out")
    args = ap.parse_args(argv)
    if args.cmd == "make-probes":
        print(make_probe_inputs(args.out_dir))
        return 0
    roles = json.loads(Path(args.roles).read_text())
    rows = None if args.rows == "all" else [int(v) for v in args.rows.split(",")]
    report = run_rows(roles, rows)
    text = json.dumps(report, indent=1, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text)
    for n, entry in report["rows"].items():
        verdict = "PASS" if entry["passed"] else ("MISSING" if "error" in entry else "FAIL")
        print(f"row {n:>2} {verdict:7} {entry['title']}" + (f"  [{entry['error']}]" if "error" in entry else ""))
    return int(report["status"])


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
