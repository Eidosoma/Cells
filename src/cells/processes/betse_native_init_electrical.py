"""Original INIT current/field/voltage update after an issued storage reset.

The public entry stays closed until the actual storage continuation interface
and its producer review are bound. No supplied state, operator, phase or scalar
can substitute for that owner. The selected ordinary ECM path uses lapENVinv;
it neither reads nor repairs the distinct flux-boundary inverse.
"""

import ast
import builtins
import dis
import hashlib
import os
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import CodeType, FrameType, FunctionType, MappingProxyType, ModuleType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_init_electrical_source as source
from cells.processes import betse_native_init_storage as storage
from cells.processes import betse_native_world_phase_construction as interfaces

LAW_ID = "betse_actual_INIT_StorageOwner_update_V_ECM@1"
RELEASE = "CELLS_NATIVE_INIT_ELECTRICAL_RELEASED"
PARENT_SOURCE_SHA256 = '6f979cbea6d7ec2e88e7abf83ba3708802af44ba4c73583573efa44b89bc312b'
PARENT_REVIEW_SHA256 = '9fbcbe55bb36523f3025dec86c5c9f1e36360e20a33bfaf6a01eb728065b8e52'
PARENT_CLAIM = '_claim_for_electrical'
PARENT_CHECK = '_check_electrical_authority'
NATIVE = storage.NATIVE
MAX_WORK = 100000
_REQUESTS, _CONSUMED, _RETIRED, _ISSUED = (WeakKeyDictionary() for _ in range(4))
_FORWARDED, _FIRST_STEP_LEASES = WeakKeyDictionary(), WeakKeyDictionary()
_SHORT_INIT_LEASES = WeakKeyDictionary()
_TERMINAL_INIT_LEASES = WeakKeyDictionary()
FIRST_STEP_MODULE = "cells.processes.betse_native_init_first_step"
FIRST_STEP_INTERFACE_SHA256 = FIRST_STEP_REVIEW_SHA256 = None
FIRST_STEP_PARENT_REVIEW_SHA256 = None
FIRST_STEP_BINDING_KIND = "exact_INIT_first_step_except_two_electrical_backrefs@1"
SHORT_INIT_MODULE = "cells.processes.betse_native_init_short_history"
SHORT_INIT_INTERFACE_SHA256 = 'bf77d48ba4805ec86eddf482ff5d89a66f49227925e942aeb2ea2d3ce22378f5'
SHORT_INIT_REVIEW_SHA256 = '4325b04c3c425d0a0d9b0ef60c22859cdf524d13920c4b9c7eadb29e5caaafee'
SHORT_INIT_PARENT_REVIEW_SHA256 = '9fbcbe55bb36523f3025dec86c5c9f1e36360e20a33bfaf6a01eb728065b8e52'
SHORT_INIT_BINDING_KIND = "exact_INIT_short_history_except_two_electrical_backrefs@1"
TERMINAL_INIT_MODULE = "cells.processes.betse_native_init_terminal"
TERMINAL_INIT_INTERFACE_SHA256 = 'dde69f78e857bbc10d1b319764270fefe46b1886e069190e9d387687d5bac2f5'
TERMINAL_INIT_REVIEW_SHA256 = 'b7efb6935e042ad8e325c1dc5da35294345af509f2dd2ef24be7dceb057a0056'
TERMINAL_INIT_PARENT_REVIEW_SHA256 = '9fbcbe55bb36523f3025dec86c5c9f1e36360e20a33bfaf6a01eb728065b8e52'
TERMINAL_INIT_BINDING_KIND = "exact_INIT_natural_terminal_except_two_electrical_backrefs@1"
_ACTIVE, _FAILED, _LOCK = [], [], RLock()


class ElectricalRejected(ValueError):
    def __init__(self, reason, *, stage, request=None, trial=None, partial=None):
        super().__init__(reason)
        self.stage, self.request, self.trial, self.partial = stage, request, trial, partial


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    storage_owner: object
    parent_identity: str
    source_identity: str
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("An electrical request cannot be hydrated")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    parent_identity: str
    before: object
    after: object
    rng_before: tuple
    rng_after: tuple
    stores: tuple
    work: tuple
    helpers: tuple
    raw_returns: tuple
    completed: bool
    identity: str


@dataclass(frozen=True, slots=True)
class _ParentBinding:
    module: object
    claim: object
    check: object
    atoms: tuple


@dataclass(frozen=True, slots=True)
class _StepBinding:
    module: object
    functions: tuple


def _digest(value):
    return storage._digest(value)


def _definitions():
    """Compile the complete pinned modules without executing their imports."""
    trees, modules = {}, {}
    for filename, expected in source.SOURCE_PINS.items():
        path = NATIVE / filename
        payload = path.read_bytes()
        if path.is_symlink() or hashlib.sha256(payload).hexdigest() != expected:
            raise ValueError("Original electrical source changed: " + filename)
        trees[filename] = ast.parse(payload)
        modules[filename] = compile(payload, str(path), "exec", dont_inherit=True)
    literal = ast.parse(Path(source.__file__).read_bytes())
    result = {}
    for name, filename, owner, first, last in source.ROSTER:
        tree = trees[filename]
        scope = (
            next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == owner)
            if owner
            else tree
        )
        node = next(n for n in scope.body if isinstance(n, ast.FunctionDef) and n.name == name)
        copied_scope = (
            next(
                n
                for n in literal.body
                if isinstance(n, ast.ClassDef) and n.name == "ElectricalKernel"
            )
            if owner
            else literal
        )
        copied = next(
            n for n in copied_scope.body if isinstance(n, ast.FunctionDef) and n.name == name
        )
        if (node.lineno, node.end_lineno) != (first, last) or ast.dump(node) != ast.dump(copied):
            raise ValueError("Original electrical signature/body correspondence changed: " + name)
        code = modules[filename]
        for component in (owner, name) if owner else (name,):
            code = next(v for v in code.co_consts if type(v) is CodeType and v.co_name == component)
        result[name] = (node, code)
    return result


def _stores(definitions):
    return tuple(
        (name, node.lineno, child.attr)
        for name in ("update_V", "get_current")
        for node in ast.walk(definitions[name][0])
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign))
        for target in (node.targets if isinstance(node, ast.Assign) else (node.target,))
        for child in ast.walk(target)
        if isinstance(child, ast.Attribute)
        and isinstance(child.value, ast.Name)
        and child.value.id in ("self", "sim")
        and isinstance(child.ctx, ast.Store)
    )


def source_plan():
    definitions = _definitions()
    reads = {}
    for holder in ("p", "cells", "self", "sim"):
        reads[holder] = sorted(
            {
                n.attr
                for node, _ in definitions.values()
                for n in ast.walk(node)
                if isinstance(n, ast.Attribute)
                and isinstance(n.value, ast.Name)
                and n.value.id == holder
                and isinstance(n.ctx, ast.Load)
            }
        )
    return dict(
        law=LAW_ID,
        source=dict(source.SOURCE_PINS),
        roster=source.ROSTER,
        stores=_stores(definitions),
        reads=reads,
        admitted_parameter_branch=(
            "actual p.is_ecm is True; native polarizability branches retained"
        ),
        native_helpers=("get_current", "HH_Decomp", "gradient", "diff", "divergence"),
        retained_unadmitted_helper="smooth_flux (original non-ECM source branch)",
        external_helpers=(
            "numpy.dot",
            "numpy.asarray",
            "numpy.zeros",
            "scipy.ndimage.gaussian_filter",
        ),
        operator="actual retained cells.lapENVinv; no construction or supplied replacement",
        flux_inverse_read=False,
        flux_defect_repair=False,
        timestep_credit=0,
        parent_source=PARENT_SOURCE_SHA256,
        parent_review=PARENT_REVIEW_SHA256,
        parent_claim=PARENT_CLAIM,
        parent_check=PARENT_CHECK,
        missing_contract=(
            "one-shot actual StorageOwner claim, inherited authority "
            "and original Simulator.update_V dispatch"
        ),
        actual_source_native_operator_reference_or_scientific_release=False,
    )


def _ready():
    if not all(storage.previous._pin(v) for v in (PARENT_SOURCE_SHA256, PARENT_REVIEW_SHA256)):
        raise ElectricalRejected("Reviewed storage handoff remains unavailable", stage="held")
    if PARENT_CLAIM != "_claim_for_electrical" or PARENT_CHECK != "_check_electrical_authority":
        raise ElectricalRejected("Actual storage forwarding interface required", stage="held")
    path = Path(storage.__file__)
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != PARENT_SOURCE_SHA256:
        raise ElectricalRejected("Storage producer changed", stage="producer")
    for name in (PARENT_CLAIM, PARENT_CHECK):
        if type(vars(storage).get(name)) is not FunctionType:
            raise ElectricalRejected("Actual storage hook is absent", stage="held")
    interfaces._source_interface(storage, path.read_bytes(), path, (PARENT_CLAIM, PARENT_CHECK))
    claim, check = getattr(storage, PARENT_CLAIM), getattr(storage, PARENT_CHECK)
    binding = _ParentBinding(storage, claim, check, (_parent_atoms(claim), _parent_atoms(check)))
    storage._ready()
    _check_parent_binding(binding)
    return binding


def _parent_atoms(function):
    keywords = function.__kwdefaults__
    return (
        function,
        function.__code__,
        function.__globals__,
        function.__closure__,
        function.__defaults__,
        keywords,
        *(item for pair in (keywords or {}).items() for item in pair),
    )


def _check_parent_binding(binding):
    if (
        storage is not binding.module
        or getattr(storage, PARENT_CLAIM, None) is not binding.claim
        or getattr(storage, PARENT_CHECK, None) is not binding.check
    ):
        raise ValueError("Authenticated original electrical parent hooks changed")
    for function, expected in zip((binding.claim, binding.check), binding.atoms, strict=True):
        actual = _parent_atoms(function)
        if len(actual) != len(expected) or any(
            a is not b for a, b in zip(actual, expected, strict=True)
        ):
            raise ValueError("Authenticated electrical parent callable/code/defaults changed")


def _call_parent(context, operation, *args, **kwargs):
    binding = context.parent_binding
    _check_parent_binding(binding)
    function = (
        binding.claim if operation == "claim" else binding.check if operation == "check" else None
    )
    if function is None:
        raise ValueError("Unknown electrical parent operation")
    context.last_parent_call = (operation, function, args, kwargs)
    value = function(*args, **kwargs)
    context.last_parent_return = (operation, value)
    _check_parent_binding(binding)
    return value


def request_record(request):
    return dict(law=LAW_ID, parent=request.parent_identity, source=request.source_identity)


def from_storage(owner, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise ElectricalRejected("Explicit electrical law required", stage="law")
    binding = _ready()
    api = binding.module
    with _LOCK:
        if _ACTIVE:
            _reject(_ACTIVE[-1], "Reentrant electrical declaration")
        if type(owner) is not api.StorageOwner or owner in _RETIRED:
            raise ElectricalRejected("Actual unconsumed StorageOwner required", stage="owner")
        parent = api._authority(owner)
        if parent.p.is_ecm is not True:
            raise ElectricalRejected("Only original enabled ECM path is admitted", stage="domain")
        value = Request(owner, parent.trial.identity, _digest(source_plan()), "")
        value = replace(value, identity=_digest(request_record(value)))
        _REQUESTS[value] = (parent, parent.trial, api._snapshot(parent), api._graph(parent))
        return value


def _reject(context, reason):
    context.invalid = True
    if context.entry_error is None:
        context.entry_error = ElectricalRejected(
            reason, stage=context.stage, request=context.request, partial=context
        )
    raise context.entry_error


def _capture(context, origin, error, raw):
    # Retain before any fallible report, including falsey exception objects.
    context.last_capture = (origin, error, raw)
    if context.capture_error is None:
        context.capture_error = error
    try:
        context.capture_errors += (context.last_capture,)
    except BaseException as secondary:
        context.raw_capture_append_error = (secondary, error, raw)


def _guard(context):
    if context.entry_error is not None:
        raise context.entry_error
    if context.capture_error is not None:
        raise ElectricalRejected(
            "Electrical observation failed", stage="capture", partial=context
        ) from context.capture_error
    if (
        context.inherited
        or not context.active
        or context.invalid
        or context.thread != get_ident()
        or not _ACTIVE
        or _ACTIVE[-1] is not context
    ):
        _reject(context, "Exclusive original electrical epoch required")
    if (sys.setprofile, sys.settrace, sys.getprofile, sys.gettrace, sys.call_tracing) != (
        *context.setters,
        *context.getters,
        context.call_tracing,
    ):
        _reject(context, "Electrical observer controls changed")
    if context.observing and (
        context.getters[0]() is not context.observers[0]
        or context.getters[1]() is not context.observers[1]
    ):
        _reject(context, "Both required electrical observers must be active")


def _snapshot(context, *, stable=False):
    return storage._snapshot(context, stable=stable)


def _graph(context):
    return storage._graph(context)


def _epoch(context):
    return (
        _snapshot(context).identity,
        _graph(context),
        tuple(v.identity for v in storage.previous._streams(context.parent)),
    )


def _bootstrap(context):
    function, code, namespace = context.checker
    if (
        context.atoms is not function
        or function.__code__ is not code
        or function.__globals__ is not namespace
    ):
        raise ValueError("Independent electrical metadata checker changed")
    for name, function, expected in context.metadata:
        if globals().get(name) is not function:
            raise ValueError("Electrical metadata helper replaced: " + name)
        actual = _callable_atoms(context, function)
        if len(actual) != len(expected) or any(
            a is not b for a, b in zip(actual, expected, strict=True)
        ):
            raise ValueError("Electrical metadata helper code/default/closure changed: " + name)


def _callable_atoms(context, function):
    result, seen, pending = [], set(), [function]
    while pending:
        value = pending.pop()
        if id(value) in seen:
            continue
        seen.add(id(value))
        if len(seen) > 100:
            raise ValueError("Bounded reached callable delegate graph required")
        result.extend(context.atoms(value))
        if type(value) is FunctionType:
            keywords = value.__kwdefaults__
            result.append(keywords)
            if keywords is not None:
                result.extend(keywords)
                result.extend(keywords.values())
        for name in ("__wrapped__", "_implementation"):
            delegate = getattr(value, name, None)
            result.append(delegate)
            if delegate is not None:
                pending.append(delegate)
    return tuple(result)


def _binding(context):
    _bootstrap(context)
    # Validate current clone resolution as well as acquisition. A factory-return
    # observer must not insert a shadow after the original namespace proof.
    for function in (*context.originals.values(), *context.methods.values()):
        _builtin_bindings(function)
    atoms = [
        context.parent_binding,
        context.storage_parent,
        context.storage_parent.trial,
        context.phase,
        context.p,
        context.cells,
        context.sim,
        context.handler,
        context.cache,
        context.entries,
        _REQUESTS,
        _CONSUMED,
        _RETIRED,
        _ISSUED,
        _FORWARDED,
        _FIRST_STEP_LEASES,
        _SHORT_INIT_LEASES,
        _TERMINAL_INIT_LEASES,
        FIRST_STEP_INTERFACE_SHA256,
        FIRST_STEP_REVIEW_SHA256,
        FIRST_STEP_PARENT_REVIEW_SHA256,
        SHORT_INIT_INTERFACE_SHA256,
        SHORT_INIT_REVIEW_SHA256,
        SHORT_INIT_PARENT_REVIEW_SHA256,
        TERMINAL_INIT_INTERFACE_SHA256,
        TERMINAL_INIT_REVIEW_SHA256,
        TERMINAL_INIT_PARENT_REVIEW_SHA256,
        *storage._observer_bindings(context),
    ]
    for function in (
        context.parent_claim,
        context.parent_check,
        *context.originals.values(),
        *context.methods.values(),
        *context.wrappers.values(),
        *context.external.values(),
        *context.reuse_functions,
        type(context.sim).update_V,
    ):
        atoms.extend(_callable_atoms(context, function))
    for name, namespace, retained in context.namespaces:
        if tuple(namespace) != tuple(k for k, _ in retained):
            raise ValueError("Electrical namespace roster changed: " + name)
        for key, old in retained:
            current = namespace[key]
            if current is not old:
                raise ValueError("Electrical namespace member changed: " + name + "." + key)
            atoms.extend(_callable_atoms(context, current))
    for facade, retained in context.facades:
        if tuple(vars(facade)) != tuple(k for k, _ in retained) or any(
            vars(facade)[k] is not v for k, v in retained
        ):
            raise ValueError("Reached electrical helper namespace changed")
    for namespace, name, original in context.external_members:
        if namespace.get(name) is not original:
            raise ValueError("Original electrical external helper changed: " + name)
        atoms.extend(_callable_atoms(context, original))
    return tuple(atoms)


def _check(context, *, closed=False):
    _bootstrap(context)
    if not closed:
        _guard(context)
    if (
        _REQUESTS.get(context.request) is not context.refs
        or _CONSUMED.get(context.request) is not context
        or _RETIRED.get(context.request.storage_owner) is not context
        or context.storage_parent is not context.refs[0]
        or context.storage_parent.trial is not context.refs[1]
        or _call_parent(context, "check", context) is not context.storage_parent
        or context.phase.p is not context.p
        or context.phase.cells is not context.cells
        or context.phase.sim is not context.sim
        or context.phase.dyna is not context.handler
        or context.phase.cache is not context.cache
        or context.request.identity != _digest(request_record(context.request))
    ):
        raise ValueError("Original storage/electrical ownership changed")
    storage.previous._same_refs(_binding(context), context.bindings)
    if _snapshot(context, stable=True).identity != context.stable.identity:
        raise ValueError("Electrical source changed an unowned state field")
    if tuple(v.identity for v in storage.previous._streams(context.parent)) != context.stream_ids:
        raise ValueError("Electrical update or observer advanced an original RNG")


def _native_defaults(function, node):
    positional = tuple(ast.literal_eval(value) for value in node.args.defaults) or None
    keywords = {
        key.arg: ast.literal_eval(value)
        for key, value in zip(node.args.kwonlyargs, node.args.kw_defaults, strict=True)
        if value is not None
    } or None
    constant = storage.previous.previous._constant
    if constant(function.__defaults__) != constant(positional):
        raise ValueError("Original native positional defaults changed")
    actual = function.__kwdefaults__
    if (actual is None) != (keywords is None) or (
        actual is not None
        and (
            tuple(actual) != tuple(keywords)
            or any(constant(actual[name]) != constant(keywords[name]) for name in keywords)
        )
    ):
        raise ValueError("Original native keyword defaults changed")


def _native_member(function, node, expected):
    original = storage.previous.previous.previous.caches.previous.callbacks.simulator._chain(
        function
    )[-1]
    constant = storage.previous.previous._constant
    if (
        type(original) is not FunctionType
        or original.__code__.co_filename != expected.co_filename
        or constant(original.__code__) != constant(expected)
    ):
        raise ValueError("Actual original electrical executable required")
    _native_defaults(original, node)
    return original


def _builtin_bindings(function):
    namespace = function.__globals__
    provider = namespace.get("__builtins__")
    actual = vars(provider) if type(provider) is ModuleType else provider
    if actual is not function.__builtins__ or actual is not vars(builtins):
        raise ValueError("Clone must use the original canonical cached builtin provider")
    members = [(namespace, "__builtins__", provider)]
    for code in _nested_codes(function.__code__):
        for name in code.co_names:
            if name in vars(builtins):
                value = namespace.get(name, actual[name])
                if value is not vars(builtins)[name]:
                    raise ValueError("Original electrical builtin was shadowed: " + name)
                members.append((namespace if name in namespace else actual, name, value))
    return tuple(members)


def _namespace(context):
    definitions = _definitions()
    factory = context.parent.init_parent.factories["Simulator"]
    root = _native_member(factory.update_V, *definitions["update_V"])
    current = _native_member(root.__globals__["get_current"], *definitions["get_current"])
    toolbox, finite = current.__globals__["stb"], current.__globals__["fd"]
    originals = dict(update_V=root, get_current=current)
    for name in ("HH_Decomp", "smooth_flux"):
        originals[name] = _native_member(vars(toolbox)[name], *definitions[name])
    for name in ("gradient", "diff", "divergence"):
        originals[name] = _native_member(vars(finite)[name], *definitions[name])
    numpy = root.__globals__["np"]
    if numpy is not context.parent.numpy or any(
        fn.__globals__.get("np", numpy) is not numpy for fn in originals.values()
    ):
        raise ValueError("Same actual original NumPy namespace required")
    if originals["HH_Decomp"].__globals__["fd"] is not finite:
        raise ValueError("Actual native finite-difference namespace required")
    context.originals = originals
    context.external = {name: vars(numpy)[name] for name in ("dot", "asarray", "zeros")}
    context.external["gaussian_filter"] = current.__globals__["gaussian_filter"]
    if any(
        context.parent.original_helpers.get(name) is not value
        for name, value in context.external.items()
    ):
        raise ValueError("Electrical delegates must be the actual issued dynamics helpers")
    context.external_members = tuple(
        (vars(numpy), name, context.external[name]) for name in ("dot", "asarray", "zeros")
    )
    members = [(vars(factory), "update_V", factory.update_V)]
    for original in originals.values():
        members.extend(_builtin_bindings(original))
        for name in original.__code__.co_names:
            if name in original.__globals__:
                members.append((original.__globals__, name, original.__globals__[name]))
            elif name in original.__builtins__:
                value = original.__builtins__[name]
                if vars(builtins).get(name) is not value:
                    raise ValueError("Original electrical builtin resolution changed")
                members.append((original.__builtins__, name, value))
    members.extend(
        (vars(toolbox), name, vars(toolbox)[name]) for name in ("HH_Decomp", "smooth_flux")
    )
    members.extend(
        (vars(finite), name, vars(finite)[name]) for name in ("gradient", "diff", "divergence")
    )
    context.external_members += tuple(members)
    context.wrappers = {}
    for name in (*originals, *context.external):
        if name == "update_V":
            continue

        context.wrappers[name] = _operation_wrapper(context, name)
    np_view = SimpleNamespace(**{n: context.wrappers[n] for n in ("dot", "asarray", "zeros")})
    fd_view = SimpleNamespace(
        **{n: context.wrappers[n] for n in ("gradient", "diff", "divergence")}
    )
    stb_view = SimpleNamespace(**{n: context.wrappers[n] for n in ("HH_Decomp", "smooth_flux")})
    namespaces, methods = [], {}
    for name, original in originals.items():
        namespace = dict(original.__globals__)
        namespace.update(
            np=np_view,
            fd=fd_view,
            stb=stb_view,
            get_current=context.wrappers["get_current"],
            HH_Decomp=context.wrappers["HH_Decomp"],
            diff=context.wrappers["diff"],
            gaussian_filter=context.wrappers["gaussian_filter"],
        )
        methods[name] = FunctionType(
            definitions[name][1], namespace, name, original.__defaults__, original.__closure__
        )
        methods[name].__kwdefaults__ = original.__kwdefaults__
        if methods[name].__builtins__ is not original.__builtins__:
            raise ValueError("Electrical clone cached a different builtin provider")
        namespaces.append((name, namespace, tuple(namespace.items())))
    context.methods, context.namespaces = methods, tuple(namespaces)
    context.facades = tuple((f, tuple(vars(f).items())) for f in (np_view, fd_view, stb_view))
    context.expected_body = methods["update_V"].__code__
    # The list comprehension belongs to update_V and has its exact own code.
    context.allowed_codes = frozenset(
        code for fn in methods.values() for code in _nested_codes(fn.__code__)
    )
    context.body_names = {fn.__code__: name for name, fn in methods.items()}
    context.store_instructions = {
        methods[name].__code__: _store_instructions(methods[name].__code__)
        for name in ("update_V", "get_current")
    }


def _store_instructions(code):
    return {
        instruction.offset: (instruction.positions.lineno, instruction.argval)
        for instruction in dis.get_instructions(code)
        if instruction.opname == "STORE_ATTR"
    }


def _operation_wrapper(context, name):
    def wrapper(*args, **kwargs):
        if wrapper is not context.wrappers.get(name):
            _reject(context, "Original retained electrical helper wrapper required")
        return _operation_call(context, name, args, kwargs, sys._getframe(1))

    return wrapper


def _operation_source(context, name, args, kwargs, source_frame, call_frame):
    wrapper = context.wrappers.get(name)
    frame = call_frame.f_back
    if (
        type(source_frame) is not FrameType
        or type(frame) is not FrameType
        or wrapper is None
        or frame.f_code is not wrapper.__code__
        or frame.f_globals is not wrapper.__globals__
        or frame.f_back is not source_frame
        or frame.f_locals.get("context") is not context
        or frame.f_locals.get("name") != name
        or frame.f_locals.get("wrapper") is not wrapper
        or frame.f_locals.get("args") is not args
        or frame.f_locals.get("kwargs") is not kwargs
    ):
        _reject(context, "Actual electrical wrapper and direct source frame required")


def _nested_codes(code):
    yield code
    for child in code.co_consts:
        if type(child) is CodeType:
            yield from _nested_codes(child)


def _operation_call(context, name, args, kwargs, source_frame):
    _check(context)
    row = dict(
        operation=name,
        source_frame=source_frame,
        args=args,
        kwargs=kwargs,
        entered=False,
        returned=False,
        raw=None,
    )
    context.last_helper = row
    try:
        context.helper_calls.append(row)
    except BaseException as error:
        _capture(context, "helper_enter", error, row)
    _guard(context)
    _operation_source(context, name, args, kwargs, source_frame, sys._getframe())
    admitted = context.frames.get(id(source_frame))
    if (
        admitted is None
        or admitted["frame"] is not source_frame
        or admitted["returned"]
        or name == "smooth_flux"
        or len(context.work) + len(context.helper_calls) > MAX_WORK
    ):
        _reject(context, "Electrical helper requires its actual admitted source frame")
    caller = context.body_names.get(source_frame.f_code)
    expected = {
        "get_current": ("update_V",),
        "HH_Decomp": ("get_current",),
        "gradient": ("HH_Decomp", "get_current"),
        "divergence": ("HH_Decomp",),
        "diff": ("divergence",),
        "gaussian_filter": ("get_current",),
    }
    if name in expected and caller not in expected[name]:
        _reject(context, "Electrical helper was reached by the wrong original body")
    parent_operation = context.operation
    if parent_operation is not None and parent_operation["operation"] != caller:
        _reject(context, "Electrical operation ancestry changed")
    if name == "get_current":
        if context.current_attempted:
            _reject(context, "Original update_V reaches get_current once")
        context.current_attempted = True
    delegate = context.methods.get(name, context.external.get(name))
    if delegate is None:
        _reject(context, "Unknown electrical helper")
    row["entered"] = True
    context.operation = row
    try:
        value = delegate(*args, **kwargs)
        context.last_helper_return = (row, value)
        row["raw"], row["returned"] = value, True
    except BaseException as error:
        context.last_helper_error = (row, error)
        if context.primary is None:
            context.primary = error
        raise
    finally:
        context.operation = parent_operation
    _check(context)
    return value


def _wrapper_guard(context, original, frame):
    _check(context)
    context.last_wrapper_attempt = frame
    if (
        original is not context.parent.init_parent
        or type(frame) is not FrameType
        or frame.f_locals.get("method") != "update_V"
        or frame.f_locals.get("name") != "Simulator"
        or frame.f_locals.get("actual") is not context.sim
        or frame.f_locals.get("context") is not original
        or frame.f_back is not context.driver_frame
        or context.wrapper_claim is not None
    ):
        _reject(context, "Actual once-only Simulator.update_V wrapper required")
    function = vars(type(context.sim))["update_V"]
    if frame.f_code is not function.__code__ or frame.f_globals is not function.__globals__:
        _reject(context, "Original electrical runtime wrapper changed")
    for name, cell in zip(function.__code__.co_freevars, function.__closure__ or (), strict=True):
        if frame.f_locals.get(name) is not cell.cell_contents:
            _reject(context, "Original electrical wrapper closure changed")
    context.wrapper_claim = frame


def _dispatch(context, original, label, delegate, actual, args, kwargs, frame):
    _check(context)
    context.last_dispatch = (original, label, delegate, actual, args, kwargs, frame)
    initial = storage.previous.previous.previous
    if (
        original is not context.parent.init_parent
        or label != "Simulator.update_V"
        or actual is not context.sim
        or len(args) != 2
        or kwargs
        or args[0] is not context.cells
        or args[1] is not context.p
        or frame.f_code is not initial._invoke.__code__
        or frame.f_globals is not vars(initial)
        or frame.f_back is not context.wrapper_claim
        or context.dispatched
        or delegate is not original.factories["Simulator"].update_V
    ):
        _reject(context, "Original electrical dispatch/receiver/arguments required")
    context.dispatched = True
    context.body_driver = sys._getframe()
    value = context.methods["update_V"](actual, *args)
    context.last_raw = (context.body_frame, value)
    _check(context)
    if value is not None:
        _reject(context, "Original update_V returns None")
    return value


def _observe(context, frame, event, arg):
    if event == "call":
        row = dict(
            frame=frame,
            code=frame.f_code,
            globals=frame.f_globals,
            returned=False,
            body_started=False,
        )
        context.last_attempt = row
        try:
            context.work.append(row)
        except BaseException as error:
            _capture(context, "source_entry", error, row)
        _check(context)
        if frame.f_code not in context.allowed_codes or len(context.work) > MAX_WORK:
            _reject(context, "Unselected electrical source entry")
        if frame.f_code is context.expected_body:
            if (
                context.body_frame is not None
                or frame.f_back is not context.body_driver
                or frame.f_globals is not context.methods["update_V"].__globals__
                or frame.f_locals.get("self") is not context.sim
                or frame.f_locals.get("cells") is not context.cells
                or frame.f_locals.get("p") is not context.p
            ):
                _reject(context, "Original once-dispatched electrical body required")
            context.body_frame = frame
        elif frame.f_code in context.body_names:
            operation = context.operation
            name = context.body_names[frame.f_code]
            if (
                operation is None
                or operation["operation"] != name
                or not operation["entered"]
                or frame.f_globals is not context.methods[name].__globals__
                or frame.f_back is None
                or frame.f_back.f_code is not _operation_call.__code__
            ):
                _reject(context, "Electrical helper body lacks original operation admission")
        elif frame.f_back is not context.body_frame:
            _reject(context, "Original conductivity comprehension must belong to update_V")
        context.frames[id(frame)] = row
        row["body_started"] = True
        if frame.f_code in context.store_instructions:
            frame.f_trace_opcodes = True
    row = context.frames.get(id(frame))
    if row is None:
        return
    if event == "exception":
        context.last_source_error = (frame, arg[1])
        try:
            context.pending[id(frame)] = arg[1]
        except BaseException as error:
            if context.primary is None:
                context.primary = arg[1]
            _capture(context, "source_exception", error, (frame, arg))
    _observe_stores(context, frame, event)
    if event == "opcode":
        _guard(context)
    if event == "line":
        _check(context)
    if event == "return":
        context.observer_namespace["_witness"](context, frame, arg)
        try:
            context.raw_returns.append(context.last_raw)
            context.locals[id(frame)] = dict(frame.f_locals)
        except BaseException as error:
            _capture(context, "source_return", error, context.last_raw)
        row["returned"] = True
        if frame is context.body_frame:
            context.body_returned = storage.previous.previous.previous._normal_return(frame)


def _observer_recipe(context):
    namespace = dict(
        vars(storage),
        _guard=_guard,
        _check=_check,
        _reject=_reject,
        _observe=_observe,
        _epoch=_epoch,
        _ACTIVE=_ACTIVE,
        StorageRejected=ElectricalRejected,
        MAX_WORK=MAX_WORK,
    )
    FunctionType(storage._observer_recipe.__code__, namespace)(context)


def _finish_store(context, frame, *, normal=True):
    pending = context.pending_stores.pop(id(frame), None)
    if pending is None:
        return
    original, line, name, before, existed, _ = pending
    context.last_store_attempt = pending
    if original is not frame:
        _reject(context, "Pending electrical store frame changed")
    try:
        after = vars(context.sim).get(name)
        context.last_store = (line, name, before, after, existed, normal)
        context.stores.append(context.last_store)
    except BaseException as error:
        _capture(context, "store_return", error, (pending, context.sim))


def _observe_stores(context, frame, event):
    if event == "return":
        _finish_store(
            context, frame, normal=storage.previous.previous.previous._normal_return(frame)
        )
    elif event == "exception":
        _finish_store(context, frame, normal=False)
    elif event == "opcode":
        pending = context.pending_stores.get(id(frame))
        if pending is not None and frame.f_lasti != pending[-1]:
            _finish_store(context, frame)
        instruction = context.store_instructions.get(frame.f_code, {}).get(frame.f_lasti)
        if instruction is not None:
            line, name = instruction
            if name not in context.store_fields:
                _reject(context, "Unowned original electrical attribute store")
            values = vars(context.sim)
            context.pending_stores[id(frame)] = (
                frame,
                line,
                name,
                values.get(name),
                name in values,
                frame.f_lasti,
            )


def _context(request, refs):
    parent = refs[0]
    # Read-only reuse of storage metadata projections; the mutation owner is
    # this new context and its distinct storage epoch, never a fabricated parent.
    context = storage._context(parent.request, parent.refs)
    context.request, context.refs, context.storage_parent = request, refs, parent
    # Observation of original slotted molecular data uses the SAME completed
    # storage participant. Electrical work owns no molecular runtime epoch or
    # mutation permissions; all network state remains in its stable checks.
    context.molecule, context.molecule_claim = parent.molecule, parent.molecule_claim
    context.molecule_record = parent.molecule_record
    context.stage = "electrical_retirement"
    context.store_fields = frozenset(field for _, _, field in _stores(_definitions()))
    context.operation = None
    context.current_attempted = False
    context.pending_stores = {}
    context.methods, context.originals, context.wrappers, context.external = {}, {}, {}, {}
    context.namespaces, context.facades, context.external_members = (), (), ()
    context.reuse_functions = (
        storage._context,
        storage._values,
        storage._snapshot,
        storage._graph,
        storage._observer_recipe,
        storage._observer_bindings,
        storage._finish_pending_store,
    )
    return context


def trial_record(trial):
    return dict(
        request=trial.request_identity,
        parent=trial.parent_identity,
        before=trial.before.identity,
        after=trial.after.identity,
        rng_before=trial.rng_before,
        rng_after=trial.rng_after,
        stores=tuple(
            (line, name, existed, complete) for line, name, _, _, existed, complete in trial.stores
        ),
        work=tuple(
            (
                row["code"].co_filename,
                row["code"].co_firstlineno,
                row["body_started"],
                row["returned"],
            )
            for row in trial.work
        ),
        helpers=tuple((row["operation"], row["entered"], row["returned"]) for row in trial.helpers),
        returns=len(trial.raw_returns),
        completed=trial.completed,
    )


def prepare(request, *, enabled=False):
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise ElectricalRejected("Actual electrical source remains held", stage="release")
    binding = _ready()
    api = binding.module
    with _LOCK:
        if _ACTIVE:
            _reject(_ACTIVE[-1], "Reentrant electrical preparation")
        if type(request) is not Request or request not in _REQUESTS:
            raise ElectricalRejected("Actual issued electrical request required", stage="request")
        if request in _CONSUMED or request.storage_owner in _RETIRED:
            raise ElectricalRejected("Electrical parent already attempted", stage="consumed")
        refs = _REQUESTS[request]
        parent = api._authority(request.storage_owner)
        if (
            parent is not refs[0]
            or parent.trial is not refs[1]
            or api._snapshot(parent).identity != refs[2].identity
        ):
            raise ElectricalRejected("Original storage epoch changed", stage="parent")
        graph = api._graph(parent)
        storage.previous._same_refs(graph[0], refs[3][0])
        if graph[1] != refs[3][1] or request.source_identity != _digest(source_plan()):
            raise ElectricalRejected("Original electrical source/aliases changed", stage="parent")
        context = _context(request, refs)
        context.atoms, context.checker = (
            context.parent.init_parent.atoms,
            context.parent.init_parent.checker,
        )
        context.metadata = tuple(
            (name, fn, _callable_atoms(context, fn))
            for name, fn in globals().items()
            if type(fn) is FunctionType and fn.__globals__ is globals()
        )
        _CONSUMED[request] = _RETIRED[request.storage_owner] = context
        _ACTIVE.append(context)
        primary = None
        try:
            context.parent_binding = binding
            context.parent_claim, context.parent_check = binding.claim, binding.check
            context.entries = MappingProxyType(
                dict(wrapper_guard=_wrapper_guard, dispatch=_dispatch)
            )
            context.stream_ids = tuple(
                v.identity for v in storage.previous._streams(context.parent)
            )
            _call_parent(
                context,
                "claim",
                request.storage_owner,
                expected=refs[1],
                transition=context,
                entries=context.entries,
            )
            _observer_recipe(context)
            _namespace(context)
            context.bindings = _binding(context)
            context.before, context.stable = _snapshot(context), _snapshot(context, stable=True)
            context.stage = "actual_original_update_V"
            with context.account(context):
                _run(context)
            _check(context)
            if (
                not context.body_returned
                or context.primary is not None
                or context.capture_error is not None
            ):
                raise ElectricalRejected(
                    "Electrical source did not complete", stage="sealing", partial=context
                )
            context.after, context.after_graph = _snapshot(context), _graph(context)
            value = Trial(
                request.identity,
                request.parent_identity,
                context.before,
                context.after,
                context.stream_ids,
                tuple(v.identity for v in storage.previous._streams(context.parent)),
                tuple(context.stores),
                tuple(context.work),
                tuple(context.helper_calls),
                tuple(context.raw_returns),
                True,
                "",
            )
            context.trial = replace(value, identity=_digest(trial_record(value)))
        except BaseException as error:
            primary = context.entry_error if context.entry_error is not None else context.primary
            if primary is None:
                primary = error
            context.invalid, context.failure_error = True, primary
            try:
                _FAILED.append(context)
            except BaseException as capture:
                context.retention_error = (capture, primary, context)
        finally:
            context.active = False
            if _ACTIVE and _ACTIVE[-1] is context:
                _ACTIVE.pop()
            else:
                context.invalid = True
            try:
                _restore(context)
            except BaseException as error:
                context.invalid = True
                context.cleanup_entry_error = error
                try:
                    context.cleanup_errors += (("restore_entry_or_return", error, None),)
                except BaseException as capture:
                    context.cleanup_journal_error = (capture, error)
            finally:
                # This already-entered boundary remains able to restore both
                # hooks even if an inherited profiler rejects _restore itself.
                for index in (1, 0):
                    try:
                        context.setters[index](context.required_hooks[index])
                    except BaseException as error:
                        context.invalid = True
                        context.last_cleanup_error = ("boundary_restore", error, index)
                        try:
                            context.cleanup_errors += (context.last_cleanup_error,)
                        except BaseException as capture:
                            context.cleanup_journal_error = (capture, error)
                samples = []
                for order in ((0, 1), (1, 0)):
                    pair = [None, None]
                    for index in order:
                        try:
                            pair[index] = context.getters[index]()
                        except BaseException as error:
                            context.invalid = True
                            context.last_cleanup_error = ("boundary_sample", error, index)
                            try:
                                context.cleanup_errors += (context.last_cleanup_error,)
                            except BaseException as capture:
                                context.cleanup_journal_error = (capture, error)
                    samples.append(tuple(pair))
                context.final_hooks = tuple(samples)
                context.hooks_safe = all(
                    a is context.required_hooks[0] and b is context.required_hooks[1]
                    for a, b in samples
                )
        if primary is not None:
            raise ElectricalRejected(
                "Original electrical update failed",
                stage=context.stage,
                request=request,
                trial=context.trial,
                partial=context,
            ) from primary
        if context.invalid or context.cleanup_errors or not context.hooks_safe:
            raise ElectricalRejected("Electrical closure refused", stage="closure", partial=context)
        owner = object.__new__(ElectricalOwner)
        context.owner = owner
        _ISSUED[owner] = (context, context.trial)
        return owner


def _restore(context):
    for index in (1, 0):
        try:
            context.setters[index](context.required_hooks[index])
        except BaseException as error:
            context.cleanup_errors += (("terminal_restore", error, index),)
    samples = []
    for order in ((0, 1), (1, 0)):
        pair = [None, None]
        for index in order:
            try:
                pair[index] = context.getters[index]()
            except BaseException as error:
                context.cleanup_errors += (("terminal_sample", error, index),)
        samples.append(tuple(pair))
    context.final_hooks = tuple(samples)
    context.hooks_safe = all(
        a is context.required_hooks[0] and b is context.required_hooks[1] for a, b in samples
    )


def _run(context):
    context.driver_frame = sys._getframe()
    return context.sim.update_V(context.cells, context.p)


class ElectricalOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Only successful original electrical execution issues an owner")

    def __reduce_ex__(self, protocol):
        raise TypeError("Electrical state cannot be supplied or hydrated")

    @property
    def phase(self):
        return _authority(self).phase

    @property
    def trial(self):
        return _authority(self).trial


def _authority(owner):
    if type(owner) is not ElectricalOwner or owner not in _ISSUED:
        raise ElectricalRejected("Actual issued ElectricalOwner required", stage="owner")
    context, trial = _ISSUED[owner]
    if owner in _FORWARDED:
        raise ElectricalRejected(
            "Electrical epoch consumed by its selected source continuation",
            stage="forwarded",
            trial=trial,
            partial=context,
        )
    if context.active or context.invalid or context.validating:
        context.invalid = True
        raise ElectricalRejected(
            "Invalid/reentrant electrical owner", stage="owner", partial=context
        )
    context.validating = True
    try:
        _ready()
        _check(context, closed=True)
        graph = _graph(context)
        storage.previous._same_refs(graph[0], context.after_graph[0])
        if (
            graph[1] != context.after_graph[1]
            or _snapshot(context).identity != context.after.identity
            or context.trial is not trial
            or trial.identity != _digest(trial_record(trial))
        ):
            raise ElectricalRejected("Completed electrical state or aliases changed", stage="owner")
        return context
    except BaseException:
        context.invalid = True
        raise
    finally:
        context.validating = False


def _first_step_api():
    """Exact source-gated leaf; legacy electrical preparation is unchanged."""
    if not all(
        storage.previous._pin(value)
        for value in (
            FIRST_STEP_INTERFACE_SHA256,
            FIRST_STEP_REVIEW_SHA256,
            FIRST_STEP_PARENT_REVIEW_SHA256,
        )
    ):
        raise ElectricalRejected(
            "Reviewed first-step continuation remains held", stage="first_step_held"
        )
    path = Path(__file__).parents[3] / ("src/" + FIRST_STEP_MODULE.replace(".", "/") + ".py")
    if path.is_symlink() or not path.is_file():
        raise ValueError("Actual original first-step producer required")
    payload = path.read_bytes()
    identity, backrefs = FunctionType(
        storage.previous._storage_binding.__code__,
        dict(
            vars(storage.previous),
            STORAGE_BACK_REFERENCE_SLOTS=("PARENT_SOURCE_SHA256", "PARENT_REVIEW_SHA256"),
            STORAGE_BINDING_KIND=FIRST_STEP_BINDING_KIND,
        ),
    )(payload)
    if identity != FIRST_STEP_INTERFACE_SHA256 or backrefs != (
        ("PARENT_SOURCE_SHA256", hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
        ("PARENT_REVIEW_SHA256", FIRST_STEP_PARENT_REVIEW_SHA256),
    ):
        raise ValueError("Actual first-step source/electrical back-reference changed")
    module = sys.modules.get(FIRST_STEP_MODULE)
    if (
        type(module) is not ModuleType
        or vars(module).get("previous") is not sys.modules[__name__]
        or Path(module.__file__).resolve() != path
    ):
        raise ValueError("Actual issued first-step namespace required")
    names = (
        "prepare",
        "_ready",
        "_claim_wrapper",
        "_dispatch",
        "_check_ancestor_metadata",
        "_mutation_contract",
    )
    functions = []
    for name in names:
        function = vars(module).get(name)
        if type(function) is not FunctionType:
            raise ValueError("Actual typed first-step source function required")
        functions.append((name, function, storage._electrical_atoms(function)))
    interfaces._source_interface(module, payload, path, names)
    binding = _StepBinding(module, tuple(functions))
    _check_step_binding(binding)
    next(function for name, function, _ in binding.functions if name == "_ready")()
    _check_step_binding(binding)
    return binding


def _check_step_binding(binding):
    if type(binding) is not _StepBinding or type(binding.module) is not ModuleType:
        raise ValueError("Original first-step callback proof required")
    for name, function, retained in binding.functions:
        if vars(binding.module).get(name) is not function:
            raise ValueError("Proved first-step callback slot changed")
        storage.previous._same_refs(storage._electrical_atoms(function), retained)


def _first_step_route(context):
    binding = _first_step_api()
    module = binding.module
    owner, child = (
        getattr(context, "owner", None),
        getattr(context, "first_step_transition", None),
    )
    lease = _FIRST_STEP_LEASES.get(owner)
    issued = _ISSUED.get(owner)
    if (
        type(owner) is not ElectricalOwner
        or issued is None
        or issued[0] is not context
        or (issued[1] is not context.trial)
        or (child is None)
        or (lease is None)
        or (lease.parent is not context)
        or (lease.child is not child)
        or (_FORWARDED.get(owner) is not child)
        or context.active
        or context.invalid
        or child.invalid
        or (child.thread != get_ident())
        or (child.electrical_parent is not context)
        or (type(child.request) is not module.Request)
        or (child.request.electrical_owner is not owner)
        or (module._REQUESTS.get(child.request) is not child.refs)
        or (module._CONSUMED.get(child.request) is not child)
        or (module._RETIRED.get(owner) is not child)
        or (child.refs[0] is not context)
        or (child.refs[1] is not context.trial)
        or (child.entries is not lease.entries)
        or (child.phase is not context.phase)
        or (child.sim is not context.sim)
        or (child.p is not context.p)
        or (child.cells is not context.cells)
    ) or (
        owner in _TERMINAL_INIT_LEASES
        or getattr(context, "terminal_init_transition", None) is not None
    ):
        if type(child) is SimpleNamespace and lease is not None and (lease.child is child):
            _first_step_reject(
                child, "Original electrical/first-step issuance and retirement links changed"
            )
        raise ValueError("Original electrical/first-step issuance and retirement links changed")
    for name, function, retained in lease.functions:
        if vars(module).get(name) is not function:
            raise ValueError("Authenticated first-step runtime helper replaced")
        storage.previous._same_refs(storage._electrical_atoms(function), retained)
    if child.active:
        if not module._ACTIVE or module._ACTIVE[-1] is not child:
            raise ValueError("Exclusive first-step transition required")
    else:
        issued = module._ISSUED.get(getattr(child, "owner", None))
        if (
            issued is None
            or issued[0] is not child
            or issued[1] is not child.trial
            or (not child.trial.iteration_complete)
        ):
            _first_step_reject(child, "Actually sealed selected first-step record required")
    return (child, module)


def _first_step_reject(child, reason):
    child.invalid = True
    if child.entry_error is None:
        child.entry_error = ElectricalRejected(reason, stage="first_step_entry", partial=child)
    first = getattr(child, "first_failure", None)
    if first is not None and first[0] == "source":
        raise first[1]
    raise child.entry_error


def _claim_for_first_step(owner, *, expected, transition, entries):
    binding = _first_step_api()
    module = binding.module
    frame = sys._getframe(1)
    with _LOCK:
        if (
            type(owner) is not ElectricalOwner
            or owner not in _ISSUED
            or frame.f_code is not module.prepare.__code__
            or (frame.f_globals is not vars(module))
            or (frame.f_locals.get("context") is not transition)
            or (frame.f_locals.get("request") is not transition.request)
            or (module._CONSUMED.get(transition.request) is not transition)
            or (module._RETIRED.get(owner) is not transition)
            or (not transition.active)
            or (transition.thread != get_ident())
            or (transition.entries is not entries)
        ):
            raise ElectricalRejected(
                "Actual once-only first-step issuer frame required", stage="first_step_entry"
            )
        context, trial = _ISSUED[owner]
        if (owner in _FORWARDED or owner in _FIRST_STEP_LEASES) or owner in _TERMINAL_INIT_LEASES:
            _first_step_reject(transition, "Electrical first-step epoch already attempted")
        _check_step_binding(binding)
        functions = binding.functions
        if tuple(entries) != ("wrapper_guard", "dispatch") or any(
            (
                entries[key] is not next((fn for name, fn, _ in functions if name == expected_name))
                for key, expected_name in (
                    ("wrapper_guard", "_claim_wrapper"),
                    ("dispatch", "_dispatch"),
                )
            )
        ):
            raise ValueError("Original immutable first-step entry callbacks required")
        lease = SimpleNamespace(
            parent=context,
            child=transition,
            entries=entries,
            trial=trial,
            functions=functions,
            status="claiming",
            primary=None,
        )
        _FORWARDED[owner] = context.first_step_transition = transition
        _FIRST_STEP_LEASES[owner] = lease
        try:
            if (
                expected is not trial
                or transition.refs[0] is not context
                or transition.refs[1] is not trial
                or context.active
                or context.invalid
                or context.validating
            ):
                raise ValueError(
                    "Actual closed electrical epoch required before first-step retirement"
                )
            _ready()
            _check(context, closed=True)
            graph = _graph(context)
            storage.previous._same_refs(graph[0], context.after_graph[0])
            if (
                graph[1] != context.after_graph[1]
                or _snapshot(context).identity != context.after.identity
                or (not trial.completed)
            ):
                raise ValueError("Original full electrical state changed before first-step proof")
            storage._claim_first_step_ancestor(context, transition)
            lease.status = "ready"
            return context
        except BaseException as error:
            primary = transition.entry_error if transition.entry_error is not None else error
            lease.status, lease.primary = ("failed", primary)
            if error is not primary:
                lease.secondary = (error, primary)
            context.invalid = transition.invalid = True
            raise primary from primary.__cause__


def _check_first_step_authority(transition):
    context = transition.electrical_parent
    child, module = _first_step_route(context)
    if child is not transition or _FIRST_STEP_LEASES[context.owner].status != "ready":
        raise ValueError("Original completed first-step retirement required")
    storage._check_first_step_ancestor(context, transition)
    function = next(
        fn
        for name, fn, _ in _FIRST_STEP_LEASES[context.owner].functions
        if name == "_check_ancestor_metadata"
    )
    if function(transition) is not context:
        raise ValueError("Different original electrical/first-step metadata ancestry")
    return context


def _short_init_api():
    """Distinct source-gated N-history consumer; no FirstStepOwner conversion."""
    if not all(
        storage.previous._pin(value)
        for value in (
            SHORT_INIT_INTERFACE_SHA256,
            SHORT_INIT_REVIEW_SHA256,
            SHORT_INIT_PARENT_REVIEW_SHA256,
        )
    ):
        raise ElectricalRejected(
            "Reviewed short-history continuation remains held", stage="short_init_held"
        )
    path = Path(__file__).parents[3] / ("src/" + SHORT_INIT_MODULE.replace(".", "/") + ".py")
    if path.is_symlink() or not path.is_file():
        raise ValueError("Actual original short-history producer required")
    payload = path.read_bytes()
    identity, backrefs = FunctionType(
        storage.previous._storage_binding.__code__,
        dict(
            vars(storage.previous),
            STORAGE_BACK_REFERENCE_SLOTS=("PARENT_SOURCE_SHA256", "PARENT_REVIEW_SHA256"),
            STORAGE_BINDING_KIND=SHORT_INIT_BINDING_KIND,
        ),
    )(payload)
    if identity != SHORT_INIT_INTERFACE_SHA256 or backrefs != (
        ("PARENT_SOURCE_SHA256", hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
        ("PARENT_REVIEW_SHA256", SHORT_INIT_PARENT_REVIEW_SHA256),
    ):
        raise ValueError("Actual short-history source/electrical back-reference changed")
    module = sys.modules.get(SHORT_INIT_MODULE)
    if (
        type(module) is not ModuleType
        or vars(module).get("base") is not sys.modules.get(FIRST_STEP_MODULE)
        or module.base.previous is not sys.modules[__name__]
        or Path(module.__file__).resolve() != path
    ):
        raise ValueError("Actual original short-history namespace required")
    names = (
        "prepare",
        "_ready",
        "_claim_wrapper",
        "_dispatch",
        "_check_ancestor_metadata",
        "_mutation_contract",
    )
    functions = tuple(
        (name, vars(module).get(name), storage._electrical_atoms(vars(module).get(name)))
        for name in names
    )
    if any(type(function) is not FunctionType for _, function, _ in functions):
        raise ValueError("Actual typed short-history source functions required")
    interfaces._source_interface(module, payload, path, names)
    binding = _StepBinding(module, functions)
    _check_step_binding(binding)
    next(fn for name, fn, _ in functions if name == "_ready")()
    _check_step_binding(binding)
    return binding


def _short_init_reject(child, reason):
    child.invalid = True
    if child.entry_error is None:
        child.entry_error = ElectricalRejected(reason, stage="short_init_entry", partial=child)
    first = getattr(child, "first_failure", None)
    if first is None:
        child.first_failure = ("admission", child.entry_error)
    if first is not None and first[0] == "source":
        raise first[1]
    raise child.entry_error


def _short_init_route(context):
    """Actual same-owner live route; never validate a retired numeric cache."""
    binding = _short_init_api()
    module = binding.module
    owner, child = (
        getattr(context, "owner", None),
        getattr(context, "short_init_transition", None),
    )
    lease, issued = (_SHORT_INIT_LEASES.get(owner), _ISSUED.get(owner))
    if (
        type(owner) is not ElectricalOwner
        or issued is None
        or issued[0] is not context
        or (issued[1] is not context.trial)
        or (lease is None)
        or (lease.parent is not context)
        or (lease.child is not child)
        or (lease.trial is not context.trial)
        or (getattr(context, "short_init_lease", None) is not lease)
        or (_FORWARDED.get(owner) is not child)
        or (owner in _FIRST_STEP_LEASES)
        or (getattr(context, "first_step_transition", None) is not None)
        or context.active
        or context.invalid
        or (child is None)
        or child.invalid
        or (child.thread != get_ident())
        or (child.electrical_parent is not context)
        or (type(child.request) is not module.Request)
        or (child.request.electrical_owner is not owner)
        or (type(child.request.iterations) is not int)
        or (child.request.iterations != lease.iterations)
        or (module._REQUESTS.get(child.request) is not child.refs)
        or (module._CONSUMED.get(child.request) is not child)
        or (module._RETIRED.get(owner) is not child)
        or (child.refs[0] is not context)
        or (child.refs[1] is not context.trial)
        or (child.entries is not lease.entries)
        or (child.phase is not context.phase)
        or (child.sim is not context.sim)
        or (child.p is not context.p)
        or (child.cells is not context.cells)
        or (child.handler is not context.handler)
        or (child.cache is not context.cache)
    ) or (
        owner in _TERMINAL_INIT_LEASES
        or getattr(context, "terminal_init_transition", None) is not None
    ):
        if type(child) is SimpleNamespace and lease is not None and (lease.child is child):
            _short_init_reject(child, "Original electrical/short-history ancestry changed")
        raise ValueError("Original electrical/short-history ancestry changed")
    _check_step_binding(_StepBinding(module, lease.functions))
    if child.active:
        if not module._ACTIVE or module._ACTIVE[-1] is not child:
            _short_init_reject(child, "Exclusive short-history transition required")
    else:
        published = module._ISSUED.get(getattr(child, "owner", None))
        if (
            type(getattr(child, "owner", None)) is not module.ShortHistoryOwner
            or published is None
            or published[0] is not child
            or (published[1] is not child.trial)
            or (not child.trial.source_completed)
            or (not child.trial.selected_stop)
            or child.trial.loop_returned
            or child.timeline.invalid
            or (child.timeline.current is not None)
            or (child.timeline.completed != lease.iterations)
        ):
            _short_init_reject(child, "Actually sealed short-history record required")
    return (child, module)


def _claim_for_short_init(owner, *, expected, transition, entries):
    binding = _short_init_api()
    module = binding.module
    frame = sys._getframe(1)
    with _LOCK:
        if (
            type(owner) is not ElectricalOwner
            or owner not in _ISSUED
            or frame.f_code is not module.prepare.__code__
            or (frame.f_globals is not vars(module))
            or (frame.f_locals.get("context") is not transition)
            or (frame.f_locals.get("request") is not transition.request)
            or (module._CONSUMED.get(transition.request) is not transition)
            or (module._RETIRED.get(owner) is not transition)
            or (not transition.active)
            or (transition.thread != get_ident())
            or (transition.entries is not entries)
        ):
            raise ElectricalRejected(
                "Actual once-only short-history issuer frame required", stage="short_init_entry"
            )
        context, trial = _ISSUED[owner]
        if (
            owner in _FORWARDED or owner in _SHORT_INIT_LEASES or owner in _FIRST_STEP_LEASES
        ) or owner in _TERMINAL_INIT_LEASES:
            _short_init_reject(transition, "Electrical source epoch already attempted")
        _check_step_binding(binding)
        functions = binding.functions
        if tuple(entries) != ("wrapper_guard", "dispatch") or any(
            (
                entries[key] is not next((fn for name, fn, _ in functions if name == expected_name))
                for key, expected_name in (
                    ("wrapper_guard", "_claim_wrapper"),
                    ("dispatch", "_dispatch"),
                )
            )
        ):
            raise ValueError("Original immutable short-history entry callbacks required")
        lease = SimpleNamespace(
            parent=context,
            child=transition,
            entries=entries,
            trial=trial,
            functions=functions,
            iterations=transition.request.iterations,
            status="claiming",
            primary=None,
        )
        _FORWARDED[owner] = context.short_init_transition = transition
        _SHORT_INIT_LEASES[owner] = context.short_init_lease = lease
        try:
            if (
                expected is not trial
                or transition.refs[0] is not context
                or transition.refs[1] is not trial
                or context.active
                or context.invalid
                or context.validating
                or (type(lease.iterations) is not int)
                or (not 1 <= lease.iterations <= 64)
            ):
                raise ValueError("Actual closed electrical epoch required before retirement")
            _ready()
            _check(context, closed=True)
            graph = _graph(context)
            storage.previous._same_refs(graph[0], context.after_graph[0])
            if (
                graph[1] != context.after_graph[1]
                or _snapshot(context).identity != context.after.identity
                or (not trial.completed)
            ):
                raise ValueError("Original full electrical state changed before history proof")
            storage._claim_short_init_ancestor(context, transition)
            lease.status = "ready"
            return context
        except BaseException as error:
            first = getattr(transition, "first_failure", None)
            primary = first[1] if first is not None else transition.entry_error
            if primary is None:
                primary = error
            lease.status, lease.primary = ("failed", primary)
            if error is not primary:
                lease.secondary = (error, primary)
            context.invalid = transition.invalid = True
            raise primary from primary.__cause__


def _check_short_init_authority(transition):
    context = transition.electrical_parent
    child, module = _short_init_route(context)
    lease = _SHORT_INIT_LEASES.get(context.owner)
    if child is not transition or lease.status != "ready":
        raise ValueError("Original completed short-history retirement required")
    storage._check_short_init_ancestor(context, transition)
    function = next(fn for name, fn, _ in lease.functions if name == "_check_ancestor_metadata")
    if function(transition) is not context:
        raise ValueError("Different original electrical/short-history metadata ancestry")
    return context


# Separate held natural-terminal ancestry; no selected-history reuse.


def _terminal_init_api():
    """Distinct source-gated N-history consumer; no FirstStepOwner conversion."""
    if not all(
        (
            storage.previous._pin(value)
            for value in (
                TERMINAL_INIT_INTERFACE_SHA256,
                TERMINAL_INIT_REVIEW_SHA256,
                TERMINAL_INIT_PARENT_REVIEW_SHA256,
            )
        )
    ):
        raise ElectricalRejected(
            "Reviewed natural-terminal continuation remains held", stage="terminal_init_held"
        )
    path = Path(__file__).parents[3] / ("src/" + TERMINAL_INIT_MODULE.replace(".", "/") + ".py")
    if path.is_symlink() or not path.is_file():
        raise ValueError("Actual original natural-terminal producer required")
    payload = path.read_bytes()
    identity, backrefs = FunctionType(
        storage.previous._storage_binding.__code__,
        dict(
            vars(storage.previous),
            STORAGE_BACK_REFERENCE_SLOTS=("PARENT_SOURCE_SHA256", "PARENT_REVIEW_SHA256"),
            STORAGE_BINDING_KIND=TERMINAL_INIT_BINDING_KIND,
        ),
    )(payload)
    if identity != TERMINAL_INIT_INTERFACE_SHA256 or backrefs != (
        ("PARENT_SOURCE_SHA256", hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
        ("PARENT_REVIEW_SHA256", TERMINAL_INIT_PARENT_REVIEW_SHA256),
    ):
        raise ValueError("Actual natural-terminal source/electrical back-reference changed")
    module = sys.modules.get(TERMINAL_INIT_MODULE)
    if (
        type(module) is not ModuleType
        or vars(module).get("base") is not sys.modules.get(FIRST_STEP_MODULE)
        or module.base.previous is not sys.modules[__name__]
        or (Path(module.__file__).resolve() != path)
    ):
        raise ValueError("Actual original natural-terminal namespace required")
    names = (
        "prepare",
        "_ready",
        "_claim_wrapper",
        "_dispatch",
        "_check_ancestor_metadata",
        "_mutation_contract",
        "_configured_count",
        "_terminal_runtime_status",
    )
    functions = tuple(
        (
            (name, vars(module).get(name), storage._electrical_atoms(vars(module).get(name)))
            for name in names
        )
    )
    if any((type(function) is not FunctionType for _, function, _ in functions)):
        raise ValueError("Actual typed natural-terminal source functions required")
    interfaces._source_interface(module, payload, path, names)
    binding = _StepBinding(module, functions)
    _check_step_binding(binding)
    next((fn for name, fn, _ in functions if name == "_ready"))()
    _check_step_binding(binding)
    return binding


def _terminal_init_reject(child, reason):
    child.invalid = True
    if child.entry_error is None:
        child.entry_error = ElectricalRejected(reason, stage="terminal_init_entry", partial=child)
    first = getattr(child, "first_failure", None)
    if first is None:
        child.first_failure = ("admission", child.entry_error)
    if first is not None and first[0] == "source":
        raise first[1]
    raise child.entry_error


def _terminal_init_route(context):
    """Actual same-owner live route; never validate a retired numeric cache."""
    binding = _terminal_init_api()
    module = binding.module
    owner, child = (
        getattr(context, "owner", None),
        getattr(context, "terminal_init_transition", None),
    )
    lease, issued = (_TERMINAL_INIT_LEASES.get(owner), _ISSUED.get(owner))
    if (
        type(owner) is not ElectricalOwner
        or issued is None
        or issued[0] is not context
        or (issued[1] is not context.trial)
        or (lease is None)
        or (lease.parent is not context)
        or (lease.child is not child)
        or (lease.trial is not context.trial)
        or (getattr(context, "terminal_init_lease", None) is not lease)
        or (_FORWARDED.get(owner) is not child)
        or (owner in _FIRST_STEP_LEASES)
        or (getattr(context, "first_step_transition", None) is not None)
        or context.active
        or context.invalid
        or (child is None)
        or child.invalid
        or (child.thread != get_ident())
        or (child.electrical_parent is not context)
        or (type(child.request) is not module.Request)
        or (child.request.electrical_owner is not owner)
        or (type(child.request.iterations) is not int)
        or (child.request.iterations != lease.iterations)
        or (module._REQUESTS.get(child.request) is not child.refs)
        or (module._CONSUMED.get(child.request) is not child)
        or (module._RETIRED.get(owner) is not child)
        or (child.refs[0] is not context)
        or (child.refs[1] is not context.trial)
        or (child.entries is not lease.entries)
        or (child.phase is not context.phase)
        or (child.sim is not context.sim)
        or (child.p is not context.p)
        or (child.cells is not context.cells)
        or (child.handler is not context.handler)
        or (child.cache is not context.cache)
    ) or (
        owner in _SHORT_INIT_LEASES
        or getattr(context, "short_init_transition", None) is not None
        or type(child.request.maximum) is not int
        or (child.request.maximum != lease.maximum)
        or (
            child.request.iterations
            != module._configured_count(context.p.init_tsteps, lease.maximum)
        )
    ):
        if type(child) is SimpleNamespace and lease is not None and (lease.child is child):
            _terminal_init_reject(child, "Original electrical/natural-terminal ancestry changed")
        raise ValueError("Original electrical/natural-terminal ancestry changed")
    _check_step_binding(_StepBinding(module, lease.functions))
    if child.active:
        if not module._ACTIVE or module._ACTIVE[-1] is not child:
            _terminal_init_reject(child, "Exclusive natural-terminal transition required")
    else:
        published = module._ISSUED.get(getattr(child, "owner", None))
        if (
            type(getattr(child, "owner", None)) is not module.InitTerminalOwner
            or published is None
            or published[0] is not child
            or (published[1] is not child.trial)
            or (child.trial.source_completed is not True)
            or (child.trial.selected_stop is not False)
            or (child.trial.loop_returned is not True)
            or (child.trial.context_returned is not True)
            or (child.trial.identity != module._digest(module.trial_record(child.trial)))
            or child.timeline.invalid
            or (child.timeline.current is not None)
            or (child.timeline.completed != lease.iterations)
            or (len(child.timeline.records) != lease.iterations)
        ):
            _terminal_init_reject(child, "Actually sealed natural-terminal record required")
    return (child, module)


def _claim_for_terminal_init(owner, *, expected, transition, entries):
    binding = _terminal_init_api()
    module = binding.module
    frame = sys._getframe(1)
    with _LOCK:
        if (
            type(owner) is not ElectricalOwner
            or owner not in _ISSUED
            or frame.f_code is not module.prepare.__code__
            or (frame.f_globals is not vars(module))
            or (frame.f_locals.get("context") is not transition)
            or (frame.f_locals.get("request") is not transition.request)
            or (module._CONSUMED.get(transition.request) is not transition)
            or (module._RETIRED.get(owner) is not transition)
            or (not transition.active)
            or (transition.thread != get_ident())
            or (transition.entries is not entries)
        ):
            raise ElectricalRejected(
                "Actual once-only natural-terminal issuer frame required",
                stage="terminal_init_entry",
            )
        context, trial = _ISSUED[owner]
        if (
            owner in _FORWARDED or owner in _TERMINAL_INIT_LEASES or owner in _FIRST_STEP_LEASES
        ) or owner in _SHORT_INIT_LEASES:
            _terminal_init_reject(transition, "Electrical source epoch already attempted")
        _check_step_binding(binding)
        functions = binding.functions
        if tuple(entries) != ("wrapper_guard", "dispatch") or any(
            (
                entries[key] is not next((fn for name, fn, _ in functions if name == expected_name))
                for key, expected_name in (
                    ("wrapper_guard", "_claim_wrapper"),
                    ("dispatch", "_dispatch"),
                )
            )
        ):
            raise ValueError("Original immutable natural-terminal entry callbacks required")
        lease = SimpleNamespace(
            parent=context,
            child=transition,
            entries=entries,
            trial=trial,
            functions=functions,
            iterations=transition.request.iterations,
            status="claiming",
            primary=None,
            maximum=transition.request.maximum,
        )
        _FORWARDED[owner] = context.terminal_init_transition = transition
        _TERMINAL_INIT_LEASES[owner] = context.terminal_init_lease = lease
        try:
            if (
                expected is not trial
                or transition.refs[0] is not context
                or transition.refs[1] is not trial
                or context.active
                or context.invalid
                or context.validating
                or (type(lease.iterations) is not int)
                or (not 1 <= lease.iterations <= module.MAX_ITERATIONS)
            ) or lease.iterations != module._configured_count(context.p.init_tsteps, lease.maximum):
                raise ValueError("Actual closed electrical epoch required before retirement")
            _ready()
            _check(context, closed=True)
            graph = _graph(context)
            storage.previous._same_refs(graph[0], context.after_graph[0])
            if (
                graph[1] != context.after_graph[1]
                or _snapshot(context).identity != context.after.identity
                or (not trial.completed)
            ):
                raise ValueError("Original full electrical state changed before history proof")
            storage._claim_terminal_init_ancestor(context, transition)
            lease.status = "ready"
            return context
        except BaseException as error:
            first = getattr(transition, "first_failure", None)
            primary = first[1] if first is not None else transition.entry_error
            if primary is None:
                primary = error
            lease.status, lease.primary = ("failed", primary)
            if error is not primary:
                lease.secondary = (error, primary)
            context.invalid = transition.invalid = True
            raise primary from primary.__cause__


def _check_terminal_init_authority(transition):
    context = transition.electrical_parent
    child, module = _terminal_init_route(context)
    lease = _TERMINAL_INIT_LEASES.get(context.owner)
    if child is not transition or lease.status != "ready":
        raise ValueError("Original completed natural-terminal retirement required")
    storage._check_terminal_init_ancestor(context, transition)
    function = next((fn for name, fn, _ in lease.functions if name == "_check_ancestor_metadata"))
    if function(transition) is not context:
        raise ValueError("Different original electrical/natural-terminal metadata ancestry")
    return context
