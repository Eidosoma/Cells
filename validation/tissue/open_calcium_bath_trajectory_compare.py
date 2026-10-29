"""Full-grid accuracy, all-observer refinement and actual INIT lineage checks.

Read completed role receipts only. Missing dependencies are never executed.
"""

import argparse
import math
from pathlib import Path

from validation.tissue import open_calcium_bath_trajectory_common as artifact
from validation.tissue.open_calcium_trajectory_compare import refinement


def difference(actual, expected):
    import numpy as np

    actual, expected = np.asarray(actual), np.asarray(expected)
    if actual.shape != expected.shape or actual.dtype.kind != expected.dtype.kind:
        raise ValueError("Compared complete arrays have different shapes or types")
    if not np.isfinite(actual).all() or not np.isfinite(expected).all():
        raise ValueError("Nonfinite complete comparison channel")
    return (
        np.logical_xor(actual, expected).astype(float)
        if actual.dtype.kind == "b"
        else actual - expected
    )


def maximum(error, budget):
    import numpy as np

    normalized = np.abs(error) / budget
    if not np.isfinite(normalized).all():
        raise ValueError("Nonfinite normalized trajectory error")
    return float(np.max(normalized, initial=0.0))


def selected_indices(times, wanted):
    import numpy as np

    lookup = {float(value): index for index, value in enumerate(times)}
    return np.asarray([lookup[float(value)] for value in wanted], dtype=int)


def phase_comparison(bundle, dataset, protocol, plan, sources, output):
    import numpy as np

    from validation.tissue import open_calcium_bath_reference as reference

    ids = plan["datasets"][dataset]
    raw = artifact.read_json(Path(bundle) / ids["definition"])
    context = reference.bind(raw)
    shapes = {name: list(value) for name, value in context["shapes"].items()}
    width = sum(math.prod(value) for value in shapes.values())
    node_count = len(raw["model"]["ionic"]["cells"]) + len(raw["model"]["ionic"]["extracellular"])
    loaded, records = {}, {}
    for name in ids["integrations"]:
        expected, receipt = plan["jobs"][name], sources[name]
        record = receipt["record"]
        identity = artifact.identity(
            bundle,
            protocol,
            expected,
            artifact.read_json(Path(bundle) / expected["definition"]),
            name,
        )
        wanted = identity | dict(
            state_shapes=shapes,
            complete_fields=len(shapes),
            control_times_s=artifact.control_times(raw),
        )
        if any(record.get(key) != value for key, value in wanted.items()):
            raise ValueError(
                "Dependency changed source, full fields, controls or duration: " + name
            )
        rows = artifact.read_chunks(receipt["data"])
        dt = protocol["base_dt_s"] / expected.get("dt_divisor", max(protocol["dt_divisors"]))
        grid = artifact.accepted_times(raw, dt)
        if (
            not np.array_equal(rows["times"], grid)
            or record["samples"] != len(grid)
            or len(grid) != expected["expected_samples"]
            or rows["state"].shape != (len(grid), width)
            or rows["potential_V"].shape != (len(grid), node_count)
            or not np.isfinite(rows["state"]).all()
            or not np.isfinite(rows["potential_V"]).all()
        ):
            raise ValueError("Dependency lacks its complete finite accepted grid: " + name)
        if not expected["is_epoch"] and not np.array_equal(
            rows["state"][0], reference.initial(context)
        ):
            raise ValueError("Original physical initial state changed: " + name)
        if expected["role"] == "production":
            if record["rk_stages"] != 4 * (len(grid) - 1):
                raise ValueError("Not every production RK4 stage was guarded")
            if set(record["observer_fields"]) != set(expected["observer_fields"]):
                raise ValueError("Production observer inventory changed")
            keys = {"times", "state", "potential_V"}
            keys |= {"full__" + key for key in shapes}
            keys |= {"observer__" + key for key in expected["observer_fields"]}
            if set(rows) != keys:
                raise ValueError("Full padded physical/observer trajectory is incomplete")
            for i in range(len(grid)):
                values = {key: rows["full__" + key][i] for key in shapes}
                reference.owner.validate_padded_state(
                    context["parent"],
                    {
                        key: value
                        for key, value in values.items()
                        if key in context["parent"]["shapes"]
                    },
                )
                if not np.array_equal(reference.flatten(context, values), rows["state"][i]):
                    raise ValueError("Full physical state and compact trajectory disagree")
                for key in shapes:
                    if not np.isfinite(values[key]).all():
                        raise ValueError("Nonfinite full padded field: " + key)
                extra = values["reservoir_chemical_work_pJ"]
                if (
                    extra.shape != (raw["execution"]["extracellular_capacity"],)
                    or extra.dtype != np.dtype("float64")
                    or np.any(extra[len(raw["model"]["ionic"]["extracellular"]) :] != 0)
                    or values["phase_clock_s"].shape != (1,)
                    or values["phase_clock_s"].dtype != np.dtype("float64")
                ):
                    raise ValueError("Complete bath work/clock shape, dtype or padding changed")
        elif (
            record["variant"] != expected["oracle_variant"]
            or record["imported_production_or_jax"]
            or set(rows) != {"times", "state", "potential_V"}
        ):
            raise ValueError("Independent oracle identity/independence changed")
        loaded[name], records[name] = rows, record

    projection = sources[ids["projection"]]
    pjob = plan["jobs"][ids["projection"]]
    wanted = artifact.identity(bundle, protocol, pjob, raw, ids["projection"])
    if any(projection["record"].get(key) != value for key, value in wanted.items()):
        raise ValueError("Observer projection identity changed")
    if set(projection["record"]["observer_fields"]) != set(pjob["observer_fields"]):
        raise ValueError("Independent-state observer projection inventory changed")
    oracle_rows, projected = {}, {}
    for variant, name in ids["oracles"].items():
        oracle_rows[variant] = loaded[name]
        projected[variant] = artifact.read_chunks(Path(projection["data"]) / variant)
        expected_keys = {"times", *("observer__" + key for key in pjob["observer_fields"])}
        if (
            set(projected[variant]) != expected_keys
            or not np.array_equal(projected[variant]["times"], loaded[name]["times"])
            or projection["record"]["variants"][variant]["source_result_sha256"]
            != sources[name]["child_result_sha256"]
        ):
            raise ValueError("Projection is not tied to the exact independent full-grid states")

    tight, standard = oracle_rows["tight"], oracle_rows["standard"]
    if not np.array_equal(tight["times"], standard["times"]):
        raise ValueError("Oracle tightening used different accepted clocks")
    state_budget = artifact.state_budget(context, tight["state"], protocol)
    channels = {}
    offset = 0
    for key, shape in shapes.items():
        size = math.prod(shape)
        channels["state__" + key] = (
            tight["state"][:, offset : offset + size],
            standard["state"][:, offset : offset + size],
            state_budget[:, offset : offset + size],
        )
        offset += size
    channels["potential_V"] = (
        tight["potential_V"],
        standard["potential_V"],
        protocol["tolerances"]["field_potential_atol_V"]
        + protocol["tolerances"]["field_potential_rtol"] * np.abs(tight["potential_V"]),
    )
    for key in pjob["observer_fields"]:
        target = projected["tight"]["observer__" + key]
        budget = (
            np.full(target.shape, 0.5)  # Any Boolean mismatch exceeds accuracy budget.
            if target.dtype.kind == "b"
            else artifact.observer_budget(key, target, protocol)
        )
        channels["observer__" + key] = (target, projected["standard"]["observer__" + key], budget)

    arrays, uncertainty, accuracy, refined, violations = {}, {}, {}, {}, []
    coarse_times = loaded[ids["production"]["1"]]["times"]
    coarse_ref = selected_indices(tight["times"], coarse_times)
    arrays.update(oracle_times=tight["times"], common_times=coarse_times)
    for key, (target, ordinary, budget) in channels.items():
        error = difference(ordinary, target)
        uncertainty[key] = maximum(error, budget)
        arrays["oracle_difference__" + key], arrays["budget__" + key] = error, budget
        common = []
        for divisor in protocol["dt_divisors"]:
            name = ids["production"][str(divisor)]
            rows = loaded[name]
            selected = selected_indices(tight["times"], rows["times"])
            if key.startswith("state__"):
                field = key.removeprefix("state__")
                start = sum(
                    math.prod(value)
                    for name, value in shapes.items()
                    if list(shapes).index(name) < list(shapes).index(field)
                )
                actual = rows["state"][:, start : start + math.prod(shapes[field])]
            else:
                actual = rows[key]
            error = difference(actual, target[selected])
            accuracy.setdefault(str(divisor), {})[key] = maximum(error, budget[selected])
            arrays["dt" + str(divisor) + "_difference__" + key] = error
            common.append(actual[selected_indices(rows["times"], coarse_times)])
        d1, d2 = difference(common[0], common[1]), difference(common[1], common[2])
        refined[key] = refinement(
            maximum(d1, budget[coarse_ref]),
            maximum(d2, budget[coarse_ref]),
            protocol["refinement"]["roundoff_resolution_fraction"],
        )
        arrays["coarse_middle_difference__" + key] = d1
        arrays["middle_fine_difference__" + key] = d2
    if any(
        value > protocol["tolerances"]["oracle_tightening_max_fraction_of_budget"]
        for value in uncertainty.values()
    ):
        violations.append("oracle tightening exceeds its fixed uncertainty share")
    if any(value > 1.0 for row in accuracy.values() for value in row.values()):
        violations.append("production full state/observer trajectory exceeds fixed accuracy budget")
    if any(not row["passed"] for row in refined.values()):
        violations.append("resolved state/observer differences fail fixed refinement criterion")
    record = dict(
        dataset=dataset,
        duration_s=raw["experiment"]["end_time"],
        complete_fields=len(shapes),
        observer_fields=pjob["observer_fields"],
        oracle_uncertainty_fraction=uncertainty,
        accuracy=accuracy,
        refinement=refined,
        common_samples=len(coarse_times),
        violations=violations,
        observer_scope=(
            "qualified observer map at independent states; temporal/state-to-observer accuracy"
        ),
    )
    artifact.save_arrays(output / (dataset + "-comparison.npz"), **arrays)
    artifact.write_json(output / (dataset + "-comparison.json"), record)
    return record, loaded, records


def check_carry(plan, dataset, sources, trajectories, records, protocol):
    import numpy as np

    result = {}
    for name in plan["datasets"][dataset]["integrations"]:
        parent = plan["jobs"][name]["parent"]
        before, after = trajectories[parent], trajectories[name]
        receipt = records[name]
        source = receipt["source_dependency"]
        if (
            not receipt["full_actual_INIT_carry"]
            or source["result_sha256"] != sources[parent]["result_sha256"]
            or source["child_result_sha256"] != sources[parent]["child_result_sha256"]
            or records[parent]["phase"] != "INIT"
            or records[parent]["duration_s"] != protocol["epoch_init_duration_s"]
            or not np.array_equal(before["state"][-1, :-1], after["state"][0, :-1])
            or after["state"][0, -1] != 0.0
            or receipt["source_phase_clock_s"] != before["state"][-1, -1]
        ):
            raise ValueError("Full actual INIT endpoint/clock carry disagrees: " + name)
        if plan["jobs"][name]["role"] == "production":
            for key in after:
                if key.startswith("full__") and key != "full__phase_clock_s":
                    if not np.array_equal(before[key][-1], after[key][0]):
                        raise ValueError("Actual full padded INIT array changed: " + key)
        result[name] = dict(
            parent=parent,
            source_child_result_sha256=source["child_result_sha256"],
            exact_nonclock_carry=True,
            reset_clock_only=True,
        )
    return result


def run(bundle, job_id, output, dependency_runs):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    last = {}
    try:
        bundle = Path(bundle).resolve()
        protocol, job, raw = artifact.load_job(bundle, job_id, "compare")
        plan = artifact.read_json(bundle / "plan.json")
        sources = artifact.dependencies(bundle, job, dependency_runs)
        phases, trajectories, records = {}, {}, {}
        for dataset in job["compare_datasets"]:
            last = dict(stage="all_channel_phase_comparison", dataset=dataset)
            phases[dataset], data, receipts = phase_comparison(
                bundle, dataset, protocol, plan, sources, output
            )
            trajectories.update(data)
            records.update(receipts)
        last = dict(stage="exact_full_actual_INIT_lineage")
        carry = (
            check_carry(plan, job["dataset"], sources, trajectories, records, protocol)
            if job["is_epoch"]
            else {}
        )
        violations = [
            dataset + ": " + value for dataset, row in phases.items() for value in row["violations"]
        ]
        record = artifact.identity(bundle, protocol, job, raw, job_id) | dict(
            phase_comparisons=phases,
            actual_INIT_carry=carry,
            dependencies=sources,
            violations=violations,
            claim=(
                "full8us scheduled-bath temporal coupling; no biological/native/performance claim"
            ),
        )
        artifact.write_json(output / "comparison.json", record)
        if violations:
            raise ValueError("; ".join(violations))
        artifact.success(output, record)
    except BaseException as error:
        artifact.failure(output, error, context=last)
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
