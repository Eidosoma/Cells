"""Unchanged public production runner, output/checkpoint APIs and exact restarts."""

import sys

import pilot_context as ctx
from pilot_math import canonical

c = ctx.c


def worker(r, output):
    import jax
    import numpy as np

    from cells.core.runner import run
    from cells.core.specs import parse_spec
    from cells.io import load_snapshot, write_run

    c.require(
        jax.default_backend() == "cpu"
        and jax.config.x64_enabled
        and not jax.config.jax_disable_jit,
        "Require CPU float64/JIT",
    )
    records, resumes = {}, {}
    for identifier, case in r["cases"].items():
        choices = [(True, h) for h in r["protocol"]["cells_steps_s"]] + [
            (False, r["protocol"]["cells_eager_step_s"])
        ]
        for jit, step in choices:
            definition = ctx.definition(case, step, jit=jit)
            spec = parse_spec(definition)
            result = run(spec)
            key = ctx.key(identifier, step) + ("/jax_jit" if jit else "/jax_eager")
            directory = output / "cells" / key
            checkpoints = (
                (r["protocol"]["restart_time_s"],)
                if jit and step == r["protocol"]["restart_step_s"]
                else ()
            )
            write_run(
                directory,
                result,
                checkpoint_times=checkpoints,
                provenance=dict(protocol="REF-005c_D117", matched_case=identifier),
            )
            observed = {
                name: np.asarray(value) for name, value in vars(result.observations).items()
            }
            points = [
                canonical({name: observed[name][i].tolist() for name in ctx.STATE_FIELDS})
                for i in range(len(observed["times"]))
            ]
            record = dict(
                case=identifier,
                step_s=step,
                jit=jit,
                directory=str(directory.relative_to(output)),
                times_s=observed["times"].tolist(),
                states=points,
                voltage_V=observed["voltage_V"][:, :7].tolist(),
                diagnostics={k: float(v) for k, v in result.diagnostics.items()},
            )
            records[key] = record
            if checkpoints:
                index = result.checkpoint_at(checkpoints[0]).step_index
                loaded = load_snapshot(directory / f"snapshots/step-{index:06d}")
                resumed = run(loaded.spec, loaded.checkpoint)
                resume_directory = directory / "resumed"
                write_run(resume_directory, resumed)
                c.require(
                    np.array_equal(result.times[index:], resumed.times), "Restart time suffix"
                )
                c.require(
                    all(
                        np.array_equal(np.asarray(a)[index:], np.asarray(b))
                        for a, b in zip(result.history, resumed.history, strict=True)
                    ),
                    "Restart full-state suffix",
                )
                c.require(
                    all(
                        np.array_equal(a, b)
                        for a, b in zip(result.final.layout, resumed.final.layout, strict=True)
                    ),
                    "Restart layout",
                )
                resumes[key] = dict(
                    directory=str(resume_directory.relative_to(output)),
                    full_state_bitwise_equal=True,
                    start_step=index,
                )
            print("Cells trajectory captured: " + key, flush=True)
    c.require(
        len(records) == 24
        and len(resumes) == 6
        and not any(n == "betse" or n.startswith("betse.") for n in sys.modules),
        "Cells coverage/isolation",
    )
    return dict(
        engine="unchanged_cells_checked_rk4",
        records=records,
        resumes=resumes,
        trajectories=24,
        restart_suffixes=6,
        device="cpu",
        precision="float64",
        runtime=ctx.runtime(),
        numpy_integrator_used=False,
    )
