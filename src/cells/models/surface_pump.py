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
from functools import cached_property
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
# Declared field solver surface_field.FLOOR_SOLVER_ID: the same with its floor.
FLOOR_LAYOUT_TYPE = NamedTuple(
    "SurfacePumpFloorLayout",
    [(k, object) for k in (*kinetic.FLOOR_LAYOUT_TYPE._fields, *IMEX_FIELDS)],
)
# Energy residual allowed relative to the integrated work and dissipation flows.
# RK4 keeps the family's absolute bound alone. A first/second-order step does
# not integrate the energy identity exactly: measured residuals were 4e-4/2e-6
# (Euler/ARS) on the small fixtures at 0.1 ms and 3e-5/6e-8 at 825 nodes and
# 1 ms; with dt and dt^2 scaling these bounds cover admitted steps. Ledger totals
# are compared with RK4 separately in tests/unit/test_surface_pump.py.
ENERGY_RTOL = {"rk4": 0.0, imex.EULER_ID: 2e-2, imex.ARS222_ID: 2e-3}
# Global charge (electrode charge plus charge-weighted reservoir supply) cancels
# terms that grow with the charge moved through the boundary (moved_charge), so
# its rounding accumulates with their magnitude: a fixed floor fails long runs.
# global_charge_bound adds 256 float64 eps per unit of that magnitude. Both terms
# are running accumulators, so like the material and work ledgers the check also
# allows LEDGER_STEP_ROUNDING eps x steps x moved charge (ledger_magnitudes).
# Short runs stay near 1-3 eps, but on a 7-cell gated sheet with held baths at
# 0.25 ms the residual wandered up to about 200 eps of the moved charge and
# crossed the fixed 256 eps after 1.06e5 steps (resolved_pump_tissue@3 alone,
# water-volume-pump-20261110-01/w1-gcharge-diag-01). With n accepted steps a
# conservation error of more than (256 + 2.5 n) eps of the moved charge (and the
# 3e-25 C floor) fails: 6.1e-13 after 1 s, 3.3e-11 after 1 min, 2.0e-9 after 1 h
# at dt = 1 ms. Recorded max_global_charge_bound_ratio values divide by this
# checked bound, so they are not comparable with values recorded before it.
GLOBAL_CHARGE_ATOL_C = 3e-25
GLOBAL_CHARGE_ROUNDING = 256 * np.finfo(float).eps
# Running material and work ledgers: allowance per accepted step, in eps times the
# magnitudes rounded into a ledger's residual. Each step adds its stage terms to a
# stored ledger y as y + (w dt) r, at most five additions per IMEX step, each
# rounding by up to u |y| (u = eps/2): 2.5 eps |y| per step. A residual compares
# accumulators of one flow (amounts with the route ledgers; cycles x drive with
# metabolic work; supply x mu with reservoir work; electrode charge x V with
# electrode work), so after n accepted steps it is at most 2.5 eps x n x the sum
# of their magnitudes (absolute values, never the cancelled net). The rounding is
# systematic, not a random walk: small increments into growing sums gave residuals
# growing as t^1.6 (13-32 eps x |ledger| at 1e4 steps, 140 at 1.2e5; 2-cell
# relaxing held-bath world at 1 ms, ledger-fix-20261109-01/diag/work_ledgers.json),
# about 1000x inside this allowance, which against the fixed 3e-12 pJ bound alone
# refused that world within 150 s. With n the steps accepted at the row, a
# booking error of relative size 2.5 eps n of the magnitudes is still caught:
# 5.6e-13 after 1 s, 3.3e-11 after 1 min, 2.0e-9 after 1 h at dt = 1 ms.
LEDGER_STEP_ROUNDING = 2.5
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
    kinds = {
        kinetic.FACTORED_LAYOUT_TYPE: LAYOUT_TYPE,
        kinetic.FLOOR_LAYOUT_TYPE: FLOOR_LAYOUT_TYPE,
    }
    if type(layout) not in kinds:
        raise ConfigError("Resolved pump tissue requires the factored field layout")
    solver = spec.execution.solver
    tableau = (
        imex.TABLEAUX[solver]
        if solver in imex.TABLEAUX
        else imex.Tableau(np.zeros((0, 0)), np.zeros((0, 0)), np.asarray(0.0))
    )
    return state, kinds[type(layout)](*layout, *tableau)


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


def electrode_increment(state, stage, p, *, xp=jnp):
    """Charge (C) the held nodes' electrodes deliver over a step, per extracellular slot.

    The change of the held nodes' plate charges that the start and end charge
    states determine (surface_tissue.capacitor_change), which is the reference
    the electrode and global-charge checks compare against. The step's own
    potentials give the same charges only to solve accuracy: the start (Newton
    field) and end (implicit operator) solves differ by about 0.1 ulp of the
    plate charge, and that difference does not telescope, so the ledger drifted
    linearly with the step count (4e-29 C per step on held-bath cells, ledger
    accumulation rounding below 1e-28 C in 5000 steps). This difference does
    telescope. Only ledgers use it; no rate reads it.
    """
    n = p.active.size
    _, start, _ = tissue.capacitor_change(state, p, xp=xp)
    _, end, _ = tissue.capacitor_change(stage, p, xp=xp)
    return xp.where(p.reservoir, end[n:] - start[n:], 0.0)


def imex_step(state, dt, control, p, *, xp=jnp):
    """One stiffly accurate IMEX step; returns (new or unchanged state, valid)."""
    f = tissue.field_layout(p)
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
    electrode = electrode_increment(state, stage, p, xp=xp)
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
    """The step checks of one chunk of steps (StepChecks); they read no controls."""
    bind_step_checks(spec)(steps)


def bind_step_checks(spec):
    """check_steps bound to one definition, for every chunk of its clock (StepChecks)."""
    return StepChecks(spec)


def accepted_observations(spec):
    """Refuse an observation time that is not an accepted boundary of the event grid."""
    from cells.core.grid import EventGrid

    grid = EventGrid(spec)
    for t in spec.experiment.observation_times:
        try:
            grid.exact_index(t)
        except ConfigError as error:
            raise ConfigError(
                "Resolved pump observations require accepted integration boundaries"
            ) from error


class StepChecks:
    """check_steps for one definition, called with the steps of each chunk of its clock.

    core.grid.checked_grid validates a definition's whole declared clock (at every
    plan, restart and segment start) in chunks of at most 1024 steps. These checks
    read a chunk's largest step and quantities of the definition alone: whether
    its observations are accepted boundaries, and its rate bounds, of which
    explicit_rate_bound builds the layout (initial_values). Each such quantity is
    evaluated at its first use and kept for the later chunks, so a chunk costs a
    few comparisons. (Re-evaluated per chunk, @3's took 0.77 s per chunk at 825
    nodes, an hour for a 4.2e6-step clock: clock-validation-20261112-01.) A call
    makes check_steps' refusals in check_steps' order. No check reads the chunk's
    controls, nor do the resolved tissue RK4 checks it calls (surface_kinetic).
    """

    def __init__(self, spec):
        self.spec = spec
        self._observations_accepted = False

    def require_accepted_observations(self):
        if not self._observations_accepted:
            accepted_observations(self.spec)
            self._observations_accepted = True

    @cached_property
    def junction_rate(self):
        return junction_gate_rate_bound(self.spec)

    @cached_property
    def explicit_rate(self):
        return explicit_rate_bound(self.spec)

    def __call__(self, steps):
        spec = self.spec
        if spec.execution.solver == "rk4":
            kinetic.check_steps(spec, steps, None)
            return
        self.require_accepted_observations()
        step = np.max(steps, initial=0)
        if step * self.junction_rate > GATE_STEP_BOUND:
            raise ConfigError("Resolved junction step exceeds conservative kinetic bound")
        if step * self.explicit_rate > EXPLICIT_STEP_BOUND:
            raise ConfigError("IMEX step exceeds the explicit-rate stability bound")


def junction_gate_rate_bound(spec):
    """Bound (1/s) on the junction gates' relaxation rates (1.3 exp(77 threshold) + 20).

    A junction whose minimum open fraction is 1 has its gate pinned at 1: the
    gate starts at 1 (initial >= minimum) and its rate alpha (1 - g) - beta
    (g - minimum) is exactly zero there, so it sets no step bound.
    """
    return max(
        (
            1.3 * np.exp(77 * p.threshold_voltage_V) + 20
            for p in spec.model.junctions
            if p.minimum_open_fraction < 1
        ),
        default=0.0,
    )


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


def moved_charge(row, p, *, xp=np):
    """Absolute terms of the global-charge sum (C): charge-weighted supply, electrode charge."""
    moved = CHARGE_PER_FMOL * xp.sum(xp.abs(p.valence * row.reservoir_supplied))
    return moved + xp.sum(xp.abs(row.electrode_charge_transferred_C))


def global_charge_bound(row, p, *, xp=np):
    """Floor plus a rounding allowance on the absolute terms of the global-charge sum.

    The checked bound also adds the per-step allowance on the same magnitude
    (ledger_limits with ledger_magnitudes).
    """
    return GLOBAL_CHARGE_ATOL_C + GLOBAL_CHARGE_ROUNDING * moved_charge(row, p, xp=xp)


# Ledgers in balances() order: diagnostic name and checked bound per entry.
LEDGER_DIAGNOSTICS = (
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
LEDGERS = (
    "local",
    "outside",
    "total",
    "charge",
    "electrode",
    "global_charge",
    "energy",
    "reservoir_work",
    "electrode_work",
    "metabolic_work",
)
DOMAIN_MESSAGE = "Invalid resolved pump inventory, gates or padding; no repair"
LEDGER_MESSAGE = "Resolved pump accounting failed: "
DISSIPATION_MESSAGE = "Resolved pump dissipation cannot be negative or decrease"
DISSIPATION_FIELDS = tuple(k for k in STATE_AXES if k.endswith("_dissipated_energy_pJ"))


def ledger_magnitudes(row, p, membrane, metabolic, *, xp=np):
    """Magnitudes rounded into each running ledger's residual, in LEDGERS order.

    membrane is the [species, patch] sum of absolute membrane accumulators
    (passive, channel and pump transfers) and metabolic the absolute work and
    cycles x drive terms in balances() order. Global charge sums the electrode
    and charge-weighted supply accumulators and gets their absolute terms
    (moved_charge). The capacitor, electrode and energy checks get None.
    """
    di, do = row.amount_increment, row.extracellular_amount_increment
    hj, hf = xp.abs(row.junction_transferred), xp.abs(row.face_transferred)
    supplied = xp.abs(row.reservoir_supplied)
    local = (
        xp.abs(di)
        + scatter(membrane, di, (p.membrane_cell,), xp=xp)
        + scatter(hj, di, (p.junction_sender,), xp=xp)
        + scatter(hj, di, (p.junction_receiver,), xp=xp)
    )
    outside = (
        xp.abs(do)
        + scatter(membrane, do, (p.membrane_outside,), xp=xp)
        + scatter(hf, do, (p.face_sender,), xp=xp)
        + scatter(hf, do, (p.face_receiver,), xp=xp)
        + supplied
    )
    total = xp.sum(xp.abs(di), axis=1) + xp.sum(xp.abs(do), axis=1) + xp.sum(supplied, axis=1)
    co = xp.where(p.outside_active, p.extracellular_amount_reference / p.extracellular_volume, 1.0)
    mu = R * p.temperature * xp.log(co) + p.valence * F * p.boundary_V
    reservoir_work = xp.abs(row.reservoir_work_pJ) + 1e-3 * xp.sum(xp.abs(mu) * supplied, axis=0)
    electrode_work = xp.abs(row.electrode_work_pJ) + 1e12 * xp.abs(
        p.boundary_V * row.electrode_charge_transferred_C
    )
    unchecked = (None, None)  # Capacitor, electrode.
    charge = moved_charge(row, p, xp=xp)
    rest = (None, reservoir_work, electrode_work, metabolic)  # Energy gets None.
    return (local, outside, total, *unchecked, charge, *rest)


def pump_magnitudes(row, p, *, xp=np):
    """ledger_magnitudes for the Na/K pump ledgers (resolved_pump_tissue@1)."""
    membrane = (
        xp.abs(row.membrane_transferred)
        + kinetic.channel_to_membrane(xp.abs(row.channel_transferred), p, xp=xp)
        + xp.abs(p.stoichiometry * row.pump_cycles)
    )
    metabolic = xp.abs(row.metabolic_work_pJ) + 1e-3 * xp.abs(p.pump_drive * row.pump_cycles)
    return ledger_magnitudes(row, p, membrane, metabolic, xp=xp)


def ledger_limits(row, p, tol, rtol, *, steps, magnitudes, xp=np, flow_fields=None):
    """(flows, bounds): the integrated energy flows and each ledger's bound, in order.

    tol is the per-species material tolerance, rtol the solver's energy tolerance,
    steps the accepted steps at this row and magnitudes the row's
    ledger_magnitudes. Running material and work ledgers add
    LEDGER_STEP_ROUNDING eps x steps x their magnitudes, and the capacitor
    ledger's representative rows their component net-charge rounding
    (surface_field.charge_tolerance). The host check and the device checks share
    these bounds. flow_fields: the heat and work fields by name, declared by the
    caller (a composite's energy-role table); None selects every row field ending in
    _dissipated_energy_pJ or _work_pJ, in field order.
    """
    q = xp.concatenate((p.initial_cell_charge_C, p.initial_outside_charge_C))
    q = q + tissue.charge_increment(row, p, xp=xp)
    if flow_fields is None:
        flow_fields = [
            k for k in type(row)._fields if k.endswith(("_dissipated_energy_pJ", "_work_pJ"))
        ]
    terms = [xp.sum(xp.abs(getattr(row, k))) for k in flow_fields]
    # On the host, Python floats keep sum()'s compensated float summation.
    flows = sum(float(t) for t in terms) if xp is np else sum(terms)
    rounding = LEDGER_STEP_ROUNDING * np.finfo(float).eps * steps
    bounds = (
        tol[:, None],
        tol[:, None],
        tol,
        tissue.capacitor_tolerance(q, row, p, steps, xp=xp),  # Component net charge.
        field.CHARGE_ATOL_C + field.CHARGE_RTOL * xp.abs(row.electrode_charge_transferred_C),
        global_charge_bound(row, p, xp=xp),
        tissue.ENERGY_ATOL_PJ + rtol * flows,
        3e-12,
        3e-12,
        3e-12,
    )
    return flows, tuple(
        bound if magnitude is None else bound + rounding * magnitude
        for bound, magnitude in zip(bounds, magnitudes, strict=True)
    )


def checked_rows(state, spec, p, *, domain, balances, magnitudes, dissipation, steps=None):
    """Host checks of every accepted row (one row or a [time, ...] history).

    steps: accepted steps at each row (its global step index). Without them the
    running ledgers get no rounding allowance (the fixed bounds alone).
    """
    rows = (
        [state]
        if state.amount_increment.ndim == 2
        else [type(state)(*(v[i] for v in state)) for i in range(len(state.amount_increment))]
    )
    steps = [0] * len(rows) if steps is None else list(steps)
    if len(steps) != len(rows):
        raise ValueError("Require one accepted-step count per checked row")
    diagnostics = {"max_" + k: 0.0 for k in LEDGER_DIAGNOSTICS}
    diagnostics["max_energy_balance_relative"] = 0.0
    diagnostics["max_global_charge_bound_ratio"] = 0.0
    rtol = ENERGY_RTOL[spec.execution.solver]
    tol = np.asarray(spec.execution.material_balance_atol_fmol)
    with np.errstate(all="ignore"):
        for row, count in zip(rows, steps, strict=True):
            if not domain(row, p, p.active, xp=np):
                raise NumericalError(DOMAIN_MESSAGE)
            b = balances(row, p)
            flows, limits = ledger_limits(
                row, p, tol, rtol, steps=count, magnitudes=magnitudes(row, p, xp=np)
            )
            for (name, value), key, bound in zip(
                b.items(), LEDGER_DIAGNOSTICS, limits, strict=True
            ):
                if not np.isfinite(value).all() or np.any(np.abs(value) > bound):
                    raise NumericalError(LEDGER_MESSAGE + name)
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
    for name in dissipation:
        value = getattr(state, name)
        if np.min(value, initial=0) < -1e-12 or (
            state.amount_increment.ndim == 3 and np.min(np.diff(value, axis=0), initial=0) < -1e-12
        ):
            raise NumericalError(DISSIPATION_MESSAGE)
    return diagnostics


def check_values(state, spec, steps=None):
    """Family ledgers and tolerances; energy also allows the declared IMEX bound.

    The global-charge bound scales with the charge moved (global_charge_bound);
    running ledgers allow their rounding over the row's accepted steps.
    """
    _, p = kinetic.initial_values(spec)
    return checked_rows(
        state,
        spec,
        p,
        domain=domain_valid,
        balances=balances,
        magnitudes=pump_magnitudes,
        dissipation=DISSIPATION_FIELDS,
        steps=steps,
    )


# Device checks: compiled windows evaluate check_values' tests per accepted row
# (cells.core.vector_windows). Failure codes are in host order; the diagnostics
# are check_values' keys, reduced by maximum over a world's accepted rows.
DEVICE_CHECKS = ("domain", *LEDGERS, "dissipation")
DEVICE_DIAGNOSTICS = (
    *("max_" + k for k in LEDGER_DIAGNOSTICS),
    "max_energy_balance_relative",
    "max_global_charge_bound_ratio",
)


def device_failure_message(check):
    if check == "domain":
        return DOMAIN_MESSAGE
    if check == "dissipation":
        return DISSIPATION_MESSAGE
    return LEDGER_MESSAGE + check


def device_check_constants(spec):
    from cells.models.surface_pump_checks import CheckConstants

    return CheckConstants(
        np.asarray(spec.execution.material_balance_atol_fmol, dtype=np.float64),
        np.asarray(ENERGY_RTOL[spec.execution.solver], dtype=np.float64),
    )


def device_balances(state, p):
    """balances() with jax.numpy (surface_kinetic.balances for an empty channel set)."""
    from cells.models.surface_pump_checks import tissue_balances

    total = (
        state.membrane_transferred
        + kinetic.channel_to_membrane(state.channel_transferred, p, xp=jnp)
        - p.stoichiometry * state.pump_cycles
    )
    result = tissue_balances(state, total, p)
    result["energy"] += (
        jnp.sum(state.channel_dissipated_energy_pJ)
        + jnp.sum(state.pump_dissipated_energy_pJ)
        - jnp.sum(state.metabolic_work_pJ)
    )
    result["metabolic_work"] = state.metabolic_work_pJ + 1e-3 * p.pump_drive * state.pump_cycles
    return result


def device_checks(previous, row, p, constants, steps):
    """check_values' tests for one accepted row on the device: (failed, diagnostics).

    steps is the row's accepted-step count, the host check's value for that row.
    """
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
        magnitudes=pump_magnitudes,
        dissipation=DISSIPATION_FIELDS,
    )


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
