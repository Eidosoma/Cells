"""Frozen, resource-bounded import-origin metadata controls; no numerical probes."""

import argparse
import ast
import base64
import csv
import hashlib
import importlib.abc
import io
import json
import os
import resource
import runpy
import subprocess
import sys
import traceback
from pathlib import Path

from validation import source_snapshot as snapshot
from validation.betse import betse_mesh_lifecycle_preparation_guard as guard
from validation.betse import betse_normal_channel_join_runtime as runtime

ROOT = Path(__file__).resolve().parents[2]
OWN = "validation/betse/betse_native_numpy_copy_origin_software.py"
PRODUCTION = "src/cells/processes/betse_native_numpy_copy_origin.py"
TEST = "tests/unit/test_betse_native_numpy_copy_origin.py"
CONSUMER = "src/cells/processes/betse_native_parameter_colormap_runtime.py"
CLOSURE_TOOL = (
    "agent-work/cells-worker-01/workfiles/betse_normal_ecm_reviewed_successors_resources.py"
)
LIMITS = dict(timeout=480, max_rss_bytes=2**30, min_available_bytes=8 * 2**30)
EXPECTED_CASES = 42
NATIVE = "/mnt/workspaces/Cells/betse-v1.5.0/"
PILLOW = Path("/mnt/workspaces/Cells/pillow-overlay-12.3.0-20261030-01")
BEARTYPE = Path("/mnt/workspaces/Cells/beartype-overlay-0.22.9-20261031-01")
CPU_SITE = Path("/mnt/workspaces/Cells/venv-cpu/lib/python3.13/site-packages")
CONSTANT_MODULE = "cells.processes.mobile_channel_gates"
CONSTANT_SOURCE = "src/cells/processes/mobile_channel_gates.py"
CONSTANT_NAME = "MAX_GATE_EXIT_PER_S"
CONSTANT_HELPER = "src/cells/processes/voltage_gates.py"
DECLARATIONS = (
    (CONSTANT_MODULE, CONSTANT_SOURCE, (CONSTANT_NAME,)),
    ("cells.models.bioelectric_cell", "src/cells/models/bioelectric_cell.py", ("Z", "NU")),
    ("cells.models.source_pair", "src/cells/models/source_pair.py", ("NU",)),
    (
        "cells.models.compartment_reactions",
        "src/cells/models/compartment_reactions.py",
        ("ROUND_ATOL",),
    ),
)


def write(path, value):
    snapshot.write_json(path, value)


def numpy_files(origin):
    origin._files()
    rows = csv.reader(io.StringIO((origin.SITE / origin.RECORD).read_text()))
    result = {}
    for name, encoded, size in rows:
        if not name.startswith(("numpy/", "numpy.libs/", "numpy-2.5.3.dist-info/")):
            continue
        path = origin.SITE / name
        if not encoded:
            continue
        if (
            not encoded.startswith("sha256=")
            or path.resolve() != path
            or not size.isdecimal()
            or not path.is_file()
        ):
            raise ValueError("Exact existing NumPy wheel declaration required")
        digest = base64.urlsafe_b64decode(encoded.split("=", 1)[1] + "==").hex()
        if len(digest) != 64:
            raise ValueError("Exact NumPy wheel SHA required")
        result[str(path)] = dict(sha256=digest, bytes=int(size))
    result[str(origin.SITE / origin.RECORD)] = dict(
        sha256=origin.PINS[origin.RECORD], bytes=(origin.SITE / origin.RECORD).stat().st_size
    )
    return result


def _libraries():
    result = {}
    for line in Path("/proc/self/maps").read_text().splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) != 6 or not fields[5].startswith("/"):
            continue
        path = Path(fields[5])
        if ".so" not in path.name or str(path) in result:
            continue
        if not path.is_file() or path.resolve() != path:
            # Symlink-resolved system library names are reported canonically.
            path = path.resolve(strict=True)
        result[str(path)] = snapshot.digest(path)
    return result


def dependency_files(origin):
    """Prospective files of the declared definition-only integration libraries."""
    roots = (PILLOW, BEARTYPE, origin.SITE, CPU_SITE)
    result, packages = {}, {}
    for name in (
        "scipy",
        "PIL",
        "jax",
        "jaxlib",
        "ml_dtypes",
        "matplotlib",
        "beartype",
        "opt_einsum",
        "scipy.libs",
        "pillow.libs",
        "matplotlib.libs",
    ):
        path = next((root / name for root in roots if (root / name).is_dir()), None)
        if path is None:
            continue
        packages[name] = str(path)
        for item in sorted(path.rglob("*")):
            if item.is_file() and "__pycache__" not in item.parts:
                if item.resolve() != item:
                    raise ValueError("Linked integration-library file")
                result[str(item)] = dict(sha256=snapshot.digest(item), bytes=item.stat().st_size)
    return result, packages


def _verify_loaded(inputs, manifest, producers):
    if producers["measured_cpu_affinity"] != [inputs["cpu"]]:
        raise ValueError("Worker affinity changed")
    if producers["executable"]["path"] != str(Path(sys.executable).resolve()):
        raise ValueError("Worker executable changed")
    if snapshot.digest(producers["executable"]["path"]) != producers["executable"]["sha256"]:
        raise ValueError("Worker executable bytes changed")
    frozen = Path(inputs["frozen_source"])
    loaded, numerical = set(), {}
    for name, row in producers["loaded_files"].items():
        path = Path(row["path"])
        if row.get("unavailable") or snapshot.digest(path) != row.get("sha256"):
            raise ValueError("Changed loaded producer: " + name)
        if path.is_relative_to(frozen):
            relative = str(path.relative_to(frozen))
            if manifest["files"].get(relative, {}).get("sha256") != row["sha256"]:
                raise ValueError("Unbound frozen producer")
            loaded.add(relative)
        elif name.split(".")[0] in ("cells", "validation") or name == Path(TEST).stem:
            raise ValueError("Live checkout producer escaped the image")
        if name == "numpy" or name.startswith("numpy."):
            declared = inputs["numpy_wheel_files"].get(str(path))
            if declared != dict(sha256=row["sha256"], bytes=path.stat().st_size):
                raise ValueError("Loaded NumPy producer differs from the pinned wheel")
            numerical[name] = row
        elif name.split(".")[0] in inputs["definition_packages"]:
            declared = inputs["definition_files"].get(str(path))
            if declared != dict(sha256=row["sha256"], bytes=path.stat().st_size):
                raise ValueError("Definition import escaped declared runtime")
    missing = sorted({OWN, PRODUCTION, TEST, CONSUMER} - loaded)
    return sorted(loaded), numerical, missing


def child(output, cpu, manifest_sha256):
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    inputs = json.loads((output / "inputs.json").read_text())
    snapshot.verify(ROOT, manifest_sha256=manifest_sha256)
    if (
        os.sched_getaffinity(0) != {cpu}
        or inputs["cpu"] != cpu
        or inputs["limits"] != LIMITS
        or inputs["source_manifest_sha256"] != manifest_sha256
        or inputs["frozen_source"] != str(ROOT)
        or inputs["expected_cases"] != EXPECTED_CASES
    ):
        raise ValueError("Frozen child declaration changed")
    attempted, reports, definition_calls, code = [], [], {}, None
    constant_calls, constant_frames, constant_specs = {}, {}, {}
    for module, source, names in DECLARATIONS:
        path = ROOT / source
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != inputs["sources"][source]:
            raise ValueError("Frozen import-time constant source changed")
        tree = ast.parse(raw)
        nodes = {}
        for name in names:
            node = next(
                n
                for n in tree.body
                if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)
            )
            nodes[name] = (node.lineno, node.end_lineno)
        constant_specs[module] = (path, compile(raw, str(path), "exec", dont_inherit=True), nodes)
    helper_path = ROOT / CONSTANT_HELPER
    helper_raw = helper_path.read_bytes()
    if hashlib.sha256(helper_raw).hexdigest() != inputs["sources"][CONSTANT_HELPER]:
        raise ValueError("Frozen constant helper changed")
    helper_codes = {}

    def collect_codes(value):
        helper_codes[value.co_qualname] = value
        for item in value.co_consts:
            if type(item) is type(value):
                collect_codes(item)

    collect_codes(compile(helper_raw, str(helper_path), "exec", dont_inherit=True))
    previous, trace = sys.getprofile(), sys.gettrace()

    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] == "betse":
                attempted.append(dict(kind="forbidden_import", name=fullname))
                raise AssertionError("Original BETSE package import forbidden")

    def importing(frame):
        for _ in range(128):
            if frame is None:
                return False
            module = frame.f_globals.get("__name__", "")
            spec = frame.f_globals.get("__spec__")
            if (
                frame.f_code.co_name == "<module>"
                and module.split(".")[0] in ("numpy", "scipy", "jax", "jaxlib", "ml_dtypes")
                and getattr(spec, "_initializing", False) is True
            ):
                return True
            frame = frame.f_back
        return False

    def profile(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        module = frame.f_globals.get("__name__", "")
        if (
            event == "call"
            and module in constant_specs
            and frame.f_code.co_name == "<module>"
            and frame.f_code.co_filename == str(constant_specs[module][0])
        ):
            constant_path, constant_code, _ = constant_specs[module]
            spec = frame.f_globals.get("__spec__")
            observed = sys.modules.get(module)
            if (
                observed is None
                or frame.f_globals is not vars(observed)
                or frame.f_code.co_filename != str(constant_path)
                or frame.f_code != constant_code
                or getattr(spec, "origin", None) != str(constant_path)
                or getattr(spec, "_initializing", False) is not True
            ):
                raise ValueError("Genuine frozen initializing constant module required")
            constant_frames[frame] = module
        constant_active = next(
            (
                owner + "." + name
                for current, owner in constant_frames.items()
                for name, (start, end) in constant_specs[owner][2].items()
                if start <= current.f_lineno <= end
                and getattr(current.f_globals.get("__spec__"), "_initializing", False) is True
            ),
            None,
        )
        if constant_active and event in ("call", "c_call"):
            name = (
                module + ":" + frame.f_code.co_qualname
                if event == "call"
                else (getattr(arg, "__module__", "") or "")
                + ":"
                + (getattr(arg, "__qualname__", "") or getattr(arg, "__name__", ""))
            )
            name = constant_active + "|" + name
            if len(constant_calls) >= 4096 and name not in constant_calls:
                raise ValueError("Bounded declaration call roster exceeded")
            constant_calls[name] = constant_calls.get(name, 0) + 1
        if event == "return":
            constant_frames.pop(frame, None)
        if event == "call":
            name = frame.f_code.co_name
            if module == "cells.processes.voltage_gates" and name != "<module>":
                expected = helper_codes.get(frame.f_code.co_qualname)
                if (
                    constant_active != CONSTANT_MODULE + "." + CONSTANT_NAME
                    or expected is None
                    or frame.f_code.co_filename != str(helper_path)
                    or frame.f_code != expected
                    or frame.f_globals is not vars(sys.modules[module])
                ):
                    attempted.append(
                        dict(kind="foreign_declaration_helper", module=module, name=name)
                    )
                    raise AssertionError("Only the exact original constant helper is admitted")
            forbidden = (
                module == "betse"
                or module.startswith("betse.")
                or frame.f_code.co_filename.startswith(NATIVE)
                or module.startswith("cells.processes.betse_native_")
                and module != "cells.processes.betse_native_numpy_copy_origin"
                and name in ("prepare", "from_world", "from_seed", "from_geometry", "bind")
                or module == "numpy.lib._function_base_impl"
                and name in ("copy", "_copy_dispatcher")
                or module.startswith("numpy.linalg")
                and name in ("pinv", "svd", "solve", "inv")
                or module == "cells.processes.voltage_gates"
                and name != "<module>"
                and not constant_active
            )
            if forbidden:
                attempted.append(dict(kind="forbidden_body", module=module, name=name))
                raise AssertionError("Native/copy/argument/operator execution forbidden")
        if event == "c_call":
            module, name = getattr(arg, "__module__", "") or "", getattr(arg, "__name__", "")
            if module.startswith("numpy") and name in (
                "array",
                "asarray",
                "copy",
                "dot",
                "matmul",
                "random",
                "rand",
                "randn",
                "seed",
                "normal",
            ):
                if name in ("array", "asarray") and constant_active:
                    pass  # Exact declared constant call tree, recorded separately above.
                elif name in ("array", "asarray") and importing(frame):
                    caller = frame.f_globals.get("__name__", "")
                    key = caller + ":" + module + "." + name
                    definition_calls[key] = definition_calls.get(key, 0) + 1
                else:
                    attempted.append(dict(kind="forbidden_c_probe", module=module, name=name))
                    raise AssertionError("Numerical/RNG probe forbidden")

    class Reports:
        def pytest_collection_finish(self, session):
            ids = [item.nodeid for item in session.items]
            write(output / "collected.json", dict(nodeids=ids, count=len(ids)))
            if len(ids) != EXPECTED_CASES or len(set(ids)) != len(ids):
                raise ValueError("Unexpected observer control roster")

        def pytest_runtest_logreport(self, report):
            row = dict(
                nodeid=report.nodeid,
                phase=report.when,
                outcome=report.outcome,
                traceback=str(report.longrepr) if report.failed else None,
            )
            reports.append(row)
            path = hashlib.sha256((report.nodeid + report.when).encode()).hexdigest() + ".json"
            write(output / "case-reports" / path, row)

    block = Block()
    sys.meta_path.insert(0, block)
    cleanup = []
    try:
        sys.setprofile(profile)
        import pytest

        code = pytest.main(
            [
                "-q",
                "--noconftest",
                "-c",
                "/dev/null",
                "-p",
                "no:cacheprovider",
                str(ROOT / TEST),
                "--junitxml=" + str(output / "junit.xml"),
                "--basetemp=" + str(output / "tmp"),
            ],
            plugins=[Reports()],
        )
    finally:
        actual_restored = sys.getprofile() is profile and sys.gettrace() is trace
        for setter, target in ((sys.setprofile, previous), (sys.settrace, trace)):
            try:
                setter(target)
            except BaseException as error:
                cleanup.append(dict(type=type(error).__name__, id=id(error)))
        if block in sys.meta_path:
            sys.meta_path.remove(block)
        write(
            output / "native-entry-guard.json",
            dict(
                attempted=attempted,
                observer_returned_outer_hooks=actual_restored,
                outer_hooks_restored=sys.getprofile() is previous and sys.gettrace() is trace,
                cleanup_errors=cleanup,
                pytest_completed=code is not None,
                allowed=(
                    "One fresh pinned NumPy import; dependency definitions for the real "
                    "colormap metadata consumer; stdlib observer controls"
                ),
                library_definition_c_calls=definition_calls,
                declaration_constant_evaluation=dict(
                    declarations=inputs["declaration_constant_evaluation"],
                    call_counts=constant_calls,
                    numerical_constant_work=bool(constant_calls),
                    scope=(
                        "Exact frozen initializing module assignment only; not a model run or probe"
                    ),
                ),
                numerical_or_argument_probe_calls=0,
                actual_native_execution=False,
            ),
        )
        write(output / "runtime-producers.json", runtime.inventory())
        write(output / "loaded-libraries.json", _libraries())
        # Independently retain the import observation even when the positive
        # control fails before its own evidence/assertions or consumer import.
        observed = sys.modules.get("cells.processes.betse_native_numpy_copy_origin")
        if observed is not None:
            try:
                write(output / "origin-final.json", observed.record())
            except BaseException as error:
                write(
                    output / "origin-record-failure.json",
                    dict(type=type(error).__name__, id=id(error)),
                )
    write(output / "pytest-exit.json", dict(returncode=int(code)))
    return int(code) if not attempted and not cleanup and actual_restored else 1


def prepare(output, cpu, *, run=False):
    from cells.processes import betse_native_numpy_copy_origin as origin

    output = output.absolute()
    if (
        not output.is_relative_to("/mnt/workspaces/Cells")
        or output.resolve() != output
        or type(cpu) is not int
        or cpu != 4
        or os.sched_getaffinity(0) != {cpu}
    ):
        raise ValueError("Fresh canonical output and coordinated singleton CPU4 required")
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
    external = numpy_files(origin)
    definitions, packages = dependency_files(origin)
    output.mkdir(parents=True, exist_ok=False)
    closure = runpy.run_path(str(ROOT / CLOSURE_TOOL))["closure"]
    files = closure(ROOT, [OWN, PRODUCTION, TEST, CONSUMER])
    files[CLOSURE_TOOL] = snapshot.digest(ROOT / CLOSURE_TOOL)
    frozen = output / "source"
    manifest = snapshot.freeze(ROOT, frozen, {name: name for name in files})
    pin = snapshot.digest(frozen / "SNAPSHOT.json")
    command = [
        sys.executable,
        "-B",
        "-m",
        "validation.betse.betse_native_numpy_copy_origin_software",
        "--output",
        str(output),
        "--cpu",
        str(cpu),
        "--child",
        "--manifest-sha256",
        pin,
    ]
    inputs = dict(
        kind="cells.numpy_copy_origin_software@1",
        cpu=cpu,
        threads=1,
        limits=LIMITS,
        source_manifest_sha256=pin,
        frozen_source=str(frozen),
        sources={n: r["sha256"] for n, r in manifest["files"].items()},
        numpy_wheel_files=external,
        definition_files=definitions,
        definition_packages=packages,
        numpy_primary_path=str(origin.SITE),
        expected_cases=EXPECTED_CASES,
        command=command,
        held=not run,
        import_origin_positive=True,
        declaration_constant_evaluation=[
            dict(
                module=module,
                names=names,
                source=source,
                source_sha256=manifest["files"][source]["sha256"],
            )
            for module, source, names in DECLARATIONS
        ],
        actual_native_release=False,
        scientific_credit=0,
        automatic_retry=False,
    )
    write(output / "inputs.json", inputs)
    if not run:
        return 0
    for name in ("process", "case-reports", "tmp", "evidence"):
        (output / name).mkdir()
    environment = dict(os.environ)
    environment.update(
        PYTHONPATH=os.pathsep.join(
            (
                str(frozen / "src"),
                str(frozen),
                str(PILLOW),
                str(BEARTYPE),
                str(origin.SITE),
                str(CPU_SITE),
            )
        ),
        PYTHONNOUSERSITE="1",
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        VECLIB_MAXIMUM_THREADS="1",
        CUDA_VISIBLE_DEVICES="",
        CELLS_NUMPY_COPY_ORIGIN_EVIDENCE=str(output / "evidence"),
        TMPDIR=str(output / "tmp"),
    )
    environment.pop("PYTEST_ADDOPTS", None)
    try:
        try:
            process = guard.run_bounded(
                command,
                directory=output / "process",
                cwd=frozen,
                env=environment,
                process_tree_memory_metric="rss",
                **LIMITS,
            )
        except subprocess.CalledProcessError:
            process = json.loads((output / "process/failure.json").read_text())
        snapshot.verify(frozen, manifest_sha256=pin)
        producers = json.loads((output / "runtime-producers.json").read_text())
        loaded, numpy, missing = _verify_loaded(inputs, manifest, producers)
        native = json.loads((output / "native-entry-guard.json").read_text())
        origin_record = json.loads((output / "origin-final.json").read_text())
        passed = (
            process["returncode"] == 0
            and missing == []
            and native["attempted"] == []
            and native["observer_returned_outer_hooks"]
            and native["outer_hooks_restored"]
            and native["cleanup_errors"] == []
            and origin_record["completed"]
            and origin_record["hooks_restored"]
            and origin_record["source_error"] is None
            and origin_record["capture_errors"] == origin_record["cleanup_errors"] == []
        )
        artifacts = {
            str(p.relative_to(output)): snapshot.digest(p)
            for folder in ("case-reports", "evidence")
            for p in sorted((output / folder).rglob("*"))
            if p.is_file()
        }
        for name in (
            "junit.xml",
            "collected.json",
            "pytest-exit.json",
            "runtime-producers.json",
            "native-entry-guard.json",
            "loaded-libraries.json",
            "origin-final.json",
        ):
            artifacts[name] = snapshot.digest(output / name)
        write(
            output / "result.json",
            dict(
                status="passed_metadata_controls" if passed else "failed_metadata_controls",
                process=process,
                snapshot_sha256=pin,
                loaded_sources=loaded,
                missing_required_producers=missing,
                loaded_numpy=numpy,
                artifact_sha256=artifacts,
                actual_native_execution=False,
                numerical_probe_calls=0,
                scientific_credit=0,
            ),
        )
        return 0 if passed else 1
    except BaseException as error:
        write(
            output / "failure.json",
            dict(
                status="failed",
                type=type(error).__name__,
                traceback=traceback.format_exc(),
                snapshot_sha256=pin,
                actual_native_execution=False,
                automatic_retry=False,
            ),
        )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cpu", type=int, default=4)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--manifest-sha256", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.child:
        if args.run or not args.manifest_sha256:
            parser.error("Frozen child only")
        return child(args.output.absolute(), args.cpu, args.manifest_sha256)
    if args.manifest_sha256:
        parser.error("Only a child accepts a snapshot pin")
    return prepare(args.output, args.cpu, run=args.run)


if __name__ == "__main__":
    raise SystemExit(main())
