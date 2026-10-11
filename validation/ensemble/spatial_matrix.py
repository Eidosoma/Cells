"""Prepare a bounded L4 cost profile from the qualified spatial CPU/GPU panel.

Uses the ordinary ensemble runner, guarded ionic windows and complete snapshots.
Deterministic replicas measure throughput; they are not additional biological
samples. Preparation never launches a job or changes a physical definition.
"""

import argparse
import copy
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from cells.core.batch_windows import plan_batch_windows
from cells.core.output_paths import within_output_root
from cells.core.runner import timeline
from cells.core.specs import parse_spec
from cells.core.windows import WindowPolicy
from cells.ensemble.cli import write
from cells.ensemble.ionic import parse_spec as parse_worlds
from cells.ensemble.plan import plan

ROOT = Path(__file__).resolve().parents[2]
ARMS = ("baseline", "pump_release")
BATCHES = (16, 64)
WORLDS_PER_ARM = 128


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(path.read_text())


def need(value, message):
    if not value:
        raise ValueError(message)


def qualified_definitions(parent):
    """Bind the exact finest-step GPU definitions and unchanged production code."""
    parent = parent.resolve()
    result, complete = read(parent / "result.json"), read(parent / "completion.json")
    need(
        complete["result_sha256"] == sha(parent / "result.json")
        and complete["status"] == result["status"] == "spatial_kinetic_cluster_cpu_gpu_panel_pass"
        and complete["registration_sha256"]
        == result["registration_sha256"]
        == sha(parent / "registration.json"),
        "Require an authenticated completed spatial qualification",
    )
    registration = read(parent / "registration.json")
    protocol = read(parent / "protocol.json")
    need(
        sha(parent / "protocol.json") == registration["inputs_sha256"]["protocol.json"],
        "Qualified protocol changed",
    )
    expected = {k: v for k, v in registration["sources_sha256"].items() if k.startswith("src/")}
    current = {str(p.relative_to(ROOT)): sha(p) for p in sorted((ROOT / "src").rglob("*.py"))}
    need(current == expected, "Production code differs from the qualified spatial panel")
    need(
        sha(parent / "gpu/completion.json") == result["phase_completions_sha256"]["gpu"],
        "Qualified GPU receipt changed",
    )
    gpu = read(parent / "gpu/completion.json")
    need(gpu["status"] == "completed", "Qualified GPU phase is incomplete")
    level = len(protocol["steps_s"]) - 1
    definitions, inputs = {}, {}
    for arm in ARMS:
        for filename in ("resolved_config.json", "checkpoint_final/state.npz"):
            name = f"{arm}/{level}/run/{filename}"
            path = parent / "gpu" / name
            need(sha(path) == gpu["files_sha256"][name], "Qualified GPU input changed: " + name)
            inputs[str(path)] = sha(path)
        raw = read(parent / f"gpu/{arm}/{level}/run/resolved_config.json")
        need(
            raw["model"]["id"] == "spatial_extracellular@2"
            and raw["execution"]["backend"] == "gpu"
            and raw["execution"]["precision"] == "float64"
            and raw["execution"]["dt"] == protocol["steps_s"][-1]
            and raw["experiment"]["end_time"] == protocol["duration_s"],
            "Require the qualified finest-step spatial GPU configuration",
        )
        definitions[arm] = raw
    return definitions, dict(
        path=str(parent),
        result_sha256=sha(parent / "result.json"),
        registration_sha256=sha(parent / "registration.json"),
        gpu_completion_sha256=sha(parent / "gpu/completion.json"),
        selected_inputs_sha256=inputs,
        production_sources_sha256=current,
    )


def definition(qualified):
    arms = []
    for name in ARMS:
        raw = qualified[name]
        steps = len(timeline(parse_spec(raw))) - 1
        need(steps > 0 and steps % 200 == 0, "Require complete 200-step windows without a tail")
        for width in BATCHES:
            arms.append(
                dict(
                    id=f"{name}-batch-{width}",
                    definition=dict(
                        model="ionic_worlds@1",
                        simulation=copy.deepcopy(raw),
                        window_steps=200,
                        max_working_bytes=2 * 1024**3,
                        max_output_bytes=256 * 1024**2,
                        max_wall_seconds=600,
                    ),
                    worlds=WORLDS_PER_ARM,
                    batch_worlds=width,
                    seconds_per_world=None,
                )
            )
    return dict(
        kind="ionic_ensemble@1",
        seed=20260925,
        arms=arms,
        execution=dict(
            max_wall_seconds=1800,
            max_output_bytes=2 * 1024**3,
            target_gpu_utilization_pct=70,
            worker_threads=1,
            workers_per_gpu=2,
        ),
    )


def prepare(parent, output):
    need(within_output_root(output) and not output.exists(), "Require a fresh workspace output")
    physical, origin = qualified_definitions(parent)
    data = definition(physical)
    planned = plan(data, 1)
    ids, shapes = [], {}
    for task in planned["tasks"]:
        spec = parse_worlds(task["definition"])
        ids.extend(range(spec.world_id_start, spec.world_id_start + spec.worlds))
        if task["arm"] not in shapes:
            windows = plan_batch_windows(
                spec.batch(), WindowPolicy(spec.window_steps, "checkpoints")
            )
            shapes[task["arm"]] = dict(
                batch_worlds=spec.worlds,
                window_steps=spec.window_steps,
                dt_s=spec.simulation.execution.dt,
                horizon_s=spec.end_time_s,
                estimated_working_bytes=windows.estimated_working_bytes,
            )
        source = task["arm"].rsplit("-batch-", 1)[0]
        need(spec.simulation.to_dict() == physical[source], "Task changed its physical definition")
    need(sorted(ids) == list(range(planned["worlds"])), "Profile world ownership has a gap/overlap")
    need(
        shutil.disk_usage(output.parent).free >= planned["output_bytes_bound"] + 4 * 1024**3,
        "Spatial profile would consume the 4-GiB disk reserve",
    )
    available = next(
        int(row.split()[1]) * 1024
        for row in Path("/proc/meminfo").read_text().splitlines()
        if row.startswith("MemAvailable:")
    )
    need(available >= 8 * 1024**3, "Require two 2-GiB workers plus a 4-GiB memory reserve")
    output.mkdir(parents=True)
    write(output / "definition.json", data)
    write(output / "plan.json", planned)
    shutil.copyfile(__file__, output / "spatial_matrix.py")
    receipt = dict(
        status="prepared",
        created_utc=datetime.now(UTC).isoformat(),
        qualified_parent=origin,
        definition_sha256=sha(output / "definition.json"),
        plan_sha256=sha(output / "plan.json"),
        generator_sha256=sha(output / "spatial_matrix.py"),
        worlds=planned["worlds"],
        tasks=len(planned["tasks"]),
        arm_shapes=shapes,
        deterministic_replicas=True,
        scientific_definitions_unchanged=True,
        output_bytes_bound=planned["output_bytes_bound"],
        available_memory_bytes=available,
        cpu_affinity=[4, 5],
        allocated_gpus=1,
        max_gpu_memory_fraction_per_worker=0.2,
        automatic_launch=False,
        automatic_followup=False,
        purpose=(
            "Measure batch-size costs, host overhead, arm timing and whole-job L4 utilization "
            "using unchanged qualified spatial definitions; no multi-GPU efficiency claim."
        ),
    )
    write(output / "preparation.json", receipt)
    return {
        k: receipt[k] for k in ("status", "worlds", "tasks", "arm_shapes", "output_bytes_bound")
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.parent.resolve(), args.output.resolve()), indent=2))


if __name__ == "__main__":
    main()
