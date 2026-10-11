"""Small real CPU/GPU and native-decoder checks before a detached campaign."""

import argparse
import time
import traceback
from pathlib import Path

import common as u


def cpu(output, preparation):
    from cells.core.runner import run
    from cells.core.specs import parse_spec
    from cells.io import write_run

    u.module_path("pump_matched_pilot")
    import pilot_context as ctx

    plan = u.plan(0.001)
    case = dict(preparation["cases"]["pump_leak"], end_time_s=0.001)
    records = {}
    for dt in plan["cells_steps_s"]:
        result = run(parse_spec(ctx.definition(case, dt, times=plan["common_times_s"])))
        key = ctx.key("pump_leak", dt) + "/jax_jit"
        directory = output / "cells" / key
        write_run(directory, result)
        records[key] = dict(directory=str(directory.relative_to(output)), timings=result.timings)
    u.write(output / "cells.json", dict(records=records))
    return dict(checked_trajectories=3, records=records)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("phase", choices=("cpu", "gpu", "native", "review"))
    p.add_argument("output", type=Path)
    p.add_argument("--preparation", type=Path, required=True)
    args = p.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    frozen = u.sources()
    u.write(
        output / "registration.json",
        dict(
            phase=args.phase,
            preparation=str(args.preparation),
            preparation_sha256=u.sha(args.preparation),
            sources_sha256=frozen,
            purpose="Short engineering check, not 10 ms qualification",
        ),
    )
    preparation = u.read(args.preparation)
    start = time.monotonic()
    try:
        if args.phase == "cpu":
            result = cpu(output, preparation)
        elif args.phase == "gpu":
            import workers

            result = workers.gpu(
                output, preparation, u.plan(0.001), output.parent / "cpu", variants=("pump_leak",)
            )
        elif args.phase == "native":
            import prepare

            result = prepare.capture(
                output / "capture",
                Path("/mnt/workspaces/Cells"),
                preparation,
                "pump_only",
                0,
                "observed",
                0.0002,
            )
        else:
            import fresh_review

            saved, reader, clocks = fresh_review.modules()
            e = saved.e
            with e.model_fence():
                row, facts = reader.read(output.parent / "native/capture/stream")
                baseline = preparation["rows"]["pump_only/observed"]
                variant = next(
                    v
                    for v in preparation["native_preparation"]["protocol"]["variants"]
                    if v["id"] == "pump_only"
                )
                plan = dict(u.plan(), duration_s=0.0002, common_times_s=[0.0, 0.0002])
                saved.native_records.identity(row, baseline, 6.25e-6, 0.0002, "observed")
                ledger = e.Ledger()
                physics = clocks.inspect(
                    saved.native_records, saved.c.exact.Exact, row, baseline, plan, variant, ledger
                )
                points = saved.native_energy.reconstruct(
                    row, variant, plan["common_times_s"], ledger
                )
            result = dict(
                format=facts, physics=physics, points=points, independent_comparisons=ledger.count
            )
        u.need(frozen == u.sources(), "Source changed during smoke")
        u.write(
            output / "completion.json",
            dict(
                status="smoke_pass",
                phase=args.phase,
                elapsed_seconds=time.monotonic() - start,
                result=result,
                sources_sha256=frozen,
                files_sha256=u.inventory(output),
            ),
        )
        print(
            {
                "phase": args.phase,
                "status": "smoke_pass",
                "elapsed_seconds": time.monotonic() - start,
            }
        )
    except BaseException:
        u.write(
            output / "failure.json", dict(status="smoke_failed", traceback=traceback.format_exc())
        )
        raise


if __name__ == "__main__":
    main()
