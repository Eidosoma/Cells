"""Freeze the static catalog package; run groups only in a requested new round."""

import argparse
import ast
import hashlib
import json
import os
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = "agent-work/cells-worker-01/workfiles/"
INVENTORY = "validation/betse/betse_normal_catalog_join_inventory.json"
PROTOCOL = "validation/betse/betse_normal_catalog_join_protocol.json"
QUEUE = WORK + "betse_normal_catalog_join_workqueue.json"
TEST = "tests/unit/test_betse_normal_catalog_join.py"


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
    inv = json.loads((ROOT / INVENTORY).read_text())
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
    fixture_tree = trees["validation/betse/betse_normal_catalog_join_fixtures.py"]
    fixtures = {
        t.id: ast.literal_eval(n.value)
        for n in fixture_tree.body
        if isinstance(n, ast.Assign)
        for t in n.targets
        if isinstance(t, ast.Name) and t.id in ("CASES", "CARRIED_CASES")
    }
    if set(fixtures["CASES"]) != set(inv["classes"]):
        raise ValueError("Prepared class matrix mismatch")
    groups = {family: [] for family in ("Na", "K", "Ca", "Cl", "Fun", "Cat", "ML")}
    for name, row in inv["classes"].items():
        groups[row["family"]].append(TEST + "::test_native_catalog_actual_parent[" + name + "]")
    for name in fixtures["CARRIED_CASES"]:
        groups[inv["classes"][name]["family"]].append(
            TEST + "::test_native_catalog_carried_diagnostics[" + name + "]"
        )
    groups["mixed"] = [
        TEST + "::test_mixed_native_catalog_populations[" + order + "]"
        for order in ("forward", "reverse")
    ]
    groups["controls"] = [
        TEST + "::test_unimplemented_coupled_state_is_explicit[" + kind + "]"
        for kind in ("CaATP", "ER", "legacy_cag")
    ]
    groups["raw"] = [
        TEST + "::test_raw_native_catalog_failures[" + name + "]"
        for name in (
            "empty_profile",
            "Nav1p2_zero_quotient",
            "Cav2p2_zero_quotient",
            "Cav_G_zero_quotient",
        )
    ]
    assert sum(map(len, groups.values())) == 72
    hashes = {str(p.relative_to(source)): sha(p) for p in sorted(source.rglob("*")) if p.is_file()}
    for path, expected in hashes.items():
        if path not in queue["coordinated_shared_edit_paths"] and sha(ROOT / path) != expected:
            raise ValueError("Source changed during static freeze: " + path)
    (out / "driver.py").write_bytes(Path(__file__).read_bytes())
    write(
        out / "inputs.json",
        dict(
            kind="cells.betse_normal_catalog_join_prepared@1",
            status="prepared_not_executed_not_qualified",
            source_hashes=hashes,
            owned_sha256=queue["owned_sha256"],
            protected_sha256=queue["protected_sha256"],
            native_snapshot_sha256=copies,
            driver_sha256=sha(out / "driver.py"),
            groups=groups,
            planned_total_checks=72,
            planned_native_captures=69,
            planned_actual_parent_checks=85,
            planned_conditional_references=170,
            planned_carried_references=130,
            source_seam_AST_audit=queue["source_seam_AST_audit"],
            port_AST_audit=queue["port_AST_audit"],
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


def run(out, group, cpu):
    inputs = json.loads((out / "inputs.json").read_text())
    if group not in inputs["groups"]:
        raise ValueError("Choose a prepared bounded group")
    target = out / ("run-" + group)
    target.mkdir(exist_ok=False)
    for path, expected in inputs["source_hashes"].items():
        if sha(out / "source" / path) != expected:
            raise ValueError("Frozen source changed: " + path)
    for path, expected in inputs["native_snapshot_sha256"].items():
        if sha(out / path) != expected:
            raise ValueError("Frozen native source changed: " + path)
    if sha(out / "driver.py") != inputs["driver_sha256"]:
        raise ValueError("Frozen runner changed")
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
        CELLS_CATALOG_JOIN_CPU=str(cpu),
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
    os.sched_setaffinity(0, {cpu})
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(out / "source/src"), str(out / "source")]
    from validation.assembly.component_process import run_bounded

    write(
        target / "execution.json",
        dict(group=group, cpu=cpu, command=command, requested_round=True, automatic_retry=False),
    )
    try:
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
        tests = ET.parse(target / "tests.xml").getroot().findall(".//testcase")
        assert len(tests) == len(inputs["groups"][group])
        assert all(
            all(t.find(tag) is None for tag in ("failure", "error", "skipped")) for t in tests
        )
        reports = [
            json.loads(p.read_text())
            for p in (target / "evidence/normal-catalog-join").glob("isolated-*/comparison.json")
        ]
        assert all(
            row["completed"] and row["exact_native"] and row["maximum_error_fraction"] <= 1
            for row in reports
        )
        for path, expected in (inputs["owned_sha256"] | inputs["protected_sha256"]).items():
            assert sha(ROOT / path) == expected, path
        write(
            target / "result.json",
            dict(
                status="passed",
                group=group,
                checks=len(tests),
                resources=resources,
                reports=reports,
                source_unchanged=True,
                conditional_local_only=True,
                carried_diagnostic_only=True,
                physical_or_full_native_parity=False,
                automatic_followup=False,
            ),
        )
    except BaseException as error:
        write(
            target / "failure.json",
            dict(
                status="failed",
                type=type(error).__name__,
                message=str(error),
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
