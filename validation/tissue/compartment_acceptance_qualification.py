"""fr1-closed-compartment-v1's generator: the protocol's parts, as records (FR-1, D216).

The protocol is validation/tissue/compartment_acceptance_protocol.json; its worlds are
validation/tissue/compartment_acceptance_fixtures' builders, with compartment_fixtures' W and W+ for
C2 and C9. The generator writes records and computes no verdict; the judge
(validation/tissue/compartment_acceptance_judge.py) reads them. Each part is its own unit
(OUT_DIR/results.json), and the judge merges the units (MG0c's form, as FR-4's, FR-5's and FR-10's).

Parts (the protocol's judged_parts):
* C1_refusals: §1.4's refusals 1 to 7, each representative refused at the definition, its reason
  classified from the message, and its neighbour admitted and run;
* C2_identity: S5's four traced pairs (the declaration against the same world without it);
* C3_flux, C3_first_order: loading with retention at the declared 1 ms;
* C4_rung_1ms ... C4_rung_0p125ms: the two-way first-order exchange on the ladder;
* C5_saturable: the saturable release at 1 ms;
* C6_rung_*, C7_rung_*, C8_rung_*: loading with clearance, with D152's S -> P, and the uptake path,
  on the ladder;
* C9_silence: W+ in the scalar, RK4, windowed, vector-window and batch programs and across a
  restart through a snapshot: S1 to S3 and what shows the check is live (S4 reported);
* C10_rk4: first-order loading under RK4 at 0.1 ms, every row;
* C11_<law>_ars, C11_<law>_rk4: each loading and release law from a 1e-15 mM trace, every row;
* C12_restart: two_way with a rate change at 0.5 s, straight and resumed through the engine's
  checkpoint at 0.25, 0.5 and 0.75 s, in process and through a snapshot (cells.records.io), with K4's
  restart whose change is moved one step; C12_batch: four worlds of different compartment volumes
  and rates in one vector batch, against each scalar run and against the reversed batch;
* K1_one_way: C4 at 1 ms without its import; K2_no_clearance: C6 at 1 ms without its clearance;
* C13_controls: the misbooked move and work; K3_planted: C9's planted controls; each plant in
  its own process (validation/tissue/compartment_acceptance_plants), with its identity and size
  in its bundle;
* references: the FR references agent's (validation/fr1/references, through its usage note's API
  only, REFERENCES_USAGE.md), on the registered inputs.

Each run part records, at every observation time: every node's S (and P) amount
(amount_SPECIES_NODE, fmol); each exchange route's cumulative moved amount, work and energy
magnitude (moved_ROUTE_fmol, work_ROUTE_pJ, magnitude_ROUTE_pJ); turnover's cleared amount and work
at each node (cleared_NODE_fmol, cleared_work_NODE_pJ); the energy residual, integrated flows and
bound of @3's energy ledger; and each ledger's largest |balance| over its bound (ratio_LEDGER).

Modes:
  python -m validation.tissue.compartment_acceptance_qualification dev OUT_DIR PART [PART ...]
      [--quick]
  python -m validation.tissue.compartment_acceptance_qualification judged PROTOCOL_JSON OUT_DIR
      PART [PART ...]
A judged run is refused, before anything is computed or written, unless the protocol is registered
(its status and its registration record), the source is a clean execution snapshot, no stand-in
blocks a requested part, and OUT_DIR is new (D150's and MG0c's guard). `--quick` (development
only) runs every engine world to QUICK_FRACTION of its horizon.
"""  # noqa: E501

import argparse
import copy
import hashlib
import json
import math
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from validation.tissue import compartment_acceptance_fixtures as af
from validation.tissue import compartment_fixtures as cf
from validation.tissue import field_solver_choice
from validation.tissue import secreted_species_fixtures as fx

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "validation" / "tissue" / "compartment_acceptance_protocol.json"
PROTOCOL_ID = "fr1-closed-compartment-v1"
QUICK_FRACTION = 0.4
ARS, RK4 = af.ARS, af.RK4


def dt_key(dt):
    """1e-3 -> '1ms', 1.25e-4 -> '0p125ms'."""
    return f"{dt * 1e3:g}".replace(".", "p") + "ms"


def rungs(prefix):
    return {f"{prefix}_rung_{dt_key(dt)}": dt for dt in af.LADDER_S}


C4_RUNGS, C6_RUNGS, C7_RUNGS, C8_RUNGS = (rungs(p) for p in ("C4", "C6", "C7", "C8"))
C11_PARTS = {f"C11_{law}_{'ars' if solver == ARS else 'rk4'}": (law, solver)
             for law in af.C11_LAWS for solver in (ARS, RK4)}
PARTS = ("C1_refusals", "C2_identity", "C3_flux", "C3_first_order", *C4_RUNGS, "C5_saturable",
         *C6_RUNGS, *C7_RUNGS, *C8_RUNGS, "C9_silence", "C10_rk4", *C11_PARTS, "C12_restart",
         "C12_batch", "K1_one_way", "K2_no_clearance", "C13_controls", "K3_planted",
         "references")
RESTART_TIMES_S = (0.25, 0.5, 0.75)
C12_CHANGE = (0.5, 4.0, 8.0)  # (time s, a 1/s, b 1/s): both of C4's rates fall at 0.5 s.
C12_WORLDS = ((0.05, 10.0, 20.0), (0.1, 5.0, 10.0), (0.2, 10.0, 5.0), (0.4, 2.0, 2.0))
C9_END_S = {ARS: 0.1, RK4: 0.01}
# What remains a stand-in, and the parts each blocks.
STAND_INS = {}
STAND_IN_PARTS = {}
REFERENCES_INPUTS = ROOT / "validation" / "fr1" / "references" / "reference_inputs.json"
REGISTERED_INPUTS = ROOT / "validation" / "closed_compartment" / "reference_inputs.json"
# R_energy's world names, by part: the eight from-trace runs and C6's declared rung.
ENERGY_PARTS = {**{f"{law} {'ARS' if solver == ARS else 'RK4'}": part
                   for part, (law, solver) in C11_PARTS.items()},
                "C6_load_and_degrade": f"C6_rung_{dt_key(af.DECLARED_DT)}"}
# The checks a refusal may name (C1's classes), by a phrase of their messages.
CHECKS = (
    ("refusal 1 (the node: a face)", "has no face (it is closed)"),
    ("refusal 1 (the node: a held bath)", "is a held bath; a compartment is a finite node"),
    ("refusal 2 (the patch)", "is bounded by exactly one patch"),
    ("refusal 2 (the owner)", "not on its declared owner"),
    ("refusal 3 (one compartment per node)", "one compartment per node"),
    ("refusal 4 (an ion route)", "in a world that declares no kind"),
    ("refusal 5 (the charge anchor)", "declares a nonzero charge anchor"),
    ("refusal 6 (a held-bath topology)", "is the representative of its capacitor component"),
    ("refusal 7 (replacement's owners)", "which owns a compartment"),
)
# Phrases of earlier versions' messages, as saved records hold them, each its check's too.
EARLIER = (  # Refusal 6, version 1 (CLOSED_COMPARTMENT_DESIGN §3.5.1 has version 1.1).
    ("refusal 6 (a held-bath topology)", "lies in a capacitor component with no held bath"),
)


def classify(message):
    """The check a refusal message names, or None: by its phrase, or an earlier version's."""
    for check, phrase in (*CHECKS, *EARLIER):
        if phrase in (message or ""):
            return check
    return None


# ------------------------------------------------------------------ provenance and guards


def snapshot_identity(root=ROOT):
    manifest = Path(root) / "SNAPSHOT.json"
    if manifest.exists():
        snapshot = json.loads(manifest.read_text())
        return dict(kind="snapshot", git_revision=snapshot.get("git_revision"),
                    patch_sha256=snapshot.get("patch_sha256"), status=snapshot.get("status"))

    from validation import executed_sources  # noqa: PLC0415
    executed_sources.refuse_untracked(  # D259
        root, "compartment_acceptance_qualification's source record"
    )

    def git(*args):
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                              check=False).stdout.strip()

    return dict(kind="checkout", git_revision=git("rev-parse", "HEAD"),
                dirty=git("status", "--porcelain"))


def blocking_stand_ins(requested):
    return sorted(name for name in STAND_INS if STAND_IN_PARTS[name] & set(requested))


def judged_run_refusal(protocol, root=None):
    """Why a judged run may not start (None: it may). root: the source tree, ROOT (read when
    called) by default."""
    root = ROOT if root is None else root
    status = protocol.get("status")
    if not (isinstance(status, str) and status.lower().startswith("registered")):
        return "the protocol is not registered (its status does not begin 'registered')"
    record = protocol.get("registration")
    if not (isinstance(record, dict) and record.get("status") == status):
        return "the protocol's registration record is missing or does not match its status"
    if protocol.get("id") != PROTOCOL_ID:
        return f"not {PROTOCOL_ID}"
    manifest = Path(root) / "SNAPSHOT.json"
    if not manifest.exists():
        return "a judged run comes from a clean execution snapshot, not a checkout"
    snapshot = json.loads(manifest.read_text())
    if (snapshot.get("status") != "complete"
            or snapshot.get("patch_sha256") != hashlib.sha256(b"").hexdigest()):
        return "the execution snapshot is incomplete or carries uncommitted changes"
    return None


def refusal_before_writing(requested, out_dir, *, judged, quick):
    unknown = sorted(set(requested) - set(PARTS))
    if unknown or not requested:
        return f"unknown or no parts {unknown} (the parts: {list(PARTS)})"
    if judged and quick:
        return "a judged run has no quick horizon"
    blocked = blocking_stand_ins(requested)
    if blocked:
        return "; ".join(f"parts {sorted(set(requested) & STAND_IN_PARTS[n])} need what is still "
                         f"a stand-in here: {STAND_INS[n]}" for n in blocked)
    if Path(out_dir).exists():
        return "the output directory exists (each attempt writes its own)"
    return None


def plain(value):
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        return value.item()
    return value


# ------------------------------------------------------------------ worlds, quick horizons


def quick(raw):
    """The world to QUICK_FRACTION of its horizon (on its dt grid), its schedule changes kept
    before it."""
    out = copy.deepcopy(raw)
    x, dt = out["experiment"], out["execution"]["dt"]
    end = max(dt, round(QUICK_FRACTION * x["end_time"] / dt) * dt)
    x["end_time"] = end
    x["observation_times"] = sorted({t for t in x["observation_times"] if t < end} | {end})
    for key in ("exchange_controls", "turnover_controls", "reaction_controls"):
        for control in x.get(key, []):
            control["schedule"] = [c for c in control["schedule"] if c["time"] < end]
    out["execution"]["max_steps"] = int(math.ceil(end / dt)) + 8
    return out


def every_step(raw):
    """The world recorded at every step (C10's and C11's rows)."""
    out = copy.deepcopy(raw)
    x, dt = out["experiment"], out["execution"]["dt"]
    x["observation_times"] = fx.grid_times(x["end_time"], dt, dt)
    return out


# ------------------------------------------------------------------ admission and runs


def admit(raw):
    """(spec, None) when the definition is admitted (parsed, and its clock's step checks pass:
    cells.execution.runner.timeline), else (None, the refusal message)."""
    from cells.definitions.specs import ConfigError, parse_spec
    from cells.execution.runner import timeline

    try:
        spec = parse_spec(raw)
        timeline(spec)
    except ConfigError as error:
        return None, str(error)
    return spec, None


def _row(model, history, i):
    return model.STATE_TYPE(*(np.asarray(v)[i] for v in history))


def _ratio(balance, bound):
    balance, bound = np.abs(np.asarray(balance, dtype=float)), np.asarray(bound, dtype=float)
    bound = bound * np.ones_like(balance)
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.where(bound > 0, balance / bound, np.where(balance > 0, np.inf, 0.0))
    return float(np.max(r, initial=0.0))


def records_of(result, raw):
    """Every observation time's series (module docstring) from a runner result; `raw` names the
    exchange routes and turnover's nodes in declared order."""
    from cells.models.surface_pump import ENERGY_RTOL
    from cells.registry.models import get_model

    spec = result.spec
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    m, x = spec.model, spec.execution
    tol = np.asarray(x.material_balance_atol_fmol)
    names = list(model.LEDGERS)
    times, obs = np.asarray(result.times), result.observations
    obs_times = np.asarray(obs.times)
    species = list(m.species_ids)
    tracked = [s for s in ("S", "P") if s in species]
    cells = [c.id for c in m.cells]
    outside = [c.id for c in m.extracellular]
    ops = raw["model"]["operators"]
    routes = next((op["routes"] for op in ops if op["law"] == fx.EXCHANGE), [])
    turnover = next((op["routes"] for op in ops if op["law"] == fx.TURNOVER), [])
    series = {}

    def add(name, value):
        series.setdefault(name, []).append(float(value))

    moved = np.asarray(getattr(obs, "exchange_moved_fmol", np.zeros((len(obs_times), 0))))
    work = np.asarray(getattr(obs, "exchange_work_pJ", np.zeros((len(obs_times), 0))))
    magnitude = np.asarray(getattr(obs, "exchange_energy_magnitude_pJ",
                                   np.zeros((len(obs_times), 0))))
    cleared = getattr(obs, "turnover_outside_cleared_fmol", None)
    cleared_work = getattr(obs, "turnover_outside_work_pJ", None)
    for j, t in enumerate(obs_times):
        i = int(np.argmin(np.abs(times - t)))
        if abs(times[i] - t) > 1e-9 * max(1.0, abs(t)):
            raise ValueError(f"observation time {t} is not an accepted step")
        row = _row(model, result.history, i)
        steps = int(round(t / x.dt))
        balances = model.balances(row, p)
        magnitudes = model.magnitudes(row, p)
        flows, bounds = model.ledger_limits(
            row, p, tol, ENERGY_RTOL[x.solver], steps=steps, magnitudes=magnitudes
        )
        add("energy_residual_pJ", float(balances["energy"]))
        add("energy_flows_pJ", float(flows))
        add("energy_bound_pJ", float(np.max(np.asarray(bounds[names.index("energy")]))))
        for k, name in enumerate(names):
            if name in balances:
                add(f"ratio_{name}", _ratio(balances[name], bounds[k]))
        for sid in tracked:
            s_ = species.index(sid)
            for c_, cid in enumerate(cells):
                add(f"amount_{sid}_{cid}", np.asarray(obs.amount)[j, s_, c_])
            for o_, oid in enumerate(outside):
                if not m.extracellular[o_].reservoir:
                    add(f"amount_{sid}_{oid}", np.asarray(obs.extracellular_amount)[j, s_, o_])
        for r_, route in enumerate(routes):
            add(f"moved_{route['id']}_fmol", moved[j, r_])
            add(f"work_{route['id']}_pJ", work[j, r_])
            add(f"magnitude_{route['id']}_pJ", magnitude[j, r_])
        if turnover and cleared is not None:
            s_ = species.index(fx.SPECIES)
            for route in turnover:
                o_ = outside.index(route["node"])
                add(f"cleared_{route['node']}_fmol", np.asarray(cleared)[j, s_, o_])
                add(f"cleared_work_{route['node']}_pJ", np.asarray(cleared_work)[j, o_])
    volumes = {c.id: c.volume_pL for c in (*m.cells, *m.extracellular) if not
               getattr(c, "reservoir", False)}
    return dict(record_s=[float(t) for t in obs_times], series=series, ledgers=sorted(names),
                diagnostics=plain(dict(result.diagnostics)), species=tracked, cells=cells,
                outside=outside, routes=[r["id"] for r in routes], volumes_pL=volumes,
                temperature_K=float(m.temperature_K))


def engine_part(raw, context, *, label=None):
    """One run of one definition: its admission, run and records (records_of)."""
    from cells.execution.errors import NumericalError
    from cells.execution.runner import run

    raw = quick(raw) if context["quick"] else raw
    started = time.perf_counter()
    spec, refusal = admit(raw)
    out = dict(kind="engine", label=label, dt_s=raw["execution"]["dt"],
               solver=raw["execution"]["solver"], end_s=raw["experiment"]["end_time"],
               steps=int(round(raw["experiment"]["end_time"] / raw["execution"]["dt"])))
    if spec is None:
        return dict(out, admitted=False, completed=False, refusal=refusal,
                    refusal_check=classify(refusal), wall_s=time.perf_counter() - started)
    try:
        result = run(spec)
    except NumericalError as error:
        return dict(out, admitted=True, completed=False, refusal=str(error),
                    wall_s=time.perf_counter() - started)
    return dict(out, admitted=True, completed=True, refusal=None, **records_of(result, raw),
                wall_s=time.perf_counter() - started)


def compare_results(a, b, start=None):
    """The final state, and every history row and observation from `start` on, bit for bit."""
    from validation.tissue.composite_guard import compare_arrays

    differences = []
    for name in type(a.final.state)._fields:
        d = compare_arrays("final." + name, getattr(a.final.state, name),
                           getattr(b.final.state, name))
        if d is not None:
            differences.append(d)
    ta, tb = np.asarray(a.times), np.asarray(b.times)
    i0 = 0 if start is None else int(np.argmin(np.abs(ta - start)))
    j0 = 0 if start is None else int(np.argmin(np.abs(tb - start)))
    for name, ha, hb in zip(type(a.final.state)._fields, a.history, b.history, strict=True):
        d = compare_arrays("history." + name, np.asarray(ha)[i0:], np.asarray(hb)[j0:])
        if d is not None:
            differences.append(d)
    oa, ob = np.asarray(a.observations.times), np.asarray(b.observations.times)
    k0 = 0 if start is None else int(np.searchsorted(oa, start - 1e-12))
    l0 = 0 if start is None else int(np.searchsorted(ob, start - 1e-12))
    for name in vars(a.observations):
        d = compare_arrays("observations." + name, np.asarray(getattr(a.observations, name))[k0:],
                           np.asarray(getattr(b.observations, name))[l0:])
        if d is not None:
            differences.append(d)
    return dict(equal=not differences, first=plain(differences[0]) if differences else None,
                differences=len(differences))


# ------------------------------------------------------------------ the parts


def _engine(build):
    def part(name, context):
        del name
        return engine_part(build(), context)
    return part


def _rung(build, dt):
    def part(name, context):
        del name
        return engine_part(build(dt=dt), context)
    return part


def _c11(law, solver):
    def part(name, context):
        del name
        return engine_part(af.from_trace(law, solver), context)
    return part


def c10_rk4(name, context):
    del name
    raw = af.first_order_loading(dt=af.RK4_DT, solver=RK4, end=af.C11_END_S[RK4])
    return engine_part(every_step(raw), context)


def _restart(raw, at, workdir, *, through_snapshot):
    """Run to `at`, then resume to the end: in process from the checkpoint, or through a written
    snapshot (cells.records.io.write_snapshot and load_snapshot)."""
    from cells.definitions.specs import parse_spec
    from cells.execution.runner import branch_checkpoint, run
    from cells.records.io import load_snapshot, write_snapshot

    spec = parse_spec(raw)
    head = copy.deepcopy(raw)
    head["experiment"]["end_time"] = at
    head["experiment"]["observation_times"] = [t for t in raw["experiment"]["observation_times"]
                                               if t <= at + 1e-12]
    for key in ("exchange_controls", "turnover_controls", "reaction_controls"):
        for control in head["experiment"].get(key, []):  # Changes at or after `at` are the
            control["schedule"] = [c for c in control["schedule"] if c["time"] < at]  # resume's.
    first = run(parse_spec(head))
    origin, checkpoint = first.spec, first.final
    if through_snapshot:
        directory = Path(workdir) / f"checkpoint-{at:g}"
        directory.parent.mkdir(parents=True, exist_ok=True)
        write_snapshot(directory, first.spec, first.final)
        loaded = load_snapshot(directory)
        origin, checkpoint = loaded.spec, loaded.checkpoint
    # A branch from the head's own checkpoint into the full schedule (its changes from `at` on).
    return run(spec, branch_checkpoint(origin, checkpoint, spec))


def c12_restart(name, context):
    """C12: straight, then resumed at, before and after the rate change, in process and through a
    snapshot; K4: the change moved one step later, resumed, against the straight run."""
    from cells.definitions.specs import parse_spec
    from cells.execution.runner import run

    del name
    started = time.perf_counter()
    raw = af.two_way(changes=[C12_CHANGE])
    if context["quick"]:
        raw = quick(raw)
    end = raw["experiment"]["end_time"]
    straight = run(parse_spec(raw))
    out = {}
    with tempfile.TemporaryDirectory(dir=context["out_dir"]) as workdir:
        for at in RESTART_TIMES_S:
            if at >= end:
                continue
            for mode in ("in_process", "snapshot"):
                resumed = _restart(raw, at, workdir, through_snapshot=mode == "snapshot")
                out[f"{at:g} {mode}"] = compare_results(straight, resumed, start=at)
        t, a, b = C12_CHANGE
        moved = af.two_way(changes=[(t + raw["execution"]["dt"], a, b)])
        planted = None
        if t < end:
            moved = quick(moved) if context["quick"] else moved
            planted = compare_results(straight, _restart(moved, 0.25, Path(workdir) / "moved",
                                                         through_snapshot=True), start=0.25)
    return dict(kind="comparison", admitted=True, completed=True, restarts=out, planted=planted,
                wall_s=time.perf_counter() - started)


def c12_batch(name, context):
    """C12: four worlds of different compartment volumes and rates in one vector batch, against
    each world's scalar run (within 1e-12 relative) and against the reversed batch (bitwise)."""
    from cells.definitions.specs import parse_spec
    from cells.execution.batch import BatchSpec, WorldSpec
    from cells.execution.runner import run
    from cells.execution.vector_windows import run_vector_windowed
    from cells.execution.windows import WindowPolicy

    del name
    started = time.perf_counter()
    raws = [af.two_way(a=a, b=b, volume=v) for v, a, b in C12_WORLDS]
    if context["quick"]:
        raws = [quick(r) for r in raws]
    specs = [parse_spec(r) for r in raws]

    def cohort(worlds):
        batch = BatchSpec(tuple(WorldSpec(i + 1, s) for i, s in enumerate(worlds)), len(worlds),
                          10**8, 2**33)
        seen = {}

        def sink(window):
            for identity, found in window.observations.items():
                seen.setdefault(identity, []).append(found)

        result = run_vector_windowed(batch, WindowPolicy(10**6, "observations"), sink=sink)
        return result, seen

    forward, forward_seen = cohort(specs)
    backward, backward_seen = cohort(list(reversed(specs)))
    n = len(specs)
    out = {}
    for i, (spec, raw) in enumerate(zip(specs, raws, strict=True)):
        scalar = run(spec)
        rows = _amount_rows(forward_seen[i + 1])
        alone = (np.asarray(scalar.observations.amount),
                 np.asarray(scalar.observations.extracellular_amount))
        reversed_rows = _amount_rows(backward_seen[n - i])
        node = next(o for o in raw["model"]["extracellular"] if o["id"] == cf.NODE)
        out[f"world_{i + 1}"] = dict(
            volume_pL=node["volume_pL"],
            scalar_relative=_relative(rows, alone),
            reversed_equal=_bitwise(rows, reversed_rows),
            final_reversed_equal=_bitwise_state(forward.worlds[i + 1].final,
                                                backward.worlds[n - i].final))
    return dict(kind="comparison", admitted=True, completed=True, worlds=out,
                wall_s=time.perf_counter() - started)


def _amount_rows(windows):
    cell = np.concatenate([np.asarray(w.amount) for w in windows])
    node = np.concatenate([np.asarray(w.extracellular_amount) for w in windows])
    return cell, node


def _relative(batched, scalar):
    worst = 0.0
    for a, b in zip(batched, scalar, strict=True):
        a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
        if a.shape != b.shape:
            return None
        scale = np.maximum(np.abs(b), 1e-300)
        worst = max(worst, float(np.max(np.abs(a - b) / scale)))
    return worst


def _bitwise(a, b):
    return all(np.asarray(x).dtype == np.asarray(y).dtype and np.asarray(x).shape ==
               np.asarray(y).shape and np.asarray(x).tobytes() == np.asarray(y).tobytes()
               for x, y in zip(a, b, strict=True))


def _bitwise_state(a, b):
    return all(np.asarray(x).tobytes() == np.asarray(y).tobytes()
               for x, y in zip(a.state, b.state, strict=True))


def k1_one_way(name, context):
    del name
    return engine_part(af.two_way(b=0.0), context, label="K1: C4 without its import")


def k2_no_clearance(name, context):
    del name
    return engine_part(af.load_and_degrade(clear=0.0), context,
                       label="K2: C6 without its clearance")


def c9_silence(name, context):
    """C9: S1 to S3 on every row of W+ in every program family, with what shows the check is
    live (compartment_fixtures.silence); S4 (W+ against the world without the node) reported."""
    from cells.definitions.specs import parse_spec
    from cells.execution.batch import BatchSpec, WorldSpec, run_batch
    from cells.execution.runner import run
    from cells.execution.vector_windows import run_vector_windowed
    from cells.execution.windows import WindowPolicy, run_windowed

    del name
    started = time.perf_counter()
    end, rk4_end = C9_END_S[ARS], C9_END_S[RK4]
    if context["quick"]:
        end, rk4_end = QUICK_FRACTION * end, QUICK_FRACTION * rk4_end
    end, rk4_end = round(end / 1e-3) * 1e-3, round(rk4_end / 1e-4) * 1e-4
    every = fx.grid_times(end, 1e-3, 1e-3)
    out = {}
    spec = parse_spec(cf.live_compartment(end=end, dt=1e-3, observation_times=every))
    scalar = run(spec)
    out["scalar"] = cf.silence(spec, scalar.observations)
    rk4 = parse_spec(cf.live_compartment(end=rk4_end, dt=1e-4, solver=RK4,
                                         observation_times=fx.grid_times(rk4_end, 1e-4, 1e-4)))
    out["rk4"] = cf.silence(rk4, run(rk4).observations)
    seen = []
    run_windowed(spec, WindowPolicy(25, "observations"), sink=seen.append)
    windowed = [cf.silence(spec, w.observations) for w in seen]
    out["windowed"] = _merge_silence(windowed)
    rates = (0.1, 0.2, 0.4)
    specs = [parse_spec(cf.live_compartment(end=end, dt=1e-3, export=r, observation_times=every))
             for r in rates]
    rounds = {}
    run_vector_windowed(BatchSpec(tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs)),
                                  len(specs), 10**8, 2**33),
                        WindowPolicy(25, "observations"),
                        sink=lambda w: [rounds.setdefault(k, []).append(v)
                                        for k, v in w.observations.items()])
    out["vector_window"] = _merge_silence([cf.silence(specs[k - 1], o) for k, os_ in
                                           rounds.items() for o in os_])
    batch = run_batch(BatchSpec(tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs)),
                                len(specs), 10**8, 2**33))
    out["batch"] = _merge_silence([cf.silence(specs[k - 1], r.observations)
                                   for k, r in batch.worlds.items()])
    out["restart_snapshot"] = _silence_restart(spec, context)
    without = parse_spec(cf.live_without_compartment(end=end, dt=1e-3, observation_times=every))
    out["S4_reported"] = _s4(scalar, run(without))
    return dict(kind="silence", admitted=True, completed=True, programs=out,
                wall_s=time.perf_counter() - started)


def _merge_silence(found):
    if not found:
        return None
    return dict(s1=all(f["s1"] for f in found), s2=max(f["s2"] for f in found),
                s3=max(f["s3"] for f in found), rows=sum(f["rows"] for f in found),
                owner_ions_moved=any(f["owner_ions_moved"] for f in found),
                max_phi_owner=max(f["max_phi_owner"] for f in found),
                max_phi_node=max(f["max_phi_node"] for f in found))


def _silence_restart(spec, context):
    """W+ run to half its horizon, written as a snapshot, loaded and resumed to its end."""
    from cells.definitions.specs import parse_spec
    from cells.execution.runner import branch_checkpoint, run
    from cells.records.io import load_snapshot, write_snapshot

    end = spec.experiment.end_time
    at = round(end / 2 / 1e-3) * 1e-3
    first = run(parse_spec(cf.live_compartment(end=at, dt=1e-3,
                                               observation_times=fx.grid_times(at, 1e-3, 1e-3))))
    with tempfile.TemporaryDirectory(dir=context["out_dir"]) as workdir:
        directory = Path(workdir) / "checkpoint"
        write_snapshot(directory, first.spec, first.final)
        loaded = load_snapshot(directory)
        again = run(spec, branch_checkpoint(spec, loaded.checkpoint, spec))
    return cf.silence(spec, again.observations)


def _s4(with_node, without):
    """S4, reported: the largest relative difference of the owner's ion rows and potential."""
    a, b = with_node.observations, without.observations
    owner = np.asarray(a.amount)[:, :3, 0], np.asarray(b.amount)[:, :3, 0]
    phi = np.asarray(a.cell_potential_V)[:, 0], np.asarray(b.cell_potential_V)[:, 0]
    out = {}
    for key, (x, y) in dict(owner_ions=owner, owner_potential=phi).items():
        scale = np.maximum(np.abs(y), 1e-300)
        out[key] = float(np.max(np.abs(x - y) / scale))
    return out


def c2_identity(name, context):
    """C2, S5: the four traced pairs (compartment_fixtures.identity_differences)."""
    del name, context
    started = time.perf_counter()
    end = 0.004

    def alone(declared):
        raw = fx.face_free(pool_mM=1e-3, node_mM=1e-6, end=end)
        return cf.with_compartments(raw, [cf.compartment()]) if declared else raw

    pairs = {
        "W under ARS": lambda declared: cf.loaded_compartment(end=end, declared=declared),
        "W under RK4": lambda declared: cf.loaded_compartment(
            end=4e-4, dt=1e-4, solver=RK4, declared=declared),
        "W with clearance at the node": lambda declared: cf.loaded_compartment(
            end=end, turnover=True, declared=declared),
        "the declaration alone": alone,
    }
    out = {pair: cf.identity_differences(build) for pair, build in pairs.items()}
    return dict(kind="identity", admitted=True, completed=True, pairs=out,
                wall_s=time.perf_counter() - started)


def refusal_pairs():
    """C1's classes as {class: (refused, admitted)} raw definitions: each refused one is W (the
    silence world) changed in the one way its class names; each neighbour is W, or W with the
    admitted variant."""
    base = cf.loaded_compartment(end=0.02)
    face = copy.deepcopy(base)
    face["model"]["faces"].append(dict(copy.deepcopy(_any_face()), id="face_x", sender=cf.NODE,
                                       receiver="bath"))
    face["execution"]["face_capacity"] = len(face["model"]["faces"])
    held = copy.deepcopy(base)
    held["model"]["operators"][-1]["compartments"][0]["node"] = "bath"
    held["model"]["operators"][-1]["compartments"][0]["patch"] = "wall_cell_0"
    two_patches = _second_cell_on_node(base)
    two_entries = copy.deepcopy(base)
    two_entries["model"]["operators"][-1]["compartments"].append(
        cf.compartment(cid="lys_1"))
    routed = copy.deepcopy(base)
    next(p for p in routed["model"]["membranes"] if p["id"] == cf.PATCH)[
        "permeability_m_per_s"]["K"] = cf.PLANTED_ROUTE
    anchored = copy.deepcopy(base)
    cf._anchor(next(o for o in anchored["model"]["extracellular"] if o["id"] == cf.NODE),
               cf.PLANTED_ANCHOR_C)
    floating = _floating(base)
    return {
        "R1_a_face": (face, base),
        "R1_a_held_bath": (held, base),
        "R2_two_patches": (two_patches, base),
        "R3_one_compartment_per_node": (two_entries, base),
        "R4_an_ion_route": (routed, base),
        "R5_a_charge_anchor": (anchored, base),
        "R6_no_held_bath": (floating, base),
        "R7_replacement_on_an_owner": (_replaced([(0.005, "cell_0", "T", "c0_new")]),
                                       _replaced([(0.005, "cell_1", "T", "c1_new")])),
    }


def _any_face():
    raw = fx.world(end=0.02)
    return raw["model"]["faces"][0]


def _second_cell_on_node(base):
    out = copy.deepcopy(base)
    m = out["model"]
    donor = copy.deepcopy(m["cells"][0])
    donor["id"] = "cell_1"
    m["cells"].append(donor)
    wall = copy.deepcopy(next(p for p in m["membranes"] if p["id"] == "wall_cell_0"))
    wall.update(id="wall_cell_1", inside="cell_1")
    contact = copy.deepcopy(next(p for p in m["membranes"] if p["id"] == cf.PATCH))
    contact.update(id="contact_1", inside="cell_1")
    m["membranes"] += [wall, contact]
    x = out["experiment"]
    x["membrane_controls"] += [dict(membrane_id=p["id"], schedule=[dict(time=0.0,
                                                                         availability=1.0)])
                               for p in (wall, contact)]
    out["execution"]["capacity"] = len(m["cells"])
    out["execution"]["membrane_capacity"] = len(m["membranes"])
    return out


def _floating(base):
    """W with its owner's wall moved from the held bath to a finite node ecs_w, which a face joins
    to the bath: the owner's capacitor component floats, with no held bath and no gauge, and the
    compartment's node, declared before ecs_w, is its first outside node. It has one free field
    offset, so it declares field solver version 3 (D147), outright: `declare` would count the
    offsets by a parse, which refuses the world."""
    out = copy.deepcopy(base)
    m = out["model"]
    node = copy.deepcopy(next(o for o in m["extracellular"] if o["id"] == cf.NODE))
    m["extracellular"].append(node | dict(id="ecs_w"))
    next(p for p in m["membranes"] if p["id"] == cf.WALL)["outside"] = "ecs_w"
    face = dict(copy.deepcopy(_any_face()), id="face_w", sender="ecs_w", receiver="bath")
    face["diffusivity_m2_per_s"]["K"] = fx.D_S
    m["faces"].append(face)
    out["execution"]["extracellular_capacity"] = len(m["extracellular"])
    out["execution"]["face_capacity"] = len(m["faces"])
    return field_solver_choice.declare(out, "3")


def _replaced(events):
    """Two cells on the bath, cell_0 owning the compartment ecs_0, cell_1 beside a finite node
    ecs_1 and a junction between them; replacement@1's `events` (time, slot, template, new id)."""
    raw = fx.world(cells=(("cell_0", 1.0), ("cell_1", 1.0)),
                   nodes=(("ecs_0", 1.0), ("ecs_1", 1.0)),
                   contacts=(("contact_0", "cell_0", "ecs_0"), ("contact_1", "cell_1", "ecs_1")),
                   faces=(("face_1", "ecs_1", "bath", 1e-10, 1e-5),),
                   junctions=(("junction_0", "cell_0", "cell_1"),), end=0.01,
                   concentrations_mM=dict(cell_0=1e-3, cell_1=1e-3, ecs_0=1e-6, ecs_1=5e-4))
    template = fx.template(raw, "cell_1", "T", s_mM=1e-3)
    raw = fx.with_replacement(raw, [template], events)
    return cf.with_compartments(raw, [cf.compartment()])


def c1_refusals(name, context):
    from cells.execution.errors import NumericalError
    from cells.execution.runner import run

    del name
    started = time.perf_counter()
    out = {}
    for cls, (refused, admitted) in refusal_pairs().items():
        spec, message = admit(refused)
        rows = dict(refused=[dict(refused=spec is None, message=message,
                                  check=classify(message))], admitted=[])
        spec, message = admit(admitted)  # Short worlds: no quick horizon (replacement's event).
        ran = None
        if spec is not None:
            try:
                run(spec)
                ran = True
            except NumericalError as error:
                ran, message = False, str(error)
        rows["admitted"].append(dict(admitted=spec is not None, ran=ran, message=message))
        out[cls] = rows
    return dict(kind="refusals", admitted=True, completed=True, classes=out,
                wall_s=time.perf_counter() - started)


def _plant(plant, context):
    """One planted control in its own process (validation/tissue/compartment_acceptance_plants:
    the lead's ruling, so no plant reaches a judged world), its bundle read back."""
    import os

    directory = Path(tempfile.mkdtemp(prefix=f"plant-{plant}-", dir=context["out_dir"]))
    out = directory / f"{plant}.json"
    subprocess.run([sys.executable, "-B", "-m", "validation.tissue.compartment_acceptance_plants",
                    plant, str(out)], check=True, cwd=ROOT, env=dict(os.environ))
    bundle = json.loads(out.read_text())
    out.unlink()
    directory.rmdir()
    return bundle


def c13_controls(name, context):
    """C13: the misbooked move and the misbooked work, each in its own process."""
    del name
    started = time.perf_counter()
    plants = {plant: _plant(plant, context) for plant in ("move", "work")}
    return dict(kind="plants", admitted=True, completed=True, plants=plants,
                wall_s=time.perf_counter() - started)


def k3_planted(name, context):
    """K3: C9's planted controls (a K route and a compartment anchor through milestone 1's
    bypass), each in its own process, with S1 and S2 at every row."""
    del name
    started = time.perf_counter()
    plants = {plant: _plant(plant, context) for plant in ("route", "anchor")}
    return dict(kind="plants", admitted=True, completed=True, plants=plants,
                wall_s=time.perf_counter() - started)


def _series_of(amounts, floors=None):
    """{node: [T]} or {node: {species: [T]}} as the judge's series amount_SPECIES_NODE, plus the
    floor added when given (the floor world: the reference plus its own error bound)."""
    out = {}
    for node, value in amounts.items():
        by_species = value if isinstance(value, dict) else {fx.SPECIES: value}
        for species, series in by_species.items():
            series = np.asarray(series, dtype=float)
            if floors is not None:
                bound = floors[node]
                bound = bound[species] if isinstance(bound, dict) else bound
                series = series + np.asarray(bound, dtype=float)
            out[f"amount_{species}_{node}"] = series.tolist()
    return out


def references_part(name, context):
    """The references through their usage note's API only (validation/fr1/references/
    REFERENCES_USAGE.md: api.closed, api.step_map, api.linear and api.energy), on the references'
    copy of the inputs, which must equal the registered inputs (refused otherwise). In the
    judge's layout (compartment_acceptance_judge's docstring): worlds with their floor worlds,
    step_map by C4 rung, and energy by part."""
    from validation.fr1.references import api

    del name, context
    started = time.perf_counter()
    inputs = json.loads(REFERENCES_INPUTS.read_text())
    if inputs != json.loads(REGISTERED_INPUTS.read_text()):
        raise SystemExit("Refused: the references' copy of the inputs differs from the "
                         "registered inputs")
    constants = inputs["constants"]
    worlds = {}
    closed = inputs["R_closed"]["worlds"]
    for key, block in (("C3_flux", "C3_flux"), ("C3_first_order", "C3_first_order"),
                       ("C4", "C4_two_way"), ("C5", "C5_saturable")):
        r = api.closed(closed[block])
        t = [float(x) for x in r["times_s"]]
        worlds[key] = dict(record_s=t, series=_series_of(r["amount_fmol"]),
                           x_eq=r.get("x_eq"))
        worlds[key + "_floor"] = dict(record_s=t,
                                      series=_series_of(r["amount_fmol"], r["floor_fmol"]))
    linear = inputs["R_linear"]["worlds"]
    for key, block in (("C6", "C6_load_and_degrade"), ("C7", "C7_load_and_react"),
                       ("C8", "C8_uptake_path")):
        r = api.linear(linear[block])
        t = [float(x) for x in r["times_s"]]
        series = _series_of(r["amount_fmol"])
        if "cleared_fmol" in r:
            series[f"cleared_{af.NODE}_fmol"] = [float(x) for x in r["cleared_fmol"]]
        moiety = r.get("moiety_fmol")
        worlds[key] = dict(record_s=t, series=series,
                           moiety_fmol=[] if moiety is None else [float(x) for x in moiety])
        worlds[key + "_floor"] = dict(record_s=t,
                                      series=_series_of(r["amount_fmol"], r["floor_fmol"]))
    step_map = {}
    for rung, block in inputs["R_step_map"]["worlds"].items():
        r = api.step_map(block)
        step_map[f"C4_rung_{dt_key(float(rung))}"] = dict(
            record_s=[float(x) for x in r["times_s"]], series=_series_of(r["amount_fmol"]),
            x_star=float(r["x_star"]), x_eq=float(r["x_eq"]),
            rounding_allowance_fmol=float(r["rounding_allowance_fmol"]),
            splitting={k: float(v) for k, v in r["splitting"].items()})
    energy = {}
    for world, block in inputs["R_energy"]["worlds"].items():
        r = api.energy(block, constants)
        energy[ENERGY_PARTS[world]] = dict(
            record_s=[float(x) for x in r["times_s"]] if "times_s" in r else
            [float(x) for x in block["record_times_s"]],
            dG_pJ=[float(x) for x in r["dG_pJ"]],
            series=_series_of(r["amount_fmol"]) if "amount_fmol" in r else {})
    return dict(kind="reference", admitted=True, completed=True, worlds=worlds,
                step_map=step_map, energy=energy, inputs_equal_registered=True,
                wall_s=time.perf_counter() - started)


def stand_in(name, context):
    del context
    raise SystemExit(f"{name} is a stand-in (STAND_INS)")


FUNCTIONS = {
    "C1_refusals": c1_refusals, "C2_identity": c2_identity,
    "C3_flux": _engine(af.flux_loading), "C3_first_order": _engine(af.first_order_loading),
    **{n: _rung(af.two_way, dt) for n, dt in C4_RUNGS.items()},
    "C5_saturable": _engine(af.saturable_release),
    **{n: _rung(af.load_and_degrade, dt) for n, dt in C6_RUNGS.items()},
    **{n: _rung(af.load_and_react, dt) for n, dt in C7_RUNGS.items()},
    **{n: _rung(af.uptake_path, dt) for n, dt in C8_RUNGS.items()},
    "C9_silence": c9_silence, "C10_rk4": c10_rk4,
    **{n: _c11(law, solver) for n, (law, solver) in C11_PARTS.items()},
    "C12_restart": c12_restart, "C12_batch": c12_batch,
    "K1_one_way": k1_one_way, "K2_no_clearance": k2_no_clearance,
    "C13_controls": c13_controls, "K3_planted": k3_planted, "references": references_part,
}


def run_parts(requested, out_dir, *, status, quick_horizon):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True)
    record = dict(protocol_id=PROTOCOL_ID, status=status, source=snapshot_identity(),
                  requested_parts=list(requested), quick=quick_horizon,
                  stand_ins=blocking_stand_ins(requested), parts={}, complete=False)
    path = out_dir / "results.json"
    context = dict(quick=quick_horizon, out_dir=str(out_dir))
    for name in requested:
        started = time.perf_counter()
        value = FUNCTIONS[name](name, context)
        value["seconds"] = time.perf_counter() - started
        record["parts"][name] = plain(value)
        path.write_text(json.dumps(record, indent=1, allow_nan=False) + "\n")
    record["complete"] = True
    path.write_text(json.dumps(record, indent=1, allow_nan=False) + "\n")
    return record


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("mode", choices=("dev", "judged"))
    parser.add_argument("args", nargs="+")
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args(argv)
    if args.mode == "judged":
        if len(args.args) < 3:
            raise SystemExit("judged PROTOCOL_JSON OUT_DIR PART [PART ...]")
        protocol = json.loads(Path(args.args[0]).read_text())
        out_dir, parts = args.args[1], args.args[2:]
        why = judged_run_refusal(protocol)
        status = "Judged run of " + PROTOCOL_ID
    else:
        out_dir, parts = args.args[0], args.args[1:]
        why, status = None, "Development run of " + PROTOCOL_ID + " (not a judged run)"
    why = why or refusal_before_writing(parts, out_dir, judged=args.mode == "judged",
                                        quick=args.quick)
    if why:
        raise SystemExit("Refused: " + why)
    run_parts(parts, out_dir, status=status, quick_horizon=args.quick)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
