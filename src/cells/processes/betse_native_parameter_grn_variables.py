"""Original same-p GRN/file and variable declarations, before modulators.

Compile Parameters.load[62:109] unchanged apart from explicit transport of the
retained original YAML_VERSION. Native/parser/float work needs both releases.
No parsed dictionary, replacement GRN, constructor lease or phase is supplied.
"""

import ast
import copy
import hashlib
import io
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import get_ident
from types import FunctionType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_parameter_network_load as previous

LAW_ID = "betse_native_parameter_grn_variables@1"
PREVIOUS_SHA256 = "b08c58bb8de51cec7ea7f24dffdfa0e628f2a8bb36d0bc0a9e9f0cba27853b9e"
RELEASE = "CELLS_NATIVE_PARAMETER_GRN_VARIABLES_RELEASED"
START, STOP = 62, 109
_FLOAT = float
prefix, claims, declarations = previous.prefix, previous.claims, previous.declarations
subconfigs = declarations.previous.previous
_REQUESTS, _CONSUMED, _CLAIMED, _ISSUED = (WeakKeyDictionary() for _ in range(4))
_ACTIVE = []


class GrnVariablesRejected(ValueError):
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
    parent: previous.NetworkLoadOwner
    grn_file: prefix.FileInput | None
    parent_trial_identity: str
    source_identity: str
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("Live GRN/variable requests cannot be serialized")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    parent_trial_identity: str
    file_identity: str | None
    cache: object
    source_work: tuple
    metadata_work: tuple
    observations: tuple
    grn_loaded: bool
    source_completed: bool
    identity: str


def _digest(value):
    return previous._digest(value)


def _ast():
    path, cls, load, _ = previous.previous._ast()
    selected = load.body[START:STOP]
    if (
        ast.unparse(selected[0])
        != (
            "self.grn_enabled = self._conf['gene regulatory network settings']"
            "['gene regulatory network simulated']"
        )
        or ast.unparse(selected[1].test) != "self.grn_enabled"
        or ast.unparse(selected[-1])
        != (
            "self.dynamic_noise_level = float(self._conf['variable settings']"
            "['noise']['dynamic noise level'])"
        )
        or ast.unparse(load.body[STOP]) != "self.gradient_x_properties = {}"
    ):
        raise ValueError("Original GRN/variable/modulator boundary changed")
    return path, cls, load, selected


def source_plan():
    if hashlib.sha256(Path(previous.__file__).read_bytes()).hexdigest() != PREVIOUS_SHA256:
        raise ValueError("Exact completed network-load producer required")
    parent = previous.source_plan()
    path, cls, load, selected = _ast()
    stores = tuple(
        dict.fromkeys(
            n.targets[0].attr
            for statement in selected
            for n in ast.walk(statement)
            if isinstance(n, ast.Assign)
            and isinstance(n.targets[0], ast.Attribute)
            and isinstance(n.targets[0].value, ast.Name)
            and n.targets[0].value.id == "self"
        )
    )
    return dict(
        law=LAW_ID,
        predecessor=PREVIOUS_SHA256,
        native_pins=parent["original"]["native_pins"],
        statement_slice=(START, STOP),
        source_lines=(selected[0].lineno, selected[-1].end_lineno),
        source_body_ast=_digest(ast.dump(ast.Module(body=selected, type_ignores=[]))),
        local_transport=f"YAML_VERSION = kwargs[{previous.previous.LOCAL_KEY!r}]",
        stores=stores,
        next_source_line=load.body[STOP].lineno,
        enabled_flag_domain="actual parsed exact bool; no truth-value coercion or supplied flag",
        constructor_handoff_full_Parameters_phase_INIT_admitted=False,
    )


def _authority(parent):
    """The eighth original object, never a reconstructed seven-load parent."""
    event = parent.parent
    numeric, birth = event.parent, event.birth
    loaded = numeric.parent
    path = loaded.parent
    grn = vars(parent.p)["grn"]
    cls = loaded.authority.classes["SimConfGrnFile"]
    module = sys.modules.get("betse.science.config.grn.confgrn")
    native = prefix.parameters.inherited.tissue.aliases.NATIVE
    frame = birth.locals.get((str(native / prefix.parameters.PARAMETERS), "Parameters.__init__"))
    if (
        type(grn) is not cls
        or loaded.authority.objects["grn"] is not grn
        or module is None
        or getattr(module, "SimConfGrnFile", None) is not cls
        or Path(module.__file__).resolve() != native / "betse/science/config/grn/confgrn.py"
        or type(frame) is not dict
        or frame.get("self") is not parent.p
        or frame.get("SimConfGrnFile") is not cls
        or frame.get("__class__") is not birth.source.cls
        or not birth.source_completed
        or not birth.trial.source_completed
        or not any(value is grn for value in birth.graph[0])
        or path.p is not parent.p
        or path.yaml is not parent.bound.yaml
    ):
        raise ValueError("Actual same-p original GRN constructor/path/read authority absent")
    return SimpleNamespace(grn=grn, cls=cls, loaded=loaded, path=path, birth=birth)


def _permission(parent, authority, grn_file):
    flag = vars(parent.p)["_conf"]["gene regulatory network settings"][
        "gene regulatory network simulated"
    ]
    if type(flag) is not bool:
        raise GrnVariablesRejected(
            "Unsupported original GRN truth-value authority", stage="flag_authority"
        )
    if vars(authority.grn).get("_conf", "absent") is not None:
        raise GrnVariablesRejected(
            "Retained GRN must still be genuinely unloaded", stage="GRN_owner"
        )
    if flag:
        if grn_file is None:
            raise GrnVariablesRejected(
                "Issued immutable GRN file required for enabled branch", stage="file_authority"
            )
        prefix._verify_file(grn_file)
        filename = vars(parent.p).get("grn_config_filename")
        if type(filename) is not str or filename != grn_file.filename:
            raise GrnVariablesRejected(
                "Computed original GRN filename differs from file permission",
                stage="file_association",
            )
        if (
            authority.path.trial.paths_completed is not True
            or dict(authority.path.request.policy.paths).get("grn_config_filename") != filename
        ):
            raise GrnVariablesRejected(
                "Original path trial does not own this GRN filename", stage="file_association"
            )
    elif grn_file is not None:
        raise GrnVariablesRejected("Unreached GRN file permission refused", stage="file_route")
    return flag


def _compile(context):
    original = context.parent.bound.original
    prefix._function_bindings(original)
    if "float" in original.__globals__ or original.__builtins__.get("float") is not _FLOAT:
        raise ValueError("Original float resolution changed")
    path, cls, load, selected = _ast()
    cls = copy.deepcopy(cls)
    transport = ast.parse(f"YAML_VERSION = kwargs[{previous.previous.LOCAL_KEY!r}]").body[0]
    prefix.parameters.inherited._method(cls, "load").body = [transport, *copy.deepcopy(selected)]
    code = prefix.parameters._method_code(cls, "load", str(path))
    if code.co_freevars:
        raise ValueError("Unexpected GRN/variable closure dependency")
    function = FunctionType(code, original.__globals__, original.__name__, None, None)
    if function.__builtins__ is not original.__builtins__:
        raise ValueError("GRN/variable cached builtins changed")
    return function


def _native(context):
    native = prefix.parameters.inherited.tissue.aliases.NATIVE
    yaml_file = sys.modules.get("betse.lib.yaml.abc.yamlfileabc")
    yaml_base = sys.modules.get("betse.lib.yaml.abc.yamlabc")
    if (
        yaml_file is None
        or yaml_base is None
        or context.authority.cls.__bases__ != (yaml_file.YamlFileABC,)
        or context.birth.source.yaml is not yaml_base.YamlABC
    ):
        raise ValueError("Original GRN/YAML file/base lineage absent")
    roles = {}
    for role, cls, name in (
        ("grn_load", context.authority.cls, "load"),
        ("file_load", yaml_file.YamlFileABC, "load"),
        ("attach", yaml_base.YamlABC, "load"),
        ("filename", yaml_file.YamlFileABC, "_set_conf_filename"),
    ):
        function = vars(cls)[name]
        chain = prefix.parameters.inherited._chain(function)
        raw = chain[-1]
        module = sys.modules.get(raw.__module__)
        filename = Path(raw.__code__.co_filename).resolve()
        if (
            not filename.is_relative_to(native)
            or module is None
            or raw.__globals__ is not vars(module)
        ):
            raise ValueError("Foreign native GRN method globals/source")
        tree = ast.parse(filename.read_bytes())
        node = prefix.parameters.inherited._class(tree, cls.__name__)
        expected = prefix.parameters._method_code(node, name, str(filename))
        if prefix.parameters.inherited._code(raw.__code__) != prefix.parameters.inherited._code(
            expected
        ):
            raise ValueError("Original GRN method header/body changed")
        for name_free, cell in zip(raw.__code__.co_freevars, raw.__closure__ or (), strict=True):
            if name_free == "__class__" and cell.cell_contents is not cls:
                raise ValueError("Original GRN super/class closure changed")
        roles[role] = SimpleNamespace(function=function, raw=raw, chain=chain, cls=cls, name=name)
    return roles


def _native_bindings(context):
    labels, refs = [], [context.authority.grn, context.authority.cls]
    base = previous._native_bindings(context.parent.api)
    labels.append(base[0])
    refs.extend(base[1])
    for role, value in context.methods.items():
        if vars(value.cls).get(value.name) is not value.function:
            raise ValueError("Native GRN method dispatch changed")
        chain = prefix.parameters.inherited._chain(value.function)
        if len(chain) != len(value.chain) or any(
            a is not b for a, b in zip(chain, value.chain, strict=True)
        ):
            raise ValueError("Native GRN wrapper chain changed")
        for function in chain:
            binding = prefix._function_bindings(function)
            labels.append((role, binding[0]))
            refs.extend(binding[1])
        refs.extend(prefix.parameters.inherited.tissue._surface(value.cls))
    return tuple(labels), tuple(refs)


def _stacks(context):
    return (
        (_ACTIVE, context),
        (previous._ACTIVE, context),
        (previous.previous._ACTIVE, context),
        (declarations._ACTIVE, context),
        (declarations.previous._ACTIVE, context),
        (claims._ACTIVE, context),
        (subconfigs._ACTIVE, context),
        (subconfigs.paths._ACTIVE, context.guard),
    )


def _stable(context):
    fields = vars(context.p)
    if (
        tuple(fields)[: len(context.before)] != context.before
        or not set(fields).issubset(set(context.before) | set(context.plan["stores"]))
        or fields.get("grn") is not context.authority.grn
    ):
        raise ValueError("Earlier/later parameter field order or GRN owner changed")
    return prefix.graphs.capture(
        {name: fields[name] for name in context.before if name != "grn"},
        yaml_base=context.birth.source.yaml,
        runtime_types=context.runtime.runtime_types,
    )


def _grn_graph(context):
    return prefix.graphs.capture(
        dict(grn=context.authority.grn),
        yaml_base=context.birth.source.yaml,
        runtime_types=context.runtime.runtime_types,
    )


def _ancestry(context):
    current = _authority(context.parent)
    refs = tuple(getattr(current, name) for name in ("grn", "cls", "loaded", "path", "birth"))
    path = current.path
    subconfigs.paths._policy(path.request.policy)
    if (
        type(path.trial) is not subconfigs.paths.Trial
        or path.trial.paths_completed is not True
        or path.trial.upgrade_completed is not True
        or _digest(subconfigs.paths.trial_record(path.trial)) != path.trial.identity
    ):
        raise ValueError("Actual completed original path trial required")
    prefix.parameters.inherited.tissue.core.caches.validate(path.trial.cache)
    return (
        (path.trial.identity, _digest(path.graph[1]), _digest(current.birth.graph[1])),
        (
            *refs,
            path.request,
            path.request.policy,
            path.trial,
            path.graph,
            current.birth.trial,
            current.birth.graph,
        ),
    )


@contextmanager
def _claim(owner):
    if type(owner) is not previous.NetworkLoadOwner or owner not in previous._ISSUED:
        previous._validate(owner)
        raise AssertionError("Unissued network validator returned")
    parent = previous._ISSUED[owner]
    context = SimpleNamespace(
        parent_owner=owner,
        parent=parent,
        p=parent.p,
        birth=parent.parent.birth,
        runtime=parent.parent.parent,
        active=True,
        retired=False,
        invalid=False,
        thread=get_ident(),
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
        stream=None,
        parser=None,
        counts={
            role: 0
            for role in ("grn_load", "file_load", "load", "reader", "factory", "attach", "filename")
        },
        completed=set(),
        parser_calls=0,
        stop=_ObserverStop("GRN observer stopped before source entry"),
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
    with claims._registry(owner):
        if any(stack for stack, _ in _stacks(context)):
            claims._busy(owner, "grn_variables_conflict")
        for stack, value in _stacks(context):
            stack.append(value)
    try:
        subconfigs.paths._install_audit(context.guard)
        context.metadata_work.append(("network_parent_verification", "attempted"))
        if previous._validate(owner) is not parent:
            raise ValueError("Foreign network owner")
        context.metadata_work.append(("network_parent_verification", "completed"))
        context.plan = source_plan()
        context.authority = _authority(parent)
        context.ancestry = _ancestry(context)
        context.before = tuple(vars(context.p))
        if set(context.before) & set(context.plan["stores"]):
            raise ValueError("GRN/variable stores cannot retrofit an earlier owner")
        context.stable = _stable(context)
        context.grn_before = _grn_graph(context)
        context.refs = (
            parent.p,
            parent.bound,
            parent.trial,
            parent.graph,
            parent.parent,
            parent.api,
        )
        context.parent_trial_identity = parent.trial.identity
        context.parent_graph_identity = _digest(parent.graph[1])
        context.bindings = _bindings()
        yield context
    except BaseException as error:
        context.source_error = error
        raise
    finally:
        try:
            if not context.retired:
                previous._validate(owner)
            elif not parent.invalid:
                raise ValueError("Retired network parent rearmed")
            if context.invalid or context.guard.invalid:
                raise ValueError("Poisoned GRN/variable claim")
        except BaseException as error:
            context.capture_errors += (("claim_exit", error),)
        try:
            with claims._registry(owner):
                for stack, value in reversed(_stacks(context)):
                    if not stack or stack[-1] is not value:
                        raise ValueError("GRN activity registry changed")
                    stack.pop()
        except BaseException as error:
            context.capture_errors += (("claim_release", error),)
        context.active = context.guard.active = False
        failed = context.source_error is not None or context.invalid or bool(context.capture_errors)
        if failed:
            context.invalid = context.guard.invalid = parent.invalid = True
        if context.source_error is not None:
            try:
                context.source_error.grn_variables_claim = context
            except BaseException as error:
                context.capture_errors += (("exception_evidence", error),)
        elif failed:
            raise GrnVariablesRejected(
                "GRN claim issued no child",
                stage="claim_exit",
                partial=context,
                capture_errors=context.capture_errors,
            ) from context.capture_errors[0][1]


def request_record(value):
    return dict(
        law=LAW_ID,
        parent=value.parent_trial_identity,
        file=None if value.grn_file is None else value.grn_file.identity,
        source=value.source_identity,
        once=True,
    )


def from_network(owner, *, law_id, grn_file=None):
    if type(law_id) is not str or law_id != LAW_ID:
        raise GrnVariablesRejected("Explicit GRN/variable law required", stage="law")
    with _claim(owner) as context:
        flag = _permission(context.parent, context.authority, grn_file)
        value = Request(owner, grn_file, context.parent.trial.identity, _digest(context.plan), "")
        value = replace(value, identity=_digest(request_record(value)))
        _REQUESTS[value] = (context.refs, context.authority.grn, flag, value.identity)
        return value


def _check(context):
    parent = context.parent
    if (
        context.invalid
        or context.guard.invalid
        or context.thread != get_ident()
        or context.active is not context.guard.active
        or not context.guard.audit_ready
        or previous._ISSUED.get(context.parent_owner) is not parent
        or parent.invalid is not context.retired
        or any(
            a is not b
            for a, b in zip(
                context.refs,
                (parent.p, parent.bound, parent.trial, parent.graph, parent.parent, parent.api),
                strict=True,
            )
        )
        or parent.trial.identity != context.parent_trial_identity
        or _digest(parent.graph[1]) != context.parent_graph_identity
    ):
        raise ValueError("Original network/GRN/retirement association changed")
    if context.active and any(
        not stack or stack[-1] is not value for stack, value in _stacks(context)
    ):
        raise ValueError("GRN activity registry changed")
    prefix.parameters.inherited._same(_bindings(), context.bindings)
    prefix.parameters.inherited._same(previous._bindings(), parent.bindings)
    previous.previous._check(parent.bound)
    prefix.parameters.inherited._same(_ancestry(context), context.ancestry)
    prefix.parameters.inherited._same_graph(_stable(context), context.stable)
    if not context.retired or not getattr(context, "enabled", False):
        prefix.parameters.inherited._same_graph(_grn_graph(context), context.grn_before)
    if hasattr(context, "function"):
        prefix.parameters.inherited._same(
            prefix._function_bindings(context.function), context.function_bindings
        )
        prefix.parameters.inherited._same(_native_bindings(context), context.native_bindings)
        if context.parser is not None:
            previous._parser_receiver(context.parent.api, context.parser)
        if (
            context.request.identity != _REQUESTS[context.request][3]
            or _digest(request_record(context.request)) != context.request.identity
        ):
            raise ValueError("Issued GRN request record changed")


def _capture(context, origin, error, raw):
    prefix.parameters.inherited.tissue.captures._remember_observation_error(
        context, error, origin=origin, raw=raw
    )


def _entry(context, role, frame):
    if context.observation_error is not None:
        raise context.stop
    _check(context)
    context.counts[role] += 1
    local = frame.f_locals
    context.events.append(
        dict(role=role, event="entry", locals=dict(local), classification="attempt_not_success")
    )
    if not context.enabled or context.counts[role] != 1:
        raise ValueError("Unreached/duplicate GRN source entry")
    filename, version = context.request.grn_file.filename, context.parent.bound.version
    prerequisites = dict(
        file_load="grn_load",
        load="file_load",
        reader="load",
        factory="reader",
        attach="load",
        filename="attach",
    )
    if role in prerequisites and context.counts[prerequisites[role]] != 1:
        raise ValueError("Original GRN/file/parser source order changed")
    if (
        role in {"grn_load", "file_load", "attach", "filename"}
        and local.get("self") is not context.authority.grn
    ):
        raise ValueError("Foreign GRN receiver")
    if role == "grn_load":
        if (
            local.get("args") != ()
            or type(local.get("kwargs")) is not dict
            or tuple(local["kwargs"]) != ("conf_filename", "yaml_version")
            or local["kwargs"]["conf_filename"] != filename
            or local["kwargs"]["yaml_version"] is not version
        ):
            raise ValueError("Original GRN call/filename/version changed")
    elif role == "file_load":
        if (
            local.get("conf_filename") != filename
            or type(local.get("kwargs")) is not dict
            or tuple(local["kwargs"]) != ("yaml_version",)
            or local["kwargs"]["yaml_version"] is not version
        ):
            raise ValueError("Original YAML file load arguments changed")
    elif role == "load":
        if local.get("filename") != filename or local.get("yaml_version") is not version:
            raise ValueError("Original GRN parser filename/version changed")
    elif role == "reader":
        if local.get("filename") != filename or local.get("encoding") != "utf-8":
            raise ValueError("Original GRN reader arguments changed")
    elif role == "factory":
        if context.stream is None:
            raise ValueError("Missing actual GRN opened stream")
    elif role == "attach":
        if (
            "load" not in context.completed
            or not context.decoded_observed
            or local.get("conf") is not context.decoded
        ):
            raise ValueError("GRN attach does not own actual decoded return")
    elif role == "filename":
        if "attach" not in context.completed or local.get("conf_filename") != filename:
            raise ValueError("GRN filename publication preceded attachment")
    prefix._verify_file(context.request.grn_file)


def _returned(context, role, frame, arg):
    # Preserve forensic identity before fallible observation. This witness
    # alone never supplies decoded, stream, parser or completed-call authority.
    witness = (role, frame, arg)
    context.raw_return = witness
    context.raw_returns.append(witness)
    context.events.append(
        dict(role=role, event="return_or_unwind", value=arg, locals=dict(frame.f_locals))
    )
    context.completed.add(role)  # A possible unwind; whole source completion is still required.
    if role == "load":
        context.decoded, context.decoded_observed = arg, True
    if arg is None:
        return
    if role == "reader":
        if type(arg) is not io.TextIOWrapper or arg.name != context.request.grn_file.filename:
            raise ValueError("Original actual GRN stream required")
        info = os.fstat(arg.fileno())
        observed = (
            info.st_dev,
            info.st_ino,
            info.st_size,
            info.st_mtime_ns,
            info.st_ctime_ns,
            info.st_mode,
        )
        if observed != context.request.grn_file.stat:
            raise ValueError("Opened GRN file identity changed")
        context.stream = arg
    elif role == "factory":
        if type(arg) is not context.parent.api.parser_type:
            raise ValueError("Original actual parser factory required")
        previous._parser_receiver(context.parent.api, arg)
        context.parser = arg


@contextmanager
def _observe(context):
    with prefix.parameters._observe(context):
        prior, trace = sys.getprofile(), sys.gettrace()
        roles = {
            **context.methods,
            **{name: context.parent.api.roles[name] for name in ("load", "reader", "factory")},
        }
        raws = {value.raw.__code__: name for name, value in roles.items()}
        wrappers = {}
        for name, value in roles.items():
            for fn in value.chain[:-1]:
                wrappers.setdefault(fn.__code__, []).append(name)

        def profile(frame, event, arg):
            if event == "call":
                if frame.f_code in wrappers:
                    if context.observation_error is not None:
                        raise context.stop
                    _check(context)
                    if len(context.work) >= previous.MAX_PARSER_CALLS:
                        raise ValueError("Bounded GRN wrapper work exhausted")
                    context.work.append(
                        dict(
                            sequence=len(context.work),
                            layer="GRN_wrapper_entry",
                            roles=tuple(wrappers[frame.f_code]),
                            status="attempt_not_case",
                        )
                    )
                if frame.f_code in raws:
                    _entry(context, raws[frame.f_code], frame)
                if "/ruamel/" in frame.f_code.co_filename:
                    context.parser_calls += 1
                    if context.parser_calls > previous.MAX_PARSER_CALLS:
                        raise ValueError("Bounded GRN parser work exhausted")
                    context.work.append(
                        dict(
                            sequence=len(context.work),
                            layer="actual_parser_body",
                            method=frame.f_code.co_qualname,
                            status="entered_not_case_credit",
                        )
                    )
            elif event == "return" and frame.f_code in raws:
                try:
                    _returned(context, raws[frame.f_code], frame, arg)
                except BaseException as error:
                    _capture(context, "GRN_return_capture", error, (raws[frame.f_code], frame, arg))
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
            layer="GRN_variable_branch",
            status="attempt_not_case_credit",
        )
    )
    with prefix.parameters.inherited.tissue.aliases.issuing_native_imports(
        prefix.parameters.inherited.tissue.source.SOURCE_PINS
    ):
        return context.function(
            context.p, **{previous.previous.LOCAL_KEY: context.parent.bound.version}
        )


def _outputs(context):
    fields = vars(context.p)
    if tuple(fields)[len(context.before) :] != context.plan["stores"]:
        raise ValueError("Original GRN/variable store order incomplete")
    cfg = fields["_conf"]
    if (
        fields["grn_enabled"]
        is not cfg["gene regulatory network settings"]["gene regulatory network simulated"]
    ):
        raise ValueError("Original GRN flag alias changed")
    if (
        tuple(fields["Dtj_rel"]) != ("Na", "K", "Cl", "Ca", "M", "P")
        or fields["cbnd"] is not cfg["variable settings"]["env boundary concentrations"]
    ):
        raise ValueError("Original environment/ion order or alias changed")
    if context.enabled:
        grn = vars(context.authority.grn)
        if (
            any(value != 1 for value in context.counts.values())
            or set(context.counts) != context.completed
            or not context.decoded_observed
            or context.decoded is None
            or context.parser is None
            or context.stream is None
            or grn.get("_conf") is not context.decoded
            or grn.get("_conf_filename") != context.request.grn_file.filename
            or grn.get("_conf_dirname") != str(Path(context.request.grn_file.filename).parent)
            or grn.get("_conf_basename") != Path(context.request.grn_file.filename).name
        ):
            raise ValueError("Actual GRN read/attach/file publication incomplete")
        prefix._verify_file(context.request.grn_file)
    elif any(context.counts.values()) or context.decoded_observed:
        raise ValueError("Disabled GRN branch performed file work")


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
        grn_loaded=value.grn_loaded,
        source_completed=value.source_completed,
        full_Parameters_constructor_handoff_phase_INIT_admitted=False,
    )


class GrnVariablesOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use once-only original GRN/variable continuation")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live GRN/variable owners cannot be serialized")

    @property
    def parameters(self):
        return _validate(self).p

    @property
    def trial(self):
        return _validate(self).trial


def _validate(owner):
    if type(owner) is not GrnVariablesOwner or owner not in _ISSUED:
        raise GrnVariablesRejected("Actual issued GRN/variable owner required", stage="owner")
    context = _ISSUED[owner]
    try:
        if context.active or context.owner is not owner:
            raise ValueError("Active/replaced GRN/variable owner")
        _check(context)
        _outputs(context)
        prefix.parameters.inherited._same_graph(prefix._capture(context.view), context.graph)
        prefix.parameters.inherited.tissue.core.caches.validate(context.trial.cache)
        if (
            _digest(trial_record(context.trial)) != context.trial.identity
            or prefix.parameters.inherited.tissue.core.caches.snapshot(context.graph[1]).identity
            != context.trial.cache.identity
        ):
            raise ValueError("GRN/variable cache/trial changed")
        kinds, files, namespaces = prefix._runtime_types(context.view)
        if kinds != context.runtime.runtime_types or files != context.runtime.runtime_files:
            raise ValueError("GRN runtime inventory changed")
        prefix.parameters.inherited._same(namespaces, context.runtime.runtime_namespaces)
    except BaseException as error:
        context.invalid = True
        raise GrnVariablesRejected(
            "Stale GRN/variable owner",
            stage="owner_drift",
            partial=context,
            trial=context.trial,
            source_error=error,
        ) from error
    return context


def prepare(request, *, enabled=False):
    if (
        enabled is not True
        or os.environ.get(RELEASE) != "1"
        or os.environ.get(previous.RELEASE) != "1"
    ):
        raise GrnVariablesRejected(
            "Actual GRN/parser/variable source remains held", stage="release", request=request
        )
    if _ACTIVE:
        _ACTIVE[-1].invalid = True
        raise GrnVariablesRejected(
            "Reentrant GRN/variable work refused", stage="reentrant", request=request
        )
    if (
        type(request) is not Request
        or request not in _REQUESTS
        or _digest(request_record(request)) != request.identity
    ):
        raise GrnVariablesRejected(
            "Issued GRN/variable request required", stage="request", request=request
        )
    if request in _CONSUMED or request.parent in _CLAIMED:
        raise GrnVariablesRejected(
            "GRN/variable attempt consumed", stage="consumed", request=request
        )
    with _claim(request.parent) as context:
        context.request = request
        _CONSUMED[request] = _CLAIMED[request.parent] = context
        primary = None
        try:
            old = _REQUESTS[request]
            if (
                any(a is not b for a, b in zip(context.refs, old[0], strict=True))
                or context.authority.grn is not old[1]
                or request.identity != old[3]
                or request.parent_trial_identity != context.parent_trial_identity
                or request.source_identity != _digest(context.plan)
            ):
                raise ValueError("Actual requested GRN/source/parent association changed")
            context.enabled = _permission(context.parent, context.authority, request.grn_file)
            if context.enabled is not old[2]:
                raise ValueError("Original GRN branch changed")
            context.stage = "source_binding"
            context.function = _compile(context)
            context.function_bindings = prefix._function_bindings(context.function)
            context.methods = _native(context)
            context.native_bindings = _native_bindings(context)
            _check(context)
            with claims._registry(context.parent_owner):
                if (
                    context.parent.invalid
                    or previous._ISSUED.get(context.parent_owner) is not context.parent
                ):
                    raise ValueError("Network parent changed at retirement")
                context.parent.invalid = context.retired = True
                context.metadata_work.append(("network_parent_retirement", "completed"))
            context.stage = "native_GRN_variables"
            with _observe(context):
                _invoke(context)
            context.source_completed = True
            if context.observation_error is not None:
                raise context.stop
            _check(context)
            _outputs(context)
            context.stage = "graph_capture"
            context.view = SimpleNamespace(
                p=context.p,
                parent=context.birth,
                file_record=context.runtime.file_record,
                runtime_types=context.runtime.runtime_types,
            )
            kinds, files, namespaces = prefix._runtime_types(context.view)
            if kinds != context.runtime.runtime_types or files != context.runtime.runtime_files:
                raise ValueError("Unowned runtime introduced by GRN loading")
            prefix.parameters.inherited._same(namespaces, context.runtime.runtime_namespaces)
            context.graph = prefix._capture(context.view)
            cache = prefix.parameters.inherited.tissue.core.caches.snapshot(context.graph[1])
            value = Trial(
                request.identity,
                context.parent_trial_identity,
                None if request.grn_file is None else request.grn_file.identity,
                cache,
                tuple(context.work),
                tuple(context.metadata_work),
                tuple((e["role"], e["event"]) for e in context.events),
                context.enabled,
                True,
                "",
            )
            context.trial = replace(value, identity=_digest(trial_record(value)))
            _check(context)
            owner = object.__new__(GrnVariablesOwner)
            context.owner = owner
            _ISSUED[owner] = context
            return owner
        except BaseException as error:
            if error is context.stop:
                pass
            elif context.stage == "graph_capture":
                _capture(context, context.stage, error, context)
            else:
                primary = error
        context.invalid = True
        raise GrnVariablesRejected(
            "Original GRN/variables issued no child",
            stage=context.stage,
            request=request,
            partial=context,
            source_error=primary,
            capture_errors=context.observation_errors,
        ) from (primary if primary is not None else context.observation_error)


def require_continuation(owner):
    context = _validate(owner)
    raise GrnVariablesRejected(
        "Modulators/full Parameters/public constructor handoff remain unavailable",
        stage="next_prerequisite",
        trial=context.trial,
        partial=dict(
            next_source_line=948,
            actual_same_p=True,
            retired_seven_load_substitution=False,
            constructor_handoff_phase_cache_dyna_INIT_admitted=False,
        ),
    )


def _bindings():
    functions = (
        _digest,
        _ast,
        source_plan,
        _authority,
        _permission,
        _compile,
        _native,
        _native_bindings,
        _stacks,
        _stable,
        _grn_graph,
        _ancestry,
        _claim,
        _claim.__wrapped__,
        request_record,
        from_network,
        _check,
        _capture,
        _entry,
        _returned,
        _observe,
        _observe.__wrapped__,
        _invoke,
        _outputs,
        trial_record,
        _validate,
        prepare,
        require_continuation,
        _bindings,
    )
    return (
        (),
        (
            LAW_ID,
            PREVIOUS_SHA256,
            RELEASE,
            START,
            STOP,
            _FLOAT,
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
