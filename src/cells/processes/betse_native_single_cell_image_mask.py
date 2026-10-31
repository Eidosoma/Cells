"""Fresh literal image-picker/mask ownership on the issued source caller.

The original pathname is passed to Pillow unchanged. A duplicate of Pillow's
actual file descriptor authenticates its bytes without replacing the input.
Frozen Prelude values are comparison evidence, never a source for hydration.
Actual construction/decoding/spline/hull work remains unrun and held.
"""

import ast
import builtins
import hashlib
import json
import os
import sys
import warnings
from dataclasses import dataclass, replace
from pathlib import Path
from types import ModuleType
from weakref import WeakKeyDictionary

import numpy as np
from PIL import Image
from scipy.interpolate import RectBivariateSpline
from scipy.spatial import ConvexHull

from cells.processes import betse_native_single_cell_caller_lattice as callers
from cells.processes import betse_native_single_cell_image_mask_source as source

core = callers.core
images = core.initial.image_stage
LAW_ID = "betse_owned_single_cell_live_image_mask@1"
INVALIDATED_OWNERS = core.INVALIDATED_OWNERS
HELD_UNQUALIFIED_SOURCE_STAGE = True
CALLER_PINS = {
    "betse_native_single_cell_caller_lattice": "e5b3b09adf69b8daf42e89d511f6a17995d17eab3ec94a76cefb1df521cf5f6c",
    "betse_native_single_cell_caller_lattice_source": "026586341ef51a4d1f7cd6095e087cb07db8129a555afd505fa40aa7acdb1e30",
}
_ISSUED = WeakKeyDictionary()


@dataclass(frozen=True, slots=True)
class Request:
    caller: callers.CallerOwner
    identity: str


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    audit: object
    events: tuple
    input_receipts: tuple
    warnings: tuple
    source_completed: bool
    failure_stage: str | None
    failure_type: str | None
    failure_message: str | None
    identity: str


class ImageOwnerRejected(ValueError):
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


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _verify_sources():
    pins = callers._verify_sources()
    for module in (callers, callers.source):
        name = module.__name__.rsplit(".", 1)[-1]
        if _sha(module.__file__) != CALLER_PINS[name]:
            raise ValueError("Changed reviewed caller prerequisite: " + name)
    tree = ast.parse(Path(source.__file__).read_text())
    definitions = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    for name, site in source.SITES.items():
        if name == "DTYPE_UNSIGNED_TO_SIGNED":
            node = next(
                n
                for n in tree.body
                if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)
            )
        elif name == "make_voronoi_mesh_aliases":
            node = ast.Module(body=definitions["CallerTail"].body[0].body, type_ignores=[])
        elif name == "cell_index":
            node = definitions["CallerTail"].body[1]
        else:
            node = definitions[name]
        if hashlib.sha256(ast.dump(node).encode()).hexdigest() != site["ast_sha256"]:
            raise ValueError("Changed literal image/caller source: " + name)
    for name, expected in source.NATIVE_PINS.items():
        path = callers.NATIVE_ROOT / name
        if path.is_symlink() or _sha(path) != expected:
            raise ValueError("Original image source unavailable/changed: " + name)
    pins.update({str(Path(m.__file__).resolve()): _sha(m.__file__) for m in (source, callers)})
    pins[str(Path(__file__).resolve())] = _sha(__file__)
    return pins


def _context(owner):
    context = callers._validate_owner(owner)
    prelude = context["request"].core_request.initial_request.upstream[2]
    if type(prelude) is not images.Prelude or type(prelude.image) is not images.ImageSource:
        raise ImageOwnerRejected(
            "Owned image Prelude evidence unavailable", stage="upstream_image_evidence"
        )
    image = prelude.image
    if (
        core.records._digest(images.prelude_record(prelude)) != prelude.identity
        or core.records._digest(images.image_record(image)) != image.identity
        or hashlib.sha256(image.file_bytes).hexdigest() != image.file_sha256
        or len(image.file_bytes) > images.MAX_IMAGE_BYTES
        or any(value.flags.writeable for value in prelude.values)
        or max(image.bitmap.shape) > images.MAX_IMAGE_SIDE
    ):
        raise ImageOwnerRejected("Changed frozen image evidence", stage="upstream_image_identity")
    return context, prelude


def request_record(request):
    context, prelude = _context(request.caller)
    return dict(
        law=LAW_ID,
        caller_trial=context["trial"].identity,
        prelude_identity=prelude.identity,
        image_record=images.image_record(prelude.image),
        native_source_pins=source.NATIVE_PINS,
        full_phase_or_parameter_authority=False,
    )


def from_caller(owner, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise ImageOwnerRejected("Explicit image source-law opt-in required", stage="opt_in")
    value = Request(owner, "")
    return replace(value, identity=core.records._digest(request_record(value)))


def _file_bytes(image):
    path = Path(image.native_filename)
    if not path.is_file() or str(path.resolve()) != image.resolved_filename:
        raise ValueError("Original declared image path/owner changed")
    with path.open("rb") as stream:
        actual = stream.read(images.MAX_IMAGE_BYTES + 1)
    if actual != image.file_bytes:
        raise ValueError("Actual image file differs from its owned immutable bytes")
    return actual


class _Tape:
    def __init__(self, image):
        self.image = image
        self.events, self.locals, self.splines, self.opened = [], {}, [], []
        self.picker = self.mask = self.hull = None
        self.descriptors, self.receipts, self.recovery_errors = [], [], []

    def trace(self, frame, event, arg):
        methods = set(source.SITES) - {"type_check"}
        methods.update(
            (
                "__init__",
                "get_image_mask",
                "pick_cells",
                "pick_cells_and_mems",
                "get_clipped_points_index",
            )
        )
        if (
            frame.f_code.co_filename == str(Path(source.__file__).resolve())
            and frame.f_code.co_name in methods
            and event in ("call", "return", "exception")
        ):
            name = frame.f_code.co_qualname
            self.locals[name] = dict(frame.f_locals)
            obj = frame.f_locals.get("self")
            if name == "TissuePickerImage.__init__":
                self.picker = obj
            elif name == "TissuePickerImageMask.__init__":
                self.mask = obj
            self.events.append(
                dict(
                    method=name,
                    kind=event,
                    attributes=None if obj is None else dict(vars(obj)),
                    error=None if event != "exception" else arg[1],
                )
            )
        return self.trace

    def log_info(self, *args):
        self.events.append(dict(method="log_info", kind="log", arguments=args))

    log_debug = log_info

    def open(self, filename):
        # Preserve Pillow's actual filename call and raw parser failures.
        image = Image.open(filename)
        self.opened.append(image)
        if max(image.size) > images.MAX_IMAGE_SIDE:
            raise ValueError("Original image exceeds the declared pixel guard")
        fd = os.dup(image.fp.fileno())
        self.descriptors.append(fd)
        data = os.pread(fd, images.MAX_IMAGE_BYTES + 1, 0)
        if data != self.image.file_bytes:
            raise ValueError("Pillow opened different file bytes")
        info = os.fstat(fd)
        self.receipts.append(
            dict(
                filename=filename,
                before_sha256=hashlib.sha256(data).hexdigest(),
                device=info.st_dev,
                inode=info.st_ino,
                byte_count=len(data),
                input_mode=image.mode,
            )
        )
        return image

    def spline(self, *args, **kwargs):
        result = RectBivariateSpline(*args, **kwargs)
        self.splines.append(result)
        return result

    def convex_hull(self, *args, **kwargs):
        self.hull = ConvexHull(*args, **kwargs)
        return self.hull

    def finish_inputs(self):
        try:
            for fd, receipt in zip(self.descriptors, self.receipts, strict=True):
                data = os.pread(fd, images.MAX_IMAGE_BYTES + 1, 0)
                receipt["after_sha256"] = hashlib.sha256(data).hexdigest()
                if data != self.image.file_bytes:
                    raise ValueError("Actual decoder input changed during source construction")
        finally:
            for fd in self.descriptors:
                try:
                    os.close(fd)
                except Exception as error:
                    self.recovery_errors.append(error)


def _serialize_refused(self, protocol):
    raise TypeError("A live image source object cannot be serialized as authority")


def _namespace(tape):
    namespace = dict(__name__=source.__name__, __builtins__=dict(vars(builtins)))
    package = ModuleType("betse.util.path")

    def imports(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "betse.util.path":
            return package
        if name.split(".")[0] == "betse":
            raise ImportError("Unowned package import at image boundary: " + name)
        return builtins.__import__(name, globals, locals, fromlist, level)

    namespace["__builtins__"]["__import__"] = imports
    filename = str(Path(source.__file__).resolve())
    exec(compile(Path(filename).read_text(), filename, "exec"), namespace)
    for module_name, names in {
        "pathnames": ("is_absolute", "is_relative", "die_if_absolute", "join", "get_basename"),
        "files": ("is_file", "die_unless_file"),
        "dirs": ("is_dir",),
        "paths": ("is_path",),
        "nparray": ("to_signed",),
        "pilnumpy": ("load_image",),
    }.items():
        module = ModuleType("owned.image." + module_name)
        for name in names:
            setattr(module, name, namespace[name])
        namespace[module_name] = module
        setattr(package, module_name, module)
    image_module = ModuleType("owned.image.PIL_reader")
    image_module.open = tape.open
    namespace.update(
        Image=image_module, RectBivariateSpline=tape.spline, ConvexHull=tape.convex_hull, logs=tape
    )
    for name in ("TissuePickerImage", "TissuePickerImageMask"):
        namespace[name] = type(
            "Owned" + name, (namespace[name],), {"__reduce_ex__": _serialize_refused}
        )
    return namespace


def _construct(tape, prelude, cells):
    namespace = _namespace(tape)
    raw = json.loads(prelude.image.definition_json)
    picker = namespace["TissuePickerImage"](filename=raw["filename"], dirname=raw["conf_dirname"])
    tape.picker = picker
    tape.mask = picker.get_image_mask(cells=cells)
    return tape.picker, tape.mask


def _linear(mask):
    matches = [
        cell.cell_contents
        for cell in mask.clipping_function.__closure__ or ()
        if hasattr(cell.cell_contents, "get_knots") and hasattr(cell.cell_contents, "get_coeffs")
    ]
    if len(matches) != 1:
        raise ValueError("Original callable linear spline relationship unavailable")
    return matches[0]


def _audit(tape, prelude):
    mask = tape.mask
    local = tape.locals["TissuePickerImageMask.__init__"]
    linear = _linear(mask)
    if (
        len(tape.splines) != 2
        or linear is not tape.splines[0]
        or mask.clipping_function_fast is not tape.splines[1]
    ):
        raise ValueError("Original linear/fast interpolation objects differ")
    values = images.MaskValues(
        local["bitmap"],
        mask.clipping_matrix,
        local["xpts"],
        local["ypts"],
        np.column_stack(local["indsN"]),
        local["ppts"],
        local["bverts"],
        mask.clipcurve,
        *linear.get_knots(),
        linear.get_coeffs(),
        *mask.clipping_function_fast.get_knots(),
        mask.clipping_function_fast.get_coeffs(),
    )
    for name, actual, expected in zip(values._fields, values, prelude.values, strict=True):
        callers._equal(actual, expected, "image/" + name)
    if mask.msize != prelude.image.bitmap.shape[0] or local["bclip"] is not tape.hull:
        raise ValueError("Original mask size/hull object differs")
    if len(tape.receipts) != 1 or tape.receipts[0].get("after_sha256") != prelude.image.file_sha256:
        raise ValueError("Complete actual decoder descriptor provenance required")
    receipt = tape.receipts[0]
    if (
        tape.picker.filename != prelude.image.native_filename
        or receipt["filename"] != prelude.image.native_filename
        or receipt["before_sha256"] != prelude.image.file_sha256
        or receipt["input_mode"] != prelude.image.input_mode
    ):
        raise ValueError("Original picker/decoder filename or input mode changed")
    return core.caches.snapshot(
        dict(values=values._asdict(), msize=mask.msize, receipts=tape.receipts)
    )


def _event_record(event):
    # Inspection tokens do not reconstruct callables, splines or exceptions.
    def plain(value):
        if value is None or isinstance(value, (str, int, float, bool, np.ndarray, np.generic)):
            return value
        if isinstance(value, dict):
            return {key: plain(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return [plain(item) for item in value]
        return dict(live_source_token=type(value).__module__ + "." + type(value).__qualname__)

    return plain(event)


def trial_record(trial):
    return dict(
        request=trial.request_identity,
        audit=None if trial.audit is None else trial.audit.identity,
        events=[e.identity for e in trial.events],
        input_receipts=trial.input_receipts,
        warnings=trial.warnings,
        source_completed=trial.source_completed,
        failure_stage=trial.failure_stage,
        failure_type=trial.failure_type,
        failure_message=trial.failure_message,
        full_caller_continuation_admitted=False,
        physical_geometry_admitted=False,
        checkpoint_admitted=False,
        invalidated_owners=INVALIDATED_OWNERS,
    )


def _graph(tape):
    objects, seen = [], set()

    def visit(value):
        if (
            value is None
            or isinstance(value, (str, int, float, bool, np.generic))
            or id(value) in seen
        ):
            return
        if len(objects) > core.caches.MAX_TREE_NODES:
            raise ValueError("Image source graph exceeds its declared bound")
        seen.add(id(value))
        objects.append(value)
        if isinstance(value, np.ndarray):
            visit(value.base)
        elif isinstance(value, dict):
            for key, item in value.items():
                visit(key)
                visit(item)
        elif isinstance(value, (tuple, list)):
            for item in value:
                visit(item)
        elif callable(value) and hasattr(value, "__code__"):
            visit(value.__code__)
            visit(value.__closure__)
            for cell in value.__closure__ or ():
                visit(cell.cell_contents)
        elif hasattr(value, "tck"):
            visit(value.tck)

    for value in (
        tape,
        tape.mask,
        tape.picker,
        vars(tape.mask),
        vars(tape.picker),
        tape.splines,
        tape.hull,
        tape.locals,
        tape.events,
    ):
        visit(value)
    return tuple(objects)


class ImageOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use prepare with issued caller authority")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live mask authority cannot be serialized")

    @property
    def mask(self):
        return _validate_owner(self)["tape"].mask

    @property
    def trial(self):
        return _authority(self)["trial"]


def _authority(owner):
    if type(owner) is not ImageOwner or owner not in _ISSUED:
        raise ImageOwnerRejected(
            "Issued live image authority unavailable", stage="image_authority_unavailable"
        )
    return _ISSUED[owner]


def _validate_owner(owner):
    value = _authority(owner)
    try:
        context, prelude = _context(value["request"].caller)
        if value["invalid"] or _verify_sources() != value["producers"]:
            raise ValueError("Changed source producer")
        if core.records._digest(request_record(value["request"])) != value["request"].identity:
            raise ValueError("Changed source request")
        if context["caller"] is not value["caller"] or context["tape"].rng is not value["rng"]:
            raise ValueError("Original caller/RNG identity lost")
        if core.initial._rng_stream(value["rng"]).identity != value["rng_epoch"]:
            raise ValueError("Image construction/query changed the original RNG epoch")
        _file_bytes(prelude.image)
        if _audit(value["tape"], prelude).identity != value["trial"].audit.identity:
            raise ValueError("Changed actual mask/spline evidence")
        graph = _graph(value["tape"])
        if len(graph) != len(value["graph"]) or any(
            a is not b for a, b in zip(graph, value["graph"], strict=True)
        ):
            raise ValueError("Original image object/alias relationships changed")
        if tuple(
            core.caches.snapshot(_event_record(e)).identity for e in value["tape"].events
        ) != tuple(e.identity for e in value["trial"].events):
            raise ValueError("Original source event sequence changed")
    except Exception as error:
        value["invalid"] = True
        raise ImageOwnerRejected(
            "Stale image source authority refused without reconstruction",
            stage="image_authority_drift",
            request=value["request"],
            trial=value["trial"],
            source_error=error,
        ) from error
    return value


def prepare(request):
    if type(request) is not Request:
        raise ImageOwnerRejected(
            "Typed live image request required", stage="request_owner", request=request
        )
    producers = _verify_sources()
    context, prelude = _context(request.caller)
    if core.records._digest(request_record(request)) != request.identity:
        raise ImageOwnerRejected("Changed image request", stage="request_identity", request=request)
    _file_bytes(prelude.image)
    tape = _Tape(prelude.image)
    rng = context["tape"].rng
    epoch = core.initial._rng_stream(rng).identity
    error = capture_error = None
    audit, stage = None, "native_image_picker_and_mask"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        previous = sys.gettrace()
        try:
            sys.settrace(tape.trace)
            _construct(tape, prelude, context["caller"])
        except Exception as failure:
            error = failure
        finally:
            sys.settrace(previous)
            try:
                tape.finish_inputs()
            except Exception as failure:
                capture_error = failure
    partial = dict(
        tape=tape,
        caller=context["caller"],
        rng=rng,
        usable_live_owner_available=False,
        original_source_stage=stage,
        recovery_errors=tape.recovery_errors,
    )
    try:
        if capture_error is not None:
            raise capture_error
        if error is None:
            stage = "exact_live_image_evidence"
            _file_bytes(prelude.image)
            if core.initial._rng_stream(rng).identity != epoch:
                raise ValueError("Image source consumed an unexpected RNG epoch")
            audit = _audit(tape, prelude)
        trial = Trial(
            request.identity,
            audit,
            tuple(core.caches.snapshot(_event_record(e)) for e in tape.events),
            tuple(dict(r) for r in tape.receipts),
            tuple(str(w.message) for w in caught),
            error is None,
            None if error is None else stage,
            None if error is None else type(error).__name__,
            None if error is None else str(error),
            "",
        )
        trial = replace(trial, identity=core.records._digest(trial_record(trial)))
    except Exception as failure:
        raise ImageOwnerRejected(
            "Live image trial sealing refused",
            stage="capture",
            request=request,
            partial=partial,
            source_error=error,
            capture_error=failure,
        ) from (error if error is not None else failure)
    if error is not None:
        raise ImageOwnerRejected(
            "Original image source failed",
            stage=stage,
            request=request,
            trial=trial,
            partial=partial,
            source_error=error,
        ) from error
    try:
        if _verify_sources() != producers:
            raise ValueError("Source producer changed during construction")
        graph = _graph(tape)
        owner = object.__new__(ImageOwner)
        _ISSUED[owner] = dict(
            request=request,
            trial=trial,
            tape=tape,
            caller=context["caller"],
            rng=rng,
            rng_epoch=epoch,
            graph=graph,
            producers=producers,
            invalid=False,
        )
        return owner
    except Exception as failure:
        raise ImageOwnerRejected(
            "Live mask issuance refused",
            stage="issuance",
            request=request,
            trial=trial,
            partial=partial,
            capture_error=failure,
        ) from failure


def require_caller_continuation(owner, *, mesh_owner=None, parameter_owner=None):
    value = _validate_owner(owner)
    raise ImageOwnerRejected(
        "In-caller mesh construction/order/shared RNG and owned cell_height are unavailable",
        stage="caller_mesh_parameter_authority_unavailable",
        request=value["request"],
        trial=value["trial"],
        partial=dict(
            mesh_owner=mesh_owner,
            parameter_owner=parameter_owner,
            equal_epochs_are_not_shared_RNG_identity=True,
            complete_mesh_is_not_in_caller_init_order=True,
            full_caller_continuation_admitted=False,
            invalidated_owners=INVALIDATED_OWNERS,
        ),
    )
