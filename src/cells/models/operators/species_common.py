"""Shared definition logic of the secreted-species operators (D150, version 1).

docs/SECRETED_SPECIES_TRANSPORT_DESIGN.md §1.5, §2.6, §5.2 and §11.5; used by
scheduled_species_turnover@1 (species_turnover.py) and scheduled_species_exchange@1
(species_exchange.py). Nothing here runs on the device: these are the declarations' parsers,
the definition refusals and the host-side tables from which the operators' per-world controls
are built.

* **Identity** (§1.5). Each operator lists the species it acts on, each with an opaque catalogue
  reference, null or {"catalogue": id, "entry": key} (the S2 population form), and the kind of
  evidence (the protein catalogue plan's constraint 6), given exactly when a reference is. The
  identity reaches the summary and the definition, never the arrays. Two operators that declare
  one species must declare the same identity.
* **At most 7 species per world** (the lead's ruling 3, §2.6), refused in both operators'
  definition checks, with the reason in the message.
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
"""

import math
from bisect import bisect_left, bisect_right
from collections import Counter
from dataclasses import dataclass, replace

import numpy as np

from cells.core import pump_composite_spec as composite_spec
from cells.core.multispecies_spec import identifier
from cells.core.specs import ConfigError, _fields
from cells.models.operators.membrane_state import parse_catalogue

REPLACEMENT_LAW = "scheduled_cell_replacement@1"
SPECIES_LAWS = ("scheduled_species_turnover@1", "scheduled_species_exchange@1")
MAX_SPECIES = 7
EVIDENCE_KINDS = ("label_only", "expressed_isoform", "native_current", "model")
# Version 1 is transport on a static tissue (§5.5): both operators read the declared volumes and
# masks, so no other operator may provide them, and a closer counts as a mask's provider (S5). This
# refuses water, the lumens, insertion, partition and the bridge.
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


@dataclass(frozen=True)
class Occupant:
    carrier_id: str
    birth: float
    death: float  # math.inf for the last occupant.
    kind: str  # "founder", or replacement's newcomer kind.
    template: str | None
    donor: str | None


# ------------------------------------------------------------------ identity and the cap


def parse_species(raw, base, law):
    """The species list of an operator's declaration (neutral species of the inner model)."""
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
        if valence[name] != 0:
            raise ConfigError(
                f"{law} acts on neutral species only (valence 0); {name!r} has valence "
                f"{valence[name]}"
            )
        check_impermeant(m, name, law)
        catalogue, evidence = parse_catalogue(entry["catalogue"]), entry["evidence"]
        if catalogue is None and evidence is not None:
            raise ConfigError(f"{law}: the kind of evidence is given with a catalogue reference")
        if catalogue is not None and evidence not in EVIDENCE_KINDS:
            raise ConfigError(
                f"{law}: a catalogue reference records its kind of evidence, one of "
                + ", ".join(EVIDENCE_KINDS)
            )
        species.append(SpeciesIdentity(name, catalogue, evidence))
    if len({s.id for s in species}) != len(species):
        raise ConfigError(f"{law} lists a species twice")
    return tuple(species)


def check_impermeant(model, name, law):
    """Refuse a species with a membrane, junction or channel route of @3's (version 1).

    @3's explicit-rate bound (surface_pump.explicit_rate_bound) covers every species on faces, but
    on membranes and junctions it bounds only the z^2-weighted charge relaxation, and so do the
    channels' in-step refusal (membrane_rate): a neutral species moving through a membrane, junction
    or channel would have no material-rate bound. Templates cannot add such a route either, since a
    template replaces only routes the slot already has (core/cell_replacement_spec)."""
    row = model.species_ids.index(name)
    routes = [f"membrane {p.id}" for p in model.membranes if p.permeability_m_per_s[row] != 0] + [
        f"junction {j.id}" for j in model.junctions if j.permeability_m_per_s[row] != 0
    ]
    routes += [
        f"channel {c.id}"
        for c in model.channels
        if any(i.species_id == name and i.relative_permeability != 0 for i in c.permeant_ions)
    ]
    if routes:
        raise ConfigError(
            f"{law} acts on species with zero membrane, junction and channel permeability only; "
            f"{name!r} has a route through {routes[0]}: @3's explicit-rate bound covers a neutral "
            "species on faces alone, and on membranes and junctions bounds only the z^2-weighted "
            "charge relaxation, so such a species would have no material-rate bound at the "
            "definition"
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
            f"{law} admits at most {MAX_SPECIES} species per world in version 1 (this world "
            f"declares {count}): host-side NumPy sums over the species axis switch to pairwise "
            "summation at 8 or more terms, so the host checks could add the species in a different "
            "order from the device's explicit species-order adds (D148). The cap holds until that "
            "is checked"
        )


def check_identities(spec, law, identities):
    """Refuse a species that another secreted-species operator declares with another identity."""
    mine = {s.id: s for s in identities}
    for op, declaration, _ in composite_spec.entries(spec):
        if op.LAW_ID == law or op.LAW_ID not in SPECIES_LAWS:
            continue
        for other in declaration.species:
            own = mine.get(other.id)
            if own is not None and (own.catalogue, own.evidence) != (
                other.catalogue,
                other.evidence,
            ):
                raise ConfigError(
                    f"{law} declares species {other.id!r} with another identity than "
                    f"{op.LAW_ID} (catalogue reference and kind of evidence must agree)"
                )


def summary_identities(identities):
    return {
        s.id: dict(
            catalogue=None if s.catalogue is None else list(s.catalogue), evidence=s.evidence
        )
        for s in identities
    }


# ------------------------------------------------------------------ schedules


def _time(value, what):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ConfigError(f"{what} requires a finite time")
    return float(value)


def parse_schedules(raw, base, routes, law, key, parse_values):
    """The route schedules under the experiment key `key`.

    routes: the declaration's routes, each with `id` and `cell` (its slot's cell ID; None for an
    outside-node route). parse_values(route, entry) returns one change's value tuple. An
    outside-node route has exactly one schedule, with carrier_id null; a cell-side route needs
    its founder's (carrier_id its cell ID); newcomers' schedules are optional and checked against
    their lives with the definition. Founder and node schedules start at time 0; every change is
    an exact multiple of dt inside the horizon, in increasing order.
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
            if time != round(time / dt) * dt:
                raise ConfigError(
                    f"{law}: a schedule change must be an exact multiple of dt (k * dt)"
                )
            if not 0.0 <= time <= end:
                raise ConfigError(f"{law}: a schedule change lies outside the horizon")
            changes.append((time, parse_values(route, change)))
        times = [t for t, _ in changes]
        if any(b <= a for a, b in zip(times, times[1:], strict=False)):
            raise ConfigError(f"{law}: schedule times increase strictly")
        founder = carrier is None or carrier == route.cell
        if founder and times[0] != 0.0:
            raise ConfigError(
                f"{law}: route {route.id}'s "
                + ("node" if carrier is None else "founder")
                + " schedule starts at time 0"
            )
        schedules.append(RouteSchedule(route.id, carrier, tuple(changes)))
    for route in routes:
        if (route.id, route.cell) not in seen:
            raise ConfigError(
                f"{law}: route {route.id} needs a schedule for "
                + ("its node" if route.cell is None else f"its founder carrier {route.cell}")
            )
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
    """{cell id: (Occupant, ...)}: each slot's founder, then its newcomers in time order."""
    _, events = replacement_of(spec)
    by_slot = {c.id: [] for c in spec.model.cells}
    for v in sorted(events, key=lambda v: v.time):
        by_slot[v.slot].append(v)
    lives = {}
    for cell, rows in by_slot.items():
        deaths = [v.time for v in rows] + [math.inf]
        lives[cell] = (
            Occupant(cell, 0.0, deaths[0], "founder", None, None),
            *(
                Occupant(v.carrier_id, v.time, deaths[k + 1], v.newcomer, v.template, v.donor)
                for k, v in enumerate(rows)
            ),
        )
    return lives


def route_tables(spec, routes, schedules, templates, law):
    """Per route, its value table over the run: ((time, values), ...) in increasing time.

    An outside-node route's table is its schedule. A cell-side route's follows its slot's
    occupants (module docstring): the founder's schedule; at each newcomer's birth its template's
    rate, or for a donor copy the rate in force just before (the donor's, by admission); then the
    newcomer's own changes. Refused here with the reason: a schedule change outside its carrier's
    life, a schedule naming a carrier that never occupies the route's slot, and a template newcomer
    whose template declares no rate for a route of its slot.
    """
    lives = occupants(spec)
    names = {t.template_id: dict(t.rates) for t in templates}
    keyed = {(s.route_id, s.carrier_id): s.changes for s in schedules}
    used, tables = set(), []
    for route in routes:
        if route.cell is None:
            used.add((route.id, None))
            tables.append(keyed[(route.id, None)])
            continue
        table = []
        for occupant in lives[route.cell]:
            own = keyed.get((route.id, occupant.carrier_id), ())
            if own:
                used.add((route.id, occupant.carrier_id))
            if occupant.kind == "founder":  # Its schedule starts at 0 (parse_schedules).
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
        tables.append(tuple(table))
    unused = sorted(set(keyed) - used, key=str)
    if unused:
        route_id, carrier = unused[0]
        raise ConfigError(
            f"{law}: the schedule of route {route_id} names carrier {carrier}, which never "
            "occupies its slot"
        )
    return tables


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
