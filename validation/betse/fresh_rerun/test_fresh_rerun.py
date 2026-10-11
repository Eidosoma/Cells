"""Focused checks for fresh provenance, time handling, and detached execution."""

import copy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import common as u
import fresh_review
import pytest
import run


def test_preserves_scientific_limits():
    old = u.read(u.ROOT / "validation/betse/pump_matched_pilot/protocol.json")
    new = u.plan()
    for key in ("mapping", "trajectory", "refinement", "accounting", "reference", "cells_steps_s"):
        assert old[key] == new[key]
    assert new["duration_s"] == 0.01
    assert len(new["common_times_s"]) == 41
    assert sum(round(0.01 / h) for steps in u.RANGES.values() for h in steps) == 235200


def test_source_only_imports_do_not_require_lost_artifacts():
    command = [
        sys.executable,
        "-B",
        "-c",
        (
            "import sys; sys.path.insert(0, sys.argv[1]); import fresh_review; "
            "m, r, c = fresh_review.modules(); "
            "assert not any(n.split('.')[0] in ('numpy','scipy','cells','betse','jax') "
            "for n in sys.modules)"
        ),
        str(u.HERE),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)


def test_seal_rejects_mutated_input(tmp_path):
    u.write(tmp_path / "registration.json", {"fresh": True})
    u.write(tmp_path / "value.json", {"value": 1})
    u.write(
        tmp_path / "completion.json",
        {
            "registration_sha256": u.sha(tmp_path / "registration.json"),
            "files_sha256": {"value.json": u.sha(tmp_path / "value.json")},
        },
    )
    u.authenticate_stage(tmp_path)
    (tmp_path / "value.json").write_text('{"value": 2}')
    with pytest.raises(ValueError, match="Changed stage artifact"):
        u.authenticate_stage(tmp_path)


def test_refuses_existing_or_outside_output(tmp_path):
    with pytest.raises(ValueError, match="Fresh output"):
        run.register(tmp_path, tmp_path)
    with pytest.raises(ValueError, match="/mnt/workspaces"):
        run.register(Path("/tmp/cells-test-forbidden-new"), Path("/tmp"))


def test_timeout_retains_failure(tmp_path, monkeypatch):
    campaign = tmp_path / "campaign"
    campaign.mkdir()
    u.write(
        campaign / "registration.json",
        {"workspace": str(tmp_path), "sources_sha256": {}, "protocol": {}},
    )
    monkeypatch.setattr(u, "budget", lambda _: 0)

    def fail(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(subprocess.TimeoutExpired):
        run.run_stage(campaign, "native", campaign / "native")
    result = u.read(campaign / "native/controller_failure.json")
    assert "TimeoutExpired" in result["traceback"]
    assert result["automatic_retry"] is False
    assert not (campaign / "native/completion.json").exists()


class Match:
    def __init__(self):
        self.scalars = 0

    def match(self, a, b, _):
        assert a == b
        self.scalars += 1


@pytest.mark.parametrize("corruption", (None, "initial", "physical", "raw_call", "endpoint"))
def test_prefix_exempts_only_display_labels(corruption):
    steps = [{"raw_label_s": i, "after_voltage": {"v": i}} for i in range(2)]
    full = dict(
        dt_s=0.0005,
        steps=4,
        trace=dict(initial={"v": 0}, steps=steps, raw_steps=[{"index": 0}, {"index": 1}]),
        histories={"time": {"values": [0.0, 1.0]}, "vm": {"values": [1, 2]}},
    )
    short = copy.deepcopy(full)
    short.update(steps=2, final={"v": 1})
    short["histories"] = {"time": {"values": [0.003]}, "vm": {"values": [1]}}
    short["trace"]["steps"][1]["raw_label_s"] = 99
    if corruption == "initial":
        short["trace"]["initial"]["v"] = 3
    elif corruption == "physical":
        short["trace"]["steps"][0]["after_voltage"]["v"] = 3
    elif corruption == "raw_call":
        short["trace"]["raw_steps"][0]["index"] = 3
    elif corruption == "endpoint":
        short["final"]["v"] = 3
    if corruption is None:
        assert fresh_review.prefix(full, short, SimpleNamespace(Exact=Match))["steps"] == 2
    else:
        with pytest.raises(AssertionError):
            fresh_review.prefix(full, short, SimpleNamespace(Exact=Match))


def test_detached_source_and_output_binding(tmp_path, monkeypatch):
    output = tmp_path / "job"

    def register(path, workspace):
        path.mkdir()
        u.write(path / "registration.json", {})

    seen = {}

    def spawn(command, **kwargs):
        seen.update(command=command, **kwargs)
        return SimpleNamespace(pid=12345)

    monkeypatch.setattr(run, "register", register)
    monkeypatch.setattr(subprocess, "Popen", spawn)
    monkeypatch.setattr(
        sys, "argv", ["run.py", "launch", str(output), "--workspace", str(tmp_path)]
    )
    run.main()
    assert seen["start_new_session"] and seen["close_fds"]
    assert Path(seen["command"][2]).is_relative_to(output / "source")
    assert seen["stdin"] == subprocess.DEVNULL
    assert u.read(output / "launch.json")["pid"] == 12345
