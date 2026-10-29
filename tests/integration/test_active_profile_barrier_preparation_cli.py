"""Public, portable ordered preparation for the combined ionic schedule owner."""

import json
import subprocess
import sys
from copy import deepcopy

import pytest

from cells.core.specs import ConfigError, digest
from cells.tissue_profiles import main, prepare_request, read_preparation, replay
from tests.active_profile_barrier_dispatch_fixtures import prepared
from tests.unit.test_surface_catalog import evidence


def invoke(directory, name, *args):
    value = subprocess.run(
        [sys.executable, "-B", "-m", "cells", *map(str, args)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    (directory / (name + ".stdout.log")).write_text(value.stdout)
    (directory / (name + ".stderr.log")).write_text(value.stderr)
    assert value.returncode == 0, value.stderr
    return json.loads(value.stdout)


def test_combined_public_prepare_validate_and_portable_fresh_replay(tmp_path):
    _, request, expected = prepared()
    source = tmp_path / "request.json"
    source.write_text(json.dumps(request))
    output = tmp_path / "prepared"
    summary = invoke(tmp_path, "prepare", "tissue-profiles", "prepare", source, "--output", output)
    assert read_preparation(output) == expected
    assert summary["model_id"] == "resolved_tissue@12"
    assert summary["kind"] == "cells.active_profile_barrier_preparation@1"
    counts = summary["coefficient_changes_by_layer"]
    assert counts == dict(
        membrane=len(expected.provenance["profile_preparation"]["provenance"]["changes"]),
        extracellular=len(expected.provenance["barrier_preparation"]["provenance"]["changes"]),
    )
    assert summary["changed_coefficients"] == sum(counts.values())
    assert summary["definition_sha256"] == digest(expected.definition)
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    invoke(tmp_path, "validate", "tissue-profiles", "validate", output)
    source.unlink()
    repeated = tmp_path / "replayed"
    invoke(
        tmp_path,
        "replay",
        "tissue-profiles",
        "replay",
        output / "provenance.json",
        "--output",
        repeated,
    )
    assert read_preparation(repeated) == expected
    assert {p.name: p.read_bytes() for p in output.iterdir()} == before
    assert {p.name: p.read_bytes() for p in repeated.iterdir()} == before
    evidence(
        "combined-profile-barrier-preparation-cli",
        dict(
            request=request,
            summary=summary,
            exact_portable_fresh_replay=True,
            scope="Static preparation and source recipe only; no trajectory qualification",
        ),
    )


@pytest.mark.parametrize("fault", ("order", "owner", "nested-definition"))
def test_combined_public_request_refuses_mismatch_without_writing(fault, tmp_path, capsys):
    _, source, _ = prepared()
    request = deepcopy(source)
    if fault == "order":
        request["order"] = "reversed"
    elif fault == "owner":
        request["barrier_request"]["definition"]["model"]["id"] = "resolved_tissue@1"
    else:
        request["profile_preparation"]["definition"]["model"]["temperature_K"] *= 1.01
    with pytest.raises(ConfigError):
        prepare_request(request)
    path, output = tmp_path / "request.json", tmp_path / "refused"
    path.write_text(json.dumps(request))
    assert main(["prepare", str(path), "--output", str(output)]) == 2
    assert not output.exists() and capsys.readouterr().err


def test_combined_writer_refuses_overwrite_and_changed_artifact(tmp_path, capsys):
    from cells.tissue_profiles import _write_preparation

    _, _, expected = prepared()
    output = _write_preparation(tmp_path / "prepared", expected)
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    with pytest.raises(ConfigError, match="already exists"):
        _write_preparation(output, expected)
    assert before == {p.name: p.read_bytes() for p in output.iterdir()}
    changed = deepcopy(expected.definition)
    changed["model"]["faces"][0]["diffusivity_m2_per_s"]["Na"] *= 1.01
    (output / "definition.json").write_text(json.dumps(changed))
    assert main(["validate", str(output)]) == 2
    assert capsys.readouterr().err
    invalid = deepcopy(expected.provenance)
    invalid["initial_state_fields"] = []
    with pytest.raises(ConfigError):
        replay(invalid)
