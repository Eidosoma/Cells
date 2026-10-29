"""Actual public ECM run/restart; tiny histories qualify execution only."""

import json
import subprocess
import sys

import numpy as np

from cells.core.specs import parse_spec
from cells.io import load_snapshot
from cells.models import environment_barrier_interventions as model
from tests.environment_barrier_fixtures import public_definition
from tests.unit.test_environment_barrier_interventions import evidence


def test_public_fresh_restart_preserves_all_barrier_history_and_observations(tmp_path):
    spec = parse_spec(public_definition())
    source = tmp_path / "definition.json"
    source.write_text(json.dumps(spec.to_dict()))

    def invoke(name, arguments):
        child = subprocess.run(
            [sys.executable, "-B", "-m", "cells", *map(str, arguments)],
            capture_output=True,
            text=True,
            timeout=240,
        )
        (tmp_path / (name + ".stdout.log")).write_text(child.stdout)
        (tmp_path / (name + ".stderr.log")).write_text(child.stderr)
        assert child.returncode == 0, child.stderr

    original = tmp_path / "original"
    invoke("original", ("run", source, "--output", original, "--checkpoint-at", 1e-9))
    manifest = json.loads((original / "manifest.json").read_text())
    midpoint = original / manifest["snapshots"][0]
    continued = tmp_path / "continued"
    invoke("continued", ("resume", midpoint, "--output", continued))
    first = load_snapshot(original / "checkpoint_final")
    second = load_snapshot(continued / "checkpoint_final")
    assert first.spec == second.spec == spec
    assert type(second.checkpoint.state) is model.STATE_TYPE
    assert len(second.checkpoint.state) == 13
    assert first.checkpoint.time == second.checkpoint.time == 2e-9
    for a, b in zip(
        first.checkpoint.state + first.checkpoint.layout,
        second.checkpoint.state + second.checkpoint.layout,
        strict=True,
    ):
        np.testing.assert_array_equal(a, b)
    with (
        np.load(original / "trajectory.npz", allow_pickle=False) as a,
        np.load(continued / "trajectory.npz", allow_pickle=False) as b,
    ):
        np.testing.assert_array_equal(b["accepted_times"], a["accepted_times"][1:])
        assert len(b["accepted_times"]) == 2
        for name in model.STATE_TYPE._fields:
            np.testing.assert_array_equal(b[name], a[name][1:])
        selected = a["observation_times"] >= 1e-9
        observations = [
            name for name in a.files if name.startswith("observed_") or name == "observation_times"
        ]
        for name in observations:
            np.testing.assert_array_equal(b[name], a[name][selected])
        arrays = {"original__" + name: a[name] for name in a.files}
        arrays.update({"continued__" + name: b[name] for name in b.files})
    summary = json.loads((continued / "summary.json").read_text())
    assert summary["executed_steps"] == 1
    evidence(
        "public-fresh-restart",
        dict(
            definition=spec.to_dict(),
            state_fields=13,
            layout_fields=len(first.checkpoint.layout),
            observation_arrays=len(observations),
            original_steps=2,
            resumed_steps=1,
            full_suffix_exact=True,
            scope="Two-ns public eager execution; no scientific transient "
            "or compiled/GPU qualification",
        ),
        arrays,
    )
