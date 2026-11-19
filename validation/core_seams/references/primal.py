"""Seam C's second route: the speciation as the primal Gibbs minimum, by Newton on reaction extents.

Amendment C1 (CORE_SEAMS_DESIGN §19, amended 18 November 2026, 19:52 UTC). The engine and
``binding.solve`` share the dual formulation (Newton on the free ligands' potentials). This module
verifies their solutions by a route that shares only the inputs: the registry's μ°/RT and the
forms' ligand counts. It never forms an association constant β or a dual variable, and imports
nothing from ``binding``.

**The primal problem.** Species are the free ligands L and every form f of every binder B, its base
included. At fixed totals the node's free energy

    G/RT = Σ_s n_s (μ°_s/RT + ln(n_s/(V c°)) − 1)

is minimised over the species amounts n_s > 0 under exact conservation:
- T_L = n_L + Σ_f n_{L,f} n_f;
- T_B = Σ_{f ∈ B} n_f.

The unknowns are the extents ξ_f of every non-base form's formation from its base and ligands:
- n_f = ξ_f;
- n_base(B) = T_B − Σ_{f ∈ B} ξ_f;
- n_L = T_L − Σ_f n_{L,f} ξ_f.

So conservation holds by construction. The gradient ∂(G/RT)/∂ξ_f is the formation reaction's
ΔG/RT, μ̃_f − μ̃_base − Σ_L n_{L,f} μ̃_L per RT. The Hessian is Σ_s (∂n_s/∂ξ_f)(∂n_s/∂ξ_g)/n_s,
positive definite.

**Newton.** Damped Newton with a fraction-to-boundary rule (every species stays positive) and
Armijo backtracking on G. It starts from an interior point built from the totals alone (``start``).

**The certificate.** max_f |ΔG_f/RT| ≤ 1e-50 is the primal's own optimality condition, checked
without the dual.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, Overflow

from . import exact
from .exact import context, dec, dln

CERTIFICATE = Decimal("1e-50")


class Primal:
    """The species, conservation and standard potentials of one binding system (inputs only)."""

    def __init__(self, spec: dict, registry: dict, totals_L: dict, totals_B: dict, V):
        self.ligands = list(spec["ligands"])
        self.binders = list(spec["binders"])
        self.c0 = dec(registry["standard_concentration_mM"])
        self.V = dec(V)
        self.T_L = {L: dec(totals_L[L]) for L in self.ligands}
        self.T_B = {B: dec(totals_B[B]) for B in self.binders}
        self.mu_L = {L: dec(registry["species"][L]["mu0_RT"]) for L in self.ligands}
        self.base, self.forms = {}, []          # forms: (binder, id, counts, mu0_RT), non-base
        for B in self.binders:
            fs = registry["binders"][B]["forms"]
            self.base[B] = (fs[0]["id"], dec(fs[0]["mu0_RT"]))
            for f in fs[1:]:
                counts = {L: int(n) for L, n in f.get("counts", {}).items() if int(n) != 0}
                self.forms.append((B, f["id"], counts, dec(f["mu0_RT"])))

    def amounts(self, xi: list) -> dict:
        """Every species' amount (fmol) at extents ξ, conservation exact."""
        n = {("L", L): self.T_L[L] for L in self.ligands}
        for B in self.binders:
            n[("B", B)] = self.T_B[B]
        for (B, fid, counts, _mu), x in zip(self.forms, xi, strict=True):
            n[("f", fid)] = x
            n[("B", B)] -= x
            for L, c in counts.items():
                n[("L", L)] -= c * x
        return n

    def species(self):
        """(key, μ°/RT) for every species: free ligands, bases, non-base forms."""
        out = [(("L", L), self.mu_L[L]) for L in self.ligands]
        out += [(("B", B), self.base[B][1]) for B in self.binders]
        out += [(("f", fid), mu) for _B, fid, _c, mu in self.forms]
        return out

    def objective(self, xi: list):
        """G/RT, or None outside the interior."""
        n = self.amounts(xi)
        with context():
            G = Decimal(0)
            for key, mu in self.species():
                v = n[key]
                if v <= 0:
                    return None
                G += v * (mu + dln(v / (self.V * self.c0)) - 1)
            return G

    def potentials(self, n: dict) -> dict:
        """μ̃/RT of every species at amounts n."""
        with context():
            return {key: mu + dln(n[key] / (self.V * self.c0)) for key, mu in self.species()}

    def gradient_hessian(self, xi: list):
        n = self.amounts(xi)
        mu = self.potentials(n)
        m = len(self.forms)
        # ∂n_s/∂ξ_f: the form +1, its base −1, each ligand −n_{L,f}
        cols = []
        for B, fid, counts, _mu in self.forms:
            col = {("f", fid): Decimal(1), ("B", B): Decimal(-1)}
            for L, c in counts.items():
                col[("L", L)] = col.get(("L", L), Decimal(0)) - c
            cols.append(col)
        with context():
            g = [sum((d * mu[k] for k, d in col.items()), Decimal(0)) for col in cols]
            H = [[Decimal(0)] * m for _ in range(m)]
            for i in range(m):
                for j in range(i, m):
                    s = Decimal(0)
                    for k, d in cols[i].items():
                        if k in cols[j]:
                            s += d * cols[j][k] / n[k]
                    H[i][j] = H[j][i] = s
            return g, H, n

    def start(self) -> list:
        """An interior start from the totals alone.

        Each binder spreads a share ε of its total evenly over all its forms, base included, and
        puts the rest on an anchor form, at first its base. While some free ligand is not
        positive, each binder moves its anchor to its form with the smallest count of that
        ligand (a form below the base frees it), and ε halves when no anchor can move."""
        anchor = {B: None for B in self.binders}          # None: the base form
        per_binder = {B: [i for i, f in enumerate(self.forms) if f[0] == B] for B in self.binders}
        eps = Decimal("0.1")
        for _attempt in range(400):
            xi = [Decimal(0)] * len(self.forms)
            for B in self.binders:
                idx = per_binder[B]
                spread = self.T_B[B] * eps / (len(idx) + 1)
                for i in idx:
                    xi[i] = spread
                if anchor[B] is not None:
                    xi[anchor[B]] += self.T_B[B] * (1 - eps)
            n = self.amounts(xi)
            bad = [L for L in self.ligands if n[("L", L)] <= 0]
            if not bad and all(n[("B", B)] > 0 for B in self.binders):
                return xi
            moved = False
            for L in bad:
                for B in self.binders:
                    idx = per_binder[B]
                    if not idx:
                        continue
                    i = min(idx, key=lambda i: self.forms[i][2].get(L, 0))
                    now = 0 if anchor[B] is None else self.forms[anchor[B]][2].get(L, 0)
                    if self.forms[i][2].get(L, 0) < now:
                        anchor[B] = i
                        moved = True
            if not moved:
                eps = eps / 2
                if eps < Decimal("1e-40"):
                    break
        return self._lp_start()

    def _lp_start(self) -> list:
        """Amendment C4: where the anchors fail (a form that frees one ligand binds another), the
        start is the joint-margin LP's binder distribution (HiGHS, doubles, no dual variable of
        the speciation), mixed with the uniform one until every species is positive. Refused
        when no interior exists."""
        import numpy as np
        from scipy.optimize import linprog
        cols = list(range(len(self.forms)))
        nb = len(self.binders)
        bases = {B: len(self.forms) + k for k, B in enumerate(self.binders)}
        nv = len(self.forms) + nb + 1
        c = np.zeros(nv)
        c[-1] = -1.0
        A_ub = np.zeros((len(self.ligands), nv))
        for i, L in enumerate(self.ligands):
            for j in cols:
                B, _fid, counts, _mu = self.forms[j]
                A_ub[i, j] = float(self.T_B[B]) * counts.get(L, 0)
            A_ub[i, -1] = 1.0
        b_ub = np.array([float(self.T_L[L]) for L in self.ligands])
        A_eq = np.zeros((nb, nv))
        for k, B in enumerate(self.binders):
            A_eq[k, bases[B]] = 1.0
            for j in cols:
                if self.forms[j][0] == B:
                    A_eq[k, j] = 1.0
        bounds = [(0, None)] * (nv - 1) + [(None, None)]
        r = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=np.ones(nb), bounds=bounds,
                    method="highs")
        if not r.success or -r.fun <= 0:
            raise ValueError("no interior start found: the totals are not jointly valid")
        mix = Decimal("0.5")
        for _ in range(200):
            xi = []
            for j in cols:
                B = self.forms[j][0]
                k = sum(1 for f in self.forms if f[0] == B) + 1
                xi.append(self.T_B[B] * ((1 - mix) * Decimal(float(r.x[j])) + mix / k))
            n = self.amounts(xi)
            if all(v > 0 for v in n.values()):
                return xi
            mix = mix / 2
        raise ValueError("no interior start found")

    def solve(self, max_iter: int = 400) -> dict:
        xi = self.start()
        with context():
            G = self.objective(xi)
            for it in range(1, max_iter + 1):
                g, H, n = self.gradient_hessian(xi)
                worst = max((abs(x) for x in g), default=Decimal(0))
                if worst <= CERTIFICATE:
                    return self._result(xi, it, worst)
                step = exact.solve(H, [-x for x in g])
                # fraction to the boundary: keep every species positive
                t = Decimal(1)
                trial_n = self.amounts([x + s for x, s in zip(xi, step, strict=True)])
                for key, v in trial_n.items():
                    if v <= 0:
                        d = v - n[key]                     # the step's change of that species
                        t = min(t, Decimal("0.99") * n[key] / (-d))
                slope = sum((a * b for a, b in zip(g, step, strict=True)), Decimal(0))
                while True:
                    trial = [x + t * s for x, s in zip(xi, step, strict=True)]
                    try:
                        Gt = self.objective(trial)
                    except (Overflow, InvalidOperation):
                        Gt = None
                    if Gt is not None and (Gt <= G + Decimal("1e-4") * t * slope or
                                           worst < Decimal("1e-20")):
                        break
                    t = t / 2
                    if t < Decimal("1e-40"):
                        raise RuntimeError("primal line search failed")
                xi, G = trial, Gt
        raise RuntimeError("primal Newton did not converge")

    def _result(self, xi, it, worst) -> dict:
        n = self.amounts(xi)
        with context():
            x = {L: n[("L", L)] / self.V for L in self.ligands}
            forms = {B: {self.base[B][0]: n[("B", B)] / self.V} for B in self.binders}
            for B, fid, _c, _mu in self.forms:
                forms[B][fid] = n[("f", fid)] / self.V
            return {"x_mM": x, "forms_mM": forms, "iterations": it, "certificate": worst,
                    "G_over_RT": self.objective(xi)}


def solve_primal(spec: dict, registry: dict, totals_L: dict, totals_B: dict, V) -> dict:
    """The primal speciation at the registered totals (see the module's docstring)."""
    return Primal(spec, registry, totals_L, totals_B, V).solve()
