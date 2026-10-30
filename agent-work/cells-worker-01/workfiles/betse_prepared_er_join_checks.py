"""Freeze the static supplied-state ER package; run groups only in a requested new round."""

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
INVENTORY = "validation/betse/betse_prepared_er_join_source_map.json"
PROTOCOL = "validation/betse/betse_prepared_er_join_protocol.json"
QUEUE = WORK + "betse_prepared_er_join_workqueue.json"
TEST = "tests/unit/test_betse_prepared_er_join.py"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def prepare(out):
    queue = json.loads((ROOT / QUEUE).read_text())
    protocol = json.loads((ROOT / PROTOCOL).read_text())
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
        native, copies = protocol["native_source"], {}
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
            target = out / "native-inputs/binding-evidence" / (name + ".json")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(Path(row["path"]).read_bytes())
            copies[str(target.relative_to(out))] = row["sha256"]
        stage = "static_test_and_report_plan"
        tree = ast.parse(
            (source / "validation/betse/betse_prepared_er_join_fixtures.py").read_text()
        )
        constants = {
            target.id: ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
            and target.id in {"CASES", "SIGN_CASES", "REFINEMENT_CASES", "REFUSALS", "SUBDIVISIONS"}
        }
        groups = {name: [] for name in ("core", "context", "ER_only", "refinement", "dependencies")}
        required = {group: dict(native={}, preparation=[], diagnostics=[]) for group in groups}
        core = {
            "active",
            "serca_zero",
            "release_zero",
            "moving_reversed",
            "Ca_stationary",
            "channel_coupled",
        }
        for case in constants["CASES"]:
            group = "core" if case.split("__")[-1] in core else "context"
            groups[group].append(TEST + "::test_supplied_neutral_er_outer_history[" + case + "]")
            required[group]["native"]["isolated-" + case + "/comparison.json"] = dict(
                complete_calls=3,
                conditional_pre_endoretic_checks=3,
                diagnostic=False,
                subdivision=1,
                matched_horizon_s=0.006,
            )
            required[group]["preparation"].append("preparation-" + case + "/comparison.json")
        for case in constants["SIGN_CASES"]:
            groups["ER_only"].append(TEST + "::test_supplied_thermal_sign_er_only[" + case + "]")
            required["ER_only"]["native"]["isolated-" + case + "/comparison.json"] = dict(
                complete_calls=1, conditional_pre_endoretic_checks=1, ER_only=True
            )
            required["ER_only"]["preparation"].append("preparation-" + case + "/comparison.json")
        for case in constants["REFINEMENT_CASES"]:
            groups["refinement"].append(
                TEST + "::test_matched_horizon_refinement_diagnostic[" + case + "]"
            )
            required["refinement"]["diagnostics"].append("refinement-" + case + ".json")
            for subdivision in constants["SUBDIVISIONS"]:
                tag = "refinement-" + case + "-n" + str(subdivision)
                required["refinement"]["native"]["isolated-" + tag + "/comparison.json"] = dict(
                    complete_calls=3 * subdivision,
                    conditional_pre_endoretic_checks=3 * subdivision,
                    diagnostic=True,
                    subdivision=subdivision,
                    matched_horizon_s=0.006,
                )
                required["refinement"]["preparation"].append(
                    "preparation-" + tag + "/comparison.json"
                )
        for case in constants["REFUSALS"]:
            groups["dependencies"].append(TEST + "::test_prepared_packet_refusals[" + case + "]")
        ids = [node for group in groups.values() for node in group]
        assert len(ids) == len(set(ids)) == protocol["planned"]["checks"] == 23
        assert sum(len(row["native"]) for row in required.values()) == 21
        assert (
            sum(
                item["conditional_pre_endoretic_checks"]
                for row in required.values()
                for item in row["native"].values()
            )
            == 83
        )
        stage = "final_snapshot_hashes"
        hashes = {
            str(path.relative_to(source)): sha(path)
            for path in sorted(source.rglob("*"))
            if path.is_file()
        }
        for path, expected in hashes.items():
            if path not in queue["coordinated_shared_edit_paths"] and sha(ROOT / path) != expected:
                raise ValueError("Source changed during static freeze: " + path)
        (out / "driver.py").write_bytes(Path(__file__).read_bytes())
        write(
            out / "inputs.json",
            dict(
                kind="cells.prepared_owned_ER_prepared@1",
                status="prepared_not_executed_not_qualified",
                source_hashes=hashes,
                owned_sha256=queue["owned_sha256"],
                protected_sha256=queue["protected_sha256"],
                native_snapshot_sha256=copies,
                native_source_copies=36,
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
        any(case.find(tag) is not None for tag in ("failure", "error", "skipped")) for case in tests
    ):
        raise ValueError("A prepared pytest check failed, errored or skipped")
    return actual


def prepared_reports(target, group, inputs):
    base = target / "evidence/prepared-er-join"
    expected = inputs["required_reports"][group]
    found = {str(path.relative_to(base)): path for path in base.glob("isolated-*/comparison.json")}
    if set(found) != set(expected["native"]):
        raise ValueError("Native comparison report set differs from the exact expected cases")
    result = []
    for name in sorted(found):
        row = json.loads(found[name].read_text())
        if not (
            row["completed"] is True
            and row["exact_native"] is True
            and row["carried_reference_forms"] == 0
            and row["preparation_reference_forms"] == 2
            and row["supplied_prepared_state"] is True
            and row["native_constructor_parity"] is False
            and 0 <= row["maximum_error_fraction"] <= 1
            and all(row[key] == value for key, value in expected["native"][name].items())
        ):
            raise ValueError("Incomplete or unqualified native report: " + name)
        result.append(dict(path=name, **row))
    preparation = {
        str(path.relative_to(base)): path for path in base.glob("preparation-*/comparison.json")
    }
    if set(preparation) != set(expected["preparation"]):
        raise ValueError("Preparation report set differs from expected packets")
    for name, path in sorted(preparation.items()):
        row = json.loads(path.read_text())
        if not (
            row["completed"] is True
            and row["preparation_only"] is True
            and row["exact_binary_input"] is True
            and row["source_parent_association_preserved"] is True
            and row["reference_forms"] == 2
            and row["fields"]
            and all(
                0 <= v["normalized_max_error"] <= (0.1 if key.startswith("reference/") else 1)
                for key, v in row["fields"].items()
            )
        ):
            raise ValueError("Unqualified preparation report: " + name)
        for level in (1, 2):
            ref = json.loads(path.with_name("reference-" + str(level) + ".json").read_text())
            if not ref["production_imports_denied"] or ref["loaded_production_modules"]:
                raise ValueError("Preparation reference imports were not independent")
        result.append(dict(path=name, **row))
    diagnostics = {path.name: path for path in (base / "diagnostics").glob("*.json")}
    if set(diagnostics) != set(expected["diagnostics"]):
        raise ValueError("Matched-horizon diagnostic report set differs from expected cases")
    for name, path in sorted(diagnostics.items()):
        row = json.loads(path.read_text())
        if not (
            row["complete"] is True
            and row["subdivisions"] == [1, 2, 4]
            and row["dt_s"] == [0.002, 0.001, 0.0005]
            and row["matched_horizon_s"] == 0.006
            and row["diagnostic_only"] is True
            and row["physical_accuracy_pass_threshold"] is None
            and row["independent_carried_forms"] == 0
            and row["summary"]
        ):
            raise ValueError("Incomplete matched-horizon diagnostic: " + name)
        result.append(dict(path="diagnostics/" + name, **row))
    return result


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
            CELLS_PREPARED_ER_CPU=str(cpu),
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
        reports = prepared_reports(target, group, inputs)
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
                conditional_pre_endoretic_only=True,
                carried_reference_forms=0,
                supplied_prepared_state=True,
                native_constructor_parity=False,
                physical_or_full_native_parity=False,
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
            or args.group is None
        ):
            parser.error(
                "No numerical launch until a new user-requested round and explicit CPU coordination"
            )
        run(args.directory.resolve(), args.group, args.cpu)


if __name__ == "__main__":
    main()
