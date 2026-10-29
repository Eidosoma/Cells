"""Freeze a dispatch-patched copy and run disjoint bounded public API phases.

Each compiler/checkpoint producer/consumer is a fresh process over exactly the
same immutable source/runtime environment. No shared source is patched. Select
one phase per invocation; there is no automatic polling or follow-up execution.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SELF = (
    "agent-work/cells-worker-01/workfiles/check_surface_calcium_energy_regulated_v2_integration.py"
)
TEST = "tests/unit/test_surface_calcium_energy_regulated_v2_integration.py"
ORACLE = (
    "agent-work/cells-worker-01/workfiles/"
    "capture_surface_calcium_energy_regulated_v2_public_reference.py"
)
PATCH = "agent-work/cells-worker-01/workfiles/integrated_network_regulation_v2_dispatch.patch"
COMPONENT = Path("/mnt/workspaces/Cells/integrated-network-regulation-v2-development-20261029-03")
COMPONENT_SHA = "8ffa3ba08002b96facd5693a588516fc53a21b0d12806c7bad1a1fcab229e7a6"
PHASES = {
    "contracts": "contracts_public",
    "plans": "plans_offline",
    "reference": "reference_independent",
    "scalar-base": "scalar_checked and base",
    "scalar-fine": "scalar_checked and fine",
    "restore-scalar": "restore_scalar_fresh",
    "batch": "batch_checked_two",
    "restore-batch": "batch_restore_fresh",
}
BASE_EPOCH = Path("/mnt/workspaces/Cells/regulated-public-execution-20261029-09")
BASE_MANIFEST_SHA = "3d02c192cf26ba70d62b7e277f8f3c6f2a31ff6dd70492426be3dfa194bb8714"
PHASE_LIMITS = {name: (900 if name == "plans" else 480) for name in PHASES}
COMPILED = {"scalar-base", "scalar-fine", "restore-scalar", "batch", "restore-batch"}
PHASE_LIMITS.update({name: 2700 for name in COMPILED})


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def read(path):
    return json.loads(path.read_text())


def hashes(root):
    return {str(p.relative_to(root)): digest(p) for p in sorted(root.rglob("*")) if p.is_file()}


def environment(output):
    env = os.environ.copy()
    env.update(
        dict.fromkeys(
            ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"),
            "1",
        )
    )
    env.update(
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        PYTHONPATH=str(output / "snapshot/src") + os.pathsep + str(output / "snapshot"),
        JAX_PLATFORMS="cpu",
        JAX_ENABLE_X64="true",
        CUDA_VISIBLE_DEVICES="",
        JAX_ENABLE_COMPILATION_CACHE="false",
        XLA_FLAGS="--xla_cpu_multi_thread_eigen=false",
        CELLS_REGULATED_V2_PUBLIC_OUTPUT=str(output),
        MALLOC_ARENA_MAX="2",
        XDG_CACHE_HOME=str(output / "cache"),
        JAX_COMPILATION_CACHE_DIR=str(output / "cache/jax"),
        TMPDIR=str(output / "tmp"),
    )
    env.pop("JAX_DISABLE_JIT", None)
    return env


def bounded(command, directory, cwd, env, *, compiled=False, timeout=480):
    directory.mkdir()
    sys.path[:0] = [str(cwd / "src"), str(cwd)]
    from validation.assembly.component_process import run_bounded

    began = time.monotonic()
    error = None
    try:
        run_bounded(
            command,
            directory=directory,
            cwd=cwd,
            env=env,
            timeout=timeout,
            max_rss_bytes=(4 if compiled else 1) * 2**30,
            min_available_bytes=8 * 2**30,
        )
    except Exception as exception:
        error = dict(
            type=type(exception).__name__, message=str(exception), traceback=traceback.format_exc()
        )
    return dict(
        status="passed" if error is None else "failed",
        wall_seconds=time.monotonic() - began,
        error=error,
    )


def prepare(output):
    """Freeze integrated Chief dispatch, accepted @2 equations and new tests.

    This mode performs no trajectory compiler invocation or planner execution.
    Short contracts/reference phases can be called explicitly after freeze.
    """
    output.mkdir(exist_ok=False)
    for name in ("tmp", "cache", "inputs", "references", "evidence", "phases", "initial_owned"):
        (output / name).mkdir()
    assert sorted(os.sched_getaffinity(0)) == [7]
    for relative in (SELF, TEST, ORACLE):
        destination = output / "initial_owned" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    ruff = str(Path(sys.executable).parent / "ruff")
    setup_env = environment(output)
    for name, args in (
        ("imports", ["check", "--no-cache", "--select", "I", "--fix", SELF, TEST, ORACLE]),
        ("format", ["format", "--no-cache", SELF, TEST, ORACLE]),
        ("lint", ["check", "--no-cache", SELF, TEST, ORACLE]),
    ):
        result = bounded([ruff, *args], output / ("prepare-" + name), ROOT, setup_env, timeout=60)
        write(output / ("prepare-" + name + ".json"), result)
        if result["status"] != "passed":
            write(output / "failure.json", dict(stage="prepare-" + name, **result))
            return 1
    assert digest(COMPONENT / "result.json") == COMPONENT_SHA
    component = read(COMPONENT / "result.json")
    assert component["status"] == "passed" and component["tests"] == dict(
        tests=41, errors=0, failures=0, skipped=0
    )
    source_input = COMPONENT / "evidence/regulation-v2-coupled-refinement.json"
    source_reference = COMPONENT / "evidence/coupled-refinement.npz"
    for path in (source_input, source_reference):
        assert digest(path) == component["output_sha256"][str(path.relative_to(COMPONENT))]
    inputs = read(source_input)["inputs"]
    assert inputs["model"]["id"] == "resolved_calcium_energy_regulated@2"
    assert inputs["experiment"]["end_time"] == 5e-6
    assert len(inputs["model"]["network_regulation"]["rules"]) == 8
    write(output / "inputs/world-1.json", inputs)
    second = json.loads(json.dumps(inputs))
    rules = second["model"]["network_regulation"]["rules"]
    rules[0]["configuration"]["max effect"] = 0.6
    rules[4]["configuration"]["activator Km"] = [0.45]
    rules[7]["configuration"]["max effect"] = 0.7
    for family in ("pump_controls", "channel_controls", "junction_controls"):
        second["experiment"][family][0]["schedule"][1]["time"] = 1.7e-6
        second["experiment"][family][0]["schedule"][2].update(time=3.7e-6, availability=0.55)
    second["experiment"]["observation_times"] = [0.0, 1.7e-6, 2.5e-6, 3.7e-6, 5e-6]
    write(output / "inputs/world-2.json", second)
    shutil.copyfile(source_reference, output / "references/world-1.npz")
    # Use the established complete file list, refreshed from the integrated
    # workspace. Add every current package file and the distinct @2 family.
    # No historical patch is applied: both reviewed branches are already wired.
    assert digest(BASE_EPOCH / "frozen-sources.json") == BASE_MANIFEST_SHA
    established = read(BASE_EPOCH / "frozen-sources.json")
    paths = set(established["after_sha256"])
    paths.update(
        str(p.relative_to(ROOT))
        for p in (ROOT / "src").rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    )
    paths.update(p for p in component["source_sha256"] if (ROOT / p).is_file())
    paths.update(
        (
            SELF,
            TEST,
            ORACLE,
            PATCH,
            "agent-work/cells-worker-01/workfiles/integrated_network_regulation_v2_dispatch.json",
            "agent-work/cells-worker-01/workfiles/INTEGRATED_NETWORK_REGULATION_V2_HANDOFF.md",
        )
    )
    content = {p: (ROOT / p).read_bytes() for p in sorted(paths)}
    shared = (
        "src/cells/core/specs.py",
        "src/cells/core/schedule.py",
        "src/cells/models/registry.py",
        "src/cells/ensemble/ionic.py",
    )
    for relative in shared:
        text = content[relative].decode()
        assert (
            "resolved_calcium_energy_regulated@2"
            if relative.endswith("ionic.py")
            else "surface_calcium_energy_regulated_v2"
        ) in text, relative
    for relative, expected in component["source_sha256"].items():
        if relative in content and (
            "regulated_v2" in relative
            or "regulation_v2_" in relative
            or relative
            in read(ROOT / "validation/regulation/integrated_network_regulation_v2_protocol.json")[
                "readonly_source_sha256"
            ]
        ):
            assert hashlib.sha256(content[relative]).hexdigest() == expected, relative
    snapshot = output / "snapshot"
    for relative, data in content.items():
        target = snapshot / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    after = hashes(snapshot)
    # Refuse a mixed snapshot if Chief changed a copied source during capture.
    assert {p: digest(ROOT / p) for p in paths} == after
    manifest = dict(
        status="frozen",
        after_sha256=after,
        inherited_file_list_epoch=str(BASE_EPOCH),
        inherited_manifest_sha256=BASE_MANIFEST_SHA,
        accepted_component_receipt=str(COMPONENT / "result.json"),
        accepted_component_sha256=COMPONENT_SHA,
        integrated_working_dispatch_sha256={p: after[p] for p in shared},
        dispatch_patch_applied=False,
        dispatch_scope="Chief integrated @1/@2 branches copied; historical patch not applied",
        shared_files_written=False,
        compiled_execution_launched=False,
    )
    write(output / "frozen-sources.json", manifest)
    write(
        output / "inputs.json",
        dict(
            status="prepared",
            model_id="resolved_calcium_energy_regulated@2",
            phases=PHASES,
            environment={
                k: v
                for k, v in setup_env.items()
                if k
                in (
                    "PYTHONPATH",
                    "XLA_FLAGS",
                    "JAX_PLATFORMS",
                    "JAX_ENABLE_X64",
                    "JAX_ENABLE_COMPILATION_CACHE",
                    "CUDA_VISIBLE_DEVICES",
                    "PYTHONDONTWRITEBYTECODE",
                    "OPENBLAS_NUM_THREADS",
                    "OMP_NUM_THREADS",
                    "MKL_NUM_THREADS",
                    "NUMEXPR_NUM_THREADS",
                )
            },
            affinity=[7],
            max_host_rss_bytes=2**30,
            max_compiled_rss_bytes=4 * 2**30,
            min_available_memory_bytes=8 * 2**30,
            max_phase_seconds=PHASE_LIMITS,
            automatic_followup=False,
            compiled_execution_launched=False,
        ),
    )
    write(
        output / "reuse-proof.json",
        dict(
            status="passed",
            reused_phases={},
            accepted_component_sha256=COMPONENT_SHA,
            world_1_input_sha256=digest(output / "inputs/world-1.json"),
            source_world_1_evidence_sha256=digest(source_input),
            world_1_reference_sha256=digest(source_reference),
            world_1_reference_copied_exactly=digest(output / "references/world-1.npz")
            == digest(source_reference),
            host_components_requalified=False,
            public_phase_reuse_from_v1=False,
        ),
    )
    collected = bounded(
        [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            str(snapshot / TEST),
        ],
        output / "prepare-collect",
        snapshot,
        setup_env,
        timeout=120,
    )
    write(output / "prepare-collect.json", collected)
    assert collected["status"] == "passed", collected
    assert "8 tests collected" in (output / "prepare-collect/stdout.log").read_text()
    assert hashes(snapshot) == after
    for path in snapshot.rglob("*"):
        if path.is_file():
            path.chmod(0o444)
    for path in sorted(
        (p for p in snapshot.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True
    ):
        path.chmod(0o555)
    snapshot.chmod(0o555)
    print(
        json.dumps(
            dict(
                status="prepared",
                output=str(output),
                files=len(after),
                tests_collected=8,
                compiled_execution_launched=False,
                dispatch_patch_applied=False,
            )
        )
    )
    return 0


def phase(output, name):
    snapshot = output / "snapshot"
    frozen = read(output / "frozen-sources.json")
    assert hashes(snapshot) == frozen["after_sha256"]
    assert Path(__file__).read_bytes() == (snapshot / SELF).read_bytes()
    directory = output / "phases" / name
    directory.mkdir(exist_ok=False)
    environment_values = environment(output)
    command = [
        sys.executable,
        "-B",
        "-m",
        "pytest",
        "-q",
        "-s",
        "-p",
        "no:cacheprovider",
        str(snapshot / TEST),
        "-k",
        PHASES[name],
        "--basetemp=" + str(output / "tmp" / name),
        "--junitxml=" + str(directory / "tests.xml"),
    ]
    write(
        directory / "inputs.json",
        dict(
            command=command,
            cwd=str(snapshot),
            source_manifest_sha256=digest(output / "frozen-sources.json"),
            environment=read(output / "inputs.json")["environment"],
            compiled=name in COMPILED,
            max_wall_seconds=PHASE_LIMITS[name],
        ),
    )
    result = bounded(
        command,
        directory / "guard",
        snapshot,
        environment_values,
        compiled=name in COMPILED,
        timeout=PHASE_LIMITS[name],
    )
    result["sources_changed"] = hashes(snapshot) != frozen["after_sha256"]
    counts = {k: 0 for k in ("tests", "errors", "failures", "skipped")}
    if (directory / "tests.xml").exists():
        suites = list(ET.parse(directory / "tests.xml").getroot().iter("testsuite"))
        counts = {k: sum(int(s.get(k, "0")) for s in suites) for k in counts}
    result["tests"] = counts
    if (
        result["sources_changed"]
        or counts["tests"] != 1
        or any(counts[k] for k in ("errors", "failures", "skipped"))
    ):
        result["status"] = "failed"
    result["output_sha256"] = hashes(directory)
    write(directory / "result.json", result)
    if result["status"] != "passed":
        write(directory / "failure.json", result)
    print(
        json.dumps(
            dict(phase=name, **{k: result[k] for k in ("status", "tests", "wall_seconds", "error")})
        )
    )
    return 0 if result["status"] == "passed" else 1


def finalize(output):
    frozen = read(output / "frozen-sources.json")
    assert hashes(output / "snapshot") == frozen["after_sha256"]
    results = {name: read(output / "phases" / name / "result.json") for name in PHASES}
    assert all(
        r["status"] == "passed" and r["tests"] == dict(tests=1, errors=0, failures=0, skipped=0)
        for r in results.values()
    )
    for name, result in results.items():
        for relative, sha in result["output_sha256"].items():
            assert digest(output / "phases" / name / relative) == sha
    guards = {name: read(output / "phases" / name / "guard/result.json") for name in PHASES}
    for name, guard in guards.items():
        assert (
            guard["sampled_peak_process_tree_rss_bytes"] <= (4 if name in COMPILED else 1) * 2**30
        )
        assert guard["minimum_available_host_memory_bytes"] >= 8 * 2**30
    result = dict(
        status="passed",
        tests=8,
        phases=results,
        resource_guards=guards,
        source_manifest_sha256=digest(output / "frozen-sources.json"),
        identity=read(output / "public_identity.json"),
        reused_phase_proof=read(output / "reuse-proof.json"),
        shared_source_edits=False,
        gpu_executed=False,
        automatic_followup=False,
    )
    result["output_sha256"] = {
        p: sha
        for p, sha in hashes(output).items()
        if p not in {"job-status.json", "job-launch.json", "driver.log", "result.json"}
    }
    write(output / "result.json", result)
    print(
        json.dumps(
            dict(
                status="passed",
                receipt=str(output / "result.json"),
                sha256=digest(output / "result.json"),
            )
        )
    )
    return 0


def suite(output):
    """Explicitly requested acceptance job; intended for detached launch."""
    began = time.monotonic()
    result = dict(status="running", pid=os.getpid(), phases=[])
    write(output / "job-status.json", result)
    for name in PHASES:
        receipt = output / "phases" / name / "result.json"
        if receipt.exists():
            if read(receipt)["status"] != "passed":
                result.update(
                    status="failed",
                    failure_phase=name,
                    message="Existing failed evidence retained; use a fresh output",
                )
                write(output / "job-status.json", result)
                return 1
            result["phases"].append(dict(name=name, status="passed-preflight"))
            continue
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                str(output / "snapshot" / SELF),
                "--output",
                str(output),
                "--phase",
                name,
            ],
            check=False,
        )
        result["phases"].append(dict(name=name, exit_code=completed.returncode))
        result["elapsed_seconds"] = time.monotonic() - began
        if completed.returncode:
            result.update(status="failed", failure_phase=name)
            write(output / "job-status.json", result)
            return 1
        write(output / "job-status.json", result)
    code = finalize(output)
    result.update(
        status="passed" if code == 0 else "failed", elapsed_seconds=time.monotonic() - began
    )
    write(output / "job-status.json", result)
    return code


def launch(output):
    """Explicit future launch only; preparation never calls this function."""
    assert not (output / "job-launch.json").exists()
    assert hashes(output / "snapshot") == read(output / "frozen-sources.json")["after_sha256"]
    command = [
        sys.executable,
        "-B",
        str(output / "snapshot" / SELF),
        "--output",
        str(output),
        "--phase",
        "suite",
    ]
    with (output / "driver.log").open("xb") as log:
        process = subprocess.Popen(
            command,
            cwd=output / "snapshot",
            env=environment(output),
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
    receipt = dict(
        status="launched",
        pid=process.pid,
        started_utc=datetime.now(UTC).isoformat(),
        command=command,
        snapshot_manifest_sha256=digest(output / "frozen-sources.json"),
        expected_duration_over_10_minutes=True,
        automatic_polling=False,
        max_phase_seconds=PHASE_LIMITS,
        maximum_phase_allowance_seconds=sum(PHASE_LIMITS.values()),
    )
    write(output / "job-launch.json", receipt)
    print(json.dumps(receipt))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--phase", choices=("prepare", *PHASES, "suite", "finalize", "launch"), required=True
    )
    args = parser.parse_args()
    output = args.output.resolve()
    if output.parent != Path("/mnt/workspaces/Cells") or not output.name.startswith(
        "regulated-v2-public-execution-"
    ):
        parser.error("Use /mnt/workspaces/Cells/regulated-v2-public-execution-* output")
    assert sorted(os.sched_getaffinity(0)) == [7]
    try:
        if args.phase == "prepare":
            return prepare(output)
        if args.phase == "suite":
            return suite(output)
        if args.phase == "launch":
            return launch(output)
        return finalize(output) if args.phase == "finalize" else phase(output, args.phase)
    except Exception as exception:
        failure = dict(
            status="failed",
            phase=args.phase,
            type=type(exception).__name__,
            message=str(exception),
            traceback=traceback.format_exc(),
        )
        if output.exists() and not (output / ("failure-" + args.phase + ".json")).exists():
            write(output / ("failure-" + args.phase + ".json"), failure)
        if args.phase == "suite" and output.exists():
            write(output / "job-status.json", failure)
        print(json.dumps(failure))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
