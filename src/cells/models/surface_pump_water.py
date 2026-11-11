"""resolved_pump_water@1: resolved_pump_tissue@3 with osmotic water and compliant volumes.

The ionic model is resolved_pump_tissue@3 (models/surface_pump_v3.py),
unchanged and called, never copied. Water is the law
numerics/osmotic_water.LAW_ID on the membranes (core/surface_pump_water_spec.py):
the flow across a patch is Q = 1e15 A Lp a (psi_cell - psi_outside) pL/s with
psi = P - Pi, Pi = R T (sum of declared amounts + neutral impermeants) / V and
P = K (V / Vref - 1) + P0. Finite nodes change volume; a held bath keeps its
volume and composition, so its water potential is fixed and the water it
exchanges is booked as supply, with the work 1e-3 psi_b dS.

Concentrations. Every @3 function is evaluated on the @3 layout with the
current volumes (ionic_layout(p, state)): the field (its Newton solve and the
Kirchhoff offsets of floating components, through the currents), the
membrane, junction and face fluxes, the channel and both pump laws, the
implicit drift weights and @3's explicit-stage refusal all see amount / current
volume. Charges, capacitances and potentials do not depend on volume. Ledgers
use the declared layout plus explicit dilution and elastic terms.

Time integration (IMEX solvers). Strang splitting
Phi_dt = W_{dt/2} o I_dt o W_{dt/2}: I_dt is @3's own checked_step at the
volumes left by the first half (frozen over the ionic step); W_h advances the
volumes at frozen amounts by Heun's method (explicit trapezoid). The pieces act
on disjoint variables (I: amounts, gates and ionic ledgers at fixed volume; W:
volumes and water ledgers at fixed amounts), so a zero of the full right-hand
side is a fixed point of each piece and of Phi, and the free energy telescopes
exactly over the three pieces. Water is explicit: its relaxation is about
0.5-85 s for the sourced permeabilities (docs/PUMP_WATER_MODEL.md) against 1 ms
steps; each water step refuses itself if dt times the water relaxation rate at
its actual state exceeds MAX_WATER_RELAXATION_PER_STEP. Any refused piece
refuses the whole step (the previous state is returned). With every water
route closed the flows are exact zeros and @3's step sees exactly @3's inputs.
RK4 (reference runs) integrates the coupled, unsplit right-hand side.
"""

from dataclasses import make_dataclass, replace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.surface_pump_v2_spec import Control as IonicControl
from cells.core.surface_pump_water_spec import MODEL_ID, Control, projection
from cells.models import surface_pump as first
from cells.models import surface_pump_v2 as second
from cells.models import surface_pump_v3 as ionic
from cells.numerics import osmotic_water as water
from cells.numerics.extracellular_field import scatter
from cells.numerics.fixed_step import rk4_checked_step
from cells.processes.electrochemistry import R

OBSERVER_ID = "resolved_pump_water_accepted_grid_readouts@1"
OBSERVATION_SAMPLING = ionic.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = "positive_resolved_inventory_gates_atp_bounded_compliant_volumes@1"
BATCH_CAPACITIES = ionic.BATCH_CAPACITIES
SPLITTING_ID = "strang_water_ionic_water@1"
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
STATE_AXES = ionic.STATE_AXES | WATER_STATE_AXES
STATE_TYPE = NamedTuple("SurfacePumpWaterState", [(k, object) for k in STATE_AXES])
WATER_LAYOUT_FIELDS = (
    *("water_" + k for k in water.Parameters._fields),
    "water_bath",
    "water_bath_potential_Pa",
)
LAYOUT_TYPE = NamedTuple(
    "SurfacePumpWaterLayout",
    [(k, object) for k in (*ionic.LAYOUT_TYPE._fields, *WATER_LAYOUT_FIELDS)],
)
FLOOR_LAYOUT_TYPE = NamedTuple(  # Declared field solver surface_field.FLOOR_SOLVER_ID.
    "SurfacePumpWaterFloorLayout",
    [(k, object) for k in (*ionic.FLOOR_LAYOUT_TYPE._fields, *WATER_LAYOUT_FIELDS)],
)
ENERGY_RTOL = ionic.ENERGY_RTOL
EXPLICIT_STEP_BOUND = ionic.EXPLICIT_STEP_BOUND
IONIC_FIELDS = ionic.STATE_TYPE._fields

parameters = ionic.parameters
physical_amounts = ionic.physical_amounts
rebind = first.rebind


def batch_signature(model):
    w = model.water
    return (
        *ionic.batch_signature(model),
        w.law,
        tuple(p.compartment_id for p in w.compartments),
        tuple(p.compartment_id for p in w.baths),
    )


def working_size(spec):
    x = spec.execution
    return ionic.working_size(projection(spec)) + 2 * (
        x.capacity + 3 * x.extracellular_capacity + 2 * x.membrane_capacity
    )


def ionic_state(state):
    return ionic.STATE_TYPE(*(getattr(state, k) for k in IONIC_FIELDS))


def ionic_control(control):
    return IonicControl(*control[: len(IonicControl._fields)])


def ionic_layout(p, state=None):
    """The @3 layout: declared volumes, or the current ones of `state`."""
    kind = ionic.FLOOR_LAYOUT_TYPE if hasattr(p, "field_current_floor") else ionic.LAYOUT_TYPE
    q = kind(*(getattr(p, k) for k in kind._fields))
    if state is None:
        return q
    return q._replace(
        volume=p.volume + state.volume_increment_pL,
        extracellular_volume=p.extracellular_volume + state.extracellular_volume_increment_pL,
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


def initial_values(spec):
    state, p = ionic.initial_values(projection(spec))
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
    for row in m.water.compartments:
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
    for row in m.water.baths:
        i = index[row.compartment_id]
        nominal = p.extracellular_volume[i - n]
        bath[i - n] = True
        values["reference_volume_pL"][i] = nominal
        values["minimum_volume_pL"][i] = 0.5 * nominal
        values["maximum_volume_pL"][i] = 2.0 * nominal
        values["pressure_offset_Pa"][i] = row.hydrostatic_pressure_Pa
    for i, row in enumerate(m.water.membranes):
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
    kind = FLOOR_LAYOUT_TYPE if type(p) is ionic.FLOOR_LAYOUT_TYPE else LAYOUT_TYPE
    water_state = (np.zeros(n), np.zeros(o), np.zeros(nm), np.zeros(nm), np.zeros(o), np.zeros(o))
    return (
        STATE_TYPE(*state, *water_state),
        kind(*p, *q, bath, np.where(bath, held, 0.0)),
    )


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


def imex_step(state, dt, control, p, *, xp=jnp):
    """Strang splitting around @3's own checked step; (new or unchanged state, valid)."""
    h = 0.5 * dt
    first_half, valid = water_step(state, h, control.water, p, xp=xp)
    valid &= water_control_valid(control.water, p, xp=xp)
    inputs = (ionic_state(first_half), ionic_control(control), ionic_layout(p, first_half))
    if xp is jnp:
        inputs = jax.lax.optimization_barrier(inputs)
    moved, ok = ionic.checked_step(inputs[0], dt, inputs[1], inputs[2], p.active)
    if xp is jnp:
        moved, ok = jax.lax.optimization_barrier((moved, ok))
    middle = first_half._replace(**moved._asdict())
    final, last = water_step(middle, h, control.water, p, xp=xp)
    valid = valid & ok & last & domain_valid(final, p, p.active, xp=xp)
    return jax.tree.map(lambda old, new: xp.where(valid, new, old), state, final), valid


def checked_step(state, dt, control, p, active):
    """RK4 of the coupled right-hand side for an empty tableau; otherwise the split step."""
    if p.imex_explicit.shape[0] == 0:
        return rk4_checked_step(rhs, domain_valid, state, dt, control, p, active)
    return imex_step(state, dt, control, p)


class Values(NamedTuple):
    field: object  # @3's field values; energy rate includes water
    derivative: object
    ionic: object  # @3's readouts at the current volumes
    water: object  # WaterRates
    valid: object


def readouts(state, control, p, *, xp=jnp):
    """@3's readouts at the current volumes plus the water rates (stationary analysis, RK4)."""
    v = ionic.readouts(ionic_state(state), ionic_control(control), ionic_layout(p, state), xp=xp)
    w = water_rates(state, control.water, p, xp=xp)
    derivative = STATE_TYPE(*v.derivative, w.cell, w.outside, w.flow, w.heat, w.supply, w.work)
    valid = v.valid & water_domain_valid(state, p, xp=xp)
    valid &= water_control_valid(control.water, p, xp=xp)
    for value in derivative[len(IONIC_FIELDS) :]:
        valid &= xp.all(xp.isfinite(value))
    field = v.field._replace(
        energy_balance_pJ_s=v.field.energy_balance_pJ_s + water_energy_rate(w, p, xp=xp),
        converged=valid,
    )
    return Values(field, derivative, v, w, valid)


def water_energy_rate(w, p, *, xp=jnp):
    """d(F_mix + U)/dt from volume change at frozen amounts, plus heat, minus bath work."""
    rate = xp.concatenate((w.cell, w.outside))
    e = w.edges
    return (
        1e-3 * xp.sum((e.hydrostatic_pressure_Pa - e.osmotic_pressure_Pa) * rate)
        + xp.sum(w.heat)
        - xp.sum(w.work)
    )


def field_values(state, control, p, *, xp=jnp):
    return readouts(state, control, p, xp=xp).field


def rhs(state, control, p, active, *, xp=jnp):
    values = readouts(state, control, p, xp=xp)
    return STATE_TYPE(*(xp.where(values.valid, v, xp.nan) for v in values.derivative))


def domain_valid(state, p, active, *, xp=jnp):
    valid = ionic.domain_valid(ionic_state(state), ionic_layout(p, state), active, xp=xp)
    return valid & water_domain_valid(state, p, xp=xp)


def control_domain_valid(state, control, p, active, *, xp=jnp):
    valid = domain_valid(state, p, active, xp=xp) & water_control_valid(control.water, p, xp=xp)
    if xp is np:
        if not valid:
            return np.asarray(False)
        try:
            return np.asarray(readouts(state, control, p, xp=np).valid)
        except np.linalg.LinAlgError:
            return np.asarray(False)
    return jax.lax.cond(
        valid, lambda: readouts(state, control, p).valid, lambda: jnp.asarray(False)
    )


domain_valid.with_control = control_domain_valid


def compact(spec):
    m = spec.model
    return replace(
        spec,
        execution=replace(
            spec.execution,
            capacity=len(m.cells),
            extracellular_capacity=len(m.extracellular),
            membrane_capacity=len(m.membranes),
            edge_capacity=len(m.junctions),
            face_capacity=len(m.faces),
            channel_capacity=len(m.channels),
        ),
    )


def check_definition(spec):
    from cells.core.surface_pump_water_spec import control_values

    small = compact(spec)
    state, p = initial_values(small)
    controls = control_values(small, [c.time for c in small.experiment.changes])
    with np.errstate(all="ignore"):
        for i in range(len(controls.membrane)):
            control = Control(*(v[i] for v in controls))
            if not control_domain_valid(state, control, p, p.active, xp=np):
                raise ConfigError("Initial resolved pump water domain invalid")


def minimum_volume_spec(spec):
    """The @3 definition with every compliant node at its declared minimum volume."""
    base = projection(spec)
    rows = {c.compartment_id: c for c in spec.model.water.compartments}
    m = base.model
    cells = tuple(replace(c, volume_pL=rows[c.id].minimum_volume_pL) for c in m.cells)
    outside = tuple(
        c if c.reservoir else replace(c, volume_pL=rows[c.id].minimum_volume_pL)
        for c in m.extracellular
    )
    return replace(base, model=replace(m, cells=cells, extracellular=outside))


def check_steps(spec, steps, controls):
    """@3's step checks on this definition's full event grid, plus the water bounds.

    @3's checks read the definition by field name, so they run on the full event
    union (water controls included). IMEX: @3's face, junction and calcium
    explicit bounds also hold with every compliant node at its minimum volume
    (concentrations and 1/V at their largest). Every solver: dt x the water
    relaxation rate at the declared state with every route open is at most
    MAX_WATER_RELAXATION_PER_STEP; IMEX water steps also refuse themselves at
    their actual states.
    """
    from cells.core.surface_pump_v3_spec import projection as ionic_projection

    ionic.check_steps(spec, steps, controls)
    step = np.max(steps, initial=0)
    if spec.execution.solver != "rk4":
        low = ionic_projection(minimum_volume_spec(spec))
        if step * first.explicit_rate_bound(low) > EXPLICIT_STEP_BOUND:
            raise ConfigError("IMEX step exceeds the explicit-rate bound at minimum volumes")
        if step * second.calcium_rate_bound(low) > EXPLICIT_STEP_BOUND:
            raise ConfigError("IMEX step exceeds the calcium pump bound at minimum volumes")
    state, p = initial_values(spec)
    rate = water_rate(state, p.membrane_active.astype(float), p, xp=np)
    if not np.isfinite(rate) or step * rate > MAX_WATER_RELAXATION_PER_STEP * (
        1 + 16 * np.finfo(float).eps
    ):
        raise ConfigError("Water relaxation requires a smaller step (dt x rate exceeds 0.05)")


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
LEDGER_DIAGNOSTICS = (*first.LEDGER_DIAGNOSTICS, *WATER_DIAGNOSTICS)
LEDGERS = (*first.LEDGERS, *WATER_LEDGERS)
WATER_LEDGER_MESSAGE = "Resolved pump water accounting failed: "
DISSIPATION_FIELDS = (*ionic.DISSIPATION_FIELDS, "water_dissipated_energy_pJ")


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


def ionic_balances(state, p):
    """@3's ledgers (its balances, declared layout) with the water terms in the energy."""
    result = ionic.balances(ionic_state(state), ionic_layout(p))
    result["energy"] += water_ledgers(state, p, xp=np)[0]
    return result


def balances(state, p):
    result = ionic.balances(ionic_state(state), ionic_layout(p))
    energy, ledgers = water_ledgers(state, p, xp=np)
    result["energy"] += energy
    return result | ledgers


def device_balances(state, p):
    """balances() with jax.numpy: @3's device ledgers, then the same water terms."""
    result = ionic.device_balances(ionic_state(state), ionic_layout(p))
    energy, ledgers = water_ledgers(state, p, xp=jnp)
    result["energy"] += energy
    return result | ledgers


def ionic_magnitudes(row, p, *, xp=np):
    return ionic.channel_magnitudes(row, p, xp=xp)


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


def magnitudes(row, p, *, xp=np):
    """@3's ledger magnitudes, then the water ledgers'."""
    return (*ionic_magnitudes(row, p, xp=xp), *water_magnitudes(row, p, xp=xp))


def ledger_limits(row, p, tol, rtol, *, steps, magnitudes, xp=np):
    """surface_pump.ledger_limits for @3's ledgers, then the water bounds.

    The energy flows include the water heat and bath work (their field names);
    each water ledger allows its fixed floor plus the family's per-step rounding.
    """
    count = len(first.LEDGERS)
    flows, bounds = first.ledger_limits(
        row, p, tol, rtol, steps=steps, magnitudes=magnitudes[:count], xp=xp
    )
    return flows, (*bounds, *water_bounds(magnitudes[count:], steps))


def check_values(state, spec, steps=None):
    """Host checks of every accepted row (one row or a [time, ...] history).

    First @3's own row checks (surface_pump.checked_rows with @3's balances,
    magnitudes and bounds): the domain (here with the volume bounds), @3's ten
    ledgers with the water terms in the energy ledger, and nonnegative,
    nondecreasing dissipation of @3's fields and the water heat. Then the four
    water ledgers against their floors plus the per-step rounding allowance.
    """
    _, p = initial_values(spec)
    diagnostics = first.checked_rows(
        state,
        spec,
        p,
        domain=domain_valid,
        balances=ionic_balances,
        magnitudes=ionic_magnitudes,
        dissipation=DISSIPATION_FIELDS,
        steps=steps,
    )
    rows = (
        [state]
        if state.amount_increment.ndim == 2
        else [STATE_TYPE(*(v[i] for v in state)) for i in range(len(state.amount_increment))]
    )
    counts = [0] * len(rows) if steps is None else list(steps)
    extra = {"max_" + k: 0.0 for k in WATER_DIAGNOSTICS}
    with np.errstate(all="ignore"):
        for row, count in zip(rows, counts, strict=True):
            values = water_ledgers(row, p, xp=np)[1]
            bounds = water_bounds(water_magnitudes(row, p, xp=np), count)
            for (name, value), key, bound in zip(
                values.items(), WATER_DIAGNOSTICS, bounds, strict=True
            ):
                if not np.isfinite(value).all() or np.any(np.abs(value) > bound):
                    raise NumericalError(WATER_LEDGER_MESSAGE + name)
                key = "max_" + key
                extra[key] = max(extra[key], float(np.max(np.abs(value), initial=0)))
    return diagnostics | extra


# Device checks (core/vector_windows.py): check_values' tests per accepted row through
# the shared surface_pump_checks.row_checks, in host order: domain, @3's ledgers,
# the water ledgers, dissipation.
DEVICE_CHECKS = ("domain", *LEDGERS, "dissipation")
DEVICE_DIAGNOSTICS = (
    *("max_" + k for k in LEDGER_DIAGNOSTICS),
    "max_energy_balance_relative",
    "max_global_charge_bound_ratio",
)
device_check_constants = ionic.device_check_constants


def device_failure_message(check):
    if check in WATER_LEDGERS:
        return WATER_LEDGER_MESSAGE + check
    return ionic.device_failure_message(check)


def device_checks(previous, row, p, constants, steps):
    """check_values' tests for one accepted row on the device: (failed, diagnostics)."""
    from cells.models.surface_pump_checks import row_checks

    return row_checks(
        previous,
        row,
        p,
        constants,
        steps,
        domain_valid=domain_valid,
        balances=device_balances,
        limits=ledger_limits,
        magnitudes=magnitudes,
        dissipation=DISSIPATION_FIELDS,
    )


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
OBSERVATION_FIELDS = (*ionic.OBSERVATION_FIELDS, *WATER_STATE_AXES, *WATER_READOUTS)
Observations = make_dataclass(
    "SurfacePumpWaterObservations", [(k, np.ndarray) for k in OBSERVATION_FIELDS], frozen=True
)


def observe_history(times, history, layout, requested, spec):
    """@3's observations of each row at its current volumes, then the water readouts."""
    from cells.core.surface_pump_water_spec import control_values

    p = type(layout)(*(np.asarray(v) for v in layout))
    requested = np.asarray(requested, dtype=float)
    if any(t not in times for t in requested):
        raise ConfigError("Resolved pump water observations require accepted times")
    controls, records, base = control_values(spec, requested), [], projection(spec)
    n = p.active.size
    for j, t in enumerate(requested):
        i = int(np.flatnonzero(times == t)[0])
        state = STATE_TYPE(*(np.asarray(v[i]) for v in history))
        control = Control(*(v[j] for v in controls))
        one = ionic.STATE_TYPE(*(getattr(state, k)[None] for k in IONIC_FIELDS))
        observed = ionic.observe_history(
            np.array([t]), one, ionic_layout(p, state), np.array([t]), base
        )
        row = {k: v[0] for k, v in vars(observed).items()}
        w = water_rates(state, control.water, p, xp=np)
        volume = volumes(state, p, xp=np)
        ci, co = physical_amounts(state, p)
        row.update({k: getattr(state, k) for k in WATER_STATE_AXES})
        row.update(
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
            energy_balance_pJ=np.atleast_1d(balances(state, p)["energy"]),
            energy_balance_pJ_s=row["energy_balance_pJ_s"] + water_energy_rate(w, p, xp=np),
        )
        records.append(row)
    if records:
        return Observations(*(np.stack([r[k] for r in records]) for k in OBSERVATION_FIELDS))
    sample = observe_history(times[:1], STATE_TYPE(*(v[:1] for v in history)), p, times[:1], spec)
    return Observations(
        *(np.empty((0, *v.shape[1:]), dtype=v.dtype) for v in vars(sample).values())
    )


def ensemble_voltage(state, layout, spec, time):
    from cells.core.surface_pump_water_spec import control_values

    controls = control_values(spec, [time])
    control = Control(*(v[0] for v in controls))
    p = type(layout)(*(np.asarray(v) for v in layout))
    v = field_values(STATE_TYPE(*(np.asarray(v) for v in state)), control, p, xp=np)
    if not v.converged:
        raise NumericalError("Resolved pump water ensemble endpoint invalid")
    return v.rates.membrane_voltage_V[p.membrane_active]


def summarize(history, diagnostics, spec):
    base = projection(spec)
    solver = spec.execution.solver
    return ionic.summarize(history, diagnostics, base) | {
        "model": MODEL_ID,
        "ionic_model": ionic.MODEL_ID,
        "state_fields": list(STATE_TYPE._fields),
        "water_law": water.LAW_ID,
        "time_integrator": solver,
        "splitting": "coupled rhs (rk4)" if solver == "rk4" else SPLITTING_ID,
        "water_step": None if solver == "rk4" else WATER_STEP_ID,
        "volume_owner_ids": [c.compartment_id for c in spec.model.water.compartments],
        "water_bath_ids": [c.compartment_id for c in spec.model.water.baths],
        "water_routes": "membranes only; no junction or extracellular-face water",
        "geometry_scope": "fixed areas, capacitances and topology; compliant volumes",
    }
