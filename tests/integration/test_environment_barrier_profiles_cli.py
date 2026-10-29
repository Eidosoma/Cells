"""Portable barrier preparation through the existing tissue-profile commands."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from cells.__main__ import main
from cells.core.specs import digest
from cells.tissue_profiles import prepare_request, read_preparation
from tests.integration.test_cli import cli
from validation.transport import environment_barrier_preparation_fixtures as fixtures


@pytest.mark.parametrize("case", ("example", "permuted"))
def test_public_prepare_validate_and_fresh_replay_keep_the_complete_barrier_recipe(case, tmp_path):
    if case == "example":
        example = (
            Path(__file__).resolve().parents[2] / "examples/extracellular_barriers/request.json"
        )
        raw = json.loads(example.read_text())
        assert digest(raw) == digest(fixtures.request())
    else:
        raw = fixtures.request(permuted=True, padded=True)
    source = tmp_path / "request.json"
    source.write_text(json.dumps(raw))
    expected = prepare_request(raw)
    output = tmp_path / "prepared"
    made = cli("tissue-profiles", "prepare", source, "--output", output)
    assert made.returncode == 0, made.stderr
    assert read_preparation(output) == expected
    summary = json.loads(made.stdout)
    assert summary["definition_sha256"] == digest(expected.definition)
    assert summary["changed_coefficients"] == len(expected.provenance["changes"])
    for command in (
        ("tissue-profiles", "validate", output),
        ("validate", output / "definition.json"),
    ):
        result = cli(*command)
        assert result.returncode == 0, result.stderr
    replayed = tmp_path / "replayed"
    repeated = cli("tissue-profiles", "replay", output / "provenance.json", "--output", replayed)
    assert repeated.returncode == 0, repeated.stderr
    for name in ("definition.json", "provenance.json"):
        assert (output / name).read_bytes() == (replayed / name).read_bytes()
    assert json.loads(source.read_text()) == raw


@pytest.mark.parametrize("fault", ("duplicate", "nan", "overflow", "invalid", "missing_site"))
def test_bad_public_request_refuses_without_output(fault, tmp_path, capsys):
    raw = fixtures.request()
    if fault == "missing_site":
        raw["ion_modulators"]["Na"].pop(raw["grid"]["site_ids"][0])
    text = json.dumps(raw)
    if fault == "duplicate":
        text = '{"kind":"duplicate",' + text[1:]
    elif fault == "nan":
        text = text.replace('"tight_factor": ' + str(raw["tight_factor"]), '"tight_factor": NaN')
    elif fault == "overflow":
        text = text.replace('"tight_factor": ' + str(raw["tight_factor"]), '"tight_factor": 1e999')
    elif fault == "invalid":
        text = "{"
    path, output = tmp_path / "input.json", tmp_path / "refused"
    path.write_text(text)
    assert main(["tissue-profiles", "prepare", str(path), "--output", str(output)]) == 2
    assert not output.exists()
    assert path.read_text() == text
    assert capsys.readouterr().err


@pytest.mark.parametrize("command", ("prepare", "replay"))
def test_existing_output_refuses_before_reading_input(command, tmp_path, capsys):
    output = tmp_path / "existing"
    output.mkdir()
    kept = output / "keep.txt"
    kept.write_text("preserve")
    assert (
        main(["tissue-profiles", command, str(tmp_path / "absent.json"), "--output", str(output)])
        == 2
    )
    assert kept.read_text() == "preserve"
    assert "already exists" in capsys.readouterr().err


def test_modified_definition_refuses_public_validation(tmp_path, capsys):
    from cells.core.environment_barrier_preparation import write_preparation

    prepared = prepare_request(fixtures.request())
    output = tmp_path / "prepared"
    write_preparation(output, prepared)
    changed = deepcopy(prepared.definition)
    changed["model"]["faces"][0]["diffusivity_m2_per_s"]["Na"] *= 1.1
    (output / "definition.json").write_text(json.dumps(changed))
    assert main(["tissue-profiles", "validate", str(output)]) == 2
    assert capsys.readouterr().err
