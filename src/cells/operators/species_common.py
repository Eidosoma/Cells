"""Shared definition logic of the secreted-species operators (D150, version 1).

docs/SECRETED_SPECIES_TRANSPORT_DESIGN.md §1.5, §2.6, §5.2 and §11.5; used by
cells.operator.scheduled_species_turnover@1 (species_turnover.py) and cells.operator.scheduled_species_exchange@1
(species_exchange.py). Nothing here runs on the device: these are the declarations' parsers,
the definition refusals and the host-side tables from which the operators' per-world controls
are built.

* **Identity** (§1.5). Each operator lists the species it acts on, each with an opaque catalogue
  reference, null or {"catalogue": id, "entry": key} (the S2 population form), and the kind of
  evidence (the protein catalogue plan's constraint 6), given exactly when a reference is. The
  identity reaches the summary and the definition, never the arrays. Two operators that declare
  one species must declare the same identity.
* **Charged rows** (FR-15 S1, the lead's rulings of 19 November 2026): the operators act on
  neutral species, except cells.operator.local_species_reactions@1, whose reactions conserve charge. Every listed
  species is impermeant on @3's own routes (check_impermeant), except a declared counter-ion that
  @3's explicit-rate bound covers on each of its routes (check_counter_ion); a charged trace row's
  permeation is the passive-routes kind's constant-field law, or for cells.operator.local_species_reactions@1 a
  channel whose law declares its material term (check_impermeant's bounded_channels).
* **At most 1,024 species per world** (§2.6; FR-43 / D315 raised it from 16 on FR-43's probe,
  docs/FR43_SHARED_INVENTORIES_DESIGN.md §1; FR-9 / D165 from 7 on the W4 probe, §13), refused in
  every species operator's definition check, with the reason in the message. The cap counts every
  species, ions included. Above 16 the species sums fold by lax.scan on the device (the fold's gate,
  numerics/species_sums.py), so every world at 16 species or fewer keeps its program.
* **Rates belong to the occupant** (§5.2, the lead's decision of 13 November). Cell-side rates
  are properties of the carrier that occupies a slot, not of the slot:
  - founders' rates come from schedules keyed by the founder's carrier ID (its cell ID), from
    time 0;
  - a newcomer from an isolated template takes the rates its template declares (the operator's
    `templates`, keyed by replacement template ID, then by route ID);
  - a donor copy is admitted only when its declared route values, ion and secretion, equal the
    slot's (the lead's ruling 1); it then takes the rates in force at the slot just before the
    event, which equal the donor's, so the slot's controls are unchanged across the event;
  - a newcomer's own schedule (keyed by its carrier ID) changes its rates strictly inside its life;
  - a slot's earlier occupant's rates never carry over to a newcomer from a template;
  - outside-node routes are environment, not carriers: one schedule per route, from time 0.
  Replacement@1's events are prescribed, so every slot's occupant at every time is known from the
  definition, and the per-world controls are built from it (recomputed at a restart, R7).
* **The volume rule** (FR-43 / D315; FR-65, docs/TURNOVER_CHANGING_VOLUME_DESIGN.md §3.5): an
  operator that reads the volumes current at its split admits water as the one changer of them
  (check_volume_changers). A changer of the outside volume is refused only where it reaches a node
  the reader reads: a restricted lumen names its own nodes (contract.changed_volume_nodes, route
  B), so a lumen at a node the reader never reads is admitted.
"""

import math
from bisect import bisect_left, bisect_right
from collections import Counter
from dataclasses import dataclass, replace

import numpy as np

from cells.definitions import pump_composite_spec as composite_spec
from cells.definitions.spec_values import identifier
from cells.definitions.specs import ConfigError, _fields
from cells.numerics.clock_instants import ON_THE_GRID, on_grid  # D283's one predicate.
from cells.operators import contract
from cells.registry import species_registry as registry

REPLACEMENT_LAW = "cells.operator.scheduled_cell_replacement@1"
SPECIES_LAWS = (
    "cells.operator.scheduled_species_turnover@1",
    "cells.operator.scheduled_species_exchange@1",
)
MAX_SPECIES = 1024  # FR-43 / D315 (from 16; FR-9 / D165 from 7): FR-43's probe; above it, another.
EVIDENCE_KINDS = registry.EVIDENCE_KINDS
# Version 1 is transport on a static tissue (§5.5): its readers (exchange, the coupling and the unit
# producer) read the declared volumes and masks, so no other operator may provide them, and a
# closer counts as a mask's provider (S5). This refuses water, the lumens, insertion, partition and
# the bridge. Turnover reads its own since FR-65 (species_turnover.py).
CONFLICTS_VIEW = ("volume", "extracellular_volume", "active", "outside_active", "membrane_active")
# The docstring statement the design requires (§7, the lead's ruling 4), scoped to the IMEX solvers.
GUARD_STATEMENT = (
    "Under the IMEX solvers the shared energy bound is set by the ions' flows and is blind to "
    "these bookings at µM–nM (bound/change 1.7 to 1,721 in a probed mixed world); the "
    "species-only world and a NumPy ΔG test per law are the guards of record."
)


@dataclass(frozen=True)
class SpeciesIdentity:
    id: str
    catalogue: tuple | None  # (catalogue id, entry key), or None (unassigned).
    evidence: str | None  # One of EVIDENCE_KINDS when a catalogue reference is given.


@dataclass(frozen=True)
class RouteSchedule:
    route_id: str
    carrier_id: str | None  # None: an outside-node route (environment, not a carrier).
    changes: tuple  # ((time, values), ...), values a tuple of floats.


@dataclass(frozen=True)
class TemplateRates:
    template_id: str
    rates: tuple  # ((route id, values), ...)


# ------------------------------------------------------------------ identity and the cap


def parse_species(raw, base, law, *, charged=False, counter_ions=frozenset(), limit=""):
    """The species list of an operator's declaration: neutral species of the inner model, or
    (charged=True: FR-15 S1, cells.operator.local_species_reactions@1) charged ones too.

    Every listed species is impermeant on @3's own routes (check_impermeant; where charged rows are
    admitted, a channel whose law declares its material term is no route), except a declared
    counter-ion (counter_ions), which is charged and covered by @3's explicit-rate bound on each
    of its routes (check_counter_ion). limit: the operator's stated reason a charged species is
    refused (charged=False)."""
    if type(raw) is not list or not raw:
        raise ConfigError(f"{law} declares the species it acts on in a non-empty list")
    m = base.model
    valence = dict(zip(m.species_ids, m.valence, strict=True))
    species = []
    for entry in raw:
        _fields(entry, {"id", "catalogue", "evidence"}, f"{law} species")
        name = identifier(entry["id"])
        if name not in valence:
            raise ConfigError(f"{law} acts on a species the model does not declare: {name!r}")
        if valence[name] != 0 and not charged:
            raise ConfigError(
                f"{law} acts on neutral species only (valence 0); {name!r} has valence "
                f"{valence[name]}{limit}"
            )
        if name in counter_ions:
            if valence[name] == 0:
                raise ConfigError(f"{law}: a counter-ion is charged; {name!r} has valence 0")
            check_counter_ion(base, name, law)
        else:
            check_impermeant(m, name, law, bounded_channels=charged)
        identity = registry.parse_identity(entry["catalogue"], entry["evidence"], law)
        species.append(SpeciesIdentity(name, identity.catalogue, identity.evidence))
    if len({s.id for s in species}) != len(species):
        raise ConfigError(f"{law} lists a species twice")
    return tuple(species)


@dataclass(frozen=True)
class ReadSpecies:
    """A species row the operator reads, never writes (ruling 1: one read-only mechanism)."""

    id: str
    catalogue: tuple | None
    evidence: str | None


def parse_read_species(raw, base, law):
    """The read-only species list: any species of the world, ions included, with D150's identity
    form; read, never written (docs/INVENTORY_COUPLING_DESIGN.md §1.3, ruling 1: one mechanism,
    which D152's 1.1 door reuses). Moved here from cells.operator.species_regulated_availability@1."""
    if type(raw) is not list:
        raise ConfigError(f"{law} lists the species it reads in an explicit list")
    declared = set(base.model.species_ids)
    species = []
    for entry in raw:
        _fields(entry, {"id", "catalogue", "evidence"}, f"{law} species")
        name = identifier(entry["id"])
        if name not in declared:
            raise ConfigError(f"{law} reads a species the model does not declare: {name!r}")
        identity = registry.parse_identity(entry["catalogue"], entry["evidence"], law)
        species.append(ReadSpecies(name, identity.catalogue, identity.evidence))
    if len({s.id for s in species}) != len(species):
        raise ConfigError(f"{law} lists a species twice")
    return tuple(species)


def check_impermeant(model, name, law, *, bounded_channels=False):
    """Refuse a species with a membrane, junction or channel route of @3's (version 1).

    @3's explicit-rate bound (surface_pump.explicit_rate_bound) covers every species on faces, but
    on membranes and junctions it bounds only the z^2-weighted charge relaxation, and so do the
    channels' in-step refusal (membrane_rate): a neutral species moving through a membrane, junction
    or channel would have no material-rate bound. Templates cannot add such a route either, since a
    template replaces only routes the slot already has (core/cell_replacement_spec).

    bounded_channels (cells.operator.local_species_reactions@1 alone, through parse_species: it admits charged rows
    and refuses RK4): a channel whose law declares its material term does not count, since the IMEX
    step's material rule bounds its ions' amounts at every explicit stage
    (surface_pump_v3.material_rate; docs/CALCIUM_STORE_AND_CHANNELS_DESIGN.md §5.4)."""
    from cells.definitions.surface_pump_v3_spec import channel_laws

    row = model.species_ids.index(name)
    routes = [f"membrane {p.id}" for p in model.membranes if p.permeability_m_per_s[row] != 0] + [
        f"junction {j.id}" for j in model.junctions if j.permeability_m_per_s[row] != 0
    ]
    laws = channel_laws() if bounded_channels else {}
    bounded = {law_id for law_id, own in laws.items() if own.material_term is not None}
    routes += [
        f"channel {c.id}"
        for c in model.channels
        if c.kinetic_law not in bounded
        and any(i.species_id == name and i.relative_permeability != 0 for i in c.permeant_ions)
    ]
    if routes:
        raise ConfigError(
            f"{law} acts on species with zero membrane, junction and channel permeability only; "
            f"{name!r} has a route through {routes[0]}: @3's explicit-rate bound covers a neutral "
            "species on faces alone, and on membranes and junctions bounds only the z^2-weighted "
            "charge relaxation, so such a species would have no material-rate bound at the "
            "definition (a charged trace row likewise: its permeation goes through the "
            "passive-routes kind's constant-field law; FR-15)"
        )


# FR-15 S1 (the lead's rulings of 19 November 2026): a charged counter-ion row may keep @3's own
# routes where @3's explicit-rate bound holds its permeation. On each route, the row's own
# charge-relaxation term in the bound (surface_pump.explicit_rate_bound: slope z^2 P A max(c)/C at
# the cell, twice on a junction; membrane_rate's channel term alike) must be at least this many
# times its own material term (neutral_material_rate's form: P A (1/V_a + 1/V_b)). P and A (and a
# channel's opening) cancel, so the test is slope z^2 max(c) / C >= COVERAGE (1/V_a + 1/V_b) at
# the declared state the bound reads. 100 leaves room for the constant-field material factor
# g(u) <= 1 + |u| up to |u| = 99 (2.5 V at z = 1). @3's major ions in a pL cell sit near 5e4; a
# 1 µM trace row near 0.4 is refused, its permeation the passive-routes kind's.
COUNTER_ION_COVERAGE = 100.0


def counter_ion_margin(base, name):
    """(the smallest margin over species `name`'s @3 routes of its own charge-relaxation term
    over its own material term, that route) at the declared state; (inf, None) without a route.
    Membranes and channels on patches, junctions between cells, each against the capacitance the
    bound relaxes its charge over (surface_pump.explicit_rate_bound): a held patch's and a
    junction's, the cell's held patches'; a loose patch's, one that faces a floating node, its
    own. (A junction at a cell with no held patch has no such capacitance: the bound refuses it.)"""
    from cells.definitions.surface_pump_v3_spec import projection
    from cells.laws.electrochemistry import F, R
    from cells.models import surface_kinetic as kinetic
    from cells.models.surface_pump import floating_nodes

    m = base.model
    row = m.species_ids.index(name)
    _, p = kinetic.initial_values(projection(base))
    z2 = float(np.asarray(p.valence).reshape(-1)[row]) ** 2
    slope = F * F / (R * float(p.temperature))
    ci = np.where(p.active, p.amount_reference[row] / p.volume, 0.0)  # mM = mol/m^3.
    co = np.where(
        p.outside_active, p.extracellular_amount_reference[row] / p.extracellular_volume, 0.0
    )
    n = p.active.size
    own, floating = np.asarray(p.membrane_capacitance), floating_nodes(m)
    loose = np.zeros(own.size, dtype=bool)
    loose[: len(m.membranes)] = [patch.outside in floating for patch in m.membranes]
    capacitance = np.zeros(n)
    np.add.at(capacitance, np.asarray(p.membrane_cell), np.where(loose, 0.0, own))
    cell_volume = np.where(p.active, p.volume * 1e-15, np.inf)
    outside_volume = np.where(
        p.outside_active & ~p.reservoir, p.extracellular_volume * 1e-15, np.inf
    )
    names = [k.id for k in m.membranes]
    channel_patches = {
        c.membrane_id
        for c in m.channels
        if any(i.species_id == name and i.relative_permeability != 0 for i in c.permeant_ions)
    }
    margins = []
    for k, patch in enumerate(m.membranes):
        if patch.permeability_m_per_s[row] == 0 and patch.id not in channel_patches:
            continue
        i, o = int(p.membrane_cell[k]), int(p.membrane_outside[k])
        charge = slope * z2 * max(ci[i], co[o]) / (own[k] if loose[k] else capacitance[i])
        material = 1.0 / cell_volume[i] + 1.0 / outside_volume[o]
        margins.append((charge / material, f"membrane {names[k]}"))
    for j, junction in enumerate(m.junctions):
        if junction.permeability_m_per_s[row] == 0:
            continue
        a, b = int(p.junction_sender[j]), int(p.junction_receiver[j])
        behind = min(capacitance[a], capacitance[b])
        charge = 2 * slope * z2 * max(ci[a], ci[b]) / behind if behind > 0 else math.inf
        material = 1.0 / cell_volume[a] + 1.0 / cell_volume[b]
        margins.append((charge / material, f"junction {junction.id}"))
    return min(margins, default=(math.inf, None))


def check_counter_ion(base, name, law):
    """Refuse a counter-ion that @3's explicit-rate bound does not cover on one of its routes
    (counter_ion_margin below COUNTER_ION_COVERAGE): a charged trace row, whose permeation goes
    through the passive-routes kind's constant-field law instead."""
    margin, route = counter_ion_margin(base, name)
    if margin < COUNTER_ION_COVERAGE:
        raise ConfigError(
            f"{law}: counter-ion {name!r} is not covered by @3's explicit-rate bound on {route}: "
            f"its own charge-relaxation term is {margin:.3g} times its material term there, below "
            f"{COUNTER_ION_COVERAGE:g} (a charged trace row; its permeation goes through the "
            "passive-routes kind's constant-field law, FR-15)"
        )


def species_to_dict(identities):
    return [
        dict(
            id=s.id,
            catalogue=None
            if s.catalogue is None
            else dict(catalogue=s.catalogue[0], entry=s.catalogue[1]),
            evidence=s.evidence,
        )
        for s in identities
    ]


def check_species_cap(spec, law):
    count = len(spec.model.species_ids)
    if count > MAX_SPECIES:
        raise ConfigError(
            f"{law} admits at most {MAX_SPECIES} species per world (this world declares "
            f"{count}; the cap counts every species, ions included). Up to 1,024 FR-43's probe "
            "found no ledger, guard or promised idleness that depends on a shared module's sum "
            "order over the species axis, since every ledger adds the species in explicit species "
            "order (D148), and the reactions' answers at one accuracy at every size; above it the "
            "dense network layout's cost grows as the square of the count and no ledger, restart "
            "or batch check has run, so a larger world needs another probe (FR-43 / D315)"
        )


def check_identities(spec, law, identities):
    """Refuse a species this law declares with another identity than its one authority: the
    species registry (registry/species_registry.py; D176), resolved from the model's entries and the
    operators' declared identities, authors before users. One call per law, no pairwise check."""
    registry.check_identities(spec, law, identities)


WATER = "cells.operator.ideal_osmosis_linear_compliance_water@1"  # The one volume changer admitted.


def largest_volumes(spec):
    """{node id: the largest volume it can take (pL)} for every cell and outside node: its declared
    volume, or where water changes the volumes its water compartment's declared maximum (FR-43 /
    D315: a producer's static bound reads it; the gene unit's and D152's production_bound)."""
    m = spec.model
    out = {c.id: c.volume_pL for c in m.cells} | {c.id: c.volume_pL for c in m.extracellular}
    for op, water, _ in composite_spec.entries(spec):
        if op.LAW_ID == WATER:
            for c in water.compartments:
                if c.compartment_id in out:
                    out[c.compartment_id] = max(out[c.compartment_id], c.maximum_volume_pL)
    return out


def summary_identities(identities):
    return {
        s.id: dict(
            catalogue=None if s.catalogue is None else list(s.catalogue), evidence=s.evidence
        )
        for s in identities
    }


# ------------------------------------------------------------------ the volume rule

WATER = "cells.operator.ideal_osmosis_linear_compliance_water@1"  # The one volume changer admitted.


def finite_nodes(spec):
    """The indices of the definition's finite outside nodes (its held baths left out)."""
    return tuple(i for i, c in enumerate(spec.model.extracellular) if not c.reservoir)


def check_volume_changers(spec, law, read_nodes):
    """FR-43 / D315 and FR-65 (route B, docs/TURNOVER_CHANGING_VOLUME_DESIGN.md §3.5): `law` reads
    the volumes current at the split, and water is the one changer of them admitted beside it.

    read_nodes: the outside nodes, by index, at which `law` reads a volume.
    * A changer of the cell volume other than water is refused: a provider of `volume`, or a writer
      of water's volume increments (cells.operator.scheduled_cell_replacement@2, which writes a
      newcomer's volume into water's state).
    * A provider of extracellular_volume other than water is refused where it changes a node of
      read_nodes: at the nodes its changed_volume_nodes names (a restricted lumen's own), or at
      every node where it names none. A changer at nodes `law` never reads is admitted, since its
      volume reaches no read of `law`.
    The refusal is by name: door S admits a current read declared after a change on a shared slot
    (pump_composite.scope_errors), so no structure check refuses these pairs."""
    read = frozenset(int(k) for k in read_nodes)
    ids = [c.id for c in spec.model.extracellular]
    for op, declaration, _ in composite_spec.entries(spec):
        if op.LAW_ID in (law, WATER):
            continue
        if "volume" in op.VIEW_FIELDS or "volume_increment_pL" in op.ENTITY_WRITES:
            raise ConfigError(
                f"{law}: {op.LAW_ID} changes the volumes it reads; water is the one volume "
                "changer admitted beside it (FR-43 / D315)"
            )
        if "extracellular_volume" not in op.VIEW_FIELDS:
            continue
        nodes = op.changed_volume_nodes(spec, declaration)
        shared = sorted(read if nodes is None else read & {int(k) for k in nodes})
        if shared:
            raise ConfigError(
                f"{law}: {op.LAW_ID} changes the volumes it reads (the outside volume at "
                f"{', '.join(ids[k] for k in shared)}); water is the one volume changer admitted "
                "at a node it reads (FR-43 / D315; FR-65)"
            )


# ------------------------------------------------------------------ schedules


def _time(value, what):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ConfigError(f"{what} requires a finite time")
    return float(value)


def parse_schedules(raw, base, routes, law, key, parse_values):
    """The route schedules under the experiment key `key`.

    routes: the declaration's routes, each with `id` and `cell` (its slot's cell ID; None for an
    outside-node route). parse_values(route, entry) returns one change's value tuple. An
    outside-node route has exactly one schedule, with carrier_id null, starting at time 0. A
    cell-side route's schedules are keyed by carrier and checked against the slot's occupants with
    the definition (route_tables; FR-65 moved the founder rule there, since a partition's pending
    slot has no founder). Every change is on the clock's grid (D283) inside the horizon, in
    increasing order.
    """
    if type(raw) is not list:
        raise ConfigError(f"{key} requires an explicit list")
    by_id = {r.id: r for r in routes}
    dt, end = base.execution.dt, base.experiment.end_time
    schedules, seen = [], set()
    for entry in raw:
        _fields(entry, {"route_id", "carrier_id", "schedule"}, f"{key} entry")
        route = by_id.get(entry["route_id"])
        if route is None:
            raise ConfigError(f"{key} names an undeclared route {entry['route_id']!r}")
        carrier = None if entry["carrier_id"] is None else identifier(entry["carrier_id"])
        if (route.cell is None) != (carrier is None):
            raise ConfigError(
                f"{law}: route {route.id} is "
                + (
                    "an outside-node route, scheduled per node (carrier_id null)"
                    if route.cell is None
                    else "a cell-side route, scheduled per carrier (carrier_id its occupant's)"
                )
            )
        if (route.id, carrier) in seen:
            raise ConfigError(f"{law}: one schedule per route and carrier ({route.id}, {carrier})")
        seen.add((route.id, carrier))
        if type(entry["schedule"]) is not list or not entry["schedule"]:
            raise ConfigError(f"{law}: a schedule lists its changes")
        changes = []
        for change in entry["schedule"]:
            time = _time(change.get("time") if isinstance(change, dict) else None, key)
            if on_grid(time, dt) is None:
                raise ConfigError(f"{law}: a schedule change must be {ON_THE_GRID}")
            if not 0.0 <= time <= end:
                raise ConfigError(f"{law}: a schedule change lies outside the horizon")
            changes.append((time, parse_values(route, change)))
        times = [t for t, _ in changes]
        if any(b <= a for a, b in zip(times, times[1:], strict=False)):
            raise ConfigError(f"{law}: schedule times increase strictly")
        if carrier is None and times[0] != 0.0:
            raise ConfigError(f"{law}: route {route.id}'s node schedule starts at time 0")
        schedules.append(RouteSchedule(route.id, carrier, tuple(changes)))
    for route in routes:
        if route.cell is None and (route.id, None) not in seen:
            raise ConfigError(f"{law}: route {route.id} needs a schedule for its node")
    return tuple(schedules)


def schedules_to_dict(schedules, entry_to_dict):
    return [
        dict(
            route_id=s.route_id,
            carrier_id=s.carrier_id,
            schedule=[dict(time=t, **entry_to_dict(s.route_id, v)) for t, v in s.changes],
        )
        for s in schedules
    ]


def parse_templates(raw, routes, law, parse_value):
    """The `templates` of a declaration: each newcomer template's rates, keyed by route ID."""
    if type(raw) is not list:
        raise ConfigError(f"{law} templates require an explicit list")
    by_id = {r.id: r for r in routes}
    templates = []
    for entry in raw:
        _fields(entry, {"template_id", "rates"}, f"{law} template")
        name = identifier(entry["template_id"])
        if not isinstance(entry["rates"], dict):
            raise ConfigError(f"{law}: template {name} keys its rates by route ID")
        rates = []
        for route_id, value in entry["rates"].items():
            route = by_id.get(route_id)
            if route is None or route.cell is None:
                raise ConfigError(
                    f"{law}: template {name} declares a rate for {route_id!r}, which is not a "
                    "cell-side route"
                )
            rates.append((route_id, parse_value(route, value)))
        templates.append(TemplateRates(name, tuple(rates)))
    if len({t.template_id for t in templates}) != len(templates):
        raise ConfigError(f"{law} declares a template twice")
    return tuple(templates)


def schedule_times(schedules):
    return tuple(t for s in schedules for t, _ in s.changes)


def value_at(schedules, time):
    """Each schedule's value in force at `time` (None before its first change): hashable."""
    out = []
    for s in schedules:
        k = bisect_right([t for t, _ in s.changes], time)
        out.append(s.changes[k - 1][1] if k else None)
    return tuple(out)


# ------------------------------------------------------------------ occupants and rate tables


def replacement_of(spec):
    """(replacement@1's declaration, its events) in this composition, or (None, ())."""
    for op, declaration, schedule in composite_spec.entries(spec):
        if op.LAW_ID == REPLACEMENT_LAW:
            return declaration, schedule
    return None, ()


def occupants(spec):
    """{cell id: (contract.Occupant, ...)}: each slot's carriers in time order (FR-65 §3.4).

    A slot no operator fills holds its founder, its own cell ID, from time 0 to the end. An
    operator that decides a slot's occupants gives them through the contract's slot_occupants
    (replacement@1 from its events, the partition from its lineage), never imported here (the J2
    line). A slot two operators fill is refused. Without such an operator every slot holds its
    founder alone, and with replacement@1 alone the lives are replacement's as before."""
    lives = {
        c.id: (contract.Occupant(c.id, 0.0, math.inf, "founder", None, None),)
        for c in spec.model.cells
    }
    filled = {}
    for op, declaration, schedule in composite_spec.entries(spec):
        for cell, records in op.slot_occupants(spec, declaration, schedule).items():
            if cell in filled:
                raise ConfigError(
                    f"Slot {cell}'s occupants are decided by both {filled[cell]} and {op.LAW_ID}; "
                    "one operator decides a slot's occupants (the occupant rule, D150 §5.2)"
                )
            filled[cell] = op.LAW_ID
            lives[cell] = tuple(records)
    return lives


def route_tables(spec, routes, schedules, templates, law, idle=None):
    """Per route, its value table over the run: ((time, values), ...) in increasing time.

    An outside-node route's table is its schedule. A cell-side route's follows its slot's
    occupants (module docstring; occupants): a founder's own schedule from time 0; at a newcomer's
    birth its template's rate, or for a donor copy the rate in force just before (the donor's, by
    admission), then its own changes; a daughter's own schedule from its birth (D150 §5.2: its
    rates are its own). Where the slot has no occupant (a pending daughter's slot before its birth,
    a retired carrier's after its retirement) the table holds `idle`, the reader's idle values,
    by explicit entries (control_arrays reads a table's first entry for every time before it), and
    a reader that gives none is refused there (fails closed). Refused here with the reason: a
    founder or daughter without its own schedule, or whose schedule does not start at its birth (a
    founder's at time 0), a change outside its carrier's life, a schedule naming a carrier that
    never occupies the route's slot, and a template newcomer whose template declares no rate for a
    route of its slot.
    """
    lives = occupants(spec)
    names = {t.template_id: dict(t.rates) for t in templates}
    keyed = {(s.route_id, s.carrier_id): s.changes for s in schedules}
    used, tables = set(), []

    def unoccupied(route, time):
        if idle is None:
            raise ConfigError(
                f"{law}: route {route.id}'s slot {route.cell} has no occupant from {time} s, and "
                f"{law} gives no idle rate for an empty slot (the occupant rule, D150 §5.2)"
            )
        return (time, idle)

    for route in routes:
        if route.cell is None:
            used.add((route.id, None))
            tables.append(keyed[(route.id, None)])
            continue
        table, end = [], 0.0
        for occupant in lives[route.cell]:
            if occupant.birth > end:  # The slot is empty until this carrier's birth.
                table.append(unoccupied(route, end))
            own = keyed.get((route.id, occupant.carrier_id), ())
            if own:
                used.add((route.id, occupant.carrier_id))
            if occupant.kind in ("founder", "daughter"):  # Its own schedule, from its birth.
                if not own:
                    raise ConfigError(
                        f"{law}: route {route.id} needs a schedule for "
                        + (
                            f"its founder carrier {occupant.carrier_id}"
                            if occupant.kind == "founder"
                            else f"carrier {occupant.carrier_id}, a daughter born in slot "
                            f"{route.cell} at {occupant.birth} s, whose rates are its own (D150 "
                            "§5.2)"
                        )
                    )
                if own[0][0] != occupant.birth:
                    raise ConfigError(
                        f"{law}: route {route.id}'s founder schedule starts at time 0"
                        if occupant.kind == "founder"
                        else f"{law}: carrier {occupant.carrier_id}'s schedule of route "
                        f"{route.id} starts at its birth, {occupant.birth} s"
                    )
                start, later = own[:1], own[1:]
            elif occupant.kind == "isolated_template":
                rates = names.get(occupant.template, {})
                if route.id not in rates:
                    raise ConfigError(
                        f"{law}: a newcomer from template {occupant.template} at {route.cell} "
                        f"takes its rates from the template; declare {occupant.template} in "
                        f"templates with a rate for route {route.id}"
                    )
                start, later = ((occupant.birth, rates[route.id]),), own
            else:  # A donor copy: the slot's rates just before the event (the donor's, admitted).
                start, later = ((occupant.birth, table[-1][1]),), own
            if any(not occupant.birth < t < occupant.death for t, _ in later):
                raise ConfigError(
                    f"{law}: carrier {occupant.carrier_id}'s schedule of route {route.id} changes "
                    f"outside its life at {route.cell} ({occupant.birth}, {occupant.death}) s"
                )
            table.extend((*start, *later))
            end = occupant.death
        if end < math.inf:  # Retired with no successor: empty from then on.
            table.append(unoccupied(route, end))
        tables.append(tuple(table))
    unused = sorted(set(keyed) - used, key=str)
    if unused:
        route_id, carrier = unused[0]
        raise ConfigError(
            f"{law}: the schedule of route {route_id} names carrier {carrier}, which never "
            "occupies its slot"
        )
    return tables


def node_onsets(spec):
    """{outside node id: its onset time} for the nodes an operator opens at an onset: a node
    opens with its onset patches (contract.onset_patches, insertion@2's), read without importing
    the operator that decides them."""
    outside = {p.id: p.outside for p in spec.model.membranes}
    out = {}
    for op, declaration, schedule in composite_spec.entries(spec):
        for patch, time in op.onset_patches(spec, declaration, schedule).items():
            node = outside[patch]
            out[node] = min(float(time), out.get(node, math.inf))
    return out


def check_node_onsets(spec, routes, tables, law):
    """D150 §5.3 and FR-65 §3.4: refuse an outside-node route with a positive value in force
    before its node's onset. Outside routes are environment, scheduled per node, and a closed node
    is no route's: a rate there would act on its declared content before the node exists."""
    onsets = node_onsets(spec)
    for route, table in zip(routes, tables, strict=True):
        onset = onsets.get(route.node) if route.cell is None else None
        if onset is None:
            continue
        for time, values in table:
            if time < onset and any(v > 0 for v in values):
                raise ConfigError(
                    f"{law}: route {route.id} has a positive rate at {route.node} from {time} s, "
                    f"before the node's onset at {onset} s; a node is environment from its onset "
                    "(D150 §5.3)"
                )


def control_arrays(tables, times, width):
    """[time, route, width] values in force at `times` (side right: a change at t applies at t)."""
    times = np.asarray(times, dtype=np.float64)
    out = np.zeros((len(times), len(tables), width))
    for j, table in enumerate(tables):
        at = np.asarray([t for t, _ in table])
        values = np.asarray([v for _, v in table], dtype=np.float64).reshape(len(table), width)
        index = np.searchsorted(at, times, side="right") - 1
        out[:, j, :] = values[np.maximum(index, 0)]
    return out


def check_templates(spec, templates, routes, law):
    """Each declared template is a replacement template whose newcomers occupy a routed slot."""
    declaration, events = replacement_of(spec)
    known = {t.id for t in declaration.templates} if declaration is not None else set()
    routed = {r.cell for r in routes if r.cell is not None}
    filled = {}
    for v in events:
        if v.newcomer == "isolated_template":
            filled.setdefault(v.template, set()).add(v.slot)
    cells = {r.id: r.cell for r in routes}
    for t in templates:
        if t.template_id not in known:
            raise ConfigError(
                f"{law} declares rates for {t.template_id}, not a replacement template"
            )
        slots = filled.get(t.template_id, set()) & routed
        if not slots:
            raise ConfigError(
                f"{law}: no newcomer from template {t.template_id} occupies a slot it routes"
            )
        stray = [r for r, _ in t.rates if cells[r] not in filled.get(t.template_id, set())]
        if stray:
            raise ConfigError(
                f"{law}: template {t.template_id} declares a rate for route {stray[0]}, whose slot "
                "no newcomer from it occupies"
            )


# ------------------------------------------------------------------ donor copies (ruling 1)


def _density(pump, area, override):
    if pump is None:
        return None
    value = pump.capacity_fmol_per_s / area if override is None else override
    return replace(pump, id="", capacity_fmol_per_s=value)


def ion_route_signature(model, cell, template):
    """The intensive ion route values of a slot's occupant, as multisets over its patches and
    channel populations: the declared values, with a template's route values where it sets them
    (replacement@1's view: leak permeability per species on every patch, pump capacity per area,
    channel permeability and abundance per law)."""
    species = model.species_ids
    leak = dict(template.membrane_permeability_m_per_s) if template is not None else {}
    permeability = dict(template.channel_permeability_m_per_s) if template is not None else {}
    abundance = dict(template.channel_abundance) if template is not None else {}
    pump = None if template is None else template.pump_capacity_fmol_per_s_m2
    calcium = None if template is None else template.calcium_pump_capacity_fmol_per_s_m2
    patches = [p for p in model.membranes if p.inside == cell]
    ids = {p.id for p in patches}
    return (
        Counter(
            (
                tuple(leak.get(s, p.permeability_m_per_s[i]) for i, s in enumerate(species)),
                _density(p.pump, p.area_m2, pump),
                _density(p.calcium_pump, p.area_m2, calcium),
            )
            for p in patches
        ),
        Counter(
            (
                c.kinetic_law,
                permeability.get(c.kinetic_law, c.max_permeability_m_per_s),
                abundance.get(c.kinetic_law, c.abundance),
                c.permeant_ions,
            )
            for c in model.channels
            if c.membrane_id in ids
        ),
    )


def _before(table, time):
    """The value in force just before `time` (the last change strictly earlier)."""
    times = [t for t, _ in table]
    return table[bisect_left(times, time) - 1][1]


def _secretion(routes, tables, key_of, time, cell):
    """A slot's secretion route values just before `time`: a multiset of (route kind, values)."""
    return Counter(
        (key_of(r), _before(table, time))
        for r, table in zip(routes, tables, strict=True)
        if r.cell == cell
    )


def check_donor_copies(spec, routes, tables, law, key_of):
    """Refuse a donor copy whose declared route values, ion or secretion, differ from the slot's
    (the lead's ruling 1, 13 November): its newcomer would take the donor's rates by the occupant
    rule while replacement@1 keeps the slot's ion route values (D139). In every admitted copy the
    two rules agree. A copy naming a route-only template is refused too: version 1 does not cover
    it. key_of(route) is a route's slot-independent kind (species, law and direction)."""
    declaration, events = replacement_of(spec)
    if declaration is None:
        return
    names = {t.id: t for t in declaration.templates}
    lives = occupants(spec)
    for v in events:
        if v.newcomer != "donor_copy":
            continue
        where = f"(donor {v.donor} for {v.slot} at {v.time} s)"
        if v.template is not None:
            raise ConfigError(
                f"{law}: a donor copy naming a route-only template is refused in version 1 {where}"
            )
        donor = next(o for o in lives[v.donor] if o.birth < v.time <= o.death)
        template = names.get(donor.template) if donor.kind == "isolated_template" else None
        if ion_route_signature(spec.model, v.donor, template) != ion_route_signature(
            spec.model, v.slot, None
        ):
            raise ConfigError(
                f"{law}: a donor copy whose ion route values differ from the slot's is refused in "
                f"version 1 {where}: rates belong to the occupant, while replacement@1 keeps the "
                "slot's route values (D139)"
            )
        before = (routes, tables, key_of, v.time)
        if _secretion(*before, v.donor) != _secretion(*before, v.slot):
            raise ConfigError(
                f"{law}: a donor copy whose secretion route values differ from the slot's is "
                f"refused in version 1 {where}: the newcomer would take the donor's rates"
            )
