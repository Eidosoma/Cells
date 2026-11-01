"""Fresh original Parameters construction, explicitly unloaded and phase-held.

This separate birth neither upgrades an existing selected parameter object nor
loads YAML/paths/ions. Its live native object is not a phase or INIT authority.
"""

import ast
import hashlib
import importlib
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import CodeType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_simulator_construction as inherited

LAW_ID = "betse_native_fresh_unloaded_parameters_constructor@1"
SIMULATOR_SHA256 = "8f68eaa22a6225b044e0dbd87475ace0439443aa490369fb42612b54f3ae12ce"
PARAMETERS = "betse/science/parameters.py"
YAML_FILE = "betse/lib/yaml/abc/yamlfileabc.py"
YAML_BASE = "betse/lib/yaml/abc/yamlabc.py"
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


def _method_code(cls_node, name, filename):
    code = compile(
        ast.Module(body=[cls_node], type_ignores=[]), filename, "exec", dont_inherit=True
    )
    class_code = next(
        c for c in code.co_consts if type(c) is CodeType and c.co_name == cls_node.name
    )
    return next(c for c in class_code.co_consts if type(c) is CodeType and c.co_name == name)


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
        function = inherited._chain(getattr(cls, name))[-1]
        if function.__globals__ is not vars(module) or inherited._code(
            function.__code__
        ) != inherited._code(
            _method_code(node, name, str(inherited.tissue.aliases.NATIVE / PARAMETERS))
        ):
            raise ValueError("Native Parameters constructor executable changed")
        for key, cell in zip(
            function.__code__.co_freevars, function.__closure__ or (), strict=True
        ):
            if key == "__class__" and cell.cell_contents is not cls:
                raise ValueError("Original super/class closure association changed")
    return cls


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
    return SimpleNamespace(
        modules=modules, cls=cls, yaml=modules["betse.lib.yaml.abc.yamlabc"].YamlABC
    )


def _runtime(source):
    module = source.modules["betse.science.parameters"]
    yaml = source.modules["betse.lib.yaml.abc.yamlfileabc"]
    if _canonical(module, yaml) is not source.cls:
        raise ValueError("Original native Parameters class identity changed")
    objects = [source.cls, source.yaml]
    labels = []
    for name, module in source.modules.items():
        labels.append(name)
        objects.extend((module, vars(module)))
    objects.extend(inherited.tissue._surface(source.cls))
    objects.extend(inherited.tissue._surface(type(source.cls)))
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
