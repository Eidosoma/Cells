"""Portable numeric artifacts, strict restoration, and non-overwriting output."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from time import perf_counter

import jax
import numpy as np

import cells
from cells.core.devices import execution_device
from cells.core.runner import RunResult, validate_checkpoint
from cells.core.specs import ConfigError, SimulationSpec, digest, parse_spec, read_json
from cells.core.state import Checkpoint
from cells.models.registry import get_model

RUNTIME_PACKAGES = ("jax", "jaxlib", "numpy", "scipy", "ml_dtypes", "opt_einsum")


def source_hashes() -> dict[str, str]:
    root = Path(cells.__file__).parent
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*.py"))
    }


def runtime_identity(backend="cpu") -> dict:
    result = {
        "cells_version": cells.__version__,
        "python": platform.python_version(),
        "packages": {name: metadata.version(name) for name in RUNTIME_PACKAGES},
        "platform": platform.system(),
        "machine": platform.machine(),
        "numerical_environment": {
            name: os.environ.get(name) for name in ("XLA_FLAGS", "JAX_DISABLE_JIT")
        },
    }
    if backend == "gpu":
        device = execution_device(backend)
        result["gpu"] = {
            "device_kind": device.device_kind,
            "platform": device.platform,
            "platform_version": device.client.platform_version,
            "packages": {
                d.metadata["Name"]: d.version
                for d in metadata.distributions()
                if d.metadata["Name"].lower().startswith(("nvidia-", "jax-cuda"))
            },
        }
    return result


def _sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _write_json(path: Path, value: dict) -> None:
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


@dataclass(frozen=True)
class Snapshot:
    spec: SimulationSpec
    checkpoint: Checkpoint
    fingerprint: str


def write_snapshot(directory: str | Path, spec: SimulationSpec, checkpoint: Checkpoint) -> Path:
    spec = parse_spec(spec.to_dict())
    validate_checkpoint(spec, checkpoint)
    return _write_snapshot_payload(directory, spec, checkpoint)


def _write_snapshot_payload(directory, spec, checkpoint, *, identity=None):
    """Internal writer: caller has validated definition, numerical clock and state."""
    # A cohort publisher may share an identity captured for this publication,
    # provided it rechecks that identity before publishing its final manifest.
    # Ordinary scalar callers still collect a fresh identity for each snapshot.
    if identity is None:
        identity = {
            "runtime": runtime_identity(spec.execution.backend),
            "source_hashes": source_hashes(),
        }
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=False)
    arrays = dict(zip(checkpoint.state._fields, checkpoint.state, strict=True))
    arrays.update(zip(checkpoint.layout._fields, checkpoint.layout, strict=True))
    np.savez(path / "state.npz", **{name: np.asarray(value) for name, value in arrays.items()})
    manifest = {
        "schema_version": 1,
        "kind": "cells_complete_numerical_checkpoint",
        "spec": spec.to_dict(),
        "spec_sha256": spec.fingerprint,
        "clock": {
            "time": checkpoint.time,
            "step_index": checkpoint.step_index,
            "event_index": checkpoint.event_index,
        },
        "random_state": None,
        "runtime": identity["runtime"],
        "source_hashes": identity["source_hashes"],
        "state_sha256": _sha256(path / "state.npz"),
    }
    manifest["manifest_sha256"] = digest(manifest)
    # Written last: a partial directory without a valid manifest cannot be restored.
    _write_json(path / "manifest.json", manifest)
    return path


def load_snapshot(directory: str | Path) -> Snapshot:
    path = Path(directory)
    manifest = read_json(path / "manifest.json")
    expected_fields = {
        "schema_version",
        "kind",
        "spec",
        "spec_sha256",
        "clock",
        "random_state",
        "runtime",
        "source_hashes",
        "state_sha256",
        "manifest_sha256",
    }
    if not isinstance(manifest, dict) or set(manifest) != expected_fields:
        raise ConfigError("Invalid checkpoint manifest fields")
    fingerprint = manifest.pop("manifest_sha256")
    if digest(manifest) != fingerprint:
        raise ConfigError("Checkpoint manifest checksum mismatch")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        raise ConfigError("Unsupported checkpoint schema")
    if manifest["kind"] != "cells_complete_numerical_checkpoint":
        raise ConfigError("Not a complete Cells numerical checkpoint")
    if manifest["random_state"] is not None:
        raise ConfigError("These deterministic models have no random state")
    if manifest["source_hashes"] != source_hashes():
        raise ConfigError("Checkpoint model/engine source differs from this installation")
    spec = parse_spec(manifest["spec"])
    if manifest["runtime"] != runtime_identity(spec.execution.backend):
        raise ConfigError("Checkpoint runtime differs; cross-runtime migration is not supported")
    model = get_model(spec.model)
    if spec.fingerprint != manifest["spec_sha256"]:
        raise ConfigError("Checkpoint specification checksum mismatch")
    if _sha256(path / "state.npz") != manifest["state_sha256"]:
        raise ConfigError("Checkpoint state checksum mismatch")
    clock = manifest["clock"]
    if not isinstance(clock, dict) or set(clock) != {"time", "step_index", "event_index"}:
        raise ConfigError("Invalid checkpoint clock fields")
    if isinstance(clock["time"], bool) or not isinstance(clock["time"], (int, float)):
        raise ConfigError("Invalid checkpoint time")
    try:
        with np.load(path / "state.npz", allow_pickle=False) as archive:
            if set(archive.files) != set(model.STATE_TYPE._fields + model.LAYOUT_TYPE._fields):
                raise ConfigError("Invalid checkpoint state fields")
            state = model.STATE_TYPE(*(archive[name] for name in model.STATE_TYPE._fields))
            layout = model.LAYOUT_TYPE(*(archive[name] for name in model.LAYOUT_TYPE._fields))
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        raise ConfigError(f"Cannot read numeric checkpoint: {exc}") from exc
    checkpoint = Checkpoint(state, layout, **clock)
    validate_checkpoint(spec, checkpoint)
    device = execution_device(spec.execution.backend)
    checkpoint = Checkpoint(jax.device_put(state, device), jax.device_put(layout, device), **clock)
    return Snapshot(spec, checkpoint, fingerprint)


def write_run(
    directory: str | Path,
    result: RunResult,
    *,
    checkpoint_times: tuple[float, ...] = (),
    provenance: dict | None = None,
) -> dict:
    # Check requested boundaries before creating any output.
    checkpoints = [(time, result.checkpoint_at(time)) for time in sorted(set(checkpoint_times))]
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    started = perf_counter()
    obs = result.observations
    model = get_model(result.spec.model)
    arrays = dict(zip(result.history._fields, result.history, strict=True))
    arrays.update(
        {
            "cell_ids" if name == "ids" else name: np.asarray(value)
            for name, value in zip(result.final.layout._fields, result.final.layout, strict=True)
        }
    )
    arrays.update(
        {
            "observation_times" if name == "times" else f"observed_{name}": value
            for name, value in vars(obs).items()
        }
    )
    np.savez(
        directory / "trajectory.npz",
        accepted_times=result.times,
        **arrays,
    )
    _write_json(directory / "resolved_config.json", result.spec.to_dict())
    snapshot_paths = []
    for _, checkpoint in checkpoints:
        name = f"snapshots/step-{checkpoint.step_index:06d}"
        write_snapshot(directory / name, result.spec, checkpoint)
        snapshot_paths.append(name)
    write_snapshot(directory / "checkpoint_final", result.spec, result.final)
    summary = {
        "status": "complete",
        "start_time": float(result.times[0]),
        "end_time": result.final.time,
        "executed_steps": len(result.times) - 1,
        "global_step_index": result.final.step_index,
        "active_cells": int(np.count_nonzero(result.final.layout.active)),
        "capacity": result.spec.execution.capacity,
        "cell_ids": np.asarray(result.final.layout.ids)[
            np.asarray(result.final.layout.active)
        ].tolist(),
        **model.summarize(result.history, result.diagnostics, result.spec),
    }
    if summary["active_cells"] == 1:
        summary["cell_id"] = summary["cell_ids"][0]  # Original single-cell summary compatibility.
    _write_json(directory / "summary.json", summary)
    checksums = {
        str(path.relative_to(directory)): _sha256(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }
    manifest = {
        "schema_version": 1,
        "status": "complete",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "definition_sha256": result.spec.fingerprint,
        "runtime": runtime_identity(result.spec.execution.backend),
        "source_hashes": source_hashes(),
        "device": str(execution_device(result.spec.execution.backend)),
        "cpu_affinity": sorted(os.sched_getaffinity(0))
        if hasattr(os, "sched_getaffinity")
        else None,
        "observer": {
            "id": model.OBSERVER_ID,
            "sampling": getattr(model, "OBSERVATION_SAMPLING", "read_only_linear_interpolation"),
        },
        "numerics": {
            "grid": "zero_anchored_event_split",
            "jit": result.spec.execution.jit,
            **(
                {"stage_domain": model.STAGE_DOMAIN_ID} if hasattr(model, "STAGE_DOMAIN_ID") else {}
            ),
        },
        "random_state": "unused: deterministic model",
        "timings": {
            **result.timings,
            "artifact_payload_write_seconds": perf_counter() - started,
        },
        "timing_scope": "payload timing excludes final manifest publication; no GPU benchmark",
        "provenance": provenance or {"operation": "fresh"},
        "snapshots": snapshot_paths + ["checkpoint_final"],
        "files_sha256": checksums,
    }
    _write_json(directory / "manifest.json", manifest)
    return summary
