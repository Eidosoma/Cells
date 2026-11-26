"""Operator cells.operator.population_unit_turnover@1: a membrane population's units made from a precursor species
through maturation pools, and removed at first order (FR-7's unit producer, F1).

docs/ABUNDANCE_TO_FUNCTION_DESIGN.md §5 item 3 (the unit producer) and §4 item 1 (the unit's own
removal, declared: "FR-2's removal, or a turnover of units"), with the user's answers (D217, D218)
and the lead's rulings for F1 (19 November 2026):
* removal lives here, with a declared rate and a booked sink. This departs from D177, which put
  FR-7's removal under FR-2; it is the design note's own alternative, "or a turnover of units".
  FR-2's version 1 internalises units into a silent record that recycling returns, so it gives no
  unit a finite lifetime. D232 (the user, 19 November 2026) admits it as a scoped exception to
  D177, covering both this producer's surface insertion and its irreversible removal;
* the declared lifetime 1/k_r applies to every unit of a routed population, including the units
  present at the start (membrane state's declared units), not only to the units this producer
  inserts (D232);
* the assembly and trafficking delay is a chain of m first-order pools (the linear chain trick,
  MacDonald 1978, Time Lags in Biological Models: named from memory and not read);
* the precursor is a declared pool, which D150's cells.operator.scheduled_species_turnover@1 may also supply.
  Two writers of one row are admitted (the lead, 19 November 2026), provided each is a split part
  with exact half-steps in declared order, books its own moved amounts and the exact ΔG of its own
  move from the state its half-step receives, and refuses a non-positive amount: Strang splitting,
  second order. A row that a D152 reaction writes is refused, mirroring D152's one-writer rule;
* the unit's composition (ν precursor molecules per unit) is held in this declaration, and the
  precursor's identity is checked by the species registry (check_identities).

Declaration: `species`, the precursor species it consumes (D150's identity form: neutral rows of
@3 with no membrane, junction or channel route); `routes`, each {id, population (a channel
population of @3), precursor (a listed species), molecules_per_unit ν (an integer >= 1),
maturation_pools m (an integer, 0 <= m <= MAX_POOLS), maturation_time_s τ (> 0 when m > 0, null
when m = 0), initial_pool_units (a list of m units, each finite and >= 0: the units in transit in
each maturation pool at the start, zeros explicit; [] when m = 0)}. A route acts in its
population's cell, the inside of its patch; one route per population. Every key is explicit.

Schedule `unit_turnover_controls`: per route, piecewise-constant assembly_rate_per_s k_a (the
first-order rate at which the route consumes its precursor) and removal_rate_per_s k_r (the
first-order removal of the population's units: lifetime 1/k_r), from time 0, changing at exact
multiples of dt inside the horizon. Per-world control data, never closed-over constants.
The assembly rate is routable (B1′, docs/INVENTORY_COUPLING_DESIGN.md §2.1): a rate route's
factor F in [b, 1] multiplies it at the start of each of this operator's half-steps, from the
state that half-step receives, so the scheduled rate is the maximum and the definition's
bounds hold. Its elements are the routes, each at its population's cell.

Law, per route i in cell c with precursor P (n_P fmol in c), c_u = N_A 1e-15 / ν units per fmol,
κ = m / τ, and the population's units N (cells.operator.membrane_entity_state@1's units: declared plus
increment; every unit, the declared ones included, is removed at k_r):
    dn_P/dt = -A n_P,  with A the sum of k_a over the routes on (P, c);
    the route's share q_i = c_u n_P k_a,i / A (units), dq_i/dt = -A q_i;
    dM_1/dt = A q_i - κ M_1,  dM_j/dt = κ (M_{j-1} - M_j),  dN/dt = κ M_m - k_r N
    (with m = 0, dN/dt = A q_i - k_r N); the removed units leave into this operator's sink.
Each half-step is the exact solution of this linear chain with its rates frozen over h:
* the precursor's share in closed form, consumed_i = n_P (k_a,i / A) f with f = -expm1(-A h);
* the pools and N by uniformization (Jensen 1953; Grassmann 1977: named from memory and not
  read). With Λ the route's largest rate and Q = I + L/Λ, whose entries are non-negative and whose
  columns sum to at most 1, x(h) = Σ_k e^{-Λh} (Λh)^k / k! Q^k x0 and
  ∫_0^h x = Σ_k (T_k / Λ) Q^k x0,
  T_k the Poisson tail Pr[K > k] summed from the top. Every term is non-negative, so no
  cancellation can make an integral negative. TERMS terms, with the definition's bound Λ dt <= 1
  (so Λ h <= 1/2), leave a truncation below 1e-25 of the chain's total;
* each flux over h is its rate times its pool's integral (the first, the closed form), and every
  pool changes by its inflow less its outflow: moved amounts, never x(h) - x0, so the account
  closes by construction. A pool, the precursor or N that would not stay non-negative (the
  precursor positive) refuses the step.

The one material account. Per route: assembled units = c_u x precursor consumed (fmol), and
declared initial units in transit + assembled = units in the pools + units inserted (this
operator's ledgers, unit_conversion and unit_chain; the initial units are bound into the pools and
counted from the declaration, so the account closes by construction). Membrane state's
population ledger closes with inserted less removed, booked through ENTITY_WRITES as insertion
books its units, and @3's species ledger with the consumed precursor, booked as D152 books a
consumed reactant. The removed units stay booked in the sink.

Energy. The precursor's removal from its cell is booked as signed work: the exact free-energy
change of the node from the moved amount (adapter.species_chemical_free_energy_pJ, @3's own
term), as turnover books its clearance. Declared limits: the units carry no free energy in the
model, and the metabolic cost of assembly, trafficking and degradation lies outside it. Removal
lumps internalisation and degradation into one first-order sink.

Step checks. @3's definition-time bounds (R5) read each routed population at its largest
possible units: its declared units, its initial units in transit, and all the precursor its cell
can hold over the run assembled, the declared amount and turnover's largest production rate over
the horizon (no other writer supplies it, so that bounds the run).

Refused at the definition, each with its reason: an undeclared or charged precursor, or one
with a membrane, junction or channel route (parse_species); an unknown population, or one named
by two routes; a listed species no route consumes; ν not an integer >= 1; m outside [0,
MAX_POOLS]; τ not positive with pools, or given without them; an identity that differs from the
registry's; more than the species cap; another writer of population units anywhere in the
simulation, even on a population no route names (D232: the refusal is simulation-wide, so it
excludes FR-2's recycling, membrane insertion and division, whose moves would mix with this
removal of every unit, the declared ones included, at k_r); a precursor row that a D152 reaction
writes, another author of the precursor other than turnover, and an in-step mover of it; dt Λ > 1
anywhere in the schedule; a schedule that does not start at 0, changes off the dt grid or
outside 0 < t < end, or holds a negative or non-finite rate; and every provider of volumes and
closer of masks (CONFLICTS_VIEW, D150's static-tissue list). cells.operator.membrane_entity_state@1 precedes it
(REQUIRES). At run time: non-finite values, a negative pool, N or rate, and a precursor amount
that would not stay positive.

Idle: no route, statically idle; no positive flux in a half-step, the start state is selected,
so zero rates are bitwise idle and @3's other rows are untouched.

Guidance (D344): the operator declares one removal rate per population, so a mixture of lifetimes
is two declared populations, the fast and the slow cohort. Two studies of receptor turnover confirm
such a mixture, with a fast fraction of 13 to 20%.
"""

import math
from dataclasses import dataclass, replace
from types import MappingProxyType

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions import pump_composite_spec as composite_spec
from cells.definitions.spec_values import identifier
from cells.definitions.specs import ConfigError, _fields, _number
from cells.models import pump_composite_adapter as adapter
from cells.models import surface_pump as first
from cells.numerics.clock_instants import ON_THE_GRID, on_grid  # D283's one predicate.
from cells.numerics.species_sums import entity_sum, species_sum
from cells.operators import membrane_state, species_reactions
from cells.operators import species_common as common
from cells.operators.contract import Operator
from cells.registry import species_registry

LAW_ID = "cells.operator.population_unit_turnover@1"
STEP_ID = "exact_unit_chain_half_steps@1"
EXPERIMENT_KEY = "unit_turnover_controls"
ROUTE_AXIS, POOL_AXIS = "unit_route", "unit_pool"
MAX_POOLS = 8
AVOGADRO = 6.02214076e23  # 1/mol, exact (SI 2019).
TERMS = 20  # Uniformization terms: with Λh <= 1/2 the truncation is below 1e-25 relative.
RATE_BOUND = 1.0  # dt Λ <= 1 (so Λh <= 1/2), refused otherwise at the definition.
UNITS_FLOOR = 1e-9  # units: the floor of the units ledgers, membrane state's.

STATE_AXES = {
    "unit_pool_units": [ROUTE_AXIS, POOL_AXIS],  # Units in transit, per maturation pool.
    "unit_consumed_fmol": [ROUTE_AXIS],  # Precursor consumed (cumulative).
    "unit_assembled_units": [ROUTE_AXIS],  # Units assembled from it, c_u x consumed (cumulative).
    "unit_inserted_units": ["channel_slot"],  # Units inserted into the population (cumulative).
    "unit_removed_units": ["channel_slot"],  # Units removed into the sink (cumulative).
    "unit_turnover_work_pJ": ["cell_slot"],  # The precursor's exact free-energy change (signed).
    "unit_turnover_energy_magnitude_pJ": ["cell_slot"],  # Its absolute terms (cumulative).
}
LAYOUT_FIELDS = (
    "unit_rows",  # [k] int64: the species rows it acts on, in declared order.
    "unit_route_species",  # [route] int64: the route's precursor, a position in unit_rows.
    "unit_route_row",  # [route] int64: the precursor's species row.
    "unit_route_cell",  # [route] int64: the route's cell.
    "unit_route_channel",  # [route] int64: the population's channel slot.
    "unit_route_conversion",  # [route] c_u = N_A 1e-15 / ν, units per fmol.
    "unit_route_maturation_rate",  # [route] κ = m / τ (1/s; 0 with no pool).
    "unit_route_direct",  # [route] bool: no pool (m = 0).
    "unit_pool_present",  # [route, pool] bool: pool j < m.
    "unit_pool_last",  # [route, pool] bool: pool j = m - 1.
    "unit_route_initial_units",  # [route] the declared initial units in transit, summed.
)
LEDGERS = ("unit_chain", "unit_conversion")
LEDGER_DIAGNOSTICS = ("unit_chain_balance_error", "unit_conversion_balance_error")
LEDGER_MESSAGE = "Population unit turnover accounting failed: "


# ------------------------------------------------------------------ declaration


@dataclass(frozen=True)
class Route:
    id: str
    population: str
    precursor: str
    molecules_per_unit: int
    maturation_pools: int
    maturation_time_s: float | None
    initial_pool_units: tuple  # Units in transit in each pool at the start (m values).
    cell: str  # The population's cell, the inside of its patch (derived, not declared).


@dataclass(frozen=True)
class UnitTurnover:
    law: str
    species: tuple
    routes: tuple


@dataclass(frozen=True)
class RouteSchedule:
    route_id: str
    changes: tuple  # ((time, (assembly k_a, removal k_r)), ...), increasing in time.


def conversion(route):
    """c_u, the units assembled per fmol of precursor: N_A 1e-15 / ν."""
    return AVOGADRO * 1e-15 / route.molecules_per_unit


def _integer(value, what, low, high=None):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{LAW_ID}: {what} is an integer")
    if value < low or (high is not None and value > high):
        bound = f">= {low}" if high is None else f"in [{low}, {high}]"
        raise ConfigError(f"{LAW_ID}: {what} is {bound}")
    return value


def parse_declaration(raw, base):
    _fields(raw, {"law", "species", "routes"}, "population unit turnover")
    if raw["law"] != LAW_ID:
        raise ConfigError("Population unit turnover requires law " + LAW_ID)
    species = common.parse_species(raw["species"], base, LAW_ID)
    listed = {s.id for s in species}
    if type(raw["routes"]) is not list or not raw["routes"]:
        raise ConfigError(f"{LAW_ID} declares its routes in a non-empty list")
    cells = _population_cells(base.model)
    routes = []
    for entry in raw["routes"]:
        _fields(
            entry,
            {
                "id",
                "population",
                "precursor",
                "molecules_per_unit",
                "maturation_pools",
                "maturation_time_s",
                "initial_pool_units",
            },
            f"{LAW_ID} route",
        )
        name = identifier(entry["id"])
        population = identifier(entry["population"])
        if population not in cells:
            raise ConfigError(
                f"{LAW_ID}: route {name} names {population!r}, not a channel population of the "
                "model"
            )
        if entry["precursor"] not in listed:
            raise ConfigError(
                f"{LAW_ID}: route {name}'s precursor {entry['precursor']!r} is not a listed species"
            )
        nu = _integer(entry["molecules_per_unit"], f"route {name}'s molecules_per_unit", 1)
        pools = _integer(
            entry["maturation_pools"], f"route {name}'s maturation_pools", 0, MAX_POOLS
        )
        tau = entry["maturation_time_s"]
        if pools == 0:
            if tau is not None:
                raise ConfigError(
                    f"{LAW_ID}: route {name} has no maturation pool, so its maturation_time_s is "
                    "null"
                )
        else:
            tau = _number(tau, f"{LAW_ID}: route {name}'s maturation_time_s", positive=True)
        initial = entry["initial_pool_units"]
        if type(initial) is not list or len(initial) != pools:
            raise ConfigError(
                f"{LAW_ID}: route {name}'s initial_pool_units is an explicit list of its {pools} "
                "maturation pools' units at the start (zeros explicit)"
            )
        initial = tuple(
            _number(v, f"{LAW_ID}: route {name}'s initial_pool_units entry") for v in initial
        )
        routes.append(
            Route(name, population, entry["precursor"], nu, pools, tau, initial, cells[population])
        )
    if len({r.id for r in routes}) != len(routes):
        raise ConfigError(f"{LAW_ID}: route IDs are unique")
    named = [r.population for r in routes]
    if len(set(named)) != len(named):
        raise ConfigError(f"{LAW_ID}: one route per population (a population is named twice)")
    unused = sorted(listed - {r.precursor for r in routes})
    if unused:
        raise ConfigError(f"{LAW_ID}: species {unused[0]!r} is listed but no route consumes it")
    return UnitTurnover(LAW_ID, species, tuple(routes))


def declaration_to_dict(declaration):
    if type(declaration) is not UnitTurnover or any(
        type(r) is not Route for r in declaration.routes
    ):
        raise ConfigError("Require explicit immutable population unit turnover types")
    return dict(
        law=declaration.law,
        species=common.species_to_dict(declaration.species),
        routes=[
            dict(
                id=r.id,
                population=r.population,
                precursor=r.precursor,
                molecules_per_unit=r.molecules_per_unit,
                maturation_pools=r.maturation_pools,
                maturation_time_s=r.maturation_time_s,
                initial_pool_units=list(r.initial_pool_units),
            )
            for r in declaration.routes
        ],
    )


def _rate(value, what):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{LAW_ID}: {what} is a finite rate >= 0")
    if not math.isfinite(value) or value < 0:
        raise ConfigError(f"{LAW_ID}: {what} is a finite rate >= 0")
    return float(value)


def parse_schedule(raw, base, declaration):
    rows = raw[EXPERIMENT_KEY]
    if type(rows) is not list:
        raise ConfigError(f"{LAW_ID}: {EXPERIMENT_KEY} is an explicit list")
    dt, end = base.execution.dt, base.experiment.end_time
    known = [r.id for r in declaration.routes]
    schedules = {}
    for row in rows:
        _fields(row, {"route_id", "schedule"}, f"{LAW_ID} control")
        name = row["route_id"]
        if name not in known or name in schedules:
            raise ConfigError(f"{LAW_ID}: one schedule per declared route ({name!r})")
        changes = row["schedule"]
        if type(changes) is not list or not changes:
            raise ConfigError(f"{LAW_ID}: route {name}'s schedule is a non-empty list")
        parsed = []
        for index, change in enumerate(changes):
            _fields(
                change, {"time", "assembly_rate_per_s", "removal_rate_per_s"}, f"{LAW_ID} change"
            )
            time = _number(change["time"], f"{LAW_ID}: a schedule time")
            if index == 0 and time != 0.0:
                raise ConfigError(f"{LAW_ID}: route {name}'s schedule starts at 0")
            if on_grid(time, dt) is None:
                raise ConfigError(f"{LAW_ID}: a schedule change must be {ON_THE_GRID}")
            if index > 0 and not 0.0 < time < end:
                raise ConfigError(f"{LAW_ID}: a schedule change lies inside 0 < t < end")
            parsed.append(
                (
                    time,
                    (
                        _rate(change["assembly_rate_per_s"], f"route {name}'s assembly rate"),
                        _rate(change["removal_rate_per_s"], f"route {name}'s removal rate"),
                    ),
                )
            )
        times = [t for t, _ in parsed]
        if any(b <= a for a, b in zip(times, times[1:], strict=False)):
            raise ConfigError(f"{LAW_ID}: route {name}'s schedule times increase strictly")
        schedules[name] = tuple(parsed)
    missing = [k for k in known if k not in schedules]
    if missing:
        raise ConfigError(f"{LAW_ID}: route {missing[0]} needs its schedule in {EXPERIMENT_KEY}")
    return tuple(RouteSchedule(k, schedules[k]) for k in known)


def schedule_to_dict(schedule):
    return {
        EXPERIMENT_KEY: [
            dict(
                route_id=s.route_id,
                schedule=[
                    dict(time=t, assembly_rate_per_s=a, removal_rate_per_s=r)
                    for t, (a, r) in s.changes
                ],
            )
            for s in schedule
        ]
    }


def rates_at(changes, time):
    """(k_a, k_r) in force at `time` (a change at t applies from t)."""
    value = changes[0][1]
    for t, v in changes:
        if t <= time:
            value = v
    return value


# ------------------------------------------------------------------ definition checks


def _population_cells(model):
    """{channel id: its cell id} (the inside of its patch)."""
    inside = {p.id: p.inside for p in model.membranes}
    return {c.id: inside[c.membrane_id] for c in model.channels}


TURNOVER_LAW = (
    "cells.operator.scheduled_species_turnover@1"  # An admitted second writer of a precursor.
)
GENE_UNIT_LAW = (
    "cells.operator.templated_polymerisation@1"  # The other (FR-43 / D315), a bounded producer.
)


def check_writers(spec, declaration):
    """Refuse another writer of a population's units, a precursor row that a D152 reaction writes,
    another author of a precursor other than D150's turnover and the gene unit, and an in-step
    mover of one (module docstring): every unit here, declared ones included, is removed at k_r,
    and a precursor's writers are this operator, turnover's supply and the gene unit
    (cells.operator.templated_polymerisation@1, FR-43 / D315: the two-writer rule of 19 November 2026 extended,
    with the shared row's potential from the species registry, species_registry
    .check_shared_rows). R5 reads every producer's largest rate (supply_bound), so a precursor
    the gene unit makes without a static bound (a degradation's monomers) is refused."""
    precursors = {r.precursor for r in declaration.routes}
    rows = {(r.precursor, r.cell) for r in declaration.routes}
    for op, other, _ in composite_spec.entries(spec):
        if op.LAW_ID == LAW_ID:
            continue
        if "population_abundance_increment" in op.ENTITY_WRITES:
            raise ConfigError(
                f"{LAW_ID}: {op.LAW_ID} also writes population units. This operator removes every "
                "unit of its populations at k_r, the declared ones included, so a second writer's "
                "moves (FR-2's trafficking, insertion) would mix with that removal; version 1 is "
                "their one writer, simulation-wide (D232): FR-2's recycling, membrane insertion "
                "and division are excluded even on populations no route names"
            )
        if op.LAW_ID == species_reactions.LAW_ID:
            hit = sorted(rows & set(species_reactions.written(other)))
            if hit:
                raise ConfigError(
                    f"{LAW_ID}: a {op.LAW_ID} reaction writes the precursor {hit[0][0]!r} in "
                    f"{hit[0][1]}: one local-kinetics writer per reacting row, D152's rule "
                    "(declare the precursor's supply and use as the network's own reactions)"
                )
        elif op.IDENTITY_ROLE == "author" and op.LAW_ID not in (TURNOVER_LAW, GENE_UNIT_LAW):
            shared = sorted(precursors & {s.id for s in op.species_identities(other)})
            if shared:
                raise ConfigError(
                    f"{LAW_ID}: {op.LAW_ID} also declares the precursor {shared[0]!r}; besides "
                    f"this operator only {TURNOVER_LAW}'s supply is admitted as a writer of it"
                )
    for op, other, _ in composite_spec.entries(spec):
        bound = getattr(op, "production_bound", None)  # A producer that declares its bound.
        made = {} if bound is None else bound(spec, other)
        for name, cell in sorted(rows):
            if not math.isinf(made.get((name, cell), 0.0)):
                continue
            raise ConfigError(
                f"{LAW_ID}: the precursor {name!r} in {cell} is made at a rate with no static "
                "bound (by a degradation, a release's fates or an export's coupling), which R5's "
                "largest units need (supply_bound; FR-43 / D315)"
            )
    moved = species_registry.moved_in_step(spec)
    for name in sorted(precursors):
        movers = moved.get(name, {}).get("cell", ())
        if movers:
            raise ConfigError(
                f"{LAW_ID}: the precursor {name!r} is moved inside the inner step by {movers[0]}; "
                "its writers are split parts with exact half-steps only"
            )


def supply_bound(spec):
    """{(species, cell): the largest total production rate (fmol/s)} of every producer: turnover's
    cell routes, over every schedule of each route, and each operator that declares its own
    production_bound (the gene unit's, FR-43 / D315; math.inf where it has none): an upper bound
    on the supply a cell's precursor gets. A rate: check_spec_for multiplies it by the horizon."""
    out = {}
    for op, block, schedules in composite_spec.entries(spec):
        bound = getattr(op, "production_bound", None)
        if bound is not None:
            for key, rate in bound(spec, block).items():
                out[key] = out.get(key, 0.0) + rate
            continue
        if op.LAW_ID != TURNOVER_LAW:
            continue
        kind = {r.id: r for r in block.routes}
        top = {}
        for s in schedules:
            route = kind[s.route_id]
            if route.kind == "production" and route.cell is not None:
                peak = max(float(v[0]) for _, v in s.changes)
                top[route.id] = max(top.get(route.id, 0.0), peak)
        for route_id, peak in top.items():
            route = kind[route_id]
            key = (route.species, route.cell)
            out[key] = out.get(key, 0.0) + peak
    return out


def check_rate_bound(spec, declaration, schedule):
    """Refuse dt Λ > RATE_BOUND for a route (Λ: the largest rate of its chain over the schedule,
    with the group rate A the sum of the largest k_a of the routes sharing its precursor and cell),
    since the uniformization's truncation is bounded there (module docstring)."""
    dt = spec.execution.dt
    top = {s.route_id: [max(v[i] for _, v in s.changes) for i in (0, 1)] for s in schedule}
    groups = {}
    for r in declaration.routes:
        groups.setdefault((r.precursor, r.cell), []).append(r.id)
    for r in declaration.routes:
        assembly = math.fsum(top[k][0] for k in groups[(r.precursor, r.cell)])
        kappa = r.maturation_pools / r.maturation_time_s if r.maturation_pools else 0.0
        lam = max(assembly, kappa, top[r.id][1])
        if dt * lam > RATE_BOUND:
            raise ConfigError(
                f"{LAW_ID}: route {r.id} has dt Λ = {dt * lam:.3g} > {RATE_BOUND} (Λ, the largest "
                "rate of its chain over the schedule): the exact half-step's series is bounded for "
                "dt Λ <= 1"
            )


def densities(spec):
    """{channel id: reference density (units/m^2)}, from cells.operator.membrane_entity_state@1's declaration."""
    for op, block, _ in composite_spec.entries(spec):
        if op.LAW_ID == membrane_state.LAW_ID:
            return {p.channel_id: p.reference_density_per_m2 for p in block.populations}
    return {}


def check_spec_for(check_spec, spec, declaration):
    """R5: @3's bounds read each routed population at its largest possible units: its declared
    units plus all the precursor its cell can hold over the run assembled, the declared amount and
    turnover's largest supply over the horizon (module docstring)."""
    rho = densities(spec)
    m = spec.model
    species = list(m.species_ids)
    cells = [c.id for c in m.cells]
    channels = {c.id: c for c in m.channels}
    areas = {p.id: p.area_m2 for p in m.membranes}
    supply = supply_bound(spec)
    end = spec.experiment.end_time
    abundance = {}
    for r in declaration.routes:
        c = channels[r.population]
        if c.id not in rho:  # No membrane state: refused by REQUIRES, which names it.
            continue
        area = areas[c.membrane_id]
        declared = m.cells[cells.index(r.cell)].initial_amount_fmol[species.index(r.precursor)]
        precursor = declared + supply.get((r.precursor, r.cell), 0.0) * end
        in_transit = math.fsum(r.initial_pool_units)
        units = c.abundance * area * rho[c.id] + in_transit + conversion(r) * precursor
        abundance[c.id] = units / (area * rho[c.id])
    return replace(
        check_spec,
        model=replace(
            check_spec.model,
            channels=tuple(
                replace(c, abundance=max(c.abundance, abundance[c.id])) if c.id in abundance else c
                for c in check_spec.model.channels
            ),
        ),
    )


# ------------------------------------------------------------------ binding


def bind(spec, declaration):
    m, x = spec.model, spec.execution
    species = list(m.species_ids)
    listed = [s.id for s in declaration.species]
    cells = [c.id for c in m.cells]
    channels = [c.id for c in m.channels]
    routes = declaration.routes
    depth = max((r.maturation_pools for r in routes), default=0)
    present = np.zeros((len(routes), depth), dtype=bool)
    last = np.zeros((len(routes), depth), dtype=bool)
    for i, r in enumerate(routes):
        present[i, : r.maturation_pools] = True
        if r.maturation_pools:
            last[i, r.maturation_pools - 1] = True
    layout = dict(
        unit_rows=np.asarray([species.index(s) for s in listed], dtype=np.int64),
        unit_route_species=np.asarray([listed.index(r.precursor) for r in routes], dtype=np.int64),
        unit_route_row=np.asarray([species.index(r.precursor) for r in routes], dtype=np.int64),
        unit_route_cell=np.asarray([cells.index(r.cell) for r in routes], dtype=np.int64),
        unit_route_channel=np.asarray(
            [channels.index(r.population) for r in routes], dtype=np.int64
        ),
        unit_route_conversion=np.asarray([conversion(r) for r in routes], dtype=float),
        unit_route_maturation_rate=np.asarray(
            [
                r.maturation_pools / r.maturation_time_s if r.maturation_pools else 0.0
                for r in routes
            ],
            dtype=float,
        ),
        unit_route_direct=np.asarray([r.maturation_pools == 0 for r in routes], dtype=bool),
        unit_pool_present=present,
        unit_pool_last=last,
        unit_route_initial_units=np.asarray(
            [math.fsum(r.initial_pool_units) for r in routes], dtype=float
        ),
    )
    k, n, c = len(routes), x.capacity, x.channel_capacity
    pools = np.zeros((k, depth))
    for i, r in enumerate(routes):
        pools[i, : r.maturation_pools] = r.initial_pool_units
    state = dict(
        unit_pool_units=pools,
        unit_consumed_fmol=np.zeros(k),
        unit_assembled_units=np.zeros(k),
        unit_inserted_units=np.zeros(c),
        unit_removed_units=np.zeros(c),
        unit_turnover_work_pJ=np.zeros(n),
        unit_turnover_energy_magnitude_pJ=np.zeros(n),
    )
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


def _shift(first_values, pools, *, xp):
    """[route, pool] each pool's upstream value: the first pool's is first_values, pool j's is
    pool j - 1's."""
    return xp.concatenate([first_values[:, None], pools[:, :-1]], axis=1)


def chain_step(q, pools, n, a, kappa, r, lam, present, last, direct, *, xp):
    """One application of Q = I + L/Λ to the route chains (q, pools, N), per route (lam > 0)."""
    out_q = a * q / lam
    if pools.shape[1] == 0:  # Static: no route has a pool.
        return q - out_q, pools, n - r * n / lam + out_q
    out = xp.where(present, kappa[:, None] * pools / lam[:, None], 0.0)
    into = xp.where(present, _shift(out_q, out, xp=xp), 0.0)
    to_n = xp.where(direct, out_q, xp.max(xp.where(last, out, 0.0), axis=1))
    return q - out_q, pools - out + into, n - r * n / lam + to_n


def chain_integrals(q, pools, n, a, kappa, r, h, present, last, direct, *, xp):
    """(∫_0^h q, ∫_0^h pools, ∫_0^h N) of the exact chain with rates frozen over h, by
    uniformization (module docstring): every term non-negative."""
    lam = xp.maximum(xp.maximum(a, xp.where(direct, 0.0, kappa)), r)
    safe = xp.where(lam > 0, lam, 1.0)
    y = lam * h
    weights = [xp.exp(-y)]
    for j in range(1, TERMS + 2):
        weights.append(weights[-1] * y / j)
    tails = [None] * (TERMS + 1)
    tails[TERMS] = weights[TERMS + 1]
    for k in range(TERMS - 1, -1, -1):
        tails[k] = tails[k + 1] + weights[k + 1]
    total_q, total_pools, total_n = 0.0 * q, 0.0 * pools, 0.0 * n
    vq, vp, vn = q, pools, n
    for k in range(TERMS + 1):
        w = tails[k] / safe
        total_q, total_pools, total_n = (
            total_q + w * vq,
            total_pools + w[:, None] * vp,
            total_n + w * vn,
        )
        if k < TERMS:
            vq, vp, vn = chain_step(vq, vp, vn, a, kappa, r, safe, present, last, direct, xp=xp)
    zero = lam == 0
    return (
        xp.where(zero, 0.0, total_q),
        xp.where(zero[:, None], 0.0, total_pools),
        xp.where(zero, 0.0, total_n),
    )


def unit_half_step(state, assembly, removal, h, p, *, xp=jnp):
    """(state after h of every route's chain, every written value finite and in its domain)."""
    rows, cells, species = p.unit_route_row, p.unit_route_cell, p.unit_route_species
    channel, conv = p.unit_route_channel, p.unit_route_conversion
    kappa, direct = p.unit_route_maturation_rate, p.unit_route_direct
    present, last = p.unit_pool_present, p.unit_pool_last
    s_rows, n_cells = p.unit_rows.shape[0], p.active.size
    # The group rate A on (precursor, cell), and the route's share of the group's precursor.
    group = scatter_add(xp.zeros((s_rows, n_cells)), (species, cells), assembly, xp=xp)
    a = group[species, cells]
    share = xp.where(a > 0, assembly / xp.where(a > 0, a, 1.0), 0.0)
    amount = p.amount_reference[rows, cells] + state.amount_increment[rows, cells]
    consumed = amount * share * -xp.expm1(-a * h)  # fmol, the closed form.
    assembled = conv * consumed  # Units into the chain.
    q0 = conv * amount * share
    n0 = membrane_state.units(state, p, xp=xp)[channel]
    pools = state.unit_pool_units
    _, i_pools, i_n = chain_integrals(
        q0, pools, n0, a, kappa, removal, h, present, last, direct, xp=xp
    )
    if xp is jnp and pools.shape[1]:  # Static: compiled, with maturation pools.
        # Materialize the series' integrals once. Every state field's select below reads them
        # (through `flowing`), and with pools XLA's fusion duplicated the 21-term series into each
        # consumer: a compile of over 10 minutes and steps 8 times slower (FR-7's chain worlds,
        # m = 3, 20 November 2026). The barrier changes no operation, only where XLA may fuse;
        # m = 0 programs are unchanged (static).
        i_pools, i_n = jax.lax.optimization_barrier((i_pools, i_n))
    removed = removal * i_n
    if pools.shape[1] == 0:  # Static: no route has a pool.
        inserted, new_pools = assembled, pools
    else:
        out = xp.where(present, kappa[:, None] * i_pools, 0.0)
        into = xp.where(present, _shift(assembled, out, xp=xp), 0.0)
        inserted = xp.where(direct, assembled, xp.max(xp.where(last, out, 0.0), axis=1))
        new_pools = pools + into - out
    # The precursor rows' moved amounts and their exact free-energy change, per (row, cell).
    taken = scatter_add(xp.zeros((s_rows, n_cells)), (species, cells), consumed, xp=xp)
    moved = xp.where(p.active[None, :], -taken, 0.0)
    anchor_rows = p.amount_reference[p.unit_rows]
    increment_rows = state.amount_increment[p.unit_rows]
    held = xp.where(p.active[None, :], anchor_rows + increment_rows, 1.0)
    work = adapter.species_chemical_free_energy_pJ(held, moved, p.volume, p.temperature, xp=xp)
    magnitude = adapter.species_chemical_magnitude_pJ(held, moved, p.volume, p.temperature, xp=xp)
    after_rows = held + moved
    touched = xp.any(taken > 0, axis=0)
    net = inserted - removed
    new = state._replace(
        amount_increment=set_rows(
            state.amount_increment, p.unit_rows, increment_rows + moved, xp=xp
        ),
        population_abundance_increment=scatter_add(
            state.population_abundance_increment, channel, net, xp=xp
        ),
        unit_pool_units=new_pools,
        unit_consumed_fmol=state.unit_consumed_fmol + consumed,
        unit_assembled_units=state.unit_assembled_units + assembled,
        unit_inserted_units=scatter_add(state.unit_inserted_units, channel, inserted, xp=xp),
        unit_removed_units=scatter_add(state.unit_removed_units, channel, removed, xp=xp),
        unit_turnover_work_pJ=xp.where(
            touched,
            state.unit_turnover_work_pJ + species_sum(work, xp=xp),
            state.unit_turnover_work_pJ,
        ),
        unit_turnover_energy_magnitude_pJ=xp.where(
            touched,
            state.unit_turnover_energy_magnitude_pJ + species_sum(magnitude, xp=xp),
            state.unit_turnover_energy_magnitude_pJ,
        ),
    )
    flowing = xp.any(assembled > 0) | xp.any(removed > 0)
    if pools.shape[1]:
        flowing |= xp.any(out > 0)
    selected = type(state)(*(xp.where(flowing, x, y) for x, y in zip(new, state, strict=True)))
    n_after = n0 + net
    valid = xp.all(xp.where(p.active[None, :], xp.isfinite(after_rows) & (after_rows > 0), True))
    valid &= xp.all(xp.isfinite(new_pools) & (new_pools >= 0))
    valid &= xp.all(xp.isfinite(n_after) & (n_after >= 0))
    valid &= own_valid(selected, xp=xp)
    return selected, valid


def own_valid(state, *, xp):
    valid = xp.asarray(True)
    for name in (
        "unit_pool_units",
        "unit_consumed_fmol",
        "unit_assembled_units",
        "unit_inserted_units",
        "unit_removed_units",
        "unit_turnover_energy_magnitude_pJ",
    ):
        value = getattr(state, name)
        valid &= xp.all(xp.isfinite(value)) & xp.all(value >= 0)
    return valid & xp.all(xp.isfinite(state.unit_turnover_work_pJ))


def unit_domain_valid(state, p, *, xp):
    """Its own fields (finite, signed as booked, zero on absent pools and padding) and its
    precursor rows' amounts (finite and positive at active cells)."""
    valid = own_valid(state, xp=xp)
    if p.unit_pool_present.shape[1]:
        valid &= xp.all(xp.where(p.unit_pool_present, True, state.unit_pool_units == 0))
    for name in ("unit_turnover_work_pJ", "unit_turnover_energy_magnitude_pJ"):
        valid &= xp.all(xp.where(p.active, True, getattr(state, name) == 0))
    for name in ("unit_inserted_units", "unit_removed_units"):
        valid &= xp.all(xp.where(p.channel_active, True, getattr(state, name) == 0))
    rows = p.unit_rows
    amounts = p.amount_reference[rows] + state.amount_increment[rows]
    valid &= xp.all(xp.where(p.active[None, :], xp.isfinite(amounts) & (amounts > 0), True))
    return valid


# ------------------------------------------------------------------ the operator


class PopulationUnitTurnover(Operator):
    LAW_ID = LAW_ID
    IDENTITY_ROLE = "author"  # Species registry (D176): it declares the precursor it writes.
    STEP_ID = STEP_ID
    SPLIT = True
    RK4 = "split"
    STATE_AXES = STATE_AXES
    WORK_FIELDS = ("unit_turnover_work_pJ",)
    LAYOUT_FIELDS = LAYOUT_FIELDS
    CONTROL_FIELDS = ("unit_assembly_rate", "unit_removal_rate")
    # B1′: the assembly rate, per route, which a rate route may multiply in the half-steps (the
    # scheduled rate is the maximum).
    ROUTABLE_CONTROLS = MappingProxyType({"unit_assembly_rate": "rate"})
    EXPERIMENT_KEYS = (EXPERIMENT_KEY,)
    CONFLICTS_VIEW = common.CONFLICTS_VIEW
    ENTITY_WRITES = {
        "amount_increment": ("unit_consumed_fmol",),
        "population_abundance_increment": ("unit_inserted_units", "unit_removed_units"),
    }
    REQUIRES = (membrane_state.LAW_ID,)
    LEDGERS = LEDGERS
    LEDGER_DIAGNOSTICS = LEDGER_DIAGNOSTICS
    LEDGER_MESSAGE = LEDGER_MESSAGE
    # The run view (docs/RUN_VIEW_DESIGN.md §3): scheduled rates, prescribed.
    VIEW_LAYERS = (
        {
            "id": "unit_turnover",
            "label": "Population unit turnover",
            "representation": "prescribed",
        },
    )
    UNITS = {
        "unit_pool_units": "units",
        "unit_assembled_units": "units",
        "unit_inserted_units": "units",
        "unit_removed_units": "units",
    }
    RECORD_KINDS = {
        "unit_pool_units": "amount",
        "unit_consumed_fmol": "cumulative",
        "unit_assembled_units": "cumulative",
        "unit_inserted_units": "cumulative",
        "unit_removed_units": "cumulative",
        "unit_turnover_energy_magnitude_pJ": "cumulative",
    }

    def view_sets(self, spec, declaration):
        """The run view's sets of its two axes: each route at its population's channel, carrying
        its precursor; and the maturation pools, in chain order."""
        routes = declaration.routes
        depth = max((r.maturation_pools for r in routes), default=0)
        return {
            ROUTE_AXIS: {
                "id": ROUTE_AXIS,
                "ids": tuple(r.id for r in routes),
                "holds": "unit turnover route",
                "carries": tuple(r.precursor for r in routes),
                "at": tuple({"channel": r.population} for r in routes),
            },
            POOL_AXIS: {
                "id": POOL_AXIS,
                "ids": tuple(f"pool_{j + 1}" for j in range(depth)),
                "holds": "maturation pool",
            },
        }

    def view_events(self, spec, declaration, schedule):
        """Every scheduled rate change of each route, at its population (the entry at time 0 sets
        the starting rates). It decides no cell's life, so there are no births or retirements."""
        layer = self.VIEW_LAYERS[0]["id"]
        by_id = {r.id: r for r in declaration.routes}
        events = [
            dict(
                time=float(t),
                kind="unit turnover rates",
                layer=layer,
                at={"channel": by_id[s.route_id].population},
                label=f"{s.route_id} rates: assembly {a!r}/s, removal {r!r}/s",
            )
            for s in schedule
            for t, (a, r) in s.changes
        ]
        return tuple(sorted(events, key=lambda e: (e["time"], e["label"])))

    # ------------------------------------------------------------ definition

    def parse(self, raw, base, inner_model):
        return parse_declaration(raw, base)

    def to_dict(self, declaration, base):
        return declaration_to_dict(declaration)

    def parse_schedule(self, raw, base, declaration):
        return parse_schedule(raw, base, declaration)

    def schedule_to_dict(self, schedule, base, declaration):
        return schedule_to_dict(schedule)

    def schedule_times(self, schedule):
        return tuple(sorted({t for s in schedule for t, _ in s.changes if t > 0}))

    def value_at(self, schedule, time):
        return tuple(rates_at(s.changes, time) for s in schedule)

    def control_values(self, spec, declaration, schedule, records, indices, times):
        assembly = np.array([[a for a, _ in record] for record in records], dtype=float)
        removal = np.array([[r for _, r in record] for record in records], dtype=float)
        return assembly[indices], removal[indices]

    def routable_elements(self, declaration, field):
        """B1′: unit_assembly_rate's elements are the routes, by route ID, each at its
        population's cell, in control order."""
        return tuple((route.id, route.cell) for route in declaration.routes)

    def half_step_rows(self, declaration):
        """B1′: each route's precursor at its population's cell (assembly consumes it)."""
        return tuple(dict.fromkeys((r.precursor, r.cell) for r in declaration.routes))

    def written_species(self, declaration):
        """Its precursors, which it consumes: the registry's shared-row rule reads them
        (species_registry.check_shared_rows; FR-43 / D315)."""
        return tuple(dict.fromkeys(r.precursor for r in declaration.routes))

    def species_identities(self, declaration):
        return declaration.species

    def check_definition(self, spec, declaration, schedule, model):
        common.check_species_cap(spec, LAW_ID)
        common.check_identities(spec, LAW_ID, declaration.species)
        check_writers(spec, declaration)
        species_registry.check_shared_rows(spec, LAW_ID)
        check_rate_bound(spec, declaration, schedule)

    def inner_check_spec(self, check_spec, spec, declaration, schedule):
        return check_spec_for(check_spec, spec, declaration)

    def batch_signature(self, declaration):
        """The static structure; identities, ν, τ and the rates are not part of it."""
        return (
            LAW_ID,
            tuple(s.id for s in declaration.species),
            tuple((r.population, r.precursor, r.maturation_pools) for r in declaration.routes),
        )

    def working_size(self, spec):
        x, s = spec.execution, len(spec.model.species_ids)
        return 8 * (TERMS + 8) * (MAX_POOLS + 2) * x.channel_capacity + 8 * (s + 4) * x.capacity

    def summary(self, spec, declaration, schedule, history):
        return {
            "unit_turnover_law": LAW_ID,
            "unit_turnover_step": STEP_ID,
            "unit_turnover_species": common.summary_identities(declaration.species),
            "unit_turnover_routes": {
                r.id: dict(
                    population=r.population,
                    precursor=r.precursor,
                    molecules_per_unit=r.molecules_per_unit,
                    units_per_fmol=conversion(r),
                    maturation_pools=r.maturation_pools,
                    maturation_time_s=r.maturation_time_s,
                    initial_pool_units=list(r.initial_pool_units),
                )
                for r in declaration.routes
            },
            "unit_turnover_limits": (
                "units carry no free energy; the metabolic cost of assembly, trafficking and "
                "degradation lies outside the model; removal lumps internalisation and "
                "degradation into one first-order sink"
            ),
            "unit_turnover_rk4": "exact half-steps around the inner RK4 step",
        }

    # ------------------------------------------------------------ binding

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        return bind(spec, declaration)

    # ------------------------------------------------------------ step parts

    def statically_idle(self, p):
        return p.unit_route_row.shape[0] == 0

    def half_step(self, state, h, control, p, *, xp):
        return unit_half_step(
            state, control.unit_assembly_rate, control.unit_removal_rate, h, p, xp=xp
        )

    def control_valid(self, control, p, *, xp):
        valid = xp.asarray(True)
        for rate in (control.unit_assembly_rate, control.unit_removal_rate):
            valid &= xp.all(xp.isfinite(rate) & (rate >= 0))
        return valid

    def rates(self, state, control, p, view, *, xp):
        return {k: xp.zeros_like(getattr(state, k)) for k in self.STATE_AXES}, None, None

    def rate_checks(self, state, control, p, valid, *, xp):
        return valid & unit_domain_valid(state, p, xp=xp)

    def domain_valid(self, state, p, valid, *, xp):
        own = unit_domain_valid(state, p, xp=xp)
        return own if valid is None else valid & own

    # ------------------------------------------------------------ ledgers

    def _consumed_by_row(self, row, p, *, xp):
        """[species, cell] the precursor consumed, from the routes' cumulative amounts."""
        size = (row.amount_increment.shape[0], p.active.size)
        return scatter_add(
            xp.zeros(size), (p.unit_route_row, p.unit_route_cell), row.unit_consumed_fmol, xp=xp
        )

    def ledger_terms(self, result, row, p, *, xp):
        consumed = self._consumed_by_row(row, p, xp=xp)
        result["local"] = result["local"] + consumed
        result["total"] = result["total"] + entity_sum(consumed, axis=1, xp=xp)
        result["energy"] = result["energy"] - entity_sum(
            row.unit_turnover_work_pJ, axis=None, xp=xp
        )
        return result, self.own_ledgers(row, p, xp=xp)

    def magnitude_terms(self, magnitudes, row, p, *, xp):
        """The consumed amounts in the material ledgers and the absolute terms of the booked work
        in the energy ledger's; every term is zero without a route."""
        consumed = self._consumed_by_row(row, p, xp=xp)
        magnitudes[0] = magnitudes[0] + consumed
        magnitudes[2] = magnitudes[2] + entity_sum(consumed, axis=1, xp=xp)
        energy = entity_sum(row.unit_turnover_energy_magnitude_pJ, axis=None, xp=xp)
        magnitudes[6] = energy if magnitudes[6] is None else magnitudes[6] + energy
        return magnitudes

    def own_ledgers(self, row, p, *, xp):
        inserted = row.unit_inserted_units[p.unit_route_channel]
        if p.unit_pool_present.shape[1]:
            transit = entity_sum(row.unit_pool_units, axis=1, xp=xp)
        else:
            transit = 0.0 * row.unit_assembled_units
        return dict(
            unit_chain=row.unit_assembled_units + p.unit_route_initial_units - transit - inserted,
            unit_conversion=row.unit_assembled_units
            - p.unit_route_conversion * row.unit_consumed_fmol,
        )

    def own_magnitudes(self, row, p, *, xp):
        inserted = row.unit_inserted_units[p.unit_route_channel]
        if p.unit_pool_present.shape[1]:
            transit = entity_sum(xp.abs(row.unit_pool_units), axis=1, xp=xp)
        else:
            transit = 0.0 * row.unit_assembled_units
        assembled = xp.abs(row.unit_assembled_units)
        return (
            assembled + p.unit_route_initial_units + transit + xp.abs(inserted),
            assembled + xp.abs(p.unit_route_conversion * row.unit_consumed_fmol),
        )

    def own_bounds(self, magnitudes, steps):
        rounding = first.LEDGER_STEP_ROUNDING * np.finfo(float).eps * steps
        return tuple(UNITS_FLOOR + rounding * m for m in magnitudes)

    def external_ledger_terms(self, ledgers, row, p, *, xp):
        booked = dict(population_abundance_entity=row.unit_inserted_units - row.unit_removed_units)
        return {k: v - booked[k] for k, v in ledgers.items()}

    def external_magnitude_terms(self, magnitudes, row, p, *, xp):
        booked = dict(
            population_abundance_entity=xp.abs(row.unit_inserted_units)
            + xp.abs(row.unit_removed_units)
        )
        return {k: v + booked[k] for k, v in magnitudes.items()}
