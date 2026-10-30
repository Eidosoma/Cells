"""CPU cohorts of complete charged physiological loops with isolated commits.

The existing loop owns ionic evolution, its real post-ion sampler, deterministic
replay and cumulative decimal ledgers. Actual packets additionally pass the
complete provider/component commit contract. Only an entire accepted world is
published. Failed worlds retain their exact parents and speculative evidence.
"""

import hashlib
import struct
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass, replace
from types import MappingProxyType

import numpy as np

from cells.core import physiology_protein_loop as loop
from cells.core import physiology_protein_packet_provider as provider
from cells.core import physiology_protein_transition_commit as component_commit
from cells.core import physiology_random_streams as streams
from cells.core.errors import NumericalError
from cells.core.specs import SimulationSpec, digest
from cells.processes import betse_perturbations as perturb
from cells.processes.electrochemistry import F, R

KIND = "cells.complete_charged_protein_batch_loop@1"


def raw(value):
    """Immutable complete numeric evidence; exceptions retain their raw fields."""
    if isinstance(value, (np.ndarray, np.generic)):
        return provider._freeze(value)
    if isinstance(value, BaseException):
        return MappingProxyType(
            dict(
                type=type(value).__module__ + "." + type(value).__qualname__,
                message=str(value),
                fields=raw(vars(value)),
            )
        )
    if is_dataclass(value):
        attributes = {field.name: getattr(value, field.name) for field in fields(value)}
        if type(value) is perturb.Controls:
            # The frozen host checkpoint codec records NumPy scalar controls
            # as their exact Python scalar values. Use that same canonical
            # representation so restart replay does not invent a difference
            # between np.float64 and float. Typed array buffers stay raw.
            attributes = {
                name: item.item()
                if isinstance(item, np.generic) and type(item.item()) in (bool, int, float)
                else item
                for name, item in attributes.items()
            }
        return MappingProxyType(
            dict(
                type=type(value).__module__ + "." + type(value).__qualname__,
                fields=raw(attributes),
            )
        )
    if hasattr(value, "_asdict"):
        return MappingProxyType(
            dict(
                type=type(value).__module__ + "." + type(value).__qualname__,
                fields=raw(value._asdict()),
            )
        )
    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            raise ValueError("Journal evidence requires explicit string field names")
        return MappingProxyType({key: raw(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(raw(item) for item in value)
    if value is None or type(value) in (str, bool, int, float):
        return value
    raise ValueError("Unsupported complete-loop journal value: " + type(value).__qualname__)


def raw_record(value):
    if isinstance(value, np.ndarray):
        return dict(
            dtype=value.dtype.str,
            shape=list(value.shape),
            sha256=hashlib.sha256(value.tobytes()).hexdigest(),
        )
    if isinstance(value, Mapping):
        return {key: raw_record(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [raw_record(item) for item in value]
    if type(value) is float:
        return dict(float64_bits=struct.pack("<d", value).hex())
    return value


@dataclass(frozen=True, slots=True)
class LoopHistory:
    source: object
    target_identity: str
    proposal_identity: str
    receipt_identity: str
    budget: object
    payload: object
    identity: str


@dataclass(frozen=True, slots=True)
class ProteinBatchWorld:
    world_id: str
    spec: object
    base: object
    checkpoint: object
    history: tuple
    identity: str


@dataclass(frozen=True, slots=True)
class WorldLoopProposal:
    source: ProteinBatchWorld
    proposal: object
    failure: object
    identity: str


@dataclass(frozen=True, slots=True)
class BatchLoopProposal:
    worlds: tuple


@dataclass(frozen=True, slots=True)
class WorldLoopAttempt:
    parent: ProteinBatchWorld
    world: ProteinBatchWorld
    accepted: bool
    proposal: object
    receipt: object
    component_commit: object
    failure: object
    stage: str
    payload: object


@dataclass(frozen=True, slots=True)
class BatchLoopResult:
    worlds: tuple
    valid: object
    attempts: tuple


@dataclass(frozen=True, slots=True)
class BatchLoopRun:
    worlds: tuple
    rounds: tuple


class BatchLoopRejected(NumericalError):
    def __init__(self, reason, worlds):
        super().__init__("Complete physiological batch refused: " + str(reason))
        self.worlds = tuple(worlds)


def history_record(entry):
    if type(entry) is not LoopHistory:
        raise ValueError("Require an exact complete-loop history entry")
    payload = dict(
        kind=KIND + "/history",
        source=loop.checkpoint_record(entry.source),
        target_identity=entry.target_identity,
        proposal_identity=entry.proposal_identity,
        receipt_identity=entry.receipt_identity,
        budget=raw_record(raw(entry.budget)),
        payload=raw_record(entry.payload),
    )
    return payload | dict(identity=digest(payload))


def world_record(world):
    if type(world) is not ProteinBatchWorld:
        raise ValueError("Require an exact complete-loop world")
    payload = dict(
        kind=KIND,
        world_id=world.world_id,
        spec_sha256=world.spec.fingerprint,
        base=loop.checkpoint_record(world.base),
        checkpoint=loop.checkpoint_record(world.checkpoint),
        history=[entry.identity for entry in world.history],
    )
    return payload | dict(identity=digest(payload))


def validate_world(world, *, deep=True):
    if (
        type(world) is not ProteinBatchWorld
        or type(world.world_id) is not str
        or not world.world_id
        or type(world.spec) is not SimulationSpec
        or world.spec.execution.backend != "cpu"
        or type(world.history) is not tuple
    ):
        raise ValueError("Require a complete named CPU world and immutable history")
    if world.identity != world_record(world)["identity"]:
        raise ValueError("World source/checkpoint/history association changed")
    previous = world.base.identity
    for entry in world.history:
        if (
            entry.identity != history_record(entry)["identity"]
            or entry.source.identity != previous
            or entry.source.identity != loop.checkpoint_record(entry.source)["identity"]
        ):
            raise ValueError("Per-world history differs from its complete ordered sources")
        previous = entry.target_identity
        if deep:
            loop.validate(world.spec, entry.source)
    if previous != world.checkpoint.identity:
        raise ValueError("Per-world history does not end at its complete checkpoint")
    if deep:
        loop.validate(world.spec, world.base)
        if world.base.identity != world.checkpoint.identity:
            loop.validate(world.spec, world.checkpoint)
    return world


def initialise_world(world_id, spec, checkpoint):
    world = ProteinBatchWorld(world_id, spec, checkpoint, checkpoint, (), "")
    world = replace(world, identity=world_record(world)["identity"])
    return validate_world(world)


def _envelope(worlds):
    worlds = tuple(worlds)
    try:
        if not worlds or any(type(w) is not ProteinBatchWorld for w in worlds):
            raise ValueError("Require a nonempty sequence of complete independent worlds")
        contexts, owners, names = [], [], []
        for world in worlds:
            point, spec = world.checkpoint, world.spec
            if type(spec) is not SimulationSpec or spec.execution.backend != "cpu":
                raise ValueError(
                    "Complete batch physical evolution requires the qualified CPU path"
                )
            rng = point.component.stream.rng
            if type(rng) is perturb.NativeStream:
                engine = (perturb.NATIVE_RNG_ID, rng.numpy_version)
            elif type(rng) is perturb.StableCoordinates:
                engine = (perturb.STABLE_RNG_ID, "")
            else:
                raise ValueError("Require a frozen owned native or stable engine")
            contexts.append(
                (
                    spec.fingerprint,
                    point.origin.binding.identity,
                    float(point.component.controls.dt_s),
                    engine,
                )
            )
            names.append(world.world_id)
            owners.append((point.component.stream.stream_id, point.component.stream.world_id))
        if len(set(contexts)) != 1:
            raise ValueError(
                "A cohort requires one spec, complete binding, nominal dt and engine/version"
            )
        if len(set(names)) != len(names) or len(set(owners)) != len(owners):
            raise ValueError("World names and owned stream/world pairs must be unique")
        return worlds
    except Exception as error:
        raise BatchLoopRejected(error, worlds) from error


def proposal_record(row):
    payload = dict(
        kind=KIND + "/proposal",
        source_identity=row.source.identity,
        proposal=None if row.proposal is None else loop.proposal_record(row.proposal),
        failure=raw_record(raw(row.failure)),
    )
    return payload | dict(identity=digest(payload))


def propose_batch(worlds):
    """Attempt every complete ionic loop, then its one original post-ion draw."""
    rows = []
    for world in _envelope(worlds):
        proposal = failure = None
        try:
            validate_world(world, deep=False)
            proposal = loop.propose(world.spec, world.checkpoint)
        except Exception as error:
            failure = error
        row = WorldLoopProposal(world, proposal, failure, "")
        rows.append(replace(row, identity=proposal_record(row)["identity"]))
    return BatchLoopProposal(tuple(rows))


def _actual_provider(world, proposal):
    binding = world.checkpoint.origin.binding
    source, actual = proposal.preparation.source_state, proposal.component_transition
    loop.transition._component_law(proposal.preparation, actual, binding.component)
    encoded = provider.encode_source(source, binding)
    packet = provider.transition.SuppliedPacket(
        np.asarray(actual.packet is not None),
        np.zeros(len(binding.component.membrane_ids), np.float64)
        if actual.packet is None
        else actual.packet.values,
        np.asarray(1, np.int32),
        binding.component.kernel.membrane_tokens,
        encoded.source.stream,
        provider._stream(actual.state.stream),
    )
    packet = provider._frozen_tree(packet)
    numeric = provider._frozen_tree(
        provider.transition.propose(
            encoded.source,
            packet,
            encoded.geometry,
            **encoded.configuration,
            xp=np,
        )
    )
    target = provider.transition.ArrayComponentState(
        actual.state.protein,
        actual.state.diffusion,
        provider._stream(actual.state.stream),
        encoded.source.controls,
        np.asarray(actual.state.time_s, np.float64),
        np.asarray(actual.state.loop_calls, np.uint64),
    )
    if not component_commit._same(target, numeric.trial):
        raise ValueError("Actual complete-loop component differs from the provider's original law")
    return provider.ProvidedProteinPacket(
        source,
        binding,
        encoded,
        actual.packet,
        actual.state.stream,
        packet,
        numeric,
        MappingProxyType(
            dict(
                actual_frozen_loop_sampler=True,
                additional_draw=False,
                source_stream_identity=streams.stream_record(source.stream)["identity"],
                packet_identity=None if actual.packet is None else actual.packet.identity,
            )
        ),
    )


def _component_admission(world, proposal, budget):
    provided = _actual_provider(world, proposal)
    point, spec = world.checkpoint, world.spec
    origin, binding = point.origin, point.origin.binding
    if not proposal.intervals:
        raise ValueError("A full physical loop must retain its actual ionic intervals")
    last = proposal.intervals[-1]
    state, end = last.trial.proposed_state, last.end_s
    control = loop.held._control(spec, end)
    endpoints = []
    for component, rates in (
        (proposal.preparation.held_state, proposal.before_rates),
        (proposal.component_transition.state, proposal.after_rates),
    ):
        implementation, _, _, runtime, delta = loop.accounting._prepare(
            spec,
            state,
            state,
            point.layout,
            binding,
            origin.charge_reference,
            component,
            origin.protein_species_id,
            origin.valence,
        )
        endpoint = provider.transition.drive.endpoint_work.endpoints.endpoint_values(
            state,
            control,
            runtime,
            delta,
            implementation=implementation,
            xp=np,
        )
        for actual, expected in (
            (endpoint.potential_V, rates.field.potential_V),
            (endpoint.membrane_voltage_V, rates.field.rates.membrane_voltage_V),
            (endpoint.charged_rates_valid, rates.valid),
            (endpoint.charge_grouping_roundoff_C, rates.charge_grouping_roundoff_C),
        ):
            if not component_commit._same(np.asarray(actual), np.asarray(expected)):
                raise ValueError(
                    "Bridge field snapshot differs from the actual post-ion loop endpoint"
                )
        endpoints.append(endpoint)
    request = component_commit.CommitRequest(
        provided.parent,
        binding,
        provided,
        origin.charge_reference.protein,
        *endpoints,
        dict(
            implementation=implementation,
            valence=float(origin.valence),
            faraday_C_mol=F,
            temperature_K=spec.model.temperature_K,
            gas_constant_J_mol_K=R,
            standard_concentration_mol_m3=point.standard_concentration_mol_m3,
            external_work_pJ=np.asarray(budget.external_work_pJ, np.float64),
            dissipated_free_energy_pJ=np.asarray(budget.dissipated_free_energy_pJ, np.float64),
            budget_provenance=budget.provenance,
        ),
    )
    return component_commit.commit_batch((request,))


def attempt_payload(parent, proposal, receipt, bridge, budget, failure, stage):
    return raw(
        dict(
            world_id=parent.world_id,
            source_identity=parent.identity,
            source_checkpoint=parent.checkpoint,
            proposal=proposal,
            speculative_receipt=receipt,
            component_commit=bridge,
            budget=budget,
            failure=failure,
            stage=stage,
        )
    )


def accept_batch(worlds, proposals, budgets):
    """Atomically publish each whole world only after both complete gates pass.

    Budgets are explicitly supplied by world name. This never samples; the
    frozen complete loop replays ions and the prescribed packet. Partitions
    may select a subset of an existing proposal set, with exact named sources.
    Every refused world is its original object, including ledgers and history.
    """
    worlds = _envelope(worlds)
    if type(proposals) is not BatchLoopProposal or not isinstance(budgets, Mapping):
        raise BatchLoopRejected("Require named proposals and explicit declared budgets", worlds)
    rows = {row.source.world_id: row for row in proposals.worlds}
    if len(rows) != len(proposals.worlds) or set(budgets) - {w.world_id for w in worlds}:
        raise BatchLoopRejected("Ambiguous proposal or budget world names", worlds)
    attempts = []
    for parent in worlds:
        row = rows.get(parent.world_id)
        proposal = None if row is None else row.proposal
        receipt = bridge = failure = None
        target, stage = parent, "batch_source_association"
        budget = budgets.get(parent.world_id)
        try:
            validate_world(parent, deep=False)
            if (
                type(row) is not WorldLoopProposal
                or row.source.identity != parent.identity
                or row.identity != proposal_record(row)["identity"]
            ):
                raise ValueError("Complete loop proposal belongs to a different exact named source")
            if row.failure is not None:
                stage = "full_loop_proposal"
                raise row.failure
            stage = "declared_budget"
            if isinstance(budget, BaseException):
                raise budget
            if type(budget) is not loop.transition.DrivingBudget:
                raise ValueError("Supply this world's explicit complete-loop DrivingBudget")
            stage = "complete_loop_acceptance"
            receipt = loop.accept(parent.spec, parent.checkpoint, proposal, budget)
            stage = "actual_packet_component_commit"
            bridge = _component_admission(parent, proposal, budget)
            if not bool(bridge.valid[0]):
                raise ValueError(
                    "Complete provider/component admission refused: "
                    + str(bridge.attempts[0].error)
                )
            if loop.seals._component_identity(bridge.states[0]) != loop.seals._component_identity(
                receipt.checkpoint.component
            ):
                raise ValueError(
                    "Decoded component differs from the entire accepted loop candidate"
                )
            stage = "committed_complete_world"
            payload = attempt_payload(parent, proposal, receipt, bridge, budget, None, stage)
            entry = LoopHistory(
                parent.checkpoint,
                receipt.checkpoint.identity,
                proposal.identity,
                receipt.identity,
                budget,
                payload,
                "",
            )
            entry = replace(entry, identity=history_record(entry)["identity"])
            target = replace(
                parent, checkpoint=receipt.checkpoint, history=(*parent.history, entry), identity=""
            )
            target = replace(target, identity=world_record(target)["identity"])
        except Exception as error:
            target = parent
            failure = error
            payload = attempt_payload(parent, proposal, receipt, bridge, budget, failure, stage)
        attempts.append(
            WorldLoopAttempt(
                parent,
                target,
                target is not parent,
                proposal,
                receipt,
                bridge,
                failure,
                stage,
                payload,
            )
        )
    return BatchLoopResult(
        tuple(attempt.world for attempt in attempts),
        provider._freeze(np.asarray([attempt.accepted for attempt in attempts], np.bool_)),
        tuple(attempts),
    )


def run_batch(worlds, *, steps, budget):
    """Run explicit caller-budget loops; retire refused worlds without retry.

    budget(world, proposal) is the caller's declared drive model. No default
    work is inferred from noise. The requested count is per active world;
    original calendars and physical horizons may still refuse an attempt.
    """
    initial = _envelope(worlds)
    if type(steps) is not int or steps < 0 or not callable(budget):
        raise BatchLoopRejected(
            "Require nonnegative loop count and explicit budget callback", initial
        )
    current = {world.world_id: world for world in initial}
    active = tuple(world.world_id for world in initial)
    rounds = []
    for _ in range(steps):
        if not active:
            break
        sources = tuple(current[name] for name in active)
        proposed = propose_batch(sources)
        declarations = {}
        for row in proposed.worlds:
            if row.failure is None:
                try:
                    declarations[row.source.world_id] = budget(row.source, row.proposal)
                except Exception as error:
                    declarations[row.source.world_id] = error
        result = accept_batch(sources, proposed, declarations)
        rounds.append(result)
        for world in result.worlds:
            current[world.world_id] = world
        active = tuple(attempt.world.world_id for attempt in result.attempts if attempt.accepted)
    return BatchLoopRun(tuple(current[w.world_id] for w in initial), tuple(rounds))


def replay_world(world):
    """Explicitly recreate a world's full real tapes/ionic history from its base.

    This is an opt-in deterministic source replay, not part of restore. Every
    saved proposal, whole receipt, component bridge and checkpoint must match.
    """
    validate_world(world)
    carried = initialise_world(world.world_id, world.spec, world.base)
    for entry in world.history:
        proposed = propose_batch((carried,))
        result = accept_batch((carried,), proposed, {world.world_id: entry.budget})
        if not bool(result.valid[0]):
            raise BatchLoopRejected("Explicit full history replay refused", (world,))
        actual = result.worlds[0].history[-1]
        if history_record(actual) != history_record(entry):
            raise BatchLoopRejected(
                "Explicit full source/interval/packet/ledger replay differs", (world,)
            )
        carried = result.worlds[0]
    if world_record(carried) != world_record(world):
        raise BatchLoopRejected("Replayed whole-world endpoint differs", (world,))
    return carried
