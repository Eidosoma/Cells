"""Freeze the static network feedback package; run groups only in a requested new round."""

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
INVENTORY = "validation/betse/betse_normal_network_join_source_map.json"
PROTOCOL = "validation/betse/betse_normal_network_join_protocol.json"
QUEUE = WORK + "betse_normal_network_join_workqueue.json"
TEST = "tests/unit/test_betse_normal_network_join.py"


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
    out.mkdir(exist_ok=False)
    source = out / "source"
    source.mkdir()
    for name in ("src", "tests", "validation", "configs"):
        shutil.copytree(
            ROOT / name,
            source / name,
            ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".ruff_cache"),
        )
    for name in ("AGENTS.md", "pyproject.toml", QUEUE, queue["runner"], queue["notes"]):
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
    native = protocol["native_source"]
    copies = {}
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
    trees = {
        name: ast.parse((source / name).read_text())
        for name in queue["owned"]
        if name.endswith(".py")
    }
    fixture_tree = trees["validation/betse/betse_normal_network_join_fixtures.py"]
    fixtures = {
        t.id: ast.literal_eval(n.value)
        for n in fixture_tree.body
        if isinstance(n, ast.Assign)
        for t in n.targets
        if isinstance(t, ast.Name) and t.id == "CASES"
    }
    core = {"active", "GJ_zero", "NaK_zero", "ordered_writes", "channel_coupled"}
    groups = {"core": [], "context": []}
    for name in fixtures["CASES"]:
        groups["core" if name in core else "context"].append(
            TEST + "::test_native_endogenous_feedback_and_pre_network_reference[" + name + "]"
        )
    groups["projection"] = [TEST + "::test_empty_feedback_projection_to_frozen_calcium"]
    groups["raw"] = [TEST + "::test_native_empty_growth_reaction_stack_refusal"]
    groups["dependencies"] = [
        TEST + "::test_complete_feedback_dependencies[" + name + "]"
        for name in ("chemistry", "map_owner", "missing_controls")
    ]
    assert (
        sum(map(len, groups.values()))
        == len({node for group in groups.values() for node in group})
        == 15
    )
    library_copies = {}
    for path, expected in queue["local_library_source_sha256"].items():
        if sha(Path(path)) != expected:
            raise ValueError("Inspected library source changed: " + path)
        target = out / "native-inputs/numpy-source/shape_base.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(Path(path).read_bytes())
        library_copies[str(target.relative_to(out))] = expected
    copies.update(library_copies)
    hashes = {str(p.relative_to(source)): sha(p) for p in sorted(source.rglob("*")) if p.is_file()}
    for path, expected in hashes.items():
        if path not in queue["coordinated_shared_edit_paths"] and sha(ROOT / path) != expected:
            raise ValueError("Source changed during static freeze: " + path)
    (out / "driver.py").write_bytes(Path(__file__).read_bytes())
    write(
        out / "inputs.json",
        dict(
            kind="cells.betse_normal_network_join_prepared@1",
            status="prepared_not_executed_not_qualified",
            source_hashes=hashes,
            owned_sha256=queue["owned_sha256"],
            protected_sha256=queue["protected_sha256"],
            native_snapshot_sha256=copies,
            driver_sha256=sha(out / "driver.py"),
            groups=groups,
            planned_total_checks=15,
            planned_native_captures=11,
            planned_pre_network_checks=30,
            planned_conditional_references=60,
            planned_carried_references=0,
            source_seam_AST_audit=queue["source_seam_AST_audit"],
            network_AST_audit=queue["network_AST_audit"],
            source_base_ER02_inputs_sha256=queue["source_base_ER02_inputs_sha256"],
            authorized_physical_helper_refactor=queue["authorized_physical_helper_refactor"],
            local_library_source_sha256=queue["local_library_source_sha256"],
            reference_closure=queue["reference_closure"],
            runner_successor=queue["runner_successor"],
            grn_owner_scope=queue["grn_owner_scope"],
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
                numerical_runs=0,
            )
        )
    )


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


def feedback_reports(target, group, expected):
    base = target / "evidence/normal-network-join"
    required = (
        {"isolated-" + node.rsplit("[", 1)[1][:-1] + "/comparison.json" for node in expected}
        if group in ("core", "context")
        else set()
    )
    found = {str(path.relative_to(base)): path for path in base.glob("isolated-*/comparison.json")}
    if set(found) != required:
        raise ValueError("Feedback report set differs from the exact expected cases")
    reports = []
    for name in sorted(found):
        row = json.loads(found[name].read_text())
        if not (
            row["completed"] is True
            and row["exact_native"] is True
            and row["complete_calls"] == 3
            and row["conditional_pre_network_checks"] == 3
            and row["carried_reference_forms"] == 0
            and row["executed_chemistry"] is False
            and 0 <= row["maximum_error_fraction"] <= 1
        ):
            raise ValueError("Incomplete or unqualified feedback report: " + name)
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
            CELLS_NETWORK_JOIN_CPU=str(cpu),
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
        reports = feedback_reports(target, group, inputs["groups"][group])
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
                conditional_pre_network_only=True,
                carried_reference_forms=0,
                executed_chemistry=False,
                grn_wrapper_selection_executed=False,
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
