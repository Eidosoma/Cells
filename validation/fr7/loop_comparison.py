"""FR-7 F4's comparison: the engine's closed loop against R-loop's registered references.

R-loop is read through its interface only (validation/fr7/references/interface/, tag
fr7-references-rloop-2026-11-19; REFERENCES_USAGE.md, "How a comparison reads them"):
1. **Build F4** from interface/loop_inputs.json with loop_mapper, from the registered start.
2. **Run the closed arm** at dt = 1 ms, windowed, saving the rows. F*_engine is the engine's own
   applied loop factor at the closed arm's row t_d (the coupling's record of the c_loop route).
   It must lie within the registered bound of F*.
3. **Run the clamped arm:** the closed arm until t_d, then the coupling switched off and k_a
   stepped to k_a F*_engine.
4. **Judge both arms:** every row whose status is "compared" (interface/loop_rows.json) passes
   when |engine - value| <= band.
5. **Persistence:** N_closed - N_clamped at its registered rows, within its band.
6. **The clearance row:** D from the engine's template rows by R-clear's registered
   clearance.hill_drive and clearance.t_clear. It must give the registered row, 260 s. Those
   functions are imported from validation.fr7.references.clearance, and their code is not read
   here; before the references are on main the row is reported as pending.

**The engine's quantities at a row:**
* n_T, n_P, Na, K, M and P: the cell's amounts;
* F_T and F_loop: the coupling's observed factors at the row's own state (coupling_factor: the
  template's route, then the loop's);
* s: the regulatory state;
* N: naleak_0's units (declared plus increment);
* PA: naleak_0's P a A, from the view's current abundance;
* W and R: the producer's consumed precursor and removed units;
* C_P: turnover's cleared precursor;
* the material total: n_P + (N + R) / c_u + C_P - S_P t, with the declared c_u;
* V: the membrane voltage.

**The pump's rate** (pump_fmol_per_s) is the instantaneous cycle rate at the row's saved state. It
is computed by the engine itself: the composite's readouts at that state and its control, the
derivative of the cumulative pump_cycles (@3's pump law through its own readouts). Nothing here
re-implements the kinetics. It is cross-checked against the ledger: over each 10 s interval
between rows, the cumulative pump_cycles' difference must equal the integral of the
instantaneous rate, by Simpson's rule on states saved every SAMPLE_STEPS steps, to within
PUMP_RTOL (the step's own error at 1 ms, far below the rate's band).

Usage: loop_comparison.py OUT_JSON [--interface DIR] [--end S]
(--end runs both arms to S seconds, with t_d unchanged: a smoke check.)
Development, not judged.
"""

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import parse_spec
from cells.execution.windows import WindowPolicy, iter_windows
from cells.registry.models import get_model
from validation.fr7 import loop_mapper as lm

POLICY = WindowPolicy(window_steps=10000, recording="observations")  # Bounded memory.
SAMPLE_STEPS = 100  # States kept every 0.1 s for the pump's ledger cross-check.
PUMP_RTOL = 1e-6
OBSERVED = ("coupling_factor", "membrane_voltage_V")
LOOP_ROUTE = 1  # The coupling's routes: the template's (0), then the loop's (1).
COMPARED = (
    "n_T_fmol",
    "F_T",
    "s",
    "F_loop",
    "n_P_fmol",
    "N_units",
    "PA_units_m3_s",
    "W_fmol",
    "R_units",
    "C_P_fmol",
    "total_fmol",
    "V_V",
    "pump_fmol_per_s",
    "Na_fmol",
    "K_fmol",
    "M_fmol",
    "P_fmol",
)


def collect(spec):
    """A windowed run of `spec` (every row checked), keeping the states at its observed rows and
    every SAMPLE_STEPS steps, and the observed fields OBSERVED at its observations."""
    dt = spec.execution.dt
    observed_steps = {int(round(float(t) / dt)) for t in spec.experiment.observation_times}
    states, observed = {}, {name: [] for name in (*OBSERVED, "times")}
    for window in iter_windows(spec, POLICY):
        for i, _ in enumerate(np.asarray(window.times)):
            k = window.start_step + i
            if k in observed_steps or k % SAMPLE_STEPS == 0:
                states[k] = type(window.history)(*(np.asarray(v)[i] for v in window.history))
        obs = window.observations
        for name in observed:
            observed[name].extend(np.asarray(getattr(obs, name)))
    return states, observed


def pump_rate(model, spec, p, state, t):
    """The engine's instantaneous pump cycle rate (fmol cycles/s) at `state` and the control at
    time t: its own readouts' derivative of the cumulative pump_cycles."""
    control = model.CONTROL_TYPE(*(v[0] for v in cs.control_values(spec, [t])))
    values = model.readouts(state, control, p, xp=np)
    return float(np.asarray(values.derivative.pump_cycles)[0])


def arm_rows(spec, collected, inp):
    """(times, {quantity: [value at each row]}, the pump's ledger cross-check) of one arm."""
    loop = inp["loop"]
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    species = list(spec.model.species_ids)
    dt = spec.execution.dt
    states, observed = collected
    times = [float(t) for t in spec.experiment.observation_times]
    steps = [int(round(t / dt)) for t in times]
    if [float(t) for t in observed["times"]] != times or any(k not in states for k in steps):
        raise ValueError("the windowed run did not return every observed row")
    reference = np.asarray(p.amount_reference)
    channels = [c.id for c in spec.model.channels]
    unit_slot = channels.index(loop["units"]["id"])
    channel = spec.model.channels[unit_slot]
    area = spec.model.membranes[0].area_m2
    rho = loop["units"]["reference_density_per_m2"]
    declared = channel.abundance * area * rho
    row_p = species.index(lm.PRECURSOR)
    out = {name: [] for name in COMPARED}
    for t, k in zip(times, steps, strict=True):
        s_ = states[k]
        amounts = reference[:, 0] + np.asarray(s_.amount_increment)[:, 0]
        for sid, key in (("Na", "Na_fmol"), ("K", "K_fmol"), ("M", "M_fmol"), ("P", "P_fmol")):
            out[key].append(float(amounts[species.index(sid)]))
        out["n_T_fmol"].append(float(amounts[species.index(lm.TEMPLATE)]))
        out["n_P_fmol"].append(float(amounts[row_p]))
        n = declared + float(np.asarray(s_.population_abundance_increment)[unit_slot])
        out["N_units"].append(n)
        out["s"].append(float(np.asarray(s_.regulatory_state)[0]))
        out["W_fmol"].append(float(np.asarray(s_.unit_consumed_fmol)[0]))
        out["R_units"].append(float(np.asarray(s_.unit_removed_units)[unit_slot]))
        out["C_P_fmol"].append(float(np.asarray(s_.turnover_cleared_fmol)[row_p, 0]))
        view = model.view(p, s_, xp=np)
        abundance = float(np.asarray(view.channel_abundance)[unit_slot])
        out["PA_units_m3_s"].append(abundance * area * channel.max_permeability_m_per_s)
        out["pump_fmol_per_s"].append(pump_rate(model, spec, p, s_, t))
    c_u = loop["units"]["units_per_fmol"]
    supply = loop["start"]["supply_fmol_per_s"]
    out["total_fmol"] = [
        math.fsum((n_p, (n + r) / c_u, c_p)) - supply * t
        for t, n_p, n, r, c_p in zip(
            times, out["n_P_fmol"], out["N_units"], out["R_units"], out["C_P_fmol"], strict=True
        )
    ]
    out["F_T"] = [float(np.asarray(v)[0]) for v in observed["coupling_factor"]]
    out["F_loop"] = [float(np.asarray(v)[LOOP_ROUTE]) for v in observed["coupling_factor"]]
    out["V_V"] = [float(np.asarray(v)[0]) for v in observed["membrane_voltage_V"]]
    applied = [float(np.asarray(states[k].coupling_applied_factor)[LOOP_ROUTE]) for k in steps]
    return times, out, applied, pump_ledger(model, spec, p, states, times, steps)


def pump_ledger(model, spec, p, states, times, steps):
    """Per interval between consecutive rows that the samples tile: the cumulative pump_cycles'
    difference against Simpson's integral of the engine's instantaneous rate."""
    dt = spec.execution.dt
    out = []
    for (t0, k0), (t1, k1) in zip(
        zip(times, steps, strict=True), zip(times[1:], steps[1:], strict=True), strict=False
    ):
        grid = list(range(k0, k1 + 1, SAMPLE_STEPS))
        if (k1 - k0) % (2 * SAMPLE_STEPS) or grid[-1] != k1:
            continue  # Simpson needs an even number of sample intervals.
        rates = [pump_rate(model, spec, p, states[k], k * dt) for k in grid]
        h = SAMPLE_STEPS * dt
        integral = (
            h
            / 3
            * (rates[0] + rates[-1] + 4 * math.fsum(rates[1:-1:2]) + 2 * math.fsum(rates[2:-1:2]))
        )
        cycles = float(
            np.asarray(states[k1].pump_cycles)[0] - np.asarray(states[k0].pump_cycles)[0]
        )
        out.append(
            dict(
                from_s=t0,
                to_s=t1,
                ledger=cycles,
                integral=integral,
                relative=abs(cycles - integral) / abs(integral),
            )
        )
    return dict(
        intervals=len(out),
        worst_relative=max((r["relative"] for r in out), default=None),
        rtol=PUMP_RTOL,
        passed=bool(out) and all(r["relative"] <= PUMP_RTOL for r in out),
        rows=out,
    )


def judge(reference, times, engine):
    """Per compared quantity: the compared rows, the failures and the worst |engine - value| /
    band."""
    registered = reference["rows_s"] if "rows_s" in reference else None
    out = {}
    for q in COMPARED:
        rq = reference["quantities"].get(q)
        if rq is None or rq["cls"] != "compared":
            continue
        rows = []
        for i, t in enumerate(times):
            if t not in registered:
                continue
            j = registered.index(t)
            if rq["status"][j] != "compared":
                continue
            rows.append((t, abs(engine[q][i] - rq["value"][j]) / rq["band"][j]))
        failures = [(t, m) for t, m in rows if m > 1.0]
        worst = max(rows, key=lambda r: r[1], default=(None, 0.0))
        out[q] = dict(
            compared=len(rows),
            failed=len(failures),
            worst_margin=worst[1],
            worst_row_s=worst[0],
            failures=failures[:5],
        )
    return out


def clearance_row(inp, times, engine, registered_row):
    try:
        from validation.fr7.references import clearance  # noqa: PLC0415 (lands with them)
    except ImportError:
        return dict(status="pending: the references are not on this tree's path yet")
    loop = inp["loop"]
    factor = loop["template"]["factor"]
    drive = clearance.hill_drive(
        np.asarray(engine["n_T_fmol"]) / loop["cell"]["volume_pL"], factor["K_mM"], factor["n"]
    )
    got = clearance.t_clear(times, drive, inp["clearance"]["epsilon"])
    return dict(
        status="equal" if got == registered_row else "differs",
        engine=got,
        registered=registered_row,
    )


def load(interface):
    interface = Path(interface)
    return dict(
        inputs=lm.inputs(interface / "loop_inputs.json"),
        rows=json.loads((interface / "loop_rows.json").read_text()),
    )


def run_arm(inp, arm, *, f_star=None, end=None):
    spec = parse_spec(lm.definition(inp, arm=arm, f_star=f_star, end=end))
    started = time.perf_counter()
    collected = collect(spec)
    wall = time.perf_counter() - started
    times, engine, applied, ledger = arm_rows(spec, collected, inp)
    return dict(spec=spec, times=times, engine=engine, applied=applied, ledger=ledger, wall=wall)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out")
    parser.add_argument("--interface", default=str(lm.INTERFACE))
    parser.add_argument("--end", type=float)
    args = parser.parse_args(argv)
    refs = load(args.interface)
    inp, rows = refs["inputs"], refs["rows"]
    loop = inp["loop"]
    arms = loop["arms"]
    t_d = arms["t_d_s"]
    report = dict(
        interface=args.interface,
        pump_rate_label=(
            "pump_fmol_per_s is the instantaneous cycle rate at each row's saved state: the "
            "engine's own readouts (the derivative of pump_cycles) at that state and its control"
        ),
    )
    closed = run_arm(inp, "closed", end=args.end)
    times = closed["times"]
    f_star = None
    if t_d in times:
        f_star = closed["applied"][times.index(t_d)]
        report["F_star"] = dict(
            engine=f_star,
            registered=arms["F_star"],
            difference=f_star - arms["F_star"],
            bound=arms["F_star_bound"],
            within=abs(f_star - arms["F_star"]) <= arms["F_star_bound"],
        )
    reference = {"rows_s": rows["rows_s"], **rows["arms"]["closed"]}
    report["closed"] = dict(
        wall_s=closed["wall"],
        end_s=times[-1],
        quantities=judge(reference, times, closed["engine"]),
        pump_ledger=closed["ledger"],
        engine_rows=dict(times=times, **closed["engine"]),
    )
    report["clearance"] = (
        clearance_row(inp, times, closed["engine"], rows["persistence"]["t_clear_s"])
        if args.end is None
        else dict(status="not judged: a partial run")
    )
    print(
        "closed",
        {
            q: (v["failed"], f"{v['worst_margin']:.3g}")
            for q, v in report["closed"]["quantities"].items()
        },
        "F*",
        report.get("F_star"),
        flush=True,
    )
    Path(args.out).write_text(json.dumps(report, indent=1, default=float))
    if f_star is not None:
        clamped = run_arm(inp, "clamped", f_star=f_star, end=args.end)
        reference = {"rows_s": rows["rows_s"], **rows["arms"]["clamped"]}
        report["clamped"] = dict(
            wall_s=clamped["wall"],
            end_s=clamped["times"][-1],
            quantities=judge(reference, clamped["times"], clamped["engine"]),
            pump_ledger=clamped["ledger"],
            engine_rows=dict(times=clamped["times"], **clamped["engine"]),
        )
        persistence = rows["persistence"]
        dn = []
        for t, want, band in zip(
            persistence["rows_s"], persistence["dN_units"], persistence["band_units"], strict=True
        ):
            if t in times and t in clamped["times"]:
                got = (
                    closed["engine"]["N_units"][times.index(t)]
                    - clamped["engine"]["N_units"][clamped["times"].index(t)]
                )
                dn.append(dict(t_s=t, engine=got, registered=want, margin=abs(got - want) / band))
        report["persistence"] = dict(
            rows=dn,
            compared=len(dn),
            failed=sum(r["margin"] > 1.0 for r in dn),
            worst_margin=max((r["margin"] for r in dn), default=0.0),
        )
        print(
            "clamped",
            {
                q: (v["failed"], f"{v['worst_margin']:.3g}")
                for q, v in report["clamped"]["quantities"].items()
            },
            "persistence",
            report["persistence"]["failed"],
            flush=True,
        )
    judged = [report["closed"]["quantities"]] + (
        [report["clamped"]["quantities"]] if "clamped" in report else []
    )
    report["passed"] = (
        all(v["failed"] == 0 for q in judged for v in q.values())
        and report.get("F_star", {}).get("within", args.end is not None)
        and report.get("persistence", {}).get("failed", 0) == 0
        and report["closed"]["pump_ledger"]["passed"]
        and report.get("clamped", {}).get("pump_ledger", {}).get("passed", True)
    )
    Path(args.out).write_text(json.dumps(report, indent=1, default=float))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
