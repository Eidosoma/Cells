"""Import-time provenance for the opaque NumPy 2.5.3 ``copy`` dispatcher.

No numerical function is called to discover an edge.  The witness is the
original decorator's observed construction, not ``__wrapped__`` or a supplied
record.  The only supported installation is the explicitly pinned BETSE wheel.
This module imports only the standard library.
"""

import base64
import builtins
import csv
import dis
import functools
import hashlib
import io
import struct
import sys
import threading
from pathlib import Path
from types import (
    CodeType,
    FrameType,
    FunctionType,
    GetSetDescriptorType,
    MemberDescriptorType,
    ModuleType,
)

KIND = "cells.original_numpy_copy_import_origin@1"
SITE = Path("/mnt/workspaces/Cells/venv-betse/lib/python3.13/site-packages")
RECORD = "numpy-2.5.3.dist-info/RECORD"
ROOT = "numpy/__init__.py"
SOURCE = "numpy/lib/_function_base_impl.py"
OVERRIDES = "numpy/_core/overrides.py"
INSPECT = "numpy/_utils/_inspect.py"
BINARY = "numpy/_core/_multiarray_umath.cpython-313-x86_64-linux-gnu.so"
FUNCTOOLS = Path("/usr/lib/python3.13/functools.py")
FUNCTOOLS_SHA256 = "7aa8725afbe9b9fc47a825b4e7c0330fa374432f481d7be8202b96f56eeac9a0"
PINS = {
    RECORD: "7303d8896015c2544271821eaa20431044b67a4402fa76475dfb5d5553aae629",
    "numpy-2.5.3.dist-info/METADATA": (
        "451a9b8028000588e66b0b415587b6aef0bbc51a96d8e8a0cba0dc23acf64f99"
    ),
    ROOT: "09295a80660f17925ae23765ce8cbd7ff7ceae968d5f2f89349f1cb74c0b9e11",
    SOURCE: "000d045b739c89974bfd9bae66beaa35bfd97ea7a06d13378aa234153a3b6116",
    OVERRIDES: "88cf63f86be1eba2a303d221f011af2077194d819c06a10c725f01c939afe4ca",
    INSPECT: "cc5b890011f4f03d4a82afde79c6240f53a0834397a75b78a2a8d9c4cd2474b9",
    BINARY: "097e10f2baaf99d5a4655e549a6c76b139e3931681af39068f79c7b3abddadac",
}
MAX_EVENTS = 2048
MAX_FRAMES = 4096
MAX_ERRORS = 32
MAX_IMPORT_OPCODES = 262144
_SYSTEM = (sys.setprofile, sys.settrace, sys.getprofile, sys.gettrace)
_FRAME = sys._getframe
_SESSION = None
_ISSUED, _COMPLETED = {}, {}
_ABSENT = object()


class OriginRejected(ValueError):
    """A fixed-message refusal, with original errors retained separately."""


def _require(value, reason):
    if not value:
        raise OriginRejected(reason)


def _digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _files():
    """Re-read pinned bytes; neither timestamps nor a wheel label are authority."""
    result = {}
    for relative, expected in PINS.items():
        path = SITE / relative
        _require(path.resolve() == path and path.is_file(), "Original regular wheel file required")
        before = path.stat()
        actual = _digest(path)
        after = path.stat()
        _require(
            (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            == (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            and actual == expected,
            "Pinned NumPy source or dispatcher binary changed",
        )
        result[str(path)] = actual
    raw_record = (SITE / RECORD).read_bytes()
    _require(
        hashlib.sha256(raw_record).hexdigest() == PINS[RECORD], "Wheel RECORD changed while reading"
    )
    rows = list(csv.reader(io.StringIO(raw_record.decode())))
    _require(all(len(row) == 3 for row in rows), "Exact wheel RECORD rows required")
    entries = {row[0]: row[1:] for row in rows}
    _require(len(entries) == len(rows), "Duplicate wheel RECORD path")
    for relative in PINS:
        if relative == RECORD:
            continue
        encoded, size = entries[relative]
        actual = base64.urlsafe_b64encode(bytes.fromhex(PINS[relative])).rstrip(b"=").decode()
        _require(
            encoded == "sha256=" + actual and size == str((SITE / relative).stat().st_size),
            "Wheel RECORD does not bind the observed producer",
        )
    _require(
        Path(functools.__file__).resolve() == FUNCTOOLS and _digest(FUNCTOOLS) == FUNCTOOLS_SHA256,
        "Original stdlib wrapper source required",
    )
    result[str(FUNCTOOLS)] = FUNCTOOLS_SHA256
    return result


def _constant(value):
    if type(value) in (type(None), bool, int, str, bytes):
        return type(value).__name__, value
    if type(value) is float:
        return "float", struct.pack("<d", value)
    if type(value) is complex:
        return "complex", struct.pack("<dd", value.real, value.imag)
    if value is Ellipsis:
        return ("ellipsis",)
    if type(value) is tuple:
        return "tuple", tuple(_constant(v) for v in value)
    if type(value) is frozenset:
        return "frozenset", frozenset(_constant(v) for v in value)
    if type(value) is CodeType:
        return "code", _code(value)
    raise OriginRejected("Unsupported original code constant")


def _code(value):
    _require(type(value) is CodeType, "Original Python code required")
    return (
        value.co_argcount,
        value.co_posonlyargcount,
        value.co_kwonlyargcount,
        value.co_nlocals,
        value.co_stacksize,
        value.co_flags,
        value.co_code,
        tuple(_constant(v) for v in value.co_consts),
        value.co_names,
        value.co_varnames,
        value.co_freevars,
        value.co_cellvars,
        value.co_name,
        value.co_qualname,
        value.co_filename,
        value.co_firstlineno,
        value.co_linetable,
        value.co_exceptiontable,
    )


def _compiled(relative):
    # Compile-only whole-module context preserves Python 3.13 call bytecode.
    path = FUNCTOOLS if relative == "functools" else SITE / relative
    raw = path.read_bytes()
    expected = FUNCTOOLS_SHA256 if relative == "functools" else PINS[relative]
    _require(hashlib.sha256(raw).hexdigest() == expected, "Compile exactly the pinned source bytes")
    root = compile(raw, str(path), "exec", dont_inherit=True)
    found = {}

    def walk(code):
        found[code.co_qualname] = code
        for item in code.co_consts:
            if type(item) is CodeType:
                walk(item)

    walk(root)
    return found


def _module(name, relative):
    module = sys.modules.get(name)
    _require(type(module) is ModuleType, "Original loaded NumPy module required")
    path = vars(module).get("__file__")
    _require(type(path) is str and Path(path).resolve() == SITE / relative, "Foreign module origin")
    spec = vars(module).get("__spec__")
    _require(spec is not None and spec.origin == str(SITE / relative), "Foreign module spec")
    return module


def _function(function, module, code, defaults):
    _require(
        type(function) is FunctionType
        and function.__globals__ is vars(module)
        and function.__builtins__ is vars(builtins)
        and function.__kwdefaults__ is None
        and function.__closure__ is None
        and _constant(function.__defaults__) == _constant(defaults)
        and _code(function.__code__) == _code(code),
        "Original Python function/code/defaults/namespace required",
    )
    return function


def _function_atoms(function):
    _require(type(function) is FunctionType, "Retained Python helper required")
    closure = function.__closure__
    return (
        function,
        function.__code__,
        function.__globals__,
        function.__builtins__,
        id(function.__defaults__),
        function.__defaults__,
        _constant(function.__defaults__),
        function.__kwdefaults__,
        None if function.__kwdefaults__ is None else tuple(function.__kwdefaults__.items()),
        id(closure),
        None if closure is None else tuple((cell, cell.cell_contents) for cell in closure),
        tuple(
            (
                name,
                name in function.__globals__,
                function.__globals__.get(name, _ABSENT),
                function.__builtins__.get(name, _ABSENT),
            )
            for name in function.__code__.co_names
        ),
    )


def _same(left, right):
    """Compare container structure and actual references without user equality."""
    if type(left) is tuple and type(right) is tuple:
        return len(left) == len(right) and all(
            _same(a, b) for a, b in zip(left, right, strict=True)
        )
    if type(left) in (str, int, bool, bytes, type(None)) and type(left) is type(right):
        return left == right
    return left is right


def _class(dispatcher):
    _require(type(dispatcher) is type, "Original C dispatcher type required")
    flags = type.__getattribute__(dispatcher, "__flags__")
    _require(
        flags & (1 << 8)
        and not flags & (1 << 9)
        and type.__getattribute__(dispatcher, "__module__") == "numpy"
        and type.__getattribute__(dispatcher, "__name__") == "_ArrayFunctionDispatcher",
        "Original immutable non-heap dispatcher required",
    )
    slot = vars(dispatcher).get("_implementation")
    _require(
        type(slot) in (MemberDescriptorType, GetSetDescriptorType)
        and slot.__objclass__ is dispatcher
        and slot.__name__ == "_implementation",
        "Original implementation descriptor required",
    )
    # Version-tag/cache flags are interpreter state, not dispatcher semantics.
    return (
        dispatcher,
        flags & ((1 << 8) | (1 << 9)),
        dispatcher.__mro__,
        tuple(vars(dispatcher).items()),
        slot,
    )


def _public(value, dispatcher, implementation):
    _require(type(value) is dispatcher, "Actual original dispatcher return required")
    slot = _class(dispatcher)[-1]
    _require(
        slot.__get__(value, dispatcher) is implementation, "Construction implementation changed"
    )


def _identity(error):
    if error is None:
        return None
    return dict(id=id(error), type=type.__getattribute__(type(error), "__qualname__"))


def _normal(frame):
    return dis.opname[frame.f_code.co_code[frame.f_lasti]] in ("RETURN_VALUE", "RETURN_CONST")


def _api_check(session=None):
    """Check retained source-created slots before invoking a mutable helper."""
    if _Observation is not _ORIGINAL_CLASS or _Observation.__mro__ != _ORIGINAL_MRO:
        raise OriginRejected("Origin observer class changed")
    current = tuple(vars(_Observation).items())
    if len(current) != len(_CLASS_BINDINGS) or any(
        name != old_name or value is not old_value
        for (name, value), (old_name, old_value) in zip(current, _CLASS_BINDINGS, strict=True)
    ):
        raise OriginRejected("Origin observer class slots changed")
    for function, code, defaults, kwdefaults, closure, namespace, cached in _FUNCTION_BINDINGS:
        if (
            function.__code__ is not code
            or function.__defaults__ is not defaults
            or function.__kwdefaults__ is not kwdefaults
            or function.__closure__ is not closure
            or function.__globals__ is not namespace
            or function.__builtins__ is not cached
        ):
            raise OriginRejected("Origin helper code/defaults/closure/namespace changed")
    for namespace, name, expected in _GLOBAL_BINDINGS:
        if namespace.get(name, _ABSENT) is not expected:
            raise OriginRejected("Origin resolved helper/global changed")
    for module, name, expected in _MODULE_BINDINGS:
        if vars(module).get(name, _ABSENT) is not expected:
            raise OriginRejected("Origin metadata primitive changed")
    if tuple(PINS.items()) != _DECLARED_PINS:
        raise OriginRejected("Origin source pin declaration changed")
    if session is not None:
        if (
            type(session) is not _ORIGINAL_CLASS
            or _SESSION is not session
            or _ISSUED.get(session) is not session.token
        ):
            raise OriginRejected("Exact issued origin session required")
        if any(
            name in vars(session) for name, value in _CLASS_BINDINGS if type(value) is FunctionType
        ):
            raise OriginRejected("Origin instance shadows a source method")


class _Observation:
    def __init__(self):
        self.thread = threading.get_ident()
        self.entered = self.completed = self.invalid = self.hooks_restored = False
        self.closing = False
        self.source_error = self.scope_error = None
        self.interrupted_source_error = self.interrupted_source_frame = None
        self.capture_entry_error = None
        self.capture_errors, self.cleanup_errors, self.events = [], [], []
        self.capture_overflow, self.last_capture_error = 0, None
        self.previous = self.hooks = None
        self.owns_hooks = False
        self.trace_delegates, self.pending = {}, {}
        self.root_frame = self.module_frame = self.factory_frame = self.decorator_frame = None
        self.factory = self.decorator = self.argument = self.core = self.value = None
        self.constructor = self.binding = self.public_binding = None
        self.constructing = self.constructed = self.published = False
        self.assignment_raw = _ABSENT
        self.decorator_trace_flags = []
        self.opcode_frames, self.opcode_codes = {}, {}
        self.import_opcode_events = self.primed_frames = 0
        self.source_files, self.codes = {}, {}
        self.token = object()
        self.events_seen = 0

    def __reduce_ex__(self, protocol):
        raise TypeError("An observed NumPy construction cannot be hydrated")

    def _event(self, name, frame=None):
        _require(len(self.events) < MAX_EVENTS, "Bounded construction event journal exceeded")
        self.events.append(dict(name=name, frame=None if frame is None else id(frame)))

    def _capture(self, stage, error):
        self.invalid = True
        self.last_capture_error = (stage, error)
        if len(self.capture_errors) < MAX_ERRORS:
            self.capture_errors.append((stage, error))
        else:
            self.capture_overflow += 1

    def _restore(self):
        # No exception rendering or user callback is used in a cleared-hook gap.
        for frame, flag in tuple(self.opcode_frames.items()):
            try:
                frame.f_trace_opcodes = flag
                del self.opcode_frames[frame]
            except BaseException as error:
                self.invalid = True
                self.cleanup_errors.append(("restore_opcode_flag", None, error))
        for index in (1, 0):
            try:
                _SYSTEM[index](self.previous[index])
            except BaseException as error:
                self.invalid = True
                self.cleanup_errors.append(("restore", index, error))
        samples = []
        for order in ((0, 1), (1, 0)):
            values = [None, None]
            for index in order:
                try:
                    values[index] = _SYSTEM[index + 2]()
                except BaseException as error:
                    self.invalid = True
                    self.cleanup_errors.append(("sample", index, error))
            samples.append(tuple(values))
        self.hooks_restored = all(
            a is self.previous[0] and b is self.previous[1] for a, b in samples
        )
        self.owns_hooks = not self.hooks_restored
        if not self.hooks_restored:
            self.invalid = True

    def _close_hooks(self):
        try:
            self._restore()
        except BaseException as error:
            self.invalid = True
            self.cleanup_errors.append(("restore_entry_or_return", None, error))
        finally:
            # A rejection before _restore's body cannot skip either setter.
            if self.owns_hooks:
                for index in (1, 0):
                    try:
                        _SYSTEM[index](self.previous[index])
                    except BaseException as error:
                        self.invalid = True
                        self.cleanup_errors.append(("boundary_restore", index, error))
                try:
                    self.hooks_restored = (
                        _SYSTEM[2]() is self.previous[0] and _SYSTEM[3]() is self.previous[1]
                    )
                except BaseException as error:
                    self.invalid = True
                    self.cleanup_errors.append(("boundary_sample", None, error))
                self.owns_hooks = not self.hooks_restored

    def __enter__(self):
        try:
            _api_check(self)
            _require(_SESSION is self and not self.entered and not self.invalid, "One-shot capture")
            self.entered = True
            _require(
                not any(name == "numpy" or name.startswith("numpy.") for name in sys.modules),
                "Capture must precede every NumPy import",
            )
            _require(
                all(
                    a is b
                    for a, b in zip(
                        _SYSTEM,
                        (sys.setprofile, sys.settrace, sys.getprofile, sys.gettrace),
                        strict=True,
                    )
                ),
                "Original hook primitives changed",
            )
            self.source_files = _files()
            self.codes = {p: _compiled(p) for p in (ROOT, SOURCE, OVERRIDES, INSPECT, "functools")}
            self.previous = (_SYSTEM[2](), _SYSTEM[3]())
            self.hooks = (self._profile, self._trace)
            self.owns_hooks = True
            _SYSTEM[0](self.hooks[0])
            _SYSTEM[1](self.hooks[1])
            _require(
                _SYSTEM[2]() is self.hooks[0] and _SYSTEM[3]() is self.hooks[1],
                "Observer setup refused",
            )
            return self
        except BaseException as error:
            self.invalid = True
            self.last_capture_error = ("setup", error)
            try:
                self._capture("setup", error)
            except BaseException as secondary:
                self.capture_entry_error = ("setup", secondary)
            if self.owns_hooks:
                try:
                    self._close_hooks()
                except BaseException as cleanup:
                    self.cleanup_errors.append(("setup_cleanup", None, cleanup))
                finally:
                    if self.owns_hooks:
                        for index in (1, 0):
                            try:
                                _SYSTEM[index](self.previous[index])
                            except BaseException as cleanup:
                                self.cleanup_errors.append(("setup_boundary", index, cleanup))
            raise

    def __exit__(self, kind, error, traceback):
        self.closing = True
        # A rejecting callback can clear its hook after an inner recovery
        # sampled it. Re-establish both hooks at the outer failed-context
        # boundary; a completed import no longer owns downstream hooks.
        if self.previous is not None and not self.completed:
            self.owns_hooks = True
        if error is not None:
            self.scope_error = error
            # The surrounding demo continues after auto-restoration. Its later
            # source failure is not a failed NumPy import and does not erase
            # the already observed, still-authenticated construction.
            if not self.completed:
                self.invalid = True
        if self.owns_hooks:
            try:
                self._close_hooks()
            except BaseException as cleanup:
                self.invalid = True
                self.cleanup_errors.append(("exit_cleanup", None, cleanup))
            finally:
                if self.owns_hooks:
                    for index in (1, 0):
                        try:
                            _SYSTEM[index](self.previous[index])
                        except BaseException as cleanup:
                            self.invalid = True
                            self.cleanup_errors.append(("exit_boundary", index, cleanup))
                    samples = []
                    for order in ((0, 1), (1, 0)):
                        values = [None, None]
                        for index in order:
                            try:
                                values[index] = _SYSTEM[index + 2]()
                            except BaseException as cleanup:
                                self.invalid = True
                                self.cleanup_errors.append(("exit_sample", index, cleanup))
                        samples.append(tuple(values))
                    self.hooks_restored = all(
                        a is self.previous[0] and b is self.previous[1] for a, b in samples
                    )
                    self.owns_hooks = not self.hooks_restored
        if self.source_error is not None and error is not self.source_error:
            raise self.source_error
        if error is not None:
            return False
        _require(
            self.completed and not self.invalid and self.hooks_restored,
            "No complete clean import origin",
        )
        return False

    def _profile(self, frame, event, arg):
        if self.previous[0] is not None:
            try:
                self.previous[0](frame, event, arg)
            except BaseException as error:
                self.invalid = True
                self.last_capture_error = ("inherited_profile", error)
                try:
                    self._capture("inherited_profile", error)
                except BaseException as secondary:
                    self.capture_entry_error = ("inherited_profile", secondary)
                self.last_capture_error = ("inherited_profile", error)
                raise
        if self.invalid and not self.closing and self.owns_hooks:
            try:
                self._close_hooks()
            except BaseException as error:
                self.cleanup_errors.append(("profile_failure_recovery", None, error))
            return
        if (
            event == "call"
            and self.core is not None
            and frame.f_code in (self.core.__code__, self.argument.__code__)
        ):
            error = OriginRejected("Copy or its argument delegate cannot be a provenance probe")
            self._capture("numerical_entry", error)
            raise error

    def _trace(self, frame, event, arg):
        if type(frame) is not FrameType or _FRAME(1) is not frame:
            error = OriginRejected(
                "Only an actual interpreter trace callback may witness construction"
            )
            self._capture("foreign_trace", error)
            raise error
        # Retain the just-assigned C return before an inherited observer can
        # change the fast local. No delegate is called before that observer.
        if (
            frame is self.decorator_frame
            and event == "opcode"
            and frame.f_lasti == self.after_assignment
        ):
            self.assignment_raw = frame.f_locals.get("public_api", _ABSENT)
        tracked = frame in (self.root_frame, self.factory_frame, self.decorator_frame)
        if tracked and event == "exception":
            self.pending[frame] = arg[1]
        if (
            tracked
            and event == "return"
            and frame is not self.interrupted_source_frame
            and not _normal(frame)
        ):
            self.source_error = self.pending.get(frame, self.source_error)
        previous = self.previous[1] if event == "call" else self.trace_delegates.get(frame)
        next_trace = None
        try:
            if previous is not None:
                returned = previous(frame, event, arg)
                # A local None return retains the prior local trace in CPython;
                # a global call returning None does not install a local trace.
                next_trace = previous if returned is None and event != "call" else returned
                if returned is None:
                    if event == "call":
                        self.trace_delegates.pop(frame, None)
                else:
                    _require(
                        len(self.trace_delegates) < MAX_FRAMES or frame in self.trace_delegates,
                        "Too many inherited trace frames",
                    )
                    self.trace_delegates[frame] = returned
        except BaseException as error:
            if tracked and event == "exception":
                self.interrupted_source_error, self.interrupted_source_frame = arg[1], frame
            self.invalid = True
            self.last_capture_error = ("inherited_trace", error)
            try:
                self._capture("inherited_trace", error)
            except BaseException as secondary:
                self.capture_entry_error = ("inherited_trace", secondary)
            self.last_capture_error = ("inherited_trace", error)
            raise
        finally:
            if event == "return":
                self.trace_delegates.pop(frame, None)
        if not self.owns_hooks:
            if next_trace is None:
                frame.f_trace = None
            return next_trace
        if self.invalid and not self.closing:
            try:
                self._close_hooks()
            except BaseException as error:
                self.cleanup_errors.append(("trace_failure_recovery", None, error))
            return next_trace
        if self.closing:
            return self.hooks[1]
        try:
            self._opcode_scope(frame, event)
            self._observe(frame, event, arg)
        except BaseException as error:
            self.invalid = True
            self.last_capture_error = ("observation", error)
            try:
                self._capture("observation", error)
            except BaseException as secondary:
                self.capture_entry_error = ("observation", secondary)
            self.last_capture_error = ("observation", error)
            if self.source_error is not None:
                raise self.source_error  # noqa: B904 - preserve the original explicit cause.
            raise
        if not self.owns_hooks:
            if next_trace is None:
                frame.f_trace = None
            return next_trace
        return self.hooks[1]

    def _opcode_scope(self, frame, event):
        # CPython 3.13.5 needs the opcode flag reapplied at a line boundary;
        # setting it only on the first call event can produce no opcodes.
        # Observe these original construction frames, retaining their flags.
        # Other decorator constructions receive no provenance credit.
        if event == "call" and not self.published:
            key = None
            if (
                frame.f_globals.get("__name__") == "numpy.lib._function_base_impl"
                and frame.f_code.co_name == "<module>"
            ):
                key = SOURCE, "<module>"
            elif (
                frame.f_globals.get("__name__") == "numpy._core.overrides"
                and frame.f_code.co_qualname == "array_function_dispatch.<locals>.decorator"
            ):
                key = OVERRIDES, "array_function_dispatch.<locals>.decorator"
            if key is not None:
                old = self.opcode_codes.get(key)
                if old is None:
                    _require(
                        _code(frame.f_code) == _code(self.codes[key[0]][key[1]]),
                        "Only original import construction code may enable opcodes",
                    )
                    self.opcode_codes[key] = frame.f_code
                else:
                    _require(frame.f_code is old, "Original construction code replaced")
                _require(len(self.opcode_frames) < MAX_FRAMES, "Bounded opcode frame roster")
                self.opcode_frames[frame] = frame.f_trace_opcodes
                frame.f_trace_opcodes = True
                self.primed_frames += 1
        if frame in self.opcode_frames and event == "line":
            frame.f_trace_opcodes = True
        if frame in self.opcode_frames and event == "opcode":
            self.import_opcode_events += 1
            _require(self.import_opcode_events <= MAX_IMPORT_OPCODES, "Bounded import opcodes")
        if frame in self.opcode_frames and event == "return":
            frame.f_trace_opcodes = self.opcode_frames.pop(frame)

    def _live(self):
        source = _module("numpy.lib._function_base_impl", SOURCE)
        overrides = _module("numpy._core.overrides", OVERRIDES)
        inspect = _module("numpy._utils._inspect", INSPECT)
        binary = _module("numpy._core._multiarray_umath", BINARY)
        partial = vars(source).get("array_function_dispatch")
        _require(type(partial) is functools.partial, "Original partial decorator required")
        _require(
            partial.func is self.factory
            and type(partial.args) is tuple
            and len(partial.args) == 0
            and type(partial.keywords) is dict
            and len(partial.keywords) == 1
            and all(type(k) is str and k == "module" for k in partial.keywords)
            and type(partial.keywords["module"]) is str
            and partial.keywords["module"] == "numpy",
            "Original decorator partial changed",
        )
        constructor = vars(binary).get("_ArrayFunctionDispatcher")
        _require(
            vars(overrides).get("_ArrayFunctionDispatcher") is constructor,
            "Dispatcher export changed",
        )
        _require(
            vars(overrides).get("array_function_dispatch") is self.factory
            and vars(overrides).get("functools") is functools
            and vars(overrides).get("getargspec") is vars(inspect).get("getargspec"),
            "Original helper export/namespace changed",
        )
        helpers = (
            self.factory,
            vars(overrides)["verify_matching_signatures"],
            vars(inspect)["getargspec"],
            vars(inspect)["getargs"],
            vars(inspect)["isfunction"],
            vars(inspect)["ismethod"],
            vars(inspect)["iscode"],
            functools.update_wrapper,
            self.argument,
        )
        return (
            source,
            overrides,
            inspect,
            binary,
            partial,
            partial.keywords,
            tuple(partial.keywords.items()),
            _class(constructor),
            tuple(_function_atoms(f) for f in helpers),
            vars(overrides).get("functools"),
            vars(overrides).get("getargspec"),
            vars(overrides).get("ArgSpec"),
            vars(source).get("_copy_dispatcher"),
            functools.WRAPPER_ASSIGNMENTS,
            functools.WRAPPER_UPDATES,
        )

    def _factory_start(self, frame):
        _api_check(self)
        _require(
            self.factory_frame is None and self.root_frame is not None,
            "One genuine factory call required",
        )
        source = _module("numpy.lib._function_base_impl", SOURCE)
        overrides = _module("numpy._core.overrides", OVERRIDES)
        inspect = _module("numpy._utils._inspect", INSPECT)
        _require(
            frame.f_globals is vars(overrides)
            and frame.f_back is not None
            and frame.f_back.f_globals is vars(source)
            and _code(frame.f_back.f_code) == _code(self.codes[SOURCE]["<module>"]),
            "Factory must be called by the original importing module",
        )
        self.factory = _function(
            vars(overrides)["array_function_dispatch"],
            overrides,
            self.codes[OVERRIDES]["array_function_dispatch"],
            (None, None, True, False),
        )
        self.argument = _function(
            vars(source)["_copy_dispatcher"],
            source,
            self.codes[SOURCE]["_copy_dispatcher"],
            (None, None),
        )
        _require(frame.f_code is self.factory.__code__, "Actual original factory body required")
        for name in ("getargspec", "getargs", "isfunction", "ismethod", "iscode"):
            _function(vars(inspect)[name], inspect, self.codes[INSPECT][name], None)
        _function(
            vars(overrides)["verify_matching_signatures"],
            overrides,
            self.codes[OVERRIDES]["verify_matching_signatures"],
            None,
        )
        _function(
            functools.update_wrapper,
            functools,
            self.codes["functools"]["update_wrapper"],
            (
                (
                    "__module__",
                    "__name__",
                    "__qualname__",
                    "__doc__",
                    "__annotations__",
                    "__type_params__",
                ),
                ("__dict__",),
            ),
        )
        local = frame.f_locals
        _require(
            local["dispatcher"] is self.argument
            and type(local["module"]) is str
            and local["module"] == "numpy"
            and local["verify"] is True
            and local["docs_from_dispatcher"] is False,
            "Exact original factory arguments required",
        )
        self.factory_frame, self.module_frame = frame, frame.f_back
        self.binding = self._live()
        self.constructor = vars(_module("numpy._core.overrides", OVERRIDES))[
            "_ArrayFunctionDispatcher"
        ]
        self._event("factory_enter", frame)

    def _decorator_start(self, frame):
        _require(
            self.decorator_frame is None and self.decorator is not None,
            "Original factory return must precede decorator entry",
        )
        _require(
            frame.f_code is self.decorator.__code__
            and frame.f_back is self.module_frame
            and frame.f_globals is self.decorator.__globals__,
            "Original decorator invocation required",
        )
        source = _module("numpy.lib._function_base_impl", SOURCE)
        self.core = _function(
            frame.f_locals["implementation"], source, self.codes[SOURCE]["copy"], ("K", False)
        )
        self.decorator_frame = frame
        self.core_binding = _function_atoms(self.core)
        self.decorator_binding = _function_atoms(self.decorator)
        self.instructions = {i.offset: i for i in dis.get_instructions(frame.f_code)}
        stores = [
            i
            for i in self.instructions.values()
            if i.opname == "STORE_FAST" and i.argval == "public_api"
        ]
        _require(len(stores) == 1, "Exact original constructor assignment required")
        sequence = list(self.instructions.values())
        position = sequence.index(stores[0])
        _require(
            sequence[position - 1].opname.startswith("CALL"), "Original constructor call required"
        )
        self.constructor_call = sequence[position - 1].offset
        self.after_assignment = sequence[position + 1].offset
        self.module_opcodes = self.opcode_frames[self.module_frame]
        self.decorator_opcodes = self.opcode_frames[frame]
        frame.f_trace_opcodes = True
        self.module_frame.f_trace_opcodes = True
        self._event("decorator_enter", frame)

    def _decorator_check(self, frame):
        _api_check(self)
        local = frame.f_locals
        _require(
            local.get("dispatcher") is self.argument
            and local.get("implementation") is self.core
            and type(local.get("module")) is str
            and local.get("module") == "numpy"
            and local.get("verify") is True
            and local.get("docs_from_dispatcher") is False,
            "Construction arguments changed",
        )
        _require(
            _same(self.binding, self._live())
            and _same(self.core_binding, _function_atoms(self.core))
            and _same(self.decorator_binding, _function_atoms(self.decorator)),
            "Construction helpers changed",
        )

    def _observe(self, frame, event, arg):
        _require(
            threading.get_ident() == self.thread and not self.invalid,
            "Stopped or foreign-thread observer",
        )
        module = frame.f_globals.get("__name__")
        if event == "call" and module == "numpy" and frame.f_code.co_name == "<module>":
            _require(
                self.root_frame is None
                and _code(frame.f_code) == _code(self.codes[ROOT]["<module>"]),
                "One original NumPy module import required",
            )
            _require(
                frame.f_globals is vars(_module("numpy", ROOT)), "Original NumPy namespace required"
            )
            self.root_frame = frame
            self._event("numpy_enter", frame)
        if (
            event == "call"
            and module == "numpy._core.overrides"
            and frame.f_code.co_name == "array_function_dispatch"
        ):
            argument = frame.f_locals.get("dispatcher")
            if type(argument) is FunctionType and argument.__name__ == "_copy_dispatcher":
                self._factory_start(frame)
        if frame is self.factory_frame and event == "return":
            _require(
                _normal(frame) and type(arg) is FunctionType,
                "Original decorator factory did not return",
            )
            _require(
                _code(arg.__code__)
                == _code(self.codes[OVERRIDES]["array_function_dispatch.<locals>.decorator"])
                and arg.__globals__ is frame.f_globals,
                "Original decorator code/namespace required",
            )
            self.decorator = arg
            self._event("factory_return", frame)
        if (
            event == "call"
            and self.decorator is not None
            and frame.f_code is self.decorator.__code__
        ):
            if frame.f_locals.get("dispatcher") is self.argument:
                self._decorator_start(frame)
        if self.decorator_frame is not None and not self.published:
            self._decorator_check(self.decorator_frame)
        if frame is self.decorator_frame:
            if len(self.decorator_trace_flags) < 8:
                self.decorator_trace_flags.append((event, frame.f_lasti, frame.f_trace_opcodes))
            if event == "opcode":
                self.events_seen += 1
                _require(self.events_seen <= MAX_EVENTS, "Bounded constructor opcode observation")
                if frame.f_lasti == self.constructor_call:
                    _require(not self.constructing, "Constructor reentry")
                    self.constructing = True
                    self._event("constructor_call", frame)
                if frame.f_lasti == self.after_assignment:
                    _require(
                        self.constructing and not self.constructed,
                        "Observed constructor call required",
                    )
                    self.value = self.assignment_raw
                    _require(
                        self.value is not _ABSENT
                        and frame.f_locals.get("public_api") is self.value,
                        "Inherited observer replaced the original constructor return",
                    )
                    _public(self.value, self.constructor, self.core)
                    self.constructed = True
                    self._event("constructor_assignment", frame)
                if self.constructed:
                    _require(
                        frame.f_locals.get("public_api") is self.value,
                        "Constructor result replaced",
                    )
                    _public(self.value, self.constructor, self.core)
            if event == "return":
                self.return_check = dict(
                    normal=_normal(frame),
                    constructed=self.constructed,
                    same=arg is self.value,
                    returned=id(arg),
                    observed=None if self.value is None else id(self.value),
                    opcode=dis.opname[frame.f_code.co_code[frame.f_lasti]],
                    offset=frame.f_lasti,
                )
                _require(
                    _normal(frame) and self.constructed and arg is self.value,
                    "Original decorator return changed",
                )
                _require(
                    object.__getattribute__(arg, "__wrapped__") is self.core,
                    "Wrapper metadata changed",
                )
                frame.f_trace_opcodes = self.decorator_opcodes
                self._event("decorator_return", frame)
        if (
            frame is self.module_frame
            and event == "opcode"
            and self.constructed
            and not self.published
        ):
            if vars(_module("numpy.lib._function_base_impl", SOURCE)).get("copy") is self.value:
                self.published = True
                frame.f_trace_opcodes = self.module_opcodes
                self.opcode_frames.pop(frame)
                self._event("module_copy_assignment", frame)
        if frame is self.root_frame and event == "return":
            _require(
                _normal(frame) and self.published, "NumPy import did not complete copy construction"
            )
            self._verify_exports()
            self.public_binding = tuple(object.__getattribute__(self.value, "__dict__").items())
            self.source_files = _files()
            self._event("numpy_return", frame)
            self._close_hooks()
            _require(self.hooks_restored and not self.invalid, "Observer restoration refused")
            self.completed = True
            _COMPLETED[self] = (
                self.value,
                self.core,
                self.argument,
                self.token,
                self.root_frame,
                self.module_frame,
                self.factory_frame,
                self.decorator_frame,
                self.binding,
                self.core_binding,
                self.decorator_binding,
                self.public_binding,
            )

    def _verify_exports(self):
        numpy = _module("numpy", ROOT)
        source = _module("numpy.lib._function_base_impl", SOURCE)
        _require(
            vars(numpy).get("copy") is self.value and vars(source).get("copy") is self.value,
            "Actual public/module copy exports changed",
        )
        _require(
            vars(source).get("_copy_dispatcher") is self.argument
            and _same(self.binding, self._live())
            and _same(self.core_binding, _function_atoms(self.core))
            and _same(self.decorator_binding, _function_atoms(self.decorator)),
            "Retained helper bindings changed",
        )
        _public(self.value, self.constructor, self.core)
        _require(
            object.__getattribute__(self.value, "__wrapped__") is self.core,
            "Wrapper export changed",
        )
        functions = vars(_module("numpy._core.overrides", OVERRIDES)).get("ARRAY_FUNCTIONS")
        _require(
            type(functions) is set and self.value in functions,
            "Original dispatcher registration changed",
        )

    def require(self, value, core, argument):
        try:
            _api_check(self)
            _require(
                _SESSION is self and self.completed and not self.invalid and self.hooks_restored,
                "A complete genuine import witness is required",
            )
            _require(threading.get_ident() == self.thread, "Import witness belongs to its thread")
            _require(
                value is self.value and core is self.core and argument is self.argument,
                "Supplied objects are not the observed construction",
            )
            sealed = _COMPLETED.get(self)
            _require(
                type(sealed) is tuple
                and len(sealed) == 12
                and all(
                    a is b
                    for a, b in zip(sealed[:4], (value, core, argument, self.token), strict=True)
                )
                and all(type(frame) is FrameType for frame in sealed[4:8])
                and all(
                    a is b
                    for a, b in zip(
                        sealed[8:],
                        (
                            self.binding,
                            self.core_binding,
                            self.decorator_binding,
                            self.public_binding,
                        ),
                        strict=True,
                    )
                ),
                "Only the interpreter-observed completed construction can issue proof",
            )
            _require(
                vars(_module("numpy", ROOT))["__spec__"]._initializing is False,
                "Original import is still initializing",
            )
            self._verify_exports()
            _require(
                _same(
                    self.public_binding,
                    tuple(object.__getattribute__(self.value, "__dict__").items()),
                ),
                "Public dispatcher attributes changed",
            )
            _require(_files() == self.source_files, "Construction sources changed")
            return self.token
        except BaseException as error:
            self._capture("require_copy", error)
            raise


def capture():
    """Install before the first NumPy import; never imports NumPy itself."""
    global _SESSION
    if _api_check is not _API_CHECK or _api_check.__code__ is not _API_CHECK_CODE:
        raise OriginRejected("Original source-created API validator required")
    _api_check()
    if _SESSION is not None or _ISSUED:
        error = OriginRejected("One import-origin capture per process; reentry is irreversible")
        for session in _ISSUED:
            session._capture("reentry", error)
        raise error
    _SESSION = _Observation()
    _ISSUED[_SESSION] = _SESSION.token
    return _SESSION


def require_copy(value, core, argument):
    """Return the same immutable live token for the exact observed three objects."""
    if _api_check is not _API_CHECK or _api_check.__code__ is not _API_CHECK_CODE:
        raise OriginRejected("Original source-created API validator required")
    _api_check()
    _require(_SESSION is not None, "No original NumPy import was observed")
    _api_check(_SESSION)
    result = _ORIGINAL_REQUIRE(_SESSION, value, core, argument)
    _api_check(_SESSION)
    return result


def record():
    """JSON-safe diagnostics only. IDs and saved records never create authority."""
    value = _SESSION
    if value is None:
        return dict(
            kind=KIND,
            completed=False,
            hooks_restored=False,
            source_error=None,
            capture_errors=[],
            cleanup_errors=[],
            source_files={},
        )
    return dict(
        kind=KIND,
        completed=bool(value.completed and not value.invalid),
        hooks_restored=bool(value.hooks_restored),
        source_error=_identity(value.source_error),
        interrupted_source_error=_identity(value.interrupted_source_error),
        interrupted_source_cause=(
            None
            if value.interrupted_source_error is None
            else _identity(value.interrupted_source_error.__cause__)
        ),
        interrupted_source_frame=(
            None if value.interrupted_source_frame is None else id(value.interrupted_source_frame)
        ),
        interrupted_exception_is_completed_unwind=False,
        scope_error=_identity(value.scope_error),
        capture_errors=[dict(stage=s, error=_identity(e)) for s, e in value.capture_errors],
        cleanup_errors=[
            dict(stage=s, hook=i, error=_identity(e)) for s, i, e in value.cleanup_errors
        ],
        capture_error_overflow=value.capture_overflow,
        capture_entry_error=(
            None
            if value.capture_entry_error is None
            else dict(
                stage=value.capture_entry_error[0], error=_identity(value.capture_entry_error[1])
            )
        ),
        last_capture_error=(
            None
            if value.last_capture_error is None
            else dict(
                stage=value.last_capture_error[0], error=_identity(value.last_capture_error[1])
            )
        ),
        source_files=dict(value.source_files),
        objects={
            name: None if getattr(value, name) is None else id(getattr(value, name))
            for name in (
                "factory",
                "decorator",
                "argument",
                "core",
                "constructor",
                "value",
                "token",
            )
        },
        events=list(value.events),
        constructor_opcode_events=value.events_seen,
        import_opcode_events=value.import_opcode_events,
        primed_code_frames=value.primed_frames,
        decorator_trace_flags=value.decorator_trace_flags,
        decorator_return_check=getattr(value, "return_check", None),
        factory_arguments=dict(
            dispatcher=None if value.argument is None else id(value.argument),
            module="numpy",
            verify=True,
            docs_from_dispatcher=False,
        ),
        numerical_probe_calls=0,
        authority_from_saved_record=False,
        automatic_hook_restoration=(
            "Original numpy module return; final import state rechecked by require_copy"
        ),
    )


# Immutable import-time references are separate from mutable progress fields.
# The only issuance mutation is capture(); a completed seal is written only by
# the actual traced NumPy return after construction and restoration checks.
_ORIGINAL_CLASS, _ORIGINAL_MRO = _Observation, _Observation.__mro__
_ORIGINAL_REQUIRE = _Observation.require
_API_CHECK, _API_CHECK_CODE = _api_check, _api_check.__code__
_CLASS_BINDINGS = tuple(vars(_Observation).items())
_FUNCTION_BINDINGS = tuple(
    (
        value,
        value.__code__,
        value.__defaults__,
        value.__kwdefaults__,
        value.__closure__,
        value.__globals__,
        value.__builtins__,
    )
    for value in (*tuple(globals().values()), *tuple(vars(_Observation).values()))
    if type(value) is FunctionType and value.__globals__ is globals()
)
_DECLARED_PINS = tuple(PINS.items())
_MODULE_BINDINGS = tuple(
    (module, name, vars(module)[name])
    for module, names in (
        (sys, ("setprofile", "settrace", "getprofile", "gettrace", "_getframe")),
        (hashlib, ("sha256", "file_digest")),
        (threading, ("get_ident",)),
        (struct, ("pack",)),
        (dis, ("get_instructions",)),
        (builtins, ("compile", "getattr", "type", "vars", "id")),
    )
    for name in names
)
_GLOBAL_BINDINGS = tuple(
    (namespace, name, namespace.get(name, _ABSENT))
    for function, *_ in _FUNCTION_BINDINGS
    for namespace in (function.__globals__, function.__builtins__)
    for name in function.__code__.co_names
    if name not in ("_SESSION", "_GLOBAL_BINDINGS")
)
