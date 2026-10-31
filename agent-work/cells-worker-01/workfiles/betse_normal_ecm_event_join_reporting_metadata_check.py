"""Allowlisted actual metadata dict + stdlib reader only, never science or collection."""

import ast
import hashlib
import json
import tempfile
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PREFIX = "betse_normal_ecm_event_join"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def check():
    test = ROOT / "tests/unit" / ("test_" + PREFIX + ".py")
    tree = ast.parse(test.read_text())
    history = next(
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "test_ecm_event_history"
    )
    producer = next(
        n
        for n in ast.walk(history)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "dict"
        and any(k.arg == "complete_calls" for k in n.keywords)
    )
    allowed = {ast.Call, ast.keyword, ast.Name, ast.Load, ast.Constant, ast.Subscript}
    assert all(type(n) in allowed for n in ast.walk(producer))
    assert {n.id for n in ast.walk(producer) if isinstance(n, ast.Name)} <= {"dict", "inputs"}
    assert all(
        isinstance(n.func, ast.Name) and n.func.id == "dict"
        for n in ast.walk(producer)
        if isinstance(n, ast.Call)
    )
    expression = compile(
        ast.Expression(body=producer), "<allowlisted event report metadata dict>", "eval"
    )
    driver = WORK / (PREFIX + "_checks.py")
    driver_tree = ast.parse(driver.read_text())
    fn = next(
        n
        for n in driver_tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "molecule_reports"
    )
    namespace = dict(Path=Path, json=json)
    exec(
        compile(ast.Module(body=[fn], type_ignores=[]), "<stdlib metadata reader>", "exec"),
        namespace,
    )
    reader = namespace["molecule_reports"]
    fixture_tree = ast.parse((ROOT / "validation/betse" / (PREFIX + "_fixtures.py")).read_text())
    constants = {
        t.id: ast.literal_eval(n.value)
        for n in fixture_tree.body
        if isinstance(n, ast.Assign)
        for t in n.targets
        if isinstance(t, ast.Name) and t.id in ("RAW_CASES", "DEPENDENCIES")
    }
    rows = []
    total = 0
    with tempfile.TemporaryDirectory(prefix="cells-worker-01-event-report-", dir="/tmp") as name:
        directory = Path(name)
        for number, role in enumerate(
            ("component_control", "new_ECM_event_catalog_noise_composition")
        ):
            case = "synthetic_metadata_" + str(number)
            produced = eval(
                expression, {"__builtins__": {}, "dict": dict, "inputs": dict(case_role=role)}
            )
            target = directory / str(number)
            base = target / "evidence/normal-ecm-event-join"
            report = "isolated-" + case + "/comparison.json"
            write(base / report, produced)
            expected = dict(
                required_reports={
                    "synthetic": dict(
                        positive={
                            report: dict(
                                complete_native_ECM_events=True,
                                complete_native_ECM_protein_noise=True,
                                complete_calls=3,
                                case_role=role,
                            )
                        },
                        raw=[],
                    )
                }
            )
            modes = [("cold", "cold"), ("bootstrap", "field")] + [
                ("point-" + str(i) + "/" + mode, mode)
                for i in range(3)
                for mode in (
                    "events",
                    "material",
                    "calcium",
                    "channels",
                    "network",
                    "noise",
                    "field",
                )
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
            answers = reader(target, "synthetic", expected)
            assert len(answers) == 1 and answers[0]["complete_calls"] == 3
            # An incorrect schema must fail before publication of any qualification.
            bad = produced.pop("conditional_event_reference_forms")
            (base / report).unlink()
            write(base / report, produced)
            try:
                reader(target, "synthetic", expected)
            except KeyError as error:
                assert error.args == ("conditional_event_reference_forms",)
            else:
                raise AssertionError("Missing event reference metadata was accepted")
            produced["conditional_event_reference_forms"] = bad
            rows.append(
                dict(
                    case_role=role,
                    forms_per_mode=6,
                    metadata_fields=sorted(produced),
                    modes=[mode for _, mode in modes],
                    reader_passes=True,
                    missing_event_form_rejected=True,
                )
            )
            total += 1 + 3 * len(modes)
        target = directory / "raw"
        base = target / "evidence/normal-ecm-event-join"
        required = []
        for case in constants["RAW_CASES"]:
            path = "isolated-" + case + "/raw-retention.json"
            required.append(path)
            write(
                base / path,
                dict(
                    positive_credit=False,
                    completed_calls=2 if case == "late_negative_temperature" else 0,
                    native_complete_calls=0,
                    native_status="synthetic_schema_only",
                    port_stage="event_material_network_noise_field",
                    strict_port_guard_distinct_from_native_exception=case
                    in (
                        "negative_Dm_source_return",
                        "protein_noise_large_limit",
                        "late_negative_temperature",
                    ),
                    complete_native_raw_buffers_retained=True,
                    complete_available_port_partial_retained=True,
                    source_ER_disabled=True,
                    physical_global_conservation_credit=False,
                ),
            )
        assert (
            len(
                reader(
                    target, "raw", dict(required_reports=dict(raw=dict(positive={}, raw=required)))
                )
            )
            == 6
        )
        target = directory / "dependencies"
        base = target / "evidence/normal-ecm-event-join"
        for case in constants["DEPENDENCIES"]:
            write(
                base / ("dependency-" + case + ".json"),
                dict(
                    baseline_admitted=True,
                    intended_failure_reached=True,
                    actual_leaf_type="ValueError",
                    actual_message="synthetic",
                    expected_message="synthetic",
                    source_failure_credit=False,
                ),
            )
        expected = dict(
            required_reports=dict(dependencies=dict(positive={}, raw=[])),
            groups=dict(dependencies=["test[" + case + "]" for case in constants["DEPENDENCIES"]]),
        )
        assert len(reader(target, "dependencies", expected)) == 16
        total += 6 + 16
    return dict(
        kind="cells.event_reporting_bounded_metadata_check@1",
        status="passed_synthetic_metadata_only",
        actual_producer_test_sha256=sha(test),
        actual_metadata_expression_AST_sha256=hashlib.sha256(
            ast.dump(producer, include_attributes=False).encode()
        ).hexdigest(),
        driver_sha256=sha(driver),
        cases=rows,
        raw_schema_cases=6,
        dependency_schema_cases=16,
        metadata_temporary_files_total=total,
        scientific_imports=0,
        fixture_evaluations=0,
        model_evaluations=0,
        reference_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
    )


if __name__ == "__main__":
    result = check()
    path = WORK / (PREFIX + "_reporting_metadata_check_02.json")
    write(path, result)
    print(
        json.dumps(
            dict(
                status=result["status"],
                metadata_files=result["metadata_temporary_files_total"],
                sha256=sha(path),
            ),
            sort_keys=True,
        )
    )
