"""Same-caller environment/grid_len/make_maskM source, stopping before Poisson.

Fresh plot-grid stores and actual issued trees are required. Source trials are
not full make_world, phase, geometry/physical parity or checkpoint admission.
"""

import ast
import hashlib
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import FunctionType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_single_cell_environment_source as source
from cells.processes import betse_native_single_cell_make_ecm as ecm

geometry, parameters, core = ecm.geometry, ecm.parameters, ecm.core
LAW_ID = "betse_owned_single_cell_environment_mask@1"
INVALIDATED_OWNERS = ecm.INVALIDATED_OWNERS
HELD_UNQUALIFIED_SOURCE_STAGE = True
METHODS = ("environment", "assign_grid_len", "make_maskM")
_METHODS = {name: getattr(source.CellsEnvironment, name) for name in METHODS}
_NATIVE_TREE = source.cKDTree
_TREE_INIT, _TREE_QUERY = _NATIVE_TREE.__init__, _NATIVE_TREE.query
_GRIDDATA, _GAUSSIAN = source.interp.griddata, source.gaussian_filter
_HELPERS = ("column_stack", "zeros", "ones", "sum", "asarray", "linspace", "meshgrid", "round")
_TREE_FIELDS = ("data", "indices", "mins", "maxes", "n", "m", "leafsize", "boxsize")
_ISSUED, _TREES = WeakKeyDictionary(), WeakKeyDictionary()
_LOCK = RLock()


@dataclass(frozen=True, slots=True)
class Request:
    ecm_request: ecm.Request
    identity: str


@dataclass(frozen=True, slots=True)
class ContinuationRequest:
    ecm_owner: ecm.EcmOwner
    identity: str


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    parent_identity: str
    before: object
    cache: object
    stages: tuple
    events: tuple
    work: tuple
    stream_before: object
    stream_after: object
    source_completed: bool
    failure_stage: str | None
    failure_type: str | None
    failure_message: str | None
    identity: str


class EnvironmentRejected(ValueError):
    def __init__(
        self,
        reason,
        *,
        stage,
        request=None,
        trial=None,
        partial=None,
        source_error=None,
        capture_error=None,
    ):
        super().__init__(reason)
        self.stage, self.request, self.trial, self.partial = stage, request, trial, partial
        self.source_error, self.capture_error = source_error, capture_error


def _verify_sources():
    pins = ecm._verify_sources()
    path = geometry.callers.NATIVE_ROOT / "betse/science/cells.py"
    if hashlib.sha256(path.read_bytes()).hexdigest() != source.NATIVE_CELLS_SHA256:
        raise ValueError("Original environment/mask source changed")
    original = next(
        n
        for n in ast.parse(path.read_text()).body
        if isinstance(n, ast.ClassDef) and n.name == "Cells"
    )
    owned = next(
        n
        for n in ast.parse(Path(source.__file__).read_text()).body
        if isinstance(n, ast.ClassDef) and n.name == "CellsEnvironment"
    )
    for name in ("environment", "make_maskM"):
        a = next(n for n in original.body if isinstance(n, ast.FunctionDef) and n.name == name)
        b = next(n for n in owned.body if isinstance(n, ast.FunctionDef) and n.name == name)
        if ast.dump(ast.Module(body=a.body, type_ignores=[])) != ast.dump(
            ast.Module(body=b.body, type_ignores=[])
        ):
            raise ValueError("Literal environment/mask body changed")
    world = next(
        n for n in original.body if isinstance(n, ast.FunctionDef) and n.name == "make_world"
    )
    assignment = next(
        n
        for n in world.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Attribute) and t.attr == "grid_len" for t in n.targets)
    )
    literal = next(
        n for n in owned.body if isinstance(n, ast.FunctionDef) and n.name == "assign_grid_len"
    )
    if ast.dump(ast.Module(body=[assignment], type_ignores=[])) != ast.dump(
        ast.Module(body=literal.body, type_ignores=[])
    ):
        raise ValueError("Literal grid_len assignment changed")
    for module in (source, sys.modules[__name__]):
        file = Path(module.__file__).resolve()
        pins[str(file)] = hashlib.sha256(file.read_bytes()).hexdigest()
    return pins


def from_core(parent, configuration, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise EnvironmentRejected("Explicit environment source law required", stage="opt_in")
    p = parameters.from_core(
        parent,
        configuration,
        law_id=parameters.ENVIRONMENT_LAW_ID,
        projection=parameters.ENVIRONMENT,
        grid_descriptor=ecm.aliases.SELECTOR,
    )
    prefix = ecm.completion.Request(
        p,
        core.records._digest(
            dict(law=ecm.completion.LAW_ID, parameters=parameters.request_record(p))
        ),
    )
    geo = geometry.Request(
        prefix, core.records._digest(dict(law=geometry.LAW_ID, prefix=prefix.identity))
    )
    parent_request = ecm.Request(
        geo, core.records._digest(dict(law=ecm.LAW_ID, geometry=geo.identity))
    )
    request = Request(parent_request, "")
    return replace(
        request, identity=core.records._digest(dict(law=LAW_ID, ecm=parent_request.identity))
    )


def _preflight(owner):
    parent = ecm._validate(owner)
    p = parameters._authority(parent.parent.parent.parameter_owner)
    if (
        p.request.projection != parameters.ENVIRONMENT
        or p.trial.projection != parameters.ENVIRONMENT
        or p.trial.store_roster != parameters._projection(parameters.ENVIRONMENT)[3]
        or p.trial.store_lines != tuple(source.STORE_LINES)
    ):
        raise EnvironmentRejected(
            "Fresh original plot_grid_size store authority unavailable; no retrofit",
            stage="plot_grid_prerequisite",
            trial=parent.trial,
        )
    return parent


def request_record(request):
    parent = ecm._authority(request.ecm_owner)
    return dict(
        law=LAW_ID,
        parent=parent.trial.identity,
        methods=METHODS,
        parameter=parameters._authority(parent.parent.parent.parameter_owner).trial.identity,
        boundary="before first environmental makeLaplacian",
        invalidated_owners=INVALIDATED_OWNERS,
        full_make_world_Parameters_YAML_phase_physical_checkpoint=False,
    )


def from_ecm(owner, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise EnvironmentRejected("Explicit environment source law required", stage="opt_in")
    _preflight(owner)
    request = ContinuationRequest(owner, "")
    return replace(request, identity=core.records._digest(request_record(request)))


def _stop(context):
    if context.observation_error is not None:
        raise ecm._CaptureStop()


def _active_tree(tree):
    record = _TREES.get(tree)
    if record is None or type(tree) is not _TreeRuntime:
        raise EnvironmentRejected("Tree lacks process-local source issuance", stage="tree_owner")
    context = record.context
    if not context.active or not context.executing or context.thread != get_ident() or record.busy:
        raise EnvironmentRejected(
            "Raw tree call lacks active source driver", stage="source_call_unavailable"
        )
    _stop(context)
    _check(context)
    return record


def _operation(context, name, delegate, *args, **kwargs):
    _stop(context)
    if not context.active or not context.executing or context.thread != get_ident():
        raise EnvironmentRejected(
            "Helper lacks active environment driver", stage="source_call_unavailable"
        )
    _check(context)
    ecm._observe(context, name + "_enter", (args, kwargs))
    try:
        value = delegate(*args, **kwargs)
    except Exception:
        ecm._observe(context, name + "_unwind", (args, kwargs))
        raise
    if name == "tree_constructor":
        _TREES[args[0]].constructed = True
    ecm._observe(context, name + "_return", value)
    _stop(context)
    return value


class _TreeRuntime(_NATIVE_TREE):
    def __new__(cls, *args, **kwargs):
        raise EnvironmentRejected(
            "Use actual owned tree constructor driver", stage="source_call_unavailable"
        )

    def __init__(self, *args, **kwargs):
        record = _active_tree(self)
        if record.constructed:
            raise EnvironmentRejected(
                "Tree constructor already attempted", stage="tree_constructor"
            )
        record.busy = True
        try:
            _operation(record.context, "tree_constructor", _TREE_INIT, self, *args, **kwargs)
        finally:
            record.busy = False

    def query(self, *args, **kwargs):
        record = _active_tree(self)
        if not record.constructed:
            raise EnvironmentRejected(
                "Native tree constructor did not complete", stage="tree_constructor"
            )
        record.busy = True
        try:
            return _operation(record.context, "tree_query", _TREE_QUERY, self, *args, **kwargs)
        finally:
            record.busy = False

    @property
    def tree(self):
        raise EnvironmentRejected(
            "Lazy native tree-node view is unqualified", stage="tree_view_held"
        )

    def __reduce_ex__(self, protocol):
        raise TypeError("Live native tree authority cannot be serialized")

    def __getstate__(self):
        raise TypeError("Native tree checkpoint export is outside this source boundary")

    def __setstate__(self, state):
        raise TypeError("Native tree cannot be hydrated from supplied state")


def _refuse_tree_method(name):
    def refuse(self, *args, **kwargs):
        raise EnvironmentRejected(
            "Unqualified native tree method: " + name, stage="tree_method_held"
        )

    return refuse


_REFUSED_TREE_METHODS = tuple(
    name
    for name, value in vars(_NATIVE_TREE).items()
    if callable(value) and not name.startswith("_") and name != "query"
)
for _name in _REFUSED_TREE_METHODS:
    setattr(_TreeRuntime, _name, _refuse_tree_method(_name))


def _allocate_native_tree():
    return _NATIVE_TREE.__new__(_TreeRuntime)


def _new_tree(context, *args, **kwargs):
    if not context.active or not context.executing or context.thread != get_ident():
        raise EnvironmentRejected(
            "Tree construction lacks actual source driver", stage="source_call_unavailable"
        )
    _stop(context)
    _check(context)
    tree = _allocate_native_tree()
    record = SimpleNamespace(
        context=context,
        constructed=False,
        busy=False,
        tree=tree,
        view=SimpleNamespace(),
        tape=SimpleNamespace(rng=None, events=[], draws=[], locals={}),
    )
    context.trees.append(tree)
    _TREES[tree] = record
    tree.__init__(*args, **kwargs)
    return tree


def _tree_state(tree):
    values = {}
    for name in _TREE_FIELDS:
        try:
            values[name] = getattr(tree, name)
        except AttributeError:
            values[name] = ("unavailable", name)
    return values


def _snapshot(context):
    parent = context.parent
    caller = geometry.meshes._caller_without_mesh(parent.parent.parent.caller)
    caller.pop("grid_obj", None)
    caller.pop("points_tree", None)
    return core.caches.snapshot(
        dict(
            caller=caller,
            grid=dict(vars(parent.grid)),
            mesh=core.initial._public_cache(parent.parent.parent.mesh_context.kernel),
            parameters=geometry.callers._parameters(parent.parent.parent.p),
            trees=[_tree_state(tree) for tree in context.trees],
        )
    )


def _graphs(context):
    graphs = list(ecm._graphs(context.parent))
    for tree in context.trees:
        record = _TREES[tree]
        vars(record.view).clear()
        vars(record.view).update(_tree_state(tree))
        record.view.native_tree = tree
        # The stable view records actual C-field edges only; it is never a
        # parent, computation input, hydrated native tree or checkpoint.
        graphs.append(
            geometry.callers._graph(record.view, context.parent.parent.parent.p, record.tape)
        )
    return tuple(graphs)


def _bindings():
    functions = (
        *_METHODS.values(),
        _TREE_INIT,
        _TREE_QUERY,
        _GRIDDATA,
        _GAUSSIAN,
        _TreeRuntime.__new__,
        _TreeRuntime.__init__,
        _TreeRuntime.query,
        _TreeRuntime.__reduce_ex__,
        _TreeRuntime.__getstate__,
        _TreeRuntime.__setstate__,
        _TreeRuntime.tree.fget,
        _allocate_native_tree,
        _operation,
        _new_tree,
        source.tb.flatten,
        source.tb.flatten.__globals__["copy"].deepcopy,
        *(getattr(_TreeRuntime, name) for name in _REFUSED_TREE_METHODS),
        *(getattr(source.np, name) for name in _HELPERS),
    )
    return (
        _NATIVE_TREE,
        _TreeRuntime,
        _TreeRuntime.__mro__,
        source.np,
        source.tb,
        source.interp,
        *ecm.aliases._dispatch_bindings(_TreeRuntime),
        *geometry._callable_bindings(functions),
    )


def _namespace(context):
    def tree(*args, **kwargs):
        return _new_tree(context, *args, **kwargs)

    def interpolate(*args, **kwargs):
        return _operation(context, "griddata", _GRIDDATA, *args, **kwargs)

    def smooth(*args, **kwargs):
        return _operation(context, "gaussian_filter", _GAUSSIAN, *args, **kwargs)

    namespace = dict(
        source.__dict__,
        cKDTree=tree,
        interp=SimpleNamespace(griddata=interpolate),
        gaussian_filter=smooth,
    )
    return {
        name: FunctionType(fn.__code__, namespace, fn.__name__, fn.__defaults__, fn.__closure__)
        for name, fn in _METHODS.items()
    }


def _namespace_bindings(methods):
    bindings = []
    for name in METHODS:
        method = methods[name]
        namespace = method.__globals__
        bindings.extend(
            (method, method.__code__, namespace["np"], namespace["tb"], namespace["interp"])
        )
        for fn in (
            namespace["cKDTree"],
            namespace["interp"].griddata,
            namespace["gaussian_filter"],
            namespace["tb"].flatten,
            namespace["tb"].flatten.__globals__["copy"].deepcopy,
            *(getattr(namespace["np"], helper) for helper in _HELPERS),
        ):
            bindings.extend(ecm.aliases._atoms(fn))
    return tuple(bindings)


def _check(context):
    parent = context.parent
    if (
        ecm._authority(context.request.ecm_owner) is not parent
        or parent.invalid
        or parent.thread != get_ident()
        or parent.trial is not context.prior_trial
        or core.records._digest(ecm.trial_record(parent.trial)) != context.parent_signature
        or ecm._FORWARDED.get(context.request.ecm_owner) is not context.retirement
    ):
        raise ValueError("Original ECM lineage or irreversible environment claim changed")
    ecm._check(parent)
    parameter = parameters._authority(parent.parent.parent.parameter_owner)
    if (
        parameter.request.projection != parameters.ENVIRONMENT
        or parameter.trial.store_roster != parameters._projection(parameters.ENVIRONMENT)[3]
        or parameter.trial.store_lines != tuple(source.STORE_LINES)
    ):
        raise ValueError("Fresh plot-grid source projection changed")
    ecm.completion._check_binding_identity(_bindings(), context.bindings)
    if hasattr(context, "methods"):
        ecm.completion._check_binding_identity(
            _namespace_bindings(context.methods), context.namespace_bindings
        )
    if _verify_sources() != context.producers:
        raise ValueError("Environment/mask source/helper producers changed")
    for tree in context.trees:
        record = _TREES.get(tree)
        if type(tree) is not _TreeRuntime or record is None or record.context is not context:
            raise ValueError("Original issued tree identity changed")
    if context.finished:
        caller = parent.parent.parent.caller
        if (
            not context.trees
            or not any(caller.points_tree is tree for tree in context.trees)
            or caller.voronoi_centres is not caller.xypts
            or type(caller.grid_len) is not int
            or caller.grid_len != len(caller.xypts)
            or any(not _TREES[tree].constructed for tree in context.trees)
        ):
            raise ValueError("Environment/mask/tree source completion or aliases changed")


def trial_record(trial):
    return dict(
        request=trial.request_identity,
        parent=trial.parent_identity,
        before=trial.before.identity,
        cache=trial.cache.identity,
        stages=[(name, value.identity) for name, value in trial.stages],
        events=trial.events,
        work=trial.work,
        stream_before=trial.stream_before.identity,
        stream_after=trial.stream_after.identity,
        source_completed=trial.source_completed,
        failure_stage=trial.failure_stage,
        failure_type=trial.failure_type,
        failure_message=trial.failure_message,
        invalidated_owners=INVALIDATED_OWNERS,
        full_make_world_Poisson_physical_checkpoint=False,
    )


class EnvironmentOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use the owned environment/mask source entry")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live environment authority cannot be serialized")

    @property
    def cells(self):
        return _validate(self).parent.parent.parent.caller

    @property
    def trial(self):
        return _authority(self).trial


def _authority(owner):
    if type(owner) is not EnvironmentOwner or owner not in _ISSUED:
        raise EnvironmentRejected(
            "Issued environment source owner unavailable", stage="environment_owner"
        )
    return _ISSUED[owner]


def _validate(owner):
    context = _authority(owner)
    try:
        if context.invalid or context.active or context.thread != get_ident():
            raise ValueError("Invalid environment source owner")
        _check(context)
        if (
            _snapshot(context).identity != context.trial.cache.identity
            or core.records._digest(trial_record(context.trial)) != context.trial.identity
        ):
            raise ValueError("Changed sealed environment/mask source state")
        geometry.meshes._same_graphs(_graphs(context), context.graphs)
        for cache in (
            context.trial.before,
            context.trial.cache,
            *(c for _, c in context.trial.stages),
        ):
            core.caches.validate(cache)
    except Exception as error:
        context.invalid = True
        raise EnvironmentRejected(
            "Stale environment source owner",
            stage="environment_drift",
            trial=context.trial,
            request=context.request,
            source_error=error,
        ) from error
    return context


@contextmanager
def _account(context):
    with ecm._account(context):
        previous = sys.getprofile()

        def profile(frame, event, arg):
            module, name = frame.f_globals.get("__name__", ""), frame.f_code.co_name
            if event == "call" and (
                module == source.__name__
                or module == __name__
                and name in {"_new_tree", "__init__", "query", "_operation"}
            ):
                context.work.append(
                    dict(
                        sequence=len(context.work),
                        phase=context.stage,
                        layer="body" if module == source.__name__ else "helper_wrapper",
                        module=module,
                        method=frame.f_code.co_qualname,
                        entry_method=name,
                        source_file=frame.f_code.co_filename,
                        status="entered_not_success_credit",
                    )
                )
            if previous is not None:
                previous(frame, event, arg)

        sys.setprofile(profile)
        try:
            yield
        finally:
            sys.setprofile(previous)


@contextmanager
def _locals(context):
    previous = sys.getprofile()
    codes = {method.__code__: name for name, method in context.methods.items()}

    def profile(frame, event, arg):
        if event == "return" and frame.f_code in codes:
            try:
                geometry._capture_locals(context, codes[frame.f_code], frame)
            except Exception as capture:
                geometry._remember_observation_error(
                    context, capture, origin="raw_locals", raw=frame
                )
        if previous is not None:
            previous(frame, event, arg)

    sys.setprofile(profile)
    try:
        yield
    finally:
        sys.setprofile(previous)


def prepare_continuation(request, *, _work=None):
    if type(request) is not ContinuationRequest:
        raise EnvironmentRejected("Typed retained ECM owner required", stage="request_owner")
    if _work is None:
        work = SimpleNamespace(stage="environment", work=[])
        with _account(work):
            return prepare_continuation(request, _work=work)
    parent = ecm._authority(request.ecm_owner)
    context = SimpleNamespace(
        request=request,
        parent=parent,
        prior_trial=parent.trial,
        retirement=object(),
        thread=get_ident(),
        invalid=False,
        active=False,
        executing=False,
        finished=False,
        trees=[],
        events=[],
        locals={},
        stages=[],
        stage="preflight",
        observation_error=None,
        observation_errors=(),
        observation_origin=None,
        observation_raw=None,
        prefix=_work,
    )
    error = None
    with _LOCK:
        try:
            if (
                _preflight(request.ecm_owner) is not parent
                or core.records._digest(request_record(request)) != request.identity
            ):
                raise ValueError("Changed retained environment request")
            context.producers, context.bindings = _verify_sources(), _bindings()
            context.parent_signature = core.records._digest(ecm.trial_record(parent.trial))
            context.before = _snapshot(context)
            context.stream_before = core.initial._rng_stream(parent.parent.parent.rng)
            context.stage = "retirement"
            ecm._claim_for_environment(
                request.ecm_owner, expected=parent, transition=context.retirement
            )
            context.stage = "namespace"
            context.methods = _namespace(context)
            context.namespace_bindings = _namespace_bindings(context.methods)
            context.active = True
            with _locals(context):
                for name in METHODS:
                    context.stage = _work.stage = name
                    _check(context)
                    context.executing = True
                    try:
                        context.methods[name](parent.parent.parent.caller, parent.parent.parent.p)
                    finally:
                        context.executing = False
                    _stop(context)
                    try:
                        context.stages.append((name, _snapshot(context)))
                    except Exception as capture:
                        geometry._remember_observation_error(
                            context,
                            capture,
                            origin="stage_snapshot",
                            raw=parent.parent.parent.caller,
                        )
                        raise ecm._CaptureStop() from capture
                    _check(context)
            context.finished = True
            context.stage = "source_checks"
            _check(context)
        except Exception as failure:
            if not isinstance(failure, ecm._CaptureStop):
                error = failure
        finally:
            context.active = context.executing = False
    partial = dict(
        context=context,
        parent_trial=context.prior_trial,
        caller=parent.parent.parent.caller,
        parameters=parent.parent.parent.p,
        mesh=parent.parent.parent.mesh_context.kernel,
        grid=parent.grid,
        trees=context.trees,
        rng=parent.parent.parent.rng,
        stage=context.stage,
        events=context.events,
        raw_locals=context.locals,
        stages=context.stages,
        work=_work.work,
        observation_errors=context.observation_errors,
        observation_raw=context.observation_raw,
        ecm_consumed=request.ecm_owner in ecm._FORWARDED,
        usable_environment_child_available=False,
    )
    if context.observation_error is not None:
        raise EnvironmentRejected(
            "Environment observation failed",
            stage="capture",
            request=request,
            partial=partial,
            source_error=error,
            capture_error=context.observation_error,
        ) from (error if error is not None else context.observation_error)
    try:
        trial = Trial(
            request.identity,
            context.prior_trial.identity,
            context.before,
            _snapshot(context),
            tuple(context.stages),
            tuple(name for name, _ in context.events),
            tuple(dict(e) for e in _work.work),
            context.stream_before,
            core.initial._rng_stream(parent.parent.parent.rng),
            error is None,
            None if error is None else context.stage,
            None if error is None else type(error).__name__,
            None if error is None else str(error),
            "",
        )
        trial = replace(trial, identity=core.records._digest(trial_record(trial)))
    except Exception as capture:
        raise EnvironmentRejected(
            "Environment trial sealing failed",
            stage="capture",
            request=request,
            partial=partial,
            source_error=error,
            capture_error=capture,
        ) from (error if error is not None else capture)
    if error is not None:
        raise EnvironmentRejected(
            "Original environment source attempt failed",
            stage=context.stage,
            request=request,
            trial=trial,
            partial=partial,
            source_error=error,
        ) from error
    try:
        context.trial = trial
        _check(context)
        context.graphs = _graphs(context)
        child = object.__new__(EnvironmentOwner)
        _ISSUED[child] = context
        return child
    except Exception as capture:
        raise EnvironmentRejected(
            "Environment child issuance failed",
            stage="issuance",
            request=request,
            trial=trial,
            partial=partial,
            capture_error=capture,
        ) from capture


def prepare(request):
    if (
        type(request) is not Request
        or core.records._digest(dict(law=LAW_ID, ecm=request.ecm_request.identity))
        != request.identity
    ):
        raise EnvironmentRejected("Typed fresh environment prefix required", stage="request_owner")
    context = SimpleNamespace(stage="ecm_prefix", work=[], parent=None)
    try:
        with _account(context):
            context.parent = ecm.prepare(request.ecm_request)
            return prepare_continuation(from_ecm(context.parent, law_id=LAW_ID), _work=context)
    except Exception as error:
        raise EnvironmentRejected(
            "Owned environment prefix failed",
            stage=context.stage,
            request=request,
            partial=dict(parent=context.parent, prefix=context, work=context.work),
            source_error=error,
        ) from error


def require_Poisson(owner, *, phase=None):
    context = _validate(owner)
    raise EnvironmentRejected(
        "Environmental makeLaplacian/full make_world/phase authority remains held",
        stage="Poisson_held",
        trial=context.trial,
        partial=dict(
            invalidated_owners=INVALIDATED_OWNERS,
            supplied_phase=phase,
            physical_checkpoint_general_DEC_admitted=False,
        ),
    )
