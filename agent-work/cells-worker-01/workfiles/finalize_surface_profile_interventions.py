"""Verify frozen scheduled-profile evidence and export complete model examples."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / "agent-work/cells-worker-01/workfiles"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    component, output = args.component.resolve(), args.output.resolve()
    assert component.parent == output.parent == Path("/mnt/workspaces/Cells")
    assert output.name.startswith("scheduled-membrane-profiles-handoff-")
    report, inputs = (read(component / name) for name in ("result.json", "inputs.json"))
    assert report["status"] == "passed" and report["error"] is None
    assert report["tests"] == dict(tests=36, errors=0, failures=0, skipped=0)
    assert not report["sources_changed_during_checks"]
    assert not report["workspace_sources_changed_during_checks"]
    assert [v["name"] for v in report["checks"]] == [
        "imports",
        "format",
        "lint",
        "host",
        "jax-rhs",
        "public",
    ]
    assert all(v["exit_code"] == 0 for v in report["checks"])
    for relative, expected in report["output_sha256"].items():
        assert sha(component / relative) == expected, relative
    for relative, expected in report["source_sha256"].items():
        assert sha(ROOT / relative) == expected, relative
    protocol = read(ROOT / "validation/topology/surface_profile_interventions_protocol.json")
    for relative, expected in protocol["readonly_source_sha256"].items():
        assert sha(ROOT / relative) == expected, relative
    for receipt in protocol["component_receipts"].values():
        assert sha(Path(receipt["path"])) == receipt["sha256"]
        assert read(Path(receipt["path"]))["status"] == "passed"
    native_scope = protocol["native_phase_scope"]
    assert sha(Path(native_scope["path"])) == native_scope["sha256"]
    manifest_path = component / "workspace-manifest.json"
    assert sha(manifest_path) == report["workspace_manifest_sha256"]
    workspace = read(manifest_path)
    assert workspace["status"] == "frozen" and not workspace["shared_files_written"]
    assert set(workspace["only_metadata_dispatch_changed"]) == {
        "src/cells/core/specs.py",
        "src/cells/models/registry.py",
    }
    dispatch = inputs["test_dispatch"]
    assert sha(ROOT / protocol["test_dispatch_patch"]) == dispatch["patch_sha256"]
    for relative, expected in workspace["patched_sha256"].items():
        assert sha(component / "workspace" / relative) == expected, relative
        if relative in dispatch["files"]:
            assert expected == dispatch["files"][relative]["patched_sha256"]
        else:
            assert expected == workspace["base_sha256"][relative], relative
    assert inputs["affinity"] == [7]
    assert inputs["environment"]["CUDA_VISIBLE_DEVICES"] == ""
    assert inputs["environment"]["JAX_ENABLE_COMPILATION_CACHE"] == "false"
    guards = {}
    for name, disabled in (("host", "true"), ("jax-rhs", "false"), ("public", "true")):
        guard = read(component / (name + "-guard/result.json"))
        assert guard["status"] == "completed"
        assert guard["sampled_peak_process_tree_rss_bytes"] <= 2**30
        assert guard["minimum_available_host_memory_bytes"] >= 8 * 2**30
        command = next(v for v in report["checks"] if v["name"] == name)
        assert command["JAX_DISABLE_JIT"] == disabled and command["wall_seconds"] < 480
        guards[name] = guard
    evidence, stages, records = {}, [], {}
    for p in sorted((component / "evidence").glob("*.json")):
        value = read(p)
        assert value["status"] == "passed"
        evidence[p.name] = dict(path=str(p), sha256=sha(p))
        records[p.stem.removeprefix("scheduled-profiles-")] = value
        stages.extend(value.get("comparisons", []))
    assert len(evidence) == 36 and len(stages) == 48
    assert max(v["max_error_over_budget"] for v in stages) <= 1
    joined = records["joined-source"]
    assert joined["full_geometry_profile_chain_retained"]
    assert joined["independent_error_over_budget"] <= 1
    clock = records["clock-subtraction-boundary"]
    assert clock["dt_s"] == 1.25e-7 and clock["transition_time_s"] == 1e-6
    assert clock["max_nominal_step_s"] > clock["dt_s"]
    assert clock["physical_times_unchanged"]
    assert len(clock["nominal_refusals"]) == 2
    for value in clock["nominal_refusals"]:
        assert value["valid_nominal_baseline_passed"] and value["oversized_nominal_refused"]
        assert value["declared_dt_s"] == 2 * clock["dt_s"]
    assert clock["nominal_refusals"][-1]["horizon_s"] == 1e9
    assert clock["nominal_refusals"][-1]["clock_allowance_s"] > clock["dt_s"]
    compiled = records["cpu-jax-rhs"]
    assert compiled["full_rhs_parity"] and compiled["invalid_world_isolated"]
    assert compiled["scheduled_Dm_time_derivative"] != 0
    public = records["public-replay"]
    assert public["snapshot_resume_exact"] and public["phase_change_branch_refused"]
    assert public["steps"] == 4 and not public["compiled_trajectory"]
    trajectory = records["short-trajectory"]
    assert trajectory["duration_s"] == 1e-5
    assert len(trajectory["refinements"]) == 2
    assert all(v["error_over_budget"] <= 1 for v in trajectory["refinements"])
    history = {}
    for suffix in ("01", "02"):
        path = component.parent / ("scheduled-membrane-profiles-development-20261029-" + suffix)
        receipt = path / "result.json"
        previous = read(receipt)
        history[suffix] = dict(path=str(receipt), sha256=sha(receipt), status=previous["status"])
    assert history["01"]["status"] == "failed" and history["02"]["status"] == "passed"
    output.mkdir(exist_ok=False)
    examples = {}
    for name, value in (
        ("direct-four-ion", records["recipe-replay"]),
        ("geometry-profiles", joined),
    ):
        raw, artifact = value["inputs"], value["artifact"]
        sealed = dict(artifact)
        seal = sealed.pop("identity")
        assert identity(sealed) == seal
        assert identity(artifact["definition"]) == identity(raw)
        assert raw["model"]["id"] == protocol["model_id"]
        folder = output / "examples" / name
        folder.mkdir(parents=True)
        write(folder / "definition.json", artifact["definition"])
        write(folder / "artifact.json", artifact)
        examples[name] = dict(
            path=str(folder),
            artifact_identity=artifact["identity"],
            files_sha256={p.name: sha(p) for p in sorted(folder.iterdir())},
        )
    for source, name in (
        (WORK / "SURFACE_PROFILE_INTERVENTIONS_HANDOFF.md", "HANDOFF.md"),
        (ROOT / "validation/topology/surface_profile_interventions_protocol.json", "protocol.json"),
        (ROOT / protocol["test_dispatch_patch"], "test-dispatch.patch"),
        (ROOT / protocol["test_dispatch_metadata"], "test-dispatch.json"),
        (Path(__file__), "finalize.py"),
    ):
        shutil.copyfile(source, output / name)
    result = dict(
        status="passed",
        model_id=protocol["model_id"],
        timing_policy=protocol["timing_policy"],
        reset_policy=protocol["reset_policy"],
        tests=report["tests"],
        component_receipt=str(component / "result.json"),
        component_receipt_sha256=sha(component / "result.json"),
        verified_component_artifact_count=len(report["output_sha256"]),
        source_sha256=report["source_sha256"],
        readonly_source_sha256=protocol["readonly_source_sha256"],
        component_receipts=protocol["component_receipts"],
        workspace_manifest_sha256=sha(manifest_path),
        isolated_test_dispatch=dispatch,
        independent_full_field_rhs_stages=len(stages) + 1,
        maximum_rhs_error_over_budget=max(
            *(v["max_error_over_budget"] for v in stages), joined["independent_error_over_budget"]
        ),
        nominal_and_clock_roundoff=clock,
        short_numpy_trajectory=trajectory,
        compiled_cpu_jax_rhs=compiled,
        public_eager_replay=public,
        resources=guards,
        evidence=evidence,
        examples=examples,
        prior_attempts_preserved=history,
        native_phase_scope=native_scope,
        shared_source_edits=False,
        shared_and_ensemble_integration_owner="Cells Chief Developer",
        existing_component_suites_rerun=False,
        gpu_executed=False,
        native_generation_executed=False,
        compiled_trajectory_qualified=False,
        physical_remap_qualified=False,
        full_native_simulator_qualified=False,
        long_jobs_launched=False,
        detached_jobs_polled=False,
        automatic_followup=False,
    )
    result["handoff_artifact_sha256"] = {
        str(p.relative_to(output)): sha(p) for p in sorted(output.rglob("*")) if p.is_file()
    }
    write(output / "result.json", result)
    print(
        json.dumps(
            dict(
                status="passed",
                receipt=str(output / "result.json"),
                sha256=sha(output / "result.json"),
            )
        )
    )


if __name__ == "__main__":
    main()
