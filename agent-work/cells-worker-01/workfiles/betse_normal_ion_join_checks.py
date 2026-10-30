"""Freeze the normal-ion-join checks; execution needs a coordinated free CPU."""

import argparse
import ast
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = "agent-work/cells-worker-01/workfiles/"
QUEUE = WORK + "betse_normal_ion_join_workqueue.json"
TEST = "tests/unit/test_betse_normal_ion_join.py"
FIXTURES = "validation/betse/betse_normal_ion_join_fixtures.py"
REFERENCE = "validation/betse/betse_normal_ion_join_reference.py"
PROTOCOL = "validation/betse/betse_normal_ion_join_protocol.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, record):
    with Path(path).open("x") as stream:
        json.dump(record, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def matrix_count(source):
    fixture_tree = ast.parse((source / FIXTURES).read_text())
    cases = next(
        ast.literal_eval(node.value)
        for node in fixture_tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "CASES" for t in node.targets)
    )
    rows, captures = {}, 0
    for node in ast.parse((source / TEST).read_text()).body:
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
            continue
        factors = []
        for deco in node.decorator_list:
            if (
                isinstance(deco, ast.Call)
                and isinstance(deco.func, ast.Attribute)
                and deco.func.attr == "parametrize"
            ):
                values = deco.args[1]
                factors.append(
                    len(cases)
                    if isinstance(values, ast.Attribute) and ast.unparse(values) == "fixtures.CASES"
                    else len(ast.literal_eval(values))
                )
        rows[node.name] = math.prod(factors)
        captures += rows[node.name] * sum(
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "isolated"
            for call in ast.walk(node)
        )
    if len(cases) != 12 or sum(rows.values()) != 42 or captures != 15:
        raise ValueError("Static normal-ion-join matrix changed")
    return rows


def environment(out):
    return dict(
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        PYTHONPATH=str(out / "source/src") + os.pathsep + str(out / "source"),
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        BLIS_NUM_THREADS="1",
        VECLIB_MAXIMUM_THREADS="1",
        TF_NUM_INTRAOP_THREADS="1",
        TF_NUM_INTEROP_THREADS="1",
        CUDA_VISIBLE_DEVICES="",
        MALLOC_ARENA_MAX="2",
        TMPDIR=str(out / "tmp"),
        XDG_CACHE_HOME=str(out / "cache"),
        CELLS_COMPONENT_EVIDENCE=str(out / "evidence"),
    )


def prepare(out):
    queue = json.loads((ROOT / QUEUE).read_text())
    protocol = json.loads((ROOT / PROTOCOL).read_text())
    inventory = json.loads((ROOT / queue["inventory"]).read_text())
    out.mkdir(exist_ok=False)
    source = out / "source"
    source.mkdir()
    for name in ("src", "tests", "validation", "configs"):
        shutil.copytree(
            ROOT / name,
            source / name,
            ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".ruff_cache"),
        )
    for name in (
        "pyproject.toml",
        "AGENTS.md",
        QUEUE,
        queue["contract"],
        queue["inventory"],
        queue["runner"],
    ):
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    for name in ("tmp", "cache", "evidence", "native-inputs"):
        (out / name).mkdir()
    for path, expected in (queue["owned_sha256"] | queue["protected_sha256"]).items():
        if sha(ROOT / path) != expected or sha(source / path) != expected:
            raise ValueError("Owned/protected source changed: " + path)
    original = protocol["native_source"]
    native = Path(original["checkout"])
    installed = Path(original["installed_package"]).parent
    revision = subprocess.check_output(
        ["git", "-C", str(native), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != original["revision"] or revision != inventory["revision"]:
        raise ValueError("Pinned native revision changed")
    native_copies = {}
    pins = original["source_sha256"] | inventory["source_sha256"]
    for name, expected in pins.items():
        for label, base in (("checkout", native), ("installed", installed)):
            data = (base / name).read_bytes()
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError("Pinned native source changed: " + name)
            target = out / "native-inputs" / label / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            native_copies[str(target.relative_to(out))] = expected
    for name, sites in inventory["source_sites"].items():
        tree = ast.parse((native / name).read_bytes())
        for function, site in sites.items():
            node = next(
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef)
                and node.name == function
                and node.lineno == site["first_line"]
            )
            digest = hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
            if digest != site["AST_sha256"] or node.end_lineno != site["last_line"]:
                raise ValueError("Native inventory AST changed: " + function)
    parsed = []
    for name in (*queue["owned"], queue["runner"]):
        if name.endswith(".py"):
            ast.parse((source / name).read_text(), filename=name)
            parsed.append(name)
    for node in ast.walk(ast.parse((source / REFERENCE).read_text())):
        names = (
            [item.name for item in node.names]
            if isinstance(node, ast.Import)
            else [node.module or ""]
            if isinstance(node, ast.ImportFrom)
            else []
        )
        if any(name.split(".")[0] not in sys.stdlib_module_names for name in names):
            raise ValueError("Independent reference imports a nonstandard package")
    hashes = {str(p.relative_to(source)): sha(p) for p in sorted(source.rglob("*")) if p.is_file()}
    for name, expected in hashes.items():
        if name not in queue["coordinated_shared_edit_paths"] and sha(ROOT / name) != expected:
            raise ValueError("Concurrent source change during capture: " + name)
    counts = matrix_count(source)
    (out / "driver.py").write_bytes(Path(__file__).read_bytes())
    command = [
        sys.executable,
        "-B",
        "-m",
        "pytest",
        "--noconftest",
        "-p",
        "no:cacheprovider",
        "-q",
        TEST,
        "--basetemp",
        str(out / "tmp/qualification"),
        "--junitxml",
        str(out / "tests.xml"),
    ]
    write(
        out / "inputs.json",
        dict(
            kind="cells.betse_normal_ion_join_checks@1",
            status="prepared_not_executed",
            source_snapshot=str(source),
            source_hashes=hashes,
            owned_sha256=queue["owned_sha256"],
            protected_sha256=queue["protected_sha256"],
            coordinated_shared_edit_paths=queue["coordinated_shared_edit_paths"],
            historical_shared_sha256=queue["historical_shared_sha256"],
            driver_sha256=sha(out / "driver.py"),
            native_original_source=original,
            native_snapshot_sha256=native_copies,
            inventory=queue["inventory"],
            inventory_verified_functions=sum(map(len, inventory["source_sites"].values())),
            parsed_files=parsed,
            reference_imports_standard_library_only=True,
            AST_check_counts=counts,
            planned_checks=42,
            planned_main_complete_calls=48,
            planned_main_observed_frames=888,
            planned_fresh_native_captures=15,
            planned_independent_reference_forms=24,
            resource_limits=protocol["resources"],
            environment=environment(out),
            command=command,
            execution_requires_Chief_cpu_coordination=True,
            scientific_module_imports_during_preparation=0,
            numerical_runs=0,
            pytest_collection_runs=0,
            active_job_status_reads=0,
            automatic_launch=False,
            automatic_polling=False,
            automatic_followup=False,
            gpu_run=False,
        ),
    )
    print(
        json.dumps(
            dict(
                status="prepared_not_executed",
                inputs=str(out / "inputs.json"),
                sha256=sha(out / "inputs.json"),
                checks=42,
                numerical_runs=0,
            )
        )
    )


def run(out, cpu):
    inputs = json.loads((out / "inputs.json").read_text())
    for name in ("result.json", "failure.json", "process", "execution.json"):
        if (out / name).exists():
            raise FileExistsError(out / name)
    for name, expected in inputs["source_hashes"].items():
        if sha(out / "source" / name) != expected:
            raise ValueError("Frozen source changed: " + name)
    if sha(out / "driver.py") != inputs["driver_sha256"]:
        raise ValueError("Frozen checker changed")
    for name, expected in inputs["native_snapshot_sha256"].items():
        if sha(out / name) != expected:
            raise ValueError("Pinned native snapshot changed: " + name)
    os.sched_setaffinity(0, {cpu})
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(out / "source/src"), str(out / "source")]
    from validation.assembly.component_process import run_bounded

    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("JAX_", "XLA_", "CELLS_", "PYTEST_"))
        and key not in {"PYTHONPATH", "PYTHONHOME", "CUDA_VISIBLE_DEVICES"}
    }
    env.update(inputs["environment"] | dict(CELLS_ION_JOIN_CPU=str(cpu)))
    folder = out / "process"
    folder.mkdir()
    write(
        out / "execution.json",
        dict(
            cpu=cpu,
            authorization="Explicit coordinated CPU flag",
            command=inputs["command"],
            automatic_followup=False,
        ),
    )
    try:
        resources = run_bounded(
            inputs["command"],
            directory=folder,
            cwd=out / "source",
            env=env,
            timeout=480,
            max_rss_bytes=2**30,
            min_available_bytes=8 * 2**30,
            process_tree_memory_metric="rss",
        )
        tests = ET.parse(out / "tests.xml").getroot().findall(".//testcase")
        assert len(tests) == 42
        assert all(
            all(row.find(key) is None for key in ("failure", "error", "skipped")) for row in tests
        )
        evidence = out / "evidence/normal-ion-join"
        comparisons = [
            json.loads(path.read_text()) for path in evidence.glob("isolated-*/comparison.json")
        ]
        assert len(comparisons) == 12 and sum(row["complete_calls"] for row in comparisons) == 48
        assert sum(row["frames"] for row in comparisons) == 888
        assert all(
            row["completed"]
            and row["exact_host_native_correspondence"]
            and row["maximum_error_fraction"] <= 1
            for row in comparisons
        )
        manifests = list(evidence.glob("isolated-*/native/manifest.json"))
        refs = list(evidence.glob("isolated-*/reference-*.json"))
        assert len(manifests) == 15 and len(refs) == 24
        for path in refs:
            record = json.loads(path.read_text())
            assert record["production_imports_denied"] and not record["loaded_production_modules"]
            assert record["runtime"]["measured_cpu_affinity"] == [cpu]
        for name, expected in inputs["source_hashes"].items():
            assert sha(out / "source" / name) == expected, name
        for name, expected in (inputs["owned_sha256"] | inputs["protected_sha256"]).items():
            assert sha(ROOT / name) == expected, name
        runtime = json.loads((evidence / "runtime.json").read_text())
        assert runtime["measured_cpu_affinity"] == [cpu]
        write(
            out / "result.json",
            dict(
                kind=inputs["kind"],
                status="passed",
                checks=42,
                check_ids=[row.attrib for row in tests],
                fresh_native_captures=15,
                independent_reference_forms=24,
                main_complete_calls=48,
                main_observed_frames=888,
                maximum_error_fraction=max(row["maximum_error_fraction"] for row in comparisons),
                resources=resources,
                runtime=runtime,
                source_revision=inputs["native_original_source"]["revision"],
                owned_sha256=inputs["owned_sha256"],
                protected_sources_unchanged=True,
                coordinated_shared_edit_paths=inputs["coordinated_shared_edit_paths"],
                historical_shared_sha256=inputs["historical_shared_sha256"],
                exact_host_native_correspondence=True,
                field_voltage_or_full_native_solver_parity=False,
                physical_charge_or_energy_conservation_inferred=False,
                gpu_run=False,
                automatic_followup=False,
            ),
        )
    except BaseException:
        write(
            out / "failure.json",
            dict(
                status="failed",
                traceback=traceback.format_exc(),
                automatic_retry=False,
                automatic_followup=False,
            ),
        )
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "run"))
    parser.add_argument("directory", type=Path)
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--cpu-coordinated", action="store_true")
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.directory.resolve())
    else:
        if not args.cpu_coordinated or args.cpu is None or args.cpu < 0:
            parser.error("Numerical validation awaits an explicitly coordinated free CPU")
        run(args.directory.resolve(), args.cpu)


if __name__ == "__main__":
    main()
