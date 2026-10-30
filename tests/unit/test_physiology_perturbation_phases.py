"""Source association, nondrawing preparation and post-ion full-dt proposals."""

from dataclasses import asdict, replace

import numpy as np
import pytest

from cells.core import physiology_perturbation_phases as phases
from cells.core import physiology_perturbation_step as component_step
from cells.core import physiology_random_streams as streams
from cells.processes import betse_perturbations as perturb
from tests.unit import test_physiology_perturbation_step as component_tests
from tests.unit.test_physiology_perturbation_step import (
    equal_buffers,
    fingerprint,
    initialise,
)
from tests.unit.test_physiology_tissue_step import evidence
from validation.perturbations import physiology_perturbation_phases_reference as reference

inputs = component_tests.inputs


def plain(state):
    return dict(
        protein=state.protein._asdict(),
        diffusion=state.diffusion._asdict(),
        controls=asdict(state.controls),
        time_s=state.time_s,
        loop_calls=state.loop_calls,
        stream_next_tick=state.stream.next_tick,
    )


def make(inputs, law="native", profile="normal"):
    raw, binding, controls, protein, diffusion, original_stream = inputs
    updates = dict(
        normal={},
        INIT=dict(phase="INIT"),
        fast=dict(solver="fast"),
        dynamic_off=dict(dynamic_enabled=False),
        protein_off=dict(protein_enabled=False),
        zero_level=dict(dynamic_level_mol_m2_s=0.0),
    )
    controls = replace(controls, **updates[profile])
    if law == "native":
        rng = np.random.RandomState(17)
        rng.normal()
        stream = streams.new_stream(
            binding,
            perturb._native_stream(rng.get_state(), np.__version__),
            stream_id=original_stream.stream_id,
            world_id=original_stream.world_id,
        )
        fixture = (raw, binding, controls, protein, diffusion, stream)
    else:
        fixture = inputs
    state = initialise(fixture, controls=controls, law=law)
    state = replace(
        state,
        diffusion=state.diffusion._replace(scheduled_m2_s=-0.25 * state.diffusion.base_m2_s),
        stream=replace(state.stream, next_tick=2**40 + 3),
        time_s=0.012,
        loop_calls=6,
    )
    return raw, binding, state


def equal_state(actual, expected):
    equal_buffers(actual, expected)
    assert actual.controls == expected.controls
    assert actual.time_s == expected.time_s and actual.loop_calls == expected.loop_calls
    assert streams.stream_record(actual.stream) == streams.stream_record(expected.stream)


@pytest.mark.parametrize("law", ["native", "stable"])
@pytest.mark.parametrize(
    "profile", ["normal", "INIT", "fast", "dynamic_off", "protein_off", "zero_level"]
)
def test_initial_and_evolved_phases_match_one_qualified_transition_and_independent_reference(
    inputs, law, profile, monkeypatch
):
    raw, binding, state = make(inputs, law, profile)
    reference_state = plain(state)
    for index in range(3):
        before = fingerprint(state, binding)
        original_buffers = tuple(
            (x.tobytes(), x.flags.writeable) for x in (*state.protein, *state.diffusion)
        )
        expected = component_step.advance(state, binding)
        trace = []
        original_draw = streams.draw

        def forbidden(*args, **kwargs):
            pytest.fail("Preparation performed an RNG operation")

        with monkeypatch.context() as guard:
            guard.setattr(streams, "draw", forbidden)
            prepared = phases.prepare(state, binding)
        assert prepared.source_state is state
        assert prepared.held_state.time_s == state.time_s
        assert prepared.held_state.loop_calls == state.loop_calls
        assert prepared.held_state.stream is state.stream
        for a, b in zip(prepared.held_state.protein, state.protein, strict=True):
            np.testing.assert_array_equal(a, b)
        trace.append("caller-ion-interval")

        def draw(*args, _trace=trace, _original=original_draw, **kwargs):
            _trace.append("draw" if kwargs.get("enabled", True) else "disabled-draw-guard")
            return _original(*args, **kwargs)

        with monkeypatch.context() as guard:
            guard.setattr(streams, "draw", draw)
            actual = phases.finish(state, binding, prepared)
        assert trace[0] == "caller-ion-interval" and len(trace) == 2
        equal_state(actual.state, expected.state)
        assert actual.diagnostics["component_calls"] == 1
        assert actual.diagnostics["preparation_identity"] == prepared.identity
        assert actual.diagnostics["accepted_state_published"] is False
        assert fingerprint(state, binding) == before
        assert (
            tuple((x.tobytes(), x.flags.writeable) for x in (*state.protein, *state.diffusion))
            == original_buffers
        )
        reference_prepared = reference.prepare(raw, reference_state)
        packet = None if actual.packet is None else actual.packet.values
        reference_after = reference.finish(raw, reference_state, reference_prepared, packet)
        errors = {}
        for label, model, target in (
            ("held", prepared.held_state, reference_prepared["held"]),
            ("finish", actual.state, reference_after),
        ):
            for domain, atol in (("protein", 2e-14), ("diffusion", 1e-30)):
                for name, value in getattr(model, domain)._asdict().items():
                    expected_value = np.asarray(target[domain][name])
                    errors[label + "__" + domain + "__" + name] = float(
                        np.max(
                            np.abs(value - expected_value)
                            / (atol + 5e-13 * np.abs(expected_value)),
                            initial=0,
                        )
                    )
            assert model.time_s == target["time_s"]
            assert model.loop_calls == target["loop_calls"]
            assert model.stream.next_tick == target["stream_next_tick"]
        evidence(
            "perturbation-phases-" + law + "-" + profile + "-" + str(index),
            dict(
                raw_geometry=raw,
                law=law,
                profile=profile,
                index=index,
                reference_source=reference_state,
                prescribed_uniforms=packet,
                held=plain(prepared.held_state),
                finished=plain(actual.state),
                expected_held=reference_prepared["held"],
                expected_finished=reference_after,
                original_source=plain(state),
                source_stream=streams.stream_record(state.stream),
                finished_stream=streams.stream_record(actual.state.stream),
                packet_record=None
                if actual.packet is None
                else perturb.draw_manifest(actual.packet, binding),
                source_identity=prepared.source_identity,
                preparation_identity=prepared.identity,
                preparation_diagnostics=dict(prepared.diagnostics),
                finish_diagnostics=dict(actual.diagnostics),
                errors=errors,
                scope=(
                    "Own continuous prescribed-packet reference across three component calls; "
                    "caller ion marker only; no numeric/coupled/native-loop claim"
                ),
            ),
        )
        assert max(errors.values()) <= 1
        active = profile in ("normal", "zero_level")
        assert (actual.packet is not None) is active
        assert actual.state.stream.next_tick == state.stream.next_tick + int(active)
        assert actual.state.time_s == state.time_s + state.controls.dt_s
        if law == "native":
            assert (
                perturb.native_stream_manifest(actual.state.stream.rng)["state"][3:]
                == perturb.native_stream_manifest(state.stream.rng)["state"][3:]
            )
        reference_state, state = reference_after, actual.state


def test_finish_invokes_frozen_transition_once_and_same_source_replays_only_a_proposal(
    inputs, monkeypatch
):
    _, binding, state = make(inputs)
    prepared = phases.prepare(state, binding)
    original = component_step.advance
    calls = 0

    def advance(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    with monkeypatch.context() as guard:
        guard.setattr(component_step, "advance", advance)
        first = phases.finish(state, binding, prepared)
        assert calls == 1
        replay = phases.finish(state, binding, prepared)
        assert calls == 2
        with pytest.raises(phases.PerturbationPhaseRejected, match="source/held"):
            phases.finish(first.state, binding, prepared)
        assert calls == 2
    equal_state(first.state, replay.state)


@pytest.mark.parametrize(
    "field",
    ["cell", "membrane", "current", "scheduled", "dt", "phase", "time", "count", "tick", "world"],
)
def test_changed_source_refuses_before_any_postion_draw(inputs, field, monkeypatch):
    _, binding, state = make(inputs)
    prepared = phases.prepare(state, binding)
    if field in ("cell", "membrane"):
        name = field + "_mol_m3"
        state = replace(
            state, protein=state.protein._replace(**{name: getattr(state.protein, name) + 0.125})
        )
    elif field in ("current", "scheduled"):
        name = field + "_m2_s"
        state = replace(
            state,
            diffusion=state.diffusion._replace(**{name: getattr(state.diffusion, name) * 0.5}),
        )
    elif field == "dt":
        state = replace(state, controls=replace(state.controls, dt_s=state.controls.dt_s / 2))
    elif field == "phase":
        state = replace(state, controls=replace(state.controls, phase="INIT"))
    elif field == "time":
        state = replace(state, time_s=state.time_s + 0.1)
    elif field == "count":
        state = replace(state, loop_calls=state.loop_calls + 1)
    elif field == "tick":
        state = replace(state, stream=replace(state.stream, next_tick=state.stream.next_tick + 1))
    else:
        state = replace(
            state,
            stream=streams.new_stream(
                binding,
                state.stream.rng,
                stream_id=state.stream.stream_id,
                world_id=state.stream.world_id + 1,
                next_tick=state.stream.next_tick,
            ),
        )

    def forbidden(*args, **kwargs):
        pytest.fail("Stale source performed a post-ion component call")

    with monkeypatch.context() as guard:
        guard.setattr(component_step, "advance", forbidden)
        with pytest.raises(phases.PerturbationPhaseRejected) as caught:
            phases.finish(state, binding, prepared)
    assert caught.value.stage == "finish_association" and caught.value.packet is None
    assert caught.value.preparation is prepared and caught.value.source_state is state


@pytest.mark.parametrize(
    "field", ["identity", "source_identity", "held_state", "source_state", "diagnostics"]
)
def test_corrupt_or_resealed_preparation_cannot_replace_the_derived_hold(inputs, field):
    _, binding, state = make(inputs)
    prepared = phases.prepare(state, binding)
    if field in ("identity", "source_identity"):
        forged = replace(prepared, **{field: "0" * 64})
    elif field == "source_state":
        source = replace(
            state, protein=state.protein._replace(cell_mol_m3=state.protein.cell_mol_m3 + 0.125)
        )
        forged = replace(prepared, source_state=source)
    elif field == "held_state":
        held = replace(
            prepared.held_state,
            diffusion=prepared.held_state.diffusion._replace(
                current_m2_s=2 * prepared.held_state.diffusion.current_m2_s
            ),
        )
        held_id = phases._source_identity(held, binding)
        forged = replace(
            prepared,
            held_state=held,
            held_identity=held_id,
            identity=phases._digest(
                phases._payload(
                    prepared.source_identity,
                    held_id,
                    prepared.binding_identity,
                    prepared.diagnostics,
                )
            ),
        )
    else:
        diagnostics = dict(prepared.diagnostics) | dict(accepted_state_published=True)
        forged = replace(
            prepared,
            diagnostics=diagnostics,
            identity=phases._digest(
                phases._payload(
                    prepared.source_identity,
                    prepared.held_identity,
                    prepared.binding_identity,
                    diagnostics,
                )
            ),
        )
    with pytest.raises(phases.PerturbationPhaseRejected) as caught:
        phases.finish(state, binding, forged)
    assert caught.value.stage == "finish_association" and caught.value.packet is None


@pytest.mark.parametrize("failure", ["count", "time", "permeability"])
def test_prepare_failures_retain_raw_hold_without_draw_or_clock_advance(
    inputs, failure, monkeypatch
):
    _, binding, state = make(inputs)
    if failure == "count":
        state = replace(state, loop_calls=component_step.MAX_LOOP_CALLS)
    elif failure == "time":
        state = replace(state, time_s=1e308)
    else:
        state = replace(
            state, diffusion=state.diffusion._replace(scheduled_m2_s=-2 * state.diffusion.base_m2_s)
        )
    before = fingerprint(state, binding)

    def forbidden(*a, **k):
        pytest.fail("Preparation failure sampled RNG")

    with monkeypatch.context() as guard:
        guard.setattr(streams, "draw", forbidden)
        with pytest.raises(phases.PerturbationPhaseRejected) as caught:
            phases.prepare(state, binding)
    error = caught.value
    assert error.packet is None and error.stream is state.stream
    assert fingerprint(state, binding) == before
    if failure == "permeability":
        assert error.stage == "prepare_permeability" and error.trial is error.held_state
        assert np.any(error.trial.diffusion.current_m2_s < 0)
        assert error.trial.time_s == state.time_s and error.trial.loop_calls == state.loop_calls
        evidence(
            "perturbation-phases-rejected-prepare",
            dict(stage=error.stage, source=plain(state), trial=plain(error.trial)),
        )


@pytest.mark.parametrize("failure", ["protein", "tick"])
def test_finish_failure_retains_qualified_child_trial_packet_stream_and_source(inputs, failure):
    _, binding, state = make(inputs)
    if failure == "protein":
        state = replace(
            state, protein=perturb.ProteinState(*(np.zeros_like(v) for v in state.protein))
        )
    else:
        state = replace(state, stream=replace(state.stream, next_tick=2**64 - 1))
    prepared = phases.prepare(state, binding)
    before = fingerprint(state, binding)
    with pytest.raises(component_step.PerturbationRejected) as original:
        component_step.advance(state, binding)
    with pytest.raises(phases.PerturbationPhaseRejected) as caught:
        phases.finish(state, binding, prepared)
    error, expected = caught.value, original.value
    assert error.stage == "finish_component_transition" and error.component_rejection is not None
    assert error.preparation is prepared and error.source_state is state
    assert error.trial is error.component_rejection.trial
    assert error.packet is error.component_rejection.packet
    equal_state(error.trial, expected.trial)
    assert streams.stream_record(error.stream) == streams.stream_record(expected.stream)
    assert (error.packet is not None) == (failure == "protein")
    if error.packet is not None:
        np.testing.assert_array_equal(error.packet.values, expected.packet.values)
    assert fingerprint(state, binding) == before
    evidence(
        "perturbation-phases-rejected-finish-" + failure,
        dict(
            source=plain(state),
            held=plain(prepared.held_state),
            trial=plain(error.trial),
            packet=None if error.packet is None else error.packet.values,
            stage=error.stage,
            child_stage=error.component_rejection.stage,
            proposed_stream=streams.stream_record(error.stream),
        ),
    )


def test_held_source_and_diagnostics_are_immutable_without_becoming_accepted_state(inputs):
    _, binding, state = make(inputs)
    prepared = phases.prepare(state, binding)
    assert prepared.diagnostics["accepted_state_published"] is False
    assert prepared.diagnostics["draw_consumed"] is False
    for value in (*prepared.held_state.protein, *prepared.held_state.diffusion):
        with pytest.raises(ValueError):
            value.setflags(write=True)
    with pytest.raises(TypeError):
        prepared.diagnostics["event_finalized"] = False
    with pytest.raises(phases.PerturbationPhaseRejected):
        phases.finish(prepared.held_state, binding, prepared)


def test_source_uses_content_association_and_preserves_static_base_and_signed_schedule(inputs):
    _, binding, state = make(inputs)
    prepared = phases.prepare(state, binding)
    cloned = replace(state)
    result = phases.finish(cloned, binding, prepared)
    np.testing.assert_array_equal(result.state.diffusion.base_m2_s, state.diffusion.base_m2_s)
    np.testing.assert_array_equal(
        result.state.diffusion.scheduled_m2_s, state.diffusion.scheduled_m2_s
    )
    assert np.any(result.state.diffusion.scheduled_m2_s < 0)
    assert not np.array_equal(
        prepared.held_state.diffusion.current_m2_s, state.diffusion.current_m2_s
    )
