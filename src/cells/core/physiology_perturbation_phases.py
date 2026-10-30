"""Explicit pre-ion permeability preparation and post-ion component finish.

Preparation publishes no accepted state, samples nothing and advances no clock.
Finish validates the complete original source, then delegates exactly once to
the frozen full-dt component transition. Pure finalization is recomputed for
validation; no extra event, physical update or RNG call is introduced. Numeric
ion evolution/publication belongs to the caller. No coupled/native full-loop or
native failed-prefix parity is claimed.
"""

import hashlib
import json
import math
from dataclasses import dataclass, replace
from types import MappingProxyType

import numpy as np

from cells.core import physiology_perturbation_step as component_step
from cells.core import physiology_random_streams as streams
from cells.core.errors import NumericalError
from cells.processes import betse_perturbations as perturb

KIND = "cells.physiology_perturbation_phases@1"


def _digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _source_identity(state, binding):
    replay = perturb.replay_record(
        binding,
        state.controls,
        perturb.Replay(
            state.protein,
            state.diffusion,
            state.stream.rng,
            state.stream.next_tick,
            float(state.time_s),
        ),
    )
    return _digest(
        dict(
            replay=replay,
            stream=streams.stream_record(state.stream),
            loop_calls=state.loop_calls,
        )
    )


@dataclass(frozen=True, slots=True)
class PerturbationPreparation:
    source_state: component_step.PhysiologyPerturbationState
    held_state: component_step.PhysiologyPerturbationState
    source_identity: str
    held_identity: str
    binding_identity: str
    identity: str
    diagnostics: object


class PerturbationPhaseRejected(NumericalError):
    """Uncommitted preparation/finish, retaining source and any proposed tape."""

    def __init__(
        self,
        reason,
        *,
        source_state,
        binding,
        preparation,
        held_state,
        trial,
        packet,
        stream,
        component_rejection,
        transition,
        diagnostics,
        stage,
    ):
        super().__init__("Physiological component phase refused at " + stage + ": " + str(reason))
        self.source_state, self.binding = source_state, binding
        self.preparation, self.held_state = preparation, held_state
        self.trial, self.packet, self.stream = trial, packet, stream
        self.component_rejection, self.transition = component_rejection, transition
        self.diagnostics, self.stage = MappingProxyType(dict(diagnostics)), stage


def _payload(source_identity, held_identity, binding_identity, diagnostics):
    return dict(
        kind=KIND,
        source_identity=source_identity,
        held_identity=held_identity,
        binding_identity=binding_identity,
        diagnostics=dict(diagnostics),
    )


def prepare(state, binding):
    """Expose held diffusion D [m2/s] before caller-owned ionic work.

    The existing tissue unit adapter can map held_state to P [m/s]. This is an
    uncommitted proposal, not an accepted component checkpoint. All original
    protein/stream/controls/clock/count values stay unchanged. SIM finalizes
    base+scheduled; INIT retains current static permeability. Clock arithmetic
    is only preflighted, never advanced here. There is no static redraw.
    """
    held, source_identity = None, None
    stage, diagnostics = "prepare_input", dict(kind=KIND, automatic_retry=False)
    try:
        component_step.validate_state(state, binding)
        binding_identity = streams._binding_identity(binding)
        source_identity = _source_identity(state, binding)
        diagnostics.update(
            source_identity=source_identity,
            source_loop_label_s=float(state.time_s),
            source_loop_calls=state.loop_calls,
            source_stream_tick=state.stream.next_tick,
            physiological_dt_s=float(state.controls.dt_s),
            phase=state.controls.phase,
            solver=state.controls.solver,
            component_clock_advanced=False,
            draw_consumed=False,
            accepted_state_published=False,
            event_finalized=False,
        )
        stage = "prepare_clock_preflight"
        if state.loop_calls == component_step.MAX_LOOP_CALLS:
            raise ValueError("Component loop_calls increment would overflow uint64")
        future_time = float(state.time_s) + float(state.controls.dt_s)
        if not math.isfinite(future_time) or future_time <= state.time_s:
            raise ValueError("A full component duration cannot advance finitely")
        stage, held = "prepare_permeability", state
        if state.controls.phase == "SIM":
            with np.errstate(over="ignore", invalid="ignore"):
                held = replace(state, diffusion=perturb.finalize_scheduled(state.diffusion, xp=np))
            diagnostics["event_finalized"] = True
            component_step.validate_state(held, binding)
        held_identity = _source_identity(held, binding)
        diagnostics.update(
            dynamic_active_at_finish=perturb.dynamic_active(state.controls),
            proposed_finish_time_s=future_time,
            held_buffers_units="diffusion m2/s; tissue P requires explicit thickness mapping",
            scope="pre-ion proposal; no protein update, numeric evolution or publication",
        )
        identity = _digest(_payload(source_identity, held_identity, binding_identity, diagnostics))
        return PerturbationPreparation(
            state,
            held,
            source_identity,
            held_identity,
            binding_identity,
            identity,
            MappingProxyType(diagnostics),
        )
    except Exception as error:
        raise PerturbationPhaseRejected(
            error,
            source_state=state,
            binding=binding,
            preparation=None,
            held_state=held,
            trial=held,
            packet=None,
            stream=getattr(state, "stream", None),
            component_rejection=None,
            transition=None,
            diagnostics=diagnostics,
            stage=stage,
        ) from error


def _validate_preparation(state, binding, preparation):
    if type(preparation) is not PerturbationPreparation:
        raise ValueError("Require an exact PerturbationPreparation")
    expected = prepare(state, binding)
    component_step.validate_state(preparation.source_state, binding)
    component_step.validate_state(preparation.held_state, binding)
    actual_source = _source_identity(preparation.source_state, binding)
    actual_held = _source_identity(preparation.held_state, binding)
    if (
        preparation.source_identity != actual_source
        or preparation.held_identity != actual_held
        or preparation.binding_identity != expected.binding_identity
        or preparation.identity
        != _digest(
            _payload(
                actual_source, actual_held, preparation.binding_identity, preparation.diagnostics
            )
        )
        or preparation.identity != expected.identity
    ):
        raise ValueError("Preparation differs from the complete accepted source/held binding")
    return expected


def finish(state, binding, preparation):
    """After caller-owned ionic work, attempt one original full-dt transition.

    Pass the original accepted source state, not the held proposal. Complete
    contents (including RNG/cache, controls and clocks) must still match. The
    same source can replay an uncommitted proposal; an accepted advanced source
    cannot consume its old preparation. Caller-owned transactions commit once.
    No event/RK resampling or mutable one-shot-token state is introduced.
    """
    transition = component_rejection = packet = trial = None
    held = None
    stream = getattr(state, "stream", None)
    stage, diagnostics = "finish_association", dict(kind=KIND, automatic_retry=False)
    try:
        expected = _validate_preparation(state, binding, preparation)
        held = expected.held_state
        diagnostics.update(
            preparation_identity=expected.identity,
            preparation_source_identity=expected.source_identity,
            source_association_valid=True,
            accepted_state_published=False,
        )
        stage = "finish_component_transition"
        try:
            transition = component_step.advance(state, binding)
        except component_step.PerturbationRejected as error:
            component_rejection = error
            trial, packet, stream = error.trial, error.packet, error.stream
            raise
        trial, packet, stream = transition.state, transition.packet, transition.state.stream
        stage = "finish_held_permeability"
        if any(
            not np.array_equal(a, b)
            for a, b in zip(transition.state.diffusion, held.diffusion, strict=True)
        ):
            raise ValueError("Post-ion transition differs from the prepared held permeability")
        result_diagnostics = (
            dict(transition.diagnostics)
            | diagnostics
            | dict(
                component_calls=1,
                preion_permeability_held=True,
                finalization_recomputed_for_validation=True,
            phase_order=(
                "prepared permeability, caller ions, qualified guarded protein transition"
            ),
                native_full_loop_parity=False,
                native_failure_prefix_parity=False,
                numeric_state_evolved_by_this_module=False,
            )
        )
        return component_step.PerturbationTransition(
            transition.state, transition.packet, MappingProxyType(result_diagnostics)
        )
    except Exception as error:
        raise PerturbationPhaseRejected(
            error,
            source_state=state,
            binding=binding,
            preparation=preparation,
            held_state=held,
            trial=trial,
            packet=packet,
            stream=stream,
            component_rejection=component_rejection,
            transition=transition,
            diagnostics=diagnostics,
            stage=stage,
        ) from error
