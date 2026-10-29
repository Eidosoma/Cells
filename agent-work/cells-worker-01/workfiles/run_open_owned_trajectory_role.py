"""Execute one explicitly selected prepared role under the existing supervisor.

--check verifies only metadata. There is no matrix launcher, dependency runner,
automatic retry, polling command or numerical execution during preparation.
"""

import argparse
import importlib.metadata
import os
import platform
import sys
from pathlib import Path

MODULES = dict(
    oracle="validation.tissue.open_calcium_trajectory_oracle",
    production="validation.tissue.open_calcium_trajectory_production",
    compare="validation.tissue.open_calcium_trajectory_compare",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--job")
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dependency-runs", type=Path)
    args = parser.parse_args()
    bundle = args.bundle.resolve()
    if Path(__file__).resolve() != bundle / "runner.py":
        parser.error("Use the frozen bundle/runner.py")
    sys.dont_write_bytecode = True
    source = bundle / "source"
    sys.path[:0] = [str(source / "src"), str(source)]
    from validation.tissue import open_calcium_trajectory_common as artifact

    manifest = artifact.verify_bundle(bundle)
    if args.check:
        if any(
            value is not None for value in (args.job, args.cpu, args.output, args.dependency_runs)
        ):
            parser.error("Metadata check takes only --bundle and --check")
        print("Verified immutable metadata only; no numerical role executed")
        print("Manifest SHA256: " + artifact.sha(bundle / "manifest.json"))
        return
    if args.cpu is None or args.output is None or args.job is None:
        parser.error("One explicit --job, --cpu and new --output are required")
    protocol, job, _ = artifact.load_job(
        bundle, args.job, artifact.read_json(bundle / "plan.json")["jobs"][args.job]["role"]
    )
    if (job["role"] == "compare") != (args.dependency_runs is not None):
        parser.error("Only a compare role requires --dependency-runs")
    output = args.output.resolve()
    accepted = Path(manifest["accepted_source"]).resolve()
    if output.exists() or any(
        output.is_relative_to(path) or path.is_relative_to(output) for path in (bundle, accepted)
    ):
        parser.error("Output must be new and separate from frozen source/input bundles")
    output.mkdir(parents=True, exist_ok=False)
    last = {"stage": "role_preflight", "job_id": args.job}
    try:
        resources = protocol["resources"]
        if (
            resources["max_role_wall_seconds"] != 480
            or resources["max_child_tree_rss_bytes"] != 2**30
            or resources["min_available_host_bytes"] != 8 * 2**30
            or resources["threads"] != 1
            or resources["memory_metric"] != "rss"
            or resources["gpu"]
            or resources["persistent_compilation_cache"]
        ):
            raise ValueError("Prepared resource policy changed")
        if args.cpu not in os.sched_getaffinity(0):
            raise ValueError("Explicit selected CPU is outside available process affinity")
        os.sched_setaffinity(0, {args.cpu})
        for name in ("guard", "tmp", "cache"):
            (output / name).mkdir()
        environment = os.environ.copy()
        for name in tuple(environment):
            if (
                name.startswith("JAX_")
                or name.startswith("XLA_")
                or name in ("PYTHONPATH", "PYTHONHOME", "CUDA_VISIBLE_DEVICES")
            ):
                environment.pop(name)
        settings = dict(
            PYTHONDONTWRITEBYTECODE="1",
            PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
            PYTHONPATH=str(source / "src") + os.pathsep + str(source),
            JAX_PLATFORMS="cpu",
            JAX_ENABLE_X64="true",
            JAX_DISABLE_JIT="true",
            JAX_ENABLE_COMPILATION_CACHE="false",
            CUDA_VISIBLE_DEVICES="",
            OMP_NUM_THREADS="1",
            OPENBLAS_NUM_THREADS="1",
            MKL_NUM_THREADS="1",
            NUMEXPR_NUM_THREADS="1",
            BLIS_NUM_THREADS="1",
            VECLIB_MAXIMUM_THREADS="1",
            TF_NUM_INTRAOP_THREADS="1",
            TF_NUM_INTEROP_THREADS="1",
            MALLOC_ARENA_MAX="2",
            TMPDIR=str(output / "tmp"),
            XDG_CACHE_HOME=str(output / "cache"),
        )
        environment.update(settings)
        command = [
            sys.executable,
            "-B",
            "-m",
            MODULES[job["role"]],
            "--bundle",
            str(bundle),
            "--job",
            args.job,
            "--output",
            str(output / "data"),
        ]
        dependency_input = None
        if args.dependency_runs is not None:
            dependency_input = artifact.read_json(args.dependency_runs)
            if set(dependency_input) != set(job["requires"]):
                raise ValueError(
                    "Exactly the five explicitly completed dependency paths are required"
                )
            dependency_input = {
                key: str(Path(value).resolve()) for key, value in dependency_input.items()
            }
            if any(
                output.is_relative_to(Path(value)) or Path(value).is_relative_to(output)
                for value in dependency_input.values()
            ):
                raise ValueError("Comparison output overlaps a completed dependency")
            artifact.write_json(output / "dependency-runs.json", dependency_input)
            command += ["--dependency-runs", str(output / "dependency-runs.json")]
        artifact.write_json(
            output / "inputs.json",
            dict(
                job_id=args.job,
                job=job,
                cpu=args.cpu,
                cpu_affinity=sorted(os.sched_getaffinity(0)),
                command=command,
                environment=settings,
                python=sys.version,
                executable=sys.executable,
                platform=platform.platform(),
                versions={
                    name: importlib.metadata.version(name)
                    for name in ("numpy", "scipy", "jax", "jaxlib")
                },
                resources=resources,
                bundle_manifest_sha256=artifact.sha(bundle / "manifest.json"),
                source_before_sha256=artifact.digest(
                    {
                        key: value
                        for key, value in manifest["file_sha256"].items()
                        if key.startswith("source/")
                    }
                ),
                dependency_runs=dependency_input,
                automatic_dependency_execution=False,
                automatic_retry=False,
                automatic_followup=False,
            ),
        )
        # The supervisor's imports are confined to this parent process; the
        # independent oracle starts a fresh interpreter and rejects Cells/JAX.
        from validation.assembly.component_process import run_bounded

        last["stage"] = "bounded_child"
        resource = run_bounded(
            command,
            directory=output / "guard",
            cwd=source,
            env=environment,
            timeout=480,
            max_rss_bytes=2**30,
            min_available_bytes=8 * 2**30,
            process_tree_memory_metric="rss",
        )
        last["stage"] = "post_role_source_and_artifact_verification"
        artifact.verify_bundle(bundle)
        record = artifact.verify_result(output / "data")
        if record["job_id"] != args.job or record["bundle_manifest_sha256"] != artifact.sha(
            bundle / "manifest.json"
        ):
            raise ValueError("Role result does not belong to the frozen source/job")
        artifact.success(
            output,
            dict(
                job_id=args.job,
                role=job["role"],
                family=job["family"],
                bundle_manifest_sha256=artifact.sha(bundle / "manifest.json"),
                qualifier_result_sha256=artifact.sha(output / "data/result.json"),
                resource_result=resource,
                source_and_input_hashes_unchanged=True,
                automatic_dependency_execution=False,
                automatic_retry=False,
                automatic_followup=False,
            ),
        )
        print("Completed one role: " + args.job)
        print("Result: " + str(output / "result.json"))
    except BaseException as error:
        try:
            artifact.verify_bundle(bundle)
            last["source_and_input_hashes_unchanged"] = True
        except BaseException as drift:
            last["source_and_input_hashes_unchanged"] = False
            last["source_verification_error"] = str(drift)
        last["resource_stop_evidence"] = str(output / "guard")
        last["durable_numerical_prefix"] = str(output / "data/partial.npz")
        last["resource_stop_policy"] = (
            "Retain last durable prefix and progress; no interrupted trial is accepted"
        )
        artifact.failure(output, error, context=last)
        raise


if __name__ == "__main__":
    main()
