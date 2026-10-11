"""Integrated scheduling preserves worlds, model semantics and complete checkpoints."""

import copy
import json
import os
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.ensemble.cli import aggregate
from cells.ensemble.families import bind_definition, parse_definition, population
from cells.ensemble.plan import balance, plan

ROOT = Path(__file__).resolve().parents[2]
BACKEND = os.environ.get("CELLS_COUPLED_TEST_BACKEND", "cpu")


def parity_evidence(name, values):
    directory = os.environ.get("CELLS_INTEGRATED_EVIDENCE")
    if directory is None:
        return
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path / f"{name}-{BACKEND}.npz", **values)
    if BACKEND == "gpu":
        with np.load(path / f"{name}-cpu.npz", allow_pickle=False) as expected:
            assert set(expected.files) == set(values)
            for key, actual in values.items():
                if actual.dtype.kind in "iub":
                    np.testing.assert_array_equal(actual, expected[key])
                else:
                    np.testing.assert_allclose(actual, expected[key], atol=5e-11, rtol=5e-12)


def experiment(family, *, backend="cpu", worlds=2, width=1, end=0.0004):
    coupled = json.loads((ROOT / "configs/assembly_regulated_cell.json").read_text())
    if family == "assembly_cell":
        raw = coupled
        for key in ("worlds", "seed", "world_id_start"):
            raw["pool"].pop(key, None)
        raw["pool"].update(end_time_s=end, k_off_s_inv=3000, k_close_s_inv=1000)
        raw["ionic"]["experiment"].update(end_time=end, observation_times=[0.0, end])
        raw["ionic"]["execution"]["backend"] = backend
        raw["window_ticks"] = 2
    else:
        simulation = json.loads((ROOT / "configs/junction_finite_cluster.json").read_text())
        simulation["experiment"].update(end_time=end, observation_times=[0.0, end])
        for controls in ("membrane_controls", "channel_controls", "junction_controls"):
            for control in simulation["experiment"][controls]:
                for key, values in control.items():
                    if isinstance(values, list):
                        control[key] = [values[0]]
        simulation["execution"]["backend"] = backend
        raw = {"model": "ionic_worlds@1", "simulation": simulation, "window_steps": 2}
    return {
        "kind": family + "_ensemble@1",
        "seed": 123,
        "arms": [
            {
                "id": "active",
                "definition": raw,
                "worlds": worlds,
                "batch_worlds": width,
                "seconds_per_world": None,
            }
        ],
        "execution": {
            "max_wall_seconds": 600,
            "max_output_bytes": 512 * 1024**2,
            "target_gpu_utilization_pct": 70,
            "worker_threads": 1,
        },
    }


@pytest.mark.parametrize("family", ["ionic", "assembly_cell"])
def test_counts_ids_kind_and_balancing(family):
    data = experiment(family, worlds=16, width=8)
    original = copy.deepcopy(data)
    result = plan(data, 1)
    tuned = plan(balance(data, {"active": 1.0}, 4.0), 1)

    def ids(p):
        populations = [population(parse_definition(t["definition"])) for t in p["tasks"]]
        return [
            i for p in populations for i in range(p.world_id_start, p.world_id_start + p.worlds)
        ]

    assert ids(result) == ids(tuned) == list(range(16))
    assert data == original
    data["kind"] = "finite_bond_ensemble@1"
    with pytest.raises(ValueError, match="kind"):
        plan(data, 1)


@pytest.mark.parametrize("family", ["ionic", "assembly_cell"])
def test_reject_owned_counts_and_over_budget(family):
    data = experiment(family)
    raw = data["arms"][0]["definition"]
    target = raw["pool"] if family == "assembly_cell" else raw
    target["seed"] = 17
    with pytest.raises(ValueError, match="owns"):
        plan(data, 1)
    target.pop("seed")
    data["execution"]["max_output_bytes"] = 1024**2
    with pytest.raises(ValueError, match="bound"):
        plan(data, 1)


def test_ionic_aggregation_does_not_invent_assembly_statistics():
    row = {
        "arm": "a",
        "model": "ionic_worlds@1",
        "physical_model": "finite_extracellular@3",
        "worlds": 2,
        "wall_start": 0.0,
        "wall_end": 1.0,
        "execute_seconds": 0.1,
        "integrated_world_steps": 10,
        "final_voltage_V": [[-0.08, -0.07], [-0.06, -0.05]],
        "ionic_accounting": {"balance": 2e-15},
    }
    value = aggregate([row, row])["a"]
    assert value["worlds"] == 4 and value["integrated_world_steps"] == 20
    assert value["final_voltage_mean_V"] == pytest.approx([-0.07, -0.06])
    assert "completed_shells" not in value and "completion_probability" not in value
    assert "committed_events" not in value


def test_ionic_checkpoint_window_replay_and_scalar_parity(tmp_path):
    from cells.assembly.engine import device_for
    from cells.core.batch_windows import iter_batch_windows
    from cells.core.runner import run as scalar
    from cells.core.windows import WindowPolicy
    from cells.ensemble import ionic

    raw = experiment("ionic", backend=BACKEND)["arms"][0]["definition"]
    spec = parse_definition(bind_definition(raw, worlds=2, world_id_start=0, seed=123))
    whole, _ = ionic.run(spec, backend=BACKEND)
    first = next(iter_batch_windows(spec.batch(), WindowPolicy(2, "checkpoints")))
    path = tmp_path / "checkpoint"
    ionic.write_checkpoint(
        path,
        spec,
        first.checkpoints,
        execution={"backend": BACKEND, "device_kind": device_for(BACKEND, 0).device_kind},
    )
    saved, checkpoints, _ = ionic.load_checkpoint(path, backend=BACKEND)
    resumed, _ = ionic.run(saved, backend=BACKEND, state=checkpoints)
    reference = scalar(spec.simulation)
    for identity in whole:
        for a, b, c in zip(
            whole[identity].state, resumed[identity].state, reference.final.state, strict=True
        ):
            np.testing.assert_array_equal(a, b)
            np.testing.assert_allclose(a, c, atol=5e-13, rtol=5e-12)
    parity_evidence(
        "ionic",
        {
            f"{i}_{k}": np.asarray(v)
            for i, cp in whole.items()
            for k, v in cp.state._asdict().items()
        },
    )
    altered = json.loads((path / "manifest.json").read_text())
    altered["execution"]["device_kind"] = "different"
    (path / "manifest.json").write_text(json.dumps(altered))
    with pytest.raises(ValueError, match="device kind"):
        ionic.load_checkpoint(path, backend=BACKEND)


def test_coupled_adapter_complete_state_and_callbacks(tmp_path):
    from cells.assembly.engine import device_for
    from cells.assembly_cell import engine
    from cells.assembly_cell.io import flatten
    from cells.ensemble import coupled

    raw = experiment("assembly_cell", backend=BACKEND)["arms"][0]["definition"]
    spec = parse_definition(bind_definition(raw, worlds=2, world_id_start=9, seed=123))
    windows = []
    whole, result = coupled.run(
        spec, backend=BACKEND, callback=lambda i, state, trace: windows.append(state)
    )
    path = tmp_path / "checkpoint"
    coupled.write_checkpoint(
        path,
        spec,
        windows[0],
        execution={"backend": BACKEND, "device_kind": device_for(BACKEND, 0).device_kind},
    )
    saved, state, _ = coupled.load_checkpoint(path, backend=BACKEND)
    resumed, _ = coupled.run(saved, backend=BACKEND, state=state)
    direct, _ = engine.run(replace(spec, window_ticks=1), backend=BACKEND)
    for key, value in flatten(whole).items():
        np.testing.assert_array_equal(value, flatten(resumed)[key])
        np.testing.assert_array_equal(value, flatten(direct)[key])
    parity_evidence("coupled", flatten(whole))
    assert result["worlds"] == 2 and result["model"] == "assembly_regulated_cell@1"
    assert "committed_events" in result and "ionic_accounting" in result
    assert "final_validation_summary_seconds" in result["phase_timings"]
