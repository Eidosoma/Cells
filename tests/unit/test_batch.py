"""World isolation, clocks, guard semantics, resources and complete replay."""

import copy
from dataclasses import replace

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.batch_io import load_batch_snapshot, write_batch_run, write_batch_snapshot
from cells.core import batch
from cells.core.batch import branch_batch_checkpoints, parse_batch, plan_batch, run_batch
from cells.core.errors import NumericalError
from cells.core.runner import run
from cells.core.specs import ConfigError, InputChange, parse_spec
from cells.core.state import CellState, initialise
from cells.io import _write_json, load_snapshot
from tests.batch_fixtures import MODELS, assert_parity, definition, short_spec, synthetic_pair


@pytest.mark.parametrize("name", MODELS)
def test_all_families_match_scalar_with_independent_clocks(name):
    specs = [short_spec(name, end) for end in (0.3, 0.5)]
    result = run_batch(definition(specs))
    assert result.resources["padded_step_slots"] > result.resources["executed_world_steps"]
    for world in result.spec.worlds:
        assert_parity(result.worlds[world.world_id], run(world.simulation))
    assert parse_batch(result.spec.to_dict()) == result.spec


def test_parameters_controls_ids_and_order_do_not_cross_worlds():
    spec = synthetic_pair()
    result = run_batch(spec)
    assert 0.173 not in result.worlds[10].times and 0.137 not in result.worlds[11].times
    reverse = run_batch(replace(spec, worlds=tuple(reversed(spec.worlds))))
    renamed = run_batch(
        replace(spec, worlds=tuple(replace(w, world_id=w.world_id + 50) for w in spec.worlds))
    )
    for world in spec.worlds:
        assert_parity(result.worlds[world.world_id], run(world.simulation), exact=True)
        assert_parity(result.worlds[world.world_id], reverse.worlds[world.world_id], exact=True)
        assert_parity(
            result.worlds[world.world_id], renamed.worlds[world.world_id + 50], exact=True
        )
    changed = spec.worlds[0].simulation.to_dict()
    changed["model"]["initial_state"]["amount"] = 20
    altered = run_batch(
        replace(
            spec, worlds=(replace(spec.worlds[0], simulation=parse_spec(changed)), spec.worlds[1])
        )
    )
    assert_parity(result.worlds[11], altered.worlds[11], exact=True)
    assert not np.array_equal(result.worlds[10].history.amount, altered.worlds[10].history.amount)


@pytest.mark.parametrize("name", MODELS)
def test_snapshot_ragged_replay_and_final_only(tmp_path, name):
    spec = definition([short_spec(name, 0.3), short_spec(name, 0.5)])
    result = run_batch(spec)
    # Different clock positions, one already finished. Neither resets history.
    checkpoints = result.checkpoint_at({10: float(result.worlds[10].times[2]), 11: 0.5})
    write_batch_snapshot(tmp_path / "saved", spec, checkpoints)
    saved = load_batch_snapshot(tmp_path / "saved")
    resumed = run_batch(saved.spec, saved.checkpoints)
    for identity in result.worlds:
        expected = run(saved.spec.worlds[identity - 10].simulation, saved.checkpoints[identity])
        assert_parity(resumed.worlds[identity], expected)
        original = result.worlds[identity]
        start = np.flatnonzero(original.times == checkpoints[identity].time)[0]
        for got, want in zip(resumed.worlds[identity].history, original.history, strict=True):
            np.testing.assert_array_equal(got, want[start:])
    finals = result.checkpoint_at({10: 0.3, 11: 0.5})
    empty = run_batch(spec, finals)
    assert empty.resources["executed_world_steps"] == 0
    for identity in empty.worlds:
        assert len(empty.worlds[identity].times) == 1
        np.testing.assert_array_equal(
            empty.worlds[identity].history[0][0], finals[identity].state[0]
        )
    scalar_saved = load_snapshot(tmp_path / "saved/world-10")
    assert scalar_saved.spec == spec.worlds[0].simulation


def test_future_branch_reordering_and_per_world_ordinary_semantics(tmp_path):
    spec = synthetic_pair()
    result = run_batch(spec)
    checkpoints = result.checkpoint_at(0.5)
    first = spec.worlds[0].simulation
    changed = replace(
        first,
        experiment=replace(
            first.experiment, source=first.experiment.source + (InputChange(0.5, 0),)
        ),
    )
    branch = replace(spec, worlds=(spec.worlds[1], replace(spec.worlds[0], simulation=changed)))
    carry = branch_batch_checkpoints(spec, checkpoints, branch)
    future = run_batch(branch, carry)
    expected = run(changed, carry[10])
    assert_parity(future.worlds[10], expected, exact=True)
    assert_parity(future.worlds[11], run(spec.worlds[1].simulation, carry[11]), exact=True)
    write_batch_run(tmp_path / "branch", future)
    saved = load_batch_snapshot(tmp_path / "branch/checkpoint_final")
    assert list(saved.checkpoints) == [11, 10]
    with pytest.raises(ConfigError, match="execution"):
        branch_batch_checkpoints(spec, checkpoints, replace(spec, max_worlds=63))
    with pytest.raises(ConfigError, match="world IDs"):
        branch_batch_checkpoints(spec, checkpoints, replace(spec, worlds=spec.worlds[:1]))
    wrong = replace(first, model=replace(first.model, decay_rate=0.8))
    with pytest.raises(ConfigError, match="World 10.*model"):
        branch_batch_checkpoints(
            spec,
            checkpoints,
            replace(spec, worlds=(replace(spec.worlds[0], simulation=wrong), spec.worlds[1])),
        )
    wrong = replace(first, experiment=replace(first.experiment, source=(InputChange(0, 3),)))
    with pytest.raises(ConfigError, match="World 10.*before"):
        branch_batch_checkpoints(
            spec,
            checkpoints,
            replace(spec, worlds=(replace(spec.worlds[0], simulation=wrong), spec.worlds[1])),
        )


@pytest.mark.parametrize(
    "name",
    [
        "single_cell_pulse",
        "reaction_transport_chain",
        "source_pair_controls",
        "bioelectric_pair_baseline",
    ],
)
def test_eager_and_jit_and_cell_edge_padding(name):
    s = short_spec(name, 0.003)
    a = run_batch(definition([s, s]))
    eager = replace(s, execution=replace(s.execution, jit=False))
    b = run_batch(definition([eager, eager]))
    assert_parity(a.worlds[10], b.worlds[10])
    padded = replace(
        s,
        execution=replace(
            s.execution,
            capacity=s.execution.capacity + 2,
            edge_capacity=s.execution.edge_capacity + 2 if s.execution.edge_capacity else 0,
            membrane_capacity=s.execution.membrane_capacity + 2
            if s.execution.membrane_capacity
            else 0,
        ),
    )
    result = run_batch(definition([padded, padded]))
    assert_parity(result.worlds[10], run(padded))


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema_version",), True),
        (("schema_version",), 2),
        (("kind",), "organs"),
        (("worlds",), []),
        (("execution", "max_worlds"), 0),
        (("execution", "max_worlds"), 1),
        (("execution", "max_worlds"), 4097),
        (("execution", "max_padded_steps"), True),
        (("execution", "max_working_bytes"), float("inf")),
        (("execution", "mapping"), "vmap"),
        (("worlds", 0, "world_id"), True),
        (("worlds", 0, "world_id"), -1),
        (("worlds", 0, "world_id"), 11),
        (("worlds", 1, "simulation", "execution", "capacity"), 2),
        (("worlds", 1, "simulation", "execution", "jit"), False),
    ],
)
def test_invalid_definition(path, value):
    data = synthetic_pair().to_dict()
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ConfigError):
        parse_batch(data)


def test_mixed_family_and_unknown_fields_refused():
    data = definition([short_spec(MODELS[0]), short_spec(MODELS[1])]).to_dict()
    with pytest.raises(ConfigError, match="family"):
        parse_batch(data)
    data = synthetic_pair().to_dict()
    data["worlds"][0]["exchange"] = {}
    with pytest.raises(ConfigError, match="unknown"):
        parse_batch(data)


@pytest.mark.parametrize("setting,value", [("max_working_bytes", 1), ("max_padded_steps", 1)])
def test_aggregate_guards_before_timelines_or_capacity_allocation(monkeypatch, setting, value):
    def forbidden(*args, **kwargs):
        pytest.fail("Resource refusal must precede timeline/capacity allocation")

    monkeypatch.setattr(batch, "timeline", forbidden)
    monkeypatch.setattr(batch, "initialise", forbidden)
    with pytest.raises(ConfigError, match=setting):
        run_batch(replace(synthetic_pair(), **{setting: value}))


def test_shape_work_budget_and_invalid_continuation():
    spec = synthetic_pair()
    s = spec.worlds[0].simulation
    enormous = replace(s, execution=replace(s.execution, capacity=10**8))
    with pytest.raises(ConfigError, match="max_working_bytes"):
        plan_batch(definition([enormous]))
    with pytest.raises(ConfigError, match="max_steps"):
        plan_batch(definition([replace(s, execution=replace(s.execution, dt=1e-20))]))
    with pytest.raises(ConfigError, match="world IDs"):
        run_batch(spec, {10: initialise(s)})
    for n in (0, True, 11):
        with pytest.raises(ConfigError, match="timing_repeats"):
            run_batch(spec, timing_repeats=n)


def test_guarded_map_never_evaluates_invalid_or_completed_world_rhs():
    # A log would raise under debug_nans if a rejected RK stage were evaluated.
    def rhs(state, control, parameters, active):
        slope = -parameters + jnp.log(state.amount)
        return CellState(slope, jnp.zeros_like(slope), jnp.zeros_like(slope))

    def domain(state, parameters, active):
        return jnp.all(state.amount > 0)

    states = CellState(jnp.ones((3, 1)), jnp.zeros((3, 1)), jnp.zeros((3, 1)))
    inputs = (
        states,
        jnp.ones((3, 2)),
        jnp.zeros((3, 2)),
        jnp.array([10.0, 0.0, jnp.nan]),
        jnp.ones((3, 1), dtype=bool),
        jnp.array([2, 2, 0]),
    )
    with jax.debug_nans(True):
        final, history, ok = batch._compiled_batch(inputs, rhs, domain)
        jax.block_until_ready((final, history, ok))
    np.testing.assert_array_equal(ok, [[False, False], [True, True], [True, True]])
    np.testing.assert_array_equal(final.amount, [[1], [1], [1]])


def test_batch_failure_names_world_and_never_returns_partial_results(monkeypatch):
    from cells.models import source_decay

    original = source_decay.rhs

    def bad_rhs(state, control, parameters, active):
        result = original(state, control, parameters, active)
        return result._replace(amount=jnp.where(parameters > 0.5, jnp.inf, result.amount))

    monkeypatch.setattr(source_decay, "rhs", bad_rhs)
    with pytest.raises(NumericalError, match="World 11.*batch refused"):
        run_batch(synthetic_pair())


def test_observation_requests_and_timing_repetitions_do_not_advance_biology():
    spec = synthetic_pair()
    base = run_batch(spec)
    profiled = run_batch(spec, timing_repeats=3)
    for identity in base.worlds:
        assert_parity(base.worlds[identity], profiled.worlds[identity], exact=True)
    assert len(profiled.timings["execute_samples_seconds"]) == 3
    assert profiled.timings["untimed_warmup_seconds"] > 0
    changed = replace(
        spec,
        worlds=tuple(
            replace(
                w,
                simulation=replace(
                    w.simulation,
                    experiment=replace(
                        w.simulation.experiment,
                        observation_times=(w.simulation.experiment.end_time,),
                    ),
                ),
            )
            for w in spec.worlds
        ),
    )
    sampled = run_batch(changed)
    for identity in base.worlds:
        for a, b in zip(
            base.worlds[identity].history, sampled.worlds[identity].history, strict=True
        ):
            np.testing.assert_array_equal(a, b)


def test_snapshot_checksums_world_mapping_and_output_refusal(tmp_path):
    import json

    from cells.core.specs import digest

    result = run_batch(synthetic_pair())
    with pytest.raises(ConfigError, match="accepted time"):
        write_batch_run(tmp_path / "bad", result, checkpoint_times=(0.137,))
    assert not (tmp_path / "bad").exists()
    write_batch_run(tmp_path / "run", result, checkpoint_times=(0.5,))
    with pytest.raises(FileExistsError):
        write_batch_run(tmp_path / "run", result)
    path = tmp_path / "run/snapshots/checkpoint-000000"
    manifest = json.loads((path / "manifest.json").read_text())
    for change in ("digest", "world", "path", "runtime", "source", "spec"):
        broken = tmp_path / change
        broken.mkdir()
        data = copy.deepcopy(manifest)
        if change == "digest":
            data["manifest_sha256"] = "wrong"
        else:
            if change == "world":
                data["worlds"][0]["world_id"] = 11
            elif change == "path":
                data["worlds"][0]["path"] = "../outside"
            elif change == "runtime":
                data["runtime"]["cells_version"] = "0.0.0"
            elif change == "source":
                data["source_hashes"] = {}
            else:
                data["spec_sha256"] = "wrong"
            data.pop("manifest_sha256")
            data["manifest_sha256"] = digest(data)
        _write_json(broken / "manifest.json", data)
        with pytest.raises(ConfigError):
            load_batch_snapshot(broken)
    state_path = path / "world-10/state.npz"
    with state_path.open("ab") as handle:
        handle.write(b"corrupted test fixture")
    with pytest.raises(ConfigError, match="state checksum"):
        load_batch_snapshot(path)
