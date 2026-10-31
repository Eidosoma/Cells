"""Static protocol/lineage queue for new single-call event/mechanics composition."""

import copy
import json
from pathlib import Path

from betse_normal_ecm_event_mechanics_audit_tools import ROOT, sha, write

PREFIX = "betse_normal_ecm_event_mechanics"
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
EVENT = Path("/mnt/workspaces/Cells/betse-normal-ecm-event-join-prepared-20261031-01")
MECH = Path("/mnt/workspaces/Cells/betse-normal-ecm-mechanics-join-prepared-20261031-02")
PREPARED = "/mnt/workspaces/Cells/betse-normal-ecm-event-mechanics-prepared-20261031-01"


def row(path):
    return dict(path=str(path), sha256=sha(path))


def prepare():
    previous = json.loads((EVENT / "inputs.json").read_text())
    event_protocol = json.loads(
        (EVENT / "source/validation/betse/betse_normal_ecm_event_join_protocol.json").read_text()
    )
    mechanical = json.loads(
        (ROOT / "validation/betse/betse_normal_ecm_mechanics_join_protocol.json").read_text()
    )
    mechanical_base = json.loads(
        (ROOT / "validation/betse/betse_mechanics_join_protocol.json").read_text()
    )
    dependency = json.loads((WORK / (PREFIX + "_dependency_witness_02.json")).read_text())
    proof = json.loads((WORK / (PREFIX + "_AST_witness_01.json")).read_text())
    bindings = copy.deepcopy(previous["binding_evidence"])
    bindings.update(
        frozen_event01_inputs=row(EVENT / "inputs.json"),
        held_event01_preparation=row(
            "/mnt/workspaces/Cells/betse-normal-ecm-event-join-launch-preparation-20261031-01/PREPARATION.json"
        ),
        frozen_mechanics02_manifest=row(MECH / "manifest.json"),
        held_mechanics02_preparation=row(
            "/mnt/workspaces/Cells/betse-normal-ecm-mechanics-join-launch-preparation-20261031-02/PREPARATION.json"
        ),
        mechanics02_source_review=row(
            "/mnt/workspaces/Cells/betse-normal-ecm-mechanics-join-preflight-20261031-02/REVIEW.json"
        ),
        mechanics02_dependency_update=row(MECH / "dependency-update02.json"),
        ordinary_mechanics_source_closeout=row(
            "/mnt/workspaces/Cells/betse-mechanics-join-completion-review-20261031-02/REVIEW.json"
        ),
        saved_mechanics_finalizer_fix=row(
            "/mnt/workspaces/Cells/mechanics-finalizer-repair-20261031-01/preparation.json"
        ),
        reviewed_catalog04_inputs=dependency["catalog04_inputs"],
        reviewed_catalog04_guard=dependency["catalog04_review"],
        catalog04_preparation=row(
            "/mnt/workspaces/Cells/ecm-catalog-hot-cache-repair-20261031-01/preparation04.json"
        ),
        Chief03_source_review=row(
            "/mnt/workspaces/Cells/ecm-callback-repair-20261031-01/root-review-01/REVIEW.json"
        ),
        composition_source_AST=row(WORK / (PREFIX + "_AST_witness_01.json")),
        explicit_overlap_binding=row(WORK / (PREFIX + "_dependency_witness_02.json")),
    )
    planned = dict(
        checks=62,
        positive_three_call_histories=25,
        component_controls=10,
        new_composition_contexts=15,
        raw_source_limits=7,
        dependency_controls=26,
        corruption_controls=4,
        duplicate_baseline_histories=4,
        native_captures=36,
        conditional_points_per_positive_history=26,
        forms_per_history=52,
        new_positive_reference_forms=1300,
        duplicate_baseline_reference_forms=208,
        fresh_Decimal_reference_forms=1508,
        precision_levels=[100, 160],
        positive_completed_calls_per_implementation=75,
        duplicate_baseline_calls_per_implementation=12,
        carried_reference_forms=0,
        retained_qualification_passes=0,
        new_qualification_passes=0,
        enabled_flow_calls=0,
        dynamic_deformation_calls=0,
        completed_display_samples=0,
        physical_initializations=0,
        biological_cases=0,
    )
    scope = dict(
        supplied_state_only=True,
        ordinary_ECM_FULL_only=True,
        one_material_and_one_field_advance_per_call=True,
        actual_events_then_CaATP_GRN_channels_then_noise_then_mechanics=True,
        mechanics_before_deferred_material_and_field=True,
        actual_event_pressure_temperature=True,
        current_post_noise_primary_and_post_GRN_molecules=True,
        previous_field_current_charge_epoch=True,
        mechanical_DEC_view_separate_from_material_geometry=True,
        exact_common_owner_measure_centres_maps=True,
        supplied_mechanics_entry_cache=True,
        absent_disabled_flow_cold_stores_not_claimed_native_producers=True,
        held_zero_fluid_stores=True,
        enabled_flow=False,
        dynamic_deformation=False,
        cut_or_geometry_rebuild=False,
        maximum_field_cells=16,
        minimum_quartic_display_cells=25,
        native_calendar_sample_eligibility_preserved=True,
        sampling_policy="calendar_eligibility_only_explicit_display_refusal",
        completed_display_output=False,
        physical_initialization_or_full_native_solver=False,
        independent_carried_trajectory=False,
        physical_global_conservation_credit=False,
        component_qualification_pending=True,
        event01_and_ECM_mechanics02_scientific_passes_inherited=0,
        original_material39of40_still_failed=True,
    )
    native = copy.deepcopy(event_protocol["native_source"])
    for name, h in mechanical_base["native_source"]["source_sha256"].items():
        assert name not in native["source_sha256"] or native["source_sha256"][name] == h, name
        native["source_sha256"][name] = h
    protocol = dict(
        kind="cells.normal_ecm_event_mechanics_static_contract@1",
        status="static_preparation_unexecuted_unqualified",
        purpose=(
            "Resolve shared supplied owners and source epochs while adding steady mechanics "
            "after actual events and protein noise, without double material/field stepping"
        ),
        scope=scope,
        planned=planned,
        native_source=native,
        binding_evidence=bindings,
        acceptance=copy.deepcopy(event_protocol["acceptance"]),
        mechanics_acceptance=copy.deepcopy(mechanical["tolerances"]["unchanged_mechanics02"]),
        mechanics_budget_source_sha256=sha(
            ROOT / "validation/betse/betse_mechanics_join_checks.py"
        ),
        inherited_mechanics_divergence_category_disclosure=dependency[
            "explicit_prior_mechanics_divergence_category_change"
        ],
        new_budget_changes=False,
        new_numerical_equations=False,
        source_map="validation/betse/" + PREFIX + "_source_map.json",
        source_order=proof["original_native_order"],
        resources=dict(
            cpu=None,
            threads=1,
            gpu=False,
            max_command_seconds=480,
            max_process_tree_rss_bytes=2**30,
            min_available_host_memory_bytes=8 * 2**30,
            cpu_coordination=(
                "Only a separate requested and Root-coordinated numerical round may run"
            ),
        ),
        independent_reference=dict(
            fresh_subprocesses=True,
            production_and_scientific_imports_denied=True,
            actual_archived_inputs=True,
            mechanics_raw_Decimal_tree_preserved=True,
            runtime_inventory_every_mode=True,
            self_resolution_fraction=0.1,
            carried_reference_forms=0,
        ),
        failure_retention=dict(
            full_native_event_CaATP_GeRN_noise_mechanics_partial=True,
            native_mechanics_constructor_locals_and_partial_view=True,
            owned_initial_parent_and_every_reached_callback=True,
            native_source_guards_distinct_from_stricter_owned_admission=True,
            zero_accuracy_credit=True,
            sampled_display_refusal_preserves_reached_post_field_and_mechanics_parent=True,
        ),
        explicit_dependency_binding=dependency,
        old_frozen_and_live_component_files_edited=False,
        automatic_launch=False,
        automatic_polling=False,
        automatic_followup=False,
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_evaluations=0,
        reference_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
    )
    mapping = dict(
        kind="cells.event_mechanics_source_map@1",
        scope=scope,
        source_AST_proof=proof,
        explicit_dependency_witness=bindings["explicit_overlap_binding"],
        native_source_sha256=native["source_sha256"],
        no_new_scientific_equations=True,
        no_new_budget_changes=True,
        scientific_imports=0,
        numerical_runs=0,
    )
    protocol_path = ROOT / "validation/betse" / (PREFIX + "_protocol.json")
    map_path = ROOT / "validation/betse" / (PREFIX + "_source_map.json")
    write(protocol_path, protocol)
    write(map_path, mapping)
    owned = [str(p.relative_to(ROOT)) for p in (ROOT / "src/cells/processes").glob(PREFIX + "*.py")]
    owned += [
        str(p.relative_to(ROOT))
        for p in (ROOT / "validation/betse").glob(PREFIX + "*")
        if p.is_file()
    ]
    owned += ["tests/unit/test_" + PREFIX + ".py"]
    owned += [
        "agent-work/cells-worker-01/workfiles/" + PREFIX + suffix
        for suffix in (
            "_checks.py",
            "_audit_tools.py",
            "_ast_audit.py",
            "_dependency_audit.py",
            "_reporting_metadata_check.py",
            "_static_audit.py",
        )
    ]
    protected = copy.deepcopy(dependency["protected_sha256"])
    for relative, h in protocol["acceptance"]["inherited_budget_source_sha256"].items():
        assert relative not in protected or protected[relative] == h
        protected[relative] = h
    workfiles = sorted(
        {str(p.relative_to(ROOT)) for p in WORK.glob("*" + PREFIX + "*") if p.is_file()}
        | {
            "agent-work/cells-worker-01/workfiles/BETSE_NORMAL_ECM_EVENT_MECHANICS_NOTES.md",
            "agent-work/cells-worker-01/workfiles/" + PREFIX + "_reporting_metadata_check_01.json",
            "agent-work/cells-worker-01/workfiles/" + PREFIX + "_static_witness_01.json",
        }
    )
    q = dict(
        kind="cells.event_mechanics_workqueue@1",
        status="static_preparation_only_pending_Chief_review",
        owned=sorted(owned),
        owned_sha256={p: sha(ROOT / p) for p in owned},
        protected_sha256=protected,
        workfiles=workfiles,
        reference_closure=dependency["reference_closure"],
        scientific_import_closure=dependency["scientific_import_closure"],
        explicit_dependency_binding=dependency,
        planned=planned,
        binding_evidence=bindings,
        freeze_prerequisites={
            k: bindings[k]
            for k in (
                "Chief03_source_review",
                "reviewed_catalog04_guard",
                "mechanics02_source_review",
            )
        },
        runner="agent-work/cells-worker-01/workfiles/" + PREFIX + "_checks.py",
        prepared_inputs=PREPARED + "/inputs.json",
        authorized_physical_helper_refactor=previous["authorized_physical_helper_refactor"],
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_evaluations=0,
        reference_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
        component_qualification_pending=True,
        automatic_launch=False,
        automatic_polling=False,
        automatic_followup=False,
    )
    write(WORK / (PREFIX + "_workqueue.json"), q)
    print(
        json.dumps(
            dict(
                status=q["status"],
                owned=len(owned),
                protected=len(protected),
                native_sources=len(native["source_sha256"]),
                bindings=len(bindings),
            )
        )
    )


if __name__ == "__main__":
    prepare()
