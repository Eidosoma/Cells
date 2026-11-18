"""The multi-ligand binding closure's reference: speciation, conservation, charge, G* and P1's node.

Written from CORE_SEAMS_DESIGN §5.1–§5.3, §17 and §19, with the counting of MITOCHONDRIA_DESIGN
§1.3 and FR-4's §3–§4.4 (COMPARTMENT_PH_TRANSFER_DESIGN). No engine code is read.

**The system at one node** (volume V, pL):
- ligands L, each with a valence z_L and the registry's μ°_L/RT;
- binders B, each a row holding its total, with forms f: integer ligand counts n_{L,f} relative to
  the base form (the base has none; a form below the base has a negative count) and μ°_f/RT. The
  base form carries the row's valence z_B, and a form's charge is z_B + Σ_L n_{L,f} z_L.
- each ligand row holds its total equivalents T_L = V x_L + Σ_B Σ_f n_{L,f} V c_f, counted from
  each binder's base form; each binder row holds T_B = V Σ_f c_f.

**Equilibrium.** μ_f = μ_base + Σ_L n_{L,f} μ_L with μ = μ° + RT ln(c/c°) gives
c_f = c_base β_f Π_L (x_L/c°)^{n_{L,f}}, ln β_f = μ°_base/RT + Σ n μ°_L/RT − μ°_f/RT.
With u_L = ln(x_L/c°) and Z_B(u) = Σ_f β_f e^{n_f·u}, the free ligands minimise the convex

    Φ(u) = V c° Σ_L e^{u_L} + Σ_B T_B ln Z_B(u) − Σ_L T_L u_L,

whose gradient is the conservation residual g_L = V x_L + Σ_B T_B ⟨n_L⟩_B − T_L and whose Hessian
diag(V x) + Σ_B T_B Cov_B(n) is positive definite. So the solution is unique where it exists
(T_L > Σ_B T_B min_f n_{L,f}).

**Two solvers, in decimals:** damped Newton on Φ (``solve``), and nested bisection on the
monotone one-dimensional reductions (``solve_bisection``: the Schur complements of a positive
definite Hessian are positive). A third check is manufactured: free forms chosen, totals computed
forward, then solved back (``manufacture``).

**Energy.** G = Σ_species n (μ° + RT (ln(c/c°) − 1)) over the free ligands and every form; G* is
its value at the speciation, the minimum at fixed totals, and ∂G*/∂T_L = μ_L(free),
∂G*/∂T_B = μ_base,B(free) (checked by differences). The booked term waits for the binding owner's
statement (§19 item 3).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, Overflow

from . import exact
from .exact import context, dec, dexp, dln

NEWTON_TOL = Decimal("1e-52")
MAX_STEP = Decimal(20)       # the largest Newton step in ln units (a safeguard, not a tolerance)


# --------------------------------------------------------------------------------------------
# The system
# --------------------------------------------------------------------------------------------

class System:
    """A parsed binding system at one node: ligands, binders and their forms (from inputs)."""

    def __init__(self, spec: dict, registry: dict):
        self.spec = spec
        self.registry = registry
        species = registry["species"]
        self.ligands = list(spec["ligands"])
        self.binders = list(spec["binders"])
        self.c0 = dec(registry["standard_concentration_mM"])
        self.T_K = registry["temperature_K"]
        self.z = {L: int(species[L]["valence"]) for L in self.ligands}
        self.mu0_L = {L: dec(species[L]["mu0_RT"]) for L in self.ligands}
        self.forms = {}
        self.zb = {}
        for B in self.binders:
            b = registry["binders"][B]
            self.zb[B] = int(b["base_valence"])
            fs = []
            for f in b["forms"]:
                counts = {L: int(n) for L, n in f.get("counts", {}).items() if int(n) != 0}
                for L in counts:
                    if L not in self.ligands:
                        raise ValueError(f"form {f['id']} of {B} binds {L}, not a ligand here")
                fs.append({"id": f["id"], "counts": counts, "mu0_RT": dec(f["mu0_RT"])})
            if fs[0]["counts"]:
                raise ValueError(f"{B}: the first form must be the base form")
            self.forms[B] = fs
        with context():
            self.lnbeta = {}
            for B in self.binders:
                base = self.forms[B][0]["mu0_RT"]
                self.lnbeta[B] = [base + sum((n * self.mu0_L[L] for L, n in f["counts"].items()),
                                             Decimal(0)) - f["mu0_RT"] for f in self.forms[B]]
            self.beta = {B: [x.exp() for x in v] for B, v in self.lnbeta.items()}

    def form_valence(self, B: str, f: dict) -> int:
        return self.zb[B] + sum(n * self.z[L] for L, n in f["counts"].items())

    def admissible_floor(self, totals_B: dict) -> dict:
        """The least ligand total for which a speciation exists: Σ_B T_B min_f n_{L,f}."""
        out = {}
        with context():
            for L in self.ligands:
                out[L] = sum((dec(totals_B[B]) * min(min(f["counts"].get(L, 0)
                                                         for f in self.forms[B]), 0)
                              for B in self.binders), Decimal(0))
        return out

    # weights and moments at u
    def _weights(self, u: dict):
        with context():
            E = {L: dexp(u[L]) for L in self.ligands}
            W = {}
            for B in self.binders:
                ws = []
                for f, beta in zip(self.forms[B], self.beta[B], strict=True):
                    w = beta
                    for L, n in f["counts"].items():
                        w = w * E[L] ** n
                    ws.append(w)
                W[B] = ws
            return E, W

    def gradient_hessian(self, u: dict, totals_L: dict, totals_B: dict, V):
        """g (fmol) and H (fmol) of Φ at u."""
        V = dec(V)
        with context():
            E, W = self._weights(u)
            Ls = self.ligands
            g = {L: V * self.c0 * E[L] - dec(totals_L[L]) for L in Ls}
            H = {L: {M: (V * self.c0 * E[L] if L == M else Decimal(0)) for M in Ls} for L in Ls}
            for B in self.binders:
                TB = dec(totals_B[B])
                Z = sum(W[B], Decimal(0))
                mean = {L: sum((w * f["counts"].get(L, 0) for w, f in zip(W[B], self.forms[B],
                                                                        strict=True)),
                               Decimal(0)) / Z for L in Ls}
                for L in Ls:
                    g[L] = g[L] + TB * mean[L]
                    for M in Ls:
                        second = sum((w * f["counts"].get(L, 0) * f["counts"].get(M, 0)
                                      for w, f in zip(W[B], self.forms[B], strict=True)),
                                     Decimal(0)) / Z
                        H[L][M] = H[L][M] + TB * (second - mean[L] * mean[M])
            return g, H

    def residual(self, u: dict, totals_L: dict, totals_B: dict, V) -> dict:
        """g alone (fmol), for the bisection."""
        V = dec(V)
        with context():
            E, W = self._weights(u)
            g = {L: V * self.c0 * E[L] - dec(totals_L[L]) for L in self.ligands}
            for B in self.binders:
                TB = dec(totals_B[B])
                Z = sum(W[B], Decimal(0))
                for L in self.ligands:
                    g[L] = g[L] + TB * sum((w * f["counts"].get(L, 0)
                                            for w, f in zip(W[B], self.forms[B], strict=True)),
                                           Decimal(0)) / Z
            return g

    def potential(self, u: dict, totals_L: dict, totals_B: dict, V):
        V = dec(V)
        with context():
            E, W = self._weights(u)
            out = sum((V * self.c0 * E[L] - dec(totals_L[L]) * u[L] for L in self.ligands),
                      Decimal(0))
            for B in self.binders:
                out = out + dec(totals_B[B]) * dln(sum(W[B], Decimal(0)))
            return out


# --------------------------------------------------------------------------------------------
# Solvers
# --------------------------------------------------------------------------------------------

def _start(system: System, totals_L: dict, totals_B: dict, V) -> dict:
    """u at a feasible start: every ligand free, or a small value when its total is not positive."""
    with context():
        u = {}
        for L in system.ligands:
            T = dec(totals_L[L])
            u[L] = dln(T / (dec(V) * system.c0)) if T > 0 else Decimal(-40)
        return u


def solve(system: System, totals_L: dict, totals_B: dict, V, max_iter: int = 400) -> dict:
    """Damped Newton on Φ in decimals; returns u, the free forms and the residuals."""
    Ls = system.ligands
    with context():
        floor = system.admissible_floor(totals_B)
        for L in Ls:
            if dec(totals_L[L]) <= floor[L]:
                raise ValueError(f"ligand {L}: total {totals_L[L]} is not above {floor[L]}")
        u = _start(system, totals_L, totals_B, V)
        phi = system.potential(u, totals_L, totals_B, V)
        it, converged = 0, False
        while it < max_iter:
            it += 1
            g, H = system.gradient_hessian(u, totals_L, totals_B, V)
            rel = max(abs(g[L]) / max(abs(dec(totals_L[L])), Decimal("1e-300")) for L in Ls)
            A = [[H[L][M] for M in Ls] for L in Ls]
            step = exact.solve(A, [-g[L] for L in Ls])
            if rel < NEWTON_TOL and max(abs(s) for s in step) < NEWTON_TOL:
                converged = True
                break
            big = max(abs(s) for s in step)
            if big > MAX_STEP:
                step = [s * MAX_STEP / big for s in step]
            t = Decimal(1)
            slope = sum((g[L] * s for L, s in zip(Ls, step, strict=True)), Decimal(0))
            if rel < Decimal("1e-12") and max(abs(s) for s in step) < Decimal("1e-3"):
                # inside the quadratic region the decrease of Φ falls below its rounding, so the
                # full step is taken without the line search
                u = {L: u[L] + s for L, s in zip(Ls, step, strict=True)}
                phi = system.potential(u, totals_L, totals_B, V)
                continue
            while True:
                trial = {L: u[L] + t * s for L, s in zip(Ls, step, strict=True)}
                try:
                    ptrial = system.potential(trial, totals_L, totals_B, V)
                except (Overflow, InvalidOperation):
                    t = t / 2
                    continue
                if ptrial <= phi + Decimal("1e-4") * t * slope or t < Decimal("1e-30"):
                    break
                t = t / 2
            u, phi = trial, ptrial
        if not converged:
            raise RuntimeError("Newton did not converge")
        return speciation(system, u, totals_L, totals_B, V, iterations=it)


def solve_bisection(system: System, totals_L: dict, totals_B: dict, V, bits: int = 110,
                    lo=Decimal(-120), hi=Decimal(40)) -> dict:
    """Nested bisection: the first ligand's reduced residual is monotone in u_1 once the others
    are solved for it (a Schur complement of a positive definite Hessian), and so on inward."""
    Ls = system.ligands

    def inner(fixed: dict, depth: int):
        L = Ls[depth]
        a, b = lo, hi
        for _ in range(bits):
            mid = (a + b) / 2
            trial = dict(fixed)
            trial[L] = mid
            if depth + 1 < len(Ls):
                trial = inner(trial, depth + 1)
            g = system.residual(trial, totals_L, totals_B, V)
            if g[L] > 0:
                b = mid
            else:
                a = mid
        out = dict(fixed)
        out[L] = (a + b) / 2
        if depth + 1 < len(Ls):
            out = inner(out, depth + 1)
        return out

    with context():
        u = inner({}, 0)
        return speciation(system, u, totals_L, totals_B, V, iterations=bits)


def speciation(system: System, u: dict, totals_L: dict, totals_B: dict, V,
               iterations: int = 0) -> dict:
    """Free ligands (mM), every form's concentration (mM), mean counts, residuals and G*."""
    V = dec(V)
    with context():
        E, W = system._weights(u)
        x = {L: system.c0 * E[L] for L in system.ligands}
        forms = {}
        for B in system.binders:
            Z = sum(W[B], Decimal(0))
            cB = dec(totals_B[B]) / (V * Z)
            forms[B] = {f["id"]: cB * w for f, w in zip(system.forms[B], W[B], strict=True)}
        g, H = system.gradient_hessian(u, totals_L, totals_B, V)
        return {"u": u, "x_mM": x, "forms_mM": forms, "residual_fmol": g, "hessian_fmol": H,
                "iterations": iterations}


def manufacture(system: System, free_mM: dict, totals_B: dict, V) -> dict:
    """Totals of ligand equivalents from chosen free ligands and binder totals (exactly)."""
    V = dec(V)
    with context():
        u = {L: dln(dec(free_mM[L]) / system.c0) for L in system.ligands}
        E, W = system._weights(u)
        TL = {L: V * dec(free_mM[L]) for L in system.ligands}
        for B in system.binders:
            Z = sum(W[B], Decimal(0))
            for L in system.ligands:
                mean = sum((w * f["counts"].get(L, 0) for w, f in zip(W[B], system.forms[B],
                                                                    strict=True)), Decimal(0)) / Z
                TL[L] = TL[L] + dec(totals_B[B]) * mean
        return TL


# --------------------------------------------------------------------------------------------
# Conservation, charge and energy
# --------------------------------------------------------------------------------------------

def conservation(system: System, sp: dict, totals_L: dict, totals_B: dict, V) -> dict:
    """Each ligand's and binder's |reconstructed − total|/|total| from the speciation."""
    V = dec(V)
    with context():
        out = {}
        for L in system.ligands:
            n = V * sp["x_mM"][L]
            for B in system.binders:
                for f in system.forms[B]:
                    n = n + f["counts"].get(L, 0) * V * sp["forms_mM"][B][f["id"]]
            out[L] = abs(n - dec(totals_L[L])) / abs(dec(totals_L[L]))
        for B in system.binders:
            n = sum((V * c for c in sp["forms_mM"][B].values()), Decimal(0))
            out[B] = abs(n - dec(totals_B[B])) / dec(totals_B[B])
        return out


def charge(system: System, sp: dict, totals_L: dict, totals_B: dict, V,
           declared_valence: dict | None = None) -> dict:
    """Σ z n over the species (each form at z_B + Σ n z_L, or a declared valence) against the
    totals' Σ z_L T_L + Σ z_B T_B (fmol e)."""
    V = dec(V)
    with context():
        species = sum((system.z[L] * V * sp["x_mM"][L] for L in system.ligands), Decimal(0))
        for B in system.binders:
            for f in system.forms[B]:
                z = system.form_valence(B, f)
                if declared_valence and (B, f["id"]) in declared_valence:
                    z = declared_valence[(B, f["id"])]
                species = species + z * V * sp["forms_mM"][B][f["id"]]
        totals = sum((system.z[L] * dec(totals_L[L]) for L in system.ligands), Decimal(0))
        totals = totals + sum((system.zb[B] * dec(totals_B[B]) for B in system.binders),
                              Decimal(0))
        return {"species_fmol_e": species, "totals_fmol_e": totals,
                "difference_fmol_e": species - totals}


def free_energy(system: System, sp: dict, V) -> Decimal:
    """G = Σ n (μ° + RT (ln(c/c°) − 1)) over free ligands and every form (pJ)."""
    V = dec(V)
    with context():
        RT = exact.RT_J_per_mol(system.T_K)
        G = Decimal(0)
        for L in system.ligands:
            c = sp["x_mM"][L]
            G = G + V * c * (system.mu0_L[L] * RT + RT * (dln(c / system.c0) - 1))
        for B in system.binders:
            for f in system.forms[B]:
                c = sp["forms_mM"][B][f["id"]]
                if c > 0:
                    G = G + V * c * (f["mu0_RT"] * RT + RT * (dln(c / system.c0) - 1))
        return G / 1000


def own_terms(system: System, totals_L: dict, totals_B: dict, V) -> Decimal:
    """Σ over the stored rows of n (μ°_row + RT (ln(n/(V c°)) − 1)), each row as one species in
    its base form (the free ligand's μ° for a ligand row) (pJ). Not the booked term (§19 item 3)."""
    V = dec(V)
    with context():
        RT = exact.RT_J_per_mol(system.T_K)
        G = Decimal(0)
        rows = [(dec(totals_L[L]), system.mu0_L[L]) for L in system.ligands]
        rows += [(dec(totals_B[B]), system.forms[B][0]["mu0_RT"]) for B in system.binders]
        for n, mu0 in rows:
            if n > 0:
                G = G + n * (mu0 * RT + RT * (dln(n / (V * system.c0)) - 1))
        return G / 1000


def potentials(system: System, sp: dict) -> dict:
    """The free ligands' and free base forms' chemical potentials (J/mol)."""
    with context():
        RT = exact.RT_J_per_mol(system.T_K)
        out = {L: RT * (system.mu0_L[L] + dln(sp["x_mM"][L] / system.c0)) for L in system.ligands}
        for B in system.binders:
            base = system.forms[B][0]
            out[B] = RT * (base["mu0_RT"] + dln(sp["forms_mM"][B][base["id"]] / system.c0))
        return out


def gradient_by_differences(system: System, totals_L: dict, totals_B: dict, V,
                            rel=Decimal("1e-24")) -> dict:
    """∂G*/∂T for every row by central differences of re-solved speciations (J/mol)."""
    out = {}
    with context():
        for row in system.ligands + system.binders:
            T = dec(totals_L[row]) if row in system.ligands else dec(totals_B[row])
            h = T * rel
            vals = []
            for sgn in (1, -1):
                tl = {L: dec(v) for L, v in totals_L.items()}
                tb = {B: dec(v) for B, v in totals_B.items()}
                if row in tl:
                    tl[row] = tl[row] + sgn * h
                else:
                    tb[row] = tb[row] + sgn * h
                sp = solve(system, tl, tb, V)
                vals.append(free_energy(system, sp, V))
            out[row] = (vals[0] - vals[1]) / (2 * h) * 1000     # pJ/fmol -> J/mol
        return out


# --------------------------------------------------------------------------------------------
# Sensitivities: the conditioning floor from the inputs' rounding and from the residual's bound
# --------------------------------------------------------------------------------------------

def sensitivities(system: System, sp: dict, totals_L: dict, totals_B: dict, V,
                  residual_rel=Decimal("1e-13")) -> dict:
    """Bounds on |δ ln x_L| and |δ ln c_f| (a) from ½ ulp on every published double input (the
    totals, V and each μ°/RT), and (b) from a residual |g_L| ≤ residual_rel × |T_L| (B4's rule).

    δu = −H⁻¹ ∂g/∂p δp; ln c_f = ln T_B − ln V + ln β_f + n_f·u − ln Z_B."""
    Ls = system.ligands
    with context():
        Vd = dec(V)
        H = [[sp["hessian_fmol"][L][M] for M in Ls] for L in Ls]
        n = len(Ls)
        Hinv = [exact.solve(H, [Decimal(1 if i == j else 0) for i in range(n)]) for j in range(n)]
        Hinv = [[Hinv[j][i] for j in range(n)] for i in range(n)]      # columns -> rows
        u = sp["u"]
        _E, W = system._weights(u)
        mean = {}
        for B in system.binders:
            Z = sum(W[B], Decimal(0))
            mean[B] = {L: sum((w * f["counts"].get(L, 0) for w, f in zip(W[B], system.forms[B],
                                                                      strict=True)),
                              Decimal(0)) / Z for L in Ls}

        half_ulp = Decimal(2) ** -53

        def ulp_half(x):
            return abs(dec(x)) * half_ulp

        # inputs p and ∂g/∂p (vector over ligands), ∂(ln c_f)/∂p directly (besides via u)
        params = []
        for L in Ls:
            params.append(("T", L, {M: Decimal(-1 if M == L else 0) for M in Ls},
                           ulp_half(totals_L[L])))
        for B in system.binders:
            params.append(("T", B, {M: mean[B][M] for M in Ls}, ulp_half(totals_B[B])))
        params.append(("V", None, {M: sp["x_mM"][M] for M in Ls}, ulp_half(V)))
        for L in Ls:
            # μ°_L/RT enters every lnβ_f with n_{L,f} and x_L's own potential not at all (u is
            # relative to c°); ∂g_M/∂μ°_L = Σ_B T_B Cov_B(n_M, n_L)
            dg = {}
            for M in Ls:
                dg[M] = sum((dec(totals_B[B]) * (sum((w * f["counts"].get(M, 0) *
                                                      f["counts"].get(L, 0)
                                                      for w, f in zip(W[B], system.forms[B],
                                                                      strict=True)),
                                                     Decimal(0)) / sum(W[B], Decimal(0)) -
                                                 mean[B][M] * mean[B][L])
                             for B in system.binders), Decimal(0))
            params.append(("mu_L", L, dg, ulp_half(system.registry["species"][L]["mu0_RT"])
                           if float(system.registry["species"][L]["mu0_RT"]) != 0 else Decimal(0)))
        for B in system.binders:
            Z = sum(W[B], Decimal(0))
            for k, f in enumerate(system.forms[B]):
                if k == 0:
                    # μ°_base/RT raises every non-base ln β by 1: ∂g_M = T_B p_base ⟨n_M⟩
                    pb = W[B][0] / Z
                    dg = {M: dec(totals_B[B]) * mean[B][M] * pb for M in Ls}
                else:
                    pf = W[B][k] / Z
                    dg = {M: -dec(totals_B[B]) * pf * (f["counts"].get(M, 0) - mean[B][M])
                          for M in Ls}
                mu = system.registry["binders"][B]["forms"][k]["mu0_RT"]
                params.append(("mu_f", (B, f["id"]), dg, ulp_half(mu) if float(mu) != 0
                               else Decimal(0)))

        def du_of(dg):
            return {L: -sum((Hinv[i][j] * dg[Ls[j]] for j in range(n)), Decimal(0))
                    for i, L in enumerate(Ls)}

        bound_x = {L: Decimal(0) for L in Ls}
        bound_f = {(B, f["id"]): Decimal(0) for B in system.binders for f in system.forms[B]}
        for kind, which, dg, dp in params:
            if dp == 0:
                continue
            du = du_of(dg)
            for L in Ls:
                bound_x[L] += abs(du[L]) * dp
            for B in system.binders:
                Z = sum(W[B], Decimal(0))
                dlnZ = sum((W[B][k] / Z * sum((f["counts"].get(M, 0) * du[M] for M in Ls),
                                              Decimal(0))
                            for k, f in enumerate(system.forms[B])), Decimal(0))
                direct_lnZ = Decimal(0)
                direct_f = {f["id"]: Decimal(0) for f in system.forms[B]}
                if kind == "T" and which == B:
                    for f in system.forms[B]:
                        direct_f[f["id"]] += 1 / dec(totals_B[B])
                if kind == "V":
                    for f in system.forms[B]:
                        direct_f[f["id"]] -= 1 / Vd
                if kind == "mu_f" and which[0] == B:
                    k0 = [f["id"] for f in system.forms[B]].index(which[1])
                    if k0 == 0:
                        for k, f in enumerate(system.forms[B]):
                            if k:
                                direct_f[f["id"]] += 1
                        direct_lnZ = 1 - W[B][0] / Z
                    else:
                        direct_f[which[1]] -= 1
                        direct_lnZ = -W[B][k0] / Z
                if kind == "mu_L":
                    for f in system.forms[B]:
                        direct_f[f["id"]] += f["counts"].get(which, 0)
                    direct_lnZ = sum((W[B][k] / Z * f["counts"].get(which, 0)
                                      for k, f in enumerate(system.forms[B])), Decimal(0))
                for f in system.forms[B]:
                    d = direct_f[f["id"]] + sum((f["counts"].get(M, 0) * du[M] for M in Ls),
                                                Decimal(0)) - dlnZ - direct_lnZ
                    bound_f[(B, f["id"])] += abs(d) * dp
        # (b) the residual's bound: worst case over signs of δg_L = ± rel |T_L|, per output
        res_x = {L: Decimal(0) for L in Ls}
        res_f = {(B, f["id"]): Decimal(0) for B in system.binders for f in system.forms[B]}
        for j, M in enumerate(Ls):
            dgm = residual_rel * abs(dec(totals_L[M]))
            du = {L: -Hinv[i][j] for i, L in enumerate(Ls)}
            for L in Ls:
                res_x[L] += abs(du[L]) * dgm
            for B in system.binders:
                Z = sum(W[B], Decimal(0))
                dlnZ = sum((W[B][k] / Z * sum((f["counts"].get(N, 0) * du[N] for N in Ls),
                                              Decimal(0))
                            for k, f in enumerate(system.forms[B])), Decimal(0))
                for f in system.forms[B]:
                    d = sum((f["counts"].get(N, 0) * du[N] for N in Ls), Decimal(0)) - dlnZ
                    res_f[(B, f["id"])] += abs(d) * dgm
        return {"input_rounding": {"x": bound_x, "forms": bound_f},
                "residual_bound": {"x": res_x, "forms": res_f},
                "hessian_inverse_fmol": Hinv}


# --------------------------------------------------------------------------------------------
# P1's buffered node: the free amount against the stored equivalents
# --------------------------------------------------------------------------------------------

def p1_thresholds(system: System, ligand: str, totals_L: dict, totals_B: dict, V,
                  drawn_over_free=(Decimal("0.5"), Decimal(1), Decimal(2), Decimal(10),
                                   Decimal(100), Decimal(1000), Decimal(10000))) -> dict:
    """Rate-normalised thresholds (amounts, fmol: divide by |J| for θ·dt in s) for a route that
    draws the ligand from the node at |J|:
    - ``free``: n_free, where today's predictor (n_free − θ dt |J|) turns negative;
    - ``stored``: T_L − (its admissible floor), where the stored equivalents run out;
    - ``linearised_free``: n_free/(∂n_free/∂T_L), where the linearised free amount turns negative.
    And the equilibrated free amount after drawing Δ = k × n_free, on a ladder of k."""
    sp = solve(system, totals_L, totals_B, V)
    sens = sensitivities(system, sp, totals_L, totals_B, V)
    Ls = system.ligands
    i = Ls.index(ligand)
    with context():
        Vd = dec(V)
        n_free = Vd * sp["x_mM"][ligand]
        dfree_dT = n_free * sens["hessian_inverse_fmol"][i][i]
        floor = system.admissible_floor(totals_B)[ligand]
        T = dec(totals_L[ligand])
        ladder = []
        for k in drawn_over_free:
            drawn = k * n_free
            if T - drawn <= floor:
                ladder.append({"drawn_over_free": k, "drawn_fmol": drawn, "free_after_fmol": None,
                               "today_predictor_fmol": n_free - drawn,
                               "linearised_free_fmol": n_free - drawn * dfree_dT})
                continue
            tl = dict(totals_L)
            tl[ligand] = T - drawn
            sp2 = solve(system, tl, totals_B, V)
            ladder.append({"drawn_over_free": k, "drawn_fmol": drawn,
                           "free_after_fmol": Vd * sp2["x_mM"][ligand],
                           "today_predictor_fmol": n_free - drawn,
                           "linearised_free_fmol": n_free - drawn * dfree_dT})
        return {"n_free_fmol": n_free, "stored_fmol": T, "admissible_floor_fmol": floor,
                "dfree_dstored": dfree_dT,
                "threshold_free_fmol": n_free,
                "threshold_stored_fmol": T - floor,
                "threshold_linearised_free_fmol": n_free / dfree_dT,
                "ratio_stored_over_free": (T - floor) / n_free,
                "ratio_linearised_over_free": 1 / dfree_dT,
                "ladder": ladder}
