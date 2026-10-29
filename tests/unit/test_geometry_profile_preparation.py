"""Independent owner/selector/physical comparisons for joined frozen adapters."""

import ast
import hashlib
import json
import os
import subprocess
import sys
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from cells.core import geometry_profile_preparation as bridge
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, digest, parse_spec
from cells.models import surface_tissue as model
from cells.processes import betse_tissue_profiles as native
from validation.geometry import geometry_profile_preparation_fixtures as fixtures
from validation.geometry import geometry_profile_preparation_reference as reference
from validation.tissue import surface_dynamics_reference as equations
from validation.topology import betse_tissue_profiles_reference as selectors

ROOT = Path(__file__).resolve().parents[2]


def evidence(name, value):
    if folder := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        path = Path(folder)
        path.mkdir(parents=True, exist_ok=True)
        (path / ("geometry-profiles-" + name + ".json")).write_text(
            json.dumps(
                dict(value, status="passed"),
                indent=2,
                allow_nan=False,
                default=lambda v: v.tolist(),
            )
            + "\n"
        )


@lru_cache
def prepared(case="overlap"):
    raw = fixtures.request(case)
    return raw, bridge.prepare(raw)


@pytest.mark.parametrize("case", fixtures.CASES)
def test_independent_layout_selection_and_complete_before_after_physics(case):
    raw, result = prepared(case)
    expected = reference.prepare(raw)
    target = parse_spec(expected["definition"]).to_dict()
    observed = deepcopy(result.definition)
    for domain in ("membranes", "junctions"):
        for a, b in zip(observed["model"][domain], target["model"][domain], strict=True):
            np.testing.assert_allclose(
                list(a["permeability_m_per_s"].values()),
                list(b["permeability_m_per_s"].values()),
                rtol=5e-14,
                atol=1e-25,
            )
            a["permeability_m_per_s"] = b["permeability_m_per_s"]
    assert observed == target
    geometry = reference.derive_geometry(raw)
    layout = geometry["layout"]
    actual = result.provenance["profile_preparation"]
    for name, row in expected["profile_result"]["targets"].items():
        for domain, axis in (
            ("cells", "cell_ids"),
            ("membranes", "membrane_ids"),
            ("environments", "environment_ids"),
        ):
            assert actual["binding"]["targets"][name][domain] == [
                layout[axis][i] for i in row[domain]
            ]
    assert actual["insular_junction_weights"] == expected["insular_junction_weights"]
    records = []
    before_state = None
    for stage, definition, independent in (
        (
            "before",
            raw["geometry_preparation"]["definition"],
            raw["geometry_preparation"]["definition"],
        ),
        ("after", result.definition, target),
    ):
        spec = parse_spec(definition)
        state, p = model.initial_values(spec)
        c = equations.bind(independent)
        np.testing.assert_array_equal(equations.flatten(c, state._asdict()), equations.initial(c))
        if before_state is None:
            before_state = state
        else:
            for a, b in zip(state, before_state, strict=True):
                assert np.asarray(a).dtype == np.asarray(b).dtype
                np.testing.assert_array_equal(a, b)
        for time in (0.0, 5e-6):
            table = control_values(spec, [time])
            u = type(table)(*(v[0] for v in table))
            slope = model.rhs(state, u, p, p.active, xp=np)
            flat = equations.flatten(c, slope._asdict())
            expected_slope, phi, proof = equations.evaluate(c, equations.initial(c), time)
            budget = equations.flatten(
                c,
                {
                    key: np.full(shape, 3e-23 if key.endswith("_C") else 3e-12)
                    for key, shape in c["shapes"].items()
                },
            ) + 3e-10 * np.abs(expected_slope)
            ratio = float(np.max(np.abs(flat - expected_slope) / budget, initial=0))
            assert ratio <= 1, ratio
            field = model.field_values(state, u, p, xp=np)
            n = p.active.size
            potential = np.r_[
                field.potential_V[:n][p.active], field.potential_V[n:][p.outside_active]
            ]
            np.testing.assert_allclose(potential, phi, rtol=3e-10, atol=3e-13)
            assert bool(field.converged) and abs(field.energy_balance_pJ_s) < 1e-10
            mass = (
                slope.amount_increment.sum(axis=1)
                + slope.extracellular_amount_increment.sum(axis=1)
                - slope.reservoir_supplied.sum(axis=1)
            )
            np.testing.assert_allclose(mass, 0, rtol=0, atol=3e-14)
            records.append(
                dict(
                    stage=stage,
                    time_s=time,
                    error_over_budget=ratio,
                    independent_proof=proof,
                    physical_energy_balance_pJ_s=float(field.energy_balance_pJ_s),
                    material_residual_fmol_s=mass,
                    potential_V=potential,
                )
            )
    source = raw["geometry_preparation"]
    for key in ("species", "cells", "extracellular", "faces"):
        assert result.definition["model"][key] == source["definition"]["model"][key]
    assert result.definition["experiment"] == source["definition"]["experiment"]
    assert result.definition["execution"] == source["definition"]["execution"]
    assert result.provenance["initial_state_sha256"] == source["provenance"]["initial_state_sha256"]
    evidence(
        "physical-" + case,
        dict(
            request=raw,
            prepared=result.definition,
            provenance=result.provenance,
            independent_comparisons=records,
            inventory_state_controls_exact=True,
        ),
    )


def test_derived_geometry_uses_centroids_explicit_thickness_and_contacts():
    raw, _ = prepared()
    view = bridge.derive_geometry(raw["geometry_preparation"])
    expected = reference.derive_geometry(raw)
    actual = view.layout
    np.testing.assert_allclose(
        actual.cell_centres_m, expected["layout"]["cell_centres_m"], rtol=6e-12, atol=1e-27
    )
    seeds = raw["geometry_preparation"]["provenance"]["request"]["geometry_source"]["mesh"][
        "primal_points_m"
    ]
    assert np.max(np.abs(np.asarray(actual.cell_centres_m) - seeds)) > 1e-7
    assert actual.seed_fills is None
    for key in (
        "thickness_m",
        "partner_membrane_ids",
        "junction_membrane_ids",
        "cell_neighbor_ids",
    ):
        assert getattr(view, key) == expected[key]
    evidence(
        "derived-geometry",
        dict(
            centroids_distinct_from_seeds=True,
            seed_fills=None,
            physical_thickness_and_reciprocal_maps_exact=True,
        ),
    )


def test_image_selection_distinguishes_centroids_from_primal_seed_points():
    raw, result = prepared("image-centroids")
    layout = reference.derive_geometry(raw)["layout"]
    image = dict(bitmap=raw["profiles"][0]["selector"]["value"]["grayscale_F"])
    a = selectors.image_values(image, layout)
    other = deepcopy(layout)
    other["cell_centres_m"] = raw["geometry_preparation"]["provenance"]["request"][
        "geometry_source"
    ]["mesh"]["primal_points_m"]
    b = selectors.image_values(image, other)

    def picked(values):
        return [cid for cid, v in zip(layout["cell_ids"], values, strict=True) if v != 0]

    assert picked(a) != picked(b)
    assert result.provenance["profile_preparation"]["binding"]["targets"]["CentroidPixel"][
        "cells"
    ] == picked(a)
    evidence(
        "centroid-image-control",
        dict(actual_centroid_targets=picked(a), incorrect_seed_point_targets=picked(b)),
    )


def test_percentage_all_alias_and_duplicate_occurrence_order():
    raw, result = prepared("percent-alias")
    g = reference.derive_geometry(raw)["layout"]
    targets = result.provenance["profile_preparation"]["binding"]["targets"]
    original = [m for group in g["cell_membrane_ids"] for m in group]
    reversed_mems = [m for group in reversed(g["cell_membrane_ids"]) for m in group]
    assert targets["Default"]["cells"] == list(reversed(g["cell_ids"]))
    assert targets["Before"]["membranes"] == original
    assert targets["After"]["membranes"] == reversed_mems
    _, overlap = prepared()
    picked = overlap.provenance["profile_preparation"]["binding"]["targets"]["Region"]["cells"]
    assert picked[0] == picked[2]
    evidence(
        "selection-order",
        dict(
            all_alias_cells_and_pick_time_membrane_order_preserved=True,
            duplicate_cell_occurrences_preserved=True,
        ),
    )


def test_explicit_index_selector_uses_derived_layout_identity():
    raw = fixtures.request()
    view = bridge.derive_geometry(raw["geometry_preparation"])
    raw["profiles"] = [
        fixtures.profile(
            "Indices",
            fixtures.selector("indices", [2, 0, 2], identity=native.layout_identity(view.layout)),
            4,
            True,
        )
    ]
    result = bridge.prepare(raw)
    assert result.provenance["profile_preparation"]["binding"]["targets"]["Indices"]["cells"] == [
        view.layout.cell_ids[i] for i in (2, 0, 2)
    ]
    evidence(
        "indices", dict(explicit_derived_layout_identity=True, duplicates_and_order_preserved=True)
    )


@pytest.mark.parametrize("case", ["overlap", "percent-alias", "image-centroids"])
def test_full_two_chain_replay(case):
    raw, result = prepared(case)
    assert bridge.replay(result.provenance) == result
    assert result.provenance["request"]["geometry_preparation"] == raw["geometry_preparation"]
    evidence("replay-" + case, dict(full_geometry_and_profile_provenance_retained=True))


def test_serialization_and_fresh_portable_replay(tmp_path):
    _, result = prepared()
    folder = bridge.write_preparation(tmp_path / "prepared", result)
    assert bridge.read_preparation(folder) == result
    with pytest.raises(FileExistsError):
        bridge.write_preparation(folder, result)
    script = """
import json,sys
def audit(event,args):
    if event=='open' and isinstance(args[0],str):
        prefixes=('/mnt/workspaces/Cells/betse-geometry-',
                  '/mnt/workspaces/Cells/geometry-tissue-preparation-')
        if args[0].startswith(prefixes):
            raise RuntimeError('External geometry evidence read during portable replay')
sys.addaudithook(audit)
from cells.core import geometry_profile_preparation as b
result=b.replay(b.read_json(sys.argv[1]));b.write_preparation(sys.argv[2],result)
print(json.dumps(dict(identity=result.provenance['identity'])))
"""
    output = tmp_path / "replayed"
    env = os.environ.copy()
    env.pop("CELLS_GEOMETRY_PROFILE_REFERENCE", None)
    child = subprocess.run(
        [sys.executable, "-B", "-c", script, str(folder / "provenance.json"), str(output)],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert child.returncode == 0, child.stderr
    assert bridge.read_preparation(output) == result
    data = bridge.read_json(output / "definition.json")
    data["schema_version"] = True
    (output / "definition.json").write_text(json.dumps(data))
    with pytest.raises(ConfigError):
        bridge.read_preparation(output)
    evidence(
        "portable-replay",
        dict(
            stdout=child.stdout,
            stderr=child.stderr,
            external_geometry_reads_blocked=True,
            typed_definition_tamper_refused=True,
        ),
    )


FAULTS = (
    "definition-type",
    "artifact-identity",
    "layout-override",
    "no-colors",
    "incomplete-colors",
    "missing-permutation",
    "partial-permutation",
    "unknown-owner",
    "missing-index-identity",
    "stale-index-identity",
    "extra-profile-field",
    "unsupported-ion",
    "missing-thickness",
    "cut-kind",
    "degenerate-image",
)


@pytest.mark.parametrize("fault", FAULTS)
def test_refuse_unsupported_sources_or_implicit_selection_metadata(fault):
    raw = fixtures.request()
    ids = raw["geometry_preparation"]["definition"]["model"]["cells"]
    if fault == "definition-type":
        raw["geometry_preparation"]["definition"]["schema_version"] = True
    if fault == "artifact-identity":
        raw["geometry_preparation"]["provenance"]["identity"] = "0" * 64
    if fault == "layout-override":
        raw["layout"] = {}
    if fault == "no-colors":
        raw["profiles"] = [fixtures.profile("Color", fixtures.selector("color", "red"))]
    if fault == "incomplete-colors":
        raw["seed_fills"] = {ids[0]["id"]: "red"}
    if fault == "missing-permutation":
        raw["profiles"] = [fixtures.profile("P", fixtures.selector("percent", 50))]
    if fault == "partial-permutation":
        raw["profiles"] = [
            fixtures.profile("P", fixtures.selector("percent", 50, permutation=[ids[0]["id"]]))
        ]
    if fault == "unknown-owner":
        raw["profiles"][0]["selector"]["value"] = ["unknown"]
    if fault == "missing-index-identity":
        raw["profiles"] = [fixtures.profile("I", fixtures.selector("indices", [0]))]
    if fault == "stale-index-identity":
        raw["profiles"] = [
            fixtures.profile("I", fixtures.selector("indices", [0], identity="0" * 64))
        ]
    if fault == "extra-profile-field":
        raw["profiles"][0]["infer_colors"] = True
    if fault == "unsupported-ion":
        raw["ion_enabled"][4] = True
    if fault == "missing-thickness":
        raw["geometry_preparation"]["provenance"]["request"]["physics"]["membranes"][0].pop(
            "thickness_m"
        )
    if fault == "cut-kind":
        raw["kind"] = "cells.cut_geometry_profiles@1"
    if fault == "degenerate-image":
        bitmap = [[255.0] * 4 for _ in range(4)]
        bitmap[0][0] = 0.0
        raw["profiles"] = [
            fixtures.profile("BadImage", fixtures.selector("image", dict(grayscale_F=bitmap)))
        ]
    with pytest.raises(ConfigError):
        bridge.prepare(raw)
    evidence("refused-" + fault, dict(fault=fault, refused=True))


@pytest.mark.parametrize(
    "fault",
    [
        "geometry-link",
        "profile-link",
        "thickness",
        "seed-centres",
        "state",
        "inventory",
        "controls",
        "profile-order",
    ],
)
def test_resealed_inconsistent_provenance_refuses(fault):
    _, result = prepared()
    p = deepcopy(result.provenance)
    if fault == "geometry-link":
        p["geometry_preparation_identity"] = "0" * 64
    if fault == "profile-link":
        p["profile_preparation_identity"] = "0" * 64
    if fault == "thickness":
        p["profile_preparation"]["geometry"]["thickness_m"][
            next(iter(p["profile_preparation"]["geometry"]["thickness_m"]))
        ] *= 2
    if fault == "seed-centres":
        p["profile_preparation"]["geometry"]["layout"]["cell_centres_m"] = p["request"][
            "geometry_preparation"
        ]["provenance"]["request"]["geometry_source"]["mesh"]["primal_points_m"]
    if fault == "state":
        p["initial_state_sha256"] = "0" * 64
    if fault == "inventory":
        p["physical_inventory_sha256"] = "0" * 64
    if fault == "controls":
        p["control_history_sha256"] = "0" * 64
    if fault == "profile-order":
        p["request"]["profiles"].reverse()
    p.pop("identity")
    p["identity"] = digest(p)
    with pytest.raises(ConfigError):
        bridge.replay(p)
    evidence("replay-refused-" + fault, dict(fault=fault, refused=True))


@pytest.mark.parametrize("text", ['{"a":1,"a":1}', '{"v":NaN}', '{"v":1e999}'])
def test_strict_portable_json(text, tmp_path):
    p = tmp_path / "input.json"
    p.write_text(text)
    with pytest.raises(ConfigError):
        bridge.read_json(p)
    evidence(
        "json-" + hashlib.sha256(text.encode()).hexdigest()[:8], dict(input=text, refused=True)
    )


def test_frozen_components_example_and_reference_independence():
    contract = json.loads(
        (ROOT / "validation/geometry/geometry_profile_preparation_protocol.json").read_text()
    )
    for name, sha in contract["readonly_source_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha, name
    for receipt in contract["component_receipts"].values():
        assert hashlib.sha256(Path(receipt["path"]).read_bytes()).hexdigest() == receipt["sha256"]
    for module in (fixtures, reference):
        for node in ast.walk(ast.parse(Path(module.__file__).read_text())):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(("cells", "jax"))
    example = bridge.read_json(ROOT / contract["repository_example"])
    assert example == fixtures.request("overlap")
    evidence(
        "provenance",
        dict(
            component_receipts=contract["component_receipts"],
            readonly_sources=contract["readonly_source_sha256"],
            reference_has_no_production_imports=True,
            example_exact=True,
        ),
    )


def test_explicit_permutations_preserve_request_and_process_rng():
    raw = fixtures.request("percent-alias")
    before = deepcopy(raw)
    rng = np.random.get_state()
    bridge.prepare(raw)
    after = np.random.get_state()
    assert raw == before
    assert rng[0] == after[0] and rng[2:] == after[2:]
    np.testing.assert_array_equal(rng[1], after[1])
    evidence("purity", dict(request_preserved=True, no_rng_or_permutation_invention=True))
