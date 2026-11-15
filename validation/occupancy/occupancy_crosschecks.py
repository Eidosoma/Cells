"""Cross-checks and the numerical floor of the site-occupancy references (FR-3), for their usage
note.

    python -m validation.occupancy.occupancy_crosschecks --out DIR [--quick]

Writes DIR/crosschecks.json (every measured number) and DIR/log.txt. Every world is synthetic,
built here from docs/SITE_OCCUPANCY_DESIGN.md §8.3's descriptions. Measured:
* Q1: R-ode against R-qss at epsilon = 0.1, 0.01, 0.001 (the order in epsilon), with R-ode's floor
  (Radau rtol 1e-12, DOP853 rtol 1e-13 and DOP853 rtol 3e-14 against each other), per observable;
  Q1's world at alpha = 1/2 (copies given, so S carries alpha);
* Q2: R-eq against R-ode in a large node, a small node and two cells' populations facing one
  node, with the depletion quadratic and Langmuir's isotherm (with its depletion term);
* Q3: the fixed-c and closed-node forms against R-ode;
* Q4: the accessibility signatures on the reference side (equilibrium theta(alpha)/theta(1),
  saturation at alpha, the relaxation rate) at c << K_d and c = 100 K_d;
* R-dG: random states (the ledger, the 50-digit dG, the branches, the heat sign), the forced
  quadrature branch, and consecutive half-steps against R-ode under dt refinement (orders).
A few minutes on one free core (--quick: fewer states, shorter horizons).
"""

import argparse
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import scipy

from validation.occupancy import site_bookings as sb
from validation.occupancy import site_closed as sc
from validation.occupancy import site_equilibrium as se
from validation.occupancy import site_reference as sr

RT = 2.5775  # pJ/fmol, synthetic input (310 K with R = 8.3145)
TRACE = 1e-15
LOG = []


def log(*parts):
    line = " ".join(str(p) for p in parts)
    LOG.append(line)
    print(line, flush=True)


def q1(eps, alpha=1.0, *, k_on=1e4, k_off=10.0, k_int=10.0, V=1.0, c0=1e-3):
    """Q1's world: epsilon sets the copies at alpha = 1; alpha < 1 keeps the copies, so S and
    epsilon scale by alpha (Q4's 'Q1's world at alpha = 1/2')."""
    K_M = (k_off + k_int) / k_on
    copies = eps * V * (K_M + c0) * sr.N_F
    theta0 = c0 / (K_M + c0)  # the quasi-steady occupancy at c0, whatever S
    if alpha == 1.0:
        pop = sr.Population("ecs", k_on, k_off, sites_fmol=copies / sr.N_F,
                            initial_occupancy=theta0, k_int_per_s=k_int, receiving="cell")
    else:
        pop = sr.Population("ecs", k_on, k_off, copies=copies, sites_per_copy=1,
                            accessible_fraction=alpha, initial_occupancy=theta0,
                            k_int_per_s=k_int, receiving="cell")
    w = sr.World(RT, nodes={"ecs": sr.Node(V, c0 * V), "cell": sr.Node(2.0, TRACE * 2.0)},
                 populations={"r": pop}, trace_mM=TRACE)
    return w, pop.S, sc.sink_constants(pop.S, V, k_on, k_off, k_int)


def part_q1(quick):
    out = {}
    errs = {}
    for eps in (1e-1, 1e-2, 1e-3):
        w, S, k = q1(eps)
        n0 = 1e-3
        T = 2 * sc.sink_half_time(n0, k["a"], k["b"])
        rec = tuple(np.linspace(0, T, 21 if quick else 41)[1:])
        runs = {}
        for label, kw in (("radau_1e-12", dict(method="Radau", rtol=1e-12)),
                          ("dop853_1e-13", dict(method="DOP853", rtol=1e-13)),
                          ("dop853_3e-14", dict(method="DOP853", rtol=3e-14,
                                                atol_fraction=1e-9))):
            t0 = time.perf_counter()
            runs[label] = sr.integrate(w, T, record=rec, **kw)
            runs[label].wall = time.perf_counter() - t0
        base = runs["dop853_3e-14"]
        floors = {label: {key: v / (n0 if key in ("n", "U") else S if key in ("B", "R") else 1.0)
                          for key, v in sr.compare(r, base, rec).items()}
                  for label, r in runs.items() if r is not base}
        err = max(abs(runs["radau_1e-12"].at[t]["n_fmol"]["ecs"]
                      - sc.sink_amount(t, n0, k["a"], k["b"])) for t in rec) / n0
        errs[eps] = err
        last = runs["radau_1e-12"].at[rec[-1]]
        out[f"eps={eps:g}"] = dict(
            S_fmol=S, horizon_s=T, qss_error_of_n0=err, floors_relative=floors,
            steps={k_: r.steps for k_, r in runs.items()},
            wall_s={k_: r.wall for k_, r in runs.items()},
            closure_pJ=last["closure_pJ"], material_residual_fmol=last["material_residual_fmol"],
            heat_pJ=last["heat_pJ"], work_pJ=last["work_pJ"])
        log("Q1 eps", eps, "qss error", f"{err:.4e}", "floors", floors)
    out["order_in_eps"] = [math.log10(errs[1e-1] / errs[1e-2]), math.log10(errs[1e-2] / errs[1e-3])]
    log("Q1 order in eps", out["order_in_eps"])
    # Q1's world at alpha = 1/2 (copies fixed, so S and epsilon halve), each against R-qss with
    # V_max scaled by alpha and K_M unchanged (§2.3's sink signature): the error is O(epsilon).
    out["alpha"] = {}
    for alpha in (1.0, 0.5):
        w, S, k = q1(0.1, alpha)
        T = 2 * sc.sink_half_time(1e-3, k["a"], k["b"])
        rec = tuple(np.linspace(0, T, 21)[1:])
        run = sr.integrate(w, T, record=rec, method="DOP853", rtol=1e-13)
        err = max(abs(run.at[t]["n_fmol"]["ecs"] - sc.sink_amount(t, 1e-3, k["a"], k["b"]))
                  for t in rec) / 1e-3
        out["alpha"][f"{alpha:g}"] = dict(S_fmol=S, epsilon=sc.epsilon(S, 1.0, 1e4, 10.0, 10.0,
                                                                     1e-3),
                                          V_max_fmol_per_s=k["a"], K_M_mM=k["K_M"],
                                          qss_error_of_n0=err, horizon_s=T)
    out["alpha"]["error_ratio_1_over_half"] = (out["alpha"]["1"]["qss_error_of_n0"]
                                               / out["alpha"]["0.5"]["qss_error_of_n0"])
    log("Q1 at alpha 1/2", out["alpha"])
    return out


def part_q2_q3(quick):
    out = {}
    # Q2: large V, small V, two cells' populations facing one node.
    worlds = {
        "large_V": sr.World(RT, nodes={"n": sr.Node(1e4, 1e-3 * 1e4)},
                            populations={"p": sr.Population("n", 1e3, 1.0, sites_fmol=1e-4)}),
        "small_V": sr.World(RT, nodes={"n": sr.Node(0.5, 3e-4)},
                            populations={"p": sr.Population("n", 1e3, 1.0, sites_fmol=4e-4)}),
        "two_cells_one_node": sr.World(
            RT, nodes={"ecs": sr.Node(1.0, 2e-4)},
            populations={"c0": sr.Population("ecs", 2e3, 1.0, sites_fmol=3e-4,
                                             initial_occupancy=0.2),
                         "c1": sr.Population("ecs", 5e2, 0.1, sites_fmol=1e-4)}),
    }
    for name, w in worlds.items():
        eq = se.equilibrium(w)
        T = 300.0
        run = sr.integrate(w, T, record=(T,), method="DOP853", rtol=1e-13)
        rec = run.at[T]
        out[name] = dict(
            B_rel_diff={k: rec["B_fmol"][k] / eq["B_fmol"][k] - 1 for k in w.populations},
            heat_rel_diff=rec["heat_pJ"] / eq["heat_pJ"] - 1, heat_pJ=eq["heat_pJ"],
            langmuir_at_start=eq["langmuir_at_start"], depletion_term=eq["depletion_term"],
            occupancy=eq["occupancy"])
        if len(w.populations) == 1:
            p = next(iter(w.populations.values()))
            node = w.nodes[p.facing]
            rm, _ = sc.depletion_roots(node.ligand_fmol, p.S, p.K_d, node.volume_pL)
            out[name]["quadratic_rel_diff"] = eq["B_fmol"][next(iter(w.populations))] / rm - 1
        log("Q2", name, out[name])
    # Q3: closed node (Riccati) and fixed-c forms against R-ode.
    kon, koff, V, S, n0 = 1e3, 1.0, 0.5, 4e-4, 3e-4
    w = worlds["small_V"]
    rec = (0.001, 0.01, 0.1, 1.0, 5.0, 30.0)
    run = sr.integrate(w, 30.0, record=rec)
    out["riccati_max_abs_of_S"] = max(
        abs(run.at[t]["B_fmol"]["p"] - float(sc.depletion(t, 0.0, n0, S, V, kon, koff,
                                                            exact=True))) for t in rec) / S
    Vb, c, Sb, kint = 1e4, 2e-3, 1e-4, 0.5
    wf = sr.World(RT, nodes={"big": sr.Node(Vb, c * Vb), "cell": sr.Node(1.0, 1e-6)},
                  populations={"p": sr.Population("big", kon, koff, sites_fmol=Sb,
                                                  k_int_per_s=kint, receiving="cell")})
    runf = sr.integrate(wf, 3.0, record=(0.5, 3.0), method="DOP853", rtol=1e-13)
    out["internalisation_fixed_c"] = dict(
        B_max_abs_of_S=max(abs(runf.at[t]["B_fmol"]["p"] - sc.internalisation_fixed(
            t, 0.0, Sb, c, kon, koff, kint)[0]) for t in (0.5, 3.0)) / Sb,
        depletion_term=sc.depletion_term(Sb, Vb, koff / kon, c))
    log("Q3", out["riccati_max_abs_of_S"], out["internalisation_fixed_c"])
    return out


def part_q4(quick):
    out = {}
    kon, koff, copies, V = 1e3, 1.0, 1e5, 1e5  # K_d = 1e-3 mM; S/V tiny (depletion ~1e-12)
    for label, c in (("c<<K_d", 1e-6), ("c=100K_d", 0.1)):
        theta = {}
        rates = {}
        for alpha in (1.0, 0.5, 0.25):
            w = sr.World(RT, nodes={"n": sr.Node(V, c * V)},
                         populations={"p": sr.Population("n", kon, koff, copies=copies,
                                                         sites_per_copy=1,
                                                         accessible_fraction=alpha)})
            eq = se.equilibrium(w)
            theta[alpha] = eq["B_fmol"]["p"] / (copies / sr.N_F)  # bound per declared site
            run = sr.integrate(w, 1.0 / (kon * c + koff), record=(1.0 / (kon * c + koff),),
                               method="DOP853", rtol=1e-13)
            B1 = run.at[1.0 / (kon * c + koff)]["B_fmol"]["p"]
            rates[alpha] = -math.log(1 - B1 / eq["B_fmol"]["p"]) * (kon * c + koff) ** -1
        out[label] = dict(theta_ratio={a: theta[a] / theta[1.0] for a in theta},
                          saturation={a: theta[a] for a in theta},
                          relaxation_rate_ratio={a: rates[a] / rates[1.0] for a in rates},
                          depletion_term=copies / sr.N_F / (V * (koff / kon + c)))
        log("Q4", label, out[label])
    return out


def part_rdg(quick):
    out = {}
    w = sr.World(RT, nodes={"ecs": sr.Node(1.0, 1e-3), "cell": sr.Node(2.0, 2e-4)},
                 populations={"r": sr.Population("ecs", 1e4, 10.0, sites_fmol=3e-4,
                                                 initial_occupancy=0.3, k_int_per_s=10.0,
                                                 receiving="cell"),
                              "q": sr.Population("cell", 5e3, 2.0, sites_fmol=1e-4)})
    L = sb.Layout(w)
    rng = np.random.default_rng(2026)
    eps = float(np.finfo(float).eps)
    worst_ledger = worst_exact = 0.0
    min_heat = math.inf
    counts = {}
    admitted = 0
    for trial in range(400 if quick else 4000):
        n = np.array([10 ** rng.uniform(-5, -2), 10 ** rng.uniform(-6, -3)])
        B = L.S * rng.uniform(0, 1, 2)
        if trial % 7 == 0:
            B[0] = 0.0
        if trial % 5 == 0:  # near the binding equilibrium, to reach the reversing branch
            c = n[0]
            B[0] = L.S[0] * c / (10.0 / 1e4 + c) * (1 + rng.uniform(-1e-3, 1e-3))
        mb, mi = rng.choice([0.0, 0.5, 1.0], 2), rng.choice([0.0, 1.0], 2)
        st = sb.half_step(w, n, B, L.S - B, 10 ** rng.uniform(-6, -2.5), mb, mi)
        if not st.admitted:
            continue
        admitted += 1
        for b in st.branch:
            counts[b] = counts.get(b, 0) + 1
        scale = np.maximum(st.delta_G_terms + st.heat_terms, 1e-30)
        worst_ledger = max(worst_ledger, float(np.max(np.abs(st.ledger_residual) / (eps * scale))))
        exact = sb.exact_delta_G(w, n, B, L.S - B, *st.delta)
        worst_exact = max(worst_exact, max(abs(float(exact[c]) - st.delta_G[c])
                                           / (eps * max(st.delta_G_terms[c], 1e-30))
                                           for c in range(L.components)))
        if np.any(st.heat != 0):
            min_heat = min(min_heat, float(np.min(st.heat / scale[0])))
    out["random"] = dict(admitted=admitted, branches=counts,
                         worst_ledger_eps_scale=worst_ledger, worst_exact_dG_eps_terms=worst_exact,
                         smallest_heat_over_scale=min_heat)
    log("R-dG random", out["random"])
    # Convergence to R-ode at eps = 0.1 and 0.01.
    out["orders"] = {}
    for eps_ in (0.1, 0.01):
        wq, S, _ = q1(eps_)
        T = 0.128
        ref = sr.integrate(wq, T, record=(T,), method="DOP853", rtol=3e-14,
                           atol_fraction=1e-9).at[T]
        rows = []
        for dt in (8e-3, 4e-3, 2e-3, 1e-3):
            run = sb.run_half_steps(wq, dt / 2, int(round(2 * T / dt)))
            rows.append(dict(dt=dt, n_err_of_n0=abs(run.n[-1, 0] - ref["n_fmol"]["ecs"]) / 1e-3,
                             heat_err=abs(run.heat[-1].sum() - ref["heat_pJ"]),
                             work_err=abs(run.work[-1, 0] - ref["work_pJ"]),
                             branches=sorted({b for bs in run.branches for b in bs})))
        out["orders"][f"eps={eps_:g}"] = rows
        log("R-dG orders", eps_, [(r["dt"], f"{r['n_err_of_n0']:.3e}", f"{r['heat_err']:.3e}")
                                  for r in rows])
    # Per node and per population: the two-population mixed world (heat at each facing node,
    # work per population), and a washout through the binding equilibrium (one quadrature step
    # per run; §3.3's reversal onset, documented and not judged).
    T = 0.064
    ref = sr.integrate(w, T, record=(T,), method="DOP853", rtol=3e-14,
                       atol_fraction=1e-9).at[T]
    rows = []
    for dt in (8e-3, 4e-3, 2e-3, 1e-3, 5e-4):
        run = sb.run_half_steps(w, dt / 2, int(round(2 * T / dt)))
        rows.append(dict(dt=dt, heat_err_by_node={x: abs(run.heat[-1, i]
                                                         - ref["heat_by_node_pJ"][x])
                                                  for i, x in enumerate(L.nodes)},
                         work_err_by_population={p: abs(run.work[-1, k]
                                                        - ref["work_by_population_pJ"][p])
                                                 for k, p in enumerate(L.pops)}))
    out["two_populations_mixed"] = dict(horizon_s=T, rows=rows)
    log("R-dG two populations", [(r["dt"], r["heat_err_by_node"]) for r in rows])
    kon, koff, kint, S = 1e4, 10.0, 50.0, 3e-4
    c = 1e-6
    B_eq = S * c / (koff / kon + c)
    ww = sr.World(RT, nodes={"ecs": sr.Node(1.0, c), "cell": sr.Node(1.0, 1e-4)},
                  populations={"r": sr.Population("ecs", kon, koff, sites_fmol=S,
                                                  initial_occupancy=1.5 * B_eq / S,
                                                  k_int_per_s=kint, receiving="cell")})
    T = 0.04
    ref = sr.integrate(ww, T, record=(T,), method="DOP853", rtol=3e-14,
                       atol_fraction=1e-9).at[T]
    rows = []
    for dt in (4e-3, 2e-3, 1e-3, 5e-4):
        run = sb.run_half_steps(ww, dt / 2, int(round(2 * T / dt)))
        branches = [b for bs in run.branches for b in bs]
        rows.append(dict(dt=dt, quadrature_steps=branches.count("quadrature"),
                         n_err_of_n0=abs(run.n[-1, 0] - ref["n_fmol"]["ecs"]) / c,
                         heat_err=abs(run.heat[-1].sum() - ref["heat_pJ"]),
                         work_err=abs(run.work[-1, 0] - ref["work_pJ"])))
    out["washout_quadrature"] = dict(horizon_s=T, heat_pJ=ref["heat_pJ"],
                                     work_pJ=ref["work_pJ"], rows=rows)
    log("R-dG washout", rows)
    return out


def provenance():
    root = Path(__file__).resolve().parents[2]

    def git(*args):
        try:
            return subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                                  text=True, timeout=30, check=False).stdout.strip()
        except OSError:
            return ""

    return dict(git_revision=git("rev-parse", "HEAD") or None,
                git_status=git("status", "--porcelain", "--", "validation/occupancy") or None,
                python=sys.version, numpy=np.__version__, scipy=scipy.__version__,
                platform=platform.platform())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", required=True)
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    result = dict(kind="cells.occupancy_reference_crosschecks@1", quick=args.quick,
                  provenance=provenance(), rt_pJ_per_fmol=RT)
    for name, part in (("q1", part_q1), ("q2_q3", part_q2_q3), ("q4", part_q4),
                       ("r_dg", part_rdg)):
        t0 = time.perf_counter()
        result[name] = part(args.quick)
        log(name, f"done in {time.perf_counter() - t0:.1f} s")
        result["wall_s"] = time.perf_counter() - started
        (out / "crosschecks.json").write_text(json.dumps(result, indent=1, default=float) + "\n")
        (out / "log.txt").write_text("\n".join(LOG) + "\n")
    log("wrote", out / "crosschecks.json")


if __name__ == "__main__":
    main()
