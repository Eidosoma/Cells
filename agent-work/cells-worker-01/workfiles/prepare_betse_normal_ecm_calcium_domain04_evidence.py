"""Build source-only domain04 contract, lineage and prospective full-roster queue."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PREFIX = "betse_normal_ecm_calcium_domain04"
OLD = Path("/mnt/workspaces/Cells/betse-normal-ecm-calcium-join-prepared-20261031-03")
EVIDENCE = Path(
    "/mnt/workspaces/Cells/betse-normal-ecm-calcium-join-launch-preparation-20261031-03/qualification-01/run-core/evidence/normal-ecm-calcium-join"
)
PREPARED = "/mnt/workspaces/Cells/betse-normal-ecm-calcium-domain-prepared-20261031-04"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def row(path, expected=None):
    digest = sha(path)
    if expected is not None:
        assert digest == expected, str(path)
    return dict(path=str(path), sha256=digest)


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def prepare():
    prior = json.loads((OLD / "inputs.json").read_text())
    previous_queue = json.loads(
        (
            OLD
            / "source/agent-work/cells-worker-01/workfiles"
            / "betse_normal_ecm_calcium_join_workqueue.json"
        ).read_text()
    )
    original_protocol = json.loads(
        (OLD / "source/validation/betse/betse_normal_ecm_calcium_join_protocol.json").read_text()
    )
    proof = json.loads((WORK / (PREFIX + "_AST_witness_01.json")).read_text())
    binding = copy.deepcopy(prior["binding_evidence"])
    binding.update(
        frozen_calcium03_inputs=row(
            OLD / "inputs.json", "9df5f4fd651d81aaa4fdb9e33aeabd10f599715a243dc3b9f58f6bc2c93fe490"
        ),
        Chief03_source_review=row(
            "/mnt/workspaces/Cells/ecm-callback-repair-20261031-01/root-review-01/REVIEW.json",
            "d0eb124095d187ee26c5cb52520a8add4a45d74b86dd0da45d2f3e8de974c95c",
        ),
        saved_failure_review=row(
            "/mnt/workspaces/Cells/ecm-calcium-catalog-failure-review-20261031-01/calcium/REVIEW.json",
            "e055aff4ddd73ce47e9977db139812f19b54a7bee110b146432d45c2675d91a2",
        ),
        saved_failure_audit=row(
            "/mnt/workspaces/Cells/ecm-calcium-catalog-failure-review-20261031-01/calcium/AUDIT.json",
            "c8dbbed529dcbd957c1bc8f93e13d2f29e7637b095f877252a9798a28a68b91d",
        ),
        saved_native_failure_details=row(
            "/mnt/workspaces/Cells/ecm-calcium-catalog-failure-review-20261031-01/calcium-native-failure-details.json",
            "e283d3119aecd158e9cc73d46518750455ce54907512461e2a7957ed5ea179d9",
        ),
        strict_saved_archive_decoder=row(
            "/mnt/workspaces/Cells/betse-normal-ecm-calcium-join-launch-preparation-20261031-03/archive_binding.py",
            "4692be0920aee96b5591d38932147fa16bc892e631df0b3628103127e95a5e92",
        ),
        domain04_source_classification_AST=row(WORK / (PREFIX + "_AST_witness_01.json")),
    )
    # Keep complete saved typed archives, their exact input and all four generated
    # constructor forms. Reading/hash/copy of bytes never evaluates an array.
    retained = {}
    for relative in (
        "isolated-negative_genes/native",
        "negative_genes-cold-return-before-bootstrap",
        "negative_genes-bootstrap-return",
    ):
        manifest = json.loads((EVIDENCE / relative / "manifest.json").read_text())
        assert manifest["complete"] is True and set(manifest["files"]) == {
            "arrays.npz",
            "data.json",
        }
        for filename in ("manifest.json", *manifest["files"]):
            expected = manifest["files"].get(filename)
            retained[relative + "/" + filename] = row(EVIDENCE / relative / filename, expected)
    retained["isolated-negative_genes/inputs.json"] = row(
        EVIDENCE / "isolated-negative_genes/inputs.json", proof["original_input_sha256"]
    )
    for kind in ("cold", "bootstrap"):
        for level in (1, 2):
            relative = "preparation-negative_genes/" + kind + "/reference-" + str(level) + ".json"
            retained[relative] = row(EVIDENCE / relative)
    assert len(retained) == 14
    planned = dict(
        checks=34,
        positive_three_call_histories=15,
        component_control_histories=4,
        new_ECM_CaATP_histories=11,
        positive_completed_calls_per_implementation=45,
        raw_partial_limits=6,
        observed_raw_domain_histories=1,
        dependency_controls=12,
        native_captures=22,
        fresh_Decimal_reference_forms=442,
        positive_fresh_Decimal_reference_forms=420,
        observed_raw_fresh_Decimal_reference_forms=22,
        raw_cold_Decimal_forms=2,
        raw_bootstrap_Decimal_forms=2,
        raw_completed_call_Decimal_forms=16,
        raw_native_chemistry_prefix_Decimal_forms=2,
        raw_observed_complete_calls_per_implementation=2,
        raw_observed_partial_third_calls_per_implementation=1,
        carried_reference_forms=0,
        enabled_ER_calls=0,
        biological_cases=0,
        new_qualification_passes=0,
        retained_qualification_passes=0,
    )
    scope = copy.deepcopy(original_protocol["scope"])
    scope["observed_raw_domain"] = (
        "Exact saved negative_genes input (z=-1 products) retains native2 complete calls and "
        "partial third. First nonfinite ordinary Na GJ frame4 occurrences7/8 precedes later "
        "CaATP/GRN NaNs. Owned third stops at existing helper finite guard; native later stops "
        "at X transport/no_negs. Shared prefix and raw helper only; no whole-history/causal claim."
    )
    scope["raw_native_chemistry_reference"] = (
        "Original stdlib warm RHS/delta and chemical X commit equations at Decimal100/160, "
        "conditional on actual native third pre-GRN read projection. Full packet separately "
        "archived. No consumed value replaced; no transport prediction, owned network invocation "
        "or full return predicted."
    )
    protocol = copy.deepcopy(original_protocol)
    protocol.update(
        kind="cells.normal_ecm_calcium_domain04_static_contract@1",
        status="prepared_not_executed_not_qualified",
        purpose=(
            "Prospective full calcium roster preserving exact failed-domain input, partial native "
            "history and distinct owned finite guard, without changing scientific equations or "
            "acceptance budgets"
        ),
        planned=planned,
        scope=scope,
        source_map="validation/betse/" + PREFIX + "_source_map.json",
        binding_evidence=binding,
        declared_roster=dict(
            positive_histories=15,
            unchanged_raw_cases=6,
            observed_raw_domain_cases=["negative_genes"],
            dependencies=12,
            total=34,
        ),
        historical_classification=dict(
            original_campaign_failed=True,
            pytest_passes=33,
            pytest_failures=1,
            controller_completed_group_credit=29,
            matched_other_histories=15,
            matched_other_calls=45,
            compared_forms=420,
            negative_genes_owned_hot_calls=0,
            generated_uncompared_constructor_forms=4,
            retained_new_qualification_passes=0,
        ),
        raw_domain_acceptance=dict(
            input_exact_sha256=proof["original_input_sha256"],
            no_dt_rate_coefficient_guard_tuning=True,
            original_case_metadata_unchanged=True,
            source_and_owned_stops_distinct=True,
            prior_parent_immutable=True,
            complete_partials_required=True,
            negative_concentration_injection_claim=False,
            calcium_specific_cause_claim=False,
            full_history_acceptance=False,
            physical_global_conservation_credit=False,
        ),
        failure_interpretation_erratum=(
            "Legacy declared negative_genes context means negative gene charge. no_negs clips "
            "finite negative concentrations and raises for NaNs. Earlier ordinary Na GJ nonfinite "
            "context is retained; ultimate cause remains unresolved."
        ),
        chemistry_prefix_budget=dict(
            rhs="2e-14+5e-12*abs(reference)",
            delta="6e-14+5e-12*independent_gross",
            X_chemical_commit="3e-13+128*eps*(ions+2+cells+membranes+environment_sites+64)*independent_gross",
            self_resolution_fraction=0.1,
            unchanged_from_legacy=True,
        ),
        retained_failure_artifacts=retained,
    )
    protocol["failures"]["observed_raw_domain"] = scope["observed_raw_domain"]
    write(ROOT / "validation/betse" / (PREFIX + "_protocol.json"), protocol)
    mapping = dict(
        kind="cells.calcium_domain04_source_map@1",
        scope=scope,
        source_classification_AST_proof=proof,
        inherited_source_map_sha256=row(
            ROOT / "validation/betse/betse_normal_ecm_calcium_join_source_map.json"
        ),
        inherited_scientific_owned_sha256=prior["owned_sha256"],
        actual_legacy_science_changed=False,
        source_ER_disabled=True,
        original_native_first_nonfinite_is_ordinary_Na_GJ=True,
        raw_third_only_common_prefix_and_helper_correspond=True,
        exact_pre_GHK_chemistry_equations=True,
        independent_transport_prediction=False,
        original_failed_campaign_pass=False,
        numerical_runs=0,
        scientific_imports=0,
    )
    write(ROOT / "validation/betse" / (PREFIX + "_source_map.json"), mapping)
    spec = importlib.util.spec_from_file_location(
        "domain04_static_closure", WORK / (PREFIX + "_static_audit.py")
    )
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    refs = audit.closure("validation/betse/" + PREFIX + "_reference.py", reference=True)
    refs.update(
        audit.closure("validation/betse/betse_normal_ecm_calcium_join_reference.py", reference=True)
    )
    imports = audit.closure("tests/unit/test_" + PREFIX + ".py", reference=False)
    owned = [
        "tests/unit/test_" + PREFIX + ".py",
        *[
            "validation/betse/" + PREFIX + suffix
            for suffix in (
                "_fixtures.py",
                "_reference.py",
                "_negative_genes.json",
                "_protocol.json",
                "_source_map.json",
            )
        ],
        *[
            "agent-work/cells-worker-01/workfiles/" + PREFIX + suffix
            for suffix in (
                "_checks.py",
                "_ast_audit.py",
                "_static_audit.py",
                "_reporting_metadata_check.py",
            )
        ],
    ]
    protected = prior["owned_sha256"] | prior["protected_sha256"]
    for relative, digest in (imports | refs).items():
        if relative not in owned:
            assert relative not in protected or protected[relative] == digest, relative
            protected[relative] = digest
    assert "src/cells/processes/betse_normal_ecm_catalog_join_source.py" not in imports
    assert "src/cells/processes/betse_normal_ecm_catalog_join_source.py" not in protected
    for relative, expected in protected.items():
        assert sha(ROOT / relative) == expected, relative
    workfiles = sorted(
        {str(p.relative_to(ROOT)) for p in WORK.glob("*" + PREFIX + "*") if p.is_file()}
        | {
            "agent-work/cells-worker-01/workfiles/BETSE_NORMAL_ECM_CALCIUM_DOMAIN04_NOTES.md",
            "agent-work/cells-worker-01/workfiles/" + PREFIX + "_reporting_metadata_check_01.json",
            "agent-work/cells-worker-01/workfiles/" + PREFIX + "_static_witness_01.json",
        }
    )
    queue = dict(
        kind="cells.calcium_domain04_workqueue@1",
        status="prepared_static_only_awaits_Chief_review",
        owned=owned,
        owned_sha256={p: sha(ROOT / p) for p in owned},
        protected_sha256=protected,
        reference_closure=refs,
        scientific_import_closure=imports,
        runner="agent-work/cells-worker-01/workfiles/" + PREFIX + "_checks.py",
        workfiles=workfiles,
        planned=planned,
        binding_evidence=binding,
        retained_failure_artifacts=retained,
        freeze_prerequisites={
            k: binding[k] for k in ("Chief03_source_review", "saved_failure_review")
        },
        prepared_inputs=PREPARED + "/inputs.json",
        static_receipt="agent-work/cells-worker-01/workfiles/" + PREFIX + "_static_receipt_01.json",
        authorized_physical_helper_refactor=prior["authorized_physical_helper_refactor"],
        coordinated_shared_edit_paths=previous_queue["coordinated_shared_edit_paths"],
        coordinated_unloaded_Chief_work=[
            "src/cells/processes/betse_normal_ecm_catalog_join_source.py",
            "all betse_native_cut_lifecycle files",
        ],
        coordinated_unloaded_work_policy=(
            "Snapshot-only files are explicitly listed in frozen inputs; live protection covers "
            "the complete runtime/reference closure, old science and fixed-budget files. No "
            "current unrelated source pin is adopted as a dependency."
        ),
        numerical_runs=0,
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_evaluations=0,
        reference_evaluations=0,
        pytest_collection_runs=0,
        active_numerical_job=False,
        original_campaign_still_failed=True,
        retained_or_new_qualification_passes=0,
        automatic_launch=False,
        automatic_polling=False,
        automatic_followup=False,
    )
    write(WORK / (PREFIX + "_workqueue.json"), queue)
    print(
        json.dumps(
            dict(
                status=queue["status"],
                owned=len(owned),
                protected=len(protected),
                reference_closure=len(refs),
                import_closure=len(imports),
                retained_artifacts=len(retained),
            )
        )
    )


if __name__ == "__main__":
    prepare()
