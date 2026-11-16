"""Declared laws of resolved_pump_tissue@3, and the value-free structure of a definition.

Design: docs/INNER_MODEL_V4_DESIGN.md §7.1 (a law's declaration) and §7.4 (the interface for
D176's round). One frozen declaration per law ID, with a fixed registry code:

* channel laws (today's five, codes 0-4: core/surface_pump_v3_spec.LAW_CODES). A new law takes
  the next free code; no code is reused;
* the junction conductance law (every junction declares it today);
* the two pump laws, on today's maintained fuel kind.

The kernels stay where they are, unchanged: processes/voltage_gates.py, potassium_channels.py,
sodium_channels.py, junction_gate.py, kinetic_pump.py and calcium_atpase.py. Older families
import those modules and their shared dispatchers (sodium_channels.kinetics and opening), so a
declaration only points at a law's own kernel. Each opening keeps today's operation order, which
per-law dispatch needs to stay bitwise (probe P2 of the note): Kv1.5 m h, Kir2.1 (m h) h,
NaV1.2 m^3 h.

InnerStructure is what one definition declares, as Python values with no parameter value in it:
the inner model builds one implementation per structure (models/surface_pump_v3.implementation),
which closes over the structure and never over a value (P5).
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Callable

from cells.core.kinetic_finite_spec import METABOLISM_ID
from cells.core.surface_pump_v3_spec import (
    KIR2P1_LAW_ID,
    KLEAK_LAW_ID,
    KV1P5_LAW_ID,
    NALEAK_LAW_ID,
    NAV1P2_LAW_ID,
)
from cells.processes import (
    calcium_atpase,
    junction_gate,
    kinetic_pump,
    potassium_channels,
    sodium_channels,
    voltage_gates,
)

MAINTAINED_FUEL_ID = METABOLISM_ID  # maintained_chemical_reservoirs@1, today's pumps' fuel kind.
MEMBRANE_ROUTE_LAW_ID = "constant_field@1"  # The passive membrane and junction route law.
FACE_ROUTE_LAW_ID = "logmean_electrodiffusion@1"
BASE_GATE_ROWS = 2  # Today's channel gate rows; a law with more gates adds rows where declared.
# Reference RK4 step bounds of the resolved channel family (surface_kinetic.check_steps): 2.5 us
# with NaV1.2, 25 us with Kv1.5 or Kir2.1. surface_pump_v3's RK4_*_STEP are these.
RK4_SODIUM_STEP_S = 2.5e-6
RK4_POTASSIUM_STEP_S = 25e-6


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


@dataclass(frozen=True)
class ChannelLaw:
    """A channel law (§7.1): gates relax by the exponential stage update; leaks have none."""

    law_id: str
    code: int
    gates: tuple[str, ...]
    permeant: tuple[tuple[str, int, float], ...]  # (species, valence, relative permeability)
    voltage_domain_V: tuple[float, float]
    rk4_step_s: float | None  # The reference RK4 step bound; None for gate-free laws.
    kinetics: Callable | None = None  # (voltage, *, xp) -> (target, tau), [..., gates, n].
    opening: Callable | None = None  # (gates, *, xp) -> [..., n]; None: always open.
    stage_term: str = "constant_field_slope"  # Today's membrane_rate term at the actual opening.
    reads: tuple = ()  # Stage reads (B4): none for today's laws.
    loop_term: object = None
    provenance: str = "parity"  # Moved from the catalogue; moving is not calibrating.
    # The four optional fields of a law that stands in for something (D175, B8): reserved.
    represents: object = None
    preserves: object = None
    supports: object = None
    qualified: object = None

    @property
    def gated(self):
        return bool(self.gates)


@dataclass(frozen=True)
class JunctionLaw:
    """A junction conductance law; a gated one carries junction_gate state."""

    law_id: str
    gated: bool
    kinetics: Callable  # (voltage, parameters, *, xp) -> junction_gate.Rates
    rhs: Callable
    domain_valid: Callable
    max_abs_voltage_V: float
    provenance: str = "parity"


@dataclass(frozen=True)
class PumpLaw:
    """A pump law on a patch, its moved rows by role (inward-positive per cycle) and fuel."""

    law_id: str
    moves: tuple[tuple[str, int], ...]
    fuel_kinds: tuple[str, ...]
    kinetics: Callable
    domain_valid: Callable
    provenance: str = "parity"


_DOMAIN = voltage_gates.VOLTAGE_DOMAIN_V
CHANNEL_LAWS = MappingProxyType(
    {
        law.law_id: law
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
            ),
            ChannelLaw(KLEAK_LAW_ID, 3, (), (("K", 1, 1.0),), _DOMAIN, None),
            ChannelLaw(NALEAK_LAW_ID, 4, (), (("Na", 1, 1.0),), _DOMAIN, None),
        )
    }
)
JUNCTION_LAWS = MappingProxyType(
    {
        junction_gate.LAW_ID: JunctionLaw(
            junction_gate.LAW_ID,
            True,
            junction_gate.kinetics,
            junction_gate.rhs,
            junction_gate.domain_valid,
            junction_gate.MAX_ABS_VOLTAGE_V,
        )
    }
)
PUMP_LAWS = MappingProxyType(
    {
        kinetic_pump.LAW_ID: PumpLaw(
            kinetic_pump.LAW_ID,
            (
                ("sodium", kinetic_pump.SODIUM_PER_CYCLE),
                ("potassium", kinetic_pump.POTASSIUM_PER_CYCLE),
            ),
            (MAINTAINED_FUEL_ID,),
            kinetic_pump.kinetics,
            kinetic_pump.domain_valid,
        ),
        calcium_atpase.LAW_ID: PumpLaw(
            calcium_atpase.LAW_ID,
            (("calcium", calcium_atpase.CALCIUM_PER_CYCLE),),
            (MAINTAINED_FUEL_ID,),
            calcium_atpase.kinetics,
            calcium_atpase.domain_valid,
        ),
    }
)


@dataclass(frozen=True)
class RouteLaw:
    """A passive route law: the hosts it serves, what it is, and its provenance (§7.1)."""

    law_id: str
    hosts: tuple[str, ...]
    basis: str
    provenance: str = "parity"


# The passive route laws every membrane, junction and face declares (provenance for the run view,
# D154): moved unchanged into @3 with its families (parity, not calibrated); `basis` says what
# each is, in its own sources' words.
ROUTE_LAWS = MappingProxyType(
    {
        MEMBRANE_ROUTE_LAW_ID: RouteLaw(
            MEMBRANE_ROUTE_LAW_ID,
            ("membrane", "junction"),
            "the Goldman-Hodgkin-Katz constant-field flux of each permeant species "
            "(coupling/selective.selective_flux)",
        ),
        FACE_ROUTE_LAW_ID: RouteLaw(
            FACE_ROUTE_LAW_ID,
            ("face",),
            "Cells' own discrete electrodiffusion between two well-mixed outside nodes: the "
            "Nernst-Planck flux at the species' logarithmic-mean concentration "
            "(docs/SPATIAL_EXTRACELLULAR_SPEC.md: a design, not a reproduction of a paper)",
        ),
    }
)


def channel_codes():
    """{law ID: registry code} of every registered channel law."""
    return {law_id: law.code for law_id, law in CHANNEL_LAWS.items()}


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

    def __post_init__(self):
        ids = [kind_id for kind_id, _ in self.kinds]
        if ids != sorted(set(ids)):
            raise ValueError("Declared kinds must be distinct and in canonical (sorted ID) order")
        unknown = [law for law in self.declared_channel_laws if law not in CHANNEL_LAWS]
        unknown += [law for law in self.junction_laws if law not in JUNCTION_LAWS]
        unknown += [law for law in self.pump_laws if law not in PUMP_LAWS]
        if unknown:
            raise ValueError("Undeclared laws in an inner structure: " + ", ".join(unknown))
        order = tuple(sorted(self.declared_channel_laws, key=lambda law: CHANNEL_LAWS[law].code))
        if order != self.declared_channel_laws or len(set(order)) != len(order):
            raise ValueError("Declared channel laws must be distinct and in registry-code order")

    @property
    def channel_laws(self):
        """The declarations of the declared channel laws, in code order."""
        return tuple(CHANNEL_LAWS[law] for law in self.declared_channel_laws)

    @property
    def gate_rows(self):
        """Channel gate rows: today's two, or more where a declared law has more gates."""
        return max((BASE_GATE_ROWS, *(len(law.gates) for law in self.channel_laws)))
