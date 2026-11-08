"""Metadata-only equivalence to the unchanged recursive record serializer."""

import ast
import builtins
import hashlib
import json
import os
import struct
import subprocess
import sys
import time
from collections import namedtuple
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest

from cells.processes import betse_native_parameter_record_digest as fast
from validation.betse import betse_native_parameter_record_digest_software as software


@pytest.fixture(autouse=True)
def blocked(tmp_path):
    if os.environ.get(software.RELEASE) != "1":
        pytest.skip("Explicit immutable metadata-digest software release required")
    with software.blocked(tmp_path):
        yield


@pytest.mark.parametrize(
    "value",
    (
        None,
        False,
        True,
        0,
        -1,
        2**80,
        "",
        "snowman \u2603 and \U0001f9ec",
        "unpaired \ud800",
        0.0,
        -0.0,
        float("inf"),
        float("-inf"),
        struct.unpack("<d", bytes.fromhex("010000000000f87f"))[0],
        [],
        (),
        {},
        {"b": [1, 2.0, None], "a": (True, {"nested": -0.0})},
    ),
)
def test_record_digest_exact_builtin_equivalence_and_no_mutation(value):
    before = fast.records.record(value)
    expected = fast.records._digest(value)
    assert fast.digest(value) == expected
    assert fast.records.record(value) == before


@pytest.mark.parametrize("bits", ("0000000000000080", "010000000000f87f", "020000000000f87f"))
def test_record_digest_float_payload_is_original_json_bytes(bits):
    value = struct.unpack("<d", bytes.fromhex(bits))[0]
    encoded = json.dumps(
        {"x": {"float64_bits": bits}}, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    assert fast.digest({"x": value}) == hashlib.sha256(encoded).hexdigest()


def test_record_digest_fresh_mutation_and_shared_aliases():
    child = [1, {"value": 3.0}]
    value = {"left": child, "right": child}
    first = fast.digest(value)
    child[1]["value"] = -0.0
    second = fast.digest(value)
    assert first != second and second == fast.records._digest(value)
    child.append(8)
    assert fast.digest(value) != second
    assert value["left"] is value["right"] is child


def test_record_digest_single_audited_identity_per_container_and_fresh_alias_visit():
    shared = [{"x": 1}, 2]
    value = {"a": shared, "b": shared, "empty": (), "nested": [[]]}
    calls, prior = [], sys.getprofile()

    def profile(frame, event, arg):
        if prior is not None:
            prior(frame, event, arg)
        if (
            event == "c_call"
            and arg is builtins.id
            and frame.f_code is fast._metadata_tree.__code__
        ):
            calls.append(frame.f_locals["item"])

    sys.setprofile(profile)
    try:
        projected = fast._metadata_tree(value, fast._LIMITS)
    finally:
        sys.setprofile(prior)
    assert len(calls) == 8 and sum(item is shared for item in calls) == 2
    assert projected == fast.records.record(value)
    assert projected["a"] is not projected["b"] and value["a"] is value["b"] is shared
    shared[0]["x"] = -0.0
    assert fast.digest(value) == fast.records._digest(value)


def test_record_digest_oversized_container_refuses_before_identity_audit():
    calls, prior = [], sys.getprofile()

    def profile(frame, event, arg):
        if prior is not None:
            prior(frame, event, arg)
        if (
            event == "c_call"
            and arg is builtins.id
            and frame.f_code is fast._metadata_tree.__code__
        ):
            calls.append(arg)

    sys.setprofile(profile)
    try:
        result = fast._metadata_tree([1, 2], (1, 3, 64))
    finally:
        sys.setprofile(prior)
    assert result is fast._FALLBACK and not calls


@pytest.mark.parametrize("point", ("identity", "bulk_schedule"))
def test_record_digest_actual_metadata_observer_refusal_keeps_primary_and_cause(point):
    primary, cause, calls = FalseyError("metadata observer"), KeyError("cause"), []
    value = {"current": [1, -0.0]}
    before, prior = fast.records.record(value), sys.getprofile()

    def profile(frame, event, arg):
        if prior is not None:
            prior(frame, event, arg)
        if event == "c_call" and frame.f_code is fast._metadata_tree.__code__:
            match = (
                arg is builtins.id
                if point == "identity"
                else getattr(arg, "__name__", None) == "extend"
            )
            if match:
                calls.append(arg)
                raise primary from cause

    sys.setprofile(profile)
    try:
        with pytest.raises(FalseyError) as caught:
            fast.digest(value)
    finally:
        sys.setprofile(prior)
    assert caught.value is primary and primary.__cause__ is cause and len(calls) == 1
    assert fast.records.record(value) == before


def test_record_digest_sorted_mapping_order_is_unchanged():
    left = {"z": [1, 2], "a": -0.0}
    right = {"a": -0.0, "z": [1, 2]}
    assert fast.digest(left) == fast.digest(right) == fast.records._digest(left)


class StringSubclass(str):
    pass


class FloatSubclass(float):
    pass


class ListSubclass(list):
    pass


@pytest.mark.parametrize(
    "make",
    (
        lambda: MappingProxyType({"x": [2, -0.0]}),
        lambda: namedtuple("Metadata", "x y")(1, -0.0),
        lambda: StringSubclass("actual subtype"),
        lambda: FloatSubclass(1.25),
        lambda: ListSubclass([1, -0.0]),
        lambda: {1: "integer key", 2: "unchanged key handling"},
        lambda: {StringSubclass("key"): 1},
    ),
)
def test_record_digest_unsupported_shapes_use_original_fallback(make):
    value = make()
    assert fast._metadata_tree(value, fast._LIMITS) is fast._FALLBACK
    calls, old = [], sys.getprofile()

    def observe(frame, event, arg):
        if old is not None:
            old(frame, event, arg)
        if event == "call" and frame.f_code is fast.records._digest.__code__:
            calls.append(frame.f_locals["value"])

    sys.setprofile(observe)
    try:
        actual = fast.digest(value)
    finally:
        sys.setprofile(old)
    assert calls == [value] and calls[0] is value
    assert actual == fast.records._digest(value)


def test_record_digest_unsupported_class_does_not_evaluate_type_equality():
    class EqualityTrap(type):
        def __eq__(cls, other):
            raise AssertionError("Exact built-in classification must not call custom equality")

        __hash__ = type.__hash__

    class Metadata(metaclass=EqualityTrap):
        def _asdict(self):
            return {"x": [1, -0.0]}

    value = Metadata()
    assert fast._metadata_tree(value, fast._LIMITS) is fast._FALLBACK
    assert fast.digest(value) == fast.records._digest(value)


@pytest.mark.parametrize("shape", ("root", "list", "mapping"))
def test_record_digest_internal_token_as_input_retains_original_error(shape):
    value = fast._EXIT
    if shape == "list":
        value = [value]
    elif shape == "mapping":
        value = {"unwind_token": value}
    with pytest.raises(TypeError) as expected:
        fast.records._digest(value)
    with pytest.raises(TypeError) as actual:
        fast.digest(value)
    assert str(actual.value) == str(expected.value)


@pytest.mark.parametrize("kind", ("nodes", "depth", "bytes", "pending", "cycle"))
def test_record_digest_bounded_projection_refuses_before_unbounded_copy(kind):
    if kind == "nodes":
        value, limits = list(range(17)), (16, 8, 1024)
    elif kind == "depth":
        value, limits = [[[[[0]]]]], (32, 3, 1024)
    elif kind == "bytes":
        value, limits = {"long": "abcdef"}, (32, 8, 64)
    elif kind == "pending":
        value, limits = [[0] * 8, [0] * 8], (16, 8, 1024)
    else:
        value, limits = [], (32, 8, 1024)
        value.append(value)
    assert fast._metadata_tree(value, limits) is fast._FALLBACK


def test_record_digest_real_depth_limit_falls_back_to_same_original_result():
    value = 7
    for _ in range(fast.MAX_DEPTH + 2):
        value = [value]
    assert fast._metadata_tree(value, fast._LIMITS) is fast._FALLBACK
    assert fast.digest(value) == fast.records._digest(value)


@pytest.mark.parametrize("kind", ("unsupported", "mixed_keys", "float_subtype_nan", "cycle"))
def test_record_digest_original_error_type_and_message_are_retained(kind):
    if kind == "unsupported":
        value = object()
    elif kind == "mixed_keys":
        value = {1: 0, "a": 1}
    elif kind == "float_subtype_nan":
        value = FloatSubclass("nan")
    else:
        value = []
        value.append(value)
    with pytest.raises((TypeError, ValueError, RecursionError)) as expected:
        fast.records._digest(value)
    with pytest.raises(type(expected.value)) as actual:
        fast.digest(value)
    if kind != "cycle":
        assert str(actual.value) == str(expected.value)


class FalseyError(RuntimeError):
    def __bool__(self):
        return False


@pytest.mark.parametrize("falsey", (False, True))
def test_record_digest_real_audit_identity_denial_stays_primary_in_isolated_process(
    falsey, tmp_path
):
    script = r"""
import json, os, sys
from validation.betse import betse_normal_channel_join_runtime as runtime
from cells.processes import betse_native_parameter_record_digest as fast
class Denied(RuntimeError):
    def __bool__(self):
        if sys.argv[1] == "True":
            return False
        return True
primary, cause = Denied("actual audit denial"), KeyError("cause")
value = {"current": [1, -0.0]}
identity, token, acknowledged, calls, forbidden = id(value), object(), [], [], []
prior = sys.getprofile(), sys.gettrace()
def profile(frame, event, arg):
    name = frame.f_globals.get("__name__", "")
    if event == "call" and (
        name.startswith(("betse.", "numpy.random", "numpy.linalg"))
        or (name.startswith("cells.")
            and name != "cells.processes.betse_native_parameter_record_digest")
    ):
        forbidden.append((name, frame.f_code.co_qualname))
        raise AssertionError("Actual owner/native/operator/RNG body held")
def audit(event, args):
    if event == "cells.metadata.identity_audit_probe" and args == (token,):
        acknowledged.append(True)
    if event == "builtins.id" and args == (identity,):
        calls.append(args)
        raise primary from cause
sys.addaudithook(audit)
sys.audit("cells.metadata.identity_audit_probe", token)
assert acknowledged == [True]
try:
    sys.setprofile(profile)
    try:
        fast.digest(value)
    except Denied as actual:
        assert actual is primary and actual.__cause__ is cause
    else:
        raise AssertionError("Audit veto was bypassed")
finally:
    sys.settrace(prior[1]);sys.setprofile(prior[0])
assert len(calls) == 1 and not forbidden
print(json.dumps(dict(pid=os.getpid(), calls=len(calls), exact_primary=True,
    cause_retained=True, forbidden=forbidden, audit_acknowledged=True,
    hooks_restored=sys.getprofile() is prior[0] and sys.gettrace() is prior[1],
    runtime=runtime.inventory())))
"""
    env = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("CELLS_") and name != "PYTEST_CURRENT_TEST"
    }
    result = subprocess.run(
        [sys.executable, "-B", "-c", script, str(falsey)],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
        check=False,
    )
    (tmp_path / "isolated-id-audit.json").write_text(
        json.dumps(
            dict(
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                falsey=falsey,
                timeout_seconds=30,
            )
        )
    )
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["exact_primary"] and receipt["cause_retained"]
    assert receipt["audit_acknowledged"] and receipt["hooks_restored"]
    assert receipt["calls"] == 1 and not receipt["forbidden"]


@pytest.mark.parametrize("error_type", (RuntimeError, FalseyError))
def test_record_digest_fallback_retains_actual_error_cause_and_single_callback(error_type):
    primary, cause, calls = error_type("original metadata failure"), KeyError("original cause"), []

    class OriginalMetadata:
        def _asdict(self):
            calls.append(self)
            raise primary from cause

    value = OriginalMetadata()
    with pytest.raises(error_type) as got:
        fast.digest(value)
    assert got.value is primary and got.value.__cause__ is cause and calls == [value]


def test_record_digest_inherited_original_entry_error_is_not_retried_or_replaced():
    primary, cause = FalseyError("prior entry observer"), KeyError("cause")
    calls, old = [], sys.getprofile()

    def reject(frame, event, arg):
        if old is not None:
            old(frame, event, arg)
        if event == "call" and frame.f_code is fast.records._digest.__code__:
            calls.append(frame.f_locals["value"])
            raise primary from cause

    value = MappingProxyType({"x": 1})
    sys.setprofile(reject)
    try:
        with pytest.raises(FalseyError) as got:
            fast.digest(value)
    finally:
        sys.setprofile(old)
    assert got.value is primary and primary.__cause__ is cause and calls == [value]


@pytest.mark.parametrize(
    "mutation",
    (
        "record",
        "digest",
        "record_code",
        "digest_code",
        "record_defaults",
        "record_keywords",
        "numpy",
        "ndarray",
        "mappingproxy",
        "pack",
        "sha256",
        "dumps",
        "json_keywords",
        "encoder_code",
        "encoder_dispatch",
        "projection_code",
        "projection_pack",
        "guard_code",
    ),
)
def test_record_digest_callable_helper_default_and_global_drift_refuses(monkeypatch, mutation):
    assert fast.digest({"positive": [1, 2.0]}) == fast.records._digest({"positive": [1, 2.0]})

    def substitute(value=None, *args, **kwargs):
        raise AssertionError("Changed helper must not execute")

    with monkeypatch.context() as patch:
        if mutation in ("record", "digest"):
            patch.setattr(fast.records, "record" if mutation == "record" else "_digest", substitute)
        elif mutation in ("record_code", "digest_code"):
            function = fast._RECORD if mutation == "record_code" else fast._DIGEST
            patch.setattr(function, "__code__", substitute.__code__)
        elif mutation in ("record_defaults", "record_keywords"):
            patch.setattr(
                fast._RECORD,
                "__defaults__" if mutation == "record_defaults" else "__kwdefaults__",
                (None,) if mutation == "record_defaults" else {},
            )
        elif mutation == "numpy":
            patch.setattr(fast.records, "np", SimpleNamespace())
        elif mutation == "ndarray":
            patch.setattr(fast.records.np, "ndarray", object)
        elif mutation == "mappingproxy":
            patch.setattr(fast.records, "MappingProxyType", dict)
        elif mutation == "pack":
            patch.setattr(struct, "pack", substitute)
        elif mutation == "sha256":
            patch.setattr(hashlib, "sha256", substitute)
        elif mutation == "dumps":
            patch.setattr(json, "dumps", substitute)
        elif mutation == "json_keywords":
            patch.setitem(json.dumps.__kwdefaults__, "ensure_ascii", False)
        elif mutation == "encoder_code":
            patch.setattr(json.JSONEncoder.encode, "__code__", substitute.__code__)
        elif mutation == "encoder_dispatch":
            patch.setattr(json.JSONEncoder, "__getattribute__", substitute, raising=False)
        elif mutation == "projection_code":
            patch.setattr(fast._metadata_tree, "__code__", substitute.__code__)
        elif mutation == "projection_pack":
            patch.setattr(fast, "_PACK", substitute)
        else:
            patch.setattr(fast._authenticate, "__code__", substitute.__code__)
        with pytest.raises(ValueError, match="[Mm]etadata|[Oo]riginal"):
            fast.digest({"positive": [1, 2.0]})


def test_record_digest_foreign_serializer_refuses_before_data_access():
    class Untouched:
        @property
        def _asdict(self):
            raise AssertionError("Foreign serializer must refuse before touching value")

    with pytest.raises(ValueError, match="serializer identity"):
        fast.digest(Untouched(), selected=SimpleNamespace())


def test_record_digest_midcall_mutation_refuses_without_reusing_prior_digest(monkeypatch):
    original, old, changed = fast._metadata_tree.__code__, sys.getprofile(), []

    def mutate(frame, event, arg):
        if old is not None:
            old(frame, event, arg)
        if event == "return" and frame.f_code is original:
            changed.append(True)
            monkeypatch.setattr(fast, "_PACK", lambda *_: b"changed")

    sys.setprofile(mutate)
    try:
        with pytest.raises(ValueError, match="global"):
            fast.digest({"current": [1, 2.0]})
    finally:
        sys.setprofile(old)
        monkeypatch.undo()
    assert changed == [True]


def test_record_digest_yaml_prefix_uses_same_original_serializer_and_binding():
    path = Path(fast.__file__).with_name("betse_native_parameter_yaml_prefix.py")
    tree = ast.parse(path.read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_digest")
    namespace = dict(
        __name__="metadata_yaml_digest_route",
        record_digest=fast,
        parameters=SimpleNamespace(
            inherited=SimpleNamespace(
                tissue=SimpleNamespace(core=SimpleNamespace(records=fast.records))
            )
        ),
    )
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
    value = {"live metadata": [1, -0.0]}
    assert namespace["_digest"](value) == fast.records._digest(value)
    assert "record_digest" in node.body[0].value.func.value.id
    bindings = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_bindings"
    )
    assert any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "record_digest"
        and n.func.attr == "bindings"
        for n in ast.walk(bindings)
    )


def test_record_digest_metadata_profile_reduces_recursive_record_entries(tmp_path):
    value = {f"row{i:03d}": [(i, j, -0.0, {"name": str(j)}) for j in range(16)] for i in range(32)}
    results = []
    for label, function in (("original", fast.records._digest), ("iterative", fast.digest)):
        counts, old = {"record": 0, "python_calls": 0}, sys.getprofile()

        def observe(frame, event, arg, previous=old, measured=counts):
            if previous is not None:
                previous(frame, event, arg)
            if event == "call":
                measured["python_calls"] += 1
                if frame.f_code is fast.records.record.__code__:
                    measured["record"] += 1

        start = time.perf_counter()
        sys.setprofile(observe)
        try:
            result = function(value)
        finally:
            sys.setprofile(old)
        results.append(
            dict(label=label, sha256=result, seconds=time.perf_counter() - start, **counts)
        )
    assert results[0]["sha256"] == results[1]["sha256"]
    assert results[0]["record"] > 2000 and results[1]["record"] == 0
    assert results[1]["python_calls"] < results[0]["python_calls"]
    (tmp_path / "metadata-profile.json").write_text(
        json.dumps(
            dict(rows=results, scope="synthetic metadata only; no SEED speed claim"), indent=2
        )
        + "\n"
    )
