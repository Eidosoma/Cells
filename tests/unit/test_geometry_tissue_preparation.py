"""Explicit geometry/physics preparation, independent passive flux and replay."""

import ast
import hashlib
import json
import os
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from cells.core import geometry_tissue_preparation as bridge
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, digest, parse_spec
from cells.models import surface_tissue as model
from validation.geometry import geometry_tissue_preparation_fixtures as fixtures
from validation.geometry import geometry_tissue_preparation_reference as reference
from validation.tissue import surface_dynamics_reference as equations

ROOT = Path(__file__).resolve().parents[2]


def evidence(name, record):
    if folder := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        p = Path(folder)
        p.mkdir(parents=True, exist_ok=True)
        (p / ("geometry-tissue-" + name + ".json")).write_text(
            json.dumps(
                dict(record, status="passed"),
                indent=2,
                allow_nan=False,
                default=lambda v: v.tolist(),
            )
            + "\n"
        )


@lru_cache
def prepared(name="irregular-centroid-aux", policy="native_radial"):
    request = fixtures.request(name, policy, permuted=True)
    return request, bridge.prepare(request)


def compare_definition(actual, expected):
    actual = deepcopy(actual)
    expected = deepcopy(expected)
    for domain, fields in (
        ("cells", ("volume_pL",)),
        ("membranes", ("area_m2", "capacitance_F")),
        ("junctions", ("area_m2",)),
    ):
        for a, b in zip(actual["model"][domain], expected["model"][domain], strict=True):
            for field in fields:
                np.testing.assert_allclose(a[field], b[field], rtol=6e-12, atol=1e-30)
                a[field] = b[field]
    assert actual == expected


@pytest.mark.parametrize("name", fixtures.CASES)
@pytest.mark.parametrize("policy", ["native_radial", "polygon"])
def test_complete_native_owners_units_inventory_field_and_flux(name, policy):
    request, result = prepared(name, policy)
    expected = reference.definition(request)
    expected = parse_spec(expected).to_dict()
    compare_definition(result.definition, expected)
    assert result.definition["model"]["id"] == "resolved_tissue@1"
    assert result.provenance["request"] == request
    assert result.definition["experiment"] == request["experiment"]
    assert result.definition["execution"] == request["execution"]
    spec = parse_spec(result.definition)
    state, p = model.initial_values(spec)
    c = equations.bind(expected)
    np.testing.assert_array_equal(equations.flatten(c, state._asdict()), equations.initial(c))
    comparisons = []
    for time in (0.0, 5e-6):
        table = control_values(spec, [time])
        u = type(table)(*(v[0] for v in table))
        actual = model.rhs(state, u, p, p.active, xp=np)
        target, phi, proof = equations.evaluate(c, equations.initial(c), time)
        flat = equations.flatten(c, actual._asdict())
        budget = equations.flatten(
            c,
            {
                key: np.full(shape, 3e-23 if key.endswith("_C") else 3e-12)
                for key, shape in c["shapes"].items()
            },
        ) + 3e-10 * np.abs(target)
        ratio = float(np.max(np.abs(flat - target) / budget, initial=0))
        assert ratio <= 1, ratio
        field = model.field_values(state, u, p, xp=np)
        n = p.active.size
        voltage = np.r_[field.potential_V[:n][p.active], field.potential_V[n:][p.outside_active]]
        np.testing.assert_allclose(voltage, phi, rtol=3e-10, atol=3e-13)
        assert bool(field.converged) and bool(model.domain_valid(state, p, p.active, xp=np))
        assert abs(field.energy_balance_pJ_s) < 1e-10
        mass = (
            actual.amount_increment.sum(axis=1)
            + actual.extracellular_amount_increment.sum(axis=1)
            - actual.reservoir_supplied.sum(axis=1)
        )
        np.testing.assert_allclose(mass, 0, rtol=0, atol=3e-14)
        comparisons.append(
            dict(
                time_s=time,
                error_over_budget=ratio,
                independent_proof=proof,
                potential_V=voltage,
                material_residual_fmol_s=mass,
                physical_energy_balance_pJ_s=float(field.energy_balance_pJ_s),
            )
        )
    owners = {row["id"]: row for row in result.definition["model"]["cells"]}
    for row in request["physics"]["cells"]:
        for field in ("initial_amount_fmol", "initial_charge_C", "fixed_charge_equivalent_fmol"):
            assert owners[row["id"]][field] == row[field]
    exterior = {row["id"]: row for row in result.definition["model"]["extracellular"]}
    for row in request["physics"]["extracellular"]:
        assert exterior[row["id"]]["volume_pL"] == row["volume_m3"] * 1e15
    evidence(
        name + "-" + policy,
        dict(
            request=request,
            prepared=result.definition,
            provenance=result.provenance,
            independent_comparisons=comparisons,
            initial_inventories_and_charge_exact=True,
        ),
    )


def test_volume_choice_changes_only_cell_volumes_without_rescaling_inventory():
    raw = fixtures.request()
    a = bridge.prepare(raw)
    raw["physics"]["volume_policy"] = "polygon"
    b = bridge.prepare(raw)
    da, db = deepcopy(a.definition), deepcopy(b.definition)
    errors = []
    for x, y in zip(da["model"]["cells"], db["model"]["cells"], strict=True):
        errors.append(abs(x["volume_pL"] / y["volume_pL"] - 1))
        x["volume_pL"] = y["volume_pL"]
    assert da == db and max(errors) > 0.3
    bound = bridge.bind_source(raw["geometry_source"])
    declared = np.asarray([v["volume_pL"] * 1e-15 for v in b.definition["model"]["extracellular"]])
    assert not np.allclose(
        declared, bound.kernel.environment_native_weighted_volume_m3, rtol=1e-8, atol=0
    )
    evidence(
        "volume-choice",
        dict(
            max_relative_cell_volume_difference=max(errors),
            same_inventories_and_charge=True,
            exterior_physical_volumes_separate_from_weights=True,
        ),
    )


def test_stable_ids_allow_permuted_global_membranes_and_physical_tables():
    raw = fixtures.request()
    a = bridge.prepare(raw)
    for key in ("membrane_ids", "partner_membrane_ids", "membrane_environment_ids"):
        raw["geometry_source"]["geometry"][key].reverse()
    for key in ("cells", "extracellular", "membranes"):
        raw["physics"][key].reverse()
    b = bridge.prepare(raw)
    for key in ("cells", "extracellular", "membranes", "junctions", "faces"):
        assert {r["id"]: r for r in a.definition["model"][key]} == {
            r["id"]: r for r in b.definition["model"][key]
        }
    evidence("permuted-owners", dict(stable_physical_owners_and_coefficients_exact=True))


@pytest.mark.parametrize(
    "name", ["irregular-centroid-aux", "translated-scaled-circumcenter", "centroid-core"]
)
def test_complete_generation_specs_physics_and_state_replay(name):
    raw, result = prepared(name)
    assert bridge.replay(result.provenance) == result
    assert result.provenance["request"]["geometry_source"] == raw["geometry_source"]
    evidence("replay-" + name, dict(generation_inputs_rng_specs_and_physics_exact=True))


def test_serialized_definition_provenance_nonoverwrite_and_tampering(tmp_path):
    _, result = prepared()
    path = bridge.write_preparation(tmp_path / "prepared", result)
    assert bridge.read_preparation(path) == result
    with pytest.raises(FileExistsError):
        bridge.write_preparation(path, result)
    raw = json.loads((path / "definition.json").read_text())
    raw["model"]["extracellular"][0]["volume_pL"] *= 1.01
    (path / "definition.json").write_text(json.dumps(raw))
    with pytest.raises(ConfigError):
        bridge.read_preparation(path)
    evidence(
        "serialization", dict(full_payload_roundtrip=True, changed_exterior_volume_refused=True)
    )


FAULTS = (
    "missing-volume-policy",
    "bad-cell-policy",
    "weighted-exterior-policy",
    "missing-capacitance",
    "negative-thickness",
    "missing-diffusivity-species",
    "unknown-membrane",
    "wrong-inside",
    "wrong-outside",
    "missing-exterior",
    "missing-amounts",
    "missing-charge",
    "inconsistent-charge",
    "missing-junction",
    "duplicate-contact",
    "junction-orientation",
    "face-owner",
    "missing-control",
    "state-remap",
    "cut",
    "moving",
    "remap",
    "native-pin",
    "missing-rng",
    "height",
    "generation-link",
    "source-weights",
    "captured-metric",
    "captured-topology",
    "ordinary-id",
)


@pytest.mark.parametrize("fault", FAULTS)
def test_missing_physics_ambiguous_owners_and_noninitial_geometry_are_refused(fault):
    raw = json.loads(json.dumps(fixtures.request()))
    p = raw["physics"]
    s = raw["geometry_source"]
    if fault == "missing-volume-policy":
        p.pop("volume_policy")
    if fault == "bad-cell-policy":
        p["volume_policy"] = "DEC_control_area"
    if fault == "weighted-exterior-policy":
        p["exterior_volume_policy"] = "native_weighted"
    if fault == "missing-capacitance":
        p["membranes"][0].pop("specific_capacitance_F_per_m2")
    if fault == "negative-thickness":
        p["membranes"][0]["thickness_m"] = -5e-9
    if fault == "missing-diffusivity-species":
        p["membranes"][0]["diffusivity_m2_per_s"].pop("Na")
    if fault == "unknown-membrane":
        p["membranes"][0]["id"] = "lost-owner"
    if fault == "wrong-inside":
        p["membranes"][0]["inside"] = "lost-owner"
    if fault == "wrong-outside":
        p["membranes"][0]["outside"] = "lost-owner"
    if fault == "missing-exterior":
        p["extracellular"].pop()
    if fault == "missing-amounts":
        p["cells"][0].pop("initial_amount_fmol")
    if fault == "missing-charge":
        p["cells"][0].pop("initial_charge_C")
    if fault == "inconsistent-charge":
        p["cells"][0]["initial_charge_C"] += 1e-12
    if fault == "missing-junction":
        p["junctions"].pop()
    if fault == "duplicate-contact":
        p["junctions"].append(dict(p["junctions"][0], id="duplicate-contact"))
    if fault == "junction-orientation":
        p["junctions"][0]["sender"], p["junctions"][0]["receiver"] = (
            p["junctions"][0]["receiver"],
            p["junctions"][0]["sender"],
        )
    if fault == "face-owner":
        p["faces"][0]["sender"] = "lost-owner"
    if fault == "missing-control":
        raw["experiment"]["membrane_controls"].pop()
    if fault == "state-remap":
        raw["state"] = {}
    if fault == "cut":
        s["generation"]["mode"] = "cut_epoch@1"
    if fault == "moving":
        s["generation"]["mode"] = "moving_geometry@1"
    if fault == "remap":
        s["generation"]["mode"] = "physical_amount_remap@1"
    if fault == "native-pin":
        s["generation"]["source"]["revision"] = "unknown"
    if fault == "missing-rng":
        s["generation"].pop("rng_after")
    if fault == "height":
        s["geometry"]["height_m"] *= 2
    if fault == "generation-link":
        s["grid"]["provenance"]["generation_identity"] = "0" * 64
    if fault == "source-weights":
        s["mesh"]["dual_control_area_m2"][0] *= 1.5
    if fault == "captured-metric":
        s["mesh"]["dual_points_m"][0][0] += 1e-9
    if fault == "captured-topology":
        s["mesh"]["primal_edges"][0].reverse()
    if fault == "ordinary-id":
        name = p["junctions"][0]["id"]
        p["junctions"][0]["id"] = "unsupported:ordinary:id"
        for row in raw["experiment"]["junction_controls"]:
            if row["junction_id"] == name:
                row["junction_id"] = "unsupported:ordinary:id"
    with pytest.raises(ConfigError):
        bridge.prepare(raw)
    evidence("refused-" + fault, dict(fault=fault, refused=True))


def test_native_preset_with_incompatible_original_cell_ids_requires_new_id_contract():
    raw = fixtures.request("native-single-preset-seed17")
    with pytest.raises(ConfigError, match="IDs require"):
        bridge.prepare(raw)
    evidence("preset-ids-refused", dict(no_implicit_seed_owner_renaming=True))


@pytest.mark.parametrize(
    "fault",
    [
        "binding",
        "initial-state",
        "control-history",
        "inventory",
        "coefficient",
        "source-seed",
        "recipe",
    ],
)
def test_resealed_inconsistent_provenance_is_refused(fault):
    _, result = prepared()
    p = deepcopy(result.provenance)
    if fault == "binding":
        p["geometry_manifest"]["identity"] = "0" * 64
    if fault == "initial-state":
        p["initial_state_sha256"] = "0" * 64
    if fault == "control-history":
        p["control_history_sha256"] = "0" * 64
    if fault == "inventory":
        p["physical_inventory_sha256"] = "0" * 64
    if fault == "coefficient":
        p["request"]["physics"]["membranes"][0]["diffusivity_m2_per_s"]["Na"] *= 1.01
    if fault == "source-seed":
        p["request"]["geometry_source"]["generation"]["constructed_seed_points_m"][0][0] += 1e-8
    if fault == "recipe":
        p["request_sha256"] = "0" * 64
    p.pop("identity")
    p["identity"] = digest(p)
    with pytest.raises(ConfigError):
        bridge.replay(p)
    evidence("replay-refused-" + fault, dict(fault=fault, refused=True))


def test_preparation_preserves_caller_and_process_random_state():
    raw = fixtures.request()
    copy = deepcopy(raw)
    before = np.random.get_state()
    bridge.prepare(raw)
    after = np.random.get_state()
    assert raw == copy
    assert before[0] == after[0] and before[2:] == after[2:]
    np.testing.assert_array_equal(before[1], after[1])
    evidence("purity", dict(request_unchanged=True, no_production_rng_consumption=True))


def test_qualified_geometry_and_physics_equations_and_native_captures_are_unchanged():
    protocol = json.loads(
        (ROOT / "validation/geometry/geometry_tissue_preparation_protocol.json").read_text()
    )
    for relative, expected in protocol["readonly_source_sha256"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected, relative
    prior = protocol["geometry_receipt"]
    assert hashlib.sha256(Path(prior["path"]).read_bytes()).hexdigest() == prior["sha256"]
    folder = Path(os.environ.get("CELLS_GEOMETRY_PREPARATION_NATIVE", str(fixtures.NATIVE)))
    for name, sha in protocol["native_input_sha256"].items():
        assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == sha, name
    for module in (fixtures, reference):
        for node in ast.walk(ast.parse(Path(module.__file__).read_text())):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(("cells", "jax"))
    evidence(
        "provenance",
        dict(
            qualified_geometry_receipt=prior,
            native_capture_hashes=protocol["native_input_sha256"],
            readonly_sources=protocol["readonly_source_sha256"],
            no_shared_source_edits=True,
        ),
    )
