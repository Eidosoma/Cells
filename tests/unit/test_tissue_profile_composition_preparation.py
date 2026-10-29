"""Composed inventories, gates, volumes, fuel, histories and independent flux."""

import ast
import hashlib
import json
import os
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from cells.core import tissue_profile_composition_preparation as bridge
from cells.core import tissue_profile_preparation as direct
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, digest, parse_spec
from cells.models.registry import get_model
from cells.processes import betse_tissue_profiles as native
from validation.topology import tissue_profile_composition_fixtures as fixtures
from validation.topology import tissue_profile_composition_reference as reference

ROOT = Path(__file__).resolve().parents[2]


def evidence(name, data):
    if folder := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        path = Path(folder)
        path.mkdir(parents=True, exist_ok=True)
        (path / ("tissue-profile-composition-" + name + ".json")).write_text(
            json.dumps(
                dict(data, status="passed"), indent=2, allow_nan=False, default=lambda v: v.tolist()
            )
            + "\n"
        )


def build(raw):
    raw = deepcopy(raw)
    g = deepcopy(raw["geometry"])
    layout = g.pop("layout")
    layout["cell_centres_m"] = np.asarray(layout["cell_centres_m"], float)
    geometry = bridge.Geometry(native.Layout(**layout), **g)

    def row(r):
        return native.Profile(
            r["name"],
            native.Selector(**r["selector"]),
            tuple(r["diffusivity_m2_s"]),
            r["is_gj_insular"],
        )

    return raw, geometry, row(raw["default"]), [row(r) for r in raw["profiles"]]


@lru_cache
def prepared(family, blocked=True, permuted=True):
    raw, g, default, rows = build(fixtures.inputs(family, blocked=blocked, permuted=permuted))
    value = bridge.prepare(
        raw["definition"],
        g,
        default,
        rows,
        ion_enabled=raw["ion_enabled"],
        enabled=raw["enabled"],
        is_ecm=raw["is_ecm"],
    )
    return raw, value


def compare(c, eq, actual, expected):
    observed = eq.flatten(c, actual._asdict())
    budget = eq.flatten(
        c, {k: np.full(s, 3e-23 if k.endswith("_C") else 3e-12) for k, s in c["shapes"].items()}
    ) + 3e-10 * np.abs(expected)
    ratio = float(np.max(np.abs(observed - expected) / budget, initial=0))
    assert ratio <= 1, ratio
    return ratio


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_independent_full_owner_state_and_expected_before_after_flux(family):
    raw, result = prepared(family)
    expected = reference.prepare(raw)["definition"]
    expected = parse_spec(expected).to_dict()
    actual = deepcopy(result.definition)
    mid, schema = bridge._schema(expected)
    a, b = bridge._leaf(actual, schema["path"]), bridge._leaf(expected, schema["path"])
    for domain in ("membranes", "junctions"):
        for left, right in zip(a[domain], b[domain], strict=True):
            np.testing.assert_allclose(
                list(left["permeability_m_per_s"].values()),
                list(right["permeability_m_per_s"].values()),
                rtol=5e-14,
                atol=1e-25,
            )
            left["permeability_m_per_s"] = right["permeability_m_per_s"]
    assert actual == expected
    assert reference.owners(raw["definition"]) == reference.owners(result.definition)
    assert result.definition["experiment"] == parse_spec(raw["definition"]).to_dict()["experiment"]
    eq = reference.equations(family)
    records = []
    before_state = None
    for name, data, target in (
        ("before", raw["definition"], raw["definition"]),
        ("after", result.definition, expected),
    ):
        spec = parse_spec(data)
        implementation = get_model(spec.model)
        state, p = implementation.initial_values(spec)
        context = eq.bind(target)
        np.testing.assert_array_equal(eq.flatten(context, state._asdict()), eq.initial(context))
        table = control_values(spec, [0.0])
        u = type(table)(*(v[0] for v in table))
        actual_slope = implementation.rhs(state, u, p, p.active, xp=np)
        expected_slope, expected_potential, proof = eq.evaluate(context, eq.initial(context), 0.0)
        ratio = compare(context, eq, actual_slope, expected_slope)
        field = implementation.field_values(state, u, p, xp=np)
        n = p.active.size
        potential = np.r_[field.potential_V[:n][p.active], field.potential_V[n:][p.outside_active]]
        np.testing.assert_allclose(potential, expected_potential, rtol=3e-10, atol=3e-13)
        assert bool(field.converged)
        records.append(
            dict(
                stage=name,
                error_over_budget=ratio,
                state_fields=list(state._fields),
                actual_potential_V=potential,
                independent_potential_V=expected_potential,
                reference_proof=proof,
            )
        )
        if before_state is None:
            before_state = state
        else:
            for x, y in zip(state, before_state, strict=True):
                np.testing.assert_array_equal(x, y)
    assert result.provenance["parent_model_id"] == mid
    assert result.provenance["control_history_sha256"] == digest(result.definition["experiment"])
    if family.startswith("regulation"):
        assert (
            result.definition["model"]["network_regulation"]
            == raw["definition"]["model"]["network_regulation"]
        )
        assert result.provenance["initial_regulation"] is not None
    evidence(
        "family-" + family,
        dict(
            source=raw["definition"],
            prepared=result.definition,
            provenance=result.provenance,
            independent_comparisons=records,
            inventory_and_initial_state_exact=True,
        ),
    )


def test_full_clock_histories_are_preserved_outside_parameter_view():
    _, result = prepared("regulation_v2")
    source = parse_spec(result.provenance["source_definition"])
    view = result.provenance["direct_parameter_preparation"]["source_definition"]
    view_spec = parse_spec(view)
    assert {r.time for r in source.experiment.changes} <= {
        r.time for r in view_spec.experiment.changes
    }
    original = source.to_dict()["experiment"]
    assert original == result.definition["experiment"]
    assert result.provenance["projection_scope"].startswith("Geometry/coefficient view only")
    evidence(
        "clock-scope",
        dict(actual_parent_histories_exact=True, parameter_projection_not_a_physical_field=True),
    )


@pytest.mark.parametrize("family", ["mitochondria", "fuel_water", "regulation_v2"])
def test_replay_retains_all_composed_properties_and_state(family):
    _, result = prepared(family)
    assert bridge.replay(result.provenance) == result
    evidence(
        "replay-" + family,
        dict(
            parent=result.provenance["parent_model_id"],
            state_fields=result.provenance["initial_state_fields"],
            full_recipe_reproduced=True,
        ),
    )


def test_serialized_composed_preparation_and_nonoverwrite(tmp_path):
    _, result = prepared("mitochondria")
    path = bridge.write_preparation(tmp_path / "prepared", result)
    assert bridge.read_preparation(path) == result
    with pytest.raises(FileExistsError):
        bridge.write_preparation(path, result)
    data = json.loads((path / "definition.json").read_text())
    data["model"]["mitochondria"]["compartments"][0]["initial_voltage_V"] += 0.001
    (path / "definition.json").write_text(json.dumps(data))
    with pytest.raises(ConfigError):
        bridge.read_preparation(path)
    evidence(
        "serialization",
        dict(full_mitochondrial_definition_reproduced=True, changed_organelle_state_refused=True),
    )


@pytest.mark.parametrize(
    "fault",
    [
        "schema-path",
        "owner-state",
        "control-history",
        "fuel-inventory",
        "volume",
        "regulation",
        "projected-recipe",
    ],
)
def test_resealed_inconsistent_composed_provenance_refuses(fault):
    family = "regulation_v2" if fault == "regulation" else "fuel_water"
    _, result = prepared(family)
    p = deepcopy(result.provenance)
    if fault == "schema-path":
        p["schema"]["path"] = []
    if fault == "owner-state":
        p["initial_state_sha256"] = "0" * 64
    if fault == "control-history":
        p["control_history_sha256"] = "0" * 64
    if fault == "fuel-inventory":
        p["source_definition"]["model"]["energy_pools"][0]["initial_amount_fmol"]["ATP"] *= 1.01
    if fault == "volume":
        p["initial_owner_inventory"]["water_compartments"][0]["reference_volume_pL"] *= 1.01
    if fault == "regulation":
        p["source_definition"]["model"]["network_regulation"]["rules"].reverse()
    if fault == "projected-recipe":
        p["direct_parameter_preparation"]["geometry"]["thickness_m"][
            next(iter(p["direct_parameter_preparation"]["geometry"]["thickness_m"]))
        ] *= 2
    p.pop("identity")
    p["identity"] = digest(p)
    with pytest.raises(ConfigError):
        bridge.replay(p)
    evidence("refused-" + fault, dict(fault=fault, refused=True))


@pytest.mark.parametrize(
    "fault",
    ["cut-id", "hidden-cut", "assembly", "wrong-inner-id", "missing-inner", "unknown-family"],
)
def test_cut_epochs_assembly_and_unknown_nested_schemas_are_refused(fault):
    data = deepcopy(fixtures.definition("fuel"))
    if fault == "cut-id":
        data["model"]["id"] = "resolved_calcium_energy_excision@1"
    if fault == "hidden-cut":
        data["model"]["excision"] = {}
    if fault == "assembly":
        data["model"]["id"] = "assembly_resolved_calcium_energy@1"
    if fault == "wrong-inner-id":
        data["model"]["ionic"]["id"] = "resolved_tissue@11"
    if fault == "missing-inner":
        data["model"].pop("ionic")
    if fault == "unknown-family":
        data["model"]["id"] = "resolved_calcium_energy_water_repair@1"
    with pytest.raises(ConfigError):
        bridge._schema(data)
    evidence("schema-refused-" + fault, dict(fault=fault, refused=True))


def test_disabled_profiles_leave_composed_definition_exact_and_projection_has_no_write_access():
    raw, g, default, rows = build(fixtures.inputs("transport"))
    raw["enabled"] = False
    source = parse_spec(raw["definition"]).to_dict()
    result = bridge.prepare(
        raw["definition"],
        g,
        default,
        rows,
        ion_enabled=raw["ion_enabled"],
        enabled=False,
        is_ecm=raw["is_ecm"],
    )
    assert result.definition == source and result.provenance["changes"] == []
    assert result.definition["model"]["network_transport"] == source["model"]["network_transport"]
    evidence("disabled", dict(all_composed_properties_exact=True, transporters_unchanged=True))


def test_qualified_direct_bridge_and_independent_equations_stay_unchanged():
    p = ROOT / "validation/topology/tissue_profile_composition_protocol.json"
    protocol = json.loads(p.read_text())
    for relative, expected in protocol["readonly_source_sha256"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected, relative
    native_receipt = protocol["direct_bridge_receipt"]
    assert (
        hashlib.sha256(Path(native_receipt["path"]).read_bytes()).hexdigest()
        == native_receipt["sha256"]
    )
    assert bridge.Geometry is direct.Geometry
    for module in (fixtures, reference):
        for node in ast.walk(ast.parse(Path(module.__file__).read_text())):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(("cells", "jax"))
    evidence(
        "provenance",
        dict(
            direct_bridge=native_receipt,
            readonly_sources=protocol["readonly_source_sha256"],
            shared_source_edits=False,
        ),
    )
