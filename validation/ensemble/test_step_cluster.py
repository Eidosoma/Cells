"""Saved-step coverage, exact reproduction and isolated operation protection."""

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.assembly_cluster import engine
from cells.numerics import extracellular_field as field
from validation.ensemble import step_cluster as steps


def recorded(first_by_field, *, reproduced=True):
    return {
        "trace_reproduces_prior_screen": reproduced,
        "first_divergence": {"tick": 1},
        "first_by_field": {k: {"tick": v} for k, v in first_by_field.items()},
    }


def test_witnesses_include_both_devices_later_transients_and_final_step():
    results = [recorded({"face": 1, "chemical": 59}), recorded({"outside": 1, "gate": 2})]
    assert steps.witness_ticks(results, 1600) == [1, 2, 59, 1600]


@pytest.mark.parametrize("tick", [0, 1601, True, 1.5])
def test_outside_or_noninteger_witness_refused(tick):
    with pytest.raises(ValueError, match="Invalid witness"):
        steps.witness_ticks([recorded({"bad": tick})], 1600)


def test_unreproduced_trace_and_different_initial_case_refused():
    with pytest.raises(ValueError, match="reproduced trace"):
        steps.witness_ticks([recorded({"face": 1}, reproduced=False)], 1600)
    result = recorded({"face": 2})
    result["first_divergence"]["tick"] = 2
    with pytest.raises(ValueError, match="first-step case"):
        steps.witness_ticks([result], 1600)


def test_exact_reproduction_cannot_be_replaced_by_float_tolerance():
    before = {"energy": np.array([1.0])}
    after = {"energy": np.nextafter(before["energy"], np.inf)}
    np.testing.assert_allclose(before["energy"], after["energy"])
    with pytest.raises(ValueError, match="not reproduced"):
        steps.require_reproduction(steps.rounding.differences(before, after), "saved tick")


def test_witness_arrays_are_independent_and_clock_is_verified():
    trace = {"tick": np.array([[0, 0], [1, 1]], np.uint32), "energy": np.ones((2, 2))}
    saved = steps.state_at(trace, 1)
    saved["energy"][0] = 99
    assert trace["energy"][1, 0] == 1
    trace["tick"][1, 1] = 2
    with pytest.raises(ValueError, match="Trace tick"):
        steps.state_at(trace, 1)


@pytest.mark.parametrize("name", steps.EXPERIMENTS)
def test_experiments_restore_functions_and_preserve_host_logmean_on_error(name):
    advance, solve, logmean = engine.advance, field.solve, field.logmean
    left, right = np.array([1.0, 2.0, 0.1]), np.array([1.0, 2.000001, 10.0])
    expected = logmean(left, right, xp=np)
    with pytest.raises(RuntimeError, match="interrupt"):
        with steps.experiment(name, 4):
            assert engine.advance is not advance
            actual = field.logmean(left, right, xp=np)
            for a, b in zip(actual, expected, strict=True):
                assert a.tobytes() == b.tobytes()
            raise RuntimeError("interrupt")
    assert (engine.advance, field.solve, field.logmean) == (advance, solve, logmean)


def test_protected_logmean_handles_distinct_worlds_and_all_numerical_branches():
    left = jnp.array([[1.0, 2.0, 0.1], [3.0, 1.0, 40.0], [0.25, 5.0, 7.0]])
    right = jnp.array([[1.0, 2.000001, 10.0], [3.00001, 4.0, 0.2], [0.25, 5.0001, 3.0]])
    original = field.logmean
    expected = jax.jit(lambda a, b: jax.lax.map(lambda pair: original(*pair), (a, b)))(left, right)
    with steps.experiment("parallel_scalar_linear_logmean", 4):
        actual = jax.jit(jax.vmap(field.logmean))(left, right)
    for a, b in zip(actual, expected, strict=True):
        assert np.asarray(a).tobytes() == np.asarray(b).tobytes()


def test_compiler_capture_preserves_executable_results_and_first_ir(tmp_path):
    @jax.jit
    def advance(x):
        return x + jnp.sin(x)

    x = jnp.array([1.0, 2.0, 3.0])
    capture = steps.CompilerCapture(advance, tmp_path)
    first = capture.lower(x).compile()
    expected = advance.lower(x).compile()(x)
    assert np.asarray(first(x)).tobytes() == np.asarray(expected).tobytes()
    ir = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert set(ir) == {"lowered.mlir", "optimized.hlo"} and all(ir.values())
    second = capture.lower(x + 1).compile()
    assert np.asarray(second(x + 1)).tobytes() == np.asarray(advance(x + 1)).tobytes()
    assert ir == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
