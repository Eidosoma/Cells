import json
from dataclasses import replace
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.core.runner import NumericalError, branch_checkpoint, run, timeline, validate_checkpoint
from cells.core.specs import ConfigError, InputChange, load_spec, parse_spec
from cells.core.state import EMTState, initialise
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import emt_mirna
from tests.reference_emt import reference_rhs, reference_solution

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def emt_spec():
    spec = load_spec(ROOT / "configs/emt_isolated_m.json")
    return replace(
        spec, experiment=replace(spec.experiment, end_time=20, observation_times=(0, 20))
    )


@pytest.mark.parametrize("name", ["e", "m"])
def test_emt_definitions_round_trip(name):
    spec = load_spec(ROOT / f"configs/emt_isolated_{name}.json")
    assert parse_spec(spec.to_dict()) == spec
    assert len(timeline(spec)) == 100001
    assert spec.experiment.source == ()


@pytest.mark.parametrize(
    "path,value",
    [
        (("model", "units", "time"), "s"),
        (("model", "units", "concentration"), "fmol_per_pL"),
        (("model", "parameters", "parameter_set"), "iterate-true"),
        (("model", "parameters", "snail"), -1),
        (("model", "parameters", "snail"), True),
        (("model", "initial_state", "mir200_total"), -1),
        (("model", "initial_state", "zeb_mrna_total"), float("inf")),
        (("model", "initial_state", "zeb_protein"), "100"),
        (("model", "initial_state", "label"), "E"),
        (("experiment", "source", "kind"), "prescribed_external_amount_rate"),
        (("experiment", "source", "schedule"), [{"time": 0, "rate": 0}]),
    ],
)
def test_emt_strict_model_contract(emt_spec, path, value):
    data = emt_spec.to_dict()
    node = data
    for part in path[:-1]:
        node = node[part]
    node[path[-1]] = value
    with pytest.raises(ConfigError):
        parse_spec(data)


def test_emt_does_not_discard_python_api_forcing(emt_spec):
    changed = replace(
        emt_spec, experiment=replace(emt_spec.experiment, source=(InputChange(0, 0),))
    )
    with pytest.raises(ConfigError):
        run(changed)


def test_emt_step_and_memory_bounds(emt_spec):
    with pytest.raises(ConfigError, match="step <= 0.25"):
        timeline(replace(emt_spec, execution=replace(emt_spec.execution, dt=1)))
    with pytest.raises(ConfigError, match="storage"):
        timeline(replace(emt_spec, execution=replace(emt_spec.execution, max_trace_bytes=100)))


def test_emt_rhs_matches_independent_polynomial_and_is_pure(emt_spec):
    checkpoint = initialise(emt_spec)
    before = tuple(np.array(value) for value in checkpoint.state)
    actual = emt_mirna.rhs(checkpoint.state, 0, 72, checkpoint.layout.active)
    np.testing.assert_allclose(np.array(actual)[:, 0], reference_rhs(0, [0, 100, 100]), atol=2e-14)
    for original, after in zip(before, checkpoint.state, strict=True):
        np.testing.assert_array_equal(original, after)
    zero = EMTState(*(np.zeros(1) for _ in range(3)))
    at_zero = emt_mirna.rhs(zero, 0, 72, checkpoint.layout.active)
    np.testing.assert_allclose(np.array(at_zero)[:, 0], [4.2, 55 / 24, 0], atol=1e-15, rtol=0)


def test_emt_binding_partition_and_free_proxy():
    mir = np.array([0, 1, 40, 100, 1000.0])
    mrna = np.array([100, 5, 30, 20, 7.0])
    bound = emt_mirna.complexes(mir, mrna, xp=np)
    np.testing.assert_allclose(bound @ [1, 6, 15, 20, 15, 6, 1], mrna, rtol=2e-15)
    np.testing.assert_array_equal(bound[0], [100, 0, 0, 0, 0, 0, 0])
    np.testing.assert_array_equal(bound[2], np.full(7, 30 / 64))


@pytest.mark.parametrize("initial,label", [([100, 0, 0], "E"), ([0, 100, 100], "M")])
def test_emt_transient_refinement(emt_spec, initial, label):
    model = replace(
        emt_spec.model,
        initial_mir200_total=initial[0],
        initial_zeb_mrna_total=initial[1],
        initial_zeb_protein=initial[2],
    )
    spec = replace(
        emt_spec,
        model=model,
        experiment=replace(emt_spec.experiment, end_time=200, observation_times=(0, 200)),
    )
    reference = reference_solution(initial, 200)
    errors = []
    for dt in (0.2, 0.1, 0.05):
        result = run(replace(spec, execution=replace(spec.execution, dt=dt)))
        values = np.stack(result.history)[:, :, 0]
        errors.append(float(np.max(np.abs(values - reference.sol(result.times)))))
        assert result.observations.label[-1, 0] == label
        assert np.isfinite(values).all() and (values >= 0).all()
    assert errors[1] < 1e-6
    assert 12 < errors[0] / errors[1] < 20
    assert 12 < errors[1] / errors[2] < 20


def test_emt_padding_observer_independence_and_jit(emt_spec):
    spec = replace(
        emt_spec, experiment=replace(emt_spec.experiment, end_time=2, observation_times=(0, 2))
    )
    plain = run(spec)
    padded = run(replace(spec, execution=replace(spec.execution, capacity=4)))
    eager = run(replace(spec, execution=replace(spec.execution, jit=False)))
    sampled = run(
        replace(spec, experiment=replace(spec.experiment, observation_times=(0.015, 1, 2)))
    )
    for i in range(3):
        np.testing.assert_array_equal(plain.history[i], sampled.history[i])
        np.testing.assert_allclose(
            plain.history[i][:, 0], padded.history[i][:, 0], atol=3e-14, rtol=0
        )
        np.testing.assert_allclose(plain.history[i], eager.history[i], atol=3e-14, rtol=0)
        assert np.all(padded.history[i][:, 1:] == 0)
    np.testing.assert_array_equal(padded.observations.label[:, 1:], "-")
    obs = sampled.observations
    assert obs.zeb_protein[0, 0] == np.interp(
        0.015, sampled.times, sampled.history.zeb_protein[:, 0]
    )
    np.testing.assert_array_equal(obs.mir200_free_proxy, obs.mir200_total)
    np.testing.assert_array_equal(
        obs.bound_complexes, emt_mirna.complexes(obs.mir200_total, obs.zeb_mrna_total, xp=np)
    )
    assert all(value.device.platform == "cpu" for value in plain.final.state)
    assert jax.config.jax_enable_x64


@pytest.mark.parametrize("time", [0, 10, 20])
def test_emt_exact_restart_round_trip(emt_spec, tmp_path, time):
    original = run(emt_spec)
    checkpoint = original.checkpoint_at(time)
    assert checkpoint.event_index == -1
    path = write_snapshot(tmp_path / "snapshot", emt_spec, checkpoint)
    snapshot = load_snapshot(path)
    replay = run(snapshot.spec, snapshot.checkpoint)
    for first, second in zip(original.history, replay.history, strict=True):
        np.testing.assert_array_equal(first[checkpoint.step_index :], second)
    assert type(snapshot.checkpoint.state) is EMTState


def test_emt_branch_horizon_but_not_fixed_snail(emt_spec):
    original = run(emt_spec)
    cp = original.checkpoint_at(10)
    changed = replace(emt_spec, experiment=replace(emt_spec.experiment, end_time=30))
    branched = run(changed, branch_checkpoint(emt_spec, cp, changed))
    for a, b in zip(original.history, branched.history, strict=True):
        np.testing.assert_array_equal(a[100:], b[:101])
    assert original.final.time == 20
    with pytest.raises(ConfigError, match="model or execution"):
        branch_checkpoint(emt_spec, cp, replace(emt_spec, model=replace(emt_spec.model, snail=70)))


def test_emt_labels_are_observations_not_state(emt_spec, tmp_path):
    result = run(emt_spec)
    directory = tmp_path / "run"
    summary = write_run(directory, result)
    assert summary["final_label"] == "M"
    with np.load(directory / "checkpoint_final/state.npz", allow_pickle=False) as archive:
        assert set(archive.files) == set(EMTState._fields) | {"active", "ids"}
    with np.load(directory / "trajectory.npz", allow_pickle=False) as archive:
        assert "observed_label" in archive and "volume" not in archive
    with pytest.raises(ValueError):
        result.history.zeb_protein[0, 0] = 1
    result.observations.zeb_protein[-1, 0] = -100
    assert result.history.zeb_protein[-1, 0] > 0
    np.testing.assert_array_equal(
        emt_mirna.labels([2, 3, 0, 0], [0, 0, 2, 3], True), ["X", "E", "X", "M"]
    )


def test_emt_invalid_checkpoint_states_fail(emt_spec):
    initial = initialise(emt_spec)
    for bad in (float("nan"), -1):
        state = initial.state._replace(zeb_protein=np.array([bad], dtype=np.float64))
        with pytest.raises(NumericalError):
            validate_checkpoint(emt_spec, replace(initial, state=state))
    state = initial.state._replace(zeb_protein=np.array([99.0]))
    with pytest.raises(ConfigError, match="initial state"):
        validate_checkpoint(emt_spec, replace(initial, state=state))


def test_frozen_source_derivatives_and_complexes():
    fixture = json.loads((ROOT / "tests/fixtures/emt_source_probes.json").read_text())
    assert fixture["revision"] == emt_mirna.UPSTREAM_REVISION
    points = fixture["probes"]["points"]
    assert len(points) == 36
    cpu_device = initialise(
        load_spec(ROOT / "configs/emt_isolated_e.json")
    ).state.mir200_total.device
    state = EMTState(*(np.array([p["state"][i] for p in points]) for i in range(3)))
    state = jax.device_put(state, cpu_device)
    snail = np.array([p["snail"] for p in points])
    actual = emt_mirna.rhs(state, 0, snail, np.ones(len(points), dtype=bool))
    expected = np.array([p["rhs"] for p in points]).T
    np.testing.assert_allclose(np.array(actual), expected, atol=1e-11, rtol=0)
    bound = emt_mirna.complexes(state.mir200_total, state.zeb_mrna_total)
    np.testing.assert_allclose(bound, [p["bound_complexes"] for p in points], atol=1e-11, rtol=0)


@pytest.mark.parametrize("point", [[100.0, 0.0, 0.0], [0.0, 100.0, 100.0], [30.0, 20.0, 5.0]])
def test_emt_jacobian_is_finite_at_reference_starts(emt_spec, point):
    initialise(emt_spec)

    def function(values):
        state = EMTState(*(values[i : i + 1] for i in range(3)))
        return jax.numpy.stack(emt_mirna.rhs(state, 0, 72, np.array([True])))[:, 0]

    actual = jax.jacfwd(function)(np.array(point))
    assert np.isfinite(actual).all()
    columns = []
    for index in range(3):
        increment = np.eye(3)[index] * 1e-5
        columns.append(
            (
                reference_rhs(0, np.array(point) + increment)
                - reference_rhs(0, np.array(point) - increment)
            )
            / 2e-5
        )
    np.testing.assert_allclose(actual, np.array(columns).T, atol=2e-9, rtol=0)
