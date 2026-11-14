"""The first consumer of checkpoint continuity: a CPU development run on vector windows.

docs/CHECKPOINT_CONTINUITY_DESIGN.md, section 10 item 7. A development run, not a registered
one. Engine models run: resolved_pump_replacement@1 (cell replacement on the resolved pump
tissue; the probe-5 cohort of the design's evidence) through core/vector_windows.py.

No engine writer records a vector-window run (batch_window_io.write_windowed_batch drives the
batch_windows path), so this driver defines the run folder that verify_run.py checks:
  inputs.json      the command, the engine tree and its identity, the checkpoint and the run
                   that wrote it, and the continuity record, if any (written first)
  windows.jsonl    one line per round: each world's start and end step and time, its event
                   index and its observation count
  rounds.jsonl     one line per round: digests of each world's endpoint state, observations
                   and device-check diagnostics, with its clock (probe.window_record), for the
                   bitwise comparisons (compare)
  snapshots/       cohort snapshots every --snapshot-every rounds (batch_io)
  checkpoint_final the final cohort snapshot
  manifest.json    path, policy, identity, provenance and file digests (written last)
The provenance is {"operation": "fresh"}, {"operation": "resume", ...} for a resume under the
checkpoint's own source, or cells.continuity.provenance(admission) for an admitted resume.

Under the checkpoint's own tree S0 (which predates cells.continuity) only fresh runs and plain
resumes are possible; --continuity needs the resuming tree.

Usage:
  dev_run.py cohort --out COHORT.json [--end-steps 40]
  dev_run.py run --batch COHORT.json --out RUN --window-steps 8 --recording checkpoints
                 [--snapshot-every 1]
  dev_run.py resume --snapshot SNAP --checkpoint-run RUN0 --out RUN --window-steps 8
                    --recording checkpoints [--continuity RECORD] [--snapshot-every 1]
  dev_run.py compare A B --out FILE
"""

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from validation.continuity import probe as digests

KIND = "cells.continuity_dev_run@1"
PATH = "vector_windows"
DT = 1e-3


def sha256(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write_json(path, value):
    with Path(path).open("x") as handle:
        json.dump(value, handle, indent=1, sort_keys=True, allow_nan=False)
        handle.write("\n")


def cohort(end_steps=40, backend="cpu"):
    """The probe-5 cohort (two worlds of the seven-cell sheet), over end_steps steps of 1 ms.

    World 1 replaces cell_0 at steps 5 and 16, world 2 cells 3 and 4 at step 9; observations
    every 12 steps and at the end. backend="gpu" is for the GPU probe of design section 13.4
    only; the first landing admits CPU definitions.
    """
    from cells.core.batch import BatchSpec, WorldSpec
    from cells.core.cell_replacement_spec import exact_event_times
    from cells.core.specs import parse_spec
    from validation.tissue import cell_replacement_fixtures as fx

    observed = sorted({*range(0, end_steps + 1, 12), end_steps})

    def world(events):
        raw = fx.heredity_sheet(1, 0, dt=DT, end_time=end_steps * DT)
        raw["experiment"]["observation_times"] = [k * DT for k in observed]
        raw["execution"]["backend"] = backend
        templates = [
            fx.template_from_cell(raw, "cell_1", "h"),
            fx.template_from_cell(raw, "cell_3", "d"),
        ]
        formation = dict(fx.FORMATION, lag_s=0.0, time_constant_s=40.0)
        return parse_spec(fx.with_replacement(raw, templates, events, formation=formation))

    t = exact_event_times((5, 9, 16), DT)
    specs = [
        world(((t[0], "cell_0", "h", "a1"), (t[2], "cell_0", "d", "a2"))),
        world(((t[1], "cell_3", "h", "b1"), (t[1], "cell_4", "h", "b2"))),
    ]
    return BatchSpec(tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs)), 2, 10**6, 2**31)


def engine_identity():
    import cells
    from cells.core.specs import digest
    from cells.io import runtime_identity, source_hashes

    tree = Path(cells.__file__).resolve().parents[2]
    marker = tree / "SNAPSHOT.json"
    snapshot = json.loads(marker.read_text()) if marker.is_file() else {}
    return dict(
        cells=str(Path(cells.__file__).resolve().parent),
        source_hashes_sha256=digest(source_hashes()),
        runtime=runtime_identity("cpu"),
        execution_snapshot=str(tree) if snapshot else None,
        git_revision=snapshot.get("git_revision"),
        dirty_diff=str(tree / "checkout.patch") if snapshot else None,
    )


def prepare(out):
    """The run folder: new, or holding only the admission (continuity/) made for it."""
    out = Path(out)
    if out.exists() and {p.name for p in out.iterdir()} - {"continuity"}:
        raise SystemExit(f"{out} exists and holds more than its continuity/ folder")
    out.mkdir(parents=True, exist_ok=True)
    return out


def execute(spec, policy, checkpoints, out, provenance, inputs, every):
    """The vector-windows path; every round recorded, cohort snapshots every ``every``."""
    from cells.batch_io import write_batch_snapshot
    from cells.core.specs import canonical_json
    from cells.core.vector_windows import iter_vector_windows
    from cells.io import runtime_identity, source_hashes

    write_json(out / "inputs.json", inputs)
    started, snapshots, rounds, last = time.perf_counter(), [], 0, None
    previous = {w.world_id: checkpoints[w.world_id] for w in spec.worlds} if checkpoints else None
    with (out / "windows.jsonl").open("x") as index, (out / "rounds.jsonl").open("x") as digest:
        try:
            for window in iter_vector_windows(spec, policy, checkpoints):
                worlds = {}
                for w in spec.worlds:
                    end = window.checkpoints[w.world_id]
                    start = None if previous is None else previous[w.world_id]
                    worlds[str(w.world_id)] = dict(
                        start_step=None if start is None else start.step_index,
                        start_time=None if start is None else float(start.time),
                        end_step=end.step_index,
                        end_time=float(end.time),
                        event_index=end.event_index,
                        observations=len(window.observations[w.world_id].times)
                        if w.world_id in window.observations
                        else 0,
                    )
                index.write(canonical_json(dict(round=window.index, worlds=worlds)) + "\n")
                digest.write(canonical_json(digests.window_record(window)) + "\n")
                previous, last, rounds = dict(window.checkpoints), window, rounds + 1
                complete = all(
                    window.checkpoints[w.world_id].time == w.simulation.experiment.end_time
                    for w in spec.worlds
                )
                if every and rounds % every == 0 and not complete:
                    name = f"snapshots/round-{rounds:06d}"
                    write_batch_snapshot(out / name, spec, dict(window.checkpoints))
                    snapshots.append(name)
        except Exception as exc:
            write_json(out / "failure.json", dict(error=digests.error(exc), rounds=rounds))
            raise
    if last is not None:
        write_batch_snapshot(out / "checkpoint_final", spec, dict(last.checkpoints))
    fixed = ["inputs.json", "windows.jsonl", "rounds.jsonl"]
    fixed += [f"{s}/manifest.json" for s in snapshots]
    fixed += ["checkpoint_final/manifest.json"] if last is not None else []
    fixed += ["continuity/record.json"] if (out / "continuity" / "record.json").exists() else []
    write_json(
        out / "manifest.json",
        dict(
            kind=KIND,
            status="complete",
            path=PATH,
            policy=policy.to_dict(),
            definition_sha256=spec.fingerprint,
            runtime=runtime_identity("cpu"),
            source_hashes=source_hashes(),
            provenance=provenance,
            rounds=rounds,
            snapshots=snapshots,
            run_seconds=time.perf_counter() - started,
            created_utc=datetime.now(timezone.utc).isoformat(),
            files_sha256={name: sha256(out / name) for name in fixed},
        ),
    )
    print(KIND, out, rounds, "rounds", flush=True)


def run(args):
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.core.batch import load_batch
    from cells.core.windows import WindowPolicy

    out = prepare(args.out)
    spec = load_batch(args.batch)
    inputs = dict(
        kind=KIND + ".inputs",
        argv=sys.argv,
        engine=engine_identity(),
        batch=str(Path(args.batch).resolve()),
        batch_sha256=sha256(args.batch),
        checkpoint=None,
        checkpoint_run=None,
        continuity_record=None,
    )
    policy = WindowPolicy(args.window_steps, args.recording)
    execute(spec, policy, None, out, {"operation": "fresh"}, inputs, args.snapshot_every)


def resume(args):
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.batch_io import load_batch_snapshot
    from cells.core.windows import WindowPolicy

    out = prepare(args.out)
    policy = WindowPolicy(args.window_steps, args.recording)
    snapshot = Path(args.snapshot).resolve()
    inputs = dict(
        kind=KIND + ".inputs",
        argv=sys.argv,
        engine=engine_identity(),
        checkpoint=str(snapshot),
        checkpoint_manifest_sha256=json.loads((snapshot / "manifest.json").read_text())[
            "manifest_sha256"
        ],
        checkpoint_run=str(Path(args.checkpoint_run).resolve()),
        continuity_record=None,
    )
    if args.continuity is None:
        saved = load_batch_snapshot(snapshot)  # Refuses any source or runtime change.
        provenance = {"operation": "resume", "parent_checkpoint_sha256": saved.fingerprint}
    else:
        from cells import continuity

        record = Path(args.continuity).resolve()
        inputs.update(continuity_record=str(record), continuity_record_sha256=sha256(record))
        request = continuity.Request(record, path=PATH, policy=policy)
        saved = load_batch_snapshot(snapshot, continuity=request)
        provenance = continuity.provenance(saved.admission)
    execute(
        saved.spec, policy, dict(saved.checkpoints), out, provenance, inputs, args.snapshot_every
    )


def compare(args):
    """Rounds of B against those of A at the same step indices: digests bitwise equal?"""
    lines = {}
    for label, run in (("a", args.a), ("b", args.b)):
        lines[label] = [
            json.loads(x) for x in (Path(run) / "rounds.jsonl").read_text().splitlines()
        ]
    by_step = {}
    for row in lines["a"]:
        for world, value in row["worlds"].items():
            by_step[(world, value["step_index"])] = value
    rows, equal = [], bool(lines["b"])
    for row in lines["b"]:
        for world, value in row["worlds"].items():
            other = by_step.get((world, value["step_index"]))
            same = other is not None and all(
                value[k] == other[k]
                for k in ("time", "event_index", "state", "observations", "diagnostics")
            )
            equal &= same
            rows.append(dict(round=row["round"], world=world, step=value["step_index"], equal=same))
    report = dict(
        a=str(args.a), b=str(args.b), rows=rows, verdict="bitwise equal" if equal else "differs"
    )
    write_json(args.out, report)
    print("compare", report["verdict"], flush=True)
    return 0 if equal else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("cohort", help="write the cohort definition")
    c.add_argument("--out", required=True)
    c.add_argument("--end-steps", type=int, default=40)
    for name in ("run", "resume"):
        p = sub.add_parser(name)
        p.add_argument("--out", required=True)
        p.add_argument("--window-steps", type=int, required=True)
        p.add_argument(
            "--recording", required=True, choices=("full", "observations", "checkpoints")
        )
        p.add_argument("--snapshot-every", type=int, default=1, help="rounds; 0 for none")
        if name == "run":
            p.add_argument("--batch", required=True)
        else:
            p.add_argument("--snapshot", required=True)
            p.add_argument("--checkpoint-run", required=True, help="the run that wrote it")
            p.add_argument("--continuity", default=None, help="an admitted continuity record")
    k = sub.add_parser("compare", help="bitwise comparison of two runs' rounds")
    k.add_argument("a")
    k.add_argument("b")
    k.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.command == "cohort":
        write_json(args.out, cohort(args.end_steps).to_dict())
        return 0
    if args.command == "compare":
        return compare(args)
    return run(args) if args.command == "run" else resume(args)


if __name__ == "__main__":
    sys.exit(main())
