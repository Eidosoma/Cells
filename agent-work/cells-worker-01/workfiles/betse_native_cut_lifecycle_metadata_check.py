"""Actual report-producer metadata AST and stdlib reader only; no model data/evaluation."""

import ast
import hashlib
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PREFIX = "betse_native_cut_lifecycle"


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
    producers = {}
    for label, key in (
        ("positive", "fresh_reference_forms"),
        ("raw", "complete_raw_native_and_port_evidence"),
        ("dependencies", "baseline_admitted"),
    ):
        node = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "dict"
            and any(k.arg == key for k in n.keywords)
        )
        assert {n.id for n in ast.walk(node) if isinstance(n, ast.Name)} <= {
            "dict",
            "amount_metrics",
            "trial",
            "captured",
            "type",
            "str",
            "error",
            "expected_type",
            "expected_message",
        }
        assert all(
            isinstance(n.func, ast.Name) and n.func.id in ("dict", "type", "str")
            for n in ast.walk(node)
            if isinstance(n, ast.Call)
        )
        producers[label] = compile(
            ast.Expression(body=node), "<allowlisted actual metadata producer>", "eval"
        )
    driver = WORK / (PREFIX + "_checks.py")
    fn = next(
        n
        for n in ast.parse(driver.read_text()).body
        if isinstance(n, ast.FunctionDef) and n.name == "molecule_reports"
    )
    namespace = dict(Path=Path, json=json)
    exec(
        compile(ast.Module(body=[fn], type_ignores=[]), "<stdlib report schema reader>", "exec"),
        namespace,
    )
    reader = namespace["molecule_reports"]
    constants = {
        t.id: ast.literal_eval(n.value)
        for n in ast.parse(
            (ROOT / "validation/topology" / (PREFIX + "_fixtures.py")).read_text()
        ).body
        if isinstance(n, ast.Assign)
        for t in n.targets
        if isinstance(t, ast.Name) and t.id == "DEPENDENCIES"
    }
    basic = {"__builtins__": {}, "dict": dict, "type": type, "str": str}
    with tempfile.TemporaryDirectory(prefix="cells-worker-01-cut-report-", dir="/tmp") as name:
        directory = Path(name)
        target = directory / "core"
        base = target / "evidence/native-cut-lifecycle"
        produced = eval(
            producers["positive"], dict(basic, amount_metrics={"synthetic_metadata": 0.0})
        )
        write(base / "synthetic/comparison.json", produced)
        write(
            base / "synthetic/independent/result.json",
            dict(
                production_imports_denied=True,
                loaded_production_modules=[],
                decimal_precision=80,
                carried_reference_forms=0,
                physical_mesh_qualified=False,
                complete_native_cut=False,
            ),
        )
        expected = dict(
            required_reports=dict(
                core=dict(
                    positive={"synthetic/comparison.json": dict(exact_native_prefix=True)}, raw=[]
                )
            ),
            groups=dict(core=["synthetic"]),
        )
        assert len(reader(target, "core", expected)) == 1
        produced.pop("fresh_reference_forms")
        (base / "synthetic/comparison.json").unlink()
        write(base / "synthetic/comparison.json", produced)
        try:
            reader(target, "core", expected)
        except KeyError as error:
            assert error.args == ("fresh_reference_forms",)
        else:
            raise AssertionError("Incomplete prefix report schema accepted")
        target = directory / "raw"
        base = target / "evidence/native-cut-lifecycle"
        required = []
        for index, complete in enumerate((False, True)):
            path = str(index) + "/raw-retention.json"
            required.append(path)
            produced = eval(
                producers["raw"],
                dict(
                    basic,
                    trial=SimpleNamespace(source_prefix_completed=complete),
                    captured=dict(failure=None if complete else dict(type="IndexError")),
                ),
            )
            write(base / path, produced)
        expected = dict(
            required_reports=dict(raw=dict(positive={}, raw=required)),
            groups=dict(raw=["synthetic"]),
        )
        assert len(reader(target, "raw", expected)) == 2
        target = directory / "dependencies"
        base = target / "evidence/native-cut-lifecycle"
        for case in constants["DEPENDENCIES"]:
            produced = eval(
                producers["dependencies"],
                dict(
                    basic,
                    error=ValueError("synthetic_schema"),
                    expected_type="ValueError",
                    expected_message="synthetic_schema",
                ),
            )
            write(base / ("dependency-" + case) / "dependency.json", produced)
        expected = dict(
            required_reports=dict(dependencies=dict(positive={}, raw=[])),
            groups=dict(dependencies=["test[" + case + "]" for case in constants["DEPENDENCIES"]]),
        )
        assert len(reader(target, "dependencies", expected)) == 11
    return dict(
        kind="cells.native_cut_reporting_metadata_check@1",
        status="passed_synthetic_metadata_only",
        test_sha256=sha(test),
        driver_sha256=sha(driver),
        synthetic_metadata_files=15,
        actual_producer_AST_used=True,
        missing_reference_form_rejected=True,
        primary_schema_cases=1,
        raw_schema_cases=2,
        dependency_schema_cases=11,
        scientific_imports=0,
        model_evaluations=0,
        fixture_evaluations=0,
        reference_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
    )


if __name__ == "__main__":
    result = check()
    path = WORK / (PREFIX + "_metadata_witness_01.json")
    write(path, result)
    print(json.dumps(result, sort_keys=True))
