"""Verify complete active scheduling evidence and freeze the current Root proposal."""

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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    component, output = args.component.resolve(), args.output.resolve()
    assert component.parent == output.parent == Path("/mnt/workspaces/Cells")
    assert output.name.startswith("active-membrane-profiles-handoff-")
    report, inputs = (read(component / name) for name in ("result.json", "inputs.json"))
    assert report["status"] == "passed" and report["error"] is None
    assert report["tests"] == dict(tests=35, errors=0, failures=0, skipped=0)
    assert (
        not report["sources_changed_during_checks"]
        and not report["workspace_sources_changed_during_checks"]
    )
    assert [v["name"] for v in report["checks"]] == [
        "imports",
        "format",
        "lint",
        "host",
        "jax-eager",
        "public",
    ]
    assert all(v["exit_code"] == 0 for v in report["checks"])
    for relative, expected in report["output_sha256"].items():
        assert sha(component / relative) == expected, relative
    for relative, expected in report["source_sha256"].items():
        assert sha(ROOT / relative) == expected, relative
    protocol = read(ROOT / "validation/topology/surface_active_profile_interventions_protocol.json")
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
    assert not workspace["shared_files_written"] and not workspace["current_shared_engine_used"]
    assert len(workspace["overlay_source_sha256"]) == 2
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
    current_patch = WORK / "surface_active_profile_interventions_integration.patch"
    current = read(WORK / "surface_active_profile_interventions_integration.json")
    assert sha(current_patch) == current["patch_sha256"]
    for relative, row in current["files"].items():
        assert sha(ROOT / relative) == row["base_sha256"], relative
    subprocess.run(
        ["git", "apply", "--check", str(current_patch)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert inputs["affinity"] == [7] and inputs["environment"]["CUDA_VISIBLE_DEVICES"] == ""
    assert inputs["environment"]["JAX_ENABLE_COMPILATION_CACHE"] == "false"
    guards = {}
    for name in ("host", "jax-eager", "public"):
        guard = read(component / (name + "-guard/result.json"))
        assert guard["status"] == "completed"
        assert guard["sampled_peak_process_tree_rss_bytes"] <= 2**30
        assert guard["minimum_available_host_memory_bytes"] >= 8 * 2**30
        check = next(v for v in report["checks"] if v["name"] == name)
        assert check["JAX_DISABLE_JIT"] == "true" and check["wall_seconds"] < 480
        guards[name] = guard
    evidence, records, stages = {}, {}, []
    for path in sorted((component / "evidence").glob("*.json")):
        value = read(path)
        assert value["status"] == "passed"
        evidence[path.name] = dict(path=str(path), sha256=sha(path))
        records[path.stem.removeprefix("active-profiles-")] = value
        stages.extend(value.get("stages", []))
    assert len(evidence) == 35 and len(stages) == 56
    assert all(v["error_over_budget"] <= 1 for v in stages)
    closure = records["closure-proof"]
    assert len(closure["comparisons"]) == 4
    assert all(v["error_over_budget"] <= 1 for v in closure["comparisons"])
    for key in (
        "unmodified_vs_projected_physics_bitwise",
        "all_actual_observed_history_exact",
        "actual_material_failure_refused",
        "input_state_unmodified",
        "closed_and_reopened",
    ):
        assert closure[key]
    assert closure["all_parent_numeric_leaf_comparisons"] >= 4 * 19
    graph = records["call-graph"]
    assert graph["projected_integral_only_reaches_fixed_route_validity"]
    assert graph["physical_amounts_charge_fields_fluxes_all_derivatives_unaffected"]
    assert graph["actual_history_drives_conservation_and_observations"]
    for case in (
        "SIM",
        "INIT",
        "ion-flags",
        "safe-negative",
        "close-reopen",
        "empty-events",
        "reordered",
    ):
        value = records["all-laws-" + case]
        assert value["law_count"] == 56 and value["parent_state_and_layout_exact"]
        assert value["actual_gates_and_pumps_retained"]
    for case in ("SIM", "close-reopen"):
        trajectory = records["trajectory-" + case]
        assert (
            trajectory["all_20_state_fields_compared"]
            and trajectory["maintained_fuel_and_actual_history"]
        )
        assert all(v["error_over_budget"] <= 1 for v in trajectory["refinements"])
    cpu, public = records["cpu-jax-eager"], records["public-replay"]
    assert (
        cpu["all_56_laws_and_20_fields"]
        and cpu["full_rhs_parity"]
        and cpu["JAX_trace_preserves_state_types"]
    )
    assert cpu["pulse_time_derivative"] != 0 and not cpu["compiled_trajectory"]
    assert (
        public["all_56_laws"]
        and public["all_actual_history_observed"]
        and public["snapshot_resume_exact"]
    )
    assert public["actual_gates_pumps_metabolic_work"] and not public["compiled_trajectory"]
    recipe = records["recipe-replay"]
    artifact = recipe["artifact"]
    unsealed = dict(artifact)
    seal = unsealed.pop("identity")
    assert identity(unsealed) == seal
    assert identity(recipe["inputs"]) == identity(artifact["definition"])
    output.mkdir(exist_ok=False)
    examples = {}
    for case in ("SIM", "INIT", "close-reopen", "ion-flags"):
        value = records["all-laws-" + case]
        folder = output / "examples" / case
        folder.mkdir(parents=True)
        write(folder / "definition.json", value["inputs"])
        if case == "SIM":
            write(folder / "artifact.json", artifact)
        examples[case] = dict(
            path=str(folder), files_sha256={p.name: sha(p) for p in sorted(folder.iterdir())}
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
        (WORK / "SURFACE_ACTIVE_PROFILE_INTERVENTIONS_HANDOFF.md", "HANDOFF.md"),
        (
            ROOT / "validation/topology/surface_active_profile_interventions_protocol.json",
            "protocol.json",
        ),
        (current_patch, "proposed-current-integration.patch"),
        (
            WORK / "surface_active_profile_interventions_integration.json",
            "proposed-current-integration.json",
        ),
        (ROOT / protocol["test_dispatch_patch"], "isolated-test-dispatch.patch"),
        (ROOT / protocol["test_dispatch_metadata"], "isolated-test-dispatch.json"),
        (Path(__file__), "finalize.py"),
    ):
        shutil.copyfile(source, output / name)
    result = dict(
        status="passed",
        model_id=protocol["model_id"],
        parent_model_id=protocol["parent_model_id"],
        tests=report["tests"],
        component_receipt=str(component / "result.json"),
        component_receipt_sha256=sha(component / "result.json"),
        verified_component_artifact_count=len(report["output_sha256"]),
        source_sha256=report["source_sha256"],
        readonly_source_sha256=protocol["readonly_source_sha256"],
        frozen_engine=frozen,
        workspace_manifest_sha256=sha(manifest_path),
        independent_full_field_rhs_stages=60,
        all_channel_laws=56,
        full_state_fields=20,
        maximum_rhs_error_over_budget=max(
            v["error_over_budget"] for v in stages + closure["comparisons"]
        ),
        history_projection_call_graph=graph,
        closure_and_reopening=closure,
        short_refinement={case: records["trajectory-" + case] for case in ("SIM", "close-reopen")},
        CPU_JAX_eager=cpu,
        public_eager_replay={k: v for k, v in public.items() if k not in ("inputs", "artifact")},
        resources=guards,
        evidence=evidence,
        examples=examples,
        native_source_sha256=native_sources,
        current_integration_proposal=current,
        current_patch_applies_cleanly_at_freeze=True,
        captured_test_and_original_proposal_preserved=True,
        shared_integration_owner="Cells Chief Developer",
        shared_source_edits=False,
        frozen_passive_epoch_parent_edits=False,
        conservation_tolerances_relaxed=False,
        actual_history_modified=False,
        existing_component_suites_rerun=False,
        compiled_active_rhs_qualified=False,
        compiled_trajectory_qualified=False,
        native_solver_loop_parity_qualified=False,
        calcium_finite_fuel_water_compositions_qualified=False,
        physical_remap_qualified=False,
        gpu_executed=False,
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
