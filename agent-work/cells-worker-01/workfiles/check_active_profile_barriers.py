"""Freeze complete qualified inputs and run one bounded development check.

Shared dispatch edits occur only inside the private clone. This runner neither
launches long qualifications nor queries any other job.
"""

import argparse
import difflib
import hashlib
import json
import os
import sys
import traceback
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = Path("/mnt/workspaces/Cells/owned-barrier-development-20261029-05")
HANDOFF = Path("/mnt/workspaces/Cells/owned-barrier-stage-handoff-20261029-01/result.json")
RUNTIME = (
    "src/cells/core/active_profile_barrier_preparation.py",
    "src/cells/core/surface_active_profile_barrier_interventions_spec.py",
    "src/cells/core/surface_active_profile_barrier_binding.py",
    "src/cells/models/surface_active_profile_barrier_interventions.py",
)
NEW_FILES = (
    *RUNTIME,
    "validation/transport/active_profile_barrier_interventions_fixtures.py",
    "validation/transport/active_profile_barrier_interventions_reference.py",
    "tests/unit/test_active_profile_barrier_interventions.py",
    "agent-work/cells-worker-01/workfiles/check_active_profile_barriers.py",
)
OWNERS = (
    (
        "surface_active_profile_barrier_interventions",
        "SurfaceActiveProfileBarrierInterventionModel",
        "resolved_active_profile_barriers@1",
    ),
)

SHARED = (
    "src/cells/core/specs.py",
    "src/cells/core/schedule.py",
    "src/cells/models/registry.py",
    "src/cells/ensemble/ionic.py",
)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def routes(workspace):
    patches, metadata = [], {}
    for relative in SHARED:
        path = workspace / relative
        before = path.read_text()
        after = before
        if relative.endswith("specs.py"):
            statements = ""
            for module, cls, _ in OWNERS:
                statements += (
                    f"        from cells.core.{module}_spec import {cls}\n"
                    f"        from cells.core.{module}_spec import to_dict as {module}_dict\n"
                    f"        if isinstance(m, {cls}):\n"
                    f"            return {module}_dict(self)\n"
                )
            needle = "        m, e, x = self.model, self.experiment, self.execution\n"
            assert after.count(needle) == 1
            after = after.replace(needle, needle + statements)
            statements = ""
            for module, _, mid in OWNERS:
                statements += (
                    '    if isinstance(data["model"], dict) '
                    f'and data["model"].get("id") == "{mid}":\n'
                    f"        from cells.core.{module}_spec import parse\n"
                    "        return parse(data)\n"
                )
            needle = '        raise ConfigError("Only schema_version 1 is supported")\n'
            assert after.count(needle) == 1
            after = after.replace(needle, needle + statements)
        elif relative.endswith("registry.py"):
            statements = ""
            for module, cls, _ in OWNERS:
                statements += (
                    f"    from cells.core.{module}_spec import {cls}\n"
                    f"    if isinstance(spec, {cls}):\n"
                    f"        from cells.models import {module}\n"
                    f"        return {module}\n"
                )
            needle = "def get_model(spec):\n"
            assert after.count(needle) == 1
            after = after.replace(needle, needle + statements)
        elif relative.endswith("schedule.py"):
            statements = ""
            for module, cls, _ in OWNERS:
                statements += (
                    f"    from cells.core.{module}_spec import {cls}\n"
                    f"    from cells.core.{module}_spec import owner_spec as {module}_owner\n"
                    f"    if isinstance(spec.model, {cls}):\n"
                    f"        return control_values({module}_owner(spec), times)\n"
                )
            needle = "def control_values(spec, times):\n"
            assert after.count(needle) == 1
            after = after.replace(needle, needle + statements)
        else:
            needle = '        "resolved_calcium@1",\n'
            assert after.count(needle) == 1
            after = after.replace(needle, "".join(f'        "{v[2]}",\n' for v in OWNERS) + needle)
        path.write_text(after)
        metadata[relative] = dict(
            base_sha256=hashlib.sha256(before.encode()).hexdigest(), patched_sha256=sha(path)
        )
        patches.extend(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile="a/" + relative,
                tofile="b/" + relative,
            )
        )
    return "".join(patches), metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--selection", default="complete_preparation")
    parser.add_argument("--timeout", type=int, default=420)
    args = parser.parse_args()
    if not 1 <= args.timeout <= 480:
        raise ValueError("Only short bounded development checks are authorized")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    workspace = output / "workspace"
    workspace.mkdir()
    os.sched_setaffinity(0, {6})
    frozen = json.loads((BASE / "source-manifest.json").read_text())["source_sha256"]
    for relative, expected in frozen.items():
        original, target = BASE / "workspace" / relative, workspace / relative
        if sha(original) != expected:
            raise ValueError("Qualified frozen inventory changed: " + relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(original.read_bytes())
    sources = {}
    for relative in NEW_FILES:
        target = workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
        sources[relative] = sha(target)
    patch, shared = routes(workspace)
    (output / "private-dispatch.patch").write_text(patch)
    inventory = {
        p.relative_to(workspace).as_posix(): sha(p)
        for p in sorted(workspace.rglob("*"))
        if p.is_file()
    }
    write(
        output / "source-manifest.json",
        dict(
            static_source=str(BASE / "workspace"),
            qualified_source_manifest_sha256=sha(BASE / "source-manifest.json"),
            static_result_sha256=sha(BASE / "result.json"),
            qualified_stage_handoff_sha256=sha(HANDOFF),
            owned_source_sha256=sources,
            shared_routes=shared,
            source_sha256=inventory,
            live_shared_files_written=False,
        ),
    )
    environment = os.environ | dict(
        PYTHONPATH=str(workspace / "src") + ":" + str(workspace),
        PYTHONDONTWRITEBYTECODE="1",
        JAX_PLATFORMS="cpu",
        JAX_ENABLE_X64="true",
        JAX_DISABLE_JIT="true",
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        MALLOC_ARENA_MAX="2",
        CELLS_CHECK_TIMEOUT_SECONDS=str(args.timeout),
        CELLS_COMPONENT_BACKEND="cpu",
        CELLS_COMPONENT_EVIDENCE=str(output / "evidence"),
    )
    command = [
        sys.executable,
        "-B",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "--basetemp=" + str(output / "tmp"),
        "--junitxml=" + str(output / "tests.xml"),
        "tests/unit/test_active_profile_barrier_interventions.py",
        "-k",
        args.selection,
        "--maxfail=1",
    ]
    write(
        output / "inputs.json",
        dict(
            utc=datetime.now(UTC).isoformat(),
            command=command,
            cwd=str(workspace),
            affinity=sorted(os.sched_getaffinity(0)),
            timeout_seconds=args.timeout,
            max_child_tree_rss_bytes=2**30,
            min_host_reserve_bytes=8 * 2**30,
            owned_source_sha256=sources,
            source_manifest_sha256=sha(output / "source-manifest.json"),
            environment={
                k: environment[k]
                for k in environment
                if k.startswith(
                    ("JAX_", "OMP_", "OPENBLAS_", "MKL_", "NUMEXPR_", "CELLS_", "PYTHON")
                )
            },
            scope="new bounded component development only; no finalized test reruns",
            automatic_followup=False,
        ),
    )
    print(json.dumps(dict(status="running", output=str(output), command=command)), flush=True)
    sys.path[:0] = [str(workspace / "src"), str(workspace)]
    from validation.assembly.component_process import run_bounded

    directory = output / "guard"
    directory.mkdir()
    error = None
    try:
        run_bounded(
            command,
            directory=directory,
            cwd=workspace,
            env=environment,
            timeout=args.timeout,
            max_rss_bytes=2**30,
            min_available_bytes=8 * 2**30,
        )
    except Exception as exception:
        error = dict(
            type=type(exception).__name__, message=str(exception), traceback=traceback.format_exc()
        )
        write(output / "failure.json", error)
    changed = [name for name, expected in inventory.items() if sha(workspace / name) != expected]
    counts = dict(tests=0, errors=0, failures=0, skipped=0)
    if (output / "tests.xml").exists():
        tree = ET.parse(output / "tests.xml").getroot()
        for suite in tree.iter("testsuite"):
            for key in counts:
                counts[key] += int(suite.get(key, "0"))
    result = dict(
        status="passed" if error is None and not changed else "failed",
        utc=datetime.now(UTC).isoformat(),
        counts=counts,
        error=error,
        changed_frozen_inputs=changed,
        inputs_sha256=sha(output / "inputs.json"),
        source_manifest_sha256=sha(output / "source-manifest.json"),
        resource_receipt=str(directory / ("failure.json" if error else "result.json")),
        finalized_previous_checks_rerun=False,
        automatic_followup=False,
    )
    write(output / "result.json", result)
    print(json.dumps(result), flush=True)
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
