"""resolved_pump_tissue@1: shared kinetic rates, factored field, RK4 or IMEX steps.

State, ledgers, observations and stage rates are those of surface_kinetic with
an empty channel set. The law's field (capacitor solve plus Kirchhoff offsets)
is evaluated at every accepted state. IMEX steps (numerics/surface_imex.py)
make only face electromigration implicit; every other rate is the explicit
stage rate at stage potentials. Material ledgers are exact in flux form.
Energy is checked against a declared integrator tolerance, because a
first/second-order step does not integrate the energy identity exactly.
"""

from dataclasses import replace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.surface_pump_spec import MODEL_ID
from cells.models import kinetic_finite_extracellular as pumps
from cells.models import surface_kinetic as kinetic
from cells.models import surface_tissue as tissue
from cells.numerics import surface_field as field
from cells.numerics import surface_imex as imex
from cells.numerics import surface_transport as surface
from cells.numerics.extracellular_field import scatter
from cells.numerics.fixed_step import rk4_checked_step
from cells.processes import junction_gate
from cells.processes import kinetic_pump as pump
from cells.processes.electrochemistry import CHARGE_PER_FMOL, F, R

OBSERVER_ID = kinetic.OBSERVER_ID
OBSERVATION_SAMPLING = kinetic.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = kinetic.STAGE_DOMAIN_ID
BATCH_CAPACITIES = tissue.BATCH_CAPACITIES
STATE_AXES = kinetic.STATE_AXES
STATE_TYPE = kinetic.STATE_TYPE
IMEX_FIELDS = ("imex_explicit", "imex_implicit", "imex_operator_time")
LAYOUT_TYPE = NamedTuple(
    "SurfacePumpLayout",
    [(k, object) for k in (*kinetic.FACTORED_LAYOUT_TYPE._fields, *IMEX_FIELDS)],
)
# Energy residual allowed relative to the integrated work and dissipation flows.
# RK4 keeps the family's absolute bound alone. A first/second-order step does
# not integrate the energy identity exactly: measured residuals were 4e-4/2e-6
# (Euler/ARS) on the small fixtures at 0.1 ms and 3e-5/6e-8 at 825 nodes and
# 1 ms; with dt and dt^2 scaling these bounds cover admitted steps. Ledger totals
# are compared with RK4 separately in tests/unit/test_surface_pump.py.
ENERGY_RTOL = {"rk4": 0.0, imex.EULER_ID: 2e-2, imex.ARS222_ID: 2e-3}
# Global charge (electrode charge plus charge-weighted reservoir supply) cancels
# terms that grow with the charge moved through the boundary, so its rounding
# accumulates with their magnitude: a fixed floor fails long runs. The bound adds
# a rounding allowance of 256 float64 eps per unit of that magnitude; observed
# residuals stay near 1-3 eps, while a conservation error of 1e-13 or more of the
# moved charge still fails. The capacitor and electrode checks are unchanged.
GLOBAL_CHARGE_ATOL_C = 3e-25
GLOBAL_CHARGE_ROUNDING = 256 * np.finfo(float).eps
GATE_STEP_BOUND = 0.125  # Same conservative junction-gate bound as resolved_tissue@2.
# dt * (Gershgorin rate bound) <= 1: half the Euler/RK2 real-axis limit of 2.
EXPLICIT_STEP_BOUND = 1.0

parameters = kinetic.parameters
batch_signature = kinetic.batch_signature
physical_amounts = kinetic.physical_amounts
readouts = kinetic.readouts
field_values = kinetic.field_values
rhs = kinetic.rhs
domain_valid = kinetic.domain_valid
balances = kinetic.balances
OBSERVATION_FIELDS = kinetic.OBSERVATION_FIELDS
Observations = kinetic.Observations
observe_history = kinetic.observe_history
ensemble_voltage = kinetic.ensemble_voltage


def working_size(spec):
    """Stored values per accepted step plus a margin; dense matrices are per run."""
    x, s = spec.execution, len(spec.model.species_ids)
    nodes = x.capacity + x.extracellular_capacity
    routes = x.membrane_capacity + x.edge_capacity + x.face_capacity
    return 2 * (s * (nodes + x.extracellular_capacity + routes) + 4 * routes + 3 * nodes)


def initial_values(spec):
    state, layout = kinetic.initial_values(spec)
    if type(layout) is not kinetic.FACTORED_LAYOUT_TYPE:
        raise ConfigError("Resolved pump tissue requires the factored field layout")
    solver = spec.execution.solver
    tableau = (
        imex.TABLEAUX[solver]
        if solver in imex.TABLEAUX
        else imex.Tableau(np.zeros((0, 0)), np.zeros((0, 0)), np.asarray(0.0))
    )
    return state, LAYOUT_TYPE(*layout, *tableau)


def explicit_rates(state, potential, control, p, *, xp=jnp):
    """Membrane, junction, pump, gate and face-diffusion rates at given potentials.

    The face drift is excluded; with the drift from implicit_rates at the same
    potentials, every material rate equals surface_kinetic.readouts.
    """
    s, n = tissue.field_layout(p).surface, p.active.size
    ci, co = physical_amounts(state, p)
    ci = xp.where(p.active, ci / p.volume, 1.0)
    co = xp.where(p.outside_active, co / p.extracellular_volume, 1.0)
    r = surface.transport(
        ci,
        co,
        potential[:n],
        potential[n:],
        control.membrane,
        control.junction * state.junction_gate,
        s,
        xp=xp,
    )
    weight, log = imex.face_weights(co, s, xp=xp)
    diffusion = weight * log
    args = (
        *pumps.role_inputs(
            ci[:, p.membrane_cell],
            co[:, p.membrane_outside],
            r.membrane_delta_mu_J_mol,
            p.temperature,
            p,
            xp=xp,
        ),
        pumps.pump_parameters(p),
        control.pump,
    )
    rate = pump.kinetics(*args, xp=xp)
    cycles = xp.where(p.pump_present, rate.cycles_fmol_s, 0.0)
    extra = -p.stoichiometry * cycles  # Outward-positive pump transfer.
    zero = xp.zeros_like(co)
    inflow = (
        scatter(r.membrane_flux_fmol_s + extra, zero, (p.membrane_outside,), xp=xp)
        - scatter(diffusion, zero, (p.face_sender,), xp=xp)
        + scatter(diffusion, zero, (p.face_receiver,), xp=xp)
    )
    gate = junction_gate.rhs(
        state.junction_gate, r.junction_voltage_V, kinetic.junction_parameters(p), xp=xp
    )
    outside_zero = xp.zeros_like(p.boundary_V)
    rates = STATE_TYPE(
        r.cell_rate_fmol_s - scatter(extra, r.cell_rate_fmol_s, (p.membrane_cell,), xp=xp),
        xp.where(p.reservoir, 0.0, inflow),
        r.membrane_flux_fmol_s,
        r.junction_flux_fmol_s,
        diffusion,
        xp.where(p.reservoir, -inflow, 0.0),
        r.membrane_dissipation_pJ_s,
        r.junction_dissipation_pJ_s,
        xp.zeros_like(state.face_dissipated_energy_pJ),
        outside_zero,
        outside_zero,
        outside_zero,
        xp.zeros_like(state.channel_gate),
        xp.zeros_like(state.channel_transferred),
        xp.zeros_like(state.channel_dissipated_energy_pJ),
        xp.where(p.junction_active, gate, 0.0),
        cycles,
        -1e-3 * cycles * rate.cycle_free_energy_J_mol,
        -1e-3 * cycles * rate.chemical_drive_J_mol,
    )
    valid = r.valid & xp.all(pump.domain_valid(*args, xp=xp))
    valid &= xp.all(
        junction_gate.domain_valid(
            state.junction_gate,
            r.junction_voltage_V,
            kinetic.junction_parameters(p),
            control.junction,
            xp=xp,
        )
    )
    for value in (*control, *rates):
        valid &= xp.all(xp.isfinite(value))
    for value in control:
        valid &= xp.all((value >= 0) & (value <= 1))
    return rates, valid


def implicit_rates(weight, potential, state, p, *, xp=jnp):
    """Face electromigration rates with frozen face weights; zero elsewhere."""
    s, n = tissue.field_layout(p).surface, p.active.size
    flux = imex.drift_flux(weight, potential[n:], s, xp=xp)
    zero = xp.zeros_like(state.extracellular_amount_increment)
    inflow = scatter(flux, zero, (p.face_receiver,), xp=xp) - scatter(
        flux, zero, (p.face_sender,), xp=xp
    )
    rates = STATE_TYPE(*(xp.zeros_like(v) for v in state))
    return rates._replace(
        extracellular_amount_increment=xp.where(p.reservoir, 0.0, inflow),
        face_transferred=flux,
        reservoir_supplied=xp.where(p.reservoir, -inflow, 0.0),
    )


def _combine(state, dt, terms):
    """state + dt * sum(weight * rates) for the given (weight, rates) pairs."""
    result = state
    for weight, rates in terms:
        result = jax.tree.map(lambda y, d, w=weight: y + (w * dt) * d, result, rates)
    return result


def node_charge(state, p, *, xp=jnp):
    n = p.active.size
    q = tissue.charge_increment(state, p, xp=xp)
    return xp.concatenate((p.initial_cell_charge_C + q[:n], p.initial_outside_charge_C + q[n:]))


def imex_step(state, dt, control, p, *, xp=jnp):
    """One stiffly accurate IMEX step; returns (new or unchanged state, valid)."""
    f, n = tissue.field_layout(p), p.active.size
    s, explicit_matrix, implicit_matrix = f.surface, p.imex_explicit, p.imex_implicit
    stages = explicit_matrix.shape[0]
    first = readouts(state, control, p, xp=xp)
    start = first.field.potential_V
    valid = first.valid
    amount = p.extracellular_amount_reference + state.extracellular_amount_increment
    predicted = amount + p.imex_operator_time * dt * first.derivative.extracellular_amount_increment
    predicted = xp.where(p.outside_active, predicted / p.extracellular_volume, 1.0)
    valid &= xp.all(xp.isfinite(predicted) & (predicted > 0))
    weight, _ = imex.face_weights(xp.where(predicted > 0, predicted, 1.0), s, xp=xp)
    operator, ok = imex.factor_operator(
        implicit_matrix[-1, -1] * dt, imex.face_laplacian(weight, s, xp=xp), p.boundary_V, f, xp=xp
    )
    valid &= ok
    rates, ok = explicit_rates(state, start, control, p, xp=xp)
    explicit, implicit, valid = [rates], [None], valid & ok
    potential, stage = start, state
    for i in range(1, stages):
        known = _combine(
            state,
            dt,
            [(explicit_matrix[i, j], explicit[j]) for j in range(i)]
            + [(implicit_matrix[i, j], implicit[j]) for j in range(1, i)],
        )
        charge = node_charge(known, p, xp=xp)
        potential, residual = imex.solve_operator(charge, operator, xp=xp)
        scale = xp.maximum(xp.abs(charge), xp.abs(operator.matrix @ potential))
        valid &= xp.all(xp.isfinite(potential))
        valid &= xp.all(xp.abs(residual) <= field.CHARGE_ATOL_C + field.CHARGE_RTOL * scale)
        drift = implicit_rates(weight, potential, state, p, xp=xp)
        implicit.append(drift)
        stage = _combine(known, dt, [(implicit_matrix[i, i], drift)])
        if i < stages - 1:
            rates, ok = explicit_rates(stage, potential, control, p, xp=xp)
            explicit.append(rates)
            valid &= ok
    last = stages - 1

    def applied(name):
        return sum(
            explicit_matrix[last, j] * getattr(explicit[j], name) for j in range(stages - 1)
        ) + sum(implicit_matrix[last, j] * getattr(implicit[j], name) for j in range(1, stages))

    # Dissipation of the applied average face flux, J^2 RT / W >= 0.
    flux = applied("face_transferred")
    heat = (
        1e-3
        * R
        * p.temperature
        * xp.sum(xp.where(weight > 0, flux * flux / xp.where(weight > 0, weight, 1.0), 0.0), axis=0)
    )
    electrode = xp.where(
        p.reservoir,
        (p.field_capacitor_matrix @ potential)[n:] - (p.field_capacitor_matrix @ start)[n:],
        0.0,
    )
    co = xp.where(p.outside_active, p.extracellular_amount_reference / p.extracellular_volume, 1.0)
    mu = R * p.temperature * xp.log(co) + p.valence * F * p.boundary_V
    stage = stage._replace(
        face_dissipated_energy_pJ=state.face_dissipated_energy_pJ + dt * heat,
        electrode_charge_transferred_C=state.electrode_charge_transferred_C + electrode,
        reservoir_work_pJ=state.reservoir_work_pJ
        + 1e-3 * xp.sum(mu * (dt * applied("reservoir_supplied")), axis=0),
        electrode_work_pJ=state.electrode_work_pJ + 1e12 * p.boundary_V * electrode,
    )
    valid &= domain_valid(stage, p, p.active, xp=xp)
    for value in stage:
        valid &= xp.all(xp.isfinite(value))
    return jax.tree.map(lambda old, new: xp.where(valid, new, old), state, stage), valid


def checked_step(state, dt, control, p, active):
    """RK4 for an empty tableau (reference runs); otherwise the declared IMEX step."""
    if p.imex_explicit.shape[0] == 0:
        return rk4_checked_step(rhs, domain_valid, state, dt, control, p, active)
    return imex_step(state, dt, control, p)


def check_definition(spec):
    if spec.model.channels or spec.execution.channel_capacity:
        raise ConfigError("Resolved pump tissue has no channel population")
    kinetic.check_definition(spec)


def check_steps(spec, steps, controls):
    if spec.execution.solver == "rk4":
        return kinetic.check_steps(spec, steps, controls)
    from cells.core.grid import EventGrid

    grid = EventGrid(spec)
    for t in spec.experiment.observation_times:
        try:
            grid.exact_index(t)
        except ConfigError as error:
            raise ConfigError(
                "Resolved pump observations require accepted integration boundaries"
            ) from error
    bound = max(
        (1.3 * np.exp(77 * p.threshold_voltage_V) + 20 for p in spec.model.junctions), default=0.0
    )
    if np.max(steps, initial=0) * bound > GATE_STEP_BOUND:
        raise ConfigError("Resolved junction step exceeds conservative kinetic bound")
    if np.max(steps, initial=0) * explicit_rate_bound(spec) > EXPLICIT_STEP_BOUND:
        raise ConfigError("IMEX step exceeds the explicit-rate stability bound")


def explicit_rate_bound(spec):
    """Gershgorin bound (1/s) on the explicit rates left by implicit electromigration.

    Face diffusion: 2 max over species and finite nodes of sum_f D A/(L V).
    Junction and membrane charge relaxation against the cell's total patch
    capacitance (the outside is held near equipotential by the implicit drift):
    2 max_i sum_j G_j / C_i and max_i sum_m G_m / C_i, with constant-field slope
    conductances bounded by F^2/RT sum z^2 P A max(c) at the declared state.
    """
    _, p = kinetic.initial_values(spec)
    z2 = p.valence**2
    volume = np.where(p.outside_active & ~p.reservoir, p.extracellular_volume * 1e-15, np.inf)
    zero = np.zeros((len(z2), p.outside_active.size))
    rows = scatter(p.face_factor, zero, (p.face_sender,), xp=np)
    rows += scatter(p.face_factor, zero, (p.face_receiver,), xp=np)
    face = 2 * np.max(rows / volume, initial=0.0)
    ci = np.where(p.active, p.amount_reference / p.volume, 0.0)
    co = np.where(p.outside_active, p.extracellular_amount_reference / p.extracellular_volume, 0.0)
    slope = F * F / (R * p.temperature)
    capacitance = scatter(
        p.membrane_capacitance, np.zeros(p.active.size), (p.membrane_cell,), xp=np
    )
    capacitance = np.where(p.active, capacitance, np.inf)
    gj = (
        slope
        * np.sum(
            z2
            * p.junction_permeability
            * np.maximum(ci[:, p.junction_sender], ci[:, p.junction_receiver]),
            axis=0,
        )
        * np.where(p.junction_active, p.junction_area, 0.0)
    )
    cells = scatter(gj, np.zeros(p.active.size), (p.junction_sender,), xp=np)
    cells += scatter(gj, np.zeros(p.active.size), (p.junction_receiver,), xp=np)
    gm = (
        slope
        * np.sum(
            z2
            * p.membrane_permeability
            * np.maximum(ci[:, p.membrane_cell], co[:, p.membrane_outside]),
            axis=0,
        )
        * np.where(p.membrane_active, p.membrane_area, 0.0)
    )
    membranes = scatter(gm, np.zeros(p.active.size), (p.membrane_cell,), xp=np)
    return max(face, 2 * np.max(cells / capacitance), np.max(membranes / capacitance))


def global_charge_bound(row, p):
    """Floor plus a rounding allowance on the absolute terms of the global-charge sum."""
    moved = CHARGE_PER_FMOL * np.sum(np.abs(p.valence * row.reservoir_supplied))
    moved += np.sum(np.abs(row.electrode_charge_transferred_C))
    return GLOBAL_CHARGE_ATOL_C + GLOBAL_CHARGE_ROUNDING * moved


def check_values(state, spec):
    """Family ledgers and tolerances; energy also allows the declared IMEX bound.

    The global-charge bound scales with the charge moved (global_charge_bound).
    """
    _, p = kinetic.initial_values(spec)
    rows = (
        [state]
        if state.amount_increment.ndim == 2
        else [STATE_TYPE(*(v[i] for v in state)) for i in range(len(state.amount_increment))]
    )
    names = (
        "balance_error_fmol",
        "extracellular_balance_error_fmol",
        "global_balance_error_fmol",
        "capacitor_charge_error_C",
        "electrode_charge_error_C",
        "global_charge_error_C",
        "energy_balance_error_pJ",
        "reservoir_work_error_pJ",
        "electrode_work_error_pJ",
        "metabolic_work_error_pJ",
    )
    diagnostics = {"max_" + k: 0.0 for k in names}
    diagnostics["max_energy_balance_relative"] = 0.0
    diagnostics["max_global_charge_bound_ratio"] = 0.0
    rtol = ENERGY_RTOL[spec.execution.solver]
    tol = np.asarray(spec.execution.material_balance_atol_fmol)
    with np.errstate(all="ignore"):
        for row in rows:
            if not domain_valid(row, p, p.active, xp=np):
                raise NumericalError("Invalid resolved pump inventory, gates or padding; no repair")
            b = balances(row, p)
            q = np.r_[p.initial_cell_charge_C, p.initial_outside_charge_C]
            q = q + tissue.charge_increment(row, p, xp=np)
            flows = sum(
                float(np.sum(np.abs(getattr(row, k))))
                for k in STATE_TYPE._fields
                if k.endswith(("_dissipated_energy_pJ", "_work_pJ"))
            )
            limits = (
                tol[:, None],
                tol[:, None],
                tol,
                field.CHARGE_ATOL_C + field.CHARGE_RTOL * np.abs(q),
                field.CHARGE_ATOL_C
                + field.CHARGE_RTOL * np.abs(row.electrode_charge_transferred_C),
                global_charge_bound(row, p),
                tissue.ENERGY_ATOL_PJ + rtol * flows,
                3e-12,
                3e-12,
                3e-12,
            )
            for (name, value), key, bound in zip(b.items(), names, limits, strict=True):
                if not np.isfinite(value).all() or np.any(np.abs(value) > bound):
                    raise NumericalError("Resolved pump accounting failed: " + name)
                key = "max_" + key
                diagnostics[key] = max(diagnostics[key], float(np.max(np.abs(value), initial=0)))
            diagnostics["max_energy_balance_relative"] = max(
                diagnostics["max_energy_balance_relative"],
                float(abs(b["energy"]) / max(flows, tissue.ENERGY_ATOL_PJ)),
            )
            diagnostics["max_global_charge_bound_ratio"] = max(
                diagnostics["max_global_charge_bound_ratio"],
                float(abs(b["global_charge"]) / limits[5]),
            )
    for name in (k for k in STATE_AXES if k.endswith("_dissipated_energy_pJ")):
        value = getattr(state, name)
        if np.min(value, initial=0) < -1e-12 or (
            state.amount_increment.ndim == 3 and np.min(np.diff(value, axis=0), initial=0) < -1e-12
        ):
            raise NumericalError("Resolved pump dissipation cannot be negative or decrease")
    return diagnostics


def summarize(history, diagnostics, spec):
    return tissue.summarize(history, diagnostics, spec) | {
        "model": MODEL_ID,
        "field_solver": spec.execution.field_solver,
        "time_integrator": spec.execution.solver,
        "state_fields": list(STATE_TYPE._fields),
        "junction_law": junction_gate.RELAXATION_LAW_ID,
        "pump_law": pump.LAW_ID,
        "membrane_transfer_ledger": "baseline passive only; pump ledgers separate",
    }


def rebind(spec, **execution):
    """The same definition with changed execution fields, re-parsed strictly."""
    from cells.core.specs import parse_spec

    return parse_spec(replace(spec, execution=replace(spec.execution, **execution)).to_dict())
