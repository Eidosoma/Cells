"""Cross-checks and the numerical floor of the coupling references (R-fac, R-state, R-cell and
R-feedback), for their usage note.

    python -m validation.coupling.reference_crosschecks --out DIR [--quick]

Writes DIR/crosschecks.json (every measured number) and DIR/log.txt. Every world is synthetic
(S5's style), built here. Measured:
* R-fac: the float64 path against the 40-digit path (ulps) over a grid of laws, n, K, x and b;
  the 40-digit path against the literal 60-digit formula on random points; the log-space
  conditioning guide over the same grid.
* R-state: closed forms against DOP853 (the default) and Radau, the general input against
  nested quadrature, crossing times against their closed forms, the fast arm.
* R-cell and R-feedback: the floor at the recommended settings (Radau, rtol 1e-10, default atol)
  as the distance to rtol 1e-12 with atol / 1000, and a second method (LSODA at rtol 1e-12, atol
  / 1000) against the tight Radau run, per observable, on an A4-like feedback world (also its
  fast arm, dt (k_on + k_off) = 1 at dt = 1 ms) and an A5-like gated-leak world.
About two minutes on one free core (--quick: shorter horizons, for a smoke run).
"""

import argparse
import json
import math
import platform
import subprocess
import sys
import time
from decimal import Decimal, localcontext
from pathlib import Path

import numpy as np
import scipy

from validation.coupling import cells_reference as rc
from validation.coupling import factor_reference as fr
from validation.coupling import state_reference as rs

F_SI = 6.02214076e23 * 1.602176634e-19  # exact SI products, passed in as inputs
R_SI = 6.02214076e23 * 1.380649e-23
CONST = rc.Constants(F_SI, R_SI, 300.0)
SP, Z = ("Na", "K", "Cl"), (1, 1, -1)
BATH = (140.0, 5.0, 145.0)
CYT_A, CYT_B = (12.0, 140.0, 30.0), (30.0, 120.0, 30.0)
LEAK = (1e-10, 2e-9, 5e-10)
AREA, CAP, VOL = 4e-10, 4e-12, 2.0
LOG = []


def log(*parts):
    line = " ".join(str(p) for p in parts)
    LOG.append(line)
    print(line, flush=True)


# ---------------------------------------------------------------- R-fac


def part_rfac(quick):
    x = np.concatenate([[0.0, 1e-300], np.logspace(-10, 10, 41 if quick else 81)])
    out = {}
    for law in fr.HILL_LAWS:
        for n in (0.5, 1.0, 1.7, 2.0, 3.0, 4.0, 8.0):
            worst, cond = 0, 0.0
            for K in (1e-4, 0.37, 12.0):
                for b in (0.0, 0.2):
                    exact = fr.exact_grid(law, b, x=x, K=K, n=n)
                    approx = fr.coupling_factor(law, b, x=x, K=K, n=n)
                    worst = max(worst, int(np.max(fr.ulp_distance(approx, exact))))
                cond = max(cond, float(np.max(fr.log_space_condition(law, x[1:], K, n))))
            out[f"{law} n={n}"] = dict(float_ulps_max=worst, log_space_condition_eps_max=cond)
            log("R-fac", law, n, "float path ulps", worst, "log-space guide (eps)", f"{cond:.3g}")
    rng = np.random.default_rng(11)
    rel = Decimal(0)
    for _ in range(50 if quick else 400):
        xv, K = 10.0 ** rng.uniform(-8, 8, 2)
        n = float(rng.uniform(0.3, 8.0))
        with localcontext(prec=60):
            xd, kd, nd = Decimal(xv), Decimal(K), Decimal(n)
            literal = xd**nd / (kd**nd + xd**nd)
            act = fr.exact_hill("hill_activation", xv, K, n)
            if literal > 0:
                rel = max(rel, abs(act - literal) / literal)
    out["exact_vs_literal_60_digit_relative_max"] = float(rel)
    log("R-fac exact vs literal 60-digit, max relative", f"{float(rel):.3g}")
    return out


# ---------------------------------------------------------------- R-state


def part_rstate(quick):
    out = {}
    # Frozen input.
    worst = dict(dop=0.0, radau=0.0, crossing=0.0)
    for kon, koff, u in ((50.0, 5.0, 0.6), (900.0, 100.0, 0.3), (0.2, 0.01, 0.9)):
        inputs = [rs.Input("hill_activation", rs.constant(1.0), 1.0 / u - 1.0 if u < 1 else 1.0,
                           1.0)]
        uu = float(rs.input_value(inputs, 0.0))
        T = 20.0 / (kon * uu + koff)
        record = tuple(T * f for f in (0.01, 0.1, 0.5, 1.0))
        for label, kw in (("dop", {}), ("radau", dict(method="Radau", rtol=1e-12,
                                                       atol=(1e-15, 1e-15)))):
            run = rs.integrate(inputs, kon, koff, 0.1, T, record=record, **kw)
            for t in record:
                exact = fr.to_float(rs.frozen(t, 0.1, uu, kon, koff, exact=True))
                worst[label] = max(worst[label], abs(run.at[t][0] - exact))
            if label == "dop":
                theta = 0.5 * (0.1 + float(rs.quasi_steady(uu, kon, koff)))
                worst["crossing"] = max(worst["crossing"], abs(
                    run.crossing(theta) - rs.frozen_crossing(theta, 0.1, uu, kon, koff)))
    out["frozen"] = worst
    log("R-state frozen: max |s - exact|", worst)
    # Commitment under clearance.
    worst = dict(s=0.0, U=0.0, crossing_rel=0.0, s_radau=0.0)
    for law in fr.HILL_LAWS:
        for n in (1.0, 2.5, 4.0):
            c0, k, K, kon, s0 = 2.0, 0.05, 0.7, 0.3, 0.1
            inputs = [rs.Input(law, rs.clearance(c0, k), K, n)]
            record = (1.0, 10.0, 60.0, 200.0)
            run = rs.integrate(inputs, kon, 0.0, s0, 200.0, record=record)
            radau = rs.integrate(inputs, kon, 0.0, s0, 200.0, record=record, method="Radau",
                                 rtol=1e-12, atol=(1e-15, 1e-15))
            for t in record:
                s_ex = fr.to_float(rs.clearance_commitment(t, s0, kon, c0, k, K, n, law,
                                                           exact=True))
                U_ex = fr.to_float(rs.clearance_exposure(t, c0, k, K, n, law, exact=True))
                worst["s"] = max(worst["s"], abs(run.at[t][0] - s_ex))
                worst["s_radau"] = max(worst["s_radau"], abs(radau.at[t][0] - s_ex))
                worst["U"] = max(worst["U"], abs(run.at[t][1] - U_ex))
            for theta in (0.3, 0.5):
                t_star = rs.clearance_commitment_crossing(theta, s0, kon, c0, k, K, n, law)
                if math.isfinite(t_star) and t_star < 200.0:
                    worst["crossing_rel"] = max(worst["crossing_rel"],
                                                abs(run.crossing(theta) - t_star) / t_star)
    out["commitment_clearance"] = worst
    log("R-state commitment under clearance", worst)
    # General input: a production pulse, k_off > 0.
    reg = rs.Turnover(0.5, 2.0, ((0.0, 0.0, 0.02), (5.0, 3.0, 0.02), (15.0, 0.0, 0.02)))
    inputs = [rs.Input("hill_activation", reg, 0.6, 3.0)]
    record = (2.0, 5.0, 8.0, 12.0, 15.0, 30.0)
    dop = rs.integrate(inputs, 2.0, 0.5, 0.05, 30.0, record=record)
    radau = rs.integrate(inputs, 2.0, 0.5, 0.05, 30.0, record=record, method="Radau",
                         rtol=1e-12, atol=(1e-15, 1e-15))
    quad = {t: rs.state_quadrature(inputs, 2.0, 0.5, 0.05, t) for t in record}
    out["general"] = dict(
        dop_vs_quad=max(abs(dop.at[t][0] - quad[t]) for t in record),
        radau_vs_quad=max(abs(radau.at[t][0] - quad[t]) for t in record),
        U_dop_vs_quad=max(abs(dop.at[t][1] - rs.exposure(inputs, t)) for t in record),
        crossing_dop_vs_radau=abs(dop.crossing(0.5) - radau.crossing(0.5)),
        crossing_s=dop.crossing(0.5),
    )
    log("R-state general input", out["general"])
    # The fast arm.
    reg = rs.Turnover(0.5, 2.0, ((0.0, 0.0, 0.5), (0.5, 3.0, 0.5), (1.5, 0.0, 0.5)))
    inputs = [rs.Input("hill_activation", reg, 0.6, 3.0)]
    record = (0.25, 0.75, 1.25, 2.0, 3.0)
    t0 = time.perf_counter()
    dop = rs.integrate(inputs, 900.0, 100.0, 0.05, 3.0, record=record)
    wall_dop = time.perf_counter() - t0
    t0 = time.perf_counter()
    radau = rs.integrate(inputs, 900.0, 100.0, 0.05, 3.0, record=record, method="Radau",
                         rtol=1e-12, atol=(1e-15, 1e-15))
    wall_radau = time.perf_counter() - t0
    out["fast_arm"] = dict(
        dop_vs_radau=max(abs(dop.at[t][0] - radau.at[t][0]) for t in record),
        lag_from_quasi_steady=max(abs(dop.at[t][0] - float(rs.quasi_steady(
            rs.input_value(inputs, t), 900.0, 100.0))) for t in record),
        steps_dop=dop.steps, steps_radau=radau.steps, wall_dop_s=wall_dop,
        wall_radau_s=wall_radau)
    log("R-state fast arm", out["fast_arm"])
    return out


# ---------------------------------------------------------------- R-cell and R-feedback


def feedback_world(kon=5.0, koff=0.5):
    return rc.World(
        CONST, SP, Z, BATH,
        cells={"a": rc.Cell(VOL, CYT_A, initial_V=-0.06),
               "b": rc.Cell(VOL, CYT_B, initial_V=-0.04)},
        patches={"a.m": rc.Patch("a", AREA, CAP, LEAK), "b.m": rc.Patch("b", AREA, CAP, LEAK)},
        contacts={"e": rc.Contact(("a", "b"), 1e-10, (2e-6, 3e-6, 4e-6))},
        states={"s1": rc.State(("a", "b"), (rc.Input("hill_activation", "Na", 20.0, 2.0),), kon,
                               koff, initial=0.1, crossing_level=0.5)},
        couplings={"j": rc.Coupling("e", "state_complement", "s1", basal=0.2, side="both")},
    )


def cell_world():
    reg = rs.Turnover(0.2 * VOL, VOL, ((0.0, 0.0, 0.05), (10.0, 0.4, 0.05), (30.0, 0.0, 0.05)))
    return rc.World(
        CONST, SP, Z, BATH,
        cells={"c0": rc.Cell(VOL, CYT_A, initial_V=-0.05)},
        patches={"c0.m": rc.Patch("c0", AREA, CAP, LEAK)},
        populations={"kleak": rc.Population("c0.m", 2e-8, (0.0, 1.0, 0.0))},
        regulators={"X": rc.Regulator({"c0": reg})},
        couplings={"k_reg": rc.Coupling("kleak", "hill_inhibition", "X", basal=0.1, K_mM=1.0,
                                        n=2.0)},
    )


def differences(a, b, record):
    """Max |a - b| per observable over the records (both runs at the same records)."""
    out = dict(V=0.0, amounts=0.0, mM=0.0, s=0.0, U=0.0, F=0.0, a_eff=0.0, current=0.0)
    for t in record:
        ra, rb = a.at[t], b.at[t]
        for c in ra["V"]:
            out["V"] = max(out["V"], abs(ra["V"][c] - rb["V"][c]))
            out["amounts"] = max(out["amounts"], *(abs(x - y) for x, y in
                                                   zip(ra["amounts_fmol"][c],
                                                       rb["amounts_fmol"][c], strict=True)))
            out["mM"] = max(out["mM"], *(abs(x - y) for x, y in
                                         zip(ra["mM"][c], rb["mM"][c], strict=True)))
        for k in ra["s"]:
            out["s"] = max(out["s"], abs(ra["s"][k] - rb["s"][k]))
            out["U"] = max(out["U"], abs(ra["U"][k] - rb["U"][k]))
        for k in ra["routes"]:
            out["F"] = max(out["F"], abs(ra["routes"][k]["F"] - rb["routes"][k]["F"]))
        for e in ra["elements"]:
            out["a_eff"] = max(out["a_eff"], abs(ra["elements"][e]["a_eff"]
                                                 - rb["elements"][e]["a_eff"]))
            out["current"] = max(out["current"], abs(ra["elements"][e]["current_A"]
                                                     - rb["elements"][e]["current_A"]))
    out["crossing"] = max((abs(a.crossings[k] - b.crossings[k]) for k in a.crossings),
                          default=0.0)
    return out


def part_cells(quick):
    tight = {k: v / 1000 for k, v in rc.ATOL.items()}
    worlds = {
        "A4_feedback": (feedback_world(), 10.0 if quick else 60.0),
        "A4_fast_arm": (feedback_world(900.0, 100.0), 2.0 if quick else 20.0),
        "A5_gated_leak": (cell_world(), 10.0 if quick else 60.0),
    }
    out = {}
    for name, (world, T) in worlds.items():
        record = tuple(np.linspace(0.0, T, 13)[1:])
        runs, walls = {}, {}
        for label, kw in (("recommended", {}), ("tight", dict(rtol=1e-12, atol=tight)),
                          ("lsoda", dict(rtol=1e-12, atol=tight, method="LSODA"))):
            t0 = time.perf_counter()
            runs[label] = rc.simulate(world, T, record=record, **kw)
            walls[label] = time.perf_counter() - t0
            log(name, label, f"{walls[label]:.1f} s", runs[label].steps, "steps")
        last = runs["tight"].at[record[-1]]
        out[name] = dict(
            horizon_s=T,
            floor_recommended_vs_tight=differences(runs["recommended"], runs["tight"], record),
            method_lsoda_vs_tight=differences(runs["lsoda"], runs["tight"], record),
            crossings=runs["tight"].crossings and {f"{k[0]}@{k[1]}": v for k, v in
                                                   runs["tight"].crossings.items()},
            steps={k: r.steps for k, r in runs.items()},
            wall_s=walls,
            final=dict(V=last["V"], mM={c: list(v) for c, v in last["mM"].items()},
                       s={f"{k[0]}@{k[1]}": v for k, v in last["s"].items()},
                       a_eff={e: v["a_eff"] for e, v in last["elements"].items()}),
        )
        log(name, "floor", out[name]["floor_recommended_vs_tight"])
        log(name, "lsoda", out[name]["method_lsoda_vs_tight"])
    return out


# ---------------------------------------------------------------- the driver


def provenance():
    root = Path(__file__).resolve().parents[2]

    def git(*args):
        try:
            return subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                                  text=True, timeout=30, check=False).stdout.strip()
        except OSError:
            return ""

    return dict(root=str(root), git_revision=git("rev-parse", "HEAD") or None,
                git_status=git("status", "--porcelain", "--", "validation/coupling") or None,
                python=sys.version, numpy=np.__version__,
                scipy=scipy.__version__, platform=platform.platform())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", required=True)
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    result = dict(kind="cells.coupling_reference_crosschecks@1", quick=args.quick,
                  provenance=provenance())
    for name, part in (("r_fac", part_rfac), ("r_state", part_rstate), ("cells", part_cells)):
        t0 = time.perf_counter()
        result[name] = part(args.quick)
        log(name, f"done in {time.perf_counter() - t0:.1f} s")
    result["wall_s"] = time.perf_counter() - started
    (out / "crosschecks.json").write_text(json.dumps(result, indent=1, sort_keys=True,
                                                     default=float) + "\n")
    (out / "log.txt").write_text("\n".join(LOG) + "\n")
    log("wrote", out / "crosschecks.json")


if __name__ == "__main__":
    main()
