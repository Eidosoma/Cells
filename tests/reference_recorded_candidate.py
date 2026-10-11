"""D039 reference runner: frozen numerical kernel with explicit evidence policies.

Successful integration arithmetic is unchanged. Comparisons precede checkpoint
publication; failure diagnostics never silently become accepted restart state.
"""

from pathlib import Path
from time import perf_counter

import numpy as np

from tests import reference_graph_candidate as frozen
from tests import reference_graph_evidence as evidence

Grid, rk4_step, check_state = frozen.Grid, frozen.rk4_step, frozen.check_state
contract, digest, REVISION, ref = frozen.contract, frozen.digest, frozen.REVISION, frozen.ref
load_checkpoint = evidence.load_checkpoint


def integrate(
    model,
    output,
    *,
    step,
    end,
    numerics,
    resources,
    identity,
    artifact_root,
    policy,
    comparison=None,
    initial=None,
):
    """Fresh or exact accepted-boundary continuation; one live state across windows."""
    evidence.validate_policy(policy)
    grid = Grid(step, end)
    expected = contract(model, grid, numerics, identity)
    tick, value = 0, np.zeros(model.coordinates.size)
    if initial is not None:
        checked = load_checkpoint(initial["parent_directory"], initial["parent_chunk"], expected)
        if initial != checked:
            raise ValueError("Checkpoint carry was changed")
        tick, value = checked["tick"], np.asarray(checked["increments"], dtype=np.float64)
    start_tick = tick
    if tick >= grid.count:
        raise ValueError("Candidate continuation has no remaining steps")
    output, root = Path(output), Path(artifact_root)
    if output.resolve() != output.absolute() or not output.absolute().is_relative_to(
        root.absolute()
    ):
        raise ValueError("Candidate output must be unlinked and inside its budget root")
    output.mkdir(parents=True, exist_ok=False)
    begun, calls, steps, estimated = perf_counter(), 0, 0, 0
    recorder = None
    last_time, last_input = grid.time(tick), value.copy()
    integration_seconds = curve_seconds = 0.0
    stage_residual, extrema = 0.0, {}

    def write_json(path, value):
        evidence.save_json(path, value, root, resources["artifact_budget_bytes"])

    def guard():
        if perf_counter() - begun > resources["worker_timeout_seconds"]:
            raise ref.BudgetExceeded("Candidate wall budget exceeded")

    def rhs(time, trial):
        nonlocal calls, last_time, last_input, stage_residual
        last_time, last_input = float(time), trial.copy()
        guard()
        stage_residual = max(stage_residual, check_state(model, trial, numerics["accounting_atol"]))
        calls += 1
        result = model.derivative(trial, increments=True)
        if result.shape != trial.shape or not np.isfinite(result).all():
            raise ValueError("Nonfinite or incomplete candidate RHS")
        return result

    try:
        write_json(
            output / "attempt.json",
            {
                "contract": expected,
                "recording": {"revision": evidence.REVISION, "policy": policy},
                "contract_sha256": digest(expected),
                "resources": resources,
                "initial": initial,
                "start_tick": start_tick,
            },
        )
        width, size = resources["window_steps"], model.coordinates.size
        if type(width) is not int or not 1 <= width <= 256:
            raise ValueError("Invalid candidate window width")
        if grid.count > resources["max_steps_per_trajectory"]:
            raise ref.BudgetExceeded("Candidate global step budget exceeded")
        # Comparison batches follow this window, but all three immutable
        # reference samplers AND their grid streams can each retain a width-256
        # dense window. Account for those independently of the candidate width.
        estimated = 8 * (
            (width + 1) * (160 * size + 384 * model.n) + 6 * 257 * (8 * size + 20) + 128 * size
        )
        estimated += evidence.estimate_array_bytes(width, size, model.n)
        if estimated > resources["estimated_array_budget_bytes"]:
            raise ref.BudgetExceeded("Candidate working array estimate exceeds budget")
        check_state(model, value, numerics["accounting_atol"])
        evidence.save_arrays(
            output / "initial.npz",
            {
                "tick": np.asarray(tick),
                "time": np.asarray(grid.time(tick)),
                "increments": value,
                "anchor": model.anchor,
                "context": model.context,
            },
            root,
            resources["artifact_budget_bytes"],
        )
        if comparison is not None:
            comparison.open(start_tick, grid, guard)
        recorder = evidence.Recorder(
            model, output, resources, root, grid, tick, value, comparison, policy=policy
        )
        while tick < grid.count:
            guard()
            a, b = grid.time(tick), grid.time(tick + 1)
            phase = perf_counter()
            result, slopes, coefficients = rk4_step(rhs, a, b, value)
            integration_seconds += perf_counter() - phase
            phase = perf_counter()
            ref.merge_extrema(
                extrema,
                ref.check_curve(model, coefficients, accounting_atol=numerics["accounting_atol"]),
            )
            curve_seconds += perf_counter() - phase
            tick, value, steps = tick + 1, result, steps + 1
            recorder.append(tick, value, slopes, coefficients)
        recorder.flush()
        compared = comparison.finish() if comparison is not None else None
        if compared is not None and compared["status"] != "pass":
            raise ValueError("Short candidate reference disagreement; no automatic refinement")
        guard()
        evidence.save_arrays(
            output / "final.npz",
            {
                "tick": np.asarray(tick),
                "time": np.asarray(grid.time(tick)),
                "increments": value,
                "anchor": model.anchor,
                "context": model.context,
            },
            root,
            resources["artifact_budget_bytes"],
        )
        guard()
        report = {
            "status": "complete_engineering_candidate_not_long_qualified",
            "revision": REVISION,
            "start": grid.time(start_tick),
            "end": grid.time(tick),
            "start_tick": start_tick,
            "end_tick": tick,
            "step": step,
            "steps": steps,
            "rhs_calls": calls,
            "seconds": perf_counter() - begun,
            "window_steps": width,
            "chunks": recorder.chunks,
            "estimated_working_array_bytes": estimated,
            "maximum_stage_accounting_residual": stage_residual,
            "whole_curve": extrema,
            "timings": {
                "integration_and_stage_checks": integration_seconds,
                "cubic_domain_checks": curve_seconds,
                "window_recording": recorder.recording_seconds,
                "comparison_and_sample_recording": recorder.comparison_seconds,
            },
            "raw_trajectory_array_bytes": recorder.raw_array_bytes,
            "comparison": compared,
            "evidence": recorder.summary(),
            "recording_revision": evidence.REVISION,
            "attempt_sha256": ref.sha(output / "attempt.json"),
            "index_sha256": ref.sha(output / "chunks.jsonl"),
            "initial_sha256": ref.sha(output / "initial.npz"),
            "final_sha256": ref.sha(output / "final.npz"),
            "long_time_step_selected": False,
            "production_changed": False,
        }
        write_json(output / "trajectory.json", report)
        return report
    except BaseException as error:
        preservation = {}
        tasks = [
            (
                "last-evaluation.npz",
                lambda: {
                    "time": np.asarray(last_time),
                    "increments": last_input,
                    "accepted_time": np.asarray(grid.time(tick)),
                    "accepted_tick": np.asarray(tick),
                    "accepted_increments": value,
                    "anchor": model.anchor,
                    "context": model.context,
                },
            ),
        ]
        if recorder is not None and recorder.buffered:
            tasks.append(("uncommitted-window.npz", recorder.window))
        for name, arrays in tasks:
            try:
                evidence.save_arrays(
                    output / name,
                    arrays(),
                    root,
                    resources["artifact_budget_bytes"],
                    emergency=True,
                )
                preservation[name] = {
                    "status": "retained_diagnostic_not_restart",
                    "sha256": ref.sha(output / name),
                }
            except BaseException as secondary:
                preservation[name] = {
                    "status": "preservation_failed",
                    "error": f"{type(secondary).__name__}: {secondary}",
                }

        def existing(name):
            return ref.sha(output / name) if (output / name).exists() else None

        failed = {
            "status": "incomplete"
            if isinstance(error, (ref.BudgetExceeded, KeyboardInterrupt))
            else "refused",
            "exception": type(error).__name__,
            "message": str(error),
            "steps": steps,
            "rhs_calls": calls,
            "accepted_tick": tick,
            "accepted_time": grid.time(tick),
            "seconds": perf_counter() - begun,
            "committed_chunks": 0 if recorder is None else recorder.chunks,
            "evidence": {"committed_tick": start_tick, "head_sha256": existing("attempt.json")}
            if recorder is None
            else recorder.summary(),
            "preservation": preservation,
            "no_automatic_retry": True,
            "attempt_sha256": existing("attempt.json"),
            "initial_sha256": existing("initial.npz"),
            "index_sha256": existing("chunks.jsonl"),
            "long_time_step_selected": False,
            "production_changed": False,
        }
        try:
            evidence.save_json(
                output / "failure.json",
                failed,
                root,
                resources["artifact_budget_bytes"],
                emergency=True,
            )
        except BaseException as secondary:
            error.add_note(
                f"Failure receipt could not be retained: {type(secondary).__name__}: {secondary}"
            )
        raise
    finally:
        if comparison is not None:
            comparison.close()
