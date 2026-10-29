"""Future full-grid eager CPU role using the qualified production RK4 laws."""

import argparse
from pathlib import Path

from validation.tissue import open_calcium_trajectory_common as artifact


def run(bundle, job_id, output):
    import numpy as np

    from cells.core.grid import EventGrid, checked_grid
    from cells.core.resources import trace_bytes
    from cells.core.schedule import control_values
    from cells.numerics.fixed_step import rk4_step
    from validation.tissue import open_calcium_reference as reference

    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    last, trial = {}, {}
    try:
        bundle = Path(bundle).resolve()
        protocol, job, raw = artifact.load_job(bundle, job_id, "production")
        if job["family"] == "calcium":
            from cells.core import surface_open_calcium_spec as schema
            from cells.models import surface_open_calcium as model
        else:
            from cells.core import surface_open_calcium_energy_spec as schema
            from cells.models import surface_open_calcium_energy as model

        spec = schema.parse(raw)
        state, layout = model.initial_values(spec)
        context = reference.bind(raw)
        expected_fields = 34 if job["family"] == "calcium" else 38
        if len(state) != len(context["shapes"]) or len(state) != expected_fields:
            raise ValueError("Incomplete physical state")
        grid = EventGrid(spec)
        reserved = trace_bytes(spec, len(grid) - 1)
        artifact.write_json(
            output / "inputs.json",
            dict(
                job_id=job_id,
                definition=raw,
                definition_sha256=artifact.digest(raw),
                protocol_sha256=artifact.digest(protocol),
                full_trace_reservation_bytes=reserved,
                max_trace_bytes=spec.execution.max_trace_bytes,
                complete_fields=expected_fields,
                state_type=model.STATE_TYPE.__name__,
                state_axes=model.STATE_AXES,
                layout_type=model.LAYOUT_TYPE.__name__,
                backend="numpy_cpu_float64_eager",
            ),
        )
        if reserved > spec.execution.max_trace_bytes:
            raise ValueError("Full original trajectory exceeds original trace cap")
        checked = checked_grid(spec, window_steps=len(grid) - 1)
        times = np.fromiter(checked, dtype=np.float64)
        planned = artifact.accepted_times(raw, spec.execution.dt)
        if not np.array_equal(times, planned):
            raise ValueError("Production EventGrid differs from independent exact event union")
        events = artifact.control_times(raw)
        if list(row.time for row in spec.experiment.changes) != events:
            raise ValueError("Production parser changed original control boundaries")
        controls = control_values(schema.equation_spec(spec), times)
        artifact.save_arrays(
            output / "layout-and-controls.npz",
            **{"layout__" + key: np.asarray(value) for key, value in layout._asdict().items()},
            **{"control__" + key: np.asarray(value) for key, value in controls._asdict().items()},
            times=times,
        )
        artifact.write_json(
            output / "array-layout.json",
            dict(
                state={
                    key: dict(
                        shape=list(np.asarray(value).shape), dtype=str(np.asarray(value).dtype)
                    )
                    for key, value in state._asdict().items()
                },
                layout_fields=list(layout._fields),
                control_fields=list(controls._fields),
                compact_fields=context["shapes"],
                state_axes=model.STATE_AXES,
            ),
        )
        history, compact, potentials = [], [], []
        total_stages, max_rate_error = 0, 0.0

        def one_control(index):
            return type(controls)(*(value[index] for value in controls))

        def capture(value, control, physical_time, **metadata):
            nonlocal last, trial
            last = dict(physical_time_s=float(physical_time), **metadata)
            trial = {
                "state__" + key: np.array(row, copy=True) for key, row in value._asdict().items()
            }
            trial.update(
                {
                    "control__" + key: np.array(row, copy=True)
                    for key, row in control._asdict().items()
                }
            )

        def field(value, control):
            if not bool(model.domain_valid(value, layout, layout.active, xp=np)):
                raise ValueError("Production trial left strict physical/padding/ceiling domain")
            reference.validate_padded_state(context, value._asdict())
            witness = model.readouts(value, control, layout, xp=np)
            if not bool(witness.valid):
                raise ValueError("Production stage/control/field solve is invalid")
            if not all(np.isfinite(row).all() for row in witness.derivative):
                raise ValueError("Nonfinite complete production derivative")
            if not np.isfinite(witness.field.potential_V).all():
                raise ValueError("Nonfinite production field potential")
            return witness

        def checkpoint():
            artifact.save_arrays(
                output / "partial.npz",
                times=times[: len(history)],
                state=np.asarray(compact),
                potential_V=np.asarray(potentials),
                **{
                    "full__" + key: np.stack([getattr(row, key) for row in history])
                    for key in state._fields
                },
            )

        with (output / "progress.jsonl").open("x") as progress:

            def accept(value, index):
                nonlocal max_rate_error
                time = float(times[index])
                control = one_control(index)
                capture(
                    value,
                    control,
                    time,
                    sample_index=index,
                    stage="accepted_audit",
                    held_control_time_s=time,
                )
                witness = field(value, control)
                residual = abs(float(witness.field.energy_balance_pJ_s))
                if (
                    not np.isfinite(residual)
                    or residual > protocol["tolerances"]["rate_energy_atol_pJ_s"]
                ):
                    raise ValueError("Production accepted-time energy identity failed")
                max_rate_error = max(max_rate_error, residual)
                # The exact original parent checks use the original anchors.
                model.check_values(value, spec)
                packed = reference.flatten(context, value._asdict())
                proof = artifact.check_proof(reference.conservation(context, packed), protocol)
                phi = witness.field.potential_V
                potential = np.r_[
                    phi[: layout.active.size][layout.active],
                    phi[layout.active.size :][layout.outside_active],
                ]
                history.append(type(value)(*(np.array(v, copy=True) for v in value)))
                compact.append(packed.copy())
                potentials.append(potential.copy())
                artifact.write_progress(
                    progress,
                    last
                    | dict(
                        independent_invariants=proof,
                        max_rate_energy_error_pJ_s=max_rate_error,
                        total_rk_stages=total_stages,
                    ),
                )
                if index % 16 == 0 or time in events or index == len(times) - 1:
                    checkpoint()

            accept(state, 0)
            for step, (left, right) in enumerate(zip(times, times[1:], strict=False)):
                control = one_control(step)
                duration = float(right - left)
                stage_count = 0

                def guarded_rhs(
                    value,
                    held,
                    parameters,
                    active,
                    *,
                    control=control,
                    step=step,
                    left=float(left),
                    right=float(right),
                    duration=duration,
                ):
                    nonlocal stage_count, total_stages, max_rate_error
                    if (
                        parameters is not layout
                        or active is not layout.active
                        or held is not control
                    ):
                        raise ValueError("RK4 changed held physical parameters/control")
                    if stage_count >= 4:
                        raise ValueError("Existing RK4 produced an unexpected stage")
                    fraction = (0.0, 0.5, 0.5, 1.0)[stage_count]
                    capture(
                        value,
                        held,
                        float(left) + fraction * duration,
                        step=step,
                        rk_stage=stage_count + 1,
                        step_s=duration,
                        held_control_time_s=float(left),
                        step_left_s=float(left),
                        step_right_s=float(right),
                        held_controls=artifact.held_controls(raw, float(left)),
                    )
                    witness = field(value, held)
                    residual = abs(float(witness.field.energy_balance_pJ_s))
                    if (
                        not np.isfinite(residual)
                        or residual > protocol["tolerances"]["rate_energy_atol_pJ_s"]
                    ):
                        raise ValueError("Production RK4 stage energy identity failed")
                    stage_count += 1
                    total_stages += 1
                    max_rate_error = max(max_rate_error, residual)
                    artifact.write_progress(progress, last | dict(rate_energy_error_pJ_s=residual))
                    return witness.derivative

                evolved = rk4_step(guarded_rhs, state, duration, control, layout, layout.active)
                if stage_count != 4:
                    raise ValueError("Existing RK4 did not produce exactly four checked stages")
                accept(evolved, step + 1)
                state = evolved
        if times[0] != 0.0 or times[-1] != protocol["duration_s"]:
            raise ValueError("Production duration changed")
        artifact.save_arrays(
            output / "trajectory.npz",
            times=times,
            state=np.asarray(compact),
            potential_V=np.asarray(potentials),
        )
        artifact.save_arrays(
            output / "full-state.npz",
            times=times,
            **{key: np.stack([getattr(row, key) for row in history]) for key in state._fields},
        )
        artifact.success(
            output,
            dict(
                job_id=job_id,
                family=job["family"],
                role="production",
                dt_divisor=job["dt_divisor"],
                dt_s=spec.execution.dt,
                bundle_manifest_sha256=artifact.sha(bundle / "manifest.json"),
                definition_sha256=artifact.digest(raw),
                protocol_sha256=artifact.digest(protocol),
                physics_sha256=artifact.digest(artifact.physical_definition(raw)),
                samples=len(times),
                duration_s=float(times[-1]),
                complete_fields=expected_fields,
                state_shapes=context["shapes"],
                control_times_s=events,
                rk_stages=total_stages,
                max_rate_energy_error_pJ_s=max_rate_error,
                full_trace_reservation_bytes=reserved,
                method=(
                    "qualified classical rk4_step; four guarded NumPy stages; original full checks"
                ),
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
