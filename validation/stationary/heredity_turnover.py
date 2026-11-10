"""Design pre-screen 9: newcomer rules under turnover of a written disc (development, not judged).

Question (heredity design E07-v1, stage B renewal, criterion B1: Jaccard >= 0.8
through full founder turnover): pre-screen 8 (heredity_conversion) found that a
reset H newcomer converts to D in the disc's interior but stays H on its rim,
because the junctions between it and its D neighbours close within 0.05-0.4 s.
Its prediction is that under turnover the rim stays H and the disc erodes. This
tests that prediction with turnover and screens whether another newcomer rule
renews the rim.

Engine model analysed: resolved_pump_tissue@3, unmodified, through
stationary_continuation_analysis@1 (cells.analysis.stationary): stationary
discs by continuation (heredity_conversion.disc_state) and forward runs with
the model's own checked IMEX step through the analysis step map (dt 5 ms, every
step's validity enforced, a refusal ends the run; host ledger checks not run,
no ledgers carried). Worlds are pre-screens 7 and 8's: homogeneous hexagonal
sheets of heredity cells with held baths, E07-v1's voltage-gated junctions
(junction_voltage_relaxation@1, threshold 15 mV, minimum 0.1), coupling scale
s (theta = 1.657 s), the written disc of radius r around the centre cell.

Newcomer (one carrier replaced in a slot): the slot's intracellular amounts and
channel gates are set to the isolated-H template (the sheet's own H initial
values, as in pre-screen 8), everything else is kept except the slot's
incident junction gates, which follow one of three rules:
- open (a, pre-screen 8's rule and design.json's "incident junction gates at
  the open initial value"): each incident gate is set to 0.967, the gate's
  steady state at Vj = 0 (every gate's initial value in an all-H world).
- inherit (b): the incident gates are left at their current values, i.e. those
  of the junctions between the replaced carrier and its neighbours.
- steady (c): after the amount and channel-gate reset, each incident gate is
  set to the gate's steady state, junction_voltage_relaxation@1's target, at
  that junction's voltage Vj read from the model's field at the reset state.
  Vj does not depend on the gate values (checked in each run's checks block:
  the field is evaluated with every gate at 0.967 and at 0.1), so no fixed
  point is involved.
Attribution variants of (b) (stage-1 screens only): which side of the inherited
gate state does the work? A neighbour is D when its membrane voltage is above
the slow U voltage at the moment of replacement (before the reset).
- inherit_to_d (i): inherited gates on junctions to D neighbours, 0.967 to H
  neighbours.
- inherit_to_h (ii): 0.967 on junctions to D neighbours, inherited gates only
  on junctions to H neighbours.
Rules (b), (c), (i) and (ii) depart from design.json's replacement
specification; they are screened, not proposed.

Not varied: the junction gate rate. junction_voltage_relaxation@1's rates
(alpha 1.3/s, beta up to 20/s) are constants of the law; a junction gate
accepts only law, threshold, minimum and initial gate, and no analysis
parameter scales them. The design lists the rate control as open gap G6.

Parts:
- screen (stage 1): a single newcomer placed in the stationary 37-cell disc at
  each of the slots centre (6 disc neighbours), corner rim cell (r, 0) (3),
  mid-side rim cell (r, -1) (4) and first-ring outside cell (r + 1, -1) (2),
  for each rule, at s 0.3 and 0.6; forward to 600 s with pre-screen 8's early
  stop and verdict. The stationary H-defect stability does not depend on the
  rule (a fixed point carries its own gate values); it is read from
  pre-screen 8's sweeps. A rule passes at s when the centre, corner and side
  newcomers all convert with the disc intact and the outside newcomer stays H;
  partial when one of corner and side converts.
- turnover (stage 2): one carrier replaced per event at RATE %/min of all
  sheet cells for 50 min from the stationary disc; event i (0-based) at step
  round((i + 1/2) 60 / (RATE/100 N dt)), times k dt, so the count is exactly
  RATE/100 N x 50 and the last event falls half an interval before the end.
  Orders: oldest (founders ranked by a permutation drawn with ORDER_SEED, ties
  broken by the world seed as design.json P5 states; then newcomers by age, so
  the slots cycle through that permutation) and random (each event's slot
  drawn uniformly from all N with RANDOM_SEED, so some founders survive). The
  targets depend only on (N, rate, order), so rules and scales share them.
  Records every 10 s (taken before an event at the same step): D cells, the
  Jaccard index of the D set against the written disc, founders remaining and
  every slot's state; lineage: every carrier's slot, ring, birth and death,
  state at death or at the end and the first sample at which it was D. A run
  stops early once no cell is D.

Usage: python -m validation.stationary.heredity_turnover --output DIR
       (--screen --scales S[,S] --tag T | --turnover --plan s:rule:rate:order[,...] --tag T
        [--horizon SECONDS] | --summarize)
"""

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

import jax
import numpy as np

jax.config.update("jax_enable_x64", True)

from cells import __version__  # noqa: E402
from cells.processes import junction_gate  # noqa: E402
from validation.stationary import heredity_conversion as hc  # noqa: E402
from validation.stationary import heredity_prescreen as hp  # noqa: E402
from validation.stationary import targets, worlds  # noqa: E402

DT = hc.DT  # 5 ms, admitted by check_steps (pre-screens 7 and 8)
RULES = ("open", "inherit", "steady")  # (a), (b), (c)
ATTRIBUTION_RULES = ("inherit_to_d", "inherit_to_h")  # (i), (ii): halves of (b)
SLOT_NAMES = ("centre", "boundary", "side", "outside")  # boundary = the corner rim cell
SLOT_DISC_NEIGHBOURS = dict(centre=6, boundary=3, side=4, outside=2)
SCREEN_DISC = (6, 3)  # (sheet radius, disc radius): 127-cell sheet, 37-cell disc
HORIZON_S = 3000.0  # 50 min
RECORD_S = 10.0
ORDER_SEED = 1  # founder permutation (oldest-first ties)
RANDOM_SEED = 2  # uniformly random order
PRESCREEN_8 = Path("/mnt/workspaces/Cells/heredity-design-20261108-01/prescreen-08-conversion")
DISCS = {37: (6, 3), 91: (8, 5)}  # disc cells: (sheet radius, disc radius)

_log = hp._log


class Sheet(hp.Case):
    """Pre-screen 7's gated sheet with the written disc, a jitted field readout and step map.

    voltages() is the analysis readout without its Jacobian: the model's field at
    the embedded state (pb.evaluate returns the same membrane voltages, checked
    in each run's checks block).
    """

    def __init__(self, sheet_radius, disc_radius, heterogeneity=None):
        super().__init__(sheet_radius, disc_radius, True, heterogeneity=heterogeneity, dt=DT)
        self.full = self.disc.copy()  # heredity_conversion's name for the written disc
        self.radius = disc_radius
        pb, n = self.pb, len(self.cells)

        def fields(u, theta):
            state, p, control = pb.embed(u, theta)
            f = pb.model.field_values(state, control, p)
            return f.rates.membrane_voltage_V[:n], f.rates.junction_voltage_V, f.converged

        self._fields = jax.jit(fields)
        self.advance = jax.jit(lambda x, s, k: pb.step_residual(x, s, k))
        start = 0
        for b in pb.blocks:
            if b.field == "junction_gate":
                self.gate_range, self.gate_edge = (start, start + len(b.flat)), np.asarray(b.flat)
            start += len(b.flat)
        self.gate_parameters = junction_gate.Parameters(
            np.asarray(pb.p.junction_threshold_voltage), np.asarray(pb.p.junction_minimum)
        )
        self.rings = np.array([worlds.ring(c) for c in self.cells])

    def voltages(self, u, scale):
        return np.asarray(self._fields(u, scale)[0])

    def junction_voltages(self, u, scale):
        return np.asarray(self._fields(u, scale)[1])


def place(case, u, cells, rule, scale):
    """Newcomers in cells under a gate rule (module docstring); returns (u, incident gates)."""
    index = hc.newcomer_index(case, cells)
    lo, hi = case.gate_range
    gates = index[(index >= lo) & (index < hi)]
    own = index[(index < lo) | (index >= hi)]
    anchor = np.asarray(case.pb.anchor)
    if rule in ATTRIBUTION_RULES:
        d = case.voltages(u, scale) > case.threshold  # neighbours' states before the reset
        mine = set(cells)
        ends = np.asarray(case.edges)[case.gate_edge[gates - lo]]
        neighbour_d = np.array([d[b] if a in mine else d[a] for a, b in ends], dtype=bool)
    new = np.array(u, copy=True)
    new[own] = anchor[own]
    if rule == "open":
        new[gates] = anchor[gates]
    elif rule == "inherit_to_d":
        new[gates[~neighbour_d]] = anchor[gates[~neighbour_d]]
    elif rule == "inherit_to_h":
        new[gates[neighbour_d]] = anchor[gates[neighbour_d]]
    elif rule == "steady":
        edge = case.gate_edge[gates - lo]
        vj = case.junction_voltages(new, scale)[edge]
        p = case.gate_parameters
        rate = junction_gate.kinetics(vj, junction_gate.Parameters(p[0][edge], p[1][edge]), xp=np)
        new[gates] = rate.target
    elif rule != "inherit":
        raise ValueError(f"unknown newcomer rule {rule}")
    return new, gates


def checks(case, u, scale):
    """Readout and rule-(c) checks at a state: recorded with every run."""
    lo, hi = case.gate_range
    v_analysis = np.asarray(case.pb.evaluate(u, scale)[3])[: len(case.cells)]
    opened, shut = np.array(u, copy=True), np.array(u, copy=True)
    opened[lo:hi], shut[lo:hi] = 0.967, 0.1
    e = np.asarray(case.edges)[case.gate_edge]
    vm, vj = case.voltages(u, scale), case.junction_voltages(u, scale)[case.gate_edge]
    gate_effect = case.junction_voltages(opened, scale) - case.junction_voltages(shut, scale)
    return dict(
        readout_vs_analysis_max_abs_V=float(np.max(np.abs(vm - v_analysis))),
        vj_minus_sender_receiver_max_abs_V=float(np.max(np.abs(vj - (vm[e[:, 0]] - vm[e[:, 1]])))),
        vj_gate_dependence_max_abs_V=float(np.max(np.abs(gate_effect))),
        field_converged=bool(case._fields(u, scale)[2]),
    )


# ------------------------------------------------------------------ stage 1


def _prescreen8_defects():
    """Pre-screen 8's 37-cell H-defect sweeps: centre and corner (stationary), side (follow-up)."""
    st = json.loads((PRESCREEN_8 / "stationary/stationary.json").read_text())
    fu = json.loads((PRESCREEN_8 / "followup/followup.json").read_text())
    entry = next(e for e in st["discs"] if e["disc_cells"] == 37)
    return dict(
        centre=entry["defects"]["centre"],
        boundary=entry["defects"]["boundary"],
        side=fu["defects"]["37"]["side"],
    )


def defect_at(defect, scale, unit):
    """stable / unstable / absent at scale from a sweep's first stability loss and branch end."""
    if defect is None or defect.get("start"):
        return "absent"
    eb = defect.get("existence_boundary")
    if eb is not None and scale * unit > eb["theta"]:
        return "absent"
    up_to = hc._stable_up_to(defect, unit)
    return "stable" if up_to is None or scale < up_to else "unstable"


def screen(output, scales, tag, rules=RULES, slot_names=SLOT_NAMES):
    """Stage 1: single newcomers in the stationary 37-cell disc, per rule and slot."""
    unit = hp.units()["theta_per_unit_scale"]
    defects = _prescreen8_defects()
    case = Sheet(*SCREEN_DISC)
    where = hc.slots(case, case.radius)
    progress = open(output / f"runs_{tag}.jsonl", "x")
    for s in scales:
        _log(f"stationary 37-cell disc at s {s:g}")
        u_disc = hc.disc_state(case, s, unit)
        if u_disc is None:
            line = dict(kind="screen", scale=s, error="no disc")
            progress.write(json.dumps(line) + "\n")
            progress.flush()
            continue
        check = checks(case, u_disc, s)
        _log(f"  checks {check}")
        for rule in rules:
            for name in slot_names:
                cells, inside = [where[name]], name != "outside"
                others = int(case.full.sum()) - (1 if inside else 0)
                started = time.perf_counter()
                try:
                    u0, gates = place(case, u_disc, cells, rule, s)
                    lo = case.gate_range[0]
                    edges = case.gate_edge[gates - lo]
                    vj0 = case.junction_voltages(u0, s)[edges]
                    rows, u_end = hc.run(case, case.advance, u0, s, cells, inside)
                    res = dict(
                        kind="screen",
                        disc_cells=int(case.full.sum()),
                        sheet_cells=len(case.cells),
                        scale=s,
                        theta=s * unit,
                        rule=rule,
                        slot=name,
                        cells=cells,
                        disc_neighbours=SLOT_DISC_NEIGHBOURS[name],
                        incident=[
                            dict(
                                edge=int(k),
                                neighbour=int(sum(case.edges[k]) - cells[0]),
                                neighbour_in_disc=bool(case.full[sum(case.edges[k]) - cells[0]]),
                                gate_before=float(u_disc[g]),
                                gate_after=float(u0[g]),
                                vj_after_reset_mV=1e3 * float(v),
                            )
                            for k, g, v in zip(edges, gates, vj0, strict=True)
                        ],
                        stationary_defect=defect_at(defects.get(name), s, unit)
                        if inside
                        else "disc (retention window)",
                        **hc.verdict(rows, cells, others, inside),
                        max_abs_V_from_disc_mV=1e3
                        * float(np.max(np.abs(case.voltages(u_end, s) - case.voltages(u_disc, s)))),
                        wall_seconds=time.perf_counter() - started,
                        checks=check,
                        trajectory=rows,
                    )
                except Exception as error:  # Kept as evidence.
                    res = dict(
                        kind="screen",
                        scale=s,
                        rule=rule,
                        slot=name,
                        error=repr(error),
                        tb=traceback.format_exc(),
                    )
                progress.write(json.dumps(targets._json(res)) + "\n")
                progress.flush()
                _log(
                    f"  s {s:g} {rule} {name}: {res.get('outcome', res.get('error'))} "
                    f"latency {res.get('latency_bracket_s')} ({res.get('wall_seconds', 0):.0f} s)"
                )
    progress.close()


def screen_verdict(by_slot):
    """pass / partial / fail for one (rule, s) from its four slot outcomes."""
    ok = {k: by_slot[k].get("outcome") for k in by_slot}
    rim = [ok.get("boundary") == "converts to D", ok.get("side") == "converts to D"]
    rest = ok.get("centre", "converts to D") == "converts to D"
    rest &= ok.get("outside", "stays H") == "stays H"
    if all(rim) and rest:
        return "pass" if set(ok) >= set(SLOT_NAMES) else "pass (slots run: rim only)"
    return "partial" if any(rim) else "fail"


# ------------------------------------------------------------------ stage 2


def schedule(n, rate, order, horizon=HORIZON_S):
    """Event steps and target slots for RATE %/min of n cells over the horizon."""
    per_min = rate / 100.0 * n
    count = int(round(per_min * horizon / 60.0))
    interval = 60.0 / per_min / DT  # steps between events
    steps = np.array([int(round((i + 0.5) * interval)) for i in range(count)], dtype=np.int64)
    total = int(round(horizon / DT))
    if count and (np.any(np.diff(steps) < 1) or steps[0] < 1 or steps[-1] >= total):
        raise ValueError("events must fall on distinct steps inside the horizon")
    if order == "oldest":
        permutation = np.random.default_rng(ORDER_SEED).permutation(n)
        slots = permutation[np.arange(count) % n]
    elif order == "random":
        permutation = None
        slots = np.random.default_rng(RANDOM_SEED).integers(0, n, size=count)
    else:
        raise ValueError(f"unknown order {order}")
    return dict(
        rate_percent_per_min=rate,
        order=order,
        sheet_cells=n,
        count=count,
        interval_s=interval * DT,
        total_steps=total,
        steps=steps,
        slots=np.asarray(slots, dtype=np.int64),
        founder_permutation=permutation,
        seed=ORDER_SEED if order == "oldest" else RANDOM_SEED,
    )


def _jaccard(d, written):
    union = np.sum(d | written)
    return float(np.sum(d & written) / union) if union else 1.0


def turnover(case, u_disc, scale, rule, rate, order, unit, horizon=HORIZON_S):
    """One turnover run from the stationary disc; returns the result record."""
    n, written = len(case.cells), case.full
    plan = schedule(n, rate, order, horizon)
    event_at = {int(k): i for i, k in enumerate(plan["steps"])}
    every = int(round(RECORD_S / DT))
    record_steps = set(range(0, plan["total_steps"] + 1, every))
    marks = sorted(record_steps | set(event_at))
    carriers = [
        dict(
            carrier=i,
            slot=i,
            ring=int(case.rings[i]),
            written=bool(written[i]),
            founder=True,
            birth_s=0.0,
            death_s=None,
            end_state=None,
            end_voltage_mV=None,
            first_d_s=None,
        )
        for i in range(n)
    ]
    current = list(range(n))
    u, k_now, records, stop, applied = np.array(u_disc, copy=True), 0, [], None, 0
    started = time.perf_counter()
    for k in marks:
        if k > k_now:
            step_rate = np.asarray(case.advance(u, scale, k - k_now))
            if not np.all(np.isfinite(step_rate)):
                stop = dict(time_s=k * DT, reason="a step was refused (NaN)")
                break
            u, k_now = u + (k - k_now) * DT * step_rate, k
        t = k * DT
        v = case.voltages(u, scale)
        d = v > case.threshold
        for i in np.flatnonzero(d):
            c = carriers[current[i]]
            if c["first_d_s"] is None:
                c["first_d_s"] = t
        if k in record_steps:
            founders = np.array([carriers[c]["founder"] for c in current])
            records.append(
                dict(
                    time_s=t,
                    d_total=int(d.sum()),
                    d_written=int(np.sum(d & written)),
                    d_outside=int(np.sum(d & ~written)),
                    jaccard=_jaccard(d, written),
                    events_applied=applied,
                    founders_remaining=int(founders.sum()),
                    founders_remaining_in_disc=int(np.sum(founders & written)),
                    written_voltage_range_mV=[
                        1e3 * float(v[written].min()),
                        1e3 * float(v[written].max()),
                    ],
                    d_slots="".join("1" if x else "0" for x in d),
                )
            )
            if k > 0 and not d.any():
                stop = dict(time_s=t, reason="no D cell left (the uniform H sheet)")
                break
            if len(records) % 30 == 1:
                last = records[-1]
                _log(
                    f"    t {t:6.0f} s: D {last['d_total']} (written {last['d_written']}), "
                    f"J {last['jaccard']:.3f}, founders {last['founders_remaining']}, "
                    f"{time.perf_counter() - started:.0f} s wall"
                )
        if k in event_at:
            slot = int(plan["slots"][event_at[k]])
            old = carriers[current[slot]]
            old.update(death_s=t, end_state="D" if d[slot] else "H", end_voltage_mV=1e3 * v[slot])
            u, _ = place(case, u, [slot], rule, scale)
            applied += 1
            current[slot] = len(carriers)
            carriers.append(
                dict(
                    carrier=len(carriers),
                    slot=slot,
                    ring=int(case.rings[slot]),
                    written=bool(written[slot]),
                    founder=False,
                    birth_s=t,
                    death_s=None,
                    end_state=None,
                    end_voltage_mV=None,
                    first_d_s=None,
                )
            )
    end_t = k_now * DT
    v = case.voltages(u, scale)
    d = v > case.threshold
    for i, c in enumerate(current):
        carriers[c].update(end_state="D" if d[i] else "H", end_voltage_mV=1e3 * v[i])
    wall = time.perf_counter() - started
    plan_out = {k: v for k, v in plan.items() if k not in ("steps", "slots")}
    plan_out.update(event_times_s=[float(s * DT) for s in plan["steps"]], event_slots=plan["slots"])
    return dict(
        kind="turnover",
        disc_cells=int(written.sum()),
        sheet_cells=n,
        scale=scale,
        theta=scale * unit,
        rule=rule,
        rate_percent_per_min=rate,
        order=order,
        horizon_s=horizon,
        dt_s=DT,
        record_every_s=RECORD_S,
        stopped=stop,
        end_time_s=end_t,
        events_applied=applied,
        events_planned=plan["count"],
        wall_seconds=wall,
        wall_per_simulated_s=wall / max(end_t, DT),
        summary=turnover_summary(records, carriers, written, plan, case.radius),
        records=records,
        lineage=carriers,
        schedule=plan_out,
    )


def turnover_summary(records, carriers, written, plan, radius):
    """Jaccard and D count over time, founder turnover and newcomer conversion by ring."""
    times = [r["time_s"] for r in records]
    jac = [r["jaccard"] for r in records]
    below = next((r["time_s"] for r in records if r["jaccard"] < 0.8), None)
    last_founder = None
    if plan["order"] == "oldest" and plan["count"] >= plan["sheet_cells"]:
        last_founder = float(plan["steps"][plan["sheet_cells"] - 1] * DT)
    elif plan["order"] == "random":
        seen = set()
        for k, slot in zip(plan["steps"], plan["slots"], strict=True):
            seen.add(int(slot))
            if len(seen) == plan["sheet_cells"]:
                last_founder = float(k * DT)
                break
    after = next(
        (r for r in records if last_founder is not None and r["time_s"] > last_founder), None
    )
    by_ring = {}
    for c in carriers:
        if c["founder"]:
            continue
        g = by_ring.setdefault(c["ring"], dict(newcomers=0, end_d=0, ever_d=0, latency_s=[]))
        g["newcomers"] += 1
        g["end_d"] += c["end_state"] == "D"
        if c["first_d_s"] is not None:
            g["ever_d"] += 1
            g["latency_s"].append(c["first_d_s"] - c["birth_s"])
    for g in by_ring.values():
        g["end_d_fraction"] = g["end_d"] / g["newcomers"]
        g["ever_d_fraction"] = g["ever_d"] / g["newcomers"]
        lat = g.pop("latency_s")
        g["first_d_sample_after_birth_s_median"] = float(np.median(lat)) if lat else None
    disc_new = [c for c in carriers if not c["founder"] and c["written"]]
    out_new = [c for c in carriers if not c["founder"] and not c["written"]]

    def at(t):
        r = next((r for r in records if r["time_s"] >= t), None)
        return None if r is None else dict(jaccard=r["jaccard"], d_total=r["d_total"])

    return dict(
        jaccard_end=jac[-1] if jac else None,
        d_total_end=records[-1]["d_total"] if records else None,
        d_outside_end=records[-1]["d_outside"] if records else None,
        jaccard_min=min(jac) if jac else None,
        first_record_below_0p8_s=below,
        last_founder_replaced_s=last_founder,
        at_first_record_after_last_founder=None
        if after is None
        else dict(time_s=after["time_s"], jaccard=after["jaccard"], d_total=after["d_total"]),
        founders_remaining_end=records[-1]["founders_remaining"] if records else None,
        founders_remaining_in_disc_end=records[-1]["founders_remaining_in_disc"]
        if records
        else None,
        jaccard_at_minutes={f"{m}": at(60.0 * m) for m in (5, 10, 20, 30, 40, 50)},
        newcomers_in_disc=len(disc_new),
        newcomers_in_disc_end_d_fraction=float(np.mean([c["end_state"] == "D" for c in disc_new]))
        if disc_new
        else None,
        newcomers_outside_ever_d=int(sum(c["first_d_s"] is not None for c in out_new)),
        newcomers_by_ring={str(k): by_ring[k] for k in sorted(by_ring)},
        disc_ring_max=radius,
        record_times_s=[times[0], times[-1]] if times else None,
    )


def parse_plan(text):
    runs = []
    for item in text.split(","):
        s, rule, rate, order = item.split(":")
        if rule not in RULES + ATTRIBUTION_RULES or order not in ("oldest", "random"):
            raise ValueError(f"bad plan item {item}")
        runs.append((float(s), rule, float(rate), order))
    return runs


def turnover_runs(output, plan, tag, horizon=HORIZON_S, disc_cells=37):
    """Stage 2: the planned turnover runs, one line in runs_TAG.jsonl as each ends."""
    unit = hp.units()["theta_per_unit_scale"]
    case = Sheet(*DISCS[disc_cells])
    states = {}
    progress = open(output / f"runs_{tag}.jsonl", "x")
    for s, rule, rate, order in plan:
        _log(f"turnover s {s:g} rule {rule} {rate:g} %/min {order} ({horizon:g} s)")
        try:
            if s not in states:
                states[s] = hc.disc_state(case, s, unit)
                if states[s] is not None:
                    states[(s, "checks")] = checks(case, states[s], s)
                    _log(f"  checks {states[(s, 'checks')]}")
            if states[s] is None:
                res = dict(
                    kind="turnover",
                    scale=s,
                    rule=rule,
                    rate_percent_per_min=rate,
                    order=order,
                    error="no stationary disc",
                )
            else:
                res = turnover(case, states[s], s, rule, rate, order, unit, horizon)
                res["checks"] = states[(s, "checks")]
                sm = res["summary"]
                _log(
                    f"  done: J end {sm['jaccard_end']:.3f}, D end {sm['d_total_end']}, "
                    f"J<0.8 from {sm['first_record_below_0p8_s']} s, stop {res['stopped']}, "
                    f"{res['wall_seconds']:.0f} s wall ({res['wall_per_simulated_s']:.3f}/s)"
                )
        except Exception as error:  # Kept as evidence.
            res = dict(
                kind="turnover",
                scale=s,
                rule=rule,
                rate_percent_per_min=rate,
                order=order,
                error=repr(error),
                tb=traceback.format_exc(),
            )
            _log(f"  failed: {error!r}")
        progress.write(json.dumps(targets._json(res)) + "\n")
        progress.flush()
    progress.close()


# ------------------------------------------------------------------ summary


def _load_runs(directory):
    runs = []
    for path in sorted(Path(directory).glob("runs_*.jsonl")):
        for line in path.read_text().splitlines():
            if line.strip():
                runs.append(dict(json.loads(line), source=path.name))
    return runs


def summarize(directory):
    """results.json and table.md from every runs_*.jsonl in the directory."""
    directory = Path(directory)
    runs = _load_runs(directory)
    screens = [r for r in runs if r.get("kind") == "screen"]
    turns = [r for r in runs if r.get("kind") == "turnover"]
    lines, out = (
        [],
        dict(
            kind="cells.heredity_design_prescreen@9_summary",
            scope="Design input only (development analysis, not judged); no ledgers carried.",
            cells_version=__version__,
            runs=len(runs),
            errors=[
                {k: r.get(k) for k in ("kind", "scale", "rule", "slot", "error", "source")}
                for r in runs
                if "error" in r
            ],
        ),
    )
    if screens:
        grouped = {}
        for r in screens:
            if "outcome" in r:
                grouped.setdefault((r["scale"], r["rule"]), {})[r["slot"]] = r
        verdicts = []
        lines += [
            "| s | rule | centre | corner | side | outside | stage-1 verdict |",
            "|---|---|---|---|---|---|---|",
        ]
        for (s, rule), by in sorted(grouped.items()):
            v = screen_verdict(by)

            def cell(x):
                if x is None:
                    return "-"
                lat = x["latency_bracket_s"]
                lat = "" if lat is None else f" ({lat[0]:g}-{lat[1]:g} s)"
                return f"{hc.SHORT.get(x['outcome'], x['outcome'])}{lat} [{x['stationary_defect']}]"

            lines.append(
                f"| {s:g} | {rule} | "
                + " | ".join(cell(by.get(k)) for k in SLOT_NAMES)
                + f" | {v} |"
            )
            verdicts.append(
                dict(
                    scale=s,
                    rule=rule,
                    verdict=v,
                    slots={
                        k: {
                            kk: by[k].get(kk)
                            for kk in (
                                "outcome",
                                "latency_bracket_s",
                                "stationary_defect",
                                "last_time_s",
                            )
                        }
                        for k in by
                    },
                    initial_incident_gates={
                        k: [round(i["gate_after"], 4) for i in by[k]["incident"]] for k in by
                    },
                )
            )
        out["screen"] = verdicts
        lines += [
            "",
            "Bracketed: the stationary H-defect at that s "
            "(pre-screen 8's sweeps; rule-independent).",
            "",
        ]

    def head(r):
        return (
            f"| {r['disc_cells']} | {r['scale']:g} | {r['rule']} | "
            f"{r['rate_percent_per_min']:g} | {r['order']} |"
        )

    if turns:
        out["turnover"] = [
            {
                k: v
                for k, v in r.items()
                if k not in ("records", "lineage", "schedule", "trajectory")
            }
            for r in turns
        ]
        lines += [
            "| disc | s | rule | %/min | order | J 10 / 20 / 30 / 40 / 50 min | J min | "
            "J<0.8 from s | D end | founders left | disc newcomers D at end | stop |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for r in sorted(
            turns,
            key=lambda r: (
                r.get("disc_cells", 0),
                r["scale"],
                r["rule"],
                r["rate_percent_per_min"],
                r["order"],
            ),
        ):
            if "error" in r:
                lines.append(
                    f"| - | {r['scale']:g} | {r['rule']} | {r['rate_percent_per_min']:g} "
                    f"| {r['order']} | {r['error']} | | | | | | |"
                )
                continue
            sm = r["summary"]
            js = " / ".join(
                "-"
                if sm["jaccard_at_minutes"][m] is None
                else f"{sm['jaccard_at_minutes'][m]['jaccard']:.2f}"
                for m in ("10", "20", "30", "40", "50")
            )
            frac = sm["newcomers_in_disc_end_d_fraction"]
            stop = (
                "-"
                if not r["stopped"]
                else f"{r['stopped']['reason']} at {r['stopped']['time_s']:g} s"
            )
            lines.append(
                f"{head(r)} {js} | {sm['jaccard_min']:.2f} | {sm['first_record_below_0p8_s']} | "
                f"{sm['d_total_end']} | {sm['founders_remaining_end']} | "
                f"{'-' if frac is None else f'{frac:.2f}'} ({sm['newcomers_in_disc']}) | {stop} |"
            )
        lines += [
            "",
            "| disc | s | rule | %/min | order | "
            "disc newcomers ending D by ring (ring: D/newcomers) | outside newcomers ever D |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in turns:
            if "error" in r:
                continue
            sm = r["summary"]
            rings = ", ".join(
                f"{k}: {g['end_d']}/{g['newcomers']}"
                for k, g in sm["newcomers_by_ring"].items()
                if int(k) <= sm["disc_ring_max"]
            )
            lines.append(f"{head(r)} {rings} | {sm['newcomers_outside_ever_d']} |")
    with open(directory / "results.json", "x") as stream:
        json.dump(targets._json(out), stream, indent=1)
    with open(directory / "table.md", "x") as stream:
        stream.write("\n".join(lines) + "\n")
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--screen", action="store_true", help="stage 1 single newcomers")
    parser.add_argument("--scales", default="0.3,0.6")
    parser.add_argument("--rules", default=",".join(RULES))
    parser.add_argument("--slots", default=",".join(SLOT_NAMES))
    parser.add_argument("--turnover", action="store_true", help="stage 2 turnover runs")
    parser.add_argument("--plan", help="s:rule:rate:order[,...]")
    parser.add_argument("--disc", type=int, default=37, choices=sorted(DISCS))
    parser.add_argument("--horizon", type=float, default=HORIZON_S)
    parser.add_argument("--tag", default="main")
    parser.add_argument("--summarize", action="store_true", help="results.json and table.md")
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)  # results are never overwritten
    if args.screen:
        rules, names = tuple(args.rules.split(",")), tuple(args.slots.split(","))
        if any(r not in RULES + ATTRIBUTION_RULES for r in rules) or any(
            k not in SLOT_NAMES for k in names
        ):
            parser.error("unknown rule or slot")
        screen(args.output, [float(s) for s in args.scales.split(",")], args.tag, rules, names)
        _log("screen done")
    elif args.turnover:
        turnover_runs(args.output, parse_plan(args.plan), args.tag, args.horizon, args.disc)
        _log("turnover done")
    elif args.summarize:
        summarize(args.output)
    else:
        parser.error("give --screen, --turnover or --summarize")
    return 0


if __name__ == "__main__":
    sys.exit(main())
