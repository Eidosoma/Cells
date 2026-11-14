"""Track E M1's first development runs on the 127-cell sheet (D170), and their report.

The held-bath hexagon (validation/stationary/worlds.hexagon(6): 127 cells, 342 junctions) of the
generic cell (candidate A, or B as given) on resolved_pump_tissue@3, built by excitable_probe's
definition: gates pinned open, trapezoid_nonnegative@1, D147's declared field solver. It is a
black-box driver: the engine's own Vm and Vj at every accepted step, its host checks, and any
refusal with the probe's attribution. The criteria are in the M1 evidence folder's PLAN.md,
written before the runs.

`run` cases:
- controls under three stimuli: planar (the q = -6 column, 7 cells), corner (corner (-6, 6) and
  its three neighbours) and two-sided (the q = -6 and q = 6 columns);
- a compact disc (ring <= 2 about the centre, 19 cells) or a scattered set (19 cells drawn with
  numpy's default_rng(seed) from the cells outside the planar stimulus), under the planar
  stimulus, in a combined (r_Na = r_gj = r), coupling-only (r_gj = r), sodium-only (r_Na = r) or
  sodium-free (r_Na = 0, r_gj = r) arm. r_gj holds every junction incident to a perturbed cell,
  so s * r_gj is each such junction's coupling relative to s = 1. The sodium-free arm is each
  r_gj's passive twin.

Measures per case (host, numpy): each cell's first -30 mV crossing after the stimulus onset,
peak and its time, and end voltage; each junction's largest |Vj| over the run, by class (cluster
boundary, internal, outside); the gap between the engine's |Vj| and |Vm_a - Vm_b| per edge.

`report` reads saved records only (no engine) and evaluates the PLAN's criteria. A perturbed cell
counts as activated when its peak is above 0 mV and at least 10 mV above its sodium-free twin's
(same cells, same r_gj); an unperturbed cell when it crosses -30 mV. `select` prints PLAN's
refinement picks from a main record.
Usage:
  python -B -P excitable_sheet.py run --output DIR --name NAME --nav .. --kir .. --cm .. --kv ..
      --s 1000 --dt 2.5e-6 [--controls planar corner two-sided] [--cluster disc]
      [--combined R ..] [--coupling-only R ..] [--sodium-only R ..] [--sodium-free R ..]
      [--stim-from RECORD]
  python -B -P excitable_sheet.py report --records DIR --output FILE
  python -B -P excitable_sheet.py select --output - (--sheet RECORD | --chain SEGMENT_JSON)
"""

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

import numpy as np

from cells.core.specs import parse_spec
from cells.core.state import initialise
from cells.core.surface_pump_v3_spec import control_values as v3_controls
from cells.models import surface_pump_v3 as v3
from validation.stationary import worlds
from validation.tissue import excitable_probe as probe

RADIUS = 6
CLUSTER_SIZE = 19
FLOOR = 20.0  # D170 ruling 3: the provisional floor s * r_gj >= 20.
JUNCTION_LIMIT_V = 0.120
CHANNEL_TOP_V = 0.060
ACTIVATION_V = -0.030
TWIN_MARGIN_V = 0.010
STIM_ON_S, STIM_WIDTH_S = 2e-3, 1e-3
QUIET_S, MIN_AFTER_STIM_S = 0.010, 0.012
FLAG_JUNCTION_MARGIN_V, FLAG_CHANNEL_MARGIN_V = 0.005, 0.002
REFINE_TOLERANCES = dict(vj_V=5e-4, vm_V=5e-4, total_activation_relative=0.02)
ARMS = ("combined", "coupling_only", "sodium_only", "sodium_free")

SHEET_PLAN = dict(
    status="M1 development runs (D170): criteria fixed in PLAN.md before any run; not judged",
    world="127-cell held-bath hexagon, gates pinned open, trapezoid_nonnegative@1",
    floor="s * r_gj >= 20 at every perturbed junction (provisional, D170 ruling 3)",
    activation="unperturbed: first -30 mV crossing; perturbed: peak > 0 mV and >= 10 mV above "
    "the sodium-free twin's peak",
    J="J1: no domain-classified refusal; J2: largest |Vj| by junction class against 120 mV",
    T="block bracket per arm (largest r that blocks, smallest r that does not), refused cases "
    "excluded; T2: a disc case blocks at s * r_gj >= 20",
    P="largest peak per lightly loaded class (corner, rim, before block, collision, end) "
    "against +60 mV",
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


# ----------------------------------------------------------------------------- measures


def sheet_measures(t, vm, vj, geo, *, stim, on_s, stim_end_s):
    """Per-cell activation, peaks and end voltages; per-junction maxima (host, numpy)."""
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
    )  # fmt: skip


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


def sheet_case(args, geo, *, label, stimulus, cluster, arm, strength, dt, m_s):
    stim = stimulus_cells(geo, stimulus)
    r_na, r_gj = (1.0, 1.0) if arm is None else arm_values(arm, strength)
    held = set(cluster)
    cell_nav = {i: r_na for i in held} if r_na != 1.0 else None
    junctions = (
        {k: r_gj for k, (a, b) in enumerate(geo["edges"]) if a in held or b in held}
        if r_gj != 1.0
        else None
    )
    on, width = int(round(STIM_ON_S / dt)), int(round(STIM_WIDTH_S / dt))
    raw = probe.definition(
        len(geo["cells"]),
        dt=dt,
        end_time=args.end,
        kv_m_s=args.kv,
        s=args.s,
        booking=args.booking,
        stim=dict(cells=stim, pulses=[(on, on + width)], m_s=m_s),
        cell_nav=cell_nav,
        junction_availability=junctions,
        edges=geo["edges"],
    )
    stim_end = (on + width) * dt

    def stop(o):  # Every cell below -30 mV for 10 ms, at least 12 ms after the stimulus.
        t = o["times"]
        if not t or t[-1] < stim_end + MIN_AFTER_STIM_S:
            return False
        vm = np.asarray(o["vm"])
        recent = np.asarray(t) > t[-1] - QUIET_S
        return bool(np.all(vm[recent] < ACTIVATION_V))

    r_run = probe.execute(raw, stop=stop)
    rec = probe.record(
        raw,
        r_run,
        label=label,
        stimulus=stimulus,
        stimulus_cells=stim,
        stimulus_m_s=m_s,
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
    except probe.ConfigError as error:
        rec["static_bounds"] = dict(refusal=str(error))
    if len(r_run["times"]) > 2:
        t, vm, vj = (np.asarray(r_run[k]) for k in ("times", "vm", "vj"))
        rec["measures"] = sheet_measures(
            t, vm, vj, geo, stim=stim, on_s=on * dt, stim_end_s=stim_end
        )
    m = rec.get("measures", {})
    probe.log(
        f"sheet {label} s {args.s:g} dt {dt:g}: crossing-never {len(m.get('crossing_never', []))} "
        f"vj {m.get('vj_abs_max_V')} gap {m.get('vj_mapping_max_gap_V')} vm {m.get('vm_max_V')} "
        f"steps {rec['steps']} wall {rec['wall_seconds']:.1f} refusal "
        f"{rec['refusal_class']} {rec['refusal'] and rec['refusal']['message'][:90]}"
    )  # fmt: skip
    return rec


def captured(rec):
    m = rec.get("measures") or {}
    return bool(not rec["refusal"] and m and not m["crossing_never"])


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
    nominal = args.stim_m_s * probe.stimulus_scale()
    planar_m_s = None
    if args.stim_from:  # Refinements and later arms start from the main record's stimulus.
        with open(args.stim_from) as stream:
            nominal = planar_m_s = json.load(stream)["planar_stimulus_m_s"]
    out["stimulus_start_m_s"] = nominal
    for stimulus in args.controls:
        m_s = nominal
        for attempt in range(3):  # PLAN: double the stimulus until the control captures.
            rec = sheet_case(
                args, geo, label=f"control {stimulus}", stimulus=stimulus, cluster=[],
                arm=None, strength=None, dt=args.dt, m_s=m_s,
            )  # fmt: skip
            rec["capture_attempt"] = attempt
            rec["captured"] = captured(rec)
            out["cases"].append(rec)
            if rec["captured"] or rec["refusal"] or attempt == 2:
                break
            rec["label"] = f"control {stimulus} not captured at {m_s:g}"
            write(path, out)
            m_s *= 2.0
        write(path, out)
        if stimulus == "planar":
            planar_m_s = m_s if rec["captured"] else None
    out["planar_stimulus_m_s"] = planar_m_s if planar_m_s is not None else nominal
    planar = [c for c in out["cases"] if c["label"] == "control planar"]
    if planar and not planar[-1]["captured"]:  # PLAN: no perturbed cases without capture.
        out["skipped"] = "the planar control did not capture at the largest stimulus"
    elif args.cluster:
        cluster = cluster_cells(geo, args.cluster, args.seed)
        out["cluster"] = dict(kind=args.cluster, cells=cluster, seed=args.seed)
        for arm in ARMS:
            for r in getattr(args, arm) or []:
                rec = sheet_case(
                    args, geo, label=f"{args.cluster} {arm} {r:g}", stimulus="planar",
                    cluster=cluster, arm=arm, strength=r, dt=args.dt,
                    m_s=out["planar_stimulus_m_s"],
                )  # fmt: skip
                out["cases"].append(rec)
                write(path, out)
    out["peak_rss_mb"] = probe.peak_rss_mb()
    write(path, out)


def write(path, out):
    path.parent.mkdir(parents=True, exist_ok=True)
    probe.write_json(path, out)


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
    """Per-cell activation by the PLAN's rule, and the cells counted."""
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


def lightly_loaded(case, active, geo):
    """The PLAN's peak classes, stimulated cells excluded; perturbed neighbours are ignored in
    the collision and end tests."""
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


def case_row(case, cases, geo, planar):
    m = case["measures"]
    active, twin = activation(case, cases, geo)
    held = set(case["cluster"])
    never = [i for i, a in enumerate(active) if not a]
    perturbed_active = [i for i in held if active[i]]
    first = m["activation_s"]
    times = [first[i] for i, a in enumerate(active) if a and first[i] is not None]
    on = STIM_ON_S
    total = (max(times) - on) if times else None
    p_total = planar and planar.get("total")
    far_delay = None
    if planar and m["far_column_mean_activation_s"] is not None and planar.get("far") is not None:
        far_delay = m["far_column_mean_activation_s"] - planar["far"]
    return dict(
        label=case["label"],
        arm=case["arm"],
        strength=case["strength"],
        s_times_r_gj=case["s_times_r_gj"],
        twin=twin,
        block=bool(never),
        never=never,
        perturbed_activated=len(perturbed_active),
        perturbed=len(held),
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
        stimulus_stage_ratio=case.get("stimulus_stage_ratio"),
    )


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
        planar_case = next((c for c in reversed(good) if c["label"] == "control planar"), None)
        planar = None
        if planar_case:
            row = case_row(planar_case, cases, geo, None)
            planar = dict(
                total=row["total_activation_s"],
                far=planar_case["measures"]["far_column_mean_activation_s"],
            )
        rows = {c["label"]: case_row(c, cases, geo, planar) for c in good}
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
            a, b = rows[label], case_row(f, cases, geo, planar)
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
            T2_block_within_floor=bool(within),
            T2_blocking=within,
            rows=rows,
            P_vm_max_V=vm,
            P_margin_V=None if vm is None else CHANNEL_TOP_V - vm,
            P_margin_flag=vm is not None and CHANNEL_TOP_V - vm < FLAG_CHANNEL_MARGIN_V,
            P_classes=classes,
            R_refinement=refine,
            R_pass=all(
                r["comparable"] and r["same_never"] and r["vj_difference_V"] <= tol["vj_V"]
                and r["vm_difference_V"] <= tol["vm_V"]
                and (r["total_activation_relative"] is None
                     or r["total_activation_relative"] <= tol["total_activation_relative"])
                for r in refine
            ) if refine else None,
            A_refused_on_sheet=bool(domain),
            controls={
                c["label"]: dict(captured=c.get("captured"), stimulus_m_s=c["stimulus_m_s"],
                                 refusal_class=c.get("refusal_class"))
                for c in main if c["arm"] is None
            },
            cost=dict(
                wall_seconds=sum(c["wall_seconds"] for c in main),
                execute_ms_per_step=[c.get("execute_ms_per_step") for c in main],
                host_analysis_ms_per_step=[c.get("host_analysis_ms_per_step") for c in main],
            ),
        )  # fmt: skip
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
            f"T {row['T_brackets']} T2 {row['T2_block_within_floor']} "
            f"P vm {row['P_vm_max_V']} R {row['R_pass']}"
        )


def select_refinement(args):
    """PLAN's refinement rule, from saved records only: print the half-step run's arguments.

    Sheet (--sheet RECORD): per disc arm of item 1, the bracketing strengths and the case with
    the largest |Vj|. Chain (--chain SEGMENT_JSON): per arm, the two bracketing strengths.
    """
    picks = {}
    if args.sheet:
        with open(args.sheet) as stream:
            rec = json.load(stream)
        row = sheet_summary([rec])[str(rec["s"])]
        for arm in ("combined", "coupling_only"):
            key = f"disc {arm}"
            rows = [x for x in row["rows"].values() if x["label"].rsplit(" ", 1)[0] == key]
            if not rows:
                continue
            b = row["T_brackets"][key]
            chosen = {b["largest_r_blocking"], b["smallest_r_passing"]}
            chosen.add(max(rows, key=lambda x: x["vj_abs_max_V"])["strength"])
            picks[arm] = sorted((r for r in chosen if r is not None), reverse=True)
        # The twins of the picks, so that the half-step cases have same-step twins.
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
    a.add_argument("part", choices=("run", "report", "select"))
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
    a.add_argument("--cluster", choices=("disc", "scattered"), default=None)
    a.add_argument("--seed", type=int, default=0)
    a.add_argument("--combined", type=float, nargs="*", default=[])
    a.add_argument("--coupling-only", type=float, nargs="*", default=[])
    a.add_argument("--sodium-only", type=float, nargs="*", default=[])
    a.add_argument("--sodium-free", type=float, nargs="*", default=[])
    a.add_argument("--stim-m-s", type=float, default=1e-6, help="nominal; scaled by c_m/0.05")
    a.add_argument("--stim-from", default=None, help="take the planar stimulus from a record")
    a.add_argument("--booking", default="trapezoid_nonnegative@1")
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
        (part_run if args.part == "run" else part_report)(args)
    except Exception:
        where = Path(args.output) if args.part == "run" else Path(args.output).parent
        where.mkdir(parents=True, exist_ok=True)
        name = f"{args.name}.FAILURE.txt" if args.part == "run" else "report.FAILURE.txt"
        (where / name).write_text(traceback.format_exc())
        raise


if __name__ == "__main__":
    sys.exit(main())
