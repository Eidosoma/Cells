"""V1: option (d)'s chemistry in a vesicle world, with OL2's geometry (the lead's ruling Q3).

The fuel note (§1, last row; §11) says the factor has never been qualified in a vesicle world and
that (d)'s core step, a membrane place on both sides, has never run in one. These references carry
the pair identity, the cycle's drive and the true-equilibrium control into a vesicle world.

**The law.** OL2's ``ol2.Law2`` (geometry in integer quanta, F with the lumen's term and the
closure cost, joins by the declared encounter, the floor and lysis) is reused, with three
changes, all in this subclass (no registered OL2/OL3 module is edited):
1. **A membrane step's extent and factor on the true common state.** For n -> n' = n + nu the
   common state m = min(n, n') per place; a+ = k g(m) prod ff(n_i, alpha_i)/ff(N, r) (N(m) + 1)
   under ``multinomial`` (engine note §0.1, §2.1; OL1's count_on_m). ``Law2`` takes N(m) as
   N - r, which holds only when no species is on both sides; the core step B + L -> 2 L keeps L,
   so N(m) = N - 1 there. g(m) = 1 + Sum_j beta_j n_j(m)/N(m) (engine note §2.4), the same for both
   directions.
2. **Pool steps of any order, with held places** (fuel note §1, "Mass action with held
   activities"): a+ = k X prod_finite ff(p_s, alpha_s)/X^alpha_s prod_held (c_h/c0)^alpha_h, with
   X = N_A c0 V_pool; the reverse from the pool's F and the reservoir work w = -Sum_held nu_h mu_h.
3. **Moieties and catalysts** declared with the world.
Every reverse is a+ at the back state times e^(F(n') - F(n) - w), exact between the end states
(§0.2b rule 2), as in ``Law2``.

**Checks** (tolerances are OL2's, registered for worlds whose F reaches 1e5-1e6 k_BT): the
identity ln a-(n') - ln a+(n) = F(n') - F(n) - w on every registered edge and every registered
cycle's Sum ln(a_along/a_back) against Sum w, to 1e-8 absolute; the forward rates to 1e-12
relative with the floor's zero pattern and the lysis flags; the closed one-vesicle world's
stationary law against exp(-F)/Z to 1e-7 in total variation.

Planted (engine errors, each by its check): the fuel step without its reservoir work; the drive's
sign; the core step's extent N - r + 1 (``Law2``'s form); the factor at each direction's own state
(the closed world's law moves); the factor dropped (g = 1).
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

import numpy as np
import scipy.sparse as sp

from ..common import CheckResult
from ..ol2 import N_A, Channel, Law2, Vesicle2, World2, ff
from . import stationary as STAT

FORWARD_RTOL = 1e-12
LOG_ATOL = 1e-8
STATIONARY_TV = 1e-7
PLANTED_V = ("no_reservoir_work", "work_sign", "extent_n_minus_r", "at_state_factor", "factor_dropped")


@dataclass
class FuelWorld2(World2):
    """An OL2 world with catalysts on membrane steps: {step id: [(membrane species, beta), ...]}."""

    catalysts: dict = field(default_factory=dict)


class FuelLaw2(Law2):
    def __init__(self, world: FuelWorld2, planted: str | None = None):
        if planted is not None and planted not in PLANTED_V:
            raise ValueError(f"unknown planted form {planted!r}")
        super().__init__(world, None)
        self.fuel_planted = planted
        self.cats = {sid: [(self.mem_index[s], float(b)) for s, b in lst] for sid, lst in world.catalysts.items()}

    # ------------------------------------------------------------------ membrane steps
    def _membrane_forward(self, v: Vesicle2, v2: Vesicle2, ch: Channel, n_state=None) -> float:
        N = sum(v.n)
        r = sum(x for _, x in ch.reactants)
        act = 1.0
        for s, x in ch.reactants:
            act *= ff(v.n[self.mem_index[s]], x)
        if act == 0.0:
            return 0.0
        m = tuple(min(a, b) for a, b in zip(v.n, v2.n))
        Nm = sum(m)
        extent = Nm + 1
        if self.fuel_planted == "extent_n_minus_r":
            extent = N - r + 1
        g = 1.0
        cats = self.cats.get(ch.id, [])
        if cats and self.fuel_planted != "factor_dropped":
            at = v.n if self.fuel_planted == "at_state_factor" else m
            Na = sum(at)
            if Na > 0:
                g = 1.0 + sum(b * at[j] for j, b in cats) / Na
        return ch.constant * g * act / ff(N, r) * extent

    def forward(self, v: Vesicle2, p: tuple, ch: Channel) -> float:
        if ch.kind != "membrane":
            return super().forward(v, p, ch)
        nxt = self.after(v, p, ch, +1)
        if nxt is None:
            return 0.0
        v2, _ = nxt
        W, W2 = self.W(v), self.W(v2)
        if W != W2 and min(W, W2) < self.w.W_floor:
            return 0.0
        return self._membrane_forward(v, v2, ch)

    def rate(self, v: Vesicle2, p: tuple, ch: Channel, sign: int) -> float:
        """As ``Law2.rate``; the planted forms change the reverse as an engine with that error would."""
        if sign > 0:
            return self.forward(v, p, ch)
        back = self.after(v, p, ch, -1)
        if back is None:
            return 0.0
        vb, pb = back
        if ch.kind == "membrane" and self.fuel_planted == "at_state_factor":
            # the reverse's factor at its own state (v), the forward's at its own (vb)
            f = self.forward_at_own(vb, pb, ch, own=v)
        else:
            f = self.forward(vb, pb, ch)
        if f == 0.0:
            return 0.0
        e = self.dF(vb, pb, v, p) - self.work(ch, +1)
        return f * math.exp(e) if e < 700 else math.inf

    def forward_at_own(self, vb, pb, ch, own: Vesicle2) -> float:
        """The planted reverse at ``own``: the forward rate at vb with the factor evaluated at own."""
        nxt = self.after(vb, pb, ch, +1)
        if nxt is None:
            return 0.0
        save = self.fuel_planted
        self.fuel_planted = None
        base = self._membrane_forward(vb, nxt[0], ch)
        self.fuel_planted = save
        cats = self.cats.get(ch.id, [])
        if not cats or base == 0.0:
            return base
        m = tuple(min(a, b) for a, b in zip(vb.n, nxt[0].n))
        gm = 1.0 + sum(b * m[j] for j, b in cats) / sum(m) if sum(m) else 1.0
        go = 1.0 + sum(b * own.n[j] for j, b in cats) / sum(own.n) if sum(own.n) else 1.0
        return base / gm * go

    # ------------------------------------------------------------------ pool steps
    def pool_after(self, p: tuple, ch: Channel, sign: int):
        pl = list(p)
        for side, sgn in ((ch.reactants, -1), (ch.products, 1)):
            for s, x in side:
                kind, j, _, _ = self.w.pool_place(s)
                if kind == "finite":
                    pl[j] += sign * sgn * x
        return tuple(pl) if min(pl, default=0) >= 0 else None

    def pool_forward(self, p: tuple, ch: Channel) -> float:
        X = self.w.X_pool
        out = ch.constant * X
        for s, x in ch.reactants:
            kind, j, _, c = self.w.pool_place(s)
            if kind == "finite":
                out *= ff(p[j], x) / X ** x
            else:
                out *= (c / (self.w.c0_M * 1e3)) ** x
        return out

    def pool_work(self, ch: Channel, sign: int) -> float:
        """w = -Sum_held nu_h mu_h for the event (sign +1 forward)."""
        w = 0.0
        for side, sgn in ((ch.reactants, -1), (ch.products, 1)):
            for s, x in side:
                mu = self.held_mu(s)
                if mu is not None:
                    w -= sgn * x * mu
        if self.fuel_planted == "no_reservoir_work":
            w = 0.0
        elif self.fuel_planted == "work_sign":
            w = -w
        return sign * w

    def pool_rate(self, p: tuple, ch: Channel, sign: int) -> float:
        if sign > 0:
            return self.pool_forward(p, ch) if self.pool_after(p, ch, +1) is not None else 0.0
        pb = self.pool_after(p, ch, -1)
        if pb is None:
            return 0.0
        f = self.pool_forward(pb, ch)
        if f <= 0:
            return 0.0
        e = self._dF_pool(pb, p) - self.pool_work(ch, +1)
        return f * math.exp(e)

    def true_pool_work(self, ch: Channel, sign: int) -> float:
        save = self.fuel_planted
        self.fuel_planted = None
        try:
            return self.pool_work(ch, sign)
        finally:
            self.fuel_planted = save


# ---------------------------------------------------------------------------- one-vesicle tables

def channels(w: FuelWorld2) -> list:
    """Every declared step in declared order (pool steps included)."""
    return list(w.steps)


def after(law: FuelLaw2, state, ch: Channel, sign: int):
    v, p = Vesicle2(tuple(state[0]), tuple(state[1])), tuple(state[2])
    if ch.kind == "pool":
        p2 = law.pool_after(p, ch, sign)
        return None if p2 is None else (v.n, v.l, p2)
    nxt = law.after(v, p, ch, sign)
    return None if nxt is None else (nxt[0].n, nxt[0].l, nxt[1])


def rate(law: FuelLaw2, state, ch: Channel, sign: int) -> float:
    v, p = Vesicle2(tuple(state[0]), tuple(state[1])), tuple(state[2])
    if ch.kind == "pool":
        return law.pool_rate(p, ch, sign)
    return law.rate(v, p, ch, sign)


def table(law: FuelLaw2, states) -> dict:
    chs = channels(law.w)
    S, C = len(states), len(chs)
    out = dict(a_plus=np.zeros((S, C)), a_minus=np.zeros((S, C)), lyses_plus=np.zeros((S, C), dtype=bool),
               lyses_minus=np.zeros((S, C), dtype=bool))
    for i, s in enumerate(states):
        for c, ch in enumerate(chs):
            for sign, key in ((1, "plus"), (-1, "minus")):
                r = rate(law, s, ch, sign)
                out[f"a_{key}"][i, c] = r
                if r > 0 and ch.kind != "pool":
                    t = after(law, s, ch, sign)
                    out[f"lyses_{key}"][i, c] = law.lyses(Vesicle2(t[0], t[1]))
    return out


def delta(law: FuelLaw2, state, ch: Channel) -> float:
    """F(n') - F(n) - w for the forward event (honest F and w)."""
    t = after(law, state, ch, +1)
    v, p = Vesicle2(tuple(state[0]), tuple(state[1])), tuple(state[2])
    v2, p2 = Vesicle2(t[0], t[1]), t[2]
    if ch.kind == "pool":
        return law._dF_pool(p, p2) - law.true_pool_work(ch, +1)
    return law.dF(v, p, v2, p2) - law.work(ch, +1)


def _key(s) -> tuple:
    return (tuple(s[0]), tuple(s[1]), tuple(s[2]))


def check_identity(law: FuelLaw2, states, tab) -> CheckResult:
    idx = {_key(s): i for i, s in enumerate(states)}
    chs = channels(law.w)
    ap, am, lp = (np.asarray(tab[k]) for k in ("a_plus", "a_minus", "lyses_plus"))
    honest = FuelLaw2(law.w)
    worst, checked, failing, ex = 0.0, 0, 0, []
    for i, s in enumerate(states):
        for c, ch in enumerate(chs):
            if ap[i, c] <= 0 or lp[i, c]:
                continue
            t = after(honest, s, ch, +1)
            j = idx.get(_key(t))
            if j is None:
                continue
            checked += 1
            if not (am[j, c] > 0 and math.isfinite(am[j, c])):
                failing += 1
                worst = math.inf
                continue
            res = abs(math.log(am[j, c]) - math.log(ap[i, c]) - delta(honest, s, ch))
            worst = max(worst, res)
            if res > LOG_ATOL:
                failing += 1
                if len(ex) < 5:
                    ex.append(dict(state=[list(x) for x in s], step=ch.id, residual=res))
    return CheckResult("identity_with_reference_F", checked > 0 and failing == 0,
                       dict(edges_checked=checked, edges_failing=failing, max_abs_residual=worst, tol=LOG_ATOL,
                            world=law.w.name, examples=ex))


def check_forward(law: FuelLaw2, states, tab) -> CheckResult:
    ref = table(FuelLaw2(law.w), states)
    eng, rf = np.asarray(tab["a_plus"], float), ref["a_plus"]
    zero = int(np.sum((eng > 0) != (rf > 0))) + int(np.sum((np.asarray(tab["a_minus"]) > 0) != (ref["a_minus"] > 0)))
    both = (eng > 0) & (rf > 0)
    with np.errstate(invalid="ignore", divide="ignore"):
        res = np.abs(np.log(eng[both]) - np.log(rf[both])) if both.any() else np.zeros(0)
    worst = float(np.max(res)) if res.size else 0.0
    lys = int(np.sum(np.asarray(tab["lyses_plus"], bool) != ref["lyses_plus"])
              + np.sum(np.asarray(tab["lyses_minus"], bool) != ref["lyses_minus"]))
    return CheckResult("forward_form", zero == 0 and lys == 0 and worst <= FORWARD_RTOL,
                       dict(zero_pattern_mismatches=zero, lysis_flag_mismatches=lys, max_abs_log_residual=worst,
                            tol=FORWARD_RTOL, world=law.w.name))


def check_cycles(law: FuelLaw2, states, tab, cycles) -> CheckResult:
    """Each registered cycle (start state, [(step id, sign)]) against Sum w, to LOG_ATOL."""
    idx = {_key(s): i for i, s in enumerate(states)}
    names = {ch.id: k for k, ch in enumerate(channels(law.w))}
    ap, am = np.asarray(tab["a_plus"], float), np.asarray(tab["a_minus"], float)
    honest = FuelLaw2(law.w)
    worst, failing, checked, ex, sums = 0.0, 0, 0, [], {}
    for cyc in cycles:
        s = tuple(tuple(x) for x in cyc["start"])
        value, target, ok = 0.0, 0.0, True
        for sid, g in cyc["path"]:
            ch = honest.w.steps[names[sid]]
            t = after(honest, s, ch, g)
            i, j = idx.get(_key(s)), idx.get(_key(t))
            if i is None or j is None:
                ok = False
                break
            c = names[sid]
            along = ap[i, c] if g > 0 else am[i, c]
            back = am[j, c] if g > 0 else ap[j, c]
            if not (along > 0 and back > 0 and math.isfinite(along) and math.isfinite(back)):
                ok = False
                break
            value += math.log(along) - math.log(back)
            target += g * (honest.true_pool_work(ch, 1) if ch.kind == "pool" else honest.work(ch, 1))
            s = t
        checked += 1
        if not ok:
            failing += 1
            if len(ex) < 5:
                ex.append(dict(cycle=cyc, problem="a state is unlisted or a rate is zero or infinite"))
            continue
        res = value - target
        worst = max(worst, abs(res))
        sums.setdefault(cyc["kind"], []).append(value)
        if abs(res) > LOG_ATOL:
            failing += 1
            if len(ex) < 5:
                ex.append(dict(kind=cyc["kind"], value=value, expected=target, residual=res))
    return CheckResult("cycle_drive", checked > 0 and failing == 0,
                       dict(cycles_checked=checked, cycles_failing=failing, max_abs_residual=worst, tol=LOG_ATOL,
                            sums_by_kind={k: dict(count=len(v), min=min(v), max=max(v)) for k, v in sums.items()},
                            world=law.w.name, examples=ex))


# ---------------------------------------------------------------------------- the closed one-vesicle world

def closed_states(law: FuelLaw2, total: int) -> list:
    """Every one-vesicle state whose block molecules (membrane and finite pool places of species with
    the ``block`` moiety) total ``total``, with W at or above the floor. The lumen and every other
    pool place stay at the founder's counts."""
    w = law.w
    l = tuple(w.founder["l"])
    p0 = tuple(w.founder["p"])
    nm = len(w.membrane)
    pool_block = [j for j, (s, _) in enumerate(w.pool_finite) if w.moieties[s].get("block")]
    out = []
    for c in itertools.product(range(total + 1), repeat=nm + len(pool_block) - 1):
        s = sum(c)
        if s > total:
            continue
        full = c + (total - s,)
        n = full[:nm]
        p = list(p0)
        for j, v in zip(pool_block, full[nm:]):
            p[j] = v
        if law.W(Vesicle2(n, l)) < w.W_floor:
            continue
        out.append((n, l, tuple(p)))
    return sorted(out)


def check_closed(law: FuelLaw2, states, tab) -> dict:
    """True equilibrium in a vesicle: the table's stationary law against exp(-F)/Z."""
    honest = FuelLaw2(law.w)
    idx = {_key(s): i for i, s in enumerate(states)}
    chs = channels(law.w)
    ap, am = np.asarray(tab["a_plus"], float), np.asarray(tab["a_minus"], float)
    rows, cols, vals = [], [], []
    for i, s in enumerate(states):
        for c, ch in enumerate(chs):
            for sign, a in ((1, ap[i, c]), (-1, am[i, c])):
                if a > 0:
                    t = after(honest, s, ch, sign)
                    j = idx.get(_key(t))
                    if j is None:
                        return {"generator": CheckResult("generator", False, dict(problem=f"a rate at {s} leads "
                                                                                          f"outside, to {t}"))}
                    rows.append(i)
                    cols.append(j)
                    vals.append(a)
    S = len(states)
    out_rate = np.zeros(S)
    np.add.at(out_rate, rows, vals)
    Q = sp.csr_matrix((np.concatenate([vals, -out_rate]), (np.concatenate([rows, np.arange(S)]),
                                                          np.concatenate([cols, np.arange(S)]))), shape=(S, S))
    pi = STAT.stationary(Q)
    lw = -np.array([honest.F([Vesicle2(tuple(s[0]), tuple(s[1]))], tuple(s[2])) for s in states])
    lw -= lw.max()
    wt = np.exp(lw)
    wt /= wt.sum()
    tv = STAT.total_variation(pi, wt)
    Ws = [honest.W(Vesicle2(tuple(s[0]), tuple(s[1]))) for s in states]
    tense = sum(1 for s in states if honest.tension(Vesicle2(tuple(s[0]), tuple(s[1]))) > 0)
    return {"stationary_law": CheckResult("stationary_law_is_exp_minus_F", tv <= STATIONARY_TV,
                                          dict(total_variation=tv, tol=STATIONARY_TV, states=S,
                                               W_range=[min(Ws), max(Ws)], tense_states=tense,
                                               connected=STAT.connected(Q), world=law.w.name))}


# ---------------------------------------------------------------------------- documents

def world_document(w: FuelWorld2, registered: str, source: str, conventions: dict) -> dict:
    """``ool_references.world2@1`` with a transition_state_factor list on membrane steps and pool
    steps over held and finite places."""
    held = {s for s, _, _ in w.pool_held}

    def step_doc(c: Channel) -> dict:
        d = {"id": c.id, "kind": c.kind}
        if c.kind == "join":
            d.update(species=c.species, direction="pool_to_membrane", encounter=w.encounter,
                     constant={"insertion_area": "k_ins_m_per_s", "diffusion_radius": "D_m2_per_s"}[w.encounter],
                     value=c.constant)
        else:
            phase = "membrane" if c.kind == "membrane" else "pool"
            d.update(locus=phase, law="cells.stochastic_mass_action@1",
                     **({"membrane_kinetics": "count_on_m"} if phase == "membrane" else {}),
                     reactants=[{"phase": phase, "species": s, "count": x, **({"held": True} if phase == "pool"
                                                                              and s in held else {})}
                                for s, x in c.reactants],
                     products=[{"phase": phase, "species": s, "count": x, **({"held": True} if phase == "pool"
                                                                             and s in held else {})}
                               for s, x in c.products],
                     forward_rate_constant_per_s=c.constant)
            if c.kind == "membrane":
                d["transition_state_factor"] = [{"catalyst": s, "phase": "membrane", "beta": b,
                                                 "ddG_kT": math.log1p(b)} for s, b in w.catalysts.get(c.id, [])]
        return d

    species = sorted({s for s, _, _ in w.membrane} | {s for s, _ in w.lumen} | {s for s, _ in w.pool_finite}
                     | {s for s, _, _ in w.pool_held})
    mu = {}
    for s, _, m in w.membrane:
        mu.setdefault(s, {})["bilayer"] = m
    for s, m in w.lumen + w.pool_finite:
        mu.setdefault(s, {})["solution"] = m
    for s, m, _ in w.pool_held:
        mu.setdefault(s, {})["solution"] = m
    founder = {k: list(v) for k, v in w.founder.items()}
    return {"format": "ool_references.world2@1", "id": w.name, "registered": registered, "source": source,
            "description": w.description,
            "units": {"q": "m^2", "concentration": "mol/L (held places: mM)", "volume": "L", "k_ins": "m/s",
                      "sigma_max": "N/m", "energy": "k_BT", "time": "s"},
            "conventions": dict(conventions, exchange_encounter=w.encounter),
            "geometry": {"interface": "cells.assembly_geometry@1", "model": "cells.bilayer_geometry@1",
                         "area_quantum_m2": w.q_m2, "vesicle_floor_quanta": w.W_floor,
                         "sigma_max_N_per_m": w.sigma_max, "sigma_max_source": "a declared test parameter, unsourced",
                         "kappa_kT": w.kappa, "kappa_bar_kT": w.kappa_bar,
                         "closure_cost_kT": "8 pi kappa + 4 pi kappa_bar"},
            "temperature_K": w.T, "standard_concentration_M": w.c0_M, "outside_osmolarity_M": w.c_ext_M,
            "pool_volume_L": w.V_pool_L,
            "species": [{"id": s, "moieties": w.moieties[s], "standard_mu_kT": mu[s]} for s in species],
            "membrane": [{"species": s, "area_quanta": k} for s, k, _ in w.membrane],
            "lumen": [{"species": s} for s, _ in w.lumen],
            "pool": {"finite": [s for s, _ in w.pool_finite], "held_mM": {s: c for s, _, c in w.pool_held}},
            "steps": [step_doc(c) for c in w.steps], "founder": founder,
            "provenance": "unsourced: every value is a declared test parameter of OL5's fuel references"}


def pool_solute_mM(w: FuelWorld2, p: tuple) -> float:
    """The pool's declared solutes (finite and held), mM, for the c_ext rule (§0.2c rule 6)."""
    finite = sum(p) / (N_A * w.V_pool_L) * 1e3
    return finite + sum(c for _, _, c in w.pool_held)


# ---------------------------------------------------------------------------- probe states and cycles

def neighbours_and_squares(law: FuelLaw2, s) -> set:
    """s, its one-event neighbours over every channel (both directions), and every square's far
    corner (forward events of two channels)."""
    chs = channels(law.w)
    out = {_key(s)}
    for a, cha in enumerate(chs):
        for sign in (1, -1):
            t = after(law, s, cha, sign)
            if t is not None:
                out.add(_key(t))
        e1 = after(law, s, cha, 1)
        if e1 is None:
            continue
        for chb in chs[a + 1:]:
            e2 = after(law, s, chb, 1)
            top = after(law, e1, chb, 1)
            if e2 is not None and top is not None:
                out.update({_key(e2), _key(top)})
    return out


def cycle_paths(law: FuelLaw2) -> list:
    held = {s for s, _, _ in law.w.pool_held}
    ids = {c.id for c in law.w.steps}
    out = []
    for i in ("1", "2"):
        if "f1" in ids and {"F", "W"} <= held:
            out.append(("fuel", [("f1", 1), ("jB", 1), (f"a{i}", 1), (f"d{i}", 1), ("jS", -1)]))
            out.append(("fuel", [("jS", -1), ("f1", 1), (f"a{i}", 1), ("jB", 1), (f"d{i}", 1)]))
    out.append(("exchange", [("a1", 1), ("d1", 1), ("d2", -1), ("a2", -1)]))
    if {"jL1", "jL2"} <= ids:
        out.append(("exchange_pool", [("jL1", -1), ("jL2", 1), ("d2", 1), ("d1", -1)]))
    return out


def cycles_from(law: FuelLaw2, bases) -> list:
    """Every cycle path that is feasible from a base state, with the floor respected on the way."""
    names = {c.id: c for c in law.w.steps}
    out = []
    for b in bases:
        for kind, path in cycle_paths(law):
            s, ok, visited = b, True, [_key(b)]
            for sid, g in path:
                t = after(law, s, names[sid], g)
                if t is None or rate(law, s, names[sid], g) <= 0:
                    ok = False
                    break
                s = t
                visited.append(_key(t))
            if ok and visited[-1] == visited[0]:
                out.append(dict(kind=kind, start=[list(x) for x in b], path=[[sid, g] for sid, g in path]))
    return out


def kernel_probe(law: FuelLaw2, seed: int, n_base: int, lumen_for) -> tuple:
    """Random bases (W 1100-2000, reduced volume 0.3-1.5, pool counts 2-40), each with its
    neighbours and squares; the floor's boundary; the first tense states beyond sigma_max; every
    feasible cycle from the bases."""
    rng = np.random.default_rng(seed)
    w = law.w
    nm = len(w.membrane)
    bases = []
    for _ in range(n_base):
        n = tuple(int(x) for x in rng.integers(100, 500, size=nm))
        W = law.W(Vesicle2(n, (0,) * len(w.lumen)))
        l = (lumen_for(W, float(rng.uniform(0.3, 1.5))),)
        p = tuple(int(x) for x in rng.integers(2, 40, size=len(w.pool_finite)))
        bases.append((n, l, p))
    states = set()
    for b in bases:
        states |= neighbours_and_squares(law, b)
    for W in range(w.W_floor - 2, w.W_floor + 3):
        n = (W - 3 * (W // 4),) + (W // 4,) * (nm - 1)
        states |= neighbours_and_squares(law, (n, (lumen_for(W, 0.5),), (5,) * len(w.pool_finite)))
    n0 = (500, 300, 600, 600)
    W0 = law.W(Vesicle2(n0, (0,)))
    S0 = lumen_for(W0, 1.0)
    for S in range(S0, 3 * S0, 50):
        if law.tension(Vesicle2(n0, (S,))) > w.sigma_max:
            for s in ((n0, (S,), (5,) * len(w.pool_finite)), (n0, (S - 50,), (5,) * len(w.pool_finite))):
                states |= neighbours_and_squares(law, s)
            break
    cycles = cycles_from(law, bases)
    names = {c.id: c for c in w.steps}
    for cyc in cycles:
        s = tuple(tuple(x) for x in cyc["start"])
        for sid, g in cyc["path"]:
            s = after(law, s, names[sid], g)
            states.add(_key(s))
    out = sorted(states)
    for n, l, p in out:
        t = law.tension(Vesicle2(n, l))
        assert abs(t - w.sigma_max) > 1e-6 * w.sigma_max, (n, l, p)
    return out, cycles
