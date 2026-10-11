"""One persistent JAX process per GPU; scientific worlds never change owners."""

import os
import signal
import time
import traceback
from pathlib import Path


class PauseRequested(Exception):
    pass


def worker(root, slot, gpu, affinity, work, stopping, parents):
    root = Path(root)
    signal.signal(signal.SIGUSR1, lambda *_: stopping.set())
    signal.signal(signal.SIGTERM, lambda *_: stopping.set())
    os.environ["CUDA_VISIBLE_DEVICES"] = gpu["uuid"]
    os.environ.pop("JAX_PLATFORMS", None)
    os.sched_setaffinity(0, affinity)
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        os.environ[name] = str(len(affinity))
    # No accelerator imports before device visibility and CPU affinity are set.
    import numpy as np

    from cells.assembly.io import digest, runtime, write_json
    from cells.ensemble.families import (
        failure_state,
        first_completion,
        model_id,
        parse_definition,
        population,
        progress,
        runtime_for,
    )

    write_json(
        root / f"worker-{slot}-started.json",
        {
            "pid": os.getpid(),
            "gpu": gpu,
            "affinity": affinity,
            "runtime": runtime(),
            "time": time.time(),
        },
    )
    warmed = False
    while not stopping.is_set():
        task = work.get()
        if task is None:
            break
        directory = root / "tasks" / task["id"]
        directory.mkdir()
        began = time.time()
        spec = parse_definition(task["definition"])
        run, load_checkpoint, write_checkpoint = runtime_for(spec)
        last = None
        heartbeat = 0.0
        try:
            parent = parents.get(task["id"])
            state = None
            if parent:
                old, state, fingerprint = load_checkpoint(parent["path"])
                if old.fingerprint != spec.fingerprint or fingerprint != parent["sha256"]:
                    raise ValueError("Registered task continuation changed")

            def record(chunk, current, trace, *, directory=directory, spec=spec):
                nonlocal last, heartbeat, warmed
                last = current
                now = time.time()
                if not warmed:
                    write_json(root / f"worker-{slot}-warm.json", {"time": now, "gpu": gpu})
                    warmed = True
                if now - heartbeat >= 10:
                    write_json(
                        directory / "status.json",
                        {
                            "status": "running",
                            "chunk": chunk,
                            **progress(spec, current),
                            "time": now,
                            "slot": slot,
                        },
                        replace=True,
                    )
                    heartbeat = now
                if stopping.is_set():
                    raise PauseRequested()

            state, result = run(spec, backend="gpu", state=state, callback=record)
            checkpoint = directory / "checkpoint"
            t0 = time.monotonic()
            fingerprint = write_checkpoint(
                checkpoint,
                spec,
                state,
                execution={"backend": "gpu", "device_index": 0, "device_kind": gpu["name"]},
                provenance=parent,
            )
            checkpoint_s = time.monotonic() - t0
            t0 = time.monotonic()
            passage = first_completion(spec, state)
            observations = {}
            if model_id(spec) in ("finite_bond_assembly@1", "assembly_regulated_cell@1"):
                result["completed_shells"] = int((passage >= 0).sum())
                result["completion_event"] = "first_full_20_site_30_bond_cage"
            if passage is not None:
                horizon = population(spec).end_time_s
                samples = np.linspace(0.0, horizon, 61)
                observations = {
                    "survival_times_s": samples.tolist(),
                    "not_completed_counts": [
                        int(((passage < 0) | (passage > t)).sum()) for t in samples
                    ],
                    "restricted_wait_sum_s": float(np.where(passage >= 0, passage, horizon).sum()),
                }
            result.update(
                {
                    "status": "completed",
                    "task": task["id"],
                    "arm": task["arm"],
                    "slot": slot,
                    "gpu_uuid": gpu["uuid"],
                    "wall_start": began,
                    "definition": spec.to_dict(),
                    "checkpoint_manifest_sha256": fingerprint,
                    "checkpoint_seconds": checkpoint_s,
                    **observations,
                }
            )
            result["observation_seconds"] = time.monotonic() - t0
            result["wall_end"] = time.time()
            write_json(directory / "result.json", result)
        except PauseRequested:
            checkpoint = directory / "checkpoint-paused"
            write_checkpoint(
                checkpoint,
                spec,
                last,
                execution={"backend": "gpu", "device_index": 0, "device_kind": gpu["name"]},
                provenance=parents.get(task["id"]),
            )
            write_json(
                directory / "paused.json",
                {
                    "status": "paused",
                    "task": task["id"],
                    "checkpoint": str(checkpoint),
                    "sha256": digest(checkpoint / "manifest.json"),
                    "time": time.time(),
                },
            )
            break
        except BaseException as exc:
            if last is not None:
                np.savez_compressed(directory / "failure-state.npz", **failure_state(spec, last))
            write_json(
                directory / "failure.json",
                {
                    "status": "failed",
                    "task": task["id"],
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                    "time": time.time(),
                },
            )
            # Other registered tasks remain useful; preserve this failure without retrying it.
    write_json(
        root / f"worker-{slot}-finished.json", {"time": time.time(), "stopping": stopping.is_set()}
    )
