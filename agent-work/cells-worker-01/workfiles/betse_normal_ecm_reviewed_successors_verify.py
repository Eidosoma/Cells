"""Verify copied successor bytes, declared deltas and held plans; no science imports."""

import ast
import builtins
import json
import subprocess
import symtable
from pathlib import Path

from betse_normal_ecm_reviewed_successors_resources import BASE, PACKETS, WORK, sha

PREFIX = "betse_normal_ecm_reviewed_successors"


def signature(node):
    return ast.dump(node, include_attributes=False)


def functions(path):
    return {n.name: n for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef)}


def compile_names(path):
    text = path.read_text()
    compile(text, str(path), "exec")
    table = symtable.symtable(text, str(path), "exec")
    known = set(table.get_identifiers()) | set(dir(builtins)) | {"__file__", "__name__"}

    def check(scope):
        missing = {
            s.get_name()
            for s in scope.get_symbols()
            if s.is_global() and s.is_referenced() and s.get_name() not in known
        }
        assert not missing, (str(path), missing)
        for child in scope.get_children():
            check(child)

    check(table)


def verify():
    preparation = WORK / (PREFIX + "_preparation_receipt_01.json")
    prepared = json.loads(preparation.read_text())
    result = {}
    selected_source_deltas = set()
    for role, item in prepared["inputs"].items():
        assert sha(item["path"]) == item["sha256"]
        out = Path(item["path"]).parent
        inputs = json.loads(Path(item["path"]).read_text())
        parent_name, prefix = PACKETS[role]
        parent = BASE / parent_name
        old = json.loads((parent / "inputs.json").read_text())
        assert sha(parent / "inputs.json") == inputs["prior_packet_inputs"]["sha256"]
        actual = {
            str(p.relative_to(out / "source")) for p in (out / "source").rglob("*") if p.is_file()
        }
        declared = set(inputs["source_hashes"])
        assert declared <= actual
        extras = actual - declared
        # Ruff created these cache bytes during final lint, after the immutable
        # source manifest was written. Preserve and explicitly bind them here;
        # no extra Python/data/config file is admitted into runtime authority.
        for relative in extras:
            parts = Path(relative).parts
            assert parts[0] == ".ruff_cache"
            assert (
                len(parts) == 2
                and parts[1] in {".gitignore", "CACHEDIR.TAG"}
                or len(parts) == 3
                and parts[1] == "0.16.6"
                and parts[2].isdigit()
            ), relative
            assert (out / "source" / relative).stat().st_size < 2**20
        lint_cache = {p: sha(out / "source" / p) for p in sorted(extras)}
        for relative, pin in inputs["source_hashes"].items():
            assert sha(out / "source" / relative) == pin, relative
        for group in (
            "native_snapshot_sha256",
            "qualification_helpers_sha256",
            "preparation_artifacts_sha256",
        ):
            for relative, pin in inputs[group].items():
                assert sha(out / relative) == pin, (group, relative)
        for item in inputs["binding_evidence"].values():
            assert sha(item["path"]) == item["sha256"], item["path"]
        controlled = inputs["owned_sha256"] | inputs["protected_sha256"]
        assert all(inputs["source_hashes"][p] == h for p, h in controlled.items())
        assert all(
            controlled.get(p) == h
            for p, h in (
                inputs["scientific_import_closure"]
                | inputs["reference_closure"]
                | inputs["resource_sha256"]
            ).items()
        )
        assert inputs["groups"] == old["groups"] and inputs["planned"] == old["planned"]
        assert inputs["required_reports"] == old["required_reports"]
        ids = [node for group in inputs["groups"].values() for node in group]
        assert len(ids) == len(set(ids)) == inputs["planned"]["checks"]
        assert not inputs["source_removed_paths"]
        expected = {
            "validation/frozen_resource_dependencies.py",
            "validation/betse/betse_normal_ecm_catalog_join_reference.py",
        }
        for _upstream, (_parent, upstream_prefix) in PACKETS.items():
            expected |= {
                "validation/betse/" + upstream_prefix + suffix
                for suffix in ("_protocol.json", "_source_map.json")
            }
            if _upstream == role:
                break
        if role != "catalog05":
            expected.add("validation/betse/betse_normal_ecm_event_join_reference.py")
        if role == "lifecycle02":
            expected |= {
                "tests/unit/test_betse_normal_ecm_run_lifecycle.py",
                "validation/betse/betse_normal_ecm_run_lifecycle_native.py",
            }
        assert set(inputs["source_delta_sha256"]) == expected
        assert all(
            old["source_hashes"].get(p) == h
            for p, h in inputs["source_hashes"].items()
            if p.startswith("src/")
        )
        for relative, pin in inputs["source_delta_sha256"].items():
            assert sha(out / "source" / relative) == pin
            if relative.endswith(".py"):
                path = out / "source" / relative
                compile_names(path)
                selected_source_deltas.add((relative, pin))
        protocol_path = "validation/betse/" + prefix + "_protocol.json"
        protocol = json.loads((out / "source" / protocol_path).read_text())
        previous = json.loads((parent / "source" / protocol_path).read_text())
        for key in (
            "acceptance",
            "tolerances",
            "mechanics_acceptance",
            "inherited_mechanics_divergence_category_disclosure",
        ):
            if key in previous:
                assert protocol[key] == previous[key], key
        resource = json.loads((out / "resource-audit.json").read_text())
        assert (
            resource["all_discovered_resources_present"]
            and resource["all_manual_read_sites_classified"]
        )
        assert not resource["manual_review"]["pending_manual_reads"]
        assert not resource["imported_module_and_literal_resource_audit"]["literal_resource_audit"][
            "missing_resources"
        ]
        assert resource["manual_review"]["resource_sha256"] == inputs["resource_sha256"]
        native_files = len(protocol["native_source"]["source_sha256"])
        assert inputs["native_source_copies"] == 2 * native_files
        before = (
            functions(WORK / (PREFIX + "_proposal_03/lifecycle-evidence-reader.py"))
            if role == "lifecycle02"
            else functions(parent / "driver.py")
        )
        after = functions(out / "driver.py")
        for name in before.keys() - {"prepare", "run"}:
            assert signature(before[name]) == signature(after[name]), name
        runner = ast.unparse(after["run"])
        assert runner.index("if inputs['execution_hold']:") < runner.index("target.mkdir(")
        assert "inputs['live_execution_sha256']" in runner
        assert "inputs['qualification_helpers_sha256']" in runner
        assert "timeout=480" in runner and "min_available_bytes=8 * 2 ** 30" in runner
        assert inputs["execution_hold"] is True and inputs["numerical_release_authorized"] is False
        assert inputs["numerical_runs"] == inputs["new_or_retained_qualification_passes"] == 0
        assert sha(out / "driver.py") == inputs["driver_sha256"]
        compile_names(out / "driver.py")
        check = subprocess.run(
            [
                "/mnt/workspaces/Cells/venv-cpu/bin/ruff",
                "format",
                "--check",
                str(out / "driver.py"),
            ],
            text=True,
            capture_output=True,
        )
        assert check.returncode == 0, check.stdout
        result[role] = dict(
            inputs=dict(path=str(out / "inputs.json"), sha256=sha(out / "inputs.json")),
            declared_source_files=len(declared),
            actual_source_tree_files=len(actual),
            additional_lint_cache_sha256=lint_cache,
            no_other_unmanifested_source_resource_or_config_files=True,
            source_delta_files=len(expected),
            native_source_copies=2 * native_files,
            all_native_and_binding_copy_files=len(inputs["native_snapshot_sha256"]),
            binding_evidence_copies=inputs["binding_evidence_copies"],
            current_binding_records=inputs["current_binding_evidence_records"],
            packaged_resource_files=len(inputs["resource_sha256"]),
            manual_reads_reviewed=len(resource["manual_review"]["reviewed_unresolved_reads"]),
            planned_checks=len(ids),
            planned_native_captures=inputs["planned"]["native_captures"],
            planned_fresh_Decimal_forms=inputs["planned"]["fresh_Decimal_reference_forms"],
            all_hashes_and_rosters_and_budgets_verified=True,
            no_production_source_delta=True,
            numerical_runs=0,
            execution_hold=True,
            execution_hold_reasons=inputs["execution_hold_reasons"],
        )
    return dict(
        kind="cells.explicit_ECM_successor_batch_static_receipt@1",
        status="four_frozen_held_successors_verified_source_only",
        preparation_receipt=dict(path=str(preparation), sha256=sha(preparation)),
        packets=result,
        unique_changed_Python_path_hash_pairs=len(selected_source_deltas),
        copy_hash_compile_names_Ruff_and_AST_checks_only=True,
        old_frozen_failed_held_results_and_shared_helpers_unchanged=True,
        source_imports_and_arrays_not_evaluated=True,
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_evaluations=0,
        reference_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
        new_or_retained_qualification_passes=0,
        active_job_queries=0,
        automatic_launch=False,
        automatic_polling=False,
        automatic_followup=False,
    )


if __name__ == "__main__":
    result = verify()
    path = WORK / (PREFIX + "_static_receipt_01.json")
    with path.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps(dict(status=result["status"], receipt=str(path), sha256=sha(path))))
