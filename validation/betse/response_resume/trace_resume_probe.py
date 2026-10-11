"""Production trace estimates AND actual timeline guards, never an ODE rollout."""

import argparse
import math
from datetime import UTC, datetime
from pathlib import Path

import trace_resume_context as ctx

c = ctx.c
GUARD = "Estimated trace working storage exceeds max_trace_bytes"


def probe(r):
    import jax

    from cells.core.resources import trace_bytes
    from cells.core.runner import timeline
    from cells.core.specs import ConfigError, parse_spec
    from cells.io import runtime_identity

    c.require(
        jax.default_backend() == "cpu"
        and jax.config.x64_enabled
        and not jax.config.jax_disable_jit
        and runtime_identity() == r["cells_runtime"],
        "Resource probe runtime differs",
    )
    original, rows = ctx.previous(), []
    for row in r["cells_rows"]:
        identifier = row["id"]
        spec = parse_spec(r["cells_definitions"][identifier])
        nominal = math.ceil(spec.experiment.end_time / spec.execution.dt)
        grid = timeline(spec)
        c.require(
            grid.tolist() == [k * spec.execution.dt for k in range(nominal)] + [0.001],
            "Production event-split grid differs from registered fixed-input grid",
        )
        old = parse_spec(original["cells_definitions"][identifier])
        rejected = False
        try:
            old_grid = timeline(old)
            c.require(old_grid.tolist() == grid.tolist(), "Resource-only change altered grid")
        except ConfigError as error:
            c.require(str(error) == GUARD, "Original input has a different configuration error")
            rejected = True
        rows.append(
            {
                "id": identifier,
                "nominal_steps": nominal,
                "event_split_steps": len(grid) - 1,
                "observation_count": len(spec.experiment.observation_times),
                "nominal_trace_bytes": trace_bytes(spec, nominal),
                "event_split_trace_bytes": trace_bytes(spec, len(grid) - 1),
                "old_max_trace_bytes": old.execution.max_trace_bytes,
                "max_trace_bytes": spec.execution.max_trace_bytes,
                "original_guard_rejected": rejected,
                "production_timeline_pass": True,
            }
        )
    return {
        "schema": "cells.betse_trace_resume_resource_probe@1",
        "status": "all_48_production_timelines_pass_no_integration",
        "created_utc": datetime.now(UTC).isoformat(),
        "rows": rows,
        "original_guard_rejections": sum(row["original_guard_rejected"] for row in rows),
        "largest_trace_estimate_bytes": max(row["event_split_trace_bytes"] for row in rows),
        "runtime": runtime_identity(),
        "failure_anchors": ctx.ANCHORS,
        "source_hashes": {
            n: c.sha(c.ROOT / n)
            for n in (
                "src/cells/core/resources.py",
                "src/cells/core/runner.py",
                "src/cells/core/specs.py",
                "validation/betse/response_resume/trace_resume_probe.py",
                "validation/betse/response_resume/trace_resume_context.py",
            )
        },
        "integration_calls": 0,
        "peak_RAM_measured": False,
        "gpu_tested": False,
    }


def validate(result, r):
    c.require(
        result["schema"] == "cells.betse_trace_resume_resource_probe@1"
        and result["status"] == "all_48_production_timelines_pass_no_integration"
        and result["failure_anchors"] == ctx.ANCHORS
        and result["runtime"] == r["cells_runtime"]
        and result["integration_calls"] == 0
        and result["peak_RAM_measured"] is False
        and result["gpu_tested"] is False
        and [v["id"] for v in result["rows"]] == [row["id"] for row in r["cells_rows"]]
        and result["original_guard_rejections"] == 8
        and result["largest_trace_estimate_bytes"] == 25838496
        and all(c.sha(c.ROOT / n) == h for n, h in result["source_hashes"].items()),
        "Resource probe identity/coverage/source differs",
    )
    changed = set(ctx.changed_ids(ctx.previous()))
    for row, saved in zip(r["cells_rows"], result["rows"], strict=True):
        steps = ctx.prior.count(row["hold_step_s"]) * row["subdivision"]
        observations = ctx.prior.count(row["hold_step_s"]) + 1
        expected = 8 * (4024 * (steps + 1 + observations) + 4 * (steps + 1))
        # Separate scalar reconstruction of this registered model's 4024-column reservation.
        # The actual runner.timeline call above is still required, not just parser acceptance.
        c.require(
            saved["nominal_steps"] == saved["event_split_steps"] == steps
            and saved["observation_count"] == observations
            and saved["nominal_trace_bytes"] == saved["event_split_trace_bytes"] == expected
            and saved["max_trace_bytes"]
            == r["cells_definitions"][row["id"]]["execution"]["max_trace_bytes"]
            and saved["old_max_trace_bytes"] == 16777216
            and saved["original_guard_rejected"] is (row["id"] in changed)
            and saved["production_timeline_pass"] is True
            and expected < saved["max_trace_bytes"],
            "Resource probe row differs",
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    r = ctx.inputs()
    result = probe(r)
    validate(result, r)
    c.write(args.output.resolve(), result)
    print("48 production timeline/resource checks pass; no integration")
