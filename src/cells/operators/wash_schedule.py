"""scheduled_compartment_wash@1: timed partial washes of finite compartments (FR-27; D245, D246).

docs/COMPARTMENT_WASH_DESIGN.md. One mechanism, a liquid exchange of a compartment, is shared with
the assembly family's cells.pool_replacement@1 (FR-20), its whole-exchange execution in exact
counts; this operator is its deterministic execution at any fraction (D175, D210; D246: D175's
representation key stays reserved, and both declare it when it exists).

Declaration: `nodes`, the finite outside nodes it washes, and `ions`, which version 1 requires to
be "same_as_compartment": the buffer carries the node's own ion composition (D246). The experiment
key `compartment_wash_events` lists {time, node, fraction, buffer_mM}: the time on the dt grid with
0 < t < end and strictly increasing per node; the fraction in (0, 1]; buffer_mM a concentration for
every neutral species of the world and no other, so no wash is silently partial.

The event map, at the start of the step leaving t, at each node with a wash due: every species s of
the node's liquid becomes (1 - f) n_s + f V c_buf,s, at constant volume. An ion's buffer is the
node's own concentration, so its amount is kept as it is, and its sample and supply are both f n_s:
the books show it unchanged. Its supplied record is its collected record, one expression, so the two
are equal bit for bit at any fraction (D266). The sample f n_s and the supply f V c_buf,s are
recorded cumulatively for every species, ions included. Bound material, which is not liquid, stays
where it is.

The latest event's sample and supply at each node are level records too, `wash_last_sample_fmol`
and `wash_last_supply_fmol` [species, outside], as the latest heat is (an ion's supply record is
its sample record, one expression). They exist in every washed world, labelled or not.

Labels (FR-44, D327). Beside the label owner the event takes labels= (the labelled rows) and also
returns a LiquidExchange (operators/contract.py). Its removed and supplied amounts are those two
level records at the labelled rows where a wash is due this step, and zero elsewhere, so each is
the event's own sample and supply, never a cumulative record's gain (a gain is inexact, and at
f = 1 it leaves a kept part that is nonzero or negative). The state and validity are the
unlabelled call's, bit for bit, since the report only reads the records. The owner, not the wash,
decides the labels: the sample leaves with the node's shares, and the buffer joins the base,
whatever window is open.

For the exchanged (neutral) species it records the free energy of the sample, F_sample = f F(n, V),
taken to its sink, and of the buffer, F_buffer = F(f V c_buf, f V), drawn from its source, with
F(n, V) = 1e-3 RT n (ln(n / V) - 1) (@3's chemical term, concentrations in mM), and the heat of
mixing the kept liquid with the buffer, computed from the ideal-mixing terms rather than taken as a
ledger's remainder:

    H_mix = 1e-3 RT V sum_s c'_s [(1 - f) phi(c_s / c'_s) + f phi(c_buf,s / c'_s)] >= 0,

with c' = (1 - f) c + f c_buf and phi(r) = r ln r - r + 1 (ideal_mixing.phi: the cleft fix's form,
which takes r itself where it would round to 0 inside a log). At f = 1 nothing is kept, H_mix = 0,
and the booking is FR-20's: the sink takes F(old pool) and the source gives F(fresh pool). An ion's
sample and supply carry equal free energy, the same liquid at the node's electrochemical potential,
so they are not booked.

Its checks. The event refuses the step unless every washed amount stays positive and finite and
every event's H_mix is finite and >= 0. The latest event's H_mix per node is a record of its own,
which the domain check reads on every accepted row: so the host checks H_mix >= 0 at every event,
not only the cumulative record. @3's outside and total material ledgers gain collected - supplied
at each node (D150's sign). The energy ledger gains H_mix - (F_buffer - F_sample) against @3's own
chemical jump at the node, so its closure checks the decomposition. These records carry no heat or
work suffix and stay out of the IMEX flow bound (BATH_SCHEDULE_DESIGN.md §2.2). Its own ledger
holds each ion's sample against its supply at each node: zero by construction.

The trace. No buffer concentration is an exact zero, for any species: @3 keeps every species
positive at every active node, and at f = 1 a zero would empty it. A tracer-free buffer is declared
at the species' trace. A site ligand's buffer lies at or above its declared trace, the site
operator's own rule (site_occupancy.check_schedule_traces). A species with no declared trace takes
any positive concentration the definition chooses. The node's amount is @3's anchor plus an
increment, so at f = 1 a buffer amount below about one ulp of the node's anchor rounds the amount to
zero or below, and the event refuses the step. Above that, the new amount carries an absolute error
of about eps times the anchor.

Refused at the definition (version 1):
- a held bath, whose composition is the bath schedule's;
- a node a face touches, until measured (D246 item 5). A wash is a step in the node's
  concentration, and @3's face booking of such a step is FR-10's onset limit, measured for held
  baths only;
- a neutral species that crosses the node's surface by any declared path, its booking of the
  step unmeasured likewise, and its exchange unseen by the wash's books (fail closed; D263 finding
  2, a second review: a path through a registered route was admitted while the patch's own
  permeability was refused). The paths are read from the declarations (surface_crossings):
  - the inner model's movers, through the core's join (species_registry.inner_movers): each
    patch's permeability, channels, pumps, faces, junctions and every declared kind's moved
    rows;
  - each operator's routes: species exchange's routes through a patch facing the node, a
    site population's internalisation from it, and the gene unit's exports into the node and
    its outside degradations there (templated_polymerisation@1's amendment T; D327, the
    fail-open fix: each refused by name, since both write the node's rows outside the wash's
    books);
  - every operator's in-step process that moves a neutral species at an outside node;
  - every operator law not shown local (SHOWN_LOCAL), with its reason (REFUSED), and a law in
    no list, until it is classified;
  The refusal names every path it finds, not only the first.
- ions declared other than same_as_compartment;
- a buffer that misses a neutral species, names another, or holds a concentration <= 0 or below a
  site ligand's trace;
- a fraction outside (0, 1], and times off the grid, outside (0, end) or not increasing per node.
It reads its nodes' volumes, anchors and outside mask as declared: fixed reads at its event, scoped
to its nodes (door S). So water, the lumens and insertion, which change them unscoped, are refused
by the composite's structure check, and the bath schedule's dose at a held bath is admitted. Beside
cell_owned_compartments@1 it is refused by that declaration's admitted list, which fails closed.
"""

import math
from bisect import bisect_right
from dataclasses import dataclass

import jax.numpy as jnp
import numpy as np

from cells.definitions.spec_values import identifier
from cells.definitions.specs import ConfigError, _fields
from cells.laws.electrochemistry import R
from cells.models import surface_pump as first
from cells.numerics import ideal_mixing
from cells.numerics.clock_instants import ON_THE_GRID, on_grid  # D283's one predicate.
from cells.numerics.species_sums import entity_sum, species_sum
from cells.operators.contract import EXCHANGED, LiquidExchange, Operator, Read

LAW_ID = "scheduled_compartment_wash@1"
EVENTS_KEY = "compartment_wash_events"
EXCHANGE, SITES = "scheduled_species_exchange@1", "site_occupancy@1"
POLYMERISATION = "templated_polymerisation@1"
# The operator laws whose routes surface_crossings reads, route by route, rather than classing
# the law whole (SHOWN_LOCAL, REFUSED).
READ = (EXCHANGE, SITES, POLYMERISATION)
# The inner movers on a membrane patch, by the core's join (species_registry.NODE_KINDS): their
# entities are patch IDs. Faces' are face IDs and junctions' junction IDs (between cells); a
# kind's movers name the nodes they move between.
PATCH_MOVERS = ("membrane", "channel", "pump")
# Operator laws shown to move no species across a node's surface (D263 finding 2), each with why;
# READ's routes are read (surface_crossings), and every other law is refused.
SHOWN_LOCAL = {
    "scheduled_species_turnover@1": "makes and clears species at its own cells and nodes",
    "local_species_reactions@1": "converts species at its own sites",
    "scheduled_bath_composition@1": "sets held baths' compositions",
    "membrane_entity_state@1": "provides channel abundances, membrane areas and capacitances",
    "species_regulated_availability@1": "scales other laws' availabilities; its state is its own",
    "species_regulated_availability@2": "scales other laws' availabilities and rates",
    "cell_owned_compartments@1": "declares which cell owns each compartment",
    "scheduled_cell_replacement@1": "swaps a replaced cell's own pools",
    "scheduled_cell_replacement@2": "swaps a replaced cell's own pools",
    "site_occupant_replacement@1": "resets site pools at replacement events",
    "electrode_current_injection@1": "moves charged carriers between an electrode and a cell",
    "isopotential_partition@1": "splits a dividing cell's contents between its daughters",
    "cytoplasmic_bridge_closure@1": "sets a bridge junction's availability, between two cells",
    "population_unit_turnover@1": "consumes precursors into units in cells",
    "ideal_osmosis_linear_compliance_water@1": "changes volumes, never amounts",
    "k_anion_symport_mass_action@1": "moves its charged potassium and anion in-step (read below)",
    # templated_polymerisation@1 left this list for READ (D327, the fail-open fix): it was entered
    # here as writing only amount_increment (gene regulation's option A, G4), and amendment T
    # then gave it exports into finite nodes and outside degradations there.
    # FR-44 (D327): the label owner moves no amount and follows each wash by its report.
    "neutral_arrival_labels@1": "moves no amount; it follows each wash by the wash's report",
    LAW_ID: "is this law",
}
REFUSED = {
    "scheduled_membrane_trafficking@1": "moves membrane, and the charges on it, between nodes",
    "scheduled_membrane_insertion@1": "opens onset nodes with their declared contents",
    "scheduled_membrane_insertion@2": "opens and retires nodes and patches",
    "restricted_cleft_lumen@1": "fills a lumen node with bath fluid as it grows",
    "restricted_cleft_lumen@2": "fills a lumen node with bath fluid as it grows",
    "integer_unit_population@1": "moves species across its sites' patches, between cells and "
    "outside nodes, by transfers a wash does not read",
}
IONS_SAME = "same_as_compartment"
FLOOR_FMOL = 1e-12  # The own ledger's floor (each ion's sample against its supply: exactly 0).

STATE_AXES = {
    "wash_collected_fmol": ["species", "extracellular_slot"],  # The samples, cumulative.
    "wash_supplied_fmol": ["species", "extracellular_slot"],  # The buffer supplied, cumulative.
    "wash_sample_free_energy_pJ": ["extracellular_slot"],  # F of the exchanged species' samples.
    "wash_buffer_free_energy_pJ": ["extracellular_slot"],  # F of the exchanged species' buffer.
    "wash_mixing_heat_pJ": ["extracellular_slot"],  # H_mix, cumulative (a record).
    "wash_last_mixing_heat_pJ": ["extracellular_slot"],  # The latest event's H_mix (a record).
    # FR-44: the latest event's sample and supply (level records; an ion's supply is its sample).
    "wash_last_sample_fmol": ["species", "extracellular_slot"],
    "wash_last_supply_fmol": ["species", "extracellular_slot"],
    "wash_energy_magnitude_pJ": ["extracellular_slot"],  # Magnitudes of the energy bookings.
    "wash_applied": ["extracellular_slot"],  # int64: the events applied at each node.
}
INTEGER_FIELDS = ("wash_applied",)
LAYOUT_FIELDS = (
    "wash_node",  # [outside] bool: the washed finite nodes.
    "wash_ion",  # [species] bool: a charged species, whose buffer is the node's own composition.
)
CONTROL_FIELDS = (
    "wash_count",  # [outside] the washes due by now at each node.
    "wash_fraction",  # [outside] the latest wash's fraction (1 before any, unused).
    "wash_buffer_mM",  # [species, outside] the latest wash's buffer (1 before any and for ions).
)
LEDGERS = ("wash_ions",)
LEDGER_DIAGNOSTICS = ("wash_ions_error_fmol",)
LEDGER_MESSAGE = "Compartment wash accounting failed: "


@dataclass(frozen=True)
class WashDeclaration:
    law: str
    nodes: tuple  # The washed finite nodes, in declared order.
    ions: str  # IONS_SAME in version 1.


@dataclass(frozen=True)
class WashEvent:
    time: float
    node: str
    fraction: float
    buffer_mM: tuple  # ((neutral species, mM), ...) in the world's species order.


@dataclass(frozen=True)
class WashProgram:
    events: tuple  # WashEvent, as declared.


# ------------------------------------------------------------------ definition


def _finite(value, what):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ConfigError(f"{LAW_ID}: {what} is a finite number")
    return float(value)


def parse_declaration(raw, base):
    _fields(raw, {"law", "nodes", "ions"}, "compartment wash")
    if raw["law"] != LAW_ID:
        raise ConfigError("A compartment wash requires law " + LAW_ID)
    outside = {c.id: c for c in base.model.extracellular}
    if type(raw["nodes"]) is not list or not raw["nodes"]:
        raise ConfigError(f"{LAW_ID} declares the finite nodes it washes in a non-empty list")
    nodes = []
    for name in raw["nodes"]:
        node = identifier(name)
        if node not in outside:
            raise ConfigError(f"{LAW_ID} washes an undeclared outside node {node!r}")
        if outside[node].reservoir:
            raise ConfigError(
                f"{LAW_ID} washes finite compartments only; {node!r} is a held bath, whose "
                "composition is the bath schedule's (scheduled_bath_composition@1)"
            )
        nodes.append(node)
    if len(set(nodes)) != len(nodes):
        raise ConfigError(f"{LAW_ID} lists a node twice")
    if raw["ions"] != IONS_SAME:
        raise ConfigError(
            f"{LAW_ID}: version 1 declares its ions {IONS_SAME!r}, the buffer carrying the node's "
            "own ion composition (D246); ions in neutral formula units are a later option"
        )
    return WashDeclaration(LAW_ID, tuple(nodes), IONS_SAME)


def declaration_to_dict(declaration):
    if type(declaration) is not WashDeclaration:
        raise ConfigError("Require explicit immutable compartment wash declaration types")
    return dict(law=declaration.law, nodes=list(declaration.nodes), ions=declaration.ions)


def neutral_species(model):
    return [s for s, z in zip(model.species_ids, model.valence, strict=True) if z == 0]


def parse_events(raw, base, declaration):
    entries = raw[EVENTS_KEY]
    if type(entries) is not list:
        raise ConfigError(f"{EVENTS_KEY} requires an explicit list")
    dt, end = base.execution.dt, base.experiment.end_time
    neutral = neutral_species(base.model)
    events, last = [], {}
    for entry in entries:
        _fields(entry, {"time", "node", "fraction", "buffer_mM"}, f"{EVENTS_KEY} entry")
        time = _finite(entry["time"], "a wash time")
        if not 0.0 < time < end:
            raise ConfigError(f"{LAW_ID}: a wash lies after time 0 and before the end time")
        if on_grid(time, dt) is None:
            raise ConfigError(f"{LAW_ID}: a wash time must be {ON_THE_GRID}")
        node = identifier(entry["node"])
        if node not in declaration.nodes:
            raise ConfigError(f"{LAW_ID}: a wash names a node it does not declare, {node!r}")
        if node in last and time <= last[node]:
            raise ConfigError(f"{LAW_ID}: the washes of node {node} increase strictly in time")
        last[node] = time
        fraction = _finite(entry["fraction"], "a wash fraction")
        if not 0.0 < fraction <= 1.0:
            raise ConfigError(f"{LAW_ID}: a wash fraction lies in (0, 1]")
        buffer = entry["buffer_mM"]
        if not isinstance(buffer, dict):
            raise ConfigError(f"{LAW_ID}: a wash's buffer_mM is an object")
        missing, other = sorted(set(neutral) - set(buffer)), sorted(set(buffer) - set(neutral))
        if missing or other:
            raise ConfigError(
                f"{LAW_ID}: a wash's buffer names every neutral species of the world and no other "
                f"(missing {missing}, other {other}): no wash is silently partial, and the ions "
                f"are {IONS_SAME!r}"
            )
        values = []
        for species in neutral:
            c = _finite(buffer[species], f"the buffer's {species}")
            if not c > 0.0:
                raise ConfigError(
                    f"{LAW_ID}: the buffer's {species} is {c:g} mM; no species is set to an exact "
                    "zero (@3 keeps every species positive), so a tracer-free buffer is declared "
                    "at the species' trace"
                )
            values.append((species, c))
        events.append(WashEvent(time, node, fraction, tuple(values)))
    return WashProgram(tuple(events))


def events_to_dict(schedule):
    if type(schedule) is not WashProgram or any(type(e) is not WashEvent for e in schedule.events):
        raise ConfigError("Require explicit immutable compartment wash schedule types")
    return {
        EVENTS_KEY: [
            dict(time=e.time, node=e.node, fraction=e.fraction, buffer_mM=dict(e.buffer_mM))
            for e in schedule.events
        ]
    }


def due_at(schedule, time):
    """For each node with a wash at or before `time`: (node, the washes so far, the latest one's
    fraction and buffer), sorted by node (hashable)."""
    out = []
    for node in sorted({e.node for e in schedule.events}):
        events = [e for e in schedule.events if e.node == node]
        k = bisect_right([e.time for e in events], time)
        if k:
            out.append((node, k, events[k - 1].fraction, events[k - 1].buffer_mM))
    return tuple(out)


def surface_crossings(spec, declaration):
    """[(species, node, path)] each declared path that may move a neutral species across a washed
    node's surface (the module docstring's refusals; fail closed): an inner mover whose entity is
    a patch facing the node, a face touching it, or the node itself, or which names no node or
    patch it is known to sit on; an exchange route through a patch facing it; a site population
    internalising from it; the gene unit's export into it and its outside degradation there
    (D327), whatever the row's charge; an operator's in-step process moving the species at an
    outside node; and an operator law neither read nor shown local."""
    from cells.definitions import pump_composite_spec as composite_spec
    from cells.registry import species_registry

    m = spec.model
    washed = set(declaration.nodes)
    neutral = {s for s, z in zip(m.species_ids, m.valence, strict=True) if z == 0}
    patches = {p.id: p for p in m.membranes}
    faces = {f.id: f for f in m.faces}
    nodes = {c.id for c in m.cells} | {c.id for c in m.extracellular}
    found = []
    _, movers = species_registry.inner_movers(spec)
    for species, entries in movers.items():
        if species not in neutral:
            continue
        for kind, law, entities in entries:
            for entity in entities:
                if kind in PATCH_MOVERS and entity in patches:
                    if patches[entity].outside in washed:
                        found.append((species, patches[entity].outside, f"patch {entity}"))
                elif kind == "face" and entity in faces:
                    touched = {faces[entity].sender, faces[entity].receiver} & washed
                    found += [(species, n, f"face {entity}") for n in sorted(touched)]
                elif kind == "junction":
                    continue  # Between two cells: no outside node's surface.
                elif entity in nodes:
                    if entity in washed:
                        found.append((species, entity, f"{kind} ({law})"))
                else:
                    found.append((species, "?", f"{kind} ({law}) at {entity}, unclassified"))
    for op, other, _ in composite_spec.entries(spec):
        law = op.LAW_ID
        if law == EXCHANGE:
            for r in other.routes:
                if r.outside in washed and r.species in neutral:
                    found.append((r.species, r.outside, f"{EXCHANGE}'s route {r.id}"))
        elif law == SITES:
            for population in other.populations:
                patch = patches.get(population.owner_id)
                facing = patch.outside if patch is not None else None
                if (
                    population.internalisation_rate is not None
                    and population.owner_kind == "patch"
                    and population.facing == "outside"
                    and facing in washed
                ):
                    found.append(
                        (population.ligand, facing, f"{SITES}'s internalisation {population.id}")
                    )
        elif law == POLYMERISATION:
            # Amendment T (D327, the fail-open fix): an export carries its row from its patch's
            # cell into the patch's finite outside node, and an outside degradation writes a row
            # an export carries there. Its other routes stay at its cells.
            for export in other.exports:
                if export.node in washed:
                    found.append((export.row, export.node, f"{law}'s export {export.id}"))
            for loss in other.outside_degradations:
                if loss.node in washed:
                    path = f"{law}'s outside degradation {loss.id}"
                    found.append((loss.polymer, loss.node, path))
        elif law not in SHOWN_LOCAL:
            why = REFUSED.get(law, "is not classified (neither read nor shown local)")
            found.append(("any species", "any node", f"{law}, which {why}"))
        if op.PROCESS:
            for species, kind in op.moves_in_step(spec, other):
                if species in neutral and kind == "outside":
                    found.append((species, "an outside node", f"{law}'s in-step process"))
    return found


def check_definition(spec, declaration):
    """Version 1's refusals of what the step would book unmeasured: a face at a washed node, and
    a neutral species crossing a washed node's surface by any declared path
    (surface_crossings)."""
    m = spec.model
    for face in m.faces:
        touched = {face.sender, face.receiver} & set(declaration.nodes)
        if touched:
            raise ConfigError(
                f"{LAW_ID}: face {face.id} touches node {sorted(touched)[0]}; a wash is a step in "
                "the node's concentration, and @3's face booking of such a step is FR-10's onset "
                "limit, measured for held baths only: refused until measured (D246)"
            )
    found = surface_crossings(spec, declaration)
    if found:
        species, node, path = found[0]
        # Every path found is named (D327), so a path behind another is refused by name too.
        also = "".join(f"; also {s} by {p} at node {n}" for s, n, p in found[1:])
        if path.startswith("patch "):
            raise ConfigError(
                f"{LAW_ID}: {species} crosses {path}, which faces node {node}; its booking of a "
                "step in the node's concentration is unmeasured, as a face's: refused in version 1"
                + also
            )
        raise ConfigError(
            f"{LAW_ID}: {species} may cross node {node}'s surface by {path}; a washed node's "
            "species cross its surface by no declared path in version 1, since the step's "
            "booking is unmeasured and the wash's books do not see the exchange (D263; fail "
            "closed: a path is refused until it is shown not to move the species)" + also
        )


def bind(spec, declaration):
    m, x = spec.model, spec.execution
    o = x.extracellular_capacity
    s = len(m.species_ids)
    outside = [c.id for c in m.extracellular]
    node = np.zeros(o, dtype=bool)
    for name in declaration.nodes:
        node[outside.index(name)] = True
    state = {
        "wash_collected_fmol": np.zeros((s, o)),
        "wash_supplied_fmol": np.zeros((s, o)),
        "wash_sample_free_energy_pJ": np.zeros(o),
        "wash_buffer_free_energy_pJ": np.zeros(o),
        "wash_mixing_heat_pJ": np.zeros(o),
        "wash_last_mixing_heat_pJ": np.zeros(o),
        "wash_last_sample_fmol": np.zeros((s, o)),
        "wash_last_supply_fmol": np.zeros((s, o)),
        "wash_energy_magnitude_pJ": np.zeros(o),
        "wash_applied": np.zeros(o, dtype=np.int64),
    }
    ion = np.asarray([z != 0 for z in m.valence], dtype=bool)
    return state, dict(wash_node=node, wash_ion=ion)


# ------------------------------------------------------------------ the law


def wash_terms(n, volume, fraction, buffer_mM, ion, temperature, *, xp):
    """One wash of liquid holding n ([species, node], fmol) in `volume` ([1, node], pL), at
    `fraction` ([1, node]), with buffer concentrations `buffer_mM` ([species, node]); an ion's
    (`ion`, [species, 1]) buffer is the node's own concentration. Returns (sample, supply, change,
    F_sample, F_buffer, H_mix), each [species, node]; the free energies and H_mix are zero for
    ions."""
    f = fraction
    c = n / volume
    neutral = ~ion
    c_n = xp.where(neutral, c, 1.0)
    cb = xp.where(neutral, buffer_mM, 1.0)
    sample = f * n
    supply = xp.where(neutral, f * volume * cb, sample)
    change = xp.where(neutral, supply - sample, 0.0)
    rt = 1e-3 * R * temperature
    f_sample = xp.where(neutral, rt * sample * (xp.log(c_n) - 1.0), 0.0)
    f_buffer = xp.where(neutral, rt * f * volume * cb * (xp.log(cb) - 1.0), 0.0)
    mixed = (1.0 - f) * c_n + f * cb
    kept = ideal_mixing.phi(f * (c_n - cb) / mixed, c_n / mixed, xp=xp)
    added = ideal_mixing.phi((1.0 - f) * (cb - c_n) / mixed, cb / mixed, xp=xp)
    heat = xp.where(neutral, rt * volume * mixed * ((1.0 - f) * kept + f * added), 0.0)
    return sample, supply, change, f_sample, f_buffer, heat


def apply_events(state, control, p, *, xp=jnp, labels=None):
    """(state after the washes due at the step start, their validity). With labels (FR-44; the
    labelled rows [m], static), also its LiquidExchange report [m, outside]: the new level records
    at those rows where a wash is due, zero elsewhere (module docstring)."""
    node = p.wash_node
    applied = state.wash_applied
    count = control.wash_count
    due = node & (count == applied + 1)
    on = due[None, :]
    n = p.extracellular_amount_reference + state.extracellular_amount_increment
    volume = xp.where(due, p.extracellular_volume, 1.0)[None, :]
    sample, supply, change, f_sample, f_buffer, heat = wash_terms(
        xp.where(on, n, 1.0),
        volume,
        xp.where(due, control.wash_fraction, 1.0)[None, :],
        xp.where(on, control.wash_buffer_mM, 1.0),
        p.wash_ion[:, None],
        p.temperature,
        xp=xp,
    )
    after = n + change
    heat_node = species_sum(xp.where(on, heat, 0.0), xp=xp)
    sample_energy = species_sum(xp.where(on, f_sample, 0.0), xp=xp)
    buffer_energy = species_sum(xp.where(on, f_buffer, 0.0), xp=xp)
    # The magnitude: the bookings' absolute terms, and the stored amounts at the new level. @3
    # holds the new amount as anchor plus increment, rounded at about eps times the stored amounts,
    # and that rounding is booked at the new level's potential, RT |ln c_after| per fmol: a whole
    # wash of a large node to a deep trace needs it at the event's own step.
    exchanged = on & ~p.wash_ion[:, None]
    stored = xp.abs(p.extracellular_amount_reference) + xp.abs(n) + xp.abs(supply)
    level = xp.abs(xp.log(xp.where(exchanged & (after > 0), after, 1.0) / volume)) + 1.0
    rt = 1e-3 * R * p.temperature
    terms = (
        xp.abs(f_sample) + xp.abs(f_buffer) + heat + xp.where(exchanged, rt * stored * level, 0.0)
    )
    magnitude = species_sum(xp.where(on, terms, 0.0), xp=xp)
    valid = xp.all(due | (count == applied) | ~node)  # A stale count refuses the step.
    valid &= xp.all(xp.where(on, xp.isfinite(after) & (after > 0), True))
    valid &= xp.all(xp.isfinite(heat_node) & (heat_node >= 0))  # H_mix >= 0 at every event.
    valid &= xp.all(xp.isfinite(sample_energy) & xp.isfinite(buffer_energy))

    def add(field, term, mask):
        return xp.where(mask, getattr(state, field) + term, getattr(state, field))

    # An ion's supply is its sample (wash_terms), so its supplied record is its collected record:
    # one expression. Two accumulations of the same term round differently where a compiler fuses
    # one product into its sum and not the other (D266: three washes of 3/7 of a 1 uL well left
    # chloride's records one ulp, 2^-25 fmol, apart, and the outside ledger refused the step).
    collected = add("wash_collected_fmol", sample, on)
    last_sample = xp.where(on, sample, state.wash_last_sample_fmol)  # FR-44's level records.
    new = state._replace(
        extracellular_amount_increment=add("extracellular_amount_increment", change, on),
        wash_collected_fmol=collected,
        wash_supplied_fmol=xp.where(
            p.wash_ion[:, None], collected, add("wash_supplied_fmol", supply, on)
        ),
        wash_sample_free_energy_pJ=add("wash_sample_free_energy_pJ", sample_energy, due),
        wash_buffer_free_energy_pJ=add("wash_buffer_free_energy_pJ", buffer_energy, due),
        wash_mixing_heat_pJ=add("wash_mixing_heat_pJ", heat_node, due),
        wash_last_mixing_heat_pJ=xp.where(due, heat_node, state.wash_last_mixing_heat_pJ),
        wash_last_sample_fmol=last_sample,
        wash_last_supply_fmol=xp.where(
            p.wash_ion[:, None], last_sample, xp.where(on, supply, state.wash_last_supply_fmol)
        ),
        wash_energy_magnitude_pJ=add("wash_energy_magnitude_pJ", magnitude, due),
        wash_applied=xp.where(due, applied + 1, applied),
    )
    flowing = xp.any(due)  # Nothing due: the start state, bitwise.
    selected = type(state)(*(xp.where(flowing, a, b) for a, b in zip(new, state, strict=True)))
    if labels is None:
        return selected, valid
    # The records persist past their event, so the report is this step's alone: masked by due.
    now = due[None, :]
    report = LiquidExchange(
        removed=xp.where(now, selected.wash_last_sample_fmol[labels], 0.0),
        supplied=xp.where(now, selected.wash_last_supply_fmol[labels], 0.0),
    )
    return selected, valid, report


def own_valid(state, p, *, xp):
    """Its records at the washed nodes only; the amounts and every event's H_mix (the latest one,
    read on every accepted row) >= 0."""
    on = p.wash_node
    valid = xp.all(state.wash_applied >= 0) & xp.all(xp.where(on, True, state.wash_applied == 0))
    for name in (
        "wash_collected_fmol",
        "wash_supplied_fmol",
        "wash_last_sample_fmol",
        "wash_last_supply_fmol",
    ):
        value = getattr(state, name)
        valid &= xp.all(xp.isfinite(value) & (value >= 0))
        valid &= xp.all(xp.where(on[None, :], True, value == 0))
    for name in (
        "wash_sample_free_energy_pJ",
        "wash_buffer_free_energy_pJ",
        "wash_mixing_heat_pJ",
        "wash_last_mixing_heat_pJ",
        "wash_energy_magnitude_pJ",
    ):
        value = getattr(state, name)
        valid &= xp.all(xp.isfinite(value)) & xp.all(xp.where(on, True, value == 0))
    for name in ("wash_mixing_heat_pJ", "wash_last_mixing_heat_pJ", "wash_energy_magnitude_pJ"):
        valid &= xp.all(getattr(state, name) >= 0)
    return valid


def removed(row, p, *, xp):
    """[species, outside] collected - supplied at the washed nodes (D150's sign)."""
    on = p.wash_node[None, :]
    return xp.where(on, row.wash_collected_fmol - row.wash_supplied_fmol, 0.0)


class ScheduledCompartmentWash(Operator):
    LAW_ID = LAW_ID
    EVENT = True
    LABEL_EVENT = EXCHANGED  # FR-44: beside the label owner its event reports a LiquidExchange.
    STATE_AXES = STATE_AXES
    STATE_DTYPES = {k: np.int64 for k in INTEGER_FIELDS}
    LAYOUT_FIELDS = LAYOUT_FIELDS
    CONTROL_FIELDS = CONTROL_FIELDS
    EXPERIMENT_KEYS = (EVENTS_KEY,)
    # Its nodes' declared volumes, anchors and outside mask, read as the physical ones: fixed reads
    # at its event, scoped to its nodes (door S), so a change elsewhere, such as the bath
    # schedule's dose at a held bath, does not meet them.
    CONFLICTS_VIEW = ("extracellular_volume", "extracellular_amount_reference", "outside_active")
    SCOPED_READS = {name: Read("fixed", "event", scoped=True) for name in CONFLICTS_VIEW}
    ENTITY_WRITES = {
        "extracellular_amount_increment": ("wash_collected_fmol", "wash_supplied_fmol"),
    }
    IDENTITY_ROLE = "user"  # Species registry (D176): it washes species others declare.
    LEDGERS = LEDGERS
    LEDGER_DIAGNOSTICS = LEDGER_DIAGNOSTICS
    LEDGER_MESSAGE = LEDGER_MESSAGE
    # Its run view (docs/RUN_VIEW_DESIGN.md §3): one prescribed layer, every record a total since
    # the start but the latest event's H_mix, sample and supply, and each wash an event at its node.
    VIEW_LAYERS = ({"id": "wash", "label": "Compartment wash", "representation": "prescribed"},)
    UNITS = {"wash_applied": "1"}
    RECORD_KINDS = {
        **dict.fromkeys(STATE_AXES, "cumulative"),
        "wash_last_mixing_heat_pJ": "level",
        "wash_last_sample_fmol": "level",
        "wash_last_supply_fmol": "level",
    }
    ORIENTATION = {
        "wash_collected_fmol": {
            "from": "node",
            "to": "exterior",
            "says": "the samples taken from the node's liquid, out of the world to their sink",
        },
        "wash_supplied_fmol": {
            "from": "exterior",
            "to": "node",
            "says": "the buffer supplied to the node's liquid, into the world from its source",
        },
        "wash_last_sample_fmol": {
            "from": "node",
            "to": "exterior",
            "says": "the latest wash's sample from the node's liquid, out of the world",
        },
        "wash_last_supply_fmol": {
            "from": "exterior",
            "to": "node",
            "says": "the latest wash's buffer supplied to the node's liquid, into the world",
        },
    }

    def view_events(self, spec, declaration, schedule):
        """Its events in the run view: each wash at its node. A wash decides no cell's life, so
        there are no births or retirements to keep."""
        layer = self.VIEW_LAYERS[0]["id"]
        events = [
            dict(
                time=float(e.time),
                kind="wash",
                layer=layer,
                at={"outside": e.node},
                label=f"wash of {e.node}: fraction {e.fraction!r}",
            )
            for e in schedule.events
        ]
        return tuple(sorted(events, key=lambda e: (e["time"], e["label"])))

    # ------------------------------------------------------------ definition

    def parse(self, raw, base, inner_model):
        return parse_declaration(raw, base)

    def to_dict(self, declaration, base):
        return declaration_to_dict(declaration)

    def parse_schedule(self, raw, base, declaration):
        return parse_events(raw, base, declaration)

    def schedule_to_dict(self, schedule, base, declaration):
        return events_to_dict(schedule)

    def schedule_times(self, schedule):
        return tuple(sorted({e.time for e in schedule.events}))

    def value_at(self, schedule, time):
        return due_at(schedule, time)

    def control_values(self, spec, declaration, schedule, records, indices, times):
        outside = [c.id for c in spec.model.extracellular]
        ids = list(spec.model.species_ids)
        o = spec.execution.extracellular_capacity
        count = np.zeros((len(records), o))
        fraction = np.ones((len(records), o))
        buffer = np.ones((len(records), len(ids), o))
        for i, record in enumerate(records):
            for node, washes, f, values in record:
                j = outside.index(node)
                count[i, j], fraction[i, j] = washes, f
                for species, c in values:
                    buffer[i, ids.index(species), j] = c
        return (count[indices], fraction[indices], buffer[indices])

    def check_definition(self, spec, declaration, schedule, model):
        check_definition(spec, declaration)

    def read_slots(self, spec, declaration):
        """Door S: its washed nodes, for each scoped read."""
        outside = [c.id for c in spec.model.extracellular]
        nodes = tuple(sorted(outside.index(n) for n in declaration.nodes))
        return dict.fromkeys(self.SCOPED_READS, nodes)

    def batch_signature(self, declaration):
        """The washed nodes; the times, fractions and buffers are controls."""
        return (LAW_ID, declaration.nodes, declaration.ions)

    def working_size(self, spec):
        x = spec.execution
        return 8 * (5 * len(spec.model.species_ids) + 7) * x.extracellular_capacity

    def summary(self, spec, declaration, schedule, history):
        outside = [c.id for c in spec.model.extracellular]
        ids = list(spec.model.species_ids)

        def last(name):
            return np.asarray(getattr(history, name))[-1]

        records = {}
        for node in declaration.nodes:
            j = outside.index(node)
            records[node] = dict(
                washes=int(last("wash_applied")[j]),
                collected_fmol=dict(
                    zip(ids, last("wash_collected_fmol")[:, j].tolist(), strict=True)
                ),
                supplied_fmol=dict(
                    zip(ids, last("wash_supplied_fmol")[:, j].tolist(), strict=True)
                ),
                sample_free_energy_pJ=float(last("wash_sample_free_energy_pJ")[j]),
                buffer_free_energy_pJ=float(last("wash_buffer_free_energy_pJ")[j]),
                mixing_heat_pJ=float(last("wash_mixing_heat_pJ")[j]),
            )
        return {
            "compartment_wash_law": LAW_ID,
            "compartment_wash_nodes": list(declaration.nodes),
            "compartment_wash_ions": declaration.ions,
            "compartment_wash_events": events_to_dict(schedule)[EVENTS_KEY],
            "compartment_wash_records": records,
            "compartment_wash_mechanism": (
                "a liquid exchange of a compartment, shared with cells.pool_replacement@1 (FR-20), "
                "its whole-exchange execution in exact counts; this is its deterministic execution "
                "(docs/COMPARTMENT_WASH_DESIGN.md; D175, D210, D246)"
            ),
        }

    # ------------------------------------------------------------ binding

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        return bind(spec, declaration)

    # ------------------------------------------------------------ step parts

    def event(self, state, control, p, *, xp, labels=None):
        """The event map (apply_events). labels (FR-44; static): the labelled rows; the call then
        also returns its LiquidExchange report."""
        return apply_events(state, control, p, xp=xp, labels=labels)

    def control_valid(self, control, p, *, xp):
        on = p.wash_node
        f, count = control.wash_fraction, control.wash_count
        valid = xp.all(xp.where(on, xp.isfinite(f) & (f > 0) & (f <= 1), True))
        valid &= xp.all(xp.where(on, xp.isfinite(count) & (count >= 0), True))
        b = control.wash_buffer_mM
        return valid & xp.all(xp.where(on[None, :], xp.isfinite(b) & (b > 0), True))

    def rate_checks(self, state, control, p, valid, *, xp):
        return valid & own_valid(state, p, xp=xp)

    def domain_valid(self, state, p, valid, *, xp):
        own = own_valid(state, p, xp=xp)
        return own if valid is None else valid & own

    # ------------------------------------------------------------ ledgers

    def ledger_terms(self, result, row, p, *, xp):
        """@3's outside and total material ledgers gain collected - supplied at the washed nodes;
        its energy ledger gains H_mix - (F_buffer - F_sample) against its own chemical jump."""
        out = removed(row, p, xp=xp)
        result["outside"] = result["outside"] + out
        result["total"] = result["total"] + entity_sum(out, axis=1, xp=xp)
        exchanged = row.wash_buffer_free_energy_pJ - row.wash_sample_free_energy_pJ
        result["energy"] = result["energy"] + entity_sum(
            row.wash_mixing_heat_pJ - exchanged, axis=None, xp=xp
        )
        return result, self.own_ledgers(row, p, xp=xp)

    def magnitude_terms(self, magnitudes, row, p, *, xp):
        """The exchanged species' moved amounts in the material ledgers' magnitudes (an ion's terms
        cancel exactly), and the energy bookings' absolute terms in the energy ledger's."""
        on = p.wash_node[None, :] & ~p.wash_ion[:, None]
        moved = xp.where(on, row.wash_collected_fmol + row.wash_supplied_fmol, 0.0)
        magnitudes[1] = magnitudes[1] + moved
        magnitudes[2] = magnitudes[2] + entity_sum(moved, axis=1, xp=xp)
        energy = entity_sum(row.wash_energy_magnitude_pJ, axis=None, xp=xp)
        magnitudes[6] = energy if magnitudes[6] is None else magnitudes[6] + energy
        return magnitudes

    def own_ledgers(self, row, p, *, xp):
        """Each ion's sample against its supply at each node: zero, bit for bit (the books show
        the ions unchanged)."""
        ion = p.wash_ion[:, None]
        return dict(wash_ions=xp.where(ion, row.wash_collected_fmol - row.wash_supplied_fmol, 0.0))

    def own_magnitudes(self, row, p, *, xp):
        ion = p.wash_ion[:, None]
        return (xp.where(ion, row.wash_collected_fmol + row.wash_supplied_fmol, 0.0),)

    def own_bounds(self, magnitudes, steps):
        rounding = first.LEDGER_STEP_ROUNDING * np.finfo(float).eps * steps
        return (FLOOR_FMOL + rounding * magnitudes[0],)
