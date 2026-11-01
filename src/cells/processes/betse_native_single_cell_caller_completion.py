"""Owned normalized-parameter -> same single-cell caller prefix through cell_index.

The four original tail aliases and cell_index act on the actual retained image,
caller, parameter, mesh and RNG objects. Legacy meshes lacking the fresh ordered
height provenance refuse. Stop before cellVerts/environment; no physical,
general DEC, full Parameters/SimPhase/package or checkpoint admission follows.
"""

import hashlib
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import SimpleNamespace
from weakref import WeakKeyDictionary, WeakSet

from cells.processes import betse_native_single_cell_in_caller_mesh as meshes
from cells.processes import betse_native_single_cell_parameters as parameters

core, callers, images = meshes.core, meshes.callers, meshes.images
LAW_ID = "betse_owned_single_cell_height_caller_tail_cell_index@1"
INVALIDATED_OWNERS = core.INVALIDATED_OWNERS
HELD_UNQUALIFIED_SOURCE_STAGE = True
_ISSUED = WeakKeyDictionary()
_FORWARDED = WeakKeyDictionary()
_BUSY = WeakSet()
_LOCK = RLock()
_TAIL_ALIASES = images.source.CallerTail.make_voronoi_mesh_aliases
_CELL_INDEX = images.source.CallerTail.cell_index


@dataclass(frozen=True, slots=True)
class Request:
    parameter_request: parameters.Request
    identity: str


@dataclass(frozen=True, slots=True)
class TailRequest:
    mesh_owner: meshes.MeshOwner
    identity: str


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    mesh_parent_identity: str
    parameter_identity: str
    before_cache: object
    cache: object
    ordering: tuple
    work: tuple
    prefix_identity: str | None
    stream_before: object
    stream_after: object
    source_completed: bool
    failure_stage: str | None
    failure_type: str | None
    failure_message: str | None
    identity: str


class CompletionRejected(ValueError):
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
    pins = parameters._verify_sources()
    pins.update(meshes._verify_sources())
    for module in (parameters, meshes):
        path = Path(module.__file__).resolve()
        pins[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    pins[str(Path(__file__).resolve())] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return pins


def _bindings():
    methods = (_TAIL_ALIASES, _CELL_INDEX, _caller, _image, _mesh)
    return tuple(part for method in methods for part in (method, method.__code__))


def from_core(parent, configuration, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise CompletionRejected("Explicit caller-prefix source law required", stage="opt_in")
    param = parameters.from_core(parent, configuration, law_id=parameters.LAW_ID)
    value = Request(param, "")
    return replace(
        value,
        identity=core.records._digest(
            dict(law=LAW_ID, parameters=parameters.request_record(param))
        ),
    )


def _preflight(owner):
    context = meshes._validate_owner(owner)
    caller = context.parent_caller
    parameter_owner = caller.get("parameter_owner")
    if parameter_owner is None:
        raise CompletionRejected(
            "Fresh ordered cell-height parameter provenance is unavailable",
            stage="owned_cell_height_unavailable",
            trial=context.trial,
            partial=dict(
                caller=context.caller, mesh=context.kernel, legacy_parameters=caller["parameters"]
            ),
        )
    param = parameters._validate_binding(parameter_owner, caller["request"], caller["parameters"])
    if context.caller.mesh is not context.kernel or context.parent_image["rng"] is not context.rng:
        raise CompletionRejected(
            "Actual continuing caller/mesh/image/RNG chain changed", stage="parent_identity"
        )
    return context, param, parameter_owner


def tail_request_record(request):
    context = meshes._authority(request.mesh_owner)
    owner = context.parent_caller.get("parameter_owner")
    param = parameters._authority(owner)
    return dict(
        law=LAW_ID,
        mesh_trial=context.trial.identity,
        parameter_trial=param.trial.identity,
        caller_trial=context.parent_caller["trial"].identity,
        image_trial=context.parent_image["trial"].identity,
        boundary="make_voronoi953-960 -> cell_index963-976; stop before cellVerts",
        full_Parameters_phase_package_physical_checkpoint=False,
        invalidated_owners=INVALIDATED_OWNERS,
    )


def from_mesh(owner, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise CompletionRejected("Explicit caller-tail law required", stage="opt_in")
    _preflight(owner)
    value = TailRequest(owner, "")
    return replace(value, identity=core.records._digest(tail_request_record(value)))


def _snapshot(context):
    return core.caches.snapshot(
        dict(
            caller=meshes._caller_without_mesh(context.caller),
            mesh=core.initial._public_cache(context.mesh_context.kernel),
            parameters=callers._parameters(context.p),
        )
    )


def trial_record(trial):
    return dict(
        request=trial.request_identity,
        mesh_parent=trial.mesh_parent_identity,
        parameter_parent=trial.parameter_identity,
        before=trial.before_cache.identity,
        cache=trial.cache.identity,
        ordering=trial.ordering,
        work=trial.work,
        prefix_identity=trial.prefix_identity,
        stream_before=trial.stream_before.identity,
        stream_after=trial.stream_after.identity,
        source_completed=trial.source_completed,
        failure_stage=trial.failure_stage,
        failure_type=trial.failure_type,
        failure_message=trial.failure_message,
        normalized_configuration_only=True,
        physical_checkpoint_general_DEC_admitted=False,
        invalidated_owners=INVALIDATED_OWNERS,
    )


class CallerOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use the owned parameter/caller prefix")

    def __reduce_ex__(self, protocol):
        raise TypeError("Completed source caller authority cannot be serialized")

    @property
    def cells(self):
        return _validate(self).caller

    @property
    def parameters(self):
        return _validate(self).p

    @property
    def trial(self):
        return _authority(self).trial


def _authority(owner):
    if type(owner) is not CallerOwner or owner not in _ISSUED:
        raise CompletionRejected(
            "Issued completed caller authority unavailable", stage="caller_owner"
        )
    return _ISSUED[owner]


def _check_binding_identity(current, original):
    """Caller bindings contain pairs; compare the retained callable/code atoms."""

    def atoms(value):
        for part in value:
            if type(part) is tuple:
                yield from atoms(part)
            else:
                yield part

    actual, retained = tuple(atoms(current)), tuple(atoms(original))
    if len(actual) != len(retained) or any(
        a is not b for a, b in zip(actual, retained, strict=True)
    ):
        raise ValueError("Original mesh/caller callable or code identity changed")


def _check_runtime_authority(context):
    # The mesh epoch stays consumed. These checks neither reopen its handle nor
    # compare legitimate post-tail caller fields to an earlier numeric cache.
    mesh = context.mesh_context
    _check_binding_identity(meshes._bindings(), context.mesh_bindings)
    _check_binding_identity(callers._bindings(context.caller), context.caller_bindings)
    if (
        mesh.observer is not context.observer
        or mesh.kernel._cells_observer is not context.observer
        or mesh.kernel._cells_rng is not context.rng_wrapper
        or mesh.kernel._cells_rng.observer is not context.observer
    ):
        raise ValueError("Original kernel/RNG-wrapper observer associations changed")


def _validate(owner):
    context = _authority(owner)
    if owner in _FORWARDED:
        raise CompletionRejected(
            "Caller epoch was consumed by an initial-geometry attempt",
            stage="caller_epoch_consumed",
            request=context.request,
            trial=context.trial,
        )
    try:
        if (
            context.invalid
            or context.thread != get_ident()
            or _verify_sources() != context.producers
        ):
            raise ValueError("Changed completed caller source authority")
        mesh = context.mesh_context
        _check_runtime_authority(context)
        if (
            meshes._authority(context.request.mesh_owner) is not mesh
            or mesh.invalid
            or meshes._FORWARDED.get(context.request.mesh_owner) is not context.retirement
            or context.caller is not mesh.caller
            or context.caller.mesh is not mesh.kernel
            or mesh.kernel._cells_rng.rng is not context.rng
            or mesh.rng is not context.rng
            or mesh.parent_caller["parameters"] is not context.p
            or mesh.parent_caller["invalid"]
            or mesh.parent_image["invalid"]
            or callers._retirement_token(mesh.parent_image["request"].caller) is not mesh.retirement
        ):
            raise ValueError("Changed original caller/mesh/RNG/parameter identity or retirement")
        if core.records._digest(tail_request_record(context.request)) != context.request.identity:
            raise ValueError("Changed original requested parent identities")
        if _parent_records(mesh) != context.parent_records:
            raise ValueError("Changed retained original source parent trials")
        parameters._validate_binding(
            context.parameter_owner, mesh.parent_caller["request"], context.p
        )
        if (
            _bindings() != context.bindings
            or core.records._digest(trial_record(context.trial)) != context.trial.identity
        ):
            raise ValueError("Changed caller-tail method binding or sealed trial")
        if _snapshot(context).identity != context.trial.cache.identity:
            raise ValueError("Changed completed caller/mesh/parameter cache")
        if core.initial._rng_stream(context.rng).identity != context.trial.stream_after.identity:
            raise ValueError("Changed continuing source RNG epoch")
        meshes._same_graphs(meshes._graphs(mesh), context.graphs)
        for cache in (context.trial.before_cache, context.trial.cache):
            core.caches.validate(cache)
    except Exception as error:
        context.invalid = True
        raise CompletionRejected(
            "Stale completed caller source refused",
            stage="caller_drift",
            request=context.request,
            trial=context.trial,
            source_error=error,
        ) from error
    return context


def _claim_for_initial_geometry(owner, *, expected, transition):
    context = _validate(owner)
    if context is not expected or transition is None:
        raise CompletionRejected(
            "Initial-geometry caller issuance changed", stage="caller_identity"
        )
    _FORWARDED[owner] = transition
    return context


def _parent_records(mesh):
    return tuple(
        core.records._digest(record)
        for record in (
            meshes.trial_record(mesh.trial),
            callers.trial_record(mesh.parent_caller["trial"]),
            images.trial_record(mesh.parent_image["trial"]),
        )
    )


def prepare_tail(request, *, _prefix=None):
    if type(request) is not TailRequest:
        raise CompletionRejected(
            "Typed actual-mesh caller-tail request required", stage="request_owner"
        )
    parent = meshes._authority(request.mesh_owner)
    context = SimpleNamespace(
        request=request,
        mesh_context=parent,
        caller=parent.caller,
        rng=parent.rng,
        p=parent.parent_caller["parameters"],
        parameter_owner=parent.parent_caller.get("parameter_owner"),
        retirement=object(),
        thread=get_ident(),
        invalid=False,
        stage="preflight",
        order=[],
        bindings=_bindings(),
        producers=_verify_sources(),
        before=None,
        stream_before=None,
        parameter_trial=None,
        prefix=_prefix,
    )
    error = None
    with _LOCK:
        if context.caller in _BUSY:
            raise CompletionRejected(
                "Caller-tail attempt is reentrant", stage="caller_reentrant", request=request
            )
        _BUSY.add(context.caller)
        try:
            mesh, param, owner = _preflight(request.mesh_owner)
            if (
                mesh is not parent
                or param.p is not context.p
                or owner is not context.parameter_owner
            ):
                raise ValueError("Caller/parameter preflight issuance changed")
            context.parameter_trial = param.trial
            context.parent_records = _parent_records(parent)
            context.mesh_bindings = parent.bindings
            context.caller_bindings = parent.parent_caller["bindings"]
            context.observer = parent.observer
            context.rng_wrapper = parent.kernel._cells_rng
            _check_runtime_authority(context)
            if core.records._digest(tail_request_record(request)) != request.identity:
                raise ValueError("Changed caller-tail request")
            context.before = _snapshot(context)
            context.kernel_before = core.caches.snapshot(core.initial._public_cache(parent.kernel))
            context.caller_before = core.caches.snapshot(
                meshes._caller_without_mesh(context.caller)
            )
            context.stream_before = core.initial._rng_stream(context.rng)
            context.stage = "retirement"
            meshes._claim_for_caller_tail(
                request.mesh_owner, expected=parent, transition=context.retirement
            )
            context.order.append("mesh_parent_retired")
            context.stage = "tail_aliases"
            _TAIL_ALIASES(context.caller, parent.parent_image["tape"].mask)
            context.order.append("tail_aliases_return")
            context.stage = "cell_index"
            _CELL_INDEX(context.caller, context.p)
            context.order.append("cell_index_return")
            context.stage = "source_checks"
            mask = parent.parent_image["tape"].mask
            if (
                context.caller.ecm_verts is not parent.kernel.vcell_verts
                or context.caller.cluster_mask is not mask.clipping_matrix
                or context.caller.msize != mask.msize
                or context.caller.ecm_verts_unique is not parent.kernel.vor_verts
                or context.caller.cell_centres is not parent.kernel.vor_cents
                or core.initial._rng_stream(context.rng).identity != context.stream_before.identity
                or core.caches.snapshot(core.initial._public_cache(parent.kernel)).identity
                != context.kernel_before.identity
                or _bindings() != context.bindings
                or _verify_sources() != context.producers
            ):
                raise ValueError("Original tail aliases/source/RNG correspondence changed")
            fields = {
                "ecm_verts",
                "cluster_mask",
                "msize",
                "ecm_verts_unique",
                "cell_centres",
                "cell_vol",
            }
            if (
                core.caches.snapshot(
                    {
                        k: v
                        for k, v in meshes._caller_without_mesh(context.caller).items()
                        if k not in fields
                    }
                ).identity
                != context.caller_before.identity
            ):
                raise ValueError("Tail changed unrelated original caller attributes")
            parameters._validate_binding(owner, parent.parent_caller["request"], context.p)
            _check_runtime_authority(context)
        except Exception as failure:
            error = failure
        finally:
            _BUSY.discard(context.caller)
    partial = dict(
        context=context,
        caller=context.caller,
        parameters=context.p,
        mesh=parent.kernel,
        rng=context.rng,
        parameter_owner=context.parameter_owner,
        mesh_parent_trial=parent.trial,
        parameter_trial=context.parameter_trial,
        source_stage=context.stage,
        ordering=context.order,
        before=context.before,
        mesh_epoch_consumed=request.mesh_owner in meshes._FORWARDED,
        usable_caller_child_available=False,
    )
    try:
        if context.before is None or context.stream_before is None:
            raise ValueError("Caller-tail failed before a complete source trial")
        final = _snapshot(context)
        trial = Trial(
            request.identity,
            parent.trial.identity,
            context.parameter_trial.identity,
            context.before,
            final,
            tuple(context.order),
            () if _prefix is None else tuple(dict(w) for w in _prefix.work),
            None if _prefix is None else _prefix.request.identity,
            context.stream_before,
            core.initial._rng_stream(context.rng),
            error is None,
            None if error is None else context.stage,
            None if error is None else type(error).__name__,
            None if error is None else str(error),
            "",
        )
        trial = replace(trial, identity=core.records._digest(trial_record(trial)))
    except Exception as capture:
        raise CompletionRejected(
            "Caller-tail source sealing failed",
            stage="capture",
            request=request,
            partial=partial,
            source_error=error,
            capture_error=capture,
        ) from (error if error is not None else capture)
    if error is not None:
        raise CompletionRejected(
            "Original caller-tail source failed",
            stage=context.stage,
            request=request,
            trial=trial,
            partial=partial,
            source_error=error,
        ) from error
    try:
        context.trial = trial
        _check_runtime_authority(context)
        context.graphs = meshes._graphs(parent)
        _check_runtime_authority(context)
        child = object.__new__(CallerOwner)
        _ISSUED[child] = context
        return child
    except Exception as capture:
        raise CompletionRejected(
            "Caller-tail child issuance failed",
            stage="issuance",
            request=request,
            trial=trial,
            partial=partial,
            capture_error=capture,
        ) from capture


def _caller(request, owner):
    parent = callers.from_core_request(request.core_request, law_id=callers.LAW_ID)
    return callers.prepare(parent, _parameter_owner=owner)


def _image(owner):
    return images.prepare(images.from_caller(owner, law_id=images.LAW_ID))


def _mesh(owner):
    return meshes.prepare(meshes.from_image(owner, law_id=meshes.LAW_ID))


@contextmanager
def _account_prefix(context, *, _source_modules=(), _entry_names=()):
    """Primary, non-additive entry-attempt ledger, including failed body entries.

    Entry records do not assert method success. Original source failures and
    partial trials retain outcomes; child work ledgers are supplemental views.
    """
    previous = sys.getprofile()
    modules = {
        module.__name__
        for module in (
            parameters,
            parameters.source,
            callers,
            callers.source,
            images,
            images.source,
            meshes,
            core,
            core.initial,
            core.initial.source,
            core.lifecycle,
            core.lifecycle.source,
            core.initial.image_stage,
            core.initial.image_stage.lattice,
        )
    }
    bodies = {
        module.__name__
        for module in (
            parameters.source,
            callers.source,
            images.source,
            core.initial.source,
            core.lifecycle.source,
        )
    }
    modules.update(module.__name__ for module in _source_modules)
    bodies.update(module.__name__ for module in _source_modules)
    names = {
        "prepare",
        "prepare_parameters",
        "generate",
        "validate_state",
        "validate_prelude",
        "validate_request",
        "from_initial",
        "from_image_prelude",
        "__init__",
        "_make_cell_lattice",
        "initialize_source_stores",
        "random",
        "rand",
        "invoke",
        "cell_index",
        "make_voronoi_mesh_aliases",
        "_authenticate",
        "_execute",
        "guarded",
    }
    names.update(meshes.GUARDED_NATIVE_METHODS)
    names.update(_entry_names)

    # These seven Cells inspection sites repeatedly check callable bindings;
    # none executes the native descriptor factory/getter or a numerical body.
    # Retain exact counts per site/phase/execution without spending one ordered
    # source row per inspected atom. All other entries keep their original order
    # and the existing row allowance. Native and child ledgers remain separate.
    metadata_sites = {
        "_atoms",
        "_atoms.<locals>.visit",
        "_module_bindings.<locals>.<genexpr>",
        "_check_modules.<locals>.<genexpr>",
        "_check_modules.<locals>.<genexpr>.<genexpr>",
        "validate.<locals>.<genexpr>",
        "_bindings.<locals>.<genexpr>",
    }
    metadata_rows = {}

    def execution(frame):
        ancestor = frame
        for _ in range(256):
            if ancestor is None:
                break
            module = ancestor.f_globals.get("__name__")
            name = ancestor.f_code.co_name
            if module == meshes.__name__ and name == "_execute":
                return getattr(ancestor.f_locals.get("context"), "phase", "unknown")
            if (
                module == callers.__name__
                and name == "_validate_request"
                or module
                in {
                    core.__name__,
                    core.initial.__name__,
                    core.initial.image_stage.__name__,
                    core.initial.image_stage.lattice.__name__,
                }
                and name
                in {"validate_request", "validate_state", "validate_prelude", "from_initial"}
            ):
                return "authentication"
            ancestor = ancestor.f_back
        return "source"

    def profile(frame, event, arg):
        module = frame.f_globals.get("__name__")
        name = frame.f_code.co_name
        if event == "call" and module in modules and (module in bodies or name in names):
            execution_kind = execution(frame)
            metadata = (
                module == "cells.processes.betse_native_single_cell_grid_alias"
                and frame.f_code.co_qualname in metadata_sites
            )
            key = (
                module,
                frame.f_code.co_qualname,
                frame.f_code.co_filename,
                frame.f_code.co_firstlineno,
                context.stage,
                execution_kind,
            )
            layer = "body" if module in bodies else "driver"
            if layer != "body" and (
                name in {"invoke", "guarded"} or frame.f_code.co_qualname.startswith("_Runtime.")
            ):
                layer = "wrapper"
            if metadata and key in metadata_rows:
                metadata_rows[key]["attempts"] += 1
            else:
                if len(context.work) >= 100000:
                    raise ValueError("Bounded prefix work ledger exhausted")
                row = dict(
                    sequence=len(context.work),
                    status="entered_not_success_credit",
                    phase=context.stage,
                    execution=execution_kind,
                    layer=layer,
                    module=module,
                    method=frame.f_code.co_qualname,
                    entry_method=frame.f_locals.get("name", name)
                    if name in {"invoke", "guarded"}
                    else name,
                    source_file=frame.f_code.co_filename,
                    line=frame.f_code.co_firstlineno,
                )
                if metadata:
                    row.update(
                        layer="metadata_aggregate",
                        attempts=1,
                        aggregation="exact count; repeated metadata entry order not retained",
                        native_body_credit=False,
                    )
                    metadata_rows[key] = row
                context.work.append(row)
        if previous is not None:
            previous(frame, event, arg)

    sys.setprofile(profile)
    try:
        yield
    finally:
        sys.setprofile(previous)


def prepare(request):
    if (
        type(request) is not Request
        or core.records._digest(
            dict(law=LAW_ID, parameters=parameters.request_record(request.parameter_request))
        )
        != request.identity
    ):
        raise CompletionRejected(
            "Typed unchanged full-prefix request required", stage="request_owner", request=request
        )
    context = SimpleNamespace(
        request=request,
        stage="parameters",
        work=[],
        parameter=None,
        caller=None,
        image=None,
        mesh=None,
    )
    try:
        with _account_prefix(context):
            context.parameter = parameters.prepare_parameters(request.parameter_request)
            context.stage = "caller"
            context.caller = _caller(request.parameter_request, context.parameter)
            context.stage = "image"
            context.image = _image(context.caller)
            context.stage = "mesh"
            context.mesh = _mesh(context.image)
            context.stage = "caller_tail"
            child = prepare_tail(from_mesh(context.mesh, law_id=LAW_ID), _prefix=context)
        return child
    except Exception as error:
        raise CompletionRejected(
            "Owned source prefix failed",
            stage=context.stage,
            request=request,
            partial=dict(
                prefix=context,
                work=context.work,
                parents=dict(
                    parameter=context.parameter,
                    caller=context.caller,
                    image=context.image,
                    mesh=context.mesh,
                ),
            ),
            source_error=error,
        ) from error


def require_cellVerts(owner, *, phase=None):
    context = _validate(owner)
    raise CompletionRejected(
        "cellVerts/environment/full phase continuation remains unavailable",
        stage="cellVerts_environment_held",
        trial=context.trial,
        partial=dict(
            supplied_phase=phase,
            invalidated_owners=INVALIDATED_OWNERS,
            physical_checkpoint_general_DEC_admitted=False,
        ),
    )
