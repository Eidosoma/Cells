"""Prepare an L4 cost profile from completed ionic/calcium cluster qualification.

The ordinary ensemble runner retains every scientific and checkpoint check.
This preparation authenticates its inputs and never launches a computation.
"""

import argparse
import copy
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from cells.assembly_cluster.spec import parse_spec
from cells.core.output_paths import within_output_root
from cells.ensemble.cli import read, sha, sources, write
from cells.ensemble.plan import plan

ARMS = {
    "dynamic": "baseline",
    "fixed-ring": "control-connected-ring",
    "fixed-open": "control-connected-open",
}
BATCHES = (32, 64)
WORLDS_PER_ARM = 128
CALCIUM_BATCHES = (8, 16, 32)
CALCIUM_WORLDS_PER_ARM = 64
PLASMA_BATCHES = (16, 32)
CACHE_ALLOWANCE = 256 * 1024**2


def need(value, message):
    if not value:
        raise ValueError(message)


def arm_definition(raw):
    """Remove scheduler-owned population fields and explicitly select the GPU."""
    result = copy.deepcopy(raw)
    result["ionic"]["execution"]["backend"] = "gpu"
    for binding in result["pools"]:
        for name in ("worlds", "world_id_start", "seed"):
            binding["pool"].pop(name)
    return result


def calcium_definition(parent, done, registration, protocol, *, family="calcium"):
    """Bind the frozen example exercised by the completed calcium assembly tests."""
    name, physical_model, evidence_family = {
        "calcium": (
            "configs/assembly_regulated_calcium_cluster.json",
            "spatial_calcium@1",
            "calcium",
        ),
        "plasma": (
            "configs/assembly_regulated_plasma_calcium_cluster.json",
            "spatial_calcium@2",
            "plasma",
        ),
        "gated": (
            "configs/assembly_regulated_gated_calcium_cluster.json",
            "spatial_calcium@3",
            "cav",
        ),
        "ip3": (
            "configs/assembly_regulated_ip3_calcium_cluster.json",
            "spatial_calcium@4",
            "ip3",
        ),
    }[family]
    raw = read(parent / "source" / name)
    spec = parse_spec(raw)
    selected = {"source/" + name: registration["sources_sha256"][name]}
    for evidence in ("assembly-baseline", "assembly-reference", "assembly-replay", "cpu-gpu"):
        name = f"{evidence_family}-evidence/gpu/{evidence}.json"
        need(name in done["files_sha256"], "Unbound calcium evidence")
        row = read(parent / name)
        need(row["status"] == "passed", "Require passed calcium assembly evidence")
        selected[name] = sha(parent / name)
        if evidence == "assembly-baseline":
            need(
                row["backend"] == "gpu"
                and row["physical_model"] == spec.ionic.to_dict()["model"]["id"] == physical_model
                and row["through_time_s"] == spec.pool.end_time_s == protocol["duration_s"]
                and row["tick"] == spec.ticks
                and row["worlds"] == spec.pool.worlds
                and row["world_id_start"] == spec.pool.world_id_start
                and spec.ionic.execution.dt == protocol["steps_s"][1],
                "Require the completed calcium GPU example at the qualified timestep",
            )
            for binding in spec.pools:
                cell = row["assembly_cells"][binding.cell_id]
                need(
                    cell["seed"] == binding.pool.seed and cell["stream_id"] == binding.stream_id,
                    "Qualified calcium random stream differs from the example",
                )
    seeds = {(b.pool.seed - b.stream_id) % 2**32 for b in spec.pools}
    need(len(seeds) == 1, "Qualified calcium owners use different ensemble seeds")
    return {"dynamic": arm_definition(spec.to_dict())}, seeds, selected


def qualified_definitions(parent, *, family="ionic"):
    need(
        family in ("ionic", "calcium", "plasma", "gated", "ip3"),
        "Unsupported cluster profile family",
    )
    calcium = family in ("calcium", "plasma", "gated", "ip3")
    result, done, registration = (
        read(parent / name) for name in ("result.json", "completion.json", "registration.json")
    )
    need(
        done["status"] == "completed"
        and result["status"]
        == (
            "ip3_calcium_assembly_cpu_gpu_qualification_pass"
            if family == "ip3"
            else "gated_calcium_assembly_cpu_gpu_qualification_pass"
            if family == "gated"
            else "plasma_calcium_assembly_cpu_gpu_qualification_pass"
            if family == "plasma"
            else "spatial_calcium_assembly_cpu_gpu_qualification_pass"
            if calcium
            else "assembly_cluster_cpu_gpu_qualification_pass"
        )
        and done["result_sha256"] == sha(parent / "result.json")
        and not (parent / "failure.json").exists(),
        "Require a completed assembly-cluster CPU/GPU qualification",
    )
    for name, expected in done["files_sha256"].items():
        need(sha(parent / name) == expected, "Qualified artifact changed: " + name)
    for name, expected in registration["sources_sha256"].items():
        need(sha(parent / "source" / name) == expected, "Qualified source changed: " + name)
    production = {
        k.removeprefix("src/cells/"): v
        for k, v in registration["sources_sha256"].items()
        if k.startswith("src/cells/") and k.endswith(".py")
    }
    need(sources() == production, "Production code differs from the qualified cluster")
    protocol_name = "chemistry" if calcium else "cluster"
    protocol = read(parent / f"{protocol_name}-protocol.json")
    need(
        protocol == registration[f"{protocol_name}_protocol"]
        and sha(parent / f"{protocol_name}-protocol.json")
        == result[f"{protocol_name}_protocol_sha256"],
        "Qualified protocol changed",
    )
    definitions, seeds, selected = {}, set(), {}
    if calcium:
        definitions, seeds, selected = calcium_definition(
            parent, done, registration, protocol, family=family
        )
    for name, evidence in () if calcium else ARMS.items():
        path = parent / "cluster-evidence/gpu" / (evidence + ".json")
        need(str(path.relative_to(parent)) in done["files_sha256"], "Unbound input definition")
        row = read(path)
        spec = parse_spec(row["definition"])
        need(
            row["backend"] == "gpu"
            and row["through_time_s"] == spec.pool.end_time_s == protocol["duration_s"]
            and spec.ionic.execution.dt == protocol["steps_s"][1],
            "Require the completed GPU definition at the middle qualified timestep",
        )
        # Baseline records its parsed fingerprint; control rows bind their
        # entire definition through the authenticated completion file hashes.
        if evidence == "baseline":
            need(row["definition_sha256"] == spec.fingerprint, "Baseline fingerprint changed")
        seeds.update((b.pool.seed - b.stream_id) % 2**32 for b in spec.pools)
        definitions[name] = arm_definition(spec.to_dict())
        selected[str(path.relative_to(parent))] = sha(path)
    need(len(seeds) == 1, "Qualified arms use different ensemble seeds")
    return (
        definitions,
        seeds.pop(),
        {
            "path": str(parent),
            "result_sha256": sha(parent / "result.json"),
            "completion_sha256": sha(parent / "completion.json"),
            "registration_sha256": sha(parent / "registration.json"),
            "verified_source_files": len(registration["sources_sha256"]),
            "verified_artifacts": len(done["files_sha256"]),
            "selected_inputs_sha256": selected,
            "production_sources_sha256": production,
            "qualified_peak_child_rss_bytes": result.get("peak_child_rss_bytes"),
        },
    )


def available_host_memory():
    return next(
        int(row.split()[1]) * 1024
        for row in Path("/proc/meminfo").read_text().splitlines()
        if row.startswith("MemAvailable:")
    )


def measured_memory_allowance(root, definition, production):
    """Use a completed observation of this workload, with explicit extra headroom."""
    result, done, registered = (
        read(root / name)
        for name in ("result.json", "completion.json", "profile-registration.json")
    )
    need(
        result["status"] == done["status"] == "completed"
        and result["all_checkpoint_fields_bitwise_equal_to_parent"] is True
        and not (root / "failure.json").exists()
        and done["result_sha256"] == sha(root / "result.json")
        and result["profile_registration_sha256"] == sha(root / "profile-registration.json"),
        "Require a completed, authenticated memory profile with exact replay",
    )
    need(registered["sources_sha256"] == production, "Memory profile production differs")
    for name, expected in registered["sources_sha256"].items():
        need(sha(root / "source/cells" / name) == expected, "Memory profile source changed")
    need(
        sha(root / "source/profile_cluster.py") == registered["driver_sha256"],
        "Memory profile observer changed",
    )
    for name, expected in result["evidence_sha256"].items():
        need(sha(root / name) == expected, "Memory profile evidence changed: " + name)
    campaign = read(root / "campaign/result.json")
    campaign_registration = read(root / "campaign/registration.json")
    need(
        sha(root / "campaign/result.json") == result["campaign_result_sha256"]
        and campaign["status"] == "completed"
        and campaign["registration_sha256"] == sha(root / "campaign/registration.json"),
        "Memory profile campaign changed or incomplete",
    )
    observed = copy.deepcopy(campaign_registration["definition"])
    need(
        observed["execution"]["workers_per_gpu"] == 1, "Require a single-worker memory measurement"
    )
    for key in ("workers_per_gpu", "worker_threads", "max_wall_seconds"):
        observed["execution"][key] = definition["execution"][key]
    need(observed == definition, "Memory measurement used a different workload")
    need(
        result["resource_samples"] >= 30
        and 0 < result["maximum_resource_sample_gap_seconds"] <= 3.0
        and len(result["worker_resources"]) == 1,
        "Memory measurement has insufficient coverage",
    )
    peak_worker = next(iter(result["worker_resources"].values()))["peak_rss_bytes"]
    peak_tree = result["sampled_peak_process_tree_rss_bytes"]
    need(
        all(type(x) is int and x > 0 for x in (peak_worker, peak_tree)),
        "Memory peaks must be positive byte counts",
    )
    # Include the sampled controller/compiler tree, not only worker RSS. This
    # remains a sizing estimate: concurrent compilation still needs monitoring.
    peak = max(peak_worker, peak_tree)
    gib = 1024**3
    allowance = ((5 * peak + 4 * gib - 1) // (4 * gib)) * gib
    return allowance, {
        "path": str(root),
        "result_sha256": sha(root / "result.json"),
        "completion_sha256": sha(root / "completion.json"),
        "profile_registration_sha256": sha(root / "profile-registration.json"),
        "observed_worker_peak_rss_bytes": peak_worker,
        "observed_process_tree_peak_rss_bytes": peak_tree,
        "allowance_per_worker_bytes": allowance,
        "policy": "ceil_GiB(1.25 * max(worker_lifetime_peak, sampled_process_tree_peak))",
        "scope": "Same task shapes, science and production; concurrency memory remains unmeasured",
    }


def prepare(parent, output, *, family="ionic", workers_per_gpu=2, memory_profile=None):
    need(within_output_root(output) and not output.exists(), "Require a fresh workspace output")
    need(
        type(workers_per_gpu) is int and workers_per_gpu in (1, 2), "Require one or two GPU workers"
    )
    physical, seed, origin = qualified_definitions(parent, family=family)
    calcium = family in ("calcium", "plasma", "gated", "ip3")
    batches = (
        PLASMA_BATCHES
        if family in ("plasma", "gated", "ip3")
        else CALCIUM_BATCHES
        if calcium
        else BATCHES
    )
    worlds = CALCIUM_WORLDS_PER_ARM if calcium else WORLDS_PER_ARM
    data = {
        "kind": "assembly_cluster_ensemble@1",
        "seed": seed,
        "arms": [
            {
                "id": f"{name}-batch-{width}",
                "definition": copy.deepcopy(raw),
                "worlds": worlds,
                "batch_worlds": width,
                "seconds_per_world": None,
            }
            for name, raw in physical.items()
            for width in batches
        ],
        "execution": {
            "max_wall_seconds": 3600 // workers_per_gpu,
            "max_output_bytes": 2 * 1024**3,
            "target_gpu_utilization_pct": 70,
            "worker_threads": 2 // workers_per_gpu,
            "workers_per_gpu": workers_per_gpu,
        },
    }
    planned = plan(data, 1)
    ids, shapes = [], {}
    for task in planned["tasks"]:
        spec = parse_spec(task["definition"])
        name = task["arm"].rsplit("-batch-", 1)[0]
        need(arm_definition(spec.to_dict()) == physical[name], "Task changed its physics")
        need(
            all(b.pool.seed == (seed + b.stream_id) % 2**32 for b in spec.pools),
            "Task changed a cell's random stream",
        )
        ids.extend(range(spec.pool.world_id_start, spec.pool.world_id_start + spec.pool.worlds))
        shapes[task["arm"]] = {
            "batch_worlds": spec.pool.worlds,
            "window_ticks": spec.window_ticks,
            "dt_s": spec.ionic.execution.dt,
            "horizon_s": spec.pool.end_time_s,
            "working_bytes": spec.working_bytes,
            "output_bytes_bound_per_task": spec.output_bound,
        }
    need(sorted(ids) == list(range(planned["worlds"])), "World ownership has a gap or overlap")
    free = shutil.disk_usage(output.parent).free
    need(
        free >= planned["output_bytes_bound"] + CACHE_ALLOWANCE + 4 * 1024**3,
        "Cluster profile and cache would consume the 4-GiB disk reserve",
    )
    available = available_host_memory()
    worker_rss_allowance = (
        16 if family == "ip3" else 10 if family == "gated" else 8 if family == "plasma" else 2
    ) * 1024**3
    memory_basis = None
    if memory_profile is not None:
        worker_rss_allowance, memory_basis = measured_memory_allowance(
            memory_profile, data, origin["production_sources_sha256"]
        )
    required_memory = planned["worker_processes"] * worker_rss_allowance + 4 * 1024**3
    need(
        available >= required_memory,
        "Require the per-worker host allowance plus a 4-GiB memory reserve",
    )
    output.mkdir()
    write(output / "definition.json", data)
    write(output / "plan.json", planned)
    shutil.copyfile(__file__, output / "cluster_matrix.py")
    receipt = {
        "status": "prepared",
        "family": family,
        "created_utc": datetime.now(UTC).isoformat(),
        "qualified_parent": origin,
        "definition_sha256": sha(output / "definition.json"),
        "plan_sha256": sha(output / "plan.json"),
        "generator_sha256": sha(output / "cluster_matrix.py"),
        "worlds": planned["worlds"],
        "tasks": len(planned["tasks"]),
        "worker_processes": planned["worker_processes"],
        "worker_threads": data["execution"]["worker_threads"],
        "max_wall_seconds": data["execution"]["max_wall_seconds"],
        "arm_shapes": shapes,
        "physical_parameters_and_numerical_checks_unchanged": True,
        "output_bytes_bound": planned["output_bytes_bound"],
        "cache_allowance_bytes": CACHE_ALLOWANCE,
        "free_disk_bytes": free,
        "available_memory_bytes": available,
        "host_memory_allowance_per_worker_bytes": worker_rss_allowance,
        "required_available_memory_bytes": required_memory,
        "host_memory_allowance_scope": "Conservative prelaunch sizing, not an enforced RSS cap",
        "measured_memory_basis": memory_basis,
        "cpu_affinity": [4, 5],
        "allocated_gpus": 1,
        "max_gpu_memory_fraction_per_worker": 0.2,
        "automatic_launch": False,
        "automatic_followup": False,
        "sample_scope": (
            "Dynamic arms use distinct registered stochastic worlds. Batch sizes use "
            "different world IDs, so costs are separate timing samples, not a paired "
            "speedup or new biological evidence."
            + ("" if calcium else " Fixed-ring/open arms are deterministic replicas.")
        ),
        "purpose": (
            "Measure sustained L4 utilization, batch costs, host/checkpoint overhead and arm "
            f"timing with {workers_per_gpu} persistent worker(s) on two CPU cores; "
            "no GH200 or multi-GPU efficiency claim."
        ),
    }
    write(output / "preparation.json", receipt)
    return {
        k: receipt[k] for k in ("status", "worlds", "tasks", "arm_shapes", "output_bytes_bound")
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--family", choices=("ionic", "calcium", "plasma", "gated", "ip3"), default="ionic"
    )
    parser.add_argument("--workers-per-gpu", type=int, choices=(1, 2), default=2)
    parser.add_argument("--memory-profile", type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            prepare(
                args.parent.resolve(),
                args.output.resolve(),
                family=args.family,
                workers_per_gpu=args.workers_per_gpu,
                memory_profile=args.memory_profile.resolve() if args.memory_profile else None,
            ),
            indent=2,
        )
    )
