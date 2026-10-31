"""Callable binding regressions; no native descriptor or numerical execution."""

import importlib.abc
import sys
from types import BuiltinFunctionType, FunctionType, MethodType, ModuleType

import pytest

from cells.processes import betse_native_single_cell_grid_alias as aliases


@pytest.fixture(autouse=True)
def no_native_work(monkeypatch):
    attempts = []

    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in {"betse", "numpy", "scipy", "PIL", "jax", "jaxlib"}:
                attempts.append(fullname)
                raise AssertionError("Native/scientific import forbidden: " + fullname)

    def forbidden(*args, **kwargs):
        attempts.append("native_descriptor_factory")
        raise AssertionError("Native descriptor execution forbidden")

    blocker = Block()
    sys.meta_path.insert(0, blocker)
    monkeypatch.setattr(aliases, "_descriptor_from_source", forbidden)
    try:
        yield
    finally:
        sys.meta_path.remove(blocker)
    assert not attempts


@pytest.mark.parametrize("value", [FunctionType, MethodType, BuiltinFunctionType, type, int, len])
def test_callable_types_and_builtins_are_identity_atoms(value):
    atoms = aliases._atoms(value)
    assert len(atoms) == 1 and atoms[0] is value


def test_callable_object_does_not_execute_function_lookalike_descriptors():
    class Callable:
        @property
        def __code__(self):
            raise AssertionError("Must not use duck-typed function attributes")

        def __call__(self):
            raise AssertionError("Must not execute callable")

    instance = Callable()
    assert aliases._atoms(instance) == (instance,)


def test_function_retains_code_closure_and_default_identities():
    captured, default = object(), object()

    def function(argument=default):
        return captured, argument

    atoms = aliases._atoms(function)
    expected = (function, function.__code__, function.__closure__[0], captured, default)
    assert len(atoms) == len(expected)
    assert all(a is b for a, b in zip(atoms, expected, strict=True))


def test_bound_method_retains_code_and_defaults():
    default = object()

    class Caller:
        def method(self, argument=default):
            return argument

    method = Caller().method
    atoms = aliases._atoms(method)
    assert len(atoms) == 3
    assert all(a is b for a, b in zip(atoms, (method, method.__code__, default), strict=True))


@pytest.fixture
def module_authority(monkeypatch):
    captured, default = object(), object()

    def function(argument=default):
        return captured, argument

    module = ModuleType("synthetic_binding_module")
    module.FunctionType = FunctionType
    module.MethodType = MethodType
    module.function = function
    record = (module, "synthetic_source_path", "synthetic_source_digest")
    monkeypatch.setattr(aliases, "_module_records", lambda: {module.__name__: record})
    monkeypatch.setattr(
        aliases, "_MODULE_AUTH", {module.__name__: (record, aliases._module_bindings(module))}
    )
    return module


def test_mixed_module_callables_validate_unchanged(module_authority):
    aliases._check_modules()


@pytest.mark.parametrize("mutation", ["code", "closure", "default", "function", "class"])
def test_mixed_module_still_refuses_callable_binding_drift(module_authority, mutation):
    module = module_authority
    function = module.function
    if mutation == "code":
        function.__code__ = function.__code__.replace(co_name="changed")
    elif mutation == "closure":
        function.__closure__[0].cell_contents = object()
    elif mutation == "default":
        function.__defaults__ = (object(),)
    elif mutation == "function":
        module.function = FunctionType(
            function.__code__, function.__globals__, closure=function.__closure__
        )
    else:
        module.FunctionType = MethodType
    with pytest.raises(ValueError, match="callable/code authority changed"):
        aliases._check_modules()
