"""Operator cells.operator.scheduled_membrane_trafficking@1: membrane retrieval and recycling (FR-2, version 1).

docs/MEMBRANE_RETRIEVAL_DESIGN.md §2, §4.1 and §9, with the user's answers and the lead's rulings
(§12; D217). Membrane moves between a cell's plasma patch and a receiving pool, the charges
following the patches. Version 1 is:
* R2: the retrieved membrane keeps its charge (R1, which strips it, is an artefact and has no
  declaration);
* F0: no fluid moves;
* D1: one lumped, well-mixed receiving pool per cell (D217), declared with the world as an FR-1
  compartment, so one route per cell (a cell's other compartments stay declared, with no route);
* retrieval and recycling: one law's two schedules;
* P0: internalised channel units are silent, held in this operator's record;
* E2: no fuel draw for the machinery. The version claims no total trafficking energy and no
  ATP-limited uptake.

A route is (compartment, owner, plasma patch). The plasma patch k of the owner i faces an outside
node o, a held bath or a finite node. The compartment's node j is bounded by its patch b, whose
inside is i (cells.operator.cell_owned_compartments@1).

Law, per stage of length tau at a route's constant rate r (m^2/s):
* Retrieval (k -> b). dA = r tau moves from k to b with dC = (C_k/A_k) dA, so k keeps its
  specific capacitance. Each population on k loses units by its declared enrichment e,
  N' = N (A_k'/A_k)^e (exact for a constant rate), and the units join the route's record.
* Recycling (b -> k). dA = r tau moves from the pool to k with dC = (C_b/A_b) dA, the pool's mean
  (well mixed). The record returns units by its declared enrichment e_r, R' = R (A_b'/A_b)^e_r.
  They join the plasma population at its own gate state: a declared rule, as insertion@2's gates
  at opening are, not a claim about the channels vesicles deliver.
* The plate charges follow the pieces (adapter.charge_following_transfer, the one split-and-merge
  kernel).
  - A piece's outside plate, -dC V_source, moves from its source's outside node to its target's,
    carried by the route's declared carriers, delta_s = t_s q / (z_s F) (adapter.carrier_scale).
    Its inside plate stays in the owner.
  - At a free node the carriers are @3's amounts. At a held bath its reservoir supplies or takes
    them (reservoir_supplied), with @3's reservoir work at the declared bath's mu.
  - The clamps' plate-charge change is electrode transfer, booked with its work.
* The heat. The kernel's merge heat is booked as heat, shared among routes by their first-order
  terms 1/2 dC (V_s - V_t)^2. A negative heat refuses the step.
* The carriers' work. Their move is a driven route (D174), booked as signed work: the exact
  chemical free-energy change at the free nodes it touched (adapter.species_chemical_free_energy_pJ,
  shared among routes by the amounts they moved there), less the held baths' RT ln c share of
  their supply. With the heat and the clamps' and reservoirs' work it closes the energy ledger.

Exactness. Within a stage every source keeps its voltage: retrieval moves only compartment
potentials, and a recycled packet leaves its pool at the pool's voltage. So one transfer equals the
continuous constant-rate process. The heat agrees too, since the clamps' and reservoirs' work is
path-independent (design §2.2). The half-step is the palindrome S_ret(h/2) S_rec(h) S_ret(h/2):
exact when one direction runs, second order when both do. A stage with no positive rate selects its
start state, so zero rates are bitwise idle.

Declared rules of version 1:
* A pump stays on its plasma patch with its aggregate capacity (insertion@1's convention), so its
  density rises as the area falls. @3's step bound has no term for its own pump.
* @3's constant-field permeability is a property of a patch's area. Retrieval takes the plasma
  patch's leak with its membrane, and the pool's patch stays leak-free (refusal 4), so the
  retrieved leak is silent, as P0's units are.
* The pool is one lumped, well-mixed compartment (D1; FR-1 §1.3's regime of validity). Pooling
  chemically or electrically different vesicles is not exact.

Bookings:
* membrane state's three increments, with this operator's per-patch and per-population
  accumulators, as insertion@1 keeps them;
* the carriers, in @3's extracellular amounts or reservoir supply (trafficking_carrier_fmol, net
  per node);
* @3's reservoir work, electrode transfer and electrode work;
* per route, the heat, the carriers' work and their magnitudes.
As the only writer of capacitances, it books the view's capacitor term
(adapter.view_capacitor_terms), as insertion@1 does. Its own ledgers: per population, the plasma
change and the record's change sum to zero (P0's conserved total); per cell, the area and the
capacitance moved between its patches each sum to zero.

Refused at the definition, each with its reason:
* the requirements: cells.operator.membrane_entity_state@1 and cells.operator.cell_owned_compartments@1 come before it;
* a route's compartment that is undeclared;
* a plasma patch that is undeclared, is not the owner's, or is a compartment's bounding patch;
* two routes on one compartment or one plasma patch: version 1's routes are disjoint;
* two routes of one cell, each into its own compartment: D1's one pool per cell (two pools would
  keep two recycling histories for one cell's membrane);
* carriers that are not distinct charged rows with transference numbers t_s > 0 summing to 1;
* enrichments and records that do not name exactly the populations on the plasma patch, each
  finite and >= 0;
* floors outside (0, declared area);
* a schedule whose areas, at every stage of the palindrome, would fall below a floor. The check is
  exact, in rational arithmetic;
* a rate that is negative, a change off the dt grid or outside [0, end), or a schedule that does
  not start at 0 or increase strictly;
* a composition outside its admitted list, which fails closed; any declared kind
  (FIXED_INNER_FIELDS: it builds @3's fixed layout); and, through the composite's structure check,
  any provider or closer of what it reads as declared (CONFLICTS_VIEW: the outside nodes' volumes
  and reference amounts, and the activity masks).
At run time the step is refused, returning its start state, on a non-finite value, a negative
rate, an area or capacitance that would not stay positive, a carrier amount that would not stay
positive at a free node, or a negative heat.

Step checks (R5). @3's bounds run on the definition with each plasma patch at its largest area
and its smallest capacitance over the schedule, the palindrome's excursions included, and with
its populations at their largest units, N0 + R0. Each pool's patch is at its smallest capacitance.
A specific capacitance always lies between the declared ones of the two patches it mixes, so the
smallest capacitance is bounded below by the smaller of them times the smallest area.
"""

from bisect import bisect_right
from dataclasses import dataclass, replace
from fractions import Fraction

import jax.numpy as jnp
import numpy as np

from cells.definitions import pump_composite_spec as composite_spec
from cells.definitions.spec_values import identifier, signed_number
from cells.definitions.specs import ConfigError, _fields, _number
from cells.laws.electrochemistry import CHARGE_PER_FMOL, F, R
from cells.models import pump_composite_adapter as adapter
from cells.models import surface_pump as first
from cells.numerics.clock_instants import ON_THE_GRID, on_grid  # D283's one predicate.
from cells.numerics.extracellular_field import scatter
from cells.numerics.species_sums import entity_sum, species_sum
from cells.operators import compartments, membrane_state
from cells.operators.contract import Operator

LAW_ID = "cells.operator.scheduled_membrane_trafficking@1"
STEP_ID = "charge_following_palindromic_half_steps@1"
EXPERIMENT_KEY = "trafficking_controls"
ROUTE_AXIS = "trafficking_route"
# Admitted beside it in version 1 (fails closed): @3 is the composite's inner model.
ADMITTED = (
    membrane_state.LAW_ID,
    compartments.LAW_ID,
    "cells.operator.scheduled_species_turnover@1",
    "cells.operator.local_species_reactions@1",
    "cells.operator.species_regulated_availability@1",
    LAW_ID,
)
INSERTION_REASON = (
    "it is a second writer of capacitances, and one operator books the view's capacitor term "
    "(insertion books it as the only writer)"
)
FLUID_REASON = "no fluid moves in version 1 (F0; FR-1's door V)"
OWNER_REASON = "an owner must not divide, close or be replaced (FR-1's doors D and R)"
UNQUALIFIED_REASON = "it is not qualified beside membrane trafficking in version 1"
REFUSED = {
    "cells.operator.scheduled_membrane_insertion@1": INSERTION_REASON,
    "cells.operator.scheduled_membrane_insertion@2": INSERTION_REASON,
    "cells.operator.isopotential_partition@1": OWNER_REASON,
    "cells.operator.cytoplasmic_bridge_closure@1": OWNER_REASON,
    "cells.operator.scheduled_cell_replacement@1": OWNER_REASON,
    "cells.operator.scheduled_cell_replacement@2": OWNER_REASON,
    "cells.operator.ideal_osmosis_linear_compliance_water@1": FLUID_REASON,
    "cells.operator.restricted_cleft_lumen@1": FLUID_REASON,
    "cells.operator.restricted_cleft_lumen@2": FLUID_REASON,
    "cells.operator.scheduled_species_exchange@1": (
        "exchange reads the declared patch areas, which membrane state provides (door S, or a "
        "current-area read)"
    ),
    "cells.operator.site_occupancy@1": (
        "sites move with their membrane only from version 1.1 (FR-3's count as state)"
    ),
    "cells.operator.scheduled_bath_composition@1": UNQUALIFIED_REASON,
    "cells.operator.electrode_current_injection@1": UNQUALIFIED_REASON,
}
# Floors of the own ledgers (membrane state's): units, m^2, F.
FLOORS = (1e-9, 1e-24, 1e-26)
SCOPE = (
    "version 1 (D217): the charges follow the patches (R2); no fluid moves (F0); one lumped, "
    "well-mixed pool per route, declared with the world (D1); retrieval and recycling; "
    "internalised units silent in this operator's record (P0); no machinery fuel draw (E2), so no "
    "total trafficking energy and no ATP-limited uptake are claimed; pumps held on the plasma "
    "patch with their aggregate capacity; the retrieved leak silent in the pool"
)

STATE_AXES = {
    "trafficking_area_m2": ["membrane_slot"],  # Net area change written per patch.
    "trafficking_capacitance_F": ["membrane_slot"],  # Net capacitance change written per patch.
    "trafficking_units": ["channel_slot"],  # Net unit change written per plasma population.
    "trafficking_retrieved_m2": [ROUTE_AXIS],  # Area retrieved (gross).
    "trafficking_recycled_m2": [ROUTE_AXIS],  # Area recycled (gross).
    "trafficking_internalised_units": [ROUTE_AXIS, "channel_slot"],  # P0's record, from R0.
    "trafficking_carrier_fmol": ["species", "extracellular_slot"],  # Net carriers moved in.
    "trafficking_image_charge_C": ["extracellular_slot"],  # Sum of |clamp transfer| booked.
    "trafficking_dissipated_energy_pJ": [ROUTE_AXIS],  # The merge heat.
    "trafficking_work_pJ": [ROUTE_AXIS],  # The carriers' signed chemical work.
    "trafficking_energy_magnitude_pJ": [ROUTE_AXIS],  # Magnitudes of the energy bookings.
}
LAYOUT_FIELDS = (
    "trafficking_route_plasma",  # [route] int64: the plasma patch's slot.
    "trafficking_route_pool",  # [route] int64: the compartment's bounding patch's slot.
    "trafficking_carrier_scale",  # [route, species]: fmol each row carries per coulomb.
    "trafficking_retrieval_enrichment",  # [route, channel]: e, 0 off the route's patch.
    "trafficking_recycling_enrichment",  # [route, channel]: e_r, 0 off the route's patch.
    "trafficking_internalised_reference",  # [route, channel]: R0, the record at time 0.
)
CONTROL_FIELDS = ("trafficking_retrieval_rate_m2_s", "trafficking_recycling_rate_m2_s")
ROUTE_FIELDS = {
    "id",
    "plasma_patch",
    "compartment",
    "carriers",
    "plasma_area_floor_m2",
    "pool_area_floor_m2",
    "retrieval_enrichment",
    "recycling_enrichment",
    "internalised_units",
}


@dataclass(frozen=True)
class Route:
    id: str
    plasma_patch: str
    compartment: str  # The compartment's own ID (cells.operator.cell_owned_compartments@1).
    carriers: tuple  # ((species id, transference number), ...)
    plasma_area_floor_m2: float
    pool_area_floor_m2: float
    retrieval_enrichment: tuple  # ((channel id, e), ...), the plasma patch's populations
    recycling_enrichment: tuple  # ((channel id, e_r), ...)
    internalised_units: tuple  # ((channel id, R0), ...)


@dataclass(frozen=True)
class Trafficking:
    law: str
    routes: tuple


@dataclass(frozen=True)
class RateChange:
    time: float
    rate_m2_per_s: float


@dataclass(frozen=True)
class RouteSchedule:
    route_id: str
    retrieval: tuple  # RateChange, from time 0
    recycling: tuple  # RateChange, from time 0


# ------------------------------------------------------------------ definition


def _populations(value, channels, what, route):
    """{channel: value >= 0} naming exactly the populations on the route's plasma patch."""
    if type(value) is not dict:
        raise ConfigError(f"{LAW_ID}: route {route}'s {what} is an explicit object")
    if set(value) != set(channels):
        raise ConfigError(
            f"{LAW_ID}: route {route}'s {what} names exactly the populations on its plasma "
            f"patch, {sorted(channels)}, not {sorted(value)}"
        )
    return tuple((c, _number(value[c], f"route {route}'s {what} of {c}")) for c in channels)


def parse_trafficking(raw, base):
    """The declaration (host side)."""
    _fields(raw, {"law", "routes"}, "membrane trafficking")
    if raw["law"] != LAW_ID:
        raise ConfigError("Membrane trafficking requires law " + LAW_ID)
    if type(raw["routes"]) is not list or not raw["routes"]:
        raise ConfigError(f"{LAW_ID} declares its routes in a non-empty list")
    m = base.model
    membranes = [p.id for p in m.membranes]
    valence = dict(zip(m.species_ids, m.valence, strict=True))
    rows = {s: i for i, s in enumerate(m.species_ids)}
    routes = []
    for entry in raw["routes"]:
        _fields(entry, ROUTE_FIELDS, "trafficking route")
        rid = identifier(entry["id"])
        patch = identifier(entry["plasma_patch"])
        if patch not in membranes:
            raise ConfigError(f"{LAW_ID}: route {rid}'s plasma patch {patch!r} is not declared")
        compartment = identifier(entry["compartment"])
        carriers = entry["carriers"]
        if type(carriers) is not dict:
            raise ConfigError(f"{LAW_ID}: route {rid}'s carriers are an object {{species: t}}")
        unknown = sorted(s for s in carriers if s not in rows)
        if unknown:
            raise ConfigError(f"{LAW_ID}: route {rid} names an undeclared carrier {unknown[0]!r}")
        pairs = tuple(
            (s, _number(t, f"route {rid}'s transference number")) for s, t in carriers.items()
        )
        adapter.check_carriers(
            [rows[s] for s, _ in pairs],
            [t for _, t in pairs],
            [valence[s] for s in m.species_ids],
            f"{LAW_ID}: route {rid}",
        )
        channels = [c.id for c in m.channels if c.membrane_id == patch]
        routes.append(
            Route(
                rid,
                patch,
                compartment,
                pairs,
                _number(entry["plasma_area_floor_m2"], "plasma area floor", positive=True),
                _number(entry["pool_area_floor_m2"], "pool area floor", positive=True),
                _populations(entry["retrieval_enrichment"], channels, "retrieval enrichment", rid),
                _populations(entry["recycling_enrichment"], channels, "recycling enrichment", rid),
                _populations(entry["internalised_units"], channels, "internalised units", rid),
            )
        )
    for key, what in (
        ("id", "ID"),
        ("plasma_patch", "plasma patch"),
        ("compartment", "compartment"),
    ):
        values = [getattr(r, key) for r in routes]
        if len(set(values)) != len(values):
            raise ConfigError(
                f"{LAW_ID}: two routes share a {what}; version 1's routes are disjoint (a shared "
                "pool would recycle one patch's units to another, and a shared plasma patch needs "
                "one floor and a joint split)"
            )
    return Trafficking(LAW_ID, tuple(routes))


def trafficking_to_dict(declaration):
    if type(declaration) is not Trafficking or any(
        type(r) is not Route for r in declaration.routes
    ):
        raise ConfigError("Require explicit immutable membrane trafficking declaration types")
    return dict(
        law=declaration.law,
        routes=[
            dict(
                id=r.id,
                plasma_patch=r.plasma_patch,
                compartment=r.compartment,
                carriers=dict(r.carriers),
                plasma_area_floor_m2=r.plasma_area_floor_m2,
                pool_area_floor_m2=r.pool_area_floor_m2,
                retrieval_enrichment=dict(r.retrieval_enrichment),
                recycling_enrichment=dict(r.recycling_enrichment),
                internalised_units=dict(r.internalised_units),
            )
            for r in declaration.routes
        ],
    )


def _changes(raw, what, route, dt, end):
    """A rate schedule: from time 0, strictly increasing, on the dt grid, before the end."""
    if type(raw) is not list or not raw:
        raise ConfigError(f"{LAW_ID}: route {route}'s {what} schedule is a non-empty list")
    changes = []
    for change in raw:
        _fields(change, {"time", "rate_m2_per_s"}, f"{what} rate change")
        time = _number(change["time"], f"{what} change time")
        rate = signed_number(change["rate_m2_per_s"], f"{what} rate")
        if rate < 0:
            raise ConfigError(
                f"{LAW_ID}: route {route} has a negative {what} rate; the direction is the "
                "schedule's (retrieval or recycling), so every rate is >= 0"
            )
        if on_grid(time, dt) is None:
            raise ConfigError(f"{LAW_ID}: a schedule change must be {ON_THE_GRID}")
        if not 0.0 <= time < end:
            raise ConfigError(f"{LAW_ID}: a schedule change lies at or beyond the end time")
        changes.append(RateChange(time, rate))
    times = [c.time for c in changes]
    if times[0] != 0.0 or any(b <= a for a, b in zip(times, times[1:], strict=False)):
        raise ConfigError(
            f"{LAW_ID}: route {route}'s {what} schedule starts at time 0 with increasing times"
        )
    return tuple(changes)


def parse_controls(raw, base, declaration):
    """One retrieval and one recycling schedule per route, in declaration order (host side)."""
    entries = raw[EXPERIMENT_KEY]
    if type(entries) is not list:
        raise ConfigError(f"{EXPERIMENT_KEY} is an explicit list")
    dt, end = base.execution.dt, base.experiment.end_time
    declared = [r.id for r in declaration.routes]
    by_route = {}
    for entry in entries:
        _fields(entry, {"route_id", "retrieval", "recycling"}, "trafficking control")
        rid = entry["route_id"]
        if rid not in declared:
            raise ConfigError(f"{LAW_ID}: a schedule names an undeclared route {rid!r}")
        if rid in by_route:
            raise ConfigError(f"{LAW_ID}: one schedule per route ({rid})")
        by_route[rid] = RouteSchedule(
            rid,
            _changes(entry["retrieval"], "retrieval", rid, dt, end),
            _changes(entry["recycling"], "recycling", rid, dt, end),
        )
    if set(by_route) != set(declared):
        raise ConfigError(f"{LAW_ID}: every route, and only those, has a schedule")
    return tuple(by_route[r] for r in declared)


def controls_to_dict(schedule):
    if any(type(s) is not RouteSchedule for s in schedule):
        raise ConfigError("Require explicit immutable trafficking schedule types")
    return {
        EXPERIMENT_KEY: [
            dict(
                route_id=s.route_id,
                retrieval=[dict(time=c.time, rate_m2_per_s=c.rate_m2_per_s) for c in s.retrieval],
                recycling=[dict(time=c.time, rate_m2_per_s=c.rate_m2_per_s) for c in s.recycling],
            )
            for s in schedule
        ]
    }


def rate_at(changes, time):
    return changes[bisect_right([c.time for c in changes], time) - 1].rate_m2_per_s


def compartment_map(spec):
    """{compartment ID: compartments.Compartment} of the definition's declaration (host)."""
    found = {}
    for op, declaration, _ in composite_spec.entries(spec):
        if op.LAW_ID == compartments.LAW_ID:
            found.update({c.id: c for c in declaration.compartments})
    return found


def resolved_routes(spec, declaration):
    """((route, plasma patch, pool patch, compartment), ...), each route checked against the
    compartments' declaration, and at most one route per owner cell (D1) (host). The composite
    binds before it runs the operators' definition checks, so binding calls this too, and every
    refusal here fires with its reason."""
    pools = compartment_map(spec)
    bounding = {c.patch for c in pools.values()}
    membranes = {p.id: p for p in spec.model.membranes}
    out = []
    for route in declaration.routes:
        pool = pools.get(route.compartment)
        if pool is None:
            raise ConfigError(
                f"{LAW_ID}: route {route.id}'s compartment {route.compartment!r} is not declared "
                f"by {compartments.LAW_ID}"
            )
        plasma = membranes[route.plasma_patch]
        if plasma.inside != pool.owner:
            raise ConfigError(
                f"{LAW_ID}: route {route.id}'s plasma patch {plasma.id!r} lies on "
                f"{plasma.inside!r}, not on its compartment's owner {pool.owner!r}"
            )
        # A patch facing a compartment's node is its bounding patch (compartments' refusal 2).
        if plasma.id in bounding:
            raise ConfigError(
                f"{LAW_ID}: route {route.id}'s plasma patch {plasma.id!r} is a compartment's "
                "bounding patch; trafficking between compartments is later work"
            )
        out.append((route, plasma, membranes[pool.patch], pool))
    owners = [pool.owner for *_, pool in out]
    shared = next((owner for owner in owners if owners.count(owner) > 1), None)
    if shared is not None:
        raise ConfigError(
            f"{LAW_ID}: two routes fill receiving pools of one cell, {shared!r}; version 1 holds "
            "one lumped, well-mixed receiving pool per cell (D1, D217), so a cell has one route "
            "(its other compartments stay declared, with no route)"
        )
    return tuple(out)


def area_bounds(schedule, plasma_m2, pool_m2, dt, end):
    """(plasma min, plasma max, pool min, pool max) over every stage of the palindrome, exact.

    Between rate changes both areas move linearly at the net rate r_ret - r_rec. Within one
    half-step h = dt/2 the stages S_ret(h/2) S_rec(h) S_ret(h/2) leave that line by at most
    max(0, min(r_ret/2, r_rec - r_ret/2)) h, below at the source and above at the target, so each
    extreme is the line's, at a segment's end, widened by that excursion. Fractions keep it exact.
    """
    times = sorted({0.0, *(c.time for c in (*schedule.retrieval, *schedule.recycling)), end})
    a, b = Fraction(plasma_m2), Fraction(pool_m2)
    h = Fraction(dt) / 2
    bounds = [a, a, b, b]
    for t0, t1 in zip(times, times[1:], strict=False):
        r1 = Fraction(rate_at(schedule.retrieval, t0))
        r2 = Fraction(rate_at(schedule.recycling, t0))
        excursion = max(Fraction(0), min(r1 / 2, r2 - r1 / 2)) * h
        moved = (r1 - r2) * (Fraction(t1) - Fraction(t0))
        a1, b1 = a - moved, b + moved
        bounds = [
            min(bounds[0], min(a, a1) - excursion),
            max(bounds[1], max(a, a1) + excursion),
            min(bounds[2], min(b, b1) - excursion),
            max(bounds[3], max(b, b1) + excursion),
        ]
        a, b = a1, b1
    return tuple(bounds)


def check_definition(spec, declaration, schedule):
    """The composition rules and the routes against the compartments' declaration (host)."""
    for op, _, _ in composite_spec.entries(spec):
        if op.LAW_ID not in ADMITTED:
            reason = REFUSED.get(op.LAW_ID, "it is not on version 1's admitted list (fails closed)")
            raise ConfigError(
                f"{LAW_ID} composes only with {', '.join(ADMITTED[:-1])}; {op.LAW_ID} is "
                f"refused: {reason}"
            )
    dt, end = spec.execution.dt, spec.experiment.end_time
    resolved = resolved_routes(spec, declaration)
    for (route, plasma, bound, _), plan in zip(resolved, schedule, strict=True):
        for floor, declared, what in (
            (route.plasma_area_floor_m2, plasma.area_m2, "plasma"),
            (route.pool_area_floor_m2, bound.area_m2, "pool"),
        ):
            if not floor < declared:
                raise ConfigError(
                    f"{LAW_ID}: route {route.id}'s {what} area floor {floor} m^2 is not below the "
                    f"declared area {declared} m^2"
                )
        low, _, pool_low, _ = area_bounds(plan, plasma.area_m2, bound.area_m2, dt, end)
        for value, floor, what in (
            (low, route.plasma_area_floor_m2, "plasma patch"),
            (pool_low, route.pool_area_floor_m2, "pool"),
        ):
            if value < Fraction(floor):
                raise ConfigError(
                    f"{LAW_ID}: route {route.id}'s schedule takes its {what} below its area floor "
                    f"(to {float(value)} m^2, against {floor} m^2; refused, never clipped)"
                )


def check_spec_for(check_spec, spec, declaration, schedule):
    """R5: the definition @3's bounds read (module docstring), on the given check spec."""
    densities = {}
    for op, block, _ in composite_spec.entries(spec):
        if op.LAW_ID == membrane_state.LAW_ID:
            densities = {p.channel_id: p.reference_density_per_m2 for p in block.populations}
    m = check_spec.model
    declared = {p.id: p for p in spec.model.membranes}
    dt, end = spec.execution.dt, spec.experiment.end_time
    membranes, abundance = {}, {}
    resolved = resolved_routes(spec, declaration)
    for (route, plasma, bound, _), plan in zip(resolved, schedule, strict=True):
        low, high, pool_low, _ = area_bounds(plan, plasma.area_m2, bound.area_m2, dt, end)
        specific = min(plasma.capacitance_F / plasma.area_m2, bound.capacitance_F / bound.area_m2)
        membranes[plasma.id] = (float(high), specific * float(low))
        membranes[bound.id] = (declared[bound.id].area_m2, specific * float(pool_low))
        record = dict(route.internalised_units)
        for c in spec.model.channels:
            if c.membrane_id == plasma.id:
                rho = densities[c.id]
                units = c.abundance * plasma.area_m2 * rho + record[c.id]
                abundance[c.id] = units / (float(high) * rho)
    return replace(
        check_spec,
        model=replace(
            m,
            membranes=tuple(
                replace(p, area_m2=membranes[p.id][0], capacitance_F=membranes[p.id][1])
                if p.id in membranes
                else p
                for p in m.membranes
            ),
            channels=tuple(
                replace(c, abundance=abundance[c.id]) if c.id in abundance else c
                for c in m.channels
            ),
        ),
    )


def bind(spec, declaration):
    m, x = spec.model, spec.execution
    nm, nc, o = x.membrane_capacity, x.channel_capacity, x.extracellular_capacity
    species = list(m.species_ids)
    membranes = [p.id for p in m.membranes]
    channels = [c.id for c in m.channels]
    n = len(declaration.routes)
    rows = {s: i for i, s in enumerate(species)}
    layout = dict(
        trafficking_route_plasma=np.zeros(n, dtype=np.int64),
        trafficking_route_pool=np.zeros(n, dtype=np.int64),
        trafficking_carrier_scale=np.zeros((n, len(species))),
        trafficking_retrieval_enrichment=np.zeros((n, nc)),
        trafficking_recycling_enrichment=np.zeros((n, nc)),
        trafficking_internalised_reference=np.zeros((n, nc)),
    )
    for t, (route, _, bound, _) in enumerate(resolved_routes(spec, declaration)):
        layout["trafficking_route_plasma"][t] = membranes.index(route.plasma_patch)
        layout["trafficking_route_pool"][t] = membranes.index(bound.id)
        layout["trafficking_carrier_scale"][t] = adapter.carrier_scale(
            [rows[s] for s, _ in route.carriers],
            [v for _, v in route.carriers],
            list(m.valence),
            len(species),
        )
        for key, pairs in (
            ("trafficking_retrieval_enrichment", route.retrieval_enrichment),
            ("trafficking_recycling_enrichment", route.recycling_enrichment),
            ("trafficking_internalised_reference", route.internalised_units),
        ):
            for channel, value in pairs:
                layout[key][t, channels.index(channel)] = value
    sizes = {
        "membrane_slot": nm,
        "channel_slot": nc,
        "extracellular_slot": o,
        "species": len(species),
        ROUTE_AXIS: n,
    }
    state = {k: np.zeros([sizes[a] for a in axes]) for k, axes in STATE_AXES.items()}
    state["trafficking_internalised_units"] = layout["trafficking_internalised_reference"].copy()
    return state, layout


# ------------------------------------------------------------------ the law


def capacitor_view(state, p, *, xp):
    """(@3's layout with membrane state's capacitances, field arrays refreshed; the declared
    layout): insertion@1's capacitor view without its masks."""
    bound = adapter.inner_layout(p)
    view = bound._replace(membrane_capacitance=membrane_state.capacitance(state, p, xp=xp))
    return adapter.refresh_field(view, bound, xp=xp), bound


def _indicator(condition, *, xp):
    return xp.where(condition, 1.0, 0.0)


def _per_route(values, *, xp):
    """[route] sums of [route, species, outside] values: the species first (species_sum), then
    the nodes (an entity sum). Every sum here is one of D182's two (the species axis by
    species_sum, the routes and nodes by entity_sum, each listed in
    tests/species_sum_entity_sums.json); tests/unit/test_species_sum_sites.py refuses any other."""
    by_node = species_sum(xp.moveaxis(values, 1, 0), xp=xp)  # [route, outside]
    return entity_sum(by_node, axis=1, xp=xp)


def stage(state, tau, rate, p, retrieval, *, xp=jnp):
    """(state after one stage of length tau at the routes' rates [route], valid): retrieval
    (plasma -> pool) when `retrieval`, else recycling (pool -> plasma); module docstring."""
    plasma, pool = p.trafficking_route_plasma, p.trafficking_route_pool
    source, target = (plasma, pool) if retrieval else (pool, plasma)
    area = membrane_state.area(state, p, xp=xp)
    capacitance = membrane_state.capacitance(state, p, xp=xp)
    source_area = area[source]
    da = rate * tau
    dc = capacitance[source] * (da / source_area)  # The source keeps its specific capacitance.
    shrink = xp.log1p(-da / source_area)  # log(A'/A) of each source.
    if retrieval:
        enrichment = p.trafficking_retrieval_enrichment
        units = membrane_state.units(state, p, xp=xp)[None, :]  # Plasma units [1, channel].
    else:
        enrichment = p.trafficking_recycling_enrichment
        units = state.trafficking_internalised_units  # The record [route, channel].
    moved = -units * xp.expm1(enrichment * shrink[:, None])  # [route, channel], >= 0.
    sign = -1.0 if retrieval else 1.0  # Plasma units: lost to the record, or returned.
    unit_change = sign * entity_sum(moved, axis=0, xp=xp)  # Over routes.
    record = state.trafficking_internalised_units - sign * moved
    nm = area.size
    area_change = scatter(da, xp.zeros(nm), (target,), xp=xp) - scatter(
        da, xp.zeros(nm), (source,), xp=xp
    )
    capacitance_change = scatter(dc, xp.zeros(nm), (target,), xp=xp) - scatter(
        dc, xp.zeros(nm), (source,), xp=xp
    )
    # The charges follow the pieces: one kernel call for every route. A piece as large as its
    # source, or a negative one (a negative rate), refuses the step (below); the kernel sees only
    # admissible pieces, so the host path refuses them as the device does, never factorising a
    # patch left with no capacitance or taking the root of a negative piece.
    admissible = (da >= 0) & (da < source_area)
    view, bound = capacitor_view(state, p, xp=xp)
    pieces = xp.where(admissible, dc, 0.0)
    out = adapter.charge_following_transfer(state, view, source, target, pieces, bound, xp=xp)
    nodes = xp.arange(p.outside_active.size)
    direction = _indicator(p.membrane_outside[target][:, None] == nodes[None, :], xp=xp)
    direction = direction - _indicator(p.membrane_outside[source][:, None] == nodes[None, :], xp=xp)
    # Each route's carriers of its pieces' outside plates, -plate_C, moved source -> target node.
    carried = p.trafficking_carrier_scale * (-out.plate_C)[:, None]  # [route, species]
    contribution = carried[:, :, None] * direction[:, None, :]  # [route, species, outside]
    moved_nodes = entity_sum(contribution, axis=0, xp=xp)  # Over routes: [species, outside]
    held = p.reservoir & p.outside_active
    free = p.outside_active & ~p.reservoir
    amounts = p.extracellular_amount_reference + state.extracellular_amount_increment
    extracellular = state.extracellular_amount_increment + xp.where(free, moved_nodes, 0.0)
    supplied = xp.where(held, -moved_nodes, 0.0)  # The reservoir supplies what its node gives.
    # @3's reservoir work at the declared bath (its own mu), and its chemical part per route.
    concentration = xp.where(
        p.outside_active, p.extracellular_amount_reference / p.extracellular_volume, 1.0
    )
    chemical = R * p.temperature * xp.log(concentration)  # [species, outside], J/mol
    mu = chemical + p.valence * F * p.boundary_V
    reservoir_work = 1e-3 * species_sum(mu * supplied, xp=xp)  # [outside], pJ
    supplied_routes = xp.where(held, -contribution, 0.0)  # [route, species, outside]
    reservoir_chemical = 1e-3 * _per_route(chemical[None] * supplied_routes, xp=xp)
    # The exact chemical free-energy change at the free nodes, shared by the amounts moved there.
    anchor = xp.where(free, amounts, 1.0)
    change = xp.where(free, moved_nodes, 0.0)
    volume, temperature = p.extracellular_volume, p.temperature
    dg = adapter.species_chemical_free_energy_pJ(anchor, change, volume, temperature, xp=xp)
    dg_magnitude = adapter.species_chemical_magnitude_pJ(anchor, change, volume, temperature, xp=xp)
    weight = xp.where(free, xp.abs(contribution), 0.0)
    total = entity_sum(weight, axis=0, xp=xp)  # Over routes.
    share = xp.where(total > 0, weight / xp.where(total > 0, total, 1.0), 0.0)
    work = _per_route(share * dg[None], xp=xp) - reservoir_chemical  # [route], pJ
    # The merge heat, shared by the first-order terms.
    jump = out.before_V[source] - out.before_V[target]
    first_order = 0.5e12 * dc * jump**2
    whole = entity_sum(first_order, axis=None, xp=xp)  # Over routes.
    positive = whole > 0
    heat_share = xp.where(positive, first_order / xp.where(positive, whole, 1.0), 0.0)
    heat = out.heat_pJ * heat_share
    electrode = out.electrode_C
    electrode_work = 1e12 * p.boundary_V * electrode
    flows = entity_sum(xp.abs(electrode_work), axis=None, xp=xp) + entity_sum(
        xp.abs(reservoir_work), axis=None, xp=xp
    )  # Over nodes.
    magnitude = (
        first_order
        + _per_route(share * dg_magnitude[None], xp=xp)
        + xp.abs(reservoir_chemical)
        + heat_share * flows
    )
    gross = "trafficking_retrieved_m2" if retrieval else "trafficking_recycled_m2"
    new = state._replace(
        membrane_area_increment_m2=state.membrane_area_increment_m2 + area_change,
        membrane_capacitance_increment_F=state.membrane_capacitance_increment_F
        + capacitance_change,
        population_abundance_increment=state.population_abundance_increment + unit_change,
        extracellular_amount_increment=extracellular,
        reservoir_supplied=state.reservoir_supplied + supplied,
        reservoir_work_pJ=state.reservoir_work_pJ + reservoir_work,
        electrode_charge_transferred_C=state.electrode_charge_transferred_C + electrode,
        electrode_work_pJ=state.electrode_work_pJ + electrode_work,
        trafficking_area_m2=state.trafficking_area_m2 + area_change,
        trafficking_capacitance_F=state.trafficking_capacitance_F + capacitance_change,
        trafficking_units=state.trafficking_units + unit_change,
        trafficking_internalised_units=record,
        trafficking_carrier_fmol=state.trafficking_carrier_fmol + moved_nodes,
        trafficking_image_charge_C=state.trafficking_image_charge_C + xp.abs(electrode),
        trafficking_dissipated_energy_pJ=state.trafficking_dissipated_energy_pJ + heat,
        trafficking_work_pJ=state.trafficking_work_pJ + work,
        trafficking_energy_magnitude_pJ=state.trafficking_energy_magnitude_pJ + magnitude,
        **{gross: getattr(state, gross) + da},
    )
    rates_ok = xp.all(xp.isfinite(rate)) & xp.all(rate >= 0)
    valid = rates_ok & xp.all(admissible)
    valid &= xp.isfinite(out.heat_pJ) & (out.heat_pJ >= 0)  # Strict: no tolerance (kernel item).
    for value in (out.plate_C, electrode, carried, work, magnitude, record, unit_change):
        valid &= xp.all(xp.isfinite(value))
    valid &= xp.all(record >= 0)
    after = p.extracellular_amount_reference + extracellular
    valid &= xp.all(xp.where(free, after > 0, True))
    flowing = xp.any(rate > 0)  # No rate: select the start state (bitwise idle).
    # A refused stage keeps its start state too, so the palindrome's later stages never run from
    # an inadmissible one; the step's validity carries the refusal (never a repair).
    keep = flowing & valid
    selected = type(state)(*(xp.where(keep, a, b) for a, b in zip(new, state, strict=True)))
    return selected, xp.where(flowing, valid, rates_ok)


def trafficked(state, h, control, p, *, xp=jnp):
    """(state after h of trafficking, valid): the palindrome S_ret(h/2) S_rec(h) S_ret(h/2)."""
    retrieval = control.trafficking_retrieval_rate_m2_s
    recycling = control.trafficking_recycling_rate_m2_s
    state, first_ok = stage(state, 0.5 * h, retrieval, p, True, xp=xp)
    state, middle_ok = stage(state, h, recycling, p, False, xp=xp)
    state, last_ok = stage(state, 0.5 * h, retrieval, p, True, xp=xp)
    return state, first_ok & middle_ok & last_ok


def _route_masks(p, *, xp):
    """(patches [membrane], populations [route, channel], carrier nodes [species, outside]): the
    entries a route may write."""
    plasma, pool = p.trafficking_route_plasma, p.trafficking_route_pool
    slots = xp.arange(p.membrane_area.size)
    patches = xp.any(
        (slots[None, :] == plasma[:, None]) | (slots[None, :] == pool[:, None]), axis=0
    )
    populations = (p.channel_membranes[None, :] == plasma[:, None]) & p.channel_active[None, :]
    nodes = xp.arange(p.outside_active.size)
    touched = (nodes[None, :] == p.membrane_outside[plasma][:, None]) | (
        nodes[None, :] == p.membrane_outside[pool][:, None]
    )  # [route, outside]
    carriers = p.trafficking_carrier_scale != 0  # [route, species]
    reach = xp.any(carriers[:, :, None] & touched[:, None, :], axis=0)
    return patches, populations, reach


def own_valid(state, p, *, xp):
    patches, populations, reach = _route_masks(p, xp=xp)
    valid = xp.asarray(True)
    for name in STATE_AXES:
        valid &= xp.all(xp.isfinite(getattr(state, name)))
    for name, mask in (
        ("trafficking_area_m2", patches),
        ("trafficking_capacitance_F", patches),
        ("trafficking_units", xp.any(populations, axis=0)),
        ("trafficking_internalised_units", populations),
        ("trafficking_carrier_fmol", reach),
        ("trafficking_image_charge_C", p.reservoir & p.outside_active),
    ):
        valid &= xp.all(xp.where(mask, True, getattr(state, name) == 0))
    for name in (
        "trafficking_retrieved_m2",
        "trafficking_recycled_m2",
        "trafficking_internalised_units",
        "trafficking_image_charge_C",
        "trafficking_dissipated_energy_pJ",
        "trafficking_energy_magnitude_pJ",
    ):
        valid &= xp.all(getattr(state, name) >= 0)
    return valid


def own_ledgers(row, p, *, xp):
    """P0's conserved total per population, and the area and capacitance per cell (each 0)."""
    cells = xp.zeros(p.active.size)
    record = row.trafficking_internalised_units - p.trafficking_internalised_reference
    return dict(
        trafficking_units=row.trafficking_units + entity_sum(record, axis=0, xp=xp),  # Routes.
        trafficking_area=scatter(row.trafficking_area_m2, cells, (p.membrane_cell,), xp=xp),
        trafficking_capacitance=scatter(
            row.trafficking_capacitance_F, cells, (p.membrane_cell,), xp=xp
        ),
    )


def booked(row):
    """Membrane state's accepted ledgers, as this operator books them."""
    return dict(
        membrane_area_entity=row.trafficking_area_m2,
        membrane_capacitance_entity=row.trafficking_capacitance_F,
        population_abundance_entity=row.trafficking_units,
    )


class ScheduledMembraneTrafficking(Operator):
    LAW_ID = LAW_ID
    STEP_ID = STEP_ID
    SPLIT = True
    RK4 = "split"
    STATE_AXES = STATE_AXES
    HEAT_FIELDS = ("trafficking_dissipated_energy_pJ",)
    WORK_FIELDS = ("trafficking_work_pJ",)
    LAYOUT_FIELDS = LAYOUT_FIELDS
    CONTROL_FIELDS = CONTROL_FIELDS
    EXPERIMENT_KEYS = (EXPERIMENT_KEY,)
    VIEW_READS = ("membrane_area", "membrane_capacitance", "channel_abundance")
    # Read as declared: the outside nodes' volumes and reference amounts (the free nodes' exact
    # free-energy change, a held bath's mu) and the activity masks of its capacitor view.
    CONFLICTS_VIEW = (
        "extracellular_volume",
        "extracellular_amount_reference",
        "active",
        "outside_active",
        "membrane_active",
    )
    ENTITY_WRITES = {
        "membrane_area_increment_m2": ("trafficking_area_m2",),
        "membrane_capacitance_increment_F": ("trafficking_capacitance_F",),
        "population_abundance_increment": ("trafficking_units",),
        "extracellular_amount_increment": ("trafficking_carrier_fmol",),
        "reservoir_supplied": ("trafficking_carrier_fmol",),
        "reservoir_work_pJ": ("trafficking_carrier_fmol", "trafficking_energy_magnitude_pJ"),
        "electrode_charge_transferred_C": ("trafficking_image_charge_C",),
        "electrode_work_pJ": (
            "trafficking_dissipated_energy_pJ",
            "trafficking_energy_magnitude_pJ",
        ),
    }
    REQUIRES = (membrane_state.LAW_ID, compartments.LAW_ID)
    # It builds @3's fixed layout (adapter.inner_layout), so the composite refuses it beside any
    # declared kind: version 1 refuses every kind (kinds on its patches would read the declared
    # capacitance in their definition-time bounds), narrowed after B1's axes and hosts.
    FIXED_INNER_FIELDS = True
    IDENTITY_ROLE = "user"  # It names @3's ion rows; it declares no species.
    LEDGERS = ("trafficking_units", "trafficking_area", "trafficking_capacitance")
    LEDGER_DIAGNOSTICS = (
        "trafficking_unit_balance_error",
        "trafficking_area_balance_error_m2",
        "trafficking_capacitance_balance_error_F",
    )
    LEDGER_MESSAGE = "Membrane trafficking accounting failed: "
    # The run view (docs/RUN_VIEW_DESIGN.md §3): scheduled rates, prescribed.
    VIEW_LAYERS = (
        {"id": "trafficking", "label": "Membrane trafficking", "representation": "prescribed"},
    )
    UNITS = {"trafficking_units": "units", "trafficking_internalised_units": "units"}
    RECORD_KINDS = {
        "trafficking_area_m2": "cumulative",
        "trafficking_capacitance_F": "cumulative",
        "trafficking_units": "cumulative",
        "trafficking_retrieved_m2": "cumulative",
        "trafficking_recycled_m2": "cumulative",
        "trafficking_internalised_units": "amount",
        "trafficking_carrier_fmol": "cumulative",
        "trafficking_image_charge_C": "cumulative",
        "trafficking_energy_magnitude_pJ": "cumulative",
    }
    ORIENTATION = {
        "trafficking_retrieved_m2": {
            "from": "plasma",
            "to": "pool",
            "says": (
                "a route's retrieved area leaves its plasma patch for its pool's bounding patch"
            ),
        },
        "trafficking_recycled_m2": {
            "from": "pool",
            "to": "plasma",
            "says": "a route's recycled area leaves its pool's bounding patch for its plasma patch",
        },
    }

    def view_sets(self, spec, declaration):
        """The run view's set of its route axis: each route on its plasma patch, with its roles."""
        routes = declaration.routes
        return {
            ROUTE_AXIS: {
                "id": ROUTE_AXIS,
                "ids": tuple(r.id for r in routes),
                "holds": "trafficking route",
                "on": ("membrane", tuple(r.plasma_patch for r in routes)),
                "roles": {
                    "plasma": "the route's plasma patch",
                    "pool": "its compartment's bounding patch",
                },
            }
        }

    def view_events(self, spec, declaration, schedule):
        """Every scheduled rate of each route, at its plasma patch (the entry at time 0 sets the
        starting rate). Trafficking decides no cell's life, so there are no births or
        retirements to keep."""
        layer = self.VIEW_LAYERS[0]["id"]
        events = [
            dict(
                time=float(c.time),
                kind=f"{what} rate",
                layer=layer,
                at={"membrane": route.plasma_patch},
                label=f"{route.id} {what} rate: {c.rate_m2_per_s!r} m2/s",
            )
            for route, plan in zip(declaration.routes, schedule, strict=True)
            for what, changes in (("retrieval", plan.retrieval), ("recycling", plan.recycling))
            for c in changes
        ]
        return tuple(sorted(events, key=lambda e: (e["time"], e["label"])))

    # ------------------------------------------------------------ definition

    def parse(self, raw, base, inner_model):
        return parse_trafficking(raw, base)

    def to_dict(self, declaration, base):
        return trafficking_to_dict(declaration)

    def parse_schedule(self, raw, base, declaration):
        return parse_controls(raw, base, declaration)

    def schedule_to_dict(self, schedule, base, declaration):
        return controls_to_dict(schedule)

    def schedule_times(self, schedule):
        """The rate changes after time 0 (on the dt grid, checked when parsed)."""
        times = {c.time for s in schedule for c in (*s.retrieval, *s.recycling) if c.time > 0}
        return tuple(sorted(times))

    def value_at(self, schedule, time):
        return tuple((rate_at(s.retrieval, time), rate_at(s.recycling, time)) for s in schedule)

    def control_values(self, spec, declaration, schedule, records, indices, times):
        retrieval = np.array([[r for r, _ in record] for record in records], dtype=float)
        recycling = np.array([[r for _, r in record] for record in records], dtype=float)
        return retrieval[indices], recycling[indices]

    def check_definition(self, spec, declaration, schedule, model):
        check_definition(spec, declaration, schedule)

    def inner_check_spec(self, check_spec, spec, declaration, schedule):
        return check_spec_for(check_spec, spec, declaration, schedule)

    def charged_compartments(self, spec, declaration):
        """The compartments its routes charge, by their FR-1 IDs, in declared order: retrieval
        brings each pool its membrane's charge (R2). Refusal 5 version 1.2 reads this hook to admit
        a charged anchor where these routes are declared (a checkpoint imported as a new
        definition)."""
        return tuple(route.compartment for route in declaration.routes)

    def batch_signature(self, declaration):
        return (LAW_ID, tuple((r.plasma_patch, r.compartment) for r in declaration.routes))

    def working_size(self, spec):
        x = spec.execution
        return 3 * (8 * (x.capacity + x.extracellular_capacity) ** 2 + 16 * x.membrane_capacity)

    def summary(self, spec, declaration, schedule, history):
        routes = {}
        for route, plasma, bound, pool in resolved_routes(spec, declaration):
            routes[route.id] = dict(
                plasma_patch=plasma.id,
                compartment=pool.id,
                pool_node=pool.node,
                pool_patch=bound.id,
                owner=pool.owner,
                carriers=dict(route.carriers),
                plasma_area_floor_m2=route.plasma_area_floor_m2,
                pool_area_floor_m2=route.pool_area_floor_m2,
                retrieval_enrichment=dict(route.retrieval_enrichment),
                recycling_enrichment=dict(route.recycling_enrichment),
                internalised_units=dict(route.internalised_units),
            )
        return {
            "trafficking_law": LAW_ID,
            "trafficking_step": STEP_ID,
            "trafficking_routes": routes,
            "trafficking_scope": SCOPE,
            "trafficking_rk4": "exact half-steps around the inner RK4 step",
        }

    # ------------------------------------------------------------ binding

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        return bind(spec, declaration)

    # ------------------------------------------------------------ step parts

    def half_step(self, state, h, control, p, *, xp):
        return trafficked(state, h, control, p, xp=xp)

    def control_valid(self, control, p, *, xp):
        valid = xp.asarray(True)
        for name in CONTROL_FIELDS:
            rate = getattr(control, name)
            valid &= xp.all(xp.isfinite(rate)) & xp.all(rate >= 0)
        return valid

    def rate_checks(self, state, control, p, valid, *, xp):
        return valid & own_valid(state, p, xp=xp)

    def domain_valid(self, state, p, valid, *, xp):
        own = own_valid(state, p, xp=xp)
        return own if valid is None else valid & own

    # ------------------------------------------------------------ ledgers

    def ledger_terms(self, result, row, p, *, xp):
        view, bound = capacitor_view(row, p, xp=xp)
        energy, electrode, _, _ = adapter.view_capacitor_terms(row, view, bound, xp=xp)
        result["energy"] = (
            result["energy"]
            + energy
            + entity_sum(row.trafficking_dissipated_energy_pJ, axis=None, xp=xp)
            - entity_sum(row.trafficking_work_pJ, axis=None, xp=xp)
        )
        result["electrode"] = result["electrode"] - electrode
        result["outside"] = result["outside"] - row.trafficking_carrier_fmol
        return result, own_ledgers(row, p, xp=xp)

    def magnitude_terms(self, magnitudes, row, p, *, xp):
        """The carriers in the outside and total ledgers' magnitudes, the booked and view plate
        charges in the electrode and global-charge bounds, and the booked and view energy terms
        in the energy bound; every term is zero without trafficking."""
        view, bound = capacitor_view(row, p, xp=xp)
        _, _, energy, electrode = adapter.view_capacitor_terms(row, view, bound, xp=xp)
        carriers = xp.abs(row.trafficking_carrier_fmol)
        magnitudes[1] = magnitudes[1] + carriers
        magnitudes[2] = magnitudes[2] + 2.0 * entity_sum(carriers, axis=1, xp=xp)  # Nodes.
        image = row.trafficking_image_charge_C + electrode
        magnitudes[4] = image if magnitudes[4] is None else magnitudes[4] + image
        held = p.reservoir & p.outside_active
        supplied = xp.abs(p.valence * xp.where(held, carriers, 0.0))  # [species, outside]
        supply = CHARGE_PER_FMOL * entity_sum(species_sum(supplied, xp=xp), axis=None, xp=xp)
        charge = entity_sum(row.trafficking_image_charge_C, axis=None, xp=xp) + supply
        magnitudes[5] = charge if magnitudes[5] is None else magnitudes[5] + charge
        energy = energy + entity_sum(row.trafficking_energy_magnitude_pJ, axis=None, xp=xp)
        magnitudes[6] = energy if magnitudes[6] is None else magnitudes[6] + energy
        return magnitudes

    def own_ledgers(self, row, p, *, xp):
        return own_ledgers(row, p, xp=xp)

    def own_magnitudes(self, row, p, *, xp):
        cells = xp.zeros(p.active.size)
        record = row.trafficking_internalised_units - p.trafficking_internalised_reference
        return (
            xp.abs(row.trafficking_units) + entity_sum(xp.abs(record), axis=0, xp=xp),
            scatter(xp.abs(row.trafficking_area_m2), cells, (p.membrane_cell,), xp=xp),
            scatter(xp.abs(row.trafficking_capacitance_F), cells, (p.membrane_cell,), xp=xp),
        )

    def own_bounds(self, magnitudes, steps):
        rounding = first.LEDGER_STEP_ROUNDING * np.finfo(float).eps * steps
        return tuple(floor + rounding * m for floor, m in zip(FLOORS, magnitudes, strict=True))

    def external_ledger_terms(self, ledgers, row, p, *, xp):
        terms = booked(row)
        return {k: v - terms[k] for k, v in ledgers.items()}

    def external_magnitude_terms(self, magnitudes, row, p, *, xp):
        terms = booked(row)
        return {k: v + xp.abs(terms[k]) for k, v in magnitudes.items()}
