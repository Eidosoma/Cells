"""Freeze scientific counts; schedule batches using declared runtime estimates."""

import copy
import heapq
import math
import re

from cells.ensemble.families import MODELS, bind_definition, model_id, output_bound, population
from cells.ensemble.families import parse_definition as parse_spec


def positive(value, name, *, integer=False):
    if (
        type(value) not in ((int,) if integer else (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ValueError(f"{name} must be positive and finite")
    return value


def plan(data, slots):
    if set(data) != {"kind", "seed", "arms", "execution"} or data["kind"] not in MODELS:
        raise ValueError("Require a named ensemble with seed, arms and execution")
    positive(slots, "GPU slots", integer=True)
    if type(data["seed"]) is not int or not 0 <= data["seed"] < 2**32:
        raise ValueError("Seed must be uint32")
    execution = data["execution"]
    fields = {
        "max_wall_seconds",
        "max_output_bytes",
        "target_gpu_utilization_pct",
        "worker_threads",
    }
    if set(execution) - {"workers_per_gpu"} != fields:
        raise ValueError(f"Ensemble execution fields must be {sorted(fields)}")
    for field in fields:
        positive(execution[field], field, integer=field in ("max_output_bytes", "worker_threads"))
    workers = execution.get("workers_per_gpu", 1)
    if type(workers) is not int or workers not in (1, 2):
        raise ValueError("workers_per_gpu must be 1 or 2")
    parallel_slots = slots * workers
    if not 120 <= execution["max_wall_seconds"] <= 43200:
        raise ValueError("Ensemble wall limit must be between 120 and 43200 seconds")
    if execution["target_gpu_utilization_pct"] > 100:
        raise ValueError("GPU utilization target must be positive and at most 100 percent")
    if execution["max_output_bytes"] > 8 * 1024**3 or execution["worker_threads"] > 72:
        raise ValueError("Ensemble exceeds the 8 GiB artifact or 72 threads/worker bound")
    arms = data["arms"]
    if not isinstance(arms, list) or not 1 <= len(arms) <= 256:
        raise ValueError("Require 1 to 256 registered arms")
    ionic = data["kind"] == "ionic_ensemble@1"
    if ionic:
        from cells.ensemble.ionic import validate_population

    # A fully admitted ionic arm is physically identical for each assigned
    # world-ID range. Cache only within this call, by arm and exact batch size;
    # a smaller tail still receives full admission and its own resource bound.
    # Workers continue to parse and validate each serialized task independently.
    admitted = {}
    names, queue, offset, definitions, cost_known = set(), [], 0, {}, True
    for arm in arms:
        if set(arm) != {"id", "definition", "worlds", "batch_worlds", "seconds_per_world"}:
            raise ValueError("Invalid arm fields")
        name = arm["id"]
        if (
            not isinstance(name, str)
            or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", name)
            or name in names
        ):
            raise ValueError("Arm IDs must be unique simple names")
        names.add(name)
        count = positive(arm["worlds"], "arm worlds", integer=True)
        width = positive(arm["batch_worlds"], "batch worlds", integer=True)
        if width > count or offset + count > 2**32:
            raise ValueError("Invalid batch size or exhausted world-ID namespace")
        if ionic:
            validate_population(width, offset, data["seed"])
            if offset + count >= 2**31:
                raise ValueError("Ionic positive world-ID namespace exhausted")
        cost = arm["seconds_per_world"]
        cost_known &= cost is not None
        cost = 1.0 if cost is None else positive(cost, "seconds_per_world")
        definition = bind_definition(
            arm["definition"],
            seed=data["seed"],
            worlds=width,
            world_id_start=offset,
            reject_owned=True,
        )
        spec = parse_spec(definition)
        if model_id(spec) != MODELS[data["kind"]]:
            raise ValueError("Ensemble kind and arm model disagree")
        if population(spec).recording != "summary":
            raise ValueError(
                "Ensembles require bounded summary recording; full checkpoints are retained"
            )
        definitions[name] = spec.to_dict()
        if ionic:
            admitted[name, width] = (definitions[name], output_bound(spec))
        heapq.heappush(queue, (-count * cost, name, offset, count, width, cost))
        offset += count
    tasks, projected_load = [], [0.0] * parallel_slots
    total_output_bound = 32 * 1024**2
    while queue:
        _, name, start, remaining, width, cost = heapq.heappop(queue)
        n = min(remaining, width)
        if ionic:
            validate_population(n, start, data["seed"])
            if (name, n) not in admitted:
                spec = parse_spec(
                    bind_definition(
                        definitions[name], worlds=n, world_id_start=start, seed=data["seed"]
                    )
                )
                admitted[name, n] = (spec.to_dict(), output_bound(spec))
            template, bound = admitted[name, n]
            definition = bind_definition(
                template, worlds=n, world_id_start=start, seed=data["seed"]
            )
        else:
            spec = parse_spec(
                bind_definition(
                    definitions[name], worlds=n, world_id_start=start, seed=data["seed"]
                )
            )
            definition, bound = spec.to_dict(), output_bound(spec)
        estimate = n * cost
        tasks.append(
            {
                "id": f"task-{len(tasks):05d}",
                "arm": name,
                "definition": definition,
                "estimated_seconds": estimate if cost_known else None,
            }
        )
        # Retain a full success checkpoint and room for an interrupted continuation.
        total_output_bound += 2 * bound
        projected_load[min(range(parallel_slots), key=projected_load.__getitem__)] += estimate
        if remaining > n:
            heapq.heappush(
                queue, (-(remaining - n) * cost, name, start + n, remaining - n, width, cost)
            )
        if len(tasks) > 10000:
            raise ValueError("More than 10000 tasks; increase batch sizes")
    if len(tasks) < parallel_slots:
        raise ValueError(
            "Every allocated GPU needs work; split the registered worlds into more batches"
        )
    if total_output_bound > execution["max_output_bytes"]:
        raise ValueError(
            f"Conservative checkpoint/output bound ({total_output_bound} bytes) exceeds "
            f"ensemble max_output_bytes ({execution['max_output_bytes']} bytes)"
        )
    return {
        "tasks": tasks,
        "worlds": offset,
        "allocated_gpus": slots,
        "worker_processes": parallel_slots,
        "output_bytes_bound": total_output_bound,
        "runtime_estimates_supplied": cost_known,
        "projected_worker_seconds": projected_load if cost_known else None,
        "projected_tail_fraction": (max(projected_load) - min(projected_load)) / max(projected_load)
        if cost_known
        else None,
        "scheduling": "largest_remaining_arm_work_then_shared_dynamic_queue",
        "counts_changed_by_scheduling": False,
    }


def balance(data, costs, target_seconds):
    """Runtime estimates change batch boundaries, never seeds or scientific counts."""
    positive(target_seconds, "target task seconds")
    result = copy.deepcopy(data)
    for arm in result["arms"]:
        cost = positive(costs[arm["id"]], "measured seconds per world")
        proposed = max(1, int(target_seconds / cost))
        power = 1 << (proposed.bit_length() - 1)
        arm["batch_worlds"] = min(arm["worlds"], arm["batch_worlds"], power)
        arm["seconds_per_world"] = cost
    return result


def jupiter_plan(data, nodes):
    """Offline 1–4-node layout; task identity is independent of rank and placement.

    This describes independent worlds. It neither starts remote workers nor
    supplies the halo exchange needed by one tissue spanning multiple GPUs.
    """
    if type(nodes) is not int or not 1 <= nodes <= 4:
        raise ValueError("JUPITER planning supports 1 to 4 nodes, up to 16 GH200 GPUs")
    result = plan(data, 4 * nodes)
    workers = data["execution"].get("workers_per_gpu", 1)
    ranks = [
        {
            "rank": rank,
            "node": rank // 4,
            "local_gpu": rank % 4,
            "cpu_cores_available": 72,
            "tasks": [],
        }
        for rank in range(4 * nodes)
    ]
    slots = [(0.0, rank, worker) for rank in range(4 * nodes) for worker in range(workers)]
    heapq.heapify(slots)
    for task in result["tasks"]:
        elapsed, rank, worker = heapq.heappop(slots)
        ranks[rank]["tasks"].append(task["id"])
        cost = task["estimated_seconds"] if result["runtime_estimates_supplied"] else 1.0
        heapq.heappush(slots, (elapsed + cost, rank, worker))
    loads = [0.0] * len(ranks)
    for elapsed, rank, _ in slots:
        loads[rank] = max(loads[rank], elapsed)
    known = result["runtime_estimates_supplied"]
    wall = max(loads)
    result["deployment"] = {
        "target": "jupiter_gh200",
        "status": "offline_plan_only",
        "nodes": nodes,
        "gpus_per_node": 4,
        "gpu_memory_GB_per_device": 96,
        "maximum_target_gpus": 16,
        "ranks": ranks,
        "projected_gpu_seconds": loads if known else None,
        "projected_node_seconds": [max(loads[i : i + 4]) for i in range(0, len(loads), 4)]
        if known
        else None,
        "projected_wall_seconds": wall if known else None,
        "projected_allocated_node_hours": nodes * wall / 3600 if known else None,
        "projected_allocated_gpu_hours": 4 * nodes * wall / 3600 if known else None,
        "projected_tail_fraction": (wall - min(loads)) / wall if known else None,
        "allocation_includes_idle_gpus_and_tail": True,
        "placement_changes_world_identity": False,
        "remote_execution_qualified": False,
        "interacting_tissue_partitioning": False,
    }
    return result
