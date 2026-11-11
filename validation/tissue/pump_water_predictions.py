"""Predictions P1-P6 for resolved_pump_water@1 from the independent reduced reference.

Computed before any engine qualification run (validation/tissue/pump_water_reference.py;
no Cells code is imported) and frozen with the definitions they belong to, so the
judged engine runs use exactly these worlds:

P1  ideal osmometer: a heredity cell with every ion route closed, K = P0 = 0,
    aquaporin Pf 0.05 cm/s; the exact solution V(t) and V_inf = N / c_bath.
P2  heredity cell (held bath, approved parameters):
    states   stationary states with water (H, U, D), and the arms K = P0 = 0 and
             impermeant P at 100 mM;
    window   the number of stationary states along the Na-leak scale;
    from_H   the trajectory from the fixed-volume H state with water released at t = 0;
    from_D   the same from the fixed-volume D state.
P3  the stationary identity V = (N_P + (I + q/F - X)/2) / ((c_b + dP/RT)/2 - M_b e^{F Vm/RT})
    (isolated cells and uniform sheets; evaluated on engine stationary states).
P4  seven-cell gated held-bath sheet, centre in D, ring in H: per-cell V(t) and Vm(t).
P5  a cell and a finite outside node (the gauge) with every ion route closed, no bath:
    closed volume and the closed equilibrium N_c / V_c = N_o / V_o.
P6  heredity cell with water blocked and released off the step grid.

Usage: python -m validation.tissue.pump_water_predictions --output DIR [--parts ...]
"""

import argparse
import copy
import json
import math
import time
import traceback
from pathlib import Path

import numpy as np
from scipy import optimize

from validation.tissue import pump_water_fixtures as fixtures
from validation.tissue import pump_water_reference as ref

AQUAPORIN_PF = 5e-4  # 0.05 cm/s
PARTS = ("P1", "P2", "P4", "P5", "P6")


def closed_ions(raw):
    raw = copy.deepcopy(raw)
    for key in ("membrane_controls", "pump_controls", "channel_controls"):
        for group in raw["experiment"][key]:
            group["schedule"] = [dict(time=0.0, availability=0.0)]
    return raw


def trajectory(raw, times, *, method="Radau"):
    r = ref.Reference(raw)
    started = time.perf_counter()
    values = r.integrate(max(times), times, method=method)
    out = {f"{t:.6f}": r.observe(y) for t, y in values.items()}
    return out, time.perf_counter() - started


def p1():
    end = 4.0
    raw = closed_ions(
        fixtures.with_water(
            fixtures.heredity_cell("H", end_time=end),
            pf_m_s=AQUAPORIN_PF,
            bulk_modulus_Pa=0.0,
            pressure_offset_Pa=0.0,
        )
    )
    times = [0.0, 0.5, 1.0, 2.0, end]
    raw["experiment"]["observation_times"] = times
    r = ref.Reference(raw)
    v0 = float(r.volume0[0])
    n = float(np.sum(r.amount0[:, 0]))
    c = float(np.sum(r.out_amount0[:, 0]) / r.out_volume0[0])
    a = float(r.conductance[0]) * ref.R * r.w.temperature

    def exact(t):
        def elapsed(v):
            return -((v - v0) + (n / c) * math.log((n - c * v) / (n - c * v0))) / (a * c) - t

        if t == 0:
            return v0
        final = n / c
        return optimize.brentq(elapsed, final + 1e-12 * (v0 - final), v0, xtol=1e-17, rtol=1e-15)

    return dict(
        definition=raw,
        cell_volume_pL={f"{t:.6f}": exact(t) for t in times},
        final_volume_pL=n / c,
        method="exact inverse t(V) of dV/dt = a (N/V - c), brentq",
    )


def stationary(raw):
    states = ref.cell_stationary_states(raw)
    v0 = raw["model"]["cells"][0]["volume_pL"]
    return [
        dict(
            membrane_voltage_V=vm,
            concentration_mM=conc,
            volume_pL=volume,
            volume_ratio=volume / v0,
            osmolarity_mM=osm,
        )
        for vm, conc, volume, osm in states
    ]


def low_impermeant(raw, millimolar=100.0):
    """The heredity cell with impermeant P at `millimolar` (charge balanced by the background)."""
    raw = copy.deepcopy(raw)
    cell = raw["model"]["cells"][0]
    old = cell["initial_amount_fmol"]["P"]
    new = millimolar * cell["volume_pL"]
    cell["initial_amount_fmol"]["P"] = new
    # Keep the cell's charge: the background absorbs the change of P (z = -1).
    cell["fixed_charge_equivalent_fmol"] += new - old
    return raw


def p2():
    base = fixtures.with_water(fixtures.heredity_cell("H"))
    out = dict(
        states=dict(
            approved=stationary(base),
            modulus_and_offset_zero=stationary(
                fixtures.with_water(
                    fixtures.heredity_cell("H"), bulk_modulus_Pa=0.0, pressure_offset_Pa=0.0
                )
            ),
            impermeant_100_mM=stationary(low_impermeant(base)),
        ),
        definition=base,
    )
    window = []
    for scale in (0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5, 0.6):
        raw = copy.deepcopy(base)
        raw["model"]["membranes"][0]["permeability_m_per_s"]["Na"] *= scale / 0.2
        states = stationary(raw)
        window.append(
            dict(
                na_leak_scale=scale,
                count=len(states),
                voltages_V=[s["membrane_voltage_V"] for s in states],
                volume_ratios=[s["volume_ratio"] for s in states],
            )
        )
    out["window"] = window
    times = [0.0, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0]
    for name in ("H", "D"):
        raw = fixtures.with_water(fixtures.heredity_cell(name, end_time=times[-1]))
        raw["experiment"]["observation_times"] = times
        values, seconds = trajectory(raw, times)
        out["from_" + name] = dict(definition=raw, observations=values, reference_seconds=seconds)
    return out


def p4():
    times = [0.0, 5.0, 10.0, 20.0, 30.0, 60.0]
    raw = fixtures.with_water(fixtures.gated_sheet(end_time=times[-1]))
    raw["experiment"]["observation_times"] = times
    values, seconds = trajectory(raw, times)
    return dict(definition=raw, observations=values, reference_seconds=seconds)


def closed_pair(end):
    """A heredity-sized cell and a 0.5 pL finite outside node (the gauge), ions closed."""
    raw = fixtures.heredity_cell("H", end_time=end)
    m = raw["model"]
    z = {s["id"]: s["valence"] for s in m["species"]}
    cell, outside = m["cells"][0], m["extracellular"][0]
    cell["initial_charge_C"] = 0.0
    cell["fixed_charge_equivalent_fmol"] = -sum(
        z[s] * a for s, a in cell["initial_amount_fmol"].items()
    )
    outside.update(
        reservoir=False,
        volume_pL=0.5,
        initial_amount_fmol={s: 0.5 * a for s, a in outside["initial_amount_fmol"].items()},
    )
    outside["fixed_charge_equivalent_fmol"] = -sum(
        z[s] * a for s, a in outside["initial_amount_fmol"].items()
    )
    m["closure"]["gauge_reference"] = outside["id"]
    return closed_ions(
        fixtures.with_water(raw, pf_m_s=AQUAPORIN_PF, bulk_modulus_Pa=0.0, pressure_offset_Pa=0.0)
    )


def p5():
    times = [0.0, 0.5, 1.0, 2.0, 4.0]
    raw = closed_pair(times[-1])
    raw["experiment"]["observation_times"] = times
    values, seconds = trajectory(raw, times, method="DOP853")
    r = ref.Reference(raw)
    nc, no = float(np.sum(r.amount0[:, 0])), float(np.sum(r.out_amount0[:, 0]))
    total = float(r.volume0[0] + r.out_volume0[0])
    return dict(
        definition=raw,
        observations=values,
        closed_total_volume_pL=total,
        equilibrium_cell_volume_pL=total * nc / (nc + no),
        reference_seconds=seconds,
    )


def p6():
    times = [0.0, 1.0, 2.0005, 3.0, 4.0003, 6.0, 8.0]
    raw = fixtures.with_water(
        fixtures.heredity_cell("H", end_time=times[-1]),
        pf_m_s=AQUAPORIN_PF,
        availability=[(0.0, 1.0), (2.0005, 0.0), (4.0003, 1.0)],
    )
    raw["experiment"]["observation_times"] = times
    values, seconds = trajectory(raw, times)
    return dict(definition=raw, observations=values, reference_seconds=seconds)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--parts", nargs="*", default=list(PARTS))
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    result = dict(
        reference="validation/tissue/pump_water_reference.py (numpy/scipy, no Cells code)",
        tolerances=dict(radau_rtol=1e-11, atol=1e-15),
        identity_P3=(
            "V = (N_P + (I + q/F - X)/2) / ((c_b + dP/RT)/2 - M_b exp(F Vm / RT)); "
            "isolated cells and uniform sheets whose anion M has passive routes only"
        ),
    )
    try:
        for part in args.parts:
            started = time.perf_counter()
            result[part] = globals()[part.lower()]()
            result[part]["seconds"] = time.perf_counter() - started
            (out / "predictions.json").write_text(json.dumps(result, indent=2) + "\n")
    except Exception:
        (out / "failure.json").write_text(
            json.dumps(dict(parts=list(result), traceback=traceback.format_exc()), indent=2) + "\n"
        )
        raise


if __name__ == "__main__":
    main()
