"""Strict host publication of admitted per-world component transitions.

Real provider packets are supplied once. Complete NumPy admission is recomputed
without sampling, even when decoding a compiled selection. Every rejected world
returns its original parent object with full trial/packet evidence. Ionic state,
loop checkpoints and decimal work ledgers remain caller-owned.
"""

from dataclasses import dataclass, replace
from types import MappingProxyType

import numpy as np

from cells.core import physiology_perturbation_step as step
from cells.core import physiology_protein_packet_provider as provider
from cells.core import physiology_random_streams as streams
from cells.core import physiology_tissue_binding as units
from cells.core.errors import NumericalError
from cells.models import physiology_permeability_view as view
from cells.numerics import physiology_protein_transition_commit_arrays as arrays
from cells.processes import betse_perturbations as perturb

KIND = "cells.physiology_protein_transition_commit@1"


@dataclass(frozen=True, slots=True)
class CommitRequest:
    parent: object
    binding: object
    provided: object
    charge_reference: object
    before_endpoint: object
    after_endpoint: object
    parameters: object

    def __post_init__(self):
        for name in ("charge_reference", "before_endpoint", "after_endpoint"):
            object.__setattr__(self, name, provider._frozen_tree(getattr(self, name)))
        parameters = {
            name: provider._freeze(value) if isinstance(value, np.ndarray) else value
            for name, value in dict(self.parameters).items()
        }
        object.__setattr__(self, "parameters", MappingProxyType(parameters))


@dataclass(frozen=True, slots=True)
class CommitAttempt:
    accepted: bool
    parent: object
    state: object
    provided: object
    evaluation: object
    supplied_selection: object
    trial: object
    diagnostics: object
    error: object


@dataclass(frozen=True, slots=True)
class CommittedBatch:
    valid: object
    states: tuple
    attempts: tuple
    rng_law: str


class CommitBatchRejected(NumericalError):
    """A malformed/aliased batch publishes nothing and retains every request."""

    def __init__(self, reason, requests):
        super().__init__("Protein commit batch refused: " + str(reason))
        self.requests = requests
        self.parents = tuple(getattr(request, "parent", None) for request in requests)


def _same(first, second):
    return bool(arrays.transition._equal(first, second, xp=np))


def _batch(requests, selections):
    requests = tuple(requests)
    try:
        if not requests or any(type(r) is not CommitRequest for r in requests):
            raise ValueError("Require a nonempty sequence of exact CommitRequest records")
        laws, owners = [], []
        for r in requests:
            if type(r.parent) is not step.PhysiologyPerturbationState:
                raise ValueError("Require complete typed source parents")
            rng = r.parent.stream.rng
            if type(rng) is perturb.NativeStream:
                laws.append((perturb.NATIVE_RNG_ID, rng.numpy_version))
            elif type(rng) is perturb.StableCoordinates:
                laws.append((perturb.STABLE_RNG_ID, ""))
            else:
                raise ValueError("Require a frozen owned native or stable engine")
            owners.append((r.parent.stream.stream_id, r.parent.stream.world_id))
        if len(set(laws)) != 1:
            raise ValueError("Batch engines and native versions must be homogeneous")
        if len(set(owners)) != len(owners):
            raise ValueError("One component stream/world owner may appear only once per batch")
        selections = (None,) * len(requests) if selections is None else tuple(selections)
        if len(selections) != len(requests):
            raise ValueError("Supply exactly one complete selection per world")
        return requests, selections, laws[0][0]
    except Exception as error:
        raise CommitBatchRejected(error, requests) from error


def _associated_provider(request):
    r, supplied = request, request.provided
    units.validate_binding(r.binding)
    implementation = r.parameters.get("implementation")
    if implementation not in view.IMPLEMENTATIONS.values() or (
        implementation.MODEL_ID != r.binding.model_id
    ):
        raise ValueError("Host binding and static field model differ")
    if type(supplied) is not provider.ProvidedProteinPacket:
        raise ValueError(
            "Require an admitted real provider record; failed provider remains a trial"
        )
    units.validate_binding(supplied.binding)
    if supplied.binding.identity != r.binding.identity:
        raise ValueError("Actual packet provider belongs to another complete host binding")
    encoded = provider.encode_source(r.parent, r.binding)
    parent = provider.encode_source(supplied.parent, supplied.binding)
    if not (
        _same(encoded.source, parent.source)
        and _same(encoded.source, supplied.encoded.source)
        and _same(encoded.geometry, supplied.encoded.geometry)
        and dict(encoded.configuration) == dict(supplied.encoded.configuration)
    ):
        raise ValueError("Actual packet provider belongs to a different complete source")
    provider.phases._validate_preparation(
        r.parent, r.binding.component, supplied.encoded.preparation
    )
    stream = streams.restore_stream(
        streams.stream_record(supplied.successor_stream), r.binding.component
    )
    active = perturb.dynamic_active(r.parent.controls)
    if (supplied.packet is not None) != active:
        raise ValueError("Actual packet violates its original source guard")
    if supplied.packet is not None:
        packet = perturb.draw_manifest(supplied.packet, r.binding.component)
        first, last = r.parent.stream, stream
        if packet["site"] != "protein_flux" or packet["tick"] != first.next_tick:
            raise ValueError("Actual packet has a different source site/tick")
        if type(first.rng) is perturb.NativeStream:
            provenance = dict(
                rng_id=perturb.NATIVE_RNG_ID,
                before_identity=first.rng.identity,
                after_identity=last.rng.identity,
                numpy_version=first.rng.numpy_version,
            )
            if packet["provenance"] != provenance:
                raise ValueError("Actual native packet and complete cache/word successor differ")
        else:
            provenance = packet["provenance"]
            if any(
                provenance.get(name) != value
                for name, value in dict(
                    rng_id=perturb.STABLE_RNG_ID,
                    seed=first.rng.seed,
                    world_id=first.world_id,
                    tick=first.next_tick,
                ).items()
            ):
                raise ValueError("Actual stable packet and source coordinates differ")
    numeric_packet = arrays.transition.SuppliedPacket(
        np.asarray(active),
        np.zeros(len(r.binding.component.membrane_ids), np.float64)
        if supplied.packet is None
        else supplied.packet.values,
        np.asarray(1, np.int32),
        r.binding.component.kernel.membrane_tokens,
        encoded.source.stream,
        provider._stream(stream),
    )
    if not _same(numeric_packet, supplied.array_packet):
        raise ValueError("Actual host packet/successor differs from its numeric record")
    proposal = arrays.transition.propose(
        encoded.source, numeric_packet, encoded.geometry, **encoded.configuration, xp=np
    )
    if not _same(proposal, supplied.array_proposal) or not bool(proposal.valid):
        raise ValueError("Actual provider proposal differs from the frozen full component law")
    return encoded


def _decode(request, encoded, selection, expected):
    if type(selection) is not arrays.CommitSelection or not _same(selection, expected):
        raise ValueError("Strict decoder refuses changed dtype/shape/bits or stale admission")
    if not bool(expected.valid):
        return request.parent
    value = selection.state
    state = replace(
        request.parent,
        protein=value.protein,
        diffusion=value.diffusion,
        stream=request.provided.successor_stream,
        time_s=float(value.time_s),
        loop_calls=int(value.loop_calls),
    )
    step.validate_state(state, request.binding.component)
    decoded = arrays.transition.ArrayComponentState(
        state.protein,
        state.diffusion,
        provider._stream(state.stream),
        encoded.source.controls,
        np.asarray(state.time_s, np.float64),
        np.asarray(state.loop_calls, np.uint64),
    )
    if not _same(decoded, value):
        raise ValueError("Decoded host component loses complete numeric state or RNG bits")
    return state


def commit_batch(requests, *, selections=None):
    """Publish immutable per-world components after fresh complete admission.

    Supply real provider records; this function never samples or retries. An
    optional sequence of compiled CommitSelection records is strictly decoded
    against fresh full NumPy admission. A decoder disagreement rejects that
    world. Rejected parents retain object identity and every byte, including
    native Gaussian cache bits. Homogeneous engines and unique stream/world
    owners prevent ambiguous duplicate publication within a batch.
    """
    requests, selections, law = _batch(requests, selections)
    attempts = []
    for request, selection in zip(requests, selections, strict=True):
        evaluation = None
        trial = getattr(getattr(request.provided, "array_proposal", None), "trial", None)
        state, accepted, error = request.parent, False, None
        stage = "host_source_packet_association"
        try:
            encoded = _associated_provider(request)
            stage = "complete_transition_admission"
            evaluation = provider._frozen_tree(
                arrays.evaluate(
                    encoded.source,
                    request.provided.array_packet,
                    encoded.geometry,
                    request.charge_reference,
                    request.before_endpoint,
                    request.after_endpoint,
                    **encoded.configuration,
                    **request.parameters,
                    xp=np,
                )
            )
            trial = evaluation.selection.trial
            stage = "strict_host_decoder"
            state = _decode(
                request,
                encoded,
                evaluation.selection if selection is None else selection,
                evaluation.selection,
            )
            accepted = bool(evaluation.selection.valid)
            if not accepted:
                stage = "complete_transition_refusal"
                error = "Original complete transition admission refused"
        except Exception as failure:
            error = str(failure)
        diagnostics = MappingProxyType(
            dict(
                kind=KIND,
                stage=stage,
                accepted=accepted,
                component_only=True,
                source_parent_unchanged=True,
                draw_consumed_by_commit=False,
                ionic_state_committed=False,
                work_ledger_committed=False,
                charged_loop_checkpoint=False,
                automatic_retry=False,
            )
        )
        attempts.append(
            CommitAttempt(
                accepted,
                request.parent,
                state,
                request.provided,
                evaluation,
                selection,
                trial,
                diagnostics,
                error,
            )
        )
    return CommittedBatch(
        provider._freeze(np.asarray([a.accepted for a in attempts], np.bool_)),
        tuple(a.state for a in attempts),
        tuple(attempts),
        law,
    )
