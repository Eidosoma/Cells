"""The three interfaces of version 2, on seam F's law template (registry/laws.py, `Law`).

Each is a `cells` interface the family declares in its row of the static model table, so a
declaration of one is a frozen record of its type, registered from its home with the registry's
public call, `law_registry.BUILTIN.register(...)`, as one direct call with its ID as a literal
(registry/declarations.py reads that call).

- `cells.reaction_law@1` (ReactionLaw): a step's kinetics on the event-pair contract. It supplies
  θ⁺, the reactants' encounter at the firing state, and the locus extent on the common state. It
  never supplies a reverse rate: the kernel derives every reverse from the one free energy F.
- `cells.rate_factor_law@2` (RateFactorLaw): one factor per step pair, evaluated on the pair's
  common state m only, so it is the same for both directions (@1's cells.rate_factor_law@1 is per
  direction and per type, and admits the single-event form; this major does not).
- `cells.free_energy_term@1` (FreeEnergyTerm): an exact term of F, a function of the counts, with
  its change under a step computed incrementally. The ideal term is folded into mass action's
  reverse (k⁻ = k_f exp(Σ ν μ°) and the products' activities); an excess term enters the reverse
  rate as exp(F_ex(n) − F_ex(n − ν)).

**U2 (D199), structurally.** A law of these interfaces cannot express a driven rate: reaction laws
give only θ⁺ and the extent on m, rate factors only a factor on m, and terms only a state function.
A declaration whose energy role is not passive must name a declared source of free energy, and OL1
declares none (sources come with OL4), so every such declaration is refused at registration. The
kernel's check (balance.py) then verifies, on its own probe and on each world, that the rates keep
ln a⁺ − ln a⁻ = −ΔF + w.
"""

from dataclasses import dataclass
from typing import Callable, ClassVar

from cells.models.assembly_lineages_v2 import (
    FREE_ENERGY_INTERFACE,
    GEOMETRY_INTERFACE,
    HAZARD_INTERFACE,
    MODEL_ID,
    OPERATOR_INTERFACE,
    POPULATION_INTERFACE,
    RATE_FACTOR_INTERFACE,
    REACTION_INTERFACE,
    REPRESENTATION_INTERFACE,
)
from cells.modules import FamilyOperator, Law
from cells.registry import laws as law_registry

SPLITS = ("encounter",)  # θ⁺ the reactants' encounter, the reverse from F (§2.1's default split).
PARTS = ("ideal", "excess")
CATALYSING = ("membrane",)  # OL1: only the assembly's condensed phase catalyses (§0.2a).
# A reaction law's extent: `locus` is OL1's (the locus's X, or membrane_kinetics on m); `geometric`
# is OL2's encounter on m from the world's geometry (§0.2d item 2), which the kernel supplies.
EXTENTS = ("locus", "geometric")


def _host_and_role(law, roles=("passive",)):
    out = []
    if law_registry.qualified(law.host) != law_registry.qualified(MODEL_ID):
        out.append(f"a law of {type(law).interface} is hosted by {MODEL_ID}")
    role = getattr(law, "energy_role", "passive")
    if role not in roles:
        out.append(f"its energy_role is one of {', '.join(roles)}")
    if role != "passive" or getattr(law, "energy_source", None) is not None:
        out.append(
            "a driven law names a declared source of free energy, and none is declared in this "
            "family yet (OL4): refused (U2, D199)"
        )
    return out


def _callables(law, names):
    return [f"its {name} is callable" for name in names if not callable(getattr(law, name))]


def _limit_errors(law):
    """OL6's hook (H1): a declared limit is callable and states its formulas."""
    if law.limit is None:
        return [] if law.limit_formulas is None else ["its limit_formulas come with a limit"]
    out = [] if callable(law.limit) else ["its limit is callable"]
    if not isinstance(law.limit_formulas, dict) or not law.limit_formulas:
        out.append("its limit states its formulas in words and symbols")
    return out


@dataclass(frozen=True)
class ReactionLaw(Law):
    """cells.reaction_law@1: a step's kinetics (θ⁺ and the locus extent); never a reverse rate."""

    energy_role: str
    energy_source: object  # None: OL1 declares no source of free energy.
    split: str
    log_direction: Callable  # The kernel of one direction's log rate (mass_action.py).
    formulas: dict
    # OL2 (defaults keep OL1's laws as they are): the step's rate-constant key, or a mapping from
    # the world's exchange_encounter token to it; and the extent's kind (EXTENTS).
    rate_key: object = "forward_rate_per_s"
    extent: str = "locus"
    # OL6 (H1, D304): the law's large-count limit for cells.assembly_representation.rate_equations@1, or None (refused
    # there); and its formulas, written only into that representation's records.
    limit: Callable | None = None
    limit_formulas: dict | None = None

    interface: ClassVar[str] = REACTION_INTERFACE

    def errors(self):
        out = super().errors() + _host_and_role(self) + _callables(self, ("log_direction",))
        if self.split not in SPLITS:
            out.append(f"its split is one of {', '.join(SPLITS)}")
        if not isinstance(self.formulas, dict) or not self.formulas:
            out.append("its formulas state its rates in words and symbols")
        keys = self.rate_key.values() if isinstance(self.rate_key, dict) else [self.rate_key]
        if not keys or not all(isinstance(k, str) and k for k in keys):
            out.append("its rate key is a name, or a mapping from encounter tokens to names")
        if self.extent not in EXTENTS:
            out.append(f"its extent is one of {', '.join(EXTENTS)}")
        out += _limit_errors(self)
        return out


@dataclass(frozen=True)
class GeometryLaw(Law):
    """cells.assembly_geometry@1: a geometry kind of the assembly (OL2; §0.2c rules 4, 5 and 8).

    It reads the membrane's footprint W(n) = Σ n_i k_i in quanta (an exact integer), gives the
    encounter extents on m to the geometric reaction laws, the floor's test, and its own part of F:
    a constant per living vesicle (the closure cost), so it changes no rate."""

    data: tuple  # The keys of its world block beside `law`.
    parse_data: Callable  # (raw block, world) -> parsed data; ConfigError on refusal.
    data_to_dict: Callable
    formulas: dict

    interface: ClassVar[str] = GEOMETRY_INTERFACE

    def errors(self):
        out = super().errors() + _callables(self, ("parse_data", "data_to_dict"))
        if law_registry.qualified(self.host) != law_registry.qualified(MODEL_ID):
            out.append(f"a law of {type(self).interface} is hosted by {MODEL_ID}")
        if not isinstance(self.formulas, dict) or not self.formulas:
            out.append("its formulas state its quantities in words and symbols")
        return out


@dataclass(frozen=True)
class PopulationStructure(Law):
    """cells.population_structure@1: how a world holds several assemblies (OL2 milestone 3; §0.2c
    rules 13–15): its slots, its founders and the selection map of its one world-level SSA."""

    data: tuple  # The keys of its world block beside `structure`.
    parse_data: Callable  # (raw block, world) -> parsed data; ConfigError on refusal.
    data_to_dict: Callable
    formulas: dict

    interface: ClassVar[str] = POPULATION_INTERFACE

    def errors(self):
        out = super().errors() + _callables(self, ("parse_data", "data_to_dict"))
        if law_registry.qualified(self.host) != law_registry.qualified(MODEL_ID):
            out.append(f"a law of {type(self).interface} is hosted by {MODEL_ID}")
        if not isinstance(self.formulas, dict) or not self.formulas:
            out.append("its formulas state its quantities in words and symbols")
        return out


@dataclass(frozen=True)
class RateFactorLaw(Law):
    """cells.rate_factor_law@2: one factor per step pair, on the pair's common state m."""

    energy_role: str
    energy_source: object
    evaluated_on: str  # "common_state": the only value; the factor never sees a direction.
    catalysing_phases: tuple
    data: tuple  # The world fields it reads (its rate_factor block's keys beside `law`).
    parse_data: Callable  # (raw block, world) -> parsed data; ConfigError on refusal.
    data_to_dict: Callable
    layout: Callable  # (parsed data, world, step capacity, place capacity) -> NumPy arrays.
    state: Callable  # (counts, layout, xp) -> its incremental state, exactly.
    update: Callable  # (state, layout, places, delta, xp) -> the state after a step.
    log_factor: Callable  # (state, layout, view, xp) -> ln g at each step's common state.
    formulas: dict
    # OL6 (H1, D304): the law's large-count limit for cells.assembly_representation.rate_equations@1, or None (refused
    # there); and its formulas, written only into that representation's records.
    limit: Callable | None = None
    limit_formulas: dict | None = None

    interface: ClassVar[str] = RATE_FACTOR_INTERFACE

    def errors(self):
        kernels = ("parse_data", "data_to_dict", "layout", "state", "update", "log_factor")
        out = super().errors() + _host_and_role(self) + _callables(self, kernels)
        if self.evaluated_on != "common_state":
            out.append("a rate factor of this major is evaluated on the common state m only")
        if not self.catalysing_phases or set(self.catalysing_phases) - set(CATALYSING):
            out.append(
                f"its catalysing phases are among {', '.join(CATALYSING)} (OL1: the condensed "
                "phase only; a dilute phase's fraction would have to include the solvent)"
            )
        out += _limit_errors(self)
        return out


@dataclass(frozen=True)
class FreeEnergyTerm(Law):
    """cells.free_energy_term@1: an exact term of F (k_BT), with its incremental change."""

    part: str  # "ideal" (folded into mass action's reverse) or "excess" (exp of its change).
    phases: tuple  # The phases it reads.
    data: tuple  # The keys of its free_energy entry beside `law`.
    parse_data: Callable  # (raw entry, world) -> parsed data.
    data_to_dict: Callable
    layout: Callable  # (parsed data, world, place capacity) -> NumPy arrays (or ()).
    state: Callable  # (counts, totals, layout, xp) -> its incremental state ((): none).
    update: Callable  # (state, layout, places, delta, xp) -> the state after a step.
    value: Callable  # Host: F_term(counts) exactly, for the ledger and the check.
    delta: Callable  # (state, layout, view, delta, xp) -> F_term(n + delta) - F_term(n), per step.
    formulas: dict
    # OL6 (H1, D304): the law's large-count limit for cells.assembly_representation.rate_equations@1, or None (refused
    # there); and its formulas, written only into that representation's records.
    limit: Callable | None = None
    limit_formulas: dict | None = None

    interface: ClassVar[str] = FREE_ENERGY_INTERFACE

    def errors(self):
        kernels = ("parse_data", "data_to_dict", "layout", "state", "update", "value", "delta")
        out = super().errors() + _host_and_role(self) + _callables(self, kernels)
        if self.part not in PARTS:
            out.append(f"its part is one of {', '.join(PARTS)}")
        if not self.phases:
            out.append("it names the phases it reads")
        out += _limit_errors(self)
        return out


HAZARD_STREAMS = ("pore",)  # FR-31: the stream domain a hazard's clock draws on (streams.py)
HAZARD_OUTCOMES = ("lysis",)  # FR-31 Phase A: rupture only, through the existing release
HAZARD_READS = ("tension", "area", "temperature")


@dataclass(frozen=True)
class AssemblyHazard(Law):
    """cells.assembly_hazard@1: a vesicle's hazard on a clock (FR-31, Phase A;
    docs/VESICLE_PORES_DESIGN.md §3.1, docs/VESICLE_PORES_LAWS.md §5).

    It reads the vesicle's state (its tension, its area and the world's temperature), gives a rate
    per vesicle, and names its stream and its outcome. The hazard is passive: its event pair keeps
    ln a⁺ − ln a⁻ = −ΔF + w, w being the work of a declared source (the tension's hold), never its
    own, so U2's guard applies to it as to the family's other laws."""

    energy_role: str
    energy_source: object
    reads: tuple  # what the rate reads, among HAZARD_READS
    stream: str  # its clock's stream domain, one of HAZARD_STREAMS
    outcome: str  # what a firing does, one of HAZARD_OUTCOMES
    data: tuple  # The keys of its world block beside `law`.
    parse_data: Callable  # (raw block, world) -> parsed data; ConfigError on refusal.
    data_to_dict: Callable
    formulas: dict

    interface: ClassVar[str] = HAZARD_INTERFACE

    def errors(self):
        out = super().errors() + _host_and_role(self)
        out += _callables(self, ("parse_data", "data_to_dict"))
        if not self.reads or set(self.reads) - set(HAZARD_READS):
            out.append(f"it reads among {', '.join(HAZARD_READS)}")
        if self.stream not in HAZARD_STREAMS:
            out.append(f"its stream is one of {', '.join(HAZARD_STREAMS)}")
        if self.outcome not in HAZARD_OUTCOMES:
            out.append(f"its outcome is one of {', '.join(HAZARD_OUTCOMES)}")
        if not isinstance(self.formulas, dict) or not self.formulas:
            out.append("its formulas state its rate in words and symbols")
        return out


@dataclass(frozen=True)
class AssemblyOperator(FamilyOperator):
    """cells.assembly_operator@1: an operator acting on the family's lineages at scheduled events
    (OL3: shear fission) or at a state's trigger (OL6 S7: the size-threshold division). Its fields
    are what a run record states of it, as @1's lineage operators' are: what it reads and writes,
    its energy role, its rules, its streams and its contract in words."""

    reads: str
    writes: str
    energy_role: str
    rules: dict
    stream: str
    contract: dict

    interface: ClassVar[str] = OPERATOR_INTERFACE

    def errors(self):
        out = super().errors()
        if law_registry.qualified(self.host) != law_registry.qualified(MODEL_ID):
            out.append(f"an assembly operator is hosted by {MODEL_ID}")
        for name in ("reads", "writes", "energy_role", "stream"):
            if not (isinstance(getattr(self, name), str) and getattr(self, name)):
                out.append(f"its {name} is stated")
        if not (isinstance(self.rules, dict) and isinstance(self.contract, dict)):
            out.append("its rules and its contract are mappings")
        return out

    def record(self):
        """The declaration as a run record states it, in @1's form (lineage_operators.py)."""
        from cells.models.assembly_lineages.lineage_operators import LineageOperator

        return LineageOperator.record(self)


@dataclass(frozen=True)
class AssemblyRepresentation(Law):
    """cells.assembly_representation@1: a declared level of detail of the family's worlds (OL6,
    D304; docs/OL6_DETERMINISTIC_REPRESENTATION_DESIGN.md §1.1). The first instance of a general
    level-of-detail contract (D299 item 4), in three parts:

    - **what a level declares:** Law's four reserved fields, each required here: `represents` (the
      detailed form it stands in for, its scope and its reduction), `preserves` (what it keeps
      exactly, and what to a tolerance), `supports` (the readouts it answers) and `qualified` (its
      envelope, its error budget and the record that qualified it); plus the numerical methods it
      admits, its refused readouts and its lifecycle;
    - **what a pair agrees on** (`pair`): the quantities both levels expose at the interface, the
      same world id, the same declared laws, units and streams for what stays stochastic;
    - **how a pair is qualified** (`qualified`): a registered protocol, run at its tag by an
      independent checker, against the detailed form where both run.

    A world chooses the level at definition, never at run time; the detailed form is the default."""

    methods: tuple  # the numerical methods it admits (each declared apart from the representation)
    readouts: tuple  # what can be asked of it
    refused_readouts: tuple  # what it refuses by name
    statuses: tuple  # its own lifecycle (never the detailed form's tables)
    pair: dict  # what the two levels of one world agree on
    formulas: dict

    interface: ClassVar[str] = REPRESENTATION_INTERFACE
    LEVEL_OF_DETAIL: ClassVar[bool] = True  # D175's fields' first consumer (D304)

    def errors(self):
        out = super().errors()
        if law_registry.qualified(self.host) != law_registry.qualified(MODEL_ID):
            out.append(f"a law of {type(self).interface} is hosted by {MODEL_ID}")
        for name in ("represents", "preserves", "supports", "qualified"):
            if getattr(self, name) is None:
                out.append(f"a level of detail declares `{name}` (Law's reserved field)")
        for name in ("methods", "readouts", "refused_readouts", "statuses"):
            if not isinstance(getattr(self, name), tuple) or not getattr(self, name):
                out.append(f"its {name} is a non-empty tuple")
        if not isinstance(self.pair, dict) or not self.pair:
            out.append("its pair states what the two levels agree on")
        if not isinstance(self.formulas, dict) or not self.formulas:
            out.append("its formulas state its equations in words and symbols")
        return out
