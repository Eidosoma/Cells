"""Freeze the static supplied-entry headless normal ECM lifecycle package.

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
INVENTORY = "validation/betse/betse_normal_ecm_run_lifecycle_source_map.json"
PROTOCOL = "validation/betse/betse_normal_ecm_run_lifecycle_protocol.json"
QUEUE = WORK + "betse_normal_ecm_run_lifecycle_workqueue.json"
TEST = "tests/unit/test_betse_normal_ecm_run_lifecycle.py"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def plan(source, protocol):
    tree = ast.parse(
        (source / "validation/betse/betse_normal_ecm_run_lifecycle_fixtures.py").read_text()
    )
    constants = {
        t.id: ast.literal_eval(n.value)
        for n in tree.body
        if isinstance(n, ast.Assign)
        for t in n.targets
        if isinstance(t, ast.Name)
        and t.id in {"CASES", "RAW_CASES", "DEPENDENCIES", "CLOCK_CASES", "OBSERVER_FAILURES"}
    }
    groups = {
        name: []
        for name in (
            "windows",
            "sampling",
            "contexts",
            "raw",
            "observers",
            "dependencies",
            "clocks",
            "display",
        )
    }
    required = {
        name: dict(positive=[], raw=[], observers={}, dependencies=[], clocks=[], display=False)
        for name in groups
    }
    for case in constants["CASES"]:
        group = (
            "windows"
            if case
            in {
                "continuous",
                "window_1_then_3",
                "window_2_then_3",
                "window_each_call",
                "empty_prefix_then_all",
            }
            else "sampling"
            if case in {"fractional_sampling", "no_samples"}
            else "contexts"
        )
        groups[group].append(TEST + "::test_headless_history[" + case + "]")
        required[group]["positive"].append("isolated-" + case + "/comparison.json")
    for case in constants["RAW_CASES"]:
        groups["raw"].append(TEST + "::test_headless_raw[" + case + "]")
        required["raw"]["raw"].append("isolated-" + case + "/raw-retention.json")
    for case in constants["OBSERVER_FAILURES"]:
        groups["observers"].append(TEST + "::test_headless_observer_failure[" + case + "]")
        required["observers"]["observers"]["observer-" + case + ".json"] = {
            "before_call": 0,
            "accepted_call": 1,
            "headless_observation": 2,
        }[case]
    for case in constants["DEPENDENCIES"]:
        groups["dependencies"].append(TEST + "::test_headless_dependencies[" + case + "]")
        required["dependencies"]["dependencies"].append("dependency-" + case + ".json")
    for case in constants["CLOCK_CASES"]:
        groups["clocks"].append(TEST + "::test_headless_clock_source[" + case + "]")
        required["clocks"]["clocks"].append("isolated-clock-" + case + "/clock-comparison.json")
    groups["display"].append(TEST + "::test_headless_display_refusal")
    required["display"]["display"] = True
    ids = [node for nodes in groups.values() for node in nodes]
    assert len(ids) == len(set(ids)) == protocol["planned"]["checks"] == 48
    assert (
        sum(
            len(row["positive"]) + len(row["raw"]) + len(row["clocks"]) for row in required.values()
        )
        == 22
    )
    return groups, required


def prepare(out):
    queue = json.loads((ROOT / QUEUE).read_text())
    protocol = json.loads((ROOT / PROTOCOL).read_text())
    parent = Path(queue["frozen_dependency_parent"]["path"]).parent
    if sha(parent / "inputs.json") != queue["frozen_dependency_parent"]["sha256"]:
        raise ValueError("Reviewed dependency parent changed")
    for p, h in queue["owned_sha256"].items():
        if sha(ROOT / p) != h:
            raise ValueError("Changed owned source: " + p)
    out.mkdir(exist_ok=False)
    stage = "source_snapshot_copy"
    try:
        source = out / "source"
        shutil.copytree(
            parent / "source",
            source,
            ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".ruff_cache"),
        )
        for name in (*queue["owned"], QUEUE, *queue["workfiles"]):
            target = source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        for p, h in queue["owned_sha256"].items():
            if sha(ROOT / p) != h or sha(source / p) != h:
                raise ValueError("Owned source changed during copy: " + p)
        for p, row in queue["frozen_dependency_sources"].items():
            if sha(row["path"]) != row["sha256"] or sha(source / p) != row["sha256"]:
                raise ValueError("Reviewed frozen dependency changed: " + p)
        stage = "native_and_binding_copy"
        copies = {}
        native = protocol["native_source"]
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
            if sha(row["path"]) != row["sha256"]:
                raise ValueError("Binding changed: " + name)
            target = out / "native-inputs/binding-evidence" / (name + Path(row["path"]).suffix)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(Path(row["path"]).read_bytes())
            copies[str(target.relative_to(out))] = row["sha256"]
        stage = "static_plan_and_hashes"
        groups, required = plan(source, protocol)
        hashes = {
            str(p.relative_to(source)): sha(p) for p in sorted(source.rglob("*")) if p.is_file()
        }
        (out / "driver.py").write_bytes(Path(__file__).read_bytes())
        write(
            out / "inputs.json",
            dict(
                kind="cells.headless_ECM_lifecycle_prepared@1",
                status="prepared_static_only_unrun_unreleased",
                source_hashes=hashes,
                owned_sha256=queue["owned_sha256"],
                protected_sha256=queue["protected_snapshot_sha256"],
                frozen_dependency_sources=queue["frozen_dependency_sources"],
                frozen_dependency_parent=queue["frozen_dependency_parent"],
                dependency_runtime_authority=(
                    "Reviewed immutable parent snapshot; no live dependency adoption"
                ),
                live_hash_guard_scope=(
                    "Owned lifecycle prefix only; every imported dependency is hash-checked "
                    "in the frozen source tree"
                ),
                native_snapshot_sha256=copies,
                native_source_copies=2 * len(native["source_sha256"]),
                binding_evidence_copies=len(queue["binding_evidence"]),
                driver_sha256=sha(out / "driver.py"),
                groups=groups,
                required_reports=required,
                planned=protocol["planned"],
                binding_evidence=queue["binding_evidence"],
                source_map_sha256=sha(source / INVENTORY),
                reference_closure=queue["reference_closure"],
                local_library_source_sha256={},
                scientific_imports=0,
                scientific_AST_executions=0,
                fixture_evaluations=0,
                reference_evaluations=0,
                pytest_collection_runs=0,
                numerical_runs=0,
                new_or_retained_qualification_passes=0,
                component_qualification_pending=True,
                numerical_release_authorized=False,
                execution_requires_new_requested_round=True,
                automatic_launch=False,
                automatic_polling=False,
                automatic_followup=False,
                resource_limits=protocol["resources"],
            ),
        )
        print(
            json.dumps(
                dict(
                    status="prepared_static_only_unrun_unreleased",
                    inputs=str(out / "inputs.json"),
                    sha256=sha(out / "inputs.json"),
                    groups={k: len(v) for k, v in groups.items()},
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
    base = target / "evidence/normal-ecm-run-lifecycle"
    required = inputs["required_reports"][group]
    reports = []

    def exact(actual, expected):
        return set(actual) == set(expected) and all(
            type(actual[k]) is type(v) and actual[k] == v for k, v in expected.items()
        )

    def reference(folder, mode):
        row = json.loads((folder / "comparison.json").read_text())
        if not (
            row["fresh_conditional_reference"] is True
            and row["physical_global_conservation_credit"] is False
            and row["fields"]
            and row["resolutions"]
            and all(0 <= v["normalized_max_error"] <= 1 for v in row["fields"].values())
            and all(0 <= v["normalized_max_error"] <= 0.1 for v in row["resolutions"].values())
        ):
            raise ValueError("Invalid unchanged conditional budget")
        for level in (1, 2):
            result = json.loads((folder / ("reference-" + str(level) + ".json")).read_text())
            if not (
                result["production_imports_denied"] is True
                and not result["loaded_production_modules"]
                and result["carried_reference_forms"] == 0
                and type(result["carried_reference_forms"]) is int
                and result["decimal_precision"] == (100 if level == 1 else 160)
                and isinstance(result["runtime"]["measured_cpu_affinity"], list)
            ):
                raise ValueError("Missing fresh reference/runtime receipt")
            if mode == "cold" and result["cold_initialization"] is not True:
                raise ValueError("Wrong cold form")
            if (
                mode in {"field", "material", "calcium", "events", "channels", "noise", "mechanics"}
                and result["mode"] != mode
            ):
                raise ValueError("Wrong conditional mode")
            if mode == "mechanics":
                raw = json.loads(
                    (
                        folder
                        / ("raw-reference-" + str(level))
                        / ("raw-decimal-" + str(100 if level == 1 else 160) + ".json")
                    ).read_text()
                )
                if not raw["payload"]:
                    raise ValueError("Missing complete raw Decimal tree")

    positive = {str(p.relative_to(base)): p for p in base.glob("isolated-*/comparison.json")}
    if set(positive) != set(required["positive"]):
        raise ValueError("Exact lifecycle positive set differs")
    for name, path in sorted(positive.items()):
        row = json.loads(path.read_text())
        if not exact(
            row,
            {
                "completed": True,
                "owned_run_exhausted": True,
                "complete_calls": 3,
                "delegated_calls": 3,
                "direct_baseline_calls": 3,
                "source_labels_dt_samples_exact": True,
                "original_calendar_preserved_across_windows": True,
                "complete_component_caches_and_state_carried": True,
                "duplicate_baseline_new_case_credit": False,
                "cold_reference_forms": 2,
                "bootstrap_reference_forms": 2,
                "total_fresh_reference_forms": 52,
                "conditional_reference_forms_per_mode": 6,
                "conditional_modes": [
                    "events",
                    "material",
                    "calcium",
                    "channels",
                    "network",
                    "noise",
                    "mechanics",
                    "field",
                ],
                "carried_reference_forms": 0,
                "supplied_initialization_explicit": True,
                "headless_observations_only": True,
                "native_display_completed": False,
                "native_init_load_run_sim_core_write2storage_pickle_called": False,
                "native_full_phase_completed": False,
                "physical_initialization_claim": False,
                "physical_global_conservation_credit": False,
                "qualification_inherited": False,
            },
        ):
            raise ValueError("Invalid lifecycle scope/history report")
        case = path.parent.name.removeprefix("isolated-")
        prep = base / ("preparation-" + case)
        reference(prep / "cold", "cold")
        reference(prep / "bootstrap", "field")
        for i in range(3):
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
                reference(prep / ("point-" + str(i)) / mode, mode)
        reports.append(dict(path=name, **row))
    raw = {str(p.relative_to(base)): p for p in base.glob("isolated-*/raw-retention.json")}
    if set(raw) != set(required["raw"]):
        raise ValueError("Exact lifecycle raw set differs")
    for name, path in sorted(raw.items()):
        row = json.loads(path.read_text())
        case = path.parent.name.removeprefix("isolated-")
        expected = dict(
            positive_credit=False,
            last_accepted_calls=2 if case == "late_negative_temperature" else 0,
            full_run_and_component_partials_retained=True,
            no_automatic_retry=True,
            native_display_completed=False,
            native_full_phase_completed=False,
            physical_global_conservation_credit=False,
        )
        if not all(type(row[k]) is type(v) and row[k] == v for k, v in expected.items()) or row[
            "native_source_status"
        ] not in ("source_completed", "source_refused"):
            raise ValueError("Invalid lifecycle raw retention")
        reports.append(dict(path=name, **row))
    found = {p.name: p for p in base.glob("observer-*.json")}
    if set(found) != set(required["observers"]):
        raise ValueError("Exact observer control set differs")
    for name, path in sorted(found.items()):
        row = json.loads(path.read_text())
        count = required["observers"][name]
        if not exact(
            row,
            dict(
                expected_failure_reached=True,
                actual_leaf_type="RuntimeError",
                actual_leaf_message="Declared observer failure",
                expected_accepted_calls=count,
                actual_accepted_calls=count,
                full_reached_candidate_retained=True,
                no_automatic_retry=True,
                source_failure_credit=False,
            ),
        ):
            raise ValueError("Invalid observer commit/failure control")
        reports.append(dict(path=name, **row))
    found = {p.name: p for p in base.glob("dependency-*.json")}
    if set(found) != set(required["dependencies"]):
        raise ValueError("Exact lifecycle dependency set differs")
    for name, path in sorted(found.items()):
        row = json.loads(path.read_text())
        if not (
            row["baseline_admitted"] is True
            and row["intended_refusal_reached"] is True
            and row["actual_leaf_type"] == "ValueError"
            and row["expected_fragment"]
            and row["expected_fragment"] in row["actual_message"]
            and row["source_failure_credit"] is False
            and row["native_initializer_or_persistence_credit"] is False
        ):
            raise ValueError("Invalid lifecycle dependency refusal")
        reports.append(dict(path=name, **row))
    found = {
        str(p.relative_to(base)): p for p in base.glob("isolated-clock-*/clock-comparison.json")
    }
    if set(found) != set(required["clocks"]):
        raise ValueError("Exact source clock set differs")
    for name, path in sorted(found.items()):
        row = json.loads(path.read_text())
        if not exact(
            row,
            dict(
                source_time_profile_exact=True,
                source_labels_samples_exact=True,
                no_material_solver_executed=True,
                native_full_INIT_or_SIM_phase_executed=False,
                complete_captured_body_and_extracted_slice_distinguished=True,
            ),
        ):
            raise ValueError("Invalid clock source/scope report")
        reports.append(dict(path=name, **row))
    display = base / "display-refusal.json"
    if display.exists() != required["display"]:
        raise ValueError("Exact display refusal set differs")
    if required["display"]:
        row = json.loads(display.read_text())
        if not exact(
            row,
            dict(
                reached_state_retained=True,
                native_display_completed=False,
                native_write2storage_called=False,
                source_failure_credit=False,
            ),
        ):
            raise ValueError("Invalid display boundary")
        reports.append(dict(path="display-refusal.json", **row))
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
            CELLS_ECM_RUN_LIFECYCLE_CPU=str(cpu),
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
        for path, expected in inputs["owned_sha256"].items():
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
        for path, expected in inputs["owned_sha256"].items():
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
                supplied_entry_headless_SIM_lifecycle_only=True,
                positive_lifecycle_contracts=len(inputs["required_reports"][group]["positive"]),
                immutable_reviewed_dependency_snapshot=True,
                native_full_phase_completed=False,
                native_init_load_write2storage_pickle_called=False,
                native_display_completed=False,
                physical_initialization_claim=False,
                physical_global_conservation_credit=False,
                carried_reference_forms=0,
                component_qualification_pending=True,
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
