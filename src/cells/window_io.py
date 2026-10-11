"""Incremental numeric recording; the completion manifest is published last."""

from pathlib import Path
from time import perf_counter

import numpy as np

from cells.core.devices import execution_device
from cells.core.runner import validate_checkpoint
from cells.core.specs import ConfigError, _number, canonical_json
from cells.core.state import initialise
from cells.core.windows import DEFAULT_POLICY, _consume_windows, plan_windows
from cells.io import _sha256, _write_json, _write_snapshot_payload, runtime_identity, source_hashes
from cells.models.registry import get_model


def _write_window_chunk(directory, window, policy, window_index):
    """Shared scalar payload format; callers own indexing and cohort publication."""
    arrays = {}
    skip = 0 if window_index == 0 else 1
    accepted = len(window.times) - skip if policy.recording == "full" else 0
    observed = len(window.observations.times) if policy.recording != "checkpoints" else 0
    if policy.recording == "full":
        arrays["accepted_times"] = window.times[skip:]
        arrays.update(
            {k: v[skip:] for k, v in zip(window.history._fields, window.history, strict=True)}
        )
    if observed:
        arrays.update(
            {
                "observation_times" if k == "times" else f"observed_{k}": v
                for k, v in vars(window.observations).items()
            }
        )
    filename, checksum, payload_bytes = None, None, 0
    if arrays:
        filename = f"chunks/window-{window_index:08d}.npz"
        path = directory / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            np.savez(handle, **arrays)
        checksum = _sha256(path)
        payload_bytes = path.stat().st_size
    return {
        "kind": "window",
        "index": window_index,
        "start_step": window.start_step,
        "end_step": window.final.step_index,
        "start_time": float(window.times[0]),
        "end_time": window.final.time,
        "accepted_records": accepted,
        "observation_records": observed,
        "validated_observations": len(window.observations.times),
        "diagnostics": window.diagnostics,
        "path": filename,
        "sha256": checksum,
    }, payload_bytes


def write_windowed_run(
    directory, spec, policy=DEFAULT_POLICY, checkpoint=None, *, checkpoint_times=(), provenance=None
):
    """Run and record incrementally, without a horizon-sized payload/hash inventory."""
    started = perf_counter()
    directory = Path(directory)
    if directory.exists():
        raise ConfigError(f"Output already exists; choose a new directory: {directory}")
    plan = plan_windows(spec, policy, checkpoint)
    spec, policy = plan.spec, plan.policy
    requested = sorted({_number(t, "checkpoint time") for t in checkpoint_times})
    for time in requested:
        if time < plan.grid[plan.start_step]:
            raise ConfigError("Requested checkpoint precedes the continuation")
        plan.grid.exact_index(time)
    checkpoint = initialise(spec) if checkpoint is None else checkpoint
    validate_checkpoint(spec, checkpoint, plan.grid)
    preflight_seconds = perf_counter() - started
    directory.mkdir(parents=True, exist_ok=False)
    _write_json(directory / "resolved_config.json", spec.to_dict())
    _write_snapshot_payload(directory / "checkpoint_initial", spec, checkpoint)
    index_path = directory / "windows.jsonl"
    checkpoint_index = window_index = 0
    saved_accepted = saved_observations = payload_bytes = 0

    with index_path.open("x") as index:

        def consume(window):
            nonlocal \
                checkpoint_index, \
                window_index, \
                saved_accepted, \
                saved_observations, \
                payload_bytes
            record, size = _write_window_chunk(directory, window, policy, window_index)
            saved_accepted += record["accepted_records"]
            saved_observations += record["observation_records"]
            payload_bytes += size
            index.write(canonical_json(record) + "\n")
            while (
                checkpoint_index < len(requested)
                and requested[checkpoint_index] <= window.final.time
            ):
                saved = window.checkpoint_at(requested[checkpoint_index])
                name = f"snapshots/step-{saved.step_index:010d}"
                _write_snapshot_payload(directory / name, spec, saved)
                index.write(
                    canonical_json(
                        {
                            "kind": "checkpoint",
                            "step_index": saved.step_index,
                            "time": saved.time,
                            "path": name,
                            "manifest_sha256": _sha256(directory / name / "manifest.json"),
                            "state_sha256": _sha256(directory / name / "state.npz"),
                        }
                    )
                    + "\n"
                )
                checkpoint_index += 1
            index.flush()
            window_index += 1

        result = _consume_windows(
            plan, checkpoint, consume, started=started, preparation_seconds=preflight_seconds
        )
    _write_snapshot_payload(directory / "checkpoint_final", spec, result.final)
    summary = result.summary()
    _write_json(directory / "summary.json", summary)
    model = get_model(spec.model)
    fixed = (
        "resolved_config.json",
        "summary.json",
        "windows.jsonl",
        "checkpoint_initial/manifest.json",
        "checkpoint_initial/state.npz",
        "checkpoint_final/manifest.json",
        "checkpoint_final/state.npz",
    )
    _write_json(
        directory / "manifest.json",
        {
            "schema_version": 1,
            "kind": "cells_windowed_run",
            "status": "complete",
            "definition_sha256": spec.fingerprint,
            "runtime": runtime_identity(spec.execution.backend),
            "source_hashes": source_hashes(),
            "device": str(execution_device(spec.execution.backend)),
            "policy": policy.to_dict(),
            "index": "windows.jsonl",
            "files_sha256": {name: _sha256(directory / name) for name in fixed},
            "observer": {
                "id": model.OBSERVER_ID,
                "sampling": getattr(
                    model, "OBSERVATION_SAMPLING", "read_only_linear_interpolation"
                ),
            },
            "numerics": {
                "grid": "zero_anchored_event_split",
                "jit": spec.execution.jit,
                **(
                    {"stage_domain": model.STAGE_DOMAIN_ID}
                    if hasattr(model, "STAGE_DOMAIN_ID")
                    else {}
                ),
            },
            "resources": result.resources
            | {
                "saved_accepted_records": saved_accepted,
                "saved_observation_records": saved_observations,
                "chunk_payload_bytes": payload_bytes,
                "requested_snapshots": len(requested),
            },
            "timings": result.timings | {"payload_complete_seconds": perf_counter() - started},
            "timing_scope": (
                "CPU wall time; includes synchronous recording, excludes final manifest "
                "publication; not a GPU benchmark"
            ),
            "provenance": provenance or {"operation": "windowed_fresh"},
        },
    )
    return summary
