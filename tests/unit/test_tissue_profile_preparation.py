"""Static physical preparation, stable ownership, units and complete replay."""

import ast
import hashlib
import json
import os
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.core import tissue_profile_preparation as bridge
from cells.core.specs import ConfigError, digest, parse_spec
from cells.coupling.selective import selective_flux
from cells.models.registry import get_model
from cells.processes import betse_tissue_profiles as native
from cells.processes.electrochemistry import F, R
from validation.topology import tissue_profile_preparation_fixtures as fixtures
from validation.topology import tissue_profile_preparation_reference as reference

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads(
    (ROOT / "validation/topology/tissue_profile_preparation_protocol.json").read_text()
)


def evidence(name, data):
    if folder := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        path = Path(folder)
        path.mkdir(parents=True, exist_ok=True)
        (path / ("tissue-profile-preparation-" + name + ".json")).write_text(
            json.dumps(
                dict(data, status="passed"), indent=2, allow_nan=False, default=lambda v: v.tolist()
            )
            + "\n"
        )


def build(raw):
    raw = deepcopy(raw)
    data = deepcopy(raw["geometry"])
    layout = data.pop("layout")
    layout["cell_centres_m"] = np.asarray(layout["cell_centres_m"], float)
    layout = native.Layout(**layout)
    identity = native.layout_identity(layout)
    for row in (raw["default"], *raw["profiles"]):
        if (
            row["selector"]["kind"] == "indices"
            and row["selector"]["expected_layout_identity"] is None
        ):
            row["selector"]["expected_layout_identity"] = identity

    def profile(row):
        s = deepcopy(row["selector"])
        if s["kind"] == "image":
            s["value"] = native.Bitmap(np.asarray(s["value"]["grayscale_F"]))
        return native.Profile(
            row["name"], native.Selector(**s), tuple(row["diffusivity_m2_s"]), row["is_gj_insular"]
        )

    return (
        raw,
        bridge.Geometry(layout, **data),
        profile(raw["default"]),
        [profile(r) for r in raw["profiles"]],
    )


def prepare(raw):
    raw, geometry, default, rows = build(raw)
    return raw, bridge.prepare(
        raw["definition"],
        geometry,
        default,
        rows,
        ion_enabled=raw["ion_enabled"],
        enabled=raw["enabled"],
        is_ecm=raw["is_ecm"],
    )


@pytest.mark.parametrize("kind", ["passive", "active"])
@pytest.mark.parametrize("arm", fixtures.ARMS)
def test_independent_component_definition_ownership_and_initial_state(kind, arm):
    raw = fixtures.inputs(kind, arm, permuted=True)
    original = deepcopy(raw)
    actual_input, result = prepare(raw)
    expected = reference.prepare(actual_input)
    canonical = parse_spec(expected["definition"]).to_dict()
    for domain in ("membranes", "junctions"):
        a, b = (
            (r["permeability_m_per_s"] for r in result.definition["model"][domain]),
            (r["permeability_m_per_s"] for r in canonical["model"][domain]),
        )
        for left, right in zip(a, b, strict=True):
            np.testing.assert_allclose(
                list(left.values()), list(right.values()), rtol=5e-14, atol=1e-25
            )
    check = deepcopy(result.definition)
    for domain in ("membranes", "junctions"):
        prior = {r["id"]: r["permeability_m_per_s"] for r in canonical["model"][domain]}
        for row in check["model"][domain]:
            row["permeability_m_per_s"] = prior[row["id"]]
    assert check == canonical
    np.testing.assert_allclose(
        result.provenance["diffusivity_m2_s"],
        expected["profile_result"]["diffusion_m2_s"],
        rtol=5e-14,
        atol=1e-30,
    )
    assert result.provenance["insular_junction_weights"] == expected["insular_junction_weights"]
    names = actual_input["geometry"]["layout"]
    for name, target in expected["profile_result"]["targets"].items():
        current = result.provenance["binding"]["targets"][name]
        for axis, key in (
            ("cell", "cells"),
            ("membrane", "membranes"),
            ("environment", "environments"),
        ):
            assert current[key] == [names[axis + "_ids"][i] for i in target[key]]
    source = parse_spec(raw["definition"])
    after = parse_spec(result.definition)
    before_state, _ = get_model(source.model).initial_values(source)
    after_state, _ = get_model(after.model).initial_values(after)
    for a, b in zip(before_state, after_state, strict=True):
        np.testing.assert_array_equal(a, b)
    assert raw == original
    assert result.provenance["conversion"] == bridge.CONVERSION
    assert result.provenance["binding"]["final_cell_order"] == [
        names["cell_ids"][i] for i in expected["profile_result"]["final_cell_order"]
    ]
    if arm == "disabled":
        assert result.definition == source.to_dict()
    evidence(
        kind + "-" + arm,
        dict(
            inputs=actual_input,
            prepared=result.definition,
            provenance=result.provenance,
            initial_state_exact=True,
            independent_definition=True,
        ),
    )


def test_overlap_blocks_union_and_keeps_actual_intrinsic_gates_schedules():
    raw, result = prepare(fixtures.inputs("active", "overlap"))
    assert all(v == 0 for v in result.provenance["insular_junction_weights"].values())
    source = parse_spec(raw["definition"]).to_dict()
    assert result.definition["experiment"] == source["experiment"]
    for domain in ("cells", "extracellular", "channels", "faces"):
        assert result.definition["model"][domain] == source["model"][domain]
    for a, b in zip(
        result.definition["model"]["junctions"], source["model"]["junctions"], strict=True
    ):
        assert a["gate"] == b["gate"] and a["id"] == b["id"]
    evidence(
        "overlap-union",
        dict(no_reconnection=True, ids_and_intrinsic_gates_and_schedules_exact=True),
    )


def test_selection_uses_stable_owner_ids_without_reordering_the_actual_model():
    a, first = prepare(fixtures.inputs("active", "overlap", permuted=False))
    _, second = prepare(fixtures.inputs("active", "overlap", permuted=True))
    assert first.definition == second.definition
    assert [r["id"] for r in first.definition["model"]["cells"]] == [
        r["id"] for r in a["definition"]["model"]["cells"]
    ]
    evidence("stable-ids", dict(permuted_geometry_same_physical_definition=True))


def test_complete_provenance_replay_roundtrip_and_nonoverwrite(tmp_path):
    _, result = prepare(fixtures.inputs("active", "percent-alias", permuted=True))
    assert bridge.replay(result.provenance) == result
    directory = bridge.write_preparation(tmp_path / "prepared", result)
    assert bridge.read_preparation(directory) == result
    with pytest.raises(FileExistsError):
        bridge.write_preparation(directory, result)
    payload = json.loads((directory / "definition.json").read_text())
    payload["model"]["cells"][0]["initial_amount_fmol"]["Na"] += 1
    (directory / "definition.json").write_text(json.dumps(payload))
    with pytest.raises(ConfigError):
        bridge.read_preparation(directory)
    evidence("replay", dict(complete_recipe=True, nonoverwrite_and_changed_inventory_refused=True))


@pytest.mark.parametrize(
    "field", ["owner", "thickness", "partner", "profile-order", "state", "units"]
)
def test_resealed_inconsistent_provenance_refuses(field):
    _, result = prepare(fixtures.inputs())
    p = deepcopy(result.provenance)
    if field == "owner":
        p["geometry"]["layout"]["membrane_cell_ids"][0] = "cell_2"
    if field == "thickness":
        p["geometry"]["thickness_m"][next(iter(p["geometry"]["thickness_m"]))] *= 2
    if field == "partner":
        p["geometry"]["partner_membrane_ids"].pop(next(iter(p["geometry"]["partner_membrane_ids"])))
    if field == "profile-order":
        p["profile_declarations"]["profiles"].reverse()
    if field == "state":
        p["initial_state_sha256"] = "0" * 64
    if field == "units":
        p["units"]["coefficient_equation"] = "P=D"
    p.pop("identity")
    p["identity"] = digest(p)
    with pytest.raises(ConfigError):
        bridge.replay(p)
    evidence("replay-refused-" + field, dict(field=field, refused=True))


FAULTS = (
    "missing-thickness",
    "zero-thickness",
    "negative-thickness",
    "wrong-unit",
    "rho",
    "missing-provenance",
    "missing-partner",
    "nonreciprocal",
    "missing-edge-map",
    "wrong-edge-owner",
    "duplicate-contact",
    "unknown-neighbor",
    "missing-neighbor",
    "wrong-layout-cell",
    "wrong-layout-exterior",
    "unsupported-ion",
    "missing-ion",
    "wrong-valence",
    "negative-D",
    "stale-indices",
    "unknown-profile-owner",
    "unsupported-model",
)


@pytest.mark.parametrize("fault", FAULTS)
def test_ambiguous_or_nonphysical_binding_refuses(fault):
    raw, geometry, default, rows = build(fixtures.inputs())
    g = deepcopy(geometry)
    if fault == "missing-thickness":
        g.thickness_m.pop(next(iter(g.thickness_m)))
    if fault in ("zero-thickness", "negative-thickness"):
        g.thickness_m[next(iter(g.thickness_m))] = 0.0 if fault == "zero-thickness" else -1e-9
    if fault == "wrong-unit":
        g = replace(g, length_unit="nm")
    if fault == "rho":
        g = replace(g, rho_channel=2.0)
    if fault == "missing-provenance":
        g = replace(g, provenance={})
    if fault == "missing-partner":
        g.partner_membrane_ids.pop(next(iter(g.partner_membrane_ids)))
    if fault == "nonreciprocal":
        g.partner_membrane_ids["membrane_0_shared"] = "membrane_0_shared"
    if fault == "missing-edge-map":
        g.junction_membrane_ids.pop(next(iter(g.junction_membrane_ids)))
    if fault == "wrong-edge-owner":
        g.junction_membrane_ids["junction_0_1"].reverse()
    if fault == "duplicate-contact":
        g.junction_membrane_ids["junction_1_2"] = g.junction_membrane_ids["junction_0_1"]
    if fault == "unknown-neighbor":
        g.cell_neighbor_ids["cell_0"].append("missing")
    if fault == "missing-neighbor":
        g.cell_neighbor_ids["cell_0"] = []
    if fault == "wrong-layout-cell":
        g = replace(
            g,
            layout=replace(g.layout, membrane_cell_ids=["cell_2", *g.layout.membrane_cell_ids[1:]]),
        )
    if fault == "wrong-layout-exterior":
        g = replace(
            g,
            layout=replace(
                g.layout, membrane_environment_ids=["bath", *g.layout.membrane_environment_ids[1:]]
            ),
        )
    if fault == "unsupported-ion":
        raw["ion_enabled"][4] = True
    if fault == "missing-ion":
        raw["ion_enabled"][3] = True
    if fault == "wrong-valence":
        raw["definition"]["model"]["species"][0]["valence"] = 2
    if fault == "negative-D":
        default = replace(default, diffusivity_m2_s=(-1e-18, *default.diffusivity_m2_s[1:]))
    if fault == "stale-indices":
        rows = [replace(rows[0], selector=native.Selector("indices", [0], "bad"))]
    if fault == "unknown-profile-owner":
        rows = [replace(rows[0], selector=native.Selector("ids", ["missing"]))]
    if fault == "unsupported-model":
        raw["definition"]["model"]["id"] = "resolved_calcium_energy@5"
    before = deepcopy(raw["definition"])
    with pytest.raises((ConfigError, ValueError)):
        bridge.prepare(
            raw["definition"],
            g,
            default,
            rows,
            ion_enabled=raw["ion_enabled"],
            enabled=raw["enabled"],
            is_ecm=raw["is_ecm"],
        )
    assert raw["definition"] == before
    evidence("refused-" + fault, dict(fault=fault, source_unchanged=True))


def test_native_units_actual_area_direction_and_independent_decimal_flux():
    folder = os.environ["CELLS_PROFILE_PREPARATION_NATIVE"]
    capture = json.loads((Path(folder) / "result.json").read_text())
    assert (
        capture["status"] == "passed"
        and not capture["cells_imported"]
        and not capture["jax_imported"]
    )
    assert capture["common_constants"] == dict(F_C_mol=F, R_J_mol_K=R)
    rows = []
    for entry in capture["cases"]:
        v = entry["inputs"]
        P = v["D_m2_s"] / v["thickness_m"]
        actual = float(
            selective_flux(
                v["ci_mM"],
                v["co_mM"],
                v["voltage_V"],
                v["valence"],
                v["temperature_K"],
                v["area_m2"],
                P,
                0.0,
                1.0,
                1.0,
                xp=np,
            )
        )
        source = -entry["native_inward_mol_m2_s"] * v["area_m2"] / 1e-15
        expected = reference.outward_flux(
            v["ci_mM"],
            v["co_mM"],
            v["voltage_V"],
            v["valence"],
            v["temperature_K"],
            v["area_m2"],
            v["D_m2_s"],
            v["thickness_m"],
            F,
            R,
        )
        np.testing.assert_allclose(actual, [source, expected], rtol=5e-12, atol=1e-19)
        rows.append(
            dict(
                name=v["name"],
                permeability_m_s=P,
                cells_outward_fmol_s=actual,
                native_converted_outward_fmol_s=source,
                decimal_outward_fmol_s=expected,
            )
        )
    evidence(
        "units",
        dict(
            source_ast_sha256=capture["electroflux_ast_sha256"],
            rows=rows,
            baseline_rho=1.0,
            constants_scope=PROTOCOL["native_units"]["constants_scope"],
        ),
    )


def test_readonly_component_identities_and_independent_reference_imports():
    for name, expected in PROTOCOL["readonly_source_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
    receipt = PROTOCOL["native_component_receipt"]
    assert hashlib.sha256(Path(receipt["path"]).read_bytes()).hexdigest() == receipt["sha256"]
    for module in (fixtures, reference):
        for node in ast.walk(ast.parse(Path(module.__file__).read_text())):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(("cells", "jax"))
    evidence(
        "provenance",
        dict(
            frozen_component=receipt,
            source_hashes=PROTOCOL["readonly_source_sha256"],
            no_shared_or_native_kernel_edits=True,
        ),
    )
