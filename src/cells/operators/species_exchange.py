"""Operator cells.operator.scheduled_species_exchange@1: secretion and uptake of neutral species across patches.

docs/SECRETED_SPECIES_TRANSPORT_DESIGN.md §2.3 and §2.5 (D150, version 1). A secreted species is
one more row of @3's species axis (valence 0, zero membrane permeability), which @3 owns. This
operator moves it across a membrane patch between the patch's cell and its outside node, booked in
its own accumulators: no @3 route, no membrane-process hook (one per composition, heat >= 0 only).

Declaration: the species it acts on, with their identity (species_common.parse_species), and
routes, each a species, a patch (its cell and outside node are the two sides; a patch on a held
bath is refused: secretion into a held bath is clearance, its composition is held), a direction,
export (secretion, cell to node) or import (uptake, node to cell), and a rate law:

* flux, export: a scheduled J (fmol/s) from the cell's pool; moved = J h, refused if the pool
  would not stay positive (no clipping);
* first_order, export: k_e n_c (1/s), constitutive export of the pool;
  moved = n_c (1 - e^{-k_e h});
* first_order, import: k_u A c_o, with k_u an uptake velocity (m/s) and A the declared patch area;
  moved = n_o (1 - e^{-kappa h}), kappa = k_u A / V_o;
* saturable, import: A V_max c_o / (K_M + c_o), V_max in fmol s^-1 m^-2 and K_M in mM; n_o' solves
  b ln(n_o/n_o') + (n_o - n_o') = a h, with a = A V_max and b = K_M V_o.

Uptake is a plain sink (the lead's option (a), §2.5): no site state, no binding; the occupancy
primitive replaces it as a new law ID. The saturable solve is Newton in u = ln(n_o'/n_o) on
H(u) = -b u - n_o expm1(u) - a h, which is concave and decreasing: from the first-order step at c_o,
u0 = -a h / (b + n_o) (where H <= 0), every iterate stays at or right of the root and decreases to
it, so n_o' = n_o e^u > 0 always. A fixed number of steps, with the residual checked; a failed solve
refuses the step.

Schedule `exchange_controls`: per route and carrier, the rate (J, k_e, k_u or V_max) and, for a
saturable route, K_M, changing at exact multiples of dt: per-world control data. Every route's rate
and law parameters belong to its cell's carrier and follow it (the occupant rule, species_common):
founders' schedules from time 0, a template newcomer's from its template, a donor copy only when its
route values equal the slot's.

Combining routes, applied within each half-step h as a palindrome of exact stages,
    E1(h/2) E2(h/2) I1(h/2) S_1(h/2) ... S_m(h) ... S_1(h/2) I1(h/2) E2(h/2) E1(h/2),
so the splitting between non-commuting routes (secretion into a node that another route takes up
from, say) is second order: E1 the first-order exports, combined exactly per source cell (shared by
rate); E2 the flux exports; I1 the first-order imports, combined exactly per source node; S_j the
saturable imports of rank j (routes leaving one node in declared order, one rank each). Within a
stage the routes leave distinct sources. This canonical order replaces the design's "declared order"
(§2.3), a departure for the lead to rule on (hand-back 1). Each stage's moved amounts are applied to
@3's stored increments, never as n' - reference.

Energy: each stage books the exact free-energy change of the nodes it touched, from the moved
amounts (adapter.species_chemical_free_energy_pJ, @3's own term per species row), as signed work
shared among its routes by the amounts they moved at each node; no heat (a first-order law can run
uphill in the 1 mM reference convention). The magnitudes are the moved amounts and the absolute
terms of each booked change.

Energy guards. Under the IMEX solvers the shared energy bound is set by the ions' flows and is blind
to these bookings at µM–nM (bound/change 1.7 to 1,721 in a probed mixed world); the species-only
world and a NumPy ΔG test per law are the guards of record. Guard worlds start the species from a
pre-formed profile, the cell pool and the nodes around a secreting cell included; a ramped source is
not admissible until a probe measures it. In a mixed world the onset energy booking of a switch-on
from the trace is a few percent off and passes unseen under the ions' bound, a known limit (§2.6).
RK4 is guarded, not refused: exact half-steps around @3's RK4 step ("split").

The patch area is a current read (D191; the lead's ruling of 20 November 2026, for FR-7's U2 world
with a releasing compartment): SCOPED_READS declares membrane_area current at stage split, so where
an operator of the composition changes it (cells.operator.membrane_entity_state@1 provides it), each half-step's
imports take the area of the view it receives, the route's patch found on device as the one
declared patch that joins the route's cell to its outside node (route_areas). A second declared
patch joining that pair is then refused at the definition (check_area_reads), since the lookup
could not tell the two apart. Where no operator changes the area, the composite passes no view
(C1's fallback) and the half-step reads the declared area bound at the definition, so those worlds
keep their programs bit for bit (D148). With membrane state and no writer of its areas, the view's
area is the declared area plus a zero increment: the declared area, bit for bit. The law's ID is
kept (D191).

Refusals. At the definition: a charged species, a patch on a held bath, an import with a flux law,
a saturable export, a negative rate, K_M <= 0, a schedule change off the dt grid, more than 1,024
species per world (FR-43 / D315), an occupant without its rates, a donor copy whose route values
differ from the slot's, a second patch joining a route's cell and outside node where a provider of
the areas is composed (above), and every provider or closer of the volumes and the activity masks
(CONFLICTS_VIEW: version 1 reads the declared volumes, so water, the lumens, insertion and S5's
operators are refused). At run time: a supply shortfall, a failed saturable solve, non-finite values
and any written amount that would not stay positive; each half-step returns the finiteness and
positivity of both amounts it wrote, and the operator's own domain re-checks its species rows. The
stationary analysis does not admit the composite, and version 1 keeps it so (§8).

Resolution near depletion. Amounts are stored as an anchor (the declared amount) plus an increment,
so a pool's representable remainders are the anchor's grid: about 1.11e-16 fmol apart for a 1 fmol
anchor. The stored remainder is the grid point nearest the exact one (from 1 fmol to e^-35 fmol it
stores 6.661e-16 fmol for 6.305e-16, 5.65% high), and a remainder below half a spacing rounds to 0
and is refused at run time: the step fails closed. Conservation holds to rounding. Forming the
remainder another way cannot change this, since it is stored on the same grid; a finer resolution
needs a representation change, such as re-anchoring a depleted pool or a scale per node, which is
@3's state layout (the independent Lean project's finding, lean/PROGRESS.md, 20 November 2026).

Idle: no route, statically idle; no positive rate in a half-step, the start state is selected;
untouched entries are selected, never offset by zero. The face diffusivity that carries the species
between nodes is the effective (FRAP) kind (§6).

Labels (FR-42's stage 3, D289; operators/species_labels.py): a reporter. Given labels (rows,
arrival), the half-step also returns its one-way moves for the labelled rows (one_way_moves):
each route's amount moved over the palindrome, summed stage by stage, as a transfer from its
source to its destination (an export from the cell to the node, an import back), which carries
the source's shares. The physics is unchanged: the labelled call's state is bit for bit the
unlabelled one's, and without labels nothing of it is traced.
"""

from collections import Counter
from dataclasses import dataclass

import jax.numpy as jnp
import numpy as np

from cells.definitions import pump_composite_spec as composite_spec
from cells.definitions.spec_values import identifier
from cells.definitions.specs import ConfigError, _fields
from cells.models import pump_composite_adapter as adapter
from cells.numerics.species_sums import entity_sum
from cells.operators import species_common as common
from cells.operators.contract import Operator, Read
from cells.operators.species_turnover import scatter_add, set_rows

LAW_ID = "cells.operator.scheduled_species_exchange@1"
# FR-15 S1: exchange stays neutral. A charged scheduled flux is electrogenic transport, which needs
# its electrical work and a place in the membrane current; no consumer asks for it.
CHARGED_LIMIT = (
    ": a charged scheduled flux is electrogenic transport, which version 1 does not book (its "
    "electrical work and its place in the membrane current); charged permeation goes through the "
    "passive-routes kind's constant-field law (FR-15)"
)
STEP_ID = "palindromic_exact_exchange_stages@1"
DIRECTIONS = ("export", "import")
LAWS = ("flux", "first_order", "saturable")
# Route law codes (the stage each route belongs to).
FLUX_EXPORT, FIRST_ORDER_EXPORT, FIRST_ORDER_IMPORT, SATURABLE_IMPORT = range(4)
CODES = {
    ("export", "flux"): FLUX_EXPORT,
    ("export", "first_order"): FIRST_ORDER_EXPORT,
    ("import", "first_order"): FIRST_ORDER_IMPORT,
    ("import", "saturable"): SATURABLE_IMPORT,
}
NEWTON_STEPS = 8
NEWTON_RTOL = 1e-12  # |H(u)| against the absolute terms of H.
PL_PER_M3 = 1e15

STATE_AXES = {
    "exchange_moved_fmol": ["exchange_route"],  # Export positive.
    "exchange_work_pJ": ["exchange_route"],
    "exchange_energy_magnitude_pJ": ["exchange_route"],
}
LAYOUT_FIELDS = (
    "exchange_rows",  # [species rows] int64: the species it acts on, in declared order.
    "exchange_route_row",  # [route] int64: the route's position in exchange_rows.
    "exchange_route_species",  # [route] int64: its species' index on @3's species axis.
    "exchange_route_cell",  # [route] int64: its patch's cell.
    "exchange_route_outside",  # [route] int64: its patch's outside node.
    "exchange_route_code",  # [route] int64: FLUX_EXPORT ... SATURABLE_IMPORT.
    "exchange_route_rank",  # [route] int64: a saturable route's rank among those leaving its node.
    "exchange_route_area_m2",  # [route]: its patch's declared area.
    "exchange_saturable_ranks",  # [ranks]: its shape is the number of saturable ranks (static).
)


@dataclass(frozen=True)
class Route:
    id: str
    species: str
    patch: str
    direction: str
    law: str
    cell: str  # The patch's cell: every exchange route is keyed by its carrier.
    outside: str


@dataclass(frozen=True)
class Exchange:
    law: str
    species: tuple
    routes: tuple
    templates: tuple


def _rate(value, what):
    if type(value) not in (int, float) or not np.isfinite(value) or value < 0:
        raise ConfigError(f"{LAW_ID}: {what} is a finite rate >= 0")
    return float(value)


def _values(route, raw, what):
    """(rate, K_M) of one schedule change or template rate (K_M 0.0 unless saturable)."""
    keys = {"rate", "saturation_mM"} if route.law == "saturable" else {"rate"}
    extra = {"time"} if "time" in raw else set()
    _fields(raw, keys | extra, what)
    rate = _rate(raw["rate"], f"the rate of route {route.id}")
    if route.law != "saturable":
        return (rate, 0.0)
    km = raw["saturation_mM"]
    if type(km) not in (int, float) or not np.isfinite(km) or km <= 0:
        raise ConfigError(f"{LAW_ID}: K_M of route {route.id} is a finite concentration > 0 (mM)")
    return (rate, float(km))


def parse_exchange(raw, base):
    _fields(raw, {"law", "species", "routes", "templates"}, "species exchange")
    if raw["law"] != LAW_ID:
        raise ConfigError("Species exchange requires law " + LAW_ID)
    species = common.parse_species(raw["species"], base, LAW_ID, limit=CHARGED_LIMIT)
    listed = {s.id for s in species}
    m = base.model
    patches = {p.id: p for p in m.membranes}
    outside = {c.id: c for c in m.extracellular}
    if type(raw["routes"]) is not list:
        raise ConfigError(f"{LAW_ID} routes require an explicit list")
    routes = []
    for entry in raw["routes"]:
        _fields(entry, {"id", "species", "patch", "direction", "law"}, "species exchange route")
        name, species_id, patch = identifier(entry["id"]), entry["species"], entry["patch"]
        direction, law = entry["direction"], entry["law"]
        if species_id not in listed:
            raise ConfigError(
                f"{LAW_ID}: route {name} acts on {species_id!r}, not a listed species"
            )
        if patch not in patches:
            raise ConfigError(f"{LAW_ID}: route {name} is on an undeclared patch {patch!r}")
        if direction not in DIRECTIONS or law not in LAWS:
            raise ConfigError(
                f"{LAW_ID}: a route's direction is one of {', '.join(DIRECTIONS)} and its law one "
                f"of {', '.join(LAWS)}"
            )
        if (direction, law) not in CODES:
            raise ConfigError(
                f"{LAW_ID}: route {name}: an import law is first_order or saturable, never a flux; "
                "an export law is flux or first_order"
            )
        node = patches[patch].outside
        if outside[node].reservoir:
            raise ConfigError(
                f"{LAW_ID}: route {name}'s patch {patch} faces a held bath ({node}), whose "
                "composition is held: secretion into a held bath is clearance"
            )
        routes.append(Route(name, species_id, patch, direction, law, patches[patch].inside, node))
    if len({r.id for r in routes}) != len(routes):
        raise ConfigError(f"{LAW_ID}: route IDs are unique")
    templates = common.parse_templates(
        raw["templates"],
        routes,
        LAW_ID,
        lambda route, v: (
            _values(route, v, f"template rate of {route.id}")
            if isinstance(v, dict)
            else _values(route, {"rate": v}, "template rate")
        ),
    )
    return Exchange(LAW_ID, species, tuple(routes), templates)


def _value_dict(route, values):
    rate, km = values
    return dict(rate=rate) if route.law != "saturable" else dict(rate=rate, saturation_mM=km)


def exchange_to_dict(declaration):
    if type(declaration) is not Exchange or any(type(r) is not Route for r in declaration.routes):
        raise ConfigError("Require explicit immutable species exchange declaration types")
    by_id = {r.id: r for r in declaration.routes}
    return dict(
        law=declaration.law,
        species=common.species_to_dict(declaration.species),
        routes=[
            dict(id=r.id, species=r.species, patch=r.patch, direction=r.direction, law=r.law)
            for r in declaration.routes
        ],
        templates=[
            dict(
                template_id=t.template_id,
                rates={k: _value_dict(by_id[k], v) for k, v in t.rates},
            )
            for t in declaration.templates
        ],
    )


def parse_controls(raw, base, declaration):
    return common.parse_schedules(
        raw["exchange_controls"],
        base,
        declaration.routes,
        LAW_ID,
        "exchange_controls",
        lambda route, change: _values(route, change, f"{LAW_ID} schedule change"),
    )


def ranks(routes):
    """Each saturable route's rank among the saturable routes leaving its node (declared order)."""
    seen, out = {}, []
    for r in routes:
        if r.law == "saturable":
            key = (r.species, r.outside)
            out.append(seen.get(key, 0))
            seen[key] = seen.get(key, 0) + 1
        else:
            out.append(0)
    return out, max(seen.values(), default=0)


def bind(spec, declaration):
    m = spec.model
    species = list(m.species_ids)
    rows = [s.id for s in declaration.species]
    cells = [c.id for c in m.cells]
    outside = [c.id for c in m.extracellular]
    area = {p.id: p.area_m2 for p in m.membranes}
    routes = declaration.routes
    rank, count = ranks(routes)
    layout = dict(
        exchange_rows=np.asarray([species.index(s) for s in rows], dtype=np.int64),
        exchange_route_row=np.asarray([rows.index(r.species) for r in routes], dtype=np.int64),
        exchange_route_species=np.asarray(
            [species.index(r.species) for r in routes], dtype=np.int64
        ),
        exchange_route_cell=np.asarray([cells.index(r.cell) for r in routes], dtype=np.int64),
        exchange_route_outside=np.asarray(
            [outside.index(r.outside) for r in routes], dtype=np.int64
        ),
        exchange_route_code=np.asarray(
            [CODES[(r.direction, r.law)] for r in routes], dtype=np.int64
        ),
        exchange_route_rank=np.asarray(rank, dtype=np.int64),
        exchange_route_area_m2=np.asarray([area[r.patch] for r in routes], dtype=np.float64),
        exchange_saturable_ranks=np.zeros(count),
    )
    state = {k: np.zeros(len(routes)) for k in STATE_AXES}
    return state, layout


# ------------------------------------------------------------------ the law


def saturable_removed(n, a, b, h, *, xp):
    """(removed amount, converged) of saturable uptake over h from a pool n (module docstring)."""
    ah = a * h
    u = -ah / (b + n)  # The first-order step at c_o.
    for _ in range(NEWTON_STEPS):
        e = xp.expm1(u)
        u = u + (-b * u - n * e - ah) / (b + n * (1.0 + e))
    e = xp.expm1(u)
    residual = -b * u - n * e - ah
    scale = b * xp.abs(u) + n * xp.abs(e) + ah
    return -n * e, xp.abs(residual) <= NEWTON_RTOL * scale


def route_areas(membrane_area, p, *, xp):
    """Each route's patch area from `membrane_area`, the current area per membrane slot of the view
    a half-step receives (D191's current read): the one declared patch that joins the route's cell
    to its outside node, which check_area_reads makes unique wherever a provider of the areas is
    composed. A gather of the view's own values, so a zero increment gives the declared area."""
    joins = (
        p.membrane_active[None, :]
        & (p.membrane_cell[None, :] == p.exchange_route_cell[:, None])
        & (p.membrane_outside[None, :] == p.exchange_route_outside[:, None])
    )
    return membrane_area[xp.argmax(joins, axis=1)]


def _stage(inc_c, inc_o, acc, which, h, control, p, area, *, xp, track=False):
    """One exact stage over h on the operator's rows: (inc_c, inc_o, acc, valid); with track
    (FR-42, static) also each route's moved amount, >= 0.

    which: FIRST_ORDER_EXPORT, FLUX_EXPORT, FIRST_ORDER_IMPORT or (SATURABLE_IMPORT, rank).
    acc: the per-route (moved, work, magnitude) accumulators. area: each route's patch area, the
    declared one bound at the definition or the view's current one (route_areas)."""
    rows = p.exchange_rows
    k, n, o = rows.shape[0], p.active.size, p.outside_active.size
    row, cell, node = p.exchange_route_row, p.exchange_route_cell, p.exchange_route_outside
    code, rate = p.exchange_route_code, control.exchange_rate
    finite = p.outside_active & ~p.reservoir
    t = p.temperature
    nc = xp.where(p.active[None, :], p.amount_reference[rows] + inc_c, 1.0)
    no = xp.where(finite[None, :], p.extracellular_amount_reference[rows] + inc_o, 1.0)
    volume = p.extracellular_volume[node]
    valid = xp.asarray(True)
    if which == FIRST_ORDER_EXPORT or which == FIRST_ORDER_IMPORT:
        mask = code == which
        if which == FIRST_ORDER_EXPORT:
            k_r = xp.where(mask, rate, 0.0)
            source, index, size = nc, cell, n
        else:
            k_r = xp.where(mask, rate * area * PL_PER_M3 / volume, 0.0)
            source, index, size = no, node, o
        total = scatter_add(xp.zeros((k, size)), (row, index), k_r, xp=xp)[row, index]
        removed = source[row, index] * -xp.expm1(-total * h)
        moved = xp.where(mask & (total > 0), k_r / xp.where(total > 0, total, 1.0) * removed, 0.0)
    elif which == FLUX_EXPORT:
        mask = code == FLUX_EXPORT
        moved = xp.where(mask, rate * h, 0.0)
    else:
        mask = (code == SATURABLE_IMPORT) & (p.exchange_route_rank == which[1])
        a = xp.where(mask, rate * area, 0.0)
        b = xp.where(mask, control.exchange_saturation_mM * volume, 1.0)
        removed, converged = saturable_removed(no[row, node], a, b, h, xp=xp)
        valid &= xp.all(xp.where(mask & (a > 0), converged, True))
        moved = xp.where(mask, removed, 0.0)
    export = code < FIRST_ORDER_IMPORT
    active = moved > 0
    leaving = xp.where(export, moved, -moved)  # Out of the cell: export positive.
    dc = scatter_add(xp.zeros((k, n)), (row, cell), -leaving, xp=xp)
    do = scatter_add(xp.zeros((k, o)), (row, node), leaving, xp=xp)
    weight_c = scatter_add(xp.zeros((k, n)), (row, cell), moved, xp=xp)
    weight_o = scatter_add(xp.zeros((k, o)), (row, node), moved, xp=xp)
    touched_c, touched_o = weight_c > 0, weight_o > 0
    new_c = xp.where(touched_c, inc_c + dc, inc_c)
    new_o = xp.where(touched_o, inc_o + do, inc_o)
    after_c = p.amount_reference[rows] + new_c
    after_o = p.extracellular_amount_reference[rows] + new_o
    valid &= xp.all(xp.where(touched_c, xp.isfinite(after_c) & (after_c > 0), True))
    valid &= xp.all(xp.where(touched_o, xp.isfinite(after_o) & (after_o > 0), True))
    change_c, change_o = xp.where(touched_c, dc, 0.0), xp.where(touched_o, do, 0.0)
    vc, vo = p.volume, p.extracellular_volume
    g_c = adapter.species_chemical_free_energy_pJ(nc, change_c, vc, t, xp=xp)
    g_o = adapter.species_chemical_free_energy_pJ(no, change_o, vo, t, xp=xp)
    m_c = adapter.species_chemical_magnitude_pJ(nc, change_c, vc, t, xp=xp)
    m_o = adapter.species_chemical_magnitude_pJ(no, change_o, vo, t, xp=xp)
    # Each node's change shared among the stage's routes by the amounts they moved there.
    share_c = moved / xp.where(touched_c, weight_c, 1.0)[row, cell]
    share_o = moved / xp.where(touched_o, weight_o, 1.0)[row, node]
    work = g_c[row, cell] * share_c + g_o[row, node] * share_o
    magnitude = m_c[row, cell] * share_c + m_o[row, node] * share_o
    moved_acc, work_acc, magnitude_acc = acc
    acc = (
        xp.where(active, moved_acc + leaving, moved_acc),
        xp.where(active, work_acc + work, work_acc),
        xp.where(active, magnitude_acc + magnitude, magnitude_acc),
    )
    if track:
        return new_c, new_o, acc, valid, moved
    return new_c, new_o, acc, valid


def stages(p):
    """The palindrome's stage sequence (static: the rank count is a layout shape)."""
    count = p.exchange_saturable_ranks.shape[0]
    return (
        FIRST_ORDER_EXPORT,
        FLUX_EXPORT,
        FIRST_ORDER_IMPORT,
        *((SATURABLE_IMPORT, j) for j in range(count)),
    )


def exchange_half_step(state, control, h, p, *, xp=jnp, area=None, labels=None):
    """(state after h of exchange, validity): every written amount finite and positive, and every
    saturable solve converged. area: each route's current patch area (route_areas), or None for
    the declared area bound at the definition. With labels (FR-42, D289; static), also its
    one-way moves (one_way_moves)."""
    area = p.exchange_route_area_m2 if area is None else area
    rows = p.exchange_rows
    inc_c = state.amount_increment[rows]
    inc_o = state.extracellular_amount_increment[rows]
    acc = (state.exchange_moved_fmol, state.exchange_work_pJ, state.exchange_energy_magnitude_pJ)
    sequence = stages(p)
    plan = (
        *((s, 0.5 * h) for s in sequence[:-1]),
        (sequence[-1], h),
        *((s, 0.5 * h) for s in reversed(sequence[:-1])),
    )
    valid = xp.asarray(True)
    carried = xp.zeros_like(state.exchange_moved_fmol) if labels is not None else None
    for which, length in plan:
        if labels is None:
            inc_c, inc_o, acc, ok = _stage(
                inc_c, inc_o, acc, which, length, control, p, area, xp=xp
            )
        else:
            inc_c, inc_o, acc, ok, moved = _stage(
                inc_c, inc_o, acc, which, length, control, p, area, xp=xp, track=True
            )
            carried = carried + moved
        valid &= ok
    new = state._replace(
        amount_increment=set_rows(state.amount_increment, rows, inc_c, xp=xp),
        extracellular_amount_increment=set_rows(
            state.extracellular_amount_increment, rows, inc_o, xp=xp
        ),
        exchange_moved_fmol=acc[0],
        exchange_work_pJ=acc[1],
        exchange_energy_magnitude_pJ=acc[2],
    )
    flowing = xp.any(control.exchange_rate > 0)  # No positive rate: the start state, bitwise.
    selected = type(state)(*(xp.where(flowing, a, b) for a, b in zip(new, state, strict=True)))
    if labels is None:
        return selected, valid & _own_valid(selected, p, xp=xp)
    moves = one_way_moves(xp.where(flowing, carried, 0.0), labels, p, xp=xp)
    return selected, valid & _own_valid(selected, p, xp=xp), moves


def one_way_moves(carried, labels, p, *, xp):
    """(out, into, transfers) of the labelled rows over a half-step (FR-42's interface,
    operators/contract.py; nodes on the combined axis, cells then outside nodes): no new material
    and no loss, every route's moved amount a transfer from its source to its destination (an
    export from its cell to its outside node, an import back), carrying the source's shares."""
    label_rows, arrival = labels[0], labels[1]
    m, n = xp.asarray(label_rows).shape[0], p.active.shape[0]
    nodes = n + p.outside_active.shape[0]
    export = p.exchange_route_code < FIRST_ORDER_IMPORT
    cell, outside = p.exchange_route_cell, n + p.exchange_route_outside
    own = p.exchange_route_species[None, :] == xp.asarray(label_rows)[:, None]  # [m, route]
    amount = xp.where(own, carried[None, :], 0.0)
    transfer = (amount, xp.where(export, cell, outside), xp.where(export, outside, cell))
    return xp.zeros((m, nodes)), xp.zeros((m, arrival.shape[1], nodes)), (transfer,)


def _own_valid(state, p, *, xp):
    moved = state.exchange_moved_fmol
    export = p.exchange_route_code < FIRST_ORDER_IMPORT
    valid = xp.all(xp.isfinite(moved)) & xp.all(xp.where(export, moved >= 0, moved <= 0))
    valid &= xp.all(xp.isfinite(state.exchange_work_pJ))
    magnitude = state.exchange_energy_magnitude_pJ
    return valid & xp.all(xp.isfinite(magnitude)) & xp.all(magnitude >= 0)


def exchange_domain_valid(state, p, *, xp):
    """Its own fields (finite, signed by direction) and its species rows' amounts (finite and
    positive at active cells and finite outside nodes)."""
    valid = _own_valid(state, p, xp=xp)
    rows = p.exchange_rows
    finite = p.outside_active & ~p.reservoir
    cells = p.amount_reference[rows] + state.amount_increment[rows]
    nodes = p.extracellular_amount_reference[rows] + state.extracellular_amount_increment[rows]
    valid &= xp.all(xp.where(p.active[None, :], xp.isfinite(cells) & (cells > 0), True))
    valid &= xp.all(xp.where(finite[None, :], xp.isfinite(nodes) & (nodes > 0), True))
    return valid


# ------------------------------------------------------------------ the operator


def check_area_reads(spec, declaration):
    """Where an operator of the composition provides membrane_area, so that the half-steps read
    the view's current areas (D191), refuse a route whose patch shares its cell and outside node
    with another declared patch: route_areas finds the patch on device by that pair (fails
    closed)."""
    if not any("membrane_area" in op.VIEW_FIELDS for op, _, _ in composite_spec.entries(spec)):
        return
    patches = {p.id: p for p in spec.model.membranes}
    pairs = Counter((p.inside, p.outside) for p in spec.model.membranes)
    for route in declaration.routes:
        patch = patches[route.patch]
        if pairs[(patch.inside, patch.outside)] > 1:
            raise ConfigError(
                f"{LAW_ID}: route {route.id}'s patch {route.patch!r} is one of "
                f"{pairs[(patch.inside, patch.outside)]} declared patches joining "
                f"{patch.inside!r} to {patch.outside!r}; where an operator provides the patch "
                "areas, a route's current area is found by its cell and outside node, so that "
                "pair must name one patch (D191's current read; fails closed)"
            )


def key_of(route):
    return (route.species, route.direction, route.law)


class ScheduledSpeciesExchange(Operator):
    LAW_ID = LAW_ID
    IDENTITY_ROLE = "author"  # Species registry (D176): it declares its species.
    STEP_ID = STEP_ID
    SPLIT = True
    RK4 = "split"
    STATE_AXES = STATE_AXES
    WORK_FIELDS = ("exchange_work_pJ",)
    LAYOUT_FIELDS = LAYOUT_FIELDS
    CONTROL_FIELDS = ("exchange_rate", "exchange_saturation_mM")
    EXPERIMENT_KEYS = ("exchange_controls",)
    # Every rate reads the declared volumes. Uptake per area reads the patch area current at its
    # half-step (D191): the view's where an operator of the composition changes it, else the
    # declared one (module docstring). A change at stage split, a writer of membrane state's
    # fields included, must precede it in the declared order (C2).
    CONFLICTS_VIEW = common.CONFLICTS_VIEW
    VIEW_READS = ("membrane_area",)
    SCOPED_READS = {"membrane_area": Read("current", "split")}
    ENTITY_WRITES = {
        "amount_increment": ("exchange_moved_fmol",),
        "extracellular_amount_increment": ("exchange_moved_fmol",),
    }
    # Its layer in the run view (docs/RUN_VIEW_DESIGN.md §3): scheduled rates, prescribed.
    VIEW_LAYERS = ({"id": "exchange", "label": "Species exchange", "representation": "prescribed"},)
    # Its records in the run view (the contract): every accumulator is a total since the start; a
    # route's moved amount is positive outward (export positive, the module's convention).
    RECORD_KINDS = {
        "exchange_moved_fmol": "cumulative",
        "exchange_energy_magnitude_pJ": "cumulative",
    }
    ORIENTATION = {
        "exchange_moved_fmol": {
            "from": "inside",
            "to": "outside",
            "says": "a positive amount leaves the cell of the route's patch for that patch's "
            "outside node: an export route's total is zero or more, an import route's zero or less",
            "confirmed": "the lead, 16 November 2026",
        }
    }

    def view_sets(self, spec, declaration):
        """The run view's set of its own axis (cells/records/run_view.py): its routes, in declared order,
        each on its patch, with the species it carries, its declared direction and its roles."""  # noqa: E501
        routes = declaration.routes
        return {
            "exchange_route": {
                "id": "exchange_route",
                "ids": tuple(r.id for r in routes),
                "holds": "exchange route",
                "on": ("membrane", tuple(r.patch for r in routes)),
                "carries": tuple(r.species for r in routes),
                "direction": tuple(r.direction for r in routes),
                "roles": {
                    "inside": "the cell of the route's patch",
                    "outside": "that patch's outside node",
                },
            }
        }

    # ------------------------------------------------------------ definition

    def parse(self, raw, base, inner_model):
        return parse_exchange(raw, base)

    def to_dict(self, declaration, base):
        return exchange_to_dict(declaration)

    def parse_schedule(self, raw, base, declaration):
        return parse_controls(raw, base, declaration)

    def schedule_to_dict(self, schedule, base, declaration):
        by_id = {r.id: r for r in declaration.routes}
        return dict(
            exchange_controls=common.schedules_to_dict(
                schedule, lambda route_id, v: _value_dict(by_id[route_id], v)
            )
        )

    def schedule_times(self, schedule):
        return common.schedule_times(schedule)

    def value_at(self, schedule, time):
        return common.value_at(schedule, time)

    def control_values(self, spec, declaration, schedule, records, indices, times):
        tables = common.route_tables(
            spec, declaration.routes, schedule, declaration.templates, LAW_ID
        )
        values = common.control_arrays(tables, times, 2)
        return values[..., 0], values[..., 1]

    def species_identities(self, declaration):
        return declaration.species

    def check_definition(self, spec, declaration, schedule, model):
        common.check_species_cap(spec, LAW_ID)
        common.check_identities(spec, LAW_ID, declaration.species)
        common.check_templates(spec, declaration.templates, declaration.routes, LAW_ID)
        tables = common.route_tables(
            spec, declaration.routes, schedule, declaration.templates, LAW_ID
        )
        common.check_donor_copies(spec, declaration.routes, tables, LAW_ID, key_of)
        check_area_reads(spec, declaration)

    def batch_signature(self, declaration):
        """The static route structure; identities and rates are not part of it."""
        return (
            LAW_ID,
            tuple(s.id for s in declaration.species),
            tuple((r.species, r.patch, r.direction, r.law) for r in declaration.routes),
        )

    def working_size(self, spec):
        return 0

    def summary(self, spec, declaration, schedule, history):
        return {
            "exchange_law": LAW_ID,
            "exchange_species": common.summary_identities(declaration.species),
            "exchange_routes": {
                r.id: dict(species=r.species, patch=r.patch, direction=r.direction, law=r.law)
                for r in declaration.routes
            },
            "exchange_stages": "palindromic exact stages (module docstring)",
            "exchange_rk4": "exact half-steps around the inner RK4 step",
        }

    # ------------------------------------------------------------ binding

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        return bind(spec, declaration)

    # ------------------------------------------------------------ step parts

    def statically_idle(self, p):
        return p.exchange_route_cell.shape[0] == 0

    def half_step(self, state, h, control, p, *, xp, view=None, labels=None):
        """view: the reader view the composite passes where an operator changes membrane_area
        (D191's current read; C1: none otherwise, and the declared area is read). labels (FR-42,
        D289; static): (rows, arrival); the call then also returns its one-way moves."""
        area = None if view is None else route_areas(view.membrane_area, p, xp=xp)
        if labels is None:
            return exchange_half_step(state, control, h, p, xp=xp, area=area)
        return exchange_half_step(state, control, h, p, xp=xp, area=area, labels=labels)

    def control_valid(self, control, p, *, xp):
        rate, km = control.exchange_rate, control.exchange_saturation_mM
        saturable = p.exchange_route_code == SATURABLE_IMPORT
        valid = xp.all(xp.isfinite(rate) & (rate >= 0))
        return valid & xp.all(xp.where(saturable, xp.isfinite(km) & (km > 0), True))

    def rates(self, state, control, p, view, *, xp):
        return {k: xp.zeros_like(getattr(state, k)) for k in self.STATE_AXES}, None, None

    def rate_checks(self, state, control, p, valid, *, xp):
        return valid & exchange_domain_valid(state, p, xp=xp)

    def domain_valid(self, state, p, valid, *, xp):
        own = exchange_domain_valid(state, p, xp=xp)
        return own if valid is None else valid & own

    # ------------------------------------------------------------ ledgers

    def ledger_terms(self, result, row, p, *, xp):
        if self.statically_idle(p):
            return result, {}
        moved = row.exchange_moved_fmol
        species = p.exchange_route_species
        result["local"] = scatter_add(
            result["local"], (species, p.exchange_route_cell), moved, xp=xp
        )
        result["outside"] = scatter_add(
            result["outside"], (species, p.exchange_route_outside), -moved, xp=xp
        )
        result["energy"] = result["energy"] - entity_sum(row.exchange_work_pJ, axis=None, xp=xp)
        return result, {}

    def magnitude_terms(self, magnitudes, row, p, *, xp):
        """Moved amounts in the local, outside and total ledgers (each move enters both nodes),
        and the absolute terms of every booked work in the energy ledger's."""
        if self.statically_idle(p):
            return magnitudes
        moved = xp.abs(row.exchange_moved_fmol)
        species = p.exchange_route_species
        magnitudes[0] = scatter_add(magnitudes[0], (species, p.exchange_route_cell), moved, xp=xp)
        magnitudes[1] = scatter_add(
            magnitudes[1], (species, p.exchange_route_outside), moved, xp=xp
        )
        magnitudes[2] = scatter_add(magnitudes[2], (species,), 2.0 * moved, xp=xp)
        energy = entity_sum(row.exchange_energy_magnitude_pJ, axis=None, xp=xp)
        magnitudes[6] = energy if magnitudes[6] is None else magnitudes[6] + energy
        return magnitudes
