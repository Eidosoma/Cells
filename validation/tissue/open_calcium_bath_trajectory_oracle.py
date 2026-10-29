"""Future independent full-phase trajectories; never launches another role."""

import argparse
import sys
from pathlib import Path

from validation.tissue import open_calcium_bath_trajectory_common as artifact


def run(bundle, job_id, output, dependency_runs=None):
    import numpy as np
    from scipy.integrate import solve_ivp

    from validation.tissue import open_calcium_bath_reference as reference
    from validation.topology import open_calcium_bath_phase_handoff_reference as phase

    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    last, trial = {}, {}
    try:
        if any(name.split(".")[0] in {"cells", "jax", "jaxlib"} for name in sys.modules):
            raise RuntimeError("Independent oracle imported Cells/JAX")
        bundle = Path(bundle).resolve()
        protocol, job, raw = artifact.load_job(bundle, job_id, "oracle")
        dependencies = artifact.dependencies(bundle, job, dependency_runs)
        context = reference.bind(raw)
        state = reference.initial(context)
        source = None
        if job.get("parent"):
            source = dependencies[job["parent"]]
            parent = source["record"]
            if (
                parent["phase"] != "INIT"
                or parent["family"] != job["family"]
                or parent["variant"] != job["oracle_variant"]
                or parent["duration_s"] != protocol["epoch_init_duration_s"]
            ):
                raise ValueError("Oracle dependency is not the matching full actual INIT")
            with np.load(Path(source["data"]) / "last-state.npz", allow_pickle=False) as archive:
                carried = archive["state"].copy()
                source_clock = float(carried[-1])
            if carried.shape != state.shape:
                raise ValueError("Incomplete full actual INIT endpoint")
            state = carried.copy()
            state[-1] = 0.0
            if not np.array_equal(state[:-1], carried[:-1]):
                raise ValueError("Independent INIT carry changed a nonclock field")
            artifact.save_arrays(output / "carried-source.npz", source=carried, sim_initial=state)
            artifact.write_json(
                output / "carried-admission.json",
                phase.admission(context, state, raw["execution"]["dt"]),
            )
        else:
            source_clock = None
        setting = protocol["oracle"][job["oracle_variant"]]
        times = artifact.accepted_times(raw, protocol["base_dt_s"] / max(protocol["dt_divisors"]))
        boundaries = artifact.control_times(raw)
        atol = np.concatenate(
            [
                np.full(
                    np.prod(shape),
                    protocol["tolerances"]["clock_atol_s"] / 100
                    if key == "phase_clock_s"
                    else setting["charge_atol"]
                    if key.endswith("_C")
                    else setting["state_atol"],
                )
                for key, shape in context["shapes"].items()
            ]
        )
        history = np.empty((len(times), len(state)))
        history[0] = state
        populated = np.zeros(len(times), dtype=bool)
        populated[0] = True
        calls, maximum = 0, 0.0
        artifact.write_json(
            output / "inputs.json",
            dict(
                recipe=raw,
                job=job,
                dependencies=dependencies,
                source_phase_clock_s=source_clock,
                oracle_settings=setting,
                fixed_control_boundaries_s=boundaries,
                clock_policy="actual integrated clock; only an explicit INIT->SIM carry resets it",
            ),
        )
        artifact.write_json(
            output / "reference-dependencies.json", phase.dependency_manifest(bundle / "source")
        )
        artifact.save_arrays(output / "partial.npz", times=times[:1], state=history[:1])

        def domain(value, time):
            if not np.isfinite(value).all():
                raise ValueError("Nonfinite independent complete stage")
            fields = reference.unpack(context, value)
            if (
                abs(float(fields["phase_clock_s"][0]) - time)
                > protocol["tolerances"]["clock_atol_s"]
            ):
                raise ValueError("Independent physical and saved clocks disagree")
            for name in ("channel_gate", "junction_gate", "calcium_gate"):
                if np.any((fields[name] < 0) | (fields[name] > 1)):
                    raise ValueError("Independent physical gate left its strict domain")
            parent = context["parent"]
            if parent["finite_fuel"]:
                amount = parent["energy_initial"] + fields["energy_amount_increment_fmol"]
                if np.any(amount / parent["energy_volumes"] < 1e-9):
                    raise ValueError("Actual independent pools left the inherited1e-9mM domain")

        with (output / "progress.jsonl").open("x") as progress:
            for segment, (left, right) in enumerate(zip(boundaries, boundaries[1:], strict=False)):
                held = artifact.held_controls(raw, left)

                def rhs(time, value, *, left=left, segment=segment, held=held):
                    nonlocal calls, maximum, last, trial
                    calls += 1
                    last = dict(
                        segment=segment,
                        physical_time_s=float(time),
                        held_control_time_s=left,
                        held_controls=held,
                        rhs_evaluations=calls,
                    )
                    trial = dict(state=np.array(value, copy=True))
                    domain(value, float(time))
                    slope, phi, proof = reference.evaluate(context, value, held_time=left)
                    residual = abs(float(proof["physical_energy_balance_pJ_s"]))
                    if (
                        not np.isfinite(slope).all()
                        or not np.isfinite(phi).all()
                        or not np.isfinite(residual)
                        or residual > protocol["tolerances"]["rate_energy_atol_pJ_s"]
                    ):
                        raise ValueError("Independent full-stage field/energy identity failed")
                    maximum = max(maximum, residual)
                    if calls % 32 == 0:
                        artifact.write_progress(
                            progress, last | dict(max_rate_energy_error_pJ_s=maximum)
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
                    raise RuntimeError("Independent phase segment failed: " + solution.message)
                selected = np.flatnonzero((times > left) & (times <= right))
                history[selected] = solution.sol(times[selected]).T
                populated[selected] = True
                state = solution.y[:, -1]
                artifact.save_arrays(
                    output / "partial.npz", times=times[populated], state=history[populated]
                )
                artifact.write_progress(
                    progress,
                    dict(
                        segment_complete=segment,
                        physical_time_s=right,
                        saved_samples=int(populated.sum()),
                        rhs_evaluations=calls,
                    ),
                )
            if not populated.all():
                raise ValueError("Independent phase did not cover the full finest grid")
            potentials, metrics = [], []
            for i, time in enumerate(times):
                last = dict(
                    sample_index=i,
                    physical_time_s=float(time),
                    stage="accepted_oracle_audit",
                    held_controls=artifact.held_controls(raw, float(time)),
                )
                trial = dict(state=history[i].copy())
                domain(history[i], float(time))
                slope, phi, proof = reference.evaluate(context, history[i], held_time=float(time))
                if not np.isfinite(slope).all() or not np.isfinite(phi).all():
                    raise ValueError("Nonfinite independent accepted field")
                metric = artifact.check_proof(reference.conservation(context, history[i]), protocol)
                residual = abs(float(proof["physical_energy_balance_pJ_s"]))
                if (
                    not np.isfinite(residual)
                    or residual > protocol["tolerances"]["rate_energy_atol_pJ_s"]
                ):
                    raise ValueError("Independent accepted rate-energy identity failed")
                maximum = max(maximum, residual)
                potentials.append(phi)
                metrics.append(metric)
                artifact.write_progress(progress, last | dict(invariants=metric))
        chunks = []
        width = protocol["production"]["storage_window_steps"]
        for start in range(0, len(times) - 1, width):
            stop = min(start + width + 1, len(times))
            name = "trajectory-" + str(len(chunks)).zfill(4) + ".npz"
            artifact.save_arrays(
                output / name,
                times=times[start:stop],
                state=history[start:stop],
                potential_V=np.asarray(potentials[start:stop]),
            )
            chunks.append(
                dict(file=name, sha256=artifact.sha(output / name), start=start, stop=stop)
            )
        artifact.write_json(
            output / "trajectory-index.json", dict(samples=len(times), chunks=chunks)
        )
        artifact.save_arrays(output / "last-state.npz", state=history[-1], time_s=times[-1])
        artifact.write_json(output / "invariants.json", metrics)
        if any(name.split(".")[0] in {"cells", "jax", "jaxlib"} for name in sys.modules):
            raise RuntimeError("Independent integration imported production/JAX")
        artifact.success(
            output,
            artifact.identity(bundle, protocol, job, raw, job_id)
            | dict(
                variant=job["oracle_variant"],
                samples=len(times),
                complete_fields=len(context["shapes"]),
                state_shapes=context["shapes"],
                control_times_s=boundaries,
                rhs_evaluations=calls,
                max_rate_energy_error_pJ_s=maximum,
                source_dependency=source,
                source_phase_clock_s=source_clock,
                full_actual_INIT_carry=bool(source),
                imported_production_or_jax=False,
                source_nonclock_fields=len(context["shapes"]) - 1,
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
    parser.add_argument("--dependency-runs", type=Path)
    args = parser.parse_args()
    run(args.bundle, args.job, args.output, args.dependency_runs)


if __name__ == "__main__":
    main()
