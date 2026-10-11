"""Cross-region kinetic tissue with same-stage nonlinear return currents.

Inventories and complete transfer/energy histories evolve through ordinary RK4.
The field is recomputed from that stage and its held junction availability.
This first version exposes accepted-grid observations, not interpolated fields.
"""

from dataclasses import dataclass, replace

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.schedule import PhysicalIonicGraphControl, control_values
from cells.core.specs import ConfigError
from cells.core.tissue_spec import MODEL_ID
from cells.models import finite_extracellular as finite
from cells.models import junction_finite_extracellular as cluster
from cells.models import physical_ionic_graph as graph
from cells.models import spatial_extracellular as spatial
from cells.models import spatial_junction as local
from cells.numerics import tissue_field as field

STATE_TYPE, LAYOUT_TYPE = local.STATE_TYPE, local.LAYOUT_TYPE
STATE_AXES, BATCH_CAPACITIES = local.STATE_AXES, local.BATCH_CAPACITIES
OBSERVER_ID = "cross_region_kinetic_tissue_accepted_grid_readouts@1"
OBSERVATION_SAMPLING = "read_only_accepted_grid_control_dependent_field@1"
STAGE_DOMAIN_ID = "positive_tissue_inventory_control_dependent_return_current@1"
MAX_STEP = cluster.MAX_STEP
batch_signature, parameters = local.batch_signature, local.parameters
base_state, cell_voltage = local.base_state, local.cell_voltage
readouts, channel_readouts = local.readouts, local.channel_readouts
balances, face_scatter = local.balances, local.face_scatter


def working_size(spec):
    return local.working_size(spec) + 96 * spec.execution.extracellular_capacity**2


def initial_values(spec):
    state, layout = local.initial_values(spec)
    names = [c.id for c in (spec.model.extracellular, *spec.model.surroundings)]
    owners = np.zeros(spec.execution.membrane_capacity, dtype=np.int64)
    owners[: len(spec.model.membranes)] = [names.index(p.outside) for p in spec.model.membranes]
    # The legacy binder initializes one local outside. Replace its geometry and
    # global charge anchor with the already validated, explicitly owned mesh.
    layout = layout._replace(
        outside_owners=owners,
        initial_countercharge_C=np.asarray(
            np.sum(layout.initial_inside_charge_C) + np.sum(layout.initial_outside_charge_C)
        ),
    )
    field.validate_layout(field_layout(layout))
    return state, layout


def field_layout(p):
    return field.Layout(
        p.temperature[0],
        p.valence,
        p.active,
        p.outside_owners[p.cell_membranes],
        p.extracellular_active,
        p.gauge_mask,
        p.face_active,
        p.face_senders,
        p.face_receivers,
        p.face_factor,
        p.junction_active,
        p.senders,
        p.receivers,
        p.junction_area,
        p.junction_permeability,
    )


def field_values(state, availability, layout, *, xp=jnp):
    if state.amount_increment.ndim != 2:
        if xp is not np or state.amount_increment.ndim != 3:
            raise ValueError("Tissue fields use one world or a host observation history")
        if len(state.amount_increment) == 0:
            # Observer slopes for an endpoint-only resumed history have zero rows.
            dummy = STATE_TYPE(*(np.zeros(v.shape[1:], dtype=v.dtype) for v in state))
            dummy = dummy._replace(junction_gate=layout.junction_minimum.copy())
            sample = field_values(dummy, np.zeros(layout.junction_active.size), layout, xp=np)
            return field.Values(
                *(np.empty((0, *np.shape(v)), dtype=np.asarray(v).dtype) for v in sample)
            )
        rows = [
            field_values(STATE_TYPE(*(v[i] for v in state)), availability[i], layout, xp=np)
            for i in range(len(state.amount_increment))
        ]
        return field.Values(*(np.stack(v) for v in zip(*rows, strict=True)))
    inside, outside = finite.physical_amounts(state, layout)
    return field.solve(
        xp.where(layout.active, inside / layout.volume, 1.0),
        xp.where(layout.extracellular_active, outside / layout.extracellular_volume, 1.0),
        cell_voltage(state.amount_increment, layout, xp=xp),
        state.junction_gate,
        availability,
        field_layout(layout),
        xp=xp,
    )


def field_valid(values, state, layout, *, xp):
    gate = cluster.gate.domain_valid(
        state.junction_gate,
        values.junction_voltage_V,
        cluster.gate_parameters(layout),
        1.0,
        xp=xp,
    )
    return xp.all(values.converged) & xp.all(xp.where(layout.junction_active, gate, True))


def junction_values(state, availability, layout, values, *, xp):
    target, rate, _ = cluster.junction_kinetics(
        state.junction_gate, values.junction_voltage_V, layout, xp=xp
    )
    opened = xp.broadcast_to(
        state.junction_gate[..., None, :], values.junction_flux_fmol_per_s.shape
    )
    return graph.JunctionReadouts(
        *(
            xp.where(layout.junction_active, v, 0.0)
            for v in (
                values.junction_voltage_V,
                target,
                rate,
                opened,
                layout.junction_permeability * availability[..., None, :] * opened,
                values.junction_flux_fmol_per_s,
                -values.junction_delta_mu_J_per_mol,
                values.junction_current_A,
                values.junction_dissipation_rate_pJ_per_s,
            )
        )
    )


def junction_readouts(state, availability, layout, *, xp=jnp):
    values = field_values(state, availability, layout, xp=xp)
    readout = junction_values(state, availability, layout, values, xp=xp)
    ok = field_valid(values, state, layout, xp=xp)
    return graph.JunctionReadouts(*(xp.where(ok, v, xp.nan) for v in readout))


def rhs(state, control, layout, active, *, xp=jnp):
    values = field_values(state, control.junction, layout, xp=xp)
    _, leak, cycles, mu, affinity = readouts(state, control.membrane, layout, xp=xp)
    rates = finite.assemble_rhs(
        base_state(state),
        layout,
        active,
        leak,
        cycles,
        mu,
        affinity,
        channel_readouts(state, control.channel, layout, xp=xp),
        junction_values(state, control.junction, layout, values, xp=xp),
        xp=xp,
    )
    rates = rates._replace(
        extracellular_amount_increment=rates.extracellular_amount_increment
        + face_scatter(
            values.face_flux_fmol_per_s, state.extracellular_amount_increment, layout, xp=xp
        )
    )
    result = STATE_TYPE(*rates, values.face_flux_fmol_per_s, values.face_dissipation_rate_pJ_per_s)
    ok = field_valid(values, state, layout, xp=xp)
    # Invalid algebraic solves cannot masquerade as finite, acceptable rates.
    return STATE_TYPE(*(xp.where(ok, v, xp.nan) for v in result))


def domain_valid(state, layout, active, *, xp=jnp):
    """State-only checks; the RK4 hook below checks the actual held-control field."""
    valid = cluster.kinetic.domain_valid(base_state(state), layout, active, xp=xp)
    valid = valid & xp.all(
        xp.where(layout.junction_active, state.junction_gate >= layout.junction_minimum, True)
    )
    for value in (state.face_transferred, state.face_dissipated_energy_pJ):
        valid = (
            valid
            & xp.all(xp.isfinite(value))
            & xp.all(xp.where(layout.face_active, True, value == 0))
        )
    valid = valid & xp.all(xp.where(layout.face_factor > 0, True, state.face_transferred == 0))
    for value in (
        spatial.component_charge(state, layout, xp=xp),
        *spatial.capacitor_residuals(state, layout, xp=xp),
    ):
        valid = valid & xp.all(xp.isfinite(value) & (xp.abs(value) <= spatial.CHARGE_TOLERANCE_C))
    return valid


def control_domain_valid(state, control, layout, active, *, xp=jnp):
    valid = domain_valid(state, layout, active, xp=xp)

    def check():
        return field_valid(
            field_values(state, control.junction, layout, xp=xp), state, layout, xp=xp
        )

    if xp is np:
        if not valid:
            return np.asarray(False)
        try:
            return check()
        except np.linalg.LinAlgError:
            return np.asarray(False)
    return jax.lax.cond(valid, check, lambda: jnp.asarray(False))


domain_valid.with_control = control_domain_valid


def check_definition(spec):
    m = spec.model
    compact = replace(
        spec,
        execution=replace(
            spec.execution,
            capacity=len(m.cells),
            membrane_capacity=len(m.membranes),
            channel_capacity=len(m.channels),
            edge_capacity=len(m.junctions),
            extracellular_capacity=1 + len(m.surroundings),
            face_capacity=len(m.faces),
        ),
    )
    state, layout = initial_values(compact)
    held = control_values(compact, [p.time for p in compact.experiment.changes])
    with np.errstate(all="ignore"):
        for i in range(len(held.membrane)):
            control = PhysicalIonicGraphControl(*(v[i] for v in held))
            if not control_domain_valid(state, control, layout, layout.active, xp=np) or not all(
                np.isfinite(v).all() for v in rhs(state, control, layout, layout.active, xp=np)
            ):
                raise ConfigError("Initial tissue field, intrinsic gate or physical rates invalid")


def check_steps(spec, steps, controls):
    maximum = np.max(steps, initial=0)
    if maximum > MAX_STEP + 16 * np.finfo(float).eps:
        raise ConfigError("Tissue RK4 steps must be <= 0.0001 s")
    for edge in spec.model.junctions:
        if maximum * (1.3 * np.exp(77 * edge.threshold_voltage_V) + 20) > 0.125:
            raise ConfigError("Tissue RK4 step does not resolve junction kinetics")
    from cells.core.grid import EventGrid

    grid = EventGrid(spec)
    for time in spec.experiment.observation_times:
        try:
            grid.exact_index(time)
        except ConfigError as error:
            raise ConfigError(
                "Tissue @3 observations must lie on accepted integration boundaries"
            ) from error


def check_values(state, spec):
    _, layout = initial_values(spec)
    with np.errstate(all="ignore"):
        valid = domain_valid(state, layout, layout.active, xp=np)
    return finite.check_accounting(
        state,
        spec,
        layout,
        valid,
        balances=balances,
        dissipation_fields=(
            "dissipated_energy_pJ",
            "junction_dissipated_energy_pJ",
            "face_dissipated_energy_pJ",
        ),
    ) | {
        "max_component_charge_C": float(
            np.max(np.abs(spatial.component_charge(state, layout, xp=np)), initial=0)
        ),
    }


@dataclass(frozen=True)
class Observations(finite.Observations):
    face_transferred: np.ndarray
    face_dissipated_energy_pJ: np.ndarray
    extracellular_potential_V: np.ndarray
    cell_potential_V: np.ndarray
    face_flux_fmol_per_s: np.ndarray
    face_delta_mu_J_per_mol: np.ndarray
    face_current_A: np.ndarray
    face_dissipation_rate_pJ_per_s: np.ndarray
    current_residual_A: np.ndarray
    current_normalized: np.ndarray
    field_iterations: np.ndarray
    component_charge_C: np.ndarray


def extra_observations(state, control, layout):
    values = field_values(state, control.junction, layout, xp=np)
    if not field_valid(values, state, layout, xp=np):
        raise NumericalError("Observation tissue field failed its current or voltage domain")
    return (
        state.face_transferred,
        state.face_dissipated_energy_pJ,
        values.potential_V,
        values.cell_potential_V,
        values.face_flux_fmol_per_s,
        values.face_delta_mu_J_per_mol,
        values.face_current_A,
        values.face_dissipation_rate_pJ_per_s,
        values.current_residual_A,
        values.current_normalized,
        values.iterations,
        spatial.component_charge(state, layout, xp=np),
    )


def check_interpolants(times, history, f0, f1, layout):
    # No continuous nonlinear-field enclosure is claimed. check_steps rejects
    # off-grid observations, and every requested state/field is checked below.
    return None


def observe_history(times, history, layout, requested, spec):
    if any(t not in times for t in requested):
        raise ConfigError("Tissue observations require exact accepted times")
    layout = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    result = finite.observe_composed_history(
        times,
        history,
        layout,
        requested,
        spec,
        rhs=rhs,
        readouts=readouts,
        check_values=check_values,
        check_interpolants=check_interpolants,
        junction_readouts=junction_readouts,
        state_type=STATE_TYPE,
        balances=balances,
        observation_type=Observations,
        extra_observations=extra_observations,
    )
    return replace(
        result,
        extracellular_rate_fmol_per_s=result.extracellular_rate_fmol_per_s
        + face_scatter(result.face_flux_fmol_per_s, result.extracellular_amount, layout, xp=np),
    )


def summarize(history, diagnostics, spec):
    result = local.summarize(history, diagnostics, spec)
    result.pop("local_extracellular_id")
    return result | {
        "model": MODEL_ID,
        "boundary": "closed finite tissue with cross-region junctions",
        "closure_law": field.LAW_ID,
        "membrane_outside_owners": {p.id: p.outside for p in spec.model.membranes},
        "observation_scope": "accepted integration boundaries only",
    }
