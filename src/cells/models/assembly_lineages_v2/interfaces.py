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
    MODEL_ID,
    RATE_FACTOR_INTERFACE,
    REACTION_INTERFACE,
)
from cells.modules import Law
from cells.registry import laws as law_registry

SPLITS = ("encounter",)  # θ⁺ the reactants' encounter, the reverse from F (§2.1's default split).
PARTS = ("ideal", "excess")
CATALYSING = ("membrane",)  # OL1: only the assembly's condensed phase catalyses (§0.2a).


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

    interface: ClassVar[str] = REACTION_INTERFACE

    def errors(self):
        out = super().errors() + _host_and_role(self) + _callables(self, ("log_direction",))
        if self.split not in SPLITS:
            out.append(f"its split is one of {', '.join(SPLITS)}")
        if not isinstance(self.formulas, dict) or not self.formulas:
            out.append("its formulas state its rates in words and symbols")
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
