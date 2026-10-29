"""Short host-only cut qualification in a separate dispatch-patched source copy."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = "agent-work/cells-worker-01/workfiles/"
OWNED = (
    "src/cells/core/surface_calcium_energy_regulated_v2_excision_spec.py",
    "src/cells/core/calcium_energy_regulated_v2_tissue_excision.py",
    "src/cells/models/surface_calcium_energy_regulated_v2_excision.py",
    "tests/unit/test_surface_calcium_energy_regulated_v2_excision.py",
    WORK + "check_regulated_v2_excision.py",
)
PATCH = WORK + "regulated_v2_excision_dispatch.patch"
META = WORK + "regulated_v2_excision_dispatch.json"
BASE = Path("/mnt/workspaces/Cells/regulated-v2-public-execution-20261029-01")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def hashes(root):
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob("*")) if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--select")
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.parent == Path("/mnt/workspaces/Cells")
    assert output.name.startswith("regulated-v2-excision-host-")
    output.mkdir(exist_ok=False)
    for name in ("tmp", "cache", "evidence", "initial_owned"):
        (output / name).mkdir()
    assert sorted(os.sched_getaffinity(0)) == [7]
    overrides = dict.fromkeys(
        ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"), "1"
    )
    overrides.update(
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        JAX_PLATFORMS="cpu",
        JAX_ENABLE_X64="true",
        JAX_DISABLE_JIT="true",
        CUDA_VISIBLE_DEVICES="",
        JAX_ENABLE_COMPILATION_CACHE="false",
        XLA_FLAGS="--xla_cpu_multi_thread_eigen=false",
        MALLOC_ARENA_MAX="2",
        CELLS_COMPONENT_EVIDENCE=str(output / "evidence"),
        XDG_CACHE_HOME=str(output / "cache"),
        JAX_COMPILATION_CACHE_DIR=str(output / "cache/jax"),
        TMPDIR=str(output / "tmp"),
    )
    env = os.environ.copy()
    env.update(overrides)
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + str(ROOT)
    sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
    from validation.assembly.component_process import run_bounded

    checks = []

    def bounded(name, command, *, cwd=ROOT, timeout=60):
        directory = output / (name + "-guard")
        directory.mkdir()
        began = time.monotonic()
        try:
            run_bounded(
                command,
                directory=directory,
                cwd=cwd,
                env=env,
                timeout=timeout,
                max_rss_bytes=2**30,
                min_available_bytes=8 * 2**30,
            )
        except Exception:
            checks.append(dict(name=name, status="failed", wall_seconds=time.monotonic() - began))
            raise
        checks.append(dict(name=name, status="passed", wall_seconds=time.monotonic() - began))

    failure = None
    frozen = {}
    try:
        for relative in OWNED:
            target = output / "initial_owned" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        ruff = str(Path(sys.executable).parent / "ruff")
        bounded("imports", [ruff, "check", "--no-cache", "--select", "I", "--fix", *OWNED])
        bounded("format", [ruff, "format", "--no-cache", *OWNED])
        bounded("lint", [ruff, "check", "--no-cache", *OWNED])
        metadata = read(ROOT / META)
        assert metadata["status"] == "prepared-not-applied"
        assert sha(ROOT / PATCH) == metadata["patch_sha256"]
        paths = set(read(BASE / "frozen-sources.json")["after_sha256"])
        paths.update(
            str(p.relative_to(ROOT))
            for p in (ROOT / "src").rglob("*.py")
            if "__pycache__" not in p.parts
        )
        paths.update((*OWNED, PATCH, META))
        paths.update(
            ("configs/resolved_hcn_extra_ionic.json", "configs/resolved_hcn_extra_calcium.json")
        )
        content = {p: (ROOT / p).read_bytes() for p in sorted(paths)}
        for relative, row in metadata["shared_files"].items():
            assert hashlib.sha256(content[relative]).hexdigest() == row["before_sha256"]
        snapshot = output / "snapshot"
        for relative, data in content.items():
            target = snapshot / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        assert {p: sha(ROOT / p) for p in paths} == hashes(snapshot)
        subprocess.run(
            ["git", "apply", str(ROOT / PATCH)],
            cwd=snapshot,
            check=True,
            capture_output=True,
            text=True,
        )
        frozen = hashes(snapshot)
        for relative, row in metadata["shared_files"].items():
            assert frozen[relative] == row["after_sha256"]
        changed = {p for p in paths if frozen[p] != hashlib.sha256(content[p]).hexdigest()}
        assert changed == set(metadata["shared_files"])
        write(
            output / "frozen-sources.json",
            dict(
                status="frozen",
                after_sha256=frozen,
                shared_files_written=False,
                dispatch_patch_sha256=metadata["patch_sha256"],
                frozen_copy_only_dispatch_changes=metadata["shared_files"],
                inherited_numerics_unchanged=True,
            ),
        )
        env["PYTHONPATH"] = str(snapshot / "src") + os.pathsep + str(snapshot)
        for path in snapshot.rglob("*"):
            if path.is_file():
                path.chmod(0o444)
        for path in sorted(
            (p for p in snapshot.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True
        ):
            path.chmod(0o555)
        snapshot.chmod(0o555)
        command = [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "-q",
            "-x",
            "-p",
            "no:cacheprovider",
            "--basetemp=" + str(output / "tmp/pytest"),
            "--junitxml=" + str(output / "host-tests.xml"),
            str(snapshot / OWNED[3]),
        ]
        if args.select:
            command.extend(("-k", args.select))
        write(
            output / "inputs.json",
            dict(
                model_id="resolved_calcium_energy_regulated_excision@1",
                parent="resolved_calcium_energy_regulated@2",
                state_fields=38,
                command=command,
                affinity=[7],
                environment={k: env[k] for k in (*overrides, "PYTHONPATH")},
                max_host_rss_bytes=2**30,
                min_available_memory_bytes=8 * 2**30,
                max_host_seconds=480,
                compiled_execution=False,
                gpu=False,
                scientific_scope=(
                    "Host owner/rule/rebase/archive contracts; independent reference Chief-owned"
                ),
                automatic_followup=False,
            ),
        )
        bounded("host", command, cwd=snapshot, timeout=480)
        assert hashes(snapshot) == frozen
    except Exception as error:
        failure = dict(
            type=type(error).__name__, message=str(error), traceback=traceback.format_exc()
        )
    counts = dict.fromkeys(("tests", "errors", "failures", "skipped"), 0)
    if (output / "host-tests.xml").exists():
        suites = ET.parse(output / "host-tests.xml").getroot().iter("testsuite")
        for suite in suites:
            for key in counts:
                counts[key] += int(suite.get(key, "0"))
    passed = (
        failure is None
        and counts["tests"] > 0
        and not any(counts[k] for k in ("errors", "failures", "skipped"))
    )
    result = dict(
        status="passed" if passed else "failed",
        tests=counts,
        checks=checks,
        error=failure,
        source_manifest_sha256=sha(output / "frozen-sources.json") if frozen else None,
        source_sha256={p: sha(ROOT / p) for p in OWNED},
        output_sha256=hashes(output),
        shared_source_edits=False,
        compiled_execution=False,
    )
    write(output / "result.json", result)
    if not passed:
        write(output / "failure.json", result)
    print(
        json.dumps(dict(output=str(output), status=result["status"], tests=counts, error=failure))
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
