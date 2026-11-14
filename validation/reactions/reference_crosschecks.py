"""Cross-checks of the independent references against the design note's development numbers, and
the measurements behind the usage note's tolerances.

The note's probes (docs/SHARED_INVENTORY_REACTIONS_DESIGN.md §3.3, §10) ran a prototype that
shares the operator's scheme and author; they are development evidence, not references of
record. This driver re-derives the fully specified ones with the independent references
(validation/reactions/*_reference.py) and records the agreement, so that a disagreement shows
up as a finding rather than being resolved by reading code. It also measures:
* the float increment form against the 50-digit evaluator, over every law;
* the spread between two correct float implementations of the half-step (different but
  equally valid evaluation orders), the scale of rounding differences an engine comparison
  will see;
* the dissipation integral's agreement between two tolerances;
* the linearisation error of MG0c's 2x2 mode propagators for single-mode starts.

Usage: python -m validation.reactions.reference_crosschecks --out DIR  (writes
crosschecks.json and crosschecks.txt; about a minute on one core).
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

from validation.reactions import chain_reference as cr
from validation.reactions import dissipation_reference as dr
from validation.reactions import network_reference as nr
from validation.reactions import turing_reference as tu

RT = 2.5773  # pJ/fmol at 310 K (Appendix A's orientation value).
EPS = float(np.finfo(float).eps)
LINES = []


def say(text=""):
    LINES.append(text)
    print(text, flush=True)


def ab_network(K, k_f, sink=None):
    species = (nr.Species("A", 0.0, {"M": 1}), nr.Species("B", -math.log(K), {"M": 1}))
    reactions = [nr.Reaction("ab", "passive", {"A": 1}, {"B": 1}, k_f_per_s=k_f)]
    if sink is not None:
        reactions.append(nr.Reaction("sink", "mass_action", {"A": 1}, {}, rate_constant=sink))
    return nr.Network(species=species, reactions=tuple(reactions))


def enzyme_network():
    """Probe 2d: passive E + S <=> C (k_on 1e3 /mM/s, K_d 1e-3 mM), driven C -> E + P (1/s)."""
    species = (
        nr.Species("E", 0.0, {"E": 1}),
        nr.Species("S", 0.0, {"S": 1}),
        nr.Species("C", math.log(1e-3), {"E": 1, "S": 1}),
        nr.Species("P", 0.0, {"S": 1}),
    )
    reactions = (
        nr.Reaction("bind", "passive", {"E": 1, "S": 1}, {"C": 1}, k_f_per_s=1e3),
        nr.Reaction("cat", "mass_action", {"C": 1}, {"E": 1, "P": 1}, rate_constant=1.0),
    )
    return nr.Network(species=species, reactions=reactions)


def onset_world():
    """Probe 2g: passive R + L <=> C (k_on 1e3, K_d 1e-3 mM), driven source 0 -> L (1e-2 mM/s)."""
    species = (
        nr.Species("R", 0.0, {"R": 1}),
        nr.Species("L", 0.0, {"L": 1}),
        nr.Species("C", math.log(1e-3), {"R": 1, "L": 1}),
    )
    reactions = (
        nr.Reaction("bind", "passive", {"R": 1, "L": 1}, {"C": 1}, k_f_per_s=1e3),
        nr.Reaction("source", "mass_action", {}, {"L": 1}, rate_constant=1e-2),
    )
    return nr.Network(species=species, reactions=reactions)


def pct(x):
    return 100.0 * float(x)


# ------------------------------------------------------------------------------- parts


def mg0c():
    say("== MG0c (§6.4): the dispersion design, non-dimensional (a = 0.1, b = 0.9, d = 10)")
    J = tu.schnakenberg_jacobian(0.1, 0.9)
    an = tu.turing_analysis(J, 1.0, 10.0)
    say(f"uniform state {tu.schnakenberg_uniform_state(0.1, 0.9)}; J = {J.tolist()}")
    say(
        f"trace {an['trace']:.6g}, det {an['determinant']:.6g}; d_c {an['critical_ratio']:.6f}; "
        f"band {an['band'][0]:.15g} .. {an['band'][1]:.15g}"
    )
    say(
        f"sigma_max {an['sigma_max']:.8f} at k2 {an['k2_fastest']:.8f} (note: 0.0572 at 0.3186); "
        f"wavelength {an['wavelength']:.5f} l; e-fold {1 / (0.1 * an['sigma_max']):.2f} s"
    )
    domains = {}
    for L in (6, 8, 11, 16, 22):
        m = tu.domain_modes(J, 1.0, 10.0, L, 0.5)
        adm = tu.admissible_unstable_modes(J, 1.0, 10.0, L, 0.5)
        domains[L] = {
            "admissible": adm,
            "sigma_discrete": m["sigma_discrete"][:6].tolist(),
            "sigma_continuum": m["sigma_continuum"][:6].tolist(),
            "k2_shortfall": (1 - m["k2_discrete"] / m["k2_continuum"])[:6].tolist(),
        }
        say(
            f"L/l = {L:2d} (N = {2 * L}): admissible {adm}; sigma_n (discrete) "
            f"{np.round(m['sigma_discrete'][:6], 5).tolist()}"
        )
    lengths = np.arange(4.0, 31.0, 0.5)
    cont = tu.staircase(J, 1.0, 10.0, lengths)
    disc = tu.staircase(J, 1.0, 10.0, lengths, 0.5)
    say("staircase (continuum): " + ", ".join(f"{L:g}:{n}" for L, n in cont))
    say(
        "discrete (h = l/2) differs at: "
        + str([(L, a, b) for (L, a), (_, b) in zip(cont, disc, strict=True) if a != b])
    )
    lam = cr.chain_eigenvalues(22, 0.5)
    b1 = {}
    for n in range(1, 7):
        ev = np.linalg.eigvals(0.1 * (J - lam[n] * np.diag([1.0, 10.0])))
        b1[n] = [complex(e) for e in ev]
        say(f"L/l = 11, mode {n}: eigenvalues (1/s, k = 0.1) {np.round(ev, 6).tolist()}")
    return {
        "analysis": {k: (list(v) if isinstance(v, tuple) else v) for k, v in an.items()},
        "domains": domains,
        "staircase_continuum": cont,
        "staircase_discrete": disc,
        "b1_eigenvalues": {n: [[e.real, e.imag] for e in v] for n, v in b1.items()},
    }


def probe_2d():
    say("\n== Probe 2d (§3.3): the mixed-node onset, enzyme recipe at one 1 pL node")
    net = enzyme_network()
    rows, whole = [], {}
    for trace in (1e-12, 1e-9, 1e-6):
        n0 = np.array([1e-4, 1e-3, trace, trace])
        true5 = dr.integrate_node(net, n0, 1.0, RT, [5.0])
        whole[trace] = float(true5.heat[0, 0])
        for h in (0.05, 0.025, 0.0125):
            st = nr.half_step(net, n0, 1.0, h, RT)
            true_h = dr.integrate_node(net, n0, 1.0, RT, [h])
            run = nr.run_half_steps(net, n0, 1.0, h, int(round(5.0 / h)), RT)
            row = {
                "trace_mM": trace,
                "h": h,
                "branch": str(st.branch[0, 0]),
                "first_H_hybrid": pct(st.heat[0] / true_h.heat[0, 0] - 1),
                "first_H_quadrature": pct(st.heat_quadrature[0, 0] / true_h.heat[0, 0] - 1),
                "whole_H_5s_hybrid": pct(run.heat[-1, 0] / true5.heat[0, 0] - 1),
                "whole_W_5s_hybrid": pct(run.work[-1, 0] / true5.work[0, 0] - 1),
                "whole_H_5s": float(run.heat[-1, 0]),
                "quadrature_steps": int(sum((b[0] == "quadrature").any() for b in run.branches)),
            }
            rows.append(row)
            say(
                f"trace {trace:g}, h {h}: first H {row['first_H_hybrid']:+.3f}% (share), "
                f"quadrature {row['first_H_quadrature']:+.2f}%; whole H at 5 s "
                f"{row['whole_H_5s_hybrid']:+.4f}%, W {row['whole_W_5s_hybrid']:+.4f}%; "
                "steps on the quadrature: "
                f"{row['quadrature_steps']}"
            )
    hyb = {r["trace_mM"]: r["whole_H_5s"] for r in rows if r["h"] == 0.025}
    sens = {
        "true_1e-12_to_1e-9": whole[1e-9] - whole[1e-12],
        "hybrid_1e-12_to_1e-9": hyb[1e-9] - hyb[1e-12],
        "true_1e-9_to_1e-6": whole[1e-6] - whole[1e-9],
        "hybrid_1e-9_to_1e-6": hyb[1e-6] - hyb[1e-9],
    }
    say(
        "trace sensitivity at h = 0.025, 5 s (pJ; note: true -6.27e-5 and -2.21e-2, attribution "
        "-6.32e-5 and -2.21e-2): " + ", ".join(f"{k} {v:.3g}" for k, v in sens.items())
    )
    return {"rows": rows, "true_whole_H_5s": whole, "trace_sensitivity": sens}


def _share_minimum(net, h, lo=1e-6, hi=1.0):
    from scipy.optimize import minimize_scalar

    grid = np.geomspace(lo, hi, 4001)
    steps = [nr.half_step(net, [1 + e, 1.0], 1.0, h, RT) for e in grid]
    shares = np.array([st.heat_share[0, 0] for st in steps])
    hybrid_min = float(np.min([st.heat[0] for st in steps]))
    k = int(np.argmin(shares))
    res = minimize_scalar(
        lambda e: nr.half_step(net, [1 + e, 1.0], 1.0, h, RT).heat_share[0, 0],
        bounds=(grid[max(k - 1, 0)], grid[min(k + 1, grid.size - 1)]),
        method="bounded",
        options={"xatol": 1e-15},
    )
    return float(res.x), float(res.fun), hybrid_min


def probe_2e():
    say(
        "\n== Probes 2e/2f (§3.3): the crossing, passive A <=> B (K = 1, k_p = 1) with a sink, "
        "1 fmol"
    )
    rows = []
    for kd in (1.0, 10.0):
        net = ab_network(1.0, 1.0, kd)
        for hL in (0.05, 0.1, 0.2, 0.5):
            h = hL / (kd + 1.0)
            eps, share, hybrid_min = _share_minimum(net, h)
            st = nr.half_step(net, [1 + eps, 1.0], 1.0, h, RT)
            true = dr.integrate_node(net, st.start, 1.0, RT, [h]).heat[0, 0]
            row = {
                "k_d": kd,
                "hL": hL,
                "most_negative_share_pJ": share,
                "start_offset": eps,
                "true_step_heat_pJ": float(true),
                "branch": str(st.branch[0, 0]),
                "hybrid_vs_true": pct(st.heat[0] / true - 1),
                "smallest_hybrid_heat_in_sweep_pJ": hybrid_min,
            }
            rows.append(row)
            say(
                f"k_d {kd:g}, h L {hL}: most negative share {share:.3g} pJ (offset {eps:.4g}); "
                f"true {true:.3g} pJ; hybrid ({row['branch']}) {row['hybrid_vs_true']:+.1f}%; "
                "smallest "
                f"hybrid heat over the sweep {hybrid_min:.3g} pJ"
            )
    return {"rows": rows}


def probe_2g():
    say("\n== Probe 2g (§3.3): the reversal onset, R + L <=> C with a source 0 -> L, 1 pL")
    net = onset_world()
    rows = []
    for trace in (1e-12, 1e-9, 1e-6):
        n0 = np.array([1e-3, trace, 1e-4])
        whole = dr.integrate_node(net, n0, 1.0, RT, [1.0])
        for h in (0.025, 0.0125, 0.00625):
            st = nr.half_step(net, n0, 1.0, h, RT)
            true = dr.integrate_node(net, n0, 1.0, RT, [h]).heat[0, 0]
            run = nr.run_half_steps(net, n0, 1.0, h, int(round(1.0 / h)), RT)
            row = {
                "trace_mM": trace,
                "h": h,
                "branch_step1": str(st.branch[0, 0]),
                "first_H_hybrid": pct(st.heat[0] / true - 1),
                "share_alone_first": pct(st.heat_share[0, 0] / true - 1),
                "whole_H_1s_hybrid": pct(run.heat[-1, 0] / whole.heat[0, 0] - 1),
                "whole_H_1s": float(run.heat[-1, 0]),
                "true_whole_H_1s": float(whole.heat[0, 0]),
            }
            rows.append(row)
            say(
                f"trace {trace:g}, h {h}: step 1 {row['branch_step1']}; first H "
                f"{row['first_H_hybrid']:+.0f}%; share alone {row['share_alone_first']:+.0f}%; "
                "whole H at 1 s "
                f"{row['whole_H_1s_hybrid']:+.3f}%"
            )
    by = {(r["trace_mM"], r["h"]): r for r in rows}
    sens_h = by[(1e-9, 0.0125)]["whole_H_1s"] - by[(1e-12, 0.0125)]["whole_H_1s"]
    sens_t = by[(1e-9, 0.0125)]["true_whole_H_1s"] - by[(1e-12, 0.0125)]["true_whole_H_1s"]
    say(
        f"trace 1e-12 -> 1e-9 at h = 0.0125: hybrid {sens_h:.3g} pJ, true {sens_t:.3g} pJ "
        "(note: -1.3e-3 and -1.4e-7)"
    )
    return {"rows": rows, "trace_sensitivity_hybrid": sens_h, "trace_sensitivity_true": sens_t}


def probe_2c():
    say("\n== Probe 2c (§4.2): the stage condition on a reverse-running A <=> B (K = 10)")
    net = ab_network(10.0, 1.0)
    n0 = np.array([1e-4, 1.0])
    rows = []
    for x in (0.05, 0.1, 0.25, 0.5, 0.54, 0.55, 0.56, 0.9, 1.1, 1.5, 3.0):
        st = nr.half_step(net, n0, 1.0, x / 1.1, RT)
        dev0 = n0[1] - 10 * n0[0]
        dev1 = st.end[1, 0] - 10 * st.end[0, 0]
        rows.append(
            {
                "h_kf_plus_kr": x,
                "admitted": st.admitted,
                "stage_condition_ok": st.stage_condition_ok,
                "positive_ok": st.positive_ok,
                "hL_max": st.hL_max,
                "deviation_ratio": float(dev1 / dev0),
                "exact_ratio": math.exp(-x),
                "heat_pJ": float(st.heat[0]),
            }
        )
        say(
            f"h(kf + kr) {x:4}: admitted {st.admitted!s:5} (stage {st.stage_condition_ok!s:5}, "
            f"positive {st.positive_ok!s:5}), h L {st.hL_max:.4f}, R {dev1 / dev0:.4f} "
            f"(exact {math.exp(-x):.4f}), heat {st.heat[0]:.3g} pJ"
        )
    return {"rows": rows}


def b4_b7_b9():
    say("\n== B4, B7 and B9 at one node")
    net = ab_network(10.0, 1.0)
    run = nr.run_half_steps(net, [1.0, 1.0], 1.0, 0.05, 4000, RT)
    end = run.amounts[-1, :, 0]
    smallest = float(run.step_heat.min())
    say(
        f"B4: c_B/c_A after 200 s at h = 0.05: {end[1] / end[0]!r} (K = 10); smallest step heat "
        f"{smallest:.3g} pJ"
    )
    first = slice(0, 20)  # B7: the relaxation's first 20 half-steps, before equilibrium.
    chem_only = (-run.chemical[1:, 0] + run.chemical[:-1, 0])[first]
    with_std = run.step_heat[first, 0]
    say(
        f"B7: from equal amounts, the first 20 step heats with the standard term >= "
        f"{with_std.min():.3g} pJ; without it (H = -d chemical) min {chem_only.min():.3g} pJ, "
        f"first {chem_only[0]:.3g} pJ"
    )
    species = (nr.Species("A"),)
    P, k, n0, T = 2e-3, 0.5, 1e-3, 4.0
    lin = nr.Network(
        species=species,
        reactions=(
            nr.Reaction("make", "mass_action", {}, {"A": 1}, rate_constant=P),
            nr.Reaction("clear", "mass_action", {"A": 1}, {}, rate_constant=k),
        ),
    )
    exact = dr.turnover_amount(n0, P, k, T)
    errs = [
        abs(nr.run_half_steps(lin, [n0], 1.0, h, int(round(T / h)), RT).amounts[-1, 0, 0] - exact)
        / exact
        for h in (0.2, 0.1, 0.05)
    ]
    say(
        f"B9 (own world): relative errors {errs[0]:.3g}, {errs[1]:.3g}, {errs[2]:.3g}; ratios "
        f"{errs[0] / errs[1]:.2f}, {errs[1] / errs[2]:.2f}"
    )
    return {
        "b4_ratio": float(end[1] / end[0]),
        "b4_smallest_step_heat_pJ": smallest,
        "b7_min_with_standard_pJ": float(with_std.min()),
        "b7_min_without_standard_pJ": float(chem_only.min()),
        "b9_errors": errs,
    }


# ---------------------------------------------------------------------- tolerance evidence


def every_law_network(rng):
    lu = lambda lo, hi: float(10 ** rng.uniform(math.log10(lo), math.log10(hi)))  # noqa: E731
    species = (
        nr.Species("X1", rng.normal(), {"a": 1}),
        nr.Species("X2", rng.normal(), {"b": 1}),
        nr.Species("X3", rng.normal(), {"a": 1, "b": 1}),
        nr.Species("X4", rng.normal(), {"a": 1, "b": 1}),
        nr.Species("E", rng.normal(), {"e": 1}),
    )
    reactions = (
        nr.Reaction("bind", "passive", {"X1": 1, "X2": 1}, {"X3": 1}, k_f_per_s=lu(0.1, 10)),
        nr.Reaction("iso", "passive", {"X3": 1}, {"X4": 1}, k_f_per_s=lu(0.1, 10)),
        nr.Reaction(
            "source",
            "mass_action",
            {},
            {"X1": 1},
            rate_constant=lu(1e-4, 1e-2),
            factors=(nr.Factor("hill_activation", "X4", lu(1e-4, 1e-2), lu(0.5, 4)),),
        ),
        nr.Reaction(
            "sink",
            "mass_action",
            {"X4": 1},
            {},
            rate_constant=lu(0.1, 2),
            factors=(nr.Factor("hill_inhibition", "X2", lu(1e-4, 1e-2), lu(0.5, 4)),),
        ),
        nr.Reaction(
            "third",
            "mass_action",
            {"X1": 2, "X2": 1},
            {"X1": 1, "X3": 1},
            rate_constant=lu(1e2, 1e5),
        ),
        nr.Reaction(
            "catalysed",
            "michaelis_menten",
            {"X4": 1},
            {"X1": 1, "X2": 1},
            k_cat_per_s=lu(0.1, 10),
            K_M_mM=lu(1e-4, 1e-2),
            catalyst="E",
        ),
        nr.Reaction(
            "saturable_sink",
            "michaelis_menten",
            {"X3": 1},
            {},
            V_max_mM_per_s=lu(1e-5, 1e-3),
            K_M_mM=lu(1e-4, 1e-2),
        ),
    )
    return nr.Network(species=species, reactions=reactions, c0_mM=lu(0.1, 10))


def variant_half_step(net, n, V, h, m):
    """A second correct float implementation: exp-log mass action, J+ - J- for passive routes,
    Shu-Osher stages with the extents accumulated alongside, and per-route summation orders."""
    cn = nr.compile_network(net)

    def rates(Y):
        ln_c = np.log(Y / V)
        ln_a = np.log(Y / (V * cn.c0))
        J = np.zeros((len(cn.reactions), Y.shape[1]))
        for r, kind in enumerate(cn.law):
            if kind == nr.PASSIVE:
                J[r] = (
                    m[r]
                    * cn.k_f[r]
                    * cn.c0
                    * V
                    * (np.exp(cn.alpha[:, r] @ ln_a) - np.exp(cn.beta[:, r] @ ln_a + cn.g[r]))
                )
                continue
            F = np.ones(Y.shape[1])
            for sign, s, K, nh in cn.factors[r]:
                F = F / (1.0 + np.exp(sign * nh * (ln_c[s] - math.log(K))))
            if kind == nr.MASS_ACTION:
                J[r] = (
                    m[r]
                    * F
                    * np.exp(math.log(cn.rate_constant[r]) + np.log(V) + cn.alpha[:, r] @ ln_c)
                )
            else:
                s = cn.substrate[r]
                vmax = (
                    cn.k_cat[r] * np.exp(ln_c[cn.catalyst[r]])
                    if cn.catalyst[r] >= 0
                    else cn.V_max[r]
                )
                J[r] = m[r] * F * V * vmax / (1.0 + cn.K_M[r] / np.exp(ln_c[s]))
        return J

    J1 = rates(n)
    u1 = n + h * (cn.nu @ J1)
    J2 = rates(u1)
    u2 = 0.75 * n + 0.25 * (u1 + h * (cn.nu @ J2))
    J3 = rates(u2)
    dxi = h / 6.0 * J1 + h / 6.0 * J2 + (2.0 * h / 3.0) * J3
    delta = cn.nu @ dxi
    dG = nr.free_energy_change(net, n, delta, V, RT)
    return {
        "end": n + delta,
        "extents": dxi,
        "delta_G": dG["delta_G"],
        "gross": h * (np.abs(J1) + np.abs(J2) + 4 * np.abs(J3)) / 6.0,
    }


def tolerance_evidence():
    say("\n== Tolerance evidence")
    rng = np.random.default_rng(20261114)
    worst_dG, spread = 0.0, {"end": 0.0, "extents": 0.0, "delta_G": 0.0}
    for trial in range(60):
        net = every_law_network(rng)
        N = 4
        V = rng.uniform(0.2, 5.0, size=N)
        lo = 1e-12 if trial % 3 == 0 else 1e-5
        n = 10 ** rng.uniform(math.log10(lo), -2, size=(5, N)) * V
        h = float(10 ** rng.uniform(-4, -2))
        m = rng.uniform(0.3, 3.0, size=(7, N))
        st = nr.half_step(net, n, V, h, RT, m)
        if not st.admitted:
            continue
        ex = nr.exact_energy_change(net, n, V, RT, delta_fmol=st.delta)
        worst_dG = max(
            worst_dG, float(np.max(np.abs(st.delta_G - ex.delta_G_float) / ex.terms_float))
        )
        var = variant_half_step(net, n, V, h, m)
        gross = (
            h
            * (np.abs(st.stage_net[0]) + np.abs(st.stage_net[1]) + 4 * np.abs(st.stage_net[2]))
            / 6
        )
        gross = gross + h * np.sum(
            np.array(nr.B_WEIGHTS)[:, None, None] * (st.stage_forward + st.stage_reverse), axis=0
        )
        spread["end"] = max(spread["end"], float(np.max(np.abs(var["end"] - st.end) / st.end)))
        spread["extents"] = max(
            spread["extents"],
            float(np.max(np.abs(var["extents"] - st.extents) / np.where(gross > 0, gross, 1.0))),
        )
        spread["delta_G"] = max(
            spread["delta_G"], float(np.max(np.abs(var["delta_G"] - st.delta_G) / ex.terms_float))
        )
    say(
        f"float increment form against 50 digits: worst {worst_dG / EPS:.2f} eps of the summed "
        "|terms|"
    )
    say(
        "spread between two correct float half-steps (in eps): end amounts "
        f"{spread['end'] / EPS:.1f} (relative), extents {spread['extents'] / EPS:.1f} (of the "
        f"gross extent), dG {spread['delta_G'] / EPS:.1f} (of the summed |terms|)"
    )
    net = enzyme_network()
    n0 = np.array([1e-4, 1e-3, 1e-12, 1e-12])
    tight = dr.integrate_node(net, n0, 1.0, RT, [0.025, 0.5, 5.0])
    loose = dr.integrate_node(net, n0, 1.0, RT, [0.025, 0.5, 5.0], rtol=1e-11)
    agree = float(np.max(np.abs(loose.heat - tight.heat) / np.abs(tight.heat)))
    say(
        f"dissipation integral, rtol 1e-11 against 1e-13 (2d onset, trace 1e-12): H agrees to "
        f"{agree:.2g}; closure |W - H - dG| at most {np.max(np.abs(tight.closure)):.2g} pJ"
    )
    # MG0c Q1: the 2x2 propagator against the nonlinear chain for single-mode starts, L/l = 11.
    k, c_star, V, hsp = 0.1, 1e-3, 0.5, 5e-6
    D = np.array([1e-11, 1e-10])
    J = tu.schnakenberg_jacobian(0.1, 0.9)
    sch = tu.schnakenberg_network(0.1, 0.9, k, c_star)
    u = tu.schnakenberg_uniform_amounts(0.1, 0.9, c_star, V)
    N = 22
    lam = cr.chain_eigenvalues(N, hsp)
    q1 = {}
    for n in range(1, 7):
        ev = np.linalg.eigvals(k * J - lam[n] * np.diag(D))
        t_rec = float(min(3.0 / np.max(np.abs(ev.real)), 600.0))
        start = u[:, None] * (1.0 + 1e-7 * cr.mode_basis(N)[n][None, :])
        res = {}
        for rtol in (1e-12, 1e-13):
            tr = cr.integrate_chain(sch, start, V, hsp, D, [t_rec], rtol=rtol)
            got = cr.mode_coefficients(tr.amounts[0])[:, n]
            want = cr.mode_propagator(k * J, D, lam[n], t_rec) @ cr.mode_coefficients(start)[:, n]
            res[rtol] = float(np.max(np.abs(got - want)) / np.max(np.abs(want)))
        q1[n] = {
            "t_record_s": t_rec,
            "rel_diff_rtol_1e-12": res[1e-12],
            "rel_diff_rtol_1e-13": res[1e-13],
        }
        say(
            f"MG0c Q1, L/l = 11, mode {n} at {t_rec:.4g} s (amplitude 1e-7): 2x2 propagator "
            f"against the nonlinear chain {res[1e-12]:.2g} (rtol 1e-12), {res[1e-13]:.2g} (1e-13)"
        )
    return {
        "increment_form_worst_eps": worst_dG / EPS,
        "two_implementation_spread_eps": {k: v / EPS for k, v in spread.items()},
        "dissipation_rtol_agreement": agree,
        "mg0c_q1_linearisation": q1,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[2]

    def git(*a):
        return subprocess.run(
            ["git", "-C", str(root), *a], capture_output=True, text=True
        ).stdout.strip()

    start = time.time()
    record = {
        "kind": "reaction_references_crosschecks@1",
        "git_revision": git("rev-parse", "HEAD"),
        "git_status_porcelain": git("status", "--porcelain"),
        "python": sys.version,
        "numpy": np.__version__,
        "platform": platform.platform(),
        "RT_pJ_per_fmol": RT,
    }
    record["mg0c"] = mg0c()
    record["probe_2d"] = probe_2d()
    record["probe_2e"] = probe_2e()
    record["probe_2g"] = probe_2g()
    record["probe_2c"] = probe_2c()
    record["b4_b7_b9"] = b4_b7_b9()
    record["tolerances"] = tolerance_evidence()
    record["seconds"] = time.time() - start
    say(f"\ndone in {record['seconds']:.1f} s")
    (out / "crosschecks.json").write_text(json.dumps(record, indent=1, default=str) + "\n")
    (out / "crosschecks.txt").write_text("\n".join(LINES) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
