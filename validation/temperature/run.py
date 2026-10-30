"""Freeze and run the assigned bounded CPU4 native-temperature investigation."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

NOTE = "agent-work/cells-specialist/ACTIVE_TEMPERATURE_POLICY.md"
OWNED = sorted(
    str(path.relative_to(ROOT))
    for path in (ROOT / "validation/temperature").glob("*")
    if path.is_file()
)


def main():
    from validation.assembly.component_process import run_bounded
    from validation.tissue import open_calcium_bath_trajectory_common as artifacts

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--native", default="/mnt/workspaces/Cells/betse-v1.5.0", type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    os.sched_setaffinity(0, {4})
    out.mkdir(exist_ok=False)
    phase, resources = {"stage": "source-capture"}, {}
    try:
        for name in ("source", "native", "tmp", "cache", "evidence"):
            (out / name).mkdir()
        snapshot = out / "source"
        selected = []
        for top in ("src", "tests", "validation", "configs"):
            selected.extend(
                path
                for path in sorted((ROOT / top).rglob("*"))
                if path.is_file() and path.suffix in (".py", ".json")
            )
        selected.extend(
            ROOT / name
            for name in (
                NOTE,
                "pyproject.toml",
                "requirements-lock.txt",
                "requirements-reference.txt",
                "AGENTS.md",
            )
        )
        hashes = {}
        for path in selected:
            name = str(path.relative_to(ROOT))
            payload = path.read_bytes()
            destination = snapshot / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
            hashes[name] = hashlib.sha256(payload).hexdigest()
        manifest = json.loads(
            (snapshot / "validation/temperature/source_manifest.json").read_text()
        )
        native_hashes = manifest["source_files"] | manifest["temperature_scan_files"]
        for name, expected in native_hashes.items():
            payload = (args.native / name).read_bytes()
            assert hashlib.sha256(payload).hexdigest() == expected, name
            destination = out / "native" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
        (out / "driver.py").write_bytes(Path(__file__).read_bytes())
        protocol = json.loads((snapshot / "validation/temperature/protocol.json").read_text())
        environment = os.environ.copy()
        for key in tuple(environment):
            if key.startswith(("JAX_", "XLA_", "PYTEST_", "CELLS_")) or key in (
                "PYTHONPATH",
                "PYTHONHOME",
                "CUDA_VISIBLE_DEVICES",
            ):
                environment.pop(key)
        settings = dict(
            PYTHONDONTWRITEBYTECODE="1",
            PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
            PYTHONPATH=str(snapshot),
            CUDA_VISIBLE_DEVICES="",
            OMP_NUM_THREADS="1",
            OPENBLAS_NUM_THREADS="1",
            MKL_NUM_THREADS="1",
            NUMEXPR_NUM_THREADS="1",
            BLIS_NUM_THREADS="1",
            VECLIB_MAXIMUM_THREADS="1",
            TF_NUM_INTRAOP_THREADS="1",
            TF_NUM_INTEROP_THREADS="1",
            MALLOC_ARENA_MAX="2",
            TMPDIR=str(out / "tmp"),
            XDG_CACHE_HOME=str(out / "cache"),
            CELLS_COMPONENT_EVIDENCE=str(out / "evidence"),
            CELLS_BETSE_SOURCE=str(out / "native"),
        )
        environment.update(settings)
        command = [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "--noconftest",
            "-p",
            "no:cacheprovider",
            "-p",
            "validation.temperature.runtime_capture",
            "-q",
            "-W",
            "error",
            "--maxfail=1",
            "validation/temperature/test_correspondence.py",
            "--basetemp",
            str(out / "tmp/tests"),
            "--junitxml",
            str(out / "tests.xml"),
        ]
        phases = [
            ("checks", command),
            (
                "isolated-reference",
                [sys.executable, "-B", "-m", "validation.temperature.isolated_replay"],
            ),
        ]
        artifacts.write_json(
            out / "inputs.json",
            dict(
                kind=protocol["kind"],
                source_snapshot=str(snapshot),
                source_hashes=hashes,
                owned=OWNED + [NOTE],
                native_sources=native_hashes,
                native_revision=manifest["source_revision"],
                commands=dict(phases),
                cpu_affinity=[4],
                environment=settings,
                resource_limits=protocol["resources"],
                expected_checks=122,
                expected_independent_records=115,
                expected_reference_batches=1170,
                scope=(
                    "Isolated pinned source and independent finite-column correspondence; proposal "
                    "only. No whole native simulation, active guard change, new coupled physics "
                    "or thermal transition."
                ),
                automatic_followup=False,
            ),
        )
        phase = {"stage": "lint"}
        lint = subprocess.run(
            [
                str(Path(sys.executable).with_name("ruff")),
                "check",
                "--no-cache",
                "validation/temperature",
            ],
            cwd=snapshot,
            text=True,
            capture_output=True,
        )
        artifacts.write_json(
            out / "lint.json",
            dict(returncode=lint.returncode, stdout=lint.stdout, stderr=lint.stderr),
        )
        if lint.returncode:
            raise RuntimeError("Frozen source-only probe lint failed")
        for label, command in phases:
            phase = {"stage": label}
            directory = out / label
            directory.mkdir()
            artifacts.write_progress(sys.stdout, dict(starting_phase=label, output=str(out)))
            resources[label] = run_bounded(
                command,
                directory=directory,
                cwd=snapshot,
                env=environment,
                timeout=480,
                max_rss_bytes=2**30,
                min_available_bytes=8 * 2**30,
                process_tree_memory_metric="rss",
            )
            artifacts.write_progress(
                sys.stdout, dict(completed_phase=label, seconds=resources[label]["elapsed_seconds"])
            )
        cases = ET.parse(out / "tests.xml").getroot().findall(".//testcase")
        assert len(cases) == 122, len(cases)
        assert all(
            all(case.find(tag) is None for tag in ("failure", "error", "skipped")) for case in cases
        )
        for name, expected in hashes.items():
            assert artifacts.sha(snapshot / name) == expected, name
        for name in OWNED + [NOTE]:
            assert artifacts.sha(ROOT / name) == hashes[name], name
        for name, expected in native_hashes.items():
            assert artifacts.sha(out / "native" / name) == expected, name
        runtime = json.loads((out / "evidence/runtime.json").read_text())
        replay = json.loads((out / "evidence/independence.json").read_text())
        for actual in (runtime, replay["runtime"]):
            assert actual["affinity"] == [4] and not actual["loaded_production_modules"]
            assert all(value == "1" for value in actual["threads"].values())
            for name, expected in actual["files"].items():
                assert artifacts.sha(name) == expected, name
        artifacts.success(
            out,
            dict(
                kind=protocol["kind"],
                checks=len(cases),
                check_ids=[
                    case.attrib.get("classname", "") + "::" + case.attrib["name"] for case in cases
                ],
                independent_records=replay["case_count"],
                reference_batches=replay["reference_batches"],
                independent_scalar_channel_points=replay["scalar_channel_points"],
                maximum_error_fraction=max(
                    row["maximum_error_fraction"] for row in replay["records"]
                ),
                diagnostic_records=len(replay["diagnostics"]),
                native_revision=manifest["source_revision"],
                native_sources=native_hashes,
                owned_source_sha256={name: hashes[name] for name in OWNED + [NOTE]},
                captured_sources=len(hashes),
                captured_runtime_files=len(runtime["files"]),
                resource_results=resources,
                source_snapshot_verified=True,
                owned_sources_unchanged=True,
                proposed_policy="active_uniform_isothermal_fixed_empirical_kinetics@1",
                proposal_adopted=False,
                whole_native_simulation=False,
                active_guard_relaxation=False,
                thermal_transition=False,
                gpu_run=False,
                automatic_followup=False,
            ),
        )
        print(
            json.dumps(
                dict(
                    status="passed",
                    checks=len(cases),
                    output=str(out),
                    result_sha256=artifacts.sha(out / "result.json"),
                )
            ),
            flush=True,
        )
    except BaseException as error:
        artifacts.failure(
            out,
            error,
            context=phase | dict(completed_phases=list(resources), automatic_retry=False),
        )
        raise


if __name__ == "__main__":
    main()
