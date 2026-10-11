"""Actual production eager/compiled checked-RK4 and complete checkpoint resume."""

import sys

import feedback_context as ctx
import feedback_io as io

c = ctx.c


def record_result(result, identifier, definition):
    from cells.io import runtime_identity

    array = ctx.audit.preparation.array_record
    return {
        "id": identifier,
        "definition": definition,
        "canonical_definition": result.spec.to_dict(),
        "times": array(result.times),
        "history": {name: array(v) for name, v in result.history._asdict().items()},
        "observations": {name: array(v) for name, v in vars(result.observations).items()},
        "diagnostics": {name: float(v) for name, v in result.diagnostics.items()},
        "timings": result.timings,
        "start_step": result.start_step,
        "final_step_index": result.final.step_index,
        "runtime": runtime_identity(),
    }


def worker(r, output):
    import jax
    import numpy as np

    from cells.core.runner import run
    from cells.core.specs import parse_spec
    from cells.io import load_snapshot, runtime_identity, write_snapshot
    from cells.models import finite_extracellular as model

    c.require(
        jax.default_backend() == "cpu"
        and jax.config.x64_enabled
        and not jax.config.jax_disable_jit,
        "Require CPU float64 with enabled JIT",
    )
    c.require(
        runtime_identity() == r["preparation_registration"]["cells_runtime"],
        "Accepted Cells runtime differs",
    )
    records, resumes = {}, {}
    for identifier, definition in r["cells_definitions"].items():
        spec = parse_spec(definition)
        result = run(spec)
        directory = output / "cells" / identifier
        directory.mkdir(parents=True, exist_ok=False)
        io.write_compressed(
            directory / "result.json.gz", record_result(result, identifier, definition)
        )
        write_snapshot(directory / "final-checkpoint", spec, result.final)
        records[identifier] = str((directory / "result.json.gz").relative_to(output))
        if identifier.endswith(f"jax_jit/dt_{r['protocol']['restart_step_s']:.8g}"):
            checkpoint = result.checkpoint_at(r["protocol"]["restart_time_s"])
            write_snapshot(directory / "midpoint-checkpoint", spec, checkpoint)
            restored = load_snapshot(directory / "midpoint-checkpoint")
            c.require(
                all(
                    np.array_equal(a, b)
                    for a, b in zip(checkpoint.state, restored.checkpoint.state, strict=True)
                ),
                "Full restored state differs",
            )
            c.require(
                all(
                    np.array_equal(a, b)
                    for a, b in zip(checkpoint.layout, restored.checkpoint.layout, strict=True)
                ),
                "Restored layout differs",
            )
            resumed = run(restored.spec, restored.checkpoint)
            io.write_compressed(
                directory / "resumed.json.gz", record_result(resumed, identifier, definition)
            )
            write_snapshot(directory / "resumed-checkpoint", spec, resumed.final)
            resumes[identifier] = str((directory / "resumed.json.gz").relative_to(output))
        print(f"Cells trajectory completed: {identifier}", flush=True)
    c.require(
        not any(n.split(".")[0] == "betse" for n in sys.modules), "Cells imported native model"
    )
    return {
        "engine": "unchanged_cells_checked_rk4_eager_and_jit",
        "records": records,
        "resumed": resumes,
        "accepted_runtime": runtime_identity(),
        "source_path": model.__file__,
        "source_sha256": c.sha(model.__file__),
        "cells_trajectories": len(records),
        "resumed_segments": len(resumes),
        "device": "cpu",
        "x64_enabled": True,
        "numpy_trajectory_runner_used": False,
        "trajectory_run": True,
    }
