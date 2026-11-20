"""The fuel rows OL4-1 to OL4-9, run against saved records in the canonical layout.

    python -m validation.ool.references.fuel.harness --records DIR [--rows OL4-1,OL4-5] [--out verdict.json]

Exit status: 0 every requested row passed; 1 a row failed; 2 a record is missing or malformed.

**Canonical layout** (an adapter writes it from the engine's own records once the family's format
for fuel exists; ``standin`` writes it directly). Every record directory ends with
``manifest.json``, written last.
- ``kernel/<world>/``: ``probe.json`` {world, conventions, steps, places}; ``probe.npz`` with
  ``input_states`` [S, D] (the registered probe states, echoed bitwise), ``a_plus``, ``a_minus``
  [S, R]. Worlds: ``ol4_fd_kernel``, ``ol4_fd_heldB``, ``ol4_fd_d0``, ``ol4_fd_null``,
  ``ol4_fd_finite``.
- ``tables/<world>/``: the same arrays over every state of a finite world (its registered state
  list). Worlds: the ``ol4_fd_ness`` family, the ``ol4_fd_edge`` pair and ``ol4_fd_finite``.
- ``vkernel/<world>/`` and ``vtables/<world>/`` (V1): ``probe.json`` {world, steps}; ``probe.npz``
  with ``input_states`` [S, 3 parts flattened: membrane, lumen, pool], ``a_plus``, ``a_minus``,
  ``lyses_plus``, ``lyses_minus`` [S, C] over every declared step (pool steps included).
- ``runs/<run>/``: ``run.json`` {world, conventions, ssa, channels, stream, initial_state,
  end_reason}; ``records.npz`` with ``event_time``, ``event_channel``, ``row_event``, ``counts``,
  ``heat_kT``, ``work_kT`` and ``supplied`` [rows, H] (``ledger`` docstring).
- ``refusals/refusals.json``: {declaration id: {refused, message}}.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

from ..common import CheckResult, MissingRecord, RecordFormatError, jsonable
from ..records import load_probe, load_refusals, load_run
from ..ssa_oracle import ChannelTable
from ..world import Conventions
from . import bistability as BI
from . import design as DS
from . import kernel as K
from . import ledger as LG
from . import registered as R
from . import stationary as ST
from . import vesicle as V
from .design import ROWS
from .law import FuelLaw



def _phys(meta: dict) -> Conventions:
    c = Conventions.from_declared(meta.get("conventions"))
    if (c.condensed_measure, c.last_molecule) != ("multinomial", "kept"):
        raise RecordFormatError(f"the fuel references probe (multinomial, kept) only, not {c.as_dict()}")
    return c


def _echo(meta: dict, arrays: dict, world_id: str, expected: np.ndarray, where: str) -> None:
    if meta.get("world") != world_id:
        raise RecordFormatError(f"{where}: world {meta.get('world')!r}, {world_id!r} expected")
    w = R.registered_world(world_id)
    if list(meta["steps"]) != [st.name for st in w.steps] or list(meta["places"]) != [p.name for p in w.finite]:
        raise RecordFormatError(f"{where}: step or place order differs from the registered world")
    got = np.asarray(arrays.get("input_states"))
    if got.shape != expected.shape or not np.array_equal(got, expected):
        raise RecordFormatError(f"{where}: the echoed input_states differ from the registered states")
    for k in ("a_plus", "a_minus"):
        if k not in arrays or np.shape(arrays[k]) != (len(expected), len(w.steps)):
            raise RecordFormatError(f"{where}: {k} missing or of the wrong shape")


def _probe(root: Path, sub: str, world_id: str, states: np.ndarray):
    meta, arr = load_probe(root / sub / world_id)
    _phys(meta)
    _echo(meta, arr, world_id, states, f"{sub}/{world_id}")
    return arr


# ---------------------------------------------------------------------------- rows

def row_kernel(root: Path) -> list:
    out = []
    for wid in DS.KERNEL_WORLDS:
        states, cycles = DS.kernel_inputs(wid)
        arr = _probe(root, "kernel", wid, states)
        law = FuelLaw(R.registered_world(wid))
        res = K.check_kernel(law, states, arr["a_plus"], arr["a_minus"], cycles)
        for name, c in res.items():
            c.detail["world"] = wid
            out.append((name, c))
    return out


def row_vkernel(root: Path) -> list:
    out = []
    for wid in DS.V_KERNEL_WORLDS:
        w = DS.v_world(wid)
        states, cycles = DS.v_kernel_inputs(wid)
        tab = _vprobe(root, "vkernel", wid, w, states)
        law = V.FuelLaw2(w)
        out += [("identity", V.check_identity(law, states, tab)), ("forward_form", V.check_forward(law, states, tab)),
                ("cycle_drive", V.check_cycles(law, states, tab, cycles))]
    return out


def _vprobe(root: Path, sub: str, wid: str, w, states) -> dict:
    meta, arr = _load_vprobe(root / sub / wid)
    if meta.get("world") != wid or list(meta.get("steps", [])) != [c.id for c in w.steps]:
        raise RecordFormatError(f"{sub}/{wid}: world or step order differs from the registered one")
    flat = np.array([list(a) + list(b) + list(c) for a, b, c in states], dtype=np.int64)
    if not np.array_equal(np.asarray(arr.get("input_states")), flat):
        raise RecordFormatError(f"{sub}/{wid}: the echoed input_states differ from the registered states")
    for k in ("a_plus", "a_minus", "lyses_plus", "lyses_minus"):
        if k not in arr:
            raise MissingRecord(f"{sub}/{wid}: probe.npz lacks {k}")
    return arr


def _load_vprobe(d: Path):
    from ..records import MANIFEST

    if not (d / MANIFEST).is_file():
        raise MissingRecord(f"{d} has no {MANIFEST}")
    for f in ("probe.json", "probe.npz"):
        if not (d / f).is_file():
            raise MissingRecord(f"{d / f} is missing")
    meta = json.loads((d / "probe.json").read_text())
    with np.load(d / "probe.npz", allow_pickle=False) as z:
        return meta, {k: z[k] for k in z.files}


def row_ledger(root: Path, which: str) -> list:
    out = []
    for run_id, spec in DS.LEDGER_RUNS.items():
        meta, rec = load_run(root / "runs" / run_id)
        wid = spec["world"]
        if meta.get("world") != wid:
            raise RecordFormatError(f"runs/{run_id}: world {meta.get('world')!r}, {wid!r} expected")
        _phys(meta)
        if meta.get("end_reason") != "max_events":
            out.append(("end_reason", CheckResult("end_reason", False, dict(run=run_id, end_reason=meta.get("end_reason")))))
            continue
        w = R.registered_world(wid)
        law = FuelLaw(w)
        table = ChannelTable.from_declared(meta["channels"], law)
        for k in ("event_channel", "row_event", "counts", "heat_kT", "work_kT", "supplied"):
            if k not in rec:
                raise MissingRecord(f"runs/{run_id}: records.npz lacks {k}")
        if len(rec["event_channel"]) != spec["max_events"]:
            raise RecordFormatError(f"runs/{run_id}: {len(rec['event_channel'])} events, {spec['max_events']} registered")
        n0 = w.state_from(meta["initial_state"])
        if which == "closure":
            c = LG.check_closure(law, table, n0, rec["event_channel"], rec["row_event"], rec["counts"], rec["heat_kT"],
                                 rec["work_kT"])
            c.detail["run"] = run_id
            out.append(("closure", c))
            p = LG.check_payers(w, rec["row_event"], rec["supplied"], rec["work_kT"])
            p.detail["run"] = run_id
            out.append(("payers", p))
        else:
            tr = LG.supplied_from_trace(w, table, rec["event_channel"], rec["row_event"])
            m = LG.check_moieties(w, rec["counts"], rec["supplied"], trace_supplied=tr)
            m.detail["run"] = run_id
            out.append(("moieties", m))
    return out


def row_equilibrium(root: Path) -> list:
    out = []
    for wid in DS.EQUILIBRIUM_WORLDS:
        states = DS.closed_inputs(wid)
        arr = _probe(root, "tables", wid, states)
        law = FuelLaw(R.registered_world(wid))
        for name, c in ST.check_equilibrium(law, states, arr["a_plus"], arr["a_minus"]).items():
            c.detail["world"] = wid
            out.append((name, c))
    for wid in DS.V_CLOSED_WORLDS:
        w = DS.v_world(wid)
        states = DS.v_closed_inputs(wid)
        tab = _vprobe(root, "vtables", wid, w, states)
        for name, c in V.check_closed(V.FuelLaw2(w), states, tab).items():
            out.append((name, c))
    return out


def row_driven(root: Path, cache: dict) -> list:
    out = []
    for wid in DS.DRIVEN_WORLDS:
        states = DS.closed_inputs(wid)
        arr = _probe(root, "tables", wid, states)
        law = FuelLaw(R.registered_world(wid))
        ref = cache.setdefault(wid, ST.reference_solution(law, states))
        drive = DS.drive(wid)
        start = DS.SWITCH_START.get(wid)
        res = ST.check_driven(law, states, arr["a_plus"], arr["a_minus"], ref, drive, start=start)
        for name, c in res.items():
            c.detail["world"] = wid
            out.append((name, c))
    return out


def row_long_run(root: Path, cache: dict) -> list:
    spec = DS.NESS_RUN
    meta, rec = load_run(root / "runs" / spec["id"])
    wid = spec["world"]
    if meta.get("world") != wid:
        raise RecordFormatError(f"runs/{spec['id']}: world {meta.get('world')!r}, {wid!r} expected")
    _phys(meta)
    for k in ("event_channel", "event_time", "heat_kT", "row_event", "counts"):
        if k not in rec:
            raise MissingRecord(f"runs/{spec['id']}: records.npz lacks {k}")
    if meta.get("end_reason") != "max_events" or len(rec["event_channel"]) != spec["max_events"]:
        return [("long_run", CheckResult("long_run", False, dict(problem="the run is not the registered one",
                                                                  end_reason=meta.get("end_reason"),
                                                                  events=len(rec["event_channel"]))))]
    w = R.registered_world(wid)
    law = FuelLaw(w)
    states = DS.closed_inputs(wid)
    ref = cache.setdefault(wid, ST.reference_solution(law, states))
    table = ChannelTable.from_declared(meta["channels"], law)
    return [(k, c) for k, c in DS.long_run_checks(law, states, ref, table, w.state_from(meta["initial_state"]),
                                                   rec).items()]


def row_closed_form() -> list:
    out = []
    S = BI.sample()
    s = BI.check_sample(S)
    out.append(("closed_form_vs_raw_count", CheckResult("closed_form_vs_raw_count", s["disagreements"] == 0, s)))
    a = BI.check_A_star(S)
    out.append(("A_star_equivalence", CheckResult("A_star_equivalence", a["disagreements"] == 0, a)))
    n = BI.nulls(S)
    out.append(("nulls", CheckResult("nulls", all(v["failures"] == 0 for v in n.values()), n)))
    rep = BI.reproductions()
    ok = (abs(rep["c4"]["stable"][0] - 0.082) < 5e-4 and abs(rep["c4"]["gamma"][0] - 1.06) < 6e-3
          and abs(rep["c5"]["A_star_beta2_rho4"] - 6.6) < 0.05 and abs(rep["c5"]["A_star_beta64_rho4"] - 3.4) < 0.05
          and rep["zero_affinity_rho_quarter"] == "655680" and rep["feed_regime_rho_ninth"] == "8"
          and rep["constructed_c4b"]["gamma_even"] == "0" and rep["constructed_c4b"]["bistable"])
    out.append(("note_numbers", CheckResult("note_numbers_reproduced", ok, rep)))
    pred = DS.zero_affinity_predictions()
    ok = pred["ol4_fd_d0"]["bistable"] and not pred["ol4_fd_null"]["bistable"] and pred["ol4_fd_null"]["gamma_even"] > 0
    out.append(("zero_affinity_worlds", CheckResult("zero_affinity_world_predictions", ok, pred)))
    return out


def row_refusals(root: Path) -> list:
    rec = load_refusals(root / "refusals")
    out = []
    for rid in R.refusal_documents():
        r = rec.get(rid)
        if r is None:
            raise MissingRecord(f"refusals.json has no entry for {rid}")
        out.append((rid, CheckResult("refused", bool(r.get("refused")), dict(declaration=rid, message=r.get("message")))))
    return out


def run_rows(root, rows=None) -> dict:
    root = Path(root)
    rows = rows or list(ROWS)
    cache: dict = {}
    report = {}
    for row in rows:
        try:
            if row == "OL4-1":
                checks = [c for c in row_kernel(root) if c[0] in ("identity", "forward_form", "reverse_rates")]
                checks += [c for c in row_vkernel(root) if c[0] in ("identity", "forward_form")]
            elif row == "OL4-2":
                checks = [c for c in row_kernel(root) if c[0] in ("kolmogorov_squares", "cycle_drive")]
                checks += [c for c in row_vkernel(root) if c[0] == "cycle_drive"]
            elif row == "OL4-3":
                checks = row_ledger(root, "closure")
            elif row == "OL4-4":
                checks = row_ledger(root, "moieties")
            elif row == "OL4-5":
                checks = row_equilibrium(root)
            elif row == "OL4-6":
                checks = [c for c in row_driven(root, cache) if c[0] in ("stationary_law", "flux", "heat")]
                checks += row_long_run(root, cache)
            elif row == "OL4-7":
                checks = [c for c in row_driven(root, cache) if c[0] in ("modality", "switching")]
            elif row == "OL4-8":
                checks = row_closed_form()
            elif row == "OL4-9":
                checks = row_refusals(root)
            else:
                raise RecordFormatError(f"unknown row {row}")
            report[row] = dict(title=ROWS[row], passed=all(c.passed for _, c in checks) and bool(checks),
                               checks=[c.as_dict() for _, c in checks])
        except (MissingRecord, RecordFormatError) as exc:
            report[row] = dict(title=ROWS[row], passed=False, missing_or_malformed=str(exc), checks=[])
    return report


def exit_status(report: dict) -> int:
    if any(r.get("missing_or_malformed") for r in report.values()):
        return 2
    return 0 if all(r["passed"] for r in report.values()) else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--records", required=True)
    ap.add_argument("--rows", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    rep = run_rows(a.records, a.rows.split(",") if a.rows else None)
    text = json.dumps(jsonable(rep), indent=1)
    if a.out:
        Path(a.out).write_text(text)
    for row, r in rep.items():
        print(row, "PASS" if r["passed"] else ("MISSING" if r.get("missing_or_malformed") else "FAIL"),
              r.get("missing_or_malformed") or "")
    return exit_status(rep)


if __name__ == "__main__":
    sys.exit(main())
