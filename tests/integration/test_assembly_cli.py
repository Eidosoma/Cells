"""Public assembly command, saved continuation and durable launch/failure paths."""

import json
import os
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from cells.assembly.cli import execute, main
from cells.assembly.io import digest, runtime, source_identity
from cells.assembly.spec import AssemblyError, parse_spec


def command(*args):
    return subprocess.run(
        [sys.executable, "-B", "-m", "cells", "assembly", *map(str, args)],
        capture_output=True,
        text=True,
        timeout=45,
    )


def definition(tmp_path, **changes):
    path = tmp_path / "definition.json"
    spec = parse_spec(
        {
            "worlds": 2,
            "end_time_s": 1.0,
            "event_chunk_size": 8,
            "recording": "events",
            "max_events_per_world": 128,
        }
        | changes
    )
    path.write_text(json.dumps(spec.to_dict()))
    return path, spec


def test_public_cpu_command_and_saved_restart(tmp_path):
    config, _ = definition(tmp_path)
    checked = command("validate", config)
    assert checked.returncode == 0, checked.stderr
    assert json.loads(checked.stdout)["status"] == "valid"
    output = tmp_path / "original"
    first = command("run", config, "--output", output, "--checkpoint-at", 0.013)
    assert first.returncode == 0, first.stderr
    result = json.loads(first.stdout)
    assert result["status"] == "completed" and result["backend"] == "cpu"
    assert (output / "completion.json").exists()
    restored = tmp_path / "restored"
    second = command("resume", output / "checkpoint-000", "--output", restored)
    assert second.returncode == 0, second.stderr
    with (
        np.load(output / "checkpoint/state.npz") as a,
        np.load(restored / "checkpoint/state.npz") as b,
    ):
        assert set(a.files) == set(b.files)
        for field in a.files:
            np.testing.assert_array_equal(a[field], b[field], err_msg=field)
    parent = json.loads((restored / "registration.json").read_text())["parent"]
    assert parent["sha256"] == digest(output / "checkpoint-000/manifest.json")
    assert command("run", config, "--output", output).returncode == 2


def test_bad_definition_and_output_refused(tmp_path):
    config, _ = definition(tmp_path)
    assert command("run", config, "--output", "/tmp/cells-assembly-not-authorized").returncode == 2
    bad = json.loads(config.read_text()) | {"initial_nodes": [1, 10]}
    config.write_text(json.dumps(bad))
    output = tmp_path / "invalid"
    assert command("run", config, "--output", output).returncode == 2
    assert not output.exists()


def test_detached_launch_freezes_source_and_logs(tmp_path, monkeypatch, capsys):
    config, spec = definition(tmp_path)
    calls = []

    def popen(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(pid=123456789)

    monkeypatch.setattr("cells.assembly.cli.subprocess.Popen", popen)
    output = tmp_path / "detached"
    assert main(["run", str(config), "--output", str(output), "--backend", "gpu", "--detach"]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["status"] == "launched"
    argv, options = calls[0]
    assert options["start_new_session"] and options["close_fds"]
    assert options["stdin"] == subprocess.DEVNULL
    assert options["env"]["PYTHONPATH"] == str(output / "source")
    assert argv[-2:] == ["_worker", str(output)]
    assert (output / "source/cells/assembly/kernel.py").exists()
    assert (output / "stdout.log").exists() and (output / "stderr.log").exists()
    registration = json.loads((output / "registration.json").read_text())
    assert registration["definition"] == spec.to_dict()
    assert registration["backend"] == "gpu"
    assert registration["sources_sha256"] == source_identity()


def test_preflight_worker_failure_is_durable(tmp_path):
    output = tmp_path / "failure"
    output.mkdir()
    (output / "registration.json").write_text(
        json.dumps(
            {
                "sources_sha256": {},
                "runtime": runtime(),
            }
        )
    )
    with pytest.raises(AssemblyError, match="source/runtime"):
        execute(output)
    failure = json.loads((output / "failure.json").read_text())
    assert failure["status"] == "failed" and failure["exception"] == "AssemblyError"


def test_event_limit_saves_partial_state(tmp_path):
    config, _ = definition(tmp_path, initial_nodes=[10, 0, 1, 2, 3], max_events_per_world=1)
    output = tmp_path / "limited"
    failed = command("run", config, "--output", output)
    assert failed.returncode == 2
    assert (output / "failure.json").exists()
    assert (output / "failure-state.npz").exists()
    assert not (output / "completion.json").exists()
    with np.load(output / "failure-state.npz") as state:
        assert np.all(state["event_count"] <= 1)


def test_requested_gpu_never_silently_uses_cpu(tmp_path):
    config, _ = definition(tmp_path)
    output = tmp_path / "no-gpu"
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "cells",
            "assembly",
            "run",
            str(config),
            "--backend",
            "gpu",
            "--output",
            str(output),
        ],
        env=os.environ | {"JAX_PLATFORMS": "cpu"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 2 and "no CPU fallback" in result.stderr
    assert (output / "failure.json").exists()
    assert not (output / "completion.json").exists()
