"""Node kinetics and bookings: an independent reference for local_species_reactions@1 (D152).

Written from docs/SHARED_INVENTORY_REACTIONS_DESIGN.md, Appendix A (with §2.2, §3.1-§3.4 and
§4.2), and from textbook sources, never from the engine's operator code. NumPy and the standard
library only; nothing here imports `cells` (tests/unit/test_reaction_references.py checks this
statically). The interface is documented in validation/reactions/REFERENCES_USAGE.md.

Units are @3's (Appendix A): amounts fmol, volumes pL, concentrations mM (= fmol/pL), time s,
energies pJ. RT is an input in pJ/fmol (1e-3 R T with R in J/(mol K); `rt_pJ_per_fmol`). The
standard concentration c0 (mM) is part of the network declaration.

Laws (§2.2, Appendix A), at node i with c = n/V_i and activities a = c/c0:
* mass_action (driven): J = m F k V prod_s c_s^alpha_s, k in mM^(1-q) s^-1, q = sum alpha <= 3
  (Guldberg and Waage; Keener & Sneyd 2009, ch. 1).
* michaelis_menten (driven): J = m F V k_cat c_E c_S/(K_M + c_S) with a catalyst E that is read,
  not written; or J = m F V V_max c_S/(K_M + c_S) (Michaelis & Menten 1913; Briggs & Haldane
  1925; Keener & Sneyd 2009, ch. 1).
* passive, ideal detailed-balanced mass action: J = m V c0 k_f [exp(f) - exp(r)] with
  f = sum alpha ln a and r = sum beta ln a + sum nu mu0/RT, evaluated in Appendix A's stable form
  m V c0 k_f exp(max(f, r)) (-expm1(-|A|)) sign(A), A = f - r (Rao & Esposito 2016). Its
  unidirectional fluxes are J+ = m V c0 k_f exp(f) and J- = m V c0 k_f exp(r).
* factors, on driven laws only: Hill activation x^n/(K^n + x^n) and inhibition K^n/(K^n + x^n),
  evaluated as exp(-logaddexp(0, -/+ n (ln x - ln K))) with x the factor species' concentration
  (Hill 1910; Weiss 1997; Keener & Sneyd 2009, ch. 1).

The half-step (§4.2, Appendix A) is SSPRK(3,3) (Shu & Osher 1988; Gottlieb, Shu & Tadmor 2001)
in its extent-consistent Butcher form, one sub-step of length h (the engine's h = dt/2):
    Y1 = n,  Y2 = n + h nu J(Y1),  Y3 = n + h nu (J(Y1) + J(Y2))/4,
    dxi = h (J(Y1) + J(Y2) + 4 J(Y3))/6,  n' = n + nu dxi.
Stage condition: h max_s L_s(Y_k) <= 1/2 at k = 1, 2, 3, with L_s the consumption rate per
amount written with unidirectional fluxes (never a passive route's signed net rate). A step
that fails it, or has a non-positive or non-finite stage or result, is refused.

Free energy (§3.3, Appendix A): G_i = RT sum_s n_s (ln(n_s/V_i) - 1) + sum_s mu0'_s n_s with
mu0'_s = RT (mu0_s/RT - ln c0), and over a half-step from a (start amounts) to a + delta,
    dG_i = RT sum_s [delta_s (ln(a_s/V_i) - 1) + (a_s + delta_s) log1p(delta_s/a_s)]
           + sum_s mu0'_s delta_s.
Bookings per node and half-step, by the node's class in the step (from the multipliers):
idle (start selected, nothing booked); driven only, W = dG and H = 0; passive only, H = -dG and
W = 0; mixed, H = sum_passive H_r and W = dG + H, where a passive route that does not reverse
(its three stage net rates and its end-state affinity share one nonzero sign) books its
average-vector-field share H_r = -dxi_r sum_s nu_sr mubar_s (McLachlan, Quispel & Robidoux
1999), and any other passive route books its stage quadrature H_r = h sum_k b_k RT J_r A_r with
b = (1/6, 1/6, 2/3). The standard term gains sum_r dG0'_r dxi_r, dG0'_r = sum_s nu_sr mu0'_s,
and the ledger closes: d(chemical) + d(standard) + H - W = 0.

Readings of Appendix A taken here (each is also in the usage note and the hand-back):
* A node's class comes from the step's multipliers only (m > 0 on a route sited there), never
  from the rates: a driven route with m > 0 whose Hill factor underflows still makes it driven.
* An idle node returns its start amounts untouched (array selection), books zeros and is not
  checked for positivity or the stage condition (it takes no stages).
* delta_s is the computed net change (nu dxi)_s, used in dG's increment form and in mubar; the
  candidate end state is n + delta.
* A refused half-step reports `admitted = False` and `accepted = start`; its booking fields
  describe the refused candidate and are diagnostic only.
* The domain is positive, finite amounts of every declared species at every non-idle node; the
  positivity check covers every species of such a node at Y1, Y2, Y3 and the result.
* The stage condition is inclusive (h max L = 1/2 passes).
* At a mixed node H sums every passive route sited there, including routes with m = 0, which
  contribute exactly 0. A route with m = 0 has J, J+ and J- set to exactly 0 by selection.
* The standard term is booked in route form; dG uses the species form; both are reported, and
  they agree to rounding.
* Molecularity: sum alpha <= 3 for every law, and sum beta <= 3 for the passive law.
* michaelis_menten declares reactants {S: 1} exactly; its catalyst is named separately and may
  not be a reactant or product.
"""

import math
from dataclasses import dataclass, field
from decimal import Decimal, localcontext

import numpy as np

THETA = 0.5  # The stage condition's bound on h max L (§4.2; version 1, one sub-step).
SERIES_SWITCH = 1e-6  # |x| below which (1 + x) log1p(x)/x takes its series (Appendix A).
B_WEIGHTS = (1.0 / 6.0, 1.0 / 6.0, 2.0 / 3.0)  # SSPRK(3,3) weights at stages (0, 1, 1/2).
MAX_ORDER = 3  # Molecularity at most 3 (§2.2).

MASS_ACTION, MICHAELIS_MENTEN, PASSIVE = "mass_action", "michaelis_menten", "passive"
LAW_NAMES = {
    "mass_action": MASS_ACTION,
    "michaelis_menten": MICHAELIS_MENTEN,
    "passive": PASSIVE,
    "ideal_detailed_balance_mass_action@1": PASSIVE,  # The passive law's registered name.
}
HILL_ACTIVATION, HILL_INHIBITION = "hill_activation", "hill_inhibition"
_FACTOR_SIGN = {HILL_ACTIVATION: -1.0, HILL_INHIBITION: 1.0}


class DeclarationError(ValueError):
    """The network declaration lies outside the reference's (and version 1's) domain."""


def rt_pJ_per_fmol(gas_constant_J_per_mol_K, temperature_K):
    """RT in pJ/fmol from R in J/(mol K) and T in K: 1 J/mol = 1e-3 pJ/fmol."""
    return 1e-3 * float(gas_constant_J_per_mol_K) * float(temperature_K)


# ------------------------------------------------------------------------- declaration


@dataclass(frozen=True)
class Species:
    """A neutral species row: its standard potential mu0/RT at c0 and integer moiety counts."""

    name: str
    mu0_RT: float = 0.0
    moieties: dict | None = None  # {moiety: count}; None means the species is its own moiety.


@dataclass(frozen=True)
class Factor:
    """A Hill factor on a driven route: `kind` is hill_activation or hill_inhibition."""

    kind: str
    species: str
    K_mM: float
    n: float


@dataclass(frozen=True)
class Reaction:
    """One declared reaction. Parameters by law (§2.2):

    * mass_action: `rate_constant` k (mM^(1-q) s^-1);
    * michaelis_menten: `K_M_mM`, and either `k_cat_per_s` with `catalyst`, or `V_max_mM_per_s`;
      reactants must be {S: 1};
    * passive (or "ideal_detailed_balance_mass_action@1"): `k_f_per_s` (s^-1 at c0); closed and
      without factors.
    """

    name: str
    law: str
    reactants: dict = field(default_factory=dict)
    products: dict = field(default_factory=dict)
    rate_constant: float | None = None
    k_f_per_s: float | None = None
    k_cat_per_s: float | None = None
    V_max_mM_per_s: float | None = None
    K_M_mM: float | None = None
    catalyst: str | None = None
    factors: tuple = ()


@dataclass(frozen=True)
class Network:
    """A declared network: species and reactions in order (the arrays' axes), and c0 in mM."""

    species: tuple
    reactions: tuple
    c0_mM: float = 1.0


@dataclass(frozen=True)
class Compiled:
    """The network as arrays: species s and reactions r index every [S, ...] and [R, ...] axis."""

    species: tuple
    reactions: tuple
    c0: float
    mu0_RT: np.ndarray  # [S]
    alpha: np.ndarray  # [S, R] reactant coefficients
    beta: np.ndarray  # [S, R] product coefficients
    nu: np.ndarray  # [S, R] beta - alpha
    law: tuple  # [R]
    driven: np.ndarray  # [R] bool
    passive: np.ndarray  # [R] bool
    rate_constant: np.ndarray  # [R] mass action k (nan elsewhere)
    k_f: np.ndarray  # [R] passive k_f (nan elsewhere)
    k_cat: np.ndarray  # [R] (nan where absent)
    V_max: np.ndarray  # [R] (nan where absent)
    K_M: np.ndarray  # [R] (nan where absent)
    substrate: np.ndarray  # [R] species index of S (-1 elsewhere)
    catalyst: np.ndarray  # [R] species index of E (-1 elsewhere)
    g: np.ndarray  # [R] sum_s nu_sr mu0_s/RT
    factors: tuple  # [R] of tuples (sign, species index, K, n)
    moieties: tuple  # [Q] names
    M: np.ndarray  # [Q, S] integer moiety counts
    role: tuple  # [R] "closed", "source" or "sink"


def _coefficients(side, index, reaction):
    out = {}
    for name, value in dict(side).items():
        if name not in index:
            raise DeclarationError(f"{reaction}: unknown species {name!r}")
        if isinstance(value, bool) or not float(value).is_integer() or value < 0:
            raise DeclarationError(f"{reaction}: coefficient of {name!r} must be an integer >= 0")
        if int(value) > 0:
            out[index[name]] = int(value)
    return out


def _positive(value, what, reaction):
    if value is None or not np.isfinite(value) or value <= 0.0:
        raise DeclarationError(f"{reaction}: {what} must be finite and > 0")
    return float(value)


def _non_negative(value, what, reaction):
    if value is None or not np.isfinite(value) or value < 0.0:
        raise DeclarationError(f"{reaction}: {what} must be finite and >= 0")
    return float(value)


def compile_network(network):
    """Validate a `Network` and return its `Compiled` arrays; raises DeclarationError."""
    if isinstance(network, Compiled):
        return network
    species = tuple(network.species)
    reactions = tuple(network.reactions)
    names = [s.name for s in species]
    if len(set(names)) != len(names) or not names:
        raise DeclarationError("species names must be unique and non-empty")
    if len({r.name for r in reactions}) != len(reactions):
        raise DeclarationError("reaction names must be unique")
    c0 = _positive(network.c0_mM, "c0", "network")
    index = {name: s for s, name in enumerate(names)}
    S, R = len(species), len(reactions)
    mu0 = np.array([float(s.mu0_RT) for s in species])
    if not np.isfinite(mu0).all():
        raise DeclarationError("standard potentials must be finite")
    moiety_names = []
    for s in species:
        for q in (s.moieties if s.moieties is not None else {s.name: 1}):
            if q not in moiety_names:
                moiety_names.append(q)
    M = np.zeros((len(moiety_names), S), dtype=np.int64)
    for s, sp in enumerate(species):
        for q, count in (sp.moieties if sp.moieties is not None else {sp.name: 1}).items():
            if isinstance(count, bool) or not float(count).is_integer() or count < 0:
                raise DeclarationError(f"{sp.name}: moiety counts must be integers >= 0")
            M[moiety_names.index(q), s] = int(count)
    alpha = np.zeros((S, R))
    beta = np.zeros((S, R))
    law, role, factors = [], [], []
    nan = np.full(R, np.nan)
    rate_constant, k_f, k_cat, V_max, K_M = (nan.copy() for _ in range(5))
    substrate = np.full(R, -1, dtype=np.int64)
    catalyst = np.full(R, -1, dtype=np.int64)
    for r, rx in enumerate(reactions):
        if rx.law not in LAW_NAMES:
            raise DeclarationError(f"{rx.name}: unknown law {rx.law!r}")
        kind = LAW_NAMES[rx.law]
        reac = _coefficients(rx.reactants, index, rx.name)
        prod = _coefficients(rx.products, index, rx.name)
        for s, v in reac.items():
            alpha[s, r] = v
        for s, v in prod.items():
            beta[s, r] = v
        if sum(reac.values()) > MAX_ORDER or (kind == PASSIVE and sum(prod.values()) > MAX_ORDER):
            raise DeclarationError(f"{rx.name}: molecularity above {MAX_ORDER}")
        nu_r = beta[:, r] - alpha[:, r]
        change = M @ nu_r.astype(np.int64)
        if not change.any():
            role.append("closed")
        elif (nu_r >= 0).all():
            role.append("source")
        elif (nu_r <= 0).all():
            role.append("sink")
        else:
            raise DeclarationError(f"{rx.name}: unbalanced and neither a source nor a sink")
        facs = []
        for fac in rx.factors:
            if fac.kind not in _FACTOR_SIGN:
                raise DeclarationError(f"{rx.name}: unknown factor kind {fac.kind!r}")
            if fac.species not in index:
                raise DeclarationError(f"{rx.name}: unknown factor species {fac.species!r}")
            facs.append(
                (
                    _FACTOR_SIGN[fac.kind],
                    index[fac.species],
                    _positive(fac.K_mM, "a factor's K", rx.name),
                    _positive(fac.n, "a factor's n", rx.name),
                )
            )
        if kind == PASSIVE:
            if role[-1] != "closed":
                raise DeclarationError(f"{rx.name}: a passive reaction must be closed")
            if facs:
                raise DeclarationError(f"{rx.name}: a passive reaction takes no factors")
            if not nu_r.any():
                raise DeclarationError(f"{rx.name}: a passive reaction must change something")
            k_f[r] = _positive(rx.k_f_per_s, "k_f", rx.name)
        elif kind == MASS_ACTION:
            rate_constant[r] = _non_negative(rx.rate_constant, "the rate constant", rx.name)
        else:
            if len(reac) != 1 or next(iter(reac.values())) != 1:
                raise DeclarationError(f"{rx.name}: michaelis_menten needs reactants {{S: 1}}")
            substrate[r] = next(iter(reac))
            K_M[r] = _positive(rx.K_M_mM, "K_M", rx.name)
            if rx.catalyst is not None:
                if rx.catalyst not in index:
                    raise DeclarationError(f"{rx.name}: unknown catalyst {rx.catalyst!r}")
                e = index[rx.catalyst]
                if alpha[e, r] or beta[e, r]:
                    raise DeclarationError(f"{rx.name}: the catalyst is read, not written")
                if rx.V_max_mM_per_s is not None:
                    raise DeclarationError(f"{rx.name}: give k_cat with a catalyst, not V_max")
                catalyst[r] = e
                k_cat[r] = _non_negative(rx.k_cat_per_s, "k_cat", rx.name)
            else:
                if rx.k_cat_per_s is not None:
                    raise DeclarationError(f"{rx.name}: k_cat needs a catalyst")
                V_max[r] = _non_negative(rx.V_max_mM_per_s, "V_max", rx.name)
        law.append(kind)
        factors.append(tuple(facs))
    nu = beta - alpha
    passive = np.array([k == PASSIVE for k in law], dtype=bool)
    return Compiled(
        species=tuple(names),
        reactions=tuple(r.name for r in reactions),
        c0=c0,
        mu0_RT=mu0,
        alpha=alpha,
        beta=beta,
        nu=nu,
        law=tuple(law),
        driven=~passive,
        passive=passive,
        rate_constant=rate_constant,
        k_f=k_f,
        k_cat=k_cat,
        V_max=V_max,
        K_M=K_M,
        substrate=substrate,
        catalyst=catalyst,
        g=nu.T @ mu0,
        factors=tuple(factors),
        moieties=tuple(moiety_names),
        M=M,
        role=tuple(role),
    )


# ---------------------------------------------------------------------- array helpers


def _state(cn, amounts, volumes):
    n = np.array(amounts, dtype=float)
    if n.ndim == 1:
        n = n[:, None]
    if n.ndim != 2 or n.shape[0] != len(cn.species):
        raise ValueError(f"amounts must be [species, node] with {len(cn.species)} species rows")
    V = np.broadcast_to(np.asarray(volumes, dtype=float), (n.shape[1],)).copy()
    if not (np.isfinite(V).all() and (V > 0).all()):
        raise ValueError("volumes must be finite and > 0")
    return n, V


def _multipliers(cn, multipliers, sites, N):
    R = len(cn.reactions)
    m = np.ones((R, N)) if multipliers is None else np.array(multipliers, dtype=float)
    if m.ndim == 1:
        m = np.broadcast_to(m[:, None], (R, N)).copy()
    if m.shape != (R, N):
        raise ValueError(f"multipliers must be [reaction] or [reaction, node] = {(R, N)}")
    if not (np.isfinite(m).all() and (m >= 0).all()):
        raise ValueError("multipliers must be finite and >= 0")
    if sites is not None:
        mask = np.broadcast_to(np.asarray(sites, dtype=bool), (R, N))
        m = np.where(mask, m, 0.0)
    return m


@dataclass(frozen=True)
class Rates:
    """Route rates at one state ([reaction, node] axes; L is [species, node])."""

    net: np.ndarray  # J_r (fmol/s); the passive net rate in Appendix A's stable form
    forward: np.ndarray  # J+_r on passive routes, J_r on driven routes (fmol/s)
    reverse: np.ndarray  # J-_r on passive routes, 0 on driven routes (fmol/s)
    affinity: np.ndarray  # A_r = f - r (dimensionless, in units of RT) on passive routes, else 0
    factor: np.ndarray  # F_r, the product of the route's Hill factors (1 if none)
    consumption_rate: np.ndarray  # L_s (1/s) per species and node


def _evaluate(cn, Y, V, m):
    """Rates at state Y [S, N] (no positivity assumed: invalid entries come out non-finite)."""
    S, N = Y.shape
    R = len(cn.reactions)
    on = m > 0.0
    with np.errstate(divide="ignore", invalid="ignore", over="ignore", under="ignore"):
        c = Y / V
        a = Y / (V * cn.c0)
        ln_c = np.log(c)
        ln_a = np.log(a)
        F = np.ones((R, N))
        for r, facs in enumerate(cn.factors):
            for sign, s, K, n_hill in facs:
                F[r] = F[r] * np.exp(-np.logaddexp(0.0, sign * n_hill * (ln_c[s] - math.log(K))))
        net = np.zeros((R, N))
        fwd = np.zeros((R, N))
        rev = np.zeros((R, N))
        aff = np.zeros((R, N))
        for r, kind in enumerate(cn.law):
            if kind == MASS_ACTION:
                prod = np.ones(N)
                for s in np.flatnonzero(cn.alpha[:, r]):
                    prod = prod * c[s] ** cn.alpha[s, r]
                J = m[r] * F[r] * cn.rate_constant[r] * V * prod
                net[r] = fwd[r] = J
            elif kind == MICHAELIS_MENTEN:
                s = cn.substrate[r]
                if cn.catalyst[r] >= 0:
                    cE = c[cn.catalyst[r]]
                    J = m[r] * F[r] * V * cn.k_cat[r] * cE * c[s] / (cn.K_M[r] + c[s])
                else:
                    J = m[r] * F[r] * V * cn.V_max[r] * c[s] / (cn.K_M[r] + c[s])
                net[r] = fwd[r] = J
            else:
                f = np.zeros(N)
                for s in np.flatnonzero(cn.alpha[:, r]):
                    f = f + cn.alpha[s, r] * ln_a[s]
                rr = np.zeros(N)
                for s in np.flatnonzero(cn.beta[:, r]):
                    rr = rr + cn.beta[s, r] * ln_a[s]
                rr = rr + cn.g[r]
                A = f - rr
                pref = m[r] * V * cn.c0 * cn.k_f[r]
                net[r] = pref * np.exp(np.maximum(f, rr)) * (-np.expm1(-np.abs(A))) * np.sign(A)
                fwd[r] = pref * np.exp(f)
                rev[r] = pref * np.exp(rr)
                aff[r] = A
        net = np.where(on, net, 0.0)
        fwd = np.where(on, fwd, 0.0)
        rev = np.where(on, rev, 0.0)
        consumed = np.maximum(-cn.nu, 0.0) @ fwd + np.maximum(cn.nu, 0.0) @ rev
        L = consumed / Y
    return Rates(net, fwd, rev, aff, F, L)


def rates(network, amounts_fmol, volumes_pL, multipliers=None, sites=None):
    """Route rates, unidirectional fluxes, affinities, factors and L at one state.

    amounts_fmol [S, N] (or [S] for one node), volumes_pL [N] (or scalar), multipliers [R] or
    [R, N] (default 1), sites [R, N] bool (default every route at every node).
    """
    cn = compile_network(network)
    n, V = _state(cn, amounts_fmol, volumes_pL)
    return _evaluate(cn, n, V, _multipliers(cn, multipliers, sites, n.shape[1]))


# ------------------------------------------------------------------------ free energy


def standard_potentials_pJ(network, RT_pJ_per_fmol):
    """mu0'_s = RT (mu0_s/RT - ln c0) in pJ/fmol, against @3's 1 mM reference [S]."""
    cn = compile_network(network)
    return RT_pJ_per_fmol * (cn.mu0_RT - math.log(cn.c0))


def free_energy_pJ(network, amounts_fmol, volumes_pL, RT_pJ_per_fmol):
    """G_i = RT sum_s n_s (ln(n_s/V_i) - 1) + sum_s mu0'_s n_s per node [N] (pJ)."""
    cn = compile_network(network)
    n, V = _state(cn, amounts_fmol, volumes_pL)
    mu0p = standard_potentials_pJ(cn, RT_pJ_per_fmol)
    return RT_pJ_per_fmol * np.sum(n * (np.log(n / V) - 1.0), axis=0) + mu0p @ n


def _dG_parts(cn, n, delta, V, RT):
    """The increment form's parts per node: chemical, standard (species form), sum |terms|."""
    mu0p = RT * (cn.mu0_RT - math.log(cn.c0))
    with np.errstate(divide="ignore", invalid="ignore"):
        t1 = delta * (np.log(n / V) - 1.0)
        t2 = (n + delta) * np.log1p(delta / n)
    t1 = np.where(delta == 0.0, 0.0, t1)
    t2 = np.where(delta == 0.0, 0.0, t2)
    std_terms = mu0p[:, None] * delta
    chemical = RT * np.sum(t1 + t2, axis=0)
    standard = np.sum(std_terms, axis=0)
    terms = RT * np.sum(np.abs(t1) + np.abs(t2), axis=0) + np.sum(np.abs(std_terms), axis=0)
    return chemical, standard, terms


def free_energy_change(network, start_fmol, delta_fmol, volumes_pL, RT_pJ_per_fmol):
    """dG_i from start amounts a and change delta in Appendix A's increment form.

    Returns a dict of [N] arrays (pJ): "delta_G", "chemical" (the RT part), "standard"
    (sum_s mu0'_s delta_s) and "terms" (the sum of the absolute values of the terms).
    """
    cn = compile_network(network)
    n, V = _state(cn, start_fmol, volumes_pL)
    delta = np.array(delta_fmol, dtype=float).reshape(n.shape)
    chemical, standard, terms = _dG_parts(cn, n, delta, V, RT_pJ_per_fmol)
    return {"delta_G": chemical + standard, "chemical": chemical, "standard": standard,
            "terms": terms}


def _mu_bar(cn, n, delta, V, RT):
    """The divided-difference potentials [g_s(n + delta) - g_s(n)]/delta_s (Appendix A)."""
    mu0p = RT * (cn.mu0_RT - math.log(cn.c0))
    with np.errstate(divide="ignore", invalid="ignore"):
        x = delta / n
        ratio_log = (1.0 + x) * np.log1p(x) / x
    ratio = np.where(np.abs(x) < SERIES_SWITCH, 1.0 + x / 2.0 - x * x / 6.0, ratio_log)
    return RT * (np.log(n / V) + ratio - 1.0) + mu0p[:, None]


def divided_difference_potentials(network, start_fmol, delta_fmol, volumes_pL, RT_pJ_per_fmol):
    """mubar_s per species and node [S, N] (pJ/fmol), in Appendix A's stable form."""
    cn = compile_network(network)
    n, V = _state(cn, start_fmol, volumes_pL)
    delta = np.array(delta_fmol, dtype=float).reshape(n.shape)
    return _mu_bar(cn, n, delta, V, RT_pJ_per_fmol)


# -------------------------------------------------------------------------- half-step


@dataclass(frozen=True)
class HalfStep:
    """One reference half-step. Axes: S species, R reactions, N nodes; stages k = 0, 1, 2."""

    h: float
    start: np.ndarray  # [S, N] n = Y1
    end: np.ndarray  # [S, N] candidate n' = n + delta (the start, bitwise, at idle nodes)
    accepted: np.ndarray  # [S, N] end if admitted, else start
    delta: np.ndarray  # [S, N] nu dxi
    extents: np.ndarray  # [R, N] dxi (fmol)
    stages: np.ndarray  # [3, S, N] Y1, Y2, Y3
    stage_net: np.ndarray  # [3, R, N] J_r(Y_k)
    stage_forward: np.ndarray  # [3, R, N] J+ (passive) or J (driven)
    stage_reverse: np.ndarray  # [3, R, N] J- (passive) or 0
    stage_affinity: np.ndarray  # [3, R, N] A_r(Y_k) (passive) or 0
    end_net: np.ndarray  # [R, N] J_r(n'), the rate observation at the end state
    end_affinity: np.ndarray  # [R, N] A_r(n') (passive) or 0
    hL: np.ndarray  # [3, N] h max_s L_s(Y_k) (0 at idle nodes)
    hL_max: float  # the largest h L over stages and active nodes
    hL_argmax: tuple  # (stage, node) of hL_max
    L_max: float  # hL_max / h (1/s); dt <= 1/L_max is the corresponding step
    stage_condition_ok: bool
    positive_ok: bool
    finite_ok: bool
    admitted: bool
    node_class: np.ndarray  # [N] "idle", "driven", "passive" or "mixed"
    non_reversing: np.ndarray  # [R, N] the branch test on passive routes at non-idle nodes
    branch: np.ndarray  # [R, N] "share", "quadrature", "node" (single class), "idle" or ""
    sign_margin: np.ndarray  # [R, N] min |A| over the three stages and the end (passive)
    heat_share: np.ndarray  # [R, N] -dxi_r sum_s nu_sr mubar_s (passive, non-idle nodes)
    heat_quadrature: np.ndarray  # [R, N] h sum_k b_k RT J_r A_r (passive, non-idle nodes)
    route_heat: np.ndarray  # [R, N] the booked H_r at mixed nodes, 0 elsewhere
    mu_bar: np.ndarray  # [S, N] divided-difference potentials (pJ/fmol)
    heat: np.ndarray  # [N] H (pJ)
    work: np.ndarray  # [N] W (pJ)
    delta_G: np.ndarray  # [N] chemical + standard_species (pJ)
    chemical: np.ndarray  # [N] the RT part of dG (pJ)
    standard: np.ndarray  # [N] sum_r dG0'_r dxi_r (pJ), the booked standard term
    standard_species: np.ndarray  # [N] sum_s mu0'_s delta_s (pJ)
    delta_G_terms: np.ndarray  # [N] the sum of |terms| of dG (pJ)
    ledger_residual: np.ndarray  # [N] chemical + standard + H - W (pJ)


def half_step(network, amounts_fmol, volumes_pL, h_s, RT_pJ_per_fmol, multipliers=None,
              sites=None, theta=THETA):
    """One SSPRK(3,3) half-step of length h at every node, with its checks and bookings.

    amounts_fmol [S, N] (or [S]); volumes_pL [N] (or scalar); h_s the half-step (s), dt/2 in
    the engine; RT in pJ/fmol; multipliers [R] or [R, N] (>= 0, default 1); sites [R, N] bool.
    Returns a `HalfStep`.
    """
    cn = compile_network(network)
    n, V = _state(cn, amounts_fmol, volumes_pL)
    S, N = n.shape
    R = len(cn.reactions)
    h = float(h_s)
    if not (np.isfinite(h) and h > 0):
        raise ValueError("h must be finite and > 0")
    RT = float(RT_pJ_per_fmol)
    m = _multipliers(cn, multipliers, sites, N)
    on = m > 0.0
    driven_active = (on & cn.driven[:, None]).any(axis=0)
    passive_active = (on & cn.passive[:, None]).any(axis=0)
    idle = ~(driven_active | passive_active)
    active = ~idle
    node_class = np.where(
        idle, "idle", np.where(driven_active & passive_active, "mixed",
                               np.where(driven_active, "driven", "passive"))
    )
    nu = cn.nu
    with np.errstate(all="ignore"):
        r1 = _evaluate(cn, n, V, m)
        Y2 = n + h * (nu @ r1.net)
        r2 = _evaluate(cn, Y2, V, m)
        Y3 = n + h * (nu @ (r1.net + r2.net)) / 4.0
        r3 = _evaluate(cn, Y3, V, m)
        dxi = h * (r1.net + r2.net + 4.0 * r3.net) / 6.0
        dxi = np.where(idle[None, :], 0.0, dxi)
        delta = np.where(idle[None, :], 0.0, nu @ dxi)
        end = np.where(idle[None, :], n, n + delta)
        r_end = _evaluate(cn, end, V, m)
        stages = np.stack([n, Y2, Y3])
        hL = np.stack([h * np.max(r.consumption_rate, axis=0) for r in (r1, r2, r3)])
        hL = np.where(idle[None, :], 0.0, hL)
    states = np.concatenate([stages, end[None]], axis=0)[:, :, active]
    positive_ok = bool((states > 0).all())
    finite_ok = bool(
        np.isfinite(states).all()
        and all(np.isfinite(r.net[:, active]).all() for r in (r1, r2, r3))
        and np.isfinite(hL).all()
    )
    stage_condition_ok = bool(np.isfinite(hL).all() and (hL <= theta).all())
    admitted = positive_ok and finite_ok and stage_condition_ok
    finite_hL = np.where(np.isfinite(hL), hL, np.inf)
    k_max, i_max = np.unravel_index(int(np.argmax(finite_hL)), hL.shape)
    hL_max = float(finite_hL[k_max, i_max])

    # Energies (Appendix A): the increment form from the start, and the per-route hybrid.
    with np.errstate(all="ignore"):
        chemical, standard_species, terms = _dG_parts(cn, n, delta, V, RT)
        mu0p = RT * (cn.mu0_RT - math.log(cn.c0))
        dG0p = nu.T @ mu0p  # [R]
        standard = np.sum(dG0p[:, None] * dxi, axis=0)
        delta_G = chemical + standard_species
        mu_bar = _mu_bar(cn, n, delta, V, RT)
        share = -dxi * (nu.T @ mu_bar)
        quad = RT * h * sum(
            b * r.net * r.affinity for b, r in zip(B_WEIGHTS, (r1, r2, r3), strict=True)
        )
        signs = np.stack([np.sign(r1.net), np.sign(r2.net), np.sign(r3.net),
                          np.sign(r_end.affinity)])
        non_reversing = (signs[0] != 0) & (signs == signs[0]).all(axis=0)
        margin = np.min(np.abs(np.stack([r1.affinity, r2.affinity, r3.affinity,
                                         r_end.affinity])), axis=0)
    passive_route = cn.passive[:, None] & active[None, :]
    non_reversing = non_reversing & passive_route
    share = np.where(passive_route, share, 0.0)
    quad = np.where(passive_route, quad, 0.0)
    margin = np.where(passive_route, margin, np.nan)
    mixed = node_class == "mixed"
    route_heat = np.where(passive_route & mixed[None, :], np.where(non_reversing, share, quad), 0.0)
    heat_mixed = np.sum(route_heat, axis=0)
    heat = np.where(mixed, heat_mixed, np.where(node_class == "passive", -delta_G, 0.0))
    work = np.where(mixed, delta_G + heat, np.where(node_class == "driven", delta_G, 0.0))
    heat = np.where(idle, 0.0, heat)
    work = np.where(idle, 0.0, work)
    chemical = np.where(idle, 0.0, chemical)
    standard = np.where(idle, 0.0, standard)
    standard_species = np.where(idle, 0.0, standard_species)
    delta_G = np.where(idle, 0.0, delta_G)
    terms = np.where(idle, 0.0, terms)
    branch = np.full((R, N), "", dtype="<U10")
    branch = np.where(cn.passive[:, None] & idle[None, :], "idle", branch)
    branch = np.where(passive_route & ~mixed[None, :], "node", branch)
    branch = np.where(passive_route & mixed[None, :],
                      np.where(non_reversing, "share", "quadrature"), branch)
    return HalfStep(
        h=h,
        start=n,
        end=end,
        accepted=end if admitted else n,
        delta=delta,
        extents=dxi,
        stages=stages,
        stage_net=np.stack([r1.net, r2.net, r3.net]),
        stage_forward=np.stack([r1.forward, r2.forward, r3.forward]),
        stage_reverse=np.stack([r1.reverse, r2.reverse, r3.reverse]),
        stage_affinity=np.stack([r1.affinity, r2.affinity, r3.affinity]),
        end_net=r_end.net,
        end_affinity=r_end.affinity,
        hL=hL,
        hL_max=hL_max,
        hL_argmax=(int(k_max), int(i_max)),
        L_max=hL_max / h,
        stage_condition_ok=stage_condition_ok,
        positive_ok=positive_ok,
        finite_ok=finite_ok,
        admitted=admitted,
        node_class=node_class,
        non_reversing=non_reversing,
        branch=branch,
        sign_margin=margin,
        heat_share=share,
        heat_quadrature=quad,
        route_heat=route_heat,
        mu_bar=mu_bar,
        heat=heat,
        work=work,
        delta_G=delta_G,
        chemical=chemical,
        standard=standard,
        standard_species=standard_species,
        delta_G_terms=terms,
        ledger_residual=chemical + standard + heat - work,
    )


@dataclass(frozen=True)
class HalfStepRun:
    """Consecutive half-steps from one start (no transport between them)."""

    h: float
    taken: int  # admitted half-steps
    refused_at: int | None  # index of the first refused half-step, or None
    refusal: HalfStep | None  # that refused half-step
    times: np.ndarray  # [taken + 1] (s)
    amounts: np.ndarray  # [taken + 1, S, N]
    extents: np.ndarray  # [taken + 1, R, N] cumulative
    heat: np.ndarray  # [taken + 1, N] cumulative H
    work: np.ndarray  # [taken + 1, N] cumulative W
    standard: np.ndarray  # [taken + 1, N] cumulative standard term
    chemical: np.ndarray  # [taken + 1, N] cumulative chemical change
    step_heat: np.ndarray  # [taken, N] each half-step's H
    branches: list  # per admitted half-step, the [R, N] branch array


def run_half_steps(network, amounts_fmol, volumes_pL, h_s, count, RT_pJ_per_fmol,
                   multipliers=None, sites=None, theta=THETA):
    """`count` consecutive half-steps of length h, stopping at the first refusal.

    multipliers: None, [R], [R, N], or a callable k -> [R] or [R, N] for half-step k (from 0).
    """
    cn = compile_network(network)
    n, V = _state(cn, amounts_fmol, volumes_pL)
    S, N = n.shape
    R = len(cn.reactions)
    amounts, extents = [n], [np.zeros((R, N))]
    heat, work, standard, chemical = ([np.zeros(N)] for _ in range(4))
    step_heat, branches = [], []
    refused_at, refusal = None, None
    for k in range(int(count)):
        mk = multipliers(k) if callable(multipliers) else multipliers
        step = half_step(cn, amounts[-1], V, h_s, RT_pJ_per_fmol, mk, sites, theta)
        if not step.admitted:
            refused_at, refusal = k, step
            break
        amounts.append(step.end)
        extents.append(extents[-1] + step.extents)
        heat.append(heat[-1] + step.heat)
        work.append(work[-1] + step.work)
        standard.append(standard[-1] + step.standard)
        chemical.append(chemical[-1] + step.chemical)
        step_heat.append(step.heat)
        branches.append(step.branch)
    taken = len(amounts) - 1
    return HalfStepRun(
        h=float(h_s),
        taken=taken,
        refused_at=refused_at,
        refusal=refusal,
        times=float(h_s) * np.arange(taken + 1),
        amounts=np.array(amounts),
        extents=np.array(extents),
        heat=np.array(heat),
        work=np.array(work),
        standard=np.array(standard),
        chemical=np.array(chemical),
        step_heat=np.array(step_heat).reshape(taken, N),
        branches=branches,
    )


# --------------------------------------------------------------------------- moieties


def moiety_totals(network, amounts_fmol):
    """Moiety totals sum_s M_qs n_s per moiety and node [Q, N] (fmol)."""
    cn = compile_network(network)
    n = np.array(amounts_fmol, dtype=float)
    n = n[:, None] if n.ndim == 1 else n
    return cn.M.astype(float) @ n


def moiety_change_from_extents(network, extents_fmol):
    """sum over open routes of (M nu_r) dxi_r per moiety and node [Q, N] (§3.1)."""
    cn = compile_network(network)
    dxi = np.array(extents_fmol, dtype=float)
    dxi = dxi[:, None] if dxi.ndim == 1 else dxi
    open_routes = np.array([role != "closed" for role in cn.role])
    Mnu = (cn.M @ cn.nu.astype(np.int64)).astype(float)  # [Q, R], integer-valued
    return (Mnu * open_routes[None, :]) @ dxi


# ------------------------------------------------------------ arbitrary precision (Decimal)


@dataclass(frozen=True)
class ExactEnergy:
    """dG_i and its parts at `digits` significant digits (Decimal lists per node, and floats)."""

    digits: int
    delta_G: list  # [N] Decimal, chemical + standard_species
    chemical: list  # [N] Decimal
    standard_species: list  # [N] Decimal, sum_s mu0'_s delta_s
    standard_routes: list | None  # [N] Decimal, sum_r dG0'_r dxi_r (when extents are given)
    terms: list  # [N] Decimal, the sum of |terms| of dG
    delta_G_float: np.ndarray  # [N]
    chemical_float: np.ndarray  # [N]
    standard_species_float: np.ndarray  # [N]
    standard_routes_float: np.ndarray | None  # [N]
    terms_float: np.ndarray  # [N]


def _dec(x):
    """The exact decimal value of a binary64 number."""
    return Decimal(float(x))


def _ln1p(x, prec):
    """ln(1 + x) to `prec` significant digits, for Decimal x > -1."""
    with localcontext() as ctx:
        ctx.prec = prec + max(0, -x.adjusted()) + 5
        value = (1 + x).ln()
    with localcontext() as ctx:
        ctx.prec = prec
        return +value


def exact_energy_change(network, start_fmol, volumes_pL, RT_pJ_per_fmol, *, delta_fmol=None,
                        end_fmol=None, extents_fmol=None, digits=50):
    """dG_i, the chemical change and the standard term at `digits` digits (Python's decimal).

    The float inputs are taken exactly (Decimal(float)). Give exactly one of
    * delta_fmol [S, N]: the change delta as the engine holds it (preferred; the increment);
    * end_fmol [S, N]: delta = end - start, exactly;
    * extents_fmol [R, N]: delta = nu dxi, exactly; then standard_routes is also returned.
    extents_fmol may also be given with delta_fmol or end_fmol, to obtain standard_routes.
    Returns an `ExactEnergy`.
    """
    cn = compile_network(network)
    n = np.array(start_fmol, dtype=float)
    n = n[:, None] if n.ndim == 1 else n
    S, N = n.shape
    V = np.broadcast_to(np.asarray(volumes_pL, dtype=float), (N,))
    given = [x is not None for x in (delta_fmol, end_fmol)]
    if sum(given) > 1 or (sum(given) == 0 and extents_fmol is None):
        raise ValueError("give exactly one of delta_fmol, end_fmol, or extents_fmol alone")
    R = len(cn.reactions)
    dxi = None
    if extents_fmol is not None:
        dxi = np.array(extents_fmol, dtype=float).reshape(R, N)
    prec = int(digits) + 40
    with localcontext() as ctx:
        ctx.prec = prec
        RT = _dec(RT_pJ_per_fmol)
        ln_c0 = _dec(cn.c0).ln()
        mu0p = [RT * (_dec(mu) - ln_c0) for mu in cn.mu0_RT]
        nu = [[int(cn.nu[s, r]) for r in range(R)] for s in range(S)]
        out = {key: [] for key in ("delta_G", "chemical", "standard_species", "routes", "terms")}
        for i in range(N):
            Vi = _dec(V[i])
            if delta_fmol is not None:
                d = np.array(delta_fmol, dtype=float).reshape(S, N)
                delta = [_dec(d[s, i]) for s in range(S)]
            elif end_fmol is not None:
                e = np.array(end_fmol, dtype=float).reshape(S, N)
                delta = [_dec(e[s, i]) - _dec(n[s, i]) for s in range(S)]
            else:
                delta = [sum((nu[s][r] * _dec(dxi[r, i]) for r in range(R)), Decimal(0))
                         for s in range(S)]
            chem, std, terms = Decimal(0), Decimal(0), Decimal(0)
            for s in range(S):
                d_s = delta[s]
                if d_s == 0:
                    continue
                a_s = _dec(n[s, i])
                if a_s <= 0 or a_s + d_s <= 0:
                    raise ValueError("start and end amounts must be > 0")
                t1 = d_s * ((a_s / Vi).ln() - 1)
                t2 = (a_s + d_s) * _ln1p(d_s / a_s, prec)
                chem += t1 + t2
                std += mu0p[s] * d_s
                terms += RT * (abs(t1) + abs(t2)) + abs(mu0p[s] * d_s)
            chem = RT * chem
            out["chemical"].append(chem)
            out["standard_species"].append(std)
            out["delta_G"].append(chem + std)
            out["terms"].append(terms)
            if dxi is not None:
                dG0p = [sum((nu[s][r] * mu0p[s] for s in range(S)), Decimal(0)) for r in range(R)]
                out["routes"].append(sum((dG0p[r] * _dec(dxi[r, i]) for r in range(R)),
                                         Decimal(0)))
    with localcontext() as ctx:
        ctx.prec = int(digits)
        rounded = {key: [+v for v in values] for key, values in out.items()}

    def floats(values):
        return np.array([float(v) for v in values])

    routes = rounded["routes"] if dxi is not None else None
    return ExactEnergy(
        digits=int(digits),
        delta_G=rounded["delta_G"],
        chemical=rounded["chemical"],
        standard_species=rounded["standard_species"],
        standard_routes=routes,
        terms=rounded["terms"],
        delta_G_float=floats(rounded["delta_G"]),
        chemical_float=floats(rounded["chemical"]),
        standard_species_float=floats(rounded["standard_species"]),
        standard_routes_float=floats(routes) if routes is not None else None,
        terms_float=floats(rounded["terms"]),
    )


def exact_free_energy(network, amounts_fmol, volumes_pL, RT_pJ_per_fmol, digits=50):
    """G_i per node at `digits` digits (Decimal list), the float inputs taken exactly."""
    cn = compile_network(network)
    n = np.array(amounts_fmol, dtype=float)
    n = n[:, None] if n.ndim == 1 else n
    S, N = n.shape
    V = np.broadcast_to(np.asarray(volumes_pL, dtype=float), (N,))
    out = []
    with localcontext() as ctx:
        ctx.prec = int(digits) + 40
        RT = _dec(RT_pJ_per_fmol)
        ln_c0 = _dec(cn.c0).ln()
        for i in range(N):
            Vi, total = _dec(V[i]), Decimal(0)
            for s in range(S):
                a_s = _dec(n[s, i])
                total += RT * a_s * ((a_s / Vi).ln() - 1) + RT * (_dec(cn.mu0_RT[s]) - ln_c0) * a_s
            out.append(total)
    with localcontext() as ctx:
        ctx.prec = int(digits)
        return [+v for v in out]
