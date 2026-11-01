"""Held four-call use of existing original BETSE and independent Decimal providers.

Only the existing native adapter's bounded length guard changes from 3 to 4.
No Cells numerical body is imported here, no native package is imported, and
the actual original-source compiler/geometry setup runs only after release.
"""

import ast
import builtins
import copy
import dis
import hashlib
import os
from pathlib import Path
from types import CodeType, FunctionType, ModuleType

from validation.betse import betse_ecm_transport_native as native
from validation.betse import betse_ecm_transport_reference as decimal

RELEASES = ("CELLS_ECM_MOLECULE_RUN_LIFECYCLE_RELEASED", "CELLS_ECM_MOLECULE_EVENTS_RELEASED")
NATIVE_ADAPTER_SHA256 = "f7dc33413b07be8430f885262e842c413a2f29867e8d44edfdf5356357d0b3b3"
DECIMAL_SHA256 = "b58f097b4e11f06c9b06404f165b5766d4eeac708a13e3d2df1fd1fcb072bfdd"
PREFIX = "<held original ECM material four-call adapter>"


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _global_names(code):
    result = {i.argval for i in dis.get_instructions(code) if i.opname == "LOAD_GLOBAL"}
    for item in code.co_consts:
        if type(item) is CodeType:
            result.update(_global_names(item))
    return result


def _resolve(function, name):
    return function.__globals__.get(name, function.__builtins__.get(name))


_FUNCTIONS = (
    native.evaluate,
    decimal.evaluate,
    native.capture,
    native.geometry_native.capture,
    native.geometry_native.wrapper,
    decimal.geometry,
)
_CODES = tuple(f.__code__ for f in _FUNCTIONS)
_BUILTINS = tuple(f.__builtins__ for f in _FUNCTIONS)
_LOOKUPS = tuple(
    {name: _resolve(f, name) for name in _global_names(f.__code__)} for f in _FUNCTIONS
)
_NP_LOOKUPS = {
    name: getattr(native.np, name)
    for name in (
        "asarray",
        "array",
        "arange",
        "flatnonzero",
        "column_stack",
        "array_equal",
        "zeros",
    )
}
_RNG_READER = native.np.random.get_state


def check_context():
    """No-call resolution/cached-builtins guard, before construction and work."""
    require(
        (
            native.evaluate,
            decimal.evaluate,
            native.capture,
            native.geometry_native.capture,
            native.geometry_native.wrapper,
            decimal.geometry,
        )
        == _FUNCTIONS,
        "Foreign/equal-copied reference provider",
    )
    for index, function in enumerate(_FUNCTIONS):
        require(
            function.__code__ is _CODES[index] and function.__builtins__ is _BUILTINS[index],
            "Changed reference code/cached builtins",
        )
        namespace_builtins = function.__globals__["__builtins__"]
        if type(namespace_builtins) is ModuleType:
            namespace_builtins = vars(namespace_builtins)
        require(
            namespace_builtins is _BUILTINS[index],
            "Construction namespace/cached builtins mismatch",
        )
        require(
            all(_resolve(function, name) is expected for name, expected in _LOOKUPS[index].items()),
            "Reached reference global/builtin lookup changed",
        )
    require(
        all(getattr(native.np, name) is expected for name, expected in _NP_LOOKUPS.items())
        and native.np.random.get_state is _RNG_READER,
        "Reached NumPy reference helpers changed",
    )
    require(_BUILTINS[0] is builtins.__dict__, "Expected actual interpreter builtin dictionary")


def adapter_ast():
    """The complete pinned evaluator, allowing one explicit temporal guard delta."""
    path = Path(native.__file__)
    data = path.read_bytes()
    require(
        hashlib.sha256(data).hexdigest() == NATIVE_ADAPTER_SHA256, "Native adapter source changed"
    )
    require(
        hashlib.sha256(Path(decimal.__file__).read_bytes()).hexdigest() == DECIMAL_SHA256,
        "Independent Decimal source changed",
    )
    old = next(
        n for n in ast.parse(data).body if isinstance(n, ast.FunctionDef) and n.name == "evaluate"
    )
    changed = copy.deepcopy(old)
    nodes = [
        n
        for n in ast.walk(changed)
        if isinstance(n, ast.Compare) and ast.unparse(n) == "1 <= len(inputs['steps']) <= 3"
    ]
    require(
        len(nodes) == 1 and type(nodes[0].comparators[-1].value) is int,
        "Unique original native call cap",
    )
    nodes[0].comparators[-1].value = 4
    restored = copy.deepcopy(changed)
    cap = next(
        n
        for n in ast.walk(restored)
        if isinstance(n, ast.Compare) and ast.unparse(n) == "1 <= len(inputs['steps']) <= 4"
    )
    cap.comparators[-1].value = 3
    require(
        ast.dump(restored, include_attributes=False) == ast.dump(old, include_attributes=False),
        "Non-cap native evaluator AST delta",
    )
    return changed, dict(
        native_adapter_sha256=NATIVE_ADAPTER_SHA256,
        decimal_provider_sha256=DECIMAL_SHA256,
        original_AST_sha256=hashlib.sha256(
            ast.dump(old, include_attributes=False).encode()
        ).hexdigest(),
        four_call_AST_sha256=hashlib.sha256(
            ast.dump(changed, include_attributes=False).encode()
        ).hexdigest(),
        allowed_delta="only native adapter len(steps) upper bound 3 -> 4",
        original_source_compiler="validation.betse.betse_ecm_transport_native.capture",
        native_package_or_Cells_numerical_imports=False,
    )


def compile_adapter():
    """Compile a trusted definition only; never invoke setup, RNG or arithmetic."""
    check_context()
    function, _ = adapter_ast()
    module = compile(
        ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])), PREFIX, "exec"
    )
    code = next(c for c in module.co_consts if type(c) is CodeType and c.co_name == "evaluate")
    result = FunctionType(code, _FUNCTIONS[0].__globals__, "original_material_four_calls")
    require(
        result.__globals__ is _FUNCTIONS[0].__globals__ and result.__builtins__ is _BUILTINS[0],
        "Original evaluator namespace/builtins association changed",
    )
    check_context()
    return result


def released(enabled):
    require(
        enabled is True and all(os.environ.get(n) == "1" for n in RELEASES),
        "Original/arithmetic/reference-positive work remains held for Root",
    )


def evaluate_original(inputs, *, enabled=False):
    released(enabled)
    require(
        type(inputs) is dict and type(inputs.get("steps")) is list and len(inputs["steps"]) == 4,
        "Explicit original four-call sequence required",
    )
    function = compile_adapter()
    try:
        return function(inputs)
    finally:
        # A failed source exception remains primary if this secondary guard
        # also refuses; the caller retains the error and partial observation.
        import sys

        primary = sys.exception()
        try:
            check_context()
        except BaseException as secondary:
            if primary is None:
                raise
            primary.add_note("Reference context also changed: " + repr(secondary))


def evaluate_decimal(inputs, *, refinement, enabled=False, retain_decimal=None):
    released(enabled)
    require(
        type(inputs) is dict
        and type(inputs.get("steps")) is list
        and len(inputs["steps"]) == 4
        and type(refinement) is int
        and refinement in (1, 2),
        "Explicit four-call Decimal100/160 input required",
    )
    check_context()
    try:
        return _FUNCTIONS[1](inputs, refinement=refinement, retain_decimal=retain_decimal)
    finally:
        import sys

        primary = sys.exception()
        try:
            check_context()
        except BaseException as secondary:
            if primary is None:
                raise
            primary.add_note("Reference context also changed: " + repr(secondary))
