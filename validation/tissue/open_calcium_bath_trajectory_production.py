"""Future guarded RK4 phase roles with bounded recording and actual INIT carry."""

import argparse
from pathlib import Path

from validation.tissue import open_calcium_bath_trajectory_common as artifact


def run(bundle, job_id, output, dependency_runs=None):
    import numpy as np

    from cells.core.grid import EventGrid, checked_grid
    from cells.core.resources import trace_bytes
    from cells.core.schedule import control_values, event_index
    from cells.core.state import Checkpoint
    from cells.numerics.fixed_step import rk4_step
    from validation.tissue import open_calcium_bath_reference as reference
    from validation.topology import open_calcium_bath_phase_handoff_reference as phase_reference

    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    last, trial = {}, {}
    try:
        bundle = Path(bundle).resolve()
        protocol, job, raw = artifact.load_job(bundle, job_id, "production")
        parents = artifact.dependencies(bundle, job, dependency_runs)
        if job["family"] == "calcium":
            from cells.core import surface_open_calcium_bath_epoch_spec as epoch_schema
            from cells.core import surface_open_calcium_bath_events_spec as ordinary_schema
            from cells.models import surface_open_calcium_bath_epoch as epoch_model
            from cells.models import surface_open_calcium_bath_events as ordinary_model
        else:
            from cells.core import surface_open_calcium_energy_bath_epoch_spec as epoch_schema
            from cells.core import surface_open_calcium_energy_bath_events_spec as ordinary_schema
            from cells.models import surface_open_calcium_energy_bath_epoch as epoch_model
            from cells.models import surface_open_calcium_energy_bath_events as ordinary_model
        source = None
        if job.get("parent"):
            from cells.core import open_calcium_bath_phase_handoff as bridge

            source = parents[job["parent"]]
            record = source["record"]
            if (
                record["phase"] != "INIT"
                or record["family"] != job["family"]
                or record["dt_divisor"] != job["dt_divisor"]
                or record["duration_s"] != protocol["epoch_init_duration_s"]
            ):
                raise ValueError("Require the matching completed full actual INIT resolution")
            definition = artifact.read_json(Path(source["data"]) / "checkpoint.json")
            source_spec = ordinary_schema.parse(definition["definition"])
            zero, original_layout = ordinary_model.initial_values(source_spec)
            with np.load(Path(source["data"]) / "last-state.npz", allow_pickle=False) as archive:
                source_state = ordinary_model.STATE_TYPE(
                    *(archive["full__" + key].copy() for key in zero._fields)
                )
                source_layout = ordinary_model.LAYOUT_TYPE(
                    *(archive["layout__" + key].copy() for key in original_layout._fields)
                )
            trial = {
                "source__" + key: np.asarray(value) for key, value in source_state._asdict().items()
            }
            last = dict(stage="actual_INIT_checkpoint_handoff", source=source)
            point = Checkpoint(
                source_state,
                source_layout,
                definition["time_s"],
                definition["step_index"],
                definition["event_index"],
            )
            request = dict(
                kind=bridge.REQUEST_KIND,
                policies=epoch_schema.POLICIES,
                source=bridge.capture_source(source_spec, point),
                simulation=raw,
            )
            artifact.write_json(output / "epoch-request.json", request)
            prepared = bridge.prepare(request)
            artifact.write_json(output / "epoch-definition.json", prepared.definition)
            artifact.write_json(output / "epoch-provenance.json", prepared.provenance)
            schema, model = epoch_schema, epoch_model
            spec = schema.parse(prepared.definition)
            state, layout = model.initial_values(spec)
            for key in state._fields:
                expected = (
                    np.zeros_like(state.phase_clock_s)
                    if key == "phase_clock_s"
                    else getattr(source_state, key)
                )
                if not np.array_equal(getattr(state, key), expected):
                    raise ValueError("Actual full INIT carry changed a saved array: " + key)
            context, independent_initial = phase_reference.verify_epoch(prepared.definition)
            if not np.array_equal(reference.flatten(context, state._asdict()), independent_initial):
                raise ValueError("Independent complete carried-state verification disagrees")
            source_clock = float(source_state.phase_clock_s[0])
        else:
            schema, model = ordinary_schema, ordinary_model
            spec = schema.parse(raw)
            state, layout = model.initial_values(spec)
            context = reference.bind(raw)
            source_clock = None
        expected_fields = 36 if job["family"] == "calcium" else 40
        if len(state) != expected_fields or len(context["shapes"]) != expected_fields:
            raise ValueError("Incomplete physical calcium/fuel bath state")
        # Full clock validation is independent of small execution recording
        # windows. checked_grid retains its storage-capped validation batches.
        grid = checked_grid(spec, window_steps=1024)
        times = np.fromiter(grid, dtype=np.float64)
        if not np.array_equal(times, artifact.accepted_times(raw, spec.execution.dt)):
            raise ValueError("Production and independently prepared event clocks disagree")
        width = protocol["production"]["storage_window_steps"]
        while width > 1 and trace_bytes(spec, width, width + 1) > spec.execution.max_trace_bytes:
            width //= 2
        reservation = trace_bytes(spec, width, width + 1)
        if reservation > spec.execution.max_trace_bytes:
            raise ValueError("Even the smallest recording window exceeds original trace cap")
        ordinary = schema.scheduled_spec(spec) if source else spec
        controls = control_values(ordinary_schema.owner_spec(ordinary), times)
        artifact.write_json(
            output / "inputs.json",
            dict(
                recipe=raw,
                job=job,
                dependencies=parents,
                source_phase_clock_s=source_clock,
                storage_window_steps=width,
                window_trace_reservation_bytes=reservation,
                original_max_trace_bytes=spec.execution.max_trace_bytes,
                original_max_steps=spec.execution.max_steps,
                complete_fields=expected_fields,
                observer_fields=list(model.OBSERVATION_FIELDS),
                numerical_backend="guarded NumPy RK4 float64",
            ),
        )
        artifact.save_arrays(
            output / "layout-and-controls.npz",
            times=times,
            **{"layout__" + key: np.asarray(value) for key, value in layout._asdict().items()},
            **{"control__" + key: np.asarray(value) for key, value in controls._asdict().items()},
        )
        chunks, states, compact, potentials, buffer_times = [], [], [], [], []
        total_stages, maximum, saved_samples = 0, 0.0, 0

        def one_control(i):
            return type(controls)(*(value[i] for value in controls))

        def capture(value, u, time, **metadata):
            nonlocal last, trial
            last = dict(physical_time_s=float(time), **metadata)
            trial = {
                "state__" + key: np.array(row, copy=True) for key, row in value._asdict().items()
            }
            trial.update(
                {"control__" + key: np.array(row, copy=True) for key, row in u._asdict().items()}
            )

        def field(value, u, time):
            if (
                not model.domain_valid(value, layout, layout.active, xp=np)
                or abs(float(value.phase_clock_s[0]) - float(time))
                > protocol["tolerances"]["clock_atol_s"]
            ):
                raise ValueError("Production stage left its strict physical/clock domain")
            witness = model.readouts(value, u, layout, xp=np)
            if (
                not witness.valid
                or not np.isfinite(witness.field.potential_V).all()
                or not all(np.isfinite(row).all() for row in witness.derivative)
            ):
                raise ValueError("Invalid complete production bath field/derivative")
            return witness

        def flush(final=False):
            nonlocal saved_samples
            history = model.STATE_TYPE(
                *(np.stack([getattr(row, key) for row in states]) for key in state._fields)
            )
            sample_times = np.asarray(buffer_times)
            observed = model.observe_history(sample_times, history, layout, sample_times, spec)
            if set(vars(observed)) != set(model.OBSERVATION_FIELDS):
                raise ValueError("Incomplete qualified observer output")
            name = "trajectory-" + str(len(chunks)).zfill(4) + ".npz"
            artifact.save_arrays(
                output / name,
                times=sample_times,
                state=np.asarray(compact),
                potential_V=np.asarray(potentials),
                **{"full__" + key: np.asarray(value) for key, value in history._asdict().items()},
                **{"observer__" + key: np.asarray(value) for key, value in vars(observed).items()},
            )
            saved_samples += len(sample_times) - bool(chunks)
            chunks.append(
                dict(file=name, sha256=artifact.sha(output / name), rows=len(sample_times))
            )
            artifact.write_json(
                output / ("trajectory-index.json" if final else "trajectory-index.partial.json"),
                dict(samples=saved_samples, chunks=chunks),
            )
            artifact.save_arrays(
                output / "partial.npz",
                time_s=sample_times[-1],
                state=compact[-1],
                **{"full__" + key: getattr(states[-1], key) for key in state._fields},
            )

        with (output / "progress.jsonl").open("x") as progress:

            def accept(value, index):
                nonlocal maximum
                time, u = float(times[index]), one_control(index)
                capture(value, u, time, stage="accepted_state", sample_index=index)
                witness = field(value, u, time)
                residual = abs(float(witness.field.energy_balance_pJ_s))
                if (
                    not np.isfinite(residual)
                    or residual > protocol["tolerances"]["rate_energy_atol_pJ_s"]
                ):
                    raise ValueError("Production accepted rate-energy identity failed")
                maximum = max(maximum, residual)
                if states:
                    pair = model.STATE_TYPE(
                        *(np.stack((a, b)) for a, b in zip(states[-1], value, strict=True))
                    )
                    model.check_values(pair, spec)
                else:
                    model.check_values(value, spec)
                packed = reference.flatten(context, value._asdict())
                metric = artifact.check_proof(reference.conservation(context, packed), protocol)
                phi = witness.field.potential_V
                potentials.append(
                    np.r_[
                        phi[: layout.active.size][layout.active],
                        phi[layout.active.size :][layout.outside_active],
                    ]
                )
                states.append(type(value)(*(np.array(row, copy=True) for row in value)))
                compact.append(packed.copy())
                buffer_times.append(time)
                artifact.write_progress(
                    progress,
                    last
                    | dict(
                        independent_invariants=metric,
                        max_rate_energy_error_pJ_s=maximum,
                        total_rk_stages=total_stages,
                    ),
                )

            accept(state, 0)
            for step, (left, right) in enumerate(zip(times, times[1:], strict=False)):
                u, duration, stage_count = one_control(step), float(right - left), 0

                def rhs(
                    value,
                    held,
                    p,
                    active,
                    *,
                    step=step,
                    left=float(left),
                    right=float(right),
                    duration=duration,
                    expected=u,
                ):
                    nonlocal stage_count, total_stages, maximum
                    if (
                        p is not layout
                        or active is not layout.active
                        or held is not expected
                        or stage_count >= 4
                    ):
                        raise ValueError("Qualified RK4 parameter/control/stage contract changed")
                    time = left + (0.0, 0.5, 0.5, 1.0)[stage_count] * duration
                    capture(
                        value,
                        held,
                        time,
                        step=step,
                        rk_stage=stage_count + 1,
                        step_left_s=left,
                        step_right_s=right,
                        step_s=duration,
                        held_control_time_s=left,
                        held_controls=artifact.held_controls(raw, left),
                    )
                    witness = field(value, held, time)
                    residual = abs(float(witness.field.energy_balance_pJ_s))
                    if (
                        not np.isfinite(residual)
                        or residual > protocol["tolerances"]["rate_energy_atol_pJ_s"]
                    ):
                        raise ValueError("Production RK4 stage energy identity failed")
                    stage_count += 1
                    total_stages += 1
                    maximum = max(maximum, residual)
                    artifact.write_progress(progress, last | dict(rate_energy_error_pJ_s=residual))
                    return model.STATE_TYPE(*witness.derivative)

                evolved = rk4_step(rhs, state, duration, u, layout, layout.active)
                if stage_count != 4:
                    raise ValueError("Production did not check exactly four RK4 stages")
                accept(evolved, step + 1)
                state = evolved
                if len(states) == width + 1 or step + 1 == len(times) - 1:
                    final = step + 1 == len(times) - 1
                    flush(final=final)
                    if not final:
                        states[:], compact[:], potentials[:], buffer_times[:] = (
                            [states[-1]],
                            [compact[-1]],
                            [potentials[-1]],
                            [buffer_times[-1]],
                        )
        if saved_samples != len(times) or times[-1] != protocol["duration_s"]:
            raise ValueError("Production phase lost rows or changed the original duration")
        artifact.save_arrays(
            output / "last-state.npz",
            state=compact[-1],
            time_s=times[-1],
            **{"full__" + key: getattr(state, key) for key in state._fields},
            **{"layout__" + key: value for key, value in layout._asdict().items()},
        )
        artifact.write_json(
            output / "checkpoint.json",
            dict(
                definition=ordinary_schema.to_dict(ordinary),
                time_s=float(times[-1]),
                step_index=len(EventGrid(ordinary)) - 1,
                event_index=event_index(ordinary, float(times[-1])),
            ),
        )
        artifact.success(
            output,
            artifact.identity(bundle, protocol, job, raw, job_id)
            | dict(
                dt_divisor=job["dt_divisor"],
                dt_s=spec.execution.dt,
                samples=len(times),
                complete_fields=expected_fields,
                state_shapes=context["shapes"],
                control_times_s=artifact.control_times(raw),
                rk_stages=total_stages,
                max_rate_energy_error_pJ_s=maximum,
                source_dependency=source,
                source_phase_clock_s=source_clock,
                full_actual_INIT_carry=bool(source),
                source_nonclock_fields=expected_fields - 1,
                observer_fields=list(model.OBSERVATION_FIELDS),
                storage_window_steps=width,
                window_trace_reservation_bytes=reservation,
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
