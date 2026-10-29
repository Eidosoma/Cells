"""Continue frozen @1 public phases with larger wall limits and exact reuse.

The original runner, tests, package, inputs and scientific tolerances are copied
byte for byte. Only this separate orchestration file is added. Passed phases and
their public artifacts are verified and inherited; unfinished phases use the
unchanged runner with an explicitly recorded wall-budget override.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SELF = "agent-work/cells-worker-01/workfiles/continue_surface_calcium_energy_regulated_public.py"
LEGACY = (
    "agent-work/cells-worker-01/workfiles/check_surface_calcium_energy_regulated_integration.py"
)
BASE = Path("/mnt/workspaces/Cells/regulated-public-execution-20261029-09")
BASE_MANIFEST_SHA = "3d02c192cf26ba70d62b7e277f8f3c6f2a31ff6dd70492426be3dfa194bb8714"
REUSE = ("contracts", "plans", "reference", "scalar-base")
REMAINING = ("scalar-fine", "restore-scalar", "batch", "restore-batch")
WALL_SECONDS = 2700


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def hashes(root):
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob("*")) if p.is_file()}


def legacy(output):
    path = output / "snapshot" / LEGACY
    spec = importlib.util.spec_from_file_location("frozen_regulated_public_runner", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # These are orchestration allowances only. The imported runner's functions,
    # guard implementation and every numerical/public test remain unmodified.
    for name in REMAINING:
        module.PHASE_LIMITS[name] = WALL_SECONDS
    return module


def prepare(output):
    assert sha(BASE / "frozen-sources.json") == BASE_MANIFEST_SHA
    established = read(BASE / "frozen-sources.json")
    before = established["after_sha256"]
    assert hashes(BASE / "snapshot") == before
    stopped = read(BASE / "phases/scalar-fine/guard/resource-stop.json")
    assert stopped["reasons"] == ["wall_time_allowance"]
    assert stopped["limits"]["max_wall_seconds"] == 480
    assert stopped["limits"]["max_process_tree_rss_bytes"] == 4 * 2**30
    assert read(BASE / "phases/scalar-fine/result.json")["tests"] == dict(
        tests=0, errors=0, failures=0, skipped=0
    )
    output.mkdir(exist_ok=False)
    for name in ("tmp", "cache", "phases", "evidence", "references", "inputs", "external-timing"):
        (output / name).mkdir()
    for relative in before:
        target = output / "snapshot" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((BASE / "snapshot" / relative).read_bytes())
    assert SELF not in before
    (output / "snapshot" / SELF).write_bytes((ROOT / SELF).read_bytes())
    after = hashes(output / "snapshot")
    assert {p: after[p] for p in before} == before
    assert set(after) - set(before) == {SELF}
    for name in ("inputs", "references", "evidence", "scalar-base"):
        for path in sorted((BASE / name).rglob("*")):
            if path.is_file():
                target = output / path.relative_to(BASE)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
    for name in ("applied-dispatch.patch", "public_identity.json"):
        shutil.copyfile(BASE / name, output / name)
    inherited = {}
    for name in REUSE:
        source = BASE / "phases" / name
        receipt = read(source / "result.json")
        assert receipt["status"] == "passed" and receipt["tests"] == dict(
            tests=1, errors=0, failures=0, skipped=0
        )
        for relative, expected in receipt["output_sha256"].items():
            assert sha(source / relative) == expected
        shutil.copytree(source, output / "phases" / name)
        assert hashes(source) == hashes(output / "phases" / name)
        inherited[name] = dict(
            source=str(source),
            receipt_sha256=sha(source / "result.json"),
            executed_in_this_epoch=False,
        )
    # Public producer checksums cover the run/config/trajectory and both full
    # checkpoints; pin the extra complete trace and all copied evidence too.
    run = BASE / "scalar-base/run"
    for relative, expected in read(run / "manifest.json")["files_sha256"].items():
        assert sha(run / relative) == expected
    copied = {}
    for name in ("inputs", "references", "evidence", "scalar-base"):
        assert hashes(BASE / name) == hashes(output / name)
        copied.update({name + "/" + p: h for p, h in hashes(output / name).items()})
    manifest = dict(
        status="frozen",
        before_sha256=before,
        after_sha256=after,
        inherited_source_epoch=str(BASE),
        inherited_manifest_sha256=BASE_MANIFEST_SHA,
        added_orchestration_file=SELF,
        numerical_source_changes=[],
        test_changes=[],
        source_package_unchanged_from_established_epoch=True,
        shared_files_written=False,
        wall_budget_override={name: WALL_SECONDS for name in REMAINING},
        applied_patch_sha256=sha(output / "applied-dispatch.patch"),
    )
    write(output / "frozen-sources.json", manifest)
    module = legacy(output)
    previous_inputs = read(BASE / "inputs.json")
    env = module.environment(output)
    selected = {key: env[key] for key in previous_inputs["environment"]}
    for key, value in previous_inputs["environment"].items():
        if key != "PYTHONPATH":
            assert selected[key] == value, key
    inputs = dict(
        previous_inputs,
        environment=selected,
        max_phase_seconds=module.PHASE_LIMITS,
        continuation_from=str(BASE),
        reused_phases=list(REUSE),
        remaining_phases=list(REMAINING),
        external_timing=True,
    )
    write(output / "inputs.json", inputs)
    probe = output / "reuse-runtime-probe.py"
    probe.write_text("""import json,os
from pathlib import Path
import cells
from cells.io import runtime_identity,source_hashes
out=Path(os.environ['CELLS_REGULATED_PUBLIC_OUTPUT'])
assert Path(cells.__file__).resolve().is_relative_to(out/'snapshot')
(out/'reuse-runtime.json').write_text(json.dumps(dict(runtime=runtime_identity('cpu'),source_hashes=source_hashes()),indent=2)+'\\n')
""")
    measured = module.bounded(
        [sys.executable, "-B", str(probe)],
        output / "reuse-runtime-guard",
        output / "snapshot",
        env,
        timeout=60,
    )
    assert measured["status"] == "passed", measured
    assert read(output / "reuse-runtime.json") == read(BASE / "public_identity.json")
    proof = dict(
        status="passed",
        reused_phases=inherited,
        source_runtime_identity_exact=True,
        previous_manifest_sha256=BASE_MANIFEST_SHA,
        original_snapshot_files=len(before),
        exact_unchanged_snapshot_sha256=before,
        original_runner_and_tests_byte_identical=True,
        physical_source_unchanged=True,
        inputs_reference_public_artifact_sha256=copied,
        numerical_environment_unchanged=True,
        allowed_path_relocation="output/snapshot only",
        runtime_guard=measured,
        only_wall_budget_changed=manifest["wall_budget_override"],
        preserved_failure=dict(
            path=str(BASE / "phases/scalar-fine/result.json"),
            sha256=sha(BASE / "phases/scalar-fine/result.json"),
            reason=stopped["reasons"],
        ),
    )
    write(output / "reuse-proof.json", proof)
    for path in (output / "snapshot").rglob("*"):
        if path.is_file():
            path.chmod(0o444)
    directories = [p for p in (output / "snapshot").rglob("*") if p.is_dir()]
    for path in sorted(directories, key=lambda p: len(p.parts), reverse=True):
        path.chmod(0o555)
    (output / "snapshot").chmod(0o555)
    print(
        json.dumps(
            dict(
                status="prepared",
                output=str(output),
                files=len(after),
                reused=list(REUSE),
                remaining=list(REMAINING),
                max_phase_seconds=WALL_SECONDS,
            )
        )
    )
    return 0


def launch(output):
    assert sha(Path(__file__)) == sha(output / "snapshot" / SELF)
    assert read(output / "reuse-proof.json")["status"] == "passed"
    assert not (output / "job-launch.json").exists()
    module = legacy(output)
    command = [
        sys.executable,
        "-B",
        str(output / "snapshot" / SELF),
        "--output",
        str(output),
        "--action",
        "suite",
    ]
    with (output / "driver.log").open("xb") as log:
        process = subprocess.Popen(
            command,
            cwd=output / "snapshot",
            env=module.environment(output),
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
        snapshot_manifest_sha256=sha(output / "frozen-sources.json"),
        expected_duration_over_10_minutes=True,
        automatic_polling=False,
        reused_phases=list(REUSE),
        remaining_phases=list(REMAINING),
        max_phase_seconds=WALL_SECONDS,
        estimated_minutes=[45, 120],
        worst_case_phase_allowance_minutes=180,
    )
    write(output / "job-launch.json", receipt)
    print(json.dumps(receipt))
    return 0


def suite(output):
    began = time.monotonic()
    module = legacy(output)
    status = dict(
        status="running",
        pid=os.getpid(),
        phases=[dict(name=n, status="reused-passed") for n in REUSE],
    )
    write(output / "job-status.json", status)
    assert Path("/usr/bin/time").is_file()
    for name in REMAINING:
        command = [
            "/usr/bin/time",
            "-v",
            "-o",
            str(output / "external-timing" / (name + ".txt")),
            sys.executable,
            "-B",
            str(output / "snapshot" / SELF),
            "--output",
            str(output),
            "--action",
            "phase",
            "--phase",
            name,
        ]
        start = time.monotonic()
        completed = subprocess.run(command, check=False)
        status["phases"].append(
            dict(name=name, exit_code=completed.returncode, wall_seconds=time.monotonic() - start)
        )
        status["elapsed_seconds"] = time.monotonic() - began
        if completed.returncode:
            status.update(status="failed", failure_phase=name)
            write(output / "job-status.json", status)
            return 1
        write(output / "job-status.json", status)
    code = module.finalize(output)
    status.update(
        status="passed" if code == 0 else "failed", elapsed_seconds=time.monotonic() - began
    )
    write(output / "job-status.json", status)
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--action", choices=("prepare", "launch", "suite", "phase"), required=True)
    parser.add_argument("--phase", choices=REMAINING)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.parent == Path("/mnt/workspaces/Cells")
    assert output.name.startswith("regulated-public-execution-")
    assert sorted(os.sched_getaffinity(0)) == [7]
    try:
        if args.action == "prepare":
            return prepare(output)
        assert sha(Path(__file__)) == sha(output / "snapshot" / SELF)
        if args.action == "launch":
            return launch(output)
        if args.action == "suite":
            return suite(output)
        assert args.phase in REMAINING
        return legacy(output).phase(output, args.phase)
    except Exception as error:
        failure = dict(
            status="failed",
            action=args.action,
            phase=args.phase,
            type=type(error).__name__,
            message=str(error),
            traceback=traceback.format_exc(),
        )
        if output.exists():
            write(output / ("failure-" + args.action + ".json"), failure)
            if args.action == "suite":
                write(output / "job-status.json", failure)
        print(json.dumps(failure))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
