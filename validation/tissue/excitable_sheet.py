"""Track E M1's development runs on the 127-cell sheet (D170), and their report.

The held-bath hexagon (validation/stationary/worlds.hexagon(6): 127 cells, 342 junctions) of the
generic cell (candidate A, or B as given) on cells.model.resolved_pump_tissue@3, built by excitable_probe's
definition: gates pinned open, cells.heat.trapezoid_nonnegative@1, D147's declared field solver. It is a
black-box driver: the engine's own readouts at every accepted step (Vm, Vj, each membrane's net
ionic current and dVm/dt), its host checks, and any refusal with the probe's attribution. The
criteria are in the M1 evidence folder's PLAN.md, written before the runs.

`run` cases:
- controls under three stimuli: planar (the q = -6 column, 7 cells), corner (corner (-6, 6) and
  its three neighbours) and two-sided (the q = -6 and q = 6 columns). Each control climbs its
  stimulus ladder (width:strength rungs) until the front is launched (below);
- a compact disc (ring <= 2 about the centre, 19 cells) or a scattered set (19 cells drawn with
  numpy's default_rng(seed) from the cells outside the planar stimulus), under the planar
  control's launching rung, in a combined (r_Na = r_gj = r), coupling-only (r_gj = r),
  sodium-only (r_Na = r) or sodium-free (r_Na = 0, r_gj = r) arm. r_gj holds every junction
  incident to a perturbed cell, so s * r_gj is each such junction's coupling relative to s = 1.

Measures per case (host, numpy):
- each cell's first -30 mV crossing after the stimulus onset, peak and its time, end voltage;
- each cell's own upstroke: its largest dVm/dt (after the stimulus end for a stimulated cell)
  and, over its rise from -50 mV to its peak, the inward part of its net ionic membrane current
  integrated (inward charge) and its most inward value. The source fraction is the inward
  charge over C (V_peak - V_rest): 0 for a passive cell, which is a pure sink;
- each junction's largest |Vj| over the run, by class (cluster boundary, internal, outside);
- the front: the mean activation per graph-distance ring from the stimulated cells. It is
  launched when every cell crosses -30 mV, every stimulated cell crosses within its stimulus,
  the ring means rise strictly with distance, and every ring at distance >= 2 activates after
  the stimulus ends (the front outruns the stimulus).

`report` reads saved records only (no engine). `select` prints the refinement picks from a main
record. `selfcheck` runs the new series' fail-fast checks (one cell: C dVm/dt = -I_m; the sheet
during its stimulus: the most inward currents are the stimulated cells; a sodium-free twin: no
inward charge in its perturbed cells).
Usage:
  python -B -P excitable_sheet.py run --output DIR --name NAME --nav .. --kir .. --cm .. --kv ..
      --s 1000 --dt 2.5e-6 [--controls planar corner two-sided] [--ladder W:P ..]
      [--cluster disc] [--combined R ..] [--coupling-only R ..] [--sodium-only R ..]
      [--sodium-free R ..] [--stim-from RECORD]
  python -B -P excitable_sheet.py report --records DIR --output FILE
  python -B -P excitable_sheet.py select --output - (--sheet RECORD | --chain SEGMENT_JSON)
  python -B -P excitable_sheet.py selfcheck --output DIR --s 1000 --dt 2.5e-6 [point]
"""

import argparse
import json
import sys
import time
import traceback
from collections import deque
from pathlib import Path

import jax

jax.config.update("jax_enable_x64", True)

import jax.numpy as jnp  # noqa: E402
import numpy as np  # noqa: E402

from cells.definitions.specs import ConfigError, parse_spec  # noqa: E402
from cells.definitions.surface_pump_v3_spec import control_values as v3_controls  # noqa: E402
from cells.execution.errors import NumericalError  # noqa: E402
from cells.execution.state import initialise  # noqa: E402
from cells.execution.windows import WindowPolicy, iter_windows  # noqa: E402
from cells.models import surface_pump_v3 as v3  # noqa: E402
from validation.stationary import worlds  # noqa: E402
from validation.tissue import excitable_probe as probe  # noqa: E402

RADIUS = 6
CLUSTER_SIZE = 19
FLOOR = 20.0  # D170 ruling 3: the provisional floor s * r_gj >= 20.
JUNCTION_LIMIT_V = 0.120
CHANNEL_TOP_V = 0.060
ACTIVATION_V = -0.030
RISE_START_V = -0.050
TWIN_MARGIN_V = 0.010
STIM_ON_S = 2e-3
QUIET_S, MIN_AFTER_STIM_S = 0.010, 0.012
FLAG_JUNCTION_MARGIN_V, FLAG_CHANNEL_MARGIN_V = 0.005, 0.003
REFINE_TOLERANCES = dict(vj_V=5e-4, vm_V=5e-4, total_activation_relative=0.02)
ARMS = ("combined", "coupling_only", "sodium_only", "sodium_free")
SERIES_CHUNK = 128
DEFAULT_LADDER = ("1e-3:2e-7", "1e-3:4e-7", "1e-3:8e-7")

SHEET_PLAN = dict(
    status="M1 development runs (D170): criteria fixed in PLAN.md before any run; not judged",
    world="127-cell held-bath hexagon, gates pinned open, cells.heat.trapezoid_nonnegative@1",
    floor="s * r_gj >= 20 at every perturbed junction (provisional, D170 ruling 3)",
    activation="recorded as continuous values: each cell's max dVm/dt and its source fraction "
    "(inward ionic charge over its rise / C (V_peak - V_rest)); the earlier twin rule (peak > 0 mV "
    "and >= 10 mV above the sodium-free twin's) is kept for comparison",
    capture="launched front: all cross -30 mV; stimulated cells within the stimulus; ring means "
    "rise strictly with graph distance; every ring at distance >= 2 after the stimulus ends",
    J="J1: no domain-classified refusal; J2: largest |Vj| by junction class against 120 mV",
    T="block bracket per arm, refused cases excluded; T2: a disc case blocks at s * r_gj >= 20",
    P="largest peak per lightly loaded class (corner, rim, before block, collision, end) "
    "against +60 mV; a margin under 3 mV is flagged",
    R="half-step repeats: same non-activated cells, |Vj| and Vm maxima within 0.5 mV, total "
    "activation time within 2 %",
)


# ----------------------------------------------------------------------------- geometry


def geometry(radius=RADIUS):
    cells, edges = worlds.hexagon(radius)
    n = len(cells)
    nbrs = neighbours(n, edges)
    ring = [worlds.ring(c) for c in cells]
    kind = [
        "corner" if len(nbrs[i]) == 3 else "rim" if ring[i] == radius else "interior"
        for i in range(n)
    ]
    return dict(
        cells=cells,
        edges=edges,
        nbrs=nbrs,
        ring=ring,
        kind=kind,
        index={c: i for i, c in enumerate(cells)},
    )


def neighbours(n, edges):
    nbrs = [[] for _ in range(n)]
    for k, (a, b) in enumerate(edges):
        nbrs[a].append((b, k))
        nbrs[b].append((a, k))
    return nbrs


def distances(n, edges, sources):
    """Graph distance of every cell from the source set (breadth first)."""
    nbrs = neighbours(n, edges)
    dist = [None] * n
    queue = deque()
    for s in sources:
        dist[s] = 0
        queue.append(s)
    while queue:
        i = queue.popleft()
        for j, _ in nbrs[i]:
            if dist[j] is None:
                dist[j] = dist[i] + 1
                queue.append(j)
    return dist


def stimulus_cells(geo, kind):
    q = [c[0] for c in geo["cells"]]
    n = len(q)
    if kind == "planar":
        return [i for i in range(n) if q[i] == -RADIUS]
    if kind == "two-sided":
        return [i for i in range(n) if abs(q[i]) == RADIUS]
    if kind == "corner":
        corner = geo["index"][(-RADIUS, RADIUS)]
        return sorted([corner] + [b for b, _ in geo["nbrs"][corner]])
    raise ValueError(kind)


def cluster_cells(geo, kind, seed=0):
    n = len(geo["cells"])
    if kind == "disc":
        return [i for i in range(n) if geo["ring"][i] <= 2]
    if kind == "scattered":
        stim = set(stimulus_cells(geo, "planar"))
        pool = [i for i in range(n) if i not in stim]
        rng = np.random.default_rng(seed)
        return sorted(int(i) for i in rng.choice(pool, size=CLUSTER_SIZE, replace=False))
    raise ValueError(kind)


def arm_values(arm, r):
    """(r_Na, r_gj) for an arm at strength r."""
    return dict(
        combined=(r, r), coupling_only=(1.0, r), sodium_only=(r, 1.0), sodium_free=(0.0, r)
    )[arm]


def parse_ladder(words):
    """'width_s:m_s' rungs, in order."""
    out = []
    for w in words:
        width, m_s = w.split(":")
        out.append((float(width), float(m_s)))
    return out


# ----------------------------------------------------------------------------- execution


@jax.jit
def _series(states, controls, layout):
    """The engine's Vm, Vj, net ionic membrane current (outward +) and dVm/dt per row."""

    def one(state, control):
        w = v3.readouts(state, control, layout)
        f = w.field
        r = f.rates
        return (
            r.membrane_voltage_V,
            r.junction_voltage_V,
            r.membrane_current_A,
            f.membrane_voltage_rate_V_s,
            w.valid,
        )

    return jax.vmap(one)(states, controls)


def window_series(spec, window, skip_first):
    times = np.asarray(window.times)
    history = window.history
    controls = v3_controls(spec, times)
    rows = len(times)
    parts = [[] for _ in range(5)]
    for start in range(0, rows, SERIES_CHUNK):
        index = np.minimum(np.arange(start, start + SERIES_CHUNK), rows - 1)
        states = type(history)(*(jnp.asarray(np.asarray(v)[index]) for v in history))
        control = type(controls)(*(jnp.asarray(np.asarray(v)[index]) for v in controls))
        out = _series(states, control, window.final.layout)
        keep = min(SERIES_CHUNK, rows - start)
        for k in range(5):
            parts[k].append(np.asarray(out[k])[:keep])
    first = 1 if skip_first else 0
    vm, vj, im, dv = (np.concatenate(parts[k])[first:] for k in range(4))
    return times[first:], vm, vj, im, dv, bool(np.all(np.concatenate(parts[4])))


def execute_sheet(raw, *, window_steps=1024, stop=None):
    """iter_windows with the readouts series at every accepted step (numpy, not lists).

    The keys probe.record reads are kept: steps, wall_seconds, timings, diagnostics, refusal,
    readouts_valid, observer_max_abs_dV, stopped_early_at_s and last.
    """
    out = dict(
        diagnostics={},
        timings={},
        steps=0,
        refusal=None,
        observer_max_abs_dV=0.0,
        readouts_valid=True,
    )
    chunks = dict(times=[], vm=[], vj=[], im=[], dvdt=[])
    last, started, series_seconds = None, time.perf_counter(), 0.0
    try:
        spec = parse_spec(raw)
        for window in iter_windows(spec, WindowPolicy(window_steps, "observations")):
            before = time.perf_counter()
            t, vm, vj, im, dv, ok = window_series(spec, window, skip_first=bool(chunks["times"]))
            series_seconds += time.perf_counter() - before
            for k, v in (("times", t), ("vm", vm), ("vj", vj), ("im", im), ("dvdt", dv)):
                chunks[k].append(v)
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
            if stop is not None:
                view = dict(times=np.concatenate(chunks["times"]), vm=np.concatenate(chunks["vm"]))
                if stop(view):
                    out["stopped_early_at_s"] = float(window.final.time)
                    break
    except (NumericalError, ConfigError) as error:
        out["refusal"] = dict(
            kind=type(error).__name__,
            message=str(error),
            last_accepted_window_end_s=None if last is None else float(last.time),
        )
        if last is None and isinstance(error, NumericalError):
            try:  # A refusal inside the first window: attribute from the initial state.
                last = initialise(parse_spec(raw))
            except (NumericalError, ConfigError):
                last = None
    for k, v in chunks.items():
        out[k] = np.concatenate(v) if v else np.zeros((0,))
    out["timings"]["probe_voltage_seconds"] = series_seconds
    out["wall_seconds"] = time.perf_counter() - started
    out["last"] = last
    return out


# ----------------------------------------------------------------------------- measures


def upstroke(t, vm, im, dv, *, stim, on_s, off_s, capacitance):
    """Per cell: max dVm/dt; over the rise from -50 mV to the peak, the inward ionic charge,
    the most inward current, the depolarising charge C (V_peak - V_rest) and their ratio."""
    n = vm.shape[1]
    k_on, k_off = int(np.searchsorted(t, on_s)), int(np.searchsorted(t, off_s))
    dts = np.diff(t, prepend=t[0])
    stim = set(stim)
    out = dict(
        max_dvdt_V_s=[],
        inward_charge_C=[],
        peak_inward_A=[],
        rise_charge_C=[],
        source_fraction=[],
        rise_start_s=[],
    )
    for i in range(n):
        s0 = k_off if i in stim else k_on
        if s0 >= len(t):
            for key in out:
                out[key].append(None)
            continue
        out["max_dvdt_V_s"].append(float(dv[s0:, i].max()))
        k_peak = s0 + int(np.argmax(vm[s0:, i]))
        above = np.flatnonzero(vm[s0 : k_peak + 1, i] >= RISE_START_V)
        v_rest = float(vm[min(k_on, len(t) - 1), i])
        rise = float(capacitance[i] * (vm[k_peak, i] - v_rest))
        if above.size == 0:
            q_in, peak_in, start = 0.0, 0.0, None
        else:
            k0 = s0 + int(above[0])
            seg = im[k0 : k_peak + 1, i]
            q_in = float(np.sum(np.maximum(-seg, 0.0) * dts[k0 : k_peak + 1]))
            peak_in = float(max(-seg.min(), 0.0))
            start = float(t[k0])
        out["inward_charge_C"].append(q_in)
        out["peak_inward_A"].append(peak_in)
        out["rise_charge_C"].append(rise)
        out["source_fraction"].append(q_in / rise if rise > 0 else 0.0)
        out["rise_start_s"].append(start)
    return out


def front(activation, stim, edges, *, on_s, off_s):
    """The launched-front rule from the activation times (see the module docstring)."""
    n = len(activation)
    dist = distances(n, edges, stim)
    top = max(d for d in dist if d is not None)
    means = []
    for d in range(top + 1):
        ts = [activation[i] for i in range(n) if dist[i] == d and activation[i] is not None]
        means.append(float(np.mean(ts)) if ts else None)
    all_cross = all(x is not None for x in activation)
    within = all(activation[i] is not None and on_s <= activation[i] <= off_s for i in stim)
    rising = all(
        x is not None and y is not None and y > x for x, y in zip(means, means[1:], strict=False)
    )
    outruns = all(m is not None and m > off_s for m in means[2:])
    return dict(
        ring_mean_activation_s=means,
        all_cross=all_cross,
        stimulated_within_stimulus=within,
        rings_rise=rising,
        outruns_stimulus=outruns,
        launched=bool(all_cross and within and rising and outruns),
    )


def sheet_measures(t, vm, vj, im, dv, geo, *, stim, on_s, stim_end_s, capacitance):
    """Per-cell activation, upstroke, peaks and end voltages; per-junction maxima; the front."""
    n = vm.shape[1]
    start = int(np.searchsorted(t, on_s))
    acts = [probe.crossings(t, vm[:, i], ACTIVATION_V, start=start) for i in range(n)]
    first = [a[0] if a else None for a in acts]
    peak = vm.max(axis=0)
    peak_time = t[vm.argmax(axis=0)]
    edges = np.asarray(geo["edges"])
    absvj = np.abs(vj)
    jmax = absvj.max(axis=0)
    jarg = absvj.argmax(axis=0)
    gap = np.abs(absvj - np.abs(vm[:, edges[:, 0]] - vm[:, edges[:, 1]]))
    top = int(np.argmax(jmax))
    activated = [f for f in first if f is not None]
    far = [i for i in range(n) if geo["cells"][i][0] == RADIUS and i not in set(stim)]
    far_times = [first[i] for i in far if first[i] is not None]
    return dict(
        activation_s=first,
        activations_per_cell=[len(a) for a in acts],
        max_activations=max(len(a) for a in acts),
        peak_V=peak.tolist(),
        peak_time_s=peak_time.tolist(),
        end_V=vm[-1].tolist(),
        end_time_s=float(t[-1]),
        crossing_never=[i for i in range(n) if first[i] is None],
        activated_during_stimulus=[
            i for i in range(n) if first[i] is not None and first[i] < stim_end_s
        ],
        total_crossing_s=(max(activated) - on_s) if activated else None,
        far_column_mean_activation_s=float(np.mean(far_times)) if far_times else None,
        far_column_activated=len(far_times),
        vj_abs_max_V=float(jmax[top]),
        vj_top=dict(
            junction=top,
            cells=[int(edges[top, 0]), int(edges[top, 1])],
            time_s=float(t[jarg[top]]),
            vm_at_V=[float(vm[jarg[top], edges[top, 0]]), float(vm[jarg[top], edges[top, 1]])],
        ),
        vj_per_junction_V=jmax.tolist(),
        vj_time_s=t[jarg].tolist(),
        vj_mapping_max_gap_V=float(gap.max()),
        vm_max_V=float(peak.max()),
        vm_max_cell=int(np.argmax(peak)),
        vm_max_time_s=float(peak_time[int(np.argmax(peak))]),
        vm_min_V=float(vm.min()),
        upstroke=upstroke(
            t, vm, im, dv, stim=stim, on_s=on_s, off_s=stim_end_s, capacitance=capacitance
        ),
        front=front(first, stim, geo["edges"], on_s=on_s, off_s=stim_end_s),
    )


def stimulus_stage_ratio(raw, dt, on_step):
    """dt x membrane_rate of the initial state with the stimulus on (host, numpy)."""
    spec = parse_spec(raw)
    first = initialise(spec)
    p = type(first.layout)(*(np.asarray(v) for v in first.layout))
    control = probe.Control(*(np.asarray(v[0]) for v in v3_controls(spec, [(on_step + 0.5) * dt])))
    state = v3.STATE_TYPE(*(np.asarray(v) for v in first.state))
    return float(dt * v3.membrane_rate(state, control, p, xp=np))


def refusal_class(rec):
    """domain: no host retry down to dt/8 is accepted; step: a smaller sub-step is; check: the
    whole step is accepted on the host, so a window check refused it; unattributed otherwise."""
    if not rec.get("refusal"):
        return None
    trials = (rec.get("attribution") or {}).get("host_retry")
    if not trials:
        return "unattributed"
    ok = {k: bool(v.get("accepted")) and v.get("error") is None for k, v in trials.items()}
    if ok.get("1"):
        return "check"
    return "step" if any(ok.values()) else "domain"


# ----------------------------------------------------------------------------- runs


def sheet_definition(args, geo, *, stim, cell_nav, junctions, dt, width_s, m_s, end=None):
    on, width = int(round(STIM_ON_S / dt)), max(1, int(round(width_s / dt)))
    raw = probe.definition(
        len(geo["cells"]),
        dt=dt,
        end_time=end or args.end,
        kv_m_s=args.kv,
        s=args.s,
        booking=args.booking,
        stim=dict(cells=stim, pulses=[(on, on + width)], m_s=m_s),
        cell_nav=cell_nav,
        junction_availability=junctions,
        edges=geo["edges"],
    )
    return raw, on, (on + width) * dt


def sheet_case(args, geo, *, label, stimulus, cluster, arm, strength, dt, width_s, m_s):
    stim = stimulus_cells(geo, stimulus)
    r_na, r_gj = (1.0, 1.0) if arm is None else arm_values(arm, strength)
    held = set(cluster)
    cell_nav = {i: r_na for i in held} if r_na != 1.0 else None
    junctions = (
        {k: r_gj for k, (a, b) in enumerate(geo["edges"]) if a in held or b in held}
        if r_gj != 1.0
        else None
    )
    raw, on, stim_end = sheet_definition(
        args, geo, stim=stim, cell_nav=cell_nav, junctions=junctions, dt=dt, width_s=width_s,
        m_s=m_s,
    )  # fmt: skip

    def stop(o):  # Every cell below -30 mV for 10 ms, at least 12 ms after the stimulus.
        t = o["times"]
        if len(t) == 0 or t[-1] < stim_end + MIN_AFTER_STIM_S:
            return False
        recent = t > t[-1] - QUIET_S
        return bool(np.all(o["vm"][recent] < ACTIVATION_V))

    r_run = execute_sheet(raw, stop=stop)
    rec = probe.record(
        raw,
        r_run,
        label=label,
        stimulus=stimulus,
        stimulus_cells=stim,
        stimulus_m_s=m_s,
        stimulus_width_s=stim_end - on * dt,
        cluster=sorted(held),
        arm=arm,
        strength=strength,
        r_na=r_na,
        r_gj=r_gj,
        s=args.s,
        dt_s=dt,
        s_times_r_gj=args.s * r_gj,
        stim_end_s=stim_end,
    )
    rec["refusal_class"] = refusal_class(rec)
    try:
        rec["static_bounds"] = probe.static_bounds(raw)
        rec["stimulus_stage_ratio"] = stimulus_stage_ratio(raw, dt, on)
    except ConfigError as error:
        rec["static_bounds"] = dict(refusal=str(error))
    if len(r_run["times"]) > 2:
        cap = np.asarray(r_run["last"].layout.membrane_capacitance)[: len(geo["cells"])]
        rec["capacitance_F"] = cap.tolist()
        rec["measures"] = sheet_measures(
            r_run["times"], r_run["vm"], r_run["vj"], r_run["im"], r_run["dvdt"], geo,
            stim=stim, on_s=on * dt, stim_end_s=stim_end, capacitance=cap,
        )  # fmt: skip
    m = rec.get("measures", {})
    probe.log(
        f"sheet {label} s {args.s:g} dt {dt:g} stim {width_s:g}:{m_s:g}: "
        f"launched {m.get('front', {}).get('launched')} "
        f"crossing-never {len(m.get('crossing_never', []))} vj {m.get('vj_abs_max_V')} "
        f"vm {m.get('vm_max_V')} steps {rec['steps']} wall {rec['wall_seconds']:.1f} refusal "
        f"{rec['refusal_class']} {rec['refusal'] and rec['refusal']['message'][:90]}"
    )
    return rec


def captured(rec):
    """A control captures when its front is launched without a refusal."""
    m = rec.get("measures") or {}
    return bool(not rec["refusal"] and m and m.get("front", {}).get("launched"))


def part_run(args):
    probe.set_point(args.nav, args.kir, args.cm)
    geo = geometry()
    out = dict(
        provenance=probe.provenance(),
        plan=SHEET_PLAN,
        part="sheet",
        name=args.name,
        point=dict(nav_m_s=args.nav, kir_m_s=args.kir, cm_F_m2=args.cm, kv_m_s=args.kv),
        s=args.s,
        dt_s=args.dt,
        geometry=dict(
            cells=[list(c) for c in geo["cells"]],
            edges=[list(e) for e in geo["edges"]],
            kind=geo["kind"],
            ring=geo["ring"],
        ),
        cases=[],
    )
    out["rest"] = probe.relax_rest(args.kv)
    path = Path(args.output) / f"{args.name}.json"
    ladder = parse_ladder(args.ladder)
    planar = None
    if args.stim_from:  # Refinements and later arms use the main record's launching rung.
        with open(args.stim_from) as stream:
            planar = json.load(stream).get("planar_stimulus")
        if planar:
            ladder = [(planar["width_s"], planar["m_s"])]
    out["ladder"] = [dict(width_s=w, m_s=m) for w, m in ladder]
    for stimulus in args.controls:
        rec = None
        for attempt, (width_s, m_s) in enumerate(ladder):
            rec = sheet_case(
                args, geo, label=f"control {stimulus}", stimulus=stimulus, cluster=[],
                arm=None, strength=None, dt=args.dt, width_s=width_s, m_s=m_s,
            )  # fmt: skip
            rec["capture_attempt"] = attempt
            rec["captured"] = captured(rec)
            out["cases"].append(rec)
            if rec["captured"]:
                break
            rec["label"] = f"control {stimulus} not launched at {width_s:g}:{m_s:g}"
            write(path, out)
        write(path, out)
        if stimulus == "planar" and rec is not None and rec["captured"]:
            planar = dict(width_s=rec["stimulus_width_s"], m_s=rec["stimulus_m_s"])
    out["planar_stimulus"] = planar
    out["planar_stimulus_m_s"] = None if planar is None else planar["m_s"]
    if args.cluster and planar is None:  # PLAN: no perturbed cases without a launched front.
        out["skipped"] = "the planar control launched no front on its ladder"
    elif args.cluster:
        cluster = cluster_cells(geo, args.cluster, args.seed)
        out["cluster"] = dict(kind=args.cluster, cells=cluster, seed=args.seed)
        for arm in ARMS:
            for r in getattr(args, arm) or []:
                rec = sheet_case(
                    args, geo, label=f"{args.cluster} {arm} {r:g}", stimulus="planar",
                    cluster=cluster, arm=arm, strength=r, dt=args.dt,
                    width_s=planar["width_s"], m_s=planar["m_s"],
                )  # fmt: skip
                out["cases"].append(rec)
                write(path, out)
    out["peak_rss_mb"] = probe.peak_rss_mb()
    write(path, out)


def write(path, out):
    path.parent.mkdir(parents=True, exist_ok=True)
    probe.write_json(path, out)


# ----------------------------------------------------------------------------- self-check


def part_selfcheck(args):
    """Fail-fast checks of the new series before any run relies on them (PLAN amendment 1)."""
    probe.set_point(args.nav, args.kir, args.cm)
    rest = probe.relax_rest(args.kv)
    checks = dict(provenance=probe.provenance(), rest=rest)
    # (i) One cell, kicked to -20 mV (kicks are depolarisations in mV): C dVm/dt = -I_m.
    kick_mV = 1e3 * (-0.020 - probe.POINT["rest"][0])
    raw = probe.definition(
        1, dt=args.dt, end_time=0.005, kv_m_s=args.kv, kicks={0: kick_mV}, obs_dt=1e-3
    )
    r = execute_sheet(raw)
    cap = float(np.asarray(r["last"].layout.membrane_capacitance)[0])
    lhs, rhs = cap * r["dvdt"][:, 0], -r["im"][:, 0]
    scale = float(np.max(np.abs(rhs)))
    checks["one_cell"] = dict(
        refusal=r["refusal"],
        rows=int(len(lhs)),
        max_abs_residual_A=float(np.max(np.abs(lhs - rhs))),
        current_scale_A=scale,
        peak_V=float(r["vm"][:, 0].max()),
        passes=bool(r["refusal"] is None and np.max(np.abs(lhs - rhs)) <= 1e-9 * scale),
    )
    # (ii) and (iii): the disc's sodium-free twin at r = 0.25 on the sheet, under the first rung.
    geo = geometry()
    stim = stimulus_cells(geo, "planar")
    disc = cluster_cells(geo, "disc")
    held = set(disc)
    width_s, m_s = parse_ladder(args.ladder)[0]
    rec = sheet_case(
        args, geo, label="selfcheck disc sodium_free 0.25", stimulus="planar", cluster=disc,
        arm="sodium_free", strength=0.25, dt=args.dt, width_s=width_s, m_s=m_s,
    )  # fmt: skip
    junctions = {k: 0.25 for k, (a, b) in enumerate(geo["edges"]) if a in held or b in held}
    # The run covers the whole stimulus: every control must lie within the horizon (attempt 1 of
    # PLAN amendment 1 stopped here when the horizon ended inside the stimulus).
    raw2, on, stim_end = sheet_definition(
        args, geo, stim=stim, cell_nav={i: 0.0 for i in disc}, junctions=junctions, dt=args.dt,
        width_s=width_s, m_s=m_s, end=STIM_ON_S + width_s + 1e-4,
    )  # fmt: skip
    r2 = execute_sheet(raw2)
    t2, im2 = r2["times"], r2["im"]
    rows = [k for k in range(len(t2)) if on * args.dt < t2[k] <= on * args.dt + 0.1e-3]
    inward_ok = []
    for k in rows:
        order = set(np.argsort(im2[k])[: len(stim)].tolist())
        inward_ok.append(order == set(stim) and np.all(im2[k, stim] < 0))
    checks["stimulus_inward"] = dict(
        refusal=r2["refusal"],
        rows_checked=len(rows),
        passes=bool(r2["refusal"] is None and rows and all(inward_ok)),
    )
    up = (rec.get("measures") or {}).get("upstroke", {})
    q = [up["inward_charge_C"][i] for i in disc] if up else []
    rise = [up["rise_charge_C"][i] for i in disc] if up else []
    risen = sum(1 for i in disc if up and up["rise_start_s"][i] is not None)
    checks["twin_no_inward"] = dict(
        refusal=rec["refusal"],
        disc_cells_risen_above_minus50mV=risen,
        largest_inward_charge_C=max(q) if q else None,
        median_rise_charge_C=float(np.median(rise)) if rise else None,
        passes=bool(
            rec["refusal"] is None
            and risen > 0
            and q
            and max(q) <= 1e-6 * max(float(np.median(rise)), 1e-30)
        ),
    )
    names = ("one_cell", "stimulus_inward", "twin_no_inward")
    checks["passes"] = all(checks[k]["passes"] for k in names)
    probe.write_json(Path(args.output) / "selfcheck.json", checks)
    probe.log(f"selfcheck: { {k: checks[k]['passes'] for k in names} }")
    if not checks["passes"]:
        raise SystemExit("selfcheck failed: see selfcheck.json")


# ----------------------------------------------------------------------------- report


def bracket(rows):
    """rows [(r, blocked)]: the largest r that blocks and the smallest that does not."""
    blocked = [r for r, b in rows if b]
    passing = [r for r, b in rows if not b]
    hi = max(blocked) if blocked else None
    lo = min(passing) if passing else None
    return dict(
        largest_r_blocking=hi,
        smallest_r_passing=lo,
        monotonic=hi is None or lo is None or hi < lo,
    )


def twin_of(case, cases):
    """The sodium-free twin: same s and cells, r_Na = 0, the same r_gj; the same step first."""
    pool = [
        c
        for c in cases
        if c.get("measures")
        and not c["refusal"]
        and c["r_na"] == 0.0
        and c["cluster"] == case["cluster"]
        and abs(c["r_gj"] - case["r_gj"]) < 1e-12
    ]
    same = [c for c in pool if c["dt_s"] == case["dt_s"]]
    return (same or pool or [None])[-1]


def activation(case, cases, geo):
    """The earlier twin rule (kept for comparison): unperturbed cells by -30 mV crossing;
    perturbed cells by peak > 0 mV and >= 10 mV above the sodium-free twin's."""
    m = case["measures"]
    first, peak = m["activation_s"], m["peak_V"]
    held = set(case["cluster"])
    twin = twin_of(case, cases) if held else None
    tp = twin["measures"]["peak_V"] if twin else None
    active = []
    for i in range(len(first)):
        if i not in held:
            active.append(first[i] is not None)
        elif case["r_na"] == 0.0:
            active.append(False)  # A twin is its own passive reference.
        elif tp is None:
            active.append(peak[i] > 0.0)
        else:
            active.append(peak[i] > 0.0 and peak[i] - tp[i] >= TWIN_MARGIN_V)
    return active, (None if twin is None else twin["label"])


def source_activation(case, floor_C):
    """The sign rule (development): an unstimulated cell activates when it crosses -30 mV and
    its inward ionic charge over its rise exceeds the passive floor (the twins' largest). A
    stimulated cell, a source by construction, activates when it crosses -30 mV."""
    m = case["measures"]
    up = m.get("upstroke")
    if not up or floor_C is None:
        return None
    stim = set(case["stimulus_cells"])
    return [
        m["activation_s"][i] is not None
        and (i in stim or (up["inward_charge_C"][i] or 0.0) > floor_C)
        for i in range(len(m["activation_s"]))
    ]


def lightly_loaded(case, active, geo):
    """The PLAN's peak classes, stimulated and perturbed cells excluded from the cell classes."""
    m = case["measures"]
    first, peak, ptime = m["activation_s"], m["peak_V"], m["peak_time_s"]
    stim, held = set(case["stimulus_cells"]), set(case["cluster"])
    kind, nbrs = geo["kind"], geo["nbrs"]
    n = len(first)
    free = [i for i in range(n) if i not in stim and i not in held]

    def local_max(i):
        others = [b for b, _ in nbrs[i] if b not in held]
        return all(first[b] is not None and first[b] <= first[i] for b in others)

    groups = dict(
        corner=[i for i in free if kind[i] == "corner"],
        rim=[i for i in free if kind[i] == "rim"],
        interior=[i for i in free if kind[i] == "interior"],
        before_block=[i for i in free if active[i] and any(not active[b] for b, _ in nbrs[i])],
        collision=[i for i in free if active[i] and kind[i] == "interior" and local_max(i)],
        end=[i for i in free if active[i] and kind[i] != "interior" and local_max(i)],
        perturbed=sorted(held),
        stimulated=sorted(stim),
    )
    out = {}
    for name, cells in groups.items():
        if cells:
            i = max(cells, key=lambda c: peak[c])
            out[name] = dict(
                cell=int(i),
                peak_V=float(peak[i]),
                margin_V=float(CHANNEL_TOP_V - peak[i]),
                thin=bool(CHANNEL_TOP_V - peak[i] < FLAG_CHANNEL_MARGIN_V),
                peak_time_s=float(ptime[i]),
                during_stimulus=bool(ptime[i] < case["stim_end_s"]),
                kind=kind[i],
                ring=int(geo["ring"][i]),
                axial=list(geo["cells"][i]),
                count=len(cells),
            )
    return out


def junction_classes(case, geo):
    m = case["measures"]
    held = set(case["cluster"])
    jmax, jt = m["vj_per_junction_V"], m["vj_time_s"]
    out = {}
    for k, (a, b) in enumerate(geo["edges"]):
        ca, cb = a in held, b in held
        label = "boundary" if ca != cb else "internal" if ca else "outside"
        if label not in out or jmax[k] > out[label]["vj_abs_max_V"]:
            out[label] = dict(
                junction=k,
                cells=[a, b],
                vj_abs_max_V=float(jmax[k]),
                time_s=float(jt[k]),
                during_stimulus=bool(jt[k] < case["stim_end_s"]),
                kinds=[geo["kind"][a], geo["kind"][b]],
                rings=[int(geo["ring"][a]), int(geo["ring"][b])],
            )
    return out


def upstroke_summary(case, floor_C):
    """Continuous upstroke values of the perturbed and unperturbed cells (stimulated excluded)."""
    m = case["measures"]
    up = m.get("upstroke")
    if not up:
        return None
    held, stim = set(case["cluster"]), set(case["stimulus_cells"])
    n = len(m["activation_s"])

    def stats(cells, key):
        vals = [up[key][i] for i in cells if up[key][i] is not None]
        if not vals:
            return None
        return dict(min=float(min(vals)), median=float(np.median(vals)), max=float(max(vals)))

    pert = sorted(held)
    free = [i for i in range(n) if i not in held and i not in stim]
    return dict(
        perturbed_source_fraction=stats(pert, "source_fraction"),
        perturbed_max_dvdt_V_s=stats(pert, "max_dvdt_V_s"),
        perturbed_inward_charge_C=stats(pert, "inward_charge_C"),
        unperturbed_source_fraction=stats(free, "source_fraction"),
        unperturbed_max_dvdt_V_s=stats(free, "max_dvdt_V_s"),
        perturbed_above_floor=None
        if floor_C is None
        else int(sum((up["inward_charge_C"][i] or 0.0) > floor_C for i in pert)),
    )


def case_row(case, cases, geo, planar, floor_C):
    m = case["measures"]
    active, twin = activation(case, cases, geo)
    held = set(case["cluster"])
    never = [i for i, a in enumerate(active) if not a]
    first = m["activation_s"]
    times = [first[i] for i, a in enumerate(active) if a and first[i] is not None]
    total = (max(times) - STIM_ON_S) if times else None
    p_total = planar and planar.get("total")
    far_delay = None
    if planar and m["far_column_mean_activation_s"] is not None and planar.get("far") is not None:
        far_delay = m["far_column_mean_activation_s"] - planar["far"]
    sign = source_activation(case, floor_C)
    return dict(
        label=case["label"],
        arm=case["arm"],
        strength=case["strength"],
        s_times_r_gj=case["s_times_r_gj"],
        twin=twin,
        block=bool(never),
        never=never,
        perturbed_activated=sum(1 for i in held if active[i]),
        perturbed=len(held),
        sign_rule_never=None if sign is None else [i for i, a in enumerate(sign) if not a],
        sign_rule_block=None if sign is None else not all(sign),
        unperturbed_never=[i for i in never if i not in held],
        never_end_V_max=max((m["end_V"][i] for i in never), default=None),
        max_activations=m["max_activations"],
        activated_during_stimulus=len(m["activated_during_stimulus"]),
        total_activation_s=total,
        total_over_control=None if not total or not p_total else total / p_total,
        far_column_delay_s=far_delay,
        vj_abs_max_V=m["vj_abs_max_V"],
        vj_top=m["vj_top"],
        vj_mapping_max_gap_V=m["vj_mapping_max_gap_V"],
        junction_classes=junction_classes(case, geo),
        vm_max_V=m["vm_max_V"],
        vm_max_during_stimulus=bool(m["vm_max_time_s"] < case["stim_end_s"]),
        peaks=lightly_loaded(case, active, geo),
        upstroke=upstroke_summary(case, floor_C),
        front=m.get("front"),
        stimulus_stage_ratio=case.get("stimulus_stage_ratio"),
    )


def passive_floor(cases):
    """The largest inward charge of any perturbed cell in a passive (r_Na = 0) case: the
    measured floor of the sign rule; None when no passive case carries upstroke values."""
    vals = []
    for c in cases:
        up = (c.get("measures") or {}).get("upstroke")
        if c.get("refusal") or not up or c["r_na"] != 0.0 or not c["cluster"]:
            continue
        vals += [up["inward_charge_C"][i] or 0.0 for i in c["cluster"]]
    return max(vals) if vals else None


def sheet_summary(records):
    """Criteria J, T, P and R per option (s, main dt) from the sheet records."""
    options, geos = {}, {}
    for rec in records:
        geo = rec["geometry"]
        geos[rec["s"]] = dict(
            edges=[tuple(e) for e in geo["edges"]],
            kind=geo["kind"],
            ring=geo["ring"],
            cells=[tuple(c) for c in geo["cells"]],
            nbrs=neighbours(len(geo["cells"]), geo["edges"]),
        )
        for c in rec["cases"]:
            options.setdefault(rec["s"], []).append(c)
    out = {}
    for s, cases in sorted(options.items()):
        geo = geos[s]
        main_dt = max(c["dt_s"] for c in cases)
        main = [c for c in cases if c["dt_s"] == main_dt]
        fine = {c["label"]: c for c in cases if c["dt_s"] < main_dt}
        good = [c for c in main if not c["refusal"] and c.get("measures")]
        floor_C = passive_floor(good)
        planar_case = next((c for c in reversed(good) if c["label"] == "control planar"), None)
        planar = None
        if planar_case:
            row = case_row(planar_case, cases, geo, None, floor_C)
            planar = dict(
                total=row["total_activation_s"],
                far=planar_case["measures"]["far_column_mean_activation_s"],
            )
        rows = {c["label"]: case_row(c, cases, geo, planar, floor_C) for c in good}
        refusals = [
            dict(label=c["label"], refusal_class=c.get("refusal_class"),
                 message=c["refusal"]["message"][:200],
                 at_last_accepted=(c.get("attribution") or {}).get("at_last_accepted"))
            for c in main if c["refusal"]
        ]  # fmt: skip
        domain = [r for r in refusals if r["refusal_class"] == "domain"]
        arms = {}
        for label, row in rows.items():
            if row["arm"] in (None, "sodium_free"):
                continue
            arms.setdefault(label.rsplit(" ", 1)[0], []).append(row)
        brackets = {k: bracket([(x["strength"], x["block"]) for x in v]) for k, v in arms.items()}
        sign_brackets = {
            k: bracket([(x["strength"], x["sign_rule_block"]) for x in v])
            for k, v in arms.items()
            if all(x["sign_rule_block"] is not None for x in v)
        }
        within = [
            x["label"] for k, v in arms.items() if k.startswith("disc") for x in v
            if x["block"] and x["s_times_r_gj"] >= FLOOR - 1e-9
        ]  # fmt: skip
        vj = max((x["vj_abs_max_V"] for x in rows.values()), default=None)
        top = max(rows.values(), key=lambda x: x["vj_abs_max_V"], default=None)
        vm = max((x["vm_max_V"] for x in rows.values()), default=None)
        classes = {}
        for label, row in rows.items():
            for name, p in row["peaks"].items():
                if name not in classes or p["peak_V"] > classes[name]["peak_V"]:
                    classes[name] = dict(p, label=label)
        refine = []
        for label, f in fine.items():
            c = next((x for x in reversed(main) if x["label"] == label), None)
            if c is None or label not in rows or f["refusal"] or not f.get("measures"):
                refine.append(dict(label=label, comparable=False, refused=bool(f["refusal"])))
                continue
            a, b = rows[label], case_row(f, cases, geo, planar, floor_C)
            ta, tb = a["total_activation_s"], b["total_activation_s"]
            refine.append(
                dict(
                    label=label,
                    comparable=True,
                    same_never=a["never"] == b["never"],
                    vj_difference_V=abs(a["vj_abs_max_V"] - b["vj_abs_max_V"]),
                    vm_difference_V=abs(a["vm_max_V"] - b["vm_max_V"]),
                    total_activation_relative=None if not ta or not tb else abs(ta - tb) / tb,
                )
            )
        tol = REFINE_TOLERANCES
        out[str(s)] = dict(
            s=s,
            main_dt_s=main_dt,
            cases=len(main),
            J1_no_domain_refusal=not domain,
            refusals=refusals,
            J_vj_abs_max_V=vj,
            J_margin_V=None if vj is None else JUNCTION_LIMIT_V - vj,
            J_margin_flag=vj is not None and JUNCTION_LIMIT_V - vj < FLAG_JUNCTION_MARGIN_V,
            J_top=None if top is None else dict(label=top["label"], **top["vj_top"]),
            J_mapping_max_gap_V=max(
                (x["vj_mapping_max_gap_V"] for x in rows.values()), default=None
            ),
            T_brackets=brackets,
            T_sign_rule_brackets=sign_brackets,
            T2_block_within_floor=bool(within),
            T2_blocking=within,
            passive_floor_C=floor_C,
            rows=rows,
            P_vm_max_V=vm,
            P_margin_V=None if vm is None else CHANNEL_TOP_V - vm,
            P_margin_flag=vm is not None and CHANNEL_TOP_V - vm < FLAG_CHANNEL_MARGIN_V,
            P_classes=classes,
            P_edges_and_corners={k: classes[k] for k in ("corner", "rim", "end") if k in classes},
            R_refinement=refine,
            R_pass=all(
                r["comparable"]
                and r["same_never"]
                and r["vj_difference_V"] <= tol["vj_V"]
                and r["vm_difference_V"] <= tol["vm_V"]
                and (
                    r["total_activation_relative"] is None
                    or r["total_activation_relative"] <= tol["total_activation_relative"]
                )
                for r in refine
            )
            if refine
            else None,  # fmt: skip
            A_refused_on_sheet=bool(domain),
            controls={
                c["label"]: dict(
                    captured=c.get("captured"),
                    stimulus_m_s=c["stimulus_m_s"],
                    stimulus_width_s=c.get("stimulus_width_s"),
                    refusal_class=c.get("refusal_class"),
                    front=(c.get("measures") or {}).get("front"),
                )
                for c in main
                if c["arm"] is None
            },  # fmt: skip
            cost=dict(
                wall_seconds=sum(c["wall_seconds"] for c in main),
                execute_ms_per_step=[c.get("execute_ms_per_step") for c in main],
                host_analysis_ms_per_step=[c.get("host_analysis_ms_per_step") for c in main],
            ),
        )
    return out


def segment_summary(paths):
    """Per-arm block brackets, delays and junction maxima from segment records (chains)."""
    cases = []
    for p in paths:
        with open(p) as stream:
            rec = json.load(stream)
        cases += [dict(c, s=rec["s"]) for c in rec["cases"]]
    main_dt = max(c["dt_s"] for c in cases)
    out = dict(main_dt_s=main_dt, arms={}, refinement=[])
    by = {}
    for c in cases:
        by.setdefault(c["label"], {})[c["dt_s"]] = c
    control = by.get("control", {}).get(main_dt, {}).get("measures", {})
    d0 = control.get("segment_delay_s")
    for label, steps in by.items():
        c = steps.get(main_dt)
        if c is None:
            continue
        m = c.get("measures", {})
        peaks = m.get("peak_V") or []
        over = [i for i, v in enumerate(peaks) if v > 0.0]
        row = dict(
            label=label,
            r_na=c["r_na"],
            r_gj=c["r_gj"],
            s_times_r_gj=c["s"] * c["r_gj"],
            reaches=m.get("reaches_segment"),
            exits=m.get("exits_segment"),
            blocked=bool(m.get("reaches_segment")) and not m.get("exits_segment"),
            last_activated=m.get("last_activated_cell"),
            last_overshoot=max(over) if over else None,
            last_overshoot_peak_V=peaks[max(over)] if over else None,
            delay_over_control=None
            if m.get("segment_delay_s") is None or not d0
            else m["segment_delay_s"] / d0,
            segment_vj_abs_max_V=m.get("segment_vj_abs_max_V"),
            vm_max_V=m.get("vm_max_V"),
            refused=bool(c.get("refusal")),
        )
        out["arms"].setdefault(label.rsplit(" ", 1)[0], []).append(row)
        for dt, f in steps.items():
            if dt == main_dt:
                continue
            fm = f.get("measures", {})
            da, db = m.get("segment_delay_s"), fm.get("segment_delay_s")
            out["refinement"].append(
                dict(
                    label=label,
                    dt_s=dt,
                    same_outcome=(m.get("exits_segment"), m.get("last_activated_cell"))
                    == (fm.get("exits_segment"), fm.get("last_activated_cell")),
                    delay_relative=None if da is None or db is None else abs(da - db) / db,
                    vj_difference_V=None
                    if m.get("segment_vj_abs_max_V") is None
                    else abs(m["segment_vj_abs_max_V"] - fm.get("segment_vj_abs_max_V", 0.0)),
                    refused=bool(f.get("refusal")),
                )
            )
    out["brackets"] = {
        arm: bracket([(x["r_gj"] if arm.startswith("coupling") else x["r_na"], x["blocked"])
                      for x in rows if not x["refused"]])
        for arm, rows in out["arms"].items() if arm != "control"
    }  # fmt: skip
    out["refused"] = [x["label"] for rows in out["arms"].values() for x in rows if x["refused"]]
    return out


def part_report(args):
    root = Path(args.records)
    paths = sorted(root.glob("sheet-*.json"))
    sheets = []
    for p in paths:
        with open(p) as stream:
            sheets.append(json.load(stream))
    report = dict(
        plan=SHEET_PLAN,
        made=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        sheet_records=[str(p) for p in paths],
        sheet=sheet_summary(sheets) if sheets else None,
    )
    for name in ("chain-A", "segment-B"):
        found = sorted(root.glob(f"{name}*/segment.json"))
        if found:
            report[name] = segment_summary(found)
            report[name]["records"] = [str(p) for p in found]
    probe.write_json(Path(args.output), report)
    for s, row in (report["sheet"] or {}).items():
        probe.log(
            f"s {s}: J1 {row['J1_no_domain_refusal']} vj {row['J_vj_abs_max_V']} "
            f"T {row['T_brackets']} sign {row['T_sign_rule_brackets']} "
            f"T2 {row['T2_block_within_floor']} P vm {row['P_vm_max_V']} R {row['R_pass']}"
        )


def select_refinement(args):
    """The refinement picks, from saved records only: print the half-step run's arguments.

    Sheet (--sheet RECORD): per disc arm (combined and coupling-only), the bracketing strengths
    (the sign rule's when the record has upstroke values, else the twin rule's) and the case with
    the largest |Vj|, with those strengths' sodium-free twins. Chain (--chain SEGMENT_JSON): per
    arm, the two bracketing strengths.
    """
    picks = {}
    if args.sheet:
        with open(args.sheet) as stream:
            rec = json.load(stream)
        row = sheet_summary([rec])[str(rec["s"])]
        brackets = row["T_sign_rule_brackets"] or row["T_brackets"]
        for arm in ("combined", "coupling_only"):
            key = f"disc {arm}"
            rows = [x for x in row["rows"].values() if x["label"].rsplit(" ", 1)[0] == key]
            if not rows or key not in brackets:
                continue
            b = brackets[key]
            chosen = {b["largest_r_blocking"], b["smallest_r_passing"]}
            chosen.add(max(rows, key=lambda x: x["vj_abs_max_V"])["strength"])
            picks[arm] = sorted((r for r in chosen if r is not None), reverse=True)
        twins = sorted({r for v in picks.values() for r in v}, reverse=True)
        if twins:
            picks["sodium_free"] = twins
    else:
        summary = segment_summary([args.chain])
        for arm, b in summary["brackets"].items():
            chosen = {b["largest_r_blocking"], b["smallest_r_passing"]}
            picks[arm.replace("-", "_")] = sorted(
                (r for r in chosen if r is not None), reverse=True
            )
    flags = dict(
        combined="--combined",
        coupling_only="--coupling-only",
        sodium_only="--sodium-only",
        sodium_free="--sodium-free",
    )
    words = []
    for arm in ("combined", "sodium_only", "coupling_only", "sodium_free"):
        values = picks.get(arm) or []
        words += [flags[arm], *(f"{r:g}" for r in values)] if values else []
    print(" ".join(words))


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("part", choices=("run", "report", "select", "selfcheck"))
    a.add_argument("--output", required=True)
    a.add_argument("--records", default=None, help="report: the records directory")
    a.add_argument("--name", default="sheet")
    a.add_argument("--nav", type=float, default=1e-6)
    a.add_argument("--kir", type=float, default=1e-8)
    a.add_argument("--cm", type=float, default=0.01)
    a.add_argument("--kv", type=float, default=3e-7)
    a.add_argument("--s", type=float, default=1000.0)
    a.add_argument("--dt", type=float, default=2.5e-6)
    a.add_argument("--end", type=float, default=0.06)
    a.add_argument("--controls", nargs="*", default=[])
    a.add_argument(
        "--ladder",
        nargs="+",
        default=list(DEFAULT_LADDER),
        help="stimulus rungs width_s:m_s in order (each control climbs until launched)",
    )
    a.add_argument("--cluster", choices=("disc", "scattered"), default=None)
    a.add_argument("--seed", type=int, default=0)
    a.add_argument("--combined", type=float, nargs="*", default=[])
    a.add_argument("--coupling-only", type=float, nargs="*", default=[])
    a.add_argument("--sodium-only", type=float, nargs="*", default=[])
    a.add_argument("--sodium-free", type=float, nargs="*", default=[])
    a.add_argument("--stim-from", default=None, help="use a main record's launching rung")
    a.add_argument("--booking", default="cells.heat.trapezoid_nonnegative@1")
    a.add_argument("--sheet", default=None, help="select: a main sheet record")
    a.add_argument("--chain", default=None, help="select: a main chain segment.json")
    args = a.parse_args(argv)
    if args.part == "report" and not args.records:
        a.error("report needs --records")
    if args.part == "select":
        if bool(args.sheet) == bool(args.chain):
            a.error("select needs exactly one of --sheet and --chain")
        return select_refinement(args)
    probe.log(f"sheet {args.part}: driver {__file__}")
    try:
        dict(run=part_run, report=part_report, selfcheck=part_selfcheck)[args.part](args)
    except Exception:
        where = Path(args.output) if args.part != "report" else Path(args.output).parent
        where.mkdir(parents=True, exist_ok=True)
        name = f"{args.name}.FAILURE.txt" if args.part == "run" else f"{args.part}.FAILURE.txt"
        (where / name).write_text(traceback.format_exc())
        raise


if __name__ == "__main__":
    sys.exit(main())
