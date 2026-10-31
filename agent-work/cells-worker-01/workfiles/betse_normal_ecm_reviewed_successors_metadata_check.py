"""Bounded scalar report producer/reader check; no science or captured solver execution."""

import ast
import copy
import importlib.util
import json
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

from betse_normal_ecm_reviewed_successors_resources import BASE, ROOT, sha

PREFIX = "betse_normal_ecm_run_lifecycle"
PARENT = BASE / "betse-normal-ecm-run-lifecycle-prepared-20261031-01"

WORK = ROOT / "agent-work/cells-worker-01/workfiles"
MODES = ("events", "material", "calcium", "channels", "network", "noise", "mechanics", "field")


def producer(tree, function, marker):
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function)
    node = next(
        n
        for n in ast.walk(fn)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "dict"
        and marker in {k.arg for k in n.keywords}
    )
    allowed = {
        ast.Call,
        ast.keyword,
        ast.Name,
        ast.Load,
        ast.Constant,
        ast.Subscript,
        ast.Attribute,
    }
    assert all(type(n) in allowed for n in ast.walk(node))
    permitted = {
        "dict",
        "list",
        "str",
        "type",
        "MODES",
        "accepted",
        "captured",
        "expected",
        "leaf",
        "fragment",
        "witness",
    }
    assert {n.id for n in ast.walk(node) if isinstance(n, ast.Name)} <= permitted
    assert all(
        isinstance(n.func, ast.Name) and n.func.id in {"dict", "list", "str", "type"}
        for n in ast.walk(node)
        if isinstance(n, ast.Call)
    )
    assert all(
        ast.unparse(n) in {"accepted.cursor", "type(leaf).__name__"}
        for n in ast.walk(node)
        if isinstance(n, ast.Attribute)
    )
    code = compile(ast.Expression(body=node), "<allowlisted scalar report dict>", "eval")

    def evaluate(**context):
        return eval(
            code,
            {
                "__builtins__": {},
                "dict": dict,
                "list": list,
                "str": str,
                "type": type,
                "MODES": MODES,
                **context,
            },
        )

    return evaluate


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")


def rejects(callback):
    try:
        callback()
    except (ValueError, KeyError, FileNotFoundError):
        return
    raise AssertionError("Malformed metadata was accepted")


def check():
    proposal = WORK / "betse_normal_ecm_reviewed_successors_proposal_03"
    test = proposal / "tests/unit" / ("test_" + PREFIX + ".py")
    tree = ast.parse(test.read_text())
    positive = producer(tree, "test_headless_history", "completed")
    raw = producer(tree, "test_headless_raw", "positive_credit")
    observer = producer(tree, "test_headless_observer_failure", "expected_failure_reached")
    dependency = producer(tree, "test_headless_dependencies", "baseline_admitted")
    clock = producer(tree, "test_headless_clock_source", "source_time_profile_exact")
    display = producer(tree, "test_headless_display_refusal", "reached_state_retained")
    driver_path = proposal / "lifecycle-evidence-reader.py"
    spec = importlib.util.spec_from_file_location("headless_lifecycle_stdlib_driver", driver_path)
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    protocol = json.loads(
        (PARENT / "source/validation/betse" / (PREFIX + "_protocol.json")).read_text()
    )
    groups, required = driver.plan(PARENT / "source", protocol)
    inputs = dict(required_reports=required)
    rejected = []
    with tempfile.TemporaryDirectory(
        prefix="cells-worker01-lifecycle-metadata-", dir="/tmp"
    ) as name:
        directory = Path(name)
        targets = {}
        for group, expected in required.items():
            target = directory / group
            targets[group] = target
            base = target / "evidence/normal-ecm-run-lifecycle"
            for report in expected["positive"]:
                put(base / report, positive())
                case = Path(report).parent.name.removeprefix("isolated-")
                modes = [("cold", "cold"), ("bootstrap", "field")] + [
                    ("point-" + str(i) + "/" + mode, mode) for i in range(3) for mode in MODES
                ]
                for relative, mode in modes:
                    folder = base / ("preparation-" + case) / relative
                    put(
                        folder / "comparison.json",
                        dict(
                            fresh_conditional_reference=True,
                            physical_global_conservation_credit=False,
                            fields=dict(scalar_metadata=dict(normalized_max_error=0.0)),
                            resolutions=dict(scalar_metadata=dict(normalized_max_error=0.0)),
                        ),
                    )
                    for level, precision in ((1, 100), (2, 160)):
                        put(
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
                            put(
                                folder
                                / ("raw-reference-" + str(level))
                                / ("raw-decimal-" + str(precision) + ".json"),
                                dict(precision=precision, payload=dict(scalar_metadata_only=True)),
                            )
            named = {
                "events_zero_width": (
                    "events_zero_width_store_equality",
                    "ZeroDivisionError",
                    "float division by zero",
                ),
                "network_refuses": (
                    "GRN_refusal_before_noise_unchanged_RNG",
                    "BetseSimUnstableException",
                    "Your simulation has become unstable. Please try a smaller time step",
                ),
                "late_negative_temperature": (
                    "negative_event_temperature_call2_before_material_drive",
                    "ValueError",
                    "Require explicit finite source scalar: runtime_temperature_K",
                ),
                "mechanics_overflow": (
                    "nonfinite_mechanics_trial_before_material_commit",
                    "MechanicsRejected",
                    "Native mechanics refused at steady_deformation: "
                    "Nonfinite complete mechanics output",
                ),
            }
            for report in expected["raw"]:
                case = Path(report).parent.name.removeprefix("isolated-")
                count = 2 if case == "late_negative_temperature" else 0
                witness, cause, message = named[case]
                put(
                    base / report,
                    raw(
                        accepted=SimpleNamespace(cursor=count),
                        captured=dict(composition=dict(status="source_completed")),
                        witness=witness,
                        leaf=type(cause, (Exception,), {})(message),
                    ),
                )
            for report, count in expected["observers"].items():
                put(
                    base / report,
                    observer(
                        expected=count,
                        accepted=SimpleNamespace(cursor=count),
                        leaf=RuntimeError("Declared observer failure"),
                    ),
                )
            for report in expected["dependencies"]:
                put(
                    base / report,
                    dependency(
                        leaf=ValueError("declared scalar refusal"),
                        fragment="declared scalar refusal",
                    ),
                )
            for report in expected["clocks"]:
                put(base / report, clock())
            if expected["display"]:
                put(base / "display-refusal.json", display())
            reports = driver.molecule_reports(target, group, inputs)
            assert len(reports) == len(groups[group])
        file_count = sum(p.is_file() for p in directory.rglob("*"))
        byte_count = sum(p.stat().st_size for p in directory.rglob("*") if p.is_file())
        assert file_count < 1200 and byte_count < 2**20
        target = targets["windows"]
        base = target / "evidence/normal-ecm-run-lifecycle"
        path = base / required["windows"]["positive"][0]
        saved = json.loads(path.read_text())

        def read():
            return driver.molecule_reports(target, "windows", inputs)

        for key, value in (
            ("complete_calls", True),
            ("delegated_calls", 4),
            ("native_display_completed", True),
            ("native_full_phase_completed", True),
            ("complete_component_caches_and_state_carried", False),
            ("carried_reference_forms", 2),
            ("qualification_inherited", True),
        ):
            put(path, dict(saved, **{key: value}))
            rejects(read)
            rejected.append(key)
        put(path, dict(saved, unexpected_scope_claim=True))
        rejects(read)
        rejected.append("unexpected_scope_claim")
        put(path, saved)
        case = path.parent.name.removeprefix("isolated-")
        ref = base / ("preparation-" + case) / "point-0/channels/reference-2.json"
        saved_ref = json.loads(ref.read_text())
        changed = copy.deepcopy(saved_ref)
        changed.pop("runtime")
        put(ref, changed)
        rejects(read)
        rejected.append("missing_reference_runtime")
        put(ref, dict(saved_ref, mode="field"))
        rejects(read)
        rejected.append("wrong_conditional_reference_role")
        put(ref, saved_ref)
        raw_tree = (
            base
            / ("preparation-" + case)
            / "point-0/mechanics/raw-reference-2/raw-decimal-160.json"
        )
        saved_tree = json.loads(raw_tree.read_text())
        put(raw_tree, dict(saved_tree, payload={}))
        rejects(read)
        rejected.append("missing_raw_Decimal_tree")
        put(raw_tree, saved_tree)
        extra = base / "isolated-unprepared/comparison.json"
        put(extra, saved)
        rejects(read)
        rejected.append("extra_unprepared_positive")
        extra.unlink()
        assert len(read()) == 5
        for group, pattern in (("raw", "raw"), ("observers", "observers")):
            target_group = targets[group]
            base_group = target_group / "evidence/normal-ecm-run-lifecycle"
            files = required[group][pattern]
            for item in files:
                file = base_group / item
                saved_row = json.loads(file.read_text())
                if group == "raw":
                    changed_row = dict(saved_row, named_cause_type="FileExistsError")
                else:
                    changed_row = dict(saved_row, actual_leaf_type="FileExistsError")
                put(file, changed_row)
                rejects(
                    lambda group=group, target_group=target_group: driver.molecule_reports(
                        target_group, group, inputs
                    )
                )
                put(file, saved_row)
        rejected.extend(["unrelated_raw_first_call_error", "unrelated_observer_archive_collision"])
        for group in groups:
            cases = []
            for node in groups[group]:
                filename, method = node.split("::")
                cases.append(
                    ET.Element("testcase", classname=filename[:-3].replace("/", "."), name=method)
                )
            assert len(driver.verify_pytest_ids(cases, groups[group])) == len(cases)
            rejects(
                lambda cases=cases, group=group: driver.verify_pytest_ids(
                    cases + cases[:1], groups[group]
                )
            )
            rejects(
                lambda cases=cases, group=group: driver.verify_pytest_ids(cases[:-1], groups[group])
            )
            ET.SubElement(cases[0], "skipped")
            rejects(lambda cases=cases, group=group: driver.verify_pytest_ids(cases, groups[group]))
        rejected.extend(["duplicate_JUnit_ID", "missing_JUnit_ID", "skipped_JUnit_ID"])
    return dict(
        kind="cells.explicit_successor_lifecycle_scalar_metadata_check@1",
        status="passed_synthetic_metadata_only",
        actual_report_producer_dicts=6,
        actual_stdlib_reader_and_plan=True,
        synthetic_files=file_count,
        synthetic_bytes=byte_count,
        exact_ID_schema_cases=sum(map(len, groups.values())),
        report_groups={k: len(v) for k, v in groups.items()},
        rejected_metadata_mutations=rejected,
        test_sha256=sha(test),
        driver_sha256=sha(driver_path),
        science_modules_imported=[],
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_evaluations=0,
        reference_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
        qualification_credit=0,
    )


if __name__ == "__main__":
    result = check()
    path = WORK / "betse_normal_ecm_reviewed_successors_metadata_witness_01.json"
    with path.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(dict(status=result["status"], files=result["synthetic_files"], sha256=sha(path)))
    )
