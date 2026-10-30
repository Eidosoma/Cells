"""Native blocker memory and complete charged loops in one atomic checkpoint.

The frozen loop owns actual ionic/RK/gate evolution, post-ion protein draws and
local/global decimal work/electrode admission. An explicit private control scope
adds qualified block setters before permeability/ions. Refusals retain the exact
outer parent and all speculative states, packets, controls and ledgers.
"""

import math
from dataclasses import dataclass, replace
from types import MappingProxyType

import numpy as np

from cells.core import physiology_protein_batch_loop as journal
from cells.core import physiology_protein_block_calendar_scope as scoped
from cells.core import physiology_protein_loop as loop
from cells.core import physiology_protein_packet_provider as provider
from cells.core.errors import NumericalError
from cells.core.grid import EventGrid
from cells.models import physiology_block_control_view as blocks
from cells.numerics import surface_field as field

KIND = "cells.complete_charged_protein_block_calendar@1"


@dataclass(frozen=True, slots=True)
class ProteinBlockCheckpoint:
    point: object
    binding: object
    initial_block_state: object
    block_state: object
    calendar: object
    origin_call_index: int
    call_index: int
    identity: str


@dataclass(frozen=True, slots=True)
class ProteinBlockProposal:
    source_identity: str
    preparation: object
    actuation: object
    charged_proposal: object
    interval_controls: tuple
    identity: str


@dataclass(frozen=True, slots=True)
class ProteinBlockReceipt:
    checkpoint: ProteinBlockCheckpoint
    proposal: ProteinBlockProposal
    charged_receipt: object
    identity: str


def _failed_value(failure, name):
    """Keep the first actual payload through existing nested refusal wrappers."""
    seen = set()
    while failure is not None and id(failure) not in seen:
        seen.add(id(failure))
        value = getattr(failure, name, None)
        if value is not None:
            return value
        failure = getattr(failure, "failure", None)
    return None


class ProteinBlockRejected(NumericalError):
    def __init__(
        self,
        reason,
        *,
        source,
        stage,
        preparation=None,
        proposal=None,
        charged_proposal=None,
        charged_receipt=None,
        actuation=None,
        failure=None,
    ):
        super().__init__("Complete charged blocker call refused at " + stage + ": " + str(reason))
        self.source, self.stage, self.preparation = source, stage, preparation
        self.proposal, self.charged_proposal = proposal, charged_proposal
        self.charged_receipt, self.actuation, self.failure = charged_receipt, actuation, failure
        self.intervals = tuple(
            getattr(charged_proposal, "intervals", getattr(failure, "intervals", ()))
        )
        component = getattr(charged_proposal, "component_transition", None)
        self.packet = (
            component.packet if component is not None else getattr(failure, "packet", None)
        )
        self.stream = (
            component.state.stream if component is not None else getattr(failure, "stream", None)
        )
        self.trial = _failed_value(failure, "trial")


def record(checkpoint):
    if type(checkpoint) is not ProteinBlockCheckpoint:
        raise ValueError("Require the complete charged/block/calendar checkpoint")
    payload = dict(
        kind=KIND,
        control_policy=scoped.POLICY,
        frozen_sources=scoped.PINS,
        charged_checkpoint=loop.checkpoint_record(checkpoint.point),
        block_binding=blocks.record(checkpoint.binding),
        initial_block_state=journal.raw_record(journal.raw(checkpoint.initial_block_state)),
        block_state=journal.raw_record(journal.raw(checkpoint.block_state)),
        calendar=scoped.clocks.record(checkpoint.calendar),
        origin_call_index=checkpoint.origin_call_index,
        call_index=checkpoint.call_index,
    )
    return payload | dict(identity=loop.seals._digest(payload))


def _seal(checkpoint):
    return replace(checkpoint, identity=record(checkpoint)["identity"])


def scope(spec, checkpoint):
    return scoped.ControlScope(
        spec,
        checkpoint.point.origin.binding,
        checkpoint.binding,
        checkpoint.initial_block_state,
        checkpoint.calendar,
        checkpoint.origin_call_index,
    )


def validate(spec, checkpoint):
    if (
        type(checkpoint) is not ProteinBlockCheckpoint
        or checkpoint.identity != record(checkpoint)["identity"]
    ):
        raise ValueError("Changed complete blocker/charged source association")
    point, calendar = checkpoint.point, scoped.clocks.validate(checkpoint.calendar)
    if (
        calendar.step_count == 0
        or type(checkpoint.call_index) is not int
        or not checkpoint.origin_call_index <= checkpoint.call_index <= calendar.step_count
        or point.origin_loop_index != checkpoint.origin_call_index
        or point.loop_index != checkpoint.call_index
        or point.time != checkpoint.call_index * calendar.dt_s
        or point.initial_component.controls.phase != calendar.phase
        or point.initial_component.controls.dt_s != calendar.dt_s
    ):
        raise ValueError("Charged state and original native calendar/cursor differ")
    EventGrid(spec).exact_index(calendar.step_count * calendar.dt_s)
    if point.schedule is not None and point.schedule.native_calendar is not None:
        if point.schedule.native_calendar.identity != calendar.identity:
            raise ValueError("Permeability and blocker native calendars must be identical")
    context = scope(spec, checkpoint)
    if not bool(
        provider.transition._equal(
            checkpoint.block_state, context.memory_at(checkpoint.call_index), xp=np
        )
    ):
        raise ValueError("Carried blocker memory differs from original ordered source calls")
    context.validation.validate(spec, point)
    return context


def bind(spec, point, binding, block_state, calendar):
    """Associate an original qualified charged origin with explicit block memory.

    The caller's existing initializer supplies the complete charged origin.
    Evolved bare checkpoints cannot invent an unrecorded blocker history.
    """
    loop.validate(spec, point)
    if point.loop_index != point.origin_loop_index:
        raise ValueError(
            "Bind blockers at the declared original charged boundary; restart evolved calls"
        )
    block_state = provider._frozen_tree(blocks._state(block_state, binding))
    checkpoint = _seal(
        ProteinBlockCheckpoint(
            point,
            binding,
            block_state,
            block_state,
            calendar,
            point.origin_loop_index,
            point.loop_index,
            "",
        )
    )
    validate(spec, checkpoint)
    return checkpoint


def proposal_record(proposal):
    if type(proposal) is not ProteinBlockProposal:
        raise ValueError("Require the complete controlled charged-loop proposal")
    payload = dict(
        kind=KIND + "/proposal",
        source_identity=proposal.source_identity,
        preparation=journal.raw_record(journal.raw(proposal.preparation)),
        actuation=journal.raw_record(journal.raw(proposal.actuation)),
        charged_proposal=loop.proposal_record(proposal.charged_proposal),
        interval_controls=journal.raw_record(journal.raw(proposal.interval_controls)),
    )
    return payload | dict(identity=loop.seals._digest(payload))


def _actuation(spec, checkpoint, context, preparation):
    point = checkpoint.point
    runtime, before, _ = context._fixed_actual(
        checkpoint.block_state, spec, point, point.state, point.component, point.time
    )
    _, after, _ = context._fixed_actual(
        preparation.block_state, spec, point, point.state, point.component, point.time
    )
    v0, v1 = before.field.rates.membrane_voltage_V, after.field.rates.membrane_voltage_V
    delta = math.fsum(
        float(value) for value in 5e11 * runtime.membrane_capacitance * (v1 - v0) * (v1 + v0)
    )
    charge = after.field.electrode_charge_C - before.field.electrode_charge_C
    qlimit = 2 * field.CHARGE_ATOL_C + field.CHARGE_RTOL * (
        abs(before.actual_charge_C[runtime.active.size :])
        + abs(after.actual_charge_C[runtime.active.size :])
    )
    limit = loop.accounting._limits(spec, point.state, runtime)["energy"]
    report = provider._frozen_tree(
        dict(
            capacitor_energy_change_pJ=np.asarray(delta),
            physical_energy_limit_pJ=np.asarray(limit),
            electrode_charge_change_C=charge,
            electrode_charge_limit_C=qlimit,
            checks=dict(
                stored_energy=np.asarray(abs(delta) <= limit),
                electrode_charge=np.asarray(np.all(abs(charge) <= qlimit)),
            ),
        )
    )
    if not all(bool(value) for value in report["checks"].values()):
        error = ValueError(
            "Blocker actuation changes stored electrical state without a supplied law"
        )
        error.report = report
        raise error
    return report


def propose(spec, checkpoint):
    preparation = charged = actuation = None
    stage = "accepted_source"
    try:
        context = validate(spec, checkpoint)
        stage = "native_block_preparation"
        controlled, preparation = context.proposal_loop(checkpoint.call_index)
        stage = "blocker_actuation"
        actuation = _actuation(spec, checkpoint, context, preparation)
        stage = "complete_charged_loop"
        charged = controlled.propose(spec, checkpoint.point)
        proposal = ProteinBlockProposal(
            checkpoint.identity,
            preparation,
            actuation,
            charged,
            context.controls(charged, preparation.block_state),
            "",
        )
        return replace(proposal, identity=proposal_record(proposal)["identity"])
    except Exception as error:
        raise ProteinBlockRejected(
            error,
            source=checkpoint,
            stage=stage,
            preparation=preparation,
            charged_proposal=charged,
            actuation=actuation if actuation is not None else getattr(error, "report", None),
            failure=error,
        ) from error


def accept(spec, checkpoint, proposal, budget):
    """Replay/admit the whole controlled call, preserving source on every refusal."""
    preparation = charged_receipt = actuation = None
    stage = "complete_proposal_association"
    try:
        context = validate(spec, checkpoint)
        if (
            type(proposal) is not ProteinBlockProposal
            or proposal.source_identity != checkpoint.identity
            or proposal.identity != proposal_record(proposal)["identity"]
        ):
            raise ValueError("Controlled proposal belongs to another exact complete source")
        controlled, preparation = context.proposal_loop(checkpoint.call_index)
        actuation = _actuation(spec, checkpoint, context, preparation)
        expected = (
            preparation,
            actuation,
            context.controls(proposal.charged_proposal, preparation.block_state),
        )
        actual = (proposal.preparation, proposal.actuation, proposal.interval_controls)
        if journal.raw_record(journal.raw(actual)) != journal.raw_record(journal.raw(expected)):
            raise ValueError("Actual setter memory/control/actuation source association changed")
        stage = "complete_ionic_protein_and_cumulative_acceptance"
        charged_receipt = controlled.accept(
            spec, checkpoint.point, proposal.charged_proposal, budget
        )
        candidate = _seal(
            replace(
                checkpoint,
                point=charged_receipt.checkpoint,
                block_state=preparation.block_state,
                call_index=checkpoint.call_index + 1,
                identity="",
            )
        )
        stage = "complete_checkpoint"
        validate(spec, candidate)
        payload = dict(
            kind=KIND + "/receipt",
            checkpoint=candidate.identity,
            proposal=proposal.identity,
            charged_receipt=charged_receipt.identity,
        )
        return ProteinBlockReceipt(
            candidate, proposal, charged_receipt, loop.seals._digest(payload)
        )
    except Exception as error:
        raise ProteinBlockRejected(
            error,
            source=checkpoint,
            stage=stage,
            preparation=preparation,
            proposal=proposal,
            charged_proposal=getattr(proposal, "charged_proposal", None),
            charged_receipt=charged_receipt,
            actuation=actuation,
            failure=error,
        ) from error


def admission(receipt):
    """Explicit clocks/order for a fully accepted call; no inferred drive/heat."""
    p, c = receipt.proposal, receipt.checkpoint
    return MappingProxyType(
        dict(
            calendar_identity=c.calendar.identity,
            call_index=c.call_index - 1,
            event_label_s=p.preparation.event_time_s,
            phase=c.calendar.phase,
            physical_start_s=p.charged_proposal.intervals[0].start_s,
            physical_end_s=c.point.time,
            declared_duration_s=c.calendar.dt_s,
            physical_subintervals=len(p.charged_proposal.intervals),
            source_order=(
                "block setters",
                "permeability",
                "charged ions",
                "protein",
                "local/global ledgers",
            ),
            original_anchors_preserved=True,
            complete_atomic_call=True,
            temperature_or_voltage_transition=False,
            work_or_heat_law_inferred=False,
        )
    )
