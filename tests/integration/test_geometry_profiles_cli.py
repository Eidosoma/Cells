"""The public geometry/profile path retains physical inputs and both recipes."""

import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from cells.__main__ import main
from cells.core import geometry_profile_preparation as geometric
from cells.core.specs import digest, parse_spec
from cells.models.registry import get_model
from cells.tissue_profiles import prepare_request, read_preparation
from tests.integration.test_cli import cli
from tests.integration.test_tissue_profiles_cli import request as direct_request
from tests.integration.test_tissue_profiles_composed_cli import request as composed_request

EXAMPLE = Path(__file__).resolve().parents[2] / (
    "examples/geometry_tissue_profiles/irregular_overlap.request.json"
)


def geometry_request():
    return json.loads(EXAMPLE.read_text())


def test_public_geometry_profiles_replays_without_original_input(tmp_path):
    raw = geometry_request()
    source = tmp_path / "request.json"
    source.write_bytes(EXAMPLE.read_bytes())
    output = tmp_path / "prepared"
    prepared = cli("tissue-profiles", "prepare", source, "--output", output)
    assert prepared.returncode == 0, prepared.stderr
    summary = json.loads(prepared.stdout)
    actual = read_preparation(output)
    assert summary["kind"] == geometric.KIND
    assert summary["model_id"] == "resolved_tissue@1"
    assert summary["definition_sha256"] == digest(actual.definition)
    assert digest(actual.provenance["request"]) == digest(raw)
    assert (
        actual.provenance["geometry_preparation_identity"]
        == (raw["geometry_preparation"]["provenance"]["identity"])
    )
    assert (
        actual.provenance["profile_preparation_identity"]
        == (actual.provenance["profile_preparation"]["identity"])
    )
    original = raw["geometry_preparation"]["definition"]
    before, after = parse_spec(original), parse_spec(actual.definition)
    a, _ = get_model(before.model).initial_values(before)
    b, _ = get_model(after.model).initial_values(after)
    assert type(a) is type(b)
    for left, right in zip(a, b, strict=True):
        assert np.asarray(left).dtype == np.asarray(right).dtype
        np.testing.assert_array_equal(left, right)
    for key in ("species", "cells", "extracellular"):
        assert digest(original["model"][key]) == digest(actual.definition["model"][key])
    assert digest(original["experiment"]) == digest(actual.definition["experiment"])
    assert actual.provenance["changes"]
    assert source.read_bytes() == EXAMPLE.read_bytes()
    source.unlink()
    validated = cli("tissue-profiles", "validate", output)
    assert validated.returncode == 0, validated.stderr
    replayed = tmp_path / "replayed"
    result = cli("tissue-profiles", "replay", output / "provenance.json", "--output", replayed)
    assert result.returncode == 0, result.stderr
    for name in ("definition.json", "provenance.json"):
        assert (output / name).read_bytes() == (replayed / name).read_bytes()


@pytest.mark.parametrize("family", ["direct", "composed", "geometry"])
@pytest.mark.parametrize("fault", ["boolean_as_integer", "integer_as_boolean"])
def test_artifact_validation_rejects_equal_values_with_different_json_types(
    family, fault, tmp_path, capsys
):
    raw = {
        "direct": direct_request,
        "composed": lambda: composed_request("regulation_v2"),
        "geometry": geometry_request,
    }[family]()
    result = prepare_request(raw)
    definition = deepcopy(result.definition)
    if fault == "boolean_as_integer":
        assert type(definition["execution"]["jit"]) is bool
        definition["execution"]["jit"] = int(definition["execution"]["jit"])
    else:
        assert definition["schema_version"] == 1
        definition["schema_version"] = True
    assert definition == result.definition
    assert digest(definition) != digest(result.definition)
    root = tmp_path / "prepared"
    root.mkdir()
    for name, value in (("definition", definition), ("provenance", result.provenance)):
        (root / (name + ".json")).write_text(json.dumps(value))
    saved = {p.name: p.read_bytes() for p in root.iterdir()}
    assert main(["tissue-profiles", "validate", str(root)]) == 2
    assert "changed" in capsys.readouterr().err
    assert {p.name: p.read_bytes() for p in root.iterdir()} == saved


@pytest.mark.parametrize(
    "fault",
    ["artifact", "source_identity", "typed_definition", "unknown_field", "missing_thickness"],
)
def test_geometry_profile_requests_refuse_damaged_sources_without_output(fault, tmp_path, capsys):
    raw = geometry_request()
    if fault == "artifact":
        raw["geometry_preparation"] = []
    elif fault == "source_identity":
        raw["geometry_preparation"]["provenance"]["identity"] = "0" * 64
    elif fault == "typed_definition":
        raw["geometry_preparation"]["definition"]["schema_version"] = True
    elif fault == "unknown_field":
        raw["inferred_owners"] = True
    else:
        raw["geometry_preparation"]["provenance"]["request"]["physics"]["membranes"][0].pop(
            "thickness_m"
        )
    source = tmp_path / "request.json"
    source.write_text(json.dumps(raw))
    saved = source.read_bytes()
    output = tmp_path / "refused"
    assert main(["tissue-profiles", "prepare", str(source), "--output", str(output)]) == 2
    assert "cells tissue-profiles:" in capsys.readouterr().err
    assert not output.exists() and source.read_bytes() == saved


@pytest.mark.parametrize("fault", ["unknown_kind", "profile_chain", "geometry_chain"])
def test_geometry_profile_replay_refuses_resealed_incomplete_chains(fault, tmp_path, capsys):
    value = deepcopy(prepare_request(geometry_request()).provenance)
    if fault == "unknown_kind":
        value["kind"] = "cells.initial_geometry_profile_preparation@99"
    elif fault == "profile_chain":
        value["profile_preparation"] = None
    else:
        value["request"]["geometry_preparation"]["provenance"] = None
    value["identity"] = digest({k: v for k, v in value.items() if k != "identity"})
    source = tmp_path / "provenance.json"
    source.write_text(json.dumps(value))
    saved = source.read_bytes()
    output = tmp_path / "refused"
    assert main(["tissue-profiles", "replay", str(source), "--output", str(output)]) == 2
    assert "cells tissue-profiles:" in capsys.readouterr().err
    assert not output.exists() and source.read_bytes() == saved


def test_deeply_nested_json_is_a_clean_refusal(tmp_path, capsys):
    source = tmp_path / "request.json"
    content = "[" * 2000 + "0" + "]" * 2000
    source.write_text(content)
    output = tmp_path / "refused"
    assert main(["tissue-profiles", "prepare", str(source), "--output", str(output)]) == 2
    # JSON decoders differ in whether this reaches their recursion limit or
    # the ordinary request-schema check. Both must give a clean refusal.
    error = capsys.readouterr().err
    assert error.startswith("cells tissue-profiles:") and "Traceback" not in error
    assert not output.exists() and source.read_text() == content
