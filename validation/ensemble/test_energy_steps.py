"""Saved energy witnesses, unmodified equations and preserved RK4 refusal checks."""

import copy

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.assembly_cluster import engine, kernel
from cells.core.schedule import control_values
from cells.models import finite_extracellular as finite
from cells.models import multispecies_membrane as membrane
from cells.models.registry import get_model
from validation.ensemble import step_cluster as steps
from validation.ensemble.test_parallel_cluster import physical_spec


def energy_traces():
    reference = {
        "tick": np.broadcast_to(np.arange(9, dtype=np.uint32)[:, None], (9, 4)).copy(),
        "ionic_dissipated_energy_pJ": np.ones((9, 4, 2)),
        "ionic_amount_increment": np.zeros((9, 4, 3, 2)),
    }
    changed = copy.deepcopy(reference)
    energy = changed["ionic_dissipated_energy_pJ"]
    energy[2, 3, 1] = np.nextafter(1.0, np.inf)
    energy[4, 0, 0] = np.nextafter(np.nextafter(1.0, np.inf), np.inf)
    energy[6:8, 1, 0] = np.nextafter(1.0, np.inf)
    return reference, changed


def test_energy_witnesses_cover_each_world_maximum_error_and_recovery():
    reference, changed = energy_traces()
    result = steps.energy_witnesses(reference, changed)
    assert result["first_different_tick_by_world_offset"] == {"0": 4, "1": 6, "3": 2}
    assert result["witness_ticks"] == [1, 2, 4, 6, 7, 8]
    assert result["first_maximum_ulp_tick"] == 4
    assert result["last_changed_tick"] == 7
    row = result["complete_trace_comparison"]["different_fields"]["ionic_dissipated_energy_pJ"]
    assert row["max_ulp_difference"] == 2 and row["different_scalars"] == 4


def test_signed_zero_does_not_displace_largest_ulp_witness():
    reference, changed = energy_traces()
    reference["ionic_dissipated_energy_pJ"][1, 2, 0] = 0.0
    changed["ionic_dissipated_energy_pJ"][1, 2, 0] = -0.0
    assert steps.energy_witnesses(reference, changed)["first_maximum_ulp_tick"] == 4


@pytest.mark.parametrize("bad", ["matched", "other_field", "initial", "final", "clock", "negative"])
def test_energy_witnesses_refuse_inconsistent_or_different_failure(bad):
    reference, changed = energy_traces()
    energy = "ionic_dissipated_energy_pJ"
    if bad == "matched":
        changed = copy.deepcopy(reference)
    elif bad == "other_field":
        changed["ionic_amount_increment"][2, 0, 0, 0] = 1e-20
    elif bad in ("initial", "final"):
        changed[energy][0 if bad == "initial" else -1, 0, 0] = np.nextafter(1.0, np.inf)
    elif bad == "clock":
        reference["tick"][3, 0] = changed["tick"][3, 0] = 7
    else:
        reference[energy][3, 0, 0] = changed[energy][3, 0, 0] = -1
    with pytest.raises(ValueError):
        steps.energy_witnesses(reference, changed)


@pytest.mark.parametrize("name", steps.ENERGY_EXPERIMENTS)
def test_energy_experiments_restore_functions_and_leave_numpy_rhs_exact(name):
    spec = physical_spec()
    model = get_model(spec.ionic.model)
    state, layout = model.initial_values(spec.ionic)
    controls = control_values(spec.ionic, [0.0])
    control = type(controls)(*(v[0] for v in controls))
    expected = model.rhs(state, control, layout, layout.active, xp=np)
    original = (
        engine.advance,
        finite.assemble_rhs,
        membrane.dissipation_rate,
        kernel.rk4_checked_step,
    )
    with pytest.raises(RuntimeError, match="deliberate"):
        with steps.energy_experiment(name, 32):
            actual = model.rhs(state, control, layout, layout.active, xp=np)
            assert not steps.rounding.differences(expected._asdict(), actual._asdict())[
                "different_fields"
            ]
            raise RuntimeError("deliberate interruption")
    assert original == (
        engine.advance,
        finite.assemble_rhs,
        membrane.dissipation_rate,
        kernel.rk4_checked_step,
    )


def test_protected_membrane_rate_preserves_distinct_worlds_and_scalar_bits():
    args = (
        jnp.arange(1.0, 25.0).reshape(3, 4, 2) / 7,
        jnp.arange(1.0, 7.0).reshape(3, 2) / 3,
        -jnp.arange(1.0, 25.0).reshape(3, 4, 2) / 11,
        -jnp.arange(1.0, 7.0).reshape(3, 2) / 13,
    )
    original = membrane.dissipation_rate
    expected = jax.jit(lambda values: jax.lax.map(lambda row: original(*row), values))(args)
    with steps.energy_experiment("parallel_scalar_membrane_rate", 32):
        actual = jax.jit(jax.vmap(membrane.dissipation_rate))(*args)
    assert not steps.rounding.differences(
        {"rate": np.asarray(expected)}, {"rate": np.asarray(actual)}
    )["different_fields"]


def test_protected_energy_component_accepts_complete_batched_spatial_calcium_rhs():
    spec = physical_spec()
    model = get_model(spec.ionic.model)
    state, layout = model.initial_values(spec.ionic)
    controls = control_values(spec.ionic, [0.0])
    control = type(controls)(*(v[0] for v in controls))
    packed = jax.tree.map(lambda v: np.stack([v, v, v]), state)
    with steps.energy_experiment("parallel_scalar_membrane_energy", 32):
        shape = jax.eval_shape(
            jax.vmap(lambda s: model.rhs(s, control, layout, layout.active)), packed
        )
    assert type(shape) is type(state)
    for actual, expected in zip(shape, packed, strict=True):
        assert actual.shape == expected.shape and actual.dtype == expected.dtype


def test_protected_rk4_preserves_complete_update_and_trial_refusal():
    original = kernel.rk4_checked_step

    def rhs(y, control, parameters, active):
        return control - parameters * y

    def valid(y, parameters, active):
        return jnp.all(jnp.isfinite(y) & (y >= 0))

    args = (
        jnp.array([[1.0, 2.0], [0.1, 0.2]]),
        jnp.array([0.01, 1.0]),
        jnp.array([0.5, -100.0]),
        jnp.array([0.2, 0.4]),
    )
    expected = jax.jit(
        lambda values: jax.lax.map(lambda row: original(rhs, valid, *row, True), values)
    )(args)
    with steps.energy_experiment("parallel_scalar_rk4", 32):
        actual = jax.jit(
            jax.vmap(lambda s, h, c, p: kernel.rk4_checked_step(rhs, valid, s, h, c, p, True))
        )(*args)
    for left, right in zip(expected, actual, strict=True):
        assert np.asarray(left).tobytes() == np.asarray(right).tobytes()
    np.testing.assert_array_equal(actual[1], [True, False])
    np.testing.assert_array_equal(actual[0][1], args[0][1])
