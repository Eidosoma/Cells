"""MG0b: a bistable voltage domain wall on resolved_pump_tissue@3.

Engine model run: resolved_pump_tissue@3 (src/cells/core/surface_pump_v3_spec.py,
src/cells/models/surface_pump_v3.py), unmodified, IMEX ARS(2,2,2), CPU, float64.
Each cell is a heredity cell (validation/tissue/surface_pump_v3_fixtures.py:
heredity_cells) facing its own held bath: BETSE-default membrane coefficients
with the Na leak x0.2, Kir2.1 1e-8 m/s, NaV1.2 2.5e-7 m/s, the Na/K-ATPase,
310 K, fixed volume. This rung adds, through @3's own interface only:
  - NaV1.2 availability held at NAV_AVAILABILITY, so that a cell without the
    control is monostable H and the hysteresis loop can close;
  - a control population per cell (naleak_always_open@1, CONTROL_M_S at
    availability 1): the ramped control u, a depolarising leak like the
    light-gated CheRiff conductance of McNamara et al. 2020;
  - a write population (naleak, WRITE_M_S) in written cells, pulsed on once;
  - gap junctions between neighbours (constant_field@1 for Na, K and M; the
    impermeant P is blocked) with the voltage gate held open
    (junction_voltage_relaxation@1, minimum open fraction 1, initial gate 1,
    threshold 0), so coupling is the linear G of the theory. Self-insulating
    gated junctions are a later arm.
Cut and restore use @3's junction availability schedule: a cut closes the
junctions across a line (isolation); restore reopens them. @3 has no excision
or carrier-replacement contract, so removal and replacement are not tested.

Every experiment is one Protocol, from which both the engine definition and
the reduced-model prediction (validation/morphogenesis/mg0b_theory.py: an
independent numpy/scipy model of the same laws at fixed composition, gates at
steady state) are built. All cells start in the slow H state at the
self-consistent Maxwell control u_M.

Usage:
  python -m validation.morphogenesis.mg0b_domain_wall PART [PART ...] --output DIR
      [--protocol FILE] [--quick]
  PART: theory single width timestep pinning hysteresis cut   (or: all)
"""

import argparse
import copy
import json
import math
import resource
import sys
import time
import traceback
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np

from validation.morphogenesis import mg0b_theory as theory
from validation.tissue import surface_pump_v3_fixtures as fixtures

MODEL_ID = "resolved_pump_tissue@3"
SOLVER = "imex_ars222_face_electromigration@1"
NALEAK_LAW_ID = "naleak_always_open@1"
NAV_AVAILABILITY = 0.4
CONTROL_M_S = 2.0e-10
WRITE_M_S = 4 * 9 * fixtures.HEREDITY_PERMEABILITY["Na"]  # 4x the @3 write test's cue.
JUNCTION_AREA_M2 = 1.0e-11
JUNCTION_SPECIES = ("Na", "K", "M")
# With minimum open fraction 1 the gate's target is 1 at every voltage, so the
# gate stays exactly open and the threshold has no effect; threshold 0 keeps
# @3's conservative gate-rate step bound (1.3 exp(77 threshold) + 20 1/s) small.
GATE_OPEN = dict(
    law="junction_voltage_relaxation@1",
    threshold_voltage_V=0.0,
    minimum_open_fraction=1.0,
    initial_gate=1.0,
)
DT = 1.0e-3
WRITE_PULSE = ((0.0, 0.0), (0.05, 1.0), (0.35, 0.0))


@dataclass(frozen=True)
class Protocol:
    """One experiment: chain, coupling (G/g_H), schedules and observation times."""

    n: int
    coupling_ratio: float
    control: tuple  # ((t, u), ...) for every cell with a control population
    end_time: float
    observe: tuple
    written: tuple = ()
    write: tuple = WRITE_PULSE
    no_control: tuple = ()
    anchored_d: tuple = ()
    junctions: tuple = ()  # ((t, (availability per junction)), ...); default open
    dt: float = DT
    label: str = ""
    extra: dict = field(default_factory=dict)

    def junction_schedule(self):
        return self.junctions or ((0.0, (1.0,) * (self.n - 1)),)

    def observation_times(self):
        """Observation times as exact multiples of dt (accepted grid boundaries)."""
        return [round(o / self.dt) * self.dt for o in self.observe]


def cell_parameters():
    """The heredity cell with this rung's NaV availability and control, for theory."""
    return theory.CellParameters(
        temperature_K=fixtures.HEREDITY_TEMPERATURE_K,
        area_m2=fixtures.HEREDITY_AREA_M2,
        capacitance_F=fixtures.HEREDITY_CAPACITANCE_F,
        volume_m3=fixtures.HEREDITY_VOLUME_PL * 1e-15,
        permeability_m_s={k: fixtures.HEREDITY_PERMEABILITY[k] for k in ("Na", "K", "M")},
        bath_mM={k: fixtures.HEREDITY_BATH_mM[k] for k in ("Na", "K", "M")},
        fixed_anion_mM=fixtures.HEREDITY_FIXED_ANION_mM,
        kir_m_s=fixtures.HEREDITY_KIR_M_S,
        nav_m_s=fixtures.HEREDITY_NAV_M_S,
        nav_availability=NAV_AVAILABILITY,
        control_m_s=CONTROL_M_S,
        # heredity_cells: capacity 1e-7 mol/m^2/s x area (declared in fmol cycles/s).
        pump_capacity_mol_s=1e-7 * fixtures.HEREDITY_AREA_M2,
        pump=dict(
            km_na_mM=12.0,
            km_k_mM=0.2,
            km_atp_mM=0.5,
            atp_mM=1.5,
            adp_mM=0.1,
            pi_mM=0.1,
            delta_g0_J_per_mol=-37000.0,
        ),
    )


def junction_permeability_for(ratio, g_h, composition, p):
    """Junction permeability (m/s, equal for Na, K, M) giving G = ratio * g_H."""
    unit = theory.junction_conductance_S(
        p, composition, JUNCTION_AREA_M2, {s: 1.0 for s in JUNCTION_SPECIES}
    )
    return ratio * g_h / unit


def _schedule(points):
    return [dict(time=float(t), availability=float(a)) for t, a in points]


def chain_definition(
    n,
    *,
    state,
    end_time,
    observation_times,
    control,
    junction_m_s,
    written=(),
    write=WRITE_PULSE,
    no_control=(),
    anchored_d=(),
    junction_schedule=None,
    dt=DT,
):
    """A chain of n heredity cells joined by n - 1 open-gated junctions (@3 JSON).

    state: (Vm, Na, K, M) of every cell. control: [(t, u)] for every cell's
    control population, except cells in no_control. written cells get a write
    population pulsed by `write`; anchored_d cells get one held on throughout.
    junction_schedule: [(t, [availability per junction])], default all open.
    """
    vm = state[0]
    raw = fixtures.heredity_cells(
        [state] * n,
        dt=dt,
        end_time=end_time,
        solver=SOLVER,
        observation_times=observation_times,
        gate_voltages=[vm] * n,
    )
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    for group in e["channel_controls"]:
        if group["channel_id"].startswith("nav_"):
            group["schedule"] = _schedule([(0.0, NAV_AVAILABILITY)])
    for i in range(n):
        populations = []
        if i not in no_control:
            populations.append((f"ctrl_{i}", CONTROL_M_S, control))
        if i in written:
            populations.append((f"write_{i}", WRITE_M_S, write))
        if i in anchored_d:
            populations.append((f"anchor_{i}", WRITE_M_S, ((0.0, 1.0),)))
        for cid, permeability, schedule in populations:
            m["channels"].append(
                fixtures.channel(cid, i, NALEAK_LAW_ID, "Na", permeability, 1.0, [])
            )
            e["channel_controls"].append(dict(channel_id=cid, schedule=_schedule(schedule)))
    m["junctions"] = [
        dict(
            id=f"junction_{i}",
            sender=f"cell_{i}",
            receiver=f"cell_{i + 1}",
            area_m2=JUNCTION_AREA_M2,
            permeability_m_per_s={
                s: (junction_m_s if s in JUNCTION_SPECIES else 0.0)
                for s, _ in fixtures.HEREDITY_SPECIES
            },
            law="constant_field@1",
            gate=dict(GATE_OPEN),
        )
        for i in range(n - 1)
    ]
    schedule = [(0.0, [1.0] * (n - 1))] if junction_schedule is None else junction_schedule
    e["junction_controls"] = [
        dict(
            junction_id=f"junction_{i}",
            schedule=[dict(time=float(t), availability=float(a[i])) for t, a in schedule],
        )
        for i in range(n - 1)
    ]
    x["channel_capacity"] = len(m["channels"])
    x["edge_capacity"] = n - 1
    x["max_steps"] = int(math.ceil(end_time / dt)) + 64
    return raw


def engine_definition(protocol, t):
    p, c = cell_parameters(), t["composition_mM"]
    pj = junction_permeability_for(protocol.coupling_ratio, t["slope_conductance_S"]["H"], c, p)
    return chain_definition(
        protocol.n,
        state=_state(t),
        end_time=protocol.end_time,
        observation_times=protocol.observation_times(),
        control=protocol.control,
        junction_m_s=pj,
        written=protocol.written,
        write=protocol.write,
        no_control=protocol.no_control,
        anchored_d=protocol.anchored_d,
        junction_schedule=[(s, list(a)) for s, a in protocol.junction_schedule()],
        dt=protocol.dt,
    )


def _step_value(schedule, time_s):
    value = schedule[0][1]
    for s, v in schedule:
        if s <= time_s:
            value = v
    return value


def reduced_run(protocol, t):
    """The same protocol in the reduced chain: V at the observation times."""
    p, c = cell_parameters(), t["composition_mM"]
    g_h = t["slope_conductance_S"]["H"]
    n = protocol.n
    ratio = WRITE_M_S / CONTROL_M_S
    has_control = np.array([i not in protocol.no_control for i in range(n)], dtype=float)
    written = np.array([i in protocol.written for i in range(n)], dtype=float)
    anchored = np.array([i in protocol.anchored_d for i in range(n)], dtype=float)
    base = theory.Chain(p, c, n, protocol.coupling_ratio * g_h)

    def at(time_s):
        u = _step_value(protocol.control, time_s) * has_control
        u = u + ratio * (_step_value(protocol.write, time_s) * written + anchored)
        g = (
            protocol.coupling_ratio
            * g_h
            * np.asarray(_step_value(protocol.junction_schedule(), time_s), dtype=float)
        )
        return u, replace(base, coupling_S=g)

    breaks = {
        s
        for schedule in (protocol.control, protocol.write, protocol.junction_schedule())
        for s, _ in schedule
    }
    v0 = np.full(n, t["fast_states_V"]["H"])
    return theory.integrate_chain(
        base, v0, at, protocol.end_time, protocol.observation_times(), breakpoints=sorted(breaks)
    )


def run_windows(raw, *, window_s=2.0):
    """Run in horizon windows (runner branches); keep voltages and cell amounts."""
    from cells.core.runner import branch_checkpoint, run
    from cells.core.specs import parse_spec

    end, dt = raw["experiment"]["end_time"], raw["execution"]["dt"]
    observe = sorted(raw["experiment"]["observation_times"])
    steps = max(1, int(round(window_s / dt)))
    ends, k = [], steps
    while k * dt < end - 0.5 * dt:
        ends.append(k * dt)
        k += steps
    ends.append(end)
    previous, checkpoint, start = None, None, 0.0
    out = dict(times=[], vm=[], amount=[])
    diagnostics, execute, total = [], 0.0, 0.0
    for stop in ends:
        window = copy.deepcopy(raw)
        ex = window["experiment"]
        ex["end_time"] = stop
        ex["observation_times"] = [s for s in observe if s <= stop + 1e-12] or [stop]
        for key in ("membrane_controls", "junction_controls", "pump_controls", "channel_controls"):
            for group in ex[key]:
                group["schedule"] = [c for c in group["schedule"] if c["time"] <= stop]
        spec = parse_spec(window)
        if checkpoint is not None:
            checkpoint = branch_checkpoint(previous, checkpoint, spec)
        value = run(spec, checkpoint)
        obs = value.observations
        for i, s in enumerate(obs.times):
            if (s > start or (start == 0.0 and s == 0.0)) and any(
                abs(s - o) < 1e-12 for o in observe
            ):
                out["times"].append(float(s))
                out["vm"].append(np.asarray(obs.membrane_voltage_V[i]))
                out["amount"].append(np.asarray(obs.amount[i]))
        diagnostics.append({k: float(v) for k, v in value.diagnostics.items() if np.isscalar(v)})
        execute += float(value.timings.get("execute_seconds", 0.0))
        total += float(value.timings.get("total_run_seconds", 0.0))
        previous, checkpoint, start = spec, value.final, stop
    keys = set().union(*diagnostics)
    worst = {k: max(d.get(k, -math.inf) for d in diagnostics) for k in keys}
    result = {k: (v if k == "times" else np.asarray(v)) for k, v in out.items()}
    return result, dict(
        diagnostics_max=worst, windows=len(ends), execute_seconds=execute, run_seconds=total
    )


def run_both(protocol, t, *, window_s=2.0):
    """Engine and reduced model on one protocol; voltages at the observation times."""
    t0 = time.perf_counter()
    engine, info = run_windows(engine_definition(protocol, t), window_s=window_s)
    info["wall_seconds"] = time.perf_counter() - t0
    reduced = reduced_run(protocol, t)
    if len(engine["times"]) != len(protocol.observe):
        raise RuntimeError("Engine observations do not match the protocol")
    amount = engine["amount"]
    drift = np.max(np.abs(amount[-1, :3] / amount[0, :3] - 1)) if len(amount) else None
    info["max_cell_composition_drift_rel"] = None if drift is None else float(drift)
    return engine["vm"], reduced, info


# ---------------------------------------------------------------- theory


COUPLING_RATIOS = (0.25, 0.5, 1.0, 2.0, 4.0, 8.0)  # G / g_H
WIDTH_FIT_RATIOS = (1.0, 2.0, 4.0, 8.0)
WALL_CELLS = 48
SETTLE_S = 6.0


def prepare_theory(quick=False):
    """Self-consistent Maxwell control, its composition and single-cell predictions."""
    p = cell_parameters()
    u_m, c, fast = theory.maxwell_control(p, 0.4, 0.7)
    v_h, v_u, v_d = fast
    g_h = theory.slope_conductance_S(p, c, v_h, u_m)
    g_d = theory.slope_conductance_S(p, c, v_d, u_m)
    bistable = theory.bistable_range(p, c, 0.0, 1.0, n=101 if quick else 401)
    return dict(
        cell=dict(
            nav_availability=NAV_AVAILABILITY,
            control_m_s=CONTROL_M_S,
            write_m_s=WRITE_M_S,
            kir_m_s=p.kir_m_s,
            nav_m_s=p.nav_m_s,
            capacitance_F=p.capacitance_F,
        ),
        u_maxwell=u_m,
        composition_mM=c,
        fast_states_V=dict(H=v_h, U=v_u, D=v_d),
        slope_conductance_S=dict(H=g_h, D=g_d),
        membrane_time_constant_s=dict(H=p.capacitance_F / g_h, D=p.capacitance_F / g_d),
        bistable_control_range=list(bistable),
        continuum_width_cells={
            str(r): theory.continuum_width_cells(p, c, u_m, v_h, v_d, r * g_h)
            for r in COUPLING_RATIOS
        },
    )


def part_theory(args):
    return prepare_theory(args.quick)


def _theory(args):
    if getattr(args, "_theory", None) is None:
        path = args.output / "theory.json"
        args._theory = json.loads(path.read_text()) if path.exists() else prepare_theory(args.quick)
    return args._theory


def _state(t):
    c = t["composition_mM"]
    return (t["fast_states_V"]["H"], c["Na"], c["K"], c["M"])


def _d_cells(vm, threshold):
    return set(np.flatnonzero(np.asarray(vm) > threshold).tolist())


def _jaccard(a, b):
    return 1.0 if not a and not b else len(a & b) / len(a | b)


def _width(v, t):
    return theory.wall_width_cells(v, t["fast_states_V"]["H"], t["fast_states_V"]["D"])


def _position(v, t):
    return theory.front_position(v, t["fast_states_V"]["H"], t["fast_states_V"]["D"])


# ---------------------------------------------------------------- parts


def part_single(args):
    """Two uncoupled cells at u_M: H holds; a write pulse gives D, which holds."""
    t = _theory(args)
    protocol = Protocol(
        n=2,
        coupling_ratio=0.0,
        control=((0.0, t["u_maxwell"]),),
        end_time=4.0,
        observe=(0.0, 0.5, 1.0, 2.0, 3.0, 4.0),
        written=(1,),
        label="single",
    )
    vm, reduced, info = run_both(protocol, t)
    return dict(
        times_s=list(protocol.observe),
        vm_V=vm.tolist(),
        reduced_vm_V=reduced.tolist(),
        h_drift_V=float(np.max(np.abs(vm[:, 0] - t["fast_states_V"]["H"]))),
        written_final_V=float(vm[-1, 1]),
        written_vs_fast_D_V=float(vm[-1, 1] - t["fast_states_V"]["D"]),
        run=info,
    )


def wall_protocol(t, ratio, *, dt=DT):
    n = WALL_CELLS
    return Protocol(
        n=n,
        coupling_ratio=ratio,
        control=((0.0, t["u_maxwell"]),),
        end_time=SETTLE_S,
        observe=(0.0, 2.0, 4.0, SETTLE_S),
        written=tuple(range(n // 2, n)),
        dt=dt,
        label=f"wall_{ratio:g}",
    )


def part_width(args):
    """Walls at the Maxwell control: engine width against the reduced model and sqrt(G)."""
    t = _theory(args)
    out = []
    for ratio in COUPLING_RATIOS:
        vm, reduced, info = run_both(wall_protocol(t, ratio), t)
        widths = [_width(v, t) for v in vm[1:]]
        reduced_w = _width(reduced[-1], t)
        out.append(
            dict(
                coupling_ratio=ratio,
                engine_width_cells=widths[-1],
                engine_width_history=widths,
                reduced_width_cells=reduced_w,
                continuum_width_cells=t["continuum_width_cells"][str(ratio)],
                width_vs_reduced_rel=widths[-1] / reduced_w - 1,
                engine_front_position=[_position(v, t) for v in vm[1:]],
                reduced_front_position=[_position(v, t) for v in reduced[1:]],
                final_vm_V=vm[-1].tolist(),
                reduced_final_vm_V=reduced[-1].tolist(),
                run=info,
            )
        )
    fit = [w for w in out if w["coupling_ratio"] in WIDTH_FIT_RATIOS]
    x = np.log([w["coupling_ratio"] for w in fit])
    slope = float(np.polyfit(x, np.log([w["engine_width_cells"] for w in fit]), 1)[0])
    reduced_slope = float(np.polyfit(x, np.log([w["reduced_width_cells"] for w in fit]), 1)[0])
    return dict(
        walls=out,
        log_slope_width_vs_coupling=slope,
        reduced_log_slope=reduced_slope,
        continuum_slope=0.5,
        fit_ratios=list(WIDTH_FIT_RATIOS),
        width_vs_reduced_rel=[w["width_vs_reduced_rel"] for w in out],
    )


TIMESTEP_DTS = (1.0e-3, 5.0e-4, 2.5e-4)
TIMESTEP_RATIO = 2.0


def part_timestep(args):
    """The kappa = 2 wall at dt 1, 0.5 and 0.25 ms: stationary width and position."""
    t = _theory(args)
    levels = []
    for dt in TIMESTEP_DTS:
        vm, _, info = run_both(wall_protocol(t, TIMESTEP_RATIO, dt=dt), t)
        levels.append(
            dict(
                dt_s=dt, width=_width(vm[-1], t), position=_position(vm[-1], t), vm=vm[-1], run=info
            )
        )
    finest = levels[-1]
    for lv in levels:
        lv["width_vs_finest_rel"] = lv["width"] / finest["width"] - 1
        lv["max_vm_vs_finest_V"] = float(np.max(np.abs(lv["vm"] - finest["vm"])))
        lv["vm"] = lv["vm"].tolist()
    return dict(
        coupling_ratio=TIMESTEP_RATIO,
        levels=levels,
        width_vs_finest_rel=[lv["width_vs_finest_rel"] for lv in levels[:-1]],
        max_vm_vs_finest_V=[lv["max_vm_vs_finest_V"] for lv in levels[:-1]],
    )


PIN_DETUNING = 0.03  # u_pin = u_M + 0.03 (D favoured)
PIN_FACTORS = (0.5, 0.8, 1.25, 2.0)
PIN_SWITCH_S, PIN_START_S, PIN_TEST_S = 1.0, 2.0, 20.0
PIN_TOLERANCE_CELLS = 0.5
MOVING_CELLS = 2.0


def pin_protocol(t, ratio):
    n = WALL_CELLS
    end = PIN_START_S + PIN_TEST_S
    return Protocol(
        n=n,
        coupling_ratio=ratio,
        control=((0.0, t["u_maxwell"]), (PIN_SWITCH_S, t["u_maxwell"] + PIN_DETUNING)),
        end_time=end,
        observe=(0.0, PIN_START_S, end),
        written=tuple(range(n // 2, n)),
        label=f"pin_{ratio:g}",
    )


def reduced_shift(t, ratio):
    reduced = reduced_run(pin_protocol(t, ratio), t)
    return _position(reduced[-1], t) - _position(reduced[1], t)


def critical_ratio(t, lo=0.02, hi=8.0, rel=0.01):
    """Reduced-model pinning threshold G*/g_H for the pinning protocol (bisection)."""
    if (
        abs(reduced_shift(t, lo)) >= PIN_TOLERANCE_CELLS
        or abs(reduced_shift(t, hi)) < PIN_TOLERANCE_CELLS
    ):
        raise ValueError("Pinning bracket does not straddle the threshold")
    while hi / lo > 1 + rel:
        mid = math.sqrt(lo * hi)
        if abs(reduced_shift(t, mid)) < PIN_TOLERANCE_CELLS:
            lo = mid
        else:
            hi = mid
    return math.sqrt(lo * hi)


def part_pinning(args):
    """Below the reduced model's critical coupling a wall stays; above it, it moves."""
    t = _theory(args)
    ratio_star = critical_ratio(t)
    cases = []
    for factor in PIN_FACTORS:
        protocol = pin_protocol(t, factor * ratio_star)
        vm, reduced, info = run_both(protocol, t)
        shift = _position(vm[-1], t) - _position(vm[1], t)
        cases.append(
            dict(
                factor=factor,
                coupling_ratio=factor * ratio_star,
                engine_shift_cells=float(shift),
                reduced_shift_cells=float(_position(reduced[-1], t) - _position(reduced[1], t)),
                engine_pinned=bool(abs(shift) < PIN_TOLERANCE_CELLS),
                run=info,
            )
        )
    by = {c["factor"]: c for c in cases}
    return dict(
        u_pin=t["u_maxwell"] + PIN_DETUNING,
        critical_ratio=ratio_star,
        cases=cases,
        weak_shift_cells=abs(by[0.5]["engine_shift_cells"]),
        strong_shift_cells=abs(by[2.0]["engine_shift_cells"]),
    )


HYSTERESIS_STEP = 0.025
HYSTERESIS_RANGE = (0.2, 0.9)  # Brackets the fixed-composition bistable range.
HYSTERESIS_DWELL_S = 1.0
UNIFORM_CELLS = 24
ANCHORED_CELLS = 16
ANCHOR_CELLS = 3


def _ramp():
    lo, hi = HYSTERESIS_RANGE
    levels = int(round((hi - lo) / HYSTERESIS_STEP))
    up = np.round(lo + HYSTERESIS_STEP * np.arange(levels + 1), 12)
    values = np.concatenate([up, up[-2::-1]])
    times = np.round(HYSTERESIS_DWELL_S * np.arange(len(values)), 12)
    return tuple((float(a), float(b)) for a, b in zip(times, values, strict=True))


def _loop(u, frac):
    half = len(u) // 2
    up = np.flatnonzero(frac[: half + 1] >= 0.5)
    down = np.flatnonzero(frac[half:] <= 0.5)
    u_up = float(u[up[0]]) if len(up) else None
    u_down = float(u[half + down[0]]) if len(down) else None
    width = (u_up - u_down) if u_up is not None and u_down is not None else None
    return u_up, u_down, width


HYSTERESIS_ARMS = dict(
    uncoupled=(0.0, False),
    coupled_uniform=(1.0, False),
    anchored_weak=(0.25, True),
    anchored_mid=(1.0, True),
    anchored_strong=(4.0, True),
)


def part_hysteresis(args):
    """Staircase ramp of u up and down: fraction of D cells against u, engine and reduced."""
    t = _theory(args)
    threshold = t["fast_states_V"]["U"]
    ramp = _ramp()
    end = ramp[-1][0] + HYSTERESIS_DWELL_S
    observe = tuple(round(s + HYSTERESIS_DWELL_S - DT, 9) for s, _ in ramp)
    a = ANCHOR_CELLS
    u = np.array([b for _, b in ramp])
    out = {}
    for name, (ratio, anchors) in HYSTERESIS_ARMS.items():
        n = ANCHORED_CELLS if anchors else UNIFORM_CELLS
        protocol = Protocol(
            n=n,
            coupling_ratio=ratio,
            control=ramp,
            end_time=end,
            observe=observe,
            no_control=tuple(range(a)) if anchors else (),
            anchored_d=tuple(range(n - a, n)) if anchors else (),
            label=name,
        )
        vm, reduced, info = run_both(protocol, t, window_s=4.0)
        cells = slice(a, n - a) if anchors else slice(None)
        frac = np.array([np.mean(v[cells] > threshold) for v in vm])
        rfrac = np.array([np.mean(v[cells] > threshold) for v in reduced])
        up, down, width = _loop(u, frac)
        rup, rdown, rwidth = _loop(u, rfrac)
        out[name] = dict(
            coupling_ratio=ratio,
            anchors=anchors,
            u=u.tolist(),
            d_fraction=frac.tolist(),
            reduced_d_fraction=rfrac.tolist(),
            u_up=up,
            u_down=down,
            loop_width=width,
            reduced_u_up=rup,
            reduced_u_down=rdown,
            reduced_loop_width=rwidth,
            run=info,
        )

    def diff(a, b):
        return None if a is None or b is None else a - b

    unc, cu = out["uncoupled"], out["coupled_uniform"]
    anchored = [out[k]["loop_width"] for k in ("anchored_weak", "anchored_mid", "anchored_strong")]
    return dict(
        threshold_V=threshold,
        step=HYSTERESIS_STEP,
        dwell_s=HYSTERESIS_DWELL_S,
        arms=out,
        uncoupled_switch_vs_reduced=[
            diff(unc["u_up"], unc["reduced_u_up"]),
            diff(unc["u_down"], unc["reduced_u_down"]),
        ],
        coupled_uniform_vs_uncoupled=[
            diff(cu["u_up"], unc["u_up"]),
            diff(cu["u_down"], unc["u_down"]),
        ],
        anchored_widths=anchored,
        anchored_width_decrements=[
            diff(anchored[i], anchored[i + 1]) for i in range(len(anchored) - 1)
        ],
    )


CUT_CELLS = 60
DOMAIN = (20, 40)  # Written cells [20, 40).
CUT_RATIO = 0.25
T_CUT, T_RESTORE, T_END = 6.0, 12.0, 24.0


def part_cut(args):
    """Write a domain, isolate it by closing both wall junctions, restore; with controls."""
    t = _theory(args)
    threshold = t["fast_states_V"]["U"]
    n = CUT_CELLS
    lo, hi = DOMAIN
    closed = [1.0] * (n - 1)
    closed[lo - 1] = closed[hi - 1] = 0.0  # Junctions (lo-1, lo) and (hi-1, hi).
    closed, opened = tuple(closed), (1.0,) * (n - 1)
    arms = dict(
        no_cut=(True, ((0.0, opened), (T_CUT, opened), (T_RESTORE, opened))),
        cut_without_restore=(True, ((0.0, opened), (T_CUT, closed))),
        cut_and_restore=(True, ((0.0, opened), (T_CUT, closed), (T_RESTORE, opened))),
        uniform_cut_and_restore=(False, ((0.0, opened), (T_CUT, closed), (T_RESTORE, opened))),
    )
    observe = (0.0, T_CUT - DT, T_RESTORE - DT, T_RESTORE + 2.0, T_END)
    out = {}
    for name, (written, schedule) in arms.items():
        protocol = Protocol(
            n=n,
            coupling_ratio=CUT_RATIO,
            control=((0.0, t["u_maxwell"]),),
            end_time=T_END,
            observe=observe,
            written=tuple(range(lo, hi)) if written else (),
            junctions=schedule,
            label=name,
        )
        vm, reduced, info = run_both(protocol, t)
        sets = [_d_cells(v, threshold) for v in vm]
        rsets = [_d_cells(v, threshold) for v in reduced]
        target = set(range(lo, hi)) if written else set()
        out[name] = dict(
            times_s=list(observe),
            d_cells=[sorted(s) for s in sets],
            reduced_d_cells=[sorted(s) for s in rsets],
            jaccard_vs_written=[_jaccard(s, target) for s in sets],
            final_jaccard_vs_precut=_jaccard(sets[-1], sets[1]),
            final_jaccard_vs_reduced=_jaccard(sets[-1], rsets[-1]),
            d_count=[len(s) for s in sets],
            final_vm_V=vm[-1].tolist(),
            run=info,
        )
    out["cut_and_restore"]["final_jaccard_vs_no_cut"] = _jaccard(
        set(out["cut_and_restore"]["d_cells"][-1]), set(out["no_cut"]["d_cells"][-1])
    )
    return dict(
        coupling_ratio=CUT_RATIO,
        domain=list(DOMAIN),
        t_cut_s=T_CUT,
        t_restore_s=T_RESTORE,
        threshold_V=threshold,
        arms=out,
        uniform_max_d_count=max(out["uniform_cut_and_restore"]["d_count"]),
    )


def numerics_summary(results):
    """Worst engine diagnostics over every run of every part (from the run records)."""
    runs = []

    def walk(value):
        if isinstance(value, dict):
            if "diagnostics_max" in value:
                runs.append(value)
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)

    walk(results)
    keys = ("max_energy_balance_relative", "max_global_charge_bound_ratio")
    worst = {k: max((r["diagnostics_max"].get(k, 0.0) for r in runs), default=None) for k in keys}
    drift = [r.get("max_cell_composition_drift_rel") for r in runs]
    worst["max_cell_composition_drift_rel"] = max((d for d in drift if d is not None), default=None)
    worst["engine_runs"] = len(runs)
    worst["energy_rtol_ars222"] = 2e-3  # surface_pump.ENERGY_RTOL[ARS(2,2,2)]
    return worst


PARTS = dict(
    theory=part_theory,
    single=part_single,
    width=part_width,
    timestep=part_timestep,
    pinning=part_pinning,
    hysteresis=part_hysteresis,
    cut=part_cut,
)


def main(argv=None):
    import jax

    jax.config.update("jax_enable_x64", True)
    from validation.morphogenesis.mg0a_gradient import _jsonable, evaluate

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("parts", nargs="+", choices=[*PARTS, "all"])
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    args._theory = None
    parts = list(PARTS) if "all" in args.parts else args.parts
    results, failures = {}, {}
    for part in parts:
        t0 = time.perf_counter()
        try:
            results[part] = PARTS[part](args)
            results[part]["part_wall_seconds"] = time.perf_counter() - t0
            if part == "theory":
                args._theory = results[part]
            (args.output / f"{part}.json").write_text(
                json.dumps(_jsonable(results[part]), indent=1)
            )
        except Exception as error:  # Preserve the failure as evidence.
            failures[part] = dict(error=repr(error), traceback=traceback.format_exc())
        status = "ok" if part in results else "FAILED"
        print(f"{part}: {status} in {time.perf_counter() - t0:.1f} s", flush=True)
    results["numerics"] = numerics_summary(results)
    report = dict(
        kind="cells.morphogenesis_mg0b_results@1",
        engine_model=MODEL_ID,
        parts=_jsonable(results),
        failures=failures,
        peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
    )
    if args.protocol is not None:
        protocol = json.loads(args.protocol.read_text())
        report["protocol_id"] = protocol["id"]
        report["verdict"] = (
            evaluate(protocol, report["parts"])
            if not failures
            else dict(passed=False, reason="part failures")
        )
    with (args.output / "results.json").open("x") as stream:
        json.dump(report, stream, indent=1)
    if failures:
        (args.output / "failure.json").write_text(json.dumps(failures, indent=1))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
