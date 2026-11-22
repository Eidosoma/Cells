"""A stand-in record set for the fuel rows, written from the references themselves, for dry runs
of the harness: on it every row passes, and with a planted engine the rows that must see it fail.

- Kernel probes and tables come from the float path (``FloatRates``) for an honest engine and from
  the exact planted law (``law.FuelLaw``) for a planted one; vesicle tables from ``vesicle.table``.
- Runs come from the host direct method (``ssa_oracle.run_host_ssa``) on the engine's own rates
  (honest or planted), booked as that engine would book them: each event's heat
  ln a(drawn) - ln a(reverse at the new state), its work from its own reservoir work, and the
  reservoirs' net supply from the events.
- Refusals come from the reference's own parser.

    python -m validation.ool.references.fuel.standin --out DIR [--planted FORM] [--short]
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from ..common import RecordFormatError
from ..records import write_manifest
from ..ssa_oracle import (
    SELECT_FIRST_PREFIX_GT,
    TAU_NEG_LOG_U1,
    ChannelTable,
    FloatRates,
    run_host_ssa,
)
from . import design as DS
from . import ledger as LG
from . import registered as R
from . import stationary as ST
from . import vesicle as V
from .law import FUEL_PLANTED, PHYSICAL, FuelLaw, parse_fuel_world

SSA = {"tau": TAU_NEG_LOG_U1, "select": SELECT_FIRST_PREFIX_GT}


class LawRates:
    """``FloatRates``'s interface on an exact (possibly planted) law, for planted host runs."""

    def __init__(self, law: FuelLaw):
        self.law = law
        self.steps = law.world.steps
        self.nu = np.array([law.nu[st.name] for st in self.steps], dtype=np.int64)
        self.planted_bias = None

    def forward(self, r, n) -> float:
        return float(self.law.forward(self.steps[r], tuple(int(v) for v in n)))

    def reverse(self, r, n) -> float:
        return float(self.law.reverse(self.steps[r], tuple(int(v) for v in n)))

    def channel_rates(self, n, table: ChannelTable) -> np.ndarray:
        return np.array([self.forward(r, n) if s > 0 else self.reverse(r, n) for r, s in zip(table.step, table.sign)])


def _law(wid: str, planted: str | None) -> FuelLaw:
    return FuelLaw(R.registered_world(wid), PHYSICAL, planted=planted)


def _table_for(law: FuelLaw, states) -> dict:
    return ST.float_table(law, states)


def write_probe(out: Path, wid: str, states, planted: str | None = None) -> Path:
    out.mkdir(parents=True, exist_ok=False)
    law = _law(wid, planted)
    t = _table_for(law, states)
    w = law.world
    (out / "probe.json").write_text(json.dumps(dict(world=wid, conventions=PHYSICAL.as_dict(),
                                                    steps=[st.name for st in w.steps],
                                                    places=[p.name for p in w.finite]), indent=1))
    np.savez(out / "probe.npz", input_states=np.asarray(states, dtype=np.int64), a_plus=t["a_plus"],
             a_minus=t["a_minus"])
    write_manifest(out, ["probe.json", "probe.npz"])
    return out


def write_vprobe(out: Path, wid: str, states, planted: str | None = None) -> Path:
    out.mkdir(parents=True, exist_ok=False)
    w = DS.v_world(wid)
    t = V.table(V.FuelLaw2(w, planted=planted), states)
    flat = np.array([list(a) + list(b) + list(c) for a, b, c in states], dtype=np.int64)
    (out / "probe.json").write_text(json.dumps(dict(world=wid, steps=[c.id for c in w.steps]), indent=1))
    np.savez(out / "probe.npz", input_states=flat, **t)
    write_manifest(out, ["probe.json", "probe.npz"])
    return out


def host_run(wid: str, spec: dict, planted: str | None = None, world=None) -> dict:
    """A host run of a registered world (or of ``world``) with its booking, as an engine with
    ``planted`` would book it."""
    if world is None:
        law, honest = _law(wid, planted), _law(wid, None)
    else:
        law, honest = FuelLaw(world, PHYSICAL, planted=planted), FuelLaw(world, PHYSICAL)
    w = law.world
    rates = FloatRates(honest) if planted is None else LawRates(law)
    table = ChannelTable.default(honest)
    n0 = w.state_from(w.initial_state)
    run = run_host_ssa(rates, table, n0, t_end=spec["t_end"], rng=np.random.default_rng(spec["seed"]),
                       max_events=spec["max_events"])
    E = len(run["event_channel"])
    # the engine's own booking: heat from its own rates, work from its own reservoir work
    nu = rates.nu
    n = np.array(n0, dtype=np.int64)
    q, wk = np.zeros(E), np.zeros(E)
    work = [law.reservoir_work(st) for st in w.steps]
    if planted == "no_reservoir_work":
        work = [0.0] * len(work)
    elif planted == "work_sign":
        work = [-x for x in work]
    code_row = {c: j for j, c in enumerate(table.code)}
    states = [n.copy()]
    for e, code in enumerate(run["event_channel"]):
        j = code_row[int(code)]
        r, s = table.step[j], table.sign[j]
        p = n + s * nu[r]
        if s > 0:
            a, b = rates.forward(r, n), rates.reverse(r, p)
        else:
            a, b = rates.reverse(r, n), rates.forward(r, p)
        q[e] = math.log(a) - math.log(b)
        wk[e] = s * work[r]
        n = p
        states.append(n.copy())
    rows = sorted(set(list(range(0, E + 1, spec["row_every"])) + [E]))
    supplied = LG.supplied_from_trace(w, table, run["event_channel"], rows)
    return dict(run=run, table=table, rows=np.asarray(rows, dtype=np.int64), counts=np.asarray(states)[rows],
                heat=np.concatenate([[0.0], np.cumsum(q)])[rows], work=np.concatenate([[0.0], np.cumsum(wk)])[rows],
                supplied=supplied, world=w)


def write_run(out: Path, run_id: str, spec: dict, planted: str | None = None) -> Path:
    out.mkdir(parents=True, exist_ok=False)
    h = host_run(spec["world"], spec, planted)
    w, table = h["world"], h["table"]
    channels = [dict(step=w.steps[r].name, direction=int(s), code=int(c))
                for r, s, c in zip(table.step, table.sign, table.code)]
    (out / "run.json").write_text(json.dumps(dict(world=spec["world"], conventions=PHYSICAL.as_dict(), ssa=SSA,
                                                  channels=channels, stream=f"standin-{spec['seed']}",
                                                  initial_state=w.initial_state,
                                                  end_reason=h["run"]["end_reason"]), indent=1))
    np.savez(out / "records.npz", event_time=h["run"]["event_time"], event_channel=h["run"]["event_channel"],
             event_uniforms=h["run"]["event_uniforms"], row_event=h["rows"], counts=h["counts"], heat_kT=h["heat"],
             work_kT=h["work"], supplied=h["supplied"])
    write_manifest(out, ["run.json", "records.npz"])
    return out


def write_refusals(out: Path, accept: tuple = ()) -> Path:
    out.mkdir(parents=True, exist_ok=False)
    rec = {}
    for rid, doc in R.refusal_documents().items():
        if rid in accept:
            rec[rid] = dict(refused=False, message="")
            continue
        try:
            parse_fuel_world(doc)
            rec[rid] = dict(refused=False, message="")
        except RecordFormatError as exc:
            rec[rid] = dict(refused=True, message=str(exc))
    (out / "refusals.json").write_text(json.dumps(rec, indent=1))
    write_manifest(out, ["refusals.json"])
    return out


def build(out_dir, planted: str | None = None, *, long_events: int | None = None, rows=None) -> Path:
    """Every record the rows read; ``planted`` applies to the engine's rates everywhere it can."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=False)
    rows = set(rows or DS.ROWS)
    fp = planted if planted in FUEL_PLANTED + ("at_state_factor", "forward_only_catalysis") else None
    vp = planted if planted in V.PLANTED_V else None
    if rows & {"OL4-1", "OL4-2"}:
        for wid in DS.KERNEL_WORLDS:
            write_probe(out / "kernel" / wid, wid, DS.kernel_inputs(wid)[0], fp)
        for wid in DS.V_KERNEL_WORLDS:
            write_vprobe(out / "vkernel" / wid, wid, DS.v_kernel_inputs(wid)[0], vp)
    if rows & {"OL4-5", "OL4-6", "OL4-7"}:
        for wid in sorted(set(DS.EQUILIBRIUM_WORLDS + DS.DRIVEN_WORLDS)):
            write_probe(out / "tables" / wid, wid, DS.closed_inputs(wid), fp)
        for wid in DS.V_CLOSED_WORLDS:
            write_vprobe(out / "vtables" / wid, wid, DS.v_closed_inputs(wid), vp)
    if rows & {"OL4-3", "OL4-4"}:
        for run_id, spec in DS.LEDGER_RUNS.items():
            write_run(out / "runs" / run_id, run_id, spec, fp)
    if "OL4-6" in rows:
        spec = dict(DS.NESS_RUN)
        if long_events is not None:
            spec["max_events"] = long_events
        write_run(out / "runs" / spec["id"], spec["id"], spec, fp)
    if "OL4-9" in rows:
        write_refusals(out / "refusals")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Write the fuel references' stand-in records.")
    ap.add_argument("--out", required=True)
    ap.add_argument("--planted", default=None)
    a = ap.parse_args(argv)
    build(a.out, a.planted)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
