"""Development evidence for the lead's items 2-3 (15 November 2026): an engine part's records
against R-closure at the same records, with the judge's own arithmetic, and the engine part's
ledgers as the judge reads them. Analysis only, from an execution snapshot's root (it ran from
fr45/pipeline/ until it moved here, its logic unchanged):

    python -m validation.compartment_ph.compare_reference RESULTS PART WORLD OUT_JSON
        [--lag-horizon T]

WORLD: `declared` (R-closure on FR-4's declared world, the reference stage's base_world) or `k2b`
(K2(b), the same world with the pump's two sides exchanged: ph_reference.Pump.reversed_sides).
R-closure is integrated at the reference stage's rtol to the part's last record, recorded at the
part's records. Differences are the judge's max-norm differences on shared integer-second
records (compartment_ph_judge.max_abs_difference) and J4's pH over both buffered nodes
(ph_max_abs, the lead's ruling); each with its record, and the first records at or beyond J4's
budget (1e-3) and K2's catch (2e-3). With --lag-horizon T, R-closure's trajectory of WORLD to T s
(every 1 s) gives the closure's lag estimate at each record and node, (beta/ln10 - h) /
(h ln10 lambda/rho), rapid_proton_buffer.lag_estimate_ph's formula at the record's rates: the
envelope's prediction over the full horizon, with the cytosol's band and |dG_cyc/RT| beside it.
"""

import argparse
import dataclasses
import json
import math
import time
from pathlib import Path

from validation.compartment_ph import ph_reference as ph
from validation.compartment_ph.parameters import World
from validation.tissue import compartment_ph_judge as judge
from validation.tissue import compartment_ph_reference_stage as stage

OBSERVABLES = ("pH_L", "pH_c", "V_b", "K_L", "K_c", "Heq_L", "Heq_c", "cycles", "work_pJ",
               "heat_pJ")
PH_NODES = ("pH_L", "pH_c")
BUDGET, CATCH = 1e-3, 2e-3
LN10 = math.log(10.0)


def world(name):
    base = stage.base_world(World())
    if name == "k2b":
        return dataclasses.replace(base, pump=dataclasses.replace(base.pump, reversed_sides=True))
    if name != "declared":
        raise SystemExit(f"WORLD is declared or k2b, not {name!r}")
    return base


def reference(name, times):
    started = time.perf_counter()
    run = ph.integrate(world(name), times[-1], record=times, rtol=stage.RTOL)
    part = dict(record_s=times, series=stage.ph_series(run, times), completed=True)
    return part, run, time.perf_counter() - started


def detail(eng, ref, name):
    if not judge.usable(eng, name) or not judge.usable(ref, name):
        return None
    a, b = judge.aligned(eng, ref, name)
    shared = sorted({round(t) for t in eng["record_s"]} & {round(t) for t in ref["record_s"]})
    diffs = [abs(x - y) for x, y in zip(a, b, strict=True)]
    k = max(range(len(diffs)), key=diffs.__getitem__)
    out = dict(max_abs=diffs[k], at_s=shared[k], engine=a[k], reference=b[k],
               last=dict(t_s=shared[-1], engine=a[-1], reference=b[-1], abs=diffs[-1]))
    assert out["max_abs"] == judge.max_abs_difference(eng, ref, name)
    if name in PH_NODES:
        out["first_at_or_beyond_budget_s"] = next(
            (t for t, d in zip(shared, diffs, strict=True) if d >= BUDGET), None)
        out["first_at_or_beyond_catch_s"] = next(
            (t for t, d in zip(shared, diffs, strict=True) if d >= CATCH), None)
    return out


def lag_prediction(name, horizon):
    times = [float(t) for t in range(int(horizon) + 1)]
    started = time.perf_counter()
    run = ph.integrate(world(name), horizon, record=times, rtol=stage.RTOL)
    worst = dict(cytosol=(0.0, None), lumen=(0.0, None))
    band, dg = (0.0, None), (0.0, None)
    for t in times:
        o = run.at[t]
        for i, node in enumerate(("cytosol", "lumen")):
            h = o["h_c"] if i == 0 else o["h_L"]
            ratio, beta = o["envelope_ratio"][i], o["buffer_capacity"][i]
            lag = 0.0 if math.isinf(ratio) else (beta / LN10 - h) / (h * LN10 * ratio)
            if lag > worst[node][0]:
                worst[node] = (lag, t)
        if abs(o["pH_c"] - 7.2) > band[0]:
            band = (abs(o["pH_c"] - 7.2), t)
        if abs(o["dG_cyc"]) / run.model.rt > dg[0]:
            dg = (abs(o["dG_cyc"]) / run.model.rt, t)
    return dict(world=name, horizon_s=horizon, records=len(times),
                max_lag_ph={k: dict(value=v, at_s=t) for k, (v, t) in worst.items()},
                lag_budget_ph=BUDGET, cytosol_band_max=dict(value=band[0], at_s=band[1]),
                dG_cyc_over_RT_max=dict(value=dg[0], at_s=dg[1]),
                pH_L_end=run.at[times[-1]]["pH_L"], seconds=time.perf_counter() - started)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("results", type=Path)
    parser.add_argument("part")
    parser.add_argument("world")
    parser.add_argument("out_json", type=Path)
    parser.add_argument("--lag-horizon", type=float)
    args = parser.parse_args(argv)
    data = json.loads(args.results.read_text())
    eng = data["parts"][args.part]
    protocol = json.loads(Path(stage.__file__).resolve().parents[1].joinpath(
        "compartment_ph", "protocols", "fr4_acidification_v1.json").read_text())
    d = protocol["judge"]["derivation"]
    out = dict(results=str(args.results), part=args.part, world=args.world,
               engine_source=data.get("source"), quick=data.get("quick"), path=data.get("path"),
               admitted=eng.get("admitted"), completed=eng.get("completed"),
               refusal=eng.get("refusal"), steps=eng.get("steps"),
               engine_seconds=eng.get("seconds"), budget_pH=BUDGET, catch_pH=CATCH)
    if eng.get("record_s"):
        times = [float(round(t)) for t in eng["record_s"]]
        ref, _, seconds = reference(args.world, times)
        out["reference_seconds"] = seconds
        out["differences"] = {x: detail(eng, ref, x) for x in OBSERVABLES}
        out["pH_max_abs_over_nodes"] = judge.ph_max_abs(eng, ref, PH_NODES)
        parts = {args.part: eng}
        out["ledgers"] = dict(
            material=judge.material(parts, [args.part], d),
            charge_over_tolerance=judge.charge(parts, [args.part]),
            energy_over_flows=judge.energy_over_flows(eng),
            envelope=judge.envelope(parts, [args.part]),
            cytosol_band_max_deviation=judge.cytosol_band(parts, [args.part], d["cytosol_pH"]),
            heat_monotone=all(b >= a - 1e-12 for a, b in zip(
                eng["series"]["heat_pJ"], eng["series"]["heat_pJ"][1:], strict=False)))
    if args.lag_horizon:
        out["lag_prediction"] = lag_prediction(args.world, args.lag_horizon)
    args.out_json.write_text(json.dumps(out, indent=1, allow_nan=False, default=float) + "\n")
    print(json.dumps({k: out.get(k) for k in ("part", "world", "pH_max_abs_over_nodes")}))
    for x, v in (out.get("differences") or {}).items():
        print(x, None if v is None else {k: v[k] for k in v if k != "last"})
    print("ledgers", json.dumps(out.get("ledgers", {}).get("material", {}).get(
        "max_over_allowance")), out.get("ledgers", {}).get("charge_over_tolerance"),
        out.get("ledgers", {}).get("energy_over_flows"), out.get("ledgers", {}).get("envelope"))
    if "lag_prediction" in out:
        print("lag", json.dumps(out["lag_prediction"]))


if __name__ == "__main__":
    main()
