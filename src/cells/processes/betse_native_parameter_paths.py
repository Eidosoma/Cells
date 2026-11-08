"""Same-p original compatibility/path continuation; full Parameters stays closed.

The policy permits paths; it never supplies configuration or computed stores.
All source helpers are the actual retained original functions, not projections.
"""

import ast
import hashlib
import io
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import CodeType, ModuleType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_parameter_yaml_prefix as prefix

LAW_ID = prefix.PATHS_LAW
SUBCONFIGURATION_LAW = "betse_native_same_parameter_subconfigurations@1"
YAML_SHA256 = 'a01470c493818d93cc68737dcb945d61b8d3bdd4e47c1491baaaf6a25ddc87a0'
RELEASE = "CELLS_NATIVE_PARAMETER_PATHS_RELEASED"
BASE = Path("/mnt/workspaces")
COMPAT = "betse/science/compat/compatconf.py"
VERSIONS = (
    "upgrade_sim_conf",
    "_upgrade_sim_conf_to_0_5_0",
    "_upgrade_sim_conf_to_0_5_2",
    "_upgrade_sim_conf_to_0_6_0",
    "_upgrade_sim_conf_to_0_7_1",
    "_upgrade_sim_conf_to_1_0_0",
)
EXPORT_UPGRADE = "_upgrade_sim_conf_to_1_0_0_exports_name"
FIELDS = (
    "init_pickle_dirname",
    "sim_pickle_dirname",
    "init_pickle_filename",
    "seed_pickle_filename",
    "sim_pickle_filename",
    "init_export_dirname",
    "sim_export_dirname",
    "grn_config_filename",
    "grn_pickle_dirname",
    "grn_pickle_filename",
    "grn_unpickle_filename",
)
DIRECTORIES = (
    "init_pickle_dirname",
    "sim_pickle_dirname",
    "init_export_dirname",
    "sim_export_dirname",
    "grn_pickle_dirname",
)
_POLICIES, _REQUESTS, _CONSUMED, _CLAIMED, _ISSUED = (WeakKeyDictionary() for _ in range(5))
_LOCK, _ACTIVE = RLock(), []
_AUDIT_INSTALLED = False


class PathsRejected(ValueError):
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
class PathPolicy:
    paths: tuple
    identity: str


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    parent: prefix.YamlPrefixOwner
    parent_trial_identity: str
    policy: PathPolicy
    source_identity: str
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("Live continuation requests cannot be serialized")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    before_trial_identity: str
    cache: object
    work: tuple
    calls: tuple
    filesystem: tuple
    upgrade_completed: bool
    paths_completed: bool
    identity: str


def _digest(value):
    return prefix._digest(value)


def _path(value):
    if type(value) is not str or not value or len(value) > 4096 or "\x00" in value:
        raise ValueError("Explicit bounded original pathname required")
    p = Path(value)
    if not p.is_absolute() or not p.resolve().is_relative_to(BASE):
        raise ValueError("Original path must remain under /mnt/workspaces")
    if any(part.is_symlink() for part in (p, *p.parents)):
        raise ValueError("Linked original path refused")
    return p.resolve()


def policy_record(value):
    return dict(
        law=LAW_ID,
        paths=value.paths,
        authority="permission only; never native derivation or stored paths",
    )


def declare_paths(*, paths, law_id):
    if (
        type(law_id) is not str
        or law_id != LAW_ID
        or type(paths) is not tuple
        or tuple(n for n, _ in paths) != FIELDS
    ):
        raise PathsRejected(
            "All original ordered path fields must be declared", stage="path_declaration"
        )
    for name, value in paths:
        if value is None and name == "grn_unpickle_filename":
            continue
        _path(value)
    value = PathPolicy(paths, "")
    value = replace(value, identity=_digest(policy_record(value)))
    _POLICIES[value] = value.identity
    return value


def _policy(value):
    if (
        type(value) is not PathPolicy
        or _POLICIES.get(value) != value.identity
        or _digest(policy_record(value)) != value.identity
    ):
        raise PathsRejected("Issued exact path permission required", stage="path_authority")
    for name, path in value.paths:
        if path is None and name == "grn_unpickle_filename":
            continue
        _path(path)


def source_plan():
    if hashlib.sha256(Path(prefix.__file__).read_bytes()).hexdigest() != YAML_SHA256:
        raise ValueError("Explicit YAML read/handoff producer required")
    parent = prefix.source_plan()
    native = prefix.parameters.inherited.tissue.aliases.NATIVE
    cls = prefix.parameters.inherited._class(
        ast.parse((native / prefix.parameters.PARAMETERS).read_bytes()), "Parameters"
    )
    load = prefix.parameters.inherited._method(cls, "load")
    reload = prefix.parameters.inherited._method(cls, "reload_paths")
    expected = ast.parse("compatconf.upgrade_sim_conf(self)\nself.reload_paths()").body
    if ast.dump(ast.Module(body=load.body[3:5], type_ignores=[])) != ast.dump(
        ast.Module(body=expected, type_ignores=[])
    ):
        raise ValueError("Original continuation order/call sites changed")
    tree = ast.parse((native / COMPAT).read_bytes())
    upgrade = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == VERSIONS[0])
    called = tuple(
        n.value.func.id
        for n in upgrade.body
        if isinstance(n, ast.Expr)
        and isinstance(n.value, ast.Call)
        and isinstance(n.value.func, ast.Name)
    )
    if called != VERSIONS[1:]:
        raise ValueError("Original chronological compatibility order changed")
    stores = tuple(
        dict.fromkeys(
            n.targets[0].attr
            for n in ast.walk(reload)
            if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Attribute)
        )
    )
    if set(stores) != set(FIELDS) | {"grn_config_filename_relative"}:
        raise ValueError("Original reload path stores changed")
    return dict(
        law=LAW_ID,
        native_pins=parent["native_pins"],
        yaml_producer=YAML_SHA256,
        compatibility_order=VERSIONS,
        reload_lines=(reload.lineno, reload.end_lineno),
        continuation_lines=(load.body[3].lineno, load.body[4].end_lineno),
        next_source_line=load.body[5].lineno,
        fields=FIELDS,
        directory_order=DIRECTORIES,
        subconfigurations_ions_phase_INIT_admitted=False,
    )


def _function(node, filename, *, native_context=False):
    if type(native_context) is not bool:
        raise ValueError("Explicit native compilation context required")
    tree = ast.Module(body=[node], type_ignores=[])
    if native_context:
        tree = ast.parse(Path(filename).read_bytes(), filename=str(filename))
        originals = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == node.name]
        if len(originals) != 1 or ast.dump(originals[0], include_attributes=True) != ast.dump(
            node, include_attributes=True
        ):
            raise ValueError("Exact original function AST required for native compilation context")
    code = compile(tree, str(filename), "exec", dont_inherit=True)
    return next(v for v in code.co_consts if type(v) is CodeType and v.co_name == node.name)


def _native(yaml):
    """Resolve the actual import captured by the already executed read prefix."""
    native = prefix.parameters.inherited.tissue.aliases.NATIVE
    key = (str(native / prefix.parameters.PARAMETERS), "Parameters.load")
    frame = yaml.locals.get(key)
    if (
        type(frame) is not dict
        or frame.get("self") is not yaml.p
        or type(frame.get("args")) is not tuple
        or frame["args"] != (yaml.request.file.filename,)
        or type(frame.get("kwargs")) is not dict
        or frame["kwargs"]
        or type(frame.get("YAML_VERSION")) is not str
        or frame["YAML_VERSION"] != "1.2"
        or frame.get("__class__") is not yaml.parent.source.cls
    ):
        raise PathsRejected(
            "Actual original read-frame/import authority absent", stage="retained_import"
        )
    module = frame.get("compatconf")
    if (
        type(module) is not ModuleType
        or sys.modules.get("betse.science.compat.compatconf") is not module
        or Path(module.__file__).resolve() != native / COMPAT
    ):
        raise PathsRejected(
            "Actual retained original compat module required", stage="retained_import"
        )
    prefix.parameters.inherited.tissue.aliases._check_modules()
    reload = yaml.parent.source.cls.reload_paths
    original = prefix.parameters._method_original(yaml.parent.source, "reload_paths")
    dirs = original.__globals__["dirs"]
    if dirs is not sys.modules.get("betse.util.path.dirs"):
        raise ValueError("Original reload directory helper module changed")
    return SimpleNamespace(
        compat=module,
        upgrade=module.upgrade_sim_conf,
        reload=reload,
        mkdir=dirs.make_unless_dir,
        methods={name: getattr(module, name) for name in (*VERSIONS, EXPORT_UPGRADE)},
    )


def _native_bindings(context):
    native = prefix.parameters.inherited.tissue.aliases.NATIVE
    tree = ast.parse((native / COMPAT).read_bytes())
    objects = [context.native.compat, vars(context.native.compat)]
    labels = []
    for name, fn in context.native.methods.items():
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
        chain = prefix.parameters.inherited._chain(fn)
        original = chain[-1]
        if original.__globals__ is not vars(
            context.native.compat
        ) or prefix.parameters.inherited._code(
            original.__code__
        ) != prefix.parameters.inherited._code(
            _function(node, native / COMPAT, native_context=True)
        ):
            raise ValueError("Original compatibility executable/namespace changed")
        for part in chain:
            label, refs = prefix._function_bindings(part)
            labels.append((name, label))
            objects.extend(refs)
    cls = prefix.parameters.inherited._class(
        ast.parse((native / prefix.parameters.PARAMETERS).read_bytes()), "Parameters"
    )
    chain = prefix.parameters.inherited._chain(context.native.reload)
    original = prefix.parameters._method_original(context.parent.source, "reload_paths")
    if chain[0] is not context.parent.source.cls.reload_paths or chain[-1] is not original:
        raise ValueError("Original reload method identity changed")
    expected = prefix.parameters._method_code(
        cls, "reload_paths", str(native / prefix.parameters.PARAMETERS), native_context=True
    )
    if prefix.parameters.inherited._code(original.__code__) != prefix.parameters.inherited._code(
        expected
    ):
        raise ValueError("Original reload executable changed")
    objects.extend(prefix.parameters._method_wrapper_bindings(chain[0], context.parent.source.cls))
    for fn in (*chain, *prefix.parameters.inherited._chain(context.native.mkdir)):
        label, refs = prefix._function_bindings(fn)
        labels.append(label)
        objects.extend(refs)
    return tuple(labels), tuple(objects)


def request_record(value):
    return dict(
        law=LAW_ID,
        parent_trial=value.parent_trial_identity,
        paths=value.policy.identity,
        source=value.source_identity,
        same_live_p=True,
    )


def from_yaml(owner, policy, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise PathsRejected("Explicit next source law required", stage="law")
    plan = source_plan()
    yaml = prefix._validate(owner)
    _policy(policy)
    native = _native(yaml)
    value = Request(owner, yaml.trial.identity, policy, _digest(plan), "")
    value = replace(value, identity=_digest(request_record(value)))
    _REQUESTS[value] = (yaml, yaml.p, yaml.p._conf, yaml.trial, yaml.graph, yaml.parent, native)
    return value


def _stable(context):
    fields = vars(context.p)
    allowed = set(context.before_names) | set(FIELDS) | {"config", "grn_config_filename_relative"}
    if not set(context.before_names).issubset(fields) or not set(fields).issubset(allowed):
        raise ValueError("Continuation changed unrelated parameter stores")
    return prefix.graphs.capture(
        {name: fields[name] for name in context.stable_names},
        yaml_base=context.parent.source.yaml,
        runtime_types=context.yaml.runtime_types,
    )


def _check(context):
    request = context.request
    old = _REQUESTS.get(request)
    if (
        context.invalid
        or context.thread != get_ident()
        or _CONSUMED.get(request) is not context
        or _CLAIMED.get(request.parent) is not context
        or old is None
        or _digest(request_record(request)) != request.identity
    ):
        raise ValueError("Original one-shot continuation epoch changed")
    if (
        context.yaml is not old[0]
        or context.p is not old[1]
        or context.p._conf is not old[2]
        or context.yaml.trial is not old[3]
        or context.yaml.graph is not old[4]
        or context.parent is not old[5]
        or not context.yaml.invalid
        or context.yaml.active
        or type(context.p) is not context.parent.source.cls
    ):
        raise ValueError("Original typed YAML/config/parent association changed")
    _policy(request.policy)
    prefix._verify_file(context.yaml.request.file)
    prefix.parameters.inherited._same(_bindings(), context.bindings)
    prefix.parameters.inherited._same(prefix._bindings(), context.yaml.bindings)
    prefix.parameters.inherited._same(
        prefix.parameters._runtime(context.parent.source), context.parent.runtime
    )
    prefix.parameters.inherited._same(_native_bindings(context), context.native_bindings)
    prefix.parameters.inherited._same_graph(_stable(context), context.stable)
    if _digest(source_plan()) != request.source_identity:
        raise ValueError("Continuation source epoch changed")


def _computed(context):
    values = tuple((name, vars(context.p).get(name, "missing")) for name in FIELDS)
    if values != context.request.policy.paths or any(
        type(v) is not str and v is not None for _, v in values
    ):
        raise ValueError("Native computed original paths differ from declared permission")
    for name, value in values:
        if value is None and name == "grn_unpickle_filename":
            continue
        _path(value)
    if vars(context.p).get("config") is not context.config:
        raise ValueError("Original compatibility config alias changed")
    return values


def _directory_entry(context, dirnames):
    _check(context)
    _computed(context)
    expected = tuple(dict(context.request.policy.paths)[name] for name in DIRECTORIES)
    if (
        context.stage != "native_reload_paths"
        or type(dirnames) is not tuple
        or dirnames != expected
        or context.directory_calls
    ):
        raise ValueError("Original single directory call/order changed")
    context.directory_calls += 1
    context.directory_depth += 1
    context.directory_targets = tuple(_path(p) for p in expected)


def _audit(event, args):
    if not _ACTIVE:
        return
    context = _ACTIVE[-1]
    if context.thread != get_ident():
        raise ValueError("Foreign thread during native continuation")
    if event == "cells.native_parameter_paths.guard_probe":
        if args == (context,):
            context.audit_ready = True
        return
    if event == "os.mkdir":
        if not context.directory_depth or not context.directory_calls:
            raise ValueError("Directory write outside original helper refused")
        target = _path(args[0])
        if len(args) > 2 and args[2] not in (-1, None):
            raise ValueError("Relative directory descriptor refused")
        if not any(target == p or target in p.parents for p in context.directory_targets):
            raise ValueError("Undeclared directory write refused")
        if len(context.filesystem) >= 128:
            raise ValueError("Bounded original directory writes exhausted")
        context.filesystem.append(
            dict(event=event, path=args[0], status="requested_not_creation_receipt")
        )
    elif event == "open":
        flags = args[2]
        if type(flags) is int and flags & (
            os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
        ):
            raise ValueError("File writes are outside directory-only continuation")
    elif event in {
        "os.remove",
        "os.rename",
        "os.rmdir",
        "os.link",
        "os.symlink",
        "os.chmod",
        "os.truncate",
        "os.utime",
        "os.chdir",
    }:
        raise ValueError("Other filesystem mutation outside original directory scope")


def _install_audit(context):
    global _AUDIT_INSTALLED
    if not _AUDIT_INSTALLED:
        sys.addaudithook(_audit)
        _AUDIT_INSTALLED = True
    sys.audit("cells.native_parameter_paths.guard_probe", context)
    if not context.audit_ready:
        raise ValueError("Directory audit guard installation unavailable")


@contextmanager
def _observe(context):
    with prefix.parameters._observe(context):
        previous, trace = sys.getprofile(), sys.gettrace()
        directory = prefix.parameters.inherited._chain(context.native.mkdir)[-1].__code__
        selected = {
            prefix.parameters.inherited._chain(fn)[-1].__code__: name
            for name, fn in context.native.methods.items()
        }
        selected[prefix.parameters.inherited._chain(context.native.reload)[-1].__code__] = (
            "reload_paths"
        )
        selected[directory] = "make_unless_dir"

        def profile(frame, event, arg):
            if event == "c_call" and getattr(arg, "__name__", None) in {
                "write",
                "writelines",
                "truncate",
            }:
                stream = getattr(arg, "__self__", None)
                if (
                    isinstance(stream, io.IOBase)
                    and stream is not sys.stdout
                    and stream is not sys.stderr
                ):
                    raise ValueError("Unowned pre-opened file writer refused")
            if previous is not None:
                previous(frame, event, arg)
            if event == "call":
                if frame.f_code in selected:
                    context.calls.append(selected[frame.f_code])
                    if frame.f_code is directory:
                        _directory_entry(context, frame.f_locals.get("dirnames"))
            elif event == "return" and frame.f_code in selected:
                try:
                    context.locals[(frame.f_code.co_filename, frame.f_code.co_qualname)] = dict(
                        frame.f_locals
                    )
                except BaseException as error:
                    prefix.parameters.inherited.tissue.captures._remember_observation_error(
                        context, error, origin="continuation_locals", raw=frame
                    )
                if frame.f_code is directory:
                    context.directory_depth -= 1

        sys.setprofile(profile)
        try:
            yield
        finally:
            sys.setprofile(previous)
            sys.settrace(trace)


def _upgrade(context):
    with prefix.parameters.inherited.tissue.aliases.issuing_native_imports(
        prefix.parameters.inherited.tissue.source.SOURCE_PINS
    ):
        return context.native.upgrade(context.p)


def _reload(context):
    with prefix.parameters.inherited.tissue.aliases.issuing_native_imports(
        prefix.parameters.inherited.tissue.source.SOURCE_PINS
    ):
        return context.native.reload(context.p)


def _directories_complete(context):
    return all(Path(dict(context.request.policy.paths)[name]).is_dir() for name in DIRECTORIES)


def _bindings():
    funcs = (
        source_plan,
        _function,
        _native,
        _native_bindings,
        policy_record,
        declare_paths,
        _policy,
        _path,
        request_record,
        from_yaml,
        _stable,
        _check,
        _computed,
        _directory_entry,
        _audit,
        _install_audit,
        _observe,
        _observe.__wrapped__,
        _upgrade,
        _reload,
        _directories_complete,
        _bindings,
        trial_record,
        _validate,
        prepare,
        require_complete_load,
        handoff_subconfigurations,
        handoff_subconfigurations.__wrapped__,
        prefix.begin_paths,
    )
    return (
        (),
        (
            _POLICIES,
            _REQUESTS,
            _CONSUMED,
            _CLAIMED,
            _ISSUED,
            _LOCK,
            _ACTIVE,
            LAW_ID,
            SUBCONFIGURATION_LAW,
            YAML_SHA256,
            RELEASE,
            BASE,
            FIELDS,
            DIRECTORIES,
            VERSIONS,
            sys.audit,
            sys.addaudithook,
            *(
                atom
                for fn in funcs
                for atom in prefix.parameters.inherited.tissue.aliases._atoms(fn)
            ),
        ),
    )


def trial_record(value):
    return dict(
        law=LAW_ID,
        request=value.request_identity,
        before=value.before_trial_identity,
        cache=value.cache.identity,
        work=value.work,
        calls=value.calls,
        filesystem=value.filesystem,
        upgrade_completed=value.upgrade_completed,
        paths_completed=value.paths_completed,
        full_load_completed=False,
    )


class PathsOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use same-p original continuation")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live continuation owners cannot be serialized")

    @property
    def parameters(self):
        return _validate(self).p

    @property
    def trial(self):
        return _validate(self).trial


def _validate(owner):
    if type(owner) is not PathsOwner or owner not in _ISSUED:
        raise PathsRejected("Issued compatibility/path owner required", stage="owner")
    context = _ISSUED[owner]
    try:
        if context.active or context.owner is not owner:
            raise ValueError("Active/replaced path owner")
        _check(context)
        _computed(context)
        prefix.parameters.inherited._same_graph(prefix._capture(context), context.graph)
        prefix.parameters.inherited._same(
            prefix._class_bindings(context.runtime_types), context.runtime_classes
        )
        kinds, files, namespaces = prefix._runtime_types(context)
        if kinds != context.runtime_types or files != context.runtime_files:
            raise ValueError("Continuation runtime changed")
        prefix.parameters.inherited._same(namespaces, context.runtime_namespaces)
        caches = prefix.parameters.inherited.tissue.core.caches
        caches.validate(context.trial.cache)
        if (
            caches.snapshot(context.graph[1]).identity != context.trial.cache.identity
            or _digest(trial_record(context.trial)) != context.trial.identity
        ):
            raise ValueError("Continuation trial/cache changed")
    except BaseException as error:
        context.invalid = True
        raise PathsRejected(
            "Stale compatibility/path owner refused",
            stage="owner_drift",
            request=context.request,
            partial=context,
            trial=context.trial,
            source_error=error,
        ) from error
    return context


def prepare(request, *, enabled=False):
    if (
        enabled is not True
        or os.environ.get(RELEASE) != "1"
        or os.environ.get(prefix.parameters.inherited.RELEASE) != "1"
    ):
        raise PathsRejected(
            "Actual compatibility/directory continuation held", stage="release", request=request
        )
    with _LOCK:
        if _ACTIVE:
            _ACTIVE[-1].invalid = True
            raise PathsRejected(
                "Reentrant continuation refused", stage="reentrant", request=request
            )
        if (
            type(request) is not Request
            or request not in _REQUESTS
            or _digest(request_record(request)) != request.identity
        ):
            raise PathsRejected(
                "Issued exact continuation request required", stage="request", request=request
            )
        if request in _CONSUMED or request.parent in _CLAIMED:
            raise PathsRejected("Continuation attempt consumed", stage="consumed", request=request)
        context = SimpleNamespace(
            request=request,
            thread=get_ident(),
            active=True,
            invalid=False,
            stage="continuation_admission",
            work=[],
            locals={},
            calls=[],
            filesystem=[],
            directory_calls=0,
            directory_depth=0,
            directory_targets=(),
            audit_ready=False,
            observation_error=None,
            observation_errors=(),
            observation_origin=None,
            observation_raw=None,
            upgrade_completed=False,
            paths_completed=False,
        )
        _CONSUMED[request] = _CLAIMED[request.parent] = context
        _ACTIVE.append(context)
        error = None
        try:
            context.bindings = _bindings()
            _policy(request.policy)
            context.yaml = prefix._validate(request.parent)
            old = _REQUESTS[request]
            if context.yaml is not old[0] or context.yaml.trial is not old[3]:
                raise ValueError("Original read epoch changed")
            context.native = _native(context.yaml)
            context.parent = context.yaml.parent
            context.p = context.yaml.p
            context.config = context.p._conf
            context.native_bindings = _native_bindings(context)
            context.before_names = tuple(vars(context.p))
            context.stable_names = tuple(
                n
                for n in context.before_names
                if n not in set(FIELDS) | {"_conf", "config", "grn_config_filename_relative"}
            )
            context.stable = _stable(context)
            retired = prefix.begin_paths(request.parent, law_id=LAW_ID)
            if retired is not context.yaml:
                raise ValueError("Foreign YAML handoff")
            _check(context)
            _install_audit(context)
            context.stage = "native_compatibility_upgrade"
            with _observe(context):
                _upgrade(context)
            context.upgrade_completed = True
            if context.observation_error is None:
                _check(context)
                if (
                    tuple(context.calls) != (*VERSIONS, EXPORT_UPGRADE)
                    or vars(context.p).get("config") is not context.config
                ):
                    raise ValueError("Original compatibility order/config alias incomplete")
                context.stage = "native_reload_paths"
                with _observe(context):
                    _reload(context)
                context.paths_completed = True
                if context.observation_error is None:
                    _check(context)
                    _computed(context)
                    if (
                        context.directory_calls != 1
                        or context.directory_depth
                        or not _directories_complete(context)
                    ):
                        raise ValueError("Original directory completion unavailable")
        except BaseException as primary:
            error = primary
        try:
            if error is None and context.observation_error is None:
                context.stage = "continuation_capture"
                context.file_record = context.yaml.file_record
                context.runtime_types, context.runtime_files, context.runtime_namespaces = (
                    prefix._runtime_types(context)
                )
                context.runtime_classes = prefix._class_bindings(context.runtime_types)
                context.graph = prefix._capture(context)
                cache = prefix.parameters.inherited.tissue.core.caches.snapshot(context.graph[1])
                trial = Trial(
                    request.identity,
                    context.yaml.trial.identity,
                    cache,
                    tuple(context.work),
                    tuple(context.calls),
                    tuple(context.filesystem),
                    True,
                    True,
                    "",
                )
                context.trial = replace(trial, identity=_digest(trial_record(trial)))
                _check(context)
                prefix.parameters.inherited._same_graph(prefix._capture(context), context.graph)
                owner = object.__new__(PathsOwner)
                _check(context)
                context.owner = owner
                _ISSUED[owner] = context
                return owner
        except BaseException as capture:
            prefix.parameters.inherited.tissue.captures._remember_observation_error(
                context, capture, origin=context.stage, raw=context
            )
        finally:
            context.active = False
            _ACTIVE.pop()
        context.invalid = True
        refusal = PathsRejected(
            "Continuation issued no child",
            stage=context.stage,
            request=request,
            partial=context,
            source_error=error,
            capture_errors=context.observation_errors,
        )
        raise refusal from (error if error is not None else context.observation_error)


def require_complete_load(owner):
    context = _validate(owner)
    raise PathsRejected(
        "Original subconfiguration/ion/material/phase continuation unavailable",
        stage="full_load_prerequisites",
        request=context.request,
        trial=context.trial,
        partial=dict(
            next_source_line=source_plan()["next_source_line"],
            full_parameters_or_phase_or_INIT_admitted=False,
        ),
    )


@contextmanager
def handoff_subconfigurations(owner, *, law_id):
    """Retire the path epoch and keep its existing audit guard read-only."""
    if type(law_id) is not str or law_id != SUBCONFIGURATION_LAW:
        raise PathsRejected("Explicit subconfiguration consumer required", stage="consumer")
    if os.environ.get(RELEASE) != "1":
        raise PathsRejected("Actual subconfiguration handoff held", stage="consumer")
    with _LOCK:
        if _ACTIVE:
            _ACTIVE[-1].invalid = True
            raise PathsRejected("Active path epoch cannot be consumed", stage="consumer")
        context = _validate(owner)
        context.invalid = True
        guard = SimpleNamespace(
            thread=get_ident(),
            active=True,
            invalid=False,
            directory_depth=0,
            directory_calls=0,
            directory_targets=(),
            filesystem=[],
            audit_ready=False,
        )
        _ACTIVE.append(guard)
        try:
            _install_audit(guard)
            yield context, guard
        finally:
            guard.active = False
            _ACTIVE.pop()
