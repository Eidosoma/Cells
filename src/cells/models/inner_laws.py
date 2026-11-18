"""Declared laws of resolved_pump_tissue@3, and the value-free structure of a definition.

Design: docs/INNER_MODEL_V4_DESIGN.md §7.1 (a law's declaration) and §7.4 (the interface for
D176's round). One frozen declaration per law ID, with a fixed registry code:

* channel laws (today's five, codes 0-4: core/surface_pump_v3_spec.LAW_CODES). A new law takes
  the next free code; no code is reused;
* the junction conductance law (every junction declares it today);
* the two pump laws, on today's maintained fuel kind.

The kernels stay where they are, unchanged: laws/channels/voltage_gates.py, potassium_channels.py,
sodium_channels.py, junction_gate.py, kinetic_pump.py and calcium_atpase.py. Older families
import those modules and their shared dispatchers (sodium_channels.kinetics and opening), so a
declaration only points at a law's own kernel. Each opening keeps today's operation order, which
per-law dispatch needs to stay bitwise (probe P2 of the note): Kv1.5 m h, Kir2.1 (m h) h,
NaV1.2 m^3 h.

Each declaration is an instance of the law template (registry/laws.py; docs/CORE_SEAMS_DESIGN.md
§8.1), hosted by @3 itself (HOST), and registers on the law registry's BUILTIN here, its home until
each law moves to its own module (§8.2). The tables below keep today's names. @3 finds its laws in
the active law registry by interface and host: InnerStructure validates against it (§8.3).

InnerStructure is what one definition declares, as Python values with no parameter value in it:
the inner model builds one implementation per structure (models/surface_pump_v3.implementation),
which closes over the structure and never over a value (P5).
"""

from dataclasses import dataclass
from types import MappingProxyType

from cells.definitions.kinetic_pump_spec import METABOLISM_ID
from cells.definitions.surface_pump_v3_spec import (
    DEFAULT_JUNCTION_HEAT,
    KIR2P1_LAW_ID,
    KLEAK_LAW_ID,
    KV1P5_LAW_ID,
    MODEL_ID,
    NALEAK_LAW_ID,
    NAV1P2_LAW_ID,
    TRAPEZOID_JUNCTION_HEAT,
)
from cells.laws.channels import potassium_channels, sodium_channels, voltage_gates
from cells.laws.junctions import junction_gate
from cells.laws.pumps import calcium_atpase, kinetic_pump
from cells.registry import kind_registry
from cells.registry import laws as law_registry
from cells.registry.kind_registry import qualified
from cells.registry.laws import ChannelLaw, JunctionLaw, PumpLaw, RouteLaw  # noqa: F401

HOST = qualified(MODEL_ID)  # @3 runs its own populations' laws (registry/laws.py: `host`).
MAINTAINED_FUEL_ID = METABOLISM_ID  # maintained_chemical_reservoirs@1, today's pumps' fuel kind.
MEMBRANE_ROUTE_LAW_ID = "constant_field@1"  # The passive membrane and junction route law.
FACE_ROUTE_LAW_ID = "logmean_electrodiffusion@1"
BASE_GATE_ROWS = 2  # Today's channel gate rows; a law with more gates adds rows where declared.
# Reference RK4 step bounds of the resolved channel family (surface_kinetic.check_steps): 2.5 us
# with NaV1.2, 25 us with Kv1.5 or Kir2.1. surface_pump_v3's RK4_*_STEP are these.
RK4_SODIUM_STEP_S = 2.5e-6
RK4_POTASSIUM_STEP_S = 25e-6
# Heat bookings (docs/CORE_SEAMS_DESIGN.md §6.1): the tableau books every mover class by default
# and is never listed; @3's own mover classes, and the bookings each admits beyond it (the
# trapezoid for channels, as ruled there, and for junctions, today's junction_heat_booking). A
# declared kind's routes are the class its namespaced ID names, admitting its heat_bookings.
TABLEAU_HEAT_BOOKING = DEFAULT_JUNCTION_HEAT
CHANNELS, JUNCTIONS = "channels", "junctions"
OWN_HEAT_BOOKINGS = MappingProxyType(
    {CHANNELS: (TRAPEZOID_JUNCTION_HEAT,), JUNCTIONS: (TRAPEZOID_JUNCTION_HEAT,)}
)


def _open_mh(gates, *, xp):
    return gates[..., 0, :] * gates[..., 1, :]


def _open_mh2(gates, *, xp):
    m, h = gates[..., 0, :], gates[..., 1, :]
    return m * h * h  # (m h) h, today's order (potassium_channels.opening).


def _open_m3h(gates, *, xp):
    return gates[..., 0, :] ** 3 * gates[..., 1, :]  # Today's order (sodium_channels.opening).


def _kv1p5_kinetics(voltage, *, xp):
    return voltage_gates.kinetics(voltage, xp=xp)


def _kir2p1_kinetics(voltage, *, xp):
    return potassium_channels.kir2p1_kinetics(voltage, xp=xp)


def _nav1p2_kinetics(voltage, *, xp):
    return sodium_channels.nav1p2_kinetics(voltage, xp=xp)


_DOMAIN = voltage_gates.VOLTAGE_DOMAIN_V
CHANNEL_LAWS = MappingProxyType(
    {
        law.law_id: law_registry.BUILTIN.register(law)
        for law in (
            ChannelLaw(
                KV1P5_LAW_ID,
                0,
                ("m", "h"),
                (("K", 1, 1.0),),
                _DOMAIN,
                RK4_POTASSIUM_STEP_S,
                _kv1p5_kinetics,
                _open_mh,
                host=HOST,
            ),
            ChannelLaw(
                KIR2P1_LAW_ID,
                1,
                ("m", "h"),
                (("K", 1, 1.0),),
                _DOMAIN,
                RK4_POTASSIUM_STEP_S,
                _kir2p1_kinetics,
                _open_mh2,
                host=HOST,
            ),
            ChannelLaw(
                NAV1P2_LAW_ID,
                2,
                ("m", "h"),
                (("Na", 1, 1.0),),
                _DOMAIN,
                RK4_SODIUM_STEP_S,
                _nav1p2_kinetics,
                _open_m3h,
                host=HOST,
            ),
            ChannelLaw(KLEAK_LAW_ID, 3, (), (("K", 1, 1.0),), _DOMAIN, None, host=HOST),
            ChannelLaw(NALEAK_LAW_ID, 4, (), (("Na", 1, 1.0),), _DOMAIN, None, host=HOST),
        )
    }
)
JUNCTION_LAWS = MappingProxyType(
    {
        junction_gate.LAW_ID: law_registry.BUILTIN.register(
            JunctionLaw(
                junction_gate.LAW_ID,
                True,
                junction_gate.kinetics,
                junction_gate.rhs,
                junction_gate.domain_valid,
                junction_gate.MAX_ABS_VOLTAGE_V,
                host=HOST,
            )
        )
    }
)
PUMP_LAWS = MappingProxyType(
    {
        kinetic_pump.LAW_ID: law_registry.BUILTIN.register(
            PumpLaw(
                kinetic_pump.LAW_ID,
                (
                    ("sodium", kinetic_pump.SODIUM_PER_CYCLE),
                    ("potassium", kinetic_pump.POTASSIUM_PER_CYCLE),
                ),
                (MAINTAINED_FUEL_ID,),
                kinetic_pump.kinetics,
                kinetic_pump.domain_valid,
                host=HOST,
            )
        ),
        calcium_atpase.LAW_ID: law_registry.BUILTIN.register(
            PumpLaw(
                calcium_atpase.LAW_ID,
                (("calcium", calcium_atpase.CALCIUM_PER_CYCLE),),
                (MAINTAINED_FUEL_ID,),
                calcium_atpase.kinetics,
                calcium_atpase.domain_valid,
                host=HOST,
            )
        ),
    }
)


# The passive route laws every membrane, junction and face declares (provenance for the run view,
# D154): moved unchanged into @3 with its families (parity, not calibrated); `basis` says what
# each is, in its own sources' words.
ROUTE_LAWS = MappingProxyType(
    {
        MEMBRANE_ROUTE_LAW_ID: law_registry.BUILTIN.register(
            RouteLaw(
                MEMBRANE_ROUTE_LAW_ID,
                ("membrane", "junction"),
                "the Goldman-Hodgkin-Katz constant-field flux of each permeant species "
                "(coupling/selective.selective_flux)",
                host=HOST,
            )
        ),
        FACE_ROUTE_LAW_ID: law_registry.BUILTIN.register(
            RouteLaw(
                FACE_ROUTE_LAW_ID,
                ("face",),
                "Cells' own discrete electrodiffusion between two well-mixed outside nodes: the "
                "Nernst-Planck flux at the species' logarithmic-mean concentration "
                "(docs/SPATIAL_EXTRACELLULAR_SPEC.md: a design, not a reproduction of a paper)",
                host=HOST,
            )
        ),
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

    def __post_init__(self):
        ids = [kind_id for kind_id, _ in self.kinds]
        if ids != sorted(set(ids)):
            raise ValueError("Declared kinds must be distinct and in canonical (sorted ID) order")
        problems = heat_booking_errors(self.heat_bookings, ids, self.junction_heat_booking)
        if problems:
            raise ValueError("Heat bookings of an inner structure: " + "; ".join(problems))
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
