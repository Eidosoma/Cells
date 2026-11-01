"""No-call compiler/namespace/release controls; original positive work is held."""

import ast
import json
import os
import sys
from types import FunctionType

import pytest

from validation.betse import betse_normal_ecm_molecule_material_four_call_reference as reference


@pytest.fixture(autouse=True)
def no_reference_work(tmp_path):
    previous, attempted = sys.getprofile(), []
    codes = {id(f.__code__) for f in reference._FUNCTIONS}

    def guard(frame, event, arg):
        if event == "call" and (
            id(frame.f_code) in codes
            or frame.f_code.co_filename.startswith(("<pinned native ", reference.PREFIX))
        ):
            attempted.append(frame.f_code.co_name)
            raise AssertionError("Original/native/Decimal positive body forbidden")
        if previous is not None:
            previous(frame, event, arg)

    sys.setprofile(guard)
    yield attempted
    sys.setprofile(previous)
    (tmp_path / "reference-blocked.json").write_text(
        json.dumps(dict(attempted=attempted, scientific_acceptance=False))
    )
    assert attempted == []


def test_complete_adapter_AST_and_actual_function_namespace_have_only_declared_cap_delta(tmp_path):
    function, report = reference.adapter_ast()
    assert report["allowed_delta"] == "only native adapter len(steps) upper bound 3 -> 4"
    assert "1 <= len(inputs['steps']) <= 4" in ast.unparse(function)
    prepared = reference.compile_adapter()
    assert prepared.__globals__ is reference.native.evaluate.__globals__
    assert prepared.__builtins__ is reference.native.evaluate.__builtins__
    assert prepared.__code__.co_filename == reference.PREFIX
    (tmp_path / "compiler-control.json").write_text(json.dumps(report))


@pytest.mark.parametrize(
    "fault",
    [
        "provider",
        "capture",
        "geometry-capture",
        "code",
        "cached-builtins",
        "shadow-float",
        "shadow-setattr",
        "numpy",
    ],
)
def test_no_call_foreign_copied_or_shadowed_source_helpers_refuse(monkeypatch, fault):
    original = reference.native.evaluate
    if fault == "provider":
        monkeypatch.setattr(
            reference.native, "evaluate", FunctionType(original.__code__, original.__globals__)
        )
    elif fault == "capture":
        function = reference.native.capture
        monkeypatch.setattr(
            reference.native, "capture", FunctionType(function.__code__, function.__globals__)
        )
    elif fault == "geometry-capture":
        function = reference.native.geometry_native.capture
        monkeypatch.setattr(
            reference.native.geometry_native,
            "capture",
            FunctionType(function.__code__, function.__globals__),
        )
    elif fault == "code":
        monkeypatch.setattr(
            original, "__code__", original.__code__.replace(co_filename="foreign-equal-bytecode")
        )
    elif fault == "cached-builtins":
        monkeypatch.setitem(original.__globals__, "__builtins__", dict(original.__builtins__))
    elif fault.startswith("shadow-"):
        monkeypatch.setitem(original.__globals__, fault[7:], lambda *args: None)
    else:
        monkeypatch.setattr(reference.native.np, "asarray", lambda *args: None)
    with pytest.raises(ValueError):
        reference.compile_adapter()


@pytest.mark.parametrize("entry", ["original", "Decimal100", "Decimal160"])
@pytest.mark.parametrize("gates", [("0", "0"), ("1", "0"), ("0", "1"), ("1", "1")])
def test_all_positive_source_calls_require_explicit_Root_release_before_inputs(
    monkeypatch, entry, gates
):
    for name, state in zip(reference.RELEASES, gates, strict=True):
        monkeypatch.setenv(name, state)
    with pytest.raises(ValueError, match="remains held"):
        if entry == "original":
            reference.evaluate_original(None, enabled=False)
        else:
            reference.evaluate_decimal(
                None, refinement=1 if entry == "Decimal100" else 2, enabled=False
            )


@pytest.mark.parametrize("entry", ["original", "decimal"])
def test_released_but_missing_declared_sequence_refuses_before_provider(monkeypatch, entry):
    for name in reference.RELEASES:
        monkeypatch.setenv(name, "1")
    with pytest.raises(ValueError, match="four-call"):
        if entry == "original":
            reference.evaluate_original({}, enabled=True)
        else:
            reference.evaluate_decimal({}, refinement=1, enabled=True)


def test_reference_module_has_no_Cells_numerical_import_or_equation_definition():
    from pathlib import Path

    tree = ast.parse(Path(reference.__file__).read_bytes())
    imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not any(n and n.startswith("cells") for n in imports)
    definitions = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    assert (
        not {"flux", "smooth", "electroflux", "nernst_planck_flux", "update_Co", "step"}
        & definitions
    )
    assert all(os.environ.get(n) != "1" for n in reference.RELEASES)
