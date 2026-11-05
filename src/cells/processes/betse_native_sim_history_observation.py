"""Held read-only traversal of one genuine completed SIM history.

Full original authority/cache validation brackets the interval. Every boundary
rechecks all actual immutable cache storage/header/descriptor associations and
captures the live state/graph/RNG freshly. Each selected row's three payloads
reach the original validator again; successful closure requires every row.
The interval is an observation token, never another history or execution owner.
"""

import hashlib
import os
import struct
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import get_ident
from types import FunctionType, MethodType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_sim_run as parent

RELEASE = "CELLS_NATIVE_SIM_HISTORY_OBSERVATION_RELEASED"
LAW_ID = "actual_completed_SIM_read_only_complete_history_interval@1"
PARENT_SHA256 = "c3238c6c6704f8bc133d23450235eb2b742e6505530bd47de0d590a958e3e4d4"
PARENT_REVIEW_SHA256 = None
MAX_OPERATIONS = 100000
_PENDING, _FAILED = None, []
_ISSUED = WeakKeyDictionary()
_CACHE = parent.previous.terminal.retained_cache
_NUMPY, _ARRAY, _CACHE_TYPE, _COLUMN_TYPE = (
    _CACHE.np,
    _CACHE.np.ndarray,
    _CACHE.Cache,
    _CACHE.CacheColumn,
)
_FUNCTION_NAMES = (
    "completed_sim",
    "validate_sim",
    "_links",
    "_bindings",
    "_stable",
    "_snapshot",
    "_metadata",
    "_same",
    "record_document",
    "_digest",
    "_observation_roster",
)
_API = tuple(
    (parent, name, function, function.__code__, function.__globals__, function.__builtins__)
    for name in _FUNCTION_NAMES
    for function in (vars(parent)[name],)
) + tuple(
    (module, name, function, function.__code__, function.__globals__, function.__builtins__)
    for module, name in (
        (_CACHE, "validate"),
        (parent.previous.terminal, "_column_bytes"),
        (parent, "_recover"),
    )
    for function in (vars(module)[name],)
)
_ATTRIBUTES = tuple(
    (holder, name, actual)
    for _, _, function, _, _, _ in _API
    for holder, name, actual in parent._attributes(function)
)
_CLASS_API = tuple(
    (
        cls,
        cls.__mro__,
        tuple(vars(cls).items()),
        tuple(
            (function, function.__code__, function.__globals__, function.__builtins__)
            for actual in vars(cls).values()
            for function in ((actual.fget,) if type(actual) is property else (actual,))
            if type(function) is FunctionType
        ),
    )
    for cls in (_CACHE_TYPE, _COLUMN_TYPE)
)


class HistoryObservationRejected(ValueError):
    def __init__(self, reason, *, stage, partial=None):
        super().__init__(reason)
        self.stage, self.partial = stage, partial


@dataclass(frozen=True, slots=True)
class ObservationRecord:
    law: str
    status: str
    trial_identity: str
    configured_rows: int
    checked_rows: tuple
    work: tuple
    full_authority_attempts: int
    full_authority_returns: int
    retained_payload_attempts: int
    retained_payload_returns: int
    source_metadata_operations: int
    source_retained_cache_attempts: int
    source_retained_cache_returns: int
    callback_calls: tuple
    native_or_scientific_credit: int = 0


def source_plan():
    return dict(
        law=LAW_ID,
        parent=(PARENT_SHA256, PARENT_REVIEW_SHA256),
        entry="observing_completed(owner, *, enabled=False)",
        entry_wrapper="stdlib contextmanager; __wrapped__ is this module's original generator",
        methods=(
            "completed_sim()",
            "validate_sim(*, row=None, caches=())",
            "call(callback, *args, row=None, caches=(), **kwargs)",
        ),
        full_authority=(
            "original completed_sim at entry; original validate_sim at exit, including failure exit"
        ),
        each_boundary=(
            "all cache/row roots and immutable bytes/header/descriptor proofs; "
            "fresh live values/graph/RNG"
        ),
        each_row=(
            "all three original cache validators again; every row required before successful close"
        ),
        callbacks="original result/error retained; active reentry and captured failure are sticky",
        maximum_rows=parent.MAX_ITERATIONS,
        maximum_operation_records=MAX_OPERATIONS,
        no_hydration_or_new_history_owner=True,
        native_or_scientific_admission=False,
    )


def _producer():
    _check_self(None)
    pin = parent.previous.preparation._pin
    if not pin(PARENT_SHA256) or not pin(PARENT_REVIEW_SHA256):
        raise HistoryObservationRejected(
            "Reviewed completed-SIM producer held", stage="producer_held"
        )
    path = Path(parent.__file__)
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != PARENT_SHA256:
        raise HistoryObservationRejected("Exact completed-SIM producer required", stage="producer")
    for module, name, function, code, namespace, builtins in _API:
        if (
            vars(module).get(name) is not function
            or function.__code__ is not code
            or function.__globals__ is not namespace
            or namespace is not vars(module)
            or function.__builtins__ is not builtins
        ):
            raise HistoryObservationRejected(
                "Original observation helper changed: " + name, stage="binding"
            )
    for holder, name, actual in _ATTRIBUTES:
        if vars(holder).get(name) is not actual:
            raise HistoryObservationRejected(
                "Reached observation lookup changed: " + name, stage="binding"
            )
    for cls, mro, members, functions in _CLASS_API:
        current = vars(cls)
        if (
            cls.__mro__ is not mro
            or len(current) != len(members)
            or any(current.get(name) is not value for name, value in members)
        ):
            raise HistoryObservationRejected(
                "Original cache class dispatch changed", stage="binding"
            )
        if any(
            function.__code__ is not code
            or function.__globals__ is not namespace
            or function.__builtins__ is not builtins
            for function, code, namespace, builtins in functions
        ):
            raise HistoryObservationRejected(
                "Original cache method executable changed", stage="binding"
            )
    if (
        _CACHE.np is not _NUMPY
        or _NUMPY.ndarray is not _ARRAY
        or _CACHE.Cache is not _CACHE_TYPE
        or _CACHE.CacheColumn is not _COLUMN_TYPE
    ):
        raise HistoryObservationRejected(
            "Original immutable cache types/runtime changed", stage="binding"
        )
    parent._ready()
    return parent


def _reject(context, reason, stage):
    context.invalid = True
    if context.entry_error is None:
        context.entry_error = HistoryObservationRejected(reason, stage=stage, partial=context)
    raise context.entry_error


def _remember(context, label, error, raw=None):
    context.last_error = (label, error, raw)
    try:
        context.secondary.append(context.last_error)
    except BaseException as secondary:
        context.recording_error = (secondary, context.last_error)


def _work(context, label, function, *args, **kwargs):
    if len(context.work) >= MAX_OPERATIONS:
        _reject(context, "Declared observation operations exhausted", "work")
    row = dict(
        sequence=len(context.work),
        call=label,
        status="entered",
        cache_checks=0,
        columns=0,
        payload_attempts=0,
        payload_returns=0,
    )
    context.work.append(row)
    previous = context.operation
    context.operation = row
    try:
        result = function(*args, **kwargs)
    except BaseException as error:
        row["status"] = "failed"
        context.last_operation_failure = (row, error)
        raise
    else:
        row["status"] = "returned"
        return result
    finally:
        context.operation = previous


def _caches(trial):
    count = parent._count(len(trial.iterations))
    if (
        type(trial.iterations) is not tuple
        or len(trial.rng_before) != 2
        or len(trial.rng_after) != 2
        or any(
            type(row) is not parent.Iteration or type(row.rng) is not tuple or len(row.rng) != 2
            for row in trial.iterations
        )
    ):
        raise ValueError("Complete actual typed row/RNG roster required")
    result = (
        trial.before,
        trial.ready[0],
        trial.after[0],
        trial.calendar,
        trial.sampled,
        *trial.rng_before,
        *trial.rng_after,
        *(row.after for row in trial.iterations),
        *(value for row in trial.iterations for value in row.rng),
    )
    if len(result) != 9 + 3 * count:
        raise ValueError("Complete actual retained cache occurrence roster required")
    return result


def _column(value):
    raw = parent.previous.terminal._column_bytes(value)
    return (
        value,
        value.dtype,
        tuple(value.shape),
        tuple(value.strides),
        value.nbytes,
        bool(value.flags.writeable),
        bool(value.flags.c_contiguous),
        bool(value.flags.f_contiguous),
        value.ctypes.data,
        raw,
    )


def _proof(cache):
    if (
        type(cache) is not _CACHE_TYPE
        or type(cache.descriptor_json) is not str
        or type(cache.identity) is not str
        or type(cache.all_finite) is not bool
        or type(cache.columns) is not tuple
        or any(
            type(column) is not _COLUMN_TYPE or type(column.name) is not str
            for column in cache.columns
        )
    ):
        raise ValueError("Exact complete immutable Cache/column types required")
    return (
        cache,
        cache.descriptor_json,
        cache.columns,
        cache.all_finite,
        cache.identity,
        tuple((column, column.name, _column(column.values)) for column in cache.columns),
    )


def _check_proof(context, proof, index):
    cache, descriptor, columns, finite, identity, records = proof
    context.last_cache = (index, cache)
    context.operation["cache_checks"] += 1
    if (
        type(cache) is not _CACHE_TYPE
        or cache.descriptor_json is not descriptor
        or cache.columns is not columns
        or cache.all_finite is not finite
        or cache.identity is not identity
    ):
        raise ValueError("Original complete cache descriptor/column roots changed")
    for column, name, saved in records:
        context.last_cache = (index, cache, column)
        context.operation["columns"] += 1
        if (
            type(column) is not _COLUMN_TYPE
            or column.name is not name
            or column.values is not saved[0]
        ):
            raise ValueError("Original cache column identity/name changed")
        actual = _column(column.values)
        if (
            actual[0] is not saved[0]
            or actual[1] is not saved[1]
            or actual[-1] is not saved[-1]
            or actual[2:-1] != saved[2:-1]
        ):
            raise ValueError("Original complete immutable column bits/header/storage changed")


def _row_record(row):
    if (
        type(row) is not parent.Iteration
        or type(row.ordinal) is not int
        or type(row.sampled) is not bool
        or type(row.work_end) is not int
    ):
        raise ValueError("Original typed iteration required")
    return (
        row,
        row.ordinal,
        type(row.source_time),
        struct.pack("!d", row.source_time),
        row.sampled,
        row.after,
        row.graph,
        row.rng,
        row.event_calls,
        row.callback_calls,
        row.work_end,
    )


def _roster(context):
    actual = _caches(context.trial)
    if len(actual) != len(context.proofs) or any(
        cache is not proof[0] for cache, proof in zip(actual, context.proofs, strict=True)
    ):
        raise ValueError("Original cache occurrence order/identity changed")
    if context.trial.iterations is not context.rows:
        raise ValueError("Original completed iteration tuple changed")
    for index, (row, saved) in enumerate(zip(context.rows, context.row_records, strict=True)):
        current = _row_record(row)
        if (
            current[0] is not saved[0]
            or current[1] != index
            or current[1:5] != saved[1:5]
            or current[-1] != saved[-1]
            or any(a is not b for a, b in zip(current[5:10], saved[5:10], strict=True))
        ):
            raise ValueError("Original row/time/cache/graph/event/callback association changed")
    for index, proof in enumerate(context.proofs):
        _check_proof(context, proof, index)


def _guard(context):
    if context.entry_error is not None:
        raise context.entry_error
    if (
        context.invalid
        or not context.active
        or _PENDING is not context.attempt
        or context.attempt["invalid"]
        or context.thread != get_ident()
        or _ISSUED.get(context.token) is not context
        or not parent._ACTIVE
        or parent._ACTIVE[-1] is not context
        or parent._PREPARING is not context.attempt
    ):
        _reject(context, "Actual exclusive active observation interval required", "epoch")
    if sys.getprofile() is not context.prior[0] or sys.gettrace() is not context.prior[1]:
        _reject(context, "Both original inherited observer hooks required", "hooks")


def _live(context):
    _check_self(context)
    _guard(context)
    if _producer() is not parent or parent._ISSUED.get(context.owner) is not context.source:
        _reject(context, "Original actually issued completed owner required", "owner")
    source = context.source
    if (
        source.owner is not context.owner
        or source.trial is not context.trial
        or source.active
        or source.invalid
    ):
        _reject(context, "Original completed source epoch changed", "owner")
    parent._links(source)
    parent._bindings(source)
    if context.trial.identity != context.identity or context.trial.identity != parent._digest(
        parent.record_document(context.trial)
    ):
        raise ValueError("Original complete trial metadata changed")
    _roster(context)
    stable = parent._metadata(source, "history_interval_fresh_stable_state", parent._stable, source)
    if stable.identity != source.stable.identity:
        raise ValueError("Actual completed stable state changed")
    current = parent._metadata(
        source, "history_interval_fresh_live_state_graph_RNG", parent._snapshot, source
    )
    if current[0].identity != source.after[0].identity:
        raise ValueError("Actual completed values changed")
    parent._same(current[1][0], source.after[1][0])
    if current[1][1] != source.after[1][1] or tuple(v.identity for v in current[2]) != tuple(
        v.identity for v in source.after[2]
    ):
        raise ValueError("Actual completed graph/layout/aliases/RNG changed")
    objects, fields = parent._observation_roster(source)
    for actual, expected in (
        (objects, context.view["observation_objects"]),
        (fields, context.view["observation_field_objects"]),
    ):
        if len(actual) != len(expected) or any(
            a[0] != b[0] or a[1] is not b[1] for a, b in zip(actual, expected, strict=True)
        ):
            raise ValueError("Original full observation object roster changed")
    _guard(context)


def _payload(context, cache):
    if not any(cache is proof[0] for proof in context.proofs):
        raise ValueError("Actual retained cache occurrence required")
    context.last_payload = (context.payload_attempts, cache)
    context.payload_attempts += 1
    context.operation["payload_attempts"] += 1
    result = _CACHE.validate(cache)
    context.payload_returns += 1
    context.operation["payload_returns"] += 1
    if result is not cache:
        raise ValueError("Original cache validator must return the identical cache")


def _validate(context, row, caches):
    _live(context)
    if type(caches) is not tuple:
        raise ValueError("Explicit tuple of actual retained caches required")
    if row is not None:
        if (
            type(row) is not parent.Iteration
            or type(row.ordinal) is not int
            or not 0 <= row.ordinal < len(context.rows)
            or context.rows[row.ordinal] is not row
        ):
            raise ValueError("Original identical retained iteration required")
        for cache in (row.after, *row.rng):
            _payload(context, cache)
        context.checked_rows.add(row.ordinal)
    for cache in caches:
        _payload(context, cache)
    _roster(context)
    _guard(context)
    return context.trial


def _token_context(token):
    if type(token) is not CompletedHistoryObservation or token not in _ISSUED:
        raise HistoryObservationRejected(
            "Actual issued observation interval required", stage="interval"
        )
    context = _ISSUED[token]
    _guard(context)
    if context.busy:
        _reject(context, "Reentrant observation/capture operation", "reentrant")
    return context


class CompletedHistoryObservation:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Only the actual completed-history interval issues this token")

    def __reduce_ex__(self, protocol):
        raise TypeError("An active observation interval cannot be hydrated")

    def validate_sim(self, *, row=None, caches=()):
        context = _token_context(self)
        context.busy = True
        try:
            return _work(
                context,
                "fresh_live_and_selected_payload_validation",
                _validate,
                context,
                row,
                caches,
            )
        except BaseException as error:
            context.invalid = True
            if context.primary is None:
                context.primary = error
            raise
        finally:
            context.busy = False

    def completed_sim(self):
        self.validate_sim()
        return dict(_ISSUED[self].view)

    def call(self, callback, *args, row=None, caches=(), **kwargs):
        context = _token_context(self)
        context.busy = True
        context.raw_callback = (callback, args, kwargs, row, caches)
        raw = dict(
            sequence=len(context.callbacks),
            input=context.raw_callback,
            result=None,
            error=None,
            status="entered",
        )
        context.callbacks.append(raw)
        try:
            _work(context, "before_capture", _validate, context, row, caches)
            if type(callback) not in (FunctionType, MethodType):
                raise TypeError("Original explicit function/method capture callback required")
            result = _work(context, "capture_callback", callback, *args, **kwargs)
            context.raw_callback_result = result
            raw["result"], raw["status"] = result, "returned"
            if context.api_guard.__code__ is not context.api_guard_code:
                context.invalid = True
                raise HistoryObservationRejected(
                    "Observation guard code changed", stage="binding", partial=context
                )
            context.api_guard(context)
            _work(context, "after_capture", _validate, context, row, caches)
            return result
        except BaseException as error:
            raw["error"], raw["status"] = error, "failed"
            context.invalid = True
            if context.primary is None:
                context.primary = error
            raise
        finally:
            context.busy = False

    @property
    def record(self):
        if type(self) is not CompletedHistoryObservation or self not in _ISSUED:
            raise HistoryObservationRejected("Actual interval record required", stage="interval")
        return _ISSUED[self].record


def _restore(context):
    try:
        parent._recover(context, context.prior)
    except BaseException as error:
        _remember(context, "recovery_entry", error)
    finally:
        for label, getter, setter, original in (
            ("trace", sys.gettrace, sys.settrace, context.prior[1]),
            ("profile", sys.getprofile, sys.setprofile, context.prior[0]),
        ):
            for attempt in range(3):
                try:
                    if getter() is not original:
                        setter(original)
                    if getter() is original:
                        break
                except BaseException as error:
                    _remember(context, label, error, attempt)
        final = []
        for name, getter in (("profile", sys.getprofile), ("trace", sys.gettrace)):
            try:
                final.append(getter())
            except BaseException as error:
                _remember(context, name + "_final", error)
                final.append(None)
        context.final_hooks = tuple(final)


def _record(context, status):
    return ObservationRecord(
        LAW_ID,
        status,
        context.identity,
        len(context.rows),
        tuple(sorted(context.checked_rows)),
        tuple(
            (
                r["sequence"],
                r["call"],
                r["status"],
                r["cache_checks"],
                r["columns"],
                r["payload_attempts"],
                r["payload_returns"],
            )
            for r in context.work
        ),
        context.full_attempts,
        context.full_returns,
        context.payload_attempts,
        context.payload_returns,
        len(context.source.metadata_work) - context.source_metadata_start,
        context.source.retained_validation_attempts - context.source_retained_start,
        context.source.retained_validation_returns - context.source_retained_return_start,
        tuple((row["sequence"], row["status"]) for row in context.callbacks),
    )


def _exit_api(context):
    """Authenticate the retained exit delegate after arbitrary body/cleanup.

    Return that exact retained function; never perform a mutable module lookup
    at the callsite. Entry admission also checks the actual executing frame;
    a post-call check alone cannot prevent a self-restoring code substitution.
    """
    if context.api_guard.__code__ is not context.api_guard_code:
        raise ValueError("Original observation guard executable changed at exit")
    context.api_guard(context)
    if _producer() is not context.exit_parent:
        raise ValueError("Original full-exit producer changed")
    function, code, namespace, builtins, defaults, keywords, closure = context.exit_binding
    if (
        vars(context.exit_parent).get("validate_sim") is not function
        or type(function) is not FunctionType
        or function.__code__ is not code
        or function.__globals__ is not namespace
        or function.__builtins__ is not builtins
        or function.__defaults__ is not defaults
    ):
        raise ValueError("Original full-exit callable/code/globals changed")
    current = function.__kwdefaults__ or {}
    if len(current) != len(keywords) or any(
        key not in current or current[key] is not value for key, value in keywords
    ):
        raise ValueError("Original full-exit keyword defaults changed")
    cells = function.__closure__ or ()
    if len(cells) != len(closure) or any(
        cell is not old or cell.cell_contents is not value
        for cell, (old, value) in zip(cells, closure, strict=True)
    ):
        raise ValueError("Original full-exit closure changed")
    return function


@contextmanager
def observing_completed(owner, *, enabled=False):
    """A full, exclusive read-only traversal; no native or history owner issue."""
    global _PENDING
    if _PENDING is not None:
        _PENDING["invalid"] = True
        context = _PENDING["context"]
        if context is not None:
            _reject(context, "Reentrant completed-history interval", "reentrant")
        if _PENDING["entry_error"] is None:
            _PENDING["entry_error"] = HistoryObservationRejected(
                "Reentrant completed-history admission", stage="reentrant", partial=_PENDING
            )
        raise _PENDING["entry_error"]
    attempt = dict(owner=owner, context=None, invalid=False, entry_error=None)
    _PENDING = attempt
    context = None
    try:
        if enabled is not True or os.environ.get(RELEASE) != "1":
            raise HistoryObservationRejected("Completed-history observation held", stage="release")
        attempt["prior"] = sys.getprofile(), sys.gettrace()
        if parent._PREPARING is not None or parent._ACTIVE:
            raise HistoryObservationRejected("Actual source admission overlaps", stage="exclusive")
        parent._PREPARING = attempt
        _producer()
        if attempt["invalid"]:
            raise attempt["entry_error"]
        with parent._LOCK:
            if parent._ACTIVE or parent._PREPARING is not attempt:
                raise HistoryObservationRejected(
                    "Actual source execution/observation overlaps", stage="exclusive"
                )
            if type(owner) is not parent.SimRunOwner or owner not in parent._ISSUED:
                raise HistoryObservationRejected(
                    "Actual completed SIM owner required", stage="owner"
                )
            source = parent._ISSUED[owner]
            trial = source.trial
            exit_function = vars(parent).get("validate_sim")
            if type(exit_function) is not FunctionType:
                raise HistoryObservationRejected(
                    "Original full-exit function required", stage="binding"
                )
            context = SimpleNamespace(
                attempt=attempt,
                owner=owner,
                source=source,
                trial=trial,
                identity=trial.identity,
                rows=trial.iterations,
                row_records=tuple(_row_record(row) for row in trial.iterations),
                proofs=tuple(_proof(cache) for cache in _caches(trial)),
                token=None,
                view=None,
                active=True,
                invalid=False,
                busy=False,
                thread=get_ident(),
                entry_error=None,
                primary=None,
                secondary=[],
                last_error=None,
                recording_error=None,
                work=[],
                operation=None,
                payload_attempts=0,
                payload_returns=0,
                full_attempts=0,
                full_returns=0,
                raw_callback=None,
                raw_callback_result=None,
                last_cache=None,
                last_payload=None,
                last_operation_failure=None,
                checked_rows=set(),
                prior=attempt["prior"],
                callbacks=[],
                source_metadata_start=len(source.metadata_work),
                source_retained_start=source.retained_validation_attempts,
                source_retained_return_start=source.retained_validation_returns,
                cleanup_errors=[],
                last_cleanup_error=None,
                last_cleanup_recording_error=None,
                final_hooks=None,
                record=None,
                api_bindings=_SELF_API,
                api_guard=_check_self,
                api_guard_code=_check_self.__code__,
                exit_parent=parent,
                exit_entry=None,
                exit_entry_events=[],
                exit_binding=(
                    exit_function,
                    exit_function.__code__,
                    exit_function.__globals__,
                    exit_function.__builtins__,
                    exit_function.__defaults__,
                    tuple((exit_function.__kwdefaults__ or {}).items()),
                    tuple((cell, cell.cell_contents) for cell in (exit_function.__closure__ or ())),
                ),
            )
            attempt["context"] = context
            if attempt["invalid"]:
                context.entry_error = attempt["entry_error"]
                raise context.entry_error
            parent._ACTIVE.append(context)
            try:
                if context.invalid or attempt["invalid"]:
                    raise context.entry_error
                context.full_attempts += 1
                context.view = parent.completed_sim(owner)
                context.full_returns += 1
                if (
                    context.view["owner"] is not owner
                    or context.view["trial"] is not trial
                    or attempt["invalid"]
                ):
                    _reject(context, "Original complete authority/view required", "entry")
                token = object.__new__(CompletedHistoryObservation)
                context.token = token
                _ISSUED[token] = context
                _work(context, "entry_immutable_and_live_verification", _live, context)
                try:
                    yield token
                except BaseException as error:
                    context.invalid = True
                    if context.primary is None:
                        context.primary = error
                finally:
                    try:
                        _restore(context)
                    except BaseException as error:
                        context.last_error = ("restore_boundary", error, None)
                        context.invalid = True
                    finally:
                        # Recovery is also protected in the caller. An
                        # inherited entry hook may reject _restore itself.
                        for label, getter, setter, original in (
                            ("trace", sys.gettrace, sys.settrace, context.prior[1]),
                            ("profile", sys.getprofile, sys.setprofile, context.prior[0]),
                        ):
                            for attempt_index in range(3):
                                try:
                                    if getter() is not original:
                                        setter(original)
                                    if getter() is original:
                                        break
                                except BaseException as error:
                                    context.last_error = (label, error, attempt_index)
                                    context.invalid = True
                        final = []
                        for label, getter in (("profile", sys.getprofile), ("trace", sys.gettrace)):
                            try:
                                final.append(getter())
                            except BaseException as error:
                                context.last_error = (label + "_final", error, None)
                                context.invalid = True
                                final.append(None)
                        context.final_hooks = tuple(final)
                    try:
                        exit_delegate = _work(context, "full_exit_API_before", _exit_api, context)
                        context.full_attempts += 1
                        dispatch = sys._getframe()
                        expected = context.exit_binding
                        old_hooks = sys.getprofile(), sys.gettrace()
                        locals_ = {}
                        armed = False

                        def admit(frame, event):
                            # A function's current __code__ is insufficient:
                            # an inherited hook may restore it after a foreign
                            # frame was already created for this exact call.
                            if not armed:
                                return
                            target = event == "call" and frame.f_back is dispatch
                            if not target and frame is not context.exit_entry:
                                return
                            context.exit_entry_events.append((frame, event))
                            function, code, namespace, cached, defaults, keywords, closure = (
                                expected
                            )
                            if (
                                sys.getprofile() is not profile
                                or sys.gettrace() is not trace
                                or exit_delegate is not function
                                or vars(context.exit_parent).get("validate_sim") is not function
                                or function.__code__ is not code
                                or frame.f_code is not code
                                or frame.f_globals is not namespace
                                or frame.f_builtins is not cached
                                or function.__globals__ is not namespace
                                or function.__builtins__ is not cached
                                or function.__defaults__ is not defaults
                                or frame.f_locals.get(code.co_varnames[0]) is not owner
                            ):
                                raise ValueError(
                                    "Original full-exit call-boundary executable required"
                                )
                            current = function.__kwdefaults__ or {}
                            cells = function.__closure__ or ()
                            if (
                                len(current) != len(keywords)
                                or any(current.get(key) is not value for key, value in keywords)
                                or len(cells) != len(closure)
                                or any(
                                    cell is not old
                                    or cell.cell_contents is not value
                                    or frame.f_locals.get(name) is not value
                                    for name, cell, (old, value) in zip(
                                        code.co_freevars, cells, closure, strict=True
                                    )
                                )
                            ):
                                raise ValueError(
                                    "Original full-exit call-boundary closure required"
                                )
                            if target:
                                if (
                                    context.exit_entry is not None
                                    and context.exit_entry is not frame
                                ):
                                    raise ValueError("One actual original full-exit entry required")
                                context.exit_entry = frame

                        admit_code = admit.__code__

                        def profile(frame, event, arg):
                            if old_hooks[0] is not None:
                                old_hooks[0](frame, event, arg)
                            if admit.__code__ is not admit_code:
                                raise ValueError("Original full-exit admission code changed")
                            admit(frame, event)

                        def trace(frame, event, arg):
                            fn = old_hooks[1] if event == "call" else locals_.get(id(frame))
                            result = None if fn is None else fn(frame, event, arg)
                            if event == "return":
                                locals_.pop(id(frame), None)
                            elif result is not None:
                                locals_[id(frame)] = result
                            if admit.__code__ is not admit_code:
                                raise ValueError("Original full-exit admission code changed")
                            admit(frame, event)
                            return trace

                        gate_primary = None
                        try:
                            sys.setprofile(profile)
                            sys.settrace(trace)
                            armed = True
                            result = exit_delegate(owner)
                        except BaseException as error:
                            gate_primary = error
                            raise
                        finally:
                            armed = False
                            # A rejected entry can disable the hook that
                            # rejected it. Recover both independently, even
                            # when the other inherited hook also refuses.
                            for label, getter, setter, original in (
                                ("trace", sys.gettrace, sys.settrace, old_hooks[1]),
                                ("profile", sys.getprofile, sys.setprofile, old_hooks[0]),
                            ):
                                for index in range(3):
                                    try:
                                        setter(original)
                                        if getter() is original:
                                            break
                                    except BaseException as error:
                                        context.last_error = (label + "_exit_gate", error, index)
                                        context.invalid = True
                            final_gate = []
                            for label, getter in (
                                ("profile", sys.getprofile),
                                ("trace", sys.gettrace),
                            ):
                                try:
                                    final_gate.append(getter())
                                except BaseException as error:
                                    context.last_error = (label + "_exit_gate_final", error, None)
                                    context.invalid = True
                                    final_gate.append(None)
                            if (
                                final_gate[0] is not old_hooks[0]
                                or final_gate[1] is not old_hooks[1]
                            ):
                                error = ValueError("Original full-exit observer hooks not restored")
                                _remember(context, "exit_gate_recovery", error)
                                context.invalid = True
                                if gate_primary is None:
                                    raise error
                        context.full_returns += 1
                        _work(context, "full_exit_API_after", _exit_api, context)
                        if result is not trial:
                            raise ValueError("Identical original trial required at full exit")
                        _work(
                            context,
                            "exit_complete_immutable_history_verification",
                            _roster,
                            context,
                        )
                    except BaseException as error:
                        _remember(context, "full_exit", error)
                        context.invalid = True
                    if context.checked_rows != set(range(len(context.rows))):
                        _remember(
                            context,
                            "incomplete_history",
                            ValueError("Every actual row must be freshly payload-validated"),
                        )
                        context.invalid = True
                    if (
                        context.secondary
                        or context.cleanup_errors
                        or context.last_cleanup_error is not None
                    ):
                        context.invalid = True
                    if (
                        context.final_hooks[0] is not context.prior[0]
                        or context.final_hooks[1] is not context.prior[1]
                    ):
                        context.invalid = True
            except BaseException as error:
                context.invalid = True
                if context.primary is None:
                    context.primary = error
            finally:
                if parent._PREPARING is not attempt or _PENDING is not attempt:
                    context.invalid = True
                    context.last_error = (
                        "reservation",
                        ValueError("Original observation reservation changed"),
                        None,
                    )
                context.active = False
                if parent._ACTIVE and parent._ACTIVE[-1] is context:
                    parent._ACTIVE.pop()
                else:
                    context.invalid = True
            try:
                context.record = _record(
                    context, "failed_observation" if context.invalid else "completed_observation"
                )
            except BaseException as error:
                context.last_error = ("record", error, None)
                context.invalid = True
            # Record/sealing callbacks are fallible too. Sample and repair
            # both hooks after the last writer, not only before full exit.
            for label, getter, setter, original in (
                ("trace", sys.gettrace, sys.settrace, context.prior[1]),
                ("profile", sys.getprofile, sys.setprofile, context.prior[0]),
            ):
                for index in range(3):
                    try:
                        if getter() is original:
                            break
                        context.invalid = True
                        setter(original)
                    except BaseException as error:
                        context.last_error = (label + "_after_record", error, index)
                        context.invalid = True
            final = []
            for label, getter in (("profile", sys.getprofile), ("trace", sys.gettrace)):
                try:
                    final.append(getter())
                except BaseException as error:
                    context.last_error = (label + "_after_record_final", error, None)
                    context.invalid = True
                    final.append(None)
            context.final_hooks = tuple(final)
            if (
                context.final_hooks[0] is not context.prior[0]
                or context.final_hooks[1] is not context.prior[1]
            ):
                context.invalid = True
            if (
                context.invalid
                and context.record is not None
                and context.record.status == "completed_observation"
            ):
                context.raw_record, context.record = context.record, None
            if context.invalid:
                try:
                    _FAILED.append(context)
                except BaseException as secondary:
                    context.failure_recording_error = secondary
                primary = (
                    context.primary
                    if context.primary is not None
                    else (
                        context.last_error[1]
                        if context.last_error is not None
                        else context.entry_error
                    )
                )
                raise HistoryObservationRejected(
                    "Completed-history observation failed", stage="observation", partial=context
                ) from primary
    except BaseException as error:
        attempt["primary"] = error
        if context is None:
            try:
                _FAILED.append(attempt)
            except BaseException as secondary:
                attempt["recording_error"] = secondary
        if isinstance(error, HistoryObservationRejected):
            if error.partial is None:
                error.partial = context if context is not None else attempt
            raise
        raise HistoryObservationRejected(
            "Completed-history admission failed",
            stage="admission",
            partial=context if context is not None else attempt,
        ) from error
    finally:
        if parent._PREPARING is attempt:
            parent._PREPARING = None
        if _PENDING is attempt:
            _PENDING = None
        else:
            attempt["invalid"] = True


def _check_self(context):
    records = _SELF_API if context is None else context.api_bindings
    if context is not None and records is not _SELF_API:
        raise ValueError("Original observation dispatch table changed")
    for (
        holder,
        name,
        actual,
        function,
        code,
        namespace,
        builtins,
        defaults,
        keywords,
        closure,
    ) in records:
        if (
            vars(holder).get(name) is not actual
            or function.__code__ is not code
            or function.__globals__ is not namespace
            or function.__builtins__ is not builtins
            or function.__defaults__ is not defaults
        ):
            raise ValueError("Original observation callable/code/globals changed: " + name)
        current = function.__kwdefaults__ or {}
        if len(current) != len(keywords) or any(
            key not in current or current[key] is not value for key, value in keywords
        ):
            raise ValueError("Original observation keyword defaults changed: " + name)
        cells = function.__closure__ or ()
        if len(cells) != len(closure) or any(
            cell is not old or cell.cell_contents is not value
            for cell, (old, value) in zip(cells, closure, strict=True)
        ):
            raise ValueError("Original observation closure changed: " + name)


def _self_bindings():
    module = sys.modules[__name__]
    rows = [
        (module, name, value, value)
        for name, value in tuple(vars(module).items())
        if type(value) is FunctionType and value.__module__ == __name__
    ]
    rows.append(
        (
            observing_completed,
            "__wrapped__",
            observing_completed.__wrapped__,
            observing_completed.__wrapped__,
        )
    )
    rows.extend(
        (CompletedHistoryObservation, name, value, value)
        for name, value in vars(CompletedHistoryObservation).items()
        if type(value) is FunctionType
    )
    rows.append(
        (
            CompletedHistoryObservation,
            "record",
            CompletedHistoryObservation.record,
            CompletedHistoryObservation.record.fget,
        )
    )
    return tuple(
        (
            holder,
            name,
            actual,
            function,
            function.__code__,
            function.__globals__,
            function.__builtins__,
            function.__defaults__,
            tuple((function.__kwdefaults__ or {}).items()),
            tuple((cell, cell.cell_contents) for cell in (function.__closure__ or ())),
        )
        for holder, name, actual, function in rows
    )


_SELF_API = _self_bindings()
