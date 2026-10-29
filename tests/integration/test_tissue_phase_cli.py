"""Explicit phase preparation is portable, strict and distinct from ordinary restart."""

import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from cells.__main__ import main
from cells.core import membrane_profile_phase_handoff as handoff
from cells.core.specs import digest, parse_spec
from cells.core.state import initialise
from cells.io import load_snapshot, write_snapshot
from cells.tissue_phase import read_preparation
from tests.integration.test_cli import cli
from tests.phase_fixtures import EXAMPLE, prepared, request


def test_portable_cli_prepare_validate_and_fresh_replay(tmp_path, capsys):
    original = EXAMPLE.read_bytes()
    folder = tmp_path / "prepared"
    assert main(["tissue-phase", "prepare", str(EXAMPLE), "--output", str(folder)]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["model_id"] == "resolved_membrane_profile_epoch@1"
    assert len(summary["carried_parent_fields"]) == 12
    assert summary["clocks"]["init_checkpoint_time_s"] > 0
    assert summary["clocks"]["sim_epoch_time_s"] == 0
    expected = prepared()
    assert read_preparation(folder) == expected
    result = cli("tissue-phase", "validate", folder)
    assert result.returncode == 0, result.stderr
    replayed = tmp_path / "replayed"
    result = cli("tissue-phase", "replay", folder / "provenance.json", "--output", replayed)
    assert result.returncode == 0, result.stderr
    assert read_preparation(replayed) == expected
    # The embedded checkpoint suffices after the original preparation is removed.
    portable = tmp_path / "portable.json"
    (folder / "provenance.json").replace(portable)
    (folder / "definition.json").unlink()
    folder.rmdir()
    result = cli("tissue-phase", "replay", portable, "--output", tmp_path / "portable-replay")
    assert result.returncode == 0, result.stderr
    assert read_preparation(tmp_path / "portable-replay") == expected
    assert EXAMPLE.read_bytes() == original


def test_cli_from_evolved_snapshot_preserves_the_same_complete_recipe(tmp_path):
    value = request()
    source, point = handoff.decode_source(value["source"])
    folder = write_snapshot(tmp_path / "INIT", source, point)
    original = {p.name: p.read_bytes() for p in folder.iterdir()}
    simulation = tmp_path / "SIM.json"
    simulation.write_text(json.dumps(value["simulation"]))
    output = tmp_path / "SIM-preparation"
    result = cli("tissue-phase", "from-snapshot", folder, simulation, "--output", output)
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["source_snapshot_sha256"] == load_snapshot(folder).fingerprint
    actual = read_preparation(output)
    assert actual == prepared()
    state = initialise(parse_spec(actual.definition)).state
    for name in summary["carried_parent_fields"]:
        np.testing.assert_array_equal(getattr(state, name), getattr(point.state, name))
    np.testing.assert_array_equal(state.phase_clock_s, [0.0])
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == original


@pytest.mark.parametrize("command", ["prepare", "replay", "from-snapshot"])
def test_no_output_overwrite_before_reading_any_input(command, tmp_path, capsys):
    for symbolic in (False, True):
        output = tmp_path / ("link" if symbolic else "existing")
        if symbolic:
            output.symlink_to(tmp_path / "absent")
        else:
            output.mkdir()
            (output / "keep").write_text("unchanged")
        inputs = [str(tmp_path / "missing.json")] * (2 if command == "from-snapshot" else 1)
        assert main(["tissue-phase", command, *inputs, "--output", str(output)]) == 2
        assert "already exists" in capsys.readouterr().err
        assert output.is_symlink() if symbolic else (output / "keep").read_text() == "unchanged"


@pytest.mark.parametrize("fault", ["duplicate", "nonfinite", "overflow", "invalid", "wrong_kind"])
def test_bad_json_or_wrong_request_refuses_without_output(fault, tmp_path, capsys):
    text = EXAMPLE.read_text()
    if fault == "duplicate":
        text = '{"kind":"duplicate",' + text.lstrip()[1:]
    elif fault in ("nonfinite", "overflow"):
        value = "NaN" if fault == "nonfinite" else "1e999"
        text = '{"bad_number":' + value + "," + text.lstrip()[1:]
    elif fault == "invalid":
        text = "{"
    else:
        value = request()
        value["kind"] = "unrecognized@1"
        text = json.dumps(value)
    source = tmp_path / "bad.json"
    source.write_text(text)
    target = tmp_path / "refused"
    assert main(["tissue-phase", "prepare", str(source), "--output", str(target)]) == 2
    assert "cells tissue-phase:" in capsys.readouterr().err
    assert not target.exists() and source.read_text() == text


@pytest.mark.parametrize("field", ["definition", "provenance"])
def test_changed_artifacts_refuse_public_validation(field, tmp_path, capsys):
    folder = tmp_path / "preparation"
    value = prepared()
    handoff.write_preparation(folder, value)
    if field == "definition":
        altered = deepcopy(value.definition)
        altered["model"]["handoff"]["clocks"]["sim_epoch_time_s"] = False
    else:
        altered = deepcopy(value.provenance)
        altered["preservation"]["carried_parent_fields"] = []
        altered["identity"] = digest({k: v for k, v in altered.items() if k != "identity"})
    (folder / (field + ".json")).write_text(json.dumps(altered))
    assert main(["tissue-phase", "validate", str(folder)]) == 2
    assert "cells tissue-phase:" in capsys.readouterr().err


def test_SIM_snapshot_cannot_silently_become_a_new_SIM_epoch(tmp_path, capsys):
    value = request()
    sim = parse_spec(value["simulation"])
    folder = write_snapshot(tmp_path / "SIM", sim, initialise(sim))
    simulation = tmp_path / "new-SIM.json"
    simulation.write_text(json.dumps(value["simulation"]))
    output = tmp_path / "refused"
    assert (
        main(
            ["tissue-phase", "from-snapshot", str(folder), str(simulation), "--output", str(output)]
        )
        == 2
    )
    assert "INIT" in capsys.readouterr().err and not output.exists()


def test_help_lists_the_explicit_phase_operation():
    assert "tissue-phase" in cli("--help").stdout
    result = cli("tissue-phase", "--help")
    assert result.returncode == 0 and "from-snapshot" in result.stdout
    assert Path(EXAMPLE).is_file()
