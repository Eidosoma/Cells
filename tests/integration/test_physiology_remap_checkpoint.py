"""Restart of explicitly remapped components; numeric tissue coupling is external."""

import math
from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

from cells import physiology_checkpoint as checkpoint
from cells.core import physiology_perturbation_remap as remap
from cells.core import physiology_perturbation_step as step
from cells.core import physiology_random_streams as streams
from cells.core.runner import run
from cells.core.specs import parse_spec, read_json
from cells.processes import betse_perturbations as perturb


@pytest.fixture
def numeric(config_data):
    raw = deepcopy(config_data)
    raw["experiment"] = dict(
        end_time=0.1,
        source=dict(kind="prescribed_external_amount_rate", schedule=[dict(time=0.0, rate=0.1)]),
        observation_times=[0.0, 0.05, 0.1],
    )
    raw["execution"].update(jit=False, max_steps=4)
    spec = parse_spec(raw)
    reference = run(spec)
    return spec, reference.checkpoint_at(0.05), reference


def original_layout():
    # Deliberately interleave membrane ownership; array position is not identity.
    return perturb.Layout(
        cell_ids=("left", "middle", "right"),
        membrane_ids=("m4", "m1", "m6", "m0", "m8"),
        environment_ids=("outside-1", "outside-0"),
        ion_ids=("P", "Na", "K"),
        membrane_cell_ids=("middle", "left", "right", "left", "middle"),
        membrane_environment_ids=("outside-1", "outside-0", "outside-1", "outside-1", "outside-0"),
        boundary_cell_occurrences=("left", "right", "middle", "right"),
        membrane_area_m2=np.array([2e-12, 3e-12, 1e-12, 4e-12, 2e-12]),
        cell_volume_m3=np.array([2e-15, 4e-15, 3e-15]),
        environment_parameter_volume_m3=1e-12,
        environment_mode="matrix",
        provenance=dict(test="component-only removal and paired restart"),
    )


def keep_layout(layout, cells):
    cell_indices = [layout.cell_ids.index(name) for name in cells]
    membrane_indices = [
        i for i in reversed(range(len(layout.membrane_ids))) if layout.membrane_cell_ids[i] in cells
    ]
    return replace(
        layout,
        cell_ids=tuple(cells),
        membrane_ids=tuple(layout.membrane_ids[i] for i in membrane_indices),
        membrane_cell_ids=tuple(layout.membrane_cell_ids[i] for i in membrane_indices),
        membrane_environment_ids=tuple(
            layout.membrane_environment_ids[i] for i in membrane_indices
        ),
        membrane_area_m2=layout.membrane_area_m2[membrane_indices],
        cell_volume_m3=layout.cell_volume_m3[cell_indices],
        environment_ids=layout.environment_ids[::-1],
        ion_ids=layout.ion_ids[::-1],
        boundary_cell_occurrences=tuple(
            name for name in layout.boundary_cell_occurrences if name in cells
        ),
    )


def initial_state(binding, law):
    rng = perturb.native_stream(23) if law == "native" else perturb.StableCoordinates(23, 2**40 + 9)
    stream = streams.new_stream(
        binding, rng, stream_id="removal", world_id=2**40 + 9, next_tick=2**32 + 17
    )
    # The native five-element prefix leaves a cached Gaussian, which a cut and
    # paired restart must preserve. This is a stream probe, not a physical law.
    _, stream = streams.draw(stream, binding, site="microtubule_gaussian")
    state = step.initialise(
        binding,
        perturb.Controls("SIM", "normal", True, True, 2.0, 3e-7, 0.002),
        perturb.ProteinState(np.array([8.0, 7.0, 6.0]), np.arange(5.0) + 11, np.array([5.0, 4.0])),
        (np.arange(15.0).reshape(3, 5) + 1) * 1e-18,
        stream,
    )
    return replace(
        state, diffusion=state.diffusion._replace(scheduled_m2_s=-0.25 * state.diffusion.base_m2_s)
    )


def material_amounts(state, binding):
    return (
        *(state.protein.cell_mol_m3 * binding.kernel.cell_volume_m3),
        *(state.protein.environment_mol_m3 * binding.kernel.environment_effective_volume_m3),
    )


def assert_same(actual, expected):
    assert actual.controls == expected.controls
    assert actual.time_s == expected.time_s and actual.loop_calls == expected.loop_calls
    assert streams.stream_record(actual.stream) == streams.stream_record(expected.stream)
    for a, b in zip(
        (*actual.protein, *actual.diffusion), (*expected.protein, *expected.diffusion), strict=True
    ):
        np.testing.assert_array_equal(a, b, strict=True)
        assert not a.flags.writeable


def assert_same_transition(actual, expected, binding):
    assert_same(actual.state, expected.state)
    assert perturb.draw_manifest(actual.packet, binding) == perturb.draw_manifest(
        expected.packet, binding
    )
    assert dict(actual.diagnostics) == dict(expected.diagnostics)


@pytest.mark.parametrize("law", ["native", "stable"])
@pytest.mark.parametrize("prefix_calls", [0, 3])
def test_remap_restart_preserves_six_buffers_clocks_and_future_component_calls(
    tmp_path, numeric, law, prefix_calls, monkeypatch
):
    spec, numeric_point, numeric_reference = numeric
    layout = original_layout()
    old = perturb.bind_layout(layout)
    current = initial_state(old, law)
    for _ in range(prefix_calls):
        current = step.advance(current, old).state
    new_layout = keep_layout(layout, ("right", "left"))
    new = perturb.bind_layout(new_layout)
    cut = remap.remap_component(current, old, new)
    assert cut.archive.cell_ids == ("middle",)
    assert (
        math.fsum(
            (
                *material_amounts(current, old),
                *(-np.asarray(material_amounts(cut.state, new))),
                -cut.archive.total_amount_mol,
            )
        )
        == 0.0
    )

    def forbidden(*args, **kwargs):
        pytest.fail("Writing or loading the accepted remap consumed a random draw")

    with monkeypatch.context() as guarded:
        guarded.setattr(streams, "draw", forbidden)
        guarded.setattr(perturb, "sample_native", forbidden)
        guarded.setattr(perturb, "sample_stable", forbidden)
        root = checkpoint.write_physiology_checkpoint(
            tmp_path / "post_removal",
            spec,
            numeric_point,
            cut.state.stream,
            new,
            component_state=cut.state,
        )
        saved = checkpoint.load_physiology_checkpoint(
            root,
            new,
            require_component=True,
            expected_stream_id="removal",
            expected_world_id=2**40 + 9,
        )
    resumed = saved.component_state
    assert_same(resumed, cut.state)
    assert resumed.stream.next_tick == current.stream.next_tick
    assert resumed.stream.rng == current.stream.rng
    assert resumed.time_s == current.time_s
    assert resumed.loop_calls == prefix_calls
    assert saved.snapshot.checkpoint.time == 0.05  # Independent numeric state association.
    if law == "native":
        assert perturb.native_stream_manifest(resumed.stream.rng)["state"][3] == 1
    manifest = read_json(root / "manifest.json")
    assert manifest["layout_identity"] == new.identity != old.identity
    assert manifest["component_clock"]["loop_calls"] == prefix_calls
    with pytest.raises(ValueError, match="layout"):
        checkpoint.load_physiology_checkpoint(root, old, require_component=True)

    uninterrupted = cut.state
    for _ in range(5):
        expected = step.advance(uninterrupted, new)
        actual = step.advance(resumed, new)
        assert_same_transition(actual, expected, new)
        uninterrupted, resumed = expected.state, actual.state
    assert resumed.loop_calls == prefix_calls + 5
    continued = run(saved.snapshot.spec, saved.snapshot.checkpoint)
    for actual, expected in zip(continued.final.state, numeric_reference.final.state, strict=True):
        np.testing.assert_array_equal(np.asarray(actual), np.asarray(expected), strict=True)


@pytest.mark.parametrize("law", ["native", "stable"])
def test_successive_removal_restart_preserves_each_explicit_sink(tmp_path, numeric, law):
    spec, numeric_point, _ = numeric
    first_layout = original_layout()
    first_binding = perturb.bind_layout(first_layout)
    initial = initial_state(first_binding, law)
    second_layout = keep_layout(first_layout, ("right", "left"))
    second_binding = perturb.bind_layout(second_layout)
    first_cut = remap.remap_component(initial, first_binding, second_binding)
    root = checkpoint.write_physiology_checkpoint(
        tmp_path / "first_cut",
        spec,
        numeric_point,
        first_cut.state.stream,
        second_binding,
        component_state=first_cut.state,
    )
    reloaded = checkpoint.load_physiology_checkpoint(root, second_binding, require_component=True)
    final_layout = keep_layout(second_layout, ("left",))
    final_binding = perturb.bind_layout(final_layout)
    expected_cut = remap.remap_component(first_cut.state, second_binding, final_binding)
    actual_cut = remap.remap_component(reloaded.component_state, second_binding, final_binding)
    assert_same(actual_cut.state, expected_cut.state)
    for actual, expected in zip(
        (*actual_cut.archive.protein, *actual_cut.archive.diffusion),
        (*expected_cut.archive.protein, *expected_cut.archive.diffusion),
        strict=True,
    ):
        np.testing.assert_array_equal(actual, expected, strict=True)
    assert first_cut.archive.cell_ids == ("middle",) and actual_cut.archive.cell_ids == ("right",)
    # Both removed archives remain caller-owned; an ordinary complete-state
    # checkpoint saves the survivor, not a fabricated history of earlier cuts.
    removed = (*first_cut.archive.cell_amount_mol, *actual_cut.archive.cell_amount_mol)
    assert (
        math.fsum(
            (
                *material_amounts(initial, first_binding),
                *(-np.asarray(material_amounts(actual_cut.state, final_binding))),
                *(-np.asarray(removed)),
            )
        )
        == 0.0
    )
    second_root = checkpoint.write_physiology_checkpoint(
        tmp_path / "second_cut",
        spec,
        numeric_point,
        actual_cut.state.stream,
        final_binding,
        component_state=actual_cut.state,
    )
    final = checkpoint.load_physiology_checkpoint(
        second_root, final_binding, require_component=True
    )
    assert_same(final.component_state, actual_cut.state)
    assert_same_transition(
        step.advance(final.component_state, final_binding),
        step.advance(expected_cut.state, final_binding),
        final_binding,
    )
    with pytest.raises(ValueError, match="layout"):
        checkpoint.load_physiology_checkpoint(second_root, second_binding, require_component=True)


def test_postcut_state_cannot_be_published_under_parent_binding(tmp_path, numeric):
    spec, numeric_point, _ = numeric
    layout = original_layout()
    before = perturb.bind_layout(layout)
    after = perturb.bind_layout(keep_layout(layout, ("right", "left")))
    cut = remap.remap_component(initial_state(before, "native"), before, after)
    root = tmp_path / "wrong_binding"
    with pytest.raises(ValueError, match="layout"):
        checkpoint.write_physiology_checkpoint(
            root,
            spec,
            numeric_point,
            cut.state.stream,
            before,
            component_state=cut.state,
        )
    assert not root.exists()
