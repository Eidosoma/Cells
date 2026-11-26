"""Track E's conduction probe on the engine as it is (D155 item 3): exploratory, not judged.

Question. Can the channel laws cells.model.resolved_pump_tissue@3 admits produce an action potential in one
cell and propagate it along a short static chain of cells joined by @3's gap junctions, at a
feasible step under @3's IMEX solvers and every host and device check? The verdict decides
between proceeding with the existing mechanisms and naming the particular missing mechanism the
excitable-tissue feature must add. This driver changes no engine source; it builds definitions
from the validation fixtures and reads every number from the engine's own run path, observer,
step checks, host checks and device checks.

Success criteria, fixed before any run (the coordinator's update of 14 November 2026; the plan's
operational definitions are in PLAN, also written to plan.json):
  C1 Regeneration: excitation continues beyond the stimulated cells after the stimulus ends.
  C2 Controls: passive (every voltage-gated population unavailable), subthreshold (a stimulus
     below capture) and sodium-disabled (NaV1.2 unavailable) controls distinguish regeneration
     from passive spread.
  C3 Measures: activation time, conduction velocity, capture, recovery and block, each
     measured explicitly.
  C4 Robustness: timestep refinement stabilises those measures; chain-length and
     boundary-distance checks show they are not a boundary artefact.
  C5 Accounting and record: material, charge and energy checks keep passing (the model's host
     checks on every accepted row; its device row checks on the vector-window path), and the
     admitted mechanisms and the numerical cost are recorded with the result.
Order: the single cell with its controls first (part single); the chain only if the single
cell regenerates (part chain); then the verdict (part verdict), before any design note.

Engine models run (nothing here adds physics):
* cells.model.resolved_pump_tissue@3: cells.channel.kv1p5_mh@1, cells.channel.kir2p1_mh2@1, cells.channel.nav1p2_m3h_regularized@1,
  cells.channel.kleak_always_open@1 and cells.channel.naleak_always_open@1 populations; cells.route.constant_field@1 leaks and
  junctions; cells.cycle.nak_atp_mass_action_positive@1 pumps; cells.junction.junction_voltage_relaxation@1 gates (pinned
  open, or as declared); IMEX ARS(2,2,2) and Euler with exponential stage gates
  (exponential_mean_rate_linear_target_gates@1), and @3's own RK4 path as its step reference.
  Field solver: whatever validation/tissue/field_solver_choice.declare() gives (D147). Every
  world here has held baths only, so no free field offsets: each world records its count and
  declared solver.

World. surface_pump_v3_fixtures.heredity_cells (the heredity pre-screen's cell: BETSE v1.5.0
default-world coefficients, Na leak x0.2, Kir2.1 1e-8 m/s, NaV1.2 2.5e-7 m/s, 310 K, own held
bath, its H state) plus one Kv1.5 population per cell, alone or in a chain joined by the E07-v1
junction (validation/stationary/worlds.e07_junction: area 5.34e-11 m^2, BETSE default
gap-junction permeabilities) multiplied by a coupling factor s. Parameters are synthetic, not a
measured cell type.

Stimuli. A kick (Na added so that Vm rises by the stated mV with gates at rest;
surface_pump_v3_fixtures.kicked), or a 1 ms cation conductance: one cells.channel.kleak_always_open@1 and one
cells.channel.naleak_always_open@1 population of equal permeability on each stimulated cell (reversal near
0 mV), switched by @3's own channel_controls.

Execution. cells.execution.windows.iter_windows (each step's own refusal, the host checks on every
accepted row, the model's observer every millisecond). Membrane and junction voltages at every
accepted step come from the engine's own readouts (surface_pump_v3.readouts, compiled) on each
window's accepted history, checked against the observer's rows. The device row checks run in
cells.execution.vector_windows.run_vector_windowed. Refusals are attributed with the engine's own
functions at the last accepted state. Run through run_part.sh in the evidence folder.
"""

import argparse
import copy
import hashlib
import json
import math
import resource
import sys
import time
import traceback
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

jax.config.update("jax_enable_x64", True)

import cells  # noqa: E402
from cells.definitions.specs import ConfigError, parse_spec  # noqa: E402
from cells.definitions.surface_pump_v3_spec import (  # noqa: E402
    KLEAK_LAW_ID,
    KV1P5_LAW_ID,
    NALEAK_LAW_ID,
    Control,
)
from cells.definitions.surface_pump_v3_spec import control_values as v3_controls  # noqa: E402
from cells.execution.errors import NumericalError  # noqa: E402
from cells.execution.windows import WindowPolicy, iter_windows  # noqa: E402
from cells.laws.channels import voltage_gates  # noqa: E402
from cells.laws.electrochemistry import CHARGE_PER_FMOL  # noqa: E402
from cells.laws.junctions import junction_gate  # noqa: E402
from cells.models import surface_pump_v3 as v3  # noqa: E402
from validation.stationary import worlds  # noqa: E402
from validation.tissue import field_solver_choice  # noqa: E402
from validation.tissue import surface_pump_v3_fixtures as fx  # noqa: E402

ARS = "cells.solver.imex_ars222_face_electromigration@1"
EULER = "cells.solver.imex_euler_face_electromigration@1"
H = fx.HEREDITY_STATES["H"]  # (Vm, Na, K, M, fastest relaxation time)
# The point every definition of a part uses: NaV1.2 and Kir2.1 permeabilities (m/s), specific
# capacitance (F/m^2) and the rest (Vm, Na, K, M) its cells start from (gates at rest). The
# default is the heredity cell at its H state; parts set it from their arguments (set_point),
# and a point other than the heredity cell's takes its rest from a relaxation (relax_rest).
POINT = dict(
    nav_m_s=fx.HEREDITY_NAV_M_S, kir_m_s=fx.HEREDITY_KIR_M_S, cm_F_m2=0.05, rest=tuple(H[:4])
)
HEREDITY_CM_F_M2 = 0.05
CELL_SPACING_M = 9.25e-6  # resolved_scale_world.geometry spacing (W225): for m/s only
DT_LADDER = (1e-3, 5e-4, 2.5e-4, 1e-4, 5e-5, 2.5e-5, 1e-5, 5e-6, 2.5e-6, 1.25e-6, 6.25e-7)
VOLTAGE_CHUNK = 128

PLAN = dict(
    status="fixed before any run (exploratory probe; no judged reading)",
    definitions=dict(
        activation="a cell's activation time: its first upward crossing of -30 mV after the "
        "stimulus onset, linearly interpolated between accepted steps",
        action_potential="an activation whose peak exceeds 0 mV (overshoot)",
        repolarised="Vm back within 5 mV of the pre-stimulus rest within 60 ms of the upstroke",
        single_cell_recovery="the shortest S1-S2 interval at which S2 (1 ms, twice the "
        "stimulus threshold) gives a new upward crossing of -30 mV followed by an overshoot",
        regenerates_single_cell="a suprathreshold kick gives an overshooting upstroke whose "
        "max dV/dt after the kick exceeds 10 V/s, while the same kick with NaV1.2 unavailable "
        "gives no regenerative rise after t = 0 (max dV/dt below 1 V/s) and no overshoot, and "
        "the response is all-or-none across the kick threshold (peaks 0.5 mV either side "
        "differ by > 50 mV)",
        C1="in the chain, every cell from the 4th beyond the stimulated set to the far end "
        "fires an action potential, each activating after the stimulus has ended",
        C2="with the same stimulus, the passive, subthreshold and sodium-disabled controls "
        "activate no cell beyond the first two outside the stimulated set, and their peak "
        "depolarisation decreases with distance",
        C3="activation times of every cell; CV as the inverse least-squares slope of activation "
        "time over the middle third of the chain (cells/s; m/s at 9.25 um spacing); capture "
        "as the stimulus permeability threshold for a wave reaching the far end; recovery as "
        "the shortest S1-S2 interval giving a second wave at the far end; block as the "
        "coupling bracket between a blocked and a propagating chain",
        C4="CV at the two finest steps within 2%, activation times within 5% of the "
        "delay per cell; CV over three spans of the 40-cell chain within 2% of each other and "
        "of the 20-cell chain's middle third",
        C5="no host-check, device-check or step refusal in an accepted case (a refusal is "
        "recorded and attributed); law, solver and field-solver IDs, D147 offsets, steps, "
        "compile and execute times recorded per case",
    ),
    selection="Kv1.5 permeability: the smallest of the scan whose suprathreshold kick (50 mV) "
    "gives a repolarised action potential with peak <= +55 mV and no refusal at dt 10 us",
    single_cell=[
        "Kv1.5 scan 0, 1e-8, 3e-8, 1e-7, 3e-7 m/s, kick 50 mV, ARS(2,2,2) 10 us, 80 ms",
        "rest: 4 s unstimulated at 1 ms",
        "kick threshold by bisection on [0, 60] mV",
        "controls at 2x the kick threshold: sodium-disabled, passive; subthreshold kick",
        "dt refinement: ARS(2,2,2) 1 ms to 2.5 us, Euler 100 to 2.5 us, @3 RK4 2.5 and 1.25 us",
        "stimulus threshold (1 ms cation conductance) by bisection; S1-S2 recovery at 2x",
    ],
    chain=[
        "20 cells, cells 0-2 stimulated 1 ms (cation conductance 1e-6 m/s per ion), "
        "coupling s in 10, 30, 100, 300, 1000, 3000 at dt = min(10 us, static bound)",
        "at the main coupling: passive, subthreshold and sodium-disabled controls; capture "
        "threshold; dt refinement (10, 5, 2.5 us); 40-cell length check; S1-S2 recovery; "
        "block bracket by bisection on s; the default junction-heat booking and gated "
        "junctions as arms",
        "chain runs book junction heat with cells.heat.trapezoid_nonnegative@1 (E07-v1's registered "
        "booking; the default explicit_tableau can book a negative increment where a junction "
        "voltage crosses zero), and the default booking runs as an arm",
        "device row checks (vector windows) on the main cases",
    ],
)


def log(line):
    print(time.strftime("%H:%M:%S"), line, flush=True)


def jsonable(value):
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, (np.floating, float)):
        v = float(value)
        return v if math.isfinite(v) else repr(v)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.ndarray):
        return jsonable(value.tolist())
    return value


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(jsonable(value), indent=1, sort_keys=True))
    tmp.replace(path)


def provenance():
    root = Path(cells.__file__).resolve().parents[2]
    manifest = root / "SNAPSHOT.json"
    out = dict(
        cells_file=cells.__file__,
        driver=__file__,
        argv=sys.argv,
        jax=jax.__version__,
        devices=[str(d) for d in jax.devices()],
    )
    if manifest.exists():
        value = json.loads(manifest.read_text())
        out.update(
            snapshot_manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
            git_revision=value.get("git_revision"),
            patch_sha256=value.get("patch_sha256"),
        )
    return out


def peak_rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


# ----------------------------------------------------------------------------- definitions


def kv_gate(voltage):
    target, _ = voltage_gates.kinetics(np.array([voltage]), xp=np)
    return [float(target[0, 0]), float(target[1, 0])]


def kicked(rest, millivolts, cm):
    """A rest state with Na added so that Vm rises by the given mV (charge C dV)."""
    if cm == HEREDITY_CM_F_M2:
        return fx.kicked((*rest, None), millivolts)
    vm, na, k, mm = rest
    delta = cm * fx.HEREDITY_AREA_M2 * 1e-3 * millivolts
    return (vm + 1e-3 * millivolts, na + delta / CHARGE_PER_FMOL / fx.HEREDITY_VOLUME_PL, k, mm)


def rescale_capacitance(raw, cm, states):
    """heredity_cells' capacitance, initial charge and fixed charge at another specific
    capacitance: C = cm A, q = C Vm, fixed = q / F - sum z n (its own arithmetic)."""
    z = dict(fx.HEREDITY_SPECIES)
    for cell, membrane, state in zip(
        raw["model"]["cells"], raw["model"]["membranes"], states, strict=True
    ):
        capacitance = cm * fx.HEREDITY_AREA_M2
        charge = capacitance * state[0]
        amounts = cell["initial_amount_fmol"]
        membrane["capacitance_F"] = capacitance
        cell["initial_charge_C"] = charge
        cell["fixed_charge_equivalent_fmol"] = charge / CHARGE_PER_FMOL - math.fsum(
            z[sp] * amounts[sp] for sp in amounts
        )


def stimulus_scale():
    """Stimulus permeabilities scale with the specific capacitance, so that a stimulus has the
    heredity cell's rate (G/C) at any point (amendment 1's addendum)."""
    return POINT["cm_F_m2"] / HEREDITY_CM_F_M2


def set_point(nav_m_s, kir_m_s, cm_F_m2, rest=None):
    POINT.update(
        nav_m_s=nav_m_s,
        kir_m_s=kir_m_s,
        cm_F_m2=cm_F_m2,
        rest=tuple(H[:4]) if rest is None else tuple(rest),
    )


def relax_rest(kv_m_s, seconds=2.0):
    """The point's quasi-steady rest: Vm after an unstimulated 2 s at 1 ms from H's
    composition (gates at H's Vm); the composition is kept (it moves on minutes)."""
    set_point(POINT["nav_m_s"], POINT["kir_m_s"], POINT["cm_F_m2"])
    raw = definition(1, dt=1e-3, end_time=seconds, kv_m_s=kv_m_s, obs_dt=0.1)
    r = execute(raw)
    out = dict(refusal=r["refusal"], steps=r["steps"])
    if r["times"]:
        t, vm = np.asarray(r["times"]), np.asarray(r["vm"])[:, 0]
        last = t >= t[-1] - 0.5
        out.update(rest_V=float(vm[-1]), drift_last_0p5s_V=float(vm[-1] - vm[last][0]))
    rest = (out.get("rest_V", H[0]), *H[1:4])
    set_point(POINT["nav_m_s"], POINT["kir_m_s"], POINT["cm_F_m2"], rest)
    out["rest"] = list(rest)
    return out


def junction_gate_block(gated):
    j = worlds.e07_junction()
    if gated:
        par = junction_gate.Parameters(j["threshold_voltage_V"], j["minimum_open_fraction"])
        target = float(junction_gate.kinetics(np.asarray(0.0), par, xp=np).target)
        gate = dict(
            law=junction_gate.LAW_ID,
            threshold_voltage_V=j["threshold_voltage_V"],
            minimum_open_fraction=j["minimum_open_fraction"],
            initial_gate=target,
        )
    else:  # Pinned open (mg0b_domain_wall.GATE_OPEN): zero gate rate, no gate step bound.
        gate = dict(
            law=junction_gate.LAW_ID,
            threshold_voltage_V=0.0,
            minimum_open_fraction=1.0,
            initial_gate=1.0,
        )
    return j, gate


CONTROLS = {
    "excitable": {},
    "sodium_disabled": {"nav": 0.0},
    "passive": {"nav": 0.0, "kv": 0.0, "kir": 0.0},
}


def definition(
    n,
    *,
    dt,
    end_time,
    kv_m_s,
    solver=ARS,
    temperature_K=310.0,
    kicks=None,
    s=None,
    gated=False,
    stim=None,
    booking=None,
    control="excitable",
    obs_dt=1e-3,
    cell_nav=None,
    junction_availability=None,
    edges=None,
):
    """n heredity cells (own held baths) with Kv1.5; a chain of junctions at coupling s.

    cell_nav {cell: availability} and junction_availability {junction: availability} hold a
    segment's NaV1.2 and junction availabilities from t = 0 (probe 2, PLAN amendment 3).
    edges [(a, b), ...] replaces the chain by that graph (M1's sheet); junction k joins edge k.

    kicks {cell: mV}; stim dict(cells, pulses [(on_step, off_step)], m_s) declares the
    stimulus populations on its cells (always declared when given, so worlds share shapes);
    control sets the availability of each cell's NaV1.2, Kv1.5 and Kir2.1 (CONTROLS). Events
    and observations are integer multiples of dt. D147: field_solver_choice.declare().
    """
    rest, cm = tuple(POINT["rest"]), POINT["cm_F_m2"]
    states = [rest] * n
    for i, mv in (kicks or {}).items():
        states[i] = kicked(rest, mv, cm)
    steps = int(round(end_time / dt))
    stride = max(1, int(round(obs_dt / dt)))
    times = [k * dt for k in range(0, steps + 1, stride)]
    if times[-1] != steps * dt:
        times.append(steps * dt)
    raw = fx.heredity_cells(
        states,
        dt=dt,
        end_time=steps * dt,
        solver=solver,
        observation_times=times,
        nav_m_s=POINT["nav_m_s"],
        kir_m_s=POINT["kir_m_s"],
        gate_voltages=[rest[0]] * n,
        temperature_K=temperature_K,
    )
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    if cm != HEREDITY_CM_F_M2:
        rescale_capacitance(raw, cm, states)
    if kv_m_s > 0:
        gate = kv_gate(rest[0])
        for i in range(n):
            m["channels"].append(fx.channel(f"kv_{i}", i, KV1P5_LAW_ID, "K", kv_m_s, 1.0, gate))
            e["channel_controls"].append(
                dict(channel_id=f"kv_{i}", schedule=[dict(time=0.0, availability=1.0)])
            )
    if stim is not None:
        schedule = [dict(time=0.0, availability=0.0)]
        for on, off in stim["pulses"]:
            schedule += [
                dict(time=on * dt, availability=1.0),
                dict(time=off * dt, availability=0.0),
            ]
        for i in stim["cells"]:
            for name, law, ion in (("stimk", KLEAK_LAW_ID, "K"), ("stimna", NALEAK_LAW_ID, "Na")):
                m["channels"].append(fx.channel(f"{name}_{i}", i, law, ion, stim["m_s"], 1.0, []))
                e["channel_controls"].append(
                    dict(channel_id=f"{name}_{i}", schedule=copy.deepcopy(schedule))
                )
    for group in e["channel_controls"]:
        kind = group["channel_id"].split("_")[0]
        if kind in CONTROLS[control]:
            group["schedule"] = [dict(time=0.0, availability=CONTROLS[control][kind])]
        cell = group["channel_id"].split("_")[-1]
        if kind == "nav" and cell_nav and int(cell) in cell_nav:
            group["schedule"] = [dict(time=0.0, availability=float(cell_nav[int(cell)]))]
    x["channel_capacity"] = len(m["channels"])
    if s is not None and n > 1:
        pairs = [(k, k + 1) for k in range(n - 1)] if edges is None else list(edges)
        j, gate = junction_gate_block(gated)
        m["junctions"] = [
            dict(
                id=f"junction_{k}",
                sender=f"cell_{a}",
                receiver=f"cell_{b}",
                area_m2=j["area_m2"],
                permeability_m_per_s={sp: s * v for sp, v in j["permeability_m_per_s"].items()},
                law="cells.route.constant_field@1",
                gate=dict(gate),
            )
            for k, (a, b) in enumerate(pairs)
        ]
        held = junction_availability or {}
        e["junction_controls"] = [
            dict(
                junction_id=f"junction_{k}",
                schedule=[dict(time=0.0, availability=float(held.get(k, 1.0)))],
            )
            for k in range(len(pairs))
        ]
        x["edge_capacity"] = len(pairs)
    if booking is not None:
        m["junction_heat_booking"] = booking
    x["max_steps"] = steps + 16
    return field_solver_choice.declare(raw)


def mechanisms(raw):
    """The admitted mechanisms of a definition and its D147 record."""
    m, x = raw["model"], raw["execution"]
    return dict(
        model=m["id"],
        time_integrator=x["solver"],
        field_solver=x["field_solver"],
        free_field_offsets=field_solver_choice.free_field_offsets(raw),
        channel_laws=sorted({c["kinetic_law"] for c in m["channels"]}),
        membrane_law=sorted({p["law"] for p in m["membranes"]}),
        pump_law=sorted({p["pump"]["law"] for p in m["membranes"] if p.get("pump")}),
        junction_law=sorted({p["law"] for p in m["junctions"]}),
        junction_gate_law=sorted({p["gate"]["law"] for p in m["junctions"]}),
        junction_heat_booking=m.get("junction_heat_booking", "explicit_tableau"),
        dt_s=x["dt"],
        point=dict(
            nav_m_s=POINT["nav_m_s"],
            kir_m_s=POINT["kir_m_s"],
            cm_F_m2=POINT["cm_F_m2"],
            rest=list(POINT["rest"]),
        ),
        cells=len(m["cells"]),
        temperature_K=m["temperature_K"],
    )


def static_bounds(raw):
    """The engine's own definition-level rate bounds (1/s) and the steps they admit."""
    checks = v3.StepChecks(parse_spec(raw))
    explicit, gate = float(checks.explicit_rate), float(checks.junction_rate)
    return dict(
        explicit_rate_per_s=explicit,
        junction_gate_rate_per_s=gate,
        largest_dt_explicit_s=1.0 / explicit if explicit else None,
        largest_dt_gate_s=0.125 / gate if gate else None,
    )


def admissible(bounds):
    limits = [v for v in (bounds["largest_dt_explicit_s"], bounds["largest_dt_gate_s"]) if v]
    return min(limits) if limits else None


def ladder_dt(limit, cap):
    """The largest ladder step at or below the cap and strictly below the static limit.

    Probe 1's version excluded the cap itself (its planned 10 us ran at 5 us); D170 ruling 6
    asks that the ladder include its own cap.
    """
    for dt in DT_LADDER:
        if dt <= cap * (1 + 1e-12) and (limit is None or dt < limit * (1 - 1e-12)):
            return dt
    return DT_LADDER[-1]


# ----------------------------------------------------------------------------- execution


@jax.jit
def _engine_voltages(states, controls, layout):
    """The engine's membrane and junction voltages and validity at each accepted row."""

    def one(state, control):
        w = v3.readouts(state, control, layout)
        r = w.field.rates
        return r.membrane_voltage_V, r.junction_voltage_V, w.valid

    return jax.vmap(one)(states, controls)


def window_voltages(spec, window, skip_first):
    times = np.asarray(window.times)
    history = window.history
    controls = v3_controls(spec, times)
    rows = len(times)
    vm, vj, ok = [], [], []
    for start in range(0, rows, VOLTAGE_CHUNK):
        index = np.minimum(np.arange(start, start + VOLTAGE_CHUNK), rows - 1)
        states = type(history)(*(jnp.asarray(np.asarray(v)[index]) for v in history))
        control = type(controls)(*(jnp.asarray(np.asarray(v)[index]) for v in controls))
        a, b, c = _engine_voltages(states, control, window.final.layout)
        keep = min(VOLTAGE_CHUNK, rows - start)
        vm.append(np.asarray(a)[:keep])
        vj.append(np.asarray(b)[:keep])
        ok.append(np.asarray(c)[:keep])
    first = 1 if skip_first else 0
    return (
        times[first:],
        np.concatenate(vm)[first:],
        np.concatenate(vj)[first:],
        bool(np.all(np.concatenate(ok))),
    )


def execute(raw, *, window_steps=1024, stop=None):
    """iter_windows: Vm and Vj at every accepted step, diagnostics, timings and any refusal."""
    out = dict(
        times=[],
        vm=[],
        vj=[],
        diagnostics={},
        timings={},
        steps=0,
        refusal=None,
        observer_max_abs_dV=0.0,
        readouts_valid=True,
    )
    last, started, spec = None, time.perf_counter(), None
    voltage_seconds = 0.0
    try:
        spec = parse_spec(raw)
        for window in iter_windows(spec, WindowPolicy(window_steps, "observations")):
            before = time.perf_counter()
            t, vm, vj, ok = window_voltages(spec, window, skip_first=bool(out["times"]))
            voltage_seconds += time.perf_counter() - before
            out["times"].extend(t.tolist())
            out["vm"].extend(vm.tolist())
            out["vj"].extend(vj.tolist())
            out["readouts_valid"] &= ok
            obs = window.observations
            for row, when in enumerate(np.asarray(obs.times)):
                k = np.flatnonzero(t == when)
                if len(k):
                    diff = np.max(np.abs(np.asarray(obs.membrane_voltage_V)[row] - vm[k[0]]))
                    out["observer_max_abs_dV"] = max(out["observer_max_abs_dV"], float(diff))
            for k, v in window.diagnostics.items():
                out["diagnostics"][k] = max(out["diagnostics"].get(k, 0.0), float(v))
            for k, v in window.timings.items():
                out["timings"][k] = out["timings"].get(k, 0.0) + float(v)
            out["steps"] = int(window.final.step_index)
            last = window.final
            if stop is not None and stop(out):
                out["stopped_early_at_s"] = float(window.final.time)
                break
    except (NumericalError, ConfigError) as error:
        out["refusal"] = dict(
            kind=type(error).__name__,
            message=str(error),
            last_accepted_window_end_s=None if last is None else float(last.time),
        )
        if last is None and isinstance(error, NumericalError):
            from cells.execution.state import initialise

            try:  # A refusal inside the first window: attribute from the initial state.
                last = initialise(parse_spec(raw))
            except (NumericalError, ConfigError):
                last = None
    out["timings"]["probe_voltage_seconds"] = voltage_seconds
    out["wall_seconds"] = time.perf_counter() - started
    out["last"] = last
    return out


def attribute(raw, checkpoint):
    """Name a refused step's cause with the engine's own functions (host, numpy).

    One-step windows from the last accepted window end reach the last accepted state S. At S:
    readouts validity, the Vm and Vj ranges against the channel (-120..60 mV) and junction
    (|Vj| <= 120 mV) domains, and dt x membrane_rate. Then the refused interval is retried on
    the host as 1, 2, 4 and 8 sub-steps, with the same predicates at each retry's end.
    """
    spec = parse_spec(raw)
    dt = spec.execution.dt
    out, last, message = {}, checkpoint, None
    try:
        for window in iter_windows(spec, WindowPolicy(1, "observations"), checkpoint):
            last = window.final
    except (NumericalError, ConfigError) as error:
        message = str(error)
    out["one_step_refusal"] = message
    out["last_accepted_time_s"] = float(last.time)
    p = type(last.layout)(*(np.asarray(v) for v in last.layout))
    control = Control(*(np.asarray(v[0]) for v in v3_controls(spec, [last.time])))
    state = v3.STATE_TYPE(*(np.asarray(v) for v in last.state))

    def predicates(st):
        with np.errstate(all="ignore"):
            w = v3.readouts(st, control, p, xp=np)
            r = w.field.rates
            vm = np.asarray(r.membrane_voltage_V)[np.asarray(p.membrane_active, dtype=bool)]
            vj = np.asarray(r.junction_voltage_V)
            if vj.size:
                vj = vj[np.asarray(p.junction_active, dtype=bool)]
            rate = float(v3.membrane_rate(st, control, p, xp=np))
        return dict(
            readouts_valid=bool(w.valid),
            vm_min_V=float(vm.min()),
            vm_max_V=float(vm.max()),
            channel_domain_ok=bool(vm.min() >= -0.120 and vm.max() <= 0.060),
            vj_abs_max_V=float(np.abs(vj).max()) if vj.size else 0.0,
            junction_domain_ok=bool(np.abs(vj).max() <= 0.120) if vj.size else True,
            membrane_rate_per_s=rate,
            dt_times_membrane_rate=dt * rate,
        )

    out["at_last_accepted"] = predicates(state)
    trials = {}
    for parts in (1, 2, 4, 8):
        h, st, accepted, error_text = dt / parts, state, True, None
        try:
            with np.errstate(all="ignore"):
                for _ in range(parts):
                    st, ok = v3.imex_step(st, h, control, p, xp=np)
                    accepted &= bool(ok)
                    if not ok:
                        break
        except Exception as error:  # A host retry is a diagnostic only.
            error_text = repr(error)
        trials[str(parts)] = dict(substep_s=h, accepted=accepted, error=error_text)
        if accepted and error_text is None:
            trials[str(parts)]["end"] = predicates(st)
    out["host_retry"] = trials
    return out


# ----------------------------------------------------------------------------- measures


def crossings(t, v, level, start=0):
    """Every upward linear-interpolated crossing of level from index start."""
    out = []
    for i in range(max(start, 1), len(v)):
        a, b = v[i - 1], v[i]
        if a < level <= b:
            out.append(float(t[i - 1] + (level - a) * (t[i] - t[i - 1]) / (b - a)))
    return out


def falling(t, v, level, start):
    for i in range(max(start, 1), len(v)):
        a, b = v[i - 1], v[i]
        if a > level >= b:
            return float(t[i - 1] + (level - a) * (t[i] - t[i - 1]) / (b - a))
    return None


def ap_features(t, v, *, after=0.0, rest=None):
    """Rest, peak, upstroke and repolarisation of one cell's trace after a time."""
    t, v = np.asarray(t), np.asarray(v)
    first = int(np.searchsorted(t, after))
    if rest is None:
        rest = float(v[max(first - 1, 0)])
    k = first + int(np.argmax(v[first:]))
    peak = float(v[k])
    dv = np.diff(v[first:]) / np.diff(t[first:]) if len(v) - first > 1 else np.zeros(1)
    up = first + int(np.argmax(dv))
    out = dict(
        rest_V=rest,
        peak_V=peak,
        time_to_peak_s=float(t[k] - after),
        max_dVdt_V_s=float(dv.max()),
        upstroke_time_s=float(0.5 * (t[up] + t[min(up + 1, len(t) - 1)])),
        end_V=float(v[-1]),
        min_after_peak_V=float(v[k:].min()),
    )
    amplitude = peak - rest
    for fraction in (0.5, 0.9):
        cross = falling(t, v, peak - fraction * amplitude, k)
        out[f"apd{int(fraction * 100)}_s"] = (
            None if cross is None else cross - out["upstroke_time_s"]
        )
    back = falling(t, v, rest + 0.005, k)
    out["repolarised"] = bool(back is not None and back - out["upstroke_time_s"] <= 0.06)
    if peak > 0.0 and out["repolarised"]:
        out["class"] = "action potential, repolarised"
    elif peak > 0.0 and v[-1] > -0.040:
        out["class"] = "overshoot, latched depolarised"
    elif peak > 0.0:
        out["class"] = "overshoot, not repolarised within 60 ms"
    else:
        out["class"] = "no overshoot"
    return out


def chain_measures(t, vm, *, stim_cells, stim_end, span=None):
    """Activations, C1 and C2 tests, CV over a span, delays, peaks along the chain."""
    t, vm = np.asarray(t), np.asarray(vm)
    n = vm.shape[1]
    acts = [crossings(t, vm[:, i], -0.030) for i in range(n)]
    first = [a[0] if a else None for a in acts]
    peaks = vm.max(axis=0).tolist()
    beyond = [i for i in range(n) if i > max(stim_cells)]
    c1_cells = [i for i in beyond if i >= max(stim_cells) + 4]
    c1 = bool(c1_cells) and all(
        first[i] is not None and first[i] > stim_end and peaks[i] > 0.0 for i in c1_cells
    )
    far = [i for i in beyond if i >= max(stim_cells) + 3]
    c2_quiet = all(first[i] is None for i in far)
    outside = [peaks[i] for i in beyond]
    c2_decreasing = all(b <= a + 1e-6 for a, b in zip(outside, outside[1:], strict=False))
    lo, hi = span if span is not None else (n // 3, (2 * n) // 3)
    cv = None
    if all(first[i] is not None for i in range(lo, hi + 1)):
        slope = np.polyfit(np.arange(lo, hi + 1), [first[i] for i in range(lo, hi + 1)], 1)[0]
        cv = 1.0 / slope if slope > 0 else None
    reached = [i for i in range(n) if first[i] is not None]
    return dict(
        activation_s=first,
        activations_per_cell=[len(a) for a in acts],
        all_activations_s=acts,
        peak_V=peaks,
        last_activated_cell=max(reached) if reached else None,
        propagated_to_end=first[-1] is not None,
        captured=all(peaks[i] > 0.0 for i in stim_cells),
        c1_regeneration=c1,
        c2_no_spread=c2_quiet,
        c2_peaks_decrease=c2_decreasing,
        cv_span=[lo, hi],
        cv_cells_per_s=cv,
        cv_m_per_s=None if cv is None else cv * CELL_SPACING_M,
        delay_per_cell_s=[
            None if first[k] is None or first[k + 1] is None else first[k + 1] - first[k]
            for k in range(n - 1)
        ],
    )


def record(raw, r, **extra):
    """A case's record: mechanisms, refusal, checks, cost."""
    out = dict(
        mechanisms=mechanisms(raw),
        steps=r["steps"],
        wall_seconds=r["wall_seconds"],
        timings=r["timings"],
        diagnostics=r["diagnostics"],
        refusal=r["refusal"],
        readouts_valid=r["readouts_valid"],
        observer_max_abs_dV=r["observer_max_abs_dV"],
        stopped_early_at_s=r.get("stopped_early_at_s"),
        **extra,
    )
    if r["steps"] and r["timings"].get("execute_seconds"):
        out["execute_ms_per_step"] = 1e3 * r["timings"]["execute_seconds"] / r["steps"]
        out["host_analysis_ms_per_step"] = (
            1e3 * r["timings"].get("analysis_seconds", 0.0) / r["steps"]
        )
    if r["refusal"] and r["last"] is not None and raw["execution"]["solver"] != "rk4":
        try:
            out["attribution"] = attribute(raw, r["last"])
        except Exception:  # Attribution is diagnostic; keep the failure as evidence.
            out["attribution_error"] = traceback.format_exc()
    return out


# ----------------------------------------------------------------------------- single cell


def single_run(
    kv,
    *,
    dt=1e-5,
    end=0.08,
    kick=None,
    stim=None,
    control="excitable",
    solver=ARS,
    temperature_K=310.0,
):
    raw = definition(
        1,
        dt=dt,
        end_time=end,
        kv_m_s=kv,
        solver=solver,
        temperature_K=temperature_K,
        kicks=None if kick is None else {0: kick},
        stim=stim,
        control=control,
    )
    r = execute(raw)
    rec = record(raw, r, kick_mV=kick, control=control)
    if len(r["times"]) > 2:
        after = 0.0 if stim is None else stim["pulses"][0][0] * dt
        rec["features"] = ap_features(
            r["times"],
            np.asarray(r["vm"])[:, 0],
            after=after,
            rest=POINT["rest"][0] if kick is not None else None,
        )
        dv = np.diff(np.asarray(r["vm"])[:, 0]) / np.diff(np.asarray(r["times"]))
        rec["max_dVdt_from_t0_V_s"] = float(dv.max())
    return rec, r


def part_single(args):
    out = dict(provenance=provenance(), plan=PLAN, part="single")
    path = Path(args.output) / "single.json"
    write_json(Path(args.output) / "plan.json", dict(provenance=provenance(), plan=PLAN))
    out["kv_scan"] = []
    set_point(args.nav, args.kir, args.cm)
    heredity = (args.nav, args.kir, args.cm) == (
        fx.HEREDITY_NAV_M_S,
        fx.HEREDITY_KIR_M_S,
        HEREDITY_CM_F_M2,
    )
    rests = {}
    for kv in args.kv_values:
        if heredity:  # The plan's run: the H state as declared.
            set_point(args.nav, args.kir, args.cm)
            rests[kv] = dict(rest=list(H[:4]), source="H state (heredity cell)")
        else:
            rests[kv] = dict(source="relaxation", **relax_rest(kv))
        kick = 50.0 if args.kick_to is None else 1e3 * (args.kick_to - POINT["rest"][0])
        rec, _ = single_run(kv, kick=kick)
        out["kv_scan"].append(dict(kv_m_s=kv, rest=rests[kv], **rec))
        f = rec.get("features", {})
        log(
            f"kv {kv:g}: {f.get('class')} peak {f.get('peak_V')} end {f.get('end_V')} "
            f"refusal {rec['refusal'] and rec['refusal']['message'][:80]}"
        )
        write_json(path, out)
    chosen = [
        c["kv_m_s"]
        for c in out["kv_scan"]
        if not c["refusal"]
        and c.get("features", {}).get("class") == "action potential, repolarised"
        and c["features"]["peak_V"] <= 0.055
    ]
    kv = min(chosen) if chosen else None
    out["selected_kv_m_s"] = kv
    out["point"] = dict(nav_m_s=args.nav, kir_m_s=args.kir, cm_F_m2=args.cm)
    out["selection_rule"] = PLAN["selection"]
    log(f"selected Kv1.5 {kv}")
    write_json(path, out)
    if kv is None:  # Still characterise the cell: rest, threshold and controls at kv = 0.
        kv = 0.0
        out["characterised_kv_m_s"] = kv
    if heredity:
        set_point(args.nav, args.kir, args.cm)
    elif kv in rests:
        set_point(args.nav, args.kir, args.cm, rests[kv]["rest"])
    else:
        rests[kv] = dict(source="relaxation", **relax_rest(kv))
    out["characterised_rest"] = list(POINT["rest"])
    # Rest.
    rec, r = single_run(kv, dt=1e-3, end=4.0)
    vm, t = np.asarray(r["vm"])[:, 0], np.asarray(r["times"])
    i2 = int(np.searchsorted(t, 2.0))
    out["rest"] = dict(
        start_V=float(vm[0]),
        at_2s_V=float(vm[i2]),
        at_4s_V=float(vm[-1]),
        drift_2_to_4s_V=float(vm[-1] - vm[i2]),
        record=rec,
    )
    log(f"rest {out['rest']['at_4s_V']}")
    write_json(path, out)
    # Kick threshold.
    trail, lo, hi = [], 0.0, 60.0

    def fires(kick):
        rec, _ = single_run(kv, kick=kick, end=0.06)
        trail.append(
            dict(
                kick_mV=kick,
                peak_V=rec.get("features", {}).get("peak_V"),
                cls=rec.get("features", {}).get("class"),
                refusal=rec["refusal"],
            )
        )
        return None if rec["refusal"] else rec["features"]["peak_V"] > 0.0

    threshold = None
    if fires(hi):
        for _ in range(args.bisections):
            mid = 0.5 * (lo + hi)
            ok = fires(mid)
            if ok is None:
                break
            lo, hi = (lo, mid) if ok else (mid, hi)
        threshold = hi
    out["kick_threshold"] = dict(threshold_mV=threshold, bracket_mV=[lo, hi], trail=trail)
    log(f"kick threshold {threshold} ({lo}, {hi})")
    write_json(path, out)
    if threshold is None:
        out["verdict_single"] = "no overshoot at kicks up to 60 mV"
        write_json(path, out)
        return
    # Controls and the all-or-none test.
    out["controls"] = {}
    supra = min(2 * threshold, 60.0)
    for label, kick, control in (
        ("suprathreshold_2x", supra, "excitable"),
        ("sodium_disabled_2x", supra, "sodium_disabled"),
        ("passive_2x", supra, "passive"),
        ("subthreshold_minus_0p5mV", max(threshold - 0.5, 0.0), "excitable"),
        ("threshold_plus_0p5mV", threshold + 0.5, "excitable"),
        ("subthreshold_minus_5mV", max(threshold - 5.0, 0.0), "excitable"),
    ):
        rec, _ = single_run(kv, kick=kick, control=control)
        out["controls"][label] = rec
        f = rec.get("features", {})
        log(f"control {label}: peak {f.get('peak_V')} max dV/dt {rec.get('max_dVdt_from_t0_V_s')}")
        write_json(path, out)
    c = out["controls"]
    na_ok = (
        c["sodium_disabled_2x"].get("max_dVdt_from_t0_V_s", 1.0) < 1.0
        and c["sodium_disabled_2x"]["features"]["peak_V"] <= 0.0
    )
    regen = (
        c["suprathreshold_2x"]["features"]["peak_V"] > 0.0
        and c["suprathreshold_2x"]["features"]["max_dVdt_V_s"] > 10.0
        and na_ok
        and c["threshold_plus_0p5mV"]["features"]["peak_V"]
        - c["subthreshold_minus_0p5mV"]["features"]["peak_V"]
        > 0.050
    )
    out["regenerates"] = bool(regen)
    out["recovers"] = bool(c["suprathreshold_2x"]["features"]["repolarised"])
    log(f"regenerates {regen}; repolarises {out['recovers']}")
    write_json(path, out)
    # Step refinement and the largest admissible step.
    out["dt_refinement"] = []
    runs = [("rk4", 2.5e-6), ("rk4", 1.25e-6)]
    runs += [(ARS, dt) for dt in DT_LADDER[:9]] + [(EULER, dt) for dt in DT_LADDER[3:9]]
    for solver, dt in runs:
        rec, r = single_run(kv, kick=supra, solver=solver, dt=dt)
        if r["times"] and dt >= 1e-5:
            rec["trace"] = dict(t=r["times"], vm=np.asarray(r["vm"])[:, 0].tolist())
        out["dt_refinement"].append(dict(solver=solver, dt_s=dt, **rec))
        f = rec.get("features", {})
        log(
            f"dt {solver} {dt:g}: peak {f.get('peak_V')} dV/dt {f.get('max_dVdt_V_s')} "
            f"apd90 {f.get('apd90_s')} refusal {rec['refusal'] and rec['refusal']['message'][:80]}"
        )
        write_json(path, out)
    # Stimulus threshold (1 ms cation conductance) and S1-S2 recovery at twice it.
    dt = 1e-5
    on, width = int(round(2e-3 / dt)), int(round(1e-3 / dt))
    trail, lo, hi = [], 1e-9 * stimulus_scale(), 1e-6 * stimulus_scale()

    def stim_fires(m_s):
        rec, _ = single_run(kv, end=0.06, stim=dict(cells=[0], pulses=[(on, on + width)], m_s=m_s))
        trail.append(
            dict(m_s=m_s, peak_V=rec.get("features", {}).get("peak_V"), refusal=rec["refusal"])
        )
        return None if rec["refusal"] else rec["features"]["peak_V"] > 0.0

    stim_threshold = None
    if stim_fires(hi):
        for _ in range(args.bisections):
            mid = math.sqrt(lo * hi)
            ok = stim_fires(mid)
            if ok is None:
                break
            lo, hi = (lo, mid) if ok else (mid, hi)
        stim_threshold = hi
    out["stimulus_threshold"] = dict(
        threshold_m_s=stim_threshold, bracket_m_s=[lo, hi], trail=trail
    )
    log(f"stimulus threshold {stim_threshold}")
    write_json(path, out)
    out["s1s2"] = []
    if stim_threshold is not None:
        for delta_ms in args.s1s2_ms:
            s2 = on + int(round(delta_ms * 1e-3 / dt))
            stim = dict(
                cells=[0], pulses=[(on, on + width), (s2, s2 + width)], m_s=2 * stim_threshold
            )
            rec, r = single_run(kv, end=s2 * dt + 0.04, stim=stim)
            row = dict(
                delta_ms=delta_ms,
                stimulus_m_s=2 * stim_threshold,
                refusal=rec["refusal"],
                record=rec,
            )
            if len(r["times"]) > 2:
                tt, vv = np.asarray(r["times"]), np.asarray(r["vm"])[:, 0]
                row["s2"] = ap_features(tt, vv, after=s2 * dt)
                up = crossings(tt, vv, -0.030, start=int(np.searchsorted(tt, s2 * dt)))
                # A response to S2: a new upward crossing of -30 mV after S2's onset, then an
                # overshoot (an incompletely repolarised S1 cannot count as one).
                row["s2_fired"] = bool(up) and float(vv[tt >= up[0]].max()) > 0.0
            out["s1s2"].append(row)
            log(f"S1-S2 {delta_ms} ms: S2 fired {row.get('s2_fired')}")
            write_json(path, out)
        fired = [r["delta_ms"] for r in out["s1s2"] if r.get("s2_fired")]
        failed = [r["delta_ms"] for r in out["s1s2"] if r.get("s2_fired") is False]
        out["recovery_bracket_ms"] = [
            max([d for d in failed if d < min(fired, default=1e9)], default=None),
            min(fired, default=None),
        ]
    out["peak_rss_mb"] = peak_rss_mb()
    write_json(path, out)


# ----------------------------------------------------------------------------- chain


def chain_run(
    args,
    s,
    *,
    n=None,
    dt,
    control="excitable",
    m_s=None,
    pulses=None,
    gated=False,
    booking="main",
    end=None,
    span=None,
):
    n = n or args.n
    stim_cells = list(range(args.stim_cells))
    on, width = int(round(2e-3 / dt)), int(round(1e-3 / dt))
    pulses = pulses or [(on, on + width)]
    m_s = args.stim_m_s * stimulus_scale() if m_s is None else m_s
    booking = args.booking if booking == "main" else booking
    raw = definition(
        n,
        dt=dt,
        end_time=end or args.chain_end,
        kv_m_s=args.kv,
        s=s,
        gated=gated,
        booking=booking,
        control=control,
        stim=dict(cells=stim_cells, pulses=pulses, m_s=m_s),
    )
    stim_end = pulses[-1][1] * dt

    def stop(o):  # The far end has fired once per pulse and 15 ms passed, or 25 ms all quiet.
        t = o["times"]
        if not t or t[-1] < stim_end + 0.01:
            return False
        vm = np.asarray(o["vm"])
        far = crossings(t, vm[:, -1], -0.030)
        if len(far) >= len(pulses) and t[-1] > far[-1] + 0.015:
            return True
        recent = np.asarray(t) > t[-1] - 0.025
        return bool(np.all(vm[recent] < -0.030) and t[-1] > stim_end + 0.03)

    r = execute(raw, stop=stop)
    rec = record(raw, r, s=s, n=n, control=control, stimulus_m_s=m_s, pulses=pulses, gated=gated)
    try:
        rec["static_bounds"] = static_bounds(raw)
    except ConfigError as error:
        rec["static_bounds"] = dict(refusal=str(error))
    if len(r["times"]) > 2:
        t, vm = np.asarray(r["times"]), np.asarray(r["vm"])
        rec["measures"] = chain_measures(t, vm, stim_cells=stim_cells, stim_end=stim_end, span=span)
        vj = np.asarray(r["vj"])
        rec["vm_max_V"], rec["vm_min_V"] = float(vm.max()), float(vm.min())
        rec["vj_abs_max_V"] = float(np.abs(vj).max()) if vj.size else 0.0
        rec["mid_cell"] = ap_features(t, vm[:, n // 2], after=pulses[0][0] * dt)
        if args.keep_traces:
            stride = max(1, int(round(2e-5 / dt)))
            rec["trace"] = dict(t=t[::stride].tolist(), vm=vm[::stride].tolist())
    return rec


def log_chain(prefix, c):
    m = c.get("measures", {})
    dt = c.get("mechanisms", {}).get("dt_s")
    log(
        f"{prefix} s {c['s']:g} dt {dt} {c['control']}: last {m.get('last_activated_cell')} "
        f"cv {m.get('cv_cells_per_s')} C1 {m.get('c1_regeneration')} vj {c.get('vj_abs_max_V')} "
        f"vmax {c.get('vm_max_V')} refusal {c['refusal'] and c['refusal']['message'][:90]}"
    )


def part_chain(args):
    out = dict(
        provenance=provenance(),
        plan=PLAN,
        part="chain",
        kv_m_s=args.kv,
        n=args.n,
        stimulus=dict(
            cells=args.stim_cells, m_s=args.stim_m_s, width_s=1e-3, scaled_with_capacitance=True
        ),
        bounds=[],
        sweep=[],
        controls=[],
        refinement=[],
        length=[],
        capture=[],
        recovery=[],
        block=[],
        arms=[],
    )
    path = Path(args.output) / "chain.json"
    set_point(args.nav, args.kir, args.cm)
    out["point"] = dict(nav_m_s=args.nav, kir_m_s=args.kir, cm_F_m2=args.cm, kv_m_s=args.kv)
    out["rest"] = relax_rest(args.kv) if not args.h_rest else dict(rest=list(H[:4]), source="H")
    log(f"chain point {out['point']} rest {POINT['rest'][0]}")
    write_json(path, out)

    def dt_for(s, cap):
        return ladder_dt(
            admissible(
                static_bounds(definition(args.n, dt=1e-5, end_time=0.01, kv_m_s=args.kv, s=s))
            ),
            cap,
        )

    for s in args.s_values:
        raw = definition(args.n, dt=1e-5, end_time=0.01, kv_m_s=args.kv, s=s)
        out["bounds"].append(dict(s=s, **static_bounds(raw), mechanisms=mechanisms(raw)))
    write_json(path, out)
    for s in args.s_values:
        c = chain_run(args, s, dt=dt_for(s, args.dt_cap))
        out["sweep"].append(c)
        log_chain("sweep", c)
        write_json(path, out)
    s0, dt0 = args.s_main, dt_for(args.s_main, args.dt_cap)
    for control, m_s in (("sodium_disabled", None), ("passive", None)):
        c = chain_run(args, s0, dt=dt0, control=control, m_s=m_s)
        out["controls"].append(c)
        log_chain("control", c)
        write_json(path, out)
    # Capture threshold at the main coupling (bisection on the stimulus permeability).
    lo, hi = (v * stimulus_scale() for v in args.capture_bracket)
    for _ in range(args.bisections):
        mid = math.sqrt(lo * hi)
        c = chain_run(args, s0, dt=dt0, m_s=mid)
        out["capture"].append(c)
        log_chain(f"capture {mid:.3g}", c)
        ok = c.get("measures", {}).get("propagated_to_end")
        if c["refusal"]:
            break
        lo, hi = (lo, mid) if ok else (mid, hi)
        out["capture_bracket_m_s"] = [lo, hi]
        write_json(path, out)
    c = chain_run(args, s0, dt=dt0, m_s=0.5 * out.get("capture_bracket_m_s", [lo, hi])[0])
    c["label"] = "subthreshold control: half the largest non-capturing stimulus"
    out["controls"].append(c)
    log_chain("control subthreshold", c)
    write_json(path, out)
    for dt in args.refine_dt:
        c = chain_run(args, s0, dt=dt)
        out["refinement"].append(c)
        log_chain("refine", c)
        write_json(path, out)
    big = ladder_dt(
        admissible(static_bounds(definition(args.n, dt=1e-5, end_time=0.01, kv_m_s=args.kv, s=s0))),
        1e-3,
    )
    c = chain_run(args, s0, dt=big)
    c["label"] = "largest step the static bounds admit"
    out["refinement"].append(c)
    log_chain("largest static step", c)
    write_json(path, out)
    for n in (args.n_long,):
        c = chain_run(args, s0, n=n, dt=dt0, end=args.chain_end)
        if c.get("measures"):
            t_act = c["measures"]["activation_s"]
            spans = {}
            for lo_, hi_ in ((5, 15), (15, 25), (25, 35), (n // 3, (2 * n) // 3)):
                if all(t_act[i] is not None for i in range(lo_, hi_ + 1)):
                    slope = np.polyfit(
                        np.arange(lo_, hi_ + 1), [t_act[i] for i in range(lo_, hi_ + 1)], 1
                    )[0]
                    spans[f"{lo_}-{hi_}"] = 1.0 / slope
                else:
                    spans[f"{lo_}-{hi_}"] = None
            c["cv_spans_cells_per_s"] = spans
        out["length"].append(c)
        log_chain(f"length {n}", c)
        write_json(path, out)
    # Recovery: S1-S2 at the stimulated end.
    on, width = int(round(2e-3 / dt0)), int(round(1e-3 / dt0))
    for delta_ms in args.s1s2_ms:
        s2 = on + int(round(delta_ms * 1e-3 / dt0))
        c = chain_run(
            args,
            s0,
            dt=dt0,
            pulses=[(on, on + width), (s2, s2 + width)],
            end=s2 * dt0 + args.chain_end,
        )
        c["delta_ms"] = delta_ms
        out["recovery"].append(c)
        log_chain(f"S1-S2 {delta_ms} ms", c)
        write_json(path, out)
    second = [
        c["delta_ms"]
        for c in out["recovery"]
        if c.get("measures", {}).get("activations_per_cell", [0])[-1] >= 2
    ]
    none = [
        c["delta_ms"]
        for c in out["recovery"]
        if c.get("measures", {}).get("activations_per_cell", [2])[-1] < 2
    ]
    out["recovery_bracket_ms"] = [
        max([d for d in none if d < min(second, default=1e9)], default=None),
        min(second, default=None),
    ]
    # Block: bisection on s between the sweep's largest blocked and smallest propagating s.
    sweep = [
        (c["s"], c.get("measures", {}).get("propagated_to_end"))
        for c in out["sweep"]
        if not c["refusal"]
    ]
    blocked = [s for s, ok in sweep if ok is False]
    passing = [s for s, ok in sweep if ok]
    if blocked and passing and max(blocked) < min(passing):
        lo, hi = max(blocked), min(passing)
        for _ in range(args.bisections):
            mid = math.sqrt(lo * hi)
            c = chain_run(args, mid, dt=dt_for(mid, args.dt_cap))
            out["block"].append(c)
            log_chain("block", c)
            ok = c.get("measures", {}).get("propagated_to_end")
            if c["refusal"]:
                break
            lo, hi = (lo, mid) if ok else (mid, hi)
            out["block_bracket_s"] = [lo, hi]
            write_json(path, out)
    # Arms at the main coupling: trapezoid junction heat; the declared junction gate.
    for label, kw in (
        ("default junction heat booking (explicit_tableau)", dict(booking=None)),
        ("gated junctions (15 mV, minimum 0.1)", dict(gated=True)),
    ):
        try:
            dt = (
                dt0
                if not kw.get("gated")
                else ladder_dt(
                    admissible(
                        static_bounds(
                            definition(
                                args.n, dt=1e-5, end_time=0.01, kv_m_s=args.kv, s=s0, gated=True
                            )
                        )
                    ),
                    args.dt_cap,
                )
            )
            c = chain_run(args, s0, dt=dt, **kw)
        except ConfigError as error:
            c = dict(
                s=s0,
                control="excitable",
                refusal=dict(kind="ConfigError", message=str(error)),
                mechanisms={"dt_s": None},
            )
        c["label"] = label
        out["arms"].append(c)
        log_chain(label, c)
        write_json(path, out)
    out["peak_rss_mb"] = peak_rss_mb()
    write_json(path, out)


def segment_case(args, label, r_na, r_gj, dt):
    """One probe-2 run: the chain with its segment held at (r_na, r_gj) (PLAN amendment 3)."""
    n, (lo, hi) = args.n_segment, args.segment
    on, width = int(round(2e-3 / dt)), int(round(1e-3 / dt))
    stim = dict(
        cells=list(range(args.stim_cells)),
        pulses=[(on, on + width)],
        m_s=args.stim_m_s * stimulus_scale(),
    )
    raw = definition(
        n,
        dt=dt,
        end_time=args.chain_end,
        kv_m_s=args.kv,
        s=args.s_main,
        booking=args.booking,
        stim=stim,
        cell_nav=None if r_na == 1.0 else {i: r_na for i in range(lo, hi + 1)},
        junction_availability=None if r_gj == 1.0 else {k: r_gj for k in range(lo - 1, hi + 1)},
    )
    stim_end = (on + width) * dt

    def stop(o):  # The far end fired and 15 ms passed, or every cell quiet for 25 ms.
        t = o["times"]
        if not t or t[-1] < stim_end + 0.01:
            return False
        vm = np.asarray(o["vm"])
        far = crossings(t, vm[:, -1], -0.030)
        if far and t[-1] > far[-1] + 0.015:
            return True
        recent = np.asarray(t) > t[-1] - 0.025
        return bool(np.all(vm[recent] < -0.030) and t[-1] > stim_end + 0.03)

    r = execute(raw, stop=stop)
    rec = record(raw, r, label=label, r_na=r_na, r_gj=r_gj, segment=[lo, hi], n=n)
    if len(r["times"]) > 2:
        t, vm = np.asarray(r["times"]), np.asarray(r["vm"])
        act = [
            crossings(t, vm[:, i], -0.030, start=int(np.searchsorted(t, on * dt))) for i in range(n)
        ]
        first = [a[0] if a else None for a in act]

        def cv(a, b):
            if all(first[i] is not None for i in range(a, b + 1)):
                slope = np.polyfit(np.arange(a, b + 1), [first[i] for i in range(a, b + 1)], 1)[0]
                return 1.0 / slope if slope > 0 else None
            return None

        reached = [i for i in range(n) if first[i] is not None]
        vj = np.asarray(r["vj"])
        rec["measures"] = dict(
            activation_s=first,
            last_activated_cell=max(reached) if reached else None,
            reaches_segment=first[lo - 1] is not None,
            exits_segment=first[hi + 1] is not None,
            segment_delay_s=None
            if first[lo - 1] is None or first[hi + 1] is None
            else first[hi + 1] - first[lo - 1],
            upstream_cv_cells_per_s=cv(6, lo - 2),
            segment_cv_cells_per_s=cv(lo, hi),
            downstream_cv_cells_per_s=cv(hi + 2, min(hi + 8, n - 9)),
            peak_V=vm.max(axis=0).tolist(),
            vm_max_V=float(vm.max()),
            segment_vj_abs_max_V=float(np.abs(vj[:, lo - 1 : hi + 1]).max()) if vj.size else 0.0,
            vj_abs_max_V=float(np.abs(vj).max()) if vj.size else 0.0,
        )
    m = rec.get("measures", {})
    log(
        f"segment {label} dt {dt:g}: last {m.get('last_activated_cell')} "
        f"exits {m.get('exits_segment')} "
        f"delay {m.get('segment_delay_s')} vj {m.get('segment_vj_abs_max_V')} "
        f"refusal {rec['refusal'] and rec['refusal']['message'][:90]}"
    )
    return rec


def part_segment(args):
    """Probe 2: a wave meeting a mid-chain segment of reduced NaV1.2 and coupling."""
    set_point(args.nav, args.kir, args.cm)
    out = dict(
        provenance=provenance(),
        plan=PLAN,
        part="segment",
        point=dict(nav_m_s=args.nav, kir_m_s=args.kir, cm_F_m2=args.cm, kv_m_s=args.kv),
        n=args.n_segment,
        segment=list(args.segment),
        s=args.s_main,
        cases=[],
    )
    out["rest"] = relax_rest(args.kv)
    path = Path(args.output) / "segment.json"
    cases = [("control", 1.0, 1.0)]
    cases += [(f"combined {r:g}", r, r) for r in args.combined]
    cases += [(f"sodium-only {r:g}", r, 1.0) for r in args.sodium_only]
    cases += [(f"coupling-only {r:g}", 1.0, r) for r in args.coupling_only]
    for dt in args.segment_dt:
        for label, r_na, r_gj in cases:
            out["cases"].append(dict(dt_s=dt, **segment_case(args, label, r_na, r_gj, dt)))
            write_json(path, out)
    if not args.no_extension and not any(
        c.get("measures", {}).get("reaches_segment")
        and not c.get("measures", {}).get("exits_segment")
        for c in out["cases"]
    ):
        out["extension"] = "no case blocked: the combined series extended to 0.02 and 0.01"
        for dt in args.segment_dt:
            for r in (0.02, 0.01):
                out["cases"].append(
                    dict(dt_s=dt, **segment_case(args, f"combined {r:g}", r, r, dt))
                )
                write_json(path, out)
    # The criteria of amendment 3.
    by = {}
    for c in out["cases"]:
        by.setdefault(c["label"], {})[c["dt_s"]] = c
    control = by["control"][min(args.segment_dt)]
    d0 = control.get("measures", {}).get("segment_delay_s")
    fine, coarse = min(args.segment_dt), max(args.segment_dt)
    rows = []
    for label, steps in by.items():
        a, b = steps.get(coarse, {}), steps.get(fine, {})
        ma, mb = a.get("measures", {}), b.get("measures", {})
        da, db = ma.get("segment_delay_s"), mb.get("segment_delay_s")
        rows.append(
            dict(
                label=label,
                r_na=a.get("r_na"),
                r_gj=a.get("r_gj"),
                outcome_coarse=(ma.get("exits_segment"), ma.get("last_activated_cell")),
                outcome_fine=(mb.get("exits_segment"), mb.get("last_activated_cell")),
                delay_coarse_s=da,
                delay_fine_s=db,
                delay_step_relative=None if da is None or db is None else abs(da - db) / db,
                delay_over_control=None if db is None or d0 is None else db / d0,
                refused=bool(a.get("refusal") or b.get("refusal")),
                segment_vj_abs_max_V=max(
                    ma.get("segment_vj_abs_max_V", 0.0), mb.get("segment_vj_abs_max_V", 0.0)
                ),
                vm_max_V=max(ma.get("vm_max_V", -1.0), mb.get("vm_max_V", -1.0)),
            )
        )
    combined = sorted(
        [r for r in rows if r["label"].startswith("combined")], key=lambda r: -r["r_na"]
    )
    exits = [r["delay_fine_s"] for r in combined if r["outcome_fine"][0]]
    out["criteria"] = dict(
        rows=rows,
        S1_slowing=any(r["outcome_fine"][0] and (r["delay_over_control"] or 0) > 1.10 for r in rows)
        and all(b >= a - 1e-12 for a, b in zip(exits, exits[1:], strict=False)),
        S2_block=any(
            by[r["label"]][fine].get("measures", {}).get("reaches_segment")
            and not r["outcome_fine"][0]
            for r in rows
        ),
        S3_refinement=all(
            r["outcome_coarse"] == r["outcome_fine"]
            and (r["delay_step_relative"] is None or r["delay_step_relative"] < 0.02)
            for r in rows
        ),
        S4_accounting=not any(r["refused"] for r in rows),
        segment_vj_abs_max_V=max(r["segment_vj_abs_max_V"] for r in rows),
        vm_max_V=max(r["vm_max_V"] for r in rows),
    )
    log(f"segment criteria: { {k: v for k, v in out['criteria'].items() if k != 'rows'} }")
    out["peak_rss_mb"] = peak_rss_mb()
    write_json(path, out)


def part_domain(args):
    """Probe 2: the 0.01 F/m^2 point against the +60 mV domain (PLAN amendment 3)."""
    import argparse as _argparse

    out = dict(provenance=provenance(), plan=PLAN, part="domain", candidates=[])
    path = Path(args.output) / "domain.json"
    for name, nav, kir, kv in (("A", 1e-6, 1e-8, 3e-7), ("B", 2.5e-7, 1e-8, 1e-7)):
        set_point(nav, kir, 0.01)
        row = dict(name=name, point=dict(nav_m_s=nav, kir_m_s=kir, cm_F_m2=0.01, kv_m_s=kv))
        row["rest"] = relax_rest(kv)
        rest_v = POINT["rest"][0]
        singles = {}
        for label, target in (("kick to -20 mV", -0.020), ("kick to 0 mV", 0.0)):
            rec, _ = single_run(kv, dt=5e-6, kick=1e3 * (target - rest_v))
            singles[label] = rec
        on, width = int(round(2e-3 / 5e-6)), int(round(1e-3 / 5e-6))
        rec, _ = single_run(
            kv,
            dt=5e-6,
            stim=dict(cells=[0], pulses=[(on, on + width)], m_s=1e-6 * stimulus_scale()),
        )
        singles["stimulus 1 ms"] = rec
        row["single"] = singles
        a = _argparse.Namespace(**vars(args))
        a.kv, a.n = kv, args.n_segment
        row["chain"] = chain_run(a, args.s_main, n=args.n_segment, dt=5e-6)
        f = singles["kick to -20 mV"].get("features", {})
        cm_ = row["chain"].get("measures", {})
        refusals = [k for k, v in singles.items() if v.get("refusal")] + (
            ["chain"] if row["chain"].get("refusal") else []
        )
        row["criteria"] = dict(
            fires=bool(f.get("peak_V", -1) > 0 and f.get("max_dVdt_V_s", 0) > 10),
            repolarises=bool(f.get("repolarised")),
            propagates=bool(cm_.get("c1_regeneration")),
            inside_domain=not refusals,
            refusals=refusals,
            vm_max_V=max(
                [v.get("features", {}).get("peak_V", -1.0) for v in singles.values()]
                + [row["chain"].get("vm_max_V", -1.0)]
            ),
        )
        row["passes"] = all(
            row["criteria"][k] for k in ("fires", "repolarises", "propagates", "inside_domain")
        )
        out["candidates"].append(row)
        log(f"domain {name}: {row['criteria']} passes {row['passes']}")
        write_json(path, out)
        if row["passes"]:
            break
    passing = [c["name"] for c in out["candidates"] if c["passes"]]
    out["ruling_input"] = (
        f"0.01 F/m^2 at candidate {passing[0]}"
        if passing
        else "0.05 F/m^2 (no 0.01 candidate passed)"
    )
    out["peak_rss_mb"] = peak_rss_mb()
    write_json(path, out)


def part_device(args):
    """The model's device row checks (vector windows) on the main accepted cases."""
    from cells.execution.batch import BatchSpec, WorldSpec
    from cells.execution.vector_windows import run_vector_windowed

    out = dict(provenance=provenance(), plan=PLAN, part="device", batches=[])
    path = Path(args.output) / "device.json"
    set_point(args.nav, args.kir, args.cm)
    out["rest"] = relax_rest(args.kv) if not args.h_rest else dict(rest=list(H[:4]), source="H")
    supra = 1e3 * (args.kick_to - POINT["rest"][0])
    out["kick_mV"] = supra
    batches = [
        (
            "single cell, kick, dt 10 and 25 us",
            [
                definition(1, dt=dt, end_time=0.08, kv_m_s=args.kv, kicks={0: supra})
                for dt in (1e-5, 2.5e-5)
            ],
        )
    ]
    dt = ladder_dt(
        admissible(
            static_bounds(definition(args.n, dt=1e-5, end_time=0.01, kv_m_s=args.kv, s=args.s_main))
        ),
        args.dt_cap,
    )
    on, width = int(round(2e-3 / dt)), int(round(1e-3 / dt))
    stim = dict(
        cells=list(range(args.stim_cells)),
        pulses=[(on, on + width)],
        m_s=args.stim_m_s * stimulus_scale(),
    )
    batches.append(
        (
            f"chain n {args.n} s {args.s_main:g} dt {dt:g}: excitable and sodium-disabled",
            [
                definition(
                    args.n,
                    dt=dt,
                    end_time=args.device_end,
                    kv_m_s=args.kv,
                    s=args.s_main,
                    stim=stim,
                    control=c,
                    booking=args.booking,
                )
                for c in ("excitable", "sodium_disabled")
            ],
        )
    )
    for label, raws in batches:
        row = dict(label=label, worlds=len(raws), mechanisms=[mechanisms(r) for r in raws])
        started = time.perf_counter()
        try:
            spec = BatchSpec(
                tuple(WorldSpec(i + 1, parse_spec(r)) for i, r in enumerate(raws)),
                len(raws),
                2**53 - 1,
                2**53 - 1,
            )
            result = run_vector_windowed(spec, WindowPolicy(args.device_window, "checkpoints"))
            row.update(
                status="passed",
                timings=result.timings,
                resources=dict(result.resources),
                diagnostics={str(k): w.diagnostics for k, w in result.worlds.items()},
                executed_steps={
                    str(k): w.resources["executed_steps"] for k, w in result.worlds.items()
                },
            )
        except Exception as error:  # Preserved as evidence.
            row.update(
                status="failed",
                error=repr(error),
                checks=getattr(error, "checks", None),
                world=getattr(error, "world_id", None),
                interval=getattr(error, "time_interval", None),
                traceback=traceback.format_exc(),
            )
        row["wall_seconds"] = time.perf_counter() - started
        out["batches"].append(row)
        log(f"device {label}: {row['status']} {row.get('error', '')[:120]}")
        write_json(path, out)
    out["peak_rss_mb"] = peak_rss_mb()
    write_json(path, out)


SCAN_ORDER = ("cm_F_m2", "nav_m_s", "kir_m_s", "kv_m_s")
SCAN_GRID = dict(
    cm_F_m2=(0.05, 0.01),
    nav_m_s=(2.5e-7, 1e-6),
    kir_m_s=(1e-8, 4e-8),
    kv_m_s=(1e-7, 3e-7, 1e-6),
)


def part_scan(args):
    """Post-hoc amendment (PLAN.md, 14 November): the admitted laws over their densities.

    Every grid point, in the fixed order (least departure from the heredity cell first):
    its rest from a 2 s relaxation; a kick to -20 mV; the fixed AP definition (overshoot,
    repolarised within 5 mV of that rest within 60 ms, peak <= +55 mV, no refusal) at
    ARS(2,2,2) 10 us. The selection is the first passing point; a point also needs a rest
    below -60 mV. Every point runs, so the scan maps where the laws make an action potential.
    """
    import itertools

    out = dict(
        provenance=provenance(),
        plan=PLAN,
        part="scan",
        order=SCAN_ORDER,
        grid=SCAN_GRID,
        kick_to_V=args.kick_to_scan,
        points=[],
    )
    path = Path(args.output) / "scan.json"
    for values in itertools.product(*(SCAN_GRID[k] for k in SCAN_ORDER)):
        point = dict(zip(SCAN_ORDER, values, strict=True))
        set_point(point["nav_m_s"], point["kir_m_s"], point["cm_F_m2"])
        rest = relax_rest(point["kv_m_s"])
        row = dict(point=point, rest=rest)
        if rest["refusal"] is None and rest.get("rest_V", 0.0) < -0.060:
            kick = 1e3 * (args.kick_to_scan - POINT["rest"][0])
            rec, _ = single_run(point["kv_m_s"], kick=kick)
            f = rec.get("features", {})
            row.update(
                kick_mV=kick,
                record=rec,
                passes=bool(
                    not rec["refusal"]
                    and f.get("class") == "action potential, repolarised"
                    and f.get("peak_V", 1.0) <= 0.055
                ),
            )
        else:
            row["passes"] = False
            row["reason"] = "no rest below -60 mV" if rest["refusal"] is None else "rest refused"
        out["points"].append(row)
        f = row.get("record", {}).get("features", {})
        log(
            f"scan {point}: rest {rest.get('rest_V')} {f.get('class')} peak {f.get('peak_V')} "
            f"dV/dt {f.get('max_dVdt_V_s')} apd90 {f.get('apd90_s')} passes {row['passes']}"
        )
        write_json(path, out)
    passing = [r for r in out["points"] if r["passes"]]
    out["selected"] = passing[0]["point"] if passing else None
    out["passing_points"] = [r["point"] for r in passing]
    log(f"scan selected {out['selected']}")
    out["peak_rss_mb"] = peak_rss_mb()
    write_json(path, out)


def relative(a, b):
    return None if a is None or b is None or b == 0 else abs(a - b) / abs(b)


def part_verdict(args):
    """C1-C5 evaluated mechanically from the saved parts, by PLAN's definitions."""
    root = Path(args.output)
    single = json.loads((root / "single.json").read_text())
    chain = (
        json.loads((root / "chain.json").read_text()) if (root / "chain.json").exists() else None
    )
    device = (
        json.loads((root / "device.json").read_text()) if (root / "device.json").exists() else None
    )
    out = dict(provenance=provenance(), plan=PLAN, part="verdict")
    out["single"] = dict(
        regenerates=single.get("regenerates"),
        recovers=single.get("recovers"),
        selected_kv_m_s=single.get("selected_kv_m_s"),
        kick_threshold_mV=single.get("kick_threshold", {}).get("threshold_mV"),
        stimulus_threshold_m_s=single.get("stimulus_threshold", {}).get("threshold_m_s"),
        recovery_bracket_ms=single.get("recovery_bracket_ms"),
    )
    ladder = {(c["solver"], c["dt_s"]): c for c in single.get("dt_refinement", [])}
    accepted = {k: v for k, v in ladder.items() if not v["refusal"] and v.get("features")}
    out["single"]["accepted_steps"] = sorted([f"{k[0]} {k[1]:g}" for k in accepted])
    out["single"]["refused_steps"] = {
        f"{k[0]} {k[1]:g}": v["refusal"]["message"] for k, v in ladder.items() if v["refusal"]
    }
    ref = accepted.get(("rk4", 1.25e-6))
    if ref:
        out["single"]["against_rk4_1p25us"] = {
            f"{k[0]} {k[1]:g}": {
                q: relative(v["features"].get(q), ref["features"].get(q))
                for q in ("peak_V", "max_dVdt_V_s", "apd50_s", "apd90_s")
            }
            for k, v in accepted.items()
        }
    if chain:
        main = next((c for c in chain["sweep"] if c["s"] == args.s_main), None)
        m = (main or {}).get("measures", {})
        out["C1"] = dict(
            met=bool(m.get("c1_regeneration")), main_case_refusal=(main or {}).get("refusal")
        )
        controls = {c.get("label", c["control"]): c.get("measures", {}) for c in chain["controls"]}
        out["C2"] = dict(
            met=bool(controls)
            and all(
                v.get("c2_no_spread") and v.get("c2_peaks_decrease") for v in controls.values()
            ),
            controls={
                k: dict(
                    no_spread=v.get("c2_no_spread"),
                    decreasing=v.get("c2_peaks_decrease"),
                    last_activated=v.get("last_activated_cell"),
                )
                for k, v in controls.items()
            },
        )
        out["C3"] = dict(
            cv_cells_per_s={
                str(c["s"]): c.get("measures", {}).get("cv_cells_per_s") for c in chain["sweep"]
            },
            capture_bracket_m_s=chain.get("capture_bracket_m_s"),
            recovery_bracket_ms=chain.get("recovery_bracket_ms"),
            block_bracket_s=chain.get("block_bracket_s"),
        )
        out["C3"]["met"] = (
            all(
                out["C3"][k] is not None
                for k in ("capture_bracket_m_s", "recovery_bracket_ms", "block_bracket_s")
            )
            and m.get("cv_cells_per_s") is not None
        )
        refine = {c["mechanisms"]["dt_s"]: c for c in [main, *chain["refinement"]] if c}
        cvs = {
            dt: c.get("measures", {}).get("cv_cells_per_s")
            for dt, c in refine.items()
            if not c["refusal"]
        }
        finest = sorted(cvs)[:2]
        dcv = relative(cvs[finest[0]], cvs[finest[1]]) if len(finest) == 2 else None
        long = chain["length"][0] if chain["length"] else {}
        spans = long.get("cv_spans_cells_per_s", {})
        values = [v for v in spans.values() if v is not None]
        spread = (max(values) - min(values)) / min(values) if values else None
        short_cv = m.get("cv_cells_per_s")
        long_cv = spans.get(f"{40 // 3}-{(2 * 40) // 3}")
        # Activation times at the two finest steps: within 5% of the mean delay per cell,
        # over the cells beyond the stimulated set.
        act_shift = None
        if len(finest) == 2:
            a0 = refine[finest[0]].get("measures", {}).get("activation_s", [])
            a1 = refine[finest[1]].get("measures", {}).get("activation_s", [])
            beyond = range(args.stim_cells, min(len(a0), len(a1)))
            pairs = [(a0[i], a1[i]) for i in beyond if a0[i] is not None and a1[i] is not None]
            delays = [d for d in refine[finest[0]]["measures"]["delay_per_cell_s"] if d]
            if pairs and delays:
                act_shift = max(abs(x - y) for x, y in pairs) / float(np.mean(delays))
        out["C4"] = dict(
            cv_by_dt=cvs,
            cv_two_finest_relative=dcv,
            activation_shift_over_delay=act_shift,
            spans=spans,
            spans_spread=spread,
            short_vs_long=relative(short_cv, long_cv),
        )
        out["C4"]["met"] = (
            all(v is not None and v < 0.02 for v in (dcv, spread, out["C4"]["short_vs_long"]))
            and act_shift is not None
            and act_shift < 0.05
        )
        # C5: every case's refusal (with its attribution), device checks, mechanisms, cost.
        kinds = (
            "sweep",
            "controls",
            "refinement",
            "length",
            "capture",
            "recovery",
            "block",
            "arms",
        )
        cases = [(g, c) for g in kinds for c in chain.get(g, [])]
        stopped = [
            dict(
                group=g,
                s=c.get("s"),
                control=c.get("control"),
                label=c.get("label"),
                dt_s=c.get("mechanisms", {}).get("dt_s"),
                message=c["refusal"]["message"],
                attribution=c.get("attribution", {}).get("at_last_accepted"),
            )
            for g, c in cases
            if c.get("refusal")
        ]
        main_kinds = ("controls", "refinement", "length")
        main_stopped = [r for r in stopped if r["group"] in main_kinds] + [
            r for r in stopped if r["group"] == "sweep" and r["s"] == args.s_main
        ]
        out["C5"] = dict(
            cases=len(cases),
            refused=stopped,
            main_cases_refused=len(main_stopped),
            mechanisms=(main or {}).get("mechanisms"),
            execute_ms_per_step=(main or {}).get("execute_ms_per_step"),
            host_analysis_ms_per_step=(main or {}).get("host_analysis_ms_per_step"),
            max_energy_balance_relative=max(
                (
                    c.get("diagnostics", {}).get("max_energy_balance_relative", 0.0)
                    for _, c in cases
                ),
                default=None,
            ),
        )
    if device:
        out["device"] = {b["label"]: b["status"] for b in device["batches"]}
        if "C5" in out:
            out["C5"]["device_batches"] = out["device"]
            out["C5"]["met"] = out["C5"]["main_cases_refused"] == 0 and all(
                v == "passed" for v in out["device"].values()
            )
    if args.scan_json:
        scan = json.loads(Path(args.scan_json).read_text())
        out["scan"] = dict(
            selected=scan.get("selected"),
            passing_points=scan.get("passing_points"),
            points=[
                dict(
                    point=r["point"],
                    rest_V=r["rest"].get("rest_V"),
                    passes=r["passes"],
                    features=r.get("record", {}).get("features"),
                    refusal=r.get("record", {}).get("refusal"),
                    reason=r.get("reason"),
                )
                for r in scan["points"]
            ],
        )
    write_json(root / "verdict.json", out)
    log(
        json.dumps(
            jsonable({k: v for k, v in out.items() if k not in ("plan", "provenance")}), indent=1
        )[:4000]
    )


def span_cv(activation, lo, hi):
    """The inverse least-squares slope of activation time against index over cells lo..hi."""
    if hi <= lo or any(activation[i] is None for i in range(lo, hi + 1)):
        return None
    slope = np.polyfit(np.arange(lo, hi + 1), [activation[i] for i in range(lo, hi + 1)], 1)[0]
    return float(1.0 / slope) if slope > 0 else None


def part_lengths(args):
    """C4's measurement fix (design note section 6; M1 PLAN amendment 2): CV against chain
    length, stimulus strength and span, with the first ten cells beyond the stimulus and the
    last ten excluded."""
    set_point(args.nav, args.kir, args.cm)
    out = dict(
        provenance=provenance(),
        plan=PLAN,
        part="lengths",
        point=dict(nav_m_s=args.nav, kir_m_s=args.kir, cm_F_m2=args.cm, kv_m_s=args.kv),
        cases=[],
    )
    out["rest"] = relax_rest(args.kv)
    path = Path(args.output) / "lengths.json"
    lo = args.stim_cells + 10
    longest = max(args.length_n)
    for s in args.length_s:
        bounds = static_bounds(definition(longest, dt=1e-5, end_time=0.01, kv_m_s=args.kv, s=s))
        dt = ladder_dt(admissible(bounds), args.dt_cap)
        for n in args.length_n:
            hi = n - 11
            for k in args.strengths:
                c = chain_run(
                    args, s, n=n, dt=dt, m_s=k * args.stim_m_s * stimulus_scale(), span=(lo, hi)
                )
                c.update(strength=k, span=[lo, hi], dt_s=dt)
                act = (c.get("measures") or {}).get("activation_s")
                if act:
                    cuts = np.linspace(lo, hi, 4).round().astype(int).tolist()
                    c["subspan_cv_cells_per_s"] = [
                        span_cv(act, a, b) for a, b in zip(cuts[:-1], cuts[1:], strict=False)
                    ]
                    c["shared_span_cv_cells_per_s"] = span_cv(act, lo, min(args.length_n) - 11)
                out["cases"].append(c)
                log_chain(f"length s {s:g} n {n} strength {k:g} dt {dt:g}", c)
                write_json(path, out)
    rows = {}
    for c in out["cases"]:
        rows[(c["s"], c["n"], c["strength"])] = c
    criteria = {}
    short, long_ = min(args.length_n), max(args.length_n)
    base, strong = min(args.strengths), max(args.strengths)
    for s in args.length_s:
        a, b = rows.get((s, short, base), {}), rows.get((s, long_, base), {})
        c2 = rows.get((s, long_, strong), {})
        cv_short, cv_long = a.get("shared_span_cv_cells_per_s"), b.get("shared_span_cv_cells_per_s")
        sub_cvs = [v for v in b.get("subspan_cv_cells_per_s") or [] if v]
        cv1 = (b.get("measures") or {}).get("cv_cells_per_s")
        cv2 = (c2.get("measures") or {}).get("cv_cells_per_s")
        criteria[str(s)] = dict(
            L1_end_effect=relative(cv_short, cv_long),
            L2_steadiness=None
            if len(sub_cvs) < 3
            else (max(sub_cvs) - min(sub_cvs)) / min(sub_cvs),
            L3_strength=relative(cv2, cv1),
            refused=[
                c["label"] if c.get("label") else c.get("n") for c in (a, b, c2) if c.get("refusal")
            ],
        )
        row = criteria[str(s)]
        row["met"] = not row["refused"] and all(
            row[k] is not None and row[k] < 0.02
            for k in ("L1_end_effect", "L2_steadiness", "L3_strength")
        )
    out["criteria"] = criteria
    out["peak_rss_mb"] = peak_rss_mb()
    write_json(path, out)
    log(f"lengths criteria: {criteria}")


def kick_chain_run(args, s, *, n, dt, kick_mV, kicked, span):
    """A chain launched by kicks on its first cells at t = 0: no stimulus onset in the run."""
    raw = definition(
        n,
        dt=dt,
        end_time=args.chain_end,
        kv_m_s=args.kv,
        s=s,
        booking=args.booking,
        kicks={i: kick_mV for i in range(kicked)},
    )

    def stop(o):  # The far end fired and 15 ms passed, or 25 ms all quiet after 30 ms.
        t = o["times"]
        if not t or t[-1] < 0.01:
            return False
        vm = np.asarray(o["vm"])
        far = crossings(t, vm[:, -1], -0.030)
        if far and t[-1] > far[0] + 0.015:
            return True
        recent = np.asarray(t) > t[-1] - 0.025
        return bool(np.all(vm[recent] < -0.030) and t[-1] > 0.03)

    r = execute(raw, stop=stop)
    rec = record(raw, r, s=s, n=n, dt_s=dt, kick_mV=kick_mV, kicked=kicked, control="excitable")
    try:
        rec["static_bounds"] = static_bounds(raw)
    except ConfigError as error:
        rec["static_bounds"] = dict(refusal=str(error))
    if len(r["times"]) > 2:
        t, vm = np.asarray(r["times"]), np.asarray(r["vm"])
        rec["measures"] = chain_measures(
            t, vm, stim_cells=list(range(kicked)), stim_end=0.0, span=span
        )
        rec["vm_max_V"] = float(vm.max())
    return rec


def part_steps(args):
    """C5's measurement fix (design note section 6; M1 PLAN amendment 2): the wave's own
    largest admissible step. The wave is launched by kicks at t = 0, so no stimulus onset
    enters the run; the steps are the largest the static bounds admit, below a cap."""
    set_point(args.nav, args.kir, args.cm)
    out = dict(
        provenance=provenance(),
        plan=PLAN,
        part="steps",
        point=dict(nav_m_s=args.nav, kir_m_s=args.kir, cm_F_m2=args.cm, kv_m_s=args.kv),
        cases=[],
    )
    out["rest"] = relax_rest(args.kv)
    path = Path(args.output) / "steps.json"
    n = args.n_long
    kick = 1e3 * (args.kick_to_V - POINT["rest"][0])
    span = (args.stim_cells + 10, n - 11)
    criteria = {}
    for s in args.step_s:
        limit = admissible(
            static_bounds(definition(n, dt=1e-5, end_time=0.01, kv_m_s=args.kv, s=s))
        )
        dts = [
            dt for dt in DT_LADDER if dt <= args.step_cap * (1 + 1e-12) and dt < limit * (1 - 1e-12)
        ][: args.step_count]
        runs = []
        for dt in dts:
            c = kick_chain_run(args, s, n=n, dt=dt, kick_mV=kick, kicked=args.stim_cells, span=span)
            runs.append(c)
            out["cases"].append(c)
            log_chain(f"steps s {s:g} dt {dt:g}", c)
            write_json(path, out)
        finest = runs[-1] if runs else {}
        f_cv = (finest.get("measures") or {}).get("cv_cells_per_s")
        f_act = (finest.get("measures") or {}).get("activation_s")
        table = []
        for c in runs:
            m = c.get("measures") or {}
            shift = None
            if f_act and m.get("activation_s"):
                pairs = [
                    (x, y)
                    for x, y in zip(m["activation_s"], f_act, strict=False)
                    if x is not None and y is not None
                ]
                shift = max(abs(x - y) for x, y in pairs) if pairs else None
            table.append(
                dict(
                    dt_s=c["dt_s"],
                    refused=bool(c.get("refusal")),
                    attribution=(c.get("attribution") or {}).get("at_last_accepted"),
                    cv_cells_per_s=m.get("cv_cells_per_s"),
                    cv_over_finest=relative(m.get("cv_cells_per_s"), f_cv),
                    activation_shift_s=shift,
                    propagated=m.get("propagated_to_end"),
                    energy=(c.get("diagnostics") or {}).get("max_energy_balance_relative"),
                )
            )
        good = [
            r["dt_s"]
            for r in table
            if not r["refused"]
            and r["propagated"]
            and r["cv_over_finest"] is not None
            and r["cv_over_finest"] < 0.01
        ]
        criteria[str(s)] = dict(
            static_limit_s=limit,
            table=table,
            largest_good_dt_s=max(good) if good else None,
        )
    out["criteria"] = criteria
    out["peak_rss_mb"] = peak_rss_mb()
    write_json(path, out)
    log(f"steps criteria: { {k: v['largest_good_dt_s'] for k, v in criteria.items()} }")


QUALCELL_TOLERANCES = dict(  # excitable_qualification_v1.json, CELL_rest and CELL_AP (PROPOSED)
    rest_V=1e-5,
    kick_threshold_widen_V=5e-5,
    peak_V=1e-4,
    time_relative=0.01,
    time_absolute_s=1e-5,
    dvdt_relative=0.02,
    v80_V=1e-4,
)


def ap_row(t, v, *, reference_s, rest_V):
    """The protocol's action-potential measures (conduction_observables; times from t = 0)."""
    from validation.tissue import conduction_observables as co

    t, v = np.asarray(t), np.asarray(v)
    ap = co.action_potential(t, v, reference_s=reference_s, rest_V=rest_V)
    dv = np.diff(v) / np.diff(t)
    k = int(np.argmax(v))
    back = co.falling(t, v, rest_V + 0.005, k)
    return dict(
        peak_V=float(v.max()),
        time_to_peak_s=float(t[k]),
        max_dVdt_V_per_s=float(dv.max()),
        time_of_max_dVdt_s=float(0.5 * (t[int(np.argmax(dv))] + t[int(np.argmax(dv)) + 1])),
        APD50_s=ap["apd50_s"] if ap and ap["peak_V"] > 0 else None,
        APD90_s=ap["apd90_s"] if ap and ap["peak_V"] > 0 else None,
        apd_reference_s=reference_s,
        return_within_5mV_s=back,
        V_at_80ms=float(np.interp(0.08, t, v)) if t[-1] >= 0.08 else None,
        overshoot=bool(v.max() > 0.0),
    )


def compare_ap(engine, ref, tol):
    """Engine against reference for the shared measures (development; not a verdict).

    A measure absent from the reference is not compared (within None). APD and the return
    within 5 mV are compared only when both runs overshoot: a non-firing run's APD is
    undefined (the references' usage note).
    """
    out = {}
    fired = bool(engine.get("overshoot")) and bool(ref.get("overshoot", ref.get("peak_V", -1) > 0))
    for key, kind in (
        ("peak_V", "V"),
        ("V_at_80ms", "V80"),
        ("max_dVdt_V_per_s", "dvdt"),
        ("time_to_peak_s", "t"),
        ("APD50_s", "t"),
        ("APD90_s", "t"),
        ("return_within_5mV_s", "t"),
    ):
        a, b = engine.get(key), ref.get(key)
        if key in ("APD50_s", "APD90_s", "return_within_5mV_s") and not fired:
            out[key] = dict(engine=a, reference=b, within=None, note="not firing: undefined")
            continue
        if b is None:
            out[key] = dict(engine=a, reference=None, within=None, note="not in the reference")
            continue
        if a is None:
            out[key] = dict(engine=None, reference=b, within=False)
            continue
        d = abs(a - b)
        if kind == "V":
            ok = d <= tol["peak_V"]
        elif kind == "V80":
            ok = d <= tol["v80_V"]
        elif kind == "dvdt":
            ok = d <= tol["dvdt_relative"] * abs(b)
        else:
            ok = d <= max(tol["time_relative"] * abs(b), tol["time_absolute_s"])
        out[key] = dict(engine=a, reference=b, difference=d, within=bool(ok))
    return out


def part_qualcell(args):
    """The PROPOSED protocol's one-cell criteria at the point given (A): development values and
    their comparison with the references' saved results (excitable_qualification_v1.json;
    M1 PLAN amendment 3). Kicked runs last 80 ms with APD from the largest dV/dt; the
    stimulus run's APD is from the stimulus end (appendix section 8.3)."""
    set_point(args.nav, args.kir, args.cm)
    tol = QUALCELL_TOLERANCES
    ref_all = json.loads(Path(args.reference_results).read_text())["cm001"][args.reference_point]
    checks = json.loads(Path(args.reference_checks).read_text()) if args.reference_checks else {}
    out = dict(
        provenance=provenance(),
        plan=PLAN,
        part="qualcell",
        point=dict(nav_m_s=args.nav, kir_m_s=args.kir, cm_F_m2=args.cm, kv_m_s=args.kv),
        dt_s=args.cell_dt,
        tolerances=tol,
        references=dict(results=args.reference_results, checks=args.reference_checks),
    )
    path = Path(args.output) / "qualcell.json"
    out["rest"] = relax_rest(args.kv)
    rest_V = POINT["rest"][0]
    out["CELL_rest"] = dict(
        engine=rest_V,
        reference=ref_all["rest_V"],
        difference=abs(rest_V - ref_all["rest_V"]),
        within=abs(rest_V - ref_all["rest_V"]) <= tol["rest_V"],
    )
    write_json(path, out)

    def kicked_run(kick_mV, control="excitable"):
        rec, r = single_run(args.kv, dt=args.cell_dt, end=0.08, kick=kick_mV, control=control)
        t, v = np.asarray(r["times"]), np.asarray(r["vm"])[:, 0]
        row = None
        if len(t) > 2:
            from validation.tissue import conduction_observables as co

            row = ap_row(t, v, reference_s=co.largest_dvdt_time(t, v), rest_V=rest_V)
        return rec, row

    # The kick threshold by bisection on [0, 60] mV: fires when the peak exceeds 0 mV.
    lo, hi, trail = 0.0, 60.0, []
    while hi - lo > args.kick_tol_mV:
        mid = 0.5 * (lo + hi)
        rec, row = kicked_run(mid)
        fired = bool(row and row["overshoot"]) and rec["refusal"] is None
        trail.append(dict(kick_mV=mid, fired=fired, refusal=rec["refusal"]))
        lo, hi = (lo, mid) if fired else (mid, hi)
        log(f"qualcell kick {mid:.5f} mV fired {fired}")
    ref_k = ref_all["kick_threshold"]
    out["CELL_kick_threshold"] = dict(
        engine_bracket_mV=[lo, hi],
        reference_mV=1e3 * ref_k["threshold"],
        within=bool(lo - 1e3 * tol["kick_threshold_widen_V"] <= 1e3 * ref_k["threshold"]
                    <= hi + 1e3 * tol["kick_threshold_widen_V"]),
        runs=trail,
    )  # fmt: skip
    write_json(path, out)
    threshold = hi
    twice = min(2.0 * threshold, 60.0)
    panel = {}
    for name, kick, control, ref_key in (
        ("twice", twice, "excitable", "twice"),
        ("twice_nav_off", twice, "sodium_disabled", "twice_nav_off"),
        ("twice_all_off", twice, "passive", "twice_all_off"),
        ("kick_to_-20mV", 1e3 * (-0.020 - rest_V), "excitable", None),
        ("kick_to_0mV", 1e3 * (0.0 - rest_V), "excitable", None),
    ):
        rec, row = kicked_run(kick, control)
        ref = ref_all["panel"][ref_key] if ref_key else ref_all[name]
        panel[name] = dict(
            kick_mV=kick,
            control=control,
            refusal=rec["refusal"],
            engine=row,
            comparison=None if row is None else compare_ap(row, ref, tol),
        )
        log(f"qualcell {name}: peak {row and row['peak_V']} refusal {rec['refusal']}")
        write_json(path, out)
    out["CELL_AP_and_controls"] = panel
    # The 1 ms stimulus at 2e-7 m/s (scaled nominal), APD from the stimulus end.
    on, width = int(round(2e-3 / args.cell_dt)), int(round(1e-3 / args.cell_dt))
    stim = dict(cells=[0], pulses=[(on, on + width)], m_s=args.stim_m_s * stimulus_scale())
    rec, r = single_run(args.kv, dt=args.cell_dt, end=0.08, stim=stim)
    t, v = np.asarray(r["times"]), np.asarray(r["vm"])[:, 0]
    row = (
        ap_row(t, v, reference_s=(on + width) * args.cell_dt, rest_V=rest_V) if len(t) > 2 else None
    )
    ref_end = checks.get("stimulus_" + args.reference_point) or {}
    ref_stim = dict(ref_all["stimulus_2e-7"])
    if ref_end:  # The references' APDs from the stimulus end (checks-final: t_upstroke_s, 3 ms).
        ref_stim["APD50_s"] = ref_end["APD50_from_upstroke_s"]
        ref_stim["APD90_s"] = ref_end["APD90_from_upstroke_s"]
        ref_stim["apd_reference_s"] = ref_end["t_upstroke_s"]
        ref_stim.pop("max_dVdt_V_per_s", None)  # the stimulus onset's: not an upstroke measure
    out["CELL_stimulus_run"] = dict(
        refusal=rec["refusal"],
        engine=row,
        reference=ref_stim,
        reference_from_stimulus_end=bool(ref_end),
        comparison=None if row is None else compare_ap(row, ref_stim, tol),
    )
    out["peak_rss_mb"] = peak_rss_mb()
    write_json(path, out)
    within = [out["CELL_rest"]["within"], out["CELL_kick_threshold"]["within"]]
    for entry in list(panel.values()) + [out["CELL_stimulus_run"]]:
        within += [
            c["within"] for c in (entry["comparison"] or {}).values() if c["within"] is not None
        ]
    log(f"qualcell: {sum(within)} of {len(within)} comparisons within the PROPOSED tolerances")


PARTS = dict(
    qualcell=part_qualcell,
    lengths=part_lengths,
    steps=part_steps,
    segment=part_segment,
    domain=part_domain,
    single=part_single,
    scan=part_scan,
    chain=part_chain,
    device=part_device,
    verdict=part_verdict,
)


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("part", choices=sorted(PARTS))
    a.add_argument("--output", required=True)
    a.add_argument("--kv", type=float, default=None, help="Kv1.5 (m/s): chain and device")
    a.add_argument("--nav", type=float, default=fx.HEREDITY_NAV_M_S, help="NaV1.2 (m/s)")
    a.add_argument("--kir", type=float, default=fx.HEREDITY_KIR_M_S, help="Kir2.1 (m/s)")
    a.add_argument("--cm", type=float, default=HEREDITY_CM_F_M2, help="capacitance (F/m^2)")
    a.add_argument(
        "--kick-to",
        type=float,
        default=None,
        help="single: kick to this Vm (V) instead of 50 mV; device: required",
    )
    a.add_argument("--kick-to-scan", type=float, default=-0.020)
    a.add_argument("--h-rest", action="store_true", help="chain/device: start at H as declared")
    a.add_argument("--scan-json", default=None, help="verdict: the scan's record")
    a.add_argument("--n-segment", type=int, default=40)
    a.add_argument("--segment", type=int, nargs=2, default=[16, 23])
    a.add_argument("--segment-dt", type=float, nargs="+", default=[5e-6, 2.5e-6])
    a.add_argument("--combined", type=float, nargs="+", default=[0.5, 0.3, 0.2, 0.1, 0.05])
    a.add_argument("--sodium-only", type=float, nargs="+", default=[0.3, 0.1])
    a.add_argument("--coupling-only", type=float, nargs="+", default=[0.1, 0.03])
    a.add_argument(
        "--no-extension",
        action="store_true",
        help="segment: no extension to 0.02 and 0.01 (M1 keeps s * r_gj >= 20, D170)",
    )
    a.add_argument("--kv-values", type=float, nargs="+", default=[0.0, 1e-8, 3e-8, 1e-7, 3e-7])
    a.add_argument("--bisections", type=int, default=7)
    a.add_argument(
        "--s1s2-ms", type=float, nargs="+", default=[5, 8, 10, 12, 15, 20, 25, 30, 40, 60]
    )
    a.add_argument("--n", type=int, default=20)
    a.add_argument("--n-long", type=int, default=40)
    a.add_argument("--stim-cells", type=int, default=3)
    a.add_argument("--stim-m-s", type=float, default=1e-6)
    a.add_argument("--s-values", type=float, nargs="+", default=[10, 30, 100, 300, 1000, 3000])
    a.add_argument("--s-main", type=float, default=1000.0)
    a.add_argument("--dt-cap", type=float, default=1e-5)
    a.add_argument("--refine-dt", type=float, nargs="+", default=[5e-6, 2.5e-6])
    a.add_argument("--chain-end", type=float, default=0.25)
    a.add_argument("--capture-bracket", type=float, nargs=2, default=[1e-9, 1e-6])
    a.add_argument("--device-end", type=float, default=0.05)
    a.add_argument("--device-window", type=int, default=512)
    a.add_argument("--keep-traces", action="store_true")
    a.add_argument("--length-s", type=float, nargs="+", default=[100.0, 1000.0, 3000.0])
    a.add_argument("--length-n", type=int, nargs="+", default=[40, 80])
    a.add_argument("--strengths", type=float, nargs="+", default=[1.0, 2.0])
    a.add_argument("--step-s", type=float, nargs="+", default=[100.0, 300.0])
    a.add_argument("--step-cap", type=float, default=1e-4)
    a.add_argument("--step-count", type=int, default=4)
    a.add_argument("--kick-to-V", type=float, default=0.0, help="steps: the kicked cells' V(0)")
    a.add_argument("--cell-dt", type=float, default=5e-6, help="qualcell: the step")
    a.add_argument("--kick-tol-mV", type=float, default=0.01, help="qualcell: bisection width")
    a.add_argument("--reference-results", default=None, help="qualcell: references' results.json")
    a.add_argument("--reference-checks", default=None, help="qualcell: their final_checks.json")
    a.add_argument("--reference-point", default="A")
    a.add_argument(
        "--booking",
        default="cells.heat.trapezoid_nonnegative@1",
        help="the chain's junction-heat booking (E07-v1's registered one by default)",
    )
    args = a.parse_args(argv)
    if (
        args.part in ("chain", "device", "segment", "lengths", "steps", "qualcell")
        and args.kv is None
    ):
        a.error("chain and device need --kv explicitly")
    if args.part == "device" and args.kick_to is None:
        a.error("device needs --kick-to explicitly")
    log(f"part {args.part}: cells from {cells.__file__}; driver {__file__}")
    try:
        PARTS[args.part](args)
    except Exception:
        Path(args.output).mkdir(parents=True, exist_ok=True)
        (Path(args.output) / f"{args.part}.FAILURE.txt").write_text(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
