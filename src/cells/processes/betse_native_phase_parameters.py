"""Fresh original Parameters construction, explicitly unloaded and phase-held.

This separate birth neither upgrades an existing selected parameter object nor
loads YAML/paths/ions. Its live native object is not a phase or INIT authority.
"""

import ast
import builtins
import dis
import hashlib
import importlib
import operator
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from threading import RLock, get_ident
from types import CodeType, FunctionType, ModuleType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_simulator_construction as inherited

LAW_ID = "betse_native_fresh_unloaded_parameters_constructor@1"
SIMULATOR_SHA256 = "6f94d0cf79191c952a7055a63865080ffe1693c8798c6ee73aa24ad24c8d5884"
PARAMETERS = "betse/science/parameters.py"
YAML_FILE = "betse/lib/yaml/abc/yamlfileabc.py"
YAML_BASE = "betse/lib/yaml/abc/yamlabc.py"
RETURN_NONE_WRAPPER_PINS = (
    (
        "beartype._check.error.errmain",
        "96c94fbfb6dd3a132014347e7878dac009f01a5f8c99f51499a69f04d27b82b8",
    ),
    (
        "beartype._check.metadata.metacheck",
        "029a5dab742c77b1a3cc44fd75751a35cb5664913bc5499374de6abc1e74e558",
    ),
    ("beartype._conf.confmain", "4fbe9f5482c9f82b98737e91c3b4b6d3e338342906863d4bfcad8d98eb0ddf22"),
    (
        "beartype.claw._clawstate",
        "26d127daefb8ac782caf31e91e6e8004d87ef472d4dfc515152d3164a87b2efe",
    ),
    (
        "beartype.claw._importlib.clawimpcache",
        "77ea6518ebfd478a755bafd79dc7fb873afe7204cf30bf3bb9ca38e6c2cf0f8c",
    ),
)
_ROSTER = (
    "cut_profiles",
    "tissue_default",
    "tissue_profiles",
    "anim",
    "csv",
    "plot",
    "visual",
    "grn",
)
_REQUESTS, _CONSUMED, _ISSUED = (WeakKeyDictionary() for _ in range(3))
_YAML_LEASES = WeakKeyDictionary()
YAML_PREFIX_LAW = "betse_native_parameter_yaml_read_prefix@1"
_LOCK, _ACTIVE = RLock(), []


class ParameterRejected(ValueError):
    def __init__(
        self,
        reason,
        *,
        stage,
        request=None,
        partial=None,
        trial=None,
        source_error=None,
        capture_errors=(),
    ):
        super().__init__(reason)
        self.stage, self.request, self.partial, self.trial = stage, request, partial, trial
        self.source_error, self.capture_errors = source_error, tuple(capture_errors)


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    run_id: str
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("Live parameter birth requests cannot be serialized")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    cache: object
    work: tuple
    source_completed: bool
    identity: str


def source_plan():
    if hashlib.sha256(Path(inherited.__file__).read_bytes()).hexdigest() != SIMULATOR_SHA256:
        raise ValueError("Explicit existing source/capture producer required")
    plan = inherited.source_plan()
    path = inherited.tissue.aliases.NATIVE / PARAMETERS
    cls = inherited._class(ast.parse(path.read_bytes()), "Parameters")
    init = inherited._method(cls, "__init__")
    unload = inherited._method(cls, "_unload_paths")
    stores = tuple(
        n.targets[0].attr
        for n in init.body
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Attribute)
    )
    if stores != _ROSTER:
        raise ValueError("Original native parameter subconfiguration construction order changed")
    if any(
        not isinstance(n.value, ast.Constant) or n.value.value is not None
        for n in unload.body
        if isinstance(n, ast.Assign)
    ):
        raise ValueError("Original unloaded native path stores changed")
    paths = tuple(n.targets[0].attr for n in unload.body if isinstance(n, ast.Assign))
    return dict(
        law=LAW_ID,
        native_pins=plan["native_pins"],
        simulator_sha256=SIMULATOR_SHA256,
        return_none_wrapper_pins=dict(RETURN_NONE_WRAPPER_PINS),
        constructor_lines=(init.lineno, init.end_lineno),
        path_fields=paths,
        subconfigurations=_ROSTER,
        fresh_birth=True,
        existing_selected_parameter_or_tissue_owner_adopted=False,
        constructor_arguments="none; original unloaded no-file branch",
        phase_prerequisites=(
            "original YAML/file/compatibility/path load on this exact native Parameters instance",
            "genuine same-parameter tissue, Cells and phase construction in original source order",
            "native ion/material init_core and profile mapping before positive INIT",
        ),
        loaded_Parameters_or_phase_or_INIT_authority=False,
    )


def request_record(request):
    return dict(
        law=LAW_ID,
        run_id=request.run_id,
        fresh_native_birth=True,
        supplied_state_or_parameter_or_configuration=False,
        loaded=False,
    )


def declare(*, law_id, run_id):
    if (
        type(law_id) is not str
        or law_id != LAW_ID
        or type(run_id) is not str
        or not run_id
        or len(run_id) > 256
    ):
        raise ParameterRejected(
            "Explicit source law and bounded declared run ID required", stage="request"
        )
    request = Request(run_id, "")
    request = replace(
        request, identity=inherited.tissue.core.records._digest(request_record(request))
    )
    _REQUESTS[request] = request.identity
    return request


_COMPILATION_MAX_BYTES = 4 * 2**20
_COMPILATION_MAX_NODES = 100000
_COMPILATION_MAX_CODES = 100000
_COMPILATION_MAX_CLASS_PLAN = 16384
_COMPILATION_ATTRGETTER = operator.attrgetter
_COMPILATION_ITEMGETTER = operator.itemgetter


def _compilation_function_record(function):
    """Seal callable metadata at import, without executing a source body."""
    namespace, cached = function.__globals__, function.__builtins__
    names, pending = set(), [function.__code__]
    while pending:
        code = pending.pop()
        names.update(
            instruction.argval
            for instruction in dis.get_instructions(code)
            if instruction.opname == "LOAD_GLOBAL"
        )
        pending.extend(value for value in code.co_consts if type(value) is CodeType)
    # Self-referential records are independently anchored after publication.
    # Their anchors are checked explicitly, never reconstructed from live data.
    names.difference_update(
        (
            "_COMPILATION_RECORDS",
            "_CONTEXT_RECORDS",
            "_compilation_record_anchor",
            "_COMPILATION_ANCHOR",
            "_COMPILATION_ANCHOR_CODE",
            "_COMPILATION_ANCHOR_DEFAULTS",
            "_context_record_anchor",
            "_CONTEXT_ANCHOR",
            "_CONTEXT_ANCHOR_CODE",
            "_CONTEXT_ANCHOR_DEFAULTS",
        )
    )
    keywords = function.__kwdefaults__
    return (
        function,
        function.__code__,
        namespace,
        cached,
        function.__defaults__,
        keywords,
        None if keywords is None else tuple(keywords.items()),
        function.__closure__,
        tuple(cell.cell_contents for cell in function.__closure__ or ()),
        tuple(
            (name, name in namespace, namespace.get(name), name in cached, cached.get(name))
            for name in sorted(names)
        ),
    )


def _compilation_validate(records):
    """Compare identities, including equal-code replacements and resolved globals."""
    for (
        function,
        code,
        namespace,
        cached,
        defaults,
        keywords,
        items,
        closure,
        cells,
        names,
    ) in records:
        declared = namespace.get("__builtins__")
        declared = vars(declared) if type(declared) is ModuleType else declared
        if (
            type(function) is not FunctionType
            or function.__code__ is not code
            or function.__globals__ is not namespace
            or function.__builtins__ is not cached
            or declared is not cached
            or function.__defaults__ is not defaults
            or function.__kwdefaults__ is not keywords
            or function.__closure__ is not closure
            or len(function.__closure__ or ()) != len(cells)
            or any(
                cell.cell_contents is not old
                for cell, old in zip(closure or (), cells, strict=True)
            )
        ):
            raise ValueError("Original source compiler callable/code/defaults required")
        if keywords is not None:
            current = tuple(dict.items(keywords))
            if len(current) != len(items) or any(
                key is not old_key or value is not old_value
                for (key, value), (old_key, old_value) in zip(current, items, strict=True)
            ):
                raise ValueError("Original source compiler keyword-default items required")
        for name, present, value, builtin_present, builtin_value in names:
            if (
                (name in namespace) is not present
                or namespace.get(name) is not value
                or (name in cached) is not builtin_present
                or cached.get(name) is not builtin_value
            ):
                raise ValueError("Original source compiler resolved globals/builtins required")


def _compilation_key(payload, filename, optimize):
    if (
        type(payload) is not bytes
        or len(payload) > _COMPILATION_MAX_BYTES
        or type(filename) is not str
        or type(optimize) is not int
        or optimize not in (-1, 0, 1, 2)
    ):
        raise ValueError("Bounded exact source bytes/filename/optimization required")


def _compilation_class_plan(node):
    """Data-only selectors/values; retain no AST node or callable in the LRU."""
    rows, pending, accesses = [None], [(node, 0)], {}
    primitive = (str, bytes, int, bool, type(None), float, complex, type(Ellipsis))
    while pending:
        value, index = pending.pop()
        cls = type(value)
        if isinstance(value, ast.AST):
            if type(cls) is not type or cls.__module__ != "ast":
                return ()
            fields, attributes = value._fields, value._attributes
            if (
                type(cls.__name__) is not str
                or type(fields) is not tuple
                or type(attributes) is not tuple
                or any(type(name) is not str for name in (*fields, *attributes))
            ):
                return ()
            names = (*fields, *attributes)
            if names:
                accesses[id(cls)] = names
            getter = _COMPILATION_ATTRGETTER(*names) if names else None
            try:
                values = () if getter is None else getter(value)
            except AttributeError:
                return ()
            if len(names) == 1:
                values = (values,)
            header = ("node", id(cls), cls.__name__, fields, attributes, names)
            none_defaults = tuple(
                (position, int(getattr(cls, names[position], ...) is None))
                for position, current in enumerate(values)
                if current is None
            )
            empty_fields = tuple(
                (
                    position,
                    int(getattr(cls._field_types.get(name, object), "__origin__", ...) is list),
                )
                for position, name in enumerate(fields)
                if type(values[position]) is list and not values[position]
            )
        elif cls is list:
            values, header = value, ("list", len(value))
            none_defaults = empty_fields = ()
        else:
            return ()
        scalar_positions, scalar_values, floating, float_values, children = [], [], [], [], []
        for position, current in enumerate(values):
            current_type = type(current)
            if isinstance(current, ast.AST) or current_type is list:
                child = len(rows)
                rows.append(None)
                children.append((position, child))
                pending.append((current, child))
            elif current_type in primitive:
                if current_type in (float, complex, bytes):
                    floating.append(position)
                    float_values.append(repr(current))
                elif current is not None and current is not Ellipsis:
                    scalar_positions.append(position)
                    scalar_values.append(int(current) if current_type is bool else current)
            else:
                return ()
        rows[index] = (
            header,
            tuple(map(id, map(type, values))),
            tuple(scalar_positions),
            tuple(scalar_values),
            tuple(floating),
            tuple(float_values),
            tuple(children),
            none_defaults,
            empty_fields,
        )
        # Unsupported/large fast plans fall back to the unchanged full dump.
        if len(rows) > _COMPILATION_MAX_CLASS_PLAN:
            return ()
    return tuple(rows), tuple(accesses.items())


def _compilation_class_matches(node, plan):
    """Fast positive proof; all mismatches keep the original dump comparison."""
    if not plan:
        return False
    rows = plan[0]
    classes = {
        id(value): value for namespace, _name, value in _COMPILATION_ATTRIBUTES if namespace is ast
    }

    def plain_fields():
        # A batched getter must never invoke a later field descriptor before
        # the legacy dump would format an earlier field. Such metadata uses
        # the original traversal, including its primary-exception ordering.
        for type_id, names in plan[1]:
            cls = classes.get(type_id)
            if cls is None:
                return False
            for base in cls.__mro__:
                namespace = vars(base)
                if any(namespace.get(name) is not None for name in names):
                    return False
        return True

    if not plain_fields():
        return False
    pending, attributes_cache, positions_cache = [(node, 0)], {}, {}
    while pending:
        value, index = pending.pop()
        (
            header,
            types,
            selector,
            expected,
            float_selector,
            floats,
            children,
            none_defaults,
            empty_fields,
        ) = rows[index]
        if header[0] == "node":
            _, type_id, name, fields, attributes, names = header
            cls = type(value)
            if (
                id(cls) != type_id
                or value.__class__ is not cls
                or type(cls.__name__) is not str
                or cls.__name__ != name
                or (
                    value._fields is not fields
                    and (
                        type(value._fields) is not tuple
                        or any(type(label) is not str for label in value._fields)
                        or value._fields != fields
                    )
                )
                or (
                    value._attributes is not attributes
                    and (
                        type(value._attributes) is not tuple
                        or any(type(label) is not str for label in value._attributes)
                        or value._attributes != attributes
                    )
                )
            ):
                return False
            if not names:
                continue
            getter = attributes_cache.get(names)
            if getter is None and names:
                getter = _COMPILATION_ATTRGETTER(*names)
                attributes_cache[names] = getter
            try:
                values = () if getter is None else getter(value)
            except AttributeError:
                return False
            if len(names) == 1:
                values = (values,)
            if none_defaults and any(
                int(getattr(cls, names[position], ...) is None) != old
                for position, old in none_defaults
            ):
                return False
            if empty_fields and any(
                int(
                    getattr(cls._field_types.get(names[position], object), "__origin__", ...)
                    is list
                )
                != old
                for position, old in empty_fields
            ):
                return False
        else:
            if type(value) is not list or len(value) != header[1]:
                return False
            if not value:
                continue
            values = value
        if tuple(map(id, map(type, values))) != types:
            return False
        if selector:
            getter = positions_cache.get(selector)
            if getter is None:
                getter = _COMPILATION_ITEMGETTER(*selector)
                positions_cache[selector] = getter
            actual = getter(values)
            if len(expected) == 1:
                actual = (actual,)
            if actual != expected:
                return False
        if float_selector:
            getter = positions_cache.get(float_selector)
            if getter is None:
                getter = _COMPILATION_ITEMGETTER(*float_selector)
                positions_cache[float_selector] = getter
            actual = getter(values)
            if len(floats) == 1:
                actual = (actual,)
            if tuple(map(repr, actual)) != floats:
                return False
        if children:
            pending.extend((values[position], child) for position, child in children)
    return plain_fields()


@lru_cache(maxsize=16, typed=True)
def _compilation_metadata(payload, filename, optimize):
    """Only code/closed AST metadata; no owner or successful validation cache."""
    guard = _compilation_contract
    if guard is not _COMPILATION_CONTRACT or guard.__code__ is not _COMPILATION_CONTRACT_CODE:
        raise ValueError("Original source compilation guard required")
    guard()
    _compilation_key(payload, filename, optimize)
    compiler = compile
    tree = ast.parse(payload, filename=filename)
    pending, functions, visited = [(tree, "")], [], 0
    while pending:
        node, scope = pending.pop()
        visited += 1
        if visited > _COMPILATION_MAX_NODES:
            raise ValueError("Bounded compiler AST exhausted")
        nested = scope
        if type(node) in (ast.FunctionDef, ast.AsyncFunctionDef):
            qualified = scope + node.name
            functions.append(
                (
                    node.name,
                    node.lineno,
                    node.col_offset,
                    ast.dump(node, include_attributes=True),
                    qualified,
                    min([node.lineno, *(value.lineno for value in node.decorator_list)]),
                )
            )
            nested = qualified + ".<locals>."
        elif type(node) is ast.ClassDef:
            nested = scope + node.name + "."
        pending.extend((child, nested) for child in ast.iter_child_nodes(node))
    classes = tuple(
        (node.name, ast.dump(node, include_attributes=True), _compilation_class_plan(node))
        for node in tree.body
        if isinstance(node, ast.ClassDef)
    )
    if guard is not _compilation_contract or guard.__code__ is not _COMPILATION_CONTRACT_CODE:
        raise ValueError("Original source compilation guard required")
    guard()
    compiled = compiler(tree, filename, "exec", dont_inherit=True, optimize=optimize)
    if guard is not _compilation_contract or guard.__code__ is not _COMPILATION_CONTRACT_CODE:
        raise ValueError("Original source compilation guard required")
    guard()
    pending, codes = [compiled], []
    while pending:
        code = pending.pop()
        codes.append((code.co_qualname, code.co_firstlineno, code))
        if len(codes) > _COMPILATION_MAX_CODES:
            raise ValueError("Bounded compiled-code traversal exhausted")
        pending.extend(value for value in code.co_consts if type(value) is CodeType)
    if guard is not _compilation_contract or guard.__code__ is not _COMPILATION_CONTRACT_CODE:
        raise ValueError("Original source compilation guard required")
    guard()
    return compiled, classes, tuple(functions), tuple(codes), visited


def _compilation_contract():
    validator = _compilation_validate
    if (
        _compilation_contract is not _COMPILATION_CONTRACT
        or _compilation_contract.__code__ is not _COMPILATION_CONTRACT_CODE
        or validator is not _COMPILATION_VALIDATOR
        or validator.__code__ is not _COMPILATION_VALIDATOR_CODE
        or _compilation_metadata is not _COMPILATION_CACHE
        or _compilation_metadata.__wrapped__ is not _COMPILATION_BODY
        or Path.__mro__ is not _COMPILATION_PATH_MRO
        or _compilation_record_anchor is not _COMPILATION_ANCHOR
        or _compilation_record_anchor.__code__ is not _COMPILATION_ANCHOR_CODE
        or _compilation_record_anchor.__defaults__ is not _COMPILATION_ANCHOR_DEFAULTS
        or _compilation_record_anchor.__kwdefaults__ is not None
        or _compilation_record_anchor.__closure__ is not None
        or _COMPILATION_RECORDS is not _COMPILATION_ANCHOR_DEFAULTS[0]
    ):
        raise ValueError("Original source compilation cache/guard/delegate required")
    current = tuple(vars(_compilation_metadata).items())
    if len(current) != len(_COMPILATION_CACHE_ITEMS) or any(
        key is not old_key or value is not old_value
        for (key, value), (old_key, old_value) in zip(
            current, _COMPILATION_CACHE_ITEMS, strict=True
        )
    ):
        raise ValueError("Original source compilation cache wrapper required")
    for namespace, name, value in _COMPILATION_ATTRIBUTES:
        current = (
            next((vars(base)[name] for base in namespace.__mro__ if name in vars(base)), None)
            if type(namespace) is type
            else vars(namespace).get(name)
        )
        if current is not value:
            raise ValueError("Original source compilation helper attribute required")
    validator(_COMPILATION_RECORDS)
    return (), (
        _COMPILATION_CACHE,
        _COMPILATION_RECORDS,
        _COMPILATION_CACHE_ITEMS,
        _COMPILATION_ATTRIBUTES,
    )


def _compiled_source(payload, filename, *, optimize=-1):
    guard = _compilation_contract
    if guard is not _COMPILATION_CONTRACT or guard.__code__ is not _COMPILATION_CONTRACT_CODE:
        raise ValueError("Original source compilation guard required")
    guard()
    _compilation_key(payload, filename, optimize)
    value = _compilation_metadata(payload, filename, optimize)
    if guard is not _compilation_contract or guard.__code__ is not _COMPILATION_CONTRACT_CODE:
        raise ValueError("Original source compilation guard required")
    guard()
    return value


def _method_code(cls_node, name, filename, *, native_context=False):
    """Keep authentic module code distinct from deliberate selected AST slices."""
    if type(native_context) is not bool:
        raise ValueError("Explicit native compilation context required")
    if native_context:
        guard = _compilation_contract
        if guard is not _COMPILATION_CONTRACT or guard.__code__ is not _COMPILATION_CONTRACT_CODE:
            raise ValueError("Original source compilation guard required")
        guard()
        path = Path(filename)
        if path.stat().st_size > _COMPILATION_MAX_BYTES:
            raise ValueError("Bounded complete compiler source exhausted")
        code, classes, _, _, _ = _compiled_source(path.read_bytes(), str(filename))
        original, plan = next(
            (value, plan) for class_name, value, plan in classes if class_name == cls_node.name
        )
        if not _compilation_class_matches(cls_node, plan) and (
            original != ast.dump(cls_node, include_attributes=True)
        ):
            raise ValueError("Exact original class AST required for native compilation context")
        if guard is not _compilation_contract or guard.__code__ is not _COMPILATION_CONTRACT_CODE:
            raise ValueError("Original source compilation guard required")
        guard()
    else:
        code = compile(
            ast.Module(body=[cls_node], type_ignores=[]), str(filename), "exec", dont_inherit=True
        )
    class_code = next(
        c for c in code.co_consts if type(c) is CodeType and c.co_name == cls_node.name
    )
    result = next(c for c in class_code.co_consts if type(c) is CodeType and c.co_name == name)
    if native_context:
        if guard is not _compilation_contract or guard.__code__ is not _COMPILATION_CONTRACT_CODE:
            raise ValueError("Original source compilation guard required")
        guard()
    return result


_COMPILATION_CACHE = _compilation_metadata
_COMPILATION_BODY = _compilation_metadata.__wrapped__
_COMPILATION_CACHE_ITEMS = tuple(vars(_compilation_metadata).items())
_COMPILATION_CONTRACT = _compilation_contract
_COMPILATION_CONTRACT_CODE = _compilation_contract.__code__
_COMPILATION_VALIDATOR = _compilation_validate
_COMPILATION_VALIDATOR_CODE = _compilation_validate.__code__
_COMPILATION_PATH_MRO = Path.__mro__
_COMPILATION_ATTRIBUTES = (
    tuple(
        (module, name, getattr(module, name))
        for module, names in (
            (
                ast,
                (
                    "parse",
                    "dump",
                    "iter_child_nodes",
                    "iter_fields",
                    "ClassDef",
                    "FunctionDef",
                    "AsyncFunctionDef",
                ),
            ),
            (Path, ("read_bytes", "stat", "open")),
            (operator, ("attrgetter", "itemgetter")),
        )
        for name in names
    )
    + tuple(
        (ast, name, value)
        for name, value in vars(ast).items()
        if type(value) is type and issubclass(value, ast.AST)
    )
    + tuple(
        (value, name, getattr(value, name, None))
        for value in vars(ast).values()
        if type(value) is type and issubclass(value, ast.AST)
        for name in ("__eq__", "__getattribute__", "__getattr__")
    )
)
_COMPILATION_RECORDS = tuple(
    _compilation_function_record(function)
    for function in (
        _compilation_function_record,
        _compilation_validate,
        _compilation_key,
        _compilation_class_plan,
        _compilation_class_matches,
        _COMPILATION_BODY,
        _compilation_metadata.cache_parameters,
        _compilation_contract,
        _compiled_source,
        _method_code,
        ast.parse,
        ast.dump,
        ast.iter_child_nodes,
        ast.iter_fields,
        Path.read_bytes,
        Path.stat,
        Path.open,
    )
)


def _compilation_record_anchor(records=_COMPILATION_RECORDS):
    """Independent immutable tuple anchor; never used as validation output."""
    return records


_COMPILATION_ANCHOR = _compilation_record_anchor
_COMPILATION_ANCHOR_CODE = _compilation_record_anchor.__code__
_COMPILATION_ANCHOR_DEFAULTS = _compilation_record_anchor.__defaults__


def _canonical(module, yaml):
    inherited.tissue.aliases._check_modules()
    cls = module.Parameters
    if (
        sys.modules.get("betse.science.parameters") is not module
        or Path(module.__file__).resolve() != inherited.tissue.aliases.NATIVE / PARAMETERS
        or cls.__module__ != module.__name__
        or cls.__bases__ != (yaml.YamlFileDefaultABC,)
    ):
        raise ValueError("Actual original Parameters class/module/base required")
    node = inherited._class(
        ast.parse((inherited.tissue.aliases.NATIVE / PARAMETERS).read_bytes()), "Parameters"
    )
    for name in ("__init__", "_unload_paths"):
        outer = getattr(cls, name)
        _method_wrapper_bindings(outer, cls)
        function = inherited._chain(outer)[-1]
        expected = _method_code(
            node, name, str(inherited.tissue.aliases.NATIVE / PARAMETERS), native_context=True
        )
        if (
            function.__globals__ is not vars(module)
            or function.__code__.co_filename != expected.co_filename
            or function.__code__.co_qualname != expected.co_qualname
            or inherited._code(function.__code__) != inherited._code(expected)
        ):
            raise ValueError("Native Parameters constructor executable changed")
        for key, cell in zip(
            function.__code__.co_freevars, function.__closure__ or (), strict=True
        ):
            if key == "__class__" and cell.cell_contents is not cls:
                raise ValueError("Original super/class closure association changed")
    return cls


def _return_none_wrapper_code(none_name):
    """Compile the selected beartype return-None wrapper without running it."""
    text = f"""def wrapper(*args,
    {none_name}=None, __beartype_get_violation=None, __beartype_conf=None,
    __beartype_check_meta=None, __beartype_func=None, **kwargs):
    __beartype_pith_0 = __beartype_func(*args, **kwargs)
    if True:
        if not isinstance(__beartype_pith_0, {none_name}):
            __beartype_violation = __beartype_get_violation(
                check_meta=__beartype_check_meta,
                pith_name='return', pith_value=__beartype_pith_0)
            raise __beartype_violation
    return __beartype_pith_0
"""
    code = compile(text, "<return-None-wrapper-metadata>", "exec", dont_inherit=True)
    return next(value for value in code.co_consts if type(value) is CodeType)


def _method_wrapper_bindings(function, cls):
    """Authenticate the reached wrapper and retain its mutable delegate edges.

    Package-wide beartype decoration is separate from the original method body.
    Only the observed return-None wrapper is admitted; arbitrary wrapped chains
    do not acquire original-source authority.
    """
    chain = inherited._chain(function)
    objects = list(inherited.tissue._factory_atoms(function))
    if len(chain) == 1:
        return tuple(objects)
    if len(chain) != 2:
        raise ValueError("Exact native return-None wrapper chain required")
    wrapper, original = chain
    none_name = "__beartype_object_" + str(id(type(None)))
    keys = (
        none_name,
        "__beartype_get_violation",
        "__beartype_conf",
        "__beartype_check_meta",
        "__beartype_func",
    )
    defaults = wrapper.__kwdefaults__
    if (
        type(defaults) is not dict
        or tuple(defaults) != keys
        or defaults[none_name] is not type(None)
        or defaults["__beartype_func"] is not original
        or vars(wrapper).get("__beartype_wrapper") is not True
        or set(vars(wrapper)) != {"__wrapped__", "__beartype_wrapper"}
        or wrapper.__defaults__ is not None
        or wrapper.__closure__ is not None
        or tuple(wrapper.__globals__) != ("__builtins__",)
        or wrapper.__builtins__ is not vars(builtins)
        or (
            wrapper.__globals__["__builtins__"] is not builtins
            and wrapper.__globals__["__builtins__"] is not vars(builtins)
        )
        or wrapper.__annotations__ is not original.__annotations__
        or tuple(original.__annotations__) != ("return",)
        or original.__annotations__["return"] is not None
        or inherited._code(wrapper.__code__)
        != inherited._code(_return_none_wrapper_code(none_name))
    ):
        raise ValueError("Original native return-None wrapper executable/delegate changed")
    modules = []
    for name, digest in RETURN_NONE_WRAPPER_PINS:
        module = sys.modules.get(name)
        if (
            type(module) is not ModuleType
            or hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() != digest
        ):
            raise ValueError("Pinned return-None wrapper library required")
        modules.append(module)
        objects.extend((module, vars(module)))
    errors, metadata, configuration, hook, hook_cache = modules
    violation = defaults["__beartype_get_violation"]
    meta, conf = defaults["__beartype_check_meta"], defaults["__beartype_conf"]
    if (
        violation is not errors.get_func_pith_violation
        or type(violation) is not FunctionType
        or violation.__globals__ is not vars(errors)
        or type(meta) is not metadata.BeartypeCheckMeta
        or type(conf) is not configuration.BeartypeConf
        or object.__getattribute__(meta, "func") is not original
        or object.__getattribute__(meta, "conf") is not conf
        or object.__getattribute__(meta, "func_annotations") is not original.__annotations__
    ):
        raise ValueError("Original return-None wrapper metadata associations changed")
    stack = object.__getattribute__(meta, "cls_stack")
    if type(stack) is not tuple or len(stack) != 1 or stack[0] is not cls:
        raise ValueError("Original return-None wrapper class stack changed")
    state = original.__globals__.get("__claw_state_beartype__")
    if state is not hook.claw_state or type(state) is not hook.BeartypeClawState:
        raise ValueError("Original parameter module import-hook state changed")
    configurations = object.__getattribute__(state, "module_name_to_beartype_conf")
    if (
        type(configurations) is not hook_cache.ModuleNameToBeartypeConf
        or dict.get(configurations, original.__globals__.get("__name__")) is not conf
        or object.__getattribute__(conf, "_is_violation_return_warn") is not False
    ):
        raise ValueError("Original parameter module import-hook configuration changed")
    objects.extend((state, type(state), configurations, type(configurations), conf))
    library_code = compile(
        Path(errors.__file__).read_bytes(), errors.__file__, "exec", dont_inherit=True
    )
    helpers = (violation, errors.get_hint_object_violation)
    for helper, name, defaults in (
        (helpers[0], "get_func_pith_violation", None),
        (helpers[1], "get_hint_object_violation", (None,) * 5),
    ):
        expected = next(
            c for c in library_code.co_consts if type(c) is CodeType and c.co_name == name
        )
        if (
            type(helper) is not FunctionType
            or helper.__globals__ is not vars(errors)
            or inherited._code(helper.__code__) != inherited._code(expected)
            or helper.__code__.co_filename != expected.co_filename
            or (
                helper.__defaults__ is not None
                if defaults is None
                else type(helper.__defaults__) is not tuple
                or len(helper.__defaults__) != 5
                or any(item is not None for item in helper.__defaults__)
            )
            or helper.__kwdefaults__ is not None
            or helper.__closure__ is not None
        ):
            raise ValueError("Original return-None violation executable changed")
    objects.extend((meta, conf, stack, original.__annotations__))
    objects.extend(original.__annotations__.keys())
    objects.extend(original.__annotations__.values())
    for helper in helpers:
        objects.extend(inherited.tissue._factory_atoms(helper))
        for instruction in dis.get_instructions(helper):
            if instruction.opname == "LOAD_GLOBAL":
                key = instruction.argval
                namespace = helper.__globals__ if key in helper.__globals__ else helper.__builtins__
                objects.extend((key, namespace, *inherited.tissue._factory_atoms(namespace[key])))
    objects.extend(inherited.tissue._surface(type(meta)))
    objects.extend(inherited.tissue._surface(type(conf)))
    for name in type(conf).__slots__:
        if name == "_repr":  # Lazy presentation cache, never reached by this wrapper.
            continue
        value = object.__getattribute__(conf, name)
        objects.extend((name, value))
        if type(value) is dict:
            for key, item in value.items():
                objects.extend((key, item))
        elif type(value) is tuple:
            objects.extend(value)
    return tuple(objects)


def _method_original(source, name):
    """Return only the exact original body behind an authenticated class slot."""
    outer = vars(source.cls).get(name)
    if type(outer) is not FunctionType or getattr(source.cls, name) is not outer:
        raise ValueError("Original native Parameters method slot required")
    _method_wrapper_bindings(outer, source.cls)
    original = inherited._chain(outer)[-1]
    path = inherited.tissue.aliases.NATIVE / PARAMETERS
    cls = inherited._class(ast.parse(path.read_bytes()), "Parameters")
    expected = _method_code(cls, name, str(path), native_context=True)
    if (
        original.__globals__ is not vars(source.modules["betse.science.parameters"])
        or original.__defaults__ is not None
        or original.__kwdefaults__ is not None
        or original.__code__.co_filename != expected.co_filename
        or original.__code__.co_qualname != expected.co_qualname
        or inherited._code(original.__code__) != inherited._code(expected)
    ):
        raise ValueError("Original native Parameters method executable/header/globals changed")
    for name, cell in zip(original.__code__.co_freevars, original.__closure__ or (), strict=True):
        if name != "__class__" or cell.cell_contents is not source.cls:
            raise ValueError("Original native Parameters method class cell changed")
    namespace = original.__globals__["__builtins__"]
    if type(namespace) is not dict:
        namespace = vars(namespace)
    if namespace is not original.__builtins__:
        raise ValueError("Original native Parameters cached builtins changed")
    return original


def _acquired_parameter_methods(source):
    """Native acquisition must include the actual package-installed wrappers.

    Unwrapped functions remain useful for compile-only correspondence checks;
    they cannot pass this live acquisition boundary or replace retained slots.
    """
    for name in ("__init__", "_unload_paths", "load", "reload_paths"):
        if len(inherited._chain(vars(source.cls).get(name))) != 2:
            raise ValueError("Actual package-installed Parameters wrapper required")
        _method_original(source, name)


def _live_parameter_method_bindings(source):
    """Collect only still-installed wrappers, even after validation observers."""
    objects = []
    for name in ("__init__", "_unload_paths", "load", "reload_paths"):
        method = vars(source.cls).get(name)
        if len(inherited._chain(method)) != 2:
            raise ValueError("Live Parameters package wrapper required")
        objects.extend(_method_wrapper_bindings(method, source.cls))
        if vars(source.cls).get(name) is not method:
            raise ValueError("Live Parameters method changed during binding collection")
    return tuple(objects)


def _acquire():
    with inherited.tissue.aliases.issuing_native_imports(inherited.tissue.source.SOURCE_PINS):
        modules = {
            name: importlib.import_module(name)
            for name in (
                "betse.science.parameters",
                "betse.lib.yaml.abc.yamlfileabc",
                "betse.lib.yaml.abc.yamlabc",
            )
        }
    module = modules["betse.science.parameters"]
    yaml = modules["betse.lib.yaml.abc.yamlfileabc"]
    cls = _canonical(module, yaml)
    source = SimpleNamespace(
        modules=modules, cls=cls, yaml=modules["betse.lib.yaml.abc.yamlabc"].YamlABC
    )
    _acquired_parameter_methods(source)
    return source


def _runtime(source):
    module = source.modules["betse.science.parameters"]
    yaml = source.modules["betse.lib.yaml.abc.yamlfileabc"]
    if _canonical(module, yaml) is not source.cls:
        raise ValueError("Original native Parameters class identity changed")
    # Acquisition return observers run before the first retained baseline.
    # Reauthenticate here so they cannot turn an unwrapped slot into a baseline.
    _acquired_parameter_methods(source)
    objects = [source.cls, source.yaml]
    labels = []
    for name, module in source.modules.items():
        labels.append(name)
        objects.extend((module, vars(module)))
    objects.extend(inherited.tissue._surface(source.cls))
    objects.extend(inherited.tissue._surface(type(source.cls)))
    objects.extend(_live_parameter_method_bindings(source))
    return tuple(labels), tuple(objects)


def _birth_graph(context):
    """Closed native YAML object/container graph; arbitrary object state refuses."""
    objects = []
    nodes = []
    memo = {}
    visits = 0

    def visit(value, depth=0):
        nonlocal visits
        visits += 1
        if visits > 10000 or depth > 48:
            raise ValueError("Bounded unloaded parameter graph exhausted")
        if value is None or type(value) in (str, int, bool):
            return (type(value).__name__, value)
        if isinstance(value, type):
            objects.append(value)
            return ("class", value.__module__, value.__qualname__)
        if id(value) in memo:
            return ("ref", memo[id(value)])
        token = len(nodes)
        memo[id(value)] = token
        objects.extend((value, type(value)))
        node = dict(token=token, type=type(value).__module__ + "." + type(value).__qualname__)
        nodes.append(node)
        if isinstance(value, context.source.yaml):
            fields = vars(value)
            if fields.get("_conf", "missing") is not None:
                raise ValueError("Native birth must remain unloaded")
            objects.append(fields)
            node["fields"] = [(name, visit(item, depth + 1)) for name, item in fields.items()]
        elif type(value) is dict:
            node["fields"] = [
                (visit(key, depth + 1), visit(item, depth + 1)) for key, item in value.items()
            ]
        elif type(value) in (list, tuple):
            node["items"] = [visit(item, depth + 1) for item in value]
        else:
            raise ValueError("Unsupported/unowned unloaded parameter graph object")
        return ("ref", token)

    root = visit(context.p)
    return tuple(objects), dict(root=root, nodes=nodes)


def _snapshot(context):
    return inherited.tissue.core.caches.snapshot(_birth_graph(context)[1])


def _check(context):
    if (
        context.invalid
        or context.thread != get_ident()
        or _CONSUMED.get(context.request) is not context
        or _REQUESTS.get(context.request) != context.request.identity
        or inherited.tissue.core.records._digest(request_record(context.request))
        != context.request.identity
    ):
        raise ValueError("Original fresh native parameter attempt changed")
    inherited._same(_bindings(), context.bindings)
    if source_plan() != context.plan:
        raise ValueError("Native parameter producer changed")
    inherited._same(_runtime(context.source), context.runtime)
    if (
        type(context.p) is not context.source.cls
        or vars(context.p).get("_conf", "missing") is not None
        or any(
            vars(context.p).get(name, "missing") is not None for name in context.plan["path_fields"]
        )
        or any(name not in vars(context.p) for name in _ROSTER)
    ):
        raise ValueError("Original native unloaded parameter/result/path stores changed")


def trial_record(trial):
    return dict(
        law=LAW_ID,
        request=trial.request_identity,
        cache=trial.cache.identity,
        work=trial.work,
        source_completed=trial.source_completed,
        loaded_or_phase_admitted=False,
    )


class ParameterOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use fresh native parameter construction")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live native parameter owners cannot be serialized")

    @property
    def parameters(self):
        return _validate(self).p

    @property
    def trial(self):
        return _validate(self).trial


def _validate(owner):
    if type(owner) is not ParameterOwner or owner not in _ISSUED:
        raise ParameterRejected("Issued fresh native parameter owner required", stage="owner")
    context = _ISSUED[owner]
    try:
        if context.active or context.owner is not owner:
            raise ValueError("Active/replaced native parameter owner")
        _check(context)
        inherited._same_graph(_birth_graph(context), context.graph)
        if context.trial.cache.identity != _snapshot(
            context
        ).identity or context.trial.identity != inherited.tissue.core.records._digest(
            trial_record(context.trial)
        ):
            raise ValueError("Native constructor trial changed")
    except BaseException as error:
        context.invalid = True
        raise ParameterRejected(
            "Stale native parameter birth refused",
            stage="owner_drift",
            request=context.request,
            partial=context,
            trial=context.trial,
            source_error=error,
        ) from error
    return context


def _bindings():
    functions = (
        source_plan,
        request_record,
        declare,
        _method_code,
        _return_none_wrapper_code,
        _method_wrapper_bindings,
        _method_original,
        _acquired_parameter_methods,
        _live_parameter_method_bindings,
        _canonical,
        _acquire,
        _runtime,
        _birth_graph,
        _snapshot,
        _check,
        trial_record,
        _validate,
        _bindings,
        _invoke,
        _observe,
        _observe.__wrapped__,
        prepare,
        require_loaded,
        begin_yaml_prefix,
        _yaml_prefix_parent,
        inherited.tissue._account,
        inherited.tissue._account.__wrapped__,
        inherited.tissue._stop,
    )
    return (
        (),
        (
            _REQUESTS,
            _CONSUMED,
            _ISSUED,
            _YAML_LEASES,
            _LOCK,
            _ACTIVE,
            RETURN_NONE_WRAPPER_PINS,
            *_compilation_contract()[1],
            dis,
            dis.get_instructions,
            *(atom for fn in functions for atom in inherited.tissue.aliases._atoms(fn)),
        ),
    )


def _invoke(context):
    with inherited.tissue.aliases.issuing_native_imports(inherited.tissue.source.SOURCE_PINS):
        return context.source.cls()


@contextmanager
def _observe(context):
    """Protect the inherited hook without editing the shared tissue observer."""
    previous, trace = sys.getprofile(), sys.gettrace()

    def protected(frame, event, arg):
        if previous is None:
            return
        if event in {"return", "c_return", "c_exception"}:
            try:
                previous(frame, event, arg)
            except BaseException as error:
                label = "inherited_profile_" + context.stage + "_" + event
                inherited.tissue.captures._remember_observation_error(
                    context, error, origin=label, raw=frame
                )
                try:
                    context.locals[(label, frame.f_code.co_filename, frame.f_code.co_qualname)] = (
                        inherited._copy_locals(frame)
                    )
                except BaseException as capture:
                    inherited.tissue.captures._remember_observation_error(
                        context, capture, origin=label + "_locals", raw=frame
                    )
        else:
            previous(frame, event, arg)

    sys.setprofile(protected)
    try:
        with inherited.tissue._account(context):
            yield
    finally:
        sys.setprofile(previous)
        sys.settrace(trace)


def prepare(request, *, enabled=False):
    if enabled is not True or os.environ.get(inherited.RELEASE) != "1":
        raise ParameterRejected(
            "Actual native parameter constructor remains held", stage="release", request=request
        )
    with _LOCK:
        if _ACTIVE:
            _ACTIVE[-1].invalid = True
            raise ParameterRejected(
                "Reentrant parameter birth refused", stage="reentrant", request=request
            )
        if (
            type(request) is not Request
            or _REQUESTS.get(request) != request.identity
            or inherited.tissue.core.records._digest(request_record(request)) != request.identity
        ):
            raise ParameterRejected(
                "Issued fresh constructor request required", stage="request", request=request
            )
        if request in _CONSUMED:
            raise ParameterRejected(
                "Constructor request already consumed", stage="consumed", request=request
            )
        context = SimpleNamespace(
            request=request,
            thread=get_ident(),
            active=True,
            invalid=False,
            stage="native_import",
            work=[],
            locals={},
            observation_error=None,
            observation_errors=(),
            observation_origin=None,
            observation_raw=None,
            source_completed=False,
        )
        _CONSUMED[request] = context
        _ACTIVE.append(context)
        error = None
        try:
            context.bindings = _bindings()
            context.plan = source_plan()
            with _observe(context):
                context.source = _acquire()
            # Stop at the observed method boundary without throwing a sentinel
            # into the source catch. A source/entry _CaptureStop remains its
            # exact primary even when return observation also failed.
            if context.observation_error is None:
                context.runtime = _runtime(context.source)
                context.stage = "native_parameter_constructor"
                with _observe(context):
                    context.p = _invoke(context)
                context.source_completed = True
                if context.observation_error is None:
                    _check(context)
        except BaseException as primary:
            error = primary
        try:
            if error is None and context.observation_error is None:
                context.stage = "constructor_capture"
                cache = _snapshot(context)
                trial = Trial(request.identity, cache, tuple(context.work), True, "")
                context.trial = replace(
                    trial, identity=inherited.tissue.core.records._digest(trial_record(trial))
                )
                context.graph = _birth_graph(context)
                _check(context)
                owner = object.__new__(ParameterOwner)
                context.owner = owner
                _ISSUED[owner] = context
                return owner
        except BaseException as capture:
            inherited.tissue.captures._remember_observation_error(
                context, capture, origin=context.stage, raw=context
            )
        finally:
            context.active = False
            _ACTIVE.pop()
        context.invalid = True
        capture = context.observation_error
        refusal = ParameterRejected(
            "Native parameter birth issued no owner",
            stage=context.stage,
            request=request,
            partial=context,
            source_error=error,
            capture_errors=context.observation_errors,
        )
        raise refusal from (error if error is not None else capture)


def require_loaded(owner):
    context = _validate(owner)
    raise ParameterRejected(
        "Original YAML/file/path load and runtime parameter authorities unavailable",
        stage="loaded_parameters_prerequisites",
        request=context.request,
        trial=context.trial,
        partial=dict(
            missing=context.plan["phase_prerequisites"], loaded_or_phase_or_INIT_admitted=False
        ),
    )


class _YamlPrefixLease:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use a one-shot issued unloaded parameter handoff")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live YAML load leases cannot be serialized")


def begin_yaml_prefix(owner, *, law_id):
    """Retire the unloaded epoch before its same live p is mutated by reading."""
    if law_id != YAML_PREFIX_LAW or type(law_id) is not str:
        raise ParameterRejected("Explicit native YAML prefix consumer required", stage="consumer")
    if os.environ.get(inherited.RELEASE) != "1":
        raise ParameterRejected("Native YAML handoff remains held", stage="consumer")
    with _LOCK:
        context = _validate(owner)
        if context.active:
            raise ParameterRejected("Active parameter birth cannot be consumed", stage="consumer")
        context.invalid = True
        lease = object.__new__(_YamlPrefixLease)
        _YAML_LEASES[lease] = (owner, context)
        return lease


def _yaml_prefix_parent(lease):
    if type(lease) is not _YamlPrefixLease or lease not in _YAML_LEASES:
        raise ParameterRejected("Issued same-object YAML lease required", stage="consumer")
    return _YAML_LEASES[lease]
