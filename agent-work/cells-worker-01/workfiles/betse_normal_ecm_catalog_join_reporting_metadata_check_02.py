"""Bounded synthetic report-reader check from actual producer AST; stdlib only.

No scientific/test module import, fixture/model/reference call or collection.
The only producer expression evaluated is the allowlisted metadata dict, with
simple synthetic input labels/counts and dict/len builtins. JSON answers contain
metadata and zero synthetic error metrics, never scientific result buffers.
"""

import ast
import hashlib
import json
import tempfile
import traceback
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PREFIX = "betse_normal_ecm_catalog_join"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def reader(path):
    tree = ast.parse(path.read_text())
    fn = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "molecule_reports"
    )
    ns = dict(Path=Path, json=json)
    exec(
        compile(ast.Module(body=[fn], type_ignores=[]), "<stdlib synthetic report reader>", "exec"),
        ns,
    )
    return ns["molecule_reports"]


def check():
    test = ROOT / "tests/unit" / f"test_{PREFIX}.py"
    tree = ast.parse(test.read_text())
    history = next(
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "test_ecm_catalog_history"
    )
    producer = next(
        n
        for n in ast.walk(history)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "dict"
        and any(k.arg == "complete_calls" for k in n.keywords)
    )
    allowed = {
        ast.Call,
        ast.keyword,
        ast.Name,
        ast.Load,
        ast.Constant,
        ast.Subscript,
        ast.BinOp,
        ast.Mult,
        ast.Compare,
        ast.IsNot,
        ast.BoolOp,
        ast.Or,
        ast.List,
    }
    assert all(type(n) in allowed for n in ast.walk(producer))
    assert {n.id for n in ast.walk(producer) if isinstance(n, ast.Name)} <= {
        "dict",
        "len",
        "inputs",
    }
    assert all(
        isinstance(n.func, ast.Name) and n.func.id in ("dict", "len")
        for n in ast.walk(producer)
        if isinstance(n, ast.Call)
    )
    expression = compile(
        ast.Expression(body=producer), "<allowlisted report metadata producer>", "eval"
    )
    old = reader(WORK / f"{PREFIX}_checks.py")
    new = reader(WORK / f"{PREFIX}_checks_02.py")
    rows = []
    with tempfile.TemporaryDirectory(
        prefix="cells-worker-01-catalog-report-schema-", dir="/tmp"
    ) as name:
        directory = Path(name)
        for limit, role, populations in (
            (1, "new_ECM_modern_catalog_composition", [{}]),
            (3, "component_control", None),
        ):
            case = "synthetic_schema_" + str(limit)
            # This is reporting metadata, not a scientific fixture or generated model state.
            metadata_inputs = dict(
                stop_after_calls=limit, case_role=role, catalog=dict(populations=populations)
            )
            produced = eval(
                expression,
                {"__builtins__": {}, "dict": dict, "len": len, "inputs": metadata_inputs},
            )
            target = directory / str(limit)
            base = target / "evidence/normal-ecm-catalog-join"
            report = "isolated-" + case + "/comparison.json"
            write(base / report, produced)
            expected = dict(
                required_reports={
                    "synthetic": dict(
                        positive={
                            report: dict(
                                complete_native_ECM_modern_catalog=True,
                                complete_calls=limit,
                                case_role=role,
                            )
                        },
                        raw=[],
                    )
                }
            )
            modes = [("cold", "cold"), ("bootstrap", "field")] + [
                ("point-" + str(i) + "/" + mode, mode)
                for i in range(limit)
                for mode in ("material", "calcium", "channels", "network", "field")
            ]
            for relative, mode in modes:
                folder = base / ("preparation-" + case) / relative
                write(
                    folder / "comparison.json",
                    dict(
                        fresh_conditional_reference=True,
                        physical_global_conservation_credit=False,
                        fields=dict(synthetic=dict(normalized_max_error=0.0)),
                        resolutions=dict(synthetic=dict(normalized_max_error=0.0)),
                    ),
                )
                for level, precision in ((1, 100), (2, 160)):
                    write(
                        folder / ("reference-" + str(level) + ".json"),
                        dict(
                            production_imports_denied=True,
                            loaded_production_modules=[],
                            carried_reference_forms=0,
                            decimal_precision=precision,
                            cold_initialization=mode == "cold",
                            mode=mode,
                        ),
                    )
            try:
                old(target, "synthetic", expected)
            except KeyError as error:
                assert error.args == ("conditional_channels_reference_forms",)
                old_failure = dict(
                    type=type(error).__name__, message=str(error), traceback=traceback.format_exc()
                )
            else:
                raise AssertionError(
                    "Original reporting defect did not reproduce in metadata check"
                )
            answers = new(target, "synthetic", expected)
            assert len(answers) == 1 and answers[0]["complete_calls"] == limit
            rows.append(
                dict(
                    complete_calls=limit,
                    producer_metadata=produced,
                    old_reader_failure=old_failure,
                    corrected_reader_report=answers[0],
                    conditional_modes_checked=[mode for _, mode in modes],
                    synthetic_metadata_files=1 + 3 * len(modes),
                )
            )
    return dict(
        kind="cells.catalog_reporting_bounded_synthetic_metadata_check02@1",
        actual_producer_test_sha256=sha(test),
        actual_metadata_expression_AST_sha256=hashlib.sha256(
            ast.dump(producer, include_attributes=False).encode()
        ).hexdigest(),
        successor_driver_sha256=sha(WORK / f"{PREFIX}_checks_02.py"),
        cases=rows,
        actual_producer_schema_used=True,
        corrected_reader_passes_one_and_three_call_metadata=True,
        original_reader_singular_plural_KeyError_reproduced=True,
        synthetic_metadata_only=True,
        metadata_temporary_files_total=sum(row["synthetic_metadata_files"] for row in rows),
        scientific_imports=0,
        fixture_evaluations=0,
        model_evaluations=0,
        reference_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
    )


if __name__ == "__main__":
    result = check()
    path = WORK / f"{PREFIX}_reporting_metadata_check_02.json"
    write(path, result)
    print(
        json.dumps(
            dict(
                status="passed_synthetic_metadata_only",
                cases=len(result["cases"]),
                metadata_files=result["metadata_temporary_files_total"],
                sha256=sha(path),
                scientific_imports=0,
                numerical_runs=0,
            ),
            sort_keys=True,
        )
    )
