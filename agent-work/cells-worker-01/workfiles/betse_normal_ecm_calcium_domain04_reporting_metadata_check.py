"""Actual allowlisted report dicts and stdlib readers against tiny synthetic metadata."""

import argparse
import ast
import hashlib
import importlib.util
import json
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PREFIX = "betse_normal_ecm_calcium_domain04"
INPUT_SHA = "41d5da23526aac015a219e2c7d535998c7181fc40520d5ef1a967034af808606"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def producer(path, function, key):
    tree = ast.parse(path.read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function)
    call = next(
        n
        for n in ast.walk(fn)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "dict"
        and any(k.arg == key for k in n.keywords)
    )
    allowed = {
        ast.Call,
        ast.keyword,
        ast.Name,
        ast.Load,
        ast.Constant,
        ast.Subscript,
        ast.Attribute,
        ast.List,
    }
    assert all(type(n) in allowed for n in ast.walk(call))
    assert {n.id for n in ast.walk(call) if isinstance(n, ast.Name)} <= {
        "dict",
        "len",
        "str",
        "type",
        "inputs",
        "case",
        "fixtures",
        "completed",
        "captured",
        "strict",
        "leaf",
        "messages",
        "dependency",
    }
    assert all(
        isinstance(n.func, ast.Name) and n.func.id in {"dict", "len", "str", "type"}
        for n in ast.walk(call)
        if isinstance(n, ast.Call)
    )
    assert all(
        ast.unparse(n) in {"fixtures.SAVED_INPUT_SHA256", "type(leaf).__name__"}
        for n in ast.walk(call)
        if isinstance(n, ast.Attribute)
    )
    expression = compile(ast.Expression(body=call), "<allowlisted scalar report metadata>", "eval")
    digest = hashlib.sha256(ast.dump(call, include_attributes=False).encode()).hexdigest()

    def evaluate(**values):
        return eval(
            expression,
            {"__builtins__": {}, "dict": dict, "len": len, "str": str, "type": type, **values},
        )

    return evaluate, digest


def expect_failure(callback):
    try:
        callback()
    except (KeyError, ValueError, FileNotFoundError):
        return
    raise AssertionError("Malformed synthetic report was accepted")


def check():
    old = ROOT / "tests/unit/test_betse_normal_ecm_calcium_join.py"
    new = ROOT / ("tests/unit/test_" + PREFIX + ".py")
    specs = {
        "positive": (old, "test_ecm_calcium_field_history", "complete_calls"),
        "raw": (old, "test_ecm_calcium_raw_partial", "positive_credit"),
        "dependencies": (old, "test_ecm_calcium_dependencies", "baseline_admitted"),
        "raw_domain": (new, "test_calcium_domain04_observed_history", "native_history_records"),
    }
    producers = {key: producer(*row) for key, row in specs.items()}
    driver = WORK / (PREFIX + "_checks.py")
    spec = importlib.util.spec_from_file_location("calcium04_stdlib_driver", driver)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    protocol = json.loads((ROOT / "validation/betse" / (PREFIX + "_protocol.json")).read_text())
    groups, required = module.plan(ROOT, protocol)
    constants = {
        t.id: ast.literal_eval(n.value)
        for n in ast.parse((ROOT / "validation/betse" / (PREFIX + "_fixtures.py")).read_text()).body
        if isinstance(n, ast.Assign)
        for t in n.targets
        if isinstance(t, ast.Name) and t.id in {"RAW_CASES", "DEPENDENCIES"}
    }
    rejected = []
    with tempfile.TemporaryDirectory(
        prefix="cells-worker-01-calcium04-metadata-", dir="/tmp"
    ) as name:
        folder = Path(name)

        def references(base, case, modes):
            for relative, mode in modes:
                point = base / ("preparation-" + case) / relative
                write(
                    point / "comparison.json",
                    dict(
                        fresh_conditional_reference=True,
                        physical_global_conservation_credit=False,
                        fields=dict(synthetic=dict(normalized_max_error=0.0)),
                        resolutions=dict(synthetic=dict(normalized_max_error=0.0)),
                    ),
                )
                for level, precision in ((1, 100), (2, 160)):
                    write(
                        point / ("reference-" + str(level) + ".json"),
                        dict(
                            production_imports_denied=True,
                            loaded_production_modules=[],
                            carried_reference_forms=0,
                            decimal_precision=precision,
                            cold_initialization=mode == "cold",
                            mode=mode,
                            transport_evaluations=0,
                            complete_network_return_predicted=False,
                        ),
                    )

        for index, role in enumerate(("component_control", "new_ECM_CaATP_field_case")):
            case = "synthetic_metadata_" + str(index)
            target = folder / str(index)
            base = target / "evidence/normal-ecm-calcium-join"
            relative = "isolated-" + case + "/comparison.json"
            row = producers["positive"][0](inputs=dict(case_role=role))
            write(base / relative, row)
            modes = [("cold", "cold"), ("bootstrap", "field")] + [
                ("point-" + str(i) + "/" + mode, mode)
                for i in range(3)
                for mode in ("material", "calcium", "network", "field")
            ]
            references(base, case, modes)
            inputs = dict(
                required_reports=dict(
                    synthetic=dict(
                        positive={relative: dict(case_role=role, complete_native_ECM_CaATP=True)},
                        raw=[],
                        raw_domain=[],
                    )
                )
            )
            assert len(module.molecule_reports(target, "synthetic", inputs)) == 1
            row["conditional_calcium_reference_forms"] = 0
            write(base / relative, row)
            expect_failure(
                lambda target=target, inputs=inputs: module.molecule_reports(
                    target, "synthetic", inputs
                )
            )
        rejected.append("positive_missing_calcium_forms")
        for group in ("raw", "dependencies"):
            target = folder / group
            base = target / "evidence/normal-ecm-calcium-join"
            for case in constants["RAW_CASES" if group == "raw" else "DEPENDENCIES"]:
                if group == "raw":
                    row = producers[group][0](
                        completed=[None] * (2 if case == "late_CaATP_underflow" else 0),
                        captured=dict(status="synthetic_schema_only"),
                        strict=case not in ("first_gene_negative", "second_gene_negative"),
                    )
                    relative = "isolated-" + case + "/raw-retention.json"
                else:
                    row = producers[group][0](
                        leaf=ValueError("synthetic"), messages={case: "synthetic"}, dependency=case
                    )
                    relative = "dependency-" + case + ".json"
                write(base / relative, row)
            inputs = dict(groups=groups, required_reports=required)
            assert len(module.molecule_reports(target, group, inputs)) == (
                6 if group == "raw" else 12
            )
        target = folder / "raw_domain"
        base = target / "evidence/normal-ecm-calcium-join"
        case = "negative_genes"
        relative = required["raw_domain"]["raw_domain"][0]
        row = producers["raw_domain"][0](
            case=case, fixtures=SimpleNamespace(SAVED_INPUT_SHA256=INPUT_SHA)
        )
        write(base / relative, row)
        modes = (
            [("cold", "cold"), ("bootstrap", "field")]
            + [
                ("point-" + str(i) + "/" + mode, mode)
                for i in range(2)
                for mode in ("material", "calcium", "network", "field")
            ]
            + [("failed-third-chemistry", "network_chemistry_prefix")]
        )
        references(base, case, modes)
        original = ROOT / "validation/betse" / (PREFIX + "_negative_genes.json")
        input_path = base / "preparation-negative_genes/inputs-before-constructor.json"
        input_path.write_bytes(original.read_bytes())
        archive_names = (
            "isolated-negative_genes/native",
            "negative_genes-domain-original-input",
            "negative_genes-domain-cold-return",
            "negative_genes-domain-bootstrap-return",
            "negative_genes-domain-complete-return-0",
            "negative_genes-domain-complete-return-1",
            "negative_genes-domain-native-before-failed-chemistry",
            "negative_genes-domain-complete-third-refusal",
        )
        for archive in archive_names:
            directory = base / archive
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "arrays.npz").write_bytes(
                b"synthetic schema bytes, not a scientific archive"
            )
            write(directory / "data.json", dict(synthetic_metadata_only=True))
            write(
                directory / "manifest.json",
                dict(
                    kind="cells.betse_normal_current_raw_evidence@1",
                    complete=True,
                    files={name: sha(directory / name) for name in ("arrays.npz", "data.json")},
                ),
            )
        inputs = dict(groups=groups, required_reports=required)

        def read():
            return module.molecule_reports(target, "raw_domain", inputs)

        assert len(read()) == 1 and read()[0]["positive_credit"] is False
        for key, value in (
            ("positive_credit", True),
            ("first_nonfinite_frame", 5),
            ("port_stop", row["native_stop"]),
            ("calcium_specific_cause_claim", True),
            ("total_fresh_reference_forms", 24),
            ("native_completed_calls", True),
        ):
            altered = dict(row, **{key: value})
            write(base / relative, altered)
            expect_failure(read)
            rejected.append("raw_domain_" + key)
        write(base / relative, row)
        input_path.write_bytes(original.read_bytes() + b" ")
        expect_failure(read)
        rejected.append("changed_original_input_bytes")
        input_path.write_bytes(original.read_bytes())
        path = base / "preparation-negative_genes/failed-third-chemistry/reference-2.json"
        saved = json.loads(path.read_text())
        write(path, dict(saved, transport_evaluations=1))
        expect_failure(read)
        rejected.append("chemistry_transport_scope_expansion")
        write(path, saved)
        archive = base / archive_names[-1] / "arrays.npz"
        saved_bytes = archive.read_bytes()
        archive.write_bytes(saved_bytes + b"changed")
        expect_failure(read)
        rejected.append("changed_partial_archive_digest")
        archive.write_bytes(saved_bytes)
        assert len(read()) == 1
        count = sum(p.is_file() for p in folder.rglob("*"))
        expected_ids = [node for nodes in groups.values() for node in nodes]
        cases = [
            ET.Element(
                "testcase",
                classname=node.split("::")[0][:-3].replace("/", "."),
                name=node.split("::")[1],
            )
            for node in expected_ids
        ]
        assert module.verify_pytest_ids(cases, expected_ids) == expected_ids
        expect_failure(lambda: module.verify_pytest_ids(cases + cases[:1], expected_ids))
        ET.SubElement(cases[0], "skipped")
        expect_failure(lambda: module.verify_pytest_ids(cases, expected_ids))
        rejected.extend(["duplicate_pytest_id", "skipped_pytest_id"])
    return dict(
        kind="cells.calcium_domain04_bounded_reporting_metadata_check@1",
        status="passed_synthetic_metadata_only",
        producer_sha256=dict(legacy=sha(old), new=sha(new)),
        driver_sha256=sha(driver),
        actual_metadata_expression_AST_sha256={k: row[1] for k, row in producers.items()},
        positive_role_schema_cases=2,
        existing_raw_schema_cases=6,
        dependency_schema_cases=12,
        observed_raw_domain_schema_cases=1,
        exact_planned_ID_schema_cases=34,
        metadata_temporary_files_total=count,
        malformed_metadata_rejected=rejected,
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_evaluations=0,
        model_evaluations=0,
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
    path = args.output
    with path.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            dict(
                status=result["status"],
                metadata_files=result["metadata_temporary_files_total"],
                sha256=sha(path),
            )
        )
    )
