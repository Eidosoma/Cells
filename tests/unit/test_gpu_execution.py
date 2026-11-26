"""What a GPU definition declares, and the refusals that keep a run from falling back."""

import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.batch import BatchSpec, WorldSpec, parse_batch
from cells.execution.devices import execution_device
from cells.numerics import surface_imex as imex
from validation.tissue import surface_pump_fixtures


def definition(backend="cpu"):
    """The clamped pump tissue, which admits a GPU."""
    data = surface_pump_fixtures.definition("clamped", backend=backend, solver=imex.ARS222_ID)
    data["experiment"].update(end_time=0.0004, observation_times=[0.0, 0.0002, 0.0004])
    return data


def test_gpu_definition_roundtrip_and_mixed_batch_refusal():
    cpu, gpu = (parse_spec(definition(b)) for b in ("cpu", "gpu"))
    assert gpu.execution.backend == "gpu"
    assert parse_spec(gpu.to_dict()) == gpu
    batch = BatchSpec((WorldSpec(1, cpu), WorldSpec(2, gpu)), 2, 100, 2**28)
    with pytest.raises(ConfigError, match="backend"):
        parse_batch(batch.to_dict())


@pytest.mark.parametrize("field,value", [("backend", "tpu"), ("precision", "float32")])
def test_gpu_keeps_explicit_precision_and_solver_contract(field, value):
    data = definition("gpu")
    data["execution"][field] = value
    with pytest.raises(ConfigError, match="requires float64 CPU/GPU"):
        parse_spec(data)


def test_missing_gpu_does_not_fall_back(monkeypatch):
    def missing(_backend):
        raise RuntimeError("No GPU")

    monkeypatch.setattr("jax.devices", missing)
    with pytest.raises(ConfigError, match="no CPU fallback"):
        execution_device("gpu")
