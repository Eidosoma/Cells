# ruff: noqa: E501
"""Draft narrow lifecycle evidence repairs in new files; no scientific execution."""

import ast
import json
import shutil

from betse_normal_ecm_reviewed_successors_resources import BASE, WORK, sha

PREFIX = "betse_normal_ecm_reviewed_successors"
OLD = WORK / (PREFIX + "_proposal_01")
OUT = WORK / (PREFIX + "_proposal_02")
TEST = "tests/unit/test_betse_normal_ecm_run_lifecycle.py"
NATIVE = "validation/betse/betse_normal_ecm_run_lifecycle_native.py"
PARENT = BASE / "betse-normal-ecm-run-lifecycle-prepared-20261031-01"

RAW_WITNESS = """        component_partial = ions.data(failed["component_partial"])
        assert component_partial["stage"] == "event_noise_mechanics_material_field"
        event_partial = component_partial["event_partial"]
        assert event_partial["stage"] == "event_material_network_noise_field"
        assert event_partial["available_event_stores"]
        source = captured["composition"]
        leaf = error
        while leaf.__cause__ is not None:
            leaf = leaf.__cause__
        assert failed["stage"] == "component_call"
        assert failed["attempt"]["call"]["call_index"] == accepted.cursor
        if case == "events_zero_width":
            witness = "events_zero_width_store_equality"
            assert type(leaf) is ZeroDivisionError and "division by zero" in str(leaf)
            assert accepted.cursor == 0 and source["status"] == "source_refused"
            assert source["failure"]["stage"] == "events"
            assert source["failure"]["type"] == "ZeroDivisionError"
            exact(event_partial["available_event_stores"], source["history"][0]["events"]["after"])
            assert not event_partial["available"].get("noise")
            assert not component_partial["available"].get("mechanics_input")
        elif case == "network_refuses":
            witness = "GRN_refusal_before_noise_unchanged_RNG"
            assert type(leaf).__name__ == "BetseSimUnstableException"
            assert "Your simulation has become unstable" in str(leaf)
            assert accepted.cursor == 0 and source["status"] == "source_refused"
            assert source["failure"]["stage"] == "material_network"
            assert source["failure"]["type"] == type(leaf).__name__
            assert not event_partial["available"].get("noise")
            assert not event_partial["available"].get("before_noise")
            assert not component_partial["available"].get("mechanics_input")
            declared_rng = inputs["composition_inputs"]["event_inputs"]["prepared_rng"]["manifest"]
            exact(source["history"][0]["noise_stream_after"], declared_rng)
            exact(run.composition.event.random_source.native_stream_manifest(
                accepted.active.events.noise_stream), declared_rng)
            exact(event_partial["catalog_trace"]["before"], source["history"][0]["network"]["before"])
        elif case == "late_negative_temperature":
            witness = "negative_event_temperature_call2_before_material_drive"
            assert type(leaf) is ValueError
            assert str(leaf) == "Require explicit finite source scalar: runtime_temperature_K"
            assert accepted.cursor == 2 and event_partial["available_event_stores"]["T"] < 0
            assert event_partial["available"]["events"]["source_completed"] is True
            assert event_partial["available"]["before_events"]["source_time_s"] == parent.entry.events.clock.source_times_s[2]
            exact(event_partial["available_event_stores"], source["history"][2]["events"]["after"])
            assert not component_partial["available"].get("mechanics_input")
        else:
            assert case == "mechanics_overflow"
            witness = "nonfinite_mechanics_trial_before_material_commit"
            assert type(leaf) is run.composition.mechanics.MechanicsRejected
            assert str(leaf) == "Nonfinite complete mechanics output"
            assert accepted.cursor == 0 and component_partial["available"]["mechanics_failure"] is not None
            assert event_partial["available"]["noise"]["source_completed"] is True
            assert event_partial["available"].get("material_parent") is None
            trial = component_partial["available"]["mechanics_failure"]
            assert any(not inherited.np.isfinite(value).all() for value in trial["candidate"]["cache"].values())
            assert source["mechanics_history"] and source["mechanics_history"][0]["complete_available_buffers"]
            assert any(not inherited.np.isfinite(value).all() for key, value in source["mechanics_history"][0]["candidate"].items() if not key.startswith("display_"))
        archive(tmp_path, case + "-case-specific-boundary", dict(
            component_partial=component_partial, native_capture=source,
            named_cause_type=type(leaf).__name__, named_cause_message=str(leaf), witness=witness))
"""


def replace(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new, 1)


def put(relative, text):
    path = OUT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        stream.write(text)
    return path


def prepare():
    OUT.mkdir(exist_ok=False)
    for relative in (
        "validation/betse/betse_normal_ecm_catalog_join_reference.py",
        "validation/betse/betse_normal_ecm_event_join_reference.py",
    ):
        target = OUT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(OLD / relative, target)
    before = (OLD / TEST).read_text()
    test = replace(
        before,
        '        assert captured["composition"]["history"]\n',
        '        assert captured["composition"]["history"]\n' + RAW_WITNESS,
    )
    test = replace(
        test,
        '            native_source_status=captured["composition"]["status"],\n',
        """            native_source_status=captured["composition"]["status"],
            case_specific_witness=witness,
            case_specific_boundary_verified=True,
            named_cause_type=type(leaf).__name__,
            named_cause_message=str(leaf),
""",
    )
    old_tree, new_tree = ast.parse(before), ast.parse(test)
    for old, new in zip(old_tree.body, new_tree.body, strict=True):
        if isinstance(old, ast.FunctionDef) and old.name == "test_headless_raw":
            continue
        assert ast.dump(old, include_attributes=False) == ast.dump(new, include_attributes=False)
    test_path = put(TEST, test)
    reader = (OLD / "lifecycle-observer-reader.py").read_text()
    reader = replace(
        reader,
        '        reports.append(dict(path=name, **row))\n    found = {p.name: p for p in base.glob("observer-*.json")}\n',
        """        witness, cause, fragment = {
            "events_zero_width": ("events_zero_width_store_equality", "ZeroDivisionError", "division by zero"),
            "network_refuses": ("GRN_refusal_before_noise_unchanged_RNG", "BetseSimUnstableException", "Your simulation has become unstable"),
            "late_negative_temperature": ("negative_event_temperature_call2_before_material_drive", "ValueError", "Require explicit finite source scalar: runtime_temperature_K"),
            "mechanics_overflow": ("nonfinite_mechanics_trial_before_material_commit", "MechanicsRejected", "Nonfinite complete mechanics output"),
        }[case]
        if not (
            row["case_specific_boundary_verified"] is True
            and row["case_specific_witness"] == witness
            and row["named_cause_type"] == cause
            and fragment in row["named_cause_message"]
        ):
            raise ValueError("Raw control did not reach its named source/owned boundary")
        reports.append(dict(path=name, **row))
    found = {p.name: p for p in base.glob("observer-*.json")}
""",
    )
    reader_path = put("lifecycle-evidence-reader.py", reader)
    native_before = (PARENT / "source" / NATIVE).read_text()
    native = replace(native_before, "import sys\n", "import sys\nimport traceback\n")
    native = replace(
        native, "def evaluate(inputs):\n", "def evaluate(inputs, *, retain_reached=None):\n"
    )
    # Create the complete wrapper immediately after the component returns. The
    # retain hook only stores a Python reference; it performs no scientific work.
    original_return = """    return dict(
        clock=clock,
        composition=captured,
        RNG_unchanged=captured["RNG_unchanged"],
        source_scope=(
            "Captured original component bodies and explicit time slices; no full native lifecycle"
        ),
        native_init_load_run_sim_core_write2storage_pickle_called=False,
        native_full_phase_completed=False,
        physical_initialization_claim=False,
    )
"""
    assert native.count(original_return) == 1
    native = native.replace(original_return, "    return reached\n", 1)
    reached = original_return.replace("    return dict(\n", "    reached = dict(\n", 1)
    native = replace(
        native,
        "    captured = component.evaluate(declared)\n",
        "    captured = component.evaluate(declared)\n"
        + reached
        + """    if retain_reached is not None:
        retain_reached(reached)
""",
    )
    start = native.index("    result = (\n", native.index("def main():"))
    stop = native.index('\n\n\nif __name__ == "__main__":', start)
    old_tail = native[start:stop]
    new_tail = """    reached = {}

    def retain_reached(value):
        reached.update(value)

    try:
        result = (
            dict(clock=clock_profile(inputs), RNG_unchanged=True, clock_only=True)
            if args.clock_only
            else evaluate(inputs, retain_reached=retain_reached)
        )
        retain_reached(result)
        after_rng = np.random.get_state()
        result["RNG_unchanged"] = bool(
            before_rng[0] == after_rng[0]
            and np.array_equal(before_rng[1], after_rng[1])
            and before_rng[2:] == after_rng[2:]
        )
        loaded = [name for name in sys.modules if name.split(".")[0] in blocked]
        assert not loaded
        result.update(
            production_imports_denied=True, loaded_production_modules=loaded, runtime=inventory()
        )
        component.archives.write_archive(args.output, result)
    except BaseException as error:
        if reached:
            failed_output = args.output.with_name(args.output.name + "-failed-reached")
            component.archives.write_archive(failed_output, dict(
                reached_capture=reached,
                failure=dict(type=type(error).__name__, message=str(error), traceback=traceback.format_exc()),
                failed_after_capture_return=True, native_full_phase_completed=False,
                physical_initialization_claim=False, qualification_credit=False,
            ))
        raise
"""
    assert "component.archives.write_archive(args.output, result)" in old_tail
    native = native[:start] + new_tail + native[stop:]
    native_tree = ast.parse(native)
    calls = [ast.unparse(n.func) for n in ast.walk(native_tree) if isinstance(n, ast.Call)]
    assert calls.count("component.evaluate") == 1
    native_path = put(NATIVE, native)
    result = dict(
        kind="cells.explicit_ECM_successor_lifecycle_evidence_proposals@1",
        status="ready_for_independent_static_review_unrun",
        prior_proposal=dict(
            path=str(OLD / "source-proposals.json"), sha256=sha(OLD / "source-proposals.json")
        ),
        files_sha256={
            TEST: sha(test_path),
            NATIVE: sha(native_path),
            "lifecycle-evidence-reader.py": sha(reader_path),
        },
        observer_per_call_paths_and_exact_leaf_witness_retained=True,
        raw_case_specific_boundary_witnesses=[
            "events_zero_width_store_equality",
            "GRN_refusal_before_noise_unchanged_RNG",
            "negative_event_temperature_call2_before_material_drive",
            "nonfinite_mechanics_trial_before_material_commit",
        ],
        named_root_causes_and_unrelated_failure_rejection_required=True,
        complete_native_clock_component_retained_before_correspondence_assertions=True,
        exception_path_writes_full_capture_then_rethrows=True,
        inherited_component_source_unchanged=True,
        unchanged_test_functions_except_raw_and_observer=True,
        original_lifecycle01_preserved=True,
        scientific_equations_roster_and_tolerances_unchanged=True,
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_evaluations=0,
        reference_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
        new_or_retained_qualification_passes=0,
    )
    path = put(
        "lifecycle-evidence-proposals.json",
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
    )
    print(
        json.dumps(
            dict(
                proof=str(path),
                sha256=sha(path),
                test_sha256=sha(test_path),
                native_sha256=sha(native_path),
                numerical_runs=0,
            )
        )
    )


if __name__ == "__main__":
    prepare()
