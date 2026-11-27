"""Operator cells.operator.species_regulated_availability@1: coupling out of the inventory (D155 item 1, D156).

docs/INVENTORY_COUPLING_DESIGN.md (accepted 14 November 2026; rulings in §6.3, milestone-1 notes in
§7). A species amount on @3's cell rows sets @3's availability of a declared target through the
contract's CONTROL_FACTORS, either at once (an instantaneous Hill factor) or through a regulatory
state, a two-state fraction per cell with declared on- and off-rates. Version 1 targets @3's
junction and channel-population availabilities; the channel target was admitted when milestone 1's
probe P1 matched its path through control_view and held_schedules to the scheduled availability,
bit for bit (ruling 12; its acceptance into scope is the lead's).

Declaration (§1.6): `species`, the rows the operator reads (a read-only list: any species of the
world, ions included, with D150's identity form, never written; ruling 1); `states`, each with its
law cells.regulation.hill_regulated_two_state@1, its cells, its inputs (Hill factors of species read in the same
cell, which multiply), on_rate_per_s, off_rate_per_s, initial (s0: one value for every cell of the
state, or an object naming each of its cells once, a cell's prior condition) and crossing_level
(null or a level in [0, 1]); `couplings`, each with a target ({operator: "inner", control, ids,
side}), a source ({"species": id} or {"state": id}), a law and basal. Every key is explicit. The
experiment's `regulatory_writes` set a (state, cell) at the start of the step leaving their time,
0 <= t < end: a write at 0 is applied at the first step start, before any later event.

Laws (§1.3, §1.5):
* instantaneous: hill_activation x^n/(K^n + x^n) or hill_inhibition K^n/(K^n + x^n) of the
  concentration c = n/V in the target's own cell, at the declared volume (processes/hill_factors,
  the expression of cells.operator.local_species_reactions@1); its source must be a neutral species with no
  membrane, junction or channel route, a row @3's step does not move, so the factor held through
  @3's step is exact there (§1.4);
* through a state: state_fraction s or state_complement 1 - s, with
  ds/dt = k_on u (1 - s) - k_off s, u the product of the state's input factors; each half-step is
  the exact solution with u frozen at the half-step's start (s' = s + (k_on u (1 - s) - k_off s) h
  phi(lambda h), lambda = k_on u + k_off, phi(x) = (1 - e^-x)/x), so s stays in [0, 1] in exact
  arithmetic and a value outside it is refused, never clipped. A source @3's step moves (an ion)
  enters only this way: the two halves read it before and after @3's step (Strang, §1.4);
* every coupling: F = b + (1 - b) f with 0 <= b < 1; a switched-off coupling gives exactly 1. A
  junction's side is first, second or both (the product of its two cells' factors; ruling 4). Each
  element takes the product of its routes in declared order; an untargeted element exactly 1.

Parts: an event map at each step start (a crossing record from the state at the step start with the
step counter, then due writes, then the switches copied from their schedule, then the counter), and
a split part (the states' exact half-steps), kept "split" under an RK4 inner step. The factors enter
through the composite's control view, evaluated once per step after the first half-steps and held
through @3's step (§1.1). Statically idle with no state and no coupling (the declaration alone).

Energy (§1.8): nothing is booked. Within a step a factor is a constant in [0, 1] times a scheduled
availability, the same object as a schedule; @3 books every gated flux at the effective value. The
states are kinetic, the integrals and crossings diagnostic: no ledger.

Refused at the definition (§1.11): an undeclared species; an instantaneous source that is charged
or has a route; an identity that differs from a D150 or D152 declaration; more than D150's species
cap; a target operator other than "inner"; a control outside the admitted targets; an unknown or
repeated element; a side on a channel or a junction side other than first, second or both; a law
that does not match its source kind; K <= 0, n <= 0, b outside [0, 1), negative rates, an initial
value or crossing level outside [0, 1], an initial object that does not name each of the state's
cells once; a state with no input; a state source not declared in a cell the coupling reads; a
target, state cell or junction endpoint on a slot replacement@1 replaces; dt (k_on + k_off) > 1
(ruling 5); a switch schedule that does not start at 0 or holds a value other than 0 and 1; a
later switch change off the dt grid or outside 0 < t < end; a write off the dt grid or outside
0 <= t < end, to an undeclared (state, cell), outside [0, 1], or twice at one time; and
(CONFLICTS_VIEW, D150's static-tissue list) every provider and closer of masks, and since version
1.1 every changer of the cell volume but water (species_common.check_volume_changers). At run
time a non-finite or out-of-range state or factor refuses the step (domain_valid, on every step's
end state; also rate_checks, wherever the composite evaluates readouts), as does a stale write
count (in the event map, as replacement's stale generation does).

**cells.operator.species_regulated_availability@2** (B1′; docs/INVENTORY_COUPLING_DESIGN.md §2.1; the lead's
ruling C of 19 November 2026; development, not judged) is @1 plus operator targets, rate routes
to another operator's routable control (contract ROUTABLE_CONTROLS). @1 is unchanged, its
programs included. Every @2 target declares its evaluation:
* an inner target is "step_view", as @1's: held through @3's step.
* an operator target {operator, control, ids, evaluation: "target_half_steps",
  operating_range: [low, high]} names a target law and control of RATE_ROUTES (the turnover's
  turnover_rate by route ID; the reactions' reaction_multiplier by reaction ID, every site; the
  unit producer's unit_assembly_rate by route ID, at its population's cell; templated
  polymerisation's polymerisation_initiation_rate by chain ID, at its pool's cell).
  Its factor, the same F = b + (1 - b) f, is evaluated at the start of each of the target's
  half-steps, from the state that half-step receives (pump_composite._half_step), and multiplies
  the scheduled rate, which is the maximum. Where the target's own half-steps move the route's
  species source in the element's cell (rate_route_sources against the target's half_step_rows),
  the factor is evaluated at the half-step's midpoint instead, after a predictor over h/2, so the
  route stays second order (pump_composite.self_moved_targets; the Lean project's finding). Its
  source, a concentration (mM) or a state's fraction, is held to the declared range at every
  evaluation of an enabled coupling: a value outside refuses the half-step and is never clipped.
The target's elements and their cells come from its declaration (routable_elements), bound
against it. Refused at the binding: an operator target the definition does not declare; an
unknown element; an outside-node element (version 2 routes cell-side elements only, since its
source is read in the element's cell); a state source not declared in an element's cell; and an
element on a replaced slot. The definition refuses a route to a target declared before the
coupling (pump_composite.rate_route_definition_errors).

**@2's population source** (FR-7's part (b); docs/ABUNDANCE_TO_FUNCTION_DESIGN.md §6.2; D218;
development, not judged): a coupling's source may be {"population": channel id}, the population's
absolute density rho = N/A in units per µm² (the lead's ruling: a density, never a count), through
hill_activation or hill_inhibition with half_saturation_per_um2 and hill_coefficient. At the read
rho = a rho_ref: a is @3's current channel_abundance in the coupling's reader view at the control
view (contract R2: a current read at stage inner), and rho_ref is the population's reference density
declared in cells.operator.membrane_entity_state@1, bound host side. Its target is an inner channel target
("step_view"), and its operating range [low, high] is in units per µm², checked where the factor is
evaluated. Units and area change only in writers' half-steps and event maps, so the held factor is
the exact one; an in-step process that writes either is refused. Refused at parsing: a self-source
(the population is one of the target's elements: @3 already scales its conductance by a, so a
factor would count its abundance twice; D218); a count or any half-saturation other than
half_saturation_per_um2; a source population outside the target's cell; a junction target (side
"both" needs a population per endpoint; later, with U1); an operator target (its half-steps receive
no view); an unknown population; a law other than a Hill law. Refused at binding: a population
source without cells.operator.membrane_entity_state@1. A source no declared writer of units or area changes is
reported, not refused: "constant source: the factor cannot vary in this run" (the summary). A
population route's law code is its Hill kind plus POPULATION_OFFSET, so @1's kernels give it
exactly f = 1 (padding); only version 2's population kernel evaluates it, and only from a view.

**@2's site source** (FR-24; docs/OPERATOR_FEATURES_FR23_24_26_DESIGN.md §3; D244; development,
not judged): a coupling's source may be {"site_population": id, "quantity": q}, a site population
of cells.operator.site_occupancy@1 read through its owner's readable quantities (the contract's R3: the composite
passes quantities=, a function of state, and it is called only with a site route). q is
occupied_fraction, theta = B / (B + R), through site_fraction (f = theta), site_complement
(f = 1 - theta) or a Hill law with a dimensionless half_saturation; or occupied_mM or capacity_mM,
B / V or S / V at the element's cell's declared volume (D244's Q2: a concentration, never a count),
through a Hill law with half_saturation_mM. An empty site is an ordinary state: a Hill law of 0
gives activation 0 and inhibition 1. Its targets are @3's channels ("step_view", read at the
control view) and every operator target ("target_half_steps", read at the start of each of the
target's half-steps, whose ranges are checked there), where cells.operator.site_occupancy@1 precedes the target
(refused at the definition otherwise, so both halves read after the owner's first half). The
population and the element share a cell. Its operating range is in the quantity's unit, theta's
inside [0, 1]. A capacity source is a layout constant in version 1, reported in the summary. A
loop through the ligand (the routed target writing the ligand's row at the population's facing
pool) is admitted, as D218 admits a species source's: its timing and range are declared, and each
loop's verification against a reference is a consumer's item. Refused at parsing: an unknown
quantity, a law or a half-saturation that does not match it, a junction target (side both needs a
population per endpoint: later), and a range outside the quantity's; at binding: no
cells.operator.site_occupancy@1, an unknown population, and a population outside the element's cell. Its law
codes are a Hill kind plus SITE_OFFSET and SITE_FRACTION or SITE_COMPLEMENT, so @1's kernels and
the population kernel give it exactly f = 1 (padding); only the site kernel evaluates it.

**Version 1.1, both versions (FR-65's coupling step; docs/TURNOVER_CHANGING_VOLUME_DESIGN.md
§11; D375's Q1 (b), D402).** The cell volume is read current wherever a factor or a state is
evaluated, beside water (cells.operator.ideal_osmosis_linear_compliance_water@1) declared
first, under the same law IDs:
* the states' half-steps read their inputs' concentrations at the view's volume (door S, stage
  split), and so do the routed factors at their targets' half-steps, the midpoint's predictor
  included (the contract's R2′: the composite passes the source its reader view there);
* the control view's factors and ranges read it through R2′'s view, which carries a field only
  where some operator changes it (C1 per field), so a population world's view carries no volume;
* observation reads the row's view, whose volume is the declared array itself without a changer;
* the end's validity check (factors_valid) keeps the declared volume, a reference read: a factor
  lies in [0, 1] at every finite positive volume, so its outcome is the same at both.
Without a changer of the cell volume the coupling receives no view anywhere, and every kernel
reads the declared volume with today's equations (C1). Refused at the definition: a changer of the
cell volume other than water (replacement@2 by name, the shared rule), and a site source in mM
beside any changer, since it reads the declared volume (D244's Q2; check_site_volume); the coupling
declared before water is refused by the composite's order rule (C2). The masks stay fixed, so it
stays refused beside closers, insertion and the lumens. Beside FR-50 phase 2 (D327): @3's own
one-way records beside the coupling and a changer of the cell volume are refused by name until a
world qualifies the three together (check_one_way_records).

**Scope, both versions (D337, D338, D351).** A state's off_rate_per_s is one declared closing rate,
the same at every dose. Reusing one closing rate across doses is provisional, as an indication and
with no change of law: two labs' SK2 recordings contradict one fixed closing rate in opposite
directions. A rise and a washout measured on the same low-dose patch would settle it.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from types import MappingProxyType, SimpleNamespace

import numpy as np

from cells.definitions import pump_composite_spec as composite_spec
from cells.definitions.spec_values import identifier
from cells.definitions.specs import ConfigError, _fields, _number
from cells.laws.reactions import hill_factors
from cells.numerics.clock_instants import ON_THE_GRID, on_grid  # D283's one predicate.
from cells.numerics.species_sums import entity_sum
from cells.operators import membrane_state
from cells.operators import species_common as common
from cells.operators.contract import Operator, Read, carried
from cells.registry import species_registry

LAW_ID = "cells.operator.species_regulated_availability@1"
STEP_ID = "exact_two_state_half_steps@1"
STATE_LAW = "cells.regulation.hill_regulated_two_state@1"
# Admitted targets: @3's junction and channel-population availabilities (the channel after
# milestone 1's probe P1). The leak (membrane) and pump availabilities are later targets.
TARGET_CONTROLS = ("junction", "channel")
SIDES = ("first", "second", "both")
SPECIES_LAWS = hill_factors.KINDS  # hill_activation 1, hill_inhibition 2.
STATE_FRACTION, STATE_COMPLEMENT = 3, 4
STATE_FACTOR_LAWS = {"state_fraction": STATE_FRACTION, "state_complement": STATE_COMPLEMENT}
# Version 2's population source (FR-7's part (b)): a route's law code is its Hill kind plus the
# offset, which @1's kernels treat as padding (f = 1).
POPULATION_OFFSET = 4
POPULATION_LAWS = {name: kind + POPULATION_OFFSET for name, kind in SPECIES_LAWS.items()}
# Version 2's site source (FR-24): a site population of cells.operator.site_occupancy@1, read through its owner's
# readable quantities (R3). Its law codes, which @1's kernels and the population kernel treat as
# padding (f = 1): a Hill kind plus SITE_OFFSET, and the fraction's own two laws.
SITE_LAW = "cells.operator.site_occupancy@1"
SITE_OFFSET = 6
SITE_HILL_LAWS = {name: kind + SITE_OFFSET for name, kind in SPECIES_LAWS.items()}
SITE_FRACTION, SITE_COMPLEMENT = 9, 10
SITE_FRACTION_LAWS = {"site_fraction": SITE_FRACTION, "site_complement": SITE_COMPLEMENT}
# The quantities a site source reads, by their code on the layout: the occupied fraction theta, and
# the occupied amount and the accessible capacity as concentrations in the route's cell (mM, at its
# declared volume; the lead's ruling D244, Q2), each from one of the owner's quantities.
SITE_QUANTITIES = ("occupied_fraction", "occupied_mM", "capacity_mM")
FRACTION_Q, OCCUPIED_Q, CAPACITY_Q = range(3)
SITE_READS = MappingProxyType(
    {
        "occupied_fraction": "site_occupied_fraction",
        "occupied_mM": "site_occupied_fmol",
        "capacity_mM": "site_capacity_fmol",
    }
)
FROM_SPECIES, FROM_STATE = 1, 2
CONTROLS_KEY, WRITES_KEY = "coupling_controls", "regulatory_writes"

STATE_AXES = {
    "regulatory_state": ["regulatory_slot"],  # s in [0, 1], kinetic.
    "regulatory_input_integral": ["regulatory_slot"],  # U = integral of u dt, diagnostic.
    "regulatory_crossing_step": ["regulatory_slot"],  # int64: first step end with s >= level; -1.
    "regulatory_writes_applied": ["regulatory_slot"],  # int64: writes applied so far.
    "coupling_enabled": ["coupling"],  # 0 or 1, copied from the schedule at each step start.
    "coupling_step_count": ["one"],  # int64: steps started; time of a step start = count * dt.
}
INTEGER_FIELDS = ("regulatory_crossing_step", "regulatory_writes_applied", "coupling_step_count")
LAYOUT_FIELDS = (
    "regulatory_slot_cell",  # [slot] int64: the cell of each declared (state, cell) slot.
    "regulatory_on_rate",  # [slot] 1/s
    "regulatory_off_rate",  # [slot] 1/s
    "regulatory_has_level",  # [slot] bool
    "regulatory_level",  # [slot] (0 where none)
    "regulatory_input_row",  # [slot, input] int64 species row (0 on padding)
    "regulatory_input_kind",  # [slot, input] int64: 1 activation, 2 inhibition, 0 padding
    "regulatory_input_half_saturation_mM",  # [slot, input] (1 on padding)
    "regulatory_input_coefficient",  # [slot, input] (1 on padding)
    "coupling_route_law",  # [route] int64: 1, 2 (species), 3, 4 (state), 5, 6 (population; @2)
    "coupling_route_row",  # [route] int64 species row (0 for a state route)
    "coupling_route_cell",  # [route] int64 the cell the route reads
    "coupling_route_slot",  # [route] int64 state slot (0 for a species route)
    "coupling_route_half_saturation_mM",  # [route] (1 for a state route)
    "coupling_route_coefficient",  # [route] (1 for a state route)
    "coupling_route_basal",  # [route]
    "coupling_route_coupling",  # [route] int64 its coupling (for the switch)
    "coupling_junction_routes",  # [edge capacity, width] int64 route per element (-1 pads)
    "coupling_channel_routes",  # [channel capacity, width] int64 route per element (-1 pads)
)
TARGET_TABLES = {"junction": "coupling_junction_routes", "channel": "coupling_channel_routes"}
# Version 1.1 (FR-65's coupling step, docs/TURNOVER_CHANGING_VOLUME_DESIGN.md §11): the cell volume
# is read current at the split (its states' half-steps, and its routed factors at its targets'
# half-steps, which follow it) and at the control view (R2′), and as declared by the end's validity
# check (factors_valid), whose outcome is the same at every positive volume (C3). It reads no
# outside volume. The masks stay on its fixed list as D150's static-tissue scope: it reads none.
VOLUME_READS = (Read("current", "split"), Read("current", "inner"), Read("reference", "end"))
MASKS = ("active", "outside_active", "membrane_active")

# Version 2 (the module docstring): the routable controls it routes to, each with its element
# table ([elements, width] int64 route per element, -1 pads), and every route's operating range
# ([route] low and high; -inf and inf on an inner target's route).
LAW_ID_V2 = "cells.operator.species_regulated_availability@2"
EVALUATIONS = MappingProxyType({"inner": "step_view", "operator": "target_half_steps"})
OPERATOR_TABLES = MappingProxyType(
    {
        (
            "cells.operator.scheduled_species_turnover@1",
            "turnover_rate",
        ): "coupling_turnover_rate_routes",
        (
            "cells.operator.local_species_reactions@1",
            "reaction_multiplier",
        ): "coupling_reaction_multiplier_routes",
        # FR-7's unit producer (F3), a recorded exception naming the operators owner.
        (
            "cells.operator.population_unit_turnover@1",
            "unit_assembly_rate",
        ): "coupling_unit_assembly_rate_routes",
        # Gene regulation's option A (G4, D235): a chain's initiation rate constant, a recorded
        # exception naming the operators owner.
        ("cells.operator.templated_polymerisation@1", "polymerisation_initiation_rate"): (
            "coupling_polymerisation_initiation_rate_routes"
        ),
        # FR-38's routed durable fraction p (the sheet's §9.4, source 3), the same recorded
        # exception, under the lead's leave (23 November 2026).
        ("cells.operator.templated_polymerisation@1", "polymerisation_release_fraction"): (
            "coupling_polymerisation_release_fraction_routes"
        ),
    }
)
LAYOUT_FIELDS_V2 = (
    *LAYOUT_FIELDS,
    *OPERATOR_TABLES.values(),
    "coupling_route_low",
    "coupling_route_high",
    # The population source (FR-7's part (b)): each route's population route (-1: none), and
    # each population route's source channel slot, reference density and half-saturation
    # (units per µm²). Their shape is static: no population route, no read of the view.
    "coupling_route_population",
    "coupling_population_channel",
    "coupling_population_reference_density_per_um2",
    "coupling_population_half_saturation_per_um2",
    # The site source (FR-24): each route's site route (-1: none), and per site route its
    # population's index on the owner's axis, its quantity's code and its half-saturation (in the
    # quantity's unit; 1 for the fraction's own laws). Static by shape: no site route, no read.
    "coupling_route_site",
    "coupling_site_population",
    "coupling_site_quantity",
    "coupling_site_half_saturation",
)
MEMBRANE_STATE = membrane_state.LAW_ID  # Its declaration holds each reference density.
UNIT_FIELDS = ("population_abundance_increment", "membrane_area_increment_m2")  # rho = N / A.
CONSTANT_SOURCE = "constant source: the factor cannot vary in this run"
# A site source's capacity is a layout constant in version 1 (alpha, copies and sites per copy are
# not scheduled), so its factor is constant too.
CONSTANT_CAPACITY = "constant source: the accessible capacity is a layout constant in version 1"
# Version 2's exact record (contract FACTOR_RECORD): each route's factor where it was last applied,
# at the control view (a step_view route) or at its target's half-step (an operator route).
STATE_AXES_V2 = {**STATE_AXES, "coupling_applied_factor": ["coupling_route"]}


# ------------------------------------------------------------------ declaration


@dataclass(frozen=True)
class Input:
    law: str
    species: str
    half_saturation_mM: float
    hill_coefficient: float


@dataclass(frozen=True)
class RegulatoryState:
    id: str
    law: str
    cells: tuple
    inputs: tuple
    on_rate_per_s: float
    off_rate_per_s: float
    initial: tuple  # s0 per cell, aligned with cells.
    crossing_level: float | None


@dataclass(frozen=True)
class Target:
    operator: str
    control: str
    ids: tuple
    side: str | None


@dataclass(frozen=True)
class RangedTarget(Target):
    """Version 2's inner target: @1's, with its evaluation ("step_view") and its source's
    operating range declared, which the control view enforces (the module docstring)."""

    evaluation: str = "step_view"
    operating_range: tuple = ()  # (low, high), as an operator target's.


@dataclass(frozen=True)
class OperatorTarget:
    """Version 2's operator target (the module docstring): a routable control of another
    operator, by its elements' IDs, evaluated in that operator's half-steps."""

    operator: str
    control: str
    ids: tuple
    evaluation: str  # "target_half_steps".
    operating_range: tuple  # (low, high): the source's concentration (mM) or state fraction.
    side: None = None  # An operator target takes no side.


@dataclass(frozen=True)
class Coupling:
    id: str
    target: Target
    source_kind: str  # "species" or "state"
    source: str
    law: str
    half_saturation_mM: float | None
    hill_coefficient: float | None
    basal: float


@dataclass(frozen=True)
class PopulationCoupling(Coupling):
    """Version 2's population source (FR-7's part (b)): a Hill law of the source population's
    absolute density N/A in units per µm² (the lead's ruling), with K in the same unit.
    half_saturation_mM is None; source_kind is "population" and source the channel population."""

    half_saturation_per_um2: float


@dataclass(frozen=True)
class SiteCoupling(Coupling):
    """Version 2's site source (FR-24): a site population's occupied fraction, or its occupied
    amount or accessible capacity as a concentration in the route's cell, read through the owner's
    readable quantities (R3). half_saturation_mM is None; source_kind is "site" and source the
    population; half_saturation is in the quantity's unit (None for the fraction's own laws)."""

    quantity: str
    half_saturation: float | None


@dataclass(frozen=True)
class Declaration:
    law: str
    species: tuple
    states: tuple
    couplings: tuple


@dataclass(frozen=True)
class Schedule:
    switches: tuple  # ((coupling id, ((time, enabled), ...)), ...) in declared coupling order
    writes: tuple  # (((state id, cell id), ((time, value), ...)), ...) in slot order


def _fraction(value, what, *, upper_open=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{LAW_ID}: {what} must be a finite number")
    result = float(value)
    if not np.isfinite(result) or result < 0 or result > 1 or (upper_open and result == 1):
        raise ConfigError(f"{LAW_ID}: {what} lies in [0, {'1)' if upper_open else '1]'}")
    return result


def _positive(value, what):
    return _number(value, f"{LAW_ID}: {what}", positive=True)


def _id_list(raw, what):
    if type(raw) is not list or not raw:
        raise ConfigError(f"{LAW_ID}: {what} is a non-empty explicit list")
    ids = tuple(identifier(v) for v in raw)
    if len(set(ids)) != len(ids):
        raise ConfigError(f"{LAW_ID}: {what} names an element twice")
    return ids


def _parse_initial(raw, name, where):
    """s0: one number for every cell of the state, or an object naming each of its cells once."""
    if isinstance(raw, dict):
        if set(raw) != set(where) or len(raw) != len(where):
            raise ConfigError(
                f"{LAW_ID}: state {name}'s initial object names each of its cells once"
            )
        return tuple(_fraction(raw[c], f"state {name}'s initial value in {c}") for c in where)
    value = _fraction(raw, f"state {name}'s initial value")
    return tuple(value for _ in where)


def _parse_states(raw, base, listed):
    if type(raw) is not list:
        raise ConfigError(f"{LAW_ID} declares its states in an explicit list")
    cells = [c.id for c in base.model.cells]
    states = []
    for entry in raw:
        _fields(
            entry,
            {
                "id",
                "law",
                "cells",
                "inputs",
                "on_rate_per_s",
                "off_rate_per_s",
                "initial",
                "crossing_level",
            },
            f"{LAW_ID} state",
        )
        name = identifier(entry["id"])
        if entry["law"] != STATE_LAW:
            raise ConfigError(f"{LAW_ID}: state {name} follows law {STATE_LAW}")
        where = (
            tuple(cells)
            if entry["cells"] == "all"
            else _id_list(entry["cells"], f"state {name}'s cells")
        )
        unknown = [c for c in where if c not in cells]
        if unknown:
            raise ConfigError(
                f"{LAW_ID}: state {name} is declared in an undeclared cell {unknown[0]!r}"
            )
        if type(entry["inputs"]) is not list or not entry["inputs"]:
            raise ConfigError(f"{LAW_ID}: state {name} reads at least one input")
        inputs = []
        for item in entry["inputs"]:
            _fields(
                item,
                {"law", "species", "half_saturation_mM", "hill_coefficient"},
                f"{LAW_ID} input",
            )
            if item["law"] not in SPECIES_LAWS:
                raise ConfigError(f"{LAW_ID}: an input's law is one of " + ", ".join(SPECIES_LAWS))
            if item["species"] not in listed:
                raise ConfigError(
                    f"{LAW_ID}: state {name} reads {item['species']!r}, not a listed species"
                )
            inputs.append(
                Input(
                    item["law"],
                    item["species"],
                    _positive(item["half_saturation_mM"], f"state {name}'s half_saturation_mM"),
                    _positive(item["hill_coefficient"], f"state {name}'s hill_coefficient"),
                )
            )
        level = entry["crossing_level"]
        states.append(
            RegulatoryState(
                name,
                STATE_LAW,
                where,
                tuple(inputs),
                _number(entry["on_rate_per_s"], f"{LAW_ID}: state {name}'s on_rate_per_s"),
                _number(entry["off_rate_per_s"], f"{LAW_ID}: state {name}'s off_rate_per_s"),
                _parse_initial(entry["initial"], name, where),
                None if level is None else _fraction(level, f"state {name}'s crossing level"),
            )
        )
    if len({s.id for s in states}) != len(states):
        raise ConfigError(f"{LAW_ID}: state IDs are unique")
    return tuple(states)


def _target_cells(model, target, element):
    """The cells a route of `target` on `element` reads, in order (a junction's side picks)."""
    if target.control == "channel":
        membranes = {p.id: p for p in model.membranes}
        channel = next(c for c in model.channels if c.id == element)
        return (membranes[channel.membrane_id].inside,)
    junction = next(j for j in model.junctions if j.id == element)
    return {
        "first": (junction.sender,),
        "second": (junction.receiver,),
        "both": (junction.sender, junction.receiver),
    }[target.side]


def _operating_range(raw, name):
    """Version 2: an operator target's [low, high], finite with low < high (the source kind's
    own bounds are checked with the source)."""
    if type(raw) is not list or len(raw) != 2:
        raise ConfigError(f"{LAW_ID_V2}: coupling {name}'s operating_range is [low, high]")
    low, high = (_number(v, f"{LAW_ID_V2}: coupling {name}'s operating_range bound") for v in raw)
    if not low < high:
        raise ConfigError(f"{LAW_ID_V2}: coupling {name}'s operating_range has low < high")
    return (low, high)


def _operator_target(raw, name):
    """Version 2's operator target (the module docstring), its elements bound at binding."""
    t = _fields(
        raw,
        {"operator", "control", "ids", "evaluation", "operating_range"},
        f"{LAW_ID_V2} target",
    )
    if (t["operator"], t["control"]) not in OPERATOR_TABLES:
        raise ConfigError(
            f"{LAW_ID_V2}: coupling {name} targets {t['operator']!r}'s {t['control']!r}; "
            "routable targets: " + ", ".join(f"{law}'s {field}" for law, field in OPERATOR_TABLES)
        )
    if t["evaluation"] != EVALUATIONS["operator"]:
        raise ConfigError(
            f"{LAW_ID_V2}: coupling {name}'s operator target is evaluated at "
            f"{EVALUATIONS['operator']!r}: the start of each of its target's half-steps"
        )
    ids = _id_list(t["ids"], f"coupling {name}'s target ids")
    return OperatorTarget(
        t["operator"],
        t["control"],
        ids,
        t["evaluation"],
        _operating_range(t["operating_range"], name),
    )


def _inner_target(raw, name, elements, version):
    """An inner target (@1's, unchanged; version 2 also declares its evaluation, "step_view", and
    its source's operating range)."""
    keys = {"operator", "control", "ids", "side"}
    if version == 2:
        keys |= {"evaluation", "operating_range"}
    t = _fields(raw, keys, f"{LAW_ID} target")
    if t["operator"] != "inner":
        raise ConfigError(
            f"{LAW_ID}: coupling {name} targets {t['operator']!r}; version 1 targets the inner "
            "model's controls only (routes to other operators' controls are a later door, §2)"
        )
    if version == 2 and t["evaluation"] != EVALUATIONS["inner"]:
        raise ConfigError(
            f"{LAW_ID_V2}: coupling {name}'s inner target is evaluated at "
            f"{EVALUATIONS['inner']!r}: once per step, held through @3's step"
        )
    if t["control"] not in TARGET_CONTROLS:
        raise ConfigError(
            f"{LAW_ID}: coupling {name} targets {t['control']!r}; admitted targets: "
            + ", ".join(TARGET_CONTROLS)
        )
    ids = _id_list(t["ids"], f"coupling {name}'s target ids")
    unknown = [i for i in ids if i not in elements[t["control"]]]
    if unknown:
        raise ConfigError(
            f"{LAW_ID}: coupling {name} names an unknown {t['control']} {unknown[0]!r}"
        )
    if t["control"] == "junction":
        if t["side"] not in SIDES:
            raise ConfigError(f"{LAW_ID}: a junction's side is one of " + ", ".join(SIDES))
    elif t["side"] is not None:
        raise ConfigError(f"{LAW_ID}: a {t['control']} target takes no side")
    if version == 2:
        return RangedTarget(
            "inner",
            t["control"],
            ids,
            t["side"],
            t["evaluation"],
            _operating_range(t["operating_range"], name),
        )
    return Target("inner", t["control"], ids, t["side"])


def _population_coupling(entry, m, elements):
    """Version 2's population source (the module docstring): a Hill law of the source
    population's density (units per µm²) on @3's channel targets in its own cell."""
    name = identifier(entry.get("id"))
    origin = identifier(entry["source"]["population"])
    for key in entry:
        if key.startswith("half_saturation_") and key != "half_saturation_per_um2":
            raise ConfigError(
                f"{LAW_ID_V2}: coupling {name} reads population {origin!r} through {key}; a "
                "population source is its density, half_saturation_per_um2 (units per µm²): a "
                "count would make the factor depend on the host's size"
            )
    keys = {"id", "target", "source", "law", "basal", "half_saturation_per_um2", "hill_coefficient"}
    _fields(entry, keys, f"{LAW_ID_V2} coupling")
    law = entry["law"]
    if law not in SPECIES_LAWS:
        raise ConfigError(
            f"{LAW_ID_V2}: coupling {name} reads a population through a Hill law: "
            + ", ".join(SPECIES_LAWS)
        )
    raw_target = entry["target"]
    if isinstance(raw_target, dict) and raw_target.get("operator") != "inner":
        raise ConfigError(
            f"{LAW_ID_V2}: coupling {name} reads a population onto an operator target; a "
            "population is read at the control view, which an operator target's half-steps do "
            "not receive, so its targets are @3's channels"
        )
    target = _inner_target(raw_target, name, elements, 2)
    if target.control != "channel":
        raise ConfigError(
            f"{LAW_ID_V2}: coupling {name} reads a population onto a junction; a population "
            "source targets @3's channels (a junction's side both needs a population per "
            "endpoint: later, with U1)"
        )
    channels = {c.id: c for c in m.channels}
    if origin not in channels:
        raise ConfigError(f"{LAW_ID_V2}: coupling {name} reads an unknown population {origin!r}")
    if origin in target.ids:
        raise ConfigError(
            f"{LAW_ID_V2}: coupling {name} reads population {origin}'s own abundance onto its "
            "availability; @3 already scales its conductance by that abundance, so a factor "
            "would count it twice (D218)"
        )
    membranes = {p.id: p for p in m.membranes}
    home = membranes[channels[origin].membrane_id].inside
    for element in target.ids:
        (cell,) = _target_cells(m, target, element)
        if cell != home:
            raise ConfigError(
                f"{LAW_ID_V2}: coupling {name} reads population {origin}, in {home}, onto "
                f"{element}, in {cell}; a population source is read in its target's cell"
            )
    k = _positive(entry["half_saturation_per_um2"], f"coupling {name}'s half_saturation_per_um2")
    n = _positive(entry["hill_coefficient"], f"coupling {name}'s hill_coefficient")
    basal = _fraction(entry["basal"], f"coupling {name}'s basal level", upper_open=True)
    return PopulationCoupling(name, target, "population", origin, law, None, n, basal, k)


def _site_coupling(entry, m, elements):
    """Version 2's site source (the module docstring): a site population's quantity on @3's
    channel targets or an operator target, read in the element's cell."""
    name = identifier(entry.get("id"))
    source = entry["source"]
    _fields(source, {"site_population", "quantity"}, f"{LAW_ID_V2} coupling {name}'s site source")
    origin = identifier(source["site_population"])
    quantity = source["quantity"]
    if quantity not in SITE_QUANTITIES:
        raise ConfigError(
            f"{LAW_ID_V2}: coupling {name}'s site source reads one of " + ", ".join(SITE_QUANTITIES)
        )
    law = entry.get("law")
    fraction = quantity == "occupied_fraction"
    half_key = "half_saturation" if fraction else "half_saturation_mM"
    if law in SITE_FRACTION_LAWS and fraction:
        keys = {"id", "target", "source", "law", "basal"}
    elif law in SPECIES_LAWS:
        keys = {"id", "target", "source", "law", "basal", half_key, "hill_coefficient"}
    else:
        laws = (*SITE_FRACTION_LAWS, *SPECIES_LAWS) if fraction else tuple(SPECIES_LAWS)
        raise ConfigError(
            f"{LAW_ID_V2}: coupling {name} reads a site population's {quantity} through one of "
            + ", ".join(laws)
        )
    for key in entry:
        if key.startswith("half_saturation") and key != half_key:
            raise ConfigError(
                f"{LAW_ID_V2}: coupling {name} reads {quantity} through {key}; its half-saturation "
                f"is {half_key}, in the quantity's unit"
                + (" (a fraction)" if fraction else " (mM in the element's cell)")
            )
    _fields(entry, keys, f"{LAW_ID_V2} coupling")
    raw_target = entry["target"]
    if isinstance(raw_target, dict) and raw_target.get("operator") != "inner":
        target = _operator_target(raw_target, name)
    else:
        target = _inner_target(raw_target, name, elements, 2)
        if target.control != "channel":
            raise ConfigError(
                f"{LAW_ID_V2}: coupling {name} reads a site population onto a junction; a site "
                "source targets @3's channels or an operator target (a junction's side both needs "
                "a population per endpoint: later)"
            )
    low, high = target.operating_range
    if low < 0 or (fraction and high > 1):
        raise ConfigError(
            f"{LAW_ID_V2}: coupling {name}'s operating_range lies in "
            + ("[0, 1], the occupied fraction" if fraction else "[0, inf) mM")
        )
    half = n = None
    if law in SPECIES_LAWS:
        half = _positive(entry[half_key], f"coupling {name}'s {half_key}")
        n = _positive(entry["hill_coefficient"], f"coupling {name}'s hill_coefficient")
    basal = _fraction(entry["basal"], f"coupling {name}'s basal level", upper_open=True)
    return SiteCoupling(name, target, "site", origin, law, None, n, basal, quantity, half)


def _parse_couplings(raw, base, listed, states, *, version=1):
    if type(raw) is not list:
        raise ConfigError(f"{LAW_ID} declares its couplings in an explicit list")
    m = base.model
    valence = dict(zip(m.species_ids, m.valence, strict=True))
    elements = dict(junction={j.id for j in m.junctions}, channel={c.id for c in m.channels})
    by_state = {s.id: s for s in states}
    couplings = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ConfigError(f"{LAW_ID}: a coupling is an object")
        source = entry.get("source")
        if version == 2 and isinstance(source, dict) and set(source) == {"population"}:
            couplings.append(_population_coupling(entry, m, elements))
            continue
        if version == 2 and isinstance(source, dict) and "site_population" in source:
            couplings.append(_site_coupling(entry, m, elements))  # FR-24.
            continue
        law = entry.get("law")
        keys = {"id", "target", "source", "law", "basal"}
        if law in SPECIES_LAWS:
            keys |= {"half_saturation_mM", "hill_coefficient"}
        elif law not in STATE_FACTOR_LAWS:
            raise ConfigError(
                f"{LAW_ID}: a coupling's law is one of "
                + ", ".join((*SPECIES_LAWS, *STATE_FACTOR_LAWS))
            )
        _fields(entry, keys, f"{LAW_ID} coupling")
        name = identifier(entry["id"])
        raw_target = entry["target"]
        if version == 2 and isinstance(raw_target, dict) and raw_target.get("operator") != "inner":
            target = _operator_target(raw_target, name)
        else:
            target = _inner_target(raw_target, name, elements, version)
        source = entry["source"]
        if (
            not isinstance(source, dict)
            or len(source) != 1
            or next(iter(source)) not in ("species", "state")
        ):
            raise ConfigError(
                f"{LAW_ID}: coupling {name}'s source is {{'species': id}} or {{'state': id}}"
            )
        kind, origin = next(iter(source.items()))
        if kind == "species":
            if law not in SPECIES_LAWS:
                raise ConfigError(f"{LAW_ID}: coupling {name} reads a species through a Hill law")
            if origin not in listed:
                raise ConfigError(
                    f"{LAW_ID}: coupling {name} reads {origin!r}, not a listed species"
                )
            if valence[origin] != 0:
                raise ConfigError(
                    f"{LAW_ID}: coupling {name} reads the charged species {origin!r} "
                    "instantaneously; an instantaneous source must be a neutral row (valence 0), "
                    "whether or not the row has a route or is moved by the step: read it through "
                    "a state (§1.4)"
                )
            common.check_impermeant(m, origin, LAW_ID)
            k = _positive(entry["half_saturation_mM"], f"coupling {name}'s half_saturation_mM")
            n = _positive(entry["hill_coefficient"], f"coupling {name}'s hill_coefficient")
        else:
            if law not in STATE_FACTOR_LAWS:
                raise ConfigError(f"{LAW_ID}: coupling {name} reads a state through a state law")
            if origin not in by_state:
                raise ConfigError(f"{LAW_ID}: coupling {name} reads an undeclared state {origin!r}")
            k = n = None
            for element in target.ids if isinstance(target, Target) else ():  # Operator: binding.
                for cell in _target_cells(m, target, element):
                    if cell not in by_state[origin].cells:
                        raise ConfigError(
                            f"{LAW_ID}: coupling {name} reads state {origin} in {cell}, where it "
                            "is not declared"
                        )
        if isinstance(target, (OperatorTarget, RangedTarget)):
            low, high = target.operating_range
            if low < 0 or (kind == "state" and high > 1):
                raise ConfigError(
                    f"{LAW_ID_V2}: coupling {name}'s operating_range lies in "
                    + ("[0, 1], its state's fraction" if kind == "state" else "[0, inf) mM")
                )
        basal = _fraction(entry["basal"], f"coupling {name}'s basal level", upper_open=True)
        couplings.append(Coupling(name, target, kind, origin, law, k, n, basal))
    if len({c.id for c in couplings}) != len(couplings):
        raise ConfigError(f"{LAW_ID}: coupling IDs are unique")
    return tuple(couplings)


def parse_declaration(raw, base, *, version=1):
    law = LAW_ID if version == 1 else LAW_ID_V2
    _fields(raw, {"law", "species", "states", "couplings"}, "species-regulated availability")
    if raw["law"] != law:
        raise ConfigError("Species-regulated availability requires law " + law)
    species = common.parse_read_species(raw["species"], base, law)
    listed = {s.id for s in species}
    states = _parse_states(raw["states"], base, listed)
    couplings = _parse_couplings(raw["couplings"], base, listed, states, version=version)
    return Declaration(law, species, states, couplings)


def _target_to_dict(target, law):
    """A target's declaration: @1's form; version 2 adds an inner target's evaluation, and an
    operator target is its own form."""
    if type(target) is OperatorTarget:
        return dict(
            operator=target.operator,
            control=target.control,
            ids=list(target.ids),
            evaluation=target.evaluation,
            operating_range=list(target.operating_range),
        )
    out = dict(
        operator=target.operator,
        control=target.control,
        ids=list(target.ids),
        side=target.side,
    )
    if type(target) is RangedTarget:
        out.update(evaluation=target.evaluation, operating_range=list(target.operating_range))
    return out


def _initial_to_dict(state):
    if len(set(state.initial)) == 1:
        return state.initial[0]
    return dict(zip(state.cells, state.initial, strict=True))


def declaration_to_dict(declaration):
    if type(declaration) is not Declaration:
        raise ConfigError("Require explicit immutable species-regulated availability types")
    return dict(
        law=declaration.law,
        species=[
            dict(
                id=s.id,
                catalogue=None
                if s.catalogue is None
                else dict(catalogue=s.catalogue[0], entry=s.catalogue[1]),
                evidence=s.evidence,
            )
            for s in declaration.species
        ],
        states=[
            dict(
                id=s.id,
                law=s.law,
                cells=list(s.cells),
                inputs=[
                    dict(
                        law=i.law,
                        species=i.species,
                        half_saturation_mM=i.half_saturation_mM,
                        hill_coefficient=i.hill_coefficient,
                    )
                    for i in s.inputs
                ],
                on_rate_per_s=s.on_rate_per_s,
                off_rate_per_s=s.off_rate_per_s,
                initial=_initial_to_dict(s),
                crossing_level=s.crossing_level,
            )
            for s in declaration.states
        ],
        couplings=[
            dict(
                id=c.id,
                target=_target_to_dict(c.target, declaration.law),
                source=_source_to_dict(c),
                law=c.law,
                basal=c.basal,
                **(
                    dict(
                        half_saturation_mM=c.half_saturation_mM, hill_coefficient=c.hill_coefficient
                    )
                    if c.source_kind == "species"
                    else dict(
                        half_saturation_per_um2=c.half_saturation_per_um2,
                        hill_coefficient=c.hill_coefficient,
                    )
                    if c.source_kind == "population"
                    else _site_half_saturation(c)
                    if c.source_kind == "site"
                    else {}
                ),
            )
            for c in declaration.couplings
        ],
    )


def _source_to_dict(coupling):
    if type(coupling) is SiteCoupling:  # FR-24.
        return {"site_population": coupling.source, "quantity": coupling.quantity}
    return {coupling.source_kind: coupling.source}


def _site_half_saturation(coupling):
    """FR-24: a site coupling's half-saturation in its quantity's unit, with its Hill coefficient;
    none for the fraction's own laws."""
    if coupling.half_saturation is None:
        return {}
    key = "half_saturation" if coupling.quantity == "occupied_fraction" else "half_saturation_mM"
    return {key: coupling.half_saturation, "hill_coefficient": coupling.hill_coefficient}


def slots(declaration):
    """The (state id, cell id) slots, in declared order: states, then each state's cells."""
    return tuple((s.id, c) for s in declaration.states for c in s.cells)


def _event_time(value, what, base, *, at_zero=False):
    """A switch change after time 0 (0 < t < end, the composite's rule for event times, §1.11), or
    a write (0 <= t < end: a write at 0 is applied at the first step start and is not a schedule
    change time). On the clock's grid (D283), refused here with its own message."""
    dt, end = base.execution.dt, base.experiment.end_time
    time = _number(value, f"{LAW_ID}: {what}")
    if on_grid(time, dt) is None:
        raise ConfigError(f"{LAW_ID}: {what} must be {ON_THE_GRID}")
    if not (0.0 <= time if at_zero else 0.0 < time) or not time < end:
        bound = "0 <= t < end" if at_zero else "0 < t < end"
        raise ConfigError(f"{LAW_ID}: {what} lies inside the horizon, {bound}")
    return time


def parse_schedule(raw, base, declaration):
    rows = raw[CONTROLS_KEY]
    if type(rows) is not list:
        raise ConfigError(f"{LAW_ID}: {CONTROLS_KEY} is an explicit list")
    switches = {}
    for row in rows:
        _fields(row, {"coupling_id", "schedule"}, f"{LAW_ID} coupling control")
        name = row["coupling_id"]
        if name not in {c.id for c in declaration.couplings} or name in switches:
            raise ConfigError(f"{LAW_ID}: one schedule per declared coupling ({name!r})")
        changes = row["schedule"]
        if type(changes) is not list or not changes:
            raise ConfigError(f"{LAW_ID}: coupling {name}'s schedule is a non-empty list")
        parsed = []
        for index, change in enumerate(changes):
            _fields(change, {"time", "enabled"}, f"{LAW_ID} switch change")
            if index == 0:
                time = _number(change["time"], f"{LAW_ID}: a switch time")
                if time != 0.0:
                    raise ConfigError(f"{LAW_ID}: coupling {name}'s schedule starts at 0")
            else:
                time = _event_time(change["time"], "a switch change", base)
            value = change["enabled"]
            if isinstance(value, bool) or value not in (0, 1):
                raise ConfigError(f"{LAW_ID}: a coupling is enabled (1) or not (0)")
            parsed.append((time, float(value)))
        times = [t for t, _ in parsed]
        if any(b <= a for a, b in zip(times, times[1:], strict=False)):
            raise ConfigError(f"{LAW_ID}: coupling {name}'s schedule times increase strictly")
        switches[name] = tuple(parsed)
    if set(switches) != {c.id for c in declaration.couplings}:
        raise ConfigError(f"{LAW_ID}: every coupling has its schedule in {CONTROLS_KEY}")
    writes_raw = raw[WRITES_KEY]
    if type(writes_raw) is not list:
        raise ConfigError(f"{LAW_ID}: {WRITES_KEY} is an explicit list")
    known = slots(declaration)
    writes = {key: [] for key in known}
    for row in writes_raw:
        _fields(row, {"state_id", "cell_id", "time", "value"}, f"{LAW_ID} regulatory write")
        key = (row["state_id"], row["cell_id"])
        if key not in writes:
            raise ConfigError(f"{LAW_ID}: a write names an undeclared state and cell {key!r}")
        time = _event_time(row["time"], "a write", base, at_zero=True)
        writes[key].append((time, _fraction(row["value"], "a written value")))
    for key, entries in writes.items():
        times = [t for t, _ in entries]
        if len(set(times)) != len(times):
            raise ConfigError(f"{LAW_ID}: two writes to {key!r} at one time")
        writes[key] = tuple(sorted(entries))
    return Schedule(
        tuple((c.id, switches[c.id]) for c in declaration.couplings),
        tuple((key, writes[key]) for key in known),
    )


def schedule_to_dict(schedule):
    if type(schedule) is not Schedule:
        raise ConfigError("Require explicit immutable species-regulated availability schedules")
    return {
        CONTROLS_KEY: [
            dict(coupling_id=name, schedule=[dict(time=t, enabled=int(v)) for t, v in changes])
            for name, changes in schedule.switches
        ],
        WRITES_KEY: [
            dict(state_id=key[0], cell_id=key[1], time=t, value=v)
            for key, entries in schedule.writes
            for t, v in entries
        ],
    }


def _switch_at(changes, time):
    value = changes[0][1]
    for t, v in changes:
        if t <= time:
            value = v
    return value


def _writes_at(entries, time):
    """(count of writes at or before time, the latest written value or 0)."""
    done = [v for t, v in entries if t <= time]
    return len(done), (done[-1] if done else 0.0)


# ------------------------------------------------------------------ binding


def reference_densities(spec):
    """Version 2: {population: its reference density (units/m^2)} from the definition's
    cells.operator.membrane_entity_state@1 declaration (FR-7's Q5 (a)); refused without one."""
    for op, block, _ in composite_spec.entries(spec):
        if op.LAW_ID == MEMBRANE_STATE:
            return {p.channel_id: p.reference_density_per_m2 for p in block.populations}
    raise ConfigError(
        f"{LAW_ID_V2}: a population source needs {MEMBRANE_STATE}, whose declared reference "
        "density turns @3's abundance into the source's density"
    )


def _population_layout(spec, declaration, routes):
    """Version 2: each population route's law code set (its Hill kind plus POPULATION_OFFSET,
    so @1's kernels give it f = 1), and its arrays: the route map ([route], -1 elsewhere), and
    per population route its source's channel slot, reference density and half-saturation (per
    µm²). Refused here, where the binding first reads it: a population source without
    cells.operator.membrane_entity_state@1."""
    index = -np.ones(len(routes), dtype=np.int64)
    population = [
        i
        for i, r in enumerate(routes)
        if type(declaration.couplings[r["coupling"]]) is PopulationCoupling
    ]
    couplings = [declaration.couplings[routes[i]["coupling"]] for i in population]
    density = reference_densities(spec) if population else {}
    channels = [c.id for c in spec.model.channels]
    for j, (i, coupling) in enumerate(zip(population, couplings, strict=True)):
        routes[i]["law"] = POPULATION_LAWS[coupling.law]
        index[i] = j
    return dict(
        coupling_route_population=index,
        coupling_population_channel=np.asarray(
            [channels.index(c.source) for c in couplings], dtype=np.int64
        ),
        coupling_population_reference_density_per_um2=np.asarray(
            [density[c.source] * 1e-12 for c in couplings], dtype=float
        ),
        coupling_population_half_saturation_per_um2=np.asarray(
            [c.half_saturation_per_um2 for c in couplings], dtype=float
        ),
    )


def site_entities(spec):
    """Version 2: the site populations of the definition's cells.operator.site_occupancy@1, each (id, cell) in
    its axis' order, from the owner's host-side declaration of its entities (R3); None without
    the owner."""
    for op, other, _ in composite_spec.entries(spec):
        if op.LAW_ID == SITE_LAW:
            return op.quantity_entities(spec, other)["site_population"]
    return None


def bound_site_quantities(spec, inner_state, inner_layout):
    """Version 2: {SITE_LAW: its readable quantities} at the owner's own bound state, from the
    owner's own binding and quantities (R3), host side: a site route's factor at the bound state,
    the record's start."""
    for op, other, schedule in composite_spec.entries(spec):
        if op.LAW_ID == SITE_LAW:
            state, layout = op.initial_values(spec, other, schedule, inner_state, inner_layout)
            read = SimpleNamespace(**inner_state._asdict(), **state)
            bound = SimpleNamespace(**inner_layout._asdict(), **layout)
            return {SITE_LAW: op.quantities(read, bound, xp=np)}
    raise ConfigError(f"{LAW_ID_V2}: a site source needs {SITE_LAW}")


def _site_layout(spec, declaration, routes):
    """Version 2: each site route's law code set (a Hill kind plus SITE_OFFSET, or the fraction's
    own laws, so @1's kernels and the population kernel give it f = 1), and its arrays: the route
    map ([route], -1 elsewhere), and per site route its population's index on the owner's axis,
    its quantity's code and its half-saturation (1 for the fraction's own laws). Refused here,
    where the binding first reads it: a site source without cells.operator.site_occupancy@1, an unknown
    population, and a population outside the route's cell."""
    index = -np.ones(len(routes), dtype=np.int64)
    site = [
        i
        for i, r in enumerate(routes)
        if type(declaration.couplings[r["coupling"]]) is SiteCoupling
    ]
    couplings = [declaration.couplings[routes[i]["coupling"]] for i in site]
    population, quantity, half = [], [], []
    if site:
        entities = site_entities(spec)
        if entities is None:
            raise ConfigError(
                f"{LAW_ID_V2}: coupling {couplings[0].id} reads a site population, but the "
                f"definition declares no {SITE_LAW}"
            )
        ids = [entity for entity, _ in entities]
        cells = [c.id for c in spec.model.cells]
        for j, (i, coupling) in enumerate(zip(site, couplings, strict=True)):
            if coupling.source not in ids:
                raise ConfigError(
                    f"{LAW_ID_V2}: coupling {coupling.id} reads an unknown site population "
                    f"{coupling.source!r}"
                )
            k = ids.index(coupling.source)
            home, cell = entities[k][1], cells[routes[i]["cell"]]
            if home is None:  # FR-28 (D268): a node's own sites belong to no cell.
                raise ConfigError(
                    f"{LAW_ID_V2}: coupling {coupling.id} reads site population "
                    f"{coupling.source}, a node's own sites, which belong to no cell; a site "
                    "source is read in its element's cell, and no @2 target lives at a node "
                    "(version 1)"
                )
            if home != cell:
                raise ConfigError(
                    f"{LAW_ID_V2}: coupling {coupling.id} reads site population {coupling.source}, "
                    f"in {home}, on an element in {cell}; a site source is read in its element's "
                    "cell"
                )
            routes[i]["law"] = SITE_FRACTION_LAWS.get(coupling.law) or SITE_HILL_LAWS[coupling.law]
            index[i] = j
            population.append(k)
            quantity.append(SITE_QUANTITIES.index(coupling.quantity))
            half.append(1.0 if coupling.half_saturation is None else coupling.half_saturation)
    return dict(
        coupling_route_site=index,
        coupling_site_population=np.asarray(population, dtype=np.int64),
        coupling_site_quantity=np.asarray(quantity, dtype=np.int64),
        coupling_site_half_saturation=np.asarray(half, dtype=float),
    )


def _operator_routes(spec, declaration, routes, slot_keys):
    """Version 2: each operator target's routes, appended to `routes` after the inner ones, and
    ({table field: [elements, width] route per element, -1 pads}, [(low, high) per appended
    route]). The elements and their cells are the target's (routable_elements), bound against its
    declaration. Refused here: a target the definition does not declare, an unknown element, an
    outside-node element (its source is read in the element's cell), and a state source not
    declared in an element's cell."""
    m = spec.model
    species, cells = list(m.species_ids), [c.id for c in m.cells]
    declared = {op.LAW_ID: (op, d) for op, d, _ in composite_spec.entries(spec)}
    by_state = {s.id: s for s in declaration.states}
    on_element = {key: {} for key in OPERATOR_TABLES}
    sizes = {
        key: len(declared[key[0]][0].routable_elements(declared[key[0]][1], key[1]))
        if key[0] in declared
        else 0
        for key in OPERATOR_TABLES
    }
    ranges = []
    for c_index, coupling in enumerate(declaration.couplings):
        target = coupling.target
        if type(target) is not OperatorTarget:
            continue
        if target.operator not in declared:
            raise ConfigError(
                f"{LAW_ID_V2}: coupling {coupling.id} targets {target.operator}, which the "
                "definition does not declare"
            )
        op, target_declaration = declared[target.operator]
        elements = op.routable_elements(target_declaration, target.control)
        named = {element for element, _ in elements}
        unknown = [i for i in target.ids if i not in named]
        if unknown:
            raise ConfigError(
                f"{LAW_ID_V2}: coupling {coupling.id} names {target.operator}'s unknown element "
                f"{unknown[0]!r}"
            )
        site = coupling.source_kind == "site"  # FR-24: its code set by _site_layout.
        law = 0 if site else (SPECIES_LAWS | STATE_FACTOR_LAWS)[coupling.law]
        from_state = coupling.source_kind == "state"
        padded = from_state or site
        for index, (element, cell) in enumerate(elements):
            if element not in target.ids:
                continue
            if cell is None:
                raise ConfigError(
                    f"{LAW_ID_V2}: coupling {coupling.id} routes {target.operator}'s {element} at "
                    "an outside node; version 2 routes cell-side elements only, since its source "
                    "is read in the element's cell"
                )
            if from_state and cell not in by_state[coupling.source].cells:
                raise ConfigError(
                    f"{LAW_ID_V2}: coupling {coupling.id} reads state {coupling.source} in {cell}, "
                    "where it is not declared"
                )
            key = (target.operator, target.control)
            on_element[key].setdefault(index, []).append(len(routes))
            routes.append(
                dict(
                    law=law,
                    row=0 if padded else species.index(coupling.source),
                    cell=cells.index(cell),
                    slot=slot_keys.index((coupling.source, cell)) if from_state else 0,
                    half=1.0 if padded else coupling.half_saturation_mM,
                    coefficient=1.0 if from_state else (coupling.hill_coefficient or 1.0),
                    basal=coupling.basal,
                    coupling=c_index,
                )
            )
            ranges.append(target.operating_range)
    tables = {}
    for key, field in OPERATOR_TABLES.items():
        depth = max((len(v) for v in on_element[key].values()), default=0)
        table = -np.ones((sizes[key], depth), dtype=np.int64)
        for index, members in on_element[key].items():
            table[index, : len(members)] = members
        tables[field] = table
    tables.update(_population_layout(spec, declaration, routes))  # FR-7's part (b).
    tables.update(_site_layout(spec, declaration, routes))  # FR-24.
    return tables, ranges


def bind(spec, declaration, schedule):
    m, x = spec.model, spec.execution
    species = list(m.species_ids)
    cells = [c.id for c in m.cells]
    junctions = [j.id for j in m.junctions]
    channels = [c.id for c in m.channels]
    slot_keys = slots(declaration)
    by_state = {s.id: s for s in declaration.states}
    width = max((len(s.inputs) for s in declaration.states), default=0)
    k = len(slot_keys)
    layout = dict(
        regulatory_slot_cell=np.asarray([cells.index(c) for _, c in slot_keys], dtype=np.int64),
        regulatory_on_rate=np.asarray(
            [by_state[s].on_rate_per_s for s, _ in slot_keys], dtype=float
        ),
        regulatory_off_rate=np.asarray(
            [by_state[s].off_rate_per_s for s, _ in slot_keys], dtype=float
        ),
        regulatory_has_level=np.asarray(
            [by_state[s].crossing_level is not None for s, _ in slot_keys], dtype=bool
        ),
        regulatory_level=np.asarray(
            [by_state[s].crossing_level or 0.0 for s, _ in slot_keys], dtype=float
        ),
        regulatory_input_row=np.zeros((k, width), dtype=np.int64),
        regulatory_input_kind=np.zeros((k, width), dtype=np.int64),
        regulatory_input_half_saturation_mM=np.ones((k, width)),
        regulatory_input_coefficient=np.ones((k, width)),
    )
    for i, (state_id, _) in enumerate(slot_keys):
        for j, item in enumerate(by_state[state_id].inputs):
            layout["regulatory_input_row"][i, j] = species.index(item.species)
            layout["regulatory_input_kind"][i, j] = SPECIES_LAWS[item.law]
            layout["regulatory_input_half_saturation_mM"][i, j] = item.half_saturation_mM
            layout["regulatory_input_coefficient"][i, j] = item.hill_coefficient
    routes, on_element = [], {name: {} for name in TARGET_TABLES}
    for c_index, coupling in enumerate(declaration.couplings):
        if type(coupling.target) is OperatorTarget:
            continue  # Version 2's, after every inner route (_operator_routes).
        site = coupling.source_kind == "site"  # Version 2's: its code set by _site_layout.
        law = 0 if site else (SPECIES_LAWS | STATE_FACTOR_LAWS)[coupling.law]
        for element in coupling.target.ids:
            for cell in _target_cells(m, coupling.target, element):
                from_state = coupling.source_kind == "state"
                padded = from_state or coupling.source_kind in ("population", "site")  # Version 2.
                route = dict(
                    law=law,
                    row=0 if padded else species.index(coupling.source),
                    cell=cells.index(cell),
                    slot=slot_keys.index((coupling.source, cell)) if from_state else 0,
                    half=1.0 if padded else coupling.half_saturation_mM,
                    coefficient=1.0 if from_state else (coupling.hill_coefficient or 1.0),
                    basal=coupling.basal,
                    coupling=c_index,
                )
                index = (junctions if coupling.target.control == "junction" else channels).index(
                    element
                )
                on_element[coupling.target.control].setdefault(index, []).append(len(routes))
                routes.append(route)
    operator = None
    if declaration.law == LAW_ID_V2:
        operator = _operator_routes(spec, declaration, routes, slot_keys)
    layout.update(
        coupling_route_law=np.asarray([r["law"] for r in routes], dtype=np.int64),
        coupling_route_row=np.asarray([r["row"] for r in routes], dtype=np.int64),
        coupling_route_cell=np.asarray([r["cell"] for r in routes], dtype=np.int64),
        coupling_route_slot=np.asarray([r["slot"] for r in routes], dtype=np.int64),
        coupling_route_half_saturation_mM=np.asarray([r["half"] for r in routes], dtype=float),
        coupling_route_coefficient=np.asarray([r["coefficient"] for r in routes], dtype=float),
        coupling_route_basal=np.asarray([r["basal"] for r in routes], dtype=float),
        coupling_route_coupling=np.asarray([r["coupling"] for r in routes], dtype=np.int64),
    )
    for name, field in TARGET_TABLES.items():
        size = x.edge_capacity if name == "junction" else x.channel_capacity
        depth = max((len(v) for v in on_element[name].values()), default=0)
        table = -np.ones((size, depth), dtype=np.int64)
        for index, members in on_element[name].items():
            table[index, : len(members)] = members
        layout[field] = table
    if operator is not None:  # Version 2: its element tables and every route's declared range.
        tables, _ = operator
        layout.update(tables)
        bounds = np.asarray(
            [declaration.couplings[r["coupling"]].target.operating_range for r in routes],
            dtype=float,
        ).reshape(len(routes), 2)
        layout.update(coupling_route_low=bounds[:, 0], coupling_route_high=bounds[:, 1])
    switches = np.asarray([changes[0][1] for _, changes in schedule.switches], dtype=float)
    state = dict(
        regulatory_state=np.asarray(
            [by_state[s].initial[by_state[s].cells.index(c)] for s, c in slot_keys], dtype=float
        ),
        regulatory_input_integral=np.zeros(k),
        regulatory_crossing_step=-np.ones(k, dtype=np.int64),
        regulatory_writes_applied=np.zeros(k, dtype=np.int64),
        coupling_enabled=switches,
        coupling_step_count=np.zeros(1, dtype=np.int64),
    )
    return state, layout


# ------------------------------------------------------------------ the laws


def route_factors(state, p, *, xp, volume=None):
    """[route] F = b + (1 - b) f, exactly 1 for a switched-off coupling (module docstring). A
    species source's concentration is n/V at `volume` [cell], the current volume a reader view
    carries (version 1.1), else at the declared volume (C1's fallback: today's equations)."""
    law = p.coupling_route_law
    rows, cells = p.coupling_route_row, p.coupling_route_cell
    amount = p.amount_reference[rows, cells] + state.amount_increment[rows, cells]
    v = p.volume if volume is None else volume
    log_x = xp.log(amount) - xp.log(v[cells])
    hill = hill_factors.factor(
        log_x, p.coupling_route_half_saturation_mM, p.coupling_route_coefficient, law, xp=xp
    )
    if p.regulatory_slot_cell.shape[0] > 0:  # Static: states declared.
        s = state.regulatory_state[p.coupling_route_slot]
        f = xp.where(law == STATE_FRACTION, s, xp.where(law == STATE_COMPLEMENT, 1.0 - s, hill))
    else:
        f = hill
    basal = p.coupling_route_basal
    value = basal + (1.0 - basal) * f
    on = state.coupling_enabled[p.coupling_route_coupling] > 0
    return xp.where(on, value, 1.0)


def element_product(values, table, *, xp):
    """[element] the product of each element's routes in declared order; exactly 1 elsewhere."""
    total = None
    for j in range(table.shape[1]):
        index = table[:, j]
        term = xp.where(index >= 0, values[xp.maximum(index, 0)], 1.0)
        total = term if total is None else total * term
    return total


def state_inputs(state, p, *, xp, volume=None):
    """[slot] u, the product of each state's input factors at the current amounts, each input's
    concentration at `volume` [cell] where given (version 1.1), else at the declared volume."""
    rows = p.regulatory_input_row
    cells = p.regulatory_slot_cell[:, None]
    amount = p.amount_reference[rows, cells] + state.amount_increment[rows, cells]
    v = p.volume if volume is None else volume
    log_x = xp.log(amount) - xp.log(v[p.regulatory_slot_cell])[:, None]
    log_f = hill_factors.log_factor(
        log_x,
        p.regulatory_input_half_saturation_mM,
        p.regulatory_input_coefficient,
        p.regulatory_input_kind,
        xp=xp,
    )
    return xp.exp(entity_sum(log_f, axis=1, xp=xp))


def state_half_step(state, h, p, *, xp, volume=None):
    """(state after h of every regulatory state, valid); u frozen over h (module docstring), its
    inputs' concentrations at `volume` where given (version 1.1)."""
    if p.regulatory_slot_cell.shape[0] == 0:  # Static: no state.
        return state, None
    u = state_inputs(state, p, xp=xp, volume=volume)
    k_on, k_off = p.regulatory_on_rate, p.regulatory_off_rate
    lam = k_on * u + k_off
    x = lam * h
    positive = x > 0
    phi = xp.where(positive, -xp.expm1(-x) / xp.where(positive, x, 1.0), 1.0)
    s = state.regulatory_state
    moved = s + (k_on * u * (1.0 - s) - k_off * s) * h * phi
    new_s = xp.where(lam > 0, moved, s)
    du = u * h
    total = state.regulatory_input_integral
    new_total = xp.where(du > 0, total + du, total)
    valid = xp.all(xp.isfinite(new_s) & (new_s >= 0) & (new_s <= 1))
    valid &= xp.all(xp.isfinite(new_total))
    return state._replace(regulatory_state=new_s, regulatory_input_integral=new_total), valid


def event_map(state, control, p, *, xp):
    """(state at the step start after crossings, writes, switches and the counter, consistent)."""
    count = state.coupling_step_count
    ok = None
    if p.regulatory_slot_cell.shape[0] > 0:  # Static: states declared.
        s = state.regulatory_state
        crossed = (
            p.regulatory_has_level
            & (state.regulatory_crossing_step < 0)
            & (s >= p.regulatory_level)
        )
        applied = state.regulatory_writes_applied
        target = control.regulatory_write_count
        due = target == applied + 1
        ok = xp.all((target == applied) | due)  # A stale schedule refuses the step.
        state = state._replace(
            regulatory_crossing_step=xp.where(crossed, count[0], state.regulatory_crossing_step),
            regulatory_state=xp.where(due, control.regulatory_write_value, s),
            regulatory_writes_applied=xp.where(due, applied + 1, applied),
        )
    state = state._replace(coupling_enabled=control.coupling_switch, coupling_step_count=count + 1)
    return state, ok


def factors_valid(state, p, *, xp):
    """Every route's factor finite and in [0, 1] (none declared: valid)."""
    if p.coupling_route_law.shape[0] == 0:  # Static: no route.
        return True
    f = route_factors(state, p, xp=xp)
    return xp.all(xp.isfinite(f) & (f >= 0) & (f <= 1))


def used_routes(tables, count, *, xp):
    """Version 2: [route] whether a route stands in any of `tables` ([element, width] route
    indices, -1 pads): the routes evaluated where those tables' factors are."""
    index = xp.arange(count)
    used = xp.zeros(count, dtype=bool)
    for table in tables:
        if table.size:  # Static.
            used = used | xp.any(index[:, None] == xp.reshape(table, (1, -1)), axis=1)
    return used


def range_valid(state, p, used, *, xp, density=None, site=None, volume=None):
    """Version 2: every enabled route of `used` inside its declared operating range at `state`,
    where its factor is evaluated: a species route's concentration (mM, in its cell at `volume`,
    the current volume where given, version 1.1, else the declared one), a state route's
    fraction, a population route's density (units per µm²;
    `density` [population route], given at the control view, its one point of evaluation, and
    elsewhere None, which leaves those routes out), or a site route's source (`site` [route],
    site_route_sources; None leaves those routes out). A switched-off coupling's routes are
    skipped (its factor is exactly 1)."""
    law = p.coupling_route_law
    rows, cells = p.coupling_route_row, p.coupling_route_cell
    amount = p.amount_reference[rows, cells] + state.amount_increment[rows, cells]
    source = amount / (p.volume if volume is None else volume)[cells]
    if p.regulatory_slot_cell.shape[0] > 0:  # Static: states declared.
        s = state.regulatory_state[p.coupling_route_slot]
        source = xp.where(law >= STATE_FRACTION, s, source)
    if has_population(p):  # Static (FR-7's part (b)).
        population = p.coupling_route_population >= 0
        if density is None:
            used = used & ~population
        else:
            source = xp.where(
                population, density[xp.maximum(p.coupling_route_population, 0)], source
            )
    if has_site(p):  # Static (FR-24).
        sited = p.coupling_route_site >= 0
        if site is None:
            used = used & ~sited
        else:
            source = xp.where(sited, site, source)
    inside = (source >= p.coupling_route_low) & (source <= p.coupling_route_high)
    on = state.coupling_enabled[p.coupling_route_coupling] > 0
    return xp.all(inside | ~on | ~used)


def has_population(p):
    """Version 2: whether any route reads a population (static, by shape)."""
    return p.coupling_population_channel.shape[0] > 0


def has_site(p):
    """Version 2: whether any route reads a site population (static, by shape; FR-24)."""
    return p.coupling_site_population.shape[0] > 0


def _required_quantities(quantities):
    """Version 2: the function of state a site route is evaluated from (R3), refused if none."""
    if quantities is None:
        raise ValueError(
            f"{LAW_ID_V2}: a site route is evaluated from {SITE_LAW}'s readable quantities, which "
            "the composite passes as quantities= (R3), and none was passed"
        )
    return quantities


def site_route_sources(quantities, p, *, xp):
    """Version 2: [route] each site route's source from its owner's quantities (R3): theta, or B /
    V or S / V in mM at its cell's declared volume; 1 elsewhere."""
    q = quantities[SITE_LAW]
    index = p.coupling_route_site
    j = xp.maximum(index, 0)
    population = p.coupling_site_population[j]
    kind = p.coupling_site_quantity[j]
    amount = xp.where(
        kind == OCCUPIED_Q, q["site_occupied_fmol"][population], q["site_capacity_fmol"][population]
    )
    value = xp.where(
        kind == FRACTION_Q,
        q["site_occupied_fraction"][population],
        amount / p.volume[p.coupling_route_cell],
    )
    return xp.where(index >= 0, value, 1.0)


def with_site_factors(values, state, p, source, *, xp):
    """Version 2: [route] `values` with each site route's F = b + (1 - b) f, f its law of the
    source (`source` [route], site_route_sources): theta, 1 - theta, or a Hill law, whose source may
    be exactly 0 (an empty site: ln 0 = -inf gives activation 0 and inhibition 1); exactly 1 for
    a switched-off coupling, as every route's."""
    index = p.coupling_route_site
    law = p.coupling_route_law
    positive = source > 0
    log_x = xp.where(positive, xp.log(xp.where(positive, source, 1.0)), -xp.inf)
    hill = hill_factors.factor(
        log_x,
        p.coupling_site_half_saturation[xp.maximum(index, 0)],
        p.coupling_route_coefficient,
        law - SITE_OFFSET,
        xp=xp,
    )
    f = xp.where(law == SITE_FRACTION, source, xp.where(law == SITE_COMPLEMENT, 1.0 - source, hill))
    basal = p.coupling_route_basal
    on = state.coupling_enabled[p.coupling_route_coupling] > 0
    return xp.where((index >= 0) & on, basal + (1.0 - basal) * f, values)


def _required(view):
    """Version 2: the reader view a population route is evaluated from (R2), refused if none."""
    if view is None:
        raise ValueError(
            f"{LAW_ID_V2}: a population route is evaluated at the control view, from the reader "
            "view the composite passes there (R2), and none was passed"
        )
    return view


def population_densities(view, p, *, xp):
    """Version 2: [population route] its source's density (units per µm²) in a view: rho =
    a rho_ref, from @3's current channel_abundance (FR-7's part (b))."""
    a = view.channel_abundance[p.coupling_population_channel]
    return a * p.coupling_population_reference_density_per_um2


def with_population_factors(values, state, p, density, *, xp):
    """Version 2: [route] `values` with each population route's F = b + (1 - b) f, f its Hill
    law of the source's density (`density`, [population route]); exactly 1 for a switched-off
    coupling, as every route's."""
    index = p.coupling_route_population
    j = xp.maximum(index, 0)
    hill = hill_factors.factor(
        xp.log(density[j]),
        p.coupling_population_half_saturation_per_um2[j],
        p.coupling_route_coefficient,
        p.coupling_route_law - POPULATION_OFFSET,
        xp=xp,
    )
    basal = p.coupling_route_basal
    on = state.coupling_enabled[p.coupling_route_coupling] > 0
    return xp.where((index >= 0) & on, basal + (1.0 - basal) * hill, values)


def own_valid(state, *, xp):
    s, total = state.regulatory_state, state.regulatory_input_integral
    valid = xp.all(xp.isfinite(s) & (s >= 0) & (s <= 1))
    valid &= xp.all(xp.isfinite(total) & (total >= 0))
    valid &= xp.all(state.regulatory_crossing_step >= -1)
    valid &= xp.all(state.regulatory_writes_applied >= 0)
    enabled = state.coupling_enabled
    valid &= xp.all((enabled == 0) | (enabled == 1))
    valid &= xp.all(state.coupling_step_count >= 0)
    return valid


# ------------------------------------------------------------------ definition checks


def check_identities(spec, declaration):
    """Refuse a species declared with another identity than its one authority (the species
    registry: D150's and D152's operators come first, as authors; D176)."""
    common.check_identities(spec, LAW_ID, declaration.species)


def check_unmoved_sources(declaration, moved):
    """Refuse an instantaneous coupling whose source row something moves inside the inner step
    (moved: species_registry.moved_in_step). The parse-time refusals (a charged source; a route
    through a membrane, junction or channel) stay; this one adds every other in-step mover, such
    as a pump's fuel rows under F2 or an in-step process (D176, "moved by the step")."""
    for coupling in declaration.couplings:
        if coupling.source_kind != "species":
            continue
        movers = moved.get(coupling.source, {}).get("cell", ())
        if movers:
            raise ConfigError(
                f"{LAW_ID}: coupling {coupling.id} reads {coupling.source!r} instantaneously, but "
                f"{movers[0]} moves it inside the inner step, so a factor held through the step "
                "would lag (first order): read it through a state (§1.4)"
            )


def check_replaced_slots(spec, declaration):
    """Refuse a target, state cell or junction endpoint on a slot replacement@1 replaces."""
    _, events = common.replacement_of(spec)
    replaced = {v.slot for v in events}
    if not replaced:
        return
    m = spec.model
    for state in declaration.states:
        hit = replaced & set(state.cells)
        if hit:
            raise ConfigError(
                f"{LAW_ID}: state {state.id} is declared in {sorted(hit)[0]}, a slot "
                f"{common.REPLACEMENT_LAW} replaces (version 1.1's reset rule; refused in "
                "version 1)"
            )
    for coupling in declaration.couplings:
        if type(coupling.target) is OperatorTarget:
            continue  # Version 2: check_replaced_operator_elements.
        for element in coupling.target.ids:
            if coupling.target.control == "junction":
                junction = next(j for j in m.junctions if j.id == element)
                cells = {junction.sender, junction.receiver}
            else:
                cells = set(_target_cells(m, coupling.target, element))
            hit = replaced & cells
            if hit:
                raise ConfigError(
                    f"{LAW_ID}: coupling {coupling.id} targets {element}, on "
                    f"{sorted(hit)[0]}, a slot "
                    f"{common.REPLACEMENT_LAW} replaces (refused in version 1)"
                )


def route_keys(spec, declaration):
    """Version 2: (coupling id, element id, cell id) of each route, in the binding's order: every
    inner target's routes, coupling by coupling, then every operator target's (host side)."""
    m = spec.model
    keys = [
        (c.id, element, cell)
        for c in declaration.couplings
        if type(c.target) is not OperatorTarget
        for element in c.target.ids
        for cell in _target_cells(m, c.target, element)
    ]
    declared = {op.LAW_ID: (op, d) for op, d, _ in composite_spec.entries(spec)}
    for c in declaration.couplings:
        if type(c.target) is not OperatorTarget or c.target.operator not in declared:
            continue
        op, target_declaration = declared[c.target.operator]
        keys += [
            (c.id, element, cell)
            for element, cell in op.routable_elements(target_declaration, c.target.control)
            if element in c.target.ids
        ]
    return tuple(keys)


def check_replaced_operator_elements(spec, declaration):
    """Version 2: refuse an operator target's element on a slot replacement@1 replaces (its source
    is read in that cell, which a newcomer would take over), unless its source is a species of
    that cell or a site population (FR-26's part C′, D244): replacement@1 swaps the cell's species
    and cells.operator.site_occupant_replacement@1 resets its populations, so the factor reads the newcomer's
    state. A state source there stays refused (part C, a newcomer's regulatory state, is not
    built)."""
    _, events = common.replacement_of(spec)
    replaced = {v.slot for v in events}
    if not replaced:
        return
    declared = {op.LAW_ID: (op, d) for op, d, _ in composite_spec.entries(spec)}
    for coupling in declaration.couplings:
        target = coupling.target
        if type(target) is not OperatorTarget or target.operator not in declared:
            continue
        if coupling.source_kind in ("species", "site"):  # Part C′.
            continue
        op, target_declaration = declared[target.operator]
        for element, cell in op.routable_elements(target_declaration, target.control):
            if element in target.ids and cell in replaced:
                raise ConfigError(
                    f"{LAW_ID_V2}: coupling {coupling.id} targets {target.operator}'s {element}, "
                    f"on {cell}, a slot {common.REPLACEMENT_LAW} replaces, from a state; a "
                    "newcomer's regulatory state is not built (a species or a site source is "
                    "admitted there)"
                )


def check_population_sources(spec, declaration):
    """Version 2: a population source needs cells.operator.membrane_entity_state@1 (reference_densities), and
    no in-step process may write population units or membrane area: its factor is held through
    @3's step, which is exact only while both change in half-steps and event maps."""
    readers = [c for c in declaration.couplings if type(c) is PopulationCoupling]
    if not readers:
        return
    reference_densities(spec)
    for op, _, _ in composite_spec.entries(spec):
        written = [field for field in UNIT_FIELDS if field in op.ENTITY_WRITES]
        if op.PROCESS and written:
            raise ConfigError(
                f"{LAW_ID_V2}: coupling {readers[0].id} holds a population's density through @3's "
                f"step, but {op.LAW_ID}'s in-step process writes {written[0]}: the held factor "
                "would lag it (first order)"
            )


def volume_changer(spec):
    """The definition's first changer of the cell volume (water, or a provider or writer of the
    volume), or None."""
    for op, _, _ in composite_spec.entries(spec):
        if "volume" in op.VIEW_FIELDS or "volume_increment_pL" in op.ENTITY_WRITES:
            return op
    return None


def check_one_way_records(spec, law):
    """FR-65's coupling step beside FR-50 phase 2 (D327, a combination two changes create): @3's
    own one-way records (one_way_records) beside the coupling and a changer of the cell volume are
    refused by name until a world qualifies the three together. Each pair alone was admitted by
    one change: the coupling beside the records at a fixed volume, and the records beside water."""
    if not getattr(spec.model, "one_way_records", ()):
        return
    changer = volume_changer(spec)
    if changer is not None:
        raise ConfigError(
            f"{law}: @3's own one_way records (one_way_records) beside the coupling and "
            f"{changer.LAW_ID}, a changer of the cell volume, are refused until a world qualifies "
            "the three together (FR-65's coupling step beside FR-50 phase 2, D327)"
        )


def check_site_volume(spec, declaration):
    """Version 2 (FR-65's coupling step, the lead's ruling 2): a site source in mM, occupied_mM or
    capacity_mM, reads B / V or S / V at the declared volume (D244's Q2, the user's answer), so it
    is refused by name beside a changer of the cell volume: water, or any other provider or writer
    of it. Site occupancy reads the volume as declared and is refused there itself; this refusal
    keeps the site read refused should that change."""
    sited = [
        c
        for c in declaration.couplings
        if type(c) is SiteCoupling and c.quantity != "occupied_fraction"
    ]
    if not sited:
        return
    changer = volume_changer(spec)
    if changer is not None:
        raise ConfigError(
            f"{LAW_ID_V2}: coupling {sited[0].id} reads a site population's "
            f"{sited[0].quantity} at the declared volume (D244's Q2), so it is refused beside "
            f"{changer.LAW_ID}, which changes the cell volume"
        )


def unit_writers(spec):
    """Version 2: the definition's operators that declare a write of population units or
    membrane area (ENTITY_WRITES; class level), in declared order: those that could change a
    population source's density, rho = N / A."""
    return [
        op.LAW_ID
        for op, _, _ in composite_spec.entries(spec)
        if any(field in op.ENTITY_WRITES for field in UNIT_FIELDS)
    ]


def check_rate_limit(spec, declaration):
    dt = spec.execution.dt
    for state in declaration.states:
        if dt * (state.on_rate_per_s + state.off_rate_per_s) > 1:
            raise ConfigError(
                f"{LAW_ID}: state {state.id} has dt (k_on + k_off) = "
                f"{dt * (state.on_rate_per_s + state.off_rate_per_s):.3g} > 1: a state that "
                "relaxes "
                "within one step makes @3's held value an endpoint value (ruling 5)"
            )


# ------------------------------------------------------------------ the operator


class SpeciesRegulatedAvailability(Operator):
    LAW_ID = LAW_ID
    IDENTITY_ROLE = "user"  # Species registry (D176): it reads species others declare.
    STEP_ID = STEP_ID
    EVENT = True
    SPLIT = True
    RK4 = "split"
    STATE_AXES = STATE_AXES
    STATE_DTYPES = {k: np.int64 for k in INTEGER_FIELDS}
    LAYOUT_FIELDS = LAYOUT_FIELDS
    CONTROL_FIELDS = ("coupling_switch", "regulatory_write_count", "regulatory_write_value")
    EXPERIMENT_KEYS = (CONTROLS_KEY, WRITES_KEY)
    CONTROL_FACTORS = TARGET_CONTROLS
    # Version 1.1: its own declarations (VOLUME_READS; the shared species_common.CONFLICTS_VIEW
    # stays for exchange and the unit producer). Where no operator changes the volume it receives
    # no view and reads the declared one (C1), so every world admitted before keeps its program.
    CONFLICTS_VIEW = MASKS
    VIEW_READS = ("volume",)
    SCOPED_READS = MappingProxyType({"volume": VOLUME_READS})
    READOUT_COLUMNS = ("coupling_factor",)

    # ------------------------------------------------------------ definition

    def parse(self, raw, base, inner_model):
        return parse_declaration(raw, base)

    def to_dict(self, declaration, base):
        return declaration_to_dict(declaration)

    def parse_schedule(self, raw, base, declaration):
        return parse_schedule(raw, base, declaration)

    def schedule_to_dict(self, schedule, base, declaration):
        return schedule_to_dict(schedule)

    def schedule_times(self, schedule):
        times = {t for _, changes in schedule.switches for t, _ in changes if t > 0}
        times |= {t for _, entries in schedule.writes for t, _ in entries if t > 0}
        return tuple(sorted(times))

    def value_at(self, schedule, time):
        return (
            tuple(_switch_at(changes, time) for _, changes in schedule.switches),
            tuple(_writes_at(entries, time) for _, entries in schedule.writes),
        )

    def control_values(self, spec, declaration, schedule, records, indices, times):
        count = len(records)
        switch = np.zeros((count, len(schedule.switches)))
        written = np.zeros((count, len(schedule.writes)), dtype=np.int64)
        value = np.zeros((count, len(schedule.writes)))
        for i, (switches, writes) in enumerate(records):
            switch[i] = switches
            for j, (number, last) in enumerate(writes):
                written[i, j], value[i, j] = number, last
        return switch[indices], written[indices], value[indices]

    def species_identities(self, declaration):
        return declaration.species

    def check_definition(self, spec, declaration, schedule, model):
        common.check_species_cap(spec, LAW_ID)
        check_identities(spec, declaration)
        # Version 1.1: water is the one changer of the volume it reads (it reads no outside node),
        # and not beside @3's own one-way records (D327, beside FR-50 phase 2).
        common.check_volume_changers(spec, LAW_ID, ())
        check_one_way_records(spec, LAW_ID)
        check_unmoved_sources(declaration, species_registry.moved_in_step(spec))
        check_replaced_slots(spec, declaration)
        check_rate_limit(spec, declaration)

    def batch_signature(self, declaration):
        """The static structure; identities and every parameter are not part of it."""
        return (
            LAW_ID,
            tuple(s.id for s in declaration.species),
            tuple(
                (s.id, s.cells, tuple((i.law, i.species) for i in s.inputs))
                for s in declaration.states
            ),
            tuple(
                (
                    c.target.operator,
                    c.target.control,
                    c.target.ids,
                    c.target.side,
                    c.source_kind,
                    c.source,
                    c.law,
                )
                for c in declaration.couplings
            ),
        )

    def working_size(self, spec):
        x = spec.execution
        return 8 * 16 * (x.capacity + x.edge_capacity + x.channel_capacity)

    def summary(self, spec, declaration, schedule, history):
        unrecorded = []
        if hasattr(history, "regulatory_state") and len(np.asarray(history.regulatory_state)):
            final = np.asarray(history.regulatory_state)[-1]
            record = np.asarray(history.regulatory_crossing_step)[-1]
            levels = {s.id: s.crossing_level for s in declaration.states}
            for k, (state_id, cell) in enumerate(slots(declaration)):
                level = levels[state_id]
                if level is not None and record[k] < 0 and final[k] >= level:
                    unrecorded.append([state_id, cell])
        return {
            "coupling_law": LAW_ID,
            "coupling_step": STEP_ID,
            "coupling_mechanism": "regulation of availability (a factor in [b, 1] on the schedule)",
            "coupling_species": {
                s.id: dict(
                    catalogue=None if s.catalogue is None else list(s.catalogue),
                    evidence=s.evidence,
                )
                for s in declaration.species
            },
            "coupling_states": {
                s.id: dict(
                    law=s.law,
                    cells=list(s.cells),
                    inputs=[
                        (i.law, i.species, i.half_saturation_mM, i.hill_coefficient)
                        for i in s.inputs
                    ],
                    on_rate_per_s=s.on_rate_per_s,
                    off_rate_per_s=s.off_rate_per_s,
                    initial=dict(zip(s.cells, s.initial, strict=True)),
                    crossing_level=s.crossing_level,
                )
                for s in declaration.states
            },
            "coupling_targets": {
                c.id: dict(
                    control=c.target.control,
                    ids=list(c.target.ids),
                    side=c.target.side,
                    source={c.source_kind: c.source},
                    law=c.law,
                    half_saturation_mM=c.half_saturation_mM,
                    hill_coefficient=c.hill_coefficient,
                    basal=c.basal,
                )
                for c in declaration.couplings
            },
            # A crossing in the final step has no later step start to record it (§1.5).
            "coupling_unrecorded_final_crossings": unrecorded,
        }

    # ------------------------------------------------------------ binding

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        return bind(spec, declaration, schedule)

    # ------------------------------------------------------------ step parts

    def statically_idle(self, p):
        return p.regulatory_slot_cell.shape[0] == 0 and p.coupling_route_law.shape[0] == 0

    def control_factors(self, state, p, *, xp, view=None):
        """Its factors at the control view; a species source's concentration at the current volume
        where its view carries it (R2′), else at the declared one (static)."""
        factors, values = {}, None
        for name in self.CONTROL_FACTORS:
            table = getattr(p, TARGET_TABLES[name])
            if table.shape[1] == 0:  # Static: no route on this control.
                continue
            if values is None:
                values = route_factors(state, p, xp=xp, volume=carried(view, "volume", state))
            factors[name] = element_product(values, table, xp=xp)
        return factors

    def event(self, state, control, p, *, xp, view=None):
        """The event map (view=: a door S reader's view, which the event map does not read)."""
        return event_map(state, control, p, xp=xp)

    def half_step(self, state, h, control, p, *, xp, view=None):
        """Its states' half-steps; their inputs at the current volume where the composite passes its
        reader view (a changer of the volume is composed: C1), else at the declared one."""
        return state_half_step(state, h, p, xp=xp, volume=None if view is None else view.volume)

    def control_valid(self, control, p, *, xp):
        switch = control.coupling_switch
        valid = xp.all((switch == 0) | (switch == 1))
        value = control.regulatory_write_value
        valid &= xp.all(xp.isfinite(value) & (value >= 0) & (value <= 1))
        valid &= xp.all(control.regulatory_write_count >= 0)
        return valid

    def rate_checks(self, state, control, p, valid, *, xp):
        return valid & own_valid(state, xp=xp) & factors_valid(state, p, xp=xp)

    def domain_valid(self, state, p, valid, *, xp):
        own = own_valid(state, xp=xp) & factors_valid(state, p, xp=xp)
        return own if valid is None else valid & own

    # ------------------------------------------------------------ observations

    def observe(self, row, state, control, p, view, model, spec):
        """Its state and each route's factor at the row's state, at the row's view's volume (the
        declared array itself where nothing changes the volume)."""
        columns = {k: getattr(state, k) for k in self.STATE_AXES}
        if p.coupling_route_law.shape[0]:
            columns["coupling_factor"] = np.asarray(
                route_factors(state, p, xp=np, volume=view.volume)
            )
        else:
            columns["coupling_factor"] = np.zeros(0)
        return columns


# ------------------------------------------------------------------ version 2


@contextmanager
def _named_v2():
    """Version 2's refusals from the helpers it shares with @1, which name @1, name version 2."""
    try:
        yield
    except ConfigError as error:
        raise ConfigError(str(error).replace(LAW_ID, LAW_ID_V2)) from None


class SpeciesRegulatedAvailabilityV2(SpeciesRegulatedAvailability):
    """cells.operator.species_regulated_availability@2: @1 plus operator targets (the module docstring; B1′,
    docs/INVENTORY_COUPLING_DESIGN.md §2.1) and the population source (FR-7's part (b)). It
    shares @1's laws, states, events and inner targets; its layout adds the operator targets'
    element tables, every route's operating range and the population routes' arrays. A
    population route is evaluated from its reader view of channel_abundance where the composite
    passes it (R2): control_factors, factor_valid and factor_record at the control view, and
    observe from the row's view. Elsewhere (@1's rate_checks and domain_valid, and the target
    half-steps' factor_record, where it stands in no table) its factor is @1's padding, exactly
    1; at a step's end membrane state's domain (finite units, at least 0, positive area) keeps
    its density finite and nonnegative, so its factor lies in [b, 1]. Development, not judged."""

    LAW_ID = LAW_ID_V2
    LAYOUT_FIELDS = LAYOUT_FIELDS_V2
    STATE_AXES = STATE_AXES_V2
    FACTOR_RECORD = "coupling_applied_factor"
    RATE_ROUTES = tuple(OPERATOR_TABLES)
    # R2 (step 0 of FR-7's part (b)): the populations' abundance read at the control view; and
    # version 1.1's volume reads, as @1's (VOLUME_READS). R2′ passes each control-view field only
    # where some operator changes it, so a population world's view carries no volume.
    VIEW_READS = ("channel_abundance", "volume")
    SCOPED_READS = MappingProxyType(
        {"channel_abundance": Read("current", "inner"), "volume": VOLUME_READS}
    )
    # R3 (FR-24): a site source reads cells.operator.site_occupancy@1's readable quantities.
    QUANTITY_READS = MappingProxyType({SITE_LAW: tuple(SITE_READS.values())})
    # Its run view (the contract; an operator registered after the run view declares it).
    VIEW_LAYERS = (
        {
            "id": "regulation",
            "label": "Regulated availability and rates",
            "representation": "modelled",
        },
    )
    UNITS = {
        "regulatory_state": "1",
        "regulatory_input_integral": "s",
        "regulatory_crossing_step": "1",
        "regulatory_writes_applied": "1",
        "coupling_enabled": "1",
        "coupling_step_count": "1",
        "coupling_factor": "1",
        "coupling_applied_factor": "1",
    }
    RECORD_KINDS = {
        "regulatory_state": "level",
        "regulatory_input_integral": "cumulative",
        "regulatory_crossing_step": "level",
        "regulatory_writes_applied": "cumulative",
        "coupling_enabled": "level",
        "coupling_step_count": "cumulative",
        "coupling_applied_factor": "level",
    }

    def view_sets(self, spec, declaration):
        """The run view's sets of its own axes: each regulatory slot (a state in a cell), each
        coupling with its target, and the one step counter."""
        keys = slots(declaration)
        return {
            "regulatory_slot": {
                "id": "regulatory_slot",
                "ids": tuple(f"{state}:{cell}" for state, cell in keys),
                "holds": "regulatory state in a cell",
                "at": tuple({"cell": cell} for _, cell in keys),
            },
            "coupling": {
                "id": "coupling",
                "ids": tuple(c.id for c in declaration.couplings),
                "holds": "coupling",
                "kinds": tuple(
                    f"{c.target.operator}: {c.target.control}" for c in declaration.couplings
                ),
            },
            "one": {"id": "regulation_step_counter", "ids": ("steps",), "holds": "step counter"},
            "coupling_route": {
                "id": "coupling_route",
                "ids": tuple(
                    f"{c}:{element}:{cell}" for c, element, cell in route_keys(spec, declaration)
                ),
                "holds": "coupling route (a coupling's factor read in one cell, on one element)",
                "at": tuple({"cell": cell} for _, _, cell in route_keys(spec, declaration)),
            },
        }

    def view_events(self, spec, declaration, schedule):
        """Its events in the run view: each coupling's switch changes after the start, and each
        regulatory write, at its cell."""
        layer = self.VIEW_LAYERS[0]["id"]
        events = [
            dict(
                time=float(t),
                kind="switch",
                layer=layer,
                at={"coupling": coupling},
                label=f"coupling {coupling} {'on' if value else 'off'}",
            )
            for coupling, changes in schedule.switches
            for t, value in changes
            if t > 0
        ]
        events += [
            dict(
                time=float(t),
                kind="write",
                layer=layer,
                at={"cell": cell},
                label=f"regulatory state {state} in {cell} written to {value!r}",
            )
            for (state, cell), entries in schedule.writes
            for t, value in entries
        ]
        return tuple(sorted(events, key=lambda e: (e["time"], e["label"])))

    def parse(self, raw, base, inner_model):
        with _named_v2():
            return parse_declaration(raw, base, version=2)

    def parse_schedule(self, raw, base, declaration):
        with _named_v2():
            return parse_schedule(raw, base, declaration)

    def check_definition(self, spec, declaration, schedule, model):
        with _named_v2():
            common.check_species_cap(spec, LAW_ID_V2)
            common.check_identities(spec, LAW_ID_V2, declaration.species)
            # Version 1.1: water is the one changer of the volume it reads (no outside node), and a
            # site source in mM, read at the declared volume, is refused beside any changer.
            common.check_volume_changers(spec, LAW_ID_V2, ())
            check_one_way_records(spec, LAW_ID_V2)
            check_site_volume(spec, declaration)
            check_unmoved_sources(declaration, species_registry.moved_in_step(spec))
            check_replaced_slots(spec, declaration)
            check_replaced_operator_elements(spec, declaration)
            check_population_sources(spec, declaration)
            check_rate_limit(spec, declaration)

    def batch_signature(self, declaration):
        return (LAW_ID_V2, *super().batch_signature(declaration)[1:])

    def summary(self, spec, declaration, schedule, history):
        out = super().summary(spec, declaration, schedule, history)
        out["coupling_law"] = LAW_ID_V2
        for c in declaration.couplings:
            if type(c.target) is OperatorTarget:
                out["coupling_targets"][c.id].update(
                    operator=c.target.operator,
                    evaluation=c.target.evaluation,
                    operating_range=list(c.target.operating_range),
                )
        population = [c for c in declaration.couplings if type(c) is PopulationCoupling]
        if population:  # FR-7's part (b): its K and range per µm², and the constant source.
            writers = unit_writers(spec)
            for c in population:
                entry = out["coupling_targets"][c.id]
                del entry["half_saturation_mM"]
                entry.update(
                    half_saturation_per_um2=c.half_saturation_per_um2,
                    evaluation=c.target.evaluation,
                    operating_range_per_um2=list(c.target.operating_range),
                    source_writers=writers,
                )
            # Class level (ENTITY_WRITES): a declared writer may leave this population alone.
            out["coupling_constant_sources"] = (
                {} if writers else {c.id: CONSTANT_SOURCE for c in population}
            )
        site = [c for c in declaration.couplings if type(c) is SiteCoupling]
        for c in site:  # FR-24: its quantity, its K in the quantity's unit, and its range.
            entry = out["coupling_targets"][c.id]
            del entry["half_saturation_mM"]
            entry.update(
                source={"site_population": c.source, "quantity": c.quantity},
                half_saturation=c.half_saturation,
                evaluation=c.target.evaluation,
                operating_range=list(c.target.operating_range),
                owner=SITE_LAW,
            )
        constant = {c.id: CONSTANT_CAPACITY for c in site if c.quantity == "capacity_mM"}
        if constant:
            out.setdefault("coupling_constant_sources", {}).update(constant)
        return out

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        """@1's binding plus @2's tables and ranges, and the record's start: each route's factor
        at the bound state (no factor has been applied yet)."""
        with _named_v2():
            state, layout = bind(spec, declaration, schedule)
        read = SimpleNamespace(**inner_state._asdict(), **state)
        bound = SimpleNamespace(**inner_layout._asdict(), **layout)
        values = route_factors(read, bound, xp=np)
        if has_population(bound):  # The declared abundance: no increment at the bound state.
            density = population_densities(bound, bound, xp=np)
            values = with_population_factors(values, read, bound, density, xp=np)
        if has_site(bound):  # FR-24: the owner's quantities at its own bound state.
            source = site_route_sources(
                bound_site_quantities(spec, inner_state, inner_layout), bound, xp=np
            )
            values = with_site_factors(values, read, bound, source, xp=np)
        state["coupling_applied_factor"] = np.asarray(values, float)
        return state, layout

    def _values(self, state, p, view, quantities, *, xp):
        """[route] every route's factor at `state`, a population route's from `view` (its reader
        view, R2), called only with a population route, and a site route's from `quantities` (its
        owner's, R3), called only with a site route (static)."""
        values = route_factors(state, p, xp=xp, volume=carried(view, "volume", state))
        if has_population(p):
            density = population_densities(_required(view)(state), p, xp=xp)
            values = with_population_factors(values, state, p, density, xp=xp)
        if has_site(p):
            source = site_route_sources(_required_quantities(quantities)(state), p, xp=xp)
            values = with_site_factors(values, state, p, source, xp=xp)
        return values

    def _site_sources(self, state, p, quantities, *, xp):
        """[route] the site routes' sources at `state` (R3), or None without one (static)."""
        if not has_site(p):
            return None
        return site_route_sources(_required_quantities(quantities)(state), p, xp=xp)

    def control_factors(self, state, p, *, xp, view=None, quantities=None):
        """@1's factors, with each population route's from `view` and each site route's from
        `quantities` (static: without either, @1's call)."""
        if not (has_population(p) or has_site(p)):
            return super().control_factors(state, p, xp=xp, view=view)
        values = self._values(state, p, view, quantities, xp=xp)
        return {
            name: element_product(values, getattr(p, TARGET_TABLES[name]), xp=xp)
            for name in self.CONTROL_FACTORS
            if getattr(p, TARGET_TABLES[name]).shape[1]
        }

    def factor_valid(self, state, p, *, xp, view=None, quantities=None):
        """Its step_view routes' sources inside their declared ranges at the control view, where
        their factors are evaluated (enabled routes only), a population's density from `view` and
        a site route's source from `quantities`; None without one (static)."""
        tables = [getattr(p, field) for field in TARGET_TABLES.values()]
        if not any(table.shape[1] for table in tables):
            return None
        used = used_routes(tables, p.coupling_route_law.shape[0], xp=xp)
        density = None
        if has_population(p):  # Static.
            density = population_densities(_required(view)(state), p, xp=xp)
        site = self._site_sources(state, p, quantities, xp=xp)
        volume = carried(view, "volume", state)  # R2′: the current volume, where carried.
        return range_valid(state, p, used, xp=xp, density=density, site=site, volume=volume)

    def factor_record(self, state, p, target, field, *, xp, view=None, quantities=None):
        """(each route's factor at `state`, the routes evaluated there): the step_view routes at
        the control view (target None), or one operator target's at its half-step. No population
        route stands in an operator table; a site route may (FR-24)."""
        if target is None:
            tables = [getattr(p, name) for name in TARGET_TABLES.values()]
            values = self._values(state, p, view, quantities, xp=xp)
        else:
            tables = [getattr(p, OPERATOR_TABLES[(target, field)])]
            values = route_factors(state, p, xp=xp, volume=carried(view, "volume", state))
            site = self._site_sources(state, p, quantities, xp=xp)
            if site is not None:
                values = with_site_factors(values, state, p, site, xp=xp)
        used = used_routes(tables, p.coupling_route_law.shape[0], xp=xp)
        return values, used

    def declared_quantity_reads(self, declaration):
        """R3 (FR-24): each site coupling's read, (owner, quantity, its operator target's law, or
        None for an inner target, read at the control view)."""
        return tuple(
            dict.fromkeys(
                (
                    SITE_LAW,
                    SITE_READS[c.quantity],
                    c.target.operator if type(c.target) is OperatorTarget else None,
                )
                for c in declaration.couplings
                if type(c) is SiteCoupling
            )
        )

    def declared_rate_routes(self, declaration):
        return tuple(
            dict.fromkeys(
                (c.target.operator, c.target.control)
                for c in declaration.couplings
                if type(c.target) is OperatorTarget
            )
        )

    def rate_route_sources(self, declaration):
        """B1′: each operator-target coupling with a species source, as (target law, control,
        element ids, species), the species read in each element's cell. A state or site source
        is moved only by its owner's own half-steps, never by the target's."""
        return tuple(
            (c.target.operator, c.target.control, c.target.ids, c.source)
            for c in declaration.couplings
            if type(c.target) is OperatorTarget and c.source_kind == "species"
        )

    def rate_factors(self, state, p, target, field, *, xp, quantities=None, view=None):
        """(the product of the routes on each element of the target's control, every enabled
        route's source in its range) from the state the target's half-step receives, a site
        route's from `quantities` (R3), and a species route's concentration at the current volume
        where its reader view carries it (R2′); None without a route on that control (static, by
        its table's shape)."""
        table = getattr(p, OPERATOR_TABLES[(target, field)])
        if table.shape[1] == 0:
            return None
        volume = carried(view, "volume", state)
        values = route_factors(state, p, xp=xp, volume=volume)
        site = self._site_sources(state, p, quantities, xp=xp)
        if site is not None:
            values = with_site_factors(values, state, p, site, xp=xp)
        used = used_routes((table,), values.shape[0], xp=xp)
        valid = range_valid(state, p, used, xp=xp, site=site, volume=volume)
        return element_product(values, table, xp=xp), valid

    def observe(self, row, state, control, p, view, model, spec, quantities=None):
        """@1's columns; a population route's coupling_factor from the row's view, and a site
        route's from `quantities` (R3)."""
        columns = super().observe(row, state, control, p, view, model, spec)
        factor = columns["coupling_factor"]
        if has_population(p):
            density = population_densities(view, p, xp=np)
            factor = with_population_factors(factor, state, p, density, xp=np)
        site = self._site_sources(state, p, quantities, xp=np)
        if site is not None:
            factor = with_site_factors(factor, state, p, site, xp=np)
        columns["coupling_factor"] = np.asarray(factor)
        return columns
