"""Stage-consistent spatial transport and cell-owned buffered ER chemistry.

Chemical stores own free and bound material. The spatial amount_increment is an
independent whole-cell exchange ledger: ER exchange and binding cannot charge
the plasma capacitor. Ledger/chemical agreement is checked at every trial.
"""

from dataclasses import make_dataclass
from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.schedule import ERControl, PhysicalIonicGraphControl, control_values
from cells.core.spatial_calcium_spec import MODEL_ID, ionic_spec, store_spec
from cells.core.specs import ConfigError
from cells.models import compartment_reactions as chemistry
from cells.models import er_calcium as er
from cells.models import finite_extracellular as finite
from cells.models import kinetic_finite_bounds as bounds
from cells.models import spatial_extracellular as geometry
from cells.models import spatial_junction as spatial
from cells.observers import hermite_bounds, sample_hermite_history
from cells.processes.electrochemistry import CHARGE_PER_FMOL, F, R
from cells.processes.voltage_gates import VOLTAGE_DOMAIN_V

ER_FIELDS = (
    "chemical_amount_increment",
    "reaction_extent",
    "reaction_dissipated_energy_pJ",
    "er_passive_transferred",
    "er_pump_transferred",
    "er_release_transferred",
    "er_transport_dissipated_energy_pJ",
)
State = NamedTuple("State", [(k, object) for k in (*spatial.STATE_TYPE._fields, *ER_FIELDS)])
Layout = NamedTuple(
    "Layout",
    [
        (k, object)
        for k in (
            *spatial.LAYOUT_TYPE._fields,
            *("er_" + k for k in er.Layout._fields),
            "ionic_species",
            "ion_content",
            "cytosol_selector",
            "free_ion_selector",
            "nonionic_moieties",
            "chemical_fixed_charge_C",
        )
    ],
)
IonicView = NamedTuple(
    "IonicView", [(k, object) for k in (*spatial.LAYOUT_TYPE._fields, "cytosol_amount")]
)
STATE_TYPE, LAYOUT_TYPE = State, Layout
STATE_AXES = spatial.STATE_AXES | {
    new: ["owned_cell", *er.STATE_AXES[old]]
    for new, old in zip(ER_FIELDS, er.State._fields, strict=True)
}
OBSERVER_ID = "spatial_calcium_owned_inventory_readouts@1"
OBSERVATION_SAMPLING = "read_only_control_local_hermite_spatial_calcium_enclosed@1"
STAGE_DOMAIN_ID = "positive_spatial_calcium_owned_charge_affinity@1"
BATCH_CAPACITIES = (*spatial.BATCH_CAPACITIES, "chemical_capacity", "reaction_capacity")
ENERGY_ATOL_PJ = 1e-9
parameters = spatial.parameters
cell_voltage = spatial.cell_voltage


def batch_signature(model):
    return (
        spatial.batch_signature(model),
        len(model.stores),
        chemistry.batch_signature(model.stores[0]),
    )


def ionic_model(spec):
    from cells.models.registry import get_model

    return get_model(ionic_spec(spec).model)


def working_size(spec):
    return ionic_model(spec).working_size(ionic_spec(spec)) + sum(
        er.working_size(store_spec(spec, i)) for i in range(len(spec.model.stores))
    )


def initial_values(spec):
    state, layout = ionic_model(spec).initial_values(ionic_spec(spec))
    pairs = [er.initial_values(store_spec(spec, i)) for i in range(len(spec.model.stores))]
    states = [np.stack([s[j] for s, _ in pairs]) for j in range(len(er.State._fields))]
    layouts = [np.stack([p[j] for _, p in pairs]) for j in range(len(er.Layout._fields))]
    m = spec.model.stores[0]
    indices = np.array([[s.id for s in m.species].index(k) for k in spec.model.species_ids])
    content = np.array(
        [[s.moieties[m.moieties.index(k)] for s in m.species] for k in spec.model.species_ids],
        dtype=np.float64,
    )
    cy_selector = np.zeros((len(pairs), spec.execution.chemical_capacity))
    for i, (_, p) in enumerate(pairs):
        cy_selector[i, p.cytosol] = 1
    ion_selector = np.eye(len(m.species))[:, indices]
    nonionic = np.array([k not in spec.model.species_ids for k in m.moieties])
    fixed = np.stack([p.fixed_charge_C for _, p in pairs])
    for i in range(len(pairs)):
        fixed[i] += (
            layout.capacitance[layout.cell_membranes[i]]
            * layout.voltage_reference[i]
            * cy_selector[i]
        )
    return State(*state, *states), Layout(
        *layout, *layouts, indices, content, cy_selector, ion_selector, nonionic, fixed
    )


def store_state(state, i):
    return er.State(
        *(
            getattr(state, new)[(..., i, *(slice(None) for _ in er.STATE_AXES[old]))]
            for new, old in zip(ER_FIELDS, er.State._fields, strict=True)
        )
    )


def store_layout(layout, i):
    return er.Layout(*(getattr(layout, "er_" + k)[i] for k in er.Layout._fields))


def store_control(control, i):
    return ERControl(
        control.er_reactions[..., i, :],
        control.er_passive[..., i, :],
        control.er_pump[..., i],
        control.er_release[..., i],
    )


def ionic_state(state):
    return spatial.STATE_TYPE(*(getattr(state, k) for k in spatial.STATE_TYPE._fields))


def cytosol_amount(state, p, *, xp=jnp, derivative=False):
    values = []
    for i in range(p.er_initial_amount.shape[0]):
        pair = store_state(state, i).amount_increment
        if not derivative:
            pair = p.er_initial_amount[i] + pair
        values.append(xp.take(pair[..., :, p.er_cytosol[i]], p.ionic_species, axis=-1))
    cells = xp.stack(values, axis=-1)
    return xp.concatenate(
        (cells, xp.zeros((*cells.shape[:-1], p.active.size - len(values)))), axis=-1
    )


def ionic_layout(state, p, *, xp=jnp):
    return IonicView(
        *(getattr(p, k) for k in spatial.LAYOUT_TYPE._fields), cytosol_amount(state, p, xp=xp)
    )


def rhs(state, control, p, active, *, xp=jnp, ionic=spatial):
    view = ionic_layout(state, p, xp=xp)
    external = ionic.rhs(
        ionic_state(state), PhysicalIonicGraphControl(*control[:3]), view, active, xp=xp
    )
    stores = []
    for i in range(p.er_initial_amount.shape[0]):
        local = store_layout(p, i)
        rates = er.rhs(store_state(state, i), store_control(control, i), local, local.active, xp=xp)
        influx = xp.einsum(
            "si,...i->...s", p.free_ion_selector, external.amount_increment[..., :, i]
        )
        stores.append(
            rates._replace(
                amount_increment=rates.amount_increment
                + influx[..., :, None] * p.cytosol_selector[i]
            )
        )
    # The cell axis precedes the original ER state axes, including for host histories.
    return State(
        *external,
        *(
            xp.stack([s[j] for s in stores], axis=-(len(er.STATE_AXES[old]) + 1))
            for j, old in enumerate(er.State._fields)
        ),
    )


def ownership_residual(state, p, *, xp=np):
    totals = xp.einsum(
        "is,...ns->...in", p.ion_content, xp.sum(state.chemical_amount_increment, axis=-1)
    )
    return totals - state.amount_increment[..., :, : p.er_initial_amount.shape[0]]


def domain_valid(state, p, active, *, xp=jnp, ionic=spatial):
    valid = ionic.domain_valid(ionic_state(state), ionic_layout(state, p, xp=xp), active, xp=xp)
    for i in range(p.er_initial_amount.shape[0]):
        local = store_layout(p, i)
        valid &= er.domain_valid(store_state(state, i), local, local.active, xp=xp)
        delta = xp.sum(store_state(state, i).amount_increment, axis=-1)
        moiety = xp.einsum("qs,...s->...q", local.moieties, delta)
        valid &= xp.all(xp.where(p.nonionic_moieties, xp.abs(moiety) <= chemistry.ROUND_ATOL, True))
        charge = xp.sum(local.valence * delta, axis=-1) - xp.sum(
            p.valence[:, 0] * state.amount_increment[..., :, i], axis=-1
        )
        valid &= xp.all(xp.abs(CHARGE_PER_FMOL * charge) <= finite.CHARGE_TOLERANCE_C)
    residue = ownership_residual(state, p, xp=xp)
    return valid & xp.all(xp.isfinite(residue) & (xp.abs(residue) <= chemistry.ROUND_ATOL))


def loss_bound(spec):
    _, p = initial_values(spec)
    global_ions = np.sum(p.extracellular_amount_reference, axis=-1)
    for i in range(len(spec.model.stores)):
        local = store_layout(p, i)
        global_ions += p.ion_content @ np.sum(local.initial_amount * local.active, axis=-1)
    losses = []
    for i, model in enumerate(spec.model.stores):
        local = store_layout(p, i)
        totals = local.moieties @ np.sum(local.initial_amount * local.active, axis=-1)
        for ion, value in zip(spec.model.species_ids, global_ions, strict=True):
            totals[model.moieties.index(ion)] = value
        losses.append(er.loss_bound(store_spec(spec, i), conserved_totals=totals))
    return max(losses)


def check_definition(spec):
    state, p = initial_values(spec)
    if not domain_valid(state, p, p.active, xp=np, ionic=ionic_model(spec)):
        raise ConfigError("Initial spatial calcium inventory/charge domain failed")
    loss_bound(spec)


def check_steps(spec, steps, controls):
    ionic_model(spec).check_steps(ionic_spec(spec), steps, controls)
    h = np.max(steps, initial=0)
    if h > er.MAX_STEP + 16 * np.finfo(float).eps or h * loss_bound(spec) > 0.25:
        raise ConfigError(
            "Spatial calcium requires <=50 us and step * global chemical loss bound <=0.25"
        )


def energy_balance(state, p):
    # Chemical stores count every intracellular species exactly once.
    chemical = 0.0
    er_electric, er_work, er_dissipation = 0.0, 0.0, 0.0
    for i in range(p.er_initial_amount.shape[0]):
        s, local = store_state(state, i), store_layout(p, i)
        chemical += np.sum(chemistry.free_energy_change(s, local), axis=-1)
        v = er.voltage(s, local, xp=np)
        dv = v - local.initial_voltage
        er_electric += 0.5e12 * local.capacitance * dv * (2 * local.initial_voltage + dv)
        drive = er.processes.chemical_drive(er.pump_parameters(local), local.temperature, xp=np)
        er_work += -1e-3 * drive * s.pump_transferred[..., 0]
        er_dissipation += np.sum(s.dissipated_energy_pJ, axis=-1) + np.sum(
            s.transport_dissipated_energy_pJ, axis=-1
        )
    n0 = np.where(p.extracellular_active, p.extracellular_amount_reference, 1.0)
    delta = state.extracellular_amount_increment
    chemical += (
        1e-3
        * R
        * p.temperature[0]
        * np.sum(
            delta * (np.log(n0 / p.extracellular_volume) - 1) + (n0 + delta) * np.log1p(delta / n0),
            axis=(-2, -1),
        )
    )
    dv = (
        CHARGE_PER_FMOL
        / p.capacitance[p.cell_membranes]
        * np.sum(p.valence * state.amount_increment, axis=-2)
    )
    electric = 0.5e12 * np.sum(
        p.capacitance[p.cell_membranes] * dv * (2 * p.voltage_reference + dv), axis=-1
    )
    work = -1e-3 * np.sum(p.pump_drive * state.pump_cycles, axis=-1)
    dissipation = sum(
        np.sum(getattr(state, name), axis=-1)
        for name in (
            "dissipated_energy_pJ",
            "junction_dissipated_energy_pJ",
            "face_dissipated_energy_pJ",
        )
    )
    return chemical + electric + er_electric + dissipation + er_dissipation - work - er_work


def check_values(state, spec, *, extra_exchange=None, extra_energy=0.0):
    _, p = initial_values(spec)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        if not domain_valid(state, p, p.active, xp=np, ionic=ionic_model(spec)):
            raise NumericalError(
                "Spatial calcium inventory, charge, ownership or affinity domain failed"
            )
    # Spatial accounting uses the whole-cell exchange ledger, never a duplicate
    # chemical pool. Its isolated chemical energy is superseded by the joint sum.
    exchange = finite.membrane_exchange(state, p)
    if extra_exchange is not None:
        exchange = exchange + extra_exchange
    local = (
        state.amount_increment
        - finite.gated.scatter(exchange, state.amount_increment, (p.owners,), xp=np)
        - finite.graph.scatter_edges(state.junction_transferred, state.amount_increment, p, xp=np)
    )
    outside = (
        state.extracellular_amount_increment
        + finite.gated.scatter(
            exchange, state.extracellular_amount_increment, (p.outside_owners,), xp=np
        )
        - spatial.face_scatter(
            state.face_transferred, state.extracellular_amount_increment, p, xp=np
        )
    )
    charge = CHARGE_PER_FMOL / p.capacitance[p.cell_membranes] * np.sum(p.valence * local, axis=-2)
    global_ions = np.sum(state.amount_increment, axis=-1) + np.sum(
        state.extracellular_amount_increment, axis=-1
    )
    q = finite.countercharge(state, p)
    tolerance = np.asarray(spec.execution.material_balance_atol_fmol)
    if (
        np.any(np.abs(local) > tolerance[:, None])
        or np.any(np.abs(outside) > tolerance[:, None])
        or np.any(np.abs(global_ions) > tolerance)
        or np.max(np.abs(charge), initial=0) > 1e-8
    ):
        raise NumericalError("Spatial calcium external transfer ledger failed")
    residuals = []
    for i in range(len(spec.model.stores)):
        s, c = store_state(state, i), store_layout(p, i)
        transfer = (
            s.passive_transferred
            + (s.pump_transferred + s.release_transferred) * c.calcium_selector
        )
        influx = np.einsum("si,...i->...s", p.free_ion_selector, state.amount_increment[..., :, i])
        residual = (
            s.amount_increment
            - chemistry.reaction_amount(s.reaction_extent, c)
            - transfer[..., :, None] * c.incidence
            - influx[..., :, None] * p.cytosol_selector[i]
        )
        if np.any(np.abs(residual) > chemistry.ROUND_ATOL * np.maximum(1, c.initial_amount)):
            raise NumericalError("Spatial calcium chemical/reaction/ER transport ledger failed")
        residuals.append(float(np.max(np.abs(residual), initial=0)))
    energy = energy_balance(state, p) + extra_energy
    if not np.isfinite(energy).all() or np.max(np.abs(energy), initial=0) > ENERGY_ATOL_PJ:
        raise NumericalError(
            "Spatial calcium chemical/capacitor/work/dissipation energy balance failed"
        )
    for name in (
        "dissipated_energy_pJ",
        "junction_dissipated_energy_pJ",
        "face_dissipated_energy_pJ",
        "reaction_dissipated_energy_pJ",
        "er_transport_dissipated_energy_pJ",
    ):
        value = getattr(state, name)
        if np.min(value, initial=0) < -chemistry.ROUND_ATOL:
            raise NumericalError("Negative spatial calcium dissipation")
        if (
            value.ndim > len(STATE_AXES[name])
            and np.min(np.diff(value, axis=0), initial=0) < -chemistry.ROUND_ATOL
        ):
            raise NumericalError("Spatial calcium dissipation decreased")
    result = {
        "max_balance_error_fmol": max(
            *residuals,
            float(np.max(np.abs(local), initial=0)),
            float(np.max(np.abs(outside), initial=0)),
        ),
        "max_ownership_error_fmol": float(np.max(np.abs(ownership_residual(state, p)), initial=0)),
        "max_global_ion_balance_error_fmol": float(np.max(np.abs(global_ions), initial=0)),
        "max_countercharge_error_C": float(np.max(np.abs(q), initial=0)),
        "max_energy_balance_error_pJ": float(np.max(np.abs(energy), initial=0)),
    }
    if ionic_model(spec) is spatial:
        field = spatial.field_values(state, p, xp=np)
        result["max_current_normalized"] = float(np.max(field.current_normalized, initial=0))
    else:
        # A tissue field requires actual held controls, checked by the RK4 hook
        # and accepted-grid observer. Do not invent controls for a saved state.
        result["max_component_charge_C"] = float(
            np.max(np.abs(geometry.component_charge(state, p, xp=np)), initial=0)
        )
    return result


DERIVED_FIELDS = (
    "cytosol_amount_fmol",
    "extracellular_amount_fmol",
    "plasma_voltage_V",
    "er_voltage_V",
    "extracellular_potential_V",
)
Observations = make_dataclass(
    "Observations",
    [(k, np.ndarray) for k in ("times", *State._fields, *DERIVED_FIELDS)],
    frozen=True,
)


def check_interpolants(times, history, left, right, p):
    if len(times) < 2:
        return
    for i in range(p.er_initial_amount.shape[0]):
        er.check_interpolants(
            times,
            store_state(history, i),
            store_state(left, i),
            store_state(right, i),
            store_layout(p, i),
        )
    lo, hi = hermite_bounds(
        times,
        history.extracellular_amount_increment,
        left.extracellular_amount_increment,
        right.extracellular_amount_increment,
    )
    if np.any((lo + p.extracellular_amount_reference)[..., p.extracellular_active] <= 0):
        raise NumericalError("Spatial calcium cubic outside amount is nonpositive")
    for name, mask, lower in (
        ("gate", p.channel_active, 0),
        ("junction_gate", p.junction_active, p.junction_minimum[p.junction_active]),
    ):
        lo, hi = hermite_bounds(
            times, getattr(history, name), getattr(left, name), getattr(right, name)
        )
        if np.any(lo[..., mask] < lower) or np.any(hi[..., mask] > 1):
            raise NumericalError("Spatial calcium cubic gate outside domain")

    def slope(s):
        return (
            CHARGE_PER_FMOL
            / p.capacitance[p.cell_membranes]
            * np.sum(p.valence * s.amount_increment, axis=-2)
        )

    voltage = cell_voltage(history.amount_increment, p, xp=np)
    vl, vh = hermite_bounds(times, voltage, slope(left), slope(right))
    limit = (
        spatial.cluster.finite.MAX_ABS_X * R * p.temperature[0] / (F * np.max(np.abs(p.valence)))
    )
    if np.any(vl < -limit) or np.any(vh > limit):
        raise NumericalError("Spatial calcium cubic plasma voltage outside domain")
    indices = p.owners[p.channel_membranes[p.channel_active]]
    if np.any(vl[..., indices] < VOLTAGE_DOMAIN_V[0]) or np.any(
        vh[..., indices] > VOLTAGE_DOMAIN_V[1]
    ):
        raise NumericalError("Spatial calcium cubic channel voltage outside domain")
    lo, hi = hermite_bounds(
        times,
        voltage[..., p.senders] - voltage[..., p.receivers],
        *(slope(s)[..., p.senders] - slope(s)[..., p.receivers] for s in (left, right)),
    )
    if np.any(
        np.maximum(np.abs(lo[..., p.junction_active]), np.abs(hi[..., p.junction_active]))
        > spatial.cluster.gate.MAX_ABS_VOLTAGE_V
    ):
        raise NumericalError("Spatial calcium cubic junction voltage outside domain")
    # Free cytosolic Na/K amounts and whole-cell capacitor charge have distinct
    # enclosures; passing the former explicitly avoids treating bound ions as free.
    cy = cytosol_amount(history, p, xp=np)

    def cy_rate(s):
        return cytosol_amount(s, p, xp=np, derivative=True)

    inside = bounds.cubic_hull(times, cy, cy_rate(left), cy_rate(right))
    bounds.check_pump_interpolants(times, history, left, right, p, inside=inside)
    lo, hi = hermite_bounds(
        times,
        geometry.component_charge(history, p, xp=np),
        *(geometry.component_charge(s, p, xp=np, derivative=True) for s in (left, right)),
    )
    if np.any(np.maximum(np.abs(lo), np.abs(hi)) > geometry.CHARGE_TOLERANCE_C):
        raise NumericalError("Spatial calcium cubic component charge failed")
    for name in (
        "dissipated_energy_pJ",
        "junction_dissipated_energy_pJ",
        "face_dissipated_energy_pJ",
    ):
        values = getattr(history, name)
        lo, hi = hermite_bounds(times, values, getattr(left, name), getattr(right, name))
        if np.any(lo < values[:-1] - chemistry.ROUND_ATOL) or np.any(
            hi > values[1:] + chemistry.ROUND_ATOL
        ):
            raise NumericalError("Spatial calcium cubic dissipation left its interval ledger")


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
        spatial.field_values(sampled, p, xp=np).potential_V,
    )


def summarize(history, diagnostics, spec):
    _, p = initial_values(spec)
    return {
        "model": MODEL_ID,
        "species_ids": list(spec.model.species_ids),
        "chemical_species_ids": [s.id for s in spec.model.stores[0].species],
        "cell_ids": [c.id for c in spec.model.cells],
        "state_axes": STATE_AXES,
        "chemical_fixed_charge_C": p.chemical_fixed_charge_C.tolist(),
        "amount_increment_meaning": (
            "whole-cell ionic exchange ledger; chemical_amount_increment owns material"
        ),
        "final_cytosol_amounts_fmol": cytosol_amount(history, p, xp=np)[-1].tolist(),
        "final_voltage_V": cell_voltage(history.amount_increment, p, xp=np)[-1].tolist(),
        "final_er_voltage_V": [
            float(er.voltage(store_state(history, i), store_layout(p, i), xp=np)[-1])
            for i in range(len(spec.model.stores))
        ],
        "claim_scope": (
            "Synthetic coupled spatial ions, finite buffers and ER; maintained metabolism; "
            "no biological or native BETSE trajectory calibration"
        ),
        "experimental_validation": False,
        **diagnostics,
    }
