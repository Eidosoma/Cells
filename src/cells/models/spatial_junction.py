"""Kinetic pump/channel/junction cluster coupled to finite spatial surroundings.

One local extracellular owner faces every cell in this bounded family. Junctions
stay within that capacitor component, so the existing zero-net-current outside
solve remains valid. Every RK4 stage solves the field from its own inventories;
no cached field, operator splitting, bath clamp, clipping or charge repair.
"""

from dataclasses import dataclass, replace

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.schedule import PhysicalIonicGraphControl, control_values
from cells.core.spatial_junction_spec import local_spec, passive_spec
from cells.core.specs import SPATIAL_JUNCTION_ID, ConfigError
from cells.core.state import SpatialJunctionLayout, SpatialJunctionState
from cells.models import finite_extracellular as finite
from cells.models import junction_finite_extracellular as cluster
from cells.models import spatial_extracellular as spatial
from cells.numerics import extracellular_field as field
from cells.observers import hermite_bounds

STATE_TYPE = SpatialJunctionState
LAYOUT_TYPE = SpatialJunctionLayout
STATE_AXES = finite.STATE_AXES | {
    "face_transferred": ["species", "face_slot"],
    "face_dissipated_energy_pJ": ["face_slot"],
}
BATCH_CAPACITIES = (*finite.BATCH_CAPACITIES, "face_capacity", "field_solver")
OBSERVER_ID = "spatial_kinetic_cluster_physical_readouts@1"
OBSERVATION_SAMPLING = "read_only_control_local_cubic_hermite_spatial_kinetic_enclosed@1"
STAGE_DOMAIN_ID = "local_cluster_positive_spatial_inventory_current_continuity@1"
MAX_STEP = cluster.MAX_STEP
batch_signature = cluster.batch_signature
parameters = cluster.parameters
cell_voltage = finite.cell_voltage
readouts = cluster.readouts
channel_readouts = cluster.channel_readouts
junction_readouts = cluster.junction_readouts


def working_size(spec):
    x, s = spec.execution, len(spec.model.species_ids)
    return (
        cluster.working_size(spec)
        + (48 * s + 96) * x.face_capacity
        + 24 * x.extracellular_capacity**2
    )


def base_state(state):
    return finite.STATE_TYPE(*(getattr(state, k) for k in finite.STATE_TYPE._fields))


def initial_values(spec):
    state, local = cluster.initial_values(local_spec(spec))
    _, geometry = spatial.initial_values(passive_spec(spec))
    values = local._asdict()
    values.update(
        {k: getattr(geometry, k) for k in geometry._fields if k.startswith("extracellular_")}
    )
    values.update(
        {
            k: getattr(geometry, k)
            for k in (
                "face_active",
                "face_ids",
                "face_factor",
                "gauge_mask",
                "initial_inside_charge_C",
                "initial_outside_charge_C",
            )
        }
    )
    values.update(face_senders=geometry.senders, face_receivers=geometry.receivers)
    shape = (len(spec.model.species_ids), spec.execution.face_capacity)
    return STATE_TYPE(*state, np.zeros(shape), np.zeros(shape[-1])), LAYOUT_TYPE(**values)


def field_values(state, layout, *, xp=jnp):
    outside = layout.extracellular_amount_reference + state.extracellular_amount_increment
    concentration = xp.where(
        layout.extracellular_active, outside / layout.extracellular_volume, 1.0
    )
    geometry = layout._replace(
        senders=layout.face_senders,
        receivers=layout.face_receivers,
        temperature=layout.temperature[0],
    )
    return field.solve(concentration, geometry, xp=xp)


def face_scatter(flux, target, layout, *, xp=jnp):
    return field.scatter(-flux, target, (layout.face_senders,), xp=xp) + field.scatter(
        flux, target, (layout.face_receivers,), xp=xp
    )


def rhs(state, control, layout, active, *, xp=jnp):
    rates = cluster.rhs(base_state(state), control, layout, active, xp=xp)
    bulk = field_values(state, layout, xp=xp)
    rates = rates._replace(
        extracellular_amount_increment=rates.extracellular_amount_increment
        + face_scatter(bulk.flux_fmol_per_s, state.extracellular_amount_increment, layout, xp=xp)
    )
    return STATE_TYPE(*rates, bulk.flux_fmol_per_s, bulk.dissipation_rate_pJ_per_s)


def domain_valid(state, layout, active, *, xp=jnp):
    valid = cluster.domain_valid(base_state(state), layout, active, xp=xp)
    for value in (state.face_transferred, state.face_dissipated_energy_pJ):
        valid = (
            valid
            & xp.all(xp.isfinite(value))
            & xp.all(xp.where(layout.face_active, True, value == 0))
        )
    valid = valid & xp.all(xp.where(layout.face_factor > 0, True, state.face_transferred == 0))
    charge = spatial.component_charge(state, layout, xp=xp)
    valid = valid & xp.all(xp.isfinite(charge) & (xp.abs(charge) <= spatial.CHARGE_TOLERANCE_C))
    for residual in spatial.capacitor_residuals(state, layout, xp=xp):
        valid = valid & xp.all(
            xp.isfinite(residual) & (xp.abs(residual) <= spatial.CHARGE_TOLERANCE_C)
        )

    def check_field():
        bulk = field_values(state, layout, xp=xp)
        ok = xp.all(bulk.current_normalized <= 1.0)
        for value in bulk:
            ok = ok & xp.all(xp.isfinite(value))
        return ok & xp.all(
            xp.where(layout.face_active, bulk.conductance_S > 0, bulk.conductance_S == 0)
        )

    if xp is np:
        if not valid:
            return np.asarray(False)
        try:
            return check_field()
        except np.linalg.LinAlgError:
            return np.asarray(False)
    return jax.lax.cond(valid, check_field, lambda: jnp.asarray(False))


def check_steps(spec, steps, controls):
    cluster.check_steps(local_spec(spec), steps, controls)
    state, layout = initial_values(spec)
    held = control_values(spec, [p.time for p in spec.experiment.changes])
    with np.errstate(over="ignore", invalid="ignore", divide="ignore", under="ignore"):
        if not domain_valid(state, layout, layout.active, xp=np):
            raise ConfigError("Initial spatial cluster violates inventory, charge or field domain")
        for i in range(len(held.membrane)):
            control = PhysicalIonicGraphControl(*(v[i] for v in held))
            if not all(
                np.isfinite(v).all() for v in rhs(state, control, layout, layout.active, xp=np)
            ):
                raise ConfigError("Initial spatial cluster rates exceed finite float64")


def balances(state, layout):
    local, outside, charge, energy, total, q = finite.balances(base_state(state), layout)
    outside = outside - face_scatter(state.face_transferred, outside, layout, xp=np)
    energy = energy + np.sum(state.face_dissipated_energy_pJ, axis=-1)
    return local, outside, charge, energy, total, q


def check_values(state, spec):
    _, layout = initial_values(spec)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        valid = domain_valid(state, layout, layout.active, xp=np)
    result = finite.check_accounting(
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
    )
    bulk = field_values(state, layout, xp=np)
    return result | {
        "max_component_charge_C": float(
            np.max(np.abs(spatial.component_charge(state, layout, xp=np)), initial=0)
        ),
        "max_current_residual_A": float(np.max(np.abs(bulk.current_residual_A), initial=0)),
        "max_current_normalized": float(np.max(bulk.current_normalized, initial=0)),
    }


def check_interpolants(times, history, f0, f1, layout):
    cluster.check_interpolants(times, base_state(history), base_state(f0), base_state(f1), layout)
    if len(times) < 2:
        return
    lo, hi = hermite_bounds(
        times,
        spatial.component_charge(history, layout, xp=np),
        *(spatial.component_charge(f, layout, xp=np, derivative=True) for f in (f0, f1)),
    )
    if not np.isfinite(np.r_[lo.ravel(), hi.ravel()]).all() or np.any(
        np.maximum(np.abs(lo), np.abs(hi)) > spatial.CHARGE_TOLERANCE_C
    ):
        raise NumericalError("Cubic interior violates spatial capacitor-component charge")


@dataclass(frozen=True)
class Observations(finite.Observations):
    face_transferred: np.ndarray
    face_dissipated_energy_pJ: np.ndarray
    extracellular_potential_V: np.ndarray
    face_flux_fmol_per_s: np.ndarray
    face_delta_mu_J_per_mol: np.ndarray
    face_conductance_S: np.ndarray
    face_diffusion_current_A: np.ndarray
    face_drift_current_A: np.ndarray
    face_current_A: np.ndarray
    current_residual_A: np.ndarray
    current_normalized: np.ndarray
    face_dissipation_rate_pJ_per_s: np.ndarray
    component_charge_C: np.ndarray
    cell_potential_V: np.ndarray


def extra_observations(state, control, layout):
    bulk = field_values(state, layout, xp=np)
    voltage = cell_voltage(state.amount_increment, layout, xp=np)
    cell_phi = np.where(
        layout.active,
        voltage + bulk.potential_V[..., layout.outside_owners[layout.cell_membranes]],
        0.0,
    )
    return (
        state.face_transferred,
        state.face_dissipated_energy_pJ,
        *bulk,
        spatial.component_charge(state, layout, xp=np),
        cell_phi,
    )


def observe_history(times, history, layout, requested, spec):
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
    m, x = spec.model, spec.execution
    _, layout = initial_values(spec)
    return {
        "model": SPATIAL_JUNCTION_ID,
        "species_ids": list(m.species_ids),
        "cell_ids": [c.id for c in m.cells],
        "extracellular_ids": [c.id for c in (m.extracellular, *m.surroundings)],
        "local_extracellular_id": m.extracellular.id,
        "face_ids": [f.id for f in m.faces],
        "gauge_reference": m.gauge_reference,
        "capacities": {
            k: getattr(x, k)
            for k in (
                "capacity",
                "membrane_capacity",
                "channel_capacity",
                "edge_capacity",
                "extracellular_capacity",
                "face_capacity",
            )
        },
        "boundary": (
            "closed finite extracellular mesh; junctions within one local outside component"
        ),
        "field_solver": x.field_solver,
        "pump_law": cluster.kinetic.pump.LAW_ID,
        "junction_law": cluster.gate.LAW_ID,
        "external_support": ["temperature", "fixed geometry", "maintained ATP/ADP/Pi reservoirs"],
        "energy_scope": (
            "finite ideal chemical inventories, capacitors, membrane/junction/face "
            "dissipation and hydrolysis work; no gating energy"
        ),
        "final_amounts_fmol": (layout.amount_reference + history.amount_increment[-1])[
            :, : len(m.cells)
        ].tolist(),
        "final_extracellular_amounts_fmol": (
            layout.extracellular_amount_reference + history.extracellular_amount_increment[-1]
        )[:, : 1 + len(m.surroundings)].tolist(),
        "final_voltage_V": cell_voltage(history.amount_increment[-1], layout, xp=np)[
            : len(m.cells)
        ].tolist(),
        **diagnostics,
    }
