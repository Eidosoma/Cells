"""Owned calcium/IP3 and coupled tissue fields at the same integration stage.

Only free cytosolic ions drive transport. The plasma capacitor still uses the
whole-cell exchange ledger. Assembly events pass their actual held controls
through the ordinary RK4 guard, including the combined endpoint.
"""

from dataclasses import make_dataclass, replace

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.schedule import control_values
from cells.core.specs import ConfigError
from cells.core.tissue_calcium_spec import MODEL_ID
from cells.models import ip3_calcium as base
from cells.models import spatial_calcium as chemistry
from cells.models import tissue

State, Layout = base.State, base.Layout
STATE_TYPE, LAYOUT_TYPE = State, Layout
STATE_AXES, BATCH_CAPACITIES = base.STATE_AXES, base.BATCH_CAPACITIES
OBSERVER_ID = "cross_region_calcium_ip3_accepted_grid_readouts@1"
OBSERVATION_SAMPLING = "read_only_accepted_grid_owned_calcium_tissue_field@1"
STAGE_DOMAIN_ID = "positive_owned_calcium_control_dependent_tissue_field@1"
ENERGY_ATOL_PJ = base.ENERGY_ATOL_PJ
parameters, cell_voltage = base.parameters, base.cell_voltage
cytosol_amount, store_state, store_layout, er = (
    base.cytosol_amount,
    base.store_state,
    base.store_layout,
    base.er,
)
initial_values, working_size = base.initial_values, base.working_size
batch_signature, ip3_readouts = base.batch_signature, base.ip3_readouts
check_values, energy_balance = base.check_values, base.energy_balance


def check_steps(spec, steps, controls):
    # The full clock includes chemical, plasma and calcium-channel interventions.
    # Layer projections used for numerical loss bounds omit some of those events.
    tissue.check_steps(spec, steps, controls)
    numerical = replace(
        spec,
        experiment=replace(spec.experiment, observation_times=(0.0, spec.experiment.end_time)),
    )
    base.check_steps(numerical, steps, controls)


def rhs(state, control, p, active, *, xp=jnp):
    if xp is np and state.amount_increment.ndim == 3:
        if len(state.amount_increment) == 0:
            return State(*(np.zeros_like(v) for v in state))
        rows = [
            rhs(
                State(*(v[i] for v in state)),
                type(control)(*(v[i] for v in control)),
                p,
                active,
                xp=np,
            )
            for i in range(len(state.amount_increment))
        ]
        return State(*(np.stack(v) for v in zip(*rows, strict=True)))
    return base.rhs(state, control, p, active, xp=xp, ionic=tissue)


def domain_valid(state, p, active, *, xp=jnp):
    return base.domain_valid(state, p, active, xp=xp, ionic=tissue)


def field_values(state, control, p, *, xp=jnp):
    if xp is np and state.amount_increment.ndim == 3:
        if len(state.amount_increment) == 0:
            dummy = State(*(np.zeros(v.shape[1:], dtype=v.dtype) for v in state))
            dummy = dummy._replace(junction_gate=p.junction_minimum.copy())
            held = type(control)(*(np.zeros(v.shape[1:]) for v in control))
            sample = field_values(dummy, held, p, xp=np)
            return tissue.field.Values(
                *(np.empty((0, *np.shape(v)), dtype=np.asarray(v).dtype) for v in sample)
            )
        rows = [
            field_values(
                State(*(v[i] for v in state)), type(control)(*(v[i] for v in control)), p, xp=np
            )
            for i in range(len(state.amount_increment))
        ]
        return tissue.field.Values(*(np.stack(v) for v in zip(*rows, strict=True)))
    return tissue.field_values(
        chemistry.ionic_state(state),
        control.junction,
        chemistry.ionic_layout(state, p, xp=xp),
        xp=xp,
    )


def control_domain_valid(state, control, p, active, *, xp=jnp):
    valid = domain_valid(state, p, active, xp=xp)

    def check():
        return tissue.field_valid(field_values(state, control, p, xp=xp), state, p, xp=xp)

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
    base.check_definition(spec)
    state, p = initial_values(spec)
    controls = control_values(spec, [c.time for c in spec.experiment.changes])
    for i in range(len(spec.experiment.changes)):
        held = type(controls)(*(v[i] for v in controls))
        if not control_domain_valid(state, held, p, p.active, xp=np):
            raise ConfigError("Initial owned calcium tissue field/voltage domain failed")
        if not all(np.isfinite(v).all() for v in rhs(state, held, p, p.active, xp=np)):
            raise ConfigError("Initial owned calcium tissue rates are not finite")


Observations = make_dataclass(
    "Observations",
    [
        (k, np.ndarray)
        for k in (
            *base.Observations.__dataclass_fields__,
            "cell_potential_V",
            "junction_voltage_V",
            "current_residual_A",
            "current_normalized",
            "component_charge_C",
        )
    ],
    frozen=True,
)


def observe_history(times, history, layout, requested, spec):
    requested = np.asarray(requested, dtype=np.float64)
    indices = np.searchsorted(times, requested)
    if np.any(indices >= len(times)) or not np.array_equal(np.asarray(times)[indices], requested):
        raise ConfigError("Tissue calcium observations require exact accepted times")
    p = Layout(*(np.asarray(v) for v in layout))
    sampled = State(*(np.asarray(v)[indices] for v in history))
    check_values(sampled, spec)
    controls = control_values(spec, requested)
    field = field_values(sampled, controls, p, xp=np)
    if not tissue.field_valid(field, sampled, p, xp=np):
        raise NumericalError("Observed calcium tissue field failed its current/voltage domain")
    return Observations(
        requested,
        *sampled,
        cytosol_amount(sampled, p, xp=np),
        p.extracellular_amount_reference + sampled.extracellular_amount_increment,
        cell_voltage(sampled.amount_increment, p, xp=np),
        np.stack(
            [
                er.voltage(store_state(sampled, i), store_layout(p, i), xp=np)
                for i in range(p.er_initial_amount.shape[0])
            ],
            axis=-1,
        ),
        field.potential_V,
        *ip3_readouts(sampled, p, xp=np),
        field.cell_potential_V,
        field.junction_voltage_V,
        field.current_residual_A,
        field.current_normalized,
        tissue.spatial.component_charge(sampled, p, xp=np),
    )


def summarize(history, diagnostics, spec):
    return base.summarize(history, diagnostics, spec) | {
        "model": MODEL_ID,
        "closure_law": tissue.field.LAW_ID,
        "membrane_outside_owners": {p.id: p.outside for p in spec.model.membranes},
        "observation_scope": "accepted integration boundaries only",
        "claim_scope": (
            "Synthetic cross-region calcium/IP3 composition; "
            "no native full BETSE or biological validation"
        ),
    }
