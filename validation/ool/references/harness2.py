"""The OL2 and OL3 rows, run against saved records in the references' canonical layout.

    python -m validation.ool.references.harness2 --records DIR [--rows OL2-1,OL3-2] [--out verdict.json]

Exit status: 0 every row passed; 1 a row failed; 2 a record is missing or malformed, or a run did
not exercise what its row needs (inconclusive: rerun, nothing is concluded).

**Canonical layout** (the engine's own layout is mapped onto it by an adapter once the family's
format exists; ``standin2`` writes it directly). Each record directory ends with
``manifest.json``, written last.
- ``kernel/<world>/``: ``probe.json`` {world, steps: the vesicle steps' ids in declared order};
  ``probe.npz`` with ``input_states`` [S, D] (membrane counts, lumen counts, finite pool counts, in
  the world's orders), ``a_plus`` and ``a_minus`` [S, C], ``lyses_plus`` and ``lyses_minus``
  [S, C] (the event's end state beyond sigma_max), ``derived`` [S, 7] (W, A in m^2, R in m, V_osm,
  V_sph and V in L, sigma in N/m). Worlds ``ol2_wa``, ``ol2_wa_diffusion`` (their probe states)
  and ``ol2_closed``, ``ol2_two`` (their one-vesicle states).
- ``runs/<run>/``: ``trace.json``, a ``population.TRACE_FORMAT`` trace: every draw of domains 1
  and 5 with its address, uniforms and fate (event, discarded, end); every schedule draw (domain
  6: schedule, counter, u, use); every event (steps with group, channel, lysis, heat, reservoir
  work and the changed vesicle and pool after; shears with every attempt's address, block of
  uniforms, outcome, daughters with slots, keys and birth lysis, and its shear work, heat,
  reservoir work and sink; transfers with their draws, kept and removed slots, sink and schedule
  work); the initial and final states; the end reason; the environment record.
- ``partition/``: ``partition.npz`` with, per parent id, ``<id>_u`` [M, N + k + N_L],
  ``<id>_membrane`` [M, k, G] and ``<id>_lumen`` [M, k, G_L].
- ``refusals/refusals.json``: {declaration id: {refused, message}}.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from . import ol2_checks as OC
from . import ol3_checks as O3
from . import population as P
from . import registered2 as R2
from .common import MissingRecord, RecordFormatError, jsonable
from .ol2 import Law2
from .records import MANIFEST

ROWS = {
    "OL2-1": "Exchange, permeation and the membrane step at registered states, under both encounter tokens: cycle "
             "closure, the exact-F identity, the forward forms with the floor's zero pattern and lysis flags, and the "
             "geometry in integer quanta (§0.2b 1-2, §0.2c 2-6, §0.2d 1-4)",
    "OL2-2": "Closed worlds relax to exp(-F)/Z: one vesicle across its kink, and two vesicles sharing a finite pool "
             "(§0.2b 2-3, §4.2)",
    "OL2-3": "Lysis: the event fires, the molecules return to their pool places as monomers, the closure cost is "
             "released, one row books q = -(F(n_after) - F(n)) + w, and the lineage ends lysed (§0.2c 8, §0.2d 7)",
    "OL2-4": "The shared pool's two-level selection, replayed from the world's draws, with the pool's group and empty "
             "slots (§0.2c 14, §0.2d 5), and the ledger's closure",
    "OL2-5": "Every registered OL2/OL3 declaration is refused (§0.2b, §0.2c 1-8)",
    "OL3-1": "C3x and the lumen split at registered parents: replayed from each attempt's uniforms, and against their "
             "exact laws (§0.2c 9-10)",
    "OL3-2": "A population under Poisson shear and serial transfer: the clock rule, the schedule streams, the "
             "transfer's sampling, slots and booking, and closure (§0.2c 12-14, §0.2d 6-7, §3.1-3.3)",
    "OL3-3": "Shear fission at declared times: admission, C3x at k = 3 with N mod 3 != 0, the floor's refusal, "
             "births beyond sigma_max lysing at birth, and the shear work (§0.2b 3-4, §0.2c 9-12, §0.2d 7)",
    "OL3-4": "A single lineage with a schedule: the clock rule on the followed assembly's own counter, and the "
             "unfollowed daughters' sink (§0.2d 6 at 95c98b5a, §3.3)",
    "OL3-5": "A full set of slots stops the run slots_full before the split (§0.2c 13)",
}
RUN_OF_ROW = {"OL2-3": "ol2_lysis_run", "OL2-4": "ol2_shared_run", "OL3-2": "ol3_population_run",
              "OL3-3": "ol3_shear_probe_run", "OL3-4": "ol3_lineage_run", "OL3-5": "ol3_slots_full_run"}


class Inconclusive(Exception):
    """The run did not exercise what its row needs (exit 2)."""


def _dir(path: Path) -> Path:
    if not path.is_dir():
        raise MissingRecord(f"no record at {path}")
    if not (path / MANIFEST).is_file():
        raise MissingRecord(f"{path} has no {MANIFEST} (an incomplete record)")
    return path


def _states_file(world: str) -> str:
    return {"ol2_wa": "ol2_wa_probe_states.json", "ol2_wa_diffusion": "ol2_wa_diffusion_probe_states.json",
            "ol2_closed": "ol2_closed_states.json", "ol2_two": "ol2_two_states.json"}[world]


def registered_states(world: str) -> list:
    doc = json.loads((R2.DESIGN_DIR / _states_file(world)).read_text())
    return [tuple(tuple(x) for x in s) for s in doc["states"]]


def load_kernel(root: Path, world: str) -> dict:
    d = _dir(root / "kernel" / world)
    meta = json.loads((d / "probe.json").read_text())
    with np.load(d / "probe.npz", allow_pickle=False) as z:
        arr = {k: z[k] for k in z.files}
    for k in ("input_states", "a_plus", "a_minus", "lyses_plus", "lyses_minus", "derived"):
        if k not in arr:
            raise RecordFormatError(f"{d}: probe.npz lacks {k}")
    if meta.get("world") != world:
        raise RecordFormatError(f"{d}: world {meta.get('world')!r}, {world!r} expected")
    states = registered_states(world)
    w = R2.worlds()[world]
    flat = np.array([list(a) + list(b) + list(c) for a, b, c in states], dtype=np.int64)
    if arr["input_states"].shape != flat.shape or not np.array_equal(arr["input_states"], flat):
        raise RecordFormatError(f"{d}: input_states differ from the registered states of {world}")
    ids = [c.id for c in w.vesicle_channels()]
    if meta.get("steps") != ids:
        raise RecordFormatError(f"{d}: steps {meta.get('steps')}, {ids} expected")
    return dict(states=states, table=arr)


def load_trace(root: Path, run: str) -> dict:
    d = _dir(root / "runs" / run)
    tr = json.loads((d / "trace.json").read_text())
    if tr.get("format") != P.TRACE_FORMAT:
        raise RecordFormatError(f"{d}: trace format {tr.get('format')!r}")
    return tr


def row_ol2_1(root: Path) -> list:
    out = []
    for world in ("ol2_wa", "ol2_wa_diffusion"):
        rec = load_kernel(root, world)
        law = Law2(R2.worlds()[world])
        for name, fn in (("kolmogorov", OC.kolmogorov), ("identity", OC.identity), ("forward_form", OC.forward_form),
                         ("geometry", OC.geometry)):
            out.append(dict(check=name, world=world, **fn(law, rec["states"], rec["table"])))
    return out


def closed_world_states(world: str) -> tuple:
    w = R2.worlds()[world]
    return (R2.closed_states(w), 1) if world == "ol2_closed" else (R2.two_states(w), 2)


def row_ol2_2(root: Path) -> list:
    out = []
    for world in ("ol2_closed", "ol2_two"):
        rec = load_kernel(root, world)
        law = Law2(R2.worlds()[world])
        out.append(dict(check="forward_form", world=world, **OC.forward_form(law, rec["states"], rec["table"])))
        out.append(dict(check="identity", world=world, **OC.identity(law, rec["states"], rec["table"])))
        states, slots = closed_world_states(world)
        idx = {s: i for i, s in enumerate(rec["states"])}
        C = len(law.w.vesicle_channels())
        ap = np.zeros((len(states), slots, C))
        am = np.zeros((len(states), slots, C))
        for i, s in enumerate(states):
            for j in range(slots):
                r = idx[(s[j].n, s[j].l, tuple(s[slots]))]
                ap[i, j] = rec["table"]["a_plus"][r]
                am[i, j] = rec["table"]["a_minus"][r]
        out.append(dict(check="stationary", world=world, closed_world_states=len(states),
                        **OC.stationary_check(law, law, states, slots, dict(a_plus=ap, a_minus=am))))
    return out


def run_checks(root: Path, run: str) -> tuple:
    tr = load_trace(root, run)
    spec = R2.runs()[run]
    checks = [dict(check="replay", **P.replay(spec, tr)), dict(check="closure", **P.closure_check(spec, tr)),
              dict(check="streams", **P.stream_check(tr)), dict(check="environment", **P.environment_check(tr))]
    return tr, checks


def _coverage(tr: dict) -> dict:
    ev = tr.get("events", [])
    att = [a for e in ev if e["kind"] == "shear" for a in e["attempts"]]
    return dict(lysing_steps=sum(1 for e in ev if e["kind"] == "step" and e.get("lysed")),
                splits=sum(a["outcome"] == "split" for a in att),
                refused_floor=sum(a["outcome"] == "refused_floor" for a in att),
                births_lysed=sum(bool(d.get("lysed_at_birth")) for a in att for d in a.get("daughters", [])),
                not_admitted=sum(len(e.get("not_admitted", [])) for e in ev if e["kind"] == "shear"),
                discarded=sum(d.get("fate") == "discarded" for d in tr.get("draws", [])),
                transfers_all_kept=sum(1 for e in ev if e["kind"] == "transfer" and not e["removed"]),
                transfers_removing=sum(1 for e in ev if e["kind"] == "transfer" and e["removed"]),
                pool_group_events=sum(1 for e in ev if e["kind"] == "step" and e["group"] == -1),
                groups=sorted({e["group"] for e in ev if e["kind"] == "step"}),
                k3_splits=sum(1 for e in ev if e["kind"] == "shear" for a in e["attempts"]
                              if a["outcome"] == "split" and len(a["daughters"]) == 3))


COVERAGE = {
    "ol2_lysis_run": {"lysing_steps": 1},
    "ol2_shared_run": {"pool_group_events": 1},
    "ol3_population_run": {"splits": 1, "discarded": 1, "transfers_all_kept": 1, "transfers_removing": 1},
    "ol3_shear_probe_run": {"births_lysed": 1, "refused_floor": 1, "not_admitted": 1, "k3_splits": 3},
    "ol3_lineage_run": {"splits": 1, "discarded": 1},
}
END_REASON = {"ol2_lysis_run": "lysed", "ol2_shared_run": "t_end", "ol3_population_run": "t_end",
              "ol3_shear_probe_run": "t_end", "ol3_lineage_run": "t_end", "ol3_slots_full_run": "slots_full"}


def row_run(root: Path, row: str) -> list:
    run = RUN_OF_ROW[row]
    tr, checks = run_checks(root, run)
    checks.append(dict(check="end_reason", passed=tr.get("end_reason") == END_REASON[run], end_reason=tr.get("end_reason"),
                       expected=END_REASON[run]))
    if run == "ol2_shared_run":
        disc = sum(d.get("fate") == "discarded" for d in tr.get("draws", []))
        checks.append(dict(check="no_schedule_no_discard", passed=disc == 0, discarded=disc))
    cov = _coverage(tr)
    short = {k: (cov[k], v) for k, v in COVERAGE.get(run, {}).items() if cov[k] < v}
    if run == "ol2_shared_run" and not {0, 1} <= set(cov["groups"]):
        short["vesicle_groups"] = (cov["groups"], [0, 1])
    if short and all(c["passed"] for c in checks):
        raise Inconclusive(f"{run} did not exercise {short}; its row concludes nothing")
    checks.append(dict(check="coverage", passed=True, **cov))
    return checks


def row_ol2_5(root: Path) -> list:
    rec = json.loads((_dir(root / "refusals") / "refusals.json").read_text())
    from .refusals2 import refusal_check

    return [refusal_check(rec)]


def row_ol3_1(root: Path) -> list:
    d = _dir(root / "partition")
    with np.load(d / "partition.npz", allow_pickle=False) as z:
        arr = {k: z[k] for k in z.files}
    att = {}
    for p in R2.OL3_PARENTS:
        try:
            u, m, l_ = arr[f"{p['id']}_u"], arr[f"{p['id']}_membrane"], arr[f"{p['id']}_lumen"]
        except KeyError as exc:
            raise RecordFormatError(f"{d}: partition.npz lacks {exc}") from exc
        att[p["id"]] = [dict(counter=i, u=u[i].tolist(), membrane=m[i].tolist(), lumen=l_[i].tolist())
                        for i in range(u.shape[0])]
    return [dict(check="partition", **O3.check(R2.OL3_PARENTS, att, R2.PARTITION_ATTEMPTS))]


ROW_FUNCTIONS = {"OL2-1": row_ol2_1, "OL2-2": row_ol2_2, "OL2-5": row_ol2_5, "OL3-1": row_ol3_1,
                 **{r: (lambda root, r=r: row_run(root, r)) for r in RUN_OF_ROW}}


def run_rows(root, rows=None) -> tuple:
    root = Path(root)
    verdict, status = {}, 0
    for row in rows or list(ROWS):
        try:
            checks = ROW_FUNCTIONS[row](root)
            ok = all(bool(c["passed"]) for c in checks)
            verdict[row] = dict(claim=ROWS[row], passed=ok, checks=jsonable(checks))
            if not ok:
                status = max(status, 1)
        except (MissingRecord, RecordFormatError, Inconclusive) as exc:
            verdict[row] = dict(claim=ROWS[row], passed=None, problem=f"{type(exc).__name__}: {exc}")
            status = 2
    return status, verdict


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--records", required=True)
    ap.add_argument("--rows", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    status, verdict = run_rows(a.records, a.rows.split(",") if a.rows else None)
    text = json.dumps(dict(status=status, rows=verdict), indent=1)
    if a.out:
        Path(a.out).write_text(text + "\n")
    print(json.dumps({r: v["passed"] for r, v in verdict.items()}))
    return status


if __name__ == "__main__":
    sys.exit(main())

