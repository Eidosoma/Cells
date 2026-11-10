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
import dataclasses
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


def place(case, u, cells, rule, scale, template=None):
    """Newcomers in cells under a gate rule (module docstring); returns (u, incident gates).

    template: (positions, values) of the newcomer's own amounts and channel gates in
    place of the sheet's H initial values (Redraw: its own isolated H state).
    """
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
    if template is not None:
        positions, values = template
        if set(np.asarray(positions).tolist()) != set(own.tolist()):
            raise ValueError("a newcomer template must cover exactly the slot's own entries")
        new[positions] = values
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


def turnover(case, u_disc, scale, rule, rate, order, unit, horizon=HORIZON_S, redraw=None):
    """One turnover run from the stationary disc; returns the result record.

    redraw: a Redraw (heterogeneous worlds, D133), or None (newcomers take the slot's
    parameters and the sheet's H initial values).
    """
    n, written = len(case.cells), case.full
    advance = case.advance if redraw is None else redraw.advance
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
            step_rate = np.asarray(advance(u, scale, k - k_now))
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
            drawn = None if redraw is None else redraw.birth(slot)
            u, _ = place(case, u, [slot], rule, scale, None if drawn is None else drawn[:2])
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
                    **({} if drawn is None else drawn[2]),
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
        heterogeneity=case.label.get("heterogeneity"),
        newcomers=None if redraw is None else redraw.describe(),
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
        jaccard_at_minutes={
            f"{m}": at(60.0 * m)
            for m in (5, 10, 20, 30, 40, 50, *range(60, int(plan["total_steps"] * DT / 60) + 1, 10))
        },
        newcomers_in_disc=len(disc_new),
        newcomers_in_disc_end_d_fraction=float(np.mean([c["end_state"] == "D" for c in disc_new]))
        if disc_new
        else None,
        newcomers_outside_ever_d=int(sum(c["first_d_s"] is not None for c in out_new)),
        newcomers_by_ring={str(k): by_ring[k] for k in sorted(by_ring)},
        disc_ring_max=radius,
        record_times_s=[times[0], times[-1]] if times else None,
        after_each_turnover=_after_each_turnover(records, plan),
    )


def _after_each_turnover(records, plan):
    """Oldest-first: the first record after every slot has been replaced m times."""
    if plan["order"] != "oldest":
        return None
    n, out = plan["sheet_cells"], []
    for m in range(1, plan["count"] // n + 1):
        last = float(plan["steps"][m * n - 1] * DT)
        r = next((r for r in records if r["time_s"] > last), None)
        out.append(
            dict(turnover=m, last_replaced_s=last)
            | ({} if r is None else dict(time_s=r["time_s"], jaccard=r["jaccard"], d=r["d_total"]))
        )
    return out


# ------------------------------------------------------------------ mechanism

MECHANISM_SCALE = 0.6
MECHANISM_WAITS = (20.0, 200.0, 1500.0)  # s after the last neighbour replacement
MECHANISM_LOG = (0.0, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0, 200.0, 500.0, 1000.0, 1500.0)
MECHANISM_FINE = (0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0, 20.0, 30.0)
MECHANISM_SETTLE = 10.0  # s between neighbour replacements


def composition(case, u, cells, scale):
    """Per cell: Vm (mV), intracellular concentrations (mM) and channel gates at u."""
    pb = case.pb
    if not hasattr(case, "label_index"):
        case.label_index = {label: i for i, label in enumerate(pb.labels())}
    ref, vol = np.asarray(pb.p.amount_reference), np.asarray(pb.p.volume)
    species, v = list(pb.spec.model.species_ids), case.voltages(u, scale)
    rows = []
    for i in cells:
        row = dict(cell=int(i), V_mV=1e3 * float(v[i]))
        for k, sp in enumerate(species):
            pos = case.label_index.get(f"{sp}@cell_{i}")
            if pos is not None:
                row[f"{sp}_mM"] = float(ref[k, i] / vol[i] + u[pos])
        for label in (f"gate{g}@{c}_{i}" for c in ("nav", "kir") for g in (0, 1)):
            row[label.split("@")[0] + "_" + label.split("@")[1].split("_")[0]] = float(
                u[case.label_index[label]]
            )
        rows.append(row)
    return rows


def _forward(case, u, scale, seconds):
    k = int(round(seconds / DT))
    if k == 0:
        return u
    rate = np.asarray(case.advance(u, scale, k))
    if not np.all(np.isfinite(rate)):
        raise RuntimeError("a step was refused (NaN)")
    return u + k * DT * rate


def _corner_birth(case, u, scale, corner, rule):
    """A corner newcomer placed at u: its voltage and gates over 30 s, and the outcome."""
    lo = case.gate_range[0]
    u0, gates = place(case, u, [corner], rule, scale)
    edges = np.asarray(case.edges)[case.gate_edge[gates - lo]]
    others = [int(b if a == corner else a) for a, b in edges]
    d0 = case.voltages(u, scale) > case.threshold
    rows, t, x = [], 0.0, u0
    for target in (0.0, *MECHANISM_FINE):
        x, t = _forward(case, x, scale, target - t), target
        v = case.voltages(x, scale)
        rows.append(
            dict(
                time_s=t,
                V_mV=1e3 * float(v[corner]),
                gates_to_d=[float(x[g]) for g, j in zip(gates, others, strict=True) if d0[j]],
                gates_to_h=[float(x[g]) for g, j in zip(gates, others, strict=True) if not d0[j]],
                neighbour_V_mV=[1e3 * float(v[j]) for j in others],
            )
        )
    d = case.voltages(x, scale) > case.threshold
    intact = bool(
        np.all(
            d[case.full & (np.arange(len(d)) != corner)]
            == d0[case.full & (np.arange(len(d)) != corner)]
        )
    )
    return dict(
        converted=bool(d[corner]),
        others_unchanged=intact,
        newcomer=composition(case, x, [corner], scale)[0],
        trajectory=rows,
    )


def mechanism(output, rule="inherit"):
    """Are converted newcomers weaker D neighbours than founders, and why?

    In the stationary 37-cell disc at MECHANISM_SCALE, a corner newcomer (3 disc
    neighbours) is placed (a) next to founders, (b) after its ring-2 neighbour was
    replaced by a newcomer that converted, (c) after all three disc neighbours were
    (one at a time, MECHANISM_SETTLE apart, each checked D). (b) and (c) branch at
    MECHANISM_WAITS after the last neighbour replacement; (c) also records the
    converted newcomers' composition at MECHANISM_LOG against the founders' (the
    stationary D) and the H template. The stationary disc's leading eigenvalues
    give the slowest relaxation rates.
    """
    unit = hp.units()["theta_per_unit_scale"]
    s = MECHANISM_SCALE
    case = Sheet(*SCREEN_DISC)
    corner = hc.slots(case, case.radius)["boundary"]
    neighbours = sorted(
        int(b if a == corner else a)
        for a, b in case.edges
        if corner in (a, b) and case.full[b if a == corner else a]
    )
    ring2 = [j for j in neighbours if case.rings[j] == case.radius - 1]
    sides = [j for j in neighbours if case.rings[j] == case.radius]
    _log(f"mechanism: corner {corner}, disc neighbours {neighbours} (ring 2 {ring2})")
    u_disc = hc.disc_state(case, s, unit)
    if u_disc is None:
        raise RuntimeError("no stationary disc")
    out = dict(
        kind="cells.heredity_design_prescreen@9_mechanism",
        scope="Design input only (development analysis, not judged); no ledgers carried.",
        scale=s,
        rule=rule,
        corner=corner,
        disc_neighbours=neighbours,
        founder_d=composition(case, u_disc, neighbours, s),
        h_template=composition(case, np.asarray(case.pb.anchor), [corner], s)[0],
        stationary_spectrum=hp.classify(case, u_disc, s),
        checks=checks(case, u_disc, s),
        cases=[],
    )
    _log(f"  founders: {out['founder_d']}")
    started = time.perf_counter()
    case_a = dict(name="founders", replaced=[], births=[])
    case_a["births"].append(
        dict(
            wait_s=None, neighbours=out["founder_d"], **_corner_birth(case, u_disc, s, corner, rule)
        )
    )
    out["cases"].append(case_a)
    _log(f"  founders: corner converted {case_a['births'][0]['converted']}")
    for name, sequence, waits in (
        ("one converted neighbour", ring2, MECHANISM_WAITS[:2]),
        ("three converted neighbours", ring2 + sides, MECHANISM_WAITS),
    ):
        u, entry = np.array(u_disc, copy=True), dict(name=name, replaced=sequence, births=[])
        for j in sequence:
            u, _ = place(case, u, [j], rule, s)
            u = _forward(case, u, s, MECHANISM_SETTLE)
            if not case.voltages(u, s)[j] > case.threshold:
                entry["error"] = f"neighbour {j} did not convert"
        entry["relaxation"], t = [], 0.0
        for target in sorted(set(MECHANISM_LOG) | set(waits)):
            if target > waits[-1]:
                break
            u, t = _forward(case, u, s, target - t), target
            if target in MECHANISM_LOG:
                entry["relaxation"].append(dict(time_s=t, cells=composition(case, u, sequence, s)))
            if target in waits:
                entry["births"].append(
                    dict(
                        wait_s=t,
                        neighbours=composition(case, u, neighbours, s),
                        **_corner_birth(case, u, s, corner, rule),
                    )
                )
                _log(f"  {name}, wait {t:g} s: corner converted {entry['births'][-1]['converted']}")
        out["cases"].append(entry)
    out["wall_seconds"] = time.perf_counter() - started
    with open(output / "mechanism.json", "x") as stream:
        json.dump(targets._json(out), stream, indent=1)
    with open(output / "mechanism_table.md", "x") as stream:
        stream.write(mechanism_table(out) + "\n")
    return out


def mechanism_table(out):
    def fmt(row):
        return (
            f"{row['V_mV']:.1f} mV, Na {row['Na_mM']:.2f}, K {row['K_mM']:.2f}, "
            f"M {row['M_mM']:.2f} mM"
        )

    lines = [
        f"Stationary disc at s {out['scale']:g}; corner {out['corner']}, "
        f"neighbours {out['disc_neighbours']}; rule {out['rule']}.",
        "",
        f"H template: {fmt(out['h_template'])}",
        "Founder D neighbours: " + "; ".join(fmt(r) for r in out["founder_d"]),
        "Leading eigenvalues of the stationary disc (1/s): "
        + ", ".join(
            f"{a:.3g}{b:+.3g}i" for a, b in out["stationary_spectrum"]["leading_eigenvalues_per_s"]
        ),
        "",
        "| case | wait s | corner converts | others unchanged | D neighbours at birth |",
        "|---|---|---|---|---|",
    ]
    for c in out["cases"]:
        for b in c["births"]:
            nb = "founders" if b["wait_s"] is None else "; ".join(fmt(r) for r in b["neighbours"])
            lines.append(
                f"| {c['name']} | {b['wait_s'] if b['wait_s'] is not None else '-'} | "
                f"{b['converted']} | {b['others_unchanged']} | {nb} |"
            )
    lines += ["", "| case | t after last replacement s | converted newcomers |", "|---|---|---|"]
    for c in out["cases"]:
        for r in c.get("relaxation", []):
            lines.append(
                f"| {c['name']} | {r['time_s']:g} | " + "; ".join(fmt(x) for x in r["cells"]) + " |"
            )
    return "\n".join(lines)


# ------------------------------------------------------------------ stage 3

HETEROGENEITY = dict(seed=1, cell_cv=0.10, junction_cv=0.20)  # pre-screen 8's CV10 world
NEWCOMER_SEED = 11
FACTOR_KEYS = ("nav", "kir", "na_leak", "pump")
LEAVES = ("channel_permeability", "membrane_permeability", "pump_capacity")


def _with(pb, leaves):
    """The problem with these per-cell layout leaves (traced inside jit; analysis plumbing)."""
    return dataclasses.replace(
        pb, p=pb.p._replace(**dict(zip(LEAVES, leaves, strict=True))), _cache={}
    )


def _factor_index(pb, cells):
    """Per cell: (NaV1.2 channel, Kir2.1 channel, Na row, membrane) layout indices.

    worlds.e07_sheet_definition applies the factors to channels nav_i and kir_i, membrane
    i's Na permeability and membrane i's pump capacity.
    """
    m = pb.spec.model
    channels = [c.id for c in m.channels]
    na = list(m.species_ids).index("Na")
    return [(channels.index(f"nav_{i}"), channels.index(f"kir_{i}"), na, i) for i in range(cells)]


def _rescale(leaves, index, old, new):
    cp, mp, pc = (np.array(x, copy=True) for x in leaves)
    nav, kir, na, membrane = index
    cp[nav] *= new["nav"] / old["nav"]
    cp[kir] *= new["kir"] / old["kir"]
    mp[na, membrane] *= new["na_leak"] / old["na_leak"]
    pc[membrane] *= new["pump"] / old["pump"]
    return cp, mp, pc


class SingleCell:
    """The isolated heredity cell (own held bath) with per-cell factors as arguments."""

    def __init__(self):
        from cells.analysis import stationary as sa
        from cells.core.specs import parse_spec

        raw = worlds.e07_sheet_definition([hc._states()["H"]], [], gated=True, dt=DT)
        self.pb = pb = sa.problem(parse_spec(worlds.ionic_background(raw)), mode="slow")
        self.leaves = tuple(np.asarray(getattr(pb.p, k)) for k in LEAVES)
        self.index = _factor_index(pb, 1)[0]
        self.red, self.sa = pb.reduction(), sa

        def residual(u, leaves):
            return _with(pb, leaves).rhs_residual(u, None)

        self._r = jax.jit(residual)
        self._j = jax.jit(jax.jacfwd(residual))

    def h_state(self, factors):
        """Newton from the declared H state to the cell's own H steady state."""
        ones = dict.fromkeys(FACTOR_KEYS, 1.0)
        leaves = _rescale(self.leaves, self.index, ones, factors)
        red, u = self.red, self.red.project(self.pb.anchor)
        for _ in range(40):
            r, jac = np.asarray(self._r(u, leaves)), np.asarray(self._j(u, leaves))
            step = red.full(-np.linalg.solve(red.operator(jac), red.vector(r)))
            u = u + step
            if self.sa._norm(step) <= self.sa.NEWTON_TOLERANCE:
                break
        else:
            raise RuntimeError(f"isolated H Newton did not converge for {factors}")
        v = float(np.asarray(self.pb.evaluate(u)[3])[0])
        rate = float(np.max(np.abs(np.asarray(self._r(u, leaves)))))
        return u, v, rate


class Redraw:
    """D133 newcomers: each draws its own per-cell factors (lognormal, mean one, the world's
    per-cell CV, numpy default generator with NEWCOMER_SEED, one draw per newcomer in event
    order, keys in FACTOR_KEYS order); its template is its own isolated H steady state
    (SingleCell, Newton from the declared H). Junction factors stay with the slot's junctions.
    The step map runs with the current per-cell layout leaves as arguments.
    """

    def __init__(self, case, founder_factors, cv, seed=NEWCOMER_SEED):
        self.case, self.cv, self.seed = case, cv, seed
        self.factors = [dict(f) for f in founder_factors]
        self.rng = np.random.default_rng(seed)
        pb = case.pb
        self.leaves = tuple(np.asarray(getattr(pb.p, k)) for k in LEAVES)
        self.index = _factor_index(pb, len(case.cells))
        self.single = SingleCell()
        self._advance = jax.jit(lambda u, s, k, leaves: _with(pb, leaves).step_residual(u, s, k))
        sheet = {label: i for i, label in enumerate(pb.labels())}
        own = [i for i, label in enumerate(self.single.pb.labels()) if label.endswith("_0")]
        self.labels = [self.single.pb.labels()[i] for i in own]
        self.own, self.sheet = np.asarray(own), sheet
        self.count = 0

    def advance(self, u, scale, k):
        return self._advance(u, scale, k, self.leaves)

    def positions(self, slot):
        return np.array([self.sheet[label[:-2] + f"_{slot}"] for label in self.labels])

    def birth(self, slot):
        """New factors for slot; returns (positions, template values, lineage fields)."""
        f = {k: float(worlds.lognormal_factors(1, self.cv, self.rng)[0]) for k in FACTOR_KEYS}
        u1, v1, rate = self.single.h_state(f)
        self.leaves = _rescale(self.leaves, self.index[slot], self.factors[slot], f)
        self.factors[slot] = f
        self.count += 1
        lineage = dict(factors=f, template_voltage_mV=1e3 * v1, template_max_rate=rate)
        return self.positions(slot), u1[self.own], lineage

    def describe(self):
        return dict(
            rule="each newcomer draws its own per-cell factors (D133); template = its own "
            "isolated H steady state; junction factors stay with the slot",
            factor_keys=FACTOR_KEYS,
            cell_cv=self.cv,
            seed=self.seed,
            draws=self.count,
        )


def parse_plan(text):
    runs = []
    for item in text.split(","):
        s, rule, rate, order = item.split(":")
        if rule not in RULES + ATTRIBUTION_RULES or order not in ("oldest", "random"):
            raise ValueError(f"bad plan item {item}")
        runs.append((float(s), rule, float(rate), order))
    return runs


def turnover_runs(output, plan, tag, horizon=HORIZON_S, disc_cells=37, heterogeneous=False):
    """Stages 2-3: the planned turnover runs, one line in runs_TAG.jsonl as each ends.

    heterogeneous: HETEROGENEITY's world, newcomers drawing their own factors (Redraw);
    each run starts a fresh Redraw, so every run sees the same newcomer draws.
    """
    unit = hp.units()["theta_per_unit_scale"]
    hetero = HETEROGENEITY if heterogeneous else None
    case = Sheet(*DISCS[disc_cells], heterogeneity=hetero)
    founders = None
    if hetero:
        founders = worlds.e07_heterogeneity(len(case.cells), len(case.edges), **hetero)[0]
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
                redraw = None if not hetero else Redraw(case, founders, hetero["cell_cv"])
                res = turnover(case, states[s], s, rule, rate, order, unit, horizon, redraw)
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


def rim_births(run):
    """Rim newcomers by their neighbourhood at birth and whether they were ever D.

    Rim = the written disc's outer ring; corner = 3 disc neighbours, side = 4. D
    neighbours are read from the last record at or before the birth (records every
    RECORD_S, so a neighbour replaced within that interval can be misread); founder or
    newcomer is the neighbour slot's carrier at the birth (lineage, exact).
    """
    cells, edges = worlds.hexagon(
        next(s for s, r in DISCS.values() if 3 * r * (r + 1) + 1 == run["disc_cells"])
    )
    radius = DISCS[run["disc_cells"]][1]
    neighbours = {i: set() for i in range(len(cells))}
    for a, b in edges:
        neighbours[a].add(b)
        neighbours[b].add(a)
    history = {}
    for c in run["lineage"]:
        history.setdefault(c["slot"], []).append(c)
    last_founder = run["summary"]["last_founder_replaced_s"]
    times = [r["time_s"] for r in run["records"]]
    counts = {}
    for c in run["lineage"]:
        if c["founder"] or worlds.ring(cells[c["slot"]]) != radius:
            continue
        k = int(np.searchsorted(times, c["birth_s"], side="right")) - 1
        d = run["records"][k]["d_slots"]
        d_old = d_new = 0
        for j in neighbours[c["slot"]]:
            if d[j] == "1":
                holder = max(
                    (x for x in history[j] if x["birth_s"] <= c["birth_s"]),
                    key=lambda x: x["birth_s"],
                )
                d_old += holder["founder"]
                d_new += not holder["founder"]
        inside = sum(worlds.ring(cells[j]) <= radius for j in neighbours[c["slot"]])
        key = (
            "corner" if inside == 3 else "side",
            d_old + d_new,
            d_new,
            last_founder is not None and c["birth_s"] <= last_founder,
            "D" if c["first_d_s"] is not None else "H",
        )
        counts[key] = counts.get(key, 0) + 1
    return [
        dict(
            slot_kind=k[0],
            d_neighbours=k[1],
            newcomer_d_neighbours=k[2],
            within_first_founder_turnover=k[3],
            outcome=k[4],
            count=v,
        )
        for k, v in sorted(counts.items())
    ]


def summarize(directory):
    """results.json and table.md from every runs_*.jsonl in the directory."""
    directory = Path(directory)
    out, lines = _summary(_load_runs(directory))
    with open(directory / "results.json", "x") as stream:
        json.dump(targets._json(out), stream, indent=1)
    with open(directory / "table.md", "x") as stream:
        stream.write("\n".join(lines) + "\n")
    return out


STAGES = ("pilot", "stage1-screen", "stage1b-attribution", "stage2-turnover", "stage3-robustness")


def final(root):
    """final.json and final_table.md over every stage directory's runs_*.jsonl."""
    root, runs = Path(root), []
    for stage in STAGES:
        if (root / stage).is_dir():
            runs += [dict(r, source=f"{stage}/{r['source']}") for r in _load_runs(root / stage)]
    out, lines = _summary(runs)
    out["kind"] = "cells.heredity_design_prescreen@9_final"
    out["stages"] = [s for s in STAGES if (root / s).is_dir()]
    with open(root / "final.json", "x") as stream:
        json.dump(targets._json(out), stream, indent=1)
    with open(root / "final_table.md", "x") as stream:
        stream.write("\n".join(lines) + "\n")
    return out


def _summary(runs):
    """(results, table lines) for screen and turnover runs."""
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
        het = " het" if r.get("heterogeneity") else ""
        short = r.get("horizon_s", HORIZON_S) != HORIZON_S
        horizon = f" ({r['horizon_s']:g} s pilot)" if short else ""
        return (
            f"| {r.get('disc_cells', '-')}{het} | {r['scale']:g} | {r['rule']} | "
            f"{r['rate_percent_per_min']:g} | {r['order']}{horizon} |"
        )

    def order(r):
        return (
            r.get("disc_cells", 0),
            bool(r.get("heterogeneity")),
            r["scale"],
            r["rule"],
            r["rate_percent_per_min"],
            r["order"],
            r.get("horizon_s", 0),
        )

    turns = sorted(turns, key=order)
    if turns:
        out["turnover"] = [
            {
                k: v
                for k, v in r.items()
                if k not in ("records", "lineage", "schedule", "trajectory")
            }
            for r in turns
        ]
        for entry, r in zip(out["turnover"], turns, strict=True):
            if "error" not in r:
                entry["rim_births"] = rim_births(r)
        lines += [
            "| disc | s | rule | %/min | order | J 10 / 20 / 30 / 40 / 50 min | J min | "
            "J<0.8 from s | J (D) after last founder | D end | founders left | "
            "disc newcomers D at end | stop |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for r in turns:
            if "error" in r:
                lines.append(f"{head(r)} {r['error']} | | | | | | | | |")
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
            after = sm["at_first_record_after_last_founder"]
            after = "-" if after is None else f"{after['jaccard']:.3f} ({after['d_total']})"
            lines.append(
                f"{head(r)} {js} | {sm['jaccard_min']:.2f} | {sm['first_record_below_0p8_s']} | "
                f"{after} | {sm['d_total_end']} | {sm['founders_remaining_end']} | "
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
        lines += [
            "",
            "Rim newcomers by neighbourhood at birth (rim_births): "
            "kind, D neighbours / of which newcomers -> ever D or H, count; "
            "first = born within the first founder turnover.",
            "",
            "| disc | s | rule | %/min | order | rim births |",
            "|---|---|---|---|---|---|",
        ]
        for entry, r in zip(out["turnover"], turns, strict=True):
            if "rim_births" not in entry:
                continue
            text = "; ".join(
                f"{b['slot_kind']} {b['d_neighbours']}/{b['newcomer_d_neighbours']}"
                f"{' first' if b['within_first_founder_turnover'] else ''} -> "
                f"{b['outcome']} x{b['count']}"
                for b in entry["rim_births"]
            )
            lines.append(f"{head(r)} {text} |")
    return out, lines


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
    parser.add_argument("--heterogeneous", action="store_true", help="stage 3 world (D133)")
    parser.add_argument("--horizon", type=float, default=HORIZON_S)
    parser.add_argument("--tag", default="main")
    parser.add_argument("--summarize", action="store_true", help="results.json and table.md")
    parser.add_argument("--final", action="store_true", help="final.json over the stage dirs")
    parser.add_argument("--mechanism", action="store_true", help="corner births next to newcomers")
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
        turnover_runs(
            args.output,
            parse_plan(args.plan),
            args.tag,
            args.horizon,
            args.disc,
            args.heterogeneous,
        )
        _log("turnover done")
    elif args.summarize:
        summarize(args.output)
    elif args.final:
        final(args.output)
    elif args.mechanism:
        mechanism(args.output)
        _log("mechanism done")
    else:
        parser.error("give --screen, --turnover or --summarize")
    return 0


if __name__ == "__main__":
    sys.exit(main())
