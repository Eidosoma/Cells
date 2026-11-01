"""Bounded immutable AST descriptions, never source or owner admission.

Callers must freshly read and authenticate source bytes on every verification.
Only parsing and structural serialization are reused. No path, timestamp,
mutable AST, producer dictionary or successful validation is cached.
"""

import ast
from functools import lru_cache
from types import FunctionType, MethodType

CACHE_SIZE = 32
MAX_SOURCE_BYTES = 2**21
MAX_SIGNATURE_CHARS = 2**20
MAX_SELECTOR_CHARS = 256
MAX_SELECTED_LINES = 64


def _target(statement):
    if not hasattr(statement, "targets"):
        return ("missing_targets", type(statement).__name__)
    first = statement.targets[0]
    if not hasattr(first, "attr"):
        return ("missing_attr", type(first).__name__)
    return ("attribute", first.attr)


@lru_cache(maxsize=CACHE_SIZE)
def _method(raw, class_name, method_name, lines):
    tree = ast.parse(raw.decode("utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    fn = next(
        n
        for n in cls.body
        if isinstance(n, ast.FunctionDef) and (method_name is None or n.name == method_name)
    )
    body = fn.body if lines is None else [n for n in fn.body if n.lineno in lines]
    arguments = ast.dump(fn.args)
    body_dump = ast.dump(ast.Module(body=body, type_ignores=[]))
    rows = tuple((n.lineno, ast.dump(n), _target(n)) for n in body)
    if len(arguments) + len(body_dump) + sum(len(row[1]) for row in rows) > MAX_SIGNATURE_CHARS:
        raise ValueError("Bounded source structure exceeds metadata capacity")
    return arguments, body_dump, tuple(arg.arg for arg in fn.args.args), rows


def method(raw, class_name, method_name, lines=None):
    """Return argument/body dumps, positional names and ordered statement rows."""
    if type(raw) is not bytes or len(raw) > MAX_SOURCE_BYTES:
        raise ValueError("Require bounded exact source bytes")
    if type(class_name) is not str or (method_name is not None and type(method_name) is not str):
        raise TypeError("Require exact class and method selectors")
    if len(class_name) > MAX_SELECTOR_CHARS or (
        method_name is not None and len(method_name) > MAX_SELECTOR_CHARS
    ):
        raise ValueError("Bounded source selector exceeds metadata capacity")
    if lines is not None and type(lines) is not tuple:
        raise TypeError("Require immutable exact source-line selectors")
    if lines is not None and len(lines) > MAX_SELECTED_LINES:
        raise ValueError("Bounded source lines exceed metadata capacity")
    if lines is not None and any(type(line) is not int for line in lines):
        raise TypeError("Require immutable exact source-line selectors")
    if lines is not None and (any(not 0 < line <= MAX_SOURCE_BYTES for line in lines)):
        raise ValueError("Bounded source lines exceed metadata capacity")
    return _method(raw, class_name, method_name, lines)


def target_attribute(row):
    """Preserve the first-target access used by the original tail check."""
    kind, value = row[2]
    if kind == "missing_targets":
        raise AttributeError(f"'{value}' object has no attribute 'targets'")
    if kind == "missing_attr":
        raise AttributeError(f"'{value}' object has no attribute 'attr'")
    return value


def _atoms(function):
    seen, result, visited = set(), [], 0

    def visit(value, depth=0):
        nonlocal visited
        visited += 1
        if visited > 512 or depth > 32:
            raise ValueError("Callable metadata capacity exceeded")
        # The owner checker flattens tuples. Explicit type/field markers
        # preserve nested default shapes even after that flattening.
        result.append(type(value))
        if type(value) is tuple:
            if len(value) > 64:
                raise ValueError("Callable tuple metadata capacity exceeded")
            result.append(value)
            for item in value:
                visit(item, depth + 1)
            result.append("tuple_end")
            return
        if id(value) in seen:
            return
        seen.add(id(value))
        result.append(value)
        if type(value) in (FunctionType, MethodType):
            result.append(value.__code__)
            closure, defaults, keywords = (
                value.__closure__,
                value.__defaults__,
                value.__kwdefaults__,
            )
            if any(len(items) > 64 for items in (closure or (), defaults or (), keywords or ())):
                raise ValueError("Callable field metadata capacity exceeded")
            result.append("closure")
            for cell in closure or ():
                result.append(cell)
                visit(cell.cell_contents, depth + 1)
            result.append("defaults")
            visit(defaults, depth + 1)
            result.append("keyword_defaults")
            for name, item in (keywords or {}).items():
                visit(name, depth + 1)
                visit(item, depth + 1)
            result.append("function_end")

    visit(function)
    return tuple(result)


def bindings():
    """Include the cache's actual Python body, not just wrapper identity."""
    functions = (
        method,
        _method,
        _method.__wrapped__,
        _target,
        target_attribute,
        _atoms,
        ast.parse,
        ast.dump,
    )
    return (
        CACHE_SIZE,
        MAX_SOURCE_BYTES,
        MAX_SIGNATURE_CHARS,
        MAX_SELECTOR_CHARS,
        MAX_SELECTED_LINES,
        FunctionType,
        MethodType,
        ast,
        ast.ClassDef,
        ast.FunctionDef,
        ast.Module,
        *(atom for fn in functions for atom in _atoms(fn)),
    )
