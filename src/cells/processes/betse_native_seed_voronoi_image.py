"""Prepared same-phase make_voronoi image prefix, before every mesh branch.

The only parent is the issued fresh-world SEED/lattice child. Image arguments
are read by the literal body from its actual p; no Prelude, normalized caller,
replacement phase or RNG is accepted. All new dependency pins remain unbound.
"""

import ast
import builtins
import hashlib
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import CodeType, FunctionType, MappingProxyType, MethodType, ModuleType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_seed_voronoi_image_source as source
from cells.processes import betse_native_seed_world_prefix as prefix
from cells.processes import betse_native_single_cell_image_mask as images

PARENT_MODULE = "cells.processes.betse_native_seed_world_prefix"
MODE = "fresh_world_seed_lattice_make_voronoi_image_prefix"
LAW_ID = "betse_same_seed_phase_voronoi_actual_image_prefix@1"
RELEASE = "CELLS_NATIVE_SEED_VORONOI_IMAGE_RELEASED"
SOURCE_SHA256 = None
IMAGE_SOURCE_SHA256 = None
IMAGE_HELPERS_SHA256 = None
ROOT_METHOD = "Cells.make_voronoi"
CORE_METHODS = (
    "TissuePickerImage.__init__",
    "TissuePickerImage.get_image_mask",
    "TissuePickerImageMask.__init__",
)
RETURN_ORDER = (CORE_METHODS[0], CORE_METHODS[2], CORE_METHODS[1], ROOT_METHOD)
WRAPPER_METHOD = "original_Cells.make_voronoi_wrapper"
NUMPY_HELPERS = ("zeros", "flipud", "linspace", "meshgrid", "column_stack")
HELPER_MODULES = ("pathnames", "files", "dirs", "paths", "nparray", "pilnumpy", "Image")
IMPORT = "betse.science.tissue.picker.tispickimage"
MAX_WORK = prefix.MAX_WORK
_REQUESTS, _CONSUMED, _ISSUED = (WeakKeyDictionary() for _ in range(3))
_PLANS = WeakKeyDictionary()
_ACTIVE, _LOCK = [], RLock()
_LITERAL_CLASS = source.VoronoiImagePrefix
_LITERAL_FUNCTION = vars(_LITERAL_CLASS)["make_voronoi"]
_LITERAL_CODE = _LITERAL_FUNCTION.__code__


class VoronoiImageRejected(ValueError):
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


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    prefix_owner: object
    parent_identity: str
    source_identity: str
    mode: str
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("A live same-phase prefix cannot be hydrated")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    parent_identity: str
    before: object
    cache: object
    input_receipts: tuple
    return_order: tuple
    work: tuple
    source_completed: bool
    failure_stage: str | None
    source_error_type: str | None
    capture_error_type: str | None
    identity: str


def _digest(value):
    return prefix._digest(value)


def _body(node):
    nodes = list(node.body)
    if nodes and isinstance(nodes[0], ast.Expr) and isinstance(nodes[0].value, ast.Constant):
        if isinstance(nodes[0].value.value, str):
            nodes.pop(0)
    return nodes


def _literal_callable(
    payload, filename, namespace, *, expected_class, expected_function, with_binding=False
):
    """Compare loaded definitions with compiled bytes, without executing them.

    Pure metadata comparison only. The production caller separately requires
    the exact reviewed source-file pin and canonical module/initial identities.
    """
    if type(payload) is not bytes or type(filename) is not str or type(namespace) is not dict:
        raise ValueError("Exact literal bytes, filename and actual module namespace required")
    compiled = compile(payload, filename, "exec", dont_inherit=True)
    classes = [
        code
        for code in compiled.co_consts
        if type(code) is CodeType and code.co_name == "VoronoiImagePrefix"
    ]
    methods = (
        []
        if len(classes) != 1
        else [
            code
            for code in classes[0].co_consts
            if type(code) is CodeType and code.co_name == "make_voronoi"
        ]
    )
    cls = namespace.get("VoronoiImagePrefix")
    if len(methods) != 1 or type(cls) is not type or cls is not expected_class:
        raise ValueError("One original plain literal class/method required")
    function = vars(cls).get("make_voronoi")
    code = None if type(function) is not FunctionType else function.__code__
    if (
        type(function) is not FunctionType
        or function is not expected_function
        or function.__globals__ is not namespace
        or code != methods[0]
        or code.co_filename != filename
        or function.__defaults__ is not None
        or function.__kwdefaults__ is not None
        or function.__closure__ is not None
        or vars(function)
        or getattr(function, "__annotate__", None) is not None
        or function.__annotations__
        or function.__module__ != namespace.get("__name__")
        or function.__name__ != "make_voronoi"
        or function.__qualname__ != "VoronoiImagePrefix.make_voronoi"
        or cls.__module__ != namespace.get("__name__")
    ):
        raise ValueError("Loaded literal code/signature/context differs from exact source bytes")
    return (cls, function, code, namespace) if with_binding else function


def _root_literal():
    path = Path(source.__file__)
    if path.is_symlink() or not prefix.previous._world_api()._pin(SOURCE_SHA256):
        raise ValueError("Reviewed canonical root literal remains unavailable")
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != SOURCE_SHA256:
        raise ValueError("Exact pinned root literal bytes changed")
    binding = _literal_callable(
        payload,
        str(path.resolve()),
        vars(source),
        expected_class=_LITERAL_CLASS,
        expected_function=_LITERAL_FUNCTION,
        with_binding=True,
    )
    if binding[2] is not _LITERAL_CODE:
        raise ValueError("Original loaded root literal class/function identity changed")
    return binding


def _check_root_literal(context):
    cls, function, code, namespace = context.literal_binding
    if (
        context.literal_namespace is not namespace
        or namespace.get("VoronoiImagePrefix") is not cls
        or vars(cls).get("make_voronoi") is not function
        or function.__code__ is not code
        or function.__globals__ is not namespace
        or function.__defaults__ is not None
        or function.__kwdefaults__ is not None
        or function.__closure__ is not None
        or vars(function)
        or getattr(function, "__annotate__", None) is not None
        or function.__annotations__
    ):
        raise ValueError("Authenticated root literal changed after source comparison")


def source_plan():
    """Literal/source declaration only, never constructor or parameter replay."""
    path = prefix.aliases.NATIVE / source.NATIVE_FILE
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != source.NATIVE_SHA256:
        raise ValueError("Exact original Cells source required")
    native = ast.parse(path.read_bytes())
    cls = next(
        node for node in native.body if isinstance(node, ast.ClassDef) and node.name == "Cells"
    )
    method = next(
        node
        for node in cls.body
        if isinstance(node, ast.FunctionDef) and node.name == "make_voronoi"
    )
    selected = _body(method)[:4]
    copied = ast.parse(Path(source.__file__).read_bytes())
    copied_cls = next(node for node in copied.body if isinstance(node, ast.ClassDef))
    copied_method = next(node for node in copied_cls.body if isinstance(node, ast.FunctionDef))

    def dump(nodes):
        return ast.dump(ast.Module(body=nodes, type_ignores=[]), include_attributes=False)

    if (
        len(selected) != 4
        or dump(selected) != dump(_body(copied_method))
        or ast.unparse(_body(method)[4]).split(" = ", 1)[0] != "lattice_to_mesh_type"
    ):
        raise ValueError("Literal log/import/picker/get_image_mask boundary changed")
    for name, expected in images.source.NATIVE_PINS.items():
        native_path = prefix.aliases.NATIVE / name
        if (
            native_path.is_symlink()
            or hashlib.sha256(native_path.read_bytes()).hexdigest() != expected
        ):
            raise ValueError("Original read-only image helper source changed: " + name)
    return dict(
        law=LAW_ID,
        mode=MODE,
        parent_module=PARENT_MODULE,
        source_pin=SOURCE_SHA256,
        image_literal_pin=IMAGE_SOURCE_SHA256,
        image_helpers_pin=IMAGE_HELPERS_SHA256,
        native_source=source.NATIVE_SHA256,
        source_lines=(selected[0].lineno, selected[-1].end_lineno),
        order=(
            "native log",
            "original lazy import",
            "actual p picker arguments",
            "actual Cells mask bounds",
        ),
        root=ROOT_METHOD,
        return_order=RETURN_ORDER,
        arguments="phase.p.tissue_default.picker_image_filename and phase.p.conf_dirname",
        caller_stores_permitted=(),
        actual_global_rng_may_advance=False,
        helper_binding="one-way coordinator full image-module binding; no reciprocal parent hash",
        image_helpers_reused_read_only=True,
        no_prelude_or_supplied_image_arguments=True,
        preserves_flipud_negative_view_and_array_base=True,
        stop_before="lattice_to_mesh_type/DECMesh",
        phase_mesh_physical_checkpoint_admission=False,
        source_or_scientific_release=False,
        invalidated_owners=11,
        held_postcut_cases=12,
    )


def _ready():
    api = prefix.previous._world_api()
    if api._world_voronoi_api() is not sys.modules.get(__name__):
        raise VoronoiImageRejected("Actual canonical image module required", stage="producer")
    for module, expected in (
        (source, SOURCE_SHA256),
        (images.source, IMAGE_SOURCE_SHA256),
        (images, IMAGE_HELPERS_SHA256),
    ):
        if not api._pin(expected):
            raise VoronoiImageRejected(
                "Reviewed image/helper pins remain unbound", stage="unbound_image_helpers"
            )
        path = Path(module.__file__)
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise VoronoiImageRejected("Original image/helper producer changed", stage="producer")
    return api


def request_record(request):
    return dict(
        law=LAW_ID,
        mode=request.mode,
        parent=request.parent_identity,
        source=request.source_identity,
        next_boundary="before DECMesh",
    )


def from_prefix(owner, *, law_id, mode=MODE):
    _ready()  # No unadopted owner, parameter descriptor or file inspection.
    if type(law_id) is not str or law_id != LAW_ID or type(mode) is not str or mode != MODE:
        raise VoronoiImageRejected("Exact explicit image source mode required", stage="law")
    parent = prefix._validate(owner)
    plan = source_plan()
    value = Request(owner, parent.trial.identity, _digest(plan), mode, "")
    value = replace(value, identity=_digest(request_record(value)))
    _REQUESTS[value] = (parent, parent.trial, parent.phase, parent.p, parent.cells)
    _PLANS[value] = plan
    return value


def _reject(context, row, reason):
    context.invalid = True
    if row is not None:
        row["state"] = "rejected_before_body"
    if context.entry_error is None:
        context.entry_error = VoronoiImageRejected(
            reason, stage="source_entry", request=context.request
        )
    raise context.entry_error


def _guard(context):
    if context.entry_error is not None:
        raise context.entry_error
    if context.observation_error is not None:
        raise prefix.literal._CaptureStop()
    if (
        context.invalid
        or not context.active
        or context.thread != get_ident()
        or not _ACTIVE
        or _ACTIVE[-1] is not context
    ):
        _reject(context, None, "Inactive/poisoned/foreign-thread image attempt")


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
        _reject(context, None, "Bounded image source work exhausted")
    context.work.append(row)
    return row


def _capture_failure(context, error, origin, raw):
    context.capture_failures += ((origin, error, raw),)
    if context.observation_error is None:
        context.observation_error = error
        context.observation_origin, context.observation_raw = origin, raw
    try:
        prefix._remember(context, error, origin, raw)
    except BaseException as secondary:
        context.capture_reporting_errors += ((origin, secondary, error, raw),)


def _check_bootstrap(context):
    fn, code, namespace = context.bootstrap_validator
    if (
        context.api._independent_atoms is not fn
        or fn.__code__ is not code
        or fn.__globals__ is not namespace
    ):
        raise ValueError("Original independent metadata checker changed")
    for helper, retained in context.bootstrap:
        actual = fn(helper)
        if len(actual) != len(retained) or any(
            a is not b for a, b in zip(actual, retained, strict=True)
        ):
            raise ValueError("Original image atom/comparison helper changed")


def _observer_bindings(context=None):
    if context is None and not _ACTIVE:
        raise ValueError("Actual active image observer required")
    context = _ACTIVE[-1] if context is None else context
    _check_bootstrap(context)
    result = tuple(
        atom
        for fn in (
            _admit,
            _capture,
            _capture_failure,
            _guard,
            _check,
            _epoch,
            _same_epoch,
            prefix._account,
            prefix._account.__wrapped__,
            images._Tape.trace,
            images._graph,
            images._event_record,
            images._namespace,
            _ImageTape.open,
            _ImageTape.spline,
            _ImageTape.convex_hull,
            _ImageTape.log_info,
            _ImageTape.log_debug,
            _ImageTape.finish_inputs,
        )
        for atom in prefix._atoms(fn)
    )
    scope = context.observer_scope
    return (
        *result,
        context.observer_function,
        scope,
        *(atom for pair in (() if scope is None else scope.items()) for atom in pair),
    )


def _bindings(context):
    _check_bootstrap(context)
    functions = (
        source_plan,
        _ready,
        request_record,
        from_prefix,
        prepare,
        _authority,
        _reject,
        _guard,
        _attempt,
        _capture_failure,
        _check_bootstrap,
        _observer_bindings,
        _bindings,
        _check,
        _admit,
        _capture,
        _observe,
        _operation,
        _values,
        _epoch,
        _same_epoch,
        _namespace,
        _namespace_bindings,
        _call_atoms,
        _module_atoms,
        _wrapper_guard,
        _dispatch,
        _partial,
        trial_record,
        _account,
        _account.__wrapped__,
        _retire_inputs,
        _restore_required_hooks,
        _literal_callable,
        _root_literal,
        _check_root_literal,
        _check_namespace_bindings,
        _raise_issuance_failure,
    )
    return (
        MODE,
        LAW_ID,
        RELEASE,
        SOURCE_SHA256,
        IMAGE_SOURCE_SHA256,
        IMAGE_HELPERS_SHA256,
        ROOT_METHOD,
        CORE_METHODS,
        RETURN_ORDER,
        WRAPPER_METHOD,
        NUMPY_HELPERS,
        HELPER_MODULES,
        MAX_WORK,
        _REQUESTS,
        _CONSUMED,
        _ISSUED,
        _ACTIVE,
        _LOCK,
        _PLANS,
        source,
        images,
        prefix,
        context.api,
        source.NATIVE_FILE,
        source.NATIVE_SHA256,
        _LITERAL_CLASS,
        _LITERAL_FUNCTION,
        _LITERAL_CODE,
        images.source.NATIVE_PINS,
        *(atom for pair in images.source.NATIVE_PINS.items() for atom in pair),
        *context.bootstrap_validator,
        *context.bootstrap,
        context.restore_setters,
        context.restore_getters,
        *context.restore_setters,
        *context.restore_getters,
        context.required_hooks,
        *context.required_hooks,
        *(atom for fn in functions for atom in prefix._atoms(fn)),
        *(
            atom
            for cls in (Request, Trial, VoronoiImageOwner, _ImageTape)
            for atom in prefix.literal._surface(cls)
        ),
        *(
            atom
            for fn in (
                images._namespace,
                images._graph,
                images._linear,
                images.Image.open,
                images.RectBivariateSpline,
                images.ConvexHull,
                os.dup,
                os.pread,
                os.fstat,
                os.close,
                sys.setprofile,
                sys.settrace,
                sys.getprofile,
                sys.gettrace,
            )
            for atom in prefix._atoms(fn)
        ),
        *(
            atom
            for fn in (context.native_method, context.native_wrapper)
            for atom in prefix._atoms(fn)
        ),
        context.parent.native_logs,
        *(
            atom
            for fn in (context.parent.native_logs.log_info, context.parent.native_logs.log_debug)
            for atom in _call_atoms(fn)
        ),
        *(atom for cls in (images.Image.Image,) for atom in prefix.literal._surface(cls)),
        images.core.caches.MAX_ARRAY_ELEMENTS,
        images.core.caches.MAX_TREE_NODES,
    )


def _check(context):
    if context.active:
        _guard(context)
    _check_bootstrap(context)
    if (
        _ready() is not context.api
        or prefix._check_voronoi_authority(context) is not context.parent
    ):
        raise ValueError("Actual retained prefix/image authority changed")
    if (
        _REQUESTS.get(context.request) is not context.refs
        or _CONSUMED.get(context.request) is not context
        or context.phase is not context.parent.phase
        or context.cells is not context.parent.cells
        or context.p is not context.parent.p
        or context.phase.p is not context.p
        or context.phase.cells is not context.cells
        or context.request.parent_identity != context.parent.trial.identity
        or _PLANS.get(context.request) is not context.plan
        or context.request.source_identity != _digest(context.plan)
        or context.request.identity != _digest(request_record(context.request))
    ):
        raise ValueError("Original actual phase/p/Cells/request changed")
    prefix.literal._same(_bindings(context), context.bindings)
    if context.source_ready:
        if (
            context.tape.context is not context
            or context.image_namespace["logs"] is not context.tape
            or context.image_namespace["Image"].open.__self__ is not context.tape
        ):
            raise ValueError("Original image observer/namespace/receiver association changed")
        _check_namespace_bindings(context)
    prefix.literal._same(_observer_bindings(context), context.observer_bindings)


def _admit(context, frame):
    old = context.admitted.get(id(frame))
    if old is not None and old["frame"] is frame:
        return  # Shared trace/profile claim, never two claims for one frame.
    name = context.body_codes[frame.f_code]
    row = _attempt(context, name, frame, "literal_body")
    context.admitted[id(frame)] = row  # Retain raw rejected entry before callbacks.
    _guard(context)
    parent = frame.f_back
    caller = None if parent is None else context.admitted.get(id(parent))
    if name == WRAPPER_METHOD:
        valid = (
            parent is context.driver_frame
            and not context.wrapper_claimed
            and frame.f_locals.get("context") is context.parent.prefix
            and frame.f_locals.get("name") == "Cells"
            and frame.f_locals.get("method") == "make_voronoi"
            and frame.f_locals.get("actual") is context.cells
            and frame.f_locals.get("delegate") is context.native_method
        )
        if valid:
            context.wrapper_claimed, context.wrapper_frame = True, frame
    elif name == ROOT_METHOD:
        valid = (
            parent is context.body_parent_frame
            and context.root_claimed
            and frame.f_locals.get("self") is context.cells
            and frame.f_locals.get("phase") is context.phase
            and context.root_body is None
        )
        if valid:
            context.root_body = frame
    elif name in CORE_METHODS:
        expected = context.root_body if name != CORE_METHODS[2] else context.getter_body
        valid = (
            parent is expected
            and caller is not None
            and caller["body_started"]
            and name not in context.core_claimed
        )
        if name == CORE_METHODS[1]:
            valid = (
                valid
                and frame.f_locals.get("self") is context.tape.picker
                and frame.f_locals.get("cells") is context.cells
                and CORE_METHODS[0] in context.return_order
            )
        elif name == CORE_METHODS[2]:
            valid = valid and frame.f_locals.get("filename") is context.tape.picker.filename
            valid = valid and all(
                frame.f_locals.get(arg) is vars(context.cells)[field]
                for arg, field in (
                    ("x_min", "xmin"),
                    ("x_max", "xmax"),
                    ("y_min", "ymin"),
                    ("y_max", "ymax"),
                )
            )
        if valid:
            context.core_claimed.add(name)
            if name == CORE_METHODS[0]:
                context.tape.picker = frame.f_locals["self"]
            elif name == CORE_METHODS[1]:
                context.getter_body = frame
            else:
                context.tape.mask = frame.f_locals["self"]
    else:
        valid = (
            caller is not None
            and caller["frame"] is parent
            and caller["body_started"]
            and not caller.get("returned", False)
        )
        if name in context.forbidden_image_methods:
            valid = False
    if not valid:
        _reject(context, row, "Image body has no original ordered source parent frame")
    row["state"] = "admitted"


def _capture(context, frame, event):
    raw = dict(frame.f_locals)
    context.locals[(frame.f_code.co_qualname, event)] = raw
    context.last_raw_frame = frame
    if frame.f_code in context.image_codes:
        arg = None
        if event == "exception" and context.pending_source_error is not None:
            error = context.pending_source_error
            arg = (type(error), error, error.__traceback__)
        context.tape.trace(frame, event, arg)
    row = context.admitted.get(id(frame))
    if row is not None and row["frame"] is frame:
        if event == "exception":
            row["source_exception"] = context.pending_source_error
        if event == "return" and not row.get("returned", False):
            row["returned"] = True
            row["state"] = "unwound" if row.get("source_exception") is not None else "returned"
            name = context.body_codes[frame.f_code]
            if row["state"] == "returned" and name in (*CORE_METHODS, ROOT_METHOD):
                context.return_order.append(name)
            if name == ROOT_METHOD:
                context.last_root_locals = raw
                context.last_completed = (name, raw)


def _observe(context, name, raw):
    retained = None
    try:
        retained = _epoch(context)
        context.events.append((name, raw))
    except BaseException as error:
        _capture_failure(context, error, name, raw)
    if retained is not None:
        try:
            _same_epoch(context, retained)
        except BaseException as error:
            _capture_failure(context, error, name + "_state", raw)


def _operation(context, name, delegate, *args, **kwargs):
    frame = sys._getframe(1)
    row = _attempt(context, name, frame, "helper_delegate")
    _guard(context)
    if context.operation_active or frame.f_code not in context.operation_wrappers:
        _reject(context, row, "Unowned/reentrant image helper delegate")
    source_frame = frame.f_back
    admission = None if source_frame is None else context.admitted.get(id(source_frame))
    if admission is None or admission["frame"] is not source_frame or not admission["body_started"]:
        _reject(context, row, "Helper delegate was not called by an admitted literal frame")
    _check(context)
    context.operation_active = True
    try:
        _observe(context, name + "_enter", (args, kwargs))
        _guard(context)  # Failed entry capture cannot run the delegate.
        try:
            result = delegate(*args, **kwargs)
        except BaseException as native_error:
            row["source_error"] = native_error
            context.last_native_error = native_error
            raise
        row["delegate_returned"] = True
        context.last_operation_result = (name, result)
        row["state"] = "returned"
        _observe(context, name + "_return", result)
        _guard(context)
        _check(context)
        return result
    except BaseException as primary:
        row["state"] = "failed"
        row["entry_or_observation_error"] = primary
        raise
    finally:
        context.operation_active = False


class _ImageTape(images._Tape):
    def __init__(self, context):
        super().__init__(None)
        self.context, self.file_bytes = context, None

    def open(self, filename):
        context = self.context
        image = _operation(context, "PIL.Image.open", images.Image.open, filename)
        try:
            self.opened.append(image)  # Raw return also retained by _operation.
            if self.picker is None or filename != self.picker.filename:
                raise ValueError("Decoder lost the original picker filename")
            if max(image.size) > images.images.MAX_IMAGE_SIDE:
                raise ValueError("Original image exceeds the existing pixel guard")
            fd = os.dup(image.fp.fileno())
            self.descriptors.append(fd)
            data = os.pread(fd, images.images.MAX_IMAGE_BYTES + 1, 0)
            if len(data) > images.images.MAX_IMAGE_BYTES:
                raise ValueError("Original image exceeds the existing byte guard")
            info = os.fstat(fd)
            self.file_bytes = data
            self.receipts.append(
                dict(
                    filename=filename,
                    byte_count=len(data),
                    device=info.st_dev,
                    inode=info.st_ino,
                    before_sha256=hashlib.sha256(data).hexdigest(),
                    input_mode=image.mode,
                )
            )
        except BaseException as error:
            _capture_failure(context, error, "decoder_descriptor_capture", image)
            _guard(context)
        return image

    def spline(self, *args, **kwargs):
        result = _operation(
            self.context, "RectBivariateSpline", images.RectBivariateSpline, *args, **kwargs
        )
        try:
            self.splines.append(result)
        except BaseException as error:
            _capture_failure(self.context, error, "spline_result_capture", result)
            _guard(self.context)
        return result

    def convex_hull(self, *args, **kwargs):
        result = _operation(self.context, "ConvexHull", images.ConvexHull, *args, **kwargs)
        self.hull = result
        return result

    def log_info(self, *args):
        value = _operation(
            self.context, "logs.log_info", self.context.parent.native_logs.log_info, *args
        )
        try:
            self.events.append(dict(method="log_info", kind="log", arguments=args))
        except BaseException as error:
            _capture_failure(self.context, error, "log_result_capture", value)
            _guard(self.context)
        return value

    def log_debug(self, *args):
        value = _operation(
            self.context, "logs.log_debug", self.context.parent.native_logs.log_debug, *args
        )
        try:
            self.events.append(dict(method="log_debug", kind="log", arguments=args))
        except BaseException as error:
            _capture_failure(self.context, error, "debug_log_result_capture", value)
            _guard(self.context)
        return value

    def finish_inputs(self):
        for fd, receipt in zip(self.descriptors, self.receipts, strict=True):
            data = os.pread(fd, images.images.MAX_IMAGE_BYTES + 1, 0)
            receipt["after_sha256"] = hashlib.sha256(data).hexdigest()
            if data != self.file_bytes:
                raise ValueError("Actual decoder descriptor bytes changed during source work")


def _values(context):
    tape = context.tape
    return dict(
        picker=None if tape.picker is None else images._event_record(vars(tape.picker)),
        mask=None if tape.mask is None else images._event_record(vars(tape.mask)),
        splines=[
            dict(tck=value.tck, fields=images._event_record(vars(value))) for value in tape.splines
        ],
        hull=None if tape.hull is None else images._event_record(vars(tape.hull)),
        input_receipts=tape.receipts,
        literal_locals=images._event_record(tape.locals),
    )


def _epoch(context):
    _check_bootstrap(context)
    view = context.image_view
    if (
        view.splines is not context.tape.splines
        or view.locals is not context.tape.locals
        or view.events is not context.tape.events
        or type(context.empty_attributes) is not dict
        or context.empty_attributes
    ):
        raise ValueError("Original graph observation/absence metadata changed")
    view.mask, view.picker, view.hull = context.tape.mask, context.tape.picker, context.tape.hull
    return (
        prefix._epoch(context.parent),
        images.core.caches.snapshot(_values(context)).identity,
        context.partial_graph(view),
    )


def _same_epoch(context, retained):
    actual = _epoch(context)
    prefix._same_epoch(context.parent, retained[0])
    prefix.literal._same(actual[2][0], retained[2][0])
    if actual[1] != retained[1] or actual[2][1] != retained[2][1]:
        raise ValueError("Observer changed actual image values/reference edges")


def _namespace(context):
    context.literal_binding = _root_literal()  # BEFORE helper factory or cloning.
    context.literal_namespace = context.literal_binding[3]
    namespace = images._namespace(context.tape)
    _check_root_literal(context)  # Factory callbacks cannot replace the root.
    context.image_namespace = namespace
    allowed = {}

    def codes(code):
        allowed[code] = code.co_qualname
        for value in code.co_consts:
            if type(value) is CodeType:
                codes(value)

    for value in namespace.values():
        if type(value) is FunctionType and value.__globals__ is namespace:
            codes(value.__code__)
        elif isinstance(value, type):
            for base in value.__mro__:
                for member in vars(base).values():
                    if type(member) is FunctionType and member.__globals__ is namespace:
                        codes(member.__code__)
    context.image_codes = set(allowed)
    context.body_codes = dict(allowed)
    context.forbidden_image_methods = {
        "TissuePickerImage.pick_cells",
        "TissuePickerImageMask.get_clipped_points_index",
        "cell_index",
        "make_voronoi_mesh_aliases",
    }

    def imports(name, globals=None, locals=None, fromlist=(), level=0):
        _guard(context)
        frame = sys._getframe(1)
        if (
            name != IMPORT
            or tuple(fromlist) != ("TissuePickerImage",)
            or level
            or frame is not context.root_body
            or context.import_claimed
        ):
            _reject(context, None, "Unexpected/reentrant original image import")
        context.import_claimed = True
        _observe(context, "original_image_import", name)
        _guard(context)
        return context.import_view

    context.import_view = SimpleNamespace(TissuePickerImage=namespace["TissuePickerImage"])
    scope = dict(
        source.__dict__, logs=context.tape, __builtins__=dict(vars(builtins), __import__=imports)
    )
    context.method = FunctionType(
        context.literal_binding[2], scope, context.literal_binding[2].co_name
    )
    context.root_scope, context.imports = scope, imports
    context.body_codes[context.method.__code__] = ROOT_METHOD
    context.body_codes[context.native_wrapper.__code__] = WRAPPER_METHOD
    context.operation_wrappers = {
        _ImageTape.open.__code__,
        _ImageTape.spline.__code__,
        _ImageTape.convex_hull.__code__,
        _ImageTape.log_info.__code__,
        _ImageTape.log_debug.__code__,
    }
    context.empty_attributes = {}

    def graph_vars(value):
        # A graph-only absence sentinel; never passed to native source APIs.
        return context.empty_attributes if value is None else vars(value)

    graph_scope = dict(images._graph.__globals__, vars=graph_vars)
    context.partial_graph = FunctionType(images._graph.__code__, graph_scope)
    context.image_view = SimpleNamespace(
        mask=None,
        picker=None,
        hull=None,
        splines=context.tape.splines,
        locals=context.tape.locals,
        events=context.tape.events,
        _trace_metadata=context.tape._trace_metadata,
        _trace_callable_bindings=context.tape._trace_callable_bindings,
    )
    context.namespace_bindings = _namespace_bindings(context)


def _call_atoms(value):
    # Attribute lookup creates fresh bound-method wrappers. Retain the actual
    # receiver/function/code instead of comparing those transient wrappers.
    if type(value) is MethodType:
        return (value.__self__, *prefix._atoms(value.__func__))
    return prefix._atoms(value)


def _module_atoms(module):
    if type(module) is not ModuleType:
        raise ValueError("Original private image helper module required")
    namespace = vars(module)
    return (
        module,
        namespace,
        *(atom for pair in namespace.items() for atom in pair),
        *(
            atom
            for value in namespace.values()
            if type(value) in (FunctionType, MethodType)
            for atom in _call_atoms(value)
        ),
    )


def _namespace_bindings(context):
    namespace = context.image_namespace
    builtins_scope = namespace["__builtins__"]
    private_import = builtins_scope["__import__"]
    packages = tuple(
        cell.cell_contents
        for cell in private_import.__closure__ or ()
        if type(cell.cell_contents) is ModuleType
    )
    return (
        namespace,
        *(atom for pair in namespace.items() for atom in pair),
        *(
            atom
            for function in namespace.values()
            if type(function) in (FunctionType, MethodType)
            for atom in _call_atoms(function)
        ),
        context.literal_namespace,
        context.literal_namespace["VoronoiImagePrefix"],
        *_call_atoms(vars(context.literal_namespace["VoronoiImagePrefix"])["make_voronoi"]),
        context.root_scope,
        *(atom for pair in context.root_scope.items() for atom in pair),
        context.import_view,
        context.import_view.TissuePickerImage,
        context.body_codes,
        *(atom for pair in context.body_codes.items() for atom in pair),
        context.operation_wrappers,
        *sorted(context.operation_wrappers, key=id),
        context.forbidden_image_methods,
        *sorted(context.forbidden_image_methods),
        namespace["np"],
        *(atom for name in NUMPY_HELPERS for atom in prefix._atoms(getattr(namespace["np"], name))),
        namespace["DTYPE_UNSIGNED_TO_SIGNED"],
        *(atom for pair in namespace["DTYPE_UNSIGNED_TO_SIGNED"].items() for atom in pair),
        *(atom for name in HELPER_MODULES for atom in _module_atoms(namespace[name])),
        *(atom for module in packages for atom in _module_atoms(module)),
        builtins_scope,
        *(atom for pair in builtins_scope.items() for atom in pair),
        *_call_atoms(private_import),
        context.root_scope["__builtins__"],
        *(atom for pair in context.root_scope["__builtins__"].items() for atom in pair),
        *(
            atom
            for fn in (context.imports, context.method, context.partial_graph)
            for atom in prefix._atoms(fn)
        ),
        context.partial_graph.__globals__,
        *(atom for pair in context.partial_graph.__globals__.items() for atom in pair),
        *_call_atoms(context.partial_graph.__globals__["vars"]),
        *(
            atom
            for value in namespace.values()
            if isinstance(value, type)
            for atom in prefix.literal._surface(value)
        ),
    )


def _check_namespace_bindings(context):
    _check_root_literal(context)
    prefix.literal._same(_namespace_bindings(context), context.namespace_bindings)


def _wrapper_guard(context, original, wrapper):
    _guard(context)
    if (
        not context.source_ready
        or original is not context.parent.prefix
        or not context.wrapper_claimed
        or context.wrapper_frame is not wrapper
        or wrapper.f_back is not context.driver_frame
        or wrapper.f_locals.get("name") != "Cells"
        or wrapper.f_locals.get("method") != "make_voronoi"
        or wrapper.f_locals.get("actual") is not context.cells
        or wrapper.f_locals.get("delegate") is not context.native_method
    ):
        _reject(context, None, "Only the same original Cells.make_voronoi wrapper may enter")
    _check(context)


def _dispatch(context, original, label, delegate, actual, args, kwargs, dispatch_frame):
    row = _attempt(context, label, dispatch_frame, "original_native_wrapper_dispatch")
    _guard(context)
    caller, native = sys._getframe(1), dispatch_frame.f_back
    wrapper = None if native is None else native.f_back
    if (
        caller is not dispatch_frame
        or caller.f_code is not prefix.previous._dispatch_seed_world.__code__
        or native is None
        or native.f_code is not context.parent.native_call_code
        or native.f_locals.get("context") is not original
        or wrapper is None
        or wrapper.f_code is not context.native_wrapper.__code__
        or wrapper is not context.wrapper_frame
        or not context.wrapper_claimed
        or wrapper.f_back is not context.driver_frame
        or context.root_claimed
        or not context.source_ready
        or label != ROOT_METHOD
        or original is not context.parent.prefix
        or actual is not context.cells
        or delegate is not context.native_method
        or len(args) != 1
        or args[0] is not context.phase
        or kwargs
    ):
        _reject(context, row, "Unclaimed/reentrant/foreign original Voronoi dispatch")
    context.root_claimed = True  # Irreversible BEFORE any observer or source.
    context.body_parent_frame = sys._getframe()
    _check(context)
    _observe(context, "make_voronoi_enter", (actual, context.phase))
    _guard(context)
    result = context.method(actual, *args)
    context.raw_root_result = result
    row["state"] = "returned"
    _observe(context, "make_voronoi_return", result)
    _guard(context)
    return result


@contextmanager
def _account(context):
    scope = dict(prefix.__dict__)
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
    original = prefix._account.__wrapped__
    fn = FunctionType(
        original.__code__, scope, original.__name__, original.__defaults__, original.__closure__
    )
    context.observer_scope, context.observer_function = scope, fn
    context.observer_bindings = _observer_bindings(context)
    with contextmanager(fn)(context):
        yield


def _retire_inputs(context):
    tape = context.tape
    if tape is None:
        return
    # Source/unwind observers may have disabled either inherited hook. No
    # finish_inputs observation may run until both exact identities are proved.
    try:
        _restore_required_hooks(context)
    except BaseException as error:
        context.cleanup_errors += (("input_restore_entry_or_return", error, None),)
        if context.observation_error is None:
            context.observation_error = error
        # Independent caller-boundary fallback if the restoration helper was
        # itself rejected before its body or on its return.
        if context.required_hooks is not None:
            for index in (1, 0):
                try:
                    context.restore_setters[index](context.required_hooks[index])
                except BaseException as secondary:
                    context.cleanup_errors += (("input_emergency_restore", secondary, index),)
    samples = []
    for order in ((0, 1), (1, 0)):
        pair = [None, None]
        for index in order:
            try:
                pair[index] = context.restore_getters[index]()
            except BaseException as error:
                pair[index] = error
                context.cleanup_errors += (("input_hook_sample", error, index),)
        samples.append(tuple(pair))
    context.input_hook_samples = tuple(samples)
    healthy = context.required_hooks is not None and all(
        pair[0] is context.required_hooks[0] and pair[1] is context.required_hooks[1]
        for pair in samples
    )
    if context.cleanup_errors and context.observation_error is None:
        context.observation_error = context.cleanup_errors[0][1]
    if healthy:
        try:
            tape.finish_inputs()
        except BaseException as error:
            context.capture_failures += (("final_input_verification", error, tape),)
            if context.observation_error is None:
                context.observation_error = error
    else:
        context.input_observation_skipped = True
        error = RuntimeError("Required inherited hooks unavailable before finish_inputs")
        context.capture_failures += (("input_hook_identity", error, tape),)
        if context.observation_error is None:
            context.observation_error = error
    # Independent close attempts even if finish/recording entry was rejected.
    for fd in tape.descriptors:
        if fd in context.closed_descriptors:
            continue
        context.closed_descriptors.add(fd)  # Never close a return-rejected fd twice.
        try:
            os.close(fd)
        except BaseException as error:
            context.input_cleanup_errors += ((fd, error),)
            context.capture_failures += (("input_descriptor_close", error, fd),)
            if context.observation_error is None:
                context.observation_error = error


def _restore_required_hooks(context):
    """Raw independent cleanup only; no reporter before final identity proof."""
    expected = context.required_hooks
    for index in (1, 0):
        try:
            context.restore_setters[index](expected[index])
        except BaseException as error:
            context.cleanup_errors += (("finalization_hook_restore", error, index),)
    samples = []
    for order in ((0, 1), (1, 0)):
        actual = [None, None]
        for index in order:
            try:
                actual[index] = context.restore_getters[index]()
            except BaseException as error:
                actual[index] = error
                context.cleanup_errors += (("finalization_hook_sample", error, index),)
        samples.append(tuple(actual))
    context.finalization_hook_samples = tuple(samples)
    return all(pair[0] is expected[0] and pair[1] is expected[1] for pair in samples)


def _partial(context):
    return dict(
        context=context,
        parent=context.parent,
        parent_trial=context.refs[1],
        phase=context.phase,
        parameters=context.p,
        cells=context.cells,
        raw_tape=context.tape,
        raw_locals=context.locals,
        work=context.work,
        before=context.before,
        last_completed=context.last_completed,
        last_operation_result=context.last_operation_result,
        entry_error=context.entry_error,
        capture_failures=context.capture_failures,
        cleanup_errors=context.cleanup_errors,
        input_cleanup_errors=context.input_cleanup_errors,
        usable_child=False,
    )


def _raise_issuance_failure(context, primary, trial):
    """Retain failed publication and independent failed forensic capture."""
    context.invalid = True
    context.issuance_error = primary
    partial = context
    try:
        partial = _partial(context)
    except BaseException as secondary:
        context.capture_reporting_errors += (("issuance_partial", secondary, primary, context),)
    try:
        rejection = VoronoiImageRejected(
            "Image child issuance failed",
            stage="issuance",
            request=context.request,
            trial=trial,
            partial=partial,
            source_error=None,
            capture_error=primary,
        )
    except BaseException as secondary:
        context.capture_reporting_errors += (
            ("issuance_exception_seal", secondary, primary, partial),
        )
        raise primary  # noqa: B904 - retain the original issuance identity and cause
    raise rejection from primary


def trial_record(value):
    return dict(
        law=LAW_ID,
        mode=MODE,
        request=value.request_identity,
        parent=value.parent_identity,
        before=None if value.before is None else value.before.identity,
        cache=None if value.cache is None else value.cache.identity,
        input_receipts=value.input_receipts,
        return_order=value.return_order,
        work=value.work,
        source_completed=value.source_completed,
        failure_stage=value.failure_stage,
        source_error_type=value.source_error_type,
        capture_error_type=value.capture_error_type,
        source_counts_are_not_independent_cases=True,
        next_boundary="before DECMesh",
        phase_mesh_physical_checkpoint_admission=False,
    )


def prepare(request, *, enabled=False):
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise VoronoiImageRejected(
            "Actual image source execution remains held", stage="release", request=request
        )
    api = _ready()
    if type(request) is not Request or request not in _REQUESTS:
        raise VoronoiImageRejected(
            "Actual issued prefix request required", stage="request", request=request
        )
    with _LOCK:
        if _ACTIVE:
            _reject(_ACTIVE[-1], None, "Reentrant image preparation")
        if request in _CONSUMED:
            raise VoronoiImageRejected("Image attempt consumed", stage="consumed", request=request)
        refs = _REQUESTS[request]
        parent = refs[0]
        context = SimpleNamespace(
            request=request,
            refs=refs,
            parent=parent,
            phase=refs[2],
            p=refs[3],
            cells=refs[4],
            api=api,
            thread=get_ident(),
            active=True,
            invalid=False,
            stage="preflight",
            source_ready=False,
            entry_error=None,
            observation_error=None,
            observation_errors=(),
            capture_failures=(),
            capture_reporting_errors=(),
            pending_source_error=None,
            work=[],
            events=[],
            locals={},
            admitted={},
            return_order=[],
            core_claimed=set(),
            root_claimed=False,
            root_body=None,
            getter_body=None,
            body_parent_frame=None,
            operation_active=False,
            import_claimed=False,
            wrapper_claimed=False,
            wrapper_frame=None,
            observer_scope=None,
            observer_function=None,
            before=None,
            tape=None,
            trial=None,
            last_completed=None,
            last_operation_result=None,
            cleanup_errors=(),
            input_cleanup_errors=(),
            closed_descriptors=set(),
            restore_setters=(sys.setprofile, sys.settrace),
            restore_getters=(sys.getprofile, sys.gettrace),
            required_hooks=None,
            driver_frame=sys._getframe(),
            callback=None,
            callback_codes=set(),
            forbidden_callback_codes=set(),
            rand=None,
            draw_active=False,
            validating=False,
            plan=_PLANS[request],
        )
        _CONSUMED[request] = context
        _ACTIVE.append(context)
        primary = capture = trial = None
        try:
            context.required_hooks = (sys.getprofile(), sys.gettrace())
            authentication = _attempt(
                context, "retained_prefix_authentication", sys._getframe(), "authentication"
            )
            actual = prefix._validate(request.prefix_owner)
            if actual is not parent or parent.trial is not refs[1]:
                raise ValueError("Original prefix source trial changed")
            _guard(context)
            context.callback, context.rand = parent.callback, parent.rand
            context.forbidden_callback_codes = set(parent.forbidden_callback_codes) | set(
                parent.callback_codes
            )
            authentication["state"] = "returned"
            checker = api._independent_atoms
            context.bootstrap_validator = (checker, checker.__code__, checker.__globals__)
            context.bootstrap = tuple(
                (fn, checker(fn)) for fn in (prefix._atoms, prefix.literal._same)
            )
            context.before = prefix._snapshot(parent)
            context.native_method = parent.prefix.factories["Cells"].make_voronoi
            context.native_wrapper = vars(type(context.cells))["make_voronoi"]
            callback_source = prefix.previous.previous.caches.previous.callbacks
            callback_source._source_function(
                context.native_method, source.NATIVE_FILE, "make_voronoi", "Cells"
            )
            if type(context.native_wrapper) is not FunctionType:
                raise ValueError("Original owned Cells method wrapper required")
            cells = dict(
                zip(
                    context.native_wrapper.__code__.co_freevars,
                    context.native_wrapper.__closure__ or (),
                    strict=True,
                )
            )
            if (
                cells.get("delegate") is None
                or cells["delegate"].cell_contents is not context.native_method
                or cells.get("context") is None
                or cells["context"].cell_contents is not parent.prefix
            ):
                raise ValueError("Original same-instance native wrapper/delegate changed")
            context.entries = MappingProxyType({ROOT_METHOD: _dispatch})
            context.bindings = _bindings(context)
            context.observer_bindings = _observer_bindings()
            context.stage = "irreversible_prefix_claim"
            if (
                prefix._claim_for_voronoi_image(
                    request.prefix_owner,
                    expected=parent,
                    transition=context,
                    entries=context.entries,
                )
                is not parent
            ):
                raise ValueError("Different prefix retired")
            context.stage = "image_helper_namespace_factory"
            factory = _attempt(context, "image_namespace", sys._getframe(), "source_factory")
            context.tape = _ImageTape(context)
            _namespace(context)
            factory["state"] = "returned"
            context.source_ready = True
            _check(context)
            context.stage = "literal_make_voronoi_image_prefix"
            with _account(context):
                context.cells.make_voronoi(context.phase)
                _guard(context)
                _check(context)
            if tuple(context.return_order) != RETURN_ORDER or not context.import_claimed:
                raise ValueError("Original image construction/return order changed")
            local = context.last_root_locals
            if (
                local.get("image_picker") is not context.tape.picker
                or local.get("image_mask") is not context.tape.mask
            ):
                raise ValueError("Original local picker/mask object was replaced")
        except BaseException as error:
            if context.entry_error is not None:
                primary = context.entry_error
            elif isinstance(error, prefix.literal._CaptureStop):
                primary = context.pending_source_error
            else:
                primary = error
        finally:
            try:
                _retire_inputs(context)
            except BaseException as error:
                context.input_cleanup_errors += ((None, error),)
                context.capture_failures += (("input_cleanup_entry", error, context.tape),)
                if context.observation_error is None:
                    context.observation_error = error
                # The cleanup function may have been rejected before its body.
                for fd in () if context.tape is None else context.tape.descriptors:
                    if fd in context.closed_descriptors:
                        continue
                    context.closed_descriptors.add(fd)
                    try:
                        os.close(fd)
                    except BaseException as secondary:
                        context.input_cleanup_errors += ((fd, secondary),)
        hooks_ok = False
        if context.required_hooks is not None:
            try:
                hooks_ok = _restore_required_hooks(context)
                # A return observer can invalidate the just-returned proof.
                hooks_ok = hooks_ok and (
                    sys.getprofile() is context.required_hooks[0]
                    and sys.gettrace() is context.required_hooks[1]
                )
            except BaseException as error:
                context.cleanup_errors += (("restore_entry_or_return", error, None),)
                # Caller-boundary recovery: helper entry/return rejection must
                # not leave either required hook disabled before later capture.
                for index in (1, 0):
                    try:
                        context.restore_setters[index](context.required_hooks[index])
                    except BaseException as secondary:
                        context.cleanup_errors += (("emergency_restore", secondary, index),)
                samples = []
                for order in ((0, 1), (1, 0)):
                    pair = [None, None]
                    for index in order:
                        try:
                            pair[index] = context.restore_getters[index]()
                        except BaseException as secondary:
                            pair[index] = secondary
                            context.cleanup_errors += (("emergency_sample", secondary, index),)
                    samples.append(tuple(pair))
                context.finalization_hook_samples = tuple(samples)
                hooks_ok = all(
                    pair[0] is context.required_hooks[0] and pair[1] is context.required_hooks[1]
                    for pair in samples
                )
        if context.cleanup_errors and context.observation_error is None:
            context.observation_error = context.cleanup_errors[0][1]
        if not hooks_ok:
            context.invalid, context.active = True, False
            if _ACTIVE and _ACTIVE[-1] is context:
                _ACTIVE.pop()
            # Stop before any further cache/projector/reporter callback. Raw
            # request/parent/partial state remains in the consumed registry.
            if primary is not None:
                raise primary
            if context.observation_error is not None:
                raise context.observation_error
            raise RuntimeError("Required inherited hooks unavailable before image finalization")
        capture = context.observation_error
        cache = None
        try:
            if context.tape is not None:
                cache = images.core.caches.snapshot(_values(context))
            value = Trial(
                request.identity,
                request.parent_identity,
                context.before,
                cache,
                ()
                if context.tape is None
                else tuple(tuple(row.items()) for row in context.tape.receipts),
                tuple(context.return_order),
                tuple(
                    (row["sequence"], row["name"], row["layer"], row["state"])
                    for row in context.work
                ),
                tuple(context.return_order) == RETURN_ORDER,
                context.stage if primary is not None or capture is not None else None,
                None if primary is None else type(primary).__qualname__,
                None if capture is None else type(capture).__qualname__,
                "",
            )
            trial = context.trial = replace(value, identity=_digest(trial_record(value)))
            if primary is None and capture is None:
                _check(context)
                context.graph = images._graph(context.tape)
        except BaseException as error:
            context.final_capture_error = error
            if capture is None:
                capture = error
        finally:
            context.active = False
            if _ACTIVE and _ACTIVE[-1] is context:
                _ACTIVE.pop()
            else:
                context.invalid = True
        # Cache/Trial/graph observation can reject on entry or return and
        # disable an inherited hook. These caller-local cleanup actions run
        # before any subsequent partial/exception/publication callback.
        for index in (1, 0):
            try:
                context.restore_setters[index](context.required_hooks[index])
            except BaseException as error:
                context.cleanup_errors += (("post_capture_restore", error, index),)
                if capture is None:
                    capture = error
        samples = []
        for order in ((0, 1), (1, 0)):
            pair = [None, None]
            for index in order:
                try:
                    pair[index] = context.restore_getters[index]()
                except BaseException as error:
                    pair[index] = error
                    context.cleanup_errors += (("post_capture_sample", error, index),)
                    if capture is None:
                        capture = error
            samples.append(tuple(pair))
        context.post_capture_hook_samples = tuple(samples)
        if not all(
            pair[0] is context.required_hooks[0] and pair[1] is context.required_hooks[1]
            for pair in samples
        ):
            context.invalid = True
            if primary is not None:
                raise primary
            if capture is not None:
                raise capture
            raise RuntimeError("Inherited hooks unavailable after image final capture")
        if primary is not None or capture is not None or trial is None or context.invalid:
            context.invalid = True
            partial = context
            try:
                partial = _partial(context)
            except BaseException as secondary:
                context.capture_reporting_errors += (
                    ("failed_partial", secondary, primary, context),
                )
                if capture is None:
                    capture = secondary
            try:
                rejected = VoronoiImageRejected(
                    "Same-phase image prefix failed",
                    stage=context.stage,
                    request=request,
                    trial=trial,
                    partial=partial,
                    source_error=primary,
                    capture_error=capture,
                )
            except BaseException as secondary:
                context.capture_reporting_errors += (
                    ("failed_exception_seal", secondary, primary, partial),
                )
                if primary is not None:
                    raise primary  # noqa: B904 - preserve original source identity and cause
                if capture is not None:
                    raise capture  # noqa: B904 - preserve the original capture identity/cause
                raise
            raise rejected from primary
        try:
            owner = object.__new__(VoronoiImageOwner)
            context.owner = owner
            _ISSUED[owner] = context
            return owner
        except BaseException as error:
            context.invalid = True
            context.issuance_error = error
            try:
                _raise_issuance_failure(context, error, trial)
            except BaseException as rejection:
                if rejection is error or (
                    type(rejection) is VoronoiImageRejected
                    and rejection.capture_error is error
                    and rejection.__cause__ is error
                ):
                    raise
                context.capture_reporting_errors += (
                    ("issuance_handler_entry", rejection, error, context),
                )
                raise error  # noqa: B904 - a secondary handler-entry error cannot replace primary


class VoronoiImageOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use the genuine same-phase image source continuation")

    def __reduce_ex__(self, protocol):
        raise TypeError("No image/phase hydration or ordinary checkpoint")

    @property
    def trial(self):
        return _authority(self).trial

    @property
    def phase(self):
        return _authority(self).phase


def _authority(owner):
    if type(owner) is not VoronoiImageOwner or owner not in _ISSUED:
        raise VoronoiImageRejected("Actual issued same-phase image owner required", stage="owner")
    context = _ISSUED[owner]
    if context.validating:
        _reject(context, None, "Recursive/competing image-owner validation")
    context.validating = True
    try:
        if context.active or context.owner is not owner or context.invalid:
            raise ValueError("Unavailable image owner")
        _check(context)
        if (
            not context.trial.source_completed
            or tuple(context.return_order) != RETURN_ORDER
            or _digest(trial_record(context.trial)) != context.trial.identity
            or images.core.caches.snapshot(_values(context)).identity
            != context.trial.cache.identity
        ):
            raise ValueError("Original image trial/value cache changed")
        graph = images._graph(context.tape)
        prefix.literal._same(graph[0], context.graph[0])
        if graph[1] != context.graph[1]:
            raise ValueError("Original image references, bases or closure edges changed")
        if context.invalid or context.entry_error is not None:
            raise (
                context.entry_error
                if context.entry_error is not None
                else ValueError("Poisoned image owner")
            )
    except BaseException as error:
        context.invalid = True
        context.last_owner_error = error
        partial = context
        try:
            partial = _partial(context)
        except BaseException as secondary:
            context.capture_reporting_errors += (("owner_partial", secondary, error, context),)
        try:
            rejected = VoronoiImageRejected(
                "Stale same-phase image owner",
                stage="owner_drift",
                request=context.request,
                trial=context.trial,
                partial=partial,
                source_error=error,
            )
        except BaseException as secondary:
            context.capture_reporting_errors += (("owner_rejection", secondary, error, partial),)
            raise error  # noqa: B904 - retain the actual owner error and its original cause
        raise rejected from error
    finally:
        context.validating = False
    return context


def require_mesh(owner):
    context = _authority(owner)
    raise VoronoiImageRejected(
        "Actual same-instance DECMesh continuation is not admitted",
        stage="mesh_held",
        request=context.request,
        trial=context.trial,
    )
