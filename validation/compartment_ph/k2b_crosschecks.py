"""K2(b)'s effect against J4, by R-closure: the self-consistent reversed pump against the declared
FR-4 world, at the reference's own resolution, before the judged run (D176's G3).

    python -m validation.compartment_ph.k2b_crosschecks --out DIR [--protocol-json PATH]

The control is fr4_acidification_v1's controls.K2_planted_sign (branch fr45-physics, e71f1200):
the declared world with its pump's two sides exchanged in the law (ph_reference.Pump's
``reversed_sides``). Both worlds are integrated over 900 s with the protocol's records (901 rows,
every 1 s). Reports the effect, max over the records of |pH(K2b) - pH(declared)| per node,
against J4's budget (1e-3) and K2's catch threshold (2e-3), with the first records that exceed
them; V_b, the lumen's K+ and the pump's cycles beside it; K2(b)'s own ledgers and its pump's
domain; and the floor (rtol 1e-11 against 1e-12). With ``--protocol-json``, the protocol file's
K2 text and records are copied into the output as the inputs. About a minute of CPU.
"""

import argparse
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
import scipy

from validation.compartment_ph import ph_reference as ph

T = 900.0
BUDGET, CATCH = 1e-3, 2e-3  # J4's budget; K2's catch threshold (the lead's ruling on Q1)
NODES = (("lumen", "pH_L"), ("cytosol", "pH_c"))
LOG = []


def log(*parts):
    line = " ".join(str(p) for p in parts)
    LOG.append(line)
    print(line, flush=True)


def records():
    return tuple(float(t) for t in range(0, int(T) + 1))  # 901 rows, every 1 s


def effect(a, b, rec, key):
    diffs = [(abs(a.at[t][key] - b.at[t][key]), t) for t in rec]
    v, t = max(diffs)
    return dict(max=v, at_s=t,
                first_at_or_above_budget_s=next((t for d, t in diffs if d >= BUDGET), None),
                first_at_or_above_catch_s=next((t for d, t in diffs if d >= CATCH), None),
                at_1s=abs(a.at[1.0][key] - b.at[1.0][key]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", required=True)
    parser.add_argument("--protocol-json", default=None)
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    rec = records()
    result = dict(kind="cells.compartment_k2b_reference_effect@1", horizon_s=T, records=len(rec),
                  budget_pH=BUDGET, catch_pH=CATCH, python=sys.version, numpy=np.__version__,
                  scipy=scipy.__version__, platform=platform.platform())
    if args.protocol_json:
        protocol = json.loads(Path(args.protocol_json).read_text())
        result["inputs"] = dict(protocol_path=args.protocol_json,
                                K2_planted_sign=protocol["controls"]["K2_planted_sign"],
                                records=protocol["world"]["records"],
                                J4_reference=protocol["criteria"]["J4_reference"])
    declared = ph.integrate(ph.acceptance_world(), T, record=rec)
    k2b = ph.integrate(ph.acceptance_world(reversed_pump=True), T, record=rec)
    result["effect"] = {name: effect(k2b, declared, rec, key) for name, key in NODES}
    log("effect", result["effect"])
    beside = {}
    for t in (1.0, 10.0, 100.0, 300.0, T):
        beside[str(t)] = {
            label: dict(pH_L=run.at[t]["pH_L"], pH_c=run.at[t]["pH_c"], Vb=run.at[t]["Vb"],
                        K_L_fmol=run.at[t]["ions_L"]["K"], cycles=run.at[t]["cycles"],
                        J_H_pump=run.at[t]["J_H_pump"])
            for label, run in (("declared", declared), ("K2b", k2b))}
    result["beside"] = beside
    log("beside", beside[str(T)])
    m = k2b.model
    K0 = m.ions0[0]["K"] + m.ions0[1]["K"]
    heat = [k2b.at[t]["heat_pJ"] for t in rec]
    result["K2b_ledgers"] = dict(
        energy_residual_max_pJ=max(abs(k2b.at[t]["energy_residual_pJ"]) for t in rec),
        work_pJ=k2b.at[T]["work_pJ"], heat_pJ=k2b.at[T]["heat_pJ"],
        heat_monotone=all(b >= a - 1e-12 for a, b in zip(heat, heat[1:], strict=False)),
        Heq_drift_max=max(abs(k2b.at[t]["Heq_c"] + k2b.at[t]["Heq_L"] - sum(m.Heq0))
                          for t in rec) / sum(m.Heq0),
        K_drift_max=max(abs(k2b.at[t]["ions_c"]["K"] + k2b.at[t]["ions_L"]["K"] - K0)
                        for t in rec) / K0,
        phi_c_max=max(abs(k2b.at[t]["phi_c"]) for t in rec),
        dG_cyc_over_RT_max=max(abs(k2b.at[t]["dG_cyc"]) for t in rec) / m.rt,
        cytosol_band_max=max(abs(k2b.at[t]["pH_c"] - 7.2) for t in rec),
        steps=k2b.steps)
    log("K2b ledgers", result["K2b_ledgers"])
    tight_d = ph.integrate(ph.acceptance_world(), T, record=rec, rtol=1e-12)
    tight_k = ph.integrate(ph.acceptance_world(reversed_pump=True), T, record=rec, rtol=1e-12)
    result["floor"] = {label: max(abs(a.at[t]["pH_L"] - b.at[t]["pH_L"]) for t in rec)
                       for label, a, b in (("declared", declared, tight_d),
                                           ("K2b", k2b, tight_k))}
    log("floor", result["floor"])
    result["wall_s"] = time.perf_counter() - started
    (out / "crosschecks.json").write_text(json.dumps(result, indent=1, default=float) + "\n")
    (out / "log.txt").write_text("\n".join(LOG) + "\n")
    log("wrote", out / "crosschecks.json")


if __name__ == "__main__":
    main()
