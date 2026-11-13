"""Operator membrane_entity_state@1: membrane area, capacitance and population abundance as state.

docs/PUMP_COMPOSITE_V2_DESIGN.md §3 (decision 5) and docs/CELL_DIVISION_DESIGN.md §2. A state
owner with no dynamics of its own. It holds, as anchored increments from the declared values:
* per patch, area A and capacitance C. C is kept beside A because a declared patch need not
  satisfy C = c_d A; writers keep dC = c_d dA;
* per population, abundance N in units, from the declared abundance a0 as
  N0 = a0 A0 rho_ref, with rho_ref the population's declared reference density (units/m^2).
Its writers are later operators, each booking its contributions in its own accumulators:
scheduled_membrane_insertion@1 now; partition, mechanics and trafficking later.

View (R2): @3's membrane_area = A0 + dA, membrane_capacitance = C0 + dC and
channel_abundance = a0 A0 / A + dN / (A rho_ref). Zero increments give the declared values
bit for bit (R8). A fixed number of units keeps its conductance (P a A = P N / rho_ref)
whatever the area; only writers add units. The field arrays follow the capacitance through the
adapter's refresh (R3). The capacitor energy at the view is booked against @3's term on the
declared layout by the writer that changes it (adapter.view_capacitor_terms).

Populations: each of @3's channel populations is declared once, with a functional_unit ID and
an opaque catalogue reference: null, or {"catalogue": id, "entry": key}
(docs/PROTEIN_CATALOGUE_PLAN.md). The references reach the summary and the definition (whose
hash the run manifest records) and never the arrays, so changing one leaves bindings, jaxprs
and trajectories bitwise unchanged.

Ledgers: per patch and population, the increment equals the writers' booked contributions
(membrane_area_entity, membrane_capacitance_entity, population_abundance_entity). Domain:
finite increments, none on undeclared patches or padding, A > 0 and C > 0 on declared patches,
and N >= 0.
"""

from dataclasses import dataclass

import numpy as np

from cells.core.multispecies_spec import identifier
from cells.core.specs import ConfigError, _fields, _number
from cells.models import surface_pump as first
from cells.models.operators.contract import Operator

LAW_ID = "membrane_entity_state@1"

STATE_AXES = {
    "membrane_area_increment_m2": ["membrane_slot"],
    "membrane_capacitance_increment_F": ["membrane_slot"],
    "population_abundance_increment": ["channel_slot"],  # Units.
}
LEDGERS = ("membrane_area_entity", "membrane_capacitance_entity", "population_abundance_entity")
LEDGER_DIAGNOSTICS = (
    "membrane_area_balance_error_m2",
    "membrane_capacitance_balance_error_F",
    "population_abundance_balance_error",
)
LEDGER_MESSAGE = "Membrane entity accounting failed: "
# Floors of the entity ledgers. Each writer adds the same increments to its accumulator and
# to the entity field, so the ledgers are exact; the floors and per-step rounding are margins.
FLOORS = (1e-24, 1e-26, 1e-9)  # m^2, F, units.
READOUT_COLUMNS = ("membrane_area_m2", "membrane_capacitance_F", "population_units")


@dataclass(frozen=True)
class Population:
    channel_id: str
    functional_unit: str
    catalogue: tuple | None  # (catalogue id, entry key), or None (unassigned).
    reference_density_per_m2: float


@dataclass(frozen=True)
class MembraneState:
    law: str
    populations: tuple


def parse_catalogue(raw):
    if raw is None:
        return None
    _fields(raw, {"catalogue", "entry"}, "catalogue reference")
    if any(type(raw[k]) is not str or not raw[k] for k in ("catalogue", "entry")):
        raise ConfigError("A catalogue reference names a catalogue and an entry")
    return (raw["catalogue"], raw["entry"])


def parse_state(raw, base):
    _fields(raw, {"law", "populations"}, "membrane state")
    if raw["law"] != LAW_ID:
        raise ConfigError("Membrane state requires law " + LAW_ID)
    if type(raw["populations"]) is not list:
        raise ConfigError("Membrane state populations require an explicit list")
    populations = []
    for entry in raw["populations"]:
        _fields(
            entry,
            {"channel_id", "functional_unit", "catalogue", "reference_density_per_m2"},
            "membrane population",
        )
        density = _number(entry["reference_density_per_m2"], "reference density", positive=True)
        populations.append(
            Population(
                identifier(entry["channel_id"]),
                identifier(entry["functional_unit"]),
                parse_catalogue(entry["catalogue"]),
                density,
            )
        )
    declared = [p.channel_id for p in populations]
    channels = [c.id for c in base.model.channels]
    if sorted(declared) != sorted(channels):
        raise ConfigError("Membrane state declares every channel population exactly once")
    order = {c: i for i, c in enumerate(channels)}
    return MembraneState(LAW_ID, tuple(sorted(populations, key=lambda p: order[p.channel_id])))


def state_to_dict(declaration):
    if type(declaration) is not MembraneState or any(
        type(p) is not Population for p in declaration.populations
    ):
        raise ConfigError("Require explicit immutable membrane state declaration types")
    return dict(
        law=declaration.law,
        populations=[
            dict(
                channel_id=p.channel_id,
                functional_unit=p.functional_unit,
                catalogue=None
                if p.catalogue is None
                else dict(catalogue=p.catalogue[0], entry=p.catalogue[1]),
                reference_density_per_m2=p.reference_density_per_m2,
            )
            for p in declaration.populations
        ],
    )


def bind(spec, declaration):
    x = spec.execution
    nm, nc = x.membrane_capacity, x.channel_capacity
    density = np.ones(nc)  # Padding keeps 1; its abundance view is the declared 0.
    for i, p in enumerate(declaration.populations):
        density[i] = p.reference_density_per_m2
    state = {
        "membrane_area_increment_m2": np.zeros(nm),
        "membrane_capacitance_increment_F": np.zeros(nm),
        "population_abundance_increment": np.zeros(nc),
    }
    return state, dict(population_reference_density_per_m2=density)


# ------------------------------------------------------------------ the entity quantities


def area(state, p, *, xp):
    return p.membrane_area + state.membrane_area_increment_m2


def capacitance(state, p, *, xp):
    return p.membrane_capacitance + state.membrane_capacitance_increment_F


def units(state, p, *, xp):
    """Each population's abundance N (units): a0 A0 rho_ref plus its increment."""
    patch = p.channel_membranes
    declared = p.channel_abundance * p.membrane_area[patch] * p.population_reference_density_per_m2
    return xp.where(p.channel_active, declared + state.population_abundance_increment, 0.0)


def abundance(state, p, *, xp):
    """@3's channel_abundance at the current area: a0 A0 / A + dN / (A rho_ref)."""
    patch = p.channel_membranes
    a = area(state, p, xp=xp)[patch]
    value = p.channel_abundance * (p.membrane_area[patch] / a) + (
        state.population_abundance_increment / (a * p.population_reference_density_per_m2)
    )
    return xp.where(p.channel_active, value, p.channel_abundance)


def domain_valid(state, p, *, xp):
    valid = xp.asarray(True)
    for name, mask in (
        ("membrane_area_increment_m2", p.membrane_active),
        ("membrane_capacitance_increment_F", p.membrane_active),
        ("population_abundance_increment", p.channel_active),
    ):
        value = getattr(state, name)
        valid &= xp.all(xp.isfinite(value)) & xp.all(xp.where(mask, True, value == 0))
    positive = (area(state, p, xp=xp) > 0) & (capacitance(state, p, xp=xp) > 0)
    valid &= xp.all(xp.where(p.membrane_active, positive, True))
    return valid & xp.all(units(state, p, xp=xp) >= 0)


class MembraneEntityState(Operator):
    LAW_ID = LAW_ID
    STATE_AXES = STATE_AXES
    LAYOUT_FIELDS = ("population_reference_density_per_m2",)
    VIEW_FIELDS = ("membrane_area", "membrane_capacitance", "channel_abundance")
    ACCEPTS_WRITES = {
        "membrane_area_increment_m2": ("membrane_area_entity",),
        "membrane_capacitance_increment_F": ("membrane_capacitance_entity",),
        "population_abundance_increment": ("population_abundance_entity",),
    }
    LEDGERS = LEDGERS
    LEDGER_DIAGNOSTICS = LEDGER_DIAGNOSTICS
    LEDGER_MESSAGE = LEDGER_MESSAGE
    READOUT_COLUMNS = READOUT_COLUMNS

    # ------------------------------------------------------------ definition

    def parse(self, raw, base, inner_model):
        return parse_state(raw, base)

    def to_dict(self, declaration, base):
        return state_to_dict(declaration)

    def batch_signature(self, declaration):
        # Catalogue references and densities are not array axes; worlds that differ in them
        # batch together.
        return (LAW_ID, tuple(p.channel_id for p in declaration.populations))

    def working_size(self, spec):
        x = spec.execution
        return 2 * (2 * x.membrane_capacity + x.channel_capacity)

    def summary(self, spec, declaration, schedule, history):
        return {
            "membrane_state_law": LAW_ID,
            "membrane_populations": {
                p.channel_id: dict(
                    functional_unit=p.functional_unit,
                    catalogue=None
                    if p.catalogue is None
                    else dict(catalogue=p.catalogue[0], entry=p.catalogue[1]),
                    reference_density_per_m2=p.reference_density_per_m2,
                )
                for p in declaration.populations
            },
        }

    # ------------------------------------------------------------ binding

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        return bind(spec, declaration)

    # ------------------------------------------------------------ view and domain

    def view(self, state, p, q, *, xp):
        return dict(
            membrane_area=area(state, p, xp=xp),
            membrane_capacitance=capacitance(state, p, xp=xp),
            channel_abundance=abundance(state, p, xp=xp),
        )

    def rate_checks(self, state, control, p, valid, *, xp):
        return valid & domain_valid(state, p, xp=xp)

    def domain_valid(self, state, p, valid, *, xp):
        own = domain_valid(state, p, xp=xp)
        return own if valid is None else valid & own

    # ------------------------------------------------------------ ledgers

    def ledger_terms(self, result, row, p, *, xp):
        return result, self.own_ledgers(row, p, xp=xp)

    def own_ledgers(self, row, p, *, xp):
        return dict(
            membrane_area_entity=row.membrane_area_increment_m2,
            membrane_capacitance_entity=row.membrane_capacitance_increment_F,
            population_abundance_entity=row.population_abundance_increment,
        )

    def own_magnitudes(self, row, p, *, xp):
        return (
            xp.abs(row.membrane_area_increment_m2),
            xp.abs(row.membrane_capacitance_increment_F),
            xp.abs(row.population_abundance_increment),
        )

    def own_bounds(self, magnitudes, steps):
        rounding = first.LEDGER_STEP_ROUNDING * np.finfo(float).eps * steps
        return tuple(floor + rounding * m for floor, m in zip(FLOORS, magnitudes, strict=True))

    # ------------------------------------------------------------ observations

    def observe(self, row, state, control, p, view, model, spec):
        columns = {k: getattr(state, k) for k in self.STATE_AXES}
        columns.update(
            membrane_area_m2=np.asarray(area(state, p, xp=np)),
            membrane_capacitance_F=np.asarray(capacitance(state, p, xp=np)),
            population_units=np.asarray(units(state, p, xp=np)),
        )
        return columns
