"""Declared laws of cells.model.resolved_pump_tissue@3, and the value-free structure of a definition.

Design: docs/INNER_MODEL_V4_DESIGN.md §7.1 (a law's declaration) and §7.4 (the interface for
D176's round). One frozen declaration per law ID, with a fixed registry code:

* channel laws (codes 0-4 today: definitions/surface_pump_v3_spec.LAW_CODES). A new law takes
  the next free code; no code is reused;
* the junction conductance law (every junction declares it today);
* the two pump laws, on today's maintained fuel kind;
* the two route laws every membrane, junction and face declares (provenance for the run view).

**Each law's declaration lives in its own module** (docs/CORE_SEAMS_DESIGN.md §8.2; the lead's
ruling R1, 18 November 2026), with its kernels and its docstring, and the law registry's loader
registers it (registry/laws.py), so @3 finds its laws in the active law registry by interface and
host, never in a table here: InnerStructure validates against it (§8.3). The modules:
laws/channels/{kv1p5_mh, kir2p1_mh2, nav1p2_m3h_regularized, kleak_always_open,
naleak_always_open}.py, laws/junctions/junction_voltage_relaxation.py,
laws/pumps/{nak_atp_mass_action_positive, ca_atp_mass_action_positive}.py and
laws/routes/{constant_field, logmean_electrodiffusion}.py. The shared kernel modules
(voltage_gates, potassium_channels, sodium_channels, junction_gate, kinetic_pump and
calcium_atpase) re-import their names for the other families. Each opening keeps today's
operation order, which per-law dispatch needs to stay bitwise (probe P2 of the note): Kv1.5 m h,
Kir2.1 (m h) h, NaV1.2 m^3 h.

The tables below keep today's names for their readers. CHANNEL_LAWS is the active registry's
channel laws that @3 runs, in code order, so a channel law registered later is in it with no
edit here; the junction, pump and route tables name version 1's laws, which its layout runs each
by name, in today's order (the pumps' order is the structure's: models/surface_pump_v3.structure).

InnerStructure is what one definition declares, as Python values with no parameter value in it:
the inner model builds one implementation per structure (models/surface_pump_v3.implementation),
which closes over the structure and never over a value (P5).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from cells.definitions.kinetic_pump_spec import METABOLISM_ID
from cells.definitions.surface_pump_v3_spec import (
    DEFAULT_JUNCTION_HEAT,
    EXACT_FREE_ENERGY_HEAT,
    MODEL_ID,
    ONE_WAY_ENTITIES,
    TRAPEZOID_JUNCTION_HEAT,
)
from cells.laws.channels import kv1p5_mh, nav1p2_m3h_regularized
from cells.laws.channels.voltage_shift import KINDS as SHIFT_KINDS
from cells.laws.junctions import junction_series_gates, junction_voltage_relaxation
from cells.laws.pumps import ca_atp_mass_action_positive, nak_atp_mass_action_positive
from cells.laws.routes import (
    constant_field,
    logmean_electrodiffusion,
    logmean_electrodiffusion_forms,
)
from cells.registry import kind_registry
from cells.registry import laws as law_registry
from cells.registry.kind_registry import qualified
from cells.registry.laws import ChannelLaw, JunctionLaw, PumpLaw, RouteLaw  # noqa: F401

HOST = qualified(MODEL_ID)  # @3 runs its own populations' laws (registry/laws.py: `host`).
MAINTAINED_FUEL_ID = (
    METABOLISM_ID  # cells.fuel_kind.maintained_chemical_reservoirs@1, today's pumps' fuel kind.
)
MEMBRANE_ROUTE_LAW_ID = constant_field.LAW_ID  # The passive membrane and junction route law.
FACE_ROUTE_LAW_ID = logmean_electrodiffusion.LAW_ID
# The forms law (the face note's §2-4, MITOCHONDRIA_DESIGN; its build plan's item 1): a face that
# declares it moves each row it carries as its forms, in its own entity set (InnerStructure
# .forms_faces); every other face keeps FACE_ROUTE_LAW_ID.
FORMS_FACE_ROUTE_LAW_ID = logmean_electrodiffusion_forms.LAW_ID
BASE_GATE_ROWS = 2  # Today's channel gate rows; a law with more gates adds rows where declared.
# Reference RK4 step bounds: 2.5 us with NaV1.2, 25 us with Kv1.5 or Kir2.1, as their declarations
# hold them. surface_pump_v3's RK4_*_STEP are these.
RK4_SODIUM_STEP_S = nav1p2_m3h_regularized.RK4_STEP_S
RK4_POTASSIUM_STEP_S = kv1p5_mh.RK4_STEP_S
# Heat bookings (docs/CORE_SEAMS_DESIGN.md §6.1): the tableau books every mover class by default
# and is never listed; @3's own mover classes, and the bookings each admits beyond it: the
# trapezoid for channels, as ruled there, for junctions, today's junction_heat_booking, and for
# membranes, pumps and calcium pumps, whose power is never negative (the lead, 18 November 2026);
# and for faces the exact booking alone, their neutral rows' exact free-energy release (D280; added
# at the lead's word, a recorded exception in this file; surface_pump_v3.exact_face_heat).
# A declared kind's routes are the class its namespaced ID names, admitting its heat_bookings.
TABLEAU_HEAT_BOOKING = DEFAULT_JUNCTION_HEAT
CHANNELS, JUNCTIONS = "channels", "junctions"
MEMBRANES, PUMPS, CALCIUM_PUMPS = "membranes", "pumps", "calcium_pumps"
FACES = "faces"
OWN_HEAT_BOOKINGS = MappingProxyType(
    {
        **{
            mover: (TRAPEZOID_JUNCTION_HEAT,)
            for mover in (CHANNELS, JUNCTIONS, MEMBRANES, PUMPS, CALCIUM_PUMPS)
        },
        FACES: (EXACT_FREE_ENERGY_HEAT,),
    }
)


class _HostedChannelLaws(Mapping):
    """The active law registry's channel laws that @3 runs, by law ID as declared, in code order
    (the module docstring): a live view, so a channel law registered later needs no edit here."""

    def _laws(self):
        laws = sorted(_hosted(law_registry.CHANNEL_LAW), key=lambda law: law.code)
        return {law.law_id: law for law in laws}

    def __getitem__(self, law_id):
        return self._laws()[law_id]

    def __iter__(self):
        return iter(self._laws())

    def __len__(self):
        return len(self._laws())

    def __repr__(self):
        return f"CHANNEL_LAWS({list(self)!r})"


CHANNEL_LAWS = _HostedChannelLaws()
JUNCTION_LAWS = MappingProxyType(
    {
        junction_voltage_relaxation.LAW_ID: junction_voltage_relaxation.LAW,
        # FR-30, development only (D262; the @3 owner's recorded exception in the F owner's file).
        junction_series_gates.LAW_ID: junction_series_gates.LAW,
    }
)
PUMP_LAWS = MappingProxyType(  # Today's order: the structure's.
    {
        nak_atp_mass_action_positive.LAW_ID: nak_atp_mass_action_positive.LAW,
        ca_atp_mass_action_positive.LAW_ID: ca_atp_mass_action_positive.LAW,
    }
)
# The passive route laws every membrane, junction and face declares (provenance for the run view,
# D154): moved unchanged into @3 with its families (parity, not calibrated).
ROUTE_LAWS = MappingProxyType(
    {
        constant_field.LAW_ID: constant_field.LAW,
        logmean_electrodiffusion.LAW_ID: logmean_electrodiffusion.LAW,
        logmean_electrodiffusion_forms.LAW_ID: logmean_electrodiffusion_forms.LAW,
    }
)


def channel_codes():
    """{law ID: registry code} of every channel law @3 runs, in the active law registry."""
    return {law.law_id: law.code for law in _hosted(law_registry.CHANNEL_LAW)}


def _hosted(interface):
    """The active law registry's laws of `interface` that @3 runs (§8.3)."""
    return law_registry.active().laws(interface, HOST)


def heat_booking_errors(bookings, kinds, junction_heat_booking=DEFAULT_JUNCTION_HEAT):
    """Why an InnerStructure's heat_bookings break seam D's switch (empty: they keep it), for a
    structure whose declared kinds are `kinds` (namespaced IDs): pairs of non-empty names,
    strictly sorted by mover class, none on the tableau; each class one of @3's own, admitting
    the booking (OWN_HEAT_BOOKINGS), or a declared kind whose heat_bookings admit it, found in the
    active kind registry; a JUNCTIONS pair equal to junction_heat_booking. Today's empty switch
    reads nothing."""
    if bookings == ():
        return []
    if not (
        isinstance(bookings, tuple)
        and all(
            isinstance(pair, tuple)
            and len(pair) == 2
            and all(isinstance(name, str) and name for name in pair)
            for pair in bookings
        )
    ):
        return ["they are (mover class, booking ID) pairs of names"]
    out, classes = [], [mover for mover, _ in bookings]
    if classes != sorted(set(classes)):
        out.append("they are sorted, one pair per mover class")
    for mover, booking in bookings:
        if booking == TABLEAU_HEAT_BOOKING:
            out.append(f"{mover}: the tableau is the default and is never listed")
        elif mover in OWN_HEAT_BOOKINGS:
            if booking not in OWN_HEAT_BOOKINGS[mover]:
                admitted = ", ".join(OWN_HEAT_BOOKINGS[mover])
                out.append(f"{mover} admit {admitted} beyond the tableau, not {booking}")
            elif mover == JUNCTIONS and booking != junction_heat_booking:
                out.append(f"junctions book {junction_heat_booking}, not {booking}")
        elif mover not in kinds:
            own = ", ".join(OWN_HEAT_BOOKINGS)
            out.append(
                f"{mover} is neither one of @3's own mover classes ({own}) nor a declared kind"
            )
        elif booking not in kind_registry.active().lookup(mover).heat_bookings:
            out.append(f"kind {mover} admits no heat booking {booking}")
    return out


def kind_ledger_errors(ledgers, kinds):
    """Why an InnerStructure's kind_ledgers break E's list (empty: they keep it), for a structure
    whose declared kinds are `kinds` (namespaced IDs): (kind ID, ((ledger, diagnostic), ...))
    entries of non-empty names, at most one per declared kind, sorted by kind ID, each with at
    least one pair; every name distinct across them, none taken by @1's ten ledgers or their
    diagnostics (surface_pump's, read only where a kind declares a ledger), and no ledger named
    for one of ledger_terms' roles (kind_registry.LEDGER_TERM_ROLES, as kind_ledgers refuses).
    Today's empty list reads nothing."""
    if ledgers == ():
        return []
    if not (
        isinstance(ledgers, tuple)
        and all(
            isinstance(entry, tuple)
            and len(entry) == 2
            and isinstance(entry[0], str)
            and entry[0]
            and isinstance(entry[1], tuple)
            and entry[1]
            and all(
                isinstance(pair, tuple)
                and len(pair) == 2
                and all(isinstance(name, str) and name for name in pair)
                for pair in entry[1]
            )
            for entry in ledgers
        )
    ):
        return ["they are (kind ID, ((ledger, diagnostic), ...)) entries of names"]
    from cells.models import surface_pump as today  # @1's ten, where a kind declares a ledger.

    out, owners = [], [kind_id for kind_id, _ in ledgers]
    if owners != sorted(set(owners)):
        out.append("they are sorted, one entry per kind")
    for kind_id in owners:
        if kind_id not in kinds:
            out.append(f"{kind_id} is not a declared kind")
    names = [(kind_id, name) for kind_id, pairs in ledgers for pair in pairs for name in pair]
    seen, taken = set(), {*today.LEDGERS, *today.LEDGER_DIAGNOSTICS}
    for kind_id, name in names:
        if name in taken:
            out.append(f"kind {kind_id}'s {name} is one of @1's ledgers or diagnostics")
        elif name in seen:
            out.append(f"kind {kind_id}'s {name} is named twice")
        seen.add(name)
    reserved = sorted(
        {ledger for _, pairs in ledgers for ledger, _ in pairs}
        & set(kind_registry.LEDGER_TERM_ROLES)
    )
    if reserved:
        out.append(f"ledgers {reserved} take names of ledger_terms' roles, as kind_ledgers refuses")
    return out


def loop_errors(loops, routes):
    """Why a structure's loops break their form (empty: they keep it): distinct and sorted ((route,
    row), (kind ID, pair)) positions, each route one of `routes` and each kind a source of it."""

    def position(value):
        return type(value) is int and value >= 0

    def formed(loop):
        pairs = isinstance(loop, tuple) and len(loop) == 2
        if not (pairs and all(isinstance(end, tuple) and len(end) == 2 for end in loop)):
            return False
        (route, row), (kind_id, pair) = loop
        if not (position(route) and route < len(routes) and position(row) and position(pair)):
            return False
        return kind_id in {source for source, _ in routes[route][3]}

    if not (isinstance(loops, tuple) and all(map(formed, loops))):
        return ["they are ((route, row), (source kind ID, pair)) positions of the declared routes"]
    return [] if list(loops) == sorted(set(loops)) else ["they are distinct and sorted"]


@dataclass(frozen=True)
class InnerStructure:
    """What one definition declares (§7.4 (a)): Python values only, never a parameter value.

    declared_channel_laws lists the channel law IDs its populations name, in registry-code
    order (not the layout's per-slot code array, which is data). Later kinds join as fields
    present only when declared.
    """

    declared_channel_laws: tuple[str, ...]
    junction_laws: tuple[str, ...]
    pump_laws: tuple[str, ...]
    fuel_kinds: tuple[str, ...]
    junction_heat_booking: str
    # True where the definition's composition closes population slots mid-run (an operator
    # with CLOSES): a closed slot carries code 0 and keeps its gate update, so the compiled
    # kinetics also evaluate the code-0 law there, today's dynamics, as the host's declared
    # fill does everywhere (docs/INNER_MODEL_V4_DESIGN.md §7.4 (b); temporary, until an
    # explicit absent marker).
    padding_fill: bool = False
    # The declared kinds (§7.4 (j), (k)): ((namespaced kind ID, the kind's structure entry), ...)
    # in canonical (sorted ID) order; () for every definition of today's.
    kinds: tuple = ()
    # The routing door's table (§7.4 (n)), resolved at binding: ((sink kind ID, control field,
    # slot, ((source kind ID, position), ...)), ...), value-free; () without a sink (A4).
    routes: tuple = ()
    # Seam D's static switch (docs/CORE_SEAMS_DESIGN.md §6.1): ((mover class, booking ID), ...),
    # sorted, one pair per mover class whose heat the tableau does not book: @3's own CHANNELS or
    # JUNCTIONS, or a declared kind's namespaced ID for its routes. The tableau, the default, is
    # never listed, so () for every definition of today's and no structure or fingerprint moves.
    # A JUNCTIONS pair agrees with junction_heat_booking.
    heat_bookings: tuple = ()
    # P1's static switch (docs/CORE_SEAMS_DESIGN.md §17; §19 as amended, the general layout only;
    # the binding owner's selector, ruling (a) of 19 November 2026): the declared kinds' IDs,
    # sorted, whose stage rows all name, as their third item, a registered law that declares
    # free_amounts. The IMEX step's positivity predictor reads those kinds' stage reads at the
    # predicted stored totals. () for every definition of today's, so no structure or program
    # moves. Added by the @3 owner at the lead's word (a recorded exception in this file).
    free_amount_reads: tuple = ()
    # E's kind ledgers (docs/CORE_SEAMS_DESIGN.md §7.3; INNER_MODEL_V4_DESIGN §7.4 (p)): each
    # declared kind's own ledgers, ((kind ID, ((ledger, diagnostic), ...)), ...) in canonical
    # (sorted ID) order, read once from its declaration (kind_registry.kind_ledgers). Names only:
    # the values are the kind's ledger_terms under those names and the bounds its ledger_bounds,
    # both at check time. () for every definition of today's, so no structure or program moves.
    # Added by the @3 owner at the lead's word (a recorded exception in this file).
    kind_ledgers: tuple = ()
    # FR-30 (D262): the kinds of cells.junction.junction_series_gates@1's gates, in its GATES order, where the
    # junctions declare that law (every junction or none in v1); () otherwise, so no structure or
    # program of today's moves. Added by the @3 owner (a recorded exception in this file).
    junction_series_kinds: tuple = ()
    # Fix (A) (D273): the IDs, sorted, of the junctions that join two capacitor components where
    # one floats (surface_pump_v3.crossing_junctions, from the parsed topology). Where any exists
    # the IMEX step's explicit rates, and N2's stage junction gates, read each stage state's
    # quasi-static potentials. () for a world whose junctions all join held components, so no
    # structure or program of those moves. Added by the @3 owner (a recorded exception here).
    crossing_junctions: tuple = ()
    # The forms faces (cells.route.logmean_electrodiffusion_forms@1; MITOCHONDRIA_DESIGN's face note, its
    # build plan's item 1): their IDs, sorted, where the definition declares any. They are their
    # own entity set, with their own layout and state fields (surface_pump_v3.FORMS_*), so () for
    # every other definition: no structure, layout or program of those moves (D148 case 2). Added
    # by the face builder under the @3 owner's leave (a recorded exception in this file).
    forms_faces: tuple = ()
    # FR-51 (D327, ruling 6): the channel populations that declare a block
    # (cells.channel_block.open_channel_block_weighted_modes@1), their IDs sorted, and the static mode count M (the
    # largest any declares, at most 4). They are () and 0 for every other definition, so no
    # structure, layout or program of those moves. Added by the @3 owner at the lead's word (a
    # recorded exception in this file).
    blocked_channels: tuple = ()
    block_modes: int = 0
    # The charge rule beside a floating node (docs/CALCIUM_STORE_AND_CHANNELS_DESIGN.md §8.3):
    # whether an outside node floats (surface_pump.floating_nodes, from the parsed topology).
    # Where one does, membrane_rate takes charge_rows. False for every other definition, so no
    # structure or program of those moves; no layout, state or control field depends on it.
    floating_nodes: bool = False
    # A factor's feedback (docs/CALCIUM_STORE_AND_CHANNELS_DESIGN.md §6.5): the loops that the
    # door's slots close on their own gates, ((m, p), ...), sorted, where a source of a slot reads a
    # row that the slot moves (surface_pump_v3._loops): m = (the slot's position in `routes`, the
    # row's position among its moved rows), p = (the source's kind ID, the pair's position among
    # that kind's pairs). Positions, value-free: the arrays' indices are layout fields
    # (LOOP_LAYOUT_FIELDS), present only where this is not empty. () for every definition without
    # such a loop, so no structure, layout or program of those moves.
    loops: tuple = ()
    # FR-50 phase 2 (D327, ruling 4): @3's own one-way record pairs, ((entity kind, entity ID,
    # species ID), ...), sorted, names only (surface_pump_v3_spec.one_way_pairs), each entity kind
    # one of ONE_WAY_ENTITIES, so the pairs of one kind are contiguous. () for every definition
    # without the model key, so no structure, layout or program of those moves. Added by the @3
    # owner at the lead's word (a recorded exception in this file).
    one_way_records: tuple = ()
    # FR-64 (D356, D361): the shifted readers, ((channel ID, reader, kind key), ...), sorted
    # (surface_pump_v3_spec.shifted_readers). A reader is a gate name of the population's law or
    # "block", and a kind key is one of laws/channels/voltage_shift.KINDS. The entry is value-free:
    # every static switch on a shift reads it, so only declared kinds are traced, and the values
    # are layout fields present only where it is not empty. () for every definition without a
    # shift, so no structure, layout or program of those moves. Added by the @3 owner at the lead's
    # word (a recorded exception in this file).
    shifted_readers: tuple = ()

    def __post_init__(self):
        ids = [kind_id for kind_id, _ in self.kinds]
        if ids != sorted(set(ids)):
            raise ValueError("Declared kinds must be distinct and in canonical (sorted ID) order")
        problems = heat_booking_errors(self.heat_bookings, ids, self.junction_heat_booking)
        if problems:
            raise ValueError("Heat bookings of an inner structure: " + "; ".join(problems))
        reads = self.free_amount_reads
        if not (isinstance(reads, tuple) and all(isinstance(k, str) and k for k in reads)):
            raise ValueError("Free-amount reads are a tuple of declared kind IDs")
        if list(reads) != sorted(set(reads)) or not set(reads) <= set(ids):
            raise ValueError(
                "Free-amount reads must be distinct declared kinds, in canonical (sorted ID) order"
            )
        problems = kind_ledger_errors(self.kind_ledgers, ids)
        if problems:
            raise ValueError("Kind ledgers of an inner structure: " + "; ".join(problems))
        crossing = self.crossing_junctions
        if not (
            isinstance(crossing, tuple)
            and all(isinstance(j, str) and j for j in crossing)
            and list(crossing) == sorted(set(crossing))
        ):
            raise ValueError("Crossing junctions are a sorted tuple of distinct junction IDs")
        forms = self.forms_faces
        if not (
            isinstance(forms, tuple)
            and all(isinstance(f, str) and f for f in forms)
            and list(forms) == sorted(set(forms))
        ):
            raise ValueError("Forms faces are a sorted tuple of distinct face IDs")
        blocked = self.blocked_channels
        if not (
            isinstance(blocked, tuple)
            and all(isinstance(c, str) and c for c in blocked)
            and list(blocked) == sorted(set(blocked))
            and type(self.block_modes) is int
            and (0 if not blocked else 1) <= self.block_modes <= (4 if blocked else 0)
        ):
            raise ValueError(
                "Blocked channels are a sorted tuple of distinct channel IDs, with a mode count "
                "from 1 to 4 where any is declared and 0 where none is"
            )
        if type(self.floating_nodes) is not bool:
            raise ValueError("A structure's floating_nodes is a bool (whether a node floats)")
        pairs = self.one_way_records
        if not (
            isinstance(pairs, tuple)
            and all(
                isinstance(pair, tuple)
                and len(pair) == 3
                and all(isinstance(name, str) and name for name in pair)
                and pair[0] in ONE_WAY_ENTITIES
                for pair in pairs
            )
            and list(pairs) == sorted(set(pairs))
        ):
            raise ValueError(
                "One-way records are a sorted tuple of distinct (entity kind, entity ID, species "
                f"ID) pairs, each entity kind one of {', '.join(ONE_WAY_ENTITIES)}"
            )
        readers = self.shifted_readers
        if not (
            isinstance(readers, tuple)
            and all(
                isinstance(reader, tuple)
                and len(reader) == 3
                and all(isinstance(name, str) and name for name in reader)
                and reader[2] in SHIFT_KINDS
                for reader in readers
            )
            and list(readers) == sorted(set(readers))
            and len({reader[:2] for reader in readers}) == len(readers)
        ):
            raise ValueError(
                "Shifted readers are a sorted tuple of distinct (channel ID, reader, kind key) "
                f"triples, one kind per reader, each kind one of {', '.join(SHIFT_KINDS)}"
            )
        problems = loop_errors(self.loops, self.routes)
        if problems:
            raise ValueError("Loops of an inner structure: " + "; ".join(problems))
        series = self.junction_series_kinds
        if (
            (junction_series_gates.LAW_ID in self.junction_laws) != bool(series)
            or series
            and (
                not isinstance(series, tuple)
                or len(series) != junction_series_gates.GATE_COUNT
                or any(kind not in junction_series_gates.KINDS for kind in series)
                or self.junction_laws != (junction_series_gates.LAW_ID,)
            )
        ):
            raise ValueError(
                "Series gate kinds name one kind per gate of "
                "cells.junction.junction_series_gates@1, the "
                "structure's only junction law"
            )
        # Validated against the active law registry (§8.3): each declared law is one @3 runs.
        unknown = []
        for interface, declared in (
            (law_registry.CHANNEL_LAW, self.declared_channel_laws),
            (law_registry.JUNCTION_LAW, self.junction_laws),
            (law_registry.CYCLE_LAW, self.pump_laws),
        ):
            hosted = {qualified(law.law_id) for law in _hosted(interface)}
            unknown += [law for law in declared if qualified(law) not in hosted]
        if unknown:
            raise ValueError("Undeclared laws in an inner structure: " + ", ".join(unknown))
        codes = {qualified(law.law_id): law.code for law in _hosted(law_registry.CHANNEL_LAW)}
        order = tuple(sorted(self.declared_channel_laws, key=lambda law: codes[qualified(law)]))
        if order != self.declared_channel_laws or len(set(order)) != len(order):
            raise ValueError("Declared channel laws must be distinct and in registry-code order")

    @property
    def channel_laws(self):
        """The declarations of the declared channel laws, in code order, from the active law
        registry (one object per cells law ID, so the same in every registry)."""
        registry = law_registry.active()
        return tuple(registry.lookup(law) for law in self.declared_channel_laws)

    @property
    def gate_rows(self):
        """Channel gate rows: today's two, or more where a declared law has more gates."""
        return max((BASE_GATE_ROWS, *(len(law.gates) for law in self.channel_laws)))
