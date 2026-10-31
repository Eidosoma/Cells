"""Run only the repository's native-blocked tissue software controls.

Use ``python -m validation.betse.betse_tissue_source_software --output PATH``.
Outputs belong under /mnt/workspaces/Cells. Native/scientific qualification is
held; the polygon numerical panel is explicitly deselected by this runner.
"""

import argparse
import hashlib
import json
import os
import resource
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS = (
    "tests/unit/test_betse_native_single_cell_core_preparation.py",
    "tests/unit/test_betse_native_single_cell_core_contract_repairs.py",
    "tests/unit/test_fixed_polygon_removal.py",
)
SOURCES = (
    "src/cells/processes/betse_native_single_cell_core_preparation.py",
    "src/cells/processes/fixed_polygon_removal.py",
    "validation/betse/betse_native_single_cell_core_synthetic.py",
    "validation/betse/betse_tissue_source_software.py",
    "validation/betse/betse_mesh_lifecycle_preparation_guard.py",
    "validation/geometry/fixed_polygon_removal_fixtures.py",
    "validation/geometry/fixed_polygon_removal_reference.py",
    *TESTS,
)


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def run_tests(output):
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    import pytest

    args = [
        "-q",
        "-c",
        str(ROOT / "pyproject.toml"),
        "-p",
        "no:cacheprovider",
        *(str(ROOT / name) for name in TESTS),
        "-k",
        "software",
        "--junitxml=" + str(output / "junit.xml"),
        "--basetemp=" + str(output / "tmp"),
    ]
    code = pytest.main(args)
    write(output / "pytest-exit.json", dict(returncode=int(code), argv=args))
    modules = {}
    for name, module in list(sys.modules.items()):
        if (
            name == "cells"
            or name.startswith(("cells.", "validation.", "PIL."))
            or name == "PIL"
            or name.startswith("test_betse_native_single_cell_core_")
            or name == "test_fixed_polygon_removal"
        ) and getattr(module, "__file__", None):
            path = Path(module.__file__).resolve()
            modules[name] = dict(
                path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest()
            )
    write(output / "runtime-producers.json", modules)
    for name, value in modules.items():
        if name == "cells" or name.startswith(("cells.", "validation.")):
            if not Path(value["path"]).is_relative_to(ROOT):
                raise RuntimeError("Control imported a source outside the checkout: " + name)
    from cells.processes import betse_native_single_cell_core_preparation as core

    core._verify_sources()  # Hash checks only; no constructor, replay or operator call.
    return int(code)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--_child", action="store_true", help=argparse.SUPPRESS)
    options = parser.parse_args()
    output = options.output.resolve()
    if not output.is_relative_to(Path("/mnt/workspaces/Cells")):
        parser.error("Output must be under /mnt/workspaces/Cells")
    if os.sched_getaffinity(0) != {6}:
        parser.error("Run with taskset -c 6")
    if options._child:
        return run_tests(output)
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
    from validation.betse import betse_mesh_lifecycle_preparation_guard as guard

    output.mkdir(parents=True, exist_ok=False)
    (output / "guard").mkdir()
    (output / "evidence" / "core").mkdir(parents=True)
    producers = {}
    for relative in SOURCES:
        raw = (ROOT / relative).read_bytes()
        target = output / "execution-snapshot" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)
        producers[relative] = hashlib.sha256(raw).hexdigest()
    environment = dict(os.environ)
    pythonpath = os.pathsep.join((str(ROOT / "src"), str(ROOT)))
    if inherited_path := environment.get("PYTHONPATH"):
        pythonpath += os.pathsep + inherited_path
    environment.update(
        PYTHONPATH=pythonpath,
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        CELLS_DEC_PREREQUISITE_EVIDENCE=str(output / "evidence" / "core"),
        CELLS_COMPONENT_EVIDENCE=str(output / "evidence" / "polygon"),
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        VECLIB_MAXIMUM_THREADS="1",
        CUDA_VISIBLE_DEVICES="",
        JAX_PLATFORMS="cpu",
    )
    write(
        output / "inputs.json",
        dict(
            checkout=str(ROOT),
            source_sha256=producers,
            selection="software",
            tests=TESTS,
            scientific_qualification=False,
            positive_native_path_released=False,
            all11_native_owners_remain_invalid=True,
        ),
    )
    result = guard.run_bounded(
        [sys.executable, "-B", str(Path(__file__).resolve()), "--output", str(output), "--_child"],
        directory=output / "guard",
        cwd=ROOT,
        env=environment,
        max_rss_bytes=2**30,
        timeout=480,
        min_available_bytes=8 * 2**30,
    )
    changed = [
        relative
        for relative, digest in producers.items()
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != digest
    ]
    write(output / "post-run-source-check.json", dict(changed_during_run=changed))
    if changed:
        raise RuntimeError("Source changed during software controls: " + ", ".join(changed))
    result.update(
        scientific_qualification=False,
        native_parent_admitted=False,
        all11_native_owners_remain_invalid=True,
    )
    write(output / "result.json", result)
    print(json.dumps(dict(status=result["status"], output=str(output))))
    return int(result["returncode"])


if __name__ == "__main__":
    raise SystemExit(main())
