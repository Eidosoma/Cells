"""R2's protocol: MT-1b's worlds W3 (a)-(d) on section 7's steps, integrated with restarts.

The schedule is the world declaration's G7, read from declaration.json:
- every world starts from the declared start state (R2's anchored state-4 steady state, G7);
- world (a): state 4 (0-60 s), the ADP step (60-180 s), state 4 (180-300 s), then the uncoupler and
  the inhibitor as separate 120 s branches from the 300 s state, each with the ATP bath;
- controls (b) and (c): the uncoupler patch on, or the exchange off, from t = 0, on (a)'s main
  schedule (R2's reading: the branches are world (a)'s);
- world (d): O2 in its own finite node from t = 0, the ADP step at 60 s held to 240 s.

Each segment is one solve_ivp call, so the integrator restarts at every scheduled step and no step
lies inside an integration interval. Outputs: each segment's start (its right limit), every 10 ms
for 2 s, then every 0.5 s, and its end (its left limit).
"""

import time

import numpy as np
from scipy.integrate import solve_ivp

from . import model

# Each physical state's absolute tolerance is rtol times its floor, so the error control is
# relative for every concentration above 1e-9 M (trace-level rows included) and for dPsi above
# 1 mV. The ledger states are quadratures (their Jacobian columns are exactly zero): they start
# at zero and take no part in the error control or the Newton test (atol 1), and their accuracy
# is the physical steps' own, which the energy ledger's closure measures.
CONCENTRATION_FLOOR = 1e-9
DPSI_FLOOR = 1.0
LEDGER_ATOL = 1.0

JUDGED = {  # readout: (band key, kind): the MT-1b draft's plateau bands
    "dpsi_mV": ("dpsi_mV", "absolute"),
    "pH_N": ("pH", "absolute"),
    "pH_P": ("pH", "absolute"),
    "NADH_fraction": ("fraction", "absolute"),
    "cytc_reduced_fraction": ("fraction", "absolute"),
    "O2_flux": ("relative", "relative"),
    "K_N": ("relative", "relative"),
    "Pi_N": ("relative", "relative"),
    "ATP_N": ("relative", "relative"),
}


def atol_vector(rtol):
    a = np.full(len(model.STATE), LEDGER_ATOL)
    a[:model.NPHYS] = rtol * CONCENTRATION_FLOOR
    a[model.IDX["dpsi"]] = rtol * DPSI_FLOOR
    return a


def output_grid(t0, t1, out):
    fdt, fwin, cdt = out["fine_dt_s"], out["fine_window_s"], out["coarse_dt_s"]
    n_fine = int(round(fwin / fdt))
    fine = t0 + fdt * np.arange(1, n_fine + 1)
    first = np.ceil((t0 + fwin) / cdt + 1e-9) * cdt
    coarse = np.arange(first, t1 - 1e-9, cdt)
    grid = np.concatenate(([t0], fine[fine < t1 - 1e-9], coarse, [t1]))
    return np.unique(np.round(grid, 9))


def integrate(world, y0, t0, t1, ctl, t_eval, rtol, method="Radau"):
    """One segment from its start state, the solver restarted at t0.

    The right-hand side is autonomous, so the segment runs in its own time, t - t0. After a step
    that moves a trace row by many decades, the first steps can then shrink far below the
    spacing of floating-point times near t0 and grow geometrically from there.
    """
    fun = lambda t, y: world.rhs(t, y, ctl)  # noqa: E731
    local = None if t_eval is None else np.asarray(t_eval, dtype=float) - t0
    if local is not None:
        local[0] = max(local[0], 0.0)
        local[-1] = min(local[-1], t1 - t0)
    kwargs = dict(method=method, t_eval=local, rtol=rtol, atol=atol_vector(rtol))
    if method in ("Radau", "BDF"):
        kwargs["jac"] = lambda t, y: world.jac(t, y, ctl)  # noqa: E731
    started = time.process_time()
    sol = solve_ivp(fun, (0.0, t1 - t0), y0, **kwargs)
    if sol.status != 0:
        raise RuntimeError("integration failed: " + sol.message)
    sol.t = np.asarray(t_eval, dtype=float) if t_eval is not None else sol.t + t0
    return sol, dict(nfev=int(sol.nfev), njev=int(sol.njev), nlu=int(sol.nlu),
                     outputs=int(len(sol.t)), cpu_s=time.process_time() - started)


def schedule(world, name):
    """World ``name``'s segments: (segment, branch, t0, t1, controls) in run order."""
    p = world.declaration["protocol"]
    base = dict(p["controls"][name])
    segs = []
    if name == "d":
        for seg in p["world_d"]:
            segs.append((seg["name"], None, seg["t0"], seg["t1"], dict(base, bath=seg["bath"])))
        return segs
    for seg in p["main"]:
        segs.append((seg["name"], None, seg["t0"], seg["t1"], dict(base, bath=seg["bath"])))
    if name == "a":
        for br in p["branches"]:
            ctl = dict(base, bath=br["bath"])
            for key in ("a_unc", "a_C4", "a_ANT"):
                if key in br:
                    ctl[key] = br[key]
            segs.append((br["name"], br["name"], br["t0"], br["t1"], ctl))
    return segs


def run_world(world, name, start, rtol, method="Radau"):
    """Run world ``name`` from the declared start; return its output records and costs."""
    out = world.declaration["protocol"]["output"]
    stats = []
    records = []
    y0 = np.array(start, dtype=float)
    y0[model.NPHYS:] = 0.0  # every ledger starts at t = 0
    main_end = None
    y_cur = y0
    for seg, branch, t0, t1, kwargs in schedule(world, name):
        ctl = model.Controls(world, **kwargs)
        y_start = main_end if branch else y_cur
        grid = output_grid(t0, t1, out)
        sol, st = integrate(world, y_start, t0, t1, ctl, grid, rtol, method)
        stats.append(dict(segment=seg, branch=branch, **st))
        for k, t in enumerate(sol.t):
            side = "start" if k == 0 else ("end" if k == len(sol.t) - 1 else "inside")
            records.append(dict(segment=seg, branch=branch, t=float(t), side=side,
                                controls=ctl.describe(), y=sol.y[:, k].copy()))
        if branch is None:
            y_cur = sol.y[:, -1].copy()
            main_end = y_cur
    return dict(world=name, rtol=rtol, method=method, records=records, stats=stats)


def evaluate_records(world, result):
    """Readouts and ledgers at every output record.

    The ledger states run on from t = 0 (a branch starts from the main run's 300 s state with its
    ledgers), so every record's invariants and energy residual are taken against the start:
    energy residual = (A - A_0) + D - W, which the integration should hold at zero.
    """
    rows = []
    ref = None
    for rec in result["records"]:
        ctl = model.Controls(world, **rec["controls"])
        y = rec["y"]
        r = world.readouts(y, ctl)
        inv = world.invariants(y, ctl.o2)
        A, D, W = world.energy_terms(y, ctl.o2)
        if ref is None:
            ref = dict(inv=inv, A=A)
        rows.append(dict(segment=rec["segment"], branch=rec["branch"], t=rec["t"],
                         side=rec["side"], controls=rec["controls"], readouts=r, invariants=inv,
                         scales=world.invariant_scales(y, ctl.o2),
                         A=A, D=D, W=W, energy_residual=(A - ref["A"]) + D - W,
                         stall_mV=world.synthase_stall_mV(y)))
    return rows, ref


def ledger_closure(rows, ref):
    """Each invariant's largest drift from the start, over the magnitude of its terms, and the
    energy ledger's residual against the dissipation, per run part."""
    out = {}
    parts = {}
    for r in rows:
        parts.setdefault(r["branch"] or "main", []).append(r)
    for part, rs in parts.items():
        drift = {}
        for key, v0 in ref["inv"].items():
            vals = np.array([r["invariants"][key] for r in rs])
            scale = max(max(r["scales"][key] for r in rs), 1e-300)
            drift[key] = float(np.max(np.abs(vals - v0)) / scale)
        e = max(abs(r["energy_residual"]) for r in rs)
        d = max(abs(r["D"]) for r in rs)
        out[part] = dict(invariant_relative_drift=drift, energy_residual_max=float(e),
                         dissipation_max=float(d),
                         energy_residual_over_dissipation=float(e / max(d, 1e-300)))
    return out


def plateau_drift(world, rows):
    """The drift rule: each judged readout's change over the last 10 s, against a tenth of its
    band."""
    p = world.declaration["protocol"]
    window = p["drift_window_s"]
    bands = world.declaration["bands"]
    out = {}
    keys = []
    for r in rows:
        k = (r["branch"], r["segment"])
        if k not in keys:
            keys.append(k)
    for branch, seg in keys:
        seg_rows = [r for r in rows if r["segment"] == seg and r["branch"] == branch]
        end = seg_rows[-1]
        t_end = end["t"]
        before = min(seg_rows, key=lambda r: abs(r["t"] - (t_end - window)))
        entry = {"t_end": t_end, "t_window_start": before["t"], "readouts": {}}
        worst = 0.0
        for key, (band_key, kind) in JUDGED.items():
            a, b = before["readouts"][key], end["readouts"][key]
            band = bands[band_key]
            drift = abs(b - a) if kind == "absolute" else abs(b - a) / max(abs(b), 1e-300)
            ratio = drift / (band / 10.0)
            worst = max(worst, ratio)
            entry["readouts"][key] = {"value": b, "drift": drift, "drift_over_tenth_band": ratio}
        entry["outer_potential_mV"] = end["readouts"]["outer_potential_mV"]
        entry["K_P"] = end["readouts"]["K_P"]
        entry["meets_drift_rule"] = bool(worst < 1.0)
        entry["worst_drift_over_tenth_band"] = worst
        out[seg] = entry
    return out
