"""Cycle forms: a membrane cycle law's general form (docs/CORE_SEAMS_DESIGN.md §3, §16 and §19).

Its home is the lead's ruling with the F owner (18 November 2026): a law-side module of the kinds
owner's, binding no law of its own (so the model table's scans pass it by) and importing nothing
from Cells beyond laws/ (so the surface's guard admits it). The law template's `cycle` field
(registry/laws.py) holds a CycleForm; the template checks it with the form's own errors(), and the
declarations manifest writes it under `fields`, with its changes() as the law's `changes`.

**What a cycle form is.** The data a cycle law gives the cycle kind (cells.transporter@1's
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
    every one of its Hill cycles, each with its edges' directions;
  - `net_flow`: per mode, terms J = k a sum_t w_t (1 - exp(x_t + eps_t psi)), x_t the free energy of
    the term's own stoichiometry (the fallback of §3.2; it exposes no one-way flux, D202);
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
row: Wegscheider's structural part, decided exactly in integers.
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
KINETICS = ("factored", "diagram", "net_flow")
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
    ((role, end, order), ...), each order a positive integer, and a = c/c° at the row's end."""

    k0_per_s: float
    orders: tuple = ()
    zeta: float = 0.0


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
    the population's k a), its own stoichiometry (one integer count per row) and its shift eps."""

    weight: float
    counts: tuple
    shift: float = 0.0


def _named(value):
    return isinstance(value, str) and bool(value)


def _int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


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
        }
        stray = sorted(k for k, v in given.items() if v and k != self.kinetics)
        if stray:
            out.append(f"a {self.kinetics} form gives no {', '.join(stray)} data")
        if self.kinetics == "factored":
            out += self._saturation_errors(by_name)
        elif self.kinetics == "diagram":
            out += diagram_errors(self)
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
                    and t.weight > 0
                    and isinstance(t.counts, tuple)
                    and len(t.counts) == len(self.rows)
                    and all(map(_int, t.counts))
                    and _finite(t.shift)
                ):
                    out.append(
                        f"mode {mode_id}'s flux terms are FluxTerms: a positive weight, an integer "
                        "count per row and a finite shift"
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


@lru_cache(maxsize=None)
def topology(diagram):
    """The diagram's Topology (module docstring); cached, since a diagram is a value."""
    ids = {edge.id: k for k, edge in enumerate(diagram.edges)}
    pairs = tuple((edge.source, edge.target) for edge in diagram.edges)
    n = len(diagram.states)
    trees = tuple(spanning_trees(n, pairs))
    terms = tuple(
        (root, _directed(tree, pairs, root, lambda s: s)) for tree in trees for root in range(n)
    )
    plus, minus, cut = [], [], []
    for _, signed in diagram.cycles:
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
                and _finite(rate.k0_per_s)
                and rate.k0_per_s > 0
                and _finite(rate.zeta)
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
                    "positive integer orders on the form's rows"
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
    needed only for roles whose net change is nonzero. Decided algebraically; never at a state."""
    d = form.diagram
    mode_id, counts = form.modes[mode_index]
    _, signed = d.cycles[mode_index]
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
    with localcontext() as ctx:
        ctx.prec = DIGITS
        constant, terms = Decimal(0), Decimal(0)
        for e, sign in signed:
            edge = by_id[e]
            ln_f = Decimal(edge.forward.k0_per_s).ln()
            ln_b = Decimal(edge.backward.k0_per_s).ln()
            constant += sign * (ln_f - ln_b)
            terms += abs(ln_f) + abs(ln_b)
        net = {}
        for k, (role, _) in enumerate(form.rows):
            net[role] = net.get(role, 0) + counts[k]
        ln_c0 = Decimal(c0_mM).ln()
        ln_standard = Decimal(d.standard_state_mM).ln()
        for role, delta in net.items():
            if delta == 0:
                continue
            mu = Decimal(potential[role])
            constant += delta * (mu - ln_c0 + ln_standard)
            terms += abs(delta) * (abs(mu) + abs(ln_c0) + abs(ln_standard))
        n_constants = 2 * len(signed)
        band = Decimal(WEGSCHEIDER_BAND) * Decimal(EPS) * (terms + n_constants)
    return Wegscheider(
        mode_id,
        coefficients,
        zeta - charge,
        u * zeta_abs,
        +constant,
        +terms,
        n_constants,
        +band,
    )


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
    """The tables of a diagram form (DiagramTables)."""
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


def sign_exact_flux(log_plus, x, *, xp=jnp):
    """J = J+ (1 - exp(x)) from log J+ and x, with J's sign exactly that of -x (version 1's form,
    laws/pumps/proton_pump.py): exp(log J+ + max(x, 0)) times expm1(-x) or -expm1(x)."""
    magnitude = xp.exp(log_plus + xp.maximum(x, 0.0))
    departure = xp.where(x >= 0, xp.expm1(-x), -xp.expm1(x))
    return magnitude * departure
