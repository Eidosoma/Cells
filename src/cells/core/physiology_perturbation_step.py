"""Atomic host perturbation-component transitions over the qualified RNG laws.

This is one explicit source-style loop call, never an RK stage or a complete
BETSE physiology loop. Callers stage scheduled permeability modifiers; only
their SIM finalization and the frozen protein component are composed here.
Downstream bulk refresh/clipping, tissue mapping and other RNG sites remain
separate. Rejected trials retain their draw and proposed RNG without commit.
"""

import math
from dataclasses import dataclass, replace
from numbers import Real
from types import MappingProxyType

import numpy as np

from cells.core import physiology_random_streams as streams
from cells.core.errors import NumericalError
from cells.processes import betse_perturbations as perturb

MAX_LOOP_CALLS = 2**64 - 1
BALANCE_RELATIVE_TOLERANCE = 3e-13


def _freeze(value):
    # An immutable bytes owner also prevents callers from re-enabling writes.
    value = np.asarray(value)
    if value.dtype.kind not in "fiu":
        raise ValueError("Require explicit real numeric component buffers")
    shape = value.shape
    value = np.ascontiguousarray(value, dtype=np.float64)
    return np.frombuffer(value.tobytes(), dtype=np.float64).reshape(shape)


@dataclass(frozen=True, slots=True)
class PhysiologyPerturbationState:
    protein: perturb.ProteinState
    diffusion: perturb.StaticState
    stream: streams.PhysiologyRandomStream
    controls: perturb.Controls
    time_s: float
    loop_calls: int

    def __post_init__(self):
        if (
            type(self.protein) is not perturb.ProteinState
            or type(self.diffusion) is not perturb.StaticState
        ):
            raise ValueError("Require complete typed protein and permeability buffers")
        if (
            type(self.controls) is not perturb.Controls
            or type(self.stream) is not streams.PhysiologyRandomStream
        ):
            raise ValueError("Require explicit component controls and stream ownership")
        object.__setattr__(
            self, "protein", perturb.ProteinState(*(_freeze(value) for value in self.protein))
        )
        object.__setattr__(
            self, "diffusion", perturb.StaticState(*(_freeze(value) for value in self.diffusion))
        )


@dataclass(frozen=True, slots=True)
class PerturbationTransition:
    state: PhysiologyPerturbationState
    packet: object
    diagnostics: object


class PerturbationRejected(NumericalError):
    """An uncommitted attempt; trial/cache/tape evidence remains available."""

    def __init__(self, reason, *, trial, packet, stream, diagnostics, stage):
        super().__init__("Physiological component refused at " + stage + ": " + str(reason))
        self.trial, self.packet, self.stream = trial, packet, stream
        self.diagnostics = MappingProxyType(dict(diagnostics))
        self.stage = stage


def validate_state(state, binding):
    """Return the validated original state, without sampling or mutation.

    Physical protein/current/base buffers are finite and nonnegative. Signed
    scheduled modifiers are allowed; their resulting current buffer is checked
    when a SIM call finalizes them. Elapsed component time is independent of
    the paired deterministic checkpoint clock and logical draw counter.
    """
    if type(state) is not PhysiologyPerturbationState:
        raise ValueError("Require a complete physiological component state")
    perturb.validate_controls(state.controls)
    streams.restore_stream(streams.stream_record(state.stream), binding)
    if (
        not isinstance(state.time_s, Real)
        or isinstance(state.time_s, (bool, np.bool_))
        or not math.isfinite(state.time_s)
        or state.time_s < 0
    ):
        raise ValueError("Require finite nonnegative accumulated component time")
    if type(state.loop_calls) is not int or not 0 <= state.loop_calls <= MAX_LOOP_CALLS:
        raise ValueError("Require uint64 component loop_calls")
    for value, ids in zip(
        state.protein,
        (binding.cell_ids, binding.membrane_ids, binding.environment_ids),
        strict=True,
    ):
        if value.shape != (len(ids),) or not np.isfinite(value).all() or np.any(value < 0):
            raise ValueError("Protein buffers require finite nonnegative explicit owner axes")
    expected = (len(binding.ion_ids), len(binding.membrane_ids))
    for name, value in state.diffusion._asdict().items():
        if (
            value.shape != expected
            or not np.isfinite(value).all()
            or name != "scheduled_m2_s"
            and np.any(value < 0)
        ):
            raise ValueError("Invalid physical permeability or scheduled-buffer domain")
    return state


def _finite(value):
    value = float(value)
    return value if math.isfinite(value) else None


def _diagnostics(state):
    return dict(
        phase=state.controls.phase,
        solver=state.controls.solver,
        source_loop_label_s=float(state.time_s),
        dt_s=state.controls.dt_s,
        loop_calls_before=state.loop_calls,
        stream_tick_before=state.stream.next_tick,
        event_finalized=False,
        dynamic_active=False,
        draw_consumed=False,
        balance_relative_tolerance=BALANCE_RELATIVE_TOLERANCE,
        scope="explicit perturbation-component call; no downstream bulk refresh or clipping",
    )


def initialise(binding, controls, protein, diffusion_m2_s, stream):
    """Draw static_K once in every phase/solver, keeping the pre-noise base.

    No physical loop has elapsed: time_s and loop_calls start at zero. Source
    zero level still consumes its static draw. All caller buffers remain owned
    by the caller; accepted and rejected component buffers are immutable copies.
    """
    trial, packet, proposed = None, None, stream
    stage, diagnostics = "initial_input", {}
    try:
        controls = perturb.validate_controls(controls)
        initial = _freeze(diffusion_m2_s)
        diffusion = perturb.StaticState(initial, initial, np.zeros_like(initial))
        trial = PhysiologyPerturbationState(protein, diffusion, stream, controls, 0.0, 0)
        validate_state(trial, binding)
        diagnostics = _diagnostics(trial)
        stage = "static_draw"
        packet, proposed = streams.draw(stream, binding, site="static_K")
        trial = replace(trial, stream=proposed)
        diagnostics.update(
            draw_consumed=True,
            draw_tick=packet.tick,
            packet_identity=packet.identity,
            stream_tick_after=proposed.next_tick,
        )
        stage = "static_trial"
        with np.errstate(over="ignore", invalid="ignore"):
            diffusion = perturb.static_initialize(
                initial, packet.values, controls.static_level, binding, xp=np
            )
        trial = replace(trial, diffusion=diffusion)
        if not perturb.static_domain_valid(
            initial, packet.values, controls.static_level, binding, xp=np
        ):
            raise ValueError("Static permeability trial leaves the strict nonnegative domain")
        validate_state(trial, binding)
        return trial
    except Exception as error:
        raise PerturbationRejected(
            error, trial=trial, packet=packet, stream=proposed, diagnostics=diagnostics, stage=stage
        ) from error


def advance(state, binding):
    """Attempt exactly one controls.dt_s component call and return its commit.

    The first call has loop label zero but applies a full dt. SIM finalizes
    current permeability from base+scheduled before the protein branch. INIT,
    fast and disabled dynamic guards consume no protein draw; all successful
    calls advance elapsed time/count. No sqrt(dt) or stage-dependent resampling
    is introduced. Nonconservative source_fast outcomes are refused unchanged.
    """
    trial, packet, proposed = state, None, getattr(state, "stream", None)
    stage, diagnostics = "accepted_input", {}
    try:
        validate_state(state, binding)
        diagnostics = _diagnostics(state)
        stage = "loop_clock"
        if state.loop_calls == MAX_LOOP_CALLS:
            raise ValueError("Component loop_calls increment would overflow uint64")
        time = float(state.time_s) + float(state.controls.dt_s)
        if not math.isfinite(time) or time <= state.time_s:
            raise ValueError("Accumulated component time must advance finitely before sampling")
        trial = replace(state, time_s=time, loop_calls=state.loop_calls + 1)
        diagnostics.update(elapsed_time_s=time, loop_calls_after=trial.loop_calls)
        stage = "event_finalization"
        if state.controls.phase == "SIM":
            with np.errstate(over="ignore", invalid="ignore"):
                trial = replace(trial, diffusion=perturb.finalize_scheduled(state.diffusion, xp=np))
            diagnostics["event_finalized"] = True
            validate_state(trial, binding)
        active = perturb.dynamic_active(state.controls)
        diagnostics["dynamic_active"] = active
        stage = "protein_draw"
        packet, proposed = streams.draw(state.stream, binding, site="protein_flux", enabled=active)
        trial = replace(trial, stream=proposed)
        diagnostics.update(
            draw_consumed=packet is not None,
            draw_tick=None if packet is None else packet.tick,
            packet_identity=None if packet is None else packet.identity,
            stream_tick_after=proposed.next_tick,
        )
        uniforms = np.zeros(len(binding.membrane_ids)) if packet is None else packet.values
        stage = "protein_trial"
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            result = perturb.protein_step(
                state.protein,
                uniforms,
                state.controls.dynamic_level_mol_m2_s,
                state.controls.dt_s,
                binding,
                enabled=active,
                xp=np,
            )
            trial = replace(trial, protein=result.state)
            residual = float(result.balance_residual_mol)
            scale = float(
                np.sum(np.abs(result.cell_amount_change_mol))
                + np.sum(np.abs(result.environment_amount_change_mol))
            )
            diagnostics.update(
                balance_residual_mol=_finite(residual), transferred_amount_scale_mol=_finite(scale)
            )
            valid = perturb.protein_domain_valid(
                state.protein,
                uniforms,
                state.controls.dynamic_level_mol_m2_s,
                state.controls.dt_s,
                binding,
                enabled=active,
                conservation_required=True,
                xp=np,
            )
        if not valid:
            raise ValueError("Protein trial violates nonnegative/conservative component domain")
        validate_state(trial, binding)
        return PerturbationTransition(trial, packet, MappingProxyType(diagnostics))
    except Exception as error:
        raise PerturbationRejected(
            error, trial=trial, packet=packet, stream=proposed, diagnostics=diagnostics, stage=stage
        ) from error
