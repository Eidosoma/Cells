"""Synthetic contract harness. Every real native entry point remains forbidden."""

import dataclasses
import json
import os
import struct
from types import SimpleNamespace

import numpy as np

from cells.processes import betse_native_single_cell_core_preparation as core


class SyntheticSourceCause(Exception):
    pass


class SyntheticSourceFailure(Exception):
    pass


class SyntheticObservationFailure(Exception):
    pass


class SyntheticCaptureCause(Exception):
    pass


class SyntheticCaptureFailure(Exception):
    pass


class SyntheticStringFailure(Exception):
    def __str__(self):
        raise SyntheticCaptureFailure("source exception formatting failed")


class SyntheticRecoveryFailure(Exception):
    pass


def encode(value, memo=None):
    """Independent evidence transport; no production sealing or exception str."""
    memo = {} if memo is None else memo
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is float:
        return dict(binary64_bits=struct.pack(">d", value).hex())
    if isinstance(value, bytes):
        return dict(bytes_hex=value.hex())
    if id(value) in memo:
        return dict(ref=memo[id(value)])
    token = len(memo)
    memo[id(value)] = token
    tag = dict(id=token, type=type(value).__module__ + "." + type(value).__qualname__)
    if isinstance(value, np.ndarray):
        return dict(
            tag,
            dtype=value.dtype.str,
            shape=list(value.shape),
            data=value.tobytes().hex() if not value.dtype.hasobject else None,
            items=None if not value.dtype.hasobject else [encode(v, memo) for v in value.flat],
        )
    if isinstance(value, np.generic):
        return dict(tag, dtype=value.dtype.str, bits=value.tobytes().hex())
    if isinstance(value, BaseException):
        frames, tb = [], value.__traceback__
        while tb is not None:
            frames.append(
                dict(
                    file=tb.tb_frame.f_code.co_filename,
                    function=tb.tb_frame.f_code.co_name,
                    line=tb.tb_lineno,
                )
            )
            tb = tb.tb_next
        return dict(
            tag,
            args=encode(value.args, memo),
            cause=encode(value.__cause__, memo),
            context=encode(value.__context__, memo),
            suppress_context=value.__suppress_context__,
            frames=frames,
        )
    if isinstance(value, dict):
        return dict(tag, items=[[encode(k, memo), encode(v, memo)] for k, v in value.items()])
    if isinstance(value, (list, tuple)):
        return dict(tag, items=[encode(v, memo) for v in value])
    if dataclasses.is_dataclass(value):
        return dict(
            tag,
            fields={
                f.name: encode(getattr(value, f.name), memo) for f in dataclasses.fields(value)
            },
        )
    if hasattr(value, "__dict__") and not isinstance(value, type):
        return dict(tag, fields=encode(vars(value), memo))
    return dict(tag, representation_available=False)


def save(path, label, value):
    with (path / (label + ".json")).open("x") as stream:
        json.dump(encode(value), stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def event_signature(events):
    return [(e.sequence, e.kind, e.method, e.depth, e.payload.identity) for e in events]


def harness(monkeypatch, *, outcome="success", warning=None):
    calls = dict(
        native_attempts=[],
        synthetic_constructor=0,
        synthetic_pre_mesh=0,
        synthetic_core=0,
        real_rng_attempts=[],
        capture_attempts=[],
    )
    errors = {}
    original_snapshot = core.caches.snapshot
    point_ids = ("synthetic-v0", "synthetic-v1")

    def attributes(marker):
        raw = {name: None for name in core.REQUIRED_PRE_MESH_FIELDS}
        raw.update(n_tverts=2, n_tedges=1, n_tcell=0, make_all_operators=False, single_cell=True)
        raw["synthetic_marker"] = marker
        return raw

    def event(observer, method, marker):
        observer.stack.append(method)
        try:
            observer.add("synthetic-prefix", dict(marker=marker, synthetic_only=True))
        finally:
            observer.stack.pop()

    expected_observer = core.initial._Observer(point_ids)
    event(expected_observer, "synthetic-constructor", "constructor")
    event(expected_observer, "synthetic-pre_mesh", "pre_mesh")
    constructed = original_snapshot(attributes("constructed"))
    before = original_snapshot(attributes("ready"))
    stream = SimpleNamespace(identity="synthetic-stream", classification="software-only")
    base = SimpleNamespace(
        constructor_point_ids=point_ids, constructor_kwargs={}, stream_before=stream
    )
    parent = SimpleNamespace(
        constructed_cache=constructed,
        cache=before,
        stream_after_constructor=stream,
        stream_after=stream,
        retained_point_ids=point_ids,
        events=tuple(expected_observer.events),
        warnings=() if warning is None else (warning,),
    )
    request = SimpleNamespace(
        identity="synthetic-request", initial_request=base, initial_state=parent
    )

    def forbidden(*args, **kwargs):
        calls["native_attempts"].append("forbidden-native-entry")
        raise AssertionError("A synthetic contract check reached actual native source work")

    actual_runtime = core._Runtime
    monkeypatch.setattr(core.initial, "validate_state", forbidden)
    monkeypatch.setattr(core.initial, "prepare", forbidden)
    monkeypatch.setattr(core.initial.image_stage, "prepare", forbidden)
    monkeypatch.setattr(core.initial.image_stage.lattice, "generate", forbidden)
    monkeypatch.setattr(core.np.linalg, "pinv", forbidden)
    monkeypatch.setattr(core.initial._Runtime, "__init__", forbidden)
    monkeypatch.setattr(core.initial._Runtime, "pre_mesh", forbidden)
    monkeypatch.setattr(core.initial.source.Kernel, "__init__", forbidden)
    monkeypatch.setattr(core.initial.source.Kernel, "pre_mesh", forbidden)
    for name in ("__init__", "pre_mesh", "create_core_operators"):
        monkeypatch.setattr(actual_runtime, name, forbidden)
    monkeypatch.setattr(core.lifecycle.source.LifecycleKernel, "create_core_operators", forbidden)
    monkeypatch.setattr(core, "validate_request", lambda value: value)

    class SyntheticRng:
        def set_state(self, value):
            self.saved = value

        def get_state(self):
            return self.saved

    monkeypatch.setattr(core.np.random, "RandomState", lambda seed: SyntheticRng())
    monkeypatch.setattr(core.initial, "_rng_stream", lambda rng: stream)
    monkeypatch.setattr(core.initial, "_Random", lambda rng, observer: SimpleNamespace(rng=rng))
    monkeypatch.setattr(
        core.initial.streams,
        "native_stream_manifest",
        lambda value: dict(state=["synthetic_rng", [0], 0, 0, 0.0], synthetic_only=True),
    )

    class SyntheticKernel:
        def __init__(self, **kwargs):
            calls["synthetic_constructor"] += 1
            self.__dict__.update(attributes("constructed"))
            event(self._cells_observer, "synthetic-constructor", "constructor")

        def pre_mesh(self):
            calls["synthetic_pre_mesh"] += 1
            self.synthetic_marker = "ready"
            event(self._cells_observer, "synthetic-pre_mesh", "pre_mesh")
            if warning is not None:
                core.warnings.warn(warning, RuntimeWarning)

        def create_core_operators(self):
            calls["synthetic_core"] += 1
            self._cells_observer.add("synthetic-core-enter", dict(synthetic_only=True))
            if outcome != "success":
                try:
                    raise SyntheticSourceCause("retained synthetic source cause")
                except SyntheticSourceCause as cause:
                    errors["source_cause"] = cause
                    primary = (
                        SyntheticStringFailure("unprintable synthetic source failure")
                        if outcome == "bad-str"
                        else SyntheticSourceFailure("source failure")
                    )
                    errors["source"] = primary
                    if outcome == "observation-failure":
                        try:
                            raise primary from cause
                        except SyntheticSourceFailure as original:
                            observation = SyntheticObservationFailure("observer capture failure")
                            errors["boundary"] = observation
                            raise observation from original
                    if outcome == "cycle":
                        # CPython removes a would-be context cycle during raise.
                        # An explicit cause cycle survives and tests the guard.
                        cause.__cause__ = primary
                    raise primary from cause
            # Literal synthetic array data; no native incidence or pinv routine.
            self.delta_tri_0 = np.asarray([[-1.0, 1.0]])
            self.delta_tri_0_inv = np.asarray([[-0.5], [0.5]])

    monkeypatch.setattr(core, "_Runtime", SyntheticKernel)
    return SimpleNamespace(
        request=request,
        base=base,
        parent=parent,
        calls=calls,
        errors=errors,
        original_snapshot=original_snapshot,
        stream=stream,
    )


def inject_capture(monkeypatch, h, point):
    def fail():
        try:
            raise SyntheticCaptureCause("retained synthetic capture cause")
        except SyntheticCaptureCause as cause:
            error = SyntheticCaptureFailure("capture failure at " + point)
            h.errors["capture_cause"], h.errors["capture"] = cause, error
            raise error from cause

    if point in ("final_snapshot", "initial_snapshot"):
        import sys

        def snapshot(value):
            caller = sys._getframe(1).f_code.co_name
            if caller == "_incomplete_capture":
                raise AssertionError("Recovery attempted serialization again")
            if caller == ("_seal_trial" if point == "final_snapshot" else "prepare"):
                h.calls["capture_attempts"].append(point)
                fail()
            return h.original_snapshot(value)

        monkeypatch.setattr(core.caches, "snapshot", snapshot)
    elif point == "final_stream":
        import sys

        def stream(rng):
            if sys._getframe(1).f_code.co_name == "_seal_trial":
                h.calls["capture_attempts"].append(point)
                fail()
            return h.stream

        monkeypatch.setattr(core.initial, "_rng_stream", stream)
    elif point == "State":

        def state(*args, **kwargs):
            h.calls["capture_attempts"].append(point)
            fail()

        monkeypatch.setattr(core, "State", state)
    else:
        target, attr = (
            (core, "state_record")
            if point == "state_record"
            else (core.records, "_digest")
            if point == "identity_digest"
            else (core, "replace")
        )

        def seal(*args, **kwargs):
            h.calls["capture_attempts"].append(point)
            fail()

        monkeypatch.setattr(target, attr, seal)


def exercise(h, evidence):
    """Archive inputs and actual returns/errors before any test assertion."""
    save(
        evidence,
        "before-prepare",
        dict(request=h.request, calls=h.calls, synthetic_only=True, native_execution=False),
    )
    try:
        result = core.prepare(h.request)
    except BaseException as error:
        value = dict(
            error=error,
            request=h.request,
            calls=h.calls,
            synthetic_only=True,
            native_execution=False,
        )
        if isinstance(error, core.CorePrerequisiteRejected):
            value.update(
                parent_request=error.parent_request,
                parent_state=error.parent_state,
                trial=error.trial,
                partial=error.partial,
                source_error=error.source_error,
                capture_error=error.capture_error,
                source_stage=error.source_stage,
                capture_stage=error.capture_stage,
            )
        save(evidence, "actual-exception", value)
        raise
    else:
        save(
            evidence,
            "actual-return",
            dict(result=result, calls=h.calls, synthetic_only=True, native_execution=False),
        )
        return result
