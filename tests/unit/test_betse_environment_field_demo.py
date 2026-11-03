"""Synthetic operator-policy controls; real SVD/native/RNG work stays blocked."""

import ast
import hashlib
import json
import os
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_environment_field as field
from cells.processes import betse_normal_current as current


def declaration(mode=None, *, delta=1.0):
    raw = dict(
        kind=field.INPUT_KIND,
        provenance="Declared one-cell/four-site synthetic software specimen; no native owner",
        is_ecm=True,
        current_definition=dict(
            kind=current.INPUT_KIND,
            provenance="Explicit synthetic membrane/ion axes",
            geometry=dict(
                cell_ids=["cell"],
                membrane_ids=["membrane"],
                owner=[0],
                membrane_area_m2=[1.0],
                cell_area_m2=[1.0],
                normal_xy=[[1.0, 0.0]],
            ),
            ions=dict(ids=["Na", "Cl"], valence=[1.0, -1.0]),
            parameters=dict(F_C_mol=2.0, sharpness_cell=0.5),
        ),
        world=dict(xmin_m=0.0, xmax_m=2 * delta, ymin_m=0.0, ymax_m=2 * delta, grid_size=2),
        geometry=dict(
            cell_centres_m=[[0.5 * delta, 0.5 * delta]],
            membrane_midpoints_m=[[0.5 * delta, 0.5 * delta]],
            cell_volume_m3=[0.25],
        ),
        parameters=dict(
            q_C=1.0,
            kb_J_K=1.0,
            NAv_per_mol=1.0,
            relative_permittivity=1.0,
            vacuum_permittivity_F_m=1.0,
            configured_temperature_K=1.0,
            cell_height_m=0.5,
            cell_space_m=0.1,
            cell_radius_m=0.1,
            true_cell_size_m=0.2,
            magnetic_permeability_H_m=1.0,
        ),
        cache_initial_state=dict(
            cell_mol_m3=[[1.0], [1.0]],
            environment_mol_m3=[[1.0] * 4, [1.0] * 4],
            free_diffusion_m2_s=[1.0, 2.0],
        ),
    )
    if mode is not None:
        raw.update(kind=field.DEMO_INPUT_KIND, flux_operator=mode)
    return raw


@pytest.fixture
def operator(monkeypatch, request):
    """Exact 2x2 rational stand-ins; do not call any decomposition routine."""
    calls, evidence = [], {}
    policy = dict(flux_shift=0.0, bad_dirichlet=False, nonfinite_flux=False, fail_flux=None)
    inverse = (
        np.asarray([[-5, 1, 1, 3], [1, -5, 3, 1], [1, 3, -5, 1], [3, 1, 1, -5]], dtype=np.float64)
        / 16
    )

    def nearest(points, requested, delta, label):
        assert points.shape == (4, 2) and requested.shape == (1, 2)
        np.testing.assert_array_equal(requested[0], points[0])
        return field.frozen([0], np.int64)

    def pinv(matrix, *args, **kwargs):
        assert not args and not kwargs  # Actual source default-call ABI is required.
        is_flux = bool(matrix[0, 0] < 0)
        scale = (-2.0 if is_flux else 1.0) / matrix[0, 0]
        calls.append(dict(flux=is_flux, matrix=matrix.copy(), args=args, kwargs=kwargs))
        if is_flux and policy["fail_flux"] is not None:
            raise policy["fail_flux"]
        returned = (inverse * scale + policy["flux_shift"]) if is_flux else np.eye(4) * scale
        if is_flux and policy["nonfinite_flux"]:
            returned[0, 0] = np.nan
        if not is_flux and policy["bad_dirichlet"]:
            returned[0, 0] += 1
        calls[-1]["returned"] = returned.copy()
        return returned

    monkeypatch.setattr(field, "_nearest", nearest)
    monkeypatch.setattr(np.linalg, "pinv", pinv)
    yield policy, calls, evidence
    if root := os.environ.get("CELLS_FIELD_DEMO_EVIDENCE"):
        folder = Path(root) / hashlib.sha256(request.node.nodeid.encode()).hexdigest()
        folder.mkdir(parents=True, exist_ok=False)
        arrays = {}

        def capture(value):
            if isinstance(value, np.ndarray):
                key = "array_" + str(len(arrays)).zfill(4)
                arrays[key] = value
                return dict(array=key, **current.record(value))
            if isinstance(value, Mapping):
                return {key: capture(item) for key, item in value.items()}
            if isinstance(value, (tuple, list)):
                return [capture(item) for item in value]
            if isinstance(value, BaseException):
                return dict(type=type(value).__name__, message=str(value))
            if type(value) is float:
                return current.record(value)
            return value

        record = capture(
            dict(nodeid=request.node.nodeid, policy=policy, calls=calls, data=evidence)
        )
        with (folder / "arrays.npz").open("xb") as stream:
            np.savez(stream, **arrays)
        (folder / "evidence.json").write_text(json.dumps(record, sort_keys=True, allow_nan=False))


def test_strict_unchanged_geometry_and_record_ast():
    """Remove only the explicit new demo branches; original strict AST must remain."""
    nodes = {
        node.name: node
        for node in ast.parse(Path(field.__file__).read_text()).body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    expected = {
        "_laplacian": "d4fa527eb0462640ec0aad3419119b2d54abacf76d459b6f1900dface6ea5446",
        "_nearest": "34fc79580b9f7ac7b24583f6147d37212a534e8d20fb630319741c59290b5777",
        "gradient": "25f971e623665934912d2769ba602c72e146185ff5b13045dfde895beaab79b3",
        "source_diff": "020811a510daccf24bdd75d3f9ce4ea34bcf747279257dbc31fe77fa64c4c986",
        "_hodge": "c203cb9e3046b1a97a0b079e4132ff4f30176623d658aa272eaa6c9f40357dbb",
        "_packet": "931494e14acaa7f01d42db8ebb81505b8f35484d9bbb90fea6e2b87a91fdb992",
        "Binding": "b522cee284919319ae9f280a29c5ee0df8481e9866481b099babd876ebfdcb86",
        "Geometry": "a3931a460b77fad250c3ff62cddcdc6ab59fbef55fdc67dea7ca7e6e83c82934",
        "_geometry": "5f92f3a73c1592090b94a1aea1f6eee7b0bf2e31eb02a2cbc67e20da9a0283d5",
        "binding_record": "36e713cb68b8f20aa5564cea85c3912079af0057d4bcc46ec68ae0f651ece4ca",
        "_bind": "94ea267d82522e4d94741318269fa7bc4b983807239fc8602997ab36088bbfc1",
        "readout_record": "27c71b0d17c9304c132cdc2c2d44e2e4314a0989947a22bb2e3a70efd5674798",
        "evaluate": "b347c39806802ff03763256cb1cc4cf59c275a6664c0bd04336b430055ccafae",
        "voltage_dependencies": "62f998687beb98ad7ddc68ac14720f79f5f2567c8f0a132e3b59eaccd8971174",
    }
    for name in ("_geometry", "binding_record"):
        node = nodes[name]
        branches = [
            item
            for item in node.body
            if isinstance(item, ast.If) and "DEMO_INPUT_KIND" in ast.unparse(item.test)
        ]
        assert len(branches) == 1
        node.body.remove(branches[0])
    shared = nodes["_bind"]
    shared.name = "bind"
    shared.args.kwonlyargs, shared.args.kw_defaults = [], []
    checked = shared.body[1].body
    declaration_check = checked[0].test.values
    declaration_check[1].comparators[0] = declaration_check[1].comparators[0].left
    declaration_check[2].comparators[0] = declaration_check[2].comparators[0].orelse
    assert isinstance(checked[1], ast.If) and "demo" in ast.unparse(checked[1].test)
    checked.pop(1)
    for name in ("readout_record", "voltage_dependencies"):
        laws = [
            item
            for item in ast.walk(nodes[name])
            if isinstance(item, ast.keyword) and item.arg == "law"
        ]
        assert len(laws) == 1 and isinstance(laws[0].value, ast.IfExp)
        laws[0].value = laws[0].value.orelse
    body = nodes["evaluate"].body[1].body
    branches = [
        item
        for item in body
        if isinstance(item, ast.If) and "DEMO_INPUT_KIND" in ast.unparse(item.test)
    ]
    assert len(branches) == 1
    body.remove(branches[0])
    prepared = [
        item
        for item in ast.walk(nodes["evaluate"])
        if isinstance(item, ast.keyword) and item.arg == "neumann_pseudoinverse_prepared_but_unused"
    ]
    assert len(prepared) == 1
    prepared[0].value = ast.Constant(value=True)
    for name, digest in expected.items():
        assert (
            hashlib.sha256(ast.dump(nodes[name], include_attributes=False).encode()).hexdigest()
            == digest
        )
    assert field.INPUT_KIND == "cells.betse_environment_field_inputs@1"
    assert field.LAW_ID == "betse_environment_field_source_v1_5_0@1"
    assert field.OPERATOR_RESIDUAL_LIMIT == 1e-10 and field.MAX_GRID_POINTS == 49


def test_strict_identity_and_default_pinv_are_retained(operator):
    _, calls, saved = operator
    raw = declaration(delta=0.25)
    before = deepcopy(raw)
    binding = field.bind(raw)
    assert raw == before and binding.definition == raw
    assert [call["flux"] for call in calls] == [False, True]
    np.testing.assert_array_equal(calls[0]["matrix"], np.eye(4) * 16)
    assert binding.identity == current._digest(field.binding_record(binding))
    assert field.binding_record(binding)["law"] == field.LAW_ID
    assert "flux_operator" not in field.binding_record(binding)
    assert field.validate_binding(binding) is binding
    saved.update(definition=raw, identity=binding.identity, geometry=binding.geometry._asdict())


def test_known_bad_flux_is_retained_without_repair_only_in_demo(operator):
    policy, calls, saved = operator
    policy["flux_shift"] = 8.0
    with pytest.raises(field.EnvironmentFieldRejected, match="gauge residual") as caught:
        field.bind(declaration())
    assert caught.value.stage == "operators"
    binding = field.bind_demo(declaration("original"))
    diagnostics = binding.geometry.diagnostics
    assert diagnostics["neumann_diagnostics_passed"] is False
    assert "neumann_zero_mean_gauge" in diagnostics["neumann_diagnostic_failures"]
    assert diagnostics["operator_acceptance"] is diagnostics["scientific_acceptance"] is False
    np.testing.assert_array_equal(binding.geometry.neumann_inverse_m2, calls[-1]["returned"])
    assert np.any(binding.geometry.neumann_inverse_m2.sum(axis=0) != 0)
    assert field.validate_binding(binding) is binding
    saved.update(strict_failure=dict(caught.value.trial), geometry=binding.geometry._asdict())


def test_disabled_never_constructs_or_delegates_flux(monkeypatch, operator):
    _, calls, saved = operator
    original = field._laplacian

    def value_only(shape, delta, *, flux):
        assert flux is False
        return original(shape, delta, flux=flux)

    monkeypatch.setattr(field, "_laplacian", value_only)
    binding = field.bind_demo(declaration("disabled"))
    assert field.validate_binding(binding) is binding
    assert all(not call["flux"] for call in calls) and len(calls) == 2
    assert binding.geometry.neumann_laplacian_per_m2 is None
    assert binding.geometry.neumann_inverse_m2 is None
    assert binding.geometry.diagnostics["neumann_diagnostics_passed"] is None
    saved.update(geometry=binding.geometry._asdict(), identity=binding.identity)


@pytest.mark.parametrize("mode", ("original", "disabled"))
def test_demo_is_explicit_and_cannot_enter_strict_bind(mode, operator):
    with pytest.raises(field.EnvironmentFieldRejected, match="declaration"):
        field.bind(declaration(mode))
    with pytest.raises(field.EnvironmentFieldRejected, match="declaration"):
        field.bind_demo(declaration())


@pytest.mark.parametrize("mode", (None, True, 0, "repair", "compatible_gauge"))
def test_demo_mode_refuses_missing_or_foreign_policy(mode, operator):
    raw = declaration("original")
    if mode is None:
        del raw["flux_operator"]
    else:
        raw["flux_operator"] = mode
    with pytest.raises(field.EnvironmentFieldRejected):
        field.bind_demo(raw)
    assert operator[1] == []


def test_demo_does_not_disable_ecm_or_weaken_dirichlet(operator):
    policy, _, saved = operator
    raw = declaration("disabled")
    raw["is_ecm"] = False
    with pytest.raises(field.EnvironmentFieldRejected, match="ECM on"):
        field.bind_demo(raw)
    policy["bad_dirichlet"] = True
    with pytest.raises(field.EnvironmentFieldRejected, match="Dirichlet") as caught:
        field.bind_demo(declaration("original"))
    assert caught.value.trial["dirichlet_inverse_m2"] is not None
    assert caught.value.trial["neumann_inverse_m2"] is not None
    saved.update(trial=dict(caught.value.trial))


def test_original_flux_failure_retains_primary_and_previous_buffers(operator):
    policy, _, saved = operator
    original = RuntimeError("synthetic flux pinv failure")
    policy["fail_flux"] = original
    with pytest.raises(field.EnvironmentFieldRejected) as caught:
        field.bind_demo(declaration("original"))
    assert caught.value.__cause__ is original
    assert caught.value.trial["dirichlet_inverse_m2"] is not None
    assert caught.value.trial["neumann_laplacian_per_m2"] is not None
    assert caught.value.trial["neumann_inverse_m2"] is None
    saved.update(trial=dict(caught.value.trial), primary=original)


def test_nonfinite_flux_is_retained_but_refused(operator):
    operator[0]["nonfinite_flux"] = True
    with pytest.raises(field.EnvironmentFieldRejected, match="Nonfinite unused") as caught:
        field.bind_demo(declaration("original"))
    assert np.isnan(caught.value.trial["neumann_inverse_m2"][0, 0])
    operator[2].update(trial=dict(caught.value.trial))


@pytest.mark.parametrize("mutation", ("bits", "mode", "present_when_disabled"))
def test_revalidation_refuses_changed_operator_bits_or_mode(mutation, operator):
    binding = field.bind_demo(
        declaration("disabled" if mutation == "present_when_disabled" else "original")
    )
    geometry = binding.geometry
    if mutation == "bits":
        altered = geometry.neumann_inverse_m2.copy()
        altered.view(np.uint64)[0, 0] ^= np.uint64(1)
        geometry = geometry._replace(neumann_inverse_m2=field.frozen(altered))
        binding = replace(binding, geometry=geometry)
    elif mutation == "present_when_disabled":
        binding = replace(
            binding, geometry=geometry._replace(neumann_inverse_m2=field.frozen(np.zeros((4, 4))))
        )
    else:
        raw = binding.definition
        raw["flux_operator"] = "disabled"
        binding = replace(
            binding, definition_json=json.dumps(raw, sort_keys=True, separators=(",", ":"))
        )
    binding = replace(binding, identity=current._digest(field.binding_record(binding)))
    with pytest.raises(ValueError, match="Derived geometry"):
        field.validate_binding(binding)


def test_modes_have_distinct_persisted_fingerprints_and_immutable_buffers(operator):
    original = field.bind_demo(declaration("original"))
    disabled = field.bind_demo(declaration("disabled"))
    strict = field.bind(declaration())
    assert len({original.identity, disabled.identity, strict.identity}) == 3
    for binding in (original, disabled):
        roundtrip = field.bind_demo(json.loads(binding.definition_json))
        assert roundtrip.identity == binding.identity
        assert field.binding_record(binding)["law"] == field.DEMO_LAW_ID
        for value in binding.geometry:
            if isinstance(value, np.ndarray):
                assert not value.flags.writeable
                with pytest.raises(ValueError):
                    value.setflags(write=True)
    operator[2].update(identities=[strict.identity, original.identity, disabled.identity])


def test_selected_field_path_preserves_currents_and_reports_mode(monkeypatch, operator):
    # Pure deterministic smoothing stand-in; this checks composition/policy,
    # not SciPy/Gaussian or native numerical correspondence.
    monkeypatch.setattr(field, "gaussian_filter", lambda a, *args, **kwargs: a.copy())
    results = []
    retained = operator[2].setdefault("returned_modes", [])
    for mode in (None, "original", "disabled"):
        operator[0]["flux_shift"] = 0.0 if mode is None else 8.0
        binding = field.bind(declaration()) if mode is None else field.bind_demo(declaration(mode))
        source = current.inputs(
            binding.current_binding, [[1.0], [1.0]], [[0.1], [-0.2]], [[0.3], [0.4]], [0.0], [0.0]
        )
        prefix = current.evaluate(binding.current_binding, source)
        row = dict(mode=mode, current=field.readout_current_record(prefix))
        retained.append(row)
        packet = dict(
            old_voltage_V=[0.0],
            boundary_V=dict.fromkeys(("R", "L", "T", "B"), 0.0),
            environment_mol_m3=[[1.0] * 4, [1.0] * 4],
            environment_flux_x=[[0.1] * 4, [-0.2] * 4],
            environment_flux_y=[[0.3] * 4, [0.4] * 4],
            extra_environment_current_xy=[[0.0, 0.0]] * 4,
            extra_environment_charge_C_m3=[0.0] * 4,
        )
        result = field.evaluate(binding, prefix, packet)
        row["field"] = field.readout_record(result)
        assert result.source_current is prefix and result.diagnostics["finite"]
        assert result.diagnostics["neumann_pseudoinverse_prepared_but_unused"] == (
            mode != "disabled"
        )
        if mode is not None:
            assert result.diagnostics["flux_operator"] == mode
            assert result.diagnostics["flux_operator_used"] is False
            assert field.readout_record(result)["law"] == field.DEMO_LAW_ID
            assert (
                json.loads(field.voltage_dependencies(binding)["operator_provenance"])["law"]
                == field.DEMO_LAW_ID
            )
        results.append(result)
    for result in results[1:]:
        assert current.record(result.values) == current.record(results[0].values)
        assert current.record(
            field.readout_current_record(result.source_current)
        ) == current.record(field.readout_current_record(results[0].source_current))
    operator[2].update(values=[result.values._asdict() for result in results])
