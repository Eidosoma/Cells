"""fr10-dose-schedule-v1's generator: the protocol's parts, as records (FR-10, D216).

The protocol is validation/tissue/bath_schedule_protocol.json; its worlds are
validation/tissue/bath_schedule_fixtures' builders. The generator writes records and computes no
verdict; the judge (validation/tissue/bath_schedule_judge.py) reads them. Each part is its own unit
(OUT_DIR/results.json), and the judge merges the units (MG0c's form, as FR-4's and FR-5's).

Parts (the protocol's judged_parts):
* W1_rung_1ms ... W1_rung_0p125ms: W1 (chain_world) at each dt of the ladder; W1_control: W1 with
  the operator and no event (K1);
* W2_rung_1ms ... W2_rung_0p125ms: W2 (ion_world); W2_control: no event (K2);
* W3_rk4: the ledgers across an event under RK4, every row (with K3's quantity, @3's own
  reservoir-work ledger without the operator's term);
* W4_idle: the operator with no event against the composition without it, bitwise, and K4's
  planted one-ulp pair;
* W5_restart: W1 straight and resumed through the engine's checkpoint (cells.records.io.write_snapshot and
  load_snapshot, within this run's snapshot) from 0.5, 1 and 1.5 s, and K5's moved event;
  W5_batch: three schedules on one bath in a vector batch against each in a batch of one;
* W6_water: the isosmotic step beside water@1; W7_staircase_ars, W7_staircase_rk4: the six-stair
  dose from the trace;
* refusals: every refusal class (refusal_classes) refused at the definition, its reason
  classified from the message, and its neighbour admitted and run;
* references: R-faces, R-ion and R-records, the FR references agent's (validation/fr10/references,
  through its usage note's API only, REFERENCES_USAGE.md), on the registered inputs; it reads
  W3_rk4's records (--w3 OUT/W3_rk4/results.json) for R-records' K from W3's own supply, so it runs
  after W3_rk4.

Each run part records, at every observation time: every node's amount of every species
(amount_SPECIES_NODE, fmol), every patch's voltage (V_PATCH, V), the energy residual and the
integrated flows of @3's energy ledger (energy_residual_pJ, energy_flows_pJ), each ledger's largest
|balance| over its bound (ratio_LEDGER), the reservoir-work ledger at the scheduled bath with the
operator's term, its bound and @3's own ledger without the term, and the operator's records at the
bath (the held content, the dose, its free-energy change, the compensation charge).

Modes:
  python -m validation.tissue.bath_schedule_qualification dev OUT_DIR PART [PART ...] [--quick]
  python -m validation.tissue.bath_schedule_qualification judged PROTOCOL_JSON OUT_DIR PART
      [PART ...]
A judged run is refused, before anything is computed or written, unless the protocol is registered
(its status and its registration record), the source is a clean execution snapshot, no stand-in
blocks a requested part, and OUT_DIR is new (D150's and MG0c's guard). `--quick` (development
only) runs every engine world to QUICK_FRACTION of its horizon, events kept inside it.
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

from validation.tissue import bath_schedule_fixtures as bfx
from validation.tissue import secreted_species_fixtures as fx

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "validation" / "tissue" / "bath_schedule_protocol.json"
PROTOCOL_ID = "fr10-dose-schedule-v1"
QUICK_FRACTION = 0.4
LADDER_S = (1e-3, 5e-4, 2.5e-4, 1.25e-4)


def dt_key(dt):
    """1e-3 -> '1ms', 1.25e-4 -> '0p125ms'."""
    return f"{dt * 1e3:g}".replace(".", "p") + "ms"


W1_RUNGS = {f"W1_rung_{dt_key(dt)}": dt for dt in LADDER_S}
W2_RUNGS = {f"W2_rung_{dt_key(dt)}": dt for dt in LADDER_S}
PARTS = (
    *W1_RUNGS, "W1_control", *W2_RUNGS, "W2_control", "W3_rk4", "W4_idle", "W5_restart",
    "W5_batch", "W6_water", "W7_staircase_ars", "W7_staircase_rk4", "refusals", "references",
)
RESTART_TIMES_S = (0.5, 1.0, 1.5)
# What remains a stand-in, and the parts each blocks: none since the FR references agent's
# references landed (branch fr10-references, 23b8ff58, merged 17 November 2026).
STAND_INS = {}
STAND_IN_PARTS = {}
REFERENCES_INPUTS = ROOT / "validation" / "fr10" / "references" / "reference_inputs.json"
REGISTERED_INPUTS = ROOT / "validation" / "bath_schedule" / "reference_inputs.json"
# The checks a refusal may name (refusal_classes' `check`), by a phrase of their messages.
# "the species cap" names no class since R9_the_species_cap's retirement (the lead's ruling,
# 23 November 2026); its phrase still names the cap's check, now at 1,024 (FR-43, D315).
CHECKS = (
    ("the step rule (solver and dt)", "dose steps are measured only under"),
    ("the step rule (face)", "steps are measured only beside faces"),
    ("the step rule (region)", "lies outside the measured region"),
    ("the species cap", "species per world"),
    ("the neutrality rule (integer charge)", "carries a net charge"),
    ("the isosmotic rule", "is anisosmotic"),
    ("@3's explicit-rate bound", "exceeds the explicit-rate stability bound"),
    ("the held-bath rule", "schedules held baths only"),
)


def classify(message):
    """The check a refusal message names, or None."""
    for check, phrase in CHECKS:
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
    executed_sources.refuse_untracked(root, "bath_schedule_qualification's source record")  # D259

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
    """The world to QUICK_FRACTION of its horizon (on its dt grid), its events kept before it."""
    out = copy.deepcopy(raw)
    x, dt = out["experiment"], out["execution"]["dt"]
    end = max(dt, round(QUICK_FRACTION * x["end_time"] / dt) * dt)
    x["end_time"] = end
    x["observation_times"] = sorted({t for t in x["observation_times"] if t < end} | {end})
    if "bath_composition_events" in x:
        x["bath_composition_events"] = [e for e in x["bath_composition_events"]
                                        if e["time"] < end]
    out["execution"]["max_steps"] = int(math.ceil(end / dt)) + 8
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


def records_of(result):
    """Every observation time's series (module docstring) from a runner result."""
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
    cells = [c.id for c in m.cells]
    outside = [c.id for c in m.extracellular]
    patches = [mb.id for mb in m.membranes]
    scheduled = [k for k, c in enumerate(m.extracellular) if c.reservoir]
    baths = [k for k in scheduled if bool(np.asarray(p.bath_scheduled)[k])] if hasattr(
        p, "bath_scheduled") else []
    series = {}

    def add(name, value):
        series.setdefault(name, []).append(float(value))

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
        for s_, sid in enumerate(species):
            for c_, cid in enumerate(cells):
                add(f"amount_{sid}_{cid}", np.asarray(obs.amount)[j, s_, c_])
            for o_, oid in enumerate(outside):
                add(f"amount_{sid}_{oid}", np.asarray(obs.extracellular_amount)[j, s_, o_])
        for k, pid in enumerate(patches):
            add(f"V_{pid}", np.asarray(obs.membrane_voltage_V)[j, k])
        if baths:
            b = baths[0]
            own = model.inner.balances(model.inner.inner_state(row), model.inner.inner_layout(p))
            r = names.index("reservoir_work")
            add("reservoir_work_pJ", np.asarray(balances["reservoir_work"])[b])
            add("reservoir_work_bound_pJ", (np.asarray(bounds[r]) * np.ones(len(outside)))[b])
            add("reservoir_work_own_pJ", np.asarray(own["reservoir_work"])[b])
            # K, the operator's reconciliation term: its ledger term takes K from @3's balance.
            add("bath_reconciliation_pJ", np.asarray(own["reservoir_work"])[b]
                - np.asarray(balances["reservoir_work"])[b])
            supplied = np.asarray(model.inner.inner_state(row).reservoir_supplied)
            for s_, sid in enumerate(species):
                add(f"supplied_{sid}_fmol", supplied[s_, b])  # @3's cumulative supply S_s.
            for s_, sid in enumerate(species):
                add(f"bath_held_{sid}_fmol", np.asarray(obs.bath_held_amount_fmol)[j, s_, b])
                add(f"bath_dose_{sid}_fmol", np.asarray(obs.bath_dose_fmol)[j, s_, b])
            add("bath_dose_free_energy_pJ", np.asarray(obs.bath_dose_free_energy_pJ)[j, b])
            add("bath_compensation_charge_C", np.asarray(obs.bath_compensation_charge_C)[j, b])
    return dict(record_s=[float(t) for t in obs_times], series=series,
                ledgers=sorted(names), diagnostics=dict(result.diagnostics),
                bath=outside[baths[0]] if baths else None, species=species, cells=cells,
                outside=outside, patches=patches,
                valences=dict(zip(species, (int(v) for v in m.valence), strict=True)))


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
        return dict(out, admitted=True, completed=False, refusal=str(error), refusal_check=None,
                    wall_s=time.perf_counter() - started)
    record = records_of(result)
    return dict(out, admitted=True, completed=True, refusal=None, refusal_check=None,
                timings={k: float(v) for k, v in result.timings.items()},
                wall_s=time.perf_counter() - started, **record)


# ------------------------------------------------------------------ comparisons (W4, W5)


def compare_results(a, b, *, start=None):
    """Two runner results bit for bit (validation.tissue.composite_guard's compare_arrays): every
    history field, observation column and max_ diagnostic; with `start`, only from that time on
    (a restart against the straight run). Returns dict(equal, first, compared)."""
    from validation.tissue.composite_guard import compare_arrays

    ta, tb = np.asarray(a.times), np.asarray(b.times)
    ia = 0 if start is None else int(np.argmin(np.abs(ta - start)))
    ib = 0 if start is None else int(np.argmin(np.abs(tb - start)))
    differences = []
    if not np.array_equal(ta[ia:], tb[ib:]):
        differences.append(dict(field="times"))
    for name in type(a.history)._fields:
        d = compare_arrays("history." + name, np.asarray(getattr(a.history, name))[ia:],
                           np.asarray(getattr(b.history, name))[ib:])
        if d is not None:
            differences.append(d)
    oa, ob = np.asarray(a.observations.times), np.asarray(b.observations.times)
    ja = 0 if start is None else int(np.searchsorted(oa, start - 1e-12))
    jb = 0 if start is None else int(np.searchsorted(ob, start - 1e-12))
    for name in vars(a.observations):
        d = compare_arrays("observations." + name, np.asarray(getattr(a.observations, name))[ja:],
                           np.asarray(getattr(b.observations, name))[jb:])
        if d is not None:
            differences.append(d)
    if start is None:
        for key, value in a.diagnostics.items():
            if key.startswith("max_") and b.diagnostics.get(key) != value:
                differences.append(dict(field="diagnostics." + key))
    return dict(equal=not differences, first=differences[0] if differences else None,
                differences=len(differences))


def w4_idle(name, context):
    from cells.execution.runner import run

    del name
    started = time.perf_counter()
    raws = dict(with_operator=bfx.chain_world(events=False),
                without=bfx.chain_world(events=False, operator=False))
    planted = copy.deepcopy(raws["without"])
    bath = next(n for n in planted["model"]["extracellular"] if n["id"] == "bath")
    bath["initial_amount_fmol"][fx.SPECIES] = float(
        np.nextafter(bath["initial_amount_fmol"][fx.SPECIES], np.inf))
    raws["planted"] = planted
    if context["quick"]:
        raws = {k: quick(v) for k, v in raws.items()}
    results, admitted = {}, {}
    for key, raw in raws.items():
        spec, refusal = admit(raw)
        admitted[key] = refusal
        results[key] = None if spec is None else run(spec)
    ok = all(r is not None for r in results.values())
    return dict(
        kind="comparison", admitted=ok, completed=ok, refusals=admitted,
        idle=compare_results(results["without"], results["with_operator"]) if ok else None,
        planted=compare_results(results["planted"], results["with_operator"]) if ok else None,
        wall_s=time.perf_counter() - started)


def _restart(raw, at, workdir):
    """raw run to `at` (truncated), its checkpoint written and loaded through cells.records.io, and the
    full definition resumed from it (cells.execution.runner.branch_checkpoint)."""  # noqa: E501
    from cells.definitions.specs import parse_spec
    from cells.execution.runner import branch_checkpoint, run
    from cells.records.io import load_snapshot, write_snapshot

    first = run(parse_spec(bfx.truncated(raw, at)))
    directory = Path(workdir) / f"checkpoint-{at:g}"
    directory.parent.mkdir(parents=True, exist_ok=True)
    write_snapshot(directory, first.spec, first.final)
    snapshot = load_snapshot(directory)
    full = parse_spec(raw)
    return run(full, branch_checkpoint(snapshot.spec, snapshot.checkpoint, full))


def w5_restart(name, context):
    from cells.definitions.specs import parse_spec
    from cells.execution.runner import run

    del name
    started = time.perf_counter()
    raw = bfx.chain_world()
    moved = copy.deepcopy(raw)
    for event in moved["experiment"]["bath_composition_events"]:
        if abs(event["time"] - 1.0) < 1e-12:
            event["time"] = bfx.on_grid(1.0 + raw["execution"]["dt"], raw["execution"]["dt"])
    if context["quick"]:
        raw, moved = quick(raw), quick(moved)
    straight = run(parse_spec(raw))
    out = {}
    with tempfile.TemporaryDirectory(dir=context["out_dir"]) as workdir:
        for at in RESTART_TIMES_S:
            if at >= raw["experiment"]["end_time"]:
                continue
            out[f"{at:g}"] = compare_results(straight, _restart(raw, at, workdir), start=at)
        planted = _restart(moved, 1.0, Path(workdir) / "moved") if (
            1.0 < raw["experiment"]["end_time"]) else None
    return dict(kind="comparison", admitted=True, completed=True, restarts=out,
                planted=None if planted is None else compare_results(straight, planted, start=1.0),
                wall_s=time.perf_counter() - started)


def w5_batch(name, context):
    """Three schedules on one bath in one vector batch (cells.execution.batch, run_vector_windowed),
    each against itself in a batch of one: the final state and every observation, bit for bit."""
    from cells.definitions.specs import parse_spec
    from cells.execution.batch import BatchSpec, WorldSpec
    from cells.execution.vector_windows import run_vector_windowed
    from cells.execution.windows import WindowPolicy

    del name
    started = time.perf_counter()
    raws = bfx.batch_worlds()
    if context["quick"]:
        raws = [quick(r) for r in raws]
    specs = [parse_spec(r) for r in raws]

    def run_cohort(worlds):
        cohort = BatchSpec(tuple(WorldSpec(i + 1, s) for i, s in enumerate(worlds)), len(worlds),
                           10**8, 2**33)
        collected = {}

        def sink(window):
            for identity, found in window.observations.items():
                collected.setdefault(identity, []).append(found)

        result = run_vector_windowed(cohort, WindowPolicy(10**6, "observations"), sink=sink)
        return result, collected

    batch, batch_observations = run_cohort(specs)
    out = {}
    for i, spec in enumerate(specs):
        alone, alone_observations = run_cohort([spec])
        out[f"world_{i + 1}"] = _compare_worlds(
            alone.worlds[1], alone_observations[1], batch.worlds[i + 1], batch_observations[i + 1])
    return dict(kind="comparison", admitted=True, completed=True, worlds=out,
                wall_s=time.perf_counter() - started)


def _compare_worlds(a, a_observations, b, b_observations):
    from validation.tissue.composite_guard import compare_arrays

    differences = []
    for name in type(a.final.state)._fields:
        d = compare_arrays("final." + name, getattr(a.final.state, name),
                           getattr(b.final.state, name))
        if d is not None:
            differences.append(d)
    if len(a_observations) != len(b_observations):
        differences.append(dict(field="observation windows"))
    for x, y in zip(a_observations, b_observations, strict=False):
        for name in vars(x):
            d = compare_arrays("observations." + name, getattr(x, name), getattr(y, name))
            if d is not None:
                differences.append(d)
    for key, value in a.diagnostics.items():
        if key.startswith("max_") and b.diagnostics.get(key) != value:
            differences.append(dict(field="diagnostics." + key))
    return dict(equal=not differences, first=differences[0] if differences else None,
                differences=len(differences))


def refusals_part(name, context):
    """Every refusal class: its representative(s) refused, with the check the message names, and
    its neighbour(s) admitted and run (R12 adds the declared composition alone at 1 ms)."""
    from cells.execution.errors import NumericalError
    from cells.execution.runner import run

    del name
    started = time.perf_counter()
    out = {}
    for cls, (refused, admitted) in bfx.refusal_pairs().items():
        refused = refused if isinstance(refused, list) else [refused]
        admitted = admitted if isinstance(admitted, list) else [admitted]
        rows = dict(refused=[], admitted=[])
        for raw in refused:
            spec, message = admit(raw)
            rows["refused"].append(dict(refused=spec is None, message=message,
                                        check=classify(message)))
        for raw in admitted:
            raw = quick(raw) if context["quick"] else raw
            spec, message = admit(raw)
            ran = None
            if spec is not None:
                try:
                    run(spec)
                    ran = True
                except NumericalError as error:
                    ran, message = False, str(error)
            rows["admitted"].append(dict(admitted=spec is not None, ran=ran, message=message))
        out[cls] = rows
    spec, message = admit(bfx.bound_world(events=False))
    out["R12_beyond_the_explicit_bound"]["declared_alone_at_1ms"] = dict(
        admitted=spec is not None, message=message)
    return dict(kind="refusals", admitted=True, completed=True, classes=out,
                wall_s=time.perf_counter() - started)


def references_part(name, context):
    """The references through their usage note's API only (validation/fr10/references/
    REFERENCES_USAGE.md): faces.reference, ion.reference, records.event_records and
    records.reconciliation_K, on the references' copy of the inputs, which must equal the
    registered inputs (refused otherwise). In the judge's layout (bath_schedule_judge's
    docstring): W1 and W2 at every record, each with a floor world (the reference plus its own
    error bound, so the judge's floor difference is that bound); the event records; and K_W3 from
    W3_rk4's own recorded supply (context["w3_results"]), with that supply kept beside it so the
    judge can check it is W3's."""
    from validation.fr10.references import faces, ion, records

    del name
    started = time.perf_counter()
    inputs = json.loads(REFERENCES_INPUTS.read_text())
    if inputs != json.loads(REGISTERED_INPUTS.read_text()):
        raise SystemExit("Refused: the references' copy of the inputs differs from the "
                         "registered inputs")
    constants = inputs["constants"]
    f = faces.reference(inputs["R_faces"])
    t1 = [float(t) for t in f["times_s"]]
    amounts, bound = np.asarray(f["amount_fmol"]), np.asarray(f["floor_fmol"])
    nodes = list(f["nodes"])
    w1 = {f"amount_S_{n}": amounts[:, k].tolist() for k, n in enumerate(nodes)}
    w1_floor = {f"amount_S_{n}": (amounts[:, k] + bound[:, k]).tolist()
                for k, n in enumerate(nodes)}
    i = ion.reference(inputs["R_ion"], constants)
    t2 = [float(t) for t in i["times_s"]]
    v, v_floor = np.asarray(i["V_m_V"]), np.asarray(i["floor"]["V_m_V"])
    w2 = {"V_wall_cell_0": v.tolist()}
    w2_floor = {"V_wall_cell_0": (v + v_floor).tolist()}
    for species, series in i["amount_fmol"].items():
        w2[f"amount_{species}_cell_0"] = [float(x) for x in series]
        extra = np.asarray(i["floor"]["amount_fmol"][species])
        w2_floor[f"amount_{species}_cell_0"] = (np.asarray(series) + extra).tolist()
    event_records = {}
    for world in ("W1", "W2", "W3"):
        event_records[world] = [
            dict(time_s=float(e["time_s"]), dose_fmol={k: float(x) for k, x in
                                                        e["dose_fmol"].items()},
                 free_energy_pJ=float(e["dG_b_pJ"]), charge_C=float(e["charge_C"]))
            for e in records.event_records(inputs["R_records"]["worlds"][world], constants)]
    w3 = json.loads(Path(context["w3_results"]).read_text())["parts"]["W3_rk4"]
    if w3.get("completed") is not True:
        raise SystemExit("Refused: W3_rk4's records are incomplete")
    supply = {sid: w3["series"][f"supplied_{sid}_fmol"] for sid in w3["species"]}
    k = records.reconciliation_K(inputs["R_records"]["worlds"]["W3"], w3["record_s"], supply,
                                 constants)
    return dict(
        kind="reference", admitted=True, completed=True,
        worlds=dict(W1=dict(record_s=t1, series=w1), W1_floor=dict(record_s=t1, series=w1_floor),
                    W2=dict(record_s=t2, series=w2), W2_floor=dict(record_s=t2, series=w2_floor)),
        records=event_records,
        K_W3=dict(record_s=[float(t) for t in k["times_s"]],
                  series=dict(K_pJ=[float(x) for x in k["K_pJ"]]),
                  floor_pJ=[float(x) for x in k["floor_pJ"]], supply_fmol=supply),
        reported=dict(zero_current_V=[float(x) for x in i["zero_current_V"]],
                      W1_supply_fmol=[float(x) for x in f["supply_fmol"]]),
        inputs_equal_registered=True, w3_results=str(context["w3_results"]),
        w3_results_sha256=hashlib.sha256(Path(context["w3_results"]).read_bytes()).hexdigest(),
        wall_s=time.perf_counter() - started)


# ------------------------------------------------------------------ the parts


def _rung(world, dt):
    return bfx.chain_world(dt=dt) if world == "W1" else bfx.ion_world(dt=dt)


FUNCTIONS = {
    **{n: (lambda name, ctx, dt=dt: engine_part(_rung("W1", dt), ctx, label=name))
       for n, dt in W1_RUNGS.items()},
    "W1_control": lambda name, ctx: engine_part(bfx.chain_world(events=False), ctx, label=name),
    **{n: (lambda name, ctx, dt=dt: engine_part(_rung("W2", dt), ctx, label=name))
       for n, dt in W2_RUNGS.items()},
    "W2_control": lambda name, ctx: engine_part(bfx.ion_world(events=False), ctx, label=name),
    "W3_rk4": lambda name, ctx: engine_part(bfx.ledger_world(), ctx, label=name),
    "W4_idle": w4_idle,
    "W5_restart": w5_restart,
    "W5_batch": w5_batch,
    "W6_water": lambda name, ctx: engine_part(
        bfx.water_world({"NaM": -10.0, "KM": 10.0}), ctx, label=name),
    "W7_staircase_ars": lambda name, ctx: engine_part(bfx.staircase_world(), ctx, label=name),
    "W7_staircase_rk4": lambda name, ctx: engine_part(
        bfx.staircase_world(solver=bfx.RK4), ctx, label=name),
    "refusals": refusals_part,
    "references": references_part,
}


def run_parts(requested, out_dir, *, status, quick_horizon=False, w3_results=None):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True)
    results = dict(status=status, protocol_id=PROTOCOL_ID, source=snapshot_identity(),
                   requested_parts=list(requested), complete=False, quick=quick_horizon,
                   stand_ins=blocking_stand_ins(PARTS), parts={})
    context = dict(quick=quick_horizon, out_dir=out_dir, w3_results=w3_results)
    for name in [p for p in PARTS if p in requested]:
        started = time.perf_counter()
        value = FUNCTIONS[name](name, context)
        value["seconds"] = time.perf_counter() - started
        results["parts"][name] = value
        (out_dir / "results.json").write_text(json.dumps(plain(results), allow_nan=True) + "\n")
    results["complete"] = True
    (out_dir / "results.json").write_text(json.dumps(plain(results), allow_nan=True) + "\n")
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=("dev", "judged"))
    parser.add_argument("rest", nargs="+")
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--w3", help="W3_rk4's results.json, for the references part's K")
    args = parser.parse_args(argv)
    if args.mode == "judged":
        protocol = json.loads(Path(args.rest[0]).read_text())
        out_dir, parts = args.rest[1], args.rest[2:]
        why = judged_run_refusal(protocol)
        status = "Judged run of " + str(protocol.get("id"))
    else:
        out_dir, parts = args.rest[0], args.rest[1:]
        why, status = None, "Development run"
    if why is None:
        why = refusal_before_writing(parts, out_dir, judged=args.mode == "judged",
                                     quick=args.quick)
    if why is None and "references" in parts and not (args.w3 and Path(args.w3).exists()):
        why = ("the references part reads W3_rk4's records for K: pass --w3 "
               "OUT/W3_rk4/results.json, from the same source")
    if why:
        raise SystemExit("Refused: " + why)
    run_parts(parts, out_dir, status=status, quick_horizon=args.quick, w3_results=args.w3)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
