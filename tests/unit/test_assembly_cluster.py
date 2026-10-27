"""Cell ownership, union clocks, independent references and complete cluster replay."""

import copy
import importlib.util
import json
import os
from dataclasses import replace
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.assembly.engine import device_for
from cells.assembly.io import write_json
from cells.assembly.kernel import random_pair
from cells.assembly.spec import AssemblyError
from cells.assembly_cell.io import flatten, load_checkpoint, write_checkpoint
from cells.assembly_cluster import engine
from cells.assembly_cluster.spec import channel_owners, parse_spec
from cells.assembly_pool import engine as pool_engine
from cells.assembly_pool import reference as pool_reference
from cells.core.errors import NumericalError
from cells.ensemble.families import bind_definition, first_completion, runtime_for
from cells.ensemble.plan import balance, jupiter_plan, plan

ROOT = Path(__file__).resolve().parents[2]
BACKEND = os.environ.get("CELLS_COUPLED_TEST_BACKEND", "cpu")
EVIDENCE = os.environ.get("CELLS_CLUSTER_EVIDENCE")


def raw_for(*, worlds=2, dt=0.00005):
    raw = json.loads((ROOT / "configs/assembly_regulated_cluster.json").read_text())
    for binding in raw["pools"]:
        binding["pool"]["worlds"] = worlds
    raw["ionic"]["execution"]["dt"] = dt
    return raw


def oracle():
    path = ROOT / "validation/assembly/cluster_reference.py"
    spec = importlib.util.spec_from_file_location("cluster_reference", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evidence(name, result, state=None):
    if EVIDENCE:
        directory = Path(EVIDENCE) / BACKEND
        directory.mkdir(parents=True, exist_ok=True)
        write_json(directory / (name + ".json"), result)
        if state is not None:
            np.savez_compressed(directory / (name + ".npz"), **flatten(state))


def same(a, b):
    right = flatten(b)
    for key, value in flatten(a).items():
        assert value.tobytes() == right[key].tobytes(), key


def test_partition_evidence_counts_all_changed_fields_and_last_bits():
    path = ROOT / "validation/assembly/cluster_partition_replay.py"
    spec = importlib.util.spec_from_file_location("partition_replay", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    left = {
        "energy": np.array([1.0, -1.0, np.inf, 0.0]),
        "events": np.array([2, 3], np.uint32),
        "unchanged": np.array([True]),
    }
    right = {k: v.copy() for k, v in left.items()}
    right["energy"][:2] = np.nextafter(left["energy"][:2], np.inf)
    right["energy"][3] = -0.0
    right["events"][1] = 4
    compared = module.differences(left, right)
    assert compared["compared_scalars"] == 7
    assert set(compared["different_fields"]) == {"energy", "events"}
    assert compared["different_fields"]["energy"]["different_scalars"] == 3
    assert compared["different_fields"]["energy"]["max_ulp_difference"] == 1
    assert compared["different_fields"]["energy"]["max_absolute_difference"] == np.spacing(1.0)
    assert compared["different_fields"]["events"]["different_scalars"] == 1
    assert not module.differences(left, left)["different_fields"]
    right["energy"][2] = -np.inf
    with pytest.raises(ValueError, match="Nonfinite"):
        module.differences(left, right)


@pytest.fixture(scope="module")
def baseline():
    spec = parse_spec(raw_for())
    state, result = engine.run(spec, backend=BACKEND)
    evidence(
        "baseline",
        result | {"definition_sha256": spec.fingerprint, "definition": spec.to_dict()},
        state,
    )
    return spec, state, result


def test_definition_owner_order_and_separate_streams():
    raw = raw_for()
    spec = parse_spec(raw)
    assert parse_spec(spec.to_dict()).fingerprint == spec.fingerprint
    raw["pools"].reverse()
    assert parse_spec(raw).fingerprint == spec.fingerprint
    np.testing.assert_array_equal(channel_owners(spec), [0, 1, 0])
    state, checks = engine.validate_state(spec, engine.initial_state(spec))
    assert state.pool.free.shape == (2, 2)
    assert checks["max_global_balance_error_fmol"] == 0
    assert len({b.pool.seed for b in spec.pools}) == 2


@pytest.mark.parametrize(
    "case",
    [
        "missing_owner",
        "duplicate_owner",
        "duplicate_stream",
        "bad_seed",
        "different_worlds",
        "different_clock",
        "bad_availability",
        "wrong_ionic_family",
        "off_grid",
        "external_change_outside_horizon",
    ],
)
def test_invalid_definitions(case):
    raw = raw_for()
    second = raw["pools"][1]
    if case == "missing_owner":
        raw["pools"].pop()
    elif case == "duplicate_owner":
        second["cell_id"] = "cell_0"
    elif case == "duplicate_stream":
        second["stream_id"] = 0
    elif case == "bad_seed":
        second["pool"]["seed"] += 1
    elif case == "different_worlds":
        second["pool"]["world_id_start"] = 1
    elif case == "different_clock":
        second["pool"]["end_time_s"] = 0.01
    elif case == "bad_availability":
        second["coupling"]["active_availability"] = float("nan")
    elif case == "wrong_ionic_family":
        raw["ionic"] = json.loads((ROOT / "configs/assembly_regulated_cell.json").read_text())[
            "ionic"
        ]
    elif case == "off_grid":
        raw["ionic"]["experiment"]["observation_times"] = [0.0, 0.000073, 0.02]
    else:
        raw["ionic"]["experiment"]["channel_controls"][0]["schedule"].append(
            {"time": raw["ionic"]["experiment"]["end_time"] + 0.01, "availability": 0.0}
        )
    with pytest.raises(ValueError):
        parse_spec(raw)


@pytest.mark.parametrize("case", ["transfer_between_cells", "clock", "exposure", "ionic", "shape"])
def test_corrupt_state_and_cross_cell_material_transfer_rejected(case):
    spec = parse_spec(raw_for())
    state = engine.initial_state(spec)
    if case == "transfer_between_cells":
        # Global protein total is unchanged; each cell's own balance must fail.
        state.pool.free[0, 0] -= 1
        state.pool.free[0, 1] += 1
    elif case == "clock":
        state.pool.time_s[0, 1] = spec.ionic.execution.dt
    elif case == "exposure":
        state.availability_exposure_s[0, 1] = 1
    elif case == "ionic":
        state.ionic.extracellular_amount_increment[0, 0, 0] = 0.01
    else:
        state = state._replace(availability_exposure_s=np.zeros((spec.pool.worlds,)))
    with pytest.raises((AssemblyError, NumericalError)):
        engine.validate_state(spec, state)


def ensemble_definition():
    raw = raw_for()
    for binding in raw["pools"]:
        for key in ("worlds", "world_id_start", "seed"):
            binding["pool"].pop(key, None)
    return {
        "kind": "assembly_cluster_ensemble@1",
        "seed": 2**32 - 1,
        "arms": [
            {
                "id": "cluster",
                "definition": raw,
                "worlds": 64,
                "batch_worlds": 2,
                "seconds_per_world": 2.0,
            }
        ],
        "execution": {
            "max_wall_seconds": 1800,
            "max_output_bytes": 8 * 1024**3,
            "target_gpu_utilization_pct": 70,
            "worker_threads": 1,
            "workers_per_gpu": 1,
        },
    }


def test_ensemble_identities_survive_balance_and_sixteen_gpu_planning():
    data = ensemble_definition()
    local, future = plan(data, 1), jupiter_plan(data, 4)
    assert local["tasks"] == future["tasks"]
    assert future["deployment"]["maximum_target_gpus"] == 16
    assert not future["deployment"]["remote_execution_qualified"]
    assert future["worlds"] == 64
    split = plan(balance(data, {"cluster": 2.0}, 2.0), 1)
    identities = []
    for planned in (local, split):
        ids = []
        for task in planned["tasks"]:
            spec = parse_spec(task["definition"])
            assert [b.pool.seed for b in spec.pools] == [2**32 - 1, 0]
            ids.extend(range(spec.pool.world_id_start, spec.pool.world_id_start + spec.pool.worlds))
        identities.append(sorted(ids))
    assert identities == [list(range(64))] * 2
    bad = copy.deepcopy(data)
    bad["arms"][0]["definition"]["pools"][1]["pool"]["seed"] = 1
    with pytest.raises(ValueError, match="Ensemble owns"):
        plan(bad, 1)


def event_histories(spec, state, world):
    events = {}
    for index, binding in enumerate(spec.pools):
        p = binding.pool
        count = int(state.pool.event_count[world, index])
        with jax.default_device(device_for("cpu")):
            uniforms = np.asarray(
                jax.vmap(
                    lambda event, p=p: random_pair(
                        np.uint32(p.seed), np.uint32(p.world_id_start + world), event
                    )
                )(np.arange(count + 1, dtype=np.uint32))
            )
        trace = pool_reference.trajectory(p, uniforms)
        assert len(trace) == count
        if trace:
            final = trace[-1]
            assert tuple(int(v[world, index]) for v in state.pool[:3]) == final[1:4]
            np.testing.assert_array_equal(state.pool.fragments[world, index], final[5])
        events[binding.cell_id] = trace
    return events


def test_union_clock_independent_references_and_refinement(baseline):
    spec, middle, _ = baseline
    ref = oracle()
    context = ref.spatial.bind(spec.ionic.to_dict())
    results = {spec.ionic.execution.dt: middle}
    for dt in (0.0001, 0.000025):
        variant = parse_spec(raw_for(dt=dt))
        results[dt], result = engine.run(variant, backend=BACKEND)
        evidence(f"refinement-{dt:.8f}", result | {"definition": variant.to_dict()}, results[dt])
    errors, comparisons, calls = [], 0, 0
    for world in range(spec.pool.worlds):
        events = event_histories(spec, middle, world)
        expected = ref.integrate(spec.to_dict(), events)
        second = ref.integrate(spec.to_dict(), events, method="Radau")
        np.testing.assert_allclose(expected["state"], second["state"], rtol=3e-9, atol=3e-12)
        evidence(
            f"reference-world-{world}",
            {
                "definition": spec.to_dict(),
                "world_id": spec.pool.world_id_start + world,
                "events": events,
                "dop853": {
                    k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in expected.items()
                },
                "radau": {
                    k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in second.items()
                },
            },
        )
        calls += expected["rhs_calls"] + second["rhs_calls"]
        local_errors = []
        for dt in (0.0001, 0.00005, 0.000025):
            state = results[dt]
            actual = ref.spatial.flatten(
                context, {k: v[world] for k, v in state.ionic._asdict().items()}
            )
            np.testing.assert_allclose(actual, expected["state"], rtol=3e-9, atol=3e-12)
            np.testing.assert_allclose(
                state.availability_exposure_s[world], expected["exposure_s"], rtol=0, atol=2e-14
            )
            for key in ("occupied", "bonds", "free", "fragments", "event_count"):
                np.testing.assert_array_equal(getattr(state.pool, key), getattr(middle.pool, key))
            local_errors.append(float(np.max(np.abs(actual - expected["state"]))))
            comparisons += actual.size
        assert local_errors[1] <= 0.5 * local_errors[0] + 1e-13
        assert local_errors[2] <= 0.5 * local_errors[1] + 1e-13
        errors.append(local_errors)
    evidence(
        "independent-reference",
        {
            "status": "passed",
            "comparisons": comparisons,
            "rhs_calls": calls,
            "max_absolute_errors_by_world_and_step": errors,
            "steps_s": [0.0001, 0.00005, 0.000025],
            "reference_methods": ["DOP853", "Radau"],
            "refinement_floor": 1e-13,
            "scope": "No measured order claim below the numerical floor",
        },
    )


def control_spec(kind, opened):
    raw = parse_spec(raw_for()).to_dict()
    for binding in raw["pools"]:
        binding["pool"].update(k_on_M_inv_s=0.0, k_off_s_inv=0.0, k_close_s_inv=0.0)
    if opened:
        raw["pools"][0]["pool"]["initial_bond_indices"].pop()
    if kind in ("junction_off", "receiver_isolated"):
        raw["ionic"]["experiment"]["junction_controls"][0]["schedule"][0]["open_fraction"] = 0.0
    if kind == "receiver_isolated":
        receiver = raw["ionic"]["experiment"]["membrane_controls"][1]
        receiver["leak"][0]["multipliers"] = dict.fromkeys(receiver["leak"][0]["multipliers"], 0.0)
        receiver["pump"][0]["multiplier"] = 0.0
        raw["ionic"]["experiment"]["channel_controls"][1]["schedule"][0]["availability"] = 0.0
    if kind == "coupling_disabled":
        raw["pools"][0]["coupling"]["active_availability"] = 0.0
    return parse_spec(raw)


def test_organization_neighbour_response_and_disconnected_controls():
    ref, rows, differences = oracle(), {}, {}
    for kind in ("connected", "junction_off", "receiver_isolated", "coupling_disabled"):
        pair = []
        for opened in (False, True):
            spec = control_spec(kind, opened)
            state, result = engine.run(spec, backend=BACKEND)
            expected = ref.integrate(spec.to_dict(), {p.cell_id: [] for p in spec.pools})
            np.testing.assert_allclose(
                result["final_voltage_V"], [expected["voltage_V"]] * 2, rtol=3e-9, atol=3e-12
            )
            name = kind + ("-open" if opened else "-ring")
            rows[name] = result
            evidence("control-" + name, result | {"definition": spec.to_dict()}, state)
            pair.append((state, result))
        differences[kind] = (
            np.array(pair[0][1]["final_voltage_V"]) - np.array(pair[1][1]["final_voltage_V"])
        )[0]
        if kind == "receiver_isolated":
            assert differences[kind][1] == 0
        elif kind == "coupling_disabled":
            for a, b in zip(pair[0][0].ionic, pair[1][0].ionic, strict=True):
                np.testing.assert_array_equal(a, b)
    assert abs(differences["connected"][0]) > 1e-10
    assert abs(differences["connected"][1]) > 1e-10
    assert abs(differences["connected"][1] - differences["junction_off"][1]) > 1e-10
    evidence(
        "neighbour-response",
        {
            "status": "passed",
            "ring_minus_open_voltage_V": {k: v.tolist() for k, v in differences.items()},
            "scope": (
                "Junction-off retains the shared bath; only isolated receiver has zero transfer"
            ),
            "experimental_validation": False,
        },
    )


def test_complete_restart_windows_world_partition_and_pool_independence(baseline, tmp_path):
    spec, whole, _ = baseline
    first, _ = engine.run(spec, backend=BACKEND, until=0.0073)
    path = tmp_path / "cluster-checkpoint"
    write_checkpoint(path, spec, first, backend=BACKEND)
    saved, restored, _ = load_checkpoint(path, backend=BACKEND)
    same(first, restored)
    resumed, _ = engine.run(saved, backend=BACKEND, state=restored)
    same(whole, resumed)
    windows, _ = engine.run(replace(spec, window_ticks=7), backend=BACKEND)
    same(whole, windows)
    pieces = []
    for start in range(2):
        raw = bind_definition(spec.to_dict(), worlds=1, world_id_start=start, seed=spec.pool.seed)
        part, result = engine.run(parse_spec(raw), backend=BACKEND)
        # Preserve every endpoint before comparing; a failed exact check must
        # leave enough evidence to localize all differing fields and magnitudes.
        evidence(f"partition-world-{start}", result | {"definition": raw}, part)
        pieces.append(part)
    combined = jax.tree.map(lambda a, b: np.concatenate((a, b)), *pieces)
    evidence("partition-combined", {"definition": spec.to_dict()}, combined)
    same(whole, combined)

    # An unrelated neighbouring world must not change these two trajectories.
    # Exercise another compilation shape and a nonzero starting world ID.
    raw = bind_definition(spec.to_dict(), worlds=3, world_id_start=0, seed=spec.pool.seed)
    wider, result = engine.run(parse_spec(raw), backend=BACKEND)
    evidence("partition-width-three", result | {"definition": raw}, wider)
    same(whole, jax.tree.map(lambda value: value[:2], wider))
    raw = bind_definition(spec.to_dict(), worlds=2, world_id_start=1, seed=spec.pool.seed)
    shifted, result = engine.run(parse_spec(raw), backend=BACKEND)
    evidence("partition-shifted", result | {"definition": raw}, shifted)
    same(shifted, jax.tree.map(lambda value: value[1:3], wider))
    for i, binding in enumerate(spec.pools):
        standalone, _ = pool_engine.run(binding.pool, backend=BACKEND)
        for key, expected in standalone._asdict().items():
            actual = getattr(whole.pool, key)[:, i]
            if actual.dtype.kind == "f":
                np.testing.assert_allclose(actual, expected, rtol=3e-12, atol=2e-14, err_msg=key)
            else:
                np.testing.assert_array_equal(actual, expected, err_msg=key)
    with pytest.raises(AssemblyError, match="backend"):
        load_checkpoint(path, backend="gpu" if BACKEND == "cpu" else "cpu")
    evidence(
        "replay",
        {
            "status": "passed",
            "disk_restart_exact": True,
            "windows_exact": True,
            "world_partition_exact": True,
            "widths_compared": [1, 2, 3],
            "nonzero_world_id_start": True,
            "cell_pool_independence": True,
        },
    )


def test_simultaneous_events_at_grid_boundary_use_preceding_assembly():
    raw = parse_spec(raw_for()).to_dict()
    for binding in raw["pools"]:
        binding["pool"].update(k_on_M_inv_s=0.0, k_close_s_inv=0.0)
    spec = parse_spec(raw)
    state = engine.initial_state(spec)
    dt = spec.ionic.execution.dt
    state.pool.pending_valid[:] = True
    state.pool.pending_time_s[:] = dt
    for i, binding in enumerate(spec.pools):
        state.pool.pending_event[:, i] = 30 + binding.pool.initial_bond_indices[0]
    first, _ = engine.run(spec, backend=BACKEND, state=state, until=dt)
    assert np.all(first.pool.event_count == 1)
    np.testing.assert_array_equal(first.availability_exposure_s, np.full((2, 2), dt))
    second, _ = engine.run(spec, backend=BACKEND, state=first, until=2 * dt)
    np.testing.assert_array_equal(second.availability_exposure_s, first.availability_exposure_s)
    evidence(
        "simultaneous-grid-events",
        {"status": "passed", "event_time_s": dt, "independent_tied_events": 4},
    )


def test_event_budget_fault_is_retained():
    raw = raw_for()
    for binding in raw["pools"]:
        binding["pool"]["max_events_per_world"] = 1
    captured = []
    with pytest.raises(AssemblyError, match="fault"):
        engine.run(
            parse_spec(raw), backend=BACKEND, callback=lambda _, state: captured.append(state)
        )
    assert captured and np.any(captured[-1].pool.fault == 2)
    evidence("expected-event-budget-fault", {"status": "expected_refusal"}, captured[-1])


def test_public_cli_observations_and_complete_resume(tmp_path, capsys):
    from cells.__main__ import main

    spec = parse_spec(raw_for())
    config = tmp_path / "definition.json"
    config.write_text(json.dumps(spec.to_dict()))
    first, second = tmp_path / "first", tmp_path / "second"
    assert main(["assembly-cluster", "validate", str(config)]) == 0
    for command, source, output, until in (
        ("run", config, first, "0.005"),
        ("resume", first / "checkpoint", second, "0.01"),
    ):
        assert (
            main(
                [
                    "assembly-cluster",
                    command,
                    str(source),
                    "--output",
                    str(output),
                    "--backend",
                    BACKEND,
                    "--until",
                    until,
                ]
            )
            == 0
        )
        assert (output / "completion.json").exists()
        assert len(list((output / "observations").glob("*.json"))) == 2
    _, restored, _ = load_checkpoint(second / "checkpoint", backend=BACKEND)
    whole, _ = engine.run(spec, backend=BACKEND, until=0.01)
    same(whole, restored)
    assert (
        main(
            [
                "assembly-cell",
                "resume",
                str(second / "checkpoint"),
                "--backend",
                BACKEND,
                "--output",
                str(tmp_path / "wrong-family"),
            ]
        )
        == 2
    )
    payload = second / "checkpoint/state.npz"
    data = bytearray(payload.read_bytes())
    data[50] ^= 1
    payload.write_bytes(data)
    with pytest.raises(AssemblyError, match="state_sha256"):
        load_checkpoint(second / "checkpoint", backend=BACKEND)
    capsys.readouterr()


def test_scheduler_adapter_and_per_cell_aggregation(baseline, tmp_path):
    from cells.ensemble.cli import aggregate

    spec, state, report = baseline
    run, load, write = runtime_for(spec)
    replay, result = run(spec, backend=BACKEND, state=state)
    same(replay, state)
    assert first_completion(spec, state) is None
    directory = tmp_path / "ensemble-checkpoint"
    write(
        directory,
        spec,
        state,
        execution={
            "backend": BACKEND,
            "device_index": 0,
            "device_kind": device_for(BACKEND).device_kind,
        },
    )
    _, restored, _ = load(directory, backend=BACKEND)
    same(state, restored)
    rows = []
    for i in range(2):
        raw = bind_definition(spec.to_dict(), worlds=1, world_id_start=i, seed=spec.pool.seed)
        current = jax.tree.map(lambda value, i=i: value[i : i + 1], state)
        row = engine.summary(parse_spec(raw), current)
        row.update(arm="cluster", wall_start=0.0, wall_end=1.0, execute_seconds=0.5)
        rows.append(row)
    combined = aggregate(rows)["cluster"]
    assert combined["worlds"] == 2
    assert "completed_shells" not in combined
    np.testing.assert_allclose(
        combined["final_voltage_mean_V"], np.mean(report["final_voltage_V"], axis=0), rtol=0, atol=0
    )
    for name, cell in combined["assembly_cells"].items():
        assert cell["worlds"] == 2
        assert sum(cell["final_size_histogram"]) == 2
        assert (
            cell["initial_total_trimers"] == report["assembly_cells"][name]["initial_total_trimers"]
        )
        assert cell["material_residual_trimers"] == 0
    evidence("scheduler-adapter", {"status": "passed", "aggregate": combined})


def test_one_cell_no_spatial_faces_reduces_to_previous_composition():
    from cells.assembly_cell import engine as previous
    from cells.assembly_cell.spec import parse_spec as parse_previous

    old = json.loads((ROOT / "configs/assembly_regulated_cell.json").read_text())
    old["pool"].update(worlds=2, k_off_s_inv=300.0, k_close_s_inv=1000.0)
    prior = parse_previous(old)
    raw = {
        "model": "assembly_regulated_cluster@1",
        "pools": [
            {
                "cell_id": "cell_0",
                "stream_id": 0,
                "pool": prior.pool.to_dict(),
                "coupling": old["coupling"],
            }
        ],
        "ionic": copy.deepcopy(old["ionic"]),
        "window_ticks": 32,
    }
    raw["ionic"]["model"].update(
        id="spatial_extracellular@2",
        surroundings=[],
        faces=[],
        closure={"law": "capacitive_components_current_continuity@1", "gauge_reference": "outside"},
    )
    raw["ionic"]["execution"].update(face_capacity=0, field_solver="gauged_dense_kirchhoff@1")
    current, _ = engine.run(parse_spec(raw), backend=BACKEND)
    old_state, _ = previous.run(prior, backend=BACKEND)
    compared = 0
    for name, value in flatten(old_state).items():
        actual = flatten(current)[name]
        if name.startswith("pool_") or name == "availability_exposure_s":
            actual = actual[:, 0]
        if value.dtype.kind == "f":
            np.testing.assert_allclose(actual, value, rtol=3e-10, atol=3e-13, err_msg=name)
        else:
            np.testing.assert_array_equal(actual, value, err_msg=name)
        compared += actual.size
    evidence("one-cell-reduction", {"status": "passed", "comparisons": compared})


def test_detached_cli_selects_correct_module(tmp_path, monkeypatch, capsys):
    from cells.assembly_cell import cli

    launches = []

    def launch(command, **kwargs):
        launches.append((command, kwargs))
        return type("DetachedProcess", (), {"pid": 12345})()

    monkeypatch.setattr(cli.subprocess, "Popen", launch)
    for cluster in (False, True):
        raw = (
            raw_for()
            if cluster
            else json.loads((ROOT / "configs/assembly_regulated_cell.json").read_text())
        )
        name = "assembly_cluster" if cluster else "assembly_cell"
        definition = tmp_path / (name + ".json")
        definition.write_text(json.dumps(raw))
        output = tmp_path / name
        assert (
            cli.main(["run", str(definition), "--output", str(output), "--detach"], cluster=cluster)
            == 0
        )
        command, kwargs = launches[-1]
        assert command[command.index("-m") + 1] == "cells." + name
        assert kwargs["start_new_session"] is True
        assert kwargs["env"]["PYTHONPATH"] == str(output / "source")
        assert (output / "launch.json").exists()
    capsys.readouterr()


@pytest.mark.skipif(BACKEND != "gpu", reason="Saved CPU/L4 comparison runs in the GPU phase")
def test_cpu_gpu_cluster_agreement(baseline):
    spec, gpu, report = baseline
    assert report["backend"] == "gpu" and device_for("gpu").platform == "gpu"
    if EVIDENCE:
        path = Path(EVIDENCE) / "cpu/baseline"
        saved = json.loads(path.with_suffix(".json").read_text())
        assert saved["definition_sha256"] == spec.fingerprint
        with np.load(path.with_suffix(".npz"), allow_pickle=False) as arrays:
            cpu = {k: arrays[k].copy() for k in arrays.files}
    else:
        cpu = flatten(engine.run(spec, backend="cpu")[0])
    comparisons = 0
    for key, actual in flatten(gpu).items():
        expected = cpu[key]
        if actual.dtype.kind == "f":
            np.testing.assert_allclose(actual, expected, rtol=3e-10, atol=3e-13, err_msg=key)
        else:
            np.testing.assert_array_equal(actual, expected, err_msg=key)
        comparisons += actual.size
    evidence(
        "cpu-gpu-comparison",
        {"status": "passed", "comparisons": comparisons, "rtol": 3e-10, "atol": 3e-13},
    )
