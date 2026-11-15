"""cells.passive_routes@1: the passive permeation law's insertion point (A5).

docs/INNER_MODEL_V4_DESIGN.md §7.4 (i), §7.5 (version 1, ruled), §11; the kernel is
processes/passive_permeation.py (law passive_neutral_permeation@1, the FR-4/FR-5 owner's), called
here and never edited.

The declaration (model key `passive_routes`), each route on one host:

    [{"id": "leak_S", "law": "passive_neutral_permeation@1", "membrane": "contact_0",
      "permeability_m_per_s": {"S": 1e-9}},
     {"id": "gap_S", "law": "passive_neutral_permeation@1", "junction": "junction_0",
      "permeability_m_per_s": {"S": 1e-9}}]

- **The flux** is the kernel's constant-field route at valence 0 (Fick), inward from the host's
  outside end (a patch's outside node, a junction's receiver) to its inside end (a patch's cell, a
  junction's sender), at every explicit stage, on the read amounts. Its opening is the host's:
  a patch's availability, or a junction's gate times its availability.
- **Version 1 carries neutral species only**, and the host route's own constant-field
  permeability for a carried species must be zero, so one law moves it there.
- **Its own fields:** `passive_transferred` [species, route] (cumulative, inward) and
  `passive_dissipated_energy_pJ` [route]; both join @3's material and energy ledgers by role.
- **The booking (§7.5, version 1):** a route whose every carried row (species, end node) is moved
  by exact-booked passive routes alone (checked at binding from moved_nodes; a held bath's row is
  never one) books, per step, its exact divided-difference share of each row's exact free-energy
  decrease: Q = -1e-3 RT moved (mu-bar_in - mu-bar_out), mu-bar the row's divided-difference
  potential over the step (the kernel's divided_potential_RT and route_heat_pJ). No clamp, no
  scaling. A step with any negative share, or a row whose shares miss its exact decrease by more
  than RAW_SUM_FACTOR eps times its terms, is refused ("negative exact share: step-bound breach").
  Every other route keeps the tableau's booking of its dissipation rate, as today's routes do.
- **Its step (ruled):** dt L <= 1, with L = 1e15 P A (1/V_a + 1/V_b) summed over the routes at
  each node (finding 3's z = 0 term for its routes), as its bound term (bound_rate).
"""

from typing import NamedTuple

import numpy as np

from cells.core.kind_registry import BUILTIN, Kind
from cells.core.specs import ConfigError
from cells.numerics.extracellular_field import scatter
from cells.numerics.species_sums import species_sum
from cells.processes import passive_permeation as passive
from cells.processes.electrochemistry import R

KIND_ID = "cells.passive_routes@1"
MODEL_KEY = "passive_routes"
LAW_ID = passive.LAW_ID
RAW_SUM_FACTOR = 16.0  # §7.5: |sum of shares - exact decrease| <= 16 eps sum|terms|, per row.
NEGATIVE_SHARE = "negative exact share: step-bound breach"
HOSTS = ("membrane", "junction")


class Route(NamedTuple):
    id: str
    host_kind: str  # "membrane" or "junction"
    host: str
    inside: str  # A patch's cell, a junction's sender.
    outside: str  # A patch's outside node, a junction's receiver.
    permeability: tuple  # ((species, P in m/s), ...), sorted by species.


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
        hosts = [h for h in HOSTS if h in raw]
        if set(raw) != {"id", "law", "permeability_m_per_s", *hosts} or len(hosts) != 1:
            raise ConfigError(
                f"{MODEL_KEY}: a route declares id, law, permeability_m_per_s and one host "
                "(membrane or junction)"
            )
        if raw["law"] != LAW_ID:
            raise ConfigError(f"{MODEL_KEY} {raw['id']}: law must be {LAW_ID}")
        kind, host = hosts[0], raw[hosts[0]]
        if kind == "membrane":
            if host not in patches:
                raise ConfigError(f"{MODEL_KEY} {raw['id']}: unknown membrane patch {host!r}")
            inside, outside = patches[host].inside, patches[host].outside
        else:
            if host not in junctions:
                raise ConfigError(f"{MODEL_KEY} {raw['id']}: unknown junction {host!r}")
            inside, outside = junctions[host].sender, junctions[host].receiver
        carried = raw["permeability_m_per_s"]
        if not isinstance(carried, dict) or not carried:
            raise ConfigError(f"{MODEL_KEY} {raw['id']}: permeability_m_per_s names its species")
        values = []
        for species, value in carried.items():
            if species not in m.species_ids:
                raise ConfigError(f"{MODEL_KEY} {raw['id']}: unknown species {species!r}")
            value = float(value)
            if not (np.isfinite(value) and value >= 0):
                raise ConfigError(f"{MODEL_KEY} {raw['id']}: a permeability is finite and >= 0")
            values.append((species, value))
        routes.append(Route(str(raw["id"]), kind, host, inside, outside, tuple(sorted(values))))
    ids = [r.id for r in routes]
    if len(set(ids)) != len(ids):
        raise ConfigError(f"{MODEL_KEY}: route IDs must be unique")
    return tuple(sorted(routes))


def to_dict(declaration):
    return [
        {
            "id": r.id,
            "law": LAW_ID,
            r.host_kind: r.host,
            "permeability_m_per_s": dict(r.permeability),
        }
        for r in declaration
    ]


def structure_entry(declaration):
    return ()  # Hosts, permeabilities and the booking mask are layout values.


def _node_ids(spec):
    m, x = spec.model, spec.execution
    nodes = [c.id for c in m.cells] + [None] * (x.capacity - len(m.cells))
    return (
        nodes
        + [o.id for o in m.extracellular]
        + [None] * (x.extracellular_capacity - len(m.extracellular))
    )


def _exact(spec, declaration):
    """Version 1's scope, per route: every carried row (species, end node) is moved by passive
    routes alone, and neither end is a held bath."""
    from cells.models.surface_pump_v3 import moved_nodes

    m = spec.model
    held = {o.id for o in m.extracellular if o.reservoir}
    movers = moved_nodes(m)
    out = []
    for route in declaration:
        ok = route.outside not in held
        for species, value in route.permeability:
            for node in (route.inside, route.outside):
                others = [w for w in movers.get((species, node), ()) if w != KIND_ID]
                ok = ok and not (value > 0 and others)
        out.append(ok)
    return np.asarray(out, dtype=bool)


def initial(spec, declaration, layout):
    m = spec.model
    ids, nodes = list(m.species_ids), _node_ids(spec)
    s, r = len(ids), len(declaration)
    membranes = [p.id for p in m.membranes]
    junctions = [j.id for j in m.junctions]
    patches = {p.id: p for p in m.membranes}
    permeability = np.zeros((s, r))
    for k, route in enumerate(declaration):
        for species, value in route.permeability:
            permeability[ids.index(species), k] = value
    on_junction = np.asarray([route.host_kind == "junction" for route in declaration], dtype=bool)
    area = np.asarray(
        [
            patches[route.host].area_m2
            if route.host_kind == "membrane"
            else next(j.area_m2 for j in m.junctions if j.id == route.host)
            for route in declaration
        ]
    )
    own = dict(
        passive_permeability=permeability,
        passive_area=area,
        passive_inside=np.asarray([nodes.index(route.inside) for route in declaration]),
        passive_outside=np.asarray([nodes.index(route.outside) for route in declaration]),
        passive_membrane=np.asarray(
            [membranes.index(r.host) if r.host_kind == "membrane" else 0 for r in declaration]
        ),
        passive_junction=np.asarray(
            [junctions.index(r.host) if r.host_kind == "junction" else 0 for r in declaration]
        ),
        passive_on_junction=on_junction,
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
    """Each route's opening: its patch's availability, or its junction's gate x availability."""
    opening = xp.ones(p.passive_area.shape)
    if control.membrane.shape[-1]:  # Static: membrane routes need a patch to exist.
        opening = control.membrane[p.passive_membrane]
    if control.junction.shape[-1]:  # Static: junction routes need a junction to exist.
        gated = control.junction * state.junction_gate
        opening = xp.where(p.passive_on_junction, gated[p.passive_junction], opening)
    return opening


def rates(state, potentials, control, p, *, xp):
    from cells.models.surface_pump_v3 import KindRates

    volume, active = _volumes(p, xp)
    c = xp.where(active, _amounts(state, p, xp) / volume, 1.0)  # mM, the read's amounts.
    c_in, c_out = c[:, p.passive_inside], c[:, p.passive_outside]
    flux = passive.flux_fmol_s(
        c_in, c_out, p.passive_area, p.passive_permeability, _opening(state, control, p, xp), xp=xp
    )  # [species, route], inward.
    n = p.active.size
    net = _net(flux, p, volume.shape[0], xp)
    log_ratio = xp.log(c_out) - xp.log(c_in)
    heat = 1e-3 * R * p.temperature * species_sum(flux * log_ratio, xp=xp)  # >= 0, pJ/s.
    outward = xp.where(p.passive_on_junction, 0.0, -flux)
    patch_flux = scatter(outward, p.membrane_permeability, (p.passive_membrane,), xp=xp)
    return KindRates(
        cell=net[:, :n],
        outside=net[:, n:],
        derivatives=dict(passive_transferred=flux, passive_dissipated_energy_pJ=heat),
        heat_pJ_s=xp.sum(heat),
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


def _booking(start, end, p, *, xp):
    volume, _ = _volumes(p, xp)
    n0, n1 = _amounts(start, p, xp), _amounts(end, p, xp)
    moved = end.passive_transferred - start.passive_transferred  # [species, route], inward.
    mu = passive.divided_potential_RT(n0, n1, volume[None, :], xp=xp)  # [species, node]
    mu_in, mu_out = mu[:, p.passive_inside], mu[:, p.passive_outside]
    shares = passive.route_heat_pJ(moved, mu_in, mu_out, p.temperature, xp=xp)
    exact = p.passive_exact[None, :] & (p.passive_permeability > 0)
    negative = xp.any(xp.where(exact, shares < 0, False))
    # Raw sums: each exact row's shares (mu-bar times every route's transfer at it) against its
    # exact change of G, within RAW_SUM_FACTOR eps of the terms' magnitudes.
    carried = xp.where(exact, moved, 0.0)
    zero = xp.zeros_like(n0)

    def at_ends(values):  # [species, route] -> [species, node], at both of each route's ends.
        inside = scatter(values, zero, (p.passive_inside,), xp=xp)
        return inside + scatter(values, zero, (p.passive_outside,), xp=xp)

    rows = at_ends(xp.where(exact, 1.0, 0.0)) > 0  # Every row an exact route touches.
    g0, g1 = _row_energy(n0, volume[None, :], xp), _row_energy(n1, volume[None, :], xp)
    summed = mu * _net(carried, p, volume.shape[0], xp)
    magnitude = (
        xp.abs(g0)
        + xp.abs(g1)
        + scatter(xp.abs(mu_in * carried), zero, (p.passive_inside,), xp=xp)
        + scatter(xp.abs(mu_out * carried), zero, (p.passive_outside,), xp=xp)
    )
    bound = RAW_SUM_FACTOR * np.finfo(float).eps * magnitude
    heat = xp.sum(xp.where(exact, shares, 0.0), axis=0)
    return heat, ~negative, xp.abs(summed - (g1 - g0)), bound, rows


def book(applied, start, end, p, dt, *, xp):
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
        for species, value in route.permeability:
            if value > 0:
                rows += [(species, route.inside, LAW_ID), (species, route.outside, LAW_ID)]
    return tuple(rows)


def bound_rate(spec, declaration):
    """dt L <= 1 (§7.4 (i)): L = 1e15 P A (1/V_a + 1/V_b) summed over the routes at each node,
    the largest over species and nodes (availability and gate at most 1)."""
    m = spec.model
    volume = {c.id: c.volume_pL for c in m.cells} | {o.id: o.volume_pL for o in m.extracellular}
    area = {p.id: p.area_m2 for p in m.membranes} | {j.id: j.area_m2 for j in m.junctions}
    totals = {}
    for route in declaration:
        both = 1.0 / volume[route.inside] + 1.0 / volume[route.outside]
        for species, value in route.permeability:
            rate = 1e15 * value * area[route.host] * both  # P A in m^3/s over V in pL (1e-15 m^3).
            for node in (route.inside, route.outside):
                totals[(species, node)] = totals.get((species, node), 0.0) + rate
    return max(totals.values(), default=0.0)


def check_definition(spec):
    """Version 1's admission: neutral species only, and the host route's own permeability for a
    carried species is zero; route IDs unique among the definition's entity IDs."""
    m = spec.model
    declaration = dict(m.kinds)[KIND_ID]
    patches = {p.id: p for p in m.membranes}
    junctions = {j.id: j for j in m.junctions}
    taken = {x.id for x in (*m.cells, *m.extracellular, *m.membranes, *m.junctions, *m.faces)}
    for route in declaration:
        if route.id in taken:
            raise ConfigError(f"{MODEL_KEY} {route.id}: the ID is already an entity's")
        host = patches[route.host] if route.host_kind == "membrane" else junctions[route.host]
        for species, value in route.permeability:
            row = m.species_ids.index(species)
            if m.valence[row] != 0:
                raise ConfigError(
                    f"{MODEL_KEY} {route.id}: version 1 carries neutral species only, not {species}"
                )
            if value > 0 and host.permeability_m_per_s[row]:
                raise ConfigError(
                    f"{MODEL_KEY} {route.id}: its {route.host_kind} {route.host} has its own "
                    f"permeability for {species}; one law moves a species on a route"
                )


PASSIVE_ROUTES = BUILTIN.register(
    Kind(
        kind_id=KIND_ID,
        model_key=MODEL_KEY,
        state_axes=(
            ("passive_transferred", ("species", "passive_route")),
            ("passive_dissipated_energy_pJ", ("passive_route",)),
        ),
        layout_fields=(
            "passive_permeability",
            "passive_area",
            "passive_inside",
            "passive_outside",
            "passive_membrane",
            "passive_junction",
            "passive_on_junction",
            "passive_exact",
        ),
        parse=parse,
        to_dict=to_dict,
        structure_entry=structure_entry,
        initial=initial,
        rates=rates,
        book=book,
        ledger_terms=ledger_terms,
        domain=domain,
        moved_rows=moved_rows,
        bound_rate=bound_rate,
        check_definition=check_definition,
    )
)
