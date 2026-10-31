"""Bounded snapshot/runner software controls; scientific imports are forbidden."""

import argparse
import importlib.abc
import json
import os
import resource
import sys
from pathlib import Path

from validation.betse import betse_mesh_lifecycle_preparation_guard as guard
from validation.betse.init_phase_qualification import prepare

TESTS = ("tests/unit/test_source_snapshot.py", prepare.OWNED + "/test_software.py")


def child(output):
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    attempted = []

    class NoScience(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in {"cells", "betse", "numpy", "scipy", "jax", "jaxlib"}:
                attempted.append(fullname)
                raise ImportError(
                    "Scientific import forbidden in snapshot/runner software controls"
                )
            return None

    sys.meta_path.insert(0, NoScience())
    import pytest

    arguments = [
        "-q",
        "--noconftest",
        "-c",
        "/dev/null",
        "-p",
        "no:cacheprovider",
        *(str(prepare.ROOT / name) for name in TESTS),
        "--junitxml=" + str(output / "tests.xml"),
        "--basetemp=" + str(output / "tmp"),
    ]
    code = pytest.main(arguments)
    prepare.write(output / "pytest-exit.json", dict(returncode=int(code), argv=arguments))
    prepare.write(output / "scientific-import-refusal.json", dict(attempted=attempted))
    if attempted:
        raise RuntimeError("A software control attempted to import scientific code")
    return int(code)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--_child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(prepare.BASE) or os.sched_getaffinity(0) != {6}:
        parser.error("Require CPU6 and a fresh /mnt/workspaces/Cells output")
    if args._child:
        return child(output)
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
    output.mkdir(parents=True, exist_ok=False)
    (output / "process").mkdir()
    files = {
        "validation/source_snapshot.py",
        *TESTS,
        *prepare.RUNNER_FILES.values(),
        *prepare.TOOL_FILES.values(),
        *(str(p.relative_to(prepare.ROOT)) for p in (prepare.ROOT / prepare.OWNED).glob("*.py")),
    }
    frozen = output / "tested-source"
    snapshot = prepare.source_snapshot.freeze(prepare.ROOT, frozen, {name: name for name in files})
    sources = {name: row["sha256"] for name, row in snapshot["files"].items()}
    prepare.write(
        output / "inputs.json",
        dict(
            checkout=str(prepare.ROOT),
            source_sha256=sources,
            git_revision=snapshot["git_revision"],
            selected_tests=TESTS,
            checkout_snapshot_sha256=prepare.sha(frozen / "SNAPSHOT.json"),
            execution_source_root=str(frozen),
            numerical_execution_authorized=False,
        ),
    )
    environment = dict(os.environ)
    environment.update(
        PYTHONPATH=os.pathsep.join((str(frozen), str(frozen / "src"))),
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        VECLIB_MAXIMUM_THREADS="1",
        CUDA_VISIBLE_DEVICES="",
    )
    result = guard.run_bounded(
        [
            sys.executable,
            "-B",
            "-m",
            "validation.betse.init_phase_qualification.software",
            "--output",
            str(output),
            "--_child",
        ],
        directory=output / "process",
        cwd=frozen,
        env=environment,
        timeout=480,
        max_rss_bytes=2**30,
        min_available_bytes=8 * 2**30,
    )
    changed = [
        name for name, digest in sources.items() if prepare.sha(prepare.ROOT / name) != digest
    ]
    if changed:
        raise RuntimeError("Tested source drift: " + repr(changed))
    prepare.source_snapshot.verify(frozen)
    result.update(scientific_execution=0, scientific_imports=0, source_sha256=sources)
    prepare.write(output / "result.json", result)
    print(json.dumps(dict(output=str(output), status=result["status"])))
    return int(result["returncode"])


if __name__ == "__main__":
    raise SystemExit(main())
