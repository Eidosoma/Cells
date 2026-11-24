"""Every quantity SPEC §3 asks for, world by world, from SPEC.md and CRITERIA.md alone.

``compute_world`` runs R-ode (method B, Taylor in decimal, writes the values; method A,
DOP853 at rtol 1e-12 and 1e-13, gives the tolerance gap and the cross-check), R-eq
(bracket, Newton and, where it applies, Wang's closed form), R-dG, the balances, the pairs
and the plants. It returns the reference payload (SPEC §5) and, separately, the accuracy
record (normalised disagreements only).
"""

from __future__ import annotations

import decimal
import math
from decimal import Decimal
from fractions import Fraction

import fr45ref_equilibrium as EQ
import numpy as np
from fr45ref_hp import EPS, EPS_Q, ONE, ZERO, D, Q, dmax, exp, f64, fq, ln, sqrt
from fr45ref_model import C_STD, RT, System
from fr45ref_worlds import K_B_TEXT, N_A_TEXT, N_F, T_TEXT, TRACE_MM_TEXT, steps

PROFILES = {
    # working digits; (order, tolerance) of method B's fine and coarse runs; method A's two rtols.
    "reference": {
        "digits": 70,
        "fine": (40, 1e-58),
        "coarse": (32, 1e-48),
        "rtols": (1e-12, 1e-13),
    },
    # the first, 50-digit profile, kept to show which written values the precision moves
    "reference50": {
        "digits": 50,
        "fine": (32, 1e-38),
        "coarse": (24, 1e-30),
        "rtols": (1e-12, 1e-13),
    },
    "sample": {"digits": 50, "fine": (20, 1e-24), "coarse": (16, 1e-19), "rtols": (1e-12, 1e-13)},
}

BAND_C1 = D("1e-6")
BAND_C2A = D("1e-9")
INCONCLUSIVE = D("1e-10")
HALF = D("0.5")

UNITS = {
    "copies": "count (the one declared count)",
    "amount": "fmol",
    "volume": "pL",
    "concentration": "mM",
    "k_on": "per mM per s",
    "k_off": "per s",
    "time": "s",
    "free_energy_and_heat": "pJ",
    "tolerance_gap": "the observable's own unit",
    "distance_in_bounds": "multiples of the criterion's bound",
}

CLASS_NOTE = (
    "No pair is spread: nothing is drawn (SPEC.md §3.4). Trajectory pairs carry integration "
    "error and are class band, judged by their criterion's band directly, never by "
    "agreement.judge."
)


# ------------------------------------------------------------------------------------------
# R-ode


def integrate(sys: System, world: dict, profile: dict, wash_variant: bool = False):
    """Both methods over the world's observation times.

    Returns dict with 'B' (fine Taylor), 'Bc' (coarse Taylor) and 'A' {rtol: states}; each
    a list of states at [start] + times. For a wash world also the pre/post-wash states and
    the wash records per method.
    """
    times = world["times"]
    wash = world["wash"]
    y0 = sys.start()
    out = {"y0": y0}

    def run_taylor(order, tol):
        y = list(y0)
        t_prev = ZERO
        states = [list(y0)]
        nsteps = 0
        pre = post = rec = None
        for t in times:
            td = D(t)
            y, ns = sys.taylor(y, t_prev, td, order, tol, sys.taylor_scales(y))
            nsteps += ns
            states.append(list(y))
            if wash is not None and t == wash["t"]:
                pre = list(y)
                y, rec = sys.wash(y, wash, scale_bound=wash_variant)
                post = list(y)
            t_prev = td
        return {"states": states, "pre": pre, "post": post, "records": rec, "steps": nsteps}

    out["B"] = run_taylor(*profile["fine"])
    out["Bc"] = run_taylor(*profile["coarse"])
    out["A"] = {}
    for rtol in profile["rtols"]:
        # method A starts from the exact start rounded once (the anchors), so it is pure
        # binary64 and independent of the decimal working precision
        y = np.array(sys.anchors(), dtype=np.float64)
        t_prev = 0.0
        states = [y.copy()]
        pre = post = rec = None
        nfev = 0
        for t in times:
            atol = rtol * sys.atol_scale(y)
            y, nf = sys.dop853(y, t_prev, t, rtol, atol)
            nfev += nf
            states.append(y.copy())
            if wash is not None and t == wash["t"]:
                pre = y.copy()
                y = sys.wash_binary64(y, wash, scale_bound=wash_variant)
                post = y.copy()
            t_prev = t
        out["A"][rtol] = {"states": states, "pre": pre, "post": post, "records": rec, "nfev": nfev}
    return out


def s_nodes(sys: System, states) -> dict[str, Decimal]:
    """CRITERIA's s_node: largest |reference value| of any amount at the node, over the start
    (its anchors, rounded once from the exact start) and the observation times."""
    out = {}
    anchors = sys.anchors()
    for node in sys.facing_nodes():
        idx = [i for i in range(sys.n) if sys.node_of_component(i) == node]
        vals = [abs(D(anchors[i])) for i in idx]
        vals += [abs(D(f64(y[i]))) for y in states[1:] for i in idx]
        out[node] = dmax(vals)
    return out


Q_C1 = Fraction(1, 10**6)
Q_C2A = Fraction(1, 10**9)


def supplied_exact(sys: System, wash: dict, p: int) -> Fraction:
    c = [b["c"] for b in wash["buffer"] if b["ligand"] == sys.pools[p]["ligand"]][0]
    return Q(wash["f"]) * Q(sys.pools[p]["V"]) * Q(c)


# ------------------------------------------------------------------------------------------
# R-eq


def equilibrium(sys: System, N: list[Decimal]) -> dict:
    br = EQ.bracket(sys, N)
    nw = EQ.newton(sys, N)
    root = br["state"]
    w = {}
    for comp in EQ.components(sys):
        if (
            len(comp["sets"]) == 1
            and len(comp["pools"]) == 2
            and len(sys.pops_of_set[comp["sets"][0]]) == 2
        ):
            s = comp["sets"][0]
            wr = EQ.wang(sys, N, s)
            w[sys.sets[s]["id"]] = {
                "wang": wr,
                "bracket_R": br["R"][s],
                "binary64": EQ.wang_binary64(sys, N, s),
            }
    pooled = {sys.sets[s]["id"]: v for s, v in EQ.pooled(sys, N).items()}
    written = [D(f64(v)) for v in root]
    return {
        "root": root,
        "newton": nw,
        "bracket": br,
        "wang": w,
        "pooled": pooled,
        "N": N,
        "residual_written": EQ.residuals(sys, N, written),
        "residual_root": EQ.residuals(sys, N, root),
        "affinities": EQ.affinities(sys, root),
    }


def theta_both_ways(sys: System, y) -> list[tuple[Decimal, Decimal]]:
    """(formula, B_b / S_s) for each population at state y (SPEC §3.1, amendment 2).

    The user's formula theta_b = (c_b/K_b) / (1 + sum_j c_j/K_j), over the populations j of
    b's set, from the free concentrations c = n/V of the state's pools; and B_b / S_s.
    """
    x = [y[q["pool_index"]] / sys.Vd[q["pool_index"]] / sys.K[b] for b, q in enumerate(sys.pops)]
    out = []
    for b, q in enumerate(sys.pops):
        s = q["set_index"]
        den = ONE + sum((x[j] for j in sys.pops_of_set[s]), ZERO)
        out.append((x[b] / den, y[sys.i_pop(b)] / sys.Sd[s]))
    return out


def equilibrium_accuracy(sysm: System, eq: dict, snode: dict) -> dict:
    """The routes' agreement at one R-eq root, normalised by s_node (accuracy record)."""
    root = eq["root"]
    nw = eq["newton"]["state"]
    acc = {}
    acc["newton_vs_bracket"] = f64(
        dmax(abs(root[i] - nw[i]) / snode[sysm.node_of_component(i)] for i in range(sysm.n))
    )
    acc["bracket_width"] = f64(
        dmax((eq["bracket"]["width"][s] / snode[sysm.sets[s]["faces"]]) for s in range(sysm.nS))
    )
    acc["bracket_iterations"] = eq["bracket"]["iterations"]
    acc["newton_iterations"] = eq["newton"]["iterations"]
    acc["residual_root"] = {
        k: f64(v / dmax(snode.values())) for k, v in eq["residual_root"].items()
    }
    acc["residual_written"] = {
        k: f64(v / dmax(snode.values())) for k, v in eq["residual_written"].items()
    }
    acc["affinity_over_RT"] = f64(dmax(abs(a) / RT for a in eq["affinities"]))
    wg = {}
    for sid, w in eq["wang"].items():
        s = sysm.set_index[sid]
        sn = snode[sysm.sets[s]["faces"]]
        wg[sid] = {
            "gap": f64(abs(w["wang"]["R"] - w["bracket_R"]) / sn),
            "binary64_gap": f64(abs(D(w["binary64"]) - w["bracket_R"]) / sn),
            "branch": w["wang"]["branch"],
            "is_largest_root": w["wang"]["is_largest"],
            "cubic_residual_over_terms": f64(
                abs(w["wang"]["cubic_residual"]) / w["wang"]["cubic_terms"]
            ),
        }
    acc["wang"] = wg
    if eq["pooled"]:
        acc["pooled_closed_form"] = {
            sid: {
                "gap_over_s_node": f64(
                    dmax(
                        abs(v - root[i]) / snode[sysm.node_of_component(i)]
                        for i, v in pl["amounts"].items()
                    )
                )
            }
            for sid, pl in eq["pooled"].items()
        }
    return acc


def loads_max(sys: System, y, rule: str) -> Decimal:
    L = sys.loads(y)
    vals = list(L["L_n"].values()) + list(L["L_B"].values())
    vals += (
        list(L["L_R_summed"].values())
        if rule == "summed"
        else list(L["L_R_per_population"].values())
    )
    return dmax(vals)


# ------------------------------------------------------------------------------------------
# R-dG


def interval_list(world: dict):
    """(k, k+1) index pairs into [start] + times; the interval across the wash is excluded."""
    times = world["times"]
    out = []
    for k in range(len(times)):
        t_start = 0.0 if k == 0 else times[k - 1]
        if world["wash"] is not None and k > 0 and t_start == world["wash"]["t"]:
            continue
        out.append((k, k + 1))
    return out


def heat_bound(sys: System, ya, yb, node: str, delta: Decimal, E: Decimal) -> Decimal:
    total = ZERO
    for y in (ya, yb):
        for p, pool in enumerate(sys.pools):
            if pool["node"] == node:
                x = max(y[p], delta)
                total += RT * (abs(ln(x / (sys.Vd[p] * C_STD))) + 1)
        for s, st in enumerate(sys.sets):
            if st["faces"] != node:
                continue
            S = sys.Sd[s]
            x = max(y[sys.i_set(s)], delta)
            total += RT * (abs(ln(x / S)) + 1)
            for b in sys.pops_of_set[s]:
                x = max(y[sys.i_pop(b)], delta)
                total += abs(sys.mu0[b]) + RT * (abs(ln(x / S)) + 1)
    return 2 * total * delta + 16 * EPS * E


def planted_G(sys: System, y, node: str, plant: str) -> Decimal:
    """G under P3 (one-ligand lattice per population) or P6 (R term once per ligand pool)."""
    if plant == "P3":
        total = ZERO
        for p, pool in enumerate(sys.pools):
            if pool["node"] == node:
                n = y[p]
                total += RT * n * (ln(n / (sys.Vd[p] * C_STD)) - 1)
        for s, st in enumerate(sys.sets):
            if st["faces"] != node:
                continue
            S = sys.Sd[s]
            for b in sys.pops_of_set[s]:
                B = y[sys.i_pop(b)]
                F = S - B
                if B != 0:
                    total += B * (sys.mu0[b] + RT * ln(B / S))
                if F != 0:
                    total += RT * F * ln(F / S)
        return total
    if plant == "P6":
        total = sys.G(y, node)
        for s, st in enumerate(sys.sets):
            if st["faces"] != node:
                continue
            m = len({sys.pops[b]["pool_index"] for b in sys.pops_of_set[s]})
            R = y[sys.i_set(s)]
            if R != 0:
                total += (m - 1) * RT * R * ln(R / sys.Sd[s])
        return total
    raise ValueError(plant)


# ------------------------------------------------------------------------------------------
# W4's closed form


def closed_form(sys: System, y0, t: Decimal, s: int = 0):
    """B(t) = B_eq + e^(A t)(B0 - B_eq) at the start's fixed concentrations (SPEC §3.2).

    A = [[-(k1 c1 + k-1), -k1 c1], [-k2 c2, -(k2 c2 + k-2)]] has real distinct eigenvalues
    (its off-diagonal product is positive), so e^(At) follows from its two projectors.
    """
    if len(sys.pops_of_set[s]) != 2:
        raise ValueError("the closed form is for a set with two populations")
    b1, b2 = sys.pops_of_set[s]
    p1, p2 = sys.pops[b1]["pool_index"], sys.pops[b2]["pool_index"]
    S = sys.Sd[s]
    u1 = sys.kon[b1] * y0[p1] / sys.Vd[p1]
    u2 = sys.kon[b2] * y0[p2] / sys.Vd[p2]
    a11, a12 = -(u1 + sys.koff[b1]), -u1
    a21, a22 = -u2, -(u2 + sys.koff[b2])
    det = a11 * a22 - a12 * a21
    f1, f2 = S * u1, S * u2
    # B_eq = -A^{-1} (f1, f2)
    beq1 = -(a22 * f1 - a12 * f2) / det
    beq2 = -(-a21 * f1 + a11 * f2) / det
    tr = a11 + a22
    disc = sqrt(tr * tr - 4 * det)
    l1, l2 = (tr + disc) / 2, (tr - disc) / 2
    e1, e2 = exp(l1 * t), exp(l2 * t)
    # e^{At} = (e1 (A - l2 I) - e2 (A - l1 I)) / (l1 - l2)
    m11 = (e1 * (a11 - l2) - e2 * (a11 - l1)) / (l1 - l2)
    m12 = (e1 * a12 - e2 * a12) / (l1 - l2)
    m21 = (e1 * a21 - e2 * a21) / (l1 - l2)
    m22 = (e1 * (a22 - l2) - e2 * (a22 - l1)) / (l1 - l2)
    d1 = y0[sys.i_pop(b1)] - beq1
    d2 = y0[sys.i_pop(b2)] - beq2
    B1 = beq1 + m11 * d1 + m12 * d2
    B2 = beq2 + m21 * d1 + m22 * d2
    others = sum((y0[sys.i_pop(b)] for b in sys.pops_of_set[s] if b not in (b1, b2)), ZERO)
    return {"B": [B1, B2], "R": S - B1 - B2 - others}


# ------------------------------------------------------------------------------------------
# helpers


def _pair(criterion, observable, time_s, klass, value, tolerance, against, **extra):
    d = {"criterion": criterion, "observable": observable, "time_s": time_s}
    for k in ("start_s", "end_s", "dt_s"):
        if k in extra:
            d[k] = extra.pop(k)
    d.update({"class": klass, "value": value, "tolerance": tolerance, "against": against})
    d.update(extra)
    return d


# ------------------------------------------------------------------------------------------
# One world


class WorldRun:
    """Everything about one world, kept in decimal until the writer rounds it."""

    def __init__(self, world: dict, profile_name: str, criteria: list[str]):
        self.world = world
        self.profile = PROFILES[profile_name]
        self.criteria = criteria
        self.sys = System(world)
        self.obs = self.sys.observables()
        self.times = world["times"]
        self.has_traj = len(self.times) > 0
        self.acc: dict = {}
        if self.has_traj:
            self.ode = integrate(self.sys, world, self.profile)
            self.yB = self.ode["B"]["states"]
            self.snode = s_nodes(self.sys, self.yB)
        else:
            self.ode = None
            self.yB = [self.sys.start()]
            self.snode = s_nodes(self.sys, self.yB)

    # ---- R-eq ----------------------------------------------------------------------------
    def totals(self) -> list[Decimal]:
        if self.world["wash"] is not None:
            return self.sys.pool_totals(self.ode["B"]["post"])
        return self.sys.pool_totals(self.sys.start())

    def row_index(self, t: float) -> int:
        """The index of a saved row in [start] + times: 0 for the start (0.0 s)."""
        return 0 if t == 0.0 else self.times.index(t) + 1

    def compute_equilibrium(self):
        self.eq = equilibrium(self.sys, self.totals())
        root = self.eq["root"]
        acc = equilibrium_accuracy(self.sys, self.eq, self.snode)
        if self.world["wash"] is not None:
            # sensitivity of W2's root to R-ode's state at the wash: method A's state instead
            yA = self.ode["A"][self.profile["rtols"][-1]]["post"]
            NA = self.sys.pool_totals([D(float(v)) for v in yA])
            rootA = EQ.bracket(self.sys, NA)["state"]
            acc["root_from_methodA_wash_state"] = f64(
                dmax(
                    abs(root[i] - rootA[i]) / self.snode[self.sys.node_of_component(i)]
                    for i in range(self.sys.n)
                )
            )
        self.acc["equilibrium"] = acc

    def theta_section(self) -> dict:
        """SPEC §3.1 and §5 (amendment 2): each population's occupied fraction at R-eq's root,
        by the user's formula from the root's free concentrations and as B_b / S_s, and their
        gap, at the working precision. The accuracy record adds the formula from Newton's
        root and the gap at the written binary64 values."""
        sysm = self.sys
        hp = theta_both_ways(sysm, self.eq["root"])
        nw = theta_both_ways(sysm, self.eq["newton"]["state"])
        wr = theta_both_ways(sysm, [D(f64(v)) for v in self.eq["root"]])
        self.acc["equilibrium"]["theta"] = {
            "formula_vs_root_max": f64(dmax(abs(a - b) for a, b in hp)),
            "newton_formula_vs_bracket_root_max": f64(
                dmax(abs(nw[b][0] - hp[b][1]) for b in range(sysm.nB))
            ),
            "written_formula_vs_root_max": f64(dmax(abs(a - b) for a, b in wr)),
        }
        return {
            q["id"]: {
                "formula": f64(hp[b][0]),
                "root": f64(hp[b][1]),
                "gap": f64(abs(hp[b][0] - hp[b][1])),
            }
            for b, q in enumerate(sysm.pops)
        }

    def equilibrium_section(self, totals_note: str, theta: bool = False):
        root = self.eq["root"]
        sysm = self.sys
        res = self.eq["residual_written"]
        out = {
            "totals": totals_note,
            "sets": {s["id"]: f64(root[sysm.i_set(i)]) for i, s in enumerate(sysm.sets)},
            "populations": {q["id"]: f64(root[sysm.i_pop(b)]) for b, q in enumerate(sysm.pops)},
            "pools": {p["id"]: f64(root[i]) for i, p in enumerate(sysm.pools)},
            "residual": f64(dmax(res.values())),
            "residual_definition": (
                "largest |residual| in fmol of the ligand totals, set moieties and "
                "detailed balance B_b = R_s c_l / K_b, at the written binary64 values"
            ),
            "wang": {
                sid: {"gap": f64(abs(w["wang"]["R"] - w["bracket_R"]))}
                for sid, w in self.eq["wang"].items()
            },
        }
        if theta:
            out["theta"] = self.theta_section()
        return out

    # ---- R-ode outputs -------------------------------------------------------------------
    def trajectory_section(self):
        out = []
        r12, r13 = self.profile["rtols"]
        A12 = self.ode["A"][r12]["states"]
        A13 = self.ode["A"][r13]["states"]
        gap_max = ZERO
        ab_max = ZERO
        bc_max = ZERO
        above = 0
        misses = 0
        worst = ZERO
        c8 = "C8" in self.criteria
        sysm = self.sys
        for k, t in enumerate(self.times, start=1):
            for i, name in enumerate(self.obs):
                sn = self.snode[sysm.node_of_component(i)]
                gap = abs(D(float(A12[k][i])) - D(float(A13[k][i])))
                ab = abs(D(float(A13[k][i])) - self.yB[k][i])
                bc = abs(self.ode["Bc"]["states"][k][i] - self.yB[k][i])
                gap_max = max(gap_max, gap / sn)
                ab_max = max(ab_max, ab / sn)
                bc_max = max(bc_max, bc / sn)
                if gap > INCONCLUSIVE * sn:
                    above += 1
                # AMENDMENT answer 2: Taylor within tolerance_gap + 1e-12 of the pair's scale of
                # DOP853 at 1e-13: the node's scale, and S as well for C8's R and B
                scales = [sn]
                if c8 and i >= sysm.nP:
                    if i < sysm.nP + sysm.nS:
                        scales.append(sysm.Sd[i - sysm.nP])
                    else:
                        scales.append(sysm.Sd[sysm.pops[i - sysm.nP - sysm.nS]["set_index"]])
                for sc in scales:
                    allow = gap + D("1e-12") * sc
                    worst = max(worst, ab / allow)
                    if ab > allow:
                        misses += 1
                out.append(
                    {
                        "observable": name,
                        "time_s": t,
                        "value": f64(self.yB[k][i]),
                        "tolerance_gap": f64(gap),
                    }
                )
        self.acc["trajectory_convergence_requirement"] = {
            "misses": misses,
            "worst_ratio": f64(worst),
        }
        self.acc["trajectory"] = {
            "tolerance_gap_over_scale_max": f64(gap_max),
            "pairs_with_gap_above_1e-10_of_scale": above,
            "taylor_vs_dop853_rtol1e-13_over_scale_max": f64(ab_max),
            "taylor_fine_vs_coarse_over_scale_max": f64(bc_max),
            "taylor_steps": {"fine": self.ode["B"]["steps"], "coarse": self.ode["Bc"]["steps"]},
            "dop853_nfev": {repr(r): self.ode["A"][r]["nfev"] for r in self.profile["rtols"]},
        }
        if "C8" in self.criteria:
            # C8's own scale is the set's capacity S, over R and the B_b only
            g8 = ab8 = ZERO
            above8 = 0
            sysm = self.sys
            for k in range(1, len(self.times) + 1):
                for i in range(sysm.nP, sysm.n):
                    if i < sysm.nP + sysm.nS:
                        s = i - sysm.nP
                    else:
                        s = sysm.pops[i - sysm.nP - sysm.nS]["set_index"]
                    S = sysm.Sd[s]
                    gap = abs(D(float(A12[k][i])) - D(float(A13[k][i])))
                    g8 = max(g8, gap / S)
                    ab8 = max(ab8, abs(D(float(A13[k][i])) - self.yB[k][i]) / S)
                    if gap > INCONCLUSIVE * S:
                        above8 += 1
            tr = self.acc["trajectory"]
            tr["C8_tolerance_gap_over_S_max"] = f64(g8)
            tr["C8_pairs_with_gap_above_1e-10_of_S"] = above8
            tr["C8_taylor_vs_dop853_rtol1e-13_over_S_max"] = f64(ab8)
        return out

    def balances_section(self):
        """Each pool's free + bound and each set's R + sum B at every observation time.

        The closure record compares them with the totals they must keep: the declared
        totals, or after W2's wash the post-wash totals; and every set's S_s. It is kept
        both in working precision and at the written binary64 values.
        """
        sysm = self.sys
        lig = []
        sets = []
        N0 = sysm.pool_totals(sysm.start())
        wash_t = self.world["wash"]["t"] if self.world["wash"] else None
        Npost = sysm.pool_totals(self.ode["B"]["post"]) if wash_t is not None else None
        tot_hp = tot_w = set_hp = set_w = ZERO
        for k, t in enumerate(self.times, start=1):
            y = self.yB[k]
            yw = [D(f64(v)) for v in y]
            ref = N0 if (wash_t is None or t <= wash_t) else Npost
            tot, totw = sysm.pool_totals(y), sysm.pool_totals(yw)
            for p, pool in enumerate(sysm.pools):
                lig.append(
                    {
                        "ligand": pool["ligand"],
                        "node": pool["node"],
                        "time_s": t,
                        "total": f64(tot[p]),
                    }
                )
                sn = self.snode[pool["node"]]
                tot_hp = max(tot_hp, abs(tot[p] - ref[p]) / sn)
                tot_w = max(tot_w, abs(totw[p] - ref[p]) / sn)
            sums, sw = sysm.set_sums(y), sysm.set_sums(yw)
            for s, st in enumerate(sysm.sets):
                sets.append({"set": st["id"], "time_s": t, "sites": f64(sums[s])})
                set_hp = max(set_hp, abs(sums[s] - sysm.Sd[s]) / sysm.Sd[s])
                set_w = max(set_w, abs(sw[s] - sysm.Sd[s]) / sysm.Sd[s])
        self.acc["closure"] = {
            "ligand_totals_high_precision_over_s_node": f64(tot_hp),
            "ligand_totals_written_over_s_node": f64(tot_w),
            "moieties_high_precision_over_S": f64(set_hp),
            "moieties_written_over_S": f64(set_w),
        }
        if wash_t is not None:
            # each ligand's books across the wash (C4a's identity): free + bound + collected -
            # supplied against the declared total, at the start and every observation time
            rec = self.ode["B"]["records"]
            node = self.world["wash"]["node"]
            books_hp = books_w = ZERO
            for k, t in enumerate([0.0] + list(self.times)):
                y = self.yB[k]
                tot = sysm.pool_totals(y)
                totw = sysm.pool_totals([D(f64(v)) for v in y])
                for p, pool in enumerate(sysm.pools):
                    if pool["node"] != node:
                        continue
                    col, sup = rec[pool["ligand"]] if t > wash_t else (ZERO, ZERO)
                    sn = self.snode[pool["node"]]
                    books_hp = max(books_hp, abs(tot[p] + col - sup - N0[p]) / sn)
                    books_w = max(books_w, abs(totw[p] + D(f64(col)) - D(f64(sup)) - N0[p]) / sn)
            self.acc["closure"]["books_high_precision_over_s_node"] = f64(books_hp)
            self.acc["closure"]["books_written_over_s_node"] = f64(books_w)
        return {"ligands": lig, "sets": sets}

    def heats_section(self):
        sysm = self.sys
        nodes = sysm.facing_nodes()
        states = self.yB
        G = {node: [sysm.G(y, node) for y in states] for node in nodes}
        r12, r13 = self.profile["rtols"]
        GA12 = {
            node: [sysm.G([D(float(v)) for v in y], node) for y in self.ode["A"][r12]["states"]]
            for node in nodes
        }
        GA13 = {
            node: [sysm.G([D(float(v)) for v in y], node) for y in self.ode["A"][r13]["states"]]
            for node in nodes
        }
        tt = [0.0] + list(self.times)
        intervals = []
        Glist = []
        self.heat_rows = []
        acc_gap = ZERO
        acc_ab = ZERO
        min_h = None
        for node in nodes:
            for k, t in enumerate(tt):
                Glist.append({"node": node, "time_s": t, "G": f64(G[node][k])})
        for node in nodes:
            delta = BAND_C1 * self.snode[node]
            for ka, kb in interval_list(self.world):
                H = G[node][ka] - G[node][kb]
                E = sysm.E_terms(states[ka], node) + sysm.E_terms(states[kb], node)
                BH = heat_bound(sysm, states[ka], states[kb], node, delta, E)
                H12 = GA12[node][ka] - GA12[node][kb]
                H13 = GA13[node][ka] - GA13[node][kb]
                acc_gap = max(acc_gap, abs(H12 - H13) / E)
                acc_ab = max(acc_ab, abs(H13 - H) / E)
                min_h = H / E if min_h is None else min(min_h, H / E)
                row = {
                    "node": node,
                    "start_s": tt[ka],
                    "end_s": tt[kb],
                    "heat": f64(H),
                    "bound": f64(BH),
                    "tolerance_gap": f64(abs(H12 - H13)),
                }
                intervals.append(row)
                self.heat_rows.append(
                    {
                        "node": node,
                        "ka": ka,
                        "kb": kb,
                        "H": H,
                        "E": E,
                        "BH": BH,
                        "gap": abs(H12 - H13),
                    }
                )
        # C3c covers every interval, the wash's included (AMENDMENT answer 7). Across the wash
        # the site heat runs from the post-wash state to the next row, so its E is taken over
        # those two states.
        wash = self.world["wash"]
        self.c3c_rows = []
        wash_heats = []
        for node in nodes:
            for ka in range(len(self.times)):
                kb = ka + 1
                t_start = 0.0 if ka == 0 else self.times[ka - 1]
                if wash is not None and ka > 0 and t_start == wash["t"]:
                    post = self.ode["B"]["post"]
                    E = sysm.E_terms(post, node) + sysm.E_terms(states[kb], node)
                    H = sysm.G(post, node) - sysm.G(states[kb], node)
                    wash_heats.append(H / E)
                    self.c3c_rows.append(
                        {"node": node, "ka": ka, "kb": kb, "E": E, "H": H, "wash": True}
                    )
                else:
                    row = [r for r in self.heat_rows if r["node"] == node and r["ka"] == ka][0]
                    self.c3c_rows.append(dict(row, wash=False))
        if wash_heats:
            self.acc["wash_interval_site_heat_over_E_min"] = f64(min(wash_heats))
        # AMENDMENT answer 2: Taylor within tolerance_gap + 1e-12 of E of DOP853 at 1e-13
        misses = 0
        worst = ZERO
        for row in self.heat_rows:
            H13 = GA13[row["node"]][row["ka"]] - GA13[row["node"]][row["kb"]]
            allow = row["gap"] + D("1e-12") * row["E"]
            worst = max(worst, abs(H13 - row["H"]) / allow)
            if abs(H13 - row["H"]) > allow:
                misses += 1
        self.acc["heats_convergence_requirement"] = {"misses": misses, "worst_ratio": f64(worst)}
        # the written heats' own precision: the fine Taylor run against the coarse one
        Gc = {node: [sysm.G(y, node) for y in self.ode["Bc"]["states"]] for node in nodes}
        fc_E = ZERO
        fc_rel = ZERO
        for row in self.heat_rows:
            Hc = Gc[row["node"]][row["ka"]] - Gc[row["node"]][row["kb"]]
            fc_E = max(fc_E, abs(Hc - row["H"]) / row["E"])
            if row["H"] != 0:
                fc_rel = max(fc_rel, abs(Hc - row["H"]) / abs(row["H"]))
        # Heats this precision does not resolve to binary64: fewer than 17 significant digits
        # survive G's rounding at the working precision (|H| <= 10^(17 - digits) E), or the
        # fine and coarse Taylor runs disagree beyond 1e-17 of the heat. Such a heat is written
        # as computed; it lies far below every band (W7s's late intervals, 280 time constants
        # from its start, are the case).
        floor = Decimal(10) ** (17 - decimal.getcontext().prec)
        unresolved = []
        for row in self.heat_rows:
            Hc = Gc[row["node"]][row["ka"]] - Gc[row["node"]][row["kb"]]
            if abs(row["H"]) <= floor * row["E"] or abs(Hc - row["H"]) > Decimal("1e-17") * abs(
                row["H"]
            ):
                unresolved.append(
                    {
                        "node": row["node"],
                        "start_s": tt[row["ka"]],
                        "end_s": tt[row["kb"]],
                        "heat_over_E": f64(row["H"] / row["E"]),
                    }
                )
        if unresolved:
            self.acc["heats_below_binary64_resolution"] = {
                "rule": "|H| <= 10^(17 - working digits) E, or |H_fine - H_coarse| > 1e-17 |H|",
                "intervals": unresolved,
            }
        ratios = [row["BH"] / abs(row["H"]) for row in self.heat_rows if row["H"] != 0]
        self.acc["heats_C3a_bound_over_heat"] = {
            "min": f64(min(ratios)) if ratios else None,
            "max": f64(max(ratios)) if ratios else None,
        }
        self.acc["heat_pairs_with_gap_above_1e-10_of_E"] = sum(
            1 for row in self.heat_rows if row["gap"] > INCONCLUSIVE * row["E"]
        )
        self.acc["heats"] = {
            "tolerance_gap_over_E_max": f64(acc_gap),
            "taylor_vs_dop853_rtol1e-13_over_E_max": f64(acc_ab),
            "taylor_fine_vs_coarse_over_E_max": f64(fc_E),
            "taylor_fine_vs_coarse_relative_to_heat_max": f64(fc_rel),
            "smallest_heat_over_E": f64(min_h) if min_h is not None else None,
        }
        out = {"intervals": intervals, "G": Glist}
        if self.world["wash"] is not None:
            pre, post = self.ode["B"]["pre"], self.ode["B"]["post"]
            rows = []
            for node in nodes:
                # term by term, so the sets' part (R and B unchanged by the map) is exactly zero
                before = sysm.g_terms(pre, node)
                after = sysm.g_terms(post, node)
                diffs = [(ka, va - vb) for (ka, va), (_kb, vb) in zip(after, before, strict=True)]
                if [k for k, _ in after] != [k for k, _ in before]:
                    raise RuntimeError("G's terms changed order across the wash")
                dG = sum((v for _, v in diffs), ZERO)
                sets_part = sum((v for k, v in diffs if not k.startswith("pool:")), ZERO)
                rows.append(
                    {
                        "node": node,
                        "time_s": self.world["wash"]["t"],
                        "free_energy_change": f64(dG),
                        "sets_part": f64(sets_part),
                    }
                )
            out["wash_free_energy_change"] = rows
        return out

    def distance_at_horizon(self):
        root = self.eq["root"]
        yT = self.yB[-1]
        out = {}
        worst = ZERO
        for i, name in enumerate(self.obs):
            r = abs(yT[i] - root[i])
            out[name] = f64(r)
            worst = max(worst, r / (BAND_C2A * self.snode[self.sys.node_of_component(i)]))
        self.acc["horizon_distance_over_C2a_band_max"] = f64(worst)
        return out

    # ---- pairs ---------------------------------------------------------------------------
    def kt(self, t_text: str, dt_text: str) -> int:
        return steps(t_text, dt_text)

    def time_text(self, t: float) -> str:
        return self.world["time_texts"][self.times.index(t)]

    def build_pairs(self, extra: dict) -> list[dict]:
        sysm = self.sys
        P = []
        crit = self.criteria
        dts = list(zip(self.world["dt"], self.world["dt_texts"], strict=True))

        def dtkw(dt):
            # every pair whose tolerance counts steps carries its dt, in every world
            return {"dt_s": dt}

        if "C1" in crit:
            for k, t in enumerate(self.times, start=1):
                for i, name in enumerate(self.obs):
                    sn = self.snode[sysm.node_of_component(i)]
                    P.append(
                        _pair(
                            "C1", name, t, "band", f64(self.yB[k][i]), fq(Q_C1 * Q(sn)), "reference"
                        )
                    )
        if "C2a" in crit:
            T = self.times[-1]
            for i, name in enumerate(self.obs):
                sn = self.snode[sysm.node_of_component(i)]
                P.append(
                    _pair(
                        "C2a",
                        name,
                        T,
                        "band",
                        f64(self.eq["root"][i]),
                        fq(Q_C2A * Q(sn)),
                        "reference",
                    )
                )
        if "C2b" in crit:
            xroot = extra["C2b_root"]
            anchors = sysm.anchors()
            Lx = sysm.loads_exact(sysm.start_exact())
            L = max(
                list(Lx["L_n"].values())
                + list(Lx["L_R_summed"].values())
                + list(Lx["L_B"].values())
            )
            c2b_used = Fraction(0)
            # W1eq: every observation time; W7 (amendment 2): its rows before its wash
            c2b_times = extra.get("C2b_times", self.times)
            for dt, dtt in dts:
                h = Q(dt) / 2
                for t in c2b_times:
                    k = self.row_index(t)
                    kt = self.kt(self.time_text(t), dtt)
                    for i, name in enumerate(self.obs):
                        tol = (
                            (2 + 3 * kt * h * L)
                            * 4
                            * EPS_Q
                            * max(abs(Q(xroot[i])), abs(Q(anchors[i])))
                        )
                        # the exact solution's own distance from the root, in this tolerance
                        used = abs(Q(self.yB[k][i]) - Q(xroot[i])) / tol
                        c2b_used = max(c2b_used, used)
                        P.append(
                            _pair(
                                "C2b",
                                name,
                                t,
                                "derived",
                                f64(xroot[i]),
                                fq(tol),
                                "reference",
                                **dtkw(dt),
                            )
                        )
            self.acc["C2b_reference_fraction_of_tolerance_max"] = fq(c2b_used)
        rows = [(0.0, "0", 0)] + [
            (t, self.time_text(t), k) for k, t in enumerate(self.times, start=1)
        ]  # the saved rows: the start and every observation time (AMENDMENT answer 7)
        if any(c in crit for c in ("C3a", "C3b", "C3c")):
            tt = [0.0] + list(self.times)
            ttx = ["0"] + list(self.world["time_texts"])
            for row in self.c3c_rows:
                ka, kb, node = row["ka"], row["kb"], row["node"]
                obs = f"H:{node}"
                if "C3a" in crit and not row["wash"]:
                    P.append(
                        _pair(
                            "C3a",
                            obs,
                            tt[kb],
                            "band",
                            f64(row["H"]),
                            f64(row["BH"]),
                            "reference",
                            start_s=tt[ka],
                            end_s=tt[kb],
                        )
                    )
                if "C3b" in crit and not row["wash"]:
                    for dt, dtt in dts:
                        ksteps = self.kt(ttx[kb], dtt) - self.kt(ttx[ka], dtt)
                        P.append(
                            _pair(
                                "C3b",
                                obs,
                                tt[kb],
                                "derived",
                                None,
                                f64(16 * EPS * ksteps * row["E"]),
                                "engine: -dG of its own saved states, G by the references' "
                                "fr45ref_free_energy.G (SPEC §1.3; AMENDMENT §2.2)",
                                start_s=tt[ka],
                                end_s=tt[kb],
                                **dtkw(dt),
                            )
                        )
                if "C3c" in crit:
                    more = {"spans_wash": True} if row["wash"] else {}
                    P.append(
                        _pair(
                            "C3c",
                            f"cumulative_site_heat:{node}",
                            tt[kb],
                            "derived",
                            None,
                            f64(16 * EPS * row["E"]),
                            "engine: its own cumulative site heat may not fall by more than "
                            "the tolerance",
                            start_s=tt[ka],
                            end_s=tt[kb],
                            **more,
                        )
                    )
        if "C4a" in crit:
            N0 = sysm.pool_totals(sysm.start())
            wash = self.world["wash"]
            rec = self.ode["B"]["records"]
            for dt, dtt in dts:
                for t, ttext, k in rows:
                    kt = self.kt(ttext, dtt)
                    y = self.yB[k]
                    tot = sysm.pool_totals(y)
                    for p, pool in enumerate(sysm.pools):
                        if pool["node"] != wash["node"]:
                            continue
                        after = t > wash["t"]
                        col, sup = rec[pool["ligand"]] if after else (ZERO, ZERO)
                        M = abs(y[p]) + (tot[p] - y[p]) + col + sup
                        P.append(
                            _pair(
                                "C4a",
                                f"books:{pool['ligand']}@{pool['node']}",
                                t,
                                "derived",
                                f64(N0[p]),
                                f64(16 * EPS * (kt + 1) * M),
                                "reference: the declared total N_l",
                                **dtkw(dt),
                            )
                        )
        if "C4b" in crit:
            # AMENDMENT answer 9: the terms the inputs fix are written; the terms from a state
            # are R-ode's, marked as information, and the judge recomputes them from the
            # engine's own state at the event.
            # The event map alone on each saved state it is registered on: W2's 4.0 s row; W7's
            # start (0.0 s) and its 1.0 s wash row (amendment 2).
            wash = self.world["wash"]
            anchors = sysm.anchors()
            f = Q(wash["f"])
            for tw in extra["wash_alone_times"]:
                yw = self.yB[self.row_index(tw)]
                for p, pool in enumerate(sysm.pools):
                    if pool["node"] != wash["node"]:
                        continue
                    sup = supplied_exact(sysm, wash, p)
                    n = Q(yw[p])
                    P.append(
                        _pair(
                            "C4b",
                            f"n:{pool['id']}",
                            tw,
                            "derived",
                            None,
                            None,
                            "engine: (1 - f) n + f V c_buf of its own state at the event",
                            tolerance_terms={
                                "eps_factor": fq(4 * EPS_Q),
                                "f_V_c_buf": fq(sup),
                                "a_n_information": anchors[p],
                                "n_information": f64(yw[p]),
                                "formula": "eps_factor * (|a_n| + |n| + f_V_c_buf), with a_n and "
                                "n the engine's anchor and amount at the event",
                            },
                            tolerance_information=fq(
                                4 * EPS_Q * (abs(Q(anchors[p])) + abs(n) + sup)
                            ),
                        )
                    )
                    P.append(
                        _pair(
                            "C4b",
                            f"removed:{pool['ligand']}@{pool['node']}",
                            tw,
                            "derived",
                            None,
                            None,
                            "engine: f n of its own state at the event",
                            tolerance_terms={
                                "eps_factor": fq(2 * EPS_Q),
                                "f": wash["f"],
                                "n_information": f64(yw[p]),
                                "formula": "eps_factor * f * |n|, with n the engine's amount at "
                                "the event",
                            },
                            tolerance_information=fq(2 * EPS_Q * f * abs(n)),
                        )
                    )
                    P.append(
                        _pair(
                            "C4b",
                            f"supplied:{pool['ligand']}@{pool['node']}",
                            tw,
                            "derived",
                            fq(sup),
                            fq(2 * EPS_Q * sup),
                            "reference: f V c_buf",
                        )
                    )
        if "C4c" in crit:
            wash = self.world["wash"]
            rec = self.ode["B"]["records"]
            for p, pool in enumerate(sysm.pools):
                if pool["node"] != wash["node"]:
                    continue
                rem, _ = rec[pool["ligand"]]
                sup = supplied_exact(sysm, wash, p)
                sn = self.snode[pool["node"]]
                P.append(
                    _pair(
                        "C4c",
                        f"removed:{pool['ligand']}@{pool['node']}",
                        wash["t"],
                        "band",
                        f64(rem),
                        fq(Q(wash["f"]) * Q_C1 * Q(sn)),
                        "reference",
                    )
                )
                P.append(
                    _pair(
                        "C4c",
                        f"supplied:{pool['ligand']}@{pool['node']}",
                        wash["t"],
                        "band",
                        fq(sup),
                        fq(2 * EPS_Q * sup),
                        "reference",
                    )
                )
        if "C5" in crit:
            for dt, dtt in dts:
                for t, ttext, _k in rows:
                    kt = self.kt(ttext, dtt)
                    for _s, st in enumerate(sysm.sets):
                        P.append(
                            _pair(
                                "C5",
                                f"sites:{st['id']}",
                                t,
                                "derived",
                                st["S"],
                                fq(16 * EPS_Q * (kt + 1) * Q(st["S"])),
                                "reference: S_s",
                                **dtkw(dt),
                            )
                        )
        if "C6" in crit:
            wash = self.world["wash"]
            for t5 in extra["wash_alone_times"]:
                for s, st in enumerate(sysm.sets):
                    if st["faces"] != wash["node"]:
                        continue
                    P.append(
                        _pair(
                            "C6",
                            f"R:{st['id']}",
                            t5,
                            "constant",
                            "unchanged",
                            None,
                            "engine: its own value before the event map",
                        )
                    )
                    for b in sysm.pops_of_set[s]:
                        P.append(
                            _pair(
                                "C6",
                                f"B:{sysm.pops[b]['id']}",
                                t5,
                                "constant",
                                "unchanged",
                                None,
                                "engine: its own value before the event map",
                            )
                        )
        if "C7" in crit:
            P.append(
                _pair(
                    "C7",
                    "stage:first_step",
                    0.0,
                    "constant",
                    "refused",
                    None,
                    "engine: its step report gives h*max L above 1/2",
                )
            )
        if "C8" in crit:
            for dt, dtt in dts:
                for k, t in enumerate(self.times, start=1):
                    for i, name in enumerate(self.obs):
                        if i < sysm.nP:
                            continue  # free amounts are left out (CRITERIA.md C8)
                        s = (
                            i - sysm.nP
                            if i < sysm.nP + sysm.nS
                            else sysm.pops[i - sysm.nP - sysm.nS]["set_index"]
                        )
                        S = sysm.Sd[s]
                        tol = f64(BAND_C1 * S) if dtt == extra["C8_finest"] else None
                        P.append(
                            _pair(
                                "C8",
                                name,
                                t,
                                "band",
                                f64(self.yB[k][i]),
                                tol,
                                "reference",
                                dt_s=dt,
                                scale=f64(S),
                            )
                        )
            for (_d1, t1), (_d2, t2) in zip(dts[:-1], dts[1:], strict=True):
                P.append(
                    _pair(
                        "C8",
                        f"ratio:e({t1})/e({t2})",
                        None,
                        "band",
                        None,
                        None,
                        "engine: e(dt) = max |y_e - y_ref| / S over R and the B_b at its times",
                        minimum=6.0,
                    )
                )
        if "C9" in crit:
            # AMENDMENT answer 9: 4 eps is the term the inputs fix; the moiety term is the
            # engine's own state's, recomputed by the judge, and R-ode's is information.
            for t, _ttext, k in rows:
                yw = [Q(f64(v)) for v in self.yB[k]]
                for _b, q in enumerate(sysm.pops):
                    s = q["set_index"]
                    Sq = Q(sysm.sets[s]["S"])
                    total = yw[sysm.i_set(s)] + sum(
                        (yw[sysm.i_pop(c)] for c in sysm.pops_of_set[s]), 0
                    )
                    moiety = abs(total - Sq) / Sq
                    P.append(
                        _pair(
                            "C9",
                            f"theta:{q['id']}",
                            t,
                            "derived",
                            None,
                            None,
                            "engine: B_b / S_s of its own saved state",
                            tolerance_terms={
                                "eps_term": fq(4 * EPS_Q),
                                "moiety_term_information": fq(moiety),
                                "formula": "eps_term + |R_s + sum B - S_s| / S_s, the moiety "
                                "term from the engine's same saved state",
                            },
                            tolerance_information=fq(4 * EPS_Q + moiety),
                        )
                    )
        if "C10" in crit:
            for dt, _dtt in dts:
                P.append(
                    _pair(
                        "C10",
                        "run",
                        self.world["horizon"],
                        "constant",
                        "completes",
                        None,
                        "engine: the run completes and closes its ledgers on every row",
                        **dtkw(dt),
                    )
                )
        return P

    # ---- the start echo --------------------------------------------------------------------
    def world_echo(self, extra_note: str | None = None):
        w = self.world
        sysm = self.sys
        anchors = sysm.anchors()
        echo = {
            "id": w["id"],
            "title": w["title"],
            "constants": {
                "N_f_sites_per_fmol": N_F,
                "N_A_per_mol": float(N_A_TEXT),
                "k_B_J_per_K": float(K_B_TEXT),
                "T_K": float(T_TEXT),
                "RT_pJ_per_fmol": f64(RT),
                "standard_concentration_mM": 1.0,
                "trace_mM": float(TRACE_MM_TEXT),
                "epsilon": 2.0**-52,
            },
            "nodes": [{"id": n["id"], "kind": n["kind"], "V": n["V"]} for n in w["nodes"]],
        }
        if w.get("patches"):
            echo["patches"] = w["patches"]
        echo["ligands"] = list(w["ligands"])
        if sysm.inert:
            echo["inert_amounts_information"] = sysm.inert
        echo["free_amounts"] = [
            {"ligand": p["ligand"], "node": p["node"], "n": f64(p["n0"]), "declared": p["declared"]}
            for p in sysm.pools
        ]
        echo["sets"] = [
            {
                "id": s["id"],
                "owner": s["owner"],
                "faces": s["faces"],
                "copies": s["copies"],
                "sites_per_copy": s["sites_per_copy"],
                "accessible_fraction": s["accessible_fraction"],
                "S": s["S"],
            }
            for s in sysm.sets
        ]
        echo["populations"] = [
            {
                "id": q["id"],
                "set": q["set"],
                "ligand": q["ligand"],
                "faces": sysm.sets[q["set_index"]]["faces"],
                "k_on": q["k_on"],
                "k_off": q["k_off"],
                "initial_occupancy": q["occupancy"],
            }
            for q in sysm.pops
        ]
        echo["start"] = [
            {"observable": name, "value": anchors[i]} for i, name in enumerate(self.obs)
        ]
        echo["dt"] = list(w["dt"])
        echo["observation_times"] = list(self.times)
        echo["horizon"] = w["horizon"]
        if w["wash"] is not None:
            echo["wash"] = {
                "t": w["wash"]["t"],
                "node": w["wash"]["node"],
                "f": w["wash"]["f"],
                "buffer": {b["ligand"]: b["c"] for b in w["wash"]["buffer"]},
            }
        if extra_note:
            echo["start_source"] = extra_note
        return echo


# ------------------------------------------------------------------------------------------
# Plants (CRITERIA.md), sized from the reference alone


def _largest(entries):
    """The entry of largest distance. Distances equal to 30 significant digits (such as a
    pool and its population, whose changes are equal and opposite) count as a tie, and a tie
    keeps the first entry in observable order, so the choice does not depend on precision."""

    def key(e):
        d = e["distance"]
        return d if d == 0 else d.quantize(Decimal(10) ** (d.adjusted() - 29))

    best = None
    for e in entries:
        if best is None or key(e) > key(best):
            best = e
    return best


def _plant_entry(plant, criterion, best, **extra):
    d = {
        "plant": plant,
        "criterion": criterion,
        "compared": best["compared"],
        "honest": best["honest"],
        "planted": best["planted"],
        "distance_in_bounds": f64(best["distance"]),
    }
    d.update(extra)
    return d


P1_ASSUMPTION = (
    "ranked over the free and bound amounts only: the plant gives each population "
    "S_s - B_b as its free sites and does not say what the set's R_s does"
)
P5_ASSUMPTION = (
    "the planted map scales every B_b facing the washed node by (1 - f) and leaves R_s unchanged"
)


def plant_dynamics_C1(
    honest: WorldRun, planted_world: dict, profile, plant: str, skip_R: bool = False, **variant
):
    """A dynamics plant judged by C1: the planted trajectory against the honest one."""
    sysp = System(planted_world, **variant)
    ode = integrate(sysp, planted_world, profile)
    yP = ode["B"]["states"]
    yA = ode["A"][profile["rtols"][-1]]["states"]
    entries = []
    worst_ab = ZERO
    for k, t in enumerate(honest.times, start=1):
        for i, name in enumerate(honest.obs):
            if skip_R and name.startswith("R:"):
                continue
            sn = honest.snode[honest.sys.node_of_component(i)]
            band = BAND_C1 * sn
            d = abs(yP[k][i] - honest.yB[k][i]) / band
            dA = abs(D(float(yA[k][i])) - honest.yB[k][i]) / band
            worst_ab = max(worst_ab, abs(d - dA))
            entries.append(
                {
                    "compared": {"observable": name, "time_s": t},
                    "honest": f64(honest.yB[k][i]),
                    "planted": f64(yP[k][i]),
                    "distance": d,
                }
            )
    return _largest(entries), ode, {"taylor_vs_dop853_distance_gap": f64(worst_ab)}


def _first_dt(run: WorldRun):
    """A plant runs at the world's (first) dt; FR-45's plant worlds each have one."""
    return run.world["dt"][0], run.world["dt_texts"][0]


def crossed_koff_world(world: dict) -> dict:
    """P2: the first set's first two populations exchange k_off."""
    w = dict(world)
    pops = [dict(p) for p in world["populations"]]
    first_set = pops[0]["set"]
    idx = [i for i, p in enumerate(pops) if p["set"] == first_set][:2]
    a, b = idx
    pops[a]["k_off"], pops[b]["k_off"] = pops[b]["k_off"], pops[a]["k_off"]
    w["populations"] = pops
    return w


def _states_A(run: WorldRun) -> list:
    """Method A's (DOP853, rtol 1e-13) states, exactly in decimal, for a second sizing."""
    return [[D(float(v)) for v in st] for st in run.ode["A"][run.profile["rtols"][-1]]["states"]]


def _method_gap(eB: list, eA: list) -> float:
    """Largest |d_B - d_A| / max(d_B, 1) between the two methods' distances, entry by entry."""
    worst = ZERO
    for b, a in zip(eB, eA, strict=True):
        worst = max(worst, abs(b["distance"] - a["distance"]) / max(b["distance"], ONE))
    return f64(worst)


def _energy_entries(run: WorldRun, plant: str, states) -> list:
    sysm = run.sys
    _dt, dtt = _first_dt(run)
    tt = [0.0] + list(run.times)
    ttx = ["0"] + list(run.world["time_texts"])
    entries = []
    for row in run.heat_rows:
        ka, kb, node = row["ka"], row["kb"], row["node"]
        H = sysm.G(states[ka], node) - sysm.G(states[kb], node)
        Hp = planted_G(sysm, states[ka], node, plant) - planted_G(sysm, states[kb], node, plant)
        ks = steps(ttx[kb], dtt) - steps(ttx[ka], dtt)
        tol = 16 * EPS * ks * row["E"]
        entries.append(
            {
                "compared": {"observable": f"H:{node}", "start_s": tt[ka], "end_s": tt[kb]},
                "honest": f64(H),
                "planted": f64(Hp),
                "distance": abs(Hp - H) / tol,
                "Hp": Hp,
            }
        )
    return entries


def plant_energy(run: WorldRun, plant: str) -> tuple[list, dict]:
    """P3 or P6: the energy accounting changed on the honest trajectory, judged by C3b.

    Their distances under C3a stay in the file as information (AMENDMENT §2.2).
    """
    eB = _energy_entries(run, plant, run.yB)
    eA = _energy_entries(run, plant, _states_A(run))
    sign = "negative" if min(e["Hp"] for e in eB) < 0 else "non-negative"
    acc = {
        "smallest_planted_heat_sign": sign,
        "taylor_vs_dop853_relative_distance_gap": _method_gap(eB, eA),
    }
    c3a = []
    for e, row in zip(eB, run.heat_rows, strict=True):
        c3a.append(dict(e, distance=abs(e["Hp"] - row["H"]) / row["BH"]))
    entries = [
        _plant_entry(plant, "C3b", _largest(eB)),
        _plant_entry(plant, "C3a", _largest(c3a), information=True),
    ]
    return entries, acc


def _P8_entries(run: WorldRun, states) -> list:
    sysm = run.sys
    _dt, dtt = _first_dt(run)
    entries = []
    for k, t in enumerate(run.times, start=1):
        kt = steps(run.time_text(t), dtt)
        y = states[k]
        for b, q in enumerate(sysm.pops):
            s = q["set_index"]
            v = y[sysm.i_set(s)] + y[sysm.i_pop(b)]
            tol = 16 * EPS * (kt + 1) * sysm.Sd[s]
            entries.append(
                {
                    "compared": {"observable": f"R:{sysm.sets[s]['id']}+B:{q['id']}", "time_s": t},
                    "honest": sysm.sets[s]["S"],
                    "planted": f64(v),
                    "distance": abs(v - sysm.Sd[s]) / tol,
                }
            )
    return entries


def plant_P8(run: WorldRun) -> tuple[dict, dict]:
    """P8: the moiety checked per population (R_s + B_b = S_s), refused by its own ledger."""
    eB = _P8_entries(run, run.yB)
    eA = _P8_entries(run, _states_A(run))
    entry = _plant_entry(
        "P8",
        "C10",
        _largest(eB),
        bound_used="C5's moiety tolerance 16 eps (k_t + 1) S_s, as the ledger's own",
    )
    return entry, {"taylor_vs_dop853_relative_distance_gap": _method_gap(eB, eA)}


def _P9_entries(run: WorldRun, states) -> list:
    """C9's tolerance is held at the written values (R-ode's) for either route's states."""
    sysm = run.sys
    entries = []
    for k, t in enumerate(run.times, start=1):
        y = states[k]
        sums = sysm.set_sums([D(f64(v)) for v in run.yB[k]])
        for b, q in enumerate(sysm.pops):
            s = q["set_index"]
            B, R = y[sysm.i_pop(b)], y[sysm.i_set(s)]
            th = B / sysm.Sd[s]
            tp = B / (B + R)
            tol = 4 * EPS + abs(sums[s] - sysm.Sd[s]) / sysm.Sd[s]
            entries.append(
                {
                    "compared": {"observable": f"theta:{q['id']}", "time_s": t},
                    "honest": f64(th),
                    "planted": f64(tp),
                    "distance": abs(tp - th) / tol,
                }
            )
    return entries


def plant_P9(run: WorldRun) -> tuple[dict, dict]:
    """P9: theta_b = B_b / (B_b + R_s), judged by C9."""
    eB = _P9_entries(run, run.yB)
    eA = _P9_entries(run, _states_A(run))
    return _plant_entry("P9", "C9", _largest(eB)), {
        "taylor_vs_dop853_relative_distance_gap": _method_gap(eB, eA)
    }


def plants_W1p(run: WorldRun, profile) -> tuple[list, dict]:
    out = []
    acc = {}
    best, _, a = plant_dynamics_C1(run, run.world, profile, "P1", skip_R=True, unshared=True)
    out.append(_plant_entry("P1", "C1", best, assumption=P1_ASSUMPTION))
    acc["P1"] = a
    best, _, a = plant_dynamics_C1(run, crossed_koff_world(run.world), profile, "P2")
    out.append(_plant_entry("P2", "C1", best))
    acc["P2"] = a
    for plant in ("P3", "P6"):
        entries, a = plant_energy(run, plant)
        out += entries
        acc[plant] = a
    for plant, fn in (("P8", plant_P8), ("P9", plant_P9)):
        entry, a = fn(run)
        out.append(entry)
        acc[plant] = a
    return out, acc


def _P5_C6_entries(run: WorldRun, y, t: float) -> list:
    """The honest and the planted event map on one state, in ulps of the honest value."""
    sysm = run.sys
    wash = run.world["wash"]
    after_h, _ = sysm.wash(y, wash, scale_bound=False)
    after_p, _ = sysm.wash(y, wash, scale_bound=True)
    entries = []
    for i, name in enumerate(run.obs):
        if name.startswith("n:"):
            continue
        hv = f64(after_h[i])
        pv = f64(after_p[i])
        ulp = math.ulp(hv)
        entries.append(
            {
                "compared": {"observable": name, "time_s": t},
                "honest": hv,
                "planted": pv,
                "distance": abs(D(pv) - D(hv)) / D(ulp),
            }
        )
    return entries


def plants_wash(run: WorldRun, profile, wash_alone_times) -> tuple[list, dict]:
    """P5 (CRITERIA.md) in a wash world: W2, and W7 by the coordinator's ruling of 24 November
    2026 on amendment 2 (CRITERIA.md's plant row names C6 and C4a for both worlds).

    C6: the planted event map alone on each state it is registered on (W2's 4.0 s row; W7's
    start and its 1.0 s wash row), one entry per state, so a tie between states cannot hide
    one. C4a: the planted wash in the full run.
    """
    sysm = run.sys
    out = []
    acc = {}
    wash = run.world["wash"]
    yA_states = _states_A(run)
    eB_all, eA_all = [], []
    for t in wash_alone_times:
        k = run.row_index(t)
        eB = _P5_C6_entries(run, run.yB[k], t)
        eB_all += eB
        eA_all += _P5_C6_entries(run, yA_states[k], t)
        out.append(
            _plant_entry(
                "P5",
                "C6",
                _largest(eB),
                bound_used="ulps of the honest value (bit for bit)",
                assumption=P5_ASSUMPTION,
            )
        )
    c6_gap = _method_gap(eB_all, eA_all)
    # C4a: the planted wash in the full run
    sysp = System(run.world)
    ode = integrate(sysp, run.world, profile, wash_variant=True)
    yP = ode["B"]["states"]
    recP = ode["B"]["records"]
    yA = ode["A"][profile["rtols"][-1]]["states"]
    N0 = sysm.pool_totals(sysm.start())
    dt, dtt = _first_dt(run)
    entries = []
    worst_ab = ZERO
    for k, t in enumerate(run.times, start=1):
        kt = steps(run.time_text(t), dtt)
        y = yP[k]
        tot = sysm.pool_totals(y)
        totA = sysm.pool_totals([D(float(v)) for v in yA[k]])
        for p, pool in enumerate(sysm.pools):
            if pool["node"] != wash["node"]:
                continue
            after = t > wash["t"]
            col, sup = recP[pool["ligand"]] if after else (ZERO, ZERO)
            books = tot[p] + col - sup
            booksA = totA[p] + col - sup
            M = abs(y[p]) + (tot[p] - y[p]) + col + sup
            tol = 16 * EPS * (kt + 1) * M
            d = abs(books - N0[p]) / tol
            worst_ab = max(worst_ab, abs(d - abs(booksA - N0[p]) / tol) / max(d, ONE))
            entries.append(
                {
                    "compared": {
                        "observable": f"books:{pool['ligand']}@{pool['node']}",
                        "time_s": t,
                    },
                    "honest": f64(N0[p]),
                    "planted": f64(books),
                    "distance": d,
                }
            )
    out.append(_plant_entry("P5", "C4a", _largest(entries), assumption=P5_ASSUMPTION))
    acc["P5"] = {
        "C6_taylor_vs_dop853_relative_distance_gap": c6_gap,
        "C4a_taylor_vs_dop853_relative_distance_gap": f64(worst_ab),
    }
    return out, acc


def plants_W3p(
    honest_W3p: WorldRun, planted_world: dict, profile, label: str = "W3p"
) -> tuple[list, dict]:
    out = []
    acc = {}
    sysp = System(planted_world, dR_first_only=True)
    ode = integrate(sysp, planted_world, profile)
    yP = ode["B"]["states"]
    yA = ode["A"][profile["rtols"][-1]]["states"]
    dtt = planted_world["dt_texts"][0]
    # C5
    entries = []
    for k, t in enumerate(honest_W3p.times, start=1):
        kt = steps(honest_W3p.time_text(t), dtt)
        sums = sysp.set_sums(yP[k])
        for s, st in enumerate(sysp.sets):
            tol = 16 * EPS * (kt + 1) * sysp.Sd[s]
            entries.append(
                {
                    "compared": {"observable": f"sites:{st['id']}", "time_s": t},
                    "honest": st["S"],
                    "planted": f64(sums[s]),
                    "distance": abs(sums[s] - sysp.Sd[s]) / tol,
                }
            )
    out.append(_plant_entry("P7", "C5", _largest(entries), world=label))
    # C1
    entries = []
    worst_ab = ZERO
    for k, t in enumerate(honest_W3p.times, start=1):
        for i, name in enumerate(honest_W3p.obs):
            band = BAND_C1 * honest_W3p.snode[honest_W3p.sys.node_of_component(i)]
            d = abs(yP[k][i] - honest_W3p.yB[k][i]) / band
            dA = abs(D(float(yA[k][i])) - honest_W3p.yB[k][i]) / band
            worst_ab = max(worst_ab, abs(d - dA))
            entries.append(
                {
                    "compared": {"observable": name, "time_s": t},
                    "honest": f64(honest_W3p.yB[k][i]),
                    "planted": f64(yP[k][i]),
                    "distance": d,
                }
            )
    out.append(_plant_entry("P7", "C1", _largest(entries), world=label))
    acc["P7"] = {"C1_taylor_vs_dop853_distance_gap": f64(worst_ab)}
    return out, acc


def stage_section(sysm: System, dt: float) -> dict:
    """SPEC §3.5-3.6: the loads at the start times h = dt/2, exact, and each rule's verdict."""
    L = sysm.loads_exact(sysm.start_exact())
    h = Q(dt) / 2
    hL = {k: {name: fq(h * v) for name, v in d.items()} for k, d in L.items()}
    common = list(L["L_n"].values()) + list(L["L_B"].values())
    m_sum = h * max(common + list(L["L_R_summed"].values()))
    m_per = h * max(common + list(L["L_R_per_population"].values()))
    half = Fraction(1, 2)
    return {
        "h_s": fq(h),
        "loads_times_h": hL,
        "max_hL_summed": fq(m_sum),
        "max_hL_per_population": fq(m_per),
        "threshold": 0.5,
        "verdict_summed": "refused" if m_sum > half else "admitted",
        "verdict_per_population": "refused" if m_per > half else "admitted",
        "_m": (m_sum, m_per),
    }


def stage_binary64_check(sysm: System, dt: float, stage: dict) -> dict:
    """The same loads in plain binary64 from the declared start: a second route to SPEC §3.6."""
    y = sysm.anchors()
    h = dt / 2
    per_pop = {}
    for q in sysm.pops:
        per_pop[q["id"]] = q["k_on"] * y[q["pool_index"]] / sysm.pools[q["pool_index"]]["V"]
    summed = {}
    for si, st in enumerate(sysm.sets):
        acc = 0.0
        for b in sysm.pops_of_set[si]:
            acc += per_pop[sysm.pops[b]["id"]]
        summed[st["id"]] = acc
    Ln = {}
    for p, pool in enumerate(sysm.pools):
        if sysm.pops_of_pool[p]:
            acc = 0.0
            for b in sysm.pops_of_pool[p]:
                acc += sysm.pops[b]["k_on"] * y[sysm.i_set(sysm.pops[b]["set_index"])]
            Ln[pool["id"]] = acc / pool["V"]
    LB = {q["id"]: q["k_off"] for q in sysm.pops}
    loads = {"L_n": Ln, "L_R_summed": summed, "L_R_per_population": per_pop, "L_B": LB}
    worst = ZERO
    for kind, d in loads.items():
        for name, v in d.items():
            exact = D(stage["loads_times_h"][kind][name])
            worst = max(worst, abs(D(h * v) - exact) / abs(exact))
    common = list(Ln.values()) + list(LB.values())
    m_sum = h * max(common + list(summed.values()))
    m_per = h * max(common + list(per_pop.values()))
    return {
        "binary64_vs_exact_relative_max": f64(worst),
        "verdicts_agree": (
            ("refused" if m_sum > 0.5 else "admitted") == stage["verdict_summed"]
            and ("refused" if m_per > 0.5 else "admitted") == stage["verdict_per_population"]
        ),
    }


def plant_P4(stage: dict) -> dict:
    m_sum, m_per = stage["_m"]
    return {
        "plant": "P4",
        "criterion": "C7",
        "compared": {"observable": "stage:h*max_L", "time_s": 0.0},
        "honest": fq(m_sum),
        "planted": fq(m_per),
        "distance_in_bounds": fq(abs(m_sum - m_per) / Fraction(1, 2)),
        "bound_used": "the stage condition's 1/2",
        "verdict_honest": stage["verdict_summed"],
        "verdict_planted": stage["verdict_per_population"],
    }


# ------------------------------------------------------------------------------------------
# W7's stated start (AMENDMENT-2-2026-11-24.md)


def stated_start_checks(run: WorldRun) -> tuple[dict, dict]:
    """W7's start as SPEC.md states it, checked, and W7's own root at its start's totals.

    The facts are checked in plain binary64 on the declared start (the anchors, the start
    as the engine forms it from its inputs), with exact rationals beside where they apply:
    the capacity S; B = 2.0 and 1.0 and R = 3.0; both K; detailed balance at the start; both
    of §1.2's net fluxes 0.0; §1.4's map on the start removing 4.0 and 2.0 fmol and supplying
    4.0 fmol of L2; and the rows before and after the wash. Any failure stops the run: it is
    a question for the protocol's author, not something the references adjust.

    C2b compares W7's rows before its wash with "its start, its own root" (CRITERIA.md;
    amendment 2's §3). That root is R-eq at the start's totals, solved as every other root
    here; it must round to the declared start, or the run stops. As information: R-eq at the
    declared start's own binary64 totals, the formula's theta at the own root, and whether
    R-ode's rows before the wash and the wash's removed amounts round to the example too.
    Returns (the own root's equilibrium, the accuracy record).
    """
    w = run.world
    st = w["stated"]
    sysm = run.sys
    anchors = sysm.anchors()
    a = dict(zip(run.obs, anchors, strict=True))
    if len(sysm.sets) != 1:
        raise RuntimeError("W7 has one set")
    s0 = sysm.sets[0]
    checked, fails = [], []

    def need(ok, what):
        (checked if ok else fails).append(what)

    need(s0["S"] == float(st["S"]) and s0["S_naive_binary64_same"], f"S = {st['S']} fmol")
    for pid, txt in st["B_start"].items():
        need(a[f"B:{pid}"] == float(txt), f"the start's B of {pid} = {txt} fmol")
    R = a[f"R:{s0['id']}"]
    need(R == float(st["R_start"]), f"the start's R = {st['R_start']} fmol")
    for q in sysm.pops:
        pool = sysm.pools[q["pool_index"]]
        n, B = a[f"n:{pool['id']}"], a[f"B:{q['id']}"]
        K_exact = Q(q["k_off"]) / Q(q["k_on"])
        need(
            q["k_off"] / q["k_on"] == float(st["K_mM"]) and K_exact == Q(st["K_mM"]),
            f"K of {q['id']} = {st['K_mM']} mM",
        )
        need(Q(B) / Q(R) == Q(n) / Q(pool["V"]) / K_exact, f"B/R = c/K at the start, {q['id']}")
        J = q["k_on"] * (n / pool["V"]) * R - q["k_off"] * B
        need(J == 0.0, f"the net flux of {q['id']} at the start is 0.0 in binary64")
    wash = w["wash"]
    for pool in sysm.pools:
        lig = pool["ligand"]
        c = [b["c"] for b in wash["buffer"] if b["ligand"] == lig][0]
        n = a[f"n:{pool['id']}"]
        want = st["removed_at_start"][lig]
        need(
            wash["f"] * n == float(want) and Q(wash["f"]) * Q(n) == Q(want),
            f"the map on the start removes {want} fmol of {lig}",
        )
        if lig in st["supplied_at_start"]:
            want = st["supplied_at_start"][lig]
            need(
                wash["f"] * pool["V"] * c == float(want)
                and Q(wash["f"]) * Q(pool["V"]) * Q(c) == Q(want),
                f"the map on the start supplies {want} fmol of {lig}",
            )
    before = [t for t in run.times if t <= wash["t"]]
    need(
        before == [float(x) for x in st["rows_before_wash"]] and before[-1] == wash["t"],
        "the rows before the wash are " + " and ".join(st["rows_before_wash"]) + " s",
    )
    need(
        run.times[len(before)] == float(st["first_row_after_wash"]),
        f"the first row after the wash is {st['first_row_after_wash']} s",
    )
    if fails:
        raise RuntimeError("W7's start does not hold as SPEC.md states it: " + "; ".join(fails))
    eq0 = equilibrium(sysm, sysm.pool_totals(sysm.start()))
    root0 = eq0["root"]
    if [f64(v) for v in root0] != anchors:
        raise RuntimeError("W7's own root at its start's totals does not round to its start")
    eqb = equilibrium(sysm, sysm.pool_totals([D(v) for v in anchors]))
    sn = run.snode

    def dist(y):
        return f64(
            dmax(abs(y[i] - D(anchors[i])) / sn[sysm.node_of_component(i)] for i in range(sysm.n))
        )

    occ = {q["id"]: q["occupancy"] for q in sysm.pops}
    th0 = theta_both_ways(sysm, root0)
    rec = run.ode["B"]["records"]
    acc = {
        "stated_facts_checked": checked,
        "own_root_at_the_start_totals": equilibrium_accuracy(sysm, eq0, sn),
        "own_root_equals_declared_start_in_binary64": True,
        "own_root_vs_declared_start_over_s_node": dist(root0),
        "root_at_declared_binary64_totals_vs_declared_start_over_s_node": dist(eqb["root"]),
        "own_root_theta_formula_equals_declared_occupancy": all(
            f64(th0[b][0]) == occ[q["id"]] for b, q in enumerate(sysm.pops)
        ),
        "rows_before_wash_equal_declared_start_in_binary64": all(
            [f64(v) for v in run.yB[run.row_index(t)]] == anchors for t in before
        ),
        "wash_removed_round_to_the_amounts_stated_for_the_start": all(
            f64(rec[lig][0]) == float(v) for lig, v in st["removed_at_start"].items()
        ),
    }
    return eq0, acc
