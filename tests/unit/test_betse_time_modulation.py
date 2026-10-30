"""Pinned time modulation, independent Decimal phases and CPU array compilation."""

import json
import os
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.processes import betse_time_modulation as modulation
from validation.perturbations import time_modulation_native as native
from validation.perturbations import time_modulation_reference as reference

CASES = (
    ("periodic-zero", "periodic", dict(frequency_Hz=0.0, phase_rad=0.0)),
    ("periodic-phase", "periodic", dict(frequency_Hz=0.0, phase_rad=0.37)),
    ("periodic-basic", "periodic", dict(frequency_Hz=1.0, phase_rad=0.0)),
    ("periodic-signed", "periodic", dict(frequency_Hz=-3.75, phase_rad=-0.25)),
    ("periodic-fast", "periodic", dict(frequency_Hz=123.75, phase_rad=0.71)),
    ("sweep-fixed", "sweep", dict(start_Hz=2.0, slope_Hz_s=0.0)),
    ("sweep-up", "sweep", dict(start_Hz=0.125, slope_Hz_s=1.375)),
    ("sweep-down", "sweep", dict(start_Hz=3.0, slope_Hz_s=-2.0)),
    ("sweep-auto", "sweep", dict(start_Hz=0.2, stop_Hz=0.8, original_duration_s=0.3)),
    ("sweep-auto-down", "sweep", dict(start_Hz=2.75, stop_Hz=-0.25, original_duration_s=1.7)),
)
TIMES = np.asarray([-0.125, 0.0, 1e-12, 0.125, 0.25, 0.5, 0.75, 1.0, 1.7], dtype=np.float64)


def program(kind, parameters):
    return getattr(modulation, kind + "_program")(
        **parameters, provenance="Explicit synthetic comparison to pinned BETSE modulation"
    )


def evidence(name, payload):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        folder = Path(directory) / "time-modulation"
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / (name + ".json")).open("x") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")


def compare(actual, expected):
    assert np.asarray(actual.finite).all()
    assert np.all((np.asarray(actual.factor) >= 0) & (np.asarray(actual.factor) <= 1))
    phase = np.array([row["phase_rad"] for row in expected])
    value = np.array([row["factor"] for row in expected])
    phase_budget = np.array([row["phase_budget_rad"] for row in expected])
    factor_budget = np.array([row["factor_budget"] for row in expected])
    errors = dict(
        phase=float(np.max(abs(np.asarray(actual.phase_rad) - phase) / phase_budget)),
        factor=float(np.max(abs(np.asarray(actual.factor) - value) / factor_budget)),
    )
    assert max(errors.values()) <= 1, errors
    return errors


@pytest.mark.parametrize("name,kind,parameters", CASES)
def test_numpy_source_arithmetic_and_independent_trigonometry(name, kind, parameters):
    prepared = program(kind, parameters)
    saved = modulation.record(prepared)
    actual = modulation.evaluate(prepared, TIMES, xp=np)
    source = native.evaluate(saved, TIMES)
    np.testing.assert_array_equal(actual.factor, source["factor"])
    assert source["scalar"] == 1
    if kind == "sweep":
        assert source["resolved_slope_Hz_s"] == prepared.slope_Hz_s
        assert reference.resolved_slope(saved) == prepared.slope_Hz_s
    wanted = reference.evaluate(saved, TIMES.tolist())
    errors = compare(actual, wanted)
    evidence(
        name,
        dict(
            parameters=saved,
            times=TIMES.tolist(),
            reference=wanted,
            source=dict(
                factor=source["factor"].tolist(),
                scalar=source["scalar"],
                resolved_slope_Hz_s=source["resolved_slope_Hz_s"],
                source_sha256=native.PINNED,
            ),
            actual={key: value.tolist() for key, value in actual._asdict().items()},
            error_fractions=errors,
            biological_cases=0,
        ),
    )


def test_source_sweep_setup_failure_is_retained_as_an_explicit_refusal():
    source = native.capture()
    parameters = SimpleNamespace(
        _run_sim=False,
        sim_time_total=1.0,
        f_scan_properties={"f start": 1.0, "f stop": 2.0, "f slope": None},
    )
    _, dynamic = source["f_sweep"](None, None, parameters)
    with pytest.raises(TypeError):
        dynamic(0.1)
    with pytest.raises(ValueError, match="unresolved"):
        modulation.sweep_program(
            start_Hz=1.0,
            stop_Hz=2.0,
            original_duration_s=1.0,
            run_sim=False,
            provenance="Retain undefined native INIT slope",
        )
    evidence(
        "native-init-refusal",
        dict(
            native_setup_leaves_slope_none=True,
            native_call_failure="TypeError",
            cells_bind_failure="ValueError",
            source_sha256=native.PINNED,
            scope="Explicit automatic slope outside native SIM",
        ),
    )


def test_original_sweep_duration_is_not_rebased_on_resume():
    prepared = modulation.sweep_program(
        start_Hz=0.25, stop_Hz=2.5, original_duration_s=2.0, provenance="Original complete sweep"
    )
    saved = json.loads(json.dumps(modulation.record(prepared)))
    restored = modulation.restore(saved, expected_identity=prepared.identity)
    full = modulation.evaluate(prepared, TIMES, xp=np)
    tail = modulation.evaluate(restored, TIMES[5:], xp=np)
    for original, resumed in zip(full, tail, strict=True):
        np.testing.assert_array_equal(original[5:], resumed)
    rebased = modulation.sweep_program(
        start_Hz=0.25, stop_Hz=2.5, original_duration_s=1.0, provenance=prepared.provenance
    )
    with pytest.raises(ValueError):
        modulation.restore(modulation.record(rebased), expected_identity=prepared.identity)
    assert not np.array_equal(modulation.evaluate(rebased, TIMES, xp=np).factor, full.factor)


@pytest.mark.parametrize("defect", ("coefficient", "duration", "kind", "seal", "extra", "missing"))
def test_saved_program_retains_complete_coefficient_association(defect):
    prepared = modulation.sweep_program(
        start_Hz=0.25, stop_Hz=2.5, original_duration_s=2.0, provenance="Declared sweep"
    )
    saved = modulation.record(prepared)
    if defect == "coefficient":
        changed = replace(prepared, slope_Hz_s=3.0)
        saved = modulation.record(changed)
    elif defect == "duration":
        saved["original_duration_s"] = 1.0
    elif defect == "kind":
        saved["kind"] = "chirp"
    elif defect == "seal":
        saved["identity"] = "0" * 64
    elif defect == "extra":
        saved["clock"] = "implicit"
    else:
        saved.pop("frequency_Hz")
    with pytest.raises(ValueError):
        modulation.restore(saved, expected_identity=prepared.identity)


@pytest.mark.parametrize("bad", (True, float("nan"), float("inf"), "1.0"))
def test_program_rejects_nonfinite_or_implicit_coefficients(bad):
    with pytest.raises(ValueError):
        modulation.periodic_program(frequency_Hz=bad, phase_rad=0.0, provenance="Invalid")


@pytest.mark.parametrize(
    "parameters",
    (
        dict(start_Hz=1.0, stop_Hz=2.0, original_duration_s=0.0),
        dict(start_Hz=1.0, stop_Hz=2.0, original_duration_s=-1.0),
        dict(start_Hz=-1e308, stop_Hz=1e308, original_duration_s=1.0),
        dict(start_Hz=1.0, slope_Hz_s=0.5, stop_Hz=2.0),
        dict(start_Hz=1.0, slope_Hz_s=0.5, run_sim=1),
    ),
)
def test_sweep_refuses_undefined_or_ambiguous_setup(parameters):
    with pytest.raises(ValueError):
        modulation.sweep_program(**parameters, provenance="Invalid sweep")


@pytest.mark.parametrize("dtype", (np.float32, np.int64, np.bool_))
def test_kernel_requires_explicit_double_precision(dtype):
    with pytest.raises(ValueError):
        modulation.periodic(np.ones(3, dtype=dtype), 1.0, 0.0, xp=np)


@pytest.mark.parametrize("kind", ("periodic", "sweep"))
def test_array_shapes_empty_owners_and_nonfinite_arithmetic(kind):
    kernel = getattr(modulation, kind)
    arrays = kernel(np.zeros((2, 0), dtype=np.float64), 1.0, 0.5, xp=np)
    assert all(value.shape == (2, 0) for value in arrays)
    with pytest.raises(ValueError):
        kernel(np.ones((2, 3)), np.ones(4), 0.5, xp=np)
    with np.errstate(over="ignore", invalid="ignore"):
        bad = kernel(np.asarray([np.nan, np.inf, 1e308]), 1e308, 1e308, xp=np)
    assert not bad.finite.any()
    # A finite mathematical rearrangement must not hide source overflow.
    with np.errstate(over="ignore", invalid="ignore"):
        if kind == "periodic":
            zero = kernel(np.asarray([1e308]), 0.0, 0.0, xp=np)
        else:
            zero = kernel(np.asarray([0.0]), 1e308, 0.0, xp=np)
    assert not zero.finite.any()


@pytest.mark.parametrize("kind", ("periodic", "sweep"))
def test_cpu_jax_compiled_two_world_batch_and_staged_program(kind):
    assert jax.config.x64_enabled and jax.default_backend() == "cpu"
    kernel = getattr(modulation, kind)
    coefficients = np.array([[1.375, 0.27], [-0.75, -0.25]], dtype=np.float64)
    fn = jax.jit(jax.vmap(lambda pair: kernel(jnp.asarray(TIMES), pair[0], pair[1], xp=jnp)))
    result = jax.device_get(fn(jnp.asarray(coefficients)))
    rows = []
    for index, (a, b) in enumerate(coefficients):
        params = (
            dict(frequency_Hz=a, phase_rad=b)
            if kind == "periodic"
            else dict(start_Hz=a, slope_Hz_s=b)
        )
        prepared = program(kind, params)
        wanted = reference.evaluate(modulation.record(prepared), TIMES.tolist())
        actual = modulation.Values(*(value[index] for value in result))
        rows.append(
            dict(
                parameters=modulation.record(prepared),
                reference=wanted,
                actual={name: value.tolist() for name, value in actual._asdict().items()},
                error_fractions=compare(actual, wanted),
            )
        )
    prepared = program(
        kind,
        dict(frequency_Hz=1.375, phase_rad=0.27)
        if kind == "periodic"
        else dict(start_Hz=1.375, slope_Hz_s=0.27),
    )
    staged = jax.jit(lambda t: modulation.evaluate(prepared, t, xp=jnp))(jnp.asarray(TIMES))
    np.testing.assert_allclose(jax.device_get(staged.factor), result.factor[0], rtol=0, atol=2e-14)
    evidence(
        "cpu-jax-" + kind,
        dict(
            times=TIMES.tolist(),
            worlds=rows,
            backend="cpu",
            compiled=True,
            vmap_worlds=2,
            gpu_qualified=False,
        ),
    )


@pytest.mark.parametrize("kind", ("periodic", "sweep"))
def test_cpu_jax_empty_and_invalid_domains(kind):
    assert jax.config.x64_enabled and jax.default_backend() == "cpu"
    kernel = getattr(modulation, kind)
    fn = jax.jit(lambda t, a, b: kernel(t, a, b, xp=jnp))
    empty = fn(jnp.empty((2, 0), dtype=jnp.float64), jnp.asarray(1.0), jnp.asarray(0.5))
    assert empty.factor.shape == (2, 0)
    bad = fn(jnp.asarray([np.nan, np.inf, 1e308]), jnp.asarray(1e308), jnp.asarray(1e308))
    assert not np.asarray(bad.finite).any()
    time, a = (1e308, 0.0) if kind == "periodic" else (0.0, 1e308)
    overflow = fn(jnp.asarray([time]), jnp.asarray(a), jnp.asarray(0.0))
    assert not np.asarray(overflow.finite).any()
