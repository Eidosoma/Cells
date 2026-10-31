"""Issued literal Cells constructor/lattice owner before the live image picker.

The ordered parameter stores have the existing normalized scalar boundary;
this is not full Parameters/YAML/SimPhase/package authority. SeedState and
Prelude are comparison evidence, never instructions for hydrating a caller.
All positive constructor, lattice, RNG and authentication replay work is held.
"""

import ast
import hashlib
import json
import math
import sys
import warnings
from dataclasses import dataclass, replace
from pathlib import Path
from threading import get_ident
from types import FunctionType
from weakref import WeakKeyDictionary

import numpy as np

from cells.processes import betse_native_single_cell_caller_lattice_source as source
from cells.processes import betse_native_single_cell_core_preparation as core

LAW_ID = "betse_owned_single_cell_Cells_lattice_source_prerequisite@1"
INVALIDATED_OWNERS = core.INVALIDATED_OWNERS
HELD_UNQUALIFIED_SOURCE_STAGE = True
NATIVE_ROOT = Path("/mnt/workspaces/Cells/betse-v1.5.0")
DEPENDENCIES = {
    "betse_native_single_cell_core_preparation": (
        "b1db6df0c74f92d4526b9854c7d01838552e2ec044858e64e43c93f7ce8b068a"
    ),
    "betse_lattice_seed_generation": (
        "d1e20f37d37007460229edde9484513dad7f36642c1ec83a9c80e4640eb52df6"
    ),
    "betse_image_mask_prelude": "e8e14819df8a80692c2c3990189aaccb2e375a6c984c2cd8dc727ce80e2ce03b",
}
_ISSUED = WeakKeyDictionary()
_ACTIVE = WeakKeyDictionary()


@dataclass(frozen=True, slots=True)
class Request:
    core_request: core.Request
    identity: str


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    constructor_cache: object
    parameters_cache: object
    cache: object
    audit: object
    events: tuple
    stream_after: object
    warnings: tuple
    status: str
    failure_stage: str | None
    failure_type: str | None
    failure_message: str | None
    identity: str


class CallerRejected(ValueError):
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


class _Parameters(source.ParameterStores):
    def __init__(self, recipe):
        # Explicit normalized scalar inputs, not derived counts or SeedState.
        self.world_len = float(recipe["world_len_m"])
        self.cell_radius = float(recipe["cell_radius_m"])
        self.cell_lattice_disorder = float(recipe["lattice_disorder"])
        self.cell_lattice_type = source.CellLatticeType[recipe["lattice_type"]]
        self.initialize_source_stores()


class _Runtime(source.CellsKernel):
    def _make_cell_lattice(self, p):
        if _ACTIVE.get(self) != get_ident():
            raise CallerRejected(
                "Original lattice driver authority unavailable", stage="source_call_unavailable"
            )
        return self._cells_original_lattice(self, p)

    def __reduce_ex__(self, protocol):
        raise TypeError("A live Cells source caller cannot be serialized as authority")

    def make_voronoi(self, phase):
        raise CallerRejected(
            "Live image-picker/mask ownership is not implemented",
            stage="live_image_mask_unavailable",
        )

    def cell_index(self, p):
        raise CallerRejected(
            "make_voronoi has no complete live caller/image/mesh authority",
            stage="caller_continuation_unavailable",
        )


def _public(caller):
    return {k: v for k, v in vars(caller).items() if not k.startswith("_cells_")}


def _parameters(p):
    return {k: v.name if k == "cell_lattice_type" else v for k, v in vars(p).items()}


def _digest(value):
    return core.records._digest(value)


def _verify_sources():
    core._verify_sources()
    modules = (core, core.initial.image_stage.lattice, core.initial.image_stage, source)
    pins = {}
    for module in modules:
        path = Path(module.__file__)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        name = module.__name__.rsplit(".", 1)[-1]
        if name in DEPENDENCIES and digest != DEPENDENCIES[name]:
            raise ValueError("Changed upstream source: " + name)
        pins[str(path.resolve())] = digest
    for name, expected in source.NATIVE_PINS.items():
        path = NATIVE_ROOT / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Original native caller source unavailable/changed: " + name)
    tree = ast.parse(Path(source.__file__).read_text())
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    for method in ("__init__", "_make_cell_lattice"):
        node = next(
            n
            for n in classes["CellsKernel"].body
            if isinstance(n, ast.FunctionDef) and n.name == method
        )
        if hashlib.sha256(ast.dump(node).encode()).hexdigest() != source.SITES["Cells." + method]:
            raise ValueError("Changed literal Cells method: " + method)
    stores = next(n for n in classes["ParameterStores"].body if isinstance(n, ast.FunctionDef)).body
    if (
        hashlib.sha256(ast.dump(ast.Module(body=stores, type_ignores=[])).encode()).hexdigest()
        != source.SITES["parameter_stores"]
    ):
        raise ValueError("Changed original ordered parameter stores")
    for name in ("BetseException", "BetseSimException", "BetseSimConfException"):
        if hashlib.sha256(ast.dump(classes[name]).encode()).hexdigest() != source.SITES[name]:
            raise ValueError("Changed original exception hierarchy: " + name)
    pins[str(Path(__file__).resolve())] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return pins


def _precheck(parent):
    if type(parent) is not core.Request:
        raise CallerRejected(
            "Typed owned single-cell core request required; no supplied caller/cache/phase",
            stage="upstream_request_owner",
        )
    core._precheck(parent.initial_request, parent.initial_state)
    binding, seed, prelude = parent.initial_request.upstream
    if (
        type(binding) is not core.initial.image_stage.lattice.Binding
        or type(seed) is not core.initial.image_stage.lattice.SeedState
        or type(prelude) is not core.initial.image_stage.Prelude
        or seed.binding_identity != binding.identity
        or prelude.lattice_state_identity != seed.identity
        or json.loads(prelude.controls_json)["single_cell"] is not True
        or seed.stream_after.identity != parent.initial_request.stream_before.identity
    ):
        raise CallerRejected(
            "Complete owned single-cell seed/image evidence required", stage="upstream_evidence"
        )


def request_record(request):
    parent = request.core_request
    binding, seed, prelude = parent.initial_request.upstream
    return dict(
        law=LAW_ID,
        core_request_identity=parent.identity,
        core_request=core.request_record(parent),
        normalized_parameter_stores_only=True,
        seed_evidence=core.initial.image_stage.lattice.state_record(seed),
        binding_evidence=core.initial.image_stage.lattice.binding_record(binding),
        image_prelude_identity=prelude.identity,
    )


def from_core_request(parent, *, law_id):
    if law_id != LAW_ID or type(law_id) is not str:
        raise CallerRejected("Explicit caller source-law opt-in required", stage="opt_in")
    _precheck(parent)
    if _digest(core.request_record(parent)) != parent.identity:
        raise CallerRejected("Changed original core request", stage="upstream_identity")
    value = Request(parent, "")
    return replace(value, identity=_digest(request_record(value)))


def _validate_request(request):
    if type(request) is not Request:
        raise CallerRejected(
            "Typed caller lattice request required", stage="request_owner", request=request
        )
    expected = from_core_request(request.core_request, law_id=LAW_ID)
    if request.identity != expected.identity:
        raise CallerRejected(
            "Changed caller source request", stage="request_identity", request=request
        )
    # Numerical replay, not metadata: one existing seed authentication replay.
    binding, seed, _ = request.core_request.initial_request.upstream
    core.initial.image_stage.lattice.validate_state(binding, seed)
    return binding, seed


class _Tape:
    def __init__(self, rng):
        self.rng, self.draws, self.events, self.locals = rng, [], [], {}
        self.original_error = None

    def rand(self, *shape):
        if math.prod(shape) > 128:
            raise ValueError("Native lattice draw exceeds original source bound")
        frame = sys._getframe(1)
        before = core.initial._rng_stream(self.rng)
        values = self.rng.rand(*shape)
        self.draws.append(
            dict(
                shape=shape,
                values=values,
                before=before,
                after=core.initial._rng_stream(self.rng),
                before_locals=dict(frame.f_locals),
            )
        )
        return values

    def trace(self, frame, event, arg):
        if frame.f_code in self.codes and event in ("call", "return", "exception"):
            self.locals = dict(frame.f_locals)
            if event == "exception":
                self.original_error = arg[1]
            self.events.append(
                dict(
                    method=frame.f_code.co_name,
                    kind=event,
                    attributes=_public(frame.f_locals["self"]),
                )
            )
        return self.trace

    def log_info(self, *args):
        self.events.append(dict(method="logs.log_info", kind="log", arguments=args))


class _Numpy:
    def __init__(self, tape):
        self.random = tape

    def __getattr__(self, name):
        return getattr(np, name)


def _body(tape):
    namespace = dict(source.CellsKernel._make_cell_lattice.__globals__)
    namespace.update(np=_Numpy(tape), logs=tape)
    return FunctionType(
        source.CellsKernel._make_cell_lattice.__code__, namespace, "_make_cell_lattice"
    )


def _equal(actual, expected, label):
    if actual is None or expected is None:
        if actual is not expected:
            raise ValueError("Changed source buffer: " + label)
        return
    a, b = np.asarray(actual), np.asarray(expected)
    if a.shape != b.shape or a.dtype != b.dtype or a.tobytes(order="C") != b.tobytes(order="C"):
        raise ValueError("Changed exact source buffer: " + label)


def _audit(caller, p, tape, seed, binding):
    if len(tape.draws) != 2:
        raise ValueError("Native lattice must retain both original draw blocks")
    before = tape.draws[0]["before_locals"]
    local = tape.locals
    # Assemble inspection records only; these never populate the live caller.
    base = np.column_stack((before["x_2d"].ravel(), before["y_2d"].ravel()))
    blue = red = None
    if binding.definition["lattice_type"] == "HEX":
        blue = np.column_stack((local["x_2d_blue"].ravel(), local["y_2d_blue"].ravel()))
        red = np.column_stack((local["x_2d_red"].ravel(), local["y_2d_red"].ravel()))
    actual = (
        base,
        blue,
        red,
        tape.draws[0]["values"],
        tape.draws[1]["values"],
        local["x_rnd"],
        local["y_rnd"],
        local["xypts"],
        local["bbox"],
        caller.clust_xy,
        caller.bbox,
        caller.centre,
        np.asarray(caller.xyaxis),
    )
    for name, value, expected in zip(seed.values._fields, actual, seed.values, strict=True):
        _equal(value, expected, name)
    for draw, (_, shape, count) in zip(tape.draws, seed.draw_order, strict=True):
        if draw["shape"] != shape or draw["values"].size != count:
            raise ValueError("Changed original lattice draw shape/order")
    if (
        tape.draws[0]["before"].identity != seed.stream_before.identity
        or tape.draws[-1]["after"].identity != seed.stream_after.identity
        or core.initial._rng_stream(tape.rng).identity != seed.stream_after.identity
        or len(caller.clust_xy) != len(seed.occurrence_ids)
    ):
        raise ValueError("Changed original complete RNG or occurrence epoch")
    q = binding.parameters
    expected = dict(
        wsx=q.expanded_width_m,
        wsy=q.expanded_height_m,
        ac=q.drawing_gap_m,
        d_cell=q.diameter_m,
        nx=q.nx,
        ny=q.ny,
    )
    for name, value in expected.items():
        _equal(getattr(p, name), value, "parameter/" + name)
    return core.caches.snapshot(
        dict(
            values=dict(zip(seed.values._fields, actual, strict=True)),
            draw_shapes=[d["shape"] for d in tape.draws],
            point_ids=seed.occurrence_ids,
        )
    )


def trial_record(trial):
    return dict(
        request=trial.request_identity,
        constructor_cache=trial.constructor_cache.identity,
        parameters_cache=trial.parameters_cache.identity,
        cache=trial.cache.identity,
        audit=None if trial.audit is None else trial.audit.identity,
        events=[e.identity for e in trial.events],
        stream_after=trial.stream_after.identity,
        warnings=trial.warnings,
        status=trial.status,
        failure_stage=trial.failure_stage,
        failure_type=trial.failure_type,
        failure_message=trial.failure_message,
        normalized_parameters_only=True,
        live_image_mask_available=False,
        executable_DEC_parent_admitted=False,
        physical_geometry_admitted=False,
        invalidated_owners=INVALIDATED_OWNERS,
    )


def _graph(caller, p, tape):
    objects, seen = [], set()

    def visit(value):
        if (
            id(value) in seen
            or value is None
            or isinstance(value, (str, bool, int, float, np.generic))
        ):
            return
        if len(objects) > core.caches.MAX_TREE_NODES:
            raise ValueError("Bounded live caller graph exhausted")
        seen.add(id(value))
        objects.append(value)
        if isinstance(value, np.ndarray):
            visit(value.base)
            if value.dtype.hasobject:
                for item in value.flat:
                    visit(item)
        elif isinstance(value, dict):
            for key, item in value.items():
                visit(key)
                visit(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                visit(item)

    for value in (
        caller,
        p,
        tape,
        tape.rng,
        vars(caller),
        vars(p),
        tape.events,
        tape.draws,
        tape.locals,
    ):
        visit(value)
    return tuple(objects)


class CallerOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use prepare with an owned caller request")

    def __reduce_ex__(self, protocol):
        raise TypeError("Caller source authority cannot be serialized")

    @property
    def cells(self):
        return _validate_owner(self)["caller"]

    @property
    def trial(self):
        return _authority(self)["trial"]


def _authority(owner):
    if type(owner) is not CallerOwner or owner not in _ISSUED:
        raise CallerRejected(
            "Issued live caller authority unavailable", stage="caller_authority_unavailable"
        )
    return _ISSUED[owner]


def _validate_owner(owner):
    value = _authority(owner)
    try:
        if value["invalid"] or _verify_sources() != value["producers"]:
            raise ValueError("Changed source authority")
        if _digest(request_record(value["request"])) != value["request"].identity:
            raise ValueError("Changed request evidence")
        if core.caches.snapshot(_public(value["caller"])).identity != value["trial"].cache.identity:
            raise ValueError("Changed source caller cache")
        if (
            core.caches.snapshot(_parameters(value["parameters"])).identity
            != value["trial"].parameters_cache.identity
        ):
            raise ValueError("Changed actual source parameters")
        if (
            core.initial._rng_stream(value["tape"].rng).identity
            != value["trial"].stream_after.identity
        ):
            raise ValueError("Changed original RNG epoch")
        binding, seed, _ = value["request"].core_request.initial_request.upstream
        if (
            _audit(value["caller"], value["parameters"], value["tape"], seed, binding).identity
            != value["trial"].audit.identity
        ):
            raise ValueError("Changed source draw/local-buffer evidence")
        if tuple(core.caches.snapshot(e).identity for e in value["tape"].events) != tuple(
            e.identity for e in value["trial"].events
        ):
            raise ValueError("Changed actual source event sequence")
        if _bindings(value["caller"]) != value["bindings"]:
            raise ValueError("Changed actual constructor/lattice method bindings")
        graph = _graph(value["caller"], value["parameters"], value["tape"])
        if len(graph) != len(value["graph"]) or any(
            a is not b for a, b in zip(graph, value["graph"], strict=True)
        ):
            raise ValueError("Changed original objects or aliases")
    except Exception as error:
        value["invalid"] = True
        raise CallerRejected(
            "Stale live caller refused without replay",
            stage="caller_authority_drift",
            request=value["request"],
            trial=value["trial"],
            source_error=error,
        ) from error
    return value


def _bindings(caller):
    methods = (
        _Runtime.__init__,
        _Runtime._make_cell_lattice,
        source.CellsKernel.__init__,
        source.CellsKernel._make_cell_lattice,
        _Parameters.initialize_source_stores,
    )
    return (
        type(caller),
        *((method, method.__code__) for method in methods),
        caller._cells_original_lattice.__code__,
    )


def prepare(request):
    if type(request) is not Request:
        raise CallerRejected(
            "Typed caller lattice request required", stage="request_owner", request=request
        )
    producers = _verify_sources()
    binding, seed = _validate_request(request)
    caller = p = rng = tape = None
    captured = {}
    error, stage, audit = None, "parameter_stores", None
    try:
        p = object.__new__(_Parameters)
        p.__init__(binding.definition)
        captured["parameters"] = core.caches.snapshot(_parameters(p))
        saved = core.initial.streams.native_stream_manifest(seed.stream_before)["state"]
        stage = "RNG_constructor"
        rng = np.random.RandomState(0)
        rng.set_state((saved[0], np.asarray(saved[1], np.uint32), saved[2], saved[3], saved[4]))
        tape = _Tape(rng)
        caller = object.__new__(_Runtime)
        caller._cells_original_lattice = _body(tape)
        tape.codes = {_Runtime.__init__.__code__, caller._cells_original_lattice.__code__}
        previous = sys.gettrace()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _ACTIVE[caller] = get_ident()
            try:
                sys.settrace(tape.trace)
                stage = "Cells.__init__"
                caller.__init__(p)
                captured["constructor"] = core.caches.snapshot(_public(caller))
                stage = "Cells._make_cell_lattice"
                caller._make_cell_lattice(p)
            finally:
                sys.settrace(previous)
                _ACTIVE.pop(caller, None)
        stage = "exact_seed_evidence"
        audit = _audit(caller, p, tape, seed, binding)
    except Exception as failure:
        error = failure
    partial = dict(
        caller=caller,
        parameters=p,
        rng=rng,
        tape=tape,
        last_successful_snapshots=captured,
        source_stage=stage,
        usable_live_owner_available=False,
    )
    try:
        if caller is None or p is None or tape is None or "constructor" not in captured:
            raise ValueError("Source construction ended before a complete caller trial")
        captured["final"] = core.caches.snapshot(_public(caller))
        trial = Trial(
            request.identity,
            captured["constructor"],
            captured["parameters"],
            captured["final"],
            audit,
            tuple(core.caches.snapshot(event) for event in tape.events),
            core.initial._rng_stream(rng),
            tuple(str(w.message) for w in caught),
            "source_lattice_completed_unqualified" if error is None else "retained_source_failure",
            None if error is None else stage,
            None if error is None else type(error).__name__,
            None if error is None else str(error),
            "",
        )
        trial = replace(trial, identity=_digest(trial_record(trial)))
    except Exception as capture_error:
        raise CallerRejected(
            "Caller trial sealing refused",
            stage="capture",
            request=request,
            partial=partial,
            source_error=error,
            capture_error=capture_error,
        ) from (error if error is not None else capture_error)
    if error is not None:
        raise CallerRejected(
            "Original caller source refused",
            stage=stage,
            request=request,
            trial=trial,
            partial=partial,
            source_error=error,
        ) from error
    try:
        if _verify_sources() != producers:
            raise ValueError("Producer drift during caller execution")
        graph = _graph(caller, p, tape)
        owner = object.__new__(CallerOwner)
        _ISSUED[owner] = dict(
            request=request,
            caller=caller,
            parameters=p,
            tape=tape,
            trial=trial,
            producers=producers,
            graph=graph,
            bindings=_bindings(caller),
            invalid=False,
        )
        return owner
    except Exception as capture_error:
        raise CallerRejected(
            "Live caller issuance refused",
            stage="issuance",
            request=request,
            trial=trial,
            partial=partial,
            capture_error=capture_error,
        ) from capture_error


def require_voronoi_continuation(owner, *, image_owner=None, mesh_owner=None):
    value = _validate_owner(owner)
    raise CallerRejected(
        "Live image-mask caller provenance is unavailable; stored Prelude is inspection evidence",
        stage="live_image_mask_unavailable",
        request=value["request"],
        trial=value["trial"],
        partial=dict(
            image_owner=image_owner,
            mesh_owner=mesh_owner,
            separate_mesh_RNG_epoch_equality_is_not_shared_RNG_identity=True,
            executable_DEC_parent_admitted=False,
            invalidated_owners=INVALIDATED_OWNERS,
        ),
    )
