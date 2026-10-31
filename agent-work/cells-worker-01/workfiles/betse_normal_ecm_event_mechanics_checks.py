"""Freeze the static full normal ECM event/noise composition package.

Run bounded groups only in a newly requested round.
"""

import argparse
import ast
import hashlib
import json
import os
import shutil
import sys
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = "agent-work/cells-worker-01/workfiles/"
INVENTORY = "validation/betse/betse_normal_ecm_event_mechanics_source_map.json"
PROTOCOL = "validation/betse/betse_normal_ecm_event_mechanics_protocol.json"
QUEUE = WORK + "betse_normal_ecm_event_mechanics_workqueue.json"
TEST = "tests/unit/test_betse_normal_ecm_event_mechanics.py"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def plan(source, protocol):
    fixture = ast.parse(
        (source / "validation/betse/betse_normal_ecm_event_mechanics_fixtures.py").read_text()
    )
    constants = {
        t.id: ast.literal_eval(n.value)
        for n in fixture.body
        if isinstance(n, ast.Assign)
        for t in n.targets
        if isinstance(t, ast.Name)
        and t.id in {"CASES", "COMPONENT_CONTROLS", "RAW_CASES", "DEPENDENCIES", "CORRUPTIONS"}
    }
    groups = {name: [] for name in ("core", "events", "controls", "raw", "dependencies")}
    groups.update({"corruption-" + case: [] for case in constants["CORRUPTIONS"]})
    required = {group: dict(positive=[], raw=[], corruptions=[]) for group in groups}
    for case in constants["CASES"]:
        group = (
            "controls"
            if case in constants["COMPONENT_CONTROLS"]
            else "core"
            if case in {"combined", "temperature", "moving_P_noise", "ecmJ"}
            else "events"
        )
        groups[group].append(TEST + "::test_event_mechanics_history[" + case + "]")
        required[group]["positive"].append("isolated-" + case + "/comparison.json")
    for case in constants["RAW_CASES"]:
        groups["raw"].append(TEST + "::test_event_mechanics_raw[" + case + "]")
        required["raw"]["raw"].append("isolated-" + case + "/raw-retention.json")
    for case in constants["DEPENDENCIES"]:
        groups["dependencies"].append(TEST + "::test_event_mechanics_dependencies[" + case + "]")
    for case in constants["CORRUPTIONS"]:
        group = "corruption-" + case
        groups[group].append(TEST + "::test_event_mechanics_corruptions[" + case + "]")
        required[group]["positive"].append("isolated-combined/comparison.json")
        required[group]["corruptions"].append("corruption-" + case + ".json")
    ids = [i for nodes in groups.values() for i in nodes]
    assert len(ids) == len(set(ids)) == protocol["planned"]["checks"] == 62
    assert sum(len(row["positive"]) + len(row["raw"]) for row in required.values()) == 36
    return groups, required


def prepare(out):
    queue = json.loads((ROOT / QUEUE).read_text())
    protocol = json.loads((ROOT / PROTOCOL).read_text())
    if not queue["freeze_prerequisites"]["Chief03_source_review"]:
        raise ValueError("Chief03 source review is required before the event freeze")
    for path, expected in (queue["owned_sha256"] | queue["protected_sha256"]).items():
        if sha(ROOT / path) != expected:
            raise ValueError("Changed controlled source before static freeze: " + path)
    out.mkdir(exist_ok=False)
    stage = "source_copy"
    try:
        source = out / "source"
        source.mkdir()
        for name in ("src", "tests", "validation", "configs"):
            shutil.copytree(
                ROOT / name,
                source / name,
                ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".ruff_cache"),
            )
        for name in ("AGENTS.md", "pyproject.toml", QUEUE, *queue["workfiles"]):
            target = source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        for name in ("tmp", "cache", "evidence", "native-inputs"):
            (out / name).mkdir()
        for path, expected in (queue["owned_sha256"] | queue["protected_sha256"]).items():
            if sha(ROOT / path) != expected or sha(source / path) != expected:
                raise ValueError("Changed frozen/owned source: " + path)
        for path, expected in protocol["acceptance"]["inherited_budget_source_sha256"].items():
            if sha(source / path) != expected:
                raise ValueError("Changed inherited budget: " + path)
        stage = "native_and_binding_evidence_copy"
        native, copies = (protocol["native_source"], {})
        for name, expected in native["source_sha256"].items():
            for label, base in (
                ("checkout", Path(native["checkout"])),
                ("installed", Path(native["installed_package"]).parent),
            ):
                data = (base / name).read_bytes()
                if hashlib.sha256(data).hexdigest() != expected:
                    raise ValueError("Native source changed: " + name)
                target = out / "native-inputs" / label / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                copies[str(target.relative_to(out))] = expected
        for name, row in queue["binding_evidence"].items():
            if sha(Path(row["path"])) != row["sha256"]:
                raise ValueError("Binding evidence changed: " + name)
            target = out / "native-inputs/binding-evidence" / (name + Path(row["path"]).suffix)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(Path(row["path"]).read_bytes())
            copies[str(target.relative_to(out))] = row["sha256"]
        stage = "static_test_and_report_plan"
        groups, required = plan(source, protocol)
        stage = "final_snapshot_hashes"
        hashes = {
            str(path.relative_to(source)): sha(path)
            for path in sorted(source.rglob("*"))
            if path.is_file()
        }
        controlled = queue["owned_sha256"] | queue["protected_sha256"]
        for path, expected in controlled.items():
            if sha(ROOT / path) != expected or hashes[path] != expected:
                raise ValueError("Controlled dependency changed during freeze: " + path)
        (out / "driver.py").write_bytes(Path(__file__).read_bytes())
        write(
            out / "inputs.json",
            dict(
                kind="cells.normal_ecm_event_mechanics_prepared@1",
                status="prepared_not_executed_not_qualified",
                source_hashes=hashes,
                owned_sha256=queue["owned_sha256"],
                protected_sha256=queue["protected_sha256"],
                native_snapshot_sha256=copies,
                native_source_copies=2 * len(native["source_sha256"]),
                snapshot_only_unloaded_paths=sorted(set(hashes) - set(controlled)),
                snapshot_only_paths_are_not_adopted_dependencies=True,
                explicit_dependency_binding=queue["explicit_dependency_binding"],
                new_or_retained_qualification_passes=0,
                component_qualification_pending=True,
                binding_evidence_copies=len(queue["binding_evidence"]),
                driver_sha256=sha(out / "driver.py"),
                groups=groups,
                required_reports=required,
                planned=protocol["planned"],
                binding_evidence=queue["binding_evidence"],
                source_map_sha256=sha(source / INVENTORY),
                reference_closure=queue["reference_closure"],
                authorized_physical_helper_refactor=queue["authorized_physical_helper_refactor"],
                local_library_source_sha256={},
                scientific_imports=0,
                numerical_runs=0,
                pytest_collection_runs=0,
                execution_requires_new_requested_round=True,
                automatic_launch=False,
                automatic_followup=False,
                automatic_polling=False,
                resource_limits=protocol["resources"],
            ),
        )
        print(
            json.dumps(
                dict(
                    status="prepared_not_executed_not_qualified",
                    inputs=str(out / "inputs.json"),
                    sha256=sha(out / "inputs.json"),
                    groups={k: len(v) for k, v in groups.items()},
                    planned=protocol["planned"],
                    numerical_runs=0,
                )
            )
        )
    except BaseException as error:
        write(
            out / "failure.json",
            dict(
                status="static_preparation_failed",
                stage=stage,
                type=type(error).__name__,
                message=str(error),
                traceback=traceback.format_exc(),
                scientific_imports=0,
                numerical_runs=0,
                automatic_retry=False,
            ),
        )
        raise


def verify_pytest_ids(tests, expected):
    actual = [
        case.attrib["classname"].replace(".", "/") + ".py::" + case.attrib["name"] for case in tests
    ]
    if (
        len(expected) != len(set(expected))
        or len(actual) != len(set(actual))
        or set(actual) != set(expected)
    ):
        raise ValueError("Pytest IDs differ from the exact unique prepared set")
    if any(
        (
            any((case.find(tag) is not None for tag in ("failure", "error", "skipped")))
            for case in tests
        )
    ):
        raise ValueError("A prepared pytest check failed, errored or skipped")
    return actual


def molecule_reports(target, group, inputs):
    base = target / "evidence/normal-ecm-event-mechanics"
    required = inputs["required_reports"][group]
    reports = []

    def reference(folder, mode):
        comp = json.loads((folder / "comparison.json").read_text())
        if not (
            comp["fresh_conditional_reference"] is True
            and comp["physical_global_conservation_credit"] is False
            and comp["fields"]
            and comp["resolutions"]
            and all(0 <= v["normalized_max_error"] <= 1 for v in comp["fields"].values())
            and all(0 <= v["normalized_max_error"] <= 0.1 for v in comp["resolutions"].values())
        ):
            raise ValueError("Inherited conditional budget failed")
        for level in (1, 2):
            row = json.loads((folder / ("reference-" + str(level) + ".json")).read_text())
            if not (
                row["production_imports_denied"] is True
                and not row["loaded_production_modules"]
                and type(row["carried_reference_forms"]) is int
                and row["carried_reference_forms"] == 0
                and row["decimal_precision"] == (100 if level == 1 else 160)
                and isinstance(row["runtime"]["measured_cpu_affinity"], list)
            ):
                raise ValueError("Missing fresh reference/runtime receipt")
            if mode == "cold" and row["cold_initialization"] is not True:
                raise ValueError("Missing cold form")
            if (
                mode in {"field", "material", "calcium", "events", "noise", "mechanics"}
                and row["mode"] != mode
            ):
                raise ValueError("Wrong conditional mode")
            if mode == "mechanics":
                raw = (
                    folder
                    / ("raw-reference-" + str(level))
                    / ("raw-decimal-" + str(100 if level == 1 else 160) + ".json")
                )
                preserved = json.loads(raw.read_text())
                if not (
                    preserved["precision"] == (100 if level == 1 else 160) and preserved["payload"]
                ):
                    raise ValueError("Missing complete raw Decimal mechanics tree")

    positive = {str(p.relative_to(base)): p for p in base.glob("isolated-*/comparison.json")}
    if set(positive) != set(required["positive"]):
        raise ValueError("Wrong exact positive/baseline report set")
    for name, path in sorted(positive.items()):
        row = json.loads(path.read_text())
        expected = {
            "completed": True,
            "exact_native_event_material_field": True,
            "complete_calls": 3,
            "mechanics_calls": 3,
            "cold_reference_forms": 2,
            "bootstrap_reference_forms": 2,
            "conditional_event_reference_forms": 6,
            "conditional_material_reference_forms": 6,
            "conditional_calcium_reference_forms": 6,
            "conditional_channel_reference_forms": 6,
            "conditional_network_reference_forms": 6,
            "conditional_noise_reference_forms": 6,
            "conditional_mechanics_reference_forms": 6,
            "conditional_field_reference_forms": 6,
            "total_fresh_reference_forms": 52,
            "carried_reference_forms": 0,
            "single_material_field_advance": True,
            "actual_event_pressure_and_temperature": True,
            "actual_post_noise_primary_and_post_GRN_molecules": True,
            "previous_field_epoch": True,
            "source_ER_disabled": True,
            "held_zero_fluid_stores": True,
            "dynamic_deformation_enabled": False,
            "display_completed": False,
            "native_calendar_sample_eligibility_preserved": True,
            "complete_native_and_owned_partials_required": True,
            "qualification_inherited": False,
            "full_native_normal_solver_executed": False,
            "physical_initialization_claim": False,
            "physical_global_conservation_credit": False,
            "retained_material_panel_accepted": False,
        }
        if set(row) != set(expected) or any(
            type(row[k]) is not type(v) or row[k] != v for k, v in expected.items()
        ):
            raise ValueError("Invalid coupled source history/scope report")
        case = path.parent.name.removeprefix("isolated-")
        prep = base / ("preparation-" + case)
        reference(prep / "cold", "cold")
        reference(prep / "bootstrap", "field")
        for index in range(3):
            for mode in (
                "events",
                "material",
                "calcium",
                "channels",
                "network",
                "noise",
                "mechanics",
                "field",
            ):
                reference(prep / ("point-" + str(index)) / mode, mode)
        reports.append(dict(path=name, **row))
    raw = {str(p.relative_to(base)): p for p in base.glob("isolated-*/raw-retention.json")}
    if set(raw) != set(required["raw"]):
        raise ValueError("Wrong exact raw source-limit report set")
    for name, path in sorted(raw.items()):
        row = json.loads(path.read_text())
        case = path.parent.name.removeprefix("isolated-")
        if not (
            row["positive_credit"] is False
            and type(row["completed_calls"]) is int
            and 0 <= row["completed_calls"] < 3
            and row["completed_calls"]
            == (2 if case == "late_negative_temperature" else row["completed_calls"])
            and row["full_native_partial_retained"] is True
            and row["full_owned_partial_retained"] is True
            and row["source_and_owned_endpoints_reported_separately"] is True
            and row["display_completed"] is False
            and row["physical_global_conservation_credit"] is False
            and row["qualification_inherited"] is False
            and row["port_stage"] == "event_noise_mechanics_material_field"
            and row["native_status"] in ("source_completed", "source_refused")
            and type(row["native_complete_calls"]) is int
            and 0 <= row["native_complete_calls"] <= 3
        ):
            raise ValueError("Invalid raw refusal/partial scope report")
        reports.append(dict(path=name, **row))
    if group == "dependencies":
        names = [node.split("[", 1)[1][:-1] for node in inputs["groups"][group]]
        found = {p.name: p for p in base.glob("dependency-*.json")}
        if set(found) != {"dependency-" + name + ".json" for name in names}:
            raise ValueError("Wrong dependency set")
        for name in names:
            row = json.loads(found["dependency-" + name + ".json"].read_text())
            if not (
                row["baseline_admitted"] is True
                and row["intended_failure_reached"] is True
                and row["actual_leaf_type"] in ("ValueError", "AssertionError", "MechanicsRejected")
                and row["expected_fragment"] in row["actual_message"]
                and row["source_failure_credit"] is False
                and row["display_completed"] is False
            ):
                raise ValueError("Invalid dependency witness")
            reports.append(dict(path="dependency-" + name + ".json", **row))
    found = {p.name: p for p in base.glob("corruption-*.json")}
    if set(found) != set(required["corruptions"]):
        raise ValueError("Wrong corruption report set")
    for name, path in sorted(found.items()):
        row = json.loads(path.read_text())
        if row != dict(
            baseline_complete=True,
            intended_corruption_rejected=True,
            duplicate_baseline_positive_credit=False,
            scientific_budget_changed=False,
        ):
            raise ValueError("Invalid corruption control")
        reports.append(dict(path=name, **row))
    return reports


def run(out, group, cpu):
    inputs = json.loads((out / "inputs.json").read_text())
    if group not in inputs["groups"]:
        raise ValueError("Choose a prepared bounded group")
    target = out / ("run-" + group)
    target.mkdir(exist_ok=False)
    stage = "frozen_hashes"
    try:
        for path, expected in inputs["source_hashes"].items():
            if sha(out / "source" / path) != expected:
                raise ValueError("Frozen source changed: " + path)
        for path, expected in inputs["native_snapshot_sha256"].items():
            if sha(out / path) != expected:
                raise ValueError("Frozen native source changed: " + path)
        if sha(out / "driver.py") != inputs["driver_sha256"]:
            raise ValueError("Frozen runner changed")
        stage = "setup"
        for name in ("tmp", "cache", "evidence"):
            (target / name).mkdir()
        env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith(("JAX_", "XLA_", "CELLS_", "PYTEST_"))
            and k not in ("PYTHONPATH", "PYTHONHOME", "CUDA_VISIBLE_DEVICES")
        }
        env.update(
            PYTHONPATH=str(out / "source/src") + os.pathsep + str(out / "source"),
            PYTHONDONTWRITEBYTECODE="1",
            PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
            OMP_NUM_THREADS="1",
            OPENBLAS_NUM_THREADS="1",
            MKL_NUM_THREADS="1",
            NUMEXPR_NUM_THREADS="1",
            BLIS_NUM_THREADS="1",
            VECLIB_MAXIMUM_THREADS="1",
            CUDA_VISIBLE_DEVICES="",
            MALLOC_ARENA_MAX="2",
            TMPDIR=str(target / "tmp"),
            XDG_CACHE_HOME=str(target / "cache"),
            CELLS_COMPONENT_EVIDENCE=str(target / "evidence"),
            CELLS_ECM_EVENT_MECHANICS_CPU=str(cpu),
        )
        command = [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "--noconftest",
            "-p",
            "no:cacheprovider",
            "-q",
            *inputs["groups"][group],
            "--basetemp",
            str(target / "tmp/pytest"),
            "--junitxml",
            str(target / "tests.xml"),
        ]
        write(
            target / "execution.json",
            dict(
                group=group, cpu=cpu, command=command, requested_round=True, automatic_retry=False
            ),
        )
        stage = "affinity_and_import"
        os.sched_setaffinity(0, {cpu})
        sys.dont_write_bytecode = True
        sys.path[:0] = [str(out / "source/src"), str(out / "source")]
        from validation.assembly.component_process import run_bounded

        (target / "process").mkdir()
        stage = "live_hashes_before_computation"
        for path, expected in (inputs["owned_sha256"] | inputs["protected_sha256"]).items():
            if sha(ROOT / path) != expected:
                raise ValueError("Live controlled source changed before computation: " + path)
        for path, expected in inputs["local_library_source_sha256"].items():
            if sha(Path(path)) != expected:
                raise ValueError("Current library source changed: " + path)
        stage = "bounded_computation"
        resources = run_bounded(
            command,
            directory=target / "process",
            cwd=out / "source",
            env=env,
            timeout=480,
            max_rss_bytes=2**30,
            min_available_bytes=8 * 2**30,
            process_tree_memory_metric="rss",
        )
        stage = "exact_pytest_and_report_sets"
        tests = ET.parse(target / "tests.xml").getroot().findall(".//testcase")
        observed_ids = verify_pytest_ids(tests, inputs["groups"][group])
        reports = molecule_reports(target, group, inputs)
        stage = "live_hashes_after_computation"
        for path, expected in (inputs["owned_sha256"] | inputs["protected_sha256"]).items():
            if sha(ROOT / path) != expected:
                raise ValueError("Live controlled source changed after computation: " + path)
        stage = "result"
        write(
            target / "result.json",
            dict(
                status="passed",
                group=group,
                checks=len(tests),
                exact_pytest_ids=observed_ids,
                resources=resources,
                reports=reports,
                source_unchanged=True,
                scoped_supplied_event_noise_steady_mechanics_contract=True,
                new_positive_contexts=0
                if group.startswith("corruption-") or group == "controls"
                else len(inputs["required_reports"][group]["positive"]),
                component_control_histories=(
                    len(inputs["required_reports"][group]["positive"]) if group == "controls" else 0
                ),
                duplicate_baseline_positive_credit=False,
                component_qualification_pending=True,
                carried_reference_forms=0,
                sampled_display_completed=False,
                native_full_initialization_parity=False,
                physical_global_conservation_credit=False,
                full_native_normal_solver_executed=False,
                automatic_followup=False,
            ),
        )
    except BaseException as error:
        write(
            target / "failure.json",
            dict(
                status="failed",
                stage=stage,
                type=type(error).__name__,
                message=str(error),
                traceback=traceback.format_exc(),
                automatic_retry=False,
                preserve_all_raw_evidence=True,
            ),
        )
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "run"))
    parser.add_argument("directory", type=Path)
    parser.add_argument("--group")
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--requested-round", action="store_true")
    parser.add_argument("--cpu-coordinated", action="store_true")
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.directory.resolve())
    else:
        if (
            not args.requested_round
            or not args.cpu_coordinated
            or args.cpu is None
            or (args.group is None)
        ):
            parser.error(
                "No numerical launch until a new user-requested round and explicit CPU coordination"
            )
        run(args.directory.resolve(), args.group, args.cpu)


if __name__ == "__main__":
    main()
