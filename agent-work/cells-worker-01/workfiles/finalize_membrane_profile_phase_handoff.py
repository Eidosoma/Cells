"""Freeze verified INIT/SIM evidence, exact portable recipes and integration patch."""

import argparse
import hashlib
import json
import shutil
import subprocess
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


def leaves(value):
    if isinstance(value, list):
        for item in value:
            yield from leaves(item)
    else:
        yield value


def verify_recipe(value):
    request, definition, provenance = (value[k] for k in ("request", "definition", "provenance"))
    unsealed = dict(provenance)
    seal = unsealed.pop("identity")
    assert identity(unsealed) == seal
    assert identity(request) == identity(provenance["request"])
    assert identity(definition) == provenance["prepared_definition_sha256"]
    source = dict(request["source"])
    source_seal = source.pop("identity")
    assert identity(source) == source_seal == provenance["source_identity"]
    record = definition["model"]["handoff"]
    assert identity(record["source"]) == identity(request["source"])
    assert identity(record["clocks"]) == identity(provenance["clocks"])
    assert record["clocks"]["init_checkpoint_time_s"] == source["checkpoint"]["time"]
    assert (
        record["clocks"]["init_phase_clock_s"]
        == source["checkpoint"]["state"]["phase_clock_s"]["values"][0]
    )
    assert record["clocks"]["sim_epoch_time_s"] == record["clocks"]["sim_phase_clock_s"] == 0.0
    assert all(v == 0.0 for v in leaves(record["buffer_reset"]["scheduled_buffer_m2_s"]))
    fields = provenance["preservation"]["carried_parent_fields"]
    assert len(fields) == 12 and "phase_clock_s" not in fields
    state = {k: source["checkpoint"]["state"][k] for k in fields}
    assert identity(state) == provenance["preservation"]["typed_parent_state_sha256"]
    target = dict(definition, model=definition["model"]["scheduled"])
    assert identity(target) == identity(request["simulation"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    component, output = args.component.resolve(), args.output.resolve()
    assert component.parent == output.parent == Path("/mnt/workspaces/Cells")
    assert output.name.startswith("membrane-phase-handoff-20")
    report, inputs = (read(component / name) for name in ("result.json", "inputs.json"))
    assert report["status"] == "passed" and report["error"] is None
    assert report["tests"]["tests"] >= 44
    assert all(report["tests"][k] == 0 for k in ("errors", "failures", "skipped"))
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
    protocol = read(ROOT / "validation/topology/membrane_profile_phase_handoff_protocol.json")
    for relative, expected in protocol["readonly_source_sha256"].items():
        assert sha(ROOT / relative) == expected, relative
    frozen = protocol["frozen_workspace"]
    for path_key, sha_key in (
        ("manifest", "manifest_sha256"),
        ("component_receipt", "component_receipt_sha256"),
        ("handoff_receipt", "handoff_receipt_sha256"),
    ):
        assert sha(Path(frozen[path_key])) == frozen[sha_key]
    assert read(Path(frozen["component_receipt"]))["status"] == "passed"
    assert read(Path(frozen["handoff_receipt"]))["status"] == "passed"
    manifest_path = component / "workspace-manifest.json"
    assert sha(manifest_path) == report["workspace_manifest_sha256"]
    workspace = read(manifest_path)
    assert workspace["status"] == "frozen" and not workspace["shared_files_written"]
    assert not workspace["current_shared_engine_used"]
    assert set(workspace["only_test_dispatch_changed"]) == {
        "src/cells/core/specs.py",
        "src/cells/models/registry.py",
    }
    for relative, expected in workspace["source_sha256"].items():
        assert sha(component / "workspace" / relative) == expected, relative
        if relative in workspace["overlay_source_sha256"]:
            assert expected == workspace["overlay_source_sha256"][relative]
        elif relative not in workspace["only_test_dispatch_changed"]:
            assert expected == workspace["qualified_base_source_sha256"][relative]
    assert len(workspace["overlay_source_sha256"]) == 3
    proposed_path = WORK / "membrane_profile_phase_handoff_dispatch.patch"
    proposed = read(WORK / "membrane_profile_phase_handoff_dispatch.json")
    assert sha(proposed_path) == proposed["patch_sha256"]
    for relative, row in proposed["files"].items():
        assert sha(ROOT / relative) == row["base_sha256"], relative
    subprocess.run(
        ["git", "apply", "--check", str(proposed_path)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
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
    evidence, records, stages = {}, {}, []
    for path in sorted((component / "evidence").glob("*.json")):
        value = read(path)
        assert value["status"] == "passed"
        evidence[path.name] = dict(path=str(path), sha256=sha(path))
        records[path.stem.removeprefix("phase-handoff-")] = value
        stages.extend(value.get("stages", []))
    assert len(evidence) == report["tests"]["tests"]
    assert len(stages) == 32 and max(v["max_error_over_budget"] for v in stages) <= 1
    joined = records["joined-chain"]
    assert joined["complete_geometry_profile_chain_retained"]
    assert (
        joined["accepted_interior_INIT_checkpoint"] and joined["independent_error_over_budget"] <= 1
    )
    assert records["operation-boundary"]["resume_cannot_transition"]
    assert records["operation-boundary"]["branch_cannot_transition"]
    assert records["operation-boundary"]["initial_history_reset_refused"]
    assert records["portable-replay"]["external_source_reads_blocked"]
    trajectory = records["continued-trajectory"]
    assert trajectory["INIT_ledgers_retained_in_SIM"]
    assert all(v["error_over_budget"] <= 1 for v in trajectory["refinements"])
    compiled, public = records["cpu-jax"], records["public-replay"]
    assert compiled["full_rhs_parity"] and compiled["invalid_world_isolated"]
    assert public["snapshot_resume_exact"] and public["original_INIT_history_at_SIM_zero"]
    assert public["both_phase_clocks_observed"] and not public["compiled_trajectory"]
    for case in protocol["cases"]:
        value = records["preserved-" + case]
        assert value["physical_and_history_exact"] and value["original_origin_retained"]
        verify_recipe(value)
    output.mkdir(exist_ok=False)
    examples = {}
    for name, value in (
        ("direct-continued", records["preserved-continued-controls"]),
        ("changed-controls", records["preserved-changed-controls"]),
        ("joined-interior", joined),
        ("small-public", public),
    ):
        verify_recipe(value)
        folder = output / "examples" / name
        folder.mkdir(parents=True)
        for key in ("request", "definition", "provenance"):
            write(folder / (key + ".json"), value[key])
        examples[name] = dict(
            path=str(folder),
            provenance_identity=value["provenance"]["identity"],
            files_sha256={p.name: sha(p) for p in sorted(folder.iterdir())},
        )
    native_sources = {}
    for row in protocol["native_phase_scope"]:
        source = Path(row["path"])
        assert sha(source) == row["sha256"]
        target = output / "native-source" / source.name
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(source, target)
        native_sources[str(target.relative_to(output))] = sha(target)
    for source, name in (
        (WORK / "MEMBRANE_PROFILE_PHASE_HANDOFF.md", "HANDOFF.md"),
        (
            ROOT / "validation/topology/membrane_profile_phase_handoff_protocol.json",
            "protocol.json",
        ),
        (proposed_path, "proposed-shared-dispatch.patch"),
        (WORK / "membrane_profile_phase_handoff_dispatch.json", "proposed-shared-dispatch.json"),
        (ROOT / protocol["test_dispatch_patch"], "isolated-test-dispatch.patch"),
        (ROOT / protocol["test_dispatch_metadata"], "isolated-test-dispatch.json"),
        (Path(__file__), "finalize.py"),
    ):
        shutil.copyfile(source, output / name)
    result = dict(
        status="passed",
        model_id=protocol["model_id"],
        bridge_id=protocol["bridge_id"],
        tests=report["tests"],
        component_receipt=str(component / "result.json"),
        component_receipt_sha256=sha(component / "result.json"),
        verified_component_artifact_count=len(report["output_sha256"]),
        source_sha256=report["source_sha256"],
        readonly_source_sha256=protocol["readonly_source_sha256"],
        frozen_engine=frozen,
        workspace_manifest_sha256=sha(manifest_path),
        independent_SIM_full_field_rhs_stages=len(stages) + 1,
        maximum_SIM_rhs_error_over_budget=max(
            *(v["max_error_over_budget"] for v in stages), joined["independent_error_over_budget"]
        ),
        independent_INIT_checks={
            k: v for k, v in records.items() if k.startswith("INIT-reference-")
        },
        continuous_global_history_trajectory=trajectory,
        compiled_cpu_jax_rhs=compiled,
        public_eager_replay={
            k: v for k, v in public.items() if k not in ("request", "definition", "provenance")
        },
        resources=guards,
        evidence=evidence,
        examples=examples,
        native_source_sha256=native_sources,
        proposed_current_base_shared_patch=proposed,
        proposed_patch_applies_cleanly_at_freeze=True,
        shared_integration_owner="Cells Chief Developer",
        shared_source_edits=False,
        frozen_scheduled_model_edits=False,
        existing_component_suites_rerun=False,
        gpu_executed=False,
        native_generation_executed=False,
        compiled_trajectory_qualified=False,
        native_solver_loop_parity_qualified=False,
        profile_default_changes_qualified=False,
        physical_remap_qualified=False,
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
