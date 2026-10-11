"""Finite IP3 inventory gates ER calcium release at every shared solver stage."""

from dataclasses import make_dataclass
from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

from cells.core.ip3_calcium_spec import MODEL_ID, base_spec
from cells.core.schedule import control_values
from cells.models import gated_calcium as base
from cells.observers import sample_hermite_history
from cells.processes import ip3_release as process

State = STATE_TYPE = base.State
Layout = NamedTuple(
    "Layout",
    [(k, object) for k in (*base.Layout._fields, "ip3_weights", "ip3_activation", "ip3_power")],
)
LAYOUT_TYPE = Layout
STATE_AXES, BATCH_CAPACITIES = base.STATE_AXES, base.BATCH_CAPACITIES
OBSERVER_ID = "spatial_calcium_ip3_owned_readouts@1"
OBSERVATION_SAMPLING = "read_only_control_local_hermite_ip3_calcium_enclosed@1"
STAGE_DOMAIN_ID = "positive_spatial_calcium_finite_ip3@1"
ENERGY_ATOL_PJ = base.ENERGY_ATOL_PJ
parameters, cell_voltage = base.parameters, base.cell_voltage
cytosol_amount, store_state, store_layout, er = (
    base.cytosol_amount,
    base.store_state,
    base.store_layout,
    base.er,
)
domain_valid, check_definition, check_steps = (
    base.domain_valid,
    base.check_definition,
    base.check_steps,
)
check_values, check_interpolants, energy_balance = (
    base.check_values,
    base.check_interpolants,
    base.energy_balance,
)


def batch_signature(model):
    return (
        base.batch_signature(model),
        tuple(r.species_id for r in model.ip3_release),
        process.LAW_ID,
    )


def working_size(spec):
    return base.working_size(base_spec(spec)) + 16 * len(spec.model.stores) * (
        len(spec.model.stores[0].species) * spec.execution.chemical_capacity + 2
    )


def initial_values(spec):
    state, p = base.initial_values(base_spec(spec))
    weights = np.zeros_like(p.er_initial_amount)
    for i, binding in enumerate(spec.model.ip3_release):
        species = [s.id for s in spec.model.stores[i].species].index(binding.species_id)
        weights[i, species, p.er_cytosol[i]] = 1 / p.er_volume[i, p.er_cytosol[i]]
    return state, Layout(
        *p,
        weights,
        np.array([r.activation_mM for r in spec.model.ip3_release]),
        np.array([r.activation_n for r in spec.model.ip3_release], dtype=np.float64),
    )


def ip3_readouts(state, p, *, xp=jnp):
    concentration = xp.sum(
        (p.er_initial_amount + state.chemical_amount_increment) * p.ip3_weights, axis=(-2, -1)
    )
    return concentration, process.open_fraction(concentration, p.ip3_activation, p.ip3_power, xp=xp)


def rhs(state, control, p, active, *, xp=jnp, ionic=base.spatial.spatial):
    _, fraction = ip3_readouts(state, p, xp=xp)
    # Only the release permeability changes. Its existing inventory, capacitor
    # and energy ledgers therefore see exactly the same stage-dependent flux.
    return base.rhs(
        state,
        control._replace(er_release=control.er_release * fraction),
        p,
        active,
        xp=xp,
        ionic=ionic,
    )


Observations = make_dataclass(
    "Observations",
    [
        (k, np.ndarray)
        for k in (
            "times",
            *State._fields,
            *base.spatial.DERIVED_FIELDS,
            "ip3_cytosol_mM",
            "ip3_release_fraction",
        )
    ],
    frozen=True,
)


def observe_history(times, history, layout, requested, spec):
    p = Layout(*(np.asarray(v) for v in layout))
    requested = np.asarray(requested, dtype=np.float64)
    controls = control_values(spec, times[:-1])
    left, right = (
        rhs(State(*(v[part] for v in history)), controls, p, p.active, xp=np)
        for part in (slice(None, -1), slice(1, None))
    )
    check_interpolants(times, history, left, right, p)
    sampled = State(
        *(
            sample_hermite_history(times, v, requested, a, b)
            for v, a, b in zip(history, left, right, strict=True)
        )
    )
    check_values(sampled, spec)
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
        base.spatial.spatial.field_values(sampled, p, xp=np).potential_V,
        *ip3_readouts(sampled, p, xp=np),
    )


def summarize(history, diagnostics, spec):
    _, p = initial_values(spec)
    concentration, fraction = ip3_readouts(history, p, xp=np)
    return base.summarize(history, diagnostics, base_spec(spec)) | {
        "model": MODEL_ID,
        "ip3_release_law": process.LAW_ID,
        "ip3_cell_ids": [r.cell_id for r in spec.model.ip3_release],
        "final_ip3_cytosol_mM": concentration[-1].tolist(),
        "final_ip3_release_fraction": fraction[-1].tolist(),
        "claim_scope": (
            "Pinned BETSE IP3/calcium release factor using finite owned ligand chemistry; "
            "synthetic IP3 buffering, no native full trajectories or biological calibration"
        ),
    }
