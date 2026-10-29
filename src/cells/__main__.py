"""Command line: validate, run, resume, and explicitly branch a saved world."""

import argparse
import json
import sys
from pathlib import Path

from cells import __version__
from cells.batch_io import load_batch_snapshot, write_batch_run
from cells.batch_window_io import write_windowed_batch
from cells.core.batch import branch_batch_checkpoints, load_batch, plan_batch, run_batch
from cells.core.batch_windows import plan_batch_windows
from cells.core.runner import NumericalError, branch_checkpoint, run, timeline
from cells.core.specs import ConfigError, load_spec
from cells.core.windows import WindowPolicy, plan_windows
from cells.io import load_snapshot, write_run
from cells.window_io import write_windowed_run


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cells", description=__doc__)
    parser.add_argument("--version", action="version", version=f"Cells {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("assembly", help="stochastic molecular assembly on CPU or GPU")
    commands.add_parser("assembly-pool", help="finite material and breakable assembly bonds")
    commands.add_parser("assembly-cell", help="assembly-controlled channel in a finite ionic cell")
    commands.add_parser(
        "assembly-cluster", help="cell-owned assembly controlling interacting cells"
    )
    commands.add_parser("ensemble", help="balanced independent assembly worlds across GPUs")
    commands.add_parser("tissue-profiles", help="prepare and replay static tissue profiles")
    commands.add_parser("tissue-phase", help="carry INIT history into a new SIM phase")
    commands.add_parser(
        "tissue-geometry", help="prepare and replay initial passive tissue geometry"
    )
    validate = commands.add_parser("validate", help="validate a definition and its resource bounds")
    validate.add_argument("config", type=Path)
    fresh = commands.add_parser("run", help="run a fresh configured world")
    fresh.add_argument("config", type=Path)
    resume = commands.add_parser("resume", help="continue under a snapshot's unchanged definition")
    resume.add_argument("snapshot", type=Path)
    branch = commands.add_parser("branch", help="continue with explicitly changed future inputs")
    branch.add_argument("snapshot", type=Path)
    branch.add_argument("config", type=Path)
    excision = commands.add_parser(
        "excise",
        help="remove named cells and rebuild supported passive, active or calcium/fuel tissue",
    )
    excision.add_argument("snapshot", type=Path)
    excision.add_argument(
        "--remove", action="append", required=True, help="cell ID; repeat for several cells"
    )
    excision.add_argument(
        "--output", type=Path, required=True, help="new excision archive directory"
    )
    for command in (fresh, resume, branch):
        command.add_argument(
            "--output", type=Path, required=True, help="new directory; never overwritten"
        )
        command.add_argument("--checkpoint-at", type=float, action="append", default=[])
    batch = commands.add_parser("batch", help="validate/run/resume/branch independent worlds")
    batch_commands = batch.add_subparsers(dest="batch_command", required=True)
    for name in ("validate", "run", "resume", "branch"):
        command = batch_commands.add_parser(name)
        if name in ("resume", "branch"):
            command.add_argument("snapshot", type=Path)
        if name in ("validate", "run", "branch"):
            command.add_argument("config", type=Path)
        if name != "validate":
            command.add_argument("--output", type=Path, required=True)
            command.add_argument("--checkpoint-at", type=float, action="append", default=[])
    batch_windowed = batch_commands.add_parser(
        "windowed", help="bounded rounds with independent clocks and complete cohort checkpoints"
    )
    cohort_commands = batch_windowed.add_subparsers(dest="cohort_command", required=True)
    for name in ("validate", "run", "resume", "branch"):
        command = cohort_commands.add_parser(name)
        if name in ("resume", "branch"):
            command.add_argument("snapshot", type=Path)
        if name in ("validate", "run", "branch"):
            command.add_argument("config", type=Path)
        command.add_argument("--window-steps", type=int, default=256)
        command.add_argument(
            "--recording", choices=("full", "observations", "checkpoints"), default="observations"
        )
        if name != "validate":
            command.add_argument("--output", type=Path, required=True)
            command.add_argument("--checkpoint-every-windows", type=int, default=0)
    windowed = commands.add_parser("windowed", help="bounded single-world execution and recording")
    window_commands = windowed.add_subparsers(dest="window_command", required=True)
    for name in ("validate", "run", "resume", "branch"):
        command = window_commands.add_parser(name)
        if name in ("resume", "branch"):
            command.add_argument("snapshot", type=Path)
        if name in ("validate", "run", "branch"):
            command.add_argument("config", type=Path)
        command.add_argument("--window-steps", type=int, default=256)
        command.add_argument(
            "--recording", choices=("full", "observations", "checkpoints"), default="observations"
        )
        if name != "validate":
            command.add_argument("--output", type=Path, required=True)
            command.add_argument("--checkpoint-at", type=float, action="append", default=[])
    return parser


def _batch_main(args):
    if args.batch_command == "windowed":
        return _batch_window_main(args)
    if args.batch_command == "validate":
        plan = plan_batch(load_batch(args.config))
        return {
            "status": "valid",
            "worlds": len(plan.spec.worlds),
            "sha256": plan.spec.fingerprint,
            "estimated_working_bytes": plan.estimated_working_bytes,
            "padded_step_bound": plan.padded_step_bound,
        }
    if args.output.exists():
        raise ConfigError(f"Output already exists; choose a new directory: {args.output}")
    checkpoints = None
    provenance = {"operation": f"batch_{args.batch_command}"}
    if args.batch_command == "run":
        spec = load_batch(args.config)
    else:
        saved = load_batch_snapshot(args.snapshot)
        spec, checkpoints = saved.spec, saved.checkpoints
        provenance["parent_batch_snapshot_sha256"] = saved.fingerprint
        if args.batch_command == "branch":
            spec = load_batch(args.config)
            checkpoints = branch_batch_checkpoints(saved.spec, checkpoints, spec)
    result = run_batch(spec, checkpoints)
    return write_batch_run(
        args.output, result, checkpoint_times=tuple(args.checkpoint_at), provenance=provenance
    ) | {"output": str(args.output)}


def _batch_window_main(args):
    policy = WindowPolicy(args.window_steps, args.recording)
    if args.cohort_command == "validate":
        plan = plan_batch_windows(load_batch(args.config), policy)
        return {
            "status": "valid",
            "worlds": len(plan.spec.worlds),
            "sha256": plan.spec.fingerprint,
            "rounds": max(p.window_count for p in plan.worlds),
            "estimated_working_bytes": plan.estimated_working_bytes,
            "padded_step_bound": plan.padded_step_bound,
            "policy": policy.to_dict(),
        }
    if args.output.exists():
        raise ConfigError(f"Output already exists; choose a new directory: {args.output}")
    checkpoints = None
    provenance = {"operation": f"windowed_batch_{args.cohort_command}"}
    if args.cohort_command == "run":
        spec = load_batch(args.config)
    else:
        saved = load_batch_snapshot(args.snapshot)
        spec, checkpoints = saved.spec, saved.checkpoints
        provenance["parent_batch_snapshot_sha256"] = saved.fingerprint
        if args.cohort_command == "branch":
            spec = load_batch(args.config)
            checkpoints = branch_batch_checkpoints(saved.spec, checkpoints, spec)
    return write_windowed_batch(
        args.output,
        spec,
        policy,
        checkpoints,
        checkpoint_every_windows=args.checkpoint_every_windows,
        provenance=provenance,
    ) | {"output": str(args.output)}


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] == "tissue-phase":
        from cells.tissue_phase import main as phase_main

        return phase_main(args[1:])
    if args and args[0] == "tissue-geometry":
        from cells.tissue_geometry import main as geometry_main

        return geometry_main(args[1:])
    if args and args[0] == "tissue-profiles":
        from cells.tissue_profiles import main as profiles_main

        return profiles_main(args[1:])
    if args and args[0] == "assembly-cluster":
        from cells.assembly_cluster.cli import main as cluster_main

        return cluster_main(args[1:])
    if args and args[0] == "assembly-cell":
        from cells.assembly_cell.cli import main as coupled_main

        return coupled_main(args[1:])
    if args and args[0] == "assembly-pool":
        from cells.assembly_pool.cli import main as pool_main

        return pool_main(args[1:])
    if args and args[0] == "ensemble":
        from cells.ensemble.cli import main as ensemble_main

        return ensemble_main(args[1:])
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv and argv[0] == "assembly":
        from cells.assembly.cli import main as assembly_main

        return assembly_main(argv[1:])
    args = _parser().parse_args(argv)
    try:
        if args.command == "excise":
            from cells.core.excision import excise
            from cells.excision_io import write_excision

            saved = load_snapshot(args.snapshot)
            result = excise(saved.spec, saved.checkpoint, args.remove)
            write_excision(args.output, result)
            print(
                json.dumps(
                    dict(
                        status="complete",
                        output=str(args.output),
                        terminal=result.report["terminal"],
                        absolute_time_s=saved.checkpoint.time,
                        continuation=str(args.output / "after")
                        if result.spec is not None
                        else None,
                    ),
                    indent=2,
                )
            )
            return 0
        if args.command == "windowed":
            print(json.dumps(_window_main(args), indent=2))
            return 0
        if args.command == "batch":
            print(json.dumps(_batch_main(args), indent=2))
            return 0
        if args.command == "validate":
            spec = load_spec(args.config)
            grid = timeline(spec)
            print(
                json.dumps({"status": "valid", "steps": len(grid) - 1, "sha256": spec.fingerprint})
            )
            return 0
        if args.output.exists():
            raise ConfigError(f"Output already exists; choose a new directory: {args.output}")
        checkpoint = None
        provenance = {"operation": args.command}
        if args.command == "run":
            spec = load_spec(args.config)
        else:
            snapshot = load_snapshot(args.snapshot)
            checkpoint = snapshot.checkpoint
            spec = snapshot.spec
            provenance.update(
                {
                    "parent_snapshot_sha256": snapshot.fingerprint,
                    "parent_definition_sha256": snapshot.spec.fingerprint,
                    "branch_time": checkpoint.time,
                }
            )
            if args.command == "branch":
                spec = load_spec(args.config)
                checkpoint = branch_checkpoint(snapshot.spec, checkpoint, spec)
        result = run(spec, checkpoint)
        summary = write_run(
            args.output, result, checkpoint_times=tuple(args.checkpoint_at), provenance=provenance
        )
        print(json.dumps({**summary, "output": str(args.output)}, indent=2))
        return 0
    except (ConfigError, NumericalError, OSError) as exc:
        print(f"cells: {exc}", file=sys.stderr)
        return 2


def _window_main(args):
    policy = WindowPolicy(args.window_steps, args.recording)
    if args.window_command == "validate":
        plan = plan_windows(load_spec(args.config), policy)
        return {
            "status": "valid",
            "sha256": plan.spec.fingerprint,
            "steps": len(plan.grid) - 1,
            "windows": plan.window_count,
            "estimated_working_bytes": plan.estimated_working_bytes,
            "max_observations_per_window": plan.max_observations,
            "policy": policy.to_dict(),
        }
    if args.output.exists():
        raise ConfigError(f"Output already exists; choose a new directory: {args.output}")
    checkpoint = None
    provenance = {"operation": f"windowed_{args.window_command}"}
    if args.window_command == "run":
        spec = load_spec(args.config)
    else:
        saved = load_snapshot(args.snapshot)
        spec, checkpoint = saved.spec, saved.checkpoint
        provenance.update(
            parent_snapshot_sha256=saved.fingerprint,
            parent_definition_sha256=spec.fingerprint,
            branch_time=checkpoint.time,
        )
        if args.window_command == "branch":
            spec = load_spec(args.config)
            checkpoint = branch_checkpoint(saved.spec, checkpoint, spec)
    return write_windowed_run(
        args.output,
        spec,
        policy,
        checkpoint,
        checkpoint_times=args.checkpoint_at,
        provenance=provenance,
    ) | {"output": str(args.output)}


if __name__ == "__main__":
    raise SystemExit(main())
