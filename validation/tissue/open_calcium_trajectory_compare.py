"""Compare separately completed full-grid roles; never run missing dependencies."""

import argparse
import math
from pathlib import Path

from validation.tissue import open_calcium_trajectory_common as artifact


def refinement(first, second, floor):
    d1, d2 = float(first), float(second)
    if d1 <= floor and d2 <= floor:
        return dict(
            coarse_middle_over_budget=d1,
            middle_fine_over_budget=d2,
            status="below_refinement_resolution",
            observed_order=None,
            passed=True,
        )
    passed = d2 < d1 and d1 >= 8.0 * d2
    return dict(
        coarse_middle_over_budget=d1,
        middle_fine_over_budget=d2,
        status="resolved_refinement",
        observed_order=math.log2(d1) - math.log2(d2) if d2 > 0 and d1 > 0 else None,
        fine_difference_exactly_zero=d2 == 0.0,
        minimum_order=3.0,
        passed=passed,
    )


def run(bundle, job_id, output, dependency_runs):
    import numpy as np

    from validation.tissue import open_calcium_reference as reference

    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    last, arrays = {}, {}
    try:
        bundle = Path(bundle).resolve()
        protocol, job, raw = artifact.load_job(bundle, job_id, "compare")
        plan = artifact.read_json(bundle / "plan.json")
        paths = artifact.read_json(dependency_runs)
        if set(paths) != set(job["requires"]):
            raise ValueError("Provide exactly the five completed roles for this family")
        context = reference.bind(raw)
        shapes = {key: list(shape) for key, shape in context["shapes"].items()}
        width = sum(math.prod(shape) for shape in shapes.values())
        node_count = len(raw["model"]["ionic"]["cells"]) + len(
            raw["model"]["ionic"]["extracellular"]
        )
        manifest_sha = artifact.sha(bundle / "manifest.json")
        events = artifact.control_times(raw)
        loaded, receipts = {}, {}
        for name in job["requires"]:
            last = dict(dependency=name)
            directory = Path(paths[name]).resolve()
            supervisor = artifact.verify_result(directory)
            if supervisor["job_id"] != name or supervisor["bundle_manifest_sha256"] != manifest_sha:
                raise ValueError("Dependency supervisor belongs to another job/source capture")
            resource = artifact.read_json(directory / "guard/result.json")
            if resource["status"] != "completed" or resource["returncode"] != 0:
                raise ValueError("Dependency resource supervisor did not complete")
            data = directory / "data"
            record = artifact.verify_result(data)
            wanted = plan["jobs"][name]
            checks = dict(
                job_id=name,
                family=job["family"],
                role=wanted["role"],
                bundle_manifest_sha256=manifest_sha,
                definition_sha256=wanted["definition_sha256"],
                protocol_sha256=artifact.digest(protocol),
                physics_sha256=job["physics_sha256"],
                duration_s=protocol["duration_s"],
                control_times_s=events,
                state_shapes=shapes,
                complete_fields=len(shapes),
            )
            if any(record.get(key) != value for key, value in checks.items()):
                raise ValueError(
                    "Dependency changed duration, physics, fields or controls: " + name
                )
            if artifact.sha(data / "result.json") != supervisor["qualifier_result_sha256"]:
                raise ValueError("Dependency child receipt changed after supervision")
            with np.load(data / "trajectory.npz", allow_pickle=False) as archive:
                times, state, phi = (
                    archive[key].copy() for key in ("times", "state", "potential_V")
                )
            dt = protocol["base_dt_s"] / (wanted.get("dt_divisor") or max(protocol["dt_divisors"]))
            planned_raw = artifact.read_json(bundle / wanted["definition"])
            expected_times = artifact.accepted_times(planned_raw, dt)
            if (
                not np.array_equal(times, expected_times)
                or state.shape != (len(times), width)
                or phi.shape != (len(times), node_count)
                or record["samples"] != len(times)
                or not np.isfinite(state).all()
                or not np.isfinite(phi).all()
            ):
                raise ValueError("Dependency full-grid trajectory is incomplete/nonfinite: " + name)
            if not np.array_equal(state[0], reference.initial(context)):
                raise ValueError("Dependency changed the original initial physical state")
            if wanted["role"] == "production":
                if record["rk_stages"] != 4 * (len(times) - 1):
                    raise ValueError("Production did not check every RK4 trial")
                with np.load(data / "full-state.npz", allow_pickle=False) as full:
                    if set(full.files) != {"times", *shapes} or not np.array_equal(
                        full["times"], times
                    ):
                        raise ValueError("Incomplete full padded production state archive")
                    full_values = {key: full[key] for key in shapes}
                    for i in range(len(times)):
                        values = {key: full_values[key][i] for key in shapes}
                        reference.validate_padded_state(context, values)
                        if not np.array_equal(reference.flatten(context, values), state[i]):
                            raise ValueError(
                                "Compact state disagrees with preserved full physical history"
                            )
            else:
                if (
                    record["variant"] != wanted["oracle_variant"]
                    or record["imported_production_or_jax"]
                ):
                    raise ValueError("Independent oracle role/independence changed")
            loaded[name] = (times, state, phi)
            receipts[name] = dict(
                path=str(directory),
                result_sha256=artifact.sha(directory / "result.json"),
                child_result_sha256=artifact.sha(data / "result.json"),
            )

        family = job["family"]
        tight = loaded[family + "-oracle_tight"]
        standard = loaded[family + "-oracle_standard"]
        if not np.array_equal(tight[0], standard[0]):
            raise ValueError("Oracle tightening used different sampling clocks")
        budget = artifact.error_budget(context, tight[1], protocol)
        phi_budget = protocol["tolerances"]["field_potential_atol_V"] + protocol["tolerances"][
            "field_potential_rtol"
        ] * np.abs(tight[2])
        uncertainty = dict(
            state=float(np.max(np.abs(standard[1] - tight[1]) / budget, initial=0)),
            potential=float(np.max(np.abs(standard[2] - tight[2]) / phi_budget, initial=0)),
        )
        arrays.update(
            oracle_times=tight[0],
            oracle_state_difference=standard[1] - tight[1],
            oracle_potential_difference=standard[2] - tight[2],
            state_budget=budget,
            potential_budget=phi_budget,
        )
        tight_index = {float(time): i for i, time in enumerate(tight[0])}
        accuracy, common_states, common_phi = {}, [], []
        coarse_times = loaded[family + "-production_dt1"][0]
        coarse_ref = np.asarray([tight_index[float(time)] for time in coarse_times])
        for divisor in protocol["dt_divisors"]:
            name = family + "-production_dt" + str(divisor)
            times, state, phi = loaded[name]
            selected = np.asarray([tight_index[float(time)] for time in times])
            state_error = state - tight[1][selected]
            phi_error = phi - tight[2][selected]
            normalized = np.abs(state_error) / budget[selected]
            offset, by_field = 0, {}
            for key, shape in shapes.items():
                size = math.prod(shape)
                by_field[key] = float(np.max(normalized[:, offset : offset + size], initial=0))
                offset += size
            accuracy[str(divisor)] = dict(
                samples=len(times),
                state_error_over_budget=float(np.max(normalized, initial=0)),
                potential_error_over_budget=float(
                    np.max(np.abs(phi_error) / phi_budget[selected], initial=0)
                ),
                per_field_error_over_budget=by_field,
            )
            arrays.update(
                {
                    "dt" + str(divisor) + "_times": times,
                    "dt" + str(divisor) + "_state_error": state_error,
                    "dt" + str(divisor) + "_potential_error": phi_error,
                }
            )
            index = {float(time): i for i, time in enumerate(times)}
            shared = np.asarray([index[float(time)] for time in coarse_times])
            common_states.append(state[shared])
            common_phi.append(phi[shared])
        resolution = protocol["refinement"]["roundoff_resolution_fraction"]
        state_differences = [
            float(np.max(np.abs(a - b) / budget[coarse_ref], initial=0))
            for a, b in zip(common_states, common_states[1:], strict=False)
        ]
        phi_differences = [
            float(np.max(np.abs(a - b) / phi_budget[coarse_ref], initial=0))
            for a, b in zip(common_phi, common_phi[1:], strict=False)
        ]
        refined = dict(
            state=refinement(*state_differences, resolution),
            potential=refinement(*phi_differences, resolution),
        )
        arrays.update(
            common_times=coarse_times,
            coarse_minus_middle_state=common_states[0] - common_states[1],
            middle_minus_fine_state=common_states[1] - common_states[2],
            coarse_minus_middle_potential=common_phi[0] - common_phi[1],
            middle_minus_fine_potential=common_phi[1] - common_phi[2],
        )
        violations = []
        limit = protocol["tolerances"]["oracle_tightening_max_fraction_of_budget"]
        if any(value > limit for value in uncertainty.values()):
            violations.append("independent oracle tightening exceeds its fixed uncertainty share")
        if any(
            row[key] > 1.0
            for row in accuracy.values()
            for key in ("state_error_over_budget", "potential_error_over_budget")
        ):
            violations.append("a full production trajectory exceeds its fixed accuracy budget")
        if not all(row["passed"] for row in refined.values()):
            violations.append("resolved timestep differences fail the fixed refinement criterion")
        record = dict(
            job_id=job_id,
            family=family,
            role="compare",
            duration_s=protocol["duration_s"],
            bundle_manifest_sha256=manifest_sha,
            protocol_sha256=artifact.digest(protocol),
            physics_sha256=job["physics_sha256"],
            complete_fields=len(shapes),
            oracle_uncertainty_fraction=uncertainty,
            accuracy=accuracy,
            refinement=refined,
            dependencies=receipts,
            common_samples=len(coarse_times),
            violations=violations,
            claim=(
                "Full original8us mixed static exterior; "
                "complete accepted-grid temporal accuracy only"
            ),
        )
        artifact.save_arrays(output / "comparison.npz", **arrays)
        artifact.write_json(output / "comparison.json", record)
        if violations:
            raise ValueError("; ".join(violations))
        artifact.success(output, record)
    except BaseException as error:
        artifact.failure(output, error, context=last, arrays=arrays)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--job", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--dependency-runs", required=True, type=Path)
    args = parser.parse_args()
    run(args.bundle, args.job, args.output, args.dependency_runs)


if __name__ == "__main__":
    main()
