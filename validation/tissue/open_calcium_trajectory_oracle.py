"""Future independent full8us oracle role; this module never launches a job."""

import argparse
import sys
from pathlib import Path

from validation.tissue import open_calcium_trajectory_common as artifact


def run(bundle, job_id, output):
    import numpy as np
    from scipy.integrate import solve_ivp

    from validation.tissue import open_calcium_reference as reference

    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    last = {}
    trial = {}
    try:
        blocked = [name for name in sys.modules if name.split(".")[0] in {"cells", "jax", "jaxlib"}]
        if blocked:
            raise RuntimeError("Independent oracle imported production/JAX: " + ",".join(blocked))
        bundle = Path(bundle).resolve()
        protocol, job, raw = artifact.load_job(bundle, job_id, "oracle")
        artifact.write_json(
            output / "reference-dependencies.json", reference.dependency_manifest(bundle / "source")
        )
        setting = protocol["oracle"][job["oracle_variant"]]
        context = reference.bind(raw)
        state = reference.initial(context)
        times = artifact.accepted_times(raw, protocol["base_dt_s"] / max(protocol["dt_divisors"]))
        events = artifact.control_times(raw)
        history = np.empty((len(times), len(state)))
        history[0] = state
        valid_rows = np.zeros(len(times), dtype=bool)
        valid_rows[0] = True
        atol = np.concatenate(
            [
                np.full(
                    np.prod(shape),
                    setting["charge_atol"] if key.endswith("_C") else setting["state_atol"],
                )
                for key, shape in context["shapes"].items()
            ]
        )
        calls, max_rate_error = 0, 0.0
        artifact.write_json(
            output / "inputs.json",
            dict(
                job_id=job_id,
                definition=raw,
                definition_sha256=artifact.digest(raw),
                protocol_sha256=artifact.digest(protocol),
                controls=events,
                oracle_settings=setting,
                max_step_s=protocol["oracle"]["max_step_s"],
                production_or_jax_imports=False,
            ),
        )
        artifact.save_arrays(output / "partial.npz", times=times[:1], state=history[:1])
        with (output / "progress.jsonl").open("x") as progress:
            for segment, (left, right) in enumerate(zip(events, events[1:], strict=False)):
                held = artifact.held_controls(raw, left)
                last = dict(
                    segment=segment,
                    segment_left_s=left,
                    segment_right_s=right,
                    held_control_time_s=left,
                    held_controls=held,
                )

                def rhs(time, value, *, segment=segment, left=left, held=held):
                    nonlocal calls, max_rate_error, trial, last
                    calls += 1
                    last = dict(
                        segment=segment,
                        physical_time_s=float(time),
                        held_control_time_s=left,
                        rhs_evaluations=calls,
                        held_controls=held,
                    )
                    trial = {"state": np.array(value, copy=True)}
                    slope, phi, proof = reference.evaluate(context, value, left)
                    residual = abs(proof["physical_energy_balance_pJ_s"])
                    if (
                        not np.isfinite(slope).all()
                        or not np.isfinite(phi).all()
                        or not np.isfinite(residual)
                    ):
                        raise ValueError("Nonfinite independent oracle stage")
                    if residual > protocol["tolerances"]["rate_energy_atol_pJ_s"]:
                        raise ValueError("Oracle stage energy identity failed")
                    max_rate_error = max(max_rate_error, residual)
                    if calls % 32 == 0:
                        artifact.write_progress(
                            progress, last | dict(max_rate_energy_error_pJ_s=max_rate_error)
                        )
                    return slope

                solution = solve_ivp(
                    rhs,
                    (left, right),
                    state,
                    method="DOP853",
                    rtol=setting["rtol"],
                    atol=atol,
                    max_step=protocol["oracle"]["max_step_s"],
                    dense_output=True,
                )
                if not solution.success:
                    raise RuntimeError("Independent oracle segment failed: " + solution.message)
                selected = np.flatnonzero((times > left) & (times <= right))
                history[selected] = solution.sol(times[selected]).T
                valid_rows[selected] = True
                state = solution.y[:, -1]
                artifact.save_arrays(
                    output / "partial.npz", times=times[valid_rows], state=history[valid_rows]
                )
                artifact.write_progress(
                    progress,
                    dict(
                        segment_complete=segment,
                        time_s=right,
                        rhs_evaluations=calls,
                        saved_samples=int(valid_rows.sum()),
                    ),
                )
            if not np.all(valid_rows):
                raise RuntimeError("Oracle did not cover the complete finest accepted grid")
            potentials, invariant_metrics = [], []
            for i, time in enumerate(times):
                last = dict(
                    sample_index=i,
                    physical_time_s=float(time),
                    stage="oracle_sample_audit",
                    held_control_time_s=float(time),
                    held_controls=artifact.held_controls(raw, float(time)),
                )
                trial = {"state": history[i].copy()}
                slope, phi, proof = reference.evaluate(context, history[i], float(time))
                residual = abs(proof["physical_energy_balance_pJ_s"])
                if (
                    not np.isfinite(slope).all()
                    or not np.isfinite(phi).all()
                    or not np.isfinite(residual)
                    or residual > protocol["tolerances"]["rate_energy_atol_pJ_s"]
                ):
                    raise ValueError("Oracle accepted-time energy identity failed")
                max_rate_error = max(max_rate_error, residual)
                metrics = artifact.check_proof(
                    reference.conservation(context, history[i]), protocol
                )
                invariant_metrics.append(metrics)
                potentials.append(phi)
                artifact.write_progress(progress, last | dict(invariants=metrics))
        if times[0] != 0.0 or times[-1] != protocol["duration_s"]:
            raise RuntimeError("Oracle duration changed")
        artifact.save_arrays(
            output / "trajectory.npz",
            times=times,
            state=history,
            potential_V=np.asarray(potentials),
        )
        artifact.write_json(output / "invariants.json", invariant_metrics)
        if any(name.split(".")[0] in {"cells", "jax", "jaxlib"} for name in sys.modules):
            raise RuntimeError("Independent oracle imported production/JAX during integration")
        artifact.success(
            output,
            dict(
                job_id=job_id,
                family=job["family"],
                role="oracle",
                bundle_manifest_sha256=artifact.sha(bundle / "manifest.json"),
                variant=job["oracle_variant"],
                definition_sha256=artifact.digest(raw),
                physics_sha256=artifact.digest(artifact.physical_definition(raw)),
                protocol_sha256=artifact.digest(protocol),
                duration_s=float(times[-1]),
                samples=len(times),
                control_times_s=events,
                complete_fields=len(context["shapes"]),
                state_shapes=context["shapes"],
                rhs_evaluations=calls,
                max_rate_energy_error_pJ_s=max_rate_error,
                imported_production_or_jax=False,
                method="segmented DOP853; fixed left controls, right-continuous accepted readouts",
            ),
        )
    except BaseException as error:
        artifact.failure(output, error, context=last, arrays=trial)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--job", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    run(args.bundle, args.job, args.output)


if __name__ == "__main__":
    main()
