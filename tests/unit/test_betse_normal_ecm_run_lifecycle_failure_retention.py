"""Isolated synthetic controls; no native clock, component or science entry runs."""

import ast
import builtins
import hashlib
import importlib.abc
import importlib.util
import json
import os
import struct
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
NATIVE = "validation/betse/betse_normal_ecm_run_lifecycle_native.py"
WRITER = "validation/betse/betse_normal_current_native.py"
READER = "tests/unit/test_betse_fast_solver.py"
BLOCKED = {"cells", "betse", "jax", "jaxlib"}
SCENARIOS = (
    "evaluate-success",
    "evaluate-label",
    "evaluate-eligibility",
    "cli-success",
    "clock-success",
    "cli-label",
    "cli-eligibility",
    "cli-inventory",
    "clock-inventory",
    "cli-archive",
    "cli-before-return",
    "cli-collision",
)


def _function(path, name, namespace):
    """Use existing archive writer/reader bodies without importing their solvers."""
    node = next(
        node
        for node in ast.parse(path.read_bytes()).body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
    return namespace[name]


def _software_control(directory, scenario):
    import numpy as np

    directory.mkdir(exist_ok=False)
    events, denied = [], []
    original_import = builtins.__import__

    def guard(name, *args, **kwargs):
        if name.split(".")[0] in BLOCKED:
            denied.append(name)
            raise ImportError("Synthetic control blocks all scientific imports: " + name)
        return original_import(name, *args, **kwargs)

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in BLOCKED:
                denied.append(fullname)
                raise ImportError("Synthetic control blocks scientific importlib: " + fullname)

    builtins.__import__ = guard
    sys.meta_path.insert(0, Guard())
    try:
        for name in sorted(BLOCKED):
            with pytest.raises(ImportError, match="Synthetic control"):
                importlib.import_module(name)
        assert not [name for name in sys.modules if name.split(".")[0] in BLOCKED]
        namespace = dict(np=np, Path=Path, os=os, json=json, hashlib=hashlib, struct=struct)
        write = _function(ROOT / WRITER, "write_archive", namespace)
        read = _function(ROOT / READER, "archive_read", namespace)
        output = directory / "native"
        failed = directory / "native-failed-reached"
        clock = dict(
            phase="SIM",
            step_count=3,
            dt_s=0.2,
            sample_stride=1.0,
            source_labels_s=np.array([0.0, 0.2, 0.4]),
            sampled=[True, False, True],
        )
        captured = dict(
            RNG_unchanged=True,
            provenance="synthetic software payload; no native or physical admission",
            payload=np.array([123.0, -0.0]),
            sample_states=[
                dict(source_time_s=value, native_calendar_eligible=eligible)
                for value, eligible in zip((0.0, 0.2, 0.4), (True, False, True), strict=True)
            ],
        )
        if scenario.endswith("label") or scenario == "cli-collision":
            captured["sample_states"][0]["source_time_s"] = 9.0
        if scenario.endswith("eligibility"):
            captured["sample_states"][0]["native_calendar_eligible"] = False

        def component_evaluate(declared):
            events.append("synthetic-component")
            if scenario == "cli-before-return":
                raise RuntimeError("Synthetic before-return refusal")
            return captured

        def archive(path, value):
            events.append("archive:" + Path(path).name)
            if scenario == "cli-archive" and Path(path) == output:
                output.mkdir()
                (output / "partial.out").write_bytes(b"preserved failed writer output")
                raise OSError("Synthetic completed-output writer refusal")
            return write(path, value)

        component = ModuleType("validation.betse.betse_normal_ecm_event_mechanics_native")
        component.evaluate = component_evaluate
        component.archives = SimpleNamespace(write_archive=archive)
        sys.modules[component.__name__] = component
        package = importlib.import_module("validation.betse")
        package.betse_normal_ecm_event_mechanics_native = component
        runtime = ModuleType("validation.betse.betse_normal_channel_join_runtime")

        def inventory():
            events.append("synthetic-runtime-inventory")
            if scenario.endswith("inventory"):
                raise RuntimeError("Synthetic post-capture inventory refusal")
            return dict(synthetic_software_inventory=True, scientific_credit=0)

        runtime.inventory = inventory
        sys.modules[runtime.__name__] = runtime
        spec = importlib.util.spec_from_file_location("lifecycle_retention_control", ROOT / NATIVE)
        native = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(native)

        def forbidden(*args, **kwargs):
            events.append("FORBIDDEN-scientific-clock-entry")
            raise AssertionError("Actual native/scientific clock entry is blocked")

        for name in ("_source_counts", "_source_phase_time", "_source_clock"):
            setattr(native, name, forbidden)

        def clock_profile(raw):
            events.append("synthetic-clock-metadata")
            return clock

        native.clock_profile = clock_profile
        inputs = dict(
            time_profile=dict(synthetic_only=True),
            composition_inputs=dict(event_inputs=dict(calendar=dict(dt_s=0.2, sample_stride=1.0))),
        )
        if scenario.startswith("evaluate-"):
            reached = []
            if scenario == "evaluate-success":
                result = native.evaluate(inputs, retain_reached=reached.append)
                assert result is reached[0]
            else:
                with pytest.raises(AssertionError):
                    native.evaluate(inputs, retain_reached=reached.append)
            assert len(reached) == 1 and reached[0]["composition"] is captured
            write(directory / "observed-callback", reached[0])
        else:
            # Pin checks exercise two synthetic metadata roots, never BETSE files.
            pins = {}
            for name in ("source", "installed"):
                path = directory / name
                path.mkdir()
                (path / "metadata.txt").write_bytes(b"synthetic source pin fixture\n")
                pins[name] = str(path)
            locator = directory / "synthetic-protocol"
            locator.mkdir()
            (locator / "betse_normal_ecm_run_lifecycle_protocol.json").write_text(
                json.dumps(
                    dict(
                        native_source=dict(
                            checkout=pins["source"],
                            installed_package=pins["installed"] + "/betse",
                            source_sha256={
                                "metadata.txt": hashlib.sha256(
                                    b"synthetic source pin fixture\n"
                                ).hexdigest()
                            },
                        )
                    )
                )
            )
            # Only the protocol locator is synthetic; spec.origin and compiled
            # function filenames remain the exact snapshotted producer path.
            native.__file__ = str(locator / "native.py")
            input_path = directory / "inputs.json"
            input_path.write_text(json.dumps(inputs))
            sys.argv = ["native", "--inputs", str(input_path), "--output", str(output)]
            if scenario.startswith("clock-"):
                sys.argv.append("--clock-only")
            if scenario == "cli-collision":
                write(failed, dict(existing_failed_evidence=np.array([77.0])))
                before = {
                    path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in failed.iterdir()
                }
            expected = {
                "cli-collision": FileExistsError,
                "cli-archive": OSError,
                "cli-inventory": RuntimeError,
                "clock-inventory": RuntimeError,
                "cli-before-return": RuntimeError,
                "cli-label": AssertionError,
                "cli-eligibility": AssertionError,
            }.get(scenario)
            if expected is None:
                native.main()
                result = read(output)
                assert result["RNG_unchanged"] and result["production_imports_denied"]
                assert result["loaded_production_modules"] == []
                assert result["runtime"]["synthetic_software_inventory"]
                assert not failed.exists()
            else:
                with pytest.raises(expected) as caught:
                    native.main()
                if scenario == "cli-before-return":
                    assert not failed.exists() and not output.exists()
                elif scenario == "cli-collision":
                    assert isinstance(caught.value.__context__, AssertionError)
                    assert before == {
                        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                        for path in failed.iterdir()
                    }
                else:
                    result = read(failed)
                    assert result["failure"]["type"] == expected.__name__
                    assert result["failure"]["traceback"]
                    assert result["failed_after_capture_return"] is True
                    for name in (
                        "native_full_phase_completed",
                        "physical_initialization_claim",
                        "qualification_credit",
                    ):
                        assert result[name] is False
                    retained = result["reached_capture"]
                    assert (
                        retained["clock"]["source_labels_s"].tobytes()
                        == clock["source_labels_s"].tobytes()
                    )
                    if scenario.startswith("clock-"):
                        assert retained["clock_only"] and "synthetic-component" not in events
                    else:
                        assert (
                            retained["composition"]["payload"].tobytes()
                            == captured["payload"].tobytes()
                        )
                        assert retained["composition"]["sample_states"] == captured["sample_states"]
                    if scenario == "cli-archive":
                        assert (
                            output / "partial.out"
                        ).read_bytes() == b"preserved failed writer output"
                    else:
                        assert not output.exists()
        assert "FORBIDDEN-scientific-clock-entry" not in events
        assert not [name for name in sys.modules if name.split(".")[0] in BLOCKED]
    finally:
        builtins.__import__ = original_import
        (directory / "control.json").write_text(
            json.dumps(
                dict(
                    scenario=scenario,
                    events=events,
                    intentionally_denied_imports=denied,
                    loaded_production_modules=[
                        name for name in sys.modules if name.split(".")[0] in BLOCKED
                    ],
                    source_sha256={
                        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                        for name in (NATIVE, WRITER, READER, str(Path(__file__).relative_to(ROOT)))
                    },
                    process=dict(
                        pid=os.getpid(),
                        parent_pid=os.getppid(),
                        executable=str(Path(sys.executable).resolve()),
                    ),
                    CPU_affinity=sorted(os.sched_getaffinity(0)),
                    scientific_credit=0,
                    actual_scientific_entry_attempts=0,
                    forbidden_clock_entry_attempts=events.count("FORBIDDEN-scientific-clock-entry"),
                    synthetic_protocol_and_inventory=True,
                ),
                indent=2,
            )
            + "\n"
        )


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_reached_output_failure_retention_synthetic(tmp_path, scenario):
    directory = tmp_path / scenario
    process = subprocess.run(
        [sys.executable, "-B", str(Path(__file__).resolve()), str(directory), scenario],
        cwd=ROOT,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
        check=False,
    )
    (tmp_path / "stdout.log").write_text(process.stdout)
    (tmp_path / "stderr.log").write_text(process.stderr)
    assert process.returncode == 0, process.stderr
    result = json.loads((directory / "control.json").read_text())
    assert result["loaded_production_modules"] == []
    assert result["scientific_credit"] == 0


if __name__ == "__main__":
    _software_control(Path(sys.argv[1]), sys.argv[2])
