"""Freeze a dispatch-patched copy and run disjoint bounded public API phases.

Each compiler/checkpoint producer/consumer is a fresh process over exactly the
same immutable source/runtime environment. No shared source is patched. Select
one phase per invocation; there is no automatic polling or follow-up execution.
"""

import argparse
import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SELF = "agent-work/cells-worker-01/workfiles/check_surface_calcium_energy_regulated_integration.py"
TEST = "tests/unit/test_surface_calcium_energy_regulated_integration.py"
ORACLE = (
    "agent-work/cells-worker-01/workfiles/capture_surface_calcium_energy_regulated_reference.py"
)
PATCH = "agent-work/cells-worker-01/workfiles/integrated_network_regulation_dispatch.patch"
COMPONENT = Path("/mnt/workspaces/Cells/integrated-network-regulation-development-20261029-03")
COMPONENT_SHA = "01113b95ad364a45f0c25da84dde2a666d942f7c161d786d232e15ac2f8f6563"
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
BASE_EPOCH = Path("/mnt/workspaces/Cells/regulated-public-execution-20261029-07")
BASE_MANIFEST_SHA = "0d0343951570571f191a7ca7f544a4827df1bd2697dd06312492c685c97d3dac"
PLANNER_DIAGNOSIS = Path(
    "/mnt/workspaces/Cells/regulated-planner-diagnosis-20261029-01/result.json"
)
PHASE_LIMITS = {name: (900 if name == "plans" else 480) for name in PHASES}
COMPILED = {"scalar-base", "scalar-fine", "restore-scalar", "batch", "restore-batch"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def read(path):
    return json.loads(path.read_text())


def hashes(root):
    return {str(p.relative_to(root)): digest(p) for p in sorted(root.rglob("*")) if p.is_file()}


def ast_proof(previous, current):
    old, new = (ast.parse(p.read_text()) for p in (previous, current))

    def functions(tree):
        return {
            node.name: ast.dump(node, include_attributes=False)
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

    a, b = functions(old), functions(new)
    assert a.keys() == b.keys()
    changed = [name for name in a if a[name] != b[name]]
    assert changed == ["test_reference_independent_world_two_capture"]

    def context(tree):
        return [
            ast.dump(node, include_attributes=False)
            for node in tree.body
            if not isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Import, ast.ImportFrom)
            )
        ]

    assert context(old) == context(new)

    def imports(tree):
        return {
            ast.dump(node, include_attributes=False)
            for node in tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom))
        }

    old_imports, new_imports = imports(old), imports(new)
    assert old_imports <= new_imports
    assert new_imports - old_imports == {
        ast.dump(ast.parse("import subprocess").body[0], include_attributes=False)
    }
    return dict(
        changed_test_functions=changed,
        unchanged_functions_sha256={
            name: hashlib.sha256(value.encode()).hexdigest()
            for name, value in a.items()
            if name not in changed
        },
        only_added_import="subprocess",
    )


def reuse_passing(output):
    snapshot = output / "snapshot"
    proof = ast_proof(BASE_EPOCH / "snapshot" / TEST, snapshot / TEST)
    # Model, oracle equations and input definitions stay byte-identical. Only
    # the oracle launcher test, its standalone script and this runner changed.
    previous = read(BASE_EPOCH / "frozen-sources.json")["after_sha256"]
    current = hashes(snapshot)
    for relative, sha in previous.items():
        if relative not in (SELF, TEST):
            assert current[relative] == sha, relative
    for world in (1, 2):
        relative = "inputs/world-" + str(world) + ".json"
        assert digest(output / relative) == digest(BASE_EPOCH / relative)
    old_runner = ast.parse((BASE_EPOCH / "snapshot" / SELF).read_text())
    new_runner = ast.parse((snapshot / SELF).read_text())
    for name in ("environment", "bounded", "phase"):
        old_node = next(
            n for n in old_runner.body if isinstance(n, ast.FunctionDef) and n.name == name
        )
        new_node = next(
            n for n in new_runner.body if isinstance(n, ast.FunctionDef) and n.name == name
        )
        assert ast.dump(old_node, include_attributes=False) == ast.dump(
            new_node, include_attributes=False
        )
    # Collect actual identity in another clean process. Importing cells.io in
    # the preparer would use the guard's already-imported workspace modules.
    script = output / "reuse-runtime-probe.py"
    script.write_text("""import json,os
from pathlib import Path
import cells
from cells.io import runtime_identity,source_hashes
out=Path(os.environ['CELLS_REGULATED_PUBLIC_OUTPUT'])
assert Path(cells.__file__).resolve().is_relative_to(out/'snapshot')
value=dict(runtime=runtime_identity('cpu'),source_hashes=source_hashes())
(out/'reuse-runtime.json').write_text(json.dumps(value,indent=2)+'\\n')
""")
    measured = bounded(
        [sys.executable, "-B", str(script)],
        output / "reuse-runtime-guard",
        snapshot,
        environment(output),
        timeout=60,
    )
    assert measured["status"] == "passed", measured
    assert read(output / "reuse-runtime.json") == read(BASE_EPOCH / "public_identity.json")
    shutil.copyfile(BASE_EPOCH / "public_identity.json", output / "public_identity.json")
    inherited = {}
    for name in ("contracts", "plans"):
        source = BASE_EPOCH / "phases" / name
        receipt = read(source / "result.json")
        assert receipt["status"] == "passed" and receipt["tests"] == dict(
            tests=1, errors=0, failures=0, skipped=0
        )
        for relative, sha in receipt["output_sha256"].items():
            assert digest(source / relative) == sha
        shutil.copytree(source, output / "phases" / name)
        inherited[name] = dict(
            source=str(source),
            receipt_sha256=digest(source / "result.json"),
            executed_in_this_epoch=False,
        )
    for name in ("contracts", "offline-plans", "offline-plan-progress"):
        source = BASE_EPOCH / "evidence" / (name + ".json")
        assert read(source)["status"] == "passed"
        shutil.copyfile(source, output / "evidence" / source.name)
    proof.update(
        status="passed",
        reused_phases=inherited,
        source_runtime_identity_exact=True,
        previous_manifest_sha256=BASE_MANIFEST_SHA,
        physical_source_unchanged=True,
        runtime_guard=measured,
        failed_oracle_phase_retained=str(BASE_EPOCH / "phases/reference/result.json"),
    )
    write(output / "reuse-proof.json", proof)


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
        CELLS_REGULATED_PUBLIC_OUTPUT=str(output),
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
    output.mkdir(exist_ok=False)
    for name in ("tmp", "cache", "inputs", "references", "evidence", "phases", "initial_owned"):
        (output / name).mkdir()
    assert sorted(os.sched_getaffinity(0)) == [7]
    for relative in (SELF, TEST, ORACLE):
        destination = output / "initial_owned" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    # Formatting/lint may mutate only these newly owned workfiles, before freeze.
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
    assert component["status"] == "passed" and component["tests"]["tests"] == 46
    evidence_path = COMPONENT / "evidence/integrated-network-regulation-coupled-cpu-refinement.json"
    reference_path = COMPONENT / "evidence/coupled-cpu-refinement.npz"
    for path in (evidence_path, reference_path):
        assert digest(path) == component["output_sha256"][str(path.relative_to(COMPONENT))]
    inputs = read(evidence_path)["inputs"]
    assert inputs["experiment"]["end_time"] == 1e-5
    write(output / "inputs/world-1.json", inputs)
    second = json.loads(json.dumps(inputs))
    second["model"]["network_regulation"]["rules"][0]["configuration"]["max effect"] = 0.6
    second["experiment"]["pump_controls"][0]["schedule"][1]["time"] = 3.9e-6
    second["experiment"]["pump_controls"][0]["schedule"][2].update(time=7.4e-6, availability=0.55)
    second["experiment"]["observation_times"] = [0.0, 3.9e-6, 6.25e-6, 7.4e-6, 1e-5]
    write(output / "inputs/world-2.json", second)
    shutil.copyfile(reference_path, output / "references/world-1.npz")
    # Reuse the established frozen public source epoch so concurrent Chief cut
    # development cannot change this retry's physical or checkpoint semantics.
    assert digest(BASE_EPOCH / "frozen-sources.json") == BASE_MANIFEST_SHA
    established = read(BASE_EPOCH / "frozen-sources.json")
    assert hashes(BASE_EPOCH / "snapshot") == established["after_sha256"]
    before = established["after_sha256"]
    content = {p: (BASE_EPOCH / "snapshot" / p).read_bytes() for p in before}
    for relative in (SELF, TEST, ORACLE):
        content[relative] = (ROOT / relative).read_bytes()
    snapshot = output / "snapshot"
    for relative, data in content.items():
        destination = snapshot / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    for relative, sha in component["source_sha256"].items():
        if "regulated" in relative or "integrated_network_regulation" in relative:
            assert digest(snapshot / relative) == sha, relative
    applied = output / "applied-dispatch.patch"
    shutil.copyfile(BASE_EPOCH / "applied-dispatch.patch", applied)
    assert digest(applied) == established["applied_patch_sha256"]
    after = hashes(snapshot)
    modified = [relative for relative in before if before[relative] != after[relative]]
    assert set(modified) == {SELF, TEST}
    assert set(after) - set(before) == {ORACLE}
    assert {p: sha for p, sha in after.items() if p.startswith("src/")} == {
        p: sha for p, sha in before.items() if p.startswith("src/")
    }
    manifest = dict(
        status="frozen",
        before_sha256=before,
        after_sha256=after,
        dispatch_modified=established["dispatch_modified"],
        retry_modified=[*modified, ORACLE],
        inherited_source_epoch=str(BASE_EPOCH),
        inherited_manifest_sha256=BASE_MANIFEST_SHA,
        patch_sha256=digest(snapshot / PATCH),
        applied_patch_sha256=digest(applied),
        context_rebased=established["context_rebased"],
        source_package_unchanged_from_established_epoch=True,
        shared_files_written=False,
        planner_diagnosis=str(PLANNER_DIAGNOSIS),
        planner_diagnosis_sha256=digest(PLANNER_DIAGNOSIS),
        accepted_component_receipt=str(COMPONENT / "result.json"),
        accepted_component_sha256=COMPONENT_SHA,
    )
    write(output / "frozen-sources.json", manifest)
    write(
        output / "inputs.json",
        dict(
            status="prepared",
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
        ),
    )
    for p in snapshot.rglob("*"):
        if p.is_file():
            p.chmod(0o444)
    for p in sorted(
        (p for p in snapshot.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True
    ):
        p.chmod(0o555)
    snapshot.chmod(0o555)
    reuse_passing(output)
    print(
        json.dumps(
            dict(status="prepared", snapshot=str(snapshot), files=len(after), modified=modified)
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phase", choices=("prepare", *PHASES, "suite", "finalize"), required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.parent != Path("/mnt/workspaces/Cells") or not output.name.startswith(
        "regulated-public-execution-"
    ):
        parser.error("Use /mnt/workspaces/Cells/regulated-public-execution-* output")
    assert sorted(os.sched_getaffinity(0)) == [7]
    try:
        if args.phase == "prepare":
            return prepare(output)
        if args.phase == "suite":
            return suite(output)
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
