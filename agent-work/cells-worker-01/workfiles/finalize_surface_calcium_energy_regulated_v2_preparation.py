"""Record prepared @2 public coverage without starting any pending phase."""

import argparse
import ast
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

WORK = "agent-work/cells-worker-01/workfiles/"
DRIVER = WORK + "check_surface_calcium_energy_regulated_v2_integration.py"
TEST = "tests/unit/test_surface_calcium_energy_regulated_v2_integration.py"
BASE = Path("/mnt/workspaces/Cells/regulated-public-execution-20261029-09/snapshot")


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hashes(root):
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob("*")) if p.is_file()}


def functions(path):
    return {
        node.name: ast.dump(node, include_attributes=False)
        for node in ast.parse(path.read_text()).body
        if isinstance(node, ast.FunctionDef)
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.parent == Path("/mnt/workspaces/Cells")
    assert output.name.startswith("regulated-v2-public-execution-")
    assert not (output / "preparation-result.json").exists()
    frozen = read(output / "frozen-sources.json")
    assert hashes(output / "snapshot") == frozen["after_sha256"]
    assert not frozen["dispatch_patch_applied"] and not frozen["shared_files_written"]
    component = Path(frozen["accepted_component_receipt"])
    assert sha(component) == frozen["accepted_component_sha256"]
    assert read(component)["status"] == "passed"
    assert "8 tests collected" in (output / "prepare-collect/stdout.log").read_text()
    inputs = read(output / "inputs.json")
    assert inputs["affinity"] == [7]
    receipts, guards = {}, {}
    for name in ("contracts", "reference"):
        path = output / "phases" / name
        report = read(path / "result.json")
        assert report["status"] == "passed" and not report["sources_changed"]
        assert report["tests"] == dict(tests=1, errors=0, failures=0, skipped=0)
        for relative, expected in report["output_sha256"].items():
            assert sha(path / relative) == expected
        guard = read(path / "guard/result.json")
        assert guard["status"] == "completed"
        assert guard["sampled_peak_process_tree_rss_bytes"] <= 2**30
        assert guard["minimum_available_host_memory_bytes"] >= 8 * 2**30
        receipts[name] = dict(path=str(path / "result.json"), sha256=sha(path / "result.json"))
        guards[name] = guard
    pending = [name for name in inputs["phases"] if name not in receipts]
    assert len(pending) == 6
    assert not any((output / "phases" / name).exists() for name in pending)
    assert not (output / "job-launch.json").exists()
    assert not (output / "job-status.json").exists()
    oracle = read(output / "evidence/independent-world-two.json")
    assert oracle["status"] == "passed" and len(oracle["fields"]) == 38
    assert not oracle["execution"]["pytest_imported"]
    assert not oracle["production_imported"] and not oracle["jax_imported"]
    assert all(not v for v in oracle["independence_guards"].values())
    assert oracle["inputs"] == read(output / "inputs/world-2.json")
    # Reuse established execution/guard machinery, with different model/data
    # identity and explicit larger compiled allowances. No public API hook is
    # substituted, and no numerical integrator is implemented by this driver.
    old = functions(BASE / (WORK + "check_surface_calcium_energy_regulated_integration.py"))
    new = functions(output / "snapshot" / DRIVER)
    reused = ("bounded", "phase", "suite", "finalize")
    for name in reused:
        assert old[name] == new[name], name
    old_tests = functions(BASE / "tests/unit/test_surface_calcium_energy_regulated_integration.py")
    new_tests = functions(output / "snapshot" / TEST)
    for name in ("merge_windows", "save_trace", "scalar_run"):
        assert old_tests[name] == new_tests[name], name
    shutil.copyfile(Path(__file__), output / "preparation-finalizer.py")
    result = dict(
        status="prepared",
        completed_utc=datetime.now(UTC).isoformat(),
        model_id="resolved_calcium_energy_regulated@2",
        state_fields=38,
        frozen_public_source_files=len(frozen["after_sha256"]),
        source_manifest_sha256=sha(output / "frozen-sources.json"),
        component_receipt=str(component),
        component_receipt_sha256=sha(component),
        collected_tests=8,
        preflight_tests=2,
        preflight_receipts=receipts,
        pending_phases=pending,
        resource_guards=guards,
        exact_established_driver_functions=list(reused),
        exact_established_public_helpers=["merge_windows", "save_trace", "scalar_run"],
        integrated_dispatch_sha256=frozen["integrated_working_dispatch_sha256"],
        physical_inputs_sha256=hashes(output / "inputs"),
        independent_references_sha256=hashes(output / "references"),
        runtime_source_identity=read(output / "public_identity.json"),
        oracle_independence=oracle["independence_guards"],
        standalone_oracle_runtime=oracle["execution"],
        compiled_jobs_launched=0,
        gpu_executed=False,
        shared_source_edits=False,
        dispatch_patch_applied=False,
        automatic_followup=False,
        prepared_launch_command=[
            "taskset",
            "-c",
            "7",
            "/mnt/workspaces/Cells/venv-cpu/bin/python",
            "-B",
            str(output / "snapshot" / DRIVER),
            "--output",
            str(output),
            "--phase",
            "launch",
        ],
        launch_command_executed=False,
        qualification_scope="Public contracts and clean independent oracle passed; "
        "offline planning, compiled trajectories and fresh restores pending",
    )
    result["artifact_sha256"] = hashes(output)
    (output / "preparation-result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                status="prepared",
                receipt=str(output / "preparation-result.json"),
                sha256=sha(output / "preparation-result.json"),
                preflight_tests=2,
                compiled_jobs_launched=0,
            )
        )
    )


if __name__ == "__main__":
    main()
