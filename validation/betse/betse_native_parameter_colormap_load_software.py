"""Freeze the guarded original four-store continuation and run native-blocked software controls."""

import argparse
import ast
import json
import os
import resource
import runpy
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

from validation import source_snapshot as snapshot
from validation.betse import betse_native_phase_callbacks_software as callbacks
from validation.betse import betse_native_simulator_construction_software as inherited

FILE = "validation/betse/betse_native_parameter_colormap_load_software.py"
TEST = "tests/unit/test_betse_native_parameter_colormap_load.py"
CONTEXT_TEST = "tests/unit/test_betse_native_parameter_colormaps.py"
OWNED = (
    "src/cells/processes/betse_native_parameter_colormap_runtime.py",
    "src/cells/processes/betse_native_parameter_colormap_load.py",
    FILE,
    TEST,
    CONTEXT_TEST,
)
CONTEXT_TARGETS = (
    "test_literal_four_statements_compile_without_running_source_or_getters",
    "test_context_compiler_preserves_import_future_decorator_and_nested_class_code",
    "test_context_body_rewrite_preserves_whole_class_module_and_original_header",
    "test_context_body_rewrite_refuses_any_header_or_source_span_change",
    "test_context_compiler_requires_exact_declared_original_node",
    "test_context_compiler_refuses_bounded_source_or_traversal_exhaustion",
    "test_undecorated_context_authentication_binds_exact_lexical_qualname",
    "test_decorated_core_uses_same_complete_context_without_decorator_or_helper_calls",
    "test_context_compiler_and_keyword_defaults_refuse_entry_and_issued_lifetime_drift",
    "test_context_compiler_rechecks_contract_after_source_read_before_compilation",
    "test_native_runtime_and_reached_dispatch_binding_without_lookup",
)
TARGETS = (
    "test_prepare_shaped_catch_retains_canonical_primary_after_recovery_sentinel",
    "test_toy_getter_line_mutation_is_rejected_before_foreign_dispatch_without_owner",
    "test_pinned_reference_is_present_without_import_or_factory",
    "test_gates_hold_before_any_parent_runtime_or_work",
    "test_complete_guarded_conditional_four_stores_same_p_and_real_return_transport",
    "test_source_capture_failures_keep_actual_prefix_primary_and_returns",
    "test_current_successor_rejects_parameter_return_and_evidence_drift",
    "test_reentrant_attempt_cannot_double_enter_or_publish_success",
    "test_inherited_return_unwind_failure_preserves_original_source_cause",
    "test_lazy_missing_runtime_refuses_before_original_invocation",
    "test_metadata_binding_refuses_changed_body_before_active_or_completed_call",
    "test_named_missing_name_helper_authenticates_before_any_delegate",
    "test_numpy_copy_export_substitution_refuses_without_any_delegate",
    "test_numpy_argument_delegate_requires_actual_direct_owned_edge",
    "test_undecorated_outer_body_cannot_hide_behind_canonical_wrapped_helper",
    "test_undecorated_helper_defaults_and_delegates_are_exact",
    "test_numpy_actual_implementation_role_is_distinct_from_unordered_gc_membership",
    "test_numpy_empty_gc_edges_require_exact_observed_origin",
    "test_registry_dispatch_retarget_refuses_before_attribute_or_load_entry",
    "test_registry_rechecks_surface_after_inherited_call_hook",
    "test_inherited_getter_line_mutation_refuses_before_foreign_attribute_body",
    "test_inherited_trace_unwind_error_retains_actual_primary_and_cause",
    "test_matplotlib_guard_cleanup_keeps_primary_and_all_independent_attempts",
    "test_matplotlib_guard_unchanged_valid_cleanup_requires_evidence_return",
    "test_guard_attachment_rejection_preserves_exact_primary_and_secondary_failure",
    "test_guard_writer_hook_changes_are_recovered_after_callback_and_never_clean",
    "test_nested_matplotlib_guard_blocks_real_import_attempt_and_retains_primary",
    "test_runner_refuses_missing_or_foreign_target_before_worker",
    "test_runner_forwards_one_declared_target_to_existing_guard_and_child",
    "test_guard_failed_recovery_never_enters_attachment_formatting_or_writer",
    "test_source_unwind_hook_loss_and_restore_rejection_preserve_original_primary",
    "test_historical_metadata_body_trim_uses_complete_original_module_context",
    "test_canonical_full_module_helper_agrees_with_actual_inventory_without_entry",
    "test_isolated_import_context_cannot_be_accepted_as_an_alternate_canonical_helper",
    "test_constructor_and_copy_authentication_require_complete_module_and_class_context",
    *CONTEXT_TARGETS,
)
REFERENCE_GUARD_SHA256 = "0b274dc8084cc26119bb11d0c0c1deeedeaf13d71bc25e72b07e320c5ccd8666"


def classify_reference_guard(case, record, *, native_record, pytest_status, fixture_sha256):
    """Review pre-return evidence using this exact fixture's teardown contract.

    The persisted flag deliberately remains False. Successful full pytest
    teardown supplies the additional evidence required by that pinned source;
    this classification grants no native or parent authority.
    """
    if type(fixture_sha256) is not str or fixture_sha256 != REFERENCE_GUARD_SHA256:
        raise ValueError("Exact reference-guard fixture source required")
    if type(pytest_status) is not int or pytest_status != 0:
        raise ValueError("Successful full pytest teardown evidence required")
    if type(case) is not ET.Element or type(case.tag) is not str or case.tag != "testcase":
        raise ValueError("Actual complete JUnit testcase required")
    if type(case.get("name")) is not str or not case.get("name"):
        raise ValueError("Named complete JUnit testcase required")
    for child in case:
        if type(child.tag) is not str or child.tag in ("failure", "error", "skipped"):
            raise ValueError("Successful full pytest teardown evidence required")
    native_fields = (
        "nodeid",
        "attempted",
        "flattened_attempted",
        "fixture_setup_completed",
        "inherited_receipt_complete",
        "inherited_generator_closed",
        "profile_restored",
        "trace_restored",
        "cleanup_error_stages",
        "actual_native_numeric_parser_RNG_path_writes",
        "actual_event_source_numeric_parser_RNG_file_entries",
        "final_blocked_attempt_count",
    )
    if type(native_record) is not dict or any(name not in native_record for name in native_fields):
        raise ValueError("Complete post-teardown native-guard evidence required")
    if type(native_record["nodeid"]) is not str or native_record[
        "nodeid"
    ] != TEST + "::" + case.get("name"):
        raise ValueError("Exact case/native-guard association required")
    for name in (
        "fixture_setup_completed",
        "inherited_receipt_complete",
        "inherited_generator_closed",
        "profile_restored",
        "trace_restored",
    ):
        if native_record[name] is not True:
            raise ValueError("Successful full native-guard teardown evidence required")
    for name in ("attempted", "flattened_attempted", "cleanup_error_stages"):
        if type(native_record[name]) is not list or native_record[name]:
            raise ValueError("Native guard recorded attempts or cleanup failures")
    for name in (
        "actual_native_numeric_parser_RNG_path_writes",
        "actual_event_source_numeric_parser_RNG_file_entries",
        "final_blocked_attempt_count",
    ):
        if type(native_record[name]) is not int or native_record[name] != 0:
            raise ValueError("Native guard recorded actual entries")
    required = (
        "attempts",
        "profile_restored",
        "trace_restored",
        "final_profile_identity",
        "final_trace_identity",
        "expected_profile_identity",
        "expected_trace_identity",
        "primary_type",
        "primary_identity",
        "primary_cause_identity",
        "cleanup_errors",
        "actual_import_factory_entries",
        "clean_guard",
        "certification",
        "hook_evidence_phase",
    )
    if type(record) is not dict or any(name not in record for name in required):
        raise ValueError("Complete pre-return reference-guard evidence required")
    if type(record["attempts"]) is not list or record["attempts"]:
        raise ValueError("Reference guard recorded forbidden attempts")
    if type(record["cleanup_errors"]) is not list or record["cleanup_errors"]:
        raise ValueError("Reference guard cleanup evidence failed")
    if any(
        record[name] is not None
        for name in ("primary_type", "primary_identity", "primary_cause_identity")
    ):
        raise ValueError("Reference guard retained a primary failure")
    for kind in ("profile", "trace"):
        actual, expected = (
            record["final_" + kind + "_identity"],
            record["expected_" + kind + "_identity"],
        )
        if (
            record[kind + "_restored"] is not True
            or type(actual) is not int
            or type(expected) is not int
            or actual <= 0
            or actual != expected
        ):
            raise ValueError("Reference guard hook identity mismatch")
    if (
        type(record["actual_import_factory_entries"]) is not int
        or record["actual_import_factory_entries"] != 0
    ):
        raise ValueError("Reference guard recorded actual entries")
    if (
        record["clean_guard"] is not False
        or type(record["certification"]) is not str
        or record["certification"] != "Successful cleanup return is also required"
        or type(record["hook_evidence_phase"]) is not str
        or record["hook_evidence_phase"]
        != "Before evidence callback; returned final samples also required"
    ):
        raise ValueError("Declared pre-return guard evidence phase required")
    return dict(
        case=case.get("name"),
        classification="passed_case_with_pinned_pre_return_guard_contract",
        persisted_record_is_final_certificate=False,
        successful_full_teardown_required=True,
        fixture_sha256=fixture_sha256,
        native_or_parent_admission=False,
    )


def prepare(repository, directory):
    repo = Path(repository).resolve(strict=True)
    if Path(__file__).resolve() != repo / FILE:
        raise ValueError("Prepare current Git checkout only")
    directory = inherited.separate(directory, repo, Path("/mnt/workspaces/Cells/betse-v1.5.0"))
    directory.mkdir(parents=True, exist_ok=False)
    # Freeze without loading the production dependency tree under the metadata
    # cap. The existing 1 GiB child captures the actual source plan before tests.
    source = "src/cells/processes/betse_native_parameter_colormap_load.py"
    tree = ast.parse((repo / source).read_bytes())
    laws = [
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "LAW_ID"
    ]
    if len(laws) != 1 or type(laws[0]) is not str:
        raise ValueError("One literal source law required")
    plan = dict(
        source_plan_deferred=True,
        source_plan_capture="verified_frozen_child_before_tests",
        source=source,
        law=laws[0],
        native_or_owner_execution=False,
    )
    files = runpy.run_path(str(repo / inherited.CLOSURE_TOOL))["closure"](repo, list(OWNED))
    for name in ("pyproject.toml", "tests/__init__.py", inherited.CLOSURE_TOOL):
        files[name] = snapshot.digest(repo / name)
    manifest = snapshot.freeze(repo, directory / "source", {n: n for n in files})
    snapshot.write_json(directory / "source-plan.json", plan)
    snapshot.write_json(
        directory / "inputs.json",
        dict(
            law=laws[0],
            held=True,
            automatic_launch=False,
            snapshot=inherited.ref(directory / "source/SNAPSHOT.json"),
            source_plan=inherited.ref(directory / "source-plan.json"),
            repository=str(repo),
            git_revision=manifest["git_revision"],
            owned_files={n: manifest["files"][n]["sha256"] for n in OWNED},
            external_runtime_paths=[
                str(Path(p).resolve())
                for p in os.environ.get("PYTHONPATH", "").split(os.pathsep)
                if p and not Path(p).resolve().is_relative_to(repo)
            ],
            actual_colormap_lookup_or_constructor_or_INIT_release=False,
            remains=(
                "Actual registry owner and original retained runtime; "
                "original four calls require release; "
                "source is implemented behind release; "
                "next contiguous options/constants/ions remain separate"
            ),
            resources=dict(
                cpu=0,
                threads=1,
                metadata_bytes=512 * 2**20,
                software_bytes=2**30,
                wall_seconds=480,
                host_reserve_bytes=8 * 2**30,
            ),
        ),
    )
    return dict(
        inputs=inherited.ref(directory / "inputs.json"), files=len(manifest["files"]), held=True
    )


def _target(target):
    if type(target) is not str or target not in TARGETS:
        raise ValueError("Choose one declared bounded software target")
    return (CONTEXT_TEST if target in CONTEXT_TARGETS else TEST) + "::" + target


def child(output, *, target):
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    root = Path(__file__).resolve().parents[2]
    manifest = snapshot.verify(root)
    from cells.processes import betse_native_parameter_colormap_load as stage

    source = "src/cells/processes/betse_native_parameter_colormap_load.py"
    if (
        Path(stage.__file__).resolve() != root / source
        or snapshot.digest(root / source) != manifest["files"][source]["sha256"]
    ):
        raise ValueError("Actual frozen colormap producer required")
    snapshot.write_json(
        output / "source-plan-observed.json",
        dict(
            source=source,
            sha256=manifest["files"][source]["sha256"],
            source_plan=stage.source_plan(),
            source_plan_capture="verified_frozen_child_before_tests",
            native_or_owner_execution=False,
        ),
    )
    return callbacks.delegate(inherited.child, TEST=_target(target))(output)


def software(packet, output, *, target):
    _target(target)  # Refuse before directories or a worker can be created.

    def run_bounded(command, **kwargs):
        return inherited.guard.run_bounded([*command, "--target", target], **kwargs)

    return callbacks.delegate(
        inherited.software, FILE=FILE, guard=SimpleNamespace(run_bounded=run_bounded)
    )(packet, output)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prepare", type=Path)
    p.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[2])
    p.add_argument("--software", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--child", type=Path, help=argparse.SUPPRESS)
    p.add_argument("--target", choices=TARGETS)
    a = p.parse_args()
    if a.child:
        if not a.target:
            p.error("--child requires one bounded --target")
        return child(a.child, target=a.target)
    if a.prepare and not a.software:
        print(json.dumps(prepare(a.repository, a.prepare)))
        return 0
    if a.software and a.output and not a.prepare:
        if not a.target:
            p.error("--software requires one bounded --target")
        result = software(a.software, a.output, target=a.target)
        print(json.dumps(result))
        return int(result["returncode"])
    p.error("Choose --prepare or --software with --output")


if __name__ == "__main__":
    raise SystemExit(main())
