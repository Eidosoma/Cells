"""Operator ideal_osmosis_linear_compliance_water@1: osmotic water and compliant volumes.

The law, its Heun half-steps at frozen amounts and its ledgers, moved here unchanged
from resolved_pump_water@1 (models/surface_pump_water.py, now a thin composition;
docs/PUMP_WATER_MODEL.md). Water is numerics/osmotic_water.LAW_ID on the
membranes: the flow across a patch is Q = 1e15 A Lp a (psi_cell - psi_outside) pL/s
with psi = P - Pi, Pi = R T (sum of declared amounts + neutral impermeants) / V and
P = K (V / Vref - 1) + P0. Finite nodes change volume; a held bath keeps its volume
and composition, so its water potential is fixed and the water it exchanges is
booked as supply, with the work 1e-3 psi_b dS. W_h advances the volumes at frozen
amounts by Heun's method (explicit trapezoid); each water step refuses itself if
dt times the water relaxation rate at its actual state exceeds
MAX_WATER_RELAXATION_PER_STEP.

Contract (models/operators/contract.py):
* owned state: the volume increments, water transfers, water heat, bath supply and
  bath water work;
* view: the current cell and outside volumes as @3's ``volume`` and
  ``extracellular_volume``; the view follows the split, so @3's domain is evaluated
  at the current volumes and re-checked at the step end. The water conductances are
  bound from the declared patch areas, so no other operator may provide an area;
* parts: a split process (Heun half-steps, heun_frozen_amount_water@1); under RK4
  its rates join the coupled right-hand side;
* ledgers: its four water ledgers (cell, outside and total water, bath work) with
  their floors and rounding allowances, and the dilution, elastic, heat and bath
  work terms of the energy ledger;
* refusal: a volume at its bound at any water stage or step end, dt x the water
  relaxation rate above 0.05, a water availability outside [0, 1], and @3's
  explicit bounds at the declared minimum volumes.
"""

from bisect import bisect_right
from dataclasses import asdict, replace
from functools import cached_property
from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

from cells.core import pump_composite_spec as composite_spec
from cells.core import surface_pump_spec as first_spec
from cells.core import surface_pump_v3_spec as ionic_spec
from cells.core import surface_pump_water_spec as water_spec
from cells.core.specs import ConfigError
from cells.models import surface_pump as first
from cells.models import surface_pump_v2 as second
from cells.models import surface_pump_v3 as ionic
from cells.models.operators.contract import Operator
from cells.numerics import osmotic_water as water
from cells.numerics.extracellular_field import scatter
from cells.processes.electrochemistry import R

LAW_ID = water.LAW_ID
EXPLICIT_STEP_BOUND = ionic.EXPLICIT_STEP_BOUND
physical_amounts = ionic.physical_amounts

# ------------------------------------------------------------------ the water law
WATER_STEP_ID = "heun_frozen_amount_water@1"


# dt x (water relaxation rate) per step: the bound of the existing water
# families (models/surface_water.py); physiological values give 1e-5-2e-3 at 1 ms.
MAX_WATER_RELAXATION_PER_STEP = 0.05


VOLUME_ATOL_PL = 2e-12  # Fixed floor of the water ledgers (plus the per-step rounding).


WORK_ATOL_PJ = 3e-12  # Fixed floor of the bath water-work ledger (the family's work floor).


WATER_STATE_AXES = {
    "volume_increment_pL": ["cell_slot"],
    "extracellular_volume_increment_pL": ["extracellular_slot"],  # Finite nodes only.
    "water_transferred_pL": ["membrane_slot"],  # Cell to outside positive.
    "water_dissipated_energy_pJ": ["membrane_slot"],
    "bath_water_supplied_pL": ["extracellular_slot"],  # Into the system; baths only.
    "bath_water_work_pJ": ["extracellular_slot"],
}


WATER_LAYOUT_FIELDS = (
    *("water_" + k for k in water.Parameters._fields),
    "water_bath",
    "water_bath_potential_Pa",
)


def water_parameters(p):
    return water.Parameters(*(getattr(p, "water_" + k) for k in water.Parameters._fields))


def volumes(state, p, *, xp=jnp):
    """Current node volumes (pL), cells then outside slots; baths stay nominal."""
    return xp.concatenate(
        (
            p.volume + state.volume_increment_pL,
            p.extracellular_volume + state.extracellular_volume_increment_pL,
        )
    )


def amounts(state, p, *, xp=jnp):
    return xp.concatenate(physical_amounts(state, p), axis=-1)


def finite_nodes(p, *, xp=jnp):
    """Water nodes whose volume evolves: active cells and active non-bath outside nodes."""
    n = p.active.size
    return p.water_active & ~xp.concatenate((xp.zeros(n, dtype=bool), p.water_bath))


class WaterRates(NamedTuple):
    cell: object  # dV/dt of cells (pL/s)
    outside: object  # dV/dt of finite outside nodes; zero at baths
    flow: object  # Membrane flow, cell to outside positive (pL/s)
    heat: object  # Membrane water dissipation (pJ/s)
    supply: object  # Water baths supply to the system (pL/s)
    work: object  # Bath water work, 1e-3 psi_b supply (pJ/s)
    edges: object  # osmotic_water.EdgeValues


def water_rates(state, availability, p, *, xp=jnp):
    """Volume rates at frozen amounts; a bath's exchange is supply, not volume change."""
    e = water.edge_exchange(
        volumes(state, p, xp=xp), amounts(state, p, xp=xp), availability, water_parameters(p), xp=xp
    )
    flow = e.edge_flow_pL_s
    cell = -scatter(flow, p.volume, (p.membrane_cell,), xp=xp)
    into = scatter(flow, p.extracellular_volume, (p.membrane_outside,), xp=xp)
    supply = xp.where(p.water_bath, -into, 0.0)
    return WaterRates(
        cell,
        xp.where(p.water_bath, 0.0, into),
        flow,
        e.edge_dissipation_pJ_s,
        supply,
        1e-3 * p.water_bath_potential_Pa * supply,
        e,
    )


def water_rate(state, availability, p, *, xp=jnp):
    """Gershgorin rate (1/s) of the volume relaxation at the actual state, amounts frozen.

    d(psi)/dV = K / Vref + R T N / V^2 at finite nodes (a bath's volume is
    fixed); each route adds G a (slope_sender + slope_receiver) to both ends.
    """
    q = water_parameters(p)
    volume = xp.where(q.active, volumes(state, p, xp=xp), 1.0)
    total = xp.sum(amounts(state, p, xp=xp), axis=0) + q.impermeant_amount_fmol
    slope = xp.where(
        finite_nodes(p, xp=xp),
        q.bulk_modulus_Pa / q.reference_volume_pL + R * q.temperature_K * total / volume**2,
        0.0,
    )
    edge = xp.where(
        q.edge_active,
        q.conductance_pL_per_Pa_s * availability * (slope[q.sender] + slope[q.receiver]),
        0.0,
    )
    nodes = scatter(edge, slope, (q.sender,), xp=xp) + scatter(edge, slope, (q.receiver,), xp=xp)
    return xp.max(nodes, initial=0.0)


def water_control_valid(availability, p, *, xp=jnp):
    return (
        xp.all(xp.isfinite(availability))
        & xp.all((availability >= 0) & (availability <= 1))
        & xp.all(xp.where(p.membrane_active, True, availability == 0))
    )


def water_domain_valid(state, p, *, xp=jnp):
    """Volumes strictly inside their bounds, water fields zero where they have no owner."""
    q = water_parameters(p)
    valid = water.domain_valid(volumes(state, p, xp=xp), amounts(state, p, xp=xp), q, xp=xp)
    route = p.membrane_active & (q.conductance_pL_per_Pa_s > 0)
    masks = (
        p.active,
        p.outside_active & ~p.water_bath,
        route,
        route,
        p.water_bath,
        p.water_bath,
    )
    for name, mask in zip(WATER_STATE_AXES, masks, strict=True):
        value = getattr(state, name)
        valid &= xp.all(xp.isfinite(value)) & xp.all(xp.where(mask, True, value == 0))
    return valid


def _advance(state, h, r, p):
    """Water fields + h * rates (amounts untouched); the bath work is booked from supply."""
    supplied = h * r.supply
    return state._replace(
        volume_increment_pL=state.volume_increment_pL + h * r.cell,
        extracellular_volume_increment_pL=state.extracellular_volume_increment_pL + h * r.outside,
        water_transferred_pL=state.water_transferred_pL + h * r.flow,
        water_dissipated_energy_pJ=state.water_dissipated_energy_pJ + h * r.heat,
        bath_water_supplied_pL=state.bath_water_supplied_pL + supplied,
        bath_water_work_pJ=state.bath_water_work_pJ + 1e-3 * p.water_bath_potential_Pa * supplied,
    )


def water_step(state, h, availability, p, *, xp=jnp):
    """Heun's method for the volumes over h at frozen amounts: (state, valid)."""
    valid = water_domain_valid(state, p, xp=xp)
    valid &= 2 * h * water_rate(state, availability, p, xp=xp) <= MAX_WATER_RELAXATION_PER_STEP
    start = water_rates(state, availability, p, xp=xp)
    predicted = _advance(state, h, start, p)
    valid &= water_domain_valid(predicted, p, xp=xp)
    end = water_rates(predicted, availability, p, xp=xp)
    mean = WaterRates(*(0.5 * (a + b) for a, b in zip(start[:-1], end[:-1], strict=True)), None)
    new = _advance(state, h, mean, p)
    valid &= water_domain_valid(new, p, xp=xp)
    return new, valid


def water_energy_rate(w, p, *, xp=jnp):
    """d(F_mix + U)/dt from volume change at frozen amounts, plus heat, minus bath work."""
    rate = xp.concatenate((w.cell, w.outside))
    e = w.edges
    return (
        1e-3 * xp.sum((e.hydrostatic_pressure_Pa - e.osmotic_pressure_Pa) * rate)
        + xp.sum(w.heat)
        - xp.sum(w.work)
    )


# Row checks. @3's checks are @3's own functions and tuples (surface_pump.checked_rows
# and surface_pump_checks.row_checks with @3's balances, magnitudes, bounds and
# dissipation fields), so whatever @3's checks become applies here unchanged; the
# water ledgers and the water heat are checked after them.
WATER_LEDGERS = ("water_local", "water_outside", "water_total", "bath_water_work")


WATER_DIAGNOSTICS = (
    "cell_water_balance_error_pL",
    "outside_water_balance_error_pL",
    "global_water_balance_error_pL",
    "bath_water_work_error_pJ",
)


WATER_LEDGER_MESSAGE = "Resolved pump water accounting failed: "


def water_ledgers(state, p, *, xp):
    """Volume, water and work ledgers plus the water terms of the energy ledger."""
    q = water_parameters(p)
    dv, dve = state.volume_increment_pL, state.extracellular_volume_increment_pL
    moved, supplied = state.water_transferred_pL, state.bath_water_supplied_pL
    into = scatter(moved, dve, (p.membrane_outside,), xp=xp)
    local = xp.where(p.active, dv + scatter(moved, dv, (p.membrane_cell,), xp=xp), 0.0)
    outside = xp.where(p.outside_active, xp.where(p.water_bath, supplied + into, dve - into), 0.0)
    total = xp.sum(dv) + xp.sum(dve) - xp.sum(supplied)
    work = state.bath_water_work_pJ - 1e-3 * p.water_bath_potential_Pa * supplied
    # Endpoint free-energy terms. F_mix(N, V) - F_mix(N, V0) = -RT N_tot log(V/V0)
    # at the current amounts (the ionic term already holds F(N, V0) - F(N0, V0)),
    # and the exact quadratic elastic energy U(V) - U(V0).
    finite = finite_nodes(p, xp=xp)
    initial = xp.concatenate((p.volume, p.extracellular_volume))
    delta = xp.concatenate((dv, dve))
    total_osmolytes = xp.sum(amounts(state, p, xp=xp), axis=0) + q.impermeant_amount_fmol
    ratio = xp.where(finite, delta / initial, 0.0)
    dilution = (
        -1e-3
        * R
        * q.temperature_K
        * xp.sum(xp.where(finite, total_osmolytes * xp.log1p(ratio), 0.0))
    )
    stiffness = xp.where(finite, q.bulk_modulus_Pa / q.reference_volume_pL, 0.0)
    pressure = xp.where(
        finite, stiffness * (initial - q.reference_volume_pL) + q.pressure_offset_Pa, 0.0
    )
    elastic = 1e-3 * xp.sum(pressure * delta + 0.5 * stiffness * delta**2)
    energy = (
        dilution
        + elastic
        + xp.sum(state.water_dissipated_energy_pJ)
        - xp.sum(state.bath_water_work_pJ)
    )
    return energy, dict(
        water_local=local, water_outside=outside, water_total=total, bath_water_work=work
    )


def water_magnitudes(row, p, *, xp=np):
    """Magnitudes rounded into each water ledger, in WATER_LEDGERS order."""
    dv, dve = row.volume_increment_pL, row.extracellular_volume_increment_pL
    moved, supplied = xp.abs(row.water_transferred_pL), xp.abs(row.bath_water_supplied_pL)
    local = xp.abs(dv) + scatter(moved, dv, (p.membrane_cell,), xp=xp)
    outside = xp.abs(dve) + scatter(moved, dve, (p.membrane_outside,), xp=xp) + supplied
    total = xp.sum(xp.abs(dv)) + xp.sum(xp.abs(dve)) + xp.sum(supplied)
    work = xp.abs(row.bath_water_work_pJ) + 1e-3 * xp.abs(p.water_bath_potential_Pa) * supplied
    return local, outside, total, work


def water_bounds(magnitudes, steps):
    rounding = first.LEDGER_STEP_ROUNDING * np.finfo(float).eps * steps
    floors = (VOLUME_ATOL_PL, VOLUME_ATOL_PL, VOLUME_ATOL_PL, WORK_ATOL_PJ)
    return tuple(floor + rounding * m for floor, m in zip(floors, magnitudes, strict=True))


WATER_READOUTS = (
    "cell_volume_pL",
    "extracellular_volume_pL",
    "cell_concentration_mM",
    "extracellular_concentration_mM",
    "osmotic_pressure_Pa",
    "hydrostatic_pressure_Pa",
    "water_potential_Pa",
    "water_flow_pL_s",
    "water_dissipation_pJ_s",
    "bath_water_supply_pL_s",
    "water_availability",
    "energy_balance_pJ",
)


def bind(spec, declaration, p):
    """The water state (zero) and layout fields of a definition on @3's layout p.

    resolved_pump_water@1's binding: compartments, held baths and membrane routes of
    the declaration, the conductance 1e15 A Lp and each held bath's water potential,
    as edge_exchange computes it at a bath node.
    """
    m, x = spec.model, spec.execution
    n, o, nm = x.capacity, x.extracellular_capacity, x.membrane_capacity
    index = {c.id: i for i, c in enumerate(m.cells)} | {
        c.id: n + i for i, c in enumerate(m.extracellular)
    }
    values = dict(
        temperature_K=np.asarray(p.temperature),
        active=np.r_[p.active, p.outside_active],
        reference_volume_pL=np.ones(n + o),
        minimum_volume_pL=np.full(n + o, 0.5),
        maximum_volume_pL=np.full(n + o, 1.5),
        impermeant_amount_fmol=np.zeros(n + o),
        bulk_modulus_Pa=np.zeros(n + o),
        pressure_offset_Pa=np.zeros(n + o),
        edge_active=np.asarray(p.membrane_active),
        sender=np.asarray(p.membrane_cell),
        receiver=n + np.asarray(p.membrane_outside),
        conductance_pL_per_Pa_s=np.zeros(nm),
    )
    for row in declaration.compartments:
        i = index[row.compartment_id]
        for key in (
            "reference_volume_pL",
            "minimum_volume_pL",
            "maximum_volume_pL",
            "impermeant_amount_fmol",
            "bulk_modulus_Pa",
            "pressure_offset_Pa",
        ):
            values[key][i] = getattr(row, key)
    bath = np.zeros(o, dtype=bool)
    for row in declaration.baths:
        i = index[row.compartment_id]
        nominal = p.extracellular_volume[i - n]
        bath[i - n] = True
        values["reference_volume_pL"][i] = nominal
        values["minimum_volume_pL"][i] = 0.5 * nominal
        values["maximum_volume_pL"][i] = 2.0 * nominal
        values["pressure_offset_Pa"][i] = row.hydrostatic_pressure_Pa
    for i, row in enumerate(declaration.membranes):
        values["conductance_pL_per_Pa_s"][i] = (
            1e15 * m.membranes[i].area_m2 * row.hydraulic_permeability_m_per_Pa_s
        )
    q = water.validate_parameters(water.Parameters(**values))
    # The held bath's water potential, as edge_exchange computes it at a bath node.
    held = water.edge_exchange(
        np.r_[p.volume, p.extracellular_volume],
        np.concatenate((p.amount_reference, p.extracellular_amount_reference), axis=-1),
        np.zeros(nm),
        q,
        xp=np,
    ).water_potential_Pa[n:]
    zeros = (np.zeros(n), np.zeros(o), np.zeros(nm), np.zeros(nm), np.zeros(o), np.zeros(o))
    layout = (*q, bath, np.where(bath, held, 0.0))
    return (
        dict(zip(WATER_STATE_AXES, zeros, strict=True)),
        dict(zip(WATER_LAYOUT_FIELDS, layout, strict=True)),
    )


def minimum_volume_spec(spec, declaration):
    """The @3 definition with every compliant node at its declared minimum volume."""
    base = composite_spec.projection(spec)
    rows = {c.compartment_id: c for c in declaration.compartments}
    m = base.model
    cells = tuple(replace(c, volume_pL=rows[c.id].minimum_volume_pL) for c in m.cells)
    outside = tuple(
        c if c.reservoir else replace(c, volume_pL=rows[c.id].minimum_volume_pL)
        for c in m.extracellular
    )
    return replace(base, model=replace(m, cells=cells, extracellular=outside))


# ------------------------------------------------------------------ the operator


class WaterStepChecks:
    """The water bounds of one definition, for every chunk of its clock.

    What they read from the definition (the minimum-volume projection's explicit and
    calcium bounds, each building a layout, and the water relaxation rate at the declared
    state) is evaluated at its first use and kept; a call makes check_steps' refusals in
    check_steps' order.
    """

    def __init__(self, spec, declaration, model):
        self.spec, self.declaration, self.model = spec, declaration, model

    @cached_property
    def low(self):
        return ionic_spec.projection(minimum_volume_spec(self.spec, self.declaration))

    @cached_property
    def explicit_rate(self):
        return first.explicit_rate_bound(self.low)

    @cached_property
    def calcium_rate(self):
        return second.calcium_rate_bound(self.low)

    @cached_property
    def water_rate(self):
        state, p = self.model.initial_values(self.spec)
        return water_rate(state, p.membrane_active.astype(float), p, xp=np)

    def __call__(self, steps):
        step = np.max(steps, initial=0)
        if self.spec.execution.solver != "rk4":
            if step * self.explicit_rate > EXPLICIT_STEP_BOUND:
                raise ConfigError("IMEX step exceeds the explicit-rate bound at minimum volumes")
            if step * self.calcium_rate > EXPLICIT_STEP_BOUND:
                raise ConfigError("IMEX step exceeds the calcium pump bound at minimum volumes")
        rate = self.water_rate
        if not np.isfinite(rate) or step * rate > MAX_WATER_RELAXATION_PER_STEP * (
            1 + 16 * np.finfo(float).eps
        ):
            raise ConfigError("Water relaxation requires a smaller step (dt x rate exceeds 0.05)")


class OsmoticWater(Operator):
    LAW_ID = LAW_ID
    STEP_ID = WATER_STEP_ID
    SPLIT = True
    RK4 = "coupled"
    STATE_AXES = WATER_STATE_AXES
    HEAT_FIELDS = ("water_dissipated_energy_pJ",)
    WORK_FIELDS = ("bath_water_work_pJ",)
    LAYOUT_FIELDS = WATER_LAYOUT_FIELDS
    CONTROL_FIELDS = ("water",)
    EXPERIMENT_KEYS = ("water_controls",)
    VIEW_FIELDS = ("volume", "extracellular_volume")
    # The water conductance 1e15 A Lp is bound from the declared patch areas.
    CONFLICTS_VIEW = ("membrane_area",)
    VIEW_FOLLOWS_SPLIT = True
    LEDGERS = WATER_LEDGERS
    LEDGER_DIAGNOSTICS = WATER_DIAGNOSTICS
    LEDGER_MESSAGE = WATER_LEDGER_MESSAGE
    READOUT = "water"
    READOUT_COLUMNS = WATER_READOUTS
    REPLACES = {"energy_balance_pJ_s": "the inner energy-balance rate plus the water terms"}
    FINITE_RATES = True

    # ------------------------------------------------------------ definition

    def parse(self, raw, base, inner_model):
        return water_spec.parse_water(raw, base)

    def to_dict(self, declaration, base):
        w = declaration
        if (
            type(w) is not water_spec.Water
            or any(type(p) is not water_spec.WaterCompartment for p in w.compartments)
            or any(type(p) is not water_spec.WaterBath for p in w.baths)
            or any(type(p) is not water_spec.WaterMembrane for p in w.membranes)
        ):
            raise ConfigError("Require explicit immutable water declaration types")
        return dict(
            law=w.law,
            compartments=[asdict(p) for p in w.compartments],
            baths=[asdict(p) for p in w.baths],
            membranes=[asdict(p) for p in w.membranes],
        )

    def parse_schedule(self, raw, base, declaration):
        ids = [p.id for p in base.model.membranes]
        schedules = first_spec._schedules(
            raw["water_controls"], "membrane", ids, base.experiment.end_time
        )
        return tuple(schedules[i] for i in ids)

    def schedule_to_dict(self, schedule, base, declaration):
        return dict(
            water_controls=[
                dict(membrane_id=p.id, schedule=[asdict(c) for c in g])
                for p, g in zip(base.model.membranes, schedule, strict=True)
            ]
        )

    def schedule_times(self, schedule):
        return tuple(c.time for g in schedule for c in g)

    def value_at(self, schedule, time):
        return tuple(g[bisect_right([p.time for p in g], time) - 1].availability for g in schedule)

    def control_values(self, spec, declaration, schedule, records, indices, times):
        values = np.asarray(records, dtype=np.float64).reshape(len(records), -1)
        padded = np.zeros((len(times), spec.execution.membrane_capacity))
        padded[:, : values.shape[-1]] = values[indices]
        return (padded,)

    def check_steps(self, spec, declaration, schedule, steps, controls, model):
        """The water bounds: @3's explicit bounds at the declared minimum volumes, and
        dt x the water relaxation rate at the declared state with every route open."""
        self.bind_check_steps(spec, declaration, schedule, model)(steps)

    def bind_check_steps(self, spec, declaration, schedule, model):
        return WaterStepChecks(spec, declaration, model)

    def batch_signature(self, declaration):
        w = declaration
        return (
            w.law,
            tuple(p.compartment_id for p in w.compartments),
            tuple(p.compartment_id for p in w.baths),
        )

    def working_size(self, spec):
        x = spec.execution
        return 2 * (x.capacity + 3 * x.extracellular_capacity + 2 * x.membrane_capacity)

    def summary(self, spec, declaration, schedule, history):
        solver = spec.execution.solver
        return {
            "water_law": declaration.law,
            "water_step": None if solver == "rk4" else self.STEP_ID,
            "water_rk4": "coupled rhs (rk4)",
            "volume_owner_ids": [c.compartment_id for c in declaration.compartments],
            "water_bath_ids": [c.compartment_id for c in declaration.baths],
            "water_routes": "membranes only; no junction or extracellular-face water",
        }

    # ------------------------------------------------------------ binding

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        return bind(spec, declaration, inner_layout)

    # ------------------------------------------------------------ step parts

    def view(self, state, p, q, *, xp):
        return dict(
            volume=p.volume + state.volume_increment_pL,
            extracellular_volume=p.extracellular_volume + state.extracellular_volume_increment_pL,
        )

    def half_step(self, state, h, control, p, *, xp):
        return water_step(state, h, control.water, p, xp=xp)

    def control_valid(self, control, p, *, xp):
        return water_control_valid(control.water, p, xp=xp)

    def rates(self, state, control, p, view, *, xp):
        w = water_rates(state, control.water, p, xp=xp)
        rates = dict(
            volume_increment_pL=w.cell,
            extracellular_volume_increment_pL=w.outside,
            water_transferred_pL=w.flow,
            water_dissipated_energy_pJ=w.heat,
            bath_water_supplied_pL=w.supply,
            bath_water_work_pJ=w.work,
        )
        return rates, None, w

    def rate_checks(self, state, control, p, valid, *, xp):
        valid = valid & water_domain_valid(state, p, xp=xp)
        valid &= water_control_valid(control.water, p, xp=xp)
        return valid

    def energy_rate(self, readout, p, *, xp):
        return water_energy_rate(readout, p, xp=xp)

    def domain_valid(self, state, p, valid, *, xp):
        own = water_domain_valid(state, p, xp=xp)
        return own if valid is None else valid & own

    # ------------------------------------------------------------ ledgers

    def ledger_terms(self, result, row, p, *, xp):
        energy, ledgers = water_ledgers(row, p, xp=xp)
        result["energy"] += energy
        return result, ledgers

    def own_ledgers(self, row, p, *, xp):
        return water_ledgers(row, p, xp=xp)[1]

    def own_magnitudes(self, row, p, *, xp):
        return water_magnitudes(row, p, xp=xp)

    def own_bounds(self, magnitudes, steps):
        return water_bounds(magnitudes, steps)

    # ------------------------------------------------------------ observations

    def observe(self, row, state, control, p, view, model, spec):
        n = p.active.size
        w = water_rates(state, control.water, p, xp=np)
        volume = volumes(state, p, xp=np)
        ci, co = physical_amounts(state, p)
        columns = {k: getattr(state, k) for k in self.STATE_AXES}
        columns.update(
            cell_volume_pL=volume[:n],
            extracellular_volume_pL=volume[n:],
            cell_concentration_mM=np.where(p.active, ci / volume[:n], 0.0),
            extracellular_concentration_mM=np.where(p.outside_active, co / volume[n:], 0.0),
            osmotic_pressure_Pa=w.edges.osmotic_pressure_Pa,
            hydrostatic_pressure_Pa=w.edges.hydrostatic_pressure_Pa,
            water_potential_Pa=w.edges.water_potential_Pa,
            water_flow_pL_s=w.flow,
            water_dissipation_pJ_s=w.heat,
            bath_water_supply_pL_s=w.supply,
            water_availability=control.water,
            energy_balance_pJ=np.atleast_1d(model.balances(state, p)["energy"]),
            energy_balance_pJ_s=row["energy_balance_pJ_s"] + water_energy_rate(w, p, xp=np),
        )
        return columns
