"""Bounded actual report metadata producers and stdlib reader; no scientific evaluation."""

import argparse
import ast
import importlib.util
import json
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from betse_normal_ecm_event_mechanics_audit_tools import ROOT, sha, write

PREFIX = "betse_normal_ecm_event_mechanics"
WORK = ROOT / "agent-work/cells-worker-01/workfiles"


def producer(tree, function, variable):
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function)
    node = next(
        n.value
        for n in ast.walk(fn)
        if isinstance(n, ast.Assign)
        and isinstance(n.targets[0], ast.Name)
        and n.targets[0].id == variable
    )
    allowed = {
        ast.Call,
        ast.keyword,
        ast.Name,
        ast.Load,
        ast.Store,
        ast.Constant,
        ast.Subscript,
        ast.Attribute,
        ast.GeneratorExp,
        ast.comprehension,
        ast.IfExp,
        ast.Compare,
        ast.Is,
    }
    assert all(type(n) in allowed for n in ast.walk(node))
    permitted = {
        "dict",
        "sum",
        "bool",
        "str",
        "type",
        "completed",
        "captured",
        "partial",
        "row",
        "leaf",
        "fragment",
    }
    assert {n.id for n in ast.walk(node) if isinstance(n, ast.Name)} <= permitted
    assert all(
        isinstance(n.func, ast.Name) and n.func.id in {"dict", "sum", "bool", "str", "type"}
        for n in ast.walk(node)
        if isinstance(n, ast.Call)
    )
    assert all(
        ast.unparse(n) == "type(leaf).__name__"
        for n in ast.walk(node)
        if isinstance(n, ast.Attribute)
    )
    code = compile(ast.Expression(body=node), "<allowlisted metadata dict only>", "eval")

    def evaluate(**context):
        return eval(
            code,
            {
                "__builtins__": {},
                "dict": dict,
                "sum": sum,
                "bool": bool,
                "str": str,
                "type": type,
                **context,
            },
        )

    return evaluate


def replace_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def rejects(callback):
    try:
        callback()
    except (ValueError, KeyError, FileNotFoundError):
        return
    raise AssertionError("Malformed synthetic report accepted")


def check():
    test = ROOT / "tests/unit" / ("test_" + PREFIX + ".py")
    tree = ast.parse(test.read_text())
    positive = producer(tree, "run_history", "report")
    raw = producer(tree, "test_event_mechanics_raw", "report")
    spec = importlib.util.spec_from_file_location(
        "event_mechanics_stdlib_driver", WORK / (PREFIX + "_checks.py")
    )
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    protocol = json.loads((ROOT / "validation/betse" / (PREFIX + "_protocol.json")).read_text())
    groups, required = driver.plan(ROOT, protocol)
    rejected = []
    with tempfile.TemporaryDirectory(
        prefix="cells-worker01-event-mechanics-metadata-", dir="/tmp"
    ) as name:
        root = Path(name)
        target = root / "positive"
        base = target / "evidence/normal-ecm-event-mechanics"
        case = "synthetic_metadata"
        report = "isolated-" + case + "/comparison.json"
        row = positive()
        replace_json(base / report, row)
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
                "mechanics",
                "field",
            )
        ]
        for relative, mode in modes:
            folder = base / ("preparation-" + case) / relative
            replace_json(
                folder / "comparison.json",
                dict(
                    fresh_conditional_reference=True,
                    physical_global_conservation_credit=False,
                    fields=dict(synthetic=dict(normalized_max_error=0.0)),
                    resolutions=dict(synthetic=dict(normalized_max_error=0.0)),
                ),
            )
            for level, precision in ((1, 100), (2, 160)):
                replace_json(
                    folder / ("reference-" + str(level) + ".json"),
                    dict(
                        production_imports_denied=True,
                        loaded_production_modules=[],
                        carried_reference_forms=0,
                        decimal_precision=precision,
                        mode=mode,
                        cold_initialization=mode == "cold",
                        runtime=dict(measured_cpu_affinity=[0]),
                    ),
                )
                if mode == "mechanics":
                    replace_json(
                        folder
                        / ("raw-reference-" + str(level))
                        / ("raw-decimal-" + str(precision) + ".json"),
                        dict(precision=precision, payload=dict(synthetic_metadata_only=True)),
                    )
        expected = dict(
            groups=dict(synthetic=[]),
            required_reports=dict(synthetic=dict(positive=[report], raw=[], corruptions=[])),
        )

        def read():
            return driver.molecule_reports(target, "synthetic", expected)

        assert len(read()) == 1
        for key, value in (
            ("conditional_mechanics_reference_forms", 0),
            ("single_material_field_advance", False),
            ("display_completed", True),
            ("previous_field_epoch", False),
            ("complete_calls", True),
        ):
            replace_json(base / report, dict(row, **{key: value}))
            rejects(read)
            rejected.append(key)
        replace_json(base / report, row)
        point = base / ("preparation-" + case) / "point-0/mechanics/reference-2.json"
        saved = json.loads(point.read_text())
        altered = dict(saved)
        altered.pop("runtime")
        replace_json(point, altered)
        rejects(read)
        rejected.append("missing_reference_runtime")
        replace_json(point, saved)
        point = point.parent / "raw-reference-2/raw-decimal-160.json"
        saved = json.loads(point.read_text())
        replace_json(point, dict(saved, payload={}))
        rejects(read)
        rejected.append("missing_raw_Decimal_tree")
        replace_json(point, saved)
        assert len(read()) == 1
        target = root / "raw"
        base = target / "evidence/normal-ecm-event-mechanics"
        for relative in required["raw"]["raw"]:
            case = Path(relative).parent.name.removeprefix("isolated-")
            row = raw(
                completed=2 if case == "late_negative_temperature" else 0,
                captured=dict(
                    history=[dict(source_completed=False)] * 3,
                    status="source_refused",
                    failure=dict(stage="synthetic_source_stage"),
                ),
                partial=dict(stage="event_noise_mechanics_material_field"),
            )
            replace_json(base / relative, row)
        assert (
            len(
                driver.molecule_reports(
                    target, "raw", dict(groups=groups, required_reports=required)
                )
            )
            == 7
        )
        target = root / "dependencies"
        base = target / "evidence/normal-ecm-event-mechanics"
        for node in groups["dependencies"]:
            dependency = node.split("[", 1)[1][:-1]
            replace_json(
                base / ("dependency-" + dependency + ".json"),
                dict(
                    baseline_admitted=True,
                    intended_failure_reached=True,
                    actual_leaf_type="ValueError",
                    actual_message="synthetic expected refusal",
                    expected_fragment="expected refusal",
                    source_failure_credit=False,
                    display_completed=False,
                ),
            )
        assert (
            len(
                driver.molecule_reports(
                    target, "dependencies", dict(groups=groups, required_reports=required)
                )
            )
            == 26
        )
        target = root / "corruptions"
        base = target / "evidence/normal-ecm-event-mechanics"
        # Positive baseline schema was checked independently above. This checks
        # the actual control-reader branch without synthesizing a model history.
        relative = "corruption-synthetic.json"
        replace_json(
            base / relative,
            dict(
                baseline_complete=True,
                intended_corruption_rejected=True,
                duplicate_baseline_positive_credit=False,
                scientific_budget_changed=False,
            ),
        )
        expected = dict(
            required_reports=dict(synthetic=dict(positive=[], raw=[], corruptions=[relative]))
        )
        assert len(driver.molecule_reports(target, "synthetic", expected)) == 1
        replace_json(
            base / relative,
            dict(
                baseline_complete=True,
                intended_corruption_rejected=False,
                duplicate_baseline_positive_credit=False,
                scientific_budget_changed=False,
            ),
        )
        rejects(lambda: driver.molecule_reports(target, "synthetic", expected))
        rejected.append("unrejected_corruption")
        expected_ids = [i for nodes in groups.values() for i in nodes]
        cases = [
            ET.Element(
                "testcase",
                classname=node.split("::")[0][:-3].replace("/", "."),
                name=node.split("::")[1],
            )
            for node in expected_ids
        ]
        assert driver.verify_pytest_ids(cases, expected_ids) == expected_ids
        rejects(lambda: driver.verify_pytest_ids(cases + cases[:1], expected_ids))
        rejected.append("duplicate_test_ID")
        ET.SubElement(cases[0], "skipped")
        rejects(lambda: driver.verify_pytest_ids(cases, expected_ids))
        rejected.append("skipped_test_ID")
        count = sum(p.is_file() for p in root.rglob("*"))
    return dict(
        kind="cells.event_mechanics_reporting_metadata_check@1",
        status="passed_synthetic_metadata_only",
        test_sha256=sha(test),
        driver_sha256=sha(WORK / (PREFIX + "_checks.py")),
        positive_schema_cases=1,
        raw_schema_cases=7,
        dependency_schema_cases=26,
        corruption_schema_cases=1,
        exact_ID_schema_cases=62,
        temporary_metadata_files=count,
        malformed_cases_rejected=rejected,
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_evaluations=0,
        reference_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=WORK / (PREFIX + "_reporting_metadata_check_01.json")
    )
    args = parser.parse_args()
    result = check()
    write(args.output, result)
    print(
        json.dumps(
            dict(
                status=result["status"],
                metadata_files=result["temporary_metadata_files"],
                sha256=sha(args.output),
            )
        )
    )
