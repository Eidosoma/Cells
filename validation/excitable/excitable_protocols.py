"""The protocols of the excitable-tissue appendix (§8) on the independent reference, and the
driver that computes their numbers (Track E).

    python -m validation.excitable.excitable_protocols --out DIR [--parts ...] [--rtol 1e-10]

Writes DIR/results.json after every part (rest, single, stimulus, chain, convergence) and
DIR/log.txt. Every number comes from excitable_reference (Radau, rtol 1e-10 by default); the
convergence part repeats the key observables at rtol 1e-11 and atol / 100 (appendix §9).

Readings of §8 taken here (each labelled again in REFERENCES_USAGE.md):
* a "peak" is the largest V of the run, from t = 0, so a kick's own V(0) counts; an
  "overshoot" is a peak above 0 mV;
* APD_x runs from the time of the largest dV/dt to the first time after the peak at which V
  falls to V_peak - (x/100)(V_peak - V_rest);
* "returns within 5 mV of rest within 60 ms": the first time after the peak at which V falls to
  V_rest + 5 mV is at most 60 ms (from t = 0); the time is reported;
* a threshold is reported as the bisection's bracket (lo fails, hi succeeds) and hi;
* the chain's activation time is the first upward crossing of -30 mV, exact (re-integration),
  and also as the linear interpolation on a sampled grid (``sampled_activation``);
* CV uses the cells with N/3 <= i <= 2N/3 (7 to 13 of 20; 14 to 26 of 40);
* a wave propagates when every cell has an activation time; otherwise it is blocked;
* the capture threshold and the far-end S1-S2 interval are taken at s_c = 1000, the coupling
  of §8.4's controls; the "passive" control has NaV, Kv and Kir unavailable (§8.2's wording).
"""

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

from validation.excitable import excitable_limits as el
from validation.excitable import excitable_reference as er

LEVEL = -0.030  # §8.3 and §8.4
LOG = []


def log(*parts):
    line = " ".join(str(p) for p in parts)
    LOG.append(line)
    print(line, flush=True)


# ---------------------------------------------------------------- §8.1 rest


def rest_potential(point, *, rtol=1e-10, atol=None, constants=None):
    """§8.1: V_H at the heredity point; otherwise V(2 s) of the unstimulated cell started from
    H's composition at V_H with its gates at V_H's steady state."""
    if point == "heredity":
        return er.V_H
    tissue = er.appendix_tissue(point, constants=constants)
    run = er.simulate(tissue, er.Start(V=er.V_H, gates_at_V=er.V_H), 2.0, record=(2.0,),
                      rtol=rtol, atol=atol)
    return float(run.at[2.0]["V"][0])


# ---------------------------------------------------------------- §8.2 single cell


def single(point, V_rest, *, kick=0.0, nav=1.0, kir=1.0, kv=1.0, stimuli=(), t_end=0.080,
           rtol=1e-10, atol=None, constants=None, record=()):
    tissue = er.appendix_tissue(point, constants=constants, availability_NaV=nav,
                                availability_Kir=kir, availability_Kv=kv, stimuli=stimuli)
    return er.simulate(tissue, er.Start(V=V_rest, gates_at_V=V_rest, kick_V=kick), t_end,
                       record=record, rtol=rtol, atol=atol)


def ap_measures(run, V_rest, *, cell=0, t_from=0.0):
    """§8.2's measures of one run (see the module's readings)."""
    t_end = run.t_end
    t_peak, V_peak = run.extremum(cell, t_from, t_end)
    t_up, dvdt = run.extremum(cell, t_from, t_end, quantity="dVdt")
    amp = V_peak - V_rest
    out = dict(peak_V=V_peak, time_to_peak_s=t_peak, max_dVdt_V_per_s=dvdt,
               time_of_max_dVdt_s=t_up, overshoot=V_peak > 0.0)
    for x in (50, 90):
        # An APD is defined for an action potential only: a run whose upstroke (the largest
        # dV/dt, which must be positive) precedes its peak. Otherwise None (a passive decay).
        if dvdt <= 0.0 or t_up > t_peak:
            out[f"APD{x}_s"] = None
            continue
        t_x = run.crossing(cell, V_peak - x / 100.0 * amp, direction=-1, t_from=t_peak)
        out[f"APD{x}_s"] = None if t_x is None else t_x - t_up
    if V_peak <= V_rest + 0.005:
        t_back = t_peak
    else:
        t_back = run.crossing(cell, V_rest + 0.005, direction=-1, t_from=t_peak)
    out["return_within_5mV_s"] = t_back
    out["returns_within_60ms"] = t_back is not None and t_back <= 0.060
    out["V_at_80ms"] = float(run.V(0.080)[cell]) if t_end >= 0.080 else None
    out["excursions"] = run.excursions()
    out["steps"] = run.steps
    return out


def bisect(predicate, lo, hi, *, tol, log_scale=False, label=""):
    """The bracket (lo fails, hi succeeds) of a monotone predicate, to tol (relative to the
    bracket when log_scale)."""
    runs = 0
    if predicate(lo):
        return dict(threshold=lo, lo=None, hi=lo, runs=1, note="the lower end succeeds")
    if not predicate(hi):
        return dict(threshold=None, lo=hi, hi=None, runs=2, note="the upper end fails")
    runs = 2
    while (math.log(hi / lo) if log_scale else hi - lo) > tol:
        mid = math.sqrt(lo * hi) if log_scale else 0.5 * (lo + hi)
        if predicate(mid):
            hi = mid
        else:
            lo = mid
        runs += 1
        log("   ", label, "bracket", lo, hi)
    return dict(threshold=hi, lo=lo, hi=hi, runs=runs)


def kick_threshold(point, V_rest, *, rtol=1e-10, tol=1e-7, atol=None):
    """§8.2: the smallest kick in [0, 60] mV whose peak exceeds 0 mV (bisection, tol in V)."""
    def fires(k):
        run = single(point, V_rest, kick=k, rtol=rtol, atol=atol)
        return run.extremum(0, 0.0, run.t_end)[1] > 0.0

    return bisect(fires, 0.0, 0.060, tol=tol, label=f"{point} kick")


def single_panel(point, V_rest, threshold, *, rtol=1e-10, atol=None):
    """§8.2's runs: twice the threshold kick (capped at 60 mV) with all channels, with NaV
    unavailable, with NaV, Kv and Kir unavailable; the threshold +- 0.5 mV and - 5 mV."""
    k2 = min(2.0 * threshold, 0.060)
    arms = {
        "twice": dict(kick=k2),
        "twice_nav_off": dict(kick=k2, nav=0.0),
        "twice_all_off": dict(kick=k2, nav=0.0, kv=0.0, kir=0.0),
        "threshold_plus_0.5mV": dict(kick=threshold + 0.0005),
        "threshold_minus_0.5mV": dict(kick=threshold - 0.0005),
        "threshold_minus_5mV": dict(kick=max(threshold - 0.005, 0.0)),
    }
    out = {}
    for name, kw in arms.items():
        run = single(point, V_rest, rtol=rtol, atol=atol, **kw)
        out[name] = dict(kick_V=kw["kick"], **ap_measures(run, V_rest))
        log("  ", point, name, {k: out[name][k] for k in ("kick_V", "peak_V", "time_to_peak_s",
                                                          "max_dVdt_V_per_s", "APD90_s")})
    return out


# ---------------------------------------------------------------- §8.3 stimulus and recovery


def stimulus_threshold(point, V_rest, *, rtol=1e-10, rel_tol=1e-6, atol=None):
    """§8.3: the smallest P_stim on [1e-9, 1e-6] (c_m/0.05) m/s for a 1 ms stimulus at 2 ms that
    gives an overshoot (bisection in log P)."""
    scale = er.POINTS[point]["c_m"] / 0.05

    def fires(P):
        run = single(point, V_rest, stimuli=(er.stimulus((0,), P, (0.002, 0.003)),), rtol=rtol,
                     atol=atol)
        return run.extremum(0, 0.0, run.t_end)[1] > 0.0

    return bisect(fires, 1e-9 * scale, 1e-6 * scale, tol=rel_tol, log_scale=True,
                  label=f"{point} P_stim")


def s2_response(run, t2, *, cell=0):
    """§8.3: S2 responds if, after its onset t2, V newly crosses -30 mV upward and then exceeds
    0 mV. Returns (responds, the crossing time or None, the peak after it or None)."""
    t_c = run.crossing(cell, LEVEL, direction=+1, t_from=t2)
    if t_c is None:
        return False, None, None
    peak = run.extremum(cell, t_c, run.t_end)[1]
    return peak > 0.0, t_c, peak


def s1s2(point, V_rest, P_stim, deltas, *, rtol=1e-10, atol=None, after=0.060):
    out = {}
    for d in deltas:
        t2 = 0.002 + d
        run = single(point, V_rest, rtol=rtol, atol=atol, t_end=t2 + after,
                     stimuli=(er.stimulus((0,), P_stim, (0.002, 0.003), (t2, t2 + 0.001)),))
        responds, t_c, peak = s2_response(run, t2)
        out[f"{d * 1e3:g} ms"] = dict(delta_s=d, responds=responds, crossing_s=t_c,
                                      peak_after_V=peak, V_at_S2_V=float(run.V(t2)[0]))
        log("  ", point, "S1-S2", f"{d * 1e3:g} ms", responds, peak)
    return out


# ---------------------------------------------------------------- §8.4 chain


def chain(V_rest, n, s_c, *, P_stim=None, windows=((0.002, 0.003),), point="point2", nav=1.0,
          kir=1.0, kv=1.0, t_end=0.150, rtol=1e-10, atol=None, constants=None, record=()):
    """§8.4's chain: cells 0-2 stimulated at P_stim (default 1e-6 (c_m/0.05) m/s)."""
    if P_stim is None:
        P_stim = 1e-6 * er.POINTS[point]["c_m"] / 0.05
    tissue = er.appendix_tissue(point, n=n, s_c=s_c, constants=constants,
                                availability_NaV=nav, availability_Kir=kir, availability_Kv=kv,
                                stimuli=(er.stimulus((0, 1, 2), P_stim, *windows),))
    return er.simulate(tissue, er.Start(V=V_rest, gates_at_V=V_rest), t_end, record=record,
                       rtol=rtol, atol=atol)


def activation_times(run, *, t_from=0.0):
    return [run.crossing(i, LEVEL, direction=+1, t_from=t_from) for i in range(run.model.n)]


def sampled_activation(run, cell, t_exact, dt_sample):
    """The engine's reading of an activation time from rows every dt_sample: the first sampled
    row at or above -30 mV after one below, linearly interpolated (re-integrated rows)."""
    if t_exact is None:
        return None
    k = max(1, math.ceil(t_exact / dt_sample))
    while (k - 1) * dt_sample >= t_exact:
        k -= 1
    v1 = float(run.V(k * dt_sample)[cell])
    while v1 < LEVEL:  # rounding at the crossing
        k += 1
        v1 = float(run.V(k * dt_sample)[cell])
    v0 = float(run.V((k - 1) * dt_sample)[cell])
    return (k - 1) * dt_sample + (LEVEL - v0) / (v1 - v0) * dt_sample


def conduction_velocity(times, n):
    """1/slope (cells/s) of the least-squares line of activation time against index over the
    cells N/3 <= i <= 2N/3; None if any of them did not activate."""
    lo, hi = math.ceil(n / 3), math.floor(2 * n / 3)
    idx = np.arange(lo, hi + 1)
    t = [times[i] for i in idx]
    if any(x is None for x in t):
        return None
    slope = np.polyfit(idx.astype(float), np.array(t), 1)[0]
    return float(1.0 / slope)


def chain_measures(run, *, peaks=True):
    times = activation_times(run)
    n = run.model.n
    out = dict(activation_s=times, propagates=all(t is not None for t in times),
               cv_cells_per_s=conduction_velocity(times, n), excursions=run.excursions(),
               steps=run.steps, wall_s=run.wall_s)
    if peaks:
        out["peaks_V"] = [run.extremum(i, 0.0, run.t_end)[1] for i in range(n)]
    return out


def chain_propagates(V_rest, n, s_c, **kw):
    """Whether every cell of the chain activates (no peaks computed)."""
    return chain_measures(chain(V_rest, n, s_c, **kw), peaks=False)["propagates"]


def wave_outcome(V_rest, n, s_c, *, t_end=0.150, t_max=2.0, quiet=5.0, **kw):
    """Propagation decided independently of the horizon: run to t_end; if a cell has not
    activated, the wave counts as blocked only once no new activation has followed for
    ``quiet`` times the median of the last three inter-cell intervals (and at least 20 ms);
    otherwise the horizon is doubled (up to t_max) and the run repeated. Returns
    dict(propagates, activation_s, t_end, decided_by)."""
    while True:
        run = chain(V_rest, n, s_c, t_end=t_end, **kw)
        times = activation_times(run)
        if all(t is not None for t in times):
            return dict(propagates=True, activation_s=times, t_end=t_end, decided_by="all")
        done = [t for t in times if t is not None]
        if not done:
            return dict(propagates=False, activation_s=times, t_end=t_end,
                        decided_by="no activation")
        gaps = np.diff(sorted(done))[-3:]
        wait = max(quiet * (float(np.median(gaps)) if len(gaps) else 0.0), 0.020)
        if t_end - max(done) >= wait:
            return dict(propagates=False, activation_s=times, t_end=t_end,
                        decided_by=f"quiet for {t_end - max(done):.4g} s >= {wait:.4g} s")
        if t_end >= t_max:
            return dict(propagates=None, activation_s=times, t_end=t_end,
                        decided_by="undecided at t_max")
        t_end = min(2.0 * t_end, t_max)


def far_end_second_wave(run, t2):
    """Does the far cell activate again after S2's onset t2 (a second upward crossing after
    the first wave's)?"""
    last = run.model.n - 1
    first = run.crossing(last, LEVEL, direction=+1)
    if first is None:
        return False
    return run.crossing(last, LEVEL, direction=+1, t_from=max(t2, first + 1e-9)) is not None


# ---------------------------------------------------------------- §8.5 the mid-chain segment

SEGMENT_CELLS = tuple(range(16, 24))  # cells 16-23
SEGMENT_JUNCTIONS = tuple(range(15, 24))  # junction j joins cells j and j + 1: 15-16 ... 23-24


def segment_chain(V_rest, point, *, r_na=1.0, r_gj=1.0, n=40, s_c=1000.0, t_end=0.100,
                  rtol=1e-10, atol=None, constants=None, record=()):
    """§8.5: the chain of §8.4 (cells 0-2 stimulated at 1e-6 (c_m/0.05) m/s for [2, 3) ms)
    with NaV1.2 at availability r_na on cells 16-23 and the nine junctions 15-16 ... 23-24 at
    availability r_gj (multiplying their flux, so their s_c is s_c r_gj), held from t = 0."""
    nav = np.ones(n)
    nav[list(SEGMENT_CELLS)] = r_na
    sc = np.full(n - 1, float(s_c))
    sc[list(SEGMENT_JUNCTIONS)] = s_c * r_gj
    P_stim = 1e-6 * er.POINTS[point]["c_m"] / 0.05
    tissue = er.appendix_tissue(point, n=n, s_c=sc, constants=constants, availability_NaV=nav,
                                stimuli=(er.stimulus((0, 1, 2), P_stim, (0.002, 0.003)),))
    return er.simulate(tissue, er.Start(V=V_rest, gates_at_V=V_rest), t_end, record=record,
                       rtol=rtol, atol=atol)


def range_cv(times, lo, hi):
    """1/slope (cells/s) over cells lo..hi inclusive; None unless all activated."""
    idx = np.arange(lo, hi + 1)
    t = [times[i] for i in idx]
    if any(x is None for x in t):
        return None
    return float(1.0 / np.polyfit(idx.astype(float), np.array(t), 1)[0])


def segment_measures(run):
    """§8.5's report for one case."""
    n = run.model.n
    times = activation_times(run)
    peaks = [run.extremum(i, 0.0, run.t_end)[1] for i in range(n)]
    junctions = {}
    for j in SEGMENT_JUNCTIONS:
        t, v = run.junction_voltage_max(j)
        junctions[f"{j}-{j + 1}"] = dict(t_s=t, V_i_minus_V_next=v)
    T, V, _, _, _ = run._arrays()
    stored = float(np.max(np.abs(V[:, 15:24] - V[:, 16:25])))
    activated = [i for i, t in enumerate(times) if t is not None]
    above = [i for i, v in enumerate(peaks) if v > 0.0]
    a15, a24 = times[15] is not None, times[24] is not None
    return dict(
        activation_s=times, peaks_V=peaks,
        cell_15_activates=a15, cell_24_activates=a24, block=a15 and not a24,
        segment_delay_s=(times[24] - times[15]) if a15 and a24 else None,
        cv_6_14=range_cv(times, 6, 14), cv_16_23=range_cv(times, 16, 23),
        cv_25_31=range_cv(times, 25, 31),
        last_activated_cell=max(activated) if activated else None,
        last_cell_above_0mV=max(above) if above else None,
        segment_junctions=junctions,
        entry_junction_max_abs_V=abs(junctions["15-16"]["V_i_minus_V_next"]),
        segment_junction_max_abs_V=max(abs(x["V_i_minus_V_next"]) for x in junctions.values()),
        segment_junction_max_abs_V_at_stored_steps=stored,
        largest_V=max(peaks), largest_V_cell=int(np.argmax(peaks)), end_cell_peak_V=peaks[-1],
        excursions=run.excursions(), steps=run.steps, wall_s=run.wall_s)


SEGMENT_CASES = {  # §8.5: (r_na, r_gj) per case
    "point2": dict(
        control=(1.0, 1.0),
        **{f"combined_{r:g}": (r, r) for r in (0.5, 0.3, 0.2, 0.1, 0.05)},
        **{f"sodium_{r:g}": (r, 1.0) for r in (0.3, 0.1)},
        **{f"coupling_{r:g}": (1.0, r) for r in (0.1, 0.03)}),
    "A": dict(
        control=(1.0, 1.0),
        **{f"combined_{r:g}": (r, r) for r in (0.9, 0.8, 0.7, 0.6, 0.5)},
        **{f"sodium_{r:g}": (r, 1.0) for r in (0.7, 0.5)},
        **{f"coupling_{r:g}": (1.0, r) for r in (0.5, 0.3)}),
}
EXTENSION = (0.02, 0.01)  # §8.5: added to the combined cases if none of them blocks
# The coordinator's coupling ladder for A's block-site junction voltages, down to s_c r_gj < 10.
A_LADDER = (0.3, 0.2, 0.1, 0.05, 0.03, 0.02, 0.01, 0.007, 0.005, 0.003, 0.002, 0.001)


def segment_part(point, V_rest, *, rtol, ladder=(), on_case=None):
    out = {}
    cases = dict(SEGMENT_CASES[point])
    for name, (r_na, r_gj) in list(cases.items()):
        out[name] = dict(r_na=r_na, r_gj=r_gj,
                         **segment_measures(segment_chain(V_rest, point, r_na=r_na, r_gj=r_gj,
                                                          rtol=rtol)))
        log(" ", point, name, "block", out[name]["block"], "entry |Vj|",
            out[name]["entry_junction_max_abs_V"], "largest V", out[name]["largest_V"])
        if on_case:
            on_case(out)
    combined = [k for k in out if k.startswith("combined_")]
    extra = [] if any(out[k]["block"] for k in combined) else list(EXTENSION)
    for r in sorted({*extra, *ladder}, reverse=True):
        name = f"combined_{r:g}"
        if name in out:
            continue
        out[name] = dict(r_na=r, r_gj=r, extension=r in extra,
                         **segment_measures(segment_chain(V_rest, point, r_na=r, r_gj=r,
                                                          rtol=rtol)))
        log(" ", point, name, "block", out[name]["block"], "entry |Vj|",
            out[name]["entry_junction_max_abs_V"], "largest V", out[name]["largest_V"])
        if on_case:
            on_case(out)
    return out


# ---------------------------------------------------------------- §8.6 the 0.01 F/m^2 cells


def cm001_part(point, V_rest, *, rtol, tol_kick):
    """§8.6: §8.2's protocols with kicks to -20 mV and to 0 mV, the 1 ms stimulus at 2e-7 m/s
    per ion, and §8.4's chain at s_c = 1000; the largest V of every run against +60 mV."""
    out = dict(rest_V=V_rest)
    thr = kick_threshold(point, V_rest, rtol=rtol, tol=tol_kick)
    out["kick_threshold"] = thr
    if thr["threshold"] is not None:
        out["panel"] = single_panel(point, V_rest, thr["threshold"], rtol=rtol)
    for name, target in (("kick_to_-20mV", -0.020), ("kick_to_0mV", 0.0)):
        run = single(point, V_rest, kick=target - V_rest, rtol=rtol)
        out[name] = dict(kick_V=target - V_rest, **ap_measures(run, V_rest))
    P = 1e-6 * er.POINTS[point]["c_m"] / 0.05
    run = single(point, V_rest, stimuli=(er.stimulus((0,), P, (0.002, 0.003)),), rtol=rtol)
    out["stimulus_2e-7"] = dict(P_stim=P, **ap_measures(run, V_rest))
    out["chain_1000"] = chain_measures(chain(V_rest, 20, 1000.0, point=point, rtol=rtol))
    runs = [v for v in (*(out.get("panel") or {}).values(), out["kick_to_-20mV"],
                        out["kick_to_0mV"], out["stimulus_2e-7"])]
    out["largest_V_single"] = max(r["peak_V"] for r in runs)
    out["largest_V_chain"] = max(out["chain_1000"]["peaks_V"])
    out["exceeds_60mV"] = max(out["largest_V_single"], out["largest_V_chain"]) > 0.060
    log(" ", point, "largest V", out["largest_V_single"], out["largest_V_chain"])
    return out


# ---------------------------------------------------------------- the driver


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", required=True)
    parser.add_argument("--parts", nargs="+",
                        default=["segment_A", "segment_point2", "single", "stimulus", "chain",
                                 "cm001", "limits", "convergence"])
    parser.add_argument("--rtol", type=float, default=1e-10)
    parser.add_argument("--points", nargs="+", default=["heredity", "point2", "A", "B"])
    parser.add_argument("--main", help="the main run's results.json, for bracket_check")
    parser.add_argument("--quick", action="store_true",
                        help="a smoke run: rtol 1e-8 and coarse bisection tolerances")
    args = parser.parse_args(argv)
    if args.quick:
        args.rtol = max(args.rtol, 1e-8)
    tol = dict(kick=1e-4 if args.quick else 1e-7, stim=1e-2 if args.quick else 1e-6,
               s_c=math.log(1.1 if args.quick else 1.01),
               capture=math.log(1.1 if args.quick else 1.001),
               s1s2=1e-3 if args.quick else 1e-5)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    results = dict(kind="cells.excitable_reference_protocols@1", rtol=args.rtol,
                   atol=er.ATOL, method="Radau", python=sys.version,
                   appendix="docs/EXCITABLE_TISSUE_EQUATIONS.md, draft of 14 November 2026 "
                            "(branch worktree-agent-a76bfeaf3e7eececa, db488771)")
    started = time.perf_counter()

    def save():
        results["wall_s"] = time.perf_counter() - started
        (out / "results.json").write_text(json.dumps(results, indent=1, default=float) + "\n")
        (out / "log.txt").write_text("\n".join(LOG) + "\n")

    rtol = args.rtol
    rests = {p: rest_potential(p, rtol=rtol) for p in args.points}
    results["rest"] = rests
    log("rest", rests)
    save()
    for point in ("A", "point2"):
        if f"segment_{point}" in args.parts:
            results.setdefault("segment", {})

            def keep(cases, point=point):
                results["segment"][point] = cases
                results["segment"][f"{point}_saved_utc"] = time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                save()

            ladder = A_LADDER if point == "A" else ()
            keep(segment_part(point, rests[point], rtol=rtol, ladder=ladder, on_case=keep))
    classic = [p for p in args.points if p in ("heredity", "point2")]
    if "single" in args.parts:
        results["single"] = {}
        for p in classic:
            thr = kick_threshold(p, rests[p], rtol=rtol, tol=tol["kick"])
            entry = dict(kick_threshold=thr)
            log(p, "kick threshold", thr)
            if thr["threshold"] is not None:
                entry["panel"] = single_panel(p, rests[p], thr["threshold"], rtol=rtol)
            else:
                run = single(p, rests[p], kick=0.060, rtol=rtol)
                entry["at_60mV"] = ap_measures(run, rests[p])
            results["single"][p] = entry
            save()
    if "stimulus" in args.parts:
        results["stimulus"] = {}
        for p in classic:
            thr = stimulus_threshold(p, rests[p], rtol=rtol, rel_tol=tol["stim"])
            entry = dict(stimulus_threshold=thr)
            log(p, "stimulus threshold", thr)
            if thr["threshold"] is not None:
                deltas = [x * 1e-3 for x in (5, 8, 10, 12, 15, 20, 25, 30, 40, 60)]
                entry["s1s2"] = s1s2(p, rests[p], 2.0 * thr["threshold"], deltas, rtol=rtol)
            results["stimulus"][p] = entry
            save()
    if "chain" in args.parts:
        V2 = rests.get("point2", rest_potential("point2", rtol=rtol))
        res = results["chain"] = dict(V_rest=V2, scan={}, controls={})
        for s_c in (10.0, 30.0, 100.0, 300.0, 1000.0, 3000.0):
            res["scan"][f"{s_c:g}"] = chain_measures(chain(V2, 20, s_c, rtol=rtol))
            log("chain s_c", s_c, res["scan"][f"{s_c:g}"]["propagates"],
                res["scan"][f"{s_c:g}"]["cv_cells_per_s"])
            save()
        res["controls"]["nav_off"] = chain_measures(chain(V2, 20, 1000.0, nav=0.0, rtol=rtol))
        res["controls"]["passive"] = chain_measures(chain(V2, 20, 1000.0, nav=0.0, kv=0.0,
                                                          kir=0.0, rtol=rtol))
        log("controls", {k: v["propagates"] for k, v in res["controls"].items()})
        save()
        res["length_40"] = chain_measures(chain(V2, 40, 1000.0, t_end=0.2, rtol=rtol))
        log("N = 40 CV", res["length_40"]["cv_cells_per_s"])
        save()
        # The coupling bracket between block and propagation: extend the scan down until
        # block (and probe s_c = 1e4 above it), then bisect each change of outcome in log s_c.
        outcome = {s: res["scan"][f"{s:g}"]["propagates"] for s in (10.0, 30.0, 100.0, 300.0,
                                                                    1000.0, 3000.0)}

        def propagates(s_c):
            if s_c not in outcome:
                outcome[s_c] = chain_propagates(V2, 20, s_c, rtol=rtol)
                log("   s_c", s_c, outcome[s_c])
            return outcome[s_c]

        s = 10.0
        while propagates(s) and s > 1e-2:
            s /= 3.0
        propagates(1e4)
        brackets = []
        grid = sorted(outcome)
        for a, b in zip(grid, grid[1:], strict=False):
            if outcome[a] == outcome[b]:
                continue
            if not outcome[a]:  # block below, propagation above
                found = bisect(propagates, a, b, tol=tol["s_c"], log_scale=True, label="s_c")
                found["kind"] = "block below, propagation above"
            else:  # propagation below, block above
                found = bisect(lambda x: not propagates(x), a, b, tol=tol["s_c"],
                               log_scale=True, label="s_c")
                found["kind"] = "propagation below, block above"
            brackets.append(found)
        res["coupling_bracket"] = brackets
        res["coupling_outcomes"] = {f"{k:g}": v for k, v in sorted(outcome.items())}
        log("coupling bracket", brackets)
        save()
        # The capture threshold in P_stim at s_c = 1000.
        k = er.POINTS["point2"]["c_m"] / 0.05
        res["capture_threshold"] = bisect(
            lambda P: chain_propagates(V2, 20, 1000.0, P_stim=P, rtol=rtol),
            1e-9 * k, 1e-6 * k, tol=tol["capture"], log_scale=True, label="capture P")
        log("capture", res["capture_threshold"])
        save()
        # The S1-S2 interval for a second wave at the far end (s_c = 1000).
        travel = res["scan"]["1000"]["activation_s"][-1] or 0.02

        def second(d):
            t2 = 0.002 + d
            run = chain(V2, 20, 1000.0, windows=((0.002, 0.003), (t2, t2 + 0.001)),
                        t_end=t2 + travel + 0.03, rtol=rtol)
            return far_end_second_wave(run, t2)

        res["far_end_s1s2"] = bisect(second, 0.001, 0.200, tol=tol["s1s2"],
                                     label="S1-S2 far end")
        log("far-end S1-S2", res["far_end_s1s2"])
        save()
    if "cm001" in args.parts:
        results["cm001"] = {}
        for p in [x for x in args.points if x in ("A", "B")]:
            results["cm001"][p] = cm001_part(p, rests[p], rtol=rtol, tol_kick=tol["kick"])
            save()
    if "limits" in args.parts:
        results["limits"] = limits_part(rtol)
        save()
    # Follow-up parts (not in the default list).
    if "bracket_check" in args.parts:  # the blocking ends of the main run's brackets, re-decided
        main_results = json.loads(Path(args.main).read_text())["chain"]
        V2 = main_results["V_rest"]
        out = results["bracket_check"] = {}
        for i, b in enumerate(main_results.get("coupling_bracket", [])):
            blocked_end = b["lo"] if b.get("kind", "").startswith("block below") else b["hi"]
            if blocked_end is not None:
                out[f"coupling_{i}"] = dict(s_c=blocked_end, bracket=b,
                                            **wave_outcome(V2, 20, blocked_end, rtol=rtol))
                log("  bracket check", out[f"coupling_{i}"]["propagates"],
                    out[f"coupling_{i}"]["decided_by"])
                save()
        c = main_results.get("capture_threshold") or {}
        if c.get("lo") is not None:
            out["capture"] = dict(P_stim=c["lo"], bracket=c,
                                  **wave_outcome(V2, 20, 1000.0, P_stim=c["lo"], rtol=rtol))
            log("  capture check", out["capture"]["propagates"], out["capture"]["decided_by"])
            save()
    if "bracket_robust" in args.parts:  # §8.4's bracket and capture, horizon-independent
        V2 = rests.get("point2", rest_potential("point2", rtol=rtol))
        out = results["bracket_robust"] = dict(outcomes={})

        def decided(s_c, **kw):
            key = f"s_c={s_c:g}" + "".join(f",{k}={v:g}" for k, v in kw.items())
            if key not in out["outcomes"]:
                out["outcomes"][key] = wave_outcome(V2, 20, s_c, rtol=rtol, **kw)
                log("   robust", key, out["outcomes"][key]["propagates"],
                    out["outcomes"][key]["decided_by"])
                save()
            return bool(out["outcomes"][key]["propagates"])

        grid = [3000.0, 1000.0, 300.0, 100.0, 30.0, 10.0, 3.0, 1.0, 0.3, 0.1]
        seen = {s: decided(s) for s in grid}
        out["brackets"] = []
        for a, b in zip(sorted(seen), sorted(seen)[1:], strict=False):
            if seen[a] != seen[b]:
                pred = decided if not seen[a] else (lambda x: not decided(x))
                found = bisect(pred, a, b, tol=tol["s_c"], log_scale=True, label="robust s_c")
                found["kind"] = ("block below, propagation above" if not seen[a]
                                 else "propagation below, block above")
                out["brackets"].append(found)
                save()
        k = er.POINTS["point2"]["c_m"] / 0.05
        out["capture_threshold"] = bisect(lambda P: decided(1000.0, P_stim=P), 1e-9 * k,
                                          1e-6 * k, tol=tol["capture"], log_scale=True,
                                          label="robust capture P")
        save()
    if "segment_A_tight" in args.parts:  # the block-site values at rtol / 10, atol / 100
        tight = dict(rtol=rtol / 10.0, atol={k: v / 100.0 for k, v in er.ATOL.items()})
        results["segment_A_tight"] = {}
        for name, r in (("control", 1.0), ("combined_0.5", 0.5), ("combined_0.2", 0.2),
                        ("combined_0.02", 0.02), ("combined_0.01", 0.01)):
            results["segment_A_tight"][name] = dict(
                r_na=r, r_gj=r, **segment_measures(segment_chain(rests["A"], "A", r_na=r,
                                                                 r_gj=r, **tight)))
            log("  A tight", name, results["segment_A_tight"][name]["entry_junction_max_abs_V"])
            save()
    if "segment_A_coupling_only" in args.parts:  # coupling-only rungs down to s_c r_gj = 5
        results["segment_A_coupling_only"] = {}
        for r in (0.1, 0.05, 0.02, 0.01, 0.005):
            results["segment_A_coupling_only"][f"coupling_{r:g}"] = dict(
                r_na=1.0, r_gj=r, **segment_measures(segment_chain(rests["A"], "A", r_gj=r,
                                                                   rtol=rtol)))
            log("  A coupling-only", r, results["segment_A_coupling_only"][f"coupling_{r:g}"]
                ["entry_junction_max_abs_V"])
            save()
    if "cm001_arms" in args.parts:  # §8.2's NaV-off and all-off arms at §8.6's kicks
        results["cm001_arms"] = {}
        for p in [x for x in args.points if x in ("A", "B")]:
            V = rests[p]
            entry = results["cm001_arms"][p] = {}
            for target in (-0.020, 0.0):
                for arm, kw in (("nav_off", dict(nav=0.0)),
                                ("all_off", dict(nav=0.0, kv=0.0, kir=0.0))):
                    run = single(p, V, kick=target - V, rtol=rtol, **kw)
                    entry[f"kick_to_{target * 1e3:g}mV_{arm}"] = dict(
                        kick_V=target - V, **ap_measures(run, V))
            save()
    if "convergence" in args.parts:
        results["convergence"] = convergence_part(results, rtol)
        save()
    log("done", f"{time.perf_counter() - started:.0f} s")
    save()


def limits_part(rtol):
    """The passive cable (nonlinear against linear, two stimulus sizes) and the strong-coupling
    limit (the chain against the lumped cell, three couplings)."""
    out = {}
    V2 = rest_potential("point2", rtol=rtol)
    tissue = er.appendix_tissue("point2", n=20, s_c=1000.0)
    times = (0.0025, 0.003, 0.005, 0.010)
    for P in (1e-9, 2e-9, 4e-9):
        coeffs = el.passive_linearisation(tissue, V2, p_stim=P)
        lam, r = el.space_constant_cells(coeffs["g_m_S"], coeffs["g_j_S"])
        run = chain(V2, 20, 1000.0, P_stim=P, nav=0.0, kv=0.0, kir=0.0, t_end=0.010,
                    record=times, rtol=rtol)
        C = float(run.model.capacitance[0])
        lin = el.linear_cable_response(20, C, coeffs, V2, (0, 1, 2), ((0.002, 0.003),), times)
        diffs = {f"{t * 1e3:g} ms": float(np.max(np.abs(run.at[t]["V"] - V2 - lin[t])))
                 for t in times}
        amps = {f"{t * 1e3:g} ms": float(np.max(np.abs(lin[t]))) for t in times}
        out[f"passive_cable_P={P:g}"] = dict(**coeffs, space_constant_cells=lam, r=r,
                                             max_abs_difference_V=diffs, linear_amplitude_V=amps)
        log("passive cable", P, "lambda", lam, "diffs", diffs)
    for s_c in (1e4, 1e5, 1e6):
        run = chain(V2, 20, s_c, t_end=0.030, record=(0.005, 0.010, 0.030), rtol=rtol)
        lumped = el.lumped_cell(run.model.t)
        single_run = er.simulate(lumped, er.Start(V=V2, gates_at_V=V2), 0.030,
                                 record=(0.005, 0.010, 0.030), rtol=rtol)
        out[f"strong_coupling_s_c={s_c:g}"] = {
            f"{t * 1e3:g} ms": float(np.max(np.abs(run.at[t]["V"] - single_run.at[t]["V"][0])))
            for t in (0.005, 0.010, 0.030)}
        log("strong coupling", s_c, out[f"strong_coupling_s_c={s_c:g}"])
    return out


def convergence_part(results, rtol):
    """§9's convergence check: the key observables at rtol/10 and atol/100 against rtol."""
    tight = dict(rtol=rtol / 10.0, atol={k: v / 100.0 for k, v in er.ATOL.items()})
    out = {}
    V2a = rest_potential("point2", rtol=rtol)
    V2b = rest_potential("point2", **tight)
    out["rest_point2_V"] = abs(V2a - V2b)
    for p, entry in results.get("single", {}).items():
        V = results["rest"][p]
        if "panel" not in entry:
            continue
        thr = entry["kick_threshold"]
        lo_fires = single(p, V, kick=thr["lo"], **tight)
        hi_fires = single(p, V, kick=thr["hi"], **tight)
        out[f"{p}_kick_bracket_holds"] = (
            lo_fires.extremum(0, 0.0, 0.08)[1] <= 0.0 < hi_fires.extremum(0, 0.0, 0.08)[1])
        a = ap_measures(single(p, V, kick=entry["panel"]["twice"]["kick_V"], rtol=rtol), V)
        b = ap_measures(single(p, V, kick=entry["panel"]["twice"]["kick_V"], **tight), V)
        out[f"{p}_twice"] = {k: (abs(a[k] - b[k]) if isinstance(a[k], float) else None)
                             for k in a if isinstance(a[k], float)}
        log("convergence", p, out[f"{p}_twice"], out[f"{p}_kick_bracket_holds"])
    if "chain" in results:
        V2 = results["chain"]["V_rest"]
        a = chain_measures(chain(V2, 20, 1000.0, rtol=rtol))
        b = chain_measures(chain(V2, 20, 1000.0, **tight))
        out["chain_1000"] = dict(
            activation_max_abs_s=max(abs(x - y) for x, y in zip(a["activation_s"],
                                                               b["activation_s"], strict=True)),
            peaks_max_abs_V=max(abs(x - y) for x, y in zip(a["peaks_V"], b["peaks_V"],
                                                          strict=True)),
            cv_abs=abs(a["cv_cells_per_s"] - b["cv_cells_per_s"]))
        log("convergence chain", out["chain_1000"])
    return out


if __name__ == "__main__":
    main()
