"""Seam C's envelope: the closure's lag behind the full kinetic binding network (amendment C3).

CORE_SEAMS_DESIGN §19, amended at 19:52 UTC: "the first-order lag of the linearised binding
network, with k_on per (binder, ligand); it reduces to B4's for one two-form buffer. Every form must
be reachable from its base by unit steps, refused at parse otherwise." This is B4's kinetic
reference (COMPARTMENT_PH_TRANSFER_DESIGN Appendix A.2), generalised to several ligands.

**The network.** At one node of volume V, a unit step r is f′ + L ⇌ f: two forms of one binder
whose counts differ by one ligand L. Its flux is

    v_r = V (k_on c_f′ x_L − k_off c_f),   k_off = k_on K_r,   K_r = c° β_f′/β_f (mM),

with β from the registry's potentials and k_on the declared (binder, ligand) value (D175's stand-in
parameter). A drive D (fmol/s) adds free ligand, or a binder's base form, at a constant rate. Then
dn/dt = N v + D.

**First order.** At the closure's state n*(T), each step's forward flux is F_r = V k_on c_f′ x_L
and dv_r = −F_r ν_rᵀ W dn, with W = diag(1/n*). So the network's Jacobian is K = −N diag(F) Nᵀ W.
The closure moves along its manifold at ∂n*/∂T C D, where ∂n*/∂T = W⁻¹ Cᵀ (C W⁻¹ Cᵀ)⁻¹. The rest of
the drive, P D = D − ∂n*/∂T C D, is held off the manifold by the lag

    δ = −K⁻¹ P D   on the conserved subspace (C δ = 0),

so that Δ ln x_L = δ_L/n_L and |ΔpH| = |Δ ln x_H|/ln 10. For one two-form buffer this is B4's
(ρ/λ)(β/ln 10 − h)/(h ln 10), with λ = k_on (h + b + K) (``b4_lag_pH``).

**A single step's rate** is B4's λ_r = k_on (x_L + c_f′ + K_r), at the closure's state. A per-step
estimate of the lag, (P D)_L/(n_L min_r λ_r), is the plant. Where a chain's scarce intermediate
makes the network's slowest mode slower than every single step, it is shown non-conservative.

**The kinetic reference.** The full nonlinear network under the drive is integrated from the
closure's state by Radau and by BDF (scipy), at rtol 1e-12 with per-species atol. At each record
time the lag is measured against the closure at that state's own totals, solved at 60 digits.

**Release steps (amendment C5).** A unit step f′ + L ⇌ f is a release step when its bound side f
still holds no more L than the base (count_f(L) ≤ 0): binding L there only restores a ligand a
form below its base released, as pi2_PO4 + H ⇌ pi2_base or mgx_MgmH + H ⇌ mgx_Mg. Nothing in the
network treats them differently: the same ν, flux and K_r. The planted disagreement
(``flip_release``) writes each release step's ligand with the wrong sign in N, the step taken to
release L where it binds it, the forward flux unchanged.
"""

from __future__ import annotations

import contextlib
import math
from decimal import Decimal

import numpy as np

try:
    from threadpoolctl import threadpool_limits as _threadpool_limits
except ImportError:                     # pragma: no cover - documented in the usage note
    _threadpool_limits = None

from . import binding as Bd
from . import exact
from .exact import context, dec, fl

LN10 = math.log(10.0)


def one_blas_thread():
    """BLAS and LAPACK on one thread (amendment C5's finding): the registered values were
    computed so, and a multi-threaded OpenBLAS moves the network's eigenvalues, so the record
    times and the kinetic rows, at about 1e-10 relative, so ``design --check`` then differs."""
    if _threadpool_limits is None:
        return contextlib.nullcontext()
    return _threadpool_limits(limits=1)


class Network:
    """A binding system's unit-step network (inputs: the system and its k_on per (binder, L))."""

    def __init__(self, spec: dict, registry: dict, kon: dict, V):
        self.system = Bd.System(spec, registry)
        sy = self.system
        self.V = dec(V)
        self.species = [("L", L) for L in sy.ligands]
        for B in sy.binders:
            for f in sy.forms[B]:
                self.species.append(("f", B, f["id"]))
        self.idx = {s: i for i, s in enumerate(self.species)}
        self.steps = []          # (i_f′, i_L, i_f, k_on, K_r, binder, ligand)
        for B in sy.binders:
            fs = sy.forms[B]
            for a, fa in enumerate(fs):
                for b, fb in enumerate(fs):
                    diff = {L: fb["counts"].get(L, 0) - fa["counts"].get(L, 0)
                            for L in sy.ligands}
                    if sorted(diff.values()) == [0] * (len(diff) - 1) + [1]:
                        L = next(k for k, v in diff.items() if v == 1)
                        if (B, L) not in kon:
                            raise ValueError(f"no k_on for ({B}, {L})")
                        with context():
                            Kr = sy.c0 * (sy.lnbeta[B][a] - sy.lnbeta[B][b]).exp()
                        self.steps.append((self.idx[("f", B, fa["id"])], self.idx[("L", L)],
                                           self.idx[("f", B, fb["id"])], dec(kon[(B, L)]), Kr,
                                           B, L))
        self.check_reachable()

    def check_reachable(self) -> None:
        """§19: every form must be reachable from its base by unit steps (either direction)."""
        sy = self.system
        for B in sy.binders:
            ids = [f["id"] for f in sy.forms[B]]
            seen, stack = {ids[0]}, [ids[0]]
            adj = {i: set() for i in ids}
            for fa, _l, fb, _k, _K, BB, _L in self.steps:
                if BB == B:
                    a, b = self.species[fa][2], self.species[fb][2]
                    adj[a].add(b)
                    adj[b].add(a)
            while stack:
                v = stack.pop()
                for w in adj[v]:
                    if w not in seen:
                        seen.add(w)
                        stack.append(w)
            missing = [i for i in ids if i not in seen]
            if missing:
                raise ValueError(f"{B}: forms {missing} are not reachable from the base by unit "
                                 f"steps")

    def release_steps(self) -> list:
        """Amendment C5: the indices of the release steps, whose bound form f has count_f(L) ≤ 0."""
        sy = self.system
        out = []
        for r, (_fa, _lg, fb, _k, _Kr, B, L) in enumerate(self.steps):
            fid = self.species[fb][2]
            f = next(x for x in sy.forms[B] if x["id"] == fid)
            if f["counts"].get(L, 0) <= 0:
                out.append(r)
        return out

    # ----------------------------------------------------------------------------------------
    def closure_state(self, totals_L: dict, totals_B: dict) -> list:
        """n* (fmol) of every species at the closure's speciation (60 digits)."""
        sy = self.system
        sp = Bd.solve(sy, totals_L, totals_B, self.V)
        n = [Decimal(0)] * len(self.species)
        for L in sy.ligands:
            n[self.idx[("L", L)]] = self.V * sp["x_mM"][L]
        for B in sy.binders:
            for fid, c in sp["forms_mM"][B].items():
                n[self.idx[("f", B, fid)]] = self.V * c
        return n

    def conservation_matrix(self) -> list:
        sy = self.system
        rows = []
        for L in sy.ligands:
            row = [Decimal(0)] * len(self.species)
            row[self.idx[("L", L)]] = Decimal(1)
            for B in sy.binders:
                for f in sy.forms[B]:
                    row[self.idx[("f", B, f["id"])]] = Decimal(f["counts"].get(L, 0))
            rows.append(row)
        for B in sy.binders:
            row = [Decimal(0)] * len(self.species)
            for f in sy.forms[B]:
                row[self.idx[("f", B, f["id"])]] = Decimal(1)
            rows.append(row)
        return rows

    def totals_of(self, n: list) -> tuple:
        sy = self.system
        C = self.conservation_matrix()
        with context():
            T = [sum((C[i][j] * dec(n[j]) for j in range(len(n))), Decimal(0))
                 for i in range(len(C))]
        TL = {L: T[k] for k, L in enumerate(sy.ligands)}
        TB = {B: T[len(sy.ligands) + k] for k, B in enumerate(sy.binders)}
        return TL, TB

    def step_rates(self, n: list) -> list:
        """B4's λ_r = k_on (x_L + c_f′ + K_r) per step, at n (1/s)."""
        with context():
            return [k * (n[lg] / self.V + n[fa] / self.V + Kr)
                    for fa, lg, _fb, k, Kr, _B, _L in self.steps]

    def linearised(self, n: list, drive: list, flip_release: bool = False) -> dict:
        """K = −N diag(F) Nᵀ W, ∂n*/∂T, P D and the first-order lag δ (60 digits).
        ``flip_release`` plants the release steps' ligand with the wrong sign (amendment C5)."""
        S, R = len(self.species), len(self.steps)
        C = self.conservation_matrix()
        release = set(self.release_steps()) if flip_release else set()
        with context():
            N = [[Decimal(0)] * R for _ in range(S)]
            F = []
            for r, (fa, lg, fb, k, _Kr, _B, _L) in enumerate(self.steps):
                N[fa][r] -= 1
                N[lg][r] += 1 if r in release else -1
                N[fb][r] += 1
                F.append(k * n[fa] * n[lg] / self.V)
            M = [[sum((N[i][r] * F[r] * N[j][r] for r in range(R)), Decimal(0))
                  for j in range(S)] for i in range(S)]
            Winv = [dec(x) for x in n]
            # ∂n*/∂T = W⁻¹ Cᵀ (C W⁻¹ Cᵀ)⁻¹
            m = len(C)
            G = [[sum((C[a][s] * Winv[s] * C[b][s] for s in range(S)), Decimal(0))
                  for b in range(m)] for a in range(m)]
            D = [dec(x) for x in drive]
            CD = [sum((C[a][s] * D[s] for s in range(S)), Decimal(0)) for a in range(m)]
            lam = exact.solve(G, CD)
            dn_star = [Winv[s] * sum((C[a][s] * lam[a] for a in range(m)), Decimal(0))
                       for s in range(S)]
            PD = [D[s] - dn_star[s] for s in range(S)]
            # M W δ = P D with C δ = 0: y = (M + Cᵀ C)⁻¹ P D, then the null-space correction
            MC = [[M[i][j] + sum((C[a][i] * C[a][j] for a in range(m)), Decimal(0))
                   for j in range(S)] for i in range(S)]
            y = exact.solve(MC, PD)
            Cy = [sum((C[a][s] * Winv[s] * y[s] for s in range(S)), Decimal(0)) for a in range(m)]
            mu = exact.solve(G, Cy)
            yy = [y[s] - sum((C[a][s] * mu[a] for a in range(m)), Decimal(0)) for s in range(S)]
            delta = [Winv[s] * yy[s] for s in range(S)]
            K = [[-M[i][j] / dec(n[j]) for j in range(S)] for i in range(S)]
            return {"K": K, "dn_star_dt": dn_star, "PD": PD, "delta": delta, "F": F}

    def slowest_rates(self, K: list, how_many: int = 3) -> list:
        """The network's slowest relaxation rates (1/s): −eigenvalues of K on the reaction space."""
        A = np.array([[fl(x) for x in row] for row in K])
        with one_blas_thread():
            ev = np.sort(-np.linalg.eigvals(A).real)
        scale = max(abs(ev))
        nonzero = [float(x) for x in ev if abs(x) > 1e-9 * scale]
        return nonzero[:how_many]

    # ----------------------------------------------------------------------------------------
    def rhs_jac(self, drive):
        """float64 rhs and Jacobian of the full network, for scipy."""
        steps = [(fa, lg, fb, float(k), float(Kr)) for fa, lg, fb, k, Kr, _B, _L in self.steps]
        V = float(self.V)
        D = np.array([float(x) for x in drive])
        S = len(self.species)

        def rhs(_t, n):
            out = D.copy()
            for fa, lg, fb, k, Kr in steps:
                v = k * n[fa] * n[lg] / V - k * Kr * n[fb]
                out[fa] -= v
                out[lg] -= v
                out[fb] += v
            return out

        def jac(_t, n):
            J = np.zeros((S, S))
            for fa, lg, fb, k, Kr in steps:
                dv = np.zeros(S)
                dv[fa] = k * n[lg] / V
                dv[lg] = k * n[fa] / V
                dv[fb] = -k * Kr
                J[fa] -= dv
                J[lg] -= dv
                J[fb] += dv
            return J

        return rhs, jac

    def integrate(self, n0: list, drive: list, times: list, method: str, rtol: float) -> list:
        from scipy.integrate import solve_ivp
        rhs, jac = self.rhs_jac(drive)
        y0 = np.array([float(x) for x in n0])
        atol = np.maximum(np.abs(y0), 1e-30) * rtol * 1e-2
        with one_blas_thread():
            sol = solve_ivp(rhs, (0.0, float(times[-1])), y0, method=method, jac=jac, rtol=rtol,
                            atol=atol, t_eval=[float(t) for t in times], dense_output=False)
        if not sol.success:
            raise RuntimeError(sol.message)
        return [sol.y[:, k].copy() for k in range(sol.y.shape[1])]


def b4_lag_pH(h_mM, B_mM, K_mM, kon, dHdt_mM_s) -> float:
    """B4's envelope (COMPARTMENT_PH_TRANSFER_DESIGN §4.2) for one two-form buffer:
    |ΔpH| ≈ (ρ/λ)(β/ln 10 − h)/(h ln 10), λ = k_on (h + b + K), ρ = |dH̄/dt|/(β/ln 10)."""
    b = B_mM * K_mM / (h_mM + K_mM)
    lam = kon * (h_mM + b + K_mM)
    beta_ln10 = h_mM + B_mM * K_mM * h_mM / (h_mM + K_mM) ** 2
    rho = abs(dHdt_mM_s) / beta_ln10
    return (rho / lam) * (beta_ln10 - h_mM) / (h_mM * LN10)


def run_case(case: dict, registry: dict, kinetic: bool = True, flip_release: bool = False) -> dict:
    """Every envelope quantity for one registered case (see the usage note); ``flip_release``
    plants amendment C5's sign error in the first-order lag."""
    spec = {"ligands": case["ligands"], "binders": case["binders"]}
    kon = {(B, L): k for B, L, k in case["kon_per_mM_per_s"]}
    net = Network(spec, registry, kon, case["volume_pL"])
    TL, TB = case["totals"]["ligands_fmol"], case["totals"]["binders_fmol"]
    n = net.closure_state(TL, TB)
    drive = [Decimal(0)] * len(net.species)
    for key, rate in case["drive_fmol_per_s"]:
        sp_ = ("L", key) if key in case["ligands"] else ("f", key,
                                                         net.system.forms[key][0]["id"])
        drive[net.idx[sp_]] = dec(rate)
    lin = net.linearised(n, drive, flip_release)
    lam = net.step_rates(n)
    out = {"species": ["/".join(s[1:]) for s in net.species],
           "closure_fmol": [fl(x) for x in n],
           "steps": [{"from": net.species[fa][2], "ligand": L, "to": net.species[fb][2],
                      "k_on": fl(k), "K_r_mM": fl(Kr), "lambda_per_s": fl(lr)}
                     for (fa, _l, fb, k, Kr, _B, L), lr in zip(net.steps, lam, strict=True)],
           "slowest_network_rates_per_s": net.slowest_rates(lin["K"]),
           "min_step_rate_per_s": fl(min(lam))}
    rel = net.release_steps()
    if rel:
        out["release_steps"] = [{"from": net.species[net.steps[r][0]][2],
                                 "ligand": net.steps[r][6],
                                 "to": net.species[net.steps[r][2]][2]} for r in rel]
    with context():
        lag = {}
        per_step_all, per_step_own = {}, {}
        for L in case["ligands"]:
            i = net.idx[("L", L)]
            lag[L] = lin["delta"][i] / n[i]
            per_step_all[L] = lin["PD"][i] / (n[i] * min(lam))
            own = min(lr for lr, st in zip(lam, net.steps, strict=True) if st[6] == L)
            per_step_own[L] = lin["PD"][i] / (n[i] * own)
    out["first_order_dln"] = {L: fl(v) for L, v in lag.items()}
    out["per_step_estimate_dln"] = {"min_over_all_steps": {L: fl(v) for L, v in
                                                           per_step_all.items()},
                                    "min_over_the_ligands_steps": {L: fl(v) for L, v in
                                                                   per_step_own.items()}}
    if "H" in case["ligands"]:
        out["first_order_pH"] = abs(fl(lag["H"])) / LN10
        out["per_step_pH"] = abs(fl(per_step_all["H"])) / LN10
    if len(case["binders"]) == 1 and len(net.system.forms[case["binders"][0]]) == 2 \
            and case["ligands"] == ["H"]:
        B = case["binders"][0]
        V = float(case["volume_pL"])
        h = float(n[0]) / V
        Bm = float(TB[B]) / V
        K = float(net.steps[0][4])
        rate = float(dict(case["drive_fmol_per_s"])["H"]) / V
        out["b4_formula_pH"] = b4_lag_pH(h, Bm, K, float(net.steps[0][3]), rate)
    if kinetic:
        out["kinetic"] = kinetic_run(net, n, drive, case, out["slowest_network_rates_per_s"][0])
    return out


def kinetic_run(net: Network, n0: list, drive: list, case: dict, slowest: float) -> dict:
    """The full network under the drive, by Radau and BDF; the lag at each record time against
    the closure at that state's own totals, and against the first-order lag there."""
    times = [m / slowest for m in case["record_slow_times"]]
    runs = {m: net.integrate(n0, drive, times, m, case.get("rtol", 1e-12))
            for m in ("Radau", "BDF")}
    rows = []
    for k, t in enumerate(times):
        row = {"t_s": t, "lag_dln": {}, "floor_dln": {}, "first_order_dln": {}}
        y = runs["Radau"][k]
        TL, TB = net.totals_of(list(y))
        ns = net.closure_state(TL, TB)
        lin = net.linearised(ns, drive)
        for L in net.system.ligands:
            i = net.idx[("L", L)]
            with context():
                lr = (dec(float(y[i])) / ns[i]).ln()
                lb = (dec(float(runs["BDF"][k][i])) / ns[i]).ln()
                row["lag_dln"][L] = fl(lr)
                row["floor_dln"][L] = abs(fl(lr - lb))
                row["first_order_dln"][L] = fl(lin["delta"][i] / ns[i])
        rows.append(row)
    return {"times_over_slowest": case["record_slow_times"], "rows": rows}
