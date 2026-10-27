"""Complete, authenticated event checkpoints and durable run artifacts."""

import hashlib
import importlib.metadata
import json
import os
import platform
import sys
import zipfile
from pathlib import Path

import numpy as np

from cells.assembly.engine import configure_runtime, validate_state
from cells.assembly.kernel import AssemblyState
from cells.assembly.spec import AssemblyError, parse_spec


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024**2), b""):
            value.update(chunk)
    return value.hexdigest()


def source_identity():
    result = {p.name: digest(p) for p in sorted(Path(__file__).parent.glob("*.py"))}
    policy = Path(__file__).parents[1] / "core/output_paths.py"
    result["../core/output_paths.py"] = digest(policy)
    return result


def runtime():
    configure_runtime()
    accelerators = {}
    for package in importlib.metadata.distributions():
        name = package.metadata.get("Name", "").lower().replace("_", "-")
        if name.startswith(("jax-cuda", "nvidia-")):
            accelerators[name] = package.version
    return {
        "jax_flags": {"jax_enable_x64": True, "jax_threefry_partitionable": True},
        "python": sys.version,
        "machine": platform.machine(),
        "packages": {name: importlib.metadata.version(name) for name in ("jax", "jaxlib", "numpy")},
        "accelerator_packages": dict(sorted(accelerators.items())),
        "numerical_environment": {
            name: os.environ.get(name) for name in ("XLA_FLAGS", "JAX_DISABLE_JIT")
        },
    }


def write_json(path, value, *, replace=False):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp") if replace else path
    with temporary.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    if replace:
        temporary.replace(path)


def write_checkpoint(path, spec, state, *, execution, provenance=None):
    values = validate_state(spec, state)
    path = Path(path)
    path.mkdir(parents=True, exist_ok=False)
    # Same lossless NPZ arrays and reader, with fast deflate instead of the
    # library's level-six default. Publish the manifest after the payload is durable.
    with (path / "state.npz").open("xb") as stream:
        with zipfile.ZipFile(
            stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1
        ) as archive:
            for name, value in values._asdict().items():
                with archive.open(f"{name}.npy", "w", force_zip64=True) as member:
                    np.lib.format.write_array(member, value, allow_pickle=False)
        stream.flush()
        os.fsync(stream.fileno())
    manifest = {
        "format": "cells_assembly_checkpoint@1",
        "definition": spec.to_dict(),
        "definition_sha256": spec.fingerprint,
        "sources_sha256": source_identity(),
        "state_sha256": digest(path / "state.npz"),
        "state_encoding": {"container": "npz", "compression": "deflate", "level": 1},
        "runtime": runtime(),
        "execution": execution,
        "provenance": provenance or {},
        "rng": "threefry2x32_fold_in_seed_world_event_open52@1",
        "world_ids": {"first": spec.world_id_start, "count": spec.worlds},
        "complete_state_includes_pending_event": True,
    }
    write_json(path / "manifest.json", manifest)
    return digest(path / "manifest.json")


def load_checkpoint(path):
    path = Path(path)
    record = json.loads((path / "manifest.json").read_text())
    if record.get("format") != "cells_assembly_checkpoint@1":
        raise AssemblyError("Unsupported assembly checkpoint")
    spec = parse_spec(record["definition"])
    if record["definition_sha256"] != spec.fingerprint:
        raise AssemblyError("Checkpoint definition digest mismatch")
    if record["sources_sha256"] != source_identity():
        raise AssemblyError("Checkpoint source identity differs; use its preserved source")
    if record["runtime"] != runtime():
        raise AssemblyError("Checkpoint runtime differs; cross-runtime continuation is unqualified")
    if record["state_sha256"] != digest(path / "state.npz"):
        raise AssemblyError("Checkpoint state digest mismatch")
    if record["rng"] != "threefry2x32_fold_in_seed_world_event_open52@1":
        raise AssemblyError("Checkpoint random stream identity mismatch")
    if record["world_ids"] != {"first": spec.world_id_start, "count": spec.worlds}:
        raise AssemblyError("Checkpoint world IDs differ from the random stream definition")
    with zipfile.ZipFile(path / "state.npz") as archive:
        if sum(item.file_size for item in archive.infolist()) > spec.worlds * 1024 + 65536:
            raise AssemblyError("Checkpoint exceeds its uncompressed array budget")
    with np.load(path / "state.npz", allow_pickle=False) as arrays:
        if set(arrays.files) != set(AssemblyState._fields):
            raise AssemblyError("Checkpoint fields differ from complete event state")
        state = AssemblyState(*(arrays[name].copy() for name in AssemblyState._fields))
    return spec, validate_state(spec, state), digest(path / "manifest.json")
