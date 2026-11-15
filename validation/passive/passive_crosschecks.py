"""Cross-checks of the passive permeation law's closed-pair reference, for its usage note.

    python -m validation.passive.passive_crosschecks --out DIR

Writes DIR/crosschecks.json and DIR/log.txt:
* a start-ratio sweep c_a0/c_b0 from 1 through near-equal starts (1 + 1e-8, 1 + 1e-3) to 1e12
  (a trace start): the closed form (float; its heat also in eps x its rounding scale) and the
  integration (Radau rtol 1e-12, DOP853 rtol 1e-13) against the 50-digit closed form, for the
  amounts and the heat, with the integration's closure H + dG and material residual;
* the closed test's properties: zero flux at equal concentrations with unequal volumes, reversal
  and antisymmetry, heat monotone and non-negative, the relaxation's total heat;
* the per-step heat against 50 digits on random steps, trace to large amounts;
* R-tissue's static entry point on the coordinator's world (two cells joined by a junction, a
  z = 0 species permeant only there, a trace in the bath) against the closed form.
About ten seconds on one core.
"""

import argparse
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import scipy

from validation.passive import passive_reference as pr

RT = 2.5775
V_A, V_B, PA = 2.0, 0.75, 3e-18
LOG = []


def log(*parts):
    line = " ".join(str(p) for p in parts)
    LOG.append(line)
    print(line, flush=True)


def sweep():
    out = {}
    k = pr.rate_constant(PA, V_A, V_B)
    times = (0.01 / k, 0.5 / k, 1.0 / k, 3.0 / k)
    for ratio in (1.0, 1.0 + 1e-8, 1.0 + 1e-3, 1e2, 1e4, 1e8, 1e12):
        n_a0, n_b0 = 1.0 * V_A, 1.0 / ratio * V_B
        world = pr.World(RT, {"a": pr.Compartment(V_A, n_a0), "b": pr.Compartment(V_B, n_b0)},
                         {"j": pr.Route("a", "b", PA)})
        row = {}
        for label, kw in (("closed_form", None), ("radau_1e-12", dict(method="Radau", rtol=1e-12)),
                          ("dop853_1e-13", dict(method="DOP853", rtol=1e-13))):
            run = None if kw is None else pr.integrate(world, times[-1], record=times, **kw)
            worst = dict(n_a=0.0, n_b=0.0, heat=0.0, closure=0.0, material=0.0,
                         heat_eps_scale=0.0)
            for t in times:
                ex = pr.exact_closed_pair(t, n_a0, n_b0, V_A, V_B, PA, RT)
                if run is None:
                    got = pr.closed_pair(t, n_a0, n_b0, V_A, V_B, PA, rt=RT)
                    na, nb, heat = got["n_a"], got["n_b"], got["heat_pJ"]
                    worst["heat_eps_scale"] = max(worst["heat_eps_scale"], abs(
                        heat - float(ex["heat"])) / (np.finfo(float).eps
                                                     * max(got["heat_scale_pJ"], 1e-300)))
                else:
                    r = run.at[t]
                    na, nb, heat = r["n_fmol"]["a"], r["n_fmol"]["b"], r["heat_pJ"]
                    worst["closure"] = max(worst["closure"], abs(r["closure_pJ"])
                                           / (RT * (n_a0 + n_b0)))
                    worst["material"] = max(worst["material"], abs(r["material_residual_fmol"])
                                            / (n_a0 + n_b0))
                worst["n_a"] = max(worst["n_a"], abs(na / float(ex["n_a"]) - 1))
                worst["n_b"] = max(worst["n_b"], abs(nb / float(ex["n_b"]) - 1))
                h = float(ex["heat"])
                worst["heat"] = max(worst["heat"], abs(heat - h) / h if h > 0 else abs(heat))
            row[label] = dict(worst_relative=worst, steps=None if run is None else run.steps)
        out[f"{ratio:g}"] = row
        log("sweep", ratio, {k_: v["worst_relative"] for k_, v in row.items()})
    return out


def properties():
    eq = pr.closed_pair(50.0, 0.5, 1.0, 1.0, 2.0, PA, rt=RT)
    fwd = pr.closed_pair(10.0, 2.0, 0.3, V_A, V_B, PA, rt=RT)
    rev = pr.closed_pair(10.0, 0.3, 2.0, V_B, V_A, PA, rt=RT)
    k = pr.rate_constant(PA, V_A, V_B)
    heats = [pr.closed_pair(t, 2.0, 0.3, V_A, V_B, PA, rt=RT)["heat_pJ"]
             for t in np.linspace(0, 5 / k, 101)]
    out = dict(equal_concentration_flux=eq["flux_fmol_per_s"],
               equal_concentration_heat=eq["heat_pJ"],
               forward_flux=fwd["flux_fmol_per_s"], swapped_flux=rev["flux_fmol_per_s"],
               antisymmetric=fwd["flux_fmol_per_s"] == -rev["flux_fmol_per_s"],
               heat_monotone=all(b >= a for a, b in zip(heats, heats[1:], strict=False)),
               heat_min=min(heats), relaxation_heat_pJ=pr.equilibrium(2.0, 0.3, V_A, V_B,
                                                                     rt=RT)["heat_pJ"])
    log("properties", out)
    return out


def steps():
    rng = np.random.default_rng(15)
    worst = 0.0
    for _ in range(5000):
        a = 10 ** rng.uniform(-15, 1, 2)
        V = 10 ** rng.uniform(-1, 1, 2)
        d = rng.uniform(-0.5, 0.5) * min(a)
        heat, scale = pr.step_heat(a, (-d, d), V, RT)
        exact = float(pr.exact_step_heat(a, (-d, d), V, RT))
        worst = max(worst, abs(heat - exact) / (np.finfo(float).eps * scale))
    out = dict(random_steps=5000, worst_eps_scale=worst)
    log("steps", out)
    return out


def r_tissue():
    from validation.division import cleft_tissue_reference as rt

    sp, z = ("Na", "K", "Cl", "X"), (1, 1, -1, 0)
    leak = (1e-10, 2e-9, 5e-10, 0.0)
    P_X, A_e = 1e-7, 1e-11
    world = rt.World(
        temperature_K=300.0, bath_mM=(140.0, 5.0, 145.0, 1e-15), species=sp, z=z,
        cells={"a": rt.CellSpec(volume_pL=V_A, mM=(12.0, 140.0, 30.0, 1.0), initial_V=-0.06),
               "b": rt.CellSpec(volume_pL=V_B, mM=(14.0, 135.0, 32.0, 1e-3), initial_V=-0.05)},
        patches={"a.m": rt.PatchSpec("a", "bath", leak, area_m2=4e-10, capacitance_F=4e-12),
                 "b.m": rt.PatchSpec("b", "bath", leak, area_m2=4e-10, capacitance_F=4e-12)},
        contacts={"e": rt.ContactSpec(("a", "b"), (2e-7, 3e-7, 4e-7, P_X), area_m2=A_e)})
    k = pr.rate_constant(P_X * A_e, V_A, V_B)
    times = (0.1 / k, 1.0 / k, 3.0 / k)
    small = dict(cell_charge=1e-15, cleft_charge=1e-17, cell_amount=1e-14, cleft_amount=1e-14,
                 heat=1e-15)
    run = rt.simulate_static(world, times[-1], record=times, atol=small)
    rows = []
    for t in times:
        cf = pr.closed_pair(t, 1.0 * V_A, 1e-3 * V_B, V_A, V_B, P_X * A_e)
        rows.append(dict(t=t, a=run.at[t]["cells"]["a"]["amounts_fmol"][3] / cf["n_a"] - 1,
                         b=run.at[t]["cells"]["b"]["amounts_fmol"][3] / cf["n_b"] - 1))
    log("r_tissue", rows)
    return dict(rows=rows, steps=run.steps)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[2]
    rev = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True,
                         text=True, check=False).stdout.strip()
    started = time.perf_counter()
    # Run from a frozen snapshot folder (not a checkout), git_revision is None: the snapshot's
    # SNAPSHOT.json carries the revision.
    result = dict(kind="cells.passive_reference_crosschecks@1", git_revision=rev or None,
                  python=sys.version, numpy=np.__version__, scipy=scipy.__version__,
                  platform=platform.platform(), rt_pJ_per_fmol=RT)
    for name, part in (("sweep", sweep), ("properties", properties), ("steps", steps),
                       ("r_tissue", r_tissue)):
        result[name] = part()
    result["wall_s"] = time.perf_counter() - started
    (out / "crosschecks.json").write_text(json.dumps(result, indent=1, default=float) + "\n")
    (out / "log.txt").write_text("\n".join(LOG) + "\n")
    log("wrote", out / "crosschecks.json")


if __name__ == "__main__":
    main()
