"""Read constants out of Python source without importing it.

The architecture extractor needs facts the engine declares in code (an operator's
LAW_ID, the fields it writes, the laws it requires). Importing ``cells`` would pull in
JAX and run the engine, so this module parses the files with ``ast`` and evaluates only
pure expressions: literals, names bound at module or class level, names imported from
other modules of the same package, container displays, comprehensions and a short list
of pure builtins. Anything else raises ``Unresolved``; callers record the attribute as
unresolved and say so, so a wrong edge is never produced silently.

Standard library only.
"""

from __future__ import annotations

import ast
from pathlib import Path


class Unresolved(Exception):
    """The expression needs something this evaluator does not model."""


class Symbol:
    """A name from outside the package (numpy.int64): kept as text, never evaluated."""

    def __init__(self, text):
        self.text = text

    def __repr__(self):
        return self.text

    def __eq__(self, other):
        return isinstance(other, Symbol) and other.text == self.text

    def __hash__(self):
        return hash(self.text)


class ModuleRef:
    def __init__(self, module):
        self.module = module


class ExternalRef:
    def __init__(self, dotted):
        self.dotted = dotted


class ClassRef:
    def __init__(self, module, node):
        self.module = module
        self.node = node


SAFE_CALLS = {
    "tuple": tuple,
    "list": list,
    "dict": dict,
    "set": set,
    "frozenset": frozenset,
    "sorted": sorted,
    "len": len,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "zip": zip,
    "range": range,
    "enumerate": enumerate,
    "min": min,
    "max": max,
    "sum": sum,
    "reversed": reversed,
    "MappingProxyType": dict,
}
SAFE_METHODS = {
    dict: {"items", "keys", "values", "get"},
    str: {"join", "format", "split", "replace", "lower", "upper", "strip", "startswith", "endswith"},
    tuple: {"index", "count"},
    list: {"index", "count"},
    set: {"union", "intersection", "difference"},
    frozenset: {"union", "intersection", "difference"},
}
MAX_DEPTH = 60


class Module:
    """One parsed source file: its module-level bindings, imports and classes."""

    def __init__(self, package, dotted, path):
        self.package = package
        self.dotted = dotted
        self.path = path
        self.source = path.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source, filename=str(path))
        self.env = {}  # name -> ast expression (the last module-level binding wins)
        self.imports = {}  # local name -> ("module", dotted) | ("name", dotted, attribute)
        self.classes = {}
        self.functions = set()
        self._collect(self.tree.body)

    def _collect(self, body):
        for node in body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    self._bind(target, node.value)
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                self._bind(node.target, node.value)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    local = alias.asname or alias.name.split(".")[0]
                    dotted = alias.name if alias.asname else alias.name.split(".")[0]
                    self.imports[local] = ("module", dotted)
            elif isinstance(node, ast.ImportFrom):
                base = self._absolute(node.module or "", node.level)
                for alias in node.names:
                    self.imports[alias.asname or alias.name] = ("name", base, alias.name)
            elif isinstance(node, ast.ClassDef):
                self.classes[node.name] = node
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.functions.add(node.name)
            elif isinstance(node, (ast.If, ast.Try)):
                # Bindings under a module-level guard still name the module's constants.
                self._collect(node.body)

    def _bind(self, target, value):
        if isinstance(target, ast.Name):
            self.env[target.id] = value
        elif isinstance(target, (ast.Tuple, ast.List)) and isinstance(value, (ast.Tuple, ast.List)):
            if len(target.elts) == len(value.elts):
                for sub_target, sub_value in zip(target.elts, value.elts):
                    self._bind(sub_target, sub_value)

    def _absolute(self, module, level):
        if not level:
            return module
        parts = self.dotted.split(".")
        if self.path.name != "__init__.py":
            parts = parts[:-1]
        parts = parts[: len(parts) - (level - 1)]
        return ".".join(parts + ([module] if module else []))

    def imported_modules(self):
        """Dotted names of every module this file imports (absolute)."""
        found = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                found.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                base = self._absolute(node.module or "", node.level)
                if base:
                    found.add(base)
                    # "from cells.models import surface_pump" names a module, not a constant.
                    found.update(f"{base}.{alias.name}" for alias in node.names)
        return found

    def line_count(self):
        return self.source.count("\n") + (0 if self.source.endswith("\n") or not self.source else 1)


class Package:
    """A source tree (src/cells) addressed by dotted module name."""

    def __init__(self, root, name):
        self.root = Path(root)
        self.name = name
        self._modules = {}

    def path_of(self, dotted):
        if dotted != self.name and not dotted.startswith(self.name + "."):
            return None
        relative = dotted.split(".")[1:]
        base = self.root.joinpath(*relative)
        if base.with_suffix(".py").is_file():
            return base.with_suffix(".py")
        if (base / "__init__.py").is_file():
            return base / "__init__.py"
        return None

    def module(self, dotted):
        if dotted not in self._modules:
            path = self.path_of(dotted)
            self._modules[dotted] = Module(self, dotted, path) if path else None
        return self._modules[dotted]

    def dotted_of(self, path):
        relative = Path(path).resolve().relative_to(self.root.resolve()).with_suffix("")
        parts = [self.name, *relative.parts]
        if parts[-1] == "__init__":
            parts.pop()
        return ".".join(parts)


class Evaluator:
    def __init__(self, package):
        self.package = package

    # ------------------------------------------------------------ public

    def constant(self, module, name):
        """The value of a module-level name, following imports within the package."""
        return self._name(name, module, {}, 0)

    def class_attributes(self, module, class_name, names=None):
        """{attribute: value} over the class and its bases; unresolved ones map to None.

        Returns (values, unresolved), where unresolved lists the attributes present in
        source that could not be evaluated.
        """
        values, unresolved = {}, []
        for owner_module, node in reversed(self._lineage(module, class_name)):
            # A class body sees its own earlier bindings, then the module: inherited
            # attributes are not in scope (LAW_ID = LAW_ID reads the module's constant).
            local = {}
            for statement in node.body:
                if isinstance(statement, ast.Assign):
                    targets, value = statement.targets, statement.value
                elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
                    targets, value = [statement.target], statement.value
                else:
                    continue
                for target in targets:
                    if not isinstance(target, ast.Name):
                        continue
                    if names is not None and target.id not in names:
                        continue
                    try:
                        values[target.id] = self._eval(value, owner_module, local, 0)
                        local[target.id] = values[target.id]
                        if target.id in unresolved:
                            unresolved.remove(target.id)
                    except Unresolved:
                        values[target.id] = None
                        if target.id not in unresolved:
                            unresolved.append(target.id)
        return values, unresolved

    # ------------------------------------------------------------ classes

    def _lineage(self, module, class_name):
        """[(module, ClassDef)] from the class up through its resolvable bases."""
        seen, order, queue = set(), [], [(module, class_name)]
        while queue:
            owner, name = queue.pop(0)
            located = self._locate_class(owner, name)
            if located is None or id(located[1]) in seen:
                continue
            seen.add(id(located[1]))
            order.append(located)
            for base in located[1].bases:
                if isinstance(base, ast.Name):
                    queue.append((located[0], base.id))
                elif isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name):
                    target = located[0].imports.get(base.value.id)
                    if target and target[0] == "name":
                        sub = self.package.module(f"{target[1]}.{target[2]}")
                        if sub:
                            queue.append((sub, base.attr))
                    elif target and target[0] == "module":
                        sub = self.package.module(target[1])
                        if sub:
                            queue.append((sub, base.attr))
        return order

    def _locate_class(self, module, name):
        if name in module.classes:
            return module, module.classes[name]
        target = module.imports.get(name)
        if target and target[0] == "name":
            source = self.package.module(target[1])
            if source:
                return self._locate_class(source, target[2])
        return None

    # ------------------------------------------------------------ names

    def _name(self, name, module, local, depth):
        if depth > MAX_DEPTH:
            raise Unresolved(f"recursion at {name}")
        if name in local:
            return local[name]
        if name in module.env:
            return self._eval(module.env[name], module, {}, depth + 1)
        if name in module.classes:
            return ClassRef(module, module.classes[name])
        if name in module.imports:
            kind, dotted, *rest = module.imports[name]
            if kind == "module":
                target = self.package.module(dotted)
                return ModuleRef(target) if target else ExternalRef(dotted)
            source = self.package.module(dotted)
            if source is None:
                if rest[0] in SAFE_CALLS:  # from types import MappingProxyType
                    return SAFE_CALLS[rest[0]]
                return Symbol(f"{dotted}.{rest[0]}")
            submodule = self.package.module(f"{dotted}.{rest[0]}")
            if rest[0] not in source.env and rest[0] not in source.classes and submodule:
                if rest[0] not in source.imports:
                    return ModuleRef(submodule)
            return self._name(rest[0], source, {}, depth + 1)
        if name in SAFE_CALLS:
            return SAFE_CALLS[name]
        raise Unresolved(name)

    # ------------------------------------------------------------ expressions

    def _eval(self, node, module, local, depth):
        if depth > MAX_DEPTH:
            raise Unresolved("depth")
        step = depth + 1
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return self._name(node.id, module, local, step)
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            items = []
            for element in node.elts:
                if isinstance(element, ast.Starred):
                    items.extend(self._eval(element.value, module, local, step))
                else:
                    items.append(self._eval(element, module, local, step))
            if isinstance(node, ast.Tuple):
                return tuple(items)
            return items if isinstance(node, ast.List) else set(items)
        if isinstance(node, ast.Dict):
            result = {}
            for key, value in zip(node.keys, node.values):
                if key is None:
                    result.update(self._eval(value, module, local, step))
                else:
                    result[self._eval(key, module, local, step)] = self._eval(
                        value, module, local, step
                    )
            return result
        if isinstance(node, ast.Attribute):
            base = self._eval(node.value, module, local, step)
            if isinstance(base, ModuleRef):
                return self._name(node.attr, base.module, {}, step)
            if isinstance(base, ExternalRef):
                return Symbol(f"{base.dotted}.{node.attr}")
            if isinstance(base, Symbol):
                return Symbol(f"{base.text}.{node.attr}")
            if isinstance(base, ClassRef):
                values, _ = self.class_attributes(base.module, base.node.name, {node.attr})
                if values.get(node.attr) is None:
                    raise Unresolved(f"{base.node.name}.{node.attr}")
                return values[node.attr]
            raise Unresolved(f"attribute {node.attr}")
        if isinstance(node, ast.Call):
            return self._call(node, module, local, step)
        if isinstance(node, ast.BinOp):
            left = self._eval(node.left, module, local, step)
            right = self._eval(node.right, module, local, step)
            try:
                if isinstance(node.op, ast.Add):
                    return left + right
                if isinstance(node.op, ast.BitOr):
                    return {**left, **right} if isinstance(left, dict) else left | right
                if isinstance(node.op, ast.Sub):
                    return left - right
                if isinstance(node.op, ast.Mult):
                    return left * right
                if isinstance(node.op, ast.Mod):
                    return left % right
            except Exception as error:  # A type this evaluator does not model.
                raise Unresolved(str(error)) from error
            raise Unresolved("operator")
        if isinstance(node, ast.UnaryOp):
            value = self._eval(node.operand, module, local, step)
            if isinstance(node.op, ast.Not):
                return not value
            if isinstance(node.op, ast.USub):
                return -value
            raise Unresolved("unary")
        if isinstance(node, ast.BoolOp):
            values = [self._eval(value, module, local, step) for value in node.values]
            if isinstance(node.op, ast.And):
                result = True
                for value in values:
                    result = result and value
                return result
            result = False
            for value in values:
                result = result or value
            return result
        if isinstance(node, ast.Compare):
            return self._compare(node, module, local, step)
        if isinstance(node, ast.IfExp):
            chosen = node.body if self._eval(node.test, module, local, step) else node.orelse
            return self._eval(chosen, module, local, step)
        if isinstance(node, ast.Subscript):
            base = self._eval(node.value, module, local, step)
            if isinstance(node.slice, ast.Slice):
                bounds = [
                    None if part is None else self._eval(part, module, local, step)
                    for part in (node.slice.lower, node.slice.upper, node.slice.step)
                ]
                index = slice(*bounds)
            else:
                index = self._eval(node.slice, module, local, step)
            try:
                return base[index]
            except Exception as error:
                raise Unresolved(str(error)) from error
        if isinstance(node, ast.JoinedStr):
            parts = []
            for value in node.values:
                if isinstance(value, ast.FormattedValue):
                    if value.format_spec is not None or value.conversion != -1:
                        raise Unresolved("format spec")
                    parts.append(str(self._eval(value.value, module, local, step)))
                else:
                    parts.append(str(value.value))
            return "".join(parts)
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            return self._comprehension(node, module, local, step)
        raise Unresolved(type(node).__name__)

    def _compare(self, node, module, local, depth):
        left = self._eval(node.left, module, local, depth)
        for operator, comparator in zip(node.ops, node.comparators):
            right = self._eval(comparator, module, local, depth)
            checks = {
                ast.Eq: lambda a, b: a == b,
                ast.NotEq: lambda a, b: a != b,
                ast.In: lambda a, b: a in b,
                ast.NotIn: lambda a, b: a not in b,
                ast.Lt: lambda a, b: a < b,
                ast.LtE: lambda a, b: a <= b,
                ast.Gt: lambda a, b: a > b,
                ast.GtE: lambda a, b: a >= b,
                ast.Is: lambda a, b: a is b,
                ast.IsNot: lambda a, b: a is not b,
            }
            check = checks.get(type(operator))
            if check is None:
                raise Unresolved("comparison")
            try:
                if not check(left, right):
                    return False
            except Exception as error:
                raise Unresolved(str(error)) from error
            left = right
        return True

    def _call(self, node, module, local, depth):
        arguments = []
        for argument in node.args:
            if isinstance(argument, ast.Starred):
                arguments.extend(self._eval(argument.value, module, local, depth))
            else:
                arguments.append(self._eval(argument, module, local, depth))
        keywords = {}
        for keyword in node.keywords:
            value = self._eval(keyword.value, module, local, depth)
            if keyword.arg is None:
                keywords.update(value)
            else:
                keywords[keyword.arg] = value
        if isinstance(node.func, ast.Attribute):
            base = self._eval(node.func.value, module, local, depth)
            allowed = next(
                (names for kind, names in SAFE_METHODS.items() if isinstance(base, kind)), ()
            )
            if node.func.attr not in allowed:
                raise Unresolved(f"method {node.func.attr}")
            try:
                return getattr(base, node.func.attr)(*arguments, **keywords)
            except Exception as error:
                raise Unresolved(str(error)) from error
        function = self._eval(node.func, module, local, depth)
        if function not in SAFE_CALLS.values():
            raise Unresolved("call")
        try:
            result = function(*arguments, **keywords)
        except Exception as error:
            raise Unresolved(str(error)) from error
        if isinstance(result, (zip, range, enumerate, reversed)):
            return list(result)
        return result

    def _comprehension(self, node, module, local, depth):
        results = []

        def assign(target, value, scope):
            if isinstance(target, ast.Name):
                scope[target.id] = value
            elif isinstance(target, (ast.Tuple, ast.List)):
                values = list(value)
                if len(values) != len(target.elts):
                    raise Unresolved("unpack")
                for sub_target, sub_value in zip(target.elts, values):
                    assign(sub_target, sub_value, scope)
            else:
                raise Unresolved("target")

        def run(index, scope):
            if index == len(node.generators):
                if isinstance(node, ast.DictComp):
                    results.append(
                        (
                            self._eval(node.key, module, scope, depth),
                            self._eval(node.value, module, scope, depth),
                        )
                    )
                else:
                    results.append(self._eval(node.elt, module, scope, depth))
                return
            generator = node.generators[index]
            iterable = self._eval(generator.iter, module, scope, depth)
            if isinstance(iterable, dict):
                iterable = list(iterable)
            try:
                items = list(iterable)
            except TypeError as error:
                raise Unresolved(str(error)) from error
            for item in items:
                inner = dict(scope)
                assign(generator.target, item, inner)
                if all(self._eval(test, module, inner, depth) for test in generator.ifs):
                    run(index + 1, inner)

        run(0, dict(local))
        if isinstance(node, ast.DictComp):
            return dict(results)
        if isinstance(node, ast.SetComp):
            return set(results)
        return results


def plain(value):
    """A JSON-ready copy: tuples and sets become lists, symbols become text."""
    if isinstance(value, dict):
        return {str(plain(key)): plain(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted((plain(item) for item in value), key=str)
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    if isinstance(value, (Symbol, ModuleRef, ExternalRef, ClassRef)):
        return repr(value) if isinstance(value, Symbol) else type(value).__name__
    return value
