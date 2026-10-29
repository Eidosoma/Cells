"""Public preparation preserves complete composed models across process boundaries."""

import json
from copy import deepcopy

import numpy as np
import pytest

from cells.__main__ import main
from cells.core import tissue_profile_composition_preparation as composed
from cells.core.specs import digest, parse_spec
from cells.models.registry import get_model
from cells.tissue_profiles import REQUEST_KIND, prepare_request, read_preparation
from tests.integration.test_cli import cli
from validation.topology import tissue_profile_composition_fixtures as fixtures
from validation.topology import tissue_profile_composition_reference as reference


def request(family):
    return dict(schema_version=1, kind=REQUEST_KIND, **fixtures.inputs(family, permuted=True))


@pytest.mark.parametrize(
    "family",
    [
        *(f"ionic_v{i}" for i in range(2, 12)),
        "transport",
        "mitochondria",
        "fuel_water",
        "energy_water",
        "regulation_v1",
        "regulation_v2",
    ],
)
def test_composed_prepare_validate_replay_preserves_independent_recipe(family, tmp_path):
    raw = request(family)
    source = tmp_path / "request.json"
    source.write_text(json.dumps(raw))
    source_bytes = source.read_bytes()
    output = tmp_path / "prepared"
    result = cli("tissue-profiles", "prepare", source, "--output", output)
    assert result.returncode == 0, result.stderr
    actual = read_preparation(output)
    expected = parse_spec(
        reference.prepare(
            {k: deepcopy(v) for k, v in raw.items() if k not in ("kind", "schema_version")}
        )["definition"]
    ).to_dict()
    canonical = deepcopy(actual.definition)
    leaf = canonical["model"].get("ionic", canonical["model"])
    expected_leaf = expected["model"].get("ionic", expected["model"])
    for domain in ("membranes", "junctions"):
        for left, right in zip(leaf[domain], expected_leaf[domain], strict=True):
            assert left["id"] == right["id"]
            a, b = left["permeability_m_per_s"], right["permeability_m_per_s"]
            assert a.keys() == b.keys()
            np.testing.assert_allclose(list(a.values()), list(b.values()), rtol=5e-14, atol=1e-25)
            left["permeability_m_per_s"] = b
    assert canonical == expected
    summary = json.loads(result.stdout)
    assert summary["kind"] == composed.KIND
    assert summary["model_id"] == expected["model"]["id"]
    assert summary["definition_sha256"] == digest(actual.definition)
    before, after = parse_spec(raw["definition"]), parse_spec(actual.definition)
    assert reference.owners(before.to_dict()) == reference.owners(after.to_dict())
    a, _ = get_model(before.model).initial_values(before)
    b, _ = get_model(after.model).initial_values(after)
    assert type(a) is type(b)
    for x, y in zip(a, b, strict=True):
        assert np.asarray(x).dtype == np.asarray(y).dtype
        np.testing.assert_array_equal(x, y)
    assert before.to_dict()["experiment"] == after.to_dict()["experiment"]
    verified = cli("tissue-profiles", "validate", output)
    assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout)["preparation_identity"] == summary["preparation_identity"]
    repeated = tmp_path / "replayed"
    replayed = cli("tissue-profiles", "replay", output / "provenance.json", "--output", repeated)
    assert replayed.returncode == 0, replayed.stderr
    for name in ("definition.json", "provenance.json"):
        assert (output / name).read_bytes() == (repeated / name).read_bytes()
    assert source.read_bytes() == source_bytes


@pytest.mark.parametrize("fault", ["unknown", "cut", "assembly", "repair", "nested", "nonobject"])
def test_unsupported_composed_requests_refuse_without_output(fault, tmp_path, capsys):
    raw = request("regulation_v2")
    if fault == "nested":
        raw["definition"]["model"]["ionic"]["id"] = "resolved_tissue@1"
    elif fault == "nonobject":
        raw["definition"] = []
    else:
        raw["definition"]["model"]["id"] = {
            "unknown": "resolved_calcium_energy_regulated@99",
            "cut": "resolved_calcium_energy_regulated_excision@1",
            "assembly": "assembly_cluster@1",
            "repair": "resolved_tissue_repair@1",
        }[fault]
    source = tmp_path / "request.json"
    text = json.dumps(raw)
    source.write_text(text)
    output = tmp_path / "refused"
    assert main(["tissue-profiles", "prepare", str(source), "--output", str(output)]) == 2
    assert "cells tissue-profiles:" in capsys.readouterr().err
    assert not output.exists() and source.read_text() == text


@pytest.mark.parametrize("fault", ["kind", "direct_kind", "recipe", "geometry", "layout", "units"])
def test_composed_provenance_refuses_malformed_or_resealed_recipe(fault, tmp_path, capsys):
    provenance = deepcopy(prepare_request(request("regulation_v2")).provenance)
    if fault == "kind":
        provenance["kind"] = "unknown"
    elif fault == "direct_kind":
        provenance["kind"] = "cells.resolved_tissue_profile_preparation@1"
    elif fault == "recipe":
        provenance["direct_parameter_preparation"] = None
    elif fault == "geometry":
        provenance["direct_parameter_preparation"]["geometry"] = None
    elif fault == "layout":
        provenance["direct_parameter_preparation"]["geometry"]["layout"] = None
    else:
        provenance["direct_parameter_preparation"]["geometry"]["length_unit"] = "nm"
    provenance["identity"] = digest({k: v for k, v in provenance.items() if k != "identity"})
    source = tmp_path / "provenance.json"
    source.write_text(json.dumps(provenance))
    output = tmp_path / "refused"
    assert main(["tissue-profiles", "replay", str(source), "--output", str(output)]) == 2
    assert "cells tissue-profiles:" in capsys.readouterr().err and not output.exists()
