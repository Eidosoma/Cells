"""Conditional ideal-protein endpoint work at one fixed ordinary tissue state.

Both material endpoints share one explicit electrical reference and the same
current permeability. No trajectory, ionic holding process, driving law or
heat is inferred. Original numeric/material objects and anchors are unchanged.
"""

import math
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np

from cells.core import physiology_protein_projection as projection
from cells.core import physiology_tissue_binding as units
from cells.core.errors import NumericalError
from cells.models import physiology_permeability_view as immutable
from cells.models import physiology_protein_charge_view as charge_view
from cells.numerics import surface_field
from cells.processes.electrochemistry import F, R

KIND = "cells.physiology_protein_work_view@1"


@dataclass(frozen=True, slots=True)
class ElectricalEndpointWork:
    membrane_capacitor_energy_change_pJ: object
    capacitor_energy_change_pJ: float
    represented_material_charge_change_C: object
    requested_material_charge_change_C: object
    charge_input_roundoff_C: object
    matrix_capacitor_charge_change_C: object
    edge_matrix_charge_difference_C: object
    electrode_charge_change_C: object
    saved_electrode_charge_change_C: object
    endpoint_electrode_roundoff_C: object
    electrode_work_pJ: object
    clamp_work_pJ: float
    matrix_energy_change_pJ: float
    edge_matrix_energy_difference_pJ: float
    midpoint_material_work_pJ: float
    electrical_identity_residual_pJ: float
    field_residual_work_bound_pJ: float
    arithmetic_work_bound_pJ: float
    electrical_identity_bound_pJ: float
    gauge_work_coefficient_C: float


@dataclass(frozen=True, slots=True)
class ProteinWorkView:
    before_field: charge_view.ProteinChargeView
    after_field: charge_view.ProteinChargeView
    thermodynamics: object
    electrical: ElectricalEndpointWork
    endpoint_work: object
    admission: object

    @property
    def conditional_reversible_work_pJ(self):
        return self.endpoint_work.reversible_driving_work_pJ


class ProteinWorkViewRejected(NumericalError):
    """An uncommitted diagnostic retaining whichever endpoint trials exist."""

    def __init__(self, reason, *, stage, before, after, change, electrical, field_rejection):
        super().__init__("Protein endpoint work refused at " + stage + ": " + str(reason))
        self.stage = stage
        self.before_field, self.after_field = before, after
        self.projection_change, self.electrical = change, electrical
        self.field_rejection = field_rejection


def _sum(values):
    return math.fsum(float(value) for value in np.asarray(values).ravel())


def _electrical(layout, before, after, change):
    p = type(layout)(*(np.asarray(value) for value in layout))
    first, last = before.after, after.after
    phi0, phi1 = first.potential_V, last.potential_V
    dphi, midpoint = phi1 - phi0, 0.5 * (phi0 + phi1)
    vm0, vm1 = first.membrane_voltage_V, last.membrane_voltage_V
    dvm = vm1 - vm0
    cap_terms = np.where(
        p.membrane_active, 0.5e12 * p.membrane_capacitance * dvm * (vm0 + vm1), 0.0
    )
    capacitor = _sum(cap_terms)
    represented = after.total_charge_C - before.total_charge_C
    requested = np.zeros_like(represented)
    nc, no = len(change.cell_charge_delta_C), len(change.environment_charge_delta_C)
    n = p.active.size
    requested[:nc] = change.cell_charge_delta_C
    requested[n : n + no] = change.environment_charge_delta_C

    # The stored matrix defines frozen electrode readouts. Edge assembly is
    # retained separately because floating matrix assembly need not be exact.
    matrix_delta = p.field_capacitor_matrix @ dphi
    edge_delta = np.zeros_like(matrix_delta)
    edge_charge = np.where(p.membrane_active, p.membrane_capacitance * dvm, 0.0)
    np.add.at(edge_delta, p.membrane_cell, edge_charge)
    np.add.at(edge_delta, n + p.membrane_outside, -edge_charge)
    electrode = np.where(p.reservoir, matrix_delta[n:] - represented[n:], 0.0)
    saved_electrode = last.electrode_charge_C - first.electrode_charge_C
    work_terms = 1e12 * p.boundary_V * electrode
    clamp_work = _sum(work_terms)
    matrix_energy = 1e12 * _sum(midpoint * matrix_delta)
    material_work = 1e12 * _sum(midpoint * represented)
    assembly_energy = capacitor - matrix_energy
    identity_error = _sum([capacitor, -clamp_work, -material_work])

    # Propagate the original field charge tolerances; do not widen the field
    # gate to match a material stock-resolution bound. All nonreservoir owners,
    # including floating representatives and the gauge node, remain included.
    required = np.r_[p.active, p.outside_active & ~p.reservoir]
    scale0 = np.maximum(abs(before.total_charge_C), abs(first.capacitor_node_charge_C))
    scale1 = np.maximum(abs(after.total_charge_C), abs(last.capacitor_node_charge_C))
    charge_budget = 2 * surface_field.CHARGE_ATOL_C + surface_field.CHARGE_RTOL * (scale0 + scale1)
    closure_bound = 1e12 * _sum(np.where(required, abs(midpoint) * charge_budget, 0.0))
    magnitude = (
        _sum(abs(cap_terms))
        + _sum(abs(work_terms))
        + 1e12 * _sum(abs(midpoint) * (abs(represented) + abs(matrix_delta)))
        + 1e12
        * _sum(
            abs(midpoint)
            * (
                abs(before.total_charge_C)
                + abs(after.total_charge_C)
                + abs(first.capacitor_node_charge_C)
                + abs(last.capacitor_node_charge_C)
            )
        )
    )
    arithmetic_bound = 128 * np.finfo(np.float64).eps * magnitude
    bound = closure_bound + abs(assembly_energy) + arithmetic_bound
    data = dict(
        membrane_capacitor_energy_change_pJ=cap_terms,
        capacitor_energy_change_pJ=capacitor,
        represented_material_charge_change_C=represented,
        requested_material_charge_change_C=requested,
        charge_input_roundoff_C=represented - requested,
        matrix_capacitor_charge_change_C=matrix_delta,
        edge_matrix_charge_difference_C=edge_delta - matrix_delta,
        electrode_charge_change_C=electrode,
        saved_electrode_charge_change_C=saved_electrode,
        endpoint_electrode_roundoff_C=saved_electrode - electrode,
        electrode_work_pJ=work_terms,
        clamp_work_pJ=clamp_work,
        matrix_energy_change_pJ=matrix_energy,
        edge_matrix_energy_difference_pJ=assembly_energy,
        midpoint_material_work_pJ=material_work,
        electrical_identity_residual_pJ=identity_error,
        field_residual_work_bound_pJ=closure_bound,
        arithmetic_work_bound_pJ=arithmetic_bound,
        electrical_identity_bound_pJ=bound,
        gauge_work_coefficient_C=-_sum(electrode),
    )
    return ElectricalEndpointWork(
        **{
            key: immutable._freeze(value) if isinstance(value, np.ndarray) else value
            for key, value in data.items()
        }
    )


def evaluate(
    spec,
    checkpoint,
    binding,
    charge_reference,
    before,
    after,
    *,
    protein_species_id,
    valence,
    standard_concentration_mol_m3,
):
    """Compare two finite protein states using one unchanged charge reference.

    Both endpoints use the same actual current permeability and original
    scheduled controls. Temperature comes from the tissue specification; the
    ideal-protein standard concentration is explicit. Closed-protein work
    requires strict material conservation, not storage-resolution-only admission.
    Report ΔG_protein + ΔU_capacitor − W_clamp under fixed-ion constraints.
    This is not total protocol work or a demonstrated attainable minimum.
    """
    from cells.core import physiology_protein_thermodynamics as thermo

    stage = "admission"
    first = last = change = electrical = field_rejection = None
    try:
        initial_P = units.component_permeability(before, binding).current_m_s
        final_P = units.component_permeability(after, binding).current_m_s
        if not np.array_equal(initial_P, final_P):
            raise ValueError("Endpoint work requires identical held current permeability")
        change = projection.delta(
            before.protein, after.protein, binding, valence=valence, faraday_C_mol=F
        )
        if not change.strict_conservation_valid:
            raise ValueError("Closed-protein endpoint work requires strict material conservation")
        stage = "before_field"
        first = charge_view.evaluate(
            spec,
            checkpoint,
            binding,
            charge_reference,
            before,
            protein_species_id=protein_species_id,
            valence=valence,
        )
        stage = "after_field"
        last = charge_view.evaluate(
            spec,
            checkpoint,
            binding,
            charge_reference,
            after,
            protein_species_id=protein_species_id,
            valence=valence,
        )
        stage = "electrical_work"
        electrical = _electrical(checkpoint.layout, first, last, change)
        if any(not np.isfinite(value).all() for value in vars_from_slots(electrical)):
            raise NumericalError("Unrepresentable electrical endpoint work")
        if (
            abs(electrical.electrical_identity_residual_pJ)
            > electrical.electrical_identity_bound_pJ
        ):
            raise NumericalError("Electrical work fails original field closure and roundoff bounds")
        stage = "protein_thermodynamics"
        chemical = thermo.change(
            before.protein,
            after.protein,
            binding,
            temperature_K=spec.model.temperature_K,
            standard_concentration_mol_m3=standard_concentration_mol_m3,
            gas_constant_J_mol_K=R,
        )
        endpoint = thermo.endpoint_work(
            chemical,
            capacitor_energy_change_pJ=electrical.capacitor_energy_change_pJ,
            clamp_work_pJ=electrical.clamp_work_pJ,
        )
        admission = MappingProxyType(
            dict(
                kind=KIND,
                source_definition_sha256=binding.source_definition_sha256,
                binding_identity=binding.identity,
                numeric_time_s=checkpoint.time,
                temperature_K=spec.model.temperature_K,
                gas_constant_J_mol_K=R,
                standard_concentration_mol_m3=standard_concentration_mol_m3,
                common_charge_reference=True,
                original_anchors_preserved=True,
                strict_material_conservation=True,
                fixed_ionic_state=True,
                ionic_holding_work_accounted=False,
                ongoing_dissipation_accounted=False,
                driving_or_heat_law_inferred=False,
                coupled_trajectory=False,
                scope="conditional reversible endpoint requirement under fixed-ion constraints",
            )
        )
        return ProteinWorkView(first, last, chemical, electrical, endpoint, admission)
    except Exception as error:
        if isinstance(error, charge_view.ProteinChargeViewRejected):
            field_rejection = error
        raise ProteinWorkViewRejected(
            error,
            stage=stage,
            before=first,
            after=last,
            change=change,
            electrical=electrical,
            field_rejection=field_rejection,
        ) from error


def vars_from_slots(value):
    return (getattr(value, name) for name in value.__dataclass_fields__)
