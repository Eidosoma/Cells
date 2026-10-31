"""Prepare source-only lifecycle contracts using the reviewed frozen dependency tree."""

import copy
import json
from pathlib import Path

from betse_normal_ecm_run_lifecycle_ast_audit import audit as AST_audit
from betse_normal_ecm_run_lifecycle_dependencies import PARENT, PREFIX, ROOT, audit, sha

WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PREPARED = "/mnt/workspaces/Cells/betse-normal-ecm-run-lifecycle-prepared-20261031-01"


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def row(path):
    return dict(path=str(path), sha256=sha(path))


def prepare():
    previous = json.loads((PARENT / "inputs.json").read_text())
    inherited = json.loads(
        (
            PARENT / "source/validation/betse/betse_normal_ecm_event_mechanics_protocol.json"
        ).read_text()
    )
    dependencies = audit()
    proof = AST_audit()
    witness = WORK / (PREFIX + "_dependency_witness_02.json")
    write(witness, dependencies)
    bindings = copy.deepcopy(previous["binding_evidence"])
    bindings.update(
        reviewed_event_mechanics02_inputs=dependencies["parent_inputs"],
        reviewed_event_mechanics02_manifest=dependencies["parent_manifest"],
        reviewed_event_mechanics02_preflight=dependencies["parent_preflight"],
        independent_calendar_API_review=dependencies["independent_calendar_review"],
        reviewed_event03_inputs=dependencies["event03_inputs"],
        headless_lifecycle_source_boundary=row(WORK / (PREFIX + "_source_boundary_02.json")),
        headless_lifecycle_AST_proof=row(WORK / (PREFIX + "_AST_witness_01.json")),
        headless_lifecycle_dependencies=row(witness),
    )
    planned = dict(
        checks=48,
        positive_lifecycle_contracts=12,
        continuous_and_window_schedules=5,
        sampling_variants=2,
        forcing_context_variants=5,
        distinct_component_forcing_families=6,
        raw_source_limits=4,
        observer_failure_controls=3,
        dependency_controls=22,
        clock_only_source_probes=6,
        display_refusal_controls=1,
        native_captures=22,
        native_material_captures=16,
        native_clock_only_captures=6,
        conditional_points_per_positive_history=26,
        forms_per_history=52,
        fresh_Decimal_reference_forms=624,
        precision_levels=[100, 160],
        primary_positive_completed_calls=36,
        duplicate_direct_component_baseline_calls=36,
        duplicate_direct_component_baseline_histories=12,
        duplicate_baseline_new_case_credit=0,
        duplicate_baseline_additional_reference_forms=0,
        carried_reference_forms=0,
        retained_qualification_passes=0,
        new_qualification_passes=0,
        installed_native_initializer_calls=0,
        native_full_phase_calls=0,
        native_display_calls=0,
        native_pickle_calls=0,
        physical_initializations=0,
        biological_cases=0,
    )
    scope = dict(
        supplied_component_entry_only=True,
        entry_receipt_is_declaration_not_initialization_attestation=True,
        ordinary_ECM_FULL_SIM_N3_only=True,
        INIT_time_setup_audited_but_INIT_material_execution_closed=True,
        original_binary64_int_total_over_dt=True,
        source_label_and_update_dt_separate=True,
        original_source_calendar_and_sampling_preserved=True,
        one_component_advance_per_owned_call=True,
        complete_component_state_and_caches_carried=True,
        pause_and_resume_at_accepted_owned_call_boundaries=True,
        pause_is_not_native_phase_completion=True,
        empty_prefix_has_no_component_call=True,
        exhaustion_has_no_pickle_report_or_display=True,
        full_failed_and_reached_state_retained=True,
        no_automatic_failure_resume_or_retry=True,
        headless_observations_at_source_sample_eligibility=True,
        native_write2storage_and_display=False,
        installed_native_seed_init_load_run_sim_core_pickle=False,
        physical_initialization_claim=False,
        independent_carried_trajectory=False,
        physical_global_conservation_credit=False,
        enabled_flow=False,
        dynamic_deformation=False,
        cut_or_geometry_rebuild=False,
        maximum_field_cells=16,
        minimum_quartic_display_cells=25,
        component_qualification_pending=True,
        scientific_passes_inherited=0,
        original_material_39of40_failure_preserved=True,
    )
    native = copy.deepcopy(inherited["native_source"])
    for name in ("betse/science/phase/phasecls.py", "betse/science/enum/enumphase.py"):
        expected = sha(Path(native["checkout"]) / name)
        assert sha(Path(native["installed_package"]).parent / name) == expected
        assert name not in native["source_sha256"] or native["source_sha256"][name] == expected
        native["source_sha256"][name] = expected
    protocol = dict(
        kind="cells.headless_ECM_run_lifecycle_static_contract@1",
        status="static_preparation_unrun_unreleased_unqualified",
        purpose=(
            "Audit phase clocks and state ownership while wrapping the existing single advance "
            "with explicit supplied entry, windows, stopping, observations and complete failure "
            "retention"
        ),
        scope=scope,
        planned=planned,
        native_source=native,
        binding_evidence=bindings,
        acceptance=copy.deepcopy(inherited["acceptance"]),
        mechanics_acceptance=copy.deepcopy(inherited["mechanics_acceptance"]),
        mechanics_budget_source_sha256=inherited["mechanics_budget_source_sha256"],
        inherited_mechanics_divergence_category_disclosure=inherited[
            "inherited_mechanics_divergence_category_disclosure"
        ],
        new_budget_changes=False,
        new_numerical_equations=False,
        source_map="validation/betse/" + PREFIX + "_source_map.json",
        source_capture=dict(
            complete_captured_function_bodies=["SimPhase._init_kludge_time"],
            extracted_statement_slices=[
                "Parameters.load.time_counts",
                "Simulator._plot_loop.clock_and_sampling",
            ],
            inherited_component_capture=(
                "Exact reviewed event/mechanics02 full function bodies and declared slices; "
                "no source equation reimplementation"
            ),
            installed_native_function_calls=0,
            no_whole_Parameters_load_plot_loop_or_phase_execution=True,
        ),
        source_lifecycle_boundary=bindings["headless_lifecycle_source_boundary"],
        source_AST_proof=bindings["headless_lifecycle_AST_proof"],
        resources=copy.deepcopy(inherited["resources"]),
        independent_reference=copy.deepcopy(inherited["independent_reference"]),
        failure_retention=dict(
            caller_supplied_entry_and_receipt=True,
            original_window_parent=True,
            completed_transition_contexts=True,
            last_accepted_full_component_and_run_state=True,
            attempted_returned_component_candidate_context_and_run_candidate=True,
            component_source_failure_partials=True,
            accepted_commit_before_observer_failure=True,
            native_instability_save_policy_audited_but_no_pickle=True,
            zero_accuracy_credit=True,
        ),
        dependency_policy=dict(
            runtime_authority="Reviewed immutable event/mechanics02/source snapshot",
            snapshot_parent=dependencies["parent_inputs"],
            source_tree_copied_before_owned_prefix_overlay=True,
            live_guards=(
                "Owned lifecycle prefix only; frozen imported dependencies checked before every run"
            ),
            five_dense_to_window_repairs_explicitly_reviewed=True,
            calendar_implementation_unchanged=True,
            live_reference_or_archive_refresh_adopted=False,
            known_followup=(
                "Root owns later catalog/event/mechanics successors containing NaLeak-only ECM "
                "reference and archive-cardinality repairs. This packet keeps exact "
                "event/mechanics02 pins and grants no qualification or release."
            ),
        ),
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_evaluations=0,
        reference_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
        automatic_launch=False,
        automatic_polling=False,
        automatic_followup=False,
    )
    mapping = dict(
        kind="cells.headless_ECM_lifecycle_source_map@1",
        scope=scope,
        source_AST_proof=proof,
        native_source_boundary=bindings["headless_lifecycle_source_boundary"],
        reviewed_dependency_witness=bindings["headless_lifecycle_dependencies"],
        source_capture=protocol["source_capture"],
        native_source_sha256=native["source_sha256"],
        new_numerical_equations=False,
        new_budget_changes=False,
        scientific_imports=0,
        numerical_runs=0,
    )
    write(ROOT / "validation/betse" / (PREFIX + "_protocol.json"), protocol)
    write(ROOT / "validation/betse" / (PREFIX + "_source_map.json"), mapping)
    protected = copy.deepcopy(dependencies["protected_snapshot_sha256"])
    for relative, pin in protocol["acceptance"]["inherited_budget_source_sha256"].items():
        assert sha(PARENT / "source" / relative) == pin
        assert relative not in protected or protected[relative] == pin
        protected[relative] = pin
    extra = "validation/betse/betse_mechanics_join_checks.py"
    assert sha(PARENT / "source" / extra) == protocol["mechanics_budget_source_sha256"]
    protected[extra] = protocol["mechanics_budget_source_sha256"]
    owned = sorted(
        {str(p.relative_to(ROOT)) for p in (ROOT / "src/cells/processes").glob(PREFIX + "*.py")}
        | {
            str(p.relative_to(ROOT))
            for p in (ROOT / "validation/betse").glob(PREFIX + "*")
            if p.is_file()
        }
        | {"tests/unit/test_" + PREFIX + ".py"}
        | {str(p.relative_to(ROOT)) for p in WORK.glob("*" + PREFIX + "*.py")}
    )
    workfiles = sorted(
        {str(p.relative_to(ROOT)) for p in WORK.glob("*" + PREFIX + "*") if p.is_file()}
        | {
            str((WORK / (PREFIX + suffix)).relative_to(ROOT))
            for suffix in ("_metadata_witness_01.json", "_static_witness_01.json")
        }
    )
    queue = dict(
        kind="cells.headless_ECM_run_lifecycle_workqueue@1",
        status="static_preparation_only_pending_Chief_review",
        owned=owned,
        owned_sha256={p: sha(ROOT / p) for p in owned},
        protected_snapshot_sha256=protected,
        frozen_dependency_sources={
            p: dict(path=str(PARENT / "source" / p), sha256=h) for p, h in protected.items()
        },
        frozen_dependency_parent=dependencies["parent_inputs"],
        reference_closure=dependencies["reference_closure"],
        scientific_import_closure=dependencies["scientific_import_closure"],
        explicit_dependency_binding=dependencies,
        workfiles=workfiles,
        binding_evidence=bindings,
        runner="agent-work/cells-worker-01/workfiles/" + PREFIX + "_checks.py",
        prepared_inputs=PREPARED + "/inputs.json",
        planned=planned,
        component_qualification_pending=True,
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_evaluations=0,
        reference_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
        automatic_launch=False,
        automatic_polling=False,
        automatic_followup=False,
    )
    write(WORK / (PREFIX + "_workqueue.json"), queue)
    print(
        json.dumps(
            dict(
                owned=len(owned),
                protected=len(protected),
                native=len(native["source_sha256"]),
                bindings=len(bindings),
                numerical_runs=0,
            )
        )
    )


if __name__ == "__main__":
    prepare()
