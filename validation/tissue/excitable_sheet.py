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
  stimulus, in a combined (r_Na = r_gj = r), coupling-only (r_gj = r) or sodium-only (r_Na = r)
  arm. r_gj holds every junction incident to a perturbed cell, so s * r_gj is the coupling of
  each such junction relative to s = 1.

Measures per case: activation (first -30 mV crossing after the stimulus onset) and overshoot per
cell; block (cells never activated); each junction's largest |Vj| over the run, by class
(cluster boundary, internal, outside); the peaks of lightly loaded cells (corners, rim, the last
cells before a block, collision sites) against +60 mV.

`report` reads saved records only (no engine) and evaluates the PLAN's criteria.
Usage:
  python -B -P excitable_sheet.py run --output DIR --name NAME --nav .. --kir .. --cm .. --kv ..
      --s 1000 --dt 2.5e-6 [--controls planar corner two-sided] [--cluster disc]
      [--combined R ..] [--coupling-only R ..] [--sodium-only R ..] [--stim-from RECORD]
  python -B -P excitable_sheet.py report --records DIR --output FILE
"""

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

import numpy as np

from validation.stationary import worlds
from validation.tissue import excitable_probe as probe

RADIUS = 6
CLUSTER_SIZE = 19
FLOOR = 20.0  # D170 ruling 3: the provisional floor s * r_gj >= 20.
JUNCTION_LIMIT_V = 0.120
CHANNEL_TOP_V = 0.060
ACTIVATION_V = -0.030
STIM_ON_S, STIM_WIDTH_S = 2e-3, 1e-3
QUIET_S, MIN_AFTER_STIM_S = 0.010, 0.012
FLAG_JUNCTION_MARGIN_V, FLAG_CHANNEL_MARGIN_V = 0.005, 0.002
REFINE_TOLERANCES = dict(vj_V=5e-4, vm_V=5e-4, total_activation_relative=0.02)

SHEET_PLAN = dict(
    status="M1 development runs (D170): criteria fixed in PLAN.md before any run; not judged",
    world="127-cell held-bath hexagon, gates pinned open, trapezoid_nonnegative@1",
    floor="s * r_gj >= 20 at every perturbed junction (provisional, D170 ruling 3)",
    J="no refusal at s * r_gj >= 20; largest |Vj| by junction class against 120 mV",
    T="block bracket per arm on the grid (largest r that blocks, smallest r that does not)",
    P="largest peak per lightly loaded class (corner, rim, before block, collision, end) "
    "against +60 mV",
    R="half-step repeats: same non-activated cells, |Vj| and Vm maxima within 0.5 mV, total "
    "activation time within 2 %",
)


# ----------------------------------------------------------------------------- geometry


def geometry(radius=RADIUS):
    cells, edges = worlds.hexagon(radius)
    n = len(cells)
    nbrs = [[] for _ in range(n)]
    for k, (a, b) in enumerate(edges):
        nbrs[a].append((b, k))
        nbrs[b].append((a, k))
    ring = [worlds.ring(c) for c in cells]
    degree = [len(x) for x in nbrs]
    kind = [
        "corner" if degree[i] == 3 else "rim" if ring[i] == radius else "interior" for i in range(n)
    ]
    return dict(
        cells=cells,
        edges=edges,
        nbrs=nbrs,
        ring=ring,
        degree=degree,
        kind=kind,
        index={c: i for i, c in enumerate(cells)},
    )


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
    return dict(combined=(r, r), coupling_only=(1.0, r), sodium_only=(r, 1.0))[arm]


# ----------------------------------------------------------------------------- measures


def best(cells, peak, geo):
    if not cells:
        return None
    i = max(cells, key=lambda c: peak[c])
    return dict(
        cell=int(i),
        peak_V=float(peak[i]),
        kind=geo["kind"][i],
        ring=int(geo["ring"][i]),
        axial=list(geo["cells"][i]),
        count=len(cells),
    )


def sheet_measures(t, vm, vj, geo, *, stim, cluster, on_s):
    """Activation, block, junction maxima by class and lightly loaded peaks (host, numpy)."""
    n = vm.shape[1]
    start = int(np.searchsorted(t, on_s))
    acts = [probe.crossings(t, vm[:, i], ACTIVATION_V, start=start) for i in range(n)]
    first = [a[0] if a else None for a in acts]
    peak = vm.max(axis=0)
    in_cluster, in_stim = set(cluster), set(stim)
    edges, nbrs, kind = geo["edges"], geo["nbrs"], geo["kind"]
    absvj = np.abs(vj)
    jmax = absvj.max(axis=0)
    jarg = absvj.argmax(axis=0)

    def junction_row(k):
        a, b = edges[k]
        at = int(jarg[k])
        return dict(
            junction=int(k),
            cells=[int(a), int(b)],
            vj_abs_max_V=float(jmax[k]),
            time_s=float(t[at]),
            vm_at_V=[float(vm[at, a]), float(vm[at, b])],
            kinds=[kind[a], kind[b]],
            rings=[int(geo["ring"][a]), int(geo["ring"][b])],
            in_cluster=[a in in_cluster, b in in_cluster],
            activation_s=[first[a], first[b]],
        )

    classes = {}
    for k, (a, b) in enumerate(edges):
        ca, cb = a in in_cluster, b in in_cluster
        label = "boundary" if ca != cb else "internal" if ca else "outside"
        if label not in classes or jmax[k] > classes[label]["vj_abs_max_V"]:
            classes[label] = junction_row(k)
    activated = [i for i in range(n) if first[i] is not None]
    never = [i for i in range(n) if first[i] is None]
    free = [i for i in range(n) if i not in in_stim]
    before_block = [
        i for i in activated if i not in in_stim and any(first[b] is None for b, _ in nbrs[i])
    ]
    local_max = [
        i
        for i in activated
        if i not in in_stim
        and all(first[b] is not None and first[b] <= first[i] for b, _ in nbrs[i])
    ]
    far = [i for i in range(n) if geo["cells"][i][0] == RADIUS]
    far_times = [first[i] for i in far if first[i] is not None]
    top = int(np.argmax(jmax))
    return dict(
        activation_s=first,
        activations_per_cell=[len(a) for a in acts],
        max_activations=max(len(a) for a in acts),
        peak_V=peak.tolist(),
        non_activated=never,
        block=bool(never),
        cluster_non_activated=[i for i in cluster if first[i] is None],
        cluster_overshoot=[i for i in cluster if peak[i] > 0.0],
        total_activation_s=(max(first[i] for i in activated) - on_s) if activated else None,
        far_column_mean_activation_s=float(np.mean(far_times)) if far_times else None,
        far_column_activated=len(far_times),
        vj_abs_max_V=float(jmax.max()),
        vj_top=junction_row(top),
        junction_classes=classes,
        vj_per_junction_V=jmax.tolist(),
        vm_max_V=float(vm.max()),
        vm_max_cell=int(np.argmax(peak)),
        vm_min_V=float(vm.min()),
        peaks=dict(
            corner=best([i for i in free if kind[i] == "corner"], peak, geo),
            rim=best([i for i in free if kind[i] == "rim"], peak, geo),
            interior=best([i for i in free if kind[i] == "interior"], peak, geo),
            before_block=best(before_block, peak, geo),
            collision=best([i for i in local_max if kind[i] == "interior"], peak, geo),
            end=best([i for i in local_max if kind[i] != "interior"], peak, geo),
            cluster=best(list(cluster), peak, geo),
            stimulated=best(list(stim), peak, geo),
        ),
    )


# ----------------------------------------------------------------------------- runs


def sheet_case(args, geo, *, label, stimulus, cluster, arm, r, dt, m_s):
    stim = stimulus_cells(geo, stimulus)
    r_na, r_gj = (1.0, 1.0) if arm is None else arm_values(arm, r)
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
        cluster=list(cluster),
        arm=arm,
        r=r,
        r_na=r_na,
        r_gj=r_gj,
        s=args.s,
        dt_s=dt,
        s_times_r_gj=args.s * r_gj,
    )
    try:
        rec["static_bounds"] = probe.static_bounds(raw)
    except probe.ConfigError as error:
        rec["static_bounds"] = dict(refusal=str(error))
    if len(r_run["times"]) > 2:
        t, vm, vj = (np.asarray(r_run[k]) for k in ("times", "vm", "vj"))
        rec["measures"] = sheet_measures(t, vm, vj, geo, stim=stim, cluster=cluster, on_s=on * dt)
    m = rec.get("measures", {})
    probe.log(
        f"sheet {label} s {args.s:g} dt {dt:g}: block {m.get('block')} "
        f"never {len(m.get('non_activated', []))} vj {m.get('vj_abs_max_V')} "
        f"vm {m.get('vm_max_V')} total {m.get('total_activation_s')} steps {rec['steps']} "
        f"wall {rec['wall_seconds']:.1f} refusal "
        f"{rec['refusal'] and rec['refusal']['message'][:90]}"
    )
    return rec


def captured(rec):
    m = rec.get("measures") or {}
    return bool(not rec["refusal"] and m and not m["non_activated"])


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
                arm=None, r=None, dt=args.dt, m_s=m_s,
            )  # fmt: skip
            rec["capture_attempt"] = attempt
            out["cases"].append(rec)
            write(path, out)
            if captured(rec) or rec["refusal"]:
                break
            m_s *= 2.0
        rec["captured"] = captured(rec)
        if stimulus == "planar":
            planar_m_s = m_s
    out["planar_stimulus_m_s"] = planar_m_s if planar_m_s is not None else nominal
    planar = [c for c in out["cases"] if c["label"] == "control planar"]
    if planar and not planar[-1]["captured"]:  # PLAN: no perturbed cases without capture.
        out["skipped"] = "the planar control did not capture at the largest stimulus"
    elif args.cluster:
        cluster = cluster_cells(geo, args.cluster, args.seed)
        out["cluster"] = dict(kind=args.cluster, cells=cluster, seed=args.seed)
        for arm, values in (
            ("combined", args.combined),
            ("coupling_only", args.coupling_only),
            ("sodium_only", args.sodium_only),
        ):
            for r in values or []:
                rec = sheet_case(
                    args, geo, label=f"{args.cluster} {arm} {r:g}", stimulus="planar",
                    cluster=cluster, arm=arm, r=r, dt=args.dt, m_s=out["planar_stimulus_m_s"],
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


def sheet_summary(records):
    """Criteria J, T, P and R per option (s, main dt) from the sheet records."""
    options = {}
    for rec in records:
        for c in rec["cases"]:
            options.setdefault(rec["s"], []).append(c)
    out = {}
    for s, cases in sorted(options.items()):
        main_dt = max(c["dt_s"] for c in cases)
        main = [c for c in cases if c["dt_s"] == main_dt]
        fine = {c["label"]: c for c in cases if c["dt_s"] < main_dt}
        inside_floor = [c for c in main if c["s_times_r_gj"] >= FLOOR - 1e-9]
        accepted = [c for c in main if not c["refusal"] and c.get("measures")]
        refusals = [
            dict(label=c["label"], message=c["refusal"]["message"][:200],
                 attribution=c.get("attribution", {}).get("at_last_accepted"))
            for c in inside_floor if c["refusal"]
        ]  # fmt: skip
        vj = max((c["measures"]["vj_abs_max_V"] for c in accepted), default=None)
        vm = max((c["measures"]["vm_max_V"] for c in accepted), default=None)
        top_vj = max(accepted, key=lambda c: c["measures"]["vj_abs_max_V"], default=None)
        classes = {}
        for c in accepted:
            for name, row in c["measures"]["peaks"].items():
                if row and (name not in classes or row["peak_V"] > classes[name]["peak_V"]):
                    classes[name] = dict(row, label=c["label"])
        controls = {c["stimulus"]: c for c in main if c["arm"] is None}
        planar = controls.get("planar", {}).get("measures")
        arms = {}
        for c in main:
            if c["arm"] is None or not c.get("measures"):
                continue
            m = c["measures"]
            row = dict(
                label=c["label"],
                r=c["r"],
                s_times_r_gj=c["s_times_r_gj"],
                block=m["block"],
                non_activated=len(m["non_activated"]),
                cluster_non_activated=len(m["cluster_non_activated"]),
                cluster_overshoot=len(m["cluster_overshoot"]),
                max_activations=m["max_activations"],
                vj_abs_max_V=m["vj_abs_max_V"],
                vj_top_class=next(
                    (k for k, v in m["junction_classes"].items()
                     if v["junction"] == m["vj_top"]["junction"]), None),
                vm_max_V=m["vm_max_V"],
                total_activation_s=m["total_activation_s"],
                total_over_control=None
                if not planar or not m["total_activation_s"]
                else m["total_activation_s"] / planar["total_activation_s"],
                far_column_delay_s=None
                if not planar or m["far_column_mean_activation_s"] is None
                else m["far_column_mean_activation_s"] - planar["far_column_mean_activation_s"],
            )  # fmt: skip
            arms.setdefault(c["label"].rsplit(" ", 1)[0], []).append(row)
        brackets = {
            key: bracket([(row["r"], row["block"]) for row in rows]) for key, rows in arms.items()
        }
        within = [  # PLAN T2: a disc case that blocks with s * r_gj >= 20.
            row for key, rows in arms.items() if key.startswith("disc") for row in rows
            if row["block"] and row["s_times_r_gj"] >= FLOOR - 1e-9
        ]  # fmt: skip
        refine = []
        for label, f in fine.items():
            c = next((x for x in main if x["label"] == label), None)
            if c is None or not c.get("measures") or not f.get("measures"):
                refine.append(dict(label=label, comparable=False))
                continue
            a, b = c["measures"], f["measures"]
            ta, tb = a["total_activation_s"], b["total_activation_s"]
            refine.append(
                dict(
                    label=label,
                    comparable=True,
                    same_non_activated=a["non_activated"] == b["non_activated"],
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
            J_no_refusal_within_floor=not refusals,
            refusals_within_floor=refusals,
            refusals_below_floor=[
                c["label"] for c in main if c["refusal"] and c not in inside_floor
            ],
            J_vj_abs_max_V=vj,
            J_margin_V=None if vj is None else JUNCTION_LIMIT_V - vj,
            J_margin_flag=vj is not None and JUNCTION_LIMIT_V - vj < FLAG_JUNCTION_MARGIN_V,
            J_top=None
            if top_vj is None
            else dict(label=top_vj["label"], **top_vj["measures"]["vj_top"]),
            T_brackets=brackets,
            T_block_within_floor=bool(within),
            T_blocking_within_floor=[row["label"] for row in within],
            arms=arms,
            P_vm_max_V=vm,
            P_margin_V=None if vm is None else CHANNEL_TOP_V - vm,
            P_margin_flag=vm is not None and CHANNEL_TOP_V - vm < FLAG_CHANNEL_MARGIN_V,
            P_classes=classes,
            controls={
                k: dict(
                    captured=v.get("captured"),
                    stimulus_m_s=v["stimulus_m_s"],
                    total_activation_s=(v.get("measures") or {}).get("total_activation_s"),
                    vm_max_V=(v.get("measures") or {}).get("vm_max_V"),
                    vj_abs_max_V=(v.get("measures") or {}).get("vj_abs_max_V"),
                    max_activations=(v.get("measures") or {}).get("max_activations"),
                )
                for k, v in controls.items()
            },
            R_refinement=refine,
            R_pass=all(
                r["comparable"]
                and r["same_non_activated"]
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
            A_refused_on_sheet=bool(refusals),
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
        c = steps[main_dt]
        m = c.get("measures", {})
        arm = label.rsplit(" ", 1)[0]
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
            delay_over_control=None
            if m.get("segment_delay_s") is None or not d0
            else m["segment_delay_s"] / d0,
            segment_vj_abs_max_V=m.get("segment_vj_abs_max_V"),
            vm_max_V=m.get("vm_max_V"),
            refused=bool(c.get("refusal")),
        )
        out["arms"].setdefault(arm, []).append(row)
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
                )
            )
    out["brackets"] = {
        arm: bracket([(row["r_gj"] if arm.startswith("coupling") else row["r_na"], row["blocked"])
                      for row in rows if arm != "control"])
        for arm, rows in out["arms"].items() if arm != "control"
    }  # fmt: skip
    out["refused"] = [
        row["label"] for rows in out["arms"].values() for row in rows if row["refused"]
    ]
    return out


def part_report(args):
    root = Path(args.records)
    sheets = []
    for p in sorted(root.glob("sheet-*.json")):
        with open(p) as stream:
            sheets.append(json.load(stream))
    report = dict(
        plan=SHEET_PLAN,
        made=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        sheet_records=[str(p) for p in sorted(root.glob("sheet-*.json"))],
        sheet=sheet_summary(sheets) if sheets else None,
    )
    for name in ("chain-A", "segment-B"):
        paths = sorted(root.glob(f"{name}*/segment.json"))
        if paths:
            report[name] = segment_summary(paths)
            report[name]["records"] = [str(p) for p in paths]
    probe.write_json(Path(args.output), report)
    for s, row in (report["sheet"] or {}).items():
        probe.log(
            f"s {s}: J {row['J_no_refusal_within_floor']} vj {row['J_vj_abs_max_V']} "
            f"T {row['T_brackets']} block-within-floor {row['T_block_within_floor']} "
            f"P vm {row['P_vm_max_V']} R {row['R_pass']}"
        )


def select_refinement(args):
    """PLAN's refinement rule, from saved records only: print the half-step run's arguments.

    Sheet (--sheet RECORD): per disc arm, the bracketing strengths and the case with the
    largest |Vj|. Chain (--chain SEGMENT_JSON): per arm, the two bracketing strengths.
    """
    picks = {}
    if args.sheet:
        with open(args.sheet) as stream:
            rec = json.load(stream)
        row = sheet_summary([rec])[str(rec["s"])]
        for arm in ("combined", "coupling_only"):
            rows = row["arms"].get(f"disc {arm}", [])
            if not rows:
                continue
            b = row["T_brackets"][f"disc {arm}"]
            chosen = {b["largest_r_blocking"], b["smallest_r_passing"]}
            chosen.add(max(rows, key=lambda x: x["vj_abs_max_V"])["r"])
            picks[arm] = sorted((r for r in chosen if r is not None), reverse=True)
    else:
        summary = segment_summary([args.chain])
        for arm, b in summary["brackets"].items():
            chosen = {b["largest_r_blocking"], b["smallest_r_passing"]}
            picks[arm.replace("-", "_")] = sorted(
                (r for r in chosen if r is not None), reverse=True
            )
    flags = dict(
        combined="--combined", coupling_only="--coupling-only", sodium_only="--sodium-only"
    )
    words = []
    for arm in ("combined", "sodium_only", "coupling_only"):
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
        Path(args.output if args.part == "run" else Path(args.output).parent).mkdir(
            parents=True, exist_ok=True
        )
        failure = (
            Path(args.output) / f"{args.name}.FAILURE.txt"
            if args.part == "run"
            else Path(f"{args.output}.FAILURE.txt")
        )
        failure.write_text(traceback.format_exc())
        raise


if __name__ == "__main__":
    sys.exit(main())
