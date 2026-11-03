"""Prepared original lifecycle on the actual issued SEED constructor mesh.

No adoption pin or release is implied. Native bodies retain their original
CodeTypes, caller/mesh/image/parameter identity and constructor-final MT. The
boundary ends at lifecycle return, before all four caller alias assignments.
"""

import ast
import dis
import hashlib
import os
import sys
import warnings
from contextlib import contextmanager
from dataclasses import dataclass, replace
from inspect import CO_GENERATOR
from pathlib import Path
from threading import RLock, get_ident
from types import CodeType, FrameType, FunctionType, MappingProxyType, ModuleType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_seed_voronoi_lifecycle_source as source
from cells.processes import betse_native_seed_voronoi_mesh as previous

MODE = "fresh_world_seed_same_mesh_original_lifecycle"
LAW_ID = "betse_same_seed_phase_observed_mesh_lifecycle@1"
RELEASE = "CELLS_NATIVE_SEED_VORONOI_LIFECYCLE_RELEASED"
SOURCE_SHA256 = "442b2f4eaf3827874bf32dfa6bc9faa0f44285bc056ccce0186ffad455bdee70"
PARENT_SOURCE_SHA256 = "c73fd24847158223373c6d77783b8e27857bede8ff59b3b6094ceba20fa2f23f"
PARENT_REVIEW_SHA256 = "a4fd24cebcb04930a7d4d884a18b0e2368020510d7d57e6be72f4b213cad1bbb"
PARENT_MODULE = "cells.processes.betse_native_seed_voronoi_mesh"
DISPATCH_LABEL = "Cells.make_voronoi"
ROOT, WRAPPER = "Cells.make_voronoi.lifecycle", previous.WRAPPER
MAX_WORK = previous.MAX_WORK
MAX_PROTOCOL_HISTORY = 256
SINGLE_METHODS = (
    "area",
    "cc_sort_inds",
    "circumc",
    "create_core_operators",
    "create_mappings",
    "create_tri_map",
    "create_tri_mesh",
    "define_vorverts",
    "init_mesh",
    "poly_centroid",
    "pre_mesh",
    "process_primary_edges",
    "process_voredges",
    "trimesh_core_calcs",
)
MULTI_METHODS = (
    "area",
    "cc_sort_inds",
    "circumc",
    "clip_and_refine",
    "clip_to_curve",
    "create_core_operators",
    "create_mappings",
    "create_tri_map",
    "create_tri_mesh",
    "define_vorverts",
    "merge_tri_mesh",
    "mesh_quality_calc",
    "poly_centroid",
    "pre_mesh",
    "process_primary_edges",
    "process_voredges",
    "quad_circumc",
    "refine_mesh",
    "sanity_check",
    "search_point_cloud",
    "trimesh_core_calcs",
)
# Conditional source-method overapproximation. Unavailable lazy helper modules
# refuse before native entry; a substituted module is never imported as authority.
NATIVE_PINS = {
    "betse.science.cells": "be38678a4f0bd084044fe7d952d74a4550003ce9701f5d073d1f124ba6daeaf2",
    "betse.science.math.mesh": "fd0dc21e1f82aa71e19a487f3b91c4b5258f02aec4c69f22c2bf3c419e425c38",
    "betse.exceptions": "c78612e009270a8d054ea6c52e9e7014ce22e0131a929530e7c3ddc318765971",
    "betse.util.math.geometry.polygon.geopoly": (
        "8a031ba303e024f13964f8bd2f225b72128f27574c10ff84a21e100a67727f83"
    ),
    "betse.util.math.geometry.polygon.geopolyconvex": (
        "7c02760027be9913dc9e1e4c76352be942a6b2628f8c3b19098b21ca6b594199"
    ),
    "betse.util.math.geometry.geopoint": (
        "e768b5ebcffd95eea6ce0cc35a8d0f5b6e7ccda6299b77c9e0a80edf1b548a41"
    ),
    "betse.util.math.mathoper": "375d44263e2b8fbda7f99ee0b63c4f62e2090dc5e8089ece8447df6f8bac4854",
    "betse.util.type.iterable.iterables": (
        "d5568a6a25f1d6c2a6dd0f3babac4eec1b860ee931531c1955dcd8f390ae5403"
    ),
    "betse.lib.numpy.nparray": "f7c1362a5c6daf545b6a516e0ce06fe53242c13abd05a5f2520226b7dd222889",
    "betse.lib.numpy.npscalar": "02080a869ae0cda8e84851c3d6e5f8d95b88a90ea3cd122c33a83c000da7af12",
    "betse.util.type.types": "9b8c83555b06a18bfb252d236c95c0d625699237e5c5cc671c085d282fc2c089",
    "betse.util.type.numeric.floats": (
        "4bc44d057523606dbdea4be47d9b42af5be748d0d4482832bf2695c3632cdb84"
    ),
    "betse.util.type.cls.classes": (
        "518cf58a45b621fae925595c3e3ed48dcba8c1f71df6718b10ffbe253710aab4"
    ),
    "betse.util.type.iterable.generators": (
        "f6acfb290e2b732e04f81c1a917c2c29915ed568ea49f81b6bfd9228cee3dd01"
    ),
    "betse.util.type.iterable.itertest": (
        "b52190a6589231f4055e018fd9de36291e4c26fe277b7db738f1122eca51be2d"
    ),
    "betse.util.type.iterable.mapping.mappings": (
        "37be12540d4f51b0ec62d17a7f321d6b61e2fdbaf030b7528c192099a42a57cf"
    ),
    "betse.util.type.typehints": "fd1ac6d86cae62d2d4ea22afa2a7f87b91a35aa0763b2e8fba89a567c8ebfc39",
    "betse.util.io.log.logs": "73195e9d13a76ad5982be04e13847d2abc76819079d1caddc6122a23d89920f2",
}
NUMPY_HELPERS = (
    "arange",
    "arctan2",
    "argsort",
    "array",
    "asarray",
    "delete",
    "hstack",
    "intersect1d",
    "linalg.norm",
    "linalg.pinv",
    "linspace",
    "mean",
    "ones",
    "roll",
    "round",
    "setdiff1d",
    "sign",
    "sqrt",
    "sum",
    "unique",
    "vstack",
    "zeros",
)
GLOBAL_HELPERS = (
    "Delaunay",
    "cKDTree",
    "array",
    "clip_counterclockwise",
    "det1d",
    "is_convex",
    "is_cyclic_quad",
    "orient_counterclockwise",
)
MATH_HELPERS = ("math.atan2",)
_REQUESTS, _CONSUMED, _RETIRED, _ISSUED = (WeakKeyDictionary() for _ in range(4))
_FORWARDED = WeakKeyDictionary()
_ACTIVE, _LOCK = [], RLock()
_LITERAL_FILE, _PARENT_FILE = Path(source.__file__), Path(previous.__file__)
_LITERAL_CLASS = source.VoronoiLifecycle
_LITERAL_METHODS = tuple(vars(_LITERAL_CLASS)[name] for name in ("single", "multi_nonSVG"))
_PIN_ITEMS = tuple(NATIVE_PINS.items())


class LifecycleRejected(previous.MeshConstructionRejected):
    pass


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    constructor_owner: object
    parent_identity: str
    witness: previous.ConstructorCallWitness
    source_identity: str
    mode: str
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("Actual constructor lineage is process-local")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    constructor_trial_identity: str
    witness_identity: str
    before: object
    cache: object
    stream_before: object
    stream_after: object
    work: tuple
    warnings: tuple
    source_completed: bool
    failure_stage: str | None
    source_failure_type: str | None
    capture_failure_type: str | None
    identity: str
    helper_cache: object = None


def _digest(value):
    return previous._digest(value)


def _native_files():
    if tuple(NATIVE_PINS.items()) != _PIN_ITEMS:
        raise ValueError("Exact original lifecycle/helper pin roster required")
    root = previous.image.prefix.aliases.NATIVE
    for module, expected in _PIN_ITEMS:
        path = root / (module.replace(".", "/") + ".py")
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Original source/helper bytes changed: " + module)
    return root


def _nodes(path, cls):
    tree = ast.parse(path.read_bytes())
    value = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    return {n.name: n for n in value.body if isinstance(n, ast.FunctionDef)}


def source_plan():
    root = _native_files()
    native = _nodes(root / "betse/science/cells.py", "Cells")["make_voronoi"]
    branch = previous._body(native)[5]
    selected = (branch.body[1], branch.orelse[0].orelse[1])
    copied = _nodes(_LITERAL_FILE, "VoronoiLifecycle")
    for name, statement in zip(("single", "multi_nonSVG"), selected, strict=True):
        if ast.dump(ast.Module(body=[statement], type_ignores=[]), include_attributes=False) != (
            ast.dump(
                ast.Module(body=previous._body(copied[name]), type_ignores=[]),
                include_attributes=False,
            )
        ):
            raise ValueError("Literal original lifecycle statement changed: " + name)
    methods = _nodes(root / "betse/science/math/mesh.py", "DECMesh")
    # Keep all data-dependent recursion. Only caller-known absent smoothing,
    # absent aux operators and single-cell merge/bad-vert cases are excluded.
    edges = {
        name: tuple(
            sorted(
                {
                    n.func.attr
                    for n in ast.walk(methods[name])
                    if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and isinstance(n.func.value, ast.Name)
                    and n.func.value.id == "self"
                    and n.func.attr in MULTI_METHODS
                }
            )
        )
        for name in sorted(set(SINGLE_METHODS) | set(MULTI_METHODS))
    }
    return dict(
        law=LAW_ID,
        mode=MODE,
        source_pin=SOURCE_SHA256,
        parent_pin=PARENT_SOURCE_SHA256,
        parent_review=PARENT_REVIEW_SHA256,
        parent=PARENT_MODULE,
        native_source=dict(NATIVE_PINS),
        branches=("single", "multi_nonSVG"),
        branch_authority="actual original constructor CALL",
        caller_descriptors_repeated=False,
        single_methods=SINGLE_METHODS,
        nonSVG_methods=MULTI_METHODS,
        static_self_edges=edges,
        numpy_helpers=NUMPY_HELPERS,
        global_helpers=GLOBAL_HELPERS,
        math_helpers=MATH_HELPERS,
        generator_authority=(
            "same actual frame/code/caller and observed YIELD/RESUME offsets; "
            "one body claim, ordered non-additive resume/yield attempts"
        ),
        lazy_helper_precondition="actual original pinned modules present; missing closure refuses",
        original_CodeTypes_and_actual_mesh=True,
        new_mesh_or_standalone_runtime=False,
        global_MT="constructor-final original object and exact epoch; no lifecycle draws",
        new_parameter_reads=("refine_mesh", "maximum_voronoi_steps", "voronoi_convergence"),
        stop_before=("ecm_verts", "cluster_mask", "msize", "ecm_verts_unique"),
        smoothing=None,
        make_all_operators=False,
        SVG=False,
        source_native_reference_scientific_release=False,
        checkpoint_or_physical_admission=False,
        work="ordered wrapper/body/helper/authentication/metadata layers; non-additive",
        initial_limits="19/22",
        stable_limits="0/9",
        invalidated_owners=11,
        held_postcut_cases=12,
    )


def _ready():
    if not all(
        type(v) is str and len(v) == 64 and all(c in "0123456789abcdef" for c in v)
        for v in (SOURCE_SHA256, PARENT_SOURCE_SHA256, PARENT_REVIEW_SHA256)
    ):
        raise LifecycleRejected(
            "Lifecycle producer/constructor adoption held", stage="unbound_contract"
        )
    for module, path, expected in (
        (source, _LITERAL_FILE, SOURCE_SHA256),
        (previous, _PARENT_FILE, PARENT_SOURCE_SHA256),
    ):
        if (
            Path(module.__file__) != path
            or path.is_symlink()
            or (hashlib.sha256(path.read_bytes()).hexdigest() != expected)
        ):
            raise LifecycleRejected("Exact reviewed producer required", stage="producer")
    _native_files()
    api = previous._ready()
    if api._world_voronoi_lifecycle_api() is not sys.modules.get(__name__):
        raise LifecycleRejected("Same-instance lifecycle route unavailable", stage="dispatch_held")
    return api


def request_record(request):
    return dict(
        law=LAW_ID,
        mode=request.mode,
        parent=request.parent_identity,
        witness=previous.witness_record(request.witness),
        source=request.source_identity,
    )


def from_constructor(owner, *, law_id, mode=MODE):
    _ready()  # Pins precede all foreign-owner or descriptor access.
    if type(law_id) is not str or law_id != LAW_ID or type(mode) is not str or mode != MODE:
        raise LifecycleRejected("Exact explicit lifecycle mode required", stage="law")
    if _ACTIVE:
        _reject(_ACTIVE[-1], None, "Reentrant lifecycle request")
    if owner in _RETIRED:
        raise LifecycleRejected("Constructor lifecycle epoch consumed", stage="consumed")
    parent = previous._authority(owner)
    witness = parent.call_witness
    if witness is None or parent.trial.call_witness is not witness:
        raise LifecycleRejected("Actual observed constructor CALL required", stage="witness")
    previous._check_callsite(parent)
    if witness.branch not in ("single", "multi_nonSVG"):
        raise LifecycleRejected("SVG lifecycle authority unavailable", stage="SVG_held")
    value = Request(owner, parent.trial.identity, witness, _digest(source_plan()), mode, "")
    value = replace(value, identity=_digest(request_record(value)))
    _REQUESTS[value] = (parent, parent.trial, witness, previous._epoch(parent))
    return value


def _attempt(context, name, frame, layer):
    row = dict(
        sequence=len(context.work),
        name=name,
        frame=frame,
        layer=layer,
        state="attempted",
        body_started=False,
    )
    if len(context.work) >= MAX_WORK:
        context.overflow_attempt = row
        _reject(context, row, "Original bounded lifecycle ledger exhausted")
    context.work.append(row)
    return row


def _reject(context, row, reason):
    context.invalid = True
    if row is None:
        row = dict(
            sequence=len(context.work),
            name="unclaimed_lifecycle_entry",
            frame=sys._getframe(1),
            layer="raw_entry_attempt",
            body_started=False,
        )
        if len(context.work) < MAX_WORK:
            context.work.append(row)
        else:
            context.overflow_attempt = row
    row["state"] = "rejected"
    if context.entry_error is None:
        context.entry_error = LifecycleRejected(
            reason,
            stage=context.stage,
            request=context.request,
            trial=context.trial,
            partial=context,
        )
    raise context.entry_error


def _guard(context):
    if context.entry_error is not None:
        raise context.entry_error
    if context.observation_error is not None:
        raise previous.image.prefix.literal._CaptureStop() from context.observation_error
    if (
        context.invalid
        or not context.active
        or context.thread != get_ident()
        or not _ACTIVE
        or _ACTIVE[-1] is not context
    ):
        _reject(context, None, "Lifecycle requires its active original thread/epoch")


def _capture_failure(context, error, origin, raw):
    if context.observation_error is None:
        context.observation_error = error
    context.capture_errors += ((origin, error, raw),)


def _rng(context):
    row = _attempt(context, "actual_constructor_final_MT_read", sys._getframe(), "metadata")
    value = previous.image.prefix._rng_state(context)
    row["state"] = "returned"
    return value


def _same(actual, expected):
    previous._same(actual, expected)


def _values(context):
    project = previous.image.prefix.literal._project
    return dict(
        inherited=previous._values(context.parent)["inherited"],
        mesh=project(context.projector, vars(context.mesh)),
        image=previous.image._values(context.parent.parent),
        assigned=context.cells.mesh is context.mesh,
    )


def _graph(context, *, final=False):
    return previous._graph(context, final=final)


def _epoch(context):
    return (
        (_snapshot(context).identity, _helper_snapshot(context).identity),
        _graph(context, final=True),
        _rng(context).identity,
    )


def _snapshot(context):
    return previous.image.images.core.caches.snapshot(_values(context))


def _helper_value(context, result):
    """Observe existing buffers only; retain the actual C objects separately.

    No lazy tree nodes or Delaunay transform are requested. This is neither
    complete C-object serialization nor an executable cache representation.
    """
    native = context.native_namespace
    if isinstance(result, native["cKDTree"]):
        return dict(
            kind="cKDTree",
            data=result.data,
            indices=result.indices,
            mins=result.mins,
            maxes=result.maxes,
        )
    if isinstance(result, native["Delaunay"]):
        return dict(
            kind="Delaunay",
            points=result.points,
            simplices=result.simplices,
            neighbors=result.neighbors,
            equations=result.equations,
        )
    return previous.image.prefix.literal._project(context.projector, result)


def _helper_snapshot(context):
    return previous.image.images.core.caches.snapshot(
        dict(
            helpers=context.helper_views,
            mask_queries=context.query_views,
            generator_values=context.generator_views,
        )
    )


def _same_epoch(context, expected):
    current = _epoch(context)
    _same(current[1][0], expected[1][0])
    if current[0] != expected[0] or current[1][1] != expected[1][1] or current[2] != expected[2]:
        raise ValueError("Observer changed actual mesh/image/caller/RNG state")


def _atoms(value):
    return previous.image._call_atoms(value)


def _resolve(module, path):
    for name in path.split("."):
        module = getattr(module, name)
    return module


def _module_bindings(module):
    namespace = vars(module)
    return (
        module,
        namespace,
        *(atom for pair in namespace.items() for atom in pair),
        *(
            atom
            for value in namespace.values()
            if type(value) is FunctionType
            for atom in _atoms(value)
        ),
    )


def _math_bindings(context):
    """Only the math export actually reached by original geopoly.is_convex."""
    geopoly = next(
        module
        for module in context.helper_modules
        if module.__name__ == "betse.util.math.geometry.polygon.geopoly"
    )
    math = vars(geopoly)["math"]
    if type(math) is not ModuleType:
        raise ValueError("Original reached math module dispatch required")
    namespace = vars(math)
    # A missing export refuses without executing a new module __getattr__.
    return geopoly, math, namespace, *_atoms(namespace["atan2"])


def _original_bindings(context):
    namespace = context.parent.original_constructor.__globals__
    numpy = namespace["np"]
    return (
        namespace,
        *(atom for pair in namespace.items() for atom in pair),
        *(
            atom
            for name in context.method_names
            for atom in _atoms(getattr(context.parent.original_type, name))
        ),
        *(atom for module in context.helper_modules for atom in _module_bindings(module)),
        *_math_bindings(context),
        *(
            previous.image.prefix.aliases._MODULE_AUTH.get(module.__name__)
            for module in context.helper_modules
        ),
        numpy,
        numpy.pi,
        type(numpy.pi),
        numpy.linalg,
        numpy.random,
        numpy.random.mtrand,
        numpy.random.mtrand._rand,
        *(atom for name in NUMPY_HELPERS for atom in _atoms(_resolve(numpy, name))),
        *(atom for name in GLOBAL_HELPERS for atom in _atoms(namespace[name])),
        namespace["cKDTree"].query,
        namespace["logs"],
        *_atoms(namespace["logs"].log_info),
        *_atoms(namespace["logs"].log_warning),
        *_atoms(namespace["logs"].__dict__["logging"].info),
        *_atoms(namespace["logs"].__dict__["logging"].warning),
        context.mask.clipping_function,
        *_atoms(context.mask.clipping_function),
    )


def _bootstrap(context):
    fn, code, namespace = context.checker
    if (
        context.api._independent_atoms is not fn
        or fn.__code__ is not code
        or fn.__globals__ is not namespace
    ):
        raise ValueError("Original independent checker changed")
    for name, helper, retained in context.metadata_helpers:
        if globals()[name] is not helper:
            raise ValueError("Lifecycle metadata helper was replaced: " + name)
        _same(fn(helper), retained)


def _bindings(context):
    _bootstrap(context)
    return (
        MODE,
        LAW_ID,
        RELEASE,
        SOURCE_SHA256,
        PARENT_SOURCE_SHA256,
        PARENT_REVIEW_SHA256,
        NATIVE_PINS,
        _PIN_ITEMS,
        *(atom for pair in NATIVE_PINS.items() for atom in pair),
        SINGLE_METHODS,
        MULTI_METHODS,
        NUMPY_HELPERS,
        GLOBAL_HELPERS,
        MATH_HELPERS,
        CO_GENERATOR,
        dis,
        *_atoms(dis.get_instructions),
        MAX_WORK,
        MAX_PROTOCOL_HISTORY,
        _REQUESTS,
        _CONSUMED,
        _RETIRED,
        _ISSUED,
        _FORWARDED,
        _ACTIVE,
        _LOCK,
        _LITERAL_CLASS,
        source.VoronoiLifecycle,
        *_LITERAL_METHODS,
        *previous.image.prefix.literal._surface(source.VoronoiLifecycle),
        *_original_bindings(context),
        context.entries,
        context.parent_claim,
        context.parent_check,
        context.body_codes,
        *(atom for pair in context.body_codes.items() for atom in pair),
        context.generator_sites,
        *(atom for pair in context.generator_sites.items() for atom in pair),
        context.method_names,
        context.edges,
        context.native_root,
        *_atoms(context.parent_claim),
        *_atoms(context.parent_check),
        *_atoms(context.native_wrapper),
        *_atoms(context.native_method),
        *_atoms(context.method),
        *(atom for fn in context.mesh_bodies.values() for atom in _atoms(fn)),
        context.mesh_scope,
        *(atom for pair in context.mesh_scope.items() for atom in pair),
        *(
            atom
            for fn in context.mesh_scope.values()
            if type(fn) is FunctionType
            for atom in _atoms(fn)
        ),
        context.numpy,
        context.numpy.context,
        context.numpy.module,
        context.numpy.linalg,
        context.logs,
        context.logs.context,
        *(
            atom
            for cls in (
                _Numpy,
                _Linalg,
                _Logs,
                _ObserverSystem,
                Request,
                Trial,
                LifecycleOwner,
                LifecycleRejected,
            )
            for atom in previous.image.prefix.literal._surface(cls)
        ),
        *(atom for path, wrapper in context.helpers.items() for atom in (path, *_atoms(wrapper))),
    )


def _check(context):
    if context.active:
        _guard(context)
    _bootstrap(context)
    if (
        _ready() is not context.api
        or context.parent_check(context) is not context.parent
        or _REQUESTS.get(context.request) is not context.refs
        or _CONSUMED.get(context.request) is not context
        or _RETIRED.get(context.request.constructor_owner) is not context
        or context.request.witness is not context.refs[2]
        or context.request.witness is not context.parent.call_witness
        or context.request.parent_identity != context.refs[1].identity
        or _digest(request_record(context.request)) != context.request.identity
        or context.request.source_identity != _digest(context.plan)
        or context.cells.mesh is not context.mesh
        or vars(context.mesh) is not context.mesh_dict
        or context.mesh.make_all_operators is not False
        or context.rng is not context.parent.rng
        or context.edges is not context.plan["static_self_edges"]
        or _rng(context).identity != context.refs[1].stream_after.identity
    ):
        raise ValueError("Original constructor/branch/mesh/image/phase/MT lineage changed")
    _same(_bindings(context), context.bindings)
    graph = _graph(context)
    _same(graph[0], context.inherited_graph[0])
    if graph[1] != context.inherited_graph[1]:
        raise ValueError("Caller aliases or inherited ancestry changed before boundary")


def _observe(context, name, raw):
    _guard(context)
    old = None
    try:
        old = _epoch(context)
        context.events.append((name, raw))
    except BaseException as error:
        _capture_failure(context, error, name, raw)
    if old is not None:
        try:
            _same_epoch(context, old)
        except BaseException as error:
            _capture_failure(context, error, name + "_state", raw)


def _record(context, name, raw):
    """Caller boundary also protects a recorder rejected before its body."""
    try:
        _observe(context, name, raw)
    except BaseException as error:
        if context.observation_error is None:
            context.observation_error = error
        context.capture_errors += ((name + "_call", error, raw),)
    _guard(context)  # Sticky entry rejection takes precedence over capture stop.


def _helper(context, name, delegate, args, kwargs):
    row = _attempt(context, name, sys._getframe(1), "helper_delegate")
    _guard(context)
    if context.helper_active:
        _reject(context, row, "Reentrant lifecycle helper")
    _check(context)
    context.helper_active = True
    try:
        _record(context, name + "_enter", (args, kwargs))
        try:
            row["body_started"] = True
            result = delegate(*args, **kwargs)
        except BaseException as error:
            row["source_error"] = context.last_source_error = error
            raise
        # This precedes ALL return observers/serializers; raw arrays/trees and
        # completed source results survive even a failed observation.
        context.helper_results.append((name, result))
        context.last_helper_result = (name, result)
        row["state"] = "returned"
        try:
            context.helper_views.append((name, _helper_value(context, result)))
        except BaseException as error:
            _capture_failure(context, error, name + "_view", result)
        _guard(context)
        _record(context, name + "_return", result)
        return result
    finally:
        context.helper_active = False


def _helper_wrapper(context, name, delegate):
    def invoke(*args, **kwargs):
        return _helper(context, name, delegate, args, kwargs)

    return invoke


class _Linalg:
    def __init__(self, context):
        self.context = context

    def __getattr__(self, name):
        path = "linalg." + name
        if path not in self.context.helpers:
            _reject(self.context, None, "Unselected NumPy linalg helper: " + path)
        return self.context.helpers[path]


class _Numpy:
    def __init__(self, module, context):
        self.module, self.context, self.linalg = module, context, _Linalg(context)

    def __getattr__(self, name):
        if name in self.context.helpers:
            return self.context.helpers[name]
        if name in ("pi", "ndarray"):
            return getattr(self.module, name)
        _reject(self.context, None, "Unselected NumPy/RNG helper: " + name)


class _Logs:
    def __init__(self, context):
        self.context = context

    def log_info(self, *args, **kwargs):
        return _helper(
            self.context, "logs.log_info", self.context.native_logs.log_info, args, kwargs
        )

    def log_warning(self, *args, **kwargs):
        return _helper(
            self.context, "logs.log_warning", self.context.native_logs.log_warning, args, kwargs
        )


def _code_tree(code):
    return (
        code,
        *(
            child
            for value in code.co_consts
            if type(value) is CodeType
            for child in _code_tree(value)
        ),
    )


def _generator_sites(code):
    """Immutable interpreter metadata, never generator/body execution.

    Synchronous generators emit return events at both YIELD_VALUE and terminal
    exits. At a resumed call CPython exposes either the saved yield offset or
    its immediately following RESUME instruction. Both sites come from this
    exact original CodeType; no frame-line rewrite or mutable event label is
    accepted as resumption evidence.
    """
    instructions = tuple(dis.get_instructions(code, show_caches=True, adaptive=False))
    yields = []
    for index, instruction in enumerate(instructions):
        if instruction.opname != "YIELD_VALUE":
            continue
        resumes = [instruction.offset]
        for following in instructions[index + 1 :]:
            if following.opname == "CACHE":
                continue
            if following.opname == "RESUME":
                resumes.append(following.offset)
            break
        yields.append((instruction.offset, tuple(resumes)))
    terminals = tuple(
        instruction.offset
        for instruction in instructions
        if instruction.opname in ("RETURN_VALUE", "RETURN_CONST")
    )
    raises = tuple(
        (instruction.offset, instruction.opname, instruction.arg)
        for instruction in instructions
        if instruction.opname in ("RERAISE", "RAISE_VARARGS")
    )
    return tuple(yields), terminals, raises


def _protocol_event(context, hook, frame, event, result=None):
    """Bounded diagnostic metadata, never a claim or an execution permission."""
    if frame.f_code not in context.generator_sites:
        return
    try:
        history = getattr(context, "protocol_history", None)
        if history is None:
            context.protocol_history, context.protocol_total, context.protocol_dropped = [], 0, 0
            history = context.protocol_history
        row = context.admitted.get(id(frame))
        token = None if row is None else row.get("suspension")
        bytecode = frame.f_code.co_code
        opcode = (
            dis.opname[bytecode[frame.f_lasti]] if 0 <= frame.f_lasti < len(bytecode) else None
        )  # Diagnostic only; admission uses the retained disassembled sites.
        error = context.entry_error
        if error is None and row is not None:
            error = row.get("source_error")
        entry = dict(
            sequence=context.protocol_total,
            hook=hook,
            event=event,
            code=frame.f_code.co_qualname,
            code_id=id(frame.f_code),
            offset=frame.f_lasti,
            opcode=opcode,
            frame_id=id(frame),
            caller_id=None if frame.f_back is None else id(frame.f_back),
            state=None if row is None else row.get("state"),
            activation=None if row is None else row.get("activation"),
            body_started=None if row is None else row.get("body_started"),
            token_id=None if token is None else id(token),
            token_activation=None if token is None else token[3],
            token_offset=None if token is None else token[4],
            token_observed_offset=None if token is None else token[5],
            token_bound_pair=None if token is None else token[6],
            result_type=None if "return" not in event else type(result).__qualname__,
            result_id=None if "return" not in event else id(result),
            error_id=None if error is None else id(error),
            error_type=None if error is None else type(error).__qualname__,
            cause_id=None if error is None or error.__cause__ is None else id(error.__cause__),
        )
        context.protocol_total += 1
        if len(history) >= MAX_PROTOCOL_HISTORY:
            del history[64]  # Retain the first64 plus the most recent192 events.
            context.protocol_dropped += 1
        history.append(entry)
    except BaseException as error:
        if context.observation_error is None:
            context.observation_error = error
        context.capture_errors += (("protocol_history", error, frame),)


def _generator_origin(context, frame):
    """A real shared trace/profile admission, before inherited observers.

    Direct calls from a callback cannot seize a suspended or active slot. The
    original account's before/profile/trace CodeTypes and private scope are
    retained; this does not attach a new source method or change a native body.
    """
    before = sys._getframe(2)
    observer = before.f_back
    codes = context.observer_system.codes
    return (
        type(frame) is FrameType
        and before.f_code is codes["before"]
        and before.f_globals is context.observer_scope
        and before.f_locals.get("context") is context
        and before.f_locals.get("frame") is frame
        and before.f_locals.get("event") == "call"
        and observer is not None
        and observer.f_code in (codes["profile"], codes["trace"])
        and observer.f_globals is context.observer_scope
        and observer.f_locals.get("context") is context
        and observer.f_locals.get("frame") is frame
        and observer.f_locals.get("event") == "call"
    )


def _generator_caller(context, frame):
    row = context.admitted.get(id(frame))
    if row is not None and row["frame"] is frame:
        return row["state"] == "admitted" and row["body_started"] is True
    return (
        frame is not None
        and frame.f_code is _helper.__code__
        and frame.f_locals.get("context") is context
        and context.helper_active
    )


def _yield_pair(context, code, offset):
    """Only a retained original YIELD and its immediate bound RESUME match."""
    sites = context.generator_sites.get(code)
    if sites is None:
        return None
    return next((pair for pair in sites[0] if offset in pair[1]), None)


def _record_generator_exception(context, frame, row):
    error = context.pending_source_error
    row["source_errors"].append((row["activation"], error, frame.f_lasti))
    row.setdefault("exception_witnesses", []).append(
        (frame, frame.f_code, row["activation"], error, frame.f_lasti)
    )
    row["exception_unwind_pending"] = True


def _exception_witness(frame, row):
    return next(
        (
            witness
            for witness in reversed(row.get("exception_witnesses", ()))
            if witness[0] is frame
            and witness[1] is frame.f_code
            and witness[2] == row["activation"]
            and witness[3] is row.get("source_error")
            and isinstance(witness[3], BaseException)
        ),
        None,
    )


def _resume(context, frame, row):
    attempt = _attempt(context, "generator_resume", frame, "generator_resume")
    _guard(context)
    token = context.generator_suspensions.get(id(frame))
    sites = context.generator_sites.get(frame.f_code)
    if (
        type(frame) is not FrameType
        or token is None
        or type(token) is not tuple
        or len(token) != 7
        or token is not row.get("suspension")
        or token[0] is not frame
        or token[1] is not frame.f_code
        or token[2] is not row["origin_parent"]
        or frame.f_back is not token[2]
        or token[3] != row["activation"]
        or row["state"] != "suspended"
        or row.get("returned", False)
        or row.get("pending_return", False)
        or sites is None
        or _yield_pair(context, frame.f_code, frame.f_lasti) is not token[6]
        or _yield_pair(context, frame.f_code, token[5]) is not token[6]
        or token[4] != token[6][0]
        or row.get("return_claim") is None
        or row["return_claim"]["token"] is not token
        or not _generator_caller(context, frame.f_back)
    ):
        _reject(context, attempt, "Foreign, completed or unobserved generator resumption")
    # Consume the actual yield token before the first inherited observer. A
    # caught observer rejection never reconstructs or rearms this token.
    del context.generator_suspensions[id(frame)]
    row["suspension"] = None
    row["activation"] += 1
    row["body_started"] = False
    row["state"] = "admitted"
    row["exception_unwind_pending"] = False
    row["return_claim"] = None
    row["return_observations"] = []
    row.pop("source_error", None)
    attempt["state"], attempt["activation"] = "admitted", row["activation"]


def _generator_return(context, frame, row):
    """Capture is idempotent; only authenticated hook results claim exits.

    Both hooks reach this function. An unknown PC is an observation pending a
    bound yield/return or actual trace unwind, never evidence of termination.
    """
    if context.entry_error is not None or context.observation_error is not None:
        return  # An interrupted observer must not replace the primary cause.
    claim = row.get("return_claim")
    if claim is None:
        if row.get("pending_return", False):
            return
        _reject(context, None, "Generator capture lacks its authenticated return observation")
    if (
        claim["frame"] is not frame
        or claim["code"] is not frame.f_code
        or claim["activation"] != row["activation"]
        or row["return_activation"] != row["activation"]
        or (
            claim["kind"] == "yield"
            and (
                row["state"] != "suspended"
                or row.get("suspension") is not claim["token"]
                or context.generator_suspensions.get(id(frame)) is not claim["token"]
                or _yield_pair(context, frame.f_code, frame.f_lasti) is not claim["yield_pair"]
                or claim["token"][4] != claim["yield_pair"][0]
                or claim["token"][5] != claim["offset"]
                or claim["token"][6] is not claim["yield_pair"]
            )
        )
        or (
            claim["kind"] != "yield"
            and (row["returned"] is not True or row["state"] not in ("returned", "unwound"))
        )
        or (
            claim["kind"] == "unwind"
            and _exception_witness(frame, row) is not claim["exception_witness"]
        )
    ):
        _reject(context, None, "Generator logical exit changed between companion observations")


def _generator_observation(context, frame, result):
    """Authenticate the actual adapter stack, not a supplied hook label."""
    result_frame = sys._getframe(2)
    hook_frame = result_frame.f_back
    system = context.observer_system
    result_method = system._result
    if (
        type(frame) is not FrameType
        or result_method.__self__ is not system
        or result_frame.f_code is not result_method.__func__.__code__
        or result_frame.f_locals.get("self") is not system
        or result_frame.f_locals.get("frame") is not frame
        or result_frame.f_locals.get("event") != "return"
        or result_frame.f_locals.get("result") is not result
        or hook_frame is None
        or hook_frame.f_locals.get("frame") is not frame
        or hook_frame.f_locals.get("event") != "return"
        or hook_frame.f_locals.get("arg") is not result
    ):
        _reject(context, None, "Generator return lacks its actual observer stack")
    for name in ("trace", "profile"):
        actual = getattr(system, name, None)
        if type(actual) is FunctionType and hook_frame.f_code is actual.__code__:
            return name
    _reject(context, None, "Unknown generator return observer")


def _generator_result(context, frame, result):
    """One logical exit per actual activation, with both raw hook observations."""
    row = context.admitted.get(id(frame))
    if row is None or row["frame"] is not frame:
        _reject(context, None, "Generator return lacks its actual frame claim")
    hook = _generator_observation(context, frame, result)
    activation = row["activation"]
    observation = (hook, frame, frame.f_code, activation, frame.f_lasti, result)
    if len(context.generator_observations) >= MAX_WORK:
        context.overflow_generator_observation = observation
        _reject(context, None, "Original bounded generator observation ledger exhausted")
    retained = dict(
        observation=observation,
        prior_state=row["state"],
        prior_token=row.get("suspension"),
        decision=None,
    )
    context.generator_observations.append(retained)
    if context.entry_error is not None or context.observation_error is not None:
        retained["decision"] = "interrupted"
        context.generator_interruptions.append(
            (observation, context.entry_error, context.observation_error, row.get("source_error"))
        )
        _protocol_event(context, hook, frame, "interrupted_return", result)
        return
    observations = row.setdefault("return_observations", [])
    if any(old[0] == hook for old in observations):
        _reject(context, None, "Repeated generator return hook in one activation")
    observations.append(observation)  # Retain raw output before projection/callbacks.
    sites = context.generator_sites[frame.f_code]
    yield_pair = _yield_pair(context, frame.f_code, frame.f_lasti)
    witness = _exception_witness(frame, row)
    raise_site = next((site for site in sites[2] if site[0] == frame.f_lasti), None)
    # A line in a finally block is not evidence that the exception was
    # suppressed. A genuine RETURN is normal, a bound raise needs this exact
    # activation's trace exception, and an immediate unwind stays explicit.
    terminal = frame.f_lasti in sites[1]
    unwind = (
        not terminal
        and witness is not None
        and (raise_site is not None or row.get("exception_unwind_pending", False))
    )
    kind = (
        "unwind"
        if unwind
        else (
            "yield"
            if yield_pair is not None
            else ("terminal" if frame.f_lasti in sites[1] else None)
        )
    )
    claim = row.get("return_claim")
    if claim is not None:
        if (
            claim["frame"] is not frame
            or claim["code"] is not frame.f_code
            or claim["activation"] != activation
            or claim["result"] is not result
            or kind != claim["kind"]
            or (kind == "yield" and yield_pair is not claim["yield_pair"])
            or (kind == "unwind" and witness is not claim["exception_witness"])
        ):
            _reject(context, None, "Generator companion result or exit evidence changed")
        _generator_return(context, frame, row)
        retained["decision"] = "companion"
        return
    if kind is None:
        retained["decision"] = "unresolved"
        row["pending_return"] = True
        return  # No guessed PC allowlist and no terminal-state fallback.
    if row["state"] != "admitted" or row["body_started"] is not True:
        _reject(context, None, "Generator exit lacks an active admitted body")
    if any(old[5] is not result for old in observations):
        _reject(context, None, "Pending generator observation changed its actual return")
    token = None
    if kind == "yield":
        if any(
            old[1] is not frame
            or old[2] is not frame.f_code
            or old[3] != activation
            or _yield_pair(context, old[2], old[4]) is not yield_pair
            for old in observations
        ):
            _reject(context, None, "Unpaired generator observations cannot claim a yield")
        token = (
            frame,
            frame.f_code,
            row["origin_parent"],
            activation,
            yield_pair[0],
            frame.f_lasti,
            yield_pair,
        )
        row["suspension"] = token
        context.generator_suspensions[id(frame)] = token
        row["state"] = "suspended"
        attempt = _attempt(context, "generator_yield", frame, "generator_yield")
        attempt["state"], attempt["activation"] = "suspended", activation
        attempt["canonical_yield_offset"], attempt["observed_offset"] = yield_pair[0], frame.f_lasti
    else:
        row["returned"] = True
        row["state"] = "unwound" if kind == "unwind" else "returned"
        context.generator_suspensions.pop(id(frame), None)
    row["return_activation"], row["pending_return"] = activation, False
    row["return_claim"] = dict(
        frame=frame,
        code=frame.f_code,
        activation=activation,
        kind=kind,
        offset=frame.f_lasti,
        result=result,
        token=token,
        yield_pair=yield_pair if kind == "yield" else None,
        exception_witness=witness if kind == "unwind" else None,
        raise_site=raise_site if kind == "unwind" else None,
    )
    retained["decision"], retained["claim"] = "logical_exit", row["return_claim"]
    context.generator_results.append(
        (
            frame,
            activation,
            "yield" if kind == "yield" else "terminal",
            result,
            row.get("source_error") if kind == "unwind" else None,
        )
    )
    context.generator_views.append(_helper_value(context, result))


def _literal_code(name):
    payload = _LITERAL_FILE.read_bytes()
    if hashlib.sha256(payload).hexdigest() != SOURCE_SHA256:
        raise ValueError("Pinned lifecycle literal required")
    compiled = compile(payload, str(_LITERAL_FILE), "exec", dont_inherit=True)
    cls = next(
        v for v in compiled.co_consts if type(v) is CodeType and v.co_name == "VoronoiLifecycle"
    )
    code = next(v for v in cls.co_consts if type(v) is CodeType and v.co_name == name)
    fn = vars(source.VoronoiLifecycle)[name]
    expected = _LITERAL_METHODS[("single", "multi_nonSVG").index(name)]
    if (
        source.VoronoiLifecycle is not _LITERAL_CLASS
        or fn is not expected
        or fn.__code__ != code
        or fn.__code__.co_filename != str(_LITERAL_FILE)
        or fn.__globals__ is not vars(source)
        or fn.__defaults__ is not None
        or fn.__kwdefaults__ is not None
        or fn.__closure__ is not None
        or fn.__dict__
        or fn.__annotations__
    ):
        raise ValueError("Original lifecycle entry code/signature changed")
    return fn.__code__


def _namespace(context):
    original = context.parent.original_type
    context.method_names = (
        SINGLE_METHODS if context.request.witness.branch == "single" else MULTI_METHODS
    )
    root = _native_files()
    callbacks = previous.image.prefix.previous.previous.caches.previous.callbacks
    previous.image.prefix.aliases._check_modules()
    methods = {name: getattr(original, name) for name in context.method_names}
    nodes = _nodes(root / "betse/science/math/mesh.py", "DECMesh")
    for name, fn in methods.items():
        callbacks._source_function(fn, "betse/science/math/mesh.py", name, "DECMesh")
        expected = tuple(ast.literal_eval(n) for n in nodes[name].args.defaults)
        defaults = () if fn.__defaults__ is None else fn.__defaults__
        if (
            fn.__closure__ is not None
            or fn.__kwdefaults__ is not None
            or fn.__dict__
            or previous.image.images.core.caches.snapshot(defaults).identity
            != previous.image.images.core.caches.snapshot(expected).identity
        ):
            raise ValueError("Native method hidden delegate/defaults changed: " + name)
    authenticated = tuple((name, fn, _atoms(fn)) for name, fn in methods.items())
    context.edges = context.plan["static_self_edges"]
    context.native_namespace = context.parent.original_constructor.__globals__
    numpy = context.native_namespace["np"]
    context.native_logs = context.native_namespace["logs"]
    context.helper_modules = []
    for module, _ in _PIN_ITEMS:
        if module in ("betse.science.cells", "betse.science.math.mesh"):
            continue
        actual = sys.modules.get(module)
        path = root / (module.replace(".", "/") + ".py")
        if type(actual) is not ModuleType or Path(actual.__file__) != path:
            raise ValueError("Actual pinned helper/import prerequisite unavailable: " + module)
        issued = previous.image.prefix.aliases._MODULE_AUTH.get(module)
        if issued is None or issued[0][0] is not actual:
            raise ValueError("Original helper requires genuine native import issuance: " + module)
        context.helper_modules.append(actual)
    context.helper_modules = tuple(context.helper_modules)
    for module in context.helper_modules:
        definitions = ast.parse(Path(module.__file__).read_bytes()).body
        for node in definitions:
            if isinstance(node, ast.FunctionDef):
                fn = getattr(module, node.name)
                callbacks._source_function(fn, module.__name__.replace(".", "/") + ".py", node.name)
    before_helpers = _original_bindings(context)
    context.helpers = {
        name: _helper_wrapper(context, "np." + name, _resolve(numpy, name))
        for name in NUMPY_HELPERS
    }
    context.numpy, context.logs = _Numpy(numpy, context), _Logs(context)
    scope = dict(context.native_namespace, np=context.numpy, logs=context.logs)
    scope.update(
        {
            name: _helper_wrapper(context, name, context.native_namespace[name])
            for name in GLOBAL_HELPERS
        }
    )
    context.mesh_scope = scope
    _same(_original_bindings(context), before_helpers)
    for name, fn, retained in authenticated:
        if getattr(original, name) is not fn:
            raise ValueError("Original method changed during namespace preparation")
        _same(_atoms(fn), retained)
    context.mesh_bodies = {
        name: FunctionType(fn.__code__, scope, fn.__name__, fn.__defaults__, fn.__closure__)
        for name, fn in methods.items()
    }
    branch = context.request.witness.branch
    context.method = FunctionType(_literal_code(branch), vars(source), branch)
    wrapper_code = vars(context.parent.runtime_type)["init_mesh"].__code__
    context.body_codes = {
        context.method.__code__: ROOT,
        context.native_wrapper.__code__: WRAPPER,
        wrapper_code: "mesh_method_wrapper",
        next(
            c for c in _helper_wrapper.__code__.co_consts if type(c) is CodeType
        ): "lifecycle_helper_wrapper",
        _Logs.log_info.__code__: "lifecycle_log_wrapper",
        _Logs.log_warning.__code__: "lifecycle_log_wrapper",
    }
    for name, fn in methods.items():
        for code in _code_tree(fn.__code__):
            context.body_codes[code] = "DECMesh." + name if code is fn.__code__ else "native_inner"
    # Keep actual helper wrapper chains AND the original helper code/globals.
    context.helper_codes = set()
    for module in context.helper_modules:
        for fn in vars(module).values():
            if type(fn) is FunctionType:
                for atom in _atoms(fn):
                    if type(atom) is CodeType:
                        context.helper_codes.update(_code_tree(atom))
    for name in GLOBAL_HELPERS:
        for atom in _atoms(context.native_namespace[name]):
            if type(atom) is CodeType:
                context.helper_codes.update(_code_tree(atom))
    for atom in _atoms(context.mask.clipping_function):
        if type(atom) is CodeType:
            context.helper_codes.update(_code_tree(atom))
    for code in context.helper_codes:
        context.body_codes.setdefault(code, "native_helper_body")
    context.native_root = str(root) + os.sep
    context.mask_codes = frozenset(
        atom for atom in _atoms(context.mask.clipping_function) if type(atom) is CodeType
    )
    context.generator_sites = MappingProxyType(
        {
            code: _generator_sites(code)
            for code in context.body_codes
            if code.co_flags & CO_GENERATOR
        }
    )


def _admit(context, frame):
    _protocol_event(context, "admission", frame, "call")
    old = context.admitted.get(id(frame))
    if old is not None and old["frame"] is frame:
        _guard(context)
        if frame.f_code in context.generator_sites:
            if not _generator_origin(context, frame):
                _reject(
                    context, None, "Direct/reentrant generator admission outside original hooks"
                )
            if old["state"] == "suspended":
                _resume(context, frame, old)
            elif old["state"] != "admitted" or old.get("returned", False):
                _reject(context, None, "Completed generator frame cannot reenter")
            elif old.get("pending_return", False):
                _reject(context, None, "Unresolved generator return cannot resume")
        elif old["state"] != "admitted" or old.get("returned", False):
            _reject(context, None, "Completed source frame cannot reenter")
        return
    name = context.body_codes[frame.f_code]
    row = _attempt(context, name, frame, "wrapper" if "wrapper" in name else "native_body")
    context.admitted[id(frame)] = row  # Claim before trace OR profile callbacks.
    _guard(context)
    parent = frame.f_back
    if frame.f_code in context.generator_sites:
        if not _generator_origin(context, frame):
            _reject(context, row, "Generator body lacks its genuine original observer entry")
        row.update(
            activation=0,
            origin_parent=parent,
            suspension=None,
            source_errors=[],
            exception_witnesses=[],
            exception_unwind_pending=False,
            return_claim=None,
            return_observations=[],
            pending_return=False,
        )
    valid = False
    if name == WRAPPER:
        valid = (
            parent is context.driver_frame
            and not context.wrapper_claimed
            and frame.f_locals.get("actual") is context.cells
            and frame.f_locals.get("delegate") is context.native_method
            and frame.f_locals.get("context") is context.parent.parent.parent.prefix
            and frame.f_locals.get("method") == "make_voronoi"
        )
        if valid:
            context.wrapper_claimed, context.wrapper_frame = True, frame
    elif name == ROOT:
        valid = (
            parent is context.body_parent_frame
            and context.root_claimed
            and context.root_frame is None
            and frame.f_locals.get("self") is context.cells
            and frame.f_locals.get("phase") is context.phase
            and frame.f_locals.get("image_mask") is context.mask
        )
        if valid:
            context.root_frame = frame
    elif name == "mesh_method_wrapper":
        method = frame.f_locals.get("name")
        parent_row = None if parent is None else context.admitted.get(id(parent))
        parent_method = None if parent is None else context.body_codes.get(parent.f_code)
        if parent is context.root_frame:
            wanted = (
                "init_mesh" if context.request.witness.branch == "single" else "clip_and_refine"
            )
            valid = not context.method_claimed and method == wanted
            if valid:
                context.method_claimed = True
        elif (
            parent_row is not None
            and parent_row["frame"] is parent
            and parent_row["body_started"]
            and parent_method is not None
            and parent_method.startswith("DECMesh.")
        ):
            valid = method in context.edges[parent_method.split(".", 1)[1]]
        valid = (
            valid
            and method in context.mesh_bodies
            and frame.f_locals.get("actual") is context.mesh
            and frame.f_locals.get("context") is context.parent
            and frame.f_locals.get("delegate") is getattr(context.parent.original_type, method)
        )
    elif name.startswith("DECMesh."):
        method = name.split(".", 1)[1]
        valid = (
            parent in context.delegate_frames.values()
            and parent is context.delegate_frames.get(method)
            and parent.f_locals.get("name") == method
            and frame.f_locals.get("self") is context.mesh
        )
    elif name in (
        "lifecycle_helper_wrapper",
        "lifecycle_log_wrapper",
        "native_inner",
        "native_helper_body",
    ):
        parent_row = None if parent is None else context.admitted.get(id(parent))
        valid = (
            parent_row is not None
            and parent_row["frame"] is parent
            and parent_row["body_started"]
            and parent_row["state"] == "admitted"
        )
        if parent is not None and parent.f_code is _helper.__code__:
            valid = context.helper_active and parent.f_locals.get("context") is context
    if not valid:
        _reject(context, row, "Unclaimed/reentrant/raw lifecycle entry: " + name)
    row["state"] = "admitted"


def _capture(context, frame, event):
    raw = dict(frame.f_locals)
    context.locals[(frame.f_code.co_qualname, event)] = raw
    context.last_frame, context.last_raw_locals = frame, raw
    row = context.admitted.get(id(frame))
    if row is None or row["frame"] is not frame:
        return
    if event == "exception":
        row["source_error"] = context.pending_source_error
        if frame.f_code in context.generator_sites:
            _record_generator_exception(context, frame, row)
    elif event == "line" and frame.f_code in context.generator_sites:
        # Continued source execution (handler/finally/next loop line) differs
        # from immediate exception-unwind return at a saved yield instruction.
        row["exception_unwind_pending"] = False
    if event == "return" and frame.f_code in context.generator_sites:
        _generator_return(context, frame, row)
        return
    if event == "return" and not row.get("returned", False):
        row["returned"] = True
        row["state"] = "unwound" if row.get("source_error") is not None else "returned"
        if context.body_codes[frame.f_code] == ROOT and row["state"] == "returned":
            context.root_returned = True


def _mesh_call(context, original, name, delegate, actual, args, kwargs, wrapper):
    row = _attempt(context, name + "_dispatch", wrapper, "wrapper_dispatch")
    _guard(context)
    if (
        original is not context.parent
        or actual is not context.mesh
        or previous._MESHES.get(actual) is not original
        or name not in context.mesh_bodies
        or delegate is not getattr(original.original_type, name)
        or type(wrapper) is not FrameType
        or context.admitted.get(id(wrapper), {}).get("frame") is not wrapper
        or not context.admitted[id(wrapper)]["body_started"]
    ):
        _reject(context, row, "Actual original guarded method/runtime claim required")
    _check(context)
    context.delegate_frames[name] = sys._getframe()
    try:
        result = context.mesh_bodies[name](actual, *args, **kwargs)
        context.last_method_result = (name, result)
        row["state"] = "returned"
        _guard(context)
        return result
    except BaseException as error:
        row["source_error"] = error
        raise
    finally:
        context.delegate_frames.pop(name, None)


def _wrapper_guard(context, original, wrapper):
    if getattr(context, "geometry", None) is not None:
        child, module = _geometry_route(context)
        return module._wrapper_guard(child, original, wrapper)
    row = _attempt(context, DISPATCH_LABEL, wrapper, "original_wrapper_guard")
    _guard(context)
    if (
        not context.source_ready
        or type(wrapper) is not FrameType
        or original is not context.parent.parent.parent.prefix
        or not context.wrapper_claimed
        or wrapper is not context.wrapper_frame
        or wrapper.f_back is not context.driver_frame
        or wrapper.f_code is not context.native_wrapper.__code__
        or wrapper.f_locals.get("actual") is not context.cells
        or wrapper.f_locals.get("delegate") is not context.native_method
    ):
        _reject(context, row, "Only original claimed Cells wrapper may enter lifecycle")
    _check(context)
    row["state"] = "returned"


def _dispatch(context, original, label, delegate, actual, args, kwargs, dispatch_frame):
    if getattr(context, "geometry", None) is not None:
        child, module = _geometry_route(context)
        return module._dispatch(
            child, original, label, delegate, actual, args, kwargs, dispatch_frame
        )
    row = _attempt(context, label, dispatch_frame, "original_native_wrapper_dispatch")
    _guard(context)
    native = None if type(dispatch_frame) is not FrameType else dispatch_frame.f_back
    wrapper = None if native is None else native.f_back
    if (
        not context.source_ready
        or type(dispatch_frame) is not FrameType
        or sys._getframe(1).f_code is not previous._dispatch.__code__
        or dispatch_frame.f_code is not previous.image.prefix.previous._dispatch_seed_world.__code__
        or native is None
        or native.f_code is not context.parent.parent.parent.native_call_code
        or native.f_locals.get("context") is not original
        or wrapper is not context.wrapper_frame
        or wrapper.f_back is not context.driver_frame
        or original is not context.parent.parent.parent.prefix
        or context.root_claimed
        or not context.wrapper_claimed
        or type(label) is not str
        or label != DISPATCH_LABEL
        or actual is not context.cells
        or delegate is not context.native_method
        or type(args) is not tuple
        or len(args) != 1
        or args[0] is not context.phase
        or type(kwargs) is not dict
        or kwargs
    ):
        _reject(context, row, "Only original full-frame same-instance lifecycle dispatch may enter")
    context.root_claimed, context.body_parent_frame = True, sys._getframe()
    _check(context)
    _record(context, "lifecycle_enter", (actual, context.phase, context.mask))
    result = context.method(actual, context.phase, context.mask)
    context.raw_root_result = result
    row["state"] = "returned"
    _record(context, "lifecycle_return", result)
    return result


class _ObserverSystem:
    """Private observer adapter; unknown native package bodies refuse at CALL.

    Delegates/installation/restoration still use the reviewed protected account
    body. Nothing patches sys or a shared native namespace.
    """

    def __init__(self, context):
        self.context = context
        self.setters = (sys.setprofile, sys.settrace)
        self.getters = (sys.getprofile, sys.gettrace)
        original = previous.image.prefix._account.__wrapped__.__code__
        self.codes = MappingProxyType(
            {v.co_name: v for v in original.co_consts if type(v) is CodeType}
        )

    def __getattr__(self, name):
        return getattr(sys, name)

    def _gate(self, frame, event):
        if event == "call" and frame.f_code not in self.context.body_codes:
            if frame.f_code.co_filename.startswith(self.context.native_root):
                _reject(self.context, None, "Unbound original helper/import body")

    def _result(self, frame, event, result):
        if event == "return" and frame.f_code in self.context.generator_sites:
            try:
                _generator_result(self.context, frame, result)
            except BaseException as error:
                if self.context.observation_error is None:
                    self.context.observation_error = error
                self.context.capture_errors += (("generator_return", error, (frame, result)),)
        if event == "return" and frame.f_code in self.context.mask_codes:
            # Called inside the profiler: retain actual query returns before
            # forwarding to any inherited return observer. Unwinds retain None
            # with their source-error row, never a fabricated successful query.
            row = self.context.admitted.get(id(frame))
            source_error = None if row is None else row.get("source_error")
            try:
                self.context.query_results.append((frame, result, source_error))
                self.context.query_views.append(_helper_value(self.context, result))
            except BaseException as error:
                if self.context.observation_error is None:
                    self.context.observation_error = error
                self.context.capture_errors += (("mask_query_return", error, (frame, result)),)
            if source_error is None:
                _guard(self.context)  # Stop normal returns; never mask a native unwind.

    def setprofile(self, function):
        if type(function) is FunctionType and function.__code__ is self.codes["profile"]:

            def guarded(frame, event, arg):
                _protocol_event(self.context, "profile", frame, event, arg)
                self._gate(frame, event)
                self._result(frame, event, arg)
                return function(frame, event, arg)

            self.profile = guarded
            return self.setters[0](guarded)
        return self.setters[0](function)

    def settrace(self, function):
        if type(function) is FunctionType and function.__code__ is self.codes["trace"]:
            delegates = {}

            def guarded(frame, event, arg):
                _protocol_event(self.context, "trace", frame, event, arg)
                self._gate(frame, event)
                if frame.f_code in self.context.generator_sites:
                    self._result(frame, event, arg)
                selected = function if event == "call" else delegates.get(id(frame))
                value = None if selected is None else selected(frame, event, arg)
                if event == "return":
                    delegates.pop(id(frame), None)
                else:
                    delegates[id(frame)] = value
                return guarded if value is not None else None

            self.trace = guarded
            return self.setters[1](guarded)
        return self.setters[1](function)


def _observer_bindings(context=None):
    context = _ACTIVE[-1] if context is None else context
    _bootstrap(context)
    return (
        context.observer_scope,
        context.observer_function,
        context.observer_system,
        context.observer_system.context,
        context.observer_system.setters,
        context.observer_system.getters,
        context.observer_system.codes,
        *(atom for pair in context.observer_system.codes.items() for atom in pair),
        *(atom for pair in context.observer_scope.items() for atom in pair),
        *(
            atom
            for fn in (
                _admit,
                _capture,
                _capture_failure,
                _guard,
                _check,
                _epoch,
                _same_epoch,
                _reject,
                _protocol_event,
                _generator_observation,
                _generator_return,
                _generator_result,
                _resume,
                _yield_pair,
                _record_generator_exception,
                _exception_witness,
            )
            for atom in _atoms(fn)
        ),
    )


@contextmanager
def _account(context):
    scope = dict(previous.image.prefix.__dict__)
    scope.update(
        {
            name: globals()[name]
            for name in (
                "_observer_bindings",
                "_admit",
                "_capture",
                "_capture_failure",
                "_guard",
                "_check",
                "_epoch",
                "_same_epoch",
                "_reject",
            )
        }
    )
    scope["_Random"] = previous._Random
    context.observer_system = _ObserverSystem(context)
    scope["sys"] = context.observer_system
    original = previous.image.prefix._account.__wrapped__
    fn = FunctionType(
        original.__code__, scope, original.__name__, original.__defaults__, original.__closure__
    )
    context.observer_scope, context.observer_function = scope, fn
    context.observer_bindings = _observer_bindings(context)
    with contextmanager(fn)(context):
        yield


def trial_record(value):
    return dict(
        request=value.request_identity,
        constructor_trial=value.constructor_trial_identity,
        witness=value.witness_identity,
        before=None if value.before is None else value.before.identity,
        cache=None if value.cache is None else value.cache.identity,
        stream_before=None if value.stream_before is None else value.stream_before.identity,
        stream_after=None if value.stream_after is None else value.stream_after.identity,
        work=value.work,
        warnings=value.warnings,
        source_completed=value.source_completed,
        failure_stage=value.failure_stage,
        source_failure=value.source_failure_type,
        capture_failure=value.capture_failure_type,
        helper_cache=None if value.helper_cache is None else value.helper_cache.identity,
    )


def _partial(context):
    return dict(
        context=context,
        request=context.request,
        constructor_parent=context.parent,
        constructor_trial=context.refs[1],
        actual_call_witness=context.refs[2],
        phase=context.phase,
        parameters=context.p,
        caller=context.cells,
        mesh=context.mesh,
        mask=context.mask,
        original_MT=context.rng,
        locals=context.locals,
        events=context.events,
        work=context.work,
        helper_results=context.helper_results,
        helper_views=context.helper_views,
        query_results=context.query_results,
        query_views=context.query_views,
        generator_results=context.generator_results,
        generator_views=context.generator_views,
        generator_interruptions=context.generator_interruptions,
        generator_observations=context.generator_observations,
        generator_suspensions=context.generator_suspensions,
        protocol_history=getattr(context, "protocol_history", ()),
        protocol_dropped=getattr(context, "protocol_dropped", 0),
        last_method_result=getattr(context, "last_method_result", None),
        primary=context.primary,
        capture_errors=context.capture_errors,
        cleanup_errors=context.cleanup_errors,
        trial=context.trial,
    )


def _failure(context, primary, capture):
    context.invalid = True
    partial = context
    try:
        partial = _partial(context)
    except BaseException as error:
        context.capture_errors += (("failure_partial", error, context),)
        if capture is None:
            capture = error
    try:
        error = LifecycleRejected(
            "Same-phase native lifecycle failed",
            stage=context.stage,
            request=context.request,
            trial=context.trial,
            partial=partial,
            source_error=primary,
            capture_error=capture,
        )
    except BaseException as secondary:
        context.capture_errors += (("failure_exception", secondary, partial),)
        if primary is not None:
            raise primary  # noqa: B904
        if capture is not None:
            raise capture  # noqa: B904
        raise
    raise error from primary


def _recover(context):
    return previous._recover(context)


def prepare(request, *, enabled=False):
    api = _ready()
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise LifecycleRejected("Actual native lifecycle remains held", stage="release")
    if _ACTIVE:
        _reject(_ACTIVE[-1], None, "Reentrant lifecycle continuation")
    if type(request) is not Request or request not in _REQUESTS:
        raise LifecycleRejected("Actual issued constructor request required", stage="request")
    with _LOCK:
        if request in _CONSUMED or request.constructor_owner in _RETIRED:
            raise LifecycleRejected("Lifecycle epoch consumed", stage="consumed", request=request)
        refs = _REQUESTS[request]
        parent = refs[0]
        context = SimpleNamespace(
            request=request,
            refs=refs,
            parent=parent,
            api=api,
            phase=parent.phase,
            p=parent.p,
            cells=parent.cells,
            mesh=parent.mesh,
            mesh_dict=parent.mesh_dict,
            mask=parent.refs[6],
            rng=parent.rng,
            rand=parent.rand,
            draw_active=False,
            thread=get_ident(),
            active=True,
            invalid=False,
            validating=False,
            source_ready=False,
            stage="constructor_retirement",
            driver_frame=sys._getframe(),
            work=[],
            events=[],
            locals={},
            helper_results=[],
            helper_views=[],
            query_results=[],
            query_views=[],
            generator_results=[],
            generator_views=[],
            generator_interruptions=[],
            generator_observations=[],
            generator_suspensions={},
            admitted={},
            caught=[],
            entry_error=None,
            observation_error=None,
            capture_errors=(),
            capture_reporting_errors=(),
            cleanup_errors=(),
            primary=None,
            pending_source_error=None,
            trial=None,
            before=None,
            stream_before=None,
            stream_after=None,
            wrapper_claimed=False,
            root_claimed=False,
            method_claimed=False,
            root_returned=False,
            wrapper_frame=None,
            root_frame=None,
            body_parent_frame=None,
            delegate_frames={},
            helper_active=False,
            callback_codes=frozenset(),
            callback=parent.callback,
            forbidden_callback_codes=parent.forbidden_callback_codes,
            required_hooks=(sys.getprofile(), sys.gettrace()),
            restore_setters=(sys.setprofile, sys.settrace),
            restore_getters=(sys.getprofile, sys.gettrace),
        )
        _CONSUMED[request] = _RETIRED[request.constructor_owner] = context
        _ACTIVE.append(context)
        primary = capture = None
        healthy = False
        try:
            context.parent_claim = previous._claim_for_voronoi_lifecycle
            context.parent_check = previous._check_lifecycle_authority
            context.entries = MappingProxyType({DISPATCH_LABEL: _dispatch})
            _attempt(context, "actual_constructor_retirement", sys._getframe(), "authentication")
            if (
                context.parent_claim(
                    request.constructor_owner,
                    expected=parent,
                    transition=context,
                    entries=context.entries,
                )
                is not parent
            ):
                raise ValueError("Different constructor was retired")
            previous._same_epoch(parent, refs[3])
            context.checker = (
                api._independent_atoms,
                api._independent_atoms.__code__,
                api._independent_atoms.__globals__,
            )
            context.metadata_helpers = tuple(
                (name, fn, api._independent_atoms(fn))
                for name, fn in globals().items()
                if type(fn) is FunctionType and fn.__globals__ is globals()
            )
            context.plan = source_plan()
            context.native_method, context.native_wrapper = (
                parent.native_method,
                parent.native_wrapper,
            )
            context.objects = parent.objects
            context.stable_fields, context.final_fields = (
                [dict() for _ in context.objects],
                [dict() for _ in context.objects],
            )
            context.stable_view = SimpleNamespace(
                objects=context.objects, fields=context.stable_fields
            )
            context.mesh_fields = {}
            context.final_observations = dict(
                events=context.events, locals=context.locals, query_results=context.query_results
            )
            context.final_view = SimpleNamespace(
                objects=context.objects,
                fields=context.final_fields,
                mesh=None,
                mesh_fields=context.mesh_fields,
                mesh_attributes=None,
                helper_results=context.helper_results,
                helper_views=context.helper_views,
                query_results=context.query_results,
                query_views=context.query_views,
                generator_results=context.generator_results,
                generator_views=context.generator_views,
            )
            context.stable_tape = SimpleNamespace(rng=context.rng, events=(), draws=(), locals={})
            base_projector = parent.parent.parent.projector
            context.projector = SimpleNamespace(
                objects=[
                    *base_projector.objects,
                    ("issued_image_mask", context.mask),
                    ("issued_mesh", context.mesh),
                ]
            )
            context.inherited_graph = _graph(context)
            context.before, context.stream_before = _snapshot(context), _rng(context)
            context.stage = "original_lifecycle_namespace"
            _namespace(context)
            context.bindings = _bindings(context)
            context.source_ready = True
            _check(context)
            context.stage = "literal_branch_lifecycle"
            with warnings.catch_warnings(record=True) as caught:
                context.caught = caught
                with _account(context):
                    context.cells.make_voronoi(context.phase)
                    _guard(context)
                    _check(context)
            if (
                not context.root_returned
                or not context.method_claimed
                or any(row.get("pending_return", False) for row in context.admitted.values())
            ):
                raise ValueError("Original selected lifecycle did not return")
        except BaseException as error:
            primary = (
                context.entry_error
                if context.entry_error is not None
                else (
                    context.pending_source_error
                    if isinstance(error, previous.image.prefix.literal._CaptureStop)
                    else error
                )
            )
            context.primary = primary
        finally:
            try:
                healthy = _recover(context)
            except BaseException as error:
                context.capture_errors += (("recovery_entry_or_return", error, context),)
                if context.observation_error is None:
                    context.observation_error = error
                for index in (1, 0):
                    try:
                        context.restore_setters[index](context.required_hooks[index])
                    except BaseException as secondary:
                        context.cleanup_errors += (("emergency_restore", secondary, index),)
                # No serializers/issuance on an unauthenticated cleanup path.
                healthy = False
        capture = context.observation_error
        if healthy and context.before is not None:
            try:
                context.stream_after = _rng(context)
                value = Trial(
                    request.identity,
                    request.parent_identity,
                    request.witness.identity,
                    context.before,
                    _snapshot(context),
                    context.stream_before,
                    context.stream_after,
                    tuple((r["sequence"], r["name"], r["layer"], r["state"]) for r in context.work),
                    tuple(
                        (
                            w.category.__module__,
                            w.category.__qualname__,
                            str(w.message),
                            w.filename,
                            w.lineno,
                        )
                        for w in context.caught
                    ),
                    primary is None and capture is None and context.root_returned,
                    context.stage if primary is not None or capture is not None else None,
                    None if primary is None else type(primary).__qualname__,
                    None if capture is None else type(capture).__qualname__,
                    "",
                    _helper_snapshot(context),
                )
                context.trial = replace(value, identity=_digest(trial_record(value)))
                if primary is None and capture is None:
                    _check(context)
                    context.final_view.observations = context.final_observations
                    context.graph = _graph(context, final=True)
            except BaseException as error:
                context.capture_errors += (("final_sealing", error, context),)
                if capture is None:
                    capture = error
        try:
            healthy = _recover(context) and healthy
        except BaseException as error:
            context.capture_errors += (("post_sealing_recovery", error, context),)
            if capture is None:
                capture = error
            healthy = False
        if context.observation_error is not None and capture is None:
            capture = context.observation_error
        context.active = False
        if _ACTIVE and _ACTIVE[-1] is context:
            _ACTIVE.pop()
        else:
            context.invalid = True
        if (
            primary is not None
            or capture is not None
            or context.trial is None
            or not healthy
            or context.invalid
        ):
            if not healthy:
                context.invalid = True
                if primary is not None:
                    raise primary
                if capture is not None:
                    raise capture
                raise RuntimeError("Inherited hooks unavailable; raw lifecycle context retained")
            _failure(context, primary, capture)
        try:
            owner = object.__new__(LifecycleOwner)
            context.owner = owner
            _ISSUED[owner] = context
            return owner
        except BaseException as error:
            context.capture_errors += (("owner_issuance", error, context),)
            _failure(context, error, capture)


class LifecycleOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use the genuine constructor-to-lifecycle continuation")

    def __reduce_ex__(self, protocol):
        raise TypeError("No native mesh hydration or ordinary checkpoint")

    @property
    def phase(self):
        return _authority(self).phase

    @property
    def trial(self):
        return _authority(self).trial


def _authority(owner):
    if type(owner) is not LifecycleOwner or owner not in _ISSUED:
        raise LifecycleRejected("Actually issued lifecycle child required", stage="owner")
    context = _ISSUED[owner]
    if owner in _FORWARDED or getattr(context, "geometry", None) is not None:
        raise LifecycleRejected(
            "Lifecycle geometry epoch consumed", stage="consumed", trial=context.trial
        )
    if context.active or context.validating or context.invalid:
        _reject(context, None, "Unavailable/reentrant lifecycle child")
    context.validating = True
    try:
        _check(context)
        if (
            context.trial.source_completed is not True
            or context.trial.identity != _digest(trial_record(context.trial))
            or context.trial.cache.identity != _snapshot(context).identity
            or context.trial.helper_cache is None
            or context.trial.helper_cache.identity != _helper_snapshot(context).identity
            or context.trial.stream_after.identity != context.refs[1].stream_after.identity
        ):
            raise ValueError("Sealed lifecycle cache/trial/global-MT changed")
        graph = _graph(context, final=True)
        _same(graph[0], context.graph[0])
        if graph[1] != context.graph[1]:
            raise ValueError("Actual lifecycle mesh/alias/helper-result edges changed")
    except BaseException as error:
        context.invalid = True
        _failure(context, error, context.observation_error)
    finally:
        context.validating = False
    return context


def _claim_for_world_geometry(owner, *, expected, transition, entries):
    """Consume the actual sealed lifecycle epoch before any alias store."""
    module = previous.image.prefix.previous._world_api()._world_seed_geometry_api()
    caller = sys._getframe(1)
    with _LOCK:
        if (
            caller.f_code is not module.prepare.__code__
            or not module._ACTIVE
            or module._ACTIVE[-1] is not transition
            or type(owner) is not LifecycleOwner
            or _ISSUED.get(owner) is not expected
        ):
            raise LifecycleRejected("Actual active geometry issuer required", stage="entry")
        parent = expected
        if owner in _FORWARDED or getattr(parent, "geometry", None) is not None:
            raise LifecycleRejected("Lifecycle geometry epoch consumed", stage="consumed")
        if (
            parent.active
            or parent.invalid
            or parent.validating
            or parent.owner is not owner
            or transition.driver_frame is not caller
            or transition.parent is not parent
            or type(transition.request) is not module.Request
            or module._REQUESTS.get(transition.request) is not transition.refs
            or module._CONSUMED.get(transition.request) is not transition
            or module._RETIRED.get(owner) is not transition
            or transition.request.lifecycle_owner is not owner
            or transition.refs[0] is not parent
            or transition.refs[1] is not parent.trial
            or transition.phase is not parent.phase
            or transition.p is not parent.p
            or transition.cells is not parent.cells
            or transition.mesh is not parent.mesh
            or transition.mask is not parent.mask
            or transition.rng is not parent.rng
            or transition.thread != parent.thread
            or transition.thread != get_ident()
            or entries is not transition.entries
            or tuple(entries) != tuple("Cells." + name for name in module.METHODS)
            or any(entry is not module._dispatch for entry in entries.values())
        ):
            parent.invalid = transition.invalid = True
            raise ValueError("Actual same-caller lifecycle/geometry transition required")
        parent.geometry = transition  # Irreversible even if the next check refuses.
        try:
            _FORWARDED[owner] = transition
            _check(parent)
            if (
                parent.trial is not transition.refs[1]
                or parent.trial.source_completed is not True
                or parent.trial.identity != _digest(trial_record(parent.trial))
                or parent.trial.cache.identity != _snapshot(parent).identity
                or parent.trial.helper_cache.identity != _helper_snapshot(parent).identity
            ):
                raise ValueError("Original lifecycle seal changed before geometry")
            graph = _graph(parent, final=True)
            _same(graph[0], parent.graph[0])
            if graph[1] != parent.graph[1] or _geometry_route(parent)[0] is not transition:
                raise ValueError("Original lifecycle graph or retirement edge changed")
        except BaseException:
            parent.invalid = transition.invalid = True
            raise
        return parent


def _geometry_route(parent):
    """Authenticate real registry edges without reopening consumed caches."""
    module = previous.image.prefix.previous._world_api()._world_seed_geometry_api()
    child, owner = getattr(parent, "geometry", None), getattr(parent, "owner", None)
    if (
        child is None
        or owner is None
        or _ISSUED.get(owner) is not parent
        or _FORWARDED.get(owner) is not child
        or parent.active
        or parent.invalid
        or child.invalid
        or child.parent is not parent
        or type(child.request) is not module.Request
        or child.request.lifecycle_owner is not owner
        or module._REQUESTS.get(child.request) is not child.refs
        or module._CONSUMED.get(child.request) is not child
        or module._RETIRED.get(owner) is not child
        or child.refs[0] is not parent
        or child.refs[1] is not parent.trial
        or child.phase is not parent.phase
        or child.p is not parent.p
        or child.cells is not parent.cells
        or child.mesh is not parent.mesh
        or child.mask is not parent.mask
        or child.rng is not parent.rng
        or child.thread != parent.thread
        or child.thread != get_ident()
        or tuple(child.entries) != tuple("Cells." + name for name in module.METHODS)
        or any(entry is not module._dispatch for entry in child.entries.values())
    ):
        raise ValueError("Original lifecycle/geometry issuance or retirement links changed")
    return child, module


def _check_world_geometry_authority(transition):
    parent = transition.parent
    if _geometry_route(parent)[0] is not transition:
        raise ValueError("Different actual geometry transition")
    # Mesh/image/RNG and original caller fields remain immutable. New caller
    # stores are validated by the typed child, never against the old cache.
    _check(parent)
    if (
        parent.trial is not transition.refs[1]
        or parent.trial.source_completed is not True
        or parent.trial.identity != _digest(trial_record(parent.trial))
        or parent.trial.helper_cache.identity != _helper_snapshot(parent).identity
        or parent.trial.stream_after.identity != _rng(parent).identity
    ):
        raise ValueError("Retained lifecycle trial/helper/RNG authority changed")
    graph = _graph(parent, final=True)
    _same(graph[0], parent.graph[0])
    if graph[1] != parent.graph[1]:
        raise ValueError("Retained lifecycle mesh/image/reference edges changed")
    return parent


def require_caller_aliases(owner):
    context = _authority(owner)
    raise LifecycleRejected(
        "Caller aliases/cell_index remain held",
        stage="caller_tail_held",
        request=context.request,
        trial=context.trial,
    )
