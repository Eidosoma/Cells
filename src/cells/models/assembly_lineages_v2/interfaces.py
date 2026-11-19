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
    MODEL_ID,
    OPERATOR_INTERFACE,
    POPULATION_INTERFACE,
    RATE_FACTOR_INTERFACE,
    REACTION_INTERFACE,
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

    interface: ClassVar[str] = FREE_ENERGY_INTERFACE

    def errors(self):
        kernels = ("parse_data", "data_to_dict", "layout", "state", "update", "value", "delta")
        out = super().errors() + _host_and_role(self) + _callables(self, kernels)
        if self.part not in PARTS:
            out.append(f"its part is one of {', '.join(PARTS)}")
        if not self.phases:
            out.append("it names the phases it reads")
        return out


@dataclass(frozen=True)
class AssemblyOperator(FamilyOperator):
    """cells.assembly_operator@1: an operator acting on the family's lineages at scheduled events
    (OL3: shear fission). Its fields are what a run record states of it, as @1's lineage
    operators' are: what it reads and writes, its energy role, its rules, its streams and its
    contract in words."""

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
