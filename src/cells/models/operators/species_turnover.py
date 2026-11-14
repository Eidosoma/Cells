"""Operator scheduled_species_turnover@1: production and first-order clearance of neutral species.

docs/SECRETED_SPECIES_TRANSPORT_DESIGN.md §2.2 (D150, version 1). A secreted species is one more
row of @3's species axis (valence 0), which @3 owns and its face law carries (core/inventory_species
declares it). This operator writes that inventory at nodes, booked in its own accumulators.

Declaration: the species it acts on, with their identity (species_common.parse_species), and
routes, each a species, a node and a kind: production (cells only) or clearance (cells and finite
outside nodes; a held bath is refused, its composition is held). Templates: rates of newcomers made
from replacement templates, keyed by template ID, then route ID.

Schedule `turnover_controls`: piecewise-constant rates, production P (fmol/s) or clearance k (1/s),
per route, changing at exact multiples of dt: per-world control data, never closed-over constants.
Cell-side routes are keyed by carrier, not slot (the occupant rule, species_common; §5.2): a slot's
rates follow its occupant, a newcomer takes its template's rates, and a donor copy is admitted only
when its route values equal the slot's. Outside-node routes are scheduled per node.

Law, exact over each half-step h, per species and node with total production P and total
clearance k (several clearance routes at one node add: simultaneous first-order processes):
    n' = n e^{-kh} + P g,   g = (1 - e^{-kh}) / k   (g = h when k = 0),
booked as produced = P h and cleared = n f + P (h - g) >= 0 with f = -expm1(-kh) and h - g formed
as (kh + expm1(-kh)) / k, which is >= 0 in floating point too. The moved amount produced - cleared
is applied to @3's stored increment, never as n' - reference. The work is the exact free-energy
change of the touched node from that moved amount (adapter.species_chemical_free_energy_pJ, @3's
own term, one species row at a time), booked as signed work: a first-order law can run uphill in
the 1 mM reference convention (removing material below 1 mM raises G), and the dissipation check
refuses a decreasing heat element. Its real metabolic cost (synthesis, proteolysis) lies outside the
modelled inventory, a declared limit. The rounding magnitudes are the moved amounts and the absolute
terms of each booked change.

Energy guards. Under the IMEX solvers the shared energy bound is set by the ions' flows and is blind
to these bookings at µM–nM (bound/change 1.7 to 1,721 in a probed mixed world); the species-only
world and a NumPy ΔG test per law are the guards of record. Guard worlds start the species from a
pre-formed profile (a resolved switch-on); a ramped source is not admissible until a probe measures
it. A switch-on from the trace is transported exactly, but its first step books the face heat a few
percent off: in a mixed world that passes unseen under the ions' bound, a known limit (§2.6, §11.4).
Under RK4 the bound is the absolute 2e-8 pJ (no solver tolerance); RK4 is guarded, not refused, and
keeps exact half-steps around @3's RK4 step ("split").

Refusals. At the definition: a charged species, a production route on an outside node, a route on
a held bath, a negative rate, a schedule change off the dt grid, at most 7 species per world (the
lead's ruling 3), an occupant without its rates, a donor copy whose route values differ from the
slot's, and every provider or closer of the volumes and activity masks (CONFLICTS_VIEW: version 1
is transport on a static tissue, so water, the lumens, insertion and S5's partition and bridge are
refused). At run time: non-finite values and any written amount that would not stay positive. Each
half-step returns the finiteness and positivity of every amount it wrote as its validity, and the
operator's own domain re-checks its species rows, since the composite re-runs @3's domain at the
step end only for an operator whose view follows its split. The stationary analysis does not admit
the composite (its own ID check), and version 1 keeps it so: trace and nM species need per-species
Newton tolerances first (§8).

Idle: no route, statically idle; no positive rate in a half-step, the start state is selected;
untouched entries are selected, never offset by zero, so @3's ion rows are bitwise unchanged. The
face diffusivity that carries the species is the effective (FRAP) kind (§6).
"""

from dataclasses import dataclass

import jax.numpy as jnp
import numpy as np

from cells.core.multispecies_spec import identifier
from cells.core.specs import ConfigError, _fields
from cells.models import pump_composite_adapter as adapter
from cells.models.operators import species_common as common
from cells.models.operators.contract import Operator

LAW_ID = "scheduled_species_turnover@1"
STEP_ID = "exact_production_clearance_half_steps@1"
KINDS = ("production", "clearance")

STATE_AXES = {
    "turnover_produced_fmol": ["species", "cell_slot"],
    "turnover_cleared_fmol": ["species", "cell_slot"],
    "turnover_outside_cleared_fmol": ["species", "extracellular_slot"],
    "turnover_work_pJ": ["cell_slot"],
    "turnover_outside_work_pJ": ["extracellular_slot"],
    "turnover_energy_magnitude_pJ": ["cell_slot"],
    "turnover_outside_energy_magnitude_pJ": ["extracellular_slot"],
}
LAYOUT_FIELDS = (
    "turnover_rows",  # [species rows] int64: the species it acts on, in declared order.
    "turnover_route_row",  # [route] int64: the route's position in turnover_rows.
    "turnover_route_node",  # [route] int64: its cell or outside node.
    "turnover_route_outside",  # [route] bool: an outside node (else a cell).
    "turnover_route_production",  # [route] bool: production (else clearance).
)


@dataclass(frozen=True)
class Route:
    id: str
    species: str
    node: str
    kind: str
    cell: str | None  # The node when it is a cell (keyed by carrier); None for an outside node.


@dataclass(frozen=True)
class Turnover:
    law: str
    species: tuple
    routes: tuple
    templates: tuple


def _rate(value, what):
    if type(value) not in (int, float) or not np.isfinite(value) or value < 0:
        raise ConfigError(f"{LAW_ID}: {what} is a finite rate >= 0")
    return float(value)


def parse_turnover(raw, base):
    _fields(raw, {"law", "species", "routes", "templates"}, "species turnover")
    if raw["law"] != LAW_ID:
        raise ConfigError("Species turnover requires law " + LAW_ID)
    species = common.parse_species(raw["species"], base, LAW_ID)
    listed = {s.id for s in species}
    m = base.model
    cells = {c.id for c in m.cells}
    outside = {c.id: c for c in m.extracellular}
    if type(raw["routes"]) is not list:
        raise ConfigError(f"{LAW_ID} routes require an explicit list")
    routes = []
    for entry in raw["routes"]:
        _fields(entry, {"id", "species", "node", "kind"}, "species turnover route")
        name, kind = identifier(entry["id"]), entry["kind"]
        species_id, node = entry["species"], entry["node"]
        if species_id not in listed:
            raise ConfigError(
                f"{LAW_ID}: route {name} acts on {species_id!r}, not a listed species"
            )
        if kind not in KINDS:
            raise ConfigError(f"{LAW_ID}: a route's kind is one of " + ", ".join(KINDS))
        if node in outside:
            if outside[node].reservoir:
                raise ConfigError(
                    f"{LAW_ID}: route {name} is on a held bath ({node}), whose composition is held"
                )
            if kind == "production":
                raise ConfigError(
                    f"{LAW_ID}: production is a cell's (route {name} is on outside node {node})"
                )
        elif node not in cells:
            raise ConfigError(f"{LAW_ID}: route {name} is on an undeclared node {node!r}")
        routes.append(Route(name, species_id, node, kind, node if node in cells else None))
    if len({r.id for r in routes}) != len(routes):
        raise ConfigError(f"{LAW_ID}: route IDs are unique")
    templates = common.parse_templates(
        raw["templates"],
        routes,
        LAW_ID,
        lambda route, v: (_rate(v, f"template rate of {route.id}"),),
    )
    return Turnover(LAW_ID, species, tuple(routes), templates)


def turnover_to_dict(declaration):
    if type(declaration) is not Turnover or any(type(r) is not Route for r in declaration.routes):
        raise ConfigError("Require explicit immutable species turnover declaration types")
    return dict(
        law=declaration.law,
        species=common.species_to_dict(declaration.species),
        routes=[
            dict(id=r.id, species=r.species, node=r.node, kind=r.kind) for r in declaration.routes
        ],
        templates=[
            dict(template_id=t.template_id, rates={k: v[0] for k, v in t.rates})
            for t in declaration.templates
        ],
    )


def parse_controls(raw, base, declaration):
    def values(route, change):
        _fields(change, {"time", "rate"}, f"{LAW_ID} schedule change")
        return (_rate(change["rate"], f"the rate of route {route.id}"),)

    return common.parse_schedules(
        raw["turnover_controls"], base, declaration.routes, LAW_ID, "turnover_controls", values
    )


def bind(spec, declaration):
    m, x = spec.model, spec.execution
    species = list(m.species_ids)
    rows = [species.index(s.id) for s in declaration.species]
    cells = [c.id for c in m.cells]
    outside = [c.id for c in m.extracellular]
    routes = declaration.routes
    layout = dict(
        turnover_rows=np.asarray(rows, dtype=np.int64),
        turnover_route_row=np.asarray(
            [[s.id for s in declaration.species].index(r.species) for r in routes], dtype=np.int64
        ),
        turnover_route_node=np.asarray(
            [cells.index(r.node) if r.cell is not None else outside.index(r.node) for r in routes],
            dtype=np.int64,
        ),
        turnover_route_outside=np.asarray([r.cell is None for r in routes], dtype=bool),
        turnover_route_production=np.asarray([r.kind == "production" for r in routes], dtype=bool),
    )
    s, n, o = len(species), x.capacity, x.extracellular_capacity
    shapes = dict(species=s, cell_slot=n, extracellular_slot=o)
    state = {k: np.zeros([shapes[a] for a in axes]) for k, axes in STATE_AXES.items()}
    return state, layout


# ------------------------------------------------------------------ the law


def scatter_add(base, index, values, *, xp):
    if xp is jnp:
        return base.at[index].add(values)
    out = np.array(base, copy=True)
    np.add.at(out, index, values)
    return out


def set_rows(full, rows, values, *, xp):
    """full with its listed species rows replaced (the other rows untouched, bit for bit)."""
    if xp is jnp:
        return full.at[rows].set(values)
    out = np.array(full, copy=True)
    out[rows] = values
    return out


def row_sum(values):
    """Sum over the leading (species row) axis with explicit adds in row order."""
    total = values[0]
    for k in range(1, values.shape[0]):
        total = total + values[k]
    return total


def produced_cleared(n, production, clearance, h, *, xp):
    """(produced, cleared) over h from amount n (module docstring): P h and n f + P (h - g)."""
    x = clearance * h
    positive = clearance > 0
    safe = xp.where(positive, clearance, 1.0)
    f = -xp.expm1(-x)
    lag = xp.where(positive, (x + xp.expm1(-x)) / safe, 0.0)  # h - g >= 0.
    return production * h, n * f + production * lag


def _node_update(increment, anchor, volume, mask, production, clearance, h, temperature, *, xp):
    """One node kind's update on the operator's rows: (increment', produced, cleared, work,
    magnitude, touched, valid), every per-element output zero or unchanged where untouched."""
    touched = mask[None, :] & ((production > 0) | (clearance > 0))
    n = xp.where(mask[None, :], anchor + increment, 1.0)
    produced, cleared = produced_cleared(n, production, clearance, h, xp=xp)
    moved = xp.where(touched, produced - cleared, 0.0)
    new = xp.where(touched, increment + moved, increment)
    after = anchor + new
    valid = xp.all(xp.where(touched, xp.isfinite(after) & (after > 0), True))
    work = adapter.species_chemical_free_energy_pJ(n, moved, volume, temperature, xp=xp)
    magnitude = adapter.species_chemical_magnitude_pJ(n, moved, volume, temperature, xp=xp)
    return (
        new,
        xp.where(touched, produced, 0.0),
        xp.where(touched, cleared, 0.0),
        xp.where(touched, work, 0.0),
        xp.where(touched, magnitude, 0.0),
        touched,
        valid,
    )


def turnover_half_step(state, rate, h, p, *, xp=jnp):
    """(state after h of turnover, every written amount finite and positive)."""
    rows = p.turnover_rows
    k, n, o = rows.shape[0], p.active.size, p.outside_active.size
    row, node = p.turnover_route_row, p.turnover_route_node
    on_cell, on_outside = ~p.turnover_route_outside, p.turnover_route_outside
    production = p.turnover_route_production

    def totals(mask, size):
        return scatter_add(
            xp.zeros((k, size)), (row, xp.where(mask, node, 0)), xp.where(mask, rate, 0.0), xp=xp
        )

    produce = totals(on_cell & production, n)
    clear_cell = totals(on_cell & ~production, n)
    clear_outside = totals(on_outside & ~production, o)
    t = p.temperature
    inc, prod, clr, work, mag, touched, ok_cell = _node_update(
        state.amount_increment[rows],
        p.amount_reference[rows],
        p.volume,
        p.active,
        produce,
        clear_cell,
        h,
        t,
        xp=xp,
    )
    finite = p.outside_active & ~p.reservoir  # Held baths are refused at the definition.
    out_inc, _, out_clr, out_work, out_mag, out_touched, ok_outside = _node_update(
        state.extracellular_amount_increment[rows],
        p.extracellular_amount_reference[rows],
        p.extracellular_volume,
        finite,
        xp.zeros((k, o)),
        clear_outside,
        h,
        t,
        xp=xp,
    )
    cell_touched, outside_touched = xp.any(touched, axis=0), xp.any(out_touched, axis=0)
    new = state._replace(
        amount_increment=set_rows(state.amount_increment, rows, inc, xp=xp),
        extracellular_amount_increment=set_rows(
            state.extracellular_amount_increment, rows, out_inc, xp=xp
        ),
        turnover_produced_fmol=set_rows(
            state.turnover_produced_fmol,
            rows,
            xp.where(
                touched,
                state.turnover_produced_fmol[rows] + prod,
                state.turnover_produced_fmol[rows],
            ),
            xp=xp,
        ),
        turnover_cleared_fmol=set_rows(
            state.turnover_cleared_fmol,
            rows,
            xp.where(
                touched, state.turnover_cleared_fmol[rows] + clr, state.turnover_cleared_fmol[rows]
            ),
            xp=xp,
        ),
        turnover_outside_cleared_fmol=set_rows(
            state.turnover_outside_cleared_fmol,
            rows,
            xp.where(
                out_touched,
                state.turnover_outside_cleared_fmol[rows] + out_clr,
                state.turnover_outside_cleared_fmol[rows],
            ),
            xp=xp,
        ),
        turnover_work_pJ=xp.where(
            cell_touched, state.turnover_work_pJ + row_sum(work), state.turnover_work_pJ
        ),
        turnover_outside_work_pJ=xp.where(
            outside_touched,
            state.turnover_outside_work_pJ + row_sum(out_work),
            state.turnover_outside_work_pJ,
        ),
        turnover_energy_magnitude_pJ=xp.where(
            cell_touched,
            state.turnover_energy_magnitude_pJ + row_sum(mag),
            state.turnover_energy_magnitude_pJ,
        ),
        turnover_outside_energy_magnitude_pJ=xp.where(
            outside_touched,
            state.turnover_outside_energy_magnitude_pJ + row_sum(out_mag),
            state.turnover_outside_energy_magnitude_pJ,
        ),
    )
    flowing = xp.any(rate > 0)  # No positive rate: select the start state (bitwise idle).
    selected = type(state)(*(xp.where(flowing, a, b) for a, b in zip(new, state, strict=True)))
    valid = ok_cell & ok_outside & _own_valid(selected, xp=xp)
    return selected, valid


def _own_valid(state, *, xp):
    valid = xp.asarray(True)
    for name in (
        "turnover_produced_fmol",
        "turnover_cleared_fmol",
        "turnover_outside_cleared_fmol",
        "turnover_energy_magnitude_pJ",
        "turnover_outside_energy_magnitude_pJ",
    ):
        value = getattr(state, name)
        valid &= xp.all(xp.isfinite(value)) & xp.all(value >= 0)
    for name in ("turnover_work_pJ", "turnover_outside_work_pJ"):
        valid &= xp.all(xp.isfinite(getattr(state, name)))
    return valid


def turnover_domain_valid(state, p, *, xp):
    """Its own fields (finite, signed as booked, zero on padding) and its species rows' amounts
    (finite and positive at active cells and finite outside nodes)."""
    valid = _own_valid(state, xp=xp)
    rows = p.turnover_rows
    for name in ("turnover_produced_fmol", "turnover_cleared_fmol", "turnover_work_pJ"):
        value = getattr(state, name)
        mask = p.active if value.ndim == 1 else p.active[None, :]
        valid &= xp.all(xp.where(mask, True, value == 0))
    finite = p.outside_active & ~p.reservoir
    for name in ("turnover_outside_cleared_fmol", "turnover_outside_work_pJ"):
        value = getattr(state, name)
        mask = finite if value.ndim == 1 else finite[None, :]
        valid &= xp.all(xp.where(mask, True, value == 0))
    cells = p.amount_reference[rows] + state.amount_increment[rows]
    nodes = p.extracellular_amount_reference[rows] + state.extracellular_amount_increment[rows]
    valid &= xp.all(xp.where(p.active[None, :], xp.isfinite(cells) & (cells > 0), True))
    valid &= xp.all(xp.where(finite[None, :], xp.isfinite(nodes) & (nodes > 0), True))
    return valid


# ------------------------------------------------------------------ the operator


def key_of(route):
    return (route.species, route.kind)


class ScheduledSpeciesTurnover(Operator):
    LAW_ID = LAW_ID
    STEP_ID = STEP_ID
    SPLIT = True
    RK4 = "split"
    STATE_AXES = STATE_AXES
    WORK_FIELDS = ("turnover_work_pJ", "turnover_outside_work_pJ")
    LAYOUT_FIELDS = LAYOUT_FIELDS
    CONTROL_FIELDS = ("turnover_rate",)
    EXPERIMENT_KEYS = ("turnover_controls",)
    CONFLICTS_VIEW = common.CONFLICTS_VIEW
    ENTITY_WRITES = {
        "amount_increment": ("turnover_produced_fmol", "turnover_cleared_fmol"),
        "extracellular_amount_increment": ("turnover_outside_cleared_fmol",),
    }

    # ------------------------------------------------------------ definition

    def parse(self, raw, base, inner_model):
        return parse_turnover(raw, base)

    def to_dict(self, declaration, base):
        return turnover_to_dict(declaration)

    def parse_schedule(self, raw, base, declaration):
        return parse_controls(raw, base, declaration)

    def schedule_to_dict(self, schedule, base, declaration):
        return dict(
            turnover_controls=common.schedules_to_dict(schedule, lambda _, v: dict(rate=v[0]))
        )

    def schedule_times(self, schedule):
        return common.schedule_times(schedule)

    def value_at(self, schedule, time):
        return common.value_at(schedule, time)

    def control_values(self, spec, declaration, schedule, records, indices, times):
        tables = common.route_tables(
            spec, declaration.routes, schedule, declaration.templates, LAW_ID
        )
        return (common.control_arrays(tables, times, 1)[..., 0],)

    def check_definition(self, spec, declaration, schedule, model):
        common.check_species_cap(spec, LAW_ID)
        common.check_identities(spec, LAW_ID, declaration.species)
        common.check_templates(spec, declaration.templates, declaration.routes, LAW_ID)
        tables = common.route_tables(
            spec, declaration.routes, schedule, declaration.templates, LAW_ID
        )
        common.check_donor_copies(spec, declaration.routes, tables, LAW_ID, key_of)

    def batch_signature(self, declaration):
        """The static route structure; identities and rates are not part of it."""
        return (
            LAW_ID,
            tuple(s.id for s in declaration.species),
            tuple((r.species, r.node, r.kind) for r in declaration.routes),
        )

    def working_size(self, spec):
        x, s = spec.execution, len(spec.model.species_ids)
        return 8 * (s + 2) * (x.capacity + x.extracellular_capacity)

    def summary(self, spec, declaration, schedule, history):
        return {
            "turnover_law": LAW_ID,
            "turnover_species": common.summary_identities(declaration.species),
            "turnover_routes": {
                r.id: dict(species=r.species, node=r.node, kind=r.kind) for r in declaration.routes
            },
            "turnover_rk4": "exact half-steps around the inner RK4 step",
        }

    # ------------------------------------------------------------ binding

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        return bind(spec, declaration)

    # ------------------------------------------------------------ step parts

    def statically_idle(self, p):
        return p.turnover_route_node.shape[0] == 0

    def half_step(self, state, h, control, p, *, xp):
        return turnover_half_step(state, control.turnover_rate, h, p, xp=xp)

    def control_valid(self, control, p, *, xp):
        rate = control.turnover_rate
        return xp.all(xp.isfinite(rate) & (rate >= 0))

    def rates(self, state, control, p, view, *, xp):
        return {k: xp.zeros_like(getattr(state, k)) for k in self.STATE_AXES}, None, None

    def rate_checks(self, state, control, p, valid, *, xp):
        return valid & turnover_domain_valid(state, p, xp=xp)

    def domain_valid(self, state, p, valid, *, xp):
        own = turnover_domain_valid(state, p, xp=xp)
        return own if valid is None else valid & own

    # ------------------------------------------------------------ ledgers

    def ledger_terms(self, result, row, p, *, xp):
        net = row.turnover_cleared_fmol - row.turnover_produced_fmol
        outside = row.turnover_outside_cleared_fmol
        result["local"] = result["local"] + net
        result["outside"] = result["outside"] + outside
        result["total"] = result["total"] + xp.sum(net, axis=1) + xp.sum(outside, axis=1)
        result["energy"] = (
            result["energy"] - xp.sum(row.turnover_work_pJ) - xp.sum(row.turnover_outside_work_pJ)
        )
        return result, {}

    def magnitude_terms(self, magnitudes, row, p, *, xp):
        """Moved amounts in the material ledgers and the absolute terms of every booked work in
        the energy ledger's; every term is zero without turnover, so the bounds are then @3's."""
        cell = row.turnover_produced_fmol + row.turnover_cleared_fmol
        outside = row.turnover_outside_cleared_fmol
        magnitudes[0] = magnitudes[0] + cell
        magnitudes[1] = magnitudes[1] + outside
        magnitudes[2] = magnitudes[2] + xp.sum(cell, axis=1) + xp.sum(outside, axis=1)
        energy = xp.sum(row.turnover_energy_magnitude_pJ) + xp.sum(
            row.turnover_outside_energy_magnitude_pJ
        )
        magnitudes[6] = energy if magnitudes[6] is None else magnitudes[6] + energy
        return magnitudes
