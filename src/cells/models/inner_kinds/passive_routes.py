"""cells.passive_routes@1: the passive routes' insertion point, laws by contract (A5).

docs/INNER_MODEL_V4_DESIGN.md §7.4 (i), §7.5 (version 1, ruled), §11; the lead's scope ruling (15
November): one kind for passive routes, its laws by contract. The kernels are the FR-4/FR-5
owner's, called here and never edited:
- `passive_neutral_permeation@1` (processes/passive_permeation.py): a neutral species, Fick's law
  at valence 0, with §7.5's exact booking;
- `proton_constant_field_leak@1` (processes/proton_leak.py): an H+ constant-field route at
  valence +1 on a membrane patch, reading free h through the stage read (B4) at buffered nodes;
  tableau-booked (charged), with its slope conductance in the stage rule (B7) and its flux in the
  membrane current.

The declaration (model key `passive_routes`, FR-4's form in validation/compartment_ph_engine/
definitions.py), each route on one host (`patch`, or `junction` for the neutral law):

    [{"id": "proton_leak_0", "patch": "bounding_0", "law": "proton_constant_field_leak@1",
      "permeability_m_per_s": 6e-7},
     {"id": "cargo_0", "patch": "bounding_0", "law": "passive_neutral_permeation@1",
      "species": "X", "permeability_m_per_s": 1e-9}]

`species` is the neutral law's carried row; the leak's is the proton row (`species`, default "H",
which must be B4's proton_row when B4 is declared). `factors` is a list of factor-source IDs
(§7.4 (n): FR-5's damage d and pH condition f), in declared order; omitted or empty, none.

The kind finds its laws in the active law registry: the route laws it hosts, named as declared
(registry/laws.py; docs/CORE_SEAMS_DESIGN.md §8.3), never a module tuple. Its two laws are declared
here, on the law template, until each moves to its own module (§8.2). Version 1 runs each of the
two by name (VERSION_1_LAWS), so it refuses any other route law it hosts.

- **The routing door's sink (§7.4 (n) 6):** where any route declares factors, the kind's entry
  records it and its fields gain the control `passive_multiplier` [route], held at 1; each
  factored route's slot is routed (`routed_controls`), so at every stage it is the left fold of
  its sources' factors. Each route's opening is multiplied by it in rates and stage_term.
  Booking, its scope, bound_rate (m <= 1) and moved_rows are unchanged. A definition whose routes
  declare no factors keeps today's entry, fields and programs.

- **The flux,** inward from the host's outside end (a patch's outside node, a junction's receiver)
  to its inside end (a patch's cell, a junction's sender), at every explicit stage, on the read
  amounts; the leak at the patch voltage phi_in - phi_out. Its opening is the host's: a patch's
  availability, or a junction's gate times its availability.
- **One law per species and route:** the host route's own constant-field permeability for a
  carried species must be zero. The neutral law carries valence-0 species only; the leak a
  valence +1 row.
- **Its own fields:** `passive_transferred` [species, route] (cumulative, inward) and
  `passive_dissipated_energy_pJ` [route]; both join @3's material and energy ledgers by role.
- **The booking (§7.5, version 1):** a neutral route whose every carried row (species, end node)
  is moved by passive routes alone (binding, from moved_nodes; a held bath's row is never one)
  books, per step, its exact divided-difference shares of each row's exact free-energy decrease:
  Q = -1e-3 RT moved (mu-bar_in - mu-bar_out) (the kernel's divided_potential_RT and
  route_heat_pJ). No clamp, no scaling. A negative share, or a row whose shares miss its exact
  decrease by more than RAW_SUM_FACTOR eps times its terms and its inputs' rounding (the stored
  amounts, increments and cumulative transfers times |mu-bar|: §7.5's raw-sum bound, amended 16
  November 2026), refuses the step ("negative exact share: step-bound breach"). Every other
  route, the leak always, keeps the tableau's booking of its dissipation rate (the leak's: the
  kernel's heat_pJ_s, >= 0).
- **Its step (ruled):** the neutral law's dt L <= 1, L = 1e15 P A (1/V_a + 1/V_b) summed over
  the routes at each node, as its bound term (bound_rate); the leak's slope conductance (the
  kernel's conductance_S, max side) joins membrane_rate's per-stage refusal (stage_term).
"""

from types import MappingProxyType
from typing import NamedTuple

import numpy as np

from cells.core.kind_registry import BUILTIN, ConfigError, Kind, KindFields, KindView
from cells.numerics.extracellular_field import scatter
from cells.numerics.species_sums import entity_sum, species_sum
from cells.processes import passive_permeation as passive
from cells.processes import proton_leak as leak
from cells.processes.electrochemistry import R
from cells.registry import laws as law_registry

KIND_ID = "cells.passive_routes@1"
MODEL_KEY = "passive_routes"
LAW_ID = passive.LAW_ID  # The neutral law.
LEAK_LAW_ID = leak.LAW_ID  # The charged proton leak.
VERSION_1_LAWS = (LAW_ID, LEAK_LAW_ID)  # Version 1 runs each by name (Route.law's dispatch).
# The kind's two laws on the law template (registry/laws.py), registered for the kind to find by
# interface and host. Each moves to its own module with step 2's extraction (CORE_SEAMS §8.2).
NEUTRAL = law_registry.BUILTIN.register(
    law_registry.RouteLaw(
        LAW_ID,
        ("membrane", "junction"),
        "Fick's law: the constant-field flux at valence 0 (processes/passive_permeation.py), with "
        "the exact booking of docs/INNER_MODEL_V4_DESIGN.md §7.5",
        host=KIND_ID,
        provenance="cited",
        source=law_registry.Citation(
            "Fick's law of diffusion (A. Fick, 1855; standard theory)",
            "docs/INNER_MODEL_V4_DESIGN.md §11",
            "no numbers taken: the law is a form, its permeability a definition's value",
        ),
    )
)
LEAK = law_registry.BUILTIN.register(
    law_registry.RouteLaw(
        LEAK_LAW_ID,
        ("membrane",),
        "the Goldman-Hodgkin-Katz constant-field flux at valence +1 of free h, read through each "
        "node's closure (processes/proton_leak.py)",
        host=KIND_ID,
        provenance="cited",
        source=law_registry.Citation(
            "the Goldman-Hodgkin-Katz constant-field flux (D. E. Goldman, 1943; A. L. Hodgkin and "
            "B. Katz, 1949; standard theory)",
            "docs/COMPARTMENT_PH_TRANSFER_DESIGN.md §7.1",
            "no numbers taken: the law is a form, its permeability a definition's value",
            ("it reads free h at both nodes through their closures and moves proton equivalents",),
        ),
    )
)
DEFAULT_PROTON = "H"
RAW_SUM_FACTOR = 16.0  # §7.5: |sum of shares - exact decrease| <= 16 eps (own + inputs), per row.
NEGATIVE_SHARE = "negative exact share: step-bound breach"
HOSTS = ("patch", "junction")
MULTIPLIER = "passive_multiplier"  # The sink's control field (§7.4 (n) 6).
STATE_AXES = (
    ("passive_transferred", ("species", "passive_route")),
    ("passive_dissipated_energy_pJ", ("passive_route",)),
)
LAYOUT_FIELDS = (
    "passive_permeability",
    "passive_area",
    "passive_inside",
    "passive_outside",
    "passive_membrane",
    "passive_junction",
    "passive_on_junction",
    "passive_leak",
    "passive_exact",
)


def hosted_laws():
    """{law ID as declared: declaration} of the route laws this kind hosts, in canonical order:
    found in the active law registry by interface and host (CORE_SEAMS §8.3)."""
    laws = law_registry.active().laws(law_registry.ROUTE_LAW, KIND_ID)
    return {law.law_id: law for law in laws}


class Route(NamedTuple):
    id: str
    law: str
    host_kind: str  # "patch" or "junction"
    host: str
    inside: str  # A patch's cell, a junction's sender.
    outside: str  # A patch's outside node, a junction's receiver.
    species: str
    permeability: float  # m/s
    factors: tuple = ()  # Factor-source IDs, in declared order (§7.4 (n)).


def parse(entries, base):
    m = base.model
    if not isinstance(entries, list) or not entries:
        raise ConfigError(f"{MODEL_KEY} is a nonempty list of routes")
    patches = {p.id: p for p in m.membranes}
    junctions = {j.id: j for j in m.junctions}
    routes = []
    for raw in entries:
        if not isinstance(raw, dict):
            raise ConfigError(f"{MODEL_KEY}: each route is a mapping")
        rid = str(raw.get("id"))
        hosts = [h for h in HOSTS if h in raw]
        allowed = {"id", "law", "permeability_m_per_s", "species", "factors", *hosts}
        if not {"id", "law", "permeability_m_per_s"} <= set(raw) <= allowed or len(hosts) != 1:
            raise ConfigError(
                f"{MODEL_KEY}: a route declares id, law, permeability_m_per_s, one host (patch or "
                "junction), and species for the neutral law"
            )
        law, hosted = raw["law"], hosted_laws()
        if not isinstance(law, str) or law not in hosted:
            raise ConfigError(f"{MODEL_KEY} {rid}: law must be one of {', '.join(hosted)}")
        if law not in VERSION_1_LAWS:
            raise ConfigError(
                f"{MODEL_KEY} {rid}: version 1 runs {', '.join(VERSION_1_LAWS)}, not {law}"
            )
        factors = raw.get("factors", [])
        if (
            not isinstance(factors, list)
            or any(not isinstance(f, str) or not f for f in factors)
            or len(set(factors)) != len(factors)
        ):
            raise ConfigError(f"{MODEL_KEY} {rid}: factors is a list of distinct factor-source IDs")
        kind, host = hosts[0], raw[hosts[0]]
        if kind == "patch":
            if host not in patches:
                raise ConfigError(f"{MODEL_KEY} {rid}: unknown membrane patch {host!r}")
            inside, outside = patches[host].inside, patches[host].outside
        else:
            if law == LEAK_LAW_ID:
                raise ConfigError(f"{MODEL_KEY} {rid}: the proton leak sits on a membrane patch")
            if host not in junctions:
                raise ConfigError(f"{MODEL_KEY} {rid}: unknown junction {host!r}")
            inside, outside = junctions[host].sender, junctions[host].receiver
        species = raw.get("species", DEFAULT_PROTON if law == LEAK_LAW_ID else None)
        if species not in m.species_ids:
            raise ConfigError(f"{MODEL_KEY} {rid}: unknown species {species!r}")
        value = raw["permeability_m_per_s"]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ConfigError(f"{MODEL_KEY} {rid}: permeability_m_per_s is one number (m/s)")
        value = float(value)
        if not (np.isfinite(value) and value >= 0):
            raise ConfigError(f"{MODEL_KEY} {rid}: permeability_m_per_s is finite and >= 0")
        routes.append(Route(rid, law, kind, host, inside, outside, species, value, tuple(factors)))
    ids = [r.id for r in routes]
    if len(set(ids)) != len(ids):
        raise ConfigError(f"{MODEL_KEY}: route IDs must be unique")
    return tuple(sorted(routes))


def to_dict(declaration):
    out = []
    for r in declaration:
        entry = {
            "id": r.id,
            r.host_kind: r.host,
            "law": r.law,
            "permeability_m_per_s": r.permeability,
        }
        if r.law == LAW_ID or r.species != DEFAULT_PROTON:
            entry["species"] = r.species
        if r.factors:
            entry["factors"] = list(r.factors)
        out.append(entry)
    return out


class Factored(NamedTuple):
    """The structure entry of a declaration whose routes declare factors (§7.4 (n) 6)."""

    laws: tuple


def structure_entry(declaration):
    """Value-free: the declared laws (the leak traces its own kernel); Factored(laws) where any
    route declares factors, so today's declarations keep today's entry."""
    laws = tuple(sorted({route.law for route in declaration}))
    return Factored(laws) if any(route.factors for route in declaration) else laws


def declared_fields(entry):
    """The kind's fields for its entry (§7.4 (n) 5): the multiplier exists only where factored."""
    return KindFields(
        STATE_AXES, LAYOUT_FIELDS, (MULTIPLIER,) if isinstance(entry, Factored) else (), ()
    )


def control_values(spec, declaration, times):
    """The multiplier's held value, 1 on every route; the door routes the factored ones."""
    return {MULTIPLIER: np.ones((len(times), len(declaration)))}


def routed_controls(declaration):
    """Each factored route's multiplier slot and its sources, in declared order (§7.4 (n))."""
    return tuple(
        (MULTIPLIER, k, route.factors) for k, route in enumerate(declaration) if route.factors
    )


def _node_ids(spec):
    m, x = spec.model, spec.execution
    nodes = [c.id for c in m.cells] + [None] * (x.capacity - len(m.cells))
    return (
        nodes
        + [o.id for o in m.extracellular]
        + [None] * (x.extracellular_capacity - len(m.extracellular))
    )


def _exact(spec, declaration):
    """Version 1's scope, per route: a neutral route whose every carried row (species, end node) is
    moved by exact-booked passive routes alone, neither end a held bath; the leak never.

    A fixpoint over shared rows: a route starts as a candidate unless it is the leak, touches a
    held bath or shares a row with a non-passive mover (moved_nodes); then any candidate sharing a
    row with a passive route that is not one drops out, until nothing changes. So a route beside
    a tableau-booked passive route on one row is tableau-booked too. Operators' writers (the
    registry's moved_in_step) are the composite's admission."""
    from cells.models.surface_pump_v3 import moved_nodes

    m = spec.model
    held = {o.id for o in m.extracellular if o.reservoir}
    movers = moved_nodes(m)
    rows, candidate = {}, []
    for k, route in enumerate(declaration):
        ends = [(route.species, route.inside), (route.species, route.outside)]
        if route.permeability > 0:
            for row in ends:
                rows.setdefault(row, []).append(k)
        others = any(w != KIND_ID for row in ends for w in movers.get(row, ()))
        candidate.append(
            route.law == LAW_ID
            and route.outside not in held
            and not (route.permeability > 0 and others)
        )
    changed = True
    while changed:
        changed = False
        for k, route in enumerate(declaration):
            ends = [(route.species, route.inside), (route.species, route.outside)]
            if candidate[k] and any(not candidate[j] for row in ends for j in rows.get(row, ())):
                candidate[k], changed = False, True
    return np.asarray(candidate, dtype=bool)


def initial(spec, declaration, layout):
    m = spec.model
    ids, nodes = list(m.species_ids), _node_ids(spec)
    s, r = len(ids), len(declaration)
    membranes = [p.id for p in m.membranes]
    junctions = [j.id for j in m.junctions]
    areas = {p.id: p.area_m2 for p in m.membranes} | {j.id: j.area_m2 for j in m.junctions}
    permeability = np.zeros((s, r))
    for k, route in enumerate(declaration):
        permeability[ids.index(route.species), k] = route.permeability
    own = dict(
        passive_permeability=permeability,
        passive_area=np.asarray([areas[route.host] for route in declaration]),
        passive_inside=np.asarray([nodes.index(route.inside) for route in declaration]),
        passive_outside=np.asarray([nodes.index(route.outside) for route in declaration]),
        passive_membrane=np.asarray(
            [membranes.index(r.host) if r.host_kind == "patch" else 0 for r in declaration]
        ),
        passive_junction=np.asarray(
            [junctions.index(r.host) if r.host_kind == "junction" else 0 for r in declaration]
        ),
        passive_on_junction=np.asarray([r.host_kind == "junction" for r in declaration]),
        passive_leak=np.asarray([r.law == LEAK_LAW_ID for r in declaration]),
        passive_exact=_exact(spec, declaration),
    )
    state = dict(passive_transferred=np.zeros((s, r)), passive_dissipated_energy_pJ=np.zeros(r))
    return state, own


def _amounts(state, p, xp):
    return xp.concatenate(
        (
            p.amount_reference + state.amount_increment,
            p.extracellular_amount_reference + state.extracellular_amount_increment,
        ),
        axis=1,
    )


def _volumes(p, xp):
    volume = xp.concatenate((p.volume, p.extracellular_volume))
    active = xp.concatenate((p.active, p.outside_active))
    return xp.where(active, volume, 1.0), active


def _net(moved, p, nodes, xp):
    """[species, node] net inward change of each node from route values [species, route]."""
    zero = xp.zeros((moved.shape[0], nodes))
    into = scatter(moved, zero, (p.passive_inside,), xp=xp)
    return into - scatter(moved, zero, (p.passive_outside,), xp=xp)


def _opening(state, control, p, xp):
    """Each route's opening: its patch's availability, or its junction's gate x availability,
    times its routed multiplier where the declaration has one (§7.4 (n) 6)."""
    opening = xp.ones(p.passive_area.shape)
    if control.membrane.shape[-1]:  # Static: membrane routes need a patch to exist.
        opening = control.membrane[p.passive_membrane]
    if control.junction.shape[-1]:  # Static: junction routes need a junction to exist.
        gated = control.junction * state.junction_gate
        opening = xp.where(p.passive_on_junction, gated[p.passive_junction], opening)
    if MULTIPLIER in type(control)._fields:  # Static: a factored declaration's field.
        opening = opening * getattr(control, MULTIPLIER)
    return opening


def _ends(state, p, xp):
    """(c_in, c_out) [species, route] in mM, from the read's amounts (free h at buffered nodes)."""
    volume, active = _volumes(p, xp)
    c = xp.where(active, _amounts(state, p, xp) / volume, 1.0)
    return c[:, p.passive_inside], c[:, p.passive_outside]


def rates(state, potentials, control, p, *, xp):
    from cells.models.surface_pump_v3 import KindRates

    c_in, c_out = _ends(state, p, xp)
    opening = _opening(state, control, p, xp)
    neutral = passive.flux_fmol_s(
        c_in, c_out, p.passive_area, p.passive_permeability, opening, xp=xp
    )  # [species, route], inward.
    voltage = potentials[p.passive_inside] - potentials[p.passive_outside]  # phi_in - phi_out.
    charged = leak.flux_fmol_s(
        c_in, c_out, voltage, p.temperature, p.passive_area, p.passive_permeability, opening, xp=xp
    )
    flux = xp.where(p.passive_leak, charged, neutral)
    volume, _ = _volumes(p, xp)
    n = p.active.size
    net = _net(flux, p, volume.shape[0], xp)
    log_ratio = xp.log(c_out) - xp.log(c_in)
    fick = 1e-3 * R * p.temperature * species_sum(flux * log_ratio, xp=xp)
    ghk = species_sum(leak.heat_pJ_s(flux, c_in, c_out, voltage, p.temperature, xp=xp), xp=xp)
    heat = xp.where(p.passive_leak, ghk, fick)  # >= 0, pJ/s per route.
    outward = xp.where(p.passive_on_junction, 0.0, -flux)
    patch_flux = scatter(outward, p.membrane_permeability, (p.passive_membrane,), xp=xp)
    return KindRates(
        cell=net[:, :n],
        outside=net[:, n:],
        derivatives=dict(passive_transferred=flux, passive_dissipated_energy_pJ=heat),
        heat_pJ_s=entity_sum(heat, axis=None, xp=xp),  # Over routes.
        work_pJ_s=xp.zeros(()),
        membrane_flux=patch_flux,
    )


def _row_energy(n, volume, xp):
    """G = n (ln(n/V) - 1) per row (RT units, fmol), n ln n -> 0 at n = 0."""
    safe = xp.where(n > 0, n, 1.0)
    return xp.where(n > 0, n * (xp.log(safe / volume) - 1.0), 0.0)


def exact_booking(start, end, p, *, xp):
    """§7.5 version 1's booking over one step: (heat per route [route] in pJ, no negative share,
    every exact row's raw sum within its rounding bound). Exact routes only; the caller keeps the
    tableau's heat on the others."""
    heat, positive, residual, bound, rows = _booking(start, end, p, xp=xp)
    return heat, positive, xp.all(xp.where(rows, residual <= bound, True))


def raw_sum_check(start, end, p, *, xp=np):
    """(|sum of shares - exact decrease| per row, its bound, the exact rows) over one step: the
    raw-sum check's terms, for its factor's test (§7.5: confirmed at implementation)."""
    _, _, residual, bound, rows = _booking(start, end, p, xp=xp)
    return residual, bound, rows


def raw_sum_terms(start, end, p, *, xp=np):
    """(residual, own, inputs, rows) over one step: the bound's two magnitudes apart, the row's own
    terms and its inputs' rounding (§7.5, the raw-sum bound); bound = RAW_SUM_FACTOR eps (own +
    inputs). For the bound's tests and probes."""
    _, _, residual, own, inputs, rows = _raw_sums(start, end, p, xp=xp)
    return residual, own, inputs, rows


def _increments(state, xp):
    """[species, node] stored increments, cells then outside nodes (_amounts less its reference)."""
    return xp.concatenate((state.amount_increment, state.extracellular_amount_increment), axis=1)


def _booking(start, end, p, *, xp):
    heat, positive, residual, own, inputs, rows = _raw_sums(start, end, p, xp=xp)
    bound = RAW_SUM_FACTOR * np.finfo(float).eps * (own + inputs)
    return heat, positive, residual, bound, rows


def _raw_sums(start, end, p, *, xp):
    volume, _ = _volumes(p, xp)
    n0, n1 = _amounts(start, p, xp), _amounts(end, p, xp)
    moved = end.passive_transferred - start.passive_transferred  # [species, route], inward.
    mu = passive.divided_potential_RT(n0, n1, volume[None, :], xp=xp)  # [species, node]
    mu_in, mu_out = mu[:, p.passive_inside], mu[:, p.passive_outside]
    shares = passive.route_heat_pJ(moved, mu_in, mu_out, p.temperature, xp=xp)
    exact = p.passive_exact[None, :] & (p.passive_permeability > 0)
    negative = xp.any(xp.where(exact, shares < 0, False))
    # Raw sums: each exact row's shares (mu-bar times every route's transfer at it) against its
    # exact change of G, within RAW_SUM_FACTOR eps of the terms' magnitudes (§7.5's bound).
    carried = xp.where(exact, moved, 0.0)
    zero = xp.zeros_like(n0)

    def at_ends(values):  # [species, route] -> [species, node], at both of each route's ends.
        inside = scatter(values, zero, (p.passive_inside,), xp=xp)
        return inside + scatter(values, zero, (p.passive_outside,), xp=xp)

    rows = at_ends(xp.where(exact, 1.0, 0.0)) > 0  # Every row an exact route touches.
    g0, g1 = _row_energy(n0, volume[None, :], xp), _row_energy(n1, volume[None, :], xp)
    summed = mu * _net(carried, p, volume.shape[0], xp)
    own = (  # The row's own terms: its G at both ends and its shares' products.
        xp.abs(g0)
        + xp.abs(g1)
        + scatter(xp.abs(mu_in * carried), zero, (p.passive_inside,), xp=xp)
        + scatter(xp.abs(mu_out * carried), zero, (p.passive_outside,), xp=xp)
    )
    # Its inputs' rounding (§7.5, the raw-sum bound): the stored amounts are reference +
    # increment, rounded to the result, and each tableau term adds onto the increments and onto
    # the exact routes' cumulative transfers (_combine), rounded to the running sum. The recorded
    # net transfer and n1 - n0 therefore differ by about eps times these magnitudes, and the
    # shares carry |mu-bar| times that difference.
    cumulative = xp.abs(start.passive_transferred) + xp.abs(end.passive_transferred)
    inputs = xp.abs(mu) * (
        xp.abs(n0)
        + xp.abs(n1)
        + xp.abs(_increments(start, xp))
        + xp.abs(_increments(end, xp))
        + at_ends(xp.where(exact, cumulative, 0.0))
    )
    heat = species_sum(xp.where(exact, shares, 0.0), xp=xp)  # A7: the species fold.
    return heat, ~negative, xp.abs(summed - (g1 - g0)), own, inputs, rows


def book(applied, start, end, control, p, dt, *, xp):
    """§7.5: exact routes book their exact shares; the others keep the tableau's heat."""
    heat, positive, within = exact_booking(start, end, p, xp=xp)
    booked = xp.where(
        p.passive_exact,
        start.passive_dissipated_energy_pJ + heat,
        end.passive_dissipated_energy_pJ,
    )
    return dict(passive_dissipated_energy_pJ=booked), positive & within


def ledger_terms(state, p, *, xp):
    n = p.active.size
    volume, _ = _volumes(p, xp)
    net = _net(state.passive_transferred, p, volume.shape[0], xp)
    return dict(cell=net[:, :n], outside=net[:, n:], heat_pJ=state.passive_dissipated_energy_pJ)


def domain(state, p, *, xp):
    moved, heat = state.passive_transferred, state.passive_dissipated_energy_pJ
    return xp.all(xp.isfinite(moved)) & xp.all(xp.isfinite(heat))


def moved_rows(declaration):
    rows = []
    for route in declaration:
        if route.permeability > 0:
            rows += [
                (route.species, route.inside, route.law),
                (route.species, route.outside, route.law),
            ]
    return tuple(rows)


def stage_term(read, potentials, control, p, *, xp):
    """B7 for the leak (gap 5): each leak route's max-side slope conductance (the kernel's
    conductance_S, S) at both of its patch's ends (cells, then outside nodes), for membrane_rate's
    per-stage refusal at every node; at the stage's patch voltage when the potentials are given
    (the max-side slope does not depend on it)."""
    c_in, c_out = _ends(read, p, xp)
    opening = _opening(read, control, p, xp)
    voltage = 0.0
    if potentials is not None:
        voltage = potentials[p.passive_inside] - potentials[p.passive_outside]
    slope = leak.conductance_S(
        c_in, c_out, voltage, p.temperature, p.passive_area, p.passive_permeability, opening, xp=xp
    )  # [species, route]; nonzero at each route's own row.
    per_route = xp.where(p.passive_leak, species_sum(slope, xp=xp), 0.0)
    nodes = xp.zeros(p.active.size + p.outside_active.size)  # Cells, then outside nodes.
    inside = scatter(per_route, nodes, (p.passive_inside,), xp=xp)
    return inside + scatter(per_route, nodes, (p.passive_outside,), xp=xp)


def bound_rate(spec, declaration):
    """The neutral law's dt L <= 1 (§7.4 (i)): L = 1e15 P A (1/V_a + 1/V_b) summed over the routes
    at each node, the largest over species and nodes (availability and gate at most 1)."""
    m = spec.model
    volume = {c.id: c.volume_pL for c in m.cells} | {o.id: o.volume_pL for o in m.extracellular}
    area = {p.id: p.area_m2 for p in m.membranes} | {j.id: j.area_m2 for j in m.junctions}
    totals = {}
    for route in declaration:
        if route.law != LAW_ID:
            continue
        both = 1.0 / volume[route.inside] + 1.0 / volume[route.outside]
        rate = 1e15 * route.permeability * area[route.host] * both  # P A (m^3/s) over V (pL).
        for node in (route.inside, route.outside):
            totals[(route.species, node)] = totals.get((route.species, node), 0.0) + rate
    return max(totals.values(), default=0.0)


def check_definition(spec):
    """Admission: the neutral law carries a valence-0 row, the leak a valence +1 row (B4's proton
    row where B4 is declared); the host route's own permeability for the carried row is zero;
    route IDs are unique among the definition's entity IDs."""
    m = spec.model
    kinds = dict(m.kinds)
    declaration = kinds[KIND_ID]
    patches = {p.id: p for p in m.membranes}
    junctions = {j.id: j for j in m.junctions}
    taken = {x.id for x in (*m.cells, *m.extracellular, *m.membranes, *m.junctions, *m.faces)}
    closure = kinds.get("cells.rapid_proton_buffer@1")
    for route in declaration:
        if route.id in taken:
            raise ConfigError(f"{MODEL_KEY} {route.id}: the ID is already an entity's")
        host = patches[route.host] if route.host_kind == "patch" else junctions[route.host]
        row = m.species_ids.index(route.species)
        if route.law == LAW_ID and m.valence[row] != 0:
            raise ConfigError(
                f"{MODEL_KEY} {route.id}: {LAW_ID} carries neutral species only, not "
                f"{route.species}"
            )
        if route.law == LEAK_LAW_ID:
            if m.valence[row] != leak.VALENCE:
                raise ConfigError(
                    f"{MODEL_KEY} {route.id}: {LEAK_LAW_ID} carries a valence +1 proton row"
                )
            if closure is not None and closure.proton != route.species:
                raise ConfigError(
                    f"{MODEL_KEY} {route.id}: the leak's row {route.species} is not the closure's "
                    f"proton row {closure.proton}"
                )
        if route.permeability > 0 and host.permeability_m_per_s[row]:
            raise ConfigError(
                f"{MODEL_KEY} {route.id}: its {route.host_kind} {route.host} has its own "
                f"permeability for {route.species}; one law moves a species on a route"
            )


# The run view's declarations (D154): the routes' own set (axis passive_route), with each route's
# ends as roles, its carried species, law and host; transfers are inward-positive (rates: `flux`).
VIEW = KindView(
    units=MappingProxyType({"passive_transferred": "fmol", "passive_dissipated_energy_pJ": "pJ"}),
    record_kinds=MappingProxyType(
        {"passive_transferred": "cumulative", "passive_dissipated_energy_pJ": "cumulative"}
    ),
    orientation=MappingProxyType(
        {
            "passive_transferred": MappingProxyType(
                {
                    "from": "outside",
                    "to": "inside",
                    "says": "inward-positive: a positive amount moves from the route's outside "
                    "end (its patch's outside node, or its junction's receiver) into its inside "
                    "end (its patch's cell, or its junction's sender)",
                    "confirmed": "the core's owner, from the code (core-next, 16 November 2026)",
                }
            )
        }
    ),
    record_layers=MappingProxyType(
        {"passive_transferred": "membrane", "passive_dissipated_energy_pJ": "membrane"}
    ),
)


def view_sets(spec, declaration):
    """The view's set of the routes' axis: one entry per route, in the declaration's order."""
    return {
        "passive_route": {
            "id": "passive_route",
            "ids": [route.id for route in declaration],
            "roles": {
                "inside": "the route's inside end: its patch's cell, or its junction's sender",
                "outside": "its outside end: its patch's outside node, or its junction's receiver",
            },
            "carries": [[route.species] for route in declaration],
            "kinds": [route.law for route in declaration],
            "at": [
                {"membrane" if route.host_kind == "patch" else "junction": route.host}
                for route in declaration
            ],
        }
    }


PASSIVE_ROUTES = BUILTIN.register(
    Kind(
        kind_id=KIND_ID,
        model_key=MODEL_KEY,
        state_axes=STATE_AXES,
        layout_fields=LAYOUT_FIELDS,
        parse=parse,
        to_dict=to_dict,
        structure_entry=structure_entry,
        initial=initial,
        rates=rates,
        stage_term=stage_term,
        book=book,
        ledger_terms=ledger_terms,
        domain=domain,
        moved_rows=moved_rows,
        bound_rate=bound_rate,
        check_definition=check_definition,
        declared_fields=declared_fields,
        control_values=control_values,
        routed_controls=routed_controls,
        view=VIEW,
        view_sets=view_sets,
    )
)
