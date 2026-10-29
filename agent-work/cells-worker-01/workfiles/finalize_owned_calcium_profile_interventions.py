"""Freeze 44 actual passes, preserving the duplicate-selection failed summary."""

import argparse
import ast
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
STEM = "owned_calcium_profile_interventions"
DRIVER = "agent-work/cells-worker-01/workfiles/check_" + STEM + ".py"
RUNTIME = (
    "src/cells/core/owned_calcium_profile_binding.py",
    "src/cells/core/surface_calcium_profile_interventions_spec.py",
    "src/cells/core/surface_calcium_energy_profile_interventions_spec.py",
    "src/cells/models/surface_calcium_profile_interventions.py",
    "src/cells/models/surface_calcium_energy_profile_interventions.py",
)
FAMILIES = ("calcium6", "fuel5")


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


def matches(expression, nodeid):
    """Evaluate the identifier/and/or/not subset used by these pytest selectors."""

    def value(node):
        if isinstance(node, ast.Expression):
            return value(node.body)
        if isinstance(node, ast.Name):
            return node.id.casefold() in nodeid.casefold()
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not value(node.operand)
        if isinstance(node, ast.BoolOp):
            operation = all if isinstance(node.op, ast.And) else any
            assert isinstance(node.op, (ast.And, ast.Or))
            return operation(value(v) for v in node.values)
        raise AssertionError(ast.dump(node))

    return value(ast.parse(expression, mode="eval"))


def reconcile(component, report, inputs):
    assert report["status"] == "failed" and report["error"] is None
    assert report["tests"] == dict(tests=46, errors=0, failures=0, skipped=2)
    assert not report["sources_changed_during_checks"]
    assert not report["workspace_sources_changed_during_checks"]
    assert all(r["exit_code"] == 0 for r in report["checks"])
    assert len(report["checks"]) == 14
    nodes = defaultdict(list)
    for path in sorted(component.glob("*-tests.xml")):
        phase = path.name.removesuffix("-tests.xml")
        for case in ET.parse(path).getroot().iter("testcase"):
            assert case.find("failure") is None and case.find("error") is None
            skipped = case.find("skipped")
            nodeid = case.attrib["classname"] + "::" + case.attrib["name"]
            nodes[nodeid].append(
                dict(
                    phase=phase,
                    status="passed" if skipped is None else "skipped",
                    skip_reason=None if skipped is None else skipped.attrib.get("message"),
                    junit=str(path),
                    junit_sha256=sha(path),
                )
            )
    assert len(nodes) == 44
    duplicates = {key: rows for key, rows in nodes.items() if len(rows) > 1}
    assert len(duplicates) == 2
    for nodeid, rows in nodes.items():
        passed = [r for r in rows if r["status"] == "passed"]
        assert len(passed) == 1, nodeid
        if "public_short" in nodeid:
            family = "calcium" if "calcium6" in nodeid else "fuel"
            assert [r["phase"] for r in passed] == ["public-" + family]
            skipped = [r for r in rows if r["status"] == "skipped"]
            assert len(skipped) == 1 and skipped[0]["phase"] == "host-" + family + "-closure"
            assert skipped[0]["skip_reason"] == "separate bounded public process"
        else:
            assert len(rows) == 1
            assert passed[0]["phase"].startswith("jax" if "cpu_jax" in nodeid else "host")
    # Fixing a phase selector must cover exactly the same 44 genuinely passed
    # identities once each. No new numerical execution or tolerance is involved.
    future = {}
    for row in inputs["commands"]:
        if "-k" not in row["argv"]:
            continue
        expression = row["argv"][row["argv"].index("-k") + 1]
        if row["name"].startswith("host"):
            expression = "(not cpu_jax and not public_short) and (" + expression + ")"
        future[row["name"]] = dict(
            expression=expression, checks=[n for n in nodes if matches(expression, n)]
        )
    assert all(v["checks"] for v in future.values())
    assert all(sum(n in v["checks"] for v in future.values()) == 1 for n in nodes)
    assert sum(len(v["checks"]) for v in future.values()) == 44
    return dict(
        unique_tests=44,
        passed=44,
        errors=0,
        failures=0,
        raw_collected=46,
        duplicate_skips=duplicates,
        checks=dict(nodes),
        corrected_future_selectors=future,
        future_coverage_exactly_once=True,
        numerical_checks_rerun=False,
        raw_failed_receipt_preserved=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    component, output = args.component.resolve(), args.output.resolve()
    assert component.parent == output.parent == Path("/mnt/workspaces/Cells")
    assert output.name.startswith("owned-calcium-profiles-handoff-")
    report, inputs = (read(component / n) for n in ("result.json", "inputs.json"))
    for name, expected in report["output_sha256"].items():
        assert sha(component / name) == expected, name
    assert read(component / "failure.json") == report
    reconciliation = reconcile(component, report, inputs)
    correction = read(WORK / (STEM + "_runner_phase_fix.json"))
    old = (component / "sources" / DRIVER).read_text()
    needle = "    for name, selection in phases:\n"
    insertion = (
        '        if name.startswith("host"):\n'
        '            selection = f"({ordinary}) and ({selection})"\n'
    )
    assert old.count(needle) == 1
    assert (ROOT / DRIVER).read_text() == old.replace(needle, needle + insertion)
    assert sha(ROOT / DRIVER) == correction["corrected_sha256"]
    assert sha(component / "sources" / DRIVER) == correction["base_sha256"]
    assert sha(WORK / (STEM + "_runner_phase_fix.patch")) == correction["patch_sha256"]
    for name, expected in report["source_sha256"].items():
        assert sha(component / "sources" / name) == expected, name
        if name != DRIVER:
            assert sha(ROOT / name) == expected, name
    protocol_path = ROOT / ("validation/topology/" + STEM + "_protocol.json")
    protocol = read(protocol_path)
    assert "validation/betse/contact.py" in protocol["readonly_source_sha256"]
    for name, expected in protocol["readonly_source_sha256"].items():
        assert sha(ROOT / name) == expected, name
    frozen = protocol["frozen_workspace"]
    for p, s in (("manifest", "manifest_sha256"), ("handoff_receipt", "handoff_receipt_sha256")):
        assert sha(Path(frozen[p])) == frozen[s]
    assert read(Path(frozen["handoff_receipt"]))["status"] == "passed"
    workspace_path = component / "workspace-manifest.json"
    assert sha(workspace_path) == report["workspace_manifest_sha256"]
    workspace = read(workspace_path)
    assert not workspace["shared_files_written"] and not workspace["current_shared_engine_used"]
    assert set(workspace["overlay_source_sha256"]) == set(RUNTIME)
    assert set(workspace["only_test_dispatch_changed"]) == {
        "src/cells/core/specs.py",
        "src/cells/models/registry.py",
        "src/cells/ensemble/ionic.py",
    }
    for name, expected in workspace["source_sha256"].items():
        assert sha(component / "workspace" / name) == expected, name
        if name in RUNTIME:
            assert expected == sha(ROOT / name) == workspace["overlay_source_sha256"][name]
        elif name not in workspace["only_test_dispatch_changed"]:
            assert expected == workspace["qualified_base_source_sha256"][name], name
    assert inputs["affinity"] == [7]
    for key, expected in {
        "CUDA_VISIBLE_DEVICES": "",
        "JAX_ENABLE_COMPILATION_CACHE": "false",
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
    }.items():
        assert inputs["environment"][key] == expected
    guards = {}
    for row in report["checks"]:
        guard = read(component / (row["name"] + "-guard/result.json"))
        assert guard["status"] == "completed" and guard["returncode"] == 0
        assert guard["sampled_peak_process_tree_rss_bytes"] <= 2**30
        assert guard["minimum_available_host_memory_bytes"] >= 8 * 2**30
        assert row["JAX_DISABLE_JIT"] == "true" and row["wall_seconds"] < 480
        guards[row["name"]] = guard
    records, evidence, stages = {}, {}, []
    for path in sorted((component / "evidence").glob("*.json")):
        value = read(path)
        assert value["status"] == "passed"
        key = path.stem.removeprefix("owned-calcium-profiles-")
        records[key] = value
        evidence[key] = dict(path=str(path), sha256=sha(path))
        stages.extend(value.get("stages", []))
    assert len(records) == 44 and len(stages) == 50
    for family in FAMILIES:
        count = 35 if family == "calcium6" else 39
        laws = 18 if family == "calcium6" else 56
        for case in ("SIM", "INIT", "close-reopen", "ion-flags", "empty-events"):
            value = records["stages-" + family + "-" + case]
            assert value["exact_initial_parent_state"] and value["exact_parent_layout"]
            assert value["all_chemical_and_fuel_fields"]
            assert len(value["stages"]) == 5
            assert all(len(r["full_state_fields"]) == count for r in value["stages"])
            channels = value["inputs"]["model"]["ionic"]["channels"]
            assert len({c["kinetic_law"] for c in channels}) == laws
        for case in ("SIM", "close-reopen"):
            value = records["trajectory-" + family + "-" + case]
            assert value["duration_s"] == 4e-6 and len(value["refinements"]) == 2
            assert value["complete_chemical_gate_fuel_history_compared"]
            assert not value["convergence_order_claim"]
            assert value["refinement_mode"] == "within_precision_floor"
            assert all(v["error_over_budget"] <= 1 for v in value["refinements"])
        closure = records["closure-" + family]
        assert len(closure["comparisons"]) == 4
        assert closure["numeric_parent_leaf_comparisons"] >= 4 * count
        for key in (
            "full_physics_projection_bitwise",
            "all_actual_observed_fields_exact",
            "actual_global_conservation_used",
            "corrupt_closed_history_refused",
        ):
            assert closure[key]
        stages.extend(closure["comparisons"])
        cpu, public = records["cpu-jax-eager-" + family], records["public-replay-" + family]
        assert cpu["full_rhs_parity"] and cpu["actual_store_and_fuel_owner"]
        assert cpu["abstract_trace_preserves_full_state"] and cpu["pulse_time_derivative"] != 0
        assert len(cpu["fields"]) == count and not cpu["compiled_trajectory"]
        for key in (
            "snapshot_resume_exact",
            "all_actual_states_observed",
            "actual_chemical_and_fuel_owner_evolves",
            "phase_branch_refused",
            "checkpoint_clock_reset_refused",
        ):
            assert public[key]
        assert public["steps"] == 2 and not public["compiled_trajectory"]
        recipe = records["recipe-" + family]
        artifact = dict(recipe["artifact"])
        seal = artifact.pop("identity")
        assert identity(artifact) == seal
        assert identity(artifact["definition"]) == identity(recipe["inputs"])
    assert len(stages) == 58 and all(v["error_over_budget"] <= 1 for v in stages)
    live = records["live-fuel"]
    for key in (
        "all_three_pumps_actual_stage_ATP_ADP_Pi",
        "finite_pool_changes",
        "exhaustion_refused",
        "unrecorded_pool_change_refused",
    ):
        assert live[key]
    # Chief's interface receipt is read once and copied; do not poll its separate
    # execution job or require that unrelated mutable receipt to stay unchanged.
    public_path = Path(
        "/mnt/workspaces/Cells/owned-calcium-profile-integration-20261029-01/result.json"
    )
    public_bytes = public_path.read_bytes()
    public_root = json.loads(public_bytes)
    assert public_root["public_checks"] == 61
    for name in RUNTIME:
        assert public_root["current_runtime_sha256"][name] == sha(ROOT / name)
    for key in ("inputs", "junit", "terminal"):
        row = public_root[key]
        assert sha(Path(row["path"])) == row["sha256"]
    output.mkdir(exist_ok=False)
    write(output / "check-reconciliation.json", reconciliation)
    write(output / "runner-correction.json", correction)
    (output / "chief-public-interface-receipt.json").write_bytes(public_bytes)
    examples = {}
    for family in FAMILIES:
        examples[family] = {}
        for case in ("SIM", "INIT", "close-reopen", "ion-flags", "empty-events"):
            folder = output / "examples" / family / case
            folder.mkdir(parents=True)
            write(folder / "definition.json", records["stages-" + family + "-" + case]["inputs"])
            if case == "SIM":
                write(folder / "artifact.json", records["recipe-" + family]["artifact"])
            examples[family][case] = {p.name: sha(p) for p in sorted(folder.iterdir())}
    for row in protocol["native_phase_scope"]:
        source = Path(row["path"])
        assert sha(source) == row["sha256"]
        target = output / "native-source" / source.name
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(source, target)
    for source, name in (
        (WORK / "OWNED_CALCIUM_PROFILE_INTERVENTIONS_HANDOFF.md", "HANDOFF.md"),
        (protocol_path, "protocol.json"),
        (component / "result.json", "raw-component-result.json"),
        (component / "failure.json", "raw-component-failure.json"),
        (component / "sources" / DRIVER, "captured-qualification-driver.py"),
        (ROOT / DRIVER, "corrected-future-driver.py"),
        (WORK / (STEM + "_runner_phase_fix.patch"), "runner-phase-fix.patch"),
        (ROOT / protocol["test_dispatch_patch"], "isolated-test-dispatch.patch"),
        (ROOT / protocol["test_dispatch_metadata"], "isolated-test-dispatch.json"),
        (Path(__file__), "finalize.py"),
    ):
        shutil.copyfile(source, output / name)
    result = dict(
        status="passed",
        supported_owners=protocol["supported_owners"],
        tests=dict(unique=44, passed=44, errors=0, failures=0),
        raw_component=dict(
            path=str(component / "result.json"),
            sha256=sha(component / "result.json"),
            status=report["status"],
            counts=report["tests"],
        ),
        check_reconciliation=dict(
            path=str(output / "check-reconciliation.json"),
            sha256=sha(output / "check-reconciliation.json"),
        ),
        verified_component_artifact_count=len(report["output_sha256"]),
        captured_source_sha256=report["source_sha256"],
        readonly_source_sha256=protocol["readonly_source_sha256"],
        frozen_engine=frozen,
        runtime_sha256={p: sha(ROOT / p) for p in RUNTIME},
        workspace_manifest_sha256=sha(workspace_path),
        future_runner_correction=correction,
        independent_full_field_rhs_stages=58,
        maximum_rhs_error_over_budget=max(v["error_over_budget"] for v in stages),
        numeric_parent_leaf_bitwise_comparisons=sum(
            records["closure-" + f]["numeric_parent_leaf_comparisons"] for f in FAMILIES
        ),
        closure_and_reopening={f: records["closure-" + f] for f in FAMILIES},
        short_refinement={
            f: {c: records["trajectory-" + f + "-" + c] for c in ("SIM", "close-reopen")}
            for f in FAMILIES
        },
        live_fuel=live,
        resources=guards,
        evidence=evidence,
        examples=examples,
        chief_public_interfaces=dict(
            original_path=str(public_path),
            frozen_copy=str(output / "chief-public-interface-receipt.json"),
            sha256=sha(output / "chief-public-interface-receipt.json"),
            checks=61,
            separate_execution_job_polled=False,
        ),
        shared_source_edits=False,
        physical_parent_or_frozen_runtime_edits=False,
        scientific_sources_unchanged=True,
        actual_history_modified=False,
        conservation_tolerances_relaxed=False,
        followup_numerical_jobs_launched=False,
        compiled_coupled_rhs_qualified=False,
        compiled_trajectory_qualified=False,
        convergence_order_claim=False,
        native_full_solver_parity_qualified=False,
        other_compositions_cuts_or_phase_transitions_qualified=False,
        gpu_executed=False,
        detached_jobs_polled_repeatedly=False,
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
