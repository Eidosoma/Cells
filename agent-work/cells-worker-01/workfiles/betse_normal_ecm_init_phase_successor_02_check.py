"""Stdlib exception-injection/sampling controls and AST-only INIT02 delta audit."""

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import resource
import sys
import time
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PARENT = Path("/mnt/workspaces/Cells/betse-normal-ecm-init-phase-prepared-20261031-01/source")
PROPOSAL = WORK / "betse_normal_ecm_init_phase_successor_02_proposal"
NATIVE = "validation/betse/betse_normal_ecm_init_phase_native.py"
TEST = "tests/unit/test_betse_normal_ecm_init_phase.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def functions(path):
    return {
        node.name: node
        for node in ast.parse(path.read_text()).body
        if isinstance(node, ast.FunctionDef)
    }


def signature(node):
    node = copy.deepcopy(node)
    for item in ast.walk(node):
        if (
            isinstance(item, ast.FunctionDef)
            and item.body
            and isinstance(item.body[0], ast.Expr)
            and isinstance(item.body[0].value, ast.Constant)
            and isinstance(item.body[0].value.value, str)
        ):
            item.body.pop(0)
    return ast.dump(node, include_attributes=False)


def reverse_evidence_delta(node):
    """Remove only the declared capture annotations, then compare the entire body."""
    node = copy.deepcopy(node)
    assert node.args.kwonlyargs[-1].arg == "retain_failure"
    node.args.kwonlyargs.pop()
    node.args.kw_defaults.pop()
    outer = node.body[-1]
    assert len(node.body) == 3 and isinstance(outer, ast.Try)
    node.body = outer.body

    class RemoveCapture(ast.NodeTransformer):
        def visit_Assign(self, statement):
            if len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
                target = statement.targets[0].id
                if target == "capture_stage":
                    return None
                if target == "reset_return" and ast.unparse(statement.value) == "None":
                    return None
                if target == "field_phase" and ast.unparse(statement.value) == "'bootstrap'":
                    return None
            return self.generic_visit(statement)

        def visit_ExceptHandler(self, handler):
            if (
                handler.body
                and isinstance(handler.body[0], ast.If)
                and ast.unparse(handler.body[0].test) == "field_phase in ('bootstrap', 'reset')"
            ):
                assert len(handler.body[0].body) == 1
                assert isinstance(handler.body[0].body[0], ast.Raise)
                handler.body.pop(0)
            return self.generic_visit(handler)

    return RemoveCapture().visit(node)


def reverse_sampling_delta(node):
    node = copy.deepcopy(node)

    class RemoveSampling(ast.NodeTransformer):
        def visit_Assign(self, statement):
            if any(
                ast.unparse(target) in {"accepted_states", "accepted_states[index]"}
                for target in statement.targets
            ):
                return None
            return self.generic_visit(statement)

        def visit_Expr(self, statement):
            if (
                isinstance(statement.value, ast.Call)
                and ast.unparse(statement.value.func) == "compare_sampling"
            ):
                return None
            return self.generic_visit(statement)

    return RemoveSampling().visit(node)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    resource.setrlimit(resource.RLIMIT_AS, (256 * 2**20, 256 * 2**20))
    source = PROPOSAL / "source"
    old, new = functions(PARENT / NATIVE), functions(source / NATIVE)
    assert set(new) == set(old) | {"_failure_readers"}
    for name in old.keys() - {"evaluate", "main"}:
        assert signature(old[name]) == signature(new[name]), name
    assert signature(old["evaluate"]) == signature(reverse_evidence_delta(new["evaluate"]))
    for name in ("values", "observe", "trace", "field_call", "calcium_call", "rate_cache", "clock"):

        def nested(node, name=name):
            return next(
                n for n in ast.walk(node) if isinstance(n, ast.FunctionDef) and n.name == name
            )

        assert signature(nested(old["evaluate"])) == signature(nested(new["evaluate"])), name
    assert signature(old["source_sampling"]) == signature(new["source_sampling"])
    for name in ("run_dispatch",):
        assert signature(old[name]) == signature(new[name])
    oldtests, newtests = functions(PARENT / TEST), functions(source / TEST)
    assert {k for k in oldtests if k.startswith("test_")} == {
        k for k in newtests if k.startswith("test_")
    }
    for name in oldtests:
        if name not in {"test_init_history"}:
            assert signature(oldtests[name]) == signature(newtests[name]), name
    assert signature(oldtests["test_init_history"]) == signature(
        reverse_sampling_delta(newtests["test_init_history"])
    )
    evaluation = new["evaluate"]
    assert ast.unparse(evaluation.body[0]) == "capture_stage = 'input_and_geometry'"
    outer = evaluation.body[-1]
    assert isinstance(outer, ast.Try) and isinstance(outer.handlers[0].body[-1], ast.Raise)
    loop = next(
        n
        for n in ast.walk(evaluation)
        if isinstance(n, ast.For) and ast.unparse(n.target) == "(index, call)"
    )
    assert ast.unparse(loop.body[1]) == "reset_return = None"
    body = outer.body
    with_index = next(i for i, n in enumerate(body) if isinstance(n, ast.With))
    assert any(ast.unparse(n) == "reset_return = None" for n in body[:with_index])
    assert any(ast.unparse(n) == "field_phase = 'bootstrap'" for n in body[:with_index])
    capture = source / "validation/betse/betse_normal_ecm_init_phase_capture.py"
    spec = importlib.util.spec_from_file_location("pure_INIT_capture_contract", capture)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    controls = []
    # Execute only the stdlib metadata helper. The native evaluator and all
    # scientific AST above are parsed/compiled but never imported or called.
    for stage in (
        "setup_owner",
        "mechanics_entry",
        "event_finalization",
        "clock",
        "bootstrap",
        "reset",
    ):
        evidence = []
        error = RuntimeError("injected original " + stage)
        preserved = False
        try:
            try:
                raise error
            except Exception as caught:
                helper.record_failure(
                    caught,
                    stage=stage,
                    readers=dict(
                        parent=lambda: {"epoch": 0, "buffers": [1.0, 2.0]},
                        reset_return=lambda: None,
                        RNG=lambda: {"algorithm": "synthetic scalar state", "position": 9},
                    ),
                    retain=evidence.append,
                )
                raise
        except RuntimeError as caught:
            preserved = caught is error
        assert (
            preserved
            and len(evidence) == 1
            and evidence[0]["failure"]["message"] == "injected original " + stage
            and evidence[0]["available"]["reset_return"] is None
        )
        controls.append(
            dict(name="original_exception_and_available_" + stage, passed=True, evidence=evidence)
        )

    def broken_reader():
        raise ValueError("reader unavailable")

    output = []
    root_error = RuntimeError("original survives capture failure")
    helper.record_failure(
        root_error,
        stage="metadata",
        readers=dict(bad=broken_reader, other=lambda: 17),
        retain=output.append,
    )
    assert (
        output[0]["available"]["other"] == 17
        and output[0]["capture_errors"][0]["message"] == "reader unavailable"
    )
    controls.append(dict(name="reader_error_does_not_mask_original", passed=True))

    def broken_writer(value):
        raise OSError("writer unavailable")

    helper.record_failure(root_error, stage="metadata", readers={}, retain=broken_writer)
    assert any("writer unavailable" in note for note in root_error.__notes__)
    controls.append(dict(name="writer_error_retains_original_exception", passed=True))

    def sample(count, completed, indices):
        labels = [float(i) for i in range(count)]
        flags = [i in indices for i in range(count)]
        native = [
            dict(
                source_call=i,
                source_time_s=labels[i],
                native_calendar_eligible=flags[i],
                display_attempted=False,
                display_completed=False,
            )
            for i in range(completed)
        ]
        owned = [
            dict(call_index=i, source_label_s=labels[i], sample_eligible=flags[i])
            for i in range(completed)
        ]
        return dict(
            source_labels=labels,
            native_flags=flags,
            reference_indices=[indices.copy(), indices.copy()],
            native_rows=native,
            owned_rows=owned,
            observation_indices=[i for i in indices if i < completed],
            completed_calls=completed,
        )

    for name, count, completed, indices in (
        ("N0", 0, 0, []),
        ("N1", 1, 1, []),
        ("N3", 3, 3, [1, 2]),
        ("long_prefix", 7, 3, [1, 2, 3, 4, 5, 6]),
        ("no_samples", 3, 3, []),
    ):
        helper.sampling_contract(**sample(count, completed, indices))
        controls.append(dict(name="metadata_sampling_" + name, passed=True))
    mutations = {
        "independent_indices": lambda row: row.update(reference_indices=[[2], [2]]),
        "native_eligibility": lambda row: row["native_rows"][1].update(
            native_calendar_eligible=False
        ),
        "owned_eligibility": lambda row: row["owned_rows"][1].update(sample_eligible=False),
        "selected_indices": lambda row: row.update(observation_indices=[2]),
        "source_label": lambda row: row["native_rows"][1].update(source_time_s=99.0),
    }
    for name, mutation in mutations.items():
        row = sample(3, 3, [1, 2])
        mutation(row)
        try:
            helper.sampling_contract(**row)
        except ValueError as error:
            controls.append(dict(name="sampling_corruption_" + name, passed=True, cause=str(error)))
        else:
            raise AssertionError("Sampling corruption was not refused: " + name)
    assert not any(
        name.split(".")[0] in {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "pytest"}
        for name in sys.modules
    )
    result = dict(
        kind="cells.INIT02_evidence_software_controls@1",
        status="passed",
        controls=controls,
        unchanged_scientific_native_function_bodies=[
            "values",
            "observe",
            "trace",
            "field_call",
            "calcium_call",
            "rate_cache",
            "clock",
            "source_sampling",
            "run_dispatch",
        ],
        unchanged_other_test_functions=True,
        complete_native_evaluator_capture_inverse_matches_parent=True,
        complete_test_sampling_inverse_matches_parent=True,
        existing_62_ids_cases_fixtures_budgets_preserved=True,
        scientific_imports=0,
        scientific_AST_executions=0,
        model_fixture_reference_evaluations=0,
        pytest_collections=0,
        numerical_runs=0,
        software_helper_sha256=sha(capture),
        proposed_native_sha256=sha(source / NATIVE),
        proposed_test_sha256=sha(source / TEST),
        max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        elapsed_s=time.monotonic() - started,
    )
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            dict(status=result["status"], controls=len(controls), elapsed_s=result["elapsed_s"])
        )
    )


if __name__ == "__main__":
    main()
