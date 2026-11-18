"""OL2's law and OL3's bookings, written from docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md §0.2b, §0.2c (rule 4
as corrected on 18 November), §0.2d (at 7fb8816f and 95c98b5a), §2.5, §3 and §4, code-blind.

**State.** Vesicles, each with membrane counts n_i (species i with an integer area quantum k_i) and
lumen counts l_s, and a pool: finite places with counts p_s, held places at concentrations c_h.

**Geometry** (§0.2c rule 4, §0.2d 1, §4.1). W = Sum_i n_i k_i counts the footprints in quanta;
A = q W/2 (m^2); R = (A/4 pi)^(1/2) (m). N_L = Sum_s l_s over every lumen species (§0.2c rule 6);
V_osm = N_L/(N_A c_ext) (L, c_ext the outside's total osmolarity, held); V_sph = A^(3/2)/(6 sqrt pi)
in m^3, times 10^3 to L before the minimum; V = min(V_osm, V_sph); V = 0 at an empty lumen. The
reduced volume is v = 6 sqrt(pi) V/A^(3/2) (V in m^3). The tension is zero while V_osm <= V_sph; at
V_osm > V_sph it is sigma = Delta p R/2 with Delta p = k_BT (N_L/V - N_A c_ext), number densities
per m^3 (§0.2b rule 3).

**Free energy** (k_BT). F = F_pool + Sum_vesicles [F_mem + F_lumen + C_close], with
- F_pool = Sum_finite [p_s (mu0_s - ln X_pool) + ln p_s!], X_pool = N_A c0 V_pool;
- F_mem = Sum_i n_i mu0_bil,i + Sum_i ln n_i! - ln N! (the multinomial measure, c = 0);
- F_lumen = Sum_s [l_s (mu0_s - ln X_L) + ln l_s!] + N_A c_ext V, X_L = N_A c0 V; 0 when empty
  (§0.2d 3);
- C_close = 8 pi kappa + 4 pi kappa-bar, once per living vesicle (§0.2c rule 8, §0.2d 7).
A held place h has mu_h = mu0_h + ln(c_h/c0); an event books reservoir work w = -Sum_h nu_h mu_h.

**Rates** (§0.2d 2 and 4, §0.2c rules 2-5). A join (pool to membrane) or an entry (pool to lumen)
moves one molecule: a+ = k E(m) rho0 theta+(n), rho0 = N_A c0 10^3 per m^3, theta+ the pool's
activity (p/X_pool, or c/c0). k and E(m), m being the state before the move:
``insertion_area`` k_ins (m/s) and A(m); ``diffusion_radius`` D_i (m^2/s) and 4 pi R(m);
``permeation_area`` P_i (m/s) and A(m). A membrane step keeps OL1's ``count_on_m`` (multinomial):
a+ = k prod ff(n_i, alpha_i)/ff(N, r) (N(m) + 1). A pool step (first order, finite places) is
a+ = k p_A. Every reverse is a- (n') = a+(n) exp(F(n') - F(n) - w), exact between the end states
(§0.2b rule 2). The floor (§0.2c rule 5): a pair whose step changes W, one of whose end states has
W < W_floor, has rate 0; a step that leaves W unchanged fires at its own rate.

**Lysis** (§0.2b rule 3, §0.2c rule 8, §0.2d 7). An event whose end state has sigma > sigma_max
(strict) fires and lyses the vesicle: its membrane and lumen molecules go to their pool places as
monomers, its closure cost is dropped, and one row books q = -(F(n_after) - F(n)) + w, with w the
step's work plus the reservoir work of the held places that receive molecules.

**Shear work** (§0.2d 7). w_shear = Sum_j F(daughter_j) - F(parent), which holds (k - 1) C_close.

ΔF is computed incrementally (sums of logarithms, log1p and expm1), so that it is precise to
rounding although F is of order 10^5 k_BT; ``F`` itself is the plain sum.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

N_A = 6.02214076e23
K_B = 1.380649e-23
ENCOUNTER_TOKENS = ("insertion_area", "diffusion_radius")
PLANTED_LAW = ("extent_on_target", "radius_for_area", "dropped_c0", "no_lumen_term", "lumen_sign", "wrong_sign",
               "floor_all_steps", "aL_double", "laplace_double", "sphere_constant", "no_m3_to_L", "impermeants_only")
PLANTED_BOOKING = ("closure_added_again", "closure_not_released", "release_work_omitted")


@dataclass(frozen=True)
class Channel:
    """One declared step, forward direction. kind: join | entry | membrane | pool."""

    kind: str
    id: str
    constant: float
    species: str = ""                       # join, entry: the molecule moved
    reactants: tuple = ()                   # membrane, pool: ((species, count), ...)
    products: tuple = ()


@dataclass
class World2:
    """A registered OL2/OL3 world. Quantities are the floats the engine reads."""

    name: str
    q_m2: float
    c0_M: float
    c_ext_M: float
    T: float
    V_pool_L: float
    membrane: list                          # [(species, k_i, mu0_bilayer)]
    lumen: list                             # [(species, mu0_solution)]
    pool_finite: list                       # [(species, mu0_solution)]
    pool_held: list                         # [(species, mu0_solution, c_mM)]
    steps: list                             # [Channel], the declared order
    encounter: str = "insertion_area"
    sigma_max: float = math.inf             # N/m
    kappa: float = 0.0                      # k_BT
    kappa_bar: float = 0.0
    W_floor: int = 1
    moieties: dict = field(default_factory=dict)
    founder: dict = field(default_factory=dict)
    description: str = ""

    @property
    def C_close(self) -> float:
        return 8 * math.pi * self.kappa + 4 * math.pi * self.kappa_bar

    @property
    def rho0(self) -> float:
        return N_A * self.c0_M * 1e3

    @property
    def kT(self) -> float:
        return K_B * self.T

    @property
    def X_pool(self) -> float:
        return N_A * self.c0_M * self.V_pool_L

    def pool_place(self, species: str) -> tuple:
        for j, (s, mu) in enumerate(self.pool_finite):
            if s == species:
                return ("finite", j, mu, None)
        for s, mu, c in self.pool_held:
            if s == species:
                return ("held", None, mu, c)
        raise KeyError(f"{species} has no pool place")

    def vesicle_channels(self) -> list:
        return [c for c in self.steps if c.kind != "pool"]

    def pool_channels(self) -> list:
        return [c for c in self.steps if c.kind == "pool"]


@dataclass(frozen=True)
class Vesicle2:
    n: tuple        # membrane counts, in the world's membrane order
    l: tuple        # lumen counts, in the world's lumen order


def dlnfact(n: int, d: int) -> float:
    """ln (n + d)! - ln n!, as a short sum of logarithms."""
    if d >= 0:
        return sum(math.log(n + t) for t in range(1, d + 1))
    return -sum(math.log(n - t) for t in range(0, -d))


def ff(v: int, a: int) -> float:
    out = 1.0
    for t in range(a):
        out *= v - t
    return out


class Law2:
    """The law of one world (``planted`` names one wrong form, for the controls)."""

    def __init__(self, world: World2, planted: str | None = None):
        self.w = world
        self.planted = planted
        self.k = [k for _, k, _ in world.membrane]
        self.mem_index = {s: i for i, (s, _, _) in enumerate(world.membrane)}
        self.lum_index = {s: i for i, (s, _) in enumerate(world.lumen)}
        self.permeants = {c.species for c in world.steps if c.kind == "entry"}
        for c in world.steps:
            if c.kind == "membrane":
                dW = sum(self.k[self.mem_index[s]] * x for s, x in c.products) - \
                     sum(self.k[self.mem_index[s]] * x for s, x in c.reactants)
                if dW:
                    raise ValueError(f"membrane step {c.id} changes the area; the references' worlds keep it")

    # ---------------------------------------------------------------- geometry
    def W(self, v: Vesicle2) -> int:
        return sum(n * k for n, k in zip(v.n, self.k))

    def area(self, W: int) -> float:
        return self.w.q_m2 * W if self.planted == "aL_double" else self.w.q_m2 * W / 2

    def radius(self, W: int) -> float:
        return math.sqrt(self.area(W) / (4 * math.pi))

    def v_sph_L(self, W: int) -> float:
        const = 6 * math.pi if self.planted == "sphere_constant" else 6 * math.sqrt(math.pi)
        conv = 1.0 if self.planted == "no_m3_to_L" else 1e3
        return self.area(W) ** 1.5 / const * conv

    def N_L(self, v: Vesicle2) -> int:
        if self.planted == "impermeants_only":
            return sum(x for x, (s, _) in zip(v.l, self.w.lumen) if s not in self.permeants)
        return sum(v.l)

    def v_osm_L(self, v: Vesicle2) -> float:
        return self.N_L(v) / (N_A * self.w.c_ext_M)

    def _volume(self, v: Vesicle2) -> tuple:
        """(V in L, the limiting branch 'osm' or 'sph', the integer that sets it)."""
        if sum(v.l) == 0 or self.N_L(v) == 0:
            return 0.0, "empty", 0
        Vo, Vs = self.v_osm_L(v), self.v_sph_L(self.W(v))
        return (Vo, "osm", self.N_L(v)) if Vo <= Vs else (Vs, "sph", self.W(v))

    def volume_L(self, v: Vesicle2) -> float:
        return self._volume(v)[0]

    def reduced_volume(self, v: Vesicle2) -> float:
        A = self.area(self.W(v))
        return 6 * math.sqrt(math.pi) * self.volume_L(v) * 1e-3 / A ** 1.5 if A > 0 else math.inf

    def tension(self, v: Vesicle2) -> float:
        V, branch, _ = self._volume(v)
        if branch != "sph":
            return 0.0
        dp = self.w.kT * 1e3 * (self.N_L(v) / V - N_A * self.w.c_ext_M)
        factor = 1.0 if self.planted == "laplace_double" else 0.5
        return max(0.0, dp * self.radius(self.W(v)) * factor)

    def lyses(self, v: Vesicle2) -> bool:
        return self.tension(v) > self.w.sigma_max

    def derived(self, v: Vesicle2) -> dict:
        W = self.W(v)
        return dict(W=W, A_m2=self.area(W), R_m=self.radius(W), V_osm_L=self.v_osm_L(v), V_sph_L=self.v_sph_L(W),
                    V_L=self.volume_L(v), tension_N_per_m=self.tension(v), N_L=self.N_L(v))

    # ---------------------------------------------------------------- free energy
    def F_membrane(self, v: Vesicle2) -> float:
        N = sum(v.n)
        out = sum(n * mu for n, (_, _, mu) in zip(v.n, self.w.membrane))
        return out + sum(math.lgamma(n + 1) for n in v.n) - math.lgamma(N + 1)

    def _lumen_sign(self) -> float:
        return {"no_lumen_term": 0.0, "lumen_sign": -1.0}.get(self.planted, 1.0)

    def F_lumen(self, v: Vesicle2) -> float:
        V = self.volume_L(v)
        if V == 0:
            return 0.0
        lnX = math.log(N_A * self.w.c0_M * V)
        out = sum(x * (mu - lnX) + math.lgamma(x + 1) for x, (_, mu) in zip(v.l, self.w.lumen))
        return self._lumen_sign() * (out + N_A * self.w.c_ext_M * V)

    def F_vesicle(self, v: Vesicle2) -> float:
        return self.F_membrane(v) + self.F_lumen(v) + self.w.C_close

    def F_pool(self, p: tuple) -> float:
        lnX = math.log(self.w.X_pool)
        return sum(x * (mu - lnX) + math.lgamma(x + 1) for x, (_, mu) in zip(p, self.w.pool_finite))

    def F(self, vesicles, p: tuple) -> float:
        return self.F_pool(p) + sum(self.F_vesicle(v) for v in vesicles if v is not None)

    def F_scale(self, vesicles, p: tuple) -> float:
        """A magnitude for rounding tolerances: the absolute sum of F's parts."""
        out = abs(self.F_pool(p))
        for v in vesicles:
            if v is not None:
                out += abs(self.F_membrane(v)) + abs(self.F_lumen(v)) + abs(self.w.C_close)
        return out

    # ---------------------------------------------------------------- moves
    def held_mu(self, species: str):
        kind, _, mu, c = self.w.pool_place(species)
        return mu + math.log(c / (self.w.c0_M * 1e3)) if kind == "held" else None

    def activity(self, species: str, p: tuple) -> float:
        kind, j, _, c = self.w.pool_place(species)
        return c / (self.w.c0_M * 1e3) if kind == "held" else p[j] / self.w.X_pool

    def after(self, v: Vesicle2, p: tuple, ch: Channel, sign: int):
        """The vesicle and pool after one event of ch (sign +1 forward, -1 reverse); None if a
        count would go negative."""
        n, l, pl = list(v.n), list(v.l), list(p)
        if ch.kind in ("join", "entry"):
            if ch.kind == "join":
                n[self.mem_index[ch.species]] += sign
            else:
                l[self.lum_index[ch.species]] += sign
            kind, j, _, _ = self.w.pool_place(ch.species)
            if kind == "finite":
                pl[j] -= sign
        elif ch.kind == "membrane":
            for s, x in ch.reactants:
                n[self.mem_index[s]] -= sign * x
            for s, x in ch.products:
                n[self.mem_index[s]] += sign * x
        else:
            raise ValueError(ch.kind)
        if min(n + l + pl, default=0) < 0:
            return None
        return Vesicle2(tuple(n), tuple(l)), tuple(pl)

    def work(self, ch: Channel, sign: int) -> float:
        """w = -Sum_h nu_h mu_h of one event: a held place supplying a molecule gives +mu_h."""
        if ch.kind not in ("join", "entry"):
            return 0.0
        mu = self.held_mu(ch.species)
        return 0.0 if mu is None else sign * mu

    def _log_ratio(self, v: Vesicle2, v2: Vesicle2) -> float:
        """ln(V(v2)/V(v)) for two nonempty lumens, precise when both sit on the same branch."""
        V, b, x = self._volume(v)
        V2, b2, x2 = self._volume(v2)
        if b == b2 == "osm":
            return math.log1p((x2 - x) / x)
        if b == b2 == "sph":
            return 1.5 * math.log1p((x2 - x) / x)
        return math.log(V2 / V)

    def _dF_lumen(self, v: Vesicle2, v2: Vesicle2) -> float:
        s = self._lumen_sign()
        if s == 0.0:
            return 0.0
        V, V2 = self.volume_L(v), self.volume_L(v2)
        if V == 0 or V2 == 0:
            return self.F_lumen(v2) - self.F_lumen(v)
        r = self._log_ratio(v, v2)
        lnX2 = math.log(N_A * self.w.c0_M * V2)
        out = 0.0
        for (_, mu), a, b in zip(self.w.lumen, v.l, v2.l):
            if b != a:
                out += (b - a) * (mu - lnX2) + dlnfact(a, b - a)
        out += -sum(v.l) * r + N_A * self.w.c_ext_M * V * math.expm1(r)
        return s * out

    def _dF_membrane(self, v: Vesicle2, v2: Vesicle2) -> float:
        out = 0.0
        for (_, _, mu), a, b in zip(self.w.membrane, v.n, v2.n):
            if b != a:
                out += (b - a) * mu + dlnfact(a, b - a)
        N, N2 = sum(v.n), sum(v2.n)
        return out - dlnfact(N, N2 - N)

    def _dF_pool(self, p: tuple, p2: tuple) -> float:
        lnX = math.log(self.w.X_pool)
        out = 0.0
        for (_, mu), a, b in zip(self.w.pool_finite, p, p2):
            if b != a:
                out += (b - a) * (mu - lnX) + dlnfact(a, b - a)
        return out

    def dF(self, v: Vesicle2, p: tuple, v2: Vesicle2, p2: tuple) -> float:
        """F(v2, p2) - F(v, p) for one vesicle and the pool, precisely."""
        return self._dF_membrane(v, v2) + self._dF_lumen(v, v2) + self._dF_pool(p, p2)

    # ---------------------------------------------------------------- rates
    def forward(self, v: Vesicle2, p: tuple, ch: Channel) -> float:
        nxt = self.after(v, p, ch, +1)
        if nxt is None:
            return 0.0
        v2, _ = nxt
        W, W2 = self.W(v), self.W(v2)
        if W != W2 and min(W, W2) < self.w.W_floor:
            return 0.0
        if self.planted == "floor_all_steps" and W < self.w.W_floor:
            return 0.0
        if ch.kind == "membrane":
            N = sum(v.n)
            r = sum(x for _, x in ch.reactants)
            act = 1.0
            for s, x in ch.reactants:
                act *= ff(v.n[self.mem_index[s]], x)
            Wm = N - r + 1 if self.planted != "extent_on_target" else sum(v2.n) + 1
            return ch.constant * act / ff(N, r) * Wm
        W_m = W if self.planted != "extent_on_target" else W2
        if ch.kind == "join" and self.w.encounter == "insertion_area" and self.planted != "radius_for_area":
            E = self.area(W_m)
        elif ch.kind == "join":
            E = 4 * math.pi * self.radius(W_m)
        else:
            E = self.area(W_m)
        rho0 = self.w.rho0 if self.planted != "dropped_c0" else N_A * 1e3
        return ch.constant * E * rho0 * self.activity(ch.species, p)

    def rate(self, v: Vesicle2, p: tuple, ch: Channel, sign: int) -> float:
        """a+ at (v, p) for sign +1; for sign -1 the reverse event's rate at (v, p), from F."""
        if sign > 0:
            return self.forward(v, p, ch)
        back = self.after(v, p, ch, -1)
        if back is None:
            return 0.0
        vb, pb = back
        f = self.forward(vb, pb, ch)
        if f == 0.0:
            return 0.0
        e = self.dF(vb, pb, v, p) - self.work(ch, +1)
        if self.planted == "wrong_sign":
            e = -e
        return f * math.exp(e) if e < 700 else math.inf

    def pool_forward(self, p: tuple, ch: Channel) -> float:
        (a, _), = ch.reactants
        return ch.constant * p[self.w.pool_place(a)[1]]

    def pool_after(self, p: tuple, ch: Channel, sign: int):
        pl = list(p)
        (a, _), = ch.reactants
        (b, _), = ch.products
        pl[self.w.pool_place(a)[1]] -= sign
        pl[self.w.pool_place(b)[1]] += sign
        return tuple(pl) if min(pl) >= 0 else None

    def pool_rate(self, p: tuple, ch: Channel, sign: int) -> float:
        if sign > 0:
            return self.pool_forward(p, ch) if self.pool_after(p, ch, +1) is not None else 0.0
        pb = self.pool_after(p, ch, -1)
        if pb is None:
            return 0.0
        f = self.pool_forward(pb, ch)
        e = self._dF_pool(pb, p)
        return f * math.exp(-e if self.planted == "wrong_sign" else e) if f > 0 else 0.0

    # ---------------------------------------------------------------- bookings
    def release(self, v: Vesicle2, p: tuple) -> tuple:
        """Lysis: the vesicle's molecules to their pool places as monomers. Returns the pool after
        and the reservoir work of the held places that receive molecules (-x mu_h each)."""
        pl = list(p)
        w_res = 0.0
        for (s, _, _), x in zip(self.w.membrane, v.n):
            w_res += self._to_pool(pl, s, x)
        for (s, _), x in zip(self.w.lumen, v.l):
            w_res += self._to_pool(pl, s, x)
        if self.planted == "release_work_omitted":
            w_res = 0.0
        return tuple(pl), w_res

    def _to_pool(self, pl: list, species: str, x: int) -> float:
        kind, j, _, _ = self.w.pool_place(species)
        if kind == "finite":
            pl[j] += x
            return 0.0
        return -x * self.held_mu(species)

    def lysis_booking(self, v_before: Vesicle2, p_before: tuple, v_end: Vesicle2, p_end: tuple, w_step: float) -> dict:
        """One lysing event's row: n is (v_before, p_before), the step ends at (v_end, p_end), and
        the release moves v_end's molecules to the pool. q = -(F(n_after) - F(n)) + w."""
        p_after, w_res = self.release(v_end, p_end)
        kept = self.w.C_close if self.planted == "closure_not_released" else 0.0
        dF = (self.F_pool(p_after) + kept) - (self.F_vesicle(v_before) + self.F_pool(p_before))
        w = w_step + w_res
        return dict(pool_after=p_after, work=w, reservoir_work_release=w_res, heat=-dF + w, dF=dF)

    def shear_work(self, parent: Vesicle2, daughters: list) -> float:
        """w_shear = Sum_j F(daughter_j) - F(parent), over every daughter as born."""
        extra = (len(daughters) - 1) * self.w.C_close if self.planted == "closure_added_again" else 0.0
        return sum(self.F_vesicle(d) for d in daughters) - self.F_vesicle(parent) + extra
