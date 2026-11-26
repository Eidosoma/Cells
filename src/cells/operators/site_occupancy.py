"""cells.operator.site_occupancy@1: binding sites as owned state (FR-3, D169; docs/SITE_OCCUPANCY_DESIGN.md).

A site population is a population of identical, independent, single-occupancy sites on one owner,
facing one free pool and binding one neutral ligand (§1.1). Its owner is a membrane patch, facing
its outside node (`outside`) or its cell (`inside`), a contact, facing one of its two cells
(`first`: the junction's sender, `second`: its receiver), or a finite outside node's own surface
(`{"node": N}`, FR-28, D268's option A: a vessel wall, a coated bottom, beads or a matrix in the
node; it faces N, binds only and belongs to no cell, so replacement@1 and W never touch it and @2's
site source refuses it; docs/NODE_SURFACE_SITES_DESIGN.md). Its stoichiometric count is copies N x
sites per copy nu, and its accessible capacity S = alpha nu N / N_f fmol, with the static accessible
fraction alpha (§2.3) and N_f = 602,214,076 sites per fmol (exact). Its state is the free accessible
sites R and the bound amount B (fmol), anchored increments from R0 = S - B0 and B0 = theta0 S, so R
+ B = S, the moiety identity (§1.1). The free ligand stays in @3's rows at the facing node (one
material ledger, §1.4); a population takes no species row.

The laws (§2):
- cells.site_binding.langmuir_site_binding@1, passive: J = m_b [k_on c R - k_off B] (fmol/s; c in mM), with detailed
  balance dG°_b = RT ln(K_d / 1 mM), K_d = k_off / k_on;
- cells.site_internalisation.site_conserving_internalisation@1, driven, on an outward-facing patch only: I = m_i k_int B moves
  the cargo into the patch's cell and returns the site free (the site count is constant, §2.4).
The multipliers m_b and m_i are scheduled per population and route (`site_controls`); a binding
multiplier scales k_on and k_off together, so the equilibrium is unchanged. Parameters, alpha,
copies and sites per copy are not scheduled.

Ownership (§1.3, option O; ARCHITECTURE.md's modular core, D174): this operator owns every site
population of a composition and provides no view, mask or capacitance, so it is no field input and
an occupancy-only composition does not refresh the field (ownership is separate from solver
invalidation). It accepts later writers on its two pools (ACCEPTS_WRITES). Its readable
quantities (R3, FR-24) are each population's occupied fraction theta = B / (B + R), occupied amount
B and accessible capacity S, computed from its own state (quantities), which a reader such as the
coupling operator reads through the composite. Species identity follows
the coupling operator's pattern until D172 consolidates it: ligands are parsed by
species_common.parse_species, with a declared trace_mM (§4.3), and their identities are checked
against D150's and D152's declarations by this operator, in either order, with no shared change.

Refused at the definition (§6.2), each with its reason: a charged, permeant or undeclared ligand; an
identity that differs from D150's or D152's; more than 1,024 species (FR-43 / D315); a declared concentration of a
ligand below its declared trace, a replacement template's or a scheduled bath composition's
included, or a trace above 1e-6 K_d of a population binding it (§4.3); an unknown patch or contact;
an outward population on a patch facing a held bath; copies <= 0, sites per copy not a positive
int, alpha outside (0, 1], an unlisted ligand, initial occupancy outside [0, 1]; k_on <= 0,
k_off <= 0, k_int < 0; internalisation on an inward patch, a contact or a compartment-facing patch;
a destination other than "cell"; a population on a replaced slot's patch, or on a contact incident
to one; RK4; schedules that are missing, do not start at 0, change off the dt grid or outside the
horizon, or carry a negative multiplier; unknown keys and duplicate IDs. The composite's structure
check refuses the providers and closers of what it reads as declared (CONFLICTS_VIEW). Its outside
anchors and volumes are read only at the outside nodes its populations face (door S's scoped fixed
reads, FR-23, D244), so a change made at other nodes, such as the bath schedule's dose at a held
bath, is admitted beside it. The stationary analysis refuses the composite by its own ID check.
A compartment wash's buffers are held to the trace rule as a scheduled bath composition is
(FR-27, D246).
"""

import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

from cells.definitions import pump_composite_spec as composite_spec
from cells.definitions.spec_values import identifier
from cells.definitions.specs import ConfigError, _fields
from cells.laws.electrochemistry import R as R_GAS
from cells.models import pump_composite_adapter as adapter
from cells.numerics.clock_instants import ON_THE_GRID, on_grid  # D283's one predicate.
from cells.numerics.species_sums import entity_sum
from cells.operators import species_common as common
from cells.operators.contract import Operator, Read
from cells.operators.membrane_state import parse_catalogue

LAW_ID = "cells.operator.site_occupancy@1"
BINDING_LAW = "cells.site_binding.langmuir_site_binding@1"
INTERNALISATION_LAW = "cells.site_internalisation.site_conserving_internalisation@1"
STEP_ID = "ssprk33_unidirectional_stage_condition_site_bookings@1"
CONTROLS_KEY = "site_controls"
ROUTES = ("binding", "internalisation")
SITES_PER_FMOL = 602_214_076.0  # N_A x 1e-15 mol, exact (SI 2019).
TRACE_LIMIT = 1e-6  # A ligand's trace at most 1e-6 K_d of every population binding it (§4.3).
TRACE_RTOL = 1e-12  # A node declared at its trace, to representation (amount / volume).
DESTINATIONS = ("cell",)  # Version 1: the patch's own cell (§2.4).
FACES, SIDES = ("outside", "inside"), ("first", "second")
SURFACE = "surface"  # A node owner's fixed facing (FR-28): its own sites face only the node.
COMPARTMENTS_LAW = "cells.operator.cell_owned_compartments@1"
BATH_LAW = "cells.operator.scheduled_bath_composition@1"
WASH_LAW = "cells.operator.scheduled_compartment_wash@1"
CELL, OUTSIDE = 0, 1  # A facing node's kind.

STATE_AXES = {
    "site_free_increment_fmol": ["site_population"],  # R - R0.
    "site_bound_increment_fmol": ["site_population"],  # B - B0.
    "site_bound_net_fmol": ["site_population"],  # Net binding, signed (bound positive).
    "site_internalised_fmol": ["site_population"],  # >= 0, non-decreasing.
    "site_dissipated_energy_pJ": ["cell_slot"],  # Heat at populations facing that cell.
    "site_outside_dissipated_energy_pJ": ["extracellular_slot"],  # ... facing that node.
    "site_work_pJ": ["site_population"],  # Signed: internalisation and the hybrid's correction.
    "site_energy_magnitude_pJ": ["site_population"],  # Rounding magnitudes.
}
LAYOUT_FIELDS = (
    "site_capacity_fmol",  # [population] S.
    "site_free_anchor_fmol",  # [population] R0 = S - B0.
    "site_bound_anchor_fmol",  # [population] B0 = theta0 S.
    "site_on_rate",  # [population] k_on, per mM per s.
    "site_off_rate",  # [population] k_off, per s.
    "site_internalisation_rate",  # [population] k_int, per s (0 without the route).
    "site_standard_RT",  # [population] dG°_b / RT = ln(K_d / 1 mM).
    "site_ligand_row",  # [population] int64: the ligand's row on @3's species axis.
    "site_facing_kind",  # [population] int64: CELL or OUTSIDE.
    "site_facing_node",  # [population] int64: its index on that axis.
    "site_receiving_cell",  # [population] int64: the patch's cell (internalisation), else 0.
    "site_internalises",  # [population] bool.
    "site_component",  # [population] int64: its static component (§3.3).
    "site_component_count",  # [components]: its shape is the number of components (static).
    "site_pool_kind",  # [pool] int64: CELL or OUTSIDE; a pool is a ligand row at one node.
    "site_pool_node",  # [pool] int64: its node on that axis.
    "site_pool_row",  # [pool] int64: its ligand row.
    "site_pool_component",  # [pool] int64.
    "site_facing_pool",  # [population] int64: the pool it binds from.
    "site_receiving_pool",  # [population] int64: the pool it internalises into (else its facing).
)
CONTROL_FIELDS = ("site_binding_multiplier", "site_internalisation_multiplier")
LEDGERS = ("site_bound_entity", "site_moiety_entity")
LEDGER_DIAGNOSTICS = ("site_bound_entity_error_fmol", "site_moiety_entity_error_fmol")
LEDGER_MESSAGE = "Site occupancy accounting failed: "
READOUT_COLUMNS = (
    "site_occupancy",
    "site_binding_rate_fmol_per_s",
    "site_internalisation_rate_fmol_per_s",
)
POPULATION_KEYS = {
    "id",
    "functional_unit",
    "catalogue",
    "owner",
    "copies",
    "sites_per_copy",
    "accessible_fraction",
    "ligand",
    "association_rate_per_mM_per_s",
    "dissociation_rate_per_s",
    "initial_occupancy",
    "internalisation",
}


@dataclass(frozen=True)
class Ligand:
    identity: common.SpeciesIdentity
    trace_mM: float


@dataclass(frozen=True)
class Population:
    id: str
    functional_unit: str
    catalogue: tuple | None  # (catalogue id, entry key), or None; metadata only.
    owner_kind: str  # "patch" or "contact".
    owner_id: str
    facing: str  # A patch's face ("outside" or "inside") or a contact's side ("first", "second").
    copies: float
    sites_per_copy: int
    accessible_fraction: float
    ligand: str
    k_on: float  # per mM per s.
    k_off: float  # per s.
    initial_occupancy: float
    internalisation_rate: float | None  # per s; None without the route.
    destination: str | None


@dataclass(frozen=True)
class Occupancy:
    law: str
    species: tuple  # Ligand, in declared order.
    populations: tuple  # Population, in declared order.


@dataclass(frozen=True)
class SiteControl:
    population: str
    route: str  # "binding" or "internalisation".
    changes: tuple  # ((time, multiplier), ...) from time 0.


# ------------------------------------------------------------------ definition


def _number(value, what, *, low=None, strict=False):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ConfigError(f"{LAW_ID}: {what} is a finite number")
    if low is not None and (value <= low if strict else value < low):
        raise ConfigError(f"{LAW_ID}: {what} must be {'>' if strict else '>='} {low}")
    return float(value)


def parse_ligands(raw, base):
    if type(raw) is not list or not raw:
        raise ConfigError(f"{LAW_ID} declares its ligands in a non-empty list")
    traces = []
    for entry in raw:
        _fields(entry, {"id", "catalogue", "evidence", "trace_mM"}, f"{LAW_ID} species")
        traces.append(_number(entry["trace_mM"], "a ligand's trace_mM", low=0.0, strict=True))
    identities = common.parse_species(
        [{k: v for k, v in e.items() if k != "trace_mM"} for e in raw], base, LAW_ID
    )
    return tuple(Ligand(i, t) for i, t in zip(identities, traces, strict=True))


def _owner(raw, m, pid):
    if not isinstance(raw, dict):
        raise ConfigError(f"{LAW_ID}: population {pid}'s owner is an object")
    patches = {p.id: p for p in m.membranes}
    contacts = {j.id for j in m.junctions}
    if set(raw) == {"node"}:  # FR-28 (D268, option A): a finite outside node's own surface.
        node = identifier(raw["node"])
        if node not in {c.id for c in m.extracellular}:
            where = (
                "a cell, whose sites sit on its patches"
                if node in {c.id for c in m.cells}
                else "unknown"
            )
            raise ConfigError(f"{LAW_ID}: population {pid}'s node {node!r} is {where}")
        return "node", node, SURFACE
    if set(raw) == {"patch", "face"}:
        patch = identifier(raw["patch"])
        if patch not in patches:
            raise ConfigError(f"{LAW_ID}: population {pid} names an unknown patch {patch!r}")
        if raw["face"] not in FACES:
            raise ConfigError(f"{LAW_ID}: a patch population faces one of {FACES}")
        return "patch", patch, raw["face"]
    if set(raw) == {"contact", "side"}:
        contact = identifier(raw["contact"])
        if contact not in contacts:
            raise ConfigError(f"{LAW_ID}: population {pid} names an unknown contact {contact!r}")
        if raw["side"] not in SIDES:
            raise ConfigError(f"{LAW_ID}: a contact population faces one of its sides {SIDES}")
        return "contact", contact, raw["side"]
    raise ConfigError(
        f"{LAW_ID}: population {pid}'s owner is {{patch, face}}, {{contact, side}} or {{node}} (a "
        "node's own sites face only the node: no face or side beside it)"
    )


def facing_node(m, population):
    """(kind, node id) of the free pool a population faces (§1.1)."""
    if population.owner_kind == "node":
        return OUTSIDE, population.owner_id
    if population.owner_kind == "patch":
        patch = next(p for p in m.membranes if p.id == population.owner_id)
        if population.facing == "outside":
            return OUTSIDE, patch.outside
        return CELL, patch.inside
    junction = next(j for j in m.junctions if j.id == population.owner_id)
    return CELL, junction.sender if population.facing == "first" else junction.receiver


def population_cell(m, population):
    """The cell a population belongs to: its patch's own cell, whichever face it binds from, or
    the cell on its side of a contact (R3's locality, FR-24); None for a node's own sites
    (FR-28)."""
    if population.owner_kind == "node":
        return None
    if population.owner_kind == "patch":
        return next(p for p in m.membranes if p.id == population.owner_id).inside
    junction = next(j for j in m.junctions if j.id == population.owner_id)
    return junction.sender if population.facing == "first" else junction.receiver


def receiving_cell(m, population):
    """The cell an internalised cargo enters: the patch's own cell (version 1's destination)."""
    patch = next(p for p in m.membranes if p.id == population.owner_id)
    return patch.inside


def _internalisation(raw, pid, kind, facing):
    if raw is None:
        return None, None
    if not isinstance(raw, dict):
        raise ConfigError(f"{LAW_ID}: population {pid}'s internalisation is null or an object")
    _fields(raw, {"rate_per_s", "destination"}, f"{LAW_ID} internalisation")
    if kind != "patch" or facing != "outside":
        raise ConfigError(
            f"{LAW_ID}: population {pid} internalises, but only an outward-facing patch "
            "population may (an inward patch or a contact has no inward for it, §2.4)"
        )
    if raw["destination"] not in DESTINATIONS:
        raise ConfigError(
            f"{LAW_ID}: population {pid}'s destination is one of {DESTINATIONS} in version 1 "
            "(the patch's own cell; FR-1's and FR-2's destinations are doors, §2.4)"
        )
    rate = _number(raw["rate_per_s"], f"population {pid}'s internalisation rate", low=0.0)
    return rate, raw["destination"]


def parse_population(raw, m, ligands):
    if not isinstance(raw, dict):
        raise ConfigError(f"{LAW_ID}: each population is an object")
    _fields(raw, POPULATION_KEYS, f"{LAW_ID} population")
    pid = identifier(raw["id"])
    unit = identifier(raw["functional_unit"])
    catalogue = parse_catalogue(raw["catalogue"])
    kind, owner, facing = _owner(raw["owner"], m, pid)
    copies = _number(raw["copies"], f"population {pid}'s copies", low=0.0, strict=True)
    nu = raw["sites_per_copy"]
    if type(nu) is not int or nu < 1:
        raise ConfigError(f"{LAW_ID}: population {pid}'s sites per copy is a positive integer")
    alpha = _number(raw["accessible_fraction"], f"population {pid}'s accessible fraction")
    if not 0.0 < alpha <= 1.0:
        raise ConfigError(f"{LAW_ID}: population {pid}'s accessible fraction lies in (0, 1]")
    ligand = identifier(raw["ligand"])
    if ligand not in ligands:
        raise ConfigError(f"{LAW_ID}: population {pid} binds an unlisted ligand {ligand!r}")
    k_on = _number(
        raw["association_rate_per_mM_per_s"], f"population {pid}'s k_on", low=0.0, strict=True
    )
    k_off = _number(
        raw["dissociation_rate_per_s"], f"population {pid}'s k_off", low=0.0, strict=True
    )
    theta = _number(raw["initial_occupancy"], f"population {pid}'s initial occupancy")
    if not 0.0 <= theta <= 1.0:
        raise ConfigError(f"{LAW_ID}: population {pid}'s initial occupancy lies in [0, 1]")
    rate, destination = _internalisation(raw["internalisation"], pid, kind, facing)
    population = Population(
        pid,
        unit,
        catalogue,
        kind,
        owner,
        facing,
        copies,
        nu,
        alpha,
        ligand,
        k_on,
        k_off,
        theta,
        rate,
        destination,
    )
    node_kind, node = facing_node(m, population)
    if node_kind == OUTSIDE and next(c for c in m.extracellular if c.id == node).reservoir:
        raise ConfigError(
            f"{LAW_ID}: population {pid} faces the held bath {node!r}; binding from a chemostat, "
            "booked as reservoir supply, is a door (§6.2)"
        )
    return population


def check_traces(m, ligands, populations, extra=()):
    """§4.3's trace rule: every declared concentration of a ligand at or above its trace, and the
    trace at most 1e-6 K_d of every population binding it. extra: (where, ligand, mM) more."""
    ids = list(m.species_ids)
    for ligand in ligands:
        row = ids.index(ligand.identity.id)
        found = [
            (f"node {c.id}", c.initial_amount_fmol[row] / c.volume_pL)
            for c in (*m.cells, *m.extracellular)
        ]
        found += [(where, mM) for where, name, mM in extra if name == ligand.identity.id]
        for where, mM in found:
            if mM < ligand.trace_mM * (1.0 - TRACE_RTOL):
                raise ConfigError(
                    f"{LAW_ID}: ligand {ligand.identity.id} is declared at {mM:g} mM at {where}, "
                    f"below its declared trace {ligand.trace_mM:g} mM (every node at or above the "
                    "trace, §4.3)"
                )
        for p in populations:
            if p.ligand != ligand.identity.id:
                continue
            k_d = p.k_off / p.k_on
            if ligand.trace_mM > TRACE_LIMIT * k_d:
                raise ConfigError(
                    f"{LAW_ID}: ligand {ligand.identity.id}'s trace {ligand.trace_mM:g} mM exceeds "
                    f"{TRACE_LIMIT:g} K_d = {TRACE_LIMIT * k_d:g} mM of population {p.id} (K_d "
                    f"{k_d:g} mM): the trace would occupy more than {TRACE_LIMIT:g} of its sites "
                    "(§4.3)"
                )


def parse_occupancy(raw, base):
    _fields(raw, {"law", "species", "populations"}, "site occupancy")
    if raw["law"] != LAW_ID:
        raise ConfigError("A site occupancy requires law " + LAW_ID)
    m = base.model
    ligands = parse_ligands(raw["species"], base)
    names = {ligand.identity.id for ligand in ligands}
    if type(raw["populations"]) is not list:
        raise ConfigError(f"{LAW_ID} declares its populations in an explicit list")
    populations = tuple(parse_population(entry, m, names) for entry in raw["populations"])
    if len({p.id for p in populations}) != len(populations):
        raise ConfigError(f"{LAW_ID} lists a population twice")
    check_traces(m, ligands, populations)
    return Occupancy(LAW_ID, ligands, populations)


def occupancy_to_dict(declaration):
    if type(declaration) is not Occupancy:
        raise ConfigError("Require explicit immutable site occupancy declaration types")

    def owner(p):
        if p.owner_kind == "node":
            return dict(node=p.owner_id)
        if p.owner_kind == "patch":
            return dict(patch=p.owner_id, face=p.facing)
        return dict(contact=p.owner_id, side=p.facing)

    def catalogue(value):
        return None if value is None else dict(catalogue=value[0], entry=value[1])

    return dict(
        law=declaration.law,
        species=[
            dict(
                id=ligand.identity.id,
                catalogue=catalogue(ligand.identity.catalogue),
                evidence=ligand.identity.evidence,
                trace_mM=ligand.trace_mM,
            )
            for ligand in declaration.species
        ],
        populations=[
            dict(
                id=p.id,
                functional_unit=p.functional_unit,
                catalogue=catalogue(p.catalogue),
                owner=owner(p),
                copies=p.copies,
                sites_per_copy=p.sites_per_copy,
                accessible_fraction=p.accessible_fraction,
                ligand=p.ligand,
                association_rate_per_mM_per_s=p.k_on,
                dissociation_rate_per_s=p.k_off,
                initial_occupancy=p.initial_occupancy,
                internalisation=None
                if p.internalisation_rate is None
                else dict(rate_per_s=p.internalisation_rate, destination=p.destination),
            )
            for p in declaration.populations
        ],
    )


# ------------------------------------------------------------------ schedules


def _changes(raw, base, what):
    if type(raw) is not list or not raw:
        raise ConfigError(f"{LAW_ID}: {what} lists its changes")
    dt, end = base.execution.dt, base.experiment.end_time
    changes = []
    for change in raw:
        _fields(change, {"time", "multiplier"}, f"{CONTROLS_KEY} change")
        time = _number(change["time"], f"a change time of {what}")
        if on_grid(time, dt) is None:
            raise ConfigError(f"{LAW_ID}: a schedule change must be {ON_THE_GRID}")
        if not 0.0 <= time <= end:
            raise ConfigError(f"{LAW_ID}: a schedule change lies outside the horizon")
        changes.append((time, _number(change["multiplier"], f"a multiplier of {what}", low=0.0)))
    times = [t for t, _ in changes]
    if any(b <= a for a, b in zip(times, times[1:], strict=False)):
        raise ConfigError(f"{LAW_ID}: schedule times increase strictly")
    if times[0] != 0.0:
        raise ConfigError(f"{LAW_ID}: {what} starts at time 0")
    return tuple(changes)


def parse_controls(raw, base, declaration):
    entries = raw[CONTROLS_KEY]
    if type(entries) is not list:
        raise ConfigError(f"{CONTROLS_KEY} requires an explicit list")
    needed = {(p.id, "binding") for p in declaration.populations}
    needed |= {
        (p.id, "internalisation")
        for p in declaration.populations
        if p.internalisation_rate is not None
    }
    controls, seen = [], set()
    for entry in entries:
        _fields(entry, {"population", "route", "schedule"}, f"{CONTROLS_KEY} entry")
        key = (entry["population"], entry["route"])
        if key not in needed:
            raise ConfigError(
                f"{LAW_ID}: {CONTROLS_KEY} names no declared route ({key[0]}, {key[1]})"
            )
        if key in seen:
            raise ConfigError(f"{LAW_ID}: one schedule per population and route {key}")
        seen.add(key)
        what = f"the {key[1]} schedule of {key[0]}"
        controls.append(SiteControl(key[0], key[1], _changes(entry["schedule"], base, what)))
    missing = sorted(needed - seen)
    if missing:
        raise ConfigError(f"{LAW_ID}: every route needs a schedule; missing {missing[0]}")
    return tuple(controls)


def route_tables(declaration, schedule, spec=None):
    """[route] multiplier tables: each population's binding, then its internalisation (or a
    constant 0 for a population without the route). With W (cells.operator.site_occupant_replacement@1) in
    `spec`, a covered population's tables follow its slot's occupants: the founder's schedule, which
    ends at its death, then each newcomer's template multipliers, held through its life (FR-26;
    a newcomer's own schedule is version 1.1). Without W the tables are as before, bit for bit."""
    keyed = {(c.population, c.route): c.changes for c in schedule}
    binding = [keyed[(p.id, "binding")] for p in declaration.populations]
    internal = [
        keyed.get((p.id, "internalisation"), ((0.0, 0.0),)) for p in declaration.populations
    ]
    occupant = None if spec is None else occupant_of(spec)
    if occupant is None:
        return binding, internal
    newcomers = occupant_tables(spec, declaration, occupant)
    for k, p in enumerate(declaration.populations):
        rows = newcomers.get(p.id, ())
        if not rows:
            continue
        death = rows[0][0]
        for table, route in ((binding, "binding"), (internal, "internalisation")):
            late = [t for t, _ in table[k] if t >= death]
            if late and (p.id, route) in keyed:
                raise ConfigError(
                    f"{LAW_ID}: the {route} schedule of {p.id} changes at {late[0]:g} s, after its "
                    f"founder's death at {death:g} s; a newcomer takes its template's multipliers "
                    "(a newcomer's own schedule is version 1.1)"
                )
        binding[k] = (*binding[k], *((t, b) for t, (_, b, _) in rows))
        if p.internalisation_rate is not None:
            internal[k] = (*internal[k], *((t, i) for t, (_, _, i) in rows))
    return binding, internal


# ------------------------------------------------------------------ composition checks


def check_identities(spec, declaration):
    """A ligand declared with another identity than its one authority is refused (the species
    registry: D150's and D152's operators come first, as authors, in either order; §1.6, D176)."""
    common.check_identities(spec, LAW_ID, tuple(ligand.identity for ligand in declaration.species))


def check_slots(spec, declaration):
    """No contact population incident to a replaced slot (§6.2; contacts stay refused), and no
    patch population on a replaced slot unless cells.operator.site_occupant_replacement@1, W, declares its
    occupants (FR-26, D244)."""
    _, events = common.replacement_of(spec)
    slots = {v.slot for v in events}
    m = spec.model
    occupant = occupant_of(spec) is not None
    for p in declaration.populations:
        if p.owner_kind == "node":
            continue  # FR-28: a node's own sites sit on no slot.
        if p.owner_kind == "patch":
            cells = {next(q for q in m.membranes if q.id == p.owner_id).inside}
        else:
            junction = next(j for j in m.junctions if j.id == p.owner_id)
            cells = {junction.sender, junction.receiver}
        if not cells & slots:
            continue
        if p.owner_kind == "contact":
            raise ConfigError(
                f"{LAW_ID}: population {p.id} sits on contact {p.owner_id}, incident to a slot "
                f"{common.REPLACEMENT_LAW} replaces; a contact population there is refused in "
                "version 1 (where its bound material goes at the contact's restart needs a ruling)"
            )
        if not occupant:
            raise ConfigError(
                f"{LAW_ID}: population {p.id} sits on patch {p.owner_id} of a slot "
                f"{common.REPLACEMENT_LAW} replaces; its occupants need {OCCUPANT_LAW} (W), "
                "which resets it from each newcomer's template"
            )


def check_compartments(spec, declaration):
    """No internalisation on a patch whose outside node is a declared compartment (§2.4, §6.4)."""
    nodes = set()
    for op, other, _ in composite_spec.entries(spec):
        if op.LAW_ID == COMPARTMENTS_LAW:
            nodes |= {c.node for c in other.compartments}
    m = spec.model
    for p in declaration.populations:
        if p.internalisation_rate is None:
            continue
        patch = next(q for q in m.membranes if q.id == p.owner_id)
        if patch.outside in nodes:
            raise ConfigError(
                f"{LAW_ID}: population {p.id} internalises from compartment {patch.outside!r}; "
                "internalisation into or out of a compartment is FR-1's and FR-2's door (§6.4)"
            )


def check_template_traces(spec, declaration):
    """§4.3's trace rule on replacement templates' declared concentrations."""
    replacement, _ = common.replacement_of(spec)
    if replacement is None:
        return
    ids = list(spec.model.species_ids)
    extra = []
    for template in replacement.templates:
        if template.amounts_fmol is None or template.volume_pL is None:
            continue  # A route-only template (donor copies) declares no amounts.
        for ligand in declaration.species:
            row = ids.index(ligand.identity.id)
            mM = template.amounts_fmol[row] / template.volume_pL
            extra.append((f"template {template.id}", ligand.identity.id, mM))
    check_traces(spec.model, declaration.species, declaration.populations, extra)


def check_schedule_traces(spec, declaration):
    """§4.3's trace rule on scheduled compositions: the bath schedule's (FR-23, D244) and the
    compartment wash's buffers (FR-27, D246). A dose or a wash may not set a ligand below its
    declared trace, as a declared node or a replacement template may not. Each is read from its
    operator's own parsed program on the host: the bath schedule's held series per bath (the
    declared content first) and the wash's events, each with a buffer for every neutral species,
    the ligands among them."""
    ids = list(spec.model.species_ids)
    volumes = {c.id: c.volume_pL for c in spec.model.extracellular}
    extra = []
    for op, other, schedule in composite_spec.entries(spec):
        if op.LAW_ID == BATH_LAW:
            for bath, series in zip(other.baths, schedule.held, strict=True):
                for time, amounts in series[1:]:
                    for ligand in declaration.species:
                        mM = amounts[ids.index(ligand.identity.id)] / volumes[bath]
                        extra.append(
                            (f"scheduled bath {bath} from {time:g} s", ligand.identity.id, mM)
                        )
        elif op.LAW_ID == WASH_LAW:
            for event in schedule.events:
                buffer = dict(event.buffer_mM)
                where = f"the buffer of the wash of {event.node} at {event.time:g} s"
                for ligand in declaration.species:
                    extra.append((where, ligand.identity.id, buffer[ligand.identity.id]))
    if extra:
        check_traces(spec.model, declaration.species, declaration.populations, extra)


def facing_outside_nodes(spec, declaration):
    """The indices of the outside nodes its populations face, sorted: finite nodes, since a
    population facing a held bath is refused at parse (parse_population)."""
    m = spec.model
    outside = [c.id for c in m.extracellular]
    nodes = set()
    for population in declaration.populations:
        kind, node = facing_node(m, population)
        if kind == OUTSIDE:
            nodes.add(outside.index(node))
    return tuple(sorted(nodes))


def check_definition(spec, declaration):
    if spec.execution.solver == "rk4":
        raise ConfigError(
            f"{LAW_ID} refuses RK4 in version 1 (§4.6): its bookings are exact and checked at "
            "rounding in the face-free world under IMEX, and no consumer needs it"
        )
    common.check_species_cap(spec, LAW_ID)
    check_identities(spec, declaration)
    check_slots(spec, declaration)
    check_compartments(spec, declaration)
    check_template_traces(spec, declaration)
    check_schedule_traces(spec, declaration)


# ------------------------------------------------------------------ binding


def components(spec, declaration):
    """[population] int64: the static components of the route graph (§3.3, 1.).

    Nodes are facing pools and receiving cells, keyed by (kind, index); binding joins a population
    to its facing node and internalisation to its receiving cell. Components are numbered in order
    of their first population."""
    m = spec.model
    cells = [c.id for c in m.cells]
    outside = [c.id for c in m.extracellular]
    parent = {}

    def root(key):
        while parent.setdefault(key, key) != key:
            key = parent[key]
        return key

    def join(a, b):
        parent[root(b)] = root(a)

    for k, p in enumerate(declaration.populations):
        kind, node = facing_node(m, p)
        join(("population", k), ("node", kind, (cells if kind == CELL else outside).index(node)))
        if p.internalisation_rate is not None:
            join(("population", k), ("node", CELL, cells.index(receiving_cell(m, p))))
    labels, out = {}, []
    for k in range(len(declaration.populations)):
        out.append(labels.setdefault(root(("population", k)), len(labels)))
    return np.asarray(out, dtype=np.int64)


def bind(spec, declaration):
    """(state, layout) arrays of the populations (§2.5; R7: every parameter a binding)."""
    m = spec.model
    cells = [c.id for c in m.cells]
    outside = [c.id for c in m.extracellular]
    ids = list(m.species_ids)
    n = len(declaration.populations)
    capacity = np.asarray(
        [
            p.accessible_fraction * p.sites_per_copy * p.copies / SITES_PER_FMOL
            for p in declaration.populations
        ],
        dtype=np.float64,
    ).reshape(n)
    bound = np.asarray([p.initial_occupancy for p in declaration.populations]).reshape(n) * capacity
    kinds, nodes, receiving = [], [], []
    for p in declaration.populations:
        kind, node = facing_node(m, p)
        kinds.append(kind)
        nodes.append((cells if kind == CELL else outside).index(node))
        receiving.append(
            cells.index(receiving_cell(m, p)) if p.internalisation_rate is not None else 0
        )
    component = components(spec, declaration)
    pools, facing_pool, receiving_pool = [], [], []
    for k, p in enumerate(declaration.populations):
        key = (kinds[k], nodes[k], ids.index(p.ligand))
        if key not in pools:
            pools.append(key)
        facing_pool.append(pools.index(key))
        if p.internalisation_rate is not None:
            key = (CELL, receiving[k], ids.index(p.ligand))
            if key not in pools:
                pools.append(key)
            receiving_pool.append(pools.index(key))
        else:
            receiving_pool.append(facing_pool[-1])
    pool_component = [0] * len(pools)
    for k in range(n):
        pool_component[facing_pool[k]] = int(component[k])
        pool_component[receiving_pool[k]] = int(component[k])
    count = int(component.max()) + 1 if n else 0
    layout = dict(
        site_capacity_fmol=capacity,
        site_free_anchor_fmol=capacity - bound,
        site_bound_anchor_fmol=bound,
        site_on_rate=np.asarray([p.k_on for p in declaration.populations]).reshape(n),
        site_off_rate=np.asarray([p.k_off for p in declaration.populations]).reshape(n),
        site_internalisation_rate=np.asarray(
            [p.internalisation_rate or 0.0 for p in declaration.populations]
        ).reshape(n),
        site_standard_RT=np.asarray(
            [math.log(p.k_off / p.k_on) for p in declaration.populations]
        ).reshape(n),
        site_ligand_row=np.asarray(
            [ids.index(p.ligand) for p in declaration.populations], dtype=np.int64
        ).reshape(n),
        site_facing_kind=np.asarray(kinds, dtype=np.int64).reshape(n),
        site_facing_node=np.asarray(nodes, dtype=np.int64).reshape(n),
        site_receiving_cell=np.asarray(receiving, dtype=np.int64).reshape(n),
        site_internalises=np.asarray(
            [p.internalisation_rate is not None for p in declaration.populations], dtype=bool
        ).reshape(n),
        site_component=component,
        site_component_count=np.zeros(count),
        site_pool_kind=np.asarray([k for k, _, _ in pools], dtype=np.int64).reshape(len(pools)),
        site_pool_node=np.asarray([v for _, v, _ in pools], dtype=np.int64).reshape(len(pools)),
        site_pool_row=np.asarray([r for _, _, r in pools], dtype=np.int64).reshape(len(pools)),
        site_pool_component=np.asarray(pool_component, dtype=np.int64).reshape(len(pools)),
        site_facing_pool=np.asarray(facing_pool, dtype=np.int64).reshape(n),
        site_receiving_pool=np.asarray(receiving_pool, dtype=np.int64).reshape(n),
    )
    x = spec.execution
    state = {
        "site_free_increment_fmol": np.zeros(n),
        "site_bound_increment_fmol": np.zeros(n),
        "site_bound_net_fmol": np.zeros(n),
        "site_internalised_fmol": np.zeros(n),
        "site_dissipated_energy_pJ": np.zeros(x.capacity),
        "site_outside_dissipated_energy_pJ": np.zeros(x.extracellular_capacity),
        "site_work_pJ": np.zeros(n),
        "site_energy_magnitude_pJ": np.zeros(n),
    }
    return state, layout


def identity_block(declaration):
    """The summary's identity block: ligands and populations, metadata only (§1.6)."""
    return dict(
        site_ligands=[
            dict(
                id=ligand.identity.id,
                catalogue=None
                if ligand.identity.catalogue is None
                else list(ligand.identity.catalogue),
                evidence=ligand.identity.evidence,
                trace_mM=ligand.trace_mM,
            )
            for ligand in declaration.species
        ],
        site_populations=[
            dict(
                id=p.id,
                functional_unit=p.functional_unit,
                catalogue=None if p.catalogue is None else list(p.catalogue),
                owner=dict(kind=p.owner_kind, id=p.owner_id, facing=p.facing),
                ligand=p.ligand,
                laws=[BINDING_LAW]
                + ([INTERNALISATION_LAW] if p.internalisation_rate is not None else []),
            )
            for p in declaration.populations
        ],
    )


# ------------------------------------------------------------------ the half-step (stage B)
#
# The integrator below is D152's SSPRK(3,3) under its unidirectional stage condition, with D152's
# exact bookings and per-route hybrid (operators/species_reactions.py, half_step_terms),
# reimplemented here over the site network, because D152's files stay untouched while MG0c is
# judged (the lead, 15 November 2026). It duplicates a numerical block: a consolidation item for
# D172's round, one shared numerical block in the inner model's numerical plan serving D152 and
# FR-3 (docs/SITE_OCCUPANCY_DESIGN.md §12).

THETA = 0.5  # The stage condition h max L <= THETA at every stage (dt L <= 1 at one sub-step).
SERIES_BELOW = 1e-6  # |x| below which (1 + x) log1p(x) / x takes its series.
SITE_FLOOR_FMOL = 1e-20  # The own ledgers' floor: D150's species-scale material floor.
ROUNDING = 2.5  # The family's per-step rounding allowance, eps x steps x magnitude.


def _scatter(values, index, size, *, xp):
    """values [k] summed onto [size] by index [k]."""
    if xp is jnp:
        return jnp.zeros(size, dtype=values.dtype).at[index].add(values)
    out = np.zeros(size)
    np.add.at(out, np.asarray(index), values)
    return out


def _scatter2(values, row, node, shape, *, xp):
    """values [k] summed onto [rows, nodes] at (row[k], node[k])."""
    if xp is jnp:
        return jnp.zeros(shape, dtype=values.dtype).at[row, node].add(values)
    out = np.zeros(shape)
    np.add.at(out, (np.asarray(row), np.asarray(node)), values)
    return out


def _ratio(x, *, xp):
    """(1 + x) log1p(x) / x, with its series 1 + x/2 - x^2/6 for |x| < SERIES_BELOW."""
    small = xp.abs(x) < SERIES_BELOW
    return xp.where(
        small, 1.0 + x / 2 - x * x / 6, (1.0 + x) * xp.log1p(x) / xp.where(small, 1.0, x)
    )


def _xlogy(x, y, *, xp):
    zero = x == 0
    return xp.where(zero, 0.0, x * xp.log(xp.where(zero, 1.0, y)))


def site_free_energy(a, d, standard, capacity, rt, *, xp):
    """(dg, its absolute terms), pJ: the change of g(x) = mu° x + RT x ln(x/S) from a to a + d
    (§3.3's stable increments: a > 0, and the a = 0 branch, xlogy)."""
    positive = a > 0
    safe = xp.where(positive, a, 1.0)
    log_a = xp.log(safe / capacity)
    grow = xp.log1p(d / safe)
    first = d * log_a
    second = (a + d) * grow
    zero_branch = _xlogy(d, xp.where(d > 0, d, 1.0) / capacity, xp=xp)
    linear = standard * d
    dg = linear + rt * xp.where(positive, first + second, zero_branch)
    terms = xp.abs(linear) + rt * xp.where(
        positive, xp.abs(first) + xp.abs(second), xp.abs(zero_branch)
    )
    return dg, terms


def site_potential(a, d, standard, capacity, rt, *, xp):
    """mu-bar, pJ/fmol: the divided difference of g over [a, a + d] (padded finite at a = d = 0)."""
    positive = a > 0
    safe = xp.where(positive, a, 1.0)
    bulk = xp.log(safe / capacity) + _ratio(d / safe, xp=xp)
    start = xp.log(xp.where(d > 0, d, capacity) / capacity)  # a = 0: mu° + RT ln(d / S).
    return standard + rt * xp.where(positive, bulk, start)


def pool_amounts(state, p, *, xp):
    """[pool] the free ligand at each node pool (fmol): @3's physical amount of its row there."""
    is_cell = p.site_pool_kind == CELL
    rows, nodes = p.site_pool_row, p.site_pool_node
    cell_node = xp.where(is_cell, nodes, 0)
    outside_node = xp.where(is_cell, 0, nodes)
    reference = xp.asarray(p.amount_reference)  # A layout bound as NumPy under jnp, too.
    outside_reference = xp.asarray(p.extracellular_amount_reference)
    cells = reference[rows, cell_node] + xp.asarray(state.amount_increment)[rows, cell_node]
    outside = (
        outside_reference[rows, outside_node]
        + xp.asarray(state.extracellular_amount_increment)[rows, outside_node]
    )
    return xp.where(is_cell, cells, outside)


def pool_volumes(p, *, xp):
    is_cell = p.site_pool_kind == CELL
    nodes = p.site_pool_node
    return xp.where(
        is_cell,
        xp.asarray(p.volume)[xp.where(is_cell, nodes, 0)],
        xp.asarray(p.extracellular_volume)[xp.where(is_cell, 0, nodes)],
    )


class SiteStep(NamedTuple):
    """One half-step of the site network: everything the update and the bookings read."""

    dn: object  # [pool] the free ligand's change.
    dbound: object  # [population] B's change; R's is its negation.
    binding: object  # [population] the binding extent (signed).
    internalised: object  # [population] the internalisation extent (>= 0).
    on: object  # [population] a route with a positive multiplier.
    pool_on: object  # [pool] a pool that a route with a positive multiplier touches.
    pool_heat: object  # [pool] pJ, booked at the pool's node.
    work: object  # [population] pJ.
    magnitude: object  # [population] pJ.
    nonreversing: object  # [population] the hybrid's branch for the binding route.
    rates: object  # ((J, U) at Y1, Y2, Y3), fmol/s.
    max_hl: object
    valid: object


def _route_rates(n, R, B, vol, mb, mi, p, *, xp):
    f = p.site_facing_pool
    c = n[f] / vol[f]
    J = mb * (p.site_on_rate * c * R - p.site_off_rate * B)
    U = mi * p.site_internalisation_rate * B
    return J, U, c


def _stage(n, R, B, vol, mb, mi, h, p, *, xp):
    """(J, U, the stage condition h max L <= THETA, max h L) at these amounts (§4.2)."""
    J, U, c = _route_rates(n, R, B, vol, mb, mi, p, xp=xp)
    f = p.site_facing_pool
    size = n.shape[0]
    load_n = _scatter(mb * p.site_on_rate * R, f, size, xp=xp) / vol
    load_r = mb * p.site_on_rate * c
    load_b = mb * p.site_off_rate + mi * p.site_internalisation_rate
    hl = h * xp.concatenate((load_n, load_r, load_b))
    worst = xp.max(hl, initial=0.0)
    return J, U, worst <= THETA, worst


def _change(J, U, p, size, *, xp):
    """(dn [pool], dB [population]) of the binding rates J and the internalisation rates U."""
    dn = -_scatter(J, p.site_facing_pool, size, xp=xp) + _scatter(
        U, p.site_receiving_pool, size, xp=xp
    )
    return dn, J - U


def _affinity(n, R, B, vol, p, *, xp):
    """The binding route's A / RT = ln(c R / (K_d B)) (finite padding where a pool is empty: the
    sign of the empty side's limit)."""
    c = n[p.site_facing_pool] / vol[p.site_facing_pool]
    full = (R > 0) & (B > 0) & (c > 0)
    safe_r = xp.where(full, R, 1.0)
    safe_b = xp.where(full, B, 1.0)
    safe_c = xp.where(full, c, 1.0)
    value = xp.log(safe_c) + xp.log(safe_r) - p.site_standard_RT - xp.log(safe_b)
    return xp.where(full, value, xp.where(B > 0, -1.0, 1.0))


def half_step_terms(state, mb, mi, h, p, *, xp):
    """SSPRK(3,3) over h on the site network (§4.2) and its bookings (§3.3): a SiteStep."""
    mi = xp.where(p.site_internalises, mi, 0.0)
    n = pool_amounts(state, p, xp=xp)
    vol = pool_volumes(p, xp=xp)
    R = p.site_free_anchor_fmol + state.site_free_increment_fmol
    B = p.site_bound_anchor_fmol + state.site_bound_increment_fmol
    size = n.shape[0]
    J1, I1, ok1, l1 = _stage(n, R, B, vol, mb, mi, h, p, xp=xp)
    dn1, db1 = _change(J1, I1, p, size, xp=xp)
    n2, B2, R2 = n + h * dn1, B + h * db1, R - h * db1
    J2, I2, ok2, l2 = _stage(n2, R2, B2, vol, mb, mi, h, p, xp=xp)
    dn2, db2 = _change(J2, I2, p, size, xp=xp)
    n3 = n + 0.25 * h * (dn1 + dn2)
    B3 = B + 0.25 * h * (db1 + db2)
    R3 = R - 0.25 * h * (db1 + db2)
    J3, I3, ok3, l3 = _stage(n3, R3, B3, vol, mb, mi, h, p, xp=xp)
    binding = h * (J1 + J2 + 4.0 * J3) / 6.0
    internalised = h * (I1 + I2 + 4.0 * I3) / 6.0
    dn, dbound = _change(binding, internalised, p, size, xp=xp)
    end_n, end_b, end_r = n + dn, B + dbound, R - dbound
    valid = ok1 & ok2 & ok3
    for pools, sites_b, sites_r in ((n2, B2, R2), (n3, B3, R3), (end_n, end_b, end_r)):
        valid &= xp.all(xp.isfinite(pools) & (pools > 0))
        valid &= xp.all(xp.isfinite(sites_b) & (sites_b >= 0))
        valid &= xp.all(xp.isfinite(sites_r) & (sites_r >= 0))
    rt = 1e-3 * R_GAS * p.temperature
    standard = rt * p.site_standard_RT
    capacity = p.site_capacity_fmol
    on = (mb > 0) | (mi > 0)
    f, g = p.site_facing_pool, p.site_receiving_pool
    internalises = p.site_internalises
    touched = _scatter(xp.where(on, 1.0, 0.0), f, size, xp=xp)
    touched = touched + _scatter(xp.where(on & internalises, 1.0, 0.0), g, size, xp=xp)
    pool_on = touched > 0
    # The exact dG of every pool over the half-step, with its absolute terms.
    change = xp.where(pool_on, dn, 0.0)
    pool_dg = adapter.species_chemical_free_energy_pJ(n, change, vol, p.temperature, xp=xp)
    pool_terms = adapter.species_chemical_magnitude_pJ(n, change, vol, p.temperature, xp=xp)
    dg_b, terms_b = site_free_energy(B, dbound, standard, capacity, rt, xp=xp)
    dg_r, terms_r = site_free_energy(R, -dbound, 0.0, capacity, rt, xp=xp)
    # The class of each component in this step (§3.3, 2.): mixed if any of its internalisation
    # routes has a positive multiplier, else passive-only.
    count = p.site_component_count.shape[0]
    mixed_component = (
        _scatter(xp.where((mi > 0) & internalises, 1.0, 0.0), p.site_component, count, xp=xp) > 0
    )
    mixed = mixed_component[p.site_component]
    pool_mixed = mixed_component[p.site_pool_component]
    # Passive-only: each facing node's sub-system books H = -dG, and no work.
    subsystem = pool_dg + _scatter(xp.where(mixed, 0.0, dg_b + dg_r), f, size, xp=xp)
    # Mixed: average-vector-field shares with divided-difference potentials, and the hybrid heat on
    # each binding route (its share unless it reverses within the step, else its quadrature).
    mu_n = rt * (xp.log(n / vol) + _ratio(change / n, xp=xp) - 1.0)
    mu_b = site_potential(B, dbound, standard, capacity, rt, xp=xp)
    mu_r = site_potential(R, -dbound, 0.0, capacity, rt, xp=xp)
    share_b = binding * (mu_b - mu_r - mu_n[f])
    share_i = internalised * (mu_r + mu_n[g] - mu_b)
    a1 = _affinity(n, R, B, vol, p, xp=xp)
    a2 = _affinity(n2, R2, B2, vol, p, xp=xp)
    a3 = _affinity(n3, R3, B3, vol, p, xp=xp)
    a_end = _affinity(end_n, end_r, end_b, vol, p, xp=xp)
    sign = xp.sign(J1)
    nonreversing = (
        (sign != 0) & (xp.sign(J2) == sign) & (xp.sign(J3) == sign) & (xp.sign(a_end) == sign)
    )
    quadrature = h * rt * (J1 * a1 + J2 * a2 + 4.0 * J3 * a3) / 6.0
    route_heat = xp.where(nonreversing, -share_b, quadrature)
    route_heat = xp.where(mixed & (mb > 0), route_heat, 0.0)
    pool_heat = xp.where(
        pool_mixed, _scatter(route_heat, f, size, xp=xp), -xp.where(pool_on, subsystem, 0.0)
    )
    work = xp.where(mixed, share_i + share_b + route_heat, 0.0)
    magnitude = terms_b + terms_r + xp.abs(share_b) + xp.abs(share_i) + xp.abs(route_heat)
    magnitude = magnitude + pool_terms[f] + xp.where(internalises, pool_terms[g], 0.0)
    for value in (pool_heat, work, magnitude):
        valid &= xp.all(xp.isfinite(value))
    worst = xp.maximum(xp.maximum(l1, l2), l3)
    return SiteStep(
        dn,
        dbound,
        binding,
        internalised,
        on,
        pool_on,
        pool_heat,
        work,
        magnitude,
        nonreversing,
        ((J1, I1), (J2, I2), (J3, I3)),
        worst,
        valid,
    )


NON_NEGATIVE = ("site_internalised_fmol", "site_energy_magnitude_pJ")
SIGNED = (
    "site_free_increment_fmol",
    "site_bound_increment_fmol",
    "site_bound_net_fmol",
    "site_dissipated_energy_pJ",
    "site_outside_dissipated_energy_pJ",
    "site_work_pJ",
)


def site_domain_valid(state, p, *, xp):
    """Its own fields finite and signed as booked, and its pools: R >= 0 and B >= 0."""
    valid = xp.asarray(True)
    for name in NON_NEGATIVE:
        value = getattr(state, name)
        valid &= xp.all(xp.isfinite(value)) & xp.all(value >= 0)
    for name in SIGNED:
        valid &= xp.all(xp.isfinite(getattr(state, name)))
    R = p.site_free_anchor_fmol + state.site_free_increment_fmol
    B = p.site_bound_anchor_fmol + state.site_bound_increment_fmol
    return valid & xp.all(R >= 0) & xp.all(B >= 0)


def site_half_step(state, mb, mi, h, p, *, xp=jnp):
    """(state after h of the site network, validity). Each entry is selected where a route with a
    positive multiplier writes it, else its start value (never offset by a computed zero, §4.8)."""
    step = half_step_terms(state, mb, mi, h, p, xp=xp)
    on = step.on
    is_cell = p.site_pool_kind == CELL
    rows, nodes = p.site_pool_row, p.site_pool_node
    dn = xp.where(step.pool_on, step.dn, 0.0)
    cell_dn = _scatter2(
        xp.where(is_cell, dn, 0.0),
        rows,
        xp.where(is_cell, nodes, 0),
        state.amount_increment.shape,
        xp=xp,
    )
    outside_dn = _scatter2(
        xp.where(is_cell, 0.0, dn),
        rows,
        xp.where(is_cell, 0, nodes),
        state.extracellular_amount_increment.shape,
        xp=xp,
    )
    cell_written = (
        _scatter2(
            xp.where(is_cell & step.pool_on, 1.0, 0.0),
            rows,
            xp.where(is_cell, nodes, 0),
            state.amount_increment.shape,
            xp=xp,
        )
        > 0
    )
    outside_written = (
        _scatter2(
            xp.where(~is_cell & step.pool_on, 1.0, 0.0),
            rows,
            xp.where(is_cell, 0, nodes),
            state.extracellular_amount_increment.shape,
            xp=xp,
        )
        > 0
    )
    heat_cell = _scatter(
        xp.where(is_cell & step.pool_on, step.pool_heat, 0.0),
        xp.where(is_cell, nodes, 0),
        state.site_dissipated_energy_pJ.shape[0],
        xp=xp,
    )
    heat_outside = _scatter(
        xp.where(~is_cell & step.pool_on, step.pool_heat, 0.0),
        xp.where(is_cell, 0, nodes),
        state.site_outside_dissipated_energy_pJ.shape[0],
        xp=xp,
    )
    heated_cell = (
        _scatter(
            xp.where(is_cell & step.pool_on, 1.0, 0.0),
            xp.where(is_cell, nodes, 0),
            state.site_dissipated_energy_pJ.shape[0],
            xp=xp,
        )
        > 0
    )
    heated_outside = (
        _scatter(
            xp.where(~is_cell & step.pool_on, 1.0, 0.0),
            xp.where(is_cell, 0, nodes),
            state.site_outside_dissipated_energy_pJ.shape[0],
            xp=xp,
        )
        > 0
    )
    new = state._replace(
        amount_increment=xp.where(
            cell_written, state.amount_increment + cell_dn, state.amount_increment
        ),
        extracellular_amount_increment=xp.where(
            outside_written,
            state.extracellular_amount_increment + outside_dn,
            state.extracellular_amount_increment,
        ),
        site_free_increment_fmol=xp.where(
            on, state.site_free_increment_fmol - step.dbound, state.site_free_increment_fmol
        ),
        site_bound_increment_fmol=xp.where(
            on, state.site_bound_increment_fmol + step.dbound, state.site_bound_increment_fmol
        ),
        site_bound_net_fmol=xp.where(
            on, state.site_bound_net_fmol + step.binding, state.site_bound_net_fmol
        ),
        site_internalised_fmol=xp.where(
            on, state.site_internalised_fmol + step.internalised, state.site_internalised_fmol
        ),
        site_dissipated_energy_pJ=xp.where(
            heated_cell,
            state.site_dissipated_energy_pJ + heat_cell,
            state.site_dissipated_energy_pJ,
        ),
        site_outside_dissipated_energy_pJ=xp.where(
            heated_outside,
            state.site_outside_dissipated_energy_pJ + heat_outside,
            state.site_outside_dissipated_energy_pJ,
        ),
        site_work_pJ=xp.where(on, state.site_work_pJ + step.work, state.site_work_pJ),
        site_energy_magnitude_pJ=xp.where(
            on, state.site_energy_magnitude_pJ + step.magnitude, state.site_energy_magnitude_pJ
        ),
    )
    return new, step.valid & site_domain_valid(new, p, xp=xp)


def site_energy(row, p, *, xp):
    """(G_site(now) - G_site(declared), its absolute terms), pJ, summed over the populations: the
    owner's endpoint free energy relative to the declared reference (§3.3)."""
    rt = 1e-3 * R_GAS * p.temperature
    capacity = p.site_capacity_fmol
    dg_b, terms_b = site_free_energy(
        p.site_bound_anchor_fmol,
        row.site_bound_increment_fmol,
        rt * p.site_standard_RT,
        capacity,
        rt,
        xp=xp,
    )
    dg_r, terms_r = site_free_energy(
        p.site_free_anchor_fmol, row.site_free_increment_fmol, 0.0, capacity, rt, xp=xp
    )
    return entity_sum(dg_b + dg_r, axis=None, xp=xp), entity_sum(
        terms_b + terms_r, axis=None, xp=xp
    )


def material_terms(row, p, shape_cell, shape_outside, *, xp):
    """(local [species, cell], outside [species, outside]) terms, removed - supplied (D150's sign):
    the facing node loses net binding, the receiving cell gains what is internalised."""
    is_cell = p.site_facing_kind == CELL
    rows = p.site_ligand_row
    nodes = p.site_facing_node
    local = _scatter2(
        xp.where(is_cell, row.site_bound_net_fmol, 0.0),
        rows,
        xp.where(is_cell, nodes, 0),
        shape_cell,
        xp=xp,
    )
    local = local - _scatter2(
        xp.where(p.site_internalises, row.site_internalised_fmol, 0.0),
        rows,
        p.site_receiving_cell,
        shape_cell,
        xp=xp,
    )
    outside = _scatter2(
        xp.where(is_cell, 0.0, row.site_bound_net_fmol),
        rows,
        xp.where(is_cell, 0, nodes),
        shape_outside,
        xp=xp,
    )
    return local, outside


def material_magnitudes(row, p, shape_cell, shape_outside, *, xp):
    is_cell = p.site_facing_kind == CELL
    rows = p.site_ligand_row
    nodes = p.site_facing_node
    moved = xp.abs(row.site_bound_net_fmol)
    local = _scatter2(
        xp.where(is_cell, moved, 0.0), rows, xp.where(is_cell, nodes, 0), shape_cell, xp=xp
    )
    local = local + _scatter2(
        xp.where(p.site_internalises, row.site_internalised_fmol, 0.0),
        rows,
        p.site_receiving_cell,
        shape_cell,
        xp=xp,
    )
    outside = _scatter2(
        xp.where(is_cell, 0.0, moved), rows, xp.where(is_cell, 0, nodes), shape_outside, xp=xp
    )
    return local, outside


def readouts(row, control, p):
    """[population] (B/S, J, I) at a row's state and its held controls, in NumPy."""
    mb = np.asarray(control.site_binding_multiplier)
    mi = np.where(
        np.asarray(p.site_internalises), np.asarray(control.site_internalisation_multiplier), 0.0
    )
    n = pool_amounts(row, p, xp=np)
    vol = pool_volumes(p, xp=np)
    R = np.asarray(p.site_free_anchor_fmol) + np.asarray(row.site_free_increment_fmol)
    B = np.asarray(p.site_bound_anchor_fmol) + np.asarray(row.site_bound_increment_fmol)
    J, U, _ = _route_rates(n, R, B, vol, mb, mi, p, xp=np)
    return B / np.asarray(p.site_capacity_fmol), J, U


def stage_report(state, control, p, dt):
    """Host-side diagnosis of a refused step (§4.2): the largest h L over the three stages and the
    condition's verdict, as D152's stage_report."""
    step = half_step_terms(
        state,
        np.asarray(control.site_binding_multiplier),
        np.asarray(control.site_internalisation_multiplier),
        0.5 * dt,
        p,
        xp=np,
    )
    return dict(
        max_hL=float(step.max_hl), admitted=bool(step.max_hl <= THETA), valid=bool(step.valid)
    )


class SiteOccupancy(Operator):
    LAW_ID = LAW_ID
    IDENTITY_ROLE = "user"  # Species registry (D176): its ligands are species others declare.

    def species_identities(self, declaration):
        return tuple(ligand.identity for ligand in declaration.species)

    STEP_ID = STEP_ID
    SPLIT = True
    RK4 = "split"  # Declared; RK4 is refused at the definition (§4.6).
    STATE_AXES = STATE_AXES
    HEAT_FIELDS = ("site_dissipated_energy_pJ", "site_outside_dissipated_energy_pJ")
    WORK_FIELDS = ("site_work_pJ",)
    LAYOUT_FIELDS = LAYOUT_FIELDS
    CONTROL_FIELDS = CONTROL_FIELDS
    EXPERIMENT_KEYS = (CONTROLS_KEY,)
    # R3 (FR-24; docs/OPERATOR_FEATURES_FR23_24_26_DESIGN.md §3.3): its readable quantities per
    # population, from its own state (quantities).
    QUANTITIES = MappingProxyType(
        {
            "site_occupied_fraction": ("site_population", "1"),
            "site_occupied_fmol": ("site_population", "fmol"),
            "site_capacity_fmol": ("site_population", "fmol"),
        }
    )
    # D150's static-tissue list and D152's addition (§1.5): the half-step reads the declared
    # volumes, masks and outside anchors.
    CONFLICTS_VIEW = (
        "volume",
        "extracellular_volume",
        "active",
        "outside_active",
        "membrane_active",
        "extracellular_amount_reference",
    )
    # Door S (docs/SCOPED_COMPOSITION_DESIGN.md §5; FR-23, D244): its outside anchors and volumes
    # are read only at the outside nodes its populations face (pool_amounts, pool_volumes;
    # read_slots names them, finite by parse_population), so a change made elsewhere, such as the
    # bath schedule's dose at a held bath, does not meet them. A cell pool's index-0 entry in those
    # gathers is padding, selected away by where: no read. Volumes and masks of cells stay unscoped.
    SCOPED_READS = {
        name: Read("fixed", "split", scoped=True)
        for name in ("extracellular_volume", "extracellular_amount_reference")
    }
    READOUT_COLUMNS = READOUT_COLUMNS
    LEDGERS = LEDGERS
    LEDGER_DIAGNOSTICS = LEDGER_DIAGNOSTICS
    LEDGER_MESSAGE = LEDGER_MESSAGE
    ENTITY_WRITES = {
        "amount_increment": ("site_bound_net_fmol", "site_internalised_fmol"),
        "extracellular_amount_increment": ("site_bound_net_fmol",),
    }
    ACCEPTS_WRITES = {
        "site_free_increment_fmol": ("site_moiety_entity",),
        "site_bound_increment_fmol": ("site_bound_entity", "site_moiety_entity"),
    }

    # ------------------------------------------------------------ definition

    def parse(self, raw, base, inner_model):
        return parse_occupancy(raw, base)

    def to_dict(self, declaration, base):
        return occupancy_to_dict(declaration)

    def parse_schedule(self, raw, base, declaration):
        return parse_controls(raw, base, declaration)

    def schedule_to_dict(self, schedule, base, declaration):
        return {
            CONTROLS_KEY: [
                dict(
                    population=c.population,
                    route=c.route,
                    schedule=[dict(time=t, multiplier=v) for t, v in c.changes],
                )
                for c in schedule
            ]
        }

    def schedule_times(self, schedule):
        return common.schedule_times(schedule)

    def value_at(self, schedule, time):
        return common.value_at(schedule, time)

    def control_values(self, spec, declaration, schedule, records, indices, times):
        binding, internal = route_tables(declaration, schedule, spec)
        n = len(declaration.populations)
        b = common.control_arrays(binding, times, 1)[..., 0] if n else np.zeros((len(times), 0))
        i = common.control_arrays(internal, times, 1)[..., 0] if n else np.zeros((len(times), 0))
        return (b, i)

    def check_definition(self, spec, declaration, schedule, model):
        check_definition(spec, declaration)
        route_tables(declaration, schedule, spec)  # FR-26: a founder's change after its death.

    def read_slots(self, spec, declaration):
        """Door S: the outside nodes its populations face, for each scoped read (FR-23)."""
        return dict.fromkeys(self.SCOPED_READS, facing_outside_nodes(spec, declaration))

    def batch_signature(self, declaration):
        """The static structure (§2.7): ligands, each population's owner and facing, its ligand,
        whether it internalises and where; identities and every parameter are not part of it."""
        return (
            LAW_ID,
            tuple(ligand.identity.id for ligand in declaration.species),
            tuple(
                (
                    p.id,
                    p.owner_kind,
                    p.owner_id,
                    p.facing,
                    p.ligand,
                    p.internalisation_rate is not None,
                    p.destination,
                )
                for p in declaration.populations
            ),
        )

    def working_size(self, spec):
        """Stored values per accepted step plus a margin, the inner model's convention
        (surface_pump.working_size): each row holds six arrays per population (the free and bound
        increments, the bound net, the internalised amount, the work and the energy magnitude)
        and the two node-indexed dissipation arrays. The stage arrays are transient, so the
        margin is 2 (the lead's ruling on the external review's finding 1, 18 November 2026)."""
        (declaration,) = (d for op, d, _ in composite_spec.entries(spec) if op.LAW_ID == LAW_ID)
        x = spec.execution
        return 2 * (6 * len(declaration.populations) + x.capacity + x.extracellular_capacity)

    def summary(self, spec, declaration, schedule, history):
        return {"site_occupancy_law": LAW_ID, **identity_block(declaration)}

    # ------------------------------------------------------------ binding

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        return bind(spec, declaration)

    def statically_idle(self, p):
        return p.site_capacity_fmol.shape[0] == 0

    # ------------------------------------------------------------ step parts

    def half_step(self, state, h, control, p, *, xp):
        return site_half_step(
            state,
            control.site_binding_multiplier,
            control.site_internalisation_multiplier,
            h,
            p,
            xp=xp,
        )

    def control_valid(self, control, p, *, xp):
        valid = xp.asarray(True)
        for m in (control.site_binding_multiplier, control.site_internalisation_multiplier):
            valid &= xp.all(xp.isfinite(m) & (m >= 0))
        return valid

    def rates(self, state, control, p, view, *, xp):
        return {k: xp.zeros_like(getattr(state, k)) for k in self.STATE_AXES}, None, None

    def rate_checks(self, state, control, p, valid, *, xp):
        return valid & site_domain_valid(state, p, xp=xp)

    def domain_valid(self, state, p, valid, *, xp):
        own = site_domain_valid(state, p, xp=xp)
        return own if valid is None else valid & own

    def quantity_entities(self, spec, declaration):
        """R3, host side: its populations in axis order, each with the cell it belongs to."""
        m = spec.model
        return {
            "site_population": tuple((q.id, population_cell(m, q)) for q in declaration.populations)
        }

    def quantities(self, state, p, *, xp):
        """R3: per population its occupied fraction theta = B / (B + R), which the domain's B >= 0
        and R >= 0 keep in [0, 1] exactly (B + R is S to the moiety's rounding); its occupied amount
        B; and its accessible capacity S (fmol)."""
        free = p.site_free_anchor_fmol + state.site_free_increment_fmol
        bound = p.site_bound_anchor_fmol + state.site_bound_increment_fmol
        total = free + bound
        return dict(
            site_occupied_fraction=bound / xp.where(total > 0, total, 1.0),
            site_occupied_fmol=bound,
            site_capacity_fmol=p.site_capacity_fmol,
        )

    # ------------------------------------------------------------ ledgers

    def ledger_terms(self, result, row, p, *, xp):
        """@3's local and outside ledgers gain net binding at the facing node and lose what is
        internalised at the receiving cell (removed - supplied); the total sums them; the energy
        ledger gains the site free energy's change + heat - work (§2.5, §3.3)."""
        local, outside = material_terms(
            row, p, result["local"].shape, result["outside"].shape, xp=xp
        )
        result["local"] = result["local"] + local
        result["outside"] = result["outside"] + outside
        result["total"] = (
            result["total"] + entity_sum(local, axis=1, xp=xp) + entity_sum(outside, axis=1, xp=xp)
        )
        energy, _ = site_energy(row, p, xp=xp)
        result["energy"] = (
            result["energy"]
            + energy
            + entity_sum(row.site_dissipated_energy_pJ, axis=None, xp=xp)
            + entity_sum(row.site_outside_dissipated_energy_pJ, axis=None, xp=xp)
            - entity_sum(row.site_work_pJ, axis=None, xp=xp)
        )
        return result, self.own_ledgers(row, p, xp=xp)

    def own_ledgers(self, row, p, *, xp):
        return {
            "site_bound_entity": row.site_bound_increment_fmol
            - (row.site_bound_net_fmol - row.site_internalised_fmol),
            "site_moiety_entity": row.site_free_increment_fmol + row.site_bound_increment_fmol,
        }

    def own_magnitudes(self, row, p, *, xp):
        return (
            xp.abs(row.site_bound_increment_fmol)
            + xp.abs(row.site_bound_net_fmol)
            + xp.abs(row.site_internalised_fmol),
            xp.abs(row.site_free_increment_fmol) + xp.abs(row.site_bound_increment_fmol),
        )

    def own_bounds(self, magnitudes, steps):
        rounding = ROUNDING * np.finfo(float).eps * steps
        return tuple(SITE_FLOOR_FMOL + rounding * m for m in magnitudes)

    def magnitude_terms(self, magnitudes, row, p, *, xp):
        """The moved amounts in the material ledgers' magnitudes, and every booking's absolute
        terms with the site free energy's in the energy ledger's."""
        local, outside = material_magnitudes(
            row, p, magnitudes[0].shape, magnitudes[1].shape, xp=xp
        )
        magnitudes[0] = magnitudes[0] + local
        magnitudes[1] = magnitudes[1] + outside
        magnitudes[2] = (
            magnitudes[2] + entity_sum(local, axis=1, xp=xp) + entity_sum(outside, axis=1, xp=xp)
        )
        _, terms = site_energy(row, p, xp=xp)
        energy = terms + entity_sum(row.site_energy_magnitude_pJ, axis=None, xp=xp)
        magnitudes[6] = energy if magnitudes[6] is None else magnitudes[6] + energy
        return magnitudes

    # ------------------------------------------------------------ observations

    def observe(self, row, state, control, p, view, model, spec):
        columns = {k: getattr(state, k) for k in self.STATE_AXES}
        occupancy, binding, internalisation = readouts(state, control, p)
        columns["site_occupancy"] = occupancy
        columns["site_binding_rate_fmol_per_s"] = binding
        columns["site_internalisation_rate_fmol_per_s"] = internalisation
        return columns


# ------------------------------------------------------------------ W: cells.operator.site_occupant_replacement@1
#
# FR-26 (D244, option W; docs/OPERATOR_FEATURES_FR23_24_26_DESIGN.md §4): a replacement writer of
# site populations. At replacement@1's event steps it resets the populations on each replaced slot's
# patches to the newcomer's template occupancy through cells.operator.site_occupancy@1's accepted writes; the
# occupant's bound material leaves with it, recorded as departed, and the template's arrives,
# recorded as arrived. cells.operator.site_occupancy@1 and replacement@1 keep their structure and programs.

REPLACEMENT_LAW = common.REPLACEMENT_LAW
# A newcomer's bound and free sites each lie at least this many ulps of the capacity from empty:
# the event writes anchor + (amount - anchor), within about 1.5 ulps of the amount (check_occupant).
ARRIVAL_ULPS = 4
SITES_LAW = LAW_ID  # cells.operator.site_occupancy@1, the owner W writes (named apart from W's own LAW_ID).
OCCUPANT_LAW = "cells.operator.site_occupant_replacement@1"
OCCUPANT_STATE_AXES = {
    "site_departed_fmol": ["site_population"],  # Bound material leaving with occupants.
    "site_arrived_fmol": ["site_population"],  # Bound material arriving with newcomers.
    "site_replacement_free_energy_pJ": ["site_population"],  # The site free energy's jumps.
    "site_replacement_energy_magnitude_pJ": ["site_population"],  # Their absolute terms.
    "site_replacement_applied": ["cell_slot"],  # int64: the replacements applied per slot.
}
OCCUPANT_LAYOUT_FIELDS = (
    "site_replaced",  # [population] bool: a patch population on a replaced slot.
    "site_population_cell",  # [population] int64: its cell (slot).
)
OCCUPANT_CONTROL_FIELDS = (
    "site_replacement_count",  # [cell_slot] the replacements due by now at each slot.
    "site_arrival_occupancy",  # [population] the latest newcomer's template occupancy.
)


@dataclass(frozen=True)
class OccupantTemplate:
    template_id: str  # A replacement@1 template.
    # ((population id, arrival occupancy, binding multiplier, internalisation multiplier or None),
    # ...) in declared order.
    populations: tuple


@dataclass(frozen=True)
class OccupantDeclaration:
    law: str
    templates: tuple  # OccupantTemplate, in declared order.


def parse_occupant(raw, base):
    _fields(raw, {"law", "templates"}, "site occupant replacement")
    if raw["law"] != OCCUPANT_LAW:
        raise ConfigError("A site occupant replacement requires law " + OCCUPANT_LAW)
    if type(raw["templates"]) is not list or not raw["templates"]:
        raise ConfigError(f"{OCCUPANT_LAW} declares its templates in a non-empty list")
    templates = []
    for entry in raw["templates"]:
        _fields(entry, {"template_id", "populations"}, f"{OCCUPANT_LAW} template")
        tid = identifier(entry["template_id"])
        if not isinstance(entry["populations"], dict) or not entry["populations"]:
            raise ConfigError(f"{OCCUPANT_LAW}: template {tid} names its populations")
        rows = []
        for pid, values in entry["populations"].items():
            keys = set(values) if isinstance(values, dict) else set()
            if not {"initial_occupancy", "binding_multiplier"} <= keys or keys - {
                "initial_occupancy",
                "binding_multiplier",
                "internalisation_multiplier",
            }:
                raise ConfigError(
                    f"{OCCUPANT_LAW}: template {tid}'s population {pid} gives initial_occupancy "
                    "and binding_multiplier, and internalisation_multiplier where it internalises"
                )
            theta = _number(values["initial_occupancy"], f"{tid}'s occupancy of {pid}")
            if not 0 < theta < 1:
                raise ConfigError(
                    f"{OCCUPANT_LAW}: {tid}'s occupancy of {pid} lies in (0, 1) in version 1: as "
                    "everywhere in the engine, a pool goes to its trace and is never exactly empty "
                    "(FR-23's dose rule), so a template gives a fresh cell's occupancy at a trace "
                    "level (cells.operator.site_occupancy@1's site free energy reads an exactly empty pool, "
                    "reached from a positive anchor, as 0 x log1p(-1))"
                )
            binding = _number(values["binding_multiplier"], f"{tid}'s binding of {pid}", low=0.0)
            internal = values.get("internalisation_multiplier")
            if internal is not None:
                internal = _number(internal, f"{tid}'s internalisation of {pid}", low=0.0)
            rows.append((identifier(pid), theta, binding, internal))
        if len({r[0] for r in rows}) != len(rows):
            raise ConfigError(f"{OCCUPANT_LAW}: template {tid} names a population twice")
        templates.append(OccupantTemplate(tid, tuple(rows)))
    if len({t.template_id for t in templates}) != len(templates):
        raise ConfigError(f"{OCCUPANT_LAW}: a template is declared twice")
    return OccupantDeclaration(OCCUPANT_LAW, tuple(templates))


def occupant_to_dict(declaration):
    if type(declaration) is not OccupantDeclaration:
        raise ConfigError("Require explicit immutable site occupant replacement types")
    return dict(
        law=declaration.law,
        templates=[
            dict(
                template_id=t.template_id,
                populations={
                    pid: dict(
                        initial_occupancy=theta,
                        binding_multiplier=binding,
                        **({} if internal is None else {"internalisation_multiplier": internal}),
                    )
                    for pid, theta, binding, internal in t.populations
                },
            )
            for t in declaration.templates
        ],
    )


def _sites_of(spec):
    """cells.operator.site_occupancy@1's declaration in this composition, or None."""
    for op, declaration, _ in composite_spec.entries(spec):
        if op.LAW_ID == LAW_ID:
            return declaration
    return None


def occupant_of(spec):
    """W's declaration in this composition, or None."""
    for op, declaration, _ in composite_spec.entries(spec):
        if op.LAW_ID == OCCUPANT_LAW:
            return declaration
    return None


def replaced_populations(spec, sites):
    """{population id: its cell} of the patch populations (either face) on a slot replacement@1
    replaces."""
    _, events = common.replacement_of(spec)
    slots = {v.slot for v in events}
    m = spec.model
    return {
        p.id: population_cell(m, p)
        for p in sites.populations
        if p.owner_kind == "patch" and population_cell(m, p) in slots
    }


def check_occupant(spec, declaration):
    """W at the definition: replacement@1 and cells.operator.site_occupancy@1 are declared (REQUIRES orders them);
    each template is a replacement template; each newcomer from a template onto a slot with
    populations has that template's occupancy and multipliers for every population of the slot,
    and each population a template names sits on a slot its newcomers fill; a donor copy onto a
    slot with populations is refused (version 1.1); an internalisation multiplier is given exactly
    for the populations that internalise."""
    replacement, events = common.replacement_of(spec)
    sites = _sites_of(spec)
    known = {t.id for t in replacement.templates}
    by_id = {p.id: p for p in sites.populations}
    covered = replaced_populations(spec, sites)
    on_slot = {}
    for pid, cell in covered.items():
        on_slot.setdefault(cell, []).append(pid)
    filled = {}
    for v in events:
        if v.slot not in on_slot:
            continue
        if v.newcomer != "isolated_template":
            raise ConfigError(
                f"{OCCUPANT_LAW}: a donor copy onto {v.slot}, which holds site populations, is "
                "version 1.1 (a donor's site state); version 1 takes newcomers from templates"
            )
        filled.setdefault(v.template, set()).add(v.slot)
    templates = {t.template_id: t for t in declaration.templates}
    for t in declaration.templates:
        if t.template_id not in known:
            raise ConfigError(
                f"{OCCUPANT_LAW} declares {t.template_id}, not a replacement template"
            )
        slots = filled.get(t.template_id, set())
        for pid, _, _, internal in t.populations:
            if pid not in covered or covered[pid] not in slots:
                raise ConfigError(
                    f"{OCCUPANT_LAW}: template {t.template_id} names {pid}, not a population on "
                    "a slot its newcomers fill"
                )
            if (internal is None) != (by_id[pid].internalisation_rate is None):
                raise ConfigError(
                    f"{OCCUPANT_LAW}: template {t.template_id} gives {pid} an internalisation "
                    "multiplier exactly when it internalises"
                )
    for t in declaration.templates:  # The trace rule on the pools as the owner reads them.
        for pid, theta, _, _ in t.populations:
            p = by_id[pid]
            capacity = p.accessible_fraction * p.sites_per_copy * p.copies / SITES_PER_FMOL
            least = ARRIVAL_ULPS * float(np.spacing(capacity))
            for which, amount in (
                ("bound", theta * capacity),
                ("free", capacity - theta * capacity),
            ):
                if amount < least:
                    raise ConfigError(
                        f"{OCCUPANT_LAW}: {t.template_id}'s occupancy {theta!r} of {pid} leaves "
                        f"its {which} sites within {ARRIVAL_ULPS} ulps of its capacity, which its "
                        "anchor plus the event's increment may round to exactly empty: a fresh "
                        f"cell's {which} sites are a trace above that, at least "
                        f"{least / capacity:.1e} of the capacity"
                    )
    for tid, slots in filled.items():
        named = {pid for pid, *_ in templates[tid].populations} if tid in templates else set()
        for cell in sorted(slots):
            missing = sorted(set(on_slot[cell]) - named)
            if missing:
                raise ConfigError(
                    f"{OCCUPANT_LAW}: a newcomer from template {tid} at {cell} declares no "
                    f"arrival occupancy for {missing[0]} (its template's site state)"
                )


def occupant_tables(spec, sites, declaration):
    """{population id: ((time, (theta', binding, internalisation)), ...)}: each covered population's
    newcomers, in time order, with their template's values (host side)."""
    covered = replaced_populations(spec, sites)
    templates = {t.template_id: {r[0]: r[1:] for r in t.populations} for t in declaration.templates}
    lives = common.occupants(spec)
    out = {}
    for pid, cell in covered.items():
        rows = [(o.birth, templates.get(o.template, {}).get(pid)) for o in lives[cell][1:]]
        out[pid] = tuple(r for r in rows if r[1] is not None)  # check_occupant refuses gaps.
    return out


def bind_occupant(spec, sites):
    m, x = spec.model, spec.execution
    cells = [c.id for c in m.cells]
    covered = replaced_populations(spec, sites)
    n = len(sites.populations)
    state = {
        "site_departed_fmol": np.zeros(n),
        "site_arrived_fmol": np.zeros(n),
        "site_replacement_free_energy_pJ": np.zeros(n),
        "site_replacement_energy_magnitude_pJ": np.zeros(n),
        "site_replacement_applied": np.zeros(x.capacity, dtype=np.int64),
    }
    layout = dict(
        site_replaced=np.asarray([p.id in covered for p in sites.populations], dtype=bool),
        site_population_cell=np.asarray(
            # A node's own sites (FR-28) take the padding index 0: the event selects by
            # site_replaced before it reads the index (docs/NODE_SURFACE_SITES_DESIGN.md §3).
            [
                0 if population_cell(m, p) is None else cells.index(population_cell(m, p))
                for p in sites.populations
            ],
            dtype=np.int64,
        ),
    )
    return state, layout


def occupant_event(state, control, p, *, xp=jnp):
    """(state after the site resets of the replacements due at the step start, their validity).
    Each covered population on a due slot leaves with its bound B (departed) and arrives at
    theta' S (arrived), its free sites S - theta' S; the site free energy's jump is booked."""
    applied = state.site_replacement_applied
    count = control.site_replacement_count
    due_slot = count == applied + 1
    valid = xp.all(due_slot | (count == applied))  # A stale count refuses the step.
    due = p.site_replaced & due_slot[p.site_population_cell]
    capacity = p.site_capacity_fmol
    bound = p.site_bound_anchor_fmol + state.site_bound_increment_fmol
    free = p.site_free_anchor_fmol + state.site_free_increment_fmol
    theta = control.site_arrival_occupancy
    arrived = theta * capacity
    rt = 1e-3 * R_GAS * p.temperature
    # The jump of G = mu° B + RT [B ln(B/S) + R ln(R/S)], formed from the endpoints, so an empty
    # or a full newcomer (theta' = 0 or 1) is exact: x ln x = 0 at x = 0 (the stable increment form
    # of site_free_energy reads 0 x log1p(-1) there).
    standard = rt * p.site_standard_RT
    g = [standard * x + rt * _xlogy(x, x / capacity, xp=xp) for x in (bound, arrived)] + [
        rt * _xlogy(x, x / capacity, xp=xp) for x in (free, capacity - arrived)
    ]
    jump = (g[1] - g[0]) + (g[3] - g[2])
    terms = xp.abs(g[0]) + xp.abs(g[1]) + xp.abs(g[2]) + xp.abs(g[3])
    bound_increment = arrived - p.site_bound_anchor_fmol
    free_increment = (capacity - arrived) - p.site_free_anchor_fmol
    # The pools as the owner reads them are never exactly empty (the trace rule; the definition
    # refuses an occupancy within ARRIVAL_ULPS of either end, so this fails closed only).
    reads_positive = (p.site_bound_anchor_fmol + bound_increment > 0) & (
        p.site_free_anchor_fmol + free_increment > 0
    )
    valid &= xp.all(xp.where(due, xp.isfinite(jump) & reads_positive, True))

    def add(name, term):
        return xp.where(due, getattr(state, name) + term, getattr(state, name))

    new = state._replace(
        site_bound_increment_fmol=xp.where(due, bound_increment, state.site_bound_increment_fmol),
        site_free_increment_fmol=xp.where(due, free_increment, state.site_free_increment_fmol),
        site_departed_fmol=add("site_departed_fmol", bound),
        site_arrived_fmol=add("site_arrived_fmol", arrived),
        site_replacement_free_energy_pJ=add("site_replacement_free_energy_pJ", jump),
        site_replacement_energy_magnitude_pJ=add("site_replacement_energy_magnitude_pJ", terms),
        site_replacement_applied=xp.where(due_slot, applied + 1, applied),
    )
    flowing = xp.any(due_slot)  # Nothing due: the start state, bitwise.
    selected = type(state)(*(xp.where(flowing, a, b) for a, b in zip(new, state, strict=True)))
    return selected, valid


def occupant_valid(state, p, *, xp):
    valid = xp.all(state.site_replacement_applied >= 0)
    for name in ("site_departed_fmol", "site_arrived_fmol", "site_replacement_energy_magnitude_pJ"):
        value = getattr(state, name)
        valid &= xp.all(xp.isfinite(value) & (value >= 0))
    valid &= xp.all(xp.isfinite(state.site_replacement_free_energy_pJ))
    for name in OCCUPANT_STATE_AXES:  # Its records stay zero off the covered populations.
        if name != "site_replacement_applied":
            valid &= xp.all(xp.where(p.site_replaced, True, getattr(state, name) == 0))
    return valid


class SiteOccupantReplacement(Operator):
    """cells.operator.site_occupant_replacement@1, W (the section's comment above): an event map at replacement@1's
    event steps that resets the covered site populations through cells.operator.site_occupancy@1's accepted
    writes, with the departed and arrived records and the site free energy's jump, closed in the
    owner's ledgers (external terms) and @3's energy ledger. It reads no view and writes no @3 row.
    The reads of the site quantities stay exact (R3): it has only an event part, and events run
    before every split part's first half, so a routed target reads the newcomer's occupancy from
    the step leaving the event (a writer with a split part would need R3's order check extended to
    writers)."""

    LAW_ID = OCCUPANT_LAW
    EVENT = True
    REQUIRES = (REPLACEMENT_LAW, SITES_LAW)
    STATE_AXES = OCCUPANT_STATE_AXES
    STATE_DTYPES = {"site_replacement_applied": np.int64}
    LAYOUT_FIELDS = OCCUPANT_LAYOUT_FIELDS
    CONTROL_FIELDS = OCCUPANT_CONTROL_FIELDS
    ENTITY_WRITES = {
        "site_bound_increment_fmol": ("site_departed_fmol", "site_arrived_fmol"),
        "site_free_increment_fmol": ("site_departed_fmol", "site_arrived_fmol"),
    }
    IDENTITY_ROLE = "user"  # It names cells.operator.site_occupancy@1's populations; it declares no species.
    VIEW_LAYERS = (
        {
            "id": "site_replacement",
            "label": "Site occupants at replacement",
            "representation": "prescribed",
        },  # noqa: E501
    )
    RECORD_KINDS = {
        "site_departed_fmol": "cumulative",
        "site_arrived_fmol": "cumulative",
        "site_replacement_free_energy_pJ": "cumulative",
        "site_replacement_energy_magnitude_pJ": "cumulative",
        "site_replacement_applied": "cumulative",
    }
    UNITS = {"site_replacement_applied": "1"}

    def view_events(self, spec, declaration, schedule):
        """Its events in the run view: each reset, at its slot's cell."""
        sites = _sites_of(spec)
        covered = set(replaced_populations(spec, sites).values())
        _, events = common.replacement_of(spec)
        out = [
            dict(
                time=float(v.time),
                kind="site_reset",
                layer=self.VIEW_LAYERS[0]["id"],
                at={"cell": v.slot},
                label=f"site populations of {v.slot} reset from template {v.template}",
            )
            for v in events
            if v.slot in covered
        ]
        return tuple(sorted(out, key=lambda e: (e["time"], e["label"])))

    def view_sets(self, spec, declaration):
        return {}

    def parse(self, raw, base, inner_model):
        return parse_occupant(raw, base)

    def to_dict(self, declaration, base):
        return occupant_to_dict(declaration)

    def check_definition(self, spec, declaration, schedule, model):
        check_occupant(spec, declaration)

    def control_values(self, spec, declaration, schedule, records, indices, times):
        """[time, slot] the replacements due by then, and [time, population] the latest newcomer's
        template occupancy (0 before any), from replacement@1's events and its templates."""
        sites = _sites_of(spec)
        _, events = common.replacement_of(spec)
        cells = [c.id for c in spec.model.cells]
        x = spec.execution
        times = np.asarray(times, dtype=np.float64)
        count = np.zeros((times.size, x.capacity))
        for v in events:
            count[:, cells.index(v.slot)] += times >= v.time
        theta = np.zeros((times.size, len(sites.populations)))
        tables = occupant_tables(spec, sites, declaration)
        for k, pop in enumerate(sites.populations):
            for birth, (value, _, _) in tables.get(pop.id, ()):
                theta[times >= birth, k] = value
        return (count, theta)

    def batch_signature(self, declaration):
        return (OCCUPANT_LAW, tuple(t.template_id for t in declaration.templates))

    def summary(self, spec, declaration, schedule, history):
        sites = _sites_of(spec)
        last = {k: np.asarray(getattr(history, k))[-1] for k in OCCUPANT_STATE_AXES}
        return {
            "site_occupant_law": OCCUPANT_LAW,
            "site_occupant_templates": occupant_to_dict(declaration)["templates"],
            "site_occupant_records": {
                p.id: dict(
                    departed_fmol=float(last["site_departed_fmol"][k]),
                    arrived_fmol=float(last["site_arrived_fmol"][k]),
                    free_energy_pJ=float(last["site_replacement_free_energy_pJ"][k]),
                )
                for k, p in enumerate(sites.populations)
                if p.id in replaced_populations(spec, sites)
            },
        }

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        return bind_occupant(spec, _sites_of(spec))

    def event(self, state, control, p, *, xp):
        return occupant_event(state, control, p, xp=xp)

    def control_valid(self, control, p, *, xp):
        theta = control.site_arrival_occupancy
        valid = xp.all(xp.isfinite(theta) & (theta >= 0) & (theta <= 1))
        return valid & xp.all(control.site_replacement_count >= 0)

    def rate_checks(self, state, control, p, valid, *, xp):
        return valid & occupant_valid(state, p, xp=xp)

    def domain_valid(self, state, p, valid, *, xp):
        own = occupant_valid(state, p, xp=xp)
        return own if valid is None else valid & own

    def ledger_terms(self, result, row, p, *, xp):
        """@3's energy ledger: the site free energy's jumps at the resets, which the owner's
        endpoint term (site_energy) includes, are booked here, against it."""
        jumps = entity_sum(row.site_replacement_free_energy_pJ, axis=None, xp=xp)
        result["energy"] = result["energy"] - jumps
        return result, {}

    def magnitude_terms(self, magnitudes, row, p, *, xp):
        energy = entity_sum(row.site_replacement_energy_magnitude_pJ, axis=None, xp=xp)
        magnitudes[6] = energy if magnitudes[6] is None else magnitudes[6] + energy
        return magnitudes

    def external_ledger_terms(self, ledgers, row, p, *, xp):
        """The owner's bound ledger closes with the resets' arrived - departed (its moiety holds by
        construction: R' + B' = S)."""
        if "site_bound_entity" in ledgers:
            jump = row.site_arrived_fmol - row.site_departed_fmol
            ledgers = ledgers | {"site_bound_entity": ledgers["site_bound_entity"] - jump}
        return ledgers

    def external_magnitude_terms(self, magnitudes, row, p, *, xp):
        moved = row.site_arrived_fmol + row.site_departed_fmol
        return {k: v + moved for k, v in magnitudes.items()}
