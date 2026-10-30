"""Atomic explicit-loop component tests; no full physiology solver is invoked."""

from dataclasses import FrozenInstanceError, replace

import numpy as np
import pytest

from cells.core import physiology_perturbation_step as step
from cells.core import physiology_random_streams as streams
from cells.processes import betse_perturbations as perturb
from validation.perturbations.betse_perturbations_fixtures import base


def bind(raw, mode="matrix"):
    return perturb.bind_layout(
        perturb.Layout(
            tuple(raw["cell_ids"]),
            tuple(raw["membrane_ids"]),
            tuple(raw["environment_ids"]),
            tuple(raw["ion_ids"]),
            tuple(raw["cell_ids"][i] for i in raw["owner"]),
            tuple(raw["environment_ids"][i] for i in raw["environment_owner"]),
            tuple(raw["cell_ids"][i] for i in raw["boundary_cells"]),
            np.asarray(raw["membrane_area_m2"]),
            np.asarray(raw["cell_volume_m3"]),
            raw["environment_volume_m3"],
            mode,
            dict(synthetic_fixture="qualified perturbation base"),
        )
    )


@pytest.fixture
def inputs():
    raw = base()
    binding = bind(raw)
    controls = perturb.Controls(
        raw["phase"],
        raw["solver"],
        raw["dynamic_enabled"],
        raw["protein_enabled"],
        raw["static_level"],
        raw["dynamic_level"],
        raw["dt_s"],
    )
    protein = perturb.ProteinState(
        *(
            np.asarray(raw[key], dtype=float)
            for key in (
                "initial_cell_mol_m3",
                "initial_membrane_mol_m3",
                "initial_environment_mol_m3",
            )
        )
    )
    diffusion = np.asarray(raw["initial_diffusion_m2_s"])
    stream = streams.new_stream(
        binding, perturb.native_stream(17), stream_id="component", world_id=7
    )
    return raw, binding, controls, protein, diffusion, stream


def initialise(inputs, *, controls=None, protein=None, law="native"):
    _, binding, original, initial_protein, diffusion, stream = inputs
    if law == "stable":
        stream = streams.new_stream(
            binding, perturb.StableCoordinates(17, 7), stream_id="component", world_id=7
        )
    return step.initialise(
        binding,
        original if controls is None else controls,
        initial_protein if protein is None else protein,
        diffusion,
        stream,
    )


def fingerprint(state, binding):
    return perturb.replay_record(
        binding,
        state.controls,
        perturb.Replay(
            state.protein, state.diffusion, state.stream.rng, state.stream.next_tick, state.time_s
        ),
    ) | dict(stream=streams.stream_record(state.stream), loop_calls=state.loop_calls)


def equal_buffers(a, b):
    for actual, expected in zip(
        (*a.protein, *a.diffusion), (*b.protein, *b.diffusion), strict=True
    ):
        np.testing.assert_array_equal(actual, expected)


@pytest.mark.parametrize("law", ["native", "stable"])
def test_initialise_keeps_base_before_static_and_consumes_exactly_one_draw(inputs, law):
    _, binding, controls, protein, diffusion, original_stream = inputs
    stream = (
        original_stream
        if law == "native"
        else streams.new_stream(
            binding, perturb.StableCoordinates(17, 7), stream_id="component", world_id=7
        )
    )
    original = streams.stream_record(stream)
    packet, after = streams.draw(stream, binding, site="static_K")
    expected = perturb.static_initialize(
        diffusion, packet.values, controls.static_level, binding, xp=np
    )
    state = step.initialise(binding, controls, protein, diffusion, stream)
    assert state.stream == after and state.stream.next_tick == stream.next_tick + 1
    assert state.time_s == 0.0 and state.loop_calls == 0
    assert streams.stream_record(stream) == original
    for actual, target in zip(state.diffusion, expected, strict=True):
        np.testing.assert_array_equal(actual, target)
    np.testing.assert_array_equal(state.diffusion.base_m2_s, diffusion)
    np.testing.assert_array_equal(state.diffusion.scheduled_m2_s, np.zeros_like(diffusion))
    assert not np.array_equal(state.diffusion.current_m2_s, state.diffusion.base_m2_s)
    for actual, target in zip(state.protein, protein, strict=True):
        np.testing.assert_array_equal(actual, target)


def test_atomic_SIM_sequence_matches_exact_component_order_and_dt(inputs):
    _, binding, controls, _, _, _ = inputs
    state = initialise(inputs)
    state = replace(
        state, diffusion=state.diffusion._replace(scheduled_m2_s=-0.25 * state.diffusion.base_m2_s)
    )
    for call in range(7):
        before = fingerprint(state, binding)
        packet, after_stream = streams.draw(state.stream, binding, site="protein_flux")
        result = perturb.protein_step(
            state.protein,
            packet.values,
            controls.dynamic_level_mol_m2_s,
            controls.dt_s,
            binding,
            xp=np,
        )
        diffusion = perturb.finalize_scheduled(state.diffusion, xp=np)
        transition = step.advance(state, binding)
        assert perturb.draw_manifest(transition.packet, binding) == perturb.draw_manifest(
            packet, binding
        )
        assert transition.state.stream == after_stream
        assert transition.state.time_s == state.time_s + controls.dt_s
        assert transition.state.loop_calls == call + 1
        assert transition.diagnostics["source_loop_label_s"] == state.time_s
        assert transition.diagnostics["dt_s"] == controls.dt_s
        assert transition.diagnostics["event_finalized"] is True
        assert abs(transition.diagnostics["balance_residual_mol"]) <= (
            3e-13 * transition.diagnostics["transferred_amount_scale_mol"]
        )
        for actual, target in zip(transition.state.protein, result.state, strict=True):
            np.testing.assert_array_equal(actual, target)
        for actual, target in zip(transition.state.diffusion, diffusion, strict=True):
            np.testing.assert_array_equal(actual, target)
        assert fingerprint(state, binding) == before
        state = transition.state


@pytest.mark.parametrize(
    "phase,solver,dynamic,protein_enabled",
    [
        ("INIT", "normal", True, True),
        ("INIT", "fast", True, True),
        ("SIM", "fast", True, True),
        ("SIM", "normal", False, True),
        ("SIM", "normal", True, False),
    ],
)
def test_inactive_guards_preserve_all_protein_buffers_but_advance_loop_clock(
    inputs, phase, solver, dynamic, protein_enabled, monkeypatch
):
    _, binding, controls, _, _, _ = inputs
    controls = replace(
        controls,
        phase=phase,
        solver=solver,
        dynamic_enabled=dynamic,
        protein_enabled=protein_enabled,
    )
    state = initialise(inputs, controls=controls)
    assert state.stream.next_tick == 1  # Static draw happens under every guard.

    def forbidden(*args, **kwargs):
        pytest.fail("Inactive component invoked a sampler")

    monkeypatch.setattr(perturb, "sample_native", forbidden)
    monkeypatch.setattr(perturb, "sample_stable", forbidden)
    transition = step.advance(state, binding)
    assert transition.packet is None and transition.state.stream is state.stream
    assert transition.state.time_s == controls.dt_s and transition.state.loop_calls == 1
    assert transition.diagnostics["draw_consumed"] is False
    for actual, target in zip(transition.state.protein, state.protein, strict=True):
        np.testing.assert_array_equal(actual, target)  # No downstream bulk refresh.
    np.testing.assert_array_equal(
        transition.state.diffusion.current_m2_s,
        state.diffusion.base_m2_s if phase == "SIM" else state.diffusion.current_m2_s,
    )


@pytest.mark.parametrize("law", ["native", "stable"])
def test_enabled_zero_levels_still_draw_at_initialisation_and_first_t0_call(inputs, law):
    _, binding, controls, _, _, _ = inputs
    controls = replace(controls, static_level=0.0, dynamic_level_mol_m2_s=0.0)
    state = initialise(inputs, controls=controls, law=law)
    np.testing.assert_array_equal(state.diffusion.current_m2_s, state.diffusion.base_m2_s)
    assert state.stream.next_tick == 1
    result = step.advance(state, binding)
    assert result.packet.tick == 1 and result.state.stream.next_tick == 2
    assert result.diagnostics["source_loop_label_s"] == 0.0
    assert result.state.time_s == controls.dt_s and result.state.loop_calls == 1
    np.testing.assert_array_equal(result.state.protein.cell_mol_m3, state.protein.cell_mol_m3)
    np.testing.assert_array_equal(
        result.state.protein.environment_mol_m3, state.protein.environment_mol_m3
    )
    assert result.diagnostics["balance_residual_mol"] == 0.0


def test_validate_state_is_nondrawing_and_owned_buffers_are_immutable(inputs, monkeypatch):
    _, binding, _, protein, diffusion, _ = inputs
    state = initialise(inputs)

    def forbidden(*args, **kwargs):
        pytest.fail("Validation sampled a draw")

    monkeypatch.setattr(streams, "draw", forbidden)
    assert step.validate_state(state, binding) is state
    protein.cell_mol_m3[0] = 1234
    diffusion[0, 0] = 1234
    assert state.protein.cell_mol_m3[0] != 1234 and state.diffusion.base_m2_s[0, 0] != 1234
    for value in (*state.protein, *state.diffusion):
        with pytest.raises(ValueError):
            value.setflags(write=True)
    with pytest.raises(FrozenInstanceError):
        state.time_s = 9.0


def test_rejected_negative_protein_retains_trial_draw_and_rng_without_commit(inputs):
    _, binding, _, protein, _, _ = inputs
    state = initialise(
        inputs, protein=perturb.ProteinState(*(np.zeros_like(value) for value in protein))
    )
    before = fingerprint(state, binding)
    packet, proposed = streams.draw(state.stream, binding, site="protein_flux")
    with pytest.raises(step.PerturbationRejected) as caught:
        step.advance(state, binding)
    error = caught.value
    assert error.stage == "protein_trial"
    assert error.stream == proposed and error.trial.stream == proposed
    assert perturb.draw_manifest(error.packet, binding) == perturb.draw_manifest(packet, binding)
    assert any(np.any(value < 0) for value in error.trial.protein)
    assert error.trial.time_s == state.time_s + state.controls.dt_s
    assert error.trial.loop_calls == state.loop_calls + 1
    assert fingerprint(state, binding) == before


def test_negative_finalized_permeability_refuses_before_protein_draw(inputs, monkeypatch):
    _, binding, _, _, _, _ = inputs
    state = initialise(inputs)
    state = replace(
        state, diffusion=state.diffusion._replace(scheduled_m2_s=-2 * state.diffusion.base_m2_s)
    )
    before = fingerprint(state, binding)

    def forbidden(*args, **kwargs):
        pytest.fail("Invalid finalized permeability reached sampling")

    monkeypatch.setattr(streams, "draw", forbidden)
    with pytest.raises(step.PerturbationRejected) as caught:
        step.advance(state, binding)
    error = caught.value
    assert error.stage == "event_finalization" and error.packet is None
    assert error.stream is state.stream and np.any(error.trial.diffusion.current_m2_s < 0)
    assert fingerprint(state, binding) == before


def test_negative_static_trial_keeps_its_already_consumed_draw(inputs):
    _, binding, controls, protein, diffusion, stream = inputs
    controls = replace(controls, static_level=-2.0)
    before = diffusion.copy()
    packet, proposed = streams.draw(stream, binding, site="static_K")
    with pytest.raises(step.PerturbationRejected) as caught:
        step.initialise(binding, controls, protein, diffusion, stream)
    error = caught.value
    assert error.stage == "static_trial" and error.stream == proposed
    assert perturb.draw_manifest(error.packet, binding) == perturb.draw_manifest(packet, binding)
    assert np.any(error.trial.diffusion.current_m2_s < 0)
    np.testing.assert_array_equal(error.trial.diffusion.base_m2_s, before)
    np.testing.assert_array_equal(diffusion, before)


def test_missing_K_rejection_preserves_static_draw_timing(inputs):
    raw, _, controls, protein, diffusion, _ = inputs
    raw["ion_ids"] = ["Na", "other", "P"]
    binding = bind(raw)
    stream = streams.new_stream(
        binding, perturb.native_stream(17), stream_id="component", world_id=7
    )
    with pytest.raises(step.PerturbationRejected) as caught:
        step.initialise(binding, controls, protein, diffusion, stream)
    assert caught.value.packet.site == "static_K" and caught.value.stream.next_tick == 1
    assert caught.value.stage == "static_trial"


def test_nonconservative_source_fast_trial_is_retained_and_refused(inputs):
    raw, _, controls, protein, diffusion, _ = inputs
    binding = bind(raw, "source_fast")
    stream = streams.new_stream(
        binding, perturb.native_stream(17), stream_id="component", world_id=7
    )
    state = step.initialise(binding, controls, protein, diffusion, stream)
    before = fingerprint(state, binding)
    with pytest.raises(step.PerturbationRejected, match="conservative") as caught:
        step.advance(state, binding)
    error = caught.value
    assert all(np.all(value >= 0) for value in error.trial.protein)
    assert abs(error.diagnostics["balance_residual_mol"]) > (
        3e-13 * error.diagnostics["transferred_amount_scale_mol"]
    )
    assert error.stream.next_tick == state.stream.next_tick + 1
    assert fingerprint(state, binding) == before


@pytest.mark.parametrize("mode", ["source_fast", "mixed_bath"])
def test_conservative_nonmatrix_mappings_are_not_categorically_refused(inputs, mode):
    raw, _, controls, protein, diffusion, _ = inputs
    if mode == "source_fast":
        raw["environment_ids"] = ["outside" + str(i) for i in range(7)]
        raw["environment_owner"] = list(range(7))
        outside = np.full(7, 5.0)
    else:
        raw["environment_ids"] = ["bath"]
        raw["environment_owner"] = [0] * 7
        outside = np.asarray([5.0])
    protein = protein._replace(environment_mol_m3=outside)
    binding = bind(raw, mode)
    stream = streams.new_stream(
        binding, perturb.native_stream(17), stream_id="component", world_id=7
    )
    result = step.advance(step.initialise(binding, controls, protein, diffusion, stream), binding)
    assert result.state.loop_calls == 1
    assert abs(result.diagnostics["balance_residual_mol"]) <= (
        3e-13 * result.diagnostics["transferred_amount_scale_mol"]
    )


@pytest.mark.parametrize("defect", ["loop_overflow", "time_overflow", "time_stagnation"])
def test_loop_clock_refusals_happen_before_sampling(inputs, defect, monkeypatch):
    _, binding, _, _, _, _ = inputs
    state = initialise(inputs)
    if defect == "loop_overflow":
        state = replace(state, loop_calls=step.MAX_LOOP_CALLS)
    elif defect == "time_overflow":
        state = replace(
            state,
            time_s=np.finfo(float).max,
            controls=replace(state.controls, dt_s=np.finfo(float).max),
        )
    else:
        state = replace(state, time_s=1e16)
    before = fingerprint(state, binding)

    def forbidden(*args, **kwargs):
        pytest.fail("Invalid loop clock reached sampling")

    monkeypatch.setattr(streams, "draw", forbidden)
    with pytest.raises(step.PerturbationRejected) as caught:
        step.advance(state, binding)
    assert caught.value.stage == "loop_clock" and caught.value.packet is None
    assert caught.value.stream is state.stream
    assert fingerprint(state, binding) == before


@pytest.mark.parametrize("active", [True, False])
def test_exhausted_draw_counter_refuses_active_call_but_inactive_loop_can_advance(inputs, active):
    _, binding, controls, _, _, _ = inputs
    state = initialise(inputs, controls=replace(controls, dynamic_enabled=active))
    stream = replace(state.stream, next_tick=streams.MAX_TICK)
    state = replace(state, stream=stream)
    if active:
        with pytest.raises(step.PerturbationRejected, match="overflow") as caught:
            step.advance(state, binding)
        assert caught.value.packet is None and caught.value.stream is stream
    else:
        result = step.advance(state, binding)
        assert result.state.stream is stream and result.state.loop_calls == 1
        assert result.state.time_s == controls.dt_s


@pytest.mark.parametrize("defect", ["negative", "nan", "batch", "complex", "bool"])
def test_invalid_initial_buffers_refuse_without_sampling(inputs, defect, monkeypatch):
    _, binding, controls, protein, diffusion, stream = inputs
    if defect == "negative":
        protein = protein._replace(cell_mol_m3=-protein.cell_mol_m3)
    elif defect == "nan":
        diffusion[0, 0] = np.nan
    elif defect == "batch":
        protein = protein._replace(cell_mol_m3=protein.cell_mol_m3[None, :])
    elif defect == "complex":
        diffusion = diffusion.astype(complex) + 1j
    else:
        diffusion = np.ones_like(diffusion, dtype=bool)

    def forbidden(*args, **kwargs):
        pytest.fail("Invalid initial buffers reached sampling")

    monkeypatch.setattr(streams, "draw", forbidden)
    with pytest.raises(step.PerturbationRejected):
        step.initialise(binding, controls, protein, diffusion, stream)


def test_validate_state_rejects_foreign_binding_without_sampling(inputs, monkeypatch):
    _, binding, _, _, _, _ = inputs
    state = initialise(inputs)
    foreign = replace(binding, identity="0" * 64)

    def forbidden(*args, **kwargs):
        pytest.fail("Validation sampled")

    monkeypatch.setattr(streams, "draw", forbidden)
    with pytest.raises(ValueError):
        step.validate_state(state, foreign)
