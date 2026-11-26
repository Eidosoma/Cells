"""Cycle forms: a membrane cycle law's general form (docs/CORE_SEAMS_DESIGN.md §3, §16 and §19).

Its home is the lead's ruling with the F owner (18 November 2026): a law-side module of the kinds
owner's, binding no law of its own (so the model table's scans pass it by) and importing nothing
from Cells beyond laws/ (so the surface's guard admits it). The law template's `cycle` field
(registry/laws.py) holds a CycleForm; the template checks it with the form's own errors(), and the
declarations manifest writes it under `fields`, with its changes() as the law's `changes`.

**What a cycle form is.** The data a cycle law gives the cycle kind (cells.kind.transporter@1's
population axis), so the kind can run any declared cycle with one generic program:
- its **roles**, each with the valence it requires of the species a population binds (or None);
- its **rows**, (role, end) with the end N or P of the population's host, in the form's order;
- its **modes**, each a stoichiometric cycle: one count per row, the row's change per forward
  cycle, an integer or a parameter's name (a leading "-" negates it);
- its **parameters**, each with its unit and its declared range;
- one **kinetic form**:
  - `factored`: per mode, a product of Hill saturations S = prod_j [1 + (K_j/c_j)^h_j]^-1, each
    factor naming its row and its K and h (a constant or a parameter);
  - `diagram`: a mass-action kinetic diagram whose every edge rate is
    alpha = k0 prod a^order exp(zeta psi), a = c/c°, psi = F (phi_N - phi_P)/RT; its modes are
    every one of its Hill cycles, each with its edges' directions. A rate's k0 and zeta are each a
    number or a parameter's name (a positive parameter in 1/s; a parameter in 1, which a leading
    "-" negates), so a law may leave its rates to each population's declaration;
  - `net_flow`: per mode, terms J = k a sum_t w_t (1 - exp(x_t + eps_t psi)), x_t the free energy of
    the term's own stoichiometry (the fallback of §3.2; it exposes no one-way flux, D202). A weight
    is signed and nonzero, so a mode may be booked as a signed combination of cycle fluxes, as a
    cycle basis gives it (J_B - J_C for C = A - B; each term is dissipative alone);
  - `monomial` (K6, the kinds owner's design note as ruled, 20 November 2026): per mode, in log
    space,
        log S = log k + sum_r o_r ln a_r + zeta psi
                - sum_f s_f log(1 + sum_g K_fg prod_r a_r^q_fgr e^(eta_fg psi))
                - log sum_{i<n} e^(i x / n),
    with a_r = c_r/c° the activity at a reference r and n the mode's affinity share (1: none). A
    reference names a role's species at an end in a form: "free", a species-registry form ID, or
    "total"; read roles are roles the kinetics read and never move. k is a number or a cited
    constant (CitedConstant: a standard free energy at pH 7, built at parse at the world's
    temperature); an exponent is a number or an Affine of a parameter (never a count). The kind's
    domain for it is one-sided, x <= 80 (complex IV's affinity falls far below -80);
- its **pH bands** (a row's pH within a declared band, the proton law's fuel band, §5.2) and its
  temperature domain, if it has one.

No form carries a standard free energy: the kind computes every mode's from the species registry
(B3). A form holds data only, so the declarations manifest writes it whole.

**What the kind computes from it** (Hill, 1989; King and Altman, 1956; cited as the design note
cites them, unread):
- for a diagram, the steady state of the carrier's master equation by the directional diagrams:
  p_i = D_i/Sigma with D_i the sum, over spanning trees, of the products of the rates directed to
  state i, and Sigma = sum_i D_i;
- each Hill cycle kappa's one-way flux per carrier, j+_kappa = Pi+_kappa Sigma_kappa / Sigma, with
  Pi+ the product of its forward rates and Sigma_kappa the sum of the directional diagrams of the
  diagram with kappa contracted to one node, directed to it (1 for a cycle through every state);
- S_kappa = j+_kappa / omega, with omega the diagram's declared rate scale and the population's
  capacity k = N_carriers omega, so J+ = k a S and J- = J+ exp(x) (the contract, §16);
- every slope exactly: each directional-diagram term is a monomial in the activities and exp(psi)
  with static exponents, so d log S / d ln c and d log S / d psi are softmax-weighted averages of
  those exponents.

**Checks at registration (errors()).** A diagram's declared cycles are exactly its simple cycles,
each once and with a consistent direction (§16: a declared basis is admitted only where it is the
full set; edge-disjoint cycles span the cycle space only in a cactus diagram, where they are all of
its simple cycles). Each cycle's counts equal minus the signed sum of its edges' orders, row by
row: Wegscheider's structural part, decided exactly in integers. A named rate names a parameter
of the right kind, and a cycle that converts a species (a role's net change over both ends
nonzero) has a number for every k0 on its edges, since seam E's check reads its free-energy band
from the law's own constants (the lead's ruling E3, 19 November 2026); a named zeta is admitted
on any cycle.

**Named rates (D228 item 1, version 2; the lead's ruling (a)+(a1)).** `resolved(form, values)` is
the form with each named rate replaced by one population's declared value, and the form itself
where it names none, so a numeric form and every world that runs one are unchanged. Every numeric
consumer (diagram_tables, wegscheider, implied_free_energy, free_energy_band) refuses a rate it
reads that names a parameter, so an unresolved form never runs; the kind resolves each
population's form at parse, where Wegscheider's condition is decided for its declared values
exactly as for a law's constants. A diagram's topology is cached on its structure, not its rates,
so the populations of one law share it.
"""

import itertools
import math
from decimal import Decimal, localcontext
from fractions import Fraction
from functools import lru_cache
from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

ENDS = ("N", "P")
KINETICS = ("factored", "diagram", "net_flow", "monomial")
MAX_SHARE = 8  # A monomial mode's affinity share n: S over sum_{i<n} e^(i x / n).
FORMS = ("free", "total")  # A reference's forms beside a registry form's ID.
MAX_EDGES = 16  # A diagram's edges; its simple cycles are enumerated over every edge subset.
MAX_STATES = 10
EPS = np.finfo(float).eps  # 2^-52
UNIT_ROUNDOFF = EPS / 2  # u = 2^-53
WEGSCHEIDER_BAND = 32  # The constant's band, in eps of its terms (design statement 1, §5.1).
DIGITS = 50  # Wegscheider's constant is evaluated to this many digits.


class Parameter(NamedTuple):
    """A population parameter of a form: its name, unit and declared range (inclusive bounds; a
    positive parameter is strictly above zero; an integer one is a whole number)."""

    name: str
    unit: str
    low: float | None = None
    high: float | None = None
    integer: bool = False
    positive: bool = False


class Saturation(NamedTuple):
    """One factor [1 + (K/c)^h]^-1 of a factored mode's S: its row (role, end), K in mM and the
    Hill number h, each a constant or a parameter's name."""

    row: tuple
    k_mM: object
    hill: object


class PhBand(NamedTuple):
    """A row whose free pH, -log10(c / 1000 mM), stays within width of center (both parameters'
    names, in pH units): the transformed potentials' band of the proton law's fuel node (§5.2)."""

    row: tuple
    center: str
    width: str


class Rate(NamedTuple):
    """One direction of a diagram edge: alpha = k0 prod a^order exp(zeta psi), with the orders
    ((role, end, order), ...), each order a positive integer, and a = c/c° at the row's end. k0
    is a positive number or a positive parameter's name (1/s); zeta a finite number or a
    parameter's name (1), a leading "-" negating it (resolved)."""

    k0_per_s: float | str
    orders: tuple = ()
    zeta: float | str = 0.0


class Edge(NamedTuple):
    """A diagram edge between two states (indices): its forward rate (source to target) and its
    backward rate (target to source)."""

    id: str
    source: int
    target: int
    forward: Rate
    backward: Rate


class Diagram(NamedTuple):
    """A mass-action kinetic diagram: its states, its edges, its Hill cycles (one per mode, in the
    form's mode order: (mode id, ((edge id, +1 or -1), ...)), +1 traversing an edge from its source
    to its target), its rate scale omega (1/s) and the c° of its activities (mM)."""

    states: tuple
    edges: tuple
    cycles: tuple
    rate_scale_per_s: float
    standard_state_mM: float = 1000.0


class FluxTerm(NamedTuple):
    """One term of a net-flow mode, w (1 - exp(x_t + eps psi)): its weight w (dimensionless, times
    the population's k a; finite, nonzero and signed, so a mode may book a cycle's flux with either
    sign), its own stoichiometry (one integer count per row) and its shift eps."""

    weight: float
    counts: tuple
    shift: float = 0.0


class Affine(NamedTuple):
    """A real exponent written from one population parameter: scale p + offset. Exponents only,
    never counts (the lead's ruling of 20 November 2026)."""

    parameter: str
    scale: float = 1.0
    offset: float = 0.0


class Reference(NamedTuple):
    """A concentration a monomial form reads: its role's species at an end (N or P), in a form:
    "free" (the default), "total", or a species-registry form's ID. The kind resolves it at parse
    into monomials of free concentrations (the binding owner's three conditions)."""

    role: str
    end: str
    form: str = "free"


class CitedConstant(NamedTuple):
    """A rate constant's log built at parse from a cited standard free energy at pH 7 (kJ/mol)
    and its scalar protons' offset to the 1 M basis, at the world's temperature T (the lead's
    ruling 7): log k = offset - scale (1000 dg_kj_mol / (R T) + protons ln 1e7 + rt_term). Its mode
    emits the cited value as its seam-E entry. rt_term is a temperature-free part in RT units, such
    as -ln K of an equilibrium constant cited dimensionless (the kinase's K_base), so the entry
    carries it unrounded (the law modules' addition (b), 20 November 2026)."""

    dg_kj_mol: float
    protons: int = 0
    scale: float = 1.0
    offset: float = 0.0
    rt_term: float = 0.0


class RateConstant(NamedTuple):
    """A rate-only constant (the lead's ruling 3 on the law modules, 20 November 2026): its log is
    built at the world's T as a CitedConstant's, log k = offset - scale (1000 dg_kj_mol / (R T) +
    protons ln 1e7), but it emits no seam-E entry, and it is admitted only as a monomial mode's log
    k. So it scales S and never enters x, which stays entirely the registry's: the synthase's
    Delta G°_ATP, cited at pH 7 on total phosphate, is such a constant inside its forward term."""

    dg_kj_mol: float
    protons: int = 0
    scale: float = 1.0
    offset: float = 0.0


class Scaled(NamedTuple):
    """A factor term's K from a positive population parameter, in the form's units: factor x
    value^power (1e-3 turns a constant printed in mM into M; power -1 a constant that divides, as
    1 + c/k). The law modules' addition (a): Table 1's two columns differ in such constants."""

    parameter: str
    factor: float = 1.0
    power: int = 1


class MonomialTerm(NamedTuple):
    """One term of a monomial factor's sum: K prod a_r^q e^(eta psi), K a positive number, a
    positive parameter's name or a Scaled one, each q and eta a number or an Affine."""

    k: object
    orders: tuple = ()  # ((Reference, q), ...)
    eta: object = 0.0


class MonomialFactor(NamedTuple):
    """(1 + sum_g term_g)^(-power): its power a number or an Affine (either sign), its terms one
    or more MonomialTerms."""

    power: object
    terms: tuple


class MonomialRate(NamedTuple):
    """One mode's S (module docstring): log k (a number, a CitedConstant or a RateConstant), the
    orders ((Reference, o), ...), zeta, the factors and the affinity share n; and `constants`, each
    a positive parameter (its name or a Scaled one) that multiplies S, so a source's fitted
    constant is a population's value, never the law's (D144): log k gains sum ln K."""

    log_k: object = 0.0
    orders: tuple = ()
    zeta: object = 0.0
    factors: tuple = ()
    share: int = 1
    constants: tuple = ()


class MonomialForm(NamedTuple):
    """The monomial kinetics' data: one MonomialRate per mode, in the modes' order; its read roles
    ((role, valence or None), ...), roles its references may name that have no row; and c° (mM),
    the standard state of its activities a = c/c° (1 M, as the diagram's)."""

    rates: tuple
    read_roles: tuple = ()
    standard_state_mM: float = 1000.0


def _named(value):
    return isinstance(value, str) and bool(value)


def _int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _rate_name(value):
    """(parameter name, sign) of a named rate field, the sign -1 for a leading "-"; or None for a
    number."""
    if not _named(value):
        return None
    return (value[1:], -1) if value.startswith("-") else (value, 1)


def _k0_admitted(value, by_name):
    """A k0: a positive number, or the name of a positive parameter in 1/s (never negated)."""
    if _finite(value):
        return value > 0
    p = by_name.get(value) if _named(value) else None
    return p is not None and p.positive and p.unit == "1/s"


def _zeta_admitted(value, by_name):
    """A zeta: a finite number, or a parameter's name in 1, a leading "-" negating it."""
    if _finite(value):
        return True
    named = _rate_name(value)
    p = by_name.get(named[0]) if named is not None else None
    return p is not None and p.unit == "1"


def _named_rates(diagram, signed=None, *, zeta=True):
    """The named rate fields, (edge ID, field, value), on a cycle's signed edges (every edge where
    signed is None); zeta's too unless zeta=False."""
    keep = None if signed is None else {e for e, _ in signed}
    out = []
    for edge in diagram.edges:
        if keep is not None and edge.id not in keep:
            continue
        for direction, rate in (("forward", edge.forward), ("backward", edge.backward)):
            if _named(rate.k0_per_s):
                out.append((edge.id, f"{direction} k0", rate.k0_per_s))
            if zeta and _named(rate.zeta):
                out.append((edge.id, f"{direction} zeta", rate.zeta))
    return out


def _numeric(diagram, signed=None, *, zeta=True):
    """Refuses a named rate a numeric consumer would read (resolved gives one population's)."""
    named = _named_rates(diagram, signed, zeta=zeta)
    if named:
        edge, field, value = named[0]
        raise ValueError(
            f"edge {edge}'s {field} names the parameter {value!r}: resolve the form for one "
            "population first (forms.resolved)"
        )


class CycleForm(NamedTuple):
    """A cycle law's general form (module docstring)."""

    kinetics: str
    roles: tuple
    rows: tuple
    modes: tuple
    parameters: tuple = ()
    fuel_roles: tuple = ()
    saturation: tuple = ()
    diagram: Diagram | None = None
    flux_terms: tuple = ()
    ph_bands: tuple = ()
    temperature_K: tuple | None = None  # (low, high) in K, or None: no domain of its own
    monomial: MonomialForm | None = None  # The monomial kinetics' data (K6).

    @property
    def role_names(self):
        return tuple(role for role, _ in self.roles)

    @property
    def parameter_names(self):
        return tuple(p.name for p in self.parameters)

    def changes(self):
        """The manifest's change rows (registry/declarations.py): ({role, per_cycle, mode}, ...),
        one per row a mode changes, with role "role@end" and per_cycle its count per forward cycle
        (an integer, or a parameter's name with an optional leading "-")."""
        return tuple(
            dict(role=f"{role}@{end}", per_cycle=count, mode=mode)
            for mode, counts in self.modes
            for (role, end), count in zip(self.rows, counts, strict=True)
            if count != 0
        )

    def free_energy_band(self, mode, terms, c0_mM):
        """The band within which a free-energy entry this form produced may differ from the
        registry's (seam E; the binding owner's check, under ruling (d): computed from the form,
        never from the entry), a Decimal, or None for a form with no constants of its own
        (factored and net-flow forms: the registry then uses its generic rule).
        - mode: the entry's mode ID; terms: ((nu, mu°/RT at c0_mM), ...), the entry's
          coefficients each with the registry's potential; c0_mM: the registry's standard
          concentration.
        - A diagram form gives that mode's cycle's Wegscheider band, B_W = WEGSCHEIDER_BAND eps
          (T + N), T the cycle's edges' |ln k0+-| plus sum |nu| (|mu| + |ln c0_mM| + |ln c°|), c°
          the diagram's standard state, N its rate constants: _cycle_band, wegscheider's own code,
          so it equals wegscheider(...).band where each species has one role.
        - Plus one ulp of the mode's implied dG°/RT (implied_free_energy, rounded once), the
          lead's ruling, so that every law Wegscheider's condition admits, the entry's check
          admits too: the entry carries that rounding beyond the residual the band admits."""
        if self.kinetics != "diagram":
            return None
        modes = [m for m, _ in self.modes]
        if mode not in modes:
            raise ValueError(f"the form has no mode {mode!r}; its modes are {modes}")
        index = modes.index(mode)
        _, signed = self.diagram.cycles[index]
        _, _, _, band = _cycle_band(self.diagram, signed, tuple(terms), c0_mM)
        _, implied, _ = implied_free_energy(self, index)
        return band + Decimal(math.ulp(implied))

    def errors(self):
        """Why this form breaks its contract (empty: it keeps it)."""
        out = []
        if self.kinetics not in KINETICS:
            return [f"its kinetics is one of {', '.join(KINETICS)}"]
        roles = self.roles
        if not (
            isinstance(roles, tuple)
            and roles
            and all(
                isinstance(r, tuple)
                and len(r) == 2
                and _named(r[0])
                and (r[1] is None or _int(r[1]))
                for r in roles
            )
            and len({r[0] for r in roles}) == len(roles)
        ):
            return out + ["its roles are distinct (role, valence or None) pairs"]
        names = set(self.role_names)
        rows = self.rows
        if not (
            isinstance(rows, tuple)
            and rows
            and all(
                isinstance(r, tuple) and len(r) == 2 and r[0] in names and r[1] in ENDS
                for r in rows
            )
            and len(set(rows)) == len(rows)
        ):
            return out + ["its rows are distinct (role, N or P) pairs of its roles"]
        unused = sorted(names - {role for role, _ in rows})
        if unused:
            out.append(f"roles {unused} have no row")
        parameters = self.parameters
        if not (
            isinstance(parameters, tuple)
            and all(isinstance(p, Parameter) and _named(p.name) and _named(p.unit) for p in parameters)
            and len({p.name for p in parameters}) == len(parameters)
        ):
            return out + ["its parameters are distinct Parameters, each named with its unit"]
        for p in parameters:
            if any(b is not None and not _finite(b) for b in (p.low, p.high)):
                out.append(f"parameter {p.name}'s bounds are finite numbers or None")
            elif p.low is not None and p.high is not None and p.low > p.high:
                out.append(f"parameter {p.name}'s range is empty")
        by_name = {p.name: p for p in parameters}
        modes = self.modes
        if not (
            isinstance(modes, tuple)
            and modes
            and all(
                isinstance(m, tuple)
                and len(m) == 2
                and _named(m[0])
                and isinstance(m[1], tuple)
                and len(m[1]) == len(rows)
                for m in modes
            )
            and len({m[0] for m in modes}) == len(modes)
        ):
            return out + ["its modes are distinct (mode id, (count per row, ...)) pairs"]
        for mode_id, counts in modes:
            for count in counts:
                if _int(count):
                    continue
                name = count[1:] if _named(count) and count.startswith("-") else count
                p = by_name.get(name) if _named(name) else None
                if p is None or not p.integer:
                    out.append(
                        f"mode {mode_id}'s count {count!r} is an integer or an integer "
                        "parameter's name"
                    )
            if all(_int(c) and c == 0 for c in counts):
                out.append(f"mode {mode_id} changes no row")
        if not (isinstance(self.fuel_roles, tuple) and set(self.fuel_roles) <= names):
            out.append("its fuel roles are among its roles")
        for band in self.ph_bands:
            if not (
                isinstance(band, PhBand)
                and band.row in rows
                and band.center in by_name
                and band.width in by_name
            ):
                out.append("each pH band names a row and two of its parameters")
        t = self.temperature_K
        if t is not None and not (
            isinstance(t, tuple) and len(t) == 2 and all(map(_finite, t)) and 0 < t[0] < t[1]
        ):
            out.append("its temperature domain is a (low, high) interval in K, or None")
        given = {
            "factored": bool(self.saturation),
            "diagram": self.diagram is not None,
            "net_flow": bool(self.flux_terms),
            "monomial": self.monomial is not None,
        }
        stray = sorted(k for k, v in given.items() if v and k != self.kinetics)
        if stray:
            out.append(f"a {self.kinetics} form gives no {', '.join(stray)} data")
        if self.kinetics == "factored":
            out += self._saturation_errors(by_name)
        elif self.kinetics == "diagram":
            out += diagram_errors(self)
        elif self.kinetics == "monomial":
            out += monomial_errors(self)
        else:
            out += self._flux_term_errors()
        return out

    def _saturation_errors(self, by_name):
        out = []
        if not (isinstance(self.saturation, tuple) and len(self.saturation) == len(self.modes)):
            return ["a factored form gives one tuple of saturations per mode"]
        for (mode_id, _), factors in zip(self.modes, self.saturation, strict=True):
            if not isinstance(factors, tuple):
                out.append(f"mode {mode_id}'s saturations are a tuple")
                continue
            for f in factors:
                if not (isinstance(f, Saturation) and f.row in self.rows):
                    out.append(f"mode {mode_id}'s saturations are Saturations on its rows")
                    continue
                k = by_name.get(f.k_mM) if _named(f.k_mM) else None
                if not ((_finite(f.k_mM) and f.k_mM > 0) or (k is not None and k.positive)):
                    out.append(f"mode {mode_id}: a saturation's K is positive, or a positive parameter")
                h = by_name.get(f.hill) if _named(f.hill) else None
                if not ((_int(f.hill) and f.hill > 0) or (h is not None and h.integer and h.positive)):
                    out.append(
                        f"mode {mode_id}: a saturation's Hill number is a positive integer, or a "
                        "positive integer parameter"
                    )
        return out

    def _flux_term_errors(self):
        out = []
        if not (isinstance(self.flux_terms, tuple) and len(self.flux_terms) == len(self.modes)):
            return ["a net-flow form gives one tuple of flux terms per mode"]
        for (mode_id, _), terms in zip(self.modes, self.flux_terms, strict=True):
            if not (isinstance(terms, tuple) and terms):
                out.append(f"mode {mode_id}'s flux terms are a non-empty tuple")
                continue
            for t in terms:
                if not (
                    isinstance(t, FluxTerm)
                    and _finite(t.weight)
                    and t.weight != 0
                    and isinstance(t.counts, tuple)
                    and len(t.counts) == len(self.rows)
                    and all(map(_int, t.counts))
                    and _finite(t.shift)
                ):
                    out.append(
                        f"mode {mode_id}'s flux terms are FluxTerms: a finite nonzero weight (either "
                        "sign), an integer count per row and a finite shift"
                    )
        return out


# ------------------------------------------------------------------ resolving a population's values


def resolve(form, values):
    """The form's numbers for one population's parameter values ({name: float}): (counts [M, K]
    integers, saturation [(row index, K, h), ...] per mode, bands [(row index, center, width)])."""

    def number(item, cast):
        if _named(item):
            sign = -1 if item.startswith("-") else 1
            return sign * cast(values[item.lstrip("-")])
        return cast(item)

    counts = np.array(
        [[number(c, int) for c in mode_counts] for _, mode_counts in form.modes], dtype=np.int64
    )
    index = {row: k for k, row in enumerate(form.rows)}
    saturation = [
        [(index[f.row], number(f.k_mM, float), number(f.hill, int)) for f in factors]
        for factors in (form.saturation or [()] * len(form.modes))
    ]
    bands = [(index[b.row], float(values[b.center]), float(values[b.width])) for b in form.ph_bands]
    return counts, saturation, bands


def resolved(form, values):
    """The form for one population's parameter values ({name: value}): each named diagram rate
    replaced by its value (a k0 by its parameter's, a zeta by its parameter's, negated where it
    names "-name"). The form itself where it names none, so a numeric form, and every world that
    runs one, is unchanged; a form of another kinetics is returned as it is."""
    if form.kinetics == "monomial":
        return _resolved_monomial(form, values)
    d = form.diagram
    if form.kinetics != "diagram" or not _named_rates(d):
        return form

    def number(value):
        named = _rate_name(value)
        if named is None:
            return value
        name, sign = named
        return sign * float(values[name])

    def rate(r):
        return r._replace(k0_per_s=number(r.k0_per_s), zeta=number(r.zeta))

    edges = tuple(e._replace(forward=rate(e.forward), backward=rate(e.backward)) for e in d.edges)
    return form._replace(diagram=d._replace(edges=edges))


def _resolved_monomial(form, values):
    """resolved()'s monomial part: each Affine exponent and each named K replaced by its value for
    one population (a CitedConstant stays: the kind builds it at the world's temperature). The form
    itself where it names none."""
    named = []

    def number(value):
        if isinstance(value, Affine):
            named.append(value)
            return value.scale * float(values[value.parameter]) + value.offset
        return value

    def constant(value):
        if _named(value):
            named.append(value)
            return float(values[value])
        if isinstance(value, Scaled):
            named.append(value)
            return value.factor * float(values[value.parameter]) ** value.power
        return value

    def orders(pairs):
        return tuple((reference, number(e)) for reference, e in pairs)

    def term(x):
        return x._replace(k=constant(x.k), orders=orders(x.orders), eta=number(x.eta))

    def factor(f):
        return f._replace(power=number(f.power), terms=tuple(map(term, f.terms)))

    rates = tuple(
        r._replace(
            orders=orders(r.orders),
            zeta=number(r.zeta),
            factors=tuple(map(factor, r.factors)),
            constants=tuple(map(constant, r.constants)),
        )
        for r in form.monomial.rates
    )
    return form._replace(monomial=form.monomial._replace(rates=rates)) if named else form


def parameter_errors(form, values):
    """Why a population's parameter values ({name: value}) break the form's declared ranges."""
    out = []
    for p in form.parameters:
        v = values.get(p.name)
        if not _finite(v):
            out.append(f"parameter {p.name} is a finite number")
            continue
        if p.integer and float(v) != round(float(v)):
            out.append(f"parameter {p.name} is an integer")
        if p.positive and not v > 0:
            out.append(f"parameter {p.name} is positive")
        if p.low is not None and v < p.low:
            out.append(f"parameter {p.name} is at least {p.low}")
        if p.high is not None and v > p.high:
            out.append(f"parameter {p.name} is at most {p.high}")
    return out


# ------------------------------------------------------------------ the diagram's topology


def _connected(nodes, pairs):
    parent = {n: n for n in nodes}

    def find(n):
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n

    for u, v in pairs:
        parent[find(u)] = find(v)
    return len({find(n) for n in nodes}) <= 1


def simple_cycles(n_states, pairs):
    """Every simple cycle of an undirected multigraph (n_states nodes, edges as (u, v) pairs), as
    frozensets of edge indices: the edge subsets in which every touched node has degree 2 and that
    are connected. Two parallel edges form one; a single edge forms none."""
    del n_states
    out = []
    for size in range(2, len(pairs) + 1):
        for subset in itertools.combinations(range(len(pairs)), size):
            degree = {}
            for e in subset:
                for node in pairs[e]:
                    degree[node] = degree.get(node, 0) + 1
            if all(d == 2 for d in degree.values()) and _connected(
                degree, [pairs[e] for e in subset]
            ):
                out.append(frozenset(subset))
    return out


def spanning_trees(n_states, pairs):
    """Every spanning tree of a connected multigraph, as tuples of edge indices."""
    out = []
    nodes = range(n_states)
    for subset in itertools.combinations(range(len(pairs)), n_states - 1):
        if _connected(nodes, [pairs[e] for e in subset]):
            out.append(subset)
    return out


def _directed(tree, pairs, root, node_of):
    """(edge index, forward) for each edge of `tree`, oriented towards `root`: the transition from
    its child to its parent. node_of maps a state to its node (a contraction's merged node)."""
    adjacent = {}
    for e in tree:
        u, v = (node_of(s) for s in pairs[e])
        adjacent.setdefault(u, []).append((e, v))
        adjacent.setdefault(v, []).append((e, u))
    out, seen, todo = [], {root}, [root]
    while todo:
        parent = todo.pop()
        for e, child in adjacent.get(parent, ()):
            if child in seen:
                continue
            seen.add(child)
            todo.append(child)
            source = node_of(pairs[e][0])
            out.append((e, source == child))  # Forward: the edge's source is the child.
    return tuple(sorted(out))


class Topology(NamedTuple):
    """A diagram's directional diagrams and its cycles' parts (state, edge and cycle indices)."""

    pairs: tuple  # ((source, target), ...) per edge
    trees: tuple  # every spanning tree
    terms: tuple  # ((root, ((edge, forward), ...)), ...): every directional diagram
    plus: tuple  # per declared cycle: ((edge, forward), ...) in its + direction
    minus: tuple  # per declared cycle: the reverse
    cut: tuple  # per declared cycle: (((edge, forward), ...), ...), its contraction's diagrams
    simple: tuple  # every simple cycle, as frozensets of edge indices


def topology(diagram):
    """The diagram's Topology (module docstring), cached on its structure (its states' count, its
    edges' IDs and ends, and its cycles), not its rates, so the populations of one law, each
    resolved with its own values, share one."""
    edges = tuple((edge.id, edge.source, edge.target) for edge in diagram.edges)
    return _topology(len(diagram.states), edges, diagram.cycles)


@lru_cache(maxsize=None)
def _topology(n, edges, cycles):
    ids = {edge_id: k for k, (edge_id, _, _) in enumerate(edges)}
    pairs = tuple((source, target) for _, source, target in edges)
    trees = tuple(spanning_trees(n, pairs))
    terms = tuple(
        (root, _directed(tree, pairs, root, lambda s: s)) for tree in trees for root in range(n)
    )
    plus, minus, cut = [], [], []
    for _, signed in cycles:
        steps = [(ids[e], sign > 0) for e, sign in signed]
        plus.append(tuple(steps))
        minus.append(tuple((e, not forward) for e, forward in steps))
        members = {state for e, _ in steps for state in pairs[e]}
        merged = -1  # The contracted node.

        def node_of(state, members=members):
            return merged if state in members else state

        kept = [e for e in range(len(pairs)) if not set(pairs[e]) <= members]
        nodes = [merged] + [s for s in range(n) if s not in members]
        contracted = [(node_of(pairs[e][0]), node_of(pairs[e][1])) for e in kept]
        diagrams = []
        for subset in itertools.combinations(range(len(kept)), len(nodes) - 1):
            if _connected(nodes, [contracted[i] for i in subset]):
                tree = tuple(kept[i] for i in subset)
                diagrams.append(_directed(tree, pairs, merged, node_of))
        cut.append(tuple(diagrams))
    simple = tuple(simple_cycles(n, pairs))
    return Topology(pairs, trees, terms, tuple(plus), tuple(minus), tuple(cut), simple)


def _is_directed_cycle(steps, pairs):
    """Whether signed edges ((edge, forward), ...) form one directed closed walk through distinct
    states: each touched state is left once and entered once, and they are connected."""
    out_degree, in_degree = {}, {}
    for e, forward in steps:
        u, v = pairs[e] if forward else pairs[e][::-1]
        out_degree[u] = out_degree.get(u, 0) + 1
        in_degree[v] = in_degree.get(v, 0) + 1
    states = set(out_degree) | set(in_degree)
    return (
        all(out_degree.get(s) == 1 and in_degree.get(s) == 1 for s in states)
        and _connected(states, [pairs[e] for e, _ in steps])
    )


def diagram_errors(form):
    """Why a diagram form breaks its contract (CycleForm.errors's diagram part)."""
    d = form.diagram
    if not isinstance(d, Diagram):
        return ["a diagram form gives a Diagram"]
    out = []
    n = len(d.states) if isinstance(d.states, tuple) else 0
    if not (2 <= n <= MAX_STATES and all(map(_named, d.states)) and len(set(d.states)) == n):
        return [f"its diagram has 2 to {MAX_STATES} distinct named states"]
    edges = d.edges
    if not (isinstance(edges, tuple) and 1 <= len(edges) <= MAX_EDGES):
        return [f"its diagram has 1 to {MAX_EDGES} edges"]
    rows = set(form.rows)
    by_name = {p.name: p for p in form.parameters}
    for edge in edges:
        if not (
            isinstance(edge, Edge)
            and _named(edge.id)
            and _int(edge.source)
            and _int(edge.target)
            and 0 <= edge.source < n
            and 0 <= edge.target < n
            and edge.source != edge.target
        ):
            return ["its diagram's edges are Edges between two distinct states"]
        for rate in (edge.forward, edge.backward):
            if not (
                isinstance(rate, Rate)
                and _k0_admitted(rate.k0_per_s, by_name)
                and _zeta_admitted(rate.zeta, by_name)
                and isinstance(rate.orders, tuple)
                and all(
                    isinstance(o, tuple)
                    and len(o) == 3
                    and (o[0], o[1]) in rows
                    and _int(o[2])
                    and o[2] > 0
                    for o in rate.orders
                )
                and len({(o[0], o[1]) for o in rate.orders}) == len(rate.orders)
            ):
                out.append(
                    f"edge {edge.id}: each rate has a positive k0, a finite zeta and distinct "
                    "positive integer orders on the form's rows (a k0 may name a positive "
                    'parameter in 1/s, and a zeta a parameter in 1, negated by a leading "-")'
                )
    if len({edge.id for edge in edges}) != len(edges):
        out.append("its diagram's edge IDs are distinct")
    if not (_finite(d.rate_scale_per_s) and d.rate_scale_per_s > 0):
        out.append("its diagram's rate scale is positive")
    if not (_finite(d.standard_state_mM) and d.standard_state_mM > 0):
        out.append("its diagram's standard state is positive")
    if out:
        return out
    pairs = tuple((edge.source, edge.target) for edge in edges)
    if not _connected(range(n), pairs):
        return ["its diagram is connected"]
    ids = {edge.id: k for k, edge in enumerate(edges)}
    cycles = d.cycles
    if not (isinstance(cycles, tuple) and len(cycles) == len(form.modes)):
        return ["its diagram gives one Hill cycle per mode, in the modes' order"]
    declared = []
    for (mode_id, counts), cycle in zip(form.modes, cycles, strict=True):
        if not (
            isinstance(cycle, tuple)
            and len(cycle) == 2
            and cycle[0] == mode_id
            and isinstance(cycle[1], tuple)
            and cycle[1]
            and all(
                isinstance(s, tuple) and len(s) == 2 and s[0] in ids and s[1] in (1, -1)
                for s in cycle[1]
            )
            and len({s[0] for s in cycle[1]}) == len(cycle[1])
        ):
            out.append(f"mode {mode_id}'s cycle is (its ID, ((edge ID, +1 or -1), ...))")
            continue
        steps = [(ids[e], sign > 0) for e, sign in cycle[1]]
        if not _is_directed_cycle(steps, pairs):
            out.append(f"mode {mode_id}'s edges do not form one directed cycle")
            continue
        declared.append(frozenset(e for e, _ in steps))
        if not all(map(_int, counts)):
            out.append(f"mode {mode_id}: a diagram's counts are integers")
            continue
        for k, row in enumerate(form.rows):
            b = structural_coefficient(d, cycle[1], row) + counts[k]
            if b != 0:
                out.append(
                    f"mode {mode_id}: Wegscheider's coefficient of ln a at {row[0]}@{row[1]} is "
                    f"{b}, not 0 (its count disagrees with its edges' orders)"
                )
        net = {}
        for (role, _), count in zip(form.rows, counts, strict=True):
            net[role] = net.get(role, 0) + count
        named = _named_rates(d, cycle[1], zeta=False)
        if any(net.values()) and named:  # E3: seam E reads a converting cycle's constants.
            edge_id, field, value = named[0]
            out.append(
                f"mode {mode_id}: a cycle that converts a species gives every k0 on its edges as "
                f"a number (edge {edge_id}'s {field} names {value!r}): seam E's check reads its "
                "free-energy band from the law's own constants"
            )
    if out:
        return out
    simple = set(simple_cycles(n, pairs))
    if len(set(declared)) != len(declared):
        out.append("its diagram declares a Hill cycle twice")
    missing, extra = simple - set(declared), set(declared) - simple
    names = {k: edge.id for k, edge in enumerate(edges)}
    for cycle in sorted(missing, key=sorted):
        out.append(
            "its modes miss the Hill cycle through "
            + ", ".join(names[e] for e in sorted(cycle))
            + " (§16: every cycle of the diagram, dependent ones included)"
        )
    if extra:
        out.append("a declared cycle is not a simple cycle of the diagram")
    return out


def structural_coefficient(diagram, signed, row):
    """sum_e s_e (order+ - order-) at row, over a cycle's signed edges: Wegscheider's coefficient of
    ln a at that row, less the row's count (exact, in integers)."""
    by_id = {edge.id: edge for edge in diagram.edges}
    total = 0
    for e, sign in signed:
        edge = by_id[e]
        forward = sum(o[2] for o in edge.forward.orders if (o[0], o[1]) == row)
        backward = sum(o[2] for o in edge.backward.orders if (o[0], o[1]) == row)
        total += sign * (forward - backward)
    return total


# ------------------------------------------------------------------ Wegscheider at parse (§5.1)


class Wegscheider(NamedTuple):
    """One cycle's residual r = R0 + sum_rows B ln a + B_psi psi at the engine's potentials, decided
    algebraically: B in integers, B_psi in rationals, R0 to DIGITS digits; and its bands."""

    mode: str
    coefficients: tuple  # ((role, end, B), ...), each an integer
    psi: Fraction  # B_psi
    psi_band: Fraction  # u sum |zeta|
    constant: Decimal  # R0
    terms: Decimal  # T
    constants: int  # N, the cycle's rate constants
    band: Decimal  # 32 eps (T + N)

    @property
    def admitted(self):
        return (
            all(b == 0 for *_, b in self.coefficients)
            and abs(self.psi) <= self.psi_band
            and abs(self.constant) <= self.band
        )


def wegscheider(form, mode_index, valence, potential, c0_mM):
    """Wegscheider's residual of a diagram form's cycle (design statement 1, §5.1), for the species
    a population binds: valence {role: z} and potential {role: mu°/RT at c0_mM}; potentials are
    needed only for roles whose net change is nonzero. Decided algebraically; never at a state.
    The form is one population's (resolved): a named rate on the cycle is refused."""
    d = form.diagram
    mode_id, counts = form.modes[mode_index]
    _, signed = d.cycles[mode_index]
    _numeric(d, signed)
    by_id = {edge.id: edge for edge in d.edges}
    coefficients = tuple(
        (role, end, structural_coefficient(d, signed, (role, end)) + counts[k])
        for k, (role, end) in enumerate(form.rows)
    )
    charge = sum(valence[role] * counts[k] for k, (role, end) in enumerate(form.rows) if end == "P")
    zeta = Fraction(0)
    zeta_abs = Fraction(0)
    for e, sign in signed:
        edge = by_id[e]
        zeta += sign * (Fraction(edge.forward.zeta) - Fraction(edge.backward.zeta))
        zeta_abs += abs(Fraction(edge.forward.zeta)) + abs(Fraction(edge.backward.zeta))
    u = Fraction(UNIT_ROUNDOFF)
    net = {}
    for k, (role, _) in enumerate(form.rows):
        net[role] = net.get(role, 0) + counts[k]
    pairs = tuple((delta, potential[role]) for role, delta in net.items() if delta != 0)
    constant, terms, n_constants, band = _cycle_band(d, signed, pairs, c0_mM)
    return Wegscheider(
        mode_id, coefficients, zeta - charge, u * zeta_abs, constant, terms, n_constants, band
    )


def _cycle_band(diagram, signed, pairs, c0_mM):
    """One cycle's constant R0, its terms T, its rate constants N and Wegscheider's band
    B_W = WEGSCHEIDER_BAND eps (T + N), each a Decimal at DIGITS digits from the declared doubles:
    R0 = sum_e s_e (ln k0+ - ln k0-) + sum Delta (mu - ln c0 + ln c°) and T = sum_e (|ln k0+| +
    |ln k0-|) + sum |Delta| (|mu| + |ln c0| + |ln c°|), over the cycle's signed edges and the pairs
    ((Delta, mu°/RT at c0_mM), ...) of the species it converts, c° the diagram's standard state.
    The one code for wegscheider's band and CycleForm.free_energy_band, so they cannot drift. It
    reads the cycle's k0 only, each a number (a named one is refused)."""
    _numeric(diagram, signed, zeta=False)
    by_id = {edge.id: edge for edge in diagram.edges}
    with localcontext() as ctx:
        ctx.prec = DIGITS
        constant, terms = Decimal(0), Decimal(0)
        for e, sign in signed:
            edge = by_id[e]
            ln_f = Decimal(edge.forward.k0_per_s).ln()
            ln_b = Decimal(edge.backward.k0_per_s).ln()
            constant += sign * (ln_f - ln_b)
            terms += abs(ln_f) + abs(ln_b)
        ln_c0 = Decimal(c0_mM).ln()
        ln_standard = Decimal(diagram.standard_state_mM).ln()
        for delta, mu in pairs:
            mu = Decimal(mu)
            constant += delta * (mu - ln_c0 + ln_standard)
            terms += abs(delta) * (abs(mu) + abs(ln_c0) + abs(ln_standard))
        n_constants = 2 * len(signed)
        band = Decimal(WEGSCHEIDER_BAND) * Decimal(EPS) * (terms + n_constants)
        return +constant, +terms, n_constants, +band


def implied_free_energy(form, mode_index):
    """A diagram form's cycle's standard free energy implied by its own constants (seam E's kind
    hook; the lead's answer of 19 November): ({role: net change over both ends}, dG°/RT, c0 in mM),
    dG°/RT = -sum_e s_e (ln k0+ - ln k0-) at the diagram's standard state c0, evaluated at DIGITS
    digits from the declared doubles and rounded once. Wegscheider's condition (wegscheider) holds
    when it equals the registry's sum of nu mu°/RT at that standard state, within its band; the
    species registry's check of a kind's free energies confirms it. An empty change: the cycle
    converts nothing (it only transports). It reads the cycle's k0 only, each a number (a named one
    is refused: E3 keeps a converting cycle's k0 the law's own)."""
    d = form.diagram
    _, counts = form.modes[mode_index]
    _, signed = d.cycles[mode_index]
    _numeric(d, signed, zeta=False)
    by_id = {edge.id: edge for edge in d.edges}
    net = {}
    for k, (role, _) in enumerate(form.rows):
        net[role] = net.get(role, 0) + counts[k]
    with localcontext() as ctx:
        ctx.prec = DIGITS
        constant = Decimal(0)
        for e, sign in signed:
            edge = by_id[e]
            constant += sign * (Decimal(edge.forward.k0_per_s).ln() - Decimal(edge.backward.k0_per_s).ln())
        value = float(-constant)
    return {role: n for role, n in net.items() if n != 0}, value, d.standard_state_mM


# ------------------------------------------------------------------ the monomial form (K6)


def monomial_errors(form):
    """Why a monomial form breaks its contract (CycleForm.errors's monomial part)."""
    m = form.monomial
    if not isinstance(m, MonomialForm):
        return ["a monomial form gives a MonomialForm"]
    reads = m.read_roles
    if not (
        isinstance(reads, tuple)
        and all(
            isinstance(r, tuple) and len(r) == 2 and _named(r[0]) and (r[1] is None or _int(r[1]))
            for r in reads
        )
        and len({r[0] for r in reads}) == len(reads)
    ):
        return ["its read roles are distinct (role, valence or None) pairs"]
    out = []
    if not (_finite(m.standard_state_mM) and m.standard_state_mM > 0):
        out.append("its standard state is positive")
    names, read_names = set(form.role_names), {r[0] for r in reads}
    if read_names & names:
        out.append(f"read roles {sorted(read_names & names)} are also its rows' roles")
    if not (isinstance(m.rates, tuple) and len(m.rates) == len(form.modes)):
        return out + ["a monomial form gives one MonomialRate per mode, in the modes' order"]
    by_name = {p.name: p for p in form.parameters}
    known = names | read_names

    def exponent_ok(value):
        if _finite(value):
            return True
        return (
            isinstance(value, Affine)
            and value.parameter in by_name
            and _finite(value.scale)
            and _finite(value.offset)
        )

    def orders_ok(pairs):
        return (
            isinstance(pairs, tuple)
            and all(
                isinstance(o, tuple)
                and len(o) == 2
                and isinstance(o[0], Reference)
                and o[0].role in known
                and o[0].end in ENDS
                and _named(o[0].form)
                and exponent_ok(o[1])
                for o in pairs
            )
            and len({o[0] for o in pairs}) == len(pairs)
        )

    def cited_ok(k):
        return (
            isinstance(k, CitedConstant)
            and all(map(_finite, (k.dg_kj_mol, k.scale, k.offset, k.rt_term)))
            and _int(k.protons)
        )

    def rate_only_ok(k):
        return (
            isinstance(k, RateConstant)
            and all(map(_finite, (k.dg_kj_mol, k.scale, k.offset)))
            and _int(k.protons)
        )

    def k_ok(value):
        if isinstance(value, Scaled):
            p = by_name.get(value.parameter)
            return (
                p is not None
                and p.positive
                and _finite(value.factor)
                and value.factor > 0
                and _int(value.power)
                and value.power != 0
            )
        k = by_name.get(value) if _named(value) else None
        return (_finite(value) and value > 0) or (k is not None and k.positive)

    def term_ok(x):
        if not isinstance(x, MonomialTerm):
            return False
        return k_ok(x.k) and orders_ok(x.orders) and exponent_ok(x.eta)

    for (mode_id, _), rate in zip(form.modes, m.rates, strict=True):
        where = f"mode {mode_id}"
        if not isinstance(rate, MonomialRate):
            out.append(f"{where}'s rate is a MonomialRate")
            continue
        if not (_finite(rate.log_k) or cited_ok(rate.log_k) or rate_only_ok(rate.log_k)):
            out.append(f"{where}: log k is a finite number, a CitedConstant or a RateConstant")
        if not orders_ok(rate.orders):
            out.append(
                f"{where}: its orders are distinct (Reference, exponent) pairs on its roles and "
                "read roles, each exponent a finite number or an Affine of a parameter"
            )
        if not exponent_ok(rate.zeta):
            out.append(f"{where}: zeta is a finite number or an Affine of a parameter")
        if not (_int(rate.share) and 1 <= rate.share <= MAX_SHARE):
            out.append(f"{where}: its share is an integer from 1 to {MAX_SHARE}")
        if not (
            isinstance(rate.constants, tuple)
            and all((_named(c) or isinstance(c, Scaled)) and k_ok(c) for c in rate.constants)
        ):
            out.append(
                f"{where}: its constants are positive parameters, each by its name or Scaled, "
                "never a number (a source's fitted value is a population's, D144)"
            )
        factors = rate.factors if isinstance(rate.factors, tuple) else (None,)
        constants = (RateConstant, CitedConstant)
        if any(
            isinstance(term.k, constants)
            for f in factors
            if isinstance(f, MonomialFactor) and isinstance(f.terms, tuple)
            for term in f.terms
            if isinstance(term, MonomialTerm)
        ):
            out.append(
                f"{where}: a RateConstant or a CitedConstant is a mode's log k only, never a "
                "factor's K (a rate-only constant scales S and never enters x)"
            )
            continue
        for f in factors:
            if not (
                isinstance(f, MonomialFactor)
                and exponent_ok(f.power)
                and isinstance(f.terms, tuple)
                and f.terms
                and all(map(term_ok, f.terms))
            ):
                out.append(
                    f"{where}: each factor is a MonomialFactor, its power a number or an Affine "
                    "and its terms one or more MonomialTerms (K positive, a number or a positive "
                    "parameter, plain or Scaled; distinct orders on its roles; eta a number or an "
                    "Affine)"
                )
    return out


class Monomial(NamedTuple):
    """A monomial of a population's free-concentration slots: its log constant and its
    ((slot, coefficient), ...): exp(log_c) prod a_slot^coefficient."""

    log_c: float
    coefficients: tuple = ()


class ExpandedRate(NamedTuple):
    """One mode's S over a population's free slots, in numbers: log k, orders {slot: o}, zeta, its
    factors ((power, ((log K, {slot: q}, eta), ...)), ...) and its share."""

    log_k: float
    orders: dict
    zeta: float
    factors: tuple
    share: int


def _add(target, coefficients, scale):
    for slot, value in coefficients:
        target[slot] = target.get(slot, 0.0) + scale * value


def expand_rate(rate, read, log_k):
    """One resolved MonomialRate (resolved(): numbers) over a population's free slots.
    read(reference) -> (Monomial, ...): the reference's activity as a sum of monomials of free
    slots, its base first (one for "free" and a registry form, base then each form for "total").
    log_k: the mode's log k, a number (the kind builds a CitedConstant at the world's T).
    - A total in the orders, a_tot^o = m_0^o (1 + sum_j m_j/m_0)^o: m_0^o joins the orders and a
      factor of power -o holds the ratios.
    - A total inside a factor term expands the term into one term per form; it has order 1 and is
      the term's only total, refused otherwise (ValueError, the kind's parse turns it into a
      refusal)."""
    orders, factors = {}, []
    log_k += sum(math.log(c) for c in rate.constants)  # Resolved: each a positive number.
    for reference, o in rate.orders:
        found = read(reference)
        base = found[0]
        log_k += o * base.log_c
        _add(orders, base.coefficients, o)
        if len(found) > 1:  # A total: the forms over the base, as a factor of power -o.
            ratios = []
            for m in found[1:]:
                q = {}
                _add(q, m.coefficients, 1.0)
                _add(q, base.coefficients, -1.0)
                ratios.append((m.log_c - base.log_c, q, 0.0))
            factors.append((-o, tuple(ratios)))
    for f in rate.factors:
        terms = []
        for term in f.terms:
            log_term, q, total = math.log(term.k), {}, None
            for reference, e in term.orders:
                found = read(reference)
                if len(found) == 1:
                    log_term += e * found[0].log_c
                    _add(q, found[0].coefficients, e)
                elif total is None and e == 1:
                    total = found
                else:
                    raise ValueError(
                        f"a total inside a factor term has order 1 and is its term's only total "
                        f"({reference.role}@{reference.end})"
                    )
            if total is None:
                terms.append((log_term, q, term.eta))
            else:
                for m in total:
                    qm = dict(q)
                    _add(qm, m.coefficients, 1.0)
                    terms.append((log_term + m.log_c, qm, term.eta))
        factors.append((f.power, tuple(terms)))
    return ExpandedRate(log_k, orders, rate.zeta, tuple(factors), rate.share)


class MonomialTables(NamedTuple):
    """One population's monomial tables (NumPy, unpadded but for its own maxima): [M], [M, R],
    [M], [M, F], [M, F, G], [M, F, G, R], [M, F, G], [M, F, G] and [M]."""

    log_k: np.ndarray
    orders: np.ndarray
    zeta: np.ndarray
    power: np.ndarray
    term_log_k: np.ndarray
    term_q: np.ndarray
    term_eta: np.ndarray
    term_present: np.ndarray
    share: np.ndarray


def monomial_tables(expanded, n_slots):
    """The tables of one population's expanded rates (ExpandedRate per mode) over n_slots slots."""
    m = len(expanded)
    f_n = max((len(e.factors) for e in expanded), default=0)
    g_n = max((len(terms) for e in expanded for _, terms in e.factors), default=0)
    out = MonomialTables(
        np.zeros(m), np.zeros((m, n_slots)), np.zeros(m), np.zeros((m, f_n)),
        np.zeros((m, f_n, g_n)), np.zeros((m, f_n, g_n, n_slots)), np.zeros((m, f_n, g_n)),
        np.zeros((m, f_n, g_n), dtype=bool), np.ones(m, dtype=np.int64),
    )  # fmt: skip
    for i, e in enumerate(expanded):
        out.log_k[i], out.zeta[i], out.share[i] = e.log_k, e.zeta, e.share
        for slot, o in e.orders.items():
            out.orders[i, slot] = o
        for f, (power, terms) in enumerate(e.factors):
            out.power[i, f] = power
            for g, (log_term, q, eta) in enumerate(terms):
                out.term_log_k[i, f, g], out.term_eta[i, f, g] = log_term, eta
                out.term_present[i, f, g] = True
                for slot, value in q.items():
                    out.term_q[i, f, g, slot] = value
    return out


# ------------------------------------------------------------------ a diagram's tables


class DiagramTables(NamedTuple):
    """A diagram's static tables over a form's rows (NumPy, unpadded), for the kind's layout.
    Edge-direction slots: e forward, E + e backward, and 2E a zero slot (log rate 0)."""

    log_k0: np.ndarray  # [2E + 1]
    orders: np.ndarray  # [2E + 1, K]
    zeta: np.ndarray  # [2E + 1]
    term_slots: np.ndarray  # [T, n - 1]
    term_root: np.ndarray  # [T]
    plus_slots: np.ndarray  # [M, L], padded with the zero slot
    minus_slots: np.ndarray  # [M, L]
    cut_slots: np.ndarray  # [M, C, I], padded with the zero slot
    cut_present: np.ndarray  # [M, C]
    edge_states: np.ndarray  # [E, 2] (source, target)


def diagram_tables(form):
    """The tables of a diagram form (DiagramTables), for one population (resolved): a named rate
    is refused."""
    _numeric(form.diagram)
    d, top = form.diagram, topology(form.diagram)
    n_edges, rows = len(d.edges), {row: k for k, row in enumerate(form.rows)}
    zero = 2 * n_edges
    log_k0 = np.zeros(2 * n_edges + 1)
    orders = np.zeros((2 * n_edges + 1, len(form.rows)))
    zeta = np.zeros(2 * n_edges + 1)
    for e, edge in enumerate(d.edges):
        for slot, rate in ((e, edge.forward), (n_edges + e, edge.backward)):
            log_k0[slot] = math.log(rate.k0_per_s)
            zeta[slot] = rate.zeta
            for role, end, order in rate.orders:
                orders[slot, rows[(role, end)]] += order

    def slot(e, forward):
        return e if forward else n_edges + e

    term_slots = np.array(
        [[slot(e, f) for e, f in steps] for _, steps in top.terms], dtype=np.int64
    ).reshape(len(top.terms), len(d.states) - 1)
    term_root = np.array([root for root, _ in top.terms], dtype=np.int64)
    longest = max(len(steps) for steps in top.plus)
    plus = np.full((len(top.plus), longest), zero, dtype=np.int64)
    minus = np.full((len(top.plus), longest), zero, dtype=np.int64)
    for m, (p, q) in enumerate(zip(top.plus, top.minus, strict=True)):
        plus[m, : len(p)] = [slot(e, f) for e, f in p]
        minus[m, : len(q)] = [slot(e, f) for e, f in q]
    cuts = max(len(c) for c in top.cut)
    width = max((len(steps) for c in top.cut for steps in c), default=0)
    cut_slots = np.full((len(top.cut), cuts, max(width, 1)), zero, dtype=np.int64)
    cut_present = np.zeros((len(top.cut), cuts), dtype=bool)
    for m, c in enumerate(top.cut):
        for t, steps in enumerate(c):
            cut_slots[m, t, : len(steps)] = [slot(e, f) for e, f in steps]
            cut_present[m, t] = True
    edge_states = np.array(top.pairs, dtype=np.int64).reshape(n_edges, 2)
    return DiagramTables(
        log_k0, orders, zeta, term_slots, term_root, plus, minus, cut_slots, cut_present, edge_states
    )


# ------------------------------------------------------------------ the kernels (xp style)


def logsumexp(values, mask, axis, *, xp=jnp):
    """log sum exp(values) over `axis`, counting only where mask is true: -inf where none is."""
    top = xp.max(xp.where(mask, values, -xp.inf), axis=axis, keepdims=True)
    top = xp.where(xp.isfinite(top), top, 0.0)
    shifted = xp.where(mask, values - top, -xp.inf)
    total = xp.sum(xp.exp(shifted), axis=axis, keepdims=True)
    some = total > 0  # Nothing masked in: -inf, without taking log(0).
    out = xp.where(some, xp.log(xp.where(some, total, 1.0)) + top, -xp.inf)
    return xp.squeeze(out, axis=axis)


def softmax(values, mask, axis, *, xp=jnp):
    """exp(values - logsumexp) where mask is true, 0 elsewhere."""
    lse = xp.expand_dims(logsumexp(values, mask, axis, xp=xp), axis)
    return xp.where(mask, xp.exp(xp.where(mask, values - lse, -xp.inf)), 0.0)


def gather(values, slots, *, xp=jnp):
    """values [D, P] read at slots [..., P] per population: [..., P]."""
    cols = xp.arange(values.shape[-1])
    return values[slots, cols]


def hill_log_saturation(row, log_k, hill, present, ln_c, *, xp=jnp):
    """A factored form's log S and its exact gradient (module docstring): per mode m and factor f,
    the row index row [M, F, P], ln K, the Hill number and whether it is present; ln c [K, P].
    Returns (log S [M, P], d log S / d ln c [M, K, P])."""
    k = ln_c.shape[0]
    c = ln_c[row, xp.arange(ln_c.shape[-1])]  # [M, F, P]
    z = hill * (log_k - c)
    soft = xp.logaddexp(0.0, z)
    log_s = -xp.sum(xp.where(present, soft, 0.0), axis=1)
    sigma = xp.exp(z - soft)  # z's logistic: (K/c)^h / (1 + (K/c)^h)
    weight = xp.where(present, hill * sigma, 0.0)  # [M, F, P]
    hit = row[:, :, None, :] == xp.arange(k)[None, None, :, None]  # [M, F, K, P]
    gradient = xp.sum(xp.where(hit, weight[:, :, None, :], 0.0), axis=1)
    return log_s, gradient


class DiagramLogs(NamedTuple):
    """A diagram's quantities per population, in logs where they are positive."""

    log_s: object  # [M, P]
    d_log_s_d_ln_c: object  # [M, K, P]
    d_log_s_d_psi: object  # [M, P]
    log_plus: object  # [M, P]: log Pi+ (per carrier, s^-L)
    log_minus: object  # [M, P]
    log_share: object  # [M, P]: log Sigma_kappa / Sigma
    log_rates: object  # [D, P]: every edge direction's log alpha (1/s); the zero slot last
    occupancy: object  # [states, P]


def diagram_logs(t, ln_c, psi, *, xp=jnp):
    """A diagram form's per-population quantities from its padded tables t (the kind's layout
    fields: log_k0 [D, P], orders [D, K, P], zeta [D, P], term_slots [T, J, P], term_root [T, P],
    term_present [T, P], term_orders [T, K, P], term_zeta [T, P], plus_slots, minus_slots [M, L, P],
    plus_orders [M, K, P], plus_zeta [M, P], cut_slots [M, C, I, P], cut_present [M, C, P],
    cut_orders [M, C, K, P], cut_zeta [M, C, P], log_scale [P], ln_standard [P], state_present
    [S, P]), at ln c [K, P] (mM) and psi [P]."""
    ln_a = ln_c - t.ln_standard[None, :]
    log_rates = t.log_k0 + xp.sum(t.orders * ln_a[None, :, :], axis=1) + t.zeta * psi[None, :]
    terms = xp.sum(gather(log_rates, t.term_slots, xp=xp), axis=1)  # [T, P]
    log_sigma = logsumexp(terms, t.term_present, 0, xp=xp)  # [P]
    # A population that runs no diagram has no term: 0 there, so nothing below is -inf - -inf.
    log_sigma = xp.where(xp.any(t.term_present, axis=0), log_sigma, 0.0)
    weights = softmax(terms, t.term_present, 0, xp=xp)  # [T, P]
    mean_orders = xp.sum(weights[:, None, :] * t.term_orders, axis=0)  # [K, P]
    mean_zeta = xp.sum(weights * t.term_zeta, axis=0)  # [P]
    log_plus = xp.sum(gather(log_rates, t.plus_slots, xp=xp), axis=1)  # [M, P]
    log_minus = xp.sum(gather(log_rates, t.minus_slots, xp=xp), axis=1)
    cut = xp.sum(gather(log_rates, t.cut_slots, xp=xp), axis=2)  # [M, C, P]
    log_cut = logsumexp(cut, t.cut_present, 1, xp=xp)  # [M, P]
    cut_weights = softmax(cut, t.cut_present, 1, xp=xp)  # [M, C, P]
    cut_orders = xp.sum(cut_weights[:, :, None, :] * t.cut_orders, axis=1)  # [M, K, P]
    cut_zeta = xp.sum(cut_weights * t.cut_zeta, axis=1)  # [M, P]
    log_share = log_cut - log_sigma[None, :]
    log_s = log_plus + log_share - t.log_scale[None, :]
    d_ln_c = t.plus_orders + cut_orders - mean_orders[None, :, :]
    d_psi = t.plus_zeta + cut_zeta - mean_zeta[None, :]
    states = t.state_present.shape[0]
    rooted = (t.term_root[None, :, :] == xp.arange(states)[:, None, None]) & t.term_present[None]
    log_d = logsumexp(xp.broadcast_to(terms[None], rooted.shape), rooted, 1, xp=xp)  # [S, P]
    occupancy = xp.where(t.state_present, xp.exp(log_d - log_sigma[None, :]), 0.0)
    return DiagramLogs(log_s, d_ln_c, d_psi, log_plus, log_minus, log_share, log_rates, occupancy)


class MonomialLogs(NamedTuple):
    """A monomial form's log S [M, P] and its exact slopes: d log S / d ln a over the free slots
    [M, R, P], d log S / d psi [M, P] and d log S / d x [M, P] (the share's)."""

    log_s: object
    d_ln_a: object
    d_psi: object
    d_x: object


def monomial_logs(t, ln_a, psi, x, *, xp=jnp):
    """The monomial form's log S and its exact slopes (module docstring), per mode and population:
    t's fields log_k [M, P], orders [M, R, P], zeta [M, P], power [M, F, P], term_log_k
    [M, F, G, P], term_q [M, F, G, R, P], term_eta [M, F, G, P], term_present [M, F, G, P] and
    share [M, P] (n);
    ln a [R, P] at the free slots, psi [P] and x [M, P]. Each factor's log(1 + sum_g e^z_g) is a
    logsumexp with the 1 as a zero term, and its weights sigma_g a softmax over the same terms."""
    z = (
        t.term_log_k
        + xp.sum(t.term_q * ln_a[None, None, None], axis=3)
        + t.term_eta * psi[None, None, None]
    )  # [M, F, G, P]
    one = xp.zeros(z.shape[:2] + (1,) + z.shape[3:])
    values = xp.concatenate((one, z), axis=2)
    mask = xp.concatenate((xp.ones(one.shape, dtype=bool), t.term_present), axis=2)
    soft = logsumexp(values, mask, 2, xp=xp)  # [M, F, P]: log(1 + sum_g e^z_g)
    sigma = softmax(values, mask, 2, xp=xp)[:, :, 1:]  # [M, F, G, P]
    weight = t.power[:, :, None] * sigma  # s_f sigma_fg
    n = t.share
    i = xp.arange(MAX_SHARE)[None, :, None]  # [1, I, 1]
    within = i < n[:, None, :]
    shares = xp.where(within, i * x[:, None, :] / n[:, None, :], 0.0)
    log_s = (
        t.log_k
        + xp.sum(t.orders * ln_a[None], axis=1)
        + t.zeta * psi[None]
        - xp.sum(t.power * soft, axis=1)
        - logsumexp(shares, within, 1, xp=xp)
    )
    w = softmax(shares, within, 1, xp=xp)  # [M, I, P]
    d_x = -xp.sum(w * i / n[:, None, :], axis=1)
    d_ln_a = t.orders - xp.sum(weight[:, :, :, None] * t.term_q, axis=(1, 2))
    d_psi = t.zeta - xp.sum(weight * t.term_eta, axis=(1, 2))
    return MonomialLogs(log_s, d_ln_a, d_psi, d_x)


def slots_on_rows(d_ln_a, slot_row, slot_is_row, rows, *, xp=jnp):
    """A monomial form's slopes over its free slots [M, R, P] summed onto the population's rows
    [M, K, P] (K = rows): each slot that is a row (its species at its end) adds to that row, so a
    ligand a total's form reads lands on the row it is."""
    hit = (slot_row[:, None, :] == xp.arange(rows)[None, :, None]) & slot_is_row[:, None, :]
    return xp.sum(xp.where(hit[None], d_ln_a[:, :, None, :], 0.0), axis=1)


def sign_exact_flux(log_plus, x, *, xp=jnp):
    """J = J+ (1 - exp(x)) from log J+ and x, with J's sign exactly that of -x (version 1's form,
    laws/pumps/proton_pump.py): exp(log J+ + max(x, 0)) times expm1(-x) or -expm1(x)."""
    magnitude = xp.exp(log_plus + xp.maximum(x, 0.0))
    departure = xp.where(x >= 0, xp.expm1(-x), -xp.expm1(x))
    return magnitude * departure
