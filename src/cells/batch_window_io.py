"""One incremental cohort index, independent clocks, and complete restart rounds."""

from pathlib import Path
from time import perf_counter

from cells.batch_io import _write_batch_snapshot_payload
from cells.core.batch_windows import (
    _consume_batch_windows,
    _initial_checkpoints,
    plan_batch_windows,
)
from cells.core.devices import execution_device
from cells.core.specs import ConfigError, _integer, canonical_json
from cells.core.windows import DEFAULT_POLICY
from cells.io import _sha256, _write_json, runtime_identity, source_hashes
from cells.models.registry import get_model
from cells.window_io import _write_window_chunk


def write_windowed_batch(
    directory,
    spec,
    policy=DEFAULT_POLICY,
    checkpoints=None,
    *,
    checkpoint_every_windows=0,
    provenance=None,
):
    """Record fully checked rounds; cadence counts rounds, never biological time."""
    started = perf_counter()
    directory = Path(directory)
    if directory.exists():
        raise ConfigError(f"Output already exists; choose a new directory: {directory}")
    cadence = _integer(checkpoint_every_windows, "checkpoint_every_windows", minimum=0)
    plan = plan_batch_windows(spec, policy, checkpoints)
    spec, policy = plan.spec, plan.policy
    starts = _initial_checkpoints(plan, checkpoints)
    preflight_seconds = perf_counter() - started
    directory.mkdir(parents=True, exist_ok=False)
    _write_json(directory / "resolved_batch.json", spec.to_dict())
    _write_batch_snapshot_payload(directory / "checkpoint_initial", spec, starts)
    records = {
        w.world_id: {
            "world_id": w.world_id,
            "windows": 0,
            "saved_accepted_records": 0,
            "saved_observation_records": 0,
            "chunk_payload_bytes": 0,
        }
        for w in spec.worlds
    }
    snapshot_count = 0
    with (directory / "windows.jsonl").open("x") as index:

        def consume(window):
            nonlocal snapshot_count
            for identity, world in window.worlds.items():
                total = records[identity]
                prefix = f"worlds/world-{identity}"
                record, size = _write_window_chunk(
                    directory / prefix, world, policy, total["windows"]
                )
                record.update(kind="world_window", world_id=identity, round=window.index)
                if record["path"] is not None:
                    record["path"] = f"{prefix}/{record['path']}"
                index.write(canonical_json(record) + "\n")
                total["windows"] += 1
                total["saved_accepted_records"] += record["accepted_records"]
                total["saved_observation_records"] += record["observation_records"]
                total["chunk_payload_bytes"] += size
            complete = all(
                window.checkpoints[w.world_id].time == w.simulation.experiment.end_time
                for w in spec.worlds
            )
            completed_rounds = window.index + 1
            if cadence and completed_rounds % cadence == 0 and not complete:
                name = f"snapshots/round-{completed_rounds:010d}"
                _write_batch_snapshot_payload(directory / name, spec, window.checkpoints)
                index.write(
                    canonical_json(
                        {
                            "kind": "cohort_checkpoint",
                            "completed_rounds": completed_rounds,
                            "path": name,
                            "manifest_sha256": _sha256(directory / name / "manifest.json"),
                        }
                    )
                    + "\n"
                )
                snapshot_count += 1
            index.flush()

        result = _consume_batch_windows(
            plan,
            starts,
            consume,
            started=started,
            preflight_seconds=preflight_seconds,
        )
    _write_batch_snapshot_payload(directory / "checkpoint_final", spec, result.checkpoints)
    summary = {
        "status": "complete",
        "worlds": len(spec.worlds),
        "world_ids": [w.world_id for w in spec.worlds],
        "rounds": result.resources["rounds"],
        "world_summaries": {str(i): w.summary() for i, w in result.worlds.items()},
    }
    _write_json(directory / "summary.json", summary)
    # Fixed O(worlds) inventory. The index authenticates all chunk payloads and
    # periodic cohort manifests; each cohort manifest authenticates its children.
    fixed = ["resolved_batch.json", "summary.json", "windows.jsonl"]
    for checkpoint in ("checkpoint_initial", "checkpoint_final"):
        fixed.append(f"{checkpoint}/manifest.json")
        for world in spec.worlds:
            fixed.extend(
                f"{checkpoint}/world-{world.world_id}/{name}"
                for name in ("manifest.json", "state.npz")
            )
    model = get_model(spec.worlds[0].simulation.model)
    _write_json(
        directory / "manifest.json",
        {
            "schema_version": 1,
            "kind": "cells_windowed_independent_world_run",
            "status": "complete",
            "definition_sha256": spec.fingerprint,
            "runtime": runtime_identity(spec.worlds[0].simulation.execution.backend),
            "source_hashes": source_hashes(),
            "device": str(execution_device(spec.worlds[0].simulation.execution.backend)),
            "mapping": spec.mapping,
            "policy": policy.to_dict(),
            "checkpoint_every_windows": cadence,
            "index": "windows.jsonl",
            "files_sha256": {name: _sha256(directory / name) for name in fixed},
            "worlds": list(records.values()),
            "observer": {
                "id": model.OBSERVER_ID,
                "sampling": getattr(
                    model, "OBSERVATION_SAMPLING", "read_only_linear_interpolation"
                ),
            },
            "numerics": {
                "grid": "independent_zero_anchored_event_split",
                "jit": spec.worlds[0].simulation.execution.jit,
                **(
                    {"stage_domain": model.STAGE_DOMAIN_ID}
                    if hasattr(model, "STAGE_DOMAIN_ID")
                    else {}
                ),
            },
            "resources": result.resources | {"periodic_snapshots": snapshot_count},
            "timings": result.timings | {"payload_complete_seconds": perf_counter() - started},
            "timing_scope": (
                "Shared CPU wall time including synchronous recording, excluding final manifest "
                "publication; not a GPU benchmark"
            ),
            "provenance": provenance or {"operation": "windowed_batch_fresh"},
        },
    )
    return summary
