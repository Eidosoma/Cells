"""Pure cell-removal remap of the complete perturbation component.

Reuse the existing cut ownership/quantity contract and explicit stream rebind.
Environment and ion sets remain complete; surviving membrane areas and cell/
environment volumes cannot change. Removed protein is an explicit sink, never
an exterior release. Membrane concentration views are archived, not counted as
another material inventory. No geometry generation, sampling or loop runs.
"""

import math
from dataclasses import dataclass, replace
from types import MappingProxyType

import numpy as np

from cells.core import physiology_perturbation_step as step
from cells.core import physiology_random_streams as streams
from cells.processes import betse_perturbations as perturb
from cells.processes import betse_tissue_cut as cut

KIND = "cells.physiology_perturbation_remap@1"


def _freeze(value):
    value = np.array(value, dtype=np.float64, copy=True, order="C")
    return np.frombuffer(value.tobytes(), dtype=np.float64).reshape(value.shape)


def _sum(values):
    try:
        result = math.fsum(values)
    except (OverflowError, ValueError) as error:
        raise ValueError("Protein amount/total is not representable") from error
    if not math.isfinite(result):
        raise ValueError("Protein amount/total is not representable")
    return result


@dataclass(frozen=True, slots=True)
class PerturbationRemovalArchive:
    cell_ids: tuple
    membrane_ids: tuple
    environment_ids: tuple
    ion_ids: tuple
    protein: perturb.ProteinState
    diffusion: perturb.StaticState
    cell_volume_m3: object
    membrane_area_m2: object
    environment_effective_volume_m3: object
    cell_amount_mol: object
    environment_amount_mol: object

    def __post_init__(self):
        object.__setattr__(
            self, "protein", perturb.ProteinState(*(_freeze(v) for v in self.protein))
        )
        object.__setattr__(
            self, "diffusion", perturb.StaticState(*(_freeze(v) for v in self.diffusion))
        )
        for name in (
            "cell_volume_m3",
            "membrane_area_m2",
            "environment_effective_volume_m3",
            "cell_amount_mol",
            "environment_amount_mol",
        ):
            object.__setattr__(self, name, _freeze(getattr(self, name)))

    @property
    def total_amount_mol(self):
        return _sum((*self.cell_amount_mol, *self.environment_amount_mol))


@dataclass(frozen=True, slots=True)
class PerturbationRemapResult:
    state: step.PhysiologyPerturbationState
    archive: PerturbationRemovalArchive
    diagnostics: object


def _indices(before, after):
    return np.asarray([before.index(name) for name in after], dtype=np.int64)


def _topology(binding):
    return cut.Topology(
        binding.cell_ids,
        binding.membrane_ids,
        (),
        binding.environment_ids,
        binding.kernel.owner,
        binding.kernel.environment_owner,
        np.empty((0, 2), dtype=np.int64),
        np.empty((0, 2), dtype=np.int64),
        np.empty(0, dtype=bool),
    )


def _unchanged_geometry(old_binding, new_binding, indices):
    if old_binding.environment_mode != new_binding.environment_mode:
        raise ValueError("Remap cannot change the declared environment mode")
    for field, domain in (
        ("cell_volume_m3", "cell"),
        ("membrane_area_m2", "membrane"),
        ("environment_effective_volume_m3", "environment"),
    ):
        old = np.asarray(getattr(old_binding.kernel, field))[indices[domain]]
        new = np.asarray(getattr(new_binding.kernel, field))
        if old.dtype != new.dtype or not np.array_equal(old, new):
            raise ValueError("Remap changed surviving geometry/volume/precision: " + field)


def _fields(state, binding):
    fields = dict(
        cell_protein=cut.OwnedField(
            state.protein.cell_mol_m3,
            "cell",
            kind="density",
            units="mol/m3",
            measure=binding.kernel.cell_volume_m3,
            quantity_units="mol",
            nonnegative=True,
        ),
        membrane_protein_view=cut.OwnedField(
            state.protein.membrane_mol_m3,
            "membrane",
            kind="state",
            units="mol/m3",
            nonnegative=True,
        ),
        environment_protein=cut.OwnedField(
            state.protein.environment_mol_m3,
            "environment",
            kind="density",
            units="mol/m3",
            measure=binding.kernel.environment_effective_volume_m3,
            quantity_units="mol",
            nonnegative=True,
        ),
    )
    for name, values in state.diffusion._asdict().items():
        fields[name] = cut.OwnedField(
            values,
            "membrane",
            axis=1,
            kind="state",
            units="m2/s",
            nonnegative=name != "scheduled_m2_s",
        )
    return fields


def remap_component(state, old_binding, new_binding):
    """Return explicit surviving state, immutable removed archive and ledger.

    Only named cell removal plus coordinate reordering is supported. All
    membranes of each surviving cell and all environment/ion owners must remain.
    Terminal zero-cell state, new wound owners, ion loss, bath mixing and volume
    rescaling are unsupported. A mixed-bath cut that changes its effective
    volume is refused. Caller-owned numerical geometry/fields are not remapped.
    """
    step.validate_state(state, old_binding)
    if type(new_binding) is perturb.Binding and not new_binding.cell_ids:
        raise ValueError("Terminal removal needs a separate archive; no empty perturbation binding")
    rebound = streams.rebind_stream(state.stream, old_binding, new_binding)
    for field in ("environment_ids", "ion_ids"):
        if set(getattr(old_binding, field)) != set(getattr(new_binding, field)):
            raise ValueError("Remap requires the full surviving environment and ion sets: " + field)
    indices = {
        domain: _indices(
            getattr(old_binding, domain + "_ids"), getattr(new_binding, domain + "_ids")
        )
        for domain in ("cell", "membrane", "environment", "ion")
    }
    _unchanged_geometry(old_binding, new_binding, indices)
    removed_cells = tuple(name for name in old_binding.cell_ids if name not in new_binding.cell_ids)
    result = cut.apply_cut(_topology(old_binding), removed_cells, _fields(state, old_binding))
    if set(result.plan.after.membrane_ids) != set(new_binding.membrane_ids):
        raise ValueError("Remap must retain every membrane of each surviving cell")
    protein = perturb.ProteinState(
        state.protein.cell_mol_m3[indices["cell"]],
        state.protein.membrane_mol_m3[indices["membrane"]],
        state.protein.environment_mol_m3[indices["environment"]],
    )
    diffusion = perturb.StaticState(
        *(value[np.ix_(indices["ion"], indices["membrane"])] for value in state.diffusion)
    )
    proposed = (
        state
        if old_binding.identity == new_binding.identity
        else replace(state, protein=protein, diffusion=diffusion, stream=rebound)
    )
    step.validate_state(proposed, new_binding)
    removed = result.plan.removed
    archive = PerturbationRemovalArchive(
        result.removed_owner_ids["cell"],
        result.removed_owner_ids["membrane"],
        result.removed_owner_ids["environment"],
        old_binding.ion_ids,
        perturb.ProteinState(
            result.fields["cell_protein"].removed_values,
            result.fields["membrane_protein_view"].removed_values,
            result.fields["environment_protein"].removed_values,
        ),
        perturb.StaticState(
            *(result.fields[name].removed_values for name in perturb.StaticState._fields)
        ),
        old_binding.kernel.cell_volume_m3[removed["cell"]],
        old_binding.kernel.membrane_area_m2[removed["membrane"]],
        old_binding.kernel.environment_effective_volume_m3[removed["environment"]],
        result.fields["cell_protein"].removed_quantity,
        result.fields["environment_protein"].removed_quantity,
    )
    before_cell = state.protein.cell_mol_m3 * old_binding.kernel.cell_volume_m3
    before_env = (
        state.protein.environment_mol_m3 * old_binding.kernel.environment_effective_volume_m3
    )
    retained_cell = proposed.protein.cell_mol_m3 * new_binding.kernel.cell_volume_m3
    retained_env = (
        proposed.protein.environment_mol_m3 * new_binding.kernel.environment_effective_volume_m3
    )
    residual = _sum(
        (
            *before_cell,
            *before_env,
            *(-retained_cell),
            *(-retained_env),
            *(-archive.cell_amount_mol),
            *(-archive.environment_amount_mol),
        )
    )
    if residual != 0.0:
        raise ValueError("Protein owner partition changed material beyond pure removal")
    before_record, after_record = (
        streams.stream_record(state.stream),
        streams.stream_record(proposed.stream),
    )
    diagnostics = dict(
        kind=KIND,
        cut_law_id=cut.LAW_ID,
        before_layout_identity=old_binding.identity,
        after_layout_identity=new_binding.identity,
        before_stream_identity=before_record["identity"],
        after_stream_identity=after_record["identity"],
        stream_id=state.stream.stream_id,
        world_id=state.stream.world_id,
        next_tick=state.stream.next_tick,
        time_s=float(state.time_s),
        loop_calls=state.loop_calls,
        cell_new_to_old=tuple(int(v) for v in indices["cell"]),
        membrane_new_to_old=tuple(int(v) for v in indices["membrane"]),
        environment_new_to_old=tuple(int(v) for v in indices["environment"]),
        ion_new_to_old=tuple(int(v) for v in indices["ion"]),
        removed_cell_ids=archive.cell_ids,
        removed_membrane_ids=archive.membrane_ids,
        previous_amount_mol=_sum((*before_cell, *before_env)),
        retained_amount_mol=_sum((*retained_cell, *retained_env)),
        removed_amount_mol=archive.total_amount_mol,
        partition_residual_mol=residual,
        membrane_views_are_material=False,
        draws_consumed=0,
        physical_policy="removed owned protein is an explicit sink; no exterior release",
        continuation_policy="native sequential tape and stable coordinates remain distinct laws",
        scope=(
            "component-only cell removal; "
            "numerical geometry/fields and full physiology are external"
        ),
    )
    return PerturbationRemapResult(proposed, archive, MappingProxyType(diagnostics))
