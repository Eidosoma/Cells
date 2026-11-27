"""SPEC §1's binding system, integrated by two independent methods.

State order: free pools n_p (one per ligand row that is declared or bound from), then
each set's free sites R_s, then each population's bound amount B_b. All in fmol.

  J_b = k_on,b * (n_p(b) / V_p(b)) * R_s(b) - k_off,b * B_b
  dB_b/dt = J_b,  dR_s/dt = -sum_{b on s} J_b,  dn_p/dt = -sum_{b from p} J_b

Method B (written values): a Taylor-series integrator in decimal arithmetic. The system
is quadratic, so its Taylor coefficients follow exactly from Cauchy products; every
linear invariant (each pool's total, each set's moiety) is conserved coefficient by
coefficient. Steps land exactly on the observation times.

Method A: scipy's DOP853 in binary64 at the two tolerances SPEC §3.2 names, restarted at
each observation time so a reported value is a step end, not an interpolant.

Variants carry the plants that change the dynamics (CRITERIA.md): ``unshared`` (P1, each
population binds its own S_s - B_b) and ``dR_first_only`` (P7, a set's dR from its first
population only).
"""

from __future__ import annotations

import math
from decimal import Decimal

import numpy as np
from fr45ref_hp import ZERO, D, Q, ln
from fr45ref_worlds import STANDARD_MM_TEXT, TRACE_MM_TEXT, gas_constant_RT
from scipy.integrate import solve_ivp

RT = gas_constant_RT()
C_STD = D(STANDARD_MM_TEXT)


class System:
    """One world's pools, sets and populations, with decimal and binary64 parameters."""

    def __init__(self, world: dict, unshared: bool = False, dR_first_only: bool = False):
        self.world = world
        self.unshared = unshared
        self.dR_first_only = dR_first_only
        nodes = {n["id"]: n for n in world["nodes"]}
        node_order = [n["id"] for n in world["nodes"]]
        lig_order = list(world["ligands"])
        declared = {(f["ligand"], f["node"]): f["n"] for f in world["free"]}
        set_by_id = {s["id"]: s for s in world["sets"]}

        def order(k):
            return (node_order.index(k[1]), lig_order.index(k[0]))

        # Only amounts a law moves (AMENDMENT-2026-11-24 answer 3): a ligand's free amount at a
        # node some population binds it from. A declared amount no population binds is a
        # constant; it is left out of everything and listed as information.
        binding = {(p["ligand"], set_by_id[p["set"]]["faces"]) for p in world["populations"]}
        self.inert = [
            {"ligand": k[0], "node": k[1], "n": declared[k]}
            for k in sorted((k for k in declared if k not in binding), key=order)
        ]
        pool_keys = sorted(binding, key=order)
        self.pools = []
        for lig, nid in pool_keys:
            V = nodes[nid]["V"]
            if (lig, nid) in declared:
                n0 = D(declared[(lig, nid)])
                is_declared = True
            else:
                n0 = D(TRACE_MM_TEXT) * D(V)
                is_declared = False
            self.pools.append(
                {
                    "id": f"{lig}@{nid}",
                    "ligand": lig,
                    "node": nid,
                    "V": V,
                    "n0": n0,
                    "declared": is_declared,
                }
            )
        self.sets = [dict(s) for s in world["sets"]]
        self.set_index = {s["id"]: i for i, s in enumerate(self.sets)}
        pool_index = {(p["ligand"], p["node"]): i for i, p in enumerate(self.pools)}
        self.pops = []
        for p in world["populations"]:
            si = self.set_index[p["set"]]
            pi = pool_index[(p["ligand"], self.sets[si]["faces"])]
            self.pops.append(dict(p, set_index=si, pool_index=pi))
        self.nP, self.nS, self.nB = len(self.pools), len(self.sets), len(self.pops)
        self.n = self.nP + self.nS + self.nB
        self.pops_of_pool = [
            [b for b, q in enumerate(self.pops) if q["pool_index"] == i] for i in range(self.nP)
        ]
        self.pops_of_set = [
            [b for b, q in enumerate(self.pops) if q["set_index"] == s] for s in range(self.nS)
        ]
        # decimal parameters
        self.Vd = [D(p["V"]) for p in self.pools]
        self.Sd = [D(s["S"]) for s in self.sets]
        self.kon = [D(q["k_on"]) for q in self.pops]
        self.koff = [D(q["k_off"]) for q in self.pops]
        self.a = [self.kon[b] / self.Vd[q["pool_index"]] for b, q in enumerate(self.pops)]
        self.K = [self.koff[b] / self.kon[b] for b in range(self.nB)]
        self.mu0 = [RT * ln(self.K[b] / C_STD) for b in range(self.nB)]
        # binary64 parameters for method A
        self.np_pp = np.array([q["pool_index"] for q in self.pops], dtype=np.int64)
        self.np_ps = np.array([q["set_index"] for q in self.pops], dtype=np.int64)
        self.np_kon = np.array([q["k_on"] for q in self.pops], dtype=np.float64)
        self.np_koff = np.array([q["k_off"] for q in self.pops], dtype=np.float64)
        self.np_Vp = np.array(
            [self.pools[q["pool_index"]]["V"] for q in self.pops], dtype=np.float64
        )
        self.np_S = np.array([s["S"] for s in self.sets], dtype=np.float64)
        self.np_first = np.array([self.pops_of_set[s][0] for s in range(self.nS)], dtype=np.int64)

    # ---- indexing -------------------------------------------------------------------
    def i_pool(self, p):
        return p

    def i_set(self, s):
        return self.nP + s

    def i_pop(self, b):
        return self.nP + self.nS + b

    def observables(self) -> list[str]:
        return (
            [f"n:{p['id']}" for p in self.pools]
            + [f"R:{s['id']}" for s in self.sets]
            + [f"B:{q['id']}" for q in self.pops]
        )

    def node_of_component(self, i) -> str:
        if i < self.nP:
            return self.pools[i]["node"]
        if i < self.nP + self.nS:
            return self.sets[i - self.nP]["faces"]
        return self.sets[self.pops[i - self.nP - self.nS]["set_index"]]["faces"]

    def facing_nodes(self) -> list[str]:
        order = [n["id"] for n in self.world["nodes"]]
        faced = {s["faces"] for s in self.sets}
        return [nid for nid in order if nid in faced]

    # ---- the declared start ------------------------------------------------------------
    def start(self) -> list[Decimal]:
        y = [p["n0"] for p in self.pools]
        B0 = [D(q["occupancy"]) * self.Sd[q["set_index"]] for q in self.pops]
        R0 = [self.Sd[s] - sum((B0[b] for b in self.pops_of_set[s]), ZERO) for s in range(self.nS)]
        return y + R0 + B0

    def start_exact(self):
        """The declared start (SPEC §2) as exact rationals of the binary64 inputs."""
        n0 = [Q(p["n0"]) for p in self.pools]
        B0 = [Q(q["occupancy"]) * Q(self.sets[q["set_index"]]["S"]) for q in self.pops]
        R0 = [
            Q(self.sets[s]["S"]) - sum((B0[b] for b in self.pops_of_set[s]), 0)
            for s in range(self.nS)
        ]
        return n0 + R0 + B0

    def anchors(self) -> list[float]:
        """CRITERIA's anchors a_x: the declared start, each rounded once."""
        return [float(v) for v in self.start_exact()]

    def loads_exact(self, y) -> dict:
        """SPEC §1.2's loads at a state given as exact rationals."""
        Ln = {}
        for p in range(self.nP):
            if self.pops_of_pool[p]:
                Ln[self.pools[p]["id"]] = sum(
                    (
                        Q(self.pops[b]["k_on"]) * y[self.i_set(self.pops[b]["set_index"])]
                        for b in self.pops_of_pool[p]
                    ),
                    0,
                ) / Q(self.pools[p]["V"])
        per_pop = {
            q["id"]: Q(q["k_on"]) * y[q["pool_index"]] / Q(self.pools[q["pool_index"]]["V"])
            for q in self.pops
        }
        summed = {
            s["id"]: sum((per_pop[self.pops[b]["id"]] for b in self.pops_of_set[si]), 0)
            for si, s in enumerate(self.sets)
        }
        LB = {q["id"]: Q(q["k_off"]) for q in self.pops}
        return {"L_n": Ln, "L_R_summed": summed, "L_R_per_population": per_pop, "L_B": LB}

    def pool_totals(self, y) -> list[Decimal]:
        return [
            y[p] + sum((y[self.i_pop(b)] for b in self.pops_of_pool[p]), ZERO)
            for p in range(self.nP)
        ]

    def set_sums(self, y) -> list[Decimal]:
        return [
            y[self.i_set(s)] + sum((y[self.i_pop(b)] for b in self.pops_of_set[s]), ZERO)
            for s in range(self.nS)
        ]

    # ---- the wash (SPEC §1.4) --------------------------------------------------------
    def wash(self, y, wash: dict, scale_bound: bool = False):
        """Returns (state after, {ligand: (removed, supplied)}). P5 scales B by (1 - f)."""
        f = D(wash["f"])
        node = wash["node"]
        cbuf = {b["ligand"]: D(b["c"]) for b in wash["buffer"]}
        out = list(y)
        records = {}
        for i, p in enumerate(self.pools):
            if p["node"] != node:
                continue
            c = cbuf.get(p["ligand"])
            if c is None:
                raise ValueError(f"the wash names no buffer concentration for {p['ligand']}")
            removed = f * y[i]
            supplied = f * self.Vd[i] * c
            out[i] = (1 - f) * y[i] + supplied
            records[p["ligand"]] = (removed, supplied)
        if scale_bound:
            for b, q in enumerate(self.pops):
                if self.sets[q["set_index"]]["faces"] == node:
                    out[self.i_pop(b)] = (1 - f) * y[self.i_pop(b)]
        return out, records

    # ---- loads (SPEC §1.2) -------------------------------------------------------------
    def loads(self, y) -> dict:
        Ln = {}
        for p in range(self.nP):
            if self.pops_of_pool[p]:
                Ln[self.pools[p]["id"]] = (
                    sum(
                        (
                            self.kon[b] * y[self.i_set(self.pops[b]["set_index"])]
                            for b in self.pops_of_pool[p]
                        ),
                        ZERO,
                    )
                    / self.Vd[p]
                )
        per_pop = {}
        for b, q in enumerate(self.pops):
            per_pop[q["id"]] = self.kon[b] * y[q["pool_index"]] / self.Vd[q["pool_index"]]
        summed = {
            s["id"]: sum((per_pop[self.pops[b]["id"]] for b in self.pops_of_set[si]), ZERO)
            for si, s in enumerate(self.sets)
        }
        LB = {q["id"]: self.koff[b] for b, q in enumerate(self.pops)}
        return {"L_n": Ln, "L_R_summed": summed, "L_R_per_population": per_pop, "L_B": LB}

    # ---- free energy (SPEC §1.3) -------------------------------------------------------
    def g_terms(self, y, node: str) -> list[tuple[str, Decimal]]:
        """The terms of G at one facing node: its pools and the sets facing it."""
        terms = []
        for p, pool in enumerate(self.pools):
            if pool["node"] != node:
                continue
            n = y[p]
            if n == 0:
                terms.append((f"pool:{pool['id']}", ZERO))
            else:
                terms.append((f"pool:{pool['id']}", RT * n * (ln(n / (self.Vd[p] * C_STD)) - 1)))
        for s, st in enumerate(self.sets):
            if st["faces"] != node:
                continue
            S = self.Sd[s]
            for b in self.pops_of_set[s]:
                B = y[self.i_pop(b)]
                v = ZERO if B == 0 else B * (self.mu0[b] + RT * ln(B / S))
                terms.append((f"bound:{self.pops[b]['id']}", v))
            R = y[self.i_set(s)]
            terms.append((f"free_sites:{st['id']}", ZERO if R == 0 else RT * R * ln(R / S)))
        return terms

    def G(self, y, node: str) -> Decimal:
        return sum((v for _, v in self.g_terms(y, node)), ZERO)

    def E_terms(self, y, node: str) -> Decimal:
        return sum((abs(v) for _, v in self.g_terms(y, node)), ZERO)

    # ---- method B: Taylor series in decimal -----------------------------------------
    def taylor_coefficients(self, y, order: int):
        P, S = self.nP, self.nS
        c = [[v] for v in y]
        pools_of = [q["pool_index"] for q in self.pops]
        sets_of = [q["set_index"] for q in self.pops]
        for k in range(order):
            J = []
            for b in range(self.nB):
                nser = c[pools_of[b]]
                Bser = c[P + S + b]
                if self.unshared:
                    conv = self.Sd[sets_of[b]] * nser[k] - math.sumprod(nser[: k + 1], Bser[k::-1])
                else:
                    conv = math.sumprod(nser[: k + 1], c[P + sets_of[b]][k::-1])
                J.append(self.a[b] * conv - self.koff[b] * Bser[k])
            kk = k + 1
            for p in range(P):
                bs = self.pops_of_pool[p]
                c[p].append(-sum((J[b] for b in bs), ZERO) / kk if bs else ZERO)
            for s in range(S):
                bs = self.pops_of_set[s][:1] if self.dR_first_only else self.pops_of_set[s]
                c[P + s].append(-sum((J[b] for b in bs), ZERO) / kk)
            for b in range(self.nB):
                c[P + S + b].append(J[b] / kk)
        return c

    def taylor_scales(self, y) -> list[float]:
        """Each amount's own scale for the step control: its pool's total, or its set's S."""
        tot = self.pool_totals(y)
        sc = [float(abs(tot[p])) for p in range(self.nP)]
        sc += [s["S"] for s in self.sets]
        sc += [self.sets[q["set_index"]]["S"] for q in self.pops]
        return [max(v, 1e-300) for v in sc]

    def taylor(self, y0, t0: Decimal, t1: Decimal, order: int, tol: float, scales: list[float]):
        """Integrate from t0 to t1 exactly (the last step lands on t1).

        The step keeps the last two Taylor terms below tol of each amount's own scale.
        """
        y = list(y0)
        t = t0
        steps = 0
        root = tol ** (1.0 / (order + 1))
        while t < t1:
            c = self.taylor_coefficients(y, order)
            rho = math.inf
            for k in (order - 1, order):
                m = max(abs(float(ci[k])) / scales[i] for i, ci in enumerate(c))
                if m > 0:
                    rho = min(rho, m ** (-1.0 / k))
            h = Decimal(0.9 * rho * root) if math.isfinite(rho) else t1 - t
            last = t + h >= t1
            if last:
                h = t1 - t
            ynew = []
            for ci in c:
                acc = ci[order]
                for k in range(order - 1, -1, -1):
                    acc = acc * h + ci[k]
                ynew.append(acc)
            y = ynew
            t = t1 if last else t + h
            steps += 1
        return y, steps

    # ---- method A: DOP853 in binary64 -------------------------------------------------
    def rhs(self, t, y):
        P, S = self.nP, self.nS
        n = y[:P]
        R = y[P : P + S]
        B = y[P + S :]
        c = n[self.np_pp] / self.np_Vp
        free = (self.np_S[self.np_ps] - B) if self.unshared else R[self.np_ps]
        J = self.np_kon * c * free - self.np_koff * B
        dn = -np.bincount(self.np_pp, weights=J, minlength=P)
        if self.dR_first_only:
            dR = -J[self.np_first]
        else:
            dR = -np.bincount(self.np_ps, weights=J, minlength=S)
        return np.concatenate([dn, dR, J])

    def atol_scale(self, y: np.ndarray) -> np.ndarray:
        """Each amount's natural bound: a pool's total, a set's capacity, min(S, pool total).

        Method A's inputs are exact functions of its binary64 state (Fraction, rounded once),
        so they do not depend on the decimal working precision.
        """
        yq = [Q(float(v)) for v in y]
        tot = [
            yq[p] + sum((yq[self.i_pop(b)] for b in self.pops_of_pool[p]), 0)
            for p in range(self.nP)
        ]
        sc = [float(abs(tot[p])) for p in range(self.nP)]
        sc += [s["S"] for s in self.sets]
        sc += [
            min(self.sets[q["set_index"]]["S"], float(abs(tot[q["pool_index"]]))) for q in self.pops
        ]
        return np.array([max(v, 1e-300) for v in sc], dtype=np.float64)

    def wash_binary64(self, y: np.ndarray, wash: dict, scale_bound: bool = False) -> np.ndarray:
        """SPEC §1.4's map on a binary64 state for method A: exact, then rounded once."""
        f = Q(wash["f"])
        node = wash["node"]
        cbuf = {b["ligand"]: Q(b["c"]) for b in wash["buffer"]}
        out = [Q(float(v)) for v in y]
        for i, p in enumerate(self.pools):
            if p["node"] == node:
                out[i] = (1 - f) * out[i] + f * Q(p["V"]) * cbuf[p["ligand"]]
        if scale_bound:
            for b, q in enumerate(self.pops):
                if self.sets[q["set_index"]]["faces"] == node:
                    out[self.i_pop(b)] = (1 - f) * out[self.i_pop(b)]
        return np.array([float(v) for v in out], dtype=np.float64)

    def dop853(self, y0: np.ndarray, t0: float, t1: float, rtol: float, atol: np.ndarray):
        sol = solve_ivp(self.rhs, (t0, t1), y0, method="DOP853", rtol=rtol, atol=atol)
        if not sol.success or sol.t[-1] != t1:
            raise RuntimeError(f"DOP853 failed: {sol.message}")
        return sol.y[:, -1].copy(), int(sol.nfev)
