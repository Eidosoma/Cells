"""Literal original Parameters.load YAML-read prefix, never a full load.

Read real declared file bytes through the original safe round-trip reader on
one consumed native Parameters object. Compatibility/paths/ions stay closed.
"""

import ast
import copy
import dis
import hashlib
import os
import stat
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import FunctionType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_bytecode_bindings as bytecode_bindings
from cells.processes import betse_native_parameter_record_digest as record_digest
from cells.processes import betse_native_parameter_yaml_graph as graphs
from cells.processes import betse_native_phase_parameters as parameters

LAW_ID = parameters.YAML_PREFIX_LAW
PATHS_LAW = "betse_native_parameter_compatibility_paths@1"
PARAMETERS_SHA256 = '276c6fa0d841dd46438090f1d3ebfb429aba6c2ec98e1c7fc17fae5ebc6fcaeb'
MAX_FILE_BYTES = 8 * 2**20
BASE = Path("/mnt/workspaces/Cells")
_FILES, _REQUESTS, _CONSUMED, _CLAIMED, _ISSUED = (WeakKeyDictionary() for _ in range(5))
_LOCK, _ACTIVE = RLock(), []


class YamlPrefixRejected(ValueError):
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
class FileInput:
    filename: str
    sha256: str
    origin: str
    stat: tuple
    identity: str


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    parent: parameters.ParameterOwner
    file: FileInput
    parent_trial_identity: str
    source_identity: str
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("Live YAML requests cannot be serialized")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    before_cache_identity: str
    graph: object
    work: tuple
    prefix_completed: bool
    identity: str


def _digest(value):
    return record_digest.digest(value, selected=parameters.inherited.tissue.core.records)


def _file(path):
    path = Path(path)
    if not path.is_absolute() or not path.is_relative_to(BASE):
        raise ValueError("Explicit immutable input below /mnt/workspaces/Cells required")
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Linked YAML input refused")
    if path.resolve() != path or not path.resolve().is_relative_to(BASE):
        raise ValueError("Canonical contained YAML input required")
    info = path.stat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or info.st_size > MAX_FILE_BYTES
        or info.st_mode & 0o222
    ):
        raise ValueError("Bounded read-only regular YAML input required")
    data = path.read_bytes()
    after = path.stat()

    def signature(s):
        return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_mode

    if signature(info) != signature(after) or len(data) != info.st_size:
        raise ValueError("YAML input changed during read")
    return path.resolve(), signature(info), hashlib.sha256(data).hexdigest()


def file_record(value):
    return dict(
        filename=value.filename,
        sha256=value.sha256,
        origin=value.origin,
        stat=value.stat,
        authority="declared immutable file bytes; not parsed configuration or native derivation",
    )


def input_file(filename, *, sha256, origin):
    if (
        type(sha256) is not str
        or len(sha256) != 64
        or type(origin) is not str
        or not origin
        or len(origin) > 2048
    ):
        raise YamlPrefixRejected(
            "Explicit source file hash/origin required", stage="file_declaration"
        )
    path, info, digest = _file(filename)
    if digest != sha256:
        raise YamlPrefixRejected("Declared YAML bytes differ", stage="file_hash")
    value = FileInput(str(path), digest, origin, info, "")
    value = replace(value, identity=_digest(file_record(value)))
    _FILES[value] = value.identity
    return value


def _verify_file(value):
    if (
        type(value) is not FileInput
        or _FILES.get(value) != value.identity
        or _digest(file_record(value)) != value.identity
    ):
        raise YamlPrefixRejected(
            "Issued exact immutable YAML file input required", stage="file_authority"
        )
    path, info, digest = _file(value.filename)
    if str(path) != value.filename or info != value.stat or digest != value.sha256:
        raise YamlPrefixRejected("YAML file bytes/identity changed", stage="file_epoch")


def source_plan():
    if hashlib.sha256(Path(parameters.__file__).read_bytes()).hexdigest() != PARAMETERS_SHA256:
        raise ValueError("Explicit repaired native parameter producer required")
    plan = parameters.source_plan()
    native = parameters.inherited.tissue.aliases.NATIVE
    cls = parameters.inherited._class(
        ast.parse((native / parameters.PARAMETERS).read_bytes()), "Parameters"
    )
    load = parameters.inherited._method(cls, "load")
    expected = (
        ast.parse(
            "def load(self,*args,**kwargs):\n"
            " from betse.science.compat import compatconf\n"
            ' YAML_VERSION="1.2"\n'
            " super().load(*args,yaml_version=YAML_VERSION,**kwargs)"
        )
        .body[0]
        .body
    )
    if ast.dump(ast.Module(body=load.body[:3], type_ignores=[])) != ast.dump(
        ast.Module(body=expected, type_ignores=[])
    ):
        raise ValueError("Original YAML1.2 read-prefix statements/order changed")
    return dict(
        law=LAW_ID,
        native_pins=plan["native_pins"],
        parameter_producer=PARAMETERS_SHA256,
        prefix_statements=3,
        prefix_lines=(load.body[0].lineno, load.body[2].end_lineno),
        next_source_line=load.body[3].lineno,
        yaml_version="1.2",
        continuation=(
            "compatconf.upgrade_sim_conf -> reload_paths -> subconfiguration loads -> "
            "parameter/ion stores"
        ),
        full_parameters_load_or_phase_admitted=False,
    )


def request_record(value):
    return dict(
        law=LAW_ID,
        parent_trial=value.parent_trial_identity,
        file=value.file.identity,
        source_identity=value.source_identity,
        same_live_p=True,
        prefix_only=True,
    )


def from_unloaded(parent, file, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise YamlPrefixRejected("Explicit YAML-prefix source law required", stage="law")
    plan = source_plan()
    context = parameters._validate(parent)
    _verify_file(file)
    value = Request(parent, file, context.trial.identity, _digest(plan), "")
    value = replace(value, identity=_digest(request_record(value)))
    _REQUESTS[value] = (
        context,
        context.p,
        context.trial,
        context.graph,
        context.source,
        context.runtime,
        _digest(context.plan),
    )
    return value


def _prefix(context):
    original = parameters._method_original(context.parent.source, "load")
    if original.__defaults__ is not None or original.__kwdefaults__ is not None:
        raise ValueError("Original Parameters.load defaults/header changed")
    path = parameters.inherited.tissue.aliases.NATIVE / parameters.PARAMETERS
    cls = parameters.inherited._class(ast.parse(path.read_bytes()), "Parameters")
    expected = parameters._method_code(cls, "load", str(path), native_context=True)
    if original.__globals__ is not vars(
        context.parent.source.modules["betse.science.parameters"]
    ) or parameters.inherited._code(original.__code__) != parameters.inherited._code(expected):
        raise ValueError("Actual original Parameters.load executable/globals changed")
    selected = copy.deepcopy(cls)
    method = parameters.inherited._method(selected, "load")
    method.body = method.body[:3]
    code = parameters._method_code(selected, "load", str(path))
    for name, cell in zip(original.__code__.co_freevars, original.__closure__ or (), strict=True):
        if name == "__class__" and cell.cell_contents is not context.parent.source.cls:
            raise ValueError("Native load super/class-cell association changed")
    cached = original.__globals__["__builtins__"]
    if type(cached) is not dict:
        cached = vars(cached)
    if cached is not original.__builtins__:
        raise ValueError("Original load construction namespace/cached builtins differ")
    value = FunctionType(
        code, original.__globals__, original.__name__, original.__defaults__, original.__closure__
    )
    if value.__builtins__ is not original.__builtins__:
        raise ValueError("Prefix cached builtins changed")
    return value


def _runtime_types(context):
    """Exact loaded classes, with executable/file runtime pins; no type hydration."""
    types = set()
    files = {}
    bindings = []
    yaml = context.parent.source.yaml
    for name, module in tuple(sys.modules.items()):
        if not (name.startswith("ruamel.yaml") or name.startswith("betse.")):
            continue
        path = getattr(module, "__file__", None)
        if path:
            files[str(Path(path).resolve())] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        bindings.extend((name, module, vars(module)))
        for key, value in vars(module).items():
            if not isinstance(value, type):
                continue
            if value.__module__.startswith("ruamel.yaml") or issubclass(value, yaml):
                types.add(value)
                bindings.extend((key, value))
    return frozenset(types), files, ((), tuple(bindings))


def _capture(context):
    return graphs.capture(
        dict(
            parameters=context.p,
            parsed_configuration=vars(context.p).get("_conf"),
            file_identity=context.file_record,
        ),
        yaml_base=context.parent.source.yaml,
        runtime_types=context.runtime_types,
    )


def _class_bindings(types):
    return (
        (),
        tuple(
            atom
            for cls in sorted(types, key=lambda c: (c.__module__, c.__qualname__))
            for atom in parameters.inherited.tissue._surface(cls)
        ),
    )


def _function_bindings(function, _lookup_names=bytecode_bindings.lookup_names):
    if type(function) is not FunctionType:
        raise ValueError("Exact source-prefix function required")
    namespace = function.__globals__["__builtins__"]
    if type(namespace) is not dict:
        namespace = vars(namespace)
    if namespace is not function.__builtins__:
        raise ValueError("Prefix construction namespace/cached builtins differ")
    labels = []
    objects = [
        function,
        function.__code__,
        function.__globals__,
        function.__builtins__,
        function.__defaults__,
        function.__kwdefaults__,
    ]
    objects.extend(parameters.inherited.tissue.aliases._atoms(function))
    # Small functions keep the original transport: authenticating the compact
    # decoder costs more than it saves there. Large bodies avoid constructing
    # Instruction objects; all values below are still resolved afresh.
    code = function.__code__
    lookups = (
        _lookup_names(code)
        if len(code.co_code) >= 512
        else (
            (instruction.opname, instruction.argval)
            for instruction in dis.get_instructions(function)
            if instruction.opname in ("LOAD_GLOBAL", "IMPORT_NAME")
        )
    )
    for operation, name in lookups:
        if operation == "LOAD_GLOBAL":
            local = name in function.__globals__
            labels.append((name, local))
            objects.append(function.__globals__[name] if local else function.__builtins__[name])
        elif operation == "IMPORT_NAME":
            labels.append(("import", name))
            objects.append(function.__builtins__["__import__"])
    return tuple(labels), tuple(objects)


def _bindings():
    decoder_labels, decoder_atoms = bytecode_bindings.runtime_bindings()
    functions = (
        _digest,
        _file,
        file_record,
        input_file,
        _verify_file,
        source_plan,
        request_record,
        from_unloaded,
        _prefix,
        _runtime_types,
        _capture,
        _class_bindings,
        _function_bindings,
        _bindings,
        trial_record,
        _check,
        _validate,
        _invoke,
        prepare,
        require_complete_load,
        begin_paths,
        parameters.begin_yaml_prefix,
        parameters._yaml_prefix_parent,
        parameters._observe,
        parameters._observe.__wrapped__,
        graphs.capture,
    )
    return (
        decoder_labels,
        (
            _FILES,
            _REQUESTS,
            _CONSUMED,
            _CLAIMED,
            _ISSUED,
            _LOCK,
            _ACTIVE,
            LAW_ID,
            PATHS_LAW,
            PARAMETERS_SHA256,
            MAX_FILE_BYTES,
            BASE,
            graphs.MAX_NODES,
            graphs.MAX_BYTES,
            graphs.MAX_DEPTH,
            graphs.struct,
            graphs.struct.pack,
            record_digest,
            *record_digest.bindings(),
            bytecode_bindings,
            *decoder_atoms,
            *(atom for fn in functions for atom in parameters.inherited.tissue.aliases._atoms(fn)),
        ),
    )


def trial_record(trial):
    return dict(
        law=LAW_ID,
        request=trial.request_identity,
        before=trial.before_cache_identity,
        graph=trial.graph.identity,
        work=trial.work,
        prefix_completed=trial.prefix_completed,
        full_load_completed=False,
    )


def _check(context):
    request = context.request
    if (
        context.invalid
        or context.thread != get_ident()
        or _CONSUMED.get(request) is not context
        or _CLAIMED.get(request.parent) is not context
        or request not in _REQUESTS
        or _digest(request_record(request)) != request.identity
    ):
        raise ValueError("Original one-shot YAML attempt/absolute parent epoch changed")
    old = _REQUESTS[request]
    owner, parent = parameters._yaml_prefix_parent(context.lease)
    if (
        owner is not request.parent
        or parent is not context.parent
        or parent is not old[0]
        or parent.p is not old[1]
        or context.p is not parent.p
        or parent.trial is not old[2]
        or parent.graph is not old[3]
        or parent.source is not old[4]
        or parent.runtime is not old[5]
        or _digest(parent.plan) != old[6]
        or not parent.invalid
        or parent.active
    ):
        raise ValueError("Original retired unloaded parent/live p association changed")
    if type(context.p) is not parent.source.cls:
        raise ValueError("Original native Parameters class changed")
    _verify_file(request.file)
    parameters.inherited._same(_bindings(), context.bindings)
    parameters.inherited._same(_function_bindings(context.function), context.function_bindings)
    parameters.inherited._same(parameters._runtime(parent.source), old[5])
    if _digest(source_plan()) != request.source_identity:
        raise ValueError("YAML prefix producer changed")


class YamlPrefixOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use same-object source YAML-prefix preparation")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live YAML prefix cannot be serialized")

    @property
    def parameters(self):
        return _validate(self).p

    @property
    def trial(self):
        return _validate(self).trial


def _validate(owner):
    if type(owner) is not YamlPrefixOwner or owner not in _ISSUED:
        raise YamlPrefixRejected("Issued YAML prefix owner required", stage="owner")
    context = _ISSUED[owner]
    try:
        if (
            context.invalid
            or context.active
            or context.owner is not owner
            or context.thread != get_ident()
        ):
            raise ValueError("Invalid YAML prefix epoch")
        _check(context)
        kinds, files, bindings = _runtime_types(context)
        if kinds != context.runtime_types or files != context.runtime_files:
            raise ValueError("YAML runtime class/file inventory changed")
        parameters.inherited._same(bindings, context.runtime_namespaces)
        parameters.inherited._same(_class_bindings(context.runtime_types), context.runtime_classes)
        for filename, pin in context.runtime_files.items():
            if hashlib.sha256(Path(filename).read_bytes()).hexdigest() != pin:
                raise ValueError("YAML/native runtime producer changed")
        parameters.inherited._same_graph(_capture(context), context.graph)
        caches = parameters.inherited.tissue.core.caches
        caches.validate(context.trial.graph)
        if caches.snapshot(context.graph[1]).identity != context.trial.graph.identity:
            raise ValueError("YAML graph trial/cache association changed")
        if context.trial.identity != _digest(trial_record(context.trial)):
            raise ValueError("YAML prefix trial changed")
    except BaseException as error:
        context.invalid = True
        raise YamlPrefixRejected(
            "Stale YAML prefix owner refused",
            stage="owner_drift",
            request=context.request,
            partial=context,
            trial=context.trial,
            source_error=error,
        ) from error
    return context


def _invoke(context):
    with parameters.inherited.tissue.aliases.issuing_native_imports(
        parameters.inherited.tissue.source.SOURCE_PINS
    ):
        return context.function(context.p, context.request.file.filename)


def prepare(request, *, enabled=False):
    if enabled is not True or os.environ.get(parameters.inherited.RELEASE) != "1":
        raise YamlPrefixRejected(
            "Actual YAML/source read remains held", stage="release", request=request
        )
    with _LOCK:
        if _ACTIVE:
            _ACTIVE[-1].invalid = True
            raise YamlPrefixRejected(
                "Reentrant YAML prefix refused", stage="reentrant", request=request
            )
        if (
            type(request) is not Request
            or request not in _REQUESTS
            or _digest(request_record(request)) != request.identity
        ):
            raise YamlPrefixRejected(
                "Issued same-object/file request required", stage="request", request=request
            )
        if request in _CONSUMED or request.parent in _CLAIMED:
            raise YamlPrefixRejected(
                "YAML load attempt already consumed", stage="consumed", request=request
            )
        context = SimpleNamespace(
            request=request,
            thread=get_ident(),
            active=True,
            invalid=False,
            stage="load_admission",
            work=[],
            locals={},
            observation_error=None,
            observation_errors=(),
            observation_origin=None,
            observation_raw=None,
            prefix_completed=False,
        )
        _CONSUMED[request] = _CLAIMED[request.parent] = context
        _ACTIVE.append(context)
        error = None
        try:
            context.bindings = _bindings()
            _verify_file(request.file)
            context.parent = parameters._validate(request.parent)
            old = _REQUESTS[request]
            if (
                context.parent is not old[0]
                or context.parent.p is not old[1]
                or context.parent.trial is not old[2]
            ):
                raise ValueError("Original unloaded parent changed")
            if _digest(source_plan()) != request.source_identity:
                raise ValueError("YAML source epoch changed")
            context.function = _prefix(context)
            context.function_bindings = _function_bindings(context.function)
            context.lease = parameters.begin_yaml_prefix(request.parent, law_id=LAW_ID)
            owner, parent = parameters._yaml_prefix_parent(context.lease)
            if owner is not request.parent or parent is not context.parent:
                raise ValueError("Foreign parameter lease")
            context.p = parent.p
            context.stage = "native_yaml_read_prefix"
            context.file_record = file_record(request.file)
            _check(context)
            with parameters._observe(context):
                _invoke(context)
            context.prefix_completed = True
            if context.observation_error is None:
                _check(context)
                context.stage = "yaml_file_association"
                fields = vars(context.p)
                if (
                    fields.get("_conf") is None
                    or fields.get("_conf_filename") != request.file.filename
                    or fields.get("_conf_dirname") != str(Path(request.file.filename).parent)
                ):
                    raise ValueError("Native parser/file association incomplete")
                if any(
                    fields.get(name, "missing") is not None
                    for name in context.parent.plan["path_fields"]
                ):
                    raise ValueError("YAML prefix may not run path/parameter continuation")
                context.runtime_types, context.runtime_files, context.runtime_namespaces = (
                    _runtime_types(context)
                )
                context.runtime_classes = _class_bindings(context.runtime_types)
        except BaseException as primary:
            error = primary
        try:
            if error is None and context.observation_error is None:
                context.stage = "roundtrip_graph_capture"
                context.graph = _capture(context)
                cache = parameters.inherited.tissue.core.caches.snapshot(context.graph[1])
                trial = Trial(
                    request.identity,
                    context.parent.trial.cache.identity,
                    cache,
                    tuple(context.work),
                    True,
                    "",
                )
                context.trial = replace(trial, identity=_digest(trial_record(trial)))
                _check(context)
                parameters.inherited._same_graph(_capture(context), context.graph)
                result = object.__new__(YamlPrefixOwner)
                _check(context)
                context.owner = result
                _ISSUED[result] = context
                return result
        except BaseException as capture:
            parameters.inherited.tissue.captures._remember_observation_error(
                context, capture, origin=context.stage, raw=context
            )
        finally:
            context.active = False
            _ACTIVE.pop()
        context.invalid = True
        refusal = YamlPrefixRejected(
            "YAML prefix issued no child",
            stage=context.stage,
            request=request,
            partial=context,
            source_error=error,
            capture_errors=context.observation_errors,
        )
        raise refusal from (error if error is not None else context.observation_error)


def require_complete_load(owner):
    context = _validate(owner)
    raise YamlPrefixRejected(
        "Original compatibility/path/parameter continuation remains held",
        stage="full_load_prerequisites",
        request=context.request,
        trial=context.trial,
        partial=dict(
            next_source_line=source_plan()["next_source_line"],
            full_load_or_phase_or_INIT_admitted=False,
        ),
    )


def begin_paths(owner, *, law_id):
    """Irreversibly hand the actual read epoch to the declared next source stage."""
    if type(law_id) is not str or law_id != PATHS_LAW:
        raise YamlPrefixRejected("Explicit compatibility/path consumer required", stage="consumer")
    if os.environ.get(parameters.inherited.RELEASE) != "1":
        raise YamlPrefixRejected("Actual YAML handoff remains held", stage="consumer")
    with _LOCK:
        context = _validate(owner)
        context.invalid = True
        return context
