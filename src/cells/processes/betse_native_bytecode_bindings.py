"""Fresh ordered global/import lookup metadata, without Instruction allocation.

Only CPython 3.13 uses the compact path. It reads the current immutable code
object on every call, through the original stdlib unpacker; no decoded plan,
resolved global, successful binding, or owner validation is cached. Other
interpreters retain the ordinary ``dis.get_instructions`` implementation.
"""

import dis
import opcode
import sys
from types import CodeType, FunctionType, ModuleType


def _function_row(function):
    resolved = []
    for instruction in dis.get_instructions(function):
        if instruction.opname == "LOAD_GLOBAL":
            name = instruction.argval
            local = name in function.__globals__
            namespace = function.__globals__ if local else function.__builtins__
            resolved.append((name, local, namespace[name]))
    return (
        function,
        function.__code__,
        function.__globals__,
        function.__builtins__,
        function.__defaults__,
        function.__kwdefaults__,
        tuple((function.__kwdefaults__ or {}).items()),
        function.__closure__,
        tuple((cell, cell.cell_contents) for cell in function.__closure__ or ()),
        tuple(resolved),
    )


def _check_function(row):
    function, code, namespace, builtins, defaults, keywords, items, closure, cells, names = row
    if (
        type(function) is not FunctionType
        or function.__code__ is not code
        or function.__globals__ is not namespace
        or function.__builtins__ is not builtins
        or function.__defaults__ is not defaults
        or function.__kwdefaults__ is not keywords
        or function.__closure__ is not closure
        or len(function.__kwdefaults__ or {}) != len(items)
    ):
        raise ValueError("Bytecode decoder callable/code/default/closure changed")
    for name, value in items:
        if name not in keywords or keywords[name] is not value:
            raise ValueError("Bytecode decoder keyword default changed")
    for cell, value in cells:
        if cell.cell_contents is not value:
            raise ValueError("Bytecode decoder closure value changed")
    for name, local, value in names:
        if (name in namespace) is not local:
            raise ValueError("Bytecode decoder resolved lookup category changed")
        current = namespace if local else builtins
        if name not in current or current[name] is not value:
            raise ValueError("Bytecode decoder resolved helper changed")


_DIS, _OPCODE, _SYS = dis, opcode, sys
_IMPLEMENTATION, _VERSION = sys.implementation, sys.version_info
_RUNTIME = (_IMPLEMENTATION.name, tuple(_VERSION[:2]))
_FALLBACK = dis.get_instructions
_FALLBACK_ROW = _function_row(_FALLBACK)
_FAST = _RUNTIME == ("cpython", (3, 13)) and all(
    type(getattr(dis, name, None)) is FunctionType
    for name in ("_unpack_opargs", "_deoptop", "_get_cache_size")
)
_UNPACK = dis._unpack_opargs if _FAST else None
_FUNCTIONS = (
    tuple(
        (name, _function_row(getattr(dis, name)))
        for name in ("_unpack_opargs", "_deoptop", "_get_cache_size")
    )
    if _FAST
    else ()
)
_TABLES = (
    tuple(
        (
            name,
            getattr(dis, name),
            tuple(getattr(dis, name).items())
            if type(getattr(dis, name)) is dict
            else tuple(getattr(dis, name)),
        )
        for name in (
            "_all_opname",
            "_all_opmap",
            "deoptmap",
            "hasarg",
            "_inline_cache_entries",
        )
    )
    if _FAST
    else ()
)
_OPMAP = opcode.opmap
_GLOBAL, _IMPORT = _OPMAP["LOAD_GLOBAL"], _OPMAP["IMPORT_NAME"]
_AUTHORITY = (
    _DIS,
    _OPCODE,
    _SYS,
    _IMPLEMENTATION,
    _VERSION,
    _RUNTIME,
    _OPMAP,
    _GLOBAL,
    _IMPORT,
    _FALLBACK,
    _FALLBACK_ROW,
    _FAST,
    _UNPACK,
    _FUNCTIONS,
    _TABLES,
)


def _authenticate(_check=_check_function, _authority=_AUTHORITY):
    # Defaults are intentionally traversable by the existing aliases._atoms
    # callable walker. A later owner need not reopen a retired caller's broad
    # bindings to retain this checker and its immutable expected roster.
    (
        original_dis,
        original_opcode,
        original_sys,
        implementation,
        version,
        runtime,
        opmap,
        global_op,
        import_op,
        fallback,
        fallback_row,
        fast,
        unpack,
        functions,
        tables,
    ) = _authority
    if (
        dis is not original_dis
        or opcode is not original_opcode
        or sys is not original_sys
        or type(dis) is not ModuleType
        or sys.modules.get("dis") is not dis
        or sys.modules.get("opcode") is not opcode
        or sys.implementation is not implementation
        or sys.version_info is not version
        or (implementation.name, tuple(version[:2])) != runtime
        or opcode.opmap is not opmap
        or opmap.get("LOAD_GLOBAL") is not global_op
        or opmap.get("IMPORT_NAME") is not import_op
        or dis.get_instructions is not fallback
        or fallback is not fallback_row[0]
        or _FALLBACK is not fallback
        or _UNPACK is not unpack
        or _FUNCTIONS is not functions
        or _TABLES is not tables
        or (fast and unpack is not functions[0][1][0])
    ):
        raise ValueError("Bytecode decoder runtime/opcode association changed")
    _check(fallback_row)
    for name, row in functions:
        if vars(dis).get(name) is not row[0]:
            raise ValueError("Bytecode decoder helper identity changed")
        _check(row)
    for name, table, items in tables:
        if vars(dis).get(name) is not table or len(table) != len(items):
            raise ValueError("Bytecode decoder opcode table changed")
        if type(table) is dict:
            for key, value in items:
                if key not in table or table[key] is not value:
                    raise ValueError("Bytecode decoder opcode mapping changed")
        else:
            for current, old in zip(table, items, strict=True):
                if current is not old:
                    raise ValueError("Bytecode decoder opcode sequence changed")


def lookup_names(
    code,
    _authenticate=_authenticate,
    _unpack=_UNPACK,
    _fallback=_FALLBACK,
    _fast=_FAST,
    _global=_GLOBAL,
    _import=_IMPORT,
):
    """Return ordered ``(opname, name)`` pairs, retaining duplicate lookups.

    Callers still authenticate the function/code/default/closure and resolve
    every returned name against their *current* globals and cached builtins.
    This helper does not resolve or certify any caller state. Retain this
    callable in the caller's positional default (or closure), so its existing
    recursive callable atoms include the decoder, authentication and checker
    code even after the caller's own binding epoch has retired.
    """
    if type(code) is not CodeType:
        raise TypeError("Exact current CodeType required")
    _authenticate()
    if _fast:
        names = code.co_names
        result = []
        for _, _, op, arg in _unpack(code.co_code):
            if op == _global:
                result.append(("LOAD_GLOBAL", names[arg >> 1]))
            elif op == _import:
                result.append(("IMPORT_NAME", names[arg]))
        result = tuple(result)
    else:
        result = tuple(
            (instruction.opname, instruction.argval)
            for instruction in _fallback(code)
            if instruction.opname in ("LOAD_GLOBAL", "IMPORT_NAME")
        )
    # A metadata observer may mutate the stdlib while the generator runs.
    # Refuse before publishing the decoded rows rather than returning a plan
    # produced across two different decoder epochs.
    _authenticate()
    return result


def runtime_bindings():
    """Expose exact decoder dependencies for the caller's existing bindings."""
    _authenticate()
    functions = (
        lookup_names,
        runtime_bindings,
        _authenticate,
        _check_function,
        _function_row,
        _FALLBACK,
        *(row[0] for _, row in _FUNCTIONS),
    )
    return (
        (_RUNTIME, _FAST, _GLOBAL, _IMPORT),
        (
            dis,
            opcode,
            sys,
            _IMPLEMENTATION,
            _VERSION,
            _OPMAP,
            _UNPACK,
            _FUNCTIONS,
            _TABLES,
            _FALLBACK_ROW,
            *(
                atom
                for function in functions
                for atom in (
                    function,
                    function.__code__,
                    function.__globals__,
                    function.__builtins__,
                    function.__defaults__,
                    function.__kwdefaults__,
                    function.__closure__,
                    *(atom for item in (function.__kwdefaults__ or {}).items() for atom in item),
                    *(cell.cell_contents for cell in function.__closure__ or ()),
                )
            ),
        ),
    )
