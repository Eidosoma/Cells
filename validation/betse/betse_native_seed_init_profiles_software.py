"""Frozen CPU5 software controls for held whole native tissue-profile mapping.

Uses the existing source snapshot, process resource and runtime inventory tools.
There is no native/phase/source execution mode in this software runner.
"""

import argparse
import importlib
import json
import os
import runpy
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from validation import source_snapshot as snapshot
from validation.betse import betse_normal_channel_join_runtime as runtime
from validation.betse import betse_normal_ecm_molecule_qualification_resources as resources

ROOT = Path(__file__).resolve().parents[2]
BASE = Path("/mnt/workspaces/Cells")
SOURCE = "src/cells/processes/betse_native_seed_init_profiles.py"
LITERAL = "src/cells/processes/betse_native_seed_init_profiles_source.py"
TEST = "tests/unit/test_betse_native_seed_init_profiles.py"
FILE = "validation/betse/betse_native_seed_init_profiles_software.py"
MODULE = "validation.betse.betse_native_seed_init_profiles_software"
SOFTWARE_RELEASE = "CELLS_NATIVE_SEED_INIT_PROFILES_SOFTWARE_RELEASED"
SOFTWARE_CPU = 5
OWNED = (SOURCE, LITERAL, TEST, FILE)
CLOSURE = "agent-work/cells-worker-01/workfiles/betse_normal_ecm_reviewed_successors_resources.py"
NATIVE_ROOT = "/mnt/workspaces/Cells/betse-v1.5.0"
FORBIDDEN_MODULES = frozenset(
    (
        "cells.processes.betse_native_seed_init_profiles_source",
        "cells.processes.betse_native_seed_init_core_source",
        "cells.processes.betse_native_seed_world_geometry_source",
        "cells.processes.betse_native_seed_voronoi_lifecycle_source",
        "cells.processes.betse_native_seed_voronoi_mesh_source",
        "cells.processes.betse_native_seed_voronoi_image_source",
        "cells.processes.betse_native_single_cell_poisson_source",
    )
)


def ref(path):
    return dict(path=str(path), sha256=snapshot.digest(Path(path)))


def is_forbidden_frame(frame):
    module = frame.f_globals.get("__name__", "")
    return (
        frame.f_code.co_filename.startswith(NATIVE_ROOT + os.sep)
        or module in FORBIDDEN_MODULES
        or module.startswith(("cells.numerics.", "numpy.linalg"))
        or (module == "random" and frame.f_code.co_name != "<module>")
    )


def prepare(directory, select=""):
    if ROOT != Path("/home/robert/Cells") or Path(__file__).resolve() != ROOT / FILE:
        raise ValueError("Prepare directly from the single Git checkout")
    if (directory / "source").exists():
        raise FileExistsError("Fresh immutable image required")
    names = runpy.run_path(str(ROOT / CLOSURE))["closure"](ROOT, list(OWNED))
    for name in (CLOSURE, "tests/__init__.py", "pyproject.toml"):
        names[name] = snapshot.digest(ROOT / name)
    manifest = snapshot.freeze(ROOT, directory / "source", {name: name for name in names})
    snapshot.write_json(
        directory / "inputs.json",
        dict(
            owned_files={n: manifest["files"][n]["sha256"] for n in OWNED},
            snapshot_sha256=snapshot.digest(directory / "source/SNAPSHOT.json"),
            git_revision=manifest["git_revision"],
            select=select,
            cpu=SOFTWARE_CPU,
            threads=1,
            metadata_bytes=512 * 2**20,
            software_bytes=2**30,
            wall_seconds=480,
            host_reserve_bytes=8 * 2**30,
            software_release_requested=os.environ.get(SOFTWARE_RELEASE) == "1",
            source_native_reference_or_scientific_release=False,
        ),
    )
    snapshot.assert_checkout_unchanged(directory / "source")


def child(directory):
    if (
        os.environ.get(SOFTWARE_RELEASE) != "1"
        or os.sched_getaffinity(0) != {SOFTWARE_CPU}
        or not __debug__
    ):
        raise ValueError("Explicit software CPU5 release/assertions required")
    inputs = json.loads((directory / "inputs.json").read_text())
    if not inputs["software_release_requested"] or ROOT != directory / "source":
        raise ValueError("Actual fresh frozen software child required")
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    for name, pin in inputs["owned_files"].items():
        if manifest["files"][name]["sha256"] != pin:
            raise ValueError("Exact selected producer required")
    initial = (sys.getprofile(), sys.gettrace())
    stage = importlib.import_module("cells.processes.betse_native_seed_init_profiles")
    if Path(stage.__file__).resolve() != ROOT / SOURCE:
        raise ValueError("Canonical frozen profile producer required")
    if any(n == "betse" or n.startswith("betse.") for n in sys.modules):
        raise ValueError("Native module loaded before software blockade")
    snapshot.write_json(directory / "source-plan.json", stage.source_plan())
    import pytest

    args = [
        "-q",
        "-x",
        "-p",
        "no:cacheprovider",
        str(ROOT / TEST),
        "--basetemp",
        str(directory / "pytest"),
        "--junitxml",
        str(directory / "junit.xml"),
    ]
    if inputs["select"]:
        args.extend(("-k", inputs["select"]))
    code = pytest.main(args)
    cases = list(ET.parse(directory / "junit.xml").iter("testcase"))
    guards = sorted((directory / "pytest").rglob("native-blocked.json"))
    records = [json.loads(p.read_text()) for p in guards]
    nodeids = {TEST + "::" + c.get("name") for c in cases}
    clean = (
        len(cases) == len(records) == len(nodeids)
        and all(
            not row["attempts"] and row["trace_restored"] and row["profile_restored"]
            for row in records
        )
        and {r["nodeid"] for r in records} == nodeids
    )
    snapshot.write_json(directory / "runtime.json", runtime.inventory())
    intact = sys.getprofile() is initial[0] and sys.gettrace() is initial[1]
    result = dict(
        status="completed" if code == 0 and clean and intact else "failed",
        pytest_status=int(code),
        cases=len(cases),
        complete_guards=clean,
        guards=[ref(p) for p in guards],
        source_plan=ref(directory / "source-plan.json"),
        runtime=ref(directory / "runtime.json"),
        source=ref(ROOT / SOURCE),
        literal=ref(ROOT / LITERAL),
        test=ref(ROOT / TEST),
        software=ref(ROOT / FILE),
        cpu_affinity=sorted(os.sched_getaffinity(0)),
        pid=os.getpid(),
        optimize=sys.flags.optimize,
        original_hooks_restored=intact,
        imports_scope=(
            "Shared runtime/definition bootstrap precedes per-case native/model/RNG guards"
        ),
        actual_source_native_reference_or_scientific_entries=0,
    )
    snapshot.write_json(
        directory / ("result.json" if result["status"] == "completed" else "failure.json"), result
    )
    if result["status"] != "completed":
        raise ValueError("Native-blocked software failed; evidence retained")
    return result


def software(directory, select=""):
    if os.environ.get(SOFTWARE_RELEASE) != "1" or os.sched_getaffinity(0) != {SOFTWARE_CPU}:
        raise ValueError("Explicit CPU5 software scope required")
    directory = Path(directory).absolute()
    if (
        not directory.is_relative_to(BASE)
        or directory.exists()
        or any(p.is_symlink() for p in (directory, *directory.parents))
    ):
        raise ValueError("Fresh unlinked isolated output required")
    directory.mkdir(parents=True)
    environment = {k: v for k, v in os.environ.items() if not k.startswith(("CELLS_", "PYTEST_"))}
    environment.update(
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONOPTIMIZE="0",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        VECLIB_MAXIMUM_THREADS="1",
        RAYON_NUM_THREADS="1",
        CUDA_VISIBLE_DEVICES="",
        JAX_PLATFORMS="cpu",
    )
    environment[SOFTWARE_RELEASE] = "1"
    metadata = directory / "metadata-process"
    metadata.mkdir()
    resources.run_bounded(
        [sys.executable, "-B", "-m", MODULE, "--prepare", str(directory), "--select", select],
        directory=metadata,
        cwd=ROOT,
        env=environment,
        timeout=480,
        max_rss_bytes=512 * 2**20,
        min_available_bytes=8 * 2**30,
    )
    source_root = directory / "source"
    environment["PYTHONPATH"] = os.pathsep.join(
        (
            str(source_root / "src"),
            str(source_root),
            "/mnt/workspaces/Cells/pillow-overlay-12.3.0-20261030-01",
        )
    )
    process = directory / "software-process"
    process.mkdir()
    return resources.run_bounded(
        [sys.executable, "-B", "-m", MODULE, "--child", str(directory)],
        directory=process,
        cwd=source_root,
        env=environment,
        timeout=480,
        max_rss_bytes=2**30,
        min_available_bytes=8 * 2**30,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", type=Path)
    modes.add_argument("--software", type=Path)
    modes.add_argument("--child", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--select", default="")
    args = parser.parse_args()
    if args.prepare:
        prepare(args.prepare, args.select)
    elif args.software:
        software(args.software, args.select)
    else:
        child(args.child)


if __name__ == "__main__":
    main()
