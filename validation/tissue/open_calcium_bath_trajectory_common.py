"""Prepared bath trajectory artifacts; no model import or numerical launch."""

from pathlib import Path

from validation.tissue import open_calcium_trajectory_common as prior

read_json = prior.read_json
sha, digest = prior.sha, prior.digest
save_arrays, failure, success = prior.save_arrays, prior.failure, prior.success
write_progress, verify_result, verify_bundle = (
    prior.write_progress,
    prior.verify_result,
    prior.verify_bundle,
)
accepted_times, control_times, held_controls = (
    prior.accepted_times,
    prior.control_times,
    prior.held_controls,
)


def json_values(value):
    if isinstance(value, dict):
        return {key: json_values(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_values(item) for item in value]
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    return value


def write_json(path, value):
    prior.write_json(path, json_values(value))


def physical_definition(raw):
    return {
        **raw,
        "execution": {key: value for key, value in raw["execution"].items() if key != "dt"},
    }


def load_job(bundle, job_id, role):
    bundle = Path(bundle).resolve()
    verify_bundle(bundle)
    protocol = read_json(bundle / "protocol.json")
    job = read_json(bundle / "plan.json")["jobs"][job_id]
    if job["role"] != role:
        raise ValueError("Wrong prepared bath role")
    raw = read_json(bundle / job["definition"])
    if (
        digest(raw) != job["definition_sha256"]
        or digest(physical_definition(raw)) != job["physics_sha256"]
    ):
        raise ValueError("Prepared physical recipe, controls or caps changed")
    return protocol, job, raw


def dependencies(bundle, job, path):
    import math

    paths = {} if path is None else read_json(path)
    if set(paths) != set(job["requires"]):
        raise ValueError(
            "Supply exactly the explicitly completed dependencies; nothing is launched"
        )
    manifest = sha(Path(bundle) / "manifest.json")
    plan = read_json(Path(bundle) / "plan.json")
    protocol = read_json(Path(bundle) / "protocol.json")
    records = {}
    for name, directory in paths.items():
        folder = Path(directory).resolve()
        supervisor = verify_result(folder)
        child = verify_result(folder / "data")
        guard = read_json(folder / "guard/result.json")
        inputs = read_json(folder / "inputs.json")
        expected = plan["jobs"][name]
        wanted = identity(
            bundle, protocol, expected, read_json(Path(bundle) / expected["definition"]), name
        )
        elapsed, samples = guard.get("elapsed_seconds"), guard.get("samples")
        if (
            type(elapsed) not in (int, float)
            or not math.isfinite(elapsed)
            or not 0 <= elapsed <= 480
            or type(samples) is not int
            or samples <= 0
            or supervisor["job_id"] != name
            or child["job_id"] != name
            or supervisor["bundle_manifest_sha256"] != manifest
            or child["bundle_manifest_sha256"] != manifest
            or sha(folder / "data/result.json") != supervisor["qualifier_result_sha256"]
            or guard["status"] != "completed"
            or guard["returncode"] != 0
            or supervisor["resource_result"] != guard
            or any(child.get(key) != value for key, value in wanted.items())
            or inputs["cpu_affinity"] != [inputs["cpu"]]
            or guard["limits"]["max_wall_seconds"] != 480
            or guard["limits"]["max_process_tree_rss_bytes"] != 2**30
            or guard["limits"]["min_available_host_memory_bytes"] != 8 * 2**30
            or guard["process_tree_memory_metric"] != "rss"
            or guard["sampled_peak_process_tree_rss_bytes"] > 2**30
            or guard["observed_process_high_water_bytes"] > 2**30
            or guard["minimum_available_host_memory_bytes"] < 8 * 2**30
            or (folder / "guard/failure.json").exists()
            or (folder / "guard/resource-stop.json").exists()
        ):
            raise ValueError("Dependency job/source/resource receipt disagrees: " + name)
        records[name] = dict(
            directory=str(folder),
            data=str(folder / "data"),
            result_sha256=sha(folder / "result.json"),
            child_result_sha256=sha(folder / "data/result.json"),
            record=child,
        )
    return records


def state_budget(context, target, protocol):
    import numpy as np

    result = prior.error_budget(context, target, protocol)
    result[..., -1] = protocol["tolerances"]["clock_atol_s"]
    if np.any(result <= 0) or not np.isfinite(result).all():
        raise ValueError("Invalid fixed state error budget")
    return result


def observer_budget(name, target, protocol):
    import numpy as np

    value = np.asarray(target)
    t = protocol["tolerances"]
    if name in ("times", "phase_clock_s", "init_phase_clock_s", "elapsed_time_s"):
        return np.full(value.shape, t["clock_atol_s"])
    absolute = t["trajectory_charge_atol"] if name.endswith("_C") else t["trajectory_state_atol"]
    if name.endswith("potential_V") or name in (
        "membrane_voltage_V",
        "junction_voltage_V",
        "er_voltage_V",
    ):
        absolute = t["field_potential_atol_V"]
    if name == "charge_residual_C":
        return np.full(value.shape, t["charge_atol_C"])
    if name == "component_current_residual_A":
        return np.full(value.shape, t["current_atol_A"])
    return absolute + t["trajectory_rtol"] * np.abs(value)


def check_proof(proof, protocol):
    import numpy as np

    result = prior.check_proof(proof, protocol)
    program = np.asarray(proof["program_energy_pJ"])
    if (
        not np.isfinite(program).all()
        or np.max(np.abs(program), initial=0) > protocol["tolerances"]["energy_atol_pJ"]
    ):
        raise ValueError("Independent prescribed bath work identity failed")
    result["program_energy_pJ"] = float(np.max(np.abs(program), initial=0))
    return result


def read_chunks(directory):
    import numpy as np

    directory = Path(directory)
    index = read_json(directory / "trajectory-index.json")
    previous, rows = None, []
    for entry in index["chunks"]:
        path = directory / entry["file"]
        if sha(path) != entry["sha256"]:
            raise ValueError("Trajectory chunk changed")
        with np.load(path, allow_pickle=False) as archive:
            item = {name: archive[name].copy() for name in archive.files}
        if rows and set(item) != set(rows[0]):
            raise ValueError("Trajectory chunk field inventory changed")
        if any(value.ndim == 0 or len(value) != len(item["times"]) for value in item.values()):
            raise ValueError("Trajectory chunk contains incomplete rows")
        if previous is not None:
            if item["times"][0] != previous["times"][-1]:
                raise ValueError("Missing or repeated trajectory chunk boundary")
            for name in item:
                if (
                    item[name].dtype != previous[name].dtype
                    or item[name].shape[1:] != previous[name].shape[1:]
                ):
                    raise ValueError("Trajectory chunk field type or shape changed: " + name)
                if not np.array_equal(item[name][0], previous[name][-1]):
                    raise ValueError("Trajectory chunk overlap disagrees: " + name)
        rows.append(
            {name: value if previous is None else value[1:] for name, value in item.items()}
        )
        previous = item
    if not rows:
        raise ValueError("No completed trajectory chunks")
    result = {name: np.concatenate([row[name] for row in rows]) for name in rows[0]}
    if len(result["times"]) != index["samples"]:
        raise ValueError("Incomplete full-grid chunk inventory")
    return result


def identity(bundle, protocol, job, raw, job_id):
    return dict(
        job_id=job_id,
        role=job["role"],
        family=job["family"],
        dataset=job["dataset"],
        phase=job["phase"],
        bundle_manifest_sha256=sha(Path(bundle) / "manifest.json"),
        protocol_sha256=digest(protocol),
        definition_sha256=digest(raw),
        physics_sha256=digest(physical_definition(raw)),
        duration_s=raw["experiment"]["end_time"],
    )
