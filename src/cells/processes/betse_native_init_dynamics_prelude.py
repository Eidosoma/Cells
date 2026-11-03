"""Held actual INIT dynamics prelude, before profile remapping and RNG.

Only an actual completed retained-world InitOwner may be consumed. The native
prefix and reached helpers are reused; no material, Cells, phase, callback,
parameter, timing input or gap-junction state is supplied or regenerated.
"""

import ast
import builtins
import copy
import hashlib
import os
import struct
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import CodeType, FrameType, FunctionType, MappingProxyType, ModuleType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_init_dynamics_prelude_source as source
from cells.processes import betse_native_init_retained_world as previous

LAW_ID = "betse_actual_INIT_dynamics_smoothing_gap_environment_boundary_prelude@1"
RELEASE = "CELLS_NATIVE_INIT_DYNAMICS_PRELUDE_RELEASED"
PARENT_SOURCE_SHA256 = None
PARENT_REVIEW_SHA256 = None
PARENT_CLAIM = "_claim_for_init_dynamics_prelude"
PARENT_CHECK = "_check_init_dynamics_prelude_authority"
NATIVE = Path("/mnt/workspaces/Cells/betse-v1.5.0")
SIM_FILE = "betse/science/sim.py"
GAP_FILE = "betse/science/channels/gap_junction.py"
NATIVE_PINS = {
    SIM_FILE: "02a9a049b5daa5cf6bc543332aa89437f58a4700ed31310abc3ee13697f22d43",
    GAP_FILE: "17b4bd95ea8801c0907a8363d71a194d14292df5f25509f9f353397f91d39bbd",
}
SIM_STORES = (
    "smooth_weight_mem",
    "smooth_weight_o",
    "gj_funk",
    "D_env",
    "D_env_weight",
    "D_env_weight_base",
    "TJ_modulator",
    "TJ_targets",
    "Chi",
    "c_env_bound",
)
GAP_STORES = ("lamb", "A1", "A2", "Ao", "alpha", "beta", "gjopen")
METHODS = ("init_dynamics", "initDenv", "get_ion")
MAX_WORK = 100000
_REQUESTS, _CONSUMED, _RETIRED, _ISSUED = (WeakKeyDictionary() for _ in range(4))
_ACTIVE, _FAILED, _LOCK = [], [], RLock()


class DynamicsRejected(ValueError):
    def __init__(self, reason, *, stage, request=None, trial=None, partial=None):
        super().__init__(reason)
        self.stage, self.request, self.trial, self.partial = stage, request, trial, partial


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    init_owner: object
    parent_identity: str
    source_identity: str
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("Live INIT authority cannot be reconstructed from data")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    parent_identity: str
    before: object
    after: object
    work: tuple
    c_calls: tuple
    raw_returns: tuple
    ion_order: tuple
    gap_constructed: bool
    source_completed: bool
    identity: str


def _digest(value):
    return previous._digest(value)


def _method(tree, cls, name):
    owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    return next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == name)


def _header(node):
    value = copy.deepcopy(node.args)
    for arg in (
        *value.posonlyargs,
        *value.args,
        *value.kwonlyargs,
        *(() if value.vararg is None else (value.vararg,)),
        *(() if value.kwarg is None else (value.kwarg,)),
    ):
        arg.annotation = None
    return ast.dump(value)


def _nodes():
    trees = {}
    for name, expected in NATIVE_PINS.items():
        path = NATIVE / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Original dynamics/helper source required: " + name)
        trees[name] = ast.parse(path.read_bytes())
    selected = copy.deepcopy(_method(trees[SIM_FILE], "Simulator", "init_dynamics"))
    if (
        len(selected.body) <= 10
        or selected.body[10].lineno != 809
        or ast.unparse(selected.body[10]) != "phase.dyna.init_profiles(phase)"
    ):
        raise ValueError("Exact original profile boundary required")
    selected.body = selected.body[:10]
    selected.end_lineno = selected.body[-1].end_lineno
    nodes = {
        "init_dynamics": selected,
        **{name: _method(trees[SIM_FILE], "Simulator", name) for name in METHODS[1:]},
        **{
            "Gap_Junction." + name: _method(trees[GAP_FILE], "Gap_Junction", name)
            for name in ("__init__", "init")
        },
    }
    proof = ast.parse(Path(source.__file__).read_bytes())
    for role, node in nodes.items():
        cls, name = (
            ("GapJunctionConstruction", role.split(".")[1])
            if "." in role
            else ("InitDynamicsPrelude", role)
        )
        actual = _method(proof, cls, name)
        if ast.dump(ast.Module(body=node.body, type_ignores=[])) != ast.dump(
            ast.Module(body=actual.body, type_ignores=[])
        ):
            raise ValueError("Literal original body/order changed: " + role)
        if (
            _header(node) != _header(actual)
            or actual.decorator_list
            or actual.returns is not None
            or actual.type_params
        ):
            raise ValueError("Original helper complete argument/declaration changed: " + role)
    return nodes


def _codes():
    result = {}
    for role, original in _nodes().items():
        node = copy.deepcopy(original)
        node.decorator_list, node.returns = [], None
        for arg in (
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
            *(() if node.args.vararg is None else (node.args.vararg,)),
            *(() if node.args.kwarg is None else (node.args.kwarg,)),
        ):
            arg.annotation = None
        code = compile(
            ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
            str(NATIVE / (GAP_FILE if "." in role else SIM_FILE)),
            "exec",
            dont_inherit=True,
        )
        result[role] = next(c for c in code.co_consts if type(c) is CodeType)
    return result


def _native_code(relative, cls, name):
    """Compile original module/class context; execute no native definition."""
    path = NATIVE / relative
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != NATIVE_PINS[relative]:
        raise ValueError("Pinned complete original module required")
    unit = compile(path.read_bytes(), str(path), "exec", dont_inherit=True)
    owner = next(code for code in unit.co_consts if type(code) is CodeType and code.co_name == cls)
    return next(code for code in owner.co_consts if type(code) is CodeType and code.co_name == name)


def _source_helpers(namespace, numpy):
    helpers = {name: getattr(numpy, name) for name in ("ones", "copy", "hstack", "abs", "exp")}
    logs = namespace["logs"]
    helpers.update(log_info=logs.log_info, gaussian_filter=namespace["gaussian_filter"])
    # The pinned get_ion contains logs.warning in its unknown-ion branch,
    # although native logs only exports log_warning. Preserve that conditional
    # AttributeError; normal namespace preparation must not reach it eagerly.
    if "warning" in vars(logs):
        helpers["log_warning"] = vars(logs)["warning"]
    return helpers


def _constant(value):
    """Typed executable constants, without evaluating any original body."""
    kind = type(value)
    if value is None or value is Ellipsis or kind in (str, bytes, bool, int):
        return kind, value
    if kind is float:
        return kind, struct.pack(">d", value)
    if kind is complex:
        return kind, struct.pack(">dd", value.real, value.imag)
    if kind is tuple:
        return kind, tuple(_constant(item) for item in value)
    if kind is frozenset:
        return kind, frozenset(_constant(item) for item in value)
    if kind is CodeType:
        return (
            kind,
            value.co_code,
            value.co_names,
            value.co_varnames,
            value.co_freevars,
            value.co_cellvars,
            value.co_argcount,
            value.co_posonlyargcount,
            value.co_kwonlyargcount,
            value.co_flags,
            value.co_nlocals,
            value.co_stacksize,
            value.co_exceptiontable,
            tuple(_constant(item) for item in value.co_consts),
        )
    raise ValueError("Unsupported executable constant type")


def source_plan():
    nodes = _nodes()
    return dict(
        law=LAW_ID,
        native_pins=NATIVE_PINS,
        prefix=(758, 806),
        source_extent=(
            "init_dynamics.body[:10]; original get_ion/initDenv; "
            "original Gap_Junction constructor/init"
        ),
        helpers={name: (node.lineno, node.end_lineno) for name, node in nodes.items()},
        parent_source=PARENT_SOURCE_SHA256,
        parent_review=PARENT_REVIEW_SHA256,
        parent_handoff={
            PARENT_CLAIM: "(owner, *, expected=actual retained Trial, transition, entries)",
            PARENT_CHECK: "(transition) -> identical actual retired INIT context",
            "entries.wrapper_guard": "(transition, original_INIT_context, actual_wrapper_frame)",
            "entries.dispatch": (
                "(transition, original_INIT_context, label, original_delegate, actual_sim, "
                "args_tuple, kwargs, actual_parent_invoke_frame)"
            ),
        },
        effects=SIM_STORES,
        gap_state=GAP_STORES,
        actual_parent="Actual completed same-phase InitOwner; no supplied material/cache authority",
        evidence="Original results/partial frames retained before observation; no replay",
        work="Source/helper frames and known C calls count as entries, never cases or flops",
        maximum_observed_entries=MAX_WORK,
        parent_integration="Explicit retirement and original wrapper routing required; pins unset",
        normal_ECM_only=True,
        native_arithmetic_or_branch_order_changed=False,
        stopped_before=(
            "init_profiles",
            "channel_noise_factor RNG",
            "molecule/GRN reinitialization",
            "calcium/flow/deformation",
            "init_events",
            "clear_storage",
            "update_V",
            "time vector/progress callbacks",
            "INIT timesteps",
            "pickle",
        ),
        numerical_or_fourth_step_or_completed_INIT_admission=False,
        actual_execution_held=True,
    )


def _ready():
    if not all(
        type(value) is str and len(value) == 64
        for value in (PARENT_SOURCE_SHA256, PARENT_REVIEW_SHA256)
    ):
        raise DynamicsRejected("Reviewed actual INIT handoff remains unbound", stage="unbound")
    if hashlib.sha256(Path(previous.__file__).read_bytes()).hexdigest() != PARENT_SOURCE_SHA256:
        raise DynamicsRejected("Original parent producer changed", stage="parent_source")
    for name in (PARENT_CLAIM, PARENT_CHECK):
        fn = vars(previous).get(name)
        if type(fn) is not FunctionType or fn.__globals__ is not vars(previous):
            raise DynamicsRejected(
                "Actual parent retirement/check hook unavailable", stage="handoff"
            )


def request_record(value):
    return dict(law=LAW_ID, parent=value.parent_identity, source=value.source_identity)


def from_init(owner, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise DynamicsRejected("Exact dynamics-prelude law required", stage="law")
    _ready()
    with _LOCK:
        if _ACTIVE:
            _ACTIVE[-1].invalid = True
            raise DynamicsRejected("Reentrant dynamics declaration", stage="reentrant")
        if type(owner) is not previous.InitOwner or owner in _RETIRED:
            raise DynamicsRejected("Actual unconsumed INIT core owner required", stage="owner")
        parent = previous._authority(owner)
        if parent.phase.kind.name != "INIT" or parent.p._run_sim is not False:
            raise DynamicsRejected("Actual INIT source phase required", stage="phase")
        if parent.p.is_ecm is not True:
            raise DynamicsRejected("Ordinary normal-ECM owner required", stage="ECM")
        value = Request(owner, parent.trial.identity, _digest(source_plan()), "")
        value = replace(value, identity=_digest(request_record(value)))
        _REQUESTS[value] = (
            parent,
            parent.trial,
            previous._snapshot(parent),
            previous._graph(parent),
        )
        return value


def _guard(context):
    if context.entry_error is not None:
        raise context.entry_error
    if context.capture_error is not None:
        raise DynamicsRejected(
            "Incomplete observation; no next source call",
            stage="capture",
            request=context.request,
            partial=context,
        )
    if context.inherited:
        _reject(context, "An inherited observer cannot enter source work")
    if (
        sys.setprofile is not context.setters[0]
        or sys.settrace is not context.setters[1]
        or sys.getprofile is not context.getters[0]
        or sys.gettrace is not context.getters[1]
        or sys.call_tracing is not context.call_tracing
    ):
        _reject(context, "Original observer controls changed")
    if context.observing and (
        context.getters[0]() is not context.observers[0]
        or context.getters[1]() is not context.observers[1]
    ):
        _reject(context, "Both source observers required before continuation")
    if (
        not context.active
        or context.invalid
        or context.thread != get_ident()
        or not _ACTIVE
        or _ACTIVE[-1] is not context
    ):
        raise DynamicsRejected(
            "Active exclusive dynamics epoch required", stage="epoch", partial=context
        )


def _reject(context, reason):
    context.invalid = True
    if context.entry_error is None:
        context.entry_error = DynamicsRejected(
            reason, stage=context.stage, request=context.request, partial=context
        )
    raise context.entry_error


def _record_capture(context, origin, error, witness):
    context.last_capture = (origin, error, witness)
    if context.capture_error is None:
        context.capture_error = error
    try:
        context.capture_errors += (context.last_capture,)
    except BaseException as secondary:
        context.reporting_failure = (secondary, context.last_capture)


def _values(context, *, stable=False):
    parent = context.parent
    projector = previous._projector(parent)
    gap = context.gap if context.gap is not None else context.gap_inflight
    if gap is not None:
        projector.objects = [*projector.objects, ("gap_dynamics", gap)]
    sim = {
        name: value
        for name, value in vars(context.sim).items()
        if not stable or name not in SIM_STORES
    }
    return dict(
        simulator=previous.core._LITERAL._project(projector, sim),
        cells=previous.core._LITERAL._project(projector, vars(context.cells)),
        parameters=previous.core._LITERAL._project(projector, vars(context.p)),
        phase=previous.core._LITERAL._project(projector, vars(context.phase)),
        handler=previous.core._LITERAL._project(projector, vars(context.phase.dyna)),
        other_objects=tuple(
            (role, previous.core._LITERAL._project(projector, vars(actual)))
            for role, actual in parent.objects
            if actual is not context.sim
        ),
        gap=None if stable or gap is None else vars(gap),
    )


def _scope(context):
    return previous.core.previous._scope(context.parent.parent.world)


def _snapshot(context, *, stable=False):
    return _scope(context).snapshot(_values(context, stable=stable))


def _graph(context):
    # The existing closed graph walker sees the actual holders/arrays, not
    # temporary projection dictionaries. Unknown objects remain identity leaves;
    # the actual new Gap_Junction holder is included explicitly after its return.
    context.graph_fields[:] = [vars(value) for _, value in context.parent.objects]
    gap = context.gap if context.gap is not None else context.gap_inflight
    if gap is not None:
        context.graph_fields.append(vars(gap))
    return _scope(context).graph(context.graph_view, context.graph_view, context.graph_tape)


def _binding(context):
    result = [
        context.parent,
        context.phase,
        context.p,
        context.cells,
        context.sim,
        context.parent_check,
        context.parent_claim,
        context.methods,
        context.original_globals,
        context.gap_factory,
        context.numpy,
        context.parent_record,
        context.parent_trial,
        context.entries,
        context.allowed_codes,
        context.helpers,
        context.native_delegates,
        context.metadata,
        context.sim_wrappers,
        _REQUESTS,
        _CONSUMED,
        _RETIRED,
        _ISSUED,
        _ACTIVE,
        _LOCK,
        *context.setters,
        *context.getters,
        context.call_tracing,
    ]
    for cls in (
        type(context.phase),
        type(context.sim),
        type(context.cells),
        type(context.p),
        context.gap_factory,
    ):
        result.extend((cls, *previous.factories._surface(cls)))
    functions = (
        *context.methods.values(),
        *context.native_functions,
        *context.helper_functions,
        context.parent_check,
        context.parent_claim,
    )
    for fn in functions:
        result.extend(previous._atoms(fn))
        result.extend((fn.__globals__, fn.__builtins__))
        namespace = fn.__globals__.get("__builtins__")
        namespace = vars(namespace) if type(namespace) is ModuleType else namespace
        if namespace is not fn.__builtins__ or fn.__builtins__ is not vars(builtins):
            raise ValueError("Original actual cached builtins required")
        for name in fn.__code__.co_names:
            if name not in fn.__globals__ and name in fn.__builtins__:
                result.extend((name, fn.__builtins__[name]))
    result.extend(previous.core._resolved_bindings(functions))
    if tuple(context.private) != tuple(context.original_globals) or any(
        context.private[name] is not (context.gap_constructor if name == "Gap_Junction" else value)
        for name, value in context.original_globals.items()
    ):
        raise ValueError("Private prefix namespace may replace only the declared gap factory")
    result.extend(
        (context.private, context.gap_constructor, *previous._atoms(context.gap_constructor))
    )
    result.extend(v for pair in context.helpers.items() for v in pair)
    for value in context.helpers.values():
        for name in ("__wrapped__", "_implementation"):
            result.extend((name, getattr(value, name, None)))
    result.extend((context.numpy.ndarray, context.numpy.ndarray.reshape, context.numpy.ndarray.max))
    for name, fn in context.metadata:
        if globals().get(name) is not fn:
            raise ValueError("Independent dynamics checker replaced: " + name)
        result.extend(previous._atoms(fn))
    return tuple(result)


def _check(context, *, closed=False):
    if not closed:
        _guard(context)
    if (
        context.parent_check(context) is not context.parent
        or context.thread != get_ident()
        or context.invalid
        or (closed and context.active)
        or _REQUESTS.get(context.request) is not context.refs
        or _CONSUMED.get(context.request) is not context
        or _RETIRED.get(context.request.init_owner) is not context
        or context.phase.p is not context.p
        or context.phase.cells is not context.cells
        or context.phase.sim is not context.sim
        or context.parent.trial is not context.parent_trial
        or context.parent.parameter_record is not context.parent_record
        or context.phase.callbacks is not context.callback
        or vars(context.sim).get("D_env") is not context.original_D_env
        or vars(context.sim).get("c_env_bound") is not context.original_c_env_bound
        or vars(context.sim).get("gj_funk") is not context.gap
        or previous._rng(context.parent).identity != context.stream_before.identity
        or _digest(request_record(context.request)) != context.request.identity
        or _digest(source_plan()) != context.request.source_identity
    ):
        raise ValueError("Exact actual INIT parameter/material/source ancestry changed")
    current = _binding(context)
    expected = context.bindings
    if len(current) != len(expected) or any(
        a is not b for a, b in zip(current, expected, strict=True)
    ):
        raise ValueError("Actual reached source/function/global bindings changed")
    if _snapshot(context, stable=True).identity != context.stable.identity:
        raise ValueError("Dynamics prelude changed parameters, geometry or unowned material")
    if context.gap is not None and (
        type(context.gap) is not context.gap_factory or tuple(vars(context.gap)) != GAP_STORES
    ):
        raise ValueError("Original returned gap owner/state holder changed")


def _dispatch(context, original, label, delegate, actual, args, kwargs, frame):
    _check(context)
    name = label.split(".")[-1]
    if (
        original is not context.parent
        or actual is not context.sim
        or name not in METHODS[1:]
        or delegate is not context.native_delegates[name]
        or kwargs
        or frame is not sys._getframe(1)
    ):
        _reject(context, "Original same-Simulator delegated helper required")
    expected = (context.cells, context.p) if name == "initDenv" else None
    if (
        expected is not None
        and (len(args) != 2 or any(a is not b for a, b in zip(args, expected, strict=True)))
        or name == "get_ion"
        and (len(args) != 1 or type(args[0]) is not str)
    ):
        _reject(context, "Original source helper argument association changed")
    if not context.invocations or context.invocations[-1]["name"] != "init_dynamics":
        _reject(context, "Helper must be reached from the actual original prefix")
    # The issued upstream wrapper hands its OWN live frame through unchanged.
    # Its native source caller must be the identical prefix frame, not a raw
    # source-equivalent call from a metadata observer.
    wrapper = frame.f_back
    if (
        frame.f_code is not previous._invoke.__code__
        or wrapper is None
        or wrapper.f_code is not context.sim_wrappers[name].__code__
        or wrapper.f_globals is not context.sim_wrappers[name].__globals__
        or wrapper.f_back is not context.body_frame
        or context.last_wrapper is None
        or context.last_wrapper[0] != name
        or context.last_wrapper[1] is not wrapper
    ):
        _reject(context, "Helper wrapper detached from the actual prefix frame")
    call = dict(name=name, actual=actual, frame=sys._getframe(), body=None, args=args)
    context.invocations.append(call)
    context.helper_invocations.append(call)
    try:
        returned = context.methods[name](actual, *args)
        context.last_helper_return = (name, args, returned)
        context.helper_returns.append(context.last_helper_return)
        return returned
    finally:
        context.invocations.pop()


def _wrapper_guard(context, original, frame):
    _check(context)
    if type(frame) is not FrameType:
        _reject(context, "Actual issued wrapper frame required")
    values = frame.f_locals
    method = values.get("method")
    function = context.sim_wrappers.get(method) if type(method) is str else None
    if (
        original is not context.parent
        or function is None
        or vars(type(context.sim)).get(method) is not function
        or frame.f_code is not function.__code__
        or frame.f_globals is not function.__globals__
        or values.get("context") is not original
        or values.get("name") != "Simulator"
        or values.get("delegate") is not context.native_delegates[method]
        or frame.f_back is not context.body_frame
        or values.get("actual") is not context.sim
        or not context.invocations
        or context.invocations[-1]["name"] != "init_dynamics"
    ):
        _reject(context, "Only an original issued helper wrapper reached by the prefix may enter")
    for freevar, cell in zip(
        function.__code__.co_freevars, function.__closure__ or (), strict=True
    ):
        if frame.f_locals.get(freevar) is not cell.cell_contents:
            _reject(context, "Original wrapper closure/receiver changed")
    context.last_wrapper = (method, frame)


def _namespace(context):
    native_sim = context.parent.factories["Simulator"]
    functions = {}
    helper = previous.caches.previous.callbacks
    for name in METHODS:
        functions[name] = helper._source_function(
            getattr(native_sim, name), SIM_FILE, name, "Simulator"
        )
        expected = _native_code(SIM_FILE, "Simulator", name)
        if _constant(functions[name].__code__) != _constant(expected):
            raise ValueError("Exact typed executable original required: " + name)
    namespace = functions["init_dynamics"].__globals__
    context.original_globals, context.numpy = namespace, namespace["np"]
    gap = namespace["Gap_Junction"]
    gap_module = sys.modules.get("betse.science.channels.gap_junction")
    if (
        gap_module is None
        or vars(gap_module).get("Gap_Junction") is not gap
        or type(gap) is not type
        or gap.__bases__ != (object,)
    ):
        raise ValueError("Original actually loaded gap-junction class required")
    gap_functions = tuple(
        helper._source_function(vars(gap)[name], GAP_FILE, name, "Gap_Junction")
        for name in ("__init__", "init")
    )
    for name, function in zip(("__init__", "init"), gap_functions, strict=True):
        expected = _native_code(GAP_FILE, "Gap_Junction", name)
        if _constant(function.__code__) != _constant(expected):
            raise ValueError("Original gap executable constants/headers changed: " + name)
    context.gap_factory = gap
    context.native_functions = (*functions.values(), *gap_functions)
    context.native_delegates = {name: getattr(native_sim, name) for name in METHODS[1:]}
    context.sim_wrappers = {name: vars(type(context.sim)).get(name) for name in METHODS[1:]}
    if any(type(fn) is not FunctionType for fn in context.sim_wrappers.values()):
        raise ValueError("Actual retained constructor-issued helper wrappers required")

    def construct_gap(sim, cells, p):
        _check(context)
        if (
            sim is not context.sim
            or cells is not context.cells
            or p is not context.p
            or context.gap is not None
            or context.gap_attempted
        ):
            _reject(context, "Single actual original gap construction on retained owners required")
        context.gap_attempted = True
        if sys._getframe(1) is not context.body_frame:
            _reject(context, "Gap factory detached from actual original prefix")
        invocation = dict(
            name="Gap_Junction.__init__",
            actual=None,
            frame=sys._getframe(),
            body=None,
            args=(sim, cells, p),
        )
        context.invocations.append(invocation)
        try:
            value = gap(sim, cells, p)
            context.last_gap_return = value
            if type(value) is not gap or tuple(vars(value)) != GAP_STORES:
                _reject(context, "Complete original gap constructor/state order required")
            if invocation["actual"] is not value:
                _reject(context, "Returned Gap owner differs from original constructor receiver")
            context.gap = value
            return value
        finally:
            context.invocations.pop()

    private = dict(namespace, Gap_Junction=construct_gap)
    context.private, context.gap_constructor = private, construct_gap
    context.methods = dict(
        functions, init_dynamics=FunctionType(_codes()["init_dynamics"], private, "init_dynamics")
    )
    # The entire native init_dynamics CodeType is deliberately NOT admitted.
    # Existing helpers are the original function objects with original globals.
    context.gap_bodies = {fn.__code__: fn for fn in gap_functions}
    helpers = _source_helpers(namespace, context.numpy)
    context.helpers = MappingProxyType(helpers)
    context.helper_functions = previous.core.previous.previous._native_helper_functions(
        tuple(helpers.values())
    )
    context.allowed_codes = frozenset(
        code
        for fn in (*context.methods.values(), *gap_functions, *context.helper_functions)
        for code in previous._code_tree(fn.__code__)
    )
    context.expected_body = context.methods["init_dynamics"].__code__
    context.body_functions = {fn.__code__: fn for fn in context.methods.values()}
    context.body_functions.update(context.gap_bodies)
    context.full_body = functions["init_dynamics"].__code__
    if context.full_body in context.allowed_codes:
        raise ValueError("Full dynamics body cannot enter the bounded prelude")


def _witness(context, frame, arg):
    context.last_raw = (frame, arg)
    if not previous._normal_return(frame) and context.primary is None:
        original = context.pending.get(id(frame))
        if original is not None:
            context.primary = original


def _admit(context, frame):
    old = context.frames.get(id(frame))
    if old is not None:
        if old["frame"] is not frame or old["returned"]:
            _reject(context, "Repeated completed or replaced original source frame")
        return old
    selected = any(frame.f_code is code for code in context.allowed_codes)
    if not selected and not frame.f_code.co_filename.startswith(str(NATIVE) + os.sep):
        return None
    row = dict(
        frame=frame,
        code=frame.f_code,
        globals=frame.f_globals,
        function=frame.f_code.co_qualname,
        returned=False,
        body_started=False,
    )
    context.last_attempt = row
    context.work.append(row)
    if len(context.work) > MAX_WORK:
        _reject(context, "Declared actual work bound exhausted")
    _check(context)
    if not selected:
        _reject(context, "Unbound native or later dynamics body attempted entry")
    if not context.invocations:
        _reject(context, "Original source invocation is absent")
    invocation = context.invocations[-1]
    function = context.body_functions.get(frame.f_code)
    if function is not None:
        if frame.f_code is not function.__code__ or frame.f_globals is not function.__globals__:
            _reject(context, "Exact original source namespace required")
        if frame.f_code is context.expected_body:
            if (
                invocation["name"] != "init_dynamics"
                or invocation["body"] is not None
                or frame.f_back is not invocation["frame"]
                or frame.f_locals.get("self") is not context.sim
                or frame.f_locals.get("phase") is not context.phase
            ):
                _reject(context, "Single actual same-phase prefix invocation required")
            invocation["body"] = context.body_frame = frame
        elif frame.f_code in context.gap_bodies:
            if invocation["name"] != "Gap_Junction.__init__":
                _reject(context, "Raw gap body has no actual factory invocation")
            actual = frame.f_locals.get("self")
            if (
                type(actual) is not context.gap_factory
                or frame.f_locals.get("sim") is not context.sim
                or frame.f_locals.get("cells") is not context.cells
                or frame.f_locals.get("p") is not context.p
            ):
                _reject(context, "Original gap factory receiver/arguments required")
            if frame.f_code.co_name == "__init__":
                if invocation["body"] is not None or frame.f_back is not invocation["frame"]:
                    _reject(context, "Repeated original gap constructor")
                invocation["actual"], invocation["body"] = actual, frame
                context.gap_inflight = actual
            elif invocation["actual"] is not actual or frame.f_back is not invocation["body"]:
                _reject(context, "Gap init must be reached by its actual original constructor")
        else:
            name = frame.f_code.co_name
            if (
                invocation["name"] != name
                or invocation["body"] is not None
                or frame.f_back is not invocation["frame"]
                or frame.f_locals.get("self") is not context.sim
            ):
                _reject(context, "Original routed helper invocation required")
            invocation["body"] = frame
    else:
        ancestor = frame.f_back
        while ancestor is not None and ancestor is not invocation["body"]:
            ancestor = ancestor.f_back
        if ancestor is None or invocation["body"] is None:
            _reject(context, "Helper detached from the actual selected body")
    context.frames[id(frame)] = row
    row["body_started"] = True
    return row


def _observe(context, frame, event, arg):
    if event == "call":
        _admit(context, frame)
    row = context.frames.get(id(frame))
    if row is None:
        return
    if (
        row["frame"] is not frame
        or row["code"] is not frame.f_code
        or row["globals"] is not frame.f_globals
    ):
        _reject(context, "Original admitted source frame/namespace changed")
    if event == "exception":
        context.pending[id(frame)] = arg[1]
    if event == "line":
        _guard(context)
    if event == "return":
        _witness(context, frame, arg)
        try:
            context.raw_returns.append(context.last_raw)
            context.locals[id(frame)] = dict(frame.f_locals)
        except BaseException as error:
            _record_capture(context, "raw_return_or_locals", error, context.last_raw)
        row["returned"] = True
    if frame is context.body_frame:
        if event == "line":
            _check(context)
        if event == "return" and previous._normal_return(frame):
            context.body_returned, context.body_return = True, arg


def _epoch(context):
    return _snapshot(context).identity, _graph(context), previous._rng(context.parent).identity


def _same_epoch(context, old):
    current = _epoch(context)
    previous.core.previous._same(current[1][0], old[1][0])
    if current[0] != old[0] or current[1][1] != old[1][1] or current[2] != old[2]:
        _reject(context, "Observer changed actual values, aliases/layout or continuing MT")


def _delegate(observer, frame, event, arg):
    return observer(frame, event, arg)


def _inherited(context, observer, frame, event, arg):
    if observer is None:
        return None
    if context.inherited:
        _reject(context, "Reentrant inherited source observer")
    before = _epoch(context)
    context.inherited = True
    primary = None
    try:
        return context.call_tracing(_delegate, (observer, frame, event, arg))
    except BaseException as error:
        primary = error
        if context.primary is None:
            # A return observer may be the first failure. Save it before
            # CPython removes the failing hook and another guard notices the
            # loss; that secondary refusal must not replace this exception.
            context.primary = error
        raise
    finally:
        context.inherited = False
        secondary = None
        try:
            _same_epoch(context, before)
            if context.observing and (
                context.getters[0]() is not context.observers[0]
                or context.getters[1]() is not context.observers[1]
            ):
                _reject(context, "Inherited callback removed an active source observer")
        except BaseException as error:
            secondary = error
            _record_capture(context, "inherited_state", error, (frame, event, arg))
        if primary is None and context.primary is None and secondary is not None:
            raise secondary


def _recover_hooks(context, stage):
    # Every operation is independent. Failed getter/setter evidence never
    # prevents the other hook from being restored AND sampled in both orders.
    for index in (1, 0):
        try:
            context.setters[index](context.required_hooks[index])
        except BaseException as error:
            context.cleanup_errors += ((stage + "_restore", error, index),)
    samples = []
    for order in ((0, 1), (1, 0)):
        pair = [None, None]
        for index in order:
            try:
                pair[index] = context.getters[index]()
            except BaseException as error:
                context.cleanup_errors += ((stage + "_sample", error, index),)
        samples.append(tuple(pair))
    context.final_hooks = tuple(samples)
    context.hooks_safe = all(
        a is context.required_hooks[0] and b is context.required_hooks[1] for a, b in samples
    )


@contextmanager
def _account(context):
    old_profile, old_trace = context.required_hooks
    local = {}

    def profile(frame, event, arg):
        selected = any(frame.f_code is code for code in context.allowed_codes)
        native = frame.f_code.co_filename.startswith(str(NATIVE) + os.sep)
        if context.inherited:
            if event == "call" and (selected or native):
                _reject(context, "Observer attempted raw source entry")
            return
        # CPython's return(None) also represents unwind. Direct raw roots and
        # any original exception/cause precede inherited profile callbacks.
        if event == "return" and id(frame) in context.frames:
            _witness(context, frame, arg)
        if event in ("c_call", "c_return", "c_exception") and id(frame) in context.frames:
            context.last_c_call = (frame, event, arg)
            if event == "c_call":
                context.c_calls.append(context.last_c_call)
                if len(context.work) + len(context.c_calls) > MAX_WORK:
                    _reject(context, "Declared source/C work bound exhausted")
        try:
            _inherited(context, old_profile, frame, event, arg)
        except BaseException as error:
            _record_capture(context, "inherited_profile", error, (frame, event, arg))
            if event not in ("return", "c_return", "c_exception") or context.primary is None:
                raise

    def trace(frame, event, arg):
        selected = any(frame.f_code is code for code in context.allowed_codes)
        native = frame.f_code.co_filename.startswith(str(NATIVE) + os.sep)
        if context.inherited:
            if event == "call" and (selected or native):
                _reject(context, "Observer attempted raw source entry")
            return trace
        if selected or native:
            try:
                _observe(context, frame, event, arg)
            except BaseException as error:
                if error is not context.entry_error:
                    _record_capture(context, "observer", error, (frame, event, arg))
                if event != "return" or context.primary is None:
                    raise
        prior = old_trace if event == "call" else local.get(id(frame))
        try:
            returned = _inherited(context, prior, frame, event, arg)
            if callable(returned):
                local[id(frame)] = returned
        except BaseException as error:
            _record_capture(context, "inherited_trace", error, (frame, event, arg))
            if event != "return" or context.primary is None:
                raise
        finally:
            if event == "return":
                local.pop(id(frame), None)
                context.pending.pop(id(frame), None)
        return trace

    context.observers = profile, trace
    primary = None
    try:
        context.setters[0](profile)
        context.setters[1](trace)
        if context.getters[0]() is not profile or context.getters[1]() is not trace:
            raise ValueError("Both observation guards required before source")
        context.observing = True
        yield
    except BaseException as error:
        selected = context.primary if context.primary is not None else context.entry_error
        primary = error if selected is None else selected
        context.primary = primary
        if primary is not error:
            _record_capture(context, "interrupted_primary", error, primary)
            raise primary  # noqa: B904 - preserve original source/caller primary and cause.
        raise
    finally:
        context.observing = False
        try:
            _recover_hooks(context, "account")
        except BaseException as error:
            context.cleanup_errors += (("recovery_entry_or_return", error, None),)
        finally:
            # A hostile inherited hook can reject the helper's own call entry.
            # Recovery still runs independently in this already-entered frame.
            for index in (1, 0):
                try:
                    context.setters[index](context.required_hooks[index])
                except BaseException as error:
                    context.cleanup_errors += (("boundary_restore", error, index),)
            samples = []
            for order in ((0, 1), (1, 0)):
                pair = [None, None]
                for index in order:
                    try:
                        pair[index] = context.getters[index]()
                    except BaseException as error:
                        context.cleanup_errors += (("boundary_sample", error, index),)
                samples.append(tuple(pair))
            context.final_hooks = tuple(samples)
            context.hooks_safe = all(
                a is context.required_hooks[0] and b is context.required_hooks[1]
                for a, b in samples
            )
        if context.cleanup_errors or not context.hooks_safe:
            context.invalid = True
            if primary is None:
                raise DynamicsRejected(
                    "Observer recovery incomplete", stage="recovery", partial=context
                )


def trial_record(value):
    return dict(
        request=value.request_identity,
        parent=value.parent_identity,
        before=value.before.identity,
        after=value.after.identity,
        work=tuple(
            (file, name, id(frame), started, returned)
            for file, name, frame, started, returned in value.work
        ),
        c_calls=tuple((id(frame), event, id(function)) for frame, event, function in value.c_calls),
        returns=tuple((id(frame), id(raw)) for frame, raw in value.raw_returns),
        ion_order=value.ion_order,
        gap_constructed=value.gap_constructed,
        prefix_completed=value.source_completed,
        full_init_dynamics_completed=False,
        completed_INIT_or_independent_case=False,
    )


def _raw_context(request, refs, parent):
    value = SimpleNamespace(
        request=request,
        refs=refs,
        parent=parent,
        parent_trial=refs[1],
        parent_record=parent.parameter_record,
        phase=parent.phase,
        sim=parent.phase.sim,
        p=parent.p,
        cells=parent.cells,
        callback=parent.callback,
        original_D_env=vars(parent.phase.sim)["D_env"],
        original_c_env_bound=vars(parent.phase.sim)["c_env_bound"],
        active=True,
        invalid=False,
        validating=False,
        thread=get_ident(),
        stage="claim",
        trial=None,
        entry_error=None,
        primary=None,
        capture_error=None,
        capture_errors=(),
        cleanup_errors=(),
        last_capture=None,
        reporting_failure=None,
        work=[],
        raw_returns=[],
        c_calls=[],
        frames={},
        locals={},
        last_attempt=None,
        last_wrapper=None,
        last_raw=None,
        pending={},
        invocations=[],
        helper_invocations=[],
        helper_returns=[],
        body_frame=None,
        body_returned=False,
        body_return=None,
        gap=None,
        gap_inflight=None,
        gap_attempted=False,
        last_gap_return=None,
        required_hooks=(sys.getprofile(), sys.gettrace()),
        setters=(sys.setprofile, sys.settrace),
        getters=(sys.getprofile, sys.gettrace),
        call_tracing=sys.call_tracing,
        observing=False,
        inherited=False,
        hooks_safe=True,
        before=None,
        after=None,
        graph_fields=[],
        stable=None,
        before_graph=None,
        after_graph=None,
    )
    value.graph_view = SimpleNamespace(
        fields=value.graph_fields,
        parameters=vars(parent.p),
        cells=vars(parent.cells),
        actual_phase=parent.phase,
        actual_simulator=parent.phase.sim,
        source_work=value.work,
    )
    value.graph_tape = SimpleNamespace(
        rng=parent.graph_tape.rng,
        events=value.raw_returns,
        draws=value.c_calls,
        locals=value.locals,
    )
    return value


def _run_prefix(context):
    invocation = dict(
        name="init_dynamics",
        actual=context.sim,
        frame=sys._getframe(),
        body=None,
        args=(context.phase,),
    )
    context.invocations.append(invocation)
    try:
        return context.methods["init_dynamics"](context.sim, context.phase)
    finally:
        context.invocations.pop()


def _completion(context):
    if (
        not context.body_returned
        or context.body_return is not None
        or context.primary is not None
        or context.capture_error is not None
        or context.cleanup_errors
        or any(not row["returned"] for row in context.work)
    ):
        raise ValueError("Complete exact original prefix/helper observation required")
    expected = tuple(key for key, value in context.p.ions_dict.items() if value == 1)
    actual = tuple(row["args"][0] for row in context.helper_invocations if row["name"] == "get_ion")
    if (
        len(actual) != len(expected)
        or any(a is not b for a, b in zip(actual, expected, strict=True))
        or tuple(row["name"] for row in context.helper_invocations)
        != ("initDenv", *("get_ion" for _ in expected))
        or len(context.helper_returns) != len(context.helper_invocations)
        or context.helper_returns[0][2] is not None
    ):
        raise ValueError("Literal helper/ion order or actual return association changed")
    if type(context.p.v_sensitive_gj) is not bool:
        raise ValueError("Genuine parameter gap branch must retain its bool type")
    if (
        context.gap_attempted is not context.p.v_sensitive_gj
        or (context.gap is not None) is not context.gap_attempted
        or vars(context.sim).get("gj_funk") is not context.gap
    ):
        raise ValueError(
            "Original conditional gap construction/assignment was omitted or duplicated"
        )
    context.ion_order = actual
    _check(context)


def _attach(context, primary):
    try:
        primary.init_dynamics_prelude_partial = context
    except BaseException as error:
        context.cleanup_errors += (("attachment", error, primary),)


def prepare(request, *, enabled=False):
    _ready()
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise DynamicsRejected("Actual dynamics prelude remains held", stage="release")
    with _LOCK:
        if _ACTIVE:
            _reject(_ACTIVE[-1], "Reentrant dynamics preparation")
        if type(request) is not Request or request not in _REQUESTS:
            raise DynamicsRejected("Actual process-local INIT request required", stage="request")
        if request in _CONSUMED or request.init_owner in _RETIRED:
            raise DynamicsRejected("INIT parent epoch already attempted", stage="consumed")
        refs = _REQUESTS[request]
        parent = previous._authority(request.init_owner)
        current_graph = previous._graph(parent)
        previous.core.previous._same(current_graph[0], refs[3][0])
        if (
            parent is not refs[0]
            or parent.trial is not refs[1]
            or previous._snapshot(parent).identity != refs[2].identity
            or current_graph[1] != refs[3][1]
            or request.identity != _digest(request_record(request))
            or request.source_identity != _digest(source_plan())
        ):
            raise DynamicsRejected("Completed retained INIT parent changed", stage="parent")
        context = _raw_context(request, refs, parent)
        _CONSUMED[request] = _RETIRED[request.init_owner] = context
        _ACTIVE.append(context)
        primary = None
        try:
            context.parent_claim, context.parent_check = (
                getattr(previous, PARENT_CLAIM),
                getattr(previous, PARENT_CHECK),
            )
            context.entries = MappingProxyType(
                dict(dispatch=_dispatch, wrapper_guard=_wrapper_guard)
            )
            context.parent_claim(
                request.init_owner, expected=refs[1], transition=context, entries=context.entries
            )
            _namespace(context)
            context.metadata = tuple(
                (name, globals()[name])
                for name in (
                    "_ready",
                    "_check",
                    "_binding",
                    "_guard",
                    "_admit",
                    "_observe",
                    "_witness",
                    "_wrapper_guard",
                    "_dispatch",
                    "_snapshot",
                    "_scope",
                    "_values",
                    "_graph",
                    "_epoch",
                    "_same_epoch",
                    "_inherited",
                    "_completion",
                    "_run_prefix",
                    "_namespace",
                    "_attach",
                    "_constant",
                    "_native_code",
                    "_source_helpers",
                    "_account",
                    "_recover_hooks",
                    "_record_capture",
                    "_authority",
                    "failed_context",
                    "trial_record",
                    "source_plan",
                )
            )
            context.stream_before = previous._rng(parent)
            context.bindings = _binding(context)
            context.before, context.stable = _snapshot(context), _snapshot(context, stable=True)
            context.before_graph = _graph(context)
            with _account(context):
                context.stage = "actual_native_dynamics_prelude"
                context.prefix_return = _run_prefix(context)
            _completion(context)
            context.after = _snapshot(context)
            context.after_graph = _graph(context)
            value = Trial(
                request.identity,
                request.parent_identity,
                context.before,
                context.after,
                tuple(
                    (
                        row["code"].co_filename,
                        row["function"],
                        row["frame"],
                        row["body_started"],
                        row["returned"],
                    )
                    for row in context.work
                ),
                tuple(context.c_calls),
                tuple(context.raw_returns),
                context.ion_order,
                context.gap is not None,
                True,
                "",
            )
            context.trial = replace(value, identity=_digest(trial_record(value)))
        except BaseException as error:
            primary = context.primary if context.primary is not None else error
            context.primary, context.invalid = primary, True
            _FAILED.append(context)
            # Attachment is fallible evidence work and MUST precede final
            # independent recovery/sampling. It never replaces the primary.
            try:
                _attach(context, primary)
            except BaseException as error:
                context.cleanup_errors += (("attachment_entry_or_return", error, primary),)
        finally:
            context.active = False
            if _ACTIVE and _ACTIVE[-1] is context:
                _ACTIVE.pop()
            else:
                context.invalid = True
            # Capture/sealing callbacks may have changed either hook after
            # the observer scope. Final independent attempts follow them all.
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
                a is context.required_hooks[0] and b is context.required_hooks[1]
                for a, b in samples
            )
        if primary is not None:
            raise primary
        if context.invalid or context.cleanup_errors or not context.hooks_safe:
            context.invalid = True
            _FAILED.append(context)
            raise DynamicsRejected(
                "No complete dynamics prefix publication", stage="closure", partial=context
            )
        owner = object.__new__(PreludeOwner)
        _ISSUED[owner] = (context, context.trial)
        return owner


class PreludeOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use actual retained INIT prelude preparation")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live material/source ownership cannot be reconstructed")

    @property
    def phase(self):
        return _authority(self).phase

    @property
    def trial(self):
        return _authority(self).trial


def _authority(owner):
    if type(owner) is not PreludeOwner or owner not in _ISSUED:
        raise DynamicsRejected("Actual issued prelude owner required", stage="owner")
    context, issued_trial = _ISSUED[owner]
    if context.active or context.invalid or context.validating:
        raise DynamicsRejected("Prelude epoch unavailable", stage="owner")
    context.validating = True
    try:
        # Closed validation authenticates parent metadata through its adopted
        # factored handoff, never the now-stale parent full-state reader.
        _ready()
        _check(context, closed=True)
        graph = _graph(context)
        previous.core.previous._same(graph[0], context.after_graph[0])
        if (
            context.trial is not issued_trial
            or _snapshot(context).identity != context.after.identity
            or graph[1] != context.after_graph[1]
            or context.trial.identity != _digest(trial_record(context.trial))
        ):
            raise ValueError("Actual dynamics material/cache/source state changed")
        return context
    except BaseException:
        context.invalid = True
        raise
    finally:
        context.validating = False


def failed_context(value):
    if type(value) is not Request or value not in _CONSUMED:
        raise DynamicsRejected("Actual attempted process-local request required", stage="request")
    context = _CONSUMED[value]
    if context.active or not context.invalid:
        raise DynamicsRejected("Request has no closed failed attempt", stage="failure")
    return context
