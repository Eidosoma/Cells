"""World packing, masked loops, restoration and strict comparison policy."""

import json
from functools import partial
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.assembly_cluster import engine
from cells.assembly_cluster.spec import parse_spec
from cells.models.registry import get_model
from cells.numerics import extracellular_field as field
from validation.ensemble import parallel_cluster as screen
from validation.ensemble import parallel_kernel as candidate


@pytest.mark.parametrize("worlds", [1, 2, 3, 16, 32, 33, 65])
@pytest.mark.parametrize("width", [4, 32, 64])
def test_fixed_tiles_preserve_ids_order_and_divergent_world_clocks(worlds, width):
    ids = jnp.arange(61, 61 + worlds, dtype=jnp.uint32)
    start = jnp.zeros(worlds, dtype=jnp.uint32)

    def advance(inputs):
        value, identity = inputs
        target = identity % 7
        value = jax.lax.while_loop(lambda x: x < target, lambda x: x + 1, value)
        return value, identity * 31 + value

    packed = jax.jit(partial(candidate.tile_map, advance, width=width))((start, ids))
    expected = jax.lax.map(advance, (start, ids))
    for actual, wanted in zip(packed, expected, strict=True):
        np.testing.assert_array_equal(actual, wanted)
    if worlds > 1:
        parts = [
            candidate.tile_map(advance, (start[:1], ids[:1]), width=width),
            candidate.tile_map(advance, (start[1:], ids[1:]), width=width),
        ]
        for index in range(2):
            np.testing.assert_array_equal(packed[index], np.concatenate([p[index] for p in parts]))


@pytest.mark.parametrize("width", [0, -1, True, 1.5])
def test_invalid_tile_width_is_refused(width):
    with pytest.raises(ValueError, match="positive integer"):
        candidate.tile_map(lambda x: x, jnp.ones((1, 2)), width=width)


@pytest.mark.parametrize("values", [(), (np.zeros(0),), (np.ones(2), np.ones(3)), (np.array(1),)])
def test_invalid_world_axes_are_refused(values):
    with pytest.raises(ValueError, match="world"):
        candidate.tile_map(lambda x: x, values)


@pytest.mark.parametrize("variant", candidate.VARIANTS)
def test_candidate_restores_reference_functions_even_on_failure(variant):
    advance, solve = engine.advance, field.solve
    with pytest.raises(RuntimeError, match="interrupted"):
        with candidate.candidate(variant):
            assert engine.advance is not advance
            assert (field.solve is not solve) == (variant != "parallel")
            raise RuntimeError("interrupted")
    assert engine.advance is advance and field.solve is solve


def test_screen_does_not_accept_float_tolerance_as_exact_replay():
    before = {"energy": np.array([1.0]), "events": np.array([5], np.uint32)}
    after = {"energy": np.nextafter(before["energy"], np.inf), "events": before["events"].copy()}
    assert screen.cpu_gpu_agreement(before, after)["passed"]
    assert (
        screen.differences(before, after)["different_fields"]["energy"]["max_ulp_difference"] == 1
    )
    after["events"][0] += 1
    with pytest.raises(AssertionError):
        screen.cpu_gpu_agreement(before, after)


def physical_spec():
    path = (
        Path(__file__).resolve().parents[2] / "configs/assembly_regulated_ip3_calcium_cluster.json"
    )
    return parse_spec(json.loads(path.read_text()))


def test_wall_budget_changes_only_resource_policy_and_keeps_original():
    spec = physical_spec()
    before = spec.to_dict()
    changed = screen.with_run_budget(spec, 1200.0)
    assert spec.to_dict() == before
    expected = spec.to_dict()
    for binding in expected["pools"]:
        binding["pool"]["max_wall_seconds"] = 1200.0
    assert changed.to_dict() == expected


@pytest.mark.parametrize("variant", candidate.VARIANTS)
def test_field_wrapper_leaves_numpy_observations_bitwise_unchanged(variant):
    spec = physical_spec()
    state, layout = get_model(spec.ionic.model).initial_values(spec.ionic)
    geometry = layout._replace(
        senders=layout.face_senders,
        receivers=layout.face_receivers,
        temperature=layout.temperature[0],
    )
    concentration = np.where(
        layout.extracellular_active,
        (layout.extracellular_amount_reference + state.extracellular_amount_increment)
        / layout.extracellular_volume,
        1.0,
    )
    expected = field.solve(concentration, geometry, xp=np)._asdict()
    actual = candidate.make_field_solver(variant)(concentration, geometry, xp=np)._asdict()
    assert not screen.differences(expected, actual)["different_fields"]


def test_protected_linear_solve_preserves_distinct_worlds_and_reference_bits():
    backend = candidate._FieldBackend(scalar_sums=False)
    matrices = jnp.array(
        [[[3.0, 1.0], [2.0, 4.0]], [[0.0, 2.0], [3.0, 1.0]], [[7.0, 0.0], [0.0, 5.0]]]
    )
    rhs = jnp.array([[[5.0], [10.0]], [[4.0], [5.0]], [[14.0], [20.0]]])
    reference = jax.jit(lambda a, b: jax.lax.map(lambda pair: jnp.linalg.solve(*pair), (a, b)))(
        matrices, rhs
    )
    actual = jax.jit(jax.vmap(backend.linalg.solve))(matrices, rhs)
    assert not screen.differences(
        {"solution": np.asarray(reference)}, {"solution": np.asarray(actual)}
    )["different_fields"]
    np.testing.assert_allclose(
        np.asarray(matrices) @ np.asarray(actual), np.asarray(rhs), atol=1e-14, rtol=1e-14
    )


@pytest.mark.parametrize(
    "variants,cpu_width,gpu_width,budget",
    [
        ([], 4, 32, 1200),
        (["parallel", "parallel"], 4, 32, 1200),
        (["unknown"], 4, 32, 1200),
        (["parallel"], 0, 32, 1200),
        (["parallel"], True, 32, 1200),
        (["parallel"], 4, 33, 1200),
        (["parallel"], 4, 64, 1200),
        ([screen.ENERGY_SCREEN_VARIANT], 64, 64, 1200),
        ([screen.ENERGY_SCREEN_VARIANT], 4, 128, 1200),
        (["parallel"], 4, 32, float("inf")),
        (["parallel"], 4, 32, 0),
        (["parallel"], 4, 32, screen.PHASE_CAP + 1),
    ],
)
def test_invalid_screen_execution_settings_refused(variants, cpu_width, gpu_width, budget):
    with pytest.raises(ValueError):
        screen.screen_settings(variants, cpu_width, gpu_width, budget)


def test_wider_gpu_settings_keep_cpu_width_and_budget_explicit():
    settings = screen.screen_settings([screen.ENERGY_SCREEN_VARIANT], 4, 64, 1200)
    assert settings["tile_width_by_backend"] == {"cpu": 4, "gpu": 64}
    assert settings["run_wall_seconds"] == 1200
