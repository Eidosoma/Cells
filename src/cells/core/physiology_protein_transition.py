"""Post-ion protein proposals and explicitly supplied free-energy budgets.

An accepted held-protein ionic interval is the input. One qualified component
call occurs afterwards, at a declared full nominal boundary. Acceptance produces
a split-operator receipt, not a new ionic checkpoint: variable-protein global
histories and subsequent-loop composition require their own owner. No physical
driving law, calorimetric heat or achievable protocol is inferred from noise.
"""

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass, replace
from numbers import Real
from types import MappingProxyType

import numpy as np

from cells.core import physiology_perturbation_phases as phases
from cells.core import physiology_perturbation_step as component_step
from cells.core import physiology_protein_charge_interval as held
from cells.core import physiology_protein_interval_accounting as accounting
from cells.core import physiology_protein_projection as projection
from cells.core import physiology_protein_thermodynamics as thermo
from cells.core import physiology_tissue_loop as seals
from cells.core.errors import NumericalError
from cells.models import physiology_permeability_view as immutable
from cells.models import physiology_protein_charge_rhs as charged
from cells.models import physiology_protein_charge_view as charge_view
from cells.models import physiology_protein_work_view as work
from cells.processes import betse_perturbations as perturb
from cells.processes.electrochemistry import F, R

KIND = "cells.post_ion_protein_transition@1"
BUDGET_KIND = "cells.declared_protein_free_energy_budget@1"


@dataclass(frozen=True, slots=True)
class DrivingBudget:
    external_work_pJ: float
    dissipated_free_energy_pJ: float
    provenance: str


@dataclass(frozen=True, slots=True)
class ChargeEndpoint:
    after: object
    total_charge_C: object


@dataclass(frozen=True, slots=True)
class ProteinTransitionProposal:
    source: held.HeldProteinCheckpoint
    preparation: phases.PerturbationPreparation
    loop_index: int
    standard_concentration_mol_m3: float
    transition: component_step.PerturbationTransition
    before_rates: object
    after_rates: object
    thermodynamics: object
    electrical: work.ElectricalEndpointWork
    conditional_work: object
    identity: str


@dataclass(frozen=True, slots=True)
class ProteinTransitionReceipt:
    proposal: ProteinTransitionProposal
    budget: DrivingBudget
    balance_residual_pJ: float
    balance_limit_pJ: float
    identity: str
    admission: object

    @property
    def component(self):
        return self.proposal.transition.state


class ProteinTransitionRejected(NumericalError):
    """Original source plus available uncommitted component/field/budget evidence."""

    def __init__(
        self,
        reason,
        *,
        stage,
        source,
        preparation,
        transition=None,
        proposal=None,
        before_rates=None,
        after_rates=None,
        electrical=None,
        budget=None,
        balance_residual_pJ=None,
        failure=None,
    ):
        super().__init__("Post-ion protein transition refused at " + stage + ": " + str(reason))
        self.stage, self.source, self.preparation = stage, source, preparation
        self.transition, self.proposal, self.failure = transition, proposal, failure
        self.before_rates, self.after_rates = before_rates, after_rates
        self.electrical, self.budget = electrical, budget
        self.balance_residual_pJ = balance_residual_pJ
        self.trial_component = (
            transition.state if transition is not None else getattr(failure, "trial", None)
        )
        self.packet = (
            transition.packet if transition is not None else getattr(failure, "packet", None)
        )
        self.stream = (
            transition.state.stream if transition is not None else getattr(failure, "stream", None)
        )


def _record(value):
    if isinstance(value, np.ndarray):
        return dict(
            dtype=value.dtype.str,
            shape=list(value.shape),
            sha256=hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest(),
        )
    if isinstance(value, np.generic):
        return _record(value.item())
    if is_dataclass(value):
        return {field.name: _record(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {key: _record(item) for key, item in value.items()}
    if hasattr(value, "_asdict"):
        return _record(value._asdict())
    if isinstance(value, (tuple, list)):
        return [_record(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value


def proposal_record(proposal):
    if type(proposal) is not ProteinTransitionProposal:
        raise ValueError("Require an exact post-ion proposal")
    payload = dict(
        kind=KIND,
        **{
            field.name: _record(getattr(proposal, field.name))
            for field in fields(proposal)
            if field.name != "identity"
        },
    )
    return payload | dict(identity=seals._digest(payload))


def _association(spec, point, preparation, loop_index):
    context, _ = held.validate(spec, point)
    if type(preparation) is not phases.PerturbationPreparation:
        raise ValueError("Require a complete pre-ion preparation")
    phases._validate_preparation(preparation.source_state, point.binding.component, preparation)
    if seals._component_identity(point.component) != seals._component_identity(
        preparation.held_state
    ):
        raise ValueError("Ionic interval belongs to a different held component/RNG context")
    seals._index(loop_index)
    if loop_index == seals.MAX_LOOP_INDEX:
        raise ValueError("Nominal loop index cannot advance")
    dt = float(preparation.source_state.controls.dt_s)
    start, end = loop_index * dt, (loop_index + 1) * dt
    if not math.isfinite(end) or end <= start or point.seed.time != start or point.time != end:
        raise ValueError("Post-ion operation requires one complete declared nominal interval")
    context[0].exact_index(start)
    context[0].exact_index(end)
    return context


def _component_law(preparation, transition, binding):
    """Validate the prescribed packet transformation without drawing again.

    Proposal generation owns the qualified draw and successor RNG. These seals
    detect edits; they are not an authentication scheme for adversarial authors.
    """
    source, target, packet = preparation.source_state, transition.state, transition.packet
    component_step.validate_state(target, binding)
    if target.controls != source.controls or target.loop_calls != source.loop_calls + 1:
        raise ValueError("Protein transition changed controls or component call count")
    if target.time_s != float(source.time_s) + float(source.controls.dt_s):
        raise ValueError("Protein transition does not retain its full accumulated duration")
    active = perturb.dynamic_active(source.controls)
    if (packet is not None) != active:
        raise ValueError("Protein packet violates its source draw guard")
    if packet is not None:
        perturb.draw_manifest(packet, binding)
        if packet.site != "protein_flux" or packet.tick != source.stream.next_tick:
            raise ValueError("Protein packet belongs to another draw site/tick")
        provenance = json.loads(packet.provenance_json)
        if type(source.stream.rng) is perturb.NativeStream:
            expected = dict(
                rng_id=perturb.NATIVE_RNG_ID,
                before_identity=source.stream.rng.identity,
                after_identity=target.stream.rng.identity,
                numpy_version=np.__version__,
            )
            if provenance != expected:
                raise ValueError("Native packet and complete source/successor RNG differ")
        else:
            if (
                target.stream.rng != source.stream.rng
                or provenance.get("rng_id") != perturb.STABLE_RNG_ID
                or provenance.get("seed") != source.stream.rng.seed
                or provenance.get("world_id") != source.stream.world_id
                or provenance.get("tick") != source.stream.next_tick
            ):
                raise ValueError("Stable packet belongs to different owner/world coordinates")
    for name in ("stream_id", "world_id", "layout_identity"):
        if getattr(target.stream, name) != getattr(source.stream, name):
            raise ValueError("Protein transition changed random stream ownership")
    if type(target.stream.rng) is not type(source.stream.rng):
        raise ValueError("Protein transition changed its RNG engine")
    if target.stream.next_tick != source.stream.next_tick + int(active):
        raise ValueError("Protein transition has the wrong draw count")
    if not active and target.stream != source.stream:
        raise ValueError("Disabled protein update changed its RNG/cache")
    expected = perturb.protein_step(
        source.protein,
        np.zeros(len(binding.membrane_ids)) if packet is None else packet.values,
        source.controls.dynamic_level_mol_m2_s,
        source.controls.dt_s,
        binding,
        enabled=active,
        xp=np,
    ).state
    for actual, wanted in (
        (target.protein, expected),
        (target.diffusion, preparation.held_state.diffusion),
    ):
        if any(not np.array_equal(a, b) for a, b in zip(actual, wanted, strict=True)):
            raise ValueError("Protein/permeability transition differs from its prescribed packet")


def _endpoints(spec, point, after, runtime, initial_delta, implementation, standard, evidence=None):
    control = held._control(spec, point.time)
    evidence = {} if evidence is None else evidence
    change = projection.delta(
        point.component.protein,
        after.protein,
        point.binding,
        valence=point.valence,
        faraday_C_mol=F,
    )
    if not change.strict_conservation_valid:
        raise ValueError("Post-ion protein movement must conserve material strictly")
    _, _, _, final_runtime, final_delta = accounting._prepare(
        spec,
        point.state,
        point.state,
        point.layout,
        point.binding,
        point.charge_reference,
        after,
        point.protein_species_id,
        point.valence,
    )
    if any(not np.array_equal(a, b) for a, b in zip(runtime, final_runtime, strict=True)):
        raise ValueError("Post-ion protein step must retain the identical held layout/P")
    rates = tuple(
        immutable._immutable_tree(
            charged.array_readouts(
                point.state,
                control,
                runtime,
                delta,
                implementation=implementation,
                xp=np,
            )
        )
        for delta in (initial_delta, final_delta)
    )
    evidence.update(before_rates=rates[0], after_rates=rates[1])
    if any(
        not bool(rate.valid)
        or not np.isfinite(rate.field.energy_balance_pJ_s)
        or abs(float(rate.field.energy_balance_pJ_s)) > held.ENERGY_RATE_ATOL_PJ_S
        for rate in rates
    ):
        raise ValueError("Protein endpoint leaves complete charged field/rate/energy domain")
    # This same-state audit retains material/work/domain checks without applying
    # a new protein charge retrospectively to the prior ionic energy history.
    accounting.evaluate(
        spec,
        point.state,
        point.state,
        point.layout,
        point.binding,
        point.charge_reference,
        after,
        protein_species_id=point.protein_species_id,
        valence=point.valence,
        before_control=control,
        after_control=control,
    )
    first, last = (
        ChargeEndpoint(charge_view._electrostatic(rate.field), rate.actual_charge_C)
        for rate in rates
    )
    electrical = work._electrical(runtime, first, last, change)
    evidence["electrical"] = electrical
    if any(not np.isfinite(value).all() for value in work.vars_from_slots(electrical)):
        raise ValueError("Unrepresentable post-ion electrical work")
    if abs(electrical.electrical_identity_residual_pJ) > electrical.electrical_identity_bound_pJ:
        raise ValueError("Post-ion electrical identity exceeds original field/roundoff bounds")
    chemical = thermo.change(
        point.component.protein,
        after.protein,
        point.binding,
        temperature_K=spec.model.temperature_K,
        standard_concentration_mol_m3=standard,
        gas_constant_J_mol_K=R,
    )
    endpoint = thermo.endpoint_work(
        chemical,
        capacitor_energy_change_pJ=electrical.capacitor_energy_change_pJ,
        clamp_work_pJ=electrical.clamp_work_pJ,
    )
    return (*rates, chemical, electrical, endpoint)


def propose(spec, point, preparation, *, loop_index, standard_concentration_mol_m3):
    """Attempt one post-ion component call; retain its proposed RNG on refusal."""
    stage, transition = "source_association", None
    before_rates = after_rates = electrical = None
    evidence = {}
    try:
        _, implementation, runtime, delta = _association(spec, point, preparation, loop_index)
        standard = standard_concentration_mol_m3
        if (
            not isinstance(standard, Real)
            or isinstance(standard, (bool, np.bool_))
            or not math.isfinite(standard)
            or standard <= 0
        ):
            raise ValueError("Declare a finite positive protein standard concentration")
        stage = "post_ion_component"
        transition = phases.finish(preparation.source_state, point.binding.component, preparation)
        stage = "protein_endpoint_work"
        before_rates, after_rates, chemical, electrical, endpoint = _endpoints(
            spec,
            point,
            transition.state,
            runtime,
            delta,
            implementation,
            float(standard),
            evidence,
        )
        proposal = ProteinTransitionProposal(
            point,
            preparation,
            loop_index,
            float(standard),
            transition,
            before_rates,
            after_rates,
            chemical,
            electrical,
            endpoint,
            "",
        )
        return replace(proposal, identity=proposal_record(proposal)["identity"])
    except Exception as error:
        raise ProteinTransitionRejected(
            error,
            stage=stage,
            source=point,
            preparation=preparation,
            transition=transition,
            before_rates=evidence.get("before_rates", before_rates),
            after_rates=evidence.get("after_rates", after_rates),
            electrical=evidence.get("electrical", electrical),
            failure=error,
        ) from error


def accept(spec, proposal, budget):
    """Check a caller-declared work/dissipation budget without another RNG draw.

    Nonnegative dissipation is the explicit external-drive model used here,
    not a theorem about thermal stochastic trajectories. This tests energetic
    consistency of supplied declarations, not a measured or attainable law.
    """
    stage, residual = "proposal_association", None
    try:
        if type(proposal) is not ProteinTransitionProposal:
            raise ValueError("Require a complete post-ion proposal")
        if proposal.identity != proposal_record(proposal)["identity"]:
            raise ValueError("Post-ion proposal content changed")
        point, preparation = proposal.source, proposal.preparation
        _, implementation, runtime, delta = _association(
            spec, point, preparation, proposal.loop_index
        )
        _component_law(preparation, proposal.transition, point.binding.component)
        expected = _endpoints(
            spec,
            point,
            proposal.transition.state,
            runtime,
            delta,
            implementation,
            proposal.standard_concentration_mol_m3,
        )
        actual = (
            proposal.before_rates,
            proposal.after_rates,
            proposal.thermodynamics,
            proposal.electrical,
            proposal.conditional_work,
        )
        if _record(actual) != _record(expected):
            raise ValueError("Post-ion proposal differs from its actual field/chemical endpoints")
        stage = "declared_work_budget"
        if (
            type(budget) is not DrivingBudget
            or type(budget.provenance) is not str
            or not budget.provenance.strip()
        ):
            raise ValueError("Require an explicit external-work/dissipation budget and provenance")
        for value in (budget.external_work_pJ, budget.dissipated_free_energy_pJ):
            if (
                not isinstance(value, Real)
                or isinstance(value, (bool, np.bool_))
                or not math.isfinite(value)
            ):
                raise ValueError("Work and dissipation require explicit finite real values")
        if budget.dissipated_free_energy_pJ < 0:
            raise ValueError("Declared external-drive dissipation must be nonnegative")
        residual = math.fsum(
            (
                proposal.thermodynamics.total_free_energy_change_pJ,
                proposal.electrical.capacitor_energy_change_pJ,
                budget.dissipated_free_energy_pJ,
                -proposal.electrical.clamp_work_pJ,
                -budget.external_work_pJ,
            )
        )
        limit = float(accounting._limits(spec, point.state, runtime)["energy"])
        if not math.isfinite(residual) or abs(residual) > limit:
            raise ValueError("Declared protein work/dissipation fails the original energy budget")
        payload = dict(
            kind=BUDGET_KIND,
            proposal_identity=proposal.identity,
            budget=_record(budget),
            balance_residual_pJ=residual,
            balance_limit_pJ=limit,
        )
        return ProteinTransitionReceipt(
            proposal,
            budget,
            residual,
            limit,
            seals._digest(payload),
            MappingProxyType(
                dict(
                    kind=KIND,
                    ionic_state_unchanged=True,
                    original_anchors_preserved=True,
                    component_calls=1,
                    work_law_inferred=False,
                    calorimetric_heat_inferred=False,
                    full_loop_checkpoint=False,
                    automatic_retry=False,
                    scope="post-ion constrained split operator with declared external drive",
                )
            ),
        )
    except Exception as error:
        raise ProteinTransitionRejected(
            error,
            stage=stage,
            source=getattr(proposal, "source", None),
            preparation=getattr(proposal, "preparation", None),
            transition=getattr(proposal, "transition", None),
            proposal=proposal,
            before_rates=getattr(proposal, "before_rates", None),
            after_rates=getattr(proposal, "after_rates", None),
            electrical=getattr(proposal, "electrical", None),
            budget=budget,
            balance_residual_pJ=residual,
            failure=error,
        ) from error
