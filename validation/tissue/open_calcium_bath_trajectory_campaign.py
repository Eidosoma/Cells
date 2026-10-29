"""Run an explicitly selected frozen bath trajectory plan on one or two CPUs.

Preparation only validates and freezes the controller; it launches no roles::

    python -B -m validation.tissue.open_calcium_bath_trajectory_campaign \
        prepare --inputs /mnt/workspaces/Cells/campaign-inputs.json --output NEW_DIRECTORY
    python -B -m validation.tissue.open_calcium_bath_trajectory_campaign \
        launch --output NEW_DIRECTORY

Inputs name a bundle {path, manifest_sha256}, pending_jobs, cpus, and optional
retained {job_id: {path, result_sha256}}. All dependencies must be explicitly
selected or retained. Launch detaches and returns immediately. A failed role
stops new launches; active roles finish. No retry, dependency expansion, polling
command or subsequent campaign is provided. Individual workers retain the
existing 480-second / 1-GiB RSS / 8-GiB host reserve supervisor.
"""

import argparse
import math
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path

if __name__ == "__main__" and Path(__file__).name == "driver.py":
    import campaign_artifacts as artifact
else:
    from validation.tissue import open_calcium_trajectory_common as artifact

KIND = "cells.open_calcium_bath_trajectory_campaign@1"
LAUNCH_RESERVE = 12 * 2**30
POLICY = dict(automatic_retry=False, automatic_followup=False, automatic_polling=False)
RESOURCES = dict(
    max_role_wall_seconds=480,
    max_child_tree_rss_bytes=2**30,
    min_available_host_bytes=8 * 2**30,
    threads=1,
    memory_metric="rss",
    gpu=False,
    persistent_compilation_cache=False,
)
LIMITS = dict(
    max_wall_seconds=480,
    max_process_tree_memory_bytes=2**30,
    max_process_tree_rss_bytes=2**30,
    max_individual_process_rss_bytes=2**30,
    min_available_host_memory_bytes=8 * 2**30,
    process_tree_memory_metric="rss",
)


def utc():
    return datetime.now(timezone.utc).isoformat()


def receipt(path):
    return dict(path=str(path), sha256=artifact.sha(path))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def available_memory():
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    raise RuntimeError("Host available memory could not be measured")


def disjoint_output(output, paths):
    for path in paths:
        path = Path(path).resolve()
        require(
            not (output.is_relative_to(path) or path.is_relative_to(output)),
            "Campaign output overlaps frozen source or retained evidence: " + str(path),
        )


def validate_inputs(inputs, output):
    """Check the frozen graph and retained receipts without importing model code."""
    require(inputs["kind"] == KIND, "Unknown campaign input kind")
    bundle = Path(inputs["bundle"]["path"]).resolve()
    manifest_sha = inputs["bundle"]["manifest_sha256"]
    require(artifact.sha(bundle / "manifest.json") == manifest_sha, "Bundle manifest changed")
    manifest = artifact.verify_bundle(bundle)
    protocol = artifact.read_json(bundle / "protocol.json")
    require(
        all(protocol["resources"].get(k) == v for k, v in RESOURCES.items()),
        "Frozen role resource policy changed",
    )
    require(protocol["duration_s"] == 8e-6, "Full original 8-us horizon required")
    require((bundle / "runner.py").is_file(), "Frozen role runner is missing")
    jobs = artifact.read_json(bundle / "plan.json")["jobs"]
    require(len(jobs) == protocol["planned_roles"], "Frozen plan role count disagrees")
    cpus = inputs["cpus"]
    require(
        isinstance(cpus, list)
        and 1 <= len(cpus) <= 2
        and all(type(cpu) is int for cpu in cpus)
        and len(set(cpus)) == len(cpus)
        and set(cpus) <= os.sched_getaffinity(0),
        "Select one or two distinct available CPUs",
    )
    pending, retained = inputs["pending_jobs"], inputs.get("retained", {})
    require(
        isinstance(pending, list) and pending and len(pending) == len(set(pending)),
        "Select a nonempty list of distinct pending jobs",
    )
    require(set(pending).isdisjoint(retained), "Pending and retained jobs overlap")
    selected = set(pending) | set(retained)
    require(selected <= jobs.keys(), "Unknown selected or retained job")
    for name in selected:
        require(re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", name), "Unsafe role ID")
        job = jobs[name]
        require(job["role"] in ("oracle", "production", "projection", "compare"), "Unknown role")
        dependencies = job["requires"]
        require(
            isinstance(dependencies, list)
            and len(dependencies) == len(set(dependencies))
            and set(dependencies) <= selected,
            "Duplicate or unselected dependencies: " + name,
        )
        if name in retained:
            require(
                set(dependencies) <= retained.keys(), "Retained role has unretained dependencies"
            )
        definition = (bundle / job["definition"]).resolve()
        require(definition.is_relative_to(bundle), "Definition is outside the frozen bundle")
        raw = artifact.read_json(definition)
        physics = {
            **raw,
            "execution": {key: value for key, value in raw["execution"].items() if key != "dt"},
        }
        require(
            artifact.digest(raw) == job["definition_sha256"]
            and artifact.digest(physics) == job["physics_sha256"]
            and raw["experiment"]["end_time"] == protocol["duration_s"],
            "Job definition, physical recipe or duration changed: " + name,
        )
    # Check the entire selected graph, including retained roles, before any launch.
    remaining, resolved = set(selected), set()
    while remaining:
        ready = {name for name in remaining if set(jobs[name]["requires"]) <= resolved}
        require(ready, "Selected dependency graph contains a cycle")
        resolved.update(ready)
        remaining.difference_update(ready)
    completed = {name: Path(value["path"]).resolve() for name, value in retained.items()}
    disjoint_output(output, [bundle, manifest["accepted_source"], *completed.values()])
    context = dict(inputs=inputs, bundle=bundle, jobs=jobs, protocol=protocol, completed=completed)
    for name, path in completed.items():
        verify_role(context, name, path, completed, retained[name]["result_sha256"])
    return context


def verify_role(context, name, path, completed, expected_sha=None):
    """Authenticate child, supervisor, physical identity, dependencies and limits."""
    if expected_sha is not None:
        require(artifact.sha(path / "result.json") == expected_sha, "Retained result changed")
    outer = artifact.verify_result(path)
    child = artifact.verify_result(path / "data")
    job, protocol = context["jobs"][name], context["protocol"]
    required = {"inputs.json", "guard/result.json", "guard/process-inputs.json", "data/result.json"}
    require(required <= outer["artifacts"].keys(), "Supervisor omits required receipt hashes")
    manifest_sha = context["inputs"]["bundle"]["manifest_sha256"]
    for record in (outer, child):
        require(
            record["job_id"] == name
            and record["bundle_manifest_sha256"] == manifest_sha
            and all(record[key] == job[key] for key in ("role", "family", "dataset", "phase")),
            "Role result belongs to a different job or source: " + name,
        )
    require(
        child["definition_sha256"] == job["definition_sha256"]
        and child["physics_sha256"] == job["physics_sha256"]
        and child["duration_s"] == protocol["duration_s"]
        and child["protocol_sha256"] == artifact.digest(protocol)
        and outer["qualifier_result_sha256"] == artifact.sha(path / "data/result.json")
        and outer["source_and_input_hashes_unchanged"] is True,
        "Child definition, duration, protocol or source evidence disagrees: " + name,
    )
    inputs = artifact.read_json(path / "inputs.json")
    require(
        inputs["job_id"] == name
        and inputs["job"] == job
        and inputs["bundle_manifest_sha256"] == manifest_sha
        and inputs["resources"] == protocol["resources"]
        and inputs["cpu_affinity"] == [inputs["cpu"]],
        "Role execution inputs disagree: " + name,
    )
    dependencies = {key: str(completed[key]) for key in job["requires"]}
    require(
        (inputs["dependency_runs"] or {}) == dependencies,
        "Role used different dependency evidence: " + name,
    )
    if dependencies:
        require("dependency-runs.json" in outer["artifacts"], "Dependency paths are unsealed")
        require(
            artifact.read_json(path / "dependency-runs.json") == dependencies,
            "Saved dependency paths disagree",
        )
    resource = artifact.read_json(path / "guard/result.json")
    limits = artifact.read_json(path / "guard/process-inputs.json")["limits"]
    require(
        not (path / "guard/failure.json").exists()
        and resource == outer["resource_result"]
        and resource["status"] == "completed"
        and resource["returncode"] == 0
        and resource["process_tree_memory_metric"] == "rss"
        and resource["samples"] >= 1
        and all(resource["limits"].get(k) == limits.get(k) == v for k, v in LIMITS.items()),
        "Supervisor resource receipt or limits disagree: " + name,
    )
    for key, lower, upper in (
        ("elapsed_seconds", 0, 480),
        ("sampled_peak_process_tree_rss_bytes", 0, 2**30),
        ("observed_process_high_water_bytes", 0, 2**30),
        ("minimum_available_host_memory_bytes", 8 * 2**30, float("inf")),
    ):
        value = resource[key]
        require(math.isfinite(value) and lower <= value <= upper, "Resource bound failed: " + key)
    return receipt(path / "result.json")


def prepare(input_path, output):
    inputs = artifact.read_json(input_path)
    context = validate_inputs(inputs, output)
    require(not output.exists(), "Campaign output already exists")
    output.mkdir(parents=True, exist_ok=False)
    inputs["bundle"]["path"] = str(context["bundle"])
    for name, path in context["completed"].items():
        inputs["retained"][name]["path"] = str(path)
    artifact.write_json(output / "inputs.json", inputs)
    shutil.copyfile(Path(__file__), output / "driver.py")
    shutil.copyfile(Path(artifact.__file__), output / "campaign_artifacts.py")
    artifact.write_json(
        output / "seal.json",
        dict(
            files={
                name: artifact.sha(output / name)
                for name in ("inputs.json", "driver.py", "campaign_artifacts.py")
            },
            executable=str(Path(sys.executable).absolute()),
            created_utc=utc(),
            original_inputs=receipt(Path(input_path)),
        ),
    )
    artifact.write_json(output / "status.json", dict(status="prepared", utc=utc(), **POLICY))
    return output


def checked(output):
    seal = artifact.read_json(output / "seal.json")
    require(
        set(seal["files"]) == {"inputs.json", "driver.py", "campaign_artifacts.py"},
        "Controller seal inventory changed",
    )
    for name, checksum in seal["files"].items():
        require(artifact.sha(output / name) == checksum, "Frozen controller changed: " + name)
    return validate_inputs(artifact.read_json(output / "inputs.json"), output)


def launch(output):
    checked(output)
    memory = available_memory()
    require(memory >= LAUNCH_RESERVE, "12-GiB launch reserve unavailable; no job launched")
    # Atomic claim prevents two launchers from running or overwriting the same campaign.
    (output / "launched").mkdir(exist_ok=False)
    try:
        seal = artifact.read_json(output / "seal.json")
        command = [
            seal["executable"],
            "-B",
            str(output / "driver.py"),
            "_execute",
            "--output",
            str(output),
        ]
        artifact.write_json(
            output / "launch-inputs.json",
            dict(
                command=command,
                available_host_bytes=memory,
                seal=receipt(output / "seal.json"),
                utc=utc(),
                **POLICY,
            ),
        )
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        environment.pop("PYTHONPATH", None)
        environment.pop("PYTHONHOME", None)
        with (output / "controller.log").open("x") as log:
            child = subprocess.Popen(
                command,
                cwd=output,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )
        record = dict(pid=child.pid, process_group=child.pid, utc=utc(), **POLICY)
        artifact.write_json(output / "launch.json", record)
        return record
    except BaseException as error:
        artifact.failure(output, error, context=dict(stage="detached_launch", **POLICY))
        raise


def run_role(context, output, name, cpu, completed, receipts):
    # Recheck evidence immediately before it is consumed, including retained parents.
    for parent in context["jobs"][name]["requires"]:
        verify_role(context, parent, completed[parent], completed, receipts[parent]["sha256"])
    destination = output / "roles" / name
    command = [
        sys.executable,
        "-B",
        str(context["bundle"] / "runner.py"),
        "--bundle",
        str(context["bundle"]),
        "--execute",
        "--job",
        name,
        "--cpu",
        str(cpu),
        "--output",
        str(destination),
    ]
    dependencies = context["jobs"][name]["requires"]
    if dependencies:
        dependency_file = output / "dependencies" / (name + ".json")
        artifact.write_json(dependency_file, {key: str(completed[key]) for key in dependencies})
        command += ["--dependency-runs", str(dependency_file)]
    environment = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
    )
    with (output / "logs" / (name + ".log")).open("x") as log:
        subprocess.run(
            command,
            cwd=context["bundle"] / "source",
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
        )
    verify_role(context, name, destination, completed)
    return destination


def execute(output):
    require((output / "launched").is_dir(), "Use explicit detached launch first")
    (output / "started").mkdir(exist_ok=False)
    began = time.monotonic()
    try:
        context = checked(output)
        launch_input = artifact.read_json(output / "launch-inputs.json")
        require(launch_input["seal"] == receipt(output / "seal.json"), "Launch seal changed")
        for name in ("roles", "logs", "dependencies"):
            (output / name).mkdir(exist_ok=False)
        inputs, completed = context["inputs"], dict(context["completed"])
        receipts = {name: receipt(path / "result.json") for name, path in completed.items()}
        pending, failures, active = list(inputs["pending_jobs"]), [], {}
        free = set(inputs["cpus"])

        def status():
            artifact.write_json(
                output / "status.json",
                dict(
                    status="stopping_after_failure" if failures else "running",
                    utc=utc(),
                    elapsed_seconds=time.monotonic() - began,
                    completed=receipts,
                    active=list(active.values()),
                    pending=list(pending),
                    failures=failures,
                    **POLICY,
                ),
            )

        status()
        with ThreadPoolExecutor(max_workers=len(free)) as pool:
            while pending or active:
                while free and pending and not failures:
                    ready = next(
                        (
                            name
                            for name in pending
                            if set(context["jobs"][name]["requires"]) <= completed.keys()
                        ),
                        None,
                    )
                    if ready is None:
                        break
                    cpu = min(free)
                    free.remove(cpu)
                    pending.remove(ready)
                    future = pool.submit(
                        run_role, context, output, ready, cpu, dict(completed), dict(receipts)
                    )
                    active[future] = dict(job=ready, cpu=cpu, started_utc=utc())
                    status()
                if not active:
                    require(not pending or failures, "Explicit dependency plan has no ready role")
                    break
                done, _ = wait(active, return_when=FIRST_COMPLETED)
                for future in done:
                    assigned = active.pop(future)
                    free.add(assigned["cpu"])
                    try:
                        path = future.result()
                        completed[assigned["job"]] = path
                        receipts[assigned["job"]] = receipt(path / "result.json")
                    except Exception:
                        failures.append(assigned | dict(traceback=traceback.format_exc()))
                status()
        if failures:
            artifact.write_json(
                output / "failure.json",
                dict(
                    status="failed",
                    utc=utc(),
                    failures=failures,
                    completed=receipts,
                    unlaunched=pending,
                    elapsed_seconds=time.monotonic() - began,
                    **POLICY,
                ),
            )
            artifact.write_json(
                output / "status.json",
                dict(
                    status="failed", utc=utc(), failure=receipt(output / "failure.json"), **POLICY
                ),
            )
            return 1
        checked(output)
        require(
            set(completed) == set(inputs["pending_jobs"]) | set(inputs.get("retained", {})),
            "Explicit selected roles are incomplete",
        )
        for name, path in completed.items():
            verify_role(context, name, path, completed, receipts[name]["sha256"])
        artifact.write_json(
            output / "result.json",
            dict(
                status="passed",
                utc=utc(),
                elapsed_seconds=time.monotonic() - began,
                newly_executed_roles=len(inputs["pending_jobs"]),
                retained_roles=len(context["completed"]),
                distinct_roles=len(completed),
                all_plan_jobs_completed=set(completed) == set(context["jobs"]),
                results=receipts,
                bundle=inputs["bundle"],
                inputs=receipt(output / "inputs.json"),
                seal=receipt(output / "seal.json"),
                scope="Explicit frozen roles completed; scientific comparisons remain in child "
                "results. No biological, native BETSE solver-loop or GPU claim.",
                **POLICY,
            ),
        )
        artifact.write_json(
            output / "status.json",
            dict(status="passed", utc=utc(), result=receipt(output / "result.json"), **POLICY),
        )
        return 0
    except BaseException as error:
        artifact.failure(output, error, context=dict(stage="campaign", **POLICY))
        artifact.write_json(
            output / "status.json",
            dict(status="failed", utc=utc(), failure=receipt(output / "failure.json"), **POLICY),
        )
        return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "check", "launch", "_execute"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--inputs", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if (args.action == "prepare") != (args.inputs is not None):
        parser.error("--inputs is required only for prepare")
    if args.action == "prepare":
        prepare(args.inputs, output)
        print("Prepared; no role executed: " + str(output))
    elif args.action == "check":
        checked(output)
        print("Verified controller, frozen bundle and retained receipts; no role executed")
    elif args.action == "launch":
        print(launch(output))
    else:
        require(
            Path(__file__).resolve() == output / "driver.py", "Execute only the frozen controller"
        )
        return execute(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
