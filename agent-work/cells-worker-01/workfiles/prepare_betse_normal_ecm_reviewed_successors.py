# ruff: noqa: E501
"""Copy/hash/AST-only explicit successors; no scientific imports, collection or launch."""

import argparse
import ast
import copy
import json
import shutil
import subprocess
import traceback
from pathlib import Path

from betse_normal_ecm_reviewed_successors_resources import (
    BASE,
    PACKETS,
    ROOT,
    WORK,
    audit,
    manual_review,
    sha,
)

PREFIX = "betse_normal_ecm_reviewed_successors"
PROPOSAL1 = WORK / (PREFIX + "_proposal_01")
PROPOSAL2 = WORK / (PREFIX + "_proposal_03")
CATALOG = "validation/betse/betse_normal_ecm_catalog_join_reference.py"
EVENT = "validation/betse/betse_normal_ecm_event_join_reference.py"
LIFE_TEST = "tests/unit/test_betse_normal_ecm_run_lifecycle.py"
LIFE_NATIVE = "validation/betse/betse_normal_ecm_run_lifecycle_native.py"
ARCHIVE = BASE / "ecm-catalog-archive-cardinality-repair-20261031-01"
NALEAK = BASE / "ecm-catalog-naleak-reference-repair-20261031-01"
LIFE_REVIEW = BASE / "betse-normal-ecm-run-lifecycle-preflight-20261031-01/REVIEW.json"
SUCCESSORS = {
    "catalog05": "betse-normal-ecm-catalog-join-prepared-20261031-05",
    "event04": "betse-normal-ecm-event-join-prepared-20261031-04",
    "event_mechanics03": "betse-normal-ecm-event-mechanics-prepared-20261031-03",
    "lifecycle02": "betse-normal-ecm-run-lifecycle-prepared-20261031-02",
}


def row(path):
    return dict(path=str(path), sha256=sha(path))


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def replace_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def signature(node):
    return ast.dump(node, include_attributes=False)


def functions(text):
    return {n.name: n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef)}


def verify_inputs(parent, inputs):
    actual = {
        str(p.relative_to(parent / "source")) for p in (parent / "source").rglob("*") if p.is_file()
    }
    assert actual == set(inputs["source_hashes"]), "Unexpected parent snapshot files"
    for relative, pin in inputs["source_hashes"].items():
        assert sha(parent / "source" / relative) == pin, relative
    for relative, pin in inputs["native_snapshot_sha256"].items():
        assert sha(parent / relative) == pin, relative
    assert sha(parent / "driver.py") == inputs["driver_sha256"]


def reviewed_repairs():
    promotion = json.loads((NALEAK / "promotion.json").read_text())
    assert promotion["status"] == "reviewed_candidate_promoted_byte_exact"
    assert (
        sha(ROOT / CATALOG)
        == promotion["live_source_sha256"][CATALOG]
        == ("6c51cdddbeb166ee33a9000143aad16f003cb9e6d4178cb3993aa62a1538ea70")
    )
    review = ARCHIVE / "root-review-01/REVIEW.json"
    assert sha(review) == "0f8a681b50d57e88adc3617099e2a1fc39ad269d6b72a9414c3583254fcf3744"
    assert (
        sha(ARCHIVE / "archive_binding.py")
        == "e25aaedfe6b9255740bcdb83acc36a35d5e31e1741507dd01e03488ab2e26e59"
    )
    assert sha(LIFE_REVIEW) == "4d28d4bc4f18283f2f5d2b1c4ec5108e0598f3c044ac108306c8c3f699520e4a"
    archive = json.loads((ARCHIVE / "result.json").read_text())
    old = (ARCHIVE / "archive_binding_before.py").read_bytes()
    candidate = (ARCHIVE / "archive_binding.py").read_bytes()
    inverse = candidate.replace(b"MAX_MEMBERS=32768\n", b"", 1)
    inverse = inverse.replace(b"len(entries)<=MAX_MEMBERS", b"len(entries)<=10000", 1)
    assert inverse == old
    assert archive["delta"]["compressed_expanded_and_JSON_bytes_each_unchanged"] == 64 * 2**20
    original = json.loads((PROPOSAL1 / "source-proposals.json").read_text())
    event = original["event_NaLeak_only"]
    assert sha(event["candidate_path"]) == event["after_sha256"]
    assert sha(PROPOSAL1 / CATALOG) == sha(ROOT / CATALOG)
    evidence = json.loads((PROPOSAL2 / "lifecycle-evidence-proposals.json").read_text())
    for relative, pin in evidence["files_sha256"].items():
        assert sha(PROPOSAL2 / relative) == pin, relative
    return dict(
        reviewed_NaLeak_promotion=row(NALEAK / "promotion.json"),
        reviewed_NaLeak_source_review=promotion["independent_review"],
        reviewed_archive_cardinality=row(review),
        archive_cardinality_result=row(ARCHIVE / "result.json"),
        archive_cardinality_basis=row(ARCHIVE / "cardinality-bound.json"),
        proposed_event_NaLeak_inverse_AST=row(PROPOSAL1 / "source-proposals.json"),
        lifecycle01_held_review=row(LIFE_REVIEW),
        proposed_lifecycle_evidence_repairs=row(PROPOSAL2 / "lifecycle-evidence-proposals.json"),
        successor_scalar_metadata_contract=row(WORK / (PREFIX + "_metadata_witness_01.json")),
    )


def driver_text(original):
    """Keep original numerical command/report readers; make held pin policy explicit."""
    tree = ast.parse(original)
    before = functions(original)
    for fn in tree.body:
        if not isinstance(fn, ast.FunctionDef):
            continue
        if fn.name == "prepare":
            fn.body = ast.parse(
                'raise ValueError("This explicit successor is already frozen; use its separately reviewed preparation tool for further successors")'
            ).body
        if fn.name != "run":
            continue
        fn.body[1:1] = ast.parse("""
if inputs["execution_hold"]:
    raise ValueError("Frozen successor is held: " + "; ".join(inputs["execution_hold_reasons"]))
""").body
        for node in ast.walk(fn):
            if not isinstance(node, ast.For) or not isinstance(node.iter, ast.Call):
                continue
            if not isinstance(node.iter.func, ast.Attribute) or node.iter.func.attr != "items":
                continue
            value = ast.unparse(node.iter.func.value)
            if value in (
                "inputs['owned_sha256']",
                "inputs['owned_sha256'] | inputs['protected_sha256']",
            ):
                node.iter.func.value = ast.parse(
                    "inputs['live_execution_sha256']", mode="eval"
                ).body
        protected = ast.parse("""
for path, expected in inputs["qualification_helpers_sha256"].items():
    if sha(out / path) != expected:
        raise ValueError("Changed explicitly bound qualification helper: " + path)
""").body
        inner = next(n for n in fn.body if isinstance(n, ast.Try))
        inner.body[0:0] = protected
    text = "# ruff: noqa: E501\n" + ast.unparse(ast.fix_missing_locations(tree)) + "\n"
    after = functions(text)
    for name in before.keys() - {"prepare", "run"}:
        assert signature(before[name]) == signature(after[name]), name
    return text


def prepare_one(role, prior, repairs):
    parent_name, prefix = PACKETS[role]
    parent = BASE / parent_name
    out = BASE / SUCCESSORS[role]
    old = json.loads((parent / "inputs.json").read_text())
    verify_inputs(parent, old)
    out.mkdir(exist_ok=False)
    stage = "source_copy"
    try:
        source = out / "source"
        shutil.copytree(
            parent / "source",
            source,
            ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".ruff_cache"),
        )
        shutil.copytree(parent / "native-inputs", out / "native-inputs")
        ancestors = {}
        for ancestor_role, ancestor in prior.items():
            inputs = json.loads((ancestor / "inputs.json").read_text())
            for relative in inputs["source_delta_sha256"]:
                target = source / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ancestor / "source" / relative, target)
            ancestors[ancestor_role] = row(ancestor / "inputs.json")
        shutil.copy2(PROPOSAL1 / CATALOG, source / CATALOG)
        if role != "catalog05":
            shutil.copy2(PROPOSAL1 / EVENT, source / EVENT)
        if role == "lifecycle02":
            shutil.copy2(PROPOSAL2 / LIFE_TEST, source / LIFE_TEST)
            shutil.copy2(PROPOSAL2 / LIFE_NATIVE, source / LIFE_NATIVE)
        shutil.copy2(
            ROOT / "validation/frozen_resource_dependencies.py",
            source / "validation/frozen_resource_dependencies.py",
        )
        protocol_path = source / "validation/betse" / (prefix + "_protocol.json")
        source_map_path = source / "validation/betse" / (prefix + "_source_map.json")
        protocol = json.loads(protocol_path.read_text())
        mapping = json.loads(source_map_path.read_text())
        original_protocol = copy.deepcopy(protocol)
        refresh = dict(
            role=role,
            parent_inputs=row(parent / "inputs.json"),
            upstream_successor_inputs=ancestors,
            repairs=repairs,
            reviewed_catalog_reference_sha256=sha(source / CATALOG),
            proposed_event_reference_sha256=None if role == "catalog05" else sha(source / EVENT),
            event_reference_proposal_review_pending=role != "catalog05",
            lifecycle_evidence_proposal_review_pending=role == "lifecycle02",
            old_held_failed_parents_untouched=True,
            no_new_equations_except_explicit_reviewed_NaLeak_domain_adapter=True,
            new_budget_changes=False,
            rosters_unchanged=True,
            scientific_passes_inherited=0,
            numerical_runs=0,
        )
        protocol["explicit_prospective_successor_refresh"] = refresh
        mapping["explicit_prospective_successor_refresh"] = refresh
        mapping["parent_source_AST_evidence_is_historical"] = True
        replace_json(protocol_path, protocol)
        replace_json(source_map_path, mapping)
        stage = "resource_closure"
        resources = audit(source, prefix)
        manual = manual_review(resources)
        assert not resources["literal_resource_audit"]["missing_resources"]
        assert not manual["pending_manual_reads"]
        native = protocol["native_source"]
        for relative, pin in manual["native_source_union_sha256"].items():
            assert (
                relative not in native["source_sha256"] or native["source_sha256"][relative] == pin
            )
            native["source_sha256"][relative] = pin
        replace_json(protocol_path, protocol)
        mapping["effective_native_source_union_sha256"] = native["source_sha256"]
        replace_json(source_map_path, mapping)
        # Only the two metadata JSON files changed after source read discovery.
        # Rebind their final bytes; no scientific or path expression changed.
        for relative in list(manual["resource_sha256"]):
            manual["resource_sha256"][relative] = sha(source / relative)
        for entry in manual["reviewed_unresolved_reads"]:
            if "resource" in entry:
                entry["sha256"] = sha(source / entry["resource"])
        for entry in resources["literal_resource_audit"]["required_resources"]:
            if entry["present"]:
                entry["sha256"] = sha(source / entry["resource"])
        resource_proof = dict(
            kind="cells.explicit_successor_resource_closure@1",
            role=role,
            imported_module_and_literal_resource_audit=resources,
            manual_review=manual,
            protocol_and_source_map_final_hashes={
                str(protocol_path.relative_to(source)): sha(protocol_path),
                str(source_map_path.relative_to(source)): sha(source_map_path),
            },
            all_discovered_resources_present=True,
            all_manual_read_sites_classified=True,
            no_general_dynamic_dependency_solver_claim=True,
            scientific_imports=0,
            scientific_AST_executions=0,
            numerical_runs=0,
        )
        write(out / "resource-audit.json", resource_proof)
        stage = "native_and_evidence_binding"
        for relative, pin in native["source_sha256"].items():
            for label, base in (
                ("checkout", Path(native["checkout"])),
                ("installed", Path(native["installed_package"]).parent),
            ):
                assert sha(base / relative) == pin, relative
                target = out / "native-inputs" / label / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    assert sha(target) == pin
                else:
                    shutil.copy2(base / relative, target)
        bindings = copy.deepcopy(old["binding_evidence"])
        bindings.update(repairs)
        bindings["successor_parent_inputs"] = row(parent / "inputs.json")
        bindings["successor_resource_closure"] = row(out / "resource-audit.json")
        for name, item in ancestors.items():
            bindings["successor_upstream_" + name] = item
        for name, item in bindings.items():
            assert sha(item["path"]) == item["sha256"], name
            target = (
                out
                / "native-inputs/binding-evidence"
                / ("successor_" + name + Path(item["path"]).suffix)
            )
            assert not target.exists()
            shutil.copy2(item["path"], target)
        helpers = {
            "archive_binding.py": ARCHIVE / "archive_binding.py",
            "qualification_typed_evidence.py": ARCHIVE / "qualification_typed_evidence.py",
            "resource-audit-tools/frozen_resource_dependencies.py": ROOT
            / "validation/frozen_resource_dependencies.py",
        }
        for relative, original in helpers.items():
            target = out / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, target)
        preparation_artifacts = {}
        for original in sorted(WORK.glob("*" + PREFIX + "*")):
            if original.is_dir():
                selected = [p for p in original.rglob("*") if p.is_file()]
            elif original.is_file():
                selected = [original]
            else:
                continue
            for item in selected:
                relative = "preparation-tools/" + str(item.relative_to(WORK))
                target = out / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)
                preparation_artifacts[relative] = sha(target)
        stage = "held_runner"
        driver_original = (
            (PROPOSAL2 / "lifecycle-evidence-reader.py").read_text()
            if role == "lifecycle02"
            else (parent / "driver.py").read_text()
        )
        (out / "driver.py").write_text(driver_text(driver_original))
        # Ruff only formats the new driver and removes imports used solely by
        # the deliberately disabled legacy live-tree preparation function.
        subprocess.run(
            [
                "/mnt/workspaces/Cells/venv-cpu/bin/ruff",
                "check",
                "--select",
                "F401",
                "--fix",
                str(out / "driver.py"),
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["/mnt/workspaces/Cells/venv-cpu/bin/ruff", "format", str(out / "driver.py")],
            check=True,
            capture_output=True,
        )
        driver_functions = functions((out / "driver.py").read_text())
        for name in functions(driver_original).keys() - {"prepare", "run"}:
            assert signature(functions(driver_original)[name]) == signature(
                driver_functions[name]
            ), name
        source_hashes = {
            str(p.relative_to(source)): sha(p) for p in sorted(source.rglob("*")) if p.is_file()
        }
        own = {p: source_hashes[p] for p in old["owned_sha256"]}
        protected = {p: source_hashes[p] for p in old["protected_sha256"]}
        required = (
            resources["scientific_import_closure"]
            | resources["reference_closure"]
            | manual["resource_sha256"]
        )
        for relative, pin in required.items():
            assert source_hashes[relative] == pin
            if relative not in own:
                protected[relative] = pin
        live_execution = {
            p: h for p, h in (own | protected).items() if p.startswith("src/") and p.endswith(".py")
        }
        live_execution[CATALOG] = source_hashes[CATALOG]
        observed_live_drift = {
            p: dict(frozen_sha256=h, current_live_sha256=sha(ROOT / p))
            for p, h in live_execution.items()
            if sha(ROOT / p) != h
        }
        hold = [
            "Independent review of this explicit frozen successor is required; no numerical release granted"
        ]
        if role != "catalog05":
            hold.extend(
                [
                    "Exact event NaLeak-only branch proposal requires independent review",
                    "The catalog31726-member engineering envelope does not account for event/mechanics/lifecycle capture overhead",
                ]
            )
        if role == "lifecycle02":
            hold.append(
                "Observer paths, named raw boundaries and completed-capture retention repairs require independent review"
            )
        if observed_live_drift:
            hold.append(
                "Controlled live production drift must be resolved explicitly before any coordinated run"
            )
        inputs = copy.deepcopy(old)
        inputs.update(
            kind="cells.explicit_reviewed_ECM_successor_prepared@1",
            status="prepared_source_only_held_unrun_unreleased",
            successor_role=role,
            prior_packet_inputs=row(parent / "inputs.json"),
            upstream_successor_inputs=ancestors,
            authorized_explicit_successor_refresh=refresh,
            source_hashes=source_hashes,
            owned_sha256=own,
            protected_sha256=protected,
            reference_closure=resources["reference_closure"],
            scientific_import_closure=resources["scientific_import_closure"],
            resource_sha256=manual["resource_sha256"],
            resource_audit=row(out / "resource-audit.json"),
            source_map_sha256=sha(source_map_path),
            driver_sha256=sha(out / "driver.py"),
            native_snapshot_sha256={
                str(p.relative_to(out)): sha(p)
                for p in sorted((out / "native-inputs").rglob("*"))
                if p.is_file()
            },
            native_source_copies=2 * len(native["source_sha256"]),
            binding_evidence=bindings,
            binding_evidence_copies=sum(
                p.is_file() for p in (out / "native-inputs/binding-evidence").rglob("*")
            ),
            current_binding_evidence_records=len(bindings),
            qualification_helpers_sha256={relative: sha(out / relative) for relative in helpers},
            preparation_artifacts_sha256=preparation_artifacts,
            qualification_archive_binding_scope="Explicit prospective evidence verifier only; source/runtime archive writer unchanged; fixed32768 members, unchanged64MiB and integrity guards",
            archive_schema_allowance_scope="31726 members is catalog-only3calls/3populations/5routes. No bound is claimed for added event/mechanics/lifecycle capture overhead.",
            source_delta_sha256={
                p: h for p, h in source_hashes.items() if old["source_hashes"].get(p) != h
            },
            source_removed_paths=sorted(set(old["source_hashes"]) - set(source_hashes)),
            live_execution_sha256=live_execution,
            observed_live_production_drift_not_adopted=observed_live_drift,
            effective_execution_pin_policy="Every frozen source/native/helper hash plus declared live production and promoted catalog reference pins. Frozen metadata/proposals are explicit; no live shared dependency refresh.",
            inherited_static_preparation_scripts_are_historical=True,
            legacy_live_tree_prepare_disabled=True,
            execution_hold=True,
            execution_hold_reasons=hold,
            numerical_release_authorized=False,
            execution_requires_new_requested_round=True,
            component_qualification_pending=True,
            full_roster_without_retained_passes=True,
            scientific_imports=0,
            scientific_AST_executions=0,
            fixture_evaluations=0,
            reference_evaluations=0,
            pytest_collection_runs=0,
            numerical_runs=0,
            scientific_qualification_passes=0,
            qualification_scientific_passes_retained=0,
            new_or_retained_qualification_passes=0,
            automatic_launch=False,
            automatic_polling=False,
            automatic_followup=False,
        )
        if "explicit_dependency_binding" in inputs:
            inputs["ancestor_dependency_binding_historical"] = inputs["explicit_dependency_binding"]
            inputs["explicit_dependency_binding"] = dict(
                status="new_successor_dependencies_explicitly_bound_review_pending",
                parent_inputs=inputs["prior_packet_inputs"],
                upstream_successor_inputs=ancestors,
                current_frozen_source_sha256=protected,
            )
        if role == "lifecycle02":
            inputs["frozen_dependency_parent"] = ancestors["event_mechanics03"]
            inputs["frozen_dependency_sources"] = {
                p: dict(path=str(source / p), sha256=h) for p, h in protected.items()
            }
            inputs["dependency_runtime_authority"] = (
                "Explicit new frozen successor tree; event/mechanics03 ancestry; independent review pending"
            )
            inputs["live_hash_guard_scope"] = (
                "Declared live production + promoted catalog reference only; all frozen source/native/helper bytes remain guarded"
            )
        assert inputs["planned"] == old["planned"] and inputs["groups"] == old["groups"]
        assert inputs["required_reports"] == old["required_reports"]
        assert not inputs["source_removed_paths"]
        # Every original scientific budget field is byte/value-identical.
        for key in (
            "acceptance",
            "mechanics_acceptance",
            "tolerances",
            "inherited_mechanics_divergence_category_disclosure",
        ):
            if key in original_protocol:
                assert protocol[key] == original_protocol[key], key
        stage = "static_delta_and_compile"
        for relative in inputs["source_delta_sha256"]:
            if relative.startswith("src/"):
                raise ValueError("Unexpected production source delta: " + relative)
            if relative.endswith(".py"):
                compile((source / relative).read_text(), relative, "exec")
        compile((out / "driver.py").read_text(), "driver.py", "exec")
        for path in [
            out / "driver.py",
            *[source / p for p in inputs["source_delta_sha256"] if p.endswith(".py")],
        ]:
            # Reviewed byte-exact helpers retain their own established style;
            # scientific candidates and new driver must pass the existing Ruff rules.
            checked = subprocess.run(
                ["/mnt/workspaces/Cells/venv-cpu/bin/ruff", "check", str(path)],
                text=True,
                capture_output=True,
            )
            assert checked.returncode == 0, (str(path), checked.stdout, checked.stderr)
        write(out / "inputs.json", inputs)
        write(
            out / "static-review-inputs.json",
            dict(
                kind="cells.explicit_ECM_successor_static_delta@1",
                role=role,
                parent_inputs=inputs["prior_packet_inputs"],
                successor_inputs=row(out / "inputs.json"),
                source_delta_sha256=inputs["source_delta_sha256"],
                all_original_test_rosters_report_sets_and_budgets_unchanged=True,
                only_physics_reference_delta="Reviewed NaLeak-only constant law domain adapter; exact branch proposal in event copy",
                extra_lifecycle_delta="Observer archive names and named raw-case evidence, plus native completed-capture exception retention"
                if role == "lifecycle02"
                else None,
                scientific_imports=0,
                scientific_AST_executions=0,
                numerical_runs=0,
                execution_hold=True,
                execution_hold_reasons=hold,
                new_or_retained_qualification_passes=0,
            ),
        )
        print(
            json.dumps(
                dict(
                    role=role,
                    inputs=str(out / "inputs.json"),
                    sha256=sha(out / "inputs.json"),
                    checks=sum(map(len, inputs["groups"].values())),
                    source_delta=len(inputs["source_delta_sha256"]),
                    native_files=len(native["source_sha256"]),
                    resources=len(manual["resource_sha256"]),
                    numerical_runs=0,
                )
            )
        )
        return out
    except BaseException as error:
        write(
            out / "failure.json",
            dict(
                stage=stage,
                type=type(error).__name__,
                message=str(error),
                traceback=traceback.format_exc(),
                numerical_runs=0,
                automatic_retry=False,
                preserve_partial_preparation=True,
            ),
        )
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true", required=True)
    args = parser.parse_args()
    assert args.prepare
    repairs = reviewed_repairs()
    prepared = {}
    for role in SUCCESSORS:
        prepared[role] = prepare_one(role, prepared, repairs)
    receipt = WORK / (PREFIX + "_preparation_receipt_01.json")
    write(
        receipt,
        dict(
            kind="cells.explicit_ECM_successor_batch_receipt@1",
            status="prepared_four_held_source_only_successors",
            inputs={k: row(v / "inputs.json") for k, v in prepared.items()},
            source_preparation_tool=row(Path(__file__)),
            repairs=repairs,
            scientific_imports=0,
            scientific_AST_executions=0,
            numerical_runs=0,
            new_or_retained_qualification_passes=0,
            automatic_followup=False,
        ),
    )
    print(json.dumps(dict(receipt=str(receipt), sha256=sha(receipt))))


if __name__ == "__main__":
    main()
