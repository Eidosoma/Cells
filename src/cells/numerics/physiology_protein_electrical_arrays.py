"""Array electrical endpoint diagnostics for a fixed-ion protein movement.

Actual provider records and the direct requested charge change are distinct
inputs. Original anchors and charge grouping remain intact. This pure port
computes no chemical energy, heat, physical drive, elapsed time or publication.
"""

from typing import NamedTuple

import jax.numpy as jnp

from cells.core.physiology_protein_chemical_arrays import _product, _sum_pair
from cells.models import physiology_permeability_view as view
from cells.models import surface_calcium as calcium
from cells.models import surface_tissue as passive
from cells.numerics import physiology_protein_interval_arrays as endpoints
from cells.numerics import surface_field as field
from cells.numerics import surface_transport as transport
from cells.numerics.extracellular_field import ordered_scatter

EPS = 2.220446049250313e-16


class ElectricalEndpointWork(NamedTuple):
    valid: object
    membrane_capacitor_energy_change_pJ: object
    capacitor_energy_change_pJ: object
    represented_material_charge_change_C: object
    requested_material_charge_change_C: object
    charge_input_roundoff_C: object
    matrix_capacitor_charge_change_C: object
    edge_matrix_charge_difference_C: object
    electrode_charge_change_C: object
    saved_electrode_charge_change_C: object
    endpoint_electrode_roundoff_C: object
    electrode_work_pJ: object
    clamp_work_pJ: object
    matrix_energy_change_pJ: object
    edge_matrix_energy_difference_pJ: object
    midpoint_material_work_pJ: object
    electrical_identity_residual_pJ: object
    field_residual_work_bound_pJ: object
    arithmetic_work_bound_pJ: object
    electrical_identity_bound_pJ: object
    gauge_work_coefficient_C: object
    electrical_requirement_pJ: object
    stored_reference_increment_change_C: object
    stored_increment_roundoff_C: object
    checks: object
    diagnostics: object


def _sum(value, *, xp):
    high, low = _sum_pair(xp.asarray(value).reshape(-1), xp=xp)
    return high + low


def _actual_charge(state, p, delta, *, xp):
    anchors = xp.concatenate((p.initial_cell_charge_C, p.initial_outside_charge_C))
    ions = passive.charge_increment(state, p, xp=xp)
    grouped = endpoints._barrier(anchors + delta, xp=xp)
    actual = endpoints._barrier(grouped + ions, xp=xp)
    source = endpoints._barrier(anchors + ions, xp=xp)
    alternate = endpoints._barrier(source + delta, xp=xp)
    return actual, alternate, actual - alternate


def _check_endpoint(label, endpoint, state, control, p, implementation, checks, diagnostics, *, xp):
    delta = endpoint.protein_charge_increment_C
    checks[label + "/source_association"] = endpoints._association(
        endpoint, state, control, p, delta, xp=xp
    )
    # Keep raw endpoint quantities even when its fixed-frame association fails.
    state, control, p = endpoint.source_state, endpoint.source_control, endpoint.runtime_layout
    active = xp.concatenate((p.active, p.outside_active))
    if (
        delta.dtype != xp.float64
        or endpoint.charge_grouping_roundoff_C.shape != delta.shape
        or endpoint.charge_grouping_roundoff_C.dtype != xp.float64
    ):
        raise ValueError("Require original float64 charge/grouping owner arrays")
    checks[label + "/protein_charge_domain"] = xp.all(xp.isfinite(delta)) & xp.all(
        xp.where(active, True, delta == 0)
    )
    checks[label + "/state_domain"] = implementation.domain_valid(state, p, p.active, xp=xp)
    checks[label + "/control_domain"] = xp.all(
        xp.stack([xp.all(xp.isfinite(value) & (value >= 0) & (value <= 1)) for value in control])
    )
    if (
        endpoint.charged_rates_valid.shape != ()
        or endpoint.charged_rates_valid.dtype != xp.bool_
        or endpoint.domain_valid.shape != ()
        or endpoint.domain_valid.dtype != xp.bool_
    ):
        raise ValueError("Require an actual scalar boolean charged-rate provider flag")
    checks[label + "/actual_rates"] = endpoint.charged_rates_valid & endpoint.domain_valid
    phi, vm = endpoint.potential_V, endpoint.membrane_voltage_V
    checks[label + "/field_finite"] = xp.all(xp.isfinite(phi)) & xp.all(xp.isfinite(vm))
    n = p.active.size
    represented_vm = xp.where(
        p.membrane_active, phi[p.membrane_cell] - phi[n + p.membrane_outside], 0.0
    )
    diagnostics[label + "/voltage_relation_residual_V"] = vm - represented_vm
    checks[label + "/voltage_relation"] = xp.all(vm == represented_vm)
    fp = passive.field_layout(p)
    physical_fixed = ~active | xp.concatenate(
        (xp.zeros_like(p.active), p.reservoir | fp.gauge_mask)
    )
    boundary = xp.concatenate((xp.zeros_like(p.initial_cell_charge_C), p.boundary_V))
    fixed_residual = xp.where(physical_fixed, phi - boundary, 0.0)
    diagnostics[label + "/fixed_potential_residual_V"] = fixed_residual
    checks[label + "/fixed_potential"] = xp.all(fixed_residual == 0)
    actual, alternate, grouping = _actual_charge(state, p, delta, xp=xp)
    checks[label + "/charge_grouping"] = xp.all(grouping == endpoint.charge_grouping_roundoff_C)
    diagnostics[label + "/actual_charge_C"] = actual
    diagnostics[label + "/alternate_grouped_charge_C"] = alternate
    diagnostics[label + "/charge_grouping_roundoff_C"] = grouping
    cap = p.field_capacitor_matrix @ phi
    required = xp.concatenate((p.active, p.outside_active & ~p.reservoir))
    budget = field.CHARGE_ATOL_C + field.CHARGE_RTOL * xp.maximum(xp.abs(actual), xp.abs(cap))
    residual = xp.where(required, cap - actual, 0.0)
    diagnostics[label + "/matrix_charge_residual_C"] = residual
    diagnostics[label + "/matrix_charge_bound_C"] = budget
    checks[label + "/matrix_charge"] = xp.all(xp.isfinite(residual)) & xp.all(
        xp.abs(residual) <= budget
    )
    edge_residual, edge_budget = endpoints._endpoint_charge(vm, state, p, delta, xp=xp)
    diagnostics[label + "/edge_charge_residual_C"] = edge_residual
    checks[label + "/edge_charge"] = xp.all(xp.isfinite(edge_residual)) & xp.all(
        xp.abs(edge_residual) <= edge_budget
    )
    inside = (
        calcium.cytosol_amount(state, p, xp=xp)
        if hasattr(state, "chemical_amount_increment")
        else p.amount_reference + state.amount_increment
    )
    outside = p.extracellular_amount_reference + state.extracellular_amount_increment
    ci = xp.where(p.active, inside / p.volume, 1.0)
    co = xp.where(p.outside_active, outside / p.extracellular_volume, 1.0)
    junction = control.junction
    if hasattr(state, "junction_gate"):
        junction = junction * state.junction_gate
    rates = transport.transport(
        ci, co, phi[:n], phi[n:], control.membrane, junction, fp.surface, xp=xp
    )
    current = (
        fp.face_incidence @ rates.face_current_A + fp.junction_incidence @ rates.junction_current_A
    )
    current_scale = xp.maximum(
        xp.max(xp.abs(rates.face_current_A), initial=0.0),
        xp.max(xp.abs(rates.junction_current_A), initial=0.0),
    )
    current_budget = field.CURRENT_ATOL_A + field.CURRENT_RTOL * current_scale
    normalized = xp.max(xp.abs(current), initial=0.0) / current_budget
    diagnostics[label + "/component_current_residual_A"] = current
    diagnostics[label + "/component_current_normalized"] = normalized
    checks[label + "/passive_rates"] = rates.valid
    checks[label + "/component_current"] = xp.isfinite(normalized) & (
        normalized <= field.NEWTON_TARGET
    )
    return actual, cap


def evaluate(
    before_endpoint, after_endpoint, requested_material_charge_change_C, *, implementation, xp=jnp
):
    """Electrical contribution only; strict protein/projected material is external.

    Provider records share complete numeric state, layout/P and controls, while
    their explicit protein charge increments may differ. Requested charge is
    independently supplied on the same padded physical-node axis. Reservoir
    protein charges remain finite owners; only inactive padding must be zero.
    """
    if implementation not in view.IMPLEMENTATIONS.values():
        raise ValueError("Require a static exact ordinary implementation")
    if (
        type(before_endpoint) is not endpoints.ArrayEndpoint
        or type(after_endpoint) is not endpoints.ArrayEndpoint
    ):
        raise ValueError("Require frozen-provider ArrayEndpoint records")
    b, e = before_endpoint, after_endpoint
    state, p, control = b.source_state, b.runtime_layout, b.source_control
    for value in (*state, *control):
        if value.dtype != xp.float64:
            raise ValueError("Require the original float64 state and control arrays")
    requested = xp.asarray(requested_material_charge_change_C)
    if requested.shape != (p.active.size + p.outside_active.size,) or requested.dtype != xp.float64:
        raise ValueError("Require the padded float64 physical-node requested charge axis")
    active = xp.concatenate((p.active, p.outside_active))
    checks = dict(
        requested_domain=xp.all(xp.isfinite(requested))
        & xp.all(xp.where(active, True, requested == 0))
    )
    diagnostics = {}
    q0, cap0 = _check_endpoint(
        "before", b, state, control, p, implementation, checks, diagnostics, xp=xp
    )
    q1, cap1 = _check_endpoint(
        "after", e, state, control, p, implementation, checks, diagnostics, xp=xp
    )
    phi0, phi1, vm0, vm1 = b.potential_V, e.potential_V, b.membrane_voltage_V, e.membrane_voltage_V
    dphi, midpoint = phi1 - phi0, 0.5 * phi0 + 0.5 * phi1
    dvm = vm1 - vm0
    cap_product = _product((0.5e12, p.membrane_capacitance, dvm, vm0 + vm1), xp=xp)
    cap_terms = xp.where(p.membrane_active, cap_product[0], 0.0)
    capacitor = _sum(cap_terms, xp=xp)
    represented = q1 - q0
    stored = e.protein_charge_increment_C - b.protein_charge_increment_C
    matrix_delta = p.field_capacitor_matrix @ dphi
    edge_charge = xp.where(p.membrane_active, p.membrane_capacitance * dvm, 0.0)
    edge_delta = xp.concatenate(
        (
            ordered_scatter(
                edge_charge, xp.zeros_like(p.initial_cell_charge_C), (p.membrane_cell,), xp=xp
            ),
            -ordered_scatter(
                edge_charge, xp.zeros_like(p.initial_outside_charge_C), (p.membrane_outside,), xp=xp
            ),
        )
    )
    n = p.active.size
    electrode = xp.where(p.reservoir, matrix_delta[n:] - represented[n:], 0.0)
    snapshot0 = xp.where(p.reservoir, cap0[n:] - q0[n:], 0.0)
    snapshot1 = xp.where(p.reservoir, cap1[n:] - q1[n:], 0.0)
    saved_electrode = snapshot1 - snapshot0
    work_product = _product((1e12, p.boundary_V, electrode), xp=xp)
    work_terms = work_product[0]
    clamp_work = _sum(work_terms, xp=xp)
    matrix_terms = _product((1e12, midpoint, matrix_delta), xp=xp)
    material_terms = _product((1e12, midpoint, represented), xp=xp)
    matrix_energy, material_work = _sum(matrix_terms[0], xp=xp), _sum(material_terms[0], xp=xp)
    assembly_energy = capacitor - matrix_energy
    identity_error = _sum(xp.stack((capacitor, -clamp_work, -material_work)), xp=xp)
    required = xp.concatenate((p.active, p.outside_active & ~p.reservoir))
    scale0, scale1 = xp.maximum(xp.abs(q0), xp.abs(cap0)), xp.maximum(xp.abs(q1), xp.abs(cap1))
    charge_budget = 2 * field.CHARGE_ATOL_C + field.CHARGE_RTOL * (scale0 + scale1)
    closure_terms = _product((1e12, xp.abs(midpoint), charge_budget), xp=xp)[0]
    closure_bound = _sum(xp.where(required, closure_terms, 0.0), xp=xp)
    magnitude = (
        _sum(xp.abs(cap_terms), xp=xp)
        + _sum(xp.abs(work_terms), xp=xp)
        + _sum(
            _product((1e12, xp.abs(midpoint), xp.abs(represented) + xp.abs(matrix_delta)), xp=xp)[
                0
            ],
            xp=xp,
        )
        + _sum(
            _product(
                (1e12, xp.abs(midpoint), xp.abs(q0) + xp.abs(q1) + xp.abs(cap0) + xp.abs(cap1)),
                xp=xp,
            )[0],
            xp=xp,
        )
    )
    arithmetic_bound = 128 * EPS * magnitude
    bound = closure_bound + xp.abs(assembly_energy) + arithmetic_bound
    checks["electrical_identity"] = (
        xp.isfinite(identity_error) & xp.isfinite(bound) & (xp.abs(identity_error) <= bound)
    )
    products = (cap_product, work_product, matrix_terms, material_terms)
    diagnostics["energy_underflow"] = xp.any(xp.stack([xp.any(value[1]) for value in products]))
    diagnostics["energy_overflow"] = xp.any(xp.stack([xp.any(value[2]) for value in products]))
    checks["energy_representable"] = (
        ~diagnostics["energy_underflow"] & ~diagnostics["energy_overflow"]
    )
    diagnostics.update(
        before_capacitor_node_charge_C=cap0,
        after_capacitor_node_charge_C=cap1,
        before_endpoint_electrode_charge_C=snapshot0,
        after_endpoint_electrode_charge_C=snapshot1,
        stored_protein_increment_change_C=stored,
        represented_net_charge_C=_sum(represented, xp=xp),
        requested_net_charge_C=_sum(requested, xp=xp),
        requested_gross_charge_C=_sum(xp.abs(requested), xp=xp),
        requested_response_unresolved=xp.any(requested != 0) & xp.all(represented == 0),
        reservoir_requested_charge_change_C=xp.where(p.reservoir, requested[n:], 0.0),
        reconstructed_endpoint_electrode_difference=xp.asarray(True),
    )
    scalar_values = (
        capacitor,
        clamp_work,
        matrix_energy,
        material_work,
        assembly_energy,
        identity_error,
        closure_bound,
        arithmetic_bound,
        bound,
    )
    checks["finite_work"] = xp.all(xp.stack([xp.isfinite(value) for value in scalar_values]))
    checks = {key: checks[key] for key in sorted(checks)}
    valid = xp.all(xp.stack(tuple(checks.values())))
    return ElectricalEndpointWork(
        valid,
        cap_terms,
        capacitor,
        represented,
        requested,
        represented - requested,
        matrix_delta,
        edge_delta - matrix_delta,
        electrode,
        saved_electrode,
        saved_electrode - electrode,
        work_terms,
        clamp_work,
        matrix_energy,
        assembly_energy,
        material_work,
        identity_error,
        closure_bound,
        arithmetic_bound,
        bound,
        -_sum(electrode, xp=xp),
        capacitor - clamp_work,
        stored,
        stored - requested,
        checks,
        diagnostics,
    )
