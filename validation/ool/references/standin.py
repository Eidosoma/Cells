"""A complete stand-in record set, written from the references themselves, for dry runs of the
harness. On it every row passes; with a planted form it must fail (the tests hold both).

- Probe tables come from ``detailed_balance.reference_table`` (a planted law where asked).
- The ladder's ensemble is drawn exactly from the master equation: each run's states at the
  registered times are a path of the chain sampled through its transition matrices
  exp(Q Delta t), so the stand-in has the exact joint law at those times (``planted_ladder``
  draws from a planted chain instead).
- Runs come from the host direct method (``ssa_oracle.run_host_ssa``), booked by
  ``ledger.rebook``; ``replay`` is the same run written twice, ``other_stream`` another seed.
- Refusals come from the reference's own parser.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.linalg import expm

from . import ledger, mass_action
from .common import RecordFormatError
from .design import (
    BOUNDARY_PROBE_FILE,
    CLOSED_WORLD_FILE,
    KERNEL_PROBE_FILE,
    LEDGER_RUN,
    PROBED_CONVENTIONS,
    RESCALE_RUN,
)
from .detailed_balance import reference_table
from .laws import Law
from .records import write_manifest
from .registered import DESIGN_DIR, WB_RUNGS, registered_world
from .ssa_oracle import (
    SELECT_FIRST_PREFIX_GT,
    TAU_NEG_LOG_U1,
    ChannelTable,
    FloatRates,
    run_host_ssa,
)
from .world import Conventions, load_world

SSA_DECLARED = {"tau": TAU_NEG_LOG_U1, "select": SELECT_FIRST_PREFIX_GT}


def _states(name: str) -> np.ndarray:
    return np.asarray(json.loads((DESIGN_DIR / name).read_text())["states"], dtype=np.int64)


def float_table(law: Law, states) -> dict:
    """A kernel table from the float path (``FloatRates``), as a float64 engine would report it."""
    fr = FloatRates(law)
    R = len(law.world.steps)
    return dict(a_plus=np.array([[fr.forward(r, s) for r in range(R)] for s in states]),
                a_minus=np.array([[fr.reverse(r, s) for r in range(R)] for s in states]))


def write_probe(out: Path, world_id: str, conv: Conventions, states, planted=None, planted_params=None) -> Path:
    """Honest probes come from the float path; planted ones from the exact planted law."""
    out.mkdir(parents=True, exist_ok=False)
    w = registered_world(world_id)
    if planted is None:
        t = float_table(Law(w, conv), states)
    else:
        t = reference_table(Law(w, conv, planted=planted, planted_params=planted_params), states)
    (out / "probe.json").write_text(json.dumps(dict(world=world_id, conventions=conv.as_dict(),
                                                    steps=[st.name for st in w.steps],
                                                    places=[p.name for p in w.finite]), indent=1))
    np.savez(out / "probe.npz", input_states=np.asarray(states, dtype=np.int64), a_plus=t["a_plus"],
             a_minus=t["a_minus"])
    write_manifest(out, ["probe.json", "probe.npz"])
    return out


def write_run(out: Path, world_id: str, conv: Conventions, seed: int, *, max_events: int, row_every: int,
              t_end: float, stream: str, bias: float | None = None) -> Path:
    out.mkdir(parents=True, exist_ok=False)
    w = registered_world(world_id)
    law = Law(w, conv)
    rates = FloatRates(law)
    rates.planted_bias = bias
    table = ChannelTable.default(law)
    n0 = w.state_from(w.initial_state)
    run = run_host_ssa(rates, table, n0, t_end=t_end, rng=np.random.default_rng(seed), max_events=max_events)
    E = len(run["event_channel"])
    book = ledger.rebook(law, table, n0, run["event_channel"])
    rows = sorted(set(list(range(0, E + 1, row_every)) + [E]))
    q = np.concatenate([[0.0], np.cumsum(book["q"])])
    wk = np.concatenate([[0.0], np.cumsum(book["w"])])
    channels = [dict(step=w.steps[r].name, direction=int(s), code=int(c))
                for r, s, c in zip(table.step, table.sign, table.code)]
    (out / "run.json").write_text(json.dumps(dict(world=world_id, conventions=conv.as_dict(), ssa=SSA_DECLARED,
                                                  channels=channels, stream=stream, initial_state=w.initial_state),
                                             indent=1))
    np.savez(out / "records.npz", event_time=run["event_time"], event_channel=run["event_channel"],
             event_uniforms=run["event_uniforms"], row_event=np.asarray(rows, dtype=np.int64),
             counts=book["states"][rows], heat_kT=q[rows], work_kT=wk[rows])
    write_manifest(out, ["run.json", "records.npz"])
    return out


def sample_paths(states, Q, initial, times, runs: int, rng: np.random.Generator) -> np.ndarray:
    """Exact samples of the chain at the given times: [runs, times, D]."""
    idx = {tuple(int(v) for v in s): k for k, s in enumerate(states)}
    S = np.asarray(states)
    cur = np.full(runs, idx[tuple(int(v) for v in initial)])
    out = np.empty((runs, len(times), S.shape[1]), dtype=np.int64)
    prev = 0.0
    Qd = Q.toarray()
    for k, t in enumerate(times):
        P = expm(Qd * (t - prev))
        P = np.clip(P, 0.0, None)
        P /= P.sum(1, keepdims=True)
        cdf = np.cumsum(P, axis=1)
        u = rng.random(runs)
        cur = np.minimum((cdf[cur] < u[:, None]).sum(1), len(states) - 1)
        out[:, k] = S[cur]
        prev = t
    return out


def write_ensemble(out: Path, runs: int, seed: int, planted: str | None = None) -> Path:
    out.mkdir(parents=True, exist_ok=False)
    rng = np.random.default_rng(seed)
    conv = Conventions(condensed_measure="multinomial", last_molecule="kept")
    arrays, meta = {}, {"rungs": {}}
    for M in WB_RUNGS:
        if planted is None:
            law = Law(mass_action.rung_world(M), conv)
            states, Q = mass_action.chain(law)
            n0 = law.world.state_from(law.world.initial_state)
        else:
            states, Q, n0 = mass_action.planted_chain(M, planted, conv)
        arrays[f"observation_counts_m{M}"] = sample_paths(states, Q, n0, mass_action.OBSERVATION_TIMES, runs, rng)
        meta["rungs"][str(M)] = {"streams": [f"standin-m{M}-{k}" for k in range(runs)]}
    (out / "ensemble.json").write_text(json.dumps(meta))
    np.savez(out / "ensemble.npz", **arrays)
    write_manifest(out, ["ensemble.json", "ensemble.npz"])
    return out


def write_refusals(out: Path, accept: tuple = ()) -> Path:
    out.mkdir(parents=True, exist_ok=False)
    rec = {}
    for f in sorted((DESIGN_DIR / "refusals").glob("*.world.json")):
        rid = f.name[: -len(".world.json")]
        try:
            load_world(f)
            rec[rid] = dict(refused=False, message="parsed")
        except (RecordFormatError, ValueError, KeyError) as exc:
            rec[rid] = dict(refused=True, message=str(exc))
        if rid in accept:
            rec[rid] = dict(refused=False, message="planted: accepted")
    (out / "refusals.json").write_text(json.dumps(rec, indent=1))
    write_manifest(out, ["refusals.json"])
    return out


def build_standin(out_dir, *, ensemble_runs: int = mass_action.ENSEMBLE_RUNS, events: int | None = None,
                  planted: dict | None = None) -> dict:
    """Write every role into out_dir and return the roles mapping.

    ``planted`` may name {"kernel_probe": form, "closed_world": form, "ladder": form,
    "selection_bias": weight, "refusal_accepted": id}; everything else is honest."""
    planted = dict(planted or {})
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=False)
    events = events or LEDGER_RUN["max_events"]
    pp = dict(step="r3", place="D@membrane", lam=1)
    roles = {k: [] for k in ("kernel_probe", "boundary_probe", "closed_world", "closed_world_uncatalysed",
                             "ledger_run", "replay", "other_stream")}
    kp, cw, bp = _states(KERNEL_PROBE_FILE), _states(CLOSED_WORLD_FILE), _states(BOUNDARY_PROBE_FILE)
    for i, pair in enumerate(PROBED_CONVENTIONS):
        conv = Conventions(**pair)
        tag = f"{conv.condensed_measure}-{conv.last_molecule}"
        roles["kernel_probe"].append(str(write_probe(out / f"kernel_probe-{tag}", "ol1_wa", conv, kp,
                                                     planted.get("kernel_probe"), pp)))
        roles["boundary_probe"].append(str(write_probe(out / f"boundary_probe-{tag}", "ol1_boundary", conv, bp,
                                                       planted.get("boundary_probe"))))
        roles["closed_world"].append(str(write_probe(out / f"closed_world-{tag}", "ol1_wa_closed", conv, cw,
                                                     planted.get("closed_world"), pp)))
        roles["closed_world_uncatalysed"].append(str(write_probe(out / f"closed_world_uncatalysed-{tag}",
                                                                 "ol1_wa_closed_uncatalysed", conv, cw)))
        kw = dict(max_events=events, row_every=LEDGER_RUN["row_every_events"], t_end=LEDGER_RUN["t_end_s"])
        bias = planted.get("selection_bias")
        roles["ledger_run"].append(str(write_run(out / f"ledger_run-{tag}", "ol1_wa", conv, 100 + i,
                                                 stream=f"standin-ledger-{i}", bias=bias, **kw)))
        roles["replay"].append(str(write_run(out / f"replay-{tag}", "ol1_wa", conv, 100 + i,
                                             stream=f"standin-ledger-{i}", bias=bias, **kw)))
        roles["other_stream"].append(str(write_run(out / f"other_stream-{tag}", "ol1_wa", conv, 200 + i,
                                                   stream=f"standin-other-{i}", **kw)))
    conv = Conventions(**PROBED_CONVENTIONS[0])
    base = write_run(out / "rescale-base", "ol1_wa_closed", conv, 300, max_events=RESCALE_RUN["events"],
                     row_every=RESCALE_RUN["events"], t_end=1e9, stream="standin-rescale")
    scaled = write_run(out / "rescale-scaled", "ol1_wa_closed_x2", conv, 300, max_events=RESCALE_RUN["events"],
                       row_every=RESCALE_RUN["events"], t_end=1e9, stream="standin-rescale")
    roles["rescale_pair"] = {"base": str(base), "scaled": str(scaled)}
    roles["wb_ensemble"] = str(write_ensemble(out / "wb_ensemble", ensemble_runs, 400, planted.get("ladder")))
    accept = (planted["refusal_accepted"],) if "refusal_accepted" in planted else ()
    roles["refusals"] = str(write_refusals(out / "refusals", accept))
    (out / "roles.json").write_text(json.dumps(roles, indent=1))
    return roles
