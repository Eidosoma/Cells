"""site_occupancy@1: binding sites as owned state (FR-3, D169; docs/SITE_OCCUPANCY_DESIGN.md).

A site population is a population of identical, independent, single-occupancy sites on one owner,
facing one free pool and binding one neutral ligand (§1.1). Its owner is a membrane patch, facing
its outside node (`outside`) or its cell (`inside`), or a contact, facing one of its two cells
(`first`: the junction's sender, `second`: its receiver). Its stoichiometric count is copies N x
sites per copy nu, and its accessible capacity S = alpha nu N / N_f fmol, with the static accessible
fraction alpha (§2.3) and N_f = 602,214,076 sites per fmol (exact). Its state is the free accessible
sites R and the bound amount B (fmol), anchored increments from R0 = S - B0 and B0 = theta0 S, so
R + B = S, the moiety identity (§1.1). The free ligand stays in @3's rows at the facing node (one
material ledger, §1.4); a population takes no species row.

The laws (§2):
- langmuir_site_binding@1, passive: J = m_b [k_on c R - k_off B] (fmol/s; c in mM), with detailed
  balance dG°_b = RT ln(K_d / 1 mM), K_d = k_off / k_on;
- site_conserving_internalisation@1, driven, on an outward-facing patch only: I = m_i k_int B moves
  the cargo into the patch's cell and returns the site free (the site count is constant, §2.4).
The multipliers m_b and m_i are scheduled per population and route (`site_controls`); a binding
multiplier scales k_on and k_off together, so the equilibrium is unchanged. Parameters, alpha,
copies and sites per copy are not scheduled.

Ownership (§1.3, option O; ARCHITECTURE.md's modular core, D174): this operator owns every site
population of a composition and provides no view, mask or capacitance, so it is no field input and
an occupancy-only composition does not refresh the field (ownership is separate from solver
invalidation). It accepts later writers on its two pools (ACCEPTS_WRITES). Species identity follows
the coupling operator's pattern until D172 consolidates it: ligands are parsed by
species_common.parse_species, with a declared trace_mM (§4.3), and their identities are checked
against D150's and D152's declarations by this operator, in either order, with no shared change.

Refused at the definition (§6.2), each with its reason: a charged, permeant or undeclared ligand; an
identity that differs from D150's or D152's; more than 16 species; a declared concentration of a
ligand below its declared trace, or a trace above 1e-6 K_d of a population binding it (§4.3); an
unknown patch or contact; an outward population on a patch facing a held bath; copies <= 0, sites
per copy not a positive int, alpha outside (0, 1], an unlisted ligand, initial occupancy outside
[0, 1]; k_on <= 0, k_off <= 0, k_int < 0; internalisation on an inward patch, a contact or a
compartment-facing patch; a destination other than "cell"; a population on a replaced slot's patch,
or on a contact incident to one; RK4; schedules that are missing, do not start at 0, change off the
dt grid or outside the horizon, or carry a negative multiplier; unknown keys and duplicate IDs. The
composite's structure check refuses the providers and closers of what it reads as declared
(CONFLICTS_VIEW). The stationary analysis refuses the composite by its own ID check.
"""

import math
from dataclasses import dataclass

import numpy as np

from cells.core import pump_composite_spec as composite_spec
from cells.core.multispecies_spec import identifier
from cells.core.specs import ConfigError, _fields
from cells.models.operators import species_common as common
from cells.models.operators.contract import Operator
from cells.models.operators.membrane_state import parse_catalogue

LAW_ID = "site_occupancy@1"
BINDING_LAW = "langmuir_site_binding@1"
INTERNALISATION_LAW = "site_conserving_internalisation@1"
STEP_ID = "ssprk33_unidirectional_stage_condition_site_bookings@1"
CONTROLS_KEY = "site_controls"
ROUTES = ("binding", "internalisation")
SITES_PER_FMOL = 602_214_076.0  # N_A x 1e-15 mol, exact (SI 2019).
TRACE_LIMIT = 1e-6  # A ligand's trace at most 1e-6 K_d of every population binding it (§4.3).
TRACE_RTOL = 1e-12  # A node declared at its trace, to representation (amount / volume).
DESTINATIONS = ("cell",)  # Version 1: the patch's own cell (§2.4).
FACES, SIDES = ("outside", "inside"), ("first", "second")
REACTIONS_LAW = "local_species_reactions@1"
COMPARTMENTS_LAW = "cell_owned_compartments@1"
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
    raise ConfigError(f"{LAW_ID}: population {pid}'s owner is {{patch, face}} or {{contact, side}}")


def facing_node(m, population):
    """(kind, node id) of the free pool a population faces (§1.1)."""
    if population.owner_kind == "patch":
        patch = next(p for p in m.membranes if p.id == population.owner_id)
        if population.facing == "outside":
            return OUTSIDE, patch.outside
        return CELL, patch.inside
    junction = next(j for j in m.junctions if j.id == population.owner_id)
    return CELL, junction.sender if population.facing == "first" else junction.receiver


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
        if time != round(time / dt) * dt:
            raise ConfigError(f"{LAW_ID}: a schedule change must be an exact multiple of dt")
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


def route_tables(declaration, schedule):
    """[route] multiplier tables: each population's binding, then its internalisation (or a
    constant 0 for a population without the route)."""
    keyed = {(c.population, c.route): c.changes for c in schedule}
    binding = [keyed[(p.id, "binding")] for p in declaration.populations]
    internal = [
        keyed.get((p.id, "internalisation"), ((0.0, 0.0),)) for p in declaration.populations
    ]
    return binding, internal


# ------------------------------------------------------------------ composition checks


def check_identities(spec, declaration):
    """A ligand that D150's or D152's operators declare with another identity is refused, whichever
    comes first (§1.6; the coupling operator's pattern)."""
    mine = {ligand.identity.id: ligand.identity for ligand in declaration.species}
    for op, other, _ in composite_spec.entries(spec):
        if op.LAW_ID in common.SPECIES_LAWS:
            theirs = other.species
        elif op.LAW_ID == REACTIONS_LAW:
            theirs = tuple(s.identity for s in other.species)
        else:
            continue
        for item in theirs:
            own = mine.get(item.id)
            if own is not None and (own.catalogue, own.evidence) != (item.catalogue, item.evidence):
                raise ConfigError(
                    f"{LAW_ID} declares species {item.id!r} with another identity than "
                    f"{op.LAW_ID} (catalogue reference and kind of evidence must agree)"
                )


def check_slots(spec, declaration):
    """No population on a replaced slot's patch, or on a contact incident to one (§6.2)."""
    _, events = common.replacement_of(spec)
    slots = {v.slot for v in events}
    m = spec.model
    for p in declaration.populations:
        if p.owner_kind == "patch":
            cells = {next(q for q in m.membranes if q.id == p.owner_id).inside}
        else:
            junction = next(j for j in m.junctions if j.id == p.owner_id)
            cells = {junction.sender, junction.receiver}
        if cells & slots:
            raise ConfigError(
                f"{LAW_ID}: population {p.id} sits on {p.owner_kind} {p.owner_id} of a slot "
                f"{common.REPLACEMENT_LAW} replaces; version 1 has no occupant rule for sites "
                "(their reset at replacement is a door, §5.2)"
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
        site_component=components(spec, declaration),
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


# The half-step and its bookings (stage B) follow the operator's declarations below.


class SiteOccupancy(Operator):
    LAW_ID = LAW_ID
    STEP_ID = STEP_ID
    SPLIT = True
    RK4 = "split"  # Declared; RK4 is refused at the definition (§4.6).
    STATE_AXES = STATE_AXES
    HEAT_FIELDS = ("site_dissipated_energy_pJ", "site_outside_dissipated_energy_pJ")
    WORK_FIELDS = ("site_work_pJ",)
    LAYOUT_FIELDS = LAYOUT_FIELDS
    CONTROL_FIELDS = CONTROL_FIELDS
    EXPERIMENT_KEYS = (CONTROLS_KEY,)
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
        binding, internal = route_tables(declaration, schedule)
        n = len(declaration.populations)
        b = common.control_arrays(binding, times, 1)[..., 0] if n else np.zeros((len(times), 0))
        i = common.control_arrays(internal, times, 1)[..., 0] if n else np.zeros((len(times), 0))
        return (b, i)

    def check_definition(self, spec, declaration, schedule, model):
        check_definition(spec, declaration)

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
        return 0

    def summary(self, spec, declaration, schedule, history):
        return {"site_occupancy_law": LAW_ID, **identity_block(declaration)}

    # ------------------------------------------------------------ binding

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        return bind(spec, declaration)

    def statically_idle(self, p):
        return p.site_capacity_fmol.shape[0] == 0
