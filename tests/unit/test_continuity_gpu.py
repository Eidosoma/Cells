"""GPU definitions at the loaders: admitted only through the CPU-host probe's patch (§13.4).

docs/CHECKPOINT_CONTINUITY_DESIGN.md, section 13.4: on the L4, a CPU-host trace with
execution_device patched equalled the GPU host's in jaxprs, constants, bindings and host replay,
and its cuda cross-lowering the GPU host's own; so GPU definitions are probed on the CPU host
with no GPU time, and the record notes the patch (probe.execution_device).

This host has no GPU. Every test here patches execution_device, in every module that bound it,
to the CPU device, as the probe does: the snapshots are written and loaded under that patch,
and their manifests' "gpu" runtime describes the CPU device. They are test artifacts, which no
GPU host would load (its runtime differs), as the loader then refuses.
"""

import json

import jax
import pytest

from cells import batch_io, io
from cells.core import devices
from cells.core.batch import BatchSpec, WorldSpec, parse_batch
from cells.core.specs import ConfigError, parse_spec
from cells.core.state import initialise
from cells.numerics import surface_imex as imex
from tests.unit.test_continuity_loaders import build_record, change_source, refused, request
from validation.tissue import surface_pump_fixtures

PATCH = {
    "backend": "gpu",
    "patched": True,
    "probe_device": "cpu",
    "modules_patched": 9,
    "lowering_platforms": ["cpu", "cuda"],
}


@pytest.fixture(autouse=True)
def gpu_on_cpu(monkeypatch):
    """execution_device returns the CPU device, in every module that bound it by name."""
    jax.config.update("jax_enable_x64", True)
    import sys

    original, cpu = devices.execution_device, jax.devices("cpu")[0]

    def on_cpu(backend="cpu"):
        original("cpu")
        return cpu

    for module in list(sys.modules.values()):
        if getattr(module, "execution_device", None) is original:
            monkeypatch.setattr(module, "execution_device", on_cpu)


def gpu_definition(scale=1.0):
    raw = surface_pump_fixtures.definition("clamped", backend="gpu", solver=imex.ARS222_ID)
    for membrane in raw["model"]["membranes"]:
        membrane["pump"]["capacity_fmol_per_s"] *= scale
    return parse_spec(raw)


@pytest.fixture
def gpu_scalar(tmp_path):
    spec = gpu_definition()
    return io.write_snapshot(tmp_path / "gpu-scalar", spec, initialise(spec))


@pytest.fixture
def gpu_cohort(tmp_path):
    specs = [gpu_definition(1.0), gpu_definition(1.1)]
    batch = parse_batch(
        BatchSpec(
            tuple(WorldSpec(10 + i, s) for i, s in enumerate(specs)), 2, 10**6, 2**31
        ).to_dict()
    )
    starts = {w.world_id: initialise(w.simulation) for w in batch.worlds}
    return batch_io.write_batch_snapshot(tmp_path / "gpu-cohort", batch, starts)


def gpu_record(snapshot, patch=PATCH, **overrides):
    """A record for a GPU checkpoint: to is the GPU runtime, the probe ran on the CPU host."""
    probe = {"runtime": io.runtime_identity("cpu"), "host_fields_equal_to_runtime": True}
    if patch is not None:
        probe["execution_device"] = patch
    values = {"to.runtime": io.runtime_identity("gpu"), "probe": probe, **overrides}
    return build_record(snapshot, **values)


def test_the_manifests_runtime_is_a_gpu_one(gpu_scalar):
    runtime = json.loads((gpu_scalar / "manifest.json").read_text())["runtime"]
    assert "gpu" in runtime and runtime == io.runtime_identity("gpu")


def test_a_gpu_checkpoint_is_admitted_through_the_patched_probe(
    gpu_scalar, gpu_cohort, monkeypatch, tmp_path
):
    change_source(monkeypatch)
    saved = io.load_snapshot(gpu_scalar, continuity=request(tmp_path, gpu_record(gpu_scalar)))
    assert saved.admission.case == "identical_programs"
    assert saved.spec.execution.backend == "gpu"
    restored = batch_io.load_batch_snapshot(
        gpu_cohort, continuity=request(tmp_path, gpu_record(gpu_cohort))
    )
    assert sorted(restored.checkpoints) == [10, 11] and restored.admission is not None


def test_a_gpu_record_without_the_patch_is_refused(gpu_scalar, gpu_cohort, monkeypatch, tmp_path):
    change_source(monkeypatch)
    message = (
        "a GPU definition is admitted only through the CPU-host probe with execution_device "
        "patched (docs/CHECKPOINT_CONTINUITY_DESIGN.md, section 13.4), and the record notes no "
        "patch"
    )
    unpatched = gpu_record(gpu_scalar, patch=None)
    refused(
        lambda: io.load_snapshot(gpu_scalar, continuity=request(tmp_path, unpatched)),
        "Definition scalar: " + message,
    )
    unpatched = gpu_record(gpu_cohort, patch=None)
    refused(
        lambda: batch_io.load_batch_snapshot(gpu_cohort, continuity=request(tmp_path, unpatched)),
        "Definition 10: " + message,
    )


def test_a_cpu_record_with_a_patch_is_refused(spec, monkeypatch, tmp_path):
    path = io.write_snapshot(tmp_path / "cpu", spec, initialise(spec))
    change_source(monkeypatch)
    probe = {
        "runtime": io.runtime_identity("cpu"),
        "host_fields_equal_to_runtime": True,
        "execution_device": PATCH,
    }
    record = build_record(path, probe=probe)
    refused(
        lambda: io.load_snapshot(path, continuity=request(tmp_path, record)),
        "Definition scalar: the record notes a device patch, but this is a CPU definition",
    )


def test_a_gpu_record_binds_the_gpu_runtime(gpu_scalar, monkeypatch, tmp_path):
    """The probe's own CPU runtime is not the resuming GPU host's (admit.resuming_runtime)."""
    change_source(monkeypatch)
    wrong = gpu_record(gpu_scalar, **{"to.runtime": io.runtime_identity("cpu")})
    refused(
        lambda: io.load_snapshot(gpu_scalar, continuity=request(tmp_path, wrong)),
        "Continuity record's to runtime is not this installation's",
    )


def test_a_gpu_records_probe_jaxlib_counts_with_its_host_fields(gpu_scalar, monkeypatch, tmp_path):
    """The cuda cross-lowering was shown equal to the GPU host's with jax and jaxlib unchanged."""
    change_source(monkeypatch)
    probe = io.runtime_identity("cpu")
    probe = {**probe, "packages": {**probe["packages"], "jaxlib": "0.0.0"}}
    record = gpu_record(
        gpu_scalar,
        probe={"runtime": probe, "host_fields_equal_to_runtime": True, "execution_device": PATCH},
    )
    refused(
        lambda: io.load_snapshot(gpu_scalar, continuity=request(tmp_path, record)),
        "The probe's host-side runtime differs from the resuming runtime (['packages.jaxlib']); "
        "rerun the probe under the resuming runtime",
    )


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"lowering_platforms": ["cpu"]}, "must name cpu and cuda"),
        ({"patched": False}, "notes a GPU definition patched to the CPU device"),
        ({"backend": "cpu"}, "notes a GPU definition patched to the CPU device"),
        ({"probe_device": "gpu"}, "notes a GPU definition patched to the CPU device"),
        ({"modules_patched": 0}, "modules_patched must be an integer of at least 1"),
        ({"extra": 1}, "probe.execution_device must have exactly the fields"),
    ],
)
def test_the_patch_note_is_verified(gpu_scalar, monkeypatch, tmp_path, change, message):
    change_source(monkeypatch)
    record = gpu_record(gpu_scalar, patch={**PATCH, **change})
    with pytest.raises(ConfigError, match=message):
        io.load_snapshot(gpu_scalar, continuity=request(tmp_path, record))


def test_without_a_record_a_gpu_checkpoint_loads_as_today(gpu_scalar, monkeypatch):
    assert io.load_snapshot(gpu_scalar).admission is None
    change_source(monkeypatch)
    refused(
        lambda: io.load_snapshot(gpu_scalar),
        "Checkpoint model/engine source differs from this installation",
    )


def test_a_gpu_record_is_still_refused_for_other_paths(gpu_scalar, monkeypatch, tmp_path):
    change_source(monkeypatch)
    record = gpu_record(gpu_scalar)
    refused(
        lambda: io.load_snapshot(
            gpu_scalar, continuity=request(tmp_path, record, path="batch_windows")
        ),
        "Continuity cannot decide the batch_windows path: the first landing decides vector "
        "windows only (docs/CHECKPOINT_CONTINUITY_DESIGN.md, section 13.1)",
    )
