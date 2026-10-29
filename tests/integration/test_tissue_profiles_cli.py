"""Public static preparation keeps units, recipe identity and refusal semantics."""

import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from cells.__main__ import main
from cells.core.specs import digest, parse_spec
from cells.models.registry import get_model
from cells.processes import betse_tissue_profiles as native
from cells.tissue_profiles import REQUEST_KIND, prepare_request, read_preparation
from tests.integration.test_cli import cli
from validation.topology import tissue_profile_preparation_fixtures as fixtures
from validation.topology import tissue_profile_preparation_reference as reference


def request(kind="active", arm="overlap"):
    raw = fixtures.inputs(kind, arm, permuted=True)
    if arm == "indices-duplicates":
        identity = native.layout_identity(native.Layout(**raw["geometry"]["layout"]))
        for row in raw["profiles"]:
            row["selector"]["expected_layout_identity"] = identity
    return dict(schema_version=1, kind=REQUEST_KIND, **raw)


@pytest.mark.parametrize("kind", ["passive", "active"])
@pytest.mark.parametrize("arm", ["overlap", "image", "indices-duplicates"])
def test_public_prepare_replay_and_validation_preserve_independent_recipe(kind, arm, tmp_path):
    raw = request(kind, arm)
    original = deepcopy(raw)
    source = tmp_path / "request.json"
    source.write_text(json.dumps(raw))
    prepared = tmp_path / "prepared"
    result = cli("tissue-profiles", "prepare", source, "--output", prepared)
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    expected = parse_spec(reference.prepare(fixtures_for_reference(raw))["definition"]).to_dict()
    actual = read_preparation(prepared)
    canonical = deepcopy(actual.definition)
    for domain in ("membranes", "junctions"):
        for left, right in zip(canonical["model"][domain], expected["model"][domain], strict=True):
            assert left["id"] == right["id"]
            a, b = left["permeability_m_per_s"], right["permeability_m_per_s"]
            assert a.keys() == b.keys()
            # The independent Decimal conversion has its established component
            # tolerance; complete CLI artifact replay below remains bitwise.
            np.testing.assert_allclose(list(a.values()), list(b.values()), rtol=5e-14, atol=1e-25)
            left["permeability_m_per_s"] = b
    assert canonical == expected
    assert summary["definition_sha256"] == digest(actual.definition)
    assert summary["model_id"] == expected["model"]["id"]
    assert json.loads(source.read_text()) == original
    before = parse_spec(raw["definition"])
    after = parse_spec(actual.definition)
    a, _ = get_model(before.model).initial_values(before)
    b, _ = get_model(after.model).initial_values(after)
    for x, y in zip(a, b, strict=True):
        np.testing.assert_array_equal(x, y)
    verified = cli("tissue-profiles", "validate", prepared)
    assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout)["preparation_identity"] == summary["preparation_identity"]
    repeated = tmp_path / "replayed"
    replayed = cli("tissue-profiles", "replay", prepared / "provenance.json", "--output", repeated)
    assert replayed.returncode == 0, replayed.stderr
    for name in ("definition.json", "provenance.json"):
        assert (prepared / name).read_bytes() == (repeated / name).read_bytes()


def fixtures_for_reference(raw):
    return {k: deepcopy(v) for k, v in raw.items() if k not in ("kind", "schema_version")}


@pytest.mark.parametrize(
    "fault",
    [
        "schema_bool",
        "unknown_request",
        "unknown_profile",
        "unknown_selector",
        "missing_units",
        "wrong_units",
        "missing_partner",
        "unbound_indices",
        "unsupported_ion",
        "nonfinite",
        "overflow",
        "duplicate_field",
        "invalid_json",
    ],
)
def test_invalid_requests_refuse_without_output_or_source_changes(fault, tmp_path, capsys):
    raw = request(arm="indices-duplicates" if fault == "unbound_indices" else "overlap")
    if fault == "schema_bool":
        raw["schema_version"] = True
    elif fault == "unknown_request":
        raw["tissue"] = "unused"
    elif fault == "unknown_profile":
        raw["profiles"][0]["typo_diffusion"] = 1.0
    elif fault == "unknown_selector":
        raw["profiles"][0]["selector"]["extra"] = []
    elif fault == "missing_units":
        raw["geometry"].pop("length_unit")
    elif fault == "wrong_units":
        raw["geometry"]["length_unit"] = "nm"
    elif fault == "missing_partner":
        raw["geometry"]["partner_membrane_ids"].pop(next(iter(raw["geometry"]["thickness_m"])))
    elif fault == "unbound_indices":
        raw["profiles"][0]["selector"]["expected_layout_identity"] = None
    elif fault == "unsupported_ion":
        raw["ion_enabled"][-1] = True
    text = json.dumps(raw)
    if fault == "nonfinite":
        text = text.replace('"rho_channel": 1.0', '"rho_channel": NaN')
    elif fault == "overflow":
        text = text.replace('"rho_channel": 1.0', '"rho_channel": 1e999')
    elif fault == "duplicate_field":
        text = text.replace('"schema_version": 1', '"schema_version": 0, "schema_version": 1')
    elif fault == "invalid_json":
        text = "{"
    source = tmp_path / "request.json"
    source.write_text(text)
    output = tmp_path / "refused"
    assert main(["tissue-profiles", "prepare", str(source), "--output", str(output)]) == 2
    assert "cells tissue-profiles:" in capsys.readouterr().err
    assert not output.exists()
    assert source.read_text() == text


def test_nonoverwrite_is_checked_before_loading_recipe(tmp_path, capsys):
    output = tmp_path / "existing"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("original")
    missing = tmp_path / "missing.json"
    for operation in ("prepare", "replay"):
        assert main(["tissue-profiles", operation, str(missing), "--output", str(output)]) == 2
        assert "already exists" in capsys.readouterr().err
        assert marker.read_text() == "original"
    link = tmp_path / "dangling"
    link.symlink_to(tmp_path / "absent")
    assert main(["tissue-profiles", "prepare", str(missing), "--output", str(link)]) == 2
    assert "already exists" in capsys.readouterr().err and link.is_symlink()


def test_artifact_tampering_refuses_with_clean_cli_error(tmp_path, capsys):
    from cells.core.tissue_profile_preparation import write_preparation

    root = tmp_path / "prepared"
    prepared = prepare_request(request())
    write_preparation(root, prepared)
    definition = deepcopy(prepared.definition)
    definition["model"]["membranes"][0]["permeability_m_per_s"]["K"] *= 2
    (root / "definition.json").write_text(json.dumps(definition))
    assert main(["tissue-profiles", "validate", str(root)]) == 2
    assert "changed" in capsys.readouterr().err
    (root / "definition.json").write_text(json.dumps(prepared.definition))
    provenance = deepcopy(prepared.provenance)
    provenance["geometry"]["length_unit"] = "nm"
    provenance["identity"] = digest({k: v for k, v in provenance.items() if k != "identity"})
    (root / "provenance.json").write_text(json.dumps(provenance))
    assert main(["tissue-profiles", "validate", str(root)]) == 2
    assert "geometry" in capsys.readouterr().err
    path = tmp_path / "not-provenance.json"
    path.write_text("3")
    output = tmp_path / "refused"
    assert main(["tissue-profiles", "replay", str(path), "--output", str(output)]) == 2
    assert "provenance" in capsys.readouterr().err and not output.exists()


def test_repository_example_and_top_level_help():
    path = Path(__file__).resolve().parents[2] / "configs/tissue_profiles_active.json"
    result = prepare_request(json.loads(path.read_text()))
    assert result.definition["model"]["id"] == "resolved_tissue@12"
    assert "tissue-profiles" in cli("--help").stdout
    assert cli("tissue-profiles", "--help").returncode == 0
