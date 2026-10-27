"""Moving ATPase proteins, joint channels, owned calcium/ER and prescribed injury.

Neutral protein diffusion is separate from electrogenic Na/K pumping. Each pump
population retains its own signed cycles, heat and maintained ATP-reservoir work.
No finite ATP supply, protein exchange or autonomous repair law is introduced.
"""

from dataclasses import make_dataclass
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.surface_mobile_pump_repair_spec import MODEL_ID, prior_spec
from cells.models import surface_calcium as calcium
from cells.models import surface_mobile_repair as prior
from cells.models import surface_redistribution as surface
from cells.models import surface_tissue as ionic
from cells.numerics.extracellular_field import scatter
from cells.processes import kinetic_pump as pump
from cells.processes.electrochemistry import CHARGE_PER_FMOL, R

EXTRA_AXES = {
    "mobile_pump_amount_increment": ["pump_population_slot", "membrane_slot"],
    "mobile_pump_surface_transferred": ["pump_population_slot", "surface_edge_slot"],
    "mobile_pump_surface_dissipated_energy_pJ": ["pump_population_slot", "surface_edge_slot"],
    "mobile_pump_cycles": ["pump_population_slot", "membrane_slot"],
    "mobile_pump_dissipated_energy_pJ": ["pump_population_slot", "membrane_slot"],
    "mobile_pump_metabolic_work_pJ": ["pump_population_slot", "membrane_slot"],
}
STATE_AXES = prior.STATE_AXES | EXTRA_AXES
STATE_TYPE = NamedTuple("SurfaceMobilePumpRepairState", [(k, object) for k in STATE_AXES])
LAYOUT_TYPE = NamedTuple(
    "SurfaceMobilePumpRepairLayout",
    [
        (k, object)
        for k in (
            *prior.LAYOUT_TYPE._fields,
            "mobile_pump_active",
            "mobile_pump_reference",
            "mobile_pump_density_reference",
            "mobile_pump_diffusivity",
            "mobile_pump_turnover",
            "mobile_pump_stoichiometry",
            "mobile_pump_na",
            "mobile_pump_k",
            "mobile_pump_drive",
            *("mobile_pump_" + k for k in pump.Parameters._fields[1:]),
        )
    ],
)
BATCH_CAPACITIES = (*prior.BATCH_CAPACITIES, "pump_population_capacity")
OBSERVER_ID = "resolved_mobile_pumps_channels_calcium_repair_readouts@1"
STAGE_DOMAIN_ID = "positive_mobile_pump_owned_calcium_actual_control@1"
OBSERVATION_SAMPLING = prior.OBSERVATION_SAMPLING
READOUTS = (
    "mobile_pump_amount_fmol",
    "mobile_pump_density_fmol_um2",
    "mobile_pump_surface_flux_fmol_s",
    "mobile_pump_surface_energy_balance_pJ",
    "mobile_pump_cycle_rate_fmol_s",
    "mobile_pump_capacity_fmol_s",
    "mobile_pump_affinity_J_mol",
    "mobile_pump_metabolic_power_pJ_s",
    "mobile_pump_availability",
)
OBSERVATION_FIELDS = (*prior.OBSERVATION_FIELDS, *EXTRA_AXES, *READOUTS)
Observations = make_dataclass(
    "SurfaceMobilePumpRepairObservations",
    [(k, np.ndarray) for k in OBSERVATION_FIELDS],
    frozen=True,
)
parameters = prior.parameters
cytosol_amount = prior.cytosol_amount
store_state, store_layout, er = prior.store_state, prior.store_layout, prior.er
ip3_readouts = prior.ip3_readouts


class Values(NamedTuple):
    prior: object
    field: object
    derivative: object
    motion: object
    capacity: object
    affinity: object
    valid: object


def prior_state(state):
    return prior.STATE_TYPE(*(getattr(state, k) for k in prior.STATE_TYPE._fields))


def prior_layout(p):
    return prior.LAYOUT_TYPE(*(getattr(p, k) for k in prior.LAYOUT_TYPE._fields))


def prior_control(control):
    from cells.core.schedule import SurfaceMobileRepairControl

    return SurfaceMobileRepairControl(
        *(getattr(control, k) for k in SurfaceMobileRepairControl._fields)
    )


def batch_signature(model):
    return (*prior.batch_signature(model), tuple((p.id, p.roles) for p in model.mobile_pumps))


def working_size(spec):
    x = spec.execution
    return prior.working_size(prior_spec(spec)) + 256 * x.pump_population_capacity * (
        x.membrane_capacity + x.surface_edge_capacity + len(spec.model.species_ids)
    )


def initial_values(spec):
    state, p = prior.initial_values(prior_spec(spec))
    m, x = spec.model, spec.execution
    k, n, e = x.pump_population_capacity, x.membrane_capacity, x.surface_edge_capacity
    values = p._asdict() | dict(
        mobile_pump_active=np.arange(k) < len(m.mobile_pumps),
        mobile_pump_reference=np.zeros((k, n)),
        mobile_pump_density_reference=np.ones(k),
        mobile_pump_diffusivity=np.zeros((k, e)),
        mobile_pump_turnover=np.zeros((k, 1)),
        mobile_pump_stoichiometry=np.zeros((len(m.species_ids), k)),
        mobile_pump_na=np.zeros(k, dtype=np.int64),
        mobile_pump_k=np.zeros(k, dtype=np.int64),
        mobile_pump_drive=np.zeros((k, 1)),
    )
    for key in pump.Parameters._fields[1:]:
        values["mobile_pump_" + key] = (
            np.zeros((k, 1)) if key == "delta_g0_J_mol" else np.ones((k, 1))
        )
    for i, pop in enumerate(m.mobile_pumps):
        values["mobile_pump_reference"][i, : len(m.membranes)] = pop.initial_amount_fmol
        values["mobile_pump_density_reference"][i] = pop.reference_density_fmol_per_um2
        values["mobile_pump_diffusivity"][i, : len(m.surface_edges)] = pop.diffusivity_um2_per_s
        values["mobile_pump_turnover"][i, 0] = pop.turnover_per_s
        values["mobile_pump_stoichiometry"][:, i] = pop.stoichiometry
        values["mobile_pump_na"][i], values["mobile_pump_k"][i] = [
            m.species_ids.index(s) for s in pop.roles
        ]
        for key in ("atp_mM", "adp_mM", "pi_mM"):
            values["mobile_pump_" + key][i, 0] = getattr(pop.metabolism, key)
        for key in ("km_na_mM", "km_k_mM", "km_atp_mM"):
            values["mobile_pump_" + key][i, 0] = getattr(pop, key)
        values["mobile_pump_delta_g0_J_mol"][i, 0] = pop.metabolism.delta_g0_J_per_mol
    q = LAYOUT_TYPE(**values)
    q = q._replace(
        mobile_pump_drive=pump.chemical_drive(
            pump_parameters(q, np.zeros((k, n))), p.temperature, xp=np
        )
    )
    return STATE_TYPE(
        *state,
        np.zeros((k, n)),
        np.zeros((k, e)),
        np.zeros((k, e)),
        np.zeros((k, n)),
        np.zeros((k, n)),
        np.zeros((k, n)),
    ), q


def pump_parameters(p, capacity):
    return pump.Parameters(
        capacity, *(getattr(p, "mobile_pump_" + key) for key in pump.Parameters._fields[1:])
    )


def surface_state(state):
    return surface.STATE_TYPE(
        *(getattr(state, k) for k in ionic.STATE_TYPE._fields),
        state.mobile_pump_amount_increment,
        state.mobile_pump_surface_transferred,
        state.mobile_pump_surface_dissipated_energy_pJ,
    )


def surface_layout(p, *, xp=np):
    return prior.surface_layout(prior_layout(p), xp=xp)._replace(
        surface_amount_reference=p.mobile_pump_reference,
        reference_density=p.mobile_pump_density_reference,
        reference_permeability=xp.zeros_like(p.mobile_pump_stoichiometry),
        mobile_effective_charge_e=xp.zeros_like(p.mobile_pump_active, dtype=float),
        mobile_edge_diffusivity_um2_s=p.mobile_pump_diffusivity,
    )


def domain_valid(state, p, active, *, xp=jnp):
    valid = prior.domain_valid(prior_state(state), prior_layout(p), active, xp=xp)
    valid &= surface.surface_domain_valid(surface_state(state), surface_layout(p, xp=xp), xp=xp)
    support = (p.mobile_pump_reference > 0) & (p.mobile_pump_turnover > 0)
    for name in (
        "mobile_pump_cycles",
        "mobile_pump_dissipated_energy_pJ",
        "mobile_pump_metabolic_work_pJ",
    ):
        value = getattr(state, name)
        valid &= xp.all(xp.isfinite(value)) & xp.all(xp.where(support, True, value == 0))
    return valid


def readouts(state, control, p, *, xp=jnp):
    q = prior_layout(p)
    w = prior.readouts(prior_state(state), prior_control(control), q, xp=xp)
    v, r, dr = w.field, w.field.rates, w.derivative
    amount = p.mobile_pump_reference + state.mobile_pump_amount_increment
    capacity = p.mobile_pump_turnover * amount
    support = p.mobile_pump_active[:, None] & p.membrane_active
    ci = xp.where(p.active, calcium.cytosol_amount(state, q, xp=xp) / p.volume, 1.0)
    co = xp.where(
        p.outside_active,
        (p.extracellular_amount_reference + state.extracellular_amount_increment)
        / p.extracellular_volume,
        1.0,
    )
    a, b = p.membrane_cell, p.membrane_outside
    na, ka = p.mobile_pump_na, p.mobile_pump_k
    args = (
        xp.where(support, ci[na[:, None], a], 1.0),
        xp.where(support, co[ka[:, None], b], 1.0),
        xp.where(support, r.membrane_delta_mu_J_mol[na], 0.0),
        xp.where(support, r.membrane_delta_mu_J_mol[ka], 0.0),
        p.temperature,
        pump_parameters(p, capacity),
        control.mobile_pump,
    )
    kinetics = pump.kinetics(*args, xp=xp)
    cycles = xp.where(support, kinetics.cycles_fmol_s, 0.0)
    heat = -1e-3 * cycles * kinetics.cycle_free_energy_J_mol
    work = -1e-3 * cycles * kinetics.chemical_drive_J_mol
    outward = -p.mobile_pump_stoichiometry @ cycles
    cell = -scatter(outward, dr.amount_increment, (a,), xp=xp)
    outside = scatter(outward, dr.extracellular_amount_increment, (b,), xp=xp)
    chemical = xp.stack(
        [
            (p.free_ion_selector @ cell[:, i])[:, None] * p.cytosol_selector[i]
            for i in range(p.er_initial_amount.shape[0])
        ]
    )
    qdot = CHARGE_PER_FMOL * xp.sum(p.valence * xp.concatenate((cell, outside), axis=1), axis=0)
    dphi = calcium.field._capacitor_solve(qdot, xp.zeros_like(qdot), ionic.field_layout(q), xp=xp)
    dvm = xp.where(p.membrane_active, dphi[a] - dphi[p.active.size + b], 0.0)
    chemical_power = (
        1e-3 * R * p.temperature * (xp.sum(xp.log(ci) * cell) + xp.sum(xp.log(co) * outside))
    )
    electric_power = 1e12 * xp.sum(p.membrane_capacitance * r.membrane_voltage_V * dvm)
    motion, mixing_heat = surface.surface_readouts(
        surface_state(state), surface_layout(p, xp=xp), xp=xp
    )
    derivative = STATE_TYPE(
        *dr._replace(
            amount_increment=dr.amount_increment + cell,
            extracellular_amount_increment=dr.extracellular_amount_increment + outside,
            chemical_amount_increment=dr.chemical_amount_increment + chemical,
        ),
        motion.amount_rate_fmol_s,
        motion.flux_fmol_s,
        mixing_heat,
        cycles,
        heat,
        work,
    )
    valid = w.valid & motion.valid & domain_valid(state, p, p.active, xp=xp)
    valid &= xp.all(pump.domain_valid(*args, xp=xp))
    valid &= xp.all(xp.where(support, True, control.mobile_pump == 0))
    for value in (*derivative, chemical_power, electric_power, dvm):
        valid &= xp.all(xp.isfinite(value))
    rates = r._replace(
        cell_rate_fmol_s=r.cell_rate_fmol_s + cell,
        outside_rate_fmol_s=r.outside_rate_fmol_s + outside,
        membrane_flux_fmol_s=r.membrane_flux_fmol_s + outward,
        membrane_current_A=r.membrane_current_A
        + CHARGE_PER_FMOL * xp.sum(p.valence * outward, axis=0),
        membrane_dissipation_pJ_s=r.membrane_dissipation_pJ_s + xp.sum(heat, axis=0),
        valid=valid,
    )
    field = v._replace(
        rates=rates,
        membrane_voltage_rate_V_s=v.membrane_voltage_rate_V_s + dvm,
        chemical_energy_rate_pJ_s=v.chemical_energy_rate_pJ_s + chemical_power,
        capacitor_energy_rate_pJ_s=v.capacitor_energy_rate_pJ_s + electric_power,
        dissipation_pJ_s=v.dissipation_pJ_s + xp.sum(heat),
        energy_balance_pJ_s=v.energy_balance_pJ_s
        + chemical_power
        + electric_power
        + xp.sum(heat)
        - xp.sum(work),
        converged=valid,
    )
    return Values(
        w,
        field,
        derivative,
        motion,
        capacity,
        xp.where(support, kinetics.cycle_free_energy_J_mol, 0.0),
        valid,
    )


def rhs(state, control, p, active, *, xp=jnp):
    w = readouts(state, control, p, xp=xp)
    return STATE_TYPE(*(xp.where(w.valid, v, xp.nan) for v in w.derivative))


def field_values(state, control, p, *, xp=jnp):
    return readouts(state, control, p, xp=xp).field


def control_domain_valid(state, control, p, active, *, xp=jnp):
    valid = domain_valid(state, p, active, xp=xp)
    if xp is np:
        if not valid:
            return np.asarray(False)
        try:
            return readouts(state, control, p, xp=np).valid
        except np.linalg.LinAlgError:
            return np.asarray(False)
    return jax.lax.cond(
        valid, lambda: readouts(state, control, p).valid, lambda: jnp.asarray(False)
    )


domain_valid.with_control = control_domain_valid


def check_definition(spec):
    from cells.core.schedule import control_values

    state, p = initial_values(spec)
    controls = control_values(spec, [c.time for c in spec.experiment.changes])
    for i in range(len(controls.mobile_pump)):
        if not control_domain_valid(
            state, type(controls)(*(v[i] for v in controls)), p, p.active, xp=np
        ):
            raise ConfigError("Mobile pump repair initial state or controls outside domain")


def check_steps(spec, steps, controls):
    prior.check_steps(spec, steps, controls)
    loss = surface.surface_loss_bound(spec.model, spec.model.mobile_pumps)
    if np.max(steps, initial=0) * loss > surface.MAX_SURFACE_LOSS_PER_STEP * (
        1 + 16 * np.finfo(float).eps
    ):
        raise ConfigError("Mobile pump diffusion requires a smaller RK4 step")


def pump_balances(state, p):
    return surface.surface_balances(surface_state(state), surface_layout(p)) | dict(
        metabolic_work=state.mobile_pump_metabolic_work_pJ
        + 1e-3 * p.mobile_pump_drive * state.mobile_pump_cycles
    )


def check_values(state, spec):
    _, p = initial_values(spec)
    outward = -np.einsum("sk,...kn->...sn", p.mobile_pump_stoichiometry, state.mobile_pump_cycles)
    extra = (
        outward,
        state.mobile_pump_dissipated_energy_pJ.sum(axis=-2),
        state.mobile_pump_metabolic_work_pJ.sum(axis=-2),
    )
    diagnostics = prior.check_values(
        prior_state(state), prior_spec(spec), additional_transport=extra
    )
    rows = (
        [state]
        if state.damage.ndim == 1
        else [STATE_TYPE(*(v[i] for v in state)) for i in range(len(state.damage))]
    )
    for row in rows:
        if not domain_valid(row, p, p.active, xp=np):
            raise NumericalError("Invalid mobile pump inventory, history or padding")
        for name, value in pump_balances(row, p).items():
            limit = (
                surface.SURFACE_ENERGY_ATOL_PJ
                if name == "energy"
                else 3e-12
                if name == "metabolic_work"
                else surface.SURFACE_MATERIAL_ATOL_FMOL
            )
            if not np.isfinite(value).all() or np.any(np.abs(value) > limit):
                raise NumericalError("Mobile pump balance failed: " + name)
            key = "max_mobile_pump_" + name + "_error"
            diagnostics[key] = max(
                diagnostics.get(key, 0.0), float(np.max(np.abs(value), initial=0))
            )
    for name in EXTRA_AXES:
        if name.endswith("_dissipated_energy_pJ"):
            value = getattr(state, name)
            if np.min(value, initial=0) < -1e-12 or (
                state.damage.ndim > 1 and np.min(np.diff(value, axis=0), initial=0) < -1e-12
            ):
                raise NumericalError("Mobile pump dissipation is negative or decreased: " + name)
    return diagnostics


def observe_history(times, history, layout, requested, spec):
    from cells.core.schedule import control_values

    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    original = prior.observe_history(
        times, prior_state(history), prior_layout(p), requested, prior_spec(spec)
    )
    controls = control_values(spec, requested)
    rows = []
    for j, t in enumerate(requested):
        i = int(np.flatnonzero(times == t)[0])
        state = STATE_TYPE(*(np.asarray(v[i]) for v in history))
        control = type(controls)(*(v[j] for v in controls))
        w = readouts(state, control, p, xp=np)
        if not w.valid:
            raise NumericalError("Mobile pump repair observation outside domain")
        row = {k: v[j] for k, v in vars(original).items()}
        row.update({k: getattr(state, k) for k in EXTRA_AXES})
        for name in ("membrane_flux_fmol_s", "membrane_current_A"):
            row[name] = getattr(w.field.rates, name)
        row["energy_balance_pJ_s"] = np.atleast_1d(w.field.energy_balance_pJ_s)
        values = (
            p.mobile_pump_reference + state.mobile_pump_amount_increment,
            w.motion.density_fmol_um2,
            w.motion.flux_fmol_s,
            pump_balances(state, p)["energy"],
            w.derivative.mobile_pump_cycles,
            w.capacity,
            w.affinity,
            w.derivative.mobile_pump_metabolic_work_pJ,
            control.mobile_pump,
        )
        row.update(zip(READOUTS, values, strict=True))
        rows.append(tuple(row[k] for k in OBSERVATION_FIELDS))
    if rows:
        return Observations(*(np.stack(v) for v in zip(*rows, strict=True)))
    sample = observe_history(times[:1], STATE_TYPE(*(v[:1] for v in history)), p, times[:1], spec)
    return Observations(
        *(np.empty((0, *v.shape[1:]), dtype=v.dtype) for v in vars(sample).values())
    )


def ensemble_voltage(state, layout, spec, time):
    from cells.core.schedule import control_values

    controls = control_values(spec, [time])
    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    w = readouts(
        STATE_TYPE(*(np.asarray(v) for v in state)),
        type(controls)(*(v[0] for v in controls)),
        p,
        xp=np,
    )
    if not w.valid:
        raise NumericalError("Mobile pump repair ensemble state outside domain")
    return w.field.rates.membrane_voltage_V[p.membrane_active]


def summarize(history, diagnostics, spec):
    return prior.summarize(prior_state(history), diagnostics, prior_spec(spec)) | dict(
        model=MODEL_ID,
        state_fields=list(STATE_AXES),
        mobile_pumps=[p.id for p in spec.model.mobile_pumps],
        mobile_pump_energy_scope=(
            "Maintained ATP/ADP/Pi reservoirs; separate neutral protein inventory"
        ),
    )
