"""A restart with a rate change at the join (FR-25's follow-up, D251): a world of worlds.py run
uninterrupted, and run to the join, saved, and resumed from the checkpoint, in process and through
the snapshot files (records/io.py). Development, not judged.

The checkpoint is the composite's whole state (execution/state.Checkpoint), so it carries
cells.operator.templated_polymerisation@1's own fields: free machines, complexes per stage, the cumulative
initiations, stage exits, releases, degradations and transfers, every heat, and with a release
(FR-38) its hold, the releases into each fate row and their heats. A route's rate is
piecewise constant from each change's time (the operator's value_at), so a change at the join
belongs to the interval that starts there: the first run's last step runs at the old rate, and the
resumed run's first step at the new one.

It writes `restart.json`: the verdicts (every recorded step and the final state identical, bit for
bit, between the uninterrupted run and each joined run), the rows either side of the join and the
initiation extents of the steps that end and start there, with the source's identity.

Run: PYTHONPATH=src:. JAX_ENABLE_X64=1 python -m validation.gene_regulation.restart_example
[--world NAME] [--route ID] [--join S] [--factor F] [--window-steps N] --out DIR
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.windows import WindowPolicy, iter_windows
from cells.records.io import load_snapshot, write_snapshot
from validation.gene_regulation import engine_run, worlds


def with_change(raw, route, join, factor):
    """raw with `route`'s rate multiplied by `factor` from `join` on."""
    for control in raw["experiment"]["polymerisation_controls"]:
        if control["route_id"] == route:
            value = control["schedule"][-1]["value"]
            control["schedule"].append({"time": float(join), "value": factor * value})
            return raw
    raise ValueError(f"no route {route!r}")


def rows(windows, stop=None):
    """({time: state} of every recorded step, the last window's final checkpoint), stopping after
    the window that ends at `stop`."""
    out, final = {}, None
    for window in windows:
        for i, t in enumerate(np.asarray(window.times)):
            out[float(t)] = type(window.history)(*(np.asarray(v)[i] for v in window.history))
        final = window.final
        if stop is not None and float(final.time) >= stop:
            break
    return out, final


def identical(a, b):
    return all(np.array_equal(np.asarray(x), np.asarray(y)) for x, y in zip(a, b, strict=True))


def example(world, route, join, factor, window_steps, out):
    raw = with_change(worlds.world(world), route, join, factor)
    spec = parse_spec(raw)
    dt = spec.execution.dt
    if abs(join / dt / window_steps - round(join / dt / window_steps)) > 1e-9:
        raise ValueError("the join must fall on a window's end")
    policy = WindowPolicy(window_steps=window_steps, recording="observations")
    seconds = {}
    started = time.perf_counter()
    whole, whole_final = rows(iter_windows(spec, policy))
    seconds["uninterrupted"] = time.perf_counter() - started
    started = time.perf_counter()
    first, checkpoint = rows(iter_windows(spec, policy), stop=join)
    seconds["to the join"] = time.perf_counter() - started
    started = time.perf_counter()
    second, joined_final = rows(iter_windows(spec, policy, checkpoint))
    seconds["resumed in process"] = time.perf_counter() - started
    started = time.perf_counter()
    write_snapshot(out / "snapshot", spec, checkpoint)
    snapshot = load_snapshot(out / "snapshot")
    third, disk_final = rows(iter_windows(snapshot.spec, policy, snapshot.checkpoint))
    seconds["resumed from the files"] = time.perf_counter() - started
    (block,) = [d for d in spec.model.operators if d.law == worlds.POLYMERISATION]
    index = [c.id for c in block.chains].index(route) if route in [
        c.id for c in block.chains] else None  # fmt: skip

    def initiated(state):
        return None if index is None else float(state.poly_initiated_fmol[index])

    verdicts = {}
    for name, (later, final) in {
        "resumed in process": (second, joined_final),
        "resumed from the files": (third, disk_final),
    }.items():
        joined = {**first, **later}
        verdicts[name] = dict(
            same_steps=sorted(joined) == sorted(whole),
            every_step_identical=all(identical(whole[t], joined[t]) for t in whole),
            final_identical=identical(whole_final.state, final.state),
            join_row_identical=identical(first[join], later[join]),
        )
    before, at, after = join - dt, join, join + dt
    return dict(
        kind="cells.gene_regulation.restart_example@1",
        world=world,
        route=route,
        join_s=join,
        factor=factor,
        dt_s=dt,
        window_steps=window_steps,
        checkpoint=dict(
            time=float(checkpoint.time),
            step_index=checkpoint.step_index,
            event_index=checkpoint.event_index,
        ),  # fmt: skip
        owner=(
            "the interval that starts at the join: the change's time is its first step's start, "
            "and the rate is piecewise constant from it"
        ),
        initiation_extent_fmol=dict(
            step_ending_at_join=initiated(whole[at]) - initiated(whole[before]),
            step_starting_at_join=initiated(whole[after]) - initiated(whole[at]),
        )
        if index is not None
        else None,
        verdicts=verdicts,
        seconds=seconds,
        counters_at_end={
            k: np.asarray(getattr(whole_final.state, k)).tolist()
            for k in (
                "poly_initiated_fmol",
                "poly_stage_exits_fmol",
                "poly_released_fmol",
                "poly_degraded_fmol",
                "poly_transferred_fmol",
                "poly_dissipated_energy_pJ",
                "poly_hold_fmol",  # The release's (the sheet's §9.7), empty without one.
                "poly_hold_released_fmol",
                "poly_release_heat_pJ",
            )
        },
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--world", default="pol T=5")
    parser.add_argument("--route", default="tx")
    parser.add_argument("--join", type=float, default=1800.0)
    parser.add_argument("--factor", type=float, default=0.5)
    parser.add_argument("--window-steps", type=int, default=1200)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    source, patch = engine_run.provenance(out)
    if patch is not None:
        (out / "checkout.patch").write_text(patch)
    record = example(args.world, args.route, args.join, args.factor, args.window_steps, out)
    record.update(engine_run.late_sources(out, source))
    (out / "restart.json").write_text(json.dumps(record, indent=1) + "\n")
    print(json.dumps(record["verdicts"]), record["initiation_extent_fmol"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
