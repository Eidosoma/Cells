"""Operator isopotential_partition@1: prescribed division into fresh daughter slots (stage S5).

docs/CELL_DIVISION_S5_DESIGN.md §3; the law is docs/CELL_DIVISION_DESIGN.md §5.2. The name is
general: a cleaving egg is one use (D144).

Declaration: divisions, each with a parent cell, two daughter cells, a volume fraction f, and maps
from each parent patch, population and contact to one slot in each daughter. A patch map carries
the area fraction a_k of its first daughter. A population takes its patch's fraction, and a
contact map carries its own a_e. Mismatch carriers (transference numbers) are needed when some
a_k differs from f. Schedule (`partition_events`): at most one event per division, with its time
(an exact multiple of dt inside the horizon) and the daughters' carrier IDs.

Slots and anchors (§3.2). Daughters take fresh declared slots, closed by this operator until
their division; the parent's slots close at it. Every daughter anchor is its fraction of the
parent's declared anchor: daughter 1 takes fl(a x) and daughter 2 fl(x - fl(a x)), and the two
must sum to x exactly. That covers reference amounts, volume, background and charge anchor (with
f), and patch area and capacitance (with a_k). The parser refuses anchors that do not follow the
rule; core/partition_spec.add_division writes them. With anchors proportional, the actual content
travels in the increments (D057).

The event map (§3.4), at the start of the step leaving a division's time:
* charges follow the patches: with q_k = C_k V_k at the composite's view, the mismatch
  dq = sum_k (a_k - f) q_k is carried by the declared carriers, delta_s = t_s dq / (z_s F);
* amount increments split: daughter 1 takes f dn_P + delta, daughter 2 dn_P minus that, and the
  parent's increment becomes 0. Area, capacitance and population-abundance increments split by
  their fractions the same way; each move is booked as a signed transfer summing to zero;
* population and contact gates are copied (intensive). A contact that opens without a map (a
  bridge between the daughters) takes its declared gate, and every contact closed at the view
  holds @3's padded gate 0 (the composite pads the initial state the same way);
* retirement (§3.5): the inner history of the parent's patches, populations and contacts
  (transfers and heat) moves into this operator's record and is zeroed, so the inner model sees
  padding. adjust_inner adds the record back, and the composite runs its ledger and dissipation
  checks on that row (the domain on the actual row, at the view);
* the daughters' potentials must equal the parent's and the outside potentials stay put, within
  rounding (the isopotential check). The clamps' rounding-level plate-charge change is booked as
  electrode transfer with its work, at the view;
* the free-energy change of the touched cells (@3's chemical terms on the declared layout) plus
  the change of the physical capacitor energy at the view, less the clamps' work, is booked as
  partition work. With proportional anchors that is the unmixing term, >= 0 and about
  RT sum delta^2 / (2 n f (1 - f)). For f = a_k = 1/2 every term is an exact zero.
A refused event (a daughter amount <= 0, a potential or plate charge moved beyond rounding, a
non-finite value) refuses the step, which returns the full prior state.

Refused at the definition (§3.8): pumps on a dividing cell; a volume provider (CONFLICTS_VIEW);
replacement, insertion@1 and lumen@1 in the composition; unmapped parent patches, populations or
contacts (a bridge between two daughters is not a contact to map); a daughter's patch, population
or contact that no map makes (a contact may be another division's target or a bridge); inexact
anchors; a slot that is
the parent or the daughter of two divisions; a division of an unborn parent; injection current
into a slot outside its living interval.

Lineage (§6): carriers are declared per event and slots are storage. The summary rebuilds the
records from the declaration, the schedule and the final division_applied.
"""

from dataclasses import dataclass, replace

import jax
import jax.numpy as jnp
import numpy as np

from cells.core import pump_composite_spec as composite_spec
from cells.core.multispecies_spec import identifier
from cells.core.specs import ConfigError, _fields, _number
from cells.models import pump_composite_adapter as adapter
from cells.models.operators import membrane_state
from cells.models.operators.contract import Operator
from cells.numerics.extracellular_field import scatter
from cells.processes.electrochemistry import CHARGE_PER_FMOL

LAW_ID = "isopotential_partition@1"
FRACTION_TOLERANCE = 1e-12  # Transference numbers sum to 1.
POTENTIAL_RTOL = 1e-9  # Isopotential check: of the largest |potential| ...
POTENTIAL_ATOL_V = 1e-15  # ... plus this.
PLATE_RTOL = 1e-9  # The clamps' plate charges move only by rounding.
PLATE_ATOL_C = 1e-30
EVENT_ROUNDING = 8.0  # eps multiples of each moved magnitude, for the own ledgers.
FLOORS = (1e-12, 1e-24, 1e-26, 1e-9)  # fmol, m^2, F, units.

STATE_AXES = {
    "division_applied": ["division_slot"],  # int64: 1 once the division has happened.
    "partition_moved_fmol": ["species", "cell_slot"],  # Signed; sums to 0 per division.
    "partition_area_moved_m2": ["membrane_slot"],
    "partition_capacitance_moved_F": ["membrane_slot"],
    "partition_units_moved": ["channel_slot"],
    # The retirement record (§3.5): the retired slots' inner history, added back for the checks.
    "partition_retired_membrane_transferred_fmol": ["species", "membrane_slot"],
    "partition_retired_membrane_heat_pJ": ["membrane_slot"],
    "partition_retired_junction_transferred_fmol": ["species", "edge_slot"],
    "partition_retired_junction_heat_pJ": ["edge_slot"],
    "partition_retired_channel_transferred_fmol": ["species", "channel_slot"],
    "partition_retired_channel_heat_pJ": ["species", "channel_slot"],
    "partition_image_charge_C": ["extracellular_slot"],  # Sum of |plate-charge change| booked.
    "partition_work_pJ": ["cell_slot"],  # At each division's parent slot.
    "partition_energy_magnitude_pJ": ["cell_slot"],
}
LAYOUT_FIELDS = (
    "partition_parent",  # [division] int64
    "partition_daughters",  # [division, 2] int64
    "partition_volume_fraction",  # [division]
    "partition_carrier_fraction",  # [division, species]: transference numbers (0 if none)
    "partition_born_of",  # [cell] int64: the division that makes the cell (-1: none)
    "partition_retired_by",  # [cell] int64: the division that retires it (-1: none)
    "partition_patch_parent",  # [patch row] int64, and the rows below
    "partition_patch_daughters",
    "partition_patch_fraction",
    "partition_patch_division",
    "partition_channel_parent",
    "partition_channel_daughters",
    "partition_channel_fraction",
    "partition_channel_division",
    "partition_contact_parent",
    "partition_contact_daughters",
    "partition_contact_division",
    "partition_birth_gate",  # [edge]: the declared gate, which a contact opening unmapped takes
)
RECORD = {  # The record field of each inner history field it retires.
    "membrane_transferred": "partition_retired_membrane_transferred_fmol",
    "membrane_dissipated_energy_pJ": "partition_retired_membrane_heat_pJ",
    "junction_transferred": "partition_retired_junction_transferred_fmol",
    "junction_dissipated_energy_pJ": "partition_retired_junction_heat_pJ",
    "channel_transferred": "partition_retired_channel_transferred_fmol",
    "channel_dissipated_energy_pJ": "partition_retired_channel_heat_pJ",
}
LEDGERS = ("partition_material", "partition_area", "partition_capacitance", "partition_units")
LEDGER_DIAGNOSTICS = (
    "partition_material_error_fmol",
    "partition_area_error_m2",
    "partition_capacitance_error_F",
    "partition_units_error",
)
LEDGER_MESSAGE = "Partition accounting failed: "
READOUT_COLUMNS = ("partition_slot_phase",)  # Per cell: 0 pending, 1 live, 2 retired.
REFUSED_LAWS = {
    "scheduled_cell_replacement": "replacement books at the declared layout",
    "scheduled_membrane_insertion@1": "insertion@1 provides the masks and computes at its own view",
    "restricted_cleft_lumen@1": "lumen@1 follows one patch; use restricted_cleft_lumen@2",
}


@dataclass(frozen=True)
class SlotMap:
    parent: str
    daughters: tuple  # (daughter 1's slot, daughter 2's slot)
    fraction: float  # Daughter 1's share (patches, contacts); populations take their patch's.


@dataclass(frozen=True)
class Division:
    id: str
    parent: str
    daughters: tuple
    volume_fraction: float
    patches: tuple  # SlotMap
    populations: tuple  # SlotMap (fraction: the patch's)
    contacts: tuple  # SlotMap
    mismatch_carriers: tuple  # ((species, transference number), ...)


@dataclass(frozen=True)
class Partition:
    law: str
    divisions: tuple


@dataclass(frozen=True)
class DivisionEvent:
    division: str
    time: float
    carriers: tuple  # (daughter 1's carrier ID, daughter 2's)


# ------------------------------------------------------------------ the anchor rule


def split(x, a):
    """(fl(a x), fl(x - fl(a x))): daughter 1's and daughter 2's anchor of x."""
    first = a * x
    return first, x - first


def exact_split(x, a, first, second):
    """Whether (first, second) is the anchor rule's split of x, summing to x exactly."""
    one, two = split(x, a)
    return first == one and second == two and first + second == x


# ------------------------------------------------------------------ definition


def _pair(value, what):
    if type(value) is not list or len(value) != 2:
        raise ConfigError(f"A {what} names its two daughter slots")
    return tuple(identifier(v) for v in value)


def _fraction(value, what, *, closed=False):
    value = _number(value, what)
    if not (0.0 <= value <= 1.0 if closed else 0.0 < value < 1.0):
        raise ConfigError(f"A {what} lies in {'[0, 1]' if closed else '(0, 1)'}")
    return value


def parse_partition(raw, base):
    _fields(raw, {"law", "divisions"}, "partition")
    if raw["law"] != LAW_ID:
        raise ConfigError("A partition requires law " + LAW_ID)
    if type(raw["divisions"]) is not list:
        raise ConfigError("A partition declares its divisions in a list")
    divisions = []
    for entry in raw["divisions"]:
        _fields(
            entry,
            {
                "id",
                "parent",
                "daughters",
                "volume_fraction",
                "patches",
                "populations",
                "contacts",
                "mismatch_carriers",
            },
            "division",
        )

        def maps(rows, what, *, fraction, closed=False):
            if type(rows) is not list:
                raise ConfigError(f"A division lists its {what} maps")
            out = []
            for row in rows:
                _fields(row, {"parent", "daughters", *(("fraction",) if fraction else ())}, what)
                a = _fraction(row["fraction"], f"{what} fraction", closed=closed) if fraction else 0
                out.append(SlotMap(identifier(row["parent"]), _pair(row["daughters"], what), a))
            return tuple(out)

        carriers = entry["mismatch_carriers"]
        if type(carriers) is not dict:
            raise ConfigError("Mismatch carriers are an explicit object {species: fraction}")
        divisions.append(
            Division(
                identifier(entry["id"]),
                identifier(entry["parent"]),
                _pair(entry["daughters"], "division"),
                _fraction(entry["volume_fraction"], "volume fraction"),
                maps(entry["patches"], "patch", fraction=True),
                maps(entry["populations"], "population", fraction=False),
                maps(entry["contacts"], "contact", fraction=True, closed=True),
                tuple((s, _number(t, "transference number")) for s, t in carriers.items()),
            )
        )
    declaration = Partition(LAW_ID, tuple(divisions))
    check_structure(base, declaration)
    return declaration


def partition_to_dict(declaration):
    if type(declaration) is not Partition or any(
        type(d) is not Division for d in declaration.divisions
    ):
        raise ConfigError("Require explicit immutable partition declaration types")

    def rows(maps, fraction):
        return [
            dict(
                parent=m.parent,
                daughters=list(m.daughters),
                **(dict(fraction=m.fraction) if fraction else {}),
            )
            for m in maps
        ]

    return dict(
        law=declaration.law,
        divisions=[
            dict(
                id=d.id,
                parent=d.parent,
                daughters=list(d.daughters),
                volume_fraction=d.volume_fraction,
                patches=rows(d.patches, True),
                populations=rows(d.populations, False),
                contacts=rows(d.contacts, True),
                mismatch_carriers=dict(d.mismatch_carriers),
            )
            for d in declaration.divisions
        ],
    )


def bridges(base, declaration):
    """Junction IDs between the two daughters of one division (not contacts to map)."""
    pairs = {frozenset(d.daughters) for d in declaration.divisions}
    return {j.id for j in base.model.junctions if frozenset((j.sender, j.receiver)) in pairs}


def check_structure(base, declaration):
    """The slot structure and the anchor rule on the inner definition (module docstring)."""
    m = base.model
    cells = {c.id: c for c in m.cells}
    membranes = {p.id: p for p in m.membranes}
    channels = {c.id: c for c in m.channels}
    junctions = {j.id: j for j in m.junctions}
    species = list(m.species_ids)
    z = dict(zip(species, m.valence, strict=True))
    ids = [d.id for d in declaration.divisions]
    if len(set(ids)) != len(ids):
        raise ConfigError("Division IDs are unique")
    parents = [d.parent for d in declaration.divisions]
    daughters = [x for d in declaration.divisions for x in d.daughters]
    if len(set(parents)) != len(parents) or len(set(daughters)) != len(daughters):
        raise ConfigError("A cell is the parent of at most one division and a daughter of one")
    links = bridges(base, declaration)
    contact_targets = {x for d in declaration.divisions for e in d.contacts for x in e.daughters}
    for d in declaration.divisions:
        for cell in (d.parent, *d.daughters):
            if cell not in cells:
                raise ConfigError(f"Division {d.id} names an unknown cell {cell!r}")
        if d.parent in d.daughters or d.daughters[0] == d.daughters[1]:
            raise ConfigError(f"Division {d.id}: the parent and its two daughters are distinct")
        f = d.volume_fraction
        parent, one, two = (cells[k] for k in (d.parent, *d.daughters))
        anchors = [("volume", parent.volume_pL, one.volume_pL, two.volume_pL)]
        anchors.append(
            (
                "fixed background",
                parent.fixed_charge_equivalent_fmol,
                one.fixed_charge_equivalent_fmol,
                two.fixed_charge_equivalent_fmol,
            )
        )
        anchors.append(
            ("charge anchor", parent.initial_charge_C, one.initial_charge_C, two.initial_charge_C)
        )
        anchors += [
            (f"amount of {s}", x, y, w)
            for s, x, y, w in zip(
                species,
                parent.initial_amount_fmol,
                one.initial_amount_fmol,
                two.initial_amount_fmol,
                strict=True,
            )
        ]
        for what, x, y, w in anchors:
            if not exact_split(x, f, y, w):
                raise ConfigError(
                    f"Division {d.id}: the daughters' {what} must be the anchor rule's split of "
                    f"the parent's (fl(f x), fl(x - fl(f x)), summing exactly; "
                    "core/partition_spec.add_division writes them)"
                )
        # Patches: every parent patch mapped once, into the right daughters, same domain.
        mapped = {k.parent: k for k in d.patches}
        owned = [p.id for p in m.membranes if p.inside == d.parent]
        if sorted(mapped) != sorted(owned) or len(mapped) != len(d.patches):
            raise ConfigError(f"Division {d.id} maps each of its parent's patches exactly once")
        for k in d.patches:
            parent_patch = membranes[k.parent]
            if parent_patch.pump is not None or parent_patch.calcium_pump is not None:
                raise ConfigError(
                    "Pumps on a dividing cell are later work (pump capacity as state)"
                )
            for daughter, patch_id in zip(d.daughters, k.daughters, strict=True):
                patch = membranes.get(patch_id)
                if patch is None or patch.inside != daughter:
                    raise ConfigError(f"Division {d.id}: patch {patch_id!r} is not {daughter}'s")
                if patch.outside != parent_patch.outside:
                    raise ConfigError(f"Division {d.id}: patch {patch_id!r} faces another node")
                if (
                    patch.permeability_m_per_s != parent_patch.permeability_m_per_s
                    or patch.pump is not None
                    or patch.calcium_pump is not None
                ):
                    raise ConfigError(f"Division {d.id}: patch {patch_id!r} is another domain")
            one_p, two_p = (membranes[x] for x in k.daughters)
            for what, x, y, w in (
                ("area", parent_patch.area_m2, one_p.area_m2, two_p.area_m2),
                (
                    "capacitance",
                    parent_patch.capacitance_F,
                    one_p.capacitance_F,
                    two_p.capacitance_F,
                ),
            ):
                if not exact_split(x, k.fraction, y, w):
                    raise ConfigError(
                        f"Division {d.id}: the {what} of {k.daughters} must be the anchor rule's "
                        f"split of {k.parent}'s"
                    )
        # Populations: every population on a parent patch mapped once, onto the patch's daughters.
        on_parent = [c.id for c in m.channels if c.membrane_id in mapped]
        populations = {c.parent: c for c in d.populations}
        if sorted(populations) != sorted(on_parent) or len(populations) != len(d.populations):
            raise ConfigError(f"Division {d.id} maps each population of its parent exactly once")
        for c in d.populations:
            source = channels[c.parent]
            patch_map = mapped[source.membrane_id]
            for patch_id, channel_id in zip(patch_map.daughters, c.daughters, strict=True):
                target = channels.get(channel_id)
                if target is None or target.membrane_id != patch_id:
                    raise ConfigError(f"Division {d.id}: population {channel_id!r} is misplaced")
                same = (
                    target.kinetic_law == source.kinetic_law
                    and target.max_permeability_m_per_s == source.max_permeability_m_per_s
                    and target.abundance == source.abundance
                    and target.permeant_ions == source.permeant_ions
                )
                if not same:
                    raise ConfigError(f"Division {d.id}: population {channel_id!r} differs")
        # Contacts: every junction of the parent mapped once, except its bridge to a sibling.
        incident = [
            j.id for j in m.junctions if d.parent in (j.sender, j.receiver) and j.id not in links
        ]
        contacts = {e.parent: e for e in d.contacts}
        if sorted(contacts) != sorted(incident) or len(contacts) != len(d.contacts):
            raise ConfigError(f"Division {d.id} maps each contact of its parent exactly once")
        for e in d.contacts:
            source = junctions[e.parent]
            neighbour = source.receiver if source.sender == d.parent else source.sender
            for daughter, junction_id in zip(d.daughters, e.daughters, strict=True):
                target = junctions.get(junction_id)
                if target is None or {target.sender, target.receiver} != {daughter, neighbour}:
                    raise ConfigError(f"Division {d.id}: contact {junction_id!r} is misplaced")
                same = (
                    target.permeability_m_per_s == source.permeability_m_per_s
                    and target.law == source.law
                    and target.threshold_voltage_V == source.threshold_voltage_V
                    and target.minimum_open_fraction == source.minimum_open_fraction
                )
                if not same:
                    raise ConfigError(f"Division {d.id}: contact {junction_id!r} differs")
            one_j, two_j = (junctions[x] for x in e.daughters)
            if not exact_split(source.area_m2, e.fraction, one_j.area_m2, two_j.area_m2):
                raise ConfigError(f"Division {d.id}: contact areas follow the anchor rule")
        # The daughters hold only mapped slots: an unmapped one would open at birth with no
        # anchor from the parent (contacts may also be another division's targets or a bridge).
        made_patches = {x for k in d.patches for x in k.daughters}
        made_populations = {x for c in d.populations for x in c.daughters}
        for daughter in d.daughters:
            for p in m.membranes:
                if p.inside == daughter and p.id not in made_patches:
                    raise ConfigError(f"Division {d.id}: patch {p.id!r} of {daughter} is unmapped")
            for c in m.channels:
                if membranes[c.membrane_id].inside == daughter and c.id not in made_populations:
                    raise ConfigError(
                        f"Division {d.id}: population {c.id!r} of {daughter} is unmapped"
                    )
            for j in m.junctions:
                if daughter in (j.sender, j.receiver) and j.id not in contact_targets | links:
                    raise ConfigError(
                        f"Division {d.id}: contact {j.id!r} of {daughter} is unmapped"
                    )
        # Mismatch carriers: charged species, transference numbers summing to 1.
        uneven = any(k.fraction != f for k in d.patches)
        total = sum(t for _, t in d.mismatch_carriers)
        for s, t in d.mismatch_carriers:
            if s not in z or z[s] == 0 or t < 0:
                raise ConfigError(f"Division {d.id}: carrier {s!r} is a charged species, t >= 0")
        if uneven and abs(total - 1.0) > FRACTION_TOLERANCE:
            raise ConfigError(
                f"Division {d.id}: area fractions differ from f, so mismatch carriers summing "
                "to 1 are declared"
            )
        if d.mismatch_carriers and abs(total - 1.0) > FRACTION_TOLERANCE:
            raise ConfigError(f"Division {d.id}: transference numbers sum to 1")


def parse_events(raw, base, declaration):
    rows = raw["partition_events"]
    if type(rows) is not list:
        raise ConfigError("Partition events are an explicit list")
    known = {d.id for d in declaration.divisions}
    events = []
    for row in rows:
        _fields(row, {"division", "time", "carriers"}, "partition event")
        if row["division"] not in known:
            raise ConfigError(f"A partition event names an unknown division {row['division']!r}")
        events.append(
            DivisionEvent(
                row["division"], _number(row["time"], "time"), _pair(row["carriers"], "carrier")
            )
        )
    if len({e.division for e in events}) != len(events):
        raise ConfigError("A division happens at most once")
    carriers = [c for e in events for c in e.carriers]
    if len(set(carriers)) != len(carriers) or set(carriers) & {c.id for c in base.model.cells}:
        raise ConfigError("Daughter carrier IDs are new and unique")
    # A division's parent must be live at its time: born before it, if it is a daughter.
    when = {e.division: e.time for e in events}
    born = {x: d.id for d in declaration.divisions for x in d.daughters}
    for d in declaration.divisions:
        if d.id in when and d.parent in born:
            birth = when.get(born[d.parent])
            if birth is None or not birth < when[d.id]:
                raise ConfigError(f"Division {d.id} happens after its parent's birth")
    return tuple(sorted(events, key=lambda e: (e.time, e.division)))


def events_to_dict(schedule):
    if any(type(e) is not DivisionEvent for e in schedule):
        raise ConfigError("Require explicit immutable partition event types")
    return dict(
        partition_events=[
            dict(division=e.division, time=e.time, carriers=list(e.carriers)) for e in schedule
        ]
    )


def living_interval(declaration, schedule, cell):
    """(birth, retirement) times of a cell (None: from the start, or never)."""
    when = {e.division: e.time for e in schedule}
    birth = retirement = None
    for d in declaration.divisions:
        if cell in d.daughters:
            birth = when.get(d.id, float("inf"))
        if cell == d.parent and d.id in when:
            retirement = when[d.id]
    return birth, retirement


def check_definition(spec, declaration, schedule, model):
    """Composition refusals and activity outside a slot's living interval (module docstring)."""
    for op in model.operators:
        for law, reason in REFUSED_LAWS.items():
            if op.LAW_ID.startswith(law):
                raise ConfigError(f"A partition cannot run with {op.LAW_ID}: {reason}")
    for op, op_declaration, op_schedule in composite_spec.entries(spec):
        if op.LAW_ID != "electrode_current_injection@1":
            continue
        for electrode, changes in zip(op_declaration.electrodes, op_schedule, strict=True):
            birth, retirement = living_interval(declaration, schedule, electrode.cell_id)
            for k, c in enumerate(changes):
                stop = changes[k + 1].time if k + 1 < len(changes) else float("inf")
                dead = (birth is not None and c.time < birth) or (
                    retirement is not None and stop > retirement
                )
                if c.current_A != 0.0 and dead:
                    raise ConfigError(
                        f"Injection into {electrode.cell_id} outside its living interval"
                    )


def bind(spec, declaration, schedule, inner_state):
    m, x = spec.model, spec.execution
    cells = [c.id for c in m.cells]
    membranes = [p.id for p in m.membranes]
    channels = [c.id for c in m.channels]
    junctions = [j.id for j in m.junctions]
    species = list(m.species_ids)
    n, nd, s = x.capacity, len(declaration.divisions), len(species)
    layout = dict(
        partition_parent=np.zeros(nd, dtype=np.int64),
        partition_daughters=np.zeros((nd, 2), dtype=np.int64),
        partition_volume_fraction=np.zeros(nd),
        partition_carrier_fraction=np.zeros((nd, s)),
        partition_born_of=-np.ones(n, dtype=np.int64),
        partition_retired_by=-np.ones(n, dtype=np.int64),
        partition_birth_gate=np.array(inner_state.junction_gate, dtype=float, copy=True),
    )
    rows = dict(patch=[], channel=[], contact=[])
    for i, d in enumerate(declaration.divisions):
        layout["partition_parent"][i] = cells.index(d.parent)
        layout["partition_daughters"][i] = [cells.index(k) for k in d.daughters]
        layout["partition_volume_fraction"][i] = d.volume_fraction
        for sp, t in d.mismatch_carriers:
            layout["partition_carrier_fraction"][i, species.index(sp)] = t
        layout["partition_retired_by"][cells.index(d.parent)] = i
        for k in d.daughters:
            layout["partition_born_of"][cells.index(k)] = i
        fraction = {}
        for k in d.patches:
            rows["patch"].append(
                (
                    membranes.index(k.parent),
                    [membranes.index(v) for v in k.daughters],
                    k.fraction,
                    i,
                )
            )
            fraction[k.parent] = k.fraction
        for c in d.populations:
            patch = m.channels[channels.index(c.parent)].membrane_id
            rows["channel"].append(
                (
                    channels.index(c.parent),
                    [channels.index(v) for v in c.daughters],
                    fraction[patch],
                    i,
                )
            )
        for e in d.contacts:
            rows["contact"].append(
                (
                    junctions.index(e.parent),
                    [junctions.index(v) for v in e.daughters],
                    e.fraction,
                    i,
                )
            )
    for kind in ("patch", "channel", "contact"):
        table = rows[kind]
        layout[f"partition_{kind}_parent"] = np.asarray([r[0] for r in table], dtype=np.int64)
        layout[f"partition_{kind}_daughters"] = np.asarray(
            [r[1] for r in table], dtype=np.int64
        ).reshape(len(table), 2)
        layout[f"partition_{kind}_division"] = np.asarray([r[3] for r in table], dtype=np.int64)
        if kind != "contact":
            layout[f"partition_{kind}_fraction"] = np.asarray([r[2] for r in table], dtype=float)
    sizes = dict(
        division_slot=nd,
        species=s,
        cell_slot=n,
        membrane_slot=x.membrane_capacity,
        channel_slot=x.channel_capacity,
        edge_slot=x.edge_capacity,
        extracellular_slot=x.extracellular_capacity,
    )
    state = {k: np.zeros([sizes[a] for a in axes]) for k, axes in STATE_AXES.items()}
    state["division_applied"] = np.zeros(nd, dtype=np.int64)
    return state, layout


def check_spec(check_spec_, spec, declaration):
    """R5 (§3.9): each daughter patch with its share of what its parent patch gains over the
    schedule (the incoming check spec's area above the declared one), at its declared,
    smallest, capacitance."""
    declared = {p.id: p.area_m2 for p in spec.model.membranes}
    incoming = {p.id: p.area_m2 for p in check_spec_.model.membranes}
    extra = {}
    for d in declaration.divisions:
        for k in d.patches:
            gained = incoming[k.parent] - declared[k.parent]
            if gained:
                extra[k.daughters[0]] = k.fraction * gained
                extra[k.daughters[1]] = gained - k.fraction * gained
    if not extra:
        return check_spec_
    m = check_spec_.model
    membranes = tuple(
        replace(p, area_m2=p.area_m2 + extra[p.id]) if p.id in extra else p for p in m.membranes
    )
    return replace(check_spec_, model=replace(m, membranes=membranes))


# ------------------------------------------------------------------ the law


def _put(array, index, values, *, xp):
    """array with array[..., index] = values (distinct static slots)."""
    if xp is np:
        out = np.array(array, copy=True)
        out[..., index] = values
        return out
    return array.at[..., index].set(values)


def phases(state, p, *, xp):
    """[cell] 0 pending (a daughter before its division), 2 retired, 1 live."""
    born, retired = p.partition_born_of, p.partition_retired_by
    applied = state.division_applied
    if applied.shape[0] == 0:  # Static: no divisions declared.
        return xp.ones(born.shape, dtype=np.int64)
    pending = (born >= 0) & (applied[xp.maximum(born, 0)] == 0)
    gone = (retired >= 0) & (applied[xp.maximum(retired, 0)] == 1)
    return xp.where(pending, 0, xp.where(gone, 2, 1))


def capacitor_state(state, q, *, xp):
    """(node potentials, patch voltages, live capacitances, held plate charges, U in pJ)."""
    n = q.active.size
    phi = adapter.node_potentials(state, q, xp=xp)
    v = adapter.patch_voltages(phi, q, xp=xp)
    c = xp.where(q.membrane_active, q.membrane_capacitance, 0.0)
    plates = (q.field_capacitor_matrix @ phi)[n:]
    return phi, v, c, plates, 0.5e12 * xp.sum(c * v * v)


def event_map(state, due, p, *, xp, view):
    """(state after the due divisions, validity) (module docstring)."""
    n = p.active.size
    z = xp.reshape(p.valence, (-1,))
    before = view(state)
    phi0, v0, c0, plates0, u0 = capacitor_state(state, before, xp=xp)
    parent, one, two = p.partition_parent, p.partition_daughters[:, 0], p.partition_daughters[:, 1]
    f = p.partition_volume_fraction
    # Charges follow the patches: the mismatch, carried by the declared carriers.
    rows = p.partition_patch_division
    q_patch = (c0 * v0)[p.partition_patch_parent]
    mismatch = scatter(
        (p.partition_patch_fraction - f[rows]) * q_patch, xp.zeros_like(f), (rows,), xp=xp
    )
    valence = xp.where(z == 0, 1.0, z)
    delta = (
        p.partition_carrier_fraction.T * mismatch[None, :] / (valence[:, None] * CHARGE_PER_FMOL)
    )
    # Amounts: daughter 1 takes f dn_P + delta, daughter 2 the rest; the parent's goes to 0.
    increment, moved = state.amount_increment, state.partition_moved_fmol
    dn = increment[:, parent]
    first = f[None, :] * dn + delta
    second = dn - first
    on = due[None, :]
    increment = _put(increment, one, xp.where(on, first, increment[:, one]), xp=xp)
    increment = _put(increment, two, xp.where(on, second, increment[:, two]), xp=xp)
    increment = _put(increment, parent, xp.where(on, 0.0, increment[:, parent]), xp=xp)
    moved = _put(moved, one, xp.where(on, moved[:, one] + first, moved[:, one]), xp=xp)
    moved = _put(moved, two, xp.where(on, moved[:, two] + second, moved[:, two]), xp=xp)
    moved = _put(moved, parent, xp.where(on, moved[:, parent] - dn, moved[:, parent]), xp=xp)
    updates = dict(amount_increment=increment, partition_moved_fmol=moved)

    def split_rows(field, booked, k, kids, fraction, due_rows):
        value, book = getattr(state, field), getattr(state, booked)
        x = value[k]
        a = fraction * x
        b = x - a
        k1, k2 = kids[:, 0], kids[:, 1]
        value = _put(value, k1, xp.where(due_rows, a, value[k1]), xp=xp)
        value = _put(value, k2, xp.where(due_rows, b, value[k2]), xp=xp)
        value = _put(value, k, xp.where(due_rows, 0.0, value[k]), xp=xp)
        book = _put(book, k1, xp.where(due_rows, book[k1] + a, book[k1]), xp=xp)
        book = _put(book, k2, xp.where(due_rows, book[k2] + b, book[k2]), xp=xp)
        book = _put(book, k, xp.where(due_rows, book[k] - x, book[k]), xp=xp)
        updates[field], updates[booked] = value, book

    patch_due = due[p.partition_patch_division]
    channel_due = due[p.partition_channel_division]
    for field, booked in (
        ("membrane_area_increment_m2", "partition_area_moved_m2"),
        ("membrane_capacitance_increment_F", "partition_capacitance_moved_F"),
    ):
        split_rows(
            field,
            booked,
            p.partition_patch_parent,
            p.partition_patch_daughters,
            p.partition_patch_fraction,
            patch_due,
        )
    split_rows(
        "population_abundance_increment",
        "partition_units_moved",
        p.partition_channel_parent,
        p.partition_channel_daughters,
        p.partition_channel_fraction,
        channel_due,
    )
    # Gates are intensive: the daughters' populations and contacts take the parent's.
    gate = state.channel_gate
    for column in (0, 1):
        kids = p.partition_channel_daughters[:, column]
        gate = _put(
            gate,
            kids,
            xp.where(channel_due[None, :], gate[:, p.partition_channel_parent], gate[:, kids]),
            xp=xp,
        )
    junction_gate = state.junction_gate
    contact_due = due[p.partition_contact_division]
    mapped = xp.zeros(junction_gate.shape, dtype=bool)
    for column in (0, 1):
        kids = p.partition_contact_daughters[:, column]
        junction_gate = _put(
            junction_gate,
            kids,
            xp.where(contact_due, junction_gate[p.partition_contact_parent], junction_gate[kids]),
            xp=xp,
        )
        mapped = _put(mapped, kids, mapped[kids] | contact_due, xp=xp)
    updates.update(channel_gate=gate)
    # Retirement: the parent's patches, populations and contacts become padding to @3.
    retired = scatter(xp.where(due, 1.0, 0.0), xp.zeros(n), (parent,), xp=xp) > 0
    patches = retired[p.membrane_cell] & p.membrane_active
    masks = dict(
        membrane_transferred=patches,
        membrane_dissipated_energy_pJ=patches,
        channel_transferred=patches[p.channel_membranes] & p.channel_active,
        channel_dissipated_energy_pJ=patches[p.channel_membranes] & p.channel_active,
        junction_transferred=(retired[p.junction_sender] | retired[p.junction_receiver])
        & p.junction_active,
        junction_dissipated_energy_pJ=(retired[p.junction_sender] | retired[p.junction_receiver])
        & p.junction_active,
    )
    for field, record in RECORD.items():
        value, kept, mask = getattr(state, field), getattr(state, record), masks[field]
        updates[record] = xp.where(mask, kept + value, kept)
        updates[field] = xp.where(mask, 0.0, value)
    updates["division_applied"] = xp.where(due, 1, state.division_applied)
    new = state._replace(**updates)
    # After the event, at the view: isopotential, plate charges, free energy.
    after = view(new)
    # Contacts (a view reads no gate): one that opens takes the parent contact's gate when it
    # maps one, else its declared gate (a bridge); a closed contact holds @3's padded 0.
    opened = after.junction_active & ~before.junction_active
    junction_gate = xp.where(opened & ~mapped, p.partition_birth_gate, junction_gate)
    new = new._replace(junction_gate=xp.where(after.junction_active, junction_gate, 0.0))
    phi1, _, _, plates1, u1 = capacitor_state(new, after, xp=xp)
    scale = POTENTIAL_RTOL * xp.max(xp.abs(phi0)) + POTENTIAL_ATOL_V
    jump = xp.maximum(xp.abs(phi1[one] - phi0[parent]), xp.abs(phi1[two] - phi0[parent]))
    valid = xp.all(xp.where(due, jump <= scale, True))
    outside = after.outside_active & ~p.reservoir
    valid &= xp.all(xp.where(outside, xp.abs(phi1[n:] - phi0[n:]) <= scale, True))
    image = xp.where(p.reservoir, plates1 - plates0, 0.0)
    valid &= xp.all(xp.abs(image) <= PLATE_RTOL * xp.abs(plates0) + PLATE_ATOL_C)
    amounts = p.amount_reference + increment
    kids = xp.concatenate((one, two))
    alive = xp.concatenate((due, due))
    valid &= xp.all(xp.where(alive[None, :], amounts[:, kids] > 0, True))
    work = 1e12 * p.boundary_V * image
    g0 = adapter.chemical_free_energy_pJ(state.amount_increment, p, xp=xp)
    g1 = adapter.chemical_free_energy_pJ(increment, p, xp=xp)
    chemical = (g1[parent] + g1[one] + g1[two]) - (g0[parent] + g0[one] + g0[two])
    count = xp.maximum(xp.sum(due), 1)
    shared = (u1 - u0 - xp.sum(work)) / count
    magnitude = (
        xp.abs(g0[parent])
        + xp.abs(g1[one])
        + xp.abs(g1[two])
        + (xp.abs(u0) + xp.abs(u1) + xp.sum(xp.abs(work))) / count
    )
    booked = new.partition_work_pJ
    booked = _put(
        booked, parent, xp.where(due, booked[parent] + chemical + shared, booked[parent]), xp=xp
    )
    size = new.partition_energy_magnitude_pJ
    size = _put(size, parent, xp.where(due, size[parent] + magnitude, size[parent]), xp=xp)
    new = new._replace(
        electrode_charge_transferred_C=new.electrode_charge_transferred_C + image,
        electrode_work_pJ=new.electrode_work_pJ + work,
        partition_image_charge_C=new.partition_image_charge_C + xp.abs(image),
        partition_work_pJ=booked,
        partition_energy_magnitude_pJ=size,
    )
    for value in new:
        valid &= xp.all(xp.isfinite(value))
    return new, valid


def apply_divisions(state, control, p, *, xp, view):
    """(state after the divisions due at the step start, validity and schedule consistency)."""
    due = (control.partition_due > 0) & (state.division_applied == 0)
    stale = (control.partition_due == 0) & (state.division_applied != 0)
    ok = ~xp.any(stale)
    if xp is np:
        if np.any(due):
            new, valid = event_map(state, due, p, xp=np, view=view)
            return new, ok & valid
        return state, ok
    new, valid = jax.lax.cond(
        jnp.any(due),
        lambda s: event_map(s, due, p, xp=jnp, view=view),
        lambda s: (s, jnp.asarray(True)),
        state,
    )
    return new, ok & valid


def own_valid(state, p, *, xp):
    applied = state.division_applied
    valid = xp.all((applied == 0) | (applied == 1))
    phase = phases(state, p, xp=xp)
    retired = phase == 2
    patches = retired[p.membrane_cell] & p.membrane_active
    channels = patches[p.channel_membranes] & p.channel_active
    contacts = (retired[p.junction_sender] | retired[p.junction_receiver]) & p.junction_active
    for record, mask, sign in (
        ("partition_retired_membrane_transferred_fmol", patches, 0),
        ("partition_retired_membrane_heat_pJ", patches, 1),
        ("partition_retired_junction_transferred_fmol", contacts, 0),
        ("partition_retired_junction_heat_pJ", contacts, 1),
        ("partition_retired_channel_transferred_fmol", channels, 0),
        ("partition_retired_channel_heat_pJ", channels, 1),
    ):
        value = getattr(state, record)
        valid &= xp.all(xp.isfinite(value)) & xp.all(xp.where(mask, True, value == 0))
        if sign:
            valid &= xp.all(value >= 0)
    for name in (
        "partition_moved_fmol",
        "partition_area_moved_m2",
        "partition_capacitance_moved_F",
        "partition_units_moved",
        "partition_work_pJ",
    ):
        valid &= xp.all(xp.isfinite(getattr(state, name)))
    image = state.partition_image_charge_C
    valid &= xp.all(xp.isfinite(image)) & xp.all(image >= 0)
    valid &= xp.all(xp.where(p.reservoir, True, image == 0))
    size = state.partition_energy_magnitude_pJ
    return valid & xp.all(xp.isfinite(size)) & xp.all(size >= 0)


# ------------------------------------------------------------------ the operator


class IsopotentialPartition(Operator):
    LAW_ID = LAW_ID
    EVENT = True
    BOOKS_AT_VIEW = True  # Its event books at the composite's view.
    RETIRES = True
    CLOSES = ("active",)  # Cells only: patches, populations and contacts follow (§2).
    STATE_AXES = STATE_AXES
    STATE_DTYPES = {"division_applied": np.int64}
    WORK_FIELDS = ("partition_work_pJ",)
    LAYOUT_FIELDS = LAYOUT_FIELDS
    CONTROL_FIELDS = ("partition_due",)
    EXPERIMENT_KEYS = ("partition_events",)
    CONFLICTS_VIEW = ("volume",)  # Daughters' volumes are declared anchors (water: later).
    ENTITY_WRITES = {
        "amount_increment": ("partition_moved_fmol",),
        "membrane_area_increment_m2": ("partition_area_moved_m2",),
        "membrane_capacitance_increment_F": ("partition_capacitance_moved_F",),
        "population_abundance_increment": ("partition_units_moved",),
        "electrode_charge_transferred_C": ("partition_image_charge_C",),
        "electrode_work_pJ": ("partition_work_pJ", "partition_energy_magnitude_pJ"),
        **{field: (record,) for field, record in RECORD.items()},
    }
    STATE_RESETS = ("channel_gate", "junction_gate")
    LEDGERS = LEDGERS
    LEDGER_DIAGNOSTICS = LEDGER_DIAGNOSTICS
    LEDGER_MESSAGE = LEDGER_MESSAGE
    READOUT_COLUMNS = READOUT_COLUMNS
    REQUIRES = (membrane_state.LAW_ID,)

    # ------------------------------------------------------------ definition

    def parse(self, raw, base, inner_model):
        return parse_partition(raw, base)

    def to_dict(self, declaration, base):
        return partition_to_dict(declaration)

    def parse_schedule(self, raw, base, declaration):
        return parse_events(raw, base, declaration)

    def schedule_to_dict(self, schedule, base, declaration):
        return events_to_dict(schedule)

    def schedule_times(self, schedule):
        return tuple(e.time for e in schedule)

    def value_at(self, schedule, time):
        return tuple(sorted((e.division, float(e.time <= time)) for e in schedule))

    def control_values(self, spec, declaration, schedule, records, indices, times):
        ids = [d.id for d in declaration.divisions]
        due = np.zeros((len(records), len(ids)))
        for i, record in enumerate(records):
            for division, value in record:
                due[i, ids.index(division)] = value
        return (due[indices],)

    def check_definition(self, spec, declaration, schedule, model):
        check_definition(spec, declaration, schedule, model)

    def inner_check_spec(self, check_spec_, spec, declaration, schedule):
        return check_spec(check_spec_, spec, declaration)

    def batch_signature(self, declaration):
        return (
            LAW_ID,
            tuple(
                (
                    d.id,
                    d.parent,
                    d.daughters,
                    tuple((k.parent, k.daughters) for k in d.patches),
                    tuple((c.parent, c.daughters) for c in d.populations),
                    tuple((e.parent, e.daughters) for e in d.contacts),
                    tuple(s for s, _ in d.mismatch_carriers),
                )
                for d in declaration.divisions
            ),
        )

    def working_size(self, spec):
        x, s = spec.execution, len(spec.model.species_ids)
        return 8 * ((2 * s + 4) * (x.capacity + x.membrane_capacity + x.channel_capacity))

    def summary(self, spec, declaration, schedule, history):
        """The divisions, the lineage, and @3's history totals at the last row with the record
        added (§3.5: the retired slots' transfers and heat still count)."""
        applied = None
        if hasattr(history, "division_applied") and len(np.asarray(history.division_applied)):
            applied = np.asarray(history.division_applied)[-1]
        totals = {}
        if hasattr(history, "division_applied") and len(np.asarray(history.division_applied)):
            for field, record in RECORD.items():
                inner = np.asarray(getattr(history, field))[-1]
                kept = np.asarray(getattr(history, record))[-1]
                totals[field] = dict(
                    live=float(np.sum(inner)),
                    record=float(np.sum(kept)),
                    total=float(np.sum(inner + kept)),
                )
        return {
            "partition_history_totals": totals,
            "partition_law": LAW_ID,
            "partition_divisions": {
                d.id: dict(
                    parent=d.parent,
                    daughters=list(d.daughters),
                    volume_fraction=d.volume_fraction,
                    area_fractions={k.parent: k.fraction for k in d.patches},
                    mismatch_carriers=dict(d.mismatch_carriers),
                )
                for d in declaration.divisions
            },
            "lineage": lineage(spec, declaration, schedule, applied),
        }

    # ------------------------------------------------------------ binding

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        return bind(spec, declaration, schedule, inner_state)

    # ------------------------------------------------------------ step parts

    def statically_idle(self, p):
        return p.partition_parent.shape[0] == 0

    def closures(self, state, p, q, *, xp):
        return dict(active=phases(state, p, xp=xp) == 1)

    def event(self, state, control, p, *, xp, view=None):
        if view is None:
            raise ConfigError("The partition books at the composite's view")
        return apply_divisions(state, control, p, xp=xp, view=view)

    def control_valid(self, control, p, *, xp):
        due = control.partition_due
        return xp.all((due == 0) | (due == 1))

    def rate_checks(self, state, control, p, valid, *, xp):
        return valid & own_valid(state, p, xp=xp)

    def domain_valid(self, state, p, valid, *, xp):
        own = own_valid(state, p, xp=xp)
        return own if valid is None else valid & own

    # ------------------------------------------------------------ ledgers

    def adjust_inner(self, row, p, *, xp):
        """The row with the retirement record added back into @3's history fields (§3.5)."""
        return row._replace(
            **{
                field: getattr(row, field) + getattr(row, record)
                for field, record in RECORD.items()
            }
        )

    def ledger_terms(self, result, row, p, *, xp):
        moved = row.partition_moved_fmol
        result["local"] = result["local"] - moved
        result["total"] = result["total"] - xp.sum(moved, axis=1)
        result["energy"] = result["energy"] - xp.sum(row.partition_work_pJ)
        return result, self.own_ledgers(row, p, xp=xp)

    def magnitude_terms(self, magnitudes, row, p, *, xp):
        moved = xp.abs(row.partition_moved_fmol)
        magnitudes[0] = magnitudes[0] + moved
        magnitudes[2] = magnitudes[2] + xp.sum(moved, axis=1)
        image = row.partition_image_charge_C
        magnitudes[4] = image if magnitudes[4] is None else magnitudes[4] + image
        charge = xp.sum(image)
        magnitudes[5] = charge if magnitudes[5] is None else magnitudes[5] + charge
        energy = xp.sum(row.partition_energy_magnitude_pJ)
        magnitudes[6] = energy if magnitudes[6] is None else magnitudes[6] + energy
        return magnitudes

    def own_ledgers(self, row, p, *, xp):
        return dict(
            partition_material=xp.sum(row.partition_moved_fmol, axis=1),
            partition_area=xp.sum(row.partition_area_moved_m2),
            partition_capacitance=xp.sum(row.partition_capacitance_moved_F),
            partition_units=xp.sum(row.partition_units_moved),
        )

    def own_magnitudes(self, row, p, *, xp):
        return (
            xp.sum(xp.abs(row.partition_moved_fmol), axis=1),
            xp.sum(xp.abs(row.partition_area_moved_m2)),
            xp.sum(xp.abs(row.partition_capacitance_moved_F)),
            xp.sum(xp.abs(row.partition_units_moved)),
        )

    def own_bounds(self, magnitudes, steps):
        rounding = EVENT_ROUNDING * np.finfo(float).eps
        return tuple(floor + rounding * m for floor, m in zip(FLOORS, magnitudes, strict=True))

    def external_ledger_terms(self, ledgers, row, p, *, xp):
        booked = dict(
            membrane_area_entity=row.partition_area_moved_m2,
            membrane_capacitance_entity=row.partition_capacitance_moved_F,
            population_abundance_entity=row.partition_units_moved,
        )
        return {k: v - booked[k] for k, v in ledgers.items()}

    def external_magnitude_terms(self, magnitudes, row, p, *, xp):
        booked = dict(
            membrane_area_entity=row.partition_area_moved_m2,
            membrane_capacitance_entity=row.partition_capacitance_moved_F,
            population_abundance_entity=row.partition_units_moved,
        )
        return {k: v + xp.abs(booked[k]) for k, v in magnitudes.items()}

    # ------------------------------------------------------------ observations

    def observe(self, row, state, control, p, view, model, spec):
        columns = {k: getattr(state, k) for k in self.STATE_AXES}
        columns["partition_slot_phase"] = np.asarray(phases(state, p, xp=np))
        return columns


def lineage(spec, declaration, schedule, applied=None):
    """One record per carrier: founders, then daughters in event order (§6.1).

    applied: the final division_applied (None: every scheduled event counts).
    """
    divisions = {d.id: (i, d) for i, d in enumerate(declaration.divisions)}
    daughters = {x for d in declaration.divisions for x in d.daughters}
    current = {
        c.id: dict(carrier_id=c.id, slot=c.id, kind="founder", birth_s=0.0)
        for c in spec.model.cells
        if c.id not in daughters
    }
    records = list(current.values())
    for e in schedule:
        i, d = divisions[e.division]
        if applied is not None and not int(applied[i]):
            continue
        parent = current[d.parent]
        parent.update(death_s=e.time, successors=list(e.carriers))
        for k, (slot, carrier) in enumerate(zip(d.daughters, e.carriers, strict=True)):
            record = dict(
                carrier_id=carrier,
                slot=slot,
                kind="daughter",
                birth_s=e.time,
                parent_carrier=parent["carrier_id"],
                sibling=e.carriers[1 - k],
                route="division",
                division=d.id,
                volume_fraction=d.volume_fraction if k == 0 else 1.0 - d.volume_fraction,
            )
            records.append(record)
            current[slot] = record
    for r in records:
        r.setdefault("death_s", None)
        r.setdefault("successors", [])
    return records
