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
INVENTORY = "validation/topology/betse_native_cut_lifecycle_source_map.json"
PROTOCOL = "validation/topology/betse_native_cut_lifecycle_protocol.json"
QUEUE = WORK + "betse_native_cut_lifecycle_workqueue.json"
TEST = "tests/unit/test_betse_native_cut_lifecycle.py"


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
    if not queue["freeze_prerequisites"]["frozen_event01_bound"]:
        raise ValueError(
            "Frozen event01 dependency evidence is required before the separate cut freeze"
        )
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
            target = out / "native-inputs/binding-evidence" / (name + ".json")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(Path(row["path"]).read_bytes())
            copies[str(target.relative_to(out))] = row["sha256"]
        stage = "static_test_and_report_plan"
        tree = ast.parse(
            (source / "validation/topology/betse_native_cut_lifecycle_fixtures.py").read_text()
        )
        constants = {
            target.id: ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
            and target.id
            in {"CASES", "CLASSES", "FAMILIES", "COMPONENT_CONTROLS", "RAW_CASES", "DEPENDENCIES"}
        }
        groups = {name: [] for name in ("core", "raw", "dependencies")}
        required = {group: dict(positive={}, raw=[]) for group in groups}
        for case in constants["CASES"]:
            groups["core"].append(TEST + "::test_native_cut_prefix[" + case + "]")
            required["core"]["positive"][case + "/comparison.json"] = dict(exact_native_prefix=True)
        for case in constants["RAW_CASES"]:
            groups["raw"].append(TEST + "::test_native_cut_raw_partial[" + case + "]")
            required["raw"]["raw"].append(case + "/raw-retention.json")
        for case in constants["DEPENDENCIES"]:
            groups["dependencies"].append(TEST + "::test_native_cut_capabilities[" + case + "]")
        ids = [node for group in groups.values() for node in group]
        assert len(ids) == len(set(ids)) == protocol["planned"]["checks"] == 25
        assert sum((len(row["positive"]) + len(row["raw"]) for row in required.values())) == 14
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
                kind="cells.native_cut_lifecycle_prepared@1",
                status="prepared_not_executed_not_qualified",
                source_hashes=hashes,
                owned_sha256=queue["owned_sha256"],
                protected_sha256=queue["protected_sha256"],
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
    base = target / "evidence/native-cut-lifecycle"
    required = inputs["required_reports"][group]
    reports = []
    positive = {str(p.relative_to(base)): p for p in base.glob("*/comparison.json")}
    if set(positive) != set(required["positive"]):
        raise ValueError("Exact native cut prefix positive set differs")
    for name, path in sorted(positive.items()):
        row = json.loads(path.read_text())
        if not (
            row["completed"] is True
            and row["exact_native_prefix"] is True
            and (row["fresh_reference_forms"] == 1)
            and (row["carried_reference_forms"] == 0)
            and (row["retained_prefix_and_sink_ledgers"] is True)
            and (row["ordinary_continuation_refused"] is True)
            and (row["source_mesh_calls"] == 0)
            and (row["complete_native_cut"] is False)
            and (row["physical_mesh_qualified"] is False)
            and (row["physical_global_conservation_credit"] is False)
            and row["amount_metrics"]
            and all((0 <= v <= 1 for v in row["amount_metrics"].values()))
        ):
            raise ValueError("Invalid cut prefix/owner conditional report")
        ref = json.loads((path.parent / "independent/result.json").read_text())
        if not (
            ref["production_imports_denied"] is True
            and (not ref["loaded_production_modules"])
            and (ref["decimal_precision"] == 80)
            and (ref["carried_reference_forms"] == 0)
            and (ref["physical_mesh_qualified"] is False)
            and (ref["complete_native_cut"] is False)
        ):
            raise ValueError("Missing independent conditional cut form")
        reports.append(dict(path=name, **row))
    raw = {str(p.relative_to(base)): p for p in base.glob("*/raw-retention.json")}
    if set(raw) != set(required["raw"]):
        raise ValueError("Exact raw cut set differs")
    for name, path in sorted(raw.items()):
        row = json.loads(path.read_text())
        if not (
            row["positive_credit"] is False
            and row["complete_raw_native_and_port_evidence"] is True
            and (row["strict_ordinary_continuation_credit"] is False)
            and (row["complete_native_cut"] is False)
            and (row["physical_mesh_qualified"] is False)
            and (row["geometry_calls"] == 0)
        ):
            raise ValueError("Invalid raw native cut retention report")
        reports.append(dict(path=name, **row))
    dependencies = {
        p.parent.name.removeprefix("dependency-"): p
        for p in base.glob("dependency-*/dependency.json")
    }
    expected = (
        [node.split("[", 1)[1][:-1] for node in inputs["groups"][group]]
        if group == "dependencies"
        else []
    )
    if set(dependencies) != set(expected):
        raise ValueError("Exact cut dependency set differs")
    for name, path in sorted(dependencies.items()):
        row = json.loads(path.read_text())
        if not (
            row["baseline_admitted"] is True
            and row["intended_failure_reached"] is True
            and (row["ordinary_checkpoint_ready"] is False)
            and (row["source_failure_credit"] is False)
            and (row["actual_type"] == row["expected_type"])
            and (row["actual_message"] == row["expected_message"])
        ):
            raise ValueError("Invalid cut dependency refusal witness")
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
            CELLS_NATIVE_CUT_CPU=str(cpu),
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
                automatic_followup=False,
                native_deletion_prefix_only=True,
                geometry_calls_executed=0,
                complete_native_cut=False,
                physical_mesh_qualified=False,
                ordinary_checkpoint_ready=False,
                existing_owner_ledger_is_separate=True,
                carried_reference_forms=0,
                physical_global_conservation_credit=False,
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
