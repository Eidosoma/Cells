"""Once-only original network-file branch, ending before GRN line802.

Native join/read/parser work requires explicit release and a genuine retained
boundary. No supplied namespace, parsed object, phase or file result is accepted.
"""

import ast
import hashlib
import io
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import get_ident
from types import MethodType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_parameter_network_boundary as previous

LAW_ID = "betse_native_parameter_network_file_load@1"
PREVIOUS_SHA256 = "15d73328ffdeee700656d1a44bec0ba9e68ca9e1e5a605342618923de77cdea8"
RELEASE = "CELLS_NATIVE_PARAMETER_NETWORK_LOAD_RELEASED"
MAX_PARSER_CALLS = 200000
_OPEN = open
prefix, claims, declarations = previous.prefix, previous.claims, previous.previous
_FIELDS = (
    "molecules_enabled",
    "mol_mit_enabled",
    "expression_data_path_rel",
    "expression_data_path",
    "expression_data",
)
_REQUESTS, _CONSUMED, _CLAIMED, _ISSUED = (WeakKeyDictionary() for _ in range(4))
_ACTIVE = []


class NetworkLoadRejected(ValueError):
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


class _ObserverStop(RuntimeError):
    pass


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    boundary: previous.NetworkBoundary
    binding_identity: str
    source_identity: str
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("Live network-load requests cannot be serialized")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    parent_trial_identity: str
    file_identity: str | None
    cache: object
    source_work: tuple
    metadata_work: tuple
    observations: tuple
    parsed: bool
    identity: str


def _digest(value):
    return previous._digest(value)


def source_plan():
    if hashlib.sha256(Path(previous.__file__).read_bytes()).hexdigest() != PREVIOUS_SHA256:
        raise ValueError("Exact network-boundary producer required")
    return dict(
        law=LAW_ID,
        boundary_producer=PREVIOUS_SHA256,
        original=previous.source_plan(),
        max_parser_calls=MAX_PARSER_CALLS,
        end_before_GRN=802,
        full_Parameters_ions_phase_INIT_admitted=False,
    )


def _born_parser(parser_type, runtime_types, runtime_classes):
    if parser_type not in runtime_types:
        raise ValueError("Actual born YAML parser class authority absent")
    prefix.parameters.inherited._same(prefix._class_bindings(runtime_types), runtime_classes)
    method = vars(parser_type).get("load")
    chain = prefix.parameters.inherited._chain(method)
    return method, chain, tuple(prefix._function_bindings(fn) for fn in chain)


def _native(boundary):
    native = prefix.parameters.inherited.tissue.aliases.NATIVE
    namespace = boundary.original.__globals__
    modules = {"pathnames": namespace.get("pathnames"), "yamls": namespace.get("yamls")}
    expected = {
        "pathnames": ("betse.util.path.pathnames", "betse/util/path/pathnames.py"),
        "yamls": ("betse.lib.yaml.yamls", "betse/lib/yaml/yamls.py"),
    }
    for key, (name, relative) in expected.items():
        module = modules[key]
        if (
            module is not sys.modules.get(name)
            or Path(module.__file__).resolve() != native / relative
        ):
            raise ValueError("Original network helper module absent/foreign")
    modules["iofiles"] = modules["yamls"].iofiles
    if modules["iofiles"] is not sys.modules.get("betse.util.io.iofiles"):
        raise ValueError("Original reader module changed")
    specs = {
        "join": ("pathnames", "join"),
        "load": ("yamls", "load"),
        "reader": ("iofiles", "reading_chars"),
        "factory": ("yamls", "_make_ruamel_parser"),
    }
    roles = {}
    for role, (module_name, name) in specs.items():
        module = modules[module_name]
        function = getattr(module, name)
        chain = prefix.parameters.inherited._chain(function)
        raw = chain[-1]
        path = Path(module.__file__).resolve()
        node = next(
            n
            for n in ast.parse(path.read_bytes()).body
            if isinstance(n, ast.FunctionDef) and n.name == name
        )
        expected_code = declarations.previous.previous.paths._function(
            node, str(path), native_context=True
        )
        if prefix.parameters.inherited._code(raw.__code__) != prefix.parameters.inherited._code(
            expected_code
        ) or raw.__globals__ is not vars(module):
            raise ValueError("Native network helper code/header/globals changed")
        roles[role] = SimpleNamespace(
            function=function,
            raw=raw,
            chain=chain,
            bindings=tuple(prefix._function_bindings(fn) for fn in chain),
            module=module,
            module_name=module_name,
            name=name,
        )
    reader = roles["reader"].raw
    if "open" in reader.__globals__ or reader.__builtins__.get("open") is not _OPEN:
        raise ValueError("Original native reader builtin open changed")
    parser_type = modules["yamls"].ruamel_yaml.YAML
    runtime = boundary.parent.parent
    method, chain, bindings = _born_parser(
        parser_type, runtime.runtime_types, runtime.runtime_classes
    )
    return SimpleNamespace(
        roles=roles,
        modules=modules,
        parser_type=parser_type,
        parser_namespace=modules["yamls"].ruamel_yaml,
        parser_runtime_types=runtime.runtime_types,
        parser_runtime_classes=runtime.runtime_classes,
        parser_method=method,
        parser_chain=chain,
        parser_bindings=bindings,
    )


def _parser_bindings(api):
    if vars(api.parser_type).get("load") is not api.parser_method:
        raise ValueError("Original YAML.load class dispatch changed")
    prefix.parameters.inherited._same(
        prefix._class_bindings(api.parser_runtime_types), api.parser_runtime_classes
    )
    chain = prefix.parameters.inherited._chain(api.parser_method)
    if len(chain) != len(api.parser_chain) or any(
        a is not b for a, b in zip(chain, api.parser_chain, strict=True)
    ):
        raise ValueError("Original YAML.load wrapper association changed")
    values = tuple(prefix._function_bindings(fn) for fn in chain)
    for actual, retained in zip(values, api.parser_bindings, strict=True):
        prefix.parameters.inherited._same(actual, retained)
    return (
        tuple(value[0] for value in values),
        tuple(atom for value in values for atom in value[1]),
    )


def _parser_receiver(api, parser):
    if type(parser) is not api.parser_type:
        raise ValueError("Actual original YAML.load receiver required")
    if "load" in object.__getattribute__(parser, "__dict__"):
        raise ValueError("Instance YAML.load dispatch override refused")
    bound = object.__getattribute__(parser, "load")
    if (
        type(bound) is not MethodType
        or bound.__self__ is not parser
        or bound.__func__ is not api.parser_method
    ):
        raise ValueError("Original YAML.load receiver/class association changed")


def _native_bindings(api):
    labels = []
    refs = [api.parser_type, api.parser_namespace]
    if (
        api.modules["yamls"].iofiles is not api.modules["iofiles"]
        or api.modules["yamls"].ruamel_yaml is not api.parser_namespace
        or api.parser_namespace.YAML is not api.parser_type
    ):
        raise ValueError("Native reader/parser dispatch association changed")
    parser_bindings = _parser_bindings(api)
    labels.append(("YAML.load", parser_bindings[0]))
    refs.extend(parser_bindings[1])
    for name, role in api.roles.items():
        if (
            api.modules[role.module_name] is not role.module
            or vars(role.module).get(role.name) is not role.function
        ):
            raise ValueError("Native network helper dispatch changed")
        chain = prefix.parameters.inherited._chain(role.function)
        if len(chain) != len(role.chain) or any(
            a is not b for a, b in zip(chain, role.chain, strict=True)
        ):
            raise ValueError("Native network wrapper association changed")
        for fn in chain:
            value = prefix._function_bindings(fn)
            labels.append((name, value[0]))
            refs.extend(value[1])
    for name, module in api.modules.items():
        refs.extend((name, module, vars(module)))
    return tuple(labels), tuple(refs)


def _stacks(context):
    return (
        (_ACTIVE, context),
        (previous._ACTIVE, context),
        (declarations._ACTIVE, context),
        (declarations.previous._ACTIVE, context),
        (claims._ACTIVE, context),
        (declarations.previous.previous._ACTIVE, context),
        (declarations.previous.previous.paths._ACTIVE, context.guard),
    )


@contextmanager
def _claim(boundary):
    if type(boundary) is not previous.NetworkBoundary or boundary not in previous._ISSUED:
        previous._validate(boundary)
        raise AssertionError("Unissued boundary validator returned")
    bound = previous._ISSUED[boundary]
    parent = bound.parent
    context = SimpleNamespace(
        boundary_owner=boundary,
        bound=bound,
        parent=parent,
        p=bound.p,
        thread=get_ident(),
        active=True,
        invalid=False,
        retired=False,
        stage="admission",
        work=[],
        metadata_work=[],
        events=[],
        raw_returns=[],
        raw_return=None,
        locals={},
        observation_error=None,
        observation_errors=(),
        observation_origin=None,
        observation_raw=None,
        source_error=None,
        capture_errors=(),
        source_completed=False,
        decoded=None,
        decoded_observed=False,
        join_verified=False,
        parser=None,
        stream=None,
        stream_stat=None,
        counts={name: 0 for name in ("join", "load", "reader", "factory")},
        parser_calls=0,
        stop=_ObserverStop("Observer refusal before native entry"),
        guard=SimpleNamespace(
            thread=get_ident(),
            active=True,
            invalid=False,
            directory_depth=0,
            directory_calls=0,
            directory_targets=(),
            filesystem=[],
            audit_ready=False,
        ),
    )
    with claims._registry(bound.owner_parent):
        if any(stack for stack, _ in _stacks(context)):
            claims._busy(bound.owner_parent, "network_load_conflict")
        for stack, value in _stacks(context):
            stack.append(value)
    try:
        declarations.previous.previous.paths._install_audit(context.guard)
        context.metadata_work.append(("parent_verification", "attempted"))
        if declarations._validate(bound.owner_parent) is not parent:
            raise ValueError("Foreign event parent")
        previous._check(bound)
        context.metadata_work.append(("parent_verification", "completed"))
        context.bindings = _bindings()
        context.before = tuple(vars(context.p))
        context.stable = prefix.graphs.capture(
            dict(vars(context.p)),
            yaml_base=parent.birth.source.yaml,
            runtime_types=parent.parent.runtime_types,
        )
        context.parent_refs = (parent.trial, parent.graph, parent.birth, parent.parent, parent.view)
        context.parent_graph_identity = _digest(parent.graph[1])
        context.bound_identity = bound.binding.identity
        yield context
    except BaseException as error:
        context.source_error = error
        raise
    finally:
        try:
            if not context.retired:
                declarations._validate(bound.owner_parent)
            elif not parent.invalid:
                raise ValueError("Retired declaration parent rearmed")
            if context.invalid or context.guard.invalid:
                raise ValueError("Poisoned network claim")
        except BaseException as error:
            context.capture_errors += (("claim_exit", error),)
        try:
            with claims._registry(bound.owner_parent):
                for stack, value in reversed(_stacks(context)):
                    if not stack or stack[-1] is not value:
                        raise ValueError("Network claim registry changed")
                    stack.pop()
        except BaseException as error:
            context.capture_errors += (("claim_release", error),)
        context.active = context.guard.active = False
        failed = context.source_error is not None or context.invalid or bool(context.capture_errors)
        if failed:
            context.invalid = context.guard.invalid = parent.invalid = True
        if context.source_error is not None:
            try:
                context.source_error.network_load_claim = context
            except BaseException as error:
                context.capture_errors += (("exception_evidence", error),)
        elif failed:
            raise NetworkLoadRejected(
                "Network claim issued no success",
                stage="claim_exit",
                partial=context,
                capture_errors=context.capture_errors,
            ) from context.capture_errors[0][1]


def _stable(context):
    fields = vars(context.p)
    if tuple(fields)[: len(context.before)] != context.before or not set(fields).issubset(
        set(context.before) | set(_FIELDS)
    ):
        raise ValueError("Network branch changed earlier/later parameter field layout")
    return prefix.graphs.capture(
        {name: fields[name] for name in context.before},
        yaml_base=context.parent.birth.source.yaml,
        runtime_types=context.parent.parent.runtime_types,
    )


def _check(context):
    parent = context.parent
    if (
        context.invalid
        or context.guard.invalid
        or context.active is not context.guard.active
        or context.thread != get_ident()
        or not context.guard.audit_ready
        or previous._ISSUED.get(context.boundary_owner) is not context.bound
        or context.bound.parent is not parent
        or context.p is not parent.p
        or parent.invalid is not context.retired
        or any(
            a is not b
            for a, b in zip(
                context.parent_refs,
                (parent.trial, parent.graph, parent.birth, parent.parent, parent.view),
                strict=True,
            )
        )
    ):
        raise ValueError("Actual network/declaration/claim association changed")
    if context.active and any(
        not stack or stack[-1] is not value for stack, value in _stacks(context)
    ):
        raise ValueError("Network activity registry changed")
    if hasattr(context, "request"):
        _request_plan(context)
    prefix.parameters.inherited._same(_bindings(), context.bindings)
    prefix.parameters.inherited._same(declarations._bindings(), parent.bindings)
    previous._check(context.bound)
    if (
        _digest(parent.graph[1]) != context.parent_graph_identity
        or context.bound.binding.identity != context.bound_identity
    ):
        raise ValueError("Retained event/boundary graph changed")
    prefix.parameters.inherited._same_graph(_stable(context), context.stable)
    if hasattr(context, "api"):
        prefix.parameters.inherited._same(_native_bindings(context.api), context.native_bindings)
        if context.parser is not None:
            _parser_receiver(context.api, context.parser)


def _capture(context, origin, error, raw):
    prefix.parameters.inherited.tissue.captures._remember_observation_error(
        context, error, origin=origin, raw=raw
    )


def _entry(context, role, frame):
    if context.observation_error is not None:
        raise context.stop
    _check(context)
    context.counts[role] += 1
    context.events.append(
        dict(
            role=role,
            event="entry",
            classification="attempt_not_success",
            locals=dict(frame.f_locals),
        )
    )
    if context.bound.binding.branch != "expression_file" or context.counts[role] != 1:
        raise ValueError("Unreached or duplicate network helper entry")
    local = frame.f_locals
    file = context.bound.file
    if role == "join":
        if local.get("partnames") != context.bound.binding.join_arguments:
            raise ValueError("Original native join arguments changed")
    elif role == "load":
        if (
            not context.join_verified
            or local.get("filename") != file.filename
            or local.get("yaml_version") is not context.bound.version
        ):
            raise ValueError("Native computed path/file/version association absent")
        prefix._verify_file(file)
    elif role == "reader":
        if (
            context.counts["load"] != 1
            or local.get("filename") != file.filename
            or local.get("encoding") != "utf-8"
        ):
            raise ValueError("Original native read/encoding association changed")
        prefix._verify_file(file)
    elif role == "factory" and (context.counts["reader"] != 1 or context.stream is None):
        raise ValueError("Parser construction did not follow the actual reader")


def _returned(context, role, frame, arg):
    # Forensic observation is separate from verified ownership. Preserve the
    # exact return/unwind witness before copying locals or appending events.
    witness = (role, frame, arg)
    context.raw_return = witness
    context.raw_returns.append(witness)
    context.events.append(
        dict(role=role, event="return_or_unwind", value=arg, locals=dict(frame.f_locals))
    )
    if role == "load":
        # Empty YAML may return None normally. Overall source completion and
        # the separately retained primary error distinguish that from unwind.
        context.decoded, context.decoded_observed = arg, True
    if arg is None:
        return  # CPython also returns(None) while an original exception unwinds.
    if role == "join":
        if type(arg) is not str or arg != context.bound.file.filename:
            raise ValueError("Native computed path differs from issued file permission")
        context.join_verified = True
    elif role == "reader":
        if type(arg) is not io.TextIOWrapper or arg.name != context.bound.file.filename:
            raise ValueError("Actual native text stream required")
        info = os.fstat(arg.fileno())
        observed = (
            info.st_dev,
            info.st_ino,
            info.st_size,
            info.st_mtime_ns,
            info.st_ctime_ns,
            info.st_mode,
        )
        if observed != context.bound.file.stat:
            raise ValueError("Opened native stream file identity differs")
        context.stream, context.stream_stat = arg, observed
    elif role == "factory":
        if type(arg) is not context.api.parser_type:
            raise ValueError("Original actual YAML parser type required")
        _parser_receiver(context.api, arg)
        context.parser = arg


@contextmanager
def _observe(context):
    with prefix.parameters._observe(context):
        prior, trace = sys.getprofile(), sys.gettrace()
        raws = {value.raw.__code__: name for name, value in context.api.roles.items()}
        wrappers = {}
        for name, value in context.api.roles.items():
            for function in value.chain[:-1]:
                wrappers.setdefault(function.__code__, []).append(name)

        def profile(frame, event, arg):
            if event == "call":
                # Native beartype wrappers may expose only args/kwargs. Bind
                # actual argument locals at the original body, before it runs.
                if frame.f_code in wrappers:
                    if context.observation_error is not None:
                        raise context.stop
                    _check(context)
                    if len(context.work) >= MAX_PARSER_CALLS:
                        raise ValueError("Bounded native wrapper work exhausted")
                    context.work.append(
                        dict(
                            sequence=len(context.work),
                            layer="network_helper_wrapper_entry",
                            roles=tuple(wrappers[frame.f_code]),
                            status="entered_not_success_credit",
                        )
                    )
                if frame.f_code in raws:
                    _entry(context, raws[frame.f_code], frame)
                if frame.f_code.co_filename.find("/ruamel/") != -1:
                    context.parser_calls += 1
                    if context.parser_calls > MAX_PARSER_CALLS:
                        raise ValueError("Bounded parser work exhausted")
                    context.work.append(
                        dict(
                            sequence=len(context.work),
                            layer="actual_parser_body",
                            method=frame.f_code.co_qualname,
                            source_file=frame.f_code.co_filename,
                            status="entered_not_success_credit",
                        )
                    )
            elif event == "return" and frame.f_code in raws:
                try:
                    _returned(context, raws[frame.f_code], frame, arg)
                except BaseException as error:
                    _capture(
                        context, "network_return_capture", error, (raws[frame.f_code], frame, arg)
                    )
            if prior is not None:
                prior(frame, event, arg)

        sys.setprofile(profile)
        try:
            yield
        finally:
            sys.setprofile(prior)
            sys.settrace(trace)


def _invoke(context):
    context.work.append(
        dict(
            sequence=len(context.work),
            layer="network_branch_entry",
            status="attempted_not_case_credit",
        )
    )
    with prefix.parameters.inherited.tissue.aliases.issuing_native_imports(
        prefix.parameters.inherited.tissue.source.SOURCE_PINS
    ):
        return context.bound.function(context.p, **{previous.LOCAL_KEY: context.bound.version})


def request_record(value):
    return dict(
        law=LAW_ID, boundary=value.binding_identity, source=value.source_identity, once=True
    )


def _request_plan(context):
    request = context.request
    retained = _REQUESTS.get(request)
    if (
        retained is None
        or request.identity != retained[5]
        or _digest(request_record(request)) != request.identity
        or request.binding_identity != context.bound.binding.identity
    ):
        raise ValueError("Original sealed network request changed")
    context.observed_source_plan = source_plan()
    context.observed_source_identity = _digest(context.observed_source_plan)
    if request.source_identity != context.observed_source_identity:
        raise ValueError("Sealed network source plan differs from current source_plan")


def from_boundary(boundary, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise NetworkLoadRejected("Explicit network-load law required", stage="law")
    with _claim(boundary) as context:
        if any(name in vars(context.p) for name in _FIELDS):
            raise ValueError("Network branch cannot retrofit existing stores")
        request = Request(boundary, context.bound.binding.identity, _digest(source_plan()), "")
        request = replace(request, identity=_digest(request_record(request)))
        _REQUESTS[request] = (
            context.bound,
            context.parent,
            context.parent.trial,
            context.parent.graph,
            context.bound.binding,
            request.identity,
        )
        return request


def _retire(context):
    _check(context)
    with claims._registry(context.bound.owner_parent):
        if (
            context.invalid
            or context.guard.invalid
            or context.parent.invalid
            or declarations._ISSUED.get(context.bound.owner_parent) is not context.parent
        ):
            raise ValueError("Actual declaration parent changed at retirement")
        context.parent.invalid = True
        context.retired = True
        context.metadata_work.append(("declaration_retirement", "completed"))


def _outputs(context):
    fields = vars(context.p)
    branch = context.bound.binding.branch
    expected = (
        ("mol_mit_enabled",)
        if branch == "no_network"
        else _FIELDS[:3]
        if branch == "no_expression_file"
        else _FIELDS
    )
    if tuple(fields)[len(context.before) :] != expected or context.p.mol_mit_enabled is not False:
        raise ValueError("Original network branch stores/order incomplete")
    if branch != "no_network":
        config = context.p.network_config
        if context.p.molecules_enabled is not config[
            "implement network"
        ] or context.p.expression_data_path_rel is not config.get("expression data file", None):
            raise ValueError("Original network declaration aliases changed")
    if branch == "expression_file":
        if (
            not context.join_verified
            or any(context.counts[k] != 1 for k in context.counts)
            or context.parser is None
            or context.stream is None
            or not context.decoded_observed
            or context.p.expression_data is not context.decoded
            or context.p.expression_data_path != context.bound.file.filename
        ):
            raise ValueError("Actual native join/read/parser/decoded ownership incomplete")
        prefix._verify_file(context.bound.file)
    elif any(context.counts.values()) or context.decoded_observed:
        raise ValueError("Unreached file/parser activity in no-file branch")


def trial_record(value):
    return dict(
        law=LAW_ID,
        request=value.request_identity,
        parent=value.parent_trial_identity,
        file=value.file_identity,
        cache=value.cache.identity,
        source_work=value.source_work,
        metadata_work=value.metadata_work,
        observations=value.observations,
        parsed=value.parsed,
        GRN_full_Parameters_phase_INIT_admitted=False,
    )


class NetworkLoadOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use the original once-only network branch")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live network loads cannot be serialized")

    @property
    def parameters(self):
        return _validate(self).p

    @property
    def trial(self):
        return _validate(self).trial


def _validate(owner):
    if type(owner) is not NetworkLoadOwner or owner not in _ISSUED:
        raise NetworkLoadRejected("Issued network-load owner required", stage="owner")
    context = _ISSUED[owner]
    try:
        if context.active or context.owner is not owner:
            raise ValueError("Active/replaced network owner")
        _check(context)
        _outputs(context)
        prefix.parameters.inherited._same_graph(prefix._capture(context.view), context.graph)
        prefix.parameters.inherited.tissue.core.caches.validate(context.trial.cache)
        if (
            _digest(trial_record(context.trial)) != context.trial.identity
            or prefix.parameters.inherited.tissue.core.caches.snapshot(context.graph[1]).identity
            != context.trial.cache.identity
        ):
            raise ValueError("Network graph/cache/trial changed")
        kinds, files, namespaces = prefix._runtime_types(context.view)
        if (
            kinds != context.parent.parent.runtime_types
            or files != context.parent.parent.runtime_files
        ):
            raise ValueError("Original parser/runtime inventory changed")
        prefix.parameters.inherited._same(namespaces, context.parent.parent.runtime_namespaces)
    except BaseException as error:
        context.invalid = True
        raise NetworkLoadRejected(
            "Stale network-load owner refused",
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
        or os.environ.get(declarations.RELEASE) != "1"
    ):
        raise NetworkLoadRejected(
            "Actual native network join/parser work remains held", stage="release", request=request
        )
    if _ACTIVE:
        _ACTIVE[-1].invalid = True
        raise NetworkLoadRejected(
            "Reentrant network load refused", stage="reentrant", request=request
        )
    if (
        type(request) is not Request
        or request not in _REQUESTS
        or _digest(request_record(request)) != request.identity
    ):
        raise NetworkLoadRejected(
            "Issued exact network-load request required", stage="request", request=request
        )
    if request in _CONSUMED or request.boundary in _CLAIMED:
        raise NetworkLoadRejected(
            "Network branch attempt consumed", stage="consumed", request=request
        )
    with _claim(request.boundary) as context:
        context.request = request
        _CONSUMED[request] = _CLAIMED[request.boundary] = context
        error = None
        try:
            old = _REQUESTS[request]
            if any(
                a is not b
                for a, b in zip(
                    (
                        context.bound,
                        context.parent,
                        context.parent.trial,
                        context.parent.graph,
                        context.bound.binding,
                    ),
                    old[:5],
                    strict=True,
                )
            ):
                raise ValueError("Original requested boundary/parent changed")
            context.stage = "source_plan"
            _request_plan(context)
            context.stage = "native_helper_binding"
            context.api = _native(context.bound)
            context.native_bindings = _native_bindings(context.api)
            _retire(context)
            context.stage = "native_network_branch"
            with _observe(context):
                _invoke(context)
            context.source_completed = True
            if context.observation_error is not None:
                raise context.stop
            _check(context)
            _outputs(context)
            context.stage = "network_graph_capture"
            context.view = SimpleNamespace(
                p=context.p,
                parent=context.parent.birth,
                file_record=context.parent.parent.file_record,
                runtime_types=context.parent.parent.runtime_types,
            )
            kinds, files, namespaces = prefix._runtime_types(context.view)
            if (
                kinds != context.parent.parent.runtime_types
                or files != context.parent.parent.runtime_files
            ):
                raise ValueError("Native parse introduced an unowned runtime")
            prefix.parameters.inherited._same(namespaces, context.parent.parent.runtime_namespaces)
            context.graph = prefix._capture(context.view)
            cache = prefix.parameters.inherited.tissue.core.caches.snapshot(context.graph[1])
            summaries = tuple(
                (e["role"], e["event"], e.get("classification", "observed_not_independent_case"))
                for e in context.events
            )
            trial = Trial(
                request.identity,
                context.parent.trial.identity,
                context.bound.binding.file_identity,
                cache,
                tuple(context.work),
                tuple(context.metadata_work),
                summaries,
                context.bound.binding.branch == "expression_file",
                "",
            )
            context.trial = replace(trial, identity=_digest(trial_record(trial)))
            _check(context)
            owner = object.__new__(NetworkLoadOwner)
            context.owner = owner
            _ISSUED[owner] = context
            return owner
        except BaseException as primary:
            if primary is context.stop:
                pass
            elif context.stage == "network_graph_capture":
                _capture(context, context.stage, primary, context)
            else:
                error = primary
        context.invalid = True
        raise NetworkLoadRejected(
            "Original network branch issued no child",
            stage=context.stage,
            request=request,
            partial=context,
            source_error=error,
            capture_errors=context.observation_errors,
        ) from (error if error is not None else context.observation_error)


def require_grn(owner):
    context = _validate(owner)
    raise NetworkLoadRejected(
        "Actual GRN/file continuation remains unavailable",
        stage="GRN_authority",
        partial=dict(next_source_line=802, parsed=context.trial.parsed, phase_INIT_admitted=False),
        trial=context.trial,
    )


def _bindings():
    functions = (
        _digest,
        source_plan,
        _born_parser,
        _native,
        _parser_bindings,
        _parser_receiver,
        _native_bindings,
        _stacks,
        _claim,
        _claim.__wrapped__,
        _stable,
        _check,
        _capture,
        _entry,
        _returned,
        _observe,
        _observe.__wrapped__,
        _invoke,
        request_record,
        _request_plan,
        from_boundary,
        _retire,
        _outputs,
        trial_record,
        _validate,
        prepare,
        require_grn,
        _bindings,
    )
    return (
        (),
        (
            LAW_ID,
            PREVIOUS_SHA256,
            RELEASE,
            MAX_PARSER_CALLS,
            _OPEN,
            _FIELDS,
            _REQUESTS,
            _CONSUMED,
            _CLAIMED,
            _ISSUED,
            _ACTIVE,
            *claims._bindings()[1],
            *(
                atom
                for fn in functions
                for atom in prefix.parameters.inherited.tissue.aliases._atoms(fn)
            ),
        ),
    )
