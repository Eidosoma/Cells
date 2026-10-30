"""Read-only electrostatic response to an explicitly referenced protein charge.

Original ionic inventories and electrical anchors remain unchanged. Charge
changes enter the field solver through its explicit charge inputs. This is a
same-state field comparison, not a coupled RHS, trajectory or work ledger.
"""

from dataclasses import dataclass
from types import MappingProxyType

import numpy as np

from cells.core import physiology_random_streams as streams
from cells.core import physiology_tissue_binding as units
from cells.core.errors import NumericalError
from cells.core.runner import validate_checkpoint
from cells.core.schedule import control_values
from cells.core.specs import SimulationSpec
from cells.core.state import Checkpoint
from cells.models import physiology_permeability_view as permeability
from cells.models import surface_tissue
from cells.numerics import surface_field
from cells.processes.electrochemistry import F

KIND = "cells.physiology_protein_charge_view@1"


@dataclass(frozen=True, slots=True)
class ElectrostaticState:
    potential_V: object
    membrane_voltage_V: object
    membrane_charge_C: object
    capacitor_node_charge_C: object
    electrode_charge_C: object
    capacitor_energy_pJ: object
    charge_residual_C: object
    charge_normalized: object
    component_current_residual_A: object
    current_normalized: object


@dataclass(frozen=True, slots=True)
class ProteinChargeView:
    before: ElectrostaticState
    after: ElectrostaticState
    source_charge_C: object
    applied_delta_charge_C: object
    total_charge_C: object
    potential_change_V: object
    capacitor_energy_change_pJ: float
    projection_change: object
    admission: object


class ProteinChargeViewRejected(NumericalError):
    """Refusal with the uncommitted field trial and explicit source charges."""

    def __init__(self, reason, *, stage, before=None, trial=None, charges=None, change=None):
        super().__init__("Protein-charge field view refused at " + stage + ": " + str(reason))
        self.stage, self.before, self.projection_change = stage, before, change
        self.trial = None if trial is None else permeability._immutable_tree(trial)
        self.charges = None if charges is None else permeability._freeze(charges)


def _electrostatic(field):
    return ElectrostaticState(
        **{
            name: permeability._freeze(
                field.rates.membrane_voltage_V
                if name == "membrane_voltage_V"
                else getattr(field, name)
            )
            for name in ElectrostaticState.__dataclass_fields__
        }
    )


def _prepare(spec, checkpoint, binding, component):
    if type(spec) is not SimulationSpec or type(spec.model) not in permeability.IMPLEMENTATIONS:
        raise ValueError("Protein-charge views require the four exact ordinary tissue families")
    if type(checkpoint) is not Checkpoint:
        raise ValueError("Require an exact accepted ordinary Checkpoint")
    units.restore_binding(units.binding_record(binding), spec)
    validate_checkpoint(spec, checkpoint)
    implementation = permeability.IMPLEMENTATIONS[type(spec.model)]
    state = type(checkpoint.state)(*(np.asarray(value) for value in checkpoint.state))
    layout = type(checkpoint.layout)(*(np.asarray(value) for value in checkpoint.layout))
    table = control_values(spec, [checkpoint.time])
    held = type(table)(*(np.asarray(value[0]) for value in table))
    physical = units.component_permeability(component, binding)
    runtime = layout._replace(membrane_permeability=physical.current_m_s)
    if not implementation.domain_valid(state, runtime, runtime.active, xp=np):
        raise NumericalError("Held permeability violates the original state/route domain")
    if not implementation.control_domain_valid(state, held, runtime, runtime.active, xp=np):
        raise NumericalError("Original same-state readout fails its actual-control domain")
    inside, outside = implementation.physical_amounts(state, runtime)
    ci = np.where(runtime.active, inside / runtime.volume, 1.0)
    co = np.where(runtime.outside_active, outside / runtime.extracellular_volume, 1.0)
    charge = np.r_[runtime.initial_cell_charge_C, runtime.initial_outside_charge_C]
    charge = charge + surface_tissue.charge_increment(state, runtime, xp=np)
    junction = held.junction
    if hasattr(state, "junction_gate"):
        junction = junction * state.junction_gate
    return runtime, held, ci, co, charge, junction


def _solve(runtime, held, ci, co, charge, junction):
    size = runtime.active.size
    return surface_field.solve(
        ci,
        co,
        charge[:size],
        charge[size:],
        held.membrane,
        junction,
        runtime.boundary_V,
        surface_tissue.field_layout(runtime),
        xp=np,
    )


def _species_ids(raw):
    """Declared ionic and chemical inventory names, including nested stores."""
    result = set()
    if isinstance(raw, dict):
        for key, value in raw.items():
            if key == "species" and isinstance(value, list):
                result.update(row["id"] for row in value if isinstance(row, dict) and "id" in row)
            result.update(_species_ids(value))
    elif isinstance(raw, list):
        for value in raw:
            result.update(_species_ids(value))
    return result


def _admission(checkpoint, binding, held, reference, current, protein_species_id, valence):
    return MappingProxyType(
        dict(
            kind=KIND,
            source_definition_sha256=binding.source_definition_sha256,
            binding_identity=binding.identity,
            numeric_time_s=checkpoint.time,
            numeric_step_index=checkpoint.step_index,
            numeric_event_index=checkpoint.event_index,
            held_control=permeability._immutable_tree(held),
            protein_species_id=protein_species_id,
            protein_valence=valence,
            faraday_C_mol=F,
            reference_component_time_s=reference.time_s,
            current_component_time_s=current.time_s,
            reference_component_loop_calls=reference.loop_calls,
            current_component_loop_calls=current.loop_calls,
            reference_stream_identity=streams.stream_record(reference.stream)["identity"],
            current_stream_identity=streams.stream_record(current.stream)["identity"],
            original_anchors_preserved=True,
            ionic_inventories_preserved=True,
            current_permeability_held=True,
            protein_charge_is_an_explicit_increment=True,
            coupled_rhs=False,
            coupled_trajectory=False,
            protein_transfer_work_accounted=False,
            scope="same-state electrostatic response at the original scheduled control",
        )
    )


def evaluate(spec, checkpoint, binding, reference, current, *, protein_species_id, valence):
    """Compare fields with and without a declared protein charge increment.

    ``reference`` explicitly identifies the protein state already represented
    by the unmodified electrical baseline. No baseline is inferred from clocks
    or numeric ionic stocks. ``current`` supplies held permeability and protein.
    The named protein must be absent from existing ionic/chemical inventories.
    Both fields use the same ions, geometry, controls and permeability; only
    the explicit charge inputs differ. No noise, material transfer, integration
    or checkpoint publication occurs, and capacitor energy change is not an
    accounting of the work needed to move protein.
    """
    from cells.core import physiology_protein_projection as projection

    stage, before, trial, charge, change = "admission", None, None, None, None
    try:
        if type(protein_species_id) is not str or not protein_species_id.strip():
            raise ValueError("Declare the separate protein species identity")
        if type(spec) is not SimulationSpec:
            raise ValueError("Require an exact original SimulationSpec")
        occupied = _species_ids(spec.to_dict()["model"])
        if type(spec.model) is permeability.fuel_spec.SurfaceCalciumEnergyHCNExtraModel:
            occupied.update(("ATP", "ADP", "Pi"))
        if protein_species_id in occupied:
            raise ValueError("Protein already belongs to a declared ionic/chemical inventory")
        units.restore_binding(units.binding_record(binding), spec)
        units.component_permeability(reference, binding)
        runtime, held, ci, co, charge, junction = _prepare(spec, checkpoint, binding, current)
        stage = "protein_projection"
        change = projection.delta(
            reference.protein, current.protein, binding, valence=valence, faraday_C_mol=F
        )
        if not change.conservation_valid:
            raise ValueError("Protein change requires a declared external material/charge source")
        delta = np.zeros_like(charge)
        n = runtime.active.size
        cell = np.asarray(change.cell_charge_delta_C)
        outside = np.asarray(change.environment_charge_delta_C)
        if cell.shape != (len(binding.tissue_cell_ids),) or outside.shape != (
            len(binding.tissue_environment_ids),
        ):
            raise ValueError("Projection charge axes disagree with actual tissue owners")
        delta[: len(cell)] = cell
        delta[n : n + len(outside)] = outside
        total = charge + delta
        if not np.isfinite(total).all():
            raise ValueError("Unrepresentable combined ionic/protein charge")
        stage = "original_field"
        trial = _solve(runtime, held, ci, co, charge, junction)
        if not trial.converged:
            raise NumericalError("Original field does not satisfy charge/current closure")
        before = _electrostatic(trial)
        source_charge = charge
        stage, charge = "protein_field", total
        trial = _solve(runtime, held, ci, co, total, junction)
        if not trial.converged:
            raise NumericalError("Protein charge does not satisfy original field closure")
        after = _electrostatic(trial)
        return ProteinChargeView(
            before,
            after,
            permeability._freeze(source_charge),
            permeability._freeze(delta),
            permeability._freeze(total),
            permeability._freeze(after.potential_V - before.potential_V),
            float(after.capacitor_energy_pJ - before.capacitor_energy_pJ),
            change,
            _admission(checkpoint, binding, held, reference, current, protein_species_id, valence),
        )
    except Exception as error:
        raise ProteinChargeViewRejected(
            error, stage=stage, before=before, trial=trial, charges=charge, change=change
        ) from error
