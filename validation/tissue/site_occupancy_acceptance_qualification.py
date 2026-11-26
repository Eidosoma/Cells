"""fr3-site-occupancy-v1's generator: the protocol's parts, as records (FR-3, D216).

The protocol is validation/tissue/site_occupancy_acceptance_protocol.json; its worlds are the
references' registered worlds, built by validation/tissue/site_occupancy_acceptance_fixtures (the
engine-layout adapter). The generator writes records and computes no verdict; the judge
(validation/tissue/site_occupancy_acceptance_judge.py) reads them. Each part is its own unit
(OUT_DIR/results.json), and the judge merges the units (MG0c's form, as FR-4's, FR-5's, FR-10's
and FR-1's).

Parts (the protocol's judged_parts):
* every registered world but q1_fast at the declared 1 ms, by its world id (q1_eps_1e-1, ...);
* q1_fast_rung_1ms, q1_fast_rung_0p5ms, q1_fast_rung_0p25ms: Q1's dt study on the references'
  ladder (the lead's ruling: the orders on q1_fast);
* the control worlds (declared variants, run by the engine): K_rates, K_alpha,
  K_binding_multiplier, K_internalisation_multiplier, K_cell_volume, Q4_kinetic, Q4_affinity;
* Q5_material_plants (move, bound) and Q5_energy_plants (work, heat_sign, site_free_energy):
  checkpoint edits, each in its own process (validation/tissue/site_occupancy_acceptance_plants);
* Q6_restart, Q6_batch, Q6_idle, Q6_twins, Q6_signature, Q6_refusals;
* references: the FR references agent's, through its usage note only (validation/fr3/references/
  REFERENCES_USAGE.md: api.reference and api.accessibility), on the registered inputs.
Development only (never judged): the dt study's slow ladders, dt_WORLD_rung_DT for the
references' stand-in worlds at 0.5 and 0.25 ms (their 1 ms rung is the world's own part).

Each engine run records, at every observation time (record_ms: integer milliseconds): the ligand's
amount at every cell and finite node (amount_NODE, fmol); each population's bound and free sites,
internalised and net-bound amounts, work and energy magnitude (B_POP, R_POP, internalised_POP,
net_POP, work_POP_pJ, magnitude_POP_pJ); the heat at every cell and finite node (heat_NODE_pJ) and
in total (heat_pJ), the total work (work_pJ); the energy ledger's residual, magnitude, integrated
flows and bound (energy_residual_pJ, energy_magnitude_pJ, energy_flows_pJ, energy_bound_pJ); and
every ledger's largest |balance| over the engine's bound (ratio_LEDGER). Beside them: the layout
(volumes, capacities, K_d, facing and receiving nodes) and the IDs the definition prints.

Modes:
  python -m validation.tissue.site_occupancy_acceptance_qualification dev OUT_DIR PART [PART ...]
      [--quick]
  python -m validation.tissue.site_occupancy_acceptance_qualification judged PROTOCOL_JSON OUT_DIR
      PART [PART ...]
A judged run is refused, before anything is computed or written, unless the protocol is registered
(its status and its registration record), the source is a clean execution snapshot, no stand-in
blocks a requested part, only judged parts are requested, and OUT_DIR is new (D150's and MG0c's
guard). `--quick` (development only, to test the tools) runs every engine world to QUICK_FRACTION
of its horizon, keeping the schedule changes before it; the dt study and rehearsals run in full.
"""

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

from validation.tissue import site_occupancy_acceptance_fixtures as af

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "validation" / "tissue" / "site_occupancy_acceptance_protocol.json"
PROTOCOL_ID = "fr3-site-occupancy-v1"
QUICK_FRACTION = 0.4
EPS = 2.0**-52
LIGAND = af.LIGAND


def dt_key(dt):
    """1e-3 -> '1ms', 2.5e-4 -> '0p25ms'."""
    return f"{dt * 1e3:g}".replace(".", "p") + "ms"


LADDER_PARTS = {f"{af.LADDER_WORLD}_rung_{dt_key(dt)}": dt for dt in af.LADDER_S}
WORLD_PARTS = tuple(w for w in af.world_ids() if w != af.LADDER_WORLD)
CONTROL_PARTS = ("K_rates", "K_alpha", "K_binding_multiplier", "K_internalisation_multiplier",
                 "K_cell_volume", "Q4_kinetic", "Q4_affinity")
PLANT_PARTS = {"Q5_material_plants": ("move", "bound"),
               "Q5_energy_plants": ("work", "heat_sign", "site_free_energy")}
Q6_PARTS = ("Q6_restart", "Q6_batch", "Q6_idle", "Q6_twins", "Q6_signature", "Q6_refusals")
PARTS = (*WORLD_PARTS, *LADDER_PARTS, *CONTROL_PARTS, *PLANT_PARTS, *Q6_PARTS, "references")
DT_STUDY_WORLDS = ("q1_eps_1e-1", "q2_closed", "q3_internalisation", "q5_washout")
DEV_PARTS = {f"dt_{w}_rung_{dt_key(dt)}": (w, dt) for w in DT_STUDY_WORLDS
             for dt in af.LADDER_S[1:]}
# Q6_restart: q5_class_switch around its 5 s switch-on; K4 moves the switch one step later.
RESTART_WORLD, RESTART_TIMES_S, SWITCH_S = "q5_class_switch", (4.0, 5.0, 6.0), 5.0
IDLE_WORLD, IDLE_END_S = "q5_inward", 0.1
Q4_ALPHAS = (0.5, 0.25)
Q4_REGIMES = ("low", "high")
# What remains a stand-in, and the parts each blocks.
STAND_INS = {}
STAND_IN_PARTS = {}


# ------------------------------------------------------------------ provenance and guards


def snapshot_identity(root=None):
    root = ROOT if root is None else root
    manifest = Path(root) / "SNAPSHOT.json"
    if manifest.exists():
        snapshot = json.loads(manifest.read_text())
        return dict(kind="snapshot", git_revision=snapshot.get("git_revision"),
                    patch_sha256=snapshot.get("patch_sha256"), status=snapshot.get("status"))

    from validation import executed_sources  # noqa: PLC0415
    executed_sources.refuse_untracked(  # D259
        root, "site_occupancy_acceptance_qualification's source record"
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
    known = set(PARTS) if judged else set(PARTS) | set(DEV_PARTS)
    unknown = sorted(set(requested) - known)
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


def git_blob(data):
    """git's blob identity of a file's bytes (hash-object): the references' design file records
    their inputs' blob."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def ms(t):
    """A record time in integer milliseconds (records align on these, never by float equality)."""
    return int(round(t / af.RECORD_UNIT_S))


# ------------------------------------------------------------------ worlds, quick horizons


def quick(raw):
    """The world to QUICK_FRACTION of its horizon (on its dt grid), its schedule changes kept
    before it (development only, to test the tools)."""
    out = copy.deepcopy(raw)
    x, dt = out["experiment"], out["execution"]["dt"]
    end = max(dt, round(QUICK_FRACTION * x["end_time"] / dt) * dt)
    x["end_time"] = end
    x["observation_times"] = sorted({t for t in x["observation_times"] if t < end} | {end})
    for control in x.get("site_controls", []):
        control["schedule"] = [c for c in control["schedule"] if c["time"] < end]
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


def ids_of(spec):
    """The IDs the definition prints: the composite, its inner model, the closure, the patches'
    laws, the operators with their steps and laws, the solver and the field solver."""
    from cells.operators import OPERATORS
    from cells.operators import site_occupancy as so

    d = spec.to_dict()
    m, x = d["model"], d["execution"]
    found = {m.get("id"), m.get("inner_model"), (m.get("closure") or {}).get("law"),
             x.get("solver"), x.get("field_solver")}
    found |= {p.get("law") for p in m.get("membranes", [])}
    found |= {f.get("law") for f in m.get("faces", [])}
    found |= {j.get("law") for j in m.get("junctions", [])}
    for op in m.get("operators", []):
        found.add(op["law"])
        step = getattr(OPERATORS.get(op["law"]), "STEP_ID", None)
        if step:
            found.add(step)
        if op["law"] == so.LAW_ID:
            found.add(so.BINDING_LAW)
            if any(p.get("internalisation") for p in op["populations"]):
                found.add(so.INTERNALISATION_LAW)
    return sorted(i for i in found if isinstance(i, str))


def _row(model, history, i):
    return model.STATE_TYPE(*(np.asarray(v)[i] for v in history))


def _ratio(balance, bound):
    balance, bound = np.abs(np.asarray(balance, dtype=float)), np.asarray(bound, dtype=float)
    bound = bound * np.ones_like(balance)
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.where(bound > 0, balance / bound, np.where(balance > 0, np.inf, 0.0))
    return float(np.max(r, initial=0.0))


def declared_populations(raw):
    from cells.operators import site_occupancy as so

    block = next((op for op in raw["model"]["operators"] if op["law"] == so.LAW_ID), None)
    return [] if block is None else list(block["populations"])


def row_terms(model, spec, p, row, steps):
    """One row's energy and ledger terms: (residual, magnitude, flows, energy bound, ratios)."""
    from cells.models.surface_pump import ENERGY_RTOL

    names = list(model.LEDGERS)
    k = names.index("energy")
    balances = model.balances(row, p)
    magnitudes = model.magnitudes(row, p)
    tol = np.asarray(spec.execution.material_balance_atol_fmol)
    flows, bounds = model.ledger_limits(row, p, tol, ENERGY_RTOL[spec.execution.solver],
                                        steps=steps, magnitudes=magnitudes)
    ratios = {name: _ratio(balances[name], bounds[i]) for i, name in enumerate(names)
              if name in balances}
    return (float(balances["energy"]), float(np.asarray(magnitudes[k])), float(flows),
            float(np.max(np.asarray(bounds[k]))), ratios)


def series_of_state(model, spec, p, row, steps, populations):
    """{series name: value} of one state row (the module docstring's series)."""
    m = spec.model
    s = list(m.species_ids).index(LIGAND)
    cells = [c.id for c in m.cells]
    outside = [c.id for c in m.extracellular]
    out = {}
    residual, magnitude, flows, bound, ratios = row_terms(model, spec, p, row, steps)
    out["energy_residual_pJ"], out["energy_magnitude_pJ"] = residual, magnitude
    out["energy_flows_pJ"], out["energy_bound_pJ"] = flows, bound
    out.update({f"ratio_{name}": value for name, value in ratios.items()})
    amount = np.asarray(p.amount_reference)[s] + np.asarray(row.amount_increment)[s]
    outside_amount = (np.asarray(p.extracellular_amount_reference)[s]
                      + np.asarray(row.extracellular_amount_increment)[s])
    heat_cells = np.asarray(row.site_dissipated_energy_pJ)
    heat_outside = np.asarray(row.site_outside_dissipated_energy_pJ)
    for i, cid in enumerate(cells):
        out[f"amount_{cid}"] = float(amount[i])
        out[f"heat_{cid}_pJ"] = float(heat_cells[i])
    for o, oid in enumerate(outside):
        if not m.extracellular[o].reservoir:
            out[f"amount_{oid}"] = float(outside_amount[o])
            out[f"heat_{oid}_pJ"] = float(heat_outside[o])
    out["heat_pJ"] = math.fsum([*heat_cells.tolist(), *heat_outside.tolist()])
    bound_ = np.asarray(p.site_bound_anchor_fmol) + np.asarray(row.site_bound_increment_fmol)
    free = np.asarray(p.site_free_anchor_fmol) + np.asarray(row.site_free_increment_fmol)
    work = np.asarray(row.site_work_pJ)
    for k, pop in enumerate(populations):
        pid = pop["id"]
        out[f"B_{pid}"] = float(bound_[k])
        out[f"R_{pid}"] = float(free[k])
        out[f"internalised_{pid}"] = float(np.asarray(row.site_internalised_fmol)[k])
        out[f"net_{pid}"] = float(np.asarray(row.site_bound_net_fmol)[k])
        out[f"work_{pid}_pJ"] = float(work[k])
        out[f"magnitude_{pid}_pJ"] = float(np.asarray(row.site_energy_magnitude_pJ)[k])
    out["work_pJ"] = math.fsum(work.tolist())
    return out


def layout_of(spec, p, populations):
    m = spec.model
    capacity = np.asarray(p.site_capacity_fmol)
    volumes = {c.id: float(c.volume_pL) for c in (*m.cells, *m.extracellular)
               if not getattr(c, "reservoir", False)}
    out = dict(
        volumes_pL=volumes,
        cells=[c.id for c in m.cells],
        finite_nodes=[c.id for c in m.extracellular if not c.reservoir],
        populations=[pop["id"] for pop in populations],
        sites_fmol={pop["id"]: float(capacity[k]) for k, pop in enumerate(populations)},
        K_d_mM={pop["id"]: pop["dissociation_rate_per_s"] / pop["association_rate_per_mM_per_s"]
                for pop in populations},
        internalises={pop["id"]: pop["internalisation"] is not None for pop in populations},
        ligand_floor_fmol=float(np.asarray(spec.execution.material_balance_atol_fmol)[
            list(m.species_ids).index(LIGAND)]),
        temperature_K=float(m.temperature_K),
    )
    return out


def records_of(result, raw):
    """Every observation time's series (module docstring) from a runner result."""
    from cells.registry.models import get_model

    spec = result.spec
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    populations = declared_populations(raw)
    times = np.asarray(result.times)
    obs_times = np.asarray(result.observations.times)
    series = {}
    for t in obs_times:
        i = int(np.argmin(np.abs(times - t)))
        if abs(times[i] - t) > 1e-9 * max(1.0, abs(t)):
            raise ValueError(f"observation time {t} is not an accepted step")
        row = _row(model, result.history, i)
        steps = int(round(t / spec.execution.dt))
        for name, value in series_of_state(model, spec, p, row, steps, populations).items():
            series.setdefault(name, []).append(value)
    return dict(record_s=[float(t) for t in obs_times], record_ms=[ms(t) for t in obs_times],
                dt_s=float(spec.execution.dt), series=series, ledgers=list(model.LEDGERS),
                ids=ids_of(spec),
                diagnostics=plain(dict(result.diagnostics)), **layout_of(spec, p, populations))


def engine_part(raw, context, *, label=None, arm=None):
    """One run of one definition: its admission, run and records (records_of)."""
    from cells.execution.errors import NumericalError
    from cells.execution.runner import run

    raw = quick(raw) if context["quick"] else raw
    started = time.perf_counter()
    spec, refusal = admit(raw)
    out = dict(kind="engine", label=label, arm=arm, dt_s=raw["execution"]["dt"],
               solver=raw["execution"]["solver"], end_s=raw["experiment"]["end_time"],
               steps=int(round(raw["experiment"]["end_time"] / raw["execution"]["dt"])))
    if spec is None:
        return dict(out, admitted=False, completed=False, refusal=refusal,
                    wall_s=time.perf_counter() - started)
    try:
        result = run(spec)
    except NumericalError as error:
        return dict(out, admitted=True, completed=False, refusal=str(error),
                    wall_s=time.perf_counter() - started)
    return dict(out, admitted=True, completed=True, refusal=None, **records_of(result, raw),
                wall_s=time.perf_counter() - started)


def engine_set(builds, context, *, arm_of):
    """Several declared variants, each its own engine run: {variant: engine record}."""
    started = time.perf_counter()
    runs = {name: engine_part(af.build(world), context, label=name, arm=arm_of[name])
            for name, world in builds.items()}
    ok = all(r["admitted"] and r["completed"] for r in runs.values())
    return dict(kind="engine_set", admitted=True, completed=ok, runs=runs,
                wall_s=time.perf_counter() - started)


# ------------------------------------------------------------------ the world parts


def _world(world_id, dt=af.DECLARED_DT):
    def part(name, context):
        del name
        return engine_part(af.registered_world(world_id, dt=dt), context, label=world_id,
                           arm=world_id)
    return part


# ------------------------------------------------------------------ the controls


def k_rates(name, context):
    del name
    builds = {w: af.rates(af.LADDER_WORLD, w) for w in ("k_on", "k_off", "k_int")}
    return engine_set(builds, context, arm_of={w: af.LADDER_WORLD for w in builds})


def k_alpha(name, context):
    del name
    arm = "q1_eps_1e-1_alpha_half"
    return engine_set({"alpha_ignored": af.alpha_ignored(arm)}, context,
                      arm_of={"alpha_ignored": arm})


def k_binding_multiplier(name, context):
    del name
    arm = "q3_binding_multiplier"
    builds = {mode: af.binding_multiplier(arm, mode) for mode in ("ignored", "squared")}
    return engine_set(builds, context, arm_of={mode: arm for mode in builds})


def k_internalisation_multiplier(name, context):
    del name
    arm = "q5_class_switch"
    return engine_set({"ignored": af.internalisation_multiplier_ignored(arm)}, context,
                      arm_of={"ignored": arm})


def k_cell_volume(name, context):
    del name
    builds = {w: af.cell_volume(w, "cell_0", 1.0) for w in ("q5_inward", "q1_eps_1e-1")}
    return engine_set(builds, context, arm_of={w: w for w in builds})


def _q4(form):
    def part(name, context):
        del name
        builds, arms = {}, {}
        for regime in Q4_REGIMES:
            for alpha in Q4_ALPHAS:
                key = f"{regime}_{alpha:g}"
                builds[key] = form(f"q4_alpha_1_{regime}", alpha)
                arms[key] = f"q4_alpha_1_{regime}"
        return engine_set(builds, context, arm_of=arms)
    return part


# ------------------------------------------------------------------ Q6


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


def _head(raw, at):
    """The world to `at`: its records to `at`, its schedule changes before `at`."""
    head = copy.deepcopy(raw)
    head["experiment"]["end_time"] = at
    head["experiment"]["observation_times"] = [
        t for t in raw["experiment"]["observation_times"] if t <= at + 1e-12]
    for control in head["experiment"].get("site_controls", []):
        control["schedule"] = [c for c in control["schedule"] if c["time"] < at]
    return head


def _restart(raw, at, workdir, *, through_snapshot):
    """Run to `at`, then resume to the end: in process from the head's checkpoint, or through a
    written snapshot (cells.records.io.write_snapshot and load_snapshot); a branch from the head's own
    checkpoint into the full schedule (its changes from `at` on)."""  # noqa: E501
    from cells.definitions.specs import parse_spec
    from cells.execution.runner import branch_checkpoint, run
    from cells.records.io import load_snapshot, write_snapshot

    spec = parse_spec(raw)
    first = run(parse_spec(_head(raw, at)))
    origin, checkpoint = first.spec, first.final
    if through_snapshot:
        directory = Path(workdir) / f"checkpoint-{at:g}"
        directory.parent.mkdir(parents=True, exist_ok=True)
        write_snapshot(directory, first.spec, first.final)
        loaded = load_snapshot(directory)
        origin, checkpoint = loaded.spec, loaded.checkpoint
    return run(spec, branch_checkpoint(origin, checkpoint, spec))


def moved_switch(world_id=RESTART_WORLD, at=SWITCH_S, dt=af.DECLARED_DT):
    """K4's world: the epoch at `at` moved one step later (on the step grid)."""
    w = af.registered(world_id)
    moved = False
    for epoch in w["site_controls"]:
        if ms(epoch["time_s"]) == ms(at):
            epoch["time_s"] = (round(at / dt) + 1) * dt
            moved = True
    if not moved:
        raise ValueError(f"{world_id} has no epoch at {at} s")
    return w


def q6_restart(name, context):
    """Q6: straight, then resumed before, at and after the switch-on, in process and through a
    snapshot; K4: the switch moved one step, resumed, against the straight run."""
    from cells.definitions.specs import parse_spec
    from cells.execution.runner import run

    del name
    started = time.perf_counter()
    raw = af.registered_world(RESTART_WORLD)
    if context["quick"]:
        raw = quick(raw)
    end = raw["experiment"]["end_time"]
    straight = run(parse_spec(raw))
    out = {}
    planted = None
    with tempfile.TemporaryDirectory(dir=context["out_dir"]) as workdir:
        for at in RESTART_TIMES_S:
            if at >= end:
                continue
            for mode in ("in_process", "snapshot"):
                resumed = _restart(raw, at, workdir, through_snapshot=mode == "snapshot")
                out[f"{at:g} {mode}"] = compare_results(straight, resumed, start=at)
        if SWITCH_S < end:
            moved = af.build(moved_switch())
            moved = quick(moved) if context["quick"] else moved
            first = RESTART_TIMES_S[0]
            planted = compare_results(straight, _restart(moved, first, Path(workdir) / "moved",
                                                         through_snapshot=True), start=first)
    return dict(kind="comparison", admitted=True, completed=True, world=RESTART_WORLD,
                restarts=out, planted=planted, wall_s=time.perf_counter() - started)


BATCH_CHANGE_S = 0.1  # Every batched world's multipliers change here (one event grid).
BATCH_VARIANTS = (
    # copies x, sites per copy, alpha, k_on x, k_off x, theta0, k_int x, V_node, c0, V_cell,
    # m_b and m_i from BATCH_CHANGE_S.
    (1.0, 1, 1.0, 1.0, 1.0, None, 1.0, None, None, None, 1.0, 1.0),
    (0.5, 2, 0.5, 0.8, 1.25, 0.05, 1.5, 2.0, 2e-4, 1.5, 0.5, 1.0),
    (2.0, 1, 0.25, 1.5, 0.5, 0.2, 0.5, 0.5, 5e-5, 0.75, 2.0, 1.0),
    (1.0, 3, 0.75, 0.5, 2.0, 0.0, 2.0, 1.25, 1.5e-4, 2.0, 0.75, 0.5),
)


def batch_world(variant, base=af.LADDER_WORLD):
    """A q1_fast-shaped world with every parameter changed (BATCH_VARIANTS' row)."""
    copies, nu, alpha, kon, koff, theta, kint, v_node, c0, v_cell, mb, mi = variant
    w = af.registered(base)
    p = w["populations"][0]
    pid = p["id"]
    p["copies"] *= copies
    p["sites_per_copy"] = nu
    p["accessible_fraction"] = alpha
    p["association_rate_per_mM_per_s"] *= kon
    p["dissociation_rate_per_s"] *= koff
    if theta is not None:
        p["initial_occupancy"] = theta
    p["internalisation"]["rate_per_s"] *= kint
    if v_node is not None:
        w["nodes"]["ecs_0"]["volume_pL"] = v_node
    if c0 is not None:
        w["nodes"]["ecs_0"]["L_mM"] = c0
    if v_cell is not None:
        w["nodes"]["cell_0"]["volume_pL"] = v_cell
    w["site_controls"].append(dict(time_s=BATCH_CHANGE_S, binding={pid: mb},
                                   internalisation={pid: mi}))
    return w


def _concat(windows):
    """{field: rows} of one world's observation windows, concatenated in time."""
    names = [k for k in vars(windows[0]) if k != "times"]
    return {k: np.concatenate([np.asarray(getattr(w, k)) for w in windows]) for k in names}


def _relative(a, b):
    worst = 0.0
    for name in sorted(set(a) & set(b)):
        x, y = np.asarray(a[name], dtype=float), np.asarray(b[name], dtype=float)
        if x.shape != y.shape:
            return None
        scale = np.maximum(np.abs(y), 1e-300)
        worst = max(worst, float(np.max(np.abs(x - y) / scale, initial=0.0)))
    return worst


def _bitwise(a, b):
    if set(a) != set(b):
        return False
    return all(np.asarray(a[k]).dtype == np.asarray(b[k]).dtype
               and np.asarray(a[k]).shape == np.asarray(b[k]).shape
               and np.asarray(a[k]).tobytes() == np.asarray(b[k]).tobytes() for k in a)


def q6_batch(name, context):
    """Q6: four worlds with every parameter different in one vector batch, against each scalar
    run (within 1e-12 relative, every observed field) and against the reversed batch (bitwise)."""
    from cells.definitions.specs import parse_spec
    from cells.execution.batch import BatchSpec, WorldSpec
    from cells.execution.runner import run
    from cells.execution.vector_windows import run_vector_windowed
    from cells.execution.windows import WindowPolicy

    del name
    started = time.perf_counter()
    raws = [af.build(batch_world(v)) for v in BATCH_VARIANTS]
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
    for i, spec in enumerate(specs):
        scalar = run(spec)
        alone = {k: np.asarray(getattr(scalar.observations, k))
                 for k in vars(scalar.observations) if k != "times"}
        rows = _concat(forward_seen[i + 1])
        reversed_rows = _concat(backward_seen[n - i])
        out[f"world_{i + 1}"] = dict(
            fields=sorted(rows),
            scalar_relative=_relative(rows, alone),
            scalar_bitwise=_bitwise({k: rows[k] for k in alone if k in rows},
                                    {k: alone[k] for k in rows if k in alone}),
            reversed_equal=_bitwise(rows, reversed_rows),
            final_reversed_equal=all(
                np.asarray(x).tobytes() == np.asarray(y).tobytes()
                for x, y in zip(forward.worlds[i + 1].final.state,
                                backward.worlds[n - i].final.state, strict=True)))
    return dict(kind="comparison", admitted=True, completed=True, worlds=out,
                variants=[list(v) for v in BATCH_VARIANTS], wall_s=time.perf_counter() - started)


def idle_world(*, zero=True):
    """Q6_idle's world: IDLE_WORLD's layout to IDLE_END_S, recorded at every step, with every
    multiplier zero (zero). The world with no populations is af.build(idle_world(),
    populations=False): the same layout, the operator declared with none."""
    w = af.registered(IDLE_WORLD)
    w["end_s"] = IDLE_END_S
    w["record_times_s"] = [k * af.DECLARED_DT for k in range(ms(IDLE_END_S) + 1)]
    if zero:
        w["site_controls"] = [dict(
            time_s=0.0, binding={p["id"]: 0.0 for p in w["populations"]},
            internalisation={p["id"]: 0.0 for p in w["populations"]})]
    return w


def same_inner(a, b, model):
    """The names of the inner fields whose history differs bit for bit (empty: none)."""
    found = []
    for name in model.STATE_TYPE._fields:
        x, y = np.asarray(getattr(a.history, name)), np.asarray(getattr(b.history, name))
        if x.dtype != y.dtype or x.shape != y.shape or x.tobytes() != y.tobytes():
            found.append(name)
    return found


def q6_idle(name, context):
    """Q6, §4.8's claim 2: every multiplier zero, and no populations, each bitwise the world
    without the operator on every inner field and row; the zero world's own fields frozen."""
    from cells.definitions.specs import parse_spec
    from cells.execution.runner import run
    from cells.registry.models import get_model

    del name, context
    started = time.perf_counter()
    plain_world = af.build(idle_world(), operator=False)
    reference = run(parse_spec(plain_world))
    model = get_model(reference.spec.model)
    zero = run(parse_spec(af.build(idle_world())))
    empty = run(parse_spec(af.build(idle_world(), populations=False)))
    frozen = []
    for field in ("site_free_increment_fmol", "site_bound_increment_fmol", "site_bound_net_fmol",
                  "site_internalised_fmol", "site_dissipated_energy_pJ",
                  "site_outside_dissipated_energy_pJ", "site_work_pJ",
                  "site_energy_magnitude_pJ"):
        values = np.asarray(getattr(zero.history, field))
        if values.tobytes() != np.broadcast_to(values[0], values.shape).tobytes():
            frozen.append(field)
    return dict(kind="idle", admitted=True, completed=True, rows=int(len(reference.times)),
                zero_multipliers=same_inner(reference, zero, model),
                no_populations=same_inner(reference, empty, model),
                zero_world_fields_moved=frozen,
                no_populations_statically_idle=bool(get_model(empty.spec.model).operators[0]
                                                    .statically_idle(empty.final.layout)),
                wall_s=time.perf_counter() - started)


def twin(world_id=IDLE_WORLD, *, changed=False):
    """Q6_twins' worlds: IDLE_WORLD to 0.01 s, and its value twin with every parameter and
    multiplier changed (the same structure)."""
    w = af.registered(world_id)
    w["end_s"] = 0.01
    w["record_times_s"] = [0.0, 0.005, 0.01]
    if changed:
        for k, p in enumerate(w["populations"]):
            p["copies"] *= 1.5 + k
            p["sites_per_copy"] += 1
            p["accessible_fraction"] *= 0.5
            p["association_rate_per_mM_per_s"] *= 2.0
            p["dissociation_rate_per_s"] *= 3.0
            p["initial_occupancy"] = 0.25 + 0.1 * k
            if p["internalisation"] is not None:
                p["internalisation"]["rate_per_s"] *= 4.0
        for epoch in w["site_controls"]:
            epoch["binding"] = {pid: 0.5 for pid in epoch["binding"]}
            epoch["internalisation"] = {pid: 0.75 for pid in epoch["internalisation"]}
    return w


def q6_twins(name, context):
    """Q6, §6.3: two value twins traced: identical jaxpr text and closed-over constants for every
    program, the bindings the same names, dtypes and shapes (their values differ)."""
    from validation.tissue import compartment_fixtures as cf

    del name, context
    started = time.perf_counter()
    a_raw, b_raw = af.build(twin()), af.build(twin(changed=True))
    a, b = cf.traced(a_raw), cf.traced(b_raw)
    programs = {}
    for kind in sorted(set(a) | set(b)):
        if kind not in a or kind not in b:
            programs[kind] = dict(text_equal=False, constants_equal=False)
            continue
        programs[kind] = dict(text_equal=a[kind][0] == b[kind][0],
                              constants_equal=a[kind][1] == b[kind][1])
    ba, bb = cf.bindings(a_raw), cf.bindings(b_raw)
    layout_same = sorted(ba) == sorted(bb) and all(
        ba[k].dtype == bb[k].dtype and ba[k].shape == bb[k].shape for k in ba)
    differing = sorted(k for k in ba if k in bb and ba[k].tobytes() != bb[k].tobytes())
    return dict(kind="twins", admitted=True, completed=True, programs=programs,
                bindings_same_names_dtypes_shapes=layout_same, bindings_differing=differing,
                wall_s=time.perf_counter() - started)


def q6_signature(name, context):
    """Q6, §2.7: worlds of different structure in one batch refused by the batch signature, with
    its reason; worlds of one structure and different parameters admitted (planned)."""
    from cells.definitions.specs import ConfigError, parse_spec
    from cells.execution.batch import BatchSpec, WorldSpec, plan_batch

    del name, context
    started = time.perf_counter()
    base = af.registered(af.LADDER_WORLD)
    no_route = copy.deepcopy(base)
    no_route["populations"][0]["internalisation"] = None
    no_route = af.build(no_route)
    # The same layout (the contact patch kept), the population facing the cytosol instead.
    inward = _engine_edit(no_route, lambda raw: _first_pop(raw).update(
        owner=dict(patch="wall_cell_0", face="inside")))
    cases = {"internalisation_differs": (af.build(base), no_route),
             "facing_differs": (no_route, inward),
             "same_structure": (af.build(base), af.build(batch_world(BATCH_VARIANTS[1])))}
    out = {}
    for case, (x, y) in cases.items():
        specs = [parse_spec(x), parse_spec(y)]
        try:
            plan_batch(BatchSpec((WorldSpec(1, specs[0]), WorldSpec(2, specs[1])), 2, 10**8,
                                 2**33))
            out[case] = dict(refused=False, message=None)
        except ConfigError as error:
            out[case] = dict(refused=True, message=str(error))
    return dict(kind="signature", admitted=True, completed=True, cases=out,
                wall_s=time.perf_counter() - started)


# ------------------------------------------------------------------ Q6_refusals

# The checks a refusal may name, by a phrase of their messages (one label per check).
# Disclosed repair of this judged tool (22 November 2026): "replaced slot" took FR-26's words
# (a305c4c2 narrowed the check and reworded it, so the old phrase named nothing), and "schedule
# grid" D283 stage 2's; their labels are unchanged. The class view_conflict_bath_schedule is
# retired (the lead's ruling, 22 November 2026): FR-23 (D244, e7a54539, 20 November, after the
# judged run at 1b838d75) admits site occupancy beside the bath schedule through door S's scoped
# reads, so its view conflict no longer exists and its planted world is refused only by the bath
# schedule's step rule, another check. Q6's registered results stay reproducible at their tags.
# The class species_cap is retired (the lead's ruling, 23 November 2026): FR-43 (D315, after the
# judged run) raised the species cap from 16 to 1,024, so its 17-species world is admitted; the cap
# is an engine limit with its own tests (tests/unit/test_species_cap*.py). The label "species cap"
# stays, its phrase now the cap's message at any value (the old "at most 16 species" named nothing).
CHECKS = (
    ("ligand charged", "neutral species only"),
    ("ligand undeclared", "does not declare"),
    ("ligand permeant", "zero membrane, junction"),
    ("identity", "another identity"),
    ("species cap", "species per world"),
    ("trace: node below", "below its declared trace"),
    ("trace: above 1e-6 K_d", "exceeds 1e-06 K_d"),
    ("unknown patch", "unknown patch"),
    ("unknown contact", "unknown contact"),
    ("held bath", "faces the held bath"),
    ("copies", "copies must be >"),
    ("sites per copy", "sites per copy is a positive integer"),
    ("accessible fraction", "accessible fraction lies in (0, 1]"),
    ("unlisted ligand", "unlisted ligand"),
    ("initial occupancy", "initial occupancy lies in [0, 1]"),
    ("k_on", "k_on must be >"),
    ("k_off", "k_off must be >"),
    ("k_int", "internalisation rate must be >="),
    ("internalisation owner", "only an outward-facing patch"),
    ("compartment", "internalises from compartment"),
    ("destination", "destination is one of"),
    ("replaced slot", "replaces; its occupants need"),
    ("RK4", "refuses RK4"),
    ("schedule missing", "every route needs a schedule; missing"),
    ("schedule start", "starts at time 0"),
    ("schedule grid", "on the clock's grid"),
    ("schedule horizon", "outside the horizon"),
    ("schedule negative", "must be >= 0"),
    ("schedule route", "names no declared route"),
    ("unknown key", "unknown"),
    ("duplicate population", "lists a population twice"),
    ("view conflict", "Invalid operator composition: cells.operator.site_occupancy@1 reads"),
    ("stationary analysis", "not cells.model.resolved_pump_composite@1"),
    ("batch signature", "matching model array axes"),
)


def classify(message):
    """The check a refusal message names, or None (the first label whose phrase it contains)."""
    for check, phrase in CHECKS:
        if phrase in (message or ""):
            return check
    return None


def _w(edit=None, world_id=af.LADDER_WORLD):
    """W, the refusals' base: q1_fast's world in the references' form, edited."""
    w = af.registered(world_id)
    if edit is not None:
        edit(w)
    return w


def _engine_edit(raw, edit):
    out = copy.deepcopy(raw)
    edit(out)
    return out


def _site_block(raw):
    return next(
        op for op in raw["model"]["operators"] if op["law"] == "cells.operator.site_occupancy@1"
    )


def _first_pop(raw):
    return _site_block(raw)["populations"][0]


def _inward(w):
    w["populations"].append(dict(copy.deepcopy(w["populations"][0]), id="r_in", owner=dict(
        cell="cell_0", orientation="inward", faces_node="cell_0"), internalisation=None))
    w["nodes"]["cell_0"]["L_mM"] = 1e-4
    for epoch in w["site_controls"]:
        epoch["binding"]["r_in"] = 1.0


def _permeant(raw):
    next(p for p in raw["model"]["membranes"] if p["id"] == "wall_cell_0")[
        "permeability_m_per_s"][LIGAND] = 1e-12


def _schedule(edit):
    def apply(raw):
        edit(raw["experiment"]["site_controls"])
    return apply


def _identity(agree):
    """W beside D150's exchange declaring S with a catalogue identity: the sites declare S
    without it (refused) or with it (agree: admitted)."""
    from validation.tissue import site_occupancy_fixtures as sfx

    raw = af.build(_w())
    catalogue = dict(catalogue="uniprot", entry="P00001")
    raw = af.fx.with_exchange(raw, [("sec", "contact_cell_0_ecs_0", "export", "first_order")],
                              [("sec", "cell_0", [(0.0, 0.1)])],
                              species=af.fx.identity(catalogue=catalogue, evidence="model"))
    if agree:
        _site_block(raw)["species"] = [sfx.ligand(catalogue=catalogue, evidence="model")]
    return raw


def _replaced(on_replaced):
    """Two cells on the bath, cell_1 replaced at 5 ms; an inward population on cell_1's wall
    (refused) or on cell_0's (admitted)."""
    from validation.tissue import site_occupancy_fixtures as sfx

    raw = af.fx.world(cells=(("cell_0", 1.0), ("cell_1", 1.0)), nodes=(("ecs_0", 1.0),),
                      contacts=(("contact_0", "cell_0", "ecs_0"),), faces=(),
                      junctions=(("j0", "cell_0", "cell_1"),), end=0.01,
                      trace_mM=sfx.TRACE_mM,
                      concentrations_mM=dict(cell_0=1e-3, cell_1=1e-3, ecs_0=1e-3))
    template = af.fx.template(raw, "cell_1", "T", s_mM=1e-3)
    raw = af.fx.with_replacement(raw, [template], [(0.005, "cell_1", "T", "c1_new")])
    cell = "cell_1" if on_replaced else "cell_0"
    return sfx.with_site_occupancy(raw, [sfx.population("w", patch=f"wall_{cell}",
                                                        face="inside")])


def _compartment():
    from validation.tissue import compartment_fixtures as cf

    raw = af.build(_w())
    return cf.with_compartments(raw, [cf.compartment(node="ecs_0", patch="contact_cell_0_ecs_0",
                                                     owner="cell_0")])


def _threshold(w):
    """W with its trace at exactly 1e-6 K_d (q1_fast's K_d is 1e-3 mM) and every node at or
    above it."""
    w["trace_mM"] = 1e-9
    w["nodes"]["cell_0"]["L_mM"] = 1e-9


def refusal_classes():
    """{class: (kind, refused, neighbour)}: each refused definition is W (q1_fast's world)
    changed in the one way its class names; each neighbour is W, or W with the admitted variant.
    kind: 'definition' (parse and timeline), 'structure' (the composite's structure check, both
    orders), 'analysis' (the stationary analysis), 'runtime' (the run)."""
    from cells.operators import site_occupancy as so
    from validation.tissue import site_occupancy_fixtures as sfx

    W = af.build(_w())

    def pop(**changes):
        def edit(raw):
            _first_pop(raw).update(changes)
        return lambda: _engine_edit(W, edit)

    def ligand(**changes):
        def edit(raw):
            _site_block(raw)["species"] = [sfx.ligand(**changes)]
        return lambda: _engine_edit(W, edit)

    def same():
        return W

    inward = lambda: af.build(_w(_inward))  # noqa: E731
    sched = lambda edit: lambda: _engine_edit(W, _schedule(edit))  # noqa: E731
    return {
        "ligand_charged": ("definition", ligand(species="K"), same),
        "ligand_undeclared": ("definition", ligand(species="X"), same),
        "ligand_permeant": ("definition", lambda: _engine_edit(W, _permeant), same),
        "identity": ("definition", lambda: _identity(False), lambda: _identity(True)),
        "trace_node_below": ("definition", ligand(trace_mM=2e-4), same),
        "trace_above_limit": (
            "definition",
            lambda: af.build(
                _w(
                    lambda w: (
                        w.update(trace_mM=1.01e-9) or w["nodes"]["cell_0"].update(L_mM=1.01e-9)
                    )
                )
            ),
            lambda: af.build(_w(_threshold)),
        ),
        "unknown_patch": ("definition", pop(owner=dict(patch="nope", face="outside")), same),
        "unknown_contact": ("definition", pop(owner=dict(contact="j9", side="first")), same),
        "held_bath": ("definition", pop(owner=dict(patch="wall_cell_0", face="outside")), inward),
        "copies": ("definition", pop(copies=0.0), same),
        "sites_per_copy": ("definition", pop(sites_per_copy=1.5), same),
        "accessible_fraction": ("definition", pop(accessible_fraction=0.0), same),
        "unlisted_ligand": ("definition", pop(ligand="Na"), same),
        "initial_occupancy": ("definition", pop(initial_occupancy=1.1), same),
        "k_on": ("definition", pop(association_rate_per_mM_per_s=0.0), same),
        "k_off": ("definition", pop(dissociation_rate_per_s=0.0), same),
        "k_int": (
            "definition",
            pop(internalisation=dict(rate_per_s=-1.0, destination="cell")),
            same,
        ),
        "internalisation_inward": (
            "definition",
            lambda: _engine_edit(
                inward(),
                lambda raw: next(
                    p for p in _site_block(raw)["populations"] if p["id"] == "r_in"
                ).update(internalisation=dict(rate_per_s=0.1, destination="cell")),
            ),
            inward,
        ),
        "internalisation_compartment": ("definition", _compartment, same),
        "destination": (
            "definition",
            pop(internalisation=dict(rate_per_s=10.0, destination="lysosome")),
            same,
        ),
        "replaced_slot": ("definition", lambda: _replaced(True), lambda: _replaced(False)),
        "rk4": ("definition", lambda: af.build(_w(), dt=1e-4, solver="rk4"), same),
        "schedule_missing": ("definition", sched(lambda c: c.pop()), same),
        "schedule_start": (
            "definition",
            sched(lambda c: c[0]["schedule"][0].update(time=0.002)),
            same,
        ),
        "schedule_grid": (
            "definition",
            sched(lambda c: c[0]["schedule"].append(dict(time=0.0015, multiplier=1.0))),
            same,
        ),
        "schedule_horizon": (
            "definition",
            sched(lambda c: c[0]["schedule"].append(dict(time=1.0, multiplier=1.0))),
            same,
        ),
        "schedule_negative": (
            "definition",
            sched(lambda c: c[0]["schedule"][0].update(multiplier=-1.0)),
            same,
        ),
        "schedule_static_parameter": (
            "definition",
            sched(
                lambda c: c.append(
                    dict(
                        population="r0",
                        route="accessibility",
                        schedule=[dict(time=0.0, multiplier=1.0)],
                    )
                )
            ),
            same,
        ),
        "unknown_key": ("definition", pop(colour="red"), same),
        "duplicate_population": (
            "definition",
            lambda: _engine_edit(
                W,
                lambda raw: _site_block(raw)["populations"].append(copy.deepcopy(_first_pop(raw))),
            ),
            same,
        ),
        "view_conflict_water": (
            "structure",
            ("cells.operator.ideal_osmosis_linear_compliance_water@1", so.LAW_ID),
            ("cells.operator.scheduled_species_exchange@1", so.LAW_ID),
        ),
        "stationary_analysis": ("analysis", same, same),
        "stage_condition": ("runtime", pop(association_rate_per_mM_per_s=2e7), same),
    }


# The check each class must name (its label in CHECKS), by class.
EXPECTED_CHECKS = {
    "ligand_charged": "ligand charged", "ligand_undeclared": "ligand undeclared",
    "ligand_permeant": "ligand permeant", "identity": "identity",
    "trace_node_below": "trace: node below", "trace_above_limit": "trace: above 1e-6 K_d",
    "unknown_patch": "unknown patch", "unknown_contact": "unknown contact",
    "held_bath": "held bath", "copies": "copies", "sites_per_copy": "sites per copy",
    "accessible_fraction": "accessible fraction", "unlisted_ligand": "unlisted ligand",
    "initial_occupancy": "initial occupancy", "k_on": "k_on", "k_off": "k_off", "k_int": "k_int",
    "internalisation_inward": "internalisation owner",
    "internalisation_compartment": "compartment", "destination": "destination",
    "replaced_slot": "replaced slot", "rk4": "RK4", "schedule_missing": "schedule missing",
    "schedule_start": "schedule start", "schedule_grid": "schedule grid",
    "schedule_horizon": "schedule horizon", "schedule_negative": "schedule negative",
    "schedule_static_parameter": "schedule route", "unknown_key": "unknown key",
    "duplicate_population": "duplicate population",
    "view_conflict_water": "view conflict",
    "stationary_analysis": "stationary analysis", "stage_condition": None,
}


def _run_admitted(raw, cache):
    """(admitted, ran, message) of a neighbour, each distinct definition run once."""
    from cells.execution.errors import NumericalError
    from cells.execution.runner import run

    key = json.dumps(raw, sort_keys=True)
    if key not in cache:
        spec, message = admit(raw)
        ran = None
        if spec is not None:
            try:
                run(spec)
                ran = True
            except NumericalError as error:
                ran, message = False, str(error)
        cache[key] = (spec is not None, ran, message)
    return cache[key]


def q6_refusals(name, context):
    from cells.analysis import stationary
    from cells.definitions.specs import ConfigError, parse_spec
    from cells.execution.errors import NumericalError
    from cells.execution.runner import run
    from cells.models import pump_composite
    from cells.models import pump_composite_adapter as adapter
    from cells.operators import OPERATORS

    del name, context
    started = time.perf_counter()
    cache, out = {}, {}
    for cls, (kind, refused, neighbour) in refusal_classes().items():
        if kind == "structure":
            rows = []
            for laws in (refused, tuple(reversed(refused))):
                errors = pump_composite.structure_errors(adapter, tuple(OPERATORS[k]
                                                                        for k in laws))
                message = ("Invalid operator composition: " + "; ".join(errors)
                           if errors else None)
                rows.append(dict(refused=bool(errors) and any(refused[0] in e for e in errors),
                                 message=message, check=classify(message)))
            admitted = []
            for laws in (neighbour, tuple(reversed(neighbour))):
                errors = pump_composite.structure_errors(adapter, tuple(OPERATORS[k]
                                                                        for k in laws))
                admitted.append(dict(admitted=not errors, ran=None, needs_run=False,
                                     message="; ".join(errors) or None))
            out[cls] = dict(kind=kind, refused=rows, admitted=admitted)
            continue
        if kind == "analysis":
            try:
                stationary.problem(parse_spec(refused()))
                row = dict(refused=False, message=None, check=None)
            except ConfigError as error:
                row = dict(refused=True, message=str(error), check=classify(str(error)))
        elif kind == "runtime":
            spec, message = admit(refused())
            row = dict(refused=False, message=message, check=None, admitted=spec is not None)
            if spec is not None:
                try:
                    run(spec)
                except NumericalError as error:
                    row.update(refused=True, message=str(error), kind=type(error).__name__)
        else:
            spec, message = admit(refused())
            row = dict(refused=spec is None, message=message, check=classify(message))
        admitted, ran, message = _run_admitted(neighbour(), cache)
        out[cls] = dict(kind=kind, refused=[row], admitted=[dict(
            admitted=admitted, ran=ran, needs_run=True, message=message)])
    return dict(kind="refusals", admitted=True, completed=True, classes=out,
                neighbour_runs=len(cache), wall_s=time.perf_counter() - started)


# ------------------------------------------------------------------ the plants


def _plant(plant, context):
    """One planted control in its own process (validation/tissue/
    site_occupancy_acceptance_plants: the lead's ruling, so no plant reaches a judged world),
    its bundle read back."""
    import os

    directory = Path(tempfile.mkdtemp(prefix=f"plant-{plant}-", dir=context["out_dir"]))
    out = directory / f"{plant}.json"
    module = "validation.tissue.site_occupancy_acceptance_plants"
    subprocess.run([sys.executable, "-B", "-m", module, plant, str(out)], check=True, cwd=ROOT,
                   env=dict(os.environ))
    bundle = json.loads(out.read_text())
    out.unlink()
    directory.rmdir()
    return bundle


def _plants(names):
    def part(name, context):
        del name
        started = time.perf_counter()
        plants = {plant: _plant(plant, context) for plant in names}
        return dict(kind="plants", admitted=True, completed=True, plants=plants,
                    wall_s=time.perf_counter() - started)
    return part


# ------------------------------------------------------------------ the references


def _array(value):
    return np.asarray(value, dtype=float)


def reference_record(r, world):
    """api.reference's outputs in the judge's names (the engine records' names)."""
    times = _array(r["times_s"])
    nodes, pops = [str(n) for n in r["nodes"]], [str(p) for p in r["populations"]]
    series = {}
    for key, prefix, names in (("n_fmol", "amount_", nodes), ("B_fmol", "B_", pops),
                               ("R_fmol", "R_", pops),
                               ("internalised_fmol", "internalised_", pops)):
        values, floors = _array(r[key]), _array(r[key + "_floor"])
        for j, name in enumerate(names):
            series[prefix + name] = values[:, j].tolist()
            series["floor_" + prefix + name] = floors[:, j].tolist()
    for key in ("heat_pJ", "work_pJ"):
        series[key] = _array(r[key]).tolist()
        series["floor_" + key] = _array(r[key + "_floor"]).tolist()
    series["ledger_residual_pJ"] = _array(r["ledger_residual_pJ"]).tolist()
    out = dict(record_s=times.tolist(), record_ms=[ms(t) for t in times], series=series,
               nodes=nodes, populations=pops,
               sites_fmol={p: float(v) for p, v in zip(pops, _array(r["sites_fmol"]), strict=True)},
               K_d_mM={p: float(v) for p, v in zip(pops, _array(r["K_d_mM"]), strict=True)},
               volumes_pL={nid: float(n["volume_pL"]) for nid, n in world["nodes"].items()},
               facing={p["id"]: p["owner"]["faces_node"] for p in world["populations"]},
               depletion_term=None if r.get("depletion_term") is None
               else float(r["depletion_term"]))
    if "equilibrium" in r:
        e = r["equilibrium"]
        out["equilibrium"] = dict(
            c_mM=float(e["c_mM"]),
            B_fmol={p: float(v) for p, v in zip(pops, np.atleast_1d(_array(e["B_fmol"])),
                                                strict=True)},
            heat_to_equilibrium_pJ=float(e["heat_to_equilibrium_pJ"]))
    if "riccati" in r:
        k = r["riccati"]
        (pid,) = pops
        node = out["facing"][pid]
        out["riccati"] = dict(population=pid, node=node, record_ms=out["record_ms"],
                              series={f"B_{pid}": _array(k["B_fmol"]).tolist(),
                                      f"amount_{node}": _array(k["n_fmol"]).tolist()},
                              B_eq_fmol=float(k["B_eq_fmol"]))
    if "qss" in r:
        q = r["qss"]
        out["qss"] = dict(epsilon=float(q["epsilon"]),
                          relative_error_over_uptake=float(q["relative_error_over_uptake"]))
    return out


def references_part(name, context):
    """The references through their usage note's API only (validation/fr3/references/
    REFERENCES_USAGE.md: api.reference and api.accessibility), on the registered inputs, whose
    git blob must be the one the references' design file records (refused otherwise)."""
    from validation.fr3.references import api

    del name, context
    started = time.perf_counter()
    data = af.INPUTS.read_bytes()
    design = json.loads(af.DESIGN.read_text())
    blob = git_blob(data)
    if blob != design["inputs"]["git_blob"]:
        raise SystemExit("Refused: the references' inputs are not the registered file (their "
                         "git blob differs from the design file's)")
    inputs = json.loads(data)
    worlds = {wid: reference_record(api.reference(world), world)
              for wid, world in inputs["worlds"].items()}
    accessibility = {}
    for regime in Q4_REGIMES:
        found = api.accessibility({1.0: inputs["worlds"][f"q4_alpha_1_{regime}"],
                                   0.5: inputs["worlds"][f"q4_alpha_1_2_{regime}"],
                                   0.25: inputs["worlds"][f"q4_alpha_1_4_{regime}"]})
        accessibility[regime] = {key: {f"{a:g}": float(v) for a, v in found[key].items()}
                                 for key in ("theta_ratio", "relaxation_rate_per_s")}
    return dict(kind="reference", admitted=True, completed=True, worlds=worlds,
                accessibility=accessibility, inputs_git_blob=blob,
                wall_s=time.perf_counter() - started)


def stand_in(name, context):
    del context
    raise SystemExit(f"{name} is a stand-in (STAND_INS)")


def _dev_rung(world_id, dt):
    def part(name, context):
        del name
        return engine_part(af.registered_world(world_id, dt=dt), context,
                           label=f"{world_id} at {dt:g} s (development)", arm=world_id)
    return part


FUNCTIONS = {
    **{w: _world(w) for w in WORLD_PARTS},
    **{n: _world(af.LADDER_WORLD, dt) for n, dt in LADDER_PARTS.items()},
    "K_rates": k_rates, "K_alpha": k_alpha, "K_binding_multiplier": k_binding_multiplier,
    "K_internalisation_multiplier": k_internalisation_multiplier, "K_cell_volume": k_cell_volume,
    "Q4_kinetic": _q4(af.kinetic_factor), "Q4_affinity": _q4(af.affinity_factor),
    **{n: _plants(names) for n, names in PLANT_PARTS.items()},
    "Q6_restart": q6_restart, "Q6_batch": q6_batch, "Q6_idle": q6_idle, "Q6_twins": q6_twins,
    "Q6_signature": q6_signature, "Q6_refusals": q6_refusals, "references": references_part,
    **{n: _dev_rung(w, dt) for n, (w, dt) in DEV_PARTS.items()},
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
