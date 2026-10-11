"""Public pump–leak placement, conservative history and complete GPU continuation."""

import copy
import json
import os
from pathlib import Path

import numpy as np
import pytest

from cells.core.batch import BatchSpec, WorldSpec, parse_batch, run_batch
from cells.core.devices import execution_device
from cells.core.runner import run
from cells.core.specs import ConfigError, parse_spec
from cells.core.windows import WindowPolicy, iter_windows
from cells.io import load_snapshot, write_snapshot

ROOT = Path(__file__).parents[2]


def definition(backend="cpu"):
    data = json.loads((ROOT / "configs/kinetic_finite_cell.json").read_text())
    data["execution"]["backend"] = backend
    data["experiment"]["end_time"] = 0.0004
    data["experiment"]["observation_times"] = [0.0, 0.0002, 0.0004]
    return data


def test_gpu_definition_roundtrip_and_mixed_batch_refusal():
    cpu, gpu = (parse_spec(definition(b)) for b in ("cpu", "gpu"))
    assert gpu.execution.backend == "gpu"
    assert parse_spec(gpu.to_dict()) == gpu
    batch = BatchSpec((WorldSpec(1, cpu), WorldSpec(2, gpu)), 2, 100, 2**28)
    with pytest.raises(ConfigError, match="backend"):
        parse_batch(batch.to_dict())


@pytest.mark.parametrize(
    "field,value", [("backend", "tpu"), ("precision", "float32"), ("jit", False)]
)
def test_gpu_keeps_explicit_precision_and_solver_contract(field, value):
    data = definition("gpu")
    data["execution"][field] = value
    with pytest.raises(ConfigError):
        parse_spec(data)


def test_missing_gpu_does_not_fall_back(monkeypatch):
    def missing(_backend):
        raise RuntimeError("No GPU")

    monkeypatch.setattr("jax.devices", missing)
    with pytest.raises(ConfigError, match="no CPU fallback"):
        execution_device("gpu")


@pytest.mark.skipif(os.environ.get("CELLS_TEST_GPU") != "1", reason="explicit CUDA test")
def test_public_gpu_cpu_history_windows_and_saved_restart(tmp_path):
    cpu = run(parse_spec(definition("cpu")))
    spec = parse_spec(definition("gpu"))
    gpu = run(spec)  # CPU initialization must not disable a later explicit GPU.
    assert all(x.device.platform in ("cuda", "gpu") for x in gpu.final.state)
    for expected, actual in zip(cpu.history, gpu.history, strict=True):
        np.testing.assert_allclose(actual, expected, atol=2e-12, rtol=2e-11)
    assert gpu.diagnostics["max_energy_balance_error_pJ"] < 2e-8
    cp = gpu.checkpoint_at(0.0002)
    write_snapshot(tmp_path / "checkpoint", spec, cp)
    saved = load_snapshot(tmp_path / "checkpoint")
    manifest = json.loads((tmp_path / "checkpoint/manifest.json").read_text())
    assert manifest["runtime"]["gpu"]["device_kind"]
    resumed = run(saved.spec, saved.checkpoint)
    for actual, expected in zip(resumed.history, gpu.history, strict=True):
        np.testing.assert_array_equal(actual, expected[2:])
    windows = list(iter_windows(spec, WindowPolicy(window_steps=2)))
    for actual, expected in zip(windows[-1].final.state, gpu.final.state, strict=True):
        np.testing.assert_array_equal(actual, expected)
    # Complete checkpoint domain checks still reject depleted ionic pools.
    from dataclasses import replace

    bad = copy.deepcopy(saved.checkpoint)
    fields = bad.state._asdict()
    fields["amount_increment"] = -1000 * np.ones_like(fields["amount_increment"])
    with pytest.raises((ConfigError, RuntimeError)):
        run(spec, replace(bad, state=type(bad.state)(**fields)))


@pytest.mark.skipif(os.environ.get("CELLS_TEST_GPU") != "1", reason="explicit CUDA test")
def test_guarded_gpu_batch_matches_separate_worlds():
    definitions = [definition("gpu"), definition("gpu")]
    definitions[1]["experiment"]["membrane_controls"][0]["pump"][0]["multiplier"] = 0.0
    specs = [parse_spec(d) for d in definitions]
    batch = BatchSpec(tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs)), 2, 100, 2**29)
    combined = run_batch(batch)
    for world in combined.worlds.values():
        scalar = run(world.spec)
        for expected, actual in zip(scalar.history, world.history, strict=True):
            np.testing.assert_allclose(actual, expected, atol=2e-12, rtol=2e-11)
