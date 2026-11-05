"""Original network-branch input authority; parsing/advancement remains held.

Bind the actual original YAML read frame and an optional issued immutable file
permission. Compile the original branch with one explicit retained-local
transport statement. No native join/parser, callback, constructor or branch is
invoked, and p is never mutated or retired by this metadata preparation.
"""

import ast
import copy
import hashlib
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import get_ident
from types import FunctionType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_parameter_event_declarations as previous

LAW_ID = "betse_native_parameter_network_boundary_inputs@1"
PREVIOUS_SHA256 = "3440e519d5c0232ef99245a1a57db5852278f8c11843ccfc437cea69ec53928b"
START, STOP = 61, 62
LOCAL_KEY = "_cells_original_yaml_version"
prefix, claims = previous.prefix, previous.claims
_ISSUED, _ACTIVE = WeakKeyDictionary(), []


class BoundaryRejected(ValueError):
    def __init__(
        self, reason, *, stage, parent=None, partial=None, source_error=None, capture_errors=()
    ):
        super().__init__(reason)
        self.stage, self.parent, self.partial = stage, parent, partial
        self.source_error, self.capture_errors = source_error, tuple(capture_errors)


@dataclass(frozen=True, slots=True)
class Binding:
    parent_trial_identity: str
    yaml_read_trial_identity: str
    original_file_identity: str
    yaml_version: str
    branch: str
    file_identity: str | None
    join_arguments: tuple | None
    source_identity: str
    identity: str


class NetworkBoundary:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use same-p network-boundary preparation")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live network boundaries cannot be serialized")

    @property
    def binding(self):
        return _validate(self).binding

    @property
    def parameters(self):
        return _validate(self).p


def _digest(value):
    return previous._digest(value)


def _ast():
    path, cls, load, _ = previous._ast()
    selected = load.body[START:STOP]
    if (
        len(selected) != 1
        or ast.unparse(selected[0].test) != "self.network_config is not None"
        or ast.unparse(load.body[STOP])
        != (
            "self.grn_enabled = self._conf['gene regulatory network settings']"
            "['gene regulatory network simulated']"
        )
    ):
        raise ValueError("Original network/GRN branch boundary changed")
    return path, cls, load, selected


def source_plan():
    if hashlib.sha256(Path(previous.__file__).read_bytes()).hexdigest() != PREVIOUS_SHA256:
        raise ValueError("Explicit event-declaration producer required")
    parent = previous.source_plan()
    if parent["statement_slice"] != (29, START):
        raise ValueError("Contiguous declaration parent required")
    _, _, load, selected = _ast()
    return dict(
        law=LAW_ID,
        predecessor=PREVIOUS_SHA256,
        native_pins=parent["native_pins"],
        statement_slice=(START, STOP),
        source_lines=(selected[0].lineno, selected[-1].end_lineno),
        next_source_line=load.body[STOP].lineno,
        original_branch_ast=_digest(ast.dump(ast.Module(body=selected, type_ignores=[]))),
        local_transport=f"YAML_VERSION = kwargs[{LOCAL_KEY!r}]",
        permission="issued immutable file bytes; native computed-path observation still required",
        branch_join_parser_execution=False,
        parameter_advance_phase_INIT_admitted=False,
    )


def _ancestor(parent):
    # Event -> numeric -> seven loads -> paths -> original YAML read.
    numeric, subconfig, paths = parent.parent, parent.parent.parent, parent.parent.parent.parent
    yaml = paths.yaml
    if (
        numeric.birth is not parent.birth
        or subconfig.birth is not parent.birth
        or yaml.parent is not parent.birth
        or yaml.p is not parent.p
        or yaml.request.parent is not parent.birth.owner
        or prefix.parameters._ISSUED.get(yaml.request.parent) is not parent.birth
        or type(yaml.owner) is not prefix.YamlPrefixOwner
        or prefix._ISSUED.get(yaml.owner) is not yaml
        or prefix._CONSUMED.get(yaml.request) is not yaml
        or prefix._CLAIMED.get(yaml.request.parent) is not yaml
        or yaml.prefix_completed is not True
        or yaml.trial.prefix_completed is not True
    ):
        raise BoundaryRejected("Original issued YAML read ancestry absent", stage="read_ancestry")
    prefix.parameters.inherited.tissue.core.caches.validate(yaml.trial.graph)
    if _digest(prefix.trial_record(yaml.trial)) != yaml.trial.identity:
        raise BoundaryRejected("Original YAML read trial changed", stage="read_ancestry")
    return yaml


def _read_frame(parent):
    try:
        yaml = _ancestor(parent)
        prefix._verify_file(yaml.request.file)
        native = prefix.parameters.inherited.tissue.aliases.NATIVE
        key = (str(native / prefix.parameters.PARAMETERS), "Parameters.load")
        frame = yaml.locals.get(key)
        if (
            type(frame) is not dict
            or frame.get("self") is not parent.p
            or frame.get("__class__") is not parent.birth.source.cls
            or type(frame.get("args")) is not tuple
            or frame["args"] != (yaml.request.file.filename,)
            or type(frame.get("kwargs")) is not dict
            or frame["kwargs"]
            or type(frame.get("YAML_VERSION")) is not str
            or frame["YAML_VERSION"] != "1.2"
        ):
            raise BoundaryRejected(
                "Actual original YAML_VERSION/read frame required", stage="read_frame"
            )
        prefix.parameters.inherited._same(
            prefix._function_bindings(yaml.function), yaml.function_bindings
        )
        if yaml.function.__globals__ is not vars(
            parent.birth.source.modules["betse.science.parameters"]
        ):
            raise BoundaryRejected(
                "Original read function/module association changed", stage="read_function"
            )
        return yaml, frame
    except BoundaryRejected:
        raise
    except (AttributeError, KeyError, TypeError) as error:
        raise BoundaryRejected(
            "Original read-frame authority unavailable", stage="read_ancestry", source_error=error
        ) from error


def _compile(parent):
    # Original function/header/cached builtins are checked by the existing code.
    _, native = previous._compile(parent)
    path, cls, load, selected = _ast()
    cls = copy.deepcopy(cls)
    method = prefix.parameters.inherited._method(cls, "load")
    transport = ast.parse(f"YAML_VERSION = kwargs[{LOCAL_KEY!r}]").body[0]
    method.body = [transport, *copy.deepcopy(selected)]
    code = prefix.parameters._method_code(cls, "load", str(path))
    if code.co_freevars:
        raise ValueError("Unexpected network closure dependency")
    function = FunctionType(code, native.__globals__, native.__name__, None, None)
    if function.__builtins__ is not native.__builtins__:
        raise ValueError("Network compiler cached builtins changed")
    return function, native


@contextmanager
def _inspection(owner):
    if type(owner) is not previous.EventDeclarationsOwner or owner not in previous._ISSUED:
        previous._validate(owner)
        raise AssertionError("Unissued declaration validator returned")
    parent = previous._ISSUED[owner]
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
    context = SimpleNamespace(
        owner=owner,
        parent=parent,
        guard=guard,
        active=True,
        invalid=False,
        work=[],
        source_error=None,
        capture_errors=(),
    )
    stacks = (
        (_ACTIVE, context),
        (previous._ACTIVE, context),
        (previous.previous._ACTIVE, context),
        (claims._ACTIVE, context),
        (previous.previous.previous._ACTIVE, context),
        (previous.previous.previous.paths._ACTIVE, guard),
    )
    with claims._registry(owner):
        if any(stack for stack, _ in stacks):
            claims._busy(owner, "network_boundary_conflict")
        for stack, value in stacks:
            stack.append(value)
    try:
        previous.previous.previous.paths._install_audit(guard)
        context.work.append(("parent_validation", "attempted"))
        if previous._validate(owner) is not parent:
            raise ValueError("Foreign declaration parent")
        context.work.append(("parent_validation", "completed"))
        yield context
    except BaseException as error:
        context.source_error = error
        raise
    finally:
        try:
            if context.invalid or guard.invalid:
                raise ValueError("Poisoned boundary claim")
            previous._validate(owner)
        except BaseException as error:
            context.capture_errors += (("exit_validation", error),)
        try:
            with claims._registry(owner):
                for stack, value in reversed(stacks):
                    if not stack or stack[-1] is not value:
                        raise ValueError("Boundary registry changed")
                    stack.pop()
        except BaseException as error:
            context.capture_errors += (("claim_release", error),)
        context.active = guard.active = False
        failed = context.source_error is not None or context.invalid or bool(context.capture_errors)
        if failed:
            context.invalid = guard.invalid = parent.invalid = True
        if context.source_error is not None:
            try:
                context.source_error.network_boundary_claim = context
            except BaseException as error:
                context.capture_errors += (("exception_evidence", error),)
        elif failed:
            raise BoundaryRejected(
                "Network input claim issued no success",
                stage="claim_exit",
                parent=owner,
                partial=context,
                capture_errors=context.capture_errors,
            ) from context.capture_errors[0][1]


def binding_record(value):
    return dict(
        law=LAW_ID,
        parent=value.parent_trial_identity,
        read=value.yaml_read_trial_identity,
        original_file=value.original_file_identity,
        yaml_version=value.yaml_version,
        branch=value.branch,
        file=value.file_identity,
        join_arguments=value.join_arguments,
        source=value.source_identity,
        parsed=False,
        advanced=False,
    )


def _permissions(parent, expression_file):
    config = parent.p.network_config
    if config is None:
        branch, relative = "no_network", None
    else:
        # Preserve the original first-key failure and literal None/'None' test.
        config["implement network"]
        relative = config.get("expression data file", None)
        branch = (
            "no_expression_file" if relative is None or relative == "None" else "expression_file"
        )
    if branch != "expression_file":
        if expression_file is not None:
            raise BoundaryRejected(
                "Unreached expression-file permission refused", stage="file_route"
            )
        return branch, None
    if expression_file is None:
        raise BoundaryRejected(
            "Issued immutable expression-data file required", stage="file_authority"
        )
    prefix._verify_file(expression_file)
    dirname = vars(parent.p).get("_conf_dirname")
    if type(dirname) is not str or dirname != str(
        Path(parent.parent.parent.parent.yaml.request.file.filename).parent
    ):
        raise BoundaryRejected(
            "Actual retained configuration directory required", stage="directory"
        )
    return branch, (dirname, relative)


def prepare(owner, *, law_id, expression_file=None):
    if type(law_id) is not str or law_id != LAW_ID:
        raise BoundaryRejected("Explicit network-boundary law required", stage="law", parent=owner)
    with _inspection(owner) as claim:
        parent = claim.parent
        plan = source_plan()
        yaml, frame = _read_frame(parent)
        branch, join_arguments = _permissions(parent, expression_file)
        function, original = _compile(parent)
        value = Binding(
            parent.trial.identity,
            yaml.trial.identity,
            yaml.request.file.identity,
            frame["YAML_VERSION"],
            branch,
            None if expression_file is None else expression_file.identity,
            join_arguments,
            _digest(plan),
            "",
        )
        value = replace(value, identity=_digest(binding_record(value)))
        boundary = object.__new__(NetworkBoundary)
        context = SimpleNamespace(
            owner_parent=owner,
            parent=parent,
            p=parent.p,
            binding=value,
            yaml=yaml,
            frame=frame,
            version=frame["YAML_VERSION"],
            file=expression_file,
            function=function,
            original=original,
            function_bindings=prefix._function_bindings(function),
            original_bindings=prefix._function_bindings(original),
            before=(parent.trial, parent.graph, parent.birth),
            bindings=_bindings(),
            source_identity=_digest(plan),
            work=claim.work,
            claim=claim,
        )
        _ISSUED[boundary] = context
        _check(context)
        return boundary


def _check(context):
    parent = context.parent
    if (
        previous._ISSUED.get(context.owner_parent) is not parent
        or context.p is not parent.p
        or any(
            a is not b
            for a, b in zip(context.before, (parent.trial, parent.graph, parent.birth), strict=True)
        )
        or context.claim.invalid
        or context.claim.guard.invalid
    ):
        raise ValueError("Original boundary/parameter association changed")
    prefix.parameters.inherited._same(_bindings(), context.bindings)
    yaml, frame = _read_frame(parent)
    if (
        yaml is not context.yaml
        or frame is not context.frame
        or frame["YAML_VERSION"] is not context.version
    ):
        raise ValueError("Original read frame/version association changed")
    branch, arguments = _permissions(parent, context.file)
    if branch != context.binding.branch or arguments != context.binding.join_arguments:
        raise ValueError("Original network/file route changed")
    prefix.parameters.inherited._same(
        prefix._function_bindings(context.function), context.function_bindings
    )
    prefix.parameters.inherited._same(
        prefix._function_bindings(context.original), context.original_bindings
    )
    if (
        _digest(source_plan()) != context.source_identity
        or _digest(binding_record(context.binding)) != context.binding.identity
    ):
        raise ValueError("Network boundary producer/binding changed")


def _validate(boundary):
    if type(boundary) is not NetworkBoundary or boundary not in _ISSUED:
        raise BoundaryRejected("Issued network boundary required", stage="boundary")
    context = _ISSUED[boundary]
    with _inspection(context.owner_parent):
        _check(context)
    return context


def require_execution(boundary):
    context = _validate(boundary)
    raise BoundaryRejected(
        "Actual native join observation, parser and branch retirement remain held",
        stage="native_branch_held",
        parent=context.owner_parent,
        partial=dict(
            binding=binding_record(context.binding),
            native_join_observed=False,
            no_supplied_join_result_admission=True,
            parsed=False,
            advanced=False,
            next_source_line=802,
        ),
    )


def _bindings():
    functions = (
        _digest,
        _ast,
        source_plan,
        _ancestor,
        _read_frame,
        _compile,
        _inspection,
        _inspection.__wrapped__,
        binding_record,
        _permissions,
        prepare,
        _check,
        _validate,
        require_execution,
        _bindings,
    )
    return (
        (),
        (
            LAW_ID,
            PREVIOUS_SHA256,
            START,
            STOP,
            LOCAL_KEY,
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
