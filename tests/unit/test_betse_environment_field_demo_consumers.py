"""Synthetic policy propagation; no completed phase or native owner is fabricated.

Transport/field bindings are real immutable records. The large lifecycle/grid
modules are read as literal function ASTs in explicitly supplied metadata
namespaces. Their whole-source baseline checks and call-site controls prevent
an isolated predicate from standing in for unwired production code. The codec
uses its unchanged implementation with only the existing relevant record
classes; the checkpoint check is its literal binding-seal predicate, not a
successful full run-checkpoint load or phase admission.
"""

import ast
import hashlib
import json
import math
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import fields, is_dataclass, replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import test_betse_environment_field_demo as specimen

from cells.core.specs import digest
from cells.processes import betse_ecm_transport as material
from cells.processes import betse_environment_field as field
from cells.processes import betse_normal_current as current

operator = specimen.operator
ROOT = Path(__file__).resolve().parents[2]
PROCESS = ROOT / "src/cells/processes"
BASE_AST = {
    "betse_ecm_transport": "c092d7f20fb4afbd1422c1218a27f929106826eb2c230169d822acc1de98e289",
    "betse_ecm_sim_grn": "980d21b982e440e29b70a0ea4b02b718d2bb4403780cb9c98502c9c0d0bd5ea0",
    "betse_normal_ecm_molecule_lifecycle": (
        "a7c8ba7f1624f5f83283ed1bcbdc9577d5c5d74915e38b25568d5a15cd0898f2"
    ),
    "betse_normal_ecm_initialization": (
        "24b492cc0a6d329166037eeccb0d2c6292cdf0a3f354b0e77ef4dc571999caf0"
    ),
}


def declaration(mode=None):
    return dict(
        kind=material.INPUT_KIND,
        provenance="Declared synthetic transport axes; no acquired phase authority",
        environment_geometry_definition=specimen.declaration(mode),
        junction_geometry=dict(partner=[0], boundary=[True], gap_length_m=[1.0], gap_weights=[1.0]),
        ions=dict(
            moving_ids=["Na", "Cl"],
            membrane_diffusion_m2_s=[[1.0], [2.0]],
            gap_diffusion_m2_s=[[3.0], [4.0]],
            environment_diffusion_m2_s=[[5.0] * 4, [6.0] * 4],
            tight_junction_modulator=[[1.0] * 4, [1.0] * 4],
        ),
        parameters=dict(
            R_J_mol_K=1.0,
            membrane_thickness_m=1.0,
            gap_surface_fraction=1.0,
            cluster_open=False,
            fast_update_ecm=True,
            sharpness=0.5,
            fluid_flow=False,
            v_sensitive_gj=False,
        ),
    )


def nodes(name):
    path = PROCESS / (name + ".py")
    return path, ast.parse(path.read_text())


def literal(name, selected, namespace):
    path, tree = nodes(name)
    body = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in selected]
    assert {n.name for n in body} == set(selected)
    scope = dict(__name__="_field_demo_consumer_literals", __file__=str(path), **namespace)
    exec(compile(ast.Module(body=body, type_ignores=[]), str(path), "exec"), scope)
    return SimpleNamespace(**scope)


@pytest.mark.parametrize("name", tuple(BASE_AST))
def test_original_source_ast_survives_narrow_policy_additions(name):
    _, tree = nodes(name)
    by_name = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    if name == "betse_ecm_transport":
        constants = [
            n
            for n in tree.body
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "DEMO_LAW_ID" for t in n.targets)
        ]
        assert len(constants) == 1
        tree.body.remove(constants[0])
        branch = by_name["binding_record"].body.pop(0)
        assert isinstance(branch, ast.If) and "DEMO_INPUT_KIND" in ast.unparse(branch.test)
        body = by_name["bind"].body
        branches = [
            n for n in body if isinstance(n, ast.If) and "DEMO_INPUT_KIND" in ast.unparse(n.test)
        ]
        assert len(branches) == 1
        branch = branches[0]
        body[body.index(branch) : body.index(branch) + 1] = branch.orelse
    elif name == "betse_ecm_sim_grn":
        body = by_name["build_grid"].body
        branch = body[0]
        assert isinstance(branch, ast.If) and "DEMO_INPUT_KIND" in ast.unparse(branch.test)
        body[0:1] = branch.orelse
    elif name == "betse_normal_ecm_molecule_lifecycle":
        tree.body.remove(by_name["_check_environment_policy"])
        body = by_name["check_owners"].body
        added = [
            n
            for n in body
            if isinstance(n, ast.Expr) and ast.unparse(n) == "_check_environment_policy(old, new)"
        ]
        assert len(added) == 1
        body.remove(added[0])
    else:
        tree.body.remove(by_name["_same_flux_operator"])
        loops = [
            n
            for n in by_name["_check_owners"].body
            if isinstance(n, ast.For) and ast.unparse(n.iter) == "cell_pairs.items()"
        ]
        assert len(loops) == 1 and len(loops[0].body) == 1
        branch = loops[0].body[0]
        assert isinstance(branch, ast.If) and ast.unparse(branch.test) == "key == 'lapENV_P_inv'"
        assert ast.unparse(branch.body[0]) == "_same_flux_operator(c(key), gb)"
        loops[0].body = branch.orelse
    assert (
        hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest()
        == BASE_AST[name]
    )


@pytest.mark.parametrize("mode", [None, "original", "disabled"])
def test_real_transport_binding_revalidation_preserves_all_transport_axes(mode, operator):
    policy, calls, saved = operator
    policy["flux_shift"] = 0.0 if mode is None else 8.0
    raw = declaration(mode)
    before = deepcopy(raw)
    bound = material.bind(raw)
    saved.update(definition=raw, record=material.binding_record(bound))
    assert type(bound) is material.Binding and raw == before and bound.definition == raw
    assert bound.geometry_binding.definition["is_ecm"] is True
    assert bound.kernel.moving == (0, 1)
    for name in (
        "membrane_diffusion_m2_s",
        "gap_diffusion_m2_s",
        "environment_diffusion_m2_s",
        "tight_junction_modulator",
    ):
        np.testing.assert_array_equal(getattr(bound.kernel, name), raw["ions"][name])
    assert material.validate_binding(bound) is bound
    assert bound.identity == current._digest(material.binding_record(bound))
    record = material.binding_record(bound)
    if mode is None:
        expected = dict(
            law=material.LAW_ID,
            definition=raw,
            geometry_binding=field.binding_record(bound.geometry_binding),
            geometry_identity=bound.geometry_binding.identity,
            kernel=bound.kernel,
        )
        assert current.record(record) == current.record(expected)
        assert "flux_operator" not in record
    else:
        assert record["law"] == material.DEMO_LAW_ID and record["material_law"] == material.LAW_ID
        assert record["flux_operator"] == mode
        assert record["scientific_acceptance"] is record["native_phase_admission"] is False
    if mode == "disabled":
        assert all(not row["flux"] for row in calls)
        assert bound.geometry_binding.geometry.neumann_inverse_m2 is None
    elif mode == "original":
        assert bound.geometry_binding.geometry.diagnostics["neumann_diagnostics_passed"] is False


def test_transport_strict_failure_and_demo_primary_are_not_suppressed(operator):
    policy, _, saved = operator
    policy["flux_shift"] = 8.0
    with pytest.raises(field.EnvironmentFieldRejected, match="gauge residual") as strict:
        material.bind(declaration())
    primary = RuntimeError("synthetic original flux delegate refused")
    policy["fail_flux"] = primary
    with pytest.raises(field.EnvironmentFieldRejected) as demo:
        material.bind(declaration("original"))
    saved.update(strict_trial=strict.value.trial, demo_trial=demo.value.trial, cause=str(primary))
    assert demo.value.__cause__ is primary and demo.value.stage == "demo_operators"
    assert demo.value.trial["neumann_laplacian_per_m2"] is not None


@pytest.mark.parametrize("defect", ["unknown_kind", "invalid_mode", "missing_mode", "ECM_off"])
def test_transport_never_infers_demo_or_disables_ecm(defect, operator):
    raw = declaration("disabled")
    field_raw = raw["environment_geometry_definition"]
    if defect == "unknown_kind":
        field_raw["kind"] = "undeclared_demo"
    elif defect == "invalid_mode":
        field_raw["flux_operator"] = "repaired"
    elif defect == "missing_mode":
        del field_raw["flux_operator"]
    else:
        field_raw["is_ecm"] = False
    with pytest.raises((ValueError, field.EnvironmentFieldRejected)):
        material.bind(raw)


@pytest.mark.parametrize("mode", [None, "original", "disabled"])
def test_literal_grid_constructor_dispatches_actual_field_binding(mode, monkeypatch, operator):
    operator[0]["flux_shift"] = 0.0 if mode is None else 8.0
    seen, bindings = [], []
    strict, demo = field.bind, field.bind_demo

    def observe(call, label):
        def bound(raw):
            seen.append(label)
            result = call(raw)
            bindings.append(result)
            return result

        return bound

    monkeypatch.setattr(field, "bind", observe(strict, "strict"))
    monkeypatch.setattr(field, "bind_demo", observe(demo, "demo"))
    selected = literal(
        "betse_ecm_sim_grn",
        ["build_grid"],
        dict(
            field=field,
            np=np,
            clone=lambda value: (
                np.array(value, copy=True) if isinstance(value, np.ndarray) else value
            ),
        ),
    )
    # A metadata target, not a Cells caller or an issued phase owner.
    target = SimpleNamespace(cell_to_mems=((0,),))
    selected.build_grid(target, None, dict(material_definition=declaration(mode)))
    operator[2].update(grid=vars(target), binding=field.binding_record(bindings[0]), dispatch=seen)
    assert seen == ["strict" if mode is None else "demo"]
    for target_name, attr in (
        ("X", "X_m"),
        ("Y", "Y_m"),
        ("xypts", "grid_points_m"),
        ("delta", "delta_m"),
        ("map_cell2ecm", "cell_to_grid"),
        ("map_mem2ecm", "membrane_to_grid"),
        ("memSa_per_envSquare", "membrane_area_per_site_m2"),
        ("M_divmap_mem2ecm", "membrane_divergence_map_m2"),
        ("true_ecm_vol", "true_environment_volume_m3"),
    ):
        np.testing.assert_array_equal(
            getattr(target, target_name), getattr(bindings[0].geometry, attr)
        )
    np.testing.assert_array_equal(target.num_mems, [1])


class MetadataBoundaryReached(Exception):
    pass


@pytest.mark.parametrize(
    "before,after",
    [
        (None, None),
        ("original", "original"),
        ("disabled", "disabled"),
        (None, "original"),
        (None, "disabled"),
        ("original", None),
        ("disabled", None),
        ("original", "disabled"),
        ("disabled", "original"),
    ],
)
def test_literal_INIT_SIM_callsite_keeps_kind_and_mode(before, after, operator):
    left, right = material.bind(declaration(before)), material.bind(declaration(after))
    raw = dict(
        sim_composition_template=dict(event_inputs=dict(field=dict(definition=right.definition)))
    )

    class StopBeforeOwnerUse(dict):
        def __getitem__(self, key):
            if key == "source_setup":
                raise MetadataBoundaryReached(
                    "policy/owner-definition checks reached; no phase admission"
                )
            return super().__getitem__(key)

    selected = literal(
        "betse_normal_ecm_molecule_lifecycle",
        ["_check_environment_policy", "check_owners"],
        dict(
            material=material,
            json=json,
            Mapping=Mapping,
            np=np,
            setup=SimpleNamespace(legacy_setup_inputs=lambda value: value),
            catalog=SimpleNamespace(equal_tree=lambda a, b: current.record(a) == current.record(b)),
        ),
    )
    # These are lenses over real typed bindings for the literal metadata
    # predicate only. They cannot pass an INIT/run API and never yield success.
    completed = SimpleNamespace(
        binding=SimpleNamespace(
            identity=left.identity,
            material_binding=left,
            inputs_raw=dict(field=dict(definition=left.definition)),
        )
    )
    target = SimpleNamespace(
        inputs=StopBeforeOwnerUse(raw),
        expected_init_identity=left.identity,
        declaration=SimpleNamespace(base=SimpleNamespace(material_binding=right)),
    )
    operator[2].update(before=material.binding_record(left), after=material.binding_record(right))
    if before == after:
        with pytest.raises(MetadataBoundaryReached, match="no phase admission"):
            selected.check_owners(target, completed)
    else:
        with pytest.raises(ValueError, match="environment operator policy"):
            selected.check_owners(target, completed)


@pytest.mark.parametrize(
    "mode,actual",
    [
        (None, "same"),
        ("original", "same"),
        ("disabled", "none"),
        (None, "none"),
        ("original", "none"),
        ("disabled", "zeros"),
        ("disabled", "scalar"),
        ("original", "changed"),
        ("disabled", "missing"),
    ],
)
def test_literal_owner_loop_requires_exact_disabled_absence(mode, actual, operator):
    binding = material.bind(declaration(mode)).geometry_binding
    selected = literal(
        "betse_normal_ecm_initialization",
        ["_same", "_same_flux_operator"],
        dict(np=np, math=math, material=material),
    )
    path, tree = nodes("betse_normal_ecm_initialization")
    function = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_check_owners"
    )
    loop = next(
        n
        for n in function.body
        if isinstance(n, ast.For) and ast.unparse(n.iter) == "cell_pairs.items()"
    )
    expected = binding.geometry.neumann_inverse_m2
    values = dict(other=np.asarray([1.0]))
    if actual != "missing":
        values["lapENV_P_inv"] = (
            expected
            if actual == "same"
            else None
            if actual == "none"
            else np.zeros((4, 4))
            if actual == "zeros"
            else 0.0
            if actual == "scalar"
            else expected + np.eye(4)
        )
    scope = dict(
        __name__="_field_demo_consumer_literals",
        gb=binding,
        c=values.__getitem__,
        cell_pairs=dict(other=np.asarray([1.0]), lapENV_P_inv=expected),
        _same=selected._same,
        _same_flux_operator=selected._same_flux_operator,
    )
    code = compile(ast.Module(body=[loop], type_ignores=[]), str(path), "exec")
    operator[2].update(binding=field.binding_record(binding), observed=values)
    if actual == "missing":
        with pytest.raises(KeyError, match="lapENV_P_inv"):
            exec(code, scope)
    elif actual == "same" or (mode == "disabled" and actual == "none"):
        exec(code, scope)
    else:
        with pytest.raises(ValueError, match="lapENV_P_inv"):
            exec(code, scope)


def codec_subset():
    """Literal unchanged codec, actual declared record subset; no phase import."""
    path, tree = nodes("betse_normal_ecm_molecule_checkpoint_codec")
    omitted = {
        "cells.physiology_checkpoint",
        "cells.processes.betse_normal_ecm_molecule_checkpoint_records",
    }
    tree.body = [
        n for n in tree.body if not (isinstance(n, ast.ImportFrom) and n.module in omitted)
    ]
    _, records_tree = nodes("betse_normal_ecm_molecule_checkpoint_records")
    declared = ast.literal_eval(
        next(
            n.value
            for n in records_tree.body
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "RECORDS" for t in n.targets)
        )
    )
    registry = {}
    for module in (field, current, material):
        for name in declared[module.__name__]:
            cls = getattr(module, name)
            names = tuple(f.name for f in fields(cls)) if is_dataclass(cls) else cls._fields
            registry[module.__name__ + "." + name] = cls, names
    namespace = dict(
        __name__=__name__, __file__=str(path), registry=lambda: registry, digest=digest
    )
    # Keep the actual nonnumerical writer/fsync helpers as literal definitions.
    helpers = ROOT / "src/cells/physiology_checkpoint.py"
    selected = [
        n
        for n in ast.parse(helpers.read_text()).body
        if isinstance(n, ast.FunctionDef) and n.name in ("_write_json", "_sync_directory")
    ]
    exec(compile(tree, str(path), "exec"), namespace)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(helpers), "exec"), namespace)
    return SimpleNamespace(**namespace)


def checkpoint_binding_gate(codec, manifest, binding):
    """Execute the exact existing load predicate, never a full load/owner API."""
    path, tree = nodes("betse_normal_ecm_molecule_checkpoint")
    load = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "load_checkpoint"
    )
    matches = [
        n
        for n in ast.walk(load)
        if isinstance(n, ast.Expr)
        and isinstance(n.value, ast.Call)
        and any(
            isinstance(arg, ast.Constant) and arg.value == "Complete supplied binding mismatch"
            for arg in n.value.args
        )
    ]
    assert len(matches) == 1
    exec(
        compile(ast.Module(body=matches, type_ignores=[]), str(path), "exec"),
        dict(
            __name__="_field_demo_consumer_literals",
            codec=codec,
            manifest=manifest,
            binding=binding,
            limits=codec.DEFAULT_LIMITS,
        ),
    )


@pytest.mark.parametrize("mode", [None, "original", "disabled"])
def test_existing_codec_roundtrip_keeps_policy_absence_and_alias(mode, tmp_path, operator):
    bound = material.bind(declaration(mode))
    codec = codec_subset()
    payload = dict(binding=bound, same_binding=bound)
    encoder = codec.Encoder()
    tree = encoder.capture(payload)
    seal = encoder.seal(tree)
    folder = tmp_path / "closed-record-codec"
    folder.mkdir()
    encoder.write(folder, tree)
    restored = codec.decode(tree, (folder / "arrays.npz").read_bytes())
    operator[2].update(seal=seal, restored=material.binding_record(restored["binding"]))
    assert type(restored["binding"]) is material.Binding
    assert restored["binding"] is restored["same_binding"]
    assert codec.fingerprint(restored) == seal
    assert material.validate_binding(restored["binding"]) is restored["binding"]
    assert restored["binding"].definition == bound.definition
    if mode == "disabled":
        assert restored["binding"].geometry_binding.geometry.neumann_inverse_m2 is None
    manifest = dict(binding_identity=bound.identity, binding_seal=codec.fingerprint(bound))
    checkpoint_binding_gate(codec, manifest, restored["binding"])


@pytest.mark.parametrize(
    "before,after",
    [
        (None, "original"),
        (None, "disabled"),
        ("original", None),
        ("disabled", None),
        ("original", "disabled"),
        ("disabled", "original"),
    ],
)
def test_existing_checkpoint_binding_gate_refuses_mode_switch(before, after, operator):
    left, right = material.bind(declaration(before)), material.bind(declaration(after))
    codec = codec_subset()
    manifest = dict(binding_identity=left.identity, binding_seal=codec.fingerprint(left))
    operator[2].update(
        manifest=manifest,
        supplied_identity=right.identity,
        supplied_fingerprint=codec.fingerprint(right),
    )
    with pytest.raises(ValueError, match="Complete supplied binding mismatch"):
        checkpoint_binding_gate(codec, manifest, right)
    # A forged identity alone cannot erase the complete typed binding seal.
    with pytest.raises(ValueError, match="Complete supplied binding mismatch"):
        checkpoint_binding_gate(codec, manifest, replace(right, identity=left.identity))


@pytest.mark.parametrize(
    "before,after", [(None, "original"), ("original", "disabled"), ("disabled", "original")]
)
def test_resealed_geometry_policy_substitution_fails_revalidation(before, after, operator):
    left, right = material.bind(declaration(before)), material.bind(declaration(after))
    forged = replace(left, geometry_binding=right.geometry_binding)
    forged = replace(forged, identity=current._digest(material.binding_record(forged)))
    operator[2].update(
        original=material.binding_record(left), forged=material.binding_record(forged)
    )
    with pytest.raises(ValueError, match="Resealed ECM geometry"):
        material.validate_binding(forged)
